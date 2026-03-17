"""
Build a daily ledger of unallocated transaction expenses.

Inputs:
- out/transaction_expense_allocations.csv

Outputs:
- out/transaction_unallocated_daily.csv
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ALLOC_PATH = Path("out/transaction_expense_allocations.csv")
OUT_PATH = Path("out/transaction_unallocated_daily.csv")


def main() -> None:
    if not ALLOC_PATH.exists():
        print({"status": "skip", "reason": "missing_transaction_expense_allocations"})
        return
    df = pd.read_csv(ALLOC_PATH, dtype=str).fillna("")
    if df.empty:
        print({"status": "skip", "reason": "empty_transaction_expense_allocations"})
        return
    df = df[df["status"] == "unallocated"].copy()
    if df.empty:
        print({"status": "skip", "reason": "no_unallocated_rows"})
        return
    df["date"] = pd.to_datetime(df["posted_date"], errors="coerce", utc=True).dt.strftime("%Y-%m-%d")
    df["amount_value"] = pd.to_numeric(df.get("amount_value"), errors="coerce").fillna(0.0)
    daily = (
        df.groupby(["date", "transaction_type", "breakdown_type", "currency"], dropna=False)
        .agg(rows=("amount_value", "size"), amount_total=("amount_value", "sum"))
        .reset_index()
        .sort_values(by=["date", "transaction_type", "breakdown_type"])
    )
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    daily.to_csv(OUT_PATH, index=False)
    print({"status": "success", "rows": len(daily), "out": str(OUT_PATH)})


if __name__ == "__main__":
    main()

