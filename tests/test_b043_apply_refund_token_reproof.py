from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B043_apply_refund_token_reproof as b043


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


PREVIEW_COLUMNS = [
    "order_id",
    "sku",
    "reproof_lane",
    "reproof_readiness",
    "ledger_allocated_token_ids",
    "b008_event_ids",
    "preview_live_write_allowed",
    "roi_or_restock_use_allowed",
    "sellerboard_final_truth_allowed",
]


def test_b043_refuses_without_protected_approval(tmp_path: Path) -> None:
    result = b043.apply_refund_token_reproof(root=tmp_path, approve_protected_b008_repair=False)

    assert result.status == "blocked_needs_approval"
    assert result.applied_rows == 0
    assert (tmp_path / "out" / "systems" / "B" / "refunds" / "b008_refund_token_reproof_manifest.json").exists()


def test_b043_applies_b008_reproof_to_local_proof_files_only(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_token_reproof_preview.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "reproof_lane": "b008_refund_token_marking",
                "reproof_readiness": "ready_for_b008_order_sku_reproof",
                "ledger_allocated_token_ids": "TOKEN-1",
                "b008_event_ids": "REF-1",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
        PREVIEW_COLUMNS,
    )
    ledger_cols = [
        "token_id",
        "seller_sku",
        "status",
        "allocated_order_id",
        "return_order_id",
        "return_date",
        "return_event_id",
        "last_return_order_id",
        "last_return_date",
        "last_return_event_id",
        "notes",
    ]
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-1",
                "seller_sku": "SKU-A",
                "status": "allocated",
                "allocated_order_id": "ORDER-1",
                "return_order_id": "",
                "return_date": "",
                "return_event_id": "",
                "last_return_order_id": "",
                "last_return_date": "",
                "last_return_event_id": "",
                "notes": "",
            }
        ],
        ledger_cols,
    )
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "live" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-1",
                "seller_sku": "SKU-A",
                "status": "allocated",
                "allocated_order_id": "ORDER-1",
                "return_order_id": "",
                "return_date": "",
                "return_event_id": "",
                "last_return_order_id": "",
                "last_return_date": "",
                "last_return_event_id": "",
                "notes": "",
            }
        ],
        ledger_cols,
    )
    _write_csv(
        tmp_path / "out" / "refund_token_events.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "refund_date": "2026-05-20T10:00:00Z",
                "requested_qty": "1",
                "applied_qty": "0",
                "status": "partial",
                "note": "",
                "refund_event_id": "REF-1",
                "event_ts": "2026-05-20T10:01:00Z",
            }
        ],
        ["order_id", "sku", "refund_date", "requested_qty", "applied_qty", "status", "note", "refund_event_id", "event_ts"],
    )

    result = b043.apply_refund_token_reproof(
        root=tmp_path,
        approve_protected_b008_repair=True,
        observed_utc="2026-06-03T11:30:00Z",
    )

    assert result.status == "applied"
    assert result.token_rows_updated == 1
    assert result.refund_event_rows_updated == 1
    assert result.snapshot_dir is not None
    assert (result.snapshot_dir / "token_ledger_live.csv").exists()

    ledger = pd.read_csv(tmp_path / "out" / "token_ledger_live.csv", dtype=str).fillna("")
    assert ledger.loc[0, "status"] == "returned_pending"
    assert ledger.loc[0, "return_order_id"] == "ORDER-1"
    assert ledger.loc[0, "return_event_id"] == "REF-1"

    events = pd.read_csv(tmp_path / "out" / "refund_token_events.csv", dtype=str).fillna("")
    assert events.loc[0, "applied_qty"] == "1"
    assert events.loc[0, "status"] == "ok"
    assert "controlled_b008_local_reproof" in events.loc[0, "note"]


