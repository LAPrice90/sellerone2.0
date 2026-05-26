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

from scripts.one_off.F029_build_history_borderline_near_miss_audit import (  # noqa: E402
    OUTPUT_COLUMNS,
    build_history_borderline_near_miss_audit,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _near_row(asin: str, *, supplier_sku: str | None = None, near_miss_type: str = "history_risk_conflict") -> dict[str, str]:
    token = asin.lower()
    return {
        "supplier_sku": supplier_sku or f"sku-{token}",
        "asin": asin,
        "candidate_id": f"cand-{token}",
        "title": f"Product {asin}",
        "near_miss_type": near_miss_type,
        "reviewability_state": "remove_from_clean_pass",
        "screening_fail_code": "HISTORY_RISK_BLOCK",
        "history_risk_code": "history_fail_phase_avoid",
        "history_recommended_action": "remove_from_clean_pass",
        "expected_units_next_30d": "50",
        "expected_profit_next_30d_gbp": "40",
        "profit_per_unit_30d_gbp": "5",
        "main_rank": "12345",
    }


def _scrape_row(
    asin: str,
    *,
    supplier_sku: str | None = None,
    profit_pct: str = "20",
    loss_pct: str = "55",
    longest_loss_days: str = "100",
    pricing_score: str = "20",
    history_score: str = "35",
    avg_30_day_price: str = "30",
    break_even: str = "20",
    chart_phase_daily_series: str = "",
    chart_raw_amazon_daily_series: str = "",
) -> dict[str, str]:
    token = asin.lower()
    return {
        "observed_utc": "2026-04-29T10:00:00Z",
        "scan_day": "2026-04-29",
        "supplier_sku": supplier_sku or f"sku-{token}",
        "asin": asin,
        "candidate_id": f"cand-{token}",
        "phase_profit_pct": profit_pct,
        "phase_low_roi_pct": "5",
        "phase_break_even_pct": "0",
        "phase_loss_pct": loss_pct,
        "avg_30_day_price": avg_30_day_price,
        "break_even": break_even,
        "phase_longest_profit_days": "30",
        "phase_longest_loss_days": longest_loss_days,
        "pricing_history_score": pricing_score,
        "ranking_history_score": "60",
        "history_operational_score": history_score,
        "history_recommendation": "FAIL",
        "phase_recommendation": "AVOID",
        "exit_strategy": "SELL_OFF_ALLOWED",
        "chart_phase_daily_series": chart_phase_daily_series,
        "chart_raw_amazon_daily_series": chart_raw_amazon_daily_series,
    }


def _phase_series(days: int, *, profit: int = 0, low_roi: int = 0, loss: int = 0, break_even: int = 0) -> str:
    values = (
        ["loss"] * loss
        + ["low_roi"] * low_roi
        + ["break_even"] * break_even
        + ["profit"] * profit
    )
    assert len(values) == days
    start = pd.Timestamp("2026-01-01")
    return ";".join(f"{(start + pd.Timedelta(days=i)).date()}={value}" for i, value in enumerate(values))


def _phase_series_from_values(values: list[str]) -> str:
    start = pd.Timestamp("2026-01-01")
    return ";".join(f"{(start + pd.Timedelta(days=i)).date()}={value}" for i, value in enumerate(values))


def _price_series(days: int, *, below: int = 0, near: int = 0, good: int = 0, break_even: float = 20.0) -> str:
    values = (
        [break_even - 1.0] * below
        + [break_even * 1.05] * near
        + [break_even * 1.5] * good
    )
    assert len(values) == days
    start = pd.Timestamp("2026-01-01")
    return ";".join(f"{(start + pd.Timedelta(days=i)).date()}={value:.2f}" for i, value in enumerate(values))


def _run_audit(tmp_path: Path, near_rows: list[dict[str, str]], scrape_rows: list[dict[str, str]]):
    near_path = tmp_path / "near.csv"
    scrape_path = tmp_path / "scrape.csv"
    output_path = tmp_path / "audit.csv"
    summary_path = tmp_path / "summary.md"
    _write_csv(near_path, near_rows)
    _write_csv(scrape_path, scrape_rows)
    return build_history_borderline_near_miss_audit(
        near_miss_path=near_path,
        scrape_evidence_path=scrape_path,
        output_path=output_path,
        summary_path=summary_path,
    )


def _row_for_asin(df: pd.DataFrame, asin: str) -> dict[str, str]:
    rows = df.loc[df["asin"] == asin]
    assert not rows.empty
    return rows.iloc[0].to_dict()


def test_strong_borderline_candidate_is_marked_for_manual_review_candidate(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        near_rows=[_near_row("ASIN-STRONG")],
        scrape_rows=[
            _scrape_row(
                "ASIN-STRONG",
                profit_pct="84.15",
                loss_pct="5.46",
                longest_loss_days="11",
                pricing_score="78",
                history_score="80",
            )
        ],
    )

    row = _row_for_asin(result.audit_df, "ASIN-STRONG")
    assert row["history_borderline_code"] == "history_pass_candidate_after_user_calibration"
    assert row["suggested_action"] == "manual_review_candidate"
    assert row["phase_profit_pct"] == "84.15"
    assert row["phase_loss_pct"] == "5.46"
    assert row["weak_days_pct"] == "10.46"
    assert row["avg_price_vs_break_even_pct"] == "50"
    assert result.report["unclassified_rows"] == 0


def test_strong_shape_without_user_calibration_stays_strong_borderline(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        near_rows=[_near_row("ASIN-STRONG-SHAPE")],
        scrape_rows=[
            _scrape_row(
                "ASIN-STRONG-SHAPE",
                profit_pct="70",
                loss_pct="5",
                longest_loss_days="11",
                pricing_score="70",
                history_score="70",
                avg_30_day_price="30",
                break_even="20",
            )
        ],
    )

    row = _row_for_asin(result.audit_df, "ASIN-STRONG-SHAPE")
    assert row["history_borderline_code"] == "strong_borderline_history_review_candidate"
    assert row["suggested_action"] == "manual_review_candidate"


def test_good_shape_but_limited_upside_stays_remove_from_clean_pass(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        near_rows=[_near_row("ASIN-LIMITED-UP")],
        scrape_rows=[
            _scrape_row(
                "ASIN-LIMITED-UP",
                profit_pct="84.15",
                loss_pct="5.46",
                longest_loss_days="11",
                pricing_score="78",
                history_score="80",
                avg_30_day_price="107.08",
                break_even="83.21",
            )
        ],
    )

    row = _row_for_asin(result.audit_df, "ASIN-LIMITED-UP")
    assert row["history_borderline_code"] == "borderline_but_limited_upside"
    assert row["suggested_action"] == "keep_remove_from_clean_pass"
    assert row["avg_price_vs_break_even_pct"] == "28.686456"


def test_recent_clean_recovery_overrides_old_bad_history(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        near_rows=[_near_row("ASIN-RECOVERED")],
        scrape_rows=[
            _scrape_row(
                "ASIN-RECOVERED",
                profit_pct="60",
                loss_pct="20",
                longest_loss_days="40",
                pricing_score="58",
                history_score="59",
                avg_30_day_price="40",
                break_even="20",
                chart_phase_daily_series=_phase_series(180, loss=40, low_roi=20, profit=120),
            )
        ],
    )

    row = _row_for_asin(result.audit_df, "ASIN-RECOVERED")
    assert row["history_borderline_code"] == "history_recent_recovery_pass_candidate"
    assert row["suggested_action"] == "manual_review_candidate"
    assert row["phase_profit_pct_90d"] == "100"
    assert row["phase_loss_pct_90d"] == "0"


def test_amazon_below_break_even_hard_fails_even_after_recent_recovery(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        near_rows=[_near_row("ASIN-AMAZON-BELOW")],
        scrape_rows=[
            _scrape_row(
                "ASIN-AMAZON-BELOW",
                profit_pct="76",
                loss_pct="8",
                longest_loss_days="20",
                pricing_score="65",
                history_score="65",
                avg_30_day_price="40",
                break_even="20",
                chart_phase_daily_series=_phase_series(180, loss=10, profit=170),
                chart_raw_amazon_daily_series=_price_series(180, below=45, near=20, good=115, break_even=20),
            )
        ],
    )

    row = _row_for_asin(result.audit_df, "ASIN-AMAZON-BELOW")
    assert row["history_borderline_code"] == "history_amazon_below_be_fail_supported"
    assert row["suggested_action"] == "keep_remove_from_clean_pass"
    assert row["amazon_pressure_signal"] == "amazon_below_break_even_hard_fail"


def test_sparse_amazon_with_clean_recent_phase_is_recovery_candidate(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        near_rows=[_near_row("ASIN-SPARSE-AMAZON")],
        scrape_rows=[
            _scrape_row(
                "ASIN-SPARSE-AMAZON",
                profit_pct="52",
                loss_pct="18",
                longest_loss_days="50",
                pricing_score="58",
                history_score="58",
                avg_30_day_price="50",
                break_even="25",
                chart_phase_daily_series=_phase_series(180, loss=8, low_roi=42, profit=130),
                chart_raw_amazon_daily_series=_price_series(10, near=10, break_even=25),
            )
        ],
    )

    row = _row_for_asin(result.audit_df, "ASIN-SPARSE-AMAZON")
    assert row["history_borderline_code"] == "history_recent_recovery_pass_candidate"
    assert row["amazon_pressure_signal"] == "amazon_sparse_or_absent"


def test_recent_amazon_recovery_can_support_history_pass_candidate(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        near_rows=[_near_row("ASIN-AMAZON-RECOVERED")],
        scrape_rows=[
            _scrape_row(
                "ASIN-AMAZON-RECOVERED",
                profit_pct="67",
                loss_pct="13",
                longest_loss_days="31",
                pricing_score="58",
                history_score="58",
                avg_30_day_price="34",
                break_even="25",
                chart_phase_daily_series=_phase_series(180, loss=30, low_roi=30, profit=120),
                chart_raw_amazon_daily_series=_price_series(180, below=12, near=8, good=160, break_even=25),
            )
        ],
    )

    row = _row_for_asin(result.audit_df, "ASIN-AMAZON-RECOVERED")
    assert row["history_borderline_code"] == "history_recent_recovery_pass_candidate"
    assert row["amazon_pressure_signal"] == "amazon_recent_above_break_even_recovered"


def test_recent_weakness_stays_failed(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        near_rows=[_near_row("ASIN-RECENT-WEAK")],
        scrape_rows=[
            _scrape_row(
                "ASIN-RECENT-WEAK",
                profit_pct="55",
                loss_pct="18",
                longest_loss_days="38",
                pricing_score="58",
                history_score="59",
                avg_30_day_price="30",
                break_even="20",
                chart_phase_daily_series=_phase_series_from_values(["profit"] * 90 + ["loss"] * 30 + ["low_roi"] * 60),
            )
        ],
    )

    row = _row_for_asin(result.audit_df, "ASIN-RECENT-WEAK")
    assert row["history_borderline_code"] == "history_recent_weakness_fail_supported"
    assert row["suggested_action"] == "keep_remove_from_clean_pass"


def test_possible_borderline_candidate_is_separate_from_strong_candidate(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        near_rows=[_near_row("ASIN-POSSIBLE")],
        scrape_rows=[
            _scrape_row(
                "ASIN-POSSIBLE",
                profit_pct="55",
                loss_pct="18",
                longest_loss_days="40",
                pricing_score="58",
                history_score="60",
            )
        ],
    )

    row = _row_for_asin(result.audit_df, "ASIN-POSSIBLE")
    assert row["history_borderline_code"] == "possible_borderline_history_review_candidate"
    assert row["suggested_action"] == "inspect_before_rule_change"


def test_bad_history_stays_supported_fail(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        near_rows=[_near_row("ASIN-BAD")],
        scrape_rows=[
            _scrape_row(
                "ASIN-BAD",
                profit_pct="10",
                loss_pct="70",
                longest_loss_days="160",
                pricing_score="10",
                history_score="20",
            )
        ],
    )

    row = _row_for_asin(result.audit_df, "ASIN-BAD")
    assert row["history_borderline_code"] == "history_fail_supported"
    assert row["suggested_action"] == "keep_remove_from_clean_pass"


def test_missing_metrics_are_reported_as_rescan_needed(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        near_rows=[_near_row("ASIN-MISSING")],
        scrape_rows=[{"supplier_sku": "sku-asin-missing", "asin": "ASIN-MISSING", "candidate_id": "cand-asin-missing"}],
    )

    row = _row_for_asin(result.audit_df, "ASIN-MISSING")
    assert row["history_borderline_code"] == "history_metrics_missing"
    assert row["suggested_action"] == "targeted_rescan_needed"


def test_non_history_near_misses_are_excluded_and_schema_is_stable(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        near_rows=[
            _near_row("ASIN-HISTORY"),
            _near_row("ASIN-DEMAND", near_miss_type="demand_range_conflict"),
        ],
        scrape_rows=[_scrape_row("ASIN-HISTORY")],
    )

    assert list(result.audit_df.columns) == OUTPUT_COLUMNS
    assert len(result.audit_df.index) == 1
    assert result.output_path.exists()
    assert result.summary_path.exists()
