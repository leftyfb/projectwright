"""Safe project initialization cannot authorize work or overwrite projects."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1]/"src"/"projectwright"

class SafeInitTests(unittest.TestCase):
    def invoke(self, module, home, *args):
        env = {**os.environ, "HOME": str(home), "PYTHONPATH": str(SRC)}
        env.pop("HERMES_PROJECT_CONFIG_DIR", None)
        env.pop("PROJECTWRIGHT_CONFIG_DIR", None)
        return subprocess.run([sys.executable, "-B", "-m", module, *args], env=env,
                              capture_output=True, text=True)

    def test_init_is_inert_and_preserves_existing_config(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            cfgdir=home/"cfg"
            args=("--project","demo","--config-dir",str(cfgdir))
            made=self.invoke("pw_init",home,*args)
            self.assertEqual(made.returncode,0,made.stderr)
            path=cfgdir/"projects/demo/config.json"
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            self.assertEqual(path.parent.stat().st_mode & 0o777,0o700)
            original=path.read_bytes()
            self.assertFalse(json.loads(original)["execution"]["enabled"])
            manager=self.invoke("project_queue_manager",home,*args,"--once")
            self.assertEqual(json.loads(manager.stdout)["decision"],"disabled",manager.stderr)
            worker=self.invoke("project_task_worker",home,*args,"--once")
            self.assertEqual(worker.returncode,3,worker.stderr)
            self.assertEqual(json.loads(worker.stdout)["decision"],"disabled")
            again=self.invoke("pw_init",home,*args)
            self.assertNotEqual(again.returncode,0)
            self.assertEqual(path.read_bytes(),original)
            self.assertFalse((home/".hermes").exists())

    def test_invalid_project_id_and_relative_config_home_fail(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            x=self.invoke("pw_init",home,"--project","../escape","--config-dir",str(home/"cfg"))
            self.assertNotEqual(x.returncode,0)
            y=self.invoke("pw_init",home,"--project","demo","--config-dir","relative")
            self.assertEqual(y.returncode,2)
            self.assertFalse((home/"cfg").exists())

if __name__=="__main__":
    unittest.main()
