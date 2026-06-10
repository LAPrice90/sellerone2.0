from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.flows.B import B070_build_fallback_token_cost_audit as b070


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def test_b070_labels_receipt_proved_and_weak_fallback_costs(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "SRC-1",
                "seller_sku": "SKU-1",
                "cost_per_unit": "2.50",
                "currency": "GBP",
                "status": "allocated",
                "received_date": "2026-01-01",
                "created_at": "2026-01-01T00:00:00Z",
                "source": "",
                "source_batch_id": "",
                "source_order_key": "",
                "notes": "",
            },
            {
                "token_id": "ADJ-SKU-1-EVT-1-0001",
                "seller_sku": "SKU-1",
                "cost_per_unit": "2.50",
                "currency": "GBP",
                "status": "available",
                "received_date": "2026-02-01",
                "created_at": "2026-02-01T00:00:00Z",
                "source": "stock_adjustment_fallback",
                "source_batch_id": "EVT-1",
                "source_order_key": "",
                "notes": "adjustment_fallback_create:EVT-1",
            },
            {
                "token_id": "SRC-2",
                "seller_sku": "SKU-2",
                "cost_per_unit": "3.10",
                "currency": "GBP",
                "status": "allocated",
                "received_date": "2026-01-01",
                "created_at": "2026-01-01T00:00:00Z",
                "source": "",
                "source_batch_id": "",
                "source_order_key": "",
                "notes": "",
            },
            {
                "token_id": "ADJ-SKU-2-EVT-2-0001",
                "seller_sku": "SKU-2",
                "cost_per_unit": "3.10",
                "currency": "GBP",
                "status": "available",
                "received_date": "2026-02-01",
                "created_at": "2026-02-01T00:00:00Z",
                "source": "stock_adjustment_fallback",
                "source_batch_id": "EVT-2",
                "source_order_key": "",
                "notes": "adjustment_fallback_create:EVT-2",
            },
        ],
    )
    _write_csv(
        tmp_path / "out" / "stock_receipts_latest.csv",
        [
            {
                "seller_sku": "SKU-1",
                "cost_per_unit": "2.50",
                "status": "APPLIED",
                "batch_id": "SR-1",
                "order_key": "PO-1",
            }
        ],
    )

    result = b070.build_fallback_token_cost_audit(root=tmp_path, observed_utc="2026-06-05T13:00:00Z")
    audit = result["audit"]

    by_token = {row["token_id"]: row for _, row in audit.iterrows()}
    assert by_token["ADJ-SKU-1-EVT-1-0001"]["cost_proof_state"] == "fallback_cost_receipt_proved"
    assert by_token["ADJ-SKU-1-EVT-1-0001"]["manager_label"] == "api_or_receipt_proved"
    assert by_token["ADJ-SKU-2-EVT-2-0001"]["cost_proof_state"] == "fallback_cost_weak_latest_token"
    assert by_token["ADJ-SKU-2-EVT-2-0001"]["manager_label"] == "weak_fallback_cost"
    assert by_token["ADJ-SKU-2-EVT-2-0001"]["roi_or_restock_use_allowed"] == "0"


def test_b070_writes_outputs(tmp_path: Path) -> None:
    path = tmp_path / "out" / "token_ledger_live.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(columns=["token_id", "seller_sku", "cost_per_unit", "source", "notes"]).to_csv(path, index=False)

    result = b070.build_fallback_token_cost_audit(root=tmp_path, observed_utc="2026-06-05T13:00:00Z")
    paths = b070.write_fallback_token_cost_audit_outputs(result, root=tmp_path)

    assert paths["audit"].exists()
    assert paths["summary"].exists()
    summary = pd.read_csv(paths["summary"], dtype=str).fillna("")
    assert dict(zip(summary["metric"], summary["value"]))["fallback_token_rows"] == "0"
