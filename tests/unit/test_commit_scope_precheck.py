"""Regression for partial scoped commits that strand the Git-cycle journal."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[2] / "src" / "projectwright"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pw_task_worker as worker


class CommitScopePrecheckTests(unittest.TestCase):
    def setUp(self):
        self.task = worker.Task(
            "P108", "COMMIT",
            "TRACK-1 / TRACK-1-M2: After M2 tests pass, commit only "
            "task_tracker.py, tests/test_task_tracker_m2.py, and README.md.",
            1, "original queue row",
        )

    def test_explicit_scope_handles_file_extensions(self):
        self.assertEqual(worker.explicit_commit_paths(self.task.description), {
            "task_tracker.py", "tests/test_task_tracker_m2.py", "README.md",
        })

    def test_legacy_commit_without_literal_scope_uses_cycle_allowlist(self):
        self.assertIsNone(worker.explicit_commit_paths("Commit the validated changes"))

    def test_dirty_file_outside_declared_scope_is_blocked_before_agent(self):
        dirty = {
            "task_tracker.py", "tests/test_task_tracker_m2.py",
            "README.md", "tests/test_task_tracker_m1.py",
        }
        with (
            patch.object(worker, "cycle_read", return_value={
                "phase": "active", "allowed": sorted(dirty),
            }),
            patch.object(worker, "repo_state", return_value=(None, None, sorted(dirty))),
        ):
            with self.assertRaisesRegex(RuntimeError, "COMMIT scope mismatch"):
                worker.cycle_commit_precheck(self.task)

    def test_matching_scope_permits_commit(self):
        dirty = {"task_tracker.py", "README.md"}
        with (
            patch.object(worker, "cycle_read", return_value={
                "phase": "active", "allowed": sorted(dirty),
            }),
            patch.object(worker, "repo_state", return_value=(None, None, sorted(dirty))),
        ):
            worker.cycle_commit_precheck(self.task)

    def test_unapproved_path_is_rejected_even_without_literal_scope(self):
        with (
            patch.object(worker, "cycle_read", return_value={
                "phase": "active", "allowed": ["README.md"],
            }),
            patch.object(worker, "repo_state", return_value=(None, None, ["unknown.py"])),
        ):
            with self.assertRaisesRegex(RuntimeError, "Unapproved dirty"):
                worker.cycle_commit_precheck(self.task)


if __name__ == "__main__":
    unittest.main()
