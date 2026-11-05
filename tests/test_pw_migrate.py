"""Legacy project migration is explicit, dry-run first and non-destructive."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from pw_migrate import inspect, migrate


class MigrationTests(unittest.TestCase):
    def make_legacy(self, base: Path):
        repo = base / "repo" / "task-tracker-example"
        repo.mkdir(parents=True)
        subprocess.run(["git", "-C", str(repo), "init", "-b", "main"],
                       capture_output=True, check=True)
        (repo / "README.md").write_text("# Work\n")
        subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=test@example.invalid",
                        "-c", "user.name=Test", "commit", "-m", "baseline"],
                       capture_output=True, check=True)
        root = base / "legacy-projects"
        state = root / "task-tracker-example"
        state.mkdir(parents=True)
        original = {
            "id": "task-tracker-example",
            "worktree": str(repo),
            "branch": "main",
            "planning": {"enabled": True},
            "execution": {"enabled": True},
        }
        (state / "config.json").write_text(json.dumps(original))
        (state / "queue.md").write_text("- [ ] **T1 — READ** fixture\n")
        (state / "work_log.md").write_text("prior progress\n")
        (state / "requirements.md").write_text("requirements\n")
        return repo, root, state

    def test_dry_run_does_not_touch_worktree_or_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, root, state = self.make_legacy(Path(tmp))
            before = (state / "config.json").read_bytes()
            report = migrate("task-tracker-example", root, repo)
            self.assertEqual(report["decision"], "dry_run")
            self.assertFalse((repo / ".pw").exists())
            self.assertFalse((repo / ".gitignore").exists())
            self.assertEqual((state / "config.json").read_bytes(), before)

    def test_explicit_copy_is_disabled_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, root, state = self.make_legacy(Path(tmp))
            prior = {p.name: p.read_bytes() for p in state.iterdir()}
            registry = Path(tmp) / "external" / "registry.json"
            with patch("pw_embedded.registry_path", return_value=registry), \
                 patch("pw_migrate.register", side_effect=lambda repo: __import__("pw_embedded").register(repo, registry)):
                result = migrate("task-tracker-example", root, repo, apply=True)
            self.assertEqual(result["decision"], "copied_disabled")
            cfg = json.loads((repo / ".pw/config.json").read_text())
            self.assertEqual(cfg["worktree"], "..")
            self.assertFalse(cfg["execution"]["enabled"])
            self.assertFalse(cfg["planning"]["enabled"])
            self.assertEqual((repo / ".pw/work_log.md").read_text(), "prior progress\n")
            self.assertIn("/.pw/", (repo / ".gitignore").read_text())
            self.assertEqual(prior, {p.name: p.read_bytes() for p in state.iterdir()})
            self.assertTrue(registry.exists())

    def test_pending_approval_blocks_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, root, state = self.make_legacy(Path(tmp))
            (state / "telegram_approval_pending.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "Pending Telegram"):
                migrate("task-tracker-example", root, repo, apply=True)
            self.assertFalse((repo / ".pw").exists())

    def test_credentials_in_config_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, root, state = self.make_legacy(Path(tmp))
            cfg = json.loads((state / "config.json").read_text())
            cfg["provider"] = {"api_key": "do-not-copy"}
            (state / "config.json").write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError, "credential"):
                inspect("task-tracker-example", root, repo)

    def test_dirty_target_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, root, _state = self.make_legacy(Path(tmp))
            (repo / "untracked.txt").write_text("dirty")
            with self.assertRaisesRegex(ValueError, "clean"):
                migrate("task-tracker-example", root, repo, apply=True)


if __name__ == "__main__":
    unittest.main()
