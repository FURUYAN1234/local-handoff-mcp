"""Serve the handoff dashboard on the loopback interface."""
import fcntl
from html import escape
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
from pathlib import Path
import re
import secrets
import sqlite3
import tarfile
import threading
import time
from urllib.parse import parse_qs, urlencode, urlsplit

from clients import LABELS, capture, configure_claude, discover, open_sign_in, powershell, ps_string
from managed_cli import OPENCODE_VERSION, install_opencode, install_supported


ROOT = Path(__file__).resolve().parent
PHASE_LABELS = {"active": "担当あり", "ready": "引き渡し待ち", "complete": "完了"}
AUTH_LABELS = {"signed-in": "認証済み", "signed-out": "認証が必要",
               "unknown": "認証状態は未確認", "local": "ローカルモデルは認証不要"}
FLASH = {"registered": "Claude CodeにMCPを登録しました。クライアントを開き直し、MCP一覧で確認してください。",
         "browser-login": "認証を開始しました。ブラウザーの案内に従ってください。表示されない場合は起動した端末を確認してください。",
         "claude-terminal": "Claude Codeの端末を開きました。初回はテーマとログイン方法を選択。設定済みなら /login を入力するとブラウザーが開きます。",
         "antigravity-opened": "Antigravityを開きました。認証状態はアプリで確認できます。",
         "opencode-installing": "OpenCode CLIを取得中です。しばらくしてから「更新」で結果を確認してください。",
         "opencode-installed": "OpenCode CLIをWSLにインストールしました。MCP設定は「MCP手順を見る」から確認できます。",
         "opencode-install-failed": "OpenCode CLIの導入に失敗しました。通信を確認して再試行するか、公式インストール手順を開いてください。",
         "failed": "操作を完了できませんでした。手順をマニュアルで確認してください。"}
PAGE_SIZE = 10
INSTALL_GUIDES = {
    "codex": "https://openai.com/codex/",
    "antigravity": "https://antigravity.google/download",
    "claude-code": "https://code.claude.com/docs/en/setup",
    "opencode": "https://opencode.ai/docs/",
    "strata": "https://github.com/Niko1221/Strata/releases",
    "Ollama": "https://ollama.com/download",
    "LM Studio": "https://lmstudio.ai/",
}


DESKTOP_GUIDES = {
    "codex": INSTALL_GUIDES["codex"],
    "antigravity": INSTALL_GUIDES["antigravity"],
    "claude-code": "https://claude.com/download",
    "opencode": "https://opencode.ai/docs/#desktop",
}


def install_guide(key, label, text="公式インストール手順", url=None):
    return (f'<a class="install-guide" href="{url or INSTALL_GUIDES[key]}" target="_blank" rel="noopener noreferrer"'
            f' aria-label="{html(label)}の{text}">{text}</a>')


def acquisition_controls(client, token, preview, cli_install):
    key = client.key
    label = LABELS[key]
    desktop = ('<button type="button" disabled>アプリ · インストール済み</button>'
               if client.desktop_installed else install_guide(key, label, "アプリを取得", DESKTOP_GUIDES[key]))
    hint = ""
    if client.cli_installed:
        cli = '<button type="button" disabled>CLI · インストール済み</button>'
    elif key in ("codex", "antigravity") and client.registered:
        cli = '<button type="button" disabled>CLI · 接続設定あり</button>'
    elif key == "opencode" and not preview and install_supported():
        cli = ('<button type="button" disabled>CLIをインストール中</button>'
               if cli_install == "opencode-installing" else control(token, "install-cli", key, "OpenCode CLIをインストール"))
        hint = (f'<p class="client-hint">OpenCode {OPENCODE_VERSION}をWSL内の'
                'Local Handoff MCP専用フォルダーに導入します。</p>')
    else:
        cli_url = ("https://antigravity.google/docs/getting-started?tab=cli"
                   if key == "antigravity" else INSTALL_GUIDES[key])
        cli = install_guide(key, label, "CLIの導入手順", cli_url)
    return f'<div class="actions acquisition">{desktop}{cli}</div>{hint}'


