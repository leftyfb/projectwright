"""Configuration CLI: typed values, embedded-path guards and fail-closed writes."""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / "src" / "projectwright"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pw_settings as settings


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "task-tracker"
        from pw_embedded import initialize
        self.path = initialize(self.repo)
        self.env = patch.dict(os.environ, {
            "PROJECTWRIGHT_PROJECT_DIR": str(self.repo),
        }, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def run_action(self, action, key=None, raw=None, yes=False):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            settings.operate(action, "task-tracker", key, raw, yes=yes)
        return output.getvalue()

    def test_strict_milestone_toggle_and_readback(self):
        self.assertEqual(self.run_action("get", "planning.milestone_sequence").strip(), '"off"')
        self.run_action("set", "planning.milestone_sequence", "strict")
        data = json.loads(self.path.read_text())
        self.assertEqual(data["planning"]["milestone_sequence"], "strict")
        self.assertFalse(data["execution"]["enabled"])
        self.assertEqual(self.run_action("get", "planning.milestone_sequence").strip(), '"strict"')
        self.run_action("reset", "planning.milestone_sequence")
        self.assertNotIn("milestone_sequence", json.loads(self.path.read_text())["planning"])
        self.assertEqual(self.run_action("get", "planning.milestone_sequence").strip(), '"off"')

    def test_nested_planning_queue_values_and_constraints(self):
        self.run_action("set", "planning.queue.target_pending", "7")
        self.run_action("set", "planning.trigger.pending_below", "4")
        self.assertEqual(json.loads(self.path.read_text())["planning"]["queue"]["target_pending"], 7)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "Planning thresholds"):
            self.run_action("set", "planning.trigger.pending_below", "8")
        self.assertEqual(self.path.read_bytes(), before)
        self.run_action("reset", "planning.trigger.pending_below")
        self.assertNotIn("trigger", json.loads(self.path.read_text())["planning"])

    def test_list_get_and_types(self):
        out = self.run_action("list")
        self.assertIn("planning.milestone_sequence = \"off\"", out)
        self.assertIn("execution.enabled = false", out)
        self.assertIn("timeout_seconds = 900", out)
        self.run_action("set", "quota.minimum_remaining_percent", "27.5")
        self.assertEqual(self.run_action("get", "quota.minimum_remaining_percent").strip(), "27.5")
        for name, value in (("planning.enabled", "yes"),
                            ("timeout_seconds", "-1"),
                            ("quota.minimum_remaining_percent", "101"),
                            ("planning.milestone_sequence", "unsafe"),
                            ("test_file_patterns", "not-json")):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.run_action("set", name, value)

    def test_execution_enablement_requires_dedicated_command(self):
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "authorize-execution"):
            self.run_action("set", "execution.enabled", "true")
        # Disabling execution or restoring the disabled default is safe.
        self.run_action("set", "execution.enabled", "false")
        self.run_action("reset", "execution.enabled")
        with self.assertRaisesRegex(ValueError, "pw plan"):
            self.run_action("set", "planning.enabled", "true")
        for key in ("id", "layout", "projectwright_initialized"):
            with self.assertRaisesRegex(ValueError, "cannot be changed"):
                self.run_action("set", key, "different")
        self.assertFalse(json.loads(self.path.read_text()).get("execution", {}).get("enabled", False))

    def test_sensitive_changes_require_explicit_yes(self):
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "sensitive"):
            self.run_action("set", "hermes", "/usr/local/bin/hermes")
        self.assertEqual(self.path.read_bytes(), before)
        self.run_action("set", "hermes", "/usr/local/bin/hermes", yes=True)
        self.assertEqual(json.loads(self.path.read_text())["hermes"], "/usr/local/bin/hermes")

    def test_embedded_path_escapes_refused_without_mutation(self):
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "escape"):
            self.run_action("set", "queue", "../../outside.md", yes=True)
        with self.assertRaisesRegex(ValueError, "owning repository"):
            self.run_action("set", "worktree", ".", yes=True)
        self.assertEqual(self.path.read_bytes(), before)

    def test_bad_scope_paths_and_bad_provider_rejected(self):
        before = self.path.read_bytes()
        for key, value in (("test_file_patterns", '["../other/test.py"]'),
                           ("provider.planner_argv", '["python3"]'),
                           ("provider.type", "command")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.run_action("set", key, value, yes=True)
        self.assertEqual(self.path.read_bytes(), before)

    def test_active_cycle_and_journal_block_updates(self):
        state = self.repo / ".pw/state"
        cycle = state / "git_cycle.json"
        cycle.write_text('{"version": 1}\n')
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "Active Git cycle"):
            self.run_action("set", "display_name", "Testing")
        cycle.unlink()
        journal = state / "worker_journal.json"
        journal.write_text('{"current_task": {"id": "P106"}}')
        with self.assertRaisesRegex(ValueError, "task journal"):
            self.run_action("set", "display_name", "Testing")
        self.assertEqual(self.path.read_bytes(), before)

    def test_unknown_keys_are_rejected(self):
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "Unknown setting"):
            self.run_action("set", "planning.milestone_sequencing", "strict")
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
