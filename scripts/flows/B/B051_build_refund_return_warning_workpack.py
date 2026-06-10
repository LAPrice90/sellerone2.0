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
PREVIEW = OUT / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv"
REPROOF_PREVIEW = OUT / "systems" / "B" / "refunds" / "b_refund_token_reproof_preview.csv"
WORKPACK = OUT / "systems" / "B" / "refunds" / "b_refund_return_warning_workpack.csv"
SUMMARY = OUT / "systems" / "B" / "refunds" / "b_refund_return_warning_workpack_summary.csv"

WORKPACK_COLUMNS = [
    "repair_lane",
    "repair_readiness",
    "row_count",
    "sample_orders",
    "manager_expectation",
    "mot_proof_check",
    "bounded_worker_task",
    "retest_rule",
    "luke_decision_rule",
    "preview_live_write_allowed",
    "roi_or_restock_use_allowed",
    "sellerboard_final_truth_allowed",
    "protected_before_apply",
    "manager_state",
]

SUMMARY_COLUMNS = ["metric", "value"]

LANE_GUIDE = {
    "amazon_return_coverage_review": {
        "manager_expectation": "Stock recovery stays untrusted until Amazon return coverage is proved or a non-customer-return exception is labelled.",
        "mot_proof_check": "B052/B039/B041/B038 plus B MOT must show either matched Amazon return proof or an approved exception label.",
        "bounded_worker_task": "Run the B052 coverage audit to separate customer-return proof from stock-adjustment-only proof; do not change token stock.",
        "retest_rule": "Rerun B052/B039/B041/B038 and B MOT; rows clear only when Amazon return proof or approved exception proof exists.",
        "luke_decision_rule": "Luke only decides if Codex proposes trusting stock recovery without Amazon return proof.",
        "manager_state": "parked_needs_amazon_return_coverage_proof",
    },
    "protected_disposition_conflict": {
        "manager_expectation": "Amazon says the item is not sellable, so reusable stock must stay blocked unless a protected review proves otherwise.",
        "mot_proof_check": "B041/B038/B MOT must show no reusable-token proof for non-sellable returns, or an explicit approved exception.",
        "bounded_worker_task": "Prepare a protected disposition-conflict correction preview; do not alter token stock in this packet.",
        "retest_rule": "After any protected correction, rerun B041/B038 and B MOT; row clears only when non-sellable stock recovery is blocked or approved.",
        "luke_decision_rule": "Luke must approve any live token correction or exception that treats a non-sellable return as reusable.",
        "manager_state": "needs_protected_disposition_decision_before_live_fix",
    },
    "protected_original_return_status_conflict": {
        "manager_expectation": "The original sold token has a live stock status after return proof, so it must not be treated as clean reusable returned stock.",
        "mot_proof_check": "B042/B041/B038/B MOT must show the original returned token state is repaired or explicitly exception-labelled before stock recovery is trusted.",
        "bounded_worker_task": "Prepare a protected original returned-token state review; do not alter token stock in this packet.",
        "retest_rule": "After any protected correction or exception label, rerun B042/B041/B038/B051 and B MOT.",
        "luke_decision_rule": "Luke must approve any live token correction or exception that treats this original-token state as acceptable.",
        "manager_state": "needs_protected_original_return_status_decision",
    },
    "protected_return_cogs_residual_conflict": {
        "manager_expectation": "Amazon says the return was not sellable, so return COGS recovery must stay blocked unless a protected correction or exception proves it.",
        "mot_proof_check": "B041/B038/B051/B MOT must show non-sellable return COGS recovery is removed, corrected, or explicitly exception-labelled before ROI trusts stock recovery.",
        "bounded_worker_task": "Prepare a protected return COGS residual review; do not alter token_return_ledger or ROI in this packet.",
        "retest_rule": "After any protected correction or exception label, rerun B041/B038/B051 and B MOT.",
        "luke_decision_rule": "Luke must approve any live COGS correction or exception for non-sellable return stock recovery.",
        "manager_state": "needs_protected_return_cogs_residual_decision",
    },
    "b008_allocation_gap": {
        "manager_expectation": "The original sale token must be found before B008 can mark the refund token path.",
        "mot_proof_check": "B053/B041/B042 must show the original order and allocation are manager-readable before any B008 reproof is attempted.",
        "bounded_worker_task": "Use B053 to prove whether the original order, order item, allocation, or token ledger is the earliest missing source; do not create replacement stock.",
        "retest_rule": "Rerun B053/B041/B042/B038 and B MOT after original order/allocation proof exists.",
        "luke_decision_rule": "Luke only decides if missing allocation proof would require a stock/token correction.",
        "manager_state": "parked_needs_original_allocation_proof",
    },
    "b008_refund_token_marking": {
        "manager_expectation": "One row is technically ready for a B008-style reproof, but it touches live token/refund-event state.",
        "mot_proof_check": "B042 must show the same row ready, then a protected proof window must apply it and B041/B038/B MOT must clear.",
        "bounded_worker_task": "Package a protected B008 refund-token marking repair for the named order/SKU only.",
        "retest_rule": "After protected B008 repair, rerun B042/B041/B038 and B MOT.",
        "luke_decision_rule": "Luke must approve the protected token/refund-event write window.",
        "manager_state": "candidate_for_protected_b008_reproof",
    },
    "b008_token_ledger_gap": {
        "manager_expectation": "The allocation names a sold token, but the current token ledger cannot prove that token exists in the expected state.",
        "mot_proof_check": "B042 must show the allocated token is visible in the token ledger before any B008 repair is proposed.",
        "bounded_worker_task": "Trace why the allocated token is missing from token-ledger proof; do not create a substitute token.",
        "retest_rule": "Rerun B042/B041/B038 and B MOT after the ledger proof is repaired or exception-labelled.",
        "luke_decision_rule": "Luke decides only if Codex proposes a live stock/token correction.",
        "manager_state": "parked_needs_token_ledger_proof",
    },
    "bridge_mapping_retest": {
        "manager_expectation": "The deeper proof says this should not be treated as a B008 write; the bridge or return COGS mapping needs to recognise an already closed or reused token.",
        "mot_proof_check": "B042 must stay clear of ready B008 rows, and B041/B038 must stop asking for B008/B009 work for the same already-closed token.",
        "bounded_worker_task": "Repair manager proof mapping so closed/reused token evidence is recognised without writing live token state.",
        "retest_rule": "Rerun B042/B041/B038/B051 and B MOT; row clears only when the bridge no longer proposes a live B008/B009 action.",
        "luke_decision_rule": "Luke decides only if mapping proof shows a live token correction is truly required.",
        "manager_state": "parked_needs_bridge_mapping_retest",
    },
    "b009_waiting_for_returned_pending_trace": {
        "manager_expectation": "B009 cannot reuse stock until B008 returned-pending proof is visible.",
        "mot_proof_check": "B041 must show a returned_pending token before any B009 order-aware repair is proposed.",
        "bounded_worker_task": "Repair B008 proof first, then retry B009 preview; do not create reusable tokens from the bridge.",
        "retest_rule": "Rerun B041 after B008 proof improves; then B038 and B MOT must clear.",
        "luke_decision_rule": "Luke only decides if the next step becomes a live token correction.",
        "manager_state": "parked_waiting_for_b008_trace",
    },
    "b009_order_aware_sellable_return": {
        "manager_expectation": "Amazon says the returned unit is sellable and B008 returned-pending token proof is visible, so B009 can create reusable returned stock through the normal token route.",
        "mot_proof_check": "B041 must show Amazon SELLABLE proof, the returned_pending token, no existing reusable duplicate, and no return COGS trace before B009 apply.",
        "bounded_worker_task": "Apply B009 order-aware returned-token reuse only inside a protected maintenance window; do not create reusable stock from Sellerboard or bridge estimates.",
        "retest_rule": "After protected B009 repair, rerun B041/B038/B051 and B MOT; row clears only when reusable token and return COGS proof agree.",
        "luke_decision_rule": "Luke must approve the protected B009 token write window unless it is already covered by the current approved repair packet.",
        "manager_state": "candidate_for_protected_b009_order_aware_reuse",
    },
}


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _text(value: object) -> str:
    return str(value or "").strip()


