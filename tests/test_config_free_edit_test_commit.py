"""Real local EDIT -> TEST -> COMMIT lifecycle with no project config.json.

Git operations and journaling are real. Only the external agent is replaced
by a deterministic fixture; no Hermes, Telegram or production files touched.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "src" / "projectwright"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

import project_task_worker as worker
import pw_worker_journal


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args],
                          check=True, capture_output=True, text=True).stdout.strip()


class ConfigFreeCycleTests(unittest.TestCase):
    def test_edit_test_commit_without_config_json(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg_home = root / "config"
            project = cfg_home / "projects/demo"
            repo = project / "worktree"
            repo.mkdir(parents=True)
            queue = project / "queue.md"
            queue.write_text(
                "- [ ] **P101 — EDIT** add fixture source\n"
                "- [ ] **P102 — TEST** add fixture test\n"
                "- [ ] **P103 — COMMIT** commit tested changes\n"
            )
            (project / "work_log.md").write_text("")
            git(repo, "init", "-q", "-b", "main")
            git(repo, "config", "user.name", "Fixture")
            git(repo, "config", "user.email", "fixture@example.invalid")
            git(repo, "commit", "-qm", "initial", "--allow-empty")
            initial = git(repo, "rev-parse", "HEAD")
            calls = []

            def fake_agent(report_path, log):
                kind = worker.CURRENT_TASK_KIND
                calls.append(kind)
                if kind == "EDIT":
                    (repo / "probe.py").write_text("VALUE = 42\n")
                elif kind == "TEST":
                    tests = repo / "scripts"
                    tests.mkdir(exist_ok=True)
                    (tests / "test_probe.py").write_text(
                        "from probe import VALUE\nassert VALUE == 42\n"
                    )
                elif kind == "COMMIT":
                    git(repo, "add", "probe.py", "scripts/test_probe.py")
                    git(repo, "commit", "-qm", "fixture task cycle")
                else:
                    raise AssertionError("unexpected task kind: " + str(kind))
                Path(report_path).write_text(json.dumps({
                    "task_id": {"EDIT":"P101","TEST":"P102","COMMIT":"P103"}[kind],
                    "status":"completed", "summary":kind+" done",
                    "verification":"fixture verified", "blocker":"",
                }))
                return 0, "fixture local agent"

            with patch.dict(os.environ, {"PROJECTWRIGHT_CONFIG_DIR":str(cfg_home)}):
                worker.load_project("demo")
                self.assertFalse((project / "config.json").exists())
                with (
                    patch.object(worker, "prompt_for",
                                 side_effect=lambda task, report: str(report)),
                    patch.object(worker, "run_agent", side_effect=fake_agent),
                ):
                    for kind in ("EDIT", "TEST", "COMMIT"):
                        rc = worker.process_once(no_telegram=True)
                        self.assertEqual(rc, 0, f"{kind}: worker rc={rc}")
                        self.assertFalse((project / "config.json").exists())

            self.assertEqual(calls, ["EDIT","TEST","COMMIT"])
            self.assertEqual(queue.read_text().count("[x]"), 3)
            self.assertNotEqual(git(repo,"rev-parse","HEAD"), initial)
            self.assertEqual(git(repo,"status","--porcelain"), "")
            self.assertFalse((project / "git_cycle.json").exists())
            self.assertIn("VALUE = 42", (repo / "probe.py").read_text())
            journal = pw_worker_journal.read(project / "worker_journal.json")
            self.assertIsNone(journal["current_task"])
            self.assertEqual(journal["last_completed_task"]["id"], "P103")


if __name__ == "__main__":
    unittest.main()
