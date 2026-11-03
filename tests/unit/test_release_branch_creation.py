"""Regression checks for the maintainer release branch preparation flow."""
import importlib.util
from pathlib import Path
from unittest import TestCase, mock
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "release.py"
SPEC = importlib.util.spec_from_file_location("projectwright_release_script", SCRIPT)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)
SHA = "a" * 40


class ReleaseBranchTests(TestCase):
    def test_preflight_accepts_clean_synced_main_with_unused_version(self):
        def output(*args):
            values = {
                ("git", "branch", "--show-current"): "main",
                ("gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"): release.REPO,
                ("git", "rev-parse", "HEAD"): SHA,
                ("git", "ls-remote", "origin", "refs/heads/main"): SHA + "\trefs/heads/main",
                ("git", "ls-remote", "--heads", "origin", "refs/heads/release/0.1.6"): "",
                ("git", "ls-remote", "--tags", "origin", "refs/tags/0.1.6"): "",
            }
            return values[args]

        def command(*args, check=True):
            return mock.Mock(returncode=1 if "show-ref" in args or args[:3] == ("gh", "release", "view") else 0, stdout="")

        with mock.patch.object(release, "output", side_effect=output), mock.patch.object(release, "command", side_effect=command):
            self.assertEqual(release.require_release_preflight("0.1.6"), ("release/0.1.6", SHA))

    def test_preflight_rejects_existing_remote_branch(self):
        with mock.patch.object(release, "output") as output, mock.patch.object(release, "command") as command:
            output.side_effect = ["main", release.REPO, SHA, SHA, SHA]
            command.return_value = mock.Mock(returncode=1, stdout="")
            with self.assertRaisesRegex(release.ReleaseError, "Remote branch"):
                release.require_release_preflight("0.1.6")

    def test_branch_created_and_pushed_without_force(self):
        with mock.patch.object(release, "output", side_effect=[
            SHA, "main", SHA, "", SHA
        ]), mock.patch.object(release, "command", return_value=mock.Mock(stdout="")) as cmd:
            release.create_release_branch("release/0.1.6", SHA)
            self.assertIn(mock.call("git", "switch", "-c", "release/0.1.6"), cmd.call_args_list)
            self.assertIn(mock.call("git", "push", "-u", "origin", "release/0.1.6"), cmd.call_args_list)
            self.assertFalse(any("--force" in repr(c) for c in cmd.call_args_list))

    def test_declined_confirmation_never_creates_branch(self):
        with mock.patch.object(release, "require_release_preflight", return_value=("release/0.1.6", SHA)), \
             mock.patch.object(release, "proposed_files", return_value={release.ROOT / "docs/release-notes.md": "Notes"}), \
             mock.patch.object(release, "create_release_branch") as branch, \
             mock.patch("builtins.input", return_value="n"), \
             mock.patch.object(release.sys.stdin, "isatty", return_value=True):
            self.assertEqual(release.main(["0.1.6"]), 1)
            branch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
