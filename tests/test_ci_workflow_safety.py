"""Keep public-branch CI on GitHub-hosted runners only."""
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO / ".github" / "workflows"

RETIRED_SELF_HOSTED = (
    "pw-test-cli-smoke.yml",
    "pw-test-deb-staging.yml",
    "pw-test-install-purge.yml",
    "pw-test-live-approval.yml",
    "pw-test-live-cleanup.yml",
    "pw-test-preflight.yml",
    "pw-test-send-approval.yml",
    "pw-test-source-upgrade.yml",
    "pw-test-verify-approval.yml",
    "tux-isolated.yml",
)


class TestWorkflowSideEffects(unittest.TestCase):
    def test_legacy_self_hosted_workflows_are_not_active(self):
        for name in RETIRED_SELF_HOSTED:
            with self.subTest(workflow=name):
                self.assertFalse((WORKFLOWS / name).exists())

    def test_active_workflows_use_only_hosted_runner_labels(self):
        workflows = tuple(WORKFLOWS.glob("*.yml"))
        self.assertTrue(workflows)
        for path in workflows:
            with self.subTest(workflow=path.name):
                text = path.read_text()
                lines = (line.strip() for line in text.splitlines())
                runners = [line for line in lines if line.startswith("runs-on:")]
                self.assertTrue(runners)
                for line in runners:
                    self.assertNotIn("self-hosted", line)
                    self.assertNotIn("pw-test", line)
                    self.assertIn("ubuntu-", line)


if __name__ == "__main__":
    unittest.main()
