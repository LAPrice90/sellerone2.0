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

from scripts.one_off.F004_build_bbp_sales_sample_audit import build_bbp_sales_sample_audit


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def test_f004_builds_sample_audit_and_flags_mismatch_rows(tmp_path: Path) -> None:
    sample_path = tmp_path / "sample.csv"
    scrape_path = tmp_path / "scrape.csv"
    input_path = tmp_path / "input.csv"
    output_dir = tmp_path / "out"

    _write_csv(
        sample_path,
        [
            {"calibration_rank": "1", "calibration_bucket": "manual_review_or_unclear", "seller_sku": "SKU-GOOD", "asin": "B000GOOD01"},
            {"calibration_rank": "2", "calibration_bucket": "demand_or_profit_inflation_risk", "seller_sku": "SKU-BAD", "asin": "B000BAD001"},
        ],
    )
    _write_csv(
        scrape_path,
        [
            {
                "observed_utc": "2026-04-13T12:00:00Z",
                "supplier_sku": "SKU-GOOD",
                "asin": "B000GOOD01",
                "bbp_sales_chart_source": "estSalesMonthlyChart:chartjs",
                "bbp_sales_chart_series": "01/26=10;02/26=10;03/26=10;04/26=70",
                "bbp_sales_chart_month_labels": "01/26|02/26|03/26|04/26",
                "bbp_sales_chart_month_units": "10|10|10|70",
                "bbp_sales_last_completed_month_label": "2026-03",
                "bbp_sales_last_completed_month_units": "10",
                "bbp_sales_current_month_label": "2026-04",
                "bbp_sales_current_month_units": "70",
                "bbp_sales_future_month_count_ignored": "2",
                "bbp_monthly_units_chosen": "50",
                "bbp_monthly_sales_current": "10",
                "bbp_monthly_sales_recent_avg": "10",
            },
            {
                "observed_utc": "2026-04-13T12:00:00Z",
                "supplier_sku": "SKU-BAD",
                "asin": "B000BAD001",
                "bbp_sales_chart_source": "estSalesMonthlyChart:chartjs",
                "bbp_sales_chart_series": "01/26=10;02/26=10;03/26=10;04/26=79",
                "bbp_sales_chart_month_labels": "01/26|02/26|03/26|04/26",
                "bbp_sales_chart_month_units": "10|10|10|79",
                "bbp_sales_last_completed_month_label": "2026-03",
                "bbp_sales_last_completed_month_units": "10",
                "bbp_sales_current_month_label": "2026-04",
                "bbp_sales_current_month_units": "79",
                "bbp_sales_future_month_count_ignored": "2",
                "bbp_monthly_units_chosen": "50",
                "bbp_monthly_sales_current": "10",
                "bbp_monthly_sales_recent_avg": "10",
            },
        ],
    )
    _write_csv(
        input_path,
        [
            {
                "observed_utc": "2026-04-13T12:02:00Z",
                "seller_sku": "SKU-GOOD",
                "asin": "B000GOOD01",
                "demand_basis_source": "bbp_last_completed_month",
                "demand_basis_units_monthly": "10",
                "demand_basis_month_label": "2026-03",
                "bbp_sales_last_completed_month_units": "10",
                "bbp_sales_future_month_count_ignored": "2",
                "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
                "bbp_sales_replay_demand_basis_label": "2026-03",
                "bbp_sales_replay_demand_basis_units": "10",
            },
            {
                "observed_utc": "2026-04-13T12:02:00Z",
                "seller_sku": "SKU-BAD",
                "asin": "B000BAD001",
                "demand_basis_source": "bbp_units_chosen_fallback",
                "demand_basis_units_monthly": "50",
                "demand_basis_month_label": "",
                "bbp_sales_last_completed_month_units": "10",
                "bbp_sales_future_month_count_ignored": "2",
                "bbp_sales_replay_demand_basis_source": "bbp_current_month_fallback",
                "bbp_sales_replay_demand_basis_label": "2026-04",
                "bbp_sales_replay_demand_basis_units": "79",
            },
        ],
    )

    result = build_bbp_sales_sample_audit(
        sample_path=sample_path,
        scrape_path=scrape_path,
        input_path=input_path,
        output_dir=output_dir,
        observed_utc="2026-04-13T12:10:00Z",
    )

    assert len(result.audit_df) == 2
    assert result.latest_path.exists()
    assert result.report_path.exists()

    good_row = result.audit_df[result.audit_df["seller_sku"] == "SKU-GOOD"].iloc[0]
    assert good_row["mismatch_flag"] == "0"
    assert good_row["amazon_link"] == "https://www.amazon.co.uk/dp/B000GOOD01"

    bad_row = result.audit_df[result.audit_df["seller_sku"] == "SKU-BAD"].iloc[0]
    assert bad_row["mismatch_flag"] == "1"
    assert "demand_basis_not_last_completed_month" in bad_row["mismatch_reason_codes"]
    assert "demand_basis_units_mismatch_last_completed" in bad_row["mismatch_reason_codes"]
    assert "helper_chosen_leak" in bad_row["mismatch_reason_codes"]


