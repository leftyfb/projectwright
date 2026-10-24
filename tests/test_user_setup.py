"""User approval timer onboarding tested without systemd or Hermes execution."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "projectwright"))
import pw_project_timer as timer


class ApprovalSetupTests(unittest.TestCase):
    def test_unit_generation_and_idempotent_user_setup(self):
        with tempfile.TemporaryDirectory(prefix="pw-setup-user-") as temp:
            home = Path(temp)
            calls = []
            def runner(argv, *, check):
                calls.append(argv)
                self.assertTrue(check)
            values = {"TELEGRAM_BOT_TOKEN": "fixture", "TELEGRAM_ALLOWED_USERS": "111"}
            with patch.object(Path, "home", return_value=home), \
                 patch.object(timer.os, "geteuid", return_value=1000), \
                 patch("pw_notify.config_values", return_value=values):
                timer.setup_user_approvals(runner=runner, enable_plugin=True)
                timer.setup_user_approvals(runner=runner)
            root = home / ".config/systemd/user"
            service = (root / "projectwright-approval-notify.service").read_text()
            unit = (root / "projectwright-approval-notify.timer").read_text()
            self.assertIn("[Service]\n", service)
            self.assertIn("pw_notify.py --send\n", service)
            self.assertIn("OnUnitInactiveSec=10min\n", unit)
            self.assertEqual(calls[0], ["hermes", "plugins", "enable", "projectwright-approvals"])
            self.assertEqual(calls[1:3], [
                ["systemctl", "--user", "daemon-reload"],
                ["systemctl", "--user", "enable", "--now", "projectwright-approval-notify.timer"],
            ])

    def test_root_cannot_implicitly_configure_a_user(self):
        with patch.object(timer.os, "geteuid", return_value=0):
            with self.assertRaisesRegex(ValueError, "non-root"):
                timer.setup_user_approvals(runner=lambda *a, **k: self.fail("called"))

    def test_custom_unit_refused_without_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="pw-unit-conflict-") as temp:
            home = Path(temp)
            root = home / ".config/systemd/user"
            root.mkdir(parents=True)
            (root / "projectwright-approval-notify.timer").write_text("custom")
            values = {"TELEGRAM_BOT_TOKEN": "fixture", "TELEGRAM_ALLOWED_USERS": "111"}
            with patch.object(Path, "home", return_value=home), \
                 patch.object(timer.os, "geteuid", return_value=1000), \
                 patch("pw_notify.config_values", return_value=values):
                with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
                    timer.setup_user_approvals(runner=lambda *a, **k: self.fail("called"))
            self.assertEqual((root / "projectwright-approval-notify.timer").read_text(), "custom")


if __name__ == "__main__":
    unittest.main()
