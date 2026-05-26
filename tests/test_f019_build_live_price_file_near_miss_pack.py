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

from scripts.one_off.F019_build_live_price_file_near_miss_pack import build_live_price_file_near_miss_pack
from scripts.core.storage import read_review_pack_dataframe, read_review_summary_dataframe


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _metric(summary_df: pd.DataFrame, metric: str) -> str:
    rows = summary_df.loc[summary_df["metric"] == metric]
    if rows.empty:
        return ""
    return str(rows.iloc[0]["value"])


def _records_by_asin(df: pd.DataFrame) -> dict[str, dict[str, str]]:
    return {str(row["asin"]): row for row in df.fillna("").to_dict("records")}


def _run_demand_pack(
    tmp_path: Path,
    cases: list[dict[str, str]],
    review_event_rows: list[dict[str, str]] | None = None,
    profit_audit_rows: list[dict[str, str]] | None = None,
    page_evidence_backfill_rows: list[dict[str, str]] | None = None,
):
    baseline_path = tmp_path / "baseline.csv"
    row_state_path = tmp_path / "row_state.csv"
    first_checks_path = tmp_path / "first_checks.csv"
    scrape_path = tmp_path / "scrape.csv"
    backtest_path = tmp_path / "backtest.csv"
    profit_audit_path = tmp_path / "profit_audit.csv"
    page_evidence_backfill_path = tmp_path / "page_evidence_backfill_results.csv"
    review_events_path = tmp_path / "review_events.csv"
    supplier_inbox_dir = tmp_path / "suppliers"
    output_dir = tmp_path / "analysis"

    row_state_rows: list[dict[str, str]] = []
    first_check_rows: list[dict[str, str]] = []
    scrape_rows: list[dict[str, str]] = []
    backtest_rows: list[dict[str, str]] = []
    supplier_rows: list[dict[str, str]] = []
    for idx, case in enumerate(cases, start=1):
        asin = case["asin"]
        candidate_id = case.get("candidate_id", f"C-DEMAND-{idx}")
        supplier_sku = case.get("supplier_sku", f"SKU-DEMAND-{idx}")
        expected_units = case.get("expected_units", case.get("bbp_units", ""))
        row_state_rows.append(
            {
                "supplier_id": "stocklist_supplier",
                "candidate_id": candidate_id,
                "supplier_sku": supplier_sku,
                "asin": asin,
                "row_status": case.get("row_status", "pass"),
                "status_reason": case.get("status_reason", "PASS"),
                "fail_code": "",
                "last_stage": "webscrape",
            }
        )
        first_check_rows.append(
            {
                "candidate_id": candidate_id,
                "supplier_sku": supplier_sku,
                "asin": asin,
                "title": case.get("amazon_title", f"Demand Case {idx}"),
                "brand": case.get("amazon_brand", "DemandBrand"),
                "main_rank": case.get("main_rank", "1200"),
                "point_score": case.get("point_score", "4.00"),
                "pf": "PASS",
                "status_reason": case.get("first_check_status_reason", case.get("status_reason", "PASS")),
                "bsr_recent_avg": case.get("bsr_recent_avg", ""),
            }
        )
        scrape_rows.append(
            {
                "observed_utc": "2026-04-22T15:00:00Z",
                "candidate_id": candidate_id,
                "supplier_sku": supplier_sku,
                "asin": asin,
                "title": case.get("amazon_title", f"Demand Case {idx}"),
                "catalog_match_scorecard": case.get("catalog_match_scorecard", ""),
                "status_reason": case.get("scrape_status_reason", case.get("status_reason", "PASS")),
                "monthly_sold": case.get("monthly_sold", ""),
                "amazon_bought_floor": case.get("amazon_bought_floor", ""),
                "bbp_sales_replay_demand_basis_units": case.get("bbp_units", ""),
                "bbp_dashboard_yes_or_no": case.get("bbp_dashboard_yes_or_no", ""),
                "bbp_dashboard_delivery_classification": case.get("bbp_dashboard_delivery_classification", ""),
                "bbp_dashboard_separate_delivery_required": case.get(
                    "bbp_dashboard_separate_delivery_required", ""
                ),
                "estimated_monthly_profit": case.get("estimated_monthly_profit", "60"),
                "profit_per_unit_30d": case.get("profit_per_unit_30d", "6"),
                "avg_30_day_price": case.get("avg_30_day_price", "14"),
                "break_even": case.get("break_even", "10"),
                "chart_phase_daily_series": case.get("chart_phase_daily_series", ""),
                "chart_raw_amazon_daily_series": case.get("chart_raw_amazon_daily_series", ""),
                "opportunity_recommendation": case.get("opportunity_recommendation", "PASS"),
                "history_recommendation": case.get("history_recommendation", "PASS"),
                "phase_recommendation": case.get("phase_recommendation", "PASS"),
                "demand_confidence_note": "strong_signal",
                "historical_uk_reviews": case.get("historical_uk_reviews", "10"),
                "variant_reviews": case.get("variant_reviews", "100"),
                "price_hist_new_30": case.get("price_hist_new_30", ""),
                "price_hist_new_90": case.get("price_hist_new_90", ""),
                "price_hist_new_180": case.get("price_hist_new_180", ""),
                "price_hist_amazon_30": case.get("price_hist_amazon_30", ""),
                "price_hist_amazon_90": case.get("price_hist_amazon_90", ""),
                "price_hist_amazon_180": case.get("price_hist_amazon_180", ""),
                "price_hist_fba_30": case.get("price_hist_fba_30", ""),
                "price_hist_fba_90": case.get("price_hist_fba_90", ""),
                "price_hist_fba_180": case.get("price_hist_fba_180", ""),
                "price_hist_buy_box_30": case.get("price_hist_buy_box_30", ""),
                "price_hist_buy_box_90": case.get("price_hist_buy_box_90", ""),
                "price_hist_buy_box_180": case.get("price_hist_buy_box_180", ""),
                "bbp_top_seller_names": case.get("bbp_top_seller_names", ""),
                "bbp_brand_match_seller": case.get("bbp_brand_match_seller", ""),
                "bbp_brand_match_score": case.get("bbp_brand_match_score", ""),
                "bbp_brand_match_flag": case.get("bbp_brand_match_flag", ""),
                "bbp_seller_rank_1_name": case.get("bbp_seller_rank_1_name", ""),
                "bbp_seller_rank_1_brand_match_flag": case.get("bbp_seller_rank_1_brand_match_flag", ""),
                "amazon_buybox_seller_name": case.get("amazon_buybox_seller_name", ""),
                "amazon_buybox_brand_match_score": case.get("amazon_buybox_brand_match_score", ""),
                "amazon_buybox_brand_match_flag": case.get("amazon_buybox_brand_match_flag", ""),
            }
        )
        backtest_rows.append(
            {
                "seller_sku": supplier_sku,
                "asin": asin,
                "decision_state": "pass",
                "decision_confidence": "high",
                "stability_state": "stable",
                "expected_units_next_30d": expected_units,
                "expected_profit_next_30d_gbp": case.get("expected_profit_next_30d_gbp", "60"),
                "recommendation": case.get("backtest_recommendation", "Managed fit"),
                "decision_reason_codes": case.get("decision_reason_codes", "meets_profit_floor"),
                "failure_event_count": case.get("failure_event_count", ""),
                "time_normal_sell_days": case.get("time_normal_sell_days", ""),
                "time_selloff_days": case.get("time_selloff_days", ""),
            }
        )
        supplier_rows.append(
            {
                "supplier_id": "stocklist_supplier",
                "supplier_sku": supplier_sku,
                "supplier_title": case.get("supplier_title", f"Demand Case {idx}"),
                "brand": case.get("supplier_brand", "DemandBrand"),
                "unit_cost": case.get("unit_cost", "10"),
                "currency": "GBP",
            }
        )

    _write_csv(baseline_path, [{"active_supplier_id": "stocklist_supplier", "active_run_id": "run-1"}])
    _write_csv(row_state_path, row_state_rows)
    _write_csv(first_checks_path, first_check_rows)
    _write_csv(scrape_path, scrape_rows)
    _write_csv(backtest_path, backtest_rows)
    if review_event_rows is not None:
        _write_csv(review_events_path, review_event_rows)
    _write_csv(profit_audit_path, profit_audit_rows or [])
    if page_evidence_backfill_rows is not None:
        _write_csv(page_evidence_backfill_path, page_evidence_backfill_rows)
    _write_csv(supplier_inbox_dir / "stocklist_supplier" / "canonical_current.csv", supplier_rows)

    return build_live_price_file_near_miss_pack(
        baseline_path=baseline_path,
        row_state_path=row_state_path,
        first_checks_path=first_checks_path,
        scrape_evidence_path=scrape_path,
        page_evidence_backfill_results_path=(
            page_evidence_backfill_path if page_evidence_backfill_rows is not None else None
        ),
        backtest_summary_path=backtest_path,
        profit_audit_path=profit_audit_path,
        review_events_path=review_events_path if review_event_rows is not None else None,
        supplier_inbox_dir=supplier_inbox_dir,
        output_dir=output_dir,
        observed_utc="2026-04-22T15:00:00Z",
        review_batch_size=20,
    )


