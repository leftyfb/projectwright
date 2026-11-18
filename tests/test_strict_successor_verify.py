"""Regression for strict successor COMMIT -> VERIFY -> approval sequencing (#39)."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1] / "src" / "projectwright"
sys.path.insert(0, str(SRC))
import pw_milestone_guard as guard
import pw_milestone_sequence as sequence
import pw_worker_journal as journal


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


class StrictSuccessorVerify(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="pw-issue39-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.name", "Fixture")
        git(self.repo, "config", "user.email", "fixture@example.invalid")
        (self.repo / "README.md").write_text("original docs\\n")
        (self.repo / "tests").mkdir()
        (self.repo / "tests/test_original.py").write_text("def test_original(): assert True\\n")
        git(self.repo, "add", "README.md", "tests/test_original.py")
        git(self.repo, "commit", "-qm", "approved baseline")
        self.before = git(self.repo, "rev-parse", "HEAD")

        self.requirements = (
            "## AX-001 — Local workflow\\n"
            "### AX-001-M1 — First milestone\\n"
            "#### Acceptance\\n"
            "- **Command:** `/bin/true`\\n"
            "- **Scope:** `README.md`\\n"
            "- **Scope:** `tests/test_original.py`\\n"
            "## AX-002 — Admin UI\\n"
            "### AX-002-M1 — Admin UI contract\\n"
            "#### Acceptance\\n"
            "- **Command:** `/bin/true`\\n"
            "- **Scope:** `README.md`\\n"
            "- **Scope:** `src/theaxiom/admin_api.py`\\n"
            "- **Scope:** `tests/test_admin_api.py`\\n"
        ).replace("\\n", "\n")
        self.policy = guard.embedded_acceptance_policy(self.requirements)
        self.queue = (
            "- [x] **P101 — READ** AX-001 / AX-001-M1: inspect\\n"
            "- [x] **P102 — COMMIT** AX-001 / AX-001-M1: commit README.md\\n"
            "- [x] **P106 — READ** AX-002 / AX-002-M1: inspect\\n"
            "- [x] **P107 — EDIT** AX-002 / AX-002-M1: implement\\n"
            "- [x] **P108 — TEST** AX-002 / AX-002-M1: test\\n"
            "- [x] **P109 — COMMIT** AX-002 / AX-002-M1: commit only README.md, src/theaxiom/admin_api.py, and tests/test_admin_api.py\\n"
            "- [ ] **P110 — VERIFY** AX-002 / AX-002-M1: verify\\n"
        ).replace("\\n", "\n")
        spec = self.policy["milestones"]["AX-001-M1"]
        self.state = {"verified_milestones": {"AX-001-M1": {
            "milestone_id": "AX-001-M1", "requirement_id": "AX-001",
            "git_head": self.before, "scope_version": 1,
            "milestone_requirements_sha256": guard.milestone_fingerprint(
                self.requirements.encode(), "AX-001-M1"),
            "acceptance_policy_sha256": guard.acceptance_policy_fingerprint(spec),
            "acceptance_command": spec["command"], "scope_paths": spec["scope_paths"],
            "completed_task_ids": ["P101", "P102"], "acceptance_exit_code": 0,
        }}}
        (self.repo / "README.md").write_text("admin route documented\\n")
        (self.repo / "src/theaxiom").mkdir(parents=True)
        (self.repo / "src/theaxiom/admin_api.py").write_text("ROUTE = '/admin'\\n")
        (self.repo / "tests/test_admin_api.py").write_text("def test_admin(): assert True\\n")
        git(self.repo, "add", "README.md", "src/theaxiom/admin_api.py", "tests/test_admin_api.py")
        git(self.repo, "commit", "-qm", "Add standalone admin UI route")
        self.after = git(self.repo, "rev-parse", "HEAD")
        self.commit = {"id": "P109", "kind": "COMMIT",
                       "git_head_before": self.before, "git_head_after": self.after}
        self.journal = {"current_task": None, "last_completed_task": self.commit}

    def receipts(self):
        return guard.current_receipts(
            self.state, self.requirements.encode(), self.queue, self.after,
            repo=self.repo, strict=True, policy=self.policy, journal=self.journal)

    def test_pending_verify_is_runnable_after_journal_verified_commit(self):
        receipts = self.receipts()
        self.assertIn("AX-001-M1", receipts)
        decision = sequence.evaluate(self.requirements, self.queue, receipts, self.policy)
        self.assertEqual(decision["decision"], "active")
        self.assertEqual(decision["milestone"], "AX-002-M1")

    def test_prior_receipt_survives_verify_completion_and_allows_acceptance(self):
        path = self.root / "worker_journal.json"
        self.journal = {
            "schema_version": 1,
            "last_completed_task": self.commit,
            "current_task": {
                "id": "P110", "kind": "VERIFY", "phase": "verified",
                "git_head_before": self.after, "git_head_after": self.after,
            },
        }
        path.write_text(json.dumps(self.journal))
        journal.finalize(path, "P110")
        self.journal = json.loads(path.read_text())
        self.assertEqual(self.journal["last_verified_commit"], self.commit)
        self.assertEqual(self.journal["last_completed_task"]["kind"], "VERIFY")
        self.queue = self.queue.replace("P110 — VERIFY** AX-002", "P110 — VERIFY** AX-002").replace(
            "- [ ] **P110", "- [x] **P110")
        receipts = self.receipts()
        self.assertIn("AX-001-M1", receipts)
        self.assertEqual(sequence.evaluate(self.requirements, self.queue, receipts, self.policy)["decision"],
                         "awaiting_acceptance")

    def test_missing_or_untrusted_commit_cannot_authorize_successor(self):
        self.journal = {"current_task": None, "last_completed_task": {"kind": "VERIFY"}}
        self.assertNotIn("AX-001-M1", self.receipts())
        self.journal["last_verified_commit"] = {**self.commit, "git_head_before": "0" * 40}
        self.assertNotIn("AX-001-M1", self.receipts())
        self.journal["last_verified_commit"] = {**self.commit, "id": "P108"}
        self.assertNotIn("AX-001-M1", self.receipts())

    def test_pending_edit_or_test_does_not_authorize_successor(self):
        self.queue += "- [ ] **P111 — EDIT** AX-002 / AX-002-M1: extra edit\\n"
        self.assertNotIn("AX-001-M1", self.receipts())
        self.queue = self.queue.replace("P111 — EDIT", "P111 — TEST")
        self.assertNotIn("AX-001-M1", self.receipts())
        self.queue = self.queue.replace("P111 — TEST", "P111 — VERIFY")
        self.assertIn("AX-001-M1", self.receipts())

    def test_commit_outside_scope_is_refused(self):
        self.policy["milestones"]["AX-002-M1"]["scope_paths"] = ["README.md"]
        self.assertNotIn("AX-001-M1", self.receipts())


if __name__ == "__main__":
    unittest.main()
