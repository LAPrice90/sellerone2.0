from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BOOT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT))

from scripts.flows.O.O488_build_po_draft_export_preview import build_po_draft_export_preview
from scripts.flows.O._contract_io import append_o_contract_row, o_contract_columns, read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract


GATE_EVENT_CONTRACT = "restock_po_draft_export_gate_events"
GATE_STATE_CONTRACT = "restock_po_draft_export_gate_live"
GATE_HEALTH_CONTRACT = "restock_po_draft_export_gate_health"
DECISION_STATUS = "local_po_draft_export_gate"
EXPORT_READY_STATE = "ready_for_local_po_draft_export_preview_only"
MORE_PROOF_STATE = "local_export_more_proof_needed"
HOLD_STATE = "local_export_keep_on_hold"
CANDIDATE_READY_STATE = "local_export_candidate_ready_not_po"
ALLOWED_DECISION_STATES = {MORE_PROOF_STATE, HOLD_STATE, CANDIDATE_READY_STATE}
NO_DECISION_STATE = "waiting_for_local_export_gate_control"
BLOCKED_SOURCE_STATE = "blocked_export_preview_not_ready"
STALE_DECISION_STATE = "blocked_local_export_gate_stale"
FALSE_READY_STATE = "blocked_false_local_export_candidate_ready"
ZERO_FLAG_COLUMNS = (
    "po_file_write_allowed",
    "po_creation_allowed",
    "purchase_commitment_allowed",
    "receiving_allowed",
    "send_to_amazon_allowed",
    "creates_live_action",
)
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


def _normalize_token(value: object) -> str:
    return "_".join(_normalize_text(value).lower().replace("-", "_").split())


def _normalize_decision_state(value: object) -> str:
    token = _normalize_token(value)
    aliases = {
        "more_proof": MORE_PROOF_STATE,
        "needs_more_proof": MORE_PROOF_STATE,
        "hold": HOLD_STATE,
        "keep_on_hold": HOLD_STATE,
        "candidate_ready": CANDIDATE_READY_STATE,
        "ready": CANDIDATE_READY_STATE,
        "ready_not_po": CANDIDATE_READY_STATE,
    }
    token = aliases.get(token, token)
    return token if token in ALLOWED_DECISION_STATES else ""


def _positive_int_text(value: object) -> str:
    text = _normalize_text(value).replace(",", "")
    if text == "":
        return ""
    try:
        parsed = float(text)
    except ValueError:
        return ""
    if parsed <= 0 or not parsed.is_integer():
        return ""
    return str(int(parsed))


def _nonnegative_int_text(value: object) -> str:
    text = _normalize_text(value).replace(",", "")
    if text == "":
        return ""
    try:
        parsed = float(text)
    except ValueError:
        return ""
    if parsed < 0 or not parsed.is_integer():
        return ""
    return str(int(parsed))


def _money_text(value: object) -> str:
    text = _normalize_text(value).replace(",", "")
    if text == "":
        return ""
    try:
        parsed = float(text)
    except ValueError:
        return ""
    if parsed < 0:
        return ""
    if parsed.is_integer():
        return str(int(parsed))
    return f"{parsed:.6f}".rstrip("0").rstrip(".")


def _normalize_utc(value: object) -> str:
    text = _normalize_text(value)
    if text == "":
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _contains_unsafe_language(*values: object) -> bool:
    text = " ".join(_normalize_text(value).lower() for value in values)
    return any(token in text for token in UNSAFE_TEXT_TOKENS)


def _all_zero_flags(row: dict[str, object]) -> bool:
    return all(_normalize_text(row.get(column, "")) == "0" for column in ZERO_FLAG_COLUMNS)


def _summary_is_export_ready(row: dict[str, object]) -> bool:
    line_count = _positive_int_text(row.get("line_count", ""))
    ready_count = _nonnegative_int_text(row.get("ready_line_count", ""))
    blocked_count = _nonnegative_int_text(row.get("blocked_line_count", ""))
    return (
        _normalize_text(row.get("export_preview_state", "")) == EXPORT_READY_STATE
        and line_count != ""
        and ready_count == line_count
        and blocked_count in {"", "0"}
        and _all_zero_flags(row)
    )


