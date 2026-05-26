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

from scripts.one_off.F021_build_new_product_review_fail_triage import (
    OUTPUT_COLUMNS,
    build_new_product_review_fail_triage,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _pass_row(
    candidate_id: str,
    asin: str,
    supplier_sku: str = "SKU-1",
    uk_review_code: str = "uk_reviews_10_plus",
    uk_review_recommended_action: str = "allow_if_other_checks_pass",
    uk_review_supporting_codes: str = "uk_reviews_10_plus",
    uk_review_evidence_source: str = "f_live_price_file_pass_or_near_miss_review_latest.csv",
    seller_history_code: str = "seller_history_clear",
    seller_history_recommended_action: str = "allow_if_other_checks_pass",
    seller_history_supporting_codes: str = "seller_history_clear",
    seller_history_evidence_source: str = "f_live_price_file_pass_or_near_miss_review_latest.csv",
    seller_history_new_30: str = "2",
    seller_history_new_90: str = "2",
    seller_history_new_180: str = "2",
    seller_history_dashboard_yes_or_no: str = "",
    seller_history_dashboard_delivery_classification: str = "",
    seller_history_dashboard_separate_delivery_required: str = "",
) -> dict[str, str]:
    return {
        "observed_utc": "2026-04-23T09:00:00Z",
        "candidate_id": candidate_id,
        "supplier_sku": supplier_sku,
        "asin": asin,
        "review_batch_id": "pass_batch_001",
        "screening_status_reason": "PASS",
        "expected_units_next_30d": "80",
        "watch_data_summary": "history_recommendation=PASS|demand_confidence_note=normal",
        "uk_review_code": uk_review_code,
        "uk_review_recommended_action": uk_review_recommended_action,
        "uk_review_supporting_codes": uk_review_supporting_codes,
        "uk_review_evidence_source": uk_review_evidence_source,
        "seller_history_code": seller_history_code,
        "seller_history_recommended_action": seller_history_recommended_action,
        "seller_history_supporting_codes": seller_history_supporting_codes,
        "seller_history_evidence_source": seller_history_evidence_source,
        "seller_history_new_30": seller_history_new_30,
        "seller_history_new_90": seller_history_new_90,
        "seller_history_new_180": seller_history_new_180,
        "seller_history_dashboard_yes_or_no": seller_history_dashboard_yes_or_no,
        "seller_history_dashboard_delivery_classification": seller_history_dashboard_delivery_classification,
        "seller_history_dashboard_separate_delivery_required": seller_history_dashboard_separate_delivery_required,
    }


def _event_fail(
    candidate_id: str,
    asin: str,
    event_id: str = "evt-fail",
    active_supplier_id: str = "",
    active_run_id: str = "",
) -> dict[str, str]:
    return {
        "event_utc": "2026-04-23T10:00:00Z",
        "event_id": event_id,
        "active_supplier_id": active_supplier_id,
        "active_run_id": active_run_id,
        "review_pack_type": "passes",
        "candidate_id": candidate_id,
        "asin_raw": asin,
        "asin_padded": asin,
        "review_decision": "fail",
    }


def _demand_row(
    candidate_id: str,
    asin: str,
    code: str,
    action: str,
    supplier_sku: str = "SKU-1",
) -> dict[str, str]:
    return {
        "asin": asin,
        "candidate_id": candidate_id,
        "supplier_sku": supplier_sku,
        "review_pack_type": "passes",
        "amazon_demand_signal": "",
        "amazon_demand_floor": "0",
        "amazon_demand_ceiling": "49",
        "bbp_units": "813",
        "expected_units_next_30d": "813",
        "demand_conflict_code": code,
        "uk_reviews": "3",
        "variant_reviews": "469",
        "confidence_adjustment": "",
        "recommended_action": action,
        "evidence_source": f"audit:{code}",
    }


def _history_row(
    candidate_id: str,
    asin: str,
    code: str,
    action: str,
    supplier_sku: str = "SKU-1",
) -> dict[str, str]:
    return {
        "asin": asin,
        "candidate_id": candidate_id,
        "supplier_sku": supplier_sku,
        "review_pack_type": "passes",
        "history_risk_code": code,
        "history_recommended_action": action,
        "history_supporting_codes": code,
        "history_recommendation": "",
        "phase_recommendation": "",
        "backtest_recommendation": "",
        "commercial_label": "",
        "failure_event_count": "",
        "time_normal_sell_days": "",
        "time_selloff_days": "",
        "expected_units_next_30d": "80",
        "expected_profit_next_30d_gbp": "55",
        "evidence_source": f"history:{code}",
    }


def _scrape_row(candidate_id: str, asin: str, historical_uk_reviews: str) -> dict[str, str]:
    return {
        "observed_utc": "2026-04-23T10:30:00Z",
        "candidate_id": candidate_id,
        "supplier_sku": "SKU-1",
        "asin": asin,
        "historical_uk_reviews": historical_uk_reviews,
    }


def _run_triage(
    tmp_path: Path,
    *,
    pass_rows: list[dict[str, str]],
    demand_rows: list[dict[str, str]],
    history_rows: list[dict[str, str]],
    review_events_rows: list[dict[str, str]] | None = None,
    near_miss_rows: list[dict[str, str]] | None = None,
    scrape_rows: list[dict[str, str]] | None = None,
    review_handoffs_root: Path | None = None,
):
    pass_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
    near_miss_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_near_miss_review_latest.csv"
    review_events_path = tmp_path / "out" / "systems" / "F" / "inbox" / "feeder_review_events.csv"
    scrape_evidence_path = tmp_path / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv"
    demand_audit_path = tmp_path / "out" / "analysis_reports" / "f_demand_range_bbp_conflict_audit_latest.csv"
    history_audit_path = tmp_path / "out" / "analysis_reports" / "f_history_risk_pass_conflict_audit_latest.csv"
    output_path = tmp_path / "out" / "analysis_reports" / "f_new_product_review_fail_triage_latest.csv"

    _write_csv(pass_path, pass_rows)
    _write_csv(near_miss_path, near_miss_rows or [])
    _write_csv(review_events_path, review_events_rows or [])
    _write_csv(scrape_evidence_path, scrape_rows or [])
    _write_csv(demand_audit_path, demand_rows)
    _write_csv(history_audit_path, history_rows)

    return build_new_product_review_fail_triage(
        pass_path=pass_path,
        near_miss_path=near_miss_path,
        review_events_path=review_events_path,
        scrape_evidence_path=scrape_evidence_path,
        demand_audit_path=demand_audit_path,
        history_audit_path=history_audit_path,
        output_path=output_path,
        review_handoffs_root=review_handoffs_root
        or tmp_path / "out" / "systems" / "F" / "price_list_manager" / "review_handoffs",
        observed_utc="2026-04-23T11:00:00Z",
    )


def _by_candidate(df: pd.DataFrame) -> dict[str, dict[str, str]]:
    return {row["candidate_id"]: row for row in df.to_dict("records")}


def test_manual_fail_memory_remains_primary_when_uk_review_evidence_exists(tmp_path: Path) -> None:
    result = _run_triage(
        tmp_path,
        pass_rows=[
            _pass_row(
                "cand-memory",
                "ASIN-MEM",
                uk_review_code="uk_reviews_lt3",
                uk_review_recommended_action="remove_from_clean_pass",
                uk_review_supporting_codes="uk_reviews_lt3",
            )
        ],
        demand_rows=[],
        history_rows=[_history_row("cand-memory", "ASIN-MEM", "history_fail_phase_avoid", "remove_from_clean_pass")],
        review_events_rows=[_event_fail("cand-memory", "ASIN-MEM")],
    )

    row = _by_candidate(result.triage_df)["cand-memory"]
    assert row["fail_type"] == "type_2_known_policy_or_memory"
    assert row["fail_reason_code"] == "review_memory_fail_decision"
    assert row["history_risk_code"] == "history_fail_phase_avoid"
    assert row["history_recommended_action"] == "remove_from_clean_pass"
    assert row["uk_review_code"] == "uk_reviews_lt3"
    assert row["uk_review_recommended_action"] == "remove_from_clean_pass"


def test_review_event_handoff_pass_rows_are_loaded(tmp_path: Path) -> None:
    supplier_id = "dhb"
    run_id = "fpm_dhb_20260507T055804Z"
    handoff_root = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "review_handoffs"
    handoff_dir = handoff_root / supplier_id / run_id
    handoff_pass_row = _pass_row("cand-handoff", "ASIN-HANDOFF", supplier_sku="SKU-HANDOFF")
    handoff_pass_row.update({"active_supplier_id": supplier_id, "active_run_id": run_id})
    _write_csv(handoff_dir / "f_live_price_file_pass_review_latest.csv", [handoff_pass_row])
    _write_csv(handoff_dir / "f_live_price_file_near_miss_review_latest.csv", [])

    result = _run_triage(
        tmp_path,
        pass_rows=[],
        demand_rows=[],
        history_rows=[],
        review_events_rows=[
            _event_fail(
                "cand-handoff",
                "ASIN-HANDOFF",
                event_id="evt-handoff-fail",
                active_supplier_id=supplier_id,
                active_run_id=run_id,
            )
        ],
        review_handoffs_root=handoff_root,
    )

    row = _by_candidate(result.triage_df)["cand-handoff"]
    assert row["fail_type"] == "type_2_known_policy_or_memory"
    assert row["fail_reason_code"] == "review_memory_fail_decision"
    assert row["evidence_source"] == "feeder_review_events:evt-handoff-fail"
    assert result.report["review_handoff_pass_input_rows"] == 1
    assert result.report["pass_input_rows"] == 1


def test_uk_reviews_lt3_appears_in_uk_review_columns(tmp_path: Path) -> None:
    result = _run_triage(
        tmp_path,
        pass_rows=[
            _pass_row(
                "cand-uk-lt3",
                "ASIN-UK-LT3",
                uk_review_code="uk_reviews_lt3",
                uk_review_recommended_action="remove_from_clean_pass",
                uk_review_supporting_codes="uk_reviews_lt3",
            )
        ],
        demand_rows=[],
        history_rows=[],
    )

    row = _by_candidate(result.triage_df)["cand-uk-lt3"]
    assert row["fail_type"] == "type_1_data_or_calc"
    assert row["fail_reason_code"] == "uk_review_uk_reviews_lt3"
    assert row["uk_review_code"] == "uk_reviews_lt3"
    assert row["uk_review_recommended_action"] == "remove_from_clean_pass"
    assert row["uk_review_supporting_codes"] == "uk_reviews_lt3"


def test_likely_dashboard_delivery_signal_is_carried_into_triage_rows(tmp_path: Path) -> None:
    result = _run_triage(
        tmp_path,
        pass_rows=[
            _pass_row(
                "cand-uk-likely",
                "ASIN-UK-LIKELY",
                uk_review_code="uk_reviews_lt3",
                uk_review_recommended_action="remove_from_clean_pass",
                uk_review_supporting_codes="uk_reviews_lt3",
                seller_history_dashboard_yes_or_no="LIKELY",
                seller_history_dashboard_delivery_classification="LIKELY_SELLABLE_HAZMAT_SEPARATE_DELIVERY",
                seller_history_dashboard_separate_delivery_required="1",
            )
        ],
        demand_rows=[],
        history_rows=[],
    )

    row = _by_candidate(result.triage_df)["cand-uk-likely"]
    assert row["seller_history_dashboard_yes_or_no"] == "LIKELY"
    assert row["seller_history_dashboard_delivery_classification"] == "LIKELY_SELLABLE_HAZMAT_SEPARATE_DELIVERY"
    assert row["seller_history_dashboard_separate_delivery_required"] == "1"


def test_uk_reviews_3_to_5_appears_in_uk_review_columns(tmp_path: Path) -> None:
    result = _run_triage(
        tmp_path,
        pass_rows=[
            _pass_row(
                "cand-uk-3to5",
                "ASIN-UK-3TO5",
                uk_review_code="uk_reviews_3_to_5",
                uk_review_recommended_action="manual_review",
                uk_review_supporting_codes="uk_reviews_3_to_5",
            )
        ],
        demand_rows=[],
        history_rows=[],
    )

    row = _by_candidate(result.triage_df)["cand-uk-3to5"]
    assert row["fail_type"] == "type_1_data_or_calc"
    assert row["fail_reason_code"] == "uk_review_uk_reviews_3_to_5_manual_review"
    assert row["uk_review_code"] == "uk_reviews_3_to_5"
    assert row["uk_review_recommended_action"] == "manual_review"
    assert row["uk_review_supporting_codes"] == "uk_reviews_3_to_5"


def test_uk_reviews_6_to_9_supporting_evidence_does_not_create_fail_by_itself(tmp_path: Path) -> None:
    result = _run_triage(
        tmp_path,
        pass_rows=[
            _pass_row(
                "cand-uk-supporting",
                "ASIN-UK-SUPPORTING",
                uk_review_code="",
                uk_review_recommended_action="",
                uk_review_supporting_codes="",
                uk_review_evidence_source="",
            )
        ],
        demand_rows=[],
        history_rows=[],
        scrape_rows=[_scrape_row("cand-uk-supporting", "ASIN-UK-SUPPORTING", "7")],
    )

    assert result.triage_df.empty
    assert list(result.triage_df.columns) == OUTPUT_COLUMNS


def test_amazon_only_single_seller_appears_in_seller_history_columns(tmp_path: Path) -> None:
    result = _run_triage(
        tmp_path,
        pass_rows=[
            _pass_row(
                "cand-seller-low",
                "ASIN-SELLER-LOW",
                seller_history_code="amazon_only_single_seller",
                seller_history_recommended_action="remove_from_clean_pass",
                seller_history_supporting_codes="amazon_only_single_seller",
                seller_history_new_30="1",
                seller_history_new_90="1",
                seller_history_new_180="1",
            )
        ],
        demand_rows=[],
        history_rows=[],
    )

    row = _by_candidate(result.triage_df)["cand-seller-low"]
    assert row["fail_type"] == "type_1_data_or_calc"
    assert row["fail_reason_code"] == "seller_history_amazon_only_single_seller"
    assert row["seller_history_code"] == "amazon_only_single_seller"
    assert row["seller_history_recommended_action"] == "remove_from_clean_pass"
    assert row["seller_history_new_30"] == "1"
    assert row["seller_history_new_90"] == "1"
    assert row["seller_history_new_180"] == "1"


def test_single_fba_seller_amazon_absent_does_not_create_fail_by_itself(tmp_path: Path) -> None:
    result = _run_triage(
        tmp_path,
        pass_rows=[
            _pass_row(
                "cand-seller-fba",
                "ASIN-SELLER-FBA",
                seller_history_code="single_fba_seller_amazon_absent",
                seller_history_recommended_action="allow_if_other_checks_pass",
                seller_history_new_30="1",
                seller_history_new_90="1",
                seller_history_new_180="1",
            )
        ],
        demand_rows=[],
        history_rows=[],
    )

    assert result.triage_df.empty
    assert list(result.triage_df.columns) == OUTPUT_COLUMNS


def test_dashboard_no_low_seller_count_appears_in_seller_history_columns(tmp_path: Path) -> None:
    result = _run_triage(
        tmp_path,
        pass_rows=[
            _pass_row(
                "cand-dashboard-low",
                "ASIN-DASHBOARD-LOW",
                seller_history_code="dashboard_no_low_seller_count",
                seller_history_recommended_action="remove_from_clean_pass",
                seller_history_supporting_codes="dashboard_no_low_seller_count",
                seller_history_new_30="1",
                seller_history_new_90="1",
                seller_history_new_180="1",
                seller_history_dashboard_yes_or_no="NO",
            )
        ],
        demand_rows=[],
        history_rows=[],
    )

    row = _by_candidate(result.triage_df)["cand-dashboard-low"]
    assert row["fail_type"] == "type_1_data_or_calc"
    assert row["fail_reason_code"] == "seller_history_dashboard_no_low_seller_count"
    assert row["seller_history_code"] == "dashboard_no_low_seller_count"
    assert row["seller_history_recommended_action"] == "remove_from_clean_pass"
    assert row["seller_history_dashboard_yes_or_no"] == "NO"


def test_low_sales_capital_idle_risk_near_miss_is_type_1(tmp_path: Path) -> None:
    result = _run_triage(
        tmp_path,
        pass_rows=[],
        demand_rows=[],
        history_rows=[],
        near_miss_rows=[
            {
                "observed_utc": "2026-04-23T09:00:00Z",
                "candidate_id": "cand-low-sales",
                "supplier_sku": "SKU-LOW-SALES",
                "asin": "ASIN-LOW-SALES",
                "review_batch_id": "near_miss_batch_001",
                "near_miss_type": "low_sales_capital_idle_risk",
                "reviewability_state": "remove_from_clean_pass",
                "screening_fail_code": "LOW_SALES_CAPITAL_IDLE_RISK",
                "expected_units_next_30d": "2",
            }
        ],
    )

    row = _by_candidate(result.triage_df)["cand-low-sales"]
    assert row["fail_type"] == "type_1_data_or_calc"
    assert row["fail_reason_code"] == "screening_low_sales_capital_idle_risk"
    assert row["review_pack_type"] == "near_misses"


def test_dashboard_no_multi_seller_count_is_supporting_only(tmp_path: Path) -> None:
    result = _run_triage(
        tmp_path,
        pass_rows=[
            _pass_row(
                "cand-dashboard-multi",
                "ASIN-DASHBOARD-MULTI",
                seller_history_code="dashboard_no_multi_seller_count",
                seller_history_recommended_action="allow_if_other_checks_pass",
                seller_history_supporting_codes="dashboard_no_multi_seller_count",
                seller_history_new_30="3",
                seller_history_new_90="3",
                seller_history_new_180="3",
                seller_history_dashboard_yes_or_no="NO",
            )
        ],
        demand_rows=[],
        history_rows=[],
    )

    assert "cand-dashboard-multi" not in _by_candidate(result.triage_df)


def test_single_seller_owner_unclear_appears_in_seller_history_columns(tmp_path: Path) -> None:
    result = _run_triage(
        tmp_path,
        pass_rows=[
            _pass_row(
                "cand-seller-unclear",
                "ASIN-SELLER-UNCLEAR",
                seller_history_code="single_seller_owner_unclear",
                seller_history_recommended_action="manual_review",
                seller_history_new_30="1",
                seller_history_new_90="1",
                seller_history_new_180="1",
            )
        ],
        demand_rows=[],
        history_rows=[],
    )

    row = _by_candidate(result.triage_df)["cand-seller-unclear"]
    assert row["fail_type"] == "type_1_data_or_calc"
    assert row["fail_reason_code"] == "seller_history_single_seller_owner_unclear_manual_review"
    assert row["seller_history_code"] == "single_seller_owner_unclear"
    assert row["seller_history_recommended_action"] == "manual_review"


def test_brand_owner_top_seller_appears_as_type_1_rule(tmp_path: Path) -> None:
    result = _run_triage(
        tmp_path,
        pass_rows=[
            _pass_row(
                "cand-brand-owner-top",
                "ASIN-BRAND-OWNER-TOP",
                seller_history_code="brand_owner_top_seller",
                seller_history_recommended_action="remove_from_clean_pass",
                seller_history_new_30="9",
                seller_history_new_90="8",
                seller_history_new_180="8",
            )
        ],
        demand_rows=[],
        history_rows=[],
    )

    row = _by_candidate(result.triage_df)["cand-brand-owner-top"]
    assert row["fail_type"] == "type_1_data_or_calc"
    assert row["fail_reason_code"] == "seller_history_brand_owner_top_seller"
    assert row["seller_history_code"] == "brand_owner_top_seller"
    assert row["seller_history_recommended_action"] == "remove_from_clean_pass"


def test_seller_history_clear_does_not_create_fail_by_itself(tmp_path: Path) -> None:
    result = _run_triage(
        tmp_path,
        pass_rows=[
            _pass_row(
                "cand-seller-clear",
                "ASIN-SELLER-CLEAR",
                seller_history_code="seller_history_clear",
                seller_history_recommended_action="allow_if_other_checks_pass",
                seller_history_new_30="2",
                seller_history_new_90="2",
                seller_history_new_180="2",
            )
        ],
        demand_rows=[],
        history_rows=[],
    )

    assert result.triage_df.empty
    assert list(result.triage_df.columns) == OUTPUT_COLUMNS


def test_remove_from_clean_pass_history_risk_appears_in_history_columns(tmp_path: Path) -> None:
    result = _run_triage(
        tmp_path,
        pass_rows=[_pass_row("cand-history-remove", "ASIN-H-REMOVE")],
        demand_rows=[],
        history_rows=[
            _history_row(
                "cand-history-remove",
                "ASIN-H-REMOVE",
                "backtest_avoid_commercial_avoid_or_exit",
                "remove_from_clean_pass",
            )
        ],
    )

    row = _by_candidate(result.triage_df)["cand-history-remove"]
    assert row["fail_type"] == "type_1_data_or_calc"
    assert row["fail_reason_code"] == "history_risk_backtest_avoid_commercial_avoid_or_exit"
    assert row["history_risk_code"] == "backtest_avoid_commercial_avoid_or_exit"
    assert row["history_recommended_action"] == "remove_from_clean_pass"


def test_manual_review_history_risk_appears_in_history_columns(tmp_path: Path) -> None:
    result = _run_triage(
        tmp_path,
        pass_rows=[_pass_row("cand-history-manual", "ASIN-H-MANUAL")],
        demand_rows=[],
        history_rows=[_history_row("cand-history-manual", "ASIN-H-MANUAL", "failure_events_100_plus", "manual_review")],
    )

    row = _by_candidate(result.triage_df)["cand-history-manual"]
    assert row["fail_type"] == "type_1_data_or_calc"
    assert row["fail_reason_code"] == "history_risk_failure_events_100_plus_manual_review"
    assert row["history_risk_code"] == "failure_events_100_plus"
    assert row["history_recommended_action"] == "manual_review"


def test_history_risk_clear_does_not_create_fail_by_itself(tmp_path: Path) -> None:
    result = _run_triage(
        tmp_path,
        pass_rows=[_pass_row("cand-history-clear", "ASIN-H-CLEAR")],
        demand_rows=[],
        history_rows=[_history_row("cand-history-clear", "ASIN-H-CLEAR", "history_risk_clear", "allow_if_other_checks_pass")],
    )

    assert result.triage_df.empty
    assert list(result.triage_df.columns) == OUTPUT_COLUMNS


def test_existing_demand_columns_and_behavior_still_work(tmp_path: Path) -> None:
    result = _run_triage(
        tmp_path,
        pass_rows=[_pass_row("cand-demand", "ASIN-DEMAND")],
        demand_rows=[_demand_row("cand-demand", "ASIN-DEMAND", "amazon_blank_bbp_high", "remove_from_clean_pass")],
        history_rows=[],
    )

    row = _by_candidate(result.triage_df)["cand-demand"]
    assert row["fail_type"] == "type_1_data_or_calc"
    assert row["fail_reason_code"] == "demand_amazon_blank_bbp_high"
    assert row["demand_conflict_code"] == "amazon_blank_bbp_high"
    assert row["demand_recommended_action"] == "remove_from_clean_pass"
    assert row["history_risk_code"] == ""


def test_no_unclassified_rows(tmp_path: Path) -> None:
    result = _run_triage(
        tmp_path,
        pass_rows=[
            _pass_row("cand-memory", "ASIN-MEM"),
            _pass_row("cand-history-remove", "ASIN-H-REMOVE"),
            _pass_row("cand-history-manual", "ASIN-H-MANUAL"),
            _pass_row("cand-demand", "ASIN-DEMAND"),
        ],
        demand_rows=[_demand_row("cand-demand", "ASIN-DEMAND", "amazon_50_bbp_warn", "manual_review")],
        history_rows=[
            _history_row("cand-memory", "ASIN-MEM", "history_fail_phase_avoid", "remove_from_clean_pass"),
            _history_row(
                "cand-history-remove",
                "ASIN-H-REMOVE",
                "backtest_avoid_commercial_avoid_or_exit",
                "remove_from_clean_pass",
            ),
            _history_row("cand-history-manual", "ASIN-H-MANUAL", "selloff_days_exceed_normal_days", "manual_review"),
        ],
        review_events_rows=[_event_fail("cand-memory", "ASIN-MEM")],
    )

    assert result.report["unclassified_rows"] == 0
    assert all(str(value).strip() != "" for value in result.triage_df["fail_type"])
    assert all(str(value).strip() != "" for value in result.triage_df["fail_reason_code"])
