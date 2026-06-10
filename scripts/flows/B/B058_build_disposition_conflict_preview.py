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
TOKEN_RETURN_LEDGER = OUT / "token_return_ledger.csv"
OUT_PREVIEW = OUT / "systems" / "B" / "refunds" / "b_disposition_conflict_preview.csv"
OUT_SUMMARY = OUT / "systems" / "B" / "refunds" / "b_disposition_conflict_preview_summary.csv"

TARGET_LANE = "protected_disposition_conflict"

PREVIEW_COLUMNS = [
    "order_id",
    "sku",
    "amazon_return_disposition",
    "amazon_return_status",
    "amazon_return_date",
    "refund_posted_date",
    "proof_label",
    "diagnosis",
    "unsafe_original_token_ids",
    "unsafe_original_token_statuses",
    "unsafe_original_allocated_order_ids",
    "reusable_return_token_ids",
    "reusable_return_token_statuses",
    "reusable_return_token_allocated_order_ids",
    "return_cogs_token_ids",
    "return_cogs_rows",
    "conflict_lane",
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
    for column in ["token_id", "seller_sku", "status", "allocated_order_id", "return_order_id", "last_return_order_id", "notes"]:
        if column not in work.columns:
            work[column] = ""
    work["token_id_norm"] = work["token_id"].map(_text)
    work["sku_norm"] = work["seller_sku"].map(_norm_sku)
    return work


def _token_statuses(ledger: pd.DataFrame, token_ids: list[str]) -> str:
    statuses: list[str] = []
    if ledger.empty:
        return "|".join([f"{token_id}:missing" for token_id in token_ids])
    for token_id in token_ids:
        rows = ledger[ledger["token_id_norm"] == token_id]
        if rows.empty:
            statuses.append(f"{token_id}:missing")
        else:
            statuses.append(f"{token_id}:{_text(rows.iloc[0].get('status', ''))}")
    return "|".join(statuses)


def _token_allocated_orders(ledger: pd.DataFrame, token_ids: list[str]) -> str:
    orders: list[str] = []
    if ledger.empty:
        return ""
    for token_id in token_ids:
        rows = ledger[ledger["token_id_norm"] == token_id]
        if rows.empty:
            continue
        order_id = _text(rows.iloc[0].get("allocated_order_id", ""))
        if order_id:
            orders.append(f"{token_id}:{order_id}")
    return "|".join(orders)


def _return_cogs_rows(return_ledger: pd.DataFrame, order_id: str, sku: str, token_ids: list[str]) -> int:
    if return_ledger.empty:
        return 0
    work = return_ledger.copy()
    for column in ["order_id", "sku", "seller_sku", "token_id"]:
        if column not in work.columns:
            work[column] = ""
    work["order_id_norm"] = work["order_id"].map(_text)
    sku_source = work["sku"].where(work["sku"].astype(str).str.strip() != "", work["seller_sku"])
    work["sku_norm"] = sku_source.map(_norm_sku)
    work["token_id_norm"] = work["token_id"].map(_text)
    token_set = set(token_ids)
    rows = work[work["sku_norm"] == sku]
    order_rows = rows[rows["order_id_norm"] == order_id]
    if not order_rows.empty:
        rows = order_rows
    if token_set:
        rows = rows[rows["token_id_norm"].isin(token_set)]
    return int(len(rows))


def _conflict_lane(disposition: str, reusable_ids: list[str], cogs_rows: int) -> str:
    disposition_norm = disposition.upper()
    if disposition_norm in {"CUSTOMER_DAMAGED", "DEFECTIVE", "DAMAGED"}:
        if reusable_ids and cogs_rows:
            return "non_sellable_return_has_reusable_token_and_cogs"
        if reusable_ids:
            return "non_sellable_return_has_reusable_token"
    if reusable_ids:
        return "non_sellable_return_reuse_needs_review"
    return "non_sellable_return_no_reusable_token"


def build_disposition_conflict_preview(*, root: Path | str | None = None) -> dict[str, object]:
    root_path = Path(root or ".")
    source = _read_csv(root_path / RETURN_REPAIR_PREVIEW)
    ledger = _prepare_ledger(_read_csv(root_path / TOKEN_LEDGER))
    return_ledger = _read_csv(root_path / TOKEN_RETURN_LEDGER)

    rows: list[dict[str, str]] = []
    if not source.empty:
        for _, source_row in source.iterrows():
            if _text(source_row.get("repair_lane", "")) != TARGET_LANE:
                continue
            order_id = _text(source_row.get("order_id", ""))
            sku = _norm_sku(source_row.get("sku", ""))
            disposition = _text(source_row.get("amazon_return_disposition", ""))
            reusable_ids = _split(source_row.get("reusable_return_token_ids", ""))
            unsafe_ids = _split(source_row.get("unsafe_original_token_ids", ""))
            cogs_ids = _split(source_row.get("return_cogs_token_ids", ""))
            cogs_rows = _return_cogs_rows(return_ledger, order_id, sku, cogs_ids or reusable_ids)
            lane = _conflict_lane(disposition, reusable_ids, cogs_rows)
            rows.append(
                {
                    "order_id": order_id,
                    "sku": sku,
                    "amazon_return_disposition": disposition,
                    "amazon_return_status": _text(source_row.get("amazon_return_status", "")),
                    "amazon_return_date": _text(source_row.get("amazon_return_date", "")),
                    "refund_posted_date": _text(source_row.get("refund_posted_date", "")),
                    "proof_label": _text(source_row.get("proof_label", "")),
                    "diagnosis": _text(source_row.get("diagnosis", "")),
                    "unsafe_original_token_ids": _join(unsafe_ids),
                    "unsafe_original_token_statuses": _token_statuses(ledger, unsafe_ids),
                    "unsafe_original_allocated_order_ids": _token_allocated_orders(ledger, unsafe_ids),
                    "reusable_return_token_ids": _join(reusable_ids),
                    "reusable_return_token_statuses": _token_statuses(ledger, reusable_ids),
                    "reusable_return_token_allocated_order_ids": _token_allocated_orders(ledger, reusable_ids),
                    "return_cogs_token_ids": _join(cogs_ids),
                    "return_cogs_rows": str(cogs_rows),
                    "conflict_lane": lane,
                    "review_readiness": "blocked_needs_protected_review",
                    "preview_action": (
                        "No-write preview only. Amazon says this return is not sellable, so reusable stock and recovered COGS "
                        "must stay blocked unless a protected correction or exception is approved."
                    ),
                    "would_touch_live_outputs": "token_ledger_live.csv;token_return_ledger.csv;stock_adjustment_token_events.csv",
                    "preview_live_write_allowed": "0",
                    "protected_before_apply": "1",
                    "roi_or_restock_use_allowed": "0",
                    "sellerboard_final_truth_allowed": "0",
                    "bounded_worker_task": (
                        "Prepare a protected disposition-conflict correction or exception packet for this order/SKU only. "
                        "Do not alter token stock from this preview."
                    ),
                    "retest_rule": (
                        "After any protected correction or exception, rerun B058, B041, B038, B051, and B MOT. "
                        "The row clears only when non-sellable returns no longer show unapproved reusable-stock proof."
                    ),
                    "protected_stop_rule": (
                        "Stop before token correction, B run/restart, Sheet write, DB alignment, output deletion, "
                        "ROI/restocking use, price/queue change, or widening beyond B return-token repair."
                    ),
                }
            )

    preview = pd.DataFrame(rows, columns=PREVIEW_COLUMNS).fillna("")
    live_write_rows = int((preview["preview_live_write_allowed"] != "0").sum()) if not preview.empty else 0
    roi_rows = int((preview["roi_or_restock_use_allowed"] != "0").sum()) if not preview.empty else 0
    sellerboard_rows = int((preview["sellerboard_final_truth_allowed"] != "0").sum()) if not preview.empty else 0
    allocated_reusable_rows = (
        int((preview["reusable_return_token_allocated_order_ids"].astype(str).str.strip() != "").sum()) if not preview.empty else 0
    )
    summary_values = {
        "status": "fail" if live_write_rows or roi_rows or sellerboard_rows else "ok",
        "preview_rows": str(len(preview)),
        "source_conflict_rows": str(
            int((source.get("repair_lane", pd.Series(dtype=str)).astype(str) == TARGET_LANE).sum()) if not source.empty else 0
        ),
        "with_reusable_token_rows": str(
            int((preview["reusable_return_token_ids"].astype(str).str.strip() != "").sum()) if not preview.empty else 0
        ),
        "with_return_cogs_rows": str(int((preview["return_cogs_rows"].astype(str).str.strip() != "0").sum()) if not preview.empty else 0),
        "allocated_reusable_token_rows": str(allocated_reusable_rows),
        "customer_damaged_rows": str(
            int((preview["amazon_return_disposition"].astype(str).str.upper() == "CUSTOMER_DAMAGED").sum()) if not preview.empty else 0
        ),
        "defective_rows": str(
            int((preview["amazon_return_disposition"].astype(str).str.upper() == "DEFECTIVE").sum()) if not preview.empty else 0
        ),
        "unclassified_rows": str(
            int((preview["conflict_lane"].astype(str).str.strip() == "").sum()) if not preview.empty else 0
        ),
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


def write_disposition_conflict_preview_outputs(result: dict[str, object]) -> dict[str, Path]:
    preview_path = Path(result["preview_path"])
    summary_path = Path(result["summary_path"])
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    safe_to_csv(result["preview"], preview_path, index=False)
    safe_to_csv(result["summary"], summary_path, index=False)
    return {"preview": preview_path, "summary": summary_path}


def main() -> None:
    result = build_disposition_conflict_preview()
    paths = write_disposition_conflict_preview_outputs(result)
    preview = result["preview"]
    values = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()} if not result["summary"].empty else {}
    print(
        {
            "status": values.get("status", ""),
            "preview_rows": len(preview),
            "with_reusable_token_rows": values.get("with_reusable_token_rows", "0"),
            "with_return_cogs_rows": values.get("with_return_cogs_rows", "0"),
            "preview": str(paths["preview"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
