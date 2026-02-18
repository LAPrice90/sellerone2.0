"""
Process stock receipt intake rows from Google Sheets (Tokens tab).

Operator fills: intake_date, seller_sku, qty, cost_per_unit, notes(optional).
System writes: batch_id, status, processed_at, error_message, tokens_created, token_id_prefix.
Tokens are appended to Token_Ledger (append-only, idempotent).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import sys
import os
from typing import Dict, List, Tuple

import gspread
import pandas as pd


INTAKE_SHEET_ID = "1H_EDAYfB_xgGvnW1esOMwWsHs2wBXYoOABcMs7SWcrY"
INTAKE_TAB = "Tokens"

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
TOKEN_LEDGER_TAB = "Token_Ledger"

SUMMARY_OUT = Path("out/stock_receipt_summary.csv")
MISSING_COST_OUT = Path("out/stock_receipt_missing_costs.csv")
MISSING_ORDER_KEY_OUT = Path("out/stock_receipt_missing_order_key.csv")
DUPLICATE_BATCH_OUT = Path("out/stock_receipt_duplicate_batches.csv")

STATUS_NEW = "NEW"
STATUS_VALIDATED = "VALIDATED"
STATUS_APPLIED = "APPLIED"
STATUS_PARTIAL = "PARTIAL"
STATUS_ERROR = "ERROR"
STATUS_CANCELLED = "CANCELLED"

REQUIRED_INPUT_COLS = ["intake_date", "seller_sku", "qty", "cost_per_unit"]
ORDER_KEY_CANDIDATES = ["order_key", "OrderKey", "orderkey"]
SYSTEM_COLS = [
    "batch_id",
    "status",
    "processed_at",
    "error_message",
    "tokens_created",
    "token_id_prefix",
]

TOKEN_REQUIRED_COLS = [
    "token_id",
    "seller_sku",
    "cost_per_unit",
    "currency",
    "status",
    "received_date",
    "notes",
    "source",
    "source_batch_id",
    "source_order_key",
    "created_at",
]


def get_gspread_client() -> gspread.Client:
    cred_path = Path("secrets/sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=str(cred_path))


def col_to_a1(idx: int) -> str:
    s = ""
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        s = chr(65 + rem) + s
    return s


def parse_date_uk(value: str) -> datetime | None:
    if not value:
        return None
    value = str(value).strip()
    for fmt in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        ts = pd.to_datetime(value, dayfirst=True, errors="coerce")
        if pd.notna(ts):
            return ts.to_pydatetime()
    except Exception:
        return None
    return None


def parse_int(value: str) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def parse_cost(value: str) -> float:
    if value is None:
        return 0.0
    match = re.search(r"[-+]?[0-9]*\.?[0-9]+", str(value).replace(",", ""))
    return float(match.group()) if match else 0.0


def ensure_columns(ws: gspread.Worksheet, header: List[str], needed: List[str]) -> List[str]:
    updated = list(header)
    for col in needed:
        if col not in updated:
            updated.append(col)
    if updated != header:
        ws.update("A1", [updated])
    return updated


def find_col_idx(header: List[str], candidates: List[str]) -> int:
    if not header:
        return -1
    name_to_idx = {str(h).strip().lower(): i for i, h in enumerate(header)}
    for cand in candidates:
        idx = name_to_idx.get(str(cand).strip().lower(), -1)
        if idx >= 0:
            return idx
    return -1


def load_sheet_table(ws: gspread.Worksheet) -> Tuple[List[str], List[List[str]]]:
    values = ws.get_all_values()
    if not values:
        return [], []
    return values[0], values[1:]


def build_batch_id(intake_dt: datetime, existing_ids: set[str]) -> str:
    date_str = intake_dt.strftime("%Y%m%d")
    prefix = f"SR-{date_str}-"
    seq = 1
    while True:
        batch_id = f"{prefix}{seq:03d}"
        if batch_id not in existing_ids:
            return batch_id
        seq += 1


def load_token_ledger(ws: gspread.Worksheet) -> Tuple[List[str], set[str], Dict[str, int]]:
    header, rows = load_sheet_table(ws)
    token_ids = set()
    batch_counts: Dict[str, int] = {}
    if not header or not rows:
        return header, token_ids, batch_counts
    token_idx = header.index("token_id") if "token_id" in header else -1
    batch_idx = header.index("source_batch_id") if "source_batch_id" in header else -1
    for row in rows:
        if token_idx >= 0 and token_idx < len(row):
            token_id = row[token_idx].strip()
            if token_id:
                token_ids.add(token_id)
        if batch_idx >= 0 and batch_idx < len(row):
            bid = row[batch_idx].strip()
            if bid:
                batch_counts[bid] = batch_counts.get(bid, 0) + 1
    return header, token_ids, batch_counts


def main() -> None:
    # Guardrail: explicit run flag required to prevent accidental runs
    if os.environ.get("RECEIPTS_RUN", "").strip().upper() != "YES":
        raise SystemExit("Guardrail: set RECEIPTS_RUN=YES to run this script.")

    client = get_gspread_client()
    intake_ws = client.open_by_key(INTAKE_SHEET_ID).worksheet(INTAKE_TAB)
    token_ws = client.open_by_key(TOKENS_SHEET_ID).worksheet(TOKEN_LEDGER_TAB)

    intake_header, intake_rows = load_sheet_table(intake_ws)
    if not intake_header:
        raise RuntimeError("Tokens tab header missing.")

    intake_header = ensure_columns(intake_ws, intake_header, REQUIRED_INPUT_COLS + SYSTEM_COLS)
    col_idx = {c: i for i, c in enumerate(intake_header)}
    order_key_idx = find_col_idx(intake_header, ORDER_KEY_CANDIDATES)
    if order_key_idx < 0:
        raise RuntimeError(
            "Tokens intake is missing OrderKey/order_key column. "
            "Add OrderKey (recommended) before running this script."
        )

    # Pre-scan guardrail: stop if any row has qty > 0 but missing required identity/cost.
    missing_cost_rows = []
    missing_order_key_rows = []
    for row_num, row in enumerate(intake_rows, start=2):
        if len(row) < len(intake_header):
            row = row + [""] * (len(intake_header) - len(row))
        status = row[col_idx["status"]].strip().upper()
        if status in (STATUS_APPLIED, STATUS_CANCELLED):
            continue
        qty_raw = row[col_idx["qty"]].strip()
        cost_raw = row[col_idx["cost_per_unit"]].strip()
        qty = parse_int(qty_raw)
        cost = parse_cost(cost_raw)
        order_key = row[order_key_idx].strip() if order_key_idx < len(row) else ""
        if qty > 0 and cost <= 0:
            missing_cost_rows.append([row_num] + row)
        if qty > 0 and not order_key:
            missing_order_key_rows.append([row_num] + row)

    if missing_cost_rows:
        MISSING_COST_OUT.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(missing_cost_rows, columns=["row_num"] + intake_header).to_csv(MISSING_COST_OUT, index=False)
        raise SystemExit(
            f"Guardrail: {len(missing_cost_rows)} intake rows have qty>0 but missing cost_per_unit. "
            f"Fill costs and re-run. Details: {MISSING_COST_OUT}"
        )
    if missing_order_key_rows:
        MISSING_ORDER_KEY_OUT.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(missing_order_key_rows, columns=["row_num"] + intake_header).to_csv(MISSING_ORDER_KEY_OUT, index=False)
        raise SystemExit(
            f"Guardrail: {len(missing_order_key_rows)} intake rows have qty>0 but missing OrderKey/order_key. "
            f"Fill keys and re-run. Details: {MISSING_ORDER_KEY_OUT}"
        )

    token_header, token_ids, batch_counts = load_token_ledger(token_ws)
    token_header = ensure_columns(token_ws, token_header, TOKEN_REQUIRED_COLS)

    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    existing_batch_ids = {row[col_idx["batch_id"]].strip() for row in intake_rows if len(row) > col_idx["batch_id"]}
    existing_batch_ids.update(batch_counts.keys())

    # Pre-scan guardrail: stop if duplicate batch_id exists in intake sheet
    batch_id_rows = {}
    duplicate_batch_rows = []
    for row_num, row in enumerate(intake_rows, start=2):
        if len(row) < len(intake_header):
            row = row + [""] * (len(intake_header) - len(row))
        bid = row[col_idx["batch_id"]].strip()
        if not bid:
            continue
        if bid in batch_id_rows:
            duplicate_batch_rows.append([row_num] + row)
        else:
            batch_id_rows[bid] = row_num

    if duplicate_batch_rows:
        DUPLICATE_BATCH_OUT.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(duplicate_batch_rows, columns=["row_num"] + intake_header).to_csv(DUPLICATE_BATCH_OUT, index=False)
        raise SystemExit(
            f"Guardrail: duplicate batch_id(s) found in intake sheet. "
            f"Fix duplicates and re-run. Details: {DUPLICATE_BATCH_OUT}"
        )

    applied = 0
    skipped = 0
    errors = 0
    summary_rows: List[Dict[str, str]] = []

    for row_num, row in enumerate(intake_rows, start=2):
        # Normalize row length
        if len(row) < len(intake_header):
            row = row + [""] * (len(intake_header) - len(row))

        status = row[col_idx["status"]].strip().upper()
        batch_id = row[col_idx["batch_id"]].strip()
        if status == STATUS_CANCELLED:
            skipped += 1
            continue
        if status == STATUS_APPLIED or batch_id:
            skipped += 1
            continue
        if status and status not in (STATUS_NEW, STATUS_VALIDATED, STATUS_PARTIAL):
            skipped += 1
            continue

        intake_date_raw = row[col_idx["intake_date"]].strip()
        sku = row[col_idx["seller_sku"]].strip()
        qty_raw = row[col_idx["qty"]].strip()
        cost_raw = row[col_idx["cost_per_unit"]].strip()
        notes = row[col_idx["notes"]].strip() if "notes" in col_idx else ""
        order_key = row[order_key_idx].strip() if order_key_idx < len(row) else ""

        err = ""
        intake_dt = parse_date_uk(intake_date_raw)
        qty = parse_int(qty_raw)
        cost = parse_cost(cost_raw)
        if not intake_dt:
            err = "invalid intake_date"
        elif not sku:
            err = "missing seller_sku"
        elif qty <= 0:
            err = "qty must be > 0"
        elif cost <= 0:
            err = "cost_per_unit must be > 0"
        elif not order_key:
            err = "missing order_key"

        if err:
            errors += 1
            row[col_idx["status"]] = STATUS_ERROR
            row[col_idx["error_message"]] = err
            row[col_idx["processed_at"]] = now_iso
            row[col_idx["tokens_created"]] = "0"
            intake_ws.update(
                f"{col_to_a1(1)}{row_num}:{col_to_a1(len(intake_header))}{row_num}",
                [row],
            )
            summary_rows.append(
                {
                    "row_num": str(row_num),
                    "intake_date": intake_date_raw,
                    "seller_sku": sku,
                    "qty": str(qty),
                    "cost_per_unit": str(cost),
                    "status": STATUS_ERROR,
                    "batch_id": "",
                    "tokens_created": "0",
                    "order_key": order_key,
                    "error_message": err,
                }
            )
            continue

        batch_id = build_batch_id(intake_dt, existing_batch_ids)
        existing_batch_ids.add(batch_id)

        # Idempotency: if tokens already exist for this batch, mark applied and continue.
        if batch_id in batch_counts:
            created_count = batch_counts.get(batch_id, 0)
            status_out = STATUS_APPLIED if created_count == qty else STATUS_PARTIAL
            err_out = "" if status_out == STATUS_APPLIED else f"partial: ledger has {created_count}/{qty}"
            row[col_idx["batch_id"]] = batch_id
            row[col_idx["status"]] = status_out
            row[col_idx["processed_at"]] = now_iso
            row[col_idx["tokens_created"]] = str(created_count)
            row[col_idx["token_id_prefix"]] = batch_id
            row[col_idx["error_message"]] = err_out
            intake_ws.update(
                f"{col_to_a1(1)}{row_num}:{col_to_a1(len(intake_header))}{row_num}",
                [row],
            )
            applied += 1
            summary_rows.append(
                {
                    "row_num": str(row_num),
                    "intake_date": intake_date_raw,
                    "seller_sku": sku,
                    "qty": str(qty),
                    "cost_per_unit": str(cost),
                    "status": status_out,
                    "batch_id": batch_id,
                    "tokens_created": str(created_count),
                    "error_message": err_out,
                }
            )
            continue

        # Build tokens
        received_date = intake_dt.date().isoformat()
        token_rows = []
        for i in range(1, qty + 1):
            token_id = f"{batch_id}-{i:04d}"
            if token_id in token_ids:
                continue
            token_ids.add(token_id)
            token_rows.append(
                [
                    token_id,
                    sku,
                    f"{cost:.2f}",
                    "GBP",
                    "available",
                    received_date,
                    notes,
                    "stock_receipt",
                    batch_id,
                    order_key,
                    now_iso,
                ]
            )

        # Append to ledger
        if token_rows:
            token_header = ensure_columns(token_ws, token_header, TOKEN_REQUIRED_COLS)
            idx = {c: token_header.index(c) for c in TOKEN_REQUIRED_COLS}
            full_rows = []
            for tr in token_rows:
                row_out = [""] * len(token_header)
                row_out[idx["token_id"]] = tr[0]
                row_out[idx["seller_sku"]] = tr[1]
                row_out[idx["cost_per_unit"]] = tr[2]
                row_out[idx["currency"]] = tr[3]
                row_out[idx["status"]] = tr[4]
                row_out[idx["received_date"]] = tr[5]
                row_out[idx["notes"]] = tr[6]
                row_out[idx["source"]] = tr[7]
                row_out[idx["source_batch_id"]] = tr[8]
                row_out[idx["source_order_key"]] = tr[9]
                row_out[idx["created_at"]] = tr[10]
                full_rows.append(row_out)
            token_ws.append_rows(full_rows, value_input_option="RAW")

        status_out = STATUS_APPLIED if len(token_rows) == qty else STATUS_PARTIAL
        err_out = "" if status_out == STATUS_APPLIED else f"partial: created {len(token_rows)}/{qty}"
        row[col_idx["batch_id"]] = batch_id
        row[col_idx["status"]] = status_out
        row[col_idx["processed_at"]] = now_iso
        row[col_idx["error_message"]] = err_out
        row[col_idx["tokens_created"]] = str(len(token_rows))
        row[col_idx["token_id_prefix"]] = batch_id
        intake_ws.update(
            f"{col_to_a1(1)}{row_num}:{col_to_a1(len(intake_header))}{row_num}",
            [row],
        )
        applied += 1
        summary_rows.append(
            {
                "row_num": str(row_num),
                "intake_date": intake_date_raw,
                "seller_sku": sku,
                "qty": str(qty),
                "cost_per_unit": str(cost),
                "status": status_out,
                "batch_id": batch_id,
                "tokens_created": str(len(token_rows)),
                "order_key": order_key,
                "error_message": err_out,
            }
        )

    SUMMARY_OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summary_rows).to_csv(SUMMARY_OUT, index=False)

    print(
        {
            "status": "success",
            "rows_scanned": len(intake_rows),
            "applied": applied,
            "skipped": skipped,
            "errors": errors,
            "summary": str(SUMMARY_OUT),
        }
    )


if __name__ == "__main__":
    main()
