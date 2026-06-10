from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from scripts.flows.O._contract_io import (
    empty_o_contract_df,
    read_o_contract_df,
    write_o_contract_df,
)
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract


ROI_FULL_THRESHOLD = 15.0
ROI_MIN_THRESHOLD = 10.0
MAX_TEST_SPEND_GBP = 150.0
DROP_REVIEW_MIN_BAD_SNAPSHOTS = 3
DROP_REVIEW_MIN_WINDOW_DAYS = 7
BAD_ECONOMICS_VERDICTS = {"do_not_buy_now", "temporary_market_risk", "drop_review_only"}
BUY_ACTIONS = {"full_restock", "test_restock"}
WEAK_REFUND_PROOF_STATES = {
    "",
    "missing",
    "unknown",
    "weak",
    "not_yet_proven",
    "sellerboard_bridge_only",
    "bridge_labelled_only",
}
WEAK_REFUND_CONFIDENCE_STATES = {"", "missing", "unknown", "weak", "not_yet_proven"}
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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _num(value: object) -> float | None:
    text = _normalize_text(value)
    if text == "":
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _num_text(value: float | int | None) -> str:
    if value is None:
        return ""
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _truthy(value: object) -> bool:
    return _normalize_text(value).lower() in {"1", "true", "yes", "y", "on"}


def _first_non_blank(*values: object) -> str:
    for value in values:
        text = _normalize_text(value)
        if text != "":
            return text
    return ""


def _reason_has(reason_text: object, *tokens: str) -> bool:
    normalized = _normalize_text(reason_text).upper().replace(",", "|")
    return any(token.upper() in normalized for token in tokens)


def _extend_unique(target: list[str], values: list[str]) -> None:
    for value in values:
        if value and value not in target:
            target.append(value)


def _row_map(df: pd.DataFrame) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    if df.empty or "seller_sku" not in df.columns:
        return out
    for _, row in df.iterrows():
        key = _normalize_key(row.get("seller_sku", ""))
        if key and key not in out:
            out[key] = row
    return out


def _row_map_by_asin(df: pd.DataFrame) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    if df.empty or "asin" not in df.columns:
        return out
    for _, row in df.iterrows():
        key = _normalize_key(row.get("asin", ""))
        if key and key not in out:
            out[key] = row
    return out


def _resolve_from_maps(row: pd.Series, sku_map: dict[str, pd.Series], asin_map: dict[str, pd.Series]) -> pd.Series | None:
    sku = _normalize_key(row.get("seller_sku", ""))
    asin = _normalize_key(row.get("asin", ""))
    if sku and sku in sku_map:
        return sku_map[sku]
    if asin and asin in asin_map:
        return asin_map[asin]
    return None


def _native_shadow_verdict(native_row: pd.Series | None) -> tuple[str, str]:
    if native_row is None:
        return "native_missing", "no_native_recommendation_row"
    status = _normalize_text(native_row.get("recommendation_status", "")).lower()
    reason = _normalize_text(native_row.get("reason_codes", ""))
    roi = _num(native_row.get("forward_roi_pct", ""))
    if status == "full_restock":
        return "safe_to_review", reason
    if status == "test_restock":
        return "test_only", reason
    if _reason_has(reason, "MISSING", "NET_FEE", "BLOCKED_MISSING"):
        return "missing_profit_inputs", reason
    if roi is not None and roi < ROI_MIN_THRESHOLD:
        return "do_not_buy_now", reason
    return "do_not_buy_now", reason


def _history_window(
    history_df: pd.DataFrame,
    seller_sku: str,
    current_check_utc: str,
    current_is_bad: bool,
) -> tuple[int, int]:
    dates: set[pd.Timestamp] = set()
    if not history_df.empty and "seller_sku" in history_df.columns and "check_utc" in history_df.columns:
        work = history_df[
            history_df.get("seller_sku", pd.Series(dtype=str)).map(_normalize_key).eq(_normalize_key(seller_sku))
            & history_df.get("profit_verdict", pd.Series(dtype=str)).isin(BAD_ECONOMICS_VERDICTS)
        ].copy()
        if not work.empty:
            parsed = pd.to_datetime(work["check_utc"], errors="coerce", utc=True)
            dates.update(ts.normalize() for ts in parsed.dropna())
    if current_is_bad:
        current = pd.to_datetime(current_check_utc, errors="coerce", utc=True)
        if not pd.isna(current):
            dates.add(current.normalize())
    if not dates:
        return 0, 0
    ordered = sorted(dates)
    return len(ordered), int((ordered[-1] - ordered[0]).days)


def _source_rows(
    bridge_df: pd.DataFrame,
    rec_df: pd.DataFrame,
    queue_df: pd.DataFrame,
) -> list[tuple[str, pd.Series]]:
    rows: list[tuple[str, pd.Series]] = []
    covered_skus: set[str] = set()
    covered_asins: set[str] = set()

    if not bridge_df.empty:
        work = bridge_df.copy()
        if "bridge_status" not in work.columns:
            work["bridge_status"] = ""
        ready_mask = work["bridge_status"].map(lambda value: _normalize_text(value).lower() in {"", "ready"})
        for _, row in work[ready_mask].iterrows():
            sku = _normalize_key(row.get("seller_sku", ""))
            asin = _normalize_key(row.get("asin", ""))
            if sku == "" and asin == "":
                continue
            rows.append(("legacy_purchase_list", row))
            if sku:
                covered_skus.add(sku)
            if asin:
                covered_asins.add(asin)

    native_base = queue_df if not queue_df.empty else rec_df
    if native_base.empty:
        return rows
    for _, row in native_base.iterrows():
        sku = _normalize_key(row.get("seller_sku", ""))
        asin = _normalize_key(row.get("asin", ""))
        if (sku and sku in covered_skus) or (asin and asin in covered_asins):
            continue
        if sku == "" and asin == "":
            continue
        rows.append(("native_o", row))
    return rows


