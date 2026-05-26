from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.one_off.F023_build_demand_range_bbp_conflict_audit import (
    DEFAULT_BACKTEST_SUMMARY_PATH,
    DEFAULT_NEAR_MISS_PATH,
    DEFAULT_PASS_PATH,
    DEFAULT_REVIEW_EVENTS_PATH,
    DEFAULT_SCRAPE_EVIDENCE_PATH,
    VALID_DEMAND_CONFLICT_CODES,
    build_demand_range_bbp_conflict_audit,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _run_audit(
    tmp_path: Path,
    *,
    pass_rows: list[dict[str, str]],
    scrape_rows: list[dict[str, str]],
    near_miss_rows: list[dict[str, str]] | None = None,
    backtest_rows: list[dict[str, str]] | None = None,
    review_event_rows: list[dict[str, str]] | None = None,
):
    pass_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
    near_miss_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_near_miss_review_latest.csv"
    scrape_path = tmp_path / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv"
    backtest_path = tmp_path / "out" / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv"
    events_path = tmp_path / "out" / "systems" / "F" / "inbox" / "feeder_review_events.csv"
    output_path = tmp_path / "out" / "analysis_reports" / "f_demand_range_bbp_conflict_audit_latest.csv"

    _write_csv(pass_path, pass_rows)
    _write_csv(near_miss_path, near_miss_rows or [])
    _write_csv(scrape_path, scrape_rows)
    _write_csv(backtest_path, backtest_rows or [])
    _write_csv(events_path, review_event_rows or [])

    return build_demand_range_bbp_conflict_audit(
        pass_path=pass_path,
        near_miss_path=near_miss_path,
        scrape_evidence_path=scrape_path,
        backtest_summary_path=backtest_path,
        review_events_path=events_path,
        output_path=output_path,
    )


def _pass_row(asin: str, expected_units: str) -> dict[str, str]:
    return {
        "asin": asin,
        "candidate_id": f"cand-{asin}",
        "supplier_sku": f"sku-{asin}",
        "expected_units_next_30d": expected_units,
    }


def _scrape_row(
    asin: str,
    *,
    monthly_sold: str,
    bbp_units: str,
    uk_reviews: str = "10",
    variant_reviews: str = "100",
) -> dict[str, str]:
    return {
        "observed_utc": "2026-04-23T10:00:00Z",
        "candidate_id": f"cand-{asin}",
        "supplier_sku": f"sku-{asin}",
        "asin": asin,
        "monthly_sold": monthly_sold,
        "amazon_bought_floor": "",
        "bbp_sales_replay_demand_basis_units": bbp_units,
        "historical_uk_reviews": uk_reviews,
        "variant_reviews": variant_reviews,
    }


def _row_for_code(audit_df: pd.DataFrame, asin: str, code: str) -> dict[str, str]:
    rows = audit_df.loc[(audit_df["asin"] == asin) & (audit_df["demand_conflict_code"] == code)]
    assert not rows.empty
    return rows.iloc[0].to_dict()


def test_amazon_blank_bbp_813_creates_high_conflict(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        pass_rows=[_pass_row("ASIN-HIGH", "813")],
        scrape_rows=[_scrape_row("ASIN-HIGH", monthly_sold="", bbp_units="813")],
    )

    row = _row_for_code(result.audit_df, "ASIN-HIGH", "amazon_blank_bbp_high")
    assert row["amazon_demand_floor"] == "0"
    assert row["amazon_demand_ceiling"] == "49"
    assert row["bbp_units"] == "813"
    assert row["recommended_action"] == "remove_from_clean_pass"


def test_amazon_blank_bbp_30_is_low_or_not_high_conflict(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        pass_rows=[_pass_row("ASIN-LOW", "30")],
        scrape_rows=[_scrape_row("ASIN-LOW", monthly_sold="", bbp_units="30")],
    )

    codes = set(result.audit_df["demand_conflict_code"])
    assert "amazon_blank_bbp_high" not in codes
    _row_for_code(result.audit_df, "ASIN-LOW", "amazon_blank_bbp_low")


def test_amazon_50_plus_bbp_67_creates_reasonable(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        pass_rows=[_pass_row("ASIN-67", "67")],
        scrape_rows=[_scrape_row("ASIN-67", monthly_sold="50+ bought in past month", bbp_units="67")],
    )

    row = _row_for_code(result.audit_df, "ASIN-67", "amazon_50_bbp_reasonable")
    assert row["amazon_demand_floor"] == "50"
    assert row["recommended_action"] == "allow_if_other_checks_pass"


def test_amazon_50_plus_bbp_180_creates_warn(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        pass_rows=[_pass_row("ASIN-180", "180")],
        scrape_rows=[_scrape_row("ASIN-180", monthly_sold="50+ bought in past month", bbp_units="180")],
    )

    row = _row_for_code(result.audit_df, "ASIN-180", "amazon_50_bbp_warn")
    assert row["recommended_action"] == "manual_review"


def test_amazon_50_plus_bbp_1000_creates_inflated(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        pass_rows=[_pass_row("ASIN-1000", "1000")],
        scrape_rows=[_scrape_row("ASIN-1000", monthly_sold="50+ bought in past month", bbp_units="1000")],
    )

    row = _row_for_code(result.audit_df, "ASIN-1000", "amazon_50_bbp_inflated")
    assert row["recommended_action"] == "remove_from_clean_pass"


def test_uk_reviews_under_6_strengthens_demand_risk_action(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        pass_rows=[_pass_row("ASIN-WEAK-UK", "813")],
        scrape_rows=[
            _scrape_row("ASIN-WEAK-UK", monthly_sold="", bbp_units="813", uk_reviews="3", variant_reviews="469")
        ],
    )

    primary = _row_for_code(result.audit_df, "ASIN-WEAK-UK", "amazon_blank_bbp_high")
    weak = _row_for_code(result.audit_df, "ASIN-WEAK-UK", "weak_uk_review_confirms_demand_risk")
    assert primary["confidence_adjustment"] == "weak_uk_review_confirms_demand_risk"
    assert weak["recommended_action"] == "strengthen_demand_risk_action"
    assert weak["uk_reviews"] == "3"


def test_missing_seller_stock_is_reported_not_invented(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        pass_rows=[_pass_row("ASIN-STOCK", "813")],
        scrape_rows=[_scrape_row("ASIN-STOCK", monthly_sold="", bbp_units="813")],
    )

    stock_row = _row_for_code(result.audit_df, "ASIN-STOCK", "seller_stock_missing_for_demand_check")
    assert stock_row["confidence_adjustment"] == "seller_stock_count_not_stored"
    assert stock_row["evidence_source"] == "seller_stock_count_missing"
    assert result.report["seller_stock_count_columns_found"] == []


def test_output_has_no_unclassified_rows(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        pass_rows=[
            _pass_row("ASIN-HIGH", "813"),
            _pass_row("ASIN-LOW", "30"),
            _pass_row("ASIN-WARN", "180"),
        ],
        scrape_rows=[
            _scrape_row("ASIN-HIGH", monthly_sold="", bbp_units="813"),
            _scrape_row("ASIN-LOW", monthly_sold="", bbp_units="30"),
            _scrape_row("ASIN-WARN", monthly_sold="50+ bought in past month", bbp_units="180"),
        ],
    )

    assert result.report["unclassified_rows"] == 0
    assert all(code in VALID_DEMAND_CONFLICT_CODES for code in result.audit_df["demand_conflict_code"])
    assert all(str(value).strip() != "" for value in result.audit_df["recommended_action"])


def test_b0c8c3jf9x_is_flagged_from_current_artifacts_if_present(tmp_path: Path) -> None:
    if not DEFAULT_PASS_PATH.exists() and not DEFAULT_NEAR_MISS_PATH.exists():
        pytest.skip("current F review artifacts are not present")

    result = build_demand_range_bbp_conflict_audit(
        pass_path=DEFAULT_PASS_PATH,
        near_miss_path=DEFAULT_NEAR_MISS_PATH,
        scrape_evidence_path=DEFAULT_SCRAPE_EVIDENCE_PATH,
        backtest_summary_path=DEFAULT_BACKTEST_SUMMARY_PATH,
        review_events_path=DEFAULT_REVIEW_EVENTS_PATH,
        output_path=tmp_path / "f_demand_range_bbp_conflict_audit_latest.csv",
    )
    b0_rows = result.audit_df.loc[result.audit_df["asin"] == "B0C8C3JF9X"]
    if b0_rows.empty:
        pytest.skip("B0C8C3JF9X is not present in current F review artifacts")

    codes = set(b0_rows["demand_conflict_code"])
    assert "amazon_blank_bbp_high" in codes
    primary = b0_rows.loc[b0_rows["demand_conflict_code"] == "amazon_blank_bbp_high"].iloc[0]
    assert primary["bbp_units"] == "1017"
    assert primary["expected_units_next_30d"] == "813.6"
