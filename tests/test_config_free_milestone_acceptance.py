"""Config-free milestone completion never silently creates acceptance receipts."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[1]/"src"/"projectwright"
if str(SOURCE) not in sys.path:
    sys.path.insert(0,str(SOURCE))

from pw_acceptance_gate import awaiting_acceptance
from pw_config import load
from project_milestone_guard import current_receipts

REQUIREMENTS=("## PW-005 — Requirement\n\n"
              "### PW-005-M1 — First milestone\nImplement and test.\n")
DONE=("- [x] **P101 — EDIT** PW-005 / PW-005-M1: edit source\n"
      "- [x] **P102 — TEST** PW-005 / PW-005-M1: verify source\n"
      "- [x] **P103 — COMMIT** PW-005 / PW-005-M1: commit work\n")


def git(repo,*args):
    return subprocess.run(["git","-C",str(repo),*args],check=True,
                          capture_output=True,text=True).stdout.strip()


class ConfigFreeMilestoneAcceptanceTests(unittest.TestCase):
    def test_completed_milestone_still_awaits_human_acceptance(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            project=root/"projects/demo"
            repo=project/"worktree"
            repo.mkdir(parents=True)
            (project/"queue.md").write_text(DONE)
            (project/"work_log.md").write_text("Completed fixture tasks.\n")
            (project/"requirements.md").write_text(REQUIREMENTS)
            git(repo,"init","-q","-b","main")
            git(repo,"config","user.name","Fixture")
            git(repo,"config","user.email","fixture@example.invalid")
            (repo/"source.py").write_text("VALUE=42\n")
            git(repo,"add","source.py")
            git(repo,"commit","-qm","milestone")
            head=git(repo,"rev-parse","HEAD")
            path,cfg=load("demo",root/"projects")
            self.assertFalse(path.exists())
            self.assertFalse(cfg["planning"]["enabled"])
            self.assertFalse(cfg["execution"]["enabled"])
            self.assertEqual(cfg["planning"]["requirements_file"],str(project/"requirements.md"))
            receipts=current_receipts({},REQUIREMENTS.encode(),DONE,head,repo=repo,
                                      strict=False,policy={},journal={})
            self.assertEqual(receipts,{})
            self.assertEqual(awaiting_acceptance(DONE,REQUIREMENTS,receipts),["PW-005-M1"])
            self.assertEqual(awaiting_acceptance(DONE.replace("P103 — COMMIT","P103 — TEST"),
                                                REQUIREMENTS,receipts),[])
            self.assertEqual(awaiting_acceptance(DONE.replace("P103 — COMMIT","P103 — COMMIT").replace("[x] **P103","[ ] **P103"),
                                                REQUIREMENTS,receipts),[])
            self.assertFalse((project/"planning_state.json").exists())
            self.assertFalse((project/"config.json").exists())
            self.assertFalse((project/"telegram_approval_pending.json").exists())

    def test_receipt_map_cannot_be_inferred_from_checked_queue(self):
        self.assertEqual(awaiting_acceptance(DONE,REQUIREMENTS,{}),["PW-005-M1"])
        self.assertEqual(awaiting_acceptance(DONE,REQUIREMENTS,{"PW-005-M1":{"receipt":"verified"}}),[])
        with self.assertRaises(ValueError):
            awaiting_acceptance(DONE,REQUIREMENTS,None)


if __name__=="__main__":
    unittest.main()
