from __future__ import annotations

import sys
import sqlite3
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.E import E006_build_sales_truth_reconciliation as e006


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def _patch_paths(monkeypatch, tmp_path: Path) -> Path:
    out = tmp_path / "out"
    monkeypatch.setattr(e006, "OUT", out)
    monkeypatch.setattr(e006, "ORDER_MASTER", out / "order_master.csv")
    monkeypatch.setattr(e006, "ORDER_LEDGER_FX", out / "order_ledger_fx.csv")
    monkeypatch.setattr(e006, "FINANCIAL_EVENTS_LEVEL2", out / "financial_events_level2.csv")
    monkeypatch.setattr(e006, "TOKEN_COGS", out / "token_cogs_ledger.csv")
    monkeypatch.setattr(e006, "FX_RATES", out / "fx_rates_daily.csv")
    monkeypatch.setattr(e006, "MARKETPLACE_PARTICIPATIONS", out / "marketplace_participations.csv")
    monkeypatch.setattr(e006, "ROI", out / "sku_roi_snapshot.csv")
    monkeypatch.setattr(e006, "OUT_B_TRUTH", out / "sales_truth_sku_30d_latest.csv")
    monkeypatch.setattr(e006, "OUT_RECON", out / "sales_truth_reconciliation_latest.csv")
    return out


