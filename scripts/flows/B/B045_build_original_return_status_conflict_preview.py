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
TOKEN_LEDGER = OUT / "token_ledger_live.csv"
OUT_PREVIEW = OUT / "systems" / "B" / "refunds" / "b_original_return_status_conflict_preview.csv"
OUT_SUMMARY = OUT / "systems" / "B" / "refunds" / "b_original_return_status_conflict_preview_summary.csv"

TARGET_LANE = "protected_original_return_status_conflict"

PREVIEW_COLUMNS = [
    "order_id",
    "sku",
    "unsafe_original_token_id",
    "unsafe_original_status",
    "unsafe_original_notes",
    "unsafe_original_allocated_order_id",
    "unsafe_original_return_order_id",
    "unsafe_original_last_return_order_id",
    "reusable_return_token_ids",
    "reusable_return_token_statuses",
    "has_reusable_duplicate_token",
    "source_repair_lane",
    "source_repair_readiness",
    "diagnosis",
    "review_lane",
    "review_readiness",
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


def _split(value: object) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for part in _text(value).split("|"):
        item = part.strip()
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _join(values: list[str]) -> str:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _text(value)
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return "|".join(out)


def _prepare_ledger(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
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
    work["token_id_norm"] = work["token_id"].map(_text)
    work["sku_norm"] = work["seller_sku"].map(_norm_sku)
    return work


def _ledger_row_by_token(ledger: pd.DataFrame, token_id: str) -> dict[str, str]:
    if ledger.empty:
        return {}
    matches = ledger[ledger["token_id_norm"] == token_id]
    if matches.empty:
        return {}
    row = matches.iloc[0]
    return {column: _text(row.get(column, "")) for column in ledger.columns}


def _token_statuses(ledger: pd.DataFrame, token_ids: list[str]) -> str:
    statuses: list[str] = []
    for token_id in token_ids:
        row = _ledger_row_by_token(ledger, token_id)
        if row:
            statuses.append(f"{token_id}:{_text(row.get('status', ''))}")
        else:
            statuses.append(f"{token_id}:missing")
    return "|".join(statuses)


def _review_lane(status: str, allocated_order_id: str, has_duplicate: bool) -> str:
    status_norm = status.strip().lower()
    if status_norm == "allocated":
        return (
            "original_allocated_after_return_with_duplicate"
            if has_duplicate
            else "original_allocated_after_return_no_duplicate"
        )
    if status_norm in {"available", "warehouse"}:
        return (
            "original_live_after_return_with_duplicate"
            if has_duplicate
            else "original_live_after_return_no_duplicate"
        )
    if allocated_order_id:
        return (
            "original_has_allocation_after_return_with_duplicate"
            if has_duplicate
            else "original_has_allocation_after_return_no_duplicate"
        )
    return "original_return_status_conflict"


def _review_action(lane: str) -> str:
    if "with_duplicate" in lane:
        return "No-write preview only. Protected review should decide whether the original token must be closed while the returned-stock duplicate remains as the reusable proof."
    if "no_duplicate" in lane:
        return "No-write preview only. Protected review should decide whether the original token was incorrectly reused and whether returned-stock duplicate proof is missing."
    return "No-write preview only. Protected review must inspect the original returned-token lifecycle before any correction."


def build_original_return_status_conflict_preview(*, root: Path | str | None = None) -> dict[str, object]:
    root_path = Path(root or ".")
    source = _read_csv(root_path / RETURN_REPAIR_PREVIEW)
    ledger = _prepare_ledger(_read_csv(root_path / TOKEN_LEDGER))

    rows: list[dict[str, str]] = []
    if not source.empty:
        for _, source_row in source.iterrows():
            if _text(source_row.get("repair_lane", "")) != TARGET_LANE:
                continue
            order_id = _text(source_row.get("order_id", ""))
            sku = _norm_sku(source_row.get("sku", ""))
            unsafe_ids = _split(source_row.get("unsafe_original_token_ids", ""))
            reusable_ids = _split(source_row.get("reusable_return_token_ids", ""))
            has_duplicate = "1" if reusable_ids else "0"
            reusable_statuses = _token_statuses(ledger, reusable_ids)
            for token_id in unsafe_ids:
                token_row = _ledger_row_by_token(ledger, token_id)
                status = _text(token_row.get("status", "missing"))
                allocated_order_id = _text(token_row.get("allocated_order_id", ""))
                lane = _review_lane(status, allocated_order_id, bool(reusable_ids))
                rows.append(
                    {
                        "order_id": order_id,
                        "sku": sku,
                        "unsafe_original_token_id": token_id,
                        "unsafe_original_status": status,
                        "unsafe_original_notes": _text(token_row.get("notes", "")),
                        "unsafe_original_allocated_order_id": allocated_order_id,
                        "unsafe_original_return_order_id": _text(token_row.get("return_order_id", "")),
                        "unsafe_original_last_return_order_id": _text(token_row.get("last_return_order_id", "")),
                        "reusable_return_token_ids": _join(reusable_ids),
                        "reusable_return_token_statuses": reusable_statuses,
                        "has_reusable_duplicate_token": has_duplicate,
                        "source_repair_lane": TARGET_LANE,
                        "source_repair_readiness": _text(source_row.get("repair_readiness", "")),
                        "diagnosis": _text(source_row.get("diagnosis", "")),
                        "review_lane": lane,
                        "review_readiness": "blocked_needs_protected_review",
                        "preview_action": _review_action(lane),
                        "would_touch_live_outputs": "token_ledger_live.csv;token_return_ledger.csv",
                        "preview_live_write_allowed": "0",
                        "protected_before_apply": "1",
                        "roi_or_restock_use_allowed": "0",
                        "sellerboard_final_truth_allowed": "0",
                        "bounded_worker_task": (
                            "Prepare a protected B008/B009 lifecycle repair plan for this named original token. "
                            "Do not edit token state from this preview."
                        ),
                        "retest_rule": (
                            "Rerun B045, B041, B038, and B MOT; row clears only when the original token is no longer "
                            "a live-status conflict and returned-stock duplicate proof remains deduped."
                        ),
                        "protected_stop_rule": (
                            "Stop before token correction, B run/restart, Sheet write, DB alignment, output deletion, "
                            "ROI/restocking use, price/queue change, or widening beyond B return-token repair."
                        ),
                    }
                )

    preview = pd.DataFrame(rows, columns=PREVIEW_COLUMNS).fillna("")
    summary_values = {
        "preview_rows": str(len(preview)),
        "source_conflict_rows": str(
            int((source.get("repair_lane", pd.Series(dtype=str)).astype(str) == TARGET_LANE).sum()) if not source.empty else 0
        ),
        "unsafe_token_rows": str(len(preview)),
        "with_reusable_duplicate_rows": str(
            int((preview["has_reusable_duplicate_token"] == "1").sum()) if not preview.empty else 0
        ),
        "without_reusable_duplicate_rows": str(
            int((preview["has_reusable_duplicate_token"] != "1").sum()) if not preview.empty else 0
        ),
        "allocated_unsafe_original_rows": str(
            int((preview["unsafe_original_status"].astype(str).str.lower() == "allocated").sum()) if not preview.empty else 0
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


def write_original_return_status_conflict_preview_outputs(result: dict[str, object]) -> dict[str, Path]:
    preview_path = Path(result["preview_path"])
    summary_path = Path(result["summary_path"])
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    safe_to_csv(result["preview"], preview_path, index=False)
    safe_to_csv(result["summary"], summary_path, index=False)
    return {"preview": preview_path, "summary": summary_path}


def main() -> None:
    result = build_original_return_status_conflict_preview()
    paths = write_original_return_status_conflict_preview_outputs(result)
    preview = result["preview"]
    values = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()} if not result["summary"].empty else {}
    print(
        {
            "status": "success",
            "preview_rows": len(preview),
            "with_reusable_duplicate_rows": int(values.get("with_reusable_duplicate_rows", "0")),
            "without_reusable_duplicate_rows": int(values.get("without_reusable_duplicate_rows", "0")),
            "preview": str(paths["preview"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
