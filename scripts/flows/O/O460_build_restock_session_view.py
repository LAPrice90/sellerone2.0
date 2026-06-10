from __future__ import annotations

import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BOOT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT))

from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract


SESSION_ID = "o_restock_session_v1"
SOURCE_CLASSES = {"native_o", "legacy_bridge", "feeder_review_handoff", "manual_walkthrough_fixture"}
PROTECTED_ACTION_COLUMNS = {
    "creates_live_action": "0",
}
WEAK_INBOUND_COST_CONFIDENCE_STATES = {
    "",
    "missing",
    "unknown",
    "weak",
    "not_yet_proven",
    "missing_inbound_cost_confidence",
    "unsupported_currency",
}
WEAK_PROFIT_INPUT_CONFIDENCE_STATES = {
    "",
    "missing_profit_inputs",
    "weak_profit_inputs",
    "unknown",
    "not_yet_proven",
}
DRAFT_DECISION_CONTRACT = "restock_session_draft_decision_events"
DECISION_REASON_ROWS = [
    {
        "reason_code": "order_qty_draft",
        "reason_label": "Draft order quantity",
        "decision_family": "draft_order_review",
        "safe_to_draft": "1",
        "creates_live_action": "0",
        "requires_luke": "0",
        "notes": "Local session draft only; does not create a purchase order.",
    },
    {
        "reason_code": "snooze",
        "reason_label": "Snooze",
        "decision_family": "wait",
        "safe_to_draft": "1",
        "creates_live_action": "0",
        "requires_luke": "0",
        "notes": "Local review state only.",
    },
    {
        "reason_code": "drop",
        "reason_label": "Drop",
        "decision_family": "reject",
        "safe_to_draft": "1",
        "creates_live_action": "0",
        "requires_luke": "0",
        "notes": "Local draft reason only; Product DB is not updated by this builder.",
    },
    {
        "reason_code": "likely_discontinued",
        "reason_label": "Likely discontinued",
        "decision_family": "supplier_state",
        "safe_to_draft": "1",
        "creates_live_action": "0",
        "requires_luke": "0",
        "notes": "Candidate state only; final discontinue decision remains protected.",
    },
    {
        "reason_code": "needs_fresh_supplier_scan",
        "reason_label": "Needs fresh supplier scan",
        "decision_family": "supplier_state",
        "safe_to_draft": "1",
        "creates_live_action": "0",
        "requires_luke": "0",
        "notes": "Blocks clean buy wording until supplier proof is fresh.",
    },
    {
        "reason_code": "backorder_wait",
        "reason_label": "Backorder wait",
        "decision_family": "supplier_state",
        "safe_to_draft": "1",
        "creates_live_action": "0",
        "requires_luke": "0",
        "notes": "Backorder state must be proved before ordering.",
    },
    {
        "reason_code": "already_ordered_or_paid",
        "reason_label": "Already ordered or paid",
        "decision_family": "ordered_state",
        "safe_to_draft": "1",
        "creates_live_action": "0",
        "requires_luke": "0",
        "notes": "Prevents duplicate buying while supplier shipment is pending.",
    },
    {
        "reason_code": "awaiting_supplier_shipment",
        "reason_label": "Awaiting supplier shipment",
        "decision_family": "ordered_state",
        "safe_to_draft": "1",
        "creates_live_action": "0",
        "requires_luke": "0",
        "notes": "Review state only.",
    },
    {
        "reason_code": "supplier_moq_too_low",
        "reason_label": "Supplier MOQ too low",
        "decision_family": "order_viability",
        "safe_to_draft": "1",
        "creates_live_action": "0",
        "requires_luke": "0",
        "notes": "Supplier order value or pack rule prevents a clean order draft.",
    },
    {
        "reason_code": "profit_too_low",
        "reason_label": "Profit too low",
        "decision_family": "profit",
        "safe_to_draft": "1",
        "creates_live_action": "0",
        "requires_luke": "0",
        "notes": "Profit floor blocks clean buy wording.",
    },
    {
        "reason_code": "proof_missing",
        "reason_label": "Proof missing",
        "decision_family": "proof",
        "safe_to_draft": "1",
        "creates_live_action": "0",
        "requires_luke": "0",
        "notes": "Missing proof must remain visible and cannot be treated as zero.",
    },
]
ALLOWED_DRAFT_DECISION_CODES = {row["reason_code"] for row in DECISION_REASON_ROWS}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _safe_fragment(value: object) -> str:
    text = _normalize_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "unknown"


def _num(value: object) -> float | None:
    text = _normalize_text(value)
    if text == "":
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _num_text(value: float | None) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _positive_whole_number_text(value: object) -> str:
    number = _num(value)
    if number is None or number <= 0 or not float(number).is_integer():
        return ""
    return str(int(number))


def _first_non_blank(*values: object) -> str:
    for value in values:
        text = _normalize_text(value)
        if text:
            return text
    return ""


