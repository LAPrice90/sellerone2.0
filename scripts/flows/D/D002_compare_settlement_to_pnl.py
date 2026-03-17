"""
Compare a settlement statement against current P&L coverage.

Outputs:
- out/settlement_fee_summary.csv
- out/settlement_vs_pnl_summary.csv
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd


DEFAULT_STATEMENT = Path("reference/549081020474.txt")
STATEMENT_PATH = Path(
    os.environ.get("SETTLEMENT_STATEMENT_PATH")
    or os.environ.get("FIN_L5_STATEMENT_PATH")
    or DEFAULT_STATEMENT
)
OUT_SUMMARY = Path("out/settlement_fee_summary.csv")
OUT_COMPARE = Path("out/settlement_vs_pnl_summary.csv")
ORDER_LEDGER_FX = Path("out/order_ledger_fx.csv")


def _to_float(val: str) -> float:
    try:
        return float(val)
    except Exception:
        return 0.0


def load_statement(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t", dtype=str).fillna("")


def extract_settlement_window(df: pd.DataFrame) -> Tuple[str, str]:
    if "settlement-start-date" in df.columns and "settlement-end-date" in df.columns:
        for _, row in df.iterrows():
            start = str(row.get("settlement-start-date") or "").strip()
            end = str(row.get("settlement-end-date") or "").strip()
            if start and end:
                return start, end
    return "", ""


def build_fee_rows(df: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, str]] = []
    def add_row(kind: str, amount_str: str, source: str, posted_date: str, txn_type: str, currency: str) -> None:
        if not amount_str:
            return
        rows.append(
            {
                "posted_date": posted_date,
                "transaction_type": txn_type,
                "fee_type": kind,
                "amount": amount_str,
                "currency": currency,
                "source": source,
            }
        )

    for _, r in df.iterrows():
        txn_type = str(r.get("transaction-type") or "").strip()
        posted_date = str(r.get("posted-date") or "").strip()
        currency = str(r.get("currency") or r.get("shipment-fee-currency") or r.get("breakdown_currency") or "").strip()
        if not txn_type:
            continue

        add_row(str(r.get("price-type") or ""), str(r.get("price-amount") or ""), "price", posted_date, txn_type, currency)
        add_row(
            str(r.get("item-related-fee-type") or ""),
            str(r.get("item-related-fee-amount") or ""),
            "item_fee",
            posted_date,
            txn_type,
            currency,
        )
        add_row(
            str(r.get("promotion-type") or ""),
            str(r.get("promotion-amount") or ""),
            "promotion",
            posted_date,
            txn_type,
            currency,
        )
        add_row(
            str(r.get("order-fee-type") or ""),
            str(r.get("order-fee-amount") or ""),
            "order_fee",
            posted_date,
            txn_type,
            currency,
        )
        add_row(
            str(r.get("shipment-fee-type") or ""),
            str(r.get("shipment-fee-amount") or ""),
            "shipment_fee",
            posted_date,
            txn_type,
            currency,
        )
        add_row(
            str(r.get("direct-payment-type") or ""),
            str(r.get("direct-payment-amount") or ""),
            "direct_payment",
            posted_date,
            txn_type,
            currency,
        )
        add_row(
            str(r.get("other-fee-reason-description") or txn_type),
            str(r.get("other-amount") or ""),
            "other",
            posted_date,
            txn_type,
            currency,
        )
        add_row(
            str(r.get("breakdown_type") or ""),
            str(r.get("breakdown_amount") or ""),
            "breakdown",
            posted_date,
            txn_type,
            currency,
        )
        amount_type = str(r.get("amount-type") or "").strip()
        amount_desc = str(r.get("amount-description") or "").strip()
        amount_val = str(r.get("amount") or "").strip()
        if amount_val:
            add_row(amount_desc or amount_type, amount_val, "amount", posted_date, txn_type, currency)
    return pd.DataFrame(rows)


def map_to_pnl_category(fee_type: str, txn_type: str) -> str:
    ft = fee_type.strip()
    if ft in ("Principal",):
        return "Price_Total"
    if ft in ("Tax", "MarketplaceFacilitatorVAT-Principal"):
        return "Price_VAT"
    if ft in ("Shipping",):
        return "Shipping_Total"
    if ft in ("ShippingTax", "MarketplaceFacilitatorVAT-Shipping"):
        return "Shipping_VAT"
    if ft in ("TaxDiscount",):
        return "Promotion_Total"
    if ft == "FBAPerUnitFulfillmentFee":
        return "FBA_Fee_Total"
    if ft == "Commission":
        return "Commission_Total"
    if ft in ("DigitalServicesFee", "Digital Services Fee"):
        return "Digital_Fee_Total"
    if ft == "RefundCommission":
        return "Refund_Commission"
    if ft == "ShippingChargeback":
        return "Shipping_Chargeback"
    if ft in ("StorageRenewalBilling", "StorageFee", "FBALongTermStorageBilling"):
        return "Storage_Charges"
    if ft in ("FBAInboundTransportationFee", "FBAInboundTransportationProgramFee"):
        return "Inbound Transportation Fee"
    if ft == "DisposalComplete":
        return "RemovalComplete"
    if ft in ("WAREHOUSE_LOST", "WAREHOUSE_DAMAGE"):
        return "WAREHOUSE_LOST"
    # transaction-level types
    if txn_type in (
        "Inbound Transportation Fee",
        "RemovalComplete",
        "WAREHOUSE_LOST",
        "REVERSAL_REIMBURSEMENT",
        "Order_Retrocharge",
        "Refund_Retrocharge",
        "COMPENSATED_CLAWBACK",
    ):
        return txn_type
    return "Other"


def build_pnl_comparison(start_date: str, end_date: str) -> pd.DataFrame:
    if not ORDER_LEDGER_FX.exists():
        return pd.DataFrame()
    df = pd.read_csv(ORDER_LEDGER_FX, dtype=str).fillna("")
    df["date"] = pd.to_datetime(df.get("Date"), errors="coerce", utc=True).dt.strftime("%Y-%m-%d")
    if start_date:
        start = pd.to_datetime(start_date, errors="coerce", utc=True, dayfirst=True).strftime("%Y-%m-%d")
        df = df[df["date"] >= start]
    if end_date:
        end = pd.to_datetime(end_date, errors="coerce", utc=True, dayfirst=True).strftime("%Y-%m-%d")
        df = df[df["date"] <= end]
    if df.empty:
        return pd.DataFrame()
    cols = [
        "Price_Total_GBP",
        "Price_VAT_GBP",
        "Shipping_Total_GBP",
        "Shipping_VAT_GBP",
        "Promotion_Total_GBP",
        "FBA_Fee_Total_GBP",
        "Commission_Total_GBP",
        "Digital_Fee_Total_GBP",
    ]
    totals = {}
    for col in cols:
        if col in df.columns:
            totals[col.replace("_GBP", "")] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).sum()
    return pd.DataFrame(
        [
            {"pnl_row": k, "pnl_total_gbp": round(v, 2), "start_date": start_date, "end_date": end_date}
            for k, v in totals.items()
        ]
    )


def main(statement_path: Path = STATEMENT_PATH) -> None:
    if not statement_path.exists():
        raise FileNotFoundError(statement_path)
    df = load_statement(statement_path)
    start_date, end_date = extract_settlement_window(df)
    fee_rows = build_fee_rows(df)
    if fee_rows.empty:
        print({"status": "skip", "reason": "no_fee_rows"})
        return
    fee_rows["amount_value"] = fee_rows["amount"].apply(_to_float)
    fee_rows["pnl_category"] = fee_rows.apply(lambda r: map_to_pnl_category(r["fee_type"], r["transaction_type"]), axis=1)
    summary = (
        fee_rows.groupby(["pnl_category", "fee_type", "transaction_type", "currency"], dropna=False)
        .agg(amount=("amount_value", "sum"), rows=("amount_value", "size"))
        .reset_index()
        .sort_values(by=["pnl_category", "fee_type"])
    )

    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUT_SUMMARY, index=False)

    pnl_compare = build_pnl_comparison(start_date, end_date)
    OUT_COMPARE.parent.mkdir(parents=True, exist_ok=True)
    pnl_compare.to_csv(OUT_COMPARE, index=False)

    print(
        {
            "status": "success",
            "statement": str(statement_path),
            "summary": str(OUT_SUMMARY),
            "pnl_compare": str(OUT_COMPARE),
            "window_start": start_date,
            "window_end": end_date,
        }
    )


if __name__ == "__main__":
    main()

