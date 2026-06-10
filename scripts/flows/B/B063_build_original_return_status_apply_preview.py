from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.safe_file_writes import safe_to_csv


OUT = Path("out")
SOURCE_PREVIEW = OUT / "systems" / "B" / "refunds" / "b_original_return_status_conflict_preview.csv"
TOKEN_LEDGER = OUT / "token_ledger_live.csv"
OUT_PREVIEW = OUT / "systems" / "B" / "refunds" / "b_original_return_status_apply_preview.csv"
OUT_SUMMARY = OUT / "systems" / "B" / "refunds" / "b_original_return_status_apply_preview_summary.csv"

LIVE_STATUSES = {"allocated", "available", "warehouse"}

PREVIEW_COLUMNS = [
    "order_id",
    "sku",
    "unsafe_original_token_id",
    "current_status",
    "target_status",
    "target_status_source",
    "current_notes",
    "allocated_order_id",
    "return_order_id",
    "last_return_order_id",
    "has_reusable_duplicate_token",
    "reusable_return_token_ids",
    "source_review_lane",
    "source_review_readiness",
    "apply_preview_lane",
    "apply_preview_readiness",
    "block_reason",
    "maintenance_required_before_apply",
    "requires_luke_live_apply",
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
    return pd.read_csv(path, dtype=str, keep_default_na=False).fillna("")


def _text(value: object) -> str:
    return str(value or "").strip()


def _norm_sku(value: object) -> str:
    return _text(value).upper()


def _target_status_from_notes(notes: object) -> tuple[str, str]:
    text = _text(notes).lower()
    if "return_closed" in text:
        return "returned_complete", "return_closed"
    if "return_unsellable" in text:
        return "unsellable", "return_unsellable"
    if "return_researching" in text:
        return "research_pending", "return_researching"
    if "researching_negative" in text:
        return "research_pending", "researching_negative"
    return "", ""


def _ledger_rows(ledger: pd.DataFrame, token_id: str) -> pd.DataFrame:
    if ledger.empty:
        return pd.DataFrame()
    work = ledger.copy()
    if "token_id" not in work.columns:
        work["token_id"] = ""
    return work[work["token_id"].map(_text) == token_id].copy()


def _prepare_ledger(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    for column in [
        "token_id",
        "seller_sku",
        "status",
        "notes",
        "allocated_order_id",
        "return_order_id",
        "last_return_order_id",
    ]:
        if column not in work.columns:
            work[column] = ""
    return work


def _classify_row(source_row: pd.Series, ledger: pd.DataFrame) -> dict[str, str]:
    order_id = _text(source_row.get("order_id", ""))
    sku = _norm_sku(source_row.get("sku", ""))
    token_id = _text(source_row.get("unsafe_original_token_id", ""))
    source_live = _text(source_row.get("preview_live_write_allowed", "0"))
    source_roi = _text(source_row.get("roi_or_restock_use_allowed", "0"))
    source_sellerboard = _text(source_row.get("sellerboard_final_truth_allowed", "0"))
    source_protected = _text(source_row.get("protected_before_apply", ""))
    matches = _ledger_rows(ledger, token_id)

    current_status = ""
    target_status = ""
    target_source = ""
    notes = ""
    allocated_order_id = ""
    return_order_id = ""
    last_return_order_id = ""
    block_reason = ""
    lane = "original_return_status_apply_preview_ready"
    readiness = "ready_for_protected_b046_apply_window"

    if not order_id or not sku or not token_id:
        block_reason = "missing_order_sku_or_token"
    elif source_live not in {"", "0"} or source_roi not in {"", "0"} or source_sellerboard not in {"", "0"}:
        block_reason = "source_preview_allows_unsafe_use"
    elif source_protected != "1":
        block_reason = "source_preview_missing_protected_stop"
    elif ledger.empty:
        block_reason = "token_ledger_missing"
    elif len(matches) != 1:
        block_reason = "token_missing_or_duplicate"
    else:
        ledger_row = matches.iloc[0]
        current_status = _text(ledger_row.get("status", ""))
        notes = _text(ledger_row.get("notes", ""))
        allocated_order_id = _text(ledger_row.get("allocated_order_id", ""))
        return_order_id = _text(ledger_row.get("return_order_id", ""))
        last_return_order_id = _text(ledger_row.get("last_return_order_id", ""))
        token_sku = _norm_sku(ledger_row.get("seller_sku", ""))
        target_status, target_source = _target_status_from_notes(notes)
        token_return_order = return_order_id or last_return_order_id
        if token_sku != sku:
            block_reason = "token_sku_mismatch"
        elif current_status.lower() not in LIVE_STATUSES:
            block_reason = "token_not_in_live_status"
        elif token_return_order != order_id:
            block_reason = "return_order_mismatch"
        elif not target_status:
            block_reason = "missing_return_lifecycle_marker"

    if block_reason:
        lane = f"original_return_status_apply_blocked_{block_reason}"
        readiness = "blocked_needs_source_repair_or_exception"

    return {
        "order_id": order_id,
        "sku": sku,
        "unsafe_original_token_id": token_id,
        "current_status": current_status,
        "target_status": target_status,
        "target_status_source": target_source,
        "current_notes": notes,
        "allocated_order_id": allocated_order_id,
        "return_order_id": return_order_id,
        "last_return_order_id": last_return_order_id,
        "has_reusable_duplicate_token": _text(source_row.get("has_reusable_duplicate_token", "")),
        "reusable_return_token_ids": _text(source_row.get("reusable_return_token_ids", "")),
        "source_review_lane": _text(source_row.get("review_lane", "")),
        "source_review_readiness": _text(source_row.get("review_readiness", "")),
        "apply_preview_lane": lane,
        "apply_preview_readiness": readiness,
        "block_reason": block_reason,
        "maintenance_required_before_apply": "1",
        "requires_luke_live_apply": "1",
        "would_touch_live_outputs": "token_ledger_live.csv",
        "preview_live_write_allowed": "0",
        "protected_before_apply": "1",
        "roi_or_restock_use_allowed": "0",
        "sellerboard_final_truth_allowed": "0",
        "bounded_worker_task": (
            "If Luke approves a protected B046 window, update only this original returned-token status "
            "through the guarded lifecycle repair path."
        ),
        "retest_rule": (
            "After any protected apply, rerun B045, B063, B041, B038, B051, and B MOT; the row clears only "
            "when the original returned token no longer has a live stock status."
        ),
        "protected_stop_rule": (
            "Stop before token correction, B run/restart, Sheet write, DB alignment, output deletion, "
            "ROI/restocking use, price/queue change, or widening beyond B original returned-token repair."
        ),
    }


def build_original_return_status_apply_preview(*, root: Path | str | None = None) -> dict[str, object]:
    root_path = Path(root or ".")
    source = _read_csv(root_path / SOURCE_PREVIEW)
    ledger = _prepare_ledger(_read_csv(root_path / TOKEN_LEDGER))

    rows: list[dict[str, str]] = []
    if not source.empty:
        for _, source_row in source.iterrows():
            rows.append(_classify_row(source_row, ledger))

    preview = pd.DataFrame(rows, columns=PREVIEW_COLUMNS).fillna("")
    ready_rows = preview[preview["apply_preview_lane"] == "original_return_status_apply_preview_ready"] if not preview.empty else preview
    blocked_rows = preview[preview["apply_preview_lane"] != "original_return_status_apply_preview_ready"] if not preview.empty else preview
    unclassified_rows = preview[
        (preview["apply_preview_lane"].astype(str).str.strip() == "")
        | (preview["apply_preview_readiness"].astype(str).str.strip() == "")
    ] if not preview.empty else preview
    summary_values = {
        "status": "ok" if len(unclassified_rows) == 0 else "fail",
        "preview_rows": str(len(preview)),
        "source_conflict_rows": str(len(source)),
        "ready_apply_rows": str(len(ready_rows)),
        "blocked_rows": str(len(blocked_rows)),
        "with_reusable_duplicate_rows": str(int((preview["has_reusable_duplicate_token"] == "1").sum()) if not preview.empty else 0),
        "without_reusable_duplicate_rows": str(int((preview["has_reusable_duplicate_token"] != "1").sum()) if not preview.empty else 0),
        "target_returned_complete_rows": str(int((preview["target_status"] == "returned_complete").sum()) if not preview.empty else 0),
        "target_unsellable_rows": str(int((preview["target_status"] == "unsellable").sum()) if not preview.empty else 0),
        "target_research_pending_rows": str(int((preview["target_status"] == "research_pending").sum()) if not preview.empty else 0),
        "maintenance_required_rows": str(int((preview["maintenance_required_before_apply"] == "1").sum()) if not preview.empty else 0),
        "requires_luke_live_apply_rows": str(int((preview["requires_luke_live_apply"] == "1").sum()) if not preview.empty else 0),
        "live_write_allowed_rows": str(int((preview["preview_live_write_allowed"] != "0").sum()) if not preview.empty else 0),
        "roi_or_restock_allowed_rows": str(int((preview["roi_or_restock_use_allowed"] != "0").sum()) if not preview.empty else 0),
        "sellerboard_final_truth_allowed_rows": str(int((preview["sellerboard_final_truth_allowed"] != "0").sum()) if not preview.empty else 0),
        "unclassified_rows": str(len(unclassified_rows)),
    }
    summary = pd.DataFrame([{"metric": key, "value": value} for key, value in summary_values.items()], columns=SUMMARY_COLUMNS)
    return {
        "preview": preview,
        "summary": summary,
        "preview_path": root_path / OUT_PREVIEW,
        "summary_path": root_path / OUT_SUMMARY,
    }


def write_original_return_status_apply_preview_outputs(result: dict[str, object]) -> dict[str, Path]:
    preview_path = Path(result["preview_path"])
    summary_path = Path(result["summary_path"])
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    safe_to_csv(result["preview"], preview_path, index=False)
    safe_to_csv(result["summary"], summary_path, index=False)
    return {"preview": preview_path, "summary": summary_path}


def main() -> None:
    result = build_original_return_status_apply_preview()
    paths = write_original_return_status_apply_preview_outputs(result)
    values = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()} if not result["summary"].empty else {}
    print(
        {
            "status": values.get("status", ""),
            "preview_rows": values.get("preview_rows", "0"),
            "ready_apply_rows": values.get("ready_apply_rows", "0"),
            "blocked_rows": values.get("blocked_rows", "0"),
            "preview": str(paths["preview"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
