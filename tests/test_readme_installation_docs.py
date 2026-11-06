"""Documentation boundary: end users must not need maintainer setup guides."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReadmeInstallationTests(unittest.TestCase):
    def test_readme_includes_complete_signed_apt_setup(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for command in (
            "curl -fsSL https://leftyfb.github.io/projectwright/projectwright-archive-keyring.gpg",
            "gpg --show-keys --with-fingerprint",
            "sudo install -m 0644",
            "/usr/share/keyrings/projectwright-archive-keyring.gpg",
            "/etc/apt/sources.list.d/projectwright.list",
            "sudo apt update",
            "sudo apt install projectwright",
            "pw setup",
        ):
            with self.subTest(command=command):
                self.assertIn(command, readme)
        self.assertIn("fingerprint", readme)

    def test_publisher_procedures_are_maintainer_only(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        maintainer = (ROOT / "docs/maintainer/README.md").read_text(encoding="utf-8")
        signing = (ROOT / "docs/maintainer/apt-publishing.md").read_text(encoding="utf-8")
        self.assertNotIn("APT_SIGNING_KEY_B64", readme)
        self.assertNotIn("gpg --quick-generate-key", readme)
        self.assertNotIn("apt-repository.md", readme)
        self.assertFalse((ROOT / "docs/apt-repository.md").exists())
        self.assertIn("apt-publishing.md", maintainer)
        self.assertIn("APT_SIGNING_KEY_B64", signing)


if __name__ == "__main__":
    unittest.main()
