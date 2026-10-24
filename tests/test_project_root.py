"""Configuration home selection without mutating a user's Hermes installation."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "projectwright"))
from project_queue_manager import default_project_root


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

    def test_legacy_override_and_custom_xdg(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"HERMES_PROJECT_CONFIG_DIR": tmp + "/legacy"}, clear=True):
                self.assertEqual(default_project_root(), Path(tmp) / "legacy")
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp + "/xdg"}, clear=True):
                self.assertEqual(default_project_root(), Path(tmp) / "xdg/projectwright/projects")


if __name__ == "__main__":
    unittest.main()
