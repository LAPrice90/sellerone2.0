from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.safe_file_writes import safe_to_csv


OUT = Path("out")
TOKEN_SHORTAGES = OUT / "token_shortages_by_sku.csv"
ORDERS_MISSING_TOKENS = OUT / "orders_missing_tokens.csv"
TOKEN_LEDGER = OUT / "token_ledger_live.csv"
STOCK_ADJUSTMENT_EVENTS = OUT / "stock_adjustment_token_events.csv"
REPAIR_DIR = OUT / "systems" / "B" / "token_shortage_repair"
PREVIEW_PATH = REPAIR_DIR / "b_token_shortage_repair_preview.csv"
SUMMARY_PATH = REPAIR_DIR / "b_token_shortage_repair_preview_summary.csv"

APPROVED_SKUS = {"AK-OB6V-HIYD"}
APPROVAL_REFERENCE = "TOKEN_SHORTAGE_20260604_LUKE_APPROVED_AK_OB6V_HIYD_COST_1_21"

PREVIEW_COLUMNS = [
    "sku",
    "repair_lane",
    "order_id",
    "order_date",
    "quantity",
    "source_level",
    "order_currency",
    "shortage_class",
    "shortage_missing_qty",
    "stock_adjustment_event_id",
    "stock_adjustment_event_date",
    "stock_adjustment_quantity",
    "new_token_role",
    "new_token_status",
    "new_token_id",
    "basis_cost_per_unit",
    "basis_currency",
    "basis_token_id",
    "approval_reference",
    "review_readiness",
    "preview_live_write_allowed",
    "protected_before_apply",
    "roi_or_restock_use_allowed",
    "sellerboard_final_truth_allowed",
    "bounded_worker_task",
    "retest_rule",
    "protected_stop_rule",
    "notes",
]

SUMMARY_COLUMNS = ["metric", "value"]


@dataclass(frozen=True)
class PendingAdjustment:
    event_id: str
    event_date: str
    quantity: int
    remaining_qty: int
    next_retry_event_id: str


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _text(value: object) -> str:
    return str(value or "").strip()


def _safe(value: object) -> str:
    raw = _text(value).upper()
    return re.sub(r"[^A-Z0-9._-]", "_", raw)[:90] or "BLANK"


def _as_int(value: object) -> int:
    try:
        return int(float(_text(value)))
    except Exception:
        return 0


def _base_adjustment_id(event_id: str) -> str:
    return re.split(r"-retry\d+$", _text(event_id), maxsplit=1)[0]


def _next_retry_id(events: pd.DataFrame, base_event_id: str) -> str:
    max_retry = 0
    if not events.empty and "event_id" in events.columns:
        for event_id in events["event_id"].astype(str).tolist():
            text = _text(event_id)
            if text == base_event_id:
                continue
            match = re.fullmatch(re.escape(base_event_id) + r"-retry(\d+)", text)
            if match:
                max_retry = max(max_retry, int(match.group(1)))
    return f"{base_event_id}-retry{max_retry + 1}"


def _pending_adjustment_for_sku(events: pd.DataFrame, sku: str, evidence_note: str) -> PendingAdjustment | None:
    if events.empty or "sku" not in events.columns:
        return None
    match = re.search(r"base_event_id=([^;]+)", evidence_note)
    if not match:
        return None
    base_event_id = match.group(1).strip()
    if not base_event_id:
        return None
    work = events.copy()
    for column in ["event_id", "sku", "event_date", "quantity", "applied_qty"]:
        if column not in work.columns:
            work[column] = ""
    work = work[work["sku"].astype(str).str.strip() == sku].copy()
    work["base_event_id"] = work["event_id"].map(_base_adjustment_id)
    group = work[work["base_event_id"] == base_event_id].copy()
    if group.empty:
        return None
    quantity = max(abs(_as_int(value)) for value in group["quantity"].tolist())
    applied = sum(abs(_as_int(value)) for value in group["applied_qty"].tolist())
    remaining = max(quantity - applied, 0)
    if remaining <= 0:
        return None
    event_date = _text(group.iloc[0].get("event_date", ""))
    return PendingAdjustment(
        event_id=base_event_id,
        event_date=event_date,
        quantity=-remaining,
        remaining_qty=remaining,
        next_retry_event_id=_next_retry_id(work, base_event_id),
    )


