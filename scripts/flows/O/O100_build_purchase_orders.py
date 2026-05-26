from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.flows.O._contract_io import empty_o_contract_df, read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract
from scripts.flows.O._schemas import get_o_output_contract


APPROVAL_ACTIONS = {"approve_full_restock", "approve_test_restock"}
NON_BUY_ACTIONS = {"wait", "skip", "snooze"}
BUYABLE_FINAL_STATUSES = {"full_restock", "test_restock"}


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


def _positive_int(value: object, *, default: int = 0) -> int:
    parsed = _num(value)
    if parsed is None or parsed <= 0:
        return default
    rounded = int(round(parsed))
    if abs(parsed - rounded) > 0.000001:
        return default
    return rounded


def _round_up_to_multiple(value: int, multiple: int) -> int:
    if value <= 0 or multiple <= 1:
        return max(0, value)
    remainder = value % multiple
    if remainder == 0:
        return value
    return value + (multiple - remainder)


def _note_codes(value: object) -> set[str]:
    text = _normalize_text(value).lower().replace(",", "|")
    codes = {code.strip() for code in text.split("|") if code.strip()}
    aliases = {
        "pack_profile_missing": "missing_pack_profile",
        "pack_profile_unconfirmed": "unconfirmed_pack_profile",
        "pack_profile_invalid": "invalid_component_conversion",
        "pack_supplier_cost_basis_missing": "missing_supplier_cost_basis",
        "pack_supplier_box_alignment_invalid": "invalid_supplier_box_alignment",
    }
    return codes | {aliases[code] for code in codes if code in aliases}


def _pack_draft_hold(context: dict[str, str]) -> tuple[str, str] | None:
    status = _normalize_text(context.get("pack_profile_status", "")).lower()
    supplier_cost_basis = _normalize_text(context.get("supplier_cost_basis_raw", "")).lower()
    quantity_strategy = _normalize_text(context.get("quantity_strategy", "")).lower()
    note_codes = _note_codes(context.get("source_notes", ""))

    if status in {"missing_pack_profile", "missing"} or "missing_pack_profile" in note_codes:
        return "missing_pack_profile", "pack profile is missing, so PO draft cannot trust the buy quantity"
    if status in {"unconfirmed_pack_profile", "draft", "pending", "provisional"} or "unconfirmed_pack_profile" in note_codes:
        return "unconfirmed_pack_profile", "pack profile is not confirmed, so PO draft cannot trust the buy quantity"
    if status == "invalid" or "invalid_component_conversion" in note_codes or "pack_title_profile_mismatch" in note_codes:
        return "invalid_pack_profile", "pack profile is invalid, so PO draft cannot trust the buy quantity"
    if status == "special_order_profile_required" or "special_order_profile_required" in note_codes:
        return "special_order_profile_required", "special order profile is required before this SKU can draft a PO line"
    if status not in {"", "default_normal"} and supplier_cost_basis == "":
        return "missing_supplier_cost_basis", "pack profile is present but supplier cost basis is missing"
    if quantity_strategy == "preferred_carton_multiple":
        confirmed_status = status in {"confirmed", "approved"}
        has_pack_fields = (
            _positive_int(context.get("components_per_sell_pack", ""), default=0) > 0
            and _positive_int(context.get("supplier_box_components", ""), default=0) > 0
            and _positive_int(context.get("preferred_order_sell_packs", ""), default=0) > 0
        )
        isolated = _normalize_text(context.get("isolate_from_normal_po", "")).lower() in {"1", "true", "yes", "y", "on"}
        has_hazmat_group = _normalize_text(context.get("hazmat_group", "")) != ""
        if not confirmed_status or not has_pack_fields or not isolated or not has_hazmat_group:
            return "missing_special_order_pack_profile", "special carton order needs a confirmed pack profile, box size, preferred order size, and isolation group"
    return None


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    return df


def _empty_contract_df(contract_name: str) -> pd.DataFrame:
    return empty_o_contract_df(contract_name)


def _read_or_init_csv(root_path: Path, contract_name: str) -> pd.DataFrame:
    return read_o_contract_df(root_path, contract_name)


