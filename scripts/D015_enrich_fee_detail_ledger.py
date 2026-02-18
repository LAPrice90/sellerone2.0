"""
Enrich fee detail ledger with SKU/ASIN/title where Order ID is available.

Outputs:
- out/fee_detail_ledger_enriched.csv
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

FEE_LEDGER = Path("out/fee_detail_ledger.csv")
ORDER_MASTER = Path("out/order_master.csv")
ORDER_LEDGER = Path("out/order_ledger_fx.csv")
PRODUCT_DB = Path("out/product_db_preview.csv")
OUT = Path("out/fee_detail_ledger_enriched.csv")


def _load_orders() -> pd.DataFrame:
    if ORDER_MASTER.exists():
        df = pd.read_csv(ORDER_MASTER, dtype=str).fillna("")
        cols = [c for c in ["Order ID", "SKU"] if c in df.columns]
        if cols:
            return df[cols].drop_duplicates()
    if ORDER_LEDGER.exists():
        df = pd.read_csv(ORDER_LEDGER, dtype=str).fillna("")
        cols = [c for c in ["Order ID", "SKU"] if c in df.columns]
        if cols:
            return df[cols].drop_duplicates()
    return pd.DataFrame(columns=["Order ID", "SKU"])


def _load_product_db() -> pd.DataFrame:
    if not PRODUCT_DB.exists():
        return pd.DataFrame(columns=["seller_sku", "asin", "title"])
    df = pd.read_csv(PRODUCT_DB, dtype=str).fillna("")
    cols = [c for c in ["seller_sku", "asin", "title"] if c in df.columns]
    if not cols:
        return pd.DataFrame(columns=["seller_sku", "asin", "title"])
    return df[cols].drop_duplicates()


def main() -> None:
    if not FEE_LEDGER.exists():
        print({"status": "skip", "reason": "missing_fee_detail_ledger"})
        return

    fee = pd.read_csv(FEE_LEDGER, dtype=str).fillna("")
    if fee.empty:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        fee.to_csv(OUT, index=False)
        print({"status": "success", "rows": 0, "out": str(OUT)})
        return

    orders = _load_orders()
    prod = _load_product_db()

    if "order_id" in fee.columns and "Order ID" in orders.columns:
        fee = fee.merge(orders, left_on="order_id", right_on="Order ID", how="left")
        fee = fee.drop(columns=["Order ID"], errors="ignore")
    if "SKU" not in fee.columns and "SKU_y" in fee.columns:
        fee = fee.rename(columns={"SKU_y": "SKU"})
    if "SKU_x" in fee.columns:
        fee = fee.drop(columns=["SKU_x"])

    if not prod.empty and "SKU" in fee.columns:
        prod = prod.rename(columns={"seller_sku": "SKU"})
        fee = fee.merge(prod, on="SKU", how="left")

    order_vals = fee.get("order_id", pd.Series([], dtype=str)).fillna("").astype(str).str.strip()
    order_vals = order_vals.replace({"---": ""})
    sku_vals = fee.get("SKU", pd.Series([], dtype=str)).fillna("").astype(str).str.strip()
    asin_vals = fee.get("asin", pd.Series([], dtype=str)).fillna("").astype(str).str.strip()
    title_vals = fee.get("title", pd.Series([], dtype=str)).fillna("").astype(str).str.strip()

    fee["has_order_link"] = order_vals.ne("").astype(int)
    fee["has_sku"] = sku_vals.ne("").astype(int)
    fee["has_asin"] = asin_vals.ne("").astype(int)
    fee["has_title"] = title_vals.ne("").astype(int)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fee = fee.fillna("")
    fee.to_csv(OUT, index=False)

    coverage = {
        "rows": len(fee),
        "order_linked": int(fee["has_order_link"].sum()),
        "sku_filled": int(fee["has_sku"].sum()),
        "asin_filled": int(fee["has_asin"].sum()),
        "title_filled": int(fee["has_title"].sum()),
    }
    print({"status": "success", "out": str(OUT), "coverage": coverage})


if __name__ == "__main__":
    main()
