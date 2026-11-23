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
PHASE_LABELS = {"active": ("担当あり", "In progress"), "ready": ("引き渡し待ち", "Awaiting handoff"),
                "complete": ("完了", "Complete")}
AUTH_LABELS = {"signed-in": ("認証済み", "Signed in"), "signed-out": ("認証が必要", "Sign-in required"),
               "unknown": ("認証状態は未確認", "Sign-in status unavailable"),
               "local": ("ローカルモデルは認証不要", "Local models need no sign-in")}
FLASH = {
    "registered": ("Claude CodeにMCPを登録しました。クライアントを開き直し、MCP一覧で確認してください。",
                   "MCP registered in Claude Code. Reopen the client and check its MCP list."),
    "browser-login": ("認証を開始しました。ブラウザーの案内に従ってください。表示されない場合は起動した端末を確認してください。",
                      "Sign-in started. Follow the browser instructions. If no page opens, check the terminal."),
    "claude-terminal": ("Claude Codeの端末を開きました。初回はテーマとログイン方法を選択。設定済みなら /login を入力するとブラウザーが開きます。",
                        "Claude Code opened in a terminal. Choose a theme and sign-in option on first launch. "
                        "If already configured, enter /login to open the browser."),
    "antigravity-opened": ("Antigravityを開きました。認証状態はアプリで確認できます。",
                          "Antigravity opened. Check sign-in status in the app."),
    "opencode-installing": ("OpenCode CLIを取得中です。「更新」で結果を確認できます。",
                            "Downloading OpenCode CLI. Select Refresh to check the result."),
    "opencode-installed": ("OpenCode CLIをWSLにインストールしました。MCP設定は「MCP手順を見る」から確認できます。",
                           "OpenCode CLI is installed in WSL. Select MCP setup guide for connection instructions."),
    "opencode-install-failed": ("OpenCode CLIの導入に失敗しました。通信を確認して再試行するか、公式インストール手順を開いてください。",
                                "OpenCode CLI installation failed. Check your connection and retry, or open the official guide."),
    "failed": ("操作を完了できませんでした。手順をマニュアルで確認してください。",
               "Could not complete the action. See the manual for setup instructions."),
}
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


class Locale:
    def __init__(self, language="ja"):
        self.language = "en" if language == "en" else "ja"

    def __call__(self, ja, en):
        return en if self.language == "en" else ja

    def url(self, path="/", **query):
        parameters = {key: value for key, value in query.items() if value}
        if self.language == "en":
            parameters["lang"] = "en"
        return path + ("?" + urlencode(parameters) if parameters else "")

    def input(self):
        return '<input type="hidden" name="lang" value="en">' if self.language == "en" else ""

    def switch(self, path="/", **query):
        other = Locale(self("en", "ja"))
        url = html(other.url(path, **query))
        return (f'<a class="locale-switch" href="{url}" lang="{other.language}"'
                f' hreflang="{other.language}">{self("English", "日本語")}</a>')


JAPANESE = Locale()


def install_guide(key, label, loc, text=None, url=None):
    text = text or loc("公式インストール手順", "Official installation guide")
    accessible_name = loc(f"{label}の{text}", f"{label}: {text}")
    return (f'<a class="install-guide" href="{url or INSTALL_GUIDES[key]}" target="_blank" rel="noopener noreferrer"'
            f' aria-label="{html(accessible_name)}">{text}</a>')


