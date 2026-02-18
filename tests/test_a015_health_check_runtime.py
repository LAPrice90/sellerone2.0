import os
import sys
import tempfile
import unittest
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts import A015_build_system_health_check as a015


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

    def test_profile_filter_mask_scopes_a_b_e_h(self) -> None:
        df = pd.DataFrame(
            [
                {"check": "a_daily_intel_coverage_non_parked", "status": "ok"},
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

        self.assertEqual(mask_a.astype(int).tolist(), [1, 0, 0, 0, 0, 0])
        self.assertEqual(mask_b.astype(int).tolist(), [0, 1, 1, 0, 0, 0])
        self.assertEqual(mask_e.astype(int).tolist(), [0, 0, 0, 1, 0, 0])
        self.assertEqual(mask_h.astype(int).tolist(), [0, 0, 0, 0, 1, 0])
        self.assertEqual(mask_global.astype(int).tolist(), [1, 1, 1, 1, 1, 1])

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
