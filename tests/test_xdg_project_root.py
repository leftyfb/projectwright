"""Regression coverage for the default XDG project root and legacy migration."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "src" / "projectwright" / "pw_dispatch.py"
spec = importlib.util.spec_from_file_location("pw_dispatch_xdg_test", SOURCE)
dispatch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatch)


class DefaultProjectRootTests(unittest.TestCase):
    def test_new_default_when_no_existing_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(home / "xdg")}, clear=True), patch("pathlib.Path.home", return_value=home):
                self.assertEqual(dispatch.default_project_root(), home / "xdg" / "projects")

    def test_new_root_wins_over_previous_and_hermes(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            xdg = home / "xdg"
            for path in (xdg / "projects", xdg / "projectwright" / "projects", home / ".hermes" / "projects"):
                path.mkdir(parents=True)
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(xdg)}, clear=True), patch("pathlib.Path.home", return_value=home):
                self.assertEqual(dispatch.default_project_root(), xdg / "projects")

    def test_previous_xdg_root_remains_discoverable(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            xdg = home / "xdg"
            old = xdg / "projectwright" / "projects"
            old.mkdir(parents=True)
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(xdg)}, clear=True), patch("pathlib.Path.home", return_value=home):
                self.assertEqual(dispatch.default_project_root(), old)

    def test_hermes_legacy_root_remains_discoverable(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            old = home / ".hermes" / "projects"
            old.mkdir(parents=True)
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(home / "xdg")}, clear=True), patch("pathlib.Path.home", return_value=home):
                self.assertEqual(dispatch.default_project_root(), old)

    def test_explicit_config_dir_preserves_subdirectory_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch.dict(os.environ, {"PROJECTWRIGHT_CONFIG_DIR": str(home / "custom"), "XDG_CONFIG_HOME": str(home / "xdg")}, clear=True):
                self.assertEqual(dispatch.default_project_root(), home / "custom" / "projects")

    def test_legacy_environment_override_remains_direct_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch.dict(os.environ, {"HERMES_PROJECT_CONFIG_DIR": str(home / "special"), "XDG_CONFIG_HOME": str(home / "xdg")}, clear=True):
                self.assertEqual(dispatch.default_project_root(), home / "special")


if __name__ == "__main__":
    unittest.main()