def html(value):
    return escape(str(value or "—"))


def text_block(label, value):
    return f'<div><dt>{label}</dt><dd>{html(value)}</dd></div>' if value else ""


def page_url(**query):
    return "/" + ("?" + urlencode({key: value for key, value in query.items() if value}) if any(query.values()) else "")


def control(token, action, key, label):
    return (
        '<form method="post" action="/client">'
        f'<input type="hidden" name="token" value="{token}">'
        f'<input type="hidden" name="action" value="{action}">'
        f'<input type="hidden" name="client" value="{key}"><button>{label}</button></form>'
    )


def client_card(client, token, preview, cli_install=None):
    availability = "検出済み" if client.installed else "未検出"
    actions = ""
    if not preview and client.installed and not client.registered and client.key == "claude-code":
        actions += control(token, "register", client.key, "MCPを登録")
    hint = ""
    if not preview and client.installed and client.auth != "signed-in":
        if client.key == "claude-code":
            label = "認証ページを開く" if client.browser_login else "Claude Codeを開く"
            actions += control(token, "signin", client.key, label)
            if not client.browser_login:
                hint = ('<p class="client-hint">この版はターミナルから認証します。初回はテーマとログイン方法を選び、'
                        '設定済みなら <code>/login</code> を入力するとブラウザーが開きます。</p>')
        elif client.key in ("codex", "antigravity"):
            label = "認証ページを開く" if client.key == "codex" else "Antigravityを開く"
            actions += control(token, "signin", client.key, label)
    actions += (f'<a class="install-guide" href="/manual?section={client.key}"'
                f' aria-label="{LABELS[client.key]}のMCP手順を見る">MCP手順を見る</a>')
    acquisition = ""
    if client.key in DESKTOP_GUIDES:
        acquisition = acquisition_controls(client, token, preview, cli_install)
    elif not client.installed:
        actions += install_guide(client.key, LABELS[client.key])
    registration = ("MCP登録はアプリで確認" if client.registered is None
                    else "MCP登録あり" if client.registered else "MCP未登録")
    auth_label = "認証はアプリで確認" if client.key == "antigravity" else AUTH_LABELS[client.auth]
    detail = f"{registration} · {auth_label}" if client.installed else registration
    state = "detected" if client.installed else "absent"
    return (
        f'<div class="client" id="client-{client.key}"><div><dt>{LABELS[client.key]}</dt>'
        f'<dd>{detail}</dd></div><span class="tag {state}">{availability}</span>'
        f'<div class="actions">{actions}</div>{hint}{acquisition}</div>'
    )


def render_history(entries):
    items = []
    for entry in entries:
        info = entry["detail"]
        if entry["kind"] == "checkpoint":
            title = "チェックポイント"
            message = info.get("next_step")
        else:
            title = "自動観測"
            message = ("ブランチ " + str(info.get("branch") or "—")
                       + " · 変更 " + str(info.get("modified", 0))
                       + " · 未追跡 " + str(info.get("untracked", 0))
                       if info["kind"] == "git" else "非Gitフォルダー")
        items.append(f'<li><strong>{title}</strong> <time>{html(entry["recorded"])}</time>'
                     f'<p>{html(message)}</p></li>')
    return "<ol class=\"history\">" + "".join(items) + "</ol>" if items else "<p>履歴はまだありません。</p>"


def project_card(item, selected, query, phase, offset):
    workspace = item["workspace"]
    phase_text = PHASE_LABELS[item["phase"]]
    participant = item["recipient"] if item["phase"] == "ready" else item["owner"]
    role = "宛先" if item["phase"] == "ready" else "担当"
    participant_label = LABELS.get(participant, participant)
    expanded = selected == workspace
    url = html(page_url(query=query, phase=phase, offset=offset, project="" if expanded else workspace))
    return (
        f'<article class="project {item["phase"]}">'
        f'<div class="row"><div><h3><a href="{url}#{ "projects" if expanded else "detail"}">'
        f'{html(item["name"])}</a></h3><p class="path">{html(workspace)}</p></div>'
        f'<span class="tag {item["phase"]}">{phase_text}</span></div>'
        f'<dl>{text_block("目的", item["goal"])}{text_block("次の操作", item["next_step"])}</dl>'
        f'<footer>{role} {html(participant_label)} <time>{html(item["updated"])}</time></footer></article>'
    )


