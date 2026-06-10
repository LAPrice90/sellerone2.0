from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.A import A001_run_listings_to_sheet as a001


def test_a001_local_refresh_writes_csv_without_google_sheets(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("A001_WRITE_LEGACY_SHEETS", raising=False)
    monkeypatch.setattr(a001, "MODE", "sheet")
    monkeypatch.setattr(a001, "load_dotenv_if_missing", lambda: None)
    monkeypatch.setattr(a001, "list_marketplace_participations", lambda: [])

    df = pd.DataFrame(
        [
            {
                "item-name": "Demo item",
                "listing-id": "LISTING1",
                "seller-sku": "SKU1",
                "price": "10.00",
                "open-date": "2026-05-26",
                "item-condition": "New",
                "product-id": "ASIN1",
                "product-id-type": "1",
                "fulfillment-channel": "AMAZON_EU",
            }
        ]
    )

    def fake_run_live(**_kwargs):
        return {
            "data": df,
            "row_count": len(df.index),
            "columns": list(df.columns),
            "attempts_used": "1",
        }

    def fail_if_sheets_opened():
        raise AssertionError("A001 local refresh must not open Google Sheets")

    monkeypatch.setattr(a001, "run_live", fake_run_live)
    monkeypatch.setattr(a001, "get_gspread_client", fail_if_sheets_opened)

    a001.main()

    latest = tmp_path / "out" / "merchant_listings_latest.csv"
    legacy = tmp_path / "out" / "listings_data_latest.csv"
    assert latest.exists()
    assert legacy.exists()
    result = pd.read_csv(latest, dtype=str).fillna("")
    assert len(result.index) == 1
    assert result.loc[0, "seller-sku"] == "SKU1"