def test_page_evidence_backfill_fills_missing_amazon_description(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "B082NMTZC2",
                "candidate_id": "cand-page-evidence",
                "supplier_sku": "1144846",
                "supplier_title": "JVC Boomblaster DAB+ Black",
                "amazon_title": "JVC RV-NB300DAB Boombox DAB Radio Bluetooth USB CD Speaker System Black",
                "expected_units": "20",
                "bbp_units": "20",
                "expected_profit_next_30d_gbp": "80",
            }
        ],
        page_evidence_backfill_rows=[
            {
                "observed_utc": "2026-05-20T16:00:00Z",
                "backfill_id": "f036_page_evidence",
                "asin": "B082NMTZC2",
                "resolved_asin": "B082NMTZC2",
                "supplier_id": "stocklist_supplier",
                "supplier_sku": "1144846",
                "backfill_status": "succeeded",
                "page_evidence_captured_flag": "1",
                "product_detail_text": "Product details block from Amazon.",
                "product_description": "Backfilled Amazon description used by AI review.",
                "product_feature_bullets": "Backfilled feature bullets.",
            }
        ],
    )

    row = _records_by_asin(result.pass_df)["B082NMTZC2"]
    assert row["amazon_product_detail_text"] == "Product details block from Amazon."
    assert row["amazon_product_description"] == "Backfilled Amazon description used by AI review."
    assert row["amazon_feature_bullets"] == "Backfilled feature bullets."
    assert _metric(result.summary_df, "page_evidence_backfill_source_rows") == "1"
    assert _metric(result.summary_df, "page_evidence_backfill_usable_rows") == "1"
    assert _metric(result.summary_df, "page_evidence_backfill_used_rows") == "1"


def test_latest_manual_fail_memory_routes_pass_out_of_clean_pass(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "B007SJSX3M",
                "candidate_id": "cand-plus-plus",
                "supplier_sku": "1167948",
                "expected_units": "52",
                "bbp_units": "52",
                "monthly_sold": "50+",
                "expected_profit_next_30d_gbp": "42.50",
            }
        ],
        review_event_rows=[
            {
                "event_utc": "2026-04-29T11:00:00Z",
                "event_id": "event-fail-plus-plus",
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-plus-plus",
                "supplier_sku": "1167948",
                "asin_raw": "B007SJSX3M",
                "asin_padded": "B007SJSX3M",
                "amazon_dp_url": "https://www.amazon.co.uk/dp/B007SJSX3M",
                "review_decision": "fail",
                "review_note": "Clearly being sold by the brand",
                "actor": "operator_ui",
                "source_reference": "o_ui_feeder_review",
            }
        ],
    )

    assert result.pass_df.empty
    near = _records_by_asin(result.near_miss_df)["B007SJSX3M"]
    assert near["near_miss_type"] == "review_memory_fail"
    assert near["reviewability_state"] == "known_fail"
    assert near["screening_fail_code"] == "REVIEW_MEMORY_FAIL"
    assert near["review_memory_event_id"] == "event-fail-plus-plus"
    assert near["review_memory_decision"] == "fail"
    assert near["review_memory_note"] == "Clearly being sold by the brand"
    assert _metric(result.summary_df, "review_memory_routed_remove_from_clean_pass_rows") == "1"


def test_f019_writes_review_pack_to_sql_snapshot_tables(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "B007SJSX3M",
                "candidate_id": "cand-sql",
                "supplier_sku": "1167948",
                "expected_units": "52",
                "bbp_units": "52",
                "monthly_sold": "50+",
                "expected_profit_next_30d_gbp": "42.50",
            }
        ],
    )

    latest_pass_df = read_review_pack_dataframe(tmp_path / "missing_pass.csv", pack_type="passes", dtype=str)
    snapshot_pass_df = read_review_pack_dataframe(
        tmp_path / "missing_pass.csv",
        pack_type="passes",
        snapshot_id="20260422T150000Z",
        dtype=str,
    )
    latest_summary_df = read_review_summary_dataframe(tmp_path / "missing_summary.csv", dtype=str)

    assert result.pass_latest_path.exists()
    assert latest_pass_df.iloc[0]["candidate_id"] == "cand-sql"
    assert snapshot_pass_df.iloc[0]["candidate_id"] == "cand-sql"
    assert _metric(latest_summary_df, "pass_review_rows") == "1"


def test_f019_preserves_existing_outputs_when_source_window_is_empty(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.csv"
    row_state_path = tmp_path / "row_state.csv"
    first_checks_path = tmp_path / "first_checks.csv"
    scrape_path = tmp_path / "scrape.csv"
    backtest_path = tmp_path / "backtest.csv"
    profit_audit_path = tmp_path / "profit_audit.csv"
    output_dir = tmp_path / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_csv(
        baseline_path,
        [{"active_supplier_id": "stocklist_supplier", "active_run_id": "old-run"}],
    )
    _write_csv(
        row_state_path,
        [
            {
                "run_id": "new-run",
                "supplier_id": "stocklist_supplier",
                "candidate_id": "cand-new",
                "supplier_sku": "SKU-NEW",
                "asin": "B000000001",
                "row_status": "pass",
            }
        ],
    )
    _write_csv(first_checks_path, [])
    _write_csv(scrape_path, [])
    _write_csv(backtest_path, [])
    _write_csv(profit_audit_path, [])
    _write_csv(
        output_dir / "f_live_price_file_pass_review_latest.csv",
        [{"candidate_id": "existing-pass", "asin": "B000PASS00"}],
    )
    _write_csv(
        output_dir / "f_live_price_file_near_miss_review_latest.csv",
        [{"candidate_id": "existing-near", "asin": "B000NEAR00"}],
    )

    result = build_live_price_file_near_miss_pack(
        baseline_path=baseline_path,
        row_state_path=row_state_path,
        first_checks_path=first_checks_path,
        scrape_evidence_path=scrape_path,
        backtest_summary_path=backtest_path,
        profit_audit_path=profit_audit_path,
        output_dir=output_dir,
        observed_utc="2026-05-19T13:15:00Z",
    )

    latest_pass = pd.read_csv(output_dir / "f_live_price_file_pass_review_latest.csv", dtype=str).fillna("")
    latest_near = pd.read_csv(output_dir / "f_live_price_file_near_miss_review_latest.csv", dtype=str).fillna("")

    assert result.report["status"] == "blocked_source_window_empty"
    assert result.report["row_state_source_rows"] == 1
    assert result.report["row_state_supplier_rows"] == 1
    assert result.report["row_state_window_rows"] == 0
    assert latest_pass.iloc[0]["candidate_id"] == "existing-pass"
    assert latest_near.iloc[0]["candidate_id"] == "existing-near"
    assert not result.pass_path.exists()
    assert _metric(result.summary_df, "f019_write_state") == "blocked_source_window_empty"


def test_latest_manual_pass_overrides_prior_fail_memory(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "B007SJSX3M",
                "candidate_id": "cand-plus-plus",
                "supplier_sku": "1167948",
                "expected_units": "52",
                "bbp_units": "52",
                "monthly_sold": "50+",
                "expected_profit_next_30d_gbp": "42.50",
            }
        ],
        review_event_rows=[
            {
                "event_utc": "2026-04-29T11:00:00Z",
                "event_id": "event-fail-plus-plus",
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-plus-plus",
                "supplier_sku": "1167948",
                "asin_raw": "B007SJSX3M",
                "asin_padded": "B007SJSX3M",
                "amazon_dp_url": "https://www.amazon.co.uk/dp/B007SJSX3M",
                "review_decision": "fail",
                "review_note": "old fail",
                "actor": "operator_ui",
                "source_reference": "o_ui_feeder_review",
            },
            {
                "event_utc": "2026-04-29T12:00:00Z",
                "event_id": "event-pass-plus-plus",
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-plus-plus",
                "supplier_sku": "1167948",
                "asin_raw": "B007SJSX3M",
                "asin_padded": "B007SJSX3M",
                "amazon_dp_url": "https://www.amazon.co.uk/dp/B007SJSX3M",
                "review_decision": "pass",
                "review_note": "latest decision allows row",
                "actor": "operator_ui",
                "source_reference": "o_ui_feeder_review",
            },
        ],
    )

    pass_row = _records_by_asin(result.pass_df)["B007SJSX3M"]
    assert pass_row["review_memory_event_id"] == "event-pass-plus-plus"
    assert pass_row["review_memory_decision"] == "pass"
    assert result.near_miss_df.empty
    assert _metric(result.summary_df, "review_memory_routed_remove_from_clean_pass_rows") == "0"


