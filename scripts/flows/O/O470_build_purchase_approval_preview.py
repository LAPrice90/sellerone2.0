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

from scripts.flows.O.O464_build_restock_supplier_batch_drafts import build_restock_supplier_batch_drafts
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract


PREVIEW_ID_PREFIX = "o_purchase_approval_preview_v1"
SOURCE_CLASSES = {"native_o", "legacy_bridge", "feeder_review_handoff", "manual_walkthrough_fixture"}
READY_STATE = "ready_for_purchase_approval_review_only"
BLOCKED_STATE = "blocked_from_purchase_approval_review"


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


def _packet_id(row: pd.Series) -> str:
    batch_id = _normalize_text(row.get("batch_id", ""))
    if batch_id:
        return f"{PREVIEW_ID_PREFIX}:{_safe_fragment(batch_id)}"
    supplier_key = _normalize_text(row.get("supplier_code", "")) or _normalize_text(row.get("supplier_name", ""))
    return f"{PREVIEW_ID_PREFIX}:{_safe_fragment(supplier_key)}"


def _approval_state(row: pd.Series) -> tuple[str, str]:
    reasons: list[str] = []
    source_class = _normalize_text(row.get("source_class", ""))
    readiness_state = _normalize_text(row.get("supplier_batch_readiness_state", ""))
    readiness_reasons = _normalize_text(row.get("supplier_batch_readiness_reasons", ""))
    checklist_status = _normalize_text(row.get("supplier_proof_checklist_status", ""))
    creates_live_action = _normalize_text(row.get("creates_live_action", ""))
    if source_class not in SOURCE_CLASSES:
        reasons.append("unsupported_source_class")
    if creates_live_action != "0":
        reasons.append("creates_live_action_not_zero")
    if readiness_state != "ready_for_purchase_approval_review_only":
        reasons.extend([part for part in readiness_reasons.split("|") if part] or ["supplier_batch_not_ready"])
    if checklist_status != "supplier_proof_clear":
        missing = _normalize_text(row.get("supplier_proof_missing_reasons", ""))
        reasons.extend(f"supplier_proof:{part}" for part in missing.split("|") if part)
    if reasons:
        return BLOCKED_STATE, "|".join(dict.fromkeys(reasons))
    return READY_STATE, ""


def _build_preview_lines(preview_utc: str, batch_lines_df: pd.DataFrame) -> pd.DataFrame:
    if batch_lines_df.empty:
        return pd.DataFrame()
    work = batch_lines_df.copy()
    required = (
        "batch_id",
        "session_id",
        "row_id",
        "supplier_name",
        "supplier_code",
        "source_class",
        "seller_sku",
        "asin",
        "title",
        "supplier_sku",
        "barcode",
        "draft_order_qty",
        "current_supplier_cost_gbp",
        "draft_line_value_gbp",
        "supplier_batch_readiness_state",
        "supplier_batch_readiness_reasons",
        "supplier_proof_checklist_status",
        "supplier_proof_missing_reasons",
    )
    for col in required:
        if col not in work.columns:
            work[col] = ""
        work[col] = work[col].map(_normalize_text)

    rows: list[dict[str, str]] = []
    for _, row in work.iterrows():
        state, block_reasons = _approval_state(row)
        rows.append(
            {
                "preview_utc": preview_utc,
                "approval_packet_id": _packet_id(row),
                "batch_id": _normalize_text(row.get("batch_id", "")),
                "session_id": _normalize_text(row.get("session_id", "")),
                "row_id": _normalize_text(row.get("row_id", "")),
                "supplier_name": _normalize_text(row.get("supplier_name", "")),
                "supplier_code": _normalize_text(row.get("supplier_code", "")),
                "source_class": _normalize_text(row.get("source_class", "")),
                "seller_sku": _normalize_text(row.get("seller_sku", "")),
                "asin": _normalize_text(row.get("asin", "")),
                "title": _normalize_text(row.get("title", "")),
                "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                "barcode": _normalize_text(row.get("barcode", "")),
                "draft_order_qty": _normalize_text(row.get("draft_order_qty", "")),
                "current_supplier_cost_gbp": _normalize_text(row.get("current_supplier_cost_gbp", "")),
                "draft_line_value_gbp": _normalize_text(row.get("draft_line_value_gbp", "")),
                "supplier_batch_readiness_state": _normalize_text(row.get("supplier_batch_readiness_state", "")),
                "supplier_batch_readiness_reasons": _normalize_text(row.get("supplier_batch_readiness_reasons", "")),
                "supplier_proof_checklist_status": _normalize_text(row.get("supplier_proof_checklist_status", "")),
                "supplier_proof_missing_reasons": _normalize_text(row.get("supplier_proof_missing_reasons", "")),
                "approval_preview_state": state,
                "approval_block_reasons": block_reasons,
                "creates_live_action": "0",
                "supplier_stock_state": _normalize_text(row.get("supplier_stock_state", "")),
                "supplier_stock_qty": _normalize_text(row.get("supplier_stock_qty", "")),
                "backorder_state": _normalize_text(row.get("backorder_state", "")),
                "supplier_file_asof_utc": _normalize_text(row.get("supplier_file_asof_utc", "")),
                "pack_moq_proof_state": _normalize_text(row.get("pack_moq_proof_state", "")),
                "pack_multiple": _normalize_text(row.get("pack_multiple", "")),
                "supplier_moq": _normalize_text(row.get("supplier_moq", "")),
                "valid_order_step": _normalize_text(row.get("valid_order_step", "")),
                "expected_profit_per_unit_gbp": _normalize_text(row.get("expected_profit_per_unit_gbp", "")),
                "expected_roi_pct": _normalize_text(row.get("expected_roi_pct", "")),
                "profit_verdict": _normalize_text(row.get("profit_verdict", "")),
                "market_price_proof_state": _normalize_text(row.get("market_price_proof_state", "")),
                "refund_proof_state": _normalize_text(row.get("refund_proof_state", "")),
                "inbound_cost_proof_state": _normalize_text(row.get("inbound_cost_proof_state", "")),
                "latest_supplier_proof_id": _normalize_text(row.get("latest_supplier_proof_id", "")),
                "latest_pack_moq_proof_id": _normalize_text(row.get("latest_pack_moq_proof_id", "")),
            }
        )
    return pd.DataFrame(rows)


