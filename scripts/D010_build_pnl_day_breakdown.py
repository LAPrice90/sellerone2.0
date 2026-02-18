"""
Build a daily P&L breakdown with line-level detail for audit.

Outputs:
- out/pnl_day_breakdown.csv
- Sheet tab P&L_Breakdown_Daily (overwritten)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import gspread
from gspread.exceptions import APIError

ORDER_LEDGER_FX = Path("out/order_ledger_fx.csv")
REFUNDS_OFFICIAL = Path("out/financial_events_refunds_official.csv")
ORDER_COGS = Path("out/order_cogs_from_tokens.csv")
TOKEN_COGS = Path("out/token_cogs_ledger.csv")
TXN_CATEGORY_LEDGER = Path("out/transaction_category_ledger.csv")

OUT_PATH = Path("out/pnl_day_breakdown.csv")

SHEET_ID = os.environ.get("PNL_SHEET_ID", "1aT26UYnTBP6-oNz0RIWVCRbuuN1RmP4_VwHEeiNzxKc")
TAB_NAME = os.environ.get("PNL_BREAKDOWN_TAB", "P&L_Breakdown_Daily")
BREAKDOWN_DATE = os.environ.get("PNL_BREAKDOWN_DATE", "").strip()
PNL_BREAKDOWN_ONLY_MAPPED = os.environ.get("PNL_BREAKDOWN_ONLY_MAPPED", "1").strip() == "1"

SHEETS_MAX_RETRIES = 5
SHEETS_BACKOFF = 2.0

CAT_MAP = {
    "Inbound_Transportation_Fee": "Inbound_Transportation_Fee",
    "Removal_Fee": "Removal_Fee",
    "Warehouse_Lost_Reimbursement": "Warehouse_Lost_Reimbursement",
    "Reversal_Reimbursement": "Reversal_Reimbursement",
    "Retrocharge": "Retrocharge_Total",
    "Refund_Retrocharge": "Retrocharge_Total",
    "Inventory_Reimbursement": "Inventory_Reimbursement",
    "Compensated_Clawback": "Compensated_Clawback",
    "Shipping_Chargeback": "Shipping_Chargeback",
    "Storage_Charges": "Storage_Charges",
    "Subscription_Fee": "Subscription_Fee_Total",
}


def _date_key(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True).dt.strftime("%Y-%m-%d")


def get_gspread_client() -> gspread.Client:
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        cred_path = str(Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=cred_path)


def write_tab_with_retry(sheet: gspread.Spreadsheet, tab_name: str, df: pd.DataFrame) -> None:
    payload = [list(df.columns)] + df.where(pd.notnull(df), "").values.tolist()
    for attempt in range(1, SHEETS_MAX_RETRIES + 1):
        try:
            try:
                ws = sheet.worksheet(tab_name)
            except gspread.WorksheetNotFound:
                ws = sheet.add_worksheet(title=tab_name, rows=max(len(payload) + 10, 2000), cols=max(len(df.columns) + 5, 40))
            else:
                ws.clear()
            ws.update(range_name="A1", values=payload, value_input_option="USER_ENTERED")
            return
        except APIError:
            if attempt == SHEETS_MAX_RETRIES:
                raise
            import time

            time.sleep(SHEETS_BACKOFF * attempt)


def _load_cogs_map() -> Dict[Tuple[str, str], float]:
    if not ORDER_COGS.exists():
        return {}
    df = pd.read_csv(ORDER_COGS, dtype=str).fillna("")
    if df.empty:
        return {}
    df["cogs_total"] = pd.to_numeric(df.get("cogs_total"), errors="coerce").fillna(0.0)
    out: Dict[Tuple[str, str], float] = {}
    for _, r in df.iterrows():
        key = (str(r.get("order_id", "")).strip(), str(r.get("sku", "")).strip())
        if not key[0] or not key[1]:
            continue
        out[key] = out.get(key, 0.0) + float(r.get("cogs_total") or 0.0)
    return out


def _load_token_map() -> Dict[Tuple[str, str], Dict[str, object]]:
    if not TOKEN_COGS.exists():
        return {}
    df = pd.read_csv(TOKEN_COGS, dtype=str).fillna("")
    if df.empty:
        return {}
    df["token_cost"] = pd.to_numeric(df.get("token_cost"), errors="coerce").fillna(0.0)
    out: Dict[Tuple[str, str], Dict[str, object]] = {}
    if "sku" not in df.columns and "seller_sku" in df.columns:
        df = df.rename(columns={"seller_sku": "sku"})
    if "token_currency" not in df.columns and "currency" in df.columns:
        df = df.rename(columns={"currency": "token_currency"})
    for (order_id, sku), grp in df.groupby(["order_id", "sku"]):
        key = (str(order_id).strip(), str(sku).strip())
        token_ids = [t for t in grp.get("token_id", "").astype(str).tolist() if t]
        token_cost = float(grp["token_cost"].sum())
        token_currency = ""
        if "token_currency" in grp.columns:
            vals = [v for v in grp["token_currency"].astype(str).tolist() if v]
            token_currency = vals[0] if vals else ""
        out[key] = {
            "token_ids": "|".join(token_ids),
            "token_cost_total": round(token_cost, 2),
            "token_currency": token_currency,
        }
    return out


def _coerce_num(df: pd.DataFrame, cols: List[str]) -> None:
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)


def main() -> None:
    if not BREAKDOWN_DATE:
        print({"status": "error", "error": "PNL_BREAKDOWN_DATE is required (YYYY-MM-DD)."})
        return

    rows: List[Dict[str, object]] = []
    cat_map = CAT_MAP
    cogs_map = _load_cogs_map()
    token_map = _load_token_map()

    if ORDER_LEDGER_FX.exists():
        orders = pd.read_csv(ORDER_LEDGER_FX, dtype=str).fillna("")
        if not orders.empty:
            orders["date"] = _date_key(orders["Date"])
            orders = orders[orders["date"] == BREAKDOWN_DATE].copy()
            num_cols = [
                "Quantity Ordered",
                "Price_Total_GBP",
                "Price_VAT_GBP",
                "Price_ExVAT_GBP",
                "Shipping_Total_GBP",
                "Shipping_VAT_GBP",
                "Shipping_ExVAT_GBP",
                "Gift_Total_GBP",
                "Gift_VAT_GBP",
                "Gift_ExVAT_GBP",
                "Promotion_Total_GBP",
                "Promotion_VAT_GBP",
                "Promotion_ExVAT_GBP",
                "FBA_Fee_Total_GBP",
                "FBA_Fee_VAT_GBP",
                "FBA_Fee_ExVAT_GBP",
                "Commission_Total_GBP",
                "Commission_VAT_GBP",
                "Commission_ExVAT_GBP",
                "Digital_Fee_Total_GBP",
                "Digital_Fee_VAT_GBP",
                "Digital_Fee_ExVAT_GBP",
            ]
            _coerce_num(orders, num_cols)
            # Skip cancelled/zero-qty lines to match P&L expectation.
            orders["Quantity Ordered"] = pd.to_numeric(orders.get("Quantity Ordered"), errors="coerce").fillna(0.0)
            orders = orders[orders["Quantity Ordered"] > 0].copy()
            for _, r in orders.iterrows():
                order_id = str(r.get("Order ID", "")).strip()
                sku = str(r.get("SKU", "")).strip()
                key = (order_id, sku)
                token_meta = token_map.get(key, {})
                rows.append(
                    {
                        "section": "order",
                        "date": BREAKDOWN_DATE,
                        "order_id": order_id,
                        "sku": sku,
                        "qty": r.get("Quantity Ordered", 0.0),
                        "price_total": r.get("Price_Total_GBP", 0.0),
                        "price_vat": r.get("Price_VAT_GBP", 0.0),
                        "price_exvat": r.get("Price_ExVAT_GBP", 0.0),
                        "shipping_total": r.get("Shipping_Total_GBP", 0.0),
                        "shipping_vat": r.get("Shipping_VAT_GBP", 0.0),
                        "shipping_exvat": r.get("Shipping_ExVAT_GBP", 0.0),
                        "gift_total": r.get("Gift_Total_GBP", 0.0),
                        "gift_vat": r.get("Gift_VAT_GBP", 0.0),
                        "gift_exvat": r.get("Gift_ExVAT_GBP", 0.0),
                        "promotion_total": r.get("Promotion_Total_GBP", 0.0),
                        "promotion_vat": r.get("Promotion_VAT_GBP", 0.0),
                        "promotion_exvat": r.get("Promotion_ExVAT_GBP", 0.0),
                        "cogs_total": round(float(cogs_map.get(key, 0.0)), 2),
                        "fba_fee_total": r.get("FBA_Fee_Total_GBP", 0.0),
                        "fba_fee_vat": r.get("FBA_Fee_VAT_GBP", 0.0),
                        "fba_fee_exvat": r.get("FBA_Fee_ExVAT_GBP", 0.0),
                        "commission_total": r.get("Commission_Total_GBP", 0.0),
                        "commission_vat": r.get("Commission_VAT_GBP", 0.0),
                        "commission_exvat": r.get("Commission_ExVAT_GBP", 0.0),
                        "digital_fee_total": r.get("Digital_Fee_Total_GBP", 0.0),
                        "digital_fee_vat": r.get("Digital_Fee_VAT_GBP", 0.0),
                        "digital_fee_exvat": r.get("Digital_Fee_ExVAT_GBP", 0.0),
                        "token_ids": token_meta.get("token_ids", ""),
                        "token_cost_total": token_meta.get("token_cost_total", 0.0),
                        "token_currency": token_meta.get("token_currency", ""),
                        "pnl_row": "",
                        "pnl_amount": "",
                        "transaction_type": "",
                        "breakdown_type": "",
                        "description": "",
                        "amount_value": "",
                        "currency": "",
                        "category": "",
                        "category_group": "",
                        "inbound_shipment_id": "",
                    }
                )

    if REFUNDS_OFFICIAL.exists():
        ref = pd.read_csv(REFUNDS_OFFICIAL, dtype=str).fillna("")
        if not ref.empty:
            ref["date"] = _date_key(ref["Date"])
            ref = ref[ref["date"] == BREAKDOWN_DATE].copy()
            num_cols = [
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
                "FixedClosingFee_Total",
                "FixedClosingFee_VAT",
                "FixedClosingFee_ExVAT",
            ]
            _coerce_num(ref, num_cols)
            for _, r in ref.iterrows():
                rows.append(
                    {
                        "section": "refund",
                        "date": BREAKDOWN_DATE,
                        "order_id": r.get("Order ID", ""),
                        "sku": r.get("SKU", ""),
                        "qty": r.get("Quantity Ordered", 0.0),
                        "price_total": r.get("Price_Total", 0.0),
                        "price_vat": r.get("Price_VAT", 0.0),
                        "price_exvat": r.get("Price_ExVAT", 0.0),
                        "shipping_total": r.get("Shipping_Total", 0.0),
                        "shipping_vat": r.get("Shipping_VAT", 0.0),
                        "shipping_exvat": r.get("Shipping_ExVAT", 0.0),
                        "gift_total": r.get("Gift_Total", 0.0),
                        "gift_vat": r.get("Gift_VAT", 0.0),
                        "gift_exvat": r.get("Gift_ExVAT", 0.0),
                        "promotion_total": r.get("Promotion_Total", 0.0),
                        "promotion_vat": r.get("Promotion_VAT", 0.0),
                        "promotion_exvat": r.get("Promotion_ExVAT", 0.0),
                        "cogs_total": "",
                        "fba_fee_total": r.get("FBA_Fee_Total", 0.0),
                        "fba_fee_vat": r.get("FBA_Fee_VAT", 0.0),
                        "fba_fee_exvat": r.get("FBA_Fee_ExVAT", 0.0),
                        "commission_total": r.get("Commission_Total", 0.0),
                        "commission_vat": r.get("Commission_VAT", 0.0),
                        "commission_exvat": r.get("Commission_ExVAT", 0.0),
                        "digital_fee_total": r.get("Digital_Fee_Total", 0.0),
                        "digital_fee_vat": r.get("Digital_Fee_VAT", 0.0),
                        "digital_fee_exvat": r.get("Digital_Fee_ExVAT", 0.0),
                        "token_ids": "",
                        "token_cost_total": "",
                        "token_currency": "",
                        "pnl_row": "",
                        "pnl_amount": "",
                        "transaction_type": "",
                        "breakdown_type": "",
                        "description": "",
                        "amount_value": "",
                        "currency": "",
                        "category": "",
                        "category_group": "",
                        "inbound_shipment_id": "",
                    }
                )

    if TXN_CATEGORY_LEDGER.exists():
        tx = pd.read_csv(TXN_CATEGORY_LEDGER, dtype=str).fillna("")
        if not tx.empty:
            tx["date"] = _date_key(tx["posted_date"])
            tx = tx[tx["date"] == BREAKDOWN_DATE].copy()
            tx["amount_value"] = pd.to_numeric(tx.get("amount_value"), errors="coerce").fillna(0.0)
            for _, r in tx.iterrows():
                category = r.get("category", "")
                desc = str(r.get("description") or "")
                if category == "Service_Fee" and "Subscription" in desc:
                    pnl_row = "Subscription_Fee_Total"
                else:
                    pnl_row = cat_map.get(category, "")
                if PNL_BREAKDOWN_ONLY_MAPPED and not pnl_row:
                    continue
                rows.append(
                    {
                        "section": "transaction",
                        "date": BREAKDOWN_DATE,
                        "order_id": "",
                        "sku": "",
                        "qty": "",
                        "price_total": "",
                        "price_vat": "",
                        "price_exvat": "",
                        "shipping_total": "",
                        "shipping_vat": "",
                        "shipping_exvat": "",
                        "gift_total": "",
                        "gift_vat": "",
                        "gift_exvat": "",
                        "promotion_total": "",
                        "promotion_vat": "",
                        "promotion_exvat": "",
                        "cogs_total": "",
                        "fba_fee_total": "",
                        "fba_fee_vat": "",
                        "fba_fee_exvat": "",
                        "commission_total": "",
                        "commission_vat": "",
                        "commission_exvat": "",
                        "digital_fee_total": "",
                        "digital_fee_vat": "",
                        "digital_fee_exvat": "",
                        "token_ids": "",
                        "token_cost_total": "",
                        "token_currency": "",
                        "pnl_row": pnl_row,
                        "pnl_amount": r.get("amount_value", 0.0),
                        "transaction_type": r.get("transaction_type", ""),
                        "breakdown_type": r.get("breakdown_type", ""),
                        "description": r.get("description", ""),
                        "amount_value": r.get("amount_value", 0.0),
                        "currency": r.get("currency", ""),
                        "category": category,
                        "category_group": r.get("category_group", ""),
                        "inbound_shipment_id": r.get("inbound_shipment_id", ""),
                    }
                )

    df_out = pd.DataFrame(rows)
    if df_out.empty:
        df_out = pd.DataFrame(
            columns=[
                "section",
                "date",
                "order_id",
                "sku",
                "qty",
                "price_total",
                "price_vat",
                "price_exvat",
                "shipping_total",
                "shipping_vat",
                "shipping_exvat",
                "gift_total",
                "gift_vat",
                "gift_exvat",
                "promotion_total",
                "promotion_vat",
                "promotion_exvat",
                "cogs_total",
                "fba_fee_total",
                "fba_fee_vat",
                "fba_fee_exvat",
                "commission_total",
                "commission_vat",
                "commission_exvat",
                "digital_fee_total",
                "digital_fee_vat",
                "digital_fee_exvat",
                "token_ids",
                "token_cost_total",
                "token_currency",
                "pnl_row",
                "pnl_amount",
                "transaction_type",
                "breakdown_type",
                "description",
                "amount_value",
                "currency",
                "category",
                "category_group",
                "inbound_shipment_id",
            ]
        )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(OUT_PATH, index=False)

    try:
        client = get_gspread_client()
        sheet = client.open_by_key(SHEET_ID)
        write_tab_with_retry(sheet, TAB_NAME, df_out)
    except Exception as exc:
        print({"status": "warning", "alert": "sheets_error", "error": str(exc)})

    print({"status": "success", "rows": len(df_out), "snapshot": str(OUT_PATH), "date": BREAKDOWN_DATE})


if __name__ == "__main__":
    main()