def acquisition_controls(client, token, preview, cli_install, loc):
    key = client.key
    label = LABELS[key]
    desktop = (f'<button type="button" disabled>{loc("アプリ · インストール済み", "Desktop app · Installed")}</button>'
               if client.desktop_installed else install_guide(key, label, loc, loc("アプリを取得", "Get desktop app"),
                                                              DESKTOP_GUIDES[key]))
    hint = ""
    if client.cli_installed:
        cli = f'<button type="button" disabled>{loc("CLI · インストール済み", "CLI · Installed")}</button>'
    elif key in ("codex", "antigravity") and client.registered:
        cli = f'<button type="button" disabled>{loc("CLI · 接続設定あり", "CLI · Connection configured")}</button>'
    elif key == "opencode" and not preview and install_supported():
        installing = loc("CLIをインストール中", "Installing CLI")
        install = loc("OpenCode CLIをインストール", "Install OpenCode CLI")
        cli = (f'<button type="button" disabled>{installing}</button>'
               if cli_install == "opencode-installing" else control(token, "install-cli", key, install, loc))
        hint_text = loc(f"OpenCode {OPENCODE_VERSION}をWSL内のLocal Handoff MCP専用フォルダーに導入します。",
                        f"Installs OpenCode {OPENCODE_VERSION} in the Local Handoff MCP directory in WSL.")
        hint = f'<p class="client-hint">{hint_text}</p>'
    else:
        cli_url = ("https://antigravity.google/docs/getting-started?tab=cli"
                   if key == "antigravity" else INSTALL_GUIDES[key])
        cli = install_guide(key, label, loc, loc("CLIの導入手順", "CLI installation guide"), cli_url)
    return f'<div class="actions acquisition">{desktop}{cli}</div>{hint}'


def html(value):
    return escape(str(value or "—"))


def format_time(value):
    safe = html(value)
    return f'<time datetime="{safe}">{safe}</time>'


def text_block(label, value, format_value=html):
    return f'<div><dt>{label}</dt><dd>{format_value(value)}</dd></div>' if value else ""


def control(token, action, key, label, loc):
    return (
        f'<form method="post" action="{html(loc.url("/client"))}">'
        f'<input type="hidden" name="token" value="{token}">'
        f'<input type="hidden" name="action" value="{action}">'
        f'<input type="hidden" name="client" value="{key}"><button>{label}</button></form>'
    )


def client_card(client, token, preview, cli_install=None, loc=JAPANESE):
    key = client.key
    client_name = LABELS[key]
    availability = loc("検出済み", "Detected") if client.installed else loc("未検出", "Not detected")
    actions = ""
    if not preview and client.installed and not client.registered and key == "claude-code":
        actions += control(token, "register", key, loc("MCPを登録", "Register MCP"), loc)
    hint = ""
    if not preview and client.installed and client.auth != "signed-in":
        sign_in = loc("認証ページを開く", "Open sign-in page")
        if key == "claude-code":
            label = sign_in if client.browser_login else loc("Claude Codeを開く", "Open Claude Code")
            actions += control(token, "signin", key, label, loc)
            if not client.browser_login:
                hint_text = loc("この版はターミナルから認証します。初回はテーマとログイン方法を選び、"
                                "設定済みなら <code>/login</code> を入力するとブラウザーが開きます。",
                                "This version uses terminal sign-in. Choose a theme and sign-in option on first launch. "
                                "If already configured, enter <code>/login</code> to open the browser.")
                hint = f'<p class="client-hint">{hint_text}</p>'
        elif key in ("codex", "antigravity"):
            label = sign_in if key == "codex" else loc("Antigravityを開く", "Open Antigravity")
            actions += control(token, "signin", key, label, loc)
    guide_url = html(loc.url("/manual", section=key))
    guide_name = loc(f"{client_name}のMCP手順を見る", f"MCP setup guide for {client_name}")
    actions += (f'<a class="install-guide" href="{guide_url}"'
                f' aria-label="{html(guide_name)}">{loc("MCP手順を見る", "MCP setup guide")}</a>')
    acquisition = ""
    if key in DESKTOP_GUIDES:
        acquisition = acquisition_controls(client, token, preview, cli_install, loc)
    elif not client.installed:
        actions += install_guide(key, client_name, loc)
    registration = (loc("MCP登録はアプリで確認", "Check MCP registration in the app") if client.registered is None
                    else loc("MCP登録あり", "MCP registered") if client.registered
                    else loc("MCP未登録", "MCP not registered"))
    auth_label = (loc("認証はアプリで確認", "Check sign-in in the app") if key == "antigravity"
                  else loc(*AUTH_LABELS[client.auth]))
    detail = f"{registration} · {auth_label}" if client.installed else registration
    state = "detected" if client.installed else "absent"
    return (
        f'<div class="client" id="client-{key}"><div><dt>{client_name}</dt>'
        f'<dd>{detail}</dd></div><span class="tag {state}">{availability}</span>'
        f'<div class="actions">{actions}</div>{hint}{acquisition}</div>'
    )