def _row_maps(df: pd.DataFrame) -> tuple[dict[str, pd.Series], dict[str, pd.Series]]:
    by_sku: dict[str, pd.Series] = {}
    by_asin: dict[str, pd.Series] = {}
    if df.empty:
        return by_sku, by_asin
    for _, row in df.iterrows():
        sku = _normalize_key(row.get("seller_sku", ""))
        asin = _normalize_key(row.get("asin", ""))
        if sku and sku not in by_sku:
            by_sku[sku] = row
        if asin and asin not in by_asin:
            by_asin[asin] = row
    return by_sku, by_asin


def _lookup(row: pd.Series, by_sku: dict[str, pd.Series], by_asin: dict[str, pd.Series]) -> pd.Series | None:
    sku = _normalize_key(row.get("seller_sku", ""))
    asin = _normalize_key(row.get("asin", ""))
    if sku and sku in by_sku:
        return by_sku[sku]
    if asin and asin in by_asin:
        return by_asin[asin]
    return None


def _candidate_source_rows(bridge_df: pd.DataFrame, queue_df: pd.DataFrame, rec_df: pd.DataFrame) -> list[tuple[str, pd.Series]]:
    rows: list[tuple[str, pd.Series]] = []
    covered_skus: set[str] = set()
    covered_asins: set[str] = set()

    if not bridge_df.empty:
        work = bridge_df.copy()
        for col in ("bridge_status", "done_flag", "seller_sku", "asin"):
            if col not in work.columns:
                work[col] = ""
        ready_mask = work["bridge_status"].map(lambda value: _normalize_text(value).lower() in {"", "ready"})
        done_mask = work["done_flag"].map(lambda value: _normalize_text(value).lower() in {"1", "true", "yes", "y"})
        for _, row in work[ready_mask & ~done_mask].iterrows():
            sku = _normalize_key(row.get("seller_sku", ""))
            asin = _normalize_key(row.get("asin", ""))
            if not sku and not asin:
                continue
            rows.append(("legacy_bridge", row))
            if sku:
                covered_skus.add(sku)
            if asin:
                covered_asins.add(asin)

    native_df = queue_df if not queue_df.empty else rec_df
    if not native_df.empty:
        for _, row in native_df.iterrows():
            sku = _normalize_key(row.get("seller_sku", ""))
            asin = _normalize_key(row.get("asin", ""))
            if not sku and not asin:
                continue
            if (sku and sku in covered_skus) or (asin and asin in covered_asins):
                continue
            rows.append(("native_o", row))
    return rows


def _field(primary: pd.Series, *rows: pd.Series | None, columns: tuple[str, ...]) -> str:
    for column in columns:
        value = _normalize_text(primary.get(column, ""))
        if value:
            return value
    for row in rows:
        if row is None:
            continue
        for column in columns:
            value = _normalize_text(row.get(column, ""))
            if value:
                return value
    return ""


def _supplier_match_state(source_class: str, source_row: pd.Series | None, profit_row: pd.Series | None) -> str:
    match_method = _first_non_blank(
        source_row.get("cost_match_method", "") if source_row is not None else "",
        profit_row.get("cost_match_method", "") if profit_row is not None else "",
    ).lower()
    review_reason = _first_non_blank(
        source_row.get("supplier_cost_review_reason", "") if source_row is not None else "",
        profit_row.get("supplier_cost_review_reason", "") if profit_row is not None else "",
    ).lower()
    if "supplier_sku" in match_method or "barcode" in match_method:
        return "exact_supplier_sku_or_barcode_match"
    if "title" in match_method:
        return "title_only_match_review_required"
    if "missing" in review_reason or "not_found" in review_reason:
        return "missing_from_latest_supplier_file"
    if source_class == "legacy_bridge":
        return "legacy_bridge_not_native_supplier_truth"
    return "not_verified"


def _supplier_cost_state(source_class: str, cost: str, source_row: pd.Series | None, profit_row: pd.Series | None) -> str:
    match_state = _supplier_match_state(source_class, source_row, profit_row)
    if cost == "":
        return "missing_supplier_cost"
    if source_class == "legacy_bridge":
        return "bridge_cost_only"
    if match_state == "exact_supplier_sku_or_barcode_match":
        return "supplier_cost_verified"
    return "supplier_cost_not_exact"


def _market_price_state(source_class: str, price: str, price_basis: str) -> str:
    basis = price_basis.lower()
    if price == "":
        return "missing_current_market_price"
    if source_class == "legacy_bridge" or any(token in basis for token in ("legacy", "sheet", "backsolve")):
        return "bridge_market_only"
    return "market_price_verified"


def _fee_state(source_row: pd.Series | None, profit_row: pd.Series | None) -> str:
    status = _first_non_blank(
        source_row.get("net_fee_model_status", "") if source_row is not None else "",
        profit_row.get("net_fee_model_status", "") if profit_row is not None else "",
    ).lower()
    if status in {"fresh", "ok", "current"}:
        return "fee_proof_verified"
    if status:
        return f"fee_proof_{status}"
    return "missing_fee_proof"


