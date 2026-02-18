"""
Rebuild Level 1 (estimated) dataset from archived orders/items.

Reads out/orders_all.csv and out/order_items_all.csv, applies the same
pricing/fee estimation used in Level 2 (per-unit banding, qty-scaled),
and writes:
- out/financial_events_level1.csv
- Level_1_Immediate sheet tab
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd
import gspread
from gspread.exceptions import APIError

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ORDERS_ALL = Path("out/orders_all.csv")
ITEMS_ALL = Path("out/order_items_all.csv")
PRODUCT_DB_PATH = Path("out/product_db_preview.csv")
OUT_LEVEL1 = Path("out/financial_events_level1.csv")
TOKEN_ALLOC_PATH = Path("out/token_allocations_live.csv")
TOKEN_LEDGER_PATH = Path("out/token_ledger_live.csv")
FX_RATES_PATH = Path("out/fx_rates_daily.csv")

SHEET_ID = "1BHueJTk4dvvhIXypzh6i2hQTgc0pB3DWj2khQ2IT6_A"
LEVEL1_TAB = "Level_1_Immediate"
SHEETS_MAX_RETRIES = 5
SHEETS_BACKOFF = 2.0

VAT_DEFAULT = 0.2
MIN_REFERRAL_FEE = 0.25


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


def get_gspread_client() -> gspread.Client:
    cred_path = Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json"
    return gspread.service_account(filename=str(cred_path))


def write_tab_with_retry(sheet: gspread.Spreadsheet, tab_name: str, df: pd.DataFrame) -> None:
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
            import time

            time.sleep(SHEETS_BACKOFF * attempt)


LEVEL1_COLUMNS = [
    "Date",
    "Order ID",
    "SKU",
    "Quantity Ordered",
    "Price_Total",
    "Price_VAT",
    "Price_ExVAT",
    "Shipping_Total",
    "Shipping_VAT",
    "Shipping_ExVAT",
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
    "token_id",
    "token_cost",
    "token_currency",
    "token_source",
]


def _load_token_allocations() -> Dict[Tuple[str, str], List[Dict[str, str]]]:
    def _from_ledger() -> Dict[Tuple[str, str], List[Dict[str, str]]]:
        if not TOKEN_LEDGER_PATH.exists():
            return {}
        try:
            df = pd.read_csv(TOKEN_LEDGER_PATH, dtype=str).fillna("")
        except Exception:
            return {}
        if df.empty:
            return {}
        df = df.rename(
            columns={
                "allocated_order_id": "Order ID",
                "seller_sku": "SKU",
                "token_id": "token_id",
                "cost_per_unit": "token_cost",
                "currency": "token_currency",
                "allocated_date": "allocation_date",
            }
        )
        df = df[df["Order ID"].astype(str).str.strip() != ""]
        alloc_map: Dict[Tuple[str, str], List[Dict[str, str]]] = {}
        for _, row in df.iterrows():
            key = (str(row.get("Order ID", "")).strip(), str(row.get("SKU", "")).strip())
            if not key[0] or not key[1]:
                continue
            alloc_map.setdefault(key, []).append(
                {
                    "token_id": row.get("token_id", ""),
                    "token_cost": row.get("token_cost", ""),
                    "token_currency": row.get("token_currency", ""),
                    "allocation_date": row.get("allocation_date", ""),
                }
            )
        for key, rows in alloc_map.items():
            rows.sort(key=lambda r: (r.get("allocation_date") or "", r.get("token_id") or ""))
        return alloc_map

    if not TOKEN_ALLOC_PATH.exists():
        return _from_ledger()
    try:
        df = pd.read_csv(TOKEN_ALLOC_PATH, dtype=str).fillna("")
    except Exception:
        return _from_ledger()
    if df.empty:
        return _from_ledger()
    df = df.rename(
        columns={
            "order_id": "Order ID",
            "seller_sku": "SKU",
            "token_id": "token_id",
            "token_cost": "token_cost",
            "currency": "token_currency",
            "allocation_date": "allocation_date",
        }
    )
    df["Order ID"] = df["Order ID"].astype(str).str.strip()
    df["SKU"] = df["SKU"].astype(str).str.strip()
    alloc_map: Dict[Tuple[str, str], List[Dict[str, str]]] = {}
    for _, row in df.iterrows():
        key = (row.get("Order ID", ""), row.get("SKU", ""))
        if not key[0] or not key[1]:
            continue
        alloc_map.setdefault(key, []).append(
            {
                "token_id": row.get("token_id", ""),
                "token_cost": row.get("token_cost", ""),
                "token_currency": row.get("token_currency", ""),
                "allocation_date": row.get("allocation_date", ""),
            }
        )
    for key, rows in alloc_map.items():
        rows.sort(key=lambda r: (r.get("allocation_date") or "", r.get("token_id") or ""))
    return alloc_map


def build_level1(df_orders: pd.DataFrame, df_items: pd.DataFrame, product_db: Dict[str, Dict[str, str]]) -> pd.DataFrame:
    if df_items.empty:
        return pd.DataFrame(columns=LEVEL1_COLUMNS)
    token_allocs = _load_token_allocations()
    order_cols = ["amazon_order_id", "purchase_date", "order_status", "order_total_currency"]
    use_cols = [c for c in order_cols if c in df_orders.columns]
    merged = df_items.merge(
        df_orders[use_cols],
        on="amazon_order_id",
        how="left",
    )
    rows = []
    fx_lookup = _load_fx_rates()
    for _, r in merged.iterrows():
        sku = r.get("seller_sku", "")
        fee_row = product_db.get(sku, {}) if product_db else {}
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
        vat_rate_row = fee_row.get("vat_rate")
        if vat_rate_row in ("", None) or pd.isna(vat_rate_row):
            vat_rate_row = fee_row.get("last_vat_rate_pct")
        live_price = fee_row.get("live_listing_price")
        last_sold_price = fee_row.get("last_sold_price")

        qty_val = 1.0
        qty_raw = r.get("quantity_ordered", "")
        try:
            qraw = qty_raw or 1
            qty_val = float(qraw)
        except Exception:
            qty_val = 1.0
        status = str(r.get("order_status", "")).strip().lower()
        is_canceled = status == "canceled" or qty_val <= 0
        if qty_val <= 0:
            qty_val = 1.0

        # Item price and VAT fallbacks
        price_total = r.get("item_price_amount", "")
        price_vat = r.get("item_tax_amount", "")
        price_val: Optional[float] = None
        price_vat_val: Optional[float] = None

        try:
            price_val = float(price_total) if price_total not in ("", None, "") else None
        except Exception:
            price_val = None
        try:
            price_vat_val = float(price_vat) if price_vat not in ("", None, "") else None
        except Exception:
            price_vat_val = None

        # If missing price, fall back to product DB live/last_sold (assumed VAT-inclusive)
        if price_val is None:
            fallback_unit = None
            for candidate in (live_price, last_sold_price):
                try:
                    if candidate not in ("", None):
                        fallback_unit = float(candidate)
                        break
                except Exception:
                    continue
            if fallback_unit is not None:
                order_currency = str(r.get("item_price_currency") or r.get("order_total_currency") or "").strip()
                date_key = _date_key(r.get("purchase_date", ""))
                if order_currency:
                    fallback_unit = _fx_convert(fallback_unit, "GBP", order_currency, date_key, fx_lookup)
                price_val = fallback_unit * qty_val
                price_total = f"{price_val:.2f}"

        # VAT rate: derive if both price and tax present; else use product DB or default
        vat_rate = VAT_DEFAULT
        try:
            if price_val is not None and price_vat_val is not None:
                ex_tmp = price_val - price_vat_val
                if ex_tmp > 0:
                    vat_rate = price_vat_val / ex_tmp
            elif vat_rate_row not in ("", None):
                vat_rate = float(vat_rate_row) / 100.0 if float(vat_rate_row) > 1 else float(vat_rate_row)
        except Exception:
            vat_rate = VAT_DEFAULT

        # If tax missing but price known, derive tax/net using vat_rate
        if price_val is not None and price_vat_val is None:
            net = price_val / (1 + vat_rate)
            price_vat_val = round_half_up(price_val - net, 2)
            price_vat = f"{price_vat_val:.2f}"
        price_ex = ""
        if price_val is not None:
            if price_vat_val is None:
                net = price_val / (1 + vat_rate)
                price_ex = f"{net:.2f}"
            else:
                price_ex = f"{price_val - price_vat_val:.2f}"

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

        unit_price_val = None
        if price_val is not None:
            try:
                unit_price_val = price_val / qty_val
            except Exception:
                unit_price_val = price_val

        # FBA fee per unit then scale
        fba_ex = fba_vat = fba_total = ""
        if price_val is not None:
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
                    ex_fee_unit = float(selected_fee)
                    ex_fee_total = ex_fee_unit * qty_val
                    fee_vat_total = round_half_up(ex_fee_total * vat_rate, 2)
                    fba_ex = f"{ex_fee_total:.2f}"
                    fba_vat = f"{fee_vat_total:.2f}"
                    fba_total = f"{round_half_up(ex_fee_total + fee_vat_total, 2):.2f}"
                except Exception:
                    pass

        # Commission
        comm_total = comm_vat = comm_ex = ""
        comm_ex_amt: Optional[float] = None
        if price_val is not None:
            selected_rate = None
            if ref_10 not in ("", None) and unit_price_val is not None and unit_price_val <= 10:
                selected_rate = ref_10
            elif ref_100 not in ("", None) and unit_price_val is not None and unit_price_val > 10:
                selected_rate = ref_100
            elif ref_10 not in ("", None):
                selected_rate = ref_10
            elif ref_100 not in ("", None):
                selected_rate = ref_100
            elif ref_band_10 not in ("", None) and unit_price_val is not None and unit_price_val <= 10:
                selected_rate = ref_band_10
            elif ref_band_100 not in ("", None) and unit_price_val is not None and unit_price_val > 10:
                selected_rate = ref_band_100
            elif ref_fallback not in ("", None):
                selected_rate = ref_fallback
            if selected_rate not in ("", None):
                try:
                    rate_val = float(selected_rate)
                    if rate_val > 1:
                        rate_val = rate_val / 100.0
                    # Per-unit rounding to match Amazon: compute per-unit fee, round, then scale by qty.
                    unit_gross = float(price_total) / qty_val if qty_val else float(price_total)
                    per_unit_fee = unit_gross * rate_val
                    if per_unit_fee < MIN_REFERRAL_FEE:
                        per_unit_fee = MIN_REFERRAL_FEE
                    per_unit_fee = round_half_up(per_unit_fee, 2)
                    comm_ex_amt = per_unit_fee * qty_val
                    comm_vat_amt = round_half_up(comm_ex_amt * vat_rate, 2)
                    comm_ex = f"{comm_ex_amt:.2f}"
                    comm_vat = f"{comm_vat_amt:.2f}"
                    comm_total = f"{comm_ex_amt + comm_vat_amt:.2f}"
                except Exception:
                    pass

        # DSF (2% of ex-VAT components, then VAT)
        dsf_comm_ex = round_half_up(comm_ex_amt * 0.02, 2) if comm_ex_amt is not None else 0.0
        try:
            fba_ex_amt = float(fba_ex) if fba_ex else 0.0
        except Exception:
            fba_ex_amt = 0.0
        dsf_fba_ex = round_half_up(fba_ex_amt * 0.02, 2) if fba_ex else 0.0
        dsf_ex_total_val = dsf_comm_ex + dsf_fba_ex
        dsf_total = dsf_vat = dsf_ex = ""
        if dsf_ex_total_val > 0:
            dsf_vat_val = round_half_up(dsf_ex_total_val * vat_rate, 2)
            dsf_total_val = dsf_ex_total_val + dsf_vat_val
            dsf_ex = f"{dsf_ex_total_val:.2f}"
            dsf_vat = f"{dsf_vat_val:.2f}"
            dsf_total = f"{dsf_total_val:.2f}"

        order_id = r.get("amazon_order_id", "")
        alloc_key = (str(order_id).strip(), str(sku).strip())
        alloc_list = token_allocs.get(alloc_key, [])

        unit_count = int(qty_val) if qty_val else 1
        unit_count = max(unit_count, 1)
        unit_price_total = price_val / unit_count if price_val is not None else None
        unit_price_vat = price_vat_val / unit_count if price_vat_val is not None else None
        unit_price_ex = None
        if price_ex not in ("", None):
            try:
                unit_price_ex = float(price_ex) / unit_count
            except Exception:
                unit_price_ex = None
        unit_ship_total = ship_price / unit_count if ship_price else None
        unit_ship_vat = ship_tax / unit_count if ship_tax else None
        unit_ship_ex = ship_net / unit_count if ship_net else None
        unit_fba_total = float(fba_total) / unit_count if fba_total else None
        unit_fba_vat = float(fba_vat) / unit_count if fba_vat else None
        unit_fba_ex = float(fba_ex) / unit_count if fba_ex else None
        unit_comm_total = float(comm_total) / unit_count if comm_total else None
        unit_comm_vat = float(comm_vat) / unit_count if comm_vat else None
        unit_comm_ex = float(comm_ex) / unit_count if comm_ex else None
        unit_dsf_total = float(dsf_total) / unit_count if dsf_total else None
        unit_dsf_vat = float(dsf_vat) / unit_count if dsf_vat else None
        unit_dsf_ex = float(dsf_ex) / unit_count if dsf_ex else None

        for _ in range(unit_count):
            if is_canceled:
                token = {}
            else:
                token = alloc_list.pop(0) if alloc_list else {}
            token_cost = token.get("token_cost", "")
            margin_ex = ""
            margin_pct = ""
            try:
                rev_ex = 0.0
                if unit_price_ex is not None:
                    rev_ex += float(unit_price_ex)
                if unit_ship_ex is not None:
                    rev_ex += float(unit_ship_ex)
                fee_ex = 0.0
                if unit_fba_ex is not None:
                    fee_ex += abs(float(unit_fba_ex))
                if unit_comm_ex is not None:
                    fee_ex += abs(float(unit_comm_ex))
                if unit_dsf_ex is not None:
                    fee_ex += abs(float(unit_dsf_ex))
                cogs_ex = abs(float(token_cost)) if token_cost not in ("", None) else 0.0
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
                    "Order ID": order_id,
                    "SKU": sku,
                    "Quantity Ordered": "0" if is_canceled else "1",
                    "Price_Total": f"{unit_price_total:.2f}" if unit_price_total is not None and not is_canceled else "",
                    "Price_VAT": f"{unit_price_vat:.2f}" if unit_price_vat is not None and not is_canceled else "",
                    "Price_ExVAT": f"{unit_price_ex:.2f}" if unit_price_ex is not None and not is_canceled else "",
                    "Shipping_Total": "",
                    "Shipping_VAT": "",
                    "Shipping_ExVAT": "",
                    "COGS_Total": token_cost,
                    "COGS_VAT": "",
                    "COGS_ExVAT": token_cost,
                    "FBA_Fee_Total": f"{unit_fba_total:.2f}" if unit_fba_total is not None and not is_canceled else "",
                    "FBA_Fee_VAT": f"{unit_fba_vat:.2f}" if unit_fba_vat is not None and not is_canceled else "",
                    "FBA_Fee_ExVAT": f"{unit_fba_ex:.2f}" if unit_fba_ex is not None and not is_canceled else "",
                    "Commission_Total": f"{unit_comm_total:.2f}" if unit_comm_total is not None and not is_canceled else "",
                    "Commission_VAT": f"{unit_comm_vat:.2f}" if unit_comm_vat is not None and not is_canceled else "",
                    "Commission_ExVAT": f"{unit_comm_ex:.2f}" if unit_comm_ex is not None and not is_canceled else "",
                    "Digital_Fee_Total": f"{unit_dsf_total:.2f}" if unit_dsf_total is not None and not is_canceled else "",
                    "Digital_Fee_VAT": f"{unit_dsf_vat:.2f}" if unit_dsf_vat is not None and not is_canceled else "",
                    "Digital_Fee_ExVAT": f"{unit_dsf_ex:.2f}" if unit_dsf_ex is not None and not is_canceled else "",
                    "Margin_ExVAT": "" if is_canceled else margin_ex,
                    "Margin_Pct": "" if is_canceled else margin_pct,
                    "token_id": token.get("token_id", ""),
                    "token_cost": token_cost,
                    "token_currency": token.get("token_currency", ""),
                    "token_source": "token_allocations_live",
                }
            )
    return pd.DataFrame(rows, columns=LEVEL1_COLUMNS)


def main() -> None:
    if not ORDERS_ALL.exists() or not ITEMS_ALL.exists():
        print("orders_all.csv or order_items_all.csv missing")
        return
    orders = pd.read_csv(ORDERS_ALL, dtype=str).fillna("")
    items = pd.read_csv(ITEMS_ALL, dtype=str).fillna("")
    # load product db
    product_db: Dict[str, Dict[str, str]] = {}
    if PRODUCT_DB_PATH.exists():
        pdf = pd.read_csv(PRODUCT_DB_PATH, dtype=str).fillna("")
        for _, row in pdf.iterrows():
            sku = row.get("seller_sku") or row.get("sku") or ""
            if not sku:
                continue
            product_db[sku] = {
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
                "last_vat_rate_pct": row.get("last_vat_rate_pct"),
                "live_listing_price": row.get("live_listing_price"),
                "last_sold_price": row.get("last_sold_price"),
            }
    df_level1 = build_level1(orders, items, product_db)
    OUT_LEVEL1.parent.mkdir(parents=True, exist_ok=True)
    df_level1.to_csv(OUT_LEVEL1, index=False)
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(SHEET_ID)
        write_tab_with_retry(sheet, LEVEL1_TAB, df_level1)
    except Exception as exc:
        print({"status": "warning", "alert": "sheets_error", "error": str(exc)})
    print({"status": "success", "rows": len(df_level1), "snapshot": str(OUT_LEVEL1)})


if __name__ == "__main__":
    main()
