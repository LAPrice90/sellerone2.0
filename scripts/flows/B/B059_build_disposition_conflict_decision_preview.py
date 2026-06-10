from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.safe_file_writes import safe_to_csv


OUT = Path("out")
DISPOSITION_PREVIEW = OUT / "systems" / "B" / "refunds" / "b_disposition_conflict_preview.csv"
OUT_PREVIEW = OUT / "systems" / "B" / "refunds" / "b_disposition_conflict_decision_preview.csv"
OUT_SUMMARY = OUT / "systems" / "B" / "refunds" / "b_disposition_conflict_decision_preview_summary.csv"

PREVIEW_COLUMNS = [
    "order_id",
    "sku",
    "amazon_return_disposition",
    "proof_label",
    "reusable_return_token_ids",
    "reusable_return_token_allocated_order_ids",
    "downstream_allocated_order_ids",
    "return_cogs_rows",
    "decision_lane",
    "recommended_manager_position",
    "correction_option",
    "exception_option",
    "impact_summary",
    "protected_decision_required",
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


def _unique(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _text(value)
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _allocated_order_ids(value: object) -> list[str]:
    orders: list[str] = []
    for part in _text(value).split("|"):
        if ":" not in part:
            continue
        order_id = part.rsplit(":", 1)[-1].strip()
        if order_id:
            orders.append(order_id)
    return _unique(orders)


def _int_text(value: object) -> int:
    raw = _text(value)
    if not raw:
        return 0
    try:
        return int(float(raw))
    except Exception:
        return 0


def _decision_lane(*, downstream_orders: list[str], return_cogs_rows: int) -> str:
    if downstream_orders and return_cogs_rows > 0:
        return "downstream_allocated_non_sellable_reuse_with_cogs"
    if downstream_orders:
        return "downstream_allocated_non_sellable_reuse"
    if return_cogs_rows > 0:
        return "unallocated_non_sellable_reuse_with_cogs"
    return "unallocated_non_sellable_reuse"


def _impact_summary(downstream_orders: list[str], return_cogs_rows: int) -> str:
    if downstream_orders:
        return (
            f"Reusable returned stock is already allocated to {len(downstream_orders)} later order(s). "
            f"Any correction must review those downstream sale tokens and {return_cogs_rows} return COGS row(s)."
        )
    return (
        "Reusable returned stock is not allocated to a later order in this preview. "
        f"Any correction must still review {return_cogs_rows} return COGS row(s)."
    )


def build_disposition_conflict_decision_preview(*, root: Path | str | None = None) -> dict[str, object]:
    root_path = Path(root or ".")
    source = _read_csv(root_path / DISPOSITION_PREVIEW)
    rows: list[dict[str, str]] = []

    if not source.empty:
        for _, source_row in source.iterrows():
            downstream_orders = _allocated_order_ids(source_row.get("reusable_return_token_allocated_order_ids", ""))
            return_cogs_rows = _int_text(source_row.get("return_cogs_rows", ""))
            lane = _decision_lane(downstream_orders=downstream_orders, return_cogs_rows=return_cogs_rows)
            rows.append(
                {
                    "order_id": _text(source_row.get("order_id", "")),
                    "sku": _text(source_row.get("sku", "")),
                    "amazon_return_disposition": _text(source_row.get("amazon_return_disposition", "")),
                    "proof_label": _text(source_row.get("proof_label", "")),
                    "reusable_return_token_ids": _text(source_row.get("reusable_return_token_ids", "")),
                    "reusable_return_token_allocated_order_ids": _text(
                        source_row.get("reusable_return_token_allocated_order_ids", "")
                    ),
                    "downstream_allocated_order_ids": "|".join(downstream_orders),
                    "return_cogs_rows": str(return_cogs_rows),
                    "decision_lane": lane,
                    "recommended_manager_position": (
                        "Keep recovered stock and return COGS blocked from clean ROI/restocking truth until a protected "
                        "correction or named business exception is approved."
                    ),
                    "correction_option": (
                        "Protected correction would remove or relabel unapproved reusable-stock and COGS recovery for the "
                        "non-sellable return, then review any downstream allocated sale token before live data changes."
                    ),
                    "exception_option": (
                        "Protected exception would keep the reusable-stock recovery despite Amazon's non-sellable disposition, "
                        "but the row must remain explicitly exception-labelled for ROI/restocking confidence."
                    ),
                    "impact_summary": _impact_summary(downstream_orders, return_cogs_rows),
                    "protected_decision_required": "1",
                    "preview_live_write_allowed": "0",
                    "protected_before_apply": "1",
                    "roi_or_restock_use_allowed": "0",
                    "sellerboard_final_truth_allowed": "0",
                    "bounded_worker_task": (
                        "Prepare a Luke decision packet for this named order/SKU. Do not correct token, COGS, order, ROI, "
                        "or restocking state from this preview."
                    ),
                    "retest_rule": (
                        "After a protected correction or exception is approved and applied, rerun B059, B058, B041, B038, "
                        "B051, and B MOT. The row clears only when the downstream impact is handled or exception-labelled."
                    ),
                    "protected_stop_rule": (
                        "Stop before token correction, downstream order correction, COGS correction, B run/restart, Sheet write, "
                        "DB alignment, output deletion, ROI/restocking use, price/queue change, or widening beyond B return-token repair."
                    ),
                }
            )

    preview = pd.DataFrame(rows, columns=PREVIEW_COLUMNS).fillna("")
    live_write_rows = int((preview["preview_live_write_allowed"] != "0").sum()) if not preview.empty else 0
    roi_rows = int((preview["roi_or_restock_use_allowed"] != "0").sum()) if not preview.empty else 0
    sellerboard_rows = int((preview["sellerboard_final_truth_allowed"] != "0").sum()) if not preview.empty else 0
    downstream_rows = int((preview["downstream_allocated_order_ids"].astype(str).str.strip() != "").sum()) if not preview.empty else 0
    decision_rows = int((preview["protected_decision_required"].astype(str).str.strip() == "1").sum()) if not preview.empty else 0
    summary_values = {
        "status": "fail" if live_write_rows or roi_rows or sellerboard_rows else "ok",
        "preview_rows": str(len(preview)),
        "source_rows": str(len(source)),
        "protected_decision_rows": str(decision_rows),
        "downstream_allocated_rows": str(downstream_rows),
        "with_return_cogs_rows": str(int((preview["return_cogs_rows"].astype(str).str.strip() != "0").sum()) if not preview.empty else 0),
        "unclassified_rows": str(int((preview["decision_lane"].astype(str).str.strip() == "").sum()) if not preview.empty else 0),
        "live_write_allowed_rows": str(live_write_rows),
        "roi_or_restock_allowed_rows": str(roi_rows),
        "sellerboard_final_truth_allowed_rows": str(sellerboard_rows),
    }
    summary = pd.DataFrame([{"metric": key, "value": value} for key, value in summary_values.items()], columns=SUMMARY_COLUMNS)
    return {
        "preview": preview,
        "summary": summary,
        "preview_path": root_path / OUT_PREVIEW,
        "summary_path": root_path / OUT_SUMMARY,
    }


def write_disposition_conflict_decision_preview_outputs(result: dict[str, object]) -> dict[str, Path]:
    preview_path = Path(result["preview_path"])
    summary_path = Path(result["summary_path"])
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    safe_to_csv(result["preview"], preview_path, index=False)
    safe_to_csv(result["summary"], summary_path, index=False)
    return {"preview": preview_path, "summary": summary_path}


def main() -> None:
    result = build_disposition_conflict_decision_preview()
    paths = write_disposition_conflict_decision_preview_outputs(result)
    preview = result["preview"]
    values = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()} if not result["summary"].empty else {}
    print(
        {
            "status": values.get("status", ""),
            "preview_rows": len(preview),
            "protected_decision_rows": values.get("protected_decision_rows", "0"),
            "downstream_allocated_rows": values.get("downstream_allocated_rows", "0"),
            "preview": str(paths["preview"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