def render_detail(store, selected, history_offset, query, phase, offset):
    try:
        path, has_git = store.workspace(selected)
    except ValueError:
        return ""
    status = store.status(path, has_git)
    record = status["record"]
    if not record:
        return ""
    history = store.history(path, limit=20, offset=history_offset)
    links = []
    for direction, label in ((-1, "新しい履歴"), (1, "古い履歴")):
        if (direction < 0 and history_offset) or (direction > 0 and history["has_more"]):
            url = page_url(query=query, phase=phase, offset=offset, project=selected,
                           history=max(0, history_offset + direction * 20))
            links.append(f'<a href="{html(url)}#detail">{label}</a>')
    observations = "".join(
        f'<li>{html(LABELS.get(host, host))} · {html(event["event"])} · {html(event["seen_at"])}</li>'
        for host, event in status["observed"].items()
    )
    return (
        f'<section class="detail" id="detail"><h3>引き継ぎ記録</h3><p class="path">{html(selected)}</p><dl>'
        f'{text_block("記録時刻", record["saved_at"])}{text_block("完了した作業", record.get("completed"))}'
        f'{text_block("確認結果", record.get("checks"))}{text_block("記録されたジョブ・最終確認", record.get("active_jobs"))}'
        '</dl>'
        + (f'<h4>クライアントの観測記録</h4><ul>{observations}</ul>' if observations else "")
        + '<h4>チェックポイント履歴</h4>'
        + render_history(history["entries"]) + f'<nav class="pager">{"".join(links)}</nav></section>'
    )


def render(store, token, parameters, client_state, preview, cli_install):
    clients, runtimes = client_state
    phase = parameters.get("phase", "")
    phase = phase if phase in PHASE_LABELS else ""
    query = parameters.get("query", "")[:100].strip()
    offset_raw = parameters.get("offset", "")
    history_raw = parameters.get("history", "")
    offset = int(offset_raw) if offset_raw.isascii() and offset_raw.isdecimal() and len(offset_raw) < 7 else 0
    history_offset = int(history_raw) if history_raw.isascii() and history_raw.isdecimal() and len(history_raw) < 4 else 0
    selected = parameters.get("project", "")
    page = store.projects(limit=PAGE_SIZE, offset=offset, phase=phase, query=query)
    project_html = "".join(project_card(item, selected, query, phase, offset) for item in page["workspaces"])
    if not project_html:
        message = ("条件に一致する引き継ぎ記録がありません。" if offset or phase or query
                   else "登録した作業フォルダーでチェックポイントを保存すると、ここに表示されます。")
        project_html = f'<p class="empty">{message}</p>'
    details = ""
    if any(item["workspace"] == selected for item in page["workspaces"]):
        from handoff import HandoffError
        try:
            details = render_detail(store, selected, history_offset, query, phase, offset)
        except HandoffError:
            details = '<p class="empty">作業フォルダーを確認できません。登録先を確認してください。</p>'
    filters = "".join(
        f'<option value="{value}"{" selected" if phase == value else ""}>{label}</option>'
        for value, label in (("", "すべての状態"), *PHASE_LABELS.items())
    )
    links = []
    for direction, label in ((-1, "前へ"), (1, "次へ")):
        if (direction < 0 and offset) or (direction > 0 and offset + PAGE_SIZE < page["total"]):
            url = page_url(query=query, phase=phase, offset=max(0, offset + direction * PAGE_SIZE))
            links.append(f'<a href="{html(url)}#projects">{label}</a>')
    cards = "".join(client_card(client, token, preview, cli_install) for client in clients.values())
    runtime_html = ""
    for label, (installed, live_port, default_port, stopped_port) in runtimes.items():
        if live_port:
            text = f"待受ポート {live_port}"
        elif stopped_port:
            text = f"停止中 · 設定ポート {stopped_port}（標準 {default_port}）"
        elif installed:
            text = f"導入済み · 標準ポート {default_port} の応答なし"
        else:
            text = f"未検出 {install_guide(label, label)}"
        runtime_html += f'<div class="ollama"><strong>{html(label)}</strong><span>{text}</span></div>'
    preview_label = ('<p class="notice">検証用画面です。サンプル案件を表示しています。</p>' if preview else "")
    notice_key = parameters.get("notice", "")
    if cli_install and (not notice_key or notice_key.startswith("opencode-")):
        notice_key = cli_install
    flash = FLASH.get(notice_key)
    notice = f'<p class="notice" role="status">{flash}</p>' if flash else ""
    version = html((ROOT / "VERSION").read_text("ascii").strip())
    reload_url = html(page_url(query=query, phase=phase, offset=offset, project=selected, rescan=1))
    return f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link href="/style.css" rel="stylesheet"><title>Local Handoff MCP</title></head>
