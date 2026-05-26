from __future__ import annotations

import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.suppliers.we_stock_lots import convert_supplier


def test_we_stock_lots_converter_converts_eur_prices_to_gbp(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("WE_STOCK_LOTS_EUR_GBP_RATE", "0.8657")
    source = tmp_path / "we_stock_lots.csv"
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["A", "Description", "C", "EAN", "E", "Pieces MOQ", "G", "Our Price"])
        writer.writerow(["", "Puzzle Box", "", "4005555000001", "", "12", "", "€10.00"])
        writer.writerow(["", "Missing Barcode", "", "", "", "24", "", "€2.00"])
        writer.writerow(["", "Bad Price", "", "4005555000003", "", "6", "", "N/A"])

    valid, holds = convert_supplier(
        source,
        supplier_id="we_stock_lots",
        supplier_name="We Stock Lots",
        source_url="https://example.test/we-stock-lots.csv",
        source_seen_at_utc="2026-04-30T16:30:00Z",
    )

    assert len(valid.index) == 1
    assert len(holds.index) == 2
    row = valid.iloc[0]
    assert row["supplier_sku"] == "MOQ - 12"
    assert row["supplier_title"] == "We Stock Lots - Puzzle Box"
    assert row["barcode"] == "4005555000001"
    assert row["unit_cost"] == "8.66"
    assert row["currency"] == "GBP"
    assert row["vat_rate"] == "20"
    assert "source_price_currency=EUR" in row["notes"]
    assert "eur_gbp_rate=0.86570000" in row["notes"]
    assert set(holds["hold_reason_codes"]) == {"missing_barcode", "missing_or_invalid_cost"}


def test_we_stock_lots_converter_can_use_positional_columns(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("WE_STOCK_LOTS_EUR_GBP_RATE", "0.86643")
    source = tmp_path / "we_stock_lots_no_friendly_headers.csv"
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["col_a", "col_b", "col_c", "col_d", "col_e", "col_f", "col_g", "col_h"])
        writer.writerow(["", "Fallback Description", "", "4005555000002", "", "48", "", "20"])

    valid, holds = convert_supplier(
        source,
        supplier_id="we_stock_lots",
        supplier_name="We Stock Lots",
        source_url="",
        source_seen_at_utc="2026-04-30T16:31:00Z",
    )

    assert len(valid.index) == 1
    assert len(holds.index) == 0
    row = valid.iloc[0]
    assert row["supplier_sku"] == "MOQ - 48"
    assert row["supplier_title"] == "We Stock Lots - Fallback Description"
    assert row["unit_cost"] == "17.33"