def _refund_state(source_row: pd.Series | None) -> str:
    proof = _normalize_text(source_row.get("refund_proof_state", "") if source_row is not None else "").lower()
    confidence = _normalize_text(source_row.get("refund_sample_confidence", "") if source_row is not None else "").lower()
    if proof and proof not in {"missing", "unknown", "weak"} and confidence not in {"", "missing", "unknown", "weak"}:
        return proof
    return "missing_refund_confidence"


def _inbound_cost_state(source_row: pd.Series | None, profit_row: pd.Series | None) -> str:
    confidence = _first_non_blank(
        source_row.get("inbound_cost_confidence", "") if source_row is not None else "",
        profit_row.get("inbound_cost_confidence", "") if profit_row is not None else "",
    ).lower()
    cost = _first_non_blank(
        source_row.get("expected_inbound_cost_per_unit_gbp", "") if source_row is not None else "",
        profit_row.get("inbound_cost_drag_gbp", "") if profit_row is not None else "",
    )
    if confidence in WEAK_INBOUND_COST_CONFIDENCE_STATES:
        return "missing_inbound_cost_confidence"
    if cost:
        return "inbound_cost_verified"
    return "missing_inbound_cost_confidence"


def _profit_input_state(source_row: pd.Series | None, profit_row: pd.Series | None) -> str:
    confidence = _first_non_blank(
        source_row.get("profit_input_confidence", "") if source_row is not None else "",
        profit_row.get("profit_input_confidence", "") if profit_row is not None else "",
    ).lower()
    if confidence in WEAK_PROFIT_INPUT_CONFIDENCE_STATES:
        return confidence or "missing_profit_inputs"
    return confidence or "missing_profit_inputs"


def _token_cost_trust_state(source_row: pd.Series | None, profit_row: pd.Series | None) -> str:
    state = _first_non_blank(
        source_row.get("token_cost_trust_state", "") if source_row is not None else "",
        profit_row.get("token_cost_trust_state", "") if profit_row is not None else "",
    ).lower()
    return state or "not_verified"


def _demand_confidence(primary: pd.Series, source_row: pd.Series | None, profit_row: pd.Series | None) -> str:
    velocity = _num(
        _field(
            primary,
            source_row,
            profit_row,
            columns=("velocity_30d", "demand_units_per_day"),
        )
    )
    if velocity is not None and velocity > 0:
        return "own_sales_velocity_available"
    if _field(primary, source_row, profit_row, columns=("backtest_history_confidence", "demand_status")):
        return "market_or_history_clue_only"
    return "missing_demand_proof"


def _pack_state(source_row: pd.Series | None) -> tuple[str, str, str, str]:
    pack = _first_non_blank(
        source_row.get("price_list_pack_size", "") if source_row is not None else "",
        source_row.get("sell_pack_qty", "") if source_row is not None else "",
        source_row.get("supplier_case_qty", "") if source_row is not None else "",
    )
    moq = _first_non_blank(
        source_row.get("price_list_moq", "") if source_row is not None else "",
        source_row.get("moq", "") if source_row is not None else "",
    )
    step = _first_non_blank(
        source_row.get("valid_order_step", "") if source_row is not None else "",
        pack,
        "1",
    )
    if pack or moq or step:
        return "pack_or_moq_visible", pack or "1", moq, step or "1"
    return "pack_moq_not_verified", "", "", ""


def _supplier_order_viability(qty: str, cost: str, moq: str, step: str) -> tuple[str, str, str]:
    qty_num = _num(qty)
    cost_num = _num(cost)
    moq_num = _num(moq)
    step_num = _num(step)
    if qty_num is None or qty_num <= 0:
        return "unknown_no_order_qty", "", "proof_missing"
    value = qty_num * cost_num if cost_num is not None else None
    if moq_num is not None and moq_num > 0 and qty_num < moq_num:
        return "blocked_supplier_moq_too_low", _num_text(value), "supplier_moq_too_low"
    if step_num is not None and step_num > 1 and qty_num % step_num != 0:
        return "blocked_order_step_not_multiple", _num_text(value), "supplier_moq_too_low"
    if cost_num is None:
        return "unknown_missing_cost", "", "proof_missing"
    return "review_only_not_po", _num_text(value), ""


