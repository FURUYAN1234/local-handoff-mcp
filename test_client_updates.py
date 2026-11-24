from pathlib import Path
import json
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from clients import Client, claude_auth_command, discover, registered, lmstudio_status, strata_install
from dashboard import client_card


def command_result(stdout, stderr="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


class ClientUpdates(unittest.TestCase):
    def test_claude_direct_login_requires_documented_subcommand(self):
        for help_text, expected in (
            ("Commands:\n  auth    Manage authentication\n  mcp     Configure MCP", True),
            ("Commands:\n  mcp     Configure MCP\n  setup-token  authentication", False),
        ):
            with self.subTest(help_text=help_text), patch("clients.capture", return_value=command_result(help_text)):
                self.assertEqual(claude_auth_command("/usr/bin/claude", False, Path("/tmp")), expected)

    def test_old_claude_card_describes_terminal_before_clicking(self):
        old = Client("claude-code", "/usr/bin/claude", True, True, "unknown", False)
        newer = Client("claude-code", "/usr/bin/claude", True, True, "signed-out", False, True)
        old_card = client_card(old, "local-token", False)
        self.assertIn("ターミナル", old_card)
        self.assertIn("/login", old_card)
        self.assertNotIn("認証ページを開く</button>", old_card)
        self.assertIn("認証ページを開く</button>", client_card(newer, "local-token", False))

    def test_missing_opencode_links_to_the_official_installation_guide(self):
        opencode = Client("opencode", None, False, False, "unknown", False)
        card = client_card(opencode, "local-token", False)
        self.assertIn('href="https://opencode.ai/docs/#desktop"', card)
        self.assertIn("アプリを取得", card)
        self.assertIn("CLIをインストール", card)

    def test_installed_app_and_cli_have_disabled_acquisition_controls(self):
        installed = Client("codex", "/usr/bin/codex", True, True, "signed-in", False,
                           desktop_installed=True, cli_installed=True)
        card = client_card(installed, "local-token", False)
        self.assertIn("disabled>アプリ · インストール済み", card)
        self.assertIn("disabled>CLI · インストール済み", card)
        self.assertNotIn("アプリを取得", card)

    def test_muse_registration_reports_enabled_entry_from_settings(self):
        with tempfile.TemporaryDirectory() as name:
            home = Path(name)
            config = home / ".config/muse/settings.json"
            config.parent.mkdir(parents=True)
            self.assertFalse(registered(home, "muse-code"))
            for enabled in (False, True):
                config.write_text(json.dumps({"mcpServers": {"local_handoff": {"enabled": enabled}}}))
                self.assertEqual(registered(home, "muse-code"), enabled)

    def test_muse_registration_preserves_existing_disabled_or_foreign_entry(self):
        from clients import configure_muse
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "launch.py").touch()
            (root / "current.json").touch()
            client = Client("muse-code", "/test/muse", True, False, "unknown", False)
            for info, expected in (({"servers": [{"name": "local_handoff"}]}, False),
                                   ({"servers": []}, True)):
                scanned = command_result(json.dumps(info))
                with patch("clients.capture", side_effect=[scanned, command_result("")]) as run:
                    self.assertEqual(configure_muse(client, root), expected)
                    self.assertEqual(run.call_count, 2 if expected else 1)
                    if expected:
                        args = run.call_args.args[0]
                        self.assertEqual(args[:4], ["/test/muse", "mcp", "add-json", "local_handoff"])
                        self.assertEqual(json.loads(args[4])["args"][-3:], ["--host", "muse-code", "serve"])

    def test_ollama_stays_detectable_if_windows_app_inventory_times_out(self):
        with (patch("clients.windows_inventory", return_value={}),
              patch("clients.runtime_available", return_value=False),
              patch("clients.local_executable", return_value=None),
              patch("clients.WINDOWS_CURL") as curl,
              patch.dict("clients.os.environ", {"WSL_DISTRO_NAME": "Ubuntu"}),
              patch("clients.capture", return_value=command_result('{"version":"0.40.17"}')) as run):
            curl.is_file.return_value = True
            curl.__str__.return_value = "curl.exe"
            _, runtimes = discover(Path("/tmp"))
            self.assertEqual(runtimes["Ollama"], (True, 11434, 11434, None))
            self.assertIn("http://127.0.0.1:11434/api/version", run.call_args.args[0])
            run.return_value = command_result('{"error":"not Ollama"}')
            _, runtimes = discover(Path("/tmp"))
            self.assertEqual(runtimes["Ollama"], (False, None, 11434, None))

    def test_lmstudio_reports_only_valid_status_ports(self):
        self.assertEqual(lmstudio_status('{"running":true,"port":32487}'), (True, 32487))
        self.assertEqual(lmstudio_status('{"running":false,"port":1234}'), (False, 1234))
        self.assertEqual(lmstudio_status('{"running":true,"port":70000}'), (None, None))

    def test_strata_detects_standard_furu_install_only_with_real_host(self):
        with tempfile.TemporaryDirectory() as name, patch("clients.local_executable", return_value=None):
            home = Path(name)
            tool = home / "Codex/tools/strata"
            app = tool / "releases/test/app/usr/lib/Strata"
            host = app / "host/server/index.mjs"
            host.parent.mkdir(parents=True)
            (tool / "active-release.json").write_text('{"app_version":"0.2.12","app":"' + str(app) + '"}')
            self.assertFalse(strata_install(home))
            host.write_text("// fixture")
            self.assertTrue(strata_install(home))
