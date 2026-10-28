"""Release-to-APT automation must retain a trusted, limited trigger."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReleaseAutomationContract(unittest.TestCase):
    def test_apt_signing_follows_successful_release_publisher_only(self):
        workflow = (ROOT / ".github/workflows/publish-apt.yml").read_text()
        self.assertIn("workflow_run:", workflow)
        self.assertIn("workflows: ['Publish Projectwright release']", workflow)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", workflow)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", workflow)
        self.assertIn("github.event.workflow_run.event == 'workflow_dispatch'", workflow)
        self.assertIn("github.repository == 'leftyfb/projectwright'", workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn('test "$CONFIRMATION" = publish-apt', workflow)
        self.assertIn("secrets.APT_SIGNING_KEY_B64", workflow)
        self.assertIn("scripts/build-apt-repository.py", workflow)

    def test_stable_release_publication_remains_explicit_and_verified(self):
        workflow = (ROOT / ".github/workflows/publish-release.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("'head_sha':os.environ['SOURCE_SHA']", workflow)
        self.assertIn("'conclusion':'success'", workflow)
        self.assertIn("sha256sum -c SHA256SUMS", workflow)
        self.assertIn("gh release create", workflow)


if __name__ == "__main__":
    unittest.main()
