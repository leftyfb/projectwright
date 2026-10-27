"""Legacy milestone guard preserves private helpers used by approval bridge."""
import importlib
import unittest


class MilestoneGuardCompatibilityTests(unittest.TestCase):
    def test_private_scope_validator_is_forwarded(self):
        legacy=importlib.import_module("project_milestone_guard")
        canonical=importlib.import_module("pw_milestone_guard")
        self.assertIs(legacy._valid_scope_path,canonical._valid_scope_path)
        self.assertTrue(legacy._valid_scope_path("src/example.py"))
        self.assertFalse(legacy._valid_scope_path("../escape"))
        self.assertIs(legacy.current_receipts,canonical.current_receipts)


if __name__=="__main__":
    unittest.main()
