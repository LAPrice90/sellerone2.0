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

from scripts.flows.O.O472_build_purchase_approval_guardrails import build_purchase_approval_guardrails
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract


SOURCE_CLASSES = {"native_o", "legacy_bridge", "feeder_review_handoff", "manual_walkthrough_fixture"}
PREVIEW_READY_STATE = "ready_for_purchase_approval_review_only"
GUARD_ACCEPT_STATE = "local_review_accept_not_commitment"
READY_STATE = "ready_for_local_po_draft_review_only"
BLOCKED_STATE = "blocked_from_local_po_draft_review"
PREVIEW_ID_PREFIX = "o_po_draft_readiness_preview_v1"
UNSAFE_TEXT_TOKENS = (
    "purchase_order",
    "purchase order",
    "po_created",
    "po created",
    "committed",
    "sent_to_amazon",
    "sent to amazon",
    "buy_committed",
    "approval_applied",
    "live_action",
)


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
        parsed = float(text)
    except ValueError:
        return None
    return parsed


def _positive_num(value: object) -> float | None:
    parsed = _num(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed


def _num_text(value: float | None) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _preview_id(packet_id: object) -> str:
    return f"{PREVIEW_ID_PREFIX}:{_safe_fragment(packet_id)}"


def _contains_unsafe_language(*values: object) -> bool:
    text = " ".join(_normalize_text(value).lower() for value in values)
    return any(token in text for token in UNSAFE_TEXT_TOKENS)


def _line_value(row: pd.Series) -> str:
    existing = _positive_num(row.get("draft_line_value_gbp", ""))
    if existing is not None:
        return _num_text(existing)
    qty = _positive_num(row.get("draft_order_qty", ""))
    cost = _positive_num(row.get("current_supplier_cost_gbp", ""))
    if qty is None or cost is None:
        return ""
    return _num_text(qty * cost)


def _readiness_state(row: pd.Series, guardrail: dict[str, str]) -> tuple[str, str]:
    reasons: list[str] = []
    source_class = _normalize_text(row.get("source_class", ""))
    if source_class not in SOURCE_CLASSES:
        reasons.append("unsupported_source_class")
    if _normalize_text(row.get("creates_live_action", "")) != "0":
        reasons.append("approval_preview_creates_live_action")
    if _normalize_text(guardrail.get("creates_live_action", "")) not in {"", "0"}:
        reasons.append("approval_guardrail_creates_live_action")
    if _normalize_text(row.get("approval_preview_state", "")) != PREVIEW_READY_STATE:
        reasons.append("approval_preview_not_ready")
    if _normalize_text(guardrail.get("approval_guardrail_state", "")) != GUARD_ACCEPT_STATE:
        reasons.append("local_review_not_accepted")
    if _positive_num(row.get("draft_order_qty", "")) is None:
        reasons.append("missing_or_invalid_draft_qty")
    if _positive_num(row.get("current_supplier_cost_gbp", "")) is None:
        reasons.append("missing_or_invalid_unit_cost")
    if _line_value(row) == "":
        reasons.append("missing_or_invalid_line_value")
    if _normalize_text(row.get("supplier_proof_checklist_status", "")) != "supplier_proof_clear":
        reasons.append("supplier_proof_not_clear")
    if reasons:
        return BLOCKED_STATE, "|".join(dict.fromkeys(reasons))
    return READY_STATE, ""


def _build_lines(preview_utc: str, approval_lines_df: pd.DataFrame, guardrails_df: pd.DataFrame) -> pd.DataFrame:
    if approval_lines_df.empty:
        return pd.DataFrame()
    guardrail_by_packet = {
        _normalize_text(row.get("approval_packet_id", "")): {key: _normalize_text(value) for key, value in row.to_dict().items()}
        for _, row in guardrails_df.iterrows()
        if _normalize_text(row.get("approval_packet_id", ""))
    }
    rows: list[dict[str, str]] = []
    for _, line in approval_lines_df.iterrows():
        packet_id = _normalize_text(line.get("approval_packet_id", ""))
        guardrail = guardrail_by_packet.get(packet_id, {})
        state, reasons = _readiness_state(line, guardrail)
        rows.append(
            {
                "preview_utc": preview_utc,
                "po_readiness_preview_id": _preview_id(packet_id),
                "approval_packet_id": packet_id,
                "source_preview_utc": _normalize_text(line.get("preview_utc", "")),
                "guardrail_utc": _normalize_text(guardrail.get("guardrail_utc", "")),
                "batch_id": _normalize_text(line.get("batch_id", "")),
                "session_id": _normalize_text(line.get("session_id", "")),
                "row_id": _normalize_text(line.get("row_id", "")),
                "supplier_name": _normalize_text(line.get("supplier_name", "")),
                "supplier_code": _normalize_text(line.get("supplier_code", "")),
                "source_class": _normalize_text(line.get("source_class", "")),
                "seller_sku": _normalize_text(line.get("seller_sku", "")),
                "asin": _normalize_text(line.get("asin", "")),
                "title": _normalize_text(line.get("title", "")),
                "supplier_sku": _normalize_text(line.get("supplier_sku", "")),
                "barcode": _normalize_text(line.get("barcode", "")),
                "draft_order_qty": _normalize_text(line.get("draft_order_qty", "")),
                "current_supplier_cost_gbp": _normalize_text(line.get("current_supplier_cost_gbp", "")),
                "draft_line_value_gbp": _line_value(line),
                "approval_preview_state": _normalize_text(line.get("approval_preview_state", "")),
                "approval_guardrail_state": _normalize_text(guardrail.get("approval_guardrail_state", "")),
                "po_draft_readiness_state": state,
                "po_draft_block_reasons": reasons,
                "po_creation_allowed": "0",
                "creates_live_action": "0",
                "supplier_proof_checklist_status": _normalize_text(line.get("supplier_proof_checklist_status", "")),
                "supplier_proof_missing_reasons": _normalize_text(line.get("supplier_proof_missing_reasons", "")),
                "expected_profit_per_unit_gbp": _normalize_text(line.get("expected_profit_per_unit_gbp", "")),
                "expected_roi_pct": _normalize_text(line.get("expected_roi_pct", "")),
                "profit_verdict": _normalize_text(line.get("profit_verdict", "")),
                "market_price_proof_state": _normalize_text(line.get("market_price_proof_state", "")),
                "refund_proof_state": _normalize_text(line.get("refund_proof_state", "")),
                "inbound_cost_proof_state": _normalize_text(line.get("inbound_cost_proof_state", "")),
                "latest_supplier_proof_id": _normalize_text(line.get("latest_supplier_proof_id", "")),
                "latest_pack_moq_proof_id": _normalize_text(line.get("latest_pack_moq_proof_id", "")),
                "source_classes": _normalize_text(guardrail.get("source_classes", "")),
            }
        )
    return pd.DataFrame(rows)


def _build_summary(preview_utc: str, lines_df: pd.DataFrame) -> pd.DataFrame:
    if lines_df.empty:
        return pd.DataFrame()
    rows: list[dict[str, str]] = []
    grouped = lines_df.groupby(
        ["po_readiness_preview_id", "approval_packet_id", "supplier_name", "supplier_code"],
        dropna=False,
        sort=True,
    )
    for (preview_id, packet_id, supplier_name, supplier_code), group in grouped:
        ready_count = int(group.get("po_draft_readiness_state", pd.Series(dtype=str)).map(_normalize_text).eq(READY_STATE).sum())
        blocked_count = int(group.get("po_draft_readiness_state", pd.Series(dtype=str)).map(_normalize_text).eq(BLOCKED_STATE).sum())
        qty_total = pd.to_numeric(group.get("draft_order_qty", ""), errors="coerce").fillna(0).sum()
        value_total = pd.to_numeric(group.get("draft_line_value_gbp", ""), errors="coerce").fillna(0).sum()
        reason_counter: Counter[str] = Counter()
        for reason_text in group.get("po_draft_block_reasons", pd.Series(dtype=str)).tolist():
            for reason in [part for part in _normalize_text(reason_text).split("|") if part]:
                reason_counter[reason] += 1
        guard_states = {
            _normalize_text(value)
            for value in group.get("approval_guardrail_state", pd.Series(dtype=str)).tolist()
            if _normalize_text(value)
        }
        source_classes = {
            _normalize_text(value)
            for value in group.get("source_class", pd.Series(dtype=str)).tolist()
            if _normalize_text(value)
        }
        packet_state = READY_STATE if ready_count and not blocked_count else BLOCKED_STATE
        rows.append(
            {
                "preview_utc": preview_utc,
                "po_readiness_preview_id": _normalize_text(preview_id),
                "approval_packet_id": _normalize_text(packet_id),
                "supplier_name": _normalize_text(supplier_name),
                "supplier_code": _normalize_text(supplier_code),
                "line_count": str(len(group.index)),
                "ready_line_count": str(ready_count),
                "blocked_line_count": str(blocked_count),
                "draft_order_qty_total": _num_text(float(qty_total)),
                "draft_order_value_gbp": _num_text(float(value_total)) if value_total > 0 else "",
                "approval_guardrail_state": "|".join(sorted(guard_states)),
                "po_draft_preview_state": packet_state,
                "po_draft_block_reasons": "|".join(reason for reason, _count in reason_counter.most_common(8)),
                "po_creation_allowed": "0",
                "creates_live_action": "0",
                "source_classes": "|".join(sorted(source_classes)),
            }
        )
    return pd.DataFrame(rows)


def _build_health(preview_utc: str, lines_df: pd.DataFrame, summary_df: pd.DataFrame, source_paths: list[Path]) -> pd.DataFrame:
    invalid_source_rows: list[str] = []
    live_action_rows: list[str] = []
    false_ready_rows: list[str] = []
    missing_block_reason_rows: list[str] = []
    live_language_rows: list[str] = []
    bad_summary_rows: list[str] = []
    if not lines_df.empty:
        for _, row in lines_df.iterrows():
            row_label = _normalize_text(row.get("row_id", "")) or _normalize_text(row.get("seller_sku", "")) or "missing_row"
            if _normalize_text(row.get("source_class", "")) not in SOURCE_CLASSES:
                invalid_source_rows.append(row_label)
            if _normalize_text(row.get("creates_live_action", "")) != "0" or _normalize_text(row.get("po_creation_allowed", "")) != "0":
                live_action_rows.append(row_label)
            if _contains_unsafe_language(row.get("po_draft_readiness_state", ""), row.get("po_draft_block_reasons", "")):
                live_language_rows.append(row_label)
            if _normalize_text(row.get("po_draft_readiness_state", "")) == READY_STATE and (
                _normalize_text(row.get("approval_preview_state", "")) != PREVIEW_READY_STATE
                or _normalize_text(row.get("approval_guardrail_state", "")) != GUARD_ACCEPT_STATE
                or _positive_num(row.get("draft_order_qty", "")) is None
                or _positive_num(row.get("current_supplier_cost_gbp", "")) is None
                or _normalize_text(row.get("supplier_proof_checklist_status", "")) != "supplier_proof_clear"
            ):
                false_ready_rows.append(row_label)
            if _normalize_text(row.get("po_draft_readiness_state", "")) == BLOCKED_STATE and _normalize_text(row.get("po_draft_block_reasons", "")) == "":
                missing_block_reason_rows.append(row_label)
    if not summary_df.empty:
        for _, row in summary_df.iterrows():
            packet_id = _normalize_text(row.get("approval_packet_id", "")) or "missing_packet"
            if _normalize_text(row.get("creates_live_action", "")) != "0" or _normalize_text(row.get("po_creation_allowed", "")) != "0":
                bad_summary_rows.append(f"{packet_id}:live_action")
            if _contains_unsafe_language(row.get("po_draft_preview_state", ""), row.get("po_draft_block_reasons", "")):
                bad_summary_rows.append(f"{packet_id}:live_language")
    checks = [
        (
            "source_label_guard",
            not invalid_source_rows,
            f"invalid_source_rows={len(invalid_source_rows)};line_rows={len(lines_df.index)}",
            "Every PO readiness preview line must keep an approved O source class.",
        ),
        (
            "local_only_guard",
            not live_action_rows and not bad_summary_rows and not live_language_rows,
            (
                f"live_action_rows={len(live_action_rows)};"
                f"bad_summary_rows={len(bad_summary_rows)};"
                f"live_language_rows={len(live_language_rows)}"
            ),
            "PO readiness preview must not create POs, allow PO creation, or look like a buying commitment.",
        ),
        (
            "readiness_claim_guard",
            not false_ready_rows and not missing_block_reason_rows,
            (
                f"false_ready_rows={len(false_ready_rows)};"
                f"missing_block_reason_rows={len(missing_block_reason_rows)}"
            ),
            "A line can only be PO-draft-review ready after local review acceptance, clear proof, quantity, and cost.",
        ),
        (
            "summary_matches_lines",
            len(summary_df.index) <= len(lines_df.index),
            f"summary_rows={len(summary_df.index)};line_rows={len(lines_df.index)}",
            "PO readiness summary must not invent packets beyond preview lines.",
        ),
    ]
    source_path_text = ";".join(str(path) for path in source_paths)
    return pd.DataFrame(
        [
            {
                "check_utc": preview_utc,
                "check": check,
                "status": "ok" if passed else "fail",
                "value": value,
                "notes": notes,
                "source_path": source_path_text,
            }
            for check, passed, value, notes in checks
        ]
    )


def build_po_draft_readiness_preview(
    root: Path | None = None,
    *,
    preview_utc: str | None = None,
    write_outputs: bool = True,
    refresh_guardrails: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    paths = ensure_o_directories(root=root_path)
    observed = preview_utc or _utc_now_iso()
    if refresh_guardrails:
        build_purchase_approval_guardrails(
            root=root_path,
            guardrail_utc=observed,
            write_outputs=write_outputs,
            refresh_preview=True,
        )
    approval_lines_df = read_o_contract_df(root_path, "restock_purchase_approval_preview_lines_live")
    guardrails_df = read_o_contract_df(root_path, "restock_purchase_approval_guardrails_live")
    lines_df = _build_lines(observed, approval_lines_df, guardrails_df)
    summary_df = _build_summary(observed, lines_df)
    source_paths = [
        root_path / "out" / "systems" / "O" / "live" / "restock_purchase_approval_preview_lines_live.csv",
        root_path / "out" / "systems" / "O" / "live" / "restock_purchase_approval_guardrails_live.csv",
    ]
    health_df = _build_health(observed, lines_df, summary_df, source_paths)
    if write_outputs:
        lines_df = write_o_contract_df(root_path, "restock_po_draft_readiness_preview_lines_live", lines_df)
        summary_df = write_o_contract_df(root_path, "restock_po_draft_readiness_preview_summary_live", summary_df)
        health_df = write_o_contract_df(root_path, "restock_po_draft_readiness_preview_health", health_df)
        history_dir = paths.history_dir / f"po_draft_readiness_preview_v1_{observed.replace(':', '').replace('-', '')}"
        history_dir.mkdir(parents=True, exist_ok=True)
        lines_df.to_csv(history_dir / "restock_po_draft_readiness_preview_lines_live.csv", index=False)
        summary_df.to_csv(history_dir / "restock_po_draft_readiness_preview_summary_live.csv", index=False)
        health_df.to_csv(history_dir / "restock_po_draft_readiness_preview_health.csv", index=False)
    return lines_df, summary_df, health_df


def main() -> int:
    lines_df, summary_df, health_df = build_po_draft_readiness_preview()
    bad_health = health_df[health_df.get("status", "").map(_normalize_text).ne("ok")]
    print(f"po_draft_readiness_line_rows={len(lines_df.index)}")
    print(f"po_draft_readiness_summary_rows={len(summary_df.index)}")
    print(f"health_status={'ok' if bad_health.empty else 'fail'}")
    return 0 if bad_health.empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
