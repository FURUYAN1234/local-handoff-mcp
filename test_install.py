"""Tests for first installation, upgrade, and configuration conflicts in Ubuntu."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

from install import install


SOURCE = Path(__file__).resolve().parent


class InstallerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "private" / "install"
        self.profile = self.base / "Windows Profile"
        self.workspace = self.base / "Project Folder"
        self.workspace.mkdir()
        self.codex = self.profile / ".codex"
        self.codex.mkdir(parents=True)
        self.codex_config = self.codex / "config.toml"
        self.codex_config.write_text('[mcp_servers.other]\ncommand = "example"\n', "utf-8")
        self.agent_rules = self.codex / "AGENTS.md"
        self.agent_rules.write_text("# Existing local rules\n", "utf-8")
        self.ag = self.profile / ".gemini" / "config"
        self.ag.mkdir(parents=True)
        self.ag_config = self.ag / "mcp_config.json"
        self.ag_config.write_text('{"mcpServers":{"another":{"command":"example"}}}', "utf-8")
        setting = patch.dict(os.environ, {"WSL_DISTRO_NAME": "Ubuntu"})
        setting.start()
        self.addCleanup(setting.stop)

    def call(self, host, tool, arguments):
        command = [sys.executable, "-B", str(self.root / "launch.py"), "--host", host, "call", tool]
        result = subprocess.run(command, text=True, input=json.dumps(arguments),
                                capture_output=True, check=True)
        return json.loads(result.stdout)

    def test_upgrade_reads_existing_record_and_keeps_registrations(self):
        install(SOURCE, self.root, self.profile, [str(self.workspace)])
        self.call("codex", "handoff_checkpoint", {
            "workspace": str(self.workspace), "goal": "Finish tests", "next_step": "Compare build",
        })
        snapshots = {path: path.read_bytes() for path in (self.codex_config, self.ag_config, self.agent_rules)}
        upgraded = self.base / "version-next"
        upgraded.mkdir()
        for name in ("handoff.py", "launch.py"):
            shutil.copyfile(SOURCE / name, upgraded / name)
        (upgraded / "VERSION").write_text("999.0.0\n", "ascii")
        install(upgraded, self.root, self.profile, [])
        status = self.call("antigravity", "handoff_status", {"workspace": str(self.workspace)})
        self.assertEqual(status["record"]["next_step"], "Compare build")
        self.assertEqual(status["record"]["owner"], "codex")
        self.assertEqual("999.0.0", json.loads((self.root / "current.json").read_text("utf-8"))["version"])
        for path, expected in snapshots.items():
            self.assertEqual(path.read_bytes(), expected)
        self.assertIn("other", tomllib.loads(self.codex_config.read_text("utf-8"))["mcp_servers"])
        self.assertIn("another", json.loads(self.ag_config.read_text("utf-8"))["mcpServers"])
        self.assertIn("# Existing local rules", self.agent_rules.read_text("utf-8"))
        with self.assertRaisesRegex(ValueError, "Downgrades"):
            install(SOURCE, self.root, self.profile, [])

    def test_conflicting_registration_keeps_both_profiles(self):
        conflict = '{"mcpServers":{"local_handoff":{"command":"example"}}}'
        self.ag_config.write_text(conflict, "utf-8")
        codex_before = self.codex_config.read_bytes()
        with self.assertRaisesRegex(ValueError, "different"):
            install(SOURCE, self.root, self.profile, [str(self.workspace)])
        self.assertEqual(self.codex_config.read_bytes(), codex_before)
        self.assertEqual(self.ag_config.read_text("utf-8"), conflict)
        self.assertFalse((self.root / "current.json").exists())


if __name__ == "__main__":
    unittest.main()
