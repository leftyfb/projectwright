"""Self-contained acceptance-receipt and Telegram approval tests.

Run directly from the repository root:
    python3 -B tests/acceptance/test_acceptance_and_telegram.py

All Git repositories, project state, Telegram payloads, and transports are
fixtures. No live Telegram service or user project state is accessed.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Import the checked-out implementation, never ~/.hermes/scripts.
SRC = Path(__file__).resolve().parents[2] / "src" / "projectwright"
sys.path.insert(0, str(SRC))

import project_milestone_guard as guard
import project_telegram_approval as bridge
import pw_buttons
import pw_notify
import pw_plugin


REQUIREMENTS = (
    "## PW-005 — Requirement\n\n"
    "### PW-005-M1 — First\nFirst work.\n\n"
    "### PW-005-M2 — Second\nSecond work.\n\n"
    "### PW-005-M3 — Third\nThird work.\n"
).encode()


def run_git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class ReceiptChainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="projectwright-receipts-")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        run_git(self.repo, "init", "-q")
        run_git(self.repo, "config", "user.email", "test@example.invalid")
        run_git(self.repo, "config", "user.name", "Projectwright Test")

        (self.repo / "approval_probe.py").write_text("base\n")
        (self.repo / "test.py").write_text("base\n")
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-qm", "M1")
        self.first = run_git(self.repo, "rev-parse", "HEAD")

        (self.repo / "approval_probe.py").write_text("M2\n")
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-qm", "M2")
        self.second = run_git(self.repo, "rev-parse", "HEAD")

        self.queue = (
            "- [x] **P951 — COMMIT** PW-005 / PW-005-M1: old\n"
            "- [x] **P104 — COMMIT** PW-005 / PW-005-M2: new\n"
        )
        self.policy = {
            "version": 1,
            "milestones": {
                milestone: {
                    "requirement": "PW-005",
                    "command": ["true"],
                    "scope_paths": ["approval_probe.py", "test.py"],
                }
                for milestone in ("PW-005-M1", "PW-005-M2", "PW-005-M3")
            },
        }
        self.journal = {
            "current_task": None,
            "last_completed_task": {
                "id": "P104",
                "kind": "COMMIT",
                "git_head_before": self.first,
                "git_head_after": self.second,
            },
        }
        self.state = {
            "verified_milestones": {
                "PW-005-M1": self.record("PW-005-M1", self.first, ["P951"])
            }
        }

    def record(self, milestone: str, head: str, task_ids: list[str]) -> dict:
        spec = self.policy["milestones"][milestone]
        return {
            "requirement_id": "PW-005",
            "milestone_id": milestone,
            "git_head": head,
            "completed_task_ids": task_ids,
            "acceptance_exit_code": 0,
            "milestone_requirements_sha256": guard.milestone_fingerprint(REQUIREMENTS, milestone),
            "acceptance_policy_sha256": guard.acceptance_policy_fingerprint(spec),
            "acceptance_command": ["true"],
            "scope_paths": ["approval_probe.py", "test.py"],
            "scope_version": 1,
        }

    def receipts(self, **kwargs: object) -> dict:
        return guard.current_receipts(
            kwargs.get("state", self.state),
            REQUIREMENTS,
            kwargs.get("queue", self.queue),
            kwargs.get("head", self.second),
            repo=self.repo,
            strict=True,
            policy=kwargs.get("policy", self.policy),
            journal=kwargs.get("journal", self.journal),
        )

    def test_accepted_receipt_survives_authorized_successor_commit(self) -> None:
        self.assertIn("PW-005-M1", self.receipts())

    def test_missing_or_wrong_journal_blocks_successor_bridge(self) -> None:
        variants = (
            {},
            {"current_task": {"id": "P103"}, "last_completed_task": self.journal["last_completed_task"]},
            {"current_task": None, "last_completed_task": {**self.journal["last_completed_task"], "id": "BAD"}},
            {"current_task": None, "last_completed_task": {**self.journal["last_completed_task"], "git_head_before": self.second}},
        )
        for journal in variants:
            with self.subTest(journal=journal):
                self.assertNotIn("PW-005-M1", self.receipts(journal=journal))

    def test_scope_or_queue_change_blocks_receipt(self) -> None:
        policy = json.loads(json.dumps(self.policy))
        policy["milestones"]["PW-005-M2"]["scope_paths"] = ["test.py"]
        self.assertNotIn("PW-005-M1", self.receipts(policy=policy))
        self.assertNotIn("PW-005-M1", self.receipts(queue=self.queue.replace("P104 — COMMIT", "P104 — TEST")))

    def test_unrelated_extra_commit_blocks_receipt(self) -> None:
        (self.repo / "other").write_text("x\n")
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-qm", "unauthorized")
        self.assertNotIn("PW-005-M1", self.receipts(head=run_git(self.repo, "rev-parse", "HEAD")))

    def test_accepted_successor_receipt_persists_without_journal(self) -> None:
        self.state["verified_milestones"]["PW-005-M2"] = self.record("PW-005-M2", self.second, ["P104"])
        self.assertEqual(set(self.receipts(journal={})), {"PW-005-M1", "PW-005-M2"})

    def test_pending_next_milestone_bridges_through_accepted_successor(self) -> None:
        self.state["verified_milestones"]["PW-005-M2"] = self.record("PW-005-M2", self.second, ["P104"])
        (self.repo / "test.py").write_text("M3\n")
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-qm", "M3")
        third = run_git(self.repo, "rev-parse", "HEAD")
        queue = self.queue + "- [x] **P204 — COMMIT** PW-005 / PW-005-M3: next\n"
        journal = {
            "current_task": None,
            "last_completed_task": {
                "id": "P204", "kind": "COMMIT",
                "git_head_before": self.second, "git_head_after": third,
            },
        }
        self.assertEqual(
            set(self.receipts(head=third, queue=queue, journal=journal)),
            {"PW-005-M1", "PW-005-M2"},
        )

    def test_milestone_hash_is_section_scoped(self) -> None:
        changed = REQUIREMENTS.replace(b"Second work.", b"Changed second work.")
        self.assertIn("PW-005-M1", self.receipts())
        self.assertNotEqual(
            guard.milestone_fingerprint(REQUIREMENTS, "PW-005-M2"),
            guard.milestone_fingerprint(changed, "PW-005-M2"),
        )


class TelegramApprovalAndButtonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="projectwright-telegram-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "projects"
        self.root.mkdir()
        self.project = self.root / "fixture"
        self.project.mkdir()
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        run_git(self.repo, "init", "-q")
        run_git(self.repo, "config", "user.name", "Fixture")
        run_git(self.repo, "config", "user.email", "fixture@example.invalid")
        (self.repo / "probe.py").write_text("VALUE = 1\n")
        run_git(self.repo, "add", "probe.py")
        run_git(self.repo, "commit", "-qm", "fixture")

        self.req = self.project / "requirements.md"
        self.req.write_text("## DEMO-1 — Requirement\n\n### DEMO-1-M1 — Milestone\n")
        self.queue = self.project / "queue.md"
        self.queue.write_text(
            "- [x] **P1 — READ** DEMO-1 / DEMO-1-M1: Inspect\n"
            "- [x] **P2 — COMMIT** DEMO-1 / DEMO-1-M1: Commit\n"
        )
        self.cfg = {
            "id": "fixture",
            "worktree": str(self.repo),
            "branch": run_git(self.repo, "branch", "--show-current"),
            "lock": str(self.project / "lock"),
            "queue": str(self.queue),
            "cycle_file": str(self.project / "cycle.json"),
            "planning": {"enabled": True, "requirements_file": str(self.req)},
        }
        (self.project / "config.json").write_text(json.dumps(self.cfg))
        self.policy = {"version": 1, "milestones": {"DEMO-1-M1": {
            "requirement": "DEMO-1",
            "command": [sys.executable, "-B", "-c", "import sys; sys.exit(0)"],
            "scope_paths": ["probe.py"],
        }}}
        (self.project / "telegram_acceptance.json").write_text(json.dumps(self.policy))

    def scan_one(self) -> dict:
        found = bridge.scan(self.root)
        self.assertEqual(len(found), 1)
        return found[0]

    def test_scan_pins_buttons_and_message_evidence(self) -> None:
        record = self.scan_one()
        self.assertEqual(record["milestone"], "DEMO-1-M1")
        approve_data = pw_buttons.callback_data("a", record)
        reject_data = pw_buttons.callback_data("r", record)
        self.assertLessEqual(len(approve_data.encode()), 64)
        self.assertEqual(pw_buttons.resolve(self.root, approve_data)[0], "a")
        self.assertEqual(pw_buttons.resolve(self.root, reject_data)[0], "r")
        self.assertIn("DEMO-1-M1", pw_buttons.message_text(record))
        self.assertNotEqual(pw_buttons.request_id(record), pw_buttons.request_id({**record, "head": "f" * 40}))

    def test_stale_button_is_rejected_after_pending_record_changes(self) -> None:
        record = self.scan_one()
        callback = pw_buttons.callback_data("a", record)
        changed = {**record, "head": "f" * 40}
        (self.project / "telegram_approval_pending.json").write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, "Stale|mismatched"):
            pw_buttons.resolve(self.root, callback)

    def test_invalid_and_traversal_callbacks_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            pw_buttons.resolve(self.root, "pwa:a:../etc:" + "0" * 20)
        with self.assertRaises(ValueError):
            pw_buttons.callback_data("a", {"project": "../etc"})

    def test_approval_persists_receipt_and_replay_is_refused(self) -> None:
        self.scan_one()
        result = bridge.approve_single(self.root)
        self.assertIn("APPROVED", result)
        self.assertFalse((self.project / "telegram_approval_pending.json").exists())
        state = json.loads((self.project / "planning_state.json").read_text())
        self.assertEqual(state["verified_milestones"]["DEMO-1-M1"]["completed_task_ids"], ["P1", "P2"])
        with self.assertRaisesRegex(ValueError, "exactly one pending"):
            bridge.approve_single(self.root)

    def test_stale_approval_fails_closed_without_receipt(self) -> None:
        self.scan_one()
        self.req.write_text(self.req.read_text() + "\nChanged while awaiting approval.\n")
        with self.assertRaisesRegex(ValueError, "stale|Stale"):
            bridge.approve_single(self.root)
        self.assertFalse((self.project / "planning_state.json").exists())
        self.assertTrue((self.project / "telegram_approval_pending.json").exists())

    def test_rejection_persists_and_blocks_notification(self) -> None:
        record = self.scan_one()
        callback = pw_buttons.callback_data("r", record)
        # pw_buttons uses dynamic top-level imports; bind those names to the
        # checked-out modules already loaded from src/projectwright.
        with patch.dict(sys.modules, {
            "project_telegram_approval": bridge,
            "project_milestone_guard": guard,
        }):
            result = pw_buttons.reject(self.root, callback)
        self.assertIn("REJECTED", result)
        self.assertEqual(
            json.loads((self.project / "telegram_approval_rejected.json").read_text()),
            record,
        )
        self.assertEqual(pw_notify.notify_pending(self.root, dry_run=True), [])

    def test_notification_sends_both_buttons_and_deduplicates(self) -> None:
        record = self.scan_one()
        payloads: list[dict] = []
        with patch.object(pw_notify, "config_values", return_value={
            "TELEGRAM_BOT_TOKEN": "fixture-token",
            "TELEGRAM_ALLOWED_USERS": "123",
        }):
            rows = pw_notify.notify_pending(
                self.root,
                transport=lambda payload: (payloads.append(payload) or 56),
            )
            self.assertEqual(len(rows), 1)
            buttons = payloads[0]["reply_markup"]["inline_keyboard"][0]
            self.assertEqual([button["text"] for button in buttons], ["Approve", "Reject"])
            self.assertEqual(
                [pw_buttons.resolve(self.root, button["callback_data"])[0] for button in buttons],
                ["a", "r"],
            )
            self.assertEqual(pw_notify.notify_pending(self.root, dry_run=True), [])
        self.assertEqual(json.loads((self.project / "telegram_approval_notified.json").read_text())["message_id"], 56)
        self.assertEqual(record["project"], "fixture")

    def test_notification_transport_failure_is_retryable(self) -> None:
        self.scan_one()
        with patch.object(pw_notify, "config_values", return_value={
            "TELEGRAM_BOT_TOKEN": "fixture-token",
            "TELEGRAM_ALLOWED_USERS": "123",
        }):
            with self.assertRaisesRegex(OSError, "fixture transport failure"):
                pw_notify.notify_pending(
                    self.root,
                    transport=lambda payload: (_ for _ in ()).throw(OSError("fixture transport failure")),
                )
            self.assertFalse((self.project / "telegram_approval_notified.json").exists())
            self.assertTrue((self.project / "telegram_approval_pending.json").exists())
            rows = pw_notify.notify_pending(self.root, transport=lambda payload: 57)
        self.assertEqual(len(rows), 1)
        self.assertEqual(json.loads((self.project / "telegram_approval_notified.json").read_text())["message_id"], 57)

    def test_notifier_and_plugin_have_different_multi_user_contracts(self) -> None:
        """Record the existing contract mismatch; source behavior is unchanged."""
        record = self.scan_one()
        values = {
            "TELEGRAM_BOT_TOKEN": "fixture-token",
            "TELEGRAM_ALLOWED_USERS": "123,456",
        }
        with patch.object(pw_notify, "config_values", return_value=values):
            self.assertEqual(pw_plugin._authorized_ids(), frozenset({"123", "456"}))
            with self.assertRaisesRegex(ValueError, "exactly one authorized"):
                pw_notify.send(self.root, record, transport=lambda payload: 58)


if __name__ == "__main__":
    unittest.main(verbosity=2)