def render_history(entries, loc):
    items = []
    for entry in entries:
        info = entry["detail"]
        if entry["kind"] == "checkpoint":
            title = loc("チェックポイント", "Checkpoint")
            message = info.get("next_step")
        else:
            title = loc("自動観測", "Automatic observation")
            branch = info.get("branch") or "—"
            modified, untracked = info.get("modified", 0), info.get("untracked", 0)
            message = (loc(f"ブランチ {branch} · 変更 {modified} · 未追跡 {untracked}",
                           f"Branch {branch} · Modified {modified} · Untracked {untracked}")
                       if info["kind"] == "git" else loc("非Gitフォルダー", "Non-Git folder"))
        items.append(f'<li><strong>{title}</strong> {format_time(entry["recorded"])}'
                     f'<p>{html(message)}</p></li>')
    return ('<ol class="history">' + "".join(items) + "</ol>" if items else
            f'<p>{loc("履歴はまだありません。", "No history yet.")}</p>')


def project_card(item, selected, query, phase, offset, loc):
    workspace = item["workspace"]
    phase_text = loc(*PHASE_LABELS[item["phase"]])
    participant = item["recipient"] if item["phase"] == "ready" else item["owner"]
    role = loc("宛先", "Recipient") if item["phase"] == "ready" else loc("担当", "Owner")
    participant_label = LABELS.get(participant, participant)
    expanded = selected == workspace
    url = html(loc.url(query=query, phase=phase, offset=offset, project="" if expanded else workspace))
    return (
        f'<article class="project {item["phase"]}">'
        f'<div class="row"><div><h3><a href="{url}#{"projects" if expanded else "detail"}">'
        f'{html(item["name"])}</a></h3><p class="path">{html(workspace)}</p></div>'
        f'<span class="tag {item["phase"]}">{phase_text}</span></div>'
        f'<dl>{text_block(loc("目的", "Goal"), item["goal"])}'
        f'{text_block(loc("次の操作", "Next step"), item["next_step"])}</dl>'
        f'<footer>{role} {html(participant_label)} {format_time(item["updated"])}</footer></article>'
    )


def render_detail(store, selected, history_offset, query, phase, offset, loc):
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
    for direction, label in ((-1, loc("新しい履歴", "Newer entries")), (1, loc("古い履歴", "Older entries"))):
        if (direction < 0 and history_offset) or (direction > 0 and history["has_more"]):
            url = loc.url(query=query, phase=phase, offset=offset, project=selected,
                          history=max(0, history_offset + direction * 20))
            links.append(f'<a href="{html(url)}#detail">{label}</a>')
    event_labels = {"start": loc("開始", "Started"), "stop": loc("終了", "Stopped")}
    observations = "".join(
        f'<li>{html(LABELS.get(host, host))} · {html(event_labels.get(event["event"], event["event"]))}'
        f' · {format_time(event["seen_at"])}</li>'
        for host, event in status["observed"].items()
    )
    return (
        f'<section class="detail" id="detail"><h3>{loc("引き継ぎ記録", "Handoff record")}</h3>'
        f'<p class="path">{html(selected)}</p><dl>'
        f'{text_block(loc("記録時刻", "Recorded at"), record["saved_at"], format_time)}'
        f'{text_block(loc("完了した作業", "Completed work"), record.get("completed"))}'
        f'{text_block(loc("確認結果", "Verification"), record.get("checks"))}'
        f'{text_block(loc("記録されたジョブ・最終確認", "Recorded jobs and last check"), record.get("active_jobs"))}'
        '</dl>'
        + (f'<h4>{loc("クライアントの観測記録", "Client observations")}</h4><ul>{observations}</ul>'
           if observations else "")
        + f'<h4>{loc("チェックポイント履歴", "Checkpoint history")}</h4>'
        + render_history(history["entries"], loc) + f'<nav class="pager">{"".join(links)}</nav></section>'
    )


def flash_message(key, loc):
    return f'<p class="notice" role="status">{loc(*FLASH[key])}</p>' if key in FLASH else ""


