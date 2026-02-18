"""
Apply research-pending deltas from inventory summaries to token ledger.

Purpose:
- Inventory "researching" units do NOT appear in stock events.
- We reconcile day-to-day changes using inventory snapshots.
- Delta > 0 moves tokens from available -> research_pending (newest first).
- Delta < 0 moves tokens from research_pending -> available (newest first).

Sheets are written only if STOCK_EVENTS_WRITE_SHEETS=1 (default is 0).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import os

import pandas as pd
import gspread

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
TOKEN_LEDGER_TAB = "Token_Ledger"
EVENTS_TAB = "Researching_Delta_Events"

WRITE_SHEETS = os.environ.get("STOCK_EVENTS_WRITE_SHEETS", "0").strip() == "1"
CURR_PATH = Path(os.environ.get("RESEARCH_CURR_SNAPSHOT", "out/inventory_summaries.csv"))
PREV_PATH = Path(os.environ.get("RESEARCH_PREV_SNAPSHOT", "out/inventory_summaries_prev.csv"))
OUT_EVENTS = Path("out/researching_delta_events.csv")
OUT_LEDGER = Path("out/token_ledger_live.csv")
ARCHIVE = os.environ.get("RESEARCH_ARCHIVE_SNAPSHOT", "0").strip() == "1"
BOOTSTRAP = os.environ.get("RESEARCH_BOOTSTRAP", "0").strip() == "1"
MODE = os.environ.get("INV_DELTA_MODE", "researching").strip().lower()


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


def main() -> None:
    if not CURR_PATH.exists():
        raise SystemExit(f"Missing {CURR_PATH}")

    curr = pd.read_csv(CURR_PATH, dtype=str).fillna("")
    if "seller_sku" not in curr.columns:
        raise SystemExit("inventory_summaries.csv missing seller_sku")
    if MODE == "researching" and "researching" not in curr.columns:
        raise SystemExit("inventory_summaries.csv missing researching")
    if MODE == "unsellable" and "unsellable" not in curr.columns:
        raise SystemExit("inventory_summaries.csv missing unsellable")

    if not PREV_PATH.exists():
        # Seed prev snapshot and exit; no delta to apply yet.
        PREV_PATH.parent.mkdir(parents=True, exist_ok=True)
        curr.to_csv(PREV_PATH, index=False)
        print({"status": "seeded_prev_snapshot", "path": str(PREV_PATH)})
        return

    prev = pd.read_csv(PREV_PATH, dtype=str).fillna("")
    if "seller_sku" not in prev.columns:
        raise SystemExit("prev inventory snapshot missing seller_sku")
    if MODE == "researching" and "researching" not in prev.columns:
        raise SystemExit("prev inventory snapshot missing researching")
    if MODE == "unsellable" and "unsellable" not in prev.columns:
        raise SystemExit("prev inventory snapshot missing unsellable")

    field = "researching" if MODE == "researching" else "unsellable"
    curr_map = (
        curr.assign(value=curr[field].apply(parse_int))
        .groupby("seller_sku")["value"]
        .sum()
        .to_dict()
    )
    prev_map = (
        prev.assign(value=prev[field].apply(parse_int))
        .groupby("seller_sku")["value"]
        .sum()
        .to_dict()
    )

    deltas = []
    if not BOOTSTRAP:
        for sku, curr_val in curr_map.items():
            prev_val = prev_map.get(sku, 0)
            delta = int(curr_val) - int(prev_val)
            if delta != 0:
                deltas.append({"seller_sku": sku, "delta": delta, "prev": int(prev_val), "curr": int(curr_val)})

        if not deltas:
            # Still update prev snapshot for next run
            curr.to_csv(PREV_PATH, index=False)
            print({"status": "no_deltas"})
            return

    # Load token ledger
    ledger = None
    if WRITE_SHEETS:
        client = get_gspread_client()
        sheet = client.open_by_key(TOKENS_SHEET_ID)
        ledger_ws = sheet.worksheet(TOKEN_LEDGER_TAB)
        ledger = load_sheet_df(ledger_ws)
    else:
        if not OUT_LEDGER.exists():
            raise SystemExit("Missing out/token_ledger_live.csv and sheets write disabled")
        ledger = pd.read_csv(OUT_LEDGER, dtype=str).fillna("")

    if ledger.empty:
        raise SystemExit("Token ledger empty")

    if "status" not in ledger.columns:
        ledger["status"] = ""
    if "notes" not in ledger.columns:
        ledger["notes"] = ""

    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    event_rows = []

    if BOOTSTRAP:
        # Align research_pending tokens to current researching counts
        status_target = "research_pending" if MODE == "researching" else "unsellable"
        token_counts = (
            ledger[ledger["status"] == status_target]
            .groupby("seller_sku")["token_id"]
            .count()
            .to_dict()
        )
        for sku, curr_val in curr_map.items():
            desired = int(curr_val)
            current = int(token_counts.get(sku, 0))
            delta = desired - current
            if delta != 0:
                deltas.append({"seller_sku": sku, "delta": delta, "prev": current, "curr": desired})

        if not deltas:
            curr.to_csv(PREV_PATH, index=False)
            print({"status": "no_deltas"})
            return

    for row in deltas:
        sku = row["seller_sku"]
        delta = row["delta"]
        applied = 0
        status = "ok"
        note = ""

        if delta > 0:
            # Move newest available -> target status
            avail = ledger[(ledger["seller_sku"] == sku) & (ledger["status"] == "available")].copy()
            if avail.empty:
                status = "partial"
                note = "no_available_tokens"
            else:
                avail["__rank"] = pd.to_numeric(
                    avail.get("lot_rank_num", avail.get("lot_rank", 0)),
                    errors="coerce",
                ).fillna(0).astype(int)
                avail = avail.sort_values("__rank", ascending=False)
                to_move = avail.index[: delta]
                for idx in to_move:
                    ledger.loc[idx, "status"] = "research_pending" if MODE == "researching" else "unsellable"
                    ledger.loc[idx, "notes"] = f"{MODE}_delta:{now_iso}"
                    applied += 1
                if applied < delta:
                    status = "partial"
                    note = "insufficient_available"
        else:
            # Move newest target status -> available
            move_count = abs(delta)
            pending = ledger[(ledger["seller_sku"] == sku) & (ledger["status"] == ("research_pending" if MODE == "researching" else "unsellable"))].copy()
            if pending.empty:
                status = "partial"
                note = "no_target_tokens"
            else:
                pending["__rank"] = pd.to_numeric(
                    pending.get("lot_rank_num", pending.get("lot_rank", 0)),
                    errors="coerce",
                ).fillna(0).astype(int)
                pending = pending.sort_values("__rank", ascending=False)
                to_move = pending.index[: move_count]
                for idx in to_move:
                    ledger.loc[idx, "status"] = "available"
                    ledger.loc[idx, "notes"] = f"{MODE}_delta:{now_iso}"
                    applied += 1
                if applied < move_count:
                    status = "partial"
                    note = "insufficient_target_tokens"

        event_rows.append(
            {
                "event_time": now_iso,
                "seller_sku": sku,
                "delta": delta,
                "applied": applied,
                "status": status,
                "note": note,
                f"prev_{field}": row["prev"],
                f"curr_{field}": row["curr"],
            }
        )

    events_df = pd.DataFrame(event_rows)
    OUT_EVENTS.parent.mkdir(parents=True, exist_ok=True)
    events_df.to_csv(OUT_EVENTS, index=False)

    if WRITE_SHEETS:
        # Write events to sheet and update ledger
        try:
            ev_ws = sheet.worksheet(EVENTS_TAB)
        except gspread.WorksheetNotFound:
            ev_ws = sheet.add_worksheet(title=EVENTS_TAB, rows=max(len(events_df) + 10, 2000), cols=12)
        payload = [events_df.columns.tolist()] + events_df.astype(object).where(pd.notnull(events_df), "").values.tolist()
        ev_ws.clear()
        ev_ws.update(range_name="A1", values=payload)

        payload = [ledger.columns.tolist()] + ledger.astype(object).where(pd.notnull(ledger), "").values.tolist()
        ledger_ws.clear()
        ledger_ws.update(range_name="A1", values=payload)
    else:
        # Write local ledger only
        ledger.to_csv(OUT_LEDGER, index=False)

    # Update prev snapshot for next run
    curr.to_csv(PREV_PATH, index=False)
    if ARCHIVE:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        archive_path = Path("out/inventory_summaries_archive")
        archive_path.mkdir(parents=True, exist_ok=True)
        curr.to_csv(archive_path / f"inventory_summaries_{stamp}.csv", index=False)

    print(
        {
            "status": "success",
            "skus_with_deltas": len(deltas),
            "events": len(event_rows),
            "events_csv": str(OUT_EVENTS),
            "ledger_written": "sheet" if WRITE_SHEETS else str(OUT_LEDGER),
        }
    )


if __name__ == "__main__":
    main()
