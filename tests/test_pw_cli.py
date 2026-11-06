"""Unified pw command routing without executing user services."""
import io
import os
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
            "status": ("pw_onboarding", ["status"]),
            "plan": ("pw_onboarding", ["plan"]),
            "start": ("pw_onboarding", ["start"]),
            "requirements": ("pw_onboarding", ["requirements"]),
            "worker": ("pw_task_worker", []),
            "notify": ("pw_notify", []),
            "timer": ("pw_project_timer", []),
            "setup": ("pw_project_timer", ["setup"]),
            "gateway-restart": ("pw_project_timer", ["gateway-restart"]),
            "setup-user": ("pw_project_timer", ["setup-user"]),
            "defaults": ("pw_defaults", []),
            "config": ("pw_settings", []),
            "init": ("pw_init", []),
        }
        for action, (module, flags) in cases.items():
            with self.subTest(action=action):
                with patch.object(sys, "argv", ["pw", action, "--help"]), patch.object(
                    pw_dispatch.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
                ) as called:
                    self.assertEqual(pw_dispatch.cli(), 0)
                    self.assertEqual(called.call_args.args[0],
                        [sys.executable, "-B", "-m", module, *flags, "--help"])

    def test_setup_options_forward_without_side_effects(self):
        with patch.object(sys, "argv", ["pw", "setup", "--minutes", "15", "--yes"]), patch.object(
            pw_dispatch.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
        ) as called:
            self.assertEqual(pw_dispatch.cli(), 0)
            self.assertEqual(called.call_args.args[0], [
                sys.executable, "-B", "-m", "pw_project_timer", "setup",
                "--minutes", "15", "--yes",
            ])

    def test_setup_user_options_forward_without_side_effects(self):
        with patch.object(sys, "argv", ["pw", "setup-user", "--minutes", "15", "--enable-hermes-plugin"]), patch.object(
            pw_dispatch.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
        ) as called:
            self.assertEqual(pw_dispatch.cli(), 0)
            self.assertEqual(called.call_args.args[0], [
                sys.executable, "-B", "-m", "pw_project_timer", "setup-user",
                "--minutes", "15", "--enable-hermes-plugin",
            ])

    def test_explicit_legacy_config_home_ignores_inherited_embedded_location(self):
        with patch.dict(os.environ,
                        {"PROJECTWRIGHT_PROJECT_DIR": "/tmp/unrelated/example"},
                        clear=True), patch.object(
            sys, "argv", ["pw", "status", "--project", "demo",
                          "--config-dir", "/tmp/legacy-home"]
        ), patch.object(
            pw_dispatch.subprocess, "run",
            return_value=subprocess.CompletedProcess([], 0)
        ) as run:
            self.assertEqual(pw_dispatch.cli(), 0)
            environment = run.call_args.kwargs["env"]
            self.assertNotIn("PROJECTWRIGHT_PROJECT_DIR", environment)
            self.assertEqual(environment["PROJECTWRIGHT_CONFIG_DIR"],
                             "/tmp/legacy-home")

    def test_unknown_command_refuses_without_execution(self):
        with patch.object(sys, "argv", ["pw", "bad"]), patch.object(
            pw_dispatch.subprocess, "run"
        ) as called, redirect_stderr(io.StringIO()) as output:
            self.assertEqual(pw_dispatch.cli(), 2)
            called.assert_not_called()
        self.assertIn("Unknown Projectwright command: bad\\nusage: pw ", output.getvalue())
        self.assertNotIn(r"\\nusage:", output.getvalue())

    def test_help_has_no_side_effects(self):
        with patch.object(sys, "argv", ["pw", "--help"]), patch.object(
            pw_dispatch.subprocess, "run"
        ) as called, redirect_stdout(io.StringIO()):
            self.assertEqual(pw_dispatch.cli(), 0)
            called.assert_not_called()


if __name__ == "__main__":
    unittest.main()
