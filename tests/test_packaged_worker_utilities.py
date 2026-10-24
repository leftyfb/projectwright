"""Prevent packaged worker utilities from regressing to ~/.hermes/scripts."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "projectwright"
WORKER = SOURCE / "project_task_worker.py"


class PackagedWorkerUtilities(unittest.TestCase):
    def test_worker_uses_bundled_utility_scripts(self):
        content = WORKER.read_text(encoding="utf-8")
        for module in ("project_queue_manager", "pw_recovery", "project_notes_sync"):
            self.assertIn(f"Path(__file__).resolve().parent / '{module}.py'", content)
            self.assertTrue((SOURCE / f"{module}.py").is_file())
        self.assertNotIn("HERMES_HOME / 'scripts/project_queue_manager.py'", content)
        self.assertNotIn("HERMES_HOME / 'scripts/project_recovery.py'", content)
        self.assertNotIn('HERMES_HOME / "scripts/project_notes_sync.py"', content)


if __name__ == "__main__":
    unittest.main()
