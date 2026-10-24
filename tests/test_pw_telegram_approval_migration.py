"""Canonical Telegram approvals preserve legacy helper identity and CLI."""
import importlib
import unittest

class ApprovalModuleMigrationTests(unittest.TestCase):
    def test_public_and_private_functions_are_compatible(self):
        legacy=importlib.import_module("project_telegram_approval")
        canonical=importlib.import_module("pw_telegram_approval")
        for name in ("scan","approve_single","load_pending","evidence","main"):
            self.assertIs(getattr(legacy,name),getattr(canonical,name))
        self.assertEqual(legacy.__name__,"project_telegram_approval")

if __name__=="__main__":
    unittest.main()
