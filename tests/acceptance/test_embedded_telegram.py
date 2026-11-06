"""Real, disposable repository-local Telegram milestone acceptance lifecycle.

Uses Git, project-state files, and the installed callbacks without Telegram
network access, an actual Hermes gateway, or any user's existing projects.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[2] / "src" / "projectwright"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pw_embedded as embedded
import pw_telegram_approval as approval
import pw_buttons
import pw_notify
import pw_completion
import pw_plugin


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], text=True,
    ).strip()


class EmbeddedTelegramLifecycle(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="pw-embedded-approval-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.registry = self.base / "config" / "registry.json"
        self.patch_registry = patch.object(embedded, "registry_path", return_value=self.registry)
        self.patch_registry.start()
        self.addCleanup(self.patch_registry.stop)
        self.root = self.base / "legacy"
        self.root.mkdir()

    def repository(self, parent="outside", contents="VALUE = 1\n", *,
                   strict=True, shared=False) -> Path:
        repo = self.base / parent / "task-tracker"
        repo.parent.mkdir(parents=True, exist_ok=True)
        config_file = embedded.initialize(repo, shared=shared)
        git(repo, "config", "user.name", "Fixture")
        git(repo, "config", "user.email", "fixture@example.invalid")
        (repo / "probe.py").write_text(contents, encoding="utf-8")
        git(repo, "add", ".gitignore", "probe.py")
        git(repo, "commit", "-qm", "baseline")
        cfg = json.loads(config_file.read_text(encoding="utf-8"))
        cfg["planning"]["enabled"] = True
        if strict:
            cfg["planning"]["milestone_sequence"] = "strict"
        config_file.write_text(json.dumps(cfg), encoding="utf-8")
        (repo / ".pw/queue.md").write_text(
            "- [x] **P1 — READ** DEMO-1 / DEMO-1-M1: inspect fixture\n"
            "- [x] **P2 — COMMIT** DEMO-1 / DEMO-1-M1: commit fixture\n",
            encoding="utf-8",
        )
        (repo / ".pw/requirements.md").write_text(
            "## DEMO-1 — Disposable requirement\n\n"
            "### DEMO-1-M1 — Milestone\n"
            "#### Acceptance\n"
            "- **Command:** `/bin/true`\n"
            "- **Scope:** `probe.py`\n",
            encoding="utf-8",
        )
        if shared:
            git(repo, "add", ".pw/README.md", ".pw/requirements.md", ".pw/config.json")
            git(repo, "commit", "-qm", "shared Projectwright definitions")
        embedded.register(repo)
        return repo

    def test_full_scan_delivery_approval_completion_and_replay(self):
        repo = self.repository()
        marker = repo / ".pw"
        records = approval.scan(self.root)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["project"], repo.name)
        self.assertEqual(pw_buttons.resolve(
            self.root, pw_buttons.callback_data("a", record))[1], marker)
        sent = []
        values = {"TELEGRAM_BOT_TOKEN": "test", "TELEGRAM_ALLOWED_USERS": "123,456"}
        with patch.object(pw_notify, "config_values", return_value=values):
            def transport(payload):
                sent.append(payload)
                return len(sent) + 100
            self.assertEqual(
                pw_notify.notify_pending(self.root, transport=transport),
                [f"NOTIFIED {repo.name} / DEMO-1-M1"],
            )
            self.assertEqual(pw_notify.notify_pending(self.root, transport=transport), [])
        self.assertEqual(len(sent), 2)
        self.assertEqual(sent[0]["reply_markup"]["inline_keyboard"][0][0]["callback_data"],
                         pw_buttons.callback_data("a", record))
        result, verified_dir = pw_buttons.approve(
            self.root, pw_buttons.callback_data("a", record), True)
        self.assertEqual(verified_dir, marker)
        self.assertIn("APPROVED task-tracker / DEMO-1-M1", result)
        state = json.loads((marker / "planning_state.json").read_text())
        self.assertEqual(state["verified_milestones"]["DEMO-1-M1"]["completed_task_ids"],
                         ["P1", "P2"])
        self.assertFalse((marker / "telegram_approval_pending.json").exists())
        with self.assertRaisesRegex(ValueError, "no longer pending"):
            pw_buttons.approve(self.root, pw_buttons.callback_data("a", record))
        self.assertIsNotNone(pw_completion.completion_details(marker))
        completion_sent = []
        with patch.object(pw_completion, "config_values", return_value=values):
            def deliver(payload):
                completion_sent.append(payload)
                return len(completion_sent) + 200
            self.assertEqual(pw_completion.notify_completion(marker, transport=deliver),
                             ["123", "456"])
            self.assertEqual(pw_completion.notify_completion(marker, transport=deliver), [])
        self.assertEqual(len(completion_sent), 2)
        self.assertTrue(all("reply_markup" not in payload for payload in completion_sent))
        self.assertEqual(git(repo, "status", "--porcelain=v1"), "")

    def test_shared_definitions_stay_clean_during_approval(self):
        repo = self.repository(shared=True)
        marker = repo / ".pw"
        records = approval.scan(self.root)
        self.assertEqual(len(records), 1)
        pinned = records[0]
        result = pw_buttons.approve(
            self.root, pw_buttons.callback_data("a", pinned))
        self.assertIn("APPROVED", result)
        tracked = git(repo, "ls-files", "--", ".pw").splitlines()
        self.assertEqual(set(tracked), {
            ".pw/README.md", ".pw/config.json", ".pw/requirements.md",
        })
        self.assertTrue((marker / "planning_state.json").exists())
        self.assertEqual(git(repo, "status", "--porcelain=v1", "--untracked-files=all"), "")

    def test_rejection_and_stale_evidence_fail_closed(self):
        repo = self.repository()
        marker = repo / ".pw"
        record = approval.scan(self.root)[0]
        msg = pw_buttons.reject(self.root, pw_buttons.callback_data("r", record))
        self.assertIn("REJECTED", msg)
        self.assertTrue((marker / "telegram_approval_pending.json").exists())
        with self.assertRaisesRegex(ValueError, "explicitly rejected"):
            pw_buttons.approve(self.root, pw_buttons.callback_data("a", record))
        self.assertFalse((marker / "planning_state.json").exists())
        (marker / "telegram_approval_rejected.json").unlink()
        (marker / "requirements.md").write_text(
            (marker / "requirements.md").read_text().replace(
                "### DEMO-1-M1 — Milestone", "### DEMO-1-M1 — Revised milestone"))
        with self.assertRaisesRegex(ValueError, "stale"):
            pw_buttons.approve(self.root, pw_buttons.callback_data("a", record))
        self.assertFalse((marker / "planning_state.json").exists())

    def test_duplicate_names_route_by_pinned_evidence_not_by_name(self):
        one = self.repository("first", "VALUE = 1\n")
        two = self.repository("second", "VALUE = 2\n")
        records = approval.scan(self.root)
        self.assertEqual(len(records), 2)
        first = json.loads((one / ".pw/telegram_approval_pending.json").read_text())
        second = json.loads((two / ".pw/telegram_approval_pending.json").read_text())
        self.assertNotEqual(pw_buttons.request_id(first), pw_buttons.request_id(second))
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            approval.scan(self.root, project=one.name, milestone="DEMO-1-M1")
        with patch.object(sys, "argv", ["pw-notify", "--root", str(self.root),
                                         "--project", one.name]):
            with self.assertRaises(SystemExit) as error:
                pw_notify.main()
        self.assertEqual(error.exception.code, 2)
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            embedded.directory(one.name, Path.home() / "projects")
        result, selected = pw_buttons.approve(
            self.root, pw_buttons.callback_data("a", first), True)
        self.assertEqual(selected, one / ".pw")
        self.assertIn("APPROVED", result)
        self.assertFalse((two / ".pw/planning_state.json").exists())
        self.assertTrue((two / ".pw/telegram_approval_pending.json").exists())
        # An identical pinned record in two registered repositories is
        # ambiguous and must never approve either one.
        (one / ".pw/telegram_approval_pending.json").write_text(json.dumps(second))
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            pw_buttons.approve(self.root, pw_buttons.callback_data("a", second))

    def test_private_chat_plugin_completion_uses_exact_approved_directory(self):
        repo = self.repository()
        record = approval.scan(self.root)[0]
        marker = repo / ".pw"
        callbacks = []
        class Handler:
            def __init__(self, callback, pattern):
                self.callback = callback
                self.pattern = pattern
        app = types.SimpleNamespace(add_handler=callbacks.append)
        telegram_ext = types.ModuleType("telegram.ext")
        telegram_ext.CallbackQueryHandler = Handler
        query = types.SimpleNamespace(
            data=pw_buttons.callback_data("a", record),
            from_user=types.SimpleNamespace(id=123),
            message=types.SimpleNamespace(chat=types.SimpleNamespace(type="private")),
        )
        answers, edits = [], []
        async def answer(*args, **kwargs):
            answers.append((args, kwargs))
        async def edit_message_text(message):
            edits.append(message)
        query.answer = answer
        query.edit_message_text = edit_message_text
        with patch.dict(sys.modules, {"telegram": types.ModuleType("telegram"),
                                      "telegram.ext": telegram_ext}), \
             patch.object(pw_plugin, "_authorized_ids", return_value=frozenset({"123"})), \
             patch.object(pw_completion, "notify_completion", return_value=[]) as completion, \
             patch.object(pw_plugin, "_plan_after_approval") as replenish:
            pw_plugin._factory(app, None)
            asyncio.run(callbacks[0].callback(
                types.SimpleNamespace(callback_query=query), None))
        self.assertEqual(answers, [(("Recorded",), {})])
        self.assertEqual(len(edits), 1)
        self.assertIn("APPROVED", edits[0])
        completion.assert_called_once_with(marker)
        replenish.assert_called_once_with(marker)


    def test_post_approval_planning_scopes_exact_repository(self):
        repo = self.repository()
        marker = repo / ".pw"
        calls = []
        def fake_run(argv, **kwargs):
            calls.append((argv, kwargs))
            return types.SimpleNamespace(returncode=0, stdout='{"decision":"queued"}', stderr='')
        with patch("pw_config.load", return_value=(marker / "config.json", {"planning": {"enabled": True}})), \
             patch.object(pw_plugin.subprocess, "run", side_effect=fake_run):
            pw_plugin._plan_after_approval(marker)
        self.assertEqual(len(calls), 1)
        argv, kwargs = calls[0]
        self.assertEqual(argv[-3:], ["--project", repo.name, "--once"])
        self.assertEqual(kwargs["env"]["PROJECTWRIGHT_PROJECT_DIR"], str(repo.resolve()))
        self.assertTrue(kwargs["check"] is False)

    def test_post_approval_planning_failure_is_retryable(self):
        repo = self.repository()
        marker = repo / ".pw"
        with patch("pw_config.load", return_value=(marker / "config.json", {"planning": {"enabled": True}})), \
             patch.object(pw_plugin.subprocess, "run",
                          return_value=types.SimpleNamespace(returncode=4, stdout='{"decision":"planner_failed"}', stderr='')):
            with self.assertRaisesRegex(RuntimeError, "Post-approval planner returned 4"):
                pw_plugin._plan_after_approval(marker)


if __name__ == "__main__":
    unittest.main()
