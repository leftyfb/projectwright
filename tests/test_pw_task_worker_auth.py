import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / "src" / "projectwright"
sys.path.insert(0, str(SRC))
import pw_task_worker
from pw_one_shot_auth import create, consume, sha256_bytes


class OneShotWorkerAuthorizationTests(unittest.TestCase):
    def test_configured_active_journal_blocks_direct_one_shot_worker(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config_home = root / "config"
            project_dir = config_home / "projects/demo"
            project_dir.mkdir(parents=True)
            journal = root / "custom-worker-journal.json"
            journal.write_text(json.dumps({"schema_version": 1, "current_task": {"id": "P101"}}))
            config = {
                "id": "demo",
                "projectwright_initialized": 1,
                "queue": str(root / "queue.md"),
                "work_log": str(root / "work.log"),
                "lock": str(root / "worker.lock"),
                "run_log": str(root / "run.log"),
                "result_dir": str(root / "results"),
                "cycle_file": str(root / "cycle.json"),
                "worktree": str(root / "worktree"),
                "hermes": "hermes",
                "timeout_seconds": 10,
                "worker_journal_file": str(journal),
            }
            (project_dir / "config.json").write_text(json.dumps(config))
            clear_report = subprocess.CompletedProcess([], 0, json.dumps({"status": "clear"}), "")
            with patch.dict(os.environ, {"PROJECTWRIGHT_CONFIG_DIR": str(config_home)}, clear=True):
                pw_task_worker.load_project("demo")
                with patch.object(pw_task_worker.subprocess, "run", return_value=clear_report) as run:
                    self.assertEqual(pw_task_worker.process_once(), 2)
                    run.assert_called_once()

    def test_disabled_project_requires_all_ephemeral_markers(self):
        with tempfile.TemporaryDirectory() as td:
            config_home = Path(td) / "config"
            project_dir = config_home / "projects/demo"
            project_dir.mkdir(parents=True)
            (project_dir / "config.json").write_text(json.dumps({
                "id": "demo", "projectwright_initialized": 1,
                "execution": {"enabled": False},
            }))
            base_env = {"PROJECTWRIGHT_CONFIG_DIR": str(config_home)}
            incomplete_envs = ({}, {"PROJECTWRIGHT_DISPATCHED": "1"},
                               {"PROJECTWRIGHT_ONE_SHOT_AUTH": "1"},
                               {"PROJECTWRIGHT_DISPATCHED": "1", "PROJECTWRIGHT_ONE_SHOT_AUTH": "1"},
                               {"PROJECTWRIGHT_ONE_SHOT_HANDOFF": "attacker-chosen"})
            for extra in incomplete_envs:
                with self.subTest(extra=extra), patch.dict(os.environ, {**base_env, **extra}, clear=True), \
                     patch("sys.argv", ["pw_task_worker.py", "--project", "demo", "--once"]), \
                     patch.object(pw_task_worker, "process_once") as process_once, \
                     patch("sys.stdout", new_callable=io.StringIO) as output:
                    result = pw_task_worker.main()
                    self.assertEqual(result, 3)
                    self.assertEqual(json.loads(output.getvalue())["decision"], "disabled")
                    process_once.assert_not_called()

    def test_handoff_is_single_use_and_bound_to_all_claims(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "demo"
            claims = {"project": "demo", "config": str(project / "config.json"),
                      "task_id": "P101", "queue_sha256": sha256_bytes(b"queue"),
                      "requirements_sha256": sha256_bytes(b"req"), "configured_branch": "main",
                      "git_branch": "main", "head": "a" * 40}
            token = create(project, claims)
            for key, changed in (("project", "other"), ("config", str(project / "other.json")),
                                 ("task_id", "P102"), ("queue_sha256", sha256_bytes(b"changed")),
                                 ("requirements_sha256", sha256_bytes(b"changed")),
                                 ("git_branch", "other"), ("head", "b" * 40)):
                altered = dict(claims, **{key: changed})
                with self.subTest(key=key), self.assertRaises(ValueError):
                    consume(project, token, altered)
            consume(project, token, claims)
            with self.assertRaises(ValueError):
                consume(project, token, claims)

    def test_expired_handoff_is_rejected(self):
        import json
        from pw_one_shot_auth import handoff_dir
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "demo"
            claims = {"project": "demo", "task_id": "P101"}
            token = create(project, claims)
            path = handoff_dir(project) / f"{token}.json"
            payload = json.loads(path.read_text())
            payload["created_at"] = 0
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "stale"):
                consume(project, token, claims)

    def test_concurrent_consumers_cannot_reuse_handoff(self):
        import threading
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "demo"
            claims = {"project": "demo", "task_id": "P101"}
            token = create(project, claims)
            barrier = threading.Barrier(2)
            outcomes = []
            def worker():
                barrier.wait()
                try:
                    consume(project, token, claims)
                    outcomes.append("accepted")
                except ValueError:
                    outcomes.append("rejected")
            threads = [threading.Thread(target=worker) for _ in range(2)]
            for thread in threads: thread.start()
            for thread in threads: thread.join()
            self.assertCountEqual(outcomes, ["accepted", "rejected"])


if __name__ == "__main__":
    unittest.main()
