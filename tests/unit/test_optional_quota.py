"""Quota is opt-in, and explicitly enabled HA policy stays fail-closed."""
import json
from pathlib import Path
import tempfile
import unittest

from pw_config import load
from pw_quota import evaluate


class OptionalQuotaTests(unittest.TestCase):
    def test_unconfigured_quota_does_not_use_home_assistant(self):
        with tempfile.TemporaryDirectory() as tmp:
            decision = evaluate({}, home=Path(tmp))
            self.assertEqual(decision["reason"], "disabled")
            self.assertTrue(decision["allowed"])
            self.assertFalse(decision["enabled"])

    def test_initialized_config_defaults_quota_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "demo"
            project.mkdir()
            (project / "config.json").write_text('{"id":"demo"}')
            _, config = load("demo", Path(tmp))
            self.assertEqual(config["quota"], {"enabled": False})

    def test_explicit_opt_in_retains_fail_closed_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "demo"
            project.mkdir()
            (project / "config.json").write_text(json.dumps({
                "id": "demo", "quota": {"enabled": True, "remaining_entity": "sensor.example"}
            }))
            _, config = load("demo", Path(tmp))
            self.assertTrue(config["quota"]["enabled"])
            decision = evaluate(config["quota"], home=Path(tmp))
            self.assertFalse(decision["allowed"])
            self.assertEqual(decision["reason"], "quota_unavailable")


if __name__ == "__main__":
    unittest.main()
