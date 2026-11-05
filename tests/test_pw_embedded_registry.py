"""Integration contracts for arbitrary embedded repositories and background identity."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import pw_embedded as embedded
from pw_buttons import callback_data
from pw_project_timer import unit_name, unit_strings
import pw_task_worker as worker


class RegistryAndSafety(unittest.TestCase):
    def test_registry_survives_move_without_mutating_project_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "first" / "task-tracker-example"
            old.parent.mkdir()
            embedded.initialize(old)
            before = (old / ".pw/config.json").read_bytes()
            registry = root / "registry.json"
            embedded.register(old, registry)
            self.assertEqual(embedded.registered_projects(registry), [old / ".pw"])
            new = root / "elsewhere" / "task-tracker-example"
            new.parent.mkdir()
            old.rename(new)
            self.assertEqual(embedded.registered_projects(registry), [])
            embedded.register(new, registry)
            self.assertEqual(embedded.registered_projects(registry), [new / ".pw"])
            self.assertEqual((new / ".pw/config.json").read_bytes(), before)

    def test_shared_clone_registration_recreates_private_runtime_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "origin" / "task-tracker-example"
            source.parent.mkdir()
            embedded.initialize(source, shared=True)
            subprocess.run(["git", "-C", str(source), "config", "user.name", "Test"],
                           check=True)
            subprocess.run(["git", "-C", str(source), "config", "user.email",
                            "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(source), "add", "."], check=True)
            subprocess.run(["git", "-C", str(source), "commit", "-qm", "shared config"],
                           check=True)
            clone = root / "elsewhere" / "task-tracker-example"
            clone.parent.mkdir()
            subprocess.run(["git", "clone", "-q", str(source), str(clone)], check=True)
            for name in ("state", "logs", "results"):
                self.assertFalse((clone / ".pw" / name).exists())
            registry = root / "registry.json"
            embedded.register(clone, registry)
            for name in ("state", "logs", "results"):
                folder = clone / ".pw" / name
                self.assertTrue(folder.is_dir())
                self.assertEqual(folder.stat().st_mode & 0o777, 0o700)
            self.assertEqual(embedded.registered_projects(registry), [clone / ".pw"])
            self.assertEqual(subprocess.check_output(
                ["git", "-C", str(clone), "status", "--porcelain=v1"],
                text=True).strip(), "")

    def test_duplicate_names_do_not_cross_route_callback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "registry.json"
            markers = []
            for parent in ("one", "two"):
                repo = root / parent / "task-tracker-example"
                repo.parent.mkdir()
                embedded.initialize(repo)
                embedded.register(repo, registry)
                markers.append(repo / ".pw")
            record = {"project": "task-tracker-example", "head": "a" * 40}
            rid = hashlib.sha256(json.dumps(record, sort_keys=True,
                separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()[:20]
            (markers[0] / "telegram_approval_pending.json").write_text(json.dumps(record))
            with patch.object(embedded, "registry_path", return_value=registry):
                self.assertEqual(embedded.callback_project(root / "legacy", "task-tracker-example", rid), markers[0])
                (markers[1] / "telegram_approval_pending.json").write_text(json.dumps(record))
                with self.assertRaisesRegex(ValueError, "ambiguous"):
                    embedded.callback_project(root / "legacy", "task-tracker-example", rid)

    def test_timers_bind_unique_repo_and_remain_inert(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "one/task-tracker-example"
            second = Path(tmp) / "two/task-tracker-example"
            self.assertNotEqual(unit_name("task-tracker-example", first),
                                unit_name("task-tracker-example", second))
            service, timer = unit_strings("task-tracker-example", 20, Path("/usr/bin/pw_dispatch.py"), repo=first)
            self.assertIn("PROJECTWRIGHT_PROJECT_DIR=", service)
            self.assertIn(str(first.resolve()), service)
            self.assertNotIn("WantedBy=", service)
            self.assertIn("WantedBy=timers.target", timer)
            self.assertNotIn("OnCalendar=", timer)

    def test_systemd_escapes_paths_with_spaces_and_specifiers(self):
        from pw_project_timer import _systemd_argument, approval_notify_units
        script = Path("/opt/project wright/dispatcher%demo.py")
        service, _ = unit_strings("task-tracker-example", 20, script,
                                  repo=Path("/home/fixture/projects with spaces/task-tracker-example"))
        self.assertIn('"/opt/project wright/dispatcher%%demo.py"', service)
        self.assertIn("PROJECTWRIGHT_PROJECT_DIR=", service)
        self.assertIn("projects with spaces", service)
        self.assertIn("ExecStart=/usr/bin/python3 -B ", service)
        notifier_service, _ = approval_notify_units(Path("/opt/project wright/notifier.py"))
        self.assertIn('"/opt/project wright/notifier.py"', notifier_service)
        with self.assertRaises(ValueError):
            _systemd_argument("/tmp/script\nExecStart=/bin/false")

    def test_existing_embedded_timer_content_must_match_before_enable(self):
        import os
        import sys
        import pw_project_timer as timer
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            repo = home / "other" / "task-tracker-example"
            repo.parent.mkdir()
            embedded.initialize(repo)
            unit = unit_name(repo.name, repo)
            dest = home / ".config/systemd/user"
            dest.mkdir(parents=True)
            (dest / (unit + ".service")).write_text(
                '[Service]\nExecStart=/bin/false\n')
            _, valid_timer = unit_strings(repo.name, 30, Path(timer.__file__).resolve().parent / "pw_dispatch.py", repo=repo)
            (dest / (unit + ".timer")).write_text(valid_timer)
            args = ["pw_project_timer.py", "enable", repo.name]
            with patch.object(timer.Path, "home", return_value=home), \
                 patch.object(sys, "argv", args), \
                 patch.dict(os.environ, {"PROJECTWRIGHT_PROJECT_DIR": str(repo)}), \
                 patch.object(timer.subprocess, "run") as runner:
                with self.assertRaisesRegex(ValueError, "differ"):
                    timer.main()
                runner.assert_not_called()

    def test_embedded_custom_interval_can_enable_and_disable_by_project_name(self):
        import os
        import sys
        import pw_project_timer as timer
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            repo = home / "outside" / "task-tracker-example"
            repo.parent.mkdir()
            embedded.initialize(repo)
            unit = unit_name(repo.name, repo)
            dest = home / ".config/systemd/user"
            dest.mkdir(parents=True)
            script = Path(timer.__file__).resolve().parent / "pw_dispatch.py"
            service, scheduled = unit_strings(repo.name, 15, script, repo=repo)
            (dest / (unit + ".service")).write_text(service)
            (dest / (unit + ".timer")).write_text(scheduled)
            with patch.object(timer.Path, "home", return_value=home), \
                 patch.dict(os.environ, {"PROJECTWRIGHT_PROJECT_DIR": str(repo)}), \
                 patch.object(timer.subprocess, "run") as runner:
                with patch.object(sys, "argv", ["pw_project_timer.py", "enable", repo.name]):
                    self.assertEqual(timer.main(), 0)
                    self.assertIn("enable", runner.call_args.args[0])
                (dest / (unit + ".service")).write_text("unsafe modified service\n")
                with patch.object(sys, "argv", ["pw_project_timer.py", "disable", repo.name]):
                    self.assertEqual(timer.main(), 0)
                    self.assertIn("disable", runner.call_args.args[0])

    def test_symlinked_embedded_timer_units_fail_closed(self):
        import os
        import sys
        import pw_project_timer as timer
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            repo = home / "other" / "task-tracker-example"
            repo.parent.mkdir()
            embedded.initialize(repo)
            unit = unit_name(repo.name, repo)
            dest = home / ".config/systemd/user"
            dest.mkdir(parents=True)
            (dest / (unit + ".service")).symlink_to(home / "elsewhere")
            args = ["pw_project_timer.py", "enable", repo.name]
            with patch.object(timer.Path, "home", return_value=home), \
                 patch.object(sys, "argv", args), \
                 patch.dict(os.environ, {"PROJECTWRIGHT_PROJECT_DIR": str(repo)}), \
                 patch.object(timer.subprocess, "run") as runner:
                with self.assertRaisesRegex(ValueError, "symlinked"):
                    timer.main()
                runner.assert_not_called()

    def test_git_runtime_state_must_not_be_in_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "task-tracker-example"
            embedded.initialize(repo)
            secret = repo / ".pw/state/worker.lock"
            secret.write_text("not for Git")
            subprocess.run(["git", "-C", str(repo), "add", "-f", ".pw/state/worker.lock"],
                           check=True, capture_output=True)
            with patch.object(worker, "PROJECT", {"layout": "embedded"}), \
                 patch.object(worker, "WORKTREE", repo):
                with self.assertRaisesRegex(RuntimeError, "Operational"):
                    worker._ensure_embedded_git_safe()

    def test_nested_repo_destination_is_refused_without_creating_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            outer = Path(tmp) / "outer"
            embedded.initialize(outer)
            nested = outer / "nested"
            with self.assertRaisesRegex(ValueError, "repository root"):
                embedded.initialize(nested)
            self.assertFalse(nested.exists())


if __name__ == "__main__":
    unittest.main()