def render_client_panel(client_state, token, preview, cli_install, loc):
    clients, runtimes = client_state
    cards = "".join(client_card(client, token, preview, cli_install, loc) for client in clients.values())
    runtime_labels = []
    for label, (installed, live_port, default_port, stopped_port) in runtimes.items():
        if live_port:
            text = loc(f"待受ポート {live_port}", f"Listening on port {live_port}")
        elif stopped_port:
            text = loc(f"停止中 · 設定ポート {stopped_port}（標準 {default_port}）",
                       f"Stopped · Configured port {stopped_port} (default {default_port})")
        elif installed:
            text = loc(f"導入済み · 標準ポート {default_port} の応答なし",
                       f"Installed · No response on default port {default_port}")
        else:
            text = loc("未検出", "Not detected") + " " + install_guide(label, label, loc)
        runtime_labels.append(f'<div class="ollama"><strong>{html(label)}</strong><span>{text}</span></div>')
    return (flash_message(cli_install, loc)
            + f'<dl class="clients">{cards}</dl>'
            + f'<h3 class="runtime-title">{loc("ローカルAI実行環境", "Local AI runtimes")}</h3>'
            + "".join(runtime_labels))


def render(store, token, parameters, client_state, preview, cli_install):
    loc = Locale(parameters.get("lang"))
    phase = parameters.get("phase", "")
    phase = phase if phase in PHASE_LABELS else ""
    query = parameters.get("query", "")[:100].strip()
    offset_raw = parameters.get("offset", "")
    history_raw = parameters.get("history", "")
    offset = int(offset_raw) if offset_raw.isascii() and offset_raw.isdecimal() and len(offset_raw) < 7 else 0
    history_offset = int(history_raw) if history_raw.isascii() and history_raw.isdecimal() and len(history_raw) < 4 else 0
    selected = parameters.get("project", "")
    page = store.projects(limit=PAGE_SIZE, offset=offset, phase=phase, query=query)
    project_html = "".join(project_card(item, selected, query, phase, offset, loc) for item in page["workspaces"])
    if not project_html:
        message = (loc("条件に一致する引き継ぎ記録がありません。", "No handoff records match these filters.")
                   if offset or phase or query else
                   loc("登録した作業フォルダーでチェックポイントを保存すると、ここに表示されます。",
                       "Save a checkpoint in a registered workspace to see it here."))
        project_html = f'<p class="empty">{message}</p>'
    details = ""
    if any(item["workspace"] == selected for item in page["workspaces"]):
        from handoff import HandoffError
        try:
            details = render_detail(store, selected, history_offset, query, phase, offset, loc)
        except HandoffError:
            message = loc("作業フォルダーを確認できません。登録先を確認してください。",
                          "Could not access the workspace. Check the registered path.")
            details = f'<p class="empty">{message}</p>'
    filters = "".join(
        f'<option value="{value}"{" selected" if phase == value else ""}>{loc(*labels)}</option>'
        for value, labels in (("", ("すべての状態", "All statuses")), *PHASE_LABELS.items())
    )
    links = []
    for direction, label in ((-1, loc("前へ", "Previous")), (1, loc("次へ", "Next"))):
        if (direction < 0 and offset) or (direction > 0 and offset + PAGE_SIZE < page["total"]):
            url = loc.url(query=query, phase=phase, offset=max(0, offset + direction * PAGE_SIZE))
            links.append(f'<a href="{html(url)}#projects">{label}</a>')
    preview_text = loc("検証用画面です。サンプル案件を表示しています。", "Preview. These are sample projects.")
    preview_label = f'<p class="notice">{preview_text}</p>' if preview else ""
    notice_key = parameters.get("notice", "")
    notice = "" if notice_key.startswith("opencode-") else flash_message(notice_key, loc)
    version = html((ROOT / "VERSION").read_text("ascii").strip())
    state = dict(query=query, phase=phase, offset=offset, project=selected, history=history_offset)
    reload_url = html(loc.url(**state, rescan=1))
    switch = loc.switch(**state)
    manual_url = html(loc.url("/manual"))
    refresh_url = html(loc.url("/clients"))
    add_project_url = html(loc.url("/manual", section="projects"))
    client_panel = render_client_panel(client_state, token, preview, cli_install, loc)
    refresh_label = loc("表示中は1分ごとにAIの検出状況を更新します。", "Refreshes AI detection every minute while visible.")
    refresh_failure = loc("AIの検出状況を更新できませんでした。「更新」で再試行できます。",
                          "Could not refresh AI detection. Select Refresh to retry.")
    return f"""<!doctype html>
<html lang="{loc.language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link href="/style.css" rel="stylesheet"><script src="/dashboard.js" defer></script><title>Local Handoff MCP</title></head>
<body><header class="mast"><div><span>Local Handoff MCP <small>v{version}</small></span>
<nav><a href="{manual_url}">{loc("操作・MCP設定", "User and MCP guide")}</a>
<a href="{reload_url}">{loc("更新", "Refresh")}</a>{switch}</nav></div></header>
<main><h1>{loc("作業の引き継ぎ", "Project handoffs")}</h1>{preview_label}{notice}
<div class="board"><section id="projects" aria-labelledby="project-title">
<div class="section-head"><h2 id="project-title">{loc("プロジェクト", "Projects")}</h2>
<div class="section-tools"><span>{loc(f'{page["total"]}件', f'Total {page["total"]}')}</span>
<a href="{add_project_url}">{loc("プロジェクトの追加方法", "How to add projects")}</a></div></div>
<form class="filter" action="/"><label>{loc("プロジェクト名・パス", "Project name or path")}
<input name="query" value="{html(query) if query else ''}" maxlength="100" placeholder="{loc("検索", "Search")}"></label>
<label>{loc("状態", "Status")}<select name="phase">{filters}</select></label>
<button>{loc("絞り込む", "Filter")}</button>{loc.input()}</form>
<div class="project-list">{project_html}</div><nav class="pager">{"".join(links)}</nav>{details}</section>
<aside aria-labelledby="client-title"><div class="section-head"><h2 id="client-title">{loc("接続先のAI", "AI connections")}</h2></div>
<p class="refresh-status" id="client-refresh-status" role="status" data-failed="{html(refresh_failure)}">{refresh_label}</p>
<p class="refresh-status" id="client-last-refresh" hidden>{loc("最終自動更新", "Last automatic refresh")} <time></time></p>
<div id="client-panel" data-refresh-url="{refresh_url}">{client_panel}</div>
</aside></div></main></body></html>"""


