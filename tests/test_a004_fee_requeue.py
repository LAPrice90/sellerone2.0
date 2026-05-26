import sqlite3
import sys
import types
import unittest
from pathlib import Path

import pandas as pd

if "gspread" not in sys.modules:
    sys.modules["gspread"] = types.SimpleNamespace(service_account=lambda *args, **kwargs: None)

from scripts.flows.A import A004_run_fees_to_sheet as a004


class A004FeeRequeueTests(unittest.TestCase):
    def test_partial_failure_recovers_on_requeue_pass(self) -> None:
        attempts = {10.0: 0, 100.0: 0}

        def _fetch(price: float):
            attempts[price] += 1
            if price == 10.0 and attempts[price] == 1:
                return None, None, "There is an internal service failure"
            if price == 10.0:
                return 1.23, 15.0, None
            return 5.67, 12.0, None

        out = a004._estimate_prices_with_requeue(
            price_points=[10.0, 100.0],
            fetch_price_fn=_fetch,
            sleep_between_calls_sec=0.0,
            requeue_max_passes=2,
            requeue_pass_backoff_sec=0.0,
            sleep_fn=lambda _s: None,
        )

        self.assertEqual(out["fees"][10.0], 1.23)
        self.assertEqual(out["fees"][100.0], 5.67)
        self.assertEqual(out["errors"][10.0], "")
        self.assertEqual(out["errors"][100.0], "")
        self.assertEqual(out["attempt_counts"][10.0], 2)
        self.assertEqual(out["attempt_counts"][100.0], 1)
        self.assertEqual(out["requeue_passes_used"], 1)
        self.assertEqual(out["unresolved_points"], [])

    def test_persistent_failures_stay_unresolved_after_final_pass(self) -> None:
        def _fetch(price: float):
            if price == 10.0:
                return None, None, "There is an internal service failure"
            return 5.67, 12.0, None

        out = a004._estimate_prices_with_requeue(
            price_points=[10.0, 100.0],
            fetch_price_fn=_fetch,
            sleep_between_calls_sec=0.0,
            requeue_max_passes=2,
            requeue_pass_backoff_sec=0.0,
            sleep_fn=lambda _s: None,
        )

        self.assertIsNone(out["fees"][10.0])
        self.assertEqual(out["fees"][100.0], 5.67)
        self.assertEqual(out["attempt_counts"][10.0], 3)
        self.assertEqual(out["attempt_counts"][100.0], 1)
        self.assertEqual(out["requeue_passes_used"], 2)
        self.assertEqual(out["unresolved_points"], [10.0])
        self.assertTrue(out["errors"][10.0])

    def test_successful_price_values_are_not_retried_or_overwritten(self) -> None:
        attempts = {10.0: 0, 100.0: 0}
        observed_values_100 = []

        def _fetch(price: float):
            attempts[price] += 1
            if price == 100.0:
                observed_values_100.append(attempts[price])
                if attempts[price] > 1:
                    return None, None, "should_not_retry_success"
                return 9.99, 13.0, None
            return None, None, "temporary_fail"

        out = a004._estimate_prices_with_requeue(
            price_points=[10.0, 100.0],
            fetch_price_fn=_fetch,
            sleep_between_calls_sec=0.0,
            requeue_max_passes=2,
            requeue_pass_backoff_sec=0.0,
            sleep_fn=lambda _s: None,
        )

        self.assertEqual(out["attempt_counts"][100.0], 1)
        self.assertEqual(out["fees"][100.0], 9.99)
        self.assertEqual(observed_values_100, [1])
        self.assertEqual(out["unresolved_points"], [10.0])


def test_write_output_frame_sql_primary_exports_csv_and_sql(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    out_csv = tmp_path / "fees_latest.csv"
    df = pd.DataFrame(
        [
            {
                "seller_sku": "SKU-1",
                "fba_fee_10": "1.23",
                "fba_fee_100": "5.67",
                "error_10": "",
                "error_100": "",
            }
        ]
    )

    result = a004._write_output_frame(df, out_csv, a004.SQL_TABLE_FEES_LATEST)

    assert result["mode"] == "sql_primary_csv_export"
    assert result["csv_rows"] == 1
    assert result["sql_rows"] == 1
    assert len(pd.read_csv(out_csv, dtype=str)) == 1
    conn = sqlite3.connect(tmp_path / "sellerone.sqlite3")
    try:
        count = conn.execute(f"select count(*) from {a004.SQL_TABLE_FEES_LATEST}").fetchone()[0]
    finally:
        conn.close()
    assert count == 1


def test_write_output_frame_csv_mode_does_not_create_sql(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "sellerone.sqlite3"
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "csv")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(db_path))
    out_csv = tmp_path / "fees_failed.csv"
    df = pd.DataFrame(columns=["seller_sku", "error_10", "error_100"])

    result = a004._write_output_frame(df, out_csv, a004.SQL_TABLE_FEES_FAILED)

    assert result["mode"] == "csv"
    assert result["csv_rows"] == 0
    assert result["sql_rows"] == 0
    assert result["sql_table"] == ""
    assert out_csv.exists()
    assert not db_path.exists()


if __name__ == "__main__":
    unittest.main()
