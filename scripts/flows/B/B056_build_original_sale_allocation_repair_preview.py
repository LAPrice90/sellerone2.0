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
SOURCE_AUDIT = OUT / "systems" / "B" / "refunds" / "b_original_allocation_gap_audit.csv"
MISSING_TOKENS = OUT / "orders_missing_tokens.csv"
TOKEN_SHORTAGES = OUT / "token_shortages_by_sku.csv"
TOKEN_ALLOCATIONS = OUT / "token_allocations_live.csv"
TOKEN_LEDGER = OUT / "token_ledger_live.csv"
TOKEN_COGS = OUT / "token_cogs_ledger.csv"
OUT_PREVIEW = OUT / "systems" / "B" / "refunds" / "b_original_sale_allocation_repair_preview.csv"
OUT_SUMMARY = OUT / "systems" / "B" / "refunds" / "b_original_sale_allocation_repair_preview_summary.csv"

TARGET_CONCLUSION = "order_seen_allocation_missing"

PREVIEW_COLUMNS = [
    "order_id",
    "sku",
    "order_date",
    "refund_posted_date",
    "source_level",
    "order_currency",
    "missing_token_rows",
    "missing_token_quantity",
    "missing_token_reason_class",
    "receipt_state_class",
    "shortage_class",
    "shortage_next_action",
    "token_allocation_rows",
    "token_ledger_allocated_rows",
    "basis_cost_per_unit",
    "basis_currency",
    "basis_source_token_id",
    "repair_lane",
    "repair_readiness",
    "manager_expectation",
    "bounded_worker_task",
    "retest_rule",
    "preview_live_write_allowed",
    "roi_or_restock_use_allowed",
    "sellerboard_final_truth_allowed",
    "protected_before_apply",
]

SUMMARY_COLUMNS = ["metric", "value"]


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, keep_default_na=False).fillna("")


def _text(value: object) -> str:
    return str(value or "").strip()


def _norm_sku(value: object) -> str:
    return _text(value).upper()


def _as_int(value: object) -> int:
    try:
        return int(float(_text(value)))
    except Exception:
        return 0


def _as_float(value: object) -> float:
    try:
        return float(_text(value))
    except Exception:
        return 0.0


