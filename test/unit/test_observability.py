import os
import unittest
from unittest.mock import patch

from src import observability as obs


class _Observation:
    trace_id = "a" * 32

    def update(self, **_kwargs):
        return None


class _Context:
    def __init__(self, *, fail_exit=False):
        self.fail_exit = fail_exit

    def __enter__(self):
        return _Observation()

    def __exit__(self, *_args):
        if self.fail_exit:
            raise RuntimeError("telemetry exit failed")
        return False


class _Client:
    def __init__(self, *, fail_start=False, fail_exit=False):
        self.fail_start = fail_start
        self.fail_exit = fail_exit

    def start_as_current_observation(self, **_kwargs):
        if self.fail_start:
            raise RuntimeError("telemetry start failed")
        return _Context(fail_exit=self.fail_exit)

    def get_current_trace_id(self):
        return "a" * 32


class ObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.old_client = obs._client
        self.old_initialised = obs._client_initialised

    def tearDown(self):
        obs._client = self.old_client
        obs._client_initialised = self.old_initialised

    def _set_client(self, client):
        obs._client = client
        obs._client_initialised = True

    def test_child_content_is_summarised_by_default(self):
        with patch.dict(os.environ, {"LANGFUSE_CAPTURE_CONTENT": "false"}, clear=False):
            result = obs.sanitise(
                {"student_email": "child@example.com", "homework": "2 + 2 = 4"}
            )
        self.assertEqual(result["student_email"], {"type": "text", "chars": 17, "sha256": result["student_email"]["sha256"]})
        self.assertEqual(result["homework"]["chars"], 9)
        self.assertNotIn("child@example.com", str(result))
        self.assertNotIn("2 + 2", str(result))

    def test_secret_values_are_redacted(self):
        self.assertEqual(obs.sanitise("secret-value", key="api_key"), "[redacted]")
        self.assertEqual(obs.sanitise("session-value", key="session"), "[redacted]")

    def test_telemetry_start_failure_does_not_break_application(self):
        self._set_client(_Client(fail_start=True))
        with obs.trace_span("test") as handle:
            self.assertIsNone(handle.observation)

    def test_telemetry_exit_failure_keeps_application_result(self):
        self._set_client(_Client(fail_exit=True))
        with obs.trace_span("test") as handle:
            self.assertEqual(handle.trace_id, "a" * 32)

    def test_application_exception_is_not_swallowed(self):
        self._set_client(_Client())
        with self.assertRaisesRegex(ValueError, "business error"):
            with obs.trace_span("test"):
                raise ValueError("business error")


if __name__ == "__main__":
    unittest.main()
