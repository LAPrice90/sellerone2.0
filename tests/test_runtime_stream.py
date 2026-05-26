from __future__ import annotations

import unittest

from scripts.core import runtime_stream


class RuntimeStreamTests(unittest.TestCase):
    def test_parse_lock_fields_and_pid(self) -> None:
        payload = "B_SUPERVISOR|pid=1234|start=2026-04-01T21:00:00Z|heartbeat=2026-04-01T21:00:05Z|worker=x\n"
        fields = runtime_stream.parse_lock_fields(payload)
        self.assertEqual(fields.get("owner"), "B_SUPERVISOR")
        self.assertEqual(fields.get("worker"), "x")
        self.assertEqual(runtime_stream.parse_lock_pid(payload), 1234)

    def test_build_lock_payload(self) -> None:
        payload = runtime_stream.build_lock_payload(
            owner="H",
            pid=77,
            start_utc="2026-04-01T21:10:00Z",
            heartbeat_utc="2026-04-01T21:10:05Z",
            fields={"run_id": "RID_1"},
        )
        self.assertIn("H|pid=77|start=2026-04-01T21:10:00Z|heartbeat=2026-04-01T21:10:05Z|run_id=RID_1", payload)
        self.assertTrue(payload.endswith("\n"))

    def test_replace_lock_heartbeat_preserves_start_and_fields(self) -> None:
        payload = "E|pid=99|start=2026-04-01T20:00:00Z|heartbeat=2026-04-01T20:00:05Z|mode=live\n"
        updated = runtime_stream.replace_lock_heartbeat(payload, heartbeat_utc="2026-04-01T20:00:10Z")
        self.assertIn("start=2026-04-01T20:00:00Z", updated)
        self.assertIn("heartbeat=2026-04-01T20:00:10Z", updated)
        self.assertIn("mode=live", updated)

    def test_parse_lock_pid_invalid_returns_none(self) -> None:
        payload = "B_SUPERVISOR|pid=abc|start=2026-04-01T20:00:00Z\n"
        self.assertIsNone(runtime_stream.parse_lock_pid(payload))


if __name__ == "__main__":
    unittest.main()
