"""
Build daily token validation checks and write to token sheet.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import gspread
import pandas as pd

from scripts.core.storage import read_dataframe_with_sql_fallback

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
TESTS_TAB = "Token_Tests_Daily"

LEDGER_CSV = Path("out/inventory_ledger_raw.csv")
ADJUST_EVENTS_CSV = Path("out/stock_adjustment_token_events.csv")
RECON_SNAPSHOT = Path("out/token_stock_recon_mismatches.csv")
TOKEN_LEDGER_SNAPSHOT = Path("out/token_ledger_live.csv")
ORDERS_SHEET_ID = "1H_EDAYfB_xgGvnW1esOMwWsHs2wBXYoOABcMs7SWcrY"
ORDERS_TAB = "Orders"
ORDERS_CSV = Path("out/orders_sheet_orders.csv")
ORDER_MASTER_CSV = Path("out/order_master.csv")
INVENTORY_CSV = Path("out/inventory_summaries.csv")
SQL_TABLE_INVENTORY_SUMMARIES = "a_inventory_summaries"
REFUNDS_CSV = Path("out/financial_events_refunds_official.csv")
CUTOFF_DATE = "2025-11-01"

OUT_TESTS = Path("out/token_tests_daily.csv")


def get_gspread_client() -> gspread.Client:
    cred_path = Path("secrets/sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=str(cred_path))


def load_sheet_df(tab_name: str) -> pd.DataFrame:
    client = get_gspread_client()
    sheet = client.open_by_key(TOKENS_SHEET_ID)
    try:
        ws = sheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        return pd.DataFrame()
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()
    return pd.DataFrame(values[1:], columns=values[0])


def parse_int(value: str) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def load_orders_df() -> pd.DataFrame:
    if ORDERS_CSV.exists():
        return pd.read_csv(ORDERS_CSV, dtype=str).fillna("")
    client = get_gspread_client()
    sheet = client.open_by_key(ORDERS_SHEET_ID)
    try:
        ws = sheet.worksheet(ORDERS_TAB)
    except gspread.WorksheetNotFound:
        return pd.DataFrame()
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()
    return pd.DataFrame(values[1:], columns=values[0])


def load_order_master() -> pd.DataFrame:
    if not ORDER_MASTER_CSV.exists():
        return pd.DataFrame()
    df = pd.read_csv(ORDER_MASTER_CSV, dtype=str).fillna("")
    return df


def load_inventory() -> pd.DataFrame:
    try:
        return read_dataframe_with_sql_fallback(
            INVENTORY_CSV,
            SQL_TABLE_INVENTORY_SUMMARIES,
            dtype=str,
        ).fillna("")
    except FileNotFoundError:
        return pd.DataFrame()


def load_refunds() -> pd.DataFrame:
    if not REFUNDS_CSV.exists():
        return pd.DataFrame()
    df = pd.read_csv(REFUNDS_CSV, dtype=str).fillna("")
    return df


def ledger_freshness() -> tuple[str, str]:
    if not LEDGER_CSV.exists():
        return "FAIL", "inventory_ledger_raw.csv missing"
    df = pd.read_csv(LEDGER_CSV, dtype=str).fillna("")
    if df.empty:
        return "FAIL", "inventory_ledger_raw.csv empty"
    ts = df.get("Date and Time", pd.Series([""])).astype(str)
    ts = pd.to_datetime(ts, errors="coerce", utc=True)
    latest = ts.max()
    if pd.isna(latest):
        return "WARN", "ledger has no parsable timestamps"
    age_hours = (datetime.now(timezone.utc) - latest).total_seconds() / 3600.0
    if age_hours > 72:
        return "FAIL", f"ledger stale: {age_hours:.1f}h"
    if age_hours > 48:
        return "WARN", f"ledger old: {age_hours:.1f}h"
    return "PASS", f"ledger latest: {latest.isoformat()}"


def adjustment_partials() -> tuple[str, str]:
    if not ADJUST_EVENTS_CSV.exists():
        return "WARN", "stock_adjustment_token_events.csv missing"
    df = pd.read_csv(ADJUST_EVENTS_CSV, dtype=str).fillna("")
    if df.empty:
        return "PASS", "no adjustment events"
    df["quantity"] = pd.to_numeric(df.get("quantity", 0), errors="coerce").fillna(0).astype(int)
    df["applied_qty"] = pd.to_numeric(df.get("applied_qty", 0), errors="coerce").fillna(0).astype(int)
    df["base_event_id"] = df["event_id"].astype(str).str.split("-retry").str[0]
    grouped = (
        df.groupby("base_event_id")
        .agg(
            original_qty=("quantity", lambda s: int(s.abs().max()) if len(s) else 0),
            applied_qty=("applied_qty", "sum"),
            sku=("sku", "first"),
        )
        .reset_index()
    )
    grouped["remaining"] = grouped["original_qty"] - grouped["applied_qty"]
    open_partials = grouped[grouped["remaining"] > 0]
    count = len(open_partials)
    if count == 0:
        return "PASS", "no partial adjustments"
    top = open_partials["sku"].value_counts().head(5).to_dict()
    return "WARN", f"partial adjustments: {count}; top_skus={top}"


def recon_mismatches() -> tuple[str, str]:
    # prefer local snapshot if present; otherwise read sheet
    if RECON_SNAPSHOT.exists():
        df = pd.read_csv(RECON_SNAPSHOT, dtype=str).fillna("")
    else:
        df = load_sheet_df("Token_Stock_Recon_Mismatches")
    if df.empty:
        return "WARN", "recon mismatches source empty/missing"
    # ignore zero deltas if present
    for col in ["delta_available", "delta_total", "delta_total_effective"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    if "delta_total_effective" in df.columns:
        df = df[
            (df.get("delta_available", 0) != 0)
            | (df.get("delta_unsellable", 0) != 0)
            | (df.get("delta_total_effective", 0) != 0)
        ]
    else:
        if "delta_available" in df.columns or "delta_total" in df.columns:
            df = df[(df.get("delta_available", 0) != 0) | (df.get("delta_total", 0) != 0)]
    count = len(df)
    if count == 0:
        return "PASS", "no non-zero mismatches"
    top = (
        df["seller_sku"]
        .value_counts()
        .head(5)
        .to_dict()
        if "seller_sku" in df.columns
        else {}
    )
    return "WARN", f"mismatches: {count}; top_skus={top}"


def duplicate_token_ids() -> tuple[str, str]:
    if TOKEN_LEDGER_SNAPSHOT.exists():
        df = pd.read_csv(TOKEN_LEDGER_SNAPSHOT, dtype=str).fillna("")
    else:
        df = load_sheet_df("Token_Ledger")
    if df.empty or "token_id" not in df.columns:
        return "WARN", "token ledger missing"
    dupes = df["token_id"].duplicated().sum()
    if dupes == 0:
        return "PASS", "no duplicate token_id"
    return "FAIL", f"duplicate token_id count: {dupes}"


def tokens_vs_nov_demand() -> tuple[str, str]:
    # Compare token counts to (net demand since cutoff + current stock available).
    if TOKEN_LEDGER_SNAPSHOT.exists():
        tokens = pd.read_csv(TOKEN_LEDGER_SNAPSHOT, dtype=str).fillna("")
    else:
        tokens = load_sheet_df("Token_Ledger")
    if tokens.empty or "seller_sku" not in tokens.columns:
        return "WARN", "token ledger missing"

    orders = load_order_master()
    if orders.empty:
        return "WARN", "order_master missing"

    orders["Quantity Ordered"] = orders["Quantity Ordered"].apply(parse_int)
    orders = orders[orders["Quantity Ordered"] > 0].copy()
    orders["Date"] = pd.to_datetime(orders["Date"], errors="coerce", utc=True)
    cutoff = pd.to_datetime(CUTOFF_DATE, utc=True)
    orders = orders[orders["Date"] >= cutoff]
    orders = orders.rename(columns={"Order ID": "order_id", "SKU": "sku"})

    refunds = load_refunds()
    refund_map = {}
    if not refunds.empty:
        refunds = refunds.rename(columns={"Order ID": "order_id", "SKU": "sku", "Quantity Ordered": "qty"})
        refunds["qty"] = refunds["qty"].apply(parse_int)
        refunds = refunds[refunds["qty"] > 0]
        for _, r in refunds.iterrows():
            key = (str(r.get("order_id", "")).strip(), str(r.get("sku", "")).strip())
            if not key[0] or not key[1]:
                continue
            refund_map[key] = refund_map.get(key, 0) + int(r["qty"])

    orders["refund_qty"] = orders.apply(
        lambda r: refund_map.get((str(r["order_id"]).strip(), str(r["sku"]).strip()), 0),
        axis=1,
    )
    orders["net_qty"] = (orders["Quantity Ordered"] - orders["refund_qty"]).clip(lower=0)
    net_demand = orders.groupby("sku")["net_qty"].sum()

    inventory = load_inventory()
    if inventory.empty or "available" not in inventory.columns:
        return "WARN", "inventory_summaries missing available"
    inventory["available"] = inventory["available"].apply(parse_int)
    stock = inventory.set_index("seller_sku")["available"]

    target = net_demand.add(stock, fill_value=0)
    token_counts = tokens.groupby("seller_sku").size()

    mismatches = []
    for sku, token_count in token_counts.items():
        target_count = int(target.get(sku, 0))
        if token_count != target_count:
            mismatches.append((sku, target_count, int(token_count)))

    if not mismatches:
        return "PASS", "token counts match net demand + stock"

    top = mismatches[:5]
    detail = "; ".join([f"{sku}:tgt={t},tok={tok}" for sku, t, tok in top])
    return "FAIL", f"nov demand/token mismatches: {len(mismatches)}; top={detail}"


def build_tests() -> pd.DataFrame:
    now = datetime.now(timezone.utc).isoformat()
    tests = []

    status, detail = ledger_freshness()
    tests.append({"timestamp": now, "check": "ledger_freshness", "status": status, "detail": detail})

    status, detail = adjustment_partials()
    tests.append({"timestamp": now, "check": "adjustment_partials", "status": status, "detail": detail})

    status, detail = recon_mismatches()
    tests.append({"timestamp": now, "check": "token_recon_mismatches", "status": status, "detail": detail})

    status, detail = duplicate_token_ids()
    tests.append({"timestamp": now, "check": "duplicate_token_ids", "status": status, "detail": detail})

    status, detail = tokens_vs_nov_demand()
    tests.append({"timestamp": now, "check": "tokens_vs_nov_demand", "status": status, "detail": detail})

    return pd.DataFrame(tests)


def main() -> None:
    df = build_tests()
    if df.empty:
        print({"status": "skip", "reason": "no_tests"})
        return

    OUT_TESTS.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_TESTS, index=False)

    client = get_gspread_client()
    sheet = client.open_by_key(TOKENS_SHEET_ID)
    payload = [list(df.columns)] + df.fillna("").astype(str).values.tolist()
    try:
        ws = sheet.worksheet(TESTS_TAB)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=TESTS_TAB, rows=max(len(payload) + 10, 2000), cols=20)
    else:
        ws.clear()
    ws.update(range_name="A1", values=payload)

    print({"status": "success", "rows": len(df), "snapshot": str(OUT_TESTS), "tab": TESTS_TAB})


if __name__ == "__main__":
    main()

