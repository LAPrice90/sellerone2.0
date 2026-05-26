"""
Apply stock adjustment events to token ledger (FIFO by return_date).

Uses out/stock_events_raw.csv (from A006) and updates Token_Ledger.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re
import sys
from typing import TYPE_CHECKING

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.core.out_paths import resolve_compat_path, write_csv_with_compat
except ModuleNotFoundError:
    from core.out_paths import resolve_compat_path, write_csv_with_compat

try:
    from scripts.core.storage import StorageConfig, connect_store, parse_storage_mode, replace_table_from_dataframe
except ModuleNotFoundError:
    from core.storage import StorageConfig, connect_store, parse_storage_mode, replace_table_from_dataframe

try:
    import gspread
except Exception:
    gspread = None

if TYPE_CHECKING:
    import gspread as gspread_types

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
TOKEN_LEDGER_TAB = "Token_Ledger"
EVENTS_TAB = "Stock_Adjustments_Token_Events"
COMPLETENESS_TAB = "Ledger_Completeness"
WRITE_SHEETS = os.environ.get("STOCK_EVENTS_WRITE_SHEETS", "1").strip() == "1"

STOCK_EVENTS = Path("out/stock_events_raw.csv")
OUT_EVENTS = Path("out/stock_adjustment_token_events.csv")
OUT_COMPLETENESS = Path("out/ledger_completeness_summary.csv")
OUT_RETURN_LEDGER = Path("out/token_return_ledger.csv")
OUT_LEDGER = Path("out/token_ledger_live.csv")
SQL_TABLE_STOCK_ADJUSTMENT_EVENTS = "b_stock_adjustment_token_events"
EVENT_COLUMNS = [
    "event_id",
    "sku",
    "event_date",
    "event_type",
    "disposition",
    "quantity",
    "applied_qty",
    "status",
    "note",
    "event_ts",
]


def get_gspread_client() -> "gspread_types.Client":
    if gspread is None:
        raise RuntimeError("gspread not available")
    cred_path = Path("secrets/sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=str(cred_path))


def load_sheet_df(ws: "gspread_types.Worksheet") -> pd.DataFrame:
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()
    header, rows = values[0], values[1:]
    return pd.DataFrame(rows, columns=header)


def parse_int(value: str) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _normalize_events(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=EVENT_COLUMNS)
    out = df.copy()
    for col in EVENT_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    return out[EVENT_COLUMNS].copy()


def _write_stock_adjustment_events_output(
    prior: pd.DataFrame,
    events: pd.DataFrame,
    *,
    use_sheets: bool,
) -> dict[str, object]:
    mode = parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE", "csv"))
    prior = _normalize_events(prior)
    events = _normalize_events(events)
    combined = pd.concat([prior, events], ignore_index=True)
    sql_rows = 0

    def write_csv() -> None:
        OUT_EVENTS.parent.mkdir(parents=True, exist_ok=True)
        combined.to_csv(OUT_EVENTS, index=False)

    def write_sql() -> None:
        nonlocal sql_rows
        store = connect_store(StorageConfig.from_env())
        try:
            result = replace_table_from_dataframe(store, SQL_TABLE_STOCK_ADJUSTMENT_EVENTS, combined)
        finally:
            store.close()
        sql_rows = int(result["rows"])

    if use_sheets:
        write_csv()
    elif mode == "sql_primary_csv_export":
        write_sql()
        write_csv()
    elif mode == "sql_shadow":
        write_csv()
        write_sql()
    else:
        write_csv()

    return {
        "mode": "csv" if use_sheets else mode,
        "sql_table": "" if use_sheets or mode == "csv" else SQL_TABLE_STOCK_ADJUSTMENT_EVENTS,
        "sql_rows": sql_rows,
        "total_events": int(len(combined)),
    }


def to_event_day(value: str) -> str:
    try:
        ts = pd.to_datetime(value, errors="coerce", utc=True)
    except Exception:
        ts = pd.NaT
    if pd.isna(ts):
        return ""
    return ts.date().isoformat()


def parse_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = pd.to_datetime(value, errors="coerce", utc=True)
    except Exception:
        return None
    if pd.isna(dt):
        return None
    return dt.to_pydatetime()


def _parse_float(value: object) -> float:
    try:
        return float(str(value).strip())
    except Exception:
        return 0.0


def _latest_cost_basis(ledger: pd.DataFrame, sku: str) -> dict[str, str] | None:
    if ledger.empty or "seller_sku" not in ledger.columns:
        return None
    sku_rows = ledger[ledger["seller_sku"].astype(str).str.strip() == str(sku).strip()].copy()
    if sku_rows.empty:
        return None
    if "cost_per_unit" not in sku_rows.columns:
        return None
    sku_rows["__cost"] = sku_rows["cost_per_unit"].apply(_parse_float)
    sku_rows = sku_rows[sku_rows["__cost"] > 0].copy()
    if sku_rows.empty:
        return None
    if "received_date" in sku_rows.columns:
        sku_rows["__received"] = pd.to_datetime(sku_rows["received_date"], errors="coerce", utc=True)
    else:
        sku_rows["__received"] = pd.NaT
    if "created_at" in sku_rows.columns:
        sku_rows["__created"] = pd.to_datetime(sku_rows["created_at"], errors="coerce", utc=True)
    else:
        sku_rows["__created"] = pd.NaT
    sku_rows["__row"] = range(len(sku_rows))
    sku_rows = sku_rows.sort_values(by=["__received", "__created", "__row"])
    latest = sku_rows.iloc[-1]
    return {
        "cost_per_unit": f"{float(latest['__cost']):.2f}",
        "currency": str(latest.get("currency", "GBP") or "GBP"),
        "notes": str(latest.get("notes", "") or ""),
    }


def _append_adjustment_fallback_tokens(
    ledger: pd.DataFrame,
    *,
    sku: str,
    qty: int,
    event_id: str,
    disposition: str,
    now_iso: str,
    event_date: str,
) -> tuple[pd.DataFrame, int]:
    if qty <= 0:
        return ledger, 0
    basis = _latest_cost_basis(ledger, sku)
    if not basis:
        return ledger, 0

    required_cols = [
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
        "allocated_order_id",
        "allocated_date",
        "return_order_id",
        "return_date",
        "return_event_id",
        "last_return_order_id",
        "last_return_date",
        "last_return_event_id",
        "disposed_event_id",
        "disposed_date",
        "disposed_reason",
    ]
    for col in required_cols:
        if col not in ledger.columns:
            ledger[col] = ""

    status_map = {
        "SELLABLE": "available",
        "RESEARCHING": "research_pending",
    }
    target_status = status_map.get(disposition.upper(), "unsellable")
    safe_sku = re.sub(r"[^A-Za-z0-9._-]", "_", str(sku).strip())
    safe_event = re.sub(r"[^A-Za-z0-9._-]", "_", str(event_id).strip())
    existing_ids = set(ledger["token_id"].astype(str).tolist()) if "token_id" in ledger.columns else set()
    event_day = to_event_day(event_date) or now_iso[:10]
    created_rows = []
    seq = 1
    while len(created_rows) < qty:
        token_id = f"ADJ-{safe_sku}-{safe_event}-{seq:04d}"
        seq += 1
        if token_id in existing_ids:
            continue
        existing_ids.add(token_id)
        created_rows.append(
            {
                "token_id": token_id,
                "seller_sku": sku,
                "cost_per_unit": basis["cost_per_unit"],
                "currency": basis["currency"],
                "status": target_status,
                "received_date": event_day,
                "notes": f"adjustment_fallback_create:{event_id}",
                "source": "stock_adjustment_fallback",
                "source_batch_id": event_id,
                "source_order_key": "",
                "created_at": now_iso,
                "allocated_order_id": "",
                "allocated_date": "",
                "return_order_id": "",
                "return_date": "",
                "return_event_id": "",
                "last_return_order_id": "",
                "last_return_date": "",
                "last_return_event_id": "",
                "disposed_event_id": "",
                "disposed_date": "",
                "disposed_reason": "",
            }
        )
    if created_rows:
        ledger = pd.concat([ledger, pd.DataFrame(created_rows)], ignore_index=True)
    return ledger, len(created_rows)


def main() -> None:
    if not STOCK_EVENTS.exists():
        print({"status": "skip", "reason": "missing_stock_events"})
        return

    events = pd.read_csv(STOCK_EVENTS, dtype=str).fillna("")
    if not events.columns.is_unique:
        events = events.loc[:, ~events.columns.duplicated()].copy()
    if events.empty:
        print({"status": "skip", "reason": "no_stock_events"})
        return

    use_sheets = bool(WRITE_SHEETS and gspread is not None)
    sheet = None
    ledger_ws = None
    if use_sheets:
        client = get_gspread_client()
        sheet = client.open_by_key(TOKENS_SHEET_ID)
        ledger_ws = sheet.worksheet(TOKEN_LEDGER_TAB)
        ledger = load_sheet_df(ledger_ws)
    else:
        ledger_paths = resolve_compat_path("token_ledger_live.csv", default_system="B")
        ledger_path = ledger_paths.live_path if ledger_paths.live_path.exists() else ledger_paths.legacy_path
        if not ledger_path.exists():
            print({"status": "skip", "reason": "empty_token_ledger"})
            return
        ledger = pd.read_csv(ledger_path, dtype=str).fillna("")
    # gspread can return duplicate header names from sheet tabs.
    # Keep the first occurrence so boolean masks resolve to Series, not DataFrame.
    if not ledger.columns.is_unique:
        ledger = ledger.loc[:, ~ledger.columns.duplicated()].copy()
    if ledger.empty:
        print({"status": "skip", "reason": "empty_token_ledger"})
        return

    if "status" not in ledger.columns:
        ledger["status"] = ""
    if "return_order_id" not in ledger.columns:
        ledger["return_order_id"] = ""
    if "return_date" not in ledger.columns:
        ledger["return_date"] = ""
    if "return_event_id" not in ledger.columns:
        ledger["return_event_id"] = ""
    if "last_return_order_id" not in ledger.columns:
        ledger["last_return_order_id"] = ""
    if "last_return_date" not in ledger.columns:
        ledger["last_return_date"] = ""
    if "last_return_event_id" not in ledger.columns:
        ledger["last_return_event_id"] = ""
    if "disposed_event_id" not in ledger.columns:
        ledger["disposed_event_id"] = ""
    if "disposed_date" not in ledger.columns:
        ledger["disposed_date"] = ""
    if "disposed_reason" not in ledger.columns:
        ledger["disposed_reason"] = ""

    # Idempotency: skip events already applied (allow partial reapply)
    if use_sheets:
        try:
            ev_ws = sheet.worksheet(EVENTS_TAB)
            prior = load_sheet_df(ev_ws)
            applied_ids = set(prior["event_id"].tolist()) if "event_id" in prior.columns else set()
        except gspread.WorksheetNotFound:
            applied_ids = set()
            prior = pd.DataFrame()
    else:
        if OUT_EVENTS.exists():
            try:
                prior = pd.read_csv(OUT_EVENTS, dtype=str).fillna("")
            except Exception:
                prior = pd.DataFrame()
        else:
            prior = pd.DataFrame()
        applied_ids = set(prior["event_id"].tolist()) if "event_id" in prior.columns else set()

    prior_map = {}
    if not prior.empty and "event_id" in prior.columns:
        prior = prior.copy()
        prior["quantity"] = prior.get("quantity", "").apply(parse_int)
        prior["applied_qty"] = prior.get("applied_qty", "").apply(parse_int)
        prior["base_event_id"] = prior["event_id"].astype(str).str.split("-retry").str[0]
        # Aggregate by base_event_id for reapply logic.
        for base_id, grp in prior.groupby("base_event_id"):
            total_applied = int(grp["applied_qty"].sum())
            original_qty = int(grp["quantity"].abs().max()) if "quantity" in grp.columns else 0
            retry_count = int(len(grp))
            prior_map[base_id] = {
                "total_applied": total_applied,
                "original_qty": original_qty,
                "retry_count": retry_count,
            }

    allowed_types = {"adjustments", "receipts", "customerreturns", "vendorreturns"}
    events["event_type_norm"] = events["event_type"].str.lower()
    events = events[events["event_type_norm"].isin(allowed_types)].copy()
    events["quantity"] = events["quantity"].apply(parse_int)
    events = events[events["quantity"] != 0]
    events = events.sort_values(by=["event_date", "event_id"])

    log_rows = []
    return_rows = []
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    def mark_disposed(idx: pd.Index, event_id: str, reason: str) -> None:
        if idx.empty:
            return
        ledger.loc[idx, "status"] = "disposed"
        ledger.loc[idx, "disposed_event_id"] = event_id
        ledger.loc[idx, "disposed_date"] = now_iso
        ledger.loc[idx, "disposed_reason"] = reason

    def first_token_index(token_id: str) -> int | None:
        matches = ledger.index[ledger["token_id"] == token_id]
        if len(matches) == 0:
            return None
        return int(matches[0])

    processed_base_event_ids: set[str] = set()
    for _, row in events.iterrows():
        note = ""
        base_event_id = str(row.get("event_id", "")).strip()
        if not base_event_id:
            continue
        if base_event_id in processed_base_event_ids:
            continue
        processed_base_event_ids.add(base_event_id)
        if base_event_id in applied_ids:
            prior_info = prior_map.get(base_event_id)
            if not prior_info:
                continue
            remaining = prior_info["original_qty"] - prior_info["total_applied"]
            if remaining <= 0:
                continue
            # Re-apply remaining quantity under a unique retry event id.
            retry_n = prior_info["retry_count"] + 1
            event_id = f"{base_event_id}-retry{retry_n}"
            qty = abs(int(row.get("quantity", 0)))
            qty = remaining if remaining > 0 else 0
            if int(row.get("quantity", 0)) < 0:
                qty *= -1
            note = f"reapply_partial:{base_event_id}"
        else:
            event_id = base_event_id
            qty = int(row.get("quantity", 0))
        sku = str(row.get("sku", "")).strip()
        disposition = str(row.get("disposition", "")).strip().upper()
        applied = 0
        status = "ok"

        if not sku or qty == 0:
            continue

        if disposition == "SELLABLE":
            if qty > 0:
                # create a NEW return token when item becomes sellable
                pending = ledger[
                    (ledger["seller_sku"] == sku) & (ledger["status"] == "returned_pending")
                ].copy()
                pending = pending.sort_values(by=["return_date", "token_id"])
                existing_ids = set(ledger["token_id"].tolist())
                for token_id in pending["token_id"].head(qty).tolist():
                    idx = first_token_index(token_id)
                    if idx is None:
                        continue
                    # mark original token as returned_complete (do not reuse it)
                    ledger.at[idx, "status"] = "returned_complete"
                    ledger.at[idx, "notes"] = f"return_closed:{event_id}"
                    ledger.at[idx, "last_return_order_id"] = ledger.at[idx, "return_order_id"]
                    ledger.at[idx, "last_return_date"] = ledger.at[idx, "return_date"]
                    ledger.at[idx, "last_return_event_id"] = ledger.at[idx, "return_event_id"]

                    # create duplicated token for new sellable stock
                    base_new_id = f"{token_id}-R{event_id}"
                    new_id = base_new_id
                    seq = 1
                    while new_id in existing_ids:
                        seq += 1
                        new_id = f"{base_new_id}-{seq}"
                    existing_ids.add(new_id)

                    new_row = {col: ledger.at[idx, col] for col in ledger.columns}
                    new_row["token_id"] = new_id
                    new_row["status"] = "available"
                    new_row["allocated_order_id"] = ""
                    new_row["allocated_date"] = ""
                    new_row["return_order_id"] = ""
                    new_row["return_date"] = ""
                    new_row["return_event_id"] = ""
                    new_row["notes"] = f"return_sellable_dup:{event_id}"
                    ledger = pd.concat([ledger, pd.DataFrame([new_row])], ignore_index=True)

                    # Emit a return ledger row to credit COGS on the return date.
                    return_rows.append(
                        {
                            "return_event_id": event_id,
                            "return_date": row.get("event_date", ""),
                            "seller_sku": sku,
                            "token_id": new_id,
                            "token_cost": ledger.at[idx, "cost_per_unit"],
                            "currency": ledger.at[idx, "currency"],
                            "source": "stock_events_raw",
                            "event_type": row.get("event_type", ""),
                        }
                    )
                    applied += 1
                if applied < qty:
                    missing = qty - applied
                    ledger, created = _append_adjustment_fallback_tokens(
                        ledger,
                        sku=sku,
                        qty=missing,
                        event_id=event_id,
                        disposition=disposition,
                        now_iso=now_iso,
                        event_date=str(row.get("event_date", "")),
                    )
                    applied += created
                    if created > 0:
                        note = "fallback_created_from_adjustment_basis"
                if applied < qty:
                    status = "partial"
                    note = note or "insufficient_returned_pending"
            else:
                # remove from available then warehouse
                remove = abs(qty)
                avail = ledger[(ledger["seller_sku"] == sku) & (ledger["status"] == "available")].copy()
                avail["__received"] = avail["received_date"].apply(parse_date)
                avail = avail.sort_values(by=["__received", "token_id"])
                to_drop = avail.index[:remove]
                mark_disposed(to_drop, event_id, "sellable_negative")
                applied += len(to_drop)
                remaining = remove - len(to_drop)
                if remaining > 0:
                    wh = ledger[(ledger["seller_sku"] == sku) & (ledger["status"] == "warehouse")].copy()
                    wh["__received"] = wh["received_date"].apply(parse_date)
                    wh = wh.sort_values(by=["__received", "token_id"])
                    to_drop = wh.index[:remaining]
                    mark_disposed(to_drop, event_id, "warehouse_negative")
                    applied += len(to_drop)
                if applied < remove:
                    status = "partial"
                    note = "insufficient_tokens_to_remove"
        elif disposition == "RESEARCHING":
            if qty > 0:
                pending = ledger[
                    (ledger["seller_sku"] == sku) & (ledger["status"] == "returned_pending")
                ].copy()
                pending = pending.sort_values(by=["return_date", "token_id"])
                for token_id in pending["token_id"].head(qty).tolist():
                    idx = first_token_index(token_id)
                    if idx is None:
                        continue
                    ledger.at[idx, "status"] = "research_pending"
                    ledger.at[idx, "notes"] = f"return_researching:{event_id}"
                    ledger.at[idx, "last_return_order_id"] = ledger.at[idx, "return_order_id"]
                    ledger.at[idx, "last_return_date"] = ledger.at[idx, "return_date"]
                    ledger.at[idx, "last_return_event_id"] = ledger.at[idx, "return_event_id"]
                    ledger.at[idx, "return_order_id"] = ""
                    ledger.at[idx, "return_date"] = ""
                    ledger.at[idx, "return_event_id"] = ""
                    applied += 1
                if applied < qty:
                    missing = qty - applied
                    ledger, created = _append_adjustment_fallback_tokens(
                        ledger,
                        sku=sku,
                        qty=missing,
                        event_id=event_id,
                        disposition=disposition,
                        now_iso=now_iso,
                        event_date=str(row.get("event_date", "")),
                    )
                    applied += created
                    if created > 0:
                        note = "fallback_created_from_adjustment_basis"
                if applied < qty:
                    status = "partial"
                    note = note or "insufficient_returned_pending"
            else:
                remove = abs(qty)
                pending = ledger[(ledger["seller_sku"] == sku) & (ledger["status"] == "research_pending")].copy()
                pending["__received"] = pending["received_date"].apply(parse_date)
                pending = pending.sort_values(by=["__received", "token_id"])
                to_move = pending.index[:remove]
                for idx in to_move:
                    ledger.loc[idx, "status"] = "available"
                    ledger.loc[idx, "notes"] = f"researching_negative:{event_id}"
                    applied += 1
                if applied < remove:
                    status = "partial"
                    note = "insufficient_research_pending"
        else:
            # non-sellable dispositions -> unsellable
            if qty > 0:
                pending = ledger[
                    (ledger["seller_sku"] == sku) & (ledger["status"] == "returned_pending")
                ].copy()
                pending = pending.sort_values(by=["return_date", "token_id"])
                for token_id in pending["token_id"].head(qty).tolist():
                    idx = first_token_index(token_id)
                    if idx is None:
                        continue
                    ledger.at[idx, "status"] = "unsellable"
                    ledger.at[idx, "notes"] = f"return_unsellable:{event_id}"
                    ledger.at[idx, "last_return_order_id"] = ledger.at[idx, "return_order_id"]
                    ledger.at[idx, "last_return_date"] = ledger.at[idx, "return_date"]
                    ledger.at[idx, "last_return_event_id"] = ledger.at[idx, "return_event_id"]
                    ledger.at[idx, "return_order_id"] = ""
                    ledger.at[idx, "return_date"] = ""
                    ledger.at[idx, "return_event_id"] = ""
                    applied += 1
                if applied < qty:
                    missing = qty - applied
                    ledger, created = _append_adjustment_fallback_tokens(
                        ledger,
                        sku=sku,
                        qty=missing,
                        event_id=event_id,
                        disposition=disposition,
                        now_iso=now_iso,
                        event_date=str(row.get("event_date", "")),
                    )
                    applied += created
                    if created > 0:
                        note = "fallback_created_from_adjustment_basis"
                if applied < qty:
                    status = "partial"
                    note = note or "insufficient_returned_pending"
            else:
                remove = abs(qty)
                uns = ledger[(ledger["seller_sku"] == sku) & (ledger["status"] == "unsellable")].copy()
                uns["__received"] = uns["received_date"].apply(parse_date)
                uns = uns.sort_values(by=["__received", "token_id"])
                to_drop = uns.index[:remove]
                mark_disposed(to_drop, event_id, "unsellable_negative")
                applied += len(to_drop)
                if applied < remove:
                    status = "partial"
                    note = "insufficient_unsellable_to_remove"

        log_rows.append(
            {
                "event_id": event_id,
                "sku": sku,
                "event_date": row.get("event_date", ""),
                "event_type": row.get("event_type", ""),
                "disposition": disposition,
                "quantity": qty,
                "applied_qty": applied,
                "status": status,
                "note": note,
                "event_ts": now_iso,
            }
        )
        applied_ids.add(event_id)

    if not log_rows:
        print({"status": "skip", "reason": "no_new_events"})
        return

    log_df = pd.DataFrame(log_rows)
    output = _write_stock_adjustment_events_output(prior, log_df, use_sheets=use_sheets)

    if return_rows:
        OUT_RETURN_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        return_df = pd.DataFrame(return_rows)
        if OUT_RETURN_LEDGER.exists():
            return_df.to_csv(OUT_RETURN_LEDGER, mode="a", index=False, header=False)
        else:
            return_df.to_csv(OUT_RETURN_LEDGER, index=False)

    if use_sheets:
        # Write updated ledger to sheet
        rows = [ledger.columns.tolist()] + ledger.astype(object).where(pd.notnull(ledger), "").values.tolist()
        ledger_ws.clear()
        ledger_ws.update(rows, value_input_option="RAW")

        # Write events to sheet
        try:
            ev_ws = sheet.worksheet(EVENTS_TAB)
        except gspread.WorksheetNotFound:
            ev_ws = sheet.add_worksheet(title=EVENTS_TAB, rows=max(len(log_rows) + 10, 2000), cols=25)
            ev_ws.update(range_name="A1", values=[list(log_rows[0].keys())])
        if log_rows:
            ev_ws.append_rows([list(r.values()) for r in log_rows], value_input_option="RAW")
    else:
        write_csv_with_compat(ledger, path_or_rel="token_ledger_live.csv", index=False, default_system="B")

    # Ledger completeness summary (daily per SKU/status)
    log_df["event_day"] = log_df["event_date"].apply(to_event_day)
    summary = (
        log_df.groupby(["event_day", "sku", "event_type", "status", "note"], dropna=False)
        .agg(
            events_count=("event_id", "count"),
            quantity_sum=("quantity", "sum"),
            applied_sum=("applied_qty", "sum"),
        )
        .reset_index()
        .sort_values(by=["event_day", "sku", "event_type", "status", "note"])
    )
    OUT_COMPLETENESS.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUT_COMPLETENESS, index=False)

    if use_sheets:
        try:
            comp_ws = sheet.worksheet(COMPLETENESS_TAB)
        except gspread.WorksheetNotFound:
            comp_ws = sheet.add_worksheet(title=COMPLETENESS_TAB, rows=max(len(summary) + 10, 2000), cols=20)
        else:
            comp_ws.clear()
        comp_ws.update(range_name="A1", values=[list(summary.columns)] + summary.astype(str).values.tolist())

    print(
        {
            "status": "success",
            "events": len(log_rows),
            "snapshot": str(OUT_EVENTS),
            "sheet_tab": EVENTS_TAB if use_sheets else "",
            "completeness_snapshot": str(OUT_COMPLETENESS),
            "completeness_tab": COMPLETENESS_TAB if use_sheets else "",
            "return_ledger": str(OUT_RETURN_LEDGER),
            "write_sheets": use_sheets,
            **output,
        }
    )


if __name__ == "__main__":
    main()

