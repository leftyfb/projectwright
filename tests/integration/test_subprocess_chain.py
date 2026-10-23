"""Actual subprocess integration: dispatcher -> manager -> worker -> fake Hermes.

No running services or installed ~/.hermes files are used. Every project,
Git repository, subprocess executable, and home directory is disposable.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[2] / "src" / "projectwright"


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=True).stdout.strip()


class RealSubprocessChain(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pw-real-chain-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.scripts = self.base / "scripts"
        shutil.copytree(SRC, self.scripts)
        self.root = self.base / "projects"
        self.project = self.root / "fixture"
        self.project.mkdir(parents=True)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "fixture@example.invalid")
        git(self.repo, "config", "user.name", "Fixture")
        (self.repo / "probe.txt").write_text("unaltered\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "baseline")
        self.head = git(self.repo, "rev-parse", "HEAD")
        self.queue = self.project / "queue.md"
        self.queue.write_text("- [ ] **P101 — READ** inspect the isolated fixture\n")
        req = self.project / "requirements.md"
        req.write_text("## DEMO-1 — Disposable requirement\n\n### DEMO-1-M1 — Read fixture\n")
        self.hermes = self.base / "fake-hermes"
        self.hermes.write_text(
            "#!/usr/bin/env python3\n"
            "import json, pathlib, re, sys\n"
            "if len(sys.argv) > 1 and sys.argv[1] == 'send':\n"
            "    sys.stdin.read()\n"
            "    sys.exit(0)\n"
            "if len(sys.argv) < 2 or sys.argv[1] != 'chat':\n"
            "    sys.exit(30)\n"
            "prompt = sys.stdin.read()\n"
            "match = re.search(r'at this EXACT absolute path:\\s*\\n([^\\n]+)', prompt)\n"
            "if not match:\n"
            "    sys.exit(31)\n"
            "dest = pathlib.Path(match.group(1).strip())\n"
            "dest.write_text(json.dumps({'task_id': 'P101', 'status': 'completed',\n"
            "    'summary': 'fixture read', 'verification': 'fixture inspected', 'blocker': ''}))\n"
            "print('FAKE_HERMES_ONLY')\n"
        )
        self.hermes.chmod(0o700)
        self.config = {
            "id": "fixture", "display_name": "Disposable Fixture",
            "queue": str(self.queue),
            "work_log": str(self.project / "work_log.md"),
            "lock": str(self.project / "worker.lock"),
            "run_log": str(self.project / "run.log"),
            "result_dir": str(self.project / "results"),
            "cycle_file": str(self.project / "cycle.json"),
            "worktree": str(self.repo), "branch": "main",
            "hermes": str(self.hermes), "timeout_seconds": 20,
            "quota": {"enabled": False},
            "planning": {
                "enabled": True, "requirements_file": str(req),
                "trigger": {"pending_below": 1,
                            "review_every_completed_tasks": 6,
                            "replan_on_blocker": True},
                "queue": {"target_pending": 2, "max_new_tasks": 1,
                          "max_pending": 3},
            },
        }
        self.save_config()
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "HERMES_PROJECT_CONFIG_DIR": str(self.root),
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def save_config(self):
        (self.project / "config.json").write_text(json.dumps(self.config))

    def dispatch(self):
        return subprocess.run([sys.executable, "-B", str(self.scripts / "pw_dispatch.py"),
                               "--project", "fixture", "--scripts", str(self.scripts)],
                              env=self.env, capture_output=True, text=True, timeout=35)

    def test_real_subprocess_chain_finishes_read_and_is_idempotent(self):
        first = self.dispatch()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertIn("MANAGER decision=no_op", first.stdout)
        self.assertIn("WORKER rc=0", first.stdout)
        self.assertIn("[x] **P101", self.queue.read_text())
        journal = json.loads((self.project / "worker_journal.json").read_text())
        self.assertEqual(journal["last_completed_task"]["id"], "P101")
        self.assertIsNone(journal["current_task"])
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), self.head)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        second = self.dispatch()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertNotIn("WORKER rc=", second.stdout)
        self.assertEqual(self.queue.read_text().count("[x] **P101"), 1)

    def test_real_manager_blocker_prevents_worker_subprocess(self):
        self.config["planning"]["requirements_file"] = str(self.project / "missing.md")
        self.save_config()
        result = self.dispatch()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("WORKER rc=", result.stdout)
        self.assertFalse((self.project / "worker_journal.json").exists())
        self.assertIn("[ ] **P101", self.queue.read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
