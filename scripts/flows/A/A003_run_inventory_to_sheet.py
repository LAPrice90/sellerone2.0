"""
Fetch FBA inventory summaries and write to Sheets/CSV.

Flow:
- Read active SKUs from out/merchant_listings_latest.csv unless INVENTORY_INCLUDE_INACTIVE=1.
- Call /fba/inventory/v1/summaries (paged) and keep only active records when filtering is enabled.
- Write raw data to Sheets tab Inventory_raw and save CSV snapshot.
- Update Run_Status row.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set

import gspread
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api.get_inventory_summaries import (
    fetch_inventory_summaries,
    get_lwa_access_token,
    load_dotenv_if_missing,
)
from run_api_collection import run_api_collection as run_api_collection_entry

SHEET_ID = "1b7iREy92vF_a1Lw72g0SOGS7t4-IOSBeeoHetLTN43s"
TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
TOKEN_LEDGER_TAB = "Token_Ledger"
TOKEN_RECON_TAB = "Token_Stock_Recon"
TOKEN_RECON_MISMATCH_TAB = "Token_Stock_Recon_Mismatches"
RAW_TAB = "Inventory_raw"
SUMMARY_TAB = "Listings_focus_summary"
RUN_STATUS_TAB = "Run_Status"
PRODUCT_DB_TAB = "Product_DB"
MARKETPLACE_ID = os.environ.get("MARKETPLACE_ID", "A1F83G8C2ARO7P")
INPUT_CSV = os.environ.get("INVENTORY_INPUT_CSV", "out/merchant_listings_latest.csv")
INCLUDE_INACTIVE = os.environ.get("INVENTORY_INCLUDE_INACTIVE", "1").strip() == "1"
LIMIT_PAGES = int(os.environ.get("INVENTORY_LIMIT_PAGES", "0"))  # 0 = no limit
SLEEP_SEC = float(os.environ.get("INVENTORY_SLEEP_SEC", "1.0"))
WRITE_SHEETS = os.environ.get("INVENTORY_WRITE_SHEETS", "1").strip() == "1"
WRITE_RAW_TAB = os.environ.get("INVENTORY_WRITE_RAW", "1").strip() == "1"
WRITE_SUMMARY_TAB = os.environ.get("INVENTORY_WRITE_SUMMARY", "1").strip() == "1"
WRITE_PRODUCT_DB = os.environ.get("INVENTORY_WRITE_PRODUCT_DB", "1").strip() == "1"
WRITE_TOKEN_RECON = os.environ.get("INVENTORY_WRITE_TOKEN_RECON", "1").strip() == "1"
USE_API_OWNER = os.environ.get("INVENTORY_USE_API_OWNER", "1").strip() == "1"
FOCUS_COLUMNS = [
    "asin",
    "fnsku",
    "seller_sku",
    "total_quantity",
    "in_stock_supply_quantity",
    "inbound_working",
    "inbound_shipped",
    "inbound_receiving",
    "available",
    "unsellable",
    "researching",
    "reserved_transfers",
    "reserved_processing",
    "reserved_customer",
    "last_updated_time",
]


def load_active_skus(csv_path: Path) -> Set[str]:
    df = pd.read_csv(csv_path, dtype=str).fillna("")
    skus: Set[str] = set()
    if "seller-sku" in df.columns:
        skus.update([s for s in df["seller-sku"].tolist() if s])
    if "seller_sku" in df.columns:
        skus.update([s for s in df["seller_sku"].tolist() if s])
    return skus


def records_to_df(records: List[Dict[str, object]]) -> pd.DataFrame:
    # Flatten selected fields
    flat: List[Dict[str, object]] = []
    for r in records:
        summary = r or {}
        fba = summary.get("inventoryDetails") or {}
        reserved = (fba.get("reservedQuantity") or {}).copy() if isinstance(fba.get("reservedQuantity"), dict) else {}
        inbound = (fba.get("inboundWorkingQuantity") or 0, fba.get("inboundShippedQuantity") or 0, fba.get("inboundReceivingQuantity") or 0)
        reserved_map = {
            "transfers": reserved.get("pendingTransshipmentQuantity", 0),
            "processing": reserved.get("fcProcessingQuantity", 0),
            "customer_reserved": reserved.get("pendingCustomerOrderQuantity", 0),
        }
        unfulfillable = fba.get("unfulfillableQuantity") or {}
        researching = fba.get("researchingQuantity", 0)
        if isinstance(researching, dict):
            researching = researching.get("totalResearchingQuantity", 0)
        if isinstance(unfulfillable, dict) and researching in (None, 0, ""):
            researching = unfulfillable.get("researchingQuantity", 0)
            if isinstance(researching, dict):
                researching = researching.get("totalResearchingQuantity", 0)
        fulfillable = fba.get("fulfillableQuantity")
        if fulfillable is None:
            fulfillable = fba.get("availableQuantity", 0)
        flat.append(
            {
                "asin": summary.get("asin", ""),
                "fnsku": summary.get("fnSku", ""),
                "seller_sku": summary.get("sellerSku", ""),
                "condition": summary.get("condition", ""),
                "inventory_status": summary.get("inventoryStatus", ""),
                "total_quantity": summary.get("totalQuantity", 0),
                "in_stock_supply_quantity": fulfillable if fulfillable is not None else 0,
                "inbound_working": inbound[0],
                "inbound_shipped": inbound[1],
                "inbound_receiving": inbound[2],
                "available": fulfillable if fulfillable is not None else 0,
                "unsellable": (unfulfillable.get("totalUnfulfillableQuantity", 0) if isinstance(unfulfillable, dict) else 0),
                "researching": researching or 0,
                "reserved_transfers": reserved_map["transfers"],
                "reserved_processing": reserved_map["processing"],
                "reserved_customer": reserved_map["customer_reserved"],
                "last_updated_time": summary.get("lastUpdatedTime", ""),
            }
        )
    return pd.DataFrame(flat)


def load_prev_focus_counts(sheet: gspread.Spreadsheet) -> dict:
    try:
        ws = sheet.worksheet(SUMMARY_TAB)
    except gspread.WorksheetNotFound:
        return {}
    values = ws.get_all_values()
    if not values or len(values) < 2:
        return {}
    prev = {}
    for row in values[1:]:
        if len(row) < 3 or row[0] != "A003":
            continue
        col = row[1]
        try:
            prev_count = int(row[2])
        except Exception:
            prev_count = 0
        prev[col] = prev_count
    return prev


def summarize_focus(df: pd.DataFrame, prev_counts: dict) -> list[list[str]]:
    rows: list[list[str]] = [["script", "column", "prev_non_empty", "curr_non_empty", "delta", "percent_change", "flag"]]
    script_name = "A003"
    for col in FOCUS_COLUMNS:
        curr = int((df[col].astype(str).str.len() > 0).sum()) if col in df.columns else 0
        prev = prev_counts.get(col, 0)
        delta = curr - prev
        pct = ""
        if prev > 0:
            pct = f"{(delta / prev) * 100:.1f}%"
        if prev > 0 and curr == 0:
            flag = "drop_to_zero"
        elif prev > 0 and curr < prev * 0.8:
            flag = "drop_over_20pct"
        else:
            flag = "ok"
        rows.append([script_name, col, str(prev), str(curr), str(delta), pct, flag])
    return rows


def get_gspread_client() -> gspread.Client:
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        cred_path = str(Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=cred_path)


def export_product_db(sheet: gspread.Spreadsheet) -> None:
    """Dump Product_DB sheet to out/product_db_preview.csv."""
    try:
        ws = sheet.worksheet(PRODUCT_DB_TAB)
    except gspread.WorksheetNotFound:
        return
    rows = ws.get_all_values()
    if not rows:
        return
    Path("out").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows[1:], columns=rows[0]).to_csv("out/product_db_preview.csv", index=False)
    print("Saved Product_DB preview to out/product_db_preview.csv")


def update_product_db_stock(sheet: gspread.Spreadsheet, df: pd.DataFrame, run_ts: str) -> None:
    """Merge stock fields into Product_DB while preserving manual columns."""
    try:
        ws = sheet.worksheet(PRODUCT_DB_TAB)
    except gspread.WorksheetNotFound:
        return
    prod_rows = ws.get_all_values()
    if not prod_rows:
        return
    headers = prod_rows[0]
    idx_map = {h: i for i, h in enumerate(headers)}
    if "last_updated_A003" not in idx_map:
        idx_map["last_updated_A003"] = len(headers)
        headers.append("last_updated_A003")
        for row in prod_rows[1:]:
            while len(row) < len(headers):
                row.append("")
    prod_dict = {}
    asin_index = {}
    for idx, row in enumerate(prod_rows[1:], start=2):
        asin_val = row[idx_map.get("asin", -1)] if idx_map.get("asin", -1) >= 0 and len(row) > idx_map.get("asin") else ""
        sku_val = row[idx_map.get("seller_sku", -1)] if idx_map.get("seller_sku", -1) >= 0 and len(row) > idx_map.get("seller_sku") else ""
        key = (asin_val, sku_val)
        prod_dict[key] = [idx, row]
        if asin_val:
            asin_index.setdefault(asin_val, []).append([idx, row])

    def to_int_str(val) -> str:
        try:
            return str(int(float(val)))
        except Exception:
            return "0"

    def to_num(val) -> float:
        try:
            return float(val)
        except Exception:
            return 0.0

    for _, r in df.iterrows():
        asin = str(r.get("asin", ""))
        sku = str(r.get("seller_sku", ""))
        if not asin and not sku:
            continue
        targets = []
        key = (asin, sku)
        if key in prod_dict:
            targets = [prod_dict[key]]
        elif asin and asin in asin_index:
            targets = asin_index[asin]
        else:
            row_idx, row_data = None, [""] * len(headers)
            if "asin" in idx_map:
                while len(row_data) <= idx_map["asin"]:
                    row_data.append("")
                row_data[idx_map["asin"]] = asin
            if "seller_sku" in idx_map:
                while len(row_data) <= idx_map["seller_sku"]:
                    row_data.append("")
                row_data[idx_map["seller_sku"]] = sku
            target = [row_idx, row_data]
            targets = [target]
            prod_dict[key] = target
            if asin:
                asin_index.setdefault(asin, []).append(target)

        total_qty = to_int_str(to_num(r.get("total_quantity", 0)))
        available = to_int_str(to_num(r.get("available", 0)))
        reserved = to_int_str(
            to_num(r.get("reserved_transfers", 0)) + to_num(r.get("reserved_processing", 0)) + to_num(r.get("reserved_customer", 0))
        )
        inbound = to_int_str(
            to_num(r.get("inbound_working", 0)) + to_num(r.get("inbound_shipped", 0)) + to_num(r.get("inbound_receiving", 0))
        )
        last_updated_time = str(r.get("last_updated_time", "")) or run_ts

        def set_val(row_data, field, value):
            if field in idx_map:
                col = idx_map[field]
                while len(row_data) <= col:
                    row_data.append("")
                row_data[col] = str(value)

        for target in targets:
            _, row_data = target
            set_val(row_data, "stock_total", total_qty)
            set_val(row_data, "stock_available", available)
            set_val(row_data, "stock_reserved", reserved)
            set_val(row_data, "stock_inbound", inbound)
            set_val(row_data, "last_updated", last_updated_time)
            set_val(row_data, "last_updated_A003", run_ts)

    rows_out = [headers]
    items = list(prod_dict.items())
    items.sort(key=lambda kv: kv[1][0] if kv[1][0] is not None else 10**9)
    for _, (idx, row_data) in items:
        rows_out.append(row_data)
    ws.clear()
    ws.update(range_name="A1", values=rows_out)


def update_local_product_db_stock(product_db_path: Path, df: pd.DataFrame, run_ts: str) -> int:
    """Refresh local out/product_db_preview.csv stock fields from inventory snapshot data."""
    if not product_db_path.exists():
        print(f"Skipped local Product DB refresh (missing file): {product_db_path}")
        return 0
    try:
        prod = pd.read_csv(product_db_path, dtype=str, keep_default_na=False)
    except Exception as exc:
        print(f"Skipped local Product DB refresh (read error): {exc}")
        return 0
    if prod.empty:
        print(f"Skipped local Product DB refresh (empty file): {product_db_path}")
        return 0
    if "seller_sku" not in prod.columns and "asin" not in prod.columns:
        print("Skipped local Product DB refresh (missing seller_sku/asin columns)")
        return 0

    def to_int_str(val) -> str:
        try:
            return str(int(float(val)))
        except Exception:
            return "0"

    inv = df.copy()
    if inv.empty:
        print("Skipped local Product DB refresh (no inventory rows)")
        return 0
    if "seller_sku" not in inv.columns and "sku" in inv.columns:
        inv["seller_sku"] = inv["sku"]
    if "asin" not in inv.columns:
        inv["asin"] = ""
    if "seller_sku" not in inv.columns:
        inv["seller_sku"] = ""
    if "total_quantity" not in inv.columns:
        inv["total_quantity"] = 0
    if "available" not in inv.columns:
        inv["available"] = 0
    for col in ("reserved_transfers", "reserved_processing", "reserved_customer", "inbound_working", "inbound_shipped", "inbound_receiving"):
        if col not in inv.columns:
            inv[col] = 0
    if "last_updated_time" not in inv.columns:
        inv["last_updated_time"] = ""

    inv["asin"] = inv["asin"].astype(str)
    inv["seller_sku"] = inv["seller_sku"].astype(str)
    inv["stock_total"] = inv["total_quantity"].apply(to_int_str)
    inv["stock_available"] = inv["available"].apply(to_int_str)
    inv["stock_reserved"] = (
        pd.to_numeric(inv["reserved_transfers"], errors="coerce").fillna(0.0)
        + pd.to_numeric(inv["reserved_processing"], errors="coerce").fillna(0.0)
        + pd.to_numeric(inv["reserved_customer"], errors="coerce").fillna(0.0)
    ).apply(to_int_str)
    inv["stock_inbound"] = (
        pd.to_numeric(inv["inbound_working"], errors="coerce").fillna(0.0)
        + pd.to_numeric(inv["inbound_shipped"], errors="coerce").fillna(0.0)
        + pd.to_numeric(inv["inbound_receiving"], errors="coerce").fillna(0.0)
    ).apply(to_int_str)
    inv["last_updated"] = inv["last_updated_time"].astype(str).replace("", run_ts)

    stock_by_key = {}
    stock_by_asin = {}
    for _, row in inv.iterrows():
        asin = row.get("asin", "")
        sku = row.get("seller_sku", "")
        payload = {
            "stock_total": row.get("stock_total", "0"),
            "stock_available": row.get("stock_available", "0"),
            "stock_reserved": row.get("stock_reserved", "0"),
            "stock_inbound": row.get("stock_inbound", "0"),
            "last_updated": row.get("last_updated", run_ts),
        }
        if asin or sku:
            stock_by_key[(asin, sku)] = payload
        if asin:
            stock_by_asin[asin] = payload

    if not stock_by_key and not stock_by_asin:
        print("Skipped local Product DB refresh (no usable inventory keys)")
        return 0

    updated_rows = 0
    a003_cols = [c for c in prod.columns if c.startswith("last_updated_A003")]
    if not a003_cols:
        prod["last_updated_A003"] = ""
        a003_cols = ["last_updated_A003"]

    for i, row in prod.iterrows():
        asin = str(row.get("asin", ""))
        sku = str(row.get("seller_sku", ""))
        payload = stock_by_key.get((asin, sku))
        if payload is None and asin:
            payload = stock_by_asin.get(asin)
        if payload is None:
            continue
        for field in ("stock_total", "stock_available", "stock_reserved", "stock_inbound", "last_updated"):
            if field in prod.columns:
                prod.at[i, field] = str(payload.get(field, ""))
        for col in a003_cols:
            prod.at[i, col] = run_ts
        updated_rows += 1

    prod.to_csv(product_db_path, index=False)
    print(f"Refreshed local Product DB stock rows={updated_rows} path={product_db_path}")
    return updated_rows


def write_token_stock_recon(df: pd.DataFrame) -> None:
    """Write inventory vs token availability reconciliation to token sheet."""
    client = get_gspread_client()
    token_sheet = client.open_by_key(TOKENS_SHEET_ID)
    try:
        token_ws = token_sheet.worksheet(TOKEN_LEDGER_TAB)
    except gspread.WorksheetNotFound:
        return

    token_rows = token_ws.get_all_values()
    if not token_rows:
        return
    token_df = pd.DataFrame(token_rows[1:], columns=token_rows[0])
    if token_df.empty:
        return

    token_df["status"] = token_df.get("status", "").fillna("")
    token_df["seller_sku"] = token_df.get("seller_sku", "").fillna("")
    token_counts = token_df.groupby("seller_sku")["token_id"].count().rename("token_total")
    token_available = token_df[token_df["status"] == "available"].groupby("seller_sku")["token_id"].count().rename(
        "token_available"
    )
    token_unsellable = token_df[token_df["status"] == "unsellable"].groupby("seller_sku")["token_id"].count().rename(
        "token_unsellable"
    )
    token_research_pending = token_df[token_df["status"] == "research_pending"].groupby("seller_sku")[
        "token_id"
    ].count().rename("token_research_pending")
    token_returned_pending = token_df[token_df["status"] == "returned_pending"].groupby("seller_sku")[
        "token_id"
    ].count().rename("token_returned_pending")
    token_ordered = token_df[token_df["status"] == "ordered"].groupby("seller_sku")["token_id"].count().rename(
        "token_ordered"
    )
    token_warehouse = token_df[token_df["status"] == "warehouse"].groupby("seller_sku")["token_id"].count().rename(
        "token_warehouse"
    )
    token_allocated = token_df[token_df["status"] == "allocated"].groupby("seller_sku")["token_id"].count().rename(
        "token_allocated"
    )

    inv = df.copy()
    inv["seller_sku"] = inv["seller_sku"].astype(str)
    inv["inventory_available"] = inv["available"].fillna(0).astype(int)
    inv["inventory_unsellable"] = inv["unsellable"].fillna(0).astype(int)
    inv["inventory_researching"] = inv["researching"].fillna(0).astype(int)
    inv["inventory_inbound_shipped"] = inv["inbound_shipped"].fillna(0).astype(int)
    inv["inventory_inbound_receiving"] = inv["inbound_receiving"].fillna(0).astype(int)
    inv["inventory_inbound_total"] = inv["inventory_inbound_shipped"] + inv["inventory_inbound_receiving"]
    include_inbound_available = os.environ.get("TOKEN_AVAILABLE_INCLUDE_INBOUND", "0") == "1"
    inv["inventory_available_effective"] = (
        inv["inventory_available"]
        + inv["reserved_transfers"].fillna(0).astype(int)
        + inv["reserved_processing"].fillna(0).astype(int)
        + (inv["inventory_inbound_total"] if include_inbound_available else 0)
    )
    # Treat FC transfer/processing as stock; exclude customer-reserved as sold.
    inv["inventory_total"] = (
        inv["inventory_available"]
        + inv["inventory_inbound_total"]
        + inv["reserved_transfers"].fillna(0).astype(int)
        + inv["reserved_processing"].fillna(0).astype(int)
    )

    sold_qty = {}
    if Path("out/order_master.csv").exists():
        om = pd.read_csv("out/order_master.csv")
        om = om[om["Quantity Ordered"] > 0]
        sold_qty = (
            om.groupby("SKU")["Quantity Ordered"].sum().astype(int).to_dict()
        )

    def to_int(val) -> int:
        try:
            return int(float(val))
        except Exception:
            return 0

    refunded_qty = {}
    refunds_path = Path("out/financial_events_refunds_official.csv")
    if refunds_path.exists():
        rf = pd.read_csv(refunds_path, dtype=str)
        if not rf.empty and "SKU" in rf.columns:
            rf["Quantity Ordered"] = rf["Quantity Ordered"].apply(to_int)
            rf.loc[rf["Quantity Ordered"] <= 0, "Quantity Ordered"] = 1
            refunded_qty = rf.groupby("SKU")["Quantity Ordered"].sum().astype(int).to_dict()

    recon = inv[
        [
            "seller_sku",
            "inventory_available",
            "inventory_available_effective",
            "inventory_unsellable",
            "inventory_researching",
            "inventory_inbound_shipped",
            "inventory_inbound_receiving",
            "inventory_inbound_total",
            "inventory_total",
        ]
    ].set_index("seller_sku")
    recon = (
        recon.join(token_counts, how="outer")
        .join(token_available, how="outer")
        .join(token_unsellable, how="outer")
        .join(token_research_pending, how="outer")
        .join(token_returned_pending, how="outer")
        .join(token_ordered, how="outer")
        .join(token_warehouse, how="outer")
        .join(token_allocated, how="outer")
        .fillna(0)
        .reset_index()
    )
    recon["sold_qty"] = recon["seller_sku"].map(sold_qty).fillna(0).astype(int)
    recon["refunded_qty"] = recon["seller_sku"].map(refunded_qty).fillna(0).astype(int)
    recon["net_sold_qty"] = (recon["sold_qty"] - recon["refunded_qty"]).clip(lower=0)
    recon["expected_token_total"] = recon["inventory_total"] + recon["net_sold_qty"]
    recon["token_total"] = recon["token_total"].astype(int)
    recon["token_available"] = recon["token_available"].astype(int)
    recon["token_unsellable"] = recon["token_unsellable"].astype(int)
    recon["token_research_pending"] = recon["token_research_pending"].astype(int)
    recon["token_returned_pending"] = recon["token_returned_pending"].astype(int)
    recon["token_ordered"] = recon["token_ordered"].astype(int)
    recon["token_warehouse"] = recon["token_warehouse"].astype(int)
    recon["token_allocated"] = recon["token_allocated"].astype(int)
    recon["token_total_effective"] = (
        recon["token_available"]
        + recon["token_unsellable"]
        + recon["token_research_pending"]
        + recon["token_returned_pending"]
        + recon["token_allocated"]
    )
    recon["expected_token_total_effective"] = (
        recon["expected_token_total"]
        + recon["inventory_unsellable"].astype(int)
        + recon["inventory_researching"].astype(int)
    )
    recon["delta_available"] = recon["token_available"] - recon["inventory_available_effective"]
    recon["delta_unsellable"] = recon["token_unsellable"] - recon["inventory_unsellable"]
    recon["delta_researching"] = recon["token_research_pending"] - recon["inventory_researching"]
    recon["delta_total"] = recon["token_total"] - recon["expected_token_total"]
    recon["delta_total_effective"] = recon["token_total_effective"] - recon["expected_token_total_effective"]
    recon["updated_at"] = datetime.now(timezone.utc).isoformat()

    payload = [recon.columns.tolist()] + recon.astype(object).where(pd.notnull(recon), "").values.tolist()
    try:
        recon_ws = token_sheet.worksheet(TOKEN_RECON_TAB)
    except gspread.WorksheetNotFound:
        recon_ws = token_sheet.add_worksheet(
            title=TOKEN_RECON_TAB,
            rows=max(len(payload) + 10, 2000),
            cols=max(len(recon.columns) + 5, 20),
        )
    else:
        recon_ws.clear()
    recon_ws.update(range_name="A1", values=payload)
    # Write local snapshots for tests
    Path("out").mkdir(parents=True, exist_ok=True)
    recon.to_csv("out/token_stock_recon.csv", index=False)

    mismatches = recon[
        (recon["delta_available"] != 0)
        | (recon["delta_unsellable"] != 0)
        | (recon["delta_researching"] != 0)
        | (recon["delta_total_effective"] != 0)
    ].copy()
    try:
        mismatches_ws = token_sheet.worksheet(TOKEN_RECON_MISMATCH_TAB)
    except gspread.WorksheetNotFound:
        mismatches_ws = token_sheet.add_worksheet(
            title=TOKEN_RECON_MISMATCH_TAB,
            rows=max(len(mismatches) + 10, 2000),
            cols=max(len(recon.columns) + 5, 30),
        )
    else:
        mismatches_ws.clear()
    if mismatches.empty:
        mismatches_ws.update(range_name="A1", values=[["status"], ["no_mismatches"]])
    else:
        mismatches_ws.update(range_name="A1", values=[mismatches.columns.tolist()] + mismatches.values.tolist())
    mismatches.to_csv("out/token_stock_recon_mismatches.csv", index=False)


def write_raw(df: pd.DataFrame) -> None:
    client = None
    sheet = None
    if WRITE_SHEETS:
        client = get_gspread_client()
        sheet = client.open_by_key(SHEET_ID)
    payload = [list(df.columns)] + df.fillna("").astype(str).values.tolist()
    try:
        ws = sheet.worksheet(RAW_TAB)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=RAW_TAB, rows=max(len(payload) + 10, 2000), cols=max(len(df.columns) + 5, 40))
    else:
        ws.clear()
    ws.update(range_name="A1", values=payload)


def write_summary(sheet: gspread.Spreadsheet, df: pd.DataFrame) -> None:
    prev_counts = load_prev_focus_counts(sheet)
    summary_rows = summarize_focus(df, prev_counts)
    header = summary_rows[0]
    try:
        ws_summary = sheet.worksheet(SUMMARY_TAB)
        existing = ws_summary.get_all_values()
    except gspread.WorksheetNotFound:
        ws_summary = sheet.add_worksheet(title=SUMMARY_TAB, rows=max(len(summary_rows) + 10, 200), cols=max(len(header) + 5, 20))
        existing = []
    other_rows = [r for r in (existing[1:] if existing else []) if r and r[0] != "A003"]
    merged = [header] + other_rows + summary_rows[1:]
    ws_summary.clear()
    ws_summary.update(range_name="A1", values=merged)


def append_run_status(sheet: gspread.Spreadsheet, row: list[str]) -> None:
    headers = [
        "script",
        "mode",
        "marketplace_id",
        "status",
        "alert",
        "run_id",
        "started_at",
        "ended_at",
        "duration_seconds",
        "attempts",
        "records_count",
        "col_count",
        "snapshot_path",
        "sheet_tabs",
        "poll_interval",
        "max_attempts",
        "consecutive_failures",
        "consecutive_successes",
        "env",
        "version",
        "last_error",
    ]
    try:
        ws = sheet.worksheet(RUN_STATUS_TAB)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=RUN_STATUS_TAB, rows=100, cols=len(headers))
        ws.update(range_name="A1", values=[headers])
    else:
        if ws.row_values(1) != headers:
            ws.clear()
            ws.update(range_name="A1", values=[headers])

    existing = ws.get_all_values()
    index = {}
    for idx, r in enumerate(existing[1:], start=2):
        if len(r) < 3:
            continue
        index[(r[0], r[1], r[2])] = idx

    key = (row[0], row[1], row[2])
    if key in index:
        ws.update(range_name=f"A{index[key]}:U{index[key]}", values=[row])
    else:
        ws.append_row(row, value_input_option="RAW")


def main() -> int:
    load_dotenv_if_missing()
    if not MARKETPLACE_ID:
        raise RuntimeError("MARKETPLACE_ID is required")

    started_at = datetime.now(timezone.utc)
    script_name = "A003_run_inventory_to_sheet.py"
    mode = "default"
    status = "success"
    alert = ""
    last_error = ""
    env_name = os.environ.get("ENV", "prod")
    git_version = os.environ.get("GIT_COMMIT", "")
    sheet_tabs_written: List[str] = []
    snapshot_path = ""
    attempts_used = 0
    row_count = 0
    col_count = 0
    missing_count = 0

    sheet = None
    if WRITE_SHEETS:
        client = get_gspread_client()
        sheet = client.open_by_key(SHEET_ID)

    try:
        active_skus = set()
        sku_filter = set()
        input_path = Path(INPUT_CSV)
        if input_path.exists():
            sku_filter = load_active_skus(input_path)
        if not INCLUDE_INACTIVE:
            active_skus = sku_filter.copy()
        if USE_API_OWNER:
            prev_dataset_env = os.environ.get("API_COLLECTION_DATASETS")
            os.environ["API_COLLECTION_DATASETS"] = "inventory_inbound"
            try:
                rc = int(run_api_collection_entry())
            finally:
                if prev_dataset_env is None:
                    os.environ.pop("API_COLLECTION_DATASETS", None)
                else:
                    os.environ["API_COLLECTION_DATASETS"] = prev_dataset_env
            attempts_used = 1
            if rc != 0:
                raise RuntimeError(f"API owner inventory collection failed rc={rc}")
            out_path = Path("out/inventory_summaries.csv")
            if not out_path.exists():
                raise RuntimeError("API owner inventory collection did not produce out/inventory_summaries.csv")
            df = pd.read_csv(out_path)
            if not INCLUDE_INACTIVE and active_skus and not df.empty and "seller_sku" in df.columns:
                df = df[df["seller_sku"].astype(str).isin(active_skus)].copy()
            if sku_filter and "seller_sku" in df.columns:
                seen_skus = set(df["seller_sku"].astype(str).tolist())
                missing_count = len([s for s in sku_filter if s not in seen_skus])
        else:
            token = get_lwa_access_token()
            records: List[Dict[str, object]] = []
            next_token = None
            page = 0
            while True:
                page += 1
                attempts_used = page
                batch, next_token = fetch_inventory_summaries(
                    marketplace_id=MARKETPLACE_ID,
                    access_token=token,
                    next_token=next_token,
                )
                records.extend(batch)
                if next_token and (LIMIT_PAGES == 0 or page < LIMIT_PAGES):
                    time.sleep(SLEEP_SEC)
                    continue
                break
            if sku_filter:
                seen_skus = {(r or {}).get("sellerSku", "") for r in records}
                missing_skus = [s for s in sku_filter if s not in seen_skus]
                if missing_skus:
                    batch_size = 40
                    for i in range(0, len(missing_skus), batch_size):
                        chunk = missing_skus[i : i + batch_size]
                        page += 1
                        attempts_used = page
                        chunk_batch, _ = fetch_inventory_summaries(
                            marketplace_id=MARKETPLACE_ID,
                            access_token=token,
                            seller_skus=chunk,
                        )
                        records.extend(chunk_batch)
                        time.sleep(SLEEP_SEC)
                # Recompute missing after targeted fetches
                seen_skus = {(r or {}).get("sellerSku", "") for r in records}
                missing_skus = [s for s in sku_filter if s not in seen_skus]
                missing_count = len(missing_skus)

            filtered = records if INCLUDE_INACTIVE or not active_skus else [r for r in records if (r or {}).get("sellerSku", "") in active_skus]
            df = records_to_df(filtered)
        row_count = len(df)
        col_count = len(df.columns)

        out_path = Path("out/inventory_summaries.csv")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False)
        snapshot_path = str(out_path)
        print(f"Saved inventory data to {out_path}")
        if missing_count > 0:
            print(f"Warning: missing {missing_count} active SKUs from inventory API (kept in alert).")

        if WRITE_SHEETS and WRITE_RAW_TAB:
            write_raw(df)
            sheet_tabs_written.append(RAW_TAB)
        if WRITE_SHEETS and WRITE_SUMMARY_TAB:
            write_summary(sheet, df)
            sheet_tabs_written.append(SUMMARY_TAB)
        if sheet_tabs_written:
            print(f"Wrote {len(df)} rows to sheet tabs {', '.join(sheet_tabs_written)}")
        if WRITE_PRODUCT_DB:
            update_ts = datetime.now(timezone.utc).isoformat()
            update_local_product_db_stock(Path("out/product_db_preview.csv"), df, update_ts)
        if WRITE_SHEETS and WRITE_PRODUCT_DB:
            update_product_db_stock(sheet, df, update_ts)
            export_product_db(sheet)
        if WRITE_SHEETS and WRITE_TOKEN_RECON:
            write_token_stock_recon(df)
    except Exception as exc:
        status = "error"
        alert = "error"
        last_error = str(exc)
        df = pd.DataFrame()
        print(
            f"[A003] inventory collection failed: {type(exc).__name__}: {exc}. "
            "Exiting nonzero."
        )

    ended_at = datetime.now(timezone.utc)
    duration_seconds = str(int((ended_at - started_at).total_seconds()))

    consecutive_failures = 0
    consecutive_successes = 0
    existing = []
    ws_status = None
    if WRITE_SHEETS and sheet is not None:
        try:
            ws_status = sheet.worksheet(RUN_STATUS_TAB)
            existing = ws_status.get_all_values()
        except gspread.WorksheetNotFound:
            existing = []
            ws_status = None
    headers = [
        "script",
        "mode",
        "marketplace_id",
        "status",
        "alert",
        "run_id",
        "started_at",
        "ended_at",
        "duration_seconds",
        "attempts",
        "records_count",
        "col_count",
        "snapshot_path",
        "sheet_tabs",
        "poll_interval",
        "max_attempts",
        "consecutive_failures",
        "consecutive_successes",
        "env",
        "version",
        "last_error",
    ]
    if existing and existing[0] == headers:
        index = {(r[0], r[1], r[2]): r for r in existing[1:] if len(r) >= 3}
        key = (script_name, mode, MARKETPLACE_ID)
        prev = index.get(key, [])
        try:
            consecutive_failures = int(prev[16]) if len(prev) > 16 else 0
        except Exception:
            consecutive_failures = 0
        try:
            consecutive_successes = int(prev[17]) if len(prev) > 17 else 0
        except Exception:
            consecutive_successes = 0
    if status == "success":
        consecutive_successes += 1
        consecutive_failures = 0
    else:
        consecutive_failures += 1
        consecutive_successes = 0

    run_id = f"{script_name}-{started_at.isoformat()}"
    if status == "success" and missing_count > 0:
        alert = "missing_skus"
        if not last_error:
            last_error = f"missing_skus={missing_count}"

    status_row = [
        script_name,
        mode,
        MARKETPLACE_ID,
        status,
        alert,
        run_id,
        started_at.isoformat(),
        ended_at.isoformat(),
        duration_seconds,
        str(attempts_used),
        str(row_count),
        str(col_count),
        snapshot_path,
        ";".join(sheet_tabs_written),
        "",  # poll_interval not used
        "",  # max_attempts not used
        str(consecutive_failures),
        str(consecutive_successes),
        env_name,
        git_version,
        last_error,
    ]
    if WRITE_SHEETS:
        append_run_status(sheet, status_row)

    print(
        {
            "timestamp": ended_at.isoformat(),
            "status": status,
            "row_count": row_count,
            "columns": col_count,
            "snapshot": snapshot_path,
            "sheet_tabs": sheet_tabs_written,
            "alert": alert,
            "error": last_error,
        }
    )
    return 0 if status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())


