"""A prepared Git worktree can be used without project config.json."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SRC=Path(__file__).resolve().parents[1]/"src"/"projectwright"

class ConfigFreePreparedWorkerTests(unittest.TestCase):
    def test_explicit_prepared_repo_is_eligible_without_json(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            cfg_home=home/"config"
            project=cfg_home/"projects/demo"
            repo=project/"worktree"
            repo.mkdir(parents=True)
            (project/"queue.md").write_text("")
            (project/"work_log.md").write_text("")
            subprocess.run(["git","-C",str(repo),"init","-q","-b","main"],check=True)
            subprocess.run(["git","-C",str(repo),"-c","user.name=Test",
                            "-c","user.email=test@example.invalid",
                            "commit","-q","--allow-empty","-m","initial"],check=True)
            env={**os.environ,"PYTHONPATH":str(SRC),
                 "PROJECTWRIGHT_CONFIG_DIR":str(cfg_home)}
            command=(
                "import json; from pw_config import load,ready_for_config_free_worker; "
                "path,cfg=load('demo'); "
                "print(json.dumps({'exists':path.exists(),"
                "'ready':ready_for_config_free_worker(cfg)}))"
            )
            result=subprocess.run([sys.executable,"-B","-c",command],
                                  env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            data=json.loads(result.stdout)
            self.assertEqual(data,{"exists":False,"ready":True})
            smoke=subprocess.run([sys.executable,"-B","-m","project_task_worker",
                 "--project","demo","--dry-run"],env=env,capture_output=True,text=True)
            self.assertEqual(smoke.returncode,0,smoke.stderr)
            self.assertFalse((project/"config.json").exists())
            (project/"queue.md").unlink()
            denied=subprocess.run([sys.executable,"-B","-m","project_task_worker",
                 "--project","demo","--once"],env=env,capture_output=True,text=True)
            self.assertEqual(denied.returncode,3,denied.stderr)
            self.assertEqual(json.loads(denied.stdout)["decision"],"disabled")
            self.assertFalse((project/"config.json").exists())

    def test_non_repository_is_never_eligible(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            project=root/"projects/demo"
            (project/"worktree").mkdir(parents=True)
            (project/"queue.md").write_text("")
            (project/"work_log.md").write_text("")
            env={**os.environ,"PYTHONPATH":str(SRC),"PROJECTWRIGHT_CONFIG_DIR":str(root)}
            result=subprocess.run([sys.executable,"-B","-m","project_task_worker",
                 "--project","demo","--once"],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,3,result.stderr)
            self.assertEqual(json.loads(result.stdout)["decision"],"disabled")

if __name__=="__main__":
    unittest.main()
