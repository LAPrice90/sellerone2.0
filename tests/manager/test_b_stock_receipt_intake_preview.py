from __future__ import annotations

import csv
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sellerone_manager.b_stock_receipt_intake_preview import build_b_stock_receipt_intake_preview


def _write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def test_stock_receipt_intake_preview_classifies_duplicate_and_partial_rows(tmp_path: Path) -> None:
    _write_csv_rows(
        tmp_path / "out" / "stock_receipts_latest.csv",
        ["row_num", "seller_sku", "qty", "order_key"],
        [{"row_num": "2", "seller_sku": "A2-T2AC-TW3L", "qty": "120", "order_key": "existing-row-88"}],
    )
    _write_csv_rows(
        tmp_path / "out" / "token_ledger_live.csv",
        ["token_id", "seller_sku", "source_order_key"],
        [
            *[
                {"token_id": f"vf-{index}", "seller_sku": "VF-3T0K-DR5O", "source_order_key": "same-vf-key"}
                for index in range(300)
            ],
            *[
                {"token_id": f"mw-{index}", "seller_sku": "MW-9K5M-VKW8", "source_order_key": "same-mw-key"}
                for index in range(20)
            ],
        ],
    )
    header = ["intake_date", "seller_sku", "qty", "cost_per_unit", "OrderKey", "status"]
    sheet_rows = [
        ["28/04/2026", "A2-T2AC-TW3L", "120", "4.44", "existing-row-88", "APPLIED"],
        ["28/04/2026", "6V-EEC1-2S9Z", "250", "2.22", "new-6v-key", ""],
        ["18/03/2026", "MW-9K5M-VKW8", "40", "13.65", "same-mw-key", ""],
        ["19/11/2025", "VF-3T0K-DR5O", "100", "2.05", "same-vf-key", ""],
    ]

    result = build_b_stock_receipt_intake_preview(
        root=tmp_path,
        observed_utc="2026-06-05T10:00:00Z",
        sheet_values=(header, sheet_rows),
        orders_sheet_values=(["SKU", "Ordered", "Delivered", "Sent to FBA", "To ship", "OrderKey"], []),
    )
    by_sku = {row["seller_sku"]: row for row in result.preview_rows}
    summary = {row["metric"]: row["value"] for row in result.summary_rows}

    assert set(by_sku) == {"6V-EEC1-2S9Z", "MW-9K5M-VKW8", "VF-3T0K-DR5O"}
    assert by_sku["6V-EEC1-2S9Z"]["manager_classification"] == "new_receipt_candidate"
    assert by_sku["6V-EEC1-2S9Z"]["tokens_processor_would_create"] == "250"
    assert by_sku["MW-9K5M-VKW8"]["manager_classification"] == "existing_order_key_receipt_row_ready_for_token_creator"
    assert by_sku["MW-9K5M-VKW8"]["tokens_processor_would_create"] == "40"
    assert by_sku["MW-9K5M-VKW8"]["manager_expected_tokens_if_new_shipment"] == "40"
    assert by_sku["MW-9K5M-VKW8"]["token_creator_proof_gap_if_unprocessed"] == "40"
    assert by_sku["VF-3T0K-DR5O"]["manager_classification"] == "existing_order_key_receipt_row_ready_for_token_creator"
    assert by_sku["VF-3T0K-DR5O"]["tokens_processor_would_create"] == "100"
    assert by_sku["VF-3T0K-DR5O"]["manager_expected_tokens_if_new_shipment"] == "100"
    assert by_sku["VF-3T0K-DR5O"]["token_creator_proof_gap_if_unprocessed"] == "100"
    assert summary["status"] == "proof_needed"
    assert summary["protected_decision_rows"] == "3"
    assert summary["tokens_processor_would_create_total"] == "390"
    assert summary["manager_expected_tokens_if_new_shipment_total"] == "390"
    assert summary["token_creator_proof_gap_if_unprocessed_total"] == "390"


def test_stock_receipt_intake_preview_flags_orders_shipment_local_proof_gap(tmp_path: Path) -> None:
    _write_csv_rows(
        tmp_path / "out" / "orders_sheet_orders.csv",
        ["SKU", "Name", "Order Date", "Ordered", "Delivered", "Sent to FBA", "To ship", "OrderKey"],
        [
            {
                "SKU": "",
                "Name": "",
                "Order Date": "",
                "Ordered": "",
                "Delivered": "",
                "Sent to FBA": "",
                "To ship": "",
                "OrderKey": "cyn20-order-key",
            }
        ],
    )
    old_mtime = datetime(2026, 4, 22, 11, 53, 15, tzinfo=timezone.utc).timestamp()
    os.utime(tmp_path / "out" / "orders_sheet_orders.csv", (old_mtime, old_mtime))
    token_header = ["intake_date", "seller_sku", "qty", "cost_per_unit", "OrderKey", "status"]
    orders_header = ["SKU", "Name", "Order Date", "Ordered", "Delivered", "Sent to FBA", "To ship", "OrderKey"]
    orders_rows = [
        [
            "6V-EEC1-2S9Z",
            "3 X Everbuild CYN20 20g General Purpose Industrial Superglue",
            "28/04/26",
            "750",
            "750",
            "500",
            "Send",
            "cyn20-order-key",
        ]
    ]

    result = build_b_stock_receipt_intake_preview(
        root=tmp_path,
        observed_utc="2026-06-05T10:00:00Z",
        sheet_values=(token_header, []),
        orders_sheet_values=(orders_header, orders_rows),
    )
    summary = {row["metric"]: row["value"] for row in result.summary_rows}

    assert len(result.orders_shipment_rows) == 1
    assert result.orders_shipment_rows[0]["seller_sku"] == "6V-EEC1-2S9Z"
    assert result.orders_shipment_rows[0]["local_match_status"] == "local_orders_proof_mismatch"
    assert summary["status"] == "proof_needed"
    assert summary["orders_shipment_rows"] == "1"
    assert summary["orders_shipment_local_gap_rows"] == "1"
    assert summary["orders_shipment_remaining_to_send_total"] == "250"
    assert summary["local_orders_file_stale"] == "1"
    assert summary["orders_staged_refresh_rows"] == "1"
    assert result.orders_staged_refresh_rows[0] == orders_header
    assert result.orders_staged_refresh_rows[1] == orders_rows[0]
