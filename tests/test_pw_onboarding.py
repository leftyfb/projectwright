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
        (self.project / "requirements.md").write_text("""## DEMO-1 — Goal
### DEMO-1-M1 — First milestone
#### Acceptance
- **Command:** `/bin/true`
- **Scope:** `README.md`
""")
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

    def test_start_requires_confirmation_without_persisting_authorization(self):
        before = self.config_path.read_bytes()
        with patch("sys.stdin.isatty", return_value=False), patch.object(
            pw_onboarding.subprocess, "run"
        ) as run:
            self.assertEqual(pw_onboarding.start("demo", False), 2)
        self.assertEqual(self.config_path.read_bytes(), before)
        run.assert_not_called()

    def test_confirmed_start_dispatches_one_shot_without_config_mutation(self):
        before = self.config_path.read_bytes()
        result = type("R", (), {"returncode": 0})()
        with patch.object(pw_onboarding.subprocess, "run", return_value=result) as run:
            self.assertEqual(pw_onboarding.start("demo", True), 0)
        self.assertEqual(self.config_path.read_bytes(), before)
        command = run.call_args.args[0]
        self.assertEqual(command[:3], [pw_onboarding.sys.executable, "-B", str(SRC / "pw_dispatch.py")])
        self.assertEqual(command[3:], ["--project", "demo", "--one-shot"])
        self.assertNotIn("pw_task_worker", command)

    def test_one_shot_dispatch_failure_does_not_enable_persistent_execution(self):
        before = self.config_path.read_bytes()
        with patch.object(
            pw_onboarding.subprocess, "run",
            return_value=type("R", (), {"returncode": 23})(),
        ):
            self.assertEqual(pw_onboarding.start("demo", True), 23)
        self.assertEqual(self.config_path.read_bytes(), before)
        self.assertFalse(json.loads(before)["execution"]["enabled"])

    def test_persistent_execution_authorization_is_explicit_and_separate(self):
        with patch.object(pw_onboarding.subprocess, "run") as run:
            self.assertEqual(pw_onboarding.authorize_persistent_execution("demo", False), 2)
            run.assert_not_called()
        self.assertFalse(json.loads(self.config_path.read_text())["execution"]["enabled"])
        with patch("sys.stdout", new_callable=__import__('io').StringIO) as out:
            self.assertEqual(pw_onboarding.authorize_persistent_execution("demo", True), 0)
        self.assertTrue(json.loads(self.config_path.read_text())["execution"]["enabled"])
        self.assertIn("pw timer", out.getvalue())

    def test_status_resolves_embedded_relative_worktree(self):
        from pw_embedded import initialize
        repo = self.home / "task-tracker"
        initialize(repo)
        result = type("R", (), {"returncode": 0,
                                "stdout": json.dumps({"project": "task-tracker",
                                                      "decision": "disabled",
                                                      "blockers": []}),
                                "stderr": ""})()
        with patch.dict(os.environ, {"PROJECTWRIGHT_PROJECT_DIR": str(repo)}), \
             patch.object(pw_onboarding.subprocess, "run", return_value=result), \
             patch("sys.stdout", new_callable=__import__("io").StringIO) as out:
            self.assertEqual(pw_onboarding.status("task-tracker", False), 0)
            self.assertIn("Worktree: " + str(repo.resolve()), out.getvalue())
            self.assertNotIn("Worktree: ..", out.getvalue())
        with patch.dict(os.environ, {"PROJECTWRIGHT_PROJECT_DIR": str(repo)}), \
             patch.object(pw_onboarding.subprocess, "run", return_value=result), \
             patch("sys.stdout", new_callable=__import__("io").StringIO) as out:
            self.assertEqual(pw_onboarding.status("task-tracker", True), 0)
            self.assertEqual(json.loads(out.getvalue())["worktree"], str(repo.resolve()))

    def test_status_reports_unknown_when_manager_cannot_read_worktree(self):
        result = type("R", (), {"returncode": 42, "stdout": "", "stderr": "fatal: worktree unavailable"})()
        with patch.object(pw_onboarding.subprocess, "run", return_value=result), \
             patch("sys.stdout", new_callable=__import__('io').StringIO) as out, \
             patch("sys.stderr", new_callable=__import__('io').StringIO):
            self.assertEqual(pw_onboarding.status("demo", False), 42)
            human = out.getvalue()
        self.assertIn("Queue pending: unknown", human)
        self.assertIn("Current activity: unknown", human)
        self.assertIn("Verify the configured worktree exists", human)
        with patch.object(pw_onboarding.subprocess, "run", return_value=result), \
             patch("sys.stdout", new_callable=__import__('io').StringIO) as out, \
             patch("sys.stderr", new_callable=__import__('io').StringIO):
            self.assertEqual(pw_onboarding.status("demo", True), 42)
            payload = json.loads(out.getvalue())
        self.assertEqual(payload["decision"], "unknown")
        self.assertIsNone(payload["pending"])
        self.assertFalse(payload["execution_enabled"])
        self.assertIn("fatal: worktree unavailable", payload["blockers"])
        self.assertEqual(payload["next_action"], "Verify the configured worktree exists and is a Git repository, then rerun pw status")

    def test_status_malformed_manager_output_returns_nonzero(self):
        result = type("R", (), {"returncode": 0, "stdout": "not-json", "stderr": ""})()
        with patch.object(pw_onboarding.subprocess, "run", return_value=result), \
             patch("sys.stdout", new_callable=__import__('io').StringIO) as out:
            self.assertNotEqual(pw_onboarding.status("demo", True), 0)
            payload = json.loads(out.getvalue())
        self.assertEqual(payload["decision"], "unknown")
        self.assertIsNone(payload["pending"])
        self.assertEqual(payload["reason"], "Manager status unavailable")

    def test_status_invalid_manager_identity_and_counts_are_unknown(self):
        report = {"project": "other", "decision": "queued", "reason": "wrong project",
                  "pending": "3", "completed": -1, "queue_blocked": None, "blockers": []}
        result = type("R", (), {"returncode": 0, "stdout": json.dumps(report), "stderr": ""})()
        with patch.object(pw_onboarding.subprocess, "run", return_value=result), patch("sys.stdout", new_callable=__import__('io').StringIO) as out:
            self.assertEqual(pw_onboarding.status("demo", True), 0)
            payload = json.loads(out.getvalue())
        self.assertEqual(payload["project"], "demo")
        self.assertEqual(payload["decision"], "unknown")
        self.assertEqual(payload["reason"], "Manager project identity mismatch")
        self.assertIsNone(payload["pending"])
        self.assertIsNone(payload["completed"])
        self.assertIsNone(payload["queue_blocked"])
        self.assertEqual(payload["blockers"], ["Manager project identity mismatch"])
        self.assertIn("Verify the selected project configuration", payload["next_action"])

    def test_status_uninitialized_project_is_human_readable(self):
        result = type("R", (), {"returncode": 3, "stdout": json.dumps({"decision": "disabled"}), "stderr": ""})()
        with patch.object(pw_onboarding.subprocess, "run", return_value=result), patch("sys.stdout", new_callable=__import__('io').StringIO) as out:
            self.assertEqual(pw_onboarding.status("new", False), 3)
        self.assertIn("Planning: disabled", out.getvalue())
        self.assertIn("Execution: disabled", out.getvalue())
        self.assertIn("pw init --project new", out.getvalue())

    def test_status_human_and_json_share_manager_values(self):
        report = {
            "decision": "blocked",
            "reason": "dirty worktree review required",
            "pending": 3,
            "completed": 1,
            "queue_blocked": 1,
            "blockers": ["dirty_worktree_review", "approval_pending"],
        }
        result = type("R", (), {"returncode": 0, "stdout": json.dumps(report), "stderr": ""})()
        with patch.object(pw_onboarding.subprocess, "run", return_value=result), patch("sys.stdout", new_callable=__import__('io').StringIO) as out:
            self.assertEqual(pw_onboarding.status("demo", False), 0)
            human = out.getvalue()
            self.assertIn("Queue pending: 3", human)
            self.assertIn("Queue completed: 1", human)
            self.assertIn("Queue blocked: 1", human)
            self.assertIn("blocked — dirty worktree review required", human)
            self.assertIn("dirty_worktree_review, approval_pending", human)
            self.assertIn("Next action:", human)
        with patch.object(pw_onboarding.subprocess, "run", return_value=result), patch("sys.stdout", new_callable=__import__('io').StringIO) as out:
            self.assertEqual(pw_onboarding.status("demo", True), 0)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload["decision"], report["decision"])
            self.assertEqual(payload["reason"], report["reason"])
            self.assertEqual(payload["pending"], report["pending"])
            self.assertEqual(payload["completed"], report["completed"])
            self.assertEqual(payload["queue_blocked"], report["queue_blocked"])
            self.assertEqual(payload["blockers"], report["blockers"])
            self.assertFalse(payload["planning_enabled"])
            self.assertFalse(payload["execution_enabled"])
            self.assertEqual(payload["recurring_execution"], "not_configured")
            self.assertFalse(payload["recurring_execution_configured"])
            self.assertFalse(payload["recurring_execution_enabled"])

    def test_status_reads_configured_current_task_journal(self):
        journal = self.home / "custom-worker-journal.json"
        task = {"task_id": "PW12", "phase": "running"}
        journal.write_text(json.dumps({"current_task": task}))
        self.config["worker_journal_file"] = str(journal)
        self.config_path.write_text(json.dumps(self.config))
        report = {
            "decision": "running", "reason": "worker active", "pending": 1,
            "completed": 0, "queue_blocked": 0, "blockers": [],
        }
        result = type("R", (), {"returncode": 0, "stdout": json.dumps(report), "stderr": ""})()
        with patch.object(pw_onboarding.subprocess, "run", return_value=result), patch(
            "sys.stdout", new_callable=__import__('io').StringIO
        ) as out:
            self.assertEqual(pw_onboarding.status("demo", False), 0)
            self.assertIn("PW12", out.getvalue())
        with patch.object(pw_onboarding.subprocess, "run", return_value=result), patch(
            "sys.stdout", new_callable=__import__('io').StringIO
        ) as out:
            self.assertEqual(pw_onboarding.status("demo", True), 0)
            payload = json.loads(out.getvalue())
        self.assertEqual(payload["current_task"], task)

if __name__ == "__main__":
    unittest.main()