def test_f019_builds_pass_and_near_miss_review_packs(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.csv"
    row_state_path = tmp_path / "row_state.csv"
    first_checks_path = tmp_path / "first_checks.csv"
    scrape_path = tmp_path / "scrape.csv"
    backtest_path = tmp_path / "backtest.csv"
    output_dir = tmp_path / "analysis"
    supplier_inbox_dir = tmp_path / "suppliers"

    _write_csv(
        baseline_path,
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "stocklist_supplier_20260422T120000Z",
            }
        ],
    )

    _write_csv(
        row_state_path,
        [
            {
                "supplier_id": "stocklist_supplier",
                "candidate_id": "C1",
                "supplier_sku": "SKU1",
                "asin": "A1",
                "row_status": "pass",
                "status_reason": "PASS",
                "fail_code": "",
                "last_stage": "webscrape",
                "source_seen_at_utc": "2026-04-10T15:26:58Z",
            },
            {
                "supplier_id": "stocklist_supplier",
                "candidate_id": "C2",
                "supplier_sku": "SKU2",
                "asin": "A2",
                "row_status": "pass",
                "status_reason": "PASS",
                "fail_code": "",
                "last_stage": "webscrape",
            },
            {
                "supplier_id": "stocklist_supplier",
                "candidate_id": "C3",
                "supplier_sku": "SKU3",
                "asin": "A3",
                "row_status": "timeout",
                "status_reason": "RESCAN",
                "fail_code": "RESCAN",
                "last_stage": "retry",
            },
            {
                "supplier_id": "stocklist_supplier",
                "candidate_id": "C4",
                "supplier_sku": "SKU4",
                "asin": "A4",
                "row_status": "timeout",
                "status_reason": "ROIFAIL",
                "fail_code": "ROIFAIL",
                "last_stage": "roi_gate",
            },
            {
                "supplier_id": "stocklist_supplier",
                "candidate_id": "C5",
                "supplier_sku": "SKU5",
                "asin": "A5",
                "row_status": "timeout",
                "status_reason": "OVER50K",
                "fail_code": "OVER50K",
                "last_stage": "rank_gate",
            },
            {
                "supplier_id": "stocklist_supplier",
                "candidate_id": "C6__alt2_B000ALT6",
                "supplier_sku": "SKU6",
                "asin": "A6",
                "row_status": "timeout",
                "status_reason": "RESCAN",
                "fail_code": "RESCAN",
                "last_stage": "retry",
            },
        ],
    )

    _write_csv(
        first_checks_path,
        [
            {
                "candidate_id": "C1",
                "supplier_sku": "SKU1",
                "asin": "A1",
                "title": "Pass One",
                "brand": "Brand1",
                "main_rank": "1200",
                "point_score": "4.00",
                "pf": "PASS",
                "status_reason": "PASS",
            },
            {
                "candidate_id": "C2",
                "supplier_sku": "SKU2",
                "asin": "A2",
                "title": "Pass Two",
                "brand": "Brand2",
                "main_rank": "4800",
                "point_score": "3.50",
                "pf": "PASS",
                "status_reason": "PASS",
            },
            {
                "candidate_id": "C3",
                "supplier_sku": "SKU3",
                "asin": "A3",
                "title": "Rescan One",
                "brand": "Brand3",
                "main_rank": "9000",
                "point_score": "2.50",
                "pf": "FAIL",
                "status_reason": "FAIL",
            },
            {
                "candidate_id": "C6",
                "supplier_sku": "SKU6_BASE",
                "asin": "A6_BASE",
                "title": "Alt Candidate Base",
                "brand": "Brand6",
                "main_rank": "15000",
                "point_score": "3.75",
                "pf": "PASS",
                "status_reason": "PASS",
            },
        ],
    )

    _write_csv(
        scrape_path,
        [
            {
                "candidate_id": "C1",
                "supplier_sku": "SKU1",
                "asin": "A1",
                "title": "Pass One",
                "status_reason": "PASS",
                "bbp_sales_replay_demand_basis_units": "18",
                "estimated_monthly_profit": "55",
                "profit_per_unit_30d": "6",
                "opportunity_recommendation": "PASS",
                "history_recommendation": "PASS",
                "demand_confidence_note": "strong_signal",
                "historical_uk_reviews": "15",
                "variant_reviews": "6867",
            },
            {
                "candidate_id": "C2",
                "supplier_sku": "SKU2",
                "asin": "A2",
                "title": "Pass Two",
                "status_reason": "PASS",
                "bbp_sales_replay_demand_basis_units": "7",
                "estimated_monthly_profit": "24",
                "profit_per_unit_30d": "4",
                "opportunity_recommendation": "REVIEW",
                "history_recommendation": "PASS",
                "demand_confidence_note": "medium_signal",
                "historical_uk_reviews": "11",
                "variant_reviews": "647",
            },
            {
                "candidate_id": "C3",
                "supplier_sku": "SKU3",
                "asin": "A3",
                "title": "Rescan One",
                "status_reason": "RESCAN",
                "opportunity_recommendation": "",
                "history_recommendation": "",
            },
            {
                "candidate_id": "C4",
                "supplier_sku": "SKU4",
                "asin": "A4",
                "title": "ROI Near Miss",
                "status_reason": "ROIFAIL",
                "bbp_sales_replay_demand_basis_units": "9",
                "estimated_monthly_profit": "15",
                "profit_per_unit_30d": "2.5",
                "opportunity_recommendation": "REVIEW",
                "history_recommendation": "REVIEW",
            },
            {
                "candidate_id": "C6__alt2_B000ALT6",
                "supplier_sku": "SKU6",
                "asin": "A6",
                "title": "Alt Candidate Derived",
                "status_reason": "RESCAN",
                "opportunity_recommendation": "",
                "history_recommendation": "",
            },
        ],
    )

    _write_csv(
        backtest_path,
        [
            {
                "seller_sku": "SKU1",
                "asin": "A1",
                "decision_state": "pass",
                "decision_confidence": "high",
                "stability_state": "stable",
                "expected_units_next_30d": "20",
                "expected_profit_next_30d_gbp": "60",
                "recommendation": "Managed fit",
                "decision_reason_codes": "meets_profit_floor",
            },
            {
                "seller_sku": "SKU2",
                "asin": "A2",
                "decision_state": "pass",
                "decision_confidence": "medium",
                "stability_state": "stable",
                "expected_units_next_30d": "8",
                "expected_profit_next_30d_gbp": "22",
                "recommendation": "Managed fit",
                "decision_reason_codes": "meets_profit_floor",
            },
            {
                "seller_sku": "SKU4",
                "asin": "A4",
                "decision_state": "fail",
                "decision_confidence": "medium",
                "stability_state": "stable",
                "expected_units_next_30d": "10",
                "expected_profit_next_30d_gbp": "15",
                "recommendation": "Avoid",
                "decision_reason_codes": "expected_profit_below_floor",
            },
        ],
    )
    _write_csv(
        supplier_inbox_dir / "stocklist_supplier" / "canonical_current.csv",
        [
            {"supplier_id": "stocklist_supplier", "supplier_sku": "SKU1", "supplier_title": "Pass One", "brand": "Brand1", "unit_cost": "10", "currency": "GBP"},
            {"supplier_id": "stocklist_supplier", "supplier_sku": "SKU2", "supplier_title": "Pass Two", "brand": "Brand2", "unit_cost": "10", "currency": "GBP"},
            {"supplier_id": "stocklist_supplier", "supplier_sku": "SKU3", "supplier_title": "Rescan One", "brand": "Brand3", "unit_cost": "10", "currency": "GBP"},
            {"supplier_id": "stocklist_supplier", "supplier_sku": "SKU4", "supplier_title": "ROI Near Miss", "brand": "Brand4", "unit_cost": "10", "currency": "GBP"},
            {"supplier_id": "stocklist_supplier", "supplier_sku": "SKU5", "supplier_title": "Over Rank", "brand": "Brand5", "unit_cost": "10", "currency": "GBP"},
            {"supplier_id": "stocklist_supplier", "supplier_sku": "SKU6", "supplier_title": "Alt Candidate Derived", "brand": "Brand6", "unit_cost": "10", "currency": "GBP"},
        ],
    )

    result = build_live_price_file_near_miss_pack(
        baseline_path=baseline_path,
        row_state_path=row_state_path,
        first_checks_path=first_checks_path,
        scrape_evidence_path=scrape_path,
        backtest_summary_path=backtest_path,
        supplier_inbox_dir=supplier_inbox_dir,
        output_dir=output_dir,
        observed_utc="2026-04-22T15:00:00Z",
        review_batch_size=2,
    )

    assert len(result.pass_df.index) == 2
    assert len(result.near_miss_df.index) == 3

    pass_by_asin = {row["asin"]: row for row in result.pass_df.to_dict("records")}
    near_by_asin = {row["asin"]: row for row in result.near_miss_df.to_dict("records")}

    assert pass_by_asin["A1"]["conservative_starter_qty"] == "5"
    assert pass_by_asin["A1"]["pass_reason_summary"] == "screening_pass|backtest_pass|profit_floor_met|demand_evidence_present"
    assert "units_likely_30d=20" in pass_by_asin["A1"]["why_data_summary"]
    assert "profit_likely_gbp=60" in pass_by_asin["A1"]["why_data_summary"]
    assert "decision_confidence=high" in pass_by_asin["A1"]["watch_data_summary"]
    assert pass_by_asin["A1"]["review_batch_id"] == "pass_batch_001"
    assert pass_by_asin["A1"]["original_point_score"] == "4"
    assert pass_by_asin["A1"]["original_test_result"] == "PASS"
    assert pass_by_asin["A1"]["original_test_gate"] == "3.5"
    assert pass_by_asin["A2"]["review_batch_id"] == "pass_batch_001"

    assert near_by_asin["A3"]["near_miss_type"] == "evidence_gap_near_miss"
    assert near_by_asin["A3"]["recovery_hint"] == "technical_or_missing_evidence_rescan"
    assert "fail_code=RESCAN" in near_by_asin["A3"]["why_data_summary"]
    assert "recovery_hint=technical_or_missing_evidence_rescan" in near_by_asin["A3"]["watch_data_summary"]
    assert near_by_asin["A3"]["review_batch_id"] == "near_miss_batch_001"
    assert near_by_asin["A3"]["original_point_score"] == "2.5"
    assert near_by_asin["A3"]["original_test_result"] == "FAIL"
    assert near_by_asin["A3"]["original_test_gate"] == "3.5"

    assert near_by_asin["A4"]["near_miss_type"] == "commercial_near_miss"
    assert near_by_asin["A4"]["conservative_starter_qty"] == "2"
    assert near_by_asin["A4"]["original_point_score"] == ""
    assert near_by_asin["A6"]["near_miss_type"] == "evidence_gap_near_miss"
    assert near_by_asin["A6"]["original_point_score"] == "3.75"
    assert near_by_asin["A6"]["original_test_result"] == "PASS"
    assert near_by_asin["A6"]["original_test_gate"] == "3.5"

    assert "A5" not in near_by_asin
    assert _metric(result.summary_df, "pass_review_rows") == "2"
    assert _metric(result.summary_df, "source_seen_at_utc") == "2026-04-10T15:26:58Z"
    assert _metric(result.summary_df, "price_file_batch_id") == "stocklist_supplier_20260410T152658Z"
    assert _metric(result.summary_df, "near_miss_review_rows") == "3"
    assert _metric(result.summary_df, "near_miss_evidence_gap_rows") == "2"
    assert _metric(result.summary_df, "near_miss_commercial_rows") == "1"
    assert _metric(result.summary_df, "hard_reject_rows") == "1"
    assert _metric(result.summary_df, "hard_reject::OVER50K") == "1"
    assert result.pass_latest_path.exists()
    assert result.near_miss_latest_path.exists()
    assert result.summary_latest_path.exists()


