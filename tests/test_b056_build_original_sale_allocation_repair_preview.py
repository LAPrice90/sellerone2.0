from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B056_build_original_sale_allocation_repair_preview as b056


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def test_b056_classifies_legacy_baseline_candidate(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_allocation_gap_audit.csv",
        [{"order_id": "ORDER-1", "sku": "SKU-A", "allocation_gap_conclusion": "order_seen_allocation_missing"}],
        ["order_id", "sku", "allocation_gap_conclusion"],
    )
    _write_csv(
        tmp_path / "out" / "orders_missing_tokens.csv",
        [{"Order ID": "ORDER-1", "SKU": "SKU-A", "Quantity Ordered": "1", "missing_token_reason_class": "missing"}],
        ["Order ID", "SKU", "Quantity Ordered", "missing_token_reason_class"],
    )
    _write_csv(
        tmp_path / "out" / "token_shortages_by_sku.csv",
        [{"seller_sku": "SKU-A", "shortage_class": "legacy_baseline_gap", "next_action": "needs_user_decision"}],
        ["seller_sku", "shortage_class", "next_action"],
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [{"seller_sku": "SKU-A", "cost_per_unit": "1.23", "currency": "GBP", "token_id": "TOK-1"}],
        ["seller_sku", "cost_per_unit", "currency", "token_id"],
    )

    result = b056.build_original_sale_allocation_repair_preview(root=tmp_path, observed_utc="2026-06-03T16:00:00Z")
    preview = result["preview"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "ok"
    assert summary["legacy_baseline_candidate_rows"] == "1"
    assert preview.iloc[0]["repair_lane"] == "protected_legacy_baseline_allocation_candidate"
    assert preview.iloc[0]["preview_live_write_allowed"] == "0"
    assert preview.iloc[0]["protected_before_apply"] == "1"


def test_b056_classifies_runtime_adjustment_candidate(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_allocation_gap_audit.csv",
        [{"order_id": "ORDER-1", "sku": "SKU-A", "allocation_gap_conclusion": "order_seen_allocation_missing"}],
        ["order_id", "sku", "allocation_gap_conclusion"],
    )
    _write_csv(
        tmp_path / "out" / "orders_missing_tokens.csv",
        [{"Order ID": "ORDER-1", "SKU": "SKU-A", "Quantity Ordered": "1"}],
        ["Order ID", "SKU", "Quantity Ordered"],
    )
    _write_csv(
        tmp_path / "out" / "token_shortages_by_sku.csv",
        [{"seller_sku": "SKU-A", "shortage_class": "runtime_adjustment_pending", "next_action": "rerun_b009"}],
        ["seller_sku", "shortage_class", "next_action"],
    )
    _write_csv(
        tmp_path / "out" / "token_cogs_ledger.csv",
        [{"seller_sku": "SKU-A", "token_cost": "2.34", "currency": "GBP", "token_id": "TOK-1"}],
        ["seller_sku", "token_cost", "currency", "token_id"],
    )

    result = b056.build_original_sale_allocation_repair_preview(root=tmp_path, observed_utc="2026-06-03T16:00:00Z")
    preview = result["preview"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "ok"
    assert summary["runtime_adjustment_candidate_rows"] == "1"
    assert preview.iloc[0]["repair_lane"] == "protected_runtime_adjustment_allocation_candidate"
    assert preview.iloc[0]["roi_or_restock_use_allowed"] == "0"
