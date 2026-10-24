"""Canonical quota module and backward-compatible import contract."""
import importlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "projectwright"))


class QuotaModuleMigrationTests(unittest.TestCase):
    def test_legacy_module_exports_canonical_api(self):
        canonical = importlib.import_module("pw_quota")
        legacy = importlib.import_module("project_quota")
        self.assertIs(legacy.evaluate, canonical.evaluate)
        self.assertIs(legacy.QuotaError, canonical.QuotaError)
        self.assertEqual(legacy.RATE_LIMITED_ENTITY_ENV,
                         canonical.RATE_LIMITED_ENTITY_ENV)

    def test_explicit_disable_remains_safe_without_credentials(self):
        canonical = importlib.import_module("pw_quota")
        self.assertEqual(canonical.evaluate({"enabled": False}), {
            "enabled": False, "allowed": True, "reason": "disabled",
            "remaining_percent": None
        })


if __name__ == "__main__":
    unittest.main()