def _safety_state(
    *,
    source_class: str,
    supplier_cost_state: str,
    market_state: str,
    fee_state: str,
    refund_state: str,
    inbound_state: str,
    token_cost_state: str,
    profit_input_state: str,
    profit_verdict: str,
    order_viability_reason: str,
) -> tuple[str, str, str]:
    blockers: list[str] = []
    if source_class != "native_o":
        blockers.append(f"{source_class}_not_native_truth")
    for label, state in (
        ("supplier_cost", supplier_cost_state),
        ("market_price", market_state),
        ("fee", fee_state),
        ("refund", refund_state),
        ("inbound_cost", inbound_state),
        ("token_cost", token_cost_state),
    ):
        if (
            state != "trusted"
            and (
                label == "token_cost"
                or state.startswith("missing")
                or state.startswith("bridge")
                or state.endswith("not_verified")
                or "unknown" in state
            )
        ):
            blockers.append(f"{label}:{state}")
    if profit_input_state in WEAK_PROFIT_INPUT_CONFIDENCE_STATES or profit_input_state.startswith("missing"):
        blockers.append(f"profit_inputs:{profit_input_state or 'missing_profit_inputs'}")
    if profit_verdict in {"do_not_buy_now", "drop_review_only", "temporary_market_risk"}:
        blockers.append(f"profit:{profit_verdict}")
    if order_viability_reason:
        blockers.append(f"order:{order_viability_reason}")
    if blockers:
        if any("profit:" in blocker for blocker in blockers):
            decision_state = "profit_too_low"
        elif any("supplier_cost:missing" in blocker or "supplier_cost:supplier_cost_not_exact" in blocker for blocker in blockers):
            decision_state = "needs_fresh_supplier_scan"
        else:
            decision_state = "proof_missing"
        return "blocked_from_clean_buy", "|".join(blockers), decision_state
    return "clean_review_ready_not_po", "", "order_qty_draft"


