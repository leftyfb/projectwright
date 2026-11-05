"""TEST workers must honor milestone acceptance paths, not just generic patterns."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pw_task_worker as worker


REQUIREMENTS = """# Demo

## TRACK-1 — Local task tracker

### TRACK-1-M1 — Core behavior
Implement task tracker.

#### Acceptance
- **Command:** `python3 -B -m unittest discover -s tests -p test_task_tracker_m1.py`
- **Scope:** `task_tracker.py`
- **Scope:** `tests/test_task_tracker_m1.py`
"""


class TestTaskAcceptancePaths(unittest.TestCase):
    def test_explicit_test_path_overrides_default_directory_choice(self):
        with tempfile.TemporaryDirectory() as temp:
            req = Path(temp) / "requirements.md"
            req.write_text(REQUIREMENTS, encoding="utf-8")
            task = worker.Task(
                "P103", "TEST",
                "TRACK-1 / TRACK-1-M1: Add isolated coverage in tests/test_task_tracker_m1.py",
                3, "",
            )
            with patch.object(worker, "PROJECT", {
                "planning": {"requirements_file": str(req)}
            }):
                self.assertEqual(worker.milestone_test_scope(task), ["tests/test_task_tracker_m1.py"])
                self.assertTrue(worker.allowed_test_file("tests/test_task_tracker_m1.py", task))
                self.assertFalse(worker.allowed_test_file("scripts/test_task_tracker_m1.py", task))
                self.assertFalse(worker.allowed_test_file("tests/test_other.py", task))
                self.assertFalse(worker.allowed_test_file("task_tracker.py", task))

    def test_without_acceptance_policy_keep_legacy_script_patterns(self):
        with patch.object(worker, "PROJECT", {}):
            self.assertTrue(worker.allowed_test_file("scripts/test_example.py"))
            self.assertTrue(worker.allowed_test_file("tests/test_example.py"))
            self.assertFalse(worker.allowed_test_file("task_tracker.py"))


if __name__ == "__main__":
    unittest.main()
