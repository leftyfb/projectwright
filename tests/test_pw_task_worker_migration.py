"""New canonical worker preserves the legacy public call interface."""
import importlib
import unittest

class WorkerMigrationTests(unittest.TestCase):
    def test_legacy_exports_same_functions(self):
        legacy=importlib.import_module("project_task_worker")
        canonical=importlib.import_module("pw_task_worker")
        for name in ("main","load_project","process_once","verify","run_agent","pick_task"):
            self.assertIs(getattr(legacy,name),getattr(canonical,name))

if __name__=="__main__":
    unittest.main()
