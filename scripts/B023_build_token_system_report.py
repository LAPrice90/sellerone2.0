"""
Build an analysis report for token coverage, stock alignment, and return handling.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


OUT_DIR = Path("out")

TOKEN_LEDGER = OUT_DIR / "token_ledger_live.csv"
TOKEN_ALLOC = OUT_DIR / "token_allocations_live.csv"
ORDER_MASTER = OUT_DIR / "order_master.csv"
INVENTORY_SUMMARIES = OUT_DIR / "inventory_summaries.csv"
REFUND_EVENTS = OUT_DIR / "refund_token_events.csv"
STOCK_ADJ_EVENTS = OUT_DIR / "stock_adjustment_token_events.csv"

OUT_SKU_REPORT = OUT_DIR / "token_system_status_report.csv"
OUT_ORDER_GAPS = OUT_DIR / "token_order_allocation_gaps.csv"
OUT_SUMMARY = OUT_DIR / "token_system_status_summary.csv"


def parse_int(value) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def main() -> None:
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    tokens = load_csv(TOKEN_LEDGER)
    allocs = load_csv(TOKEN_ALLOC)
    orders = load_csv(ORDER_MASTER)
    inventory = load_csv(INVENTORY_SUMMARIES)
    refunds = load_csv(REFUND_EVENTS)
    adjustments = load_csv(STOCK_ADJ_EVENTS)

    if tokens.empty:
        raise RuntimeError("Missing token_ledger_live.csv")
    if orders.empty:
        raise RuntimeError("Missing order_master.csv")

    # Token counts by SKU/status
    tokens["status"] = tokens.get("status", "").astype(str)
    token_counts = (
        tokens.groupby(["seller_sku", "status"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    token_counts.columns = [c if c else "status_unknown" for c in token_counts.columns]

    # Order demand by SKU and allocation coverage
    orders = orders.copy()
    orders["Quantity Ordered"] = orders["Quantity Ordered"].apply(parse_int)
    orders = orders[orders["Quantity Ordered"] > 0]
    order_demand = (
        orders.groupby(["Order ID", "SKU"])["Quantity Ordered"].sum().reset_index()
    )

    if not allocs.empty:
        allocs["quantity"] = allocs.get("quantity", "1").apply(parse_int)
        alloc_coverage = (
            allocs.groupby(["order_id", "seller_sku"])["quantity"].sum().reset_index()
        )
        alloc_coverage.rename(columns={"order_id": "Order ID", "seller_sku": "SKU"}, inplace=True)
    else:
        alloc_coverage = pd.DataFrame(columns=["Order ID", "SKU", "quantity"])

    order_check = order_demand.merge(
        alloc_coverage, on=["Order ID", "SKU"], how="left"
    )
    order_check["quantity"] = order_check["quantity"].fillna(0).apply(parse_int)
    order_check["shortfall"] = order_check["Quantity Ordered"] - order_check["quantity"]
    order_gaps = order_check[order_check["shortfall"] > 0].copy()
    if not order_gaps.empty:
        order_gaps = order_gaps.sort_values(
            by=["shortfall", "SKU", "Order ID"], ascending=[False, True, True]
        )
    OUT_ORDER_GAPS.parent.mkdir(parents=True, exist_ok=True)
    order_gaps.to_csv(OUT_ORDER_GAPS, index=False)

    sku_order_totals = order_check.groupby("SKU").agg(
        order_qty=("Quantity Ordered", "sum"),
        allocated_qty=("quantity", "sum"),
        unallocated_qty=("shortfall", "sum"),
    ).reset_index()

    # Inventory summaries
    if not inventory.empty:
        inventory = inventory.copy()
        for col in [
            "available",
            "inbound_shipped",
            "inbound_receiving",
            "unsellable",
            "total_quantity",
        ]:
            if col in inventory.columns:
                inventory[col] = inventory[col].apply(parse_int)
        inventory["inventory_inbound"] = inventory.get("inbound_shipped", 0) + inventory.get(
            "inbound_receiving", 0
        )
        inventory.rename(
            columns={
                "available": "inventory_available",
                "unsellable": "inventory_unsellable",
                "inbound_shipped": "inventory_inbound_shipped",
                "inbound_receiving": "inventory_inbound_receiving",
                "total_quantity": "inventory_total_quantity",
            },
            inplace=True,
        )
    else:
        inventory = pd.DataFrame(columns=["seller_sku"])

    # Refund/adjustment signals
    refunds_count = (
        refunds.groupby("sku").size().reset_index(name="refund_events")
        if not refunds.empty and "sku" in refunds.columns
        else pd.DataFrame(columns=["sku", "refund_events"])
    )
    adj_count = (
        adjustments.groupby("sku").size().reset_index(name="stock_adjustment_events")
        if not adjustments.empty and "sku" in adjustments.columns
        else pd.DataFrame(columns=["sku", "stock_adjustment_events"])
    )

    # Build per-SKU report
    report = token_counts.merge(
        sku_order_totals, left_on="seller_sku", right_on="SKU", how="left"
    ).drop(columns=["SKU"], errors="ignore")
    report = report.merge(
        inventory,
        left_on="seller_sku",
        right_on="seller_sku",
        how="left",
    )
    report = report.merge(refunds_count, left_on="seller_sku", right_on="sku", how="left").drop(
        columns=["sku"], errors="ignore"
    )
    report = report.merge(adj_count, left_on="seller_sku", right_on="sku", how="left").drop(
        columns=["sku"], errors="ignore"
    )

    for col in [
        "order_qty",
        "allocated_qty",
        "unallocated_qty",
        "available",
        "warehouse",
        "unsellable",
        "returned_pending",
        "allocated",
        "disposed",
        "refund_events",
        "stock_adjustment_events",
        "inventory_inbound",
        "inventory_unsellable",
        "inventory_available",
    ]:
        if col in report.columns:
            report[col] = report[col].fillna(0).apply(parse_int)

    token_total = tokens.groupby("seller_sku").size().reset_index(name="token_total")
    report = report.merge(token_total, on="seller_sku", how="left")
    report["token_total"] = report["token_total"].fillna(0).apply(parse_int)

    report["available_tokens"] = report.get("available", 0)
    report["warehouse_tokens"] = report.get("warehouse", 0)
    report["unsellable_tokens"] = report.get("unsellable", 0)
    report["returned_pending_tokens"] = report.get("returned_pending", 0)

    if "available" in report.columns:
        report["ready_to_allocate"] = report["available_tokens"] >= report["unallocated_qty"]
    else:
        report["ready_to_allocate"] = False

    # Inventory alignment deltas
    if "available" in report.columns and "available" in inventory.columns:
        report["delta_available_vs_inventory"] = report["available_tokens"] - report.get(
            "available", 0
        )
    if "unsellable" in report.columns and "unsellable" in inventory.columns:
        report["delta_unsellable_vs_inventory"] = report["unsellable_tokens"] - report.get(
            "unsellable", 0
        )
    if "inventory_inbound" in report.columns:
        report["delta_inbound_vs_tokens"] = report.get("warehouse_tokens", 0) - report.get(
            "inventory_inbound", 0
        )

    report["report_ts"] = now_iso
    report = report.sort_values(by="seller_sku")

    OUT_SKU_REPORT.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(OUT_SKU_REPORT, index=False)

    # Summary
    total_order_qty = int(sku_order_totals["order_qty"].sum()) if not sku_order_totals.empty else 0
    total_allocated = int(sku_order_totals["allocated_qty"].sum()) if not sku_order_totals.empty else 0
    total_unallocated = int(sku_order_totals["unallocated_qty"].sum()) if not sku_order_totals.empty else 0
    total_available = int(tokens[tokens["status"] == "available"].shape[0])
    total_returned_pending = int(tokens[tokens["status"] == "returned_pending"].shape[0])
    total_unsellable = int(tokens[tokens["status"] == "unsellable"].shape[0])

    summary = pd.DataFrame(
        [
            {"metric": "report_ts", "value": now_iso},
            {"metric": "order_qty_total", "value": total_order_qty},
            {"metric": "allocated_qty_total", "value": total_allocated},
            {"metric": "unallocated_qty_total", "value": total_unallocated},
            {"metric": "available_tokens_total", "value": total_available},
            {"metric": "returned_pending_tokens_total", "value": total_returned_pending},
            {"metric": "unsellable_tokens_total", "value": total_unsellable},
            {
                "metric": "allocation_coverage_rate",
                "value": f"{(total_allocated / total_order_qty):.4f}" if total_order_qty else "0",
            },
            {
                "metric": "available_vs_unallocated",
                "value": total_available - total_unallocated,
            },
            {"metric": "orders_with_shortfall", "value": int(len(order_gaps))},
        ]
    )
    summary.to_csv(OUT_SUMMARY, index=False)

    print(
        {
            "status": "success",
            "sku_report": str(OUT_SKU_REPORT),
            "order_gaps": str(OUT_ORDER_GAPS),
            "summary": str(OUT_SUMMARY),
        }
    )


if __name__ == "__main__":
    main()
