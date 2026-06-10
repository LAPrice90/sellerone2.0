from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.safe_file_writes import safe_to_csv


OUT = Path("out")
AUDIT = OUT / "systems" / "B" / "refunds" / "b_return_token_matching_audit.csv"
BRIDGE = OUT / "systems" / "B" / "refunds" / "b_refund_return_token_bridge.csv"
TOKEN_LEDGER = OUT / "token_ledger_live.csv"
TOKEN_ALLOCATIONS = OUT / "token_allocations_live.csv"
TOKEN_RETURN_LEDGER = OUT / "token_return_ledger.csv"
OUT_PREVIEW = OUT / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv"
OUT_SUMMARY = OUT / "systems" / "B" / "refunds" / "b_return_token_repair_preview_summary.csv"

PREVIEW_COLUMNS = [
    "order_id",
    "sku",
    "proof_label",
    "diagnosis",
    "amazon_return_disposition",
    "refund_posted_date",
    "amazon_return_date",
    "b008_applied_qty",
    "returned_pending_token_ids",
    "reusable_return_token_ids",
    "unsafe_original_token_ids",
    "allocated_original_token_ids",
    "return_cogs_token_ids",
    "repair_lane",
    "repair_readiness",
    "preview_action",
    "would_touch_live_outputs",
    "preview_live_write_allowed",
    "protected_before_apply",
    "sellerboard_final_truth_allowed",
    "roi_or_restock_use_allowed",
    "bounded_worker_task",
    "retest_rule",
    "protected_stop_rule",
]

SUMMARY_COLUMNS = ["metric", "value"]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


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


