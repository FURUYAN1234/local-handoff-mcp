import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


SERVER = Path(__file__).with_name("handoff.py")


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=SERVER.parent)
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.allowed = self.base / "allowed"
        self.allowed.mkdir()
        self.project = self.allowed / "build"
        self.project.mkdir()
        self.other_project = self.allowed / "draw"
        self.other_project.mkdir()
        self.settings = self.base / "settings.json"
        self.settings.write_text(json.dumps({
            "state": str(self.base / "state.sqlite3"),
            "git": os.environ.get("HANDOFF_TEST_GIT", "git"),
            "roots": [{"path": str(self.allowed), "partition": True}],
        }), encoding="utf-8")

    def process(self, host, *args, input_data=None):
        return subprocess.run(
            [sys.executable, str(SERVER), "--config", str(self.settings), "--host", host, *args],
            input=input_data, capture_output=True, encoding="utf-8", timeout=15,
        )

    def call(self, host, name, **arguments):
        proc = self.process(host, "call", name, input_data=json.dumps(arguments))
        payload = json.loads(proc.stdout)
        return proc.returncode, payload

    def item(self, path=None):
        return {"workspace": str(path or self.project), "goal": "修正", "next_step": "検証"}

    def test_cross_host_handoff_resumes_and_preserves_checkpoints(self):
        args = self.item()
        self.assertEqual(self.call("codex", "handoff_checkpoint", **args)[0], 0)
        self.assertEqual(self.call("antigravity", "handoff_checkpoint", **args)[0], 1)
        self.assertEqual(self.call("codex", "handoff_transition", workspace=args["workspace"], action="offer")[0], 0)
        code, status = self.call("antigravity", "handoff_status", workspace=args["workspace"])
        self.assertEqual(code, 0)
        self.assertEqual(status["record"]["phase"], "ready")
        self.assertEqual(status["record"]["next_step"], "検証")
        self.assertEqual(self.call("codex", "handoff_checkpoint", **args)[0], 1)
        self.assertEqual(self.call("antigravity", "handoff_transition", workspace=args["workspace"], action="resume")[0], 0)
        self.assertEqual(self.call("antigravity", "handoff_checkpoint", **args, checks="テスト完了")[0], 0)
        self.assertEqual(self.call("antigravity", "handoff_transition", workspace=args["workspace"], action="offer")[0], 0)
        code, recent = self.call("codex", "handoff_recent")
        self.assertEqual(code, 0)
        self.assertEqual(recent["workspaces"][0]["recipient"], "codex")
        recovered = self.call("codex", "handoff_status", workspace=args["workspace"])[1]
        self.assertEqual(recovered["record"]["checks"], "テスト完了")

    def test_abrupt_stop_requires_confirmation_and_separate_paths_stay_separate(self):
        args = self.item()
        self.assertEqual(self.call("codex", "handoff_checkpoint", **args)[0], 0)
        self.assertEqual(self.call("antigravity", "handoff_checkpoint", **self.item(self.other_project))[0], 0)
        denied = self.call("antigravity", "handoff_transition", workspace=args["workspace"], action="recover")
        self.assertEqual(denied[0], 1)
        self.assertEqual(self.call("antigravity", "handoff_transition", workspace=args["workspace"],
                                   action="recover", previous_stopped=True)[0], 0)
        self.assertEqual(self.call("codex", "handoff_checkpoint", **args)[0], 1)

    def test_concurrent_first_checkpoints_cannot_both_claim(self):
        with ThreadPoolExecutor(2) as executor:
            result = list(executor.map(lambda host: self.call(host, "handoff_checkpoint", **self.item()),
                                       ("codex", "antigravity")))
        self.assertEqual(sorted(code for code, _ in result), [0, 1])

    def test_outside_workspace_and_secrets_are_rejected(self):
        self.assertEqual(self.call("codex", "handoff_status", workspace=str(self.base))[0], 1)
        self.assertEqual(self.call("codex", "handoff_checkpoint", **self.item(),
                                   completed="API_KEY=" + "x" * 30)[0], 1)
        self.assertEqual(self.call("codex", "handoff_status", workspace=str(self.project))[1]["record"], None)

    def test_unrecorded_change_visible_without_leaking_file_names(self):
        git = os.environ.get("HANDOFF_TEST_GIT", "git")
        subprocess.run([git, "-C", str(self.project), "init", "-q"], check=True, capture_output=True)
        (self.project / "local-only-private-name.txt").write_text("unpublished", encoding="utf-8")
        code, status = self.call("antigravity", "handoff_status", workspace=str(self.project))
        self.assertEqual(code, 0)
        self.assertEqual(status["git"]["untracked"], 1)
        self.assertNotIn("local-only-private-name", json.dumps(status))

    def test_hook_only_emits_static_guidance_and_local_observation(self):
        self.assertEqual(self.call("codex", "handoff_checkpoint", **self.item())[0], 0)
        injected_text = "UNTRUSTED-HOOK-TRANSCRIPT-MARKER"
        for host, data in (
            ("codex", {"cwd": str(self.project), "transcript_path": injected_text}),
            ("antigravity", {"workspacePaths": [str(self.project)], "lastUserInput": injected_text}),
        ):
            started = self.process(host, "hook", "start", input_data=json.dumps(data))
            self.assertEqual(started.returncode, 0)
            self.assertIn("handoff_status", started.stdout)
            self.assertNotIn(injected_text, started.stdout)
            self.assertEqual(self.process(host, "hook", "stop", input_data=json.dumps(data)).returncode, 0)
        status = self.call("codex", "handoff_status", workspace=str(self.project))[1]
        self.assertEqual(set(status["observed"]), {"codex", "antigravity"})
        self.assertNotIn(injected_text, json.dumps(status))

    def test_actual_stdio_discovery_and_call(self):
        for host in ("codex", "antigravity"):
            requests = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                    "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": host, "version": "1"}}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "handoff_status", "arguments": {"workspace": str(self.project)}}},
            ]
            proc = self.process(host, "serve", input_data="\n".join(map(json.dumps, requests)) + "\n")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            messages = [json.loads(line) for line in proc.stdout.splitlines()]
            self.assertEqual([message["id"] for message in messages], [1, 2, 3])
            self.assertEqual(messages[0]["result"]["protocolVersion"], "2025-06-18")
            self.assertIn("handoff_checkpoint", {tool["name"] for tool in messages[1]["result"]["tools"]})
            self.assertEqual(json.loads(messages[2]["result"]["content"][0]["text"])["host"], host)


if __name__ == "__main__":
    unittest.main()