def _prepare_source(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["order_id", "sku", "refund_posted_date", "allocation_gap_conclusion"]:
        if column not in work.columns:
            work[column] = ""
    work["order_id_norm"] = work["order_id"].map(_text)
    work["sku_norm"] = work["sku"].map(_norm_sku)
    return work[
        (work["allocation_gap_conclusion"].astype(str).str.strip() == TARGET_CONCLUSION)
        & (work["order_id_norm"] != "")
        & (work["sku_norm"] != "")
    ].copy()


def _prepare_missing_tokens(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["Order ID", "SKU", "Date", "lvl", "currency_code", "Quantity Ordered", "missing_token_reason_class", "receipt_state_class"]:
        if column not in work.columns:
            work[column] = ""
    work["order_id_norm"] = work["Order ID"].map(_text)
    work["sku_norm"] = work["SKU"].map(_norm_sku)
    work["qty_int"] = work["Quantity Ordered"].map(_as_int)
    return work


def _prepare_shortages(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["seller_sku", "shortage_class", "next_action"]:
        if column not in work.columns:
            work[column] = ""
    work["sku_norm"] = work["seller_sku"].map(_norm_sku)
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
    for column in ["seller_sku", "allocated_order_id", "token_id", "cost_per_unit", "currency", "received_date", "created_at", "allocated_date"]:
        if column not in work.columns:
            work[column] = ""
    work["sku_norm"] = work["seller_sku"].map(_norm_sku)
    work["allocated_order_norm"] = work["allocated_order_id"].map(_text)
    return work


def _latest_basis(ledger: pd.DataFrame, cogs: pd.DataFrame, sku: str) -> tuple[str, str, str]:
    if not cogs.empty:
        work = cogs.copy()
        for column in ["seller_sku", "token_cost", "currency", "token_id", "order_date"]:
            if column not in work.columns:
                work[column] = ""
        work["sku_norm"] = work["seller_sku"].map(_norm_sku)
        work["cost_num"] = work["token_cost"].map(_as_float)
        rows = work[(work["sku_norm"] == sku) & (work["cost_num"] > 0)].copy()
        if not rows.empty:
            row = rows.iloc[-1]
            return f"{float(row['cost_num']):.2f}", _text(row.get("currency", "")) or "GBP", _text(row.get("token_id", ""))
    if ledger.empty:
        return "", "", ""
    rows = ledger[ledger["sku_norm"] == sku].copy()
    if rows.empty:
        return "", "", ""
    rows["cost_num"] = rows["cost_per_unit"].map(_as_float)
    rows = rows[rows["cost_num"] > 0].copy()
    if rows.empty:
        return "", "", ""
    row = rows.iloc[-1]
    return f"{float(row['cost_num']):.2f}", _text(row.get("currency", "")) or "GBP", _text(row.get("token_id", ""))


def _classify(missing_rows: int, shortage_class: str, basis_cost: str) -> tuple[str, str, str, str, str]:
    if not missing_rows:
        return (
            "allocation_gap_missing_token_row_not_visible",
            "blocked_needs_missing_token_proof",
            "The order exists, but the missing-token proof row is not visible.",
            "Repair missing-token proof before any token correction is proposed.",
            "Rerun B056 and B MOT after the missing-token row is manager-readable.",
        )
    if not basis_cost:
        return (
            "allocation_gap_missing_cost_basis",
            "blocked_needs_cost_basis",
            "The order is missing allocation proof, but no cost basis is available for a safe preview.",
            "Find API/order/token cost basis before any protected token correction is proposed.",
            "Rerun B056 after cost basis is manager-readable.",
        )
    if shortage_class == "runtime_adjustment_pending":
        return (
            "protected_runtime_adjustment_allocation_candidate",
            "blocked_needs_protected_stock_decision",
            "The missing allocation is tied to a runtime stock-adjustment shortage. Stock truth must be decided before token correction.",
            "Build a protected token-allocation correction preview using the existing token shortage route; do not apply without Luke approval.",
            "After approved correction, rerun B007/B008/B038/B041/B042/B053/B056 and B MOT.",
        )
    if shortage_class == "legacy_baseline_gap":
        return (
            "protected_legacy_baseline_allocation_candidate",
            "blocked_needs_protected_stock_decision",
            "The missing allocation is an old baseline gap. It can only be corrected through a protected token allocation decision.",
            "Build a protected legacy-baseline token allocation preview; do not apply without Luke approval.",
            "After approved correction, rerun B007/B008/B038/B041/B042/B053/B056 and B MOT.",
        )
    return (
        "protected_original_sale_allocation_candidate",
        "blocked_needs_protected_stock_decision",
        "The order exists and is missing original sale-token allocation proof.",
        "Build a protected token allocation preview through the existing token route; do not create stock from refund evidence.",
        "After approved correction, rerun B007/B008/B038/B041/B042/B053/B056 and B MOT.",
    )


def build_original_sale_allocation_repair_preview(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
) -> dict[str, pd.DataFrame]:
    root_path = Path(root or ".")
    observed = observed_utc or _utc_now_text()
    source = _prepare_source(_read_csv(root_path / SOURCE_AUDIT))
    missing = _prepare_missing_tokens(_read_csv(root_path / MISSING_TOKENS))
    shortages = _prepare_shortages(_read_csv(root_path / TOKEN_SHORTAGES))
    allocations = _prepare_allocations(_read_csv(root_path / TOKEN_ALLOCATIONS))
    ledger = _prepare_ledger(_read_csv(root_path / TOKEN_LEDGER))
    cogs = _read_csv(root_path / TOKEN_COGS)

    rows: list[dict[str, str]] = []
    for _, source_row in source.iterrows():
        order_id = _text(source_row.get("order_id_norm", ""))
        sku = _norm_sku(source_row.get("sku_norm", ""))
        missing_rows = missing[(missing["order_id_norm"] == order_id) & (missing["sku_norm"] == sku)] if not missing.empty else missing
        shortage_rows = shortages[shortages["sku_norm"] == sku] if not shortages.empty else shortages
        allocation_rows = allocations[(allocations["order_id_norm"] == order_id) & (allocations["sku_norm"] == sku)] if not allocations.empty else allocations
        ledger_rows = ledger[(ledger["allocated_order_norm"] == order_id) & (ledger["sku_norm"] == sku)] if not ledger.empty else ledger
        shortage_class = _text(shortage_rows.iloc[0].get("shortage_class", "")) if not shortage_rows.empty else ""
        basis_cost, basis_currency, basis_token = _latest_basis(ledger, cogs, sku)
        lane, readiness, expectation, worker_task, retest = _classify(len(missing_rows), shortage_class, basis_cost)
        rows.append(
            {
                "order_id": order_id,
                "sku": sku,
                "order_date": _text(missing_rows.iloc[0].get("Date", "")) if not missing_rows.empty else "",
                "refund_posted_date": _text(source_row.get("refund_posted_date", "")),
                "source_level": _text(missing_rows.iloc[0].get("lvl", "")) if not missing_rows.empty else "",
                "order_currency": _text(missing_rows.iloc[0].get("currency_code", "")) if not missing_rows.empty else "",
                "missing_token_rows": str(len(missing_rows)),
                "missing_token_quantity": str(sum(_as_int(value) for value in missing_rows.get("Quantity Ordered", pd.Series(dtype=str)).tolist())) if not missing_rows.empty else "0",
                "missing_token_reason_class": _text(missing_rows.iloc[0].get("missing_token_reason_class", "")) if not missing_rows.empty else "",
                "receipt_state_class": _text(missing_rows.iloc[0].get("receipt_state_class", "")) if not missing_rows.empty else "",
                "shortage_class": shortage_class,
                "shortage_next_action": _text(shortage_rows.iloc[0].get("next_action", "")) if not shortage_rows.empty else "",
                "token_allocation_rows": str(len(allocation_rows)),
                "token_ledger_allocated_rows": str(len(ledger_rows)),
                "basis_cost_per_unit": basis_cost,
                "basis_currency": basis_currency,
                "basis_source_token_id": basis_token,
                "repair_lane": lane,
                "repair_readiness": readiness,
                "manager_expectation": expectation,
                "bounded_worker_task": worker_task,
                "retest_rule": retest,
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "protected_before_apply": "1",
            }
        )

    preview = pd.DataFrame(rows, columns=PREVIEW_COLUMNS).fillna("")
    unclassified = preview[
        (preview["repair_lane"].astype(str).str.strip() == "")
        | (preview["repair_readiness"].astype(str).str.strip() == "")
        | (preview["bounded_worker_task"].astype(str).str.strip() == "")
    ] if not preview.empty else preview
    unsafe_rows = 0
    if not preview.empty:
        unsafe_rows = int(
            (preview["preview_live_write_allowed"].astype(str).str.strip() != "0").sum()
            + (preview["roi_or_restock_use_allowed"].astype(str).str.strip() != "0").sum()
            + (preview["sellerboard_final_truth_allowed"].astype(str).str.strip() != "0").sum()
        )
    status = "ok"
    if source.empty and not (root_path / SOURCE_AUDIT).exists():
        status = "not_checked"
    elif unclassified.shape[0] or unsafe_rows:
        status = "fail"
    summary_values = {
        "status": status,
        "observed_utc": observed,
        "preview_rows": str(len(preview)),
        "legacy_baseline_candidate_rows": str(int((preview["repair_lane"] == "protected_legacy_baseline_allocation_candidate").sum()) if not preview.empty else 0),
        "runtime_adjustment_candidate_rows": str(int((preview["repair_lane"] == "protected_runtime_adjustment_allocation_candidate").sum()) if not preview.empty else 0),
        "missing_token_proof_gap_rows": str(int((preview["repair_lane"] == "allocation_gap_missing_token_row_not_visible").sum()) if not preview.empty else 0),
        "missing_cost_basis_rows": str(int((preview["repair_lane"] == "allocation_gap_missing_cost_basis").sum()) if not preview.empty else 0),
        "unclassified_rows": str(len(unclassified)),
        "unsafe_rows": str(unsafe_rows),
    }
    summary = pd.DataFrame([{"metric": key, "value": value} for key, value in summary_values.items()], columns=SUMMARY_COLUMNS)
    return {"preview": preview, "summary": summary}


def write_original_sale_allocation_repair_preview_outputs(
    result: dict[str, pd.DataFrame],
    *,
    root: Path | str | None = None,
) -> dict[str, Path]:
    root_path = Path(root or ".")
    preview_path = root_path / OUT_PREVIEW
    summary_path = root_path / OUT_SUMMARY
    safe_to_csv(result["preview"], preview_path, index=False)
    safe_to_csv(result["summary"], summary_path, index=False)
    return {"preview": preview_path, "summary": summary_path}


def main() -> None:
    result = build_original_sale_allocation_repair_preview()
    paths = write_original_sale_allocation_repair_preview_outputs(result)
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}
    print(
        {
            "status": summary.get("status", ""),
            "preview_rows": summary.get("preview_rows", "0"),
            "legacy_baseline_candidate_rows": summary.get("legacy_baseline_candidate_rows", "0"),
            "runtime_adjustment_candidate_rows": summary.get("runtime_adjustment_candidate_rows", "0"),
            "preview": str(paths["preview"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
