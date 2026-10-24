"""Regression coverage for Projectwright config-home selection.

These tests use temporary paths and never inspect a real Hermes installation.
"""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "projectwright" / "pw_dispatch.py"
spec = importlib.util.spec_from_file_location("pw_dispatch_config_test", MODULE_PATH)
dispatch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatch)


class ProjectRootSelectionTests(unittest.TestCase):
    def test_xdg_default_when_no_legacy_root_exists(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            home.mkdir()
            xdg = Path(td) / "xdg"
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(xdg)}, clear=True):
                with mock.patch.object(Path, "home", return_value=home):
                    self.assertEqual(dispatch.default_project_root(), xdg / "projectwright" / "projects")

    def test_explicit_projectwright_home_beats_legacy(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            (home / ".hermes" / "projects").mkdir(parents=True)
            custom = Path(td) / "config"
            with mock.patch.dict(os.environ, {
                "PROJECTWRIGHT_CONFIG_DIR": str(custom),
                "HERMES_PROJECT_CONFIG_DIR": str(home / ".hermes" / "projects"),
            }, clear=True):
                with mock.patch.object(Path, "home", return_value=home):
                    self.assertEqual(dispatch.default_project_root(), custom / "projects")

    def test_legacy_root_fallback_without_xdg_projects(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            legacy = home / ".hermes" / "projects"
            legacy.mkdir(parents=True)
            with mock.patch.dict(os.environ, {}, clear=True):
                with mock.patch.object(Path, "home", return_value=home):
                    self.assertEqual(dispatch.default_project_root(), legacy)

    def test_xdg_root_preferred_when_it_exists(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            (home / ".hermes" / "projects").mkdir(parents=True)
            xdg = Path(td) / "xdg"
            root = xdg / "projectwright" / "projects"
            root.mkdir(parents=True)
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(xdg)}, clear=True):
                with mock.patch.object(Path, "home", return_value=home):
                    self.assertEqual(dispatch.default_project_root(), root)


if __name__ == "__main__":
    unittest.main()
