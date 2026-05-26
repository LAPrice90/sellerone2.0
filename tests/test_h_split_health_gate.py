import os
import sys
import tempfile
import unittest
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.cycles import run_H_pricing_cycle as h_cycle
from scripts.cycles import run_H_pricing_cycle_guarded as h_guard


class HSplitHealthGateTests(unittest.TestCase):
    def test_split_mode_fail_closed_blocks_when_snapshot_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_fail_closed = h_cycle.H_HEALTH_FAIL_CLOSED
            old_checklist = h_cycle.H_SPLIT_CHECKLIST_PATH
            old_primary_checklist = h_cycle.H_PRIMARY_CHECKLIST_PATH
            old_state_path = h_cycle.SPLIT_SHADOW_STATE_PATH
            old_compare_path = h_cycle.SPLIT_SHADOW_COMPARE_PATH
            try:
                h_cycle.H_HEALTH_FAIL_CLOSED = True
                h_cycle.H_SPLIT_CHECKLIST_PATH = root / "checklist_H_split.csv"
                h_cycle.H_PRIMARY_CHECKLIST_PATH = root / "checklist_H.csv"
                h_cycle.SPLIT_SHADOW_STATE_PATH = root / "split_shadow_state.json"
                h_cycle.SPLIT_SHADOW_COMPARE_PATH = root / "split_shadow_compare.csv"
                payload = h_cycle._resolve_h_split_gate(
                    now_utc=h_cycle._utc_now(),
                    run_id="20260218T100000Z",
                    mode_requested="split",
                    mode_effective="split",
                    state={"h_gate_health_run_utc": "2999-01-01T00:00:00Z"},
                )
                self.assertEqual(payload.get("h_gate_block_live_writes"), "1")
                self.assertEqual(payload.get("h_gate_fail_count"), "")
                self.assertEqual(payload.get("h_gate_warn_count"), "")
            finally:
                h_cycle.H_HEALTH_FAIL_CLOSED = old_fail_closed
                h_cycle.H_SPLIT_CHECKLIST_PATH = old_checklist
                h_cycle.H_PRIMARY_CHECKLIST_PATH = old_primary_checklist
                h_cycle.SPLIT_SHADOW_STATE_PATH = old_state_path
                h_cycle.SPLIT_SHADOW_COMPARE_PATH = old_compare_path

    def test_shadow_mode_never_blocks_live_writes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_checklist = h_cycle.H_SPLIT_CHECKLIST_PATH
            old_primary_checklist = h_cycle.H_PRIMARY_CHECKLIST_PATH
            old_state_path = h_cycle.SPLIT_SHADOW_STATE_PATH
            old_compare_path = h_cycle.SPLIT_SHADOW_COMPARE_PATH
            old_shadow_live_counts = h_cycle._h_shadow_live_artifact_counts
            try:
                h_cycle.H_SPLIT_CHECKLIST_PATH = root / "checklist_H_split.csv"
                h_cycle.H_PRIMARY_CHECKLIST_PATH = root / "checklist_H.csv"
                h_cycle.SPLIT_SHADOW_STATE_PATH = root / "split_shadow_state.json"
                h_cycle.SPLIT_SHADOW_COMPARE_PATH = root / "split_shadow_compare.csv"
                h_cycle._h_shadow_live_artifact_counts = lambda now_utc: (0, 0, "live_clean")
                h_cycle.H_PRIMARY_CHECKLIST_PATH.write_text(
                    "check,status,value,notes\nh_check_a,fail,1,x\nh_check_b,warn,1,y\n",
                    encoding="utf-8",
                )
                payload = h_cycle._resolve_h_split_gate(
                    now_utc=h_cycle._utc_now(),
                    run_id="20260218T110000Z",
                    mode_requested="shadow",
                    mode_effective="shadow",
                    state={"h_gate_health_run_utc": "2999-01-01T00:00:00Z"},
                )
                self.assertEqual(payload.get("h_gate_fail_count"), "0")
                self.assertEqual(payload.get("h_gate_warn_count"), "0")
                self.assertEqual(payload.get("h_gate_pending_fail_count"), "1")
                self.assertEqual(payload.get("h_gate_pending_warn_count"), "1")
                self.assertEqual(payload.get("h_gate_condition_status"), "pending_recheck")
                self.assertEqual(payload.get("h_gate_block_live_writes"), "0")
            finally:
                h_cycle.H_SPLIT_CHECKLIST_PATH = old_checklist
                h_cycle.H_PRIMARY_CHECKLIST_PATH = old_primary_checklist
                h_cycle.SPLIT_SHADOW_STATE_PATH = old_state_path
                h_cycle.SPLIT_SHADOW_COMPARE_PATH = old_compare_path
                h_cycle._h_shadow_live_artifact_counts = old_shadow_live_counts

    def test_gate_selection_uses_primary_checklist_even_when_split_exists(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_checklist = h_cycle.H_SPLIT_CHECKLIST_PATH
            old_primary_checklist = h_cycle.H_PRIMARY_CHECKLIST_PATH
            try:
                h_cycle.H_SPLIT_CHECKLIST_PATH = root / "checklist_H_split.csv"
                h_cycle.H_PRIMARY_CHECKLIST_PATH = root / "checklist_H.csv"
                h_cycle.H_SPLIT_CHECKLIST_PATH.write_text(
                    "check,status,value,notes\nh_check_a,ok,0,x\n",
                    encoding="utf-8",
                )

                path, source = h_cycle._choose_h_gate_checklist_path()
                self.assertEqual(path, h_cycle.H_PRIMARY_CHECKLIST_PATH)
                self.assertEqual(source, "flow_gate_primary_h_missing")

                h_cycle.H_PRIMARY_CHECKLIST_PATH.write_text(
                    "check,status,value,notes\nh_check_a,ok,0,x\n",
                    encoding="utf-8",
                )
                path, source = h_cycle._choose_h_gate_checklist_path()
                self.assertEqual(path, h_cycle.H_PRIMARY_CHECKLIST_PATH)
                self.assertEqual(source, "flow_gate_primary_h")
            finally:
                h_cycle.H_SPLIT_CHECKLIST_PATH = old_checklist
                h_cycle.H_PRIMARY_CHECKLIST_PATH = old_primary_checklist

    def test_effective_mode_auto_cutover_when_ready(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_mode = h_cycle.H_SPLIT_HEALTH_MODE
            old_state_path = h_cycle.SPLIT_SHADOW_STATE_PATH
            try:
                h_cycle.H_SPLIT_HEALTH_MODE = "shadow"
                h_cycle.SPLIT_SHADOW_STATE_PATH = root / "split_shadow_state.json"
                h_cycle.SPLIT_SHADOW_STATE_PATH.write_text(
                    '{"b_match_streak":10,"h_clean_streak":10,"ready_for_cutover":true,"updated_utc":"2026-02-18T11:00:00Z"}',
                    encoding="utf-8",
                )
                self.assertEqual(h_cycle._effective_h_split_mode(), "split")
            finally:
                h_cycle.H_SPLIT_HEALTH_MODE = old_mode
                h_cycle.SPLIT_SHADOW_STATE_PATH = old_state_path

    def test_shadow_live_artifact_counts_uses_terminal_fallback_for_publish_staleness(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_out = h_cycle.OUT
            old_log_path = h_cycle.H_CYCLE_LOG_PATH
            old_floor_path = h_cycle.PHASE1_RUNTIME_FLOOR_SNAPSHOT_PATH
            old_publish_info_path = h_cycle.H_CYCLE_LAST_PUBLISH_INFO_PATH
            old_terminal_info_path = h_cycle.H_CYCLE_LAST_TERMINAL_INFO_PATH
            try:
                now_utc = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
                h_cycle.OUT = root
                h_cycle.H_CYCLE_LOG_PATH = root / "H_cycle.log"
                h_cycle.PHASE1_RUNTIME_FLOOR_SNAPSHOT_PATH = root / "phase1_runtime_floor_snapshot_latest.csv"
                h_cycle.H_CYCLE_LAST_PUBLISH_INFO_PATH = root / "H_cycle_last_publish_info.txt"
                h_cycle.H_CYCLE_LAST_TERMINAL_INFO_PATH = root / "H_cycle_last_terminal_info.txt"

                listing_path = root / "listing_offer_snapshot_latest.csv"
                for p in [h_cycle.H_CYCLE_LOG_PATH, listing_path, h_cycle.PHASE1_RUNTIME_FLOOR_SNAPSHOT_PATH]:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text("ok\n", encoding="utf-8")
                    ts = now_utc.timestamp()
                    os.utime(p, (ts, ts))

                h_cycle.H_CYCLE_LAST_PUBLISH_INFO_PATH.write_text(
                    "run_id=old\nutc=2026-04-01T08:00:00Z\nstatus=ok\n",
                    encoding="utf-8",
                )
                stale_ts = datetime(2026, 4, 1, 8, 0, 0, tzinfo=timezone.utc).timestamp()
                os.utime(h_cycle.H_CYCLE_LAST_PUBLISH_INFO_PATH, (stale_ts, stale_ts))

                h_cycle.H_CYCLE_LAST_TERMINAL_INFO_PATH.write_text(
                    "run_id=recent\nutc=2026-04-01T11:59:00Z\nstate=failed\npublish_status=not_started\n",
                    encoding="utf-8",
                )
                fresh_ts = datetime(2026, 4, 1, 11, 59, 0, tzinfo=timezone.utc).timestamp()
                os.utime(h_cycle.H_CYCLE_LAST_TERMINAL_INFO_PATH, (fresh_ts, fresh_ts))

                fail_count, warn_count, notes = h_cycle._h_shadow_live_artifact_counts(now_utc)
                self.assertEqual(fail_count, 0)
                self.assertEqual(warn_count, 1)
                self.assertIn("h_publish_marker_freshness=warn", notes)
                self.assertIn("source=terminal_marker_fallback", notes)
            finally:
                h_cycle.OUT = old_out
                h_cycle.H_CYCLE_LOG_PATH = old_log_path
                h_cycle.PHASE1_RUNTIME_FLOOR_SNAPSHOT_PATH = old_floor_path
                h_cycle.H_CYCLE_LAST_PUBLISH_INFO_PATH = old_publish_info_path
                h_cycle.H_CYCLE_LAST_TERMINAL_INFO_PATH = old_terminal_info_path

    def test_no_publish_terminal_ok_is_disabled_in_wrapper(self) -> None:
        with mock.patch.dict(h_guard.os.environ, {"H_ALLOW_NO_PUBLISH_TERMINAL_OK": "0"}, clear=False):
            self.assertFalse(h_guard._allow_no_publish_terminal_ok("0"))

    def test_no_publish_terminal_ok_is_disabled_even_with_env_opt_in(self) -> None:
        with mock.patch.dict(h_guard.os.environ, {"H_ALLOW_NO_PUBLISH_TERMINAL_OK": "1"}, clear=False):
            self.assertFalse(h_guard._allow_no_publish_terminal_ok("1"))
            self.assertFalse(h_guard._allow_no_publish_terminal_ok("0"))

    def test_cycle_bool_parser_supports_handoff_flag(self) -> None:
        self.assertTrue(h_cycle._to_bool("1", default=False))
        self.assertTrue(h_cycle._to_bool("true", default=False))
        self.assertFalse(h_cycle._to_bool("0", default=True))
        self.assertFalse(h_cycle._to_bool("off", default=True))
        self.assertTrue(h_cycle._to_bool("unexpected", default=True))
        self.assertFalse(h_cycle._to_bool("unexpected", default=False))

    def test_runtime_readiness_marks_checklist_stale_when_newer_runtime_evidence_exists(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            now_utc = datetime(2026, 4, 3, 9, 30, 0, tzinfo=timezone.utc)
            run_id = "20260403T093000Z"

            old_out = h_cycle.OUT
            old_checklist = h_cycle.H_PRIMARY_CHECKLIST_PATH
            old_runtime_status = h_cycle.H_RUNTIME_STATUS_PATH
            old_terminal = h_cycle.H_CYCLE_LAST_TERMINAL_INFO_PATH
            old_publish = h_cycle.H_CYCLE_LAST_PUBLISH_INFO_PATH
            old_run_in_progress = h_cycle.H_RUN_IN_PROGRESS_PATH
            old_finalized = h_cycle.H_LAST_FINALIZED_RUN_ID_PATH
            old_readiness_json = h_cycle.H_RUNTIME_READINESS_PATH
            old_readiness_txt = h_cycle.H_RUNTIME_READINESS_TEXT_PATH
            old_exec = h_cycle.PHASE1_EXECUTION_LOG_PATH
            old_h110 = h_cycle.H110_SKU_LIFECYCLE_LOG_PATH
            old_alert_h = h_cycle.H_ALERT_STATE_PATH
            old_alert_global = h_cycle.H_ALERT_STATE_GLOBAL_PATH
            try:
                h_cycle.OUT = root
                h_cycle.H_PRIMARY_CHECKLIST_PATH = root / "checklist_H.csv"
                h_cycle.H_RUNTIME_STATUS_PATH = root / "H_runtime_status.json"
                h_cycle.H_CYCLE_LAST_TERMINAL_INFO_PATH = root / "H_cycle_last_terminal_info.txt"
                h_cycle.H_CYCLE_LAST_PUBLISH_INFO_PATH = root / "H_cycle_last_publish_info.txt"
                h_cycle.H_RUN_IN_PROGRESS_PATH = root / "H_run_in_progress.txt"
                h_cycle.H_LAST_FINALIZED_RUN_ID_PATH = root / "H_last_finalized_run_id.txt"
                h_cycle.H_RUNTIME_READINESS_PATH = root / "H_runtime_readiness.json"
                h_cycle.H_RUNTIME_READINESS_TEXT_PATH = root / "H_runtime_readiness.txt"
                h_cycle.PHASE1_EXECUTION_LOG_PATH = root / "execution_log.csv"
                h_cycle.H110_SKU_LIFECYCLE_LOG_PATH = root / "h110_lifecycle.csv"
                h_cycle.H_ALERT_STATE_PATH = root / "missing_alert_state_h.csv"
                h_cycle.H_ALERT_STATE_GLOBAL_PATH = root / "missing_alert_state_global.csv"

                h_cycle.H_PRIMARY_CHECKLIST_PATH.write_text(
                    "check,status,value,notes\nh_cycle_log_freshness,ok,0,healthy\n",
                    encoding="utf-8",
                )
                checklist_ts = (now_utc.timestamp() - 120.0)
                os.utime(h_cycle.H_PRIMARY_CHECKLIST_PATH, (checklist_ts, checklist_ts))

                h_cycle.H_RUNTIME_STATUS_PATH.write_text(
                    json.dumps({"utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"), "mode": "RUNNING", "pid": "1234"}),
                    encoding="utf-8",
                )
                runtime_ts = now_utc.timestamp()
                os.utime(h_cycle.H_RUNTIME_STATUS_PATH, (runtime_ts, runtime_ts))
                h_cycle.H_CYCLE_LAST_TERMINAL_INFO_PATH.write_text("run_id=test\nutc=2026-04-03T09:29:30Z\n", encoding="utf-8")
                os.utime(h_cycle.H_CYCLE_LAST_TERMINAL_INFO_PATH, (runtime_ts, runtime_ts))
                h_cycle.H_CYCLE_LAST_PUBLISH_INFO_PATH.write_text("run_id=test\nutc=2026-04-03T09:29:30Z\n", encoding="utf-8")
                os.utime(h_cycle.H_CYCLE_LAST_PUBLISH_INFO_PATH, (runtime_ts, runtime_ts))
                h_cycle.H_RUN_IN_PROGRESS_PATH.write_text(f"{run_id}\n", encoding="utf-8")
                os.utime(h_cycle.H_RUN_IN_PROGRESS_PATH, (runtime_ts, runtime_ts))
                h_cycle.H_LAST_FINALIZED_RUN_ID_PATH.write_text("20260403T090000Z\n", encoding="utf-8")
                os.utime(h_cycle.H_LAST_FINALIZED_RUN_ID_PATH, (runtime_ts, runtime_ts))

                h_cycle.PHASE1_EXECUTION_LOG_PATH.write_text(
                    "event_ts_utc\n2026-04-03T09:25:00Z\n",
                    encoding="utf-8",
                )
                exec_ts = now_utc.timestamp() - 30.0
                os.utime(h_cycle.PHASE1_EXECUTION_LOG_PATH, (exec_ts, exec_ts))
                h_cycle.H110_SKU_LIFECYCLE_LOG_PATH.write_text(
                    "event,event_ts_utc\nfinish,2026-04-03T09:26:00Z\n",
                    encoding="utf-8",
                )
                os.utime(h_cycle.H110_SKU_LIFECYCLE_LOG_PATH, (exec_ts, exec_ts))

                seller_snapshot = root / "snapshots" / "H" / run_id / "listing_offer_seller_snapshot.csv"
                seller_snapshot.parent.mkdir(parents=True, exist_ok=True)
                seller_snapshot.write_text("sku\nSKU-1\n", encoding="utf-8")

                h_cycle._write_runtime_readiness(
                    run_id=run_id,
                    manifest_final_state="completed",
                    item_offers_enabled=True,
                    now_utc=now_utc,
                )

                payload = json.loads(h_cycle.H_RUNTIME_READINESS_PATH.read_text(encoding="utf-8"))
                self.assertEqual(str(payload.get("checklist_age_fresh", "")), "1")
                self.assertEqual(str(payload.get("checklist_stale_vs_runtime_evidence", "")), "1")
                self.assertEqual(str(payload.get("checklist_stale_downgraded", "")), "0")
                self.assertEqual(str(payload.get("checklist_fresh", "")), "0")
                reasons = str(payload.get("reasons_csv", ""))
                self.assertIn("checklist_stale_vs_newer_runtime_evidence", reasons)
            finally:
                h_cycle.OUT = old_out
                h_cycle.H_PRIMARY_CHECKLIST_PATH = old_checklist
                h_cycle.H_RUNTIME_STATUS_PATH = old_runtime_status
                h_cycle.H_CYCLE_LAST_TERMINAL_INFO_PATH = old_terminal
                h_cycle.H_CYCLE_LAST_PUBLISH_INFO_PATH = old_publish
                h_cycle.H_RUN_IN_PROGRESS_PATH = old_run_in_progress
                h_cycle.H_LAST_FINALIZED_RUN_ID_PATH = old_finalized
                h_cycle.H_RUNTIME_READINESS_PATH = old_readiness_json
                h_cycle.H_RUNTIME_READINESS_TEXT_PATH = old_readiness_txt
                h_cycle.PHASE1_EXECUTION_LOG_PATH = old_exec
                h_cycle.H110_SKU_LIFECYCLE_LOG_PATH = old_h110
                h_cycle.H_ALERT_STATE_PATH = old_alert_h
                h_cycle.H_ALERT_STATE_GLOBAL_PATH = old_alert_global

    def test_runtime_floor_snapshot_clears_stale_execution_when_current_cycle_has_no_market_data(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out_root = root / "out"
            data_root = root / "data"
            run_id = "20990102T000000Z"
            now_utc = datetime(2099, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

            old_out = h_cycle.OUT
            old_data = h_cycle.DATA
            old_current_run_id = h_cycle._CURRENT_H_RUN_ID
            old_exec_path = h_cycle.PHASE1_EXECUTION_LOG_PATH
            old_trace_path = h_cycle.H_FLOOR_TRACE_PATH
            old_decision_path = h_cycle.H110_SKU_DECISION_LOG_PATH
            old_ceiling_path = h_cycle.SKU_CEILING_EVENTS_PATH
            old_snapshot_path = h_cycle.PHASE1_RUNTIME_FLOOR_SNAPSHOT_PATH
            old_proof_path = h_cycle.H_SELLER_DETAIL_PROOF_PATH
            old_history_path = h_cycle.H_SELLER_DETAIL_RECOVERY_HISTORY_PATH
            old_summary_path = h_cycle.H_SELLER_DETAIL_MEASUREMENT_SUMMARY_PATH
            old_alerts_path = h_cycle.H_SELLER_DETAIL_MEASUREMENT_ALERTS_PATH
            old_review_path = h_cycle.H_SELLER_DETAIL_OPERATOR_REVIEW_PATH
            old_build_proof = h_cycle._build_seller_detail_resolution_proof
            old_build_measurements = h_cycle._build_seller_detail_measurement_outputs
            old_build_alerts = h_cycle._build_seller_detail_measurement_alerts
            old_build_review = h_cycle._build_seller_detail_operator_review
            old_bucket_counts = h_cycle._seller_detail_operator_review_bucket_counts
            try:
                h_cycle.OUT = out_root
                h_cycle.DATA = data_root
                h_cycle._CURRENT_H_RUN_ID = run_id
                h_cycle.PHASE1_EXECUTION_LOG_PATH = out_root / "execution_log.csv"
                h_cycle.H_FLOOR_TRACE_PATH = out_root / "h_floor_trace.csv"
                h_cycle.H110_SKU_DECISION_LOG_PATH = out_root / "systems" / "H" / "live" / "h110_sku_decision_log.csv"
                h_cycle.SKU_CEILING_EVENTS_PATH = out_root / "sku_ceiling_events.csv"
                h_cycle.PHASE1_RUNTIME_FLOOR_SNAPSHOT_PATH = out_root / "phase1_runtime_floor_snapshot_latest.csv"
                h_cycle.H_SELLER_DETAIL_PROOF_PATH = out_root / "seller_detail_resolution_proof.csv"
                h_cycle.H_SELLER_DETAIL_RECOVERY_HISTORY_PATH = out_root / "seller_detail_recovery_history.csv"
                h_cycle.H_SELLER_DETAIL_MEASUREMENT_SUMMARY_PATH = out_root / "seller_detail_measurement_summary.csv"
                h_cycle.H_SELLER_DETAIL_MEASUREMENT_ALERTS_PATH = out_root / "seller_detail_measurement_alerts.csv"
                h_cycle.H_SELLER_DETAIL_OPERATOR_REVIEW_PATH = out_root / "seller_detail_operator_review.csv"

                (out_root / "phase1_sku_scope.csv").parent.mkdir(parents=True, exist_ok=True)
                pd.DataFrame(
                    [
                        {
                            "sku": "AX-NKNU-29C1",
                            "parked_flag": "0",
                            "asof_utc": "2099-01-02T00:00:00Z",
                        },
                        {
                            "sku": "PARK-SKU",
                            "parked_flag": "1",
                            "asof_utc": "2099-01-02T00:00:00Z",
                        }
                    ]
                ).to_csv(out_root / "phase1_sku_scope.csv", index=False)

                pd.DataFrame(
                    [
                        {
                            "sku": "AX-NKNU-29C1",
                            "event_ts_utc": "2099-01-01T00:00:00Z",
                            "state": "RAISE_FIND_LOSS",
                            "write_status": "NO_WRITE_REQUIRED",
                            "write_error": "",
                            "old_price_gbp": "10.49",
                            "new_price_gbp": "10.49",
                            "hard_floor_gbp": "10.49",
                            "final_ceiling_landed_gbp": "10.49",
                            "reason_codes_json": '["CPT_RISK_UNKNOWN_CONSERVATIVE_HOLD"]',
                        },
                        {
                            "sku": "PARK-SKU",
                            "event_ts_utc": "2099-01-01T00:00:00Z",
                            "state": "REGAIN",
                            "write_status": "APPLIED",
                            "write_error": "",
                            "old_price_gbp": "12.00",
                            "new_price_gbp": "11.50",
                            "hard_floor_gbp": "10.00",
                            "final_ceiling_landed_gbp": "13.00",
                            "reason_codes_json": '["TEST_STALE_WRITE"]',
                        }
                    ]
                ).to_csv(h_cycle.PHASE1_EXECUTION_LOG_PATH, index=False)

                pd.DataFrame(
                    [
                        {
                            "sku": "AX-NKNU-29C1",
                            "asof_utc": "2099-01-02T00:00:00Z",
                            "source_script": "test_trace",
                            "candidate_price_gbp": "10.49",
                            "floor_total_gbp": "10.49",
                            "break_even_total_gbp": "9.99",
                            "cogs_exvat_gbp": "5.00",
                            "fba_exvat_gbp": "1.00",
                            "referral_amount_gbp": "1.50",
                            "band_bucket": "STD",
                            "reason_codes_csv": "TRACE_OK",
                        },
                        {
                            "sku": "PARK-SKU",
                            "asof_utc": "2099-01-02T00:00:00Z",
                            "source_script": "test_trace",
                            "candidate_price_gbp": "11.50",
                            "floor_total_gbp": "10.00",
                            "break_even_total_gbp": "9.50",
                            "cogs_exvat_gbp": "5.00",
                            "fba_exvat_gbp": "1.00",
                            "referral_amount_gbp": "1.50",
                            "band_bucket": "STD",
                            "reason_codes_csv": "TRACE_OK",
                        }
                    ]
                ).to_csv(h_cycle.H_FLOOR_TRACE_PATH, index=False)

                h_cycle.H110_SKU_DECISION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
                pd.DataFrame(
                    [
                        {
                            "decision_ts_utc": "2099-01-02T00:00:00Z",
                            "run_id": run_id,
                            "sku": "AX-NKNU-29C1",
                            "repricing_enabled": "1",
                            "observe_effective": "1",
                            "write_effective": "1",
                            "market_data_present": "0",
                            "decision": "skip_no_market_data",
                            "reason_code": "eligible",
                        },
                        {
                            "decision_ts_utc": "2099-01-02T00:00:00Z",
                            "run_id": run_id,
                            "sku": "PARK-SKU",
                            "repricing_enabled": "1",
                            "observe_effective": "1",
                            "write_effective": "1",
                            "market_data_present": "1",
                            "decision": "execute",
                            "reason_code": "eligible",
                        }
                    ]
                ).to_csv(h_cycle.H110_SKU_DECISION_LOG_PATH, index=False)

                h_cycle._build_seller_detail_resolution_proof = lambda **kwargs: pd.DataFrame(
                    [
                        {
                            "pending_retry_count": "0",
                            "recovered_count": "0",
                            "supp_gated_detail_count": "0",
                            "supp_blocked_count": "0",
                        }
                    ]
                )
                h_cycle._build_seller_detail_measurement_outputs = lambda **kwargs: (
                    pd.DataFrame(columns=["snapshot_utc"]),
                    pd.DataFrame(
                        [
                            {
                                "amazon_missing_likely_count": "0",
                                "retry_exhausted_count": "0",
                                "newly_recovered_count": "0",
                                "stale_pending_over_threshold_count": "0",
                            }
                        ]
                    ),
                )
                h_cycle._build_seller_detail_measurement_alerts = lambda **kwargs: pd.DataFrame(
                    columns=["status"]
                )
                h_cycle._build_seller_detail_operator_review = lambda **kwargs: pd.DataFrame(
                    columns=["review_bucket"]
                )
                h_cycle._seller_detail_operator_review_bucket_counts = lambda df: {
                    "amazon_upstream": 0,
                    "local_selection": 0,
                    "retry_exhausted_review": 0,
                    "genuine_blocker": 0,
                }

                payload = h_cycle._write_phase1_runtime_floor_snapshot(now_utc)
                self.assertEqual(payload.get("phase1_runtime_floor_snapshot_status"), "ok")

                snapshot_df = pd.read_csv(h_cycle.PHASE1_RUNTIME_FLOOR_SNAPSHOT_PATH, dtype=str).fillna("")
                row = snapshot_df.loc[snapshot_df["sku"].astype(str).str.strip().eq("AX-NKNU-29C1")]
                self.assertEqual(len(row.index), 1)
                out_row = row.iloc[0]

                self.assertEqual(str(out_row.get("execution_event_ts_utc", "")).strip(), "")
                self.assertEqual(str(out_row.get("execution_reason_codes_json", "")).strip(), "")
                self.assertEqual(str(out_row.get("execution_write_status", "")).strip(), "READ_ONLY_NO_WRITE")
                self.assertEqual(str(out_row.get("stale_execution_context_cleared_flag", "")).strip(), "1")
                self.assertEqual(str(out_row.get("stale_execution_event_ts_utc", "")).strip(), "2099-01-01T00:00:00Z")
                self.assertEqual(
                    str(out_row.get("stale_execution_reason_codes_json", "")).strip(),
                    '["CPT_RISK_UNKNOWN_CONSERVATIVE_HOLD"]',
                )
                self.assertEqual(str(out_row.get("current_cycle_decision", "")).strip(), "skip_no_market_data")
                self.assertEqual(str(out_row.get("current_cycle_market_data_present", "")).strip(), "0")
                self.assertEqual(
                    str(out_row.get("current_cycle_blocker_code", "")).strip(),
                    "MARKET_DATA_MISSING_CURRENT_CYCLE",
                )
                self.assertEqual(str(out_row.get("truth_status", "")).strip(), "READ_ONLY")

                parked_row = snapshot_df.loc[snapshot_df["sku"].astype(str).str.strip().eq("PARK-SKU")]
                self.assertEqual(len(parked_row.index), 1)
                parked_out = parked_row.iloc[0]
                self.assertEqual(str(parked_out.get("execution_event_ts_utc", "")).strip(), "")
                self.assertEqual(str(parked_out.get("execution_reason_codes_json", "")).strip(), "")
                self.assertEqual(str(parked_out.get("execution_write_status", "")).strip(), "NO_WRITE_REQUIRED")
                self.assertEqual(str(parked_out.get("unified_writer_outcome", "")).strip(), "NO_WRITE_REQUIRED")
                self.assertEqual(str(parked_out.get("write_attempted_flag", "")).strip(), "0")
                self.assertEqual(str(parked_out.get("write_applied_flag", "")).strip(), "0")
                self.assertEqual(str(parked_out.get("truth_status", "")).strip(), "PARKED")
            finally:
                h_cycle.OUT = old_out
                h_cycle.DATA = old_data
                h_cycle._CURRENT_H_RUN_ID = old_current_run_id
                h_cycle.PHASE1_EXECUTION_LOG_PATH = old_exec_path
                h_cycle.H_FLOOR_TRACE_PATH = old_trace_path
                h_cycle.H110_SKU_DECISION_LOG_PATH = old_decision_path
                h_cycle.SKU_CEILING_EVENTS_PATH = old_ceiling_path
                h_cycle.PHASE1_RUNTIME_FLOOR_SNAPSHOT_PATH = old_snapshot_path
                h_cycle.H_SELLER_DETAIL_PROOF_PATH = old_proof_path
                h_cycle.H_SELLER_DETAIL_RECOVERY_HISTORY_PATH = old_history_path
                h_cycle.H_SELLER_DETAIL_MEASUREMENT_SUMMARY_PATH = old_summary_path
                h_cycle.H_SELLER_DETAIL_MEASUREMENT_ALERTS_PATH = old_alerts_path
                h_cycle.H_SELLER_DETAIL_OPERATOR_REVIEW_PATH = old_review_path
                h_cycle._build_seller_detail_resolution_proof = old_build_proof
                h_cycle._build_seller_detail_measurement_outputs = old_build_measurements
                h_cycle._build_seller_detail_measurement_alerts = old_build_alerts
                h_cycle._build_seller_detail_operator_review = old_build_review
                h_cycle._seller_detail_operator_review_bucket_counts = old_bucket_counts

    def test_runtime_readiness_downgrades_stale_checklist_when_active_alert_state_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            now_utc = datetime(2026, 4, 3, 9, 30, 0, tzinfo=timezone.utc)
            run_id = "20260403T093000Z"

            old_out = h_cycle.OUT
            old_checklist = h_cycle.H_PRIMARY_CHECKLIST_PATH
            old_runtime_status = h_cycle.H_RUNTIME_STATUS_PATH
            old_terminal = h_cycle.H_CYCLE_LAST_TERMINAL_INFO_PATH
            old_publish = h_cycle.H_CYCLE_LAST_PUBLISH_INFO_PATH
            old_run_in_progress = h_cycle.H_RUN_IN_PROGRESS_PATH
            old_finalized = h_cycle.H_LAST_FINALIZED_RUN_ID_PATH
            old_readiness_json = h_cycle.H_RUNTIME_READINESS_PATH
            old_readiness_txt = h_cycle.H_RUNTIME_READINESS_TEXT_PATH
            old_exec = h_cycle.PHASE1_EXECUTION_LOG_PATH
            old_h110 = h_cycle.H110_SKU_LIFECYCLE_LOG_PATH
            old_alert_h = h_cycle.H_ALERT_STATE_PATH
            old_alert_global = h_cycle.H_ALERT_STATE_GLOBAL_PATH
            try:
                h_cycle.OUT = root
                h_cycle.H_PRIMARY_CHECKLIST_PATH = root / "checklist_H.csv"
                h_cycle.H_RUNTIME_STATUS_PATH = root / "H_runtime_status.json"
                h_cycle.H_CYCLE_LAST_TERMINAL_INFO_PATH = root / "H_cycle_last_terminal_info.txt"
                h_cycle.H_CYCLE_LAST_PUBLISH_INFO_PATH = root / "H_cycle_last_publish_info.txt"
                h_cycle.H_RUN_IN_PROGRESS_PATH = root / "H_run_in_progress.txt"
                h_cycle.H_LAST_FINALIZED_RUN_ID_PATH = root / "H_last_finalized_run_id.txt"
                h_cycle.H_RUNTIME_READINESS_PATH = root / "H_runtime_readiness.json"
                h_cycle.H_RUNTIME_READINESS_TEXT_PATH = root / "H_runtime_readiness.txt"
                h_cycle.PHASE1_EXECUTION_LOG_PATH = root / "execution_log.csv"
                h_cycle.H110_SKU_LIFECYCLE_LOG_PATH = root / "h110_lifecycle.csv"
                h_cycle.H_ALERT_STATE_PATH = root / "system_health_alert_state_H.csv"
                h_cycle.H_ALERT_STATE_GLOBAL_PATH = root / "system_health_alert_state.csv"

                h_cycle.H_PRIMARY_CHECKLIST_PATH.write_text(
                    "check,status,value,notes\nh_cycle_log_freshness,fail,1,stale_fail\n",
                    encoding="utf-8",
                )
                checklist_ts = now_utc.timestamp() - 120.0
                os.utime(h_cycle.H_PRIMARY_CHECKLIST_PATH, (checklist_ts, checklist_ts))

                h_cycle.H_ALERT_STATE_PATH.write_text(
                    "check,status,first_seen_utc,last_seen_utc,consecutive_runs\n",
                    encoding="utf-8",
                )

                h_cycle.H_RUNTIME_STATUS_PATH.write_text(
                    json.dumps({"utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"), "mode": "RUNNING", "pid": "1234"}),
                    encoding="utf-8",
                )
                runtime_ts = now_utc.timestamp()
                os.utime(h_cycle.H_RUNTIME_STATUS_PATH, (runtime_ts, runtime_ts))
                h_cycle.H_CYCLE_LAST_TERMINAL_INFO_PATH.write_text("run_id=test\nutc=2026-04-03T09:29:30Z\n", encoding="utf-8")
                os.utime(h_cycle.H_CYCLE_LAST_TERMINAL_INFO_PATH, (runtime_ts, runtime_ts))
                h_cycle.H_CYCLE_LAST_PUBLISH_INFO_PATH.write_text("run_id=test\nutc=2026-04-03T09:29:30Z\n", encoding="utf-8")
                os.utime(h_cycle.H_CYCLE_LAST_PUBLISH_INFO_PATH, (runtime_ts, runtime_ts))
                h_cycle.H_RUN_IN_PROGRESS_PATH.write_text(f"{run_id}\n", encoding="utf-8")
                os.utime(h_cycle.H_RUN_IN_PROGRESS_PATH, (runtime_ts, runtime_ts))
                h_cycle.H_LAST_FINALIZED_RUN_ID_PATH.write_text("20260403T090000Z\n", encoding="utf-8")
                os.utime(h_cycle.H_LAST_FINALIZED_RUN_ID_PATH, (runtime_ts, runtime_ts))

                h_cycle.PHASE1_EXECUTION_LOG_PATH.write_text(
                    "event_ts_utc\n2026-04-03T09:25:00Z\n",
                    encoding="utf-8",
                )
                exec_ts = now_utc.timestamp() - 30.0
                os.utime(h_cycle.PHASE1_EXECUTION_LOG_PATH, (exec_ts, exec_ts))
                h_cycle.H110_SKU_LIFECYCLE_LOG_PATH.write_text(
                    "event,event_ts_utc\nfinish,2026-04-03T09:26:00Z\n",
                    encoding="utf-8",
                )
                os.utime(h_cycle.H110_SKU_LIFECYCLE_LOG_PATH, (exec_ts, exec_ts))

                seller_snapshot = root / "snapshots" / "H" / run_id / "listing_offer_seller_snapshot.csv"
                seller_snapshot.parent.mkdir(parents=True, exist_ok=True)
                seller_snapshot.write_text("sku\nSKU-1\n", encoding="utf-8")

                h_cycle._write_runtime_readiness(
                    run_id=run_id,
                    manifest_final_state="completed",
                    item_offers_enabled=True,
                    now_utc=now_utc,
                )

                payload = json.loads(h_cycle.H_RUNTIME_READINESS_PATH.read_text(encoding="utf-8"))
                self.assertEqual(str(payload.get("checklist_stale_downgraded", "")), "1")
                self.assertEqual(str(payload.get("checklist_fresh", "")), "1")
                self.assertEqual(str(payload.get("checklist_fail_count", "")), "0")
                self.assertEqual(str(payload.get("checklist_fail_count_raw", "")), "1")
                reasons = str(payload.get("reasons_csv", ""))
                self.assertIn("checklist_stale_downgraded_to_active_alert_state", reasons)
            finally:
                h_cycle.OUT = old_out
                h_cycle.H_PRIMARY_CHECKLIST_PATH = old_checklist
                h_cycle.H_RUNTIME_STATUS_PATH = old_runtime_status
                h_cycle.H_CYCLE_LAST_TERMINAL_INFO_PATH = old_terminal
                h_cycle.H_CYCLE_LAST_PUBLISH_INFO_PATH = old_publish
                h_cycle.H_RUN_IN_PROGRESS_PATH = old_run_in_progress
                h_cycle.H_LAST_FINALIZED_RUN_ID_PATH = old_finalized
                h_cycle.H_RUNTIME_READINESS_PATH = old_readiness_json
                h_cycle.H_RUNTIME_READINESS_TEXT_PATH = old_readiness_txt
                h_cycle.PHASE1_EXECUTION_LOG_PATH = old_exec
                h_cycle.H110_SKU_LIFECYCLE_LOG_PATH = old_h110
                h_cycle.H_ALERT_STATE_PATH = old_alert_h
                h_cycle.H_ALERT_STATE_GLOBAL_PATH = old_alert_global

    def test_strategy_sample_live_snapshot_reports_stale_vs_checklist(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            daily_path = root / "h_strategy_outcome_daily.csv"
            daily_path.write_text(
                "\n".join(
                    [
                        "asof_date,scenario_type,chosen_tactic,decision_rows,sample_min_rows",
                        "2026-04-17,multi_seller_ladder_cap,REGAIN_LADDER_CAP,10,150",
                        "2026-04-18,multi_seller_ladder_cap,REGAIN_LADDER_CAP,67,150",
                        "2026-04-18,single_rival_reset,REGAIN_SINGLE_RIVAL_RESET,5,30",
                        "2026-04-18,suppression_reactivation,SUPPRESSION_REACTIVATION,40,20",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            mtime = datetime(2026, 4, 18, 7, 2, 35, tzinfo=timezone.utc).timestamp()
            os.utime(daily_path, (mtime, mtime))

            snapshot = h_cycle._h_strategy_sample_size_live_snapshot(
                daily_path,
                "2026-04-18T05:06:22Z",
            )

            self.assertEqual(snapshot.get("h_strategy_sample_live_status"), "ok")
            self.assertEqual(snapshot.get("h_strategy_sample_live_asof_date"), "2026-04-18")
            self.assertEqual(snapshot.get("h_strategy_sample_live_stale_vs_checklist"), "1")
            self.assertEqual(snapshot.get("h_strategy_sample_live_multi_seller_ladder_cap_decision_rows"), "67")
            self.assertEqual(snapshot.get("h_strategy_sample_live_multi_seller_ladder_cap_provisional_flag"), "1")
            self.assertEqual(snapshot.get("h_strategy_sample_live_single_rival_reset_decision_rows"), "5")
            self.assertEqual(snapshot.get("h_strategy_sample_live_single_rival_reset_provisional_flag"), "1")
            self.assertEqual(snapshot.get("h_strategy_sample_live_suppression_reactivation_decision_rows"), "40")
            self.assertEqual(snapshot.get("h_strategy_sample_live_suppression_reactivation_provisional_flag"), "0")


if __name__ == "__main__":
    unittest.main()
