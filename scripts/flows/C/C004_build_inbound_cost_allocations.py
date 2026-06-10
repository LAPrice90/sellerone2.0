from __future__ import annotations

from pathlib import Path
import pandas as pd

IN_EVENTS = Path("out/inbound_cost_events.csv")
IN_DELIVERY = Path("out/inbound_delivery_status.csv")
OUT_ALLOC = Path("out/inbound_costs_allocated.csv")
OUT_UNALLOC = Path("out/inbound_costs_unallocated.csv")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _shipment_key(df: pd.DataFrame) -> pd.Series:
    for col in ["inbound_shipment_id", "parsed_fba_shipment_id", "shipment_id"]:
        if col not in df.columns:
            df[col] = ""
    key = df["inbound_shipment_id"].astype(str).str.strip()
    key = key.where(key != "", df["parsed_fba_shipment_id"].astype(str).str.strip())
    key = key.where(key != "", df["shipment_id"].astype(str).str.strip())
    return key


def _delivery_shipment_ids(delivery: pd.DataFrame) -> set[str]:
    if delivery.empty:
        return set()
    ids: set[str] = set()
    for col in ("inbound_shipment_id", "shipment_id"):
        if col not in delivery.columns:
            continue
        ids.update(value for value in delivery[col].astype(str).str.strip().tolist() if value)
    return ids


def main() -> None:
    events = _read_csv(IN_EVENTS)
    delivery = _read_csv(IN_DELIVERY)

    if events.empty:
        OUT_ALLOC.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(OUT_ALLOC, index=False)
        pd.DataFrame().to_csv(OUT_UNALLOC, index=False)
        print({"status": "success", "rows_allocated": 0, "rows_unallocated": 0})
        return

    delivery_shipments = _delivery_shipment_ids(delivery)

    events = events.copy()
    events["shipment_key"] = _shipment_key(events)
    events["amount_num"] = _num(events.get("amount", pd.Series([], dtype=str)))
    events["tax_num"] = _num(events.get("tax_amount", pd.Series([], dtype=str)))
    events["currency"] = events.get("currency", "")

    in_scope = events["shipment_key"].astype(str).str.strip()
    allocated_mask = (in_scope != "") & (in_scope.isin(delivery_shipments))
    unallocated_mask = ~allocated_mask

    allocated = events.loc[allocated_mask].copy()
    unallocated = events.loc[unallocated_mask].copy()
    unallocated["unallocated_reason"] = "missing_or_unknown_shipment_id"

    if not allocated.empty:
        alloc_summary = (
            allocated.groupby(["shipment_key", "currency"], as_index=False)
            .agg(event_count=("shipment_key", "size"), total_amount=("amount_num", "sum"), total_tax=("tax_num", "sum"))
        )
        alloc_summary["total_with_tax"] = alloc_summary["total_amount"] + alloc_summary["total_tax"]
        alloc_summary = alloc_summary.rename(columns={"shipment_key": "shipment_id"})
    else:
        alloc_summary = pd.DataFrame(columns=["shipment_id", "currency", "event_count", "total_amount", "total_tax", "total_with_tax"])

    OUT_ALLOC.parent.mkdir(parents=True, exist_ok=True)
    alloc_summary.to_csv(OUT_ALLOC, index=False)
    unallocated.to_csv(OUT_UNALLOC, index=False)

    print(
        {
            "status": "success",
            "rows_allocated": int(len(alloc_summary)),
            "rows_unallocated": int(len(unallocated)),
            "allocated_snapshot": str(OUT_ALLOC),
            "unallocated_snapshot": str(OUT_UNALLOC),
        }
    )


if __name__ == "__main__":
    main()

