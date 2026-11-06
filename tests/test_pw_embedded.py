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
            repo = Path(tmp) / "task-tracker"
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
            repo = Path(tmp) / "task-tracker"
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
            repo = Path(tmp) / "task-tracker"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init", "-b", "main"], check=True, capture_output=True)
            (repo / "README.md").write_text("existing\n")
            initialize(repo)
            self.assertEqual((repo / "README.md").read_text(), "existing\n")
            with self.assertRaises(FileExistsError):
                initialize(repo)

    def test_shared_ignore_conflict_is_preflight_and_does_not_create_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "task-tracker"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init", "-b", "main"],
                           check=True, capture_output=True)
            ignore = repo / ".gitignore"
            ignore.write_text("/.pw/\n")
            with self.assertRaisesRegex(ValueError, "conflicts"):
                initialize(repo, shared=True)
            self.assertFalse((repo / ".pw").exists())
            self.assertEqual(ignore.read_text(), "/.pw/\n")

    def test_detached_head_refused_before_creating_state_or_gitignore(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "task-tracker"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init", "-b", "main"],
                           capture_output=True, check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email",
                            "test@example.invalid"], check=True)
            (repo / "README.md").write_text("source")
            subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "baseline"],
                           check=True)
            subprocess.run(["git", "-C", str(repo), "checkout", "--detach"],
                           check=True, capture_output=True)
            with self.assertRaisesRegex(ValueError, "Detached"):
                initialize(repo)
            self.assertFalse((repo / ".pw").exists())
            self.assertFalse((repo / ".gitignore").exists())

    def test_preexisting_tracked_state_is_rejected_before_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "task-tracker"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init", "-b", "main"],
                           check=True, capture_output=True)
            state = repo / ".pw/state"
            state.mkdir(parents=True)
            (state / "record.json").write_text("sensitive")
            subprocess.run(["git", "-C", str(repo), "add", ".pw/state/record.json"],
                           check=True, capture_output=True)
            (state / "record.json").unlink()
            state.rmdir()
            (repo / ".pw").rmdir()
            with self.assertRaisesRegex(ValueError, "tracks .pw"):
                initialize(repo)
            self.assertFalse((repo / ".pw").exists())

    def test_arbitrary_location_and_name_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "custom" / "task-tracker"
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


    def test_embedded_config_rejects_secrets_and_absolute_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "task-tracker"
            config = initialize(repo)
            original = json.loads(config.read_text())
            with patch.dict(os.environ, {"PROJECTWRIGHT_PROJECT_DIR": str(repo)}):
                for invalid in (
                    {**original, "provider": {"api_key": "not-allowed"}},
                    {**original, "worktree": "/tmp/unrelated"},
                    {**original, "planning": {"enabled": False,
                                                "requirements_file": "../../outside.md"}},
                ):
                    config.write_text(json.dumps(invalid))
                    with self.assertRaises(ValueError):
                        load(repo.name)
            config.write_text(json.dumps(original))

    def test_onboarding_preserves_relative_paths_and_ignores_temp_symlink(self):
        from pw_onboarding import _config, _write
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "task-tracker"
            config_path = initialize(repo)
            with patch.dict(os.environ, {"PROJECTWRIGHT_PROJECT_DIR": str(repo)}):
                raw_path, raw = _config(repo.name)
                self.assertEqual(raw_path, config_path)
                self.assertEqual(raw["worktree"], "..")
                outside = Path(tmp) / "outside"
                outside.write_text("unchanged")
                (repo / ".pw/config.json.tmp").symlink_to(outside)
                raw["execution"]["enabled"] = True
                _write(config_path, raw)
                self.assertEqual(outside.read_text(), "unchanged")
                self.assertEqual(json.loads(config_path.read_text())["worktree"], "..")
                raw["provider"] = {"api_key": "invalid"}
                config_path.write_text(json.dumps(raw))
                with self.assertRaisesRegex(ValueError, "secrets"):
                    _config(repo.name)

    def test_registered_project_lookup_refuses_duplicate_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            names = []
            for folder in ("first", "second"):
                repo = Path(tmp) / folder / "task-tracker"
                repo.parent.mkdir()
                initialize(repo)
                names.append(repo / ".pw")
            with patch("pw_embedded.registered_projects", return_value=names), \
                 patch("pw_embedded.discover", return_value=None), \
                 patch.object(Path, "home", return_value=Path(tmp)):
                from pw_embedded import directory
                with self.assertRaisesRegex(ValueError, "Ambiguous"):
                    directory("task-tracker", Path(tmp) / "projects")

if __name__ == "__main__":
    unittest.main()
