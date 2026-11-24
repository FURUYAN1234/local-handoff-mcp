import json
from http.client import HTTPConnection
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from clients import Client
from dashboard import DashboardServer, existing_dashboard
from handoff import HandoffStore


class DashboardTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        settings = root / "settings.json"
        settings.write_text(json.dumps({
            "state": str(root / "state.sqlite3"), "git": "/usr/bin/git", "roots": [{"path": str(root)}],
        }))
        (root / "current.json").write_text("{}")
        store = HandoffStore(settings, "codex")
        store.checkpoint(root, False, {"goal": "<script>alert(1)</script>", "next_step": "Run the test"})
        self.server = DashboardServer(store, 0, root)
        self.addCleanup(self.server.server_close)
        worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(worker.join, 5)
        self.addCleanup(self.server.shutdown)
        client = Client("claude-code", "/usr/bin/claude", True, False, "unknown", False)
        self.state = {"claude-code": client}, {"LM Studio": (True, None, 1234, None), "Ollama": (False, None, 11434, None)}

    def request(self, method, url, body=None, headers=None):
        conn = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            conn.request(method, url, body=body, headers=headers or {})
            response = conn.getresponse()
            return response.status, response.headers, response.read().decode("utf-8")
        finally:
            conn.close()

    def test_denied_or_expired_action_gets_dashboard_back(self):
        with patch("dashboard.discover", return_value=self.state), patch("dashboard.configure_claude") as register:
            headers = {"Origin": self.server.origin, "Content-Type": "application/x-www-form-urlencoded"}
            form = {"client": "claude-code", "action": "register", "token": "stale"}
            status, response, _ = self.request("POST", "/client", urlencode(form), headers)
            self.assertEqual(status, 303)
            self.assertEqual(response["Location"], "/?notice=failed")
            register.assert_not_called()

            status, response, page = self.request("GET", response["Location"])
            self.assertEqual(status, 200)
            self.assertEqual(response["Referrer-Policy"], "same-origin")
            self.assertIn("操作を完了できませんでした", page)
            self.assertIn("&lt;script&gt;", page)
            self.assertIn("LM Studio", page)
            self.assertIn("導入済み · 標準ポート 1234 の応答なし", page)
            self.assertNotIn("<script>", page)

            form["token"] = self.server.token
            status, _, _ = self.request("POST", "/client", urlencode(form), dict(headers, Origin="http://foreign"))
            self.assertEqual(status, 403)
            register.assert_not_called()
            register.return_value = True
            status, response, _ = self.request("POST", "/client", urlencode(form), headers)
            self.assertEqual(status, 303)
            self.assertEqual(response["Location"], "/?notice=registered")
            register.assert_called_once()

    def test_mcp_settings_links_open_client_specific_html_guides(self):
        cases = {
            "codex": ("Codexの設定", "Local Handoff MCP"),
            "antigravity": ("Antigravityの設定", "<code>local_handoff</code>"),
            "claude-code": ("Claude Codeの設定", "MCPを登録"),
            "opencode": ("OpenCodeとローカルモデル", "OpenCode CLIをインストール"),
            "strata": ("WSL版Strataの設定", "Settings → Tools"),
        }
        for client, (title, details) in cases.items():
            with self.subTest(client=client):
                status, headers, body = self.request("GET", f"/manual?section={client}")
                self.assertEqual(status, 200)
                self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
                self.assertIn(f"<h1>{title}</h1>", body)
                self.assertIn(details, body)
                self.assertIn(f'href="/#client-{client}"', body)
                self.assertNotIn("<h2>導入・更新</h2>", body)
                self.assertNotIn("```", body.split("</article>")[0])
                if client in ("claude-code", "opencode", "strata"):
                    self.assertIn("<pre><code>", body)

    def test_muse_code_and_web_have_separate_setup_routes(self):
        cls = Client("muse-code", "/test/muse", True, False, "unknown", False, cli_installed=True)
        state = {"muse-code": cls}, {}
        with patch("dashboard.discover", return_value=state):
            for lang, action, web in (("ja", "MCPを登録", "Web版Museと連携する"),
                                      ("en", "Register MCP", "Connect with Muse on the web")):
                _, _, page = self.request("GET", f"/?lang={lang}")
                self.assertIn('id="client-muse-code"', page)
                self.assertIn(action, page)
                self.assertIn(web, page)
                _, _, manual = self.request("GET", f"/manual?section=muse-web&lang={lang}")
                self.assertEqual(manual.count("<ol>"), 1)
                self.assertEqual(manual.count("<li>"), 3)
                self.assertIn('href="https://muse.ai/"', manual)
                self.assertEqual(manual.count("data-copy hidden"), 1)
                self.assertNotIn('id="copy-manual"', manual)

    def test_full_manual_formats_lists_code_and_links(self):
        for url in ("/manual", "/manual?section=%3Cscript%3E"):
            with self.subTest(url=url):
                status, headers, body = self.request("GET", url)
                self.assertEqual(status, 200)
                self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
                self.assertIn("<h1>操作・MCP設定マニュアル</h1>", body)
                self.assertIn("<ol><li>", body)
                self.assertIn("<ul><li>", body)
                self.assertIn("<code>handoff_status</code>", body)
                self.assertIn('href="https://opencode.ai/docs/mcp-servers/"', body)
                self.assertNotIn("<script>", body)

    def test_client_card_distinguishes_registration_from_guide(self):
        with patch("dashboard.discover", return_value=self.state):
            _, _, body = self.request("GET", "/")
        self.assertIn('id="client-claude-code"', body)
        self.assertIn('<button>MCPを登録</button>', body)
        self.assertIn('href="/manual?section=claude-code"', body)
        self.assertIn('>MCP手順を見る</a>', body)

    def test_english_dashboard_keeps_language_through_actions_and_manual(self):
        with patch("dashboard.discover", return_value=self.state), patch("dashboard.configure_claude") as register:
            status, _, page = self.request("GET", "/?lang=en&phase=active")
            self.assertEqual(status, 200)
            for expected in ('<html lang="en">', "Project handoffs", "Filter", "In progress",
                             "Project name or path", "MCP setup guide", "Register MCP",
                             "Get desktop app", "Installed · No response on default port 1234",
                             "Run the test", 'name="lang" value="en"'):
                self.assertIn(expected, page)
            self.assertNotIn("管理画面", page)
            self.assertIn('href="/manual?section=claude-code&amp;lang=en"', page)
            self.assertIn('href="/?phase=active" lang="ja"', page)

            headers = {"Origin": self.server.origin, "Content-Type": "application/x-www-form-urlencoded"}
            form = {"client": "claude-code", "action": "register", "token": self.server.token}
            register.return_value = True
            status, response, _ = self.request("POST", "/client?lang=en", urlencode(form), headers)
            self.assertEqual(status, 303)
            self.assertEqual(response["Location"], "/?notice=registered&lang=en")
            _, _, page = self.request("GET", response["Location"])
            self.assertIn("MCP registered in Claude Code", page)

        status, _, page = self.request("GET", "/manual?section=claude-code&lang=en")
        self.assertEqual(status, 200)
        self.assertIn('<h1>Claude Code setup</h1>', page)
        self.assertIn('href="/?lang=en#client-claude-code"', page)
        self.assertIn('href="/manual?section=claude-code" lang="ja"', page)
        self.assertIn("After installing Claude Code", page)

    def test_english_project_details_and_zero_results(self):
        path = self.server.store.projects()["workspaces"][0]["workspace"]
        with patch("dashboard.discover", return_value=self.state):
            url = "/?" + urlencode({"project": path, "lang": "en"})
            _, _, page = self.request("GET", url)
            self.assertIn("Handoff record", page)
            self.assertIn("Checkpoint history", page)
            self.assertIn('<time datetime="', page)
            self.assertIn('href="/manual?section=projects&amp;lang=en"', page)
            self.assertIn("Run the test", page)
            self.assertIn("&lt;script&gt;", page)

            _, _, page = self.request("GET", "/?query=does-not-exist&lang=en")
            self.assertIn("No handoff records match these filters.", page)
            _, _, page = self.request("GET", "/?lang=unsupported")
            self.assertIn('<html lang="ja">', page)

    def test_project_registration_guide_distinguishes_workspaces_from_apps(self):
        for suffix, title, back in (
            ("", "プロジェクトの追加", "/#projects"),
            ("&lang=en", "Add a project", "/?lang=en#projects"),
        ):
            with self.subTest(suffix=suffix):
                status, _, body = self.request("GET", "/manual?section=projects" + suffix)
                self.assertEqual(status, 200)
                self.assertIn(f"<h1>{title}</h1>", body)
                self.assertIn(f'href="{back}"', body)
                self.assertIn("Install.bat --workspace", body)
                self.assertIn("<code>handoff_checkpoint</code>", body)

    def test_checkpoint_text_follows_dashboard_language(self):
        store = self.server.store
        workspace = store.projects()["workspaces"][0]["workspace"]
        store.call("handoff_checkpoint", {
            "workspace": workspace, "goal": "原文の目的", "next_step": "原文の次の操作",
            "checks": "原文の確認結果", "goal_en": "Translated goal",
            "next_step_en": "Translated next step", "checks_en": "Translated check",
        })
        with patch("dashboard.discover", return_value=self.state):
            query = urlencode({"lang": "en", "project": workspace})
            _, _, page = self.request("GET", "/?" + query)
            for expected in ("Translated goal", "Translated next step", "Translated check"):
                self.assertIn(expected, page)
            self.assertEqual(page.count("Translated next step"), 2)
            self.assertNotIn("原文の", page)

            _, _, page = self.request("GET", "/?" + urlencode({"project": workspace}))
            for original in ("原文の目的", "原文の次の操作", "原文の確認結果"):
                self.assertIn(original, page)
            self.assertNotIn("Translated", page)

        store.call("handoff_checkpoint", {"workspace": workspace, "goal": "新しい目的", "next_step": "原文の次の操作"})
        current = store.call("handoff_status", {"workspace": workspace})["record"]
        self.assertNotIn("goal_en", current)
        self.assertEqual(current["next_step_en"], "Translated next step")

    def test_mcp_bulk_registration_guide_matches_dashboard_language(self):
        with patch("dashboard.discover", return_value=self.state):
            _, _, page = self.request("GET", "/?lang=en")
        self.assertIn('href="/manual?section=mcp-apps&amp;lang=en"', page)

        _, _, page = self.request("GET", "/manual?section=mcp-apps&lang=en")
        self.assertIn('href="/?lang=en#client-title"', page)
        self.assertIn('src="/dashboard.js"', page)
        article = page.split('<article class="guide-copy">', 1)[1].split("</article>")[0]
        self.assertIn("Copy request", article)
        self.assertIn("Register Local Handoff MCP", article)
        self.assertIn("handoff_status", article)
        self.assertNotIn("このPC", article)

        for query in ("", "&lang=en"):
            with self.subTest(query=query):
                _, _, page = self.request("GET", "/manual?section=mcp-apps" + query)
                self.assertEqual(page.count("data-copy hidden"), 1)
                self.assertNotIn('id="copy-manual"', page)

    def test_each_scoped_guide_has_one_copyable_request(self):
        for section in ("projects", "codex", "antigravity", "claude-code", "opencode", "strata", "muse-code", "mcp-apps"):
            for language, copy_label, manual_title in (
                ("ja", "依頼文をコピー", "自分で設定する"),
                ("en", "Copy request", "Set it up yourself"),
            ):
                with self.subTest(section=section, language=language):
                    _, _, page = self.request("GET", f"/manual?section={section}&lang={language}")
                    self.assertEqual(page.count("data-copy hidden"), 1)
                    self.assertNotIn('id="copy-manual"', page)
                    self.assertIn(copy_label, page)
                    self.assertIn(f'href="/manual?lang={language}"' if language == "en" else 'href="/manual"', page)
                    if section == "mcp-apps":
                        self.assertNotIn(manual_title, page)
                    else:
                        self.assertIn(f"<h3>{manual_title}</h3>", page)
                    if section == "projects":
                        self.assertIn("この作業フォルダーを Local Handoff MCP" if language == "ja" else
                                      "Register this workspace", page)

    def test_full_manual_remains_copyable(self):
        _, _, page = self.request("GET", "/manual")
        self.assertIn('id="copy-manual"', page)
        full_text = page.split('id="copy-manual"', 1)[1]
        self.assertIn("マニュアル全体をコピー", full_text)
        self.assertIn("# 操作・MCP設定マニュアル", full_text)
        self.assertIn("## ローカルデータ", full_text)
        self.assertIn("Install.bat --workspace", full_text)
        self.assertNotIn("text agent-ja", full_text)

    def test_periodic_refresh_serves_only_recognition_and_reuses_recent_scan(self):
        known = self.state
        rediscovered = known[0], {"LM Studio": (True, 32487, 1234, None)}
        with patch("dashboard.discover", side_effect=[known, rediscovered]) as discover:
            _, headers, page = self.request("GET", "/?lang=en")
            self.assertIn('src="/dashboard.js"', page)
            self.assertIn('data-refresh-url="/clients?lang=en"', page)
            self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
            self.assertIn("connect-src 'self'", headers["Content-Security-Policy"])

            _, _, panel = self.request("GET", "/clients?lang=en")
            self.assertIn("Installed · No response on default port 1234", panel)
            self.assertEqual(discover.call_count, 1)

            self.server.scanned_at -= 61
            _, _, panel = self.request("GET", "/clients?lang=en")
            self.assertIn("Listening on port 32487", panel)
            self.assertNotIn("Project handoffs", panel)
            self.assertNotIn("Run the test", panel)
            self.assertEqual(discover.call_count, 2)

        self.assertEqual(self.request("GET", "/clients", headers={"Sec-Fetch-Site": "cross-site"})[0], 403)

    def test_reopen_recognizes_only_the_expected_instance(self):
        from io import StringIO
        data = {"port": self.server.server_port, "instance": self.server.instance}
        self.assertEqual(existing_dashboard(StringIO(json.dumps(data))), self.server.origin)
        data["instance"] = "x" * 32
        self.assertIsNone(existing_dashboard(StringIO(json.dumps(data))))
