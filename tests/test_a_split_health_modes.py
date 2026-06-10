import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_A_all as a_cycle
from scripts.flows.A import A020_run_daily_finance as a020


class ASplitHealthModeTests(unittest.TestCase):
    def test_inventory_refresh_is_not_skipped_by_legacy_sheet_output_flag(self) -> None:
        self.assertIn("A003_run_inventory_to_sheet.py", a_cycle.RUN_ORDER)
        self.assertNotIn("A003_run_inventory_to_sheet.py", a_cycle.LEGACY_SHEET_OUTPUT_STEPS)
        self.assertIn(
            "out/inventory_snapshot_latest.csv",
            a_cycle.STEP_ARTIFACTS["A003_run_inventory_to_sheet.py"],
        )

    def test_a001_local_refresh_is_not_skipped_by_legacy_sheet_output_flag(self) -> None:
        self.assertIn("A001_run_listings_to_sheet.py", a_cycle.RUN_ORDER)
        self.assertNotIn("A001_run_listings_to_sheet.py", a_cycle.LEGACY_SHEET_OUTPUT_STEPS)
        self.assertIn("A001_run_listings_to_sheet.py", a_cycle.LOCAL_REFRESH_WITH_LEGACY_SHEETS_DISABLED)
        self.assertIn(
            "out/merchant_listings_latest.csv",
            a_cycle.STEP_ARTIFACTS["A001_run_listings_to_sheet.py"],
        )

    def test_a002_and_a004_refresh_locally_when_legacy_sheets_are_disabled(self) -> None:
        self.assertIn("A002_run_catalog_items_to_sheet.py", a_cycle.RUN_ORDER)
        self.assertIn("A004_run_fees_to_sheet.py", a_cycle.RUN_ORDER)
        self.assertNotIn("A002_run_catalog_items_to_sheet.py", a_cycle.LEGACY_SHEET_OUTPUT_STEPS)
        self.assertNotIn("A004_run_fees_to_sheet.py", a_cycle.LEGACY_SHEET_OUTPUT_STEPS)
        self.assertIn("A002_run_catalog_items_to_sheet.py", a_cycle.LOCAL_REFRESH_WITH_LEGACY_SHEETS_DISABLED)
        self.assertIn("A004_run_fees_to_sheet.py", a_cycle.LOCAL_REFRESH_WITH_LEGACY_SHEETS_DISABLED)

    def test_sheet_only_product_db_steps_are_not_in_normal_a_run_order(self) -> None:
        self.assertNotIn("dedupe_product_db.py", a_cycle.RUN_ORDER)
        self.assertNotIn("sync_product_db_to_main_sheet.py", a_cycle.RUN_ORDER)
        self.assertIn("dedupe_product_db.py", a_cycle.LEGACY_SHEET_ONLY_PRODUCT_DB_STEPS)
        self.assertIn("sync_product_db_to_main_sheet.py", a_cycle.LEGACY_SHEET_ONLY_PRODUCT_DB_STEPS)

    def test_stock_receipts_sheet_is_enabled_by_default(self) -> None:
        self.assertTrue(a_cycle.A_ENABLE_STOCK_RECEIPTS_SHEET)

    def test_legacy_sheet_steps_are_disabled_by_default(self) -> None:
        self.assertTrue(a_cycle.A_SKIP_LEGACY_SHEET_OUTPUT_STEPS)

    def test_a020_daily_finance_defaults_to_no_sheet_writes(self) -> None:
        env = a020.apply_no_sheet_defaults({})
        self.assertEqual(env["FIN_L3_SKIP_SHEETS"], "1")
        self.assertEqual(env["STOCK_EVENTS_WRITE_SHEETS"], "0")
        self.assertEqual(env["TOKEN_EVENTS_WRITE_SHEETS"], "0")
        self.assertEqual(env["TOKEN_PROOF_PACK_WRITE_SHEETS"], "0")
        self.assertEqual(env["VAT_REPORT_WRITE_SHEETS"], "0")
        self.assertEqual(env["PNL_WRITE_SHEETS"], "0")

    def test_a020_daily_finance_does_not_override_explicit_env(self) -> None:
        env = a020.apply_no_sheet_defaults({"STOCK_EVENTS_WRITE_SHEETS": "1"})
        self.assertEqual(env["STOCK_EVENTS_WRITE_SHEETS"], "1")

    def test_a003_and_a016_retry_stale_producer_outputs_once(self) -> None:
        stale = {"verification_status": "failed_stale_outputs"}
        missing = {"verification_status": "failed_missing_outputs"}
        self.assertTrue(a_cycle._should_retry_stale_outputs("A003_run_inventory_to_sheet.py", stale))
        self.assertTrue(a_cycle._should_retry_stale_outputs("A016_refresh_phase1_daily_intel.py", missing))
        self.assertFalse(a_cycle._should_retry_stale_outputs("A005_run_inventory_adjustments_report.py", stale))

    def test_pid_alive_treats_windows_access_denied_as_alive(self) -> None:
        result = mock.Mock()
        result.stdout = ""
        result.stderr = "ERROR: Access denied"
        with mock.patch.object(a_cycle.os, "name", "nt"), mock.patch.object(
            a_cycle.subprocess,
            "run",
            return_value=result,
        ):
            self.assertTrue(a_cycle._pid_alive(3808))

    def test_append_a_step_records_child_output_tails(self) -> None:
        manifest = a_cycle.new_manifest(cycle="A", run_id="TEST_A_OUTPUT_TAIL")
        a_cycle._append_a_step(
            manifest,
            name="A005_run_inventory_adjustments_report.py",
            step_started="2026-05-18T12:00:00Z",
            rc=1,
            notes="fatal step failure",
            step_status="failed",
            verification_status="child_rc_nonzero",
            stdout_tail="",
            stderr_tail="ERROR: Access denied reading secrets/.env",
        )

        step = manifest["steps"][0]
        self.assertEqual(step["verification_status"], "child_rc_nonzero")
        self.assertIn("secrets/.env", step["stderr_tail"])

    def test_shadow_state_and_auto_cutover_for_a(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_state_path = a_cycle.FLOW_SELFTEST_STATE_PATH
            old_mode = a_cycle.A_SPLIT_HEALTH_MODE
            try:
                a_cycle.FLOW_SELFTEST_STATE_PATH = root / "flow_selftest_state.json"
                a_cycle.A_SPLIT_HEALTH_MODE = "shadow"
                a_cycle._write_flow_selftest_state(
                    {
                        "a_match_streak": 9,
                        "b_match_streak": 10,
                        "e_match_streak": 10,
                        "ready_for_cutover": False,
                        "updated_utc": "2026-02-18T00:00:00Z",
                    }
                )
                updated = a_cycle._update_a_shadow_streak(True)
                self.assertEqual(int(updated.get("a_match_streak", 0)), 10)
                self.assertEqual(int(updated.get("b_match_streak", 0)), 10)
                self.assertEqual(int(updated.get("e_match_streak", 0)), 10)
                self.assertTrue(bool(updated.get("ready_for_cutover", False)))
                self.assertEqual(a_cycle._effective_a_split_mode(), "split")
            finally:
                a_cycle.FLOW_SELFTEST_STATE_PATH = old_state_path
                a_cycle.A_SPLIT_HEALTH_MODE = old_mode

    def test_append_flow_selftest_compare_writes_row(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_compare = a_cycle.FLOW_SELFTEST_COMPARE_PATH
            try:
                a_cycle.FLOW_SELFTEST_COMPARE_PATH = root / "flow_selftest_compare.csv"
                a_cycle._append_flow_selftest_compare(
                    {
                        "timestamp_utc": "2026-02-18T10:00:00Z",
                        "cycle_start_utc": "20260218T100000Z",
                        "cycle": "A",
                        "mode_requested": "shadow",
                        "mode_effective": "shadow",
                        "legacy_fail_count": "0",
                        "legacy_warn_count": "1",
                        "legacy_gate_block": "0",
                        "split_fail_count": "0",
                        "split_warn_count": "0",
                        "split_gate_block": "0",
                        "decision_match": "1",
                        "a_match_streak": "7",
                        "b_match_streak": "8",
                        "e_match_streak": "9",
                        "ready_for_cutover": "0",
                        "legacy_source": "system_health_checklist.csv",
                        "split_source": "checklist_A_split.csv",
                        "notes": "ok",
                    }
                )
                df = pd.read_csv(a_cycle.FLOW_SELFTEST_COMPARE_PATH, dtype=str).fillna("")
                self.assertEqual(len(df.index), 1)
                self.assertEqual(df.loc[0, "cycle"], "A")
                self.assertEqual(df.loc[0, "split_source"], "checklist_A_split.csv")
            finally:
                a_cycle.FLOW_SELFTEST_COMPARE_PATH = old_compare


if __name__ == "__main__":
    unittest.main()

