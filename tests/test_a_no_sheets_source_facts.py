from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.A import A002_run_catalog_items_to_sheet as a002
from scripts.flows.A import A004_run_fees_to_sheet as a004


def test_a002_local_refresh_writes_catalog_without_google_sheets(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("A002_WRITE_LEGACY_SHEETS", raising=False)
    monkeypatch.setattr(sys, "argv", ["A002_run_catalog_items_to_sheet.py"])
    monkeypatch.setattr(a002, "DEBUG_ATTRS", False)
    monkeypatch.setattr(a002, "load_env", lambda: None)
    monkeypatch.setattr(a002, "get_lwa_access_token", lambda: "token")
    monkeypatch.setattr(a002, "load_asins", lambda _path, _limit: ["ASIN1"])
    monkeypatch.setattr(a002, "extend_asins_from_inventory", lambda asins, _limit, _path: asins)
    monkeypatch.setattr(a002.time, "sleep", lambda _seconds: None)

    def fake_fetch_catalog_item(asin: str, _marketplace_id: str, _token: str) -> dict[str, object]:
        return {
            "asin": asin,
            "status": 200,
            "data": {
                "summaries": [{"itemName": "Demo item", "brandName": "Demo Brand"}],
                "images": [],
                "productTypes": [{"productType": "TOOLS"}],
                "identifiers": [],
                "relationships": [],
                "attributes": {},
            },
        }

    def fail_if_sheets_opened():
        raise AssertionError("A002 local refresh must not open Google Sheets")

    monkeypatch.setattr(a002, "fetch_catalog_item", fake_fetch_catalog_item)
    monkeypatch.setattr(a002, "get_gspread_client", fail_if_sheets_opened)

    a002.main()

    out_path = tmp_path / "out" / "catalog_items_flat.csv"
    assert out_path.exists()
    out_df = pd.read_csv(out_path, dtype=str).fillna("")
    assert len(out_df.index) == 1
    assert out_df.loc[0, "asin"] == "ASIN1"


def test_a004_local_refresh_writes_fees_without_google_sheets(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("A004_WRITE_LEGACY_SHEETS", raising=False)
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "csv")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "missing.sqlite3"))
    monkeypatch.setattr(a004, "LIMIT", 1)
    monkeypatch.setattr(a004, "SLEEP_SEC", 0.0)
    monkeypatch.setattr(a004, "FEES_REQUEUE_PASS_BACKOFF_SEC", 0.0)
    monkeypatch.setattr(a004, "load_env", lambda: None)
    monkeypatch.setattr(a004, "get_lwa_access_token", lambda: "token")
    monkeypatch.setattr(a004.gspread, "service_account", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("A004 local refresh must not open Google Sheets")))

    product_view = tmp_path / "out" / "systems" / "O" / "live" / "product_db_operator_view.csv"
    product_view.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "sale_status": "active",
                "stock_available": "4",
                "stock_total": "4",
                "last_purchase_price": "2.50",
                "vat_rate": "20",
            }
        ]
    ).to_csv(product_view, index=False)

    def fake_fee_api(_token: str, _marketplace_id: str, _id_value: str, price: float, **_kwargs):
        return price / 10.0, 15.0, None

    monkeypatch.setattr(a004, "call_fee_api", fake_fee_api)

    a004.main()

    out_path = tmp_path / "out" / "fees_latest.csv"
    assert out_path.exists()
    out_df = pd.read_csv(out_path, dtype=str).fillna("")
    assert len(out_df.index) == 1
    assert out_df.loc[0, "seller_sku"] == "SKU1"
    assert out_df.loc[0, "fba_fee_10"] in {"1", "1.0"}


def test_a004_local_refresh_adds_each_missing_order_sku(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("A004_WRITE_LEGACY_SHEETS", raising=False)
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "csv")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "missing.sqlite3"))
    monkeypatch.setattr(a004, "LIMIT", 0)
    monkeypatch.setattr(a004, "SLEEP_SEC", 0.0)
    monkeypatch.setattr(a004, "FEES_REQUEUE_PASS_BACKOFF_SEC", 0.0)
    monkeypatch.setattr(a004, "load_env", lambda: None)
    monkeypatch.setattr(a004, "get_lwa_access_token", lambda: "token")
    monkeypatch.setattr(a004.gspread, "service_account", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("A004 local refresh must not open Google Sheets")))

    product_view = tmp_path / "out" / "systems" / "O" / "live" / "product_db_operator_view.csv"
    product_view.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "seller_sku": "SKU0",
                "asin": "ASIN0",
                "title": "Existing item",
                "sale_status": "active",
                "stock_available": "1",
                "stock_total": "1",
                "last_purchase_price": "2.50",
                "vat_rate": "20",
            }
        ]
    ).to_csv(product_view, index=False)

    order_items = tmp_path / "out" / "order_items_all.csv"
    pd.DataFrame(
        [
            {"seller_sku": "SKU1", "asin": "ASIN1", "title": "Order item one"},
            {"seller_sku": "SKU2", "asin": "ASIN2", "title": "Order item two"},
        ]
    ).to_csv(order_items, index=False)

    def fake_fee_api(_token: str, _marketplace_id: str, _id_value: str, price: float, **_kwargs):
        return price / 10.0, 15.0, None

    monkeypatch.setattr(a004, "call_fee_api", fake_fee_api)

    a004.main()

    out_df = pd.read_csv(tmp_path / "out" / "fees_latest.csv", dtype=str).fillna("")
    assert set(out_df["seller_sku"]) == {"SKU0", "SKU1", "SKU2"}
