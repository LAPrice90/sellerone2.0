"""
Build a side-by-side P&L comparison for a single day: system vs Amazon manual.

Outputs:
- out/pnl_side_by_side_{YYYY-MM-DD}.csv
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

import pandas as pd
import gspread
from gspread.exceptions import APIError

PNL_DAILY = Path("out/pnl_daily.csv")
MANUAL = Path("out/amazon_profitandloss_2026_01_manual.csv")
MANUAL_COMPARISON = Path("out/amazon_manual_vs_system_comparison.csv")
SELLERBOARD_ORDERS = Path(
    "reference/DRJ_Hardware_Dashboard_Order_Items_01_01_2026-01_01_2026_(2026_01_24_11_38_34_518).csv"
)
TXN_CATEGORY_LEDGER = Path("out/transaction_category_ledger.csv")

COMPARE_DATE = os.environ.get("PNL_COMPARE_DATE", "2026-01-01").strip()
PNL_SHEET_ID = os.environ.get("PNL_SHEET_ID", "1aT26UYnTBP6-oNz0RIWVCRbuuN1RmP4_VwHEeiNzxKc")
PNL_SIDE_BY_SIDE_TAB = os.environ.get("PNL_SIDE_BY_SIDE_TAB", "P&L_Side_By_Side")

SHEETS_MAX_RETRIES = 5
SHEETS_BACKOFF = 2.0

ROWS = [
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
    "Gross_Profit_ExVAT",
    "Contribution_Profit_ExVAT",
    "Refund_Sales_Total",
    "Refund_Expenses_Total",
    "Inbound_Transportation_Fee",
    "Removal_Fee",
    "Warehouse_Lost_Reimbursement",
    "Reversal_Reimbursement",
    "Retrocharge_Total",
    "Inventory_Reimbursement",
    "Compensated_Clawback",
    "Refund_Commission",
    "Shipping_Chargeback",
    "Storage_Charges",
    "Subscription_Fee_Total",
    "Subscription_Fee_VAT",
    "Subscription_Fee_ExVAT",
    "Net_Profit_ExVAT",
    "Payout_Estimate",
    "VAT_Difference",
]


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def _sum_manual(df: pd.DataFrame, col: str) -> float:
    if col not in df.columns:
        return 0.0
    return float(_num(df[col]).sum())


def _build_manual_values(df: pd.DataFrame) -> Dict[str, float]:
    vals: Dict[str, float] = {}
    for col in [
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
        "Refund_Sales_Total",
        "Refund_Expenses_Total",
        "Refund_Commission",
        "Inbound_Transportation_Fee",
        "Removal_Fee",
        "Warehouse_Lost_Reimbursement",
        "Reversal_Reimbursement",
        "Retrocharge_Total",
        "Inventory_Reimbursement",
        "Compensated_Clawback",
        "Shipping_Chargeback",
        "Storage_Charges",
        "Subscription_Fee_Total",
        "Subscription_Fee_VAT",
        "Subscription_Fee_ExVAT",
    ]:
        vals[col] = _sum_manual(df, col)

    # Align manual price to system gross (Price_Total excludes promotions).
    if "Promotion_Total" in vals:
        vals["Price_Total"] = vals.get("Price_Total", 0.0) - vals.get("Promotion_Total", 0.0)
        vals["Price_VAT"] = vals.get("Price_VAT", 0.0) - vals.get("Promotion_VAT", 0.0)
        vals["Price_ExVAT"] = vals.get("Price_ExVAT", 0.0) - vals.get("Promotion_ExVAT", 0.0)

    # Derived rows based on available manual values.
    vals["Gross_Profit_ExVAT"] = vals.get("Price_ExVAT", 0.0) - vals.get("COGS_ExVAT", 0.0)
    vals["Contribution_Profit_ExVAT"] = (
        vals.get("Price_ExVAT", 0.0)
        - vals.get("COGS_ExVAT", 0.0)
        + vals.get("FBA_Fee_ExVAT", 0.0)
        + vals.get("Commission_ExVAT", 0.0)
        + vals.get("Digital_Fee_ExVAT", 0.0)
        + vals.get("Shipping_ExVAT", 0.0)
        + vals.get("Gift_ExVAT", 0.0)
        + vals.get("Promotion_ExVAT", 0.0)
    )
    vals["Net_Profit_ExVAT"] = (
        vals.get("Price_ExVAT", 0.0)
        + vals.get("Shipping_ExVAT", 0.0)
        + vals.get("Gift_ExVAT", 0.0)
        + vals.get("Promotion_ExVAT", 0.0)
        - vals.get("COGS_ExVAT", 0.0)
        + vals.get("FBA_Fee_ExVAT", 0.0)
        + vals.get("Commission_ExVAT", 0.0)
        + vals.get("Digital_Fee_ExVAT", 0.0)
        + vals.get("Refund_Expenses_Total", 0.0)
        + vals.get("Refund_Sales_Total", 0.0)
        + vals.get("Warehouse_Lost_Reimbursement", 0.0)
        + vals.get("Reversal_Reimbursement", 0.0)
        + vals.get("Inventory_Reimbursement", 0.0)
        + vals.get("Compensated_Clawback", 0.0)
        + vals.get("Inbound_Transportation_Fee", 0.0)
        + vals.get("Removal_Fee", 0.0)
        + vals.get("Retrocharge_Total", 0.0)
        + vals.get("Refund_Commission", 0.0)
        + vals.get("Shipping_Chargeback", 0.0)
        + vals.get("Subscription_Fee_ExVAT", 0.0)
    )
    vals["Payout_Estimate"] = (
        vals.get("Price_Total", 0.0)
        + vals.get("Shipping_Total", 0.0)
        + vals.get("Gift_Total", 0.0)
        + vals.get("Promotion_Total", 0.0)
        + vals.get("Refund_Sales_Total", 0.0)
        + vals.get("Refund_Expenses_Total", 0.0)
        + vals.get("FBA_Fee_Total", 0.0)
        + vals.get("Commission_Total", 0.0)
        + vals.get("Digital_Fee_Total", 0.0)
        + vals.get("Inbound_Transportation_Fee", 0.0)
        + vals.get("Removal_Fee", 0.0)
        + vals.get("Retrocharge_Total", 0.0)
        + vals.get("Refund_Commission", 0.0)
        + vals.get("Shipping_Chargeback", 0.0)
        + vals.get("Storage_Charges", 0.0)
        + vals.get("Subscription_Fee_Total", 0.0)
        + vals.get("Warehouse_Lost_Reimbursement", 0.0)
        + vals.get("Reversal_Reimbursement", 0.0)
        + vals.get("Inventory_Reimbursement", 0.0)
        + vals.get("Compensated_Clawback", 0.0)
    )
    vals["VAT_Difference"] = (
        vals.get("Price_VAT", 0.0)
        + vals.get("Shipping_VAT", 0.0)
        + vals.get("Gift_VAT", 0.0)
        + vals.get("Promotion_VAT", 0.0)
        - vals.get("COGS_VAT", 0.0)
        - vals.get("FBA_Fee_VAT", 0.0)
        - vals.get("Commission_VAT", 0.0)
        - vals.get("Digital_Fee_VAT", 0.0)
        - vals.get("Subscription_Fee_VAT", 0.0)
    )
    return vals


def _build_manual_values_from_comparison(df: pd.DataFrame) -> Dict[str, float]:
    vals: Dict[str, float] = {}
    if "Order ID" in df.columns:
        df = df[df["Order ID"].ne("TOTAL")]
    mapping = {
        "Quantity Ordered": "Quantity Ordered",
        "Price_Total": "manual_price_total_gbp",
        "Price_VAT": "manual_price_vat_gbp",
        "Price_ExVAT": "manual_price_exvat_gbp",
        "Shipping_Total": "manual_shipping_total_gbp",
        "Shipping_VAT": "manual_shipping_vat_gbp",
        "Shipping_ExVAT": "manual_shipping_exvat_gbp",
        "Promotion_Total": "manual_promo_total_gbp",
        "Promotion_VAT": "manual_promo_vat_gbp",
        "Promotion_ExVAT": "manual_promo_exvat_gbp",
        "FBA_Fee_Total": "manual_fba_total_gbp",
        "FBA_Fee_VAT": "manual_fba_vat_gbp",
        "FBA_Fee_ExVAT": "manual_fba_exvat_gbp",
        "Commission_Total": "manual_comm_total_gbp",
        "Commission_VAT": "manual_comm_vat_gbp",
        "Commission_ExVAT": "manual_comm_exvat_gbp",
        "Digital_Fee_Total": "manual_dsf_total_gbp",
        "Digital_Fee_VAT": "manual_dsf_vat_gbp",
        "Digital_Fee_ExVAT": "manual_dsf_exvat_gbp",
    }
    for key, col in mapping.items():
        if col in df.columns:
            vals[key] = float(_num(df[col]).sum())
    return vals


def _derive_profit_fields(vals: Dict[str, float]) -> None:
    vals["Gross_Profit_ExVAT"] = vals.get("Price_ExVAT", 0.0) - vals.get("COGS_ExVAT", 0.0)
    vals["Contribution_Profit_ExVAT"] = (
        vals.get("Price_ExVAT", 0.0)
        - vals.get("COGS_ExVAT", 0.0)
        + vals.get("FBA_Fee_ExVAT", 0.0)
        + vals.get("Commission_ExVAT", 0.0)
        + vals.get("Digital_Fee_ExVAT", 0.0)
        + vals.get("Shipping_ExVAT", 0.0)
        + vals.get("Gift_ExVAT", 0.0)
        + vals.get("Promotion_ExVAT", 0.0)
    )


def _load_sellerboard_cogs_total(compare_date: str) -> float:
    if not SELLERBOARD_ORDERS.exists():
        return 0.0
    sb = pd.read_csv(SELLERBOARD_ORDERS, sep=";", dtype=str).fillna("")
    sb.columns = [c.strip('"') for c in sb.columns]
    if "Order date" not in sb.columns or "Cost of Goods" not in sb.columns:
        return 0.0
    sb["date"] = pd.to_datetime(sb["Order date"], errors="coerce", dayfirst=True).dt.strftime("%Y-%m-%d")
    sb_day = sb[sb["date"] == compare_date].copy()
    if sb_day.empty:
        return 0.0
    cogs = pd.to_numeric(sb_day["Cost of Goods"].str.replace(",", ".", regex=False), errors="coerce").fillna(0.0)
    return float(cogs.sum())


def _apply_subscription_from_txn(vals: Dict[str, float], compare_date: str) -> None:
    if not TXN_CATEGORY_LEDGER.exists():
        return
    tx = pd.read_csv(TXN_CATEGORY_LEDGER, dtype=str).fillna("")
    if tx.empty:
        return
    tx["date"] = pd.to_datetime(tx.get("posted_date"), errors="coerce", utc=True).dt.strftime("%Y-%m-%d")
    tx = tx[tx["date"] == compare_date].copy()
    if tx.empty:
        return
    sub = tx[(tx["category"] == "Service_Fee") & (tx["description"].str.contains("Subscription", na=False))].copy()
    if sub.empty:
        return
    sub["amount"] = pd.to_numeric(sub.get("amount_value"), errors="coerce").fillna(0.0)
    total = float(sub["amount"].sum())
    exvat = round(total / 1.2, 2)
    vat = round(total - exvat, 2)
    vals["Subscription_Fee_Total"] = vals.get("Subscription_Fee_Total", 0.0) + total
    vals["Subscription_Fee_ExVAT"] = vals.get("Subscription_Fee_ExVAT", 0.0) + exvat
    vals["Subscription_Fee_VAT"] = vals.get("Subscription_Fee_VAT", 0.0) + vat


def main() -> None:
    if not PNL_DAILY.exists():
        raise SystemExit("missing out/pnl_daily.csv")
    if not MANUAL.exists():
        raise SystemExit("missing out/amazon_profitandloss_2026_01_manual.csv")

    pnl = pd.read_csv(PNL_DAILY, dtype=str).fillna("")
    if COMPARE_DATE not in pnl.columns:
        raise SystemExit(f"date column {COMPARE_DATE} not in pnl_daily.csv")

    system_vals: Dict[str, float] = {}
    for _, row in pnl.iterrows():
        key = str(row.get("Parameter/Date", "")).strip()
        if not key:
            continue
        try:
            system_vals[key] = float(row.get(COMPARE_DATE) or 0.0)
        except Exception:
            system_vals[key] = 0.0

    manual_vals: Dict[str, float] = {}
    if MANUAL_COMPARISON.exists() and COMPARE_DATE == "2026-01-01":
        comp = pd.read_csv(MANUAL_COMPARISON, dtype=str).fillna("")
        manual_vals = _build_manual_values_from_comparison(comp)
    else:
        manual = pd.read_csv(MANUAL, dtype=str).fillna("")
        manual["date"] = pd.to_datetime(manual.get("Date"), errors="coerce", utc=True).dt.strftime("%Y-%m-%d")
        manual_day = manual[manual["date"] == COMPARE_DATE].copy()
        manual_vals = _build_manual_values(manual_day)
    _apply_subscription_from_txn(manual_vals, COMPARE_DATE)

    # Override Amazon-side COGS with Sellerboard totals when available.
    sb_cogs_total = _load_sellerboard_cogs_total(COMPARE_DATE)
    if sb_cogs_total != 0.0:
        manual_vals["COGS_Total"] = sb_cogs_total
        manual_vals["COGS_ExVAT"] = sb_cogs_total
        manual_vals["COGS_VAT"] = 0.0
    _derive_profit_fields(manual_vals)

    rows: List[Dict[str, object]] = []
    for name in ROWS:
        rows.append(
            {
                "Parameter/Date": name,
                f"{COMPARE_DATE} System": round(system_vals.get(name, 0.0), 2),
                f"{COMPARE_DATE} Amazon": round(manual_vals.get(name, 0.0), 2),
                f"{COMPARE_DATE} Delta": round(manual_vals.get(name, 0.0) - system_vals.get(name, 0.0), 2),
            }
        )

    out = pd.DataFrame(rows)
    out_path = Path(f"out/pnl_side_by_side_{COMPARE_DATE}.csv")
    out.to_csv(out_path, index=False)

    try:
        client = gspread.service_account(filename=str(Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json"))
        sheet = client.open_by_key(PNL_SHEET_ID)
        payload = [list(out.columns)] + out.where(pd.notnull(out), "").values.tolist()
        for attempt in range(1, SHEETS_MAX_RETRIES + 1):
            try:
                try:
                    ws = sheet.worksheet(PNL_SIDE_BY_SIDE_TAB)
                except gspread.WorksheetNotFound:
                    ws = sheet.add_worksheet(title=PNL_SIDE_BY_SIDE_TAB, rows=max(len(payload) + 10, 2000), cols=max(len(out.columns) + 5, 40))
                else:
                    ws.clear()
                ws.update(range_name="A1", values=payload, value_input_option="USER_ENTERED")
                break
            except APIError:
                if attempt == SHEETS_MAX_RETRIES:
                    raise
                import time

                time.sleep(SHEETS_BACKOFF * attempt)
    except Exception as exc:
        print({"status": "warning", "alert": "sheets_error", "error": str(exc)})

    print({"status": "success", "rows": len(out), "snapshot": str(out_path), "date": COMPARE_DATE, "tab": PNL_SIDE_BY_SIDE_TAB})


if __name__ == "__main__":
    main()

