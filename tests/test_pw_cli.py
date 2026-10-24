"""Unified pw command routing without executing user services."""
import io
import subprocess
import sys
import unittest
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "projectwright"))
import pw_dispatch


class UnifiedCommandTests(unittest.TestCase):
    def test_commands_route_to_existing_modules(self):
        cases = {
            "tick": ("pw_dispatch", []),
            "status": ("pw_queue_manager", ["--status"]),
            "plan": ("pw_queue_manager", ["--once"]),
            "worker": ("project_task_worker", []),
            "notify": ("pw_notify", []),
            "timer": ("pw_project_timer", []),
        }
        for action, (module, flags) in cases.items():
            with self.subTest(action=action):
                with patch.object(sys, "argv", ["pw", action, "--help"]), patch.object(
                    pw_dispatch.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
                ) as called:
                    self.assertEqual(pw_dispatch.cli(), 0)
                    self.assertEqual(called.call_args.args[0],
                        [sys.executable, "-B", "-m", module, *flags, "--help"])

    def test_unknown_command_refuses_without_execution(self):
        with patch.object(sys, "argv", ["pw", "bad"]), patch.object(
            pw_dispatch.subprocess, "run"
        ) as called, redirect_stderr(io.StringIO()):
            self.assertEqual(pw_dispatch.cli(), 2)
            called.assert_not_called()

    def test_help_has_no_side_effects(self):
        with patch.object(sys, "argv", ["pw", "--help"]), patch.object(
            pw_dispatch.subprocess, "run"
        ) as called, redirect_stdout(io.StringIO()):
            self.assertEqual(pw_dispatch.cli(), 0)
            called.assert_not_called()


if __name__ == "__main__":
    unittest.main()
