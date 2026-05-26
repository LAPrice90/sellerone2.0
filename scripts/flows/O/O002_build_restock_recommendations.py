from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.flows.O._contract_io import empty_o_contract_df, read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract
from scripts.flows.O._schemas import get_o_output_contract


FULL_RESTOCK_TARGET_DAYS = 30
TEST_RESTOCK_TARGET_DAYS = 10
ROI_FULL_THRESHOLD = 15.0
ROI_MIN_THRESHOLD = 10.0
MAX_TEST_SPEND_GBP = 150.0
LOW_DEMAND_FLOOR_UNITS_PER_DAY = 0.05
STALE_OOS_DAYS_THRESHOLD = 30.0
LONG_LEAD_DAYS_THRESHOLD = 45.0
TARGET_DAYS_CAP = 90
TARGET_ROI_PCT = 10.0
PACK_PROFILE_FIELDS: tuple[str, ...] = (
    "components_per_sell_pack",
    "supplier_cost_basis",
    "component_unit_label",
    "expected_sell_pack_cost_gbp",
    "expected_component_cost_gbp",
    "quantity_strategy",
    "preferred_order_sell_packs",
    "preferred_order_components",
    "preferred_supplier_boxes",
    "supplier_box_components",
    "hazmat_group",
    "isolate_from_normal_po",
    "target_carton_weight_kg",
    "pack_profile_status",
)
NET_FEE_AUDIT_FIELDS: tuple[str, ...] = (
    "market_price_ex_vat_gbp",
    "market_price_vat_rate_pct",
    "current_token_cost_gbp",
    "break_even_price_gbp",
    "net_fee_drag_per_unit_gbp",
    "net_fee_model_status",
    "net_fee_model_asof",
    "net_fee_model_age_hours",
    "net_fee_model_source",
    "net_fee_model_notes",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def _num(value: object) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _num_text(value: float | None, *, allow_blank: bool = True) -> str:
    if value is None:
        return "" if allow_blank else "0"
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _truthy(value: object) -> bool:
    token = str(value or "").strip().lower()
    return token in {"1", "true", "yes", "y", "on"}


def _is_active_candidate(row: pd.Series) -> bool:
    normalized = str(row.get("sale_status_normalized", "")).strip().lower()
    if normalized:
        return normalized == "active"
    legacy = str(row.get("sale_status", "")).strip().lower()
    if legacy in {"dropped", "inactive", "discontinued"}:
        return False
    return legacy == "active"


def _parse_utc(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    parsed = pd.to_datetime(raw, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def _round_qty(raw_qty: int, pack_size: int, moq: int) -> int:
    qty = max(0, int(raw_qty))
    pack = max(1, int(pack_size))
    min_order = max(1, int(moq))

    if qty == 0:
        return 0
    if pack > 1:
        qty = int(math.ceil(qty / pack) * pack)
    if qty < min_order:
        qty = min_order
    if pack > 1 and qty % pack != 0:
        qty = int(math.ceil(qty / pack) * pack)
    return qty


def _reason_csv(reasons: list[str]) -> str:
    seen: set[str] = set()
    ordered: list[str] = []
    for reason in reasons:
        item = str(reason or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ",".join(ordered)


def _note_codes(value: object) -> set[str]:
    text = str(value or "").strip().lower().replace(",", "|")
    return {code.strip() for code in text.split("|") if code.strip()}


def _recommendation_basis(row: pd.Series, current_cost: float | None) -> tuple[str, str]:
    cost_mode = str(row.get("cost_mode", "")).strip().lower() or "live"
    if cost_mode == "test":
        if current_cost is not None and current_cost > 0:
            return "test", "test_cost_snapshot"
        return "test", "test_mode_no_cost_match"
    if current_cost is not None and current_cost > 0:
        return "live", "live_cost_inputs"
    return "live", "live_mode_missing_cost"


def _effective_sell_pack_cost(row: pd.Series) -> float | None:
    converted = _num(row.get("expected_sell_pack_cost_gbp", ""))
    if converted is not None and converted > 0:
        return converted
    return _num(row.get("current_supplier_buy_cost_gbp", ""))


def _pack_profile_fields(row: pd.Series) -> dict[str, str]:
    return {field: str(row.get(field, "")).strip() for field in PACK_PROFILE_FIELDS}


def _net_fee_audit_fields(
    row: pd.Series,
    *,
    gross_forward_roi_pct: float | None,
    gross_forward_profit: float | None,
) -> dict[str, str]:
    out = {field: str(row.get(field, "")).strip() for field in NET_FEE_AUDIT_FIELDS}
    out["gross_forward_roi_pct"] = _num_text(gross_forward_roi_pct)
    out["gross_forward_profit_per_unit_gbp"] = _num_text(gross_forward_profit)
    return out


def _net_fee_status(row: pd.Series) -> str:
    status = str(row.get("net_fee_model_status", "")).strip().lower()
    if status:
        return status
    return "missing"


def _net_fee_block_reason(row: pd.Series) -> str:
    status = _net_fee_status(row)
    if status == "fresh":
        return ""
    if status == "stale":
        return "BLOCKED_STALE_NET_FEE_INPUT"
    if status == "invalid":
        return "BLOCKED_INVALID_NET_FEE_INPUT"
    return "BLOCKED_MISSING_NET_FEE_INPUT"


def _gross_forward_fields(
    *,
    current_cost: float | None,
    market_price: float | None,
    refund_drag: float,
) -> tuple[float | None, float | None]:
    if current_cost is None or current_cost <= 0 or market_price is None or market_price <= 0:
        return None, None
    gross_profit = market_price - current_cost - refund_drag
    return gross_profit, (gross_profit / current_cost) * 100.0


def _net_forward_fields(
    *,
    current_cost: float | None,
    market_price_ex_vat: float | None,
    net_fee_drag: float | None,
    refund_drag: float,
    net_fee_status: str,
) -> tuple[float | None, float | None]:
    if net_fee_status != "fresh":
        return None, None
    if current_cost is None or current_cost <= 0:
        return None, None
    if market_price_ex_vat is None or market_price_ex_vat <= 0:
        return None, None
    if net_fee_drag is None or net_fee_drag < 0:
        return None, None
    forward_profit = market_price_ex_vat - current_cost - net_fee_drag - max(refund_drag, 0.0)
    return forward_profit, (forward_profit / current_cost) * 100.0


def _pack_block_reason_codes(row: pd.Series) -> list[str]:
    status = str(row.get("pack_profile_status", "")).strip().lower()
    supplier_cost_basis = str(row.get("supplier_cost_basis", "")).strip().lower()
    note_codes = _note_codes(row.get("source_notes", ""))
    blockers: list[str] = []

    if status in {"missing_pack_profile", "missing"} or "missing_pack_profile" in note_codes:
        blockers.append("PACK_PROFILE_MISSING")
    if status in {"unconfirmed_pack_profile", "draft", "pending", "provisional"} or "unconfirmed_pack_profile" in note_codes:
        blockers.append("PACK_PROFILE_UNCONFIRMED")
    if status == "invalid" or "invalid_component_conversion" in note_codes:
        blockers.append("PACK_PROFILE_INVALID")
    if "missing_supplier_cost_basis" in note_codes or supplier_cost_basis == "":
        if status not in {"", "default_normal"}:
            blockers.append("PACK_SUPPLIER_COST_BASIS_MISSING")
    if "invalid_supplier_box_alignment" in note_codes:
        blockers.append("PACK_SUPPLIER_BOX_ALIGNMENT_INVALID")
    if status == "special_order_profile_required" or "special_order_profile_required" in note_codes:
        blockers.append("SPECIAL_ORDER_PROFILE_REQUIRED")
    if "pack_title_profile_mismatch" in note_codes:
        blockers.append("PACK_TITLE_PROFILE_MISMATCH")

    return list(dict.fromkeys(blockers))


def _purchase_limit_fields(
    *,
    current_cost: float | None,
    market_price_ex_vat: float | None,
    net_fee_drag: float | None,
    net_fee_status: str,
    refund_drag: float,
    target_roi_pct: float = TARGET_ROI_PCT,
) -> dict[str, str]:
    if net_fee_status != "fresh":
        return {
            "max_break_even_purchase_price_gbp": "",
            "max_target_roi_purchase_price_gbp": "",
            "target_roi_pct": _num_text(target_roi_pct, allow_blank=False),
            "purchase_price_safety_status": f"{net_fee_status or 'missing'}_net_fee_model",
        }
    if market_price_ex_vat is None or market_price_ex_vat <= 0:
        return {
            "max_break_even_purchase_price_gbp": "",
            "max_target_roi_purchase_price_gbp": "",
            "target_roi_pct": _num_text(target_roi_pct, allow_blank=False),
            "purchase_price_safety_status": "missing_market_price",
        }
    net_revenue = max(0.0, market_price_ex_vat - max(net_fee_drag or 0.0, 0.0) - max(refund_drag, 0.0))
    break_even_max = net_revenue
    target_roi_max = net_revenue / (1.0 + (target_roi_pct / 100.0))
    if current_cost is None or current_cost <= 0:
        status = "missing_expected_cost"
    elif current_cost > break_even_max:
        status = "above_break_even_max"
    elif current_cost > target_roi_max:
        status = "above_target_roi_max"
    else:
        status = "within_target_roi_max"
    return {
        "max_break_even_purchase_price_gbp": _num_text(break_even_max),
        "max_target_roi_purchase_price_gbp": _num_text(target_roi_max),
        "target_roi_pct": _num_text(target_roi_pct, allow_blank=False),
        "purchase_price_safety_status": status,
    }


def _build_wait_row(
    base_row: pd.Series,
    *,
    asof_utc: str,
    reason_codes: list[str],
    days_cover_available_only: float | None,
    days_cover_total_pipeline: float | None,
    forward_roi_pct: float | None,
    forward_profit: float | None,
    confidence_score: float,
    confidence_note: str,
    cost_mode: str,
    recommendation_basis: str,
) -> dict[str, str]:
    current_cost = _effective_sell_pack_cost(base_row)
    market_price = _num(base_row.get("market_price_gbp", ""))
    market_price_ex_vat = _num(base_row.get("market_price_ex_vat_gbp", ""))
    net_fee_drag = _num(base_row.get("net_fee_drag_per_unit_gbp", ""))
    net_fee_status = _net_fee_status(base_row)
    refund_drag = _num(base_row.get("expected_refund_cost_per_unit_gbp", "")) or 0.0
    gross_forward_profit, gross_forward_roi_pct = _gross_forward_fields(
        current_cost=current_cost,
        market_price=market_price,
        refund_drag=refund_drag,
    )
    limit_fields = _purchase_limit_fields(
        current_cost=current_cost,
        market_price_ex_vat=market_price_ex_vat,
        net_fee_drag=net_fee_drag,
        net_fee_status=net_fee_status,
        refund_drag=refund_drag,
    )
    return {
        "asof_utc": asof_utc,
        "seller_sku": str(base_row.get("seller_sku", "")).strip(),
        "asin": str(base_row.get("asin", "")).strip(),
        "title": str(base_row.get("title", "")).strip(),
        "main_image": str(base_row.get("main_image", "")).strip(),
        "supplier_code": str(base_row.get("supplier_code", "")).strip(),
        "supplier_name": str(base_row.get("supplier_name", "")).strip(),
        "recommendation_status": "wait",
        "reason_codes": _reason_csv(reason_codes),
        "recommended_qty_raw": "0",
        "recommended_qty_rounded": "0",
        "target_days_cover": "0",
        "days_cover_available_only": _num_text(days_cover_available_only),
        "days_cover_total_pipeline": _num_text(days_cover_total_pipeline),
        "current_supplier_buy_cost_gbp": _num_text(current_cost),
        "current_supplier_cost_source": str(base_row.get("current_supplier_cost_source", "")).strip(),
        "market_price_gbp": str(base_row.get("market_price_gbp", "")).strip(),
        "market_price_basis_used": str(base_row.get("market_price_basis_used", "")).strip(),
        "forward_roi_pct": _num_text(forward_roi_pct),
        "forward_profit_per_unit_gbp": _num_text(forward_profit),
        "confidence_score": _num_text(confidence_score, allow_blank=False),
        "policy_version": "o_phase1_v1",
        "cost_mode": cost_mode,
        "recommendation_basis": recommendation_basis,
        **limit_fields,
        "max_safe_unit_cost_gbp": str(limit_fields.get("max_target_roi_purchase_price_gbp", "")).strip(),
        "user_price_check_required": str(base_row.get("user_price_check_required", "")).strip(),
        "supplier_cost_review_reason": str(base_row.get("supplier_cost_review_reason", "")).strip(),
        "expected_next_unit_cost_gbp": _num_text(current_cost) if current_cost is not None else str(base_row.get("expected_next_unit_cost_gbp", "")).strip(),
        "price_list_unit_cost_gbp": str(base_row.get("price_list_unit_cost_gbp", "")).strip(),
        "purchase_reference_list_cost_gbp": str(base_row.get("purchase_reference_list_cost_gbp", "")).strip(),
        "actual_paid_unit_cost_gbp": str(base_row.get("actual_paid_unit_cost_gbp", "")).strip(),
        "usual_paid_unit_cost_gbp": str(base_row.get("usual_paid_unit_cost_gbp", "")).strip(),
        "usual_paid_cost_basis": str(base_row.get("usual_paid_cost_basis", "")).strip(),
        "usual_paid_cost_confidence": str(base_row.get("usual_paid_cost_confidence", "")).strip(),
        "usual_paid_sample_count": str(base_row.get("usual_paid_sample_count", "")).strip(),
        "usual_paid_discount_vs_list_pct": str(base_row.get("usual_paid_discount_vs_list_pct", "")).strip(),
        "usual_paid_vs_list_delta_gbp": str(base_row.get("usual_paid_vs_list_delta_gbp", "")).strip(),
        "price_list_change_status": str(base_row.get("price_list_change_status", "")).strip(),
        "price_list_previous_unit_cost_gbp": str(base_row.get("price_list_previous_unit_cost_gbp", "")).strip(),
        "price_list_previous_pack_size": str(base_row.get("price_list_previous_pack_size", "")).strip(),
        "price_list_previous_seen_at_utc": str(base_row.get("price_list_previous_seen_at_utc", "")).strip(),
        "price_list_change_delta_gbp": str(base_row.get("price_list_change_delta_gbp", "")).strip(),
        "price_list_change_pct": str(base_row.get("price_list_change_pct", "")).strip(),
        "confidence_note": confidence_note,
        "blocked_note": confidence_note if confidence_note else "",
        "snooze_until_utc": str(base_row.get("snooze_until_utc", "")).strip(),
        **_net_fee_audit_fields(
            base_row,
            gross_forward_roi_pct=gross_forward_roi_pct,
            gross_forward_profit=gross_forward_profit,
        ),
        **_pack_profile_fields(base_row),
    }


def build_restock_recommendations(root: Path | None = None, *, now_utc: datetime | None = None) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    now = now_utc or _utc_now()

    source_path = root_path / get_o_output_contract("restock_source_view").rel_path
    out_contract = get_o_output_contract("restock_recommendations_live")
    out_path = root_path / out_contract.rel_path

    source_df = read_o_contract_df(root_path, "restock_source_view")
    if source_df.empty:
        out_df = empty_o_contract_df("restock_recommendations_live")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        write_o_contract_df(root_path, "restock_recommendations_live", out_df)
        print({"status": "success", "rows": 0, "snapshot": str(out_path)})
        return out_df

    output_rows: list[dict[str, str]] = []
    for _, row in source_df.iterrows():
        asof_utc = str(row.get("asof_utc", "")).strip() or _utc_now_iso()
        sale_status = str(row.get("sale_status", "")).strip().lower()
        market_basis = str(row.get("market_price_basis_used", "")).strip().upper()
        source_notes = str(row.get("source_notes", "")).strip()
        reason_codes: list[str] = []
        confidence_notes: list[str] = []

        velocity_30d = _num(row.get("velocity_30d", "")) or 0.0
        velocity_7d = _num(row.get("velocity_7d", "")) or 0.0
        velocity_90d = _num(row.get("velocity_90d", "")) or 0.0
        available_now = _num(row.get("available_now", "")) or 0.0
        inbound_working = _num(row.get("amazon_inbound_working", "")) or 0.0
        inbound_shipped = _num(row.get("amazon_inbound_shipped", "")) or 0.0
        inbound_receiving = _num(row.get("amazon_inbound_receiving", "")) or 0.0
        effective_supply = max(0.0, available_now + inbound_working + inbound_shipped + inbound_receiving)

        days_cover_available_only = None
        days_cover_total_pipeline = None
        if velocity_30d > 0:
            days_cover_available_only = available_now / velocity_30d
            days_cover_total_pipeline = effective_supply / velocity_30d

        current_cost = _effective_sell_pack_cost(row)
        market_price = _num(row.get("market_price_gbp", ""))
        market_price_ex_vat = _num(row.get("market_price_ex_vat_gbp", ""))
        net_fee_drag = _num(row.get("net_fee_drag_per_unit_gbp", ""))
        net_fee_status = _net_fee_status(row)
        net_fee_block_reason = _net_fee_block_reason(row)
        refund_drag = _num(row.get("expected_refund_cost_per_unit_gbp", "")) or 0.0
        gross_forward_profit, gross_forward_roi_pct = _gross_forward_fields(
            current_cost=current_cost,
            market_price=market_price,
            refund_drag=refund_drag,
        )
        forward_profit, forward_roi_pct = _net_forward_fields(
            current_cost=current_cost,
            market_price_ex_vat=market_price_ex_vat,
            net_fee_drag=net_fee_drag,
            refund_drag=refund_drag,
            net_fee_status=net_fee_status,
        )
        limit_fields = _purchase_limit_fields(
            current_cost=current_cost,
            market_price_ex_vat=market_price_ex_vat,
            net_fee_drag=net_fee_drag,
            net_fee_status=net_fee_status,
            refund_drag=refund_drag,
        )
        cost_mode_value, recommendation_basis = _recommendation_basis(row, current_cost)
        if _truthy(row.get("user_price_check_required", "")):
            reason_codes.append("SUPPLIER_COST_USER_CONFIRMATION_REQUIRED")

        low_confidence = False
        if "REDUCED_CONFIDENCE" in source_notes or "MISSING_MARKET_CONTEXT" in market_basis:
            low_confidence = True
            confidence_notes.append("reduced_market_context")
            reason_codes.append("LOW_CONFIDENCE_MARKET_CONTEXT")

        stale_out_of_stock = False
        out_of_stock_days = _num(row.get("out_of_stock_days", "")) or 0.0
        stale_flag = _truthy(row.get("demand_stale_flag", "")) or _truthy(row.get("stale_demand_flag", ""))
        if stale_flag or out_of_stock_days >= STALE_OOS_DAYS_THRESHOLD:
            stale_out_of_stock = True
        elif available_now <= 0 and velocity_7d <= 0 and velocity_90d > 0:
            stale_out_of_stock = True
        if stale_out_of_stock:
            confidence_notes.append("stale_out_of_stock_context")
            reason_codes.append("STALE_OUT_OF_STOCK_CONFIDENCE")

        lead_time_days = _num(row.get("lead_time_days", "")) or 0.0
        moq = max(1, int(round(_num(row.get("moq", "")) or 1)))
        pack_size = max(1, int(round(_num(row.get("supplier_pack_size", "")) or 1)))
        bulk_long_lead = _truthy(row.get("bulk_long_lead_flag", "")) or lead_time_days >= LONG_LEAD_DAYS_THRESHOLD
        if bulk_long_lead:
            reason_codes.append("BULK_LONG_LEAD_REVIEW")
            confidence_notes.append("bulk_long_lead_review")

        snooze_until = _parse_utc(row.get("snooze_until_utc", ""))
        if snooze_until is not None and snooze_until > now:
            reason_codes.append("SNOOZED_UNTIL_DATE")
            wait_row = _build_wait_row(
                row,
                asof_utc=asof_utc,
                reason_codes=reason_codes,
                days_cover_available_only=days_cover_available_only,
                days_cover_total_pipeline=days_cover_total_pipeline,
                forward_roi_pct=forward_roi_pct,
                forward_profit=forward_profit,
                confidence_score=55.0,
                confidence_note="snoozed_until_date",
                cost_mode=cost_mode_value,
                recommendation_basis=recommendation_basis,
            )
            output_rows.append(wait_row)
            continue

        if not _is_active_candidate(row):
            reason_codes.append("SALE_STATUS_NOT_ACTIVE")
            wait_row = _build_wait_row(
                row,
                asof_utc=asof_utc,
                reason_codes=reason_codes,
                days_cover_available_only=days_cover_available_only,
                days_cover_total_pipeline=days_cover_total_pipeline,
                forward_roi_pct=forward_roi_pct,
                forward_profit=forward_profit,
                confidence_score=40.0,
                confidence_note="inactive_sale_status",
                cost_mode=cost_mode_value,
                recommendation_basis=recommendation_basis,
            )
            output_rows.append(wait_row)
            continue

        pack_blockers = _pack_block_reason_codes(row)
        if pack_blockers:
            reason_codes.extend(pack_blockers)
            wait_row = _build_wait_row(
                row,
                asof_utc=asof_utc,
                reason_codes=reason_codes,
                days_cover_available_only=days_cover_available_only,
                days_cover_total_pipeline=days_cover_total_pipeline,
                forward_roi_pct=forward_roi_pct,
                forward_profit=forward_profit,
                confidence_score=30.0,
                confidence_note="pack_profile_blocked",
                cost_mode=cost_mode_value,
                recommendation_basis=recommendation_basis,
            )
            output_rows.append(wait_row)
            continue

        if velocity_30d < LOW_DEMAND_FLOOR_UNITS_PER_DAY:
            reason_codes.append("WEAK_DEMAND_SIGNAL")
            wait_row = _build_wait_row(
                row,
                asof_utc=asof_utc,
                reason_codes=reason_codes,
                days_cover_available_only=days_cover_available_only,
                days_cover_total_pipeline=days_cover_total_pipeline,
                forward_roi_pct=forward_roi_pct,
                forward_profit=forward_profit,
                confidence_score=50.0,
                confidence_note="weak_demand",
                cost_mode=cost_mode_value,
                recommendation_basis=recommendation_basis,
            )
            output_rows.append(wait_row)
            continue

        if net_fee_block_reason:
            reason_codes.append(net_fee_block_reason)
            wait_row = _build_wait_row(
                row,
                asof_utc=asof_utc,
                reason_codes=reason_codes,
                days_cover_available_only=days_cover_available_only,
                days_cover_total_pipeline=days_cover_total_pipeline,
                forward_roi_pct=forward_roi_pct,
                forward_profit=forward_profit,
                confidence_score=35.0,
                confidence_note="net_fee_model_blocked",
                cost_mode=cost_mode_value,
                recommendation_basis=recommendation_basis,
            )
            output_rows.append(wait_row)
            continue

        if forward_roi_pct is None:
            if current_cost is None or current_cost <= 0:
                reason_codes.append("BLOCKED_MISSING_COST_INPUT")
            if market_price is None or market_price <= 0:
                reason_codes.append("BLOCKED_MISSING_MARKET_PRICE_INPUT")
            if market_price_ex_vat is None or market_price_ex_vat <= 0:
                reason_codes.append("BLOCKED_MISSING_NET_MARKET_PRICE_INPUT")
            if net_fee_drag is None or net_fee_drag < 0:
                reason_codes.append("BLOCKED_MISSING_NET_FEE_INPUT")
            if not reason_codes or all(code in {"LOW_CONFIDENCE_MARKET_CONTEXT", "STALE_OUT_OF_STOCK_CONFIDENCE", "BULK_LONG_LEAD_REVIEW"} for code in reason_codes):
                reason_codes.append("BLOCKED_MISSING_ROI_INPUT")
            wait_row = _build_wait_row(
                row,
                asof_utc=asof_utc,
                reason_codes=reason_codes,
                days_cover_available_only=days_cover_available_only,
                days_cover_total_pipeline=days_cover_total_pipeline,
                forward_roi_pct=forward_roi_pct,
                forward_profit=forward_profit,
                confidence_score=35.0,
                confidence_note="missing_forward_roi_inputs",
                cost_mode=cost_mode_value,
                recommendation_basis=recommendation_basis,
            )
            output_rows.append(wait_row)
            continue

        if forward_roi_pct < ROI_MIN_THRESHOLD:
            if limit_fields.get("purchase_price_safety_status") == "above_break_even_max":
                reason_codes.append("COST_ABOVE_BREAK_EVEN_MAX_PURCHASE_PRICE")
            elif limit_fields.get("purchase_price_safety_status") == "above_target_roi_max":
                reason_codes.append("EXPECTED_COST_ABOVE_TARGET_ROI_MAX_PURCHASE_PRICE")
            else:
                reason_codes.append("ROI_BELOW_MIN_THRESHOLD")
            wait_row = _build_wait_row(
                row,
                asof_utc=asof_utc,
                reason_codes=reason_codes,
                days_cover_available_only=days_cover_available_only,
                days_cover_total_pipeline=days_cover_total_pipeline,
                forward_roi_pct=forward_roi_pct,
                forward_profit=forward_profit,
                confidence_score=60.0,
                confidence_note="roi_below_10_percent",
                cost_mode=cost_mode_value,
                recommendation_basis=recommendation_basis,
            )
            output_rows.append(wait_row)
            continue

        recommendation_status = "test_restock"
        target_days = TEST_RESTOCK_TARGET_DAYS
        if forward_roi_pct >= ROI_FULL_THRESHOLD:
            recommendation_status = "full_restock"
            target_days = FULL_RESTOCK_TARGET_DAYS

        if stale_out_of_stock and recommendation_status == "full_restock":
            recommendation_status = "test_restock"
            target_days = TEST_RESTOCK_TARGET_DAYS
            reason_codes.append("STALE_OUT_OF_STOCK_DOWNGRADE")

        if low_confidence and recommendation_status == "full_restock":
            recommendation_status = "test_restock"
            target_days = TEST_RESTOCK_TARGET_DAYS
            reason_codes.append("LOW_CONFIDENCE_DOWNGRADE_TO_TEST")

        if low_confidence and recommendation_status == "test_restock" and forward_roi_pct < 12.0:
            reason_codes.append("WEAK_CONFIDENCE_WAIT")
            wait_row = _build_wait_row(
                row,
                asof_utc=asof_utc,
                reason_codes=reason_codes,
                days_cover_available_only=days_cover_available_only,
                days_cover_total_pipeline=days_cover_total_pipeline,
                forward_roi_pct=forward_roi_pct,
                forward_profit=forward_profit,
                confidence_score=45.0,
                confidence_note="low_confidence_mid_band",
                cost_mode=cost_mode_value,
                recommendation_basis=recommendation_basis,
            )
            output_rows.append(wait_row)
            continue

        if bulk_long_lead and recommendation_status in {"full_restock", "test_restock"}:
            target_days = min(TARGET_DAYS_CAP, int(round(target_days + max(0.0, min(lead_time_days, 60.0)))))

        required_units = max(0.0, (target_days * velocity_30d) - effective_supply)
        recommended_qty_raw = int(math.ceil(required_units))
        if recommended_qty_raw <= 0:
            reason_codes.append("SUFFICIENT_EFFECTIVE_SUPPLY")
            wait_row = _build_wait_row(
                row,
                asof_utc=asof_utc,
                reason_codes=reason_codes,
                days_cover_available_only=days_cover_available_only,
                days_cover_total_pipeline=days_cover_total_pipeline,
                forward_roi_pct=forward_roi_pct,
                forward_profit=forward_profit,
                confidence_score=75.0,
                confidence_note="supply_already_sufficient",
                cost_mode=cost_mode_value,
                recommendation_basis=recommendation_basis,
            )
            output_rows.append(wait_row)
            continue

        if recommendation_status == "test_restock":
            if current_cost is None or current_cost <= 0:
                reason_codes.append("BLOCKED_MISSING_COST_INPUT")
                wait_row = _build_wait_row(
                    row,
                    asof_utc=asof_utc,
                    reason_codes=reason_codes,
                    days_cover_available_only=days_cover_available_only,
                    days_cover_total_pipeline=days_cover_total_pipeline,
                    forward_roi_pct=forward_roi_pct,
                    forward_profit=forward_profit,
                    confidence_score=35.0,
                    confidence_note="missing_cost_for_test_spend_cap",
                    cost_mode=cost_mode_value,
                    recommendation_basis=recommendation_basis,
                )
                output_rows.append(wait_row)
                continue
            cap_units = int(math.floor(MAX_TEST_SPEND_GBP / current_cost))
            if cap_units <= 0:
                reason_codes.append("TEST_SPEND_CAP_PREVENTS_BUY")
                wait_row = _build_wait_row(
                    row,
                    asof_utc=asof_utc,
                    reason_codes=reason_codes,
                    days_cover_available_only=days_cover_available_only,
                    days_cover_total_pipeline=days_cover_total_pipeline,
                    forward_roi_pct=forward_roi_pct,
                    forward_profit=forward_profit,
                    confidence_score=60.0,
                    confidence_note="test_spend_cap_reached",
                    cost_mode=cost_mode_value,
                    recommendation_basis=recommendation_basis,
                )
                output_rows.append(wait_row)
                continue
            if recommended_qty_raw > cap_units:
                recommended_qty_raw = cap_units
                reason_codes.append("TEST_SPEND_CAP_APPLIED")

        recommended_qty_rounded = _round_qty(recommended_qty_raw, pack_size, moq)
        if recommended_qty_rounded <= 0:
            reason_codes.append("QTY_ROUNDING_RESULT_ZERO")
            wait_row = _build_wait_row(
                row,
                asof_utc=asof_utc,
                reason_codes=reason_codes,
                days_cover_available_only=days_cover_available_only,
                days_cover_total_pipeline=days_cover_total_pipeline,
                forward_roi_pct=forward_roi_pct,
                forward_profit=forward_profit,
                confidence_score=60.0,
                confidence_note="qty_rounding_zero",
                cost_mode=cost_mode_value,
                recommendation_basis=recommendation_basis,
            )
            output_rows.append(wait_row)
            continue

        confidence_score = 100.0
        if low_confidence:
            confidence_score -= 35.0
        if stale_out_of_stock:
            confidence_score -= 20.0
        if bulk_long_lead:
            confidence_score -= 10.0
        if recommendation_status == "test_restock":
            confidence_score -= 5.0
        confidence_score = max(0.0, min(100.0, confidence_score))

        output_rows.append(
            {
                "asof_utc": asof_utc,
                "seller_sku": str(row.get("seller_sku", "")).strip(),
                "asin": str(row.get("asin", "")).strip(),
                "title": str(row.get("title", "")).strip(),
                "main_image": str(row.get("main_image", "")).strip(),
                "supplier_code": str(row.get("supplier_code", "")).strip(),
                "supplier_name": str(row.get("supplier_name", "")).strip(),
                "recommendation_status": recommendation_status,
                "reason_codes": _reason_csv(reason_codes),
                "recommended_qty_raw": str(recommended_qty_raw),
                "recommended_qty_rounded": str(recommended_qty_rounded),
                "target_days_cover": str(target_days),
                "days_cover_available_only": _num_text(days_cover_available_only),
                "days_cover_total_pipeline": _num_text(days_cover_total_pipeline),
                "current_supplier_buy_cost_gbp": _num_text(current_cost),
                "current_supplier_cost_source": str(row.get("current_supplier_cost_source", "")).strip(),
                "market_price_gbp": str(row.get("market_price_gbp", "")).strip(),
                "market_price_basis_used": str(row.get("market_price_basis_used", "")).strip(),
                "forward_roi_pct": _num_text(forward_roi_pct),
                "forward_profit_per_unit_gbp": _num_text(forward_profit),
                "confidence_score": _num_text(confidence_score, allow_blank=False),
                "policy_version": "o_phase1_v1",
                "cost_mode": cost_mode_value,
                "recommendation_basis": recommendation_basis,
                **limit_fields,
                "max_safe_unit_cost_gbp": str(limit_fields.get("max_target_roi_purchase_price_gbp", "")).strip(),
                "user_price_check_required": str(row.get("user_price_check_required", "")).strip(),
                "supplier_cost_review_reason": str(row.get("supplier_cost_review_reason", "")).strip(),
                "expected_next_unit_cost_gbp": _num_text(current_cost) if current_cost is not None else str(row.get("expected_next_unit_cost_gbp", "")).strip(),
                "price_list_unit_cost_gbp": str(row.get("price_list_unit_cost_gbp", "")).strip(),
                "purchase_reference_list_cost_gbp": str(row.get("purchase_reference_list_cost_gbp", "")).strip(),
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
                "confidence_note": "|".join(confidence_notes),
                "blocked_note": "",
                "snooze_until_utc": str(row.get("snooze_until_utc", "")).strip(),
                **_net_fee_audit_fields(
                    row,
                    gross_forward_roi_pct=gross_forward_roi_pct,
                    gross_forward_profit=gross_forward_profit,
                ),
                **_pack_profile_fields(row),
            }
        )

    out_df = pd.DataFrame(output_rows)
    for col in [*out_contract.required_columns, *out_contract.optional_columns]:
        if col not in out_df.columns:
            out_df[col] = ""
    out_df = out_df[[*out_contract.required_columns, *out_contract.optional_columns] + [c for c in out_df.columns if c not in {*out_contract.required_columns, *out_contract.optional_columns}]]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_o_contract_df(root_path, "restock_recommendations_live", out_df)
    print({"status": "success", "rows": len(out_df), "snapshot": str(out_path)})
    return out_df


def main() -> None:
    build_restock_recommendations()


if __name__ == "__main__":
    main()
