"""Embedded repository layout contracts (no Hermes or network required)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from pw_embedded import discover, initialize
from pw_config import load


class EmbeddedLayoutTests(unittest.TestCase):
    def test_new_repository_inert_and_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "task-tracker-example"
            config_path = initialize(repo)
            self.assertEqual(config_path, repo / ".pw/config.json")
            self.assertTrue((repo / ".git").exists())
            self.assertEqual((repo / ".gitignore").read_text(), "/.pw/\n")
            cfg = json.loads(config_path.read_text())
            self.assertEqual(cfg["worktree"], "..")
            self.assertFalse(cfg["execution"]["enabled"])
            self.assertFalse(cfg["planning"]["enabled"])
            self.assertEqual(cfg["id"], repo.name)
            with patch.dict(os.environ, {"PROJECTWRIGHT_PROJECT_DIR": str(repo)}):
                path, resolved = load(repo.name)
            self.assertEqual(path, config_path)
            self.assertEqual(resolved["worktree"], str(repo.resolve()))
            self.assertEqual(resolved["queue"], str(repo / ".pw/queue.md"))
            self.assertIn("github.com/leftyfb/projectwright", (repo / ".pw/README.md").read_text())
            self.assertEqual(discover(repo / ".pw" / "results"), repo / ".pw")

    def test_shared_mode_excludes_operational_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "task-tracker-example"
            initialize(repo, shared=True)
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            files = subprocess.check_output(
                ["git", "-C", str(repo), "ls-files"], text=True).splitlines()
            self.assertIn(".pw/config.json", files)
            self.assertIn(".pw/requirements.md", files)
            self.assertNotIn(".pw/state/worker.lock", files)
            (repo / ".pw/state/worker.lock").write_text("private")
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            files = subprocess.check_output(
                ["git", "-C", str(repo), "ls-files"], text=True).splitlines()
            self.assertNotIn(".pw/state/worker.lock", files)

    def test_existing_repository_and_duplicate_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "task-tracker-example"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init", "-b", "main"], check=True, capture_output=True)
            (repo / "README.md").write_text("existing\n")
            initialize(repo)
            self.assertEqual((repo / "README.md").read_text(), "existing\n")
            with self.assertRaises(FileExistsError):
                initialize(repo)

    def test_arbitrary_location_and_name_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "custom" / "task-tracker-example"
            initialize(repo)
            self.assertEqual(discover(repo), repo / ".pw")
            with patch.dict(os.environ, {"PROJECTWRIGHT_PROJECT_DIR": str(repo)}):
                with self.assertRaises(ValueError):
                    load("different")

    def test_no_cross_repository_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            outer = Path(tmp) / "outer"
            initialize(outer)
            inner = outer / "nested"
            inner.mkdir()
            subprocess.run(["git", "-C", str(inner), "init", "-b", "main"], check=True, capture_output=True)
            self.assertIsNone(discover(inner))


if __name__ == "__main__":
    unittest.main()
