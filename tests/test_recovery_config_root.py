"""Recovery CLI config root resolution, without touching actual projects."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "src/projectwright/project_recovery.py"

class RecoveryConfigRootTests(unittest.TestCase):
    def test_xdg_default_looks_in_projectwright_projects(self):
        with tempfile.TemporaryDirectory() as td:
            env = {**os.environ, "HOME": td, "XDG_CONFIG_HOME": str(Path(td)/"xdg")}
            env.pop("PROJECTWRIGHT_CONFIG_DIR", None)
            env.pop("HERMES_PROJECT_CONFIG_DIR", None)
            result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--project", "fixture"],
                                    env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(str(Path(td)/"xdg/projects/fixture/config.json"), result.stderr)

    def test_custom_config_dir(self):
        with tempfile.TemporaryDirectory() as td:
            result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--project", "fixture",
                                    "--config-dir", td], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(str(Path(td)/"projects/fixture/config.json"), result.stderr)

    def test_conflicting_root_options_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--project", "fixture",
                                    "--config-dir", td, "--config-root", td],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("mutually exclusive", result.stderr)

if __name__ == "__main__":
    unittest.main()
