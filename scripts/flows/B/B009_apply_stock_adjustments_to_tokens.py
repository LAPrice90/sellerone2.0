"""
Apply stock adjustment events to token ledger (FIFO by return_date).

Uses out/stock_events_raw.csv (from A006) and updates Token_Ledger.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import gspread
import pandas as pd
import os

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


def get_gspread_client() -> gspread.Client:
    cred_path = Path("secrets/sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=str(cred_path))


def load_sheet_df(ws: gspread.Worksheet) -> pd.DataFrame:
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

    client = get_gspread_client()
    sheet = client.open_by_key(TOKENS_SHEET_ID)
    ledger_ws = sheet.worksheet(TOKEN_LEDGER_TAB)
    ledger = load_sheet_df(ledger_ws)
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
    try:
        ev_ws = sheet.worksheet(EVENTS_TAB)
        prior = load_sheet_df(ev_ws)
        applied_ids = set(prior["event_id"].tolist()) if "event_id" in prior.columns else set()
    except gspread.WorksheetNotFound:
        applied_ids = set()
        prior = pd.DataFrame()

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

    for _, row in events.iterrows():
        note = ""
        base_event_id = str(row.get("event_id", "")).strip()
        if not base_event_id:
            continue
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
                    status = "partial"
                    note = "insufficient_returned_pending"
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
                    status = "partial"
                    note = "insufficient_returned_pending"
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
                    status = "partial"
                    note = "insufficient_returned_pending"
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

    if not log_rows:
        print({"status": "skip", "reason": "no_new_events"})
        return

    OUT_EVENTS.parent.mkdir(parents=True, exist_ok=True)
    log_df = pd.DataFrame(log_rows)
    if OUT_EVENTS.exists():
        log_df.to_csv(OUT_EVENTS, mode="a", index=False, header=False)
    else:
        log_df.to_csv(OUT_EVENTS, index=False)

    if return_rows:
        OUT_RETURN_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        return_df = pd.DataFrame(return_rows)
        if OUT_RETURN_LEDGER.exists():
            return_df.to_csv(OUT_RETURN_LEDGER, mode="a", index=False, header=False)
        else:
            return_df.to_csv(OUT_RETURN_LEDGER, index=False)

    if WRITE_SHEETS:
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
        OUT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        ledger.to_csv(OUT_LEDGER, index=False)

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

    if WRITE_SHEETS:
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
            "sheet_tab": EVENTS_TAB,
            "completeness_snapshot": str(OUT_COMPLETENESS),
            "completeness_tab": COMPLETENESS_TAB,
            "return_ledger": str(OUT_RETURN_LEDGER),
            "write_sheets": WRITE_SHEETS,
        }
    )


if __name__ == "__main__":
    main()

