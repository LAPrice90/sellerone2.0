"""
Backfill Product_DB with banded FBA fee ex-VAT from Level 3 official data.

Writes:
- last_fba_fee_ex_vat_10 (<= Â£10 per unit)
- last_fba_fee_ex_vat_100 (> Â£10 per unit)
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP

import gspread
import pandas as pd


LEVEL3_OFFICIAL = Path("out/financial_events_level3_official.csv")
PRODUCT_DB_SHEET_ID = "1b7iREy92vF_a1Lw72g0SOGS7t4-IOSBeeoHetLTN43s"
PRODUCT_DB_TAB = "Product_DB"
UK_MARKETPLACE_ID = "A1F83G8C2ARO7P"


def get_gspread_client() -> gspread.Client:
    cred_path = Path("secrets/sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=str(cred_path))


def round_fee(val: float) -> str:
    try:
        return str(Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except Exception:
        return ""


def main() -> None:
    if not LEVEL3_OFFICIAL.exists():
        print({"status": "skip", "reason": "missing_level3_official"})
        return

    df = pd.read_csv(LEVEL3_OFFICIAL, dtype=str).fillna("")
    if df.empty:
        print({"status": "skip", "reason": "empty_level3_official"})
        return

    if "marketplace_id" in df.columns:
        df = df[df["marketplace_id"] == UK_MARKETPLACE_ID]

    df["__date"] = pd.to_datetime(df.get("Date"), errors="coerce", utc=True)
    df = df[df["SKU"].astype(str).str.len() > 0]
    df = df[df["__date"].notna()]
    if df.empty:
        print({"status": "skip", "reason": "no_valid_rows"})
        return

    df["__qty"] = pd.to_numeric(df.get("Quantity Ordered"), errors="coerce").fillna(1)
    df.loc[df["__qty"] <= 0, "__qty"] = 1
    df["__price_total"] = pd.to_numeric(df.get("Price_Total"), errors="coerce")
    df["__fba_ex"] = pd.to_numeric(df.get("FBA_Fee_ExVAT"), errors="coerce")
    df = df[df["__price_total"].notna() & df["__fba_ex"].notna()]
    if df.empty:
        print({"status": "skip", "reason": "missing_price_or_fba_fee"})
        return

    df["__unit_price"] = (df["__price_total"].abs() / df["__qty"]).round(2)
    df["__fba_unit"] = (df["__fba_ex"].abs() / df["__qty"]).round(2)
    df = df[df["__fba_unit"] > 0]

    bands = {
        "last_fba_fee_ex_vat_10": df[df["__unit_price"] <= 10.0],
        "last_fba_fee_ex_vat_100": df[df["__unit_price"] > 10.0],
    }

    client = get_gspread_client()
    sheet = client.open_by_key(PRODUCT_DB_SHEET_ID)
    ws = sheet.worksheet(PRODUCT_DB_TAB)
    rows = ws.get_all_values()
    if not rows:
        print({"status": "skip", "reason": "product_db_empty"})
        return

    headers = rows[0]
    idx = {h: i for i, h in enumerate(headers)}
    for col in [
        "last_fba_fee_ex_vat_10",
        "last_fba_fee_ex_vat_100",
        "last_fba_fee_updated",
        "last_fba_fee_source",
    ]:
        if col not in idx:
            idx[col] = len(headers)
            headers.append(col)
            for r in rows[1:]:
                while len(r) < len(headers):
                    r.append("")

    sku_idx = idx.get("seller_sku", -1)
    if sku_idx < 0:
        print({"status": "skip", "reason": "seller_sku_missing"})
        return

    sku_rows = {}
    for i, r in enumerate(rows[1:], start=1):
        if len(r) < len(headers):
            r.extend([""] * (len(headers) - len(r)))
        sku = r[sku_idx]
        if sku:
            sku_rows[sku] = i

    for field, bdf in bands.items():
        if bdf.empty:
            continue
        for sku, grp in bdf.groupby("SKU"):
            if sku not in sku_rows:
                continue
            window = grp.sort_values("__date").tail(10)
            counts = window["__fba_unit"].round(2).value_counts()
            if counts.empty:
                continue
            top = float(counts.index[0])
            recent_dt = window[window["__fba_unit"].round(2) == top]["__date"].max()
            fee_str = round_fee(top)
            dt_str = recent_dt.strftime("%Y-%m-%dT%H:%M:%SZ") if pd.notna(recent_dt) else ""
            row = rows[sku_rows[sku]]
            row[idx[field]] = fee_str
            row[idx["last_fba_fee_updated"]] = dt_str
            row[idx["last_fba_fee_source"]] = "Level3"

    ws.clear()
    ws.update(range_name="A1", values=[headers] + rows[1:])

    print({"status": "success", "rows": len(rows) - 1, "updated_at": datetime.now(timezone.utc).isoformat()})


if __name__ == "__main__":
    main()

