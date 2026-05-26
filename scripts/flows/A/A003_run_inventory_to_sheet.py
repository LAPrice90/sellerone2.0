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
import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Tuple

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
from scripts.core.out_paths import write_csv_with_compat
from scripts.core.storage import (
    coalesce_duplicate_header_rows,
    dataframe_from_product_db_sheet_rows,
    write_dataframe_with_sql_compat,
)

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
TOKEN_LEDGER_PATH = Path("out/token_ledger_live.csv")
PRODUCT_DB_PREVIEW = Path("out/product_db_preview.csv")
SQL_TABLE_PRODUCT_DB_PREVIEW = "sys_product_db_preview"
SQL_TABLE_INVENTORY_SUMMARIES = "a_inventory_summaries"
SQL_TABLE_INVENTORY_HISTORY = "a_inventory_history"
SQL_TABLE_INVENTORY_SNAPSHOT_LATEST = "a_inventory_snapshot_latest"
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

INVENTORY_CONTRACT_COLUMNS = [
    "timestamp_utc",
    "asof_date",
    "marketplace",
    "sku",
    "asin",
    "available",
    "inbound_working",
    "inbound_shipped",
    "inbound_receiving",
    "inbound_total",
    "unsellable",
    "researching",
    "reserved_transfers",
    "reserved_processing",
    "reserved_customer",
    "total_quantity",
    "last_updated_time",
    "source",
    "notes",
]


def _snapshot_timestamp_utc() -> str:
    override = os.environ.get("H_SNAPSHOT_DATE", "").strip()
    if override:
        return f"{override}T00:00:00Z"
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _snapshot_date_from_timestamp(timestamp_utc: str) -> str:
    return str(timestamp_utc).split("T", 1)[0]


def _to_int(value) -> int:
    try:
        return int(float(str(value).strip()))
    except Exception:
        return 0


