"""Telegram callback replay and rejection contracts without network access."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "projectwright"))
import pw_buttons


class TelegramCallbackReplay(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="pw-callback-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / "fixture"
        self.project.mkdir()
        self.lock = self.project / "worker.lock"
        (self.project / "config.json").write_text(json.dumps({"lock": str(self.lock)}))
        self.record = {
            "project": "fixture", "requirement": "DEMO-1",
            "milestone": "DEMO-1-M1", "head": "a" * 40,
            "requirements_sha256": "b" * 64, "queue_sha256": "c" * 64,
            "task_ids": ["P101"], "scope_paths": ["probe.txt"],
            "command": ["python3", "-m", "unittest"],
        }
        self.pending = self.project / "telegram_approval_pending.json"
        self.pending.write_text(json.dumps(self.record))

    def test_rejection_does_not_delete_pending_or_change_queue(self):
        # Replace just the bridge's atomic JSON writer. No Telegram, Hermes or
        # production directories are accessed by the callback under test.
        bridge = types.ModuleType("project_telegram_approval")
        def atomic_json(path, record):
            Path(path).write_text(json.dumps(record))
        bridge.atomic_json = atomic_json
        with patch.dict(sys.modules, {"project_telegram_approval": bridge}):
            outcome = pw_buttons.reject(self.root, pw_buttons.callback_data("r", self.record))
        self.assertIn("REJECTED", outcome)
        self.assertEqual(json.loads(self.pending.read_text()), self.record)
        self.assertEqual(json.loads((self.project / "telegram_approval_rejected.json").read_text()), self.record)

    def test_stale_callback_is_rejected_after_request_replaced(self):
        old = pw_buttons.callback_data("r", self.record)
        new = {**self.record, "head": "d" * 40}
        self.pending.write_text(json.dumps(new))
        with self.assertRaisesRegex(ValueError, "Stale"):
            pw_buttons.resolve(self.root, old)
        self.assertEqual(pw_buttons.resolve(self.root, pw_buttons.callback_data("a", new))[2], new)

    def test_approval_callback_with_missing_pending_is_rejected(self):
        token = pw_buttons.callback_data("a", self.record)
        self.pending.unlink()
        with self.assertRaisesRegex(ValueError, "no longer pending"):
            pw_buttons.approve(self.root, token)

    def test_rejected_callback_cannot_be_used_as_approval(self):
        with self.assertRaisesRegex(ValueError, "Not an approval"):
            pw_buttons.approve(self.root, pw_buttons.callback_data("r", self.record))

    def test_approval_receipt_consumes_pending_and_replay_is_refused(self):
        bridge = types.ModuleType("project_telegram_approval")
        guard = types.ModuleType("project_milestone_guard")
        policy = {"milestones": {
            "DEMO-1-M1": {
                "requirement": "DEMO-1",
                "command": ["python3", "-m", "unittest"],
                "scope_paths": ["probe.txt"],
            }
        }}
        bridge.project_data = lambda directory: ({"id": "fixture"}, policy)
        received = []
        def approve(cfg, directory, req, milestone, command, scope, *, expected):
            received.append((cfg, directory, req, milestone, command, scope, expected))
            return {"git_head": self.record["head"]}
        guard.approve = approve
        token = pw_buttons.callback_data("a", self.record)
        with patch.dict(sys.modules, {
            "project_telegram_approval": bridge,
            "project_milestone_guard": guard,
        }):
            response = pw_buttons.approve(self.root, token)
            self.assertIn("APPROVED", response)
            self.assertEqual(received[0][-1], self.record)
            self.assertEqual(received[0][1], self.project)
            self.assertFalse(self.pending.exists())
            with self.assertRaisesRegex(ValueError, "no longer pending"):
                pw_buttons.approve(self.root, token)
            self.assertEqual(len(received), 1)

    def test_failed_approval_keeps_pending_for_review(self):
        bridge = types.ModuleType("project_telegram_approval")
        guard = types.ModuleType("project_milestone_guard")
        bridge.project_data = lambda directory: (
            {"id": "fixture"}, {"milestones": {"DEMO-1-M1": {
                "requirement": "DEMO-1",
                "command": ["python3", "-m", "unittest"],
                "scope_paths": ["probe.txt"],
            }}},
        )
        def refuse(*args, **kwargs):
            raise ValueError("stale acceptance evidence")
        guard.approve = refuse
        with patch.dict(sys.modules, {
            "project_telegram_approval": bridge,
            "project_milestone_guard": guard,
        }):
            with self.assertRaisesRegex(ValueError, "stale acceptance"):
                pw_buttons.approve(self.root, pw_buttons.callback_data("a", self.record))
        self.assertEqual(json.loads(self.pending.read_text()), self.record)

    def test_traversal_and_tampered_callback_rejected(self):
        for bad in ("pwa:a:../fixture:0123456789abcdef0123",
                    "pwa:a:fixture:00000000000000000000",
                    "pwa:x:fixture:0123456789abcdef0123"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                pw_buttons.resolve(self.root, bad)


if __name__ == "__main__":
    unittest.main()
