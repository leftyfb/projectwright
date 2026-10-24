"""Wheel's flat module list must stay aligned with the audited source inventory."""
from __future__ import annotations
import json
from pathlib import Path
import unittest

try:
    import tomllib
except ImportError:
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]


class PackageManifestContract(unittest.TestCase):
    def test_wheel_includes_every_expected_source_module(self):
        data = tomllib.loads((ROOT / "pyproject.toml").read_text())
        modules = data["tool"]["setuptools"]["py-modules"]
        manifest = json.loads((ROOT / "installed-source-manifest.json").read_text())
        expected = {Path(name).stem for name in manifest["files"]}
        canonical_additions = {'pw_worker_progress', 'pw_milestone_sequence', 'pw_acceptance_gate', 'pw_quota', 'pw_recovery', 'pw_worker_journal', 'pw_notes_publisher', 'pw_defaults', 'pw_init', 'pw_config', 'pw_notes_sync', 'pw_milestone_guard'}
        self.assertEqual(set(modules), expected | canonical_additions)
        self.assertEqual(len(modules), len(set(modules)))
        self.assertEqual(set(modules), {p.stem for p in (ROOT / "src" / "projectwright").glob("*.py")})

    def test_console_entrypoints_reference_packaged_modules(self):
        data = tomllib.loads((ROOT / "pyproject.toml").read_text())
        modules = set(data["tool"]["setuptools"]["py-modules"])
        scripts = data["project"]["scripts"]
        self.assertIn("pw-dispatch", scripts)
        for entry in scripts.values():
            module, sep, attr = entry.partition(":")
            self.assertEqual(sep, ":")
            self.assertIn(module, modules)
            self.assertEqual(attr, "cli" if module == "pw_dispatch" and entry == "pw_dispatch:cli" else "main")


if __name__ == "__main__":
    unittest.main()
