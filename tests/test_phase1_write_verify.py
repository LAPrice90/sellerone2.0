import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.phase1 import phase1_storage, phase1_write_verify


class Phase1WriteVerifyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.data_dir = self.root / "data"
        self.lock_path = self.root / "out" / "phase1.lock"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.data_patch = patch.object(phase1_storage, "DATA_DIR", self.data_dir)
        self.lock_patch = patch.object(phase1_storage, "LOCK_PATH", self.lock_path)
        self.data_patch.start()
        self.lock_patch.start()

    def tearDown(self) -> None:
        self.data_patch.stop()
        self.lock_patch.stop()
        self.tmpdir.cleanup()

    def test_write_verified_by_primary_and_probe_window_started(self) -> None:
        captured_prices: list[str] = []

        def submitter(submitted_price: str) -> dict:
            captured_prices.append(submitted_price)
            return {"ok": "1", "http_status": "202", "submission_id": "SUB123", "response_text": ""}

        result = phase1_write_verify.execute_write_verify_and_start_probe(
            sku="SKU1",
            state_at_start="REGAIN",
            proposed_price_gbp="10.15",
            hard_floor_gbp="9.00",
            price_apply_tolerance_gbp="0.01",
            start_snapshot_id="SNAP1",
            start_featured_seller_id="SELLER_X",
            market_structure_hash_start="HASH1",
            listings_observed_price_gbp="10.15",
            latest_snapshot_rows=[],
            write_submitter=submitter,
            now_utc="2026-02-13T14:00:00Z",
        )

        self.assertEqual(captured_prices, ["10.15"])
        self.assertEqual(result.write_status, "APPLIED")
        self.assertEqual(result.verification_source, "LISTINGS_ITEMS")
        self.assertTrue(result.probe_started)
        self.assertNotEqual(result.probe_id, "")
        probe_rows = phase1_storage.read_where("probe_windows", {"sku": "SKU1"})
        self.assertEqual(len(probe_rows), 1)
        self.assertEqual(probe_rows[0]["state_at_start"], "REGAIN")
        self.assertEqual(probe_rows[0]["start_snapshot_id"], "SNAP1")
        self.assertEqual(probe_rows[0]["oas_result"], "PENDING")

    def test_write_verified_by_snapshot_fallback(self) -> None:
        def submitter(_: str) -> dict:
            return {"ok": "1", "http_status": "200", "submission_id": "SUB999", "response_text": ""}

        result = phase1_write_verify.execute_write_verify_and_start_probe(
            sku="SKU2",
            state_at_start="RAISE_FIND_LOSS",
            proposed_price_gbp="11.99",
            hard_floor_gbp="9.00",
            price_apply_tolerance_gbp="0.01",
            start_snapshot_id="SNAP2",
            start_featured_seller_id="SELLER_Y",
            market_structure_hash_start="HASH2",
            listings_observed_price_gbp="",
            latest_snapshot_rows=[
                {"is_our_offer": "0", "landed_price_gbp": "12.10"},
                {"is_our_offer": "1", "landed_price_gbp": "11.99"},
            ],
            write_submitter=submitter,
            now_utc="2026-02-13T14:05:00Z",
        )

        self.assertEqual(result.write_status, "APPLIED")
        self.assertEqual(result.verification_source, "SNAPSHOT_FALLBACK")
        self.assertEqual(result.observed_price_gbp, "11.99")
        probe_rows = phase1_storage.read_where("probe_windows", {"sku": "SKU2"})
        self.assertEqual(len(probe_rows), 1)

    def test_write_not_applied_does_not_open_probe_window(self) -> None:
        def submitter(_: str) -> dict:
            return {"ok": "1", "http_status": "202", "submission_id": "SUB404", "response_text": ""}

        result = phase1_write_verify.execute_write_verify_and_start_probe(
            sku="SKU3",
            state_at_start="BRACKET_NARROW",
            proposed_price_gbp="15.50",
            hard_floor_gbp="9.00",
            price_apply_tolerance_gbp="0.01",
            start_snapshot_id="SNAP3",
            start_featured_seller_id="SELLER_Z",
            market_structure_hash_start="HASH3",
            listings_observed_price_gbp="15.10",
            latest_snapshot_rows=[{"is_our_offer": "1", "landed_price_gbp": "15.20"}],
            write_submitter=submitter,
            now_utc="2026-02-13T14:10:00Z",
        )

        self.assertEqual(result.write_status, "WRITE_NOT_APPLIED")
        self.assertFalse(result.probe_started)
        self.assertEqual(result.write_error, "WRITE_NOT_APPLIED")
        probe_rows = phase1_storage.read_where("probe_windows", {"sku": "SKU3"})
        self.assertEqual(len(probe_rows), 0)

    def test_write_rejected_does_not_verify_or_open_probe(self) -> None:
        def submitter(_: str) -> dict:
            return {"ok": "0", "http_status": "400", "submission_id": "", "response_text": "bad schema"}

        result = phase1_write_verify.execute_write_verify_and_start_probe(
            sku="SKU4",
            state_at_start="REGAIN",
            proposed_price_gbp="8.00",
            hard_floor_gbp="9.50",
            price_apply_tolerance_gbp="0.01",
            start_snapshot_id="SNAP4",
            start_featured_seller_id="SELLER_Q",
            market_structure_hash_start="HASH4",
            listings_observed_price_gbp="9.50",
            latest_snapshot_rows=[],
            write_submitter=submitter,
            now_utc="2026-02-13T14:15:00Z",
        )

        self.assertEqual(result.write_status, "WRITE_REJECTED")
        self.assertFalse(result.probe_started)
        self.assertEqual(result.http_status, "400")
        self.assertEqual(result.write_error, "bad schema")
        probe_rows = phase1_storage.read_where("probe_windows", {"sku": "SKU4"})
        self.assertEqual(len(probe_rows), 0)

    def test_pre_write_hard_floor_clamp_is_applied(self) -> None:
        submitted: list[str] = []

        def submitter(price: str) -> dict:
            submitted.append(price)
            return {"ok": "1", "http_status": "200", "submission_id": "SUBFLOOR", "response_text": ""}

        result = phase1_write_verify.execute_write_verify_and_start_probe(
            sku="SKU5",
            state_at_start="REGAIN",
            proposed_price_gbp="8.10",
            hard_floor_gbp="9.40",
            price_apply_tolerance_gbp="0.01",
            start_snapshot_id="SNAP5",
            start_featured_seller_id="SELLER_F",
            market_structure_hash_start="HASH5",
            listings_observed_price_gbp="9.40",
            latest_snapshot_rows=[],
            write_submitter=submitter,
            now_utc="2026-02-13T14:20:00Z",
        )

        self.assertEqual(submitted, ["9.40"])
        self.assertIn("GUARDRAIL_HARD_FLOOR_CLAMP", result.reason_codes)
        self.assertEqual(result.submitted_price_gbp, "9.40")
        self.assertEqual(result.write_status, "APPLIED")


if __name__ == "__main__":
    unittest.main()

