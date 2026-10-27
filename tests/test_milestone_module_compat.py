"""Canonical milestone sequencing and legacy compatibility contract."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "projectwright"))
import pw_milestone_sequence as canonical
import project_milestone_sequence as legacy


class MilestoneNamingTests(unittest.TestCase):
    def test_legacy_exports_alias_canonical(self):
        self.assertIs(legacy.order, canonical.order)
        self.assertIs(legacy.evaluate, canonical.evaluate)

    def test_sequence_semantics_are_unchanged(self):
        requirements = "### DEMO-1-M1 — First\n### DEMO-1-M2 — Second\n"
        self.assertEqual(legacy.order(requirements), canonical.order(requirements))
        self.assertEqual(canonical.order(requirements), ["DEMO-1-M1", "DEMO-1-M2"])


if __name__ == "__main__":
    unittest.main()