def test_blank_amazon_demand_high_bbp_routes_out_of_clean_pass(tmp_path: Path) -> None:
    result = _run_demand_pack(tmp_path, [{"asin": "ASIN-HIGH", "monthly_sold": "", "bbp_units": "813"}])

    assert "ASIN-HIGH" not in set(result.pass_df["asin"])
    near = _records_by_asin(result.near_miss_df)["ASIN-HIGH"]
    assert near["near_miss_type"] == "demand_range_conflict"
    assert near["reviewability_state"] == "remove_from_clean_pass"
    assert near["screening_fail_code"] == "DEMAND_RANGE_BLOCK"
    assert near["demand_conflict_code"] == "amazon_blank_bbp_high"
    assert near["demand_recommended_action"] == "remove_from_clean_pass"


def test_very_weak_identity_match_routes_out_of_clean_pass(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-WRONG-PRODUCT",
                "status_reason": "PASS|MATCH_VERY_WEAK",
                "catalog_match_scorecard": "0|VERY_WEAK|barcode_conflict",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
            }
        ],
    )

    assert result.pass_df.empty
    near = _records_by_asin(result.near_miss_df)["ASIN-WRONG-PRODUCT"]
    assert near["near_miss_type"] == "identity_mismatch"
    assert near["reviewability_state"] == "remove_from_clean_pass"
    assert near["screening_fail_code"] == "IDENTITY_MISMATCH"
    assert near["identity_match_code"] == "identity_supplier_asin_mismatch"
    assert near["identity_recommended_action"] == "remove_from_clean_pass"
    assert "barcode_conflict" in near["identity_supporting_codes"]
    assert _metric(result.summary_df, "identity_routed_remove_from_clean_pass_rows") == "1"


def test_weak_identity_match_routes_to_manual_review(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-WEAK-MATCH",
                "status_reason": "PASS|MATCH_WEAK",
                "catalog_match_scorecard": "40|WEAK|title_overlap_low",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
            }
        ],
    )

    near = _records_by_asin(result.near_miss_df)["ASIN-WEAK-MATCH"]
    assert result.pass_df.empty
    assert near["near_miss_type"] == "identity_manual_review"
    assert near["reviewability_state"] == "reviewable"
    assert near["screening_fail_code"] == "IDENTITY_WARN"
    assert near["identity_match_code"] == "identity_weak_manual_review"
    assert near["identity_recommended_action"] == "manual_review"
    assert _metric(result.summary_df, "identity_routed_manual_review_rows") == "1"


def test_title_match_suspicion_plus_extreme_roi_routes_out_of_clean_pass(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "B07JH4JHTC",
                "candidate_id": "cand-fluval",
                "supplier_sku": "1233233",
                "supplier_title": "FLUVAL -Poly/Clearmax filter cartridge Fluval U2 - (126.2481)",
                "supplier_brand": "Fluval",
                "amazon_title": "Fluval 307 External Filter, 1 kg",
                "amazon_brand": "Fluval",
                "unit_cost": "3.05",
                "profit_per_unit_30d": "123.72",
                "expected_profit_next_30d_gbp": "5196.24",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
            }
        ],
    )

    assert result.pass_df.empty
    near = _records_by_asin(result.near_miss_df)["B07JH4JHTC"]
    assert near["near_miss_type"] == "title_match_identity_suspicion"
    assert near["reviewability_state"] == "remove_from_clean_pass"
    assert near["screening_fail_code"] == "TITLE_MATCH_BLOCK"
    assert near["title_match_action"] == "remove_from_clean_pass"
    assert near["title_match_decision_bucket"] == "high_roi_identity_suspicion"
    assert near["title_match_reason_code"] == "suspicious_title_high_roi_auto_fail"
    assert near["supplier_title"] == "FLUVAL -Poly/Clearmax filter cartridge Fluval U2 - (126.2481)"
    assert near["amazon_title"] == "Fluval 307 External Filter, 1 kg"
    assert float(near["title_match_profit_on_cost_pct"]) > 4000
    assert _metric(result.summary_df, "title_match_routed_remove_from_clean_pass_rows") == "1"


def test_low_profit_routes_to_manual_review_before_clean_pass(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-LOW-PROFIT",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "expected_profit_next_30d_gbp": "12",
                "estimated_monthly_profit": "12",
                "profit_per_unit_30d": "1.2",
            }
        ],
    )

    near = _records_by_asin(result.near_miss_df)["ASIN-LOW-PROFIT"]
    assert result.pass_df.empty
    assert near["near_miss_type"] == "profit_manual_review"
    assert near["reviewability_state"] == "reviewable"
    assert near["screening_fail_code"] == "PROFIT_WARN"
    assert near["profit_recommended_action"] == "manual_review"
    assert _metric(result.summary_df, "profit_routed_manual_review_rows") == "1"


