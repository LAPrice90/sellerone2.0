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

from scripts.one_off.F005_build_sales_history_validation_audit import build_sales_history_validation_audit


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def test_f005_builds_monthly_history_rows_and_flags_predicted_months(tmp_path: Path) -> None:
    scrape_path = tmp_path / "scrape.csv"
    input_path = tmp_path / "input.csv"
    summary_path = tmp_path / "summary.csv"
    output_dir = tmp_path / "out"

    _write_csv(
        scrape_path,
        [
            {
                "observed_utc": "2026-04-14T10:00:00Z",
                "supplier_sku": "SKU-1",
                "asin": "B00TEST001",
                "bbp_sales_chart_source": "estSalesMonthlyChart:chartjs",
                "bbp_sales_chart_series": "01/26=5;02/26=7;03/26=10;04/26=42;05/26=40;06/26=39",
                "bbp_sales_chart_month_labels": "01/26|02/26|03/26|04/26|05/26|06/26",
                "bbp_sales_chart_month_units": "5|7|10|42|40|39",
                "bbp_sales_last_completed_month_label": "2026-03",
                "bbp_sales_last_completed_month_units": "10",
                "bbp_sales_current_month_label": "2026-04",
                "bbp_sales_current_month_units": "42",
                "bbp_sales_future_month_count_ignored": "2",
                "break_even": "24.10",
                "min_sell_price": "28.40",
                "avg_30_day_price": "28.98",
                "estimated_monthly_profit": "23.20",
            }
        ],
    )
    _write_csv(
        input_path,
        [
            {
                "observed_utc": "2026-04-14T10:01:00Z",
                "seller_sku": "SKU-1",
                "asin": "B00TEST001",
                "input_status": "ready",
                "demand_basis_source": "bbp_last_completed_month",
                "demand_basis_units_monthly": "10",
                "demand_basis_month_label": "2026-03",
                "seasonality_state": "possible_seasonal",
                "seasonality_reason_codes": "seasonal_shape_present_without_full_year",
                "stability_state": "stable",
                "stability_reason_codes": "within_stability_band",
                "recent_vs_baseline_state": "stable",
                "recent_vs_baseline_reason_codes": "baseline_threshold_stable",
                "completed_months_count": "7",
                "price_qualified_units_monthly": "6",
                "price_qualified_profit_monthly_gbp": "24",
                "price_qualification_reason_codes": "amazon_heavy_30d",
                "qualification_market_gate_state": "market_open",
                "qualification_market_gate_factor": "1",
                "qualification_amazon_pressure_factor": "0.2",
                "qualification_buy_box_coverage_factor": "1",
                "qualification_maturity_factor": "1",
                "qualification_final_factor": "0.2",
                "qualification_zero_or_block_reason": "",
            }
        ],
    )
    _write_csv(
        summary_path,
        [
            {
                "observed_utc": "2026-04-14T10:02:00Z",
                "seller_sku": "SKU-1",
                "asin": "B00TEST001",
                "summary_status": "ready",
                "expected_units_source": "input_qualified",
                "expected_profit_source": "input_qualified",
                "decision_state": "pass",
                "decision_reason_codes": "meets_profit_floor",
                "decision_confidence": "medium",
                "decision_confidence_reason_codes": "confidence_medium_gate_met",
                "summary_reason_codes": "summary_ready|seasonality_state_possible_seasonal",
                "seasonality_state": "possible_seasonal",
                "seasonality_reason_codes": "seasonal_shape_present_without_full_year",
                "stability_state": "stable",
                "stability_reason_codes": "within_stability_band",
                "recent_vs_baseline_state": "stable",
                "recent_vs_baseline_reason_codes": "baseline_threshold_stable",
                "completed_months_count": "7",
            }
        ],
    )

    result = build_sales_history_validation_audit(
        scrape_path=scrape_path,
        input_path=input_path,
        summary_path=summary_path,
        output_dir=output_dir,
        observed_utc="2026-04-14T10:05:00Z",
    )

    assert len(result.validation_df) == 6
    assert result.report_path.exists()
    assert result.latest_path.exists()

    latest_df = pd.read_csv(result.latest_path, dtype=str).fillna("")
    assert len(latest_df) == 6
    assert latest_df.iloc[0]["amazon_link"] == "https://www.amazon.co.uk/dp/B00TEST001"

    march_row = latest_df[latest_df["month_label_iso"] == "2026-03"].iloc[0]
    assert march_row["month_class"] == "last_completed"
    assert march_row["trusted_for_demand_basis"] == "1"

    may_row = latest_df[latest_df["month_label_iso"] == "2026-05"].iloc[0]
    assert may_row["month_class"] == "future_predicted"
    assert may_row["predicted_or_future_flag"] == "1"
    assert may_row["trusted_for_demand_basis"] == "0"
    assert may_row["raw_observed_monthly_units"] == "10"
    assert may_row["price_qualified_monthly_units"] == "6"
    assert may_row["qualified_units_delta"] == "4"
    assert may_row["summary_status"] == "ready"
    assert may_row["expected_units_source"] == "input_qualified"
    assert may_row["decision_confidence"] == "medium"
    assert may_row["decision_confidence_reason_codes"] == "confidence_medium_gate_met"
    assert may_row["seasonality_state"] == "possible_seasonal"
    assert may_row["summary_seasonality_state"] == "possible_seasonal"
    assert may_row["summary_reason_codes"] != ""


def test_f005_uses_latest_scrape_row_per_listing_and_fallback_last_completed_row(tmp_path: Path) -> None:
    scrape_path = tmp_path / "scrape.csv"
    input_path = tmp_path / "input.csv"
    summary_path = tmp_path / "summary.csv"
    output_dir = tmp_path / "out"

    _write_csv(
        scrape_path,
        [
            {
                "observed_utc": "2026-04-14T09:00:00Z",
                "supplier_sku": "SKU-2",
                "asin": "B00TEST002",
                "bbp_sales_chart_month_labels": "01/26|02/26",
                "bbp_sales_chart_month_units": "1|2",
                "bbp_sales_last_completed_month_label": "2026-02",
                "bbp_sales_last_completed_month_units": "2",
                "bbp_sales_current_month_label": "2026-03",
                "bbp_sales_future_month_count_ignored": "0",
            },
            {
                "observed_utc": "2026-04-14T10:00:00Z",
                "supplier_sku": "SKU-2",
                "asin": "B00TEST002",
                "bbp_sales_chart_month_labels": "",
                "bbp_sales_chart_month_units": "",
                "bbp_sales_last_completed_month_label": "2026-03",
                "bbp_sales_last_completed_month_units": "9",
                "bbp_sales_current_month_label": "2026-04",
                "bbp_sales_future_month_count_ignored": "0",
            },
        ],
    )
    _write_csv(input_path, [])

    result = build_sales_history_validation_audit(
        scrape_path=scrape_path,
        input_path=input_path,
        summary_path=summary_path,
        output_dir=output_dir,
        observed_utc="2026-04-14T10:06:00Z",
    )

    assert len(result.validation_df) == 1
    row = result.validation_df.iloc[0]
    assert row["month_label_iso"] == "2026-03"
    assert row["month_class"] == "last_completed"
    assert row["month_units"] == "9"
