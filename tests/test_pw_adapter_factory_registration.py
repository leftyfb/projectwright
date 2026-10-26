"""Offline adapter callback registration regression test."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src' / 'projectwright'))
import pw_plugin

class AdapterRegistrationTest(unittest.TestCase):
    def test_registration_provides_factory(self):
        factories=[]
        pw_plugin.register(SimpleNamespace(register_telegram_handler=factories.append))
        self.assertEqual(len(factories), 1)
        self.assertTrue(callable(factories[0]))