def _to_bool(value: object, default: bool = False) -> bool:
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _parse_iso_utc(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _resolve_inventory_row_stale_hours() -> float:
    raw = os.environ.get("A003_STOCK_ROW_STALE_HOURS", os.environ.get("H_STOCK_ROW_STALE_HOURS", "24"))
    try:
        return max(float(str(raw).strip() or "24"), 0.0)
    except Exception:
        return 24.0


def _merge_stock_count_maps(base: Dict[str, int], incoming: Dict[str, int]) -> Dict[str, int]:
    merged: Dict[str, int] = dict(base)
    for sku, qty in incoming.items():
        key = str(sku or "").strip().upper()
        if not key:
            continue
        prev = int(merged.get(key, 0))
        merged[key] = max(prev, int(qty))
    return merged


def _build_token_stock_maps_from_df(token_df: pd.DataFrame) -> Tuple[Dict[str, int], Dict[str, int]]:
    if token_df is None or token_df.empty:
        return {}, {}
    sku_col = ""
    for candidate in ("seller_sku", "sku", "SellerSKU", "seller-sku"):
        if candidate in token_df.columns:
            sku_col = candidate
            break
    status_col = ""
    for candidate in ("status", "Status"):
        if candidate in token_df.columns:
            status_col = candidate
            break
    if not sku_col or not status_col:
        return {}, {}
    work = token_df[[sku_col, status_col]].copy()
    work["sku_key"] = work[sku_col].astype(str).str.strip().str.upper()
    work["status_key"] = work[status_col].astype(str).str.strip().str.lower()
    work = work.loc[work["sku_key"].ne("")].copy()
    if work.empty:
        return {}, {}
    token_available_by_sku: Dict[str, int] = {}
    token_total_effective_by_sku: Dict[str, int] = {}
    effective_statuses = {"available", "allocated", "unsellable", "research_pending", "returned_pending"}
    available_counts = work.loc[work["status_key"].eq("available")].groupby("sku_key", as_index=False).size()
    for _, row in available_counts.iterrows():
        token_available_by_sku[str(row["sku_key"])] = int(row["size"])
    effective_counts = work.loc[work["status_key"].isin(effective_statuses)].groupby("sku_key", as_index=False).size()
    for _, row in effective_counts.iterrows():
        token_total_effective_by_sku[str(row["sku_key"])] = int(row["size"])
    return token_available_by_sku, token_total_effective_by_sku


def _load_token_stock_maps(token_ledger_path: Path = TOKEN_LEDGER_PATH) -> Tuple[Dict[str, int], Dict[str, int]]:
    if not token_ledger_path.exists():
        return {}, {}
    try:
        max_attempts = max(int(float(os.environ.get("A003_TOKEN_LEDGER_READ_ATTEMPTS", "3") or "3")), 1)
    except Exception:
        max_attempts = 3
    try:
        retry_sleep = max(float(os.environ.get("A003_TOKEN_LEDGER_READ_RETRY_SEC", "0.25") or "0.25"), 0.0)
    except Exception:
        retry_sleep = 0.25

    merged_available: Dict[str, int] = {}
    merged_effective: Dict[str, int] = {}
    for attempt in range(max_attempts):
        stable_snapshot = True
        stat_before = None
        stat_after = None
        try:
            stat_before = token_ledger_path.stat()
        except Exception:
            stat_before = None
        try:
            token_df = pd.read_csv(token_ledger_path, dtype=str).fillna("")
        except Exception:
            token_df = pd.DataFrame()
        try:
            stat_after = token_ledger_path.stat()
        except Exception:
            stat_after = None
        if stat_before is None or stat_after is None:
            stable_snapshot = False
        else:
            before_ns = int(getattr(stat_before, "st_mtime_ns", int(stat_before.st_mtime * 1_000_000_000)))
            after_ns = int(getattr(stat_after, "st_mtime_ns", int(stat_after.st_mtime * 1_000_000_000)))
            stable_snapshot = (before_ns == after_ns) and (int(stat_before.st_size) == int(stat_after.st_size))

        attempt_available, attempt_effective = _build_token_stock_maps_from_df(token_df)
        merged_available = _merge_stock_count_maps(merged_available, attempt_available)
        merged_effective = _merge_stock_count_maps(merged_effective, attempt_effective)
        if stable_snapshot:
            break
        if attempt < (max_attempts - 1) and retry_sleep > 0:
            time.sleep(retry_sleep)
    return merged_available, merged_effective


def _apply_inventory_stale_token_floor(
    df: pd.DataFrame,
    *,
    scope_skus: Set[str] | None = None,
    now_utc: datetime | None = None,
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame(), {
            "row_stale_hours": _resolve_inventory_row_stale_hours(),
            "stale_rows": 0,
            "stale_scope_rows": 0,
            "token_floor_rows": 0,
            "stale_scope_token_gap_rows": 0,
            "stale_scope_sample": [],
            "token_floor_sample": [],
        }

    work = df.copy()
    for col in ("seller_sku", "last_updated_time", "available", "total_quantity", "in_stock_supply_quantity"):
        if col not in work.columns:
            work[col] = ""

    probe_now = now_utc or datetime.now(timezone.utc)
    stale_hours = _resolve_inventory_row_stale_hours()
    token_floor_enabled = _to_bool(os.environ.get("A003_STALE_TOKEN_FLOOR_ENABLED", "1"), default=True)
    scope = {str(v).strip().upper() for v in (scope_skus or set()) if str(v).strip()}

    token_available_by_sku: Dict[str, int] = {}
    token_total_effective_by_sku: Dict[str, int] = {}
    if token_floor_enabled:
        token_available_by_sku, token_total_effective_by_sku = _load_token_stock_maps()

    stale_rows = 0
    stale_scope_rows = 0
    token_floor_rows = 0
    stale_scope_token_gap_rows = 0
    stale_scope_sample: List[str] = []
    token_floor_sample: List[str] = []
    age_hours_col: List[str] = []
    status_col: List[str] = []
    stale_flag_col: List[str] = []
    adjustment_col: List[str] = []
    source_col: List[str] = []
    token_available_col: List[str] = []
    token_total_effective_col: List[str] = []

    for idx, row in work.iterrows():
        sku = str(row.get("seller_sku", "")).strip().upper()
        in_scope = (not scope) or (sku in scope)
        updated_dt = _parse_iso_utc(row.get("last_updated_time", ""))
        status_text = "UNKNOWN"
        age_hours_text = ""
        is_stale = True
        if updated_dt is not None:
            age_hours = max((probe_now - updated_dt).total_seconds() / 3600.0, 0.0)
            age_hours_text = f"{age_hours:.2f}"
            status_text = "STALE" if age_hours >= stale_hours else "FRESH"
            is_stale = status_text == "STALE"
        if is_stale:
            stale_rows += 1
        if is_stale and in_scope:
            stale_scope_rows += 1
            if len(stale_scope_sample) < 5 and sku:
                stale_scope_sample.append(sku)

        token_available = int(token_available_by_sku.get(sku, 0)) if token_floor_enabled else 0
        token_total_effective = int(token_total_effective_by_sku.get(sku, 0)) if token_floor_enabled else 0
        adjustment = ""
        source = "SPAPI"

        if is_stale and in_scope:
            source = "SPAPI_STALE"
            if token_floor_enabled:
                api_available = _to_int(row.get("available", 0))
                api_total = _to_int(row.get("total_quantity", 0))
                floor_available = max(api_available, token_available)
                floor_total = max(api_total, token_total_effective, floor_available)
                if floor_available > api_available or floor_total > api_total:
                    work.at[idx, "available"] = int(floor_available)
                    work.at[idx, "in_stock_supply_quantity"] = int(floor_available)
                    work.at[idx, "total_quantity"] = int(floor_total)
                    adjustment = "TOKEN_FLOOR"
                    source = "SPAPI_TOKEN_FLOOR"
                    token_floor_rows += 1
                    if len(token_floor_sample) < 5 and sku:
                        token_floor_sample.append(sku)
                final_available = _to_int(work.at[idx, "available"])
                if token_available > final_available:
                    stale_scope_token_gap_rows += 1

        age_hours_col.append(age_hours_text)
        status_col.append(status_text)
        stale_flag_col.append("1" if is_stale else "0")
        adjustment_col.append(adjustment)
        source_col.append(source)
        token_available_col.append(str(token_available))
        token_total_effective_col.append(str(token_total_effective))

    work["row_last_updated_age_hours"] = age_hours_col
    work["row_last_updated_status"] = status_col
    work["row_last_updated_is_stale"] = stale_flag_col
    work["row_stock_truth_adjustment"] = adjustment_col
    work["row_stock_truth_source"] = source_col
    work["row_token_available_units"] = token_available_col
    work["row_token_total_effective_units"] = token_total_effective_col

    summary = {
        "row_stale_hours": stale_hours,
        "stale_rows": stale_rows,
        "stale_scope_rows": stale_scope_rows,
        "token_floor_rows": token_floor_rows,
        "stale_scope_token_gap_rows": stale_scope_token_gap_rows,
        "stale_scope_sample": stale_scope_sample,
        "token_floor_sample": token_floor_sample,
        "scope_count": len(scope),
        "token_floor_enabled": "1" if token_floor_enabled else "0",
    }
    return work, summary


def _to_inventory_contract(df: pd.DataFrame, snapshot_timestamp_utc: str) -> pd.DataFrame:
    snapshot_date = _snapshot_date_from_timestamp(snapshot_timestamp_utc)
    if df is None or df.empty:
        return pd.DataFrame(columns=INVENTORY_CONTRACT_COLUMNS)

    inv = df.copy()
    if "seller_sku" not in inv.columns and "sku" in inv.columns:
        inv["seller_sku"] = inv["sku"]
    if "seller_sku" not in inv.columns:
        inv["seller_sku"] = ""
    if "asin" not in inv.columns:
        inv["asin"] = ""
    if "last_updated_time" not in inv.columns:
        inv["last_updated_time"] = ""
    for col in (
        "available",
        "inbound_working",
        "inbound_shipped",
        "inbound_receiving",
        "unsellable",
        "researching",
        "reserved_transfers",
        "reserved_processing",
        "reserved_customer",
        "total_quantity",
    ):
        if col not in inv.columns:
            inv[col] = 0

    contract = pd.DataFrame(index=inv.index.copy())
    contract["timestamp_utc"] = snapshot_timestamp_utc
    contract["asof_date"] = snapshot_date
    contract["marketplace"] = "UK"
    contract["sku"] = inv["seller_sku"].astype(str)
    contract["asin"] = inv["asin"].astype(str)
    contract["available"] = inv["available"].apply(_to_int)
    contract["inbound_working"] = inv["inbound_working"].apply(_to_int)
    contract["inbound_shipped"] = inv["inbound_shipped"].apply(_to_int)
    contract["inbound_receiving"] = inv["inbound_receiving"].apply(_to_int)
    contract["inbound_total"] = (
        contract["inbound_working"] + contract["inbound_shipped"] + contract["inbound_receiving"]
    )
    contract["unsellable"] = inv["unsellable"].apply(_to_int)
    contract["researching"] = inv["researching"].apply(_to_int)
    contract["reserved_transfers"] = inv["reserved_transfers"].apply(_to_int)
    contract["reserved_processing"] = inv["reserved_processing"].apply(_to_int)
    contract["reserved_customer"] = inv["reserved_customer"].apply(_to_int)
    contract["total_quantity"] = inv["total_quantity"].apply(_to_int)
    contract["last_updated_time"] = inv["last_updated_time"].astype(str)
    if "row_stock_truth_source" in inv.columns:
        source_series = inv["row_stock_truth_source"].astype(str).str.strip().replace("", "SPAPI")
        contract["source"] = source_series
    else:
        contract["source"] = "SPAPI"
    if "row_stock_truth_adjustment" in inv.columns:
        contract["notes"] = inv["row_stock_truth_adjustment"].astype(str).str.strip()
    else:
        contract["notes"] = ""
    return contract[INVENTORY_CONTRACT_COLUMNS]


def _rewrite_inventory_history_today(contract: pd.DataFrame, snapshot_date: str) -> pd.DataFrame:
    history_path = Path("out/inventory_history.csv")
    if history_path.exists():
        try:
            history = pd.read_csv(history_path, dtype=str).fillna("")
        except Exception:
            history = pd.DataFrame(columns=INVENTORY_CONTRACT_COLUMNS)
    else:
        history = pd.DataFrame(columns=INVENTORY_CONTRACT_COLUMNS)

    for col in INVENTORY_CONTRACT_COLUMNS:
        if col not in history.columns:
            history[col] = ""
    history = history[INVENTORY_CONTRACT_COLUMNS]

    def persist_history(history_df: pd.DataFrame) -> None:
        write_csv_with_compat(
            history_df,
            path_or_rel="inventory_history.csv",
            default_system="shared",
            index=False,
            mirror_legacy=True,
        )
        write_dataframe_with_sql_compat(
            history_df,
            Path("out/inventory_history.csv"),
            SQL_TABLE_INVENTORY_HISTORY,
        )

    if contract is None or contract.empty:
        persist_history(history)
        return history

    snapshot = contract.copy()
    for col in INVENTORY_CONTRACT_COLUMNS:
        if col not in snapshot.columns:
            snapshot[col] = ""
    snapshot = snapshot[INVENTORY_CONTRACT_COLUMNS]
    snapshot["asof_date"] = snapshot["asof_date"].astype(str).str.strip()

    key_cols = ["asof_date", "sku", "marketplace"]
    snapshot_today = snapshot.loc[snapshot["asof_date"].eq(snapshot_date)].copy()
    snapshot_today["_stable_order"] = list(range(len(snapshot_today.index)))
    if "timestamp_utc" in snapshot_today.columns:
        snapshot_today["_order_ts"] = pd.to_datetime(snapshot_today["timestamp_utc"], errors="coerce", utc=True)
    else:
        snapshot_today["_order_ts"] = pd.NaT
    snapshot_today = snapshot_today.sort_values(
        key_cols + ["_order_ts", "_stable_order"],
        ascending=[True, True, True, False, True],
        kind="stable",
    )
    snapshot_today = snapshot_today.drop_duplicates(subset=key_cols, keep="first").copy()
    snapshot_today = snapshot_today.drop(columns=["_stable_order", "_order_ts"], errors="ignore")

    history["asof_date"] = history["asof_date"].astype(str).str.strip()
    for col in ("sku", "marketplace"):
        history[col] = history[col].astype(str).str.strip()
        snapshot_today[col] = snapshot_today[col].astype(str).str.strip()

    marketplaces_today = {
        str(v).strip().upper()
        for v in snapshot_today.get("marketplace", pd.Series([], dtype=str)).astype(str).tolist()
        if str(v).strip()
    }
    history_marketplace_upper = history["marketplace"].astype(str).str.upper()
    history_keep_mask = ~history["asof_date"].eq(snapshot_date)
    if marketplaces_today:
        history_keep_mask = history_keep_mask | ~history_marketplace_upper.isin(marketplaces_today)
    history_keep = history.loc[history_keep_mask].copy()

    merged = pd.concat([history_keep, snapshot_today], ignore_index=True)
    merged = merged[INVENTORY_CONTRACT_COLUMNS]
    persist_history(merged)
    return merged


def _persist_inventory_contract_outputs(df: pd.DataFrame) -> tuple[str, str, int]:
    out_dir = Path("out")
    out_dir.mkdir(parents=True, exist_ok=True)
    snapshot_timestamp_utc = _snapshot_timestamp_utc()
    snapshot_date = _snapshot_date_from_timestamp(snapshot_timestamp_utc)
    contract = _to_inventory_contract(df, snapshot_timestamp_utc)

    snapshot_dated_path = out_dir / f"inventory_snapshot_{snapshot_date}.csv"
    snapshot_latest_path = out_dir / "inventory_snapshot_latest.csv"
    contract.to_csv(snapshot_dated_path, index=False)
    write_dataframe_with_sql_compat(contract, snapshot_latest_path, SQL_TABLE_INVENTORY_SNAPSHOT_LATEST)
    history = _rewrite_inventory_history_today(contract, snapshot_date)
    print(
        f"Persisted inventory contract outputs rows={len(contract)} "
        f"snapshot={snapshot_dated_path} latest={snapshot_latest_path} history_rows={len(history)}"
    )
    return str(snapshot_dated_path), str(snapshot_latest_path), int(len(history))


def _mtime_seconds(path: Path) -> float | None:
    try:
        if not path.exists():
            return None
        return float(path.stat().st_mtime)
    except Exception:
        return None


def _collect_inventory_direct(active_skus: Set[str], sku_filter: Set[str]) -> tuple[pd.DataFrame, int, int]:
    token = get_lwa_access_token()
    records: List[Dict[str, object]] = []
    next_token = None
    page = 0
    while True:
        page += 1
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

    missing_count = 0
    if sku_filter:
        seen_skus = {(r or {}).get("sellerSku", "") for r in records}
        missing_skus = [s for s in sku_filter if s not in seen_skus]
        if missing_skus:
            batch_size = 40
            for i in range(0, len(missing_skus), batch_size):
                chunk = missing_skus[i : i + batch_size]
                page += 1
                chunk_batch, _ = fetch_inventory_summaries(
                    marketplace_id=MARKETPLACE_ID,
                    access_token=token,
                    seller_skus=chunk,
                )
                records.extend(chunk_batch)
                time.sleep(SLEEP_SEC)
        seen_skus = {(r or {}).get("sellerSku", "") for r in records}
        missing_skus = [s for s in sku_filter if s not in seen_skus]
        missing_count = len(missing_skus)

    filtered = records if INCLUDE_INACTIVE or not active_skus else [r for r in records if (r or {}).get("sellerSku", "") in active_skus]
    df = records_to_df(filtered)
    return df, int(missing_count), int(page)


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
    df, repaired_headers = dataframe_from_product_db_sheet_rows(rows)
    Path("out").mkdir(parents=True, exist_ok=True)
    write_dataframe_with_sql_compat(
        df,
        PRODUCT_DB_PREVIEW,
        SQL_TABLE_PRODUCT_DB_PREVIEW,
    )
    if repaired_headers:
        print("Repaired duplicate Product_DB headers for export: " + ",".join(repaired_headers))
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
    prod_rows, repaired_headers = coalesce_duplicate_header_rows(prod_rows)
    if repaired_headers:
        print("Repaired duplicate Product_DB headers before A003 update: " + ",".join(repaired_headers))
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
        with product_db_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        repaired_rows, repaired_headers = coalesce_duplicate_header_rows(rows)
        prod = pd.DataFrame(repaired_rows[1:], columns=repaired_rows[0]) if repaired_rows else pd.DataFrame()
        if repaired_headers:
            print("Repaired duplicate Product DB headers before local A003 refresh: " + ",".join(repaired_headers))
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
            owner_paths = [
                Path("out/inventory_summaries.csv"),
                Path("out/inventory_snapshot_latest.csv"),
                Path("out/inventory_history.csv"),
            ]
            owner_before = {str(p): _mtime_seconds(p) for p in owner_paths}
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
            owner_after = {str(p): _mtime_seconds(p) for p in owner_paths}
            owner_refreshed = False
            for key, after_val in owner_after.items():
                before_val = owner_before.get(key)
                if after_val is None:
                    continue
                if before_val is None or after_val > (before_val + 1e-6):
                    owner_refreshed = True
                    break
            if not owner_refreshed:
                print(
                    "[A003] WARN API owner reported success but inventory artifacts were not refreshed; "
                    "falling back to direct collector."
                )
                df, missing_count, direct_pages = _collect_inventory_direct(active_skus, sku_filter)
                attempts_used = max(int(attempts_used), int(direct_pages))
        else:
            df, missing_count, direct_pages = _collect_inventory_direct(active_skus, sku_filter)
            attempts_used = int(direct_pages)
        df, stale_guard_summary = _apply_inventory_stale_token_floor(
            df,
            scope_skus=sku_filter,
            now_utc=datetime.now(timezone.utc),
        )
        print(
            "[A003] stale_stock_guard "
            f"row_stale_hours={stale_guard_summary.get('row_stale_hours', '')} "
            f"scope_count={stale_guard_summary.get('scope_count', 0)} "
            f"stale_rows={stale_guard_summary.get('stale_rows', 0)} "
            f"stale_scope_rows={stale_guard_summary.get('stale_scope_rows', 0)} "
            f"token_floor_rows={stale_guard_summary.get('token_floor_rows', 0)} "
            f"stale_scope_token_gap_rows={stale_guard_summary.get('stale_scope_token_gap_rows', 0)} "
            f"token_floor_enabled={stale_guard_summary.get('token_floor_enabled', '0')} "
            f"stale_scope_sample={','.join([str(v) for v in stale_guard_summary.get('stale_scope_sample', [])])} "
            f"token_floor_sample={','.join([str(v) for v in stale_guard_summary.get('token_floor_sample', [])])}"
        )

        row_count = len(df)
        col_count = len(df.columns)

        out_path = Path("out/inventory_summaries.csv")
        write_dataframe_with_sql_compat(df, out_path, SQL_TABLE_INVENTORY_SUMMARIES)
        snapshot_path = str(out_path)
        print(f"Saved inventory data to {out_path}")
        _persist_inventory_contract_outputs(df)
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


