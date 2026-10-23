"""Unit tests for baseline/development source-drift validation."""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
VALIDATOR_PATH = ROOT / "scripts" / "validate-baseline.py"
_spec = importlib.util.spec_from_file_location("projectwright_baseline_validator", VALIDATOR_PATH)
validator = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = validator
_spec.loader.exec_module(validator)


class BaselineValidatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pw-validator-")
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.source = self.root / "src/projectwright"
        self.source.mkdir(parents=True)
        self.records = {}
        for name in sorted(validator.EXPECTED_SOURCE_FILES):
            path = self.source / name
            data = b"# isolated validator fixture\n"
            path.write_bytes(data)
            self.records[name] = {
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            }
        self.manifest = self.root / "installed-source-manifest.json"
        self.manifest.write_text("fixture manifest; function under test receives parsed records\n")
        self.original_manifest = self.manifest.read_bytes()
        self.old_globals = (validator.ROOT, validator.SOURCE_DIR, validator.MANIFEST_PATH)
        validator.ROOT = self.root
        validator.SOURCE_DIR = self.source
        validator.MANIFEST_PATH = self.manifest
        self.addCleanup(self.restore_globals)
        self.old_modules = {}
        for name in validator.EXPECTED_SOURCE_FILES:
            module_name = pathlib.Path(name).stem
            if module_name in sys.modules:
                self.old_modules[module_name] = sys.modules.pop(module_name)
        self.addCleanup(self.restore_modules)

    def restore_globals(self):
        validator.ROOT, validator.SOURCE_DIR, validator.MANIFEST_PATH = self.old_globals
        source = str(self.source)
        while source in sys.path:
            sys.path.remove(source)

    def restore_modules(self):
        for name in validator.EXPECTED_SOURCE_FILES:
            sys.modules.pop(pathlib.Path(name).stem, None)
        sys.modules.update(self.old_modules)

    def inspect(self, mode):
        with contextlib.redirect_stdout(io.StringIO()):
            return validator.inspect_source(mode, self.records)

    def test_original_snapshot_passes_and_development_reports_drift_without_manifest_write(self):
        self.assertEqual(self.inspect("baseline"), (True, True, True, True))
        changed = self.source / sorted(validator.EXPECTED_SOURCE_FILES)[0]
        changed.write_text("# intentional development change\n")
        self.assertEqual(self.inspect("development"), (True, True, False, True))
        self.assertEqual(self.manifest.read_bytes(), self.original_manifest)

    def test_malformed_manifest_hash_is_invalid(self):
        bad_records = {name: dict(record) for name, record in self.records.items()}
        bad_records[sorted(bad_records)[0]]["sha256"] = "not-a-sha256"
        with contextlib.redirect_stdout(io.StringIO()):
            result = validator.inspect_source("development", bad_records)
        self.assertEqual(result[0:2], (True, True))
        self.assertFalse(result[2])
        self.assertFalse(result[3])
        self.assertEqual(self.manifest.read_bytes(), self.original_manifest)

    def test_manifest_byte_count_mismatch_is_reported_as_drift(self):
        bad_records = {name: dict(record) for name, record in self.records.items()}
        name = sorted(bad_records)[0]
        bad_records[name]["bytes"] += 1
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = validator.inspect_source("development", bad_records)
        self.assertFalse(result[2])
        self.assertIn(name, output.getvalue())
        self.assertIn("byte-count mismatch", output.getvalue())

    def test_load_manifest_reads_json_records(self):
        self.manifest.write_text(json.dumps({"files": self.records}), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(validator.load_manifest(), self.records)


if __name__ == "__main__":
    unittest.main()