def _latest_cost_basis(ledger: pd.DataFrame, sku: str) -> dict[str, str] | None:
    if ledger.empty or "seller_sku" not in ledger.columns:
        return None
    work = ledger[ledger["seller_sku"].astype(str).str.strip() == sku].copy()
    if work.empty:
        return None
    for column in ["cost_per_unit", "currency", "token_id", "received_date", "created_at", "allocated_date"]:
        if column not in work.columns:
            work[column] = ""
    work["cost_num"] = pd.to_numeric(work["cost_per_unit"], errors="coerce").fillna(0.0)
    work = work[work["cost_num"] > 0].copy()
    if work.empty:
        return None
    work["received_dt"] = pd.to_datetime(work["received_date"], errors="coerce", utc=True)
    work["created_dt"] = pd.to_datetime(work["created_at"], errors="coerce", utc=True)
    work["allocated_dt"] = pd.to_datetime(work["allocated_date"], errors="coerce", utc=True)
    work["row_num"] = range(len(work.index))
    latest = work.sort_values(["received_dt", "created_dt", "allocated_dt", "row_num"]).iloc[-1]
    return {
        "cost_per_unit": f"{float(latest['cost_num']):.2f}",
        "currency": _text(latest.get("currency", "")) or "GBP",
        "basis_token_id": _text(latest.get("token_id", "")),
    }


def _missing_orders_for_sku(missing_orders: pd.DataFrame, sku: str) -> pd.DataFrame:
    if missing_orders.empty:
        return pd.DataFrame()
    work = missing_orders.copy()
    for column in ["Order ID", "SKU", "Date", "Quantity Ordered", "lvl", "currency_code"]:
        if column not in work.columns:
            work[column] = ""
    work = work[work["SKU"].astype(str).str.strip() == sku].copy()
    work["qty_int"] = work["Quantity Ordered"].map(_as_int)
    work = work[work["qty_int"] > 0].copy()
    return work.sort_values(["Date", "Order ID"])


def _new_token_id(sku: str, role: str, sequence: int, source_key: str = "") -> str:
    key = _safe(source_key)
    key_part = f"-{key}" if key else ""
    return f"MANAGER-CORR-{_safe(sku)}-{_safe(APPROVAL_REFERENCE)}-{role}{key_part}-{sequence:04d}"