def test_too_weak_profit_routes_out_of_clean_pass(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-TOO-WEAK-PROFIT",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "expected_profit_next_30d_gbp": "5",
                "estimated_monthly_profit": "5",
                "profit_per_unit_30d": "0.5",
            }
        ],
    )

    near = _records_by_asin(result.near_miss_df)["ASIN-TOO-WEAK-PROFIT"]
    assert result.pass_df.empty
    assert near["near_miss_type"] == "profit_conflict"
    assert near["reviewability_state"] == "remove_from_clean_pass"
    assert near["screening_fail_code"] == "PROFIT_BLOCK"
    assert near["profit_recommended_action"] == "remove_from_clean_pass"
    assert _metric(result.summary_df, "profit_routed_remove_from_clean_pass_rows") == "1"


def test_amazon_50_bbp_inflated_routes_out_of_clean_pass(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [{"asin": "ASIN-INFLATED", "monthly_sold": "50+ bought in past month", "bbp_units": "1000"}],
    )

    assert "ASIN-INFLATED" not in set(result.pass_df["asin"])
    near = _records_by_asin(result.near_miss_df)["ASIN-INFLATED"]
    assert near["demand_conflict_code"] == "amazon_50_bbp_inflated"
    assert near["demand_recommended_action"] == "remove_from_clean_pass"
    assert near["near_miss_type"] == "demand_range_conflict"


def test_amazon_50_bbp_warn_routes_to_manual_review(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [{"asin": "ASIN-WARN", "monthly_sold": "50+ bought in past month", "bbp_units": "180"}],
    )

    assert "ASIN-WARN" not in set(result.pass_df["asin"])
    near = _records_by_asin(result.near_miss_df)["ASIN-WARN"]
    assert near["demand_conflict_code"] == "amazon_50_bbp_warn"
    assert near["demand_recommended_action"] == "manual_review"
    assert near["near_miss_type"] == "demand_range_manual_review"
    assert near["reviewability_state"] == "reviewable"
    assert near["screening_fail_code"] == "DEMAND_RANGE_WARN"


def test_uk_reviews_lt3_routes_out_of_clean_pass(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-UK-LT3",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "historical_uk_reviews": "2",
                "variant_reviews": "469",
            }
        ],
    )

    assert "ASIN-UK-LT3" not in set(result.pass_df["asin"])
    near = _records_by_asin(result.near_miss_df)["ASIN-UK-LT3"]
    assert near["near_miss_type"] == "uk_review_conflict"
    assert near["reviewability_state"] == "remove_from_clean_pass"
    assert near["screening_fail_code"] == "UK_REVIEW_BLOCK"
    assert near["uk_review_code"] == "uk_reviews_lt3"
    assert near["uk_review_recommended_action"] == "remove_from_clean_pass"
    assert near["uk_review_supporting_codes"] == "uk_reviews_lt3"


def test_uk_reviews_3_to_5_routes_to_manual_review(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-UK-3TO5",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "historical_uk_reviews": "3",
                "variant_reviews": "469",
            }
        ],
    )

    assert "ASIN-UK-3TO5" not in set(result.pass_df["asin"])
    near = _records_by_asin(result.near_miss_df)["ASIN-UK-3TO5"]
    assert near["near_miss_type"] == "uk_review_manual_review"
    assert near["reviewability_state"] == "reviewable"
    assert near["screening_fail_code"] == "UK_REVIEW_WARN"
    assert near["uk_review_code"] == "uk_reviews_3_to_5"
    assert near["uk_review_recommended_action"] == "manual_review"
    assert near["uk_review_supporting_codes"] == "uk_reviews_3_to_5"


def test_uk_reviews_6_to_9_remains_clean_pass_without_other_blockers(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-UK-6TO9",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "historical_uk_reviews": "9",
                "variant_reviews": "469",
            }
        ],
    )

    assert result.near_miss_df.empty
    pass_row = _records_by_asin(result.pass_df)["ASIN-UK-6TO9"]
    assert pass_row["uk_review_code"] == "uk_reviews_6_to_9"
    assert pass_row["uk_review_recommended_action"] == "supporting_evidence_only"
    assert pass_row["uk_review_supporting_codes"] == "uk_reviews_6_to_9"


def test_uk_reviews_10_plus_preserves_existing_clean_pass_behavior(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-UK-10PLUS",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "historical_uk_reviews": "10",
                "variant_reviews": "469",
            }
        ],
    )

    assert result.near_miss_df.empty
    pass_row = _records_by_asin(result.pass_df)["ASIN-UK-10PLUS"]
    assert pass_row["uk_review_code"] == "uk_reviews_10_plus"
    assert pass_row["uk_review_recommended_action"] == "allow_if_other_checks_pass"
    assert pass_row["uk_review_supporting_codes"] == "uk_reviews_10_plus"


def test_uk_reviews_missing_routes_to_targeted_rescan_needed(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-UK-MISSING",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "historical_uk_reviews": "",
                "variant_reviews": "469",
            }
        ],
    )

    assert "ASIN-UK-MISSING" not in set(result.pass_df["asin"])
    near = _records_by_asin(result.near_miss_df)["ASIN-UK-MISSING"]
    assert near["near_miss_type"] == "uk_review_targeted_rescan_needed"
    assert near["reviewability_state"] == "targeted_rescan_needed"
    assert near["screening_fail_code"] == "UK_REVIEW_MISSING"
    assert near["uk_review_code"] == "uk_reviews_missing"
    assert near["uk_review_recommended_action"] == "targeted_rescan_needed"


def test_missing_seller_stock_is_supporting_evidence_not_invented(tmp_path: Path) -> None:
    result = _run_demand_pack(tmp_path, [{"asin": "ASIN-STOCK", "monthly_sold": "", "bbp_units": "813"}])

    near = _records_by_asin(result.near_miss_df)["ASIN-STOCK"]
    assert near["demand_conflict_code"] == "amazon_blank_bbp_high"
    assert near["demand_recommended_action"] == "remove_from_clean_pass"
    assert "seller_stock_missing_for_demand_check" in near["demand_supporting_codes"]
    assert "seller_stock_count" not in result.near_miss_df.columns
    assert _metric(result.summary_df, "demand_supporting_code::seller_stock_missing_for_demand_check") == "1"


def test_amazon_50_bbp_reasonable_remains_allowed_if_other_checks_pass(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [{"asin": "ASIN-REASONABLE", "monthly_sold": "50+ bought in past month", "bbp_units": "67"}],
    )

    pass_row = _records_by_asin(result.pass_df)["ASIN-REASONABLE"]
    assert result.near_miss_df.empty
    assert pass_row["demand_conflict_code"] == "amazon_50_bbp_reasonable"
    assert pass_row["demand_recommended_action"] == "allow_if_other_checks_pass"


def test_b0c8c3jf9x_routes_out_of_clean_pass_with_supporting_codes(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "B0C8C3JF9X",
                "candidate_id": "cand-B0C8C3JF9X",
                "supplier_sku": "sku-B0C8C3JF9X",
                "monthly_sold": "",
                "bbp_units": "1017",
                "expected_units": "813.6",
                "historical_uk_reviews": "3",
                "variant_reviews": "469",
            }
        ],
    )

    assert "B0C8C3JF9X" not in set(result.pass_df["asin"])
    near = _records_by_asin(result.near_miss_df)["B0C8C3JF9X"]
    assert near["demand_conflict_code"] == "amazon_blank_bbp_high"
    assert near["demand_recommended_action"] == "remove_from_clean_pass"
    assert near["demand_supporting_codes"] == (
        "amazon_blank_bbp_high|weak_uk_review_confirms_demand_risk|seller_stock_missing_for_demand_check"
    )
    assert near["uk_review_code"] == "uk_reviews_3_to_5"
    assert near["uk_review_recommended_action"] == "manual_review"


def test_existing_clean_pass_without_high_demand_conflict_remains_clean_pass(tmp_path: Path) -> None:
    result = _run_demand_pack(tmp_path, [{"asin": "ASIN-LOW", "monthly_sold": "", "bbp_units": "30"}])

    pass_row = _records_by_asin(result.pass_df)["ASIN-LOW"]
    assert result.near_miss_df.empty
    assert pass_row["demand_conflict_code"] == "amazon_blank_bbp_low"
    assert pass_row["demand_recommended_action"] == "allow_if_other_checks_pass"


