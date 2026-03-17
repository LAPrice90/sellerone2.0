from __future__ import annotations

from pathlib import Path
import pandas as pd

IN_COSTS = Path("out/inbound_costs_allocated.csv")
IN_LEDGER = Path("out/inventory_ledger_raw.csv")
OUT_SKU = Path("out/inbound_costs_allocated_sku.csv")
OUT_UNALLOC = Path("out/inbound_costs_unallocated_sku.csv")
OUT_SUMMARY = Path("out/inbound_costs_allocation_summary.csv")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def main() -> None:
    costs = _read_csv(IN_COSTS)
    ledger = _read_csv(IN_LEDGER)

    if costs.empty:
        OUT_SKU.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            columns=[
                "shipment_id",
                "sku",
                "received_qty",
                "total_received_qty",
                "currency",
                "allocated_amount",
                "allocated_tax",
                "allocated_total",
            ]
        ).to_csv(OUT_SKU, index=False)
        pd.DataFrame(
            columns=[
                "shipment_id",
                "currency",
                "event_count",
                "total_amount",
                "total_tax",
                "total_with_tax",
                "unallocated_reason",
            ]
        ).to_csv(OUT_UNALLOC, index=False)
        pd.DataFrame(
            columns=["shipment_id", "currency", "allocated_amount", "allocated_tax", "allocated_total"]
        ).to_csv(OUT_SUMMARY, index=False)
        print(
            {
                "status": "success",
                "rows_allocated": 0,
                "rows_unallocated": 0,
                "allocated_snapshot": str(OUT_SKU),
                "unallocated_snapshot": str(OUT_UNALLOC),
                "summary_snapshot": str(OUT_SUMMARY),
            }
        )
        return

    if ledger.empty:
        unalloc = costs.copy()
        unalloc["unallocated_reason"] = "inventory_ledger_missing"
        OUT_SKU.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            columns=[
                "shipment_id",
                "sku",
                "received_qty",
                "total_received_qty",
                "currency",
                "allocated_amount",
                "allocated_tax",
                "allocated_total",
            ]
        ).to_csv(OUT_SKU, index=False)
        unalloc.to_csv(OUT_UNALLOC, index=False)
        pd.DataFrame(
            columns=["shipment_id", "currency", "allocated_amount", "allocated_tax", "allocated_total"]
        ).to_csv(OUT_SUMMARY, index=False)
        print({"status": "success", "rows_allocated": 0, "rows_unallocated": len(unalloc)})
        return

    ledger = ledger.copy()
    if "Reference ID" not in ledger.columns or "MSKU" not in ledger.columns or "Quantity" not in ledger.columns:
        raise ValueError("inventory_ledger_raw.csv missing required columns: Reference ID, MSKU, Quantity")

    ledger["qty_num"] = _num(ledger["Quantity"])
    ledger["shipment_id"] = ledger["Reference ID"].astype(str).str.strip()
    ledger["sku"] = ledger["MSKU"].astype(str).str.strip()

    # Aggregate received qty by shipment and sku.
    qty_by_ship_sku = (
        ledger.groupby(["shipment_id", "sku"], as_index=False)
        .agg(received_qty=("qty_num", "sum"))
    )

    # Shipment totals for allocation denominator.
    ship_totals = (
        qty_by_ship_sku.groupby("shipment_id", as_index=False)
        .agg(total_received_qty=("received_qty", "sum"))
    )

    costs = costs.copy()
    costs["total_amount"] = _num(costs.get("total_amount", pd.Series([], dtype=str)))
    costs["total_tax"] = _num(costs.get("total_tax", pd.Series([], dtype=str)))
    costs["total_with_tax"] = _num(costs.get("total_with_tax", pd.Series([], dtype=str)))
    costs["shipment_id"] = costs.get("shipment_id", "").astype(str).str.strip()

    merged = costs.merge(ship_totals, on="shipment_id", how="left")
    merged["total_received_qty"] = _num(merged.get("total_received_qty", pd.Series([], dtype=str)))

    alloc_rows = []
    unalloc_rows = []

    for _, row in merged.iterrows():
        shipment_id = row["shipment_id"]
        total_qty = row["total_received_qty"]
        if not shipment_id or total_qty <= 0:
            unalloc = row.to_dict()
            unalloc["unallocated_reason"] = "missing_or_zero_received_qty"
            unalloc_rows.append(unalloc)
            continue

        sku_rows = qty_by_ship_sku[qty_by_ship_sku["shipment_id"] == shipment_id]
        if sku_rows.empty:
            unalloc = row.to_dict()
            unalloc["unallocated_reason"] = "no_sku_rows_for_shipment"
            unalloc_rows.append(unalloc)
            continue

        for _, srow in sku_rows.iterrows():
            share = srow["received_qty"] / total_qty if total_qty else 0
            alloc_rows.append(
                {
                    "shipment_id": shipment_id,
                    "sku": srow["sku"],
                    "received_qty": srow["received_qty"],
                    "total_received_qty": total_qty,
                    "currency": row.get("currency", ""),
                    "allocated_amount": row["total_amount"] * share,
                    "allocated_tax": row["total_tax"] * share,
                    "allocated_total": row["total_with_tax"] * share,
                }
            )

    out_alloc = pd.DataFrame(alloc_rows)
    out_unalloc = pd.DataFrame(unalloc_rows)

    summary = (
        out_alloc.groupby(["shipment_id", "currency"], as_index=False)
        .agg(
            allocated_amount=("allocated_amount", "sum"),
            allocated_tax=("allocated_tax", "sum"),
            allocated_total=("allocated_total", "sum"),
        )
        if not out_alloc.empty
        else pd.DataFrame(columns=["shipment_id", "currency", "allocated_amount", "allocated_tax", "allocated_total"])
    )

    OUT_SKU.parent.mkdir(parents=True, exist_ok=True)
    out_alloc.to_csv(OUT_SKU, index=False)
    out_unalloc.to_csv(OUT_UNALLOC, index=False)
    summary.to_csv(OUT_SUMMARY, index=False)

    print(
        {
            "status": "success",
            "rows_allocated": int(len(out_alloc)),
            "rows_unallocated": int(len(out_unalloc)),
            "allocated_snapshot": str(OUT_SKU),
            "unallocated_snapshot": str(OUT_UNALLOC),
            "summary_snapshot": str(OUT_SUMMARY),
        }
    )


if __name__ == "__main__":
    main()

