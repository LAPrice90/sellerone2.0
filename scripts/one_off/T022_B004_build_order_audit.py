"""
Build a simple order audit CSV with the same schema as the legacy order_audit_split.csv.
Uses the latest Orders_raw and OrderItems_raw snapshots from B001 (out/orders_raw.csv, out/order_items_raw.csv).
Populates core identifiers and amounts; leaves non-derived fee fields blank for now.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import pandas as pd


AUDIT_PATH = Path("out/order_audit_split.csv")
ORDERS_CSV = Path("out/orders_raw.csv")
ITEMS_CSV = Path("out/order_items_raw.csv")


HEADERS: List[str] = [
    "row_type",
    "order_id",
    "purchase_date",
    "order_status",
    "asin",
    "sku",
    "qty",
    "currency",
    "vat_rate",
    "cogs_used",
    "token_trace",
    "order_total_amount",
    "est_product_charges",
    "est_product_tax",
    "est_sales_proceeds",
    "est_commission",
    "est_commission_tax",
    "est_dsf",
    "est_dsf_tax",
    "est_fba_fee",
    "est_fba_fee_tax",
    "posted_product_charges",
    "posted_product_tax",
    "posted_sales_proceeds",
    "posted_commission",
    "posted_commission_tax",
    "posted_dsf",
    "posted_dsf_tax",
    "posted_fba_fee",
    "posted_fba_fee_tax",
    "revenue",
    "fees",
    "net",
    "principal_component",
    "tax_component",
    "shipping_component",
    "shipping_tax_component",
    "shipping_chargeback_component",
    "shipping_tax_chargeback_component",
    "shipping_net_component",
    "promotion_component",
    "commission_component",
    "commission_tax_component",
    "refund_commission_component",
    "fba_component",
    "fba_tax_component",
    "dsf_component",
    "dsf_tax_component",
    "other_fees_component",
    "refunds_component",
    "source_used",
    "gross_split_applied",
    "tax_estimated",
    "has_posted",
    "has_estimate",
    "fee_basis_includes_shipping",
    "vat_rate_source",
    "fee_vat_rounding",
    "discrepancy_flag",
    "revenue_header_delta",
    "export_run_ts",
    "estimator_version",
    "posted_date",
    "settlement_id",
    "item_price",
    "item_tax",
    "promo",
    "shipping_price",
    "shipping_tax",
    "order_total_currency",
    "is_estimate",
]

def load_summary() -> pd.DataFrame:
    path = Path("out/financial_fees_summary.csv")
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def main() -> None:
    if not ORDERS_CSV.exists() or not ITEMS_CSV.exists():
        raise FileNotFoundError("Orders CSV or OrderItems CSV not found. Run B001 first.")

    orders = pd.read_csv(ORDERS_CSV, dtype=str).fillna("")
    items = pd.read_csv(ITEMS_CSV, dtype=str).fillna("")
    summary = load_summary()
    summary_by_order = {}
    if not summary.empty:
        for _, r in summary.iterrows():
            summary_by_order[r.get("order_id", "")] = r

    merged = items.merge(
        orders,
        left_on="amazon_order_id",
        right_on="amazon_order_id",
        how="left",
        suffixes=("", "_order"),
    )

    rows = []
    export_ts = datetime.now(timezone.utc).isoformat()
    for _, r in merged.iterrows():
        item_price_amt = r.get("item_price_amount", "")
        item_tax_amt = r.get("item_tax_amount", "")
        shipping_price_amt = r.get("shipping_price_amount", "")
        shipping_tax_amt = r.get("shipping_tax_amount", "")
        promo_amt = r.get("promotion_discount_amount", "")
        currency = r.get("item_price_currency", "") or r.get("order_total_currency", "")
        order_id = r.get("amazon_order_id", "")
        sumrow = summary_by_order.get(order_id, {})
        principal = float(sumrow.get("principal", 0) or 0)
        shipping = float(sumrow.get("shipping", 0) or 0)
        giftwrap = float(sumrow.get("giftwrap", 0) or 0)
        tax = float(sumrow.get("tax", 0) or 0)
        shipping_tax = float(sumrow.get("shipping_tax", 0) or 0)
        giftwrap_tax = float(sumrow.get("giftwrap_tax", 0) or 0)
        referral_fee = float(sumrow.get("referral_fee", 0) or 0)
        referral_fee_tax = float(sumrow.get("referral_fee_tax", 0) or 0)
        fba_fee = float(sumrow.get("fba_fee", 0) or 0)
        fba_fee_tax = float(sumrow.get("fba_fee_tax", 0) or 0)
        dsf_fee = float(sumrow.get("dsf_fee", 0) or 0)
        dsf_fee_tax = float(sumrow.get("dsf_fee_tax", 0) or 0)
        fixed_fee = float(sumrow.get("fixed_fee", 0) or 0)
        other_fee = float(sumrow.get("other_fee", 0) or 0)

        posted_product_charges = principal
        posted_product_tax = tax
        posted_sales_proceeds = principal + tax + shipping + shipping_tax + giftwrap + giftwrap_tax
        posted_commission = referral_fee
        posted_commission_tax = referral_fee_tax
        posted_dsf = dsf_fee
        posted_dsf_tax = dsf_fee_tax
        posted_fba_fee = fba_fee
        posted_fba_fee_tax = fba_fee_tax
        revenue_val = posted_sales_proceeds
        fees_val = referral_fee + referral_fee_tax + dsf_fee + dsf_fee_tax + fba_fee + fba_fee_tax + fixed_fee + other_fee
        net_val = revenue_val + fees_val
        settlement_id = sumrow.get("settlement_id", "")
        posted_date = sumrow.get("posted_date", "")
        rows.append(
            {
                "row_type": "estimate",
                "order_id": r.get("amazon_order_id", ""),
                "purchase_date": r.get("purchase_date", ""),
                "order_status": r.get("order_status", ""),
                "asin": r.get("asin", ""),
                "sku": r.get("seller_sku", ""),
                "qty": r.get("quantity_ordered", ""),
                "currency": currency,
                "vat_rate": "",
                "cogs_used": "",
                "token_trace": "",
                "order_total_amount": r.get("order_total_amount", ""),
                "est_product_charges": item_price_amt,
                "est_product_tax": item_tax_amt,
                "est_sales_proceeds": "",
                "est_commission": "",
                "est_commission_tax": "",
                "est_dsf": "",
                "est_dsf_tax": "",
                "est_fba_fee": "",
                "est_fba_fee_tax": "",
                "posted_product_charges": posted_product_charges,
                "posted_product_tax": posted_product_tax,
                "posted_sales_proceeds": posted_sales_proceeds,
                "posted_commission": posted_commission,
                "posted_commission_tax": posted_commission_tax,
                "posted_dsf": posted_dsf,
                "posted_dsf_tax": posted_dsf_tax,
                "posted_fba_fee": posted_fba_fee,
                "posted_fba_fee_tax": posted_fba_fee_tax,
                "revenue": revenue_val,
                "fees": fees_val,
                "net": net_val,
                "principal_component": item_price_amt,
                "tax_component": item_tax_amt,
                "shipping_component": shipping_price_amt,
                "shipping_tax_component": shipping_tax_amt,
                "shipping_chargeback_component": "",
                "shipping_tax_chargeback_component": "",
                "shipping_net_component": "",
                "promotion_component": promo_amt,
                "commission_component": "",
                "commission_tax_component": "",
                "refund_commission_component": "",
                "fba_component": "",
                "fba_tax_component": "",
                "dsf_component": "",
                "dsf_tax_component": "",
                "other_fees_component": "",
                "refunds_component": "",
                "source_used": "estimate",
                "gross_split_applied": "False",
                "tax_estimated": "False",
                "has_posted": "False",
                "has_estimate": "True",
                "fee_basis_includes_shipping": "True",
                "vat_rate_source": "default",
                "fee_vat_rounding": "",
                "discrepancy_flag": "",
                "revenue_header_delta": "",
                "export_run_ts": export_ts,
                "estimator_version": "b004",
                "posted_date": posted_date,
                "settlement_id": settlement_id,
                "item_price": item_price_amt,
                "item_tax": item_tax_amt,
                "promo": promo_amt,
                "shipping_price": shipping_price_amt,
                "shipping_tax": shipping_tax_amt,
                "order_total_currency": currency,
                "is_estimate": "False" if sumrow else "True",
            }
        )

    audit_df = pd.DataFrame(rows, columns=HEADERS)
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    audit_df.to_csv(AUDIT_PATH, index=False)
    print(f"Wrote order audit to {AUDIT_PATH} with {len(audit_df)} rows")


if __name__ == "__main__":
    main()