def test_f004_marks_missing_input_rows_as_mismatch(tmp_path: Path) -> None:
    sample_path = tmp_path / "sample.csv"
    scrape_path = tmp_path / "scrape.csv"
    input_path = tmp_path / "input.csv"
    output_dir = tmp_path / "out"

    _write_csv(
        sample_path,
        [
            {"calibration_rank": "1", "calibration_bucket": "on_the_line", "seller_sku": "SKU-MISS", "asin": "B000MISS01"},
        ],
    )
    _write_csv(
        scrape_path,
        [
            {
                "observed_utc": "2026-04-13T12:00:00Z",
                "supplier_sku": "SKU-MISS",
                "asin": "B000MISS01",
                "bbp_sales_last_completed_month_units": "10",
            }
        ],
    )
    _write_csv(input_path, [])

    result = build_bbp_sales_sample_audit(
        sample_path=sample_path,
        scrape_path=scrape_path,
        input_path=input_path,
        output_dir=output_dir,
        observed_utc="2026-04-13T12:11:00Z",
    )

    assert len(result.audit_df) == 1
    row = result.audit_df.iloc[0]
    assert row["mismatch_flag"] == "1"
    assert "missing_input_view_row" in row["mismatch_reason_codes"]


def test_f004_accepts_zero_history_basis_as_non_mismatch(tmp_path: Path) -> None:
    sample_path = tmp_path / "sample.csv"
    scrape_path = tmp_path / "scrape.csv"
    input_path = tmp_path / "input.csv"
    output_dir = tmp_path / "out"

    _write_csv(
        sample_path,
        [
            {"calibration_rank": "1", "calibration_bucket": "manual_review_or_unclear", "seller_sku": "SKU-ZERO", "asin": "B000ZERO01"},
        ],
    )
    _write_csv(
        scrape_path,
        [
            {
                "observed_utc": "2026-04-13T12:00:00Z",
                "supplier_sku": "SKU-ZERO",
                "asin": "B000ZERO01",
                "bbp_sales_last_completed_month_units": "0",
                "bbp_sales_future_month_count_ignored": "0",
            }
        ],
    )
    _write_csv(
        input_path,
        [
            {
                "observed_utc": "2026-04-13T12:02:00Z",
                "seller_sku": "SKU-ZERO",
                "asin": "B000ZERO01",
                "demand_basis_source": "bbp_zero_history",
                "demand_basis_units_monthly": "0",
                "demand_basis_month_label": "zero_history",
                "bbp_sales_last_completed_month_units": "0",
                "bbp_sales_future_month_count_ignored": "0",
                "bbp_sales_replay_demand_basis_source": "bbp_zero_history",
                "bbp_sales_replay_demand_basis_label": "zero_history",
                "bbp_sales_replay_demand_basis_units": "0",
            }
        ],
    )

    result = build_bbp_sales_sample_audit(
        sample_path=sample_path,
        scrape_path=scrape_path,
        input_path=input_path,
        output_dir=output_dir,
        observed_utc="2026-04-13T12:11:00Z",
    )

    assert len(result.audit_df) == 1
    row = result.audit_df.iloc[0]
    assert row["mismatch_flag"] == "0"
    assert row["mismatch_reason_codes"] == ""
