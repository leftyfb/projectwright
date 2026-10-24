"""Hermes Telegram plugin authorization at callback time, no Telegram network."""
from __future__ import annotations
import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / "src" / "projectwright"
sys.path.insert(0, str(SRC))
import pw_plugin

class FakeQuery:
    def __init__(self, uid, chat="private", data="pwa:a:fixture:" + "a"*20):
        self.from_user = types.SimpleNamespace(id=uid)
        self.message = types.SimpleNamespace(chat=types.SimpleNamespace(type=chat))
        self.data = data
        self.answers = []
        self.edits = []
    async def answer(self, *args, **kwargs):
        self.answers.append((args, kwargs))
    async def edit_message_text(self, value):
        self.edits.append(value)

class PluginAuthorization(unittest.TestCase):
    def setUp(self):
        self.handlers = []
        ext = types.ModuleType("telegram.ext")
        class Handler:
            def __init__(obj, callback, pattern):
                obj.callback = callback
                obj.pattern = pattern
        ext.CallbackQueryHandler = Handler
        self.fake_ext = ext
        self.app = types.SimpleNamespace(add_handler=self.handlers.append)

    def invoke(self, user_id, chat, allowed):
        q = FakeQuery(user_id, chat)
        with patch.dict(sys.modules, {"telegram": types.ModuleType("telegram"),
                                      "telegram.ext": self.fake_ext}), \
             patch.object(pw_plugin, "_authorized_ids", return_value=frozenset(allowed)):
            pw_plugin._factory(self.app, None)
            async def run():
                await self.handlers[-1].callback(types.SimpleNamespace(callback_query=q), None)
            asyncio.run(run())
        return q

    def test_unlisted_user_denied(self):
        q = self.invoke(222, "private", {"111"})
        self.assertEqual(len(q.answers), 1)
        self.assertEqual(q.answers[0][0], ("Not authorized",))
        self.assertEqual(q.edits, [])

    def test_authorized_user_in_group_denied(self):
        q = self.invoke(111, "group", {"111"})
        self.assertEqual(q.answers[0][0], ("Not authorized",))
        self.assertEqual(q.edits, [])

    def test_revocation_effective_on_next_callback(self):
        q = self.invoke(111, "private", set())
        self.assertEqual(q.answers[0][0], ("Not authorized",))
        self.assertEqual(q.edits, [])

    def test_bad_allowlist_fails_closed(self):
        with patch.object(pw_plugin, "SCRIPTS", SRC), \
             patch("pw_notify.config_values", return_value={"TELEGRAM_ALLOWED_USERS": "111,bad"}):
            self.assertEqual(pw_plugin._authorized_ids(), frozenset())

if __name__ == "__main__":
    unittest.main()
