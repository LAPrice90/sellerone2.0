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
ORIGINAL_GAP_AUDIT = OUT / "systems" / "B" / "refunds" / "b_original_allocation_gap_audit.csv"
REFUND_BRIDGE = OUT / "systems" / "B" / "refunds" / "b_refund_pnl_bridge.csv"
REFUND_EVENTS = OUT / "financial_events_refunds.csv"
ORDERS_RAW = OUT / "orders_raw.csv"
ORDER_ITEMS_RAW = OUT / "order_items_raw.csv"
ORDERS_PENDING_RAW = OUT / "orders_pending_raw.csv"
ORDER_ITEMS_PENDING_RAW = OUT / "order_items_pending_raw.csv"
ORDERS_ALL = OUT / "orders_all.csv"
ORDER_ITEMS_ALL = OUT / "order_items_all.csv"
ORDER_MASTER = OUT / "order_master.csv"
LEVEL1 = OUT / "financial_events_level1.csv"
TOKEN_ALLOCATIONS = OUT / "token_allocations_live.csv"
TOKEN_LEDGER = OUT / "token_ledger_live.csv"
QUARANTINE = OUT / "systems" / "B" / "recovery_quarantine" / "b_order_recovery_quarantine.csv"
SELLERBOARD_RECONCILIATION = OUT / "systems" / "M" / "sellerboard_bridge" / "b_sellerboard_bridge_order_reconciliation.csv"
OUT_PROOF = OUT / "systems" / "B" / "refunds" / "b_original_order_recovery_proof.csv"
OUT_SUMMARY = OUT / "systems" / "B" / "refunds" / "b_original_order_recovery_proof_summary.csv"


PROOF_COLUMNS = [
    "order_id",
    "sku",
    "refund_posted_date",
    "api_refund_rows",
    "refund_bridge_rows",
    "refund_bridge_original_order_state",
    "orders_raw_rows",
    "order_items_raw_rows",
    "orders_pending_raw_rows",
    "order_items_pending_raw_rows",
    "orders_all_rows",
    "order_items_all_rows",
    "order_master_rows",
    "level1_rows",
    "token_allocation_rows",
    "token_ledger_allocated_rows",
    "quarantine_rows",
    "quarantine_api_proved_rows",
    "quarantine_ready_for_live_merge_rows",
    "quarantine_duplicate_risk_rows",
    "quarantine_required_field_gaps",
    "sellerboard_witness_rows",
    "purchase_date_proof",
    "marketplace_proof",
    "order_item_proof",
    "currency_proof",
    "original_order_recovery_state",
    "manager_expectation",
    "bounded_worker_task",
    "retest_rule",
    "preview_live_write_allowed",
    "roi_or_restock_use_allowed",
    "sellerboard_final_truth_allowed",
    "protected_before_apply",
]

SUMMARY_COLUMNS = ["metric", "value"]

QUARANTINE_REQUIRED_FIELDS = [
    "purchase_utc",
    "marketplace_id",
    "sku",
    "asin",
    "order_item_ids",
    "currency",
    "order_status",
]


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


def _split_values(value: object) -> set[str]:
    text = _text(value)
    if not text:
        return set()
    return {part.strip().upper() for part in text.replace(",", ";").split(";") if part.strip()}


