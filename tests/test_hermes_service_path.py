"""Unattended worker and planner resolve Hermes without shell PATH."""
from pathlib import Path
import io
import sys
import unittest
from unittest.mock import Mock, patch

SRC = Path(__file__).resolve().parents[1] / "src" / "projectwright"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pw_queue_manager as manager
import pw_task_worker as worker


class HermesServicePathTests(unittest.TestCase):
    def test_default_hermes_uses_user_local_executable(self):
        with patch("pw_project_timer.find_hermes_cli", return_value="/home/fixture/.local/bin/hermes"):
            for phase in ("planner", "worker"):
                argv, _ = manager.provider_argv(
                    {"hermes": "hermes"}, phase, prompt="fixture request")
                self.assertEqual(argv[0], "/home/fixture/.local/bin/hermes")

    def test_explicit_hermes_override_is_not_rewritten(self):
        with patch("pw_project_timer.find_hermes_cli", side_effect=AssertionError("unexpected search")):
            argv, _ = manager.provider_argv(
                {"hermes": "/custom/hermes"}, "worker")
        self.assertEqual(argv[0], "/custom/hermes")

    def test_worker_delivery_finds_hermes_outside_path(self):
        with patch.object(worker, "HERMES", "hermes"), \\
             patch("pw_project_timer.find_hermes_cli",
                   return_value="/home/fixture/.local/bin/hermes"), \\
             patch.object(worker.subprocess, "run",
                          return_value=Mock(returncode=0)) as run:
            self.assertTrue(worker.deliver("test", io.StringIO()))
        self.assertEqual(run.call_args.args[0][0], "/home/fixture/.local/bin/hermes")

    def test_missing_hermes_delivery_is_failure_not_crash(self):
        with patch.object(worker, "HERMES", "hermes"), \\
             patch("pw_project_timer.find_hermes_cli", return_value=None), \\
             patch.object(worker.subprocess, "run",
                          side_effect=FileNotFoundError("hermes")):
            output = io.StringIO()
            self.assertFalse(worker.deliver("test", output))
            self.assertIn("not delivered", output.getvalue())


if __name__ == "__main__":
    unittest.main()
