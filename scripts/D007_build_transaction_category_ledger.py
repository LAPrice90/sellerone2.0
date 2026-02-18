"""
Normalize Finances v2024 breakdowns into a category ledger for analysis.

Inputs:
- out/financial_transactions_v2024_breakdowns.csv

Outputs:
- out/transaction_category_ledger.csv
- out/transaction_category_summary.csv
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


BREAKDOWNS = Path("out/financial_transactions_v2024_breakdowns.csv")
OUT_LEDGER = Path("out/transaction_category_ledger.csv")
OUT_SUMMARY = Path("out/transaction_category_summary.csv")
OUT_UNMAPPED = Path("out/transaction_category_unmapped.csv")
OUT_MAPPING = Path("out/transaction_category_mapping.csv")

SERVICE_FEE_MAP = [
    ("FBAPostInboundTransportation", "Inbound_Transportation_Fee"),
    ("FBAInboundTransportation", "Inbound_Transportation_Fee"),
    ("FBALongTermStorageBilling", "Storage_Charges"),
    ("FBALongTermStorageFee", "Storage_Charges"),
    ("FBAStorageBilling", "Storage_Charges"),
    ("FBAStorageFee", "Storage_Charges"),
    ("FBARemoval", "Removal_Fee"),
    ("FBADisposalFee", "Disposal_Fee"),
    ("FBADisposal", "Disposal_Fee"),
    ("CustomerReturnHRRUnitFee", "Customer_Returns_Fee"),
    ("CustomerReturnHRREvent", "Customer_Returns_Fee"),
    ("Customer Returns Fee", "Customer_Returns_Fee"),
    ("Subscription", "Subscription_Fee"),
]


def _to_float(val: str) -> float:
    try:
        return float(val)
    except Exception:
        return 0.0


def _category(row: pd.Series) -> tuple[str, str]:
    tx = str(row.get("transaction_type", "") or "")
    br = str(row.get("breakdown_type", "") or "")
    desc = str(row.get("description", "") or "")

    if tx == "Shipment":
        if br == "Sales":
            return "Shipment_Sales", "sales"
        if br == "Expenses":
            return "Shipment_Expenses", "fees"
        return "Shipment_Other", "fees"

    if tx == "Refund":
        if br == "Refunded Sales":
            return "Refund_Sales", "refunds"
        if br == "Refunded Expenses":
            return "Refund_Expenses", "refunds"
        if "RefundCommission" in desc or "RefundCommission" == br:
            return "Refund_Commission", "refunds"
        return "Refund_Other", "refunds"

    if tx == "ServiceFee":
        for needle, category in SERVICE_FEE_MAP:
            if needle in desc:
                return category, "fees"
        return "Service_Fee_Unmapped", "fees"

    if tx == "FBAInventoryReimbursement":
        if "WAREHOUSE_LOST" in desc:
            return "Warehouse_Lost_Reimbursement", "reimbursements"
        if "REVERSAL_REIMBURSEMENT" in desc:
            return "Reversal_Reimbursement", "reimbursements"
        return "Inventory_Reimbursement", "reimbursements"

    if tx == "Retrocharge":
        if "RetroChargeRefund" in desc:
            return "Refund_Retrocharge", "refunds"
        return "Retrocharge", "fees"

    if tx == "Compensation":
        if "COMPENSATED_CLAWBACK" in desc:
            return "Compensated_Clawback", "fees"
        return "Compensation", "fees"

    if tx == "Chargeback":
        if "ShippingChargeback" in desc:
            return "Shipping_Chargeback", "fees"
        return "Chargeback", "fees"

    if tx == "Transfer":
        if "Disbursement" in desc:
            return "Disbursement", "transfer"
        return "Transfer", "transfer"

    return f"Other_{tx or 'Unknown'}", "other"


def main() -> None:
    if not BREAKDOWNS.exists():
        print({"status": "skip", "reason": "missing_financial_transactions_v2024_breakdowns"})
        return

    df = pd.read_csv(BREAKDOWNS, dtype=str).fillna("")
    if df.empty:
        print({"status": "skip", "reason": "empty_financial_transactions_v2024_breakdowns"})
        return

    df["amount_value"] = df.get("breakdown_amount", "").apply(_to_float)
    categories = df.apply(_category, axis=1, result_type="expand")
    df["category"] = categories[0]
    df["category_group"] = categories[1]

    ledger = df[
        [
            "posted_date",
            "transaction_type",
            "breakdown_type",
            "description",
            "amount_value",
            "breakdown_currency",
            "category",
            "category_group",
            "inbound_shipment_id",
        ]
    ].rename(columns={"breakdown_currency": "currency"})

    OUT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(OUT_LEDGER, index=False)

    summary = (
        ledger.groupby(["category", "category_group", "currency"], dropna=False)
        .agg(rows=("amount_value", "size"), amount_total=("amount_value", "sum"))
        .reset_index()
        .sort_values(by=["category_group", "category"])
    )
    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUT_SUMMARY, index=False)

    # Export mapping table for traceability.
    mapping_df = pd.DataFrame(SERVICE_FEE_MAP, columns=["description_contains", "category"])
    OUT_MAPPING.parent.mkdir(parents=True, exist_ok=True)
    mapping_df.to_csv(OUT_MAPPING, index=False)

    # Unmapped fee audit.
    unmapped = ledger[(ledger["transaction_type"] == "ServiceFee") & (ledger["category"] == "Service_Fee_Unmapped")].copy()
    OUT_UNMAPPED.parent.mkdir(parents=True, exist_ok=True)
    unmapped.to_csv(OUT_UNMAPPED, index=False)

    print(
        {
            "status": "success",
            "rows": len(ledger),
            "summary_rows": len(summary),
            "ledger": str(OUT_LEDGER),
            "summary": str(OUT_SUMMARY),
            "mapping": str(OUT_MAPPING),
            "unmapped": str(OUT_UNMAPPED),
        }
    )


if __name__ == "__main__":
    main()
