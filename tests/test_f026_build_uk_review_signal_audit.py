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

from scripts.one_off.F026_build_uk_review_signal_audit import (
    VALID_UK_REVIEW_CODES,
    build_uk_review_signal_audit,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _pass_row(candidate_id: str, asin: str) -> dict[str, str]:
    return {
        "candidate_id": candidate_id,
        "supplier_sku": f"sku-{candidate_id}",
        "asin": asin,
        "expected_units_next_30d": "42",
        "expected_profit_next_30d_gbp": "27.5",
    }


def _scrape_row(candidate_id: str, asin: str, uk_reviews: str) -> dict[str, str]:
    return {
        "observed_utc": "2026-04-23T10:00:00Z",
        "candidate_id": candidate_id,
        "supplier_sku": f"sku-{candidate_id}",
        "asin": asin,
        "historical_uk_reviews": uk_reviews,
        "variant_reviews": "469",
    }


def _run_audit(
    tmp_path: Path,
    *,
    pass_rows: list[dict[str, str]],
    scrape_rows: list[dict[str, str]],
    near_miss_rows: list[dict[str, str]] | None = None,
):
    pass_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
    near_miss_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_near_miss_review_latest.csv"
    scrape_path = tmp_path / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv"
    output_path = tmp_path / "out" / "analysis_reports" / "f_uk_review_signal_audit_latest.csv"

    _write_csv(pass_path, pass_rows)
    _write_csv(near_miss_path, near_miss_rows or [])
    _write_csv(scrape_path, scrape_rows)

    return build_uk_review_signal_audit(
        pass_path=pass_path,
        near_miss_path=near_miss_path,
        scrape_evidence_path=scrape_path,
        output_path=output_path,
    )


def _row_for_asin(audit_df: pd.DataFrame, asin: str) -> dict[str, str]:
    rows = audit_df.loc[audit_df["asin"] == asin]
    assert not rows.empty
    return rows.iloc[0].to_dict()


@pytest.mark.parametrize("uk_reviews", ["0", "1", "2"])
def test_uk_reviews_0_to_2_creates_uk_reviews_lt3(tmp_path: Path, uk_reviews: str) -> None:
    result = _run_audit(
        tmp_path,
        pass_rows=[_pass_row("cand-lt3", "ASIN-LT3")],
        scrape_rows=[_scrape_row("cand-lt3", "ASIN-LT3", uk_reviews)],
    )

    row = _row_for_asin(result.audit_df, "ASIN-LT3")
    assert row["uk_review_code"] == "uk_reviews_lt3"
    assert row["uk_review_recommended_action"] == "remove_from_clean_pass"


@pytest.mark.parametrize("uk_reviews", ["3", "4", "5"])
def test_uk_reviews_3_to_5_creates_uk_reviews_3_to_5(tmp_path: Path, uk_reviews: str) -> None:
    result = _run_audit(
        tmp_path,
        pass_rows=[_pass_row("cand-3to5", "ASIN-3TO5")],
        scrape_rows=[_scrape_row("cand-3to5", "ASIN-3TO5", uk_reviews)],
    )

    row = _row_for_asin(result.audit_df, "ASIN-3TO5")
    assert row["uk_review_code"] == "uk_reviews_3_to_5"
    assert row["uk_review_recommended_action"] == "manual_review"


@pytest.mark.parametrize("uk_reviews", ["6", "7", "9"])
def test_uk_reviews_6_to_9_creates_uk_reviews_6_to_9(tmp_path: Path, uk_reviews: str) -> None:
    result = _run_audit(
        tmp_path,
        pass_rows=[_pass_row("cand-6to9", "ASIN-6TO9")],
        scrape_rows=[_scrape_row("cand-6to9", "ASIN-6TO9", uk_reviews)],
    )

    row = _row_for_asin(result.audit_df, "ASIN-6TO9")
    assert row["uk_review_code"] == "uk_reviews_6_to_9"
    assert row["uk_review_recommended_action"] == "supporting_evidence_only"


@pytest.mark.parametrize("uk_reviews", ["10", "25"])
def test_uk_reviews_10_plus_creates_uk_reviews_10_plus(tmp_path: Path, uk_reviews: str) -> None:
    result = _run_audit(
        tmp_path,
        pass_rows=[_pass_row("cand-10plus", "ASIN-10PLUS")],
        scrape_rows=[_scrape_row("cand-10plus", "ASIN-10PLUS", uk_reviews)],
    )

    row = _row_for_asin(result.audit_df, "ASIN-10PLUS")
    assert row["uk_review_code"] == "uk_reviews_10_plus"
    assert row["uk_review_recommended_action"] == "allow_if_other_checks_pass"


def test_missing_uk_reviews_creates_uk_reviews_missing(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        pass_rows=[_pass_row("cand-missing", "ASIN-MISSING")],
        scrape_rows=[_scrape_row("cand-missing", "ASIN-MISSING", "")],
    )

    row = _row_for_asin(result.audit_df, "ASIN-MISSING")
    assert row["uk_review_code"] == "uk_reviews_missing"
    assert row["uk_review_recommended_action"] == "targeted_rescan_needed"


def test_output_has_no_unclassified_rows(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        pass_rows=[
            _pass_row("cand-lt3", "ASIN-LT3"),
            _pass_row("cand-3to5", "ASIN-3TO5"),
            _pass_row("cand-6to9", "ASIN-6TO9"),
            _pass_row("cand-10plus", "ASIN-10PLUS"),
            _pass_row("cand-missing", "ASIN-MISSING"),
        ],
        scrape_rows=[
            _scrape_row("cand-lt3", "ASIN-LT3", "2"),
            _scrape_row("cand-3to5", "ASIN-3TO5", "4"),
            _scrape_row("cand-6to9", "ASIN-6TO9", "8"),
            _scrape_row("cand-10plus", "ASIN-10PLUS", "12"),
            _scrape_row("cand-missing", "ASIN-MISSING", ""),
        ],
    )

    assert result.report["unclassified_rows"] == 0
    assert all(code in VALID_UK_REVIEW_CODES for code in result.audit_df["uk_review_code"])
    assert all(str(value).strip() != "" for value in result.audit_df["uk_review_recommended_action"])
