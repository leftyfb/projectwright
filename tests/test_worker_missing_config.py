"""A missing project config cannot authorize worker execution."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

WORKER=Path(__file__).resolve().parents[1]/"src/projectwright/project_task_worker.py"

class ConfigFreeWorkerTests(unittest.TestCase):
    def test_missing_config_is_disabled_without_creating_project_state(self):
        with tempfile.TemporaryDirectory() as td:
            config_home=Path(td)/"config"
            env={**os.environ,"HOME":td,"PROJECTWRIGHT_CONFIG_DIR":str(config_home)}
            env.pop("HERMES_PROJECT_CONFIG_DIR",None)
            result=subprocess.run([sys.executable,"-B",str(WORKER),"--project","demo","--once","--no-telegram"],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,3,result.stderr)
            self.assertEqual(json.loads(result.stdout),{"project":"demo","decision":"disabled","reason":"project config missing"})
            self.assertFalse(config_home.exists())
            self.assertFalse((Path(td)/".hermes").exists())

    def test_traversal_is_rejected_without_reading_configs(self):
        with tempfile.TemporaryDirectory() as td:
            env={**os.environ,"HOME":td,"PROJECTWRIGHT_CONFIG_DIR":str(Path(td)/"config")}
            result=subprocess.run([sys.executable,"-B",str(WORKER),"--project","../other","--once"],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertIn("Invalid project ID",result.stderr)

if __name__=="__main__":
    unittest.main()
