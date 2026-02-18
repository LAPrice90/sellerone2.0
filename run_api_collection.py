from __future__ import annotations

import csv
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import pandas as pd

from scripts.api.get_financial_events import MissingEnvError
from scripts.api.get_inventory_summaries import (
    fetch_inventory_summaries,
    get_lwa_access_token,
    load_dotenv_if_missing,
)
from scripts.api.get_listing_item_price import run_own_offer_price_lookup
from scripts.api.get_pricing import run_market_context_lookup_with_offers
from scripts.api.spapi_owner import SpApiCallContext, acquire_spapi_lock, release_spapi_lock, spapi_get
from scripts.f_training_set import load_training_set
from scripts.H002_build_phase1_seller_history import build_phase1_seller_history

OUT = Path("out")
API_RUN_LOG = OUT / "api_run_log.csv"
LISTING_OFFER_HISTORY_PATH = OUT / "listing_offer_history.csv"
LISTING_OFFER_SELLER_HISTORY_PATH = OUT / "listing_offer_seller_observation_history.csv"
INVENTORY_HISTORY_PATH = OUT / "inventory_history.csv"
INBOUND_HISTORY_PATH = OUT / "inbound_history.csv"
REFUND_ADJUSTMENT_HISTORY_PATH = OUT / "refund_adjustment_history.csv"

LISTING_REQUIRED_COLUMNS: List[str] = [
    "timestamp_utc",
    "asof_date",
    "marketplace",
    "sku",
    "asin",
    "our_price",
    "buy_box_price",
    "buy_box_channel",
    "lowest_fba_price",
    "lowest_fbm_price",
    "offer_count_fba",
    "offer_count_fbm",
    "list_price",
    "list_price_currency",
    "apparent_sale_amount_gbp",
    "apparent_sale_pct",
    "bsr",
    "bsr_category",
    "source",
    "notes",
]

LISTING_SELLER_REQUIRED_COLUMNS: List[str] = [
    "timestamp_utc",
    "asof_date",
    "marketplace",
    "sku",
    "asin",
    "seller_id",
    "seller_seen_flag",
    "offer_price_gbp",
    "offer_shipping_price_gbp",
    "offer_landed_price_gbp",
    "is_prime",
    "fulfilment_channel",
    "min_delivery_days",
    "max_delivery_days",
    "delivery_range_days",
    "source",
    "notes",
]