def normalize_po_draft_export_gate_event(row: dict[str, object]) -> dict[str, str]:
    normalized = {column: _normalize_text(row.get(column, "")) for column in o_contract_columns(GATE_EVENT_CONTRACT)}
    normalized["event_utc"] = _normalize_utc(normalized["event_utc"]) or _utc_now_iso()
    normalized["gate_event_id"] = normalized["gate_event_id"] or f"o-po-export-gate-{uuid.uuid4().hex[:12]}"
    normalized["source_export_preview_utc"] = _normalize_utc(normalized["source_export_preview_utc"])
    normalized["decision_state"] = _normalize_decision_state(normalized["decision_state"])
    normalized["expected_line_count"] = _positive_int_text(normalized["expected_line_count"])
    normalized["expected_ready_line_count"] = _nonnegative_int_text(normalized["expected_ready_line_count"])
    normalized["expected_blocked_line_count"] = _nonnegative_int_text(normalized["expected_blocked_line_count"])
    normalized["expected_export_preview_value_gbp"] = _money_text(normalized["expected_export_preview_value_gbp"])
    normalized["actor"] = normalized["actor"] or "operator_ui"
    normalized["event_source_reference"] = normalized["event_source_reference"] or "o_ui_po_draft_export_gate"
    normalized["decision_status"] = DECISION_STATUS
    for column in ZERO_FLAG_COLUMNS:
        normalized[column] = "0"
    return normalized


def validate_po_draft_export_gate_event(row: dict[str, object]) -> list[str]:
    normalized = normalize_po_draft_export_gate_event(row)
    errors: list[str] = []
    raw_decision_state = _normalize_text(row.get("decision_state", ""))
    raw_decision_status = _normalize_text(row.get("decision_status", DECISION_STATUS)) or DECISION_STATUS
    if normalized["po_draft_export_preview_id"] == "":
        errors.append("missing_export_preview_id")
    if raw_decision_state and normalized["decision_state"] == "":
        errors.append("unsupported_decision_state")
    if normalized["decision_state"] not in ALLOWED_DECISION_STATES:
        errors.append("missing_decision_state")
    if raw_decision_status != DECISION_STATUS:
        errors.append("decision_status_must_be_local_po_draft_export_gate")
    for column in ZERO_FLAG_COLUMNS:
        if _normalize_text(row.get(column, "0")) != "0":
            errors.append(f"{column}_must_be_zero")
    if _contains_unsafe_language(
        row.get("decision_state", ""),
        row.get("decision_status", ""),
        row.get("decision_note", ""),
        row.get("event_source_reference", ""),
    ):
        errors.append("unsafe_live_language")
    return errors


def build_po_draft_export_gate_event_row(
    *,
    export_summary_row: dict[str, object],
    decision_state: object,
    decision_note: object = "",
    actor: str = "operator_ui",
    event_source_reference: str = "o_ui_po_draft_export_gate",
) -> dict[str, str]:
    source = {key: _normalize_text(value) for key, value in dict(export_summary_row).items()}
    row = {
        "event_utc": _utc_now_iso(),
        "gate_event_id": f"o-po-export-gate-{uuid.uuid4().hex[:12]}",
        "po_draft_export_preview_id": source.get("po_draft_export_preview_id", ""),
        "po_draft_file_shape_preview_id": source.get("po_draft_file_shape_preview_id", ""),
        "po_draft_hold_review_id": source.get("po_draft_hold_review_id", ""),
        "po_draft_packet_review_id": source.get("po_draft_packet_review_id", ""),
        "po_line_design_packet_id": source.get("po_line_design_packet_id", ""),
        "approval_packet_id": source.get("approval_packet_id", ""),
        "supplier_name": source.get("supplier_name", ""),
        "supplier_code": source.get("supplier_code", ""),
        "source_export_preview_utc": source.get("export_preview_utc", ""),
        "decision_state": decision_state,
        "expected_line_count": source.get("line_count", ""),
        "expected_ready_line_count": source.get("ready_line_count", ""),
        "expected_blocked_line_count": source.get("blocked_line_count", ""),
        "expected_export_preview_value_gbp": source.get("export_preview_value_gbp", ""),
        "decision_note": decision_note,
        "actor": actor,
        "event_source_reference": event_source_reference,
        "decision_status": DECISION_STATUS,
        "source_classes": source.get("source_classes", ""),
    }
    for column in ZERO_FLAG_COLUMNS:
        row[column] = "0"
    normalized = normalize_po_draft_export_gate_event(row)
    errors = validate_po_draft_export_gate_event(normalized)
    if errors:
        raise ValueError(";".join(errors))
    return normalized