MANUAL_SECTIONS = {
    "projects": "Add a project / プロジェクトの追加",
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


def guide_translation(text, loc):
    english, separator, japanese = text.partition(" / ")
    return loc(japanese, english) if separator else text


def guide_blocks(markdown, loc):
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
            blocks.append(f"<h2>{guide_inline(guide_translation(block[3:], loc))}</h2>")
        elif all(re.match(r"\d+\. ", line) for line in lines):
            items = [line.split(". ", 1)[1] for line in lines]
            blocks.append("<ol>" + guide_list(items, loc) + "</ol>")
        elif all(line.startswith("- ") for line in lines):
            blocks.append("<ul>" + guide_list((line[2:] for line in lines), loc) + "</ul>")
        else:
            blocks.append(f"<p>{guide_inline(guide_translation(block, loc))}</p>")
    return "\n".join(blocks)


def guide_list(items, loc):
    return "".join(f"<li>{guide_inline(guide_translation(item, loc))}</li>" for item in items)


def render_manual(query, loc):
    contents = (ROOT / "MANUAL.md").read_text("utf-8")
    heading, _, contents = contents.partition("\n")
    heading = heading.removeprefix("# ")
    section = query.get("section", "")
    back_url = loc.url() + "#client-title"
    back_label = loc("管理画面に戻る", "Back to dashboard")
    selected = ""
    section_heading = MANUAL_SECTIONS.get(section)
    if section_heading:
        _, match, remainder = contents.partition(f"\n## {section_heading}\n")
        if match:
            selected = section
            heading = section_heading
            contents = remainder.split("\n## ", 1)[0]
            if section == "projects":
                back_url = loc.url() + "#projects"
                back_label = loc("プロジェクト一覧に戻る", "Back to projects")
            else:
                back_url = loc.url() + f"#client-{section}"
                client = LABELS[section]
                back_label = loc(f"管理画面の{client}欄に戻る", f"Back to {client} on the dashboard")
    title = escape(guide_translation(heading, loc))
    full_guide = (f'<a href="{html(loc.url("/manual"))}">{loc("マニュアル全体", "Full manual")}</a>'
                  if selected else "")
    switch = loc.switch("/manual", section=selected)
    return f"""<!doctype html>
<html lang="{loc.language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link href="/style.css" rel="stylesheet"><title>{title} | Local Handoff MCP</title></head>
<body><header class="mast"><div><span>Local Handoff MCP</span>
<nav><a href="{html(back_url)}">{back_label}</a>{full_guide}{switch}</nav></div></header>
<main class="manual"><h1>{title}</h1>
<article class="guide-copy">{guide_blocks(contents, loc)}</article></main></body></html>"""


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
                         "default-src 'none'; style-src 'self'; script-src 'self'; connect-src 'self'; "
                         "form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        if location:
            self.send_header("Location", location)
        self.end_headers()
        self.wfile.write(data)

    def valid_host(self):
        return self.headers.get_all("Host") == [f"127.0.0.1:{self.server.server_port}"]

    def do_GET(self):
        if not self.valid_host() or self.headers.get("Sec-Fetch-Site") == "cross-site":
            self.respond(403)
            return
        loc = JAPANESE
        try:
            url = urlsplit(self.path)
            query = {key: val[0] for key, val in parse_qs(url.query, max_num_fields=12).items()}
            loc = Locale(query.get("lang"))
            if url.path == "/style.css":
                self.respond(200, (ROOT / "dashboard.css").read_text("utf-8"), "text/css; charset=utf-8")
            elif url.path == "/dashboard.js":
                self.respond(200, (ROOT / "dashboard.js").read_text("utf-8"), "text/javascript; charset=utf-8")
            elif url.path == "/manual":
                self.respond(200, render_manual(query, loc), "text/html; charset=utf-8")
            elif url.path == "/clients":
                panel = render_client_panel(self.server.scan(), self.server.token, self.server.preview,
                                            self.server.cli_install, loc)
                self.respond(200, panel, "text/html; charset=utf-8")
            elif url.path == "/client":
                self.respond(303, location=loc.url())
            elif url.path == "/_instance":
                nonce = self.headers.get("X-Local-Handoff-Instance", "")
                healthy = nonce.isascii() and hmac.compare_digest(nonce, self.server.instance)
                self.respond(200 if healthy else 404)
            elif url.path == "/":
                state = self.server.scan(query.get("rescan") == "1" or "notice" in query)
                page = render(self.server.store, self.server.token, query, state, self.server.preview,
                              self.server.cli_install)
                self.respond(200, page, "text/html; charset=utf-8")
            else:
                self.respond(404)
        except (OSError, ValueError, sqlite3.Error):
            self.respond(500, loc("記録を表示できません。設定とデータベースを確認してください。",
                                  "Could not display data. Check the settings and database."))

    def do_POST(self):
        path, _, query = self.path.partition("?")
        loc = Locale("en" if query == "lang=en" else "ja")
        if (not self.valid_host() or self.headers.get("Origin") != self.server.origin
                or path != "/client" or self.headers.get_content_type() != "application/x-www-form-urlencoded"):
            self.respond(403, loc("この画面から接続操作を実行できません。管理画面を開き直してください。",
                                  "This page cannot run connection actions. Reopen the dashboard."))
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096:
                raise ValueError
            payload = parse_qs(self.rfile.read(length).decode("ascii"), max_num_fields=3, errors="strict")
            token, key, action = (payload[field][0] for field in ("token", "client", "action"))
        except (ValueError, KeyError, OSError):
            self.respond(303, location=loc.url(notice="failed"))
            return
        if self.server.preview or not token.isascii() or not hmac.compare_digest(token, self.server.token):
            self.respond(303, location=loc.url(notice="failed"))
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
        self.respond(303, location=loc.url(notice=notice))


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
