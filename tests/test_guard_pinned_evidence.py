"""Real guard's pinned Telegram evidence must agree with disposable Git state."""
from __future__ import annotations
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "projectwright"
sys.path.insert(0, str(SRC))
import project_milestone_guard as guard

def run(*argv, cwd=None):
    return subprocess.check_output(argv, cwd=cwd, text=True).strip()

class GuardPinnedEvidence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="pw-guard-real-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / "fixture"
        self.project.mkdir()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        run("git", "init", "-q", "-b", "main", cwd=self.repo)
        run("git", "config", "user.email", "fixture@example.invalid", cwd=self.repo)
        run("git", "config", "user.name", "Fixture", cwd=self.repo)
        (self.repo / "probe.txt").write_text("fixture\n")
        run("git", "add", "probe.txt", cwd=self.repo)
        run("git", "commit", "-qm", "initial", cwd=self.repo)
        self.head = run("git", "rev-parse", "HEAD", cwd=self.repo)
        self.requirements = self.project / "requirements.md"
        self.requirements.write_text("## DEMO-1 — Fixture\n\n### DEMO-1-M1 — Demo\n")
        self.queue = self.project / "queue.md"
        self.queue.write_text("- [x] **P101 — COMMIT** DEMO-1 / DEMO-1-M1: completed commit\n")
        self.cmd = [sys.executable, "-c", "print('accepted')"]
        self.scope = ["probe.txt"]
        self.config = {
            "lock": str(self.project / "worker.lock"),
            "planning": {"requirements_file": str(self.requirements)},
            "queue": str(self.queue),
            "cycle_file": str(self.project / "cycle.json"),
            "worktree": str(self.repo),
            "branch": "main",
        }
        self.policy = {
            "version": 1,
            "milestones": {"DEMO-1-M1": {
                "requirement": "DEMO-1", "command": self.cmd, "scope_paths": self.scope
            }}
        }
        (self.project / "telegram_acceptance.json").write_text(json.dumps(self.policy))
        self.pinned = {
            "project": "fixture", "requirement": "DEMO-1",
            "milestone": "DEMO-1-M1", "head": self.head,
            "requirements_sha256": guard.sha(self.requirements.read_bytes()),
            "queue_sha256": guard.sha(self.queue.read_bytes()),
            "task_ids": ["P101"], "scope_paths": self.scope, "command": self.cmd,
        }
        (self.project / "telegram_approval_pending.json").write_text(json.dumps(self.pinned))

    def approve(self, expected):
        return guard.approve(
            self.config, self.project, "DEMO-1", "DEMO-1-M1",
            self.cmd, self.scope, expected=expected,
        )

    def test_actual_guard_rejects_stale_head_without_receipt(self):
        stale = {**self.pinned, "head": "a" * 40}
        with self.assertRaisesRegex(ValueError, "Stale|stale"):
            self.approve(stale)
        self.assertFalse((self.project / "planning_state.json").exists())

    def test_actual_guard_rejects_explicit_rejection(self):
        (self.project / "telegram_approval_rejected.json").write_text(json.dumps(self.pinned))
        with self.assertRaisesRegex(ValueError, "explicitly rejected"):
            self.approve(self.pinned)
        self.assertFalse((self.project / "planning_state.json").exists())

    def test_actual_guard_rejects_queue_mutation(self):
        self.queue.write_text(self.queue.read_text() + "\n# changed\n")
        with self.assertRaisesRegex(ValueError, "stale approval"):
            self.approve(self.pinned)
        self.assertFalse((self.project / "planning_state.json").exists())

if __name__ == "__main__":
    unittest.main()
