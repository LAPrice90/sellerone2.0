from __future__ import annotations

import pandas as pd

from scripts.flows.E import E004_build_performance_summary as e004
from scripts.flows.E import E005_build_study_report as e005


def test_e004_labels_velocity_only_rows_with_missing_roi_reason() -> None:
    summary = pd.DataFrame(
        [
            {
                "sku": "SKU_ROI",
                "units_sold_source": "roi",
                "units_sold_roi": "4",
                "profit_exvat_gbp": "20",
                "roi_exvat": "1.5",
                "missing_cogs_units": "0",
                "fx_missing_units": "0",
                "reorder_flag": "yes",
                "current_token_cost_gbp": "2",
                "break_even_price_gbp": "5",
                "refund_proof_state": "api_proved_or_not_applicable",
                "refund_sample_confidence": "enough_sales",
            },
            {
                "sku": "SKU_VELOCITY",
                "units_sold_source": "velocity",
                "units_sold_truth_30d": "2",
                "units_sold_roi": "",
                "profit_exvat_gbp": "",
                "roi_exvat": "",
                "missing_cogs_units": "0",
                "fx_missing_units": "0",
                "reorder_flag": "yes",
                "current_token_cost_gbp": "2",
                "break_even_price_gbp": "5",
                "refund_proof_state": "api_proved_or_not_applicable",
                "refund_sample_confidence": "enough_sales",
            },
        ]
    )

    labelled = e004._with_confidence_fields(summary)
    by_sku = {row["sku"]: row for row in labelled.to_dict("records")}

    assert by_sku["SKU_ROI"]["profit_confidence"] == "profit_clean"
    assert by_sku["SKU_ROI"]["stock_signal"] == "yes"
    assert by_sku["SKU_ROI"]["restock_business_ready"] == "yes"
    assert by_sku["SKU_ROI"]["restock_decision_state"] == "business_ready_clean"
    assert by_sku["SKU_ROI"]["restock_readiness_confidence"] == "clean"
    assert by_sku["SKU_ROI"]["restock_missing_proof"] == ""
    assert by_sku["SKU_ROI"]["restock_evidence_role"] == "evidence_only_not_buy_instruction"
    assert by_sku["SKU_VELOCITY"]["profit_confidence"] == "profit_missing"
    assert by_sku["SKU_VELOCITY"]["sales_truth_state"] == "velocity_only"
    assert by_sku["SKU_VELOCITY"]["restock_business_ready"] == "no"
    assert by_sku["SKU_VELOCITY"]["restock_decision_state"] == "blocked_missing_roi"
    assert "missing_roi" in by_sku["SKU_VELOCITY"]["restock_missing_proof"]
    assert by_sku["SKU_VELOCITY"]["missing_roi_reason"] == "velocity_only_sales_truth"
    assert by_sku["SKU_VELOCITY"]["missing_reason"] == "velocity_only_sales_truth"


def test_e004_blocks_business_ready_when_profit_proof_is_limited() -> None:
    summary = pd.DataFrame(
        [
            {
                "sku": "SKU_LIMITED",
                "units_sold_source": "roi",
                "units_sold_roi": "3",
                "profit_exvat_gbp": "15",
                "roi_exvat": "1.2",
                "missing_cogs_units": "1",
                "fx_missing_units": "0",
                "reorder_flag": "yes",
                "current_token_cost_gbp": "",
                "break_even_price_gbp": "",
                "refund_proof_state": "api_proved_or_not_applicable",
                "refund_sample_confidence": "enough_sales",
            }
        ]
    )

    labelled = e004._with_confidence_fields(summary)

    assert labelled.loc[0, "profit_confidence"] == "profit_limited"
    assert labelled.loc[0, "restock_business_ready"] == "no"
    assert labelled.loc[0, "restock_decision_state"] == "blocked_missing_profit_inputs"
    assert "missing_cogs_or_fx" in labelled.loc[0, "restock_missing_proof"]
    assert labelled.loc[0, "missing_roi_reason"] == "missing_cogs_or_fx"
    assert labelled.loc[0, "missing_reason"] == "missing_cogs_or_fx"


