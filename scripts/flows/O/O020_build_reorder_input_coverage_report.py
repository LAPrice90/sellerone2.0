from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract
from scripts.flows.O._schemas import get_o_output_contract
from scripts.flows.O._source_contracts import get_phase1_source_contracts


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
    "gross_forward_roi_pct",
    "gross_forward_profit_per_unit_gbp",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _as_flag(value: bool) -> str:
    return "1" if value else "0"


def _is_positive_number(value: object) -> bool:
    raw = _normalize_text(value)
    if raw == "":
        return False
    try:
        return float(raw) > 0
    except ValueError:
        return False


def _read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _align_to_contract(df: pd.DataFrame, contract_name: str) -> pd.DataFrame:
    contract = get_o_output_contract(contract_name)
    ordered = [*contract.required_columns, *contract.optional_columns]
    for col in ordered:
        if col not in df.columns:
            df[col] = ""
    return df[ordered]


def _first_non_blank(*values: object) -> str:
    for value in values:
        text = _normalize_text(value)
        if text != "":
            return text
    return ""


def _map_by_sku(df: pd.DataFrame, key_column: str) -> dict[str, pd.Series]:
    if df.empty or key_column not in df.columns:
        return {}
    work = df.copy()
    work["_sku_norm"] = work[key_column].map(_normalize_key)
    work = work[work["_sku_norm"] != ""]
    if work.empty:
        return {}
    work = work.drop_duplicates(subset=["_sku_norm"], keep="first").set_index("_sku_norm")
    return {idx: work.loc[idx] for idx in work.index}


def _dedupe_keep_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _truthy(value: object) -> bool:
    token = _normalize_text(value).lower()
    return token in {"1", "true", "yes", "y", "on"}


def _first_row_value(field: str, *rows: pd.Series | None) -> str:
    for row in rows:
        if row is None:
            continue
        value = _normalize_text(row.get(field, ""))
        if value:
            return value
    return ""


def _pack_block_reasons(source_row: pd.Series | None, rec_row: pd.Series | None, queue_row: pd.Series | None) -> list[str]:
    status = _first_row_value("pack_profile_status", source_row, rec_row, queue_row).lower()
    supplier_cost_basis = _first_row_value("supplier_cost_basis", source_row, rec_row, queue_row).lower()
    source_notes = _normalize_text(source_row.get("source_notes", "") if source_row is not None else "")
    note_codes = {code.strip() for code in source_notes.split("|") if code.strip()}
    blockers: list[str] = []

    if status in {"missing_pack_profile", "missing"} or "missing_pack_profile" in note_codes:
        blockers.append("missing_pack_profile")
    if status in {"unconfirmed_pack_profile", "draft", "pending", "provisional"} or "unconfirmed_pack_profile" in note_codes:
        blockers.append("unconfirmed_pack_profile")
    if status == "invalid" or "invalid_component_conversion" in note_codes:
        blockers.append("invalid_component_conversion")
    if "missing_supplier_cost_basis" in note_codes or supplier_cost_basis == "":
        if status not in {"", "default_normal"}:
            blockers.append("missing_supplier_cost_basis")
    if "invalid_supplier_box_alignment" in note_codes:
        blockers.append("invalid_supplier_box_alignment")
    if "special_order_profile_required" in note_codes or status == "special_order_profile_required":
        blockers.append("special_order_profile_required")
    if "pack_title_profile_mismatch" in note_codes:
        blockers.append("pack_title_profile_mismatch")

    return _dedupe_keep_order(blockers)


def _net_fee_block_reason(source_row: pd.Series | None, rec_row: pd.Series | None, queue_row: pd.Series | None) -> str:
    status = _first_row_value("net_fee_model_status", source_row, rec_row, queue_row).lower()
    if status == "fresh":
        return ""
    if status == "stale":
        return "stale_net_fee_truth"
    if status == "invalid":
        return "invalid_net_fee_truth"
    return "missing_net_fee_truth"


