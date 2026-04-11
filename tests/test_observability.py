from __future__ import annotations

import json
import unittest

from visual_annotation_mcp.observability import metrics_snapshot, observe_async, redact_value, set_request_id


class ObservabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_observe_async_records_metrics(self) -> None:
        set_request_id("test-request")

        async def ok_runner() -> str:
            return "ok"

        out = await observe_async("unit.test.tool", ok_runner, metadata={"k": "v"})
        self.assertEqual(out, "ok")

        snap = metrics_snapshot()
        self.assertIn("unit.test.tool", snap)
        self.assertGreaterEqual(snap["unit.test.tool"]["calls"], 1)

    async def test_observe_async_records_failures(self) -> None:
        set_request_id("test-request")

        async def bad_runner() -> str:
            raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            await observe_async("unit.test.fail", bad_runner)

        snap = metrics_snapshot()
        self.assertIn("unit.test.fail", snap)
        self.assertGreaterEqual(snap["unit.test.fail"]["failures"], 1)

    def test_redaction_masks_sensitive_fields(self) -> None:
        payload = {
            "password": "abc",
            "nested": {"token": "secret-token", "note": "ok"},
            "headers": {"Authorization": "Bearer very-secret-token"},
        }
        redacted = redact_value(payload)
        encoded = json.dumps(redacted)
        self.assertNotIn("very-secret-token", encoded)
        self.assertIn("***REDACTED***", encoded)


if __name__ == "__main__":
    unittest.main()
