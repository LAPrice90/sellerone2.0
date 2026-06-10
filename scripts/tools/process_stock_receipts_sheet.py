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

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.out_paths import write_csv_with_compat
from scripts.core.storage import StorageConfig, connect_store, parse_storage_mode, replace_table_from_dataframe


INTAKE_SHEET_ID = "1H_EDAYfB_xgGvnW1esOMwWsHs2wBXYoOABcMs7SWcrY"
INTAKE_TAB = "Tokens"

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
TOKEN_LEDGER_TAB = "Token_Ledger"

SUMMARY_OUT = Path("out/stock_receipt_summary.csv")
MISSING_COST_OUT = Path("out/stock_receipt_missing_costs.csv")
MISSING_ORDER_KEY_OUT = Path("out/stock_receipt_missing_order_key.csv")
DUPLICATE_BATCH_OUT = Path("out/stock_receipt_duplicate_batches.csv")
AUTO_COST_OUT = Path("out/stock_receipt_auto_cost_applied.csv")
LATEST_OUT = Path("out/stock_receipts_latest.csv")
SQL_TABLE_STOCK_RECEIPT_SUMMARY = "a_stock_receipt_summary"
SQL_TABLE_STOCK_RECEIPTS_LATEST = "a_stock_receipts_latest"
SUMMARY_COLUMNS = [
    "row_num",
    "intake_date",
    "seller_sku",
    "qty",
    "cost_per_unit",
    "auto_cost_source",
    "status",
    "batch_id",
    "tokens_created",
    "order_key",
    "error_message",
]

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

AUTO_COST_ENABLED = os.environ.get("RECEIPTS_AUTO_COST", "1").strip() == "1"
AUTO_COST_TOLERANCE = 0.000001


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


def _to_float(value: object) -> float:
    try:
        out = float(str(value).strip())
    except Exception:
        return 0.0
    return out


def _build_auto_cost_map() -> Dict[str, Tuple[float, str]]:
    """
    Build SKU -> (cost, source) using local historical outputs.
    Priority:
    1) token_ledger_live.csv latest positive cost by received_date
    2) token_cogs_ledger.csv latest positive token_cost by allocation/order date
    """
    result: Dict[str, Tuple[float, str]] = {}

    token_ledger_path = ROOT / "out" / "token_ledger_live.csv"
    if token_ledger_path.exists():
        try:
            df = pd.read_csv(token_ledger_path, dtype=str).fillna("")
            if not df.empty and {"seller_sku", "cost_per_unit"}.issubset(df.columns):
                work = df.copy()
                work["__cost"] = work["cost_per_unit"].apply(_to_float)
                work = work[work["__cost"] > AUTO_COST_TOLERANCE].copy()
                if not work.empty:
                    if "received_date" in work.columns:
                        work["__dt"] = pd.to_datetime(work["received_date"], errors="coerce", dayfirst=True, utc=True)
                    else:
                        work["__dt"] = pd.NaT
                    work["__row"] = range(len(work))
                    work = work.sort_values(by=["seller_sku", "__dt", "__row", "__cost"])
                    last = work.groupby("seller_sku", as_index=False).tail(1)
                    for _, row in last.iterrows():
                        sku = str(row.get("seller_sku", "")).strip()
                        if not sku:
                            continue
                        cost = float(row.get("__cost", 0.0) or 0.0)
                        if cost <= AUTO_COST_TOLERANCE:
                            continue
                        token_id = str(row.get("token_id", "")).strip()
                        source = f"token_ledger_live:{token_id}" if token_id else "token_ledger_live"
                        result[sku] = (cost, source)
        except Exception:
            pass

    token_cogs_path = ROOT / "out" / "token_cogs_ledger.csv"
    if token_cogs_path.exists():
        try:
            df = pd.read_csv(token_cogs_path, dtype=str).fillna("")
            if not df.empty and {"seller_sku", "token_cost"}.issubset(df.columns):
                work = df.copy()
                work["__cost"] = work["token_cost"].apply(_to_float)
                work = work[work["__cost"] > AUTO_COST_TOLERANCE].copy()
                if not work.empty:
                    if "allocation_date" in work.columns:
                        work["__dt"] = pd.to_datetime(work["allocation_date"], errors="coerce", utc=True)
                    elif "order_date" in work.columns:
                        work["__dt"] = pd.to_datetime(work["order_date"], errors="coerce", utc=True)
                    else:
                        work["__dt"] = pd.NaT
                    work["__row"] = range(len(work))
                    work = work.sort_values(by=["seller_sku", "__dt", "__row", "__cost"])
                    last = work.groupby("seller_sku", as_index=False).tail(1)
                    for _, row in last.iterrows():
                        sku = str(row.get("seller_sku", "")).strip()
                        if not sku or sku in result:
                            continue
                        cost = float(row.get("__cost", 0.0) or 0.0)
                        if cost <= AUTO_COST_TOLERANCE:
                            continue
                        token_id = str(row.get("token_id", "")).strip()
                        source = f"token_cogs_ledger:{token_id}" if token_id else "token_cogs_ledger"
                        result[sku] = (cost, source)
        except Exception:
            pass

    return result


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


