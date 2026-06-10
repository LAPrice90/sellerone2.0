from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B067_build_refund_fee_shipping_gap_review as b067


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


SUMMARY_COLUMNS = ["observed_utc", "metric", "status", "value", "proof_label", "notes", "source_path"]
REFUND_COLUMNS = ["order_id", "sku", "api_refund_proof_state"]
RATE_COLUMNS = ["sku", "window_days", "proof_state"]
PERFORMANCE_COLUMNS = [
    "sku",
    "expected_refund_cost_per_unit_gbp",
    "refund_proof_state",
    "b_money_confidence_state",
    "b_bridge_values_safe_for_live_roi",
    "restock_missing_proof",
]
RESTOCK_COLUMNS = [
    "seller_sku",
    "expected_refund_cost_per_unit_gbp",
    "refund_proof_state",
    "profit_input_blockers",
]
LEVEL3_COLUMNS = [
    "money_field",
    "api_source_file",
    "source_amount_types",
    "source_row_count",
    "official_output_file",
    "official_output_field",
    "official_output_row_count",
    "order_master_row_count",
    "required_keys_present",
    "missing_required_keys",
    "proof_label",
    "proof_reason",
    "live_roi_use_allowed",
    "roi_or_restock_use_allowed",
    "sellerboard_final_truth_allowed",
    "bounded_worker_task",
    "retest_rule",
    "protected_stop_rule",
]


def _summary_row(metric: str, value: str, notes: str = "") -> dict[str, str]:
    return {
        "observed_utc": "2026-06-04T10:00:00Z",
        "metric": metric,
        "status": "ok",
        "value": value,
        "proof_label": "",
        "notes": notes,
        "source_path": "sellerboard.csv",
    }


def _write_common_sources(tmp_path: Path, *, gap: bool) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "sellerboard_bridge" / "b_sellerboard_bridge_summary.csv",
        [
            _summary_row("sellerboard_return_rows", "3"),
            _summary_row("sellerboard_return_orders_missing_local_refund_posted_window", "1" if gap else "0"),
            _summary_row("fee_detail_ledger_api_rows", "0" if gap else "4"),
            _summary_row("fee_detail_commission_api_rows", "0" if gap else "2"),
            _summary_row("fee_detail_fba_fee_api_rows", "0" if gap else "2"),
            _summary_row("fee_detail_shipping_fee_api_rows", "0" if gap else "1"),
            _summary_row("fee_detail_other_fee_api_rows", "0"),
            _summary_row("refund_api_proof_state", "sellerboard_bridge_only" if gap else "api_proved"),
            _summary_row("commission_api_proof_state", "not_yet_proven" if gap else "api_proved"),
            _summary_row("fba_fee_api_proof_state", "not_yet_proven" if gap else "api_proved"),
            _summary_row("other_fee_api_proof_state", "api_proved_or_not_applicable"),
            _summary_row("shipping_income_api_proof_state", "api_proved"),
            _summary_row("shipping_fee_api_proof_state", "not_yet_proven" if gap else "api_proved"),
            _summary_row("roi_refund_proof_state", "api_proved_or_not_applicable"),
            _summary_row("roi_money_confidence_state", "bridge_labelled_only" if gap else "api_backed_safe"),
            _summary_row("bridge_values_safe_for_live_roi", "0" if gap else "1"),
        ],
        SUMMARY_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_pnl_bridge.csv",
        [{"order_id": "ORDER-1", "sku": "SKU-A", "api_refund_proof_state": "api_proved"}],
        REFUND_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_sku_refund_rate.csv",
        [{"sku": "SKU-A", "window_days": "30", "proof_state": "api_proved_or_not_applicable"}],
        RATE_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "sku_performance_summary.csv",
        [
            {
                "sku": "SKU-A",
                "expected_refund_cost_per_unit_gbp": "0.25",
                "refund_proof_state": "not_yet_proven" if gap else "api_proved_or_not_applicable",
                "b_money_confidence_state": "bridge_labelled_only" if gap else "api_backed_safe",
                "b_bridge_values_safe_for_live_roi": "0" if gap else "1",
                "restock_missing_proof": "weak_refund_proof;bridge_labelled_money" if gap else "",
            }
        ],
        PERFORMANCE_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "systems" / "O" / "live" / "restock_source_view.csv",
        [
            {
                "seller_sku": "SKU-A",
                "expected_refund_cost_per_unit_gbp": "0.25",
                "refund_proof_state": "not_yet_proven" if gap else "api_proved_or_not_applicable",
                "profit_input_blockers": "refund bridge proof missing" if gap else "",
            }
        ],
        RESTOCK_COLUMNS,
    )


