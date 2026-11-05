"""One-shot authorization may continue a verified active EDIT/TEST/COMMIT cycle."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pw_dispatch import parse_manual_status, run_tick


def status(*, blockers=None, decision="blocked"):
    blockers = blockers if blockers is not None else ["active_git_cycle", "dirty_worktree_review"]
    return {
        "project": "demo",
        "decision": decision,
        "reason": ", ".join(blockers),
        "pending": 2,
        "completed": 1,
        "queue_blocked": 0,
        "invalid_lines": [],
        "blockers": blockers,
        "planning_enabled": True,
        "branch": "main",
        "head": "a" * 40,
        "queue_sha256": "b" * 64,
        "requirements_sha256": "c" * 64,
        "pending_tasks": [{"id": "P103", "kind": "TEST"}, {"id": "P104", "kind": "COMMIT"}],
    }


class ManualCycleContinuationTests(unittest.TestCase):
    def test_rejects_blocked_manager_without_verified_cycle(self):
        with self.assertRaises(ValueError):
            parse_manual_status(json.dumps(status()), "demo", 2)

    def test_accepts_only_verified_cycle_blockers(self):
        parsed = parse_manual_status(json.dumps(status()), "demo", 2, cycle_authorized=True)
        self.assertEqual(parsed["pending_tasks"][0]["kind"], "TEST")
        with self.assertRaises(ValueError):
            parse_manual_status(
                json.dumps(status(blockers=["active_git_cycle", "wrong_branch"])),
                "demo", 2, cycle_authorized=True,
            )

    def test_verified_cycle_dispatches_next_task_with_one_shot_handoff(self):
        calls = []
        def runner(argv, **kwargs):
            calls.append((argv, kwargs))
            if argv[-1] == "--status":
                return SimpleNamespace(returncode=2, stdout=json.dumps(status()), stderr="")
            return SimpleNamespace(returncode=1, stdout="", stderr="test worker failure fixture")
        with (
            patch("pw_dispatch.authorized_cycle_task", return_value=True) as authorized,
            patch("pw_dispatch._manual_handoff", return_value="fixture-token"),
            patch("pw_dispatch.default_project_root", return_value=Path("/tmp/pw-cycle-test")),
        ):
            result = run_tick("demo", Path("/tmp/pw-cycle-code"), runner=runner, one_shot=True, no_telegram=True)
        self.assertEqual(result, 1)
        authorized.assert_called_once()
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1][0][-1], "--no-telegram")
        self.assertIn("pw_task_worker.py", str(calls[1][0][2]))

    def test_unverified_cycle_never_invokes_worker(self):
        calls = []
        def runner(argv, **kwargs):
            calls.append(argv)
            return SimpleNamespace(returncode=2, stdout=json.dumps(status()), stderr="")
        with patch("pw_dispatch.authorized_cycle_task", return_value=False):
            result = run_tick("demo", Path("/tmp/pw-cycle-code"), runner=runner, one_shot=True)
        self.assertEqual(result, 21)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
