from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

import pandas as pd

from scripts.flows.A import A003_run_inventory_to_sheet as a003


class A003InventoryStaleTokenFloorTests(unittest.TestCase):
    def test_apply_inventory_stale_token_floor_applies_token_floor_for_stale_scope_row(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "seller_sku": "2X-8XI7-C9T5",
                    "available": "1",
                    "in_stock_supply_quantity": "1",
                    "total_quantity": "7",
                    "last_updated_time": "2026-04-01T20:13:35Z",
                }
            ]
        )
        with mock.patch.dict(os.environ, {"A003_STOCK_ROW_STALE_HOURS": "24"}, clear=False):
            with mock.patch.object(
                a003,
                "_load_token_stock_maps",
                return_value=({"2X-8XI7-C9T5": 32}, {"2X-8XI7-C9T5": 32}),
            ):
                out_df, summary = a003._apply_inventory_stale_token_floor(
                    df,
                    scope_skus={"2X-8XI7-C9T5"},
                    now_utc=datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc),
                )

        self.assertEqual(int(out_df.iloc[0]["available"]), 32)
        self.assertEqual(int(out_df.iloc[0]["in_stock_supply_quantity"]), 32)
        self.assertEqual(int(out_df.iloc[0]["total_quantity"]), 32)
        self.assertEqual(str(out_df.iloc[0]["row_stock_truth_adjustment"]), "TOKEN_FLOOR")
        self.assertEqual(str(out_df.iloc[0]["row_stock_truth_source"]), "SPAPI_TOKEN_FLOOR")
        self.assertEqual(str(out_df.iloc[0]["row_last_updated_status"]), "STALE")
        self.assertEqual(str(out_df.iloc[0]["row_last_updated_is_stale"]), "1")
        self.assertEqual(int(summary.get("token_floor_rows", 0)), 1)
        self.assertEqual(int(summary.get("stale_scope_rows", 0)), 1)

    def test_apply_inventory_stale_token_floor_keeps_fresh_row_unadjusted(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "seller_sku": "2X-8XI7-C9T5",
                    "available": "1",
                    "in_stock_supply_quantity": "1",
                    "total_quantity": "7",
                    "last_updated_time": "2026-04-22T10:30:00Z",
                }
            ]
        )
        with mock.patch.dict(os.environ, {"A003_STOCK_ROW_STALE_HOURS": "24"}, clear=False):
            with mock.patch.object(
                a003,
                "_load_token_stock_maps",
                return_value=({"2X-8XI7-C9T5": 32}, {"2X-8XI7-C9T5": 32}),
            ):
                out_df, summary = a003._apply_inventory_stale_token_floor(
                    df,
                    scope_skus={"2X-8XI7-C9T5"},
                    now_utc=datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc),
                )

        self.assertEqual(int(out_df.iloc[0]["available"]), 1)
        self.assertEqual(int(out_df.iloc[0]["in_stock_supply_quantity"]), 1)
        self.assertEqual(int(out_df.iloc[0]["total_quantity"]), 7)
        self.assertEqual(str(out_df.iloc[0]["row_stock_truth_adjustment"]), "")
        self.assertEqual(str(out_df.iloc[0]["row_stock_truth_source"]), "SPAPI")
        self.assertEqual(str(out_df.iloc[0]["row_last_updated_status"]), "FRESH")
        self.assertEqual(str(out_df.iloc[0]["row_last_updated_is_stale"]), "0")
        self.assertEqual(int(summary.get("token_floor_rows", 0)), 0)
        self.assertEqual(int(summary.get("stale_scope_rows", 0)), 0)

    def test_main_persists_corrected_inventory_summary_through_sql_compat(self) -> None:
        raw_inventory = pd.DataFrame(
            [
                {
                    "seller_sku": "2X-8XI7-C9T5",
                    "available": "1",
                    "in_stock_supply_quantity": "1",
                    "total_quantity": "1",
                    "last_updated_time": "2026-04-01T20:13:35Z",
                }
            ]
        )
        captured_writes = []

        def capture_write(dataframe: pd.DataFrame, path, table_name: str):
            captured_writes.append((dataframe.copy(), str(path), table_name))
            return {"csv_rows": len(dataframe), "sql_rows": len(dataframe)}

        with mock.patch.multiple(
            a003,
            WRITE_SHEETS=False,
            WRITE_PRODUCT_DB=False,
            USE_API_OWNER=False,
            INPUT_CSV="out/__missing_inventory_scope_for_test__.csv",
            MARKETPLACE_ID="TEST",
        ):
            with mock.patch.object(a003, "_collect_inventory_direct", return_value=(raw_inventory, 0, 1)):
                with mock.patch.object(
                    a003,
                    "_load_token_stock_maps",
                    return_value=({"2X-8XI7-C9T5": 9}, {"2X-8XI7-C9T5": 9}),
                ):
                    with mock.patch.object(a003, "write_dataframe_with_sql_compat", side_effect=capture_write):
                        with mock.patch.object(
                            a003,
                            "_persist_inventory_contract_outputs",
                            return_value=(
                                "out/inventory_snapshot_2026-04-30.csv",
                                "out/inventory_snapshot_latest.csv",
                                1,
                            ),
                        ):
                            with mock.patch.dict(os.environ, {"A003_STOCK_ROW_STALE_HOURS": "24"}, clear=False):
                                rc = a003.main()

        self.assertEqual(rc, 0)
        inventory_writes = [
            item
            for item in captured_writes
            if item[1].replace("\\", "/").endswith("out/inventory_summaries.csv")
        ]
        self.assertEqual(len(inventory_writes), 1)
        written_df, _, table_name = inventory_writes[0]
        self.assertEqual(table_name, "a_inventory_summaries")
        self.assertEqual(int(written_df.iloc[0]["available"]), 9)
        self.assertEqual(str(written_df.iloc[0]["row_stock_truth_source"]), "SPAPI_TOKEN_FLOOR")

    def test_inventory_history_rewrite_persists_through_sql_compat(self) -> None:
        contract = pd.DataFrame(
            [
                {
                    "timestamp_utc": "2026-04-30T13:10:22Z",
                    "asof_date": "2026-04-30",
                    "marketplace": "UK",
                    "sku": "2X-8XI7-C9T5",
                    "asin": "A1",
                    "available": "9",
                    "inbound_working": "0",
                    "inbound_shipped": "0",
                    "inbound_receiving": "0",
                    "inbound_total": "0",
                    "unsellable": "0",
                    "researching": "0",
                    "reserved_transfers": "0",
                    "reserved_processing": "0",
                    "reserved_customer": "0",
                    "total_quantity": "9",
                    "last_updated_time": "2026-04-01T20:13:35Z",
                    "source": "SPAPI_TOKEN_FLOOR",
                    "notes": "TOKEN_FLOOR",
                }
            ]
        )
        captured_sql_writes = []

        def capture_sql_write(dataframe: pd.DataFrame, path, table_name: str):
            captured_sql_writes.append((dataframe.copy(), str(path), table_name))
            return {"csv_rows": len(dataframe), "sql_rows": len(dataframe)}

        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp_dir:
            try:
                os.chdir(tmp_dir)
                with mock.patch.object(a003, "write_csv_with_compat") as csv_writer:
                    with mock.patch.object(a003, "write_dataframe_with_sql_compat", side_effect=capture_sql_write):
                        history = a003._rewrite_inventory_history_today(contract, "2026-04-30")
            finally:
                os.chdir(cwd)

        self.assertEqual(len(history), 1)
        csv_writer.assert_called_once()
        inventory_history_writes = [
            item
            for item in captured_sql_writes
            if item[1].replace("\\", "/").endswith("out/inventory_history.csv")
        ]
        self.assertEqual(len(inventory_history_writes), 1)
        written_df, _, table_name = inventory_history_writes[0]
        self.assertEqual(table_name, "a_inventory_history")
        self.assertEqual(int(written_df.iloc[0]["available"]), 9)


if __name__ == "__main__":
    unittest.main()
