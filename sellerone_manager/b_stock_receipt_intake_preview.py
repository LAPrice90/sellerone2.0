from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.tools.process_stock_receipts_sheet import (  # noqa: E402
    INTAKE_SHEET_ID,
    INTAKE_TAB,
    ORDER_KEY_CANDIDATES,
    get_gspread_client,
    parse_int,
)


OUTPUT_DIR_NAME = "b_stock_receipt_token_sync"
PREVIEW_CSV_NAME = "b_stock_receipt_intake_preview.csv"
SUMMARY_CSV_NAME = "b_stock_receipt_intake_preview_summary.csv"
SUMMARY_JSON_NAME = "b_stock_receipt_intake_preview_summary.json"
ORDERS_SHIPMENT_CSV_NAME = "b_orders_shipment_local_proof.csv"
ORDERS_STAGED_REFRESH_CSV_NAME = "b_orders_sheet_orders_staged_refresh.csv"

ORDERS_SHEET_ID = "1H_EDAYfB_xgGvnW1esOMwWsHs2wBXYoOABcMs7SWcrY"
ORDERS_TAB = "Orders"

PREVIEW_COLUMNS = [
    "sheet_row_num",
    "intake_date",
    "seller_sku",
    "sheet_qty",
    "cost_per_unit",
    "order_key",
    "sheet_status",
    "local_receipt_row_seen",
    "existing_token_count_for_key_sku",
    "tokens_processor_would_create",
    "manager_expected_tokens_if_new_shipment",
    "token_creator_proof_gap_if_unprocessed",
    "manager_classification",
    "protected_decision_required",
    "manager_expectation",
    "mot_proof_check",
    "bounded_worker_task",
    "retest_rule",
    "protected_stop_rule",
]

SUMMARY_COLUMNS = ["metric", "value"]

ORDERS_SHIPMENT_COLUMNS = [
    "sheet_row_num",
    "seller_sku",
    "name",
    "order_date",
    "ordered",
    "delivered",
    "sent_to_fba",
    "to_ship",
    "order_key",
    "local_row_seen",
    "local_sku",
    "local_ordered",
    "local_delivered",
    "local_sent_to_fba",
    "local_to_ship",
    "local_match_status",
    "manager_classification",
    "manager_expectation",
    "mot_proof_check",
    "bounded_worker_task",
    "retest_rule",
    "protected_stop_rule",
]


@dataclass(frozen=True)
class StockReceiptPreviewResult:
    observed_utc: str
    preview_rows: list[dict[str, str]]
    orders_shipment_rows: list[dict[str, str]]
    orders_staged_refresh_rows: list[list[str]]
    summary_rows: list[dict[str, str]]


def utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _cell(row: list[str], index: int) -> str:
    if index < 0 or index >= len(row):
        return ""
    return str(row[index] or "").strip()


def _find_header_index(header: list[str], candidates: list[str]) -> int:
    lowered = {str(value).strip().lower(): index for index, value in enumerate(header)}
    for candidate in candidates:
        index = lowered.get(str(candidate).strip().lower())
        if index is not None:
            return index
    return -1


def _as_int(value: str) -> int:
    try:
        return int(float(str(value or "").replace(",", "").strip()))
    except ValueError:
        return 0


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [{key: value or "" for key, value in row.items() if key is not None} for row in reader]


def _token_counts_by_key_sku(root: Path) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    token_path = root / "out" / "token_ledger_live.csv"
    for row in _read_csv_rows(token_path):
        order_key = str(row.get("source_order_key", "") or "").strip()
        sku = str(row.get("seller_sku", "") or "").strip()
        if not order_key or not sku:
            continue
        counts[(order_key, sku)] = counts.get((order_key, sku), 0) + 1
    return counts


