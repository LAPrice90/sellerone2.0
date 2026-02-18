"""
Rebuild Level 1 and Level 2 from archived orders/items only (no API calls).

Inputs:
- out/orders_all.csv
- out/order_items_all.csv
- out/product_db_preview.csv

Outputs:
- out/financial_events_level1.csv (Level_1_Immediate sheet)
- out/financial_events_level2.csv (Level_2_Official sheet)
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd

import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

b002 = importlib.import_module("scripts.B002_run_pending_orders_to_sheet")
from scripts.rebuild_level1_from_archive import (
    build_level1,
    get_gspread_client,
    write_tab_with_retry,
    LEVEL1_TAB,
)

ORDERS_ALL = Path("out/orders_all.csv")
ITEMS_ALL = Path("out/order_items_all.csv")
PRODUCT_DB_PATH = Path("out/product_db_preview.csv")

OUT_LEVEL1 = Path("out/financial_events_level1.csv")
OUT_LEVEL2 = Path("out/financial_events_level2.csv")

SHEET_ID = "1BHueJTk4dvvhIXypzh6i2hQTgc0pB3DWj2khQ2IT6_A"
LEVEL2_TAB = "Level_2_Official"


def load_product_db() -> Dict[str, Dict[str, str]]:
    if not PRODUCT_DB_PATH.exists():
        return {}
    pdf = pd.read_csv(PRODUCT_DB_PATH, dtype=str).fillna("")
    product_db: Dict[str, Dict[str, str]] = {}
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
            "last_withheld_vat_flag": row.get("last_withheld_vat_flag"),
        }
    return product_db


def filter_level2_has_money(df: pd.DataFrame) -> pd.DataFrame:
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

    def _has_money(row) -> bool:
        return any(str(row.get(c, "")).strip() not in ("", "nan", "None") for c in money_cols)

    return df[df.apply(_has_money, axis=1)]


def backfill_level2_dsf(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    for idx, row in df.iterrows():
        if str(row.get("Digital_Fee_Total", "")).strip() not in ("", "nan", "None"):
            continue
        if str(row.get("marketplace_id", "")) != b002.UK_MARKETPLACE_ID:
            continue
        try:
            fba_ex_val = float(row.get("FBA_Fee_ExVAT", "") or 0.0)
            comm_ex_val = float(row.get("Commission_ExVAT", "") or 0.0)
            base_ex = fba_ex_val + comm_ex_val
            if base_ex <= 0:
                continue
            dsf_ex_val = b002.round_half_up(base_ex * 0.02, 2)
            dsf_vat_val = b002.round_half_up(dsf_ex_val * b002.VAT_DEFAULT, 2)
            dsf_total_val = dsf_ex_val + dsf_vat_val
            df.at[idx, "Digital_Fee_ExVAT"] = f"{dsf_ex_val:.2f}"
            df.at[idx, "Digital_Fee_VAT"] = f"{dsf_vat_val:.2f}"
            df.at[idx, "Digital_Fee_Total"] = f"{dsf_total_val:.2f}"
        except Exception:
            continue
    return df


def main() -> None:
    if not ORDERS_ALL.exists() or not ITEMS_ALL.exists():
        print("orders_all.csv or order_items_all.csv missing")
        return

    orders = pd.read_csv(ORDERS_ALL, dtype=str).fillna("")
    items = pd.read_csv(ITEMS_ALL, dtype=str).fillna("")
    product_db = load_product_db()

    # Level 1 rebuild
    df_level1 = build_level1(orders, items, product_db)
    OUT_LEVEL1.parent.mkdir(parents=True, exist_ok=True)
    df_level1.to_csv(OUT_LEVEL1, index=False)

    # Level 2 rebuild (archive only)
    b002.PRODUCT_DB = {
        k: {
            "fba_fee_10": v.get("fba_fee_10"),
            "fba_fee_100": v.get("fba_fee_100"),
            "last_fba_fee_ex_vat": v.get("last_fba_fee_ex_vat"),
            "last_fba_fee_ex_vat_10": v.get("last_fba_fee_ex_vat_10"),
            "last_fba_fee_ex_vat_100": v.get("last_fba_fee_ex_vat_100"),
            "referral_fee_10": v.get("referral_fee_10"),
            "referral_fee_100": v.get("referral_fee_100"),
            "last_commission_pct": v.get("last_commission_pct"),
            "last_commission_pct_10": v.get("last_commission_pct_10"),
            "last_commission_pct_100": v.get("last_commission_pct_100"),
            "vat_rate": v.get("vat_rate"),
            "last_withheld_vat_flag": v.get("last_withheld_vat_flag"),
        }
        for k, v in product_db.items()
    }
    df_level2 = b002.build_level2(orders, items)
    df_level2 = filter_level2_has_money(df_level2)
    df_level2 = b002._backfill_fees_from_level3(df_level2)
    df_level2 = backfill_level2_dsf(df_level2)
    df_level2.to_csv(OUT_LEVEL2, index=False)

    try:
        client = get_gspread_client()
        sheet = client.open_by_key(SHEET_ID)
        write_tab_with_retry(sheet, LEVEL1_TAB, df_level1)
        write_tab_with_retry(sheet, LEVEL2_TAB, df_level2)
    except Exception as exc:
        print({"status": "warning", "alert": "sheets_error", "error": str(exc)})

    print({"status": "success", "rows_l1": len(df_level1), "rows_l2": len(df_level2)})


if __name__ == "__main__":
    main()
