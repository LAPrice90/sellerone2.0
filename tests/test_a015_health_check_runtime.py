import os
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

from scripts.flows.A import A015_build_system_health_check as a015


class A015HealthCheckRuntimeTests(unittest.TestCase):
    def test_a015_script_help_bootstraps_imports(self) -> None:
        script = ROOT / "scripts" / "flows" / "A" / "A015_build_system_health_check.py"
        proc = subprocess.run(
            [sys.executable, str(script), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--profile", proc.stdout)

    def test_read_json_returns_default_on_missing_or_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            missing_path = root / "missing.json"
            default = {"a": 1}
            self.assertEqual(a015._read_json(missing_path, default=default), default)

            bad_path = root / "bad.json"
            bad_path.write_text("{not-json", encoding="utf-8")
            self.assertEqual(a015._read_json(bad_path, default=default), default)

    def test_cycle_failure_ledger_schema_check_allows_missing_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            rows = []
            a015._cycle_failure_ledger_schema_check(rows, Path(td) / "missing_failure_ledger.csv")

        self.assertEqual(rows[0]["check"], "shared_cycle_failure_ledger_schema")
        self.assertEqual(rows[0]["status"], "ok")
        self.assertEqual(rows[0]["value"], "ok")

    def test_required_non_blank_check_flags_blank_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "sample.csv"
            pd.DataFrame([{"a": "", "b": "1"}]).to_csv(path, index=False)
            rows: list[dict[str, str]] = []
            a015._required_non_blank_check(rows, "sample_required_non_blank", path, ["a", "b"])
            row = next((r for r in rows if r.get("check") == "sample_required_non_blank"), {})
            self.assertEqual(str(row.get("status", "")), "fail")
            self.assertEqual(str(row.get("value", "")), "1")

    def test_h_ceiling_effective_floor_integrity_scopes_latest_run_only(self) -> None:
        result = a015._h_ceiling_effective_floor_integrity_result(
            pd.DataFrame(
                [
                    {
                        "run_id": "20260417T050000Z",
                        "sku": "SKU_OLD_BAD",
                        "true_binding_ceiling_gbp": "8.50",
                        "hard_floor_gbp": "9.00",
                    },
                    {
                        "run_id": "20260417T060000Z",
                        "sku": "SKU_NEW_OK",
                        "true_binding_ceiling_gbp": "10.00",
                        "hard_floor_gbp": "9.00",
                    },
                ]
            ),
            path=Path("out/h_ceiling_events.csv"),
        )
        self.assertEqual(str(result.get("status", "")), "ok")
        self.assertEqual(str(result.get("value", "")), "0")
        self.assertIn("scope_run_id=20260417T060000Z", str(result.get("notes", "")))
        self.assertIn("total_rows=2", str(result.get("notes", "")))

    def test_h_ceiling_effective_floor_integrity_fails_conflict_in_latest_run(self) -> None:
        result = a015._h_ceiling_effective_floor_integrity_result(
            pd.DataFrame(
                [
                    {
                        "run_id": "20260417T050000Z",
                        "sku": "SKU_OLD_OK",
                        "true_binding_ceiling_gbp": "10.00",
                        "hard_floor_gbp": "9.00",
                    },
                    {
                        "run_id": "20260417T060000Z",
                        "sku": "SKU_NEW_BAD",
                        "true_binding_ceiling_gbp": "8.50",
                        "hard_floor_gbp": "9.00",
                    },
                ]
            ),
            path=Path("out/h_ceiling_events.csv"),
        )
        self.assertEqual(str(result.get("status", "")), "fail")
        self.assertEqual(str(result.get("value", "")), "1")
        self.assertIn("scope_run_id=20260417T060000Z", str(result.get("notes", "")))
        self.assertIn("SKU_NEW_BAD:8.50<9.00", str(result.get("notes", "")))

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
            self.assertEqual(int(stats.get("raw_fail_count", 0)), 1)
            self.assertEqual(int(stats.get("recovered_count", 0)), 0)
            self.assertEqual(int(stats.get("unresolved_count", 0)), 1)
            sample = stats.get("unresolved_sample", [])
            self.assertTrue(sample)
            self.assertIn("fail B004_build_order_master.py", str(sample[0]))

    def test_b_cycle_recent_fail_stats_ignores_maintenance_abort_rc125(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            log_path = root / "B_cycle.log"
            log_path.write_text(
                "\n".join(
                    [
                        "2026-04-01T21:23:12Z [2026-04-01T21:17:19Z] fail listing_offer collection rc=125",
                        "2026-04-01T21:23:45Z [2026-04-01T21:17:19Z] maintenance ready (after cycle end); current cycle finished request_id=A_20260401T212021Z",
                        "2026-04-01T21:28:16Z [2026-04-01T21:17:19Z] maintenance pause (after cycle end); sleeping 5s, check back in 13 minutes",
                        "2026-04-01T21:28:31Z [2026-04-01T21:17:19Z] B_FINALIZE ran rc=0 wrote_health=true reason=cycle_complete",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            stats = a015._b_cycle_recent_fail_stats(log_path, window_hours=48)
            self.assertEqual(int(stats.get("raw_fail_count", 0)), 0)
            self.assertEqual(int(stats.get("unresolved_count", 0)), 0)
            self.assertEqual(int(stats.get("ignored_non_actionable", 0)), 1)
            self.assertEqual(int(stats.get("maintenance_context", 0)), 1)

    def test_relax_check_status_for_maintenance_downgrades_fail(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            marker = root / "maintenance.active"
            marker.write_text("A_REQ_1\n", encoding="utf-8")

            old_markers = list(a015.B_MAINTENANCE_MARKER_PATHS)
            try:
                a015.B_MAINTENANCE_MARKER_PATHS = [marker]
                rows = [{"check": "b_order_master_freshness", "status": "fail", "value": "240.00", "notes": "path=x"}]
                a015._relax_check_status_for_maintenance(rows, check_name="b_order_master_freshness")
            finally:
                a015.B_MAINTENANCE_MARKER_PATHS = old_markers

            self.assertEqual(str(rows[0].get("status", "")), "warn")
            self.assertIn("maintenance_expected_staleness=1", str(rows[0].get("notes", "")))

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

    def test_pid_alive_windows_avoids_os_kill_and_uses_tasklist(self) -> None:
        fake_result = type(
            "_TasklistResult",
            (),
            {
                "stdout": '"python.exe","1234","Console","1","9,000 K"\n',
                "stderr": "",
            },
        )()
        with mock.patch.object(a015.os, "name", "nt"), mock.patch.object(
            a015.os,
            "kill",
            side_effect=AssertionError("os.kill must not be used on Windows pid probes"),
        ), mock.patch.object(a015.subprocess, "run", return_value=fake_result):
            self.assertTrue(a015._pid_alive(1234))

    def test_pid_alive_windows_reports_false_when_tasklist_has_no_match(self) -> None:
        fake_result = type(
            "_TasklistResult",
            (),
            {
                "stdout": "INFO: No tasks are running which match the specified criteria.\n",
                "stderr": "",
            },
        )()
        with mock.patch.object(a015.os, "name", "nt"), mock.patch.object(
            a015.os,
            "kill",
            side_effect=AssertionError("os.kill must not be used on Windows pid probes"),
        ), mock.patch.object(a015.subprocess, "run", return_value=fake_result):
            self.assertFalse(a015._pid_alive(5678))

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
            (out / "parking").mkdir(parents=True, exist_ok=True)

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
            pd.DataFrame(
                [
                    {
                        "date_utc": "2026-02-21",
                        "sku": "SKU_DROPPED",
                        "compliance_ceiling_landed_gbp": "5.00",
                    }
                ]
            ).to_csv(out / "phase1_daily_intel_latest.csv", index=False)
            pd.DataFrame(
                [
                    {"seller_sku": "SKU_ACTIVE_OOS", "available": "1", "total_quantity": "1"},
                    {"seller_sku": "SKU_DROPPED", "available": "0", "total_quantity": "0"},
                ]
            ).to_csv(out / "inventory_summaries.csv", index=False)
            pd.DataFrame(columns=["sku"]).to_csv(out / "parking" / "parked_skus.csv", index=False)

            old_values = {
                "OUT": a015.OUT,
                "PHASE1_SCOPE_PATH": a015.PHASE1_SCOPE_PATH,
                "PHASE1_DAILY_INTEL_PATH": a015.PHASE1_DAILY_INTEL_PATH,
                "PHASE1_DAILY_INTEL_LATEST_PATH": a015.PHASE1_DAILY_INTEL_LATEST_PATH,
                "PARKED_SKUS_PATH": a015.PARKED_SKUS_PATH,
                "INVENTORY_SUMMARIES_PATH": a015.INVENTORY_SUMMARIES_PATH,
                "STOCK_SNAPSHOT_LATEST_PATH": a015.STOCK_SNAPSHOT_LATEST_PATH,
            }
            try:
                a015.OUT = out
                a015.PHASE1_SCOPE_PATH = out / "phase1_sku_scope.csv"
                a015.PHASE1_DAILY_INTEL_PATH = data / "sku_daily_intel.csv"
                a015.PHASE1_DAILY_INTEL_LATEST_PATH = out / "phase1_daily_intel_latest.csv"
                a015.PARKED_SKUS_PATH = out / "parking" / "parked_skus.csv"
                a015.INVENTORY_SUMMARIES_PATH = out / "inventory_summaries.csv"
                a015.STOCK_SNAPSHOT_LATEST_PATH = out / "parking" / "stock_snapshot_latest.csv"
                rows: list[dict[str, str]] = []
                a015._phase1_rollout_checks(
                    rows,
                    datetime(2026, 2, 21, 6, 17, 21, tzinfo=timezone.utc),
                    lambda _message: None,
                )
            finally:
                a015.OUT = old_values["OUT"]
                a015.PHASE1_SCOPE_PATH = old_values["PHASE1_SCOPE_PATH"]
                a015.PHASE1_DAILY_INTEL_PATH = old_values["PHASE1_DAILY_INTEL_PATH"]
                a015.PHASE1_DAILY_INTEL_LATEST_PATH = old_values["PHASE1_DAILY_INTEL_LATEST_PATH"]
                a015.PARKED_SKUS_PATH = old_values["PARKED_SKUS_PATH"]
                a015.INVENTORY_SUMMARIES_PATH = old_values["INVENTORY_SUMMARIES_PATH"]
                a015.STOCK_SNAPSHOT_LATEST_PATH = old_values["STOCK_SNAPSHOT_LATEST_PATH"]

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
                {"check": "o_net_fee_bridge_health", "status": "ok"},
                {"check": "shared_custom_check", "status": "ok"},
            ]
        )
        mask_a = a015._profile_filter_mask(df, "a")
        mask_b = a015._profile_filter_mask(df, "b")
        mask_e = a015._profile_filter_mask(df, "e")
        mask_h = a015._profile_filter_mask(df, "h")
        mask_global = a015._profile_filter_mask(df, "global")

        self.assertEqual(mask_a.astype(int).tolist(), [1, 1, 0, 0, 0, 0, 0, 0])
        self.assertEqual(mask_b.astype(int).tolist(), [0, 0, 1, 1, 0, 0, 0, 0])
        self.assertEqual(mask_e.astype(int).tolist(), [0, 0, 0, 0, 1, 0, 0, 0])
        self.assertEqual(mask_h.astype(int).tolist(), [0, 0, 0, 0, 0, 1, 0, 0])
        self.assertEqual(mask_global.astype(int).tolist(), [1, 1, 1, 1, 1, 1, 1, 1])
        self.assertEqual(a015._cycle_for_check("o_net_fee_bridge_health"), "O")

    def test_write_cycle_alert_files_routes_o_checks_to_o_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_cycle_alert_dir = a015.CYCLE_ALERT_DIR
            try:
                a015.CYCLE_ALERT_DIR = root / "out" / "cycle_alerts"
                a015._write_cycle_alert_files(
                    pd.DataFrame(
                        [
                            {"check": "o_net_fee_bridge_health", "status": "ok", "value": "1", "notes": "ok"},
                            {"check": "a_stock_receipts_collection_health", "status": "ok", "value": "0", "notes": "ok"},
                        ]
                    )
                )
                o_df = pd.read_csv(a015.CYCLE_ALERT_DIR / "checklist_O.csv", dtype=str).fillna("")
                self.assertEqual(o_df["check"].tolist(), ["o_net_fee_bridge_health"])
                all_df = pd.read_csv(a015.CYCLE_ALERT_DIR / "checklist_all.csv", dtype=str).fillna("")
                o_row = all_df.loc[all_df["check"].eq("o_net_fee_bridge_health")].iloc[0]
                self.assertEqual(o_row["cycle"], "O")
            finally:
                a015.CYCLE_ALERT_DIR = old_cycle_alert_dir

    def test_o_net_fee_bridge_stats_ok_for_fresh_action_ready_row(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source_path = root / "restock_source_view.csv"
            recommendations_path = root / "restock_recommendations_live.csv"
            coverage_path = root / "reorder_input_coverage_report.csv"
            source_row = {
                "seller_sku": "SKU-1",
                "market_price_ex_vat_gbp": "10",
                "market_price_vat_rate_pct": "20",
                "current_token_cost_gbp": "4",
                "break_even_price_gbp": "6",
                "net_fee_drag_per_unit_gbp": "1.5",
                "net_fee_model_status": "fresh",
                "net_fee_model_asof": "2026-05-19",
                "net_fee_model_age_hours": "4",
                "net_fee_model_source": "sku_performance_summary",
            }
            rec_row = {
                **source_row,
                "recommendation_status": "full_restock",
                "forward_roi_pct": "25",
                "forward_profit_per_unit_gbp": "1",
                "gross_forward_roi_pct": "45",
                "gross_forward_profit_per_unit_gbp": "1.8",
            }
            coverage_row = {
                "seller_sku": "SKU-1",
                "action_ready_now": "1",
                "expected_forward_roi_pct": "25",
                "net_fee_drag_per_unit_gbp": "1.5",
                "net_fee_model_status": "fresh",
                "net_fee_model_asof": "2026-05-19",
                "net_fee_model_age_hours": "4",
            }
            pd.DataFrame([source_row]).to_csv(source_path, index=False)
            pd.DataFrame([rec_row]).to_csv(recommendations_path, index=False)
            pd.DataFrame([coverage_row]).to_csv(coverage_path, index=False)

            stats = a015._o_net_fee_bridge_stats(source_path, recommendations_path, coverage_path)

            self.assertEqual(stats["status"], "ok")
            self.assertEqual(stats["value"], "1")
            self.assertEqual(int(stats["equal_net_gross_roi_rows"]), 0)

    def test_o_net_fee_bridge_stats_skips_wait_rows_without_roi_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source_path = root / "restock_source_view.csv"
            recommendations_path = root / "restock_recommendations_live.csv"
            coverage_path = root / "reorder_input_coverage_report.csv"
            source_row = {
                "seller_sku": "SKU-WAIT-NOCOST",
                "market_price_gbp": "9.99",
                "market_price_ex_vat_gbp": "8.325",
                "market_price_vat_rate_pct": "20",
                "current_token_cost_gbp": "4",
                "break_even_price_gbp": "6",
                "net_fee_drag_per_unit_gbp": "2",
                "net_fee_model_status": "fresh",
                "net_fee_model_asof": "2026-05-19",
                "net_fee_model_age_hours": "4",
                "net_fee_model_source": "sku_performance_summary",
                "current_supplier_buy_cost_gbp": "",
            }
            rec_row = {
                **source_row,
                "recommendation_status": "wait",
                "forward_roi_pct": "",
                "forward_profit_per_unit_gbp": "",
                "gross_forward_roi_pct": "",
                "gross_forward_profit_per_unit_gbp": "",
                "reason_codes": "BLOCKED_MISSING_COST_INPUT",
            }
            pd.DataFrame([source_row]).to_csv(source_path, index=False)
            pd.DataFrame([rec_row]).to_csv(recommendations_path, index=False)
            pd.DataFrame([]).to_csv(coverage_path, index=False)

            stats = a015._o_net_fee_bridge_stats(source_path, recommendations_path, coverage_path)

            self.assertEqual(stats["status"], "ok")
            self.assertEqual(stats["value"], "no_action_ready")
            self.assertEqual(int(stats["roi_compare_missing_rows"]), 0)
            self.assertEqual(int(stats["roi_compare_not_applicable_rows"]), 1)

    def test_o_net_fee_bridge_stats_warns_when_applicable_roi_compare_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source_path = root / "restock_source_view.csv"
            recommendations_path = root / "restock_recommendations_live.csv"
            coverage_path = root / "reorder_input_coverage_report.csv"
            source_row = {
                "seller_sku": "SKU-WAIT-COMPUTABLE",
                "market_price_gbp": "9.99",
                "market_price_ex_vat_gbp": "8.325",
                "market_price_vat_rate_pct": "20",
                "current_token_cost_gbp": "4",
                "break_even_price_gbp": "6",
                "net_fee_drag_per_unit_gbp": "2",
                "net_fee_model_status": "fresh",
                "net_fee_model_asof": "2026-05-19",
                "net_fee_model_age_hours": "4",
                "net_fee_model_source": "sku_performance_summary",
                "current_supplier_buy_cost_gbp": "4",
            }
            rec_row = {
                **source_row,
                "recommendation_status": "wait",
                "forward_roi_pct": "",
                "forward_profit_per_unit_gbp": "",
                "gross_forward_roi_pct": "",
                "gross_forward_profit_per_unit_gbp": "",
                "reason_codes": "ROI_BELOW_MIN_THRESHOLD",
            }
            pd.DataFrame([source_row]).to_csv(source_path, index=False)
            pd.DataFrame([rec_row]).to_csv(recommendations_path, index=False)
            pd.DataFrame([]).to_csv(coverage_path, index=False)

            stats = a015._o_net_fee_bridge_stats(source_path, recommendations_path, coverage_path)

            self.assertEqual(stats["status"], "warn")
            self.assertEqual(stats["value"], "roi_compare_missing")
            self.assertEqual(int(stats["roi_compare_missing_rows"]), 1)
            self.assertEqual(int(stats["roi_compare_not_applicable_rows"]), 0)

    def test_o_net_fee_bridge_stats_fails_action_ready_missing_stale_and_unapplied_fee(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source_path = root / "restock_source_view.csv"
            recommendations_path = root / "restock_recommendations_live.csv"
            coverage_path = root / "reorder_input_coverage_report.csv"
            source_row = {
                "seller_sku": "SKU-2",
                "market_price_ex_vat_gbp": "10",
                "market_price_vat_rate_pct": "20",
                "current_token_cost_gbp": "4",
                "break_even_price_gbp": "",
                "net_fee_drag_per_unit_gbp": "2",
                "net_fee_model_status": "stale",
                "net_fee_model_asof": "2026-05-16",
                "net_fee_model_age_hours": "72",
                "net_fee_model_source": "sku_performance_summary",
            }
            rec_row = {
                **source_row,
                "break_even_price_gbp": "7",
                "recommendation_status": "test_restock",
                "forward_roi_pct": "30",
                "forward_profit_per_unit_gbp": "1.2",
                "gross_forward_roi_pct": "30",
                "gross_forward_profit_per_unit_gbp": "1.2",
            }
            coverage_row = {
                "seller_sku": "SKU-2",
                "action_ready_now": "1",
                "expected_forward_roi_pct": "30",
                "net_fee_drag_per_unit_gbp": "2",
                "net_fee_model_status": "stale",
                "net_fee_model_asof": "2026-05-16",
                "net_fee_model_age_hours": "72",
            }
            pd.DataFrame([source_row]).to_csv(source_path, index=False)
            pd.DataFrame([rec_row]).to_csv(recommendations_path, index=False)
            pd.DataFrame([coverage_row]).to_csv(coverage_path, index=False)

            stats = a015._o_net_fee_bridge_stats(source_path, recommendations_path, coverage_path)

            self.assertEqual(stats["status"], "fail")
            self.assertGreater(int(stats["missing_net_field_rows"]), 0)
            self.assertGreater(int(stats["bad_status_rows"]), 0)
            self.assertGreater(int(stats["stale_age_rows"]), 0)
            self.assertEqual(int(stats["equal_net_gross_roi_rows"]), 1)

    def test_o_net_fee_bridge_stats_tolerates_empty_live_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source_path = root / "restock_source_view.csv"
            recommendations_path = root / "restock_recommendations_live.csv"
            coverage_path = root / "reorder_input_coverage_report.csv"
            source_path.write_text("", encoding="utf-8")
            recommendations_path.write_text("", encoding="utf-8")
            coverage_path.write_text("", encoding="utf-8")

            stats = a015._o_net_fee_bridge_stats(source_path, recommendations_path, coverage_path)

            self.assertEqual(stats["status"], "ok")
            self.assertEqual(stats["value"], "empty_outputs")

    def test_o_net_fee_bridge_check_appends_checklist_row(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source_path = root / "restock_source_view.csv"
            recommendations_path = root / "restock_recommendations_live.csv"
            coverage_path = root / "reorder_input_coverage_report.csv"
            source_path.write_text("", encoding="utf-8")
            recommendations_path.write_text("", encoding="utf-8")
            coverage_path.write_text("", encoding="utf-8")
            rows: list[dict[str, str]] = []

            a015._o_net_fee_bridge_check(rows, source_path, recommendations_path, coverage_path)

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["check"], "o_net_fee_bridge_health")
            self.assertEqual(rows[0]["status"], "ok")
            self.assertEqual(rows[0]["value"], "empty_outputs")

    def test_order_master_l1_coverage_stats_does_not_ignore_sidecar_missing_keys(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fee_path = root / "l1_missing_fee_keys.csv"
            token_path = root / "orders_missing_tokens.csv"

            pd.DataFrame([{"Order ID": "ORDER-2", "SKU": "SKU-2"}]).to_csv(fee_path, index=False)
            pd.DataFrame([{"Order ID": "ORDER-2", "SKU": "SKU-2"}]).to_csv(token_path, index=False)

            l1 = pd.DataFrame(
                [
                    {"Order ID": "ORDER-1", "SKU": "SKU-1"},
                    {"Order ID": "ORDER-2", "SKU": "SKU-2"},
                ]
            )
            order_master = pd.DataFrame([{"Order ID": "ORDER-1", "SKU": "SKU-1"}])

            stats = a015._order_master_l1_coverage_stats(
                l1,
                order_master,
                l1_missing_fee_keys_path=fee_path,
                missing_token_orders_path=token_path,
            )

            self.assertEqual(int(stats.get("missing_count", 0)), 1)
            self.assertIn("ORDER-2||SKU-2", set(stats.get("missing_set", set())))
            self.assertIn("observed_missing_fee_keys=1", str(stats.get("note", "")))
            self.assertIn("observed_missing_token_keys=1", str(stats.get("note", "")))

    def test_order_master_placeholder_stats_counts_placeholder_and_no_basis_rows(self) -> None:
        order_master = pd.DataFrame(
            [
                {
                    "Order ID": "ORDER-1",
                    "SKU": "SKU-A",
                    "lvl": "2",
                    "Quantity Ordered": "1",
                    "COGS_Placeholder_Applied": "1",
                    "Missing_Token_Flag": "1",
                },
                {
                    "Order ID": "ORDER-2",
                    "SKU": "SKU-B",
                    "lvl": "2",
                    "Quantity Ordered": "1",
                    "COGS_Placeholder_Applied": "0",
                    "Missing_Token_Flag": "1",
                },
                {
                    "Order ID": "ORDER-3",
                    "SKU": "SKU-C",
                    "lvl": "0",
                    "Quantity Ordered": "1",
                    "COGS_Placeholder_Applied": "1",
                    "Missing_Token_Flag": "1",
                },
            ]
        )
        stats = a015._order_master_placeholder_stats(order_master)
        self.assertEqual(int(stats.get("placeholder_rows", 0)), 1)
        self.assertEqual(int(stats.get("missing_token_no_placeholder_rows", 0)), 1)
        self.assertEqual(int(stats.get("placeholder_repeat_sku_count", 0)), 0)

    def test_order_master_placeholder_stats_reports_repeat_skus(self) -> None:
        order_master = pd.DataFrame(
            [
                {
                    "Order ID": "ORDER-1",
                    "SKU": "SKU-REPEAT",
                    "lvl": "2",
                    "Quantity Ordered": "1",
                    "COGS_Placeholder_Applied": "1",
                    "Missing_Token_Flag": "1",
                },
                {
                    "Order ID": "ORDER-2",
                    "SKU": "SKU-REPEAT",
                    "lvl": "2",
                    "Quantity Ordered": "1",
                    "COGS_Placeholder_Applied": "true",
                    "Missing_Token_Flag": "1",
                },
            ]
        )
        stats = a015._order_master_placeholder_stats(order_master)
        self.assertEqual(int(stats.get("placeholder_rows", 0)), 2)
        self.assertEqual(int(stats.get("placeholder_repeat_sku_count", 0)), 1)
        self.assertEqual(int(stats.get("placeholder_repeat_row_count", 0)), 2)
        sample = [str(v) for v in stats.get("placeholder_repeat_sample", [])]
        self.assertTrue(any(v.startswith("SKU-REPEAT:2") for v in sample))

    def test_token_allocated_on_canceled_orders_stats_detects_stranded_allocations(self) -> None:
        token_allocations = pd.DataFrame(
            [
                {
                    "order_id": "ORDER-CANCEL",
                    "seller_sku": "SKU-1",
                    "quantity": "2",
                    "token_id": "tok-1",
                    "allocation_date": "2026-04-10T10:00:00Z",
                }
            ]
        )
        orders_all_status = pd.DataFrame(
            [
                {"amazon_order_id": "ORDER-CANCEL", "order_status": "Canceled"},
            ]
        )
        order_master = pd.DataFrame(
            [
                {"Order ID": "ORDER-LIVE", "SKU": "SKU-1", "Quantity Ordered": "1", "lvl": "2"},
            ]
        )

        stats = a015._token_allocated_on_canceled_orders_stats(token_allocations, orders_all_status, order_master)

        self.assertTrue(bool(stats.get("ready", False)))
        self.assertEqual(int(stats.get("rows", 0)), 1)
        self.assertEqual(int(stats.get("units", 0)), 2)
        details = stats.get("details")
        self.assertIsInstance(details, pd.DataFrame)
        self.assertEqual(len(details.index), 1)
        self.assertEqual(str(details.iloc[0]["order_status"]), "Canceled")

    def test_token_allocated_on_canceled_orders_stats_ignores_orders_still_in_demand(self) -> None:
        token_allocations = pd.DataFrame(
            [
                {
                    "order_id": "ORDER-CANCEL",
                    "seller_sku": "SKU-1",
                    "quantity": "1",
                    "token_id": "tok-1",
                    "allocation_date": "2026-04-10T10:00:00Z",
                }
            ]
        )
        orders_all_status = pd.DataFrame(
            [
                {"amazon_order_id": "ORDER-CANCEL", "order_status": "Canceled"},
            ]
        )
        order_master = pd.DataFrame(
            [
                {"Order ID": "ORDER-CANCEL", "SKU": "SKU-1", "Quantity Ordered": "1", "lvl": "2"},
            ]
        )

        stats = a015._token_allocated_on_canceled_orders_stats(token_allocations, orders_all_status, order_master)

        self.assertTrue(bool(stats.get("ready", False)))
        self.assertEqual(int(stats.get("rows", 0)), 0)
        self.assertEqual(int(stats.get("units", 0)), 0)

    def test_e_sales_truth_roi_integrity_stats_counts_fail_classes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "sku_roi_snapshot.csv"
            pd.DataFrame(
                [
                    {
                        "sku": "SKU-A",
                        "units_sold": "1",
                        "revenue_exvat_gbp": "0",
                        "profit_exvat_gbp": "0",
                        "missing_cogs_units": "1",
                    },
                    {
                        "sku": "SKU-B",
                        "units_sold": "1",
                        "revenue_exvat_gbp": "10",
                        "profit_exvat_gbp": "0",
                        "missing_cogs_units": "0",
                    },
                    {
                        "sku": "SKU-C",
                        "units_sold": "0",
                        "revenue_exvat_gbp": "0",
                        "profit_exvat_gbp": "0",
                        "missing_cogs_units": "0",
                    },
                ]
            ).to_csv(path, index=False)
            stats = a015._e_sales_truth_roi_integrity_stats(path)
            self.assertTrue(bool(stats.get("ready", False)))
            self.assertEqual(int(stats.get("selling_rows", 0)), 2)
            self.assertEqual(int(stats.get("zero_revenue_rows", 0)), 1)
            self.assertEqual(int(stats.get("zero_profit_with_revenue_rows", 0)), 1)
            self.assertEqual(int(stats.get("missing_cogs_equals_units_rows", 0)), 1)

    def test_e_sales_truth_reconciliation_stats_warn_and_fail_share(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "sales_truth_reconciliation_latest.csv"
            pd.DataFrame(
                [
                    {"confidence_status": "match", "revenue_delta_gbp": "0", "profit_delta_gbp": "0"},
                    {"confidence_status": "mismatch", "revenue_delta_gbp": "1.2", "profit_delta_gbp": "0.6"},
                ]
            ).to_csv(path, index=False)
            stats_warn = a015._e_sales_truth_reconciliation_stats(path)
            self.assertTrue(bool(stats_warn.get("ready", False)))
            self.assertEqual(str(stats_warn.get("status", "")), "warn")
            self.assertEqual(int(stats_warn.get("mismatch_rows", 0)), 1)
            self.assertEqual(int(stats_warn.get("total_rows", 0)), 2)
            with mock.patch.dict(os.environ, {"E_SALES_TRUTH_RECON_FAIL_SHARE": "0.40"}, clear=False):
                stats_fail = a015._e_sales_truth_reconciliation_stats(path)
            self.assertEqual(str(stats_fail.get("status", "")), "fail")

    def test_e_performance_units_alignment_stats_counts_mismatch_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "sku_performance_summary.csv"
            pd.DataFrame(
                [
                    {"sku": "SKU-A", "units_sold": "7", "units_sold_roi": "5", "revenue_exvat_gbp": "50", "profit_exvat_gbp": "10"},
                    {"sku": "SKU-B", "units_sold": "3", "units_sold_roi": "3", "revenue_exvat_gbp": "20", "profit_exvat_gbp": "4"},
                    {"sku": "SKU-C", "units_sold": "9", "units_sold_roi": "", "revenue_exvat_gbp": "", "profit_exvat_gbp": ""},
                ]
            ).to_csv(path, index=False)
            stats = a015._e_performance_units_alignment_stats(path)
            self.assertTrue(bool(stats.get("ready", False)))
            self.assertEqual(str(stats.get("status", "")), "fail")
            self.assertEqual(int(stats.get("roi_row_count", 0)), 2)
            self.assertEqual(int(stats.get("mismatch_rows", 0)), 1)

    def test_e_daily_sales_truth_stats_checks_source_and_confidence_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "sku_daily_sales_truth_latest.csv"
            pd.DataFrame(
                [
                    {
                        "sku": "SKU-A",
                        "date": "2026-04-16",
                        "source_state": "finalized_ledger",
                        "units": "3",
                        "revenue_gbp": "27.24",
                        "profit_gbp": "1.86",
                        "fees_gbp": "-12.06",
                        "cogs_gbp": "-13.32",
                        "confidence_status": "finalized",
                        "notes": "",
                    },
                    {
                        "sku": "SKU-A",
                        "date": "2026-04-17",
                        "source_state": "provisional_order_master",
                        "units": "6",
                        "revenue_gbp": "55.92",
                        "profit_gbp": "4.98",
                        "fees_gbp": "-24.3",
                        "cogs_gbp": "-26.64",
                        "confidence_status": "provisional",
                        "notes": "",
                    },
                ]
            ).to_csv(path, index=False)
            stats_ok = a015._e_daily_sales_truth_stats(path)
            self.assertTrue(bool(stats_ok.get("ready", False)))
            self.assertEqual(str(stats_ok.get("status", "")), "ok")
            self.assertEqual(int(stats_ok.get("invalid_source_rows", 0)), 0)
            self.assertEqual(int(stats_ok.get("provisional_bad_confidence_rows", 0)), 0)

            pd.DataFrame(
                [
                    {
                        "sku": "SKU-A",
                        "date": "2026-04-17",
                        "source_state": "provisional_order_master",
                        "units": "6",
                        "revenue_gbp": "55.92",
                        "profit_gbp": "4.98",
                        "fees_gbp": "-24.3",
                        "cogs_gbp": "-26.64",
                        "confidence_status": "finalized",
                        "notes": "",
                    }
                ]
            ).to_csv(path, index=False)
            stats_fail = a015._e_daily_sales_truth_stats(path)
            self.assertEqual(str(stats_fail.get("status", "")), "fail")
            self.assertEqual(int(stats_fail.get("provisional_bad_confidence_rows", 0)), 1)

    def test_e_study_report_fresh_vs_summary_stats_flags_stale_report(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            summary = root / "sku_performance_summary.csv"
            study = root / "e_study_report.csv"
            summary.write_text("sku,units_sold\nSKU-A,5\n", encoding="utf-8")
            study.write_text("study_rank,sku\n1,SKU-A\n", encoding="utf-8")
            summary_ts = datetime(2026, 4, 17, 22, 0, 0, tzinfo=timezone.utc).timestamp()
            study_ts = datetime(2026, 4, 17, 21, 0, 0, tzinfo=timezone.utc).timestamp()
            os.utime(summary, (summary_ts, summary_ts))
            os.utime(study, (study_ts, study_ts))

            stats = a015._e_study_report_fresh_vs_summary_stats(summary, study)
            self.assertTrue(bool(stats.get("ready", False)))
            self.assertEqual(str(stats.get("status", "")), "fail")
            self.assertEqual(int(float(stats.get("lag_seconds", 0))), 3600)

    def test_e_study_report_truth_alignment_stats_detects_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            summary = root / "sku_performance_summary.csv"
            study = root / "e_study_report.csv"
            pd.DataFrame(
                [
                    {"sku": "SKU-A", "units_sold": "5", "units_sold_truth_30d": "5", "units_sold_roi": "5", "revenue_exvat_gbp": "50", "profit_exvat_gbp": "10"},
                    {"sku": "SKU-B", "units_sold": "3", "units_sold_truth_30d": "3", "units_sold_roi": "3", "revenue_exvat_gbp": "30", "profit_exvat_gbp": "6"},
                ]
            ).to_csv(summary, index=False)
            pd.DataFrame(
                [
                    {"study_rank": "1", "sku": "SKU-A", "units_sold_30d": "5", "units_sold_truth_30d": "4", "revenue_exvat_gbp_30d": "50", "profit_exvat_gbp_30d": "10"},
                    {"study_rank": "2", "sku": "SKU-B", "units_sold_30d": "3", "units_sold_truth_30d": "3", "revenue_exvat_gbp_30d": "30", "profit_exvat_gbp_30d": "6"},
                ]
            ).to_csv(study, index=False)

            stats = a015._e_study_report_truth_alignment_stats(summary, study)
            self.assertTrue(bool(stats.get("ready", False)))
            self.assertEqual(str(stats.get("status", "")), "fail")
            self.assertEqual(int(stats.get("roi_row_count", 0)), 2)
            self.assertEqual(int(stats.get("mismatch_rows", 0)), 1)

    def test_e_study_report_truth_alignment_stats_ok_when_truth_matches(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            summary = root / "sku_performance_summary.csv"
            study = root / "e_study_report.csv"
            pd.DataFrame(
                [
                    {"sku": "SKU-A", "units_sold": "5", "units_sold_truth_30d": "5", "units_sold_roi": "5", "revenue_exvat_gbp": "50", "profit_exvat_gbp": "10"},
                ]
            ).to_csv(summary, index=False)
            pd.DataFrame(
                [
                    {"study_rank": "1", "sku": "SKU-A", "units_sold_30d": "5", "units_sold_truth_30d": "5", "revenue_exvat_gbp_30d": "50", "profit_exvat_gbp_30d": "10"},
                ]
            ).to_csv(study, index=False)

            stats = a015._e_study_report_truth_alignment_stats(summary, study)
            self.assertTrue(bool(stats.get("ready", False)))
            self.assertEqual(str(stats.get("status", "")), "ok")
            self.assertEqual(int(stats.get("mismatch_rows", 0)), 0)

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
  "final_state": "completed",
  "configured_step_count": 1,
  "recorded_step_count": 1,
  "health_summary": {"status": "current", "current_cycle_evidence": true},
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
  "final_state": "completed",
  "configured_step_count": 1,
  "recorded_step_count": 1,
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
  "final_state": "completed",
  "configured_step_count": 1,
  "recorded_step_count": 1,
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
  "final_state": "completed",
  "configured_step_count": 1,
  "recorded_step_count": 1,
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
        self.assertEqual(Path(a_runtime["alert_history_path"]), a015.ALERT_HISTORY_A_CSV)
        self.assertEqual(Path(a_runtime["health_status_path"]), a015.HEALTH_STATUS_A_CSV)

        self.assertEqual(b_runtime["profile"], "b")
        self.assertEqual(Path(b_runtime["checklist_path"]), a015.CHECKLIST_B_SPLIT_CSV)
        self.assertEqual(Path(b_runtime["alert_state_path"]), a015.ALERT_STATE_B_CSV)
        self.assertEqual(Path(b_runtime["alert_history_path"]), a015.ALERT_HISTORY_B_CSV)
        self.assertEqual(Path(b_runtime["health_status_path"]), a015.HEALTH_STATUS_B_CSV)
        self.assertTrue(bool(b_runtime["no_toast"]))

        self.assertEqual(e_runtime["profile"], "e")
        self.assertEqual(Path(e_runtime["checklist_path"]), a015.CHECKLIST_E_SPLIT_CSV)
        self.assertEqual(Path(e_runtime["alert_state_path"]), a015.ALERT_STATE_E_CSV)
        self.assertEqual(Path(e_runtime["alert_history_path"]), a015.ALERT_HISTORY_E_CSV)
        self.assertEqual(Path(e_runtime["health_status_path"]), a015.HEALTH_STATUS_E_CSV)

        self.assertEqual(h_runtime["profile"], "h")
        self.assertEqual(Path(h_runtime["checklist_path"]), a015.CHECKLIST_H_GATE_CSV)
        self.assertEqual(Path(h_runtime["alert_state_path"]), a015.ALERT_STATE_H_CSV)
        self.assertEqual(Path(h_runtime["alert_history_path"]), a015.ALERT_HISTORY_H_CSV)
        self.assertEqual(Path(h_runtime["health_status_path"]), a015.HEALTH_STATUS_H_CSV)
        self.assertFalse(bool(h_runtime["no_toast"]))

        self.assertEqual(g_runtime["profile"], "global")
        self.assertEqual(Path(g_runtime["checklist_path"]), a015.CHECKLIST_CSV)
        self.assertEqual(Path(g_runtime["alert_state_path"]), a015.ALERT_STATE_CSV)
        self.assertEqual(Path(g_runtime["alert_history_path"]), a015.ALERT_HISTORY_CSV)
        self.assertEqual(Path(g_runtime["health_status_path"]), a015.HEALTH_STATUS_CSV)

    def test_run_main_fail_closed_uses_profile_paths_from_cli(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "out"
            out.mkdir(parents=True, exist_ok=True)
            checklist_path = out / "checklist_b_custom.csv"
            alert_state_path = out / "alert_state_b_custom.csv"
            alert_history_path = out / "alert_history_b_custom.csv"
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
                    "--alert-history-path",
                    str(alert_history_path),
                    "--health-status-path",
                    str(health_status_path),
                    "--no-toast",
                ]
                rc = a015._run_main_fail_closed(_explode)
            finally:
                sys.argv = old_argv

            self.assertEqual(rc, 2)
            self.assertTrue(checklist_path.exists())
            self.assertTrue(alert_history_path.exists())
            self.assertTrue(health_status_path.exists())
            df = pd.read_csv(checklist_path, dtype=str).fillna("")
            self.assertTrue((df["check"] == "a015_runtime_exception").any())
            status_df = pd.read_csv(health_status_path, dtype=str).fillna("")
            self.assertTrue((status_df["status"] == "FAIL").any())

    def test_alert_lifecycle_moves_resolved_to_history_and_reopens_on_new_fail(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state_path = root / "alert_state.csv"
            history_path = root / "alert_history.csv"

            fail_df = pd.DataFrame([{"check": "h_cycle_log_freshness", "status": "fail", "value": "1", "notes": "stale"}])
            first_now = datetime(2026, 4, 3, 9, 0, 0, tzinfo=timezone.utc)
            out_1 = a015._apply_alert_aging(
                fail_df,
                state_path,
                first_now,
                history_path=history_path,
                recompute_source="checklist_H.csv",
                profile="h",
            )
            self.assertEqual(str(out_1.iloc[0]["alert_consecutive_runs"]), "1")
            state_1 = pd.read_csv(state_path, dtype=str).fillna("")
            self.assertEqual(len(state_1.index), 1)
            self.assertEqual(str(state_1.iloc[0]["status"]).lower(), "fail")

            ok_df = pd.DataFrame([{"check": "h_cycle_log_freshness", "status": "ok", "value": "0", "notes": "fresh"}])
            second_now = datetime(2026, 4, 3, 9, 5, 0, tzinfo=timezone.utc)
            a015._apply_alert_aging(
                ok_df,
                state_path,
                second_now,
                history_path=history_path,
                recompute_source="checklist_H.csv",
                profile="h",
            )
            state_2 = pd.read_csv(state_path, dtype=str).fillna("")
            self.assertTrue(state_2.empty)

            history = pd.read_csv(history_path, dtype=str).fillna("")
            opened = history.loc[(history["check"] == "h_cycle_log_freshness") & (history["event_type"] == "opened")]
            cleared = history.loc[(history["check"] == "h_cycle_log_freshness") & (history["event_type"] == "cleared")]
            self.assertEqual(len(opened.index), 1)
            self.assertEqual(len(cleared.index), 1)
            self.assertEqual(str(cleared.iloc[0]["clear_reason"]), "contradicted_by_newer_healthy_evidence")

            fail_again_df = pd.DataFrame([{"check": "h_cycle_log_freshness", "status": "fail", "value": "1", "notes": "stale_again"}])
            third_now = datetime(2026, 4, 3, 9, 10, 0, tzinfo=timezone.utc)
            out_3 = a015._apply_alert_aging(
                fail_again_df,
                state_path,
                third_now,
                history_path=history_path,
                recompute_source="checklist_H.csv",
                profile="h",
            )
            self.assertEqual(str(out_3.iloc[0]["alert_consecutive_runs"]), "1")
            state_3 = pd.read_csv(state_path, dtype=str).fillna("")
            self.assertEqual(len(state_3.index), 1)
            self.assertEqual(str(state_3.iloc[0]["status"]).lower(), "fail")

            history_2 = pd.read_csv(history_path, dtype=str).fillna("")
            opened_2 = history_2.loc[(history_2["check"] == "h_cycle_log_freshness") & (history_2["event_type"] == "opened")]
            self.assertEqual(len(opened_2.index), 2)

    def test_h_publish_marker_freshness_uses_terminal_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            publish_path = root / "H_cycle_last_publish_info.txt"
            terminal_path = root / "H_cycle_last_terminal_info.txt"
            publish_path.write_text("run_id=old\nutc=2026-04-01T08:00:00Z\nstatus=ok\n", encoding="utf-8")
            terminal_path.write_text(
                "run_id=recent\nutc=2026-04-01T11:59:00Z\nstate=failed\npublish_status=not_started\n",
                encoding="utf-8",
            )
            stale_ts = datetime(2026, 4, 1, 8, 0, 0, tzinfo=timezone.utc).timestamp()
            fresh_ts = datetime(2026, 4, 1, 11, 59, 0, tzinfo=timezone.utc).timestamp()
            os.utime(publish_path, (stale_ts, stale_ts))
            os.utime(terminal_path, (fresh_ts, fresh_ts))

            old_publish = list(a015.H_PUBLISH_INFO_PATH_CANDIDATES)
            old_terminal = list(a015.H_TERMINAL_INFO_PATH_CANDIDATES)
            try:
                a015.H_PUBLISH_INFO_PATH_CANDIDATES = [publish_path]
                a015.H_TERMINAL_INFO_PATH_CANDIDATES = [terminal_path]
                rows: list[dict[str, str]] = []
                a015._h_publish_marker_freshness_check(
                    rows,
                    now_utc=datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc),
                )
            finally:
                a015.H_PUBLISH_INFO_PATH_CANDIDATES = old_publish
                a015.H_TERMINAL_INFO_PATH_CANDIDATES = old_terminal

            row = next((r for r in rows if r.get("check") == "h_publish_marker_freshness"), {})
            self.assertEqual(str(row.get("status", "")), "warn")
            self.assertIn("source=terminal_marker_fallback", str(row.get("notes", "")))

    def test_a_inventory_stale_token_gap_stats_fails_on_unresolved_stale_undercount(self) -> None:
        inventory = pd.DataFrame(
            [
                {
                    "seller_sku": "2X-8XI7-C9T5",
                    "available": "1",
                    "in_stock_supply_quantity": "1",
                    "total_quantity": "7",
                    "row_last_updated_is_stale": "1",
                    "row_last_updated_status": "STALE",
                    "last_updated_time": "2026-04-01T20:13:35Z",
                }
            ]
        )
        token_rows = [{"token_id": f"T{i}", "seller_sku": "2X-8XI7-C9T5", "status": "available"} for i in range(32)]
        token_ledger = pd.DataFrame(token_rows)

        stats = a015._a_inventory_stale_token_gap_stats(
            inventory,
            token_ledger,
            scope_skus={"2X-8XI7-C9T5"},
            now_utc=datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(str(stats.get("status", "")), "fail")
        self.assertEqual(int(stats.get("unresolved_gap_rows", 0)), 1)
        self.assertEqual(int(stats.get("unresolved_available_gap_rows", 0)), 1)
        self.assertEqual(int(stats.get("stale_scope_rows", 0)), 1)

    def test_a_inventory_stale_token_gap_stats_ok_when_stale_row_matches_token_floor(self) -> None:
        inventory = pd.DataFrame(
            [
                {
                    "seller_sku": "2X-8XI7-C9T5",
                    "available": "30",
                    "in_stock_supply_quantity": "30",
                    "total_quantity": "34",
                    "row_last_updated_is_stale": "1",
                    "row_last_updated_status": "STALE",
                    "last_updated_time": "2026-04-01T20:13:35Z",
                }
            ]
        )
        token_rows = [{"token_id": f"A{i}", "seller_sku": "2X-8XI7-C9T5", "status": "available"} for i in range(30)]
        token_rows.extend(
            [{"token_id": f"B{i}", "seller_sku": "2X-8XI7-C9T5", "status": "allocated"} for i in range(4)]
        )
        token_ledger = pd.DataFrame(token_rows)

        stats = a015._a_inventory_stale_token_gap_stats(
            inventory,
            token_ledger,
            scope_skus={"2X-8XI7-C9T5"},
            now_utc=datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(str(stats.get("status", "")), "ok")
        self.assertEqual(int(stats.get("unresolved_gap_rows", 0)), 0)
        self.assertEqual(int(stats.get("stale_scope_rows", 0)), 1)


if __name__ == "__main__":
    unittest.main()
