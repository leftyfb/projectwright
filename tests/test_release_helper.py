"""Guarded maintainer release helper tests (no network, git push, or Actions)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "release.py"
spec = importlib.util.spec_from_file_location("release_helper", SCRIPT)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseHelperTests(unittest.TestCase):
    def test_prepares_version_metadata_and_package_filenames(self):
        with tempfile.TemporaryDirectory(prefix="pw-release-helper-") as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "docs").mkdir()
            (root / "pyproject.toml").write_text(
                '[project]\nname = "projectwright"\n'
                'version = "0.1.0.dev0"\n'
                'description = "Project task orchestration (development preview)"\n'
            )
            (root / "scripts/build-deb.sh").write_text(
                "# Build an uninstalled Debian preview\n"
                "Version: 0.1.0~dev0-1\n"
                "Description: Development preview of project task orchestration\n"
                " A pre-release packaging checkpoint for Projectwright. External agent\n"
                " services and project configuration are not provisioned by this package.\n"
                "projectwright_0.1.0~dev0-1_all.deb\n"
                "projectwright_0.1.0~dev0-1_all.deb\n"
            )
            with patch.object(release, "ROOT", root), \
                 patch.object(release, "generated_notes", return_value="# Approved\n"):
                changes = release.proposed_files("0.1.2", None)
            self.assertIn('version = "0.1.2"', changes[root / "pyproject.toml"])
            self.assertIn("Version: 0.1.2-1", changes[root / "scripts/build-deb.sh"])
            self.assertEqual(changes[root / "scripts/build-deb.sh"].count(
                "projectwright_0.1.2-1_all.deb"), 2)
            self.assertIn("Hermes-based project task orchestration",
                          changes[root / "scripts/build-deb.sh"])
            self.assertEqual(changes[root / "docs/release-notes.md"], "# Approved\n")
            self.assertIn("0.1.0~dev0-1",
                          (root / "scripts/build-deb.sh").read_text(),
                          "Preparation must not edit files until confirmation")

    def test_rejects_unexpected_debian_version_inventory(self):
        with tempfile.TemporaryDirectory(prefix="pw-release-bad-") as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "pyproject.toml").write_text('version = "0.1.0.dev0"\n')
            (root / "scripts/build-deb.sh").write_text("Version: 0.1.0-1\n")
            with patch.object(release, "ROOT", root):
                with self.assertRaisesRegex(release.ReleaseError, "Debian filename"):
                    release.proposed_files("0.1.2", None)

    def test_confirmation_refuses_non_version_and_unreviewed_branch(self):
        with patch.object(release, "require_clean_release_branch",
                          side_effect=release.ReleaseError("wrong branch")):
            self.assertEqual(release.main(["0.1.2", "--yes"]), 1)
        with self.assertRaises(SystemExit):
            release.main(["v0.1.2", "--yes"])

    def test_dispatch_uses_explicit_workflow_and_ref(self):
        with patch.object(release, "output",
                          return_value="https://github.com/leftyfb/projectwright/actions/runs/12345") as called:
            self.assertEqual(release.dispatch_run("publish-release.yml", "main", "a" * 40,
                                                 ("-f", "version=0.1.2")), 12345)
        args = called.call_args.args
        self.assertEqual(args[:3], ("gh", "workflow", "run"))
        self.assertIn("--ref", args)
        self.assertIn("main", args)


if __name__ == "__main__":
    unittest.main()
