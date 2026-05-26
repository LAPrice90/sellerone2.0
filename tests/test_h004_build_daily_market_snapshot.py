from __future__ import annotations

import sqlite3

import pandas as pd

from scripts.flows.H import H004_build_daily_market_snapshot as h004


def test_h004_sql_primary_writes_market_snapshot_and_history(monkeypatch, tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    sqlite_path = tmp_path / "pilot.sqlite3"
    asof = "2026-04-28"

    pd.DataFrame(
        [
            {
                "asof_date": asof,
                "marketplace": "UK",
                "sku": "SKU-1",
                "asin": "ASIN-1",
                "our_price": "12.00",
                "buy_box_price": "10.00",
                "buy_box_channel": "FBA",
                "lowest_fba_price": "10.00",
                "lowest_fbm_price": "11.00",
                "offer_count_fba": "1",
                "offer_count_fbm": "1",
            }
        ]
    ).to_csv(out_dir / f"listing_offer_snapshot_{asof}.csv", index=False)
    pd.DataFrame(
        [
            {
                "asof_date": asof,
                "marketplace": "UK",
                "sku": "SKU-1",
                "asin": "ASIN-1",
                "seller_id": "SELLER-1",
                "offer_price_gbp": "10.00",
                "fulfillment_channel": "FBA",
                "min_delivery_days": "2",
                "is_prime": "1",
            }
        ]
    ).to_csv(out_dir / f"listing_offer_seller_snapshot_{asof}.csv", index=False)
    pd.DataFrame(
        [
            {
                "sku": "SKU-1",
                "break_even_price_gbp": "6.00",
                "current_token_cost_gbp": "4.00",
            }
        ]
    ).to_csv(out_dir / "sku_performance_summary.csv", index=False)

    monkeypatch.setattr(h004, "OUT", out_dir)
    monkeypatch.setattr(h004, "PERF_PATH", out_dir / "sku_performance_summary.csv")
    monkeypatch.setattr(h004, "LISTING_HISTORY_PATH", out_dir / "listing_offer_history.csv")
    monkeypatch.setattr(h004, "HISTORY_OUTPUT_PATH", out_dir / "hos_daily_market_history.csv")
    monkeypatch.setenv("H_SNAPSHOT_DATE", asof)
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(sqlite_path))

    h004.main()

    snapshot = pd.read_csv(out_dir / f"hos_daily_market_snapshot_{asof}.csv", dtype=str).fillna("")
    latest = pd.read_csv(out_dir / "hos_daily_market_snapshot_latest.csv", dtype=str).fillna("")
    history = pd.read_csv(out_dir / "hos_daily_market_history.csv", dtype=str).fillna("")
    assert len(snapshot) == 1
    assert len(latest) == 1
    assert len(history) == 1
    assert snapshot.loc[0, "sku"] == "SKU-1"

    connection = sqlite3.connect(sqlite_path)
    try:
        snapshot_rows = connection.execute(
            "SELECT sku, asin FROM h_hos_daily_market_snapshot"
        ).fetchall()
        history_rows = connection.execute(
            "SELECT sku, asin FROM h_hos_daily_market_history"
        ).fetchall()
    finally:
        connection.close()

    assert snapshot_rows == [("SKU-1", "ASIN-1")]
    assert history_rows == [("SKU-1", "ASIN-1")]