def _sample_orders(group: pd.DataFrame, limit: int = 5) -> str:
    orders = []
    seen = set()
    for value in group.get("order_id", pd.Series([], dtype=str)).tolist():
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        orders.append(text)
        if len(orders) >= limit:
            break
    return "|".join(orders)


def _safety_count(group: pd.DataFrame, column: str) -> int:
    if column not in group.columns:
        return len(group)
    return int((group[column].astype(str).str.strip() != "0").sum())


def _refine_preview_with_b008_reproof(preview: pd.DataFrame, reproof: pd.DataFrame) -> pd.DataFrame:
    if preview.empty or reproof.empty:
        return preview
    work = preview.copy()
    for column in ["order_id", "sku", "repair_lane", "repair_readiness"]:
        if column not in work.columns:
            work[column] = ""
    needed = {"order_id", "sku", "reproof_lane", "reproof_readiness"}
    if not needed.issubset(set(reproof.columns)):
        return work
    detail = reproof.copy()
    for column in needed:
        detail[column] = detail[column].map(_text)
    detail["__key"] = detail["order_id"] + "\n" + detail["sku"]
    by_key = {
        row["__key"]: (row["reproof_lane"], row["reproof_readiness"])
        for _, row in detail.iterrows()
        if row["__key"].strip()
    }
    for idx, row in work.iterrows():
        lane = _text(row.get("repair_lane", ""))
        if lane not in {"b008_refund_token_marking", "b008_allocation_gap", "b009_waiting_for_returned_pending_trace"}:
            continue
        key = f"{_text(row.get('order_id', ''))}\n{_text(row.get('sku', ''))}"
        reproof_lane, reproof_readiness = by_key.get(key, ("", ""))
        if not reproof_lane:
            continue
        if reproof_lane == "already_closed_or_reused":
            work.at[idx, "repair_lane"] = "bridge_mapping_retest"
            work.at[idx, "repair_readiness"] = reproof_readiness or "blocked_bridge_mapping_retest"
        elif reproof_lane == "token_ledger_gap":
            work.at[idx, "repair_lane"] = "b008_token_ledger_gap"
            work.at[idx, "repair_readiness"] = reproof_readiness or "blocked_missing_allocated_token_in_ledger"
        elif reproof_lane == "original_allocation_gap":
            work.at[idx, "repair_lane"] = "b008_allocation_gap"
            work.at[idx, "repair_readiness"] = reproof_readiness or "blocked_missing_original_allocation"
        elif reproof_lane == "token_state_conflict":
            work.at[idx, "repair_lane"] = "protected_original_return_status_conflict"
            work.at[idx, "repair_readiness"] = reproof_readiness or "blocked_needs_protected_review"
        elif reproof_lane in {"b008_refund_token_marking", "b008_event_ledger_state_drift"}:
            work.at[idx, "repair_lane"] = "b008_refund_token_marking"
            work.at[idx, "repair_readiness"] = reproof_readiness or "ready_for_b008_order_sku_reproof"
        elif reproof_lane == "already_returned_pending":
            work.at[idx, "repair_lane"] = "b009_order_aware_sellable_return"
            work.at[idx, "repair_readiness"] = reproof_readiness or "ready_for_b009_after_retest"
    return work


