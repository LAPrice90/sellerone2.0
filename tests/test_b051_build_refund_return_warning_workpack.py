from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B051_build_refund_return_warning_workpack as b051


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


PREVIEW_COLUMNS = [
    "order_id",
    "sku",
    "repair_lane",
    "repair_readiness",
    "preview_live_write_allowed",
    "roi_or_restock_use_allowed",
    "sellerboard_final_truth_allowed",
    "protected_before_apply",
]


def test_b051_groups_warning_rows_into_safe_manager_lanes(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "repair_lane": "amazon_return_coverage_review",
                "repair_readiness": "blocked_missing_amazon_order_return_proof",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "protected_before_apply": "1",
            },
            {
                "order_id": "ORDER-2",
                "sku": "SKU-B",
                "repair_lane": "protected_disposition_conflict",
                "repair_readiness": "blocked_needs_protected_review",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "protected_before_apply": "1",
            },
            {
                "order_id": "ORDER-3",
                "sku": "SKU-C",
                "repair_lane": "b008_refund_token_marking",
                "repair_readiness": "ready_for_b008_order_sku_reproof",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "protected_before_apply": "1",
            },
            {
                "order_id": "ORDER-4",
                "sku": "SKU-D",
                "repair_lane": "b009_order_aware_sellable_return",
                "repair_readiness": "ready_for_b009_order_aware_preview",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "protected_before_apply": "1",
            },
            {
                "order_id": "ORDER-4B",
                "sku": "SKU-D",
                "repair_lane": "protected_original_return_status_conflict",
                "repair_readiness": "blocked_needs_protected_review",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "protected_before_apply": "1",
            },
            {
                "order_id": "ORDER-4C",
                "sku": "SKU-D",
                "repair_lane": "protected_return_cogs_residual_conflict",
                "repair_readiness": "blocked_needs_protected_review",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "protected_before_apply": "1",
            },
        ],
        PREVIEW_COLUMNS,
    )

    result = b051.build_refund_return_warning_workpack(root=tmp_path, observed_utc="2026-06-03T16:00:00Z")
    workpack = result["workpack"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "ok"
    assert summary["preview_rows"] == "6"
    assert summary["workpack_lanes"] == "6"
    assert summary["unclassified_rows"] == "0"
    assert summary["unsafe_rows"] == "0"
    assert set(workpack["preview_live_write_allowed"]) == {"0"}
    assert set(workpack["roi_or_restock_use_allowed"]) == {"0"}
    assert set(workpack["sellerboard_final_truth_allowed"]) == {"0"}
    assert "needs_protected_disposition_decision_before_live_fix" in set(workpack["manager_state"])
    assert "needs_protected_original_return_status_decision" in set(workpack["manager_state"])
    assert "needs_protected_return_cogs_residual_decision" in set(workpack["manager_state"])
    assert "candidate_for_protected_b009_order_aware_reuse" in set(workpack["manager_state"])


def test_b051_fails_unclassified_lane(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            {
                "order_id": "ORDER-4",
                "sku": "SKU-D",
                "repair_lane": "new_unknown_lane",
                "repair_readiness": "blocked",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "protected_before_apply": "1",
            }
        ],
        PREVIEW_COLUMNS,
    )

    result = b051.build_refund_return_warning_workpack(root=tmp_path, observed_utc="2026-06-03T16:00:00Z")
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "fail"
    assert summary["unclassified_rows"] == "1"


def test_b051_uses_b008_reproof_detail_before_packaging_lane(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            {
                "order_id": "ORDER-5",
                "sku": "SKU-E",
                "repair_lane": "b008_refund_token_marking",
                "repair_readiness": "ready_for_b008_order_sku_reproof",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "protected_before_apply": "1",
            },
            {
                "order_id": "ORDER-6",
                "sku": "SKU-F",
                "repair_lane": "b009_waiting_for_returned_pending_trace",
                "repair_readiness": "blocked_missing_returned_pending_token",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "protected_before_apply": "1",
            },
        ],
        PREVIEW_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_token_reproof_preview.csv",
        [
            {
                "order_id": "ORDER-5",
                "sku": "SKU-E",
                "reproof_lane": "already_closed_or_reused",
                "reproof_readiness": "blocked_bridge_mapping_retest",
            },
            {
                "order_id": "ORDER-6",
                "sku": "SKU-F",
                "reproof_lane": "token_ledger_gap",
                "reproof_readiness": "blocked_missing_allocated_token_in_ledger",
            },
        ],
        ["order_id", "sku", "reproof_lane", "reproof_readiness"],
    )

    result = b051.build_refund_return_warning_workpack(root=tmp_path, observed_utc="2026-06-03T16:00:00Z")
    workpack = result["workpack"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "ok"
    assert summary["unclassified_rows"] == "0"
    assert set(workpack["repair_lane"]) == {"bridge_mapping_retest", "b008_token_ledger_gap"}
    assert "parked_needs_bridge_mapping_retest" in set(workpack["manager_state"])
    assert "parked_needs_token_ledger_proof" in set(workpack["manager_state"])
