from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.safe_file_writes import safe_to_csv


OUT = Path("out")
REPROOF_PREVIEW = OUT / "systems" / "B" / "refunds" / "b_refund_token_reproof_preview.csv"
REFUND_BRIDGE = OUT / "systems" / "B" / "refunds" / "b_refund_pnl_bridge.csv"
ORDERS_ALL = OUT / "orders_all.csv"
ORDER_ITEMS_ALL = OUT / "order_items_all.csv"
ORDER_MASTER = OUT / "order_master.csv"
TOKEN_ALLOCATIONS = OUT / "token_allocations_live.csv"
TOKEN_LEDGER = OUT / "token_ledger_live.csv"
REFUND_EVENTS = OUT / "financial_events_refunds.csv"
OUT_AUDIT = OUT / "systems" / "B" / "refunds" / "b_original_allocation_gap_audit.csv"
OUT_SUMMARY = OUT / "systems" / "B" / "refunds" / "b_original_allocation_gap_audit_summary.csv"


AUDIT_COLUMNS = [
    "order_id",
    "sku",
    "refund_posted_date",
    "api_refund_rows",
    "refund_bridge_original_units",
    "refund_bridge_original_order_state",
    "orders_all_rows",
    "order_items_all_rows",
    "order_master_rows",
    "token_allocation_rows",
    "token_ledger_allocated_rows",
    "token_ledger_return_rows",
    "allocation_gap_conclusion",
    "manager_expectation",
    "bounded_worker_task",
    "retest_rule",
    "preview_live_write_allowed",
    "roi_or_restock_use_allowed",
    "sellerboard_final_truth_allowed",
    "protected_before_apply",
]

SUMMARY_COLUMNS = ["metric", "value"]


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _text(value: object) -> str:
    return str(value or "").strip()


def _norm_sku(value: object) -> str:
    return _text(value).upper()


def _num(value: object) -> float:
    raw = _text(value).replace(",", "")
    if not raw:
        return 0.0
    try:
        return float(raw)
    except Exception:
        return 0.0


