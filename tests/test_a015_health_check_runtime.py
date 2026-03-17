import os
import sys
import tempfile
import unittest
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.flows.A import A015_build_system_health_check as a015


class A015HealthCheckRuntimeTests(unittest.TestCase):
    def test_read_json_returns_default_on_missing_or_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            missing_path = root / "missing.json"
            default = {"a": 1}
            self.assertEqual(a015._read_json(missing_path, default=default), default)

            bad_path = root / "bad.json"
            bad_path.write_text("{not-json", encoding="utf-8")
            self.assertEqual(a015._read_json(bad_path, default=default), default)

    def test_b_cycle_recent_fail_stats_recovered_vs_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            log_path = root / "B_cycle.log"
            log_path.write_text(
                "\n".join(
                    [
                        "2026-02-17T12:00:00Z [2026-02-17T12:00:00Z] fail A015_build_system_health_check.py end_of_cycle rc=2",
                        "2026-02-17T12:00:10Z [2026-02-17T12:00:00Z] warn A015_build_system_health_check.py end_of_cycle",
                        "2026-02-17T12:10:00Z [2026-02-17T12:10:00Z] fail B004_build_order_master.py after 5",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            stats = a015._b_cycle_recent_fail_stats(log_path, window_hours=48)
            self.assertEqual(int(stats.get("raw_fail_count", 0)), 2)
            self.assertEqual(int(stats.get("recovered_count", 0)), 1)
            self.assertEqual(int(stats.get("unresolved_count", 0)), 1)
            sample = stats.get("unresolved_sample", [])
            self.assertTrue(sample)
            self.assertIn("fail B004_build_order_master.py", str(sample[0]))

    def test_run_main_fail_closed_returns_2_and_writes_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "out"
            old_values = {
                "OUT": a015.OUT,
                "CHECKLIST_CSV": a015.CHECKLIST_CSV,
                "CYCLE_ALERT_DIR": a015.CYCLE_ALERT_DIR,
                "ALERT_STATE_CSV": a015.ALERT_STATE_CSV,
                "HEALTH_STATUS_CSV": a015.HEALTH_STATUS_CSV,
            }
            try:
                a015.OUT = out
                a015.CHECKLIST_CSV = out / "system_health_checklist.csv"
                a015.CYCLE_ALERT_DIR = out / "cycle_alerts"
                a015.ALERT_STATE_CSV = out / "system_health_alert_state.csv"
                a015.HEALTH_STATUS_CSV = out / "health_status.csv"

                def _explode() -> None:
                    raise RuntimeError("boom")

                rc = a015._run_main_fail_closed(_explode)
                self.assertEqual(rc, 2)
                self.assertTrue(a015.CHECKLIST_CSV.exists())
                df = pd.read_csv(a015.CHECKLIST_CSV, dtype=str).fillna("")
                row = df.loc[df["check"].eq("a015_runtime_exception")]
                self.assertFalse(row.empty)
                self.assertTrue((row["status"] == "fail").any())
                self.assertTrue((a015.CYCLE_ALERT_DIR / "checklist_all.csv").exists())
            finally:
                a015.OUT = old_values["OUT"]
                a015.CHECKLIST_CSV = old_values["CHECKLIST_CSV"]
                a015.CYCLE_ALERT_DIR = old_values["CYCLE_ALERT_DIR"]
                a015.ALERT_STATE_CSV = old_values["ALERT_STATE_CSV"]
                a015.HEALTH_STATUS_CSV = old_values["HEALTH_STATUS_CSV"]

    def test_fees_failed_rows_today_uses_timestamp_column(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fees_path = root / "fees_failed.csv"
            pd.DataFrame(
                [
                    {"seller_sku": "SKU1", "error_10": "err", "failure_recorded_utc": "2026-02-17T05:00:00Z"},
                    {"seller_sku": "SKU2", "error_10": "err", "failure_recorded_utc": "2026-02-16T23:00:00Z"},
                ]
            ).to_csv(fees_path, index=False)

            stats = a015._fees_failed_rows_today(
                fees_path,
                datetime(2026, 2, 17, 12, 0, 0, tzinfo=timezone.utc),
            )
            self.assertEqual(int(stats.get("count", 0)), 1)
            sample = stats.get("sample_skus", [])
            self.assertTrue(sample)
            self.assertIn("SKU1", str(sample[0]))
            self.assertFalse(bool(stats.get("read_error", False)))

    def test_fees_failed_rows_today_uses_file_mtime_when_timestamp_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fees_path = root / "fees_failed.csv"
            pd.DataFrame([{"seller_sku": "SKU1", "error_10": "err"}]).to_csv(fees_path, index=False)
            stale_ts = datetime(2026, 2, 16, 23, 0, 0, tzinfo=timezone.utc).timestamp()
            os.utime(fees_path, (stale_ts, stale_ts))

            stats = a015._fees_failed_rows_today(
                fees_path,
                datetime(2026, 2, 17, 12, 0, 0, tzinfo=timezone.utc),
            )
            self.assertEqual(int(stats.get("count", 0)), 0)

    def test_h_floor_truth_guardrails_rows_present(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "out"
            data = root / "data"
            out.mkdir(parents=True, exist_ok=True)
            data.mkdir(parents=True, exist_ok=True)

            policy_path = root / "h_floor_vat_policy.json"
            policy_path.write_text(
                '{"vat_registered": true, "recover_input_vat_on_cogs": true, "recover_input_vat_on_fees": true}',
                encoding="utf-8",
            )

            pd.DataFrame(
                [
                    {
                        "asof_utc": "2026-02-17T13:00:00Z",
                        "sku": "SKU-1",
                        "order_id": "",
                        "order_date_utc": "",
                        "candidate_price_gbp": "11.97",
                        "vat_rate_market": "0.200000",
                        "cogs_total_gbp": "5.35",
                        "fba_total_gbp": "3.05",
                        "commission_total_gbp": "0.96",
                        "digital_fee_total_gbp": "0.08",
                        "fixed_total_gbp": "0.00",
                        "break_even_total_gbp": "11.33",
                        "temp_floor_10roi_gbp": "11.97",
                        "source_script": "H110_run_phase1_h_pilot",
                    }
                ]
            ).to_csv(out / "sku_temp_floor_snapshot.csv", index=False)

            pd.DataFrame(
                [
                    {
                        "seller_sku": "SKU-1",
                        "cost_per_unit": "5.35",
                        "status": "available",
                        "sort_rank": "1",
                    }
                ]
            ).to_csv(out / "token_ledger_live.csv", index=False)
            pd.DataFrame(columns=["seller_sku", "cogs_exvat", "cogs_total"]).to_csv(out / "token_cogs_ledger.csv", index=False)
            pd.DataFrame(columns=["event_ts_utc", "profit_floor_cogs_exvat_gbp", "profit_floor_cogs_total_gbp"]).to_csv(
                data / "repricing_live_execution_log.csv", index=False
            )

            pd.DataFrame(
                [
                    {
                        "asof_utc": "2026-02-17T13:00:00Z",
                        "source_script": "H110_run_phase1_h_pilot",
                        "sku": "SKU-1",
                        "candidate_price_gbp": "11.97",
                        "floor_total_gbp": "11.97",
                        "sale_exvat_gbp": "9.975",
                        "break_even_exvat_gbp": "9.440",
                        "break_even_total_gbp": "11.33",
                        "profit_exvat_at_floor": "0.000000",
                        "vat_rate": "0.200000",
                        "cogs_exvat_gbp": "5.350",
                        "fba_exvat_gbp": "3.050",
                        "referral_pct": "0.080000",
                        "referral_amount_gbp": "0.960",
                        "digital_fee_exvat_gbp": "0.080",
                        "margin_exvat_gbp": "0.535",
                        "source_cogs": "token_ledger_live_next_available",
                        "source_fba": "L3_BAND_100",
                        "source_referral": "L3_BAND_100",
                        "band_bucket": "100",
                        "referral_min_fee_applied": "0",
                        "reason_codes_csv": "",
                        "used_order_data_flag": "0",
                    }
                ]
            ).to_csv(out / "h_floor_truth_trace.csv", index=False)

            old_values = {
                "OUT": a015.OUT,
                "DATA": a015.DATA,
                "H_FLOOR_VAT_POLICY_PATH": a015.H_FLOOR_VAT_POLICY_PATH,
                "H_TEMP_FLOOR_SNAPSHOT_PATH": a015.H_TEMP_FLOOR_SNAPSHOT_PATH,
                "H_FLOOR_TRUTH_TRACE_PATH": a015.H_FLOOR_TRUTH_TRACE_PATH,
                "H_LEGACY_EXECUTION_LOG_PATH": a015.H_LEGACY_EXECUTION_LOG_PATH,
            }
            try:
                a015.OUT = out
                a015.DATA = data
                a015.H_FLOOR_VAT_POLICY_PATH = policy_path
                a015.H_TEMP_FLOOR_SNAPSHOT_PATH = out / "sku_temp_floor_snapshot.csv"
                a015.H_FLOOR_TRUTH_TRACE_PATH = out / "h_floor_truth_trace.csv"
                a015.H_LEGACY_EXECUTION_LOG_PATH = data / "repricing_live_execution_log.csv"

                rows: list[dict[str, str]] = []
                a015._h_floor_policy_checks(rows, datetime(2026, 2, 17, 15, 0, 0, tzinfo=timezone.utc))
            finally:
                a015.OUT = old_values["OUT"]
                a015.DATA = old_values["DATA"]
                a015.H_FLOOR_VAT_POLICY_PATH = old_values["H_FLOOR_VAT_POLICY_PATH"]
                a015.H_TEMP_FLOOR_SNAPSHOT_PATH = old_values["H_TEMP_FLOOR_SNAPSHOT_PATH"]
                a015.H_FLOOR_TRUTH_TRACE_PATH = old_values["H_FLOOR_TRUTH_TRACE_PATH"]
                a015.H_LEGACY_EXECUTION_LOG_PATH = old_values["H_LEGACY_EXECUTION_LOG_PATH"]

            by_check = {str(r.get("check", "")): str(r.get("status", "")) for r in rows}
            self.assertEqual(by_check.get("h_floor_no_order_inputs"), "ok")
            self.assertEqual(by_check.get("h_floor_referral_band_integrity"), "ok")
            self.assertEqual(by_check.get("h_floor_referral_source_coverage"), "ok")
            self.assertEqual(by_check.get("h_floor_formula_consistency"), "ok")

    def test_cycle_stale_lock_check_clears_dead_pid_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lock_path = root / "H_pricing_cycle.lock"
            lock_path.write_text(
                "H|pid=999999|run_id=20260314T041153Z|start=2026-03-14T04:11:53Z|heartbeat=2026-03-14T04:12:00Z\n",
                encoding="utf-8",
            )
            rows: list[dict[str, str]] = []
            a015._cycle_stale_lock_check(
                rows,
                "h_cycle_stale_lock",
                [lock_path],
                now_utc=datetime(2026, 3, 14, 6, 16, 48, tzinfo=timezone.utc),
            )
            row = next((r for r in rows if r.get("check") == "h_cycle_stale_lock"), {})
            self.assertEqual(str(row.get("status", "")), "ok")
            self.assertEqual(str(row.get("value", "")), "0")
            self.assertIn("cleared_stale=", str(row.get("notes", "")))
            self.assertFalse(lock_path.exists())

    def test_cycle_stale_lock_check_fails_on_active_pid_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lock_1 = root / "H_pricing_cycle.lock"
            lock_2 = root / "H_pricing_cycle.legacy.lock"
            lock_1.write_text(
                "H|pid=11111|run_id=20260314T041153Z|start=2026-03-14T04:11:53Z|heartbeat=2026-03-14T06:16:00Z\n",
                encoding="utf-8",
            )
            lock_2.write_text(
                "H|pid=22222|run_id=20260314T051153Z|start=2026-03-14T05:11:53Z|heartbeat=2026-03-14T06:16:00Z\n",
                encoding="utf-8",
            )
            rows: list[dict[str, str]] = []
            old_pid_alive = a015._pid_alive
            try:
                a015._pid_alive = lambda pid: bool(pid in {11111, 22222})  # type: ignore[assignment]
                a015._cycle_stale_lock_check(
                    rows,
                    "h_cycle_stale_lock",
                    [lock_1, lock_2],
                    now_utc=datetime(2026, 3, 14, 6, 16, 48, tzinfo=timezone.utc),
                )
            finally:
                a015._pid_alive = old_pid_alive  # type: ignore[assignment]
            row = next((r for r in rows if r.get("check") == "h_cycle_stale_lock"), {})
            self.assertEqual(str(row.get("status", "")), "fail")
            self.assertEqual(str(row.get("value", "")), "2")
            self.assertIn("active_conflict=", str(row.get("notes", "")))

    def test_h_floor_cogs_basis_drift_prefers_trace_for_latest_asof(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "out"
            data = root / "data"
            out.mkdir(parents=True, exist_ok=True)
            data.mkdir(parents=True, exist_ok=True)

            policy_path = root / "h_floor_vat_policy.json"
            policy_path.write_text(
                '{"vat_registered": true, "recover_input_vat_on_cogs": true, "recover_input_vat_on_fees": true}',
                encoding="utf-8",
            )

            pd.DataFrame(
                [
                    {"asof_utc": "2026-03-14T04:08:54Z", "sku": "A2-T2AC-TW3L", "cogs_total_gbp": "4.44"},
                    {"asof_utc": "2026-03-14T04:08:54Z", "sku": "SKU-2", "cogs_total_gbp": "5.10"},
                ]
            ).to_csv(out / "sku_temp_floor_snapshot.csv", index=False)
            pd.DataFrame(
                [
                    {"asof_utc": "2026-03-14T04:08:54Z", "sku": "A2-T2AC-TW3L", "cogs_exvat_gbp": "4.440"},
                    {"asof_utc": "2026-03-14T04:08:54Z", "sku": "SKU-2", "cogs_exvat_gbp": "5.100"},
                ]
            ).to_csv(out / "h_floor_truth_trace.csv", index=False)
            pd.DataFrame(
                [
                    {"seller_sku": "A2-T2AC-TW3L", "cost_per_unit": "4.51", "status": "available", "sort_rank": "1"},
                    {"seller_sku": "SKU-2", "cost_per_unit": "5.19", "status": "available", "sort_rank": "1"},
                ]
            ).to_csv(out / "token_ledger_live.csv", index=False)
            pd.DataFrame(columns=["seller_sku", "cogs_exvat", "cogs_total"]).to_csv(out / "token_cogs_ledger.csv", index=False)
            pd.DataFrame(columns=["event_ts_utc", "profit_floor_cogs_exvat_gbp", "profit_floor_cogs_total_gbp"]).to_csv(
                data / "repricing_live_execution_log.csv", index=False
            )

            old_values = {
                "OUT": a015.OUT,
                "DATA": a015.DATA,
                "H_FLOOR_VAT_POLICY_PATH": a015.H_FLOOR_VAT_POLICY_PATH,
                "H_TEMP_FLOOR_SNAPSHOT_PATH": a015.H_TEMP_FLOOR_SNAPSHOT_PATH,
                "H_FLOOR_TRUTH_TRACE_PATH": a015.H_FLOOR_TRUTH_TRACE_PATH,
                "TOKEN_LEDGER_PATH": a015.TOKEN_LEDGER_PATH,
                "H_LEGACY_EXECUTION_LOG_PATH": a015.H_LEGACY_EXECUTION_LOG_PATH,
            }
            try:
                a015.OUT = out
                a015.DATA = data
                a015.H_FLOOR_VAT_POLICY_PATH = policy_path
                a015.H_TEMP_FLOOR_SNAPSHOT_PATH = out / "sku_temp_floor_snapshot.csv"
                a015.H_FLOOR_TRUTH_TRACE_PATH = out / "h_floor_truth_trace.csv"
                a015.TOKEN_LEDGER_PATH = out / "token_ledger_live.csv"
                a015.H_LEGACY_EXECUTION_LOG_PATH = data / "repricing_live_execution_log.csv"
                rows: list[dict[str, str]] = []
                a015._h_floor_policy_checks(rows, datetime(2026, 3, 14, 6, 16, 48, tzinfo=timezone.utc))
            finally:
                a015.OUT = old_values["OUT"]
                a015.DATA = old_values["DATA"]
                a015.H_FLOOR_VAT_POLICY_PATH = old_values["H_FLOOR_VAT_POLICY_PATH"]
                a015.H_TEMP_FLOOR_SNAPSHOT_PATH = old_values["H_TEMP_FLOOR_SNAPSHOT_PATH"]
                a015.H_FLOOR_TRUTH_TRACE_PATH = old_values["H_FLOOR_TRUTH_TRACE_PATH"]
                a015.TOKEN_LEDGER_PATH = old_values["TOKEN_LEDGER_PATH"]
                a015.H_LEGACY_EXECUTION_LOG_PATH = old_values["H_LEGACY_EXECUTION_LOG_PATH"]

            row = next((r for r in rows if r.get("check") == "h_floor_phase1_cogs_basis_drift"), {})
            self.assertEqual(str(row.get("status", "")), "ok")
            self.assertEqual(str(row.get("value", "")), "0")
            self.assertIn("expected_source=trace_latest_asof", str(row.get("notes", "")))

    def test_phase1_rollout_checks_excludes_dropped_from_non_parked_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "out"
            data = root / "data"
            out.mkdir(parents=True, exist_ok=True)
            data.mkdir(parents=True, exist_ok=True)

            pd.DataFrame(
                [
                    {
                        "asof_utc": "2026-02-21T06:00:00Z",
                        "sku": "SKU_ACTIVE_OOS",
                        "asin": "ASIN1",
                        "sale_status": "active",
                        "merchant_status": "inactive",
                        "in_stock_flag": "0",
                        "writer_mode": "READ_ONLY",
                        "parked_flag": "0",
                        "park_reason_codes": "PARK_OUT_OF_STOCK",
                    },
                    {
                        "asof_utc": "2026-02-21T06:00:00Z",
                        "sku": "SKU_DROPPED",
                        "asin": "ASIN2",
                        "sale_status": "dropped",
                        "merchant_status": "inactive",
                        "in_stock_flag": "0",
                        "writer_mode": "READ_ONLY",
                        "parked_flag": "0",
                        "park_reason_codes": "PARK_SALE_STATUS_DROPPED",
                    },
                ]
            ).to_csv(out / "phase1_sku_scope.csv", index=False)

            pd.DataFrame(
                [
                    {
                        "date_utc": "2026-02-21",
                        "sku": "SKU_DROPPED",
                        "compliance_ceiling_landed_gbp": "5.00",
                    }
                ]
            ).to_csv(data / "sku_daily_intel.csv", index=False)

            old_values = {
                "PHASE1_SCOPE_PATH": a015.PHASE1_SCOPE_PATH,
                "PHASE1_DAILY_INTEL_PATH": a015.PHASE1_DAILY_INTEL_PATH,
            }
            try:
                a015.PHASE1_SCOPE_PATH = out / "phase1_sku_scope.csv"
                a015.PHASE1_DAILY_INTEL_PATH = data / "sku_daily_intel.csv"
                rows: list[dict[str, str]] = []
                a015._phase1_rollout_checks(rows, datetime(2026, 2, 21, 6, 17, 21, tzinfo=timezone.utc))
            finally:
                a015.PHASE1_SCOPE_PATH = old_values["PHASE1_SCOPE_PATH"]
                a015.PHASE1_DAILY_INTEL_PATH = old_values["PHASE1_DAILY_INTEL_PATH"]

            by_check = {str(r.get("check", "")): r for r in rows}
            coverage = by_check["a_daily_intel_coverage_non_parked"]
            compliance = by_check["a_daily_intel_compliance_nonempty_non_parked"]
            self.assertEqual(str(coverage.get("status", "")), "fail")
            self.assertEqual(str(coverage.get("value", "")), "1")
            self.assertIn("missing_sample=SKU_ACTIVE_OOS", str(coverage.get("notes", "")))
            self.assertNotIn("SKU_DROPPED", str(coverage.get("notes", "")))
            self.assertEqual(str(compliance.get("status", "")), "fail")
            self.assertEqual(str(compliance.get("value", "")), "1")
            self.assertIn("missing_rows=1", str(compliance.get("notes", "")))

    def test_profile_filter_mask_scopes_a_b_e_h(self) -> None:
        df = pd.DataFrame(
            [
                {"check": "a_daily_intel_coverage_non_parked", "status": "ok"},
                {"check": "a_stock_receipts_collection_health", "status": "warn"},
                {"check": "b_orders_all_rows", "status": "ok"},
                {"check": "l1_keys_missing_in_master", "status": "fail"},
                {"check": "e_schema_sales_velocity", "status": "ok"},
                {"check": "h_floor_referral_source_coverage", "status": "warn"},
                {"check": "shared_custom_check", "status": "ok"},
            ]
        )
        mask_a = a015._profile_filter_mask(df, "a")
        mask_b = a015._profile_filter_mask(df, "b")
        mask_e = a015._profile_filter_mask(df, "e")
        mask_h = a015._profile_filter_mask(df, "h")
        mask_global = a015._profile_filter_mask(df, "global")

        self.assertEqual(mask_a.astype(int).tolist(), [1, 1, 0, 0, 0, 0, 0])
        self.assertEqual(mask_b.astype(int).tolist(), [0, 0, 1, 1, 0, 0, 0])
        self.assertEqual(mask_e.astype(int).tolist(), [0, 0, 0, 0, 1, 0, 0])
        self.assertEqual(mask_h.astype(int).tolist(), [0, 0, 0, 0, 0, 1, 0])
        self.assertEqual(mask_global.astype(int).tolist(), [1, 1, 1, 1, 1, 1, 1])

    def test_a_stock_receipts_step_health_uses_latest_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "out"
            manifest_dir = out / "manifests" / "A" / "2026-03-07"
            manifest_dir.mkdir(parents=True, exist_ok=True)
            old_out = a015.OUT
            try:
                a015.OUT = out
                missing_step_path = manifest_dir / "20260307T060000Z.json"
                missing_step_path.write_text(
                    """
{
  "run_id": "20260307T060000Z",
  "end_time": "2026-03-07T06:08:12Z",
  "steps": [
    {"name": "A001_run_listings_to_sheet.py", "rc": 0}
  ]
}
                    """.strip(),
                    encoding="utf-8",
                )
                os.utime(missing_step_path, (100, 100))
                health_missing = a015._a_stock_receipts_step_health(datetime(2026, 3, 7, 7, 0, 0, tzinfo=timezone.utc))
                self.assertEqual(health_missing["status"], "warn")
                self.assertEqual(health_missing["value"], "step_missing")

                success_path = manifest_dir / "20260307T120228Z.json"
                success_path.write_text(
                    """
{
  "run_id": "20260307T120228Z",
  "end_time": "2026-03-07T12:03:30Z",
  "steps": [
    {"name": "process_stock_receipts_sheet.py", "rc": 0, "notes": "elapsed=18.9s"}
  ]
}
                    """.strip(),
                    encoding="utf-8",
                )
                health_ok = a015._a_stock_receipts_step_health(datetime(2026, 3, 7, 13, 0, 0, tzinfo=timezone.utc))
                self.assertEqual(health_ok["status"], "ok")
                self.assertEqual(health_ok["value"], "0")
            finally:
                a015.OUT = old_out

    def test_a_stock_receipts_step_health_flags_failed_step(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "out"
            manifest_dir = out / "manifests" / "A" / "2026-03-07"
            manifest_dir.mkdir(parents=True, exist_ok=True)
            old_out = a015.OUT
            try:
                a015.OUT = out
                failed_path = manifest_dir / "20260307T120228Z.json"
                failed_path.write_text(
                    """
{
  "run_id": "20260307T120228Z",
  "end_time": "2026-03-07T12:03:30Z",
  "steps": [
    {"name": "process_stock_receipts_sheet.py", "rc": 1, "notes": "fatal receipt failure elapsed=3.0s detail=boom"}
  ]
}
                    """.strip(),
                    encoding="utf-8",
                )
                health_fail = a015._a_stock_receipts_step_health(datetime(2026, 3, 7, 13, 0, 0, tzinfo=timezone.utc))
                self.assertEqual(health_fail["status"], "fail")
                self.assertEqual(health_fail["value"], "1")
            finally:
                a015.OUT = old_out

    def test_a_stock_receipts_step_health_keeps_noop_success_ok(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "out"
            manifest_dir = out / "manifests" / "A" / "2026-03-07"
            manifest_dir.mkdir(parents=True, exist_ok=True)
            old_out = a015.OUT
            try:
                a015.OUT = out
                noop_path = manifest_dir / "20260307T120228Z.json"
                noop_path.write_text(
                    """
{
  "run_id": "20260307T120228Z",
  "end_time": "2026-03-07T12:03:30Z",
  "steps": [
    {"name": "process_stock_receipts_sheet.py", "rc": 0, "notes": "elapsed=0.4s;no_pending_rows"}
  ]
}
                    """.strip(),
                    encoding="utf-8",
                )
                health_noop = a015._a_stock_receipts_step_health(datetime(2026, 3, 7, 13, 0, 0, tzinfo=timezone.utc))
                self.assertEqual(health_noop["status"], "ok")
                self.assertEqual(health_noop["value"], "0")
            finally:
                a015.OUT = old_out

    def test_resolve_runtime_paths_profile_defaults(self) -> None:
        a_runtime = a015._resolve_runtime_paths(Namespace(profile="a", checklist_path="", alert_state_path="", health_status_path="", no_toast=False))
        b_runtime = a015._resolve_runtime_paths(Namespace(profile="b", checklist_path="", alert_state_path="", health_status_path="", no_toast=True))
        e_runtime = a015._resolve_runtime_paths(Namespace(profile="e", checklist_path="", alert_state_path="", health_status_path="", no_toast=False))
        h_runtime = a015._resolve_runtime_paths(Namespace(profile="h", checklist_path="", alert_state_path="", health_status_path="", no_toast=False))
        g_runtime = a015._resolve_runtime_paths(Namespace(profile="global", checklist_path="", alert_state_path="", health_status_path="", no_toast=False))

        self.assertEqual(a_runtime["profile"], "a")
        self.assertEqual(Path(a_runtime["checklist_path"]), a015.CHECKLIST_A_SPLIT_CSV)
        self.assertEqual(Path(a_runtime["alert_state_path"]), a015.ALERT_STATE_A_CSV)
        self.assertEqual(Path(a_runtime["health_status_path"]), a015.HEALTH_STATUS_A_CSV)

        self.assertEqual(b_runtime["profile"], "b")
        self.assertEqual(Path(b_runtime["checklist_path"]), a015.CHECKLIST_B_SPLIT_CSV)
        self.assertEqual(Path(b_runtime["alert_state_path"]), a015.ALERT_STATE_B_CSV)
        self.assertEqual(Path(b_runtime["health_status_path"]), a015.HEALTH_STATUS_B_CSV)
        self.assertTrue(bool(b_runtime["no_toast"]))

        self.assertEqual(e_runtime["profile"], "e")
        self.assertEqual(Path(e_runtime["checklist_path"]), a015.CHECKLIST_E_SPLIT_CSV)
        self.assertEqual(Path(e_runtime["alert_state_path"]), a015.ALERT_STATE_E_CSV)
        self.assertEqual(Path(e_runtime["health_status_path"]), a015.HEALTH_STATUS_E_CSV)

        self.assertEqual(h_runtime["profile"], "h")
        self.assertEqual(Path(h_runtime["checklist_path"]), a015.CHECKLIST_H_SPLIT_CSV)
        self.assertEqual(Path(h_runtime["alert_state_path"]), a015.ALERT_STATE_H_CSV)
        self.assertEqual(Path(h_runtime["health_status_path"]), a015.HEALTH_STATUS_H_CSV)
        self.assertFalse(bool(h_runtime["no_toast"]))

        self.assertEqual(g_runtime["profile"], "global")
        self.assertEqual(Path(g_runtime["checklist_path"]), a015.CHECKLIST_CSV)
        self.assertEqual(Path(g_runtime["alert_state_path"]), a015.ALERT_STATE_CSV)
        self.assertEqual(Path(g_runtime["health_status_path"]), a015.HEALTH_STATUS_CSV)

    def test_run_main_fail_closed_uses_profile_paths_from_cli(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "out"
            out.mkdir(parents=True, exist_ok=True)
            checklist_path = out / "checklist_b_custom.csv"
            alert_state_path = out / "alert_state_b_custom.csv"
            health_status_path = out / "health_status_b_custom.csv"
            old_argv = list(sys.argv)

            def _explode() -> None:
                raise RuntimeError("boom_profile_b")

            try:
                sys.argv = [
                    "A015_build_system_health_check.py",
                    "--profile",
                    "b",
                    "--checklist-path",
                    str(checklist_path),
                    "--alert-state-path",
                    str(alert_state_path),
                    "--health-status-path",
                    str(health_status_path),
                    "--no-toast",
                ]
                rc = a015._run_main_fail_closed(_explode)
            finally:
                sys.argv = old_argv

            self.assertEqual(rc, 2)
            self.assertTrue(checklist_path.exists())
            self.assertTrue(health_status_path.exists())
            df = pd.read_csv(checklist_path, dtype=str).fillna("")
            self.assertTrue((df["check"] == "a015_runtime_exception").any())
            status_df = pd.read_csv(health_status_path, dtype=str).fillna("")
            self.assertTrue((status_df["status"] == "FAIL").any())


if __name__ == "__main__":
    unittest.main()
