"""
Allocate transaction-level expenses to SKUs when possible.

Inputs:
- out/transaction_ledger.csv
- out/inbound_shipment_contents.csv (optional: inbound_shipment_id, sku, quantity)

Outputs:
- out/transaction_expense_allocations.csv
- out/transaction_expense_allocation_summary.csv
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd

from scripts.core.safe_file_writes import safe_to_csv


TXN_LEDGER = Path("out/transaction_ledger.csv")
SHIPMENT_CONTENTS = Path("out/inbound_shipment_contents.csv")
OUT_ALLOC = Path("out/transaction_expense_allocations.csv")
OUT_SUMMARY = Path("out/transaction_expense_allocation_summary.csv")


def _to_float(val: str) -> float:
    try:
        return float(val)
    except Exception:
        return 0.0


def _load_shipment_map() -> Dict[str, List[Dict[str, object]]]:
    if not SHIPMENT_CONTENTS.exists():
        return {}
    df = pd.read_csv(SHIPMENT_CONTENTS, dtype=str).fillna("")
    required = {"inbound_shipment_id", "sku", "quantity"}
    if not required.issubset(df.columns):
        return {}
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0.0)
    shipment_map: Dict[str, List[Dict[str, object]]] = {}
    for _, r in df.iterrows():
        inbound_id = str(r.get("inbound_shipment_id") or "").strip()
        sku = str(r.get("sku") or "").strip()
        qty = float(r.get("quantity") or 0.0)
        if not inbound_id or not sku or qty <= 0:
            continue
        shipment_map.setdefault(inbound_id, []).append({"sku": sku, "quantity": qty})
    return shipment_map


def main() -> None:
    if not TXN_LEDGER.exists():
        print({"status": "skip", "reason": "missing_transaction_ledger"})
        return
    df = pd.read_csv(TXN_LEDGER, dtype=str).fillna("")
    if df.empty:
        print({"status": "skip", "reason": "empty_transaction_ledger"})
        return

    df["amount_value"] = df.get("amount_value", df.get("amount", "")).apply(_to_float)
    shipment_map = _load_shipment_map()

    rows = []
    for _, r in df.iterrows():
        inbound_id = str(r.get("inbound_shipment_id") or "").strip()
        amt = float(r.get("amount_value") or 0.0)
        if inbound_id and inbound_id in shipment_map:
            items = shipment_map[inbound_id]
            total_qty = sum(i["quantity"] for i in items)
            if total_qty <= 0:
                continue
            for item in items:
                share = item["quantity"] / total_qty
                rows.append(
                    {
                        "posted_date": r.get("posted_date", ""),
                        "transaction_id": r.get("transaction_id", ""),
                        "transaction_type": r.get("transaction_type", ""),
                        "breakdown_type": r.get("breakdown_type", ""),
                        "amount": r.get("amount", ""),
                        "currency": r.get("currency", ""),
                        "amount_value": amt,
                        "allocated_amount": amt * share,
                        "allocated_sku": item["sku"],
                        "allocation_method": "inbound_shipment_qty",
                        "inbound_shipment_id": inbound_id,
                        "status": "allocated",
                    }
                )
        else:
            rows.append(
                {
                    "posted_date": r.get("posted_date", ""),
                    "transaction_id": r.get("transaction_id", ""),
                    "transaction_type": r.get("transaction_type", ""),
                    "breakdown_type": r.get("breakdown_type", ""),
                    "amount": r.get("amount", ""),
                    "currency": r.get("currency", ""),
                    "amount_value": amt,
                    "allocated_amount": "",
                    "allocated_sku": "",
                    "allocation_method": "unallocated",
                    "inbound_shipment_id": inbound_id,
                    "status": "unallocated",
                }
            )

    alloc = pd.DataFrame(rows)
    OUT_ALLOC.parent.mkdir(parents=True, exist_ok=True)
    safe_to_csv(alloc, OUT_ALLOC, index=False)

    summary = (
        alloc.groupby(["status", "transaction_type", "breakdown_type", "currency"], dropna=False)
        .agg(rows=("amount_value", "size"), amount_total=("amount_value", "sum"))
        .reset_index()
        .sort_values(by=["status", "transaction_type", "breakdown_type"])
    )
    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    safe_to_csv(summary, OUT_SUMMARY, index=False)

    print(
        {
            "status": "success",
            "rows": len(alloc),
            "allocated_rows": int((alloc["status"] == "allocated").sum()),
            "unallocated_rows": int((alloc["status"] == "unallocated").sum()),
            "alloc": str(OUT_ALLOC),
            "summary": str(OUT_SUMMARY),
        }
    )


if __name__ == "__main__":
    main()

