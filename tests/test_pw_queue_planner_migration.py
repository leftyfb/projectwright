"""Canonical queue planner and legacy import expose the same API."""
import importlib
import unittest

class QueuePlannerCompatibilityTests(unittest.TestCase):
    def test_legacy_api_delegates_to_canonical(self):
        legacy=importlib.import_module("project_queue_planner")
        canonical=importlib.import_module("pw_queue_planner")
        for name in ("plan_once","run_planner","validate_proposal"):
            self.assertIs(getattr(legacy,name),getattr(canonical,name))

if __name__=="__main__":
    unittest.main()
