"""Configuration home selection without mutating a user's Hermes installation."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "projectwright"))
from project_queue_manager import default_project_root
import pw_dispatch
import project_queue_manager as manager
import pw_notify
import types
import io
from contextlib import redirect_stdout


class ProjectRootSelection(unittest.TestCase):
    def test_xdg_default_and_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch.object(Path, "home", return_value=home), patch.dict(os.environ, {}, clear=True):
                self.assertEqual(default_project_root(), home / ".config/projectwright/projects")
                old = home / ".hermes/projects"
                old.mkdir(parents=True)
                self.assertEqual(default_project_root(), old)
                new = home / ".config/projectwright/projects"
                new.mkdir(parents=True)
                self.assertEqual(default_project_root(), new)

    def test_explicit_projectwright_overrides_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {
                "PROJECTWRIGHT_CONFIG_DIR": tmp + "/new-home",
                "HERMES_PROJECT_CONFIG_DIR": tmp + "/old-projects",
                "XDG_CONFIG_HOME": tmp + "/xdg",
            }, clear=True):
                self.assertEqual(default_project_root(), Path(tmp) / "new-home/projects")

    def test_notify_scanner_uses_projectwright_config_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            seen = []
            bridge = types.ModuleType("project_telegram_approval")
            bridge.scan = lambda root: seen.append(root)
            with patch.dict(os.environ, {"PROJECTWRIGHT_CONFIG_DIR": tmp}, clear=True), \
                 patch.dict(sys.modules, {"project_telegram_approval": bridge}), \
                 patch.object(sys, "argv", ["pw-notify"]), \
                 patch.object(pw_notify, "notify_pending", return_value=[]), \
                 redirect_stdout(io.StringIO()):
                pw_notify.main()
            self.assertEqual(seen, [Path(tmp) / "projects"])

    def test_missing_config_is_disabled_without_creating_project_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            for mode, expected_rc in (("--status", 0), ("--once", 3)):
                argv = ["pw-manager", "--project", "fixture", "--config-dir", tmp, mode]
                output = io.StringIO()
                with patch.object(sys, "argv", argv), redirect_stdout(output):
                    self.assertEqual(manager.main(), expected_rc)
                self.assertEqual(
                    __import__("json").loads(output.getvalue()),
                    {"project": "fixture", "decision": "disabled"}
                )
                self.assertFalse((Path(tmp) / "projects").exists())

    def test_dispatcher_cli_passes_custom_config_to_child_processes(self):
        with tempfile.TemporaryDirectory() as tmp:
            argv = ["pw-dispatch", "--project", "fixture", "--config-dir", tmp]
            with patch.object(sys, "argv", argv), patch.object(pw_dispatch, "run_tick", return_value=0) as run:
                with patch.dict(os.environ, {}, clear=True):
                    self.assertEqual(pw_dispatch.main(), 0)
                    self.assertEqual(os.environ["PROJECTWRIGHT_CONFIG_DIR"], tmp)
                    self.assertEqual(pw_dispatch.default_project_root(), Path(tmp) / "projects")
            run.assert_called_once()

    def test_legacy_override_and_custom_xdg(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"HERMES_PROJECT_CONFIG_DIR": tmp + "/legacy"}, clear=True):
                self.assertEqual(default_project_root(), Path(tmp) / "legacy")
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp + "/xdg"}, clear=True):
                self.assertEqual(default_project_root(), Path(tmp) / "xdg/projectwright/projects")


if __name__ == "__main__":
    unittest.main()
