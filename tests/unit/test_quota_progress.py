"""Unit tests for source-tree Projectwright modules."""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src" / "projectwright"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

import project_quota
import project_worker_progress


class QuotaPolicyTests(unittest.TestCase):
    def test_disabled_quota_does_not_contact_home_assistant(self):
        with mock.patch.object(project_quota.urllib.request, "urlopen") as urlopen:
            decision = project_quota.evaluate({"enabled": False})
        self.assertTrue(decision["allowed"])
        self.assertEqual(decision["reason"], "disabled")
        urlopen.assert_not_called()

    def test_unavailable_quota_sensor_fails_closed(self):
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return b'{"state":"72"}'

        with tempfile.TemporaryDirectory(prefix="pw-quota-") as td:
            home = pathlib.Path(td)
            secrets = home / ".hermes/secrets/ha.env"
            secrets.parent.mkdir(parents=True)
            secrets.write_text("HA_URL=https://ha.example\nHA_TOKEN=fixture\n")
            def fetch(request, timeout):
                if request.full_url.endswith("binary_sensor.fixture_unavailable"):
                    raise OSError("fixture sensor unavailable")
                return Response()
            with (
                mock.patch.dict(project_quota.os.environ, {
                    project_quota.RATE_LIMITED_ENTITY_ENV: "binary_sensor.fixture_unavailable"
                }),
                mock.patch.object(project_quota.urllib.request, "urlopen", side_effect=fetch),
            ):
                decision = project_quota.evaluate({}, home=home)
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "quota_unavailable")
        self.assertIn("fixture sensor unavailable", decision["detail"])

    def test_omitted_optional_entity_uses_configurable_environment_default(self):
        class Response:
            def __init__(self, state):
                self.state = state
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json.dumps({"state": self.state}).encode()

        with tempfile.TemporaryDirectory(prefix="pw-quota-default-") as td:
            home = pathlib.Path(td)
            secrets = home / ".hermes/secrets/ha.env"
            secrets.parent.mkdir(parents=True)
            secrets.write_text("HA_URL=https://ha.example\nHA_TOKEN=fixture\n")
            seen = []
            def fetch(request, timeout):
                entity = request.full_url.rsplit("/", 1)[-1]
                seen.append(entity)
                if entity == "sensor.codex_usage_weekly_remaining":
                    return Response("72")
                if entity == "binary_sensor.fixture_rate_limit":
                    return Response("off")
                raise AssertionError(f"unexpected sensor request: {entity}")
            with (
                mock.patch.dict(project_quota.os.environ, {
                    project_quota.RATE_LIMITED_ENTITY_ENV: "binary_sensor.fixture_rate_limit"
                }),
                mock.patch.object(project_quota.urllib.request, "urlopen", side_effect=fetch),
            ):
                decision = project_quota.evaluate({}, home=home)
        self.assertTrue(decision["allowed"])
        self.assertEqual(seen, [
            "sensor.codex_usage_weekly_remaining",
            "binary_sensor.fixture_rate_limit",
        ])

    def test_explicit_null_disables_optional_rate_limit_sensor(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return b'{"state":"72"}'

        with tempfile.TemporaryDirectory(prefix="pw-quota-null-") as td:
            home = pathlib.Path(td)
            secrets = home / ".hermes/secrets/ha.env"
            secrets.parent.mkdir(parents=True)
            secrets.write_text("HA_URL=https://ha.example\nHA_TOKEN=fixture\n")
            seen = []
            def fetch(request, timeout):
                entity = request.full_url.rsplit("/", 1)[-1]
                seen.append(entity)
                return Response()
            with (
                mock.patch.dict(project_quota.os.environ, {
                    project_quota.RATE_LIMITED_ENTITY_ENV: "binary_sensor.fixture_rate_limit"
                }),
                mock.patch.object(project_quota.urllib.request, "urlopen", side_effect=fetch),
            ):
                decision = project_quota.evaluate({"rate_limited_entity": None}, home=home)
        self.assertTrue(decision["allowed"])
        self.assertEqual(seen, ["sensor.codex_usage_weekly_remaining"])

    def test_explicit_unavailable_rate_limit_sensor_fails_closed(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return b'{"state":"72"}'

        with tempfile.TemporaryDirectory(prefix="pw-quota-explicit-") as td:
            home = pathlib.Path(td)
            secrets = home / ".hermes/secrets/ha.env"
            secrets.parent.mkdir(parents=True)
            secrets.write_text("HA_URL=https://ha.example\nHA_TOKEN=fixture\n")
            def fetch(request, timeout):
                if request.full_url.endswith("sensor.codex_usage_weekly_remaining"):
                    return Response()
                raise OSError("configured sensor unavailable")
            with mock.patch.object(project_quota.urllib.request, "urlopen", side_effect=fetch):
                decision = project_quota.evaluate(
                    {"rate_limited_entity": "binary_sensor.fixture_rate_limit"}, home=home
                )
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "quota_unavailable")

    def test_non_null_non_string_rate_limit_setting_fails_closed(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return b'{"state":"72"}'

        with tempfile.TemporaryDirectory(prefix="pw-quota-invalid-") as td:
            home = pathlib.Path(td)
            secrets = home / ".hermes/secrets/ha.env"
            secrets.parent.mkdir(parents=True)
            secrets.write_text("HA_URL=https://ha.example\nHA_TOKEN=fixture\n")
            with mock.patch.object(project_quota.urllib.request, "urlopen", return_value=Response()):
                decision = project_quota.evaluate({"rate_limited_entity": False}, home=home)
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "quota_unavailable")


class WorkerProgressTests(unittest.TestCase):
    def test_completed_task_counter_is_idempotent(self):
        with tempfile.TemporaryDirectory(prefix="pw-progress-") as td:
            state = pathlib.Path(td) / "state/progress.json"
            self.assertTrue(project_worker_progress.record_completed(state, "P-1"))
            self.assertFalse(project_worker_progress.record_completed(state, "P-1"))
            self.assertTrue(project_worker_progress.record_completed(state, "P-2"))
            result = project_worker_progress.read_state(state)
        self.assertEqual(result["completed_tasks_total"], 2)
        self.assertEqual(result["completed_since_strategic_review"], 2)
        self.assertEqual(result["completed_task_ids"], ["P-1", "P-2"])


if __name__ == "__main__":
    unittest.main()
