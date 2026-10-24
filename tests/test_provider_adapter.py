"""Harness-neutral command provider contracts, using only the local Python interpreter."""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "projectwright"))
from project_queue_manager import provider_argv
import project_queue_planner as planner
import project_task_worker as worker


class CommandProviderTests(unittest.TestCase):
    def test_hermes_behavior_stays_compatible(self):
        cfg = {"hermes": "/tmp/fixture-hermes"}
        self.assertEqual(provider_argv(cfg, "worker"), (
            ["/tmp/fixture-hermes", "chat", "--oneshot", "--query-file", "-", "--ignore-rules"], True))
        self.assertEqual(provider_argv(cfg, "planner", prompt="hello"), (
            ["/tmp/fixture-hermes", "--ignore-rules", "-z", "hello"], False))

    def test_command_rejects_unsafe_or_missing_argv(self):
        for argv in ([], ["relative-agent"], ["agent; rm -rf /"], [""]):
            cfg = {"provider": {"type": "command", "worker_argv": argv}}
            with self.subTest(argv=argv), self.assertRaises(ValueError):
                provider_argv(cfg, "worker")
        with self.assertRaises(ValueError):
            provider_argv({"provider": {"type": "unknown"}}, "planner", prompt="test")

    def test_non_hermes_planner_reads_prompt_stdin(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = "import json,sys; text=sys.stdin.read();print(json.dumps({'tasks': [], 'got': text}))"
            cfg = {
                "worktree": tmp,
                "provider": {"type": "command", "planner_argv": [sys.executable, "-c", code]},
            }
            result = planner.run_planner(cfg, "fixture prompt", timeout=5)
            self.assertEqual(result["got"], "fixture prompt")
            self.assertEqual(result["tasks"], [])

    def test_non_hermes_worker_reads_prompt_stdin(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {
                "provider": {"type": "command", "worker_argv": [
                    sys.executable, "-c",
                    "import sys;print('received:' + sys.stdin.read())",
                ]},
            }
            with patch.object(worker, "PROJECT", cfg), patch.object(worker, "WORKTREE", Path(tmp)), \
                 patch.object(worker, "TIMEOUT", 5):
                with open(Path(tmp) / "stderr.log", "w") as log:
                    code, output = worker.run_agent("hello", log)
            self.assertEqual(code, 0)
            self.assertEqual(output.strip(), "received:hello")


if __name__ == "__main__":
    unittest.main()