def test_b043_blocks_active_b_owner_without_matching_maintenance(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_token_reproof_preview.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "reproof_lane": "b008_refund_token_marking",
                "reproof_readiness": "ready_for_b008_order_sku_reproof",
                "ledger_allocated_token_ids": "TOKEN-1",
                "b008_event_ids": "REF-1",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
        PREVIEW_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [{"token_id": "TOKEN-1", "seller_sku": "SKU-A", "status": "allocated", "allocated_order_id": "ORDER-1"}],
        ["token_id", "seller_sku", "status", "allocated_order_id"],
    )
    _write_csv(
        tmp_path / "out" / "refund_token_events.csv",
        [{"order_id": "ORDER-1", "sku": "SKU-A", "refund_event_id": "REF-1", "refund_date": "2026-05-20", "requested_qty": "1", "applied_qty": "0", "status": "partial"}],
        ["order_id", "sku", "refund_event_id", "refund_date", "requested_qty", "applied_qty", "status"],
    )
    lock = tmp_path / "out" / "systems" / "B" / "live" / "B_cycle.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("B|pid=123|heartbeat=2026-06-03T17:00:00Z", encoding="utf-8")

    result = b043.apply_refund_token_reproof(
        root=tmp_path,
        approve_protected_b008_repair=True,
        observed_utc="2026-06-03T17:00:00Z",
    )

    assert result.status == "blocked_active_b_owner"
    assert result.applied_rows == 0


def test_b043_applies_inside_matching_maintenance(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_token_reproof_preview.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "reproof_lane": "b008_refund_token_marking",
                "reproof_readiness": "ready_for_b008_order_sku_reproof",
                "ledger_allocated_token_ids": "TOKEN-1",
                "b008_event_ids": "REF-1",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
        PREVIEW_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [{"token_id": "TOKEN-1", "seller_sku": "SKU-A", "status": "allocated", "allocated_order_id": "ORDER-1"}],
        ["token_id", "seller_sku", "status", "allocated_order_id"],
    )
    _write_csv(
        tmp_path / "out" / "refund_token_events.csv",
        [{"order_id": "ORDER-1", "sku": "SKU-A", "refund_event_id": "REF-1", "refund_date": "2026-05-20", "requested_qty": "1", "applied_qty": "0", "status": "partial"}],
        ["order_id", "sku", "refund_event_id", "refund_date", "requested_qty", "applied_qty", "status"],
    )
    request_id = "B043_TEST"
    lock = tmp_path / "out" / "systems" / "B" / "live" / "B_cycle.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("B|pid=123|heartbeat=2026-06-03T17:00:00Z", encoding="utf-8")
    requested = tmp_path / "out" / "locks" / "maintenance.requested"
    ready = tmp_path / "out" / "locks" / "maintenance.ready"
    requested.parent.mkdir(parents=True, exist_ok=True)
    requested.write_text(f"requested_by=codex_b043|request_id={request_id}", encoding="utf-8")
    ready.write_text(f"B_READY|pid=123|ts=2026-06-03T17:00:00Z|request_id={request_id}", encoding="utf-8")

    result = b043.apply_refund_token_reproof(
        root=tmp_path,
        approve_protected_b008_repair=True,
        observed_utc="2026-06-03T17:00:00Z",
        maintenance_request_id=request_id,
    )

    assert result.status == "applied"
    assert result.applied_rows == 1


def test_b043_blocks_unsafe_preview_flags(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_token_reproof_preview.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "reproof_lane": "b008_refund_token_marking",
                "reproof_readiness": "ready_for_b008_order_sku_reproof",
                "ledger_allocated_token_ids": "TOKEN-1",
                "b008_event_ids": "REF-1",
                "preview_live_write_allowed": "1",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
        PREVIEW_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [{"token_id": "TOKEN-1", "seller_sku": "SKU-A", "status": "allocated", "allocated_order_id": "ORDER-1"}],
        ["token_id", "seller_sku", "status", "allocated_order_id"],
    )
    _write_csv(
        tmp_path / "out" / "refund_token_events.csv",
        [{"order_id": "ORDER-1", "sku": "SKU-A", "refund_event_id": "REF-1", "refund_date": "2026-05-20", "requested_qty": "1", "applied_qty": "0", "status": "partial"}],
        ["order_id", "sku", "refund_event_id", "refund_date", "requested_qty", "applied_qty", "status"],
    )

    result = b043.apply_refund_token_reproof(root=tmp_path, approve_protected_b008_repair=True)

    assert result.status == "blocked_validation_failed"
    assert result.applied_rows == 0
