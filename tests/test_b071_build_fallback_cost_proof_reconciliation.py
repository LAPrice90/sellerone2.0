from pathlib import Path

import pandas as pd

from scripts.flows.B import B071_build_fallback_cost_proof_reconciliation as b071


def test_b071_blocks_clean_trust_when_sheet_cost_disagrees(tmp_path: Path) -> None:
    audit_path = tmp_path / b071.B070_AUDIT
    sheet_path = tmp_path / b071.SHEET_MISMATCH
    h_path = tmp_path / b071.H_NEXT_AVAILABLE
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    sheet_path.parent.mkdir(parents=True, exist_ok=True)
    h_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "token_id": "ADJ-1",
                "seller_sku": "A2-T2AC-TW3L",
                "status": "available",
                "cost_proof_state": "fallback_cost_source_token_proved",
                "manager_label": "source_token_proved",
                "cost_per_unit": "4.51",
            },
            {
                "token_id": "ADJ-2",
                "seller_sku": "SKU-OK",
                "status": "available",
                "cost_proof_state": "fallback_cost_source_token_proved",
                "manager_label": "source_token_proved",
                "cost_per_unit": "2.25",
            },
        ]
    ).to_csv(audit_path, index=False)
    pd.DataFrame(
        [
            {
                "issue": "fallback_cost_differs_from_latest_prior_sheet_cost",
                "seller_sku": "A2-T2AC-TW3L",
                "token_id": "ADJ-1",
                "expected_prior_sheet_cost": "4.44",
                "expected_sheet_row": "33",
                "expected_sheet_intake_date": "09/02/2026",
                "latest_sheet_cost_any_date": "4.44",
            },
            {
                "issue": "ok",
                "seller_sku": "SKU-OK",
                "token_id": "ADJ-2",
                "expected_prior_sheet_cost": "2.25",
                "expected_sheet_row": "10",
                "expected_sheet_intake_date": "01/01/2026",
                "latest_sheet_cost_any_date": "2.25",
            },
        ]
    ).to_csv(sheet_path, index=False)
    pd.DataFrame(
        [
            {
                "issue": "h_next_available_cost_differs_from_latest_prior_sheet_cost",
                "seller_sku": "A2-T2AC-TW3L",
            }
        ]
    ).to_csv(h_path, index=False)

    result = b071.build_fallback_cost_proof_reconciliation(root=tmp_path, observed_utc="2026-06-05T14:00:00Z")
    recon = result["reconciliation"]
    by_token = recon.set_index("token_id")
    summary = dict(zip(result["summary"]["metric"], result["summary"]["value"]))

    assert by_token.loc["ADJ-1", "reconciliation_rule"] == "requires_batch_link_proof"
    assert by_token.loc["ADJ-1", "clean_h_o_trust_allowed"] == "0"
    assert by_token.loc["ADJ-2", "reconciliation_rule"] == "source_token_cost_is_valid"
    assert summary["requires_batch_link_proof_rows"] == "1"
    assert summary["h_next_available_blocked_skus"] == "A2-T2AC-TW3L"


def test_b071_writes_outputs(tmp_path: Path) -> None:
    (tmp_path / b071.B070_AUDIT).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(columns=["token_id", "seller_sku"]).to_csv(tmp_path / b071.B070_AUDIT, index=False)

    result = b071.build_fallback_cost_proof_reconciliation(root=tmp_path, observed_utc="2026-06-05T14:00:00Z")
    paths = b071.write_fallback_cost_proof_reconciliation_outputs(result, root=tmp_path)

    assert paths["reconciliation"].exists()
    assert paths["summary"].exists()
