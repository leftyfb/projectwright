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
            plugin = home / ".hermes/plugins/projectwright-approvals"
            self.assertTrue((plugin / "plugin.yaml").is_file())
            self.assertIn("register", (plugin / "__init__.py").read_text())
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

    def test_modified_hermes_plugin_refused_before_enabling(self):
        with tempfile.TemporaryDirectory(prefix="pw-plugin-conflict-") as temp:
            home = Path(temp)
            plugin = home / ".hermes/plugins/projectwright-approvals"
            plugin.mkdir(parents=True)
            (plugin / "plugin.yaml").write_text("custom manifest")
            values = {"TELEGRAM_BOT_TOKEN": "fixture", "TELEGRAM_ALLOWED_USERS": "111"}
            with patch.object(Path, "home", return_value=home), \
                 patch.object(timer.os, "geteuid", return_value=1000), \
                 patch("pw_notify.config_values", return_value=values):
                with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
                    timer.setup_user_approvals(
                        enable_plugin=True, runner=lambda *args, **kw: self.fail("enabled"))
            self.assertEqual((plugin / "plugin.yaml").read_text(), "custom manifest")

    def test_missing_credential_file_refuses_without_creating_units(self):
        with tempfile.TemporaryDirectory(prefix="pw-setup-missing-env-") as temp:
            home = Path(temp)
            with patch.object(Path, "home", return_value=home), \
                 patch.object(timer.os, "geteuid", return_value=1000):
                with self.assertRaisesRegex(ValueError, "Configure Telegram bot token"):
                    timer.setup_user_approvals(runner=lambda *a, **k: self.fail("called"))
            self.assertFalse((home / ".config/systemd/user").exists())
            self.assertFalse((home / ".hermes").exists())

    def test_symlinked_credential_file_refused(self):
        with tempfile.TemporaryDirectory(prefix="pw-setup-env-link-") as temp:
            home = Path(temp)
            hermes = home / ".hermes"
            hermes.mkdir()
            target = home / "test-token-file"
            target.write_text("TELEGRAM_BOT_TOKEN=fixture\\nTELEGRAM_ALLOWED_USERS=111\\n")
            (hermes / ".env").symlink_to(target)
            with patch.object(Path, "home", return_value=home), \
                 patch.object(timer.os, "geteuid", return_value=1000):
                with self.assertRaisesRegex(ValueError, "symlinked Hermes credential"):
                    timer.setup_user_approvals(runner=lambda *a, **k: self.fail("called"))
            self.assertFalse((home / ".config/systemd/user").exists())
            self.assertEqual(target.read_text(), "TELEGRAM_BOT_TOKEN=fixture\\nTELEGRAM_ALLOWED_USERS=111\\n")

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