def _prepare_reproof_preview(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["order_id", "sku", "refund_posted_date", "reproof_lane", "reproof_readiness"]:
        if column not in work.columns:
            work[column] = ""
    work["order_id_norm"] = work["order_id"].map(_text)
    work["sku_norm"] = work["sku"].map(_norm_sku)
    return work[
        (work["reproof_lane"].astype(str).str.strip() == "original_allocation_gap")
        & (work["order_id_norm"] != "")
        & (work["sku_norm"] != "")
    ].copy()


def _prepare_order_key(df: pd.DataFrame, order_columns: list[str], sku_columns: list[str] | None = None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    order_col = next((column for column in order_columns if column in work.columns), "")
    if not order_col:
        return pd.DataFrame()
    work["order_id_norm"] = work[order_col].map(_text)
    if sku_columns:
        sku_col = next((column for column in sku_columns if column in work.columns), "")
        work["sku_norm"] = work[sku_col].map(_norm_sku) if sku_col else ""
    return work[work["order_id_norm"] != ""].copy()


def _prepare_token_allocations(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["order_id", "seller_sku", "token_id"]:
        if column not in work.columns:
            work[column] = ""
    work["order_id_norm"] = work["order_id"].map(_text)
    work["sku_norm"] = work["seller_sku"].map(_norm_sku)
    return work


def _prepare_token_ledger(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["seller_sku", "allocated_order_id", "return_order_id", "last_return_order_id"]:
        if column not in work.columns:
            work[column] = ""
    work["sku_norm"] = work["seller_sku"].map(_norm_sku)
    work["allocated_order_norm"] = work["allocated_order_id"].map(_text)
    work["return_order_norm"] = work["return_order_id"].map(_text)
    work["last_return_order_norm"] = work["last_return_order_id"].map(_text)
    return work


def _prepare_refunds(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["order_id", "sku"]:
        if column not in work.columns:
            work[column] = ""
    work["order_id_norm"] = work["order_id"].map(_text)
    work["sku_norm"] = work["sku"].map(_norm_sku)
    return work


def _count_order_sku(df: pd.DataFrame, order_id: str, sku: str) -> int:
    if df.empty:
        return 0
    if "sku_norm" in df.columns:
        return int(((df["order_id_norm"] == order_id) & (df["sku_norm"] == sku)).sum())
    return int((df["order_id_norm"] == order_id).sum())


def _bridge_state(refund_bridge: pd.DataFrame, order_id: str, sku: str) -> tuple[str, str]:
    if refund_bridge.empty:
        return "0", "refund_bridge_missing"
    rows = refund_bridge[(refund_bridge["order_id_norm"] == order_id) & (refund_bridge["sku_norm"] == sku)].copy()
    if rows.empty:
        return "0", "refund_bridge_row_missing"
    units = sum(_num(value) for value in rows.get("original_units", pd.Series(dtype=str)).tolist())
    notes = " ".join(rows.get("notes", pd.Series(dtype=str)).astype(str).tolist()).lower()
    if units > 0:
        return str(int(units) if units.is_integer() else units), "original_order_seen"
    if "original_order_not_found" in notes:
        return "0", "original_order_not_found"
    return "0", "original_order_not_manager_readable"


def _classify(
    *,
    orders_rows: int,
    order_item_rows: int,
    order_master_rows: int,
    allocation_rows: int,
    ledger_allocated_rows: int,
    ledger_return_rows: int,
    refund_bridge_state: str,
) -> tuple[str, str, str, str]:
    if allocation_rows > 0 and ledger_allocated_rows > 0:
        return (
            "allocation_proof_exists_bridge_mapping_gap",
            "Original allocation proof exists. If B042 still warns, repair the proof reader before any token action.",
            "Repair B042/B041 mapping so the existing allocation is recognised; do not create stock.",
            "Rerun B053/B042/B041/B038 and B MOT; row clears when allocation proof is recognised.",
        )
    if allocation_rows > 0 and ledger_allocated_rows == 0:
        return (
            "allocation_exists_token_ledger_missing",
            "Allocation file names a token, but the token ledger does not expose the matching allocated token.",
            "Repair token-ledger trace proof for the named allocation before any B008 reproof.",
            "Rerun B053/B042/B041/B038 and B MOT after token-ledger proof is manager-readable.",
        )
    if orders_rows > 0 or order_item_rows > 0 or order_master_rows > 0:
        return (
            "order_seen_allocation_missing",
            "The order exists, but the original sale-token allocation is missing.",
            "Repair original allocation proof from the normal order/token allocation path; do not create replacement stock.",
            "Rerun B053/B042/B041/B038 and B MOT after allocation proof exists.",
        )
    if ledger_return_rows > 0:
        return (
            "return_token_seen_without_original_order",
            "A return-state token is visible, but the original sale order is not manager-readable.",
            "Repair original order proof before trusting any return-stock recovery.",
            "Rerun B053/B042/B041/B038 and B MOT after original order proof exists.",
        )
    if refund_bridge_state == "original_order_not_found":
        return (
            "refund_money_without_original_order_or_allocation_proof",
            "Refund money is API-proved, but the original sale order and token allocation are not visible.",
            "Build a read-only original-order recovery proof for this refund; do not create tokens or stock.",
            "Rerun B053 after original order recovery proof exists; keep stock recovery blocked until order and allocation proof agree.",
        )
    return (
        "refund_row_without_allocation_source",
        "Refund money is visible, but no trusted original allocation source is visible.",
        "Investigate the earliest missing source: original order, order item, allocation, then token ledger.",
        "Rerun B053/B042/B041/B038 and B MOT after the earliest source is repaired or exception-labelled.",
    )


def build_original_allocation_gap_audit(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
) -> dict[str, pd.DataFrame]:
    root_path = Path(root or ".")
    observed = observed_utc or _utc_now_text()
    source = _prepare_reproof_preview(_read_csv(root_path / REPROOF_PREVIEW))
    refund_bridge = _prepare_refunds(_read_csv(root_path / REFUND_BRIDGE))
    orders = _prepare_order_key(_read_csv(root_path / ORDERS_ALL), ["amazon_order_id", "order_id"])
    order_items = _prepare_order_key(
        _read_csv(root_path / ORDER_ITEMS_ALL),
        ["amazon_order_id", "AmazonOrderId", "order_id"],
        ["seller_sku", "SellerSKU", "sku"],
    )
    order_master = _prepare_order_key(_read_csv(root_path / ORDER_MASTER), ["Order ID", "order_id"], ["SKU", "seller_sku", "sku"])
    allocations = _prepare_token_allocations(_read_csv(root_path / TOKEN_ALLOCATIONS))
    ledger = _prepare_token_ledger(_read_csv(root_path / TOKEN_LEDGER))
    refund_events = _prepare_refunds(_read_csv(root_path / REFUND_EVENTS))

    rows: list[dict[str, str]] = []
    for _, source_row in source.iterrows():
        order_id = _text(source_row.get("order_id_norm", ""))
        sku = _norm_sku(source_row.get("sku_norm", ""))
        refund_posted_date = _text(source_row.get("refund_posted_date", ""))
        original_units, bridge_state = _bridge_state(refund_bridge, order_id, sku)
        orders_rows = _count_order_sku(orders, order_id, sku)
        item_rows = _count_order_sku(order_items, order_id, sku)
        master_rows = _count_order_sku(order_master, order_id, sku)
        allocation_rows = _count_order_sku(allocations, order_id, sku)
        ledger_allocated_rows = (
            int(((ledger["allocated_order_norm"] == order_id) & (ledger["sku_norm"] == sku)).sum()) if not ledger.empty else 0
        )
        ledger_return_rows = (
            int(
                (
                    ((ledger["return_order_norm"] == order_id) | (ledger["last_return_order_norm"] == order_id))
                    & (ledger["sku_norm"] == sku)
                ).sum()
            )
            if not ledger.empty
            else 0
        )
        refund_money_rows = _count_order_sku(refund_events, order_id, sku)
        conclusion, expectation, worker_task, retest = _classify(
            orders_rows=orders_rows,
            order_item_rows=item_rows,
            order_master_rows=master_rows,
            allocation_rows=allocation_rows,
            ledger_allocated_rows=ledger_allocated_rows,
            ledger_return_rows=ledger_return_rows,
            refund_bridge_state=bridge_state,
        )
        rows.append(
            {
                "order_id": order_id,
                "sku": sku,
                "refund_posted_date": refund_posted_date,
                "api_refund_rows": str(refund_money_rows),
                "refund_bridge_original_units": original_units,
                "refund_bridge_original_order_state": bridge_state,
                "orders_all_rows": str(orders_rows),
                "order_items_all_rows": str(item_rows),
                "order_master_rows": str(master_rows),
                "token_allocation_rows": str(allocation_rows),
                "token_ledger_allocated_rows": str(ledger_allocated_rows),
                "token_ledger_return_rows": str(ledger_return_rows),
                "allocation_gap_conclusion": conclusion,
                "manager_expectation": expectation,
                "bounded_worker_task": worker_task,
                "retest_rule": retest,
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "protected_before_apply": "1",
            }
        )

    audit = pd.DataFrame(rows, columns=AUDIT_COLUMNS).fillna("")
    unclassified = audit[audit["allocation_gap_conclusion"].astype(str).str.strip() == ""] if not audit.empty else audit
    unsafe_rows = 0
    if not audit.empty:
        unsafe_rows = int(
            (audit["preview_live_write_allowed"].astype(str).str.strip() != "0").sum()
            + (audit["roi_or_restock_use_allowed"].astype(str).str.strip() != "0").sum()
            + (audit["sellerboard_final_truth_allowed"].astype(str).str.strip() != "0").sum()
        )
    status = "ok"
    if source.empty:
        status = "not_checked"
    elif len(unclassified) or unsafe_rows:
        status = "fail"
    summary_values = {
        "status": status,
        "observed_utc": observed,
        "audit_rows": str(len(audit)),
        "refund_money_without_original_order_rows": str(
            int((audit["allocation_gap_conclusion"] == "refund_money_without_original_order_or_allocation_proof").sum())
            if not audit.empty
            else 0
        ),
        "order_seen_allocation_missing_rows": str(
            int((audit["allocation_gap_conclusion"] == "order_seen_allocation_missing").sum()) if not audit.empty else 0
        ),
        "allocation_exists_token_ledger_missing_rows": str(
            int((audit["allocation_gap_conclusion"] == "allocation_exists_token_ledger_missing").sum())
            if not audit.empty
            else 0
        ),
        "allocation_proof_exists_bridge_mapping_gap_rows": str(
            int((audit["allocation_gap_conclusion"] == "allocation_proof_exists_bridge_mapping_gap").sum())
            if not audit.empty
            else 0
        ),
        "unclassified_rows": str(len(unclassified)),
        "unsafe_rows": str(unsafe_rows),
        "live_write_allowed_rows": str(int((audit["preview_live_write_allowed"].astype(str).str.strip() != "0").sum()) if not audit.empty else 0),
        "roi_or_restock_allowed_rows": str(int((audit["roi_or_restock_use_allowed"].astype(str).str.strip() != "0").sum()) if not audit.empty else 0),
        "sellerboard_final_truth_allowed_rows": str(
            int((audit["sellerboard_final_truth_allowed"].astype(str).str.strip() != "0").sum()) if not audit.empty else 0
        ),
    }
    summary = pd.DataFrame([{"metric": key, "value": value} for key, value in summary_values.items()], columns=SUMMARY_COLUMNS)
    return {"audit": audit, "summary": summary}


def write_original_allocation_gap_audit_outputs(
    result: dict[str, pd.DataFrame],
    *,
    root: Path | str | None = None,
) -> dict[str, Path]:
    root_path = Path(root or ".")
    audit_path = root_path / OUT_AUDIT
    summary_path = root_path / OUT_SUMMARY
    safe_to_csv(result["audit"], audit_path, index=False)
    safe_to_csv(result["summary"], summary_path, index=False)
    return {"audit": audit_path, "summary": summary_path}


def main() -> None:
    result = build_original_allocation_gap_audit()
    paths = write_original_allocation_gap_audit_outputs(result)
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}
    print(
        {
            "status": summary.get("status", ""),
            "audit_rows": summary.get("audit_rows", "0"),
            "refund_money_without_original_order_rows": summary.get("refund_money_without_original_order_rows", "0"),
            "order_seen_allocation_missing_rows": summary.get("order_seen_allocation_missing_rows", "0"),
            "unclassified_rows": summary.get("unclassified_rows", "0"),
            "audit": str(paths["audit"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
