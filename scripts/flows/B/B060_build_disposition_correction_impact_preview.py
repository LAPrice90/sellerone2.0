from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.safe_file_writes import safe_to_csv


OUT = Path("out")
DECISION_PREVIEW = OUT / "systems" / "B" / "refunds" / "b_disposition_conflict_decision_preview.csv"
TOKEN_LEDGER = OUT / "token_ledger_live.csv"
ORDERS_ALL = OUT / "orders_all.csv"
ORDER_ITEMS_ALL = OUT / "order_items_all.csv"
OUT_PREVIEW = OUT / "systems" / "B" / "refunds" / "b_disposition_correction_impact_preview.csv"
OUT_SUMMARY = OUT / "systems" / "B" / "refunds" / "b_disposition_correction_impact_preview_summary.csv"

PREVIEW_COLUMNS = [
    "return_order_id",
    "sku",
    "amazon_return_disposition",
    "reusable_return_token_ids",
    "reusable_token_statuses",
    "downstream_allocated_order_ids",
    "downstream_order_statuses",
    "downstream_order_header_seen_rows",
    "downstream_order_item_match_rows",
    "return_cogs_rows",
    "correction_impact_lane",
    "correction_preview_action",
    "correction_blocker",
    "future_apply_scope",
    "protected_decision_required",
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


def _unique(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _text(value)
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _split(value: object) -> list[str]:
    return _unique(_text(value).split("|"))


def _downstream_orders(value: object) -> list[str]:
    orders: list[str] = []
    for part in _split(value):
        if ":" in part:
            orders.append(part.rsplit(":", 1)[-1])
        else:
            orders.append(part)
    return _unique(orders)


def _prepare_ledger(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["token_id", "seller_sku", "status", "allocated_order_id"]:
        if column not in work.columns:
            work[column] = ""
    work["token_id_norm"] = work["token_id"].map(_text)
    work["sku_norm"] = work["seller_sku"].map(_norm_sku)
    return work


def _token_statuses(ledger: pd.DataFrame, token_ids: list[str]) -> str:
    if ledger.empty:
        return "|".join([f"{token_id}:missing" for token_id in token_ids])
    statuses: list[str] = []
    for token_id in token_ids:
        rows = ledger[ledger["token_id_norm"] == token_id]
        if rows.empty:
            statuses.append(f"{token_id}:missing")
        else:
            statuses.append(f"{token_id}:{_text(rows.iloc[0].get('status', ''))}")
    return "|".join(statuses)


def _prepare_orders(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["amazon_order_id", "order_status"]:
        if column not in work.columns:
            work[column] = ""
    work["order_id_norm"] = work["amazon_order_id"].map(_text)
    return work


def _prepare_items(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["amazon_order_id", "seller_sku", "AmazonOrderId", "SellerSKU"]:
        if column not in work.columns:
            work[column] = ""
    order_source = work["amazon_order_id"].where(work["amazon_order_id"].astype(str).str.strip() != "", work["AmazonOrderId"])
    sku_source = work["seller_sku"].where(work["seller_sku"].astype(str).str.strip() != "", work["SellerSKU"])
    work["order_id_norm"] = order_source.map(_text)
    work["sku_norm"] = sku_source.map(_norm_sku)
    return work


def _order_statuses(orders: pd.DataFrame, order_ids: list[str]) -> str:
    statuses: list[str] = []
    if orders.empty:
        return "|".join([f"{order_id}:missing" for order_id in order_ids])
    for order_id in order_ids:
        rows = orders[orders["order_id_norm"] == order_id]
        if rows.empty:
            statuses.append(f"{order_id}:missing")
        else:
            statuses.append(f"{order_id}:{_text(rows.iloc[0].get('order_status', '')) or 'seen'}")
    return "|".join(statuses)


def _order_header_seen_rows(orders: pd.DataFrame, order_ids: list[str]) -> int:
    if orders.empty:
        return 0
    rows = orders[orders["order_id_norm"].isin(order_ids)]
    return int(len(rows))


def _item_match_rows(items: pd.DataFrame, order_ids: list[str], sku: str) -> int:
    if items.empty:
        return 0
    rows = items[(items["order_id_norm"].isin(order_ids)) & (items["sku_norm"] == sku)]
    return int(len(rows))


def _int_value(value: object) -> int:
    raw = _text(value)
    if not raw:
        return 0
    try:
        return int(float(raw))
    except Exception:
        return 0


def _impact_lane(order_ids: list[str], item_rows: int, cogs_rows: int) -> str:
    if order_ids and item_rows and cogs_rows:
        return "downstream_order_and_cogs_review_required"
    if order_ids and cogs_rows:
        return "downstream_order_missing_item_match_cogs_review_required"
    if order_ids:
        return "downstream_order_review_required"
    if cogs_rows:
        return "return_cogs_review_required"
    return "correction_review_required"


def build_disposition_correction_impact_preview(*, root: Path | str | None = None) -> dict[str, object]:
    root_path = Path(root or ".")
    decision = _read_csv(root_path / DECISION_PREVIEW)
    ledger = _prepare_ledger(_read_csv(root_path / TOKEN_LEDGER))
    orders = _prepare_orders(_read_csv(root_path / ORDERS_ALL))
    items = _prepare_items(_read_csv(root_path / ORDER_ITEMS_ALL))

    rows: list[dict[str, str]] = []
    if not decision.empty:
        for _, decision_row in decision.iterrows():
            if _text(decision_row.get("protected_decision_required", "")) != "1":
                continue
            order_id = _text(decision_row.get("order_id", ""))
            sku = _norm_sku(decision_row.get("sku", ""))
            token_ids = _split(decision_row.get("reusable_return_token_ids", ""))
            downstream_orders = _downstream_orders(decision_row.get("reusable_return_token_allocated_order_ids", ""))
            cogs_rows = _text(decision_row.get("return_cogs_rows", "")) or "0"
            cogs_count = _int_value(cogs_rows)
            header_rows = _order_header_seen_rows(orders, downstream_orders)
            item_rows = _item_match_rows(items, downstream_orders, sku)
            lane = _impact_lane(downstream_orders, item_rows, cogs_count)
            rows.append(
                {
                    "return_order_id": order_id,
                    "sku": sku,
                    "amazon_return_disposition": _text(decision_row.get("amazon_return_disposition", "")),
                    "reusable_return_token_ids": "|".join(token_ids),
                    "reusable_token_statuses": _token_statuses(ledger, token_ids),
                    "downstream_allocated_order_ids": "|".join(downstream_orders),
                    "downstream_order_statuses": _order_statuses(orders, downstream_orders),
                    "downstream_order_header_seen_rows": str(header_rows),
                    "downstream_order_item_match_rows": str(item_rows),
                    "return_cogs_rows": str(cogs_count),
                    "correction_impact_lane": lane,
                    "correction_preview_action": (
                        "No-write correction review only. A future protected correction must handle the reused token, "
                        "return COGS, and downstream order impact together."
                    ),
                    "correction_blocker": (
                        "downstream_order_impact_protected"
                        if downstream_orders
                        else "return_stock_cogs_impact_protected"
                    ),
                    "future_apply_scope": (
                        "protected preview first; then Luke-approved live correction only; update all affected token, "
                        "return COGS, downstream allocation, ROI proof-label, and restock-confidence evidence together"
                    ),
                    "protected_decision_required": "1",
                    "would_touch_live_outputs": (
                        "token_ledger_live.csv;token_return_ledger.csv;stock_adjustment_token_events.csv;"
                        "downstream_order_token_allocation;ROI/restocking proof labels"
                    ),
                    "preview_live_write_allowed": "0",
                    "protected_before_apply": "1",
                    "roi_or_restock_use_allowed": "0",
                    "sellerboard_final_truth_allowed": "0",
                    "bounded_worker_task": (
                        "If Luke approves correction review, build a protected apply preview for these exact rows. "
                        "Do not write token, COGS, downstream order, ROI, or restocking state from B060."
                    ),
                    "retest_rule": (
                        "After any future protected correction or exception, rerun B060, B059, B058, B041, B038, B051, and B MOT."
                    ),
                    "protected_stop_rule": (
                        "Stop before live token correction, downstream order correction, COGS correction, B run/restart, Sheet write, "
                        "DB alignment, output deletion, ROI/restocking use, price/queue change, or widening beyond B return-token repair."
                    ),
                }
            )

    preview = pd.DataFrame(rows, columns=PREVIEW_COLUMNS).fillna("")
    live_write_rows = int((preview["preview_live_write_allowed"] != "0").sum()) if not preview.empty else 0
    roi_rows = int((preview["roi_or_restock_use_allowed"] != "0").sum()) if not preview.empty else 0
    sellerboard_rows = int((preview["sellerboard_final_truth_allowed"] != "0").sum()) if not preview.empty else 0
    downstream_rows = int((preview["downstream_allocated_order_ids"].astype(str).str.strip() != "").sum()) if not preview.empty else 0
    item_match_rows = int(preview["downstream_order_item_match_rows"].map(_int_value).sum()) if not preview.empty else 0
    header_match_rows = int(preview["downstream_order_header_seen_rows"].map(_int_value).sum()) if not preview.empty else 0
    cogs_rows = int((preview["return_cogs_rows"].map(_int_value) > 0).sum()) if not preview.empty else 0
    protected_decision_rows = (
        int((preview["protected_decision_required"].astype(str).str.strip() == "1").sum()) if not preview.empty else 0
    )
    summary_values = {
        "status": "fail" if live_write_rows or roi_rows or sellerboard_rows else "ok",
        "preview_rows": str(len(preview)),
        "source_decision_rows": str(len(decision)),
        "protected_decision_rows": str(protected_decision_rows),
        "downstream_allocated_rows": str(downstream_rows),
        "downstream_order_header_seen_rows": str(header_match_rows),
        "downstream_item_match_rows": str(item_match_rows),
        "with_return_cogs_rows": str(cogs_rows),
        "unclassified_rows": str(
            int((preview["correction_impact_lane"].astype(str).str.strip() == "").sum()) if not preview.empty else 0
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


def write_disposition_correction_impact_preview_outputs(result: dict[str, object]) -> dict[str, Path]:
    preview_path = Path(result["preview_path"])
    summary_path = Path(result["summary_path"])
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    safe_to_csv(result["preview"], preview_path, index=False)
    safe_to_csv(result["summary"], summary_path, index=False)
    return {"preview": preview_path, "summary": summary_path}


def main() -> None:
    result = build_disposition_correction_impact_preview()
    paths = write_disposition_correction_impact_preview_outputs(result)
    preview = result["preview"]
    values = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()} if not result["summary"].empty else {}
    print(
        {
            "status": values.get("status", ""),
            "preview_rows": len(preview),
            "downstream_allocated_rows": values.get("downstream_allocated_rows", "0"),
            "with_return_cogs_rows": values.get("with_return_cogs_rows", "0"),
            "preview": str(paths["preview"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
