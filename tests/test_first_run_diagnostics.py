import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "projectwright"
sys.path.insert(0, str(SOURCE))

import pw_milestone_guard as guard
import pw_onboarding
import pw_queue_planner


class RequirementsDiagnosticsTests(unittest.TestCase):
    def test_reports_missing_milestone_and_acceptance_fields(self):
        requirements = """# Requirements
## DEMO-1 — Goal
### DEMO-1-M1 — First
#### Acceptance
- **Scope:** `src/app.py`
### DEMO-1-M2 — Second
"""
        report = guard.validate_requirements(requirements)
        self.assertFalse(report["valid"])
        codes = {item["code"] for item in report["issues"]}
        self.assertEqual(codes, {"missing_acceptance_command", "missing_acceptance",})
        self.assertEqual(report["issues"][0]["milestone"], "DEMO-1-M1")
        self.assertEqual(report["issues"][0]["requirement"], "DEMO-1")

    def test_reports_empty_and_malformed_requirement_headings(self):
        empty = guard.validate_requirements("")
        self.assertIn("missing_requirement_heading", {item["code"] for item in empty["issues"]})
        malformed = guard.validate_requirements("""## DEMO-7 Goal
### DEMO-7-M1 — First
""")
        codes = {item["code"] for item in malformed["issues"]}
        self.assertIn("malformed_requirement_heading", codes)
        self.assertIn("missing_requirement_heading", codes)

    def test_reports_malformed_heading_and_invalid_literal_scope(self):
        requirements = """## DEMO-1 — Goal
### DEMO-1-M1 First
#### Acceptance
- **Command:** `pytest tests && echo bad`
- **Scope:** `:(glob)src/**/*.py`
"""
        report = guard.validate_requirements(requirements)
        codes = {item["code"] for item in report["issues"]}
        self.assertIn("malformed_milestone_heading", codes)
        self.assertIn("invalid_acceptance_command", codes)
        self.assertIn("invalid_acceptance_scope", codes)

    def test_valid_requirements_have_normalized_policy(self):
        requirements = """## DEMO-1 — Goal
### DEMO-1-M1 — First
#### Acceptance
- **Command:** `python -m pytest tests/test_app.py -q`
- **Scope:** `src/app.py`
"""
        report = guard.validate_requirements(requirements)
        self.assertTrue(report["valid"])
        self.assertEqual(report["milestones"], ["DEMO-1-M1"])

    def test_rejects_nested_heading_inside_acceptance_like_policy_parser(self):
        requirements = """## DEMO-1 — Goal
### DEMO-1-M1 — First
#### Acceptance
- **Command:** `true`
- **Scope:** `x.py`
##### Notes
"""
        report = guard.validate_requirements(requirements)
        self.assertFalse(report["valid"])
        self.assertIn("invalid_acceptance_entry", {item["code"] for item in report["issues"]})
        with self.assertRaisesRegex(ValueError, "Invalid Acceptance entry"):
            guard.embedded_acceptance_policy(requirements)

    def test_rejects_indented_acceptance_heading_not_seen_by_policy_parser(self):
        requirements = """## DEMO-1 — Goal
### DEMO-1-M1 — First
  #### Acceptance
- **Command:** `true`
- **Scope:** `x.py`
"""
        report = guard.validate_requirements(requirements)
        self.assertFalse(report["valid"])
        self.assertIn("missing_acceptance", {item["code"] for item in report["issues"]})
        self.assertIsNone(guard.embedded_acceptance_policy(requirements))

    def test_acceptance_ends_at_heading_at_or_above_its_level(self):
        for heading in ("# Notes", "## Notes", "### Notes", "#### Notes"):
            with self.subTest(heading=heading):
                requirements = f"""## DEMO-1 — Goal
### DEMO-1-M1 — First
#### Acceptance
- **Command:** `true`
- **Scope:** `x.py`
{heading}
"""
                report = guard.validate_requirements(requirements)
                self.assertTrue(report["valid"], report["issues"])
                self.assertIsNotNone(guard.embedded_acceptance_policy(requirements))

    def test_accepts_milestone_id_with_suffix(self):
        requirements = """## DEMO-1 — Goal
### DEMO-1-M1-API — First API milestone
#### Acceptance
- **Command:** `true`
- **Scope:** `x.py`
"""
        report = guard.validate_requirements(requirements)
        self.assertTrue(report["valid"], report["issues"])
        self.assertEqual(report["milestones"], ["DEMO-1-M1-API"])
        policy = guard.embedded_acceptance_policy(requirements)
        self.assertIn("DEMO-1-M1-API", policy["milestones"])