def test_e004_labels_stock_only_and_missing_input_detail() -> None:
    summary = pd.DataFrame(
        [
            {
                "sku": "SKU_STOCK_ONLY",
                "units_sold_source": "velocity",
                "units_sold_truth_30d": "0",
                "units_sold_roi": "",
                "profit_exvat_gbp": "",
                "roi_exvat": "",
                "available": "2",
                "reorder_flag": "yes",
                "latest_price_confidence": "listing_price_unproven",
                "refund_proof_state": "not_yet_proven",
                "refund_sample_confidence": "no_refund_rate_proof",
                "break_even_price_gbp": "",
            }
        ]
    )

    labelled = e004._with_confidence_fields(summary)

    assert labelled.loc[0, "missing_roi_reason"] == "stock_only_no_sales_window"
    assert "missing_current_price_proof" in labelled.loc[0, "missing_roi_reason_detail"]
    assert "missing_refund_proof" in labelled.loc[0, "missing_roi_reason_detail"]
    assert labelled.loc[0, "restock_business_ready"] == "no"
    assert labelled.loc[0, "restock_decision_state"] == "blocked_missing_roi"
    assert "missing_current_price" in labelled.loc[0, "restock_missing_proof"]
    assert "weak_refund_proof" in labelled.loc[0, "restock_missing_proof"]


def test_e004_blocks_business_ready_when_b_money_is_bridge_labelled() -> None:
    summary = pd.DataFrame(
        [
            {
                "sku": "SKU_BRIDGE",
                "units_sold_source": "roi",
                "units_sold_roi": "4",
                "profit_exvat_gbp": "20",
                "roi_exvat": "1.5",
                "missing_cogs_units": "0",
                "fx_missing_units": "0",
                "reorder_flag": "yes",
                "latest_price_confidence": "listing_price_current",
                "current_token_cost_gbp": "2",
                "break_even_price_gbp": "5",
                "refund_proof_state": "api_proved_or_not_applicable",
                "refund_sample_confidence": "enough_sales",
            }
        ]
    )

    labelled = e004._with_confidence_fields(
        summary,
        {
            "b_money_confidence_state": "bridge_labelled_only",
            "b_bridge_values_safe_for_live_roi": "0",
        },
    )

    assert labelled.loc[0, "restock_business_ready"] == "no"
    assert labelled.loc[0, "restock_decision_state"] == "warning_bridge_labelled_money"
    assert labelled.loc[0, "restock_readiness_confidence"] == "warning"
    assert "bridge_labelled_money" in labelled.loc[0, "restock_missing_proof"]


def test_e004_blocks_business_ready_when_refund_proof_is_weak() -> None:
    summary = pd.DataFrame(
        [
            {
                "sku": "SKU_REFUND",
                "units_sold_source": "roi",
                "units_sold_roi": "4",
                "profit_exvat_gbp": "20",
                "roi_exvat": "1.5",
                "missing_cogs_units": "0",
                "fx_missing_units": "0",
                "reorder_flag": "yes",
                "latest_price_confidence": "listing_price_current",
                "current_token_cost_gbp": "2",
                "break_even_price_gbp": "5",
                "refund_proof_state": "sellerboard_bridge_only",
                "refund_sample_confidence": "enough_sales",
            }
        ]
    )

    labelled = e004._with_confidence_fields(summary)

    assert labelled.loc[0, "restock_business_ready"] == "no"
    assert labelled.loc[0, "restock_decision_state"] == "blocked_weak_refund_proof"
    assert "weak_refund_proof" in labelled.loc[0, "restock_missing_proof"]


