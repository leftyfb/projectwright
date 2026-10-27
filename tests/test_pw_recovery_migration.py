"""Recovery module migration contract for existing callers."""
import importlib
from pathlib import Path
import sys
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "src" / "projectwright"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))


class RecoveryModuleCompatibility(unittest.TestCase):
    def test_public_functions_are_identical(self):
        canonical = importlib.import_module("pw_recovery")
        legacy = importlib.import_module("project_recovery")
        for name in ("main", "project_config", "evidence", "record_incident", "digest"):
            self.assertIs(getattr(legacy, name), getattr(canonical, name))

    def test_project_id_validation_fails_closed(self):
        module = importlib.import_module("pw_recovery")
        with self.assertRaisesRegex(ValueError, "Invalid project ID"):
            module.project_config("../other", Path("/nonexistent"))


if __name__ == "__main__":
    unittest.main()