def _field(
    primary: pd.Series,
    rec_row: pd.Series | None,
    source_row: pd.Series | None,
    coverage_row: pd.Series | None,
    *columns: str,
) -> str:
    for column in columns:
        value = _normalize_text(primary.get(column, ""))
        if value:
            return value
    for row in (rec_row, source_row, coverage_row):
        if row is None:
            continue
        for column in columns:
            value = _normalize_text(row.get(column, ""))
            if value:
                return value
    return ""


def _is_net_fee_missing(source_type: str, row: pd.Series, rec_row: pd.Series | None, source_row: pd.Series | None) -> bool:
    if source_type == "legacy_purchase_list":
        return False
    status = _field(row, rec_row, source_row, None, "net_fee_model_status", "purchase_price_safety_status").lower()
    drag = _field(row, rec_row, source_row, None, "net_fee_drag_per_unit_gbp")
    if "missing_net_fee" in status or status in {"missing", "stale", "missing_net_fee_model"}:
        return True
    if drag == "" and status not in {"fresh", "ok", "current"}:
        return True
    return False


def _friendly_token(value: object) -> str:
    return _normalize_text(value).replace("_", " ").replace("|", ", ")


def _price_proof_summary(
    *,
    price_list_cost: str,
    price_list_date: str,
    price_list_unit_code: str,
    price_list_pack_size: str,
    price_list_pack_cost: str,
    match_method: str,
    confidence: str,
    review_reason: str,
    expected_source: str,
    actual_paid: str,
    usual_paid: str,
    max_safe_cost: str,
    price_list_change_status: str,
    delta_actual: str,
) -> str:
    parts: list[str] = []
    if price_list_cost:
        parts.append(f"Current supplier list GBP {price_list_cost}")
        pack_size_num = _num(price_list_pack_size)
        if pack_size_num is not None and pack_size_num > 1:
            pack_label = price_list_unit_code or f"PK{_num_text(pack_size_num)}"
            if price_list_pack_cost:
                parts.append(
                    f"{pack_label} pack cost GBP {price_list_pack_cost} divided by {_num_text(pack_size_num)} units"
                )
            else:
                parts.append(f"{pack_label} requires ordering {_num_text(pack_size_num)} units at a time")
    elif expected_source in {"last_purchase_price", "product_catalog_price", "missing_cost"} or review_reason:
        parts.append("No current supplier list match")
    if price_list_date:
        parts.append(f"list date {price_list_date[:10]}")
    if match_method:
        parts.append(f"matched by {_friendly_token(match_method)}")
    if confidence:
        parts.append(f"confidence {_friendly_token(confidence)}")
    if actual_paid:
        parts.append(f"old paid GBP {actual_paid}")
    if usual_paid:
        parts.append(f"usual paid GBP {usual_paid}")
    if max_safe_cost:
        parts.append(f"max safe buy cost GBP {max_safe_cost}")
    if price_list_change_status:
        parts.append(f"price status {_friendly_token(price_list_change_status)}")
    if delta_actual:
        delta_value = _num(delta_actual)
        if delta_value is not None and delta_value < 0:
            parts.append(f"fresh list is GBP {_num_text(abs(delta_value))} cheaper than old paid")
        elif delta_value is not None and delta_value > 0:
            parts.append(f"fresh list is GBP {_num_text(delta_value)} higher than old paid")
    if review_reason:
        parts.append(f"check reason {_friendly_token(review_reason)}")
    return "; ".join(parts)


