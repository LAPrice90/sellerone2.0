"""
Build an audit view combining Order_Master FX and withheld VAT lines.

Outputs:
- Sheet tab Order_Master_Audit (default)
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import List

import pandas as pd
import gspread
from gspread.exceptions import APIError


ORDER_FX = Path("out/order_ledger_fx.csv")
FIN_FX = Path("out/financial_ledger_fx.csv")

SHEET_ID = os.environ.get("ORDER_MASTER_SHEET_ID", "1BHueJTk4dvvhIXypzh6i2hQTgc0pB3DWj2khQ2IT6_A")
TAB_NAME = os.environ.get("ORDER_MASTER_AUDIT_TAB", "Order_Master_Audit")

SHEETS_MAX_RETRIES = 5
SHEETS_BACKOFF = 2.0


def get_gspread_client() -> gspread.Client:
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        cred_path = str(Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=cred_path)


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
            time.sleep(SHEETS_BACKOFF * attempt)


def main() -> None:
    if not ORDER_FX.exists():
        print({"status": "error", "error": "missing order_ledger_fx.csv", "path": str(ORDER_FX)})
        return
    if not FIN_FX.exists():
        print({"status": "error", "error": "missing financial_ledger_fx.csv", "path": str(FIN_FX)})
        return

    orders = pd.read_csv(ORDER_FX, dtype=str)
    fins = pd.read_csv(FIN_FX, dtype=str)

    # Withheld VAT lines (Marketplace Facilitator)
    fins = fins[fins["amount_type"].astype(str).str.contains("MarketplaceFacilitatorVAT", case=False, na=False)].copy()
    if fins.empty:
        withheld = pd.DataFrame(columns=["Order ID", "SKU", "withheld_vat_native", "withheld_vat_gbp"])
    else:
        fins["amount"] = pd.to_numeric(fins["amount"], errors="coerce").fillna(0.0)
        fins["amount_gbp"] = pd.to_numeric(fins["amount_gbp"], errors="coerce").fillna(0.0)
        withheld = (
            fins.groupby(["order_id", "sku"], dropna=False)[["amount", "amount_gbp"]]
            .sum()
            .reset_index()
            .rename(
                columns={
                    "order_id": "Order ID",
                    "sku": "SKU",
                    "amount": "withheld_vat_native",
                    "amount_gbp": "withheld_vat_gbp",
                }
            )
        )

    out = orders.copy()
    out = out.rename(columns={"Order ID": "Order ID", "SKU": "SKU"})
    out = out.merge(withheld, on=["Order ID", "SKU"], how="left")
    out["withheld_vat_native"] = pd.to_numeric(out.get("withheld_vat_native"), errors="coerce").fillna(0.0)
    out["withheld_vat_gbp"] = pd.to_numeric(out.get("withheld_vat_gbp"), errors="coerce").fillna(0.0)
    eu_countries = {"IE", "DE", "FR", "ES", "IT", "NL", "SE", "PL", "BE", "AT", "DK", "FI", "PT", "LU", "GR", "CZ", "HU", "RO", "BG", "HR", "SI", "SK", "EE", "LV", "LT", "MT", "CY"}
    if "country_code" in out.columns:
        is_eu = out["country_code"].astype(str).isin(eu_countries)
        vat_cols = [c for c in ["Price_VAT", "Shipping_VAT", "Gift_VAT", "Promotion_VAT"] if c in out.columns]
        vat_cols_gbp = [c for c in ["Price_VAT_GBP", "Shipping_VAT_GBP", "Gift_VAT_GBP", "Promotion_VAT_GBP"] if c in out.columns]
        if vat_cols:
            vat_sum = out[vat_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).sum(axis=1)
            out.loc[is_eu & (out["withheld_vat_native"] == 0), "withheld_vat_native"] = vat_sum
        if vat_cols_gbp:
            vat_sum_gbp = out[vat_cols_gbp].apply(pd.to_numeric, errors="coerce").fillna(0.0).sum(axis=1)
            out.loc[is_eu & (out["withheld_vat_gbp"] == 0), "withheld_vat_gbp"] = vat_sum_gbp

    cols = [
        "Date",
        "Order ID",
        "lvl",
        "country_code",
        "currency_code",
        "SKU",
        "Quantity Ordered",
        "Price_Total",
        "Price_VAT",
        "Price_ExVAT",
        "Shipping_Total",
        "Shipping_VAT",
        "Shipping_ExVAT",
        "fx_rate_to_gbp",
        "Price_Total_GBP",
        "Price_VAT_GBP",
        "Price_ExVAT_GBP",
        "Shipping_Total_GBP",
        "Shipping_VAT_GBP",
        "Shipping_ExVAT_GBP",
        "withheld_vat_native",
        "withheld_vat_gbp",
    ]
    cols = [c for c in cols if c in out.columns]
    out = out[cols]

    try:
        client = get_gspread_client()
        sheet = client.open_by_key(SHEET_ID)
        write_tab_with_retry(sheet, TAB_NAME, out)
    except Exception as exc:
        print({"status": "warning", "alert": "sheets_error", "error": str(exc)})
        return

    print({"status": "success", "rows": len(out), "sheet_tab": TAB_NAME})


if __name__ == "__main__":
    main()
