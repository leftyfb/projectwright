"""Config-free planner dispatch requires prepared local files and Git HEAD."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]/"src"/"projectwright"

class ConfigFreePlannerRoutingTests(unittest.TestCase):
    def test_manual_planning_routes_only_when_requirements_exist(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            config=base/"config"
            project=config/"projects/demo"
            repo=project/"worktree"
            repo.mkdir(parents=True)
            (project/"queue.md").write_text("")
            (project/"work_log.md").write_text("")
            subprocess.run(["git","-C",str(repo),"init","-q","-b","main"],check=True)
            subprocess.run(["git","-C",str(repo),"-c","user.name=Test",
                            "-c","user.email=test@example.invalid",
                            "commit","-q","--allow-empty","-m","initial"],check=True)
            env={**os.environ,"PYTHONPATH":str(SOURCE),"PROJECTWRIGHT_CONFIG_DIR":str(config)}
            code=(
                "import sys,project_queue_planner\\n"
                "project_queue_planner.plan_once=lambda *a,**kw: "
                "{'project':'demo','decision':'no_op','pending':0,'manual':kw.get('manual_config_free')}\\n"
                "from project_queue_manager import main\\n"
                "sys.argv=['pw-manager','--project','demo','--once']\\n"
                "raise SystemExit(main())\\n"
            )
            before=subprocess.run([sys.executable,"-B","-c",code],
                                  env=env,capture_output=True,text=True)
            self.assertEqual(before.returncode,3,before.stderr)
            self.assertEqual(json.loads(before.stdout)["decision"],"disabled")
            (project/"requirements.md").write_text("# Requirements\\n")
            after=subprocess.run([sys.executable,"-B","-c",code],
                                 env=env,capture_output=True,text=True)
            self.assertEqual(after.returncode,3,after.stderr)
            data=json.loads(after.stdout)
            self.assertEqual(data["decision"],"no_op")
            self.assertIs(data["manual"],True)
            self.assertFalse((project/"config.json").exists())

if __name__=="__main__":
    unittest.main()
