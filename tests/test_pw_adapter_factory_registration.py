"""Offline adapter callback registration regression test."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src' / 'projectwright'))
import pw_plugin

class AdapterRegistrationTest(unittest.TestCase):
    def test_debian_fallback_does_not_shadow_hermes_venv(self):
        # A prepend here shadows Hermes's cryptography Python files while
        # retaining the venv's Rust extension, breaking Telegram imports.
        import ast
        adapter = Path(__file__).resolve().parents[1] / "packaging/hermes-plugin/projectwright-approvals/__init__.py"
        tree = ast.parse(adapter.read_text())
        path_mutations = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Attribute)
            and isinstance(node.func.value.value, ast.Name)
            and node.func.value.value.id == "sys"
            and node.func.value.attr == "path"
        ]
        self.assertTrue(any(node.func.attr == "append" for node in path_mutations))
        self.assertFalse(any(node.func.attr == "insert" for node in path_mutations))

    def test_registration_provides_factory(self):
        factories=[]
        pw_plugin.register(SimpleNamespace(register_telegram_handler=factories.append))
        self.assertEqual(len(factories), 1)
        self.assertTrue(callable(factories[0]))
