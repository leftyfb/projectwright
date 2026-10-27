"""Canonical queue manager and legacy module remain API compatible."""
import importlib
import unittest

class QueueManagerMigrationTests(unittest.TestCase):
    def test_legacy_exports_same_functions(self):
        legacy=importlib.import_module("project_queue_manager")
        canonical=importlib.import_module("pw_queue_manager")
        for name in ("main","project_config","planning_policy","provider_argv","inspect","once_exit_code"):
            self.assertIs(getattr(legacy,name),getattr(canonical,name))

if __name__=="__main__":
    unittest.main()