def _build_review_row(
    *,
    session_utc: str,
    source_class: str,
    primary: pd.Series,
    source_row: pd.Series | None,
    rec_row: pd.Series | None,
    profit_row: pd.Series | None,
) -> dict[str, str]:
    supplier_name = _field(primary, source_row, rec_row, columns=("supplier_name",))
    supplier_code = _field(primary, source_row, rec_row, columns=("supplier_code",))
    seller_sku = _field(primary, source_row, rec_row, profit_row, columns=("seller_sku",))
    asin = _field(primary, source_row, rec_row, profit_row, columns=("asin",))
    title = _field(primary, source_row, rec_row, columns=("title",))
    supplier_sku = _field(primary, source_row, rec_row, columns=("supplier_sku", "supply_code"))
    barcode = _field(primary, source_row, rec_row, columns=("barcode",))
    suggested_action = _field(primary, rec_row, profit_row, columns=("suggested_action", "recommendation_status"))
    suggested_qty = _field(primary, rec_row, profit_row, columns=("suggested_qty", "recommended_qty_rounded", "recommended_qty"))
    cost = _field(
        primary,
        source_row,
        rec_row,
        profit_row,
        columns=("current_supplier_buy_cost_gbp", "suggested_unit_cost_gbp", "supplier_cost_gbp", "price_list_unit_cost_gbp"),
    )
    price = _field(primary, source_row, rec_row, profit_row, columns=("market_price_gbp", "suggested_market_price_gbp", "current_sell_price_gbp"))
    price_basis = _field(primary, source_row, rec_row, profit_row, columns=("market_price_basis_used", "sell_price_basis"))
    supplier_match = _supplier_match_state(source_class, source_row, profit_row)
    supplier_cost_state = _supplier_cost_state(source_class, cost, source_row, profit_row)
    market_state = _market_price_state(source_class, price, price_basis)
    fee_state = _fee_state(source_row, profit_row)
    refund_state = _refund_state(source_row)
    inbound_state = _inbound_cost_state(source_row, profit_row)
    token_cost_state = _token_cost_trust_state(source_row, profit_row)
    profit_input_state = _profit_input_state(source_row, profit_row)
    demand_confidence = _demand_confidence(primary, source_row, profit_row)
    pack_state, pack_multiple, moq, step = _pack_state(source_row)
    viability, order_value, viability_reason = _supplier_order_viability(suggested_qty, cost, moq, step)
    profit_verdict = _field(primary, profit_row, columns=("profit_verdict",))
    action_safety, block_reason, decision_state = _safety_state(
        source_class=source_class,
        supplier_cost_state=supplier_cost_state,
        market_state=market_state,
        fee_state=fee_state,
        refund_state=refund_state,
        inbound_state=inbound_state,
        token_cost_state=token_cost_state,
        profit_input_state=profit_input_state,
        profit_verdict=profit_verdict,
        order_viability_reason=viability_reason,
    )
    supplier_file_asof = _field(primary, source_row, profit_row, columns=("price_list_source_received_at_utc", "source_offer_timestamp_utc"))
    source_system = _field(primary, columns=("source_system",)) or ("legacy_purchase_list" if source_class == "legacy_bridge" else "native_o")
    source_reference = _field(primary, columns=("source_reference",)) or f"{source_class}:{seller_sku or asin}"
    supplier_proof_state = "supplier_exact_match_proved" if supplier_match == "exact_supplier_sku_or_barcode_match" else supplier_match
    supplier_stock_state = "supplier_stock_not_verified"
    backorder_state = "backorder_not_verified"

    if supplier_match == "missing_from_latest_supplier_file":
        decision_state = "likely_discontinued"
        if block_reason:
            block_reason = f"{block_reason}|supplier:likely_discontinued_candidate"
        else:
            block_reason = "supplier:likely_discontinued_candidate"

    return {
        "session_utc": session_utc,
        "session_id": SESSION_ID,
        "row_id": f"{SESSION_ID}:{_safe_fragment(source_class)}:{_safe_fragment(supplier_name)}:{_safe_fragment(seller_sku or asin)}",
        "source_class": source_class,
        "source_system": source_system,
        "source_reference": source_reference,
        "supplier_name": supplier_name,
        "supplier_code": supplier_code,
        "seller_sku": seller_sku,
        "asin": asin,
        "title": title,
        "supplier_sku": supplier_sku,
        "barcode": barcode,
        "suggested_action": suggested_action,
        "old_suggested_qty": suggested_qty,
        "order_qty_draft": "",
        "current_supplier_cost_gbp": cost,
        "current_amazon_price_gbp": price,
        "expected_profit_per_unit_gbp": _field(primary, rec_row, profit_row, columns=("expected_forward_profit_per_unit_gbp", "forward_profit_per_unit_gbp")),
        "expected_roi_pct": _field(primary, rec_row, profit_row, columns=("expected_forward_roi_pct", "forward_roi_pct")),
        "supplier_proof_state": supplier_proof_state,
        "supplier_match_state": supplier_match,
        "supplier_stock_state": supplier_stock_state,
        "backorder_state": backorder_state,
        "supplier_file_asof_utc": supplier_file_asof,
        "supplier_cost_proof_state": supplier_cost_state,
        "market_price_proof_state": market_state,
        "fee_proof_state": fee_state,
        "refund_proof_state": refund_state,
        "inbound_cost_proof_state": inbound_state,
        "token_cost_trust_state": token_cost_state,
        "demand_confidence": demand_confidence,
        "pack_moq_proof_state": pack_state,
        "pack_multiple": pack_multiple,
        "supplier_moq": moq,
        "valid_order_step": step,
        "supplier_order_value_gbp": order_value,
        "supplier_order_viability_state": viability,
        "action_safety_state": action_safety,
        "action_block_reason": block_reason,
        "operator_decision_state": decision_state,
        "allowed_decision_codes": "|".join(row["reason_code"] for row in DECISION_REASON_ROWS),
        "row_status": "blocked" if action_safety == "blocked_from_clean_buy" else "review_only",
        "main_image": _field(primary, source_row, rec_row, columns=("main_image",)),
        "profit_verdict": profit_verdict,
        "profit_check_message": _field(primary, profit_row, columns=("profit_check_message",)),
        "missing_input_reasons": _field(primary, profit_row, columns=("missing_input_reasons",)),
        "guardrail_flags": _field(primary, profit_row, columns=("guardrail_flags",)),
        "price_status": _field(primary, source_row, rec_row, profit_row, columns=("price_status",)),
        "price_basis": price_basis,
        "net_fee_model_status": _field(primary, source_row, rec_row, profit_row, columns=("net_fee_model_status",)),
        "expected_refund_cost_per_unit_gbp": _field(primary, source_row, profit_row, columns=("expected_refund_cost_per_unit_gbp", "refund_drag_gbp")),
        "refund_sample_confidence": _field(primary, source_row, columns=("refund_sample_confidence",)),
        "expected_inbound_cost_per_unit_gbp": _field(primary, source_row, profit_row, columns=("expected_inbound_cost_per_unit_gbp", "inbound_cost_drag_gbp")),
        "inbound_cost_basis": _field(primary, source_row, columns=("inbound_cost_basis",)),
        "token_cost_trust_basis": _field(primary, source_row, rec_row, profit_row, columns=("token_cost_trust_basis",)),
        "token_cost_trust_source": _field(primary, source_row, rec_row, profit_row, columns=("token_cost_trust_source",)),
        "token_cost_trust_blockers": _field(primary, source_row, rec_row, profit_row, columns=("token_cost_trust_blockers",)),
        "profit_input_confidence": profit_input_state,
        "profit_input_blockers": _field(primary, source_row, profit_row, columns=("profit_input_blockers",)),
        "velocity_30d": _field(primary, source_row, rec_row, columns=("velocity_30d",)),
        "available_now": _field(primary, source_row, columns=("available_now",)),
        "ordered_open": _field(primary, columns=("ordered_open",)),
        "display_qtys_label": _field(primary, source_row, columns=("display_qtys_label",)),
        "pack_conversion_note": _field(primary, source_row, columns=("pack_conversion_note",)),
        "source_note": _field(primary, profit_row, columns=("bridge_note", "recommendation_reason", "profit_check_message")),
    }