def _local_receipt_row_state(root: Path) -> tuple[set[str], int]:
    rows = set()
    max_row = 0
    for row in _read_csv_rows(root / "out" / "stock_receipts_latest.csv"):
        row_num = str(row.get("row_num", "") or "").strip()
        if row_num:
            rows.add(row_num)
            try:
                max_row = max(max_row, int(float(row_num)))
            except ValueError:
                pass
    return rows, max_row


def _sheet_values_from_google() -> tuple[list[str], list[list[str]]]:
    client = get_gspread_client()
    worksheet = client.open_by_key(INTAKE_SHEET_ID).worksheet(INTAKE_TAB)
    values = worksheet.get_all_values()
    if not values:
        return [], []
    return values[0], values[1:]


def _orders_sheet_values_from_google() -> tuple[list[str], list[list[str]]]:
    client = get_gspread_client()
    worksheet = client.open_by_key(ORDERS_SHEET_ID).worksheet(ORDERS_TAB)
    values = worksheet.get_all_values()
    if not values:
        return [], []
    return values[0], values[1:]


def _read_csv_table(path: Path) -> tuple[list[str], list[list[str]]]:
    if not path.exists():
        return [], []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        return [], []
    return rows[0], rows[1:]


def _file_age_hours(path: Path, observed: str) -> float | None:
    if not path.exists():
        return None
    try:
        observed_dt = datetime.fromisoformat(observed.replace("Z", "+00:00"))
        mtime_dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        return max((observed_dt - mtime_dt).total_seconds() / 3600.0, 0.0)
    except OSError:
        return None


def _classify_receipt_row(*, qty: int, order_key: str, existing_count: int, local_seen: bool) -> tuple[str, int, int, str]:
    if local_seen:
        return "already_in_local_receipt_proof", 0, 0, "0"
    if qty <= 0:
        return "not_a_receipt_row", 0, 0, "0"
    if not order_key:
        return "missing_order_key", 0, 0, "1"
    expected_if_new_shipment = qty
    if existing_count >= qty:
        return "existing_order_key_receipt_row_ready_for_token_creator", qty, expected_if_new_shipment, "1"
    if existing_count > 0:
        return (
            "existing_order_key_receipt_row_ready_for_token_creator",
            qty,
            expected_if_new_shipment,
            "1",
        )
    return "new_receipt_candidate", qty, expected_if_new_shipment, "1"


