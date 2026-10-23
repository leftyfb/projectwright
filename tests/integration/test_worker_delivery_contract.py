"""Worker persistence remains durable when Telegram delivery fails.

This fixture drives process_once through source modules only. The repository,
project files, Hermes response and notification transport are all local mocks;
no installed scripts or live service are used.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2] / "src" / "projectwright"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

import project_quota
import project_worker_journal
import project_worker_progress
import project_task_worker as worker


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


class WorkerDeliveryPersistenceTests(unittest.TestCase):
    def test_delivery_failure_does_not_roll_back_persisted_task(self) -> None:
        with tempfile.TemporaryDirectory(prefix="projectwright-delivery-") as td:
            root = Path(td)
            project_dir = root / "projects" / "fixture"
            project_dir.mkdir(parents=True)
            repo = root / "repo"
            repo.mkdir()
            git(repo, "init", "-q")
            git(repo, "config", "user.name", "Fixture")
            git(repo, "config", "user.email", "fixture@example.invalid")
            (repo / "probe.txt").write_text("fixture\n")
            git(repo, "add", "probe.txt")
            git(repo, "commit", "-qm", "fixture")

            queue = project_dir / "queue.md"
            queue.write_text("- [ ] **P101 — READ** inspect fixture\n")
            config = {
                "id": "fixture",
                "display_name": "Fixture Project",
                "queue": str(queue),
                "work_log": str(project_dir / "work_log.md"),
                "lock": str(project_dir / "worker.lock"),
                "run_log": str(project_dir / "run.log"),
                "result_dir": str(project_dir / "results"),
                "cycle_file": str(project_dir / "git_cycle.json"),
                "worktree": str(repo),
                "hermes": "/bin/false",
                "timeout_seconds": 30,
                "worker_state_file": str(project_dir / "worker_state.json"),
            }
            config_path = project_dir / "config.json"
            config_path.write_text(json.dumps(config))
            env = {"HERMES_PROJECT_CONFIG_DIR": str(root / "projects")}

            def fake_run_agent(prompt: str, log):
                report_path = Path(prompt)
                report_path.write_text(json.dumps({
                    "task_id": "P101",
                    "status": "completed",
                    "summary": "fixture read complete",
                    "verification": "fixture verified",
                    "blocker": "",
                }))
                return 0, "fixture Hermes output"

            with patch.dict(os.environ, env):
                worker.load_project("fixture")
                with (
                    patch.object(project_quota, "evaluate", return_value={"allowed": True}),
                    patch.object(worker, "prompt_for", side_effect=lambda task, report: str(report)),
                    patch.object(worker, "run_agent", side_effect=fake_run_agent),
                    patch.object(worker, "verify", return_value=(True, "fixture verified")),
                    patch.object(worker, "cycle_begin"),
                    patch.object(worker, "cycle_approved"),
                    patch.object(worker, "cycle_read", return_value=None),
                    patch.object(worker, "notification_footer", return_value="fixture footer"),
                    patch.object(worker, "deliver", return_value=False),
                ):
                    result = worker.process_once()

            self.assertEqual(result, 1, "delivery failure is reported to the caller")
            self.assertEqual(queue.read_text(), "- [x] **P101 — READ** inspect fixture\n")
            progress = project_worker_progress.read_state(project_dir / "worker_state.json")
            self.assertEqual(progress["completed_task_ids"], ["P101"])
            journal = project_worker_journal.read(project_dir / "worker_journal.json")
            self.assertIsNone(journal["current_task"])
            self.assertEqual(journal["last_completed_task"]["id"], "P101")


if __name__ == "__main__":
    unittest.main(verbosity=2)
