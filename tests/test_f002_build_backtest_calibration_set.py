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

from scripts.one_off.F002_build_backtest_calibration_set import (
    BUCKET_ORDER,
    build_backtest_calibration_set,
)


def _write_summary(path: Path, rows: list[dict[str, str]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_input(path: Path, rows: list[dict[str, str]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def _summary_row(
    *,
    seller_sku: str,
    asin: str,
    summary_status: str,
    recommendation: str,
    history_confidence: str,
    viability: str = "50",
    exit_risk: str = "50",
    amazon_risk_level: str = "low",
    compression_risk_level: str = "low",
    monthly_profit: str = "10",
    total_profit: str = "100",
    capital_lockup_days: str = "30",
    sellable_ceiling_zone: str = "normal",
    share_assumption_basis: str = "v1_measured_share",
    seasonality_flag: str = "",
    failure_event_count: str = "0",
    longest_failure_streak_days: str = "0",
    manual_review_reason: str = "",
    summary_reason_codes: str = "",
) -> dict[str, str]:
    return {
        "seller_sku": seller_sku,
        "asin": asin,
        "summary_status": summary_status,
        "summary_reason_codes": summary_reason_codes,
        "history_confidence": history_confidence,
        "market_viability_score": viability,
        "exit_risk_score": exit_risk,
        "estimated_total_profit_gbp": total_profit,
        "estimated_monthly_profit_gbp": monthly_profit,
        "capital_lockup_days": capital_lockup_days,
        "sellable_ceiling_zone": sellable_ceiling_zone,
        "amazon_risk_level": amazon_risk_level,
        "compression_risk_level": compression_risk_level,
        "recommendation": recommendation,
        "manual_review_reason": manual_review_reason,
        "share_assumption_basis": share_assumption_basis,
        "seasonality_flag": seasonality_flag,
        "failure_event_count": failure_event_count,
        "longest_failure_streak_days": longest_failure_streak_days,
    }


def test_f002_builds_review_ready_calibration_pack_when_scenarios_exist(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.csv"
    input_path = tmp_path / "input.csv"
    output_dir = tmp_path / "out"

    rows = [
        _summary_row(
            seller_sku="SKU-FAIL",
            asin="ASIN-FAIL",
            summary_status="ready",
            recommendation="Avoid",
            history_confidence="medium",
            viability="18",
            exit_risk="88",
            monthly_profit="0",
            total_profit="0",
            longest_failure_streak_days="120",
        ),
        _summary_row(
            seller_sku="SKU-NEAR-FAIL",
            asin="ASIN-NEAR-FAIL",
            summary_status="ready",
            recommendation="Exit-only",
            history_confidence="medium",
            viability="48",
            exit_risk="18",
            amazon_risk_level="high",
            monthly_profit="40",
            total_profit="480",
        ),
        _summary_row(
            seller_sku="SKU-JUST-PASS",
            asin="ASIN-JUST-PASS",
            summary_status="ready",
            recommendation="Managed fit",
            history_confidence="medium",
            viability="63",
            exit_risk="14",
            compression_risk_level="high",
            monthly_profit="35",
            total_profit="420",
        ),
        _summary_row(
            seller_sku="SKU-LINE",
            asin="ASIN-LINE",
            summary_status="ready",
            recommendation="Exit-only",
            history_confidence="medium",
            viability="60",
            exit_risk="28",
            monthly_profit="0",
            total_profit="30",
        ),
        _summary_row(
            seller_sku="SKU-MANUAL",
            asin="ASIN-MANUAL",
            summary_status="manual_review",
            recommendation="Manual review",
            history_confidence="low",
            monthly_profit="0",
            total_profit="0",
            sellable_ceiling_zone="unknown",
            manual_review_reason="sparse_history",
            summary_reason_codes="input_not_ready|history_confidence_low|attribution_confidence_low",
        ),
        _summary_row(
            seller_sku="SKU-INFLATED",
            asin="ASIN-INFLATED",
            summary_status="ready",
            recommendation="Normal fit",
            history_confidence="medium",
            viability="95",
            exit_risk="0",
            monthly_profit="240",
            total_profit="2400",
            capital_lockup_days="220",
            sellable_ceiling_zone="stretched",
            share_assumption_basis="v1_measured_share_with_prior_and_scenario_caps",
            summary_reason_codes="summary_ready|share_source_sparse_asin_blend|share_sparse_asin_history",
        ),
    ]
    _write_summary(summary_path, rows)
    _write_input(
        input_path,
        [
            {"seller_sku": "SKU-FAIL", "asin": "ASIN-FAIL", "mapping_status": "unique_asin_match"},
            {"seller_sku": "SKU-NEAR-FAIL", "asin": "ASIN-NEAR-FAIL", "mapping_status": "unique_asin_match"},
            {"seller_sku": "SKU-JUST-PASS", "asin": "ASIN-JUST-PASS", "mapping_status": "unique_asin_match"},
            {"seller_sku": "SKU-LINE", "asin": "ASIN-LINE", "mapping_status": "unique_asin_match"},
            {"seller_sku": "SKU-MANUAL", "asin": "ASIN-MANUAL", "mapping_status": "unique_asin_match"},
            {"seller_sku": "SKU-INFLATED", "asin": "ASIN-INFLATED", "mapping_status": "unique_asin_match"},
        ],
    )

    result = build_backtest_calibration_set(
        summary_path=summary_path,
        input_path=input_path,
        output_dir=output_dir,
        target_count=6,
        observed_utc="2026-04-10T16:00:00Z",
    )

    assert len(result.selected_df) == 6
    assert not result.blockers
    assert set(result.selected_df["calibration_bucket"].tolist()) == set(BUCKET_ORDER)
    assert "review_prompt" in result.selected_df.columns
    assert "calibration_review_flag" in result.selected_df.columns
    assert "calibration_review_reason" in result.selected_df.columns
    assert "critical_amazon_recommendation_mismatch_flag" in result.selected_df.columns
    assert result.latest_path.exists()
    assert result.markdown_path.exists()

    prompt_prefix_by_bucket = {
        "certain_fail": "Clear fail check",
        "almost_pass": "Near miss check",
        "just_passed": "Borderline pass check",
        "on_the_line": "Decision-line check",
        "manual_review_or_unclear": "Evidence quality check",
        "demand_or_profit_inflation_risk": "Profit inflation check",
    }
    for _, row in result.selected_df.iterrows():
        assert row["review_prompt"]
        assert prompt_prefix_by_bucket[row["calibration_bucket"]] in row["review_prompt"]

    tags = result.selected_df["bucket_tags"].tolist()
    assert any("amazon_risk_learning_case" in value for value in tags)
    assert any("compression_risk_learning_case" in value for value in tags)
    assert any("share_prior_risk" in value for value in tags)

    markdown_text = result.markdown_path.read_text(encoding="utf-8")
    assert "## Scenario availability" in markdown_text
    assert "## Selected pack coverage" in markdown_text
    assert "## Learning-case coverage" in markdown_text
    assert "- certain_fail: `1`" in markdown_text
    assert "- demand_or_profit_inflation_risk: `1`" in markdown_text


def test_f002_flags_critical_amazon_recommendation_mismatch(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.csv"
    input_path = tmp_path / "input.csv"
    output_dir = tmp_path / "out"

    rows = [
        _summary_row(
            seller_sku="SKU-MISMATCH-1",
            asin="ASIN-MISMATCH-1",
            summary_status="ready",
            recommendation="Managed fit",
            history_confidence="high",
            viability="80",
            exit_risk="20",
            amazon_risk_level="critical",
        ),
    ]
    _write_summary(summary_path, rows)
    _write_input(input_path, [{"seller_sku": "SKU-MISMATCH-1", "asin": "ASIN-MISMATCH-1", "mapping_status": "unique_asin_match"}])

    result = build_backtest_calibration_set(
        summary_path=summary_path,
        input_path=input_path,
        output_dir=output_dir,
        target_count=1,
        observed_utc="2026-04-10T16:03:00Z",
    )

    assert len(result.selected_df) == 1
    row = result.selected_df.iloc[0]
    assert row["critical_amazon_recommendation_mismatch_flag"] == "1"
    assert row["calibration_review_flag"] == "1"
    assert row["calibration_review_reason"] == "critical_amazon_recommendation_mismatch"


def test_f002_does_not_flag_mismatch_for_critical_with_exit_only_or_avoid(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.csv"
    input_path = tmp_path / "input.csv"
    output_dir = tmp_path / "out"

    rows = [
        _summary_row(
            seller_sku="SKU-CRIT-EXIT",
            asin="ASIN-CRIT-EXIT",
            summary_status="ready",
            recommendation="Exit-only",
            history_confidence="high",
            viability="55",
            exit_risk="65",
            amazon_risk_level="critical",
        ),
        _summary_row(
            seller_sku="SKU-CRIT-AVOID",
            asin="ASIN-CRIT-AVOID",
            summary_status="ready",
            recommendation="Avoid",
            history_confidence="high",
            viability="22",
            exit_risk="90",
            amazon_risk_level="critical",
        ),
    ]
    _write_summary(summary_path, rows)
    _write_input(
        input_path,
        [
            {"seller_sku": "SKU-CRIT-EXIT", "asin": "ASIN-CRIT-EXIT", "mapping_status": "unique_asin_match"},
            {"seller_sku": "SKU-CRIT-AVOID", "asin": "ASIN-CRIT-AVOID", "mapping_status": "unique_asin_match"},
        ],
    )

    result = build_backtest_calibration_set(
        summary_path=summary_path,
        input_path=input_path,
        output_dir=output_dir,
        target_count=2,
        observed_utc="2026-04-10T16:04:00Z",
    )

    assert len(result.selected_df) == 2
    assert set(result.selected_df["critical_amazon_recommendation_mismatch_flag"].tolist()) == {"0"}
    assert set(result.selected_df["calibration_review_flag"].tolist()) == {"0"}
    assert set(result.selected_df["calibration_review_reason"].tolist()) == {""}


def test_f002_flags_blockers_when_ready_rows_are_missing(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.csv"
    input_path = tmp_path / "input.csv"
    output_dir = tmp_path / "out"

    rows = [
        _summary_row(
            seller_sku="SKU-A1",
            asin="ASIN-A1",
            summary_status="manual_review",
            recommendation="Manual review",
            history_confidence="high",
            manual_review_reason="no_product_db_match",
            summary_reason_codes="input_not_ready|no_product_db_match",
            sellable_ceiling_zone="unknown",
            monthly_profit="0",
            total_profit="0",
        ),
        _summary_row(
            seller_sku="SKU-A2",
            asin="ASIN-A2",
            summary_status="manual_review",
            recommendation="Manual review",
            history_confidence="medium",
            manual_review_reason="no_product_db_match",
            summary_reason_codes="input_not_ready|no_product_db_match",
            sellable_ceiling_zone="unknown",
            monthly_profit="0",
            total_profit="0",
        ),
        _summary_row(
            seller_sku="SKU-A3",
            asin="ASIN-A3",
            summary_status="manual_review",
            recommendation="Manual review",
            history_confidence="low",
            manual_review_reason="history_confidence_low",
            summary_reason_codes="input_not_ready|history_confidence_low",
            sellable_ceiling_zone="unknown",
            monthly_profit="0",
            total_profit="0",
        ),
    ]
    _write_summary(summary_path, rows)
    _write_input(
        input_path,
        [
            {"seller_sku": "SKU-A1", "asin": "ASIN-A1", "mapping_status": "no_product_db_match"},
            {"seller_sku": "SKU-A2", "asin": "ASIN-A2", "mapping_status": "no_product_db_match"},
            {"seller_sku": "SKU-A3", "asin": "ASIN-A3", "mapping_status": "no_product_db_match"},
        ],
    )

    result = build_backtest_calibration_set(
        summary_path=summary_path,
        input_path=input_path,
        output_dir=output_dir,
        target_count=6,
        observed_utc="2026-04-10T16:05:00Z",
    )

    assert len(result.selected_df) == 3
    assert "no_ready_summary_rows" in result.blockers
    assert "missing_bucket_certain_fail" in result.blockers
    assert "missing_bucket_just_passed" in result.blockers
    assert "missing_bucket_demand_or_profit_inflation_risk" in result.blockers
    assert "input_contains_no_product_db_match_rows" in result.blockers
    assert "review_prompt" in result.selected_df.columns
    assert "calibration_review_flag" in result.selected_df.columns
    assert "critical_amazon_recommendation_mismatch_flag" in result.selected_df.columns
    markdown_text = result.markdown_path.read_text(encoding="utf-8")
    assert "Calibration cannot balance pass and fail review scenarios" in markdown_text


def test_f002_rejects_invalid_target_count(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.csv"
    input_path = tmp_path / "input.csv"
    output_dir = tmp_path / "out"
    _write_summary(
        summary_path,
        [
            _summary_row(
                seller_sku="S1",
                asin="A1",
                summary_status="ready",
                recommendation="Normal fit",
                history_confidence="high",
            )
        ],
    )
    _write_input(input_path, [])

    with pytest.raises(ValueError):
        build_backtest_calibration_set(
            summary_path=summary_path,
            input_path=input_path,
            output_dir=output_dir,
            target_count=0,
            observed_utc="2026-04-10T16:10:00Z",
        )
