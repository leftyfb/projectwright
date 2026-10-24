"""Timer status CLI preserves the underlying systemctl result."""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "projectwright"))
import pw_project_timer as timer

class TimerStatusTests(unittest.TestCase):
    def test_status_returns_systemctl_code_without_changing_units(self):
        with tempfile.TemporaryDirectory(prefix="pw-status-") as home:
            root = Path(home)
            scripts = root / ".hermes" / "scripts"
            scripts.mkdir(parents=True)
            (scripts / "pw_dispatch.py").write_text("# fixture\n")
            projects = root / "projects" / "fixture"
            projects.mkdir(parents=True)
            (projects / "config.json").write_text(json.dumps({"id": "fixture"}))
            argv = ["pw_project_timer.py", "status", "fixture", "--root", str(root / "projects")]
            with patch.object(timer.Path, "home", return_value=root), \
                 patch.object(timer.sys, "argv", argv), \
                 patch.object(timer.subprocess, "run", return_value=subprocess.CompletedProcess([], 3)) as run:
                self.assertEqual(timer.main(), 3)
            self.assertEqual(run.call_count, 1)
            self.assertIn("status", run.call_args.args[0])
            self.assertNotIn("enable", run.call_args.args[0])

    def test_status_still_works_when_dispatcher_and_config_missing(self):
        with tempfile.TemporaryDirectory(prefix="pw-missing-status-") as home:
            root = Path(home)
            argv = ["pw_project_timer.py", "status", "fixture", "--root", str(root / "missing")]
            with patch.object(timer.Path, "home", return_value=root), \
                 patch.object(timer.sys, "argv", argv), \
                 patch.object(timer.subprocess, "run", return_value=subprocess.CompletedProcess([], 4)) as run:
                self.assertEqual(timer.main(), 4)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][:3], ["systemctl", "--user", "status"])

    def test_check_uses_projectwright_config_home_by_default(self):
        with tempfile.TemporaryDirectory(prefix="pw-timer-xdg-") as base:
            root = Path(base)
            project = root / "projects" / "fixture"
            project.mkdir(parents=True)
            (project / "config.json").write_text(json.dumps({"id": "fixture"}))
            argv = ["pw_project_timer.py", "check", "fixture"]
            with patch.object(timer.sys, "argv", argv), \
                 patch.dict(timer.os.environ, {"PROJECTWRIGHT_CONFIG_DIR": str(root)}, clear=True), \
                 patch.object(timer.subprocess, "run") as runner, \
                 patch("builtins.print"):
                self.assertEqual(timer.main(), 0)
            runner.assert_not_called()

if __name__ == "__main__":
    unittest.main()
