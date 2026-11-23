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

    def test_mcp_settings_link_opens_client_specific_instructions(self):
        status, _, body = self.request("GET", "/manual?section=opencode")
        self.assertEqual(status, 200)
        self.assertIn("OpenCodeとローカルモデル", body)
        self.assertNotIn("WSL版Strata", body)

    def test_reopen_recognizes_only_the_expected_instance(self):
        from io import StringIO
        data = {"port": self.server.server_port, "instance": self.server.instance}
        self.assertEqual(existing_dashboard(StringIO(json.dumps(data))), self.server.origin)
        data["instance"] = "x" * 32
        self.assertIsNone(existing_dashboard(StringIO(json.dumps(data))))