def _level3_row(money_field: str, label: str, source_rows: str = "10") -> dict[str, str]:
    return {
        "money_field": money_field,
        "api_source_file": "out/financial_events_level3_raw.csv",
        "source_amount_types": money_field,
        "source_row_count": source_rows,
        "official_output_file": "out/financial_events_level3_official.csv",
        "official_output_field": money_field,
        "official_output_row_count": "8" if label == "api_source_available" else "0",
        "order_master_row_count": "8" if label == "api_source_available" else "0",
        "required_keys_present": "1",
        "missing_required_keys": "",
        "proof_label": label,
        "proof_reason": "test proof",
        "live_roi_use_allowed": "0",
        "roi_or_restock_use_allowed": "0",
        "sellerboard_final_truth_allowed": "0",
        "bounded_worker_task": "read only",
        "retest_rule": "rerun B068 and B067",
        "protected_stop_rule": "stop before live use",
    }


def _write_level3_proof_map(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_level3_fee_shipping_api_proof_map.csv",
        [
            _level3_row("commission", "api_source_available"),
            _level3_row("fba_fee", "api_source_available"),
            _level3_row("shipping_income", "api_source_available"),
            _level3_row("shipping_chargeback_or_cost", "api_source_available"),
            _level3_row("refund_fee_reversals", "api_source_available"),
            _level3_row("fee_detail_ledger_api", "api_source_missing", "0"),
        ],
        LEVEL3_COLUMNS,
    )


def test_b067_labels_refund_fee_shipping_gaps_without_allowing_live_roi(tmp_path: Path) -> None:
    _write_common_sources(tmp_path, gap=True)

    result = b067.build_refund_fee_shipping_gap_review(root=tmp_path, observed_utc="2026-06-04T10:00:00Z")
    review = result["review"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}
    labels = {row["money_area"]: row["manager_money_label"] for _, row in review.iterrows()}

    assert summary["status"] == "warn"
    assert labels["api_refund_money"] == "api_proved"
    assert labels["sellerboard_return_refund_gap"] == "sellerboard_bridge_estimate"
    assert labels["commission_fee"] == "not_yet_proven"
    assert labels["fba_fee"] == "not_yet_proven"
    assert labels["shipping_fee"] == "not_yet_proven"
    assert labels["e_roi_confidence"] == "sellerboard_bridge_estimate"
    assert labels["o_restock_confidence"] == "not_yet_proven"
    assert set(review["live_roi_use_allowed"]) == {"0"}
    assert set(review["roi_or_restock_use_allowed"]) == {"0"}
    assert set(review["sellerboard_final_truth_allowed"]) == {"0"}


def test_b067_uses_b068_level3_proof_without_clearing_unclear_shipping_cost(tmp_path: Path) -> None:
    _write_common_sources(tmp_path, gap=True)
    _write_level3_proof_map(tmp_path)

    result = b067.build_refund_fee_shipping_gap_review(root=tmp_path, observed_utc="2026-06-04T10:00:00Z")
    review = result["review"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}
    labels = {row["money_area"]: row["manager_money_label"] for _, row in review.iterrows()}
    source_metrics = {row["money_area"]: row["source_metric"] for _, row in review.iterrows()}

    assert summary["status"] == "warn"
    assert summary["level3_connected_api_proved_rows"] == "5"
    assert summary["level3_connected_not_yet_proven_rows"] == "0"
    assert labels["commission_fee"] == "api_proved"
    assert labels["fba_fee"] == "api_proved"
    assert labels["shipping_income"] == "api_proved"
    assert labels["refund_fee_reversals"] == "api_proved"
    assert labels["shipping_fee"] == "api_proved"
    assert source_metrics["commission_fee"] == "b_level3_fee_shipping_api_proof_map.commission"
    assert source_metrics["shipping_fee"] == "b_level3_fee_shipping_api_proof_map.shipping_chargeback_or_cost"
    assert set(review["live_roi_use_allowed"]) == {"0"}
    assert set(review["roi_or_restock_use_allowed"]) == {"0"}
    assert set(review["sellerboard_final_truth_allowed"]) == {"0"}