def _unique_text(values: list[object]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _join(values: list[str]) -> str:
    return "|".join(_unique_text(values))


def _prepare_ledger(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in [
        "token_id",
        "seller_sku",
        "status",
        "return_order_id",
        "last_return_order_id",
        "allocated_order_id",
        "notes",
    ]:
        if column not in work.columns:
            work[column] = ""
    work["sku_norm"] = work["seller_sku"].map(_norm_sku)
    work["status_norm"] = work["status"].map(lambda value: _text(value).lower())
    work["return_order_norm"] = work["return_order_id"].map(_text)
    work["last_return_order_norm"] = work["last_return_order_id"].map(_text)
    work["allocated_order_norm"] = work["allocated_order_id"].map(_text)
    work["notes_norm"] = work["notes"].map(lambda value: _text(value).lower())
    return work


def _prepare_allocations(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["order_id", "seller_sku", "token_id"]:
        if column not in work.columns:
            work[column] = ""
    work["order_id_norm"] = work["order_id"].map(_text)
    work["sku_norm"] = work["seller_sku"].map(_norm_sku)
    return work


def _prepare_return_cogs(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["seller_sku", "token_id"]:
        if column not in work.columns:
            work[column] = ""
    work["sku_norm"] = work["seller_sku"].map(_norm_sku)
    return work


def _bridge_by_key(df: pd.DataFrame) -> dict[tuple[str, str], dict[str, str]]:
    if df.empty:
        return {}
    work = df.copy()
    for column in ["order_id", "sku"]:
        if column not in work.columns:
            work[column] = ""
    out: dict[tuple[str, str], dict[str, str]] = {}
    for _, row in work.iterrows():
        order_id = _text(row.get("order_id", ""))
        sku = _norm_sku(row.get("sku", ""))
        if order_id and sku:
            out[(order_id, sku)] = {column: _text(row.get(column, "")) for column in work.columns}
    return out


def _ledger_state(ledger: pd.DataFrame, order_id: str, sku: str) -> dict[str, list[str]]:
    if ledger.empty:
        return {
            "returned_pending": [],
            "reusable": [],
            "non_sellable": [],
            "returned_complete": [],
            "allocated_original": [],
            "unsafe_original": [],
        }
    sku_rows = ledger[ledger["sku_norm"] == sku].copy()
    order_match = (
        (sku_rows["return_order_norm"] == order_id)
        | (sku_rows["last_return_order_norm"] == order_id)
        | (sku_rows["allocated_order_norm"] == order_id)
    )
    rows = sku_rows[order_match].copy()
    returned_pending = rows[
        (rows["status_norm"] == "returned_pending")
        & (rows["return_order_norm"] == order_id)
    ]["token_id"].tolist()
    returned_complete = rows[
        (rows["status_norm"] == "returned_complete")
        & (rows["last_return_order_norm"] == order_id)
    ]["token_id"].tolist()
    non_sellable = rows[rows["status_norm"].isin(["unsellable", "research_pending"])]["token_id"].tolist()
    allocated_original = rows[rows["allocated_order_norm"] == order_id]["token_id"].tolist()
    reusable_rows = rows[
        rows["notes_norm"].str.contains("return_sellable_dup", na=False)
        & (rows["last_return_order_norm"] == order_id)
        & (rows["status_norm"].isin(["available", "allocated", "warehouse"]))
    ]
    unsafe_original_rows = rows[
        rows["status_norm"].isin(["available", "allocated", "warehouse"])
        & (rows["last_return_order_norm"] == order_id)
        & (
            rows["notes_norm"].str.contains("return_closed", na=False)
            | rows["notes_norm"].str.contains("return_unsellable", na=False)
            | rows["notes_norm"].str.contains("return_researching", na=False)
            | rows["notes_norm"].str.contains("researching_negative", na=False)
        )
    ]
    return {
        "returned_pending": _unique_text(returned_pending),
        "reusable": _unique_text(reusable_rows["token_id"].tolist()),
        "non_sellable": _unique_text(non_sellable),
        "returned_complete": _unique_text(returned_complete),
        "allocated_original": _unique_text(allocated_original),
        "unsafe_original": _unique_text(unsafe_original_rows["token_id"].tolist()),
    }


def _allocation_token_ids(allocations: pd.DataFrame, order_id: str, sku: str) -> list[str]:
    if allocations.empty:
        return []
    rows = allocations[(allocations["order_id_norm"] == order_id) & (allocations["sku_norm"] == sku)]
    return _unique_text(rows["token_id"].tolist())


def _return_cogs_token_ids(return_cogs: pd.DataFrame, sku: str, token_ids: list[str]) -> list[str]:
    if return_cogs.empty or not token_ids:
        return []
    token_set = set(token_ids)
    rows = return_cogs[(return_cogs["sku_norm"] == sku) & (return_cogs["token_id"].isin(token_set))]
    return _unique_text(rows["token_id"].tolist())


def _classify_preview(
    *,
    audit_row: pd.Series,
    bridge_row: dict[str, str],
    pending_ids: list[str],
    reusable_ids: list[str],
    unsafe_original_ids: list[str],
    allocated_ids: list[str],
    return_cogs_ids: list[str],
) -> tuple[str, str, str, str, str, str]:
    label = _text(audit_row.get("proof_label", ""))
    diagnosis = _text(audit_row.get("diagnosis", ""))
    disposition = _text(audit_row.get("amazon_return_disposition", "")).upper()
    b008_applied = _num(audit_row.get("b008_applied_qty", "0"))
    cogs = _num(bridge_row.get("return_cogs_recovered_exvat", audit_row.get("return_cogs_recovered_exvat", "0")))

    if unsafe_original_ids or "Original returned token has a live status" in diagnosis:
        return (
            "protected_original_return_status_conflict",
            "blocked_needs_protected_review",
            "Stop before any live correction. The original returned token has a live stock status, but that is not clean reusable-stock proof.",
            "token_ledger_live.csv;token_return_ledger.csv",
            "Audit why the original returned token is live and repair only through the normal B008/B009 token lifecycle.",
            "Rerun B040, B041, B038, and B MOT; row clears only when the original token state and returned-stock duplicate proof agree.",
        )

    if (
        ("Amazon says the return was not sellable" in diagnosis and (reusable_ids or return_cogs_ids))
        or (disposition and disposition != "SELLABLE" and reusable_ids)
    ):
        return (
            "protected_disposition_conflict",
            "blocked_needs_protected_review",
            "Stop before any live correction. Amazon says this return should not be reusable, but token proof suggests reuse.",
            "token_ledger_live.csv;token_return_ledger.csv",
            "Audit B009 order-aware disposition matching and prepare a protected correction plan only after Luke approves.",
            "Rerun B041, B038, and B MOT; row clears only when non-sellable returns no longer have reusable-token proof or are approved exceptions.",
        )

    if label == "returned_unsellable_no_reuse" and (
        cogs > 0 or "return COGS recovery evidence" in diagnosis or "recovered COGS" in diagnosis
    ):
        return (
            "protected_return_cogs_residual_conflict",
            "blocked_needs_protected_review",
            "Stop before any live correction. Amazon says the return was not sellable, but return COGS recovery proof still exists.",
            "token_return_ledger.csv",
            "Prepare a protected return COGS residual review; do not alter stock recovery or ROI from this preview.",
            "Rerun B041, B038, B051, and B MOT; row clears only when non-sellable return COGS recovery is removed, corrected, or approved as an exception.",
        )

    if label == "returned_sellable_token_missing":
        if b008_applied <= 0:
            if allocated_ids:
                return (
                    "b008_refund_token_marking",
                    "ready_for_b008_order_sku_reproof",
                    "Preview marking the original allocated token as returned_pending through B008's normal order/SKU path.",
                    "token_ledger_live.csv;refund_token_events.csv",
                    "Repair B008 refund-token mapping for this order/SKU; do not hand-edit token rows.",
                    "Rerun B008 in an approved proof window, then B041, B038, and B MOT; row clears when returned_pending proof appears.",
                )
            return (
                "b008_allocation_gap",
                "blocked_missing_original_allocation",
                "Cannot preview a B008 token mark because the original order/SKU allocation is not manager-readable.",
                "token_allocations_live.csv",
                "Repair or prove the original token allocation source before refund stock recovery is trusted.",
                "Rerun B041 after allocation proof exists; do not create replacement tokens as a shortcut.",
            )
        if pending_ids:
            return (
                "b009_order_aware_sellable_return",
                "ready_for_b009_order_aware_preview",
                "Preview closing the returned_pending token and creating the reusable returned token through B009, matched by Amazon order/SKU.",
                "token_ledger_live.csv;stock_adjustment_token_events.csv;token_return_ledger.csv",
                "Add B009 order-aware customer-return matching that prefers Amazon order/SKU proof before SKU FIFO.",
                "Rerun B009 only in an approved proof window, then B041, B038, and B MOT; row clears when reusable token and return COGS proof appear.",
            )
        return (
            "b009_waiting_for_returned_pending_trace",
            "blocked_missing_returned_pending_token",
            "Amazon says sellable, but the matching returned_pending token is not visible for this order/SKU.",
            "token_ledger_live.csv;refund_token_events.csv",
            "Repair B008 proof first, then retry B009 order-aware matching.",
            "Rerun B041 after B008 proof improves; do not create reusable stock directly from the bridge.",
        )

    if label == "returned_sellable_token_reused" and (cogs <= 0 or not return_cogs_ids):
        return (
            "return_cogs_trace",
            "ready_for_return_cogs_trace_preview" if reusable_ids else "blocked_missing_reusable_token_trace",
            "Preview adding manager-readable return COGS trace for an already reused sellable returned token.",
            "token_return_ledger.csv",
            "Repair return COGS trace proof through the existing return ledger path before ROI uses stock recovery.",
            "Rerun B041, B038, and B MOT; row clears when reused token and return COGS proof agree.",
        )

    if label == "token_reuse_without_amazon_return_proof":
        return (
            "amazon_return_coverage_review",
            "blocked_missing_amazon_order_return_proof",
            "Do not trust stock recovery yet. Token or COGS proof exists, but Amazon customer-return proof did not match the same order/SKU.",
            "b_fba_customer_returns.csv;token_ledger_live.csv;token_return_ledger.csv",
            "Check whether this is an Amazon report coverage gap, a non-customer-return adjustment, or weak bridge mapping.",
            "Rerun B039/B041/B038 and B MOT; row clears only when Amazon return proof matches or the reuse is labelled as an approved non-customer-return exception.",
        )

    if "recovered COGS" in diagnosis or "return COGS" in diagnosis:
        return (
            "return_cogs_trace",
            "ready_for_return_cogs_trace_preview" if reusable_ids or cogs > 0 else "blocked_missing_cogs_source",
            "Preview making return COGS trace manager-readable by order/SKU/token.",
            "token_return_ledger.csv",
            "Repair return COGS source mapping before ROI uses stock recovery.",
            "Rerun B041, B038, and B MOT; row clears when COGS proof is tied to token-return evidence.",
        )

    return (
        "proof_mapping_review",
        "blocked_needs_smaller_worker_packet",
        "The row is classified, but it needs a smaller proof-mapping repair before any live action.",
        "",
        "Create a smaller B proof-mapping task for this diagnosis group.",
        "Rerun B041 after the diagnosis group has a concrete proof source.",
    )


def build_return_token_repair_preview(*, root: Path | str | None = None) -> dict[str, object]:
    root_path = Path(root or ".")
    audit = _read_csv(root_path / AUDIT)
    bridge = _bridge_by_key(_read_csv(root_path / BRIDGE))
    ledger = _prepare_ledger(_read_csv(root_path / TOKEN_LEDGER))
    allocations = _prepare_allocations(_read_csv(root_path / TOKEN_ALLOCATIONS))
    return_cogs = _prepare_return_cogs(_read_csv(root_path / TOKEN_RETURN_LEDGER))

    rows: list[dict[str, str]] = []
    for _, audit_row in audit.iterrows():
        order_id = _text(audit_row.get("order_id", ""))
        sku = _norm_sku(audit_row.get("sku", ""))
        if not order_id or not sku:
            continue
        bridge_row = bridge.get((order_id, sku), {})
        state = _ledger_state(ledger, order_id, sku)
        allocated_ids = _allocation_token_ids(allocations, order_id, sku) or state["allocated_original"]
        reusable_ids = state["reusable"]
        unsafe_original_ids = state["unsafe_original"]
        return_cogs_ids = _return_cogs_token_ids(return_cogs, sku, reusable_ids + state["returned_complete"])
        lane, readiness, action, touched, worker_task, retest = _classify_preview(
            audit_row=audit_row,
            bridge_row=bridge_row,
            pending_ids=state["returned_pending"],
            reusable_ids=reusable_ids,
            unsafe_original_ids=unsafe_original_ids,
            allocated_ids=allocated_ids,
            return_cogs_ids=return_cogs_ids,
        )
        protected = "1" if touched else "0"
        rows.append(
            {
                "order_id": order_id,
                "sku": sku,
                "proof_label": _text(audit_row.get("proof_label", "")),
                "diagnosis": _text(audit_row.get("diagnosis", "")),
                "amazon_return_disposition": _text(audit_row.get("amazon_return_disposition", "")),
                "refund_posted_date": _text(audit_row.get("refund_posted_date", "")),
                "amazon_return_date": _text(audit_row.get("amazon_return_date", "")),
                "b008_applied_qty": _text(audit_row.get("b008_applied_qty", "")),
                "returned_pending_token_ids": _join(state["returned_pending"]),
                "reusable_return_token_ids": _join(reusable_ids),
                "unsafe_original_token_ids": _join(unsafe_original_ids),
                "allocated_original_token_ids": _join(allocated_ids),
                "return_cogs_token_ids": _join(return_cogs_ids),
                "repair_lane": lane,
                "repair_readiness": readiness,
                "preview_action": action,
                "would_touch_live_outputs": touched,
                "preview_live_write_allowed": "0",
                "protected_before_apply": protected,
                "sellerboard_final_truth_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "bounded_worker_task": worker_task,
                "retest_rule": retest,
                "protected_stop_rule": (
                    "Stop before token correction, B run/restart, Sheet write, DB alignment, output deletion, "
                    "ROI/restocking use, price/queue change, or widening beyond B return-token repair."
                ),
            }
        )

    preview = pd.DataFrame(rows, columns=PREVIEW_COLUMNS).fillna("")
    unclassified = preview[
        (preview["repair_lane"].astype(str).str.strip() == "")
        | (preview["repair_readiness"].astype(str).str.strip() == "")
        | (preview["preview_action"].astype(str).str.strip() == "")
    ]
    summary_values = {
        "preview_rows": str(len(preview)),
        "unclassified_rows": str(len(unclassified)),
        "b008_reproof_rows": str(int((preview["repair_lane"] == "b008_refund_token_marking").sum()) if not preview.empty else 0),
        "b009_order_aware_rows": str(int((preview["repair_lane"] == "b009_order_aware_sellable_return").sum()) if not preview.empty else 0),
        "return_cogs_trace_rows": str(int((preview["repair_lane"] == "return_cogs_trace").sum()) if not preview.empty else 0),
        "amazon_coverage_review_rows": str(int((preview["repair_lane"] == "amazon_return_coverage_review").sum()) if not preview.empty else 0),
        "protected_conflict_rows": str(int((preview["repair_lane"] == "protected_disposition_conflict").sum()) if not preview.empty else 0),
        "protected_original_status_conflict_rows": str(int((preview["repair_lane"] == "protected_original_return_status_conflict").sum()) if not preview.empty else 0),
        "live_write_allowed_rows": str(int((preview["preview_live_write_allowed"] != "0").sum()) if not preview.empty else 0),
        "roi_or_restock_allowed_rows": str(int((preview["roi_or_restock_use_allowed"] != "0").sum()) if not preview.empty else 0),
        "sellerboard_final_truth_allowed_rows": str(int((preview["sellerboard_final_truth_allowed"] != "0").sum()) if not preview.empty else 0),
    }
    summary = pd.DataFrame([{"metric": key, "value": value} for key, value in summary_values.items()], columns=SUMMARY_COLUMNS)
    return {
        "preview": preview,
        "summary": summary,
        "preview_path": root_path / OUT_PREVIEW,
        "summary_path": root_path / OUT_SUMMARY,
    }


def write_return_token_repair_preview_outputs(result: dict[str, object]) -> dict[str, Path]:
    preview_path = Path(result["preview_path"])
    summary_path = Path(result["summary_path"])
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    safe_to_csv(result["preview"], preview_path, index=False)
    safe_to_csv(result["summary"], summary_path, index=False)
    return {"preview": preview_path, "summary": summary_path}


def main() -> None:
    result = build_return_token_repair_preview()
    paths = write_return_token_repair_preview_outputs(result)
    preview = result["preview"]
    summary = result["summary"]
    values = {row["metric"]: row["value"] for _, row in summary.iterrows()} if not summary.empty else {}
    print(
        {
            "status": "success",
            "preview_rows": len(preview),
            "unclassified_rows": int(_num(values.get("unclassified_rows", "0"))),
            "b009_order_aware_rows": int(_num(values.get("b009_order_aware_rows", "0"))),
            "preview": str(paths["preview"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