def submit_po_draft_export_gate_event(
    *,
    root: Path | None = None,
    export_summary_row: dict[str, object],
    decision_state: object,
    decision_note: object = "",
    actor: str = "operator_ui",
    event_source_reference: str = "o_ui_po_draft_export_gate",
) -> dict[str, str]:
    normalized_state = _normalize_decision_state(decision_state)
    if not _all_zero_flags(dict(export_summary_row)):
        raise ValueError("local_po_draft_export_gate_requires_zero_action_flags")
    if normalized_state == CANDIDATE_READY_STATE and not _summary_is_export_ready(dict(export_summary_row)):
        raise ValueError("local_export_candidate_ready_requires_ready_export_preview")
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    row = build_po_draft_export_gate_event_row(
        export_summary_row=export_summary_row,
        decision_state=decision_state,
        decision_note=decision_note,
        actor=actor,
        event_source_reference=event_source_reference,
    )
    return append_o_contract_row(root_path, GATE_EVENT_CONTRACT, row)


def latest_po_draft_export_gate_events(events_df: pd.DataFrame) -> pd.DataFrame:
    if events_df.empty:
        return pd.DataFrame(columns=o_contract_columns(GATE_EVENT_CONTRACT))
    work = events_df.copy()
    for column in o_contract_columns(GATE_EVENT_CONTRACT):
        if column not in work.columns:
            work[column] = ""
        work[column] = work[column].map(_normalize_text)
    good_mask = []
    for _, row in work.iterrows():
        good_mask.append(validate_po_draft_export_gate_event(row.to_dict()) == [])
    work = work[pd.Series(good_mask, index=work.index)].copy()
    if work.empty:
        return work.drop(columns=["_event_sort"], errors="ignore")
    work["_event_sort"] = pd.to_datetime(work["event_utc"], errors="coerce", utc=True)
    work = work.sort_values(by=["_event_sort", "gate_event_id"], ascending=[False, False], kind="stable")
    work = work.drop_duplicates(subset=["po_draft_export_preview_id"], keep="first")
    return work.drop(columns=["_event_sort"], errors="ignore").reset_index(drop=True)


def _event_matches_summary(event: dict[str, object], summary: dict[str, object]) -> bool:
    expected_pairs = (
        ("source_export_preview_utc", "export_preview_utc"),
        ("expected_line_count", "line_count"),
        ("expected_ready_line_count", "ready_line_count"),
        ("expected_blocked_line_count", "blocked_line_count"),
        ("expected_export_preview_value_gbp", "export_preview_value_gbp"),
    )
    for event_col, summary_col in expected_pairs:
        event_value = _normalize_text(event.get(event_col, ""))
        summary_value = _normalize_text(summary.get(summary_col, ""))
        if event_value and summary_value and event_value != summary_value:
            return False
    return True


