"""Canonical milestone acceptance gate and legacy API compatibility."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "projectwright"))
import pw_acceptance_gate as canonical
import project_acceptance_gate as legacy

class AcceptanceGateNamingTests(unittest.TestCase):
    def test_legacy_api_aliases_canonical(self):
        self.assertIs(legacy.awaiting_acceptance, canonical.awaiting_acceptance)

    def test_invalid_receipts_still_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "Invalid verified milestone"):
            legacy.awaiting_acceptance("", "", None)
        with self.assertRaisesRegex(ValueError, "Invalid verified milestone"):
            canonical.awaiting_acceptance("", "", None)

if __name__ == "__main__":
    unittest.main()
