"""Canonical worker journal migration compatibility."""
import importlib
import sys
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "src" / "projectwright"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))


class WorkerJournalMigrationTests(unittest.TestCase):
    def test_legacy_api_points_to_canonical_functions(self):
        legacy = importlib.import_module("project_worker_journal")
        canonical = importlib.import_module("pw_worker_journal")
        for name in ("journal_path", "atomic_json", "digest", "stamp"):
            self.assertIs(getattr(legacy, name), getattr(canonical, name))

    def test_default_journal_path_uses_config_parent(self):
        canonical = importlib.import_module("pw_worker_journal")
        with tempfile.TemporaryDirectory() as td:
            config = Path(td) / "config.json"
            self.assertEqual(
                canonical.journal_path({}, config),
                Path(td) / "worker_journal.json",
            )


if __name__ == "__main__":
    unittest.main()