<body><header class="mast"><div><span>Local Handoff MCP <small>v{version}</small></span>
<nav><a href="/manual">操作・MCP設定</a><a href="{reload_url}">更新</a></nav></div></header>
<main><h1>作業の引き継ぎ</h1>{preview_label}{notice}
<div class="board"><section id="projects" aria-labelledby="project-title">
<div class="section-head"><h2 id="project-title">プロジェクト</h2><span>{page["total"]}件</span></div>
<form class="filter" action="/"><label>プロジェクト名・パス<input name="query" value="{html(query) if query else ''}"
maxlength="100" placeholder="検索"></label><label>状態<select name="phase">{filters}</select></label>
<button>絞り込む</button></form>
<div class="project-list">{project_html}</div><nav class="pager">{"".join(links)}</nav>{details}</section>
<aside aria-labelledby="client-title"><div class="section-head"><h2 id="client-title">接続先のAI</h2></div>
<dl class="clients">{cards}</dl><h3 class="runtime-title">ローカルAI実行環境</h3>{runtime_html}
</aside></div></main></body></html>'''


MANUAL_SECTIONS = {
    "codex": "Codex setup / Codexの設定",
    "antigravity": "Antigravity setup / Antigravityの設定",
    "claude-code": "Claude Code setup / Claude Codeの設定",
    "opencode": "OpenCode and local models / OpenCodeとローカルモデル",
    "strata": "Strata in WSL / WSL版Strataの設定",
}
GUIDE_INLINE = re.compile(
    r"`([^`]+)`|\*\*([^*]+)\*\*|\[([^\]]+)\]\((https://[^\s)]+)\)"
)


def guide_inline(text):
    parts = []
    offset = 0
    for token in GUIDE_INLINE.finditer(text):
        parts.append(escape(text[offset:token.start()]))
        code, bold, label, url = token.groups()
        if code is not None:
            parts.append(f"<code>{escape(code)}</code>")
        elif bold is not None:
            parts.append(f"<strong>{escape(bold)}</strong>")
        else:
            parts.append(f'<a href="{escape(url)}">{escape(label)}</a>')
        offset = token.end()
    parts.append(escape(text[offset:]))
    return "".join(parts)


def guide_paragraph(text):
    english, separator, japanese = text.partition(" / ")
    if not separator:
        return guide_inline(text)
    return (f'{guide_inline(japanese)}'
            f'<span class="guide-translation" lang="en">{guide_inline(english)}</span>')


def guide_blocks(markdown):
    # The bundled guide uses blank-line-separated Markdown blocks.
    blocks = []
    for block in markdown.strip().split("\n\n"):
        lines = block.splitlines()
        if not lines:
            continue
        if lines[0].startswith("```") and lines[-1] == "```":
            code = escape("\n".join(lines[1:-1]))
            blocks.append(f"<pre><code>{code}</code></pre>")
        elif block.startswith("## "):
            blocks.append(f"<h2>{guide_inline(block[3:])}</h2>")
        elif all(re.match(r"\d+\. ", line) for line in lines):
            items = "".join(f"<li>{guide_paragraph(line.split('. ', 1)[1])}</li>" for line in lines)
            blocks.append(f"<ol>{items}</ol>")
        elif all(line.startswith("- ") for line in lines):
            items = "".join(f"<li>{guide_paragraph(line[2:])}</li>" for line in lines)
            blocks.append(f"<ul>{items}</ul>")
        else:
            blocks.append(f"<p>{guide_paragraph(block)}</p>")
    return "\n".join(blocks)


def render_manual(query):
    contents = (ROOT / "MANUAL.md").read_text("utf-8")
    heading, _, contents = contents.partition("\n")
    section = parse_qs(query, max_num_fields=12).get("section", [""])[0]
    back_url, back_label = "/#client-title", "管理画面に戻る"
    if section in MANUAL_SECTIONS:
        section_heading = MANUAL_SECTIONS[section]
        _, match, remainder = contents.partition(f"\n## {section_heading}\n")
        if match:
            heading = section_heading
            contents = remainder.split("\n## ", 1)[0]
            back_url = f"/#client-{section}"
            back_label = f"管理画面の{LABELS[section]}欄に戻る"
    title = escape(heading.split(" / ", 1)[-1])
    full_guide = '<a href="/manual">マニュアル全体</a>' if back_url != "/#client-title" else ""
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link href="/style.css" rel="stylesheet"><title>{title} | Local Handoff MCP</title></head>
<body><header class="mast"><div><span>Local Handoff MCP</span>
<nav><a href="{back_url}">{back_label}</a>{full_guide}</nav></div></header>
<main class="manual"><h1>{title}</h1>
<article class="guide-copy">{guide_blocks(contents)}</article></main></body></html>"""


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, store, port, install_root):
        self.install_root = install_root
        self.preview = not (install_root / "current.json").is_file()
        super().__init__(("127.0.0.1", port), Handler)
        self.store = store
        self.token = secrets.token_urlsafe(32)
        self.instance = secrets.token_urlsafe(24)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        self.client_action = threading.Lock()
        self.inventory_lock = threading.Lock()
        self.inventory = None
        self.scanned_at = 0
        self.cli_install = None

    def start_cli_install(self):
        if self.cli_install != "opencode-installing":
            self.cli_install = "opencode-installing"
            threading.Thread(target=self.install_cli, daemon=True).start()
        return self.cli_install

    def install_cli(self):
        try:
            install_opencode(self.install_root)
        except (OSError, ValueError, KeyError, tarfile.TarError):
            self.cli_install = "opencode-install-failed"
        else:
            with self.inventory_lock:
                self.inventory = None
            self.cli_install = "opencode-installed"

    def scan(self, force=False):
        with self.inventory_lock:
            if force or self.inventory is None or time.monotonic() - self.scanned_at >= 30:
                self.inventory = discover(self.install_root)
                self.scanned_at = time.monotonic()
            return self.inventory


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def setup(self):
        self.request.settimeout(20)
        super().setup()

    def respond(self, status, body="", content_type="text/plain; charset=utf-8", location=None):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; style-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        if location:
            self.send_header("Location", location)
        self.end_headers()
        self.wfile.write(data)

    def valid_host(self):
        return self.headers.get_all("Host") == [f"127.0.0.1:{self.server.server_port}"]

    def do_GET(self):
        if not self.valid_host():
            self.respond(403)
            return
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            self.respond(403)
            return
        try:
            url = urlsplit(self.path)
            if url.path == "/style.css":
                self.respond(200, (ROOT / "dashboard.css").read_text("utf-8"), "text/css; charset=utf-8")
            elif url.path == "/manual":
                self.respond(200, render_manual(url.query), "text/html; charset=utf-8")
            elif url.path == "/client":
                self.respond(303, location="/")
            elif url.path == "/_instance":
                nonce = self.headers.get("X-Local-Handoff-Instance", "")
                healthy = nonce.isascii() and hmac.compare_digest(nonce, self.server.instance)
                self.respond(200 if healthy else 404)
            elif url.path == "/":
                query = {key: val[0] for key, val in parse_qs(url.query, max_num_fields=12).items()}
                state = self.server.scan(query.get("rescan") == "1" or "notice" in query)
                page = render(self.server.store, self.server.token, query, state, self.server.preview,
                              self.server.cli_install)
                self.respond(200, page, "text/html; charset=utf-8")
            else:
                self.respond(404)
        except (OSError, ValueError, sqlite3.Error):
            self.respond(500, "記録を表示できません。設定とデータベースを確認してください。")

    def do_POST(self):
        if (not self.valid_host() or self.headers.get("Origin") != self.server.origin
                or self.path != "/client" or self.headers.get_content_type() != "application/x-www-form-urlencoded"):
            self.respond(403, "この画面から接続操作を実行できません。管理画面を開き直してください。")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096:
                raise ValueError
            payload = parse_qs(self.rfile.read(length).decode("ascii"), max_num_fields=3, errors="strict")
            token, key, action = (payload[field][0] for field in ("token", "client", "action"))
        except (ValueError, KeyError, OSError):
            self.respond(303, location=page_url(notice="failed"))
            return
        if self.server.preview or not token.isascii() or not hmac.compare_digest(token, self.server.token):
            self.respond(303, location=page_url(notice="failed"))
            return
        notice = "failed"
        with self.server.client_action:
            cwd = self.server.install_root
            clients, _ = discover(cwd, scan_auth=False)
            client = clients.get(key)
            if action == "install-cli" and key == "opencode" and client and not client.cli_installed and install_supported():
                notice = self.server.start_cli_install()
            elif client and client.installed:
                if action == "register" and key == "claude-code" and not client.registered:
                    if configure_claude(client, cwd):
                        notice = "registered"
                elif action == "signin":
                    notice = open_sign_in(client, cwd) or notice
        self.respond(303, location=page_url(notice=notice))


def open_dashboard(url, install_root):
    result = capture(powershell("Start-Process " + ps_string(url)), install_root, 5)
    if result is None or result.returncode:
        print("ブラウザーを開けませんでした。表示されたローカルURLを開いてください。", flush=True)


def existing_dashboard(lock):
    for _ in range(10):
        conn = None
        try:
            lock.seek(0)
            settings = json.load(lock)
            port, nonce = settings["port"], settings["instance"]
            if type(port) is int and 0 < port <= 65535 and isinstance(nonce, str) and len(nonce) == 32:
                conn = HTTPConnection("127.0.0.1", port, timeout=0.4)
                conn.request("GET", "/_instance", headers={"X-Local-Handoff-Instance": nonce})
                if conn.getresponse().status == 200:
                    return f"http://127.0.0.1:{port}"
        except (OSError, ValueError, KeyError, TypeError):
            pass
        finally:
            if conn:
                conn.close()
        time.sleep(0.1)
    return None


def run(store, port, open_browser, install_root):
    from handoff import HandoffError

    with (install_root / "dashboard.lock").open("a+", encoding="ascii") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            url = existing_dashboard(lock)
            if url is None:
                raise HandoffError("管理画面の起動状態を確認できません。元の起動ウィンドウを確認してください。")
            print(url, flush=True)
            if open_browser:
                open_dashboard(url, install_root)
            return
        with DashboardServer(store, port, install_root) as server:
            lock.seek(0)
            lock.truncate()
            json.dump({"port": server.server_port, "instance": server.instance}, lock)
            lock.flush()
            print(server.origin, flush=True)
            if open_browser:
                open_dashboard(server.origin, install_root)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