def _build_gates(gate_utc: str, summary_df: pd.DataFrame, latest_events_df: pd.DataFrame) -> pd.DataFrame:
    if summary_df.empty:
        return pd.DataFrame()
    latest_by_export = {
        _normalize_text(row.get("po_draft_export_preview_id", "")): row.to_dict()
        for _, row in latest_events_df.iterrows()
        if _normalize_text(row.get("po_draft_export_preview_id", ""))
    }
    rows: list[dict[str, str]] = []
    for _, summary_row in summary_df.iterrows():
        summary = {key: _normalize_text(value) for key, value in summary_row.to_dict().items()}
        preview_id = summary.get("po_draft_export_preview_id", "")
        latest = latest_by_export.get(preview_id, {})
        latest_state = _normalize_text(latest.get("decision_state", "")) or NO_DECISION_STATE
        reasons: list[str] = []
        export_ready = _summary_is_export_ready(summary)
        if not _all_zero_flags(summary):
            gate_state = BLOCKED_SOURCE_STATE
            reasons.append("source_action_flags_not_zero")
        elif not export_ready and latest_state == CANDIDATE_READY_STATE:
            gate_state = FALSE_READY_STATE
            reasons.append("candidate_ready_decision_without_ready_export_preview")
        elif not export_ready:
            gate_state = BLOCKED_SOURCE_STATE
            for reason in summary.get("export_preview_block_reasons", "").split("|"):
                if reason:
                    reasons.append(reason)
            if not reasons:
                reasons.append("export_preview_not_ready")
        elif latest_state == NO_DECISION_STATE:
            gate_state = NO_DECISION_STATE
            reasons.append("no_local_export_gate_control")
        elif latest_state == CANDIDATE_READY_STATE:
            if _event_matches_summary(latest, summary):
                gate_state = CANDIDATE_READY_STATE
            else:
                gate_state = STALE_DECISION_STATE
                reasons.append("export_gate_preview_stale")
        elif latest_state == HOLD_STATE:
            gate_state = HOLD_STATE
            reasons.append("kept_on_local_hold")
        elif latest_state == MORE_PROOF_STATE:
            gate_state = MORE_PROOF_STATE
            reasons.append("more_proof_needed")
        else:
            gate_state = NO_DECISION_STATE
            reasons.append("unsupported_latest_decision_state")
        row = {
            "gate_utc": gate_utc,
            "po_draft_export_preview_id": preview_id,
            "po_draft_file_shape_preview_id": summary.get("po_draft_file_shape_preview_id", ""),
            "po_draft_hold_review_id": summary.get("po_draft_hold_review_id", ""),
            "po_draft_packet_review_id": summary.get("po_draft_packet_review_id", ""),
            "po_line_design_packet_id": summary.get("po_line_design_packet_id", ""),
            "approval_packet_id": summary.get("approval_packet_id", ""),
            "source_export_preview_utc": summary.get("export_preview_utc", ""),
            "supplier_name": summary.get("supplier_name", ""),
            "supplier_code": summary.get("supplier_code", ""),
            "line_count": summary.get("line_count", ""),
            "ready_line_count": summary.get("ready_line_count", ""),
            "blocked_line_count": summary.get("blocked_line_count", ""),
            "export_preview_value_gbp": summary.get("export_preview_value_gbp", ""),
            "source_export_preview_state": summary.get("export_preview_state", ""),
            "latest_decision_state": latest_state,
            "latest_gate_event_id": _normalize_text(latest.get("gate_event_id", "")),
            "latest_decision_utc": _normalize_text(latest.get("event_utc", "")),
            "export_gate_state": gate_state,
            "export_gate_reasons": "|".join(dict.fromkeys(reasons)),
            "source_classes": summary.get("source_classes", ""),
            "latest_decision_note": _normalize_text(latest.get("decision_note", "")),
        }
        for column in ZERO_FLAG_COLUMNS:
            row[column] = "0"
        rows.append(row)
    return pd.DataFrame(rows)


