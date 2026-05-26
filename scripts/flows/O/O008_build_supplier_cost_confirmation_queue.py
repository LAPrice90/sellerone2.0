from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.flows.O._contract_io import empty_o_contract_df, read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract
from scripts.flows.O._schemas import get_o_output_contract


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _truthy(value: object) -> bool:
    return _normalize_text(value).lower() in {"1", "true", "yes", "y", "on"}


def _needs_confirmation(row: pd.Series) -> bool:
    if _truthy(row.get("user_price_check_required", "")):
        return True
    reason = _normalize_text(row.get("review_reason", "")).lower()
    hard_review_tokens = {
        "discount_assumption_needs_confirmation",
        "price_list_changed_after_discounted_purchase",
        "actual_paid_above_list_needs_review",
        "actual_paid_without_list_reference",
        "missing_current_price_list_cost",
        "missing_all_cost_inputs",
    }
    return any(token in reason for token in hard_review_tokens)


def _prompt_for(row: pd.Series) -> str:
    reason = _normalize_text(row.get("review_reason", ""))
    sku = _normalize_text(row.get("seller_sku", ""))
    expected = _normalize_text(row.get("expected_next_unit_cost_gbp", ""))
    list_cost = _normalize_text(row.get("price_list_unit_cost_gbp", ""))
    actual = _normalize_text(row.get("actual_paid_unit_cost_gbp", ""))
    ratio = _normalize_text(row.get("actual_vs_list_ratio", ""))
    if "discount_assumption_needs_confirmation" in reason:
        return (
            f"Check supplier price for {sku}: latest list is {list_cost}, "
            f"last paid was {actual}, assumed ratio is {ratio}, expected next cost is {expected}."
        )
    if "actual_paid_above_list_needs_review" in reason:
        return f"Check supplier price for {sku}: last paid cost is above the reference list price."
    if "missing_current_price_list_cost" in reason:
        return f"Check supplier price for {sku}: no current collected price-list cost is available."
    if "missing_all_cost_inputs" in reason:
        return f"Add supplier cost evidence for {sku}: no usable list or purchase cost is available."
    return f"Check supplier cost assumption for {sku}."


def build_supplier_cost_confirmation_queue(
    root: Path | None = None,
    *,
    queue_utc: str | None = None,
) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    timestamp_utc = queue_utc or _utc_now_iso()

    truth_df = read_o_contract_df(root_path, "supplier_buy_cost_truth")
    out_path = root_path / get_o_output_contract("supplier_cost_confirmation_queue").rel_path
    if truth_df.empty:
        out_df = empty_o_contract_df("supplier_cost_confirmation_queue")
        write_o_contract_df(root_path, "supplier_cost_confirmation_queue", out_df)
        print({"status": "success", "rows": 0, "snapshot": str(out_path)})
        return out_df

    queue_rows: list[dict[str, str]] = []
    for _, row in truth_df.iterrows():
        if not _needs_confirmation(row):
            continue
        queue_rows.append(
            {
                "queue_utc": timestamp_utc,
                "seller_sku": _normalize_text(row.get("seller_sku", "")),
                "asin": _normalize_text(row.get("asin", "")),
                "title": _normalize_text(row.get("title", "")),
                "supplier_code": _normalize_text(row.get("supplier_code", "")),
                "supplier_name": _normalize_text(row.get("supplier_name", "")),
                "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                "barcode": _normalize_text(row.get("barcode", "")),
                "price_list_unit_cost_gbp": _normalize_text(row.get("price_list_unit_cost_gbp", "")),
                "purchase_reference_list_cost_gbp": _normalize_text(row.get("purchase_reference_list_cost_gbp", "")),
                "actual_paid_unit_cost_gbp": _normalize_text(row.get("actual_paid_unit_cost_gbp", "")),
                "actual_vs_list_ratio": _normalize_text(row.get("actual_vs_list_ratio", "")),
                "discount_assumption_pct": _normalize_text(row.get("discount_assumption_pct", "")),
                "expected_next_unit_cost_gbp": _normalize_text(row.get("expected_next_unit_cost_gbp", "")),
                "confirmation_status": "needs_user_price_check",
                "review_reason": _normalize_text(row.get("review_reason", "")),
                "user_prompt": _prompt_for(row),
                "source_lineage": _normalize_text(row.get("source_lineage", "")),
                "price_list_source_batch_id": _normalize_text(row.get("price_list_source_batch_id", "")),
                "price_list_source_received_at_utc": _normalize_text(row.get("price_list_source_received_at_utc", "")),
                "expected_cost_source": _normalize_text(row.get("expected_cost_source", "")),
                "cost_confidence": _normalize_text(row.get("cost_confidence", "")),
            }
        )

    out_df = pd.DataFrame(queue_rows)
    out_df = write_o_contract_df(root_path, "supplier_cost_confirmation_queue", out_df)
    print({"status": "success", "rows": len(out_df), "snapshot": str(out_path)})
    return out_df


def main() -> None:
    parser = argparse.ArgumentParser(description="Build O supplier cost confirmation queue.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--queue-utc", default=None)
    args = parser.parse_args()
    build_supplier_cost_confirmation_queue(
        root=Path(args.root) if args.root else None,
        queue_utc=args.queue_utc,
    )


if __name__ == "__main__":
    main()
