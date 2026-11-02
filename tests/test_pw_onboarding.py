import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

SRC = Path(__file__).resolve().parents[1] / "src" / "projectwright"
sys.path.insert(0, str(SRC))
import pw_onboarding


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.config_home = self.home / "cfg"
        self.project = self.config_home / "projects/demo"
        self.project.mkdir(parents=True)
        self.config = {"id": "demo", "planning": {"enabled": False, "requirements_file": str(self.project / "requirements.md")}, "execution": {"enabled": False}}
        self.config_path = self.project / "config.json"
        self.config_path.write_text(json.dumps(self.config))
        (self.project / "requirements.md").write_text("# Requirements\n")
        self.env = patch.dict(os.environ, {"PROJECTWRIGHT_CONFIG_DIR": str(self.config_home)}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_plan_explicitly_enables_planning_only(self):
        with patch.object(pw_onboarding.subprocess, "run", return_value=type("R", (), {"returncode": 0})()) as run:
            self.assertEqual(pw_onboarding.authorize_planning("demo"), 0)
        cfg = json.loads(self.config_path.read_text())
        self.assertTrue(cfg["planning"]["enabled"])
        self.assertFalse(cfg["execution"]["enabled"])
        self.assertIn("pw_queue_manager", run.call_args.args[0])

    def test_malformed_configuration_and_escaping_requirements_fail_safely(self):
        for invalid in ("../demo", "bad/name", "Upper"):
            with self.assertRaisesRegex(ValueError, "Invalid project ID"):
                pw_onboarding._config(invalid)
        self.config_path.write_text("{")
        with self.assertRaisesRegex(ValueError, "Invalid project configuration"):
            pw_onboarding._config("demo")
        self.config_path.write_text(json.dumps({**self.config, "planning": {"requirements_file": "../outside.md"}}))
        with self.assertRaisesRegex(ValueError, "within this Projectwright project"):
            pw_onboarding._requirements_path("demo", json.loads(self.config_path.read_text()))
        for reserved in ("config.json", "queue.md", "work_log.md", "worker_state.json"):
            config = {"planning": {"requirements_file": reserved}}
            with self.assertRaisesRegex(ValueError, "reserved Projectwright state file"):
                pw_onboarding._requirements_path("demo", config)

    def test_requirements_uses_visual_before_editor(self):
        with patch.dict(os.environ, {"VISUAL": "custom-editor --wait", "EDITOR": "other"}), patch.object(
            pw_onboarding.subprocess, "run", return_value=type("R", (), {"returncode": 0})()
        ) as run:
            self.assertEqual(pw_onboarding.requirements("demo"), 0)
        self.assertEqual(run.call_args.args[0][0:2], ["custom-editor", "--wait"])
        self.assertEqual(Path(run.call_args.args[0][-1]), self.project / "requirements.md")

    def test_start_requires_confirmation_and_then_authorizes_one_worker(self):
        self.assertEqual(pw_onboarding.start("demo", False), 2)
        self.assertFalse(json.loads(self.config_path.read_text())["execution"]["enabled"])
        with patch.object(pw_onboarding.subprocess, "run", return_value=type("R", (), {"returncode": 0})()) as run:
            self.assertEqual(pw_onboarding.start("demo", True), 0)
        self.assertTrue(json.loads(self.config_path.read_text())["execution"]["enabled"])
        self.assertIn("pw_task_worker", run.call_args.args[0])

    def test_start_authorization_persists_if_worker_fails(self):
        with patch.object(pw_onboarding.subprocess, "run", return_value=type("R", (), {"returncode": 1})()):
            self.assertEqual(pw_onboarding.start("demo", True), 1)
        self.assertTrue(json.loads(self.config_path.read_text())["execution"]["enabled"])

    def test_status_uninitialized_project_is_human_readable(self):
        result = type("R", (), {"returncode": 3, "stdout": json.dumps({"decision": "disabled"}), "stderr": ""})()
        with patch.object(pw_onboarding.subprocess, "run", return_value=result), patch("sys.stdout", new_callable=__import__('io').StringIO) as out:
            self.assertEqual(pw_onboarding.status("new", False), 3)
        self.assertIn("Planning: disabled", out.getvalue())
        self.assertIn("Execution: disabled", out.getvalue())
        self.assertIn("pw init --project new", out.getvalue())

    def test_status_human_and_json(self):
        result = type("R", (), {"returncode": 0, "stdout": json.dumps({"decision": "blocked", "pending": 3, "completed": 1, "queue_blocked": 1, "blockers": ["dirty_worktree_review"]}), "stderr": ""})()
        with patch.object(pw_onboarding.subprocess, "run", return_value=result), patch("sys.stdout", new_callable=__import__('io').StringIO) as out:
            self.assertEqual(pw_onboarding.status("demo", False), 0)
            self.assertIn("Planning: disabled", out.getvalue())
            self.assertIn("Queue pending: 3", out.getvalue())
            self.assertIn("dirty_worktree_review", out.getvalue())
            self.assertIn("Current activity:", out.getvalue())
            self.assertIn("Blockers:", out.getvalue())
            self.assertIn("Next action:", out.getvalue())
        with patch.object(pw_onboarding.subprocess, "run", return_value=result), patch("sys.stdout", new_callable=__import__('io').StringIO) as out:
            self.assertEqual(pw_onboarding.status("demo", True), 0)
            self.assertEqual(json.loads(out.getvalue())["decision"], "blocked")

if __name__ == "__main__":
    unittest.main()
