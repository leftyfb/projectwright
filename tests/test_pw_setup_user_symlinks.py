"""User onboarding must never follow pre-existing symlinked managed files."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

SRC=Path(__file__).resolve().parents[1]/"src"/"projectwright"
sys.path.insert(0,str(SRC))
import pw_project_timer as timer

class SetupUserSymlinkSafety(unittest.TestCase):
    def test_symlinked_unit_is_refused_before_any_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)
            unit=home/".config/systemd/user/projectwright-approval-notify.timer"
            unit.parent.mkdir(parents=True)
            outside=home/"outside"
            outside.write_text("untouched")
            unit.symlink_to(outside)
            with patch.object(timer.os,"geteuid",return_value=1000), \
                 patch.object(timer.Path,"home",return_value=home), \
                 patch("pw_notify.config_values",return_value={"TELEGRAM_BOT_TOKEN":"fixture","TELEGRAM_ALLOWED_USERS":"123"}), \
                 patch("pw_notify.parse_allowed_users",return_value={"123"}):
                calls=[]
                with self.assertRaisesRegex(ValueError,"symlinked user unit"):
                    timer.setup_user_approvals(runner=lambda *a,**kw:calls.append(a))
            self.assertEqual(calls,[])
            self.assertEqual(outside.read_text(),"untouched")

    def test_symlinked_plugin_is_refused_before_enabling(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)
            plugin=home/".hermes/plugins/projectwright-approvals"
            plugin.mkdir(parents=True)
            outside=home/"outside"
            outside.write_text("untouched")
            (plugin/"plugin.yaml").symlink_to(outside)
            with patch.object(timer.os,"geteuid",return_value=1000), \
                 patch.object(timer.Path,"home",return_value=home), \
                 patch("pw_notify.config_values",return_value={"TELEGRAM_BOT_TOKEN":"fixture","TELEGRAM_ALLOWED_USERS":"123"}), \
                 patch("pw_notify.parse_allowed_users",return_value={"123"}):
                calls=[]
                with self.assertRaisesRegex(ValueError,"symlinked Hermes plugin"):
                    timer.setup_user_approvals(enable_plugin=True,runner=lambda *a,**kw:calls.append(a))
            self.assertEqual(calls,[])
            self.assertEqual(outside.read_text(),"untouched")

if __name__=="__main__":
    unittest.main()