def build_refund_return_warning_workpack(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
) -> dict[str, pd.DataFrame]:
    root_path = Path(root or ".")
    observed = observed_utc or _utc_now_text()
    preview = _read_csv(root_path / PREVIEW)
    reproof = _read_csv(root_path / REPROOF_PREVIEW)
    preview = _refine_preview_with_b008_reproof(preview, reproof)
    rows: list[dict[str, str]] = []
    unclassified_rows = 0
    live_write_total = 0
    roi_total = 0
    sellerboard_total = 0
    protected_rows = 0

    if not preview.empty:
        for column in [
            "repair_lane",
            "repair_readiness",
            "order_id",
            "preview_live_write_allowed",
            "roi_or_restock_use_allowed",
            "sellerboard_final_truth_allowed",
            "protected_before_apply",
        ]:
            if column not in preview.columns:
                preview[column] = ""
        for (lane, readiness), group in preview.groupby(["repair_lane", "repair_readiness"], dropna=False):
            lane = _text(lane)
            readiness = _text(readiness)
            guide = LANE_GUIDE.get(lane)
            live_write_rows = _safety_count(group, "preview_live_write_allowed")
            roi_rows = _safety_count(group, "roi_or_restock_use_allowed")
            sellerboard_rows = _safety_count(group, "sellerboard_final_truth_allowed")
            protected_count = int((group["protected_before_apply"].astype(str).str.strip() == "1").sum())
            protected_rows += protected_count
            live_write_total += live_write_rows
            roi_total += roi_rows
            sellerboard_total += sellerboard_rows
            if guide is None or not lane or not readiness:
                unclassified_rows += len(group)
                guide = {
                    "manager_expectation": "This lane is not yet manager-classified.",
                    "mot_proof_check": "Add a lane guide before any worker repair is allowed.",
                    "bounded_worker_task": "Split this row group into a smaller proof packet.",
                    "retest_rule": "Rerun B051 and B MOT after classification exists.",
                    "luke_decision_rule": "Luke decides only if the row crosses protected action boundaries.",
                    "manager_state": "unclassified_needs_manager_mapping",
                }
            rows.append(
                {
                    "repair_lane": lane,
                    "repair_readiness": readiness,
                    "row_count": str(len(group)),
                    "sample_orders": _sample_orders(group),
                    "manager_expectation": guide["manager_expectation"],
                    "mot_proof_check": guide["mot_proof_check"],
                    "bounded_worker_task": guide["bounded_worker_task"],
                    "retest_rule": guide["retest_rule"],
                    "luke_decision_rule": guide["luke_decision_rule"],
                    "preview_live_write_allowed": str(live_write_rows),
                    "roi_or_restock_use_allowed": str(roi_rows),
                    "sellerboard_final_truth_allowed": str(sellerboard_rows),
                    "protected_before_apply": str(protected_count),
                    "manager_state": guide["manager_state"],
                }
            )

    workpack = pd.DataFrame(rows, columns=WORKPACK_COLUMNS).fillna("")
    status = "ok"
    if preview.empty:
        status = "not_checked"
    elif unclassified_rows:
        status = "fail"
    elif live_write_total or roi_total or sellerboard_total:
        status = "fail"
    summary = pd.DataFrame(
        [
            {"metric": "status", "value": status},
            {"metric": "observed_utc", "value": observed},
            {"metric": "preview_rows", "value": str(len(preview))},
            {"metric": "workpack_lanes", "value": str(len(workpack))},
            {"metric": "classified_rows", "value": str(max(len(preview) - unclassified_rows, 0))},
            {"metric": "unclassified_rows", "value": str(unclassified_rows)},
            {"metric": "unsafe_rows", "value": str(live_write_total + roi_total + sellerboard_total)},
            {"metric": "protected_rows", "value": str(protected_rows)},
            {"metric": "live_write_allowed_rows", "value": str(live_write_total)},
            {"metric": "roi_or_restock_allowed_rows", "value": str(roi_total)},
            {"metric": "sellerboard_final_truth_allowed_rows", "value": str(sellerboard_total)},
        ],
        columns=SUMMARY_COLUMNS,
    )
    return {"workpack": workpack, "summary": summary}


def write_refund_return_warning_workpack_outputs(
    result: dict[str, pd.DataFrame],
    *,
    root: Path | str | None = None,
) -> dict[str, Path]:
    root_path = Path(root or ".")
    workpack_path = root_path / WORKPACK
    summary_path = root_path / SUMMARY
    safe_to_csv(result["workpack"], workpack_path, index=False)
    safe_to_csv(result["summary"], summary_path, index=False)
    return {"workpack": workpack_path, "summary": summary_path}


def main() -> None:
    result = build_refund_return_warning_workpack()
    paths = write_refund_return_warning_workpack_outputs(result)
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}
    print(
        {
            "status": summary.get("status", ""),
            "preview_rows": summary.get("preview_rows", "0"),
            "workpack_lanes": summary.get("workpack_lanes", "0"),
            "unclassified_rows": summary.get("unclassified_rows", "0"),
            "protected_rows": summary.get("protected_rows", "0"),
            "workpack": str(paths["workpack"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
