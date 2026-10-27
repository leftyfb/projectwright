"""The packaged worker must not require legacy ~/.hermes/scripts for replanning."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "src/projectwright/pw_task_worker.py"
MANAGER = ROOT / "src/projectwright/pw_queue_manager.py"

class PackagedManagerHandoffTests(unittest.TestCase):
    def test_worker_calls_bundled_manager_not_hermes_script(self):
        source = WORKER.read_text(encoding="utf-8")
        self.assertIn("manager = Path(__file__).resolve().parent / 'pw_queue_manager.py'", source)
        self.assertNotIn("HERMES_HOME / 'scripts/project_queue_manager.py'", source)
        self.assertTrue(MANAGER.is_file())

if __name__ == "__main__":
    unittest.main()