def _prepare_order_sku(df: pd.DataFrame, order_columns: list[str], sku_columns: list[str] | None = None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    order_col = next((column for column in order_columns if column in work.columns), "")
    if not order_col:
        return pd.DataFrame()
    work["order_id_norm"] = work[order_col].map(_text)
    sku_col = next((column for column in (sku_columns or []) if column in work.columns), "")
    work["sku_norm"] = work[sku_col].map(_norm_sku) if sku_col else ""
    return work[work["order_id_norm"] != ""].copy()


def _prepare_quarantine(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["amazon_order_id", "sku", "proof_label", "ready_for_live_merge", "duplicate_state"]:
        if column not in work.columns:
            work[column] = ""
    work["order_id_norm"] = work["amazon_order_id"].map(_text)
    work["sku_values_norm"] = work["sku"].map(_split_values)
    work["proof_label_norm"] = work["proof_label"].map(_text)
    work["ready_norm"] = work["ready_for_live_merge"].map(lambda value: _text(value).lower())
    work["duplicate_norm"] = work["duplicate_state"].map(lambda value: _text(value).lower())
    return work[work["order_id_norm"] != ""].copy()


def _prepare_token_allocations(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["order_id", "seller_sku"]:
        if column not in work.columns:
            work[column] = ""
    work["order_id_norm"] = work["order_id"].map(_text)
    work["sku_norm"] = work["seller_sku"].map(_norm_sku)
    return work


def _prepare_token_ledger(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["seller_sku", "allocated_order_id"]:
        if column not in work.columns:
            work[column] = ""
    work["sku_norm"] = work["seller_sku"].map(_norm_sku)
    work["allocated_order_norm"] = work["allocated_order_id"].map(_text)
    return work


def _source_rows(original_gap_audit: pd.DataFrame, refund_bridge: pd.DataFrame) -> pd.DataFrame:
    if not original_gap_audit.empty:
        work = original_gap_audit.copy()
        for column in ["order_id", "sku", "refund_posted_date", "allocation_gap_conclusion"]:
            if column not in work.columns:
                work[column] = ""
        work["order_id_norm"] = work["order_id"].map(_text)
        work["sku_norm"] = work["sku"].map(_norm_sku)
        return work[
            (work["allocation_gap_conclusion"].astype(str).str.strip() == "refund_money_without_original_order_or_allocation_proof")
            & (work["order_id_norm"] != "")
            & (work["sku_norm"] != "")
        ][["order_id", "sku", "refund_posted_date", "order_id_norm", "sku_norm"]].drop_duplicates()

    if refund_bridge.empty:
        return pd.DataFrame()
    work = refund_bridge.copy()
    for column in ["order_id", "sku", "refund_posted_date", "notes"]:
        if column not in work.columns:
            work[column] = ""
    work["order_id_norm"] = work["order_id"].map(_text)
    work["sku_norm"] = work["sku"].map(_norm_sku)
    notes = work["notes"].astype(str).str.lower()
    return work[
        notes.str.contains("original_order_not_found", na=False)
        & (work["order_id_norm"] != "")
        & (work["sku_norm"] != "")
    ][["order_id", "sku", "refund_posted_date", "order_id_norm", "sku_norm"]].drop_duplicates()


def _count_order_sku(df: pd.DataFrame, order_id: str, sku: str) -> int:
    if df.empty:
        return 0
    if "sku_norm" in df.columns and df["sku_norm"].astype(str).str.strip().any():
        return int(((df["order_id_norm"] == order_id) & (df["sku_norm"] == sku)).sum())
    return int((df["order_id_norm"] == order_id).sum())


def _quarantine_for_order_sku(quarantine: pd.DataFrame, order_id: str, sku: str) -> pd.DataFrame:
    if quarantine.empty:
        return pd.DataFrame()
    rows = quarantine[quarantine["order_id_norm"] == order_id].copy()
    if rows.empty:
        return rows
    return rows[rows["sku_values_norm"].map(lambda values: not values or sku in values)].copy()


def _quarantine_field_gap(row: pd.Series) -> list[str]:
    gaps = []
    for column in QUARANTINE_REQUIRED_FIELDS:
        if not _text(row.get(column, "")):
            gaps.append(column)
    return gaps


def _first_proof(rows: pd.DataFrame, columns: list[str]) -> str:
    if rows.empty:
        return ""
    values: list[str] = []
    seen: set[str] = set()
    for column in columns:
        if column not in rows.columns:
            continue
        for value in rows[column].tolist():
            text = _text(value)
            if text and text not in seen:
                values.append(text)
                seen.add(text)
            if len(values) >= 3:
                break
        if values:
            break
    return "|".join(values)


def _refund_bridge_state(refund_bridge: pd.DataFrame, order_id: str, sku: str) -> tuple[int, str]:
    if refund_bridge.empty:
        return 0, "refund_bridge_missing"
    rows = refund_bridge[(refund_bridge["order_id_norm"] == order_id) & (refund_bridge["sku_norm"] == sku)]
    if rows.empty:
        return 0, "refund_bridge_row_missing"
    notes = " ".join(rows.get("notes", pd.Series(dtype=str)).astype(str).tolist()).lower()
    if "original_order_not_found" in notes:
        return len(rows), "original_order_not_found"
    return len(rows), "original_order_not_manager_readable"


def _classify(
    *,
    api_refund_rows: int,
    raw_order_rows: int,
    raw_item_rows: int,
    pending_order_rows: int,
    pending_item_rows: int,
    compiled_order_rows: int,
    compiled_item_rows: int,
    master_rows: int,
    level1_rows: int,
    allocation_rows: int,
    ledger_allocated_rows: int,
    quarantine_rows: int,
    quarantine_api_rows: int,
    quarantine_ready_rows: int,
    quarantine_duplicate_rows: int,
    quarantine_field_gaps: int,
) -> tuple[str, str, str, str]:
    if quarantine_ready_rows:
        return (
            "protected_promotion_decision_needed",
            "API recovery proof appears ready for live merge. That must stop for Luke before any promotion writes.",
            "Prepare a promotion preview only; do not promote into live B outputs without protected approval.",
            "After approved promotion, rerun B054/B053/B037 and B MOT; row clears only when live order, item, order master, Level 1, and duplicate proof agree.",
        )
    if quarantine_duplicate_rows:
        return (
            "quarantine_duplicate_risk_blocks_recovery",
            "Recovered order proof has duplicate risk. It cannot be promoted or used for stock recovery.",
            "Build a duplicate-risk proof packet before any merge or token repair.",
            "Rerun B054 after duplicate state is unique and ready state is still blocked until approval.",
        )
    if quarantine_api_rows and quarantine_field_gaps:
        return (
            "api_quarantine_original_order_incomplete",
            "The order is API-proved in quarantine, but required order/item fields are missing.",
            "Repair the quarantine fetch/shape so purchase date, marketplace, SKU, ASIN, item ID, status, and currency are present.",
            "Rerun B054; row clears this state only when quarantine API proof has the required fields.",
        )
    if quarantine_api_rows:
        return (
            "api_quarantine_original_order_proof_exists",
            "Original order proof exists safely in quarantine. It is still not live B truth.",
            "Build a protected promotion preview for this recovered order; do not write live B outputs without Luke approval.",
            "Rerun B054 after promotion preview; final proof requires approved promotion then B MOT clearing the same order gap.",
        )
    if quarantine_rows:
        return (
            "quarantine_original_order_not_api_proved",
            "Quarantine has a row for this order, but it is not API-proved enough for order truth.",
            "Re-fetch or repair the quarantine proof from Amazon API before promotion is considered.",
            "Rerun B054; row clears when quarantine proof label is API proved and required fields exist.",
        )
    if compiled_order_rows or compiled_item_rows or master_rows or level1_rows:
        if allocation_rows or ledger_allocated_rows:
            return (
                "local_order_and_allocation_already_proved",
                "Local order and allocation proof now exists. If older refund rows still warn, refresh the bridge reader.",
                "Rerun B037/B042/B053/B054 so the refund bridge recognises the local order chain.",
                "The row clears when B053 no longer says original order/allocation is missing.",
            )
        return (
            "local_order_seen_but_allocation_missing",
            "The order is visible locally, but original sale allocation is still missing.",
            "Repair the normal original sale-token allocation proof; do not create replacement stock.",
            "Rerun B053/B054/B042/B041/B038 and B MOT after allocation proof exists.",
        )
    if raw_order_rows or raw_item_rows or pending_order_rows or pending_item_rows:
        return (
            "local_raw_order_seen_compiled_gap",
            "Raw or pending order proof exists, but it did not reach the compiled B order chain.",
            "Repair the normal B order compile path for this order; do not patch Order Master by hand.",
            "Rerun B054 after the normal compiled order, item, Order Master, and Level 1 proof exists.",
        )
    if api_refund_rows:
        return (
            "needs_api_original_order_fetch_to_quarantine",
            "Refund money is API-proved, but the original sale order is not visible anywhere manager-readable.",
            "Fetch the original order from Amazon API into quarantine proof only; do not promote or alter tokens.",
            "Rerun B054; row clears this state only when API quarantine proof exists with required order fields.",
        )
    return (
        "not_yet_proven_refund_source_missing",
        "The original order is missing and the API refund source is not manager-readable for this row.",
        "Repair refund source proof before original-order recovery is attempted.",
        "Rerun B037/B053/B054 and B MOT after API refund proof is visible.",
    )


def build_original_order_recovery_proof(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
) -> dict[str, pd.DataFrame]:
    root_path = Path(root or ".")
    observed = observed_utc or _utc_now_text()

    original_gap_audit = _read_csv(root_path / ORIGINAL_GAP_AUDIT)
    refund_bridge = _prepare_order_sku(_read_csv(root_path / REFUND_BRIDGE), ["order_id"], ["sku"])
    refund_events = _prepare_order_sku(_read_csv(root_path / REFUND_EVENTS), ["order_id"], ["sku"])
    orders_raw = _prepare_order_sku(_read_csv(root_path / ORDERS_RAW), ["amazon_order_id", "order_id"])
    order_items_raw = _prepare_order_sku(_read_csv(root_path / ORDER_ITEMS_RAW), ["amazon_order_id", "AmazonOrderId", "order_id"], ["seller_sku", "SellerSKU", "sku"])
    orders_pending = _prepare_order_sku(_read_csv(root_path / ORDERS_PENDING_RAW), ["amazon_order_id", "order_id"])
    order_items_pending = _prepare_order_sku(
        _read_csv(root_path / ORDER_ITEMS_PENDING_RAW),
        ["amazon_order_id", "AmazonOrderId", "order_id"],
        ["seller_sku", "SellerSKU", "sku"],
    )
    orders_all = _prepare_order_sku(_read_csv(root_path / ORDERS_ALL), ["amazon_order_id", "order_id"])
    order_items_all = _prepare_order_sku(_read_csv(root_path / ORDER_ITEMS_ALL), ["amazon_order_id", "AmazonOrderId", "order_id"], ["seller_sku", "SellerSKU", "sku"])
    order_master = _prepare_order_sku(_read_csv(root_path / ORDER_MASTER), ["Order ID", "order_id"], ["SKU", "seller_sku", "sku"])
    level1 = _prepare_order_sku(_read_csv(root_path / LEVEL1), ["Order ID", "order_id"], ["SKU", "sku"])
    allocations = _prepare_token_allocations(_read_csv(root_path / TOKEN_ALLOCATIONS))
    ledger = _prepare_token_ledger(_read_csv(root_path / TOKEN_LEDGER))
    quarantine = _prepare_quarantine(_read_csv(root_path / QUARANTINE))
    sellerboard = _prepare_order_sku(_read_csv(root_path / SELLERBOARD_RECONCILIATION), ["amazon_order_id", "order_id"], ["mapped_sku", "sku", "sellerboard_sku"])

    source = _source_rows(original_gap_audit, refund_bridge)
    rows: list[dict[str, str]] = []
    for _, source_row in source.iterrows():
        order_id = _text(source_row.get("order_id_norm", ""))
        sku = _norm_sku(source_row.get("sku_norm", ""))
        refund_posted_date = _text(source_row.get("refund_posted_date", ""))
        bridge_rows, bridge_state = _refund_bridge_state(refund_bridge, order_id, sku)

        q_rows = _quarantine_for_order_sku(quarantine, order_id, sku)
        q_api = q_rows[q_rows["proof_label_norm"] == "API proved"] if not q_rows.empty else q_rows
        q_ready = q_rows[q_rows["ready_norm"].isin({"1", "yes", "true", "ready"})] if not q_rows.empty else q_rows
        q_duplicate = (
            q_rows[
                q_rows["duplicate_norm"].str.contains("duplicate", na=False)
                & ~q_rows["duplicate_norm"].isin({"unique", "unique_in_quarantine", "unique_local"})
            ]
            if not q_rows.empty
            else q_rows
        )
        q_field_gap_values: list[str] = []
        for _, q_row in q_api.iterrows() if not q_api.empty else []:
            q_field_gap_values.extend(_quarantine_field_gap(q_row))
        q_field_gaps = sorted(set(q_field_gap_values))

        raw_order_rows = _count_order_sku(orders_raw, order_id, sku)
        raw_item_rows = _count_order_sku(order_items_raw, order_id, sku)
        pending_order_rows = _count_order_sku(orders_pending, order_id, sku)
        pending_item_rows = _count_order_sku(order_items_pending, order_id, sku)
        compiled_order_rows = _count_order_sku(orders_all, order_id, sku)
        compiled_item_rows = _count_order_sku(order_items_all, order_id, sku)
        master_rows = _count_order_sku(order_master, order_id, sku)
        level1_rows = _count_order_sku(level1, order_id, sku)
        allocation_rows = _count_order_sku(allocations, order_id, sku)
        ledger_allocated_rows = (
            int(((ledger["allocated_order_norm"] == order_id) & (ledger["sku_norm"] == sku)).sum()) if not ledger.empty else 0
        )
        api_refund_rows = _count_order_sku(refund_events, order_id, sku)
        sellerboard_rows = _count_order_sku(sellerboard, order_id, sku)

        state, expectation, worker_task, retest = _classify(
            api_refund_rows=api_refund_rows,
            raw_order_rows=raw_order_rows,
            raw_item_rows=raw_item_rows,
            pending_order_rows=pending_order_rows,
            pending_item_rows=pending_item_rows,
            compiled_order_rows=compiled_order_rows,
            compiled_item_rows=compiled_item_rows,
            master_rows=master_rows,
            level1_rows=level1_rows,
            allocation_rows=allocation_rows,
            ledger_allocated_rows=ledger_allocated_rows,
            quarantine_rows=len(q_rows),
            quarantine_api_rows=len(q_api),
            quarantine_ready_rows=len(q_ready),
            quarantine_duplicate_rows=len(q_duplicate),
            quarantine_field_gaps=len(q_field_gaps),
        )
        proof_rows = q_api if not q_api.empty else q_rows
        rows.append(
            {
                "order_id": order_id,
                "sku": sku,
                "refund_posted_date": refund_posted_date,
                "api_refund_rows": str(api_refund_rows),
                "refund_bridge_rows": str(bridge_rows),
                "refund_bridge_original_order_state": bridge_state,
                "orders_raw_rows": str(raw_order_rows),
                "order_items_raw_rows": str(raw_item_rows),
                "orders_pending_raw_rows": str(pending_order_rows),
                "order_items_pending_raw_rows": str(pending_item_rows),
                "orders_all_rows": str(compiled_order_rows),
                "order_items_all_rows": str(compiled_item_rows),
                "order_master_rows": str(master_rows),
                "level1_rows": str(level1_rows),
                "token_allocation_rows": str(allocation_rows),
                "token_ledger_allocated_rows": str(ledger_allocated_rows),
                "quarantine_rows": str(len(q_rows)),
                "quarantine_api_proved_rows": str(len(q_api)),
                "quarantine_ready_for_live_merge_rows": str(len(q_ready)),
                "quarantine_duplicate_risk_rows": str(len(q_duplicate)),
                "quarantine_required_field_gaps": "|".join(q_field_gaps),
                "sellerboard_witness_rows": str(sellerboard_rows),
                "purchase_date_proof": _first_proof(proof_rows, ["purchase_utc", "purchase_date", "PurchaseDate"]),
                "marketplace_proof": _first_proof(proof_rows, ["marketplace_id", "MarketplaceId", "sales_channel"]),
                "order_item_proof": _first_proof(proof_rows, ["order_item_ids", "order_item_id", "OrderItemId"]),
                "currency_proof": _first_proof(proof_rows, ["currency", "order_total_currency", "item_price_currency"]),
                "original_order_recovery_state": state,
                "manager_expectation": expectation,
                "bounded_worker_task": worker_task,
                "retest_rule": retest,
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "protected_before_apply": "1",
            }
        )

    proof = pd.DataFrame(rows, columns=PROOF_COLUMNS).fillna("")
    unclassified = proof[
        (proof["original_order_recovery_state"].astype(str).str.strip() == "")
        | (proof["manager_expectation"].astype(str).str.strip() == "")
        | (proof["bounded_worker_task"].astype(str).str.strip() == "")
    ] if not proof.empty else proof
    unsafe_rows = 0
    if not proof.empty:
        unsafe_rows = int(
            (proof["preview_live_write_allowed"].astype(str).str.strip() != "0").sum()
            + (proof["roi_or_restock_use_allowed"].astype(str).str.strip() != "0").sum()
            + (proof["sellerboard_final_truth_allowed"].astype(str).str.strip() != "0").sum()
        )
    status = "ok"
    if source.empty and original_gap_audit.empty and refund_bridge.empty:
        status = "not_checked"
    elif len(unclassified) or unsafe_rows:
        status = "fail"
    summary_values = {
        "status": status,
        "observed_utc": observed,
        "proof_rows": str(len(proof)),
        "needs_api_original_order_fetch_rows": str(
            int((proof["original_order_recovery_state"] == "needs_api_original_order_fetch_to_quarantine").sum()) if not proof.empty else 0
        ),
        "api_quarantine_original_order_rows": str(
            int((proof["original_order_recovery_state"] == "api_quarantine_original_order_proof_exists").sum()) if not proof.empty else 0
        ),
        "api_quarantine_incomplete_rows": str(
            int((proof["original_order_recovery_state"] == "api_quarantine_original_order_incomplete").sum()) if not proof.empty else 0
        ),
        "local_raw_order_seen_compiled_gap_rows": str(
            int((proof["original_order_recovery_state"] == "local_raw_order_seen_compiled_gap").sum()) if not proof.empty else 0
        ),
        "local_order_seen_allocation_missing_rows": str(
            int((proof["original_order_recovery_state"] == "local_order_seen_but_allocation_missing").sum()) if not proof.empty else 0
        ),
        "protected_promotion_decision_rows": str(
            int((proof["original_order_recovery_state"] == "protected_promotion_decision_needed").sum()) if not proof.empty else 0
        ),
        "duplicate_risk_rows": str(
            int((proof["original_order_recovery_state"] == "quarantine_duplicate_risk_blocks_recovery").sum()) if not proof.empty else 0
        ),
        "unclassified_rows": str(len(unclassified)),
        "unsafe_rows": str(unsafe_rows),
        "live_write_allowed_rows": str(int((proof["preview_live_write_allowed"].astype(str).str.strip() != "0").sum()) if not proof.empty else 0),
        "roi_or_restock_allowed_rows": str(int((proof["roi_or_restock_use_allowed"].astype(str).str.strip() != "0").sum()) if not proof.empty else 0),
        "sellerboard_final_truth_allowed_rows": str(
            int((proof["sellerboard_final_truth_allowed"].astype(str).str.strip() != "0").sum()) if not proof.empty else 0
        ),
    }
    summary = pd.DataFrame([{"metric": key, "value": value} for key, value in summary_values.items()], columns=SUMMARY_COLUMNS)
    return {"proof": proof, "summary": summary}


def write_original_order_recovery_proof_outputs(
    result: dict[str, pd.DataFrame],
    *,
    root: Path | str | None = None,
) -> dict[str, Path]:
    root_path = Path(root or ".")
    proof_path = root_path / OUT_PROOF
    summary_path = root_path / OUT_SUMMARY
    safe_to_csv(result["proof"], proof_path, index=False)
    safe_to_csv(result["summary"], summary_path, index=False)
    return {"proof": proof_path, "summary": summary_path}


def main() -> None:
    result = build_original_order_recovery_proof()
    paths = write_original_order_recovery_proof_outputs(result)
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}
    print(
        {
            "status": summary.get("status", ""),
            "proof_rows": summary.get("proof_rows", "0"),
            "needs_api_original_order_fetch_rows": summary.get("needs_api_original_order_fetch_rows", "0"),
            "api_quarantine_original_order_rows": summary.get("api_quarantine_original_order_rows", "0"),
            "unclassified_rows": summary.get("unclassified_rows", "0"),
            "proof": str(paths["proof"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