def build_batch_id(intake_dt: datetime, existing_ids: set[str], row_num: int | None = None) -> str:
    date_str = intake_dt.strftime("%Y%m%d")
    prefix = f"SR-{date_str}-"
    if row_num is not None:
        return f"{prefix}ROW{int(row_num):04d}"
    seq = 1
    while True:
        batch_id = f"{prefix}{seq:03d}"
        if batch_id not in existing_ids:
            return batch_id
        seq += 1


def _summarize_token_rows(
    header: List[str], rows: List[List[str]]
) -> Tuple[set[str], Dict[str, int], Dict[Tuple[str, str], Dict[str, object]]]:
    token_ids = set()
    batch_counts: Dict[str, int] = {}
    order_key_counts: Dict[Tuple[str, str], Dict[str, object]] = {}
    if not header or not rows:
        return token_ids, batch_counts, order_key_counts
    token_idx = header.index("token_id") if "token_id" in header else -1
    batch_idx = header.index("source_batch_id") if "source_batch_id" in header else -1
    sku_idx = header.index("seller_sku") if "seller_sku" in header else -1
    order_key_idx = header.index("source_order_key") if "source_order_key" in header else -1
    for row in rows:
        if token_idx >= 0 and token_idx < len(row):
            token_id = row[token_idx].strip()
            if token_id:
                token_ids.add(token_id)
        if batch_idx >= 0 and batch_idx < len(row):
            bid = row[batch_idx].strip()
            if bid:
                batch_counts[bid] = batch_counts.get(bid, 0) + 1
        if sku_idx >= 0 and sku_idx < len(row) and order_key_idx >= 0 and order_key_idx < len(row):
            sku = str(row[sku_idx]).strip()
            order_key = str(row[order_key_idx]).strip()
            if sku and order_key:
                key = (order_key, sku)
                info = order_key_counts.get(key)
                if not info:
                    info = {"count": 0, "batch_ids": set()}
                    order_key_counts[key] = info
                info["count"] = int(info.get("count", 0)) + 1
                if batch_idx >= 0 and batch_idx < len(row):
                    bid = str(row[batch_idx]).strip()
                    if bid:
                        cast_batches = info.get("batch_ids")
                    if isinstance(cast_batches, set):
                        cast_batches.add(bid)
    return token_ids, batch_counts, order_key_counts


def load_token_ledger(
    ws: gspread.Worksheet,
) -> Tuple[List[str], set[str], Dict[str, int], Dict[Tuple[str, str], Dict[str, object]]]:
    header, rows = load_sheet_table(ws)
    token_ids, batch_counts, order_key_counts = _summarize_token_rows(header, rows)
    return header, token_ids, batch_counts, order_key_counts