class PlanDiagnosticsTests(unittest.TestCase):
    def test_plan_reports_actionable_manager_diagnostics(self):
        result = type("R", (), {
            "returncode": 3,
            "stdout": json.dumps({"decision": "blocked", "reason": "Requirements file missing",
                                   "blockers": ["requirements_missing"]}),
            "stderr": "",
        })()
        config_path = pathlib.Path(tempfile.mkdtemp()) / "config.json"
        config_path.write_text(json.dumps({"id": "demo", "planning": {"enabled": False}}))
        requirements = config_path.parent / "requirements.md"
        requirements.write_text("## DEMO-1 — Goal\n### DEMO-1-M1 — First\n#### Acceptance\n- **Command:** `true`\n- **Scope:** `x.py`\n")
        with patch.object(pw_onboarding, "_config", return_value=(config_path, {"id": "demo", "planning": {"enabled": False}})), \
             patch.object(pw_onboarding, "_requirements_path", return_value=requirements), \
             patch.object(pw_onboarding.subprocess, "run", return_value=result), \
             patch("sys.stderr", new_callable=__import__("io").StringIO) as err:
            self.assertEqual(pw_onboarding.authorize_planning("demo"), 3)
        self.assertIn("requirements_missing", err.getvalue())
        self.assertIn("Requirements file missing", err.getvalue())
    def test_invalid_requirements_do_not_enable_planning(self):
        config_path = pathlib.Path(tempfile.mkdtemp()) / "config.json"
        config = {"id": "demo", "planning": {"enabled": False}}
        config_path.write_text(json.dumps(config))
        requirements = config_path.parent / "requirements.md"
        requirements.write_text("""## DEMO-1 — Goal
""")
        with patch.object(pw_onboarding, "_config", return_value=(config_path, config)), \
             patch.object(pw_onboarding, "_requirements_path", return_value=requirements), \
             patch.object(pw_onboarding.subprocess, "run") as manager, \
             patch("sys.stderr", new_callable=__import__("io").StringIO) as err:
            self.assertEqual(pw_onboarding.authorize_planning("demo"), 2)
        manager.assert_not_called()
        self.assertFalse(json.loads(config_path.read_text())["planning"]["enabled"])
        self.assertIn("Requirement DEMO-1", err.getvalue())

    def test_status_shows_same_blocked_requirement_diagnostic_as_json(self):
        from types import SimpleNamespace
        issue = {"code": "missing_acceptance_command", "requirement": "DEMO-1",
                 "milestone": "DEMO-1-M1", "message": "DEMO-1-M1 Acceptance requires exactly one Command"}
        payload = {"project": "demo", "decision": "blocked", "reason": "requirements_invalid",
                   "pending": 0, "completed": 0, "queue_blocked": 0,
                   "blockers": ["requirements_invalid"], "diagnostics": [issue]}
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = pathlib.Path(tmp) / "demo"
            project_dir.mkdir()
            config = project_dir / "config.json"
            config.write_text(json.dumps({"id": "demo", "planning": {"enabled": False},
                                          "execution": {"enabled": False}}))
            with patch.object(pw_onboarding, "_project_dir", return_value=project_dir), patch.object(
                    pw_onboarding, "_recurring_state", return_value=(False, False)), patch.object(
                    pw_onboarding.subprocess, "run", return_value=SimpleNamespace(
                     stdout=json.dumps(payload), stderr="", returncode=3)):
                import io
                from contextlib import redirect_stdout
                human_out = io.StringIO()
                with redirect_stdout(human_out):
                    self.assertEqual(pw_onboarding.status("demo", False), 3)
                json_out = io.StringIO()
                with redirect_stdout(json_out):
                    self.assertEqual(pw_onboarding.status("demo", True), 3)
        self.assertIn("Planning decision: blocked", human_out.getvalue())
        self.assertIn(issue["message"], human_out.getvalue())
        self.assertIn("requirements_invalid", human_out.getvalue())
        parsed = json.loads(json_out.getvalue())
        self.assertEqual(parsed["decision"], "blocked")
        self.assertEqual(parsed["blockers"], ["requirements_invalid"])
        self.assertEqual(parsed["diagnostics"], [issue])
        self.assertIn("requirements diagnostics", parsed["next_action"])


if __name__ == "__main__":
    unittest.main()
