"""Notifier scans only managed projects and can target one project."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[2] / "src" / "projectwright"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pw_notify
import pw_telegram_approval as approval


class NotifierProjectScopeTests(unittest.TestCase):
    def test_scan_skips_unmanaged_directories(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "source-checkout").mkdir()
            managed = root / "demo"
            managed.mkdir()
            (managed / "config.json").write_text('{"id":"demo"}')
            with patch.object(approval, "project_data", return_value=({"planning": {"enabled": False}}, None)) as data:
                self.assertEqual(approval.scan(root), [])
            data.assert_called_once_with(managed)

    def test_scoped_scan_does_not_inspect_other_projects(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            other = root / "other"
            other.mkdir()
            (other / "config.json").write_text('{"id":"other"}')
            target = root / "demo"
            target.mkdir()
            (target / "config.json").write_text('{"id":"demo"}')
            with patch.object(approval, "project_data", return_value=({"planning": {"enabled": False}}, None)) as data:
                self.assertEqual(approval.scan(root, project="demo"), [])
            data.assert_called_once_with(target)

    def test_minimal_init_config_resolves_effective_paths(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project = root / "demo"
            project.mkdir()
            (project / "config.json").write_text('{"id":"demo","planning":{"enabled":true}}')
            cfg, policy = approval.project_data(project)
            self.assertEqual(cfg["lock"], str(project / "worker.lock"))
            self.assertEqual(cfg["queue"], str(project / "queue.md"))
            self.assertTrue(cfg["planning"]["enabled"])

    def test_notify_project_option_scopes_both_scan_and_pending(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project = root / "demo"
            project.mkdir()
            (project / "config.json").write_text('{"id":"demo"}')
            with (
                patch.object(sys, "argv", ["pw-notify", "--root", td, "--project", "demo"]),
                patch("project_telegram_approval.scan") as scan,
                patch.object(pw_notify, "notify_pending", return_value=["PREVIEW demo / DEMO-1-M1"]) as notify,
                patch("builtins.print") as printed,
            ):
                pw_notify.main()
            scan.assert_called_once_with(root, project="demo")
            notify.assert_called_once_with(root, dry_run=True, project="demo")
            printed.assert_called_once_with("PREVIEW demo / DEMO-1-M1")

    def test_explicit_milestone_resolves_ambiguity_without_automatic_selection(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = root / "demo"
            target.mkdir()
            (target / "config.json").write_text('{"id":"demo"}')
            cfg = {"planning": {"enabled": True}, "lock": str(target / "worker.lock")}
            policy = {"version": 1, "milestones": {
                "DEMO-1-M1": {"requirement": "DEMO-1"},
                "DEMO-1-M2": {"requirement": "DEMO-1"},
            }}
            def record(_directory, _cfg, milestone, _spec):
                return {"project": "demo", "milestone": milestone}
            with (
                patch.object(approval, "project_data", return_value=(cfg, policy)),
                patch.object(approval, "evidence", side_effect=record),
            ):
                self.assertEqual(approval.scan(root, project="demo"), [])
                self.assertFalse((target / "telegram_approval_pending.json").exists())
                selected = approval.scan(root, project="demo", milestone="DEMO-1-M1")
                self.assertEqual(len(selected), 1)
                self.assertEqual(selected[0]["milestone"], "DEMO-1-M1")
                self.assertEqual(
                    json.loads((target / "telegram_approval_pending.json").read_text())["milestone"],
                    "DEMO-1-M1",
                )
                with self.assertRaisesRegex(ValueError, "No acceptance policy"):
                    approval.scan(root, project="demo", milestone="DEMO-1-M3")

    def test_cli_milestone_requires_project_and_targets_only_selected_milestone(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = root / "demo"
            target.mkdir()
            (target / "config.json").write_text('{"id":"demo"}')
            with (
                patch.object(sys, "argv", ["pw-notify", "--root", td, "--project", "demo",
                                          "--milestone", "DEMO-1-M1"]),
                patch("project_telegram_approval.scan") as scan,
                patch.object(pw_notify, "notify_pending", return_value=["PREVIEW demo / DEMO-1-M1"]) as notify,
                patch("builtins.print"),
            ):
                pw_notify.main()
            scan.assert_called_once_with(root, project="demo", milestone="DEMO-1-M1")
            notify.assert_called_once_with(root, dry_run=True, project="demo")
            with patch.object(sys, "argv", ["pw-notify", "--root", td,
                                            "--milestone", "DEMO-1-M1"]):
                with self.assertRaises(SystemExit) as error:
                    pw_notify.main()
            self.assertEqual(error.exception.code, 2)

    def test_non_project_option_does_not_allow_inert_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "demo").mkdir()
            with patch.object(sys, "argv", ["pw-notify", "--root", td, "--project", "demo"]):
                with self.assertRaises(SystemExit) as exit_info:
                    pw_notify.main()
            self.assertEqual(exit_info.exception.code, 2)

    def test_scoped_pending_filters_other_project_records(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ("demo", "other"):
                project = root / name
                project.mkdir()
                (project / "telegram_approval_pending.json").write_text(json.dumps({"project": name}))
            found = approval.load_pending(root, project="demo")
            self.assertEqual([directory.name for directory, _ in found], ["demo"])


if __name__ == "__main__":
    unittest.main()
