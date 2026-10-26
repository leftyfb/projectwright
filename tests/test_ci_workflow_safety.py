"""Guard against accidental Telegram delivery in routine preflight CI."""
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]


class TestWorkflowSideEffects(unittest.TestCase):
    def test_read_only_pw_test_preflight_cannot_send_telegram(self):
        workflow = (REPO / ".github/workflows/pw-test-preflight.yml").read_text()
        # Live bot sends belong exclusively to an explicitly triggered,
        # isolated approval workflow, never to a routine preflight.
        for forbidden in (
            "/sendMessage",
            "pw-notify --root",
            "pw_notify.notify_pending(",
            "scripts/pw-test-live-approval.py prepare",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, workflow)
        self.assertIn("Inspect", workflow)

    def test_live_delivery_requires_isolation_before_send(self):
        workflow = (REPO / ".github/workflows/pw-test-send-approval.yml").read_text()
        scope = "PROJECTWRIGHT_APPROVAL_ROOT=/home/ubuntu/projectwright-live-test/projects"
        self.assertIn(scope, workflow)
        self.assertIn("telegram_approval_pending.json", workflow)
        self.assertIn("pw-notify --root /home/ubuntu/projectwright-live-test/projects --send", workflow)
        self.assertLess(workflow.index(scope), workflow.index("pw-notify --root"))


if __name__ == "__main__":
    unittest.main()
