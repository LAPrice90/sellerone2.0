"""
Build fee detail ledger from Finances v2024 transactions breakdowns (API-only).

Output:
- out/fee_detail_ledger_api.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from scripts.core.safe_file_writes import safe_to_csv


IN_BREAKDOWNS = Path("out/financial_transactions_v2024_breakdowns.csv")
OUT_LEDGER = Path("out/fee_detail_ledger_api.csv")
OUT_COLS = [
    "date",
    "posted_date",
    "transaction_id",
    "fee_type",
    "amount_total",
    "amount_base",
    "amount_vat",
    "currency",
    "non_gbp_api_only",
    "inbound_shipment_id",
]


def _vat_split(amount: float) -> tuple[float, float]:
    base = amount / 1.2
    vat = amount - base
    return base, vat


def main() -> None:
    if not IN_BREAKDOWNS.exists():
        raise FileNotFoundError(f"Missing input: {IN_BREAKDOWNS}")

    df = pd.read_csv(IN_BREAKDOWNS)
    if df.empty:
        safe_to_csv(pd.DataFrame(columns=OUT_COLS), OUT_LEDGER, index=False)
        print({"status": "warning", "rows": 0, "ledger": str(OUT_LEDGER)})
        return

    df = df[
        (df["transaction_type"] == "ServiceFee")
        & (df["breakdown_type"] == "Expenses")
        & df["breakdown_amount"].notna()
        & (df["breakdown_amount"] != 0)
    ].copy()

    if df.empty:
        safe_to_csv(pd.DataFrame(columns=OUT_COLS), OUT_LEDGER, index=False)
        print({"status": "warning", "rows": 0, "ledger": str(OUT_LEDGER)})
        return

    df["posted_date"] = df["posted_date"].fillna("")
    df["date"] = pd.to_datetime(df["posted_date"], errors="coerce", utc=True).dt.date.astype(str)
    df["fee_type"] = df["description"].fillna("")
    df["amount_total"] = pd.to_numeric(df["breakdown_amount"], errors="coerce")
    df["currency"] = df["breakdown_currency"].fillna("")
    df["non_gbp_api_only"] = df["currency"].ne("GBP")

    base_vals = []
    vat_vals = []
    for amount, currency in zip(df["amount_total"], df["currency"]):
        if pd.isna(amount) or currency != "GBP":
            base_vals.append(None)
            vat_vals.append(None)
            continue
        base, vat = _vat_split(float(amount))
        base_vals.append(base)
        vat_vals.append(vat)

    df["amount_base"] = base_vals
    df["amount_vat"] = vat_vals

    for col in OUT_COLS:
        if col not in df.columns:
            df[col] = ""

    safe_to_csv(df[OUT_COLS], OUT_LEDGER, index=False)
    print({"status": "success", "rows": len(df), "ledger": str(OUT_LEDGER)})


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print({"status": "error", "error": str(exc)})
        sys.exit(1)