def _parse_utc(value: object) -> datetime | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    parsed = pd.to_datetime(raw, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def _decision_identity_key(row: pd.Series) -> str:
    sku = _normalize_key(row.get("seller_sku", ""))
    if sku:
        return f"sku:{sku}"
    asin = _normalize_key(row.get("asin", ""))
    if asin:
        return f"asin:{asin}"
    return ""


def _build_lookup(df: pd.DataFrame) -> tuple[dict[str, pd.Series], dict[str, pd.Series]]:
    by_sku: dict[str, pd.Series] = {}
    by_asin: dict[str, pd.Series] = {}
    for _, row in df.iterrows():
        sku = _normalize_key(row.get("seller_sku", ""))
        asin = _normalize_key(row.get("asin", ""))
        if sku and sku not in by_sku:
            by_sku[sku] = row
        if asin and asin not in by_asin:
            by_asin[asin] = row
    return by_sku, by_asin


def _uses_legacy_purchase_list_source(value: object) -> bool:
    return "legacy_purchase_list" in _normalize_text(value).lower()


def _resolve_context(
    decision: pd.Series,
    rec_by_sku: dict[str, pd.Series],
    rec_by_asin: dict[str, pd.Series],
    src_by_sku: dict[str, pd.Series],
    src_by_asin: dict[str, pd.Series],
    bridge_by_sku: dict[str, pd.Series],
    bridge_by_asin: dict[str, pd.Series],
) -> dict[str, str]:
    sku_norm = _normalize_key(decision.get("seller_sku", ""))
    asin_norm = _normalize_key(decision.get("asin", ""))
    rec = rec_by_sku.get(sku_norm)
    if rec is None:
        rec = rec_by_asin.get(asin_norm)
    src = src_by_sku.get(sku_norm)
    if src is None:
        src = src_by_asin.get(asin_norm)
    bridge = bridge_by_sku.get(sku_norm)
    if bridge is None:
        bridge = bridge_by_asin.get(asin_norm)
    legacy_source = _uses_legacy_purchase_list_source(decision.get("source_reference", ""))
    if legacy_source and bridge is not None:
        src = bridge
    elif src is None and bridge is not None:
        src = bridge

    def pick(*candidates: object) -> str:
        for item in candidates:
            text = _normalize_text(item)
            if text != "":
                return text
        return ""

    return {
        "seller_sku": pick(decision.get("seller_sku", ""), rec.get("seller_sku", "") if rec is not None else "", src.get("seller_sku", "") if src is not None else ""),
        "asin": pick(decision.get("asin", ""), rec.get("asin", "") if rec is not None else "", src.get("asin", "") if src is not None else ""),
        "supplier_code": (
            _normalize_text(src.get("supplier_code", "")) if legacy_source and src is not None else
            pick(rec.get("supplier_code", "") if rec is not None else "", src.get("supplier_code", "") if src is not None else "")
        ),
        "supplier_name": pick(
            src.get("supplier_name", "") if legacy_source and src is not None else "",
            rec.get("supplier_name", "") if rec is not None else "",
            src.get("supplier_name", "") if src is not None else "",
        ),
        "title": pick(src.get("title", "") if src is not None else "", rec.get("title", "") if rec is not None else ""),
        "supplier_sku": pick(src.get("supplier_sku", "") if src is not None else ""),
        "barcode": pick(src.get("barcode", "") if src is not None else ""),
        "source_bridge_row": pick(src.get("source_row_number", "") if src is not None and _uses_legacy_purchase_list_source(src.get("source_system", "")) else ""),
        "source_bridge_reference": pick(src.get("source_reference", "") if src is not None and _uses_legacy_purchase_list_source(src.get("source_system", "")) else ""),
        "supplier_pack_size": pick(src.get("supplier_pack_size", "") if src is not None else "", "1"),
        "moq": pick(src.get("moq", "") if src is not None else "", "1"),
        "valid_order_step": pick(src.get("valid_order_step", "") if src is not None else "", src.get("supplier_pack_size", "") if src is not None else "", "1"),
        "lead_time_days": pick(src.get("lead_time_days", "") if src is not None else "", "0"),
        "components_per_sell_pack": pick(
            src.get("components_per_sell_pack", "") if src is not None else "",
            rec.get("components_per_sell_pack", "") if rec is not None else "",
            src.get("sell_pack_qty", "") if src is not None else "",
            src.get("amazon_pack_size", "") if src is not None else "",
            "1",
        ),
        "component_unit_label": pick(src.get("component_unit_label", "") if src is not None else "", rec.get("component_unit_label", "") if rec is not None else "", "unit"),
        "supplier_cost_basis": pick(src.get("supplier_cost_basis", "") if src is not None else "", rec.get("supplier_cost_basis", "") if rec is not None else "", "sell_pack"),
        "supplier_cost_basis_raw": pick(src.get("supplier_cost_basis", "") if src is not None else "", rec.get("supplier_cost_basis", "") if rec is not None else ""),
        "supplier_box_components": pick(src.get("supplier_box_components", "") if src is not None else "", rec.get("supplier_box_components", "") if rec is not None else "", src.get("supplier_case_qty", "") if src is not None else "", ""),
        "preferred_order_sell_packs": pick(src.get("preferred_order_sell_packs", "") if src is not None else "", rec.get("preferred_order_sell_packs", "") if rec is not None else "", src.get("valid_order_step", "") if src is not None else "", ""),
        "preferred_order_components": pick(src.get("preferred_order_components", "") if src is not None else "", rec.get("preferred_order_components", "") if rec is not None else "", ""),
        "preferred_supplier_boxes": pick(src.get("preferred_supplier_boxes", "") if src is not None else "", rec.get("preferred_supplier_boxes", "") if rec is not None else "", ""),
        "quantity_strategy": pick(src.get("quantity_strategy", "") if src is not None else "", rec.get("quantity_strategy", "") if rec is not None else "", "as_needed"),
        "hazmat_group": pick(src.get("hazmat_group", "") if src is not None else "", rec.get("hazmat_group", "") if rec is not None else "", ""),
        "isolate_from_normal_po": pick(src.get("isolate_from_normal_po", "") if src is not None else "", rec.get("isolate_from_normal_po", "") if rec is not None else "", "0"),
        "target_carton_weight_kg": pick(src.get("target_carton_weight_kg", "") if src is not None else "", rec.get("target_carton_weight_kg", "") if rec is not None else "", ""),
        "pack_profile_status": pick(src.get("pack_profile_status", "") if src is not None else "", rec.get("pack_profile_status", "") if rec is not None else "", ""),
        "pack_conversion_note": pick(src.get("pack_conversion_note", "") if src is not None else "", ""),
        "source_notes": pick(src.get("source_notes", "") if src is not None else "", rec.get("blocked_note", "") if rec is not None else "", rec.get("reason_codes", "") if rec is not None else ""),
        "recommendation_basis": pick(decision.get("recommendation_basis", ""), rec.get("recommendation_basis", "") if rec is not None else ""),
        "cost_mode": pick(decision.get("cost_mode", ""), rec.get("cost_mode", "") if rec is not None else "", "live"),
    }


def _latest_decisions(decisions_df: pd.DataFrame) -> pd.DataFrame:
    work = decisions_df.copy()
    work["_decision_ts"] = pd.to_datetime(work.get("decision_utc", ""), errors="coerce", utc=True)
    work["_event_ts"] = pd.to_datetime(work.get("event_utc", ""), errors="coerce", utc=True)
    work["_identity_key"] = work.apply(_decision_identity_key, axis=1)
    work = work[work["_identity_key"] != ""]
    work = work.sort_values(by=["_identity_key", "_decision_ts", "_event_ts"], ascending=[True, True, True], kind="stable")
    work = work.groupby("_identity_key", sort=False).tail(1)
    return work


def build_purchase_orders(root: Path | None = None, *, build_utc: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    build_dt = _parse_utc(build_utc) or _utc_now()
    build_iso = build_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    decisions_path = root_path / get_o_output_contract("restock_decisions_log").rel_path
    rec_path = root_path / get_o_output_contract("restock_recommendations_live").rel_path
    src_path = root_path / get_o_output_contract("restock_source_view").rel_path
    po_header_path = root_path / get_o_output_contract("purchase_orders_live").rel_path
    po_lines_path = root_path / get_o_output_contract("purchase_order_lines_live").rel_path
    holds_path = root_path / get_o_output_contract("purchase_order_draft_holds").rel_path

    decisions_df = _read_or_init_csv(root_path, "restock_decisions_log")
    rec_df = _read_or_init_csv(root_path, "restock_recommendations_live")
    src_df = _read_or_init_csv(root_path, "restock_source_view")
    bridge_df = _read_or_init_csv(root_path, "legacy_purchase_list_bridge")

    if decisions_df.empty:
        headers_df = _empty_contract_df("purchase_orders_live")
        lines_df = _empty_contract_df("purchase_order_lines_live")
        holds_df = _empty_contract_df("purchase_order_draft_holds")
        po_header_path.parent.mkdir(parents=True, exist_ok=True)
        write_o_contract_df(root_path, "purchase_orders_live", headers_df)
        write_o_contract_df(root_path, "purchase_order_lines_live", lines_df)
        write_o_contract_df(root_path, "purchase_order_draft_holds", holds_df)
        print(
            {
                "status": "success",
                "po_headers": 0,
                "po_lines": 0,
                "holds": 0,
                "notes": "no decisions available",
            }
        )
        return headers_df, lines_df, holds_df

    latest = _latest_decisions(decisions_df)
    rec_by_sku, rec_by_asin = _build_lookup(rec_df)
    src_by_sku, src_by_asin = _build_lookup(src_df)
    bridge_df = bridge_df[
        bridge_df.get("bridge_status", pd.Series(dtype=str)).map(lambda v: _normalize_text(v).lower() in {"", "ready"})
    ].copy() if not bridge_df.empty else bridge_df
    bridge_by_sku, bridge_by_asin = _build_lookup(bridge_df)

    po_line_candidates: list[dict[str, str]] = []
    hold_rows: list[dict[str, str]] = []

    for _, decision in latest.iterrows():
        action = _normalize_text(decision.get("decision_action", "")).lower()
        final_status = _normalize_text(decision.get("final_decision_status", "")).lower()
        context = _resolve_context(decision, rec_by_sku, rec_by_asin, src_by_sku, src_by_asin, bridge_by_sku, bridge_by_asin)

        seller_sku = context["seller_sku"]
        asin = context["asin"]
        supplier_code = context["supplier_code"]
        supplier_name = context["supplier_name"]
        event_id = _normalize_text(decision.get("event_id", ""))
        recommendation_asof = _normalize_text(decision.get("recommendation_asof_utc", ""))
        confirmed_qty_num = _num(decision.get("confirmed_qty", ""))
        confirmed_cost_num = _num(decision.get("confirmed_unit_cost", ""))

        if action in NON_BUY_ACTIONS:
            continue

        if action not in APPROVAL_ACTIONS and action != "bulk_review":
            hold_rows.append(
                {
                    "hold_utc": build_iso,
                    "event_id": event_id,
                    "seller_sku": seller_sku,
                    "asin": asin,
                    "decision_action": action,
                    "final_decision_status": final_status,
                    "hold_reason": "unsupported_decision_action",
                    "hold_note": "decision action does not map to PO draft build",
                    "confirmed_qty": _normalize_text(decision.get("confirmed_qty", "")),
                    "confirmed_unit_cost": _normalize_text(decision.get("confirmed_unit_cost", "")),
                    "supplier_code": supplier_code,
                    "supplier_name": supplier_name,
                    "cost_mode": context["cost_mode"],
                    "recommendation_basis": context["recommendation_basis"],
                    "source_reference": _normalize_text(decision.get("source_reference", "")),
                    "recommendation_asof_utc": recommendation_asof,
                }
            )
            continue

        if action in APPROVAL_ACTIONS and final_status not in BUYABLE_FINAL_STATUSES:
            hold_rows.append(
                {
                    "hold_utc": build_iso,
                    "event_id": event_id,
                    "seller_sku": seller_sku,
                    "asin": asin,
                    "decision_action": action,
                    "final_decision_status": final_status,
                    "hold_reason": "final_status_not_buyable",
                    "hold_note": "approval action was recalculated to non-buyable final status",
                    "confirmed_qty": _normalize_text(decision.get("confirmed_qty", "")),
                    "confirmed_unit_cost": _normalize_text(decision.get("confirmed_unit_cost", "")),
                    "supplier_code": supplier_code,
                    "supplier_name": supplier_name,
                    "cost_mode": context["cost_mode"],
                    "recommendation_basis": context["recommendation_basis"],
                    "source_reference": _normalize_text(decision.get("source_reference", "")),
                    "recommendation_asof_utc": recommendation_asof,
                }
            )
            continue

        if action in APPROVAL_ACTIONS and _normalize_text(decision.get("confirmed_price_safety_status", "")) == "confirmed_over_max_blocked":
            hold_rows.append(
                {
                    "hold_utc": build_iso,
                    "event_id": event_id,
                    "seller_sku": seller_sku,
                    "asin": asin,
                    "decision_action": action,
                    "final_decision_status": final_status,
                    "hold_reason": "price_safety_blocked",
                    "hold_note": "confirmed unit cost is above max safe cost, so PO draft build is blocked",
                    "confirmed_qty": _normalize_text(decision.get("confirmed_qty", "")),
                    "confirmed_unit_cost": _normalize_text(decision.get("confirmed_unit_cost", "")),
                    "supplier_code": supplier_code,
                    "supplier_name": supplier_name,
                    "cost_mode": context["cost_mode"],
                    "recommendation_basis": context["recommendation_basis"],
                    "source_reference": _normalize_text(decision.get("source_reference", "")),
                    "recommendation_asof_utc": recommendation_asof,
                }
            )
            continue

        if confirmed_qty_num is None or confirmed_qty_num <= 0:
            hold_rows.append(
                {
                    "hold_utc": build_iso,
                    "event_id": event_id,
                    "seller_sku": seller_sku,
                    "asin": asin,
                    "decision_action": action,
                    "final_decision_status": final_status,
                    "hold_reason": "missing_confirmed_qty",
                    "hold_note": "decision is missing confirmed_qty required for PO draft",
                    "confirmed_qty": _normalize_text(decision.get("confirmed_qty", "")),
                    "confirmed_unit_cost": _normalize_text(decision.get("confirmed_unit_cost", "")),
                    "supplier_code": supplier_code,
                    "supplier_name": supplier_name,
                    "cost_mode": context["cost_mode"],
                    "recommendation_basis": context["recommendation_basis"],
                    "source_reference": _normalize_text(decision.get("source_reference", "")),
                    "recommendation_asof_utc": recommendation_asof,
                }
            )
            continue

        if confirmed_cost_num is None or confirmed_cost_num <= 0:
            hold_rows.append(
                {
                    "hold_utc": build_iso,
                    "event_id": event_id,
                    "seller_sku": seller_sku,
                    "asin": asin,
                    "decision_action": action,
                    "final_decision_status": final_status,
                    "hold_reason": "missing_confirmed_cost",
                    "hold_note": "decision is missing confirmed_unit_cost required for PO draft",
                    "confirmed_qty": _normalize_text(decision.get("confirmed_qty", "")),
                    "confirmed_unit_cost": _normalize_text(decision.get("confirmed_unit_cost", "")),
                    "supplier_code": supplier_code,
                    "supplier_name": supplier_name,
                    "cost_mode": context["cost_mode"],
                    "recommendation_basis": context["recommendation_basis"],
                    "source_reference": _normalize_text(decision.get("source_reference", "")),
                    "recommendation_asof_utc": recommendation_asof,
                }
            )
            continue

        if _normalize_key(supplier_code) == "" and _normalize_text(supplier_name) == "":
            hold_rows.append(
                {
                    "hold_utc": build_iso,
                    "event_id": event_id,
                    "seller_sku": seller_sku,
                    "asin": asin,
                    "decision_action": action,
                    "final_decision_status": final_status,
                    "hold_reason": "missing_supplier_identity",
                    "hold_note": "supplier_code and supplier_name both missing",
                    "confirmed_qty": _normalize_text(decision.get("confirmed_qty", "")),
                    "confirmed_unit_cost": _normalize_text(decision.get("confirmed_unit_cost", "")),
                    "supplier_code": supplier_code,
                    "supplier_name": supplier_name,
                    "cost_mode": context["cost_mode"],
                    "recommendation_basis": context["recommendation_basis"],
                    "source_reference": _normalize_text(decision.get("source_reference", "")),
                    "recommendation_asof_utc": recommendation_asof,
                }
            )
            continue

        pack_hold = _pack_draft_hold(context)
        if pack_hold is not None:
            hold_reason, hold_note = pack_hold
            hold_rows.append(
                {
                    "hold_utc": build_iso,
                    "event_id": event_id,
                    "seller_sku": seller_sku,
                    "asin": asin,
                    "decision_action": action,
                    "final_decision_status": final_status,
                    "hold_reason": hold_reason,
                    "hold_note": hold_note,
                    "confirmed_qty": _normalize_text(decision.get("confirmed_qty", "")),
                    "confirmed_unit_cost": _normalize_text(decision.get("confirmed_unit_cost", "")),
                    "supplier_code": supplier_code,
                    "supplier_name": supplier_name,
                    "cost_mode": context["cost_mode"],
                    "recommendation_basis": context["recommendation_basis"],
                    "source_reference": _normalize_text(decision.get("source_reference", "")),
                    "recommendation_asof_utc": recommendation_asof,
                }
            )
            continue

        confirmed_qty_int = _positive_int(confirmed_qty_num, default=0)
        order_step = _positive_int(context.get("valid_order_step", ""), default=0)
        supplier_pack_size = _positive_int(context.get("supplier_pack_size", ""), default=1)
        moq = _positive_int(context.get("moq", ""), default=1)
        required_multiple = max(order_step, supplier_pack_size, 1)
        if confirmed_qty_int <= 0 or abs(float(confirmed_qty_num) - confirmed_qty_int) > 0.000001:
            hold_rows.append(
                {
                    "hold_utc": build_iso,
                    "event_id": event_id,
                    "seller_sku": seller_sku,
                    "asin": asin,
                    "decision_action": action,
                    "final_decision_status": final_status,
                    "hold_reason": "confirmed_qty_not_whole_units",
                    "hold_note": "confirmed quantity must be a whole number before PO draft build",
                    "confirmed_qty": _normalize_text(decision.get("confirmed_qty", "")),
                    "confirmed_unit_cost": _normalize_text(decision.get("confirmed_unit_cost", "")),
                    "supplier_code": supplier_code,
                    "supplier_name": supplier_name,
                    "cost_mode": context["cost_mode"],
                    "recommendation_basis": context["recommendation_basis"],
                    "source_reference": _normalize_text(decision.get("source_reference", "")),
                    "recommendation_asof_utc": recommendation_asof,
                }
            )
            continue

        if moq > 1 and confirmed_qty_int < moq:
            hold_rows.append(
                {
                    "hold_utc": build_iso,
                    "event_id": event_id,
                    "seller_sku": seller_sku,
                    "asin": asin,
                    "decision_action": action,
                    "final_decision_status": final_status,
                    "hold_reason": "confirmed_qty_below_moq",
                    "hold_note": f"confirmed quantity must be at least the supplier minimum of {moq}",
                    "confirmed_qty": _normalize_text(decision.get("confirmed_qty", "")),
                    "confirmed_unit_cost": _normalize_text(decision.get("confirmed_unit_cost", "")),
                    "supplier_code": supplier_code,
                    "supplier_name": supplier_name,
                    "cost_mode": context["cost_mode"],
                    "recommendation_basis": context["recommendation_basis"],
                    "source_reference": _normalize_text(decision.get("source_reference", "")),
                    "recommendation_asof_utc": recommendation_asof,
                }
            )
            continue

        if required_multiple > 1 and confirmed_qty_int % required_multiple != 0:
            hold_rows.append(
                {
                    "hold_utc": build_iso,
                    "event_id": event_id,
                    "seller_sku": seller_sku,
                    "asin": asin,
                    "decision_action": action,
                    "final_decision_status": final_status,
                    "hold_reason": "confirmed_qty_not_pack_multiple",
                    "hold_note": f"confirmed quantity must be ordered in multiples of {required_multiple}",
                    "confirmed_qty": _normalize_text(decision.get("confirmed_qty", "")),
                    "confirmed_unit_cost": _normalize_text(decision.get("confirmed_unit_cost", "")),
                    "supplier_code": supplier_code,
                    "supplier_name": supplier_name,
                    "cost_mode": context["cost_mode"],
                    "recommendation_basis": context["recommendation_basis"],
                    "source_reference": _normalize_text(decision.get("source_reference", "")),
                    "recommendation_asof_utc": recommendation_asof,
                }
            )
            continue

        lead_days = _num(context["lead_time_days"]) or 0.0
        expected_arrival = ""
        if lead_days > 0:
            expected_arrival = (build_dt + timedelta(days=int(round(lead_days)))).strftime("%Y-%m-%dT%H:%M:%SZ")

        confirmed_sell_packs = int(round(confirmed_qty_num))
        components_per_sell_pack = _positive_int(context["components_per_sell_pack"], default=1)
        component_unit_label = _normalize_text(context["component_unit_label"]) or "unit"
        supplier_box_components = _positive_int(context["supplier_box_components"], default=0)
        preferred_order_sell_packs = _positive_int(context["preferred_order_sell_packs"], default=0)
        preferred_order_components = _positive_int(context["preferred_order_components"], default=0)
        preferred_supplier_boxes = _positive_int(context["preferred_supplier_boxes"], default=0)
        quantity_strategy = _normalize_text(context["quantity_strategy"]).lower() or "as_needed"
        isolate_from_normal_po = _normalize_text(context["isolate_from_normal_po"]).lower() in {"1", "true", "yes", "y", "on"}

        ordered_sell_packs = confirmed_sell_packs
        if quantity_strategy == "preferred_carton_multiple" and preferred_order_sell_packs > 0:
            ordered_sell_packs = _round_up_to_multiple(confirmed_sell_packs, preferred_order_sell_packs)

        ordered_components = ordered_sell_packs * components_per_sell_pack
        ordered_supplier_boxes = ""
        if supplier_box_components > 0:
            if ordered_components % supplier_box_components != 0:
                hold_rows.append(
                    {
                        "hold_utc": build_iso,
                        "event_id": event_id,
                        "seller_sku": seller_sku,
                        "asin": asin,
                        "decision_action": action,
                        "final_decision_status": final_status,
                        "hold_reason": "invalid_supplier_box_alignment",
                        "hold_note": "ordered components do not divide cleanly into supplier boxes",
                        "confirmed_qty": _normalize_text(decision.get("confirmed_qty", "")),
                        "confirmed_unit_cost": _normalize_text(decision.get("confirmed_unit_cost", "")),
                        "supplier_code": supplier_code,
                        "supplier_name": supplier_name,
                        "cost_mode": context["cost_mode"],
                        "recommendation_basis": context["recommendation_basis"],
                        "source_reference": _normalize_text(decision.get("source_reference", "")),
                        "recommendation_asof_utc": recommendation_asof,
                    }
                )
                continue
            ordered_supplier_boxes = str(ordered_components // supplier_box_components)
        ordered_supplier_packs = ""
        if supplier_pack_size > 1 and ordered_sell_packs % supplier_pack_size == 0:
            ordered_supplier_packs = str(ordered_sell_packs // supplier_pack_size)

        if quantity_strategy == "preferred_carton_multiple" and (
            components_per_sell_pack <= 0 or preferred_order_sell_packs <= 0 or supplier_box_components <= 0
        ):
            hold_rows.append(
                {
                    "hold_utc": build_iso,
                    "event_id": event_id,
                    "seller_sku": seller_sku,
                    "asin": asin,
                    "decision_action": action,
                    "final_decision_status": final_status,
                    "hold_reason": "missing_special_order_pack_profile",
                    "hold_note": "special carton order needs components per pack, preferred order packs, and supplier box size",
                    "confirmed_qty": _normalize_text(decision.get("confirmed_qty", "")),
                    "confirmed_unit_cost": _normalize_text(decision.get("confirmed_unit_cost", "")),
                    "supplier_code": supplier_code,
                    "supplier_name": supplier_name,
                    "cost_mode": context["cost_mode"],
                    "recommendation_basis": context["recommendation_basis"],
                    "source_reference": _normalize_text(decision.get("source_reference", "")),
                    "recommendation_asof_utc": recommendation_asof,
                }
            )
            continue

        line_total = float(confirmed_cost_num) * ordered_sell_packs

        po_line_candidates.append(
            {
                "supplier_code": supplier_code,
                "supplier_name": supplier_name,
                "seller_sku": seller_sku,
                "asin": asin,
                "title": _normalize_text(context["title"]),
                "supplier_sku": _normalize_text(context["supplier_sku"]),
                "barcode": _normalize_text(context["barcode"]),
                "source_bridge_row": _normalize_text(context["source_bridge_row"]),
                "source_bridge_reference": _normalize_text(context["source_bridge_reference"]),
                "ordered_qty": str(ordered_sell_packs),
                "ordered_sell_packs": str(ordered_sell_packs),
                "requested_sell_packs": str(confirmed_sell_packs),
                "components_per_sell_pack": str(components_per_sell_pack),
                "component_unit_label": component_unit_label,
                "ordered_components": str(ordered_components),
                "supplier_box_components": str(supplier_box_components) if supplier_box_components > 0 else "",
                "ordered_supplier_boxes": ordered_supplier_boxes,
                "preferred_order_sell_packs": str(preferred_order_sell_packs) if preferred_order_sell_packs > 0 else "",
                "preferred_order_components": str(preferred_order_components) if preferred_order_components > 0 else "",
                "preferred_supplier_boxes": str(preferred_supplier_boxes) if preferred_supplier_boxes > 0 else "",
                "quantity_strategy": quantity_strategy,
                "supplier_cost_basis": _normalize_text(context["supplier_cost_basis"]),
                "hazmat_group": _normalize_text(context["hazmat_group"]),
                "isolate_from_normal_po": "1" if isolate_from_normal_po else "0",
                "target_carton_weight_kg": _normalize_text(context["target_carton_weight_kg"]),
                "pack_profile_status": _normalize_text(context["pack_profile_status"]),
                "pack_conversion_note": _normalize_text(context["pack_conversion_note"]),
                "ordered_unit_cost_gbp": _num_text(confirmed_cost_num),
                "supplier_pack_size": _normalize_text(context["supplier_pack_size"]) or "1",
                "moq": _normalize_text(context["moq"]) or "1",
                "ordered_supplier_packs": ordered_supplier_packs,
                "expected_arrival_utc": expected_arrival,
                "receipt_status": "not_received",
                "received_qty": "0",
                "remaining_open_qty": str(ordered_sell_packs),
                "source_event_id": event_id,
                "source_decision_action": action,
                "cost_mode": context["cost_mode"],
                "recommendation_basis": context["recommendation_basis"],
                "source_recommendation_asof_utc": recommendation_asof,
                "line_value_gbp": _num_text(line_total),
                "max_safe_unit_cost_gbp": _normalize_text(decision.get("max_safe_unit_cost_gbp", "")),
                "current_price_list_unit_cost_gbp": _normalize_text(decision.get("current_price_list_unit_cost_gbp", "")),
                "usual_paid_unit_cost_gbp": _normalize_text(decision.get("usual_paid_unit_cost_gbp", "")),
                "price_list_change_status": _normalize_text(decision.get("price_list_change_status", "")),
                "confirmed_price_safety_status": _normalize_text(decision.get("confirmed_price_safety_status", "")),
                "confirmed_vs_max_delta_gbp": _normalize_text(decision.get("confirmed_vs_max_delta_gbp", "")),
            }
        )

    headers: list[dict[str, str]] = []
    lines: list[dict[str, str]] = []
    po_index = 0

    if po_line_candidates:
        lines_df_work = pd.DataFrame(po_line_candidates)
        lines_df_work["supplier_group_key"] = lines_df_work.apply(
            lambda r: "|".join(
                [
                    _normalize_key(r.get("supplier_code", "")) or f"NAME::{_normalize_key(r.get('supplier_name', ''))}",
                    f"HAZMAT::{_normalize_key(r.get('hazmat_group', ''))}" if _normalize_text(r.get("isolate_from_normal_po", "")) == "1" else "NORMAL",
                ]
            ),
            axis=1,
        )
        lines_df_work = lines_df_work.sort_values(by=["supplier_group_key", "seller_sku"], kind="stable")

        for supplier_key, group in lines_df_work.groupby("supplier_group_key", sort=False):
            po_index += 1
            po_id = f"PO-DRAFT-{build_dt.strftime('%Y%m%d')}-{po_index:03d}"
            supplier_code = _normalize_text(group.iloc[0].get("supplier_code", ""))
            supplier_name = _normalize_text(group.iloc[0].get("supplier_name", ""))

            group_lines = group.to_dict(orient="records")
            total_units = 0
            total_components = 0
            total_value = 0.0
            earliest_eta: datetime | None = None
            has_test_mode = False
            hazmat_group = ""
            isolated_special_order = False
            decision_batch_refs: list[str] = []

            for i, line in enumerate(group_lines, start=1):
                qty = int(round(_num(line.get("ordered_qty", "")) or 0))
                components = int(round(_num(line.get("ordered_components", "")) or qty))
                unit_cost = _num(line.get("ordered_unit_cost_gbp", "")) or 0.0
                total_units += qty
                total_components += components
                total_value += qty * unit_cost
                if _normalize_text(line.get("cost_mode", "")).lower() == "test":
                    has_test_mode = True
                if _normalize_text(line.get("isolate_from_normal_po", "")) == "1":
                    isolated_special_order = True
                    hazmat_group = _normalize_text(line.get("hazmat_group", ""))
                event_ref = _normalize_text(line.get("source_event_id", ""))
                if event_ref:
                    decision_batch_refs.append(event_ref)

                eta_dt = _parse_utc(line.get("expected_arrival_utc", ""))
                if eta_dt is not None and (earliest_eta is None or eta_dt < earliest_eta):
                    earliest_eta = eta_dt

                lines.append(
                    {
                        "po_id": po_id,
                        "po_line_id": f"{po_id}-L{i:03d}",
                        "seller_sku": _normalize_text(line.get("seller_sku", "")),
                        "asin": _normalize_text(line.get("asin", "")),
                        "ordered_qty": str(qty),
                        "ordered_unit_cost_gbp": _num_text(unit_cost),
                        "supplier_pack_size": _normalize_text(line.get("supplier_pack_size", "")) or "1",
                        "moq": _normalize_text(line.get("moq", "")) or "1",
                        "ordered_supplier_packs": _normalize_text(line.get("ordered_supplier_packs", "")),
                        "receipt_status": "not_received",
                        "received_qty": "0",
                        "remaining_open_qty": str(qty),
                        "expected_arrival_utc": _normalize_text(line.get("expected_arrival_utc", "")),
                        "source_event_id": _normalize_text(line.get("source_event_id", "")),
                        "source_decision_action": _normalize_text(line.get("source_decision_action", "")),
                        "title": _normalize_text(line.get("title", "")),
                        "supplier_sku": _normalize_text(line.get("supplier_sku", "")),
                        "barcode": _normalize_text(line.get("barcode", "")),
                        "source_bridge_row": _normalize_text(line.get("source_bridge_row", "")),
                        "source_bridge_reference": _normalize_text(line.get("source_bridge_reference", "")),
                        "cost_mode": _normalize_text(line.get("cost_mode", "")) or "live",
                        "recommendation_basis": _normalize_text(line.get("recommendation_basis", "")),
                        "source_recommendation_asof_utc": _normalize_text(line.get("source_recommendation_asof_utc", "")),
                        "ordered_sell_packs": _normalize_text(line.get("ordered_sell_packs", "")),
                        "requested_sell_packs": _normalize_text(line.get("requested_sell_packs", "")),
                        "components_per_sell_pack": _normalize_text(line.get("components_per_sell_pack", "")),
                        "component_unit_label": _normalize_text(line.get("component_unit_label", "")),
                        "ordered_components": _normalize_text(line.get("ordered_components", "")),
                        "supplier_box_components": _normalize_text(line.get("supplier_box_components", "")),
                        "ordered_supplier_boxes": _normalize_text(line.get("ordered_supplier_boxes", "")),
                        "preferred_order_sell_packs": _normalize_text(line.get("preferred_order_sell_packs", "")),
                        "preferred_order_components": _normalize_text(line.get("preferred_order_components", "")),
                        "preferred_supplier_boxes": _normalize_text(line.get("preferred_supplier_boxes", "")),
                        "quantity_strategy": _normalize_text(line.get("quantity_strategy", "")),
                        "supplier_cost_basis": _normalize_text(line.get("supplier_cost_basis", "")),
                        "hazmat_group": _normalize_text(line.get("hazmat_group", "")),
                        "isolate_from_normal_po": _normalize_text(line.get("isolate_from_normal_po", "")),
                        "target_carton_weight_kg": _normalize_text(line.get("target_carton_weight_kg", "")),
                        "pack_profile_status": _normalize_text(line.get("pack_profile_status", "")),
                        "pack_conversion_note": _normalize_text(line.get("pack_conversion_note", "")),
                        "max_safe_unit_cost_gbp": _normalize_text(line.get("max_safe_unit_cost_gbp", "")),
                        "current_price_list_unit_cost_gbp": _normalize_text(line.get("current_price_list_unit_cost_gbp", "")),
                        "usual_paid_unit_cost_gbp": _normalize_text(line.get("usual_paid_unit_cost_gbp", "")),
                        "price_list_change_status": _normalize_text(line.get("price_list_change_status", "")),
                        "confirmed_price_safety_status": _normalize_text(line.get("confirmed_price_safety_status", "")),
                        "confirmed_vs_max_delta_gbp": _normalize_text(line.get("confirmed_vs_max_delta_gbp", "")),
                    }
                )

            po_note_parts: list[str] = []
            if isolated_special_order:
                po_note_parts.append(f"isolated_special_order:{hazmat_group or 'unknown'}")
                po_note_parts.append(f"total_components:{total_components}")

            headers.append(
                {
                    "po_id": po_id,
                    "created_utc": build_iso,
                    "supplier_code": supplier_code,
                    "supplier_name": supplier_name,
                    "po_status": "draft",
                    "currency": "GBP",
                    "total_lines": str(len(group_lines)),
                    "total_units": str(total_units),
                    "total_value_gbp": _num_text(total_value),
                    "approved_from_decision_batch": "|".join(decision_batch_refs[:50]),
                    "expected_arrival_utc": earliest_eta.strftime("%Y-%m-%dT%H:%M:%SZ") if earliest_eta is not None else "",
                    "po_notes": "|".join(po_note_parts),
                    "po_build_note": "contains_test_mode_costs" if has_test_mode else "live_cost_mode_only",
                }
            )

    headers_df = pd.DataFrame(headers)
    lines_df = pd.DataFrame(lines)
    holds_df = pd.DataFrame(hold_rows)

    header_contract = get_o_output_contract("purchase_orders_live")
    header_cols = [*header_contract.required_columns, *header_contract.optional_columns]
    line_contract = get_o_output_contract("purchase_order_lines_live")
    line_cols = [*line_contract.required_columns, *line_contract.optional_columns]
    holds_contract = get_o_output_contract("purchase_order_draft_holds")
    holds_cols = [*holds_contract.required_columns, *holds_contract.optional_columns]

    headers_df = _ensure_columns(headers_df, header_cols)[header_cols + [c for c in headers_df.columns if c not in header_cols]]
    lines_df = _ensure_columns(lines_df, line_cols)[line_cols + [c for c in lines_df.columns if c not in line_cols]]
    holds_df = _ensure_columns(holds_df, holds_cols)[holds_cols + [c for c in holds_df.columns if c not in holds_cols]]

    po_header_path.parent.mkdir(parents=True, exist_ok=True)
    write_o_contract_df(root_path, "purchase_orders_live", headers_df)
    write_o_contract_df(root_path, "purchase_order_lines_live", lines_df)
    write_o_contract_df(root_path, "purchase_order_draft_holds", holds_df)

    print(
        {
            "status": "success",
            "po_headers": int(len(headers_df)),
            "po_lines": int(len(lines_df)),
            "holds": int(len(holds_df)),
            "purchase_orders_live": str(po_header_path),
            "purchase_order_lines_live": str(po_lines_path),
            "purchase_order_draft_holds": str(holds_path),
        }
    )
    return headers_df, lines_df, holds_df


def main() -> None:
    build_purchase_orders()


if __name__ == "__main__":
    main()
