"""Notifier must stop deliveries when a pending approval is withdrawn mid-send."""
from __future__ import annotations
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / "src" / "projectwright"
sys.path.insert(0, str(SRC))
import pw_notify

class RevokedDelivery(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="pw-notify-race-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.project = self.root / "fixture"
        self.project.mkdir()
        self.pinned = {
            "project": "fixture", "milestone": "DEMO-1-M1",
            "head": "a" * 40, "task_ids": ["P101"],
            "requirement": "DEMO-1",
        }
        (self.project / "telegram_approval_pending.json").write_text(json.dumps(self.pinned))
        (self.project / "config.json").write_text(
            json.dumps({"lock": str(self.project / "worker.lock")}))
        self.bridge = types.ModuleType("project_telegram_approval")
        self.bridge.load_pending = lambda root: [(self.project, self.pinned)]
        self.bridge.atomic_json = lambda path, data: Path(path).write_text(json.dumps(data))

    def test_revoked_during_first_send_prevents_second_send_and_receipt(self):
        recipients = []
        def deliver(data):
            recipients.append(data["chat_id"])
            (self.project / "telegram_approval_pending.json").unlink()
            return 117
        settings = {
            "TELEGRAM_BOT_TOKEN": "fixture-token",
            "TELEGRAM_ALLOWED_USERS": "111,222",
        }
        with patch.dict(sys.modules, {"project_telegram_approval": self.bridge}), \
             patch.object(pw_notify, "config_values", return_value=settings):
            pw_notify.notify_pending(self.root, transport=deliver)
        self.assertEqual(recipients, ["111"])
        self.assertFalse((self.project / "telegram_approval_notified.json").exists())

    def test_already_rejected_pending_request_is_not_sent(self):
        (self.project / "telegram_approval_rejected.json").write_text(json.dumps(self.pinned))
        sent = []
        with patch.dict(sys.modules, {"project_telegram_approval": self.bridge}):
            pw_notify.notify_pending(self.root, transport=lambda data: sent.append(data))
        self.assertEqual(sent, [])
        self.assertFalse((self.project / "telegram_approval_notified.json").exists())

if __name__ == "__main__":
    unittest.main()