def build_b_stock_receipt_intake_preview(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
    sheet_values: tuple[list[str], list[list[str]]] | None = None,
    orders_sheet_values: tuple[list[str], list[list[str]]] | None = None,
) -> StockReceiptPreviewResult:
    base = Path(root or ROOT)
    observed = observed_utc or utc_now_text()
    header, raw_rows = sheet_values if sheet_values is not None else _sheet_values_from_google()
    key_index = _find_header_index(header, ORDER_KEY_CANDIDATES)
    sku_index = _find_header_index(header, ["seller_sku", "SKU"])
    qty_index = _find_header_index(header, ["qty", "quantity"])
    intake_date_index = _find_header_index(header, ["intake_date", "date"])
    cost_index = _find_header_index(header, ["cost_per_unit", "cost"])
    status_index = _find_header_index(header, ["status"])

    token_counts = _token_counts_by_key_sku(base)
    local_receipt_rows, latest_local_receipt_row = _local_receipt_row_state(base)
    preview_rows: list[dict[str, str]] = []
    orders_shipment_rows: list[dict[str, str]] = []

    for offset, raw_row in enumerate(raw_rows, start=2):
        sku = _cell(raw_row, sku_index)
        qty_text = _cell(raw_row, qty_index)
        qty = parse_int(qty_text)
        if not sku and qty <= 0:
            continue
        sheet_row_num = str(offset)
        if latest_local_receipt_row and offset <= latest_local_receipt_row:
            continue
        order_key = _cell(raw_row, key_index)
        status = _cell(raw_row, status_index)
        local_seen = sheet_row_num in local_receipt_rows
        existing_count = token_counts.get((order_key, sku), 0) if order_key and sku else 0
        classification, would_create, expected_if_new_shipment, protected = _classify_receipt_row(
            qty=qty,
            order_key=order_key,
            existing_count=existing_count,
            local_seen=local_seen,
        )
        token_creator_proof_gap = expected_if_new_shipment if not local_seen else 0
        if local_seen and str(status).strip().upper() == "APPLIED":
            continue
        if classification == "not_a_receipt_row":
            continue
        if local_seen and classification == "already_in_local_receipt_proof":
            continue
        preview_rows.append(
            {
                "sheet_row_num": sheet_row_num,
                "intake_date": _cell(raw_row, intake_date_index),
                "seller_sku": sku,
                "sheet_qty": str(qty),
                "cost_per_unit": _cell(raw_row, cost_index),
                "order_key": order_key,
                "sheet_status": status,
                "local_receipt_row_seen": "1" if local_seen else "0",
                "existing_token_count_for_key_sku": str(existing_count),
                "tokens_processor_would_create": str(would_create),
                "manager_expected_tokens_if_new_shipment": str(expected_if_new_shipment),
                "token_creator_proof_gap_if_unprocessed": str(token_creator_proof_gap),
                "manager_classification": classification,
                "protected_decision_required": protected,
                "manager_expectation": "Unprocessed Sheet receipt rows must be previewed before any live stock/token action.",
                "mot_proof_check": "b_stock_receipt_token_sync",
                "bounded_worker_task": "Check why the normal token creator has not produced local proof for each unprocessed receipt row.",
                "retest_rule": "After any approved receipt/token action, rerun B MOT and confirm b_stock_receipt_token_sync clears.",
                "protected_stop_rule": "Stop before Sheet writes, token creation, stock correction, local DB alignment, output deletion, or B run/restart.",
            }
        )

    orders_header, orders_raw_rows = (
        orders_sheet_values if orders_sheet_values is not None else _orders_sheet_values_from_google()
    )
    local_orders_path = base / "out" / "orders_sheet_orders.csv"
    local_orders_header, local_orders_rows = _read_csv_table(local_orders_path)
    local_orders_age_hours = _file_age_hours(local_orders_path, observed)
    orders_key_index = _find_header_index(orders_header, ["OrderKey", "order_key", "orderkey"])
    local_orders_key_index = _find_header_index(local_orders_header, ["OrderKey", "order_key", "orderkey"])
    orders_indexes = {
        "sku": _find_header_index(orders_header, ["SKU", "seller_sku"]),
        "name": _find_header_index(orders_header, ["Name"]),
        "order_date": _find_header_index(orders_header, ["Order Date"]),
        "ordered": _find_header_index(orders_header, ["Ordered"]),
        "delivered": _find_header_index(orders_header, ["Delivered"]),
        "sent_to_fba": _find_header_index(orders_header, ["Sent to FBA"]),
        "to_ship": _find_header_index(orders_header, ["To ship"]),
    }
    local_orders_indexes = {
        "sku": _find_header_index(local_orders_header, ["SKU", "seller_sku"]),
        "ordered": _find_header_index(local_orders_header, ["Ordered"]),
        "delivered": _find_header_index(local_orders_header, ["Delivered"]),
        "sent_to_fba": _find_header_index(local_orders_header, ["Sent to FBA"]),
        "to_ship": _find_header_index(local_orders_header, ["To ship"]),
    }
    local_by_key: dict[str, list[str]] = {}
    if local_orders_key_index >= 0:
        for row in local_orders_rows:
            key = _cell(row, local_orders_key_index)
            if key:
                local_by_key[key] = row

    for offset, raw_row in enumerate(orders_raw_rows, start=2):
        sku = _cell(raw_row, orders_indexes["sku"])
        ordered = _as_int(_cell(raw_row, orders_indexes["ordered"]))
        delivered = _as_int(_cell(raw_row, orders_indexes["delivered"]))
        sent_to_fba = _as_int(_cell(raw_row, orders_indexes["sent_to_fba"]))
        to_ship = _cell(raw_row, orders_indexes["to_ship"])
        order_key = _cell(raw_row, orders_key_index)
        if not sku or ordered <= 0:
            continue
        remaining_to_send = max(delivered - sent_to_fba, 0)
        if remaining_to_send <= 0 and not to_ship:
            continue

        local_row = local_by_key.get(order_key, [])
        local_sku = _cell(local_row, local_orders_indexes["sku"]) if local_row else ""
        local_ordered = _cell(local_row, local_orders_indexes["ordered"]) if local_row else ""
        local_delivered = _cell(local_row, local_orders_indexes["delivered"]) if local_row else ""
        local_sent_to_fba = _cell(local_row, local_orders_indexes["sent_to_fba"]) if local_row else ""
        local_to_ship = _cell(local_row, local_orders_indexes["to_ship"]) if local_row else ""
        expected_values = [
            sku,
            str(ordered),
            str(delivered),
            str(sent_to_fba),
            to_ship,
        ]
        local_values = [
            local_sku,
            str(_as_int(local_ordered)),
            str(_as_int(local_delivered)),
            str(_as_int(local_sent_to_fba)),
            local_to_ship,
        ]
        if not local_row:
            match_status = "missing_local_order_key"
        elif expected_values == local_values:
            match_status = "matched"
        else:
            match_status = "local_orders_proof_mismatch"
        if match_status == "matched":
            classification = "shipment_row_proved_locally"
        else:
            classification = "shipment_row_missing_from_local_token_source"

        orders_shipment_rows.append(
            {
                "sheet_row_num": str(offset),
                "seller_sku": sku,
                "name": _cell(raw_row, orders_indexes["name"]),
                "order_date": _cell(raw_row, orders_indexes["order_date"]),
                "ordered": str(ordered),
                "delivered": str(delivered),
                "sent_to_fba": str(sent_to_fba),
                "to_ship": to_ship,
                "order_key": order_key,
                "local_row_seen": "1" if local_row else "0",
                "local_sku": local_sku,
                "local_ordered": local_ordered,
                "local_delivered": local_delivered,
                "local_sent_to_fba": local_sent_to_fba,
                "local_to_ship": local_to_ship,
                "local_match_status": match_status,
                "manager_classification": classification,
                "manager_expectation": "Live Orders shipment rows must match the local Orders proof used by the existing token creator.",
                "mot_proof_check": "b_stock_receipt_token_sync",
                "bounded_worker_task": "Repair or refresh the local Orders proof source so the existing token creator sees the shipment row.",
                "retest_rule": "Rerun this read-only preview and B MOT; the shipment row must be matched before live token action.",
                "protected_stop_rule": "Stop before Sheet writes, token creation, stock correction, local DB alignment, output deletion, or B run/restart.",
            }
        )

    classification_counts: dict[str, int] = {}
    protected_rows = 0
    would_create_total = 0
    expected_new_shipment_total = 0
    token_creator_proof_gap_total = 0
    for row in preview_rows:
        classification = row["manager_classification"]
        classification_counts[classification] = classification_counts.get(classification, 0) + 1
        if row.get("protected_decision_required") == "1":
            protected_rows += 1
        try:
            would_create_total += int(float(row.get("tokens_processor_would_create", "0") or "0"))
        except ValueError:
            pass
        try:
            expected_new_shipment_total += int(float(row.get("manager_expected_tokens_if_new_shipment", "0") or "0"))
        except ValueError:
            pass
        try:
            token_creator_proof_gap_total += int(float(row.get("token_creator_proof_gap_if_unprocessed", "0") or "0"))
        except ValueError:
            pass

    shipment_local_gap_rows = sum(
        1 for row in orders_shipment_rows if row.get("local_match_status") != "matched"
    )
    shipment_remaining_to_send_total = 0
    for row in orders_shipment_rows:
        shipment_remaining_to_send_total += max(_as_int(row.get("delivered", "0")) - _as_int(row.get("sent_to_fba", "0")), 0)

    status = "proof_needed" if protected_rows or shipment_local_gap_rows else "ok"
    local_orders_stale = local_orders_age_hours is None or local_orders_age_hours >= 24.0
    summary_values = {
        "status": status,
        "sheet_rows_seen": str(len(raw_rows)),
        "latest_local_receipt_row": str(latest_local_receipt_row),
        "preview_rows": str(len(preview_rows)),
        "protected_decision_rows": str(protected_rows),
        "tokens_processor_would_create_total": str(would_create_total),
        "manager_expected_tokens_if_new_shipment_total": str(expected_new_shipment_total),
        "token_creator_proof_gap_if_unprocessed_total": str(token_creator_proof_gap_total),
        "orders_shipment_rows": str(len(orders_shipment_rows)),
        "orders_shipment_local_gap_rows": str(shipment_local_gap_rows),
        "orders_shipment_remaining_to_send_total": str(shipment_remaining_to_send_total),
        "local_orders_file_age_hours": "" if local_orders_age_hours is None else f"{local_orders_age_hours:.2f}",
        "local_orders_file_stale": "1" if local_orders_stale else "0",
        "orders_staged_refresh_rows": str(len(orders_raw_rows)),
        "new_receipt_candidate_rows": str(classification_counts.get("new_receipt_candidate", 0)),
        "existing_order_key_receipt_rows_ready_for_token_creator": str(
            classification_counts.get("existing_order_key_receipt_row_ready_for_token_creator", 0)
        ),
        "missing_order_key_rows": str(classification_counts.get("missing_order_key", 0)),
        "observed_utc": observed,
    }
    summary_rows = [{"metric": key, "value": value} for key, value in summary_values.items()]
    return StockReceiptPreviewResult(
        observed_utc=observed,
        preview_rows=preview_rows,
        orders_shipment_rows=orders_shipment_rows,
        orders_staged_refresh_rows=[orders_header] + orders_raw_rows if orders_header else [],
        summary_rows=summary_rows,
    )