def _plus_one_week_utc(check_utc: str) -> str:
    parsed = pd.to_datetime(check_utc, errors="coerce", utc=True)
    if pd.isna(parsed):
        base = _utc_now()
    else:
        base = parsed.to_pydatetime()
    return (base + timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")


def _price_status_fields(
    *,
    price_list_cost: float | None,
    usual_paid_cost: float | None,
    expected_cost: float | None,
    max_safe_cost: float | None,
    price_list_change_status: str,
    has_current_list: bool,
    check_utc: str,
) -> tuple[str, str, str]:
    if max_safe_cost is None or max_safe_cost <= 0:
        return "max_safe_cost_missing", "Max pay is missing, so this cannot be a clean buy yet.", ""
    if not has_current_list:
        return "check_price", "No current supplier price-list match. Operator must confirm a safe unit price.", ""
    list_over_max = price_list_cost is not None and price_list_cost > max_safe_cost
    expected_over_max = expected_cost is not None and expected_cost > max_safe_cost
    usual_under_max = usual_paid_cost is not None and usual_paid_cost <= max_safe_cost
    if (list_over_max or expected_over_max) and not usual_under_max:
        return (
            "over_max_snooze_candidate",
            "Current expected cost is above Max pay. Block clean buy and check again in one week.",
            _plus_one_week_utc(check_utc),
        )
    if list_over_max and usual_under_max:
        return (
            "caution_usual_paid_under_list",
            "Supplier list is above Max pay, but usual paid cost is still safe. Confirm the actual unit cost before ordering.",
            "",
        )
    if usual_paid_cost is not None and price_list_cost is not None and usual_paid_cost < price_list_cost:
        return (
            "caution_usual_paid_under_list",
            "Usual paid cost is below the current supplier list. Confirm the actual unit cost before ordering.",
            "",
        )
    if price_list_cost is not None and usual_paid_cost is not None and price_list_cost < usual_paid_cost:
        return "list_cheaper_than_usual_paid", "Current list is cheaper than usual paid cost.", ""
    if price_list_change_status == "cost_up":
        return "caution_price_increased", "Supplier list price has gone up. Confirm the typed cost against Max pay.", ""
    return "clean_price_ok", "Current list and usual paid evidence are under Max pay.", ""


def _build_profit_check_row(
    *,
    check_utc: str,
    source_type: str,
    row: pd.Series,
    rec_row: pd.Series | None,
    source_row: pd.Series | None,
    coverage_row: pd.Series | None,
    history_df: pd.DataFrame,
) -> dict[str, str]:
    seller_sku = _field(row, rec_row, source_row, coverage_row, "seller_sku")
    asin = _field(row, rec_row, source_row, coverage_row, "asin")
    supplier_name = _field(row, rec_row, source_row, coverage_row, "supplier_name")
    suggested_action = _field(row, rec_row, source_row, coverage_row, "suggested_action", "recommendation_status").lower()
    recommendation_basis = _field(row, rec_row, source_row, coverage_row, "recommendation_basis")
    cost_mode = _field(row, rec_row, source_row, coverage_row, "cost_mode")
    reason_codes = _field(row, rec_row, source_row, coverage_row, "reason_codes", "recommendation_reason", "block_reason_codes")
    source_reference = _field(row, rec_row, source_row, coverage_row, "source_reference")

    cost = _num(_field(row, rec_row, source_row, coverage_row, "suggested_unit_cost_gbp", "current_supplier_buy_cost_gbp"))
    market = _num(_field(row, rec_row, source_row, coverage_row, "suggested_market_price_gbp", "market_price_gbp"))
    roi = _num(_field(row, rec_row, source_row, coverage_row, "expected_forward_roi_pct", "forward_roi_pct"))
    profit = _num(_field(row, rec_row, source_row, coverage_row, "expected_forward_profit_per_unit_gbp", "forward_profit_per_unit_gbp"))
    fee_drag = _num(_field(row, rec_row, source_row, coverage_row, "net_fee_drag_per_unit_gbp"))
    refund_drag = _num(_field(row, rec_row, source_row, coverage_row, "expected_refund_cost_per_unit_gbp"))
    inbound_drag = _num(_field(row, rec_row, source_row, coverage_row, "expected_inbound_cost_per_unit_gbp", "inbound_cost_drag_gbp"))
    break_even_max = _num(_field(row, rec_row, source_row, coverage_row, "max_break_even_purchase_price_gbp"))
    target_max = _num(_field(row, rec_row, source_row, coverage_row, "max_target_roi_purchase_price_gbp"))
    target_roi = _num(_field(row, rec_row, source_row, coverage_row, "target_roi_pct")) or 10.0
    velocity = _num(_field(row, rec_row, source_row, coverage_row, "velocity_30d", "demand_units_per_day")) or 0.0
    days_cover = _num(_field(row, rec_row, source_row, coverage_row, "days_cover_available_only")) or 0.0
    available = _num(_field(row, rec_row, source_row, coverage_row, "available_now", "stock")) or 0.0
    ordered_open = _num(_field(row, rec_row, source_row, coverage_row, "ordered_open")) or 0.0
    inbound = sum(
        value or 0.0
        for value in (
            _num(_field(row, rec_row, source_row, coverage_row, "amazon_inbound_working")),
            _num(_field(row, rec_row, source_row, coverage_row, "amazon_inbound_shipped")),
            _num(_field(row, rec_row, source_row, coverage_row, "amazon_inbound_receiving")),
        )
    )
    effective_supply = available + ordered_open + inbound
    recommended_qty = _num(_field(row, rec_row, source_row, coverage_row, "suggested_qty", "recommended_qty_rounded")) or 0.0
    price_basis = _field(row, rec_row, source_row, coverage_row, "market_price_basis_used")
    purchase_price_safety = _field(row, rec_row, source_row, coverage_row, "purchase_price_safety_status")
    net_fee_status = _field(row, rec_row, source_row, coverage_row, "net_fee_model_status")
    refund_proof_state = _field(row, rec_row, source_row, coverage_row, "refund_proof_state").lower()
    refund_sample_confidence = _field(row, rec_row, source_row, coverage_row, "refund_sample_confidence").lower()
    inbound_cost_confidence = _field(row, rec_row, source_row, coverage_row, "inbound_cost_confidence").lower()
    profit_input_confidence = _field(row, rec_row, source_row, coverage_row, "profit_input_confidence").lower()
    profit_input_blockers = _field(row, rec_row, source_row, coverage_row, "profit_input_blockers")
    user_price_check_required = _truthy(_field(row, rec_row, source_row, coverage_row, "user_price_check_required"))
    price_list_cost_text = _field(row, rec_row, source_row, coverage_row, "price_list_unit_cost_gbp")
    price_list_date = _field(row, rec_row, source_row, coverage_row, "price_list_source_received_at_utc")
    price_list_unit_code = _field(row, rec_row, source_row, coverage_row, "price_list_unit_code")
    price_list_pack_size = _field(row, rec_row, source_row, coverage_row, "price_list_pack_size")
    price_list_pack_cost = _field(row, rec_row, source_row, coverage_row, "price_list_pack_cost_gbp")
    price_list_moq = _field(row, rec_row, source_row, coverage_row, "price_list_moq")
    cost_match_method = _field(row, rec_row, source_row, coverage_row, "cost_match_method")
    cost_confidence = _field(row, rec_row, source_row, coverage_row, "current_cost_confidence", "cost_confidence")
    supplier_cost_review_reason = _field(row, rec_row, source_row, coverage_row, "supplier_cost_review_reason", "review_reason")
    expected_cost_source = _field(row, rec_row, source_row, coverage_row, "expected_cost_source", "current_cost_source")
    actual_paid_text = _field(row, rec_row, source_row, coverage_row, "actual_paid_unit_cost_gbp")
    usual_paid_text = _field(row, rec_row, source_row, coverage_row, "usual_paid_unit_cost_gbp")
    usual_paid_cost = _num(usual_paid_text)
    usual_paid_basis = _field(row, rec_row, source_row, coverage_row, "usual_paid_cost_basis")
    usual_paid_confidence = _field(row, rec_row, source_row, coverage_row, "usual_paid_cost_confidence")
    usual_paid_sample_count = _field(row, rec_row, source_row, coverage_row, "usual_paid_sample_count")
    usual_discount_text = _field(row, rec_row, source_row, coverage_row, "usual_paid_discount_vs_list_pct")
    usual_delta_text = _field(row, rec_row, source_row, coverage_row, "usual_paid_vs_list_delta_gbp")
    price_list_change_status = _field(row, rec_row, source_row, coverage_row, "price_list_change_status")
    price_list_previous_cost = _field(row, rec_row, source_row, coverage_row, "price_list_previous_unit_cost_gbp")
    price_list_previous_pack_size = _field(row, rec_row, source_row, coverage_row, "price_list_previous_pack_size")
    price_list_previous_seen_at = _field(row, rec_row, source_row, coverage_row, "price_list_previous_seen_at_utc")
    price_list_change_delta = _field(row, rec_row, source_row, coverage_row, "price_list_change_delta_gbp")
    price_list_change_pct = _field(row, rec_row, source_row, coverage_row, "price_list_change_pct")
    delta_actual_text = _field(row, rec_row, source_row, coverage_row, "price_list_vs_actual_paid_delta_gbp")
    delta_reference_text = _field(row, rec_row, source_row, coverage_row, "price_list_vs_purchase_reference_delta_gbp")
    price_list_cost_num = _num(price_list_cost_text)
    has_current_list = price_list_cost_num is not None and price_list_cost_num > 0
    price_status, price_status_message, recommended_snooze_until = _price_status_fields(
        price_list_cost=price_list_cost_num,
        usual_paid_cost=usual_paid_cost,
        expected_cost=cost,
        max_safe_cost=target_max,
        price_list_change_status=price_list_change_status,
        has_current_list=has_current_list,
        check_utc=check_utc,
    )
    price_proof_summary = _price_proof_summary(
        price_list_cost=price_list_cost_text,
        price_list_date=price_list_date,
        price_list_unit_code=price_list_unit_code,
        price_list_pack_size=price_list_pack_size,
        price_list_pack_cost=price_list_pack_cost,
        match_method=cost_match_method,
        confidence=cost_confidence,
        review_reason=supplier_cost_review_reason,
        expected_source=expected_cost_source,
        actual_paid=actual_paid_text,
        usual_paid=usual_paid_text,
        max_safe_cost=_num_text(target_max),
        price_list_change_status=price_list_change_status or price_status,
        delta_actual=delta_actual_text,
    )

    if source_type == "legacy_purchase_list":
        if recommendation_basis == "legacy_purchase_list_no_data":
            proof_source = "legacy_sheet_profit_hint"
        elif recommendation_basis == "legacy_purchase_list_drop" or _truthy(row.get("drop_flag", "")):
            proof_source = "legacy_sheet_drop_flag"
        else:
            proof_source = "legacy_sheet_profit_hint"
    else:
        proof_source = "native_profit_proof"

    missing_reasons: list[str] = []
    guardrails: list[str] = []
    if cost is None or cost <= 0:
        missing_reasons.append("missing_supplier_cost")
    if suggested_action in BUY_ACTIONS and (target_max is None or target_max <= 0):
        missing_reasons.append("missing_max_safe_cost")
    if market is None or market <= 0:
        missing_reasons.append("missing_market_price")
    if roi is None and recommendation_basis != "legacy_purchase_list_no_data":
        missing_reasons.append("missing_forward_roi")
    if profit is None and recommendation_basis != "legacy_purchase_list_no_data":
        missing_reasons.append("missing_forward_profit")
    if _is_net_fee_missing(source_type, row, rec_row, source_row):
        missing_reasons.append("missing_net_fee_model")
    if refund_proof_state in WEAK_REFUND_PROOF_STATES or refund_sample_confidence in WEAK_REFUND_CONFIDENCE_STATES:
        missing_reasons.append("missing_refund_confidence")
    if inbound_cost_confidence in WEAK_INBOUND_COST_CONFIDENCE_STATES:
        missing_reasons.append("missing_inbound_cost_confidence")
    if profit_input_confidence in WEAK_PROFIT_INPUT_CONFIDENCE_STATES:
        blockers = [part.strip() for part in profit_input_blockers.split("|") if part.strip()]
        _extend_unique(missing_reasons, blockers or ["missing_profit_input_confidence"])

    if profit is None and cost is not None and market is not None and fee_drag is not None and inbound_drag is not None:
        profit = market - cost - fee_drag - max(refund_drag or 0.0, 0.0) - max(inbound_drag, 0.0)
    if roi is None and profit is not None and cost is not None and cost > 0:
        roi = (profit / cost) * 100.0

    demand_status = "demand_present" if velocity > 0 else "missing_or_weak_demand"
    if _reason_has(reason_codes, "SUFFICIENT_EFFECTIVE_SUPPLY") or (
        suggested_action == "wait" and recommended_qty <= 0 and effective_supply > 0
    ):
        demand_status = "supply_sufficient"
        guardrails.append("existing_stock_or_order_prevents_overbuy")
    if suggested_action == "test_restock" and cost is not None and recommended_qty > 0 and (cost * recommended_qty) > MAX_TEST_SPEND_GBP:
        guardrails.append("test_spend_cap_exceeded_after_rounding")
    if source_type == "legacy_purchase_list":
        guardrails.append("legacy_sheet_profit_not_native_proof")
    if price_basis == "LEGACY_PURCHASE_LIST_ROI_BACKSOLVE":
        guardrails.append("legacy_roi_backsolved_from_sheet")

    verdict = "missing_profit_inputs"
    if proof_source == "legacy_sheet_drop_flag":
        verdict = "drop_review_only"
        guardrails.append("manual_sheet_drop_review")
    elif recommendation_basis == "legacy_purchase_list_no_data" and (cost is None or cost <= 0):
        verdict = "missing_profit_inputs"
        guardrails.append("no_data_missing_cost_not_buy")
    elif recommendation_basis == "legacy_purchase_list_no_data":
        verdict = "test_only"
        guardrails.append("no_data_test_only")
        if price_status in {"check_price", "max_safe_cost_missing"}:
            guardrails.append(price_status)
    elif price_status == "over_max_snooze_candidate":
        verdict = "do_not_buy_now"
        guardrails.append("current_cost_above_max_safe_cost")
        guardrails.append("recommended_one_week_snooze")
    elif "missing_max_safe_cost" in missing_reasons:
        verdict = "needs_price_check"
        guardrails.append("missing_max_safe_cost")
    elif price_status in {"check_price", "max_safe_cost_missing"}:
        verdict = "needs_price_check"
        guardrails.append(price_status)
    elif user_price_check_required:
        verdict = "needs_price_check"
        guardrails.append("supplier_cost_confirmation_required")
    elif missing_reasons:
        verdict = "missing_profit_inputs"
    elif "test_spend_cap_exceeded_after_rounding" in guardrails:
        verdict = "needs_price_check"
    elif demand_status == "supply_sufficient":
        verdict = "do_not_buy_now"
    elif purchase_price_safety in {"above_break_even_max", "above_target_roi_max"}:
        verdict = "do_not_buy_now"
        guardrails.append(f"purchase_price_{purchase_price_safety}")
    elif roi is not None and roi < ROI_MIN_THRESHOLD:
        if velocity > 0 and price_basis in {"BUY_BOX_PRICE", "LOWEST_FBA_PRICE", "LOWEST_FBA"}:
            verdict = "temporary_market_risk"
            guardrails.append("single_current_market_snapshot_not_drop")
        else:
            verdict = "do_not_buy_now"
    elif roi is not None and roi < ROI_FULL_THRESHOLD:
        verdict = "test_only"
    elif suggested_action == "test_restock":
        verdict = "test_only"
    else:
        verdict = "safe_to_review"

    bad_count, bad_window_days = _history_window(history_df, seller_sku, check_utc, verdict in BAD_ECONOMICS_VERDICTS)
    if verdict in {"do_not_buy_now", "temporary_market_risk"}:
        if bad_count >= DROP_REVIEW_MIN_BAD_SNAPSHOTS and bad_window_days >= DROP_REVIEW_MIN_WINDOW_DAYS:
            verdict = "drop_review_only"
            guardrails.append("repeated_bad_economics_window_met")
        else:
            guardrails.append("drop_review_requires_repeated_evidence")

    native_shadow_verdict, native_shadow_reason = _native_shadow_verdict(rec_row) if source_type == "legacy_purchase_list" else ("", "")
    if source_type != "legacy_purchase_list" and missing_reasons:
        proof_source = "native_profit_incomplete"

    if verdict == "safe_to_review":
        message = f"Profit check: Review - ROI {_num_text(roi)} percent, GBP {_num_text(profit)} profit/unit."
    elif verdict == "test_only":
        message = f"Profit check: Test only - ROI {_num_text(roi)} percent, GBP {_num_text(profit)} profit/unit."
    elif verdict == "needs_price_check":
        message = "Profit check: Needs price check before this is a clean buy."
        if price_status_message:
            message = f"{message} {price_status_message}"
    elif verdict == "missing_profit_inputs":
        message = f"Profit check: Missing proof - {', '.join(missing_reasons) or 'missing current proof'}."
    elif verdict == "temporary_market_risk":
        message = "Profit check: Current price looks weak, but this is not enough evidence to drop the product."
    elif verdict == "drop_review_only":
        message = "Profit check: Drop review only - do not buy unless deliberately overridden."
    else:
        message = "Profit check: Do not buy now."

    return {
        "check_utc": check_utc,
        "seller_sku": seller_sku,
        "asin": asin,
        "supplier_name": supplier_name,
        "suggested_action": suggested_action,
        "profit_verdict": verdict,
        "profit_proof_source": proof_source,
        "profit_check_message": message,
        "current_sell_price_gbp": _num_text(market),
        "sell_price_basis": price_basis,
        "supplier_cost_gbp": _num_text(cost),
        "fee_drag_gbp": _num_text(fee_drag),
        "refund_drag_gbp": _num_text(refund_drag),
        "inbound_cost_drag_gbp": _num_text(inbound_drag),
        "forward_profit_per_unit_gbp": _num_text(profit),
        "forward_roi_pct": _num_text(roi),
        "break_even_max_cost_gbp": _num_text(break_even_max),
        "target_roi_max_cost_gbp": _num_text(target_max),
        "max_safe_unit_cost_gbp": _num_text(target_max),
        "target_roi_pct": _num_text(target_roi),
        "demand_status": demand_status,
        "demand_units_per_day": _num_text(velocity),
        "days_cover_available_only": _num_text(days_cover),
        "effective_supply_units": _num_text(effective_supply),
        "recommended_qty": _num_text(recommended_qty),
        "missing_input_reasons": "|".join(dict.fromkeys(missing_reasons)),
        "guardrail_flags": "|".join(dict.fromkeys(guardrails)),
        "bad_economics_snapshot_count": str(bad_count),
        "bad_economics_window_days": str(bad_window_days),
        "drop_review_eligible": "1" if verdict == "drop_review_only" else "0",
        "source_system": source_type,
        "source_reference": source_reference,
        "recommendation_basis": recommendation_basis,
        "cost_mode": cost_mode,
        "purchase_price_safety_status": purchase_price_safety,
        "net_fee_model_status": net_fee_status,
        "native_shadow_verdict": native_shadow_verdict,
        "native_shadow_reason": native_shadow_reason,
        "price_list_unit_cost_gbp": price_list_cost_text,
        "price_list_source_received_at_utc": price_list_date,
        "price_list_unit_code": price_list_unit_code,
        "price_list_pack_size": price_list_pack_size,
        "price_list_pack_cost_gbp": price_list_pack_cost,
        "price_list_moq": price_list_moq,
        "cost_match_method": cost_match_method,
        "cost_confidence": cost_confidence,
        "supplier_cost_review_reason": supplier_cost_review_reason,
        "expected_cost_source": expected_cost_source,
        "actual_paid_unit_cost_gbp": actual_paid_text,
        "usual_paid_unit_cost_gbp": usual_paid_text,
        "usual_paid_cost_basis": usual_paid_basis,
        "usual_paid_cost_confidence": usual_paid_confidence,
        "usual_paid_sample_count": usual_paid_sample_count,
        "usual_paid_discount_vs_list_pct": usual_discount_text,
        "usual_paid_vs_list_delta_gbp": usual_delta_text,
        "price_list_change_status": price_list_change_status,
        "price_list_previous_unit_cost_gbp": price_list_previous_cost,
        "price_list_previous_pack_size": price_list_previous_pack_size,
        "price_list_previous_seen_at_utc": price_list_previous_seen_at,
        "price_list_change_delta_gbp": price_list_change_delta,
        "price_list_change_pct": price_list_change_pct,
        "price_status": price_status,
        "price_status_message": price_status_message,
        "recommended_snooze_until_utc": recommended_snooze_until,
        "price_list_vs_actual_paid_delta_gbp": delta_actual_text,
        "price_list_vs_purchase_reference_delta_gbp": delta_reference_text,
        "price_proof_summary": price_proof_summary,
        "profit_input_confidence": profit_input_confidence,
        "profit_input_blockers": profit_input_blockers,
    }


def _health_rows(check_utc: str, checks_df: pd.DataFrame) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def add(
        check_type: str,
        check_name: str,
        status: str,
        value: int | str,
        details: str = "",
        *,
        supplier_name: str = "",
        source_type: str = "",
        profit_verdict: str = "",
        reason: str = "",
    ) -> None:
        rows.append(
            {
                "check_utc": check_utc,
                "check_type": check_type,
                "check_name": check_name,
                "status": status,
                "supplier_name": supplier_name,
                "source_type": source_type,
                "profit_verdict": profit_verdict,
                "reason": reason,
                "value": str(value),
                "details": details,
            }
        )

    add("summary", "profit_check_rows", "ok", len(checks_df.index))
    if checks_df.empty:
        return rows

    for verdict, count in checks_df["profit_verdict"].value_counts().sort_index().items():
        add("verdict_count", f"verdict::{verdict}", "ok", int(count), profit_verdict=str(verdict))

    if "price_status" in checks_df.columns:
        for status, count in checks_df["price_status"].value_counts().sort_index().items():
            normalized = _normalize_text(status)
            if normalized == "":
                continue
            health_status = "warn" if normalized in {"check_price", "max_safe_cost_missing", "over_max_snooze_candidate"} else "ok"
            add("price_status_count", f"price_status::{normalized}", health_status, int(count), reason=normalized)

    for source_type, count in checks_df["profit_proof_source"].value_counts().sort_index().items():
        status = "warn" if str(source_type).startswith("legacy") or str(source_type).endswith("incomplete") else "ok"
        add("source_count", f"source::{source_type}", status, int(count), source_type=str(source_type))

    missing = (
        checks_df["missing_input_reasons"]
        .astype(str)
        .str.split("|")
        .explode()
        .fillna("")
        .map(_normalize_text)
    )
    for reason, count in missing[missing.ne("")].value_counts().sort_index().items():
        add("missing_input_count", f"missing::{reason}", "warn", int(count), reason=str(reason))

    for supplier_name, group in checks_df.groupby("supplier_name", dropna=False, sort=True):
        supplier = _normalize_text(supplier_name) or "(Unknown supplier)"
        buy_candidates = group["suggested_action"].isin(BUY_ACTIONS)
        non_native_buy = group[buy_candidates & group["profit_proof_source"].ne("native_profit_proof")]
        add(
            "supplier_guardrail",
            "buy_candidates_without_native_profit_proof",
            "warn" if len(non_native_buy.index) else "ok",
            len(non_native_buy.index),
            supplier_name=supplier,
        )
        for verdict, count in group["profit_verdict"].value_counts().sort_index().items():
            add(
                "supplier_verdict_count",
                f"supplier::{supplier}::{verdict}",
                "ok",
                int(count),
                supplier_name=supplier,
                profit_verdict=str(verdict),
            )
        current_list_rows = group["price_list_unit_cost_gbp"].map(_normalize_text).ne("")
        add(
            "supplier_price_proof",
            "current_price_list_cost_rows",
            "ok" if int(current_list_rows.sum()) else "warn",
            int(current_list_rows.sum()),
            supplier_name=supplier,
        )
        missing_list_buy = group[buy_candidates & ~current_list_rows]
        add(
            "supplier_price_proof",
            "buy_candidates_without_current_price_list_cost",
            "warn" if len(missing_list_buy.index) else "ok",
            len(missing_list_buy.index),
            supplier_name=supplier,
        )
        bridge_rows = group["source_system"].eq("legacy_purchase_list")
        bridge_with_list = group[bridge_rows & current_list_rows]
        add(
            "supplier_price_proof",
            "bridge_rows_with_current_price_list_cost",
            "ok" if len(bridge_with_list.index) else ("warn" if int(bridge_rows.sum()) else "ok"),
            len(bridge_with_list.index),
            supplier_name=supplier,
        )
        if "price_status" in group.columns:
            over_max_rows = group[group["price_status"].eq("over_max_snooze_candidate")]
            add(
                "supplier_price_proof",
                "over_max_snooze_candidates",
                "warn" if len(over_max_rows.index) else "ok",
                len(over_max_rows.index),
                supplier_name=supplier,
            )

    legacy_hint_count = int(checks_df["profit_proof_source"].eq("legacy_sheet_profit_hint").sum())
    add(
        "guardrail",
        "legacy_sheet_profit_hint_rows",
        "warn" if legacy_hint_count else "ok",
        legacy_hint_count,
        "Sheet-derived ROI is a hint, not native current-profit proof.",
    )

    unsafe_drop = checks_df[
        checks_df["profit_verdict"].eq("drop_review_only")
        & ~checks_df["guardrail_flags"].astype(str).str.contains("manual_sheet_drop_review", na=False)
        & (
            pd.to_numeric(checks_df["bad_economics_snapshot_count"], errors="coerce").fillna(0).lt(DROP_REVIEW_MIN_BAD_SNAPSHOTS)
            | pd.to_numeric(checks_df["bad_economics_window_days"], errors="coerce").fillna(0).lt(DROP_REVIEW_MIN_WINDOW_DAYS)
        )
    ]
    add(
        "guardrail",
        "drop_review_requires_repeated_bad_economics",
        "fail" if len(unsafe_drop.index) else "ok",
        len(unsafe_drop.index),
        "No automatic drop review from one weak market snapshot.",
    )
    return rows


def _split_flags(value: object) -> set[str]:
    return {
        _normalize_text(part)
        for part in str(value or "").replace(",", "|").split("|")
        if _normalize_text(part)
    }


def _market_refresh_reason(row: pd.Series) -> str:
    missing = _split_flags(row.get("missing_input_reasons", ""))
    guardrails = _split_flags(row.get("guardrail_flags", ""))
    price_status = _normalize_text(row.get("price_status", ""))
    sell_price_basis = _normalize_text(row.get("sell_price_basis", "")).upper()
    net_fee_status = _normalize_text(row.get("net_fee_model_status", "")).lower()

    reasons: list[str] = []
    if "missing_market_price" in missing or sell_price_basis in {"", "MISSING_MARKET_CONTEXT"}:
        reasons.append("missing_current_market_price")
    if sell_price_basis == "LEGACY_PURCHASE_LIST_ROI_BACKSOLVE":
        reasons.append("legacy_sheet_market_not_native")
    if "missing_max_safe_cost" in missing or price_status == "max_safe_cost_missing":
        reasons.append("missing_native_max_pay")
    if "missing_net_fee_model" in missing or net_fee_status in {"", "missing", "missing_net_fee_model"}:
        reasons.append("missing_native_fee_model")
    if "legacy_sheet_profit_not_native_proof" in guardrails:
        reasons.append("legacy_sheet_requires_native_market_proof")
    return "|".join(dict.fromkeys(reasons))


def _market_refresh_candidates(check_utc: str, checks_df: pd.DataFrame) -> pd.DataFrame:
    if checks_df.empty:
        return empty_o_contract_df("restock_market_refresh_candidates_live")

    rows: list[dict[str, str]] = []
    for _, row in checks_df.iterrows():
        action = _normalize_text(row.get("suggested_action", "")).lower()
        if action not in BUY_ACTIONS:
            continue
        supplier_cost = _num(row.get("supplier_cost_gbp", ""))
        if supplier_cost is None or supplier_cost <= 0:
            continue
        reason = _market_refresh_reason(row)
        if not reason:
            continue

        seller_sku = _normalize_text(row.get("seller_sku", ""))
        asin = _normalize_text(row.get("asin", ""))
        source_system = _normalize_text(row.get("source_system", ""))
        candidate_status = "ready" if seller_sku and asin else "missing_identity"
        priority = "high" if source_system == "legacy_purchase_list" else "normal"
        if "missing_current_market_price" in reason or "legacy_sheet_market_not_native" in reason:
            priority = "high"

        rows.append(
            {
                "check_utc": check_utc,
                "seller_sku": seller_sku,
                "asin": asin,
                "supplier_name": _normalize_text(row.get("supplier_name", "")),
                "source_system": source_system,
                "source_reference": _normalize_text(row.get("source_reference", "")),
                "suggested_action": action,
                "profit_verdict": _normalize_text(row.get("profit_verdict", "")),
                "price_status": _normalize_text(row.get("price_status", "")),
                "missing_input_reasons": _normalize_text(row.get("missing_input_reasons", "")),
                "market_refresh_reason": reason,
                "priority": priority,
                "candidate_status": candidate_status,
                "required_for_clean_buy": "1",
                "current_sell_price_gbp": _normalize_text(row.get("current_sell_price_gbp", "")),
                "sell_price_basis": _normalize_text(row.get("sell_price_basis", "")),
                "target_roi_max_cost_gbp": _normalize_text(row.get("target_roi_max_cost_gbp", "")),
                "max_safe_unit_cost_gbp": _normalize_text(row.get("max_safe_unit_cost_gbp", "")),
                "price_list_unit_cost_gbp": _normalize_text(row.get("price_list_unit_cost_gbp", "")),
                "usual_paid_unit_cost_gbp": _normalize_text(row.get("usual_paid_unit_cost_gbp", "")),
                "native_shadow_verdict": _normalize_text(row.get("native_shadow_verdict", "")),
                "native_shadow_reason": _normalize_text(row.get("native_shadow_reason", "")),
                "refresh_source_note": "read_only_market_snapshot_needed",
            }
        )

    if not rows:
        return empty_o_contract_df("restock_market_refresh_candidates_live")
    return pd.DataFrame(rows)


def _append_market_refresh_health(
    *,
    check_utc: str,
    health_rows: list[dict[str, str]],
    candidates_df: pd.DataFrame,
) -> None:
    def add(check_name: str, status: str, value: int | str, details: str = "", supplier_name: str = "") -> None:
        health_rows.append(
            {
                "check_utc": check_utc,
                "check_type": "market_refresh",
                "check_name": check_name,
                "status": status,
                "supplier_name": supplier_name,
                "source_type": "",
                "profit_verdict": "",
                "reason": "",
                "value": str(value),
                "details": details,
            }
        )

    total = len(candidates_df.index)
    if candidates_df.empty:
        add("market_refresh_candidates", "ok", 0, "No reorder rows currently need a market refresh.")
        return
    ready = int(candidates_df["candidate_status"].astype(str).eq("ready").sum())
    missing_identity = total - ready
    add(
        "market_refresh_candidates",
        "warn" if total else "ok",
        total,
        "Rows need a fresh read-only market snapshot before Max pay can be trusted.",
    )
    add("market_refresh_candidates_ready", "warn" if ready else "ok", ready)
    add("market_refresh_candidates_missing_identity", "fail" if missing_identity else "ok", missing_identity)
    for supplier_name, group in candidates_df.groupby("supplier_name", dropna=False, sort=True):
        supplier = _normalize_text(supplier_name) or "(Unknown supplier)"
        add("supplier_market_refresh_candidates", "warn", len(group.index), supplier_name=supplier)


def build_restock_profit_checks(
    root: Path | None = None,
    *,
    check_utc: str | None = None,
    append_history: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    observed_utc = _normalize_text(check_utc) or _utc_now_iso()

    rec_df = read_o_contract_df(root_path, "restock_recommendations_live")
    queue_df = read_o_contract_df(root_path, "restock_review_queue")
    source_df = read_o_contract_df(root_path, "restock_source_view")
    bridge_df = read_o_contract_df(root_path, "legacy_purchase_list_bridge")
    coverage_df = read_o_contract_df(root_path, "reorder_input_coverage_report")
    history_df = read_o_contract_df(root_path, "restock_profit_check_history")

    rec_by_sku = _row_map(rec_df)
    rec_by_asin = _row_map_by_asin(rec_df)
    source_by_sku = _row_map(source_df)
    source_by_asin = _row_map_by_asin(source_df)
    coverage_by_sku = _row_map(coverage_df)
    coverage_by_asin = _row_map_by_asin(coverage_df)

    out_rows: list[dict[str, str]] = []
    for source_type, row in _source_rows(bridge_df, rec_df, queue_df):
        rec_row = _resolve_from_maps(row, rec_by_sku, rec_by_asin)
        source_row = _resolve_from_maps(row, source_by_sku, source_by_asin)
        coverage_row = _resolve_from_maps(row, coverage_by_sku, coverage_by_asin)
        out_rows.append(
            _build_profit_check_row(
                check_utc=observed_utc,
                source_type=source_type,
                row=row,
                rec_row=rec_row,
                source_row=source_row,
                coverage_row=coverage_row,
                history_df=history_df,
            )
        )

    checks_df = pd.DataFrame(out_rows)
    if checks_df.empty:
        checks_df = empty_o_contract_df("restock_profit_checks_live")
    checks_df = write_o_contract_df(root_path, "restock_profit_checks_live", checks_df)

    market_candidates_df = _market_refresh_candidates(observed_utc, checks_df)
    market_candidates_df = write_o_contract_df(
        root_path,
        "restock_market_refresh_candidates_live",
        market_candidates_df,
    )

    health_rows = _health_rows(observed_utc, checks_df)
    _append_market_refresh_health(
        check_utc=observed_utc,
        health_rows=health_rows,
        candidates_df=market_candidates_df,
    )
    health_df = pd.DataFrame(health_rows)
    if health_df.empty:
        health_df = empty_o_contract_df("restock_profit_check_health")
    health_df = write_o_contract_df(root_path, "restock_profit_check_health", health_df)

    if append_history and not checks_df.empty:
        history_cols = empty_o_contract_df("restock_profit_check_history").columns.tolist()
        append_df = checks_df[[col for col in history_cols if col in checks_df.columns]].copy()
        existing_history = read_o_contract_df(root_path, "restock_profit_check_history")
        write_o_contract_df(root_path, "restock_profit_check_history", pd.concat([existing_history, append_df], ignore_index=True))

    print({"status": "success", "rows": len(checks_df.index), "health_rows": len(health_df.index)})
    return checks_df, health_df


def main() -> None:
    build_restock_profit_checks()


if __name__ == "__main__":
    main()