def test_amazon_only_single_seller_routes_out_of_clean_pass(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-AMAZON-ONLY",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "price_hist_new_30": "1",
                "price_hist_new_90": "1",
                "price_hist_new_180": "1",
                "price_hist_amazon_30": "46.20",
                "price_hist_amazon_90": "43.96",
                "price_hist_amazon_180": "43.96",
                "price_hist_fba_30": "0",
                "price_hist_fba_90": "0",
                "price_hist_fba_180": "0",
                "price_hist_buy_box_30": "46.17",
                "price_hist_buy_box_90": "43.95",
                "price_hist_buy_box_180": "43.95",
            }
        ],
    )

    near = _records_by_asin(result.near_miss_df)["ASIN-AMAZON-ONLY"]
    assert result.pass_df.empty
    assert near["near_miss_type"] == "seller_history_amazon_only_conflict"
    assert near["reviewability_state"] == "remove_from_clean_pass"
    assert near["seller_history_code"] == "amazon_only_single_seller"
    assert near["seller_history_recommended_action"] == "remove_from_clean_pass"
    assert near["seller_history_new_30"] == "1"
    assert near["seller_history_new_90"] == "1"
    assert near["seller_history_new_180"] == "1"
    assert _metric(result.summary_df, "seller_history_routed_remove_from_clean_pass_rows") == "1"
    assert _metric(result.summary_df, "seller_history_action::remove_from_clean_pass") == "1"


def test_single_fba_seller_amazon_absent_remains_clean_pass(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-SINGLE-FBA",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "price_hist_new_30": "1",
                "price_hist_new_90": "1",
                "price_hist_new_180": "1",
                "price_hist_amazon_30": "0",
                "price_hist_amazon_90": "0",
                "price_hist_amazon_180": "0",
                "price_hist_fba_30": "9.99",
                "price_hist_fba_90": "9.98",
                "price_hist_fba_180": "9.98",
                "price_hist_buy_box_30": "9.99",
                "price_hist_buy_box_90": "9.98",
                "price_hist_buy_box_180": "9.98",
            }
        ],
    )

    pass_row = _records_by_asin(result.pass_df)["ASIN-SINGLE-FBA"]
    assert result.near_miss_df.empty
    assert pass_row["seller_history_code"] == "single_fba_seller_amazon_absent"
    assert pass_row["seller_history_recommended_action"] == "allow_if_other_checks_pass"


def test_brand_matching_single_seller_routes_out_of_clean_pass(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-BRAND-OWNER",
                "brand": "Plus Plus",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "price_hist_new_30": "1",
                "price_hist_new_90": "1",
                "price_hist_new_180": "1",
                "price_hist_amazon_30": "0",
                "price_hist_amazon_90": "0",
                "price_hist_amazon_180": "0",
                "price_hist_fba_30": "9.99",
                "price_hist_fba_90": "9.98",
                "price_hist_fba_180": "9.98",
                "price_hist_buy_box_30": "9.99",
                "price_hist_buy_box_90": "9.98",
                "price_hist_buy_box_180": "9.98",
                "bbp_top_seller_names": "Plus Plus",
                "bbp_brand_match_seller": "Plus Plus",
                "bbp_brand_match_score": "1",
                "bbp_brand_match_flag": "True",
            }
        ],
    )

    near = _records_by_asin(result.near_miss_df)["ASIN-BRAND-OWNER"]
    assert result.pass_df.empty
    assert near["near_miss_type"] == "seller_history_brand_owner_conflict"
    assert near["reviewability_state"] == "remove_from_clean_pass"
    assert near["seller_history_code"] == "brand_owner_single_seller"
    assert near["seller_history_recommended_action"] == "remove_from_clean_pass"
    assert near["seller_history_top_seller_names"] == "Plus Plus"
    assert near["seller_history_brand_match_seller"] == "Plus Plus"
    assert _metric(result.summary_df, "seller_history_action::remove_from_clean_pass") == "1"


def test_buybox_brand_matching_single_seller_routes_out_of_clean_pass(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-BUYBOX-BRAND-OWNER",
                "brand": "Plus Plus",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "price_hist_new_30": "1",
                "price_hist_new_90": "1",
                "price_hist_new_180": "1",
                "price_hist_fba_30": "9.99",
                "price_hist_fba_90": "9.98",
                "price_hist_fba_180": "9.98",
                "price_hist_buy_box_30": "9.99",
                "price_hist_buy_box_90": "9.98",
                "price_hist_buy_box_180": "9.98",
                "amazon_buybox_seller_name": "Plus Plus",
                "amazon_buybox_brand_match_score": "1",
                "amazon_buybox_brand_match_flag": "True",
            }
        ],
    )

    near = _records_by_asin(result.near_miss_df)["ASIN-BUYBOX-BRAND-OWNER"]
    assert result.pass_df.empty
    assert near["seller_history_code"] == "brand_owner_single_seller"
    assert near["seller_history_buybox_seller_name"] == "Plus Plus"
    assert near["seller_history_buybox_brand_match_score"] == "1"


def test_rank_one_brand_matching_multi_seller_routes_out_of_clean_pass(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-RANK1-BRAND-OWNER",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "price_hist_new_30": "9",
                "price_hist_new_90": "8",
                "price_hist_new_180": "8",
                "bbp_top_seller_names": "Plus Plus|Miller Rock|Toy Store UK",
                "bbp_brand_match_seller": "Plus Plus",
                "bbp_brand_match_score": "1",
                "bbp_brand_match_flag": "True",
                "bbp_seller_rank_1_name": "Plus Plus",
                "bbp_seller_rank_1_brand_match_flag": "True",
            }
        ],
    )

    near = _records_by_asin(result.near_miss_df)["ASIN-RANK1-BRAND-OWNER"]
    assert result.pass_df.empty
    assert near["near_miss_type"] == "seller_history_brand_owner_conflict"
    assert near["seller_history_code"] == "brand_owner_top_seller"
    assert near["seller_history_rank_1_seller_name"] == "Plus Plus"
    assert near["seller_history_rank_1_brand_match_flag"] == "True"
    assert near["seller_history_recommended_action"] == "remove_from_clean_pass"


def test_dashboard_no_with_low_seller_count_routes_out_of_clean_pass(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-DASHBOARD-NO-LOW",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "bbp_dashboard_yes_or_no": "NO",
                "price_hist_new_30": "1",
                "price_hist_new_90": "1",
                "price_hist_new_180": "1",
                "price_hist_amazon_30": "0",
                "price_hist_amazon_90": "0",
                "price_hist_amazon_180": "0",
                "price_hist_fba_30": "9.99",
                "price_hist_fba_90": "9.98",
                "price_hist_fba_180": "9.98",
                "price_hist_buy_box_30": "9.99",
                "price_hist_buy_box_90": "9.98",
                "price_hist_buy_box_180": "9.98",
            }
        ],
    )

    near = _records_by_asin(result.near_miss_df)["ASIN-DASHBOARD-NO-LOW"]
    assert result.pass_df.empty
    assert near["near_miss_type"] == "seller_history_dashboard_no_conflict"
    assert near["reviewability_state"] == "remove_from_clean_pass"
    assert near["seller_history_code"] == "dashboard_no_low_seller_count"
    assert near["seller_history_recommended_action"] == "remove_from_clean_pass"
    assert near["seller_history_dashboard_yes_or_no"] == "NO"
    assert _metric(result.summary_df, "seller_history_routed_remove_from_clean_pass_rows") == "1"
    assert _metric(result.summary_df, "seller_history_action::remove_from_clean_pass") == "1"


def test_dashboard_no_with_multi_seller_count_stays_clean_pass_with_alert(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-DASHBOARD-NO-MULTI",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "bbp_dashboard_yes_or_no": "NO",
                "price_hist_new_30": "3",
                "price_hist_new_90": "3",
                "price_hist_new_180": "3",
            }
        ],
    )

    pass_row = _records_by_asin(result.pass_df)["ASIN-DASHBOARD-NO-MULTI"]
    assert result.near_miss_df.empty
    assert pass_row["seller_history_code"] == "dashboard_no_multi_seller_count"
    assert pass_row["seller_history_recommended_action"] == "allow_if_other_checks_pass"
    assert pass_row["seller_history_dashboard_yes_or_no"] == "NO"
    assert _metric(result.summary_df, "seller_history_routed_manual_review_rows") in {"", "0"}
    assert _metric(result.summary_df, "seller_history_action::allow_if_other_checks_pass") == "1"


def test_dashboard_likely_is_visible_as_separate_delivery_signal(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-DASHBOARD-LIKELY",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "bbp_dashboard_yes_or_no": "LIKELY",
                "price_hist_new_30": "3",
                "price_hist_new_90": "3",
                "price_hist_new_180": "3",
            }
        ],
    )

    pass_row = _records_by_asin(result.pass_df)["ASIN-DASHBOARD-LIKELY"]
    assert result.near_miss_df.empty
    assert pass_row["seller_history_code"] == "seller_history_clear"
    assert pass_row["seller_history_dashboard_yes_or_no"] == "LIKELY"
    assert pass_row["seller_history_dashboard_delivery_classification"] == "LIKELY_SELLABLE_HAZMAT_SEPARATE_DELIVERY"
    assert pass_row["seller_history_dashboard_separate_delivery_required"] == "1"


