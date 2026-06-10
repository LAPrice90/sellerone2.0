from __future__ import annotations

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
TOKEN_ALLOCATIONS = OUT / "token_allocations_live.csv"
MANUAL_CORRECTIONS_APPROVED = OUT / "manual_token_corrections_approved.csv"
STOCK_RECEIPT_SUMMARY = OUT / "stock_receipt_summary.csv"
REPAIR_DIR = OUT / "systems" / "B" / "token_shortage_repair"
PREVIEW_PATH = REPAIR_DIR / "b_legacy_baseline_gap_preview.csv"
SUMMARY_PATH = REPAIR_DIR / "b_legacy_baseline_gap_preview_summary.csv"

B_OWNER_LOCKS = [
    OUT / "B_cycle.lock",
    OUT / "B_supervisor.lock",
    OUT / "systems" / "B" / "live" / "B_cycle.lock",
    OUT / "systems" / "B" / "live" / "B_supervisor.lock",
]

PENDING_APPROVAL_REFERENCE = "PENDING_NAMED_LEGACY_BASELINE_DECISION"

PREVIEW_COLUMNS = [
    "sku",
    "order_id",
    "order_date",
    "quantity",
    "source_level",
    "order_currency",
    "shortage_class",
    "shortage_missing_qty",
    "shortage_next_action",
    "existing_manual_baseline_qty",
    "manual_approval_references",
    "stock_receipt_batch_ids",
    "latest_stock_receipt_cost_per_unit",
    "basis_cost_per_unit",
    "basis_currency",
    "basis_token_id",
    "existing_token_count",
    "available_token_count",
    "allocated_token_count",
    "duplicate_allocation_count",
    "proposed_repair_lane",
    "proposed_token_status",
    "proposed_token_id",
    "proposed_approval_reference",
    "manager_recommendation",
    "review_readiness",
    "preview_live_write_allowed",
    "protected_before_apply",
    "roi_or_restock_use_allowed",
    "sellerboard_final_truth_allowed",
    "active_b_owner_seen",
    "bounded_worker_task",
    "retest_rule",
    "protected_stop_rule",
    "notes",
]

SUMMARY_COLUMNS = ["metric", "value"]


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


def _as_float_text(value: object) -> str:
    try:
        number = float(_text(value))
    except Exception:
        return ""
    if number <= 0:
        return ""
    return f"{number:.2f}"


def _parse_date(value: object) -> pd.Timestamp:
    text = _text(value)
    if not text:
        return pd.NaT
    normalized = text.replace("Z", "+00:00")
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            parsed = datetime.strptime(normalized, fmt)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            return pd.Timestamp(parsed, tz="UTC")
        return pd.Timestamp(parsed).tz_convert("UTC")
    return pd.NaT


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = ""
    return out


def _latest_cost_basis(ledger: pd.DataFrame, sku: str) -> dict[str, str] | None:
    if ledger.empty:
        return None
    work = _ensure_columns(
        ledger,
        ["seller_sku", "cost_per_unit", "currency", "token_id", "received_date", "created_at", "allocated_date"],
    )
    work = work[work["seller_sku"].astype(str).str.strip() == sku].copy()
    if work.empty:
        return None
    work["cost_num"] = pd.to_numeric(work["cost_per_unit"], errors="coerce").fillna(0.0)
    work = work[work["cost_num"] > 0].copy()
    if work.empty:
        return None
    work["received_dt"] = work["received_date"].map(_parse_date)
    work["created_dt"] = work["created_at"].map(_parse_date)
    work["allocated_dt"] = work["allocated_date"].map(_parse_date)
    work["row_num"] = range(len(work.index))
    latest = work.sort_values(["received_dt", "created_dt", "allocated_dt", "row_num"]).iloc[-1]
    return {
        "cost_per_unit": f"{float(latest['cost_num']):.2f}",
        "currency": _text(latest.get("currency", "")) or "GBP",
        "basis_token_id": _text(latest.get("token_id", "")),
    }


def _missing_orders_for_sku(missing_orders: pd.DataFrame, sku: str) -> pd.DataFrame:
    work = _ensure_columns(missing_orders, ["Order ID", "SKU", "Date", "Quantity Ordered", "lvl", "currency_code"])
    work = work[work["SKU"].astype(str).str.strip() == sku].copy()
    work["qty_int"] = work["Quantity Ordered"].map(_as_int)
    work = work[work["qty_int"] > 0].copy()
    return work.sort_values(["Date", "Order ID"])


def _manual_baseline_evidence(manual: pd.DataFrame, sku: str) -> tuple[int, str]:
    if manual.empty:
        return 0, ""
    work = _ensure_columns(manual, ["seller_sku", "quantity", "correction_class", "approval_reference"])
    work = work[work["seller_sku"].astype(str).str.strip() == sku].copy()
    work = work[work["correction_class"].astype(str).str.strip() == "approved_baseline_correction"].copy()
    if work.empty:
        return 0, ""
    qty = int(work["quantity"].map(_as_int).sum())
    references = sorted({_text(value) for value in work["approval_reference"].tolist() if _text(value)})
    return qty, ";".join(references)


