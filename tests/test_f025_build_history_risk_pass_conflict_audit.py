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

from scripts.one_off.F025_build_history_risk_pass_conflict_audit import (
    VALID_HISTORY_RISK_CODES,
    build_history_risk_pass_conflict_audit,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _pass_row(
    asin: str,
    *,
    candidate_id: str | None = None,
    supplier_sku: str | None = None,
    commercial_note: str = "",
) -> dict[str, str]:
    token = asin.lower()
    return {
        "asin": asin,
        "candidate_id": candidate_id or f"cand-{token}",
        "supplier_sku": supplier_sku or f"sku-{token}",
        "expected_units_next_30d": "75",
        "expected_profit_next_30d_gbp": "55",
        "watch_data_summary": "",
        "commercial_note": commercial_note,
    }


def _scrape_row(
    asin: str,
    *,
    history_recommendation: str = "PASS",
    phase_recommendation: str = "PASS",
    opportunity_recommendation: str = "PASS",
) -> dict[str, str]:
    token = asin.lower()
    return {
        "observed_utc": "2026-04-23T10:00:00Z",
        "scan_day": "2026-04-23",
        "asin": asin,
        "candidate_id": f"cand-{token}",
        "supplier_sku": f"sku-{token}",
        "history_recommendation": history_recommendation,
        "phase_recommendation": phase_recommendation,
        "opportunity_recommendation": opportunity_recommendation,
    }


def _backtest_row(
    asin: str,
    *,
    recommendation: str = "Managed fit",
    failure_event_count: str = "0",
    time_normal_sell_days: str = "12",
    time_selloff_days: str = "3",
) -> dict[str, str]:
    token = asin.lower()
    return {
        "observed_utc": "2026-04-23T10:00:00Z",
        "asin": asin,
        "seller_sku": f"sku-{token}",
        "recommendation": recommendation,
        "failure_event_count": failure_event_count,
        "time_normal_sell_days": time_normal_sell_days,
        "time_selloff_days": time_selloff_days,
        "expected_units_next_30d": "75",
        "expected_profit_next_30d_gbp": "55",
    }


def _run_audit(
    tmp_path: Path,
    *,
    pass_rows: list[dict[str, str]],
    scrape_rows: list[dict[str, str]],
    backtest_rows: list[dict[str, str]],
):
    pass_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
    scrape_path = tmp_path / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv"
    backtest_path = tmp_path / "out" / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv"
    output_path = tmp_path / "out" / "analysis_reports" / "f_history_risk_pass_conflict_audit_latest.csv"

    _write_csv(pass_path, pass_rows)
    _write_csv(scrape_path, scrape_rows)
    _write_csv(backtest_path, backtest_rows)

    return build_history_risk_pass_conflict_audit(
        pass_path=pass_path,
        scrape_evidence_path=scrape_path,
        backtest_summary_path=backtest_path,
        output_path=output_path,
    )


def _row_for_asin(result_df: pd.DataFrame, asin: str) -> dict[str, str]:
    rows = result_df.loc[result_df["asin"] == asin]
    assert not rows.empty
    return rows.iloc[0].to_dict()


def test_history_fail_plus_phase_avoid_creates_history_fail_phase_avoid(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        pass_rows=[_pass_row("ASIN-HIST-FAIL")],
        scrape_rows=[_scrape_row("ASIN-HIST-FAIL", history_recommendation="FAIL", phase_recommendation="AVOID")],
        backtest_rows=[_backtest_row("ASIN-HIST-FAIL")],
    )

    row = _row_for_asin(result.audit_df, "ASIN-HIST-FAIL")
    assert row["history_risk_code"] == "history_fail_phase_avoid"
    assert row["history_recommended_action"] == "remove_from_clean_pass"


def test_backtest_avoid_plus_commercial_avoid_creates_backtest_avoid_commercial_rule(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        pass_rows=[_pass_row("ASIN-BT-AVOID", commercial_note="Avoid | PASS")],
        scrape_rows=[_scrape_row("ASIN-BT-AVOID", opportunity_recommendation="Avoid")],
        backtest_rows=[_backtest_row("ASIN-BT-AVOID", recommendation="Avoid")],
    )

    row = _row_for_asin(result.audit_df, "ASIN-BT-AVOID")
    assert row["history_risk_code"] == "backtest_avoid_commercial_avoid_or_exit"
    assert row["history_recommended_action"] == "remove_from_clean_pass"


def test_exit_only_clean_pass_creates_exit_only_clean_pass_rule(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        pass_rows=[_pass_row("ASIN-EXIT", commercial_note="Exit-only | PASS")],
        scrape_rows=[_scrape_row("ASIN-EXIT", opportunity_recommendation="Exit-only")],
        backtest_rows=[_backtest_row("ASIN-EXIT", recommendation="Exit-only")],
    )

    row = _row_for_asin(result.audit_df, "ASIN-EXIT")
    assert row["history_risk_code"] == "exit_only_clean_pass"
    assert row["history_recommended_action"] == "remove_from_clean_pass"


def test_failure_event_count_over_100_creates_failure_events_100_plus(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        pass_rows=[_pass_row("ASIN-FAIL-COUNT")],
        scrape_rows=[_scrape_row("ASIN-FAIL-COUNT")],
        backtest_rows=[_backtest_row("ASIN-FAIL-COUNT", failure_event_count="150")],
    )

    row = _row_for_asin(result.audit_df, "ASIN-FAIL-COUNT")
    assert row["history_risk_code"] == "failure_events_100_plus"
    assert row["history_recommended_action"] == "manual_review"


def test_selloff_days_greater_than_normal_creates_selloff_days_rule(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        pass_rows=[_pass_row("ASIN-SELLOFF")],
        scrape_rows=[_scrape_row("ASIN-SELLOFF")],
        backtest_rows=[_backtest_row("ASIN-SELLOFF", time_normal_sell_days="9", time_selloff_days="17")],
    )

    row = _row_for_asin(result.audit_df, "ASIN-SELLOFF")
    assert row["history_risk_code"] == "selloff_days_exceed_normal_days"
    assert row["history_recommended_action"] == "manual_review"


def test_clear_rows_produce_history_risk_clear(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        pass_rows=[_pass_row("ASIN-CLEAR")],
        scrape_rows=[_scrape_row("ASIN-CLEAR", history_recommendation="PASS", phase_recommendation="PASS")],
        backtest_rows=[_backtest_row("ASIN-CLEAR", recommendation="Managed fit", failure_event_count="10")],
    )

    row = _row_for_asin(result.audit_df, "ASIN-CLEAR")
    assert row["history_risk_code"] == "history_risk_clear"
    assert row["history_recommended_action"] == "allow_if_other_checks_pass"


def test_remove_rules_outrank_manual_rules_when_both_present(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        pass_rows=[_pass_row("ASIN-MIXED", commercial_note="Avoid | Exit-only")],
        scrape_rows=[_scrape_row("ASIN-MIXED", history_recommendation="FAIL", phase_recommendation="AVOID")],
        backtest_rows=[
            _backtest_row(
                "ASIN-MIXED",
                recommendation="Avoid",
                failure_event_count="190",
                time_normal_sell_days="8",
                time_selloff_days="16",
            )
        ],
    )

    row = _row_for_asin(result.audit_df, "ASIN-MIXED")
    assert row["history_risk_code"] == "history_fail_phase_avoid"
    assert row["history_recommended_action"] == "remove_from_clean_pass"
    assert row["history_supporting_codes"] == (
        "history_fail_phase_avoid|exit_only_clean_pass|backtest_avoid_commercial_avoid_or_exit|"
        "failure_events_100_plus|selloff_days_exceed_normal_days"
    )


def test_output_has_no_unclassified_rows(tmp_path: Path) -> None:
    result = _run_audit(
        tmp_path,
        pass_rows=[
            _pass_row("ASIN-R1"),
            _pass_row("ASIN-R2", commercial_note="Avoid"),
            _pass_row("ASIN-R3", commercial_note="Exit-only"),
            _pass_row("ASIN-R4"),
            _pass_row("ASIN-R5"),
            _pass_row("ASIN-R6"),
        ],
        scrape_rows=[
            _scrape_row("ASIN-R1", history_recommendation="FAIL", phase_recommendation="AVOID"),
            _scrape_row("ASIN-R2", opportunity_recommendation="Avoid"),
            _scrape_row("ASIN-R3", opportunity_recommendation="Exit-only"),
            _scrape_row("ASIN-R4"),
            _scrape_row("ASIN-R5"),
            _scrape_row("ASIN-R6"),
        ],
        backtest_rows=[
            _backtest_row("ASIN-R1"),
            _backtest_row("ASIN-R2", recommendation="Avoid"),
            _backtest_row("ASIN-R3", recommendation="Exit-only"),
            _backtest_row("ASIN-R4", failure_event_count="150"),
            _backtest_row("ASIN-R5", time_normal_sell_days="4", time_selloff_days="8"),
            _backtest_row("ASIN-R6"),
        ],
    )

    assert result.report["unclassified_rows"] == 0
    assert all(code in VALID_HISTORY_RISK_CODES for code in result.audit_df["history_risk_code"])
    assert all(str(value).strip() != "" for value in result.audit_df["history_recommended_action"])