def write_b_stock_receipt_intake_preview_outputs(
    result: StockReceiptPreviewResult,
    *,
    root: Path | str | None = None,
) -> dict[str, Path]:
    base = Path(root or ROOT)
    output_dir = base / "out" / "systems" / "M" / OUTPUT_DIR_NAME
    output_dir.mkdir(parents=True, exist_ok=True)
    preview_path = output_dir / PREVIEW_CSV_NAME
    orders_shipment_path = output_dir / ORDERS_SHIPMENT_CSV_NAME
    orders_staged_refresh_path = output_dir / ORDERS_STAGED_REFRESH_CSV_NAME
    summary_path = output_dir / SUMMARY_CSV_NAME
    summary_json_path = output_dir / SUMMARY_JSON_NAME
    with preview_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PREVIEW_COLUMNS)
        writer.writeheader()
        for row in result.preview_rows:
            writer.writerow({column: row.get(column, "") for column in PREVIEW_COLUMNS})
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(result.summary_rows)
    with orders_shipment_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ORDERS_SHIPMENT_COLUMNS)
        writer.writeheader()
        for row in result.orders_shipment_rows:
            writer.writerow({column: row.get(column, "") for column in ORDERS_SHIPMENT_COLUMNS})
    with orders_staged_refresh_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerows(result.orders_staged_refresh_rows)
    summary_payload = {row["metric"]: row["value"] for row in result.summary_rows}
    summary_json_path.write_text(json.dumps(summary_payload, indent=2) + "\n", encoding="utf-8")
    return {
        "preview": preview_path,
        "orders_shipment": orders_shipment_path,
        "orders_staged_refresh": orders_staged_refresh_path,
        "summary": summary_path,
        "summary_json": summary_json_path,
    }