def test_e004_blocks_business_ready_when_current_price_is_missing() -> None:
    summary = pd.DataFrame(
        [
            {
                "sku": "SKU_PRICE",
                "units_sold_source": "roi",
                "units_sold_roi": "4",
                "profit_exvat_gbp": "20",
                "roi_exvat": "1.5",
                "missing_cogs_units": "0",
                "fx_missing_units": "0",
                "reorder_flag": "yes",
                "latest_price_confidence": "listing_price_unproven",
                "current_token_cost_gbp": "2",
                "break_even_price_gbp": "5",
                "refund_proof_state": "api_proved_or_not_applicable",
                "refund_sample_confidence": "enough_sales",
            }
        ]
    )

    labelled = e004._with_confidence_fields(summary)

    assert labelled.loc[0, "restock_business_ready"] == "no"
    assert labelled.loc[0, "restock_decision_state"] == "blocked_missing_current_price"
    assert "missing_current_price" in labelled.loc[0, "restock_missing_proof"]


def test_e005_coverage_summary_explains_roi_and_truth_gap() -> None:
    summary = pd.DataFrame(
        [
            {
                "sku": "SKU_ROI",
                "asof_date": "2026-05-26",
                "units_sold_source": "roi",
                "profit_confidence": "profit_clean",
                "reorder_flag": "yes",
                "restock_business_ready": "yes",
                "missing_roi_reason": "roi_clean",
            },
            {
                "sku": "SKU_VELOCITY",
                "asof_date": "2026-05-26",
                "units_sold_source": "velocity",
                "profit_confidence": "profit_missing",
                "reorder_flag": "yes",
                "restock_business_ready": "no",
                "missing_roi_reason": "velocity_only_sales_truth",
            },
        ]
    )
    report = pd.DataFrame(
        [
            {"sku": "SKU_ROI", "latest_daily_truth_state": "finalized_ledger"},
            {"sku": "SKU_VELOCITY", "latest_daily_truth_state": ""},
        ]
    )
    daily_truth = pd.DataFrame(
        [
            {"sku": "SKU_ROI", "source_state": "finalized_ledger"},
            {"sku": "SKU_ROI", "source_state": "provisional_order_master"},
        ]
    )

    coverage = e005._build_coverage_summary(summary, report, daily_truth).iloc[0].to_dict()

    assert coverage["total_skus"] == 2
    assert coverage["skus_with_roi"] == 1
    assert coverage["velocity_only_skus"] == 1
    assert coverage["skus_missing_profit_proof"] == 1
    assert coverage["restock_business_ready_skus"] == 1
    assert coverage["restock_flagged_missing_roi_skus"] == 1
    assert coverage["skus_with_stock_signal"] == 0
    assert coverage["restock_decision_state_business_ready_clean_skus"] == 0
    assert coverage["restock_blocked_missing_roi_skus"] == 0
    assert coverage["missing_roi_reason_roi_clean_skus"] == 1
    assert coverage["missing_roi_reason_velocity_only_sales_truth_skus"] == 1
    assert coverage["blank_latest_daily_truth_state_rows"] == 1


def test_e005_partial_roi_fixture_counts_missing_reasons() -> None:
    rows = []
    for idx in range(161):
        has_roi = idx < 41
        rows.append(
            {
                "sku": f"SKU{idx:03d}",
                "asof_date": "2026-05-26",
                "units_sold_source": "roi" if has_roi else "velocity",
                "profit_confidence": "profit_clean" if has_roi else "profit_missing",
                "reorder_flag": "no",
                "restock_business_ready": "no",
                "missing_roi_reason": "roi_clean" if has_roi else "velocity_only_sales_truth",
            }
        )
    summary = pd.DataFrame(rows)

    coverage = e005._build_coverage_summary(summary, pd.DataFrame(), pd.DataFrame()).iloc[0].to_dict()

    assert coverage["total_skus"] == 161
    assert coverage["skus_with_roi"] == 41
    assert coverage["velocity_only_skus"] == 120
    assert coverage["missing_roi_reason_velocity_only_sales_truth_skus"] == 120