def test_b067_resolves_sellerboard_return_gap_when_refund_bridge_has_api_proof(tmp_path: Path) -> None:
    _write_common_sources(tmp_path, gap=True)
    summary_path = tmp_path / "out" / "systems" / "M" / "sellerboard_bridge" / "b_sellerboard_bridge_summary.csv"
    summary = pd.read_csv(summary_path, dtype=str).fillna("")
    summary.loc[
        summary["metric"] == "sellerboard_return_orders_missing_local_refund_posted_window",
        "notes",
    ] = "ORDER-1"
    summary.to_csv(summary_path, index=False)

    result = b067.build_refund_fee_shipping_gap_review(root=tmp_path, observed_utc="2026-06-04T10:00:00Z")
    review = result["review"]
    row = review[review["money_area"] == "sellerboard_return_refund_gap"].iloc[0]

    assert row["manager_money_label"] == "api_proved"
    assert row["api_proof_state"] == "api_proved"
    assert row["gap_rows"] == "0"
    assert "api_proved_gap_orders=1" in row["source_value"]


def test_b067_treats_downstream_consumer_warnings_as_handoff_not_b_source_gap(tmp_path: Path) -> None:
    _write_common_sources(tmp_path, gap=True)
    _write_level3_proof_map(tmp_path)
    summary_path = tmp_path / "out" / "systems" / "M" / "sellerboard_bridge" / "b_sellerboard_bridge_summary.csv"
    summary = pd.read_csv(summary_path, dtype=str).fillna("")
    summary.loc[
        summary["metric"] == "sellerboard_return_orders_missing_local_refund_posted_window",
        "notes",
    ] = "ORDER-1"
    summary.to_csv(summary_path, index=False)

    result = b067.build_refund_fee_shipping_gap_review(root=tmp_path, observed_utc="2026-06-04T10:00:00Z")
    summary_rows = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}
    labels = {row["money_area"]: row["manager_money_label"] for _, row in result["review"].iterrows()}

    assert summary_rows["status"] == "ok"
    assert summary_rows["b_source_chain_state"] == "api_proved"
    assert summary_rows["b_source_handoff_ready"] == "1"
    assert summary_rows["b_source_sellerboard_bridge_estimate_rows"] == "0"
    assert summary_rows["b_source_not_yet_proven_rows"] == "0"
    assert int(summary_rows["downstream_consumer_warning_rows"]) > 0
    assert labels["e_roi_confidence"] == "sellerboard_bridge_estimate"
    assert labels["o_restock_confidence"] == "not_yet_proven"


def test_b067_clears_when_money_chain_is_api_backed(tmp_path: Path) -> None:
    _write_common_sources(tmp_path, gap=False)

    result = b067.build_refund_fee_shipping_gap_review(root=tmp_path, observed_utc="2026-06-04T10:00:00Z")
    review = result["review"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "ok"
    assert set(review["manager_money_label"]) == {"api_proved"}
    assert summary["bridge_values_safe_for_live_roi"] == "1"


def test_b067_writes_review_and_summary(tmp_path: Path) -> None:
    _write_common_sources(tmp_path, gap=True)

    result = b067.build_refund_fee_shipping_gap_review(root=tmp_path, observed_utc="2026-06-04T10:00:00Z")
    paths = b067.write_refund_fee_shipping_gap_review_outputs(result, root=tmp_path)

    assert paths["review"].exists()
    assert paths["summary"].exists()
