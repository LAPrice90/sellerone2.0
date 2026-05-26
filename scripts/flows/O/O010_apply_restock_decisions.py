from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.flows.O._contract_io import empty_o_contract_df, read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract
from scripts.flows.O._schemas import get_o_output_contract


SUPPORTED_ACTIONS = {
    "approve_full_restock",
    "approve_test_restock",
    "wait",
    "snooze",
    "skip",
    "bulk_review",
}
COMMIT_ACTIONS = {"approve_full_restock", "approve_test_restock"}

ROI_FULL_THRESHOLD = 15.0
ROI_TEST_THRESHOLD = 10.0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _num(value: object) -> float | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return None


def _num_text(value: float | None) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


def _parse_utc(value: object) -> datetime | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    parsed = pd.to_datetime(raw, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    return df


def _empty_contract_df(contract_name: str) -> pd.DataFrame:
    return empty_o_contract_df(contract_name)


def _read_or_init_csv(root_path: Path, contract_name: str) -> pd.DataFrame:
    return read_o_contract_df(root_path, contract_name)


def _uses_legacy_purchase_list_source(value: object) -> bool:
    return "legacy_purchase_list" in _normalize_text(value).lower()


def _bridge_to_recommendation(row: pd.Series) -> pd.Series:
    recommended_qty = _normalize_text(row.get("recommended_qty_rounded", "")) or _normalize_text(row.get("suggested_qty", ""))
    bridge_note = _normalize_text(row.get("bridge_note", ""))
    reason_codes = _normalize_text(row.get("reason_codes", "")) or bridge_note
    market_price = _normalize_text(row.get("market_price_gbp", "")) or _normalize_text(row.get("suggested_market_price_gbp", ""))
    return pd.Series(
        {
            "asof_utc": _normalize_text(row.get("bridge_utc", "")),
            "seller_sku": _normalize_text(row.get("seller_sku", "")),
            "asin": _normalize_text(row.get("asin", "")),
            "supplier_code": _normalize_text(row.get("supplier_code", "")),
            "supplier_name": _normalize_text(row.get("supplier_name", "")),
            "recommendation_status": _normalize_text(row.get("recommendation_status", "")),
            "reason_codes": reason_codes,
            "recommended_qty_raw": recommended_qty,
            "recommended_qty_rounded": recommended_qty,
            "target_days_cover": "",
            "days_cover_available_only": _normalize_text(row.get("days_cover_available_only", "")),
            "days_cover_total_pipeline": _normalize_text(row.get("days_cover_available_only", "")),
            "current_supplier_buy_cost_gbp": _normalize_text(row.get("current_supplier_buy_cost_gbp", "")),
            "current_supplier_cost_source": _normalize_text(row.get("current_supplier_cost_source", "")) or "legacy_purchase_list_cpu",
            "market_price_gbp": market_price,
            "market_price_basis_used": _normalize_text(row.get("market_price_basis_used", "")),
            "forward_roi_pct": _normalize_text(row.get("forward_roi_pct", "")) or _normalize_text(row.get("expected_forward_roi_pct", "")),
            "forward_profit_per_unit_gbp": _normalize_text(row.get("forward_profit_per_unit_gbp", "")),
            "cost_mode": _normalize_text(row.get("cost_mode", "")) or "legacy_sheet",
            "recommendation_basis": _normalize_text(row.get("recommendation_basis", "")),
        }
    )


def _lookup_row(
    event: pd.Series,
    by_sku: dict[str, pd.Series],
    by_asin: dict[str, pd.Series],
) -> pd.Series | None:
    sku = _normalize_key(event.get("seller_sku", ""))
    asin = _normalize_key(event.get("asin", ""))
    if sku and sku in by_sku:
        return by_sku[sku]
    if asin and asin in by_asin:
        return by_asin[asin]
    return None


def _resolve_recommendation(
    event: pd.Series,
    by_sku: dict[str, pd.Series],
    by_asin: dict[str, pd.Series],
    bridge_by_sku: dict[str, pd.Series],
    bridge_by_asin: dict[str, pd.Series],
) -> pd.Series | None:
    bridge_row = _lookup_row(event, bridge_by_sku, bridge_by_asin)
    native_row = _lookup_row(event, by_sku, by_asin)
    if _uses_legacy_purchase_list_source(event.get("source_reference", "")) and bridge_row is not None:
        return _bridge_to_recommendation(bridge_row)
    if native_row is not None:
        return native_row
    if bridge_row is not None:
        return _bridge_to_recommendation(bridge_row)
    return None


def _extract_refund_drag(rec: pd.Series) -> float:
    market = _num(rec.get("market_price_gbp", ""))
    cost = _num(rec.get("current_supplier_buy_cost_gbp", ""))
    forward_profit = _num(rec.get("forward_profit_per_unit_gbp", ""))
    if market is None or cost is None or forward_profit is None:
        return 0.0
    drag = market - cost - forward_profit
    if drag < 0:
        return 0.0
    return drag


def _recalc_roi(rec: pd.Series, confirmed_cost: float | None) -> float | None:
    market = _num(rec.get("market_price_gbp", ""))
    if confirmed_cost is None or confirmed_cost <= 0 or market is None or market <= 0:
        return None
    refund_drag = _extract_refund_drag(rec)
    profit = market - confirmed_cost - refund_drag
    return (profit / confirmed_cost) * 100.0


def _final_status_from_roi(roi_pct: float | None) -> str:
    if roi_pct is None:
        return "wait"
    if roi_pct >= ROI_FULL_THRESHOLD:
        return "full_restock"
    if roi_pct >= ROI_TEST_THRESHOLD:
        return "test_restock"
    return "wait"


def _resolve_max_safe_cost(event: pd.Series, rec: pd.Series | None) -> float | None:
    for value in (
        event.get("max_safe_unit_cost_gbp", ""),
        event.get("target_roi_max_cost_gbp", ""),
        rec.get("max_safe_unit_cost_gbp", "") if rec is not None else "",
        rec.get("max_target_roi_purchase_price_gbp", "") if rec is not None else "",
    ):
        parsed = _num(value)
        if parsed is not None and parsed > 0:
            return parsed
    return None


def apply_restock_decisions(
    root: Path | None = None,
    *,
    applied_utc: str | None = None,
    event_ids: set[str] | list[str] | tuple[str, ...] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    now = _parse_utc(applied_utc) or _utc_now()
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    rec_path = root_path / get_o_output_contract("restock_recommendations_live").rel_path
    inbox_path = root_path / get_o_output_contract("restock_decision_events").rel_path
    log_path = root_path / get_o_output_contract("restock_decisions_log").rel_path

    rec_df = _read_or_init_csv(root_path, "restock_recommendations_live")
    bridge_df = _read_or_init_csv(root_path, "legacy_purchase_list_bridge")
    inbox_df = _read_or_init_csv(root_path, "restock_decision_events")
    existing_log_df = _read_or_init_csv(root_path, "restock_decisions_log")

    # Ensure inbox file exists with schema so operators have a durable intake target.
    if not inbox_path.exists():
        write_o_contract_df(root_path, "restock_decision_events", inbox_df)

    scoped_event_ids = {_normalize_text(value) for value in (event_ids or []) if _normalize_text(value) != ""}
    if scoped_event_ids:
        inbox_df = inbox_df[
            inbox_df.get("event_id", pd.Series(dtype=str)).map(lambda value: _normalize_text(value) in scoped_event_ids)
        ].copy()

    rec_df = _ensure_columns(rec_df, ["seller_sku", "asin"])
    bridge_df = _ensure_columns(bridge_df, ["seller_sku", "asin"])
    by_sku: dict[str, pd.Series] = {}
    by_asin: dict[str, pd.Series] = {}
    for _, rec in rec_df.iterrows():
        sku = _normalize_key(rec.get("seller_sku", ""))
        asin = _normalize_key(rec.get("asin", ""))
        if sku and sku not in by_sku:
            by_sku[sku] = rec
        if asin and asin not in by_asin:
            by_asin[asin] = rec
    bridge_by_sku: dict[str, pd.Series] = {}
    bridge_by_asin: dict[str, pd.Series] = {}
    for _, bridge in bridge_df.iterrows():
        if _normalize_text(bridge.get("bridge_status", "")).lower() not in {"", "ready"}:
            continue
        sku = _normalize_key(bridge.get("seller_sku", ""))
        asin = _normalize_key(bridge.get("asin", ""))
        if sku and sku not in bridge_by_sku:
            bridge_by_sku[sku] = bridge
        if asin and asin not in bridge_by_asin:
            bridge_by_asin[asin] = bridge

    existing_event_ids = {
        _normalize_text(v)
        for v in existing_log_df.get("event_id", pd.Series(dtype=str)).astype(str).tolist()
        if _normalize_text(v) != ""
    }

    append_rows: list[dict[str, str]] = []
    seen_new_event_ids: set[str] = set()
    for _, event in inbox_df.iterrows():
        event_id = _normalize_text(event.get("event_id", ""))
        if event_id == "":
            continue
        if event_id in existing_event_ids or event_id in seen_new_event_ids:
            continue
        seen_new_event_ids.add(event_id)

        action = _normalize_text(event.get("action", "")).lower()
        rec = _resolve_recommendation(event, by_sku, by_asin, bridge_by_sku, bridge_by_asin)

        original_status = _normalize_text(rec.get("recommendation_status", "")) if rec is not None else ""
        original_reason = _normalize_text(rec.get("reason_codes", "")) if rec is not None else ""
        original_qty = _normalize_text(rec.get("recommended_qty_rounded", "")) if rec is not None else ""
        original_roi = _normalize_text(rec.get("forward_roi_pct", "")) if rec is not None else ""
        original_market = _normalize_text(rec.get("market_price_gbp", "")) if rec is not None else ""
        original_refund_drag = _num_text(_extract_refund_drag(rec)) if rec is not None else ""

        seller_sku = _normalize_text(event.get("seller_sku", "")) or (_normalize_text(rec.get("seller_sku", "")) if rec is not None else "")
        asin = _normalize_text(event.get("asin", "")) or (_normalize_text(rec.get("asin", "")) if rec is not None else "")
        actor = _normalize_text(event.get("actor", ""))
        decision_note = _normalize_text(event.get("decision_note", ""))
        source_reference = _normalize_text(event.get("source_reference", ""))
        profit_verdict = _normalize_text(event.get("profit_verdict", ""))
        profit_proof_source = _normalize_text(event.get("profit_proof_source", ""))
        profit_check_reference = _normalize_text(event.get("profit_check_reference", ""))
        max_safe_cost = _resolve_max_safe_cost(event, rec)
        current_price_list_cost = _normalize_text(event.get("current_price_list_unit_cost_gbp", ""))
        usual_paid_cost = _normalize_text(event.get("usual_paid_unit_cost_gbp", ""))
        price_list_change_status = _normalize_text(event.get("price_list_change_status", ""))
        confirmed_price_safety_status = _normalize_text(event.get("confirmed_price_safety_status", ""))
        confirmed_vs_max_delta = _normalize_text(event.get("confirmed_vs_max_delta_gbp", ""))
        price_status = _normalize_text(event.get("price_status", ""))
        price_status_message = _normalize_text(event.get("price_status_message", ""))
        recommended_snooze_until = _normalize_text(event.get("recommended_snooze_until_utc", ""))
        event_utc = _normalize_text(event.get("event_utc", "")) or now_iso

        cost_mode = _normalize_text(event.get("cost_mode", ""))
        recommendation_basis = ""
        if rec is not None:
            if cost_mode == "":
                cost_mode = _normalize_text(rec.get("cost_mode", ""))
            recommendation_basis = _normalize_text(rec.get("recommendation_basis", ""))
        if cost_mode == "":
            cost_mode = "live"

        confirmed_cost_raw = _normalize_text(event.get("confirmed_unit_cost", ""))
        confirmed_qty_raw = _normalize_text(event.get("confirmed_qty", ""))
        confirmed_cost = _num(confirmed_cost_raw)
        confirmed_qty_num = _num(confirmed_qty_raw)
        if confirmed_qty_num is None and rec is not None and action in COMMIT_ACTIONS:
            confirmed_qty_num = _num(rec.get("recommended_qty_rounded", ""))
        confirmed_qty = int(round(confirmed_qty_num)) if confirmed_qty_num is not None else 0
        if confirmed_qty < 0:
            confirmed_qty = 0

        snooze_until_utc = _normalize_text(event.get("snooze_until_utc", ""))
        decision_result_note = ""
        recalculated_roi = None
        final_status = ""
        if action in COMMIT_ACTIONS and confirmed_cost is not None and max_safe_cost is not None:
            over_max_delta = confirmed_cost - max_safe_cost
            if over_max_delta > 0.000001:
                confirmed_price_safety_status = "confirmed_over_max_blocked"
                confirmed_vs_max_delta = _num_text(over_max_delta)

        if action not in SUPPORTED_ACTIONS:
            final_status = "invalid_action"
            decision_result_note = "unsupported_action"
        elif rec is None:
            final_status = "invalid_event"
            decision_result_note = "recommendation_not_found"
        elif action in COMMIT_ACTIONS and (confirmed_cost is None or confirmed_cost <= 0):
            final_status = "invalid_event"
            decision_result_note = "confirmed_unit_cost_required_for_approval"
        elif action in COMMIT_ACTIONS and confirmed_qty <= 0:
            final_status = "invalid_event"
            decision_result_note = "confirmed_qty_required_for_approval"
        elif action in COMMIT_ACTIONS and confirmed_price_safety_status == "confirmed_over_max_blocked":
            final_status = "wait"
            decision_result_note = "confirmed_cost_above_max_safe_cost"
        elif action == "snooze":
            snooze_dt = _parse_utc(snooze_until_utc)
            if snooze_dt is None:
                final_status = "invalid_event"
                decision_result_note = "invalid_snooze_until_utc"
            else:
                final_status = "snooze"
        elif action == "wait":
            final_status = "wait"
        elif action == "skip":
            final_status = "skip"
        elif action == "bulk_review":
            final_status = "bulk_review"
        else:
            if recommendation_basis == "legacy_purchase_list_no_data" and action == "approve_test_restock":
                final_status = "test_restock"
                decision_result_note = "legacy_no_data_test_candidate_no_roi_recalc"
            else:
                recalculated_roi = _recalc_roi(rec, confirmed_cost)
                final_status = _final_status_from_roi(recalculated_roi)
                if final_status != original_status:
                    decision_result_note = "status_changed_after_confirmed_cost_recalc"

        append_rows.append(
            {
                "decision_utc": now_iso,
                "event_utc": event_utc,
                "event_id": event_id,
                "seller_sku": seller_sku,
                "asin": asin,
                "original_recommendation_status": original_status,
                "original_recommendation_reason": original_reason,
                "decision_action": action,
                "final_decision_status": final_status,
                "confirmed_unit_cost": _num_text(confirmed_cost),
                "confirmed_qty": str(confirmed_qty),
                "recalculated_forward_roi_pct": _num_text(recalculated_roi),
                "decision_note": decision_note,
                "snooze_until_utc": snooze_until_utc,
                "actor": actor,
                "cost_mode": cost_mode,
                "recommendation_basis": recommendation_basis,
                "recommendation_asof_utc": _normalize_text(rec.get("asof_utc", "")) if rec is not None else "",
                "source_reference": source_reference,
                "decision_result_note": decision_result_note,
                "original_recommended_qty": original_qty,
                "original_forward_roi_pct": original_roi,
                "original_market_price_gbp": original_market,
                "original_refund_drag_gbp": original_refund_drag,
                "profit_verdict": profit_verdict,
                "profit_proof_source": profit_proof_source,
                "profit_check_reference": profit_check_reference,
                "max_safe_unit_cost_gbp": _num_text(max_safe_cost),
                "current_price_list_unit_cost_gbp": current_price_list_cost,
                "usual_paid_unit_cost_gbp": usual_paid_cost,
                "price_list_change_status": price_list_change_status,
                "confirmed_price_safety_status": confirmed_price_safety_status,
                "confirmed_vs_max_delta_gbp": confirmed_vs_max_delta,
                "price_status": price_status,
                "price_status_message": price_status_message,
                "recommended_snooze_until_utc": recommended_snooze_until,
            }
        )

    append_df = pd.DataFrame(append_rows)
    log_contract = get_o_output_contract("restock_decisions_log")
    ordered_log_cols = [*log_contract.required_columns, *log_contract.optional_columns]
    existing_log_df = _ensure_columns(existing_log_df, ordered_log_cols)
    if not append_df.empty:
        append_df = _ensure_columns(append_df, ordered_log_cols)
    final_log_df = pd.concat([existing_log_df, append_df], ignore_index=True)
    final_log_df = _ensure_columns(final_log_df, ordered_log_cols)

    # Preserve any legacy columns that may already exist in local logs.
    ordered = ordered_log_cols + [c for c in final_log_df.columns if c not in ordered_log_cols]
    final_log_df = final_log_df[ordered]

    log_path.parent.mkdir(parents=True, exist_ok=True)
    write_o_contract_df(root_path, "restock_decisions_log", final_log_df)
    print(
        {
            "status": "success",
            "events_seen": int(len(inbox_df)),
            "events_applied": int(len(append_df)),
            "log_rows": int(len(final_log_df)),
            "event_filter": sorted(scoped_event_ids),
            "snapshot": str(log_path),
        }
    )
    return append_df, final_log_df


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply O restock decision events to the decision log.")
    parser.add_argument(
        "--event-id",
        action="append",
        default=[],
        help="Apply only this event_id. Can be supplied more than once.",
    )
    args = parser.parse_args()
    apply_restock_decisions(event_ids=set(args.event_id))


if __name__ == "__main__":
    main()
