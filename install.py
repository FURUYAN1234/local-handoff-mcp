"""Install or update Local Handoff MCP from Windows through Ubuntu in WSL."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import tomllib

from handoff import checked_path, HandoffError
from verify_package import verify


NAME = "local_handoff"
RUNTIME_FILES = ("handoff.py", "VERSION", "clients.py", "dashboard.py", "dashboard.css", "MANUAL.md")
RULE_START = "<!-- local-handoff-mcp:begin -->"
RULE_END = "<!-- local-handoff-mcp:end -->"
RULE = """<!-- local-handoff-mcp:begin -->
## Local Handoff MCP / ローカルの作業引き継ぎ

For multi-step work in a registered folder, use handoff_status with its absolute path before editing. If the target is unclear, compare handoff_recent with the current request. Use handoff_checkpoint before editing, after milestones, when a job ID appears and before leaving. At completion, call handoff_transition with complete.
登録済みフォルダーで複数工程を進めるときは、編集前に絶対パスで handoff_status を確認します。対象が曖昧なら handoff_recent を現在の依頼と照合します。編集前、工程の区切り、ジョブID発行時、中断前には handoff_checkpoint を使い、完了時には handoff_transition の complete を使います。

If the other host owns editing, wait for it to stop. Use offer and resume for a planned handoff. Use recover with current permission only after checking that the previous host stopped and verifying the job state. Check current files and authorization. Keep secrets and conversation transcripts out of the record.
相手が編集中なら終了を待ちます。通常の交代は offer と resume を使います。recover は現在の許可があり、前任の停止とジョブの状態を確認できたときに使います。記録を現物と現在の許可に照らし、秘密値や会話全文は保存しません。
<!-- local-handoff-mcp:end -->"""


def version_tuple(version):
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*)){2}", version):
        raise ValueError("Invalid version.")
    return tuple(map(int, version.split(".")))


def read_optional(path):
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def append(original, new):
    sep = "\n" if original.endswith("\n") else "\n\n"
    return (original + sep if original else "") + new.rstrip("\n") + "\n"


def client_changes(home, launcher):
    distro = os.environ["WSL_DISTRO_NAME"]
    win = Path("/mnt/c/Windows/System32/wsl.exe")
    command = r"C:\Windows\System32\wsl.exe" if win.is_file() else "wsl.exe"
    prefix = ["-d", distro, "--exec", "/usr/bin/python3", "-B", str(launcher), "--host"]
    changes = {}
    for host, path in (("codex", home / ".codex" / "config.toml"),
                       ("antigravity", home / ".gemini" / "config" / "mcp_config.json")):
        before = read_optional(path)
        args = prefix + [host, "serve"]
        expected = {"command": command, "args": args}
        original = (before or b"").decode("utf-8-sig")
        if host == "codex":
            existing = tomllib.loads(original).get("mcp_servers", {}).get(NAME)
            if existing is None:
                entry = f"[mcp_servers.{NAME}]\ncommand = {json.dumps(command)}\nargs = {json.dumps(args, ensure_ascii=False)}"
                changes[path] = (before, append(original, entry).encode("utf-8"))
        else:
            document = json.loads(original or "{}")
            servers = document.setdefault("mcpServers", {})
            existing = servers.get(NAME)
            if existing is None:
                servers[NAME] = expected
                changes[path] = (before, json_bytes(document))
        if existing is not None and any(existing.get(key) != value for key, value in expected.items()):
            raise ValueError(f"{path} has a different {NAME} registration. Review it before migrating.")
    for path in (home / ".codex" / "AGENTS.md", home / ".gemini" / "GEMINI.md"):
        before = read_optional(path)
        original = (before or b"").decode("utf-8-sig")
        if RULE_START not in original and RULE_END not in original:
            changes[path] = (before, append(original, RULE).encode("utf-8"))
        else:
            start, end = original.find(RULE_START), original.find(RULE_END)
            if start < 0 or end < start or original.count(RULE_START) != 1 or original.count(RULE_END) != 1:
                raise ValueError(f"{path} has an incomplete or duplicated instruction block.")
    return changes


def apply_changes(changes):
    written = []
    try:
        for path, (before, after) in changes.items():
            if read_optional(path) != before:
                raise ValueError(f"{path} changed during installation. Close both clients and retry.")
            if before != after:
                atomic_write(path, after)
                written.append((path, before, after))
    except (OSError, ValueError):
        for path, before, after in reversed(written):
            if read_optional(path) == after:
                if before is None:
                    path.unlink()
                else:
                    atomic_write(path, before)
        raise


def install(source, root, home, workspaces):
    version = (source / "VERSION").read_text("ascii").strip()
    candidate = version_tuple(version)
    if (source / "SHA256SUMS.json").is_file():
        verify(source)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (root / "install.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        settings, current, launcher = (root / item for item in ("settings.json", "current.json", "launch.py"))
        active = read_optional(current)
        if active and version_tuple(json.loads(active)["version"]) > candidate:
            raise ValueError("Downgrades are blocked. Use the current or a newer release.")
        old_settings = read_optional(settings)
        data = json.loads(old_settings) if old_settings else {
            "state": str(root / "state.sqlite3"),
            "git": shutil.which("git") or "/usr/bin/git",
            "roots": [],
        }
        win_git = Path("/mnt/c/Program Files/Git/cmd/git.exe")
        if not old_settings and win_git.is_file():
            data["windows_git"] = str(win_git)
        if not data["roots"] and not workspaces:
            entry = input("Absolute path of the first project folder / 最初の作業フォルダーの絶対パス: ").strip().strip('"')
            workspaces = [entry] if entry else []
        previous = {item["path"] for item in data["roots"]}
        for item in dict.fromkeys(str(checked_path(value)) for value in workspaces):
            if item not in previous:
                data["roots"].append({"path": item, "partition": 0})
        if not data["roots"]:
            raise ValueError("Register a project folder with --workspace.")

        changes = client_changes(home, launcher)
        release = root / "versions" / ("v" + version)
        for name in RUNTIME_FILES:
            path = release / name
            code = (source / name).read_bytes()
            before = read_optional(path)
            if before is not None and before != code:
                raise ValueError(f"Version {version} already exists with different files.")
            changes[path] = (before, code)
        changes[launcher] = (read_optional(launcher), (source / launcher.name).read_bytes())
        if not old_settings or workspaces:
            changes[settings] = (old_settings, json_bytes(data))
        changes[current] = (active, json_bytes({"version": version}))
        apply_changes(changes)
    print(f"Local Handoff MCP v{version}: {root}")
    print("Reopen both clients to load this version. / 両方のクライアントを開き直してください。")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--windows-home", required=True)
    parser.add_argument("--profile", help="Use a separate Windows profile directory for testing.")
    parser.add_argument("--workspace", action="append", default=[])
    parser.add_argument("--install-dir", type=Path, default=Path.home() / ".local/share/local-handoff-mcp")
    options = parser.parse_args()
    try:
        root = options.install_dir.expanduser().resolve()
        if root.is_relative_to("/mnt") or not os.environ.get("WSL_DISTRO_NAME"):
            raise ValueError("Use the Ubuntu WSL filesystem to store the installation and SQLite database.")
        install(Path(__file__).resolve().parent, root, checked_path(options.profile or options.windows_home), options.workspace)
        return 0
    except (OSError, ValueError, EOFError, KeyError, TypeError, AttributeError, HandoffError) as error:
        print(f"Local Handoff MCP: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
