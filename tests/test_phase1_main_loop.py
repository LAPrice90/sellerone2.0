import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import phase1_main_loop, phase1_storage


class Phase1MainLoopTests(unittest.TestCase):
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

    def _market_payload(self, our_winner: bool) -> dict:
        return {
            "offers": [
                {
                    "SellerId": "OUR_SELLER",
                    "ListingPrice": {"Amount": 10.40},
                    "Shipping": {"Amount": 0.00},
                    "ShippingTime": {"minimumDays": 1, "maximumDays": 2},
                    "IsFeaturedOfferWinner": our_winner,
                    "IsFulfilledByAmazon": True,
                },
                {
                    "SellerId": "RIVAL_A",
                    "ListingPrice": {"Amount": 10.30},
                    "Shipping": {"Amount": 0.00},
                    "ShippingTime": {"minimumDays": 1, "maximumDays": 1},
                    "IsFeaturedOfferWinner": (not our_winner),
                    "IsFulfilledByAmazon": True,
                },
            ]
        }

    def _market_payload_winner_unknown_delivery(self, our_winner: bool) -> dict:
        return {
            "offers": [
                {
                    "SellerId": "OUR_SELLER",
                    "ListingPrice": {"Amount": 10.40},
                    "Shipping": {"Amount": 0.00},
                    "ShippingTime": {"minimumDays": 1, "maximumDays": 2},
                    "IsFeaturedOfferWinner": our_winner,
                    "IsFulfilledByAmazon": True,
                },
                {
                    "SellerId": "RIVAL_A",
                    "ListingPrice": {"Amount": 10.30},
                    "Shipping": {"Amount": 0.00},
                    "IsFeaturedOfferWinner": (not our_winner),
                    "IsFulfilledByAmazon": True,
                },
            ]
        }

    def _market_payload_unknown_outcome(self) -> dict:
        return {
            "offers": [
                {
                    "SellerId": "OUR_SELLER",
                    "ListingPrice": {"Amount": 10.40},
                    "Shipping": {"Amount": 0.00},
                    "ShippingTime": {"minimumDays": 1, "maximumDays": 2},
                    "IsFeaturedOfferWinner": False,
                    "IsFulfilledByAmazon": True,
                },
                {
                    "SellerId": "RIVAL_A",
                    "ListingPrice": {"Amount": 10.30},
                    "Shipping": {"Amount": 0.00},
                    "ShippingTime": {"minimumDays": 1, "maximumDays": 1},
                    "IsFeaturedOfferWinner": False,
                    "IsFulfilledByAmazon": True,
                },
            ]
        }

    def test_a_cycle_persists_daily_intel_and_non_null_source(self) -> None:
        result = phase1_main_loop.run_a_cycle(
            sku="SKU1",
            now_utc="2026-02-13T15:00:00Z",
            compliance_anchor_gbp="20.00",
            policy_buffer_pct="0.03",
            manual_cap_gbp="18.90",
            foep_price_gbp="",
            foep_status="ASIN_NOT_ELIGIBLE",
            foep_last_refresh_utc="",
            cpt_gbp="11.89",
            cpt_last_refresh_utc="2026-02-13T14:55:00Z",
            last_known_safe_gbp="",
            foep_stale_hours=48,
            foep_sanity_min_mult="0.5",
            foep_sanity_max_mult="2.0",
            market_reference_price_gbp="12.00",
        )

        self.assertEqual(result.eligibility_source, "MANUAL")
        rows = phase1_storage.read_where("sku_daily_intel", {"sku": "SKU1"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["eligibility_source"], "MANUAL")
        self.assertNotEqual(rows[0]["eligibility_source"], "")

    def test_a_cycle_cpt_error_reason_is_persisted_and_does_not_crash(self) -> None:
        result = phase1_main_loop.run_a_cycle(
            sku="SKU1E",
            now_utc="2026-02-13T15:01:00Z",
            compliance_anchor_gbp="",
            policy_buffer_pct="0.03",
            manual_cap_gbp="9.99",
            foep_price_gbp="",
            foep_status="MISSING",
            foep_last_refresh_utc="2026-02-13T15:01:00Z",
            cpt_gbp="",
            cpt_last_refresh_utc="2026-02-13T15:01:00Z",
            cpt_status="ERROR",
            last_known_safe_gbp="",
            foep_stale_hours=48,
            foep_sanity_min_mult="0.5",
            foep_sanity_max_mult="2.0",
            market_reference_price_gbp="",
            extra_reason_codes=["CPT_ERROR"],
        )
        self.assertEqual(result.cpt_status, "ERROR")
        rows = phase1_storage.read_where("sku_daily_intel", {"sku": "SKU1E"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["cpt_status"], "ERROR")
        self.assertIn("CPT_ERROR", rows[0]["eligibility_reason_codes_json"])

    def test_h_cycle_writer_lock_block_for_ppp_logs_read_only_result(self) -> None:
        phase1_main_loop.run_a_cycle(
            sku="SKU2",
            now_utc="2026-02-13T15:00:00Z",
            compliance_anchor_gbp="20.00",
            policy_buffer_pct="0.03",
            manual_cap_gbp="18.90",
            foep_price_gbp="",
            foep_status="ASIN_NOT_ELIGIBLE",
            foep_last_refresh_utc="",
            cpt_gbp="11.89",
            cpt_last_refresh_utc="2026-02-13T14:55:00Z",
            last_known_safe_gbp="",
            foep_stale_hours=48,
            foep_sanity_min_mult="0.5",
            foep_sanity_max_mult="2.0",
            market_reference_price_gbp="12.00",
        )

        calls = {"count": 0}

        def submitter(_submitted_price: str) -> dict:
            calls["count"] += 1
            return {"ok": "1", "http_status": "202", "submission_id": "SUB-2", "response_text": ""}

        result = phase1_main_loop.run_h_cycle(
            sku="SKU2",
            asin="ASIN2",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="PPP",
            enabled_live_writes=True,
            current_price_gbp="10.00",
            hard_floor_gbp="9.00",
            manual_cap_gbp="20.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload(our_winner=False),
            write_submitter=submitter,
            now_utc="2026-02-13T15:05:00Z",
        )

        self.assertEqual(calls["count"], 0)
        self.assertEqual(result.write_status, "READ_ONLY_NO_WRITE")
        self.assertIn("WRITER_LOCK_BLOCK", result.reason_codes)
        logs = phase1_storage.read_where("execution_log", {"sku": "SKU2"})
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["write_status"], "READ_ONLY_NO_WRITE")
        self.assertIn("WRITER_LOCK_BLOCK", logs[0]["reason_codes_json"])

    def test_h_cycle_parked_sku_forces_defensive_hold_no_write(self) -> None:
        phase1_main_loop.run_a_cycle(
            sku="SKU_PARKED",
            now_utc="2026-02-13T15:00:00Z",
            compliance_anchor_gbp="20.00",
            policy_buffer_pct="0.03",
            manual_cap_gbp="18.90",
            foep_price_gbp="",
            foep_status="ASIN_NOT_ELIGIBLE",
            foep_last_refresh_utc="",
            cpt_gbp="11.89",
            cpt_last_refresh_utc="2026-02-13T14:55:00Z",
            cpt_status="OK",
            cpt_risk_band="LOW",
            parked_flag="1",
            park_reason_codes=["PARK_SALE_STATUS_DROPPED"],
            last_known_safe_gbp="",
            foep_stale_hours=48,
            foep_sanity_min_mult="0.5",
            foep_sanity_max_mult="2.0",
            market_reference_price_gbp="12.00",
        )

        calls = {"count": 0}

        def submitter(_submitted_price: str) -> dict:
            calls["count"] += 1
            return {"ok": "1", "http_status": "202", "submission_id": "SUB-PARKED", "response_text": ""}

        out = phase1_main_loop.run_h_cycle(
            sku="SKU_PARKED",
            asin="ASIN_PARKED",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="CODEX_H",
            enabled_live_writes=True,
            current_price_gbp="10.00",
            hard_floor_gbp="9.00",
            manual_cap_gbp="20.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload(our_winner=False),
            write_submitter=submitter,
            now_utc="2026-02-13T15:05:00Z",
        )

        self.assertEqual(calls["count"], 0)
        self.assertEqual(out.state, "DEFENSIVE_HOLD")
        self.assertEqual(out.write_status, "READ_ONLY_NO_WRITE")
        self.assertIn("PARKED_NO_ACTION", out.reason_codes)

    def test_h_cycle_cpt_high_blocks_upward_actions(self) -> None:
        phase1_main_loop.run_a_cycle(
            sku="SKU_CPT_HIGH",
            now_utc="2026-02-13T15:00:00Z",
            compliance_anchor_gbp="20.00",
            policy_buffer_pct="0.03",
            manual_cap_gbp="18.90",
            foep_price_gbp="",
            foep_status="ASIN_NOT_ELIGIBLE",
            foep_last_refresh_utc="",
            cpt_gbp="11.89",
            cpt_last_refresh_utc="2026-02-13T14:55:00Z",
            cpt_status="OK",
            cpt_risk_band="HIGH",
            last_known_safe_gbp="",
            foep_stale_hours=48,
            foep_sanity_min_mult="0.5",
            foep_sanity_max_mult="2.0",
            market_reference_price_gbp="12.00",
        )

        calls = {"count": 0}

        def submitter(_submitted_price: str) -> dict:
            calls["count"] += 1
            return {"ok": "1", "http_status": "202", "submission_id": "SUB-CPT-HIGH", "response_text": ""}

        out = phase1_main_loop.run_h_cycle(
            sku="SKU_CPT_HIGH",
            asin="ASIN_CPT_HIGH",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="CODEX_H",
            enabled_live_writes=True,
            current_price_gbp="10.00",
            hard_floor_gbp="9.00",
            manual_cap_gbp="20.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload(our_winner=False),
            write_submitter=submitter,
            now_utc="2026-02-13T15:05:00Z",
        )

        self.assertEqual(calls["count"], 0)
        self.assertEqual(out.write_status, "NO_WRITE_REQUIRED")
        self.assertIn("CPT_RISK_HIGH_UPWARD_BLOCK", out.reason_codes)

    def test_h_cycle_cpt_unknown_uses_conservative_non_raise(self) -> None:
        phase1_main_loop.run_a_cycle(
            sku="SKU_CPT_UNKNOWN",
            now_utc="2026-02-13T15:00:00Z",
            compliance_anchor_gbp="20.00",
            policy_buffer_pct="0.03",
            manual_cap_gbp="18.90",
            foep_price_gbp="",
            foep_status="ASIN_NOT_ELIGIBLE",
            foep_last_refresh_utc="",
            cpt_gbp="",
            cpt_last_refresh_utc="2026-02-13T14:55:00Z",
            cpt_status="MISSING",
            cpt_risk_band="UNKNOWN",
            last_known_safe_gbp="",
            foep_stale_hours=48,
            foep_sanity_min_mult="0.5",
            foep_sanity_max_mult="2.0",
            market_reference_price_gbp="12.00",
        )

        calls = {"count": 0}

        def submitter(_submitted_price: str) -> dict:
            calls["count"] += 1
            return {"ok": "1", "http_status": "202", "submission_id": "SUB-CPT-UNKNOWN", "response_text": ""}

        out = phase1_main_loop.run_h_cycle(
            sku="SKU_CPT_UNKNOWN",
            asin="ASIN_CPT_UNKNOWN",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="CODEX_H",
            enabled_live_writes=True,
            current_price_gbp="10.00",
            hard_floor_gbp="9.00",
            manual_cap_gbp="20.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload(our_winner=False),
            write_submitter=submitter,
            now_utc="2026-02-13T15:05:00Z",
        )

        self.assertEqual(calls["count"], 0)
        self.assertEqual(out.write_status, "NO_WRITE_REQUIRED")
        self.assertIn("CPT_RISK_UNKNOWN_CONSERVATIVE_HOLD", out.reason_codes)

    def test_h_cycle_daily_intel_gate_fresh_allows_normal_path(self) -> None:
        phase1_main_loop.run_a_cycle(
            sku="SKU_INTEL_FRESH",
            now_utc="2026-02-13T15:00:00Z",
            compliance_anchor_gbp="20.00",
            policy_buffer_pct="0.03",
            manual_cap_gbp="19.00",
            foep_price_gbp="18.95",
            foep_status="OK",
            foep_last_refresh_utc="2026-02-13T15:00:00Z",
            cpt_gbp="18.90",
            cpt_last_refresh_utc="2026-02-13T15:00:00Z",
            last_known_safe_gbp="",
            foep_stale_hours=48,
            foep_sanity_min_mult="0.5",
            foep_sanity_max_mult="2.0",
            market_reference_price_gbp="19.00",
        )
        calls = {"count": 0}

        def submitter(_submitted_price: str) -> dict:
            calls["count"] += 1
            return {"ok": "1", "http_status": "202", "submission_id": "SUB-FRESH", "response_text": ""}

        out = phase1_main_loop.run_h_cycle(
            sku="SKU_INTEL_FRESH",
            asin="ASIN_INTEL_FRESH",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="CODEX_H",
            enabled_live_writes=True,
            current_price_gbp="10.40",
            hard_floor_gbp="9.50",
            manual_cap_gbp="19.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload(our_winner=False),
            listings_observed_price_gbp="10.30",
            write_submitter=submitter,
            now_utc="2026-02-13T15:10:00Z",
        )

        self.assertEqual(calls["count"], 1)
        self.assertEqual(out.write_status, "APPLIED")
        self.assertEqual(out.blocked_due_to_missing_intel, "0")
        self.assertEqual(out.blocked_due_to_stale_intel, "0")

    def test_h_cycle_daily_intel_gate_missing_forces_defensive_hold(self) -> None:
        calls = {"count": 0}

        def submitter(_submitted_price: str) -> dict:
            calls["count"] += 1
            return {"ok": "1", "http_status": "202", "submission_id": "SUB-MISS", "response_text": ""}

        out = phase1_main_loop.run_h_cycle(
            sku="SKU_INTEL_MISSING",
            asin="ASIN_INTEL_MISSING",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="CODEX_H",
            enabled_live_writes=True,
            current_price_gbp="10.40",
            hard_floor_gbp="9.50",
            manual_cap_gbp="19.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload(our_winner=False),
            listings_observed_price_gbp="10.30",
            write_submitter=submitter,
            now_utc="2026-02-13T15:11:00Z",
        )

        self.assertEqual(calls["count"], 0)
        self.assertEqual(out.write_status, "READ_ONLY_NO_WRITE")
        self.assertEqual(out.state, "DEFENSIVE_HOLD")
        self.assertIn("DAILY_INTEL_MISSING", out.reason_codes)
        self.assertIn("A_CYCLE_MISSING_DEFENSIVE_HOLD", out.reason_codes)
        self.assertEqual(out.blocked_due_to_missing_intel, "1")
        self.assertEqual(out.blocked_due_to_stale_intel, "0")

    def test_h_cycle_daily_intel_gate_stale_forces_defensive_hold(self) -> None:
        phase1_main_loop.run_a_cycle(
            sku="SKU_INTEL_STALE",
            now_utc="2026-02-12T15:00:00Z",
            compliance_anchor_gbp="20.00",
            policy_buffer_pct="0.03",
            manual_cap_gbp="19.00",
            foep_price_gbp="18.95",
            foep_status="OK",
            foep_last_refresh_utc="2026-02-12T15:00:00Z",
            cpt_gbp="18.90",
            cpt_last_refresh_utc="2026-02-12T15:00:00Z",
            last_known_safe_gbp="",
            foep_stale_hours=48,
            foep_sanity_min_mult="0.5",
            foep_sanity_max_mult="2.0",
            market_reference_price_gbp="19.00",
        )
        out = phase1_main_loop.run_h_cycle(
            sku="SKU_INTEL_STALE",
            asin="ASIN_INTEL_STALE",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="CODEX_H",
            enabled_live_writes=True,
            current_price_gbp="10.40",
            hard_floor_gbp="9.50",
            manual_cap_gbp="19.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload(our_winner=False),
            listings_observed_price_gbp="10.30",
            now_utc="2026-02-13T15:12:00Z",
        )
        self.assertEqual(out.write_status, "READ_ONLY_NO_WRITE")
        self.assertIn("DAILY_INTEL_STALE", out.reason_codes)
        self.assertIn("A_CYCLE_MISSING_DEFENSIVE_HOLD", out.reason_codes)
        self.assertEqual(out.blocked_due_to_missing_intel, "0")
        self.assertEqual(out.blocked_due_to_stale_intel, "1")

    def test_h_cycle_daily_intel_refresh_throttle_once_per_sku_per_day(self) -> None:
        refresh_calls = {"count": 0}

        def refresher() -> None:
            refresh_calls["count"] += 1

        first = phase1_main_loop.run_h_cycle(
            sku="SKU_INTEL_THR",
            asin="ASIN_INTEL_THR",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="CODEX_H",
            enabled_live_writes=True,
            current_price_gbp="10.40",
            hard_floor_gbp="9.50",
            manual_cap_gbp="19.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload(our_winner=False),
            now_utc="2026-02-13T15:13:00Z",
            daily_intel_refresher=refresher,
        )
        second = phase1_main_loop.run_h_cycle(
            sku="SKU_INTEL_THR",
            asin="ASIN_INTEL_THR",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="CODEX_H",
            enabled_live_writes=True,
            current_price_gbp="10.40",
            hard_floor_gbp="9.50",
            manual_cap_gbp="19.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload(our_winner=False),
            now_utc="2026-02-13T15:14:00Z",
            daily_intel_refresher=refresher,
        )

        self.assertEqual(refresh_calls["count"], 1)
        self.assertIn("DAILY_INTEL_REFRESH_ATTEMPTED", first.reason_codes)
        self.assertIn("DAILY_INTEL_REFRESH_THROTTLED", second.reason_codes)
        self.assertEqual(first.refresh_attempted_count, "1")
        self.assertEqual(first.refresh_throttled_count, "0")
        self.assertEqual(second.refresh_attempted_count, "0")
        self.assertEqual(second.refresh_throttled_count, "1")

    def test_h_cycle_daily_intel_gate_proof_counts(self) -> None:
        phase1_main_loop.run_h_cycle(
            sku="SKU_COUNT_MISSING",
            asin="ASIN_COUNT_MISSING",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="CODEX_H",
            enabled_live_writes=True,
            current_price_gbp="10.40",
            hard_floor_gbp="9.50",
            manual_cap_gbp="19.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload(our_winner=False),
            now_utc="2026-02-13T16:00:00Z",
        )
        phase1_main_loop.run_a_cycle(
            sku="SKU_COUNT_STALE",
            now_utc="2026-02-12T16:00:00Z",
            compliance_anchor_gbp="20.00",
            policy_buffer_pct="0.03",
            manual_cap_gbp="19.00",
            foep_price_gbp="18.95",
            foep_status="OK",
            foep_last_refresh_utc="2026-02-12T16:00:00Z",
            cpt_gbp="18.90",
            cpt_last_refresh_utc="2026-02-12T16:00:00Z",
            last_known_safe_gbp="",
            foep_stale_hours=48,
            foep_sanity_min_mult="0.5",
            foep_sanity_max_mult="2.0",
            market_reference_price_gbp="19.00",
        )
        phase1_main_loop.run_h_cycle(
            sku="SKU_COUNT_STALE",
            asin="ASIN_COUNT_STALE",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="CODEX_H",
            enabled_live_writes=True,
            current_price_gbp="10.40",
            hard_floor_gbp="9.50",
            manual_cap_gbp="19.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload(our_winner=False),
            now_utc="2026-02-13T16:01:00Z",
        )
        refresh_calls = {"count": 0}

        def refresher() -> None:
            refresh_calls["count"] += 1

        phase1_main_loop.run_h_cycle(
            sku="SKU_COUNT_THR",
            asin="ASIN_COUNT_THR",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="CODEX_H",
            enabled_live_writes=True,
            current_price_gbp="10.40",
            hard_floor_gbp="9.50",
            manual_cap_gbp="19.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload(our_winner=False),
            now_utc="2026-02-13T16:02:00Z",
            daily_intel_refresher=refresher,
        )
        phase1_main_loop.run_h_cycle(
            sku="SKU_COUNT_THR",
            asin="ASIN_COUNT_THR",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="CODEX_H",
            enabled_live_writes=True,
            current_price_gbp="10.40",
            hard_floor_gbp="9.50",
            manual_cap_gbp="19.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload(our_winner=False),
            now_utc="2026-02-13T16:03:00Z",
            daily_intel_refresher=refresher,
        )

        logs = phase1_storage.read_where("execution_log", {})
        blocked_due_to_missing_intel = sum(1 for r in logs if "DAILY_INTEL_MISSING" in str(r.get("reason_codes_json", "")))
        blocked_due_to_stale_intel = sum(1 for r in logs if "DAILY_INTEL_STALE" in str(r.get("reason_codes_json", "")))
        refresh_attempted_count = sum(1 for r in logs if "DAILY_INTEL_REFRESH_ATTEMPTED" in str(r.get("reason_codes_json", "")))
        refresh_throttled_count = sum(1 for r in logs if "DAILY_INTEL_REFRESH_THROTTLED" in str(r.get("reason_codes_json", "")))

        self.assertEqual(blocked_due_to_missing_intel, 3)
        self.assertEqual(blocked_due_to_stale_intel, 1)
        self.assertEqual(refresh_attempted_count, 1)
        self.assertEqual(refresh_throttled_count, 1)
        print(
            "daily_intel_gate_counts "
            f"blocked_due_to_missing_intel={blocked_due_to_missing_intel} "
            f"blocked_due_to_stale_intel={blocked_due_to_stale_intel} "
            f"refresh_attempted_count={refresh_attempted_count} "
            f"refresh_throttled_count={refresh_throttled_count}"
        )

    def test_h_cycle_wires_snapshot_dve_ceilings_and_execution_logging(self) -> None:
        phase1_main_loop.run_a_cycle(
            sku="SKU3",
            now_utc="2026-02-13T15:10:00Z",
            compliance_anchor_gbp="20.00",
            policy_buffer_pct="0.03",
            manual_cap_gbp="19.00",
            foep_price_gbp="18.95",
            foep_status="OK",
            foep_last_refresh_utc="2026-02-13T15:00:00Z",
            cpt_gbp="18.90",
            cpt_last_refresh_utc="2026-02-13T15:00:00Z",
            last_known_safe_gbp="",
            foep_stale_hours=48,
            foep_sanity_min_mult="0.5",
            foep_sanity_max_mult="2.0",
            market_reference_price_gbp="19.00",
        )

        result = phase1_main_loop.run_h_cycle(
            sku="SKU3",
            asin="ASIN3",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="CODEX_H",
            enabled_live_writes=False,
            current_price_gbp="10.40",
            hard_floor_gbp="9.50",
            manual_cap_gbp="19.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload(our_winner=False),
            now_utc="2026-02-13T15:15:00Z",
        )

        self.assertEqual(result.write_status, "READ_ONLY_NO_WRITE")
        self.assertEqual(len(phase1_storage.read_where("offer_snapshot_facts", {"sku": "SKU3"})), 2)
        self.assertEqual(len(phase1_storage.read_where("offer_variants", {"sku": "SKU3"})), 2)
        self.assertEqual(len(phase1_storage.read_where("sku_ceiling_events", {"sku": "SKU3"})), 1)
        self.assertEqual(len(phase1_storage.read_where("execution_log", {"sku": "SKU3"})), 1)
        decisions = phase1_storage.read_where("decision_log", {"sku": "SKU3"})
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["action"], "PROPOSED_WRITE")
        self.assertEqual(decisions[0]["buy_box_present"], "1")
        self.assertEqual(decisions[0]["outcome_known"], "1")
        self.assertEqual(decisions[0]["we_present"], "1")
        self.assertEqual(decisions[0]["writer_mode"], "CODEX_H")
        self.assertNotEqual(decisions[0]["best_rival_effective_price_gbp"], "")
        self.assertNotEqual(decisions[0]["direct_competitor_variant_id"], "")
        rollup = phase1_storage.read_where("scenario_rollup", {"sku": "SKU3"})
        self.assertEqual(len(rollup), 1)
        self.assertEqual(rollup[0]["hold_buy_box_missing_count"], "0")
        self.assertEqual(rollup[0]["hold_outcome_unknown_count"], "0")
        self.assertEqual(rollup[0]["allowed_to_act_count"], "1")

    def test_h_cycle_codex_h_allows_write_submitter_when_enabled(self) -> None:
        phase1_main_loop.run_a_cycle(
            sku="SKU3B",
            now_utc="2026-02-13T15:10:00Z",
            compliance_anchor_gbp="20.00",
            policy_buffer_pct="0.03",
            manual_cap_gbp="19.00",
            foep_price_gbp="18.95",
            foep_status="OK",
            foep_last_refresh_utc="2026-02-13T15:00:00Z",
            cpt_gbp="18.90",
            cpt_last_refresh_utc="2026-02-13T15:00:00Z",
            last_known_safe_gbp="",
            foep_stale_hours=48,
            foep_sanity_min_mult="0.5",
            foep_sanity_max_mult="2.0",
            market_reference_price_gbp="19.00",
        )

        calls = {"count": 0}

        def submitter(_submitted_price: str) -> dict:
            calls["count"] += 1
            return {"ok": "1", "http_status": "202", "submission_id": "SUB-3B", "response_text": ""}

        out = phase1_main_loop.run_h_cycle(
            sku="SKU3B",
            asin="ASIN3B",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="CODEX_H",
            enabled_live_writes=True,
            current_price_gbp="10.40",
            hard_floor_gbp="9.50",
            manual_cap_gbp="19.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload(our_winner=False),
            listings_observed_price_gbp="10.30",
            write_submitter=submitter,
            now_utc="2026-02-13T15:16:00Z",
        )

        self.assertEqual(calls["count"], 1)
        self.assertEqual(out.write_status, "APPLIED")

    def test_h_cycle_write_then_probe_close_logs_oas_and_updates_memory(self) -> None:
        phase1_main_loop.run_a_cycle(
            sku="SKU4",
            now_utc="2026-02-13T15:20:00Z",
            compliance_anchor_gbp="20.00",
            policy_buffer_pct="0.03",
            manual_cap_gbp="19.00",
            foep_price_gbp="18.95",
            foep_status="OK",
            foep_last_refresh_utc="2026-02-13T15:00:00Z",
            cpt_gbp="18.90",
            cpt_last_refresh_utc="2026-02-13T15:00:00Z",
            last_known_safe_gbp="",
            foep_stale_hours=48,
            foep_sanity_min_mult="0.5",
            foep_sanity_max_mult="2.0",
            market_reference_price_gbp="19.00",
        )

        def submitter(_submitted_price: str) -> dict:
            return {"ok": "1", "http_status": "202", "submission_id": "SUB-1", "response_text": ""}

        start = phase1_main_loop.run_h_cycle(
            sku="SKU4",
            asin="ASIN4",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="CODEX_H",
            enabled_live_writes=True,
            current_price_gbp="10.40",
            hard_floor_gbp="9.50",
            manual_cap_gbp="19.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload(our_winner=False),
            listings_observed_price_gbp="10.30",
            write_submitter=submitter,
            now_utc="2026-02-13T15:25:00Z",
        )

        self.assertEqual(start.write_status, "APPLIED")
        self.assertNotEqual(start.probe_id, "")

        end = phase1_main_loop.run_h_cycle(
            sku="SKU4",
            asin="ASIN4",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="CODEX_H",
            enabled_live_writes=False,
            current_price_gbp="10.20",
            hard_floor_gbp="9.50",
            manual_cap_gbp="19.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.20",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload(our_winner=False),
            probe_observation_payload=self._market_payload(our_winner=False),
            submitted_write_in_last_cycle="1",
            previous_verified_our_price_gbp="10.40",
            now_utc="2026-02-13T15:45:00Z",
        )

        self.assertEqual(end.oas_admissible_flag, "1")
        oas_rows = phase1_storage.read_where("oas_log", {"sku": "SKU4"})
        self.assertEqual(len(oas_rows), 1)
        self.assertEqual(oas_rows[0]["admissible_flag"], "1")

        probe_rows = phase1_storage.read_where("probe_windows", {"sku": "SKU4"})
        self.assertEqual(len(probe_rows), 2)
        self.assertEqual(probe_rows[-1]["oas_result"], "ADMISSIBLE")

        memory = phase1_storage.read_by_keys("variant_delta_memory", {"sku": "SKU4", "rival_key": "BEST_RIVAL"})
        self.assertIsNotNone(memory)
        self.assertEqual(memory["valid_test_count"], "1")

    def test_h_cycle_blocks_learning_when_featured_winner_delivery_unknown(self) -> None:
        phase1_main_loop.run_a_cycle(
            sku="SKU5",
            now_utc="2026-02-13T15:20:00Z",
            compliance_anchor_gbp="20.00",
            policy_buffer_pct="0.03",
            manual_cap_gbp="19.00",
            foep_price_gbp="18.95",
            foep_status="OK",
            foep_last_refresh_utc="2026-02-13T15:00:00Z",
            cpt_gbp="18.90",
            cpt_last_refresh_utc="2026-02-13T15:00:00Z",
            last_known_safe_gbp="",
            foep_stale_hours=48,
            foep_sanity_min_mult="0.5",
            foep_sanity_max_mult="2.0",
            market_reference_price_gbp="19.00",
        )

        def submitter(_submitted_price: str) -> dict:
            return {"ok": "1", "http_status": "202", "submission_id": "SUB-5", "response_text": ""}

        start = phase1_main_loop.run_h_cycle(
            sku="SKU5",
            asin="ASIN5",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="CODEX_H",
            enabled_live_writes=True,
            current_price_gbp="10.40",
            hard_floor_gbp="9.50",
            manual_cap_gbp="19.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload(our_winner=False),
            listings_observed_price_gbp="10.30",
            write_submitter=submitter,
            now_utc="2026-02-13T15:25:00Z",
        )
        self.assertEqual(start.write_status, "APPLIED")

        end = phase1_main_loop.run_h_cycle(
            sku="SKU5",
            asin="ASIN5",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="CODEX_H",
            enabled_live_writes=False,
            current_price_gbp="10.20",
            hard_floor_gbp="9.50",
            manual_cap_gbp="19.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.20",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload(our_winner=False),
            probe_observation_payload=self._market_payload_winner_unknown_delivery(our_winner=False),
            submitted_write_in_last_cycle="1",
            previous_verified_our_price_gbp="10.40",
            now_utc="2026-02-13T15:45:00Z",
        )

        self.assertEqual(end.oas_admissible_flag, "0")
        oas_rows = phase1_storage.read_where("oas_log", {"sku": "SKU5"})
        self.assertEqual(len(oas_rows), 1)
        self.assertEqual(oas_rows[0]["admissible_flag"], "0")
        self.assertIn("OAS_FAIL_FEATURED_WINNER_DELIVERY_UNKNOWN", oas_rows[0]["hard_fail_reason_codes_json"])

        probe_rows = phase1_storage.read_where("probe_windows", {"sku": "SKU5"})
        self.assertEqual(len(probe_rows), 2)
        self.assertEqual(probe_rows[-1]["oas_result"], "BLOCKED")

        memory = phase1_storage.read_by_keys("variant_delta_memory", {"sku": "SKU5", "rival_key": "BEST_RIVAL"})
        self.assertIsNotNone(memory)
        self.assertEqual(memory["valid_test_count"], "0")
        self.assertEqual(memory["contaminated_test_count"], "1")

    def test_h_cycle_read_only_mode_logs_block_without_write(self) -> None:
        phase1_main_loop.run_a_cycle(
            sku="SKU6",
            now_utc="2026-02-13T15:20:00Z",
            compliance_anchor_gbp="20.00",
            policy_buffer_pct="0.03",
            manual_cap_gbp="19.00",
            foep_price_gbp="18.95",
            foep_status="OK",
            foep_last_refresh_utc="2026-02-13T15:00:00Z",
            cpt_gbp="18.90",
            cpt_last_refresh_utc="2026-02-13T15:00:00Z",
            last_known_safe_gbp="",
            foep_stale_hours=48,
            foep_sanity_min_mult="0.5",
            foep_sanity_max_mult="2.0",
            market_reference_price_gbp="19.00",
        )

        calls = {"count": 0}

        def submitter(_submitted_price: str) -> dict:
            calls["count"] += 1
            return {"ok": "1", "http_status": "202", "submission_id": "SUB-6", "response_text": ""}

        out = phase1_main_loop.run_h_cycle(
            sku="SKU6",
            asin="ASIN6",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="READ_ONLY",
            enabled_live_writes=True,
            current_price_gbp="10.40",
            hard_floor_gbp="9.50",
            manual_cap_gbp="19.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload(our_winner=False),
            write_submitter=submitter,
            now_utc="2026-02-13T15:26:00Z",
        )

        self.assertEqual(calls["count"], 0)
        self.assertEqual(out.write_status, "READ_ONLY_NO_WRITE")
        self.assertIn("WRITER_LOCK_BLOCK", out.reason_codes)
        logs = phase1_storage.read_where("execution_log", {"sku": "SKU6"})
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["write_status"], "READ_ONLY_NO_WRITE")
        self.assertIn("WRITER_LOCK_BLOCK", logs[0]["reason_codes_json"])
        decisions = phase1_storage.read_where("decision_log", {"sku": "SKU6"})
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["writer_mode"], "READ_ONLY")

    def test_h_cycle_logs_blocked_rollup_for_unknown_outcome(self) -> None:
        phase1_main_loop.run_a_cycle(
            sku="SKU7",
            now_utc="2026-02-13T15:20:00Z",
            compliance_anchor_gbp="20.00",
            policy_buffer_pct="0.03",
            manual_cap_gbp="19.00",
            foep_price_gbp="18.95",
            foep_status="OK",
            foep_last_refresh_utc="2026-02-13T15:00:00Z",
            cpt_gbp="18.90",
            cpt_last_refresh_utc="2026-02-13T15:00:00Z",
            last_known_safe_gbp="",
            foep_stale_hours=48,
            foep_sanity_min_mult="0.5",
            foep_sanity_max_mult="2.0",
            market_reference_price_gbp="19.00",
        )
        phase1_main_loop.run_h_cycle(
            sku="SKU7",
            asin="ASIN7",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="READ_ONLY",
            enabled_live_writes=False,
            current_price_gbp="10.40",
            hard_floor_gbp="9.50",
            manual_cap_gbp="19.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload_unknown_outcome(),
            now_utc="2026-02-13T15:27:00Z",
        )

        decisions = phase1_storage.read_where("decision_log", {"sku": "SKU7"})
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["buy_box_present"], "0")
        self.assertEqual(decisions[0]["outcome_known"], "0")
        self.assertEqual(decisions[0]["action"], "HOLD")
        self.assertIn("buy_box_missing", decisions[0]["reason"])
        self.assertIn("outcome_unknown", decisions[0]["reason"])
        rollup = phase1_storage.read_where("scenario_rollup", {"sku": "SKU7"})
        self.assertEqual(len(rollup), 1)
        self.assertEqual(rollup[0]["hold_buy_box_missing_count"], "1")
        self.assertEqual(rollup[0]["hold_outcome_unknown_count"], "1")
        self.assertEqual(rollup[0]["allowed_to_act_count"], "0")

    def test_h_cycle_unobservable_blocks_live_write(self) -> None:
        phase1_main_loop.run_a_cycle(
            sku="SKU8",
            now_utc="2026-02-13T15:20:00Z",
            compliance_anchor_gbp="20.00",
            policy_buffer_pct="0.03",
            manual_cap_gbp="19.00",
            foep_price_gbp="18.95",
            foep_status="OK",
            foep_last_refresh_utc="2026-02-13T15:00:00Z",
            cpt_gbp="18.90",
            cpt_last_refresh_utc="2026-02-13T15:00:00Z",
            last_known_safe_gbp="",
            foep_stale_hours=48,
            foep_sanity_min_mult="0.5",
            foep_sanity_max_mult="2.0",
            market_reference_price_gbp="19.00",
        )

        calls = {"count": 0}

        def submitter(_submitted_price: str) -> dict:
            calls["count"] += 1
            return {"ok": "1", "http_status": "202", "submission_id": "SUB-8", "response_text": ""}

        out = phase1_main_loop.run_h_cycle(
            sku="SKU8",
            asin="ASIN8",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="CODEX_H",
            enabled_live_writes=True,
            current_price_gbp="10.40",
            hard_floor_gbp="9.50",
            manual_cap_gbp="19.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload_unknown_outcome(),
            write_submitter=submitter,
            now_utc="2026-02-13T15:27:00Z",
        )

        self.assertEqual(calls["count"], 0)
        self.assertEqual(out.write_status, "OBSERVABILITY_BLOCK_NO_WRITE")
        self.assertIn("SUPPRESSION_OR_UNKNOWN_OUTCOME", out.reason_codes)
        decisions = phase1_storage.read_where("decision_log", {"sku": "SKU8"})
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["action"], "HOLD")
        self.assertIn("outcome_unknown", decisions[0]["hold_reason"])

    def test_h_cycle_writer_mode_counts_proof(self) -> None:
        for sku in ["SKU9A", "SKU9B", "SKU9C"]:
            phase1_main_loop.run_a_cycle(
                sku=sku,
                now_utc="2026-02-13T15:20:00Z",
                compliance_anchor_gbp="20.00",
                policy_buffer_pct="0.03",
                manual_cap_gbp="19.00",
                foep_price_gbp="18.95",
                foep_status="OK",
                foep_last_refresh_utc="2026-02-13T15:00:00Z",
                cpt_gbp="18.90",
                cpt_last_refresh_utc="2026-02-13T15:00:00Z",
                last_known_safe_gbp="",
                foep_stale_hours=48,
                foep_sanity_min_mult="0.5",
                foep_sanity_max_mult="2.0",
                market_reference_price_gbp="19.00",
            )

        call_counts = {"CODEX_H": 0, "PPP": 0, "READ_ONLY": 0}

        def make_submitter(mode: str):
            def _submitter(_submitted_price: str) -> dict:
                call_counts[mode] += 1
                return {"ok": "1", "http_status": "202", "submission_id": f"SUB-{mode}", "response_text": ""}

            return _submitter

        phase1_main_loop.run_h_cycle(
            sku="SKU9A",
            asin="ASIN9A",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="CODEX_H",
            enabled_live_writes=True,
            current_price_gbp="10.40",
            hard_floor_gbp="9.50",
            manual_cap_gbp="19.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload(our_winner=False),
            listings_observed_price_gbp="10.30",
            write_submitter=make_submitter("CODEX_H"),
            now_utc="2026-02-13T15:28:00Z",
        )
        phase1_main_loop.run_h_cycle(
            sku="SKU9B",
            asin="ASIN9B",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="PPP",
            enabled_live_writes=True,
            current_price_gbp="10.40",
            hard_floor_gbp="9.50",
            manual_cap_gbp="19.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload(our_winner=False),
            write_submitter=make_submitter("PPP"),
            now_utc="2026-02-13T15:29:00Z",
        )
        phase1_main_loop.run_h_cycle(
            sku="SKU9C",
            asin="ASIN9C",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="READ_ONLY",
            enabled_live_writes=True,
            current_price_gbp="10.40",
            hard_floor_gbp="9.50",
            manual_cap_gbp="19.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=self._market_payload(our_winner=False),
            write_submitter=make_submitter("READ_ONLY"),
            now_utc="2026-02-13T15:30:00Z",
        )

        logs = [r for r in phase1_storage.read_where("execution_log", {}) if r.get("sku") in {"SKU9A", "SKU9B", "SKU9C"}]
        blocked_writes_count = sum(
            1
            for r in logs
            if r.get("write_status") == "READ_ONLY_NO_WRITE" and "WRITER_LOCK_BLOCK" in str(r.get("reason_codes_json", ""))
        )
        allowed_writes_count = sum(1 for r in logs if r.get("write_status") == "APPLIED")
        reason_code_counts = {"WRITER_LOCK_BLOCK": 0, "LIVE_WRITES_DISABLED": 0, "SUPPRESSION_OR_UNKNOWN_OUTCOME": 0}
        for row in logs:
            reason_text = str(row.get("reason_codes_json", ""))
            for reason in reason_code_counts.keys():
                if reason in reason_text:
                    reason_code_counts[reason] += 1

        self.assertEqual(call_counts["CODEX_H"], 1)
        self.assertEqual(call_counts["PPP"], 0)
        self.assertEqual(call_counts["READ_ONLY"], 0)
        self.assertEqual(blocked_writes_count, 2)
        self.assertEqual(allowed_writes_count, 1)
        self.assertEqual(reason_code_counts.get("WRITER_LOCK_BLOCK", 0), 2)

        print(
            (
                "writer_mode_counts "
                f"blocked_writes_count={blocked_writes_count} "
                f"allowed_writes_count={allowed_writes_count} "
                f"reason_code_counts={reason_code_counts}"
            )
        )


if __name__ == "__main__":
    unittest.main()
