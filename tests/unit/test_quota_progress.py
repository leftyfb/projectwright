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
                if request.full_url.endswith("binary_sensor.codex_rate_limited"):
                    raise OSError("fixture sensor unavailable")
                return Response()
            with mock.patch.object(project_quota.urllib.request, "urlopen", side_effect=fetch):
                decision = project_quota.evaluate({}, home=home)
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "quota_unavailable")
        self.assertIn("fixture sensor unavailable", decision["detail"])

    @unittest.expectedFailure
    def test_optional_rate_limit_entity_uses_audit_documented_entity_name(self):
        """Audit regression: source default differs from the observed HA entity."""
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
                seen.append(request.full_url.rsplit("/", 1)[-1])
                return Response("72" if "weekly_remaining" in request.full_url else "off")
            with mock.patch.object(project_quota.urllib.request, "urlopen", side_effect=fetch):
                project_quota.evaluate({}, home=home)
        self.assertIn("binary_sensor.codex_usage_rate_limit_reached", seen)


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
