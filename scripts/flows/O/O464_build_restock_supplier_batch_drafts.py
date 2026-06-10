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

from scripts.flows.O.O460_build_restock_session_view import build_restock_session_view
from scripts.flows.O.O466_restock_supplier_proof_events import (
    ensure_restock_session_supplier_proof_event_file,
    latest_restock_session_supplier_proof_events,
    validate_restock_session_supplier_proof_event,
)
from scripts.flows.O.O468_restock_pack_moq_proof_events import (
    ensure_restock_session_pack_moq_proof_event_file,
    latest_restock_session_pack_moq_proof_events,
    validate_restock_session_pack_moq_proof_event,
)
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract


BATCH_ID_PREFIX = "o_restock_supplier_batch_draft_v1"
SOURCE_CLASSES = {"native_o", "legacy_bridge", "feeder_review_handoff", "manual_walkthrough_fixture"}
READINESS_STATES = {"blocked_from_purchase_approval", "ready_for_purchase_approval_review_only"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _safe_fragment(value: object) -> str:
    text = _normalize_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "unknown"


def _num(value: object) -> float | None:
    text = _normalize_text(value).replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _num_text(value: float | None) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _positive_qty(value: object) -> float | None:
    number = _num(value)
    if number is None or number <= 0 or not float(number).is_integer():
        return None
    return number


def _batch_id(supplier_name: object, supplier_code: object) -> str:
    supplier_key = _safe_fragment(supplier_code) if _normalize_text(supplier_code) else _safe_fragment(supplier_name)
    return f"{BATCH_ID_PREFIX}:{supplier_key}"


def _line_state(row: pd.Series) -> str:
    row_status = _normalize_text(row.get("row_status", "")).lower()
    safety = _normalize_text(row.get("action_safety_state", "")).lower()
    if row_status == "blocked" or safety == "blocked_from_clean_buy":
        return "review_only_blocked"
    return "review_only_ready"


def _supplier_proof_checklist(row: pd.Series) -> tuple[str, str]:
    missing: list[str] = []
    supplier_match_state = _normalize_text(row.get("supplier_match_state", ""))
    supplier_proof_state = _normalize_text(row.get("supplier_proof_state", ""))
    supplier_cost_state = _normalize_text(row.get("supplier_cost_proof_state", ""))
    supplier_stock_state = _normalize_text(row.get("supplier_stock_state", ""))
    backorder_state = _normalize_text(row.get("backorder_state", ""))
    supplier_file_asof = _normalize_text(row.get("supplier_file_asof_utc", ""))
    pack_state = _normalize_text(row.get("pack_moq_proof_state", ""))

    if supplier_match_state != "exact_supplier_sku_or_barcode_match" or supplier_proof_state != "supplier_exact_match_proved":
        missing.append("exact_supplier_match_not_proved")
    if (
        supplier_cost_state == ""
        or supplier_cost_state.startswith("missing")
        or supplier_cost_state.startswith("bridge")
        or supplier_cost_state.endswith("not_verified")
        or "unknown" in supplier_cost_state
        or supplier_cost_state == "supplier_cost_not_exact"
    ):
        missing.append("supplier_cost_not_proved")
    if supplier_stock_state in {"", "supplier_stock_not_verified"}:
        missing.append("supplier_stock_not_verified")
    if backorder_state in {"", "backorder_not_verified"}:
        missing.append("backorder_not_verified")
    if supplier_file_asof == "":
        missing.append("supplier_file_asof_missing")
    if pack_state in {"", "pack_moq_not_verified"}:
        missing.append("pack_moq_not_verified")

    if missing:
        return "needs_supplier_proof", "|".join(missing)
    return "supplier_proof_clear", ""


def _apply_latest_supplier_proof_events(review_df: pd.DataFrame, proof_events_df: pd.DataFrame) -> pd.DataFrame:
    if review_df.empty:
        return review_df
    out = review_df.copy()
    for col in (
        "supplier_stock_qty",
        "backorder_eta_utc",
        "supplier_file_reference",
        "latest_supplier_proof_id",
        "latest_supplier_proof_utc",
        "latest_supplier_proof_note",
        "latest_supplier_proof_actor",
    ):
        if col not in out.columns:
            out[col] = ""
    latest = latest_restock_session_supplier_proof_events(proof_events_df)
    if latest.empty:
        return out
    latest_by_row = {
        _normalize_text(row.get("row_id", "")): row
        for _, row in latest.iterrows()
        if _normalize_text(row.get("row_id", ""))
    }
    if not latest_by_row:
        return out
    for idx, row in out.iterrows():
        proof = latest_by_row.get(_normalize_text(row.get("row_id", "")))
        if proof is None:
            continue
        for source_col, target_col in (
            ("supplier_stock_state", "supplier_stock_state"),
            ("supplier_stock_qty", "supplier_stock_qty"),
            ("backorder_state", "backorder_state"),
            ("backorder_eta_utc", "backorder_eta_utc"),
            ("supplier_file_asof_utc", "supplier_file_asof_utc"),
            ("supplier_file_reference", "supplier_file_reference"),
        ):
            value = _normalize_text(proof.get(source_col, ""))
            if value:
                out.at[idx, target_col] = value
        out.at[idx, "latest_supplier_proof_id"] = _normalize_text(proof.get("proof_id", ""))
        out.at[idx, "latest_supplier_proof_utc"] = _normalize_text(proof.get("event_utc", ""))
        out.at[idx, "latest_supplier_proof_note"] = _normalize_text(proof.get("proof_note", ""))
        out.at[idx, "latest_supplier_proof_actor"] = _normalize_text(proof.get("actor", ""))
    return out


def _apply_latest_pack_moq_proof_events(review_df: pd.DataFrame, proof_events_df: pd.DataFrame) -> pd.DataFrame:
    if review_df.empty:
        return review_df
    out = review_df.copy()
    for col in (
        "latest_pack_moq_proof_id",
        "latest_pack_moq_proof_utc",
        "latest_pack_moq_proof_file_reference",
        "latest_pack_moq_proof_note",
        "latest_pack_moq_proof_actor",
    ):
        if col not in out.columns:
            out[col] = ""
    latest = latest_restock_session_pack_moq_proof_events(proof_events_df)
    if latest.empty:
        return out
    latest_by_row = {
        _normalize_text(row.get("row_id", "")): row
        for _, row in latest.iterrows()
        if _normalize_text(row.get("row_id", ""))
    }
    if not latest_by_row:
        return out
    for idx, row in out.iterrows():
        proof = latest_by_row.get(_normalize_text(row.get("row_id", "")))
        if proof is None:
            continue
        for source_col, target_col in (
            ("pack_moq_proof_state", "pack_moq_proof_state"),
            ("pack_multiple", "pack_multiple"),
            ("supplier_moq", "supplier_moq"),
            ("valid_order_step", "valid_order_step"),
        ):
            value = _normalize_text(proof.get(source_col, ""))
            if value:
                out.at[idx, target_col] = value
        out.at[idx, "latest_pack_moq_proof_id"] = _normalize_text(proof.get("proof_id", ""))
        out.at[idx, "latest_pack_moq_proof_utc"] = _normalize_text(proof.get("event_utc", ""))
        out.at[idx, "latest_pack_moq_proof_file_reference"] = _normalize_text(proof.get("proof_file_reference", ""))
        out.at[idx, "latest_pack_moq_proof_note"] = _normalize_text(proof.get("proof_note", ""))
        out.at[idx, "latest_pack_moq_proof_actor"] = _normalize_text(proof.get("actor", ""))
    return out


def _supplier_batch_readiness(
    row: pd.Series,
    *,
    line_state: str,
    supplier_checklist_status: str,
    supplier_missing_reasons: str,
) -> tuple[str, str]:
    reasons: list[str] = []
    if _normalize_text(row.get("creates_live_action", "0")) not in {"", "0"}:
        reasons.append("creates_live_action_not_zero")
    if line_state != "review_only_ready":
        reasons.append(f"line_state:{line_state or 'not_ready'}")
    action_safety = _normalize_text(row.get("action_safety_state", ""))
    if action_safety not in {"", "clean_review_ready_not_po"} and line_state != "review_only_ready":
        reasons.append(f"action_safety:{action_safety}")
    if supplier_checklist_status != "supplier_proof_clear":
        supplier_reasons = [part for part in supplier_missing_reasons.split("|") if part]
        reasons.extend(f"supplier_proof:{reason}" for reason in supplier_reasons or ["not_clear"])
    order_viability = _normalize_text(row.get("supplier_order_viability_state", ""))
    if order_viability not in {"", "review_only_not_po"}:
        reasons.append(f"order_viability:{order_viability}")
    if reasons:
        return "blocked_from_purchase_approval", "|".join(dict.fromkeys(reasons))
    return "ready_for_purchase_approval_review_only", ""


def _build_batch_lines(batch_utc: str, review_df: pd.DataFrame) -> pd.DataFrame:
    if review_df.empty:
        return pd.DataFrame()
    work = review_df.copy()
    for col in (
        "latest_draft_decision_code",
        "order_qty_draft",
        "current_supplier_cost_gbp",
        "supplier_name",
        "supplier_code",
        "source_class",
        "row_id",
        "latest_draft_id",
        "latest_draft_utc",
        "seller_sku",
        "asin",
        "supplier_match_state",
        "supplier_proof_state",
        "supplier_stock_state",
        "backorder_state",
        "supplier_file_asof_utc",
        "supplier_cost_proof_state",
        "pack_moq_proof_state",
        "supplier_stock_qty",
        "backorder_eta_utc",
        "supplier_file_reference",
        "latest_supplier_proof_id",
        "latest_supplier_proof_utc",
        "latest_supplier_proof_note",
        "latest_supplier_proof_actor",
        "pack_multiple",
        "supplier_moq",
        "valid_order_step",
        "latest_pack_moq_proof_id",
        "latest_pack_moq_proof_utc",
        "latest_pack_moq_proof_file_reference",
        "latest_pack_moq_proof_note",
        "latest_pack_moq_proof_actor",
    ):
        if col not in work.columns:
            work[col] = ""
        work[col] = work[col].map(_normalize_text)
    work = work[work["latest_draft_decision_code"] == "order_qty_draft"].copy()
    if work.empty:
        return pd.DataFrame()

    rows: list[dict[str, str]] = []
    for _, row in work.iterrows():
        qty = _positive_qty(row.get("order_qty_draft", ""))
        if qty is None:
            continue
        cost = _num(row.get("current_supplier_cost_gbp", ""))
        line_value = qty * cost if cost is not None else None
        supplier_checklist_status, supplier_missing_reasons = _supplier_proof_checklist(row)
        line_state = _line_state(row)
        readiness_state, readiness_reasons = _supplier_batch_readiness(
            row,
            line_state=line_state,
            supplier_checklist_status=supplier_checklist_status,
            supplier_missing_reasons=supplier_missing_reasons,
        )
        rows.append(
            {
                "batch_utc": batch_utc,
                "batch_id": _batch_id(row.get("supplier_name", ""), row.get("supplier_code", "")),
                "session_id": _normalize_text(row.get("session_id", "")),
                "row_id": _normalize_text(row.get("row_id", "")),
                "draft_id": _normalize_text(row.get("latest_draft_id", "")),
                "draft_event_utc": _normalize_text(row.get("latest_draft_utc", "")),
                "supplier_name": _normalize_text(row.get("supplier_name", "")),
                "supplier_code": _normalize_text(row.get("supplier_code", "")),
                "source_class": _normalize_text(row.get("source_class", "")),
                "seller_sku": _normalize_text(row.get("seller_sku", "")),
                "asin": _normalize_text(row.get("asin", "")),
                "title": _normalize_text(row.get("title", "")),
                "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                "barcode": _normalize_text(row.get("barcode", "")),
                "draft_order_qty": _num_text(qty),
                "current_supplier_cost_gbp": _normalize_text(row.get("current_supplier_cost_gbp", "")),
                "draft_line_value_gbp": _num_text(line_value),
                "supplier_order_viability_state": _normalize_text(row.get("supplier_order_viability_state", "")),
                "action_safety_state": _normalize_text(row.get("action_safety_state", "")),
                "action_block_reason": _normalize_text(row.get("action_block_reason", "")),
                "line_state": line_state,
                "creates_live_action": "0",
                "supplier_proof_checklist_status": supplier_checklist_status,
                "supplier_proof_missing_reasons": supplier_missing_reasons,
                "supplier_match_state": _normalize_text(row.get("supplier_match_state", "")),
                "supplier_proof_state": _normalize_text(row.get("supplier_proof_state", "")),
                "supplier_stock_state": _normalize_text(row.get("supplier_stock_state", "")),
                "backorder_state": _normalize_text(row.get("backorder_state", "")),
                "supplier_file_asof_utc": _normalize_text(row.get("supplier_file_asof_utc", "")),
                "supplier_cost_proof_state": _normalize_text(row.get("supplier_cost_proof_state", "")),
                "pack_moq_proof_state": _normalize_text(row.get("pack_moq_proof_state", "")),
                "latest_draft_note": _normalize_text(row.get("latest_draft_note", "")),
                "row_source_reference": _normalize_text(row.get("source_reference", "")),
                "current_amazon_price_gbp": _normalize_text(row.get("current_amazon_price_gbp", "")),
                "expected_profit_per_unit_gbp": _normalize_text(row.get("expected_profit_per_unit_gbp", "")),
                "expected_roi_pct": _normalize_text(row.get("expected_roi_pct", "")),
                "profit_verdict": _normalize_text(row.get("profit_verdict", "")),
                "market_price_proof_state": _normalize_text(row.get("market_price_proof_state", "")),
                "supplier_cost_proof_state": _normalize_text(row.get("supplier_cost_proof_state", "")),
                "refund_proof_state": _normalize_text(row.get("refund_proof_state", "")),
                "inbound_cost_proof_state": _normalize_text(row.get("inbound_cost_proof_state", "")),
                "pack_multiple": _normalize_text(row.get("pack_multiple", "")),
                "supplier_moq": _normalize_text(row.get("supplier_moq", "")),
                "valid_order_step": _normalize_text(row.get("valid_order_step", "")),
                "supplier_stock_qty": _normalize_text(row.get("supplier_stock_qty", "")),
                "backorder_eta_utc": _normalize_text(row.get("backorder_eta_utc", "")),
                "supplier_file_reference": _normalize_text(row.get("supplier_file_reference", "")),
                "latest_supplier_proof_id": _normalize_text(row.get("latest_supplier_proof_id", "")),
                "latest_supplier_proof_utc": _normalize_text(row.get("latest_supplier_proof_utc", "")),
                "latest_supplier_proof_note": _normalize_text(row.get("latest_supplier_proof_note", "")),
                "latest_supplier_proof_actor": _normalize_text(row.get("latest_supplier_proof_actor", "")),
                "latest_pack_moq_proof_id": _normalize_text(row.get("latest_pack_moq_proof_id", "")),
                "latest_pack_moq_proof_utc": _normalize_text(row.get("latest_pack_moq_proof_utc", "")),
                "latest_pack_moq_proof_file_reference": _normalize_text(row.get("latest_pack_moq_proof_file_reference", "")),
                "latest_pack_moq_proof_note": _normalize_text(row.get("latest_pack_moq_proof_note", "")),
                "latest_pack_moq_proof_actor": _normalize_text(row.get("latest_pack_moq_proof_actor", "")),
                "supplier_batch_readiness_state": readiness_state,
                "supplier_batch_readiness_reasons": readiness_reasons,
            }
        )
    return pd.DataFrame(rows)


def _build_batch_summary(batch_utc: str, lines_df: pd.DataFrame) -> pd.DataFrame:
    if lines_df.empty:
        return pd.DataFrame()
    rows: list[dict[str, str]] = []
    grouped = lines_df.groupby(["batch_id", "supplier_name", "supplier_code"], dropna=False, sort=True)
    for (batch_id, supplier_name, supplier_code), group in grouped:
        qty_total = pd.to_numeric(group.get("draft_order_qty", ""), errors="coerce").fillna(0).sum()
        value_total = pd.to_numeric(group.get("draft_line_value_gbp", ""), errors="coerce").fillna(0).sum()
        source_classes = {
            _normalize_text(value)
            for value in group.get("source_class", pd.Series(dtype=str)).tolist()
            if _normalize_text(value)
        }
        blocked_count = int(group.get("line_state", pd.Series(dtype=str)).map(_normalize_text).eq("review_only_blocked").sum())
        ready_for_approval_count = int(
            group.get("supplier_batch_readiness_state", pd.Series(dtype=str))
            .map(_normalize_text)
            .eq("ready_for_purchase_approval_review_only")
            .sum()
        )
        blocked_readiness_count = int(
            group.get("supplier_batch_readiness_state", pd.Series(dtype=str))
            .map(_normalize_text)
            .eq("blocked_from_purchase_approval")
            .sum()
        )
        block_counter: Counter[str] = Counter()
        for reason_text in group.get("action_block_reason", pd.Series(dtype=str)).tolist():
            first_reason = _normalize_text(reason_text).split("|")[0]
            if first_reason:
                block_counter[first_reason] += 1
        readiness_counter: Counter[str] = Counter()
        for reason_text in group.get("supplier_batch_readiness_reasons", pd.Series(dtype=str)).tolist():
            for reason in [part for part in _normalize_text(reason_text).split("|") if part]:
                readiness_counter[reason] += 1
        batch_state = "review_only_blocked" if blocked_count else "review_only_ready"
        rows.append(
            {
                "batch_utc": batch_utc,
                "batch_id": _normalize_text(batch_id),
                "supplier_name": _normalize_text(supplier_name),
                "supplier_code": _normalize_text(supplier_code),
                "line_count": str(len(group.index)),
                "draft_order_qty_total": _num_text(float(qty_total)),
                "draft_order_value_gbp": _num_text(float(value_total)) if value_total > 0 else "",
                "source_classes": "|".join(sorted(source_classes)),
                "blocked_line_count": str(blocked_count),
                "native_line_count": str(int(group.get("source_class", pd.Series(dtype=str)).map(_normalize_text).eq("native_o").sum())),
                "legacy_bridge_line_count": str(int(group.get("source_class", pd.Series(dtype=str)).map(_normalize_text).eq("legacy_bridge").sum())),
                "batch_state": batch_state,
                "block_reasons": "|".join(reason for reason, _count in block_counter.most_common(5)),
                "creates_live_action": "0",
                "ready_for_purchase_approval_line_count": str(ready_for_approval_count),
                "blocked_readiness_line_count": str(blocked_readiness_count),
                "readiness_reasons": "|".join(reason for reason, _count in readiness_counter.most_common(8)),
            }
        )
    return pd.DataFrame(rows)


def _build_health(
    batch_utc: str,
    lines_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    proof_events_df: pd.DataFrame,
    pack_moq_events_df: pd.DataFrame,
    source_paths: list[Path],
) -> pd.DataFrame:
    source_path_text = ";".join(str(path) for path in source_paths)
    rows: list[dict[str, str]] = []

    invalid_source_rows = []
    bad_qty_rows = []
    live_action_rows = []
    live_language_rows = []
    bad_supplier_clear_rows = []
    missing_supplier_reason_rows = []
    bad_proof_event_rows = []
    bad_pack_moq_event_rows = []
    bad_readiness_rows = []
    missing_readiness_reason_rows = []
    if not proof_events_df.empty:
        for _, row in proof_events_df.iterrows():
            errors = validate_restock_session_supplier_proof_event(row.to_dict())
            if errors:
                proof_label = _normalize_text(row.get("proof_id", "")) or _normalize_text(row.get("row_id", "")) or "missing_proof"
                bad_proof_event_rows.append(f"{proof_label}:{'|'.join(errors)}")
    if not pack_moq_events_df.empty:
        for _, row in pack_moq_events_df.iterrows():
            errors = validate_restock_session_pack_moq_proof_event(row.to_dict())
            if errors:
                proof_label = _normalize_text(row.get("proof_id", "")) or _normalize_text(row.get("row_id", "")) or "missing_pack_moq_proof"
                bad_pack_moq_event_rows.append(f"{proof_label}:{'|'.join(errors)}")
    if not lines_df.empty:
        for _, row in lines_df.iterrows():
            row_id = _normalize_text(row.get("row_id", "")) or _normalize_text(row.get("seller_sku", "")) or "missing_row"
            if _normalize_text(row.get("source_class", "")) not in SOURCE_CLASSES:
                invalid_source_rows.append(row_id)
            if _positive_qty(row.get("draft_order_qty", "")) is None:
                bad_qty_rows.append(row_id)
            if _normalize_text(row.get("creates_live_action", "")) != "0":
                live_action_rows.append(row_id)
            state_text = " ".join(
                _normalize_text(row.get(col, "")).lower()
                for col in ("line_state", "action_safety_state")
            )
            if any(token in state_text for token in ("purchase_order", "committed", "sent_to_amazon")):
                live_language_rows.append(row_id)
            checklist_status = _normalize_text(row.get("supplier_proof_checklist_status", ""))
            missing_reasons = _normalize_text(row.get("supplier_proof_missing_reasons", ""))
            _expected_checklist_status, supplier_missing = _supplier_proof_checklist(row)
            if checklist_status == "supplier_proof_clear" and (supplier_missing or missing_reasons):
                bad_supplier_clear_rows.append(row_id)
            elif checklist_status == "needs_supplier_proof" and not missing_reasons:
                missing_supplier_reason_rows.append(row_id)
            elif checklist_status not in {"supplier_proof_clear", "needs_supplier_proof"}:
                missing_supplier_reason_rows.append(row_id)
            readiness_state = _normalize_text(row.get("supplier_batch_readiness_state", ""))
            readiness_reasons = _normalize_text(row.get("supplier_batch_readiness_reasons", ""))
            line_state = _normalize_text(row.get("line_state", ""))
            if readiness_state not in READINESS_STATES:
                bad_readiness_rows.append(f"{row_id}:unknown_state")
            elif readiness_state == "ready_for_purchase_approval_review_only" and (
                checklist_status != "supplier_proof_clear"
                or line_state != "review_only_ready"
                or _normalize_text(row.get("creates_live_action", "")) != "0"
            ):
                bad_readiness_rows.append(row_id)
            elif readiness_state == "blocked_from_purchase_approval" and not readiness_reasons:
                missing_readiness_reason_rows.append(row_id)

    bad_summary_rows = []
    if not summary_df.empty:
        for _, row in summary_df.iterrows():
            batch_id = _normalize_text(row.get("batch_id", "")) or "missing_batch"
            if _normalize_text(row.get("creates_live_action", "")) != "0":
                bad_summary_rows.append(f"{batch_id}:creates_live_action")
            state_text = _normalize_text(row.get("batch_state", "")).lower()
            if any(token in state_text for token in ("purchase_order", "committed", "sent_to_amazon")):
                bad_summary_rows.append(f"{batch_id}:live_language")

    checks = [
        (
            "line_source_labels",
            not invalid_source_rows,
            f"invalid={len(invalid_source_rows)};line_rows={len(lines_df.index)}",
            "Every supplier batch draft line must keep a clear source class.",
        ),
        (
            "line_quantities",
            not bad_qty_rows,
            f"bad_qty_rows={len(bad_qty_rows)};line_rows={len(lines_df.index)}",
            "Only positive whole draft quantities can become supplier batch draft lines.",
        ),
        (
            "local_only_guard",
            not live_action_rows and not bad_summary_rows and not live_language_rows,
            (
                f"live_action_lines={len(live_action_rows)};"
                f"bad_summary_rows={len(bad_summary_rows)};"
                f"live_language_rows={len(live_language_rows)}"
            ),
            "Supplier batch drafts are review-only and must not look like purchase orders or live actions.",
        ),
        (
            "supplier_proof_claim_guard",
            not bad_supplier_clear_rows and not missing_supplier_reason_rows,
            (
                f"bad_supplier_clear_rows={len(bad_supplier_clear_rows)};"
                f"missing_supplier_reason_rows={len(missing_supplier_reason_rows)}"
            ),
            "Batch lines must not claim supplier proof is clear while supplier proof is missing.",
        ),
        (
            "supplier_proof_events_local_only",
            not bad_proof_event_rows,
            f"bad_proof_event_rows={len(bad_proof_event_rows)};proof_event_rows={len(proof_events_df.index)}",
            "Supplier proof events are local proof only and must not create live buying actions.",
        ),
        (
            "pack_moq_proof_events_local_only",
            not bad_pack_moq_event_rows,
            f"bad_pack_moq_event_rows={len(bad_pack_moq_event_rows)};pack_moq_event_rows={len(pack_moq_events_df.index)}",
            "Pack/MOQ proof events are local proof only and must not create live buying actions.",
        ),
        (
            "batch_readiness_claim_guard",
            not bad_readiness_rows and not missing_readiness_reason_rows,
            (
                f"bad_readiness_rows={len(bad_readiness_rows)};"
                f"missing_readiness_reason_rows={len(missing_readiness_reason_rows)}"
            ),
            "Batch readiness must not claim a line is approval-ready while required proof is missing.",
        ),
        (
            "summary_matches_lines",
            len(summary_df.index) <= len(lines_df.index),
            f"summary_rows={len(summary_df.index)};line_rows={len(lines_df.index)}",
            "Supplier batch summary must not invent more supplier batches than draft lines allow.",
        ),
    ]
    for check, passed, value, notes in checks:
        rows.append(
            {
                "check_utc": batch_utc,
                "check": check,
                "status": "ok" if passed else "fail",
                "value": value,
                "notes": notes,
                "source_path": source_path_text,
            }
        )
    return pd.DataFrame(rows)


def build_restock_supplier_batch_drafts(
    root: Path | None = None,
    *,
    batch_utc: str | None = None,
    write_outputs: bool = True,
    refresh_session: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    paths = ensure_o_directories(root=root_path)
    observed = batch_utc or _utc_now_iso()

    if refresh_session:
        review_df, _session_summary_df, _reason_df, _session_health_df = build_restock_session_view(
            root=root_path,
            session_utc=observed,
            write_outputs=write_outputs,
        )
    else:
        review_df = read_o_contract_df(root_path, "restock_session_review_live")

    ensure_restock_session_supplier_proof_event_file(root_path)
    ensure_restock_session_pack_moq_proof_event_file(root_path)
    proof_events_df = read_o_contract_df(root_path, "restock_session_supplier_proof_events")
    pack_moq_events_df = read_o_contract_df(root_path, "restock_session_pack_moq_proof_events")
    review_df = _apply_latest_supplier_proof_events(review_df, proof_events_df)
    review_df = _apply_latest_pack_moq_proof_events(review_df, pack_moq_events_df)
    lines_df = _build_batch_lines(observed, review_df)
    summary_df = _build_batch_summary(observed, lines_df)
    source_paths = [
        root_path / "out" / "systems" / "O" / "live" / "restock_session_review_live.csv",
        root_path / "out" / "systems" / "O" / "live" / "restock_session_draft_decision_events.csv",
        root_path / "out" / "systems" / "O" / "live" / "restock_session_supplier_proof_events.csv",
        root_path / "out" / "systems" / "O" / "live" / "restock_session_pack_moq_proof_events.csv",
    ]
    health_df = _build_health(observed, lines_df, summary_df, proof_events_df, pack_moq_events_df, source_paths)

    if write_outputs:
        lines_df = write_o_contract_df(root_path, "restock_session_supplier_batch_lines_live", lines_df)
        summary_df = write_o_contract_df(root_path, "restock_session_supplier_batch_summary_live", summary_df)
        health_df = write_o_contract_df(root_path, "restock_session_supplier_batch_health", health_df)
        history_dir = paths.history_dir / f"supplier_batch_drafts_v1_{observed.replace(':', '').replace('-', '')}"
        history_dir.mkdir(parents=True, exist_ok=True)
        lines_df.to_csv(history_dir / "restock_session_supplier_batch_lines_live.csv", index=False)
        summary_df.to_csv(history_dir / "restock_session_supplier_batch_summary_live.csv", index=False)
        health_df.to_csv(history_dir / "restock_session_supplier_batch_health.csv", index=False)

    return lines_df, summary_df, health_df


def main() -> int:
    lines_df, summary_df, health_df = build_restock_supplier_batch_drafts()
    bad_health = health_df[health_df.get("status", "").map(_normalize_text).ne("ok")]
    print(f"batch_line_rows={len(lines_df.index)}")
    print(f"batch_summary_rows={len(summary_df.index)}")
    print(f"health_status={'ok' if bad_health.empty else 'fail'}")
    return 0 if bad_health.empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