def _build_summary_markdown(
    *,
    summary_path: Path,
    report_utc: str,
    detail_df: pd.DataFrame,
    supplier_df: pd.DataFrame,
    block_df: pd.DataFrame,
) -> None:
    total_rows = len(detail_df.index)
    action_ready = int(detail_df["action_ready_now"].eq("1").sum()) if not detail_df.empty else 0
    action_candidates = int(detail_df["action_candidate"].eq("1").sum()) if not detail_df.empty else 0
    blocked_rows = max(total_rows - action_ready, 0)

    top_block_lines: list[str] = []
    if not block_df.empty:
        top_blocks = block_df.sort_values(by="rows_count", ascending=False).head(8)
        for _, row in top_blocks.iterrows():
            top_block_lines.append(f"- `{row['block_reason']}`: {row['rows_count']}")
    if not top_block_lines:
        top_block_lines = ["- none"]

    supplier_lines: list[str] = []
    if not supplier_df.empty:
        supplier_rank = supplier_df.copy()
        supplier_rank["rows_blocked_n"] = pd.to_numeric(supplier_rank["rows_blocked"], errors="coerce").fillna(0)
        top_suppliers = supplier_rank.sort_values(by="rows_blocked_n", ascending=False).head(8)
        for _, row in top_suppliers.iterrows():
            supplier_lines.append(
                f"- `{row['supplier_name']}` ({row['supplier_code']}): total={row['rows_total']}, "
                f"ready={row['rows_action_ready']}, blocked={row['rows_blocked']}"
            )
    if not supplier_lines:
        supplier_lines = ["- none"]

    high_impact_block_df = block_df[~block_df["block_reason"].isin(["wait_or_non_action_suggestion", "snoozed"])].copy()
    fix_first_lines: list[str] = []
    if not high_impact_block_df.empty:
        for _, row in high_impact_block_df.sort_values(by="rows_count", ascending=False).head(3).iterrows():
            reason = _normalize_text(row["block_reason"])
            fix_first_lines.append(f"- `{reason}` ({row['rows_count']} rows)")
    if not fix_first_lines:
        fix_first_lines = ["- No high-impact blockers found beyond wait/snooze state."]

    text = "\n".join(
        [
            "# O Reorder Input Readiness Summary",
            "",
            f"- generated_utc: `{report_utc}`",
            f"- total_rows_considered: `{total_rows}`",
            f"- action_candidates: `{action_candidates}`",
            f"- rows_actionable_now: `{action_ready}`",
            f"- rows_blocked_now: `{blocked_rows}`",
            "",
            "## Top Block Reasons",
            *top_block_lines,
            "",
            "## Supplier Breakdown",
            *supplier_lines,
            "",
            "## What To Fix First",
            *fix_first_lines,
        ]
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(text, encoding="utf-8")


def build_reorder_input_coverage_report(root: Path | None = None, *, report_utc: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    now_utc = report_utc or _utc_now_iso()

    source_view_df = read_o_contract_df(root_path, "restock_source_view")
    recommendations_df = read_o_contract_df(root_path, "restock_recommendations_live")
    queue_df = read_o_contract_df(root_path, "restock_review_queue")

    source_contracts = get_phase1_source_contracts()
    product_df = _read_csv_safe(root_path / source_contracts["product_db_preview"].source_path)
    velocity_df = _read_csv_safe(root_path / source_contracts["sku_sales_velocity"].source_path)
    performance_df = _read_csv_safe(root_path / source_contracts["sku_performance_summary"].source_path)
    offer_df = _read_csv_safe(root_path / source_contracts["listing_offer_snapshot_latest"].source_path)

    source_view_map = _map_by_sku(source_view_df, "seller_sku")
    recommendation_map = _map_by_sku(recommendations_df, "seller_sku")
    queue_map = _map_by_sku(queue_df, "seller_sku")
    product_map = _map_by_sku(product_df, "seller_sku")
    velocity_map = _map_by_sku(velocity_df, "sku")
    performance_map = _map_by_sku(performance_df, "sku")
    offer_map = _map_by_sku(offer_df, "sku")

    sku_keys = sorted(set(source_view_map.keys()) | set(recommendation_map.keys()) | set(queue_map.keys()))

    detail_rows: list[dict[str, str]] = []
    for sku_key in sku_keys:
        source_row = source_view_map.get(sku_key)
        rec_row = recommendation_map.get(sku_key)
        queue_row = queue_map.get(sku_key)

        seller_sku = _first_non_blank(
            queue_row.get("seller_sku", "") if queue_row is not None else "",
            rec_row.get("seller_sku", "") if rec_row is not None else "",
            source_row.get("seller_sku", "") if source_row is not None else "",
        )
        asin = _first_non_blank(
            queue_row.get("asin", "") if queue_row is not None else "",
            rec_row.get("asin", "") if rec_row is not None else "",
            source_row.get("asin", "") if source_row is not None else "",
        )
        supplier_code = _first_non_blank(
            queue_row.get("supplier_code", "") if queue_row is not None else "",
            rec_row.get("supplier_code", "") if rec_row is not None else "",
            source_row.get("supplier_code", "") if source_row is not None else "",
        )
        supplier_name = _first_non_blank(
            queue_row.get("supplier_name", "") if queue_row is not None else "",
            rec_row.get("supplier_name", "") if rec_row is not None else "",
            source_row.get("supplier_name", "") if source_row is not None else "",
        )
        title = _first_non_blank(
            queue_row.get("title", "") if queue_row is not None else "",
            rec_row.get("title", "") if rec_row is not None else "",
            source_row.get("title", "") if source_row is not None else "",
        )
        main_image = _first_non_blank(
            queue_row.get("main_image", "") if queue_row is not None else "",
            rec_row.get("main_image", "") if rec_row is not None else "",
            source_row.get("main_image", "") if source_row is not None else "",
        )
        suggested_action = _first_non_blank(
            queue_row.get("suggested_action", "") if queue_row is not None else "",
            queue_row.get("recommendation_status", "") if queue_row is not None else "",
            rec_row.get("recommendation_status", "") if rec_row is not None else "",
        ).lower()
        suggested_qty = _first_non_blank(
            queue_row.get("suggested_qty", "") if queue_row is not None else "",
            rec_row.get("recommended_qty_rounded", "") if rec_row is not None else "",
        )
        suggested_unit_cost = _first_non_blank(
            queue_row.get("suggested_unit_cost_gbp", "") if queue_row is not None else "",
            rec_row.get("current_supplier_buy_cost_gbp", "") if rec_row is not None else "",
            source_row.get("current_supplier_buy_cost_gbp", "") if source_row is not None else "",
        )
        suggested_market_price = _first_non_blank(
            queue_row.get("suggested_market_price_gbp", "") if queue_row is not None else "",
            rec_row.get("market_price_gbp", "") if rec_row is not None else "",
            source_row.get("market_price_gbp", "") if source_row is not None else "",
        )
        expected_forward_roi = _first_non_blank(
            queue_row.get("expected_forward_roi_pct", "") if queue_row is not None else "",
            rec_row.get("forward_roi_pct", "") if rec_row is not None else "",
        )
        recommendation_reason = _first_non_blank(
            queue_row.get("reason_codes", "") if queue_row is not None else "",
            rec_row.get("reason_codes", "") if rec_row is not None else "",
            source_row.get("coverage_block_reason", "") if source_row is not None else "",
        )
        queue_status = _first_non_blank(
            queue_row.get("queue_status", "") if queue_row is not None else "",
        ).lower()
        cost_mode = _first_non_blank(
            queue_row.get("cost_mode", "") if queue_row is not None else "",
            rec_row.get("cost_mode", "") if rec_row is not None else "",
            source_row.get("cost_mode", "") if source_row is not None else "",
            "live",
        )
        recommendation_basis = _first_non_blank(
            queue_row.get("recommendation_basis", "") if queue_row is not None else "",
            rec_row.get("recommendation_basis", "") if rec_row is not None else "",
            "live_cost_inputs",
        )
        user_price_check_required = _truthy(
            _first_non_blank(
                queue_row.get("user_price_check_required", "") if queue_row is not None else "",
                rec_row.get("user_price_check_required", "") if rec_row is not None else "",
                source_row.get("user_price_check_required", "") if source_row is not None else "",
            )
        )
        supplier_cost_review_reason = _first_non_blank(
            queue_row.get("supplier_cost_review_reason", "") if queue_row is not None else "",
            rec_row.get("supplier_cost_review_reason", "") if rec_row is not None else "",
            source_row.get("supplier_cost_review_reason", "") if source_row is not None else "",
        )
        max_break_even_purchase_price = _first_non_blank(
            rec_row.get("max_break_even_purchase_price_gbp", "") if rec_row is not None else "",
            queue_row.get("max_break_even_purchase_price_gbp", "") if queue_row is not None else "",
            source_row.get("max_break_even_purchase_price_gbp", "") if source_row is not None else "",
        )
        max_target_roi_purchase_price = _first_non_blank(
            rec_row.get("max_target_roi_purchase_price_gbp", "") if rec_row is not None else "",
            queue_row.get("max_target_roi_purchase_price_gbp", "") if queue_row is not None else "",
            source_row.get("max_target_roi_purchase_price_gbp", "") if source_row is not None else "",
        )
        target_roi_pct = _first_non_blank(
            rec_row.get("target_roi_pct", "") if rec_row is not None else "",
            queue_row.get("target_roi_pct", "") if queue_row is not None else "",
            source_row.get("target_roi_pct", "") if source_row is not None else "",
        )
        purchase_price_safety_status = _first_non_blank(
            rec_row.get("purchase_price_safety_status", "") if rec_row is not None else "",
            queue_row.get("purchase_price_safety_status", "") if queue_row is not None else "",
            source_row.get("purchase_price_safety_status", "") if source_row is not None else "",
        )
        pack_fields = {
            field: _first_row_value(field, source_row, rec_row, queue_row)
            for field in PACK_PROFILE_FIELDS
        }
        net_fee_fields = {
            field: _first_row_value(field, source_row, rec_row, queue_row)
            for field in NET_FEE_AUDIT_FIELDS
        }
        pack_block_reasons = _pack_block_reasons(source_row, rec_row, queue_row)
        net_fee_block_reason = _net_fee_block_reason(source_row, rec_row, queue_row)

        is_active_candidate = _truthy(source_row.get("is_active_candidate", "") if source_row is not None else "")
        has_current_cost_input = _truthy(source_row.get("has_current_cost_input", "") if source_row is not None else "")
        has_current_market_price_input = _truthy(source_row.get("has_current_market_price_input", "") if source_row is not None else "")
        has_demand_input = _truthy(source_row.get("has_demand_input", "") if source_row is not None else "")
        has_minimum_restock_inputs = _truthy(source_row.get("has_minimum_restock_inputs", "") if source_row is not None else "")
        coverage_block_reason = _normalize_text(source_row.get("coverage_block_reason", "") if source_row is not None else "")

        missing_supplier_name = supplier_name == ""
        missing_seller_sku = seller_sku == ""
        missing_title = title == ""
        missing_main_image = main_image == ""
        missing_suggested_action = suggested_action == ""
        missing_suggested_qty = not _is_positive_number(suggested_qty)
        missing_suggested_unit_cost = not _is_positive_number(suggested_unit_cost)
        missing_suggested_market_price = not _is_positive_number(suggested_market_price)
        missing_expected_forward_roi = _normalize_text(expected_forward_roi) == ""
        missing_recommendation_reason = recommendation_reason == ""

        action_candidate = suggested_action in {"full_restock", "test_restock"}
        actionable_gate_ok = (
            action_candidate
            and is_active_candidate
            and has_current_cost_input
            and has_current_market_price_input
            and has_demand_input
            and (not missing_seller_sku)
            and (not missing_supplier_name)
            and (not missing_suggested_qty)
            and (not missing_suggested_unit_cost)
            and (not user_price_check_required)
            and (not pack_block_reasons)
            and (net_fee_block_reason == "")
        )
        action_ready_now = actionable_gate_ok

        block_reasons: list[str] = []
        if queue_status == "snoozed":
            block_reasons.append("snoozed")
        if not action_candidate:
            block_reasons.append("wait_or_non_action_suggestion")
        if missing_supplier_name:
            block_reasons.append("missing_supplier_name")
        if missing_seller_sku:
            block_reasons.append("missing_seller_sku")
        if missing_title:
            block_reasons.append("missing_title")
        if missing_main_image:
            block_reasons.append("missing_main_image")
        if missing_suggested_action:
            block_reasons.append("missing_suggested_action")
        if missing_suggested_qty:
            block_reasons.append("missing_suggested_qty")
        if missing_suggested_unit_cost:
            block_reasons.append("missing_suggested_unit_cost")
        if missing_suggested_market_price:
            block_reasons.append("missing_suggested_market_price")
        if missing_expected_forward_roi:
            block_reasons.append("missing_expected_forward_roi")
        if missing_recommendation_reason:
            block_reasons.append("missing_recommendation_reason")
        if not is_active_candidate:
            block_reasons.append("inactive_or_unknown_status")
        if not has_current_cost_input:
            block_reasons.append("missing_cost_truth")
        if not has_current_market_price_input:
            block_reasons.append("missing_market_truth")
        if not has_demand_input:
            block_reasons.append("missing_demand_truth")
        if coverage_block_reason:
            block_reasons.append(f"coverage_block::{coverage_block_reason}")
        if user_price_check_required:
            block_reasons.append("supplier_cost_confirmation_required")
        if purchase_price_safety_status in {"above_break_even_max", "above_target_roi_max"}:
            block_reasons.append(f"purchase_price::{purchase_price_safety_status}")
        block_reasons.extend(pack_block_reasons)
        if net_fee_block_reason and action_candidate:
            block_reasons.append(net_fee_block_reason)

        block_reason_codes = "|".join(_dedupe_keep_order(block_reasons))
        missing_flags = [
            missing_supplier_name,
            missing_seller_sku,
            missing_title,
            missing_main_image,
            missing_suggested_action,
            missing_suggested_qty,
            missing_suggested_unit_cost,
            missing_suggested_market_price,
            missing_expected_forward_roi,
            missing_recommendation_reason,
        ]
        field_missing_count = sum(1 for flag in missing_flags if flag)

        detail_rows.append(
            {
                "report_utc": now_utc,
                "seller_sku": seller_sku,
                "asin": asin,
                "supplier_code": supplier_code,
                "supplier_name": supplier_name if supplier_name else "(Unknown supplier)",
                "suggested_action": suggested_action,
                "suggested_qty": suggested_qty,
                "suggested_unit_cost_gbp": suggested_unit_cost,
                "suggested_market_price_gbp": suggested_market_price,
                "expected_forward_roi_pct": expected_forward_roi,
                "queue_status": queue_status,
                "cost_mode": cost_mode,
                "recommendation_basis": recommendation_basis,
                "is_active_candidate": _as_flag(is_active_candidate),
                "has_current_cost_input": _as_flag(has_current_cost_input),
                "has_current_market_price_input": _as_flag(has_current_market_price_input),
                "has_demand_input": _as_flag(has_demand_input),
                "has_minimum_restock_inputs": _as_flag(has_minimum_restock_inputs),
                "action_candidate": _as_flag(action_candidate),
                "action_ready_now": _as_flag(action_ready_now),
                "block_reason_codes": block_reason_codes,
                "field_missing_count": str(field_missing_count),
                "recommendation_reason": recommendation_reason,
                "missing_supplier_name": _as_flag(missing_supplier_name),
                "missing_seller_sku": _as_flag(missing_seller_sku),
                "missing_title": _as_flag(missing_title),
                "missing_main_image": _as_flag(missing_main_image),
                "missing_suggested_action": _as_flag(missing_suggested_action),
                "missing_suggested_qty": _as_flag(missing_suggested_qty),
                "missing_suggested_unit_cost_gbp": _as_flag(missing_suggested_unit_cost),
                "missing_suggested_market_price_gbp": _as_flag(missing_suggested_market_price),
                "missing_expected_forward_roi_pct": _as_flag(missing_expected_forward_roi),
                "missing_recommendation_reason": _as_flag(missing_recommendation_reason),
                "product_db_row_present": _as_flag(sku_key in product_map),
                "velocity_row_present": _as_flag(sku_key in velocity_map),
                "performance_row_present": _as_flag(sku_key in performance_map),
                "offer_row_present": _as_flag(sku_key in offer_map),
                "source_queue_present": _as_flag(queue_row is not None),
                "source_recommendation_present": _as_flag(rec_row is not None),
                "source_view_present": _as_flag(source_row is not None),
                "coverage_block_reason": coverage_block_reason,
                "user_price_check_required": _as_flag(user_price_check_required),
                "supplier_cost_review_reason": supplier_cost_review_reason,
                "max_break_even_purchase_price_gbp": max_break_even_purchase_price,
                "max_target_roi_purchase_price_gbp": max_target_roi_purchase_price,
                "target_roi_pct": target_roi_pct,
                "purchase_price_safety_status": purchase_price_safety_status,
                **net_fee_fields,
                **pack_fields,
            }
        )

    detail_df = _align_to_contract(pd.DataFrame(detail_rows), "reorder_input_coverage_report")

    supplier_rows: list[dict[str, str]] = []
    if not detail_df.empty:
        grouped = detail_df.groupby(["supplier_name", "supplier_code"], dropna=False, sort=True)
        for (supplier_name, supplier_code), group in grouped:
            rows_total = len(group.index)
            rows_action_candidate = int(group["action_candidate"].eq("1").sum())
            rows_action_ready = int(group["action_ready_now"].eq("1").sum())
            supplier_rows.append(
                {
                    "report_utc": now_utc,
                    "supplier_name": _normalize_text(supplier_name) or "(Unknown supplier)",
                    "supplier_code": _normalize_text(supplier_code),
                    "rows_total": str(rows_total),
                    "rows_action_candidate": str(rows_action_candidate),
                    "rows_action_ready": str(rows_action_ready),
                    "rows_blocked": str(max(rows_total - rows_action_ready, 0)),
                    "rows_missing_cost_truth": str(int((group["has_current_cost_input"] == "0").sum())),
                    "rows_missing_market_truth": str(int((group["has_current_market_price_input"] == "0").sum())),
                    "rows_missing_demand_truth": str(int((group["has_demand_input"] == "0").sum())),
                    "rows_wait_suggested": str(int(group["suggested_action"].eq("wait").sum())),
                    "rows_snoozed": str(int(group["queue_status"].eq("snoozed").sum())),
                    "rows_missing_qty_prefill": str(int(group["missing_suggested_qty"].eq("1").sum())),
                    "rows_missing_cost_prefill": str(int(group["missing_suggested_unit_cost_gbp"].eq("1").sum())),
                    "rows_missing_image": str(int(group["missing_main_image"].eq("1").sum())),
                }
            )
    supplier_df = _align_to_contract(pd.DataFrame(supplier_rows), "reorder_input_coverage_by_supplier")

    block_rows: list[dict[str, str]] = []
    block_counts: dict[str, int] = {}
    for codes in detail_df.get("block_reason_codes", pd.Series(dtype=str)):
        for code in _normalize_text(codes).split("|"):
            reason = _normalize_text(code)
            if reason == "":
                continue
            block_counts[reason] = block_counts.get(reason, 0) + 1

    for reason, count in sorted(block_counts.items(), key=lambda item: (-item[1], item[0])):
        if reason.startswith("missing_") or reason.startswith("coverage_block::"):
            block_type = "missing_input"
        elif reason in {"wait_or_non_action_suggestion", "snoozed", "inactive_or_unknown_status"}:
            block_type = "state_or_policy"
        else:
            block_type = "other"
        block_rows.append(
            {
                "report_utc": now_utc,
                "block_reason": reason,
                "rows_count": str(count),
                "block_type": block_type,
            }
        )
    block_df = _align_to_contract(pd.DataFrame(block_rows), "reorder_input_block_reasons")

    report_path = root_path / get_o_output_contract("reorder_input_coverage_report").rel_path
    supplier_path = root_path / get_o_output_contract("reorder_input_coverage_by_supplier").rel_path
    block_path = root_path / get_o_output_contract("reorder_input_block_reasons").rel_path
    summary_path = root_path / "out" / "systems" / "O" / "live" / "reorder_input_readiness_summary.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_o_contract_df(root_path, "reorder_input_coverage_report", detail_df)
    write_o_contract_df(root_path, "reorder_input_coverage_by_supplier", supplier_df)
    write_o_contract_df(root_path, "reorder_input_block_reasons", block_df)

    _build_summary_markdown(
        summary_path=summary_path,
        report_utc=now_utc,
        detail_df=detail_df,
        supplier_df=supplier_df,
        block_df=block_df,
    )

    print(
        {
            "status": "success",
            "rows_detail": len(detail_df),
            "rows_supplier": len(supplier_df),
            "rows_blocks": len(block_df),
            "report": str(report_path),
            "supplier_report": str(supplier_path),
            "block_report": str(block_path),
            "summary": str(summary_path),
        }
    )
    return detail_df, supplier_df, block_df


def main() -> None:
    build_reorder_input_coverage_report()


if __name__ == "__main__":
    main()
