"""
Backfill Level 2 data for orders missing Level 2 rows and re-check pending orders.

Rules:
- Primary source: compiled orders/items CSVs from B001 (out/orders_all.csv and out/order_items_all.csv).
- Processes missing/pending orders in purchase_date order.
- Always refetch items via SP-API for missing/pending orders; cached items are fallback only.
- Records only official item amounts (price/tax/shipping/gift/promo); no fee estimation.
- Writes snapshots after each processed order so progress is durable; Level_2_Official sheet accumulates.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import gspread
import requests
import pandas as pd
import csv
from gspread.exceptions import APIError
from decimal import Decimal, ROUND_HALF_UP, ROUND_UP

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api.get_orders import (  # noqa: E402
    get_lwa_access_token,
    list_order_items,
    load_dotenv_if_missing,
)

SHEET_ID = "1BHueJTk4dvvhIXypzh6i2hQTgc0pB3DWj2khQ2IT6_A"
PRODUCT_DB_SHEET_ID = os.environ.get("PRODUCT_DB_SHEET_ID", "1b7iREy92vF_a1Lw72g0SOGS7t4-IOSBeeoHetLTN43s")
PRODUCT_DB_TAB = "Product_DB"
ORDERS_TAB = "Orders_updates"
ITEMS_TAB = "OrderItems_updates"
LEVEL2_TAB = "Level_2_Official"
MAX_RETRIES = int(os.environ.get("ORDERS_MAX_RETRIES", "3"))
SLEEP_SEC = float(os.environ.get("ORDERS_SLEEP_SEC", "2.0"))
SHEETS_MAX_RETRIES = 5
SHEETS_BACKOFF_SEC = 2.0
SHEETS_MAX_CELLS = 10_000_000
MARKETPLACE_ID = os.environ.get("MARKETPLACE_ID", "A1F83G8C2ARO7P")
ORDERS_ALL = Path("out/orders_all.csv")
ITEMS_ALL = Path("out/order_items_all.csv")
LEVEL2_CSV = Path("out/financial_events_level2.csv")
LEVEL3_OFFICIAL_CSV = Path("out/financial_events_level3_official.csv")
PRODUCT_DB_PATH = Path("out/product_db_preview.csv")
REFRESH_PRODUCT_DB = os.environ.get("REFRESH_PRODUCT_DB", "1") == "1"
FX_RATES_PATH = Path("out/fx_rates_daily.csv")
VAT_DEFAULT = 0.2
UK_MARKETPLACE_ID = "A1F83G8C2ARO7P"
EU_MARKETPLACE_IDS = {
    "A28R8C7NBKEWEA",  # IE
    "A1PA6795UKMFR9",  # DE
    "A1RKKUPIHCS9HS",  # ES
    "A13V1IB3VIYZZH",  # FR
    "A1F83G8C2ARO7P",  # UK (keep in VAT markets)
    "A1805IZSGTT6HS",  # NL
    "A1C3SOZRARQ6R3",  # PL
    "A2NODRKZP88ZB9",  # SE
    "A1ZFFQZ3HTUKT9",  # FR (Non-Amazon)
}
MARKET_VAT_RATES = {
    "A1F83G8C2ARO7P": 0.20,  # UK
    "A28R8C7NBKEWEA": 0.23,  # IE
    "A13V1IB3VIYZZH": 0.20,  # FR
    "A1PA6795UKMFR9": 0.19,  # DE
    "A1RKKUPIHCS9HS": 0.21,  # ES
    "A1805IZSGTT6HS": 0.21,  # NL
    "A1C3SOZRARQ6R3": 0.23,  # PL
    "A2NODRKZP88ZB9": 0.25,  # SE
    "A1ZFFQZ3HTUKT9": 0.20,  # FR (Non-Amazon)
}
MIN_REFERRAL_FEE = 0.25  # GBP minimum fee
PRODUCT_DB: Dict[str, Dict[str, str]] = {}
FORCE_PENDING_API = os.environ.get("B002_FORCE_PENDING_API", "1") == "1"
B002_SKIP_MISSING = os.environ.get("B002_SKIP_MISSING", "0") == "1"
B002_DEDUPE_ONLY = os.environ.get("B002_DEDUPE_ONLY", "0") == "1"
PENDING_STATUSES = {"pending", "unshipped", "partiallyshipped"}
PENDING_MIN_AGE_HOURS = float(os.environ.get("B002_PENDING_MIN_AGE_HOURS", "12"))
B002_MIN_AGE_HOURS = float(os.environ.get("B002_MIN_AGE_HOURS", "12"))
B002_MAX_ORDERS = int(os.environ.get("B002_MAX_ORDERS", "0"))  # 0 = no limit
B002_MAX_SECONDS = int(os.environ.get("B002_MAX_SECONDS", "0"))  # 0 = no limit
B002_LIGHT = os.environ.get("B002_LIGHT", "1") == "1"  # avoid full Level2 read/write
FAILED_ORDERS_PATH = Path("out/pending_orders_failed.csv")
ITEMS_MERGE_SUMMARY_PATH = Path("out/orders_items_recovery_merge_summary.csv")
FX_API_URL = "https://api.frankfurter.app"
FX_API_URL_FALLBACK_LATEST = "https://open.er-api.com/v6/latest/EUR"
_FX_CACHE: Dict[Tuple[str, str], float] = {}


def _compiled_items_dedupe_key(df_items: pd.DataFrame) -> pd.Series:
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


def _write_compiled_unique(
    path: Path,
    existing: pd.DataFrame,
    incoming: pd.DataFrame,
    dedupe_key_cols: list[str],
) -> int:
    if existing.empty:
        out = incoming.copy()
    else:
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
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)
    return len(out)


def _merge_recovered_items_into_items_all(df_items: pd.DataFrame) -> Dict[str, int]:
    if df_items is None or df_items.empty:
        return {"incoming_rows": 0, "before_rows": 0, "after_rows": 0}
    incoming = df_items.copy().fillna("").astype(str)
    incoming["_dedupe_key"] = _compiled_items_dedupe_key(incoming)
    existing = pd.read_csv(ITEMS_ALL, dtype=str).fillna("") if ITEMS_ALL.exists() else pd.DataFrame()
    before_rows = int(len(existing.index))
    if not existing.empty:
        existing = existing.copy()
        existing["_dedupe_key"] = _compiled_items_dedupe_key(existing)
    after_rows = _write_compiled_unique(
        ITEMS_ALL,
        existing,
        incoming,
        dedupe_key_cols=["_dedupe_key"],
    )
    # Keep archive schema stable: remove helper column before returning.
    try:
        cleaned = pd.read_csv(ITEMS_ALL, dtype=str).fillna("")
        if "_dedupe_key" in cleaned.columns:
            cleaned = cleaned.drop(columns=["_dedupe_key"])
            cleaned.to_csv(ITEMS_ALL, index=False)
            after_rows = int(len(cleaned.index))
    except Exception:
        pass
    return {
        "incoming_rows": int(len(incoming.index)),
        "before_rows": before_rows,
        "after_rows": int(after_rows),
    }


def _append_items_merge_summary(row: Dict[str, str]) -> None:
    fields = [
        "timestamp_utc",
        "incoming_rows",
        "before_rows",
        "after_rows",
        "incoming_order_ids",
    ]
    payload = {k: str(row.get(k, "")).strip() for k in fields}
    payload["timestamp_utc"] = payload.get("timestamp_utc", "") or datetime.now(timezone.utc).isoformat()
    ITEMS_MERGE_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    need_header = not ITEMS_MERGE_SUMMARY_PATH.exists() or ITEMS_MERGE_SUMMARY_PATH.stat().st_size == 0
    with ITEMS_MERGE_SUMMARY_PATH.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if need_header:
            writer.writeheader()
        writer.writerow(payload)


def get_gspread_client() -> gspread.Client:
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        cred_path = str(Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=cred_path)


def write_tab(sheet: gspread.Spreadsheet, tab_name: str, df: pd.DataFrame) -> None:
    payload = [list(df.columns)] + df.fillna("").astype(str).values.tolist()
    try:
        ws = sheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=tab_name, rows=max(len(payload) + 10, 2000), cols=max(len(df.columns) + 5, 40))
    else:
        ws.clear()
    ws.update(range_name="A1", values=payload)


def write_tab_chunked(sheet: gspread.Spreadsheet, tab_name: str, df: pd.DataFrame, batch_size: int = 500) -> None:
    rows = [list(df.columns)] + df.fillna("").astype(str).values.tolist()
    try:
        ws = sheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=tab_name, rows=max(len(rows) + 10, 2000), cols=max(len(df.columns) + 5, 40))
    else:
        # Ensure grid is large enough for the incoming write.
        rows_needed = len(rows)
        cols_needed = max(len(df.columns), 1)
        if rows_needed * cols_needed > SHEETS_MAX_CELLS:
            print({"status": "warning", "alert": "sheet_cells_limit", "tab": tab_name, "rows": rows_needed, "cols": cols_needed})
            return
        if ws.row_count < rows_needed or ws.col_count < cols_needed:
            print({"status": "warning", "alert": "sheet_grid_too_small", "tab": tab_name, "rows": rows_needed, "cols": cols_needed})
            return
        ws.clear()
    # Write header
    ws.update(range_name="A1", values=[rows[0]])
    # Write in chunks
    for i in range(1, len(rows), batch_size):
        chunk = rows[i : i + batch_size]
        start_row = i + 1
        ws.update(range_name=f"A{start_row}", values=chunk)


def _backfill_fees_from_level3(level2: pd.DataFrame) -> pd.DataFrame:
    if level2.empty or not LEVEL3_OFFICIAL_CSV.exists():
        return level2
    try:
        level3 = pd.read_csv(LEVEL3_OFFICIAL_CSV, dtype=str).fillna("")
    except Exception:
        return level2
    if level3.empty:
        return level2
    fee_cols = [
        "FBA_Fee_Total",
        "FBA_Fee_VAT",
        "FBA_Fee_ExVAT",
        "Commission_Total",
        "Commission_VAT",
        "Commission_ExVAT",
        "Digital_Fee_Total",
        "Digital_Fee_VAT",
        "Digital_Fee_ExVAT",
        "FixedClosingFee_Total",
        "FixedClosingFee_VAT",
        "FixedClosingFee_ExVAT",
    ]
    keep_cols = ["Order ID", "SKU"] + [c for c in fee_cols if c in level3.columns]
    level3 = level3[keep_cols].copy()
    merged = level2.merge(level3, on=["Order ID", "SKU"], how="left", suffixes=("", "_lvl3"))
    for col in fee_cols:
        lvl3_col = f"{col}_lvl3"
        if lvl3_col not in merged.columns or col not in merged.columns:
            continue
        # Ensure compatible dtype for assignment (CSV writes are string-based).
        merged[col] = merged[col].astype(object)
        merged[lvl3_col] = merged[lvl3_col].astype(object)
        has_lvl3 = ~merged[lvl3_col].astype(str).str.strip().isin(["", "nan", "None"])
        # When Level 3 exists, it is the source of truth for fee fields.
        merged.loc[has_lvl3, col] = merged.loc[has_lvl3, lvl3_col]
    drop_cols = [c for c in merged.columns if c.endswith("_lvl3")]
    return merged.drop(columns=drop_cols, errors="ignore")


def _col_letter(idx: int) -> str:
    # 1-based index to column letter
    letters = ""
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def update_level2_dsf_only(sheet: gspread.Spreadsheet, df: pd.DataFrame, batch_size: int = 500) -> None:
    if df.empty:
        return
    try:
        ws = sheet.worksheet(LEVEL2_TAB)
    except gspread.WorksheetNotFound:
        # Fallback to full write if sheet missing
        write_tab_chunked(sheet, LEVEL2_TAB, df, batch_size=batch_size)
        return
    # Find DSF column positions
    header = ws.row_values(1)
    if not header:
        write_tab_chunked(sheet, LEVEL2_TAB, df, batch_size=batch_size)
        return
    col_map = {name: i + 1 for i, name in enumerate(header)}
    required = ["Digital_Fee_Total", "Digital_Fee_VAT", "Digital_Fee_ExVAT"]
    if not all(c in col_map for c in required):
        write_tab_chunked(sheet, LEVEL2_TAB, df, batch_size=batch_size)
        return

    rows_needed = len(df) + 1
    cols_needed = max(col_map[c] for c in required)
    if rows_needed * cols_needed > SHEETS_MAX_CELLS:
        print({"status": "warning", "alert": "sheet_cells_limit", "tab": LEVEL2_TAB, "rows": rows_needed, "cols": cols_needed})
        return
    if ws.row_count < rows_needed or ws.col_count < cols_needed:
        print({"status": "warning", "alert": "sheet_grid_too_small", "tab": LEVEL2_TAB, "rows": rows_needed, "cols": cols_needed})
        return

    # Build DSF values aligned to existing row order (assumes same ordering as CSV)
    dsf_vals = df[required].fillna("").astype(str).values.tolist()
    start_row = 2
    for i in range(0, len(dsf_vals), batch_size):
        chunk = dsf_vals[i : i + batch_size]
        row_start = start_row + i
        row_end = row_start + len(chunk) - 1
        start_col = col_map["Digital_Fee_Total"]
        end_col = col_map["Digital_Fee_ExVAT"]
        rng = f"{_col_letter(start_col)}{row_start}:{_col_letter(end_col)}{row_end}"
        ws.update(range_name=rng, values=chunk)


def _parse_iso(val: str) -> Optional[datetime]:
    try:
        if not val:
            return None
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except Exception:
        return None


def round_half_up(value: float, ndigits: int = 2) -> float:
    try:
        quant = Decimal("1").scaleb(-ndigits)
        return float(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP))
    except Exception:
        return round(value, ndigits)


def round_up(value: float, ndigits: int = 2) -> float:
    try:
        quant = Decimal("1").scaleb(-ndigits)
        return float(Decimal(str(value)).quantize(quant, rounding=ROUND_UP))
    except Exception:
        return round(value, ndigits)


def _recalc_promo_vat_level2(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    for col in ["Promotion_Total", "Promotion_VAT", "Promotion_ExVAT", "Quantity Ordered", "Price_VAT", "Price_ExVAT"]:
        if col not in df.columns:
            df[col] = ""

    def _calc(row: pd.Series) -> pd.Series:
        try:
            promo_total = float(str(row.get("Promotion_Total") or "").strip() or 0.0)
        except Exception:
            promo_total = 0.0
        if promo_total == 0.0:
            return row
        try:
            qty_val = float(str(row.get("Quantity Ordered") or "").strip() or 1.0)
        except Exception:
            qty_val = 1.0
        if qty_val <= 0:
            qty_val = 1.0
        # Derive VAT rate from price when available.
        vat_rate_item = VAT_DEFAULT
        try:
            price_vat = float(str(row.get("Price_VAT") or "").strip() or 0.0)
            price_ex = float(str(row.get("Price_ExVAT") or "").strip() or 0.0)
            if price_ex > 0 and price_vat != 0:
                vat_rate_item = price_vat / price_ex
        except Exception:
            vat_rate_item = VAT_DEFAULT
        unit_total = promo_total / qty_val
        vat_unit = round_up(unit_total * vat_rate_item, 2)
        vat_total = round_up(vat_unit * qty_val, 2)
        ex_val = round_up(promo_total - vat_total, 2)
        row["Promotion_VAT"] = f"{vat_total:.2f}"
        row["Promotion_ExVAT"] = f"{ex_val:.2f}"
        return row

    return df.apply(_calc, axis=1)

def round_up(value: float, ndigits: int = 2) -> float:
    try:
        quant = Decimal("1").scaleb(-ndigits)
        return float(Decimal(str(value)).quantize(quant, rounding=ROUND_UP))
    except Exception:
        return round(value, ndigits)


def _fx_date_key(val: str) -> str:
    try:
        return pd.to_datetime(val, errors="coerce", utc=True).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _load_fx_rates() -> None:
    if _FX_CACHE:
        return
    if not FX_RATES_PATH.exists():
        return
    try:
        df = pd.read_csv(FX_RATES_PATH, dtype=str)
    except Exception:
        return
    if df.empty:
        return
    for _, r in df.iterrows():
        d = str(r.get("date") or "")
        c = str(r.get("currency") or "")
        try:
            rate = float(r.get("rate_to_gbp") or "")
        except Exception:
            continue
        if d and c:
            _FX_CACHE[(d, c)] = rate


def _fetch_rate_to_gbp(date_str: str, currency: str) -> Optional[float]:
    if not date_str or not currency:
        return None
    if currency == "GBP":
        return 1.0
    params = {"from": "EUR", "to": f"GBP,{currency}"}
    url = f"{FX_API_URL}/{date_str}"
    resp = requests.get(url, params=params, timeout=30)
    if resp.status_code == 200:
        payload = resp.json() or {}
        rates = payload.get("rates") or {}
        try:
            gbp_rate = float(rates.get("GBP"))
        except Exception:
            gbp_rate = None
        if gbp_rate is not None:
            try:
                cur_rate = 1.0 if currency == "EUR" else float(rates.get(currency))
            except Exception:
                cur_rate = None
            if cur_rate:
                return gbp_rate / cur_rate
    # Fallback: latest EUR rates (not date-specific)
    resp = requests.get(FX_API_URL_FALLBACK_LATEST, timeout=30)
    if resp.status_code != 200:
        return None
    payload = resp.json() or {}
    rates = payload.get("rates") or {}
    try:
        gbp_rate = float(rates.get("GBP"))
    except Exception:
        gbp_rate = None
    if gbp_rate is None:
        return None
    try:
        cur_rate = 1.0 if currency == "EUR" else float(rates.get(currency))
    except Exception:
        cur_rate = None
    if cur_rate:
        return gbp_rate / cur_rate
    return None


def _rate_to_gbp(date_str: str, currency: str) -> Optional[float]:
    _load_fx_rates()
    key = (date_str, currency)
    if key in _FX_CACHE:
        return _FX_CACHE[key]
    rate = _fetch_rate_to_gbp(date_str, currency)
    if rate is None:
        return None
    _FX_CACHE[key] = rate
    try:
        FX_RATES_PATH.parent.mkdir(parents=True, exist_ok=True)
        row = pd.DataFrame(
            [
                {
                    "date": date_str,
                    "currency": currency,
                    "rate_to_gbp": f"{rate:.8f}",
                    "source": "B002",
                    "fx_date_used": date_str,
                }
            ]
        )
        if FX_RATES_PATH.exists() and FX_RATES_PATH.stat().st_size > 0:
            row.to_csv(FX_RATES_PATH, mode="a", header=False, index=False)
        else:
            row.to_csv(FX_RATES_PATH, index=False)
    except Exception:
        pass
    return rate


def _convert_gbp_to_currency(amount_gbp: float, date_str: str, currency: str) -> float:
    if currency == "GBP":
        return amount_gbp
    rate_to_gbp = _rate_to_gbp(date_str, currency)
    if not rate_to_gbp:
        return amount_gbp
    return amount_gbp / rate_to_gbp


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


LEVEL2_COLUMNS = [
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


def build_level2(df_orders: pd.DataFrame, df_items: pd.DataFrame) -> pd.DataFrame:
    if df_items.empty:
        return pd.DataFrame(columns=LEVEL2_COLUMNS)
    merged = df_items.merge(
        df_orders[["amazon_order_id", "purchase_date", "order_status", "marketplace_id"]] if "amazon_order_id" in df_orders.columns else df_orders,
        on="amazon_order_id",
        how="left",
    )
    rows = []
    for _, r in merged.iterrows():
        price_total = r.get("item_price_amount", "")
        price_vat = r.get("item_tax_amount", "")
        order_currency = r.get("item_price_currency", "") or r.get("shipping_price_currency", "") or r.get("order_total_currency", "")
        order_date = _fx_date_key(r.get("purchase_date", ""))
        status = str(r.get("order_status", "")).strip().lower()
        qty_raw = r.get("quantity_ordered", "")
        qty_val = 1.0
        try:
            qraw = qty_raw or 1
            qty_val = float(qraw)
        except Exception:
            qty_val = 1.0
        is_canceled = status == "canceled" or qty_val <= 0
        price_ex = ""
        try:
            if price_total not in ("", None) and price_vat not in ("", None):
                price_ex = f"{float(price_total) - float(price_vat):.2f}"
        except Exception:
            price_ex = ""

        def _calc_parts(total_key: str, vat_key: str) -> Tuple[str, str, str]:
            total_val = r.get(total_key, "")
            vat_val = r.get(vat_key, "")
            ex = ""
            try:
                if total_val not in ("", None) and vat_val not in ("", None):
                    ex = f"{float(total_val) - float(vat_val):.2f}"
            except Exception:
                ex = ""
            return (
                f"{float(total_val):.2f}" if total_val not in ("", None, "") and str(total_val) != "" else "",
                f"{float(vat_val):.2f}" if vat_val not in ("", None, "") and str(vat_val) != "" else "",
                ex,
            )

        ship_total, ship_vat, ship_ex = _calc_parts("shipping_price_amount", "shipping_tax_amount")
        gift_total, gift_vat, gift_ex = _calc_parts("giftwrap_price_amount", "giftwrap_tax_amount")
        promo_total, promo_vat, promo_ex = _calc_parts("promotion_discount_amount", "promotion_discount_tax_amount")

        market_id = r.get("marketplace_id", "")
        is_uk = market_id == UK_MARKETPLACE_ID
        is_eu = market_id in EU_MARKETPLACE_IDS and not is_uk
        is_vat_market = is_uk or is_eu

        # VAT rates: item vs market (shipping/gift/promo/fees)
        vat_rate_market = MARKET_VAT_RATES.get(market_id, VAT_DEFAULT) if is_vat_market else 0.0
        vat_rate_item = vat_rate_market
        try:
            if price_total not in ("", None) and price_vat not in ("", None):
                ex_tmp = float(price_total) - float(price_vat)
                if ex_tmp > 0 and float(price_vat) > 0:
                    vat_rate_item = float(price_vat) / ex_tmp
        except Exception:
            vat_rate_item = vat_rate_market

        def _estimate_vat_from_rate(total_str: str, vat_str: str, ex_str: str) -> Tuple[str, str]:
            if total_str in ("", None) or str(total_str).strip() == "":
                return vat_str, ex_str
            vat_str_clean = str(vat_str).strip() if vat_str is not None else ""
            if vat_str_clean not in ("", "0", "0.0", "0.00"):
                return vat_str, ex_str
            try:
                total_val = float(total_str)
            except Exception:
                return vat_str, ex_str
            if total_val == 0:
                return "0.00", "0.00"
            try:
                vat_val = round_half_up(total_val * vat_rate_item / (1.0 + vat_rate_item), 2)
            except Exception:
                vat_val = 0.0
            ex_val = round_half_up(total_val - vat_val, 2)
            return f"{vat_val:.2f}", f"{ex_val:.2f}"

        def _estimate_promo_vat(total_str: str, vat_str: str, ex_str: str, qty: float) -> Tuple[str, str]:
            if total_str in ("", None) or str(total_str).strip() == "":
                return vat_str, ex_str
            vat_str_clean = str(vat_str).strip() if vat_str is not None else ""
            if vat_str_clean not in ("", "0", "0.0", "0.00"):
                return vat_str, ex_str
            try:
                total_val = float(total_str)
            except Exception:
                return vat_str, ex_str
            if total_val == 0:
                return "0.00", "0.00"
            qty_val = qty if qty and qty > 0 else 1.0
            try:
                unit_total = total_val / qty_val
                vat_unit = round_up(unit_total * vat_rate_item, 2)
                vat_val = round_up(vat_unit * qty_val, 2)
            except Exception:
                vat_val = 0.0
            ex_val = round_up(total_val - vat_val, 2)
            return f"{vat_val:.2f}", f"{ex_val:.2f}"

        def _estimate_vat_from_ex(ex_str: str, vat_str: str) -> Tuple[str, str, str]:
            if ex_str in ("", None) or str(ex_str).strip() == "":
                return ex_str, vat_str, ex_str
            vat_str_clean = str(vat_str).strip() if vat_str is not None else ""
            try:
                ex_val = float(ex_str)
            except Exception:
                return ex_str, vat_str, ex_str
            if vat_str_clean in ("", "0", "0.0", "0.00"):
                try:
                    vat_val = round_half_up(ex_val * vat_rate_item, 2)
                except Exception:
                    vat_val = 0.0
            else:
                try:
                    vat_val = float(vat_str)
                except Exception:
                    vat_val = 0.0
            total_val = round_half_up(ex_val + vat_val, 2)
            return f"{total_val:.2f}", f"{vat_val:.2f}", f"{ex_val:.2f}"

        # Load fee data from product DB if present
        sku = r.get("seller_sku", "")
        fba_ex = ""
        fba_vat = ""
        fba_total = ""
        comm_ex = ""
        comm_vat = ""
        comm_total = ""
        dsf_ex = ""
        dsf_vat = ""
        dsf_total = ""

        fee_row = PRODUCT_DB.get(sku, {}) if PRODUCT_DB else {}
        fee_10 = fee_row.get("fba_fee_10")
        fee_100 = fee_row.get("fba_fee_100")
        fee_override_10 = fee_row.get("last_fba_fee_ex_vat_10")
        fee_override_100 = fee_row.get("last_fba_fee_ex_vat_100")
        fee_override = fee_row.get("last_fba_fee_ex_vat")
        ref_10 = fee_row.get("referral_fee_10")
        ref_100 = fee_row.get("referral_fee_100")
        ref_fallback = fee_row.get("last_commission_pct")
        ref_band_10 = fee_row.get("last_commission_pct_10")
        ref_band_100 = fee_row.get("last_commission_pct_100")
        market_id = r.get("marketplace_id", "")
        if is_vat_market:
            price_vat, price_ex = _estimate_vat_from_rate(price_total, price_vat, price_ex)
            # Use item VAT rate for shipping/gift/promo when available.
            # Shipping amount from Orders API is inconsistent: if tax is present, total is gross;
            # if tax is missing, treat total as ex-VAT and add VAT on top.
            ship_vat_clean = str(ship_vat).strip() if ship_vat is not None else ""
            if ship_vat_clean not in ("", "0", "0.0", "0.00"):
                try:
                    ship_ex_val = float(ship_total) - float(ship_vat)
                    ship_ex = f"{ship_ex_val:.2f}"
                except Exception:
                    ship_ex = ship_ex
            else:
                ship_total, ship_vat, ship_ex = _estimate_vat_from_ex(ship_total, ship_vat)
            gift_vat, gift_ex = _estimate_vat_from_rate(gift_total, gift_vat, gift_ex)
            promo_vat, promo_ex = _estimate_promo_vat(promo_total, promo_vat, promo_ex, qty_val)

        price_val = None
        try:
            price_val = float(price_total) if price_total not in ("", None, "") else None
        except Exception:
            price_val = None
        if qty_val <= 0:
            qty_val = 1.0
        unit_price_val = None
        if price_val is not None:
            try:
                unit_price_val = price_val / qty_val
            except Exception:
                unit_price_val = price_val

        # FBA fee selection (ex VAT) based on gross price bands (GB only)
        if is_uk and price_val is not None:
            selected_fee = None
            if unit_price_val is not None and unit_price_val <= 10 and fee_override_10 not in ("", None):
                selected_fee = fee_override_10
            elif unit_price_val is not None and unit_price_val > 10 and fee_override_100 not in ("", None):
                selected_fee = fee_override_100
            elif fee_override not in ("", None):
                selected_fee = fee_override
            elif fee_10 not in ("", None) and unit_price_val is not None and unit_price_val <= 10:
                selected_fee = fee_10
            elif fee_100 not in ("", None) and unit_price_val is not None and unit_price_val > 10:
                selected_fee = fee_100
            elif fee_10 not in ("", None):
                selected_fee = fee_10
            elif fee_100 not in ("", None):
                selected_fee = fee_100
            if selected_fee not in ("", None):
                try:
                    ex_fee_unit_gbp = float(selected_fee)
                    ex_fee_unit = _convert_gbp_to_currency(ex_fee_unit_gbp, order_date, order_currency or "GBP")
                    ex_fee_total = ex_fee_unit * qty_val
                    if not is_uk:
                        fee_vat_total = 0.0
                    else:
                        fee_vat_total = round_half_up(ex_fee_total * vat_rate_market, 2)
                    fba_ex = f"{-ex_fee_total:.2f}"
                    fba_vat = f"{-fee_vat_total:.2f}"
                    fba_total = f"{-round_half_up(ex_fee_total + fee_vat_total, 2):.2f}"
                except Exception:
                    pass

        # Commission: percent, ex VAT, min fee
        comm_ex_amt: Optional[float] = None
        if price_val is not None:
            selected_rate = None
            if ref_band_10 not in ("", None) and unit_price_val is not None and unit_price_val <= 10:
                selected_rate = ref_band_10
            elif ref_band_100 not in ("", None) and unit_price_val is not None and unit_price_val > 10:
                selected_rate = ref_band_100
            elif ref_fallback not in ("", None):
                selected_rate = ref_fallback
            elif ref_10 not in ("", None) and unit_price_val is not None and unit_price_val <= 10:
                selected_rate = ref_10
            elif ref_100 not in ("", None) and unit_price_val is not None and unit_price_val > 10:
                selected_rate = ref_100
            elif ref_10 not in ("", None):
                selected_rate = ref_10
            elif ref_100 not in ("", None):
                selected_rate = ref_100
            if selected_rate not in ("", None):
                try:
                    rate_val = float(selected_rate)
                    if rate_val > 1:
                        rate_val = rate_val / 100.0
                    # Per-unit rounding to match Amazon: compute per-unit fee, round, then scale by qty.
                    min_fee = _convert_gbp_to_currency(MIN_REFERRAL_FEE, order_date, order_currency or "GBP")
                    unit_gross = unit_price_val if unit_price_val is not None else (price_val / qty_val if qty_val else price_val)
                    per_unit_fee = unit_gross * rate_val
                    if per_unit_fee < min_fee:
                        per_unit_fee = min_fee
                    per_unit_fee = round_half_up(per_unit_fee, 2)
                    comm_ex_amt = per_unit_fee * qty_val
                    comm_vat_amt = round_half_up(comm_ex_amt * vat_rate_market, 2)
                    comm_ex = f"{-comm_ex_amt:.2f}"
                    comm_vat = f"{-comm_vat_amt:.2f}"
                    comm_total = f"{-(comm_ex_amt + comm_vat_amt):.2f}"
                except Exception:
                    pass

        # Digital Services Fee: UK-only estimate (2% of ex-VAT components, add VAT)
        if is_uk:
            try:
                fba_ex_amt = float(fba_ex) if fba_ex else 0.0
            except Exception:
                fba_ex_amt = 0.0
            comm_basis = abs(comm_ex_amt) if comm_ex_amt is not None else 0.0
            fba_basis = abs(fba_ex_amt)
            dsf_ex_total_val = round_half_up((comm_basis + fba_basis) * 0.02, 2)
            if dsf_ex_total_val > 0:
                dsf_vat_val = round_half_up(dsf_ex_total_val * vat_rate_market, 2)
                dsf_total_val = dsf_ex_total_val + dsf_vat_val
                dsf_ex = f"{-dsf_ex_total_val:.2f}"
                dsf_vat = f"{-dsf_vat_val:.2f}"
                dsf_total = f"{-dsf_total_val:.2f}"

        def _to_num(val: object) -> float:
            try:
                return float(val)
            except Exception:
                return 0.0

        margin_ex = ""
        margin_pct = ""
        try:
            rev_ex = _to_num(price_ex) + _to_num(ship_ex) + _to_num(gift_ex) + _to_num(promo_ex)
            fee_ex = abs(_to_num(fba_ex)) + abs(_to_num(comm_ex)) + abs(_to_num(dsf_ex))
            if rev_ex != 0:
                margin_val = rev_ex - fee_ex
                margin_ex = f"{margin_val:.2f}"
                margin_pct = f"{(margin_val / rev_ex * 100.0):.2f}"
        except Exception:
            margin_ex = ""
            margin_pct = ""

        if is_canceled:
            rows.append(
                {
                    "Date": r.get("purchase_date", ""),
                    "Order ID": r.get("amazon_order_id", ""),
                    "marketplace_id": r.get("marketplace_id", ""),
                    "SKU": r.get("seller_sku", ""),
                    "Quantity Ordered": qty_raw,
                    "Price_Total": "",
                    "Price_VAT": "",
                    "Price_ExVAT": "",
                    "Shipping_Total": "",
                    "Shipping_VAT": "",
                    "Shipping_ExVAT": "",
                    "Gift_Total": "",
                    "Gift_VAT": "",
                    "Gift_ExVAT": "",
                    "Promotion_Total": "",
                    "Promotion_VAT": "",
                    "Promotion_ExVAT": "",
                    "FBA_Fee_Total": "",
                    "FBA_Fee_VAT": "",
                    "FBA_Fee_ExVAT": "",
                    "Commission_Total": "",
                    "Commission_VAT": "",
                    "Commission_ExVAT": "",
                    "Digital_Fee_Total": "",
                    "Digital_Fee_VAT": "",
                    "Digital_Fee_ExVAT": "",
                    "Margin_ExVAT": "",
                    "Margin_Pct": "",
                }
            )
        else:
            rows.append(
                {
                    "Date": r.get("purchase_date", ""),
                    "Order ID": r.get("amazon_order_id", ""),
                    "marketplace_id": r.get("marketplace_id", ""),
                    "SKU": r.get("seller_sku", ""),
                    "Quantity Ordered": r.get("quantity_ordered", ""),
                    "Price_Total": f"{float(price_total):.2f}" if price_total not in ("", None) and str(price_total) != "" else "",
                    "Price_VAT": f"{float(price_vat):.2f}" if price_vat not in ("", None) and str(price_vat) != "" else "",
                    "Price_ExVAT": price_ex,
                    "Shipping_Total": ship_total,
                    "Shipping_VAT": ship_vat,
                    "Shipping_ExVAT": ship_ex,
                    "Gift_Total": gift_total,
                    "Gift_VAT": gift_vat,
                    "Gift_ExVAT": gift_ex,
                    "Promotion_Total": promo_total,
                    "Promotion_VAT": promo_vat,
                    "Promotion_ExVAT": promo_ex,
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
    df = pd.DataFrame(rows, columns=LEVEL2_COLUMNS)
    # Drop rows with no monetary data at all
    money_cols = [
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
    ]
    df["__has_value"] = df[money_cols].apply(
        lambda s: any(str(v).strip() not in ("", "nan", "None") for v in s), axis=1
    )
    # Keep cancelled/zero-qty rows even if they have no monetary values.
    df["__status"] = merged["order_status"].astype(str).str.lower().values
    df["__qty_raw"] = merged["quantity_ordered"].astype(str).values
    df["__is_canceled"] = df["__status"].eq("canceled") | df["__qty_raw"].isin(["0", "0.0"])
    df = df[(df["__has_value"]) | (df["__is_canceled"])].drop(columns=["__has_value", "__status", "__qty_raw", "__is_canceled"])
    return df


def refresh_token_if_needed(current_token: str) -> str:
    try:
        return get_lwa_access_token()
    except Exception:
        return current_token


def fetch_items_with_retry(order_id: str, token: str) -> Tuple[List[Dict[str, object]], str]:
    items: List[Dict[str, object]] = []
    nt = None
    attempt = 0
    while attempt < MAX_RETRIES:
        attempt += 1
        try:
            nt = None
            while True:
                itm_batch, nt = list_order_items(access_token=token, amazon_order_id=order_id, next_token=nt)
                for it in itm_batch:
                    it["AmazonOrderId"] = order_id
                items.extend(itm_batch)
                if nt:
                    continue
                break
            return items, token
        except Exception as exc:
            message = str(exc).lower()
            if "unauthorized" in message or "invalid access token" in message or "expired" in message:
                token = refresh_token_if_needed(token)
            if attempt < MAX_RETRIES:
                time.sleep(SLEEP_SEC * attempt)
                continue
            raise
    return items, token


def write_tab_with_retry(sheet: gspread.Spreadsheet, tab_name: str, df: pd.DataFrame) -> None:
    if df is None:
        return
    payload = [list(df.columns)] + df.fillna("").astype(str).values.tolist()
    for attempt in range(1, SHEETS_MAX_RETRIES + 1):
        try:
            try:
                ws = sheet.worksheet(tab_name)
            except gspread.WorksheetNotFound:
                ws = sheet.add_worksheet(title=tab_name, rows=max(len(payload) + 10, 2000), cols=max(len(df.columns) + 5, 40))
            else:
                ws.clear()
            ws.update(range_name="A1", values=payload)
            return
        except APIError:
            if attempt == SHEETS_MAX_RETRIES:
                raise
            time.sleep(SHEETS_BACKOFF_SEC * attempt)


def append_tab_rows(sheet: gspread.Spreadsheet, tab_name: str, df: pd.DataFrame, batch_size: int = 500) -> None:
    if df is None or df.empty:
        return
    rows = df.fillna("").astype(str).values.tolist()
    try:
        ws = sheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        payload = [list(df.columns)] + rows
        ws = sheet.add_worksheet(title=tab_name, rows=max(len(payload) + 10, 2000), cols=max(len(df.columns) + 5, 40))
        ws.update(range_name="A1", values=payload)
        return
    col_a = ws.col_values(1)
    next_row = len(col_a) + 1
    if next_row == 1:
        ws.update(range_name="A1", values=[list(df.columns)])
        next_row = 2
    for i in range(0, len(rows), batch_size):
        chunk = rows[i : i + batch_size]
        ws.update(range_name=f"A{next_row + i}", values=chunk)

def export_product_db(sheet: gspread.Spreadsheet) -> None:
    """Dump Product_DB sheet to out/product_db_preview.csv."""
    try:
        ws = sheet.worksheet(PRODUCT_DB_TAB)
    except gspread.WorksheetNotFound:
        return
    rows = ws.get_all_values()
    if not rows:
        return
    PRODUCT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows[1:], columns=rows[0]).to_csv(PRODUCT_DB_PATH, index=False)


def refresh_product_db() -> None:
    if not REFRESH_PRODUCT_DB:
        return
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(PRODUCT_DB_SHEET_ID)
        export_product_db(sheet)
    except Exception:
        return


def update_product_db_last_sold(df_level2: pd.DataFrame) -> None:
    """Update Product_DB with last_sold_price from Level 2 actuals."""
    if df_level2.empty:
        return
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(PRODUCT_DB_SHEET_ID)
        ws = sheet.worksheet(PRODUCT_DB_TAB)
    except Exception:
        return

    prod_rows = ws.get_all_values()
    if not prod_rows:
        return
    headers = prod_rows[0]
    idx_map = {h: i for i, h in enumerate(headers)}
    required_cols = [
        "last_sold_price",
        "last_sold_price_currency",
        "last_sold_price_updated",
    ]
    for col in required_cols:
        if col not in idx_map:
            idx_map[col] = len(headers)
            headers.append(col)
            for row in prod_rows[1:]:
                while len(row) < len(headers):
                    row.append("")

    sku_idx = idx_map.get("seller_sku", -1)
    if sku_idx < 0:
        return
    sku_lookup = {}
    for i, row in enumerate(prod_rows[1:], start=1):
        if len(row) < len(headers):
            row.extend([""] * (len(headers) - len(row)))
        sku_val = row[sku_idx]
        if sku_val:
            sku_lookup[sku_val] = i

    df = df_level2.copy()
    df["__date"] = pd.to_datetime(df.get("Date"), errors="coerce")
    df = df[df["SKU"].astype(str).str.len() > 0]
    df = df[df["__date"].notna()]
    if df.empty:
        return
    df["__qty"] = pd.to_numeric(df.get("Quantity Ordered"), errors="coerce").fillna(1)
    df.loc[df["__qty"] <= 0, "__qty"] = 1
    df["__price_total"] = pd.to_numeric(df.get("Price_Total"), errors="coerce")
    df = df[df["__price_total"].notna()]
    df["__unit_price"] = (df["__price_total"] / df["__qty"]).round(2)
    df = df.sort_values(by=["SKU", "__date"])
    latest = df.groupby("SKU", as_index=False).tail(1)

    for _, r in latest.iterrows():
        sku = r.get("SKU", "")
        if sku not in sku_lookup:
            continue
        idx = sku_lookup[sku]
        row = prod_rows[idx]
        new_dt = r.get("__date")
        existing_dt = _parse_iso(row[idx_map["last_sold_price_updated"]]) if row[idx_map["last_sold_price_updated"]] else None
        if existing_dt and new_dt and new_dt <= existing_dt:
            continue
        row[idx_map["last_sold_price"]] = f"{r.get('__unit_price'):.2f}"
        existing_cur = row[idx_map["last_sold_price_currency"]]
        if not existing_cur:
            row[idx_map["last_sold_price_currency"]] = "GBP" if MARKETPLACE_ID == "A1F83G8C2ARO7P" else ""
        row[idx_map["last_sold_price_updated"]] = r.get("__date").strftime("%Y-%m-%dT%H:%M:%SZ")

    ws.clear()
    ws.update(range_name="A1", values=[headers] + prod_rows[1:])
    export_product_db(sheet)


def _dedupe_level2_csv() -> int:
    if not LEVEL2_CSV.exists():
        print({"status": "skip", "reason": "level2_missing"})
        return 0
    df = pd.read_csv(LEVEL2_CSV, dtype=str)
    if "Order ID" not in df.columns or "SKU" not in df.columns:
        print({"status": "error", "error": "missing_order_id_or_sku_cols"})
        return 0
    before = len(df)
    df = df.drop_duplicates(subset=["Order ID", "SKU"], keep="last")
    df.to_csv(LEVEL2_CSV, index=False)
    removed = before - len(df)
    print({"status": "success", "action": "dedupe_level2", "rows_before": before, "rows_after": len(df), "removed": removed})
    return removed


def main() -> None:
    load_dotenv_if_missing()
    token: Optional[str] = None
    if B002_DEDUPE_ONLY:
        _dedupe_level2_csv()
        return
    # Load product DB fee data
    global PRODUCT_DB
    refresh_product_db()
    PRODUCT_DB = {}
    if PRODUCT_DB_PATH.exists():
        try:
            pdf = pd.read_csv(PRODUCT_DB_PATH, dtype=str).fillna("")
            for _, row in pdf.iterrows():
                sku_key = row.get("seller_sku") or row.get("sku") or ""
                if not sku_key:
                    continue
                PRODUCT_DB[sku_key] = {
                    "fba_fee_10": row.get("fba_fee_10"),
                    "fba_fee_100": row.get("fba_fee_100"),
                    "last_fba_fee_ex_vat": row.get("last_fba_fee_ex_vat"),
                    "last_fba_fee_ex_vat_10": row.get("last_fba_fee_ex_vat_10"),
                    "last_fba_fee_ex_vat_100": row.get("last_fba_fee_ex_vat_100"),
                    "referral_fee_10": row.get("referral_fee_10"),
                    "referral_fee_100": row.get("referral_fee_100"),
                    "last_commission_pct": row.get("last_commission_pct"),
                    "last_commission_pct_10": row.get("last_commission_pct_10"),
                    "last_commission_pct_100": row.get("last_commission_pct_100"),
                    "vat_rate": row.get("vat_rate"),
                    "last_withheld_vat_flag": row.get("last_withheld_vat_flag"),
                }
        except Exception:
            PRODUCT_DB = {}
    started_at = datetime.now(timezone.utc)
    status = "success"
    alert = ""
    last_error = ""
    sheet_tabs_written: List[str] = []
    processed_orders = 0
    processed_items = 0
    failed_orders: List[str] = []
    processed_orders_rows: List[pd.DataFrame] = []
    processed_items_rows: List[pd.DataFrame] = []
    processed_level2_rows: List[pd.DataFrame] = []
    recovered_items_for_archive: List[pd.DataFrame] = []
    existing_items_order_ids: set[str] = set()
    try:
        # Determine orders missing Level 2 (order-based, not date-windowed)
        if not ORDERS_ALL.exists():
            print({"status": "success", "message": "orders_all.csv not found", "row_count": 0})
            return
        print("[B002] loading orders_all.csv ...")
        all_orders = pd.read_csv(ORDERS_ALL, dtype=str)
        print(f"[B002] orders_all rows: {len(all_orders)}")
        all_orders["purchase_date_dt"] = pd.to_datetime(all_orders.get("purchase_date"), errors="coerce")
        level2_accum = pd.DataFrame(columns=LEVEL2_COLUMNS)
        done_ids = set()
        if LEVEL2_CSV.exists():
            if B002_LIGHT:
                print("[B002] B002_LIGHT=1, reading Level2 Order IDs only ...")
                try:
                    for chunk in pd.read_csv(LEVEL2_CSV, dtype=str, usecols=["Order ID"], chunksize=200000):
                        done_ids.update(chunk["Order ID"].dropna().astype(str).tolist())
                except Exception:
                    done_ids = set()
                print(f"[B002] Level2 Order IDs loaded: {len(done_ids)}")
            else:
                print("[B002] loading full financial_events_level2.csv ...")
                try:
                    level2_accum = pd.read_csv(LEVEL2_CSV, dtype=str)
                except Exception:
                    level2_accum = pd.DataFrame(columns=LEVEL2_COLUMNS)
                if not level2_accum.empty:
                    money_cols = [
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
                    ]

                    def _has_money(row):
                        return any(str(row.get(c, "")).strip() not in ("", "nan", "None") for c in money_cols)

                    level2_accum = level2_accum[level2_accum.apply(_has_money, axis=1)]
                    level2_accum = _recalc_promo_vat_level2(level2_accum)
                    level2_accum = _backfill_fees_from_level3(level2_accum)
                    # Deduplicate to one row per Order ID + SKU (latest wins)
                    if "Order ID" in level2_accum.columns and "SKU" in level2_accum.columns:
                        level2_accum = level2_accum.drop_duplicates(subset=["Order ID", "SKU"], keep="last")
                # After cleaning, persist and recompute missing set
                level2_accum.to_csv(LEVEL2_CSV, index=False)
                done_ids = set(level2_accum.get("Order ID", []))
                print(f"[B002] Level2 rows after clean: {len(level2_accum)}")

        if B002_SKIP_MISSING:
            missing = all_orders.iloc[0:0].copy()
        else:
            missing = all_orders[~all_orders["amazon_order_id"].isin(done_ids)].copy()
        # Skip cancelled/zero-qty orders to avoid wasted runs
        if "order_status" in missing.columns:
            missing = missing[missing["order_status"].str.lower() != "canceled"]
        target = missing
        if FORCE_PENDING_API and "order_status" in all_orders.columns:
            pending = all_orders[all_orders["order_status"].str.lower().isin(PENDING_STATUSES)].copy()
            if "purchase_date_dt" in pending.columns:
                min_age = datetime.now(timezone.utc) - pd.Timedelta(hours=PENDING_MIN_AGE_HOURS)
                pending = pending[pending["purchase_date_dt"] <= min_age]
            target = pd.concat([target, pending], ignore_index=True).drop_duplicates(subset=["amazon_order_id"])
        # Global minimum age filter (skip very recent orders)
        if "purchase_date_dt" in target.columns and B002_MIN_AGE_HOURS > 0:
            min_age_all = datetime.now(timezone.utc) - pd.Timedelta(hours=B002_MIN_AGE_HOURS)
            target = target[target["purchase_date_dt"] <= min_age_all]
        if target.empty and not B002_SKIP_MISSING:
            print({"status": "success", "message": "no missing Level 2 orders", "row_count": 0})
            return
        target = target.sort_values(by="purchase_date_dt")
        print(f"[B002] target orders: {len(target)} (missing + pending)")
        if ITEMS_ALL.exists():
            try:
                item_ids_df = pd.read_csv(ITEMS_ALL, dtype=str, usecols=["amazon_order_id"]).fillna("")
                existing_items_order_ids = set(item_ids_df["amazon_order_id"].astype(str).str.strip())
            except Exception:
                existing_items_order_ids = set()

        started = datetime.now(timezone.utc)
        processed_count = 0
        for _, order_row in target.iterrows():
            if B002_MAX_ORDERS > 0 and processed_count >= B002_MAX_ORDERS:
                break
            if B002_MAX_SECONDS > 0:
                elapsed = (datetime.now(timezone.utc) - started).total_seconds()
                if elapsed >= B002_MAX_SECONDS:
                    break
            order_id = order_row.get("amazon_order_id", "")
            if processed_count % 10 == 0:
                print(f"[B002] processing {processed_count+1}/{len(target)} order_id={order_id}")

            # Always try fresh SP-API items; fallback to cached Level 1 if it fails
            items: List[Dict[str, object]] = []
            items_from_cache: pd.DataFrame = pd.DataFrame()
            if ITEMS_ALL.exists():
                try:
                    items_from_cache = pd.read_csv(ITEMS_ALL, dtype=str)
                    items_from_cache = items_from_cache[items_from_cache["amazon_order_id"] == order_id]
                except Exception:
                    items_from_cache = pd.DataFrame()

            used_cache = False
            try:
                if token is None:
                    token = get_lwa_access_token()
                items, token = fetch_items_with_retry(order_id, token)
                time.sleep(SLEEP_SEC)
            except Exception:
                if not items_from_cache.empty:
                    used_cache = True
                else:
                    failed_orders.append(order_id)
                    continue

            # Build frames for this order
            df_orders = order_row.to_frame().T
            df_orders = df_orders.drop(columns=["purchase_date_dt"], errors="ignore")
            if used_cache:
                df_items = items_from_cache.copy()
            else:
                df_items = flatten_items(items)
            if not used_cache and not df_items.empty and order_id and order_id not in existing_items_order_ids:
                recovered_items_for_archive.append(df_items.copy())
                existing_items_order_ids.add(order_id)
            if not df_items.empty:
                sort_cols = ["amazon_order_id", "order_item_id"] if "order_item_id" in df_items.columns else ["amazon_order_id"]
                df_items = df_items.sort_values(by=sort_cols, na_position="last")
            df_level2 = build_level2(df_orders, df_items)

            if not B002_LIGHT:
                if "Order ID" in level2_accum.columns and order_id:
                    level2_accum = level2_accum[level2_accum["Order ID"] != order_id]
                level2_accum = pd.concat([level2_accum, df_level2], ignore_index=True)
            else:
                processed_level2_rows.append(df_level2)
            processed_orders_rows.append(df_orders)
            processed_items_rows.append(df_items)
            processed_orders += len(df_orders)
            processed_items += len(df_items)
            processed_count += 1
        print(f"[B002] processed orders: {processed_orders} items: {processed_items}")

        # Write snapshots (this run) to disk for durability
        out_orders = Path("out/orders_pending_raw.csv")
        out_items = Path("out/order_items_pending_raw.csv")
        out_orders.parent.mkdir(parents=True, exist_ok=True)
        if processed_orders_rows:
            pd.concat(processed_orders_rows, ignore_index=True).to_csv(out_orders, index=False)
        if processed_items_rows:
            pd.concat(processed_items_rows, ignore_index=True).to_csv(out_items, index=False)
        merge_stats = {"incoming_rows": 0, "before_rows": 0, "after_rows": 0}
        if recovered_items_for_archive:
            merge_df = pd.concat(recovered_items_for_archive, ignore_index=True)
            merge_stats = _merge_recovered_items_into_items_all(merge_df)
            incoming_order_ids = (
                merge_df.get("amazon_order_id", pd.Series([], dtype=str))
                .astype(str)
                .str.strip()
            )
            incoming_order_count = int(incoming_order_ids[incoming_order_ids.ne("")].nunique())
            _append_items_merge_summary(
                {
                    "incoming_rows": str(merge_stats.get("incoming_rows", 0)),
                    "before_rows": str(merge_stats.get("before_rows", 0)),
                    "after_rows": str(merge_stats.get("after_rows", 0)),
                    "incoming_order_ids": str(incoming_order_count),
                }
            )
            print(
                {
                    "status": "info",
                    "stage": "merge_recovered_items_all",
                    "incoming_rows": merge_stats.get("incoming_rows", 0),
                    "before_rows": merge_stats.get("before_rows", 0),
                    "after_rows": merge_stats.get("after_rows", 0),
                    "incoming_order_ids": incoming_order_count,
                    "path": str(ITEMS_ALL),
                }
            )
        if B002_LIGHT and processed_level2_rows:
            new_level2 = pd.concat(processed_level2_rows, ignore_index=True)
            if "Order ID" in new_level2.columns and "SKU" in new_level2.columns:
                new_level2 = new_level2.drop_duplicates(subset=["Order ID", "SKU"], keep="last")
            LEVEL2_CSV.parent.mkdir(parents=True, exist_ok=True)
            if LEVEL2_CSV.exists() and LEVEL2_CSV.stat().st_size > 0:
                new_level2.to_csv(LEVEL2_CSV, mode="a", index=False, header=False)
            else:
                new_level2.to_csv(LEVEL2_CSV, index=False)
            # Ensure the on-disk Level2 stays unique across runs.
            _dedupe_level2_csv()
        if not B002_LIGHT:
            # Recompute DSF for any rows missing it using existing FBA/Commission ex VAT
            if not level2_accum.empty:
                for idx, row in level2_accum.iterrows():
                    if not B002_SKIP_MISSING and str(row.get("Digital_Fee_Total", "")).strip() not in ("", "nan", "None"):
                        continue
                    if str(row.get("marketplace_id", "")) != UK_MARKETPLACE_ID:
                        continue
                    try:
                        fba_ex_val = float(row.get("FBA_Fee_ExVAT", "") or 0.0)
                        comm_ex_val = float(row.get("Commission_ExVAT", "") or 0.0)
                        base_ex = abs(fba_ex_val) + abs(comm_ex_val)
                        if base_ex <= 0:
                            continue
                        dsf_ex_val = round_half_up(base_ex * 0.02, 2)
                        dsf_vat_val = round_half_up(dsf_ex_val * VAT_DEFAULT, 2)
                        dsf_total_val = dsf_ex_val + dsf_vat_val
                        level2_accum.at[idx, "Digital_Fee_ExVAT"] = f"{-dsf_ex_val:.2f}"
                        level2_accum.at[idx, "Digital_Fee_VAT"] = f"{-dsf_vat_val:.2f}"
                        level2_accum.at[idx, "Digital_Fee_Total"] = f"{-dsf_total_val:.2f}"
                    except Exception:
                        continue
            level2_accum.to_csv(LEVEL2_CSV, index=False)

        # Single Google Sheets write to avoid 429s
        client = get_gspread_client()
        sheet = client.open_by_key(SHEET_ID)
        if B002_SKIP_MISSING and not B002_LIGHT:
            update_level2_dsf_only(sheet, level2_accum)
            sheet_tabs_written = [LEVEL2_TAB]
        else:
            if processed_orders_rows:
                write_tab_with_retry(sheet, ORDERS_TAB, pd.concat(processed_orders_rows, ignore_index=True))
            if processed_items_rows:
                write_tab_with_retry(sheet, ITEMS_TAB, pd.concat(processed_items_rows, ignore_index=True))
            if B002_LIGHT:
                if processed_level2_rows:
                    append_tab_rows(sheet, LEVEL2_TAB, pd.concat(processed_level2_rows, ignore_index=True))
                sheet_tabs_written = [tab for tab in [ORDERS_TAB if processed_orders_rows else None, ITEMS_TAB if processed_items_rows else None, LEVEL2_TAB if processed_level2_rows else None] if tab]
            else:
                write_tab_with_retry(sheet, LEVEL2_TAB, level2_accum)
                sheet_tabs_written = [tab for tab in [ORDERS_TAB if processed_orders_rows else None, ITEMS_TAB if processed_items_rows else None, LEVEL2_TAB] if tab]
        if B002_LIGHT and processed_level2_rows:
            update_product_db_last_sold(pd.concat(processed_level2_rows, ignore_index=True))
        else:
            update_product_db_last_sold(level2_accum)

        print(
            {
                "pulled_orders": processed_orders,
                "items": processed_items,
                "failed_orders": failed_orders,
            }
        )
    except Exception as exc:
        status = "error"
        alert = "error"
        last_error = str(exc)
    ended_at = datetime.now(timezone.utc)
    if failed_orders:
        FAILED_ORDERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        df_failed = pd.DataFrame(
            {
                "order_id": failed_orders,
                "timestamp": [ended_at.isoformat()] * len(failed_orders),
                "source": ["B002"] * len(failed_orders),
            }
        )
        df_failed.to_csv(
            FAILED_ORDERS_PATH,
            mode="a",
            index=False,
            header=not FAILED_ORDERS_PATH.exists(),
        )
    print(
        {
            "timestamp": ended_at.isoformat(),
            "status": status,
            "alert": alert,
            "error": last_error,
            "row_count": processed_orders + processed_items,
            "columns": len(LEVEL2_COLUMNS),
            "sheet_tabs": sheet_tabs_written,
        }
    )


if __name__ == "__main__":
    main()


