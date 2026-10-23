"""Recovered strict milestone-sequencing contracts against source modules."""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src" / "projectwright"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

import project_milestone_sequence


REQ = "## PW-005 — Requirement\n### PW-005-M1 — First milestone\n### PW-005-M2 — Second milestone\n"
POLICY = {
    "version": 1,
    "milestones": {
        key: {"requirement": "PW-005", "command": ["true"], "scope_paths": ["requirements.md"]}
        for key in ("PW-005-M1", "PW-005-M2")
    },
}


class MilestoneSequenceTests(unittest.TestCase):
    def test_duplicate_milestone_headings_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "Duplicate milestone"):
            project_milestone_sequence.order("## PW-005 — Requirement\n### PW-005-M1 — A\n### PW-005-M1 — Duplicate\n")

    def test_current_incomplete_milestone_is_active(self):
        queue = "- [ ] **P101 — EDIT** PW-005 / PW-005-M1: implement\n"
        result = project_milestone_sequence.evaluate(REQ, queue, {}, POLICY)
        self.assertEqual(result["decision"], "active")
        self.assertEqual(result["milestone"], "PW-005-M1")

    def test_completed_commit_milestone_awaits_acceptance(self):
        queue = "- [x] **P101 — COMMIT** PW-005 / PW-005-M1: finish\n"
        result = project_milestone_sequence.evaluate(REQ, queue, {}, POLICY)
        self.assertEqual(result["decision"], "awaiting_acceptance")
        self.assertEqual(result["milestone"], "PW-005-M1")

    def test_future_milestone_work_blocks_before_current_receipt(self):
        queue = "- [ ] **P201 — EDIT** PW-005 / PW-005-M2: premature\n"
        result = project_milestone_sequence.evaluate(REQ, queue, {}, POLICY)
        self.assertEqual(result["decision"], "blocked")
        self.assertIn("Future milestone PW-005-M2", result["reason"])

    def test_missing_policy_blocks(self):
        result = project_milestone_sequence.evaluate(REQ, "", {}, None)
        self.assertEqual(result["decision"], "blocked")
        self.assertIn("policy", result["reason"])


if __name__ == "__main__":
    unittest.main()
