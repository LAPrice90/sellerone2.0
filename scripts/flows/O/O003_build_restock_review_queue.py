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


def _first_reason(reason_codes: str) -> str:
    for token in str(reason_codes or "").split(","):
        item = token.strip()
        if item:
            return item
    return ""


def _queue_status(action: str) -> str:
    if action in {"full_restock", "test_restock"}:
        return "needs_review"
    return "watch_or_wait"


def _parse_utc(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if raw == "":
        return None
    parsed = pd.to_datetime(raw, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def _active_snooze_map(root_path: Path, queue_now: datetime) -> dict[str, str]:
    log_df = read_o_contract_df(root_path, "restock_decisions_log")
    if log_df.empty or "seller_sku" not in log_df.columns:
        return {}
    for col in ("decision_utc", "final_decision_status", "snooze_until_utc"):
        if col not in log_df.columns:
            log_df[col] = ""
    log_df["_decision_ts"] = pd.to_datetime(log_df["decision_utc"], errors="coerce", utc=True)
    log_df = log_df.sort_values(by=["seller_sku", "_decision_ts"], ascending=[True, True], kind="stable")
    latest_by_sku = log_df.groupby("seller_sku", sort=False).tail(1)
    snooze_map: dict[str, str] = {}
    for _, row in latest_by_sku.iterrows():
        if str(row.get("final_decision_status", "")).strip().lower() != "snooze":
            continue
        until_raw = str(row.get("snooze_until_utc", "")).strip()
        until_dt = _parse_utc(until_raw)
        if until_dt is None:
            continue
        if until_dt > queue_now:
            snooze_map[str(row.get("seller_sku", "")).strip()] = until_raw
    return snooze_map


def build_restock_review_queue(
    root: Path | None = None,
    *,
    queue_utc: str | None = None,
    exclude_snoozed: bool = False,
) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    queue_timestamp = queue_utc or _utc_now_iso()
    queue_now = _parse_utc(queue_timestamp) or datetime.now(timezone.utc)

    rec_path = root_path / get_o_output_contract("restock_recommendations_live").rel_path
    queue_contract = get_o_output_contract("restock_review_queue")
    out_path = root_path / queue_contract.rel_path

    rec_df = read_o_contract_df(root_path, "restock_recommendations_live")
    if rec_df.empty:
        out_df = empty_o_contract_df("restock_review_queue")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        write_o_contract_df(root_path, "restock_review_queue", out_df)
        print({"status": "success", "rows": 0, "snapshot": str(out_path)})
        return out_df

    snooze_map = _active_snooze_map(root_path, queue_now)

    queue_rows: list[dict[str, str]] = []
    for _, row in rec_df.iterrows():
        seller_sku = str(row.get("seller_sku", "")).strip()
        action = str(row.get("recommendation_status", "")).strip()
        reasons = str(row.get("reason_codes", "")).strip()
        confidence_note = str(row.get("confidence_note", "")).strip()
        active_snooze_until = snooze_map.get(seller_sku, "")
        is_snoozed = active_snooze_until != ""
        if exclude_snoozed and is_snoozed:
            continue
        queue_rows.append(
            {
                "queue_utc": queue_timestamp,
                "seller_sku": seller_sku,
                "asin": str(row.get("asin", "")).strip(),
                "title": str(row.get("title", "")).strip(),
                "main_image": str(row.get("main_image", "")).strip(),
                "supplier_code": str(row.get("supplier_code", "")).strip(),
                "supplier_name": str(row.get("supplier_name", "")).strip(),
                "recommendation_status": action,
                "suggested_action": action,
                "suggested_qty": str(row.get("recommended_qty_rounded", "")).strip(),
                "suggested_unit_cost_gbp": str(row.get("current_supplier_buy_cost_gbp", "")).strip(),
                "suggested_market_price_gbp": str(row.get("market_price_gbp", "")).strip(),
                "expected_forward_roi_pct": str(row.get("forward_roi_pct", "")).strip(),
                "expected_forward_profit_per_unit_gbp": str(row.get("forward_profit_per_unit_gbp", "")).strip(),
                "days_cover_available_only": str(row.get("days_cover_available_only", "")).strip(),
                "days_cover_total_pipeline": str(row.get("days_cover_total_pipeline", "")).strip(),
                "reason_codes": reasons,
                "key_reason": _first_reason(reasons),
                "confidence_note": confidence_note,
                "queue_status": "snoozed" if is_snoozed else _queue_status(action),
                "supplier_group_key": (
                    f"{str(row.get('supplier_code', '')).strip()}|{str(row.get('supplier_name', '')).strip()}".strip("|")
                ),
                "snooze_until_utc": active_snooze_until or str(row.get("snooze_until_utc", "")).strip(),
                "queue_notes": ("active_snooze" if is_snoozed else (confidence_note or _first_reason(reasons))),
                "cost_mode": str(row.get("cost_mode", "")).strip() or "live",
                "recommendation_basis": str(row.get("recommendation_basis", "")).strip(),
                "max_break_even_purchase_price_gbp": str(row.get("max_break_even_purchase_price_gbp", "")).strip(),
                "max_target_roi_purchase_price_gbp": str(row.get("max_target_roi_purchase_price_gbp", "")).strip(),
                "max_safe_unit_cost_gbp": str(row.get("max_safe_unit_cost_gbp", "")).strip(),
                "target_roi_pct": str(row.get("target_roi_pct", "")).strip(),
                "purchase_price_safety_status": str(row.get("purchase_price_safety_status", "")).strip(),
                "market_price_ex_vat_gbp": str(row.get("market_price_ex_vat_gbp", "")).strip(),
                "market_price_vat_rate_pct": str(row.get("market_price_vat_rate_pct", "")).strip(),
                "current_token_cost_gbp": str(row.get("current_token_cost_gbp", "")).strip(),
                "break_even_price_gbp": str(row.get("break_even_price_gbp", "")).strip(),
                "net_fee_drag_per_unit_gbp": str(row.get("net_fee_drag_per_unit_gbp", "")).strip(),
                "net_fee_model_status": str(row.get("net_fee_model_status", "")).strip(),
                "net_fee_model_asof": str(row.get("net_fee_model_asof", "")).strip(),
                "net_fee_model_age_hours": str(row.get("net_fee_model_age_hours", "")).strip(),
                "net_fee_model_source": str(row.get("net_fee_model_source", "")).strip(),
                "net_fee_model_notes": str(row.get("net_fee_model_notes", "")).strip(),
                "gross_forward_roi_pct": str(row.get("gross_forward_roi_pct", "")).strip(),
                "gross_forward_profit_per_unit_gbp": str(row.get("gross_forward_profit_per_unit_gbp", "")).strip(),
                "user_price_check_required": str(row.get("user_price_check_required", "")).strip(),
                "supplier_cost_review_reason": str(row.get("supplier_cost_review_reason", "")).strip(),
                "expected_next_unit_cost_gbp": str(row.get("expected_next_unit_cost_gbp", "")).strip(),
                "price_list_unit_cost_gbp": str(row.get("price_list_unit_cost_gbp", "")).strip(),
                "actual_paid_unit_cost_gbp": str(row.get("actual_paid_unit_cost_gbp", "")).strip(),
                "usual_paid_unit_cost_gbp": str(row.get("usual_paid_unit_cost_gbp", "")).strip(),
                "usual_paid_cost_basis": str(row.get("usual_paid_cost_basis", "")).strip(),
                "usual_paid_cost_confidence": str(row.get("usual_paid_cost_confidence", "")).strip(),
                "usual_paid_sample_count": str(row.get("usual_paid_sample_count", "")).strip(),
                "usual_paid_discount_vs_list_pct": str(row.get("usual_paid_discount_vs_list_pct", "")).strip(),
                "usual_paid_vs_list_delta_gbp": str(row.get("usual_paid_vs_list_delta_gbp", "")).strip(),
                "price_list_change_status": str(row.get("price_list_change_status", "")).strip(),
                "price_list_previous_unit_cost_gbp": str(row.get("price_list_previous_unit_cost_gbp", "")).strip(),
                "price_list_previous_pack_size": str(row.get("price_list_previous_pack_size", "")).strip(),
                "price_list_previous_seen_at_utc": str(row.get("price_list_previous_seen_at_utc", "")).strip(),
                "price_list_change_delta_gbp": str(row.get("price_list_change_delta_gbp", "")).strip(),
                "price_list_change_pct": str(row.get("price_list_change_pct", "")).strip(),
                "is_snoozed": "1" if is_snoozed else "0",
            }
        )

    out_df = pd.DataFrame(queue_rows)
    status_order = {"full_restock": 0, "test_restock": 1, "wait": 2}
    out_df["_order"] = out_df["recommendation_status"].map(lambda x: status_order.get(str(x), 99))
    out_df = out_df.sort_values(
        by=["supplier_group_key", "_order", "seller_sku"],
        kind="stable",
    ).drop(columns=["_order"])

    for col in [*queue_contract.required_columns, *queue_contract.optional_columns]:
        if col not in out_df.columns:
            out_df[col] = ""

    ordered_cols = [*queue_contract.required_columns, *queue_contract.optional_columns]
    extra_cols = [c for c in out_df.columns if c not in ordered_cols]
    out_df = out_df[ordered_cols + extra_cols]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_o_contract_df(root_path, "restock_review_queue", out_df)
    print({"status": "success", "rows": len(out_df), "snapshot": str(out_path)})
    return out_df


def main() -> None:
    parser = argparse.ArgumentParser(description="Build O restock review queue.")
    parser.add_argument(
        "--exclude-snoozed",
        action="store_true",
        help="Exclude rows that have an active snooze decision in restock_decisions_log.",
    )
    parser.add_argument(
        "--queue-utc",
        default=None,
        help="Optional fixed queue timestamp (UTC ISO).",
    )
    args = parser.parse_args()
    build_restock_review_queue(
        queue_utc=args.queue_utc,
        exclude_snoozed=args.exclude_snoozed,
    )


if __name__ == "__main__":
    main()