def test_low_sales_routes_out_of_clean_pass(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-LOW-SALES",
                "monthly_sold": "",
                "bbp_units": "2",
                "expected_units": "2",
                "expected_profit_next_30d_gbp": "39.08",
                "price_hist_new_30": "10",
                "price_hist_new_90": "9",
                "price_hist_new_180": "10",
            }
        ],
    )

    near = _records_by_asin(result.near_miss_df)["ASIN-LOW-SALES"]
    assert result.pass_df.empty
    assert near["near_miss_type"] == "low_sales_capital_idle_risk"
    assert near["reviewability_state"] == "remove_from_clean_pass"
    assert near["screening_fail_code"] == "LOW_SALES_CAPITAL_IDLE_RISK"
    assert near["expected_units_next_30d"] == "2"
    assert _metric(result.summary_df, "low_sales_routed_remove_from_clean_pass_rows") == "1"


def test_single_seller_unclear_owner_routes_to_manual_review(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-UNCLEAR-SELLER",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "price_hist_new_30": "1",
                "price_hist_new_90": "1",
                "price_hist_new_180": "1",
            }
        ],
    )

    near = _records_by_asin(result.near_miss_df)["ASIN-UNCLEAR-SELLER"]
    assert result.pass_df.empty
    assert near["near_miss_type"] == "seller_history_manual_review"
    assert near["reviewability_state"] == "reviewable"
    assert near["seller_history_code"] == "single_seller_owner_unclear"
    assert near["seller_history_recommended_action"] == "manual_review"


def test_seller_count_two_or_more_remains_clean_pass_without_other_blockers(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-SELLERS-CLEAR",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "price_hist_new_30": "2",
                "price_hist_new_90": "2",
                "price_hist_new_180": "2",
            }
        ],
    )

    pass_row = _records_by_asin(result.pass_df)["ASIN-SELLERS-CLEAR"]
    assert result.near_miss_df.empty
    assert pass_row["seller_history_code"] == "seller_history_clear"
    assert pass_row["seller_history_recommended_action"] == "allow_if_other_checks_pass"


def test_missing_seller_history_is_reported_but_not_failed(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [{"asin": "ASIN-SELLERS-MISSING", "monthly_sold": "50+ bought in past month", "bbp_units": "67"}],
    )

    pass_row = _records_by_asin(result.pass_df)["ASIN-SELLERS-MISSING"]
    assert result.near_miss_df.empty
    assert pass_row["seller_history_code"] == "seller_history_missing"
    assert pass_row["seller_history_recommended_action"] == "missing_evidence_only"
    assert _metric(result.summary_df, "seller_history_action::missing_evidence_only") == "1"


def test_demand_summary_counts_reconcile(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {"asin": "ASIN-HIGH", "monthly_sold": "", "bbp_units": "813"},
            {"asin": "ASIN-WARN", "monthly_sold": "50+ bought in past month", "bbp_units": "180"},
            {"asin": "ASIN-UK-LT3", "monthly_sold": "50+ bought in past month", "bbp_units": "67", "historical_uk_reviews": "2"},
            {"asin": "ASIN-UK-3TO5", "monthly_sold": "50+ bought in past month", "bbp_units": "67", "historical_uk_reviews": "3"},
            {"asin": "ASIN-UK-6TO9", "monthly_sold": "50+ bought in past month", "bbp_units": "67", "historical_uk_reviews": "7"},
            {"asin": "ASIN-UK-MISSING", "monthly_sold": "50+ bought in past month", "bbp_units": "67", "historical_uk_reviews": ""},
        ],
    )

    assert len(result.pass_df.index) == 1
    assert len(result.near_miss_df.index) == 5
    assert len(result.pass_df.index) + len(result.near_miss_df.index) == 6
    assert _metric(result.summary_df, "demand_routed_remove_from_clean_pass_rows") == "1"
    assert _metric(result.summary_df, "demand_routed_manual_review_rows") == "1"
    assert _metric(result.summary_df, "uk_review_routed_remove_from_clean_pass_rows") == "1"
    assert _metric(result.summary_df, "uk_review_routed_manual_review_rows") == "1"
    assert _metric(result.summary_df, "uk_review_routed_targeted_rescan_needed_rows") == "1"
    assert _metric(result.summary_df, "demand_action::allow_if_other_checks_pass") == "4"
    assert _metric(result.summary_df, "demand_action::manual_review") == "1"
    assert _metric(result.summary_df, "demand_action::remove_from_clean_pass") == "1"
    assert _metric(result.summary_df, "uk_review_action::allow_if_other_checks_pass") == "2"
    assert _metric(result.summary_df, "uk_review_action::manual_review") == "1"
    assert _metric(result.summary_df, "uk_review_action::remove_from_clean_pass") == "1"
    assert _metric(result.summary_df, "uk_review_action::supporting_evidence_only") == "1"
    assert _metric(result.summary_df, "uk_review_action::targeted_rescan_needed") == "1"


def test_history_fail_phase_avoid_routes_out_of_clean_pass(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-HISTORY-FAIL",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "history_recommendation": "FAIL",
                "phase_recommendation": "AVOID",
            }
        ],
    )

    assert "ASIN-HISTORY-FAIL" not in set(result.pass_df["asin"])
    near = _records_by_asin(result.near_miss_df)["ASIN-HISTORY-FAIL"]
    assert near["history_risk_code"] == "history_fail_phase_avoid"
    assert near["history_recommended_action"] == "remove_from_clean_pass"
    assert near["near_miss_type"] == "history_risk_conflict"


def test_recent_history_recovery_overrides_old_history_fail_phase_avoid(tmp_path: Path) -> None:
    phase_series = ";".join(
        f"{day.date()}=profit" for day in pd.date_range("2026-01-01", periods=90, freq="D")
    )
    amazon_series = ";".join(
        f"{day.date()}=14.00" for day in pd.date_range("2026-01-01", periods=30, freq="D")
    )
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-HISTORY-RECOVERED",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "history_recommendation": "FAIL",
                "phase_recommendation": "AVOID",
                "chart_phase_daily_series": phase_series,
                "chart_raw_amazon_daily_series": amazon_series,
            }
        ],
    )

    pass_row = _records_by_asin(result.pass_df)["ASIN-HISTORY-RECOVERED"]
    assert pass_row["history_risk_code"] == "history_recent_recovery_override"
    assert pass_row["history_recommended_action"] == "allow_if_other_checks_pass"
    assert "ASIN-HISTORY-RECOVERED" not in set(result.near_miss_df["asin"])


def test_rank_over_50k_routes_out_of_clean_pass_even_when_other_checks_pass(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-RANK-OVER-50K",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "main_rank": "74076.98",
            }
        ],
    )

    assert "ASIN-RANK-OVER-50K" not in set(result.pass_df["asin"])
    near = _records_by_asin(result.near_miss_df)["ASIN-RANK-OVER-50K"]
    assert near["near_miss_type"] == "rank_over_50k_review_pack_gate"
    assert near["screening_fail_code"] == "OVER50K_REVIEW_PACK_GATE"
    assert near["screening_status_reason"] == "rank_over_50k_review_pack_gate"
    assert _metric(result.summary_df, "rank_routed_remove_from_clean_pass_rows") == "1"


def test_backtest_avoid_commercial_avoid_or_exit_routes_out_of_clean_pass(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-BT-AVOID",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "backtest_recommendation": "Avoid",
                "opportunity_recommendation": "Avoid",
            }
        ],
    )

    assert "ASIN-BT-AVOID" not in set(result.pass_df["asin"])
    near = _records_by_asin(result.near_miss_df)["ASIN-BT-AVOID"]
    assert near["history_risk_code"] == "backtest_avoid_commercial_avoid_or_exit"
    assert near["history_recommended_action"] == "remove_from_clean_pass"
    assert near["near_miss_type"] == "history_risk_conflict"


def test_exit_only_clean_pass_routes_out_of_clean_pass(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-EXIT-ONLY",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "backtest_recommendation": "Exit-only",
                "opportunity_recommendation": "Exit-only",
            }
        ],
    )

    assert "ASIN-EXIT-ONLY" not in set(result.pass_df["asin"])
    near = _records_by_asin(result.near_miss_df)["ASIN-EXIT-ONLY"]
    assert near["history_risk_code"] == "exit_only_clean_pass"
    assert near["history_recommended_action"] == "remove_from_clean_pass"
    assert near["near_miss_type"] == "history_risk_conflict"