def _stock_receipt_evidence(receipts: pd.DataFrame, sku: str) -> tuple[str, str]:
    if receipts.empty:
        return "", ""
    work = _ensure_columns(receipts, ["seller_sku", "cost_per_unit", "status", "batch_id", "intake_date", "row_num"])
    work = work[work["seller_sku"].astype(str).str.strip() == sku].copy()
    work = work[work["status"].astype(str).str.strip().str.upper() == "APPLIED"].copy()
    if work.empty:
        return "", ""
    work["cost_num"] = pd.to_numeric(work["cost_per_unit"], errors="coerce").fillna(0.0)
    work["intake_dt"] = work["intake_date"].map(_parse_date)
    work["row_num_int"] = work["row_num"].map(_as_int)
    batches = sorted({_text(value) for value in work["batch_id"].tolist() if _text(value)})
    cost_rows = work[work["cost_num"] > 0].copy()
    if cost_rows.empty:
        return ";".join(batches), ""
    latest = cost_rows.sort_values(["intake_dt", "row_num_int"]).iloc[-1]
    return ";".join(batches), f"{float(latest['cost_num']):.2f}"


def _token_counts(ledger: pd.DataFrame, sku: str) -> dict[str, int]:
    work = _ensure_columns(ledger, ["seller_sku", "status"])
    work = work[work["seller_sku"].astype(str).str.strip() == sku].copy()
    statuses = work["status"].astype(str).str.strip()
    return {
        "existing": len(work),
        "available": int((statuses == "available").sum()),
        "allocated": int((statuses == "allocated").sum()),
    }


def _duplicate_allocation_count(allocations: pd.DataFrame, sku: str, order_id: str) -> int:
    if allocations.empty:
        return 0
    work = _ensure_columns(allocations, ["seller_sku", "order_id"])
    return int(
        (
            (work["seller_sku"].astype(str).str.strip() == sku)
            & (work["order_id"].astype(str).str.strip() == order_id)
        ).sum()
    )


def _active_b_owner_seen(root: Path) -> bool:
    return any((root / path).exists() for path in B_OWNER_LOCKS)


def _new_token_id(sku: str, sequence: int) -> str:
    return f"MANAGER-CORR-{_safe(sku)}-LEGACY_BASELINE_PREVIEW-{sequence:04d}"


