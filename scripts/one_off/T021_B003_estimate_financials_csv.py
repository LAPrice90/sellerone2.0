"""
Phase-0 estimator (CSV-only): generate Estimated financial_events rows for orders lacking posted financials.

Inputs (read-only, all under out/):
- order_items_raw.csv: line-level order data (amazon_order_id, asin, seller_sku, quantity_ordered, item_price_amount, item_tax_amount, promotion_discount_amount, shipping_price_amount, shipping_tax_amount, currency, purchase_date).
- orders_raw.csv (optional): order-level fields (amazon_order_id, purchase_date, order_total_currency) to backfill purchase_date/currency.
- asin_snapshot.csv (optional): per-ASIN fee/price data (referral_fee, fba_fees, total_fees, price columns such as bb_price/foep_price/etc.).
- fee_estimate_cache.csv (optional): cached fee bands per SKU (sku, price_point, referral_rate, fba_fee).
- financial_events_raw.csv (optional): posted events; any order_id present here is skipped.

Outputs:
- financial_events_estimated.csv in out/: Estimated rows with is_estimate=1. No posted rows are touched.

Fee rules:
- Fees only if sourced from asin_snapshot or fee_estimate_cache.
- No guessed/synthesized fees (including DSF). If fees are missing, fee rows are omitted and marked missing in raw_json.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import gspread
import pandas as pd

OUT_DIR = Path("out")
ORDERS_PATH = OUT_DIR / "orders_raw.csv"
ITEMS_PATH = OUT_DIR / "order_items_raw.csv"
ASIN_SNAPSHOT_PATH = OUT_DIR / "asin_snapshot.csv"
FEE_CACHE_PATH = OUT_DIR / "fee_estimate_cache.csv"
POSTED_EVENTS_PATH = OUT_DIR / "financial_events_raw.csv"
OUTPUT_PATH = OUT_DIR / "financial_events_estimated.csv"
LEVEL1_OUTPUT_PATH = OUT_DIR / "financial_events_level1.csv"
SHEET_ID = "1BHueJTk4dvvhIXypzh6i2hQTgc0pB3DWj2khQ2IT6_A"
SHEET_TAB = "FinancialEvents_estimated"
SHEET_TAB_LEVEL1 = "Level_1_Immediate"
PRODUCT_DB_PREVIEW = OUT_DIR / "product_db_preview.csv"

VAT_DEFAULT = 0.20
PRICE_PRIORITY = [
    "bb_price",
    "foep_price",
    "competitive_price",
    "cpt_price",
    "comp_price",
    "was_price",
    "lowest_fba",
    "lowest_fbm",
    "price_estimate",
]


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def load_snapshot_map() -> Dict[str, Dict[str, Optional[float]]]:
    df = load_csv(ASIN_SNAPSHOT_PATH)
    if df.empty or "asin" not in df.columns:
        return {}
    fixed_fee_col = "fixed_closing_fee" if "fixed_closing_fee" in df.columns else None
    for col in df.columns:
        if col == "asin":
            continue
        df[col] = pd.to_numeric(df[col], errors="coerce")

    def _price_row(row: pd.Series) -> Optional[float]:
        for col in PRICE_PRIORITY:
            if col not in row:
                continue
            val = row.get(col)
            if pd.notna(val) and abs(val) > 1e-9:
                return float(val)
        return None

    snap: Dict[str, Dict[str, Optional[float]]] = {}
    for _, row in df.iterrows():
        asin = str(row.get("asin") or "")
        if not asin:
            continue
        snap[asin] = {
            "price_estimate": _price_row(row),
            "referral_fee": row.get("referral_fee"),
            "fba_fees": row.get("fba_fees"),
            "total_fees": row.get("total_fees"),
            "fixed_closing_fee": row.get(fixed_fee_col) if fixed_fee_col else None,
        }
    return snap


def load_fee_cache() -> Dict[str, List[Tuple[float, float, float]]]:
    df = load_csv(FEE_CACHE_PATH)
    if df.empty or "sku" not in df.columns:
        return {}
    cache: Dict[str, List[Tuple[float, float, float]]] = {}
    for _, row in df.iterrows():
        sku = str(row.get("sku") or "")
        pp = float(row.get("price_point") or 0.0)
        rr = float(row.get("referral_rate") or 0.0)
        ff = float(row.get("fba_fee") or 0.0)
        cache.setdefault(sku, []).append((pp, rr, ff))
    for sku in cache:
        cache[sku].sort(key=lambda x: x[0])
    return cache


def posted_orders() -> set[str]:
    df = load_csv(POSTED_EVENTS_PATH)
    if df.empty or "order_id" not in df.columns:
        return set()
    return set(str(x) for x in df["order_id"].dropna().unique())


def load_product_prices() -> Dict[str, Dict[str, Any]]:
    """
    Load Product_DB preview for live vs last_sold prices.
    Returns lookup by seller_sku; includes asin for secondary lookup.
    """
    df = load_csv(PRODUCT_DB_PREVIEW)
    if df.empty:
        return {}
    # Normalize columns
    cols = {
        "live_listing_price": "live_listing_price",
        "live_listing_price_currency": "live_listing_price_currency",
        "live_price_last_updated": "live_price_last_updated",
        "last_sold_price": "last_sold_price",
        "last_sold_price_currency": "last_sold_price_currency",
        "last_sold_price_updated": "last_sold_price_updated",
        "seller_sku": "seller_sku",
        "asin": "asin",
    }
    for c in cols.values():
        if c not in df.columns:
            df[c] = None
    df["live_listing_price"] = pd.to_numeric(df["live_listing_price"], errors="coerce")
    df["last_sold_price"] = pd.to_numeric(df["last_sold_price"], errors="coerce")
    def _parse_ts(val: Any) -> Optional[pd.Timestamp]:
        try:
            return pd.to_datetime(val)
        except Exception:
            return None
    df["live_price_last_updated"] = df["live_price_last_updated"].apply(_parse_ts)
    df["last_sold_price_updated"] = df["last_sold_price_updated"].apply(_parse_ts)

    lookup: Dict[str, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        sku = str(row.get("seller_sku") or "")
        if not sku:
            continue
        lookup[sku] = {
            "asin": str(row.get("asin") or ""),
            "live_price": row.get("live_listing_price"),
            "live_currency": row.get("live_listing_price_currency") or "",
            "live_updated": row.get("live_price_last_updated"),
            "last_sold_price": row.get("last_sold_price"),
            "last_sold_currency": row.get("last_sold_price_currency") or "",
            "last_sold_updated": row.get("last_sold_price_updated"),
        }
    return lookup


def last_price_by_sku(items: pd.DataFrame) -> Dict[str, float]:
    if items.empty or "seller_sku" not in items.columns:
        return {}
    candidates = items.copy()
    # Align common column names from B001/B002 raw exports
    price_col = "item_price_amount"
    if price_col not in candidates.columns and "item_price" in candidates.columns:
        price_col = "item_price"
    candidates[price_col] = pd.to_numeric(candidates.get(price_col), errors="coerce").fillna(0.0)
    if "purchase_date" in candidates.columns:
        candidates = candidates.sort_values("purchase_date")
    latest: Dict[str, float] = {}
    for _, row in candidates.iterrows():
        sku = str(row.get("seller_sku") or "")
        price = float(row.get(price_col) or 0.0)
        if price > 0:
            latest[sku] = price
    return latest


def _choose_cache_fee(
    cache: Dict[str, List[Tuple[float, float, float]]], sku: str, gross_unit_price: float
) -> Tuple[Optional[float], Optional[float]]:
    entries = cache.get(sku or "", [])
    if not entries:
        return None, None
    chosen = None
    for entry in entries:
        if entry[0] <= gross_unit_price:
            chosen = entry
    if chosen is None:
        chosen = entries[-1]
    referral_rate, fba_fee = None, None
    if chosen:
        _, rate, fee = chosen
        referral_rate = rate if rate is not None else None
        fba_fee = fee if fee is not None else None
    return referral_rate, fba_fee


def estimate_order(
    order_id: str,
    items: pd.DataFrame,
    snapshot_map: Dict[str, Dict[str, Optional[float]]],
    fee_cache: Dict[str, List[Tuple[float, float, float]]],
    last_price_map: Dict[str, float],
    product_prices: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    principal_total = 0.0
    tax_total = 0.0
    shipping_total = 0.0
    shipping_tax_total = 0.0
    giftwrap_total = 0.0
    giftwrap_tax_total = 0.0
    promo_total = 0.0
    currency = None
    posted_dt = None
    missing_fee_data = True
    fee_source_used = "missing_fee_data"
    price_source = "none"
    has_shipping = False

    # Common column fallbacks
    price_col = "item_price_amount" if "item_price_amount" in items.columns else "item_price"
    tax_col = "item_tax_amount" if "item_tax_amount" in items.columns else "item_tax"
    ship_col = "shipping_price_amount" if "shipping_price_amount" in items.columns else "shipping_price"
    ship_tax_col = "shipping_tax_amount" if "shipping_tax_amount" in items.columns else "shipping_tax"
    promo_col = "promotion_discount_amount" if "promotion_discount_amount" in items.columns else "promotion_discount"
    gift_col = "gift_wrap_price_amount" if "gift_wrap_price_amount" in items.columns else "giftwrap_price"
    gift_tax_col = "gift_wrap_tax_amount" if "gift_wrap_tax_amount" in items.columns else "giftwrap_tax"

    for _, row in items.iterrows():
        vat_rate = VAT_DEFAULT
        qty = float(row.get("quantity_ordered") or 0.0)
        item_price = float(row.get(price_col) or 0.0)
        item_tax = float(row.get(tax_col) or 0.0)
        ship_raw = float(row.get(ship_col) or 0.0)
        shipping_price = ship_raw
        shipping_tax = float(row.get(ship_tax_col) or 0.0)
        promo = float(row.get(promo_col) or 0.0)
        gift_price = float(row.get(gift_col) or 0.0)
        gift_tax = float(row.get(gift_tax_col) or 0.0)
        asin = str(row.get("asin") or "")
        sku = str(row.get("seller_sku") or "")
        currency = currency or row.get("item_price_currency") or row.get("order_total_currency") or row.get("currency")
        posted_dt = posted_dt or row.get("purchase_date")

        snap = snapshot_map.get(asin, {})
        price_est = snap.get("price_estimate")
        if item_price <= 0 and price_est is not None:
            gross = float(price_est)
            net = gross / (1 + vat_rate)
            item_price = net * max(qty, 1.0)
            item_tax = (gross - net) * max(qty, 1.0)
        elif abs(item_tax) < 1e-9 and item_price > 0:
            net = item_price / (1 + vat_rate)
            item_tax = item_price - net
            item_price = net

        if ship_raw > 0:
            if shipping_tax <= 0 and shipping_price > 0:
                net_ship = shipping_price / (1 + vat_rate)
                shipping_tax = shipping_price - net_ship
                shipping_price = net_ship
            has_shipping = True
        else:
            shipping_price = 0.0
            shipping_tax = 0.0

        if item_price <= 0 and price_est is None:
            # Stage 1 price choice: prefer live_listing vs last_sold based on timestamps
            pp = product_prices.get(sku) or product_prices.get(asin, {})
            chosen_price = None
            chosen_currency = ""
            if pp:
                live_price = pp.get("live_price")
                live_ts = pp.get("live_updated")
                sold_price = pp.get("last_sold_price")
                sold_ts = pp.get("last_sold_updated")
                if pd.notna(live_price) and (sold_ts is None or (live_ts and live_ts >= sold_ts)):
                    chosen_price = live_price
                    chosen_currency = pp.get("live_currency", "")
                    price_source = "live_listing"
                elif pd.notna(sold_price):
                    chosen_price = sold_price
                    chosen_currency = pp.get("last_sold_currency", "")
                    price_source = "last_sold"
            if chosen_price is None:
                last_price = last_price_map.get(sku)
                if last_price:
                    chosen_price = last_price
            if chosen_price is not None:
                gross = float(chosen_price)
                net = gross / (1 + vat_rate)
                item_price = net * max(qty, 1.0)
                item_tax = (gross - net) * max(qty, 1.0)
                if not currency and chosen_currency:
                    currency = chosen_currency

        principal_total += item_price
        tax_total += item_tax
        shipping_total += shipping_price
        shipping_tax_total += shipping_tax
        if gift_price > 0:
            if gift_tax <= 0:
                net_gw = gift_price / (1 + vat_rate)
                gift_tax = gift_price - net_gw
                gift_price = net_gw
            giftwrap_total += gift_price
            giftwrap_tax_total += gift_tax
        promo_total += promo

        gross_unit = 0.0
        if qty > 0:
            gross_unit = (item_price + item_tax + shipping_price + shipping_tax) / qty

        referral_fee = snap.get("referral_fee")
        fba_fee = snap.get("fba_fees")
        fixed_fee = snap.get("fixed_closing_fee")
        dsf_fee = None  # only if explicitly provided; no synthesis
        fee_source = None

        if any(val is not None for val in (referral_fee, fba_fee, fixed_fee)):
            fee_source = "asin_snapshot"
        if (referral_fee is None or fba_fee is None) and fee_cache:
            rate, fba_cached = _choose_cache_fee(fee_cache, sku, gross_unit)
            if referral_fee is None and rate is not None and gross_unit > 0:
                referral_fee = abs(rate if rate <= 1 else rate / 100.0) * gross_unit
                fee_source = fee_source or "fee_estimate_cache"
            if fba_fee is None and fba_cached is not None:
                fba_fee = fba_cached
                fee_source = fee_source or "fee_estimate_cache"

        def _add_fee(amount_type: str, amount_val: float, source: str) -> None:
            nonlocal missing_fee_data, fee_source_used
            missing_fee_data = False
            fee_source_used = source
            entries.append(
                {
                    "amount_type": amount_type,
                    "amount": round(-abs(amount_val), 2),
                    "transaction_type": "Estimated",
                    "amount_description": f"Estimated from {source}",
                    "data_level": "fee_estimated",
                }
            )

        if referral_fee is not None and referral_fee != 0:
            _add_fee("Commission", float(referral_fee) * max(qty, 1.0), fee_source or "unknown_fee_source")
            tax_amt = abs(referral_fee) * max(qty, 1.0) * VAT_DEFAULT
            entries.append(
                {
                    "amount_type": "CommissionTax",
                    "amount": round(-abs(tax_amt), 2),
                    "transaction_type": "Estimated",
                    "amount_description": f"VAT on Commission from {fee_source or 'unknown_fee_source'}",
                    "data_level": "fee_estimated",
                }
            )
        if fba_fee is not None and fba_fee != 0:
            _add_fee("FBAPerUnitFulfillmentFee", float(fba_fee) * max(qty, 1.0), fee_source or "unknown_fee_source")
            tax_amt = abs(fba_fee) * max(qty, 1.0) * VAT_DEFAULT
            entries.append(
                {
                    "amount_type": "FBAPerUnitFulfillmentFeeTax",
                    "amount": round(-abs(tax_amt), 2),
                    "transaction_type": "Estimated",
                    "amount_description": f"VAT on FBA fee from {fee_source or 'unknown_fee_source'}",
                    "data_level": "fee_estimated",
                }
            )
        if fixed_fee is not None and fixed_fee != 0:
            _add_fee("FixedClosingFee", float(fixed_fee) * max(qty, 1.0), fee_source or "unknown_fee_source")
        if dsf_fee is not None and dsf_fee != 0:
            _add_fee("DigitalServicesFee", float(dsf_fee) * max(qty, 1.0), fee_source or "unknown_fee_source")
            tax_amt = abs(dsf_fee) * max(qty, 1.0) * VAT_DEFAULT
            entries.append(
                {
                    "amount_type": "DigitalServicesFeeTax",
                    "amount": round(-abs(tax_amt), 2),
                    "transaction_type": "Estimated",
                    "amount_description": f"VAT on DSF from {fee_source or 'unknown_fee_source'}",
                    "data_level": "fee_estimated",
                }
            )

    def _add(amount_type: str, amount: float, description: str) -> None:
        entries.append(
            {
                "amount_type": amount_type,
                "amount": round(amount, 2),
                "transaction_type": "Estimated",
                "amount_description": description,
                "data_level": "customer_known",
            }
        )

    if abs(principal_total) > 1e-9:
        _add("Principal", principal_total, "Estimated product charges")
    if abs(tax_total) > 1e-9:
        _add("Tax", tax_total, "Estimated product tax")
    if has_shipping and abs(shipping_total) > 1e-9:
        _add("ShippingCharge", shipping_total, "Estimated shipping charge")
        _add("ShippingChargeback", -shipping_total, "Estimated shipping rebate")
    if has_shipping and abs(shipping_tax_total) > 1e-9:
        _add("ShippingTax", shipping_tax_total, "Estimated shipping tax")
        _add("ShippingTaxChargeback", -shipping_tax_total, "Estimated shipping tax rebate")
    if abs(giftwrap_total) > 1e-9:
        _add("GiftWrap", giftwrap_total, "Estimated giftwrap charge")
    if abs(giftwrap_tax_total) > 1e-9:
        _add("GiftWrapTax", giftwrap_tax_total, "Estimated giftwrap tax")
    if abs(promo_total) > 1e-9:
        _add("Promotion", -abs(promo_total), "Estimated promotion")

    enriched: List[Dict[str, Any]] = []
    generated_at = datetime.now(timezone.utc).isoformat()
    for entry in entries:
        enriched.append(
            {
                "order_id": order_id,
                "posted_date": posted_dt,
                "settlement_id": None,
                "amount_type": entry["amount_type"],
                "amount": entry["amount"],
                "currency": currency,
                "transaction_type": entry.get("transaction_type", "Estimated"),
                "amount_description": entry.get("amount_description", ""),
                "is_estimate": 1,
                "data_level": entry.get("data_level"),
                "price_source": price_source,
                "raw_json": json.dumps(
                    {
                        "generated_at": generated_at,
                        "order_id": order_id,
                        "source_used": fee_source_used,
                        "missing_fee_data": missing_fee_data,
                        "amount_type": entry["amount_type"],
                    },
                    separators=(",", ":"),
                ),
            }
        )

    return enriched


def main() -> None:
    items_df = load_csv(ITEMS_PATH)
    if items_df.empty:
        print("[estimate] no order_items_raw.csv found; nothing to do")
        return
    orders_df = load_csv(ORDERS_PATH)
    # Attach purchase_date and order_total_currency from orders_raw if available
    if not orders_df.empty and "amazon_order_id" in orders_df.columns:
        base_cols = ["amazon_order_id", "purchase_date", "order_total_currency"]
        cols = [c for c in base_cols if c in orders_df.columns]
        items_df = items_df.merge(
            orders_df[cols],
            left_on="amazon_order_id",
            right_on="amazon_order_id",
            how="left",
        )

    snapshot_map = load_snapshot_map()
    fee_cache = load_fee_cache()
    posted = posted_orders()
    last_price_map = last_price_by_sku(items_df)
    product_prices = load_product_prices()

    if "amazon_order_id" not in items_df.columns:
        print("[estimate] items CSV missing amazon_order_id; nothing to do")
        return

    orders_to_estimate = [
        oid for oid in items_df["amazon_order_id"].dropna().unique().tolist() if str(oid) not in posted
    ]
    print(f"[estimate] orders without posted financials: {len(orders_to_estimate)}")

    all_entries: List[Dict[str, Any]] = []
    for oid in orders_to_estimate:
        subset = items_df[items_df["amazon_order_id"] == oid]
        entries = estimate_order(str(oid), subset, snapshot_map, fee_cache, last_price_map, product_prices)
        all_entries.extend(entries)

    out_df = pd.DataFrame(all_entries)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUTPUT_PATH, index=False)
    print(f"[estimate] wrote {len(out_df)} rows to {OUTPUT_PATH}")

    # Presentation: write to Google Sheets (new Financials sheet, dedicated tab)
    try:
        client = gspread.service_account(
            filename=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", str(Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json"))
        )
        sheet = client.open_by_key(SHEET_ID)
        payload = [list(out_df.columns)] + out_df.fillna("").astype(str).values.tolist()
        try:
            ws = sheet.worksheet(SHEET_TAB)
        except gspread.WorksheetNotFound:
            ws = sheet.add_worksheet(
                title=SHEET_TAB, rows=max(len(payload) + 10, 2000), cols=max(len(out_df.columns) + 5, 40)
            )
        else:
            ws.clear()
        ws.update(range_name="A1", values=payload)
        print(f"[estimate] wrote {len(out_df)} rows to sheet tab {SHEET_TAB}")
    except Exception as exc:
        print(f"[estimate] sheet write skipped/failed: {exc}")

    # Stage 1 output copy with price_source
    out_df.to_csv(LEVEL1_OUTPUT_PATH, index=False)
    try:
        client = gspread.service_account(
            filename=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", str(Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json"))
        )
        sheet = client.open_by_key(SHEET_ID)
        payload = [list(out_df.columns)] + out_df.fillna("").astype(str).values.tolist()
        try:
            ws = sheet.worksheet(SHEET_TAB_LEVEL1)
        except gspread.WorksheetNotFound:
            ws = sheet.add_worksheet(
                title=SHEET_TAB_LEVEL1, rows=max(len(payload) + 10, 2000), cols=max(len(out_df.columns) + 5, 40)
            )
        else:
            ws.clear()
        ws.update(range_name="A1", values=payload)
        print(f"[estimate] wrote {len(out_df)} rows to sheet tab {SHEET_TAB_LEVEL1}")
    except Exception as exc:
        print(f"[estimate] Level 1 sheet write skipped/failed: {exc}")


if __name__ == "__main__":
    main()