def _build_health(
    gate_utc: str,
    gates_df: pd.DataFrame,
    events_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    source_paths: list[Path],
) -> pd.DataFrame:
    invalid_event_rows: list[str] = []
    live_action_rows: list[str] = []
    live_language_rows: list[str] = []
    false_ready_rows: list[str] = []
    missing_reason_rows: list[str] = []
    for _, event in events_df.iterrows():
        event_id = _normalize_text(event.get("gate_event_id", "")) or "missing_event"
        errors = validate_po_draft_export_gate_event(event.to_dict())
        if errors:
            invalid_event_rows.append(event_id)
        if any(_normalize_text(event.get(column, "")) != "0" for column in ZERO_FLAG_COLUMNS):
            live_action_rows.append(event_id)
        if _contains_unsafe_language(
            event.get("decision_state", ""),
            event.get("decision_status", ""),
            event.get("decision_note", ""),
            event.get("event_source_reference", ""),
        ):
            live_language_rows.append(event_id)
    for _, row in gates_df.iterrows():
        preview_id = _normalize_text(row.get("po_draft_export_preview_id", "")) or "missing_export"
        if any(_normalize_text(row.get(column, "")) != "0" for column in ZERO_FLAG_COLUMNS):
            live_action_rows.append(preview_id)
        if _contains_unsafe_language(
            row.get("export_gate_state", ""),
            row.get("export_gate_reasons", ""),
            row.get("latest_decision_note", ""),
        ):
            live_language_rows.append(preview_id)
        gate_state = _normalize_text(row.get("export_gate_state", ""))
        if gate_state == FALSE_READY_STATE:
            false_ready_rows.append(preview_id)
        if gate_state == CANDIDATE_READY_STATE and (
            _normalize_text(row.get("source_export_preview_state", "")) != EXPORT_READY_STATE
            or _positive_int_text(row.get("line_count", "")) == ""
            or _normalize_text(row.get("ready_line_count", "")) != _normalize_text(row.get("line_count", ""))
            or _normalize_text(row.get("blocked_line_count", "")) not in {"", "0"}
        ):
            false_ready_rows.append(preview_id)
        if gate_state != CANDIDATE_READY_STATE and _normalize_text(row.get("export_gate_reasons", "")) == "":
            missing_reason_rows.append(preview_id)
    checks = [
        (
            "event_contract_guard",
            not invalid_event_rows,
            f"invalid_event_rows={len(invalid_event_rows)};event_rows={len(events_df.index)}",
            "Every PO draft export-gate event must be local-only and complete.",
        ),
        (
            "local_only_guard",
            not live_action_rows and not live_language_rows,
            f"live_action_rows={len(live_action_rows)};live_language_rows={len(live_language_rows)}",
            "PO draft export gate must not write PO files, create POs, commit buying, receive stock, or send to Amazon.",
        ),
        (
            "gate_claim_guard",
            not false_ready_rows and not missing_reason_rows,
            f"false_ready_rows={len(false_ready_rows)};missing_reason_rows={len(missing_reason_rows)}",
            "A packet can only be candidate-ready after safe export-preview proof; non-ready states must explain why.",
        ),
        (
            "summary_matches_gates",
            len(gates_df.index) <= len(summary_df.index),
            f"gate_rows={len(gates_df.index)};summary_rows={len(summary_df.index)}",
            "PO draft export gates must not invent packets beyond export-preview summaries.",
        ),
    ]
    source_path_text = ";".join(str(path) for path in source_paths)
    return pd.DataFrame(
        [
            {
                "check_utc": gate_utc,
                "check": check,
                "status": "ok" if passed else "fail",
                "value": value,
                "notes": notes,
                "source_path": source_path_text,
            }
            for check, passed, value, notes in checks
        ]
    )


def build_po_draft_export_gate(
    root: Path | None = None,
    *,
    gate_utc: str | None = None,
    write_outputs: bool = True,
    refresh_export_preview: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    paths = ensure_o_directories(root=root_path)
    observed = gate_utc or _utc_now_iso()
    if refresh_export_preview:
        build_po_draft_export_preview(
            root=root_path,
            export_preview_utc=observed,
            write_outputs=write_outputs,
            refresh_review_controls=True,
        )
    summary_df = read_o_contract_df(root_path, "restock_po_draft_export_preview_summary_live")
    events_df = read_o_contract_df(root_path, GATE_EVENT_CONTRACT)
    event_path = root_path / "out" / "systems" / "O" / "live" / "restock_po_draft_export_gate_events.csv"
    if write_outputs and not event_path.exists():
        events_df = write_o_contract_df(root_path, GATE_EVENT_CONTRACT, events_df)
    latest_events_df = latest_po_draft_export_gate_events(events_df)
    gates_df = _build_gates(observed, summary_df, latest_events_df)
    source_paths = [
        root_path / "out" / "systems" / "O" / "live" / "restock_po_draft_export_preview_summary_live.csv",
        event_path,
    ]
    health_df = _build_health(observed, gates_df, events_df, summary_df, source_paths)
    if write_outputs:
        gates_df = write_o_contract_df(root_path, GATE_STATE_CONTRACT, gates_df)
        health_df = write_o_contract_df(root_path, GATE_HEALTH_CONTRACT, health_df)
        history_dir = paths.history_dir / f"po_draft_export_gate_v1_{observed.replace(':', '').replace('-', '')}"
        history_dir.mkdir(parents=True, exist_ok=True)
        gates_df.to_csv(history_dir / "restock_po_draft_export_gate_live.csv", index=False)
        health_df.to_csv(history_dir / "restock_po_draft_export_gate_health.csv", index=False)
    return gates_df, health_df


def main() -> int:
    gates_df, health_df = build_po_draft_export_gate()
    event_rows = read_o_contract_df(get_o_path_contract().root, GATE_EVENT_CONTRACT)
    bad_health = health_df[health_df.get("status", "").map(_normalize_text).ne("ok")]
    print(f"po_draft_export_gate_rows={len(gates_df.index)}")
    print(f"po_draft_export_gate_event_rows={len(event_rows.index)}")
    print(f"health_status={'ok' if bad_health.empty else 'fail'}")
    return 0 if bad_health.empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