def _latest_draft_decision_rows(draft_df: pd.DataFrame) -> pd.DataFrame:
    if draft_df.empty:
        return pd.DataFrame()
    work = draft_df.copy()
    for col in (
        "event_utc",
        "draft_id",
        "row_id",
        "decision_code",
        "draft_order_qty",
        "snooze_until_utc",
        "decision_note",
        "actor",
        "draft_status",
        "creates_live_action",
    ):
        if col not in work.columns:
            work[col] = ""
        work[col] = work[col].map(_normalize_text)
    work = work[
        (work["row_id"] != "")
        & (work["draft_status"] == "draft")
        & (work["creates_live_action"] == "0")
        & (work["decision_code"].isin(ALLOWED_DRAFT_DECISION_CODES))
    ].copy()
    if work.empty:
        return work
    work["_event_sort"] = pd.to_datetime(work["event_utc"], errors="coerce", utc=True)
    work = work.sort_values(by=["_event_sort", "draft_id"], ascending=[False, False], kind="stable")
    work = work.drop_duplicates(subset=["row_id"], keep="first")
    return work.drop(columns=["_event_sort"], errors="ignore").reset_index(drop=True)


def _apply_latest_draft_decisions(review_df: pd.DataFrame, draft_df: pd.DataFrame) -> pd.DataFrame:
    if review_df.empty:
        return review_df
    out = review_df.copy()
    for col in (
        "latest_draft_id",
        "latest_draft_utc",
        "latest_draft_decision_code",
        "latest_draft_note",
        "latest_draft_actor",
        "snooze_until_utc",
        "draft_order_value_gbp",
    ):
        if col not in out.columns:
            out[col] = ""
    latest = _latest_draft_decision_rows(draft_df)
    if latest.empty:
        return out
    latest_by_row_id = {row["row_id"]: row for _, row in latest.iterrows()}
    for idx, row in out.iterrows():
        draft = latest_by_row_id.get(_normalize_text(row.get("row_id", "")))
        if draft is None:
            continue
        decision_code = _normalize_text(draft.get("decision_code", ""))
        out.at[idx, "latest_draft_id"] = _normalize_text(draft.get("draft_id", ""))
        out.at[idx, "latest_draft_utc"] = _normalize_text(draft.get("event_utc", ""))
        out.at[idx, "latest_draft_decision_code"] = decision_code
        out.at[idx, "latest_draft_note"] = _normalize_text(draft.get("decision_note", ""))
        out.at[idx, "latest_draft_actor"] = _normalize_text(draft.get("actor", ""))
        out.at[idx, "operator_decision_state"] = decision_code
        if decision_code == "order_qty_draft":
            qty = _positive_whole_number_text(draft.get("draft_order_qty", ""))
            out.at[idx, "order_qty_draft"] = qty
            viability, order_value, _reason = _supplier_order_viability(
                qty,
                row.get("current_supplier_cost_gbp", ""),
                row.get("supplier_moq", ""),
                row.get("valid_order_step", ""),
            )
            out.at[idx, "supplier_order_value_gbp"] = order_value
            out.at[idx, "draft_order_value_gbp"] = order_value
            out.at[idx, "supplier_order_viability_state"] = viability
        elif decision_code == "snooze":
            out.at[idx, "snooze_until_utc"] = _normalize_text(draft.get("snooze_until_utc", ""))
    return out


def _build_supplier_summary(session_utc: str, review_df: pd.DataFrame) -> pd.DataFrame:
    if review_df.empty:
        return pd.DataFrame(
            [
                {
                    "session_utc": session_utc,
                    "session_id": SESSION_ID,
                    "supplier_name": "",
                    "supplier_code": "",
                    "total_rows": "0",
                    "source_classes": "",
                    "ready_for_review_rows": "0",
                    "blocked_rows": "0",
                    "draft_order_qty_total": "0",
                    "draft_order_value_gbp": "",
                    "supplier_order_viability_state": "no_rows",
                    "top_block_reasons": "",
                    "session_state": "empty",
                }
            ]
        )
    rows: list[dict[str, str]] = []
    grouped = review_df.groupby(["supplier_name", "supplier_code"], dropna=False, sort=True)
    for (supplier_name, supplier_code), group in grouped:
        blocked = int(group.get("row_status", pd.Series(dtype=str)).map(_normalize_text).eq("blocked").sum())
        ready = int(len(group.index) - blocked)
        qty_total = pd.to_numeric(group.get("order_qty_draft", ""), errors="coerce").fillna(0).sum()
        value_total = pd.to_numeric(group.get("draft_order_value_gbp", ""), errors="coerce").fillna(0).sum()
        block_counter: Counter[str] = Counter()
        for reason_text in group.get("action_block_reason", pd.Series(dtype=str)).tolist():
            first_reason = _normalize_text(reason_text).split("|")[0]
            if first_reason:
                block_counter[first_reason] += 1
        viability_values = {
            _normalize_text(value)
            for value in group.get("supplier_order_viability_state", pd.Series(dtype=str)).tolist()
            if _normalize_text(value)
        }
        rows.append(
            {
                "session_utc": session_utc,
                "session_id": SESSION_ID,
                "supplier_name": _normalize_text(supplier_name),
                "supplier_code": _normalize_text(supplier_code),
                "total_rows": str(len(group.index)),
                "source_classes": "|".join(sorted({_normalize_text(value) for value in group["source_class"].tolist() if _normalize_text(value)})),
                "ready_for_review_rows": str(ready),
                "blocked_rows": str(blocked),
                "draft_order_qty_total": _num_text(float(qty_total)),
                "draft_order_value_gbp": _num_text(float(value_total)) if value_total > 0 else "",
                "supplier_order_viability_state": "|".join(sorted(viability_values)),
                "top_block_reasons": "|".join(reason for reason, _count in block_counter.most_common(5)),
                "session_state": "review_required" if blocked else "review_only_ready",
            }
        )
    return pd.DataFrame(rows)