def build_legacy_baseline_gap_preview(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
) -> dict[str, pd.DataFrame]:
    root_path = Path(root or ".")
    observed = observed_utc or _utc_now_text()
    shortages = _read_csv(root_path / TOKEN_SHORTAGES)
    missing_orders = _read_csv(root_path / ORDERS_MISSING_TOKENS)
    ledger = _read_csv(root_path / TOKEN_LEDGER)
    allocations = _read_csv(root_path / TOKEN_ALLOCATIONS)
    manual = _read_csv(root_path / MANUAL_CORRECTIONS_APPROVED)
    receipts = _read_csv(root_path / STOCK_RECEIPT_SUMMARY)
    active_owner = "1" if _active_b_owner_seen(root_path) else "0"

    shortages = _ensure_columns(shortages, ["seller_sku", "missing_qty", "shortage_class", "next_action"])
    target_shortages = shortages[
        shortages["shortage_class"].astype(str).str.strip() == "legacy_baseline_gap"
    ].copy()

    rows: list[dict[str, str]] = []
    blocked_reasons: list[str] = []

    for _, shortage in target_shortages.iterrows():
        sku = _text(shortage.get("seller_sku", ""))
        shortage_qty = _as_int(shortage.get("missing_qty", ""))
        sku_missing_orders = _missing_orders_for_sku(missing_orders, sku)
        missing_order_units = int(sku_missing_orders["qty_int"].sum()) if not sku_missing_orders.empty else 0
        basis = _latest_cost_basis(ledger, sku)
        manual_qty, manual_refs = _manual_baseline_evidence(manual, sku)
        receipt_batches, receipt_cost = _stock_receipt_evidence(receipts, sku)
        counts = _token_counts(ledger, sku)

        sku_blockers: list[str] = []
        if shortage_qty <= 0:
            sku_blockers.append("missing shortage quantity")
        if missing_order_units != shortage_qty:
            sku_blockers.append("missing-order units do not match shortage quantity")
        if basis is None:
            sku_blockers.append("no positive token cost basis")
        if manual_qty <= 0 and not receipt_batches:
            sku_blockers.append("no manual baseline or applied stock receipt clue")

        sequence = 0
        for _, order in sku_missing_orders.iterrows():
            order_id = _text(order.get("Order ID", ""))
            duplicate_count = _duplicate_allocation_count(allocations, sku, order_id)
            if duplicate_count:
                sku_blockers.append(f"duplicate allocation already exists for {order_id}")
            for _ in range(_as_int(order.get("Quantity Ordered", ""))):
                sequence += 1
                readiness = "blocked" if sku_blockers else "decision_ready_named_protected_window"
                rows.append(
                    {
                        "sku": sku,
                        "order_id": order_id,
                        "order_date": _text(order.get("Date", "")),
                        "quantity": "1",
                        "source_level": _text(order.get("lvl", "")),
                        "order_currency": _text(order.get("currency_code", "")),
                        "shortage_class": _text(shortage.get("shortage_class", "")),
                        "shortage_missing_qty": str(shortage_qty),
                        "shortage_next_action": _text(shortage.get("next_action", "")),
                        "existing_manual_baseline_qty": str(manual_qty),
                        "manual_approval_references": manual_refs,
                        "stock_receipt_batch_ids": receipt_batches,
                        "latest_stock_receipt_cost_per_unit": receipt_cost,
                        "basis_cost_per_unit": basis["cost_per_unit"] if basis else "",
                        "basis_currency": basis["currency"] if basis else "",
                        "basis_token_id": basis["basis_token_id"] if basis else "",
                        "existing_token_count": str(counts["existing"]),
                        "available_token_count": str(counts["available"]),
                        "allocated_token_count": str(counts["allocated"]),
                        "duplicate_allocation_count": str(duplicate_count),
                        "proposed_repair_lane": "legacy_baseline_sale_token_correction",
                        "proposed_token_status": "allocated",
                        "proposed_token_id": _new_token_id(sku, sequence),
                        "proposed_approval_reference": PENDING_APPROVAL_REFERENCE,
                        "manager_recommendation": (
                            "approve_one_token_baseline_correction"
                            if not sku_blockers and shortage_qty == 1
                            else "review_before_correction"
                        ),
                        "review_readiness": readiness,
                        "preview_live_write_allowed": "0",
                        "protected_before_apply": "1",
                        "roi_or_restock_use_allowed": "0",
                        "sellerboard_final_truth_allowed": "0",
                        "active_b_owner_seen": active_owner,
                        "bounded_worker_task": (
                            "If Luke approves the named protected window, create allocated correction tokens "
                            "only for rows that remain decision-ready in this same preview."
                        ),
                        "retest_rule": (
                            "After protected apply, rerun B MOT and require the same token-shortage and P and L "
                            "gate rows to clear through the normal B path."
                        ),
                        "protected_stop_rule": (
                            "Stop before live token write, B run/restart, lock or marker edit, Sheets, local DB, "
                            "output deletion, prices, queues, ROI/restocking use, or scope widening."
                        ),
                        "notes": ";".join(sku_blockers) if sku_blockers else "preview_only_no_live_write",
                    }
                )
        if sku_blockers:
            blocked_reasons.extend(f"{sku}: {reason}" for reason in sorted(set(sku_blockers)))

    preview = pd.DataFrame(rows, columns=PREVIEW_COLUMNS).fillna("")
    ready_rows = int((preview["review_readiness"] == "decision_ready_named_protected_window").sum()) if not preview.empty else 0
    blocked_rows = int((preview["review_readiness"] == "blocked").sum()) if not preview.empty else 0
    if preview.empty and target_shortages.empty:
        status = "no_legacy_baseline_gaps"
    elif blocked_rows:
        status = "blocked"
    else:
        status = "decision_ready"
    summary = pd.DataFrame(
        [
            {"metric": "status", "value": status},
            {"metric": "observed_utc", "value": observed},
            {"metric": "preview_rows", "value": str(len(preview))},
            {"metric": "decision_ready_rows", "value": str(ready_rows)},
            {"metric": "blocked_rows", "value": str(blocked_rows)},
            {"metric": "sku_count", "value": str(preview["sku"].nunique() if not preview.empty else 0)},
            {"metric": "active_b_owner_seen", "value": active_owner},
            {"metric": "blocked_reasons", "value": "|".join(sorted(set(blocked_reasons)))},
            {"metric": "live_write_allowed", "value": "0"},
            {"metric": "roi_or_restock_use_allowed", "value": "0"},
        ],
        columns=SUMMARY_COLUMNS,
    )
    return {"preview": preview, "summary": summary}


def write_legacy_baseline_gap_preview_outputs(
    result: dict[str, pd.DataFrame],
    *,
    root: Path | str | None = None,
) -> dict[str, Path]:
    root_path = Path(root or ".")
    preview_path = root_path / PREVIEW_PATH
    summary_path = root_path / SUMMARY_PATH
    safe_to_csv(result["preview"], preview_path, index=False)
    safe_to_csv(result["summary"], summary_path, index=False)
    return {"preview": preview_path, "summary": summary_path}


def main() -> None:
    result = build_legacy_baseline_gap_preview()
    paths = write_legacy_baseline_gap_preview_outputs(result)
    values = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}
    print(
        {
            "status": values.get("status", ""),
            "preview_rows": values.get("preview_rows", "0"),
            "decision_ready_rows": values.get("decision_ready_rows", "0"),
            "blocked_rows": values.get("blocked_rows", "0"),
            "active_b_owner_seen": values.get("active_b_owner_seen", "0"),
            "preview": str(paths["preview"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
