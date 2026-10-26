"""Offline adapter callback registration regression test."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from projectwright import pw_plugin

class AdapterRegistrationTest(unittest.TestCase):
    def test_registration_provides_factory(self):
        factories=[]
        pw_plugin.register(SimpleNamespace(register_telegram_handler=factories.append))
        self.assertEqual(len(factories), 1)
        self.assertTrue(callable(factories[0]))
