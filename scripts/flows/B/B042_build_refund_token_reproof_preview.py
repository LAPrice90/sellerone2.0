from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.safe_file_writes import safe_to_csv


OUT = Path("out")
RETURN_REPAIR_PREVIEW = OUT / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv"
REFUND_TOKEN_EVENTS = OUT / "refund_token_events.csv"
TOKEN_ALLOCATIONS = OUT / "token_allocations_live.csv"
TOKEN_LEDGER = OUT / "token_ledger_live.csv"
OUT_PREVIEW = OUT / "systems" / "B" / "refunds" / "b_refund_token_reproof_preview.csv"
OUT_SUMMARY = OUT / "systems" / "B" / "refunds" / "b_refund_token_reproof_preview_summary.csv"

TARGET_REPAIR_LANES = {
    "b008_refund_token_marking",
    "b008_allocation_gap",
    "b009_waiting_for_returned_pending_trace",
}

PREVIEW_COLUMNS = [
    "order_id",
    "sku",
    "source_repair_lane",
    "source_repair_readiness",
    "diagnosis",
    "b008_event_statuses",
    "b008_requested_qty",
    "b008_applied_qty",
    "b008_event_ids",
    "allocation_token_ids",
    "ledger_allocated_token_ids",
    "returned_pending_token_ids",
    "returned_complete_token_ids",
    "reusable_return_token_ids",
    "conflicting_token_ids",
    "reproof_lane",
    "reproof_readiness",
    "preview_action",
    "would_touch_live_outputs",
    "preview_live_write_allowed",
    "protected_before_apply",
    "roi_or_restock_use_allowed",
    "sellerboard_final_truth_allowed",
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


def _num_text(value: object) -> str:
    number = _num(value)
    if abs(number) < 0.0000005:
        return "0"
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _unique(values: list[object]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _join(values: list[object]) -> str:
    return "|".join(_unique(values))


def _split_token_ids(value: object) -> list[str]:
    return _unique(_text(value).split("|"))


def _prepare_refund_events(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in [
        "order_id",
        "sku",
        "requested_qty",
        "applied_qty",
        "status",
        "note",
        "refund_event_id",
    ]:
        if column not in work.columns:
            work[column] = ""
    work["order_id_norm"] = work["order_id"].map(_text)
    work["sku_norm"] = work["sku"].map(_norm_sku)
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


def _prepare_ledger(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in [
        "token_id",
        "seller_sku",
        "status",
        "allocated_order_id",
        "return_order_id",
        "last_return_order_id",
        "notes",
    ]:
        if column not in work.columns:
            work[column] = ""
    work["sku_norm"] = work["seller_sku"].map(_norm_sku)
    work["status_norm"] = work["status"].map(lambda value: _text(value).lower())
    work["allocated_order_norm"] = work["allocated_order_id"].map(_text)
    work["return_order_norm"] = work["return_order_id"].map(_text)
    work["last_return_order_norm"] = work["last_return_order_id"].map(_text)
    work["notes_norm"] = work["notes"].map(lambda value: _text(value).lower())
    return work


def _refund_event_state(events: pd.DataFrame, order_id: str, sku: str) -> dict[str, str]:
    if events.empty:
        return {
            "statuses": "missing",
            "requested": "0",
            "applied": "0",
            "event_ids": "",
        }
    rows = events[(events["order_id_norm"] == order_id) & (events["sku_norm"] == sku)].copy()
    if rows.empty:
        return {
            "statuses": "missing",
            "requested": "0",
            "applied": "0",
            "event_ids": "",
        }
    requested = pd.to_numeric(rows["requested_qty"], errors="coerce").fillna(0.0).sum()
    applied = pd.to_numeric(rows["applied_qty"], errors="coerce").fillna(0.0).sum()
    return {
        "statuses": _join(rows["status"].tolist()) or "seen",
        "requested": _num_text(requested),
        "applied": _num_text(applied),
        "event_ids": _join(rows["refund_event_id"].tolist()),
    }


def _allocation_ids(allocations: pd.DataFrame, order_id: str, sku: str) -> list[str]:
    if allocations.empty:
        return []
    rows = allocations[(allocations["order_id_norm"] == order_id) & (allocations["sku_norm"] == sku)]
    return _unique(rows["token_id"].tolist())


def _ledger_token_state(ledger: pd.DataFrame, order_id: str, sku: str, token_ids: list[str]) -> dict[str, list[str]]:
    empty = {
        "ledger_seen": [],
        "ledger_allocated": [],
        "returned_pending": [],
        "returned_complete": [],
        "reusable": [],
        "original_return_conflict": [],
        "conflicting": [],
    }
    if ledger.empty:
        return empty
    rows = ledger[ledger["sku_norm"] == sku].copy()
    if token_ids:
        rows = rows[rows["token_id"].isin(set(token_ids))].copy()
    else:
        rows = rows[
            (rows["allocated_order_norm"] == order_id)
            | (rows["return_order_norm"] == order_id)
            | (rows["last_return_order_norm"] == order_id)
        ].copy()
    ledger_allocated = rows[
        (rows["allocated_order_norm"] == order_id)
        & (rows["status_norm"].isin(["allocated", "sold", ""]))
    ]["token_id"].tolist()
    returned_pending = rows[
        (rows["return_order_norm"] == order_id)
        & (rows["status_norm"] == "returned_pending")
    ]["token_id"].tolist()
    returned_complete = rows[
        (rows["last_return_order_norm"] == order_id)
        & (rows["status_norm"] == "returned_complete")
    ]["token_id"].tolist()
    reusable = rows[
        rows["notes_norm"].str.contains("return_sellable_dup", na=False)
        & (rows["last_return_order_norm"] == order_id)
    ]["token_id"].tolist()
    original_return_conflict = rows[
        (rows["last_return_order_norm"] == order_id)
        & rows["status_norm"].isin(["available", "allocated", "warehouse"])
        & (
            rows["notes_norm"].str.contains("return_closed", na=False)
            | rows["notes_norm"].str.contains("return_unsellable", na=False)
            | rows["notes_norm"].str.contains("return_researching", na=False)
            | rows["notes_norm"].str.contains("researching_negative", na=False)
        )
    ]["token_id"].tolist()
    known = set(ledger_allocated + returned_pending + returned_complete + reusable + original_return_conflict)
    conflicting = [token_id for token_id in rows["token_id"].tolist() if token_id and token_id not in known]
    return {
        "ledger_seen": _unique(rows["token_id"].tolist()),
        "ledger_allocated": _unique(ledger_allocated),
        "returned_pending": _unique(returned_pending),
        "returned_complete": _unique(returned_complete),
        "reusable": _unique(reusable),
        "original_return_conflict": _unique(original_return_conflict),
        "conflicting": _unique(conflicting),
    }


def _classify(
    *,
    source_lane: str,
    refund_state: dict[str, str],
    allocation_ids: list[str],
    ledger_state: dict[str, list[str]],
) -> tuple[str, str, str, str, str, str]:
    b008_applied = _num(refund_state["applied"])
    returned_pending = ledger_state["returned_pending"]
    reusable = ledger_state["reusable"]
    returned_complete = ledger_state["returned_complete"]
    ledger_allocated = ledger_state["ledger_allocated"]
    original_return_conflict = ledger_state["original_return_conflict"]
    conflicting = ledger_state["conflicting"]
    ledger_seen = ledger_state["ledger_seen"]

    if original_return_conflict:
        return (
            "token_state_conflict",
            "blocked_needs_protected_review",
            "The original returned token has a live stock status, so B008 should not re-mark it.",
            "token_ledger_live.csv",
            "Audit the original returned token lifecycle before any token correction or stock recovery use.",
            "Rerun B042, B041, B038, and B MOT after original returned-token state is repaired or exception-labelled.",
        )
    if returned_pending:
        return (
            "already_returned_pending",
            "ready_for_b009_after_retest",
            "B008 returned-pending proof is already visible; next repair is B009 order-aware return matching.",
            "stock_adjustment_token_events.csv;token_return_ledger.csv",
            "Rerun B041 and B038, then prepare B009 order-aware matching if the bridge still warns.",
            "Rerun B042, B041, B038, and B MOT; B008 preview clears when B009 can see returned_pending proof.",
        )
    if reusable or returned_complete:
        return (
            "already_closed_or_reused",
            "blocked_bridge_mapping_retest",
            "The token already looks closed or reused, so B008 should not re-mark it. The bridge needs mapping retest.",
            "b_refund_return_token_bridge.csv",
            "Repair bridge mapping or return COGS trace before proposing any B008 action.",
            "Rerun B042, B041, B038, and B MOT; row clears when bridge recognises the closed/reused token state.",
        )
    if conflicting:
        return (
            "token_state_conflict",
            "blocked_needs_protected_review",
            "The original token is visible but no longer in a simple allocated or returned-pending state.",
            "token_ledger_live.csv",
            "Stop before correction and investigate token state history for this order/SKU.",
            "Rerun B042 after token state history is manager-readable; do not hand-edit tokens.",
        )
    if not allocation_ids and not ledger_allocated:
        return (
            "original_allocation_gap",
            "blocked_missing_original_allocation",
            "The original sold token is not manager-readable, so B008 cannot safely mark a returned-pending token.",
            "token_allocations_live.csv",
            "Repair or prove the original allocation source before any refund-token reproof.",
            "Rerun B042 after allocation proof exists; do not create a substitute token.",
        )
    if allocation_ids and not ledger_seen:
        return (
            "token_ledger_gap",
            "blocked_missing_allocated_token_in_ledger",
            "The allocation names the original token, but that token is not visible in the current token ledger.",
            "token_ledger_live.csv;token_allocations_live.csv",
            "Repair or prove the token-ledger row before any B008 refund-token reproof.",
            "Rerun B042 after the allocated token is visible in the token ledger; do not create a substitute token.",
        )
    if b008_applied > 0 and ledger_allocated:
        return (
            "b008_event_ledger_state_drift",
            "ready_for_b008_state_reproof_preview",
            "B008 event proof says it applied, but the current ledger does not show returned_pending.",
            "token_ledger_live.csv;refund_token_events.csv",
            "Repair B008 idempotent state proof so an applied refund event and current token state agree.",
            "Rerun B008 only in an approved proof window, then B042, B041, B038, and B MOT.",
        )
    if source_lane == "b008_allocation_gap":
        return (
            "original_allocation_gap",
            "blocked_missing_original_allocation",
            "The B041 preview already found an original allocation gap.",
            "token_allocations_live.csv",
            "Repair or prove the original allocation source before any refund-token reproof.",
            "Rerun B042 after allocation proof exists; do not create a substitute token.",
        )
    return (
        "b008_refund_token_marking",
        "ready_for_b008_order_sku_reproof",
        "Preview marking the original allocated token as returned_pending through B008's normal order/SKU route.",
        "token_ledger_live.csv;refund_token_events.csv",
        "Repair B008 refund-token mapping for this order/SKU; do not hand-edit token rows.",
        "Rerun B008 only in an approved proof window, then B042, B041, B038, and B MOT.",
    )


def build_refund_token_reproof_preview(*, root: Path | str | None = None) -> dict[str, object]:
    root_path = Path(root or ".")
    source = _read_csv(root_path / RETURN_REPAIR_PREVIEW)
    refund_events = _prepare_refund_events(_read_csv(root_path / REFUND_TOKEN_EVENTS))
    allocations = _prepare_allocations(_read_csv(root_path / TOKEN_ALLOCATIONS))
    ledger = _prepare_ledger(_read_csv(root_path / TOKEN_LEDGER))

    rows: list[dict[str, str]] = []
    if not source.empty:
        for _, row in source.iterrows():
            source_lane = _text(row.get("repair_lane", ""))
            if source_lane not in TARGET_REPAIR_LANES:
                continue
            order_id = _text(row.get("order_id", ""))
            sku = _norm_sku(row.get("sku", ""))
            if not order_id or not sku:
                continue
            repair_tokens = _split_token_ids(row.get("allocated_original_token_ids", ""))
            allocation_token_ids = repair_tokens or _allocation_ids(allocations, order_id, sku)
            refund_state = _refund_event_state(refund_events, order_id, sku)
            ledger_state = _ledger_token_state(ledger, order_id, sku, allocation_token_ids)
            if allocation_token_ids and not ledger_state["ledger_seen"]:
                fallback_state = _ledger_token_state(ledger, order_id, sku, [])
                if fallback_state["ledger_allocated"]:
                    allocation_token_ids = fallback_state["ledger_allocated"]
                    ledger_state = fallback_state
            lane, readiness, action, touched, worker_task, retest = _classify(
                source_lane=source_lane,
                refund_state=refund_state,
                allocation_ids=allocation_token_ids,
                ledger_state=ledger_state,
            )
            rows.append(
                {
                    "order_id": order_id,
                    "sku": sku,
                    "source_repair_lane": source_lane,
                    "source_repair_readiness": _text(row.get("repair_readiness", "")),
                    "diagnosis": _text(row.get("diagnosis", "")),
                    "b008_event_statuses": refund_state["statuses"],
                    "b008_requested_qty": refund_state["requested"],
                    "b008_applied_qty": refund_state["applied"],
                    "b008_event_ids": refund_state["event_ids"],
                    "allocation_token_ids": _join(allocation_token_ids),
                    "ledger_allocated_token_ids": _join(ledger_state["ledger_allocated"]),
                    "returned_pending_token_ids": _join(ledger_state["returned_pending"]),
                    "returned_complete_token_ids": _join(ledger_state["returned_complete"]),
                    "reusable_return_token_ids": _join(ledger_state["reusable"]),
                    "conflicting_token_ids": _join(ledger_state["conflicting"]),
                    "reproof_lane": lane,
                    "reproof_readiness": readiness,
                    "preview_action": action,
                    "would_touch_live_outputs": touched,
                    "preview_live_write_allowed": "0",
                    "protected_before_apply": "1" if touched else "0",
                    "roi_or_restock_use_allowed": "0",
                    "sellerboard_final_truth_allowed": "0",
                    "bounded_worker_task": worker_task,
                    "retest_rule": retest,
                    "protected_stop_rule": (
                        "Stop before token correction, B run/restart, Sheet write, DB alignment, output deletion, "
                        "ROI/restocking use, price/queue change, or widening beyond B008 refund-token proof."
                    ),
                }
            )

    preview = pd.DataFrame(rows, columns=PREVIEW_COLUMNS).fillna("")
    unclassified = preview[
        (preview["reproof_lane"].astype(str).str.strip() == "")
        | (preview["reproof_readiness"].astype(str).str.strip() == "")
        | (preview["preview_action"].astype(str).str.strip() == "")
    ]
    summary_values = {
        "preview_rows": str(len(preview)),
        "unclassified_rows": str(len(unclassified)),
        "ready_b008_order_sku_reproof_rows": str(
            int((preview["reproof_lane"] == "b008_refund_token_marking").sum()) if not preview.empty else 0
        ),
        "ready_b008_state_reproof_rows": str(
            int((preview["reproof_lane"] == "b008_event_ledger_state_drift").sum()) if not preview.empty else 0
        ),
        "allocation_gap_rows": str(
            int((preview["reproof_lane"] == "original_allocation_gap").sum()) if not preview.empty else 0
        ),
        "token_state_conflict_rows": str(
            int((preview["reproof_lane"] == "token_state_conflict").sum()) if not preview.empty else 0
        ),
        "token_ledger_gap_rows": str(
            int((preview["reproof_lane"] == "token_ledger_gap").sum()) if not preview.empty else 0
        ),
        "already_pending_rows": str(
            int((preview["reproof_lane"] == "already_returned_pending").sum()) if not preview.empty else 0
        ),
        "already_closed_or_reused_rows": str(
            int((preview["reproof_lane"] == "already_closed_or_reused").sum()) if not preview.empty else 0
        ),
        "live_write_allowed_rows": str(
            int((preview["preview_live_write_allowed"] != "0").sum()) if not preview.empty else 0
        ),
        "roi_or_restock_allowed_rows": str(
            int((preview["roi_or_restock_use_allowed"] != "0").sum()) if not preview.empty else 0
        ),
        "sellerboard_final_truth_allowed_rows": str(
            int((preview["sellerboard_final_truth_allowed"] != "0").sum()) if not preview.empty else 0
        ),
    }
    summary = pd.DataFrame([{"metric": key, "value": value} for key, value in summary_values.items()], columns=SUMMARY_COLUMNS)
    return {
        "preview": preview,
        "summary": summary,
        "preview_path": root_path / OUT_PREVIEW,
        "summary_path": root_path / OUT_SUMMARY,
    }


def write_refund_token_reproof_preview_outputs(result: dict[str, object]) -> dict[str, Path]:
    preview_path = Path(result["preview_path"])
    summary_path = Path(result["summary_path"])
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    safe_to_csv(result["preview"], preview_path, index=False)
    safe_to_csv(result["summary"], summary_path, index=False)
    return {"preview": preview_path, "summary": summary_path}


def main() -> None:
    result = build_refund_token_reproof_preview()
    paths = write_refund_token_reproof_preview_outputs(result)
    preview = result["preview"]
    summary = result["summary"]
    values = {row["metric"]: row["value"] for _, row in summary.iterrows()} if not summary.empty else {}
    print(
        {
            "status": "success",
            "preview_rows": len(preview),
            "unclassified_rows": int(_num(values.get("unclassified_rows", "0"))),
            "ready_b008_order_sku_reproof_rows": int(_num(values.get("ready_b008_order_sku_reproof_rows", "0"))),
            "ready_b008_state_reproof_rows": int(_num(values.get("ready_b008_state_reproof_rows", "0"))),
            "preview": str(paths["preview"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