def _write_output_frame(df: pd.DataFrame, path: Path, sql_table: str) -> dict[str, object]:
    mode = parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE"))
    sql_rows = 0
    if mode in {"sql_shadow", "sql_primary_csv_export"}:
        store = connect_store(StorageConfig.from_env())
        try:
            result = replace_table_from_dataframe(store, sql_table, df)
            sql_rows = int(result["rows"])
        finally:
            store.close()
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return {
        "mode": mode,
        "path": str(path),
        "csv_rows": int(len(df.index)),
        "sql_table": sql_table if mode != "csv" else "",
        "sql_rows": sql_rows,
    }


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
    auto_cost_map = _build_auto_cost_map() if AUTO_COST_ENABLED else {}

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
        sku = row[col_idx["seller_sku"]].strip()
        qty = parse_int(qty_raw)
        cost = parse_cost(cost_raw)
        order_key = row[order_key_idx].strip() if order_key_idx < len(row) else ""
        if qty > 0 and cost <= 0:
            auto = auto_cost_map.get(sku)
            auto_cost = float(auto[0]) if auto else 0.0
            if auto_cost <= AUTO_COST_TOLERANCE:
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

    token_header, token_ids, batch_counts, order_key_counts = load_token_ledger(token_ws)
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
        status = row[col_idx["status"]].strip().upper()
        if status in (STATUS_APPLIED, STATUS_CANCELLED):
            continue
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
    auto_cost_rows: List[Dict[str, str]] = []

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
        auto_cost_source = ""
        if qty > 0 and cost <= AUTO_COST_TOLERANCE and AUTO_COST_ENABLED:
            auto = auto_cost_map.get(sku)
            if auto:
                cost = float(auto[0])
                auto_cost_source = str(auto[1])
                if "notes" in col_idx:
                    existing_notes = notes.strip()
                    auto_note = f"auto_cost:{auto_cost_source}"
                    notes = f"{existing_notes}; {auto_note}" if existing_notes else auto_note
                row[col_idx["cost_per_unit"]] = f"{cost:.2f}"
        if not intake_dt:
            err = "invalid intake_date"
        elif not sku:
            err = "missing seller_sku"
        elif qty <= 0:
            err = "qty must be > 0"
        elif cost <= AUTO_COST_TOLERANCE:
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
                    "auto_cost_source": auto_cost_source,
                    "status": STATUS_ERROR,
                    "batch_id": "",
                    "tokens_created": "0",
                    "order_key": order_key,
                    "error_message": err,
                }
            )
            continue

        existing_for_key_info = order_key_counts.get((order_key, sku), {"count": 0, "batch_ids": set()})
        existing_for_key = int(existing_for_key_info.get("count", 0))
        existing_batches = sorted(str(v) for v in existing_for_key_info.get("batch_ids", set()) if str(v).strip())
        qty_to_create = qty

        batch_id = build_batch_id(intake_dt, existing_batch_ids, row_num=row_num)
        existing_batch_ids.add(batch_id)

        # Idempotency: if tokens already exist for this batch, mark applied and continue.
        if batch_id in batch_counts:
            created_count = batch_counts.get(batch_id, 0)
            total_with_existing = created_count
            status_out = STATUS_APPLIED if total_with_existing >= qty else STATUS_PARTIAL
            err_out = "" if status_out == STATUS_APPLIED else f"partial: ledger has {total_with_existing}/{qty}"
            row[col_idx["batch_id"]] = batch_id
            row[col_idx["status"]] = status_out
            row[col_idx["processed_at"]] = now_iso
            row[col_idx["tokens_created"]] = str(total_with_existing)
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
                    "auto_cost_source": auto_cost_source,
                    "status": status_out,
                    "batch_id": batch_id,
                    "tokens_created": str(total_with_existing),
                    "error_message": err_out,
                }
            )
            continue

        # Build tokens
        received_date = intake_dt.date().isoformat()
        token_rows = []
        for i in range(1, qty_to_create + 1):
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

        created_total = len(token_rows)
        status_out = STATUS_APPLIED if created_total >= qty else STATUS_PARTIAL
        err_out = "" if status_out == STATUS_APPLIED else f"partial: created {created_total}/{qty}"
        row[col_idx["batch_id"]] = batch_id
        row[col_idx["status"]] = status_out
        row[col_idx["processed_at"]] = now_iso
        row[col_idx["error_message"]] = err_out
        row[col_idx["tokens_created"]] = str(created_total)
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
                    "auto_cost_source": auto_cost_source,
                    "status": status_out,
                    "batch_id": batch_id,
                    "tokens_created": str(created_total),
                    "order_key": order_key,
                    "error_message": err_out,
                }
            )
        key = (order_key, sku)
        updated = order_key_counts.get(key, {"count": 0, "batch_ids": set()})
        updated["count"] = int(updated.get("count", 0)) + len(token_rows)
        cast_batches = updated.get("batch_ids")
        if isinstance(cast_batches, set):
            cast_batches.add(batch_id)
        order_key_counts[key] = updated
        if auto_cost_source:
            auto_cost_rows.append(
                {
                    "row_num": str(row_num),
                    "seller_sku": sku,
                    "qty": str(qty),
                    "resolved_cost_per_unit": f"{cost:.2f}",
                    "source": auto_cost_source,
                    "processed_at": now_iso,
                }
            )

    summary_df = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS)
    SUMMARY_OUT.parent.mkdir(parents=True, exist_ok=True)
    _write_output_frame(summary_df, SUMMARY_OUT, SQL_TABLE_STOCK_RECEIPT_SUMMARY)
    # Backward-compatible alias required by A-cycle step artifact verification.
    _write_output_frame(summary_df, LATEST_OUT, SQL_TABLE_STOCK_RECEIPTS_LATEST)
    if auto_cost_rows:
        AUTO_COST_OUT.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(auto_cost_rows).to_csv(AUTO_COST_OUT, index=False)

    # Keep local token ledger in sync for local-master allocation flow.
    token_header_latest, token_rows_latest = load_sheet_table(token_ws)
    if token_header_latest:
        token_local_df = pd.DataFrame(token_rows_latest, columns=token_header_latest).fillna("")
        write_csv_with_compat(
            token_local_df,
            path_or_rel="token_ledger_live.csv",
            default_system="B",
            index=False,
            mirror_legacy=True,
        )

    print(
        {
            "status": "success",
            "rows_scanned": len(intake_rows),
            "applied": applied,
            "skipped": skipped,
            "errors": errors,
            "summary": str(SUMMARY_OUT),
            "auto_cost_applied_rows": len(auto_cost_rows),
            "auto_cost_report": str(AUTO_COST_OUT) if auto_cost_rows else "",
        }
    )


if __name__ == "__main__":
    main()

