"""Manager and worker use the same safe defaults when config.json is absent."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"src"/"projectwright"

class SharedConfigPolicyTests(unittest.TestCase):
    def test_config_free_dispatchers_remain_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            env={**os.environ,"HOME":td,"PYTHONPATH":str(SRC),
                 "PROJECTWRIGHT_CONFIG_DIR":str(home/"config")}
            env.pop("HERMES_PROJECT_CONFIG_DIR",None)
            manager=subprocess.run([sys.executable,"-B","-m","project_queue_manager",
                 "--project","demo","--status"],env=env,capture_output=True,text=True)
            self.assertEqual(manager.returncode,0,manager.stderr)
            self.assertEqual(json.loads(manager.stdout)["decision"],"disabled")
            worker=subprocess.run([sys.executable,"-B","-m","project_task_worker",
                 "--project","demo","--once"],env=env,capture_output=True,text=True)
            self.assertEqual(worker.returncode,3,worker.stderr)
            self.assertEqual(json.loads(worker.stdout)["decision"],"disabled")
            self.assertFalse((home/"config").exists())
            self.assertFalse((home/".hermes").exists())

    def test_bad_json_is_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            directory=home/"config/projects/demo"
            directory.mkdir(parents=True)
            (directory/"config.json").write_text('{"execution":{"enabled":"yes"}}')
            env={**os.environ,"PYTHONPATH":str(SRC),
                 "PROJECTWRIGHT_CONFIG_DIR":str(home/"config")}
            manager=subprocess.run([sys.executable,"-B","-m","project_queue_manager",
                "--project","demo","--status"],env=env,capture_output=True,text=True)
            self.assertEqual(manager.returncode,1)
            self.assertIn("execution.enabled must be boolean",manager.stderr)
            worker=subprocess.run([sys.executable,"-B","-m","project_task_worker",
                "--project","demo","--once"],env=env,capture_output=True,text=True)
            self.assertNotEqual(worker.returncode,0)
            self.assertIn("execution.enabled must be boolean",worker.stderr)

if __name__=="__main__":
    unittest.main()