INVENTORY_REQUIRED_COLUMNS: List[str] = [
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

INBOUND_REQUIRED_COLUMNS: List[str] = [
    "timestamp_utc",
    "asof_date",
    "marketplace",
    "sku",
    "asin",
    "inbound_working",
    "inbound_shipped",
    "inbound_receiving",
    "inbound_total",
    "source",
    "notes",
]

REFUND_ADJUSTMENT_REQUIRED_COLUMNS: List[str] = [
    "timestamp_utc",
    "asof_date",
    "marketplace",
    "sku",
    "asin",
    "refund_event_count",
    "adjustment_event_count",
    "refund_units",
    "adjustment_units",
    "refund_amount_gbp",
    "adjustment_amount_gbp",
    "source",
    "notes",
]

UK_MARKETPLACE_ID = "A1F83G8C2ARO7P"
SPAPI_BASE_URL = os.environ.get("SPAPI_BASE_URL", "https://sellingpartnerapi-eu.amazon.com")
MARKETPLACE_ID_MAP = {
    "UK": UK_MARKETPLACE_ID,
    "GB": UK_MARKETPLACE_ID,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _snapshot_timestamp() -> str:
    override = os.environ.get("H_SNAPSHOT_DATE", "").strip()
    if override:
        return f"{override}T00:00:00Z"
    # Use real capture time for live-pricing freshness checks.
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _snapshot_date() -> str:
    return _snapshot_timestamp().split("T", 1)[0]


def _ensure_columns(df: pd.DataFrame, required_columns: Sequence[str]) -> pd.DataFrame:
    for col in required_columns:
        if col not in df.columns:
            df[col] = ""
    return df[list(required_columns)]


def _to_int(value: object) -> int:
    try:
        return int(float(str(value).strip()))
    except Exception:
        return 0


def _resolve_marketplace_id(marketplace: str) -> str:
    market = str(marketplace or "").strip().upper()
    if market in MARKETPLACE_ID_MAP:
        return MARKETPLACE_ID_MAP[market]
    env_mp = os.environ.get("MARKETPLACE_ID", "").strip()
    return env_mp or UK_MARKETPLACE_ID


def _append_note(existing: str, note: str) -> str:
    base = str(existing or "").strip()
    add = str(note or "").strip()
    if not add:
        return base
    if not base:
        return add
    parts = [p.strip() for p in base.split(" | ") if p.strip()]
    if add in parts:
        return base
    return base + " | " + add


def _upsert_history(
    *,
    snapshot: pd.DataFrame,
    history_path: Path,
    required_columns: Sequence[str],
    key_columns: Sequence[str],
) -> pd.DataFrame:
    if history_path.exists():
        try:
            history = pd.read_csv(history_path, dtype=str).fillna("")
        except Exception as exc:
            print(f"[API_COLLECTION] WARN failed to read {history_path}; rebuilding: {exc}")
            history = pd.DataFrame(columns=list(required_columns))
    else:
        history = pd.DataFrame(columns=list(required_columns))

    history = _ensure_columns(history, required_columns)
    snapshot = _ensure_columns(snapshot, required_columns)
    combined = pd.concat([history, snapshot], ignore_index=True)
    for col in key_columns:
        combined = combined[combined[col].astype(str).str.strip() != ""].copy()

    key = pd.Series("", index=combined.index, dtype=str)
    for col in key_columns:
        key = key + "||" + combined[col].astype(str)
    combined = combined.assign(_key=key).drop_duplicates(subset=["_key"], keep="last").drop(columns=["_key"])
    combined = _ensure_columns(combined, required_columns)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(history_path, index=False)
    return combined


def _append_api_run_log(
    *,
    run_id: str,
    started_utc: str,
    finished_utc: str,
    status: str,
    calls_products_pricing_get_price: int,
    calls_listings_items_get_item: int,
    calls_finances_get_financial_events: int,
    notes: str,
) -> None:
    clean_notes = str(notes).replace("\r", " ").replace("\n", " ").strip()
    fieldnames = [
        "run_id",
        "started_utc",
        "finished_utc",
        "status",
        "calls_products_pricing_get_price",
        "calls_listings_items_get_item",
        "calls_finances_get_financial_events",
        "notes",
    ]
    if API_RUN_LOG.exists():
        try:
            prior = pd.read_csv(API_RUN_LOG, dtype=str).fillna("")
        except Exception:
            prior = pd.DataFrame(columns=fieldnames)
        prior = _ensure_columns(prior, fieldnames)
        prior.to_csv(API_RUN_LOG, index=False)

    API_RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    write_header = not API_RUN_LOG.exists()
    with API_RUN_LOG.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=fieldnames,
        )
        if write_header:
            writer.writeheader()
        writer.writerow(
            {
                "run_id": run_id,
                "started_utc": started_utc,
                "finished_utc": finished_utc,
                "status": status,
                "calls_products_pricing_get_price": calls_products_pricing_get_price,
                "calls_listings_items_get_item": calls_listings_items_get_item,
                "calls_finances_get_financial_events": calls_finances_get_financial_events,
                "notes": clean_notes,
            }
        )


def _build_base_from_training_set(timestamp_utc: str, snapshot_date: str) -> pd.DataFrame:
    training = load_training_set()
    if training.empty:
        print("[API_COLLECTION] WARN training set is empty or missing; listing snapshot will be empty.")
        return pd.DataFrame(columns=LISTING_REQUIRED_COLUMNS)

    enabled = training.get("enabled", "").astype(str).str.strip().str.lower()
    is_enabled = enabled.isin(["yes", "y", "1", "true"])
    enabled_df = training.loc[is_enabled, ["sku", "asin", "marketplace", "notes"]].copy()
    enabled_df = enabled_df.fillna("")
    if enabled_df.empty:
        print("[API_COLLECTION] WARN no enabled SKUs in training set; listing snapshot will be empty.")
        return pd.DataFrame(columns=LISTING_REQUIRED_COLUMNS)

    base = enabled_df.copy()
    base["timestamp_utc"] = timestamp_utc
    base["asof_date"] = snapshot_date
    base["source"] = "SPAPI"
    base = _ensure_columns(base, LISTING_REQUIRED_COLUMNS)
    return base


def _collect_listing_offer_snapshot(run_id: str, script_name: str) -> Dict[str, int]:
    timestamp_utc = _snapshot_timestamp()
    snapshot_date = timestamp_utc.split("T", 1)[0]

    base = _build_base_from_training_set(timestamp_utc, snapshot_date)
    rows = base.copy()
    rows["notes"] = rows["notes"].astype(str)
    seller_observation_rows: List[Dict[str, str]] = []

    total_pricing_calls = 0
    total_listing_calls = 0

    for marketplace, grp in rows.groupby("marketplace", dropna=False):
        mp_id = _resolve_marketplace_id(str(marketplace))
        skus = grp["sku"].astype(str).str.strip().tolist()
        if not skus:
            continue
        try:
            our_map = run_own_offer_price_lookup(
                skus,
                mp_id,
                run_id=run_id,
                script_name=script_name,
            )
            sku_asin_rows = [
                (str(rows.at[idx, "sku"]).strip(), str(rows.at[idx, "asin"]).strip())
                for idx in grp.index
            ]
            bb_map, offer_rows = run_market_context_lookup_with_offers(
                sku_asin_rows,
                mp_id,
                snapshot_timestamp_utc=timestamp_utc,
                snapshot_asof_date=snapshot_date,
                run_id=run_id,
                script_name=script_name,
            )
            seller_observation_rows.extend(offer_rows)
            uniq_count = len([s for s in dict.fromkeys(skus) if s])
            uniq_asin_count = len(
                [a for a in dict.fromkeys([asin for _, asin in sku_asin_rows]) if str(a).strip()]
            )
            total_listing_calls += uniq_count
            total_pricing_calls += uniq_asin_count
        except (MissingEnvError, RuntimeError, Exception) as exc:
            msg = f"SPAPI_FAIL: {exc}"
            print(f"[API_COLLECTION] WARN {msg}")
            rows.loc[grp.index, "notes"] = rows.loc[grp.index, "notes"].where(rows.loc[grp.index, "notes"] != "", msg)
            continue

        for idx in grp.index:
            sku = str(rows.at[idx, "sku"]).strip()
            if sku in our_map:
                rows.at[idx, "our_price"] = our_map[sku].get("price", "")
            if sku not in bb_map:
                rows.at[idx, "notes"] = _append_note(rows.at[idx, "notes"], "pricing_context_missing")
                continue

            bb = bb_map[sku]
            rows.at[idx, "buy_box_price"] = bb.get("price", "")
            buy_box_channel = str(bb.get("buy_box_channel", "") or "").strip()
            rows.at[idx, "buy_box_channel"] = buy_box_channel if buy_box_channel else "Unknown"
            rows.at[idx, "lowest_fba_price"] = bb.get("lowest_fba_price", "")
            rows.at[idx, "lowest_fbm_price"] = bb.get("lowest_fbm_price", "")
            rows.at[idx, "offer_count_fba"] = bb.get("offer_count_fba", "")
            rows.at[idx, "offer_count_fbm"] = bb.get("offer_count_fbm", "")
            rows.at[idx, "list_price"] = bb.get("list_price", "")
            rows.at[idx, "list_price_currency"] = bb.get("list_price_currency", "")
            rows.at[idx, "apparent_sale_amount_gbp"] = bb.get("apparent_sale_amount_gbp", "")
            rows.at[idx, "apparent_sale_pct"] = bb.get("apparent_sale_pct", "")
            if not str(rows.at[idx, "buy_box_price"]).strip():
                rows.at[idx, "notes"] = _append_note(rows.at[idx, "notes"], "buy_box_price_missing")
            if not str(rows.at[idx, "buy_box_channel"]).strip():
                rows.at[idx, "notes"] = _append_note(rows.at[idx, "notes"], "buy_box_channel_missing")

    rows = _ensure_columns(rows, LISTING_REQUIRED_COLUMNS)
    snapshot_path = OUT / f"listing_offer_snapshot_{snapshot_date}.csv"
    rows.to_csv(snapshot_path, index=False)
    history = _upsert_history(
        snapshot=rows,
        history_path=LISTING_OFFER_HISTORY_PATH,
        required_columns=LISTING_REQUIRED_COLUMNS,
        key_columns=["asof_date", "sku", "marketplace"],
    )

    print(f"[API_COLLECTION] listing snapshot rows: {len(rows)} -> {snapshot_path}")
    print(f"[API_COLLECTION] listing history rows: {len(history)} -> {LISTING_OFFER_HISTORY_PATH}")

    seller_snapshot = pd.DataFrame(seller_observation_rows, dtype=str).fillna("")
    seller_snapshot = _ensure_columns(seller_snapshot, LISTING_SELLER_REQUIRED_COLUMNS)
    seller_snapshot_path = OUT / f"listing_offer_seller_snapshot_{snapshot_date}.csv"
    seller_snapshot.to_csv(seller_snapshot_path, index=False)
    seller_history = _upsert_history(
        snapshot=seller_snapshot,
        history_path=LISTING_OFFER_SELLER_HISTORY_PATH,
        required_columns=LISTING_SELLER_REQUIRED_COLUMNS,
        key_columns=["asof_date", "marketplace", "sku", "asin", "seller_id"],
    )
    print(f"[API_COLLECTION] listing seller snapshot rows: {len(seller_snapshot)} -> {seller_snapshot_path}")
    print(f"[API_COLLECTION] listing seller history rows: {len(seller_history)} -> {LISTING_OFFER_SELLER_HISTORY_PATH}")

    phase1_rows = build_phase1_seller_history()
    print(f"[API_COLLECTION] phase1 seller history rows: {phase1_rows}")
    return {
        "calls_products_pricing_get_price": int(total_pricing_calls),
        "calls_listings_items_get_item": int(total_listing_calls),
    }


def _load_active_skus(path: Path) -> List[str]:
    if not path.exists():
        return []
    df = pd.read_csv(path, dtype=str).fillna("")
    out: List[str] = []
    if "seller-sku" in df.columns:
        out.extend([str(v).strip() for v in df["seller-sku"].tolist() if str(v).strip()])
    if "seller_sku" in df.columns:
        out.extend([str(v).strip() for v in df["seller_sku"].tolist() if str(v).strip()])
    deduped = [s for s in dict.fromkeys(out) if s]
    return deduped


def _records_to_inventory_df(records: List[Dict[str, object]]) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    for rec in records:
        summary = rec or {}
        details = summary.get("inventoryDetails") or {}
        reserved = details.get("reservedQuantity") if isinstance(details.get("reservedQuantity"), dict) else {}
        unfulfillable = details.get("unfulfillableQuantity") if isinstance(details.get("unfulfillableQuantity"), dict) else {}

        researching = details.get("researchingQuantity", 0)
        if isinstance(researching, dict):
            researching = researching.get("totalResearchingQuantity", 0)
        if researching in (None, "", 0):
            fallback = unfulfillable.get("researchingQuantity", 0)
            if isinstance(fallback, dict):
                fallback = fallback.get("totalResearchingQuantity", 0)
            researching = fallback

        available = details.get("fulfillableQuantity")
        if available is None:
            available = details.get("availableQuantity", 0)

        inbound_working = details.get("inboundWorkingQuantity", 0)
        inbound_shipped = details.get("inboundShippedQuantity", 0)
        inbound_receiving = details.get("inboundReceivingQuantity", 0)

        rows.append(
            {
                "asin": summary.get("asin", ""),
                "seller_sku": summary.get("sellerSku", ""),
                "total_quantity": summary.get("totalQuantity", 0),
                "available": available if available is not None else 0,
                "unsellable": unfulfillable.get("totalUnfulfillableQuantity", 0),
                "researching": researching or 0,
                "inbound_working": inbound_working,
                "inbound_shipped": inbound_shipped,
                "inbound_receiving": inbound_receiving,
                "reserved_transfers": reserved.get("pendingTransshipmentQuantity", 0),
                "reserved_processing": reserved.get("fcProcessingQuantity", 0),
                "reserved_customer": reserved.get("pendingCustomerOrderQuantity", 0),
                "last_updated_time": summary.get("lastUpdatedTime", ""),
            }
        )
    return pd.DataFrame(rows)


def _inventory_contract_df(df: pd.DataFrame, snapshot_date: str, timestamp_utc: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=INVENTORY_REQUIRED_COLUMNS)
    out_df = pd.DataFrame(index=df.index.copy())
    out_df["timestamp_utc"] = timestamp_utc
    out_df["asof_date"] = snapshot_date
    out_df["marketplace"] = "UK"
    out_df["sku"] = df.get("seller_sku", "").astype(str)
    out_df["asin"] = df.get("asin", "").astype(str)
    out_df["available"] = df.get("available", 0).apply(_to_int)
    out_df["inbound_working"] = df.get("inbound_working", 0).apply(_to_int)
    out_df["inbound_shipped"] = df.get("inbound_shipped", 0).apply(_to_int)
    out_df["inbound_receiving"] = df.get("inbound_receiving", 0).apply(_to_int)
    out_df["inbound_total"] = out_df["inbound_working"] + out_df["inbound_shipped"] + out_df["inbound_receiving"]
    out_df["unsellable"] = df.get("unsellable", 0).apply(_to_int)
    out_df["researching"] = df.get("researching", 0).apply(_to_int)
    out_df["reserved_transfers"] = df.get("reserved_transfers", 0).apply(_to_int)
    out_df["reserved_processing"] = df.get("reserved_processing", 0).apply(_to_int)
    out_df["reserved_customer"] = df.get("reserved_customer", 0).apply(_to_int)
    out_df["total_quantity"] = df.get("total_quantity", 0).apply(_to_int)
    out_df["last_updated_time"] = df.get("last_updated_time", "").astype(str)
    out_df["source"] = "SPAPI"
    out_df["notes"] = ""
    return _ensure_columns(out_df, INVENTORY_REQUIRED_COLUMNS)


def _inbound_contract_df(inv_contract: pd.DataFrame) -> pd.DataFrame:
    if inv_contract.empty:
        return pd.DataFrame(columns=INBOUND_REQUIRED_COLUMNS)
    out_df = inv_contract[
        [
            "timestamp_utc",
            "asof_date",
            "marketplace",
            "sku",
            "asin",
            "inbound_working",
            "inbound_shipped",
            "inbound_receiving",
            "inbound_total",
            "source",
            "notes",
        ]
    ].copy()
    return _ensure_columns(out_df, INBOUND_REQUIRED_COLUMNS)


def _collect_inventory_and_inbound(run_id: str, script_name: str) -> Dict[str, int]:
    load_dotenv_if_missing()
    token = get_lwa_access_token()
    marketplace_id = os.environ.get("MARKETPLACE_ID", UK_MARKETPLACE_ID)
    include_inactive = os.environ.get("INVENTORY_INCLUDE_INACTIVE", "1").strip() == "1"
    limit_pages = int(os.environ.get("INVENTORY_LIMIT_PAGES", "0") or "0")

    active_skus = _load_active_skus(OUT / "merchant_listings_latest.csv")

    records: List[Dict[str, object]] = []
    next_token = None
    pages = 0

    while True:
        pages += 1
        batch, next_token = fetch_inventory_summaries(
            marketplace_id=marketplace_id,
            access_token=token,
            next_token=next_token,
            run_id=run_id,
            script_name=script_name,
        )
        records.extend(batch)
        if next_token and (limit_pages == 0 or pages < limit_pages):
            continue
        break

    if active_skus:
        seen = {str((r or {}).get("sellerSku", "")).strip() for r in records}
        missing = [s for s in active_skus if s and s not in seen]
        for i in range(0, len(missing), 40):
            chunk = missing[i : i + 40]
            if not chunk:
                continue
            pages += 1
            batch, _ = fetch_inventory_summaries(
                marketplace_id=marketplace_id,
                access_token=token,
                seller_skus=chunk,
                run_id=run_id,
                script_name=script_name,
            )
            records.extend(batch)

    inv_df = _records_to_inventory_df(records)
    if not include_inactive and active_skus and not inv_df.empty:
        inv_df = inv_df[inv_df["seller_sku"].astype(str).isin(set(active_skus))].copy()

    inv_df = inv_df.fillna("")
    inv_df.to_csv(OUT / "inventory_summaries.csv", index=False)

    timestamp_utc = _snapshot_timestamp()
    snapshot_date = _snapshot_date()

    inv_contract = _inventory_contract_df(inv_df, snapshot_date, timestamp_utc)
    inbound_contract = _inbound_contract_df(inv_contract)

    inventory_snapshot_path = OUT / f"inventory_snapshot_{snapshot_date}.csv"
    inbound_snapshot_path = OUT / f"inbound_snapshot_{snapshot_date}.csv"
    inv_contract.to_csv(inventory_snapshot_path, index=False)
    inbound_contract.to_csv(inbound_snapshot_path, index=False)

    inv_history = _upsert_history(
        snapshot=inv_contract,
        history_path=INVENTORY_HISTORY_PATH,
        required_columns=INVENTORY_REQUIRED_COLUMNS,
        key_columns=["asof_date", "sku", "marketplace"],
    )
    inbound_history = _upsert_history(
        snapshot=inbound_contract,
        history_path=INBOUND_HISTORY_PATH,
        required_columns=INBOUND_REQUIRED_COLUMNS,
        key_columns=["asof_date", "sku", "marketplace"],
    )

    print(f"[API_COLLECTION] inventory snapshot rows: {len(inv_contract)} -> {inventory_snapshot_path}")
    print(f"[API_COLLECTION] inbound snapshot rows: {len(inbound_contract)} -> {inbound_snapshot_path}")
    print(f"[API_COLLECTION] inventory history rows: {len(inv_history)} -> {INVENTORY_HISTORY_PATH}")
    print(f"[API_COLLECTION] inbound history rows: {len(inbound_history)} -> {INBOUND_HISTORY_PATH}")

    return {
        "calls_products_pricing_get_price": 0,
        "calls_listings_items_get_item": int(pages),
        "calls_finances_get_financial_events": 0,
    }


def _safe_float(value: object) -> float:
    try:
        return float(str(value).strip())
    except Exception:
        return 0.0


def _event_items_for_type(event: Dict[str, object], event_type: str) -> List[Dict[str, object]]:
    if event_type == "refund":
        for key in ("ShipmentItemAdjustmentList", "AdjustmentItemList"):
            items = event.get(key) if isinstance(event, dict) else None
            if isinstance(items, list) and items:
                return items
    if event_type == "adjustment":
        items = event.get("AdjustmentItemList") if isinstance(event, dict) else None
        if isinstance(items, list) and items:
            return items
    return []


def _event_amount_gbp(item: Dict[str, object], event_type: str) -> float:
    if event_type == "refund":
        for key in ("ItemChargeAdjustmentList", "ItemFeeAdjustmentList"):
            entries = item.get(key) if isinstance(item, dict) else None
            if not isinstance(entries, list):
                continue
            total = 0.0
            for entry in entries:
                amount = (entry or {}).get("ChargeAmount") if key == "ItemChargeAdjustmentList" else (entry or {}).get("FeeAmount")
                curr = str((amount or {}).get("CurrencyCode", "")).upper()
                if curr == "GBP":
                    total += _safe_float((amount or {}).get("CurrencyAmount", 0))
            if total != 0:
                return total
        return 0.0
    if event_type == "adjustment":
        amount = item.get("PerUnitAmount") if isinstance(item, dict) else None
        curr = str((amount or {}).get("CurrencyCode", "")).upper()
        if curr != "GBP":
            return 0.0
        return _safe_float((amount or {}).get("CurrencyAmount", 0))
    return 0.0


def _posted_window_utc(snapshot_date: str) -> Tuple[str, str]:
    now_safe = datetime.now(timezone.utc) - pd.Timedelta(minutes=3)
    now_safe_str = now_safe.strftime("%Y-%m-%dT%H:%M:%SZ")
    override = os.environ.get("H_SNAPSHOT_DATE", "").strip()
    if override:
        posted_after = f"{snapshot_date}T00:00:00Z"
        try:
            day_end = datetime.strptime(f"{snapshot_date}T23:59:59Z", "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            posted_before = min(day_end, now_safe).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            posted_before = now_safe_str
        return posted_after, posted_before
    posted_after = f"{snapshot_date}T00:00:00Z"
    posted_before = now_safe_str
    return posted_after, posted_before


def _collect_refunds_adjustments(run_id: str, script_name: str) -> Dict[str, int]:
    load_dotenv_if_missing()
    access_token = get_lwa_access_token()
    snapshot_date = _snapshot_date()
    timestamp_utc = _snapshot_timestamp()
    posted_after, posted_before = _posted_window_utc(snapshot_date)

    training = load_training_set().fillna("")
    enabled = training.get("enabled", "").astype(str).str.strip().str.lower()
    is_enabled = enabled.isin(["yes", "y", "1", "true"])
    seed = training.loc[is_enabled, ["sku", "asin", "marketplace"]].copy()
    if seed.empty:
        seed = pd.DataFrame(columns=["sku", "asin", "marketplace"])
    seed["timestamp_utc"] = timestamp_utc
    seed["asof_date"] = snapshot_date
    seed["marketplace"] = seed.get("marketplace", "UK").astype(str).replace("", "UK")
    seed["source"] = "SPAPI"
    seed["notes"] = "no_financial_events_in_window"
    for col in [
        "refund_event_count",
        "adjustment_event_count",
        "refund_units",
        "adjustment_units",
        "refund_amount_gbp",
        "adjustment_amount_gbp",
    ]:
        seed[col] = 0

    endpoint_calls = 0
    next_token = ""
    aggregates: Dict[str, Dict[str, object]] = {}

    while True:
        params: Dict[str, str]
        if next_token:
            params = {"NextToken": next_token}
        else:
            params = {"PostedAfter": posted_after, "PostedBefore": posted_before}
        ctx = SpApiCallContext(
            run_id=run_id,
            script_name=script_name,
            endpoint="finances_get_financial_events",
            marketplace="UK",
            sku_count=0,
        )
        url = f"{SPAPI_BASE_URL}/finances/v0/financialEvents"
        headers = {
            "x-amz-access-token": access_token,
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        resp = spapi_get(
            ctx=ctx,
            url=url,
            spapi_base_url=SPAPI_BASE_URL,
            headers=headers,
            params=params,
            min_interval_sec=1.0,
            max_retries=2,
        )
        endpoint_calls += 1
        if int(resp.status_code) >= 400:
            raise RuntimeError(f"financial events failed: {resp.status_code} {resp.text}")
        payload = resp.json() or {}
        body = payload.get("payload") or {}
        events = body.get("FinancialEvents") or {}

        for event_type, event_key in (("refund", "RefundEventList"), ("adjustment", "AdjustmentEventList")):
            ev_list = events.get(event_key) or []
            for ev in ev_list:
                posted_date = str((ev or {}).get("PostedDate", "")).strip()
                item_rows = _event_items_for_type(ev, event_type)
                for item in item_rows:
                    sku = str((item or {}).get("SellerSKU", "")).strip()
                    asin = str((item or {}).get("ASIN", "")).strip()
                    if not sku:
                        continue
                    key = f"{snapshot_date}||UK||{sku}"
                    row = aggregates.get(
                        key,
                        {
                            "timestamp_utc": timestamp_utc,
                            "asof_date": snapshot_date,
                            "marketplace": "UK",
                            "sku": sku,
                            "asin": asin,
                            "refund_event_count": 0,
                            "adjustment_event_count": 0,
                            "refund_units": 0,
                            "adjustment_units": 0,
                            "refund_amount_gbp": 0.0,
                            "adjustment_amount_gbp": 0.0,
                            "source": "SPAPI",
                            "notes": "",
                        },
                    )
                    if not row.get("asin") and asin:
                        row["asin"] = asin
                    units = _to_int((item or {}).get("QuantityShipped", 0))
                    amount_gbp = _event_amount_gbp(item, event_type)
                    if event_type == "refund":
                        row["refund_event_count"] = int(row["refund_event_count"]) + 1
                        row["refund_units"] = int(row["refund_units"]) + units
                        row["refund_amount_gbp"] = float(row["refund_amount_gbp"]) + amount_gbp
                    else:
                        row["adjustment_event_count"] = int(row["adjustment_event_count"]) + 1
                        row["adjustment_units"] = int(row["adjustment_units"]) + units
                        row["adjustment_amount_gbp"] = float(row["adjustment_amount_gbp"]) + amount_gbp
                    if not posted_date:
                        row["notes"] = _append_note(str(row.get("notes", "")), f"{event_type}_posted_date_missing")
                    aggregates[key] = row

        next_token = str(body.get("NextToken", "") or "").strip()
        if not next_token:
            break

    agg_df = pd.DataFrame(list(aggregates.values()))
    if not agg_df.empty:
        for col in [
            "refund_event_count",
            "adjustment_event_count",
            "refund_units",
            "adjustment_units",
        ]:
            agg_df[col] = agg_df[col].apply(_to_int)
        for col in ["refund_amount_gbp", "adjustment_amount_gbp"]:
            agg_df[col] = agg_df[col].apply(lambda v: f"{_safe_float(v):.2f}")
        agg_df["source"] = "SPAPI"
        agg_df["notes"] = agg_df.get("notes", "").astype(str)

    if seed.empty and agg_df.empty:
        rows = pd.DataFrame(columns=REFUND_ADJUSTMENT_REQUIRED_COLUMNS)
    elif seed.empty:
        rows = agg_df.copy()
    elif agg_df.empty:
        rows = seed.copy()
    else:
        rows = seed.drop(columns=["notes"]).merge(
            agg_df[
                [
                    "asof_date",
                    "marketplace",
                    "sku",
                    "asin",
                    "refund_event_count",
                    "adjustment_event_count",
                    "refund_units",
                    "adjustment_units",
                    "refund_amount_gbp",
                    "adjustment_amount_gbp",
                    "notes",
                ]
            ],
            on=["asof_date", "marketplace", "sku"],
            how="left",
            suffixes=("", "_agg"),
        )
        rows["asin"] = rows["asin"].astype(str)
        if "asin_agg" in rows.columns:
            rows["asin"] = rows["asin"].where(rows["asin"].str.strip() != "", rows["asin_agg"].astype(str))
            rows = rows.drop(columns=["asin_agg"])
        for col in [
            "refund_event_count",
            "adjustment_event_count",
            "refund_units",
            "adjustment_units",
            "refund_amount_gbp",
            "adjustment_amount_gbp",
        ]:
            rows[col] = rows[col].fillna(0)
        rows["notes"] = rows["notes"].fillna("no_financial_events_in_window").astype(str)
        rows["source"] = "SPAPI"
        rows["timestamp_utc"] = timestamp_utc

    rows = _ensure_columns(rows, REFUND_ADJUSTMENT_REQUIRED_COLUMNS)
    snapshot_path = OUT / f"refund_adjustment_snapshot_{snapshot_date}.csv"
    rows.to_csv(snapshot_path, index=False)
    history = _upsert_history(
        snapshot=rows,
        history_path=REFUND_ADJUSTMENT_HISTORY_PATH,
        required_columns=REFUND_ADJUSTMENT_REQUIRED_COLUMNS,
        key_columns=["asof_date", "sku", "marketplace"],
    )

    print(f"[API_COLLECTION] refund/adjustment snapshot rows: {len(rows)} -> {snapshot_path}")
    print(f"[API_COLLECTION] refund/adjustment history rows: {len(history)} -> {REFUND_ADJUSTMENT_HISTORY_PATH}")
    return {
        "calls_products_pricing_get_price": 0,
        "calls_listings_items_get_item": 0,
        "calls_finances_get_financial_events": int(endpoint_calls),
    }


def _parse_datasets() -> List[str]:
    raw = os.environ.get("API_COLLECTION_DATASETS", "listing_offer,inventory_inbound,refunds_adjustments")
    datasets = [x.strip().lower() for x in str(raw).split(",") if x.strip()]
    out: List[str] = []
    for item in datasets:
        if item in {"listing", "listing_offer", "h001"}:
            out.append("listing_offer")
        elif item in {"inventory", "inventory_inbound", "phase4"}:
            out.append("inventory_inbound")
        elif item in {"refunds", "refunds_adjustments", "phase5"}:
            out.append("refunds_adjustments")
    if not out:
        return ["listing_offer", "inventory_inbound", "refunds_adjustments"]
    return [d for d in dict.fromkeys(out)]


def run_api_collection() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    run_id = f"api_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    script_name = "run_api_collection.py"
    started_utc = _utc_now()
    os.environ["SPAPI_RUN_ID"] = run_id
    os.environ["SPAPI_SCRIPT_NAME"] = script_name

    if not acquire_spapi_lock(run_id, script_name):
        finished_utc = _utc_now()
        _append_api_run_log(
            run_id=run_id,
            started_utc=started_utc,
            finished_utc=finished_utc,
            status="SKIPPED_LOCK_BUSY",
            calls_products_pricing_get_price=0,
            calls_listings_items_get_item=0,
            calls_finances_get_financial_events=0,
            notes="lock busy",
        )
        print("[API_COLLECTION] SKIPPED_LOCK_BUSY out/locks/spapi.lock")
        return 3

    datasets = _parse_datasets()
    totals = {
        "calls_products_pricing_get_price": 0,
        "calls_listings_items_get_item": 0,
        "calls_finances_get_financial_events": 0,
    }

    try:
        for dataset in datasets:
            if dataset == "listing_offer":
                counts = _collect_listing_offer_snapshot(run_id, script_name)
            elif dataset == "inventory_inbound":
                counts = _collect_inventory_and_inbound(run_id, script_name)
            elif dataset == "refunds_adjustments":
                counts = _collect_refunds_adjustments(run_id, script_name)
            else:
                continue
            totals["calls_products_pricing_get_price"] += int(counts.get("calls_products_pricing_get_price", 0))
            totals["calls_listings_items_get_item"] += int(counts.get("calls_listings_items_get_item", 0))
            totals["calls_finances_get_financial_events"] += int(counts.get("calls_finances_get_financial_events", 0))

        finished_utc = _utc_now()
        _append_api_run_log(
            run_id=run_id,
            started_utc=started_utc,
            finished_utc=finished_utc,
            status="OK",
            calls_products_pricing_get_price=totals["calls_products_pricing_get_price"],
            calls_listings_items_get_item=totals["calls_listings_items_get_item"],
            calls_finances_get_financial_events=totals["calls_finances_get_financial_events"],
            notes=f"datasets={','.join(datasets)}",
        )
        return 0
    except Exception as exc:
        finished_utc = _utc_now()
        _append_api_run_log(
            run_id=run_id,
            started_utc=started_utc,
            finished_utc=finished_utc,
            status="FAIL",
            calls_products_pricing_get_price=totals["calls_products_pricing_get_price"],
            calls_listings_items_get_item=totals["calls_listings_items_get_item"],
            calls_finances_get_financial_events=totals["calls_finances_get_financial_events"],
            notes=f"datasets={','.join(datasets)}; error={exc}",
        )
        print(f"[API_COLLECTION] FAIL {exc}")
        return 2
    finally:
        release_spapi_lock()


def run_listing_offer_collection() -> int:
    """
    Backward-compatible entry point used by H001.
    Runs only the listing offer collection dataset.
    """
    prior = os.environ.get("API_COLLECTION_DATASETS")
    os.environ["API_COLLECTION_DATASETS"] = "listing_offer"
    try:
        return run_api_collection()
    finally:
        if prior is None:
            os.environ.pop("API_COLLECTION_DATASETS", None)
        else:
            os.environ["API_COLLECTION_DATASETS"] = prior


def main() -> None:
    raise SystemExit(run_api_collection())


if __name__ == "__main__":
    main()
