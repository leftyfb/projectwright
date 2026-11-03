"""Lightweight contract checks for the documented task-tracker starter."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "task_tracker"
GUIDE = EXAMPLE / "README.md"
STARTER = EXAMPLE / "starter" / "README.md"


class TaskTrackerExampleTests(unittest.TestCase):
    def test_starter_is_unimplemented_and_safe(self):
        self.assertTrue(STARTER.is_file())
        text = STARTER.read_text(encoding="utf-8").lower()
        self.assertIn("not been implemented yet", text)
        self.assertIn("standard library", text)
        self.assertFalse((EXAMPLE / "starter" / "task_tracker.py").exists())

    def test_walkthrough_documents_two_strict_milestones(self):
        text = GUIDE.read_text(encoding="utf-8")
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

    def test_walkthrough_covers_gates_and_local_only_limits(self):
        text = GUIDE.read_text(encoding="utf-8").lower()
        for phrase in (
            "pw init", "pw plan", "pw status", "pw start",
            "human acceptance", "telegram", "one-shot", "standard library",
            "network access", "troubleshooting", "expected outcomes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertIn("do not", text)
        self.assertIn("is not milestone approval", text)


if __name__ == "__main__":
    unittest.main()
