"""Regression specifications for independent review findings.

All tests are offline. Expected failures describe currently unresolved behavior;
removing expectedFailure requires a proven implementation fix.
"""
import asyncio
import shutil
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[2] / "src" / "projectwright"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pw_dispatch
import pw_notify
import pw_plugin
import pw_buttons


class NotificationRaceTests(unittest.TestCase):
    @unittest.expectedFailure
    def test_pending_request_revoked_during_delivery_never_gets_marked_delivered(self):
        """Current notifier checks pending once, before starting a network send."""
        # Import inside the method to prevent unittest discovery from collecting
        # the imported TestCase class a second time.
        from tests.acceptance.test_acceptance_and_telegram import TelegramApprovalAndButtonTests
        fixture = TelegramApprovalAndButtonTests("test_scan_pins_buttons_and_message_evidence")
        fixture.setUp()
        try:
            fixture.scan_one()
            values = {"TELEGRAM_BOT_TOKEN": "fixture-token",
                      "TELEGRAM_ALLOWED_USERS": "123"}
            def revoke_before_transport(_payload):
                (fixture.project / "telegram_approval_pending.json").unlink()
                return 77
            with patch.object(pw_notify, "config_values", return_value=values):
                pw_notify.notify_pending(fixture.root, transport=revoke_before_transport)
            self.assertFalse(
                (fixture.project / "telegram_approval_notified.json").exists(),
                "Revoked pending request was marked as delivered",
            )
        finally:
            fixture.doCleanups()


class CallbackConfigurationTests(unittest.TestCase):
    def test_running_callback_handler_rechecks_authorized_users(self):
        """Changing allowed users currently requires registering handlers again."""
        class Handler:
            def __init__(self, callback, pattern):
                self.callback = callback
                self.pattern = pattern
        class App:
            def add_handler(self, handler):
                self.handler = handler
        class Query:
            def __init__(self):
                self.from_user = SimpleNamespace(id=456)
                self.message = SimpleNamespace(chat=SimpleNamespace(type="private"))
                self.data = "pwa:a:fixture:" + "0" * 20
                self.answers = []
            async def answer(self, text, **kwargs):
                self.answers.append(text)
            async def edit_message_text(self, text):
                pass
        values = {"TELEGRAM_BOT_TOKEN": "fixture-token",
                  "TELEGRAM_ALLOWED_USERS": "123"}
        app = App()
        ext = SimpleNamespace(CallbackQueryHandler=Handler)
        with patch.dict(sys.modules, {"telegram": SimpleNamespace(ext=ext),
                                      "telegram.ext": ext}), \
             patch.object(pw_notify, "config_values",
                          side_effect=lambda *_: dict(values)), \
             patch.object(pw_buttons, "approve", return_value="APPROVED"):
            pw_plugin._factory(app, None)
            values["TELEGRAM_ALLOWED_USERS"] = "456"
            q = Query()
            asyncio.run(app.handler.callback(SimpleNamespace(callback_query=q), None))
        self.assertEqual(q.answers, ["Recorded"],
                         "Callback authorization stayed stale after config change")


class DispatcherImportIsolationTests(unittest.TestCase):
    def test_cycle_gate_ignores_poisoned_global_queue_manager_module(self):
        """The cycle gate must resolve its helper from the selected scripts tree."""
        with tempfile.TemporaryDirectory(prefix="pw-module-isolation-") as td:
            base = Path(td)
            root = base / "projects"
            project = root / "fixture"
            project.mkdir(parents=True)
            scripts = base / "scripts"
            scripts.mkdir()
            shutil.copyfile(SRC / "project_queue_manager.py", scripts / "project_queue_manager.py")
            cycle_file = project / "cycle.json"
            cycle = {"version": 1, "phase": "active", "last_task": "P101",
                     "head": "abc", "branch": "main", "snapshot": ["M foo.txt"],
                     "allowed": ["foo.txt"]}
            cycle_file.write_text(json.dumps(cycle))
            (project / "config.json").write_text(
                json.dumps({"id": "fixture", "cycle_file": str(cycle_file),
                            "branch": "main"}))
            queue_file = project / "queue.md"
            queue_file.write_text("- [x] **P101 — EDIT** Edit\n"
                                  "- [ ] **P102 — TEST** Test\n")
            class Match:
                def __init__(self, task_id, kind, state):
                    self.data = {"id": task_id, "kind": kind, "state": state}
                def __getitem__(self, key):
                    return self.data[key]
            worker = SimpleNamespace(
                load_project=lambda project_id: None,
                CYCLE_FILE=cycle_file,
                QUEUE=queue_file,
                pick_task=lambda text: SimpleNamespace(task_id="P102", kind="TEST"),
                ROW=SimpleNamespace(finditer=lambda text: [
                    Match("P101", "EDIT", "x"), Match("P102", "TEST", " ")]),
                repo_state=lambda: ("abc", "main", None, ["M foo.txt"]),
            )
            class Loader:
                def exec_module(self, module):
                    return None
            spec = SimpleNamespace(loader=Loader(), name="isolated_cycle_worker")
            from project_queue_manager import queue_summary, read_json_optional
            poisoned = SimpleNamespace(
                queue_summary=lambda _text: {"invalid_lines": [1]},
                read_json_optional=read_json_optional,
            )
            # The correct repository module would accept the synthetic queue.
            self.assertEqual(queue_summary(queue_file.read_text())["invalid_lines"], [])
            import importlib.util
            with patch.dict(sys.modules, {"project_queue_manager": poisoned}), \
                 patch.object(importlib.util, "spec_from_file_location", return_value=spec), \
                 patch.object(importlib.util, "module_from_spec", return_value=worker), \
                 patch.dict("os.environ", {"HERMES_PROJECT_CONFIG_DIR": str(root)}):
                self.assertTrue(
                    pw_dispatch.authorized_cycle_task("fixture", scripts,
                        {"decision": "blocked",
                         "reason": "branch_or_worktree, active_git_cycle"}),
                    "Cycle gate used a globally cached, unrelated manager module",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
