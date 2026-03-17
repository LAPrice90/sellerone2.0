"""
Build order value discrepancy lists between Sellerboard export and Order_Master.

One-off script only. Do not call from daily loops.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(".")
OUT = ROOT / "out"

DEFAULT_SELLERBOARD = (
    ROOT
    / "reference"
    / "DRJ_Hardware_Dashboard_Order_Items_01_11_2025-03_02_2026_(2026_02_03_14_19_19_557).csv"
)
SELLERBOARD_CSV = Path(os.environ.get("SELLERBOARD_CSV", str(DEFAULT_SELLERBOARD)))
SB_COUNTRY_CODE = os.environ.get("SELLERBOARD_COUNTRY_CODE", "GB").strip().upper()
SB_CURRENCY_CODE = os.environ.get("SELLERBOARD_CURRENCY_CODE", "GBP").strip().upper()

ORDER_MASTER = OUT / "order_master.csv"
L3_RAW = OUT / "financial_events_level3_raw.csv"
REVIEWED = OUT / "order_value_discrepancies_reviewed.csv"
ALL_OUT = OUT / "order_value_discrepancies_all.csv"
OPEN_OUT = OUT / "order_value_discrepancies_open.csv"


def _to_num(val: Optional[str]) -> float:
    if val is None:
        return 0.0
    s = str(val).strip()
    if s in ("", "nan", "None"):
        return 0.0
    # strip currency symbols and commas
    s = s.replace("Â£", "").replace("$", "").replace(",", "")
    try:
        return float(s)
    except Exception:
        return 0.0


def _read_sellerboard(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Sellerboard CSV not found: {path}")
    df = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8", encoding_errors="replace")
    # normalize required columns
    df.columns = [c.strip() for c in df.columns]
    return df


def _read_order_master(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"order_master.csv not found: {path}")
    return pd.read_csv(path, dtype=str)


def main() -> None:
    sb = _read_sellerboard(SELLERBOARD_CSV)
    om = _read_order_master(ORDER_MASTER)

    # Chargebacks from Level 3 raw (ShippingChargeback, GiftwrapChargeback, etc.)
    chargebacks = pd.DataFrame(columns=["Order ID", "chargeback_total"])
    l3_orders = None
    if L3_RAW.exists():
        try:
            raw = pd.read_csv(L3_RAW, dtype=str)
            l3_orders = set(raw.get("order_id", pd.Series(dtype=str)).dropna().astype(str).tolist())
            cb_types = {"ShippingChargeback", "GiftwrapChargeback", "Chargeback"}
            raw_cb = raw[raw["amount_type"].isin(cb_types)].copy()
            if not raw_cb.empty:
                # De-dup identical chargeback lines that can appear twice in raw.
                raw_cb = raw_cb.drop_duplicates(
                    subset=["order_id", "amount_type", "amount", "posted_date", "transaction_type"]
                )
                raw_cb["cb_amt"] = raw_cb["amount"].apply(_to_num)
                chargebacks = (
                    raw_cb.groupby("order_id", as_index=False)[["cb_amt"]]
                    .sum()
                    .rename(columns={"order_id": "Order ID", "cb_amt": "chargeback_total"})
                )
            # Capture shipping chargebacks separately to net from shipping.
            raw_scb = raw[raw["amount_type"] == "ShippingChargeback"].copy()
            if not raw_scb.empty:
                raw_scb = raw_scb.drop_duplicates(
                    subset=["order_id", "amount_type", "amount", "posted_date", "transaction_type"]
                )
                raw_scb["scb_amt"] = raw_scb["amount"].apply(_to_num)
                shipping_cbs = (
                    raw_scb.groupby("order_id", as_index=False)[["scb_amt"]]
                    .sum()
                    .rename(columns={"order_id": "Order ID", "scb_amt": "shipping_chargeback_total"})
                )
            else:
                shipping_cbs = pd.DataFrame(columns=["Order ID", "shipping_chargeback_total"])
            # Capture negative shipping/ship tax credits to net from shipping.
            raw_ship_credit = raw[raw["amount_type"].isin(["Shipping", "ShippingCharge", "ShippingTax"])].copy()
            if not raw_ship_credit.empty:
                raw_ship_credit["ship_amt"] = raw_ship_credit["amount"].apply(_to_num)
                raw_ship_credit = raw_ship_credit[raw_ship_credit["ship_amt"] < 0]
                if not raw_ship_credit.empty:
                    raw_ship_credit = raw_ship_credit.drop_duplicates(
                        subset=["order_id", "amount_type", "amount", "posted_date", "transaction_type"]
                    )
                    ship_credits = (
                        raw_ship_credit.groupby("order_id", as_index=False)[["ship_amt"]]
                        .sum()
                        .rename(columns={"order_id": "Order ID", "ship_amt": "shipping_credit_total"})
                    )
                else:
                    ship_credits = pd.DataFrame(columns=["Order ID", "shipping_credit_total"])
            else:
                ship_credits = pd.DataFrame(columns=["Order ID", "shipping_credit_total"])
        except Exception:
            pass

    # Sellerboard: compare only orders where refunds are zero
    for col in ["Order number", "Units", "Refunds", "Sales"]:
        if col not in sb.columns:
            raise ValueError(f"Missing column in Sellerboard CSV: {col}")
    sb["units_num"] = sb["Units"].apply(_to_num)
    sb["refunds_num"] = sb["Refunds"].fillna("0").apply(_to_num)
    sb["sales_num"] = sb["Sales"].apply(_to_num)
    sb["shipping_num"] = sb["Shipping"].apply(_to_num) if "Shipping" in sb.columns else 0.0
    sb["promo_num"] = sb["Promo"].apply(_to_num) if "Promo" in sb.columns else 0.0
    sb = sb[(sb["units_num"] > 0) & (sb["refunds_num"] == 0)]
    sb["order_id_norm"] = (
        sb["Order number"]
        .fillna("")
        .astype(str)
        .str.split(" / ", n=1, expand=False)
        .str[0]
        .str.strip()
    )
    sb_totals = (
        sb.groupby("order_id_norm", as_index=False)[["sales_num", "shipping_num", "promo_num"]]
        .sum()
        .rename(columns={"sales_num": "sellerboard_sales", "shipping_num": "sellerboard_shipping", "promo_num": "sellerboard_promo"})
    )
    sb_totals["sellerboard_total"] = sb_totals["sellerboard_sales"] + sb_totals["sellerboard_shipping"] + sb_totals["sellerboard_promo"]

    # Order_master filters: exclude zero qty lines; match Sellerboard market/currency
    for col in ["Order ID", "Quantity Ordered", "Price_Total", "country_code", "currency_code"]:
        if col not in om.columns:
            raise ValueError(f"Missing column in order_master.csv: {col}")
    om["qty_num"] = om["Quantity Ordered"].apply(_to_num)
    # Use totals as-is (already VAT-inclusive in Order_Master).
    om["price_num"] = om["Price_Total"].apply(_to_num)
    om["shipping_num"] = om["Shipping_Total"].apply(_to_num) if "Shipping_Total" in om.columns else 0.0
    om["gift_num"] = om["Gift_Total"].apply(_to_num) if "Gift_Total" in om.columns else 0.0
    om["promo_num"] = om["Promotion_Total"].apply(_to_num) if "Promotion_Total" in om.columns else 0.0
    om = om[(om["qty_num"] > 0) & (om["country_code"].str.upper() == SB_COUNTRY_CODE) & (om["currency_code"].str.upper() == SB_CURRENCY_CODE)]
    om_totals = (
        om.groupby("Order ID", as_index=False)[["price_num", "shipping_num", "gift_num", "promo_num"]]
        .sum()
        .rename(
            columns={
                "price_num": "our_sales",
                "shipping_num": "our_shipping",
                "gift_num": "our_gift",
                "promo_num": "our_promo",
            }
        )
    )
    # Only compare orders that exist in Level 3 raw (avoids pending-only orders).
    if l3_orders:
        om_totals = om_totals[om_totals["Order ID"].isin(l3_orders)].copy()
        sb_totals = sb_totals[sb_totals["order_id_norm"].isin(l3_orders)].copy()
    om_totals["our_total"] = om_totals["our_sales"] + om_totals["our_shipping"] + om_totals["our_gift"] + om_totals["our_promo"]
    if not chargebacks.empty:
        om_totals = om_totals.merge(chargebacks, on="Order ID", how="left")
        om_totals["chargeback_total"] = om_totals["chargeback_total"].fillna(0.0)
    if "shipping_chargeback_total" in globals():
        om_totals = om_totals.merge(shipping_cbs, on="Order ID", how="left")
        om_totals["shipping_chargeback_total"] = om_totals["shipping_chargeback_total"].fillna(0.0)
        # Also net shipping chargeback into shipping to mirror Sellerboard.
        om_totals["our_shipping"] = om_totals["our_shipping"] + om_totals["shipping_chargeback_total"]
    if "shipping_credit_total" in globals():
        om_totals = om_totals.merge(ship_credits, on="Order ID", how="left")
        om_totals["shipping_credit_total"] = om_totals["shipping_credit_total"].fillna(0.0)
        # Net negative shipping/ship tax credits to match Sellerboard.
        om_totals["our_shipping"] = om_totals["our_shipping"] + om_totals["shipping_credit_total"]
    # Recompute totals after any chargeback/credit adjustments.
    if "chargeback_total" in om_totals.columns:
        om_totals["our_total"] = (
            om_totals["our_sales"]
            + om_totals["our_shipping"]
            + om_totals["our_gift"]
            + om_totals["our_promo"]
            + om_totals["chargeback_total"]
        )
    else:
        om_totals["our_total"] = (
            om_totals["our_sales"]
            + om_totals["our_shipping"]
            + om_totals["our_gift"]
            + om_totals["our_promo"]
        )

    # Compare
    merged = sb_totals.merge(om_totals, left_on="order_id_norm", right_on="Order ID", how="inner")
    # Compare rules:
    # - If Sellerboard shipping is negative, Sellerboard "sales" already includes shipping;
    #   compare SB sales to our sales+shipping (ignore SB negative shipping).
    # - If SB shipping/promo are zero, compare sales-only.
    # - Otherwise, compare full totals.
    ship_neg = merged["sellerboard_shipping"] < -0.01
    ship_or_promo = (merged["sellerboard_shipping"].abs() > 0.01) | (merged["sellerboard_promo"].abs() > 0.01)
    merged["sb_compare_total"] = merged["sellerboard_sales"]
    merged["our_compare_total"] = merged["our_sales"]
    merged.loc[ship_neg, "sb_compare_total"] = merged["sellerboard_sales"]
    merged.loc[ship_neg, "our_compare_total"] = merged["our_sales"] + merged["our_shipping"]
    merged.loc[ship_or_promo & ~ship_neg, "sb_compare_total"] = merged["sellerboard_total"]
    merged.loc[ship_or_promo & ~ship_neg, "our_compare_total"] = merged["our_total"]
    # Giftwrap: if SB has no ship/promo, SB sales usually includes giftwrap.
    no_ship_promo = ~ship_or_promo
    merged.loc[no_ship_promo, "our_compare_total"] = merged["our_sales"] + merged["our_gift"]
    merged["diff"] = merged["our_compare_total"] - merged["sb_compare_total"]
    merged["diff_abs"] = merged["diff"].abs()
    diffs = merged[merged["diff_abs"] > 0.01].copy()
    # Drop known irrelevant mismatches where Sellerboard nets shipping chargebacks.
    ship_diff = diffs["sellerboard_shipping"]
    irrelevant = (ship_diff < -0.01) & ((diffs["diff"] - (-ship_diff)).abs() <= 0.02)
    diffs = diffs[~irrelevant].copy()
    # Ignore tiny rounding noise.
    diffs = diffs[diffs["diff"].abs() > 0.6].copy()
    # When Sellerboard shows negative shipping, allow small residuals caused by
    # chargeback/shipping presentation differences.
    diffs = diffs[~((diffs["sellerboard_shipping"] < -0.01) & (diffs["diff"].abs() <= 5.0))].copy()
    diffs = diffs.sort_values(by="diff_abs", ascending=False)
    diffs = diffs.drop(columns=["diff_abs"])

    # Write all discrepancies
    OUT.mkdir(parents=True, exist_ok=True)
    diffs.to_csv(ALL_OUT, index=False)

    # Filter out reviewed
    if REVIEWED.exists() and REVIEWED.stat().st_size > 0:
        reviewed = pd.read_csv(REVIEWED, dtype=str)
        reviewed_ids = set(reviewed.get("Order ID", reviewed.get("Order number", [])))
    else:
        reviewed_ids = set()
    open_diffs = diffs[~diffs["Order ID"].isin(reviewed_ids)].copy()
    open_diffs.to_csv(OPEN_OUT, index=False)

    print({"status": "success", "all": str(ALL_OUT), "open": str(OPEN_OUT), "count_all": len(diffs), "count_open": len(open_diffs)})


if __name__ == "__main__":
    main()