def _build_preview_summary(preview_utc: str, lines_df: pd.DataFrame) -> pd.DataFrame:
    if lines_df.empty:
        return pd.DataFrame()
    rows: list[dict[str, str]] = []
    grouped = lines_df.groupby(["approval_packet_id", "supplier_name", "supplier_code"], dropna=False, sort=True)
    for (packet_id, supplier_name, supplier_code), group in grouped:
        qty_total = pd.to_numeric(group.get("draft_order_qty", ""), errors="coerce").fillna(0).sum()
        value_total = pd.to_numeric(group.get("draft_line_value_gbp", ""), errors="coerce").fillna(0).sum()
        ready_count = int(group.get("approval_preview_state", pd.Series(dtype=str)).map(_normalize_text).eq(READY_STATE).sum())
        blocked_count = int(group.get("approval_preview_state", pd.Series(dtype=str)).map(_normalize_text).eq(BLOCKED_STATE).sum())
        source_classes = {
            _normalize_text(value)
            for value in group.get("source_class", pd.Series(dtype=str)).tolist()
            if _normalize_text(value)
        }
        reason_counter: Counter[str] = Counter()
        for reason_text in group.get("approval_block_reasons", pd.Series(dtype=str)).tolist():
            for reason in [part for part in _normalize_text(reason_text).split("|") if part]:
                reason_counter[reason] += 1
        packet_state = READY_STATE if ready_count and not blocked_count else BLOCKED_STATE
        rows.append(
            {
                "preview_utc": preview_utc,
                "approval_packet_id": _normalize_text(packet_id),
                "supplier_name": _normalize_text(supplier_name),
                "supplier_code": _normalize_text(supplier_code),
                "line_count": str(len(group.index)),
                "draft_order_qty_total": _num_text(float(qty_total)),
                "draft_order_value_gbp": _num_text(float(value_total)) if value_total > 0 else "",
                "ready_line_count": str(ready_count),
                "blocked_line_count": str(blocked_count),
                "source_classes": "|".join(sorted(source_classes)),
                "approval_packet_state": packet_state,
                "approval_block_reasons": "|".join(reason for reason, _count in reason_counter.most_common(8)),
                "creates_live_action": "0",
            }
        )
    return pd.DataFrame(rows)


