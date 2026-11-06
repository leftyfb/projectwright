"""Contract checks for the standalone, packaged Task Tracker example."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "task-tracker"
GUIDE = EXAMPLE / "README.md"
STARTER = EXAMPLE / "starter" / "README.md"
REQUIREMENTS = EXAMPLE / "requirements.md"


class TaskTrackerExampleTests(unittest.TestCase):
    def test_starter_is_unimplemented_and_safe(self):
        self.assertTrue(STARTER.is_file())
        text = STARTER.read_text(encoding="utf-8").lower()
        self.assertIn("not been implemented yet", text)
        self.assertIn("standard library", text)
        self.assertFalse((EXAMPLE / "starter" / "task_tracker.py").exists())

    def test_requirements_file_contains_two_strict_milestones(self):
        self.assertTrue(REQUIREMENTS.is_file())
        text = REQUIREMENTS.read_text(encoding="utf-8")
        self.assertGreaterEqual(len(re.findall(r"^### TRACK-1-M[0-9]+ — ", text, re.M)), 2)
        blocks = re.findall(r"#### Acceptance\n((?:- \*\*(?:Command|Scope):\*\* `[^`]+`\n)+)", text)
        self.assertEqual(len(blocks), 2)
        for block in blocks:
            self.assertEqual(len(re.findall(r"^- \*\*Command:\*\* `", block, re.M)), 1)
            self.assertGreaterEqual(len(re.findall(r"^- \*\*Scope:\*\* `", block, re.M)), 1)
            for scope in re.findall(r"^- \*\*Scope:\*\* `([^`]+)`", block, re.M):
                self.assertFalse(scope.startswith("/"))
                self.assertNotIn("..", Path(scope).parts)
                self.assertNotIn("*", scope)

    def test_walkthrough_uses_one_project_and_copies_packaged_requirements(self):
        text = GUIDE.read_text(encoding="utf-8")
        starter = STARTER.read_text(encoding="utf-8")
        self.assertIn("pw init ~/projects/task-tracker", text)
        self.assertIn("cd ~/projects/task-tracker", text)
        self.assertIn("cp /usr/share/doc/projectwright/examples/task-tracker/starter/README.md README.md", text)
        self.assertIn("cp /usr/share/doc/projectwright/examples/task-tracker/requirements.md .pw/requirements.md", text)
        self.assertIn(".pw/queue.md", text)
        self.assertIn(".pw/work_log.md", text)
        self.assertIn("task-tracker", starter)
        self.assertNotIn("pw init --project task-tracker --repo", text)
        self.assertNotIn("~/.hermes/projects/task-tracker", text)
        self.assertNotIn("paste the entire requirements block", text.lower())
        self.assertNotIn("#### Acceptance", text, "Keep the specifications in requirements.md, not README.md")
        self.assertIn("pw init PATH", (ROOT / "docs/cli.md").read_text(encoding="utf-8"))
        self.assertFalse((ROOT / "docs/embedded-projects.md").exists())
        forbidden = "task-tracker" + "-example"
        for source in ROOT.rglob("*"):
            if source.is_file() and ".git" not in source.parts and "__pycache__" not in source.parts:
                self.assertNotIn(forbidden, source.read_text(encoding="utf-8", errors="ignore"), str(source))

    def test_walkthrough_covers_approvals_and_local_only_limits(self):
        text = GUIDE.read_text(encoding="utf-8").lower()
        for phrase in (
            "pw init", "pw plan", "pw status", "pw start",
            "telegram", "one task", "standard library", "network access",
            "troubleshooting", "expected outcomes", "is not milestone approval",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertIn("do not", text)


if __name__ == "__main__":
    unittest.main()
