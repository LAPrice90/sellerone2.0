from pathlib import Path

from scripts.flows.O.O025_build_token_cost_trust_gate import build_token_cost_trust_gate


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_o025_blocks_weak_fallback_cost_from_restock_use(tmp_path: Path) -> None:
    _write(
        tmp_path / "out" / "sku_performance_summary.csv",
        "sku,current_token_cost_gbp,asof_date\n6V-EEC1-2S9Z,4.35,2026-06-05\nSKU-OK,2.00,2026-06-05\n",
    )
    _write(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_fallback_token_cost_audit.csv",
        "token_id,seller_sku,cost_per_unit,cost_proof_state,manager_label,roi_or_restock_use_allowed\n"
        "ADJ-1,6V-EEC1-2S9Z,4.35,fallback_cost_weak_latest_token,weak_fallback_cost,0\n",
    )

    live, health = build_token_cost_trust_gate(root=tmp_path, proof_utc="2026-06-05T12:00:00Z")

    by_sku = live.set_index("seller_sku")
    assert by_sku.loc["6V-EEC1-2S9Z", "token_cost_trust_state"] == "weak_fallback_cost"
    assert by_sku.loc["6V-EEC1-2S9Z", "safe_for_clean_buy"] == "0"
    assert by_sku.loc["SKU-OK", "token_cost_trust_state"] == "trusted"
    assert "weak_fallback=1" in health.iloc[0]["value"]


def test_o025_blocks_b071_batch_link_gap_from_clean_buy(tmp_path: Path) -> None:
    _write(
        tmp_path / "out" / "sku_performance_summary.csv",
        "sku,current_token_cost_gbp,asof_date\nA2-T2AC-TW3L,4.51,2026-06-05\nSKU-OK,2.00,2026-06-05\n",
    )
    _write(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_fallback_token_cost_audit.csv",
        "token_id,seller_sku,cost_per_unit,cost_proof_state,manager_label,roi_or_restock_use_allowed\n"
        "ADJ-1,A2-T2AC-TW3L,4.51,fallback_cost_source_token_proved,source_token_proved,0\n",
    )
    _write(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_fallback_cost_proof_reconciliation.csv",
        "token_id,seller_sku,reconciliation_rule,clean_h_o_trust_allowed\n"
        "ADJ-1,A2-T2AC-TW3L,requires_batch_link_proof,0\n",
    )

    live, health = build_token_cost_trust_gate(root=tmp_path, proof_utc="2026-06-05T12:00:00Z")

    by_sku = live.set_index("seller_sku")
    assert by_sku.loc["A2-T2AC-TW3L", "token_cost_trust_state"] == "weak_fallback_cost"
    assert by_sku.loc["A2-T2AC-TW3L", "token_cost_trust_basis"] == "b_fallback_cost_reconciliation_requires_batch_link_proof"
    assert "requires_batch_link_proof" in by_sku.loc["A2-T2AC-TW3L", "token_cost_trust_blockers"]
    assert by_sku.loc["A2-T2AC-TW3L", "safe_for_clean_buy"] == "0"
    assert by_sku.loc["SKU-OK", "token_cost_trust_state"] == "trusted"
    assert "weak_fallback=1" in health.iloc[0]["value"]


def test_o025_marks_missing_b_audit_as_not_verified(tmp_path: Path) -> None:
    _write(
        tmp_path / "out" / "sku_performance_summary.csv",
        "sku,current_token_cost_gbp,asof_date\nSKU-1,2.00,2026-06-05\n",
    )

    live, health = build_token_cost_trust_gate(root=tmp_path, proof_utc="2026-06-05T12:00:00Z")

    assert live.iloc[0]["token_cost_trust_state"] == "not_verified"
    assert live.iloc[0]["safe_for_po"] == "0"
    assert "not_verified=1" in health.iloc[0]["value"]


def test_o025_marks_zero_token_cost_as_missing(tmp_path: Path) -> None:
    _write(
        tmp_path / "out" / "sku_performance_summary.csv",
        "sku,current_token_cost_gbp,asof_date\nSKU-1,0,2026-06-05\n",
    )
    _write(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_fallback_token_cost_audit.csv",
        "token_id,seller_sku,cost_per_unit,cost_proof_state,manager_label,roi_or_restock_use_allowed\n",
    )

    live, health = build_token_cost_trust_gate(root=tmp_path, proof_utc="2026-06-05T12:00:00Z")

    assert live.iloc[0]["token_cost_trust_state"] == "missing_token_cost"
    assert live.iloc[0]["token_cost_trust_blockers"] == "missing_token_cost"
    assert "missing_token_cost=1" in health.iloc[0]["value"]
