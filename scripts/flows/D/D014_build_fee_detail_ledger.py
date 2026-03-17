"""
Build a fee detail ledger from the 90-day transactions export.

Outputs:
- out/fee_detail_ledger.csv
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

TRANSACTIONS_90D = Path("reference/Transactions in the last 90 days.csv")
OUT_LEDGER = Path("out/fee_detail_ledger.csv")

VAT_RATE_GB = 0.20


def _to_float(val: str) -> float:
    try:
        return float(val)
    except Exception:
        return 0.0


def _split_vat_gb(amount: float) -> tuple[float, float]:
    exvat = round(amount / (1.0 + VAT_RATE_GB), 2)
    vat = round(amount - exvat, 2)
    return exvat, vat


def main() -> None:
    if not TRANSACTIONS_90D.exists():
        print({"status": "skip", "reason": "missing_transactions_90d"})
        return

    df = pd.read_csv(TRANSACTIONS_90D, dtype=str).fillna("")
    if df.empty:
        print({"status": "skip", "reason": "empty_transactions_90d"})
        return

    df = df[df["Transaction type"] == "Service Fees"].copy()
    if df.empty:
        OUT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            columns=[
                "date",
                "transaction_type",
                "order_id",
                "fee_type",
                "product_details",
                "amount_total",
                "amount_exvat",
                "amount_vat",
                "currency",
                "vat_source",
                "source",
            ]
        ).to_csv(OUT_LEDGER, index=False)
        print({"status": "success", "rows": 0, "ledger": str(OUT_LEDGER)})
        return

    df["date"] = pd.to_datetime(df.get("Date"), errors="coerce", dayfirst=True).dt.strftime("%Y-%m-%d")
    df["amount_total"] = df.get("Total (GBP)", "").apply(_to_float)
    rows = []
    for _, r in df.iterrows():
        amount = float(r.get("amount_total") or 0.0)
        if amount == 0.0:
            continue
        exvat, vat = _split_vat_gb(amount)
        fee_type = str(r.get("Product Details") or "").strip() or "ServiceFee"
        rows.append(
            {
                "date": r.get("date") or "",
                "transaction_type": r.get("Transaction type") or "Service Fees",
                "order_id": r.get("Order ID") or "",
                "fee_type": fee_type,
                "product_details": r.get("Product Details") or "",
                "amount_total": round(amount, 2),
                "amount_exvat": exvat,
                "amount_vat": vat,
                "currency": "GBP",
                "vat_source": "derived_20pct_transactions",
                "source": "Transactions_90D",
            }
        )

    ledger = pd.DataFrame(rows)
    OUT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(OUT_LEDGER, index=False)
    print({"status": "success", "rows": len(ledger), "ledger": str(OUT_LEDGER)})


if __name__ == "__main__":
    main()

