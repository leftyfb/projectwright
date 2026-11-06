"""Tests for local milestone approval and disabled timer authorization."""
from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "projectwright"))
import pw_onboarding


class LocalApprovalAndAuthorizationTests(unittest.TestCase):
    def test_authorize_creates_disabled_timer_and_prints_enable_instructions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state = root / "myproject" / ".pw"
            state.mkdir(parents=True)
            config = {"id": "myproject", "execution": {"enabled": False}}
            written = []
            output = io.StringIO()
            with patch.object(pw_onboarding, "_config", return_value=(state / "config.json", config)), \
                 patch.object(pw_onboarding, "_project_dir", return_value=state), \
                 patch.object(pw_onboarding.Path, "home", return_value=root), \
                 patch.object(pw_onboarding, "_write", side_effect=lambda path, cfg: written.append(json.loads(json.dumps(cfg)))), \
                 patch.object(pw_onboarding.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as runner, \
                 redirect_stdout(output):
                self.assertEqual(pw_onboarding.authorize_persistent_execution("myproject", True, 5), 0)
            self.assertTrue(written[0]["execution"]["enabled"])
            self.assertEqual(runner.call_args.args[0][-4:], ["install", "myproject", "--minutes", "5"])
            self.assertIn("LEFT DISABLED", output.getvalue())
            self.assertIn("No recurring tasks will run", output.getvalue())
            self.assertIn("pw timer enable myproject", output.getvalue())
            self.assertIn("pw timer status myproject", output.getvalue())

    def test_failed_timer_install_does_not_authorize_execution(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state = root / "myproject" / ".pw"
            state.mkdir(parents=True)
            config = {"id": "myproject", "execution": {"enabled": False}}
            with patch.object(pw_onboarding, "_config", return_value=(state / "config.json", config)), \
                 patch.object(pw_onboarding, "_project_dir", return_value=state), \
                 patch.object(pw_onboarding.Path, "home", return_value=root), \
                 patch.object(pw_onboarding, "_write") as write, \
                 patch.object(pw_onboarding.subprocess, "run", return_value=subprocess.CompletedProcess([], 2)):
                with self.assertRaisesRegex(ValueError, "Timer installation failed"):
                    pw_onboarding.authorize_persistent_execution("myproject", True, 5)
            write.assert_not_called()
            self.assertFalse(config["execution"]["enabled"])

    def test_local_approval_uses_same_guard_and_pending_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td) / "myproject" / ".pw"
            directory.mkdir(parents=True)
            pending = {"project": "myproject", "milestone": "APP-1-M1", "head": "abc123"}
            (directory / "telegram_approval_pending.json").write_text(json.dumps(pending))
            policy = {"milestones": {"APP-1-M1": {
                "requirement": "APP-1",
                "command": ["python3", "-m", "unittest"],
                "scope_paths": ["app.py"]}}}
            cfg = {"id": "myproject"}
            receipt = {"git_head": "abc123"}
            output = io.StringIO()
            with patch.object(pw_onboarding, "_config", return_value=(directory / "config.json", cfg)), \
                 patch("pw_milestone_guard.policy_for_project", return_value=policy), \
                 patch("pw_config.load", return_value=(directory / "config.json", cfg)), \
                 patch("pw_milestone_guard.approve", return_value=receipt) as approve, \
                 redirect_stdout(output):
                self.assertEqual(pw_onboarding.approve_local("myproject", "APP-1-M1", True), 0)
            self.assertEqual(approve.call_args.kwargs["expected"], pending)
            self.assertIn("APP-1-M1 accepted", output.getvalue())
            self.assertFalse((directory / "telegram_approval_pending.json").exists())


if __name__ == "__main__":
    unittest.main()
