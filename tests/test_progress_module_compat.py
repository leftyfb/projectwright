"""Canonical worker progress module and legacy import compatibility."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "projectwright"))
import pw_worker_progress as canonical
import project_worker_progress as legacy


class ProgressNamingTests(unittest.TestCase):
    def test_legacy_exports_alias_canonical(self):
        self.assertIs(legacy.record_completed, canonical.record_completed)
        self.assertIs(legacy.read_state, canonical.read_state)
        self.assertIs(legacy.state_path, canonical.state_path)

    def test_progress_state_stays_compatible(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "state.json"
            self.assertTrue(canonical.record_completed(path, "P101"))
            self.assertFalse(legacy.record_completed(path, "P101"))
            self.assertEqual(legacy.read_state(path)["completed_tasks_total"], 1)


if __name__ == "__main__":
    unittest.main()
