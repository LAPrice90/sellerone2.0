"""
Build a normalized transaction ledger from Finances v2024 breakdowns.

Outputs:
- out/transaction_ledger.csv
- out/transaction_ledger_summary.csv
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd


TXN_BREAKDOWNS = Path("out/financial_transactions_v2024_breakdowns.csv")
OUT_LEDGER = Path("out/transaction_ledger.csv")
OUT_SUMMARY = Path("out/transaction_ledger_summary.csv")


def _to_float(val: str) -> float:
    try:
        return float(val)
    except Exception:
        return 0.0


def main() -> None:
    if not TXN_BREAKDOWNS.exists():
        print({"status": "skip", "reason": "missing_financial_transactions_breakdowns"})
        return

    df = pd.read_csv(TXN_BREAKDOWNS, dtype=str).fillna("")
    if df.empty:
        print({"status": "skip", "reason": "empty_financial_transactions_breakdowns"})
        return

    ledger = pd.DataFrame(
        {
            "posted_date": df.get("posted_date", ""),
            "transaction_id": df.get("transaction_id", ""),
            "transaction_type": df.get("transaction_type", ""),
            "breakdown_type": df.get("breakdown_type", ""),
            "amount": df.get("breakdown_amount", ""),
            "currency": df.get("breakdown_currency", ""),
            "description": df.get("description", ""),
            "inbound_shipment_id": df.get("inbound_shipment_id", ""),
        }
    )
    ledger["amount_value"] = ledger["amount"].apply(_to_float)
    ledger = ledger.sort_values(by=["posted_date", "transaction_type", "breakdown_type", "transaction_id"])

    OUT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(OUT_LEDGER, index=False)

    summary = (
        ledger.groupby(["transaction_type", "breakdown_type", "currency"], dropna=False)
        .agg(rows=("amount_value", "size"), amount_total=("amount_value", "sum"))
        .reset_index()
        .sort_values(by=["transaction_type", "breakdown_type"])
    )
    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUT_SUMMARY, index=False)

    print(
        {
            "status": "success",
            "rows": len(ledger),
            "summary_rows": len(summary),
            "ledger": str(OUT_LEDGER),
            "summary": str(OUT_SUMMARY),
        }
    )


if __name__ == "__main__":
    main()