def test_failure_events_100_plus_routes_to_manual_review_unless_stronger_remove(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-HIST-MANUAL",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "failure_event_count": "150",
            },
            {
                "asin": "ASIN-HIST-REMOVE",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "history_recommendation": "FAIL",
                "phase_recommendation": "AVOID",
                "failure_event_count": "150",
            },
        ],
    )

    near = _records_by_asin(result.near_miss_df)
    assert near["ASIN-HIST-MANUAL"]["history_risk_code"] == "failure_events_100_plus"
    assert near["ASIN-HIST-MANUAL"]["history_recommended_action"] == "manual_review"
    assert near["ASIN-HIST-MANUAL"]["near_miss_type"] == "history_risk_manual_review"
    assert near["ASIN-HIST-REMOVE"]["history_risk_code"] == "history_fail_phase_avoid"
    assert near["ASIN-HIST-REMOVE"]["history_recommended_action"] == "remove_from_clean_pass"
    assert near["ASIN-HIST-REMOVE"]["near_miss_type"] == "history_risk_conflict"


def test_selloff_days_exceed_normal_days_routes_to_manual_review_unless_stronger_remove(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-SELLOFF-MANUAL",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "time_normal_sell_days": "8",
                "time_selloff_days": "16",
            },
            {
                "asin": "ASIN-SELLOFF-REMOVE",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "backtest_recommendation": "Avoid",
                "opportunity_recommendation": "Avoid",
                "time_normal_sell_days": "8",
                "time_selloff_days": "16",
            },
        ],
    )

    near = _records_by_asin(result.near_miss_df)
    assert near["ASIN-SELLOFF-MANUAL"]["history_risk_code"] == "selloff_days_exceed_normal_days"
    assert near["ASIN-SELLOFF-MANUAL"]["history_recommended_action"] == "manual_review"
    assert near["ASIN-SELLOFF-MANUAL"]["near_miss_type"] == "history_risk_manual_review"
    assert near["ASIN-SELLOFF-REMOVE"]["history_risk_code"] == "backtest_avoid_commercial_avoid_or_exit"
    assert near["ASIN-SELLOFF-REMOVE"]["history_recommended_action"] == "remove_from_clean_pass"
    assert near["ASIN-SELLOFF-REMOVE"]["near_miss_type"] == "history_risk_conflict"


def test_history_risk_clear_preserves_existing_clean_pass_behavior(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [{"asin": "ASIN-HISTORY-CLEAR", "monthly_sold": "50+ bought in past month", "bbp_units": "67"}],
    )

    pass_row = _records_by_asin(result.pass_df)["ASIN-HISTORY-CLEAR"]
    assert result.near_miss_df.empty
    assert pass_row["history_risk_code"] == "history_risk_clear"
    assert pass_row["history_recommended_action"] == "allow_if_other_checks_pass"


def test_demand_range_routing_still_works_after_history_routing(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [{"asin": "ASIN-DEMAND-STILL", "monthly_sold": "", "bbp_units": "813"}],
    )

    near = _records_by_asin(result.near_miss_df)["ASIN-DEMAND-STILL"]
    assert near["demand_conflict_code"] == "amazon_blank_bbp_high"
    assert near["demand_recommended_action"] == "remove_from_clean_pass"
    assert near["near_miss_type"] == "demand_range_conflict"
    assert near["history_risk_code"] == "history_risk_clear"


def test_history_summary_counts_reconcile(tmp_path: Path) -> None:
    result = _run_demand_pack(
        tmp_path,
        [
            {
                "asin": "ASIN-HISTORY-REMOVE-1",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "history_recommendation": "FAIL",
                "phase_recommendation": "AVOID",
            },
            {
                "asin": "ASIN-HISTORY-MANUAL-1",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
                "failure_event_count": "180",
            },
            {
                "asin": "ASIN-HISTORY-CLEAR-1",
                "monthly_sold": "50+ bought in past month",
                "bbp_units": "67",
            },
            {
                "asin": "ASIN-DEMAND-REMOVE-1",
                "monthly_sold": "",
                "bbp_units": "813",
            },
        ],
    )

    assert len(result.pass_df.index) + len(result.near_miss_df.index) == 4
    assert _metric(result.summary_df, "history_routed_remove_from_clean_pass_rows") == "1"
    assert _metric(result.summary_df, "history_routed_manual_review_rows") == "1"
    assert _metric(result.summary_df, "history_action::allow_if_other_checks_pass") == "2"
    assert _metric(result.summary_df, "history_action::manual_review") == "1"
    assert _metric(result.summary_df, "history_action::remove_from_clean_pass") == "1"


def test_f019_keeps_identity_columns_and_adds_profit_audit_evidence(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.csv"
    row_state_path = tmp_path / "row_state.csv"
    first_checks_path = tmp_path / "first_checks.csv"
    scrape_path = tmp_path / "scrape.csv"
    backtest_path = tmp_path / "backtest.csv"
    profit_audit_path = tmp_path / "profit_audit.csv"
    output_dir = tmp_path / "analysis"

    _write_csv(baseline_path, [{"active_supplier_id": "stocklist_supplier", "active_run_id": "run-1"}])
    _write_csv(
        row_state_path,
        [
            {
                "supplier_id": "stocklist_supplier",
                "candidate_id": "C1",
                "supplier_sku": "SKU1",
                "asin": "A1",
                "row_status": "pass",
                "status_reason": "PASS",
                "fail_code": "",
                "last_stage": "webscrape",
            }
        ],
    )
    _write_csv(
        first_checks_path,
        [
            {
                "candidate_id": "C1",
                "supplier_sku": "SKU1",
                "asin": "A1",
                "title": "Pass One",
                "brand": "Brand1",
                "main_rank": "1200",
                "point_score": "4.00",
                "pf": "PASS",
                "status_reason": "PASS",
            }
        ],
    )
    _write_csv(
        scrape_path,
        [
            {
                "candidate_id": "C1",
                "supplier_sku": "SKU1",
                "asin": "A1",
                "title": "Pass One",
                "status_reason": "PASS",
                "bbp_sales_replay_demand_basis_units": "18",
                "estimated_monthly_profit": "55",
                "profit_per_unit_30d": "6",
                "opportunity_recommendation": "PASS",
                "history_recommendation": "PASS",
                "demand_confidence_note": "strong_signal",
                "historical_uk_reviews": "15",
                "variant_reviews": "6867",
            }
        ],
    )
    _write_csv(
        backtest_path,
        [
            {
                "seller_sku": "SKU1",
                "asin": "A1",
                "decision_state": "pass",
                "decision_confidence": "high",
                "stability_state": "stable",
                "expected_units_next_30d": "20",
                "expected_profit_next_30d_gbp": "60",
                "recommendation": "Managed fit",
                "decision_reason_codes": "meets_profit_floor",
            }
        ],
    )
    _write_csv(
        profit_audit_path,
        [
            {
                "candidate_id": "C1",
                "supplier_sku": "SKU1",
                "asin": "A1",
                "review_pack_type": "passes",
                "profit_formula_code": "profit_inflated_break_even_subtraction",
                "recommended_action": "remove_from_clean_pass",
                "corrected_profit_per_unit_gbp": "4.38",
                "corrected_expected_profit_next_30d_gbp": "87.6",
                "profit_delta_per_unit_gbp": "1.62",
                "profit_delta_total_gbp": "32.4",
                "evidence_source": "unit_test_profit_audit",
            }
        ],
    )

    result = build_live_price_file_near_miss_pack(
        baseline_path=baseline_path,
        row_state_path=row_state_path,
        first_checks_path=first_checks_path,
        scrape_evidence_path=scrape_path,
        backtest_summary_path=backtest_path,
        profit_audit_path=profit_audit_path,
        output_dir=output_dir,
        observed_utc="2026-04-22T15:00:00Z",
        review_batch_size=20,
    )

    assert result.pass_df.empty
    row = _records_by_asin(result.near_miss_df)["A1"]
    assert row["near_miss_type"] == "profit_conflict"
    assert row["reviewability_state"] == "remove_from_clean_pass"
    assert row["screening_fail_code"] == "PROFIT_BLOCK"
    assert row["candidate_id"] == "C1"
    assert row["supplier_sku"] == "SKU1"
    assert row["asin"] == "A1"
    assert row["profit_formula_code"] == "profit_inflated_break_even_subtraction"
    assert row["profit_recommended_action"] == "remove_from_clean_pass"
    assert row["profit_per_unit_30d_gbp"] == "4.38"
    assert row["expected_profit_next_30d_gbp"] == "87.6"
    assert row["corrected_profit_per_unit_gbp"] == "4.38"
    assert row["corrected_expected_profit_next_30d_gbp"] == "87.6"
    assert row["profit_delta_per_unit_gbp"] == "1.62"
    assert row["profit_delta_total_gbp"] == "32.4"
    assert row["profit_evidence_source"] == "unit_test_profit_audit"
    assert _metric(result.summary_df, "profit_routed_remove_from_clean_pass_rows") == "1"
