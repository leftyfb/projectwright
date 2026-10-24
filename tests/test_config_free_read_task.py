"""Execute a real READ lifecycle with built-in settings and no config.json."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]/"src"/"projectwright"
if str(SOURCE) not in sys.path:
    sys.path.insert(0,str(SOURCE))

import project_task_worker as worker
import pw_worker_journal


class ConfigFreeReadLifecycleTests(unittest.TestCase):
    def test_read_task_persists_without_config_json(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)
            config_home=home/"config"
            project=config_home/"projects/demo"
            repo=project/"worktree"
            repo.mkdir(parents=True)
            queue=project/"queue.md"
            queue.write_text("- [ ] **P101 — READ** inspect prepared repository\n")
            (project/"work_log.md").write_text("")
            subprocess.run(["git","-C",str(repo),"init","-q","-b","main"],check=True)
            subprocess.run(["git","-C",str(repo),"-c","user.name=Fixture",
                            "-c","user.email=fixture@example.invalid",
                            "commit","-q","--allow-empty","-m","initial"],check=True)

            def fake_agent(prompt, log):
                report=Path(prompt)
                report.write_text(json.dumps({
                    "task_id":"P101","status":"completed",
                    "summary":"read complete","verification":"verified","blocker":""
                }))
                return 0,"fake local agent output"

            with patch.dict(os.environ,{"PROJECTWRIGHT_CONFIG_DIR":str(config_home)}):
                worker.load_project("demo")
                self.assertEqual(worker.PROJECT["display_name"],"demo")
                self.assertFalse((project/"config.json").exists())
                with (patch.object(worker,"prompt_for",side_effect=lambda task,report:str(report)),
                      patch.object(worker,"run_agent",side_effect=fake_agent),
                      patch.object(worker,"verify",return_value=(True,"verified")),
                      patch.object(worker,"cycle_begin"),
                      patch.object(worker,"cycle_approved"),
                      patch.object(worker,"cycle_read",return_value=None)):
                    rc=worker.process_once(no_telegram=True)

            self.assertEqual(rc,0)
            self.assertIn("[x]",queue.read_text())
            self.assertIn("read complete",(project/"work_log.md").read_text())
            journal=pw_worker_journal.read(project/"worker_journal.json")
            self.assertIsNone(journal["current_task"])
            self.assertEqual(journal["last_completed_task"]["id"],"P101")
            self.assertFalse((project/"config.json").exists())


if __name__=="__main__":
    unittest.main()
