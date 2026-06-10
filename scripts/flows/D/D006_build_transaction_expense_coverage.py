"""
Build a daily coverage report for allocated vs unallocated transaction expenses.

Inputs:
- out/transaction_expense_allocations.csv

Outputs:
- out/transaction_expense_coverage_daily.csv
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.core.safe_file_writes import safe_to_csv


ALLOC_PATH = Path("out/transaction_expense_allocations.csv")
OUT_PATH = Path("out/transaction_expense_coverage_daily.csv")


def main() -> None:
    if not ALLOC_PATH.exists():
        print({"status": "skip", "reason": "missing_transaction_expense_allocations"})
        return

    df = pd.read_csv(ALLOC_PATH, dtype=str).fillna("")
    if df.empty:
        print({"status": "skip", "reason": "empty_transaction_expense_allocations"})
        return

    df["date"] = pd.to_datetime(df["posted_date"], errors="coerce", utc=True).dt.strftime("%Y-%m-%d")
    df["amount_value"] = pd.to_numeric(df.get("amount_value"), errors="coerce").fillna(0.0)
    df["allocated_amount"] = pd.to_numeric(df.get("allocated_amount"), errors="coerce").fillna(0.0)

    allocated = df[df["status"] == "allocated"].copy()
    unallocated = df[df["status"] == "unallocated"].copy()

    allocated_daily = (
        allocated.groupby(["date", "currency"], dropna=False)
        .agg(allocated_rows=("allocated_amount", "size"), allocated_total=("allocated_amount", "sum"))
        .reset_index()
    )
    unallocated_daily = (
        unallocated.groupby(["date", "currency"], dropna=False)
        .agg(unallocated_rows=("amount_value", "size"), unallocated_total=("amount_value", "sum"))
        .reset_index()
    )

    daily = pd.merge(allocated_daily, unallocated_daily, on=["date", "currency"], how="outer").fillna(0.0)
    daily["total_expenses"] = daily["allocated_total"] + daily["unallocated_total"]
    total_nonzero = daily["total_expenses"].replace(0.0, pd.NA)
    daily["allocated_pct"] = (daily["allocated_total"] / total_nonzero).fillna(0.0)

    daily = daily.sort_values(by=["date", "currency"])
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    safe_to_csv(daily, OUT_PATH, index=False)

    print({"status": "success", "rows": len(daily), "out": str(OUT_PATH)})


if __name__ == "__main__":
    main()