def _build_health(
    *,
    session_utc: str,
    review_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    reason_df: pd.DataFrame,
    draft_df: pd.DataFrame,
    source_paths: list[Path],
) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    source_path_text = ";".join(str(path) for path in source_paths)

    invalid_source_rows = 0
    if not review_df.empty:
        invalid_source_rows = int(sum(1 for value in review_df["source_class"].tolist() if _normalize_text(value) not in SOURCE_CLASSES))
    rows.append(
        {
            "check_utc": session_utc,
            "check": "source_labels",
            "status": "ok" if invalid_source_rows == 0 else "fail",
            "value": f"invalid={invalid_source_rows};rows={len(review_df.index)}",
            "notes": "Every session row must keep a clear source class.",
            "source_path": source_path_text,
        }
    )

    live_action_rows = 0
    if not reason_df.empty:
        live_action_rows = int(sum(1 for value in reason_df.get("creates_live_action", pd.Series(dtype=str)).tolist() if _normalize_text(value) != "0"))
    rows.append(
        {
            "check_utc": session_utc,
            "check": "reason_codes_local_only",
            "status": "ok" if live_action_rows == 0 else "fail",
            "value": f"live_action_rows={live_action_rows};reason_codes={len(reason_df.index)}",
            "notes": "Reason codes are draft/session-only and must not create live buying actions.",
            "source_path": source_path_text,
        }
    )

    bad_draft_rows: list[str] = []
    if not draft_df.empty:
        work = draft_df.copy()
        for col in ("row_id", "decision_code", "draft_order_qty", "snooze_until_utc", "draft_status", "creates_live_action"):
            if col not in work.columns:
                work[col] = ""
            work[col] = work[col].map(_normalize_text)
        for _, row in work.iterrows():
            row_label = _first_non_blank(row.get("row_id", ""), row.get("seller_sku", ""), row.get("draft_id", ""), "missing_row")
            code = _normalize_text(row.get("decision_code", ""))
            raw_qty = _normalize_text(row.get("draft_order_qty", ""))
            qty = _positive_whole_number_text(raw_qty)
            if _normalize_text(row.get("creates_live_action", "")) != "0":
                bad_draft_rows.append(f"{row_label}:creates_live_action")
            elif _normalize_text(row.get("draft_status", "")) != "draft":
                bad_draft_rows.append(f"{row_label}:bad_status")
            elif code not in ALLOWED_DRAFT_DECISION_CODES:
                bad_draft_rows.append(f"{row_label}:bad_code")
            elif code == "order_qty_draft" and qty == "":
                bad_draft_rows.append(f"{row_label}:bad_qty")
            elif code != "order_qty_draft" and raw_qty != "":
                bad_draft_rows.append(f"{row_label}:qty_on_non_order_code")
            elif code == "snooze" and _normalize_text(row.get("snooze_until_utc", "")) == "":
                bad_draft_rows.append(f"{row_label}:missing_snooze_date")
            elif code != "snooze" and _normalize_text(row.get("snooze_until_utc", "")) != "":
                bad_draft_rows.append(f"{row_label}:snooze_on_non_snooze_code")
    rows.append(
        {
            "check_utc": session_utc,
            "check": "draft_decisions_local_only",
            "status": "ok" if not bad_draft_rows else "fail",
            "value": f"draft_rows={len(draft_df.index)};bad_rows={len(bad_draft_rows)}",
            "notes": "Draft decisions are local UI review entries and must not create live buying actions.",
            "source_path": source_path_text,
        }
    )

    bad_buy_ready = 0
    if not review_df.empty:
        bad_buy_ready = int(
            sum(
                1
                for _, row in review_df.iterrows()
                if _normalize_text(row.get("action_safety_state", "")) == "clean_buy_ready"
                and _normalize_text(row.get("action_block_reason", "")) != ""
            )
        )
    rows.append(
        {
            "check_utc": session_utc,
            "check": "buy_ready_wording_guard",
            "status": "ok" if bad_buy_ready == 0 else "fail",
            "value": f"bad_buy_ready={bad_buy_ready}",
            "notes": "The session may be review-ready, but must not call blocked rows buy-ready.",
            "source_path": source_path_text,
        }
    )

    rows.append(
        {
            "check_utc": session_utc,
            "check": "supplier_summary",
            "status": "ok" if not summary_df.empty else "fail",
            "value": f"summary_rows={len(summary_df.index)}",
            "notes": "Supplier grouping is available for the UI.",
            "source_path": source_path_text,
        }
    )
    return pd.DataFrame(rows)