def build_token_shortage_repair_preview(*, root: Path | str | None = None) -> dict[str, pd.DataFrame]:
    root_path = Path(root or ".")
    shortages = _read_csv(root_path / TOKEN_SHORTAGES)
    missing_orders = _read_csv(root_path / ORDERS_MISSING_TOKENS)
    ledger = _read_csv(root_path / TOKEN_LEDGER)
    adjustments = _read_csv(root_path / STOCK_ADJUSTMENT_EVENTS)

    rows: list[dict[str, str]] = []
    blocked_reasons: list[str] = []

    if shortages.empty:
        blocked_reasons.append("No token shortage rows found.")
    else:
        for column in ["seller_sku", "missing_qty", "shortage_class", "evidence_note"]:
            if column not in shortages.columns:
                shortages[column] = ""

    target_shortages = shortages[
        shortages["seller_sku"].astype(str).str.strip().isin(APPROVED_SKUS)
    ].copy()

    for _, shortage in target_shortages.iterrows():
        sku = _text(shortage.get("seller_sku", ""))
        shortage_class = _text(shortage.get("shortage_class", ""))
        shortage_qty = _as_int(shortage.get("missing_qty", ""))
        evidence_note = _text(shortage.get("evidence_note", ""))
        basis = _latest_cost_basis(ledger, sku)
        if basis is None:
            blocked_reasons.append(f"{sku}: no positive token cost basis found.")
            continue
        sku_missing_orders = _missing_orders_for_sku(missing_orders, sku)
        missing_order_units = int(sku_missing_orders["qty_int"].sum()) if not sku_missing_orders.empty else 0
        if missing_order_units != shortage_qty:
            blocked_reasons.append(f"{sku}: missing-order units do not match shortage quantity.")
            continue

        sequence = 0
        if shortage_class == "true_live_shortage":
            for _, order in sku_missing_orders.iterrows():
                for _ in range(_as_int(order.get("Quantity Ordered", ""))):
                    sequence += 1
                    rows.append(
                        {
                            "sku": sku,
                            "repair_lane": "approved_live_sale_token_correction",
                            "order_id": _text(order.get("Order ID", "")),
                            "order_date": _text(order.get("Date", "")),
                            "quantity": "1",
                            "source_level": _text(order.get("lvl", "")),
                            "order_currency": _text(order.get("currency_code", "")),
                            "shortage_class": shortage_class,
                            "shortage_missing_qty": str(shortage_qty),
                            "stock_adjustment_event_id": "",
                            "stock_adjustment_event_date": "",
                            "stock_adjustment_quantity": "",
                            "new_token_role": "SALE",
                            "new_token_status": "allocated",
                            "new_token_id": _new_token_id(sku, "SALE", sequence, _text(order.get("Order ID", ""))),
                            "basis_cost_per_unit": basis["cost_per_unit"],
                            "basis_currency": basis["currency"],
                            "basis_token_id": basis["basis_token_id"],
                            "approval_reference": APPROVAL_REFERENCE,
                            "review_readiness": "ready_for_protected_apply",
                            "preview_live_write_allowed": "0",
                            "protected_before_apply": "1",
                            "roi_or_restock_use_allowed": "0",
                            "sellerboard_final_truth_allowed": "0",
                            "bounded_worker_task": "Create and allocate approved correction tokens only for this SKU shortage.",
                            "retest_rule": "Rerun B047/B048 proof and B MOT; downstream P and L remains unproved until normal B proof rebuilds.",
                            "protected_stop_rule": "Stop before Sheets, local DB, B run/restart, prices, queues, output deletion, or widening beyond approved SKUs.",
                            "notes": "approved_missing_sale_token",
                        }
                    )
        elif shortage_class == "runtime_adjustment_pending":
            pending = _pending_adjustment_for_sku(adjustments, sku, evidence_note)
            if pending is None:
                blocked_reasons.append(f"{sku}: pending stock adjustment was not found or is already closed.")
                continue
            for _ in range(pending.remaining_qty):
                sequence += 1
                rows.append(
                    {
                        "sku": sku,
                        "repair_lane": "approved_historical_stock_adjustment_close",
                        "order_id": "",
                        "order_date": "",
                        "quantity": "1",
                        "source_level": "",
                        "order_currency": "",
                        "shortage_class": shortage_class,
                        "shortage_missing_qty": str(shortage_qty),
                        "stock_adjustment_event_id": pending.event_id,
                        "stock_adjustment_event_date": pending.event_date,
                        "stock_adjustment_quantity": str(pending.quantity),
                        "new_token_role": "ADJUSTMENT",
                        "new_token_status": "disposed",
                        "new_token_id": _new_token_id(sku, "ADJ", sequence, pending.event_id),
                        "basis_cost_per_unit": basis["cost_per_unit"],
                        "basis_currency": basis["currency"],
                        "basis_token_id": basis["basis_token_id"],
                        "approval_reference": APPROVAL_REFERENCE,
                        "review_readiness": "ready_for_protected_apply",
                        "preview_live_write_allowed": "0",
                        "protected_before_apply": "1",
                        "roi_or_restock_use_allowed": "0",
                        "sellerboard_final_truth_allowed": "0",
                        "bounded_worker_task": "Create one disposed correction token so the older Amazon stock removal is recorded, not ignored.",
                        "retest_rule": "Rerun B047/B048 proof and B MOT; downstream P and L remains unproved until normal B proof rebuilds.",
                        "protected_stop_rule": "Stop before Sheets, local DB, B run/restart, prices, queues, output deletion, or widening beyond approved SKUs.",
                        "notes": f"approved_stock_adjustment_close:{pending.next_retry_event_id}",
                    }
                )
            for _, order in sku_missing_orders.iterrows():
                for _ in range(_as_int(order.get("Quantity Ordered", ""))):
                    sequence += 1
                    rows.append(
                        {
                            "sku": sku,
                            "repair_lane": "approved_runtime_sale_token_correction",
                            "order_id": _text(order.get("Order ID", "")),
                            "order_date": _text(order.get("Date", "")),
                            "quantity": "1",
                            "source_level": _text(order.get("lvl", "")),
                            "order_currency": _text(order.get("currency_code", "")),
                            "shortage_class": shortage_class,
                            "shortage_missing_qty": str(shortage_qty),
                            "stock_adjustment_event_id": "",
                            "stock_adjustment_event_date": "",
                            "stock_adjustment_quantity": "",
                            "new_token_role": "SALE",
                            "new_token_status": "allocated",
                            "new_token_id": _new_token_id(sku, "SALE", sequence, _text(order.get("Order ID", ""))),
                            "basis_cost_per_unit": basis["cost_per_unit"],
                            "basis_currency": basis["currency"],
                            "basis_token_id": basis["basis_token_id"],
                            "approval_reference": APPROVAL_REFERENCE,
                            "review_readiness": "ready_for_protected_apply",
                            "preview_live_write_allowed": "0",
                            "protected_before_apply": "1",
                            "roi_or_restock_use_allowed": "0",
                            "sellerboard_final_truth_allowed": "0",
                            "bounded_worker_task": "Create and allocate the approved sale correction token after closing the older stock adjustment.",
                            "retest_rule": "Rerun B047/B048 proof and B MOT; downstream P and L remains unproved until normal B proof rebuilds.",
                            "protected_stop_rule": "Stop before Sheets, local DB, B run/restart, prices, queues, output deletion, or widening beyond approved SKUs.",
                            "notes": "approved_missing_sale_token_after_adjustment_close",
                        }
                    )
        else:
            blocked_reasons.append(f"{sku}: shortage class {shortage_class or 'blank'} is not approved for this repair.")

    preview = pd.DataFrame(rows, columns=PREVIEW_COLUMNS).fillna("")
    if blocked_reasons and not preview.empty:
        preview["review_readiness"] = "blocked"
        preview["notes"] = preview["notes"].astype(str) + ";blocked_preview"
    summary = pd.DataFrame(
        [
            {"metric": "approved_sku_count", "value": str(len(APPROVED_SKUS))},
            {"metric": "preview_rows", "value": str(len(preview))},
            {"metric": "sale_token_rows", "value": str((preview["new_token_role"] == "SALE").sum() if not preview.empty else 0)},
            {"metric": "adjustment_token_rows", "value": str((preview["new_token_role"] == "ADJUSTMENT").sum() if not preview.empty else 0)},
            {"metric": "blocked_reasons", "value": "|".join(blocked_reasons)},
            {"metric": "status", "value": "blocked" if blocked_reasons else "ready"},
        ],
        columns=SUMMARY_COLUMNS,
    )
    return {"preview": preview, "summary": summary}


def write_token_shortage_repair_preview_outputs(result: dict[str, pd.DataFrame], *, root: Path | str | None = None) -> dict[str, Path]:
    root_path = Path(root or ".")
    preview_path = root_path / PREVIEW_PATH
    summary_path = root_path / SUMMARY_PATH
    safe_to_csv(result["preview"], preview_path, index=False)
    safe_to_csv(result["summary"], summary_path, index=False)
    return {"preview": preview_path, "summary": summary_path}


def main() -> None:
    result = build_token_shortage_repair_preview()
    paths = write_token_shortage_repair_preview_outputs(result)
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}
    print(
        {
            "status": summary.get("status", ""),
            "preview_rows": summary.get("preview_rows", "0"),
            "sale_token_rows": summary.get("sale_token_rows", "0"),
            "adjustment_token_rows": summary.get("adjustment_token_rows", "0"),
            "preview": str(paths["preview"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
