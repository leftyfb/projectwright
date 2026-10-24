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

if __name__ == "__main__":
    unittest.main()
