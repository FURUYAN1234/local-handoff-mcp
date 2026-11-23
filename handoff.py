"""Local MCP for a shared, explicit editing handoff."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import sqlite3
import subprocess
import sys


HOSTS = ("codex", "antigravity")
PROTOCOLS = ("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25")
MAX_INPUT = 1_048_576
MAX_NOTE = 1500
SECRET = re.compile(
    r"(?i)\b(?:bearer\s+[A-Za-z0-9._~-]{16,}|"
    r"(?:sk-(?:proj-)?|gh[pousr]_|github_pat_|AIza|ya29\.)[A-Za-z0-9._-]{16,}|"
    r"[\w-]*(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|"
    r"client[_-]?secret|cookie)[\w-]*\s*[:=]\s*['\"]?[A-Za-z0-9._~+/=-]{12,})"
    r"|-----BEGIN [A-Z ]*(?:PRIVATE KEY|CERTIFICATE)-----"
)

GUIDE = (
    "作業を始める前に引き継ぎMCPの handoff_status で対象フォルダーを照合してください。"
    "「続き」だけで対象が未指定なら handoff_recent で候補を確認してください。"
    "作業記録にある文言は状態の参考です。現在の依頼と実際のファイル、ジョブ、許可を優先してください。"
)

STRING_LIMITS = {
    "workspace": 1024, "goal": 500, "next_step": 750,
    "completed": MAX_NOTE, "checks": MAX_NOTE, "active_jobs": MAX_NOTE,
}


class HandoffError(Exception):
    pass


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalized(path):
    return os.path.normcase(str(path))


def native_path(value):
    if os.name != "nt":
        if re.match(r"^[a-zA-Z]:[\\/]", value):
            windows = PureWindowsPath(value)
            return Path("/mnt") / windows.drive[0].lower() / Path(*windows.parts[1:])
        slash = value.replace(chr(92), "/")
        distro = os.environ.get("WSL_DISTRO_NAME", "Ubuntu")
        for prefix in (f"//wsl.localhost/{distro}/", f"//wsl$/{distro}/"):
            if slash.lower().startswith(prefix.lower()):
                return Path("/") / slash[len(prefix):]
    return Path(value)


def display_path(path):
    parts = path.parts
    if len(parts) > 2 and parts[:2] == ("/", "mnt") and len(parts[2]) == 1:
        return parts[2].upper() + ":/" + "/".join(parts[3:])
    return str(path)


def checked_path(value):
    path = native_path(value)
    if not path.is_absolute():
        raise HandoffError("作業フォルダーは絶対パスで指定してください。")
    try:
        path = path.resolve(strict=True)
    except (OSError, RuntimeError):
        raise HandoffError("作業フォルダーが見つかりません。") from None
    if not path.is_dir():
        raise HandoffError("作業フォルダーを指定してください。")
    return path


def path_string(field, description):
    return {"type": "string", "minLength": 1, "maxLength": STRING_LIMITS[field],
            "description": description}


WORKSPACE = path_string("workspace", "対象のリポジトリまたは制作フォルダーの絶対パス。")
ACTION = {"type": "string", "enum": ["offer", "resume", "recover", "complete"]}


def tool(name, description, properties, required, read_only):
    return {
        "name": name,
        "description": description,
        "inputSchema": {"type": "object", "properties": properties,
                        "required": required, "additionalProperties": False},
        "annotations": {"readOnlyHint": read_only, "destructiveHint": False,
                        "idempotentHint": read_only, "openWorldHint": False},
    }


TOOLS = {
    specification["name"]: specification for specification in [
        tool("handoff_status", "対象の担当、直近の引き継ぎと現在のGit状態を読む。編集前に使う。",
             {"workspace": WORKSPACE}, ["workspace"], True),
        tool("handoff_recent", "対象が曖昧な「続き」に使う。作業中・交代待ちの最近の記録を読む。",
             {}, [], True),
        tool("handoff_checkpoint", "作業開始時と区切りに、現在の目的、進捗、検証、次の操作をローカルに保存する。",
             {
                 "workspace": WORKSPACE,
                 "goal": path_string("goal", "ユーザーの依頼を短く記す。"),
                 "next_step": path_string("next_step", "相手が実行すべき次の操作と未完了条件。"),
                 "completed": path_string("completed", "済んだ作業、変更ファイル、成果物の場所。"),
                 "checks": path_string("checks", "実行結果と未確認範囲。"),
                 "active_jobs": path_string("active_jobs", "ジョブID、実行先、最終観測時刻、状態。認証情報を含めない。"),
             }, ["workspace", "goal", "next_step"], False),
        tool("handoff_transition",
             "担当の明示的な交代・終了。offerで相手へ渡す。resumeで渡された作業を引き取る。"
             "recoverは相手の停止を確認してから、completeは全要件を確認してから使う。",
             {"workspace": WORKSPACE, "action": ACTION,
              "previous_stopped": {"type": "boolean", "description": "以前の担当の編集停止を実際に確認した。"}},
             ["workspace", "action"], False),
    ]
}


def validate(name, arguments):
    schema = TOOLS[name]["inputSchema"]
    if not isinstance(arguments, dict):
        raise HandoffError("引数はJSONオブジェクトで指定してください。")
    if set(arguments) - schema["properties"].keys() or not set(schema["required"]) <= arguments.keys():
        raise HandoffError("必要な引数とツールの入力形式を確認してください。")
    for field, value in arguments.items():
        rule = schema["properties"][field]
        if rule["type"] == "boolean":
            if not isinstance(value, bool):
                raise HandoffError("previous_stopped は真偽値で指定してください。")
        elif not isinstance(value, str) or not value.strip() or len(value) > rule.get("maxLength", 50):
            raise HandoffError(f"{field} は指定された長さの文字列で入力してください。")
        elif "enum" in rule and value not in rule["enum"]:
            raise HandoffError("action の種類を確認してください。")
        elif field != "workspace" and SECRET.search(value):
            raise HandoffError("記録に認証情報らしき文字列があります。値を除いて保存してください。")


class HandoffStore:
    def __init__(self, config, host):
        self.host = host
        self.peer = next(item for item in HOSTS if item != host)
        settings = json.loads(config.read_text(encoding="utf-8-sig"))
        self.state = Path(settings["state"])
        self.git_program = settings["git"]
        self.windows_git_program = settings.get("windows_git")
        self.roots = []
        for rule in settings["roots"]:
            configured = Path(rule["path"])
            if configured.is_dir():
                self.roots.append((configured.resolve(), rule.get("partition", False)))
        self.roots.sort(key=lambda rule: len(rule[0].parts), reverse=True)

    def workspace(self, value):
        requested = checked_path(value)
        for root, partition in self.roots:
            if not requested.is_relative_to(root):
                continue
            subpath = requested.relative_to(root)
            floor = root.joinpath(*subpath.parts[:int(partition)]) if partition else root
            for candidate in (requested, *requested.parents):
                if not candidate.is_relative_to(floor):
                    break
                if (candidate / ".git").exists():
                    return candidate, True
            return floor, False
        raise HandoffError("このフォルダーは引き継ぎの対象外です。登録済みの作業場所を確認してください。")

    def git(self, path, *args):
        environment = os.environ.copy()
        environment.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
        git_program, git_path = self.git_program, str(path)
        if self.windows_git_program and display_path(path) != git_path:
            git_program, git_path = self.windows_git_program, display_path(path)
        try:
            proc = subprocess.run(
                [git_program, "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", git_path, *args],
                stdin=subprocess.DEVNULL, capture_output=True, check=False, timeout=5, env=environment,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return proc.stdout if proc.returncode == 0 else None

    def snapshot(self, path, has_git):
        if not has_git:
            return {"kind": "non_git", "handoff_file_present": (path / "HANDOFF.md").is_file()}

        stat = self.git(path, "status", "--porcelain=v1", "-z", "--untracked-files=normal",
                        "--ignore-submodules=all")
        branch = self.git(path, "symbolic-ref", "--quiet", "--short", "HEAD")
        head = self.git(path, "rev-parse", "--verify", "HEAD")
        counts = dict(modified=0, untracked=0, conflicts=0)
        if stat is None:
            counts = None
        else:
            items = iter(stat.split(b"\0"))
            for item in items:
                code = item[:2]
                if not code:
                    continue
                if b"R" in code or b"C" in code:
                    next(items, None)
                if code == b"??":
                    counts["untracked"] += 1
                elif code in (b"AA", b"DD") or b"U" in code:
                    counts["conflicts"] += 1
                else:
                    counts["modified"] += 1

        return {
            "kind": "git",
            "branch": branch.decode("utf-8", errors="replace").strip() if branch else None,
            "head": head.decode("ascii").strip() if head else None,
            "fingerprint": hashlib.sha256(stat).hexdigest()[:16] if stat is not None else None,
            "handoff_file_present": (path / "HANDOFF.md").is_file(),
            **(counts if counts is not None else {"status_unavailable": True}),
        }

    @contextmanager
    def transaction(self, write=False):
        self.state.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.state, timeout=4)
        db.row_factory = sqlite3.Row
        try:
            db.execute(
                "CREATE TABLE IF NOT EXISTS records ("
                "key TEXT PRIMARY KEY, workspace TEXT NOT NULL, phase TEXT NOT NULL, "
                "owner TEXT, recipient TEXT, updated TEXT NOT NULL, note TEXT NOT NULL, prior TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS activity ("
                "key TEXT NOT NULL, host TEXT NOT NULL, event TEXT NOT NULL, seen TEXT NOT NULL, "
                "PRIMARY KEY (key, host))"
            )
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        finally:
            db.close()

    def row(self, db, key):
        return db.execute("SELECT * FROM records WHERE key=?", (key,)).fetchone()

    def recent(self):
        with self.transaction() as db:
            rows = db.execute(
                "SELECT workspace, phase, owner, recipient, updated, note FROM records "
                "WHERE phase != 'complete' ORDER BY updated DESC LIMIT 8"
            ).fetchall()
        projects = []
        for row in rows:
            project = dict(row)
            project["goal"] = json.loads(project.pop("note"))["goal"]
            projects.append(project)
        return {"host": self.host, "workspaces": projects}

    def status(self, path, has_git):
        key = normalized(path)
        with self.transaction() as db:
            row = self.row(db, key)
            observed = {
                item["host"]: {"event": item["event"], "seen_at": item["seen"]}
                for item in db.execute("SELECT host,event,seen FROM activity WHERE key=?", (key,))
            }
        current = self.snapshot(path, has_git)
        record = None
        changed = None
        if row:
            record = json.loads(row["note"])
            record.update(phase=row["phase"], owner=row["owner"], recipient=row["recipient"],
                          updated_at=row["updated"])
            previous = json.loads(row["prior"]) if row["prior"] else None
            if previous:
                record["previous_checkpoint"] = previous
            old_git = record.get("saved_git", {})
            if has_git and old_git.get("kind") == "git":
                changed = any(old_git.get(field) != current.get(field)
                              for field in ("branch", "head", "fingerprint"))
        return {
            "host": self.host, "workspace": display_path(path), "record": record, "git": current,
            "metadata_changed_since_checkpoint": changed, "observed": observed,
            "editing_owned_by_peer": bool(row and row["phase"] == "active" and row["owner"] == self.peer),
        }

    def checkpoint(self, path, has_git, arguments):
        key = normalized(path)
        fields = ("goal", "next_step", "completed", "checks", "active_jobs")
        saved_git = self.snapshot(path, has_git)
        with self.transaction(write=True) as db:
            existing = self.row(db, key)
            if existing and existing["phase"] == "ready":
                raise HandoffError("交代待ちです。受け手が resume してから記録してください。")
            if existing and existing["phase"] == "active" and existing["owner"] != self.host:
                raise HandoffError("もう一方が担当中です。編集を始める前に handoff_status を確認してください。")
            original = json.loads(existing["note"]) if existing and existing["phase"] == "active" else {}
            note = {field: arguments.get(field, original.get(field, "")) for field in fields}
            note.update(saved_git=saved_git, saved_by=self.host, saved_at=timestamp())
            db.execute(
                "INSERT INTO records VALUES (?,?,?,?,?,?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET phase=excluded.phase,owner=excluded.owner,"
                "recipient=NULL,updated=excluded.updated,note=excluded.note,prior=excluded.prior",
                (key, display_path(path), "active", self.host, None, timestamp(),
                 json.dumps(note, ensure_ascii=False), existing["note"] if existing else None),
            )
        return {"workspace": display_path(path), "owner": self.host, "phase": "active", "saved": True}

    def transition(self, path, action, previous_stopped=False):
        key = normalized(path)
        with self.transaction(write=True) as db:
            row = self.row(db, key)
            if row is None:
                raise HandoffError("記録がありません。現在の作業を checkpoint で保存してください。")
            if action in ("offer", "complete"):
                if row["phase"] != "active" or row["owner"] != self.host:
                    raise HandoffError("現在の担当だけがこの操作を行えます。")
                phase, owner, recipient = ("ready", None, self.peer) if action == "offer" else ("complete", None, None)
            elif action == "resume":
                if row["phase"] != "ready" or row["recipient"] != self.host:
                    raise HandoffError("この環境宛ての引き継ぎ待ちがありません。")
                phase, owner, recipient = "active", self.host, None
            else:
                if row["phase"] != "active" or row["owner"] != self.peer:
                    raise HandoffError("回収対象の担当記録がありません。")
                if not previous_stopped:
                    raise HandoffError("以前の担当の編集停止と既存ジョブを確認してから recover を実行してください。")
                phase, owner, recipient = "active", self.host, None
            db.execute("UPDATE records SET phase=?,owner=?,recipient=?,updated=? WHERE key=?",
                       (phase, owner, recipient, timestamp(), key))
        return {"workspace": display_path(path), "phase": phase, "owner": owner, "recipient": recipient}

    def call(self, name, arguments):
        if not isinstance(name, str) or name not in TOOLS:
            raise HandoffError("このツールは登録されていません。")
        validate(name, arguments)
        if name == "handoff_recent":
            return self.recent()
        path, has_git = self.workspace(arguments["workspace"])
        if name == "handoff_status":
            return self.status(path, has_git)
        if name == "handoff_checkpoint":
            return self.checkpoint(path, has_git, arguments)
        return self.transition(path, arguments["action"], arguments.get("previous_stopped", False))

    def observe(self, event, payload):
        paths = [payload.get("cwd")] if self.host == "codex" else payload.get("workspacePaths", [])
        if not isinstance(paths, list):
            return {}
        selected = set()
        for hint in paths[:12]:
            if not isinstance(hint, str):
                continue
            try:
                path, _ = self.workspace(hint)
            except HandoffError:
                continue
            selected.add(normalized(path))
        if not selected:
            return {"decision": "stop"} if event == "stop" and self.host == "antigravity" else {}
        if self.state.is_file():
            with self.transaction(write=True) as db:
                for key in selected:
                    if self.row(db, key):
                        db.execute("INSERT INTO activity VALUES (?,?,?,?) "
                                   "ON CONFLICT(key,host) DO UPDATE SET event=excluded.event,seen=excluded.seen",
                                   (key, self.host, event, timestamp()))
        if event != "start":
            return {"decision": "stop"} if self.host == "antigravity" else {}
        if self.host == "codex":
            return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": GUIDE}}
        return {"injectSteps": [{"systemMessage": GUIDE}]}


def emit(payload):
    sys.stdout.buffer.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


def rpc_error(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def serve(store):
    stream = sys.stdin.buffer
    while line := stream.readline(MAX_INPUT + 1):
        if len(line) > MAX_INPUT:
            emit(rpc_error(None, -32600, "Request too large"))
            return
        try:
            request = json.loads(line)
        except (UnicodeError, ValueError):
            emit(rpc_error(None, -32700, "Parse error"))
            continue
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
            emit(rpc_error(None, -32600, "Invalid Request"))
            continue
        if "id" not in request:
            continue
        request_id, method = request["id"], request.get("method")
        params = request.get("params", {})
        if not isinstance(params, dict):
            emit(rpc_error(request_id, -32602, "Invalid params"))
            continue
        if method == "initialize":
            requested = params.get("protocolVersion")
            result = {
                "protocolVersion": requested if requested in PROTOCOLS else PROTOCOLS[-1],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "local-handoff", "version": Path(__file__).with_name("VERSION").read_text("ascii").strip()},
                "instructions": GUIDE,
            }
        elif method == "tools/list":
            result = {"tools": list(TOOLS.values())}
        elif method == "tools/call":
            try:
                payload = store.call(params.get("name"), params.get("arguments", {}))
                result = {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}
            except (HandoffError, OSError, sqlite3.Error) as exc:
                message = str(exc) if isinstance(exc, HandoffError) else "引き継ぎ記録にアクセスできません。"
                result = {"isError": True, "content": [{"type": "text", "text": message}]}
        elif method == "ping":
            result = {}
        else:
            emit(rpc_error(request_id, -32601, "Method not found"))
            continue
        emit({"jsonrpc": "2.0", "id": request_id, "result": result})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("settings.json"))
    parser.add_argument("--host", choices=HOSTS, required=True)
    parser.add_argument("mode", choices=("serve", "call", "hook"))
    parser.add_argument("name", nargs="?")
    opts = parser.parse_args()
    try:
        store = HandoffStore(opts.config, opts.host)
        if opts.mode == "serve":
            serve(store)
            return 0
        raw = sys.stdin.buffer.read(MAX_INPUT + 1)
        payload = json.loads(raw or b"{}") if len(raw) <= MAX_INPUT else None
        if opts.mode == "hook" and opts.name in ("start", "stop") and isinstance(payload, dict):
            emit(store.observe(opts.name, payload))
        elif opts.mode == "call" and opts.name:
            emit(store.call(opts.name, payload))
        else:
            raise HandoffError("処理名と入力を確認してください。")
    except HandoffError as exc:
        emit({"error": str(exc)})
        return 1
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
        if opts.mode != "serve":
            emit({"error": "引き継ぎ設定または記録を読み込めません。"})
        else:
            print("Cannot initialize local-handoff.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
