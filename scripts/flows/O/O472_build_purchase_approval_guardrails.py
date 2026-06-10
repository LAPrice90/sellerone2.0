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

from scripts.flows.O.O470_build_purchase_approval_preview import build_purchase_approval_preview
from scripts.flows.O._contract_io import append_o_contract_row, o_contract_columns, read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract


DECISION_EVENT_CONTRACT = "restock_purchase_approval_decision_events"
GUARDRAIL_CONTRACT = "restock_purchase_approval_guardrails_live"
HEALTH_CONTRACT = "restock_purchase_approval_guardrails_health"
DECISION_STATUS = "draft_guardrail_decision"
PREVIEW_READY_STATE = "ready_for_purchase_approval_review_only"
ACCEPT_STATE = "local_review_accept_not_commitment"
REJECT_STATE = "local_review_reject"
MORE_PROOF_STATE = "local_review_more_proof_needed"
ALLOWED_DECISION_STATES = {ACCEPT_STATE, REJECT_STATE, MORE_PROOF_STATE}
NO_DECISION_STATE = "no_local_review_decision"
BLOCKED_PREVIEW_STATE = "blocked_preview_not_ready"
STALE_DECISION_STATE = "blocked_local_review_stale"
UNSAFE_TEXT_TOKENS = (
    "purchase_order",
    "purchase order",
    "po_created",
    "po created",
    "committed",
    "sent_to_amazon",
    "sent to amazon",
    "buy_committed",
    "approved_for_po",
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
        "accept": ACCEPT_STATE,
        "accepted": ACCEPT_STATE,
        "local_accept": ACCEPT_STATE,
        "local_review_accept": ACCEPT_STATE,
        "ok": ACCEPT_STATE,
        "reject": REJECT_STATE,
        "rejected": REJECT_STATE,
        "local_reject": REJECT_STATE,
        "needs_more_proof": MORE_PROOF_STATE,
        "more_proof": MORE_PROOF_STATE,
        "more_proof_needed": MORE_PROOF_STATE,
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


def normalize_purchase_approval_decision_event(row: dict[str, object]) -> dict[str, str]:
    normalized = {column: _normalize_text(row.get(column, "")) for column in o_contract_columns(DECISION_EVENT_CONTRACT)}
    normalized["event_utc"] = _normalize_utc(normalized["event_utc"]) or _utc_now_iso()
    normalized["decision_id"] = normalized["decision_id"] or f"o-purchase-approval-guard-{uuid.uuid4().hex[:12]}"
    normalized["source_preview_utc"] = _normalize_utc(normalized["source_preview_utc"])
    normalized["decision_state"] = _normalize_decision_state(normalized["decision_state"])
    normalized["expected_line_count"] = _positive_int_text(normalized["expected_line_count"])
    normalized["expected_ready_line_count"] = _nonnegative_int_text(normalized["expected_ready_line_count"])
    normalized["expected_blocked_line_count"] = _nonnegative_int_text(normalized["expected_blocked_line_count"])
    normalized["expected_order_value_gbp"] = _money_text(normalized["expected_order_value_gbp"])
    normalized["actor"] = normalized["actor"] or "operator_ui"
    normalized["event_source_reference"] = normalized["event_source_reference"] or "o_ui_purchase_approval_guardrails"
    normalized["decision_status"] = DECISION_STATUS
    normalized["creates_live_action"] = "0"
    return normalized


def validate_purchase_approval_decision_event(row: dict[str, object]) -> list[str]:
    normalized = normalize_purchase_approval_decision_event(row)
    errors: list[str] = []
    raw_decision_state = _normalize_text(row.get("decision_state", ""))
    raw_decision_status = _normalize_text(row.get("decision_status", DECISION_STATUS)) or DECISION_STATUS
    raw_creates_live_action = _normalize_text(row.get("creates_live_action", "0")) or "0"
    raw_expected_line_count = _normalize_text(row.get("expected_line_count", ""))
    raw_expected_ready_count = _normalize_text(row.get("expected_ready_line_count", ""))
    raw_expected_blocked_count = _normalize_text(row.get("expected_blocked_line_count", ""))
    raw_expected_order_value = _normalize_text(row.get("expected_order_value_gbp", ""))
    if normalized["approval_packet_id"] == "":
        errors.append("missing_approval_packet_id")
    if raw_decision_state and normalized["decision_state"] == "":
        errors.append("unsupported_decision_state")
    if normalized["decision_state"] not in ALLOWED_DECISION_STATES:
        errors.append("missing_decision_state")
    if raw_expected_line_count and normalized["expected_line_count"] == "":
        errors.append("invalid_expected_line_count")
    if raw_expected_ready_count and normalized["expected_ready_line_count"] == "":
        errors.append("invalid_expected_ready_line_count")
    if raw_expected_blocked_count and normalized["expected_blocked_line_count"] == "":
        errors.append("invalid_expected_blocked_line_count")
    if raw_expected_order_value and normalized["expected_order_value_gbp"] == "":
        errors.append("invalid_expected_order_value_gbp")
    if raw_decision_status != DECISION_STATUS:
        errors.append("decision_status_must_be_draft_guardrail_decision")
    if raw_creates_live_action != "0":
        errors.append("creates_live_action_must_be_zero")
    if _contains_unsafe_language(
        row.get("decision_state", ""),
        row.get("decision_status", ""),
        row.get("decision_note", ""),
        row.get("event_source_reference", ""),
    ):
        errors.append("unsafe_live_language")
    return errors


def build_purchase_approval_decision_row(
    *,
    preview_summary_row: dict[str, object],
    decision_state: object,
    decision_note: object = "",
    actor: str = "operator_ui",
    event_source_reference: str = "o_ui_purchase_approval_guardrails",
) -> dict[str, str]:
    source = {key: _normalize_text(value) for key, value in dict(preview_summary_row).items()}
    row = {
        "event_utc": _utc_now_iso(),
        "decision_id": f"o-purchase-approval-guard-{uuid.uuid4().hex[:12]}",
        "approval_packet_id": source.get("approval_packet_id", ""),
        "supplier_name": source.get("supplier_name", ""),
        "supplier_code": source.get("supplier_code", ""),
        "source_preview_utc": source.get("preview_utc", ""),
        "decision_state": decision_state,
        "expected_line_count": source.get("line_count", ""),
        "expected_ready_line_count": source.get("ready_line_count", ""),
        "expected_blocked_line_count": source.get("blocked_line_count", ""),
        "expected_order_value_gbp": source.get("draft_order_value_gbp", ""),
        "decision_note": decision_note,
        "actor": actor,
        "event_source_reference": event_source_reference,
        "decision_status": DECISION_STATUS,
        "creates_live_action": "0",
        "source_classes": source.get("source_classes", ""),
    }
    normalized = normalize_purchase_approval_decision_event(row)
    errors = validate_purchase_approval_decision_event(normalized)
    if errors:
        raise ValueError(";".join(errors))
    return normalized


def _summary_is_ready(row: dict[str, object]) -> bool:
    line_count = _positive_int_text(row.get("line_count", ""))
    ready_count = _nonnegative_int_text(row.get("ready_line_count", ""))
    blocked_count = _nonnegative_int_text(row.get("blocked_line_count", ""))
    return (
        _normalize_text(row.get("approval_packet_state", "")) == PREVIEW_READY_STATE
        and line_count != ""
        and ready_count == line_count
        and blocked_count in {"", "0"}
        and _normalize_text(row.get("creates_live_action", "")) == "0"
    )


def _event_matches_summary(event: dict[str, object], summary: dict[str, object]) -> bool:
    expected_pairs = (
        ("source_preview_utc", "preview_utc"),
        ("expected_line_count", "line_count"),
        ("expected_ready_line_count", "ready_line_count"),
        ("expected_blocked_line_count", "blocked_line_count"),
        ("expected_order_value_gbp", "draft_order_value_gbp"),
    )
    for event_col, summary_col in expected_pairs:
        event_value = _normalize_text(event.get(event_col, ""))
        summary_value = _normalize_text(summary.get(summary_col, ""))
        if event_value and summary_value and event_value != summary_value:
            return False
    return True


def submit_purchase_approval_decision_event(
    *,
    root: Path | None = None,
    preview_summary_row: dict[str, object],
    decision_state: object,
    decision_note: object = "",
    actor: str = "operator_ui",
    event_source_reference: str = "o_ui_purchase_approval_guardrails",
) -> dict[str, str]:
    normalized_state = _normalize_decision_state(decision_state)
    if normalized_state == ACCEPT_STATE and not _summary_is_ready(preview_summary_row):
        raise ValueError("local_review_accept_requires_ready_preview_packet")
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    row = build_purchase_approval_decision_row(
        preview_summary_row=preview_summary_row,
        decision_state=decision_state,
        decision_note=decision_note,
        actor=actor,
        event_source_reference=event_source_reference,
    )
    return append_o_contract_row(root_path, DECISION_EVENT_CONTRACT, row)


def latest_purchase_approval_decision_events(events_df: pd.DataFrame) -> pd.DataFrame:
    if events_df.empty:
        return pd.DataFrame(columns=o_contract_columns(DECISION_EVENT_CONTRACT))
    work = events_df.copy()
    for column in o_contract_columns(DECISION_EVENT_CONTRACT):
        if column not in work.columns:
            work[column] = ""
        work[column] = work[column].map(_normalize_text)
    good_mask = []
    for _, row in work.iterrows():
        good_mask.append(validate_purchase_approval_decision_event(row.to_dict()) == [])
    work = work[pd.Series(good_mask, index=work.index)].copy()
    if work.empty:
        return work.drop(columns=["_event_sort"], errors="ignore")
    work["_event_sort"] = pd.to_datetime(work["event_utc"], errors="coerce", utc=True)
    work = work.sort_values(by=["_event_sort", "decision_id"], ascending=[False, False], kind="stable")
    work = work.drop_duplicates(subset=["approval_packet_id"], keep="first")
    return work.drop(columns=["_event_sort"], errors="ignore").reset_index(drop=True)


def _build_guardrails(guardrail_utc: str, summary_df: pd.DataFrame, latest_events_df: pd.DataFrame) -> pd.DataFrame:
    if summary_df.empty:
        return pd.DataFrame()
    latest_by_packet = {
        _normalize_text(row.get("approval_packet_id", "")): row.to_dict()
        for _, row in latest_events_df.iterrows()
        if _normalize_text(row.get("approval_packet_id", ""))
    }
    rows: list[dict[str, str]] = []
    for _, summary_row in summary_df.iterrows():
        summary = {key: _normalize_text(value) for key, value in summary_row.to_dict().items()}
        packet_id = summary.get("approval_packet_id", "")
        latest = latest_by_packet.get(packet_id, {})
        latest_state = _normalize_text(latest.get("decision_state", "")) or NO_DECISION_STATE
        reasons: list[str] = []
        if not _summary_is_ready(summary):
            guardrail_state = BLOCKED_PREVIEW_STATE
            reasons.extend([part for part in summary.get("approval_block_reasons", "").split("|") if part])
            if not reasons:
                reasons.append("preview_packet_not_ready")
        elif latest_state == NO_DECISION_STATE:
            guardrail_state = NO_DECISION_STATE
            reasons.append("no_local_review_decision")
        elif latest_state == ACCEPT_STATE:
            if _event_matches_summary(latest, summary):
                guardrail_state = ACCEPT_STATE
            else:
                guardrail_state = STALE_DECISION_STATE
                reasons.append("decision_preview_stale")
        elif latest_state == REJECT_STATE:
            guardrail_state = REJECT_STATE
            reasons.append("local_review_rejected")
        elif latest_state == MORE_PROOF_STATE:
            guardrail_state = MORE_PROOF_STATE
            reasons.append("local_review_more_proof_needed")
        else:
            guardrail_state = NO_DECISION_STATE
            reasons.append("unsupported_latest_decision_state")
        rows.append(
            {
                "guardrail_utc": guardrail_utc,
                "approval_packet_id": packet_id,
                "source_preview_utc": summary.get("preview_utc", ""),
                "supplier_name": summary.get("supplier_name", ""),
                "supplier_code": summary.get("supplier_code", ""),
                "line_count": summary.get("line_count", ""),
                "ready_line_count": summary.get("ready_line_count", ""),
                "blocked_line_count": summary.get("blocked_line_count", ""),
                "draft_order_value_gbp": summary.get("draft_order_value_gbp", ""),
                "preview_packet_state": summary.get("approval_packet_state", ""),
                "latest_decision_state": latest_state,
                "latest_decision_id": _normalize_text(latest.get("decision_id", "")),
                "latest_decision_utc": _normalize_text(latest.get("event_utc", "")),
                "approval_guardrail_state": guardrail_state,
                "approval_guardrail_reasons": "|".join(dict.fromkeys(reasons)),
                "creates_live_action": "0",
                "source_classes": summary.get("source_classes", ""),
                "latest_decision_note": _normalize_text(latest.get("decision_note", "")),
            }
        )
    return pd.DataFrame(rows)


def _bad_event_ids(events_df: pd.DataFrame) -> list[str]:
    bad: list[str] = []
    for idx, row in events_df.iterrows():
        if validate_purchase_approval_decision_event(row.to_dict()):
            bad.append(_normalize_text(row.get("decision_id", "")) or f"row_{idx + 1}")
    return bad


def _unsafe_event_ids(events_df: pd.DataFrame) -> list[str]:
    unsafe: list[str] = []
    for idx, row in events_df.iterrows():
        row_id = _normalize_text(row.get("decision_id", "")) or f"row_{idx + 1}"
        if _normalize_text(row.get("creates_live_action", "")) != "0":
            unsafe.append(row_id)
            continue
        if _contains_unsafe_language(
            row.get("decision_state", ""),
            row.get("decision_status", ""),
            row.get("decision_note", ""),
            row.get("event_source_reference", ""),
        ):
            unsafe.append(row_id)
    return unsafe


def _build_health(
    guardrail_utc: str,
    events_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    guardrails_df: pd.DataFrame,
    source_paths: list[Path],
) -> pd.DataFrame:
    bad_events = _bad_event_ids(events_df)
    unsafe_events = _unsafe_event_ids(events_df)
    unsafe_guard_rows: list[str] = []
    false_accept_rows: list[str] = []
    invented_packet_rows: list[str] = []
    source_packet_ids = {
        _normalize_text(row.get("approval_packet_id", ""))
        for _, row in summary_df.iterrows()
        if _normalize_text(row.get("approval_packet_id", ""))
    }
    if not guardrails_df.empty:
        for _, row in guardrails_df.iterrows():
            packet_id = _normalize_text(row.get("approval_packet_id", "")) or "missing_packet"
            if packet_id not in source_packet_ids:
                invented_packet_rows.append(packet_id)
            if _normalize_text(row.get("creates_live_action", "")) != "0":
                unsafe_guard_rows.append(packet_id)
            if _contains_unsafe_language(row.get("approval_guardrail_state", ""), row.get("approval_guardrail_reasons", "")):
                unsafe_guard_rows.append(packet_id)
            if _normalize_text(row.get("approval_guardrail_state", "")) == ACCEPT_STATE and (
                _normalize_text(row.get("preview_packet_state", "")) != PREVIEW_READY_STATE
                or _normalize_text(row.get("latest_decision_state", "")) != ACCEPT_STATE
                or _normalize_text(row.get("creates_live_action", "")) != "0"
            ):
                false_accept_rows.append(packet_id)

    checks = [
        (
            "decision_event_contract",
            not bad_events,
            f"event_rows={len(events_df.index)};invalid_events={len(bad_events)}",
            "Local approval decision events must be valid draft guardrail events.",
        ),
        (
            "local_only_guard",
            not unsafe_events and not unsafe_guard_rows,
            f"unsafe_events={len(unsafe_events)};unsafe_guard_rows={len(unsafe_guard_rows)}",
            "Approval guardrails must not look like purchase orders, commitments, or live actions.",
        ),
        (
            "acceptance_guard",
            not false_accept_rows,
            f"false_accept_rows={len(false_accept_rows)}",
            "A local accept state is allowed only when the current preview packet is still ready.",
        ),
        (
            "summary_matches_preview",
            not invented_packet_rows and len(guardrails_df.index) <= len(summary_df.index),
            f"guardrail_rows={len(guardrails_df.index)};preview_packets={len(summary_df.index)};invented_packets={len(invented_packet_rows)}",
            "Approval guardrails must be built from current preview packets only.",
        ),
    ]
    source_path_text = ";".join(str(path) for path in source_paths)
    return pd.DataFrame(
        [
            {
                "check_utc": guardrail_utc,
                "check": check,
                "status": "ok" if passed else "fail",
                "value": value,
                "notes": notes,
                "source_path": source_path_text,
            }
            for check, passed, value, notes in checks
        ]
    )


def ensure_purchase_approval_decision_event_file(root: Path | None = None) -> Path:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    contract_path = root_path / "out" / "systems" / "O" / "live" / "restock_purchase_approval_decision_events.csv"
    if not contract_path.exists():
        write_o_contract_df(root_path, DECISION_EVENT_CONTRACT, pd.DataFrame(columns=o_contract_columns(DECISION_EVENT_CONTRACT)))
    return contract_path


def build_purchase_approval_guardrails(
    root: Path | None = None,
    *,
    guardrail_utc: str | None = None,
    write_outputs: bool = True,
    refresh_preview: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    paths = ensure_o_directories(root=root_path)
    observed = guardrail_utc or _utc_now_iso()
    ensure_purchase_approval_decision_event_file(root_path)
    if refresh_preview:
        _lines_df, summary_df, _preview_health_df = build_purchase_approval_preview(
            root=root_path,
            preview_utc=observed,
            write_outputs=write_outputs,
            refresh_batches=True,
        )
    else:
        summary_df = read_o_contract_df(root_path, "restock_purchase_approval_preview_summary_live")

    events_df = read_o_contract_df(root_path, DECISION_EVENT_CONTRACT)
    latest_events_df = latest_purchase_approval_decision_events(events_df)
    guardrails_df = _build_guardrails(observed, summary_df, latest_events_df)
    source_paths = [
        root_path / "out" / "systems" / "O" / "live" / "restock_purchase_approval_preview_summary_live.csv",
        root_path / "out" / "systems" / "O" / "live" / "restock_purchase_approval_decision_events.csv",
    ]
    health_df = _build_health(observed, events_df, summary_df, guardrails_df, source_paths)

    if write_outputs:
        guardrails_df = write_o_contract_df(root_path, GUARDRAIL_CONTRACT, guardrails_df)
        health_df = write_o_contract_df(root_path, HEALTH_CONTRACT, health_df)
        history_dir = paths.history_dir / f"purchase_approval_guardrails_v1_{observed.replace(':', '').replace('-', '')}"
        history_dir.mkdir(parents=True, exist_ok=True)
        events_df.to_csv(history_dir / "restock_purchase_approval_decision_events.csv", index=False)
        guardrails_df.to_csv(history_dir / "restock_purchase_approval_guardrails_live.csv", index=False)
        health_df.to_csv(history_dir / "restock_purchase_approval_guardrails_health.csv", index=False)

    return events_df, guardrails_df, health_df


def main() -> int:
    events_df, guardrails_df, health_df = build_purchase_approval_guardrails()
    bad_health = health_df[health_df.get("status", "").map(_normalize_text).ne("ok")]
    print(f"approval_decision_event_rows={len(events_df.index)}")
    print(f"approval_guardrail_rows={len(guardrails_df.index)}")
    print(f"health_status={'ok' if bad_health.empty else 'fail'}")
    return 0 if bad_health.empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
