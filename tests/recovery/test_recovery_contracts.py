#!/usr/bin/env python3
"""Isolated recovery, journal, incident, and timer contracts."""

import fcntl
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "projectwright"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SRC))

import project_recovery as recovery
import project_worker_journal as journal
import pw_project_timer as timer


TASK_RE = recovery.TASK_RE


def run_git(*args, cwd=None):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


class RecoveryContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="projectwright-recovery-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "projects" / "pw-recovery-fixture"
        self.project.mkdir(parents=True)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        run_git("init", "-q", "-b", "main", str(self.repo))
        run_git("-C", str(self.repo), "config", "user.name", "Projectwright tests")
        run_git("-C", str(self.repo), "config", "user.email", "tests@example.invalid")
        (self.repo / "probe.py").write_text("value = 1\n")
        run_git("-C", str(self.repo), "add", "probe.py")
        run_git("-C", str(self.repo), "commit", "-qm", "fixture")
        self.head = run_git("-C", str(self.repo), "rev-parse", "HEAD")
        self.queue = self.project / "queue.md"
        self.queue.write_text("- [ ] **P201 — EDIT** PW-001 / PW-001-M1: change probe\n")
        self.config = {
            "id": "pw-recovery-fixture",
            "queue": str(self.queue),
            "worktree": str(self.repo),
            "cycle_file": str(self.project / "git_cycle.json"),
            "lock": str(self.project / "worker.lock"),
        }
        (self.project / "config.json").write_text(json.dumps(self.config))

    def write_recovery_journal(self, **overrides):
        task = {
            "id": "P201",
            "phase": "running",
            "git_head_before": self.head,
            "queue_sha256_before": hashlib.sha256(self.queue.read_bytes()).hexdigest(),
            "result_prefix": str(self.project / "result"),
        }
        task.update(overrides)
        (self.project / "worker_journal.json").write_text(
            json.dumps({"schema_version": 1, "current_task": task})
        )

    def write_worker_journal(self, *, kind="EDIT", phase="running", checked=False):
        line = self.queue.read_text().rstrip("\n")
        if checked:
            line = line.replace("- [ ]", "- [x]", 1)
            self.queue.write_text(line + "\n")
        data = {
            "schema_version": 1,
            "current_task": {
                "id": "P201",
                "kind": kind,
                "line": self.queue.read_text().rstrip("\n").replace("- [x]", "- [ ]", 1)
                if checked
                else line,
                "phase": phase,
                "git_head_before": self.head,
                "repository_digest_before": "same-repository",
                "result_prefix": str(self.project / "result"),
            },
        }
        (self.project / "worker_journal.json").write_text(json.dumps(data))

    def test_no_journal_is_clear(self):
        result = recovery.evidence(self.project, self.config)
        self.assertEqual(result["status"], "clear")

    def test_interrupted_edit_requires_review_without_mutation(self):
        self.write_recovery_journal(phase="running")
        before = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.project.iterdir()
            if path.is_file()
        }
        result = recovery.evidence(self.project, self.config)
        after = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.project.iterdir()
            if path.is_file()
        }
        self.assertEqual(result["status"], "needs_review")
        self.assertIn("Interrupted task", result["reason"])
        self.assertEqual(before, after)

    def test_interrupted_commit_after_head_change_requires_review(self):
        self.write_recovery_journal(phase="running")
        (self.repo / "probe.py").write_text("value = 2\n")
        run_git("-C", str(self.repo), "add", "probe.py")
        run_git("-C", str(self.repo), "commit", "-qm", "changed")
        result = recovery.evidence(self.project, self.config)
        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["head_unchanged"])

    def test_active_git_cycle_requires_review(self):
        self.write_recovery_journal()
        (self.project / "git_cycle.json").write_text("{}")
        result = recovery.evidence(self.project, self.config)
        self.assertEqual(result["status"], "needs_review")
        self.assertTrue(result["active_git_cycle"])

    def test_untracked_change_blocks_recovery(self):
        self.write_recovery_journal()
        (self.repo / "unexpected.txt").write_text("not allowed\n")
        result = recovery.evidence(self.project, self.config)
        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["working_tree_clean"])

    def test_verified_recovery_is_candidate_not_auto_recovery(self):
        self.queue.write_text("- [x] **P201 — EDIT** PW-001 / PW-001-M1: change probe\n")
        self.write_recovery_journal(phase="verified")
        result = recovery.evidence(self.project, self.config)
        self.assertEqual(result["status"], "reconciliation_candidate")
        self.assertIsNotNone(
            json.loads((self.project / "worker_journal.json").read_text())["current_task"]
        )

    def test_corrupt_recovery_journal_is_not_replaced(self):
        original = "{invalid"
        (self.project / "worker_journal.json").write_text(original)
        with self.assertRaises(json.JSONDecodeError):
            recovery.evidence(self.project, self.config)
        self.assertEqual((self.project / "worker_journal.json").read_text(), original)

    def test_incident_record_is_idempotent(self):
        self.write_recovery_journal()
        result = recovery.evidence(self.project, self.config)
        first = recovery.record_incident(self.project, result)
        second = recovery.record_incident(self.project, result)
        incidents = json.loads((self.project / "recovery_incidents.json").read_text())
        self.assertTrue(first["recorded"])
        self.assertFalse(second["recorded"])
        self.assertEqual(len(incidents["incidents"]), 1)

    def test_recovery_record_cli_honors_busy_project_lock(self):
        self.write_recovery_journal()
        lock = self.project / "worker.lock"
        with lock.open("a+") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(SRC / "project_recovery.py"),
                    "--project",
                    self.config["id"],
                    "--config-root",
                    str(self.root / "projects"),
                    "--record",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 2)
        self.assertIn('"status": "busy"', completed.stdout)

    def test_recovery_record_cli_writes_only_incident_evidence(self):
        self.write_recovery_journal()
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(SRC / "project_recovery.py"),
                "--project",
                self.config["id"],
                "--config-root",
                str(self.root / "projects"),
                "--record",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 3, completed.stderr)
        self.assertTrue((self.project / "recovery_incidents.json").exists())
        self.assertTrue((self.project / "worker_journal.json").exists())

    def test_journal_read_missing_file_is_idle(self):
        data = journal.read(self.project / "worker_journal.json")
        self.assertIsNone(data["current_task"])
        self.assertIsNone(data["last_completed_task"])

    def test_journal_interrupted_edit_is_review_only(self):
        self.write_worker_journal(kind="EDIT", phase="running")
        result = journal.inspect(
            self.project / "worker_journal.json",
            self.queue.read_text(),
            TASK_RE,
            self.head,
            "same-repository",
            False,
        )
        self.assertEqual(result["outcome"], "review")
        self.assertEqual(result["phase"], "running")

    def test_journal_interrupted_commit_is_review_only(self):
        self.write_worker_journal(kind="COMMIT", phase="running")
        result = journal.inspect(
            self.project / "worker_journal.json",
            self.queue.read_text(),
            TASK_RE,
            self.head,
            "same-repository",
            True,
        )
        self.assertEqual(result["outcome"], "review")
        self.assertTrue(result["cycle_present"])

    def test_timer_generates_dispatcher_service_and_disabled_timer(self):
        service, timer_unit = timer.unit_strings(
            self.config["id"], 20, Path("/tmp/projectwright/pw_dispatch.py")
        )
        self.assertIn("ExecStart=/usr/bin/python3 -B /tmp/projectwright/pw_dispatch.py --project pw-recovery-fixture", service)
        self.assertNotIn("project_task_worker.py", service)
        self.assertNotIn("--once", service)
        self.assertIn("Type=oneshot", service)
        self.assertIn("OnUnitInactiveSec=20min", timer_unit)
        self.assertIn("Persistent=false", timer_unit)
        self.assertIn("WantedBy=timers.target", timer_unit)

    def test_timer_rejects_invalid_interval_and_relative_dispatcher(self):
        with self.assertRaises(ValueError):
            timer.unit_strings(self.config["id"], 1, Path("/tmp/pw_dispatch.py"))
        with self.assertRaises(ValueError):
            timer.unit_strings(self.config["id"], 20, Path("pw_dispatch.py"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