def build_restock_session_view(
    root: Path | None = None,
    *,
    session_utc: str | None = None,
    write_outputs: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    paths = ensure_o_directories(root=root_path)
    observed = session_utc or _utc_now_iso()

    source_df = read_o_contract_df(root_path, "restock_source_view")
    rec_df = read_o_contract_df(root_path, "restock_recommendations_live")
    queue_df = read_o_contract_df(root_path, "restock_review_queue")
    profit_df = read_o_contract_df(root_path, "restock_profit_checks_live")
    bridge_df = read_o_contract_df(root_path, "legacy_purchase_list_bridge")
    draft_events_df = read_o_contract_df(root_path, DRAFT_DECISION_CONTRACT)

    source_by_sku, source_by_asin = _row_maps(source_df)
    rec_by_sku, rec_by_asin = _row_maps(rec_df)
    profit_by_sku, profit_by_asin = _row_maps(profit_df)

    review_rows: list[dict[str, str]] = []
    for source_class, primary in _candidate_source_rows(bridge_df, queue_df, rec_df):
        source_row = _lookup(primary, source_by_sku, source_by_asin)
        rec_row = _lookup(primary, rec_by_sku, rec_by_asin)
        profit_row = _lookup(primary, profit_by_sku, profit_by_asin)
        review_rows.append(
            _build_review_row(
                session_utc=observed,
                source_class=source_class,
                primary=primary,
                source_row=source_row,
                rec_row=rec_row,
                profit_row=profit_row,
            )
        )

    review_df = pd.DataFrame(review_rows)
    if not review_df.empty:
        review_df = review_df.sort_values(
            by=["supplier_name", "source_class", "seller_sku", "asin"],
            ascending=[True, True, True, True],
            kind="stable",
        ).reset_index(drop=True)
    review_df = _apply_latest_draft_decisions(review_df, draft_events_df)
    summary_df = _build_supplier_summary(observed, review_df)
    reason_df = pd.DataFrame(DECISION_REASON_ROWS)
    source_paths = [
        root_path / "out" / "systems" / "O" / "live" / "restock_source_view.csv",
        root_path / "out" / "systems" / "O" / "live" / "restock_recommendations_live.csv",
        root_path / "out" / "systems" / "O" / "live" / "restock_review_queue.csv",
        root_path / "out" / "systems" / "O" / "live" / "restock_profit_checks_live.csv",
        root_path / "out" / "systems" / "O" / "live" / "legacy_purchase_list_bridge.csv",
        root_path / "out" / "systems" / "O" / "live" / "restock_session_draft_decision_events.csv",
    ]
    health_df = _build_health(
        session_utc=observed,
        review_df=review_df,
        summary_df=summary_df,
        reason_df=reason_df,
        draft_df=draft_events_df,
        source_paths=source_paths,
    )

    if write_outputs:
        draft_events_path = root_path / "out" / "systems" / "O" / "live" / "restock_session_draft_decision_events.csv"
        if not draft_events_path.exists():
            write_o_contract_df(root_path, DRAFT_DECISION_CONTRACT, draft_events_df)
        review_df = write_o_contract_df(root_path, "restock_session_review_live", review_df)
        summary_df = write_o_contract_df(root_path, "restock_session_supplier_summary_live", summary_df)
        reason_df = write_o_contract_df(root_path, "restock_session_reason_codes", reason_df)
        health_df = write_o_contract_df(root_path, "restock_session_health", health_df)
        history_dir = paths.history_dir / f"restock_session_v1_{observed.replace(':', '').replace('-', '')}"
        history_dir.mkdir(parents=True, exist_ok=True)
        review_df.to_csv(history_dir / "restock_session_review_live.csv", index=False)
        summary_df.to_csv(history_dir / "restock_session_supplier_summary_live.csv", index=False)
        reason_df.to_csv(history_dir / "restock_session_reason_codes.csv", index=False)
        health_df.to_csv(history_dir / "restock_session_health.csv", index=False)

    return review_df, summary_df, reason_df, health_df


def main() -> int:
    review_df, summary_df, _reason_df, health_df = build_restock_session_view()
    bad_health = health_df[health_df.get("status", "").map(_normalize_text).ne("ok")]
    print(f"review_rows={len(review_df.index)}")
    print(f"supplier_summary_rows={len(summary_df.index)}")
    print(f"health_status={'ok' if bad_health.empty else 'fail'}")
    return 0 if bad_health.empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
