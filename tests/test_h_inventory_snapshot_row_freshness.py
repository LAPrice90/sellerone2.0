from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.cycles import run_H_pricing_cycle as h_cycle


def test_ensure_inventory_snapshot_today_writes_row_freshness_columns(tmp_path: Path, monkeypatch) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    summaries_path = out_dir / "inventory_summaries.csv"
    pd.DataFrame(
        [
            {
                "seller_sku": "SKU-STALE",
                "asin": "A1",
                "available": "1",
                "total_quantity": "1",
                "inbound_working": "0",
                "inbound_shipped": "0",
                "inbound_receiving": "0",
                "unsellable": "0",
                "researching": "0",
                "reserved_transfers": "0",
                "reserved_processing": "0",
                "reserved_customer": "0",
                "last_updated_time": "2026-04-01T12:00:00Z",
            },
            {
                "seller_sku": "SKU-FRESH",
                "asin": "A2",
                "available": "5",
                "total_quantity": "5",
                "inbound_working": "0",
                "inbound_shipped": "0",
                "inbound_receiving": "0",
                "unsellable": "0",
                "researching": "0",
                "reserved_transfers": "0",
                "reserved_processing": "0",
                "reserved_customer": "0",
                "last_updated_time": "2026-04-22T11:00:00Z",
            },
        ]
    ).to_csv(summaries_path, index=False)

    monkeypatch.setattr(h_cycle, "OUT", out_dir)
    monkeypatch.setattr(h_cycle, "INVENTORY_SUMMARIES_PATH", summaries_path)
    monkeypatch.setattr(h_cycle, "_log", lambda *_args, **_kwargs: None)
    monkeypatch.delenv("H_STOCK_ROW_STALE_HOURS", raising=False)

    snapshot_path, source = h_cycle._ensure_inventory_snapshot_today("2026-04-22", "2026-04-22T12:00:00Z")

    assert source == "from_inventory_summaries"
    assert snapshot_path.exists()

    snapshot_df = pd.read_csv(snapshot_path, dtype=str).fillna("")
    assert {"row_last_updated_age_hours", "row_last_updated_status", "row_last_updated_is_stale"}.issubset(
        set(snapshot_df.columns)
    )

    by_sku = {str(r["sku"]).strip().upper(): r for _, r in snapshot_df.iterrows()}
    stale_row = by_sku["SKU-STALE"]
    fresh_row = by_sku["SKU-FRESH"]

    assert stale_row["row_last_updated_status"] == "STALE"
    assert stale_row["row_last_updated_is_stale"] == "1"
    assert float(stale_row["row_last_updated_age_hours"]) >= 24.0

    assert fresh_row["row_last_updated_status"] == "FRESH"
    assert fresh_row["row_last_updated_is_stale"] == "0"
    assert float(fresh_row["row_last_updated_age_hours"]) < 24.0