def _build_health(preview_utc: str, lines_df: pd.DataFrame, summary_df: pd.DataFrame, source_paths: list[Path]) -> pd.DataFrame:
    source_path_text = ";".join(str(path) for path in source_paths)
    invalid_source_rows: list[str] = []
    live_action_rows: list[str] = []
    live_language_rows: list[str] = []
    false_ready_rows: list[str] = []
    missing_block_reason_rows: list[str] = []
    bad_summary_rows: list[str] = []

    if not lines_df.empty:
        for _, row in lines_df.iterrows():
            row_id = _normalize_text(row.get("row_id", "")) or _normalize_text(row.get("seller_sku", "")) or "missing_row"
            if _normalize_text(row.get("source_class", "")) not in SOURCE_CLASSES:
                invalid_source_rows.append(row_id)
            if _normalize_text(row.get("creates_live_action", "")) != "0":
                live_action_rows.append(row_id)
            state_text = " ".join(
                _normalize_text(row.get(col, "")).lower()
                for col in ("approval_preview_state", "supplier_batch_readiness_state")
            )
            if any(token in state_text for token in ("purchase_order", "committed", "sent_to_amazon", "approved")):
                live_language_rows.append(row_id)
            if _normalize_text(row.get("approval_preview_state", "")) == READY_STATE and (
                _normalize_text(row.get("supplier_batch_readiness_state", "")) != "ready_for_purchase_approval_review_only"
                or _normalize_text(row.get("supplier_proof_checklist_status", "")) != "supplier_proof_clear"
            ):
                false_ready_rows.append(row_id)
            if _normalize_text(row.get("approval_preview_state", "")) == BLOCKED_STATE and _normalize_text(row.get("approval_block_reasons", "")) == "":
                missing_block_reason_rows.append(row_id)

    if not summary_df.empty:
        for _, row in summary_df.iterrows():
            packet_id = _normalize_text(row.get("approval_packet_id", "")) or "missing_packet"
            if _normalize_text(row.get("creates_live_action", "")) != "0":
                bad_summary_rows.append(f"{packet_id}:creates_live_action")
            state_text = _normalize_text(row.get("approval_packet_state", "")).lower()
            if any(token in state_text for token in ("purchase_order", "committed", "sent_to_amazon", "approved")):
                bad_summary_rows.append(f"{packet_id}:live_language")

    checks = [
        (
            "preview_source_labels",
            not invalid_source_rows,
            f"invalid_source_rows={len(invalid_source_rows)};line_rows={len(lines_df.index)}",
            "Every approval preview line must keep an approved source class.",
        ),
        (
            "local_only_guard",
            not live_action_rows and not bad_summary_rows and not live_language_rows,
            (
                f"live_action_rows={len(live_action_rows)};"
                f"bad_summary_rows={len(bad_summary_rows)};"
                f"live_language_rows={len(live_language_rows)}"
            ),
            "Approval preview is review-only and must not look like a PO, approval, or live action.",
        ),
        (
            "ready_claim_guard",
            not false_ready_rows and not missing_block_reason_rows,
            (
                f"false_ready_rows={len(false_ready_rows)};"
                f"missing_block_reason_rows={len(missing_block_reason_rows)}"
            ),
            "Preview lines must not claim approval readiness while batch readiness or supplier proof is missing.",
        ),
        (
            "summary_matches_lines",
            len(summary_df.index) <= len(lines_df.index),
            f"summary_rows={len(summary_df.index)};line_rows={len(lines_df.index)}",
            "Approval preview summary must not invent more packets than preview lines allow.",
        ),
    ]
    rows = []
    for check, passed, value, notes in checks:
        rows.append(
            {
                "check_utc": preview_utc,
                "check": check,
                "status": "ok" if passed else "fail",
                "value": value,
                "notes": notes,
                "source_path": source_path_text,
            }
        )
    return pd.DataFrame(rows)


def build_purchase_approval_preview(
    root: Path | None = None,
    *,
    preview_utc: str | None = None,
    write_outputs: bool = True,
    refresh_batches: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    paths = ensure_o_directories(root=root_path)
    observed = preview_utc or _utc_now_iso()

    if refresh_batches:
        batch_lines_df, _batch_summary_df, _batch_health_df = build_restock_supplier_batch_drafts(
            root=root_path,
            batch_utc=observed,
            write_outputs=write_outputs,
            refresh_session=False,
        )
    else:
        batch_lines_df = read_o_contract_df(root_path, "restock_session_supplier_batch_lines_live")

    lines_df = _build_preview_lines(observed, batch_lines_df)
    summary_df = _build_preview_summary(observed, lines_df)
    source_paths = [
        root_path / "out" / "systems" / "O" / "live" / "restock_session_supplier_batch_lines_live.csv",
        root_path / "out" / "systems" / "O" / "live" / "restock_session_supplier_batch_summary_live.csv",
        root_path / "out" / "systems" / "O" / "live" / "restock_session_supplier_batch_health.csv",
    ]
    health_df = _build_health(observed, lines_df, summary_df, source_paths)

    if write_outputs:
        lines_df = write_o_contract_df(root_path, "restock_purchase_approval_preview_lines_live", lines_df)
        summary_df = write_o_contract_df(root_path, "restock_purchase_approval_preview_summary_live", summary_df)
        health_df = write_o_contract_df(root_path, "restock_purchase_approval_preview_health", health_df)
        history_dir = paths.history_dir / f"purchase_approval_preview_v1_{observed.replace(':', '').replace('-', '')}"
        history_dir.mkdir(parents=True, exist_ok=True)
        lines_df.to_csv(history_dir / "restock_purchase_approval_preview_lines_live.csv", index=False)
        summary_df.to_csv(history_dir / "restock_purchase_approval_preview_summary_live.csv", index=False)
        health_df.to_csv(history_dir / "restock_purchase_approval_preview_health.csv", index=False)

    return lines_df, summary_df, health_df


def main() -> int:
    lines_df, summary_df, health_df = build_purchase_approval_preview()
    bad_health = health_df[health_df.get("status", "").map(_normalize_text).ne("ok")]
    print(f"approval_preview_line_rows={len(lines_df.index)}")
    print(f"approval_preview_summary_rows={len(summary_df.index)}")
    print(f"health_status={'ok' if bad_health.empty else 'fail'}")
    return 0 if bad_health.empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
