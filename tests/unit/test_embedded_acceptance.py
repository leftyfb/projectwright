import json
import pathlib
import sys
import tempfile
import unittest
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src" / "projectwright"
sys.path.insert(0, str(SOURCE))

import pw_milestone_guard as guard
import pw_telegram_approval as approval
from pw_milestone_guard import embedded_acceptance_policy, policy_for_project


VALID = """## PW-005 — Requirement
### PW-005-M1 — First milestone
#### Acceptance
- **Command:** `python -m pytest tests/test_one.py -q`
- **Scope:** `src/projectwright/one.py`
- **Scope:** `tests/test_one.py`
"""


class EmbeddedAcceptanceTests(unittest.TestCase):
    def test_parses_literal_argv_and_scopes(self):
        policy = embedded_acceptance_policy(VALID)
        self.assertEqual(policy["version"], 1)
        self.assertEqual(policy["milestones"]["PW-005-M1"]["command"],
                         ["python", "-m", "pytest", "tests/test_one.py", "-q"])
        self.assertEqual(len(policy["milestones"]["PW-005-M1"]["scope_paths"]), 2)

    def test_rejects_missing_criteria_and_shell_syntax(self):
        with self.assertRaisesRegex(ValueError, "Missing Acceptance"):
            embedded_acceptance_policy(VALID + "\n### PW-005-M2 — Second\n")
        with self.assertRaisesRegex(ValueError, "literal executable"):
            embedded_acceptance_policy(VALID.replace("pytest tests/test_one.py -q", "pytest tests/test_one.py && rm -rf ."))

    def test_rejects_duplicate_milestone_headings(self):
        with self.assertRaisesRegex(ValueError, "Duplicate milestone"):
            embedded_acceptance_policy(VALID + "### PW-005-M1 — Duplicate\n")

    def test_acceptance_entries_stop_at_next_same_or_higher_heading(self):
        requirements = VALID + "#### Notes\nThis is not an acceptance entry.\n"
        policy = embedded_acceptance_policy(requirements)
        self.assertEqual(policy["milestones"]["PW-005-M1"]["scope_paths"],
                         ["src/projectwright/one.py", "tests/test_one.py"])

    def test_rejects_non_exact_acceptance_entries_and_magic_paths(self):
        with self.assertRaisesRegex(ValueError, "Invalid Acceptance entry"):
            embedded_acceptance_policy(VALID.replace("#### Acceptance", "#### Acceptance\n- Scope: `bad.py`"))
        with self.assertRaises(ValueError):
            embedded_acceptance_policy(VALID.replace("src/projectwright/one.py", ":(glob)src/**/*.py"))
        self.assertFalse(guard._valid_scope_path(":(glob)src/**/*.py"))

    def test_legacy_json_is_used_only_without_embedded_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            req = root / "requirements.md"
            req.write_text("## PW-005\n### PW-005-M1 — First\n")
            (root / "config.json").write_text(json.dumps({"planning": {"requirements_file": str(req)}}))
            legacy = {"version": 1, "milestones": {"PW-005-M1": {
                "requirement": "PW-005", "command": ["true"], "scope_paths": ["requirements.md"]}}}
            (root / "telegram_acceptance.json").write_text(json.dumps(legacy))
            self.assertEqual(policy_for_project(root), legacy)

    def test_duplicate_sources_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            req = root / "requirements.md"
            req.write_text(VALID)
            (root / "config.json").write_text(json.dumps({"planning": {"requirements_file": str(req)}}))
            (root / "telegram_acceptance.json").write_text(json.dumps({"version": 1, "milestones": {}}))
            with self.assertRaisesRegex(ValueError, "Duplicate acceptance policy sources"):
                policy_for_project(root)

    def test_configured_requirements_source_does_not_fall_back_to_project_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            configured = root / "configured.md"
            configured.write_text("## PW-005\n### PW-005-M1 — First\n")
            (root / "requirements.md").write_text(VALID)
            (root / "config.json").write_text(json.dumps({
                "planning": {"requirements_file": str(configured)}
            }))
            self.assertIsNone(policy_for_project(root))


class EmbeddedAcceptanceE2ETests(unittest.TestCase):
    def test_embedded_strict_scan_approve_and_current_receipts(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            project = root / "demo"
            repo = project / "repo"
            project.mkdir()
            repo.mkdir()
            def run(*args):
                return subprocess.check_output(args, cwd=repo, text=True).strip()
            run("git", "init", "-q", "-b", "main")
            run("git", "config", "user.email", "fixture@example.invalid")
            run("git", "config", "user.name", "Fixture")
            (repo / "probe.txt").write_text("fixture\n")
            run("git", "add", "probe.txt")
            run("git", "commit", "-qm", "initial")
            requirements = project / "requirements.md"
            requirements.write_text(
                "## DEMO-1 — Fixture\n"
                "### DEMO-1-M1 — Demo\n"
                "#### Acceptance\n"
                "- **Command:** `python -c \\\"print('accepted')\\\"`\n"
                "- **Scope:** `probe.txt`\n"
            )
            queue = project / "queue.md"
            queue.write_text("- [x] **P101 — COMMIT** DEMO-1 / DEMO-1-M1: completed\n")
            config = {
                "id": "demo", "lock": str(project / "worker.lock"),
                "planning": {"enabled": True, "milestone_sequence": "strict",
                             "requirements_file": str(requirements)},
                "queue": str(queue), "cycle_file": str(project / "cycle.json"),
                "worktree": str(repo), "branch": "main",
            }
            (project / "config.json").write_text(json.dumps(config))
            found = approval.scan(root)
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0]["milestone"], "DEMO-1-M1")
            approval.approve_single(root)
            state = json.loads((project / "planning_state.json").read_text())
            head = run("git", "rev-parse", "HEAD")
            receipts = guard.current_receipts(
                state, requirements.read_bytes(), queue.read_text(), head,
                repo=repo, strict=True, policy=policy_for_project(project), journal={})
            self.assertIn("DEMO-1-M1", receipts)


if __name__ == "__main__":
    unittest.main()
