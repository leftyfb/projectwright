"""Prevent accidental self-hosted runner use in the public repository."""
from pathlib import Path
import unittest

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


class PublicWorkflowSafetyTests(unittest.TestCase):
    def test_active_workflows_are_hosted_only(self):
        paths = tuple(WORKFLOWS.glob("*.yml"))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(workflow=path.name):
                lines = path.read_text().splitlines()
                runner_lines = [line.strip() for line in lines
                                if line.strip().startswith("runs-on:")]
                self.assertTrue(runner_lines)
                for runner in runner_lines:
                    self.assertIn("ubuntu-", runner)
                    self.assertNotIn("self-hosted", runner)

    def test_no_live_test_triggers(self):
        for path in WORKFLOWS.glob("*.yml"):
            with self.subTest(workflow=path.name):
                text = path.read_text()
                self.assertNotIn("runs-on: [self-hosted", text)
                self.assertNotIn("telegram/sendMessage", text)


if __name__ == "__main__":
    unittest.main()
