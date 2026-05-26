from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import scripts.one_off.BEF007_build_sellerboard_window_alignment_audit as bef007


def _write_csv(path: Path, rows: list[dict[str, object]], *, sep: str = ",") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, sep=sep)


def _summary_metric(summary_df: pd.DataFrame, name: str) -> str:
    rows = summary_df.loc[summary_df["metric"] == name]
    if rows.empty:
        return ""
    return str(rows.iloc[0]["value"])


def test_bef007_builds_fixed_window_alignment_and_focus_order_proof(tmp_path: Path, monkeypatch) -> None:
    ref_dir = tmp_path / "reference"
    out_dir = tmp_path / "out"
    analysis_dir = out_dir / "analysis_reports"

    order_items_path = ref_dir / "order_items.csv"
    products_path = ref_dir / "products.csv"
    level2_path = out_dir / "financial_events_level2.csv"
    level3_path = out_dir / "financial_events_level3_official.csv"
    order_master_path = out_dir / "order_master.csv"
    order_ledger_path = out_dir / "order_ledger_fx.csv"
    daily_truth_path = out_dir / "sku_daily_sales_truth_latest.csv"
    actuals_path = analysis_dir / "f_sales_history_learning_actuals_latest.csv"
    vetting_summary_path = analysis_dir / "f_stocked_sku_vetting_summary_latest.csv"

    _write_csv(
        order_items_path,
        [
            {
                "Order number": "111-0000001-0000001 / Shipped",
                "Order date": "23.03.2026",
                "ASIN": "B07L6H9GZ2",
                "SKU": "SKU-FOCUS",
                "Units": "2",
                "Sales": "20.00",
            },
            {
                "Order number": "111-0000002-0000002 / Shipped",
                "Order date": "24.03.2026",
                "ASIN": "B07L6H9GZ2",
                "SKU": "SKU-FOCUS",
                "Units": "3",
                "Sales": "30.00",
            },
            {
                "Order number": "111-0000003-0000003 / Shipped",
                "Order date": "25.03.2026",
                "ASIN": "B000OTHER01",
                "SKU": "SKU-OTHER",
                "Units": "1",
                "Sales": "11.00",
            },
        ],
        sep=";",
    )
    _write_csv(
        products_path,
        [
            {"ASIN": "B07L6H9GZ2", "SKU": "SKU-FOCUS", "Units": "5", "Sales": "50.00"},
            {"ASIN": "B000OTHER01", "SKU": "SKU-OTHER", "Units": "1", "Sales": "11.00"},
        ],
        sep=";",
    )

    _write_csv(
        level2_path,
        [
            {
                "Date": "2026-03-23T00:00:00Z",
                "Order ID": "111-0000001-0000001",
                "SKU": "SKU-FOCUS",
                "Quantity Ordered": "2",
                "Price_ExVAT": "20.00",
                "Shipping_ExVAT": "0",
                "Gift_ExVAT": "0",
                "Promotion_ExVAT": "0",
            },
            {
                "Date": "2026-03-24T00:00:00Z",
                "Order ID": "111-0000002-0000002",
                "SKU": "SKU-FOCUS",
                "Quantity Ordered": "3",
                "Price_ExVAT": "30.00",
                "Shipping_ExVAT": "0",
                "Gift_ExVAT": "0",
                "Promotion_ExVAT": "0",
            },
            {
                "Date": "2026-03-25T00:00:00Z",
                "Order ID": "111-0000003-0000003",
                "SKU": "SKU-OTHER",
                "Quantity Ordered": "1",
                "Price_ExVAT": "11.00",
                "Shipping_ExVAT": "0",
                "Gift_ExVAT": "0",
                "Promotion_ExVAT": "0",
            },
        ],
    )
    _write_csv(
        level3_path,
        [
            {
                "Date": "2026-03-23T00:00:00Z",
                "Order ID": "111-0000001-0000001",
                "SKU": "SKU-FOCUS",
                "Quantity Ordered": "2",
            },
            {
                "Date": "2026-03-24T00:00:00Z",
                "Order ID": "111-0000002-0000002",
                "SKU": "SKU-FOCUS",
                "Quantity Ordered": "3",
            },
        ],
    )
    _write_csv(
        order_master_path,
        [
            {
                "Date": "2026-03-23T00:00:00Z",
                "Order ID": "111-0000001-0000001",
                "SKU": "SKU-FOCUS",
                "Quantity Ordered": "2",
                "Price_ExVAT": "20.00",
                "Shipping_ExVAT": "0",
                "Gift_ExVAT": "0",
                "Promotion_ExVAT": "0",
            },
            {
                "Date": "2026-03-25T00:00:00Z",
                "Order ID": "111-0000003-0000003",
                "SKU": "SKU-OTHER",
                "Quantity Ordered": "1",
                "Price_ExVAT": "11.00",
                "Shipping_ExVAT": "0",
                "Gift_ExVAT": "0",
                "Promotion_ExVAT": "0",
            },
        ],
    )
    _write_csv(
        order_ledger_path,
        [
            {
                "date": "2026-03-23T00:00:00Z",
                "Order ID": "111-0000001-0000001",
                "SKU": "SKU-FOCUS",
                "Quantity Ordered": "2",
                "Price_ExVAT_GBP": "20.00",
                "Shipping_ExVAT_GBP": "0",
                "Gift_ExVAT_GBP": "0",
                "Promotion_ExVAT_GBP": "0",
            },
            {
                "date": "2026-03-24T00:00:00Z",
                "Order ID": "111-0000002-0000002",
                "SKU": "SKU-FOCUS",
                "Quantity Ordered": "3",
                "Price_ExVAT_GBP": "30.00",
                "Shipping_ExVAT_GBP": "0",
                "Gift_ExVAT_GBP": "0",
                "Promotion_ExVAT_GBP": "0",
            },
        ],
    )
    _write_csv(
        daily_truth_path,
        [
            {
                "sku": "SKU-FOCUS",
                "date": "2026-03-23",
                "units": "5",
                "revenue_gbp": "50.00",
            },
            {
                "sku": "SKU-OTHER",
                "date": "2026-03-25",
                "units": "1",
                "revenue_gbp": "11.00",
            },
        ],
    )
    _write_csv(
        actuals_path,
        [
            {
                "asin": "B07L6H9GZ2",
                "actual_units_30d": "5",
                "actual_profit_30d_gbp": "7.50",
                "actuals_basis": "operational_baseline",
                "actuals_source_state_30d": "finalized",
                "actuals_observed_utc": "2026-04-22T10:00:00Z",
            }
        ],
    )
    _write_csv(
        vetting_summary_path,
        [
            {"metric": "current_test_buy_rows", "value": "2"},
            {"metric": "current_watch_rows", "value": "1"},
            {"metric": "current_reject_rows", "value": "9"},
        ],
    )

    monkeypatch.setattr(bef007, "LEVEL2_PATH", level2_path)
    monkeypatch.setattr(bef007, "LEVEL3_PATH", level3_path)
    monkeypatch.setattr(bef007, "ORDER_MASTER_PATH", order_master_path)
    monkeypatch.setattr(bef007, "ORDER_LEDGER_PATH", order_ledger_path)
    monkeypatch.setattr(bef007, "DAILY_TRUTH_PATH", daily_truth_path)
    monkeypatch.setattr(bef007, "ACTUALS_PATH", actuals_path)
    monkeypatch.setattr(bef007, "VETTING_SUMMARY_LATEST_PATH", vetting_summary_path)

    result = bef007.build_sellerboard_window_alignment_audit(
        order_items_path=order_items_path,
        products_path=products_path,
        output_dir=analysis_dir,
        window_start="2026-03-23",
        window_end="2026-04-21",
        focus_asin="B07L6H9GZ2",
        observed_utc="2026-04-22T10:15:00Z",
    )

    assert len(result.sku_audit_df.index) == 2
    focus_row = result.sku_audit_df.loc[result.sku_audit_df["asin"] == "B07L6H9GZ2"].iloc[0]
    assert float(focus_row["sellerboard_order_item_units"]) == 5.0
    assert float(focus_row["level2_units"]) == 5.0
    assert float(focus_row["order_master_units"]) == 2.0
    assert float(focus_row["daily_truth_units"]) == 5.0
    assert focus_row["discrepancy_class"] == "recovered_from_level2_gap"

    assert len(result.order_proof_df.index) == 2
    assert bool(result.order_proof_df["has_level2"].all())
    assert bool(result.order_proof_df["has_level3"].all())
    assert bool(result.order_proof_df["has_order_ledger"].all())
    assert not bool(result.order_proof_df["has_order_master"].all())

    assert _summary_metric(result.summary_df, "sellerboard_units_total") == "6.0"
    assert _summary_metric(result.summary_df, "daily_truth_units_total") == "6.0"
    assert _summary_metric(result.summary_df, "focus_sellerboard_units") == "5.0"
    assert _summary_metric(result.summary_df, "focus_daily_truth_units") == "5.0"
    assert _summary_metric(result.summary_df, "class::recovered_from_level2_gap") == "1"
    assert _summary_metric(result.summary_df, "vetting::current_test_buy_rows") == "2"
