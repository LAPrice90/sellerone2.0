import csv
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from scripts.flows.H import H110_run_phase1_h_pilot as h110


class H110StockStaleGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.out = self.root / "out"
        self.h_live = self.out / "systems" / "H" / "live"
        self.out.mkdir(parents=True, exist_ok=True)
        self.h_live.mkdir(parents=True, exist_ok=True)

        self.inventory_snapshot = self.out / "inventory_snapshot_2026-04-09.csv"
        self.order_master = self.out / "order_master.csv"
        self.token_ledger = self.out / "token_ledger_live.csv"
        self.inventory_summaries = self.out / "inventory_summaries.csv"
        self.parking_snapshot = self.out / "parking" / "stock_snapshot_latest.csv"

        self.patches = [
            mock.patch.object(h110, "ROOT", self.root),
            mock.patch.object(h110, "OUT", self.out),
            mock.patch.object(h110, "H_LIVE_DIR", self.h_live),
            mock.patch.object(h110, "ORDER_MASTER_PATH", self.order_master),
            mock.patch.object(h110, "TOKEN_LEDGER_PATH", self.token_ledger),
            mock.patch.object(h110, "INVENTORY_SUMMARIES_PATH", self.inventory_summaries),
            mock.patch.object(h110, "DEFAULT_STOCK_SNAPSHOT_PATH", self.parking_snapshot),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.tmpdir.cleanup()

    def _write_csv(self, path: Path, headers: list[str], rows: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k, "") for k in headers})

    def _write_inventory_snapshot(
        self,
        *,
        available: int,
        total_quantity: int | None = None,
        last_updated_time: str = "2026-04-01T14:44:37Z",
    ) -> None:
        total_qty = total_quantity if total_quantity is not None else available
        self._write_csv(
            self.inventory_snapshot,
            [
                "timestamp_utc",
                "asof_date",
                "sku",
                "available",
                "total_quantity",
                "inbound_working",
                "inbound_shipped",
                "inbound_receiving",
                "last_updated_time",
            ],
            [
                {
                    "timestamp_utc": "2026-04-09T00:03:41Z",
                    "asof_date": "2026-04-09",
                    "sku": "2T-07RT-8IMX",
                    "available": str(available),
                    "total_quantity": str(total_qty),
                    "inbound_working": "0",
                    "inbound_shipped": "0",
                    "inbound_receiving": "0",
                    "last_updated_time": last_updated_time,
                }
            ],
        )

    def _write_parking_snapshot(self, *, total_qty: int) -> None:
        self._write_csv(
            self.parking_snapshot,
            ["sku", "total_qty", "asof_utc"],
            [
                {
                    "sku": "2T-07RT-8IMX",
                    "total_qty": str(total_qty),
                    "asof_utc": "2026-04-09T11:59:00Z",
                }
            ],
        )

    def _write_order_master_with_post_update_sales(self, *, qty: int) -> None:
        self._write_csv(
            self.order_master,
            ["SKU", "Date", "Quantity Ordered"],
            [
                {
                    "SKU": "2T-07RT-8IMX",
                    "Date": "2026-04-04T09:06:46Z",
                    "Quantity Ordered": str(qty),
                }
            ],
        )

    def _run_filter(self) -> tuple[list[dict[str, str]], dict[str, str]]:
        return h110._apply_stock_universe_filter(
            due_rows=[{"sku": "2T-07RT-8IMX"}],
            now_utc=datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc),
            today_utc="2026-04-09",
        )

    def test_stale_inventory_is_excluded_when_sales_exhausted_and_no_tokens_available(self) -> None:
        self._write_inventory_snapshot(available=8)
        self._write_order_master_with_post_update_sales(qty=8)
        self._write_csv(
            self.token_ledger,
            ["seller_sku", "status", "token_id"],
            [{"seller_sku": "2T-07RT-8IMX", "status": "allocated", "token_id": "T1"}],
        )

        eligible_rows, summary = self._run_filter()

        self.assertEqual(len(eligible_rows), 0)
        self.assertEqual(summary.get("excluded_oos"), "1")
        self.assertEqual(summary.get("stale_sales_overrides"), "1")

    def test_stale_inventory_is_not_forced_out_when_tokens_still_available(self) -> None:
        self._write_inventory_snapshot(available=8)
        self._write_order_master_with_post_update_sales(qty=8)
        self._write_csv(
            self.token_ledger,
            ["seller_sku", "status", "token_id"],
            [
                {"seller_sku": "2T-07RT-8IMX", "status": "available", "token_id": "T1"},
                {"seller_sku": "2T-07RT-8IMX", "status": "allocated", "token_id": "T2"},
            ],
        )

        eligible_rows, summary = self._run_filter()

        self.assertEqual(len(eligible_rows), 1)
        self.assertEqual(summary.get("excluded_oos"), "0")
        self.assertEqual(summary.get("stale_sales_overrides"), "0")

    def test_stale_authoritative_stock_uses_token_floor_when_higher_than_fallback(self) -> None:
        self._write_inventory_snapshot(available=1, total_quantity=1, last_updated_time="2026-04-01T14:44:37Z")
        self._write_parking_snapshot(total_qty=7)
        token_rows = [{"seller_sku": "2T-07RT-8IMX", "status": "available", "token_id": f"T{i}"} for i in range(1, 31)]
        self._write_csv(self.token_ledger, ["seller_sku", "status", "token_id"], token_rows)

        eligible_rows, summary = self._run_filter()

        self.assertEqual(len(eligible_rows), 1)
        self.assertEqual(summary.get("stale_row_token_fallbacks"), "1")
        self.assertEqual((summary.get("available_stock_by_sku") or {}).get("2T-07RT-8IMX"), "30.00")

    def test_stale_authoritative_stock_without_safe_fallback_is_quarantined(self) -> None:
        self._write_inventory_snapshot(available=3, total_quantity=3, last_updated_time="2026-04-01T14:44:37Z")

        eligible_rows, summary = self._run_filter()

        self.assertEqual(len(eligible_rows), 0)
        self.assertEqual(summary.get("excluded_unknown"), "1")
        self.assertEqual(summary.get("excluded_stale"), "1")
        self.assertEqual(summary.get("stale_row_unknown_quarantined"), "1")

    def test_stale_low_stock_is_not_selected_when_fresher_higher_evidence_exists(self) -> None:
        self._write_csv(
            self.inventory_snapshot,
            [
                "timestamp_utc",
                "asof_date",
                "sku",
                "available",
                "total_quantity",
                "inbound_working",
                "inbound_shipped",
                "inbound_receiving",
                "last_updated_time",
            ],
            [
                {
                    "timestamp_utc": "2026-04-09T00:03:41Z",
                    "asof_date": "2026-04-09",
                    "sku": "2X-8XI7-C9T5",
                    "available": "1",
                    "total_quantity": "1",
                    "inbound_working": "0",
                    "inbound_shipped": "0",
                    "inbound_receiving": "0",
                    "last_updated_time": "2026-04-01T14:44:37Z",
                }
            ],
        )
        self._write_csv(
            self.parking_snapshot,
            ["sku", "total_qty", "asof_utc"],
            [
                {
                    "sku": "2X-8XI7-C9T5",
                    "total_qty": "35",
                    "asof_utc": "2026-04-09T11:59:00Z",
                }
            ],
        )
        token_rows = [{"seller_sku": "2X-8XI7-C9T5", "status": "available", "token_id": f"T{i}"} for i in range(1, 33)]
        self._write_csv(self.token_ledger, ["seller_sku", "status", "token_id"], token_rows)

        eligible_rows, summary = h110._apply_stock_universe_filter(
            due_rows=[{"sku": "2X-8XI7-C9T5"}],
            now_utc=datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc),
            today_utc="2026-04-09",
        )

        self.assertEqual(len(eligible_rows), 1)
        self.assertEqual((summary.get("available_stock_by_sku") or {}).get("2X-8XI7-C9T5"), "35.00")
        self.assertEqual(summary.get("stale_undercount_protections"), "1")
        self.assertNotEqual((summary.get("available_stock_by_sku") or {}).get("2X-8XI7-C9T5"), "1.00")

    def test_inventory_snapshot_age_uses_timestamp_utc_before_asof_date(self) -> None:
        self._write_inventory_snapshot(
            available=8,
            last_updated_time="2026-04-09T11:45:00Z",
        )
        os.utime(
            self.inventory_snapshot,
            (
                datetime(2026, 4, 9, 0, 4, 0, tzinfo=timezone.utc).timestamp(),
                datetime(2026, 4, 9, 0, 4, 0, tzinfo=timezone.utc).timestamp(),
            ),
        )

        eligible_rows, summary = self._run_filter()

        self.assertEqual(len(eligible_rows), 1)
        self.assertEqual(summary.get("stock_snapshot_age_hours"), "11.94")

        self._write_csv(
            self.inventory_snapshot,
            [
                "timestamp_utc",
                "asof_date",
                "sku",
                "available",
                "total_quantity",
                "inbound_working",
                "inbound_shipped",
                "inbound_receiving",
                "last_updated_time",
            ],
            [
                {
                    "timestamp_utc": "2026-04-09T11:30:00Z",
                    "asof_date": "2026-04-09",
                    "sku": "2T-07RT-8IMX",
                    "available": "8",
                    "total_quantity": "8",
                    "inbound_working": "0",
                    "inbound_shipped": "0",
                    "inbound_receiving": "0",
                    "last_updated_time": "2026-04-09T11:45:00Z",
                }
            ],
        )
        os.utime(
            self.inventory_snapshot,
            (
                datetime(2026, 4, 9, 11, 31, 0, tzinfo=timezone.utc).timestamp(),
                datetime(2026, 4, 9, 11, 31, 0, tzinfo=timezone.utc).timestamp(),
            ),
        )

        eligible_rows, summary = self._run_filter()

        self.assertEqual(len(eligible_rows), 1)
        self.assertEqual(summary.get("stock_snapshot_age_hours"), "0.50")


if __name__ == "__main__":
    unittest.main()
