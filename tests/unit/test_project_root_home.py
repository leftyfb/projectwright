"""Projectwright state defaults to ~/projects, never an existing legacy root."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pw_dispatch import default_project_root


class ProjectRootHomeTests(unittest.TestCase):
    def test_home_projects_is_default_even_with_legacy_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".config/projects").mkdir(parents=True)
            (home / ".config/projectwright/projects").mkdir(parents=True)
            (home / ".hermes/projects").mkdir(parents=True)
            with patch("pathlib.Path.home", return_value=home), patch.dict(
                "os.environ",
                {"HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config")},
                clear=True,
            ):
                self.assertEqual(default_project_root(), home / "projects")

    def test_explicit_direct_root_override_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            legacy = home / ".hermes" / "projects"
            with patch("pathlib.Path.home", return_value=home), patch.dict(
                "os.environ",
                {"HOME": str(home), "HERMES_PROJECT_CONFIG_DIR": str(legacy)},
                clear=True,
            ):
                self.assertEqual(default_project_root(), legacy)

    def test_explicit_configuration_home_override_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch("pathlib.Path.home", return_value=home), patch.dict(
                "os.environ",
                {"HOME": str(home), "PROJECTWRIGHT_CONFIG_DIR": str(home / "custom")},
                clear=True,
            ):
                self.assertEqual(default_project_root(), home / "custom" / "projects")


if __name__ == "__main__":
    unittest.main()