def test_e006_builds_b_truth_and_reconciliation(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    _write_csv(
        out / "order_master.csv",
        [
            {"Date": "2026-04-30T12:00:00Z"},
            {"Date": "2026-04-20T12:00:00Z"},
        ],
        ["Date"],
    )
    _write_csv(
        out / "order_ledger_fx.csv",
        [
            {
                "date": "2026-04-30T12:00:00Z",
                "SKU": "SKU-A",
                "Quantity Ordered": "2",
                "Price_ExVAT_GBP": "20",
                "Shipping_ExVAT_GBP": "0",
                "Gift_ExVAT_GBP": "0",
                "Promotion_ExVAT_GBP": "0",
                "COGS_ExVAT": "-10",
                "FBA_Fee_ExVAT_GBP": "-4",
                "Commission_ExVAT_GBP": "-2",
                "Digital_Fee_ExVAT_GBP": "0",
            },
            {
                "date": "2026-04-30T13:00:00Z",
                "SKU": "SKU-B",
                "Quantity Ordered": "1",
                "Price_ExVAT_GBP": "5",
                "Shipping_ExVAT_GBP": "0",
                "Gift_ExVAT_GBP": "0",
                "Promotion_ExVAT_GBP": "0",
                "COGS_ExVAT": "-3",
                "FBA_Fee_ExVAT_GBP": "-1",
                "Commission_ExVAT_GBP": "0",
                "Digital_Fee_ExVAT_GBP": "0",
            },
            {
                "date": "2026-03-01T10:00:00Z",
                "SKU": "OLD-SKU",
                "Quantity Ordered": "1",
                "Price_ExVAT_GBP": "9",
                "Shipping_ExVAT_GBP": "0",
                "Gift_ExVAT_GBP": "0",
                "Promotion_ExVAT_GBP": "0",
                "COGS_ExVAT": "-4",
                "FBA_Fee_ExVAT_GBP": "-1",
                "Commission_ExVAT_GBP": "-1",
                "Digital_Fee_ExVAT_GBP": "0",
            },
        ],
        [
            "date",
            "SKU",
            "Quantity Ordered",
            "Price_ExVAT_GBP",
            "Shipping_ExVAT_GBP",
            "Gift_ExVAT_GBP",
            "Promotion_ExVAT_GBP",
            "COGS_ExVAT",
            "FBA_Fee_ExVAT_GBP",
            "Commission_ExVAT_GBP",
            "Digital_Fee_ExVAT_GBP",
        ],
    )
    _write_csv(
        out / "sku_roi_snapshot.csv",
        [
            {"sku": "SKU-A", "units_sold": "2", "revenue_exvat_gbp": "20", "profit_exvat_gbp": "4"},
            {"sku": "SKU-C", "units_sold": "1", "revenue_exvat_gbp": "7", "profit_exvat_gbp": "2"},
        ],
        ["sku", "units_sold", "revenue_exvat_gbp", "profit_exvat_gbp"],
    )
    _write_csv(out / "financial_events_level2.csv", [], ["Date", "Order ID", "SKU"])
    _write_csv(out / "token_cogs_ledger.csv", [], ["order_id", "seller_sku", "quantity", "currency", "cogs_exvat", "order_date"])
    _write_csv(out / "fx_rates_daily.csv", [], ["date", "currency", "rate_to_gbp"])
    _write_csv(out / "marketplace_participations.csv", [], ["marketplace_id", "country_code", "default_currency"])

    e006.main()

    b_truth = pd.read_csv(out / "sales_truth_sku_30d_latest.csv")
    recon = pd.read_csv(out / "sales_truth_reconciliation_latest.csv")
    assert set(b_truth["sku"]) == {"SKU-A", "SKU-B"}
    assert "OLD-SKU" not in set(b_truth["sku"])

    recon = recon.set_index("sku")
    assert recon.loc["SKU-A", "confidence_status"] == "match"
    assert recon.loc["SKU-B", "confidence_status"] == "mismatch"
    assert recon.loc["SKU-B", "root_cause_hint"] == "e_missing_sku"
    assert recon.loc["SKU-C", "confidence_status"] == "mismatch"
    assert recon.loc["SKU-C", "root_cause_hint"] == "b_missing_sku"


def test_e006_writes_empty_outputs_when_sources_missing(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    e006.main()
    assert (out / "sales_truth_sku_30d_latest.csv").exists()
    assert (out / "sales_truth_reconciliation_latest.csv").exists()
    assert pd.read_csv(out / "sales_truth_sku_30d_latest.csv").empty
    assert pd.read_csv(out / "sales_truth_reconciliation_latest.csv").empty


def test_e006_builds_truth_from_level2_when_ledger_is_missing(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    _write_csv(out / "order_master.csv", [], ["Date", "Order ID", "SKU"])
    _write_csv(out / "order_ledger_fx.csv", [], ["date", "SKU"])
    _write_csv(
        out / "financial_events_level2.csv",
        [
            {
                "Date": "2026-04-30T12:00:00Z",
                "Order ID": "ORDER-1",
                "marketplace_id": "A1F83G8C2ARO7P",
                "SKU": "SKU-L2",
                "Quantity Ordered": "1",
                "Price_ExVAT": "9",
                "Shipping_ExVAT": "0",
                "Gift_ExVAT": "0",
                "Promotion_ExVAT": "0",
                "FBA_Fee_ExVAT": "-2",
                "Commission_ExVAT": "-1",
                "Digital_Fee_ExVAT": "0",
                "FixedClosingFee_ExVAT": "0",
            }
        ],
        [
            "Date",
            "Order ID",
            "marketplace_id",
            "SKU",
            "Quantity Ordered",
            "Price_ExVAT",
            "Shipping_ExVAT",
            "Gift_ExVAT",
            "Promotion_ExVAT",
            "FBA_Fee_ExVAT",
            "Commission_ExVAT",
            "Digital_Fee_ExVAT",
            "FixedClosingFee_ExVAT",
        ],
    )
    _write_csv(
        out / "marketplace_participations.csv",
        [{"marketplace_id": "A1F83G8C2ARO7P", "country_code": "GB", "default_currency": "GBP"}],
        ["marketplace_id", "country_code", "default_currency"],
    )
    _write_csv(out / "token_cogs_ledger.csv", [], ["order_id", "seller_sku", "quantity", "currency", "cogs_exvat", "order_date"])
    _write_csv(out / "fx_rates_daily.csv", [], ["date", "currency", "rate_to_gbp"])
    _write_csv(
        out / "sku_roi_snapshot.csv",
        [{"sku": "SKU-L2", "units_sold": "1", "revenue_exvat_gbp": "9", "profit_exvat_gbp": "0"}],
        ["sku", "units_sold", "revenue_exvat_gbp", "profit_exvat_gbp"],
    )

    e006.main()

    b_truth = pd.read_csv(out / "sales_truth_sku_30d_latest.csv").set_index("sku")
    recon = pd.read_csv(out / "sales_truth_reconciliation_latest.csv").set_index("sku")
    assert b_truth.loc["SKU-L2", "units_b_source"] == 1
    assert b_truth.loc["SKU-L2", "revenue_b_source_gbp"] == 9
    assert recon.loc["SKU-L2", "confidence_status"] == "match"


def test_e006_sql_primary_writes_truth_tables_and_csv_exports(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    sqlite_path = tmp_path / "pilot.sqlite3"
    _write_csv(out / "order_master.csv", [{"Date": "2026-04-30T12:00:00Z"}], ["Date"])
    _write_csv(
        out / "order_ledger_fx.csv",
        [
            {
                "date": "2026-04-30T12:00:00Z",
                "SKU": "SKU-SQL",
                "Quantity Ordered": "2",
                "Price_ExVAT_GBP": "20",
                "Shipping_ExVAT_GBP": "0",
                "Gift_ExVAT_GBP": "0",
                "Promotion_ExVAT_GBP": "0",
                "COGS_ExVAT": "-10",
                "FBA_Fee_ExVAT_GBP": "-4",
                "Commission_ExVAT_GBP": "-2",
                "Digital_Fee_ExVAT_GBP": "0",
            }
        ],
        [
            "date",
            "SKU",
            "Quantity Ordered",
            "Price_ExVAT_GBP",
            "Shipping_ExVAT_GBP",
            "Gift_ExVAT_GBP",
            "Promotion_ExVAT_GBP",
            "COGS_ExVAT",
            "FBA_Fee_ExVAT_GBP",
            "Commission_ExVAT_GBP",
            "Digital_Fee_ExVAT_GBP",
        ],
    )
    _write_csv(
        out / "sku_roi_snapshot.csv",
        [{"sku": "SKU-SQL", "units_sold": "2", "revenue_exvat_gbp": "20", "profit_exvat_gbp": "4"}],
        ["sku", "units_sold", "revenue_exvat_gbp", "profit_exvat_gbp"],
    )
    _write_csv(out / "financial_events_level2.csv", [], ["Date", "Order ID", "SKU"])
    _write_csv(out / "token_cogs_ledger.csv", [], ["order_id", "seller_sku", "quantity", "currency", "cogs_exvat", "order_date"])
    _write_csv(out / "fx_rates_daily.csv", [], ["date", "currency", "rate_to_gbp"])
    _write_csv(out / "marketplace_participations.csv", [], ["marketplace_id", "country_code", "default_currency"])
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(sqlite_path))

    e006.main()

    assert pd.read_csv(out / "sales_truth_sku_30d_latest.csv", dtype=str).fillna("").loc[0, "sku"] == "SKU-SQL"
    assert pd.read_csv(out / "sales_truth_reconciliation_latest.csv", dtype=str).fillna("").loc[0, "confidence_status"] == "match"

    connection = sqlite3.connect(sqlite_path)
    try:
        b_truth_rows = connection.execute(
            "SELECT sku, units_b_source FROM e_sales_truth_sku_30d"
        ).fetchall()
        recon_rows = connection.execute(
            "SELECT sku, confidence_status FROM e_sales_truth_reconciliation"
        ).fetchall()
    finally:
        connection.close()

    assert b_truth_rows == [("SKU-SQL", "2")]
    assert recon_rows == [("SKU-SQL", "match")]
