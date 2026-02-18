"""
Build a fee VAT ledger from financial_events_level3_* (Finances API).
Outputs:
  - out/fee_vat_ledger.csv (line-level fee + VAT)
  - out/fee_vat_summary_daily.csv (daily totals)
  - out/fee_vat_summary_type.csv (by transaction_type / amount_type)
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def _load_source() -> Path:
    cand = [
        Path("out/financial_events_level3_raw_dedup.csv"),
        Path("out/financial_events_level3_raw.csv"),
    ]
    for p in cand:
        if p.exists():
            return p
    raise FileNotFoundError("No financial_events_level3_raw(_dedup).csv found in out/")


def main() -> None:
    src = _load_source()
    df = pd.read_csv(src)

    # Normalize numeric fields
    df["amount"] = pd.to_numeric(df.get("amount"), errors="coerce").fillna(0.0)
    df["tax_amount"] = pd.to_numeric(df.get("tax_amount"), errors="coerce").fillna(0.0)

    # Fee lines only
    fees = df[df.get("is_fee", False) == True].copy()  # noqa: E712

    # Add computed totals
    fees["fee_ex_vat"] = fees["amount"]
    fees["fee_vat"] = fees["tax_amount"]
    fees["fee_total"] = fees["amount"] + fees["tax_amount"]

    # Keep useful columns
    keep_cols = [
        "posted_date",
        "order_id",
        "sku",
        "asin",
        "transaction_type",
        "amount_type",
        "currency",
        "tax_currency",
        "fee_ex_vat",
        "fee_vat",
        "fee_total",
    ]
    for col in keep_cols:
        if col not in fees.columns:
            fees[col] = ""
    fees = fees[keep_cols].copy()

    out_dir = Path("out")
    out_dir.mkdir(parents=True, exist_ok=True)

    ledger_path = out_dir / "fee_vat_ledger.csv"
    fees.to_csv(ledger_path, index=False)

    # Daily summary
    fees["posted_date_day"] = fees["posted_date"].astype(str).str[:10]
    daily = (
        fees.groupby("posted_date_day", dropna=False)[["fee_ex_vat", "fee_vat", "fee_total"]]
        .sum()
        .reset_index()
        .rename(columns={"posted_date_day": "date"})
    )
    daily_path = out_dir / "fee_vat_summary_daily.csv"
    daily.to_csv(daily_path, index=False)

    # Type summary
    type_summary = (
        fees.groupby(["transaction_type", "amount_type"], dropna=False)[["fee_ex_vat", "fee_vat", "fee_total"]]
        .sum()
        .reset_index()
    )
    type_path = out_dir / "fee_vat_summary_type.csv"
    type_summary.to_csv(type_path, index=False)

    print(json.dumps({
        "status": "success",
        "source": str(src),
        "rows": len(fees),
        "ledger": str(ledger_path),
        "daily_summary": str(daily_path),
        "type_summary": str(type_path),
    }, indent=2))


if __name__ == "__main__":
    main()
