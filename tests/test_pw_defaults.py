"""Config-free defaults must be discoverable, inert, and side-effect free."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "src" / "projectwright"

class ConfigFreeDefaultsTests(unittest.TestCase):
    def run_defaults(self, home, *args):
        env = {**os.environ, "HOME": str(home),
               "XDG_CONFIG_HOME": str(home / "xdg")}
        env.pop("PROJECTWRIGHT_CONFIG_DIR", None)
        env.pop("HERMES_PROJECT_CONFIG_DIR", None)
        return subprocess.run([sys.executable, "-B", str(SOURCE / "pw_defaults.py"), *args],
                              env=env, text=True, capture_output=True)

    def test_missing_config_is_reported_without_file_creation(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            p=self.run_defaults(home, "--project", "demo")
            self.assertEqual(p.returncode,0,p.stderr)
            data=json.loads(p.stdout)
            self.assertFalse(data["configured"])
            self.assertEqual(data["missing_config_decision"],"disabled")
            self.assertEqual(data["project_root"],str(home/"xdg/projectwright/projects"))
            self.assertTrue(all(value is False for key,value in data["defaults"].items()
                                if key.endswith("_enabled")))
            self.assertIsNone(data["defaults"]["provider"])
            self.assertFalse((home/"xdg").exists())
            self.assertFalse((home/".hermes").exists())

    def test_absolute_config_override_and_invalid_project(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            p=self.run_defaults(home, "--project","demo", "--config-dir",str(home/"other"))
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(json.loads(p.stdout)["project_root"],str(home/"other/projects"))
            bad=self.run_defaults(home,"--project","../unsafe")
            self.assertEqual(bad.returncode,2)
            self.assertIn("Invalid project ID",bad.stderr)
            relative=self.run_defaults(home,"--config-dir","relative")
            self.assertEqual(relative.returncode,2)

if __name__=="__main__":
    unittest.main()
