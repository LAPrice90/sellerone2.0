"""
Fetch live orders and order items, write to Sheets/CSV, update Run_Status.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from decimal import Decimal, ROUND_HALF_UP
import gspread
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api.get_orders import (
    get_lwa_access_token,
    list_order_items,
    list_orders,
    load_dotenv_if_missing,
)
from scripts.api.get_pricing import run_live_price_lookup
from scripts.api.get_listing_item_price import run_own_offer_price_lookup

SHEET_ID = "1BHueJTk4dvvhIXypzh6i2hQTgc0pB3DWj2khQ2IT6_A"
ORDERS_TAB = "Orders_raw"
ITEMS_TAB = "OrderItems_raw"
ORDERS_ALL_TAB = "Orders_all"
ITEMS_ALL_TAB = "OrderItems_all"
RUN_STATUS_TAB = "Run_Status"
LEVEL1_TAB = "Level_1_Immediate"
FAILED_ORDERS_PATH = Path("out/orders_failed.csv")
RETRY_QUEUE_PATH = Path("out/orders_retry_queue.csv")
MARKER_PATH = Path("out/orders_last_updated.txt")
RESET_ONCE_FLAG = Path("out/orders_reset_once.flag")
MARKETPLACE_ID = os.environ.get("MARKETPLACE_ID", "A1F83G8C2ARO7P")
CREATED_AFTER = os.environ.get("ORDERS_CREATED_AFTER")  # ISO8601 (override; otherwise marker used)
UPDATED_AFTER = os.environ.get("ORDERS_UPDATED_AFTER")  # ISO8601
CREATED_BEFORE = os.environ.get("ORDERS_CREATED_BEFORE")  # ISO8601
UPDATED_BEFORE = os.environ.get("ORDERS_UPDATED_BEFORE")  # ISO8601
MAX_RESULTS_PER_PAGE = int(os.environ.get("ORDERS_MAX_PER_PAGE", "100"))
MAX_RETRIES = int(os.environ.get("ORDERS_MAX_RETRIES", "3"))
SLEEP_SEC = float(os.environ.get("ORDERS_SLEEP_SEC", "3.0"))
PAGE_SLEEP_SEC = float(os.environ.get("ORDERS_PAGE_SLEEP", "8.0"))
ITEM_SLEEP_SEC = float(os.environ.get("ORDERS_ITEM_SLEEP", "2.0"))
# If >0, cap orders processed per run; 0 means no cap.
BATCH_ORDER_LIMIT = int(os.environ.get("ORDERS_BATCH_LIMIT", "0"))
FIRST_RUN_START_ISO = "2025-11-01T00:00:00Z"
PULLED_LAST_RUN_PATH = Path("out/orders_pulled_last_run.csv")
ORDERS_ALL_PATH = Path("out/orders_all.csv")
ITEMS_ALL_PATH = Path("out/order_items_all.csv")
FX_RATES_PATH = Path("out/fx_rates_daily.csv")
FEE_MODEL_PATH = Path("out/fee_country_model.csv")
FEE_RULES_PATH = Path("reference/fee_vat_rules.csv")
MP_PARTICIPATIONS_PATH = Path("out/marketplace_participations.csv")
# Use marker-based cursor (no forced midnight) after initial backfill.
FORCE_FROM_MIDNIGHT = False
PRODUCT_DB_PREVIEW = Path("out/product_db_preview.csv")
PRODUCT_DB_SHEET_ID = os.environ.get("PRODUCT_DB_SHEET_ID", "1b7iREy92vF_a1Lw72g0SOGS7t4-IOSBeeoHetLTN43s")
PRODUCT_DB_TAB = "Product_DB"
REFRESH_PRODUCT_DB = os.environ.get("REFRESH_PRODUCT_DB", "1") == "1"
MIN_REFERRAL_FEE = 0.25  # GBP, UK store minimum per Amazon policy for many categories
VAT_DEFAULT = 0.2  # fallback VAT rate when no SKU/market VAT available
QUOTA_MAX_RETRIES = max(4, MAX_RETRIES)  # cap retries to avoid long stalls on 429/QuotaExceeded
ITEM_MAX_RETRIES = 3  # retries per order items call on quota/429
RETRY_MAX_ATTEMPTS = int(os.environ.get("ORDERS_RETRY_MAX_ATTEMPTS", "10"))
RETRY_BACKOFF_BASE = float(os.environ.get("ORDERS_RETRY_BACKOFF_BASE", "60"))
RETRY_BACKOFF_MAX = float(os.environ.get("ORDERS_RETRY_BACKOFF_MAX", "3600"))
SKIP_MARKER_WRITE = os.environ.get("ORDERS_SKIP_MARKER_WRITE", "").strip() == "1"


def round_half_up(value: float, ndigits: int = 2) -> float:
    try:
        quant = Decimal("1").scaleb(-ndigits)
        return float(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP))
    except Exception:
        return round(value, ndigits)


def _date_key(val: object) -> str:
    try:
        return pd.to_datetime(val, errors="coerce", utc=True).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _load_fx_rates() -> Dict[tuple[str, str], float]:
    if not FX_RATES_PATH.exists():
        return {}
    try:
        fx = pd.read_csv(FX_RATES_PATH, dtype=str)
    except Exception:
        return {}
    if fx.empty:
        return {}
    lookup: Dict[tuple[str, str], float] = {}
    for _, r in fx.iterrows():
        d = str(r.get("date") or "").strip()
        c = str(r.get("currency") or "").strip()
        if not d or not c:
            continue
        try:
            rate = float(r.get("rate_to_gbp") or "")
        except Exception:
            continue
        lookup[(d, c)] = rate
    return lookup


def _fx_convert(amount: float, from_cur: str, to_cur: str, date_key: str, fx_lookup: Dict[tuple[str, str], float]) -> float:
    from_cur = (from_cur or "").strip()
    to_cur = (to_cur or "").strip()
    if not from_cur or not to_cur or from_cur == to_cur:
        return amount
    if date_key == "":
        return amount
    if from_cur == "GBP":
        rate_to = fx_lookup.get((date_key, to_cur))
        if not rate_to:
            return amount
        return amount / rate_to
    if to_cur == "GBP":
        rate_from = fx_lookup.get((date_key, from_cur))
        if not rate_from:
            return amount
        return amount * rate_from
    rate_from = fx_lookup.get((date_key, from_cur))
    rate_to = fx_lookup.get((date_key, to_cur))
    if not rate_from or not rate_to:
        return amount
    return amount * rate_from / rate_to


def _load_marketplace_map() -> Dict[str, Dict[str, str]]:
    if not MP_PARTICIPATIONS_PATH.exists():
        return {}
    try:
        df = pd.read_csv(MP_PARTICIPATIONS_PATH, dtype=str)
    except Exception:
        return {}
    if df.empty or "marketplace_id" not in df.columns:
        return {}
    return {
        str(r.get("marketplace_id")): {
            "country_code": str(r.get("country_code") or ""),
            "currency_code": str(r.get("default_currency") or ""),
        }
        for _, r in df.iterrows()
    }


def _load_fee_country_model() -> pd.DataFrame:
    if not FEE_MODEL_PATH.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(FEE_MODEL_PATH, dtype=str)
    except Exception:
        return pd.DataFrame()
    return df


def _load_fee_vat_rules() -> Dict[str, Dict[str, object]]:
    if not FEE_RULES_PATH.exists():
        return {}
    try:
        df = pd.read_csv(FEE_RULES_PATH, dtype=str).fillna("")
    except Exception:
        return {}
    rules = {}
    for _, r in df.iterrows():
        cc = str(r.get("country_code", "")).strip().upper()
        if not cc:
            continue
        rules[cc] = {
            "dsf_enabled": str(r.get("dsf_enabled", "")).strip(),
            "fba_vat_rate": str(r.get("fba_vat_rate", "")).strip(),
            "commission_vat_rate": str(r.get("commission_vat_rate", "")).strip(),
            "dsf_vat_rate": str(r.get("dsf_vat_rate", "")).strip(),
        }
    return rules




def get_gspread_client() -> gspread.Client:
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        cred_path = str(Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=cred_path)


def export_product_db() -> None:
    if not REFRESH_PRODUCT_DB:
        return
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(PRODUCT_DB_SHEET_ID)
        ws = sheet.worksheet(PRODUCT_DB_TAB)
        rows = ws.get_all_values()
        if not rows:
            return
        PRODUCT_DB_PREVIEW.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows[1:], columns=rows[0]).to_csv(PRODUCT_DB_PREVIEW, index=False)
    except Exception:
        # Fall back to any existing local snapshot.
        return


def write_tab(sheet: gspread.Spreadsheet, tab_name: str, df: pd.DataFrame) -> None:
    payload = [list(df.columns)] + df.fillna("").astype(str).values.tolist()
    try:
        ws = sheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=tab_name, rows=max(len(payload) + 10, 2000), cols=max(len(df.columns) + 5, 40))
    else:
        ws.clear()
    ws.update(range_name="A1", values=payload)


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[B001 {ts}] {msg}")


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


def load_marker() -> Optional[str]:
    """
    Cursor logic (purchase-date based, no overlap):
    - If marker does not exist, create it with FIRST_RUN_START_ISO and return it.
    - Otherwise return marker contents exactly.
    Environment override ORDERS_CREATED_AFTER takes precedence when set.
    Force mode: ORDERS_FORCE_FROM_MIDNIGHT=1 uses today's 00:00:00Z and ignores marker.
    """
    # One-time reset to the configured start date, then rely on the marker thereafter.
    if not RESET_ONCE_FLAG.exists():
        save_marker(FIRST_RUN_START_ISO)
        RESET_ONCE_FLAG.parent.mkdir(parents=True, exist_ok=True)
        RESET_ONCE_FLAG.write_text("done")
        return FIRST_RUN_START_ISO
    if FORCE_FROM_MIDNIGHT:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        return today_start.strftime("%Y-%m-%dT%H:%M:%SZ")
    if CREATED_AFTER:
        return CREATED_AFTER
    if not MARKER_PATH.exists():
        save_marker(FIRST_RUN_START_ISO)
        return FIRST_RUN_START_ISO
    txt = MARKER_PATH.read_text().strip()
    if txt:
        return txt
    save_marker(FIRST_RUN_START_ISO)
    return FIRST_RUN_START_ISO


def save_marker(latest_iso: str) -> None:
    # Normalize to Z format expected by API
    try:
        dt = datetime.fromisoformat(latest_iso.replace("Z", "+00:00"))
        latest_iso = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass
    MARKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKER_PATH.write_text(latest_iso)


def _parse_iso(val: str) -> Optional[datetime]:
    try:
        if not val:
            return None
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except Exception:
        return None


def _format_iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame()


def _load_existing_item_order_ids() -> set[str]:
    if not ITEMS_ALL_PATH.exists():
        return set()
    try:
        df = pd.read_csv(ITEMS_ALL_PATH, usecols=["amazon_order_id"], dtype=str).fillna("")
    except Exception:
        return set()
    if df.empty or "amazon_order_id" not in df.columns:
        return set()
    return set(df["amazon_order_id"].astype(str).str.strip())


def _load_retry_queue() -> pd.DataFrame:
    cols = ["order_id", "attempts", "next_attempt_at", "last_error", "last_seen_at"]
    df = _read_csv_if_exists(RETRY_QUEUE_PATH)
    if df.empty:
        return pd.DataFrame(columns=cols)
    for col in cols:
        if col not in df.columns:
            df[col] = ""
    return df[cols].fillna("")


def _save_retry_queue(df: pd.DataFrame) -> None:
    RETRY_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if df.empty:
        if RETRY_QUEUE_PATH.exists():
            RETRY_QUEUE_PATH.unlink()
        return
    df.to_csv(RETRY_QUEUE_PATH, index=False)


def _enqueue_retry(df: pd.DataFrame, order_id: str, last_error: str) -> pd.DataFrame:
    order_id = str(order_id).strip()
    if not order_id:
        return df
    now_iso = datetime.now(timezone.utc).isoformat()
    if df.empty:
        df = pd.DataFrame(columns=["order_id", "attempts", "next_attempt_at", "last_error", "last_seen_at"])
    match = df["order_id"] == order_id
    if match.any():
        df.loc[match, "last_error"] = last_error
        df.loc[match, "last_seen_at"] = now_iso
    else:
        df = pd.concat(
            [
                df,
                pd.DataFrame(
                    [
                        {
                            "order_id": order_id,
                            "attempts": 0,
                            "next_attempt_at": now_iso,
                            "last_error": last_error,
                            "last_seen_at": now_iso,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
    return df


def _quota_delay(attempt: int, headers: Optional[Dict[str, str]] = None) -> float:
    # Use Retry-After if provided, otherwise exponential backoff.
    retry_after = None
    headers = headers or {}
    for key in ("Retry-After", "retry-after", "x-amzn-RateLimit-Reset"):
        if key in headers:
            try:
                retry_after = float(headers.get(key))  # seconds
                break
            except Exception:
                retry_after = None
    if retry_after is None:
        retry_after = SLEEP_SEC * (2 ** max(0, attempt - 1))
    return min(max(retry_after, SLEEP_SEC), 60.0)


def _process_retry_queue(df: pd.DataFrame, token: str) -> tuple[pd.DataFrame, str]:
    if df.empty:
        return df, token
    now = datetime.now(timezone.utc)
    df = df.copy()
    try:
        df["attempts"] = pd.to_numeric(df["attempts"], errors="coerce").fillna(0).astype(int)
    except Exception:
        df["attempts"] = 0
    next_attempt = df["next_attempt_at"].apply(lambda v: _parse_iso(str(v)) or now)
    due_mask = next_attempt <= now
    due_df = df[due_mask & (df["attempts"] < RETRY_MAX_ATTEMPTS)]
    if due_df.empty:
        return df, token
    log(f"retry queue due: {len(due_df)}")
    for _, row in due_df.iterrows():
        order_id = str(row.get("order_id", "")).strip()
        if not order_id:
            continue
        attempt = int(row.get("attempts", 0)) + 1
        log(f"retry items for order {order_id} attempt {attempt}/{RETRY_MAX_ATTEMPTS}")
        nt = None
        page_items: List[Dict[str, object]] = []
        success = False
        last_error = ""
        try_count = 0
        while try_count < max(ITEM_MAX_RETRIES, 1):
            try_count += 1
            try:
                while True:
                    itm_batch, nt = list_order_items(access_token=token, amazon_order_id=order_id, next_token=nt)
                    for it in itm_batch:
                        it["AmazonOrderId"] = order_id
                    page_items.extend(itm_batch)
                    if nt:
                        continue
                    break
                added_now = len([it for it in page_items if it.get("AmazonOrderId") == order_id])
                if added_now == 0 and try_count < ITEM_MAX_RETRIES:
                    backoff = _quota_delay(try_count)
                    log(f"retry items order {order_id} returned 0 items, sleeping {backoff:.1f}s")
                    time.sleep(backoff)
                    continue
                success = added_now > 0
                break
            except Exception as exc:
                last_error = str(exc)
                if "expired" in last_error.lower() or "401" in last_error or "403" in last_error:
                    try:
                        token = get_lwa_access_token()
                        log(f"refreshed LWA token for retry items on {order_id}")
                        continue
                    except Exception:
                        pass
                if "QuotaExceeded" in last_error or "429" in last_error:
                    backoff = _quota_delay(try_count)
                    log(f"retry items order {order_id} quota sleep {backoff:.1f}s")
                    time.sleep(backoff)
                    continue
                break
        if success:
            df_retry_items = flatten_items(page_items).fillna("").astype(str)
            df_retry_items["_dedupe_key"] = _compiled_items_dedupe_key(df_retry_items)
            existing_items_all = _read_csv_if_exists(ITEMS_ALL_PATH)
            if not existing_items_all.empty:
                existing_items_all = existing_items_all.copy()
                existing_items_all["_dedupe_key"] = _compiled_items_dedupe_key(existing_items_all)
            _write_compiled_unique(
                ITEMS_ALL_PATH,
                existing_items_all,
                df_retry_items,
                dedupe_key_cols=["_dedupe_key"],
            )
            try:
                items_all_df = pd.read_csv(ITEMS_ALL_PATH, dtype=str).fillna("")
                if "_dedupe_key" in items_all_df.columns:
                    items_all_df = items_all_df.drop(columns=["_dedupe_key"])
                    items_all_df.to_csv(ITEMS_ALL_PATH, index=False)
            except Exception:
                pass
            df = df[df["order_id"] != order_id]
            log(f"retry items for order {order_id} succeeded")
        else:
            delay = min(RETRY_BACKOFF_BASE * (2 ** max(0, attempt - 1)), RETRY_BACKOFF_MAX)
            next_iso = (now + timedelta(seconds=delay)).isoformat()
            df.loc[df["order_id"] == order_id, "attempts"] = attempt
            df.loc[df["order_id"] == order_id, "next_attempt_at"] = next_iso
            df.loc[df["order_id"] == order_id, "last_error"] = last_error
            df.loc[df["order_id"] == order_id, "last_seen_at"] = datetime.now(timezone.utc).isoformat()
            log(f"retry items for order {order_id} failed, next attempt in {delay:.0f}s")
    df = df.reset_index(drop=True)
    return df, token


def _write_compiled_unique(
    path: Path,
    existing: pd.DataFrame,
    incoming: pd.DataFrame,
    dedupe_key_cols: list[str],
    sort_cols: Optional[list[str]] = None,
) -> int:
    """
    Append and de-duplicate into a compiled CSV.
    Returns number of rows written.
    """
    if existing.empty:
        out = incoming.copy()
    else:
        # Union columns to keep schema stable as it evolves.
        all_cols = list(dict.fromkeys(list(existing.columns) + list(incoming.columns)))
        for c in all_cols:
            if c not in existing.columns:
                existing[c] = ""
            if c not in incoming.columns:
                incoming[c] = ""
        out = pd.concat([existing[all_cols], incoming[all_cols]], ignore_index=True)

    for c in dedupe_key_cols:
        if c not in out.columns:
            out[c] = ""
    out = out.drop_duplicates(subset=dedupe_key_cols, keep="last")
    if sort_cols:
        for c in sort_cols:
            if c not in out.columns:
                out[c] = ""
        out = out.sort_values(by=sort_cols)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)
    return len(out)


def _compiled_items_dedupe_key(df_items: pd.DataFrame) -> pd.Series:
    """
    Prefer amazon_order_id + order_item_id when available; fallback to amazon_order_id + asin + seller_sku.
    """
    for c in ["amazon_order_id", "order_item_id", "asin", "seller_sku"]:
        if c not in df_items.columns:
            df_items[c] = ""
    oid = df_items["amazon_order_id"].astype(str).fillna("")
    item_id = df_items["order_item_id"].astype(str).fillna("")
    asin = df_items["asin"].astype(str).fillna("")
    sku = df_items["seller_sku"].astype(str).fillna("")
    primary = oid + "|" + item_id
    fallback = oid + "|" + asin + "|" + sku
    use_fallback = item_id.str.len() == 0
    return primary.where(~use_fallback, fallback)


def _read_product_prices() -> Dict[str, Dict[str, object]]:
    df = pd.DataFrame()
    if PRODUCT_DB_PREVIEW.exists():
        try:
            df = pd.read_csv(PRODUCT_DB_PREVIEW)
        except Exception:
            df = pd.DataFrame()
    if df.empty:
        return {}
    for col in ["live_listing_price", "last_sold_price"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in [
        "fba_fee_10",
        "fba_fee_100",
        "last_fba_fee_ex_vat_10",
        "last_fba_fee_ex_vat_100",
        "last_fba_fee_ex_vat",
        "vat_rate",
        "last_vat_rate_pct",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in [
        "referral_fee_10",
        "referral_fee_100",
        "last_commission_pct",
        "last_commission_pct_10",
        "last_commission_pct_100",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    def _parse_ts(val: object) -> Optional[datetime]:
        try:
            return pd.to_datetime(val, utc=True)
        except Exception:
            return None
    if "live_price_last_updated" in df.columns:
        df["live_price_last_updated"] = df["live_price_last_updated"].apply(_parse_ts)
    if "last_sold_price_updated" in df.columns:
        df["last_sold_price_updated"] = df["last_sold_price_updated"].apply(_parse_ts)
    lookup: Dict[str, Dict[str, object]] = {}
    for _, r in df.iterrows():
        sku = str(r.get("seller_sku") or "")
        asin = str(r.get("asin") or "")
        if not sku and not asin:
            continue
        entry = {
            "asin": asin,
            "live_price": r.get("live_listing_price"),
            "live_curr": r.get("live_listing_price_currency") or "",
            "live_ts": r.get("live_price_last_updated"),
            "last_price": r.get("last_sold_price"),
            "last_curr": r.get("last_sold_price_currency") or "",
            "last_ts": r.get("last_sold_price_updated"),
            "vat_rate": r.get("vat_rate") if pd.notna(r.get("vat_rate")) else r.get("last_vat_rate_pct"),
            "fba_fee_10": r.get("fba_fee_10"),
            "fba_fee_100": r.get("fba_fee_100"),
            "last_fba_fee_ex_vat": r.get("last_fba_fee_ex_vat"),
            "last_fba_fee_ex_vat_10": r.get("last_fba_fee_ex_vat_10"),
            "last_fba_fee_ex_vat_100": r.get("last_fba_fee_ex_vat_100"),
            "referral_fee_10": r.get("referral_fee_10"),
            "referral_fee_100": r.get("referral_fee_100"),
            "last_commission_pct": r.get("last_commission_pct"),
            "last_commission_pct_10": r.get("last_commission_pct_10"),
            "last_commission_pct_100": r.get("last_commission_pct_100"),
        }
        if sku:
            lookup[sku] = entry
        if asin and asin not in lookup:
            lookup[asin] = entry
    return lookup


LEVEL1_COLUMNS = [
    "Date",
    "Order ID",
    "marketplace_id",
    "SKU",
    "Quantity Ordered",
    "Price_Total",
    "Price_VAT",
    "Price_ExVAT",
    "Shipping_Total",
    "Shipping_VAT",
    "Shipping_ExVAT",
    "Gift_Total",
    "Gift_VAT",
    "Gift_ExVAT",
    "Promotion_Total",
    "Promotion_VAT",
    "Promotion_ExVAT",
    "COGS_Total",
    "COGS_VAT",
    "COGS_ExVAT",
    "FBA_Fee_Total",
    "FBA_Fee_VAT",
    "FBA_Fee_ExVAT",
    "Commission_Total",
    "Commission_VAT",
    "Commission_ExVAT",
    "Digital_Fee_Total",
    "Digital_Fee_VAT",
    "Digital_Fee_ExVAT",
    "Margin_ExVAT",
    "Margin_Pct",
]


def build_level1(df_orders: pd.DataFrame, df_items: pd.DataFrame, price_lookup: Optional[Dict[str, Dict[str, object]]] = None) -> pd.DataFrame:
    if df_items.empty:
        return pd.DataFrame(columns=LEVEL1_COLUMNS)
    # Drop zero-quantity items (cancelled or placeholder lines) to avoid zero rows in L1.
    if "quantity_ordered" in df_items.columns:
        df_items = df_items.copy()
        qty_num = (
            df_items["quantity_ordered"].astype(str).str.replace(",", "").str.strip()
        )
        df_items["quantity_ordered_num"] = pd.to_numeric(qty_num, errors="coerce").fillna(0)
        df_items = df_items[df_items["quantity_ordered_num"] > 0].drop(columns=["quantity_ordered_num"])
    mp_map = _load_marketplace_map()
    # Attach purchase_date for date column
    merged = df_items.merge(
        df_orders[
            [
                "amazon_order_id",
                "purchase_date",
                "order_status",
                "marketplace_id",
                "order_total_currency",
                "ship_country_code",
            ]
        ]
        if "amazon_order_id" in df_orders.columns
        else df_orders,
        left_on="amazon_order_id",
        right_on="amazon_order_id",
        how="left",
    )
    # Fill missing ship country using marketplace default to keep fee VAT rules working.
    if "ship_country_code" in merged.columns:
        merged["ship_country_code"] = (
            merged["ship_country_code"]
            .fillna("")
            .astype(str)
            .str.strip()
            .replace({"nan": ""})
        )
        if "marketplace_id" in merged.columns:
            merged.loc[merged["ship_country_code"] == "", "ship_country_code"] = (
                merged.loc[merged["ship_country_code"] == "", "marketplace_id"]
                .map(lambda mid: mp_map.get(str(mid).strip(), {}).get("country_code", ""))
                .fillna("")
            )
    rows = []
    price_lookup = price_lookup or {}
    fee_model = _load_fee_country_model()
    fee_rules = _load_fee_vat_rules()
    fee_lookup = {}
    if not fee_model.empty:
        fee_model = fee_model.fillna("")
        for _, r in fee_model.iterrows():
            key = (str(r.get("marketplace_id") or "").strip(), str(r.get("currency") or "").strip())
            if key not in fee_lookup:
                fee_lookup[key] = r.to_dict()
            key_cc = (str(r.get("country_code") or "").strip(), str(r.get("currency") or "").strip())
            if key_cc not in fee_lookup:
                fee_lookup[key_cc] = r.to_dict()

    def _fee_meta(
        marketplace_id: str, order_currency: str, ship_country_code: str = ""
    ) -> Dict[str, str]:
        mid = (marketplace_id or "").strip()
        cur = (order_currency or "").strip()
        ship_cc = (ship_country_code or "").strip()
        mkt_cc = mp_map.get(mid, {}).get("country_code", "")
        # Prefer ship country first, then marketplace default country.
        # Only fall back to marketplace-only keys if country is missing.
        return (
            fee_lookup.get((ship_cc, cur))
            or fee_lookup.get((ship_cc, ""))
            or fee_lookup.get((mkt_cc, cur))
            or fee_lookup.get((mkt_cc, ""))
            or fee_lookup.get((mid, cur))
            or fee_lookup.get((mid, ""))
            or {}
        )
    force_latest_price = os.environ.get("LEVEL1_FORCE_LATEST_PRICE", "0").strip() == "1"
    fx_lookup = _load_fx_rates()
    def _choose_price(
        sku: str, asin: str
    ) -> tuple[
        Optional[float],
        str,
        float,
        Optional[float],
        Optional[float],
        Optional[float],
        Optional[float],
        Optional[float],
        Optional[float],
        Optional[float],
        Optional[float],
        Optional[float],
        Optional[float],
    ]:
        entry = price_lookup.get(sku) or price_lookup.get(asin) or {}
        def _to_float(val: object) -> Optional[float]:
            if val is None or val == "":
                return None
            try:
                return float(val)
            except Exception:
                return None

        live_price = _to_float(entry.get("live_price"))
        last_price = _to_float(entry.get("last_price"))
        live_ts = entry.get("live_ts")
        last_ts = entry.get("last_ts")
        live_curr = entry.get("live_curr") or ""
        last_curr = entry.get("last_curr") or ""
        vat_rate = entry.get("vat_rate")
        if vat_rate in ("", None) or pd.isna(vat_rate):
            vat_rate = entry.get("last_vat_rate_pct")
        if vat_rate in ("", None) or pd.isna(vat_rate):
            vat_rate = None
        fba_fee_10 = entry.get("fba_fee_10")
        fba_fee_100 = entry.get("fba_fee_100")
        ref_fee_10 = entry.get("referral_fee_10")
        ref_fee_100 = entry.get("referral_fee_100")
        last_commission_pct = entry.get("last_commission_pct")
        last_commission_pct_10 = entry.get("last_commission_pct_10")
        last_commission_pct_100 = entry.get("last_commission_pct_100")
        last_fba_fee_ex_vat_10 = entry.get("last_fba_fee_ex_vat_10")
        last_fba_fee_ex_vat_100 = entry.get("last_fba_fee_ex_vat_100")
        last_fba_fee_ex_vat = entry.get("last_fba_fee_ex_vat")
        try:
            vat_rate = float(vat_rate)
            if pd.isna(vat_rate):
                vat_rate = None
            elif vat_rate > 1:
                vat_rate = vat_rate / 100.0
            if vat_rate is not None and vat_rate <= 0:
                vat_rate = None
        except Exception:
            vat_rate = None
        chosen_price = None
        chosen_curr = ""
        if pd.notna(live_price) and pd.isna(last_price):
            chosen_price, chosen_curr = live_price, live_curr
        elif pd.isna(live_price) and pd.notna(last_price):
            chosen_price, chosen_curr = last_price, last_curr
        elif pd.notna(live_price) and pd.notna(last_price):
            if live_ts and last_ts:
                if live_ts >= last_ts:
                    chosen_price, chosen_curr = live_price, live_curr
                else:
                    chosen_price, chosen_curr = last_price, last_curr
            else:
                chosen_price, chosen_curr = live_price, live_curr
        return (
            chosen_price if pd.notna(chosen_price) else None,
            chosen_curr,
            vat_rate if vat_rate is not None else VAT_DEFAULT,
            fba_fee_10 if pd.notna(fba_fee_10) else None,
            fba_fee_100 if pd.notna(fba_fee_100) else None,
            ref_fee_10 if pd.notna(ref_fee_10) else None,
            ref_fee_100 if pd.notna(ref_fee_100) else None,
            last_commission_pct if pd.notna(last_commission_pct) else None,
            last_commission_pct_10 if pd.notna(last_commission_pct_10) else None,
            last_commission_pct_100 if pd.notna(last_commission_pct_100) else None,
            last_fba_fee_ex_vat_10 if pd.notna(last_fba_fee_ex_vat_10) else None,
            last_fba_fee_ex_vat_100 if pd.notna(last_fba_fee_ex_vat_100) else None,
            last_fba_fee_ex_vat if pd.notna(last_fba_fee_ex_vat) else None,
        )

    for _, r in merged.iterrows():
        sku = str(r.get("seller_sku", ""))
        asin = str(r.get("asin", ""))
        order_currency = str(r.get("item_price_currency") or r.get("order_total_currency") or "").strip()
        if not order_currency:
            order_currency = mp_map.get(str(r.get("marketplace_id") or "").strip(), {}).get("currency_code", "")
        (
            price,
            price_curr,
            vat_rate,
            fee_10,
            fee_100,
            ref_10,
            ref_100,
            ref_fallback,
            ref_band_10,
            ref_band_100,
            fee_override_10,
            fee_override_100,
            fee_override_any,
        ) = _choose_price(sku, asin)
        qty_val = 1.0
        qty_raw = r.get("quantity_ordered", "")
        try:
            qraw = qty_raw or 1
            qty_val = float(qraw)
        except Exception:
            qty_val = 1.0
        status = str(r.get("order_status", "")).strip().lower()
        is_canceled = status == "canceled"
        if qty_val <= 0:
            continue
        if is_canceled:
            continue
            qty_raw = "0"
        cogs_ex_raw = r.get("COGS_ExVAT", "")
        cogs_vat_raw = r.get("COGS_VAT", "")
        cogs_total_raw = r.get("COGS_Total", "")
        price_total = ""
        price_vat = ""
        price_exvat = ""
        price_exvat_num: Optional[float] = None
        item_price_raw = r.get("item_price_amount", "")
        item_tax_raw = r.get("item_tax_amount", "")
        item_price_val: Optional[float] = None
        item_tax_val: Optional[float] = None
        try:
            if str(item_price_raw).strip() not in ("", "nan", "None"):
                item_price_val = float(item_price_raw)
        except Exception:
            item_price_val = None
        try:
            if str(item_tax_raw).strip() not in ("", "nan", "None"):
                item_tax_val = float(item_tax_raw)
        except Exception:
            item_tax_val = None

        if item_price_val is not None and not (force_latest_price and price is not None):
            # Prefer raw item price/tax when available; fall back to VAT rate if tax missing.
            try:
                gross = float(item_price_val)
                rate = vat_rate if vat_rate is not None else VAT_DEFAULT
                if item_tax_val is not None:
                    vat_amt = float(item_tax_val)
                    exvat = gross - vat_amt
                else:
                    exvat = gross / (1 + rate)
                    vat_amt = gross - exvat
                price_total = f"{gross:.2f}"
                price_exvat = f"{exvat:.2f}"
                price_vat = f"{vat_amt:.2f}"
                price_exvat_num = exvat
                # Use per-unit price for downstream fee selection.
                price = gross / qty_val if qty_val else gross
            except Exception:
                pass
        elif price is not None:
            try:
                price_currency = str(price_curr or "").strip() or "GBP"
                date_key = _date_key(r.get("purchase_date", ""))
                if order_currency:
                    price = _fx_convert(float(price), price_currency, order_currency, date_key, fx_lookup)
                gross = float(price) * qty_val  # price is per-unit; scale by qty
                rate = vat_rate if vat_rate is not None else VAT_DEFAULT
                exvat = gross / (1 + rate)
                vat_amt = gross - exvat
                price_total = f"{gross:.2f}"
                price_exvat = f"{exvat:.2f}"
                price_vat = f"{vat_amt:.2f}"
                price_exvat_num = exvat
            except Exception:
                pass
        ship_cc = str(r.get("ship_country_code") or "").strip().upper()
        fee_meta = _fee_meta(
            str(r.get("marketplace_id") or ""),
            order_currency,
            ship_cc,
        )

        def _to_float(val: object) -> Optional[float]:
            try:
                if val in ("", None) or pd.isna(val):
                    return None
                return float(val)
            except Exception:
                return None

        fba_vat_rate = _to_float(fee_meta.get("fba_vat_rate"))
        comm_vat_rate = _to_float(fee_meta.get("commission_vat_rate"))
        dsf_vat_rate = _to_float(fee_meta.get("dsf_vat_rate"))
        fba_avg_ex_per_unit = _to_float(fee_meta.get("fba_avg_ex_per_unit"))
        comm_pct_avg = _to_float(fee_meta.get("commission_pct_avg"))
        dsf_pct = _to_float(fee_meta.get("dsf_pct"))
        # Apply fixed fee VAT rules if present for this country.
        if ship_cc and ship_cc in fee_rules:
            rule = fee_rules[ship_cc]
            try:
                if rule.get("fba_vat_rate", "") != "":
                    fba_vat_rate = float(rule["fba_vat_rate"])
            except Exception:
                pass
            try:
                if rule.get("commission_vat_rate", "") != "":
                    comm_vat_rate = float(rule["commission_vat_rate"])
            except Exception:
                pass
            try:
                if rule.get("dsf_vat_rate", "") != "":
                    dsf_vat_rate = float(rule["dsf_vat_rate"])
            except Exception:
                pass
            dsf_enabled_raw = str(rule.get("dsf_enabled", "")).strip().lower()
            if dsf_enabled_raw in ("0", "false", "no", "n"):
                dsf_pct = 0.0

        ship_price = 0.0
        ship_tax = 0.0
        try:
            ship_price = float(r.get("shipping_price_amount") or 0.0)
            ship_tax = float(r.get("shipping_tax_amount") or 0.0)
        except Exception:
            ship_price, ship_tax = 0.0, 0.0
        ship_net = 0.0
        if ship_price > 0:
            ship_net = ship_price - ship_tax if ship_price >= ship_tax else ship_price
        ship_total = f"{ship_price:.2f}" if ship_price else ""
        ship_vat = f"{ship_tax:.2f}" if ship_tax else ""
        ship_ex = f"{ship_net:.2f}" if ship_net else ""

        # adjust price band selection to per-unit gross price
        unit_price_val = None
        if price is not None:
            unit_price_val = price

        # FBA fee selection (per unit) then scale by qty
        fba_ex = "0.00"
        fba_vat = "0.00"
        fba_total = "0.00"
        if price is not None:
            selected_fee = None
            if unit_price_val is not None and unit_price_val <= 10 and fee_override_10 not in (None, "", "nan"):
                selected_fee = fee_override_10
            elif unit_price_val is not None and unit_price_val > 10 and fee_override_100 not in (None, "", "nan"):
                selected_fee = fee_override_100
            elif fee_override_any not in (None, "", "nan"):
                selected_fee = fee_override_any
            elif fee_10 is not None and unit_price_val is not None and unit_price_val <= 10:
                selected_fee = fee_10
            elif fee_100 is not None and unit_price_val is not None and unit_price_val > 10:
                selected_fee = fee_100
            elif fee_10 is not None:
                selected_fee = fee_10
            elif fee_100 is not None:
                selected_fee = fee_100
            if selected_fee is not None:
                try:
                    ex_fee_unit = float(selected_fee)
                    ex_fee_total = ex_fee_unit * qty_val
                    fee_rate = fba_vat_rate if fba_vat_rate is not None else (vat_rate if vat_rate is not None else VAT_DEFAULT)
                    fee_vat_total = round_half_up(ex_fee_total * fee_rate, 2)
                    fba_ex = f"{ex_fee_total:.2f}"
                    fba_vat = f"{fee_vat_total:.2f}"
                    fba_total = f"{round_half_up(ex_fee_total + fee_vat_total, 2):.2f}"
                except Exception:
                    pass
            elif fba_avg_ex_per_unit is not None and fba_avg_ex_per_unit > 0:
                try:
                    ex_fee_total = float(fba_avg_ex_per_unit) * qty_val
                    fee_rate = fba_vat_rate if fba_vat_rate is not None else (vat_rate if vat_rate is not None else VAT_DEFAULT)
                    fee_vat_total = round_half_up(ex_fee_total * fee_rate, 2) if fee_rate else 0.0
                    fba_ex = f"{ex_fee_total:.2f}"
                    fba_vat = f"{fee_vat_total:.2f}"
                    fba_total = f"{round_half_up(ex_fee_total + fee_vat_total, 2):.2f}"
                except Exception:
                    pass
        # Commission: rate-based, base is gross (VAT-inclusive)
        comm_total = "0.00"
        comm_vat = "0.00"
        comm_ex = "0.00"
        comm_ex_amt: Optional[float] = None
        if price is not None:
            selected_rate = None
            if ref_band_10 is not None and unit_price_val is not None and unit_price_val <= 10:
                selected_rate = ref_band_10
            elif ref_band_100 is not None and unit_price_val is not None and unit_price_val > 10:
                selected_rate = ref_band_100
            elif ref_fallback is not None:
                selected_rate = ref_fallback
            elif ref_10 is not None and unit_price_val is not None and unit_price_val <= 10:
                selected_rate = ref_10
            elif ref_100 is not None and unit_price_val is not None and unit_price_val > 10:
                selected_rate = ref_100
            elif ref_10 is not None:
                selected_rate = ref_10
            elif ref_100 is not None:
                selected_rate = ref_100
            if selected_rate is None and comm_pct_avg is not None and comm_pct_avg > 0:
                selected_rate = comm_pct_avg
            if selected_rate is not None:
                try:
                    rate_val = float(selected_rate)
                    # Treat stored values as percentages if >1. Prefer fractions (e.g., 0.13 for 13%).
                    if rate_val > 1:
                        rate_val = rate_val / 100.0
                    # Per-unit rounding to match Amazon: compute per-unit fee, round, then scale by qty.
                    unit_gross = float(price)
                    per_unit_fee = unit_gross * rate_val
                    if per_unit_fee < MIN_REFERRAL_FEE:
                        per_unit_fee = MIN_REFERRAL_FEE
                    per_unit_fee = round_half_up(per_unit_fee, 2)
                    comm_ex_amt = per_unit_fee * qty_val
                    fee_rate = comm_vat_rate if comm_vat_rate is not None else (vat_rate if vat_rate is not None else VAT_DEFAULT)
                    comm_vat_amt = round_half_up(comm_ex_amt * fee_rate, 2) if fee_rate else 0.0
                    comm_ex = f"{comm_ex_amt:.2f}"
                    comm_vat = f"{comm_vat_amt:.2f}"
                    comm_total = f"{comm_ex_amt + comm_vat_amt:.2f}"
                except Exception:
                    pass

        # Digital Services Fee components (estimate): 2% of commission + FBA ex-VAT fees.
        # Use absolute fee bases and keep the DSF as a negative fee.
        try:
            fba_ex_amt = float(fba_ex) if fba_ex else 0.0
        except Exception:
            fba_ex_amt = 0.0
        comm_basis = abs(comm_ex_amt) if comm_ex_amt is not None else 0.0
        fba_basis = abs(fba_ex_amt)
        dsf_enabled = dsf_pct is None or dsf_pct >= 0.5
        dsf_ex_total_val = round_half_up((comm_basis + fba_basis) * 0.02, 2) if dsf_enabled else 0.0
        dsf_ex_total_val = -dsf_ex_total_val if dsf_ex_total_val > 0 else dsf_ex_total_val
        dsf_total = "0.00"
        dsf_vat = "0.00"
        dsf_ex = "0.00"
        if dsf_ex_total_val != 0:
            rate = dsf_vat_rate if dsf_vat_rate is not None else (vat_rate if vat_rate is not None else VAT_DEFAULT)
            dsf_vat_val = round_half_up(abs(dsf_ex_total_val) * rate, 2) if rate else 0.0
            dsf_vat_val = -dsf_vat_val if dsf_ex_total_val < 0 else dsf_vat_val
            dsf_total_val = dsf_ex_total_val + dsf_vat_val
            dsf_ex = f"{dsf_ex_total_val:.2f}"
            dsf_vat = f"{dsf_vat_val:.2f}"
            dsf_total = f"{dsf_total_val:.2f}"

        def _to_num(val: object) -> float:
            try:
                return float(val)
            except Exception:
                return 0.0

        margin_ex = ""
        margin_pct = ""
        try:
            rev_ex = _to_num(price_exvat) + _to_num(ship_ex) + _to_num(gift_ex) + _to_num(promo_ex)
            fee_ex = abs(_to_num(fba_ex)) + abs(_to_num(comm_ex)) + abs(_to_num(dsf_ex))
            cogs_ex = abs(_to_num(cogs_ex_raw))
            if rev_ex != 0:
                margin_val = rev_ex - fee_ex - cogs_ex
                margin_ex = f"{margin_val:.2f}"
                margin_pct = f"{(margin_val / rev_ex * 100.0):.2f}"
        except Exception:
            margin_ex = ""
            margin_pct = ""

        rows.append(
            {
                "Date": r.get("purchase_date", ""),
                "Order ID": r.get("amazon_order_id", ""),
                "marketplace_id": r.get("marketplace_id", ""),
                "SKU": sku,
                "Quantity Ordered": r.get("quantity_ordered", ""),
                "Price_Total": price_total,
                "Price_VAT": price_vat,
                "Price_ExVAT": price_exvat,
                "Shipping_Total": ship_total,
                "Shipping_VAT": ship_vat,
                "Shipping_ExVAT": ship_ex,
                "Gift_Total": "0.00",
                "Gift_VAT": "0.00",
                "Gift_ExVAT": "0.00",
                "Promotion_Total": "0.00",
                "Promotion_VAT": "0.00",
                "Promotion_ExVAT": "0.00",
                "COGS_Total": cogs_total_raw,
                "COGS_VAT": cogs_vat_raw,
                "COGS_ExVAT": cogs_ex_raw,
                "FBA_Fee_Total": fba_total,
                "FBA_Fee_VAT": fba_vat,
                "FBA_Fee_ExVAT": fba_ex,
                "Commission_Total": comm_total,
                "Commission_VAT": comm_vat,
                "Commission_ExVAT": comm_ex,
                "Digital_Fee_Total": dsf_total,
                "Digital_Fee_VAT": dsf_vat,
                "Digital_Fee_ExVAT": dsf_ex,
                "Margin_ExVAT": margin_ex,
                "Margin_Pct": margin_pct,
            }
        )
    return pd.DataFrame(rows, columns=LEVEL1_COLUMNS)


def flatten_orders(orders: List[Dict[str, object]]) -> pd.DataFrame:
    rows = []
    for o in orders:
        payload = o or {}
        total = payload.get("OrderTotal") or {}
        shipping_addr = payload.get("ShippingAddress") or {}
        rows.append(
            {
                "amazon_order_id": payload.get("AmazonOrderId", ""),
                "purchase_date": payload.get("PurchaseDate", ""),
                "last_update_date": payload.get("LastUpdateDate", ""),
                "order_status": payload.get("OrderStatus", ""),
                "fulfillment_channel": payload.get("FulfillmentChannel", ""),
                "sales_channel": payload.get("SalesChannel", ""),
                "ship_service_level": payload.get("ShipServiceLevel", ""),
                "order_total_amount": total.get("Amount", ""),
                "order_total_currency": total.get("CurrencyCode", ""),
                "number_items_shipped": payload.get("NumberOfItemsShipped", ""),
                "number_items_unshipped": payload.get("NumberOfItemsUnshipped", ""),
                "payment_method": payload.get("PaymentMethod", ""),
                "marketplace_id": payload.get("MarketplaceId", ""),
                "buyer_email": payload.get("BuyerEmail", ""),
                "buyer_name": payload.get("BuyerName", ""),
                "shipment_service_level_category": payload.get("ShipmentServiceLevelCategory", ""),
                "earliest_ship_date": payload.get("EarliestShipDate", ""),
                "latest_ship_date": payload.get("LatestShipDate", ""),
                "earliest_delivery_date": payload.get("EarliestDeliveryDate", ""),
                "latest_delivery_date": payload.get("LatestDeliveryDate", ""),
                "is_business_order": payload.get("IsBusinessOrder", ""),
                "is_prime": payload.get("IsPrime", ""),
                "is_premium_order": payload.get("IsPremiumOrder", ""),
                "is_replacement_order": payload.get("IsReplacementOrder", ""),
                "ship_city": shipping_addr.get("City", ""),
                "ship_state_or_region": shipping_addr.get("StateOrRegion", ""),
                "ship_postal_code": shipping_addr.get("PostalCode", ""),
                "ship_country_code": shipping_addr.get("CountryCode", ""),
            }
        )
    return pd.DataFrame(rows)


def flatten_items(items: List[Dict[str, object]]) -> pd.DataFrame:
    rows = []
    for it in items:
        payload = it or {}
        item_price = payload.get("ItemPrice") or {}
        item_tax = payload.get("ItemTax") or {}
        ship_price = payload.get("ShippingPrice") or {}
        ship_tax = payload.get("ShippingTax") or {}
        gw_price = payload.get("GiftWrapPrice") or {}
        gw_tax = payload.get("GiftWrapTax") or {}
        promo_disc = payload.get("PromotionDiscount") or {}
        promo_disc_tax = payload.get("PromotionDiscountTax") or {}
        rows.append(
            {
                "amazon_order_id": payload.get("AmazonOrderId", ""),
                "asin": payload.get("ASIN", ""),
                "seller_sku": payload.get("SellerSKU", ""),
                "order_item_id": payload.get("OrderItemId", ""),
                "title": payload.get("Title", ""),
                "quantity_ordered": payload.get("QuantityOrdered", ""),
                "quantity_shipped": payload.get("QuantityShipped", ""),
                "item_price_amount": item_price.get("Amount", ""),
                "item_price_currency": item_price.get("CurrencyCode", ""),
                "item_tax_amount": item_tax.get("Amount", ""),
                "item_tax_currency": item_tax.get("CurrencyCode", ""),
                "shipping_price_amount": ship_price.get("Amount", ""),
                "shipping_price_currency": ship_price.get("CurrencyCode", ""),
                "shipping_tax_amount": ship_tax.get("Amount", ""),
                "shipping_tax_currency": ship_tax.get("CurrencyCode", ""),
                "giftwrap_price_amount": gw_price.get("Amount", ""),
                "giftwrap_price_currency": gw_price.get("CurrencyCode", ""),
                "giftwrap_tax_amount": gw_tax.get("Amount", ""),
                "giftwrap_tax_currency": gw_tax.get("CurrencyCode", ""),
                "promotion_discount_amount": promo_disc.get("Amount", ""),
                "promotion_discount_currency": promo_disc.get("CurrencyCode", ""),
                "promotion_discount_tax_amount": promo_disc_tax.get("Amount", ""),
                "promotion_discount_tax_currency": promo_disc_tax.get("CurrencyCode", ""),
                "is_gift": payload.get("IsGift", ""),
                "is_transparency": payload.get("IsTransparency", ""),
                "condition_id": payload.get("ConditionId", ""),
                "condition_subtype_id": payload.get("ConditionSubtypeId", ""),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    load_dotenv_if_missing()
    token = get_lwa_access_token()
    if not MARKETPLACE_ID:
        raise RuntimeError("MARKETPLACE_ID is required")

    retry_df = _load_retry_queue()
    existing_item_order_ids = _load_existing_item_order_ids()
    effective_created_after = load_marker()

    started_at = datetime.now(timezone.utc)
    script_name = "B001_run_orders_to_sheet.py"
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
    failed_orders: List[str] = []

    client = get_gspread_client()
    sheet = client.open_by_key(SHEET_ID)

    try:
        retry_df, token = _process_retry_queue(retry_df, token)
        existing_item_order_ids = _load_existing_item_order_ids()
        orders_pages: List[pd.DataFrame] = []
        items_pages: List[pd.DataFrame] = []
        next_token = None
        page = 0
        total_orders = 0
        processed_orders = 0
        max_processed_ts: Optional[datetime] = None
        while True:
            page += 1
            attempts_used = page
            order_attempt = 0
            batch: List[Dict[str, object]] = []
            while True:
                order_attempt += 1
                try:
                    log(f"orders page {page} (created_after={effective_created_after}, token={bool(next_token)})")
                    batch, next_token = list_orders(
                        access_token=token,
                        marketplace_ids=[MARKETPLACE_ID],
                        created_after=effective_created_after,
                        created_before=CREATED_BEFORE,
                        updated_after=None,
                        updated_before=None,
                        next_token=next_token,
                        max_results_per_page=MAX_RESULTS_PER_PAGE,
                    )
                    time.sleep(PAGE_SLEEP_SEC)
                    break
                except Exception as exc_inner:
                    msg = str(exc_inner)
                    if "expired" in msg.lower() or "401" in msg or "403" in msg:
                        try:
                            token = get_lwa_access_token()
                            log("refreshed LWA token after 401/403")
                            continue
                        except Exception:
                            pass
                    if order_attempt < QUOTA_MAX_RETRIES and ("QuotaExceeded" in msg or "429" in msg):
                        delay = _quota_delay(order_attempt)
                        log(f"orders page {page} quota retry {order_attempt} delaying {delay:.1f}s")
                        time.sleep(delay)
                        continue
                    raise
            # If a batch limit is set (>0), trim this batch to remaining.
            if BATCH_ORDER_LIMIT > 0:
                remaining = BATCH_ORDER_LIMIT - processed_orders
                if remaining <= 0:
                    next_token = None
                    batch = []
                elif remaining < len(batch):
                    batch = batch[:remaining]
                    next_token = None
            total_orders += len(batch)
            processed_orders += len(batch)
            log(f"orders page {page} received {len(batch)} (total so far this run: {processed_orders}{'/' + str(BATCH_ORDER_LIMIT) if BATCH_ORDER_LIMIT>0 else ''}); next_token={bool(next_token)}")

            # Flatten orders for this page and fetch items for them before moving on.
            df_page_orders = flatten_orders(batch)
            page_items: List[Dict[str, object]] = []
            skipped_item_fetch = 0
            fetched_item_orders = 0
            force_fetch_ids = set()
            if not retry_df.empty and "order_id" in retry_df.columns:
                force_fetch_ids = set(retry_df["order_id"].astype(str).str.strip())
            for idx, o in enumerate(batch, 1):
                order_id = o.get("AmazonOrderId", "")
                order_id = str(order_id).strip()
                if order_id and order_id in existing_item_order_ids and order_id not in force_fetch_ids:
                    skipped_item_fetch += 1
                    continue
                nt = None
                attempt = 0
                success = False
                while attempt < QUOTA_MAX_RETRIES:
                    attempt += 1
                    try:
                        while True:
                            itm_batch, nt = list_order_items(access_token=token, amazon_order_id=order_id, next_token=nt)
                            for it in itm_batch:
                                it["AmazonOrderId"] = order_id
                            page_items.extend(itm_batch)
                            if nt:
                                continue
                            break
                        # If no items returned, treat as a soft failure and retry up to ITEM_MAX_RETRIES.
                        added_now = len([it for it in page_items if it.get("AmazonOrderId") == order_id])
                        if added_now == 0 and attempt < ITEM_MAX_RETRIES:
                            backoff = _quota_delay(attempt)
                            log(f"items order {order_id} returned 0 items, retry {attempt}/{ITEM_MAX_RETRIES} sleeping {backoff:.1f}s")
                            time.sleep(backoff)
                            continue
                        success = added_now > 0
                        break
                    except Exception as exc:
                        msg = str(exc)
                        if "expired" in msg.lower() or "401" in msg or "403" in msg:
                            try:
                                token = get_lwa_access_token()
                                log(f"refreshed LWA token for items on {order_id}")
                                continue
                            except Exception:
                                pass
                        if attempt < QUOTA_MAX_RETRIES and ("QuotaExceeded" in msg or "429" in msg):
                            backoff = _quota_delay(attempt)
                            log(f"items order {order_id} retry {attempt} due to quota, sleeping {backoff:.1f}s")
                            time.sleep(backoff)
                            continue
                        failed_orders.append(order_id)
                        retry_df = _enqueue_retry(retry_df, order_id, msg)
                        last_error = str(exc)
                time.sleep(ITEM_SLEEP_SEC)
                items_added = len([it for it in page_items if it.get("AmazonOrderId") == order_id]) if success else 0
                log(f"items for order {idx}/{len(batch)} {order_id}: added {items_added} on this page")
                if not success:
                    log(f"items for order {order_id} failed to return items after retries; marking failed")
                    failed_orders.append(order_id)
                    retry_df = _enqueue_retry(retry_df, order_id, "no_items_returned")
                else:
                    if order_id:
                        existing_item_order_ids.add(order_id)
                        fetched_item_orders += 1

            df_page_items = flatten_items(page_items)
            orders_pages.append(df_page_orders)
            items_pages.append(df_page_items)
            log(f"items fetch summary page {page}: fetched={fetched_item_orders} skipped={skipped_item_fetch}")

            # Incremental checkpoint: append to compiled CSVs and advance marker to page max purchase_date.
            try:
                existing_orders_all = _read_csv_if_exists(ORDERS_ALL_PATH)
                _write_compiled_unique(
                    ORDERS_ALL_PATH,
                    existing_orders_all,
                    df_page_orders.copy().fillna("").astype(str),
                    dedupe_key_cols=["amazon_order_id"],
                    sort_cols=["purchase_date", "amazon_order_id"],
                )
                df_page_items_in = df_page_items.copy().fillna("").astype(str)
                df_page_items_in["_dedupe_key"] = _compiled_items_dedupe_key(df_page_items_in)
                existing_items_all = _read_csv_if_exists(ITEMS_ALL_PATH)
                if not existing_items_all.empty:
                    existing_items_all = existing_items_all.copy()
                    existing_items_all["_dedupe_key"] = _compiled_items_dedupe_key(existing_items_all)
                _write_compiled_unique(
                    ITEMS_ALL_PATH,
                    existing_items_all,
                    df_page_items_in,
                    dedupe_key_cols=["_dedupe_key"],
                )
            except Exception as exc_ckpt:
                log(f"checkpoint write failed: {exc_ckpt}")

            # Advance marker to max purchase_date seen on this page (if available).
            if not SKIP_MARKER_WRITE:
                try:
                    ts_vals: List[datetime] = []
                    for _, r in df_page_orders.iterrows():
                        pu = _parse_iso(str(r.get("purchase_date") or ""))
                        if pu:
                            ts_vals.append(pu)
                    if ts_vals:
                        page_max = max(ts_vals)
                        max_processed_ts = page_max if max_processed_ts is None else max(max_processed_ts, page_max)
                        save_marker(_format_iso_z(max_processed_ts))
                except Exception:
                    pass

            if not next_token:
                break

        # Concatenate all pages for snapshots/Level1
        df_orders = pd.concat(orders_pages, ignore_index=True) if orders_pages else pd.DataFrame()
        df_items = pd.concat(items_pages, ignore_index=True) if items_pages else pd.DataFrame()
        # Sort orders by purchase_date (then order_id) for readability and stable output.
        if not df_orders.empty:
            sort_key = pd.to_datetime(df_orders.get("purchase_date"), errors="coerce")
            df_orders = df_orders.assign(_sort_purchase=sort_key)
            df_orders = df_orders.sort_values(by=["_sort_purchase", "amazon_order_id"]).drop(columns=["_sort_purchase"])
        if not df_items.empty:
            df_items = df_items.sort_values(by=["amazon_order_id", "order_item_id"], na_position="last")
        export_product_db()
        price_lookup = _read_product_prices()
        # Optional: fetch OUR offer prices for SKUs in this pull and override lookup
        # (Used for Level 1 only; does not write back to Product_DB.)
        use_own_offer_price = os.environ.get("LEVEL1_USE_OWN_OFFER_PRICE", "0").strip() == "1"
        if use_own_offer_price and not df_items.empty:
            try:
                skus = (
                    df_items.get("seller_sku")
                    .fillna("")
                    .astype(str)
                    .tolist()
                    if "seller_sku" in df_items.columns
                    else []
                )
                skus = [s for s in skus if s]
                if skus:
                    own_map = run_own_offer_price_lookup(skus, MARKETPLACE_ID)
                    now_ts = datetime.now(timezone.utc)
                    for sku, data in own_map.items():
                        entry = price_lookup.get(sku) or {}
                        entry["live_price"] = data.get("price")
                        entry["live_curr"] = data.get("currency") or entry.get("live_curr") or ""
                        entry["live_ts"] = now_ts
                        price_lookup[sku] = entry
            except Exception as exc:
                print({"status": "warning", "alert": "own_offer_price_lookup_failed", "error": str(exc)})

        # Optional: fetch live prices for SKUs in this pull and override lookup
        # (Used for Level 1 only; does not write back to Product_DB.)
        use_live_price_api = os.environ.get("LEVEL1_USE_LIVE_PRICE_API", "0").strip() == "1"
        if (not use_own_offer_price) and use_live_price_api and not df_items.empty:
            try:
                skus = (
                    df_items.get("seller_sku")
                    .fillna("")
                    .astype(str)
                    .tolist()
                    if "seller_sku" in df_items.columns
                    else []
                )
                skus = [s for s in skus if s]
                if skus:
                    live_map = run_live_price_lookup(skus, MARKETPLACE_ID)
                    now_ts = datetime.now(timezone.utc)
                    for sku, data in live_map.items():
                        entry = price_lookup.get(sku) or {}
                        entry["live_price"] = data.get("price")
                        entry["live_curr"] = data.get("currency") or entry.get("live_curr") or ""
                        entry["live_ts"] = now_ts
                        price_lookup[sku] = entry
            except Exception as exc:
                print({"status": "warning", "alert": "live_price_lookup_failed", "error": str(exc)})
        # Build Level 1 from compiled history (full DB) when available.
        try:
            orders_all_df = pd.read_csv(ORDERS_ALL_PATH, dtype=str).fillna("")
            items_all_df = pd.read_csv(ITEMS_ALL_PATH, dtype=str).fillna("")
            df_level1 = build_level1(orders_all_df, items_all_df, price_lookup)
        except Exception as exc:
            print({"status": "warning", "alert": "level1_from_archive_failed", "error": str(exc)})
            # Avoid clobbering Level 1 with a tiny pull if archive build fails.
            df_level1 = _read_csv_if_exists(Path("out/financial_events_level1.csv"))
            if df_level1.empty:
                df_level1 = build_level1(df_orders, df_items, price_lookup)
        if not df_level1.empty:
            # Drop any blank keys to avoid poisoning L1 -> Order_Master joins.
            df_level1 = df_level1[
                df_level1["Order ID"].astype(str).str.strip().ne("")
                & df_level1["SKU"].astype(str).str.strip().ne("")
            ]
            sort_key = pd.to_datetime(df_level1.get("Date"), errors="coerce")
            df_level1 = df_level1.assign(_sort_date=sort_key)
            df_level1 = df_level1.sort_values(by=["_sort_date", "Order ID", "SKU"]).drop(columns=["_sort_date"])
        row_count = len(df_orders) + len(df_items)
        col_count = max(len(df_orders.columns), len(df_items.columns))

        out_orders = Path("out/orders_raw.csv")
        out_items = Path("out/order_items_raw.csv")
        out_level1 = Path("out/financial_events_level1.csv")
        out_pulled = PULLED_LAST_RUN_PATH
        out_orders.parent.mkdir(parents=True, exist_ok=True)
        df_orders.to_csv(out_orders, index=False)
        df_items.to_csv(out_items, index=False)
        df_level1.to_csv(out_level1, index=False)
        pulled_cols = ["amazon_order_id", "purchase_date", "last_update_date", "order_status"]
        for col in pulled_cols:
            if col not in df_orders.columns:
                df_orders[col] = ""
        df_orders[pulled_cols].to_csv(out_pulled, index=False)
        # Compiled history (unique keys), in addition to latest snapshots.
        existing_orders_all = _read_csv_if_exists(ORDERS_ALL_PATH)
        existing_items_all = _read_csv_if_exists(ITEMS_ALL_PATH)

        df_orders_all_in = df_orders.copy().fillna("").astype(str)
        df_items_all_in = df_items.copy().fillna("").astype(str)

        orders_all_count = _write_compiled_unique(
            ORDERS_ALL_PATH,
            existing_orders_all,
            df_orders_all_in,
            dedupe_key_cols=["amazon_order_id"],
            sort_cols=["purchase_date", "amazon_order_id"],
        )

        # Dedupe items using preferred key; do not persist helper column.
        df_items_all_in["_dedupe_key"] = _compiled_items_dedupe_key(df_items_all_in)
        if not existing_items_all.empty:
            existing_items_all = existing_items_all.copy()
            existing_items_all["_dedupe_key"] = _compiled_items_dedupe_key(existing_items_all)
        items_all_count = _write_compiled_unique(
            ITEMS_ALL_PATH,
            existing_items_all,
            df_items_all_in,
            dedupe_key_cols=["_dedupe_key"],
        )
        # Remove helper column from the stored CSV by rewriting without it.
        try:
            items_all_df = pd.read_csv(ITEMS_ALL_PATH, dtype=str).fillna("")
            if "_dedupe_key" in items_all_df.columns:
                items_all_df = items_all_df.drop(columns=["_dedupe_key"])
                items_all_df.to_csv(ITEMS_ALL_PATH, index=False)
        except Exception:
            pass
        snapshot_path = f"{out_orders};{out_items}"

        write_tab(sheet, ORDERS_TAB, df_orders)
        write_tab(sheet, ITEMS_TAB, df_items)
        # Write compiled views to sheet if available
        try:
            orders_all_df = pd.read_csv(ORDERS_ALL_PATH, dtype=str).fillna("")
            write_tab(sheet, ORDERS_ALL_TAB, orders_all_df)
        except Exception:
            pass
        try:
            items_all_df = pd.read_csv(ITEMS_ALL_PATH, dtype=str).fillna("")
            write_tab(sheet, ITEMS_ALL_TAB, items_all_df)
        except Exception:
            pass
        try:
            write_tab(sheet, LEVEL1_TAB, df_level1)
        except Exception:
            pass
        sheet_tabs_written = [ORDERS_TAB, ITEMS_TAB, LEVEL1_TAB]
    except Exception as exc:
        status = "error"
        alert = "error"
        last_error = str(exc)
        df_orders = pd.DataFrame()
        df_items = pd.DataFrame()

    ended_at = datetime.now(timezone.utc)
    duration_seconds = str(int((ended_at - started_at).total_seconds()))

    consecutive_failures = 0
    consecutive_successes = 0
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
    # Advance marker after successful fetch: max(last_update_date, purchase_date) from returned orders.
    new_marker = effective_created_after
    min_ts = None
    max_ts = None
    if status == "success":
        if not df_orders.empty:
            per_order_purchase: List[datetime] = []
            for _, r in df_orders.iterrows():
                pu = _parse_iso(str(r.get("purchase_date") or ""))
                if pu:
                    per_order_purchase.append(pu)
            if per_order_purchase:
                min_ts = min(per_order_purchase)
                max_ts = max(per_order_purchase)
                new_marker = _format_iso_z(max_ts)
                if not FORCE_FROM_MIDNIGHT and not SKIP_MARKER_WRITE:
                    save_marker(new_marker)
        # Visibility summary (even when 0 orders)
        print(
            {
                "pulled_count": int(len(df_orders)) if isinstance(df_orders, pd.DataFrame) else 0,
                "created_after_used": effective_created_after,
                "new_marker_saved": new_marker,
                "min_order_ts": _format_iso_z(min_ts) if isinstance(min_ts, datetime) else None,
                "max_order_ts": _format_iso_z(max_ts) if isinstance(max_ts, datetime) else None,
                "orders_all_count": orders_all_count if "orders_all_count" in locals() else None,
                "items_all_count": items_all_count if "items_all_count" in locals() else None,
            }
        )
    if status == "success" and failed_orders:
        alert = "partial"
        if last_error:
            last_error = f"{last_error};failed_orders={len(failed_orders)}"
        else:
            last_error = f"failed_orders={len(failed_orders)}"

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
        "",
        "",
        str(consecutive_failures),
        str(consecutive_successes),
        env_name,
        git_version,
        last_error,
    ]
    append_run_status(sheet, status_row)

    if failed_orders:
        FAILED_ORDERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        df_failed = pd.DataFrame(
            {
                "order_id": failed_orders,
                "timestamp": [ended_at.isoformat()] * len(failed_orders),
                "source": ["B001"] * len(failed_orders),
            }
        )
        df_failed.to_csv(
            FAILED_ORDERS_PATH,
            mode="a",
            index=False,
            header=not FAILED_ORDERS_PATH.exists(),
        )

    try:
        _save_retry_queue(retry_df)
    except Exception as exc:
        log(f"retry queue save failed: {exc}")

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


if __name__ == "__main__":
    main()
