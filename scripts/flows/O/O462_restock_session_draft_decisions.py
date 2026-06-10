from __future__ import annotations

import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

BOOT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT))

from scripts.flows.O.O460_build_restock_session_view import DECISION_REASON_ROWS, SESSION_ID, SOURCE_CLASSES
from scripts.flows.O._contract_io import append_o_contract_row, o_contract_columns, read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract


DRAFT_DECISION_CONTRACT = "restock_session_draft_decision_events"
ALLOWED_DRAFT_DECISION_CODES = {row["reason_code"] for row in DECISION_REASON_ROWS}
DECISION_LABEL_TO_CODE = {
    str(row["reason_label"]).strip().lower().replace(" ", "_").replace("-", "_"): row["reason_code"]
    for row in DECISION_REASON_ROWS
}
DRAFT_STATUS = "draft"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_decision_code(value: object) -> str:
    token = _normalize_text(value).lower().replace("-", "_").replace(" ", "_")
    token = "_".join(part for part in token.split("_") if part)
    if token in ALLOWED_DRAFT_DECISION_CODES:
        return token
    return DECISION_LABEL_TO_CODE.get(token, "")


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


def _normalize_snooze_until(value: object) -> str:
    if isinstance(value, date) and not isinstance(value, datetime):
        return f"{value.isoformat()}T00:00:00Z"
    text = _normalize_text(value)
    if text == "":
        return ""
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        try:
            parsed_date = date.fromisoformat(text)
        except ValueError:
            return ""
        return f"{parsed_date.isoformat()}T00:00:00Z"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_restock_session_draft_decision(row: dict[str, object]) -> dict[str, str]:
    normalized = {column: _normalize_text(row.get(column, "")) for column in o_contract_columns(DRAFT_DECISION_CONTRACT)}
    normalized["event_utc"] = normalized["event_utc"] or _utc_now_iso()
    normalized["draft_id"] = normalized["draft_id"] or f"o-session-draft-{uuid.uuid4().hex[:12]}"
    normalized["session_id"] = normalized["session_id"] or SESSION_ID
    normalized["decision_code"] = _normalize_decision_code(normalized.get("decision_code", ""))
    normalized["draft_order_qty"] = _positive_int_text(normalized.get("draft_order_qty", ""))
    normalized["snooze_until_utc"] = _normalize_snooze_until(normalized.get("snooze_until_utc", ""))
    normalized["actor"] = normalized["actor"] or "operator_ui"
    normalized["event_source_reference"] = normalized["event_source_reference"] or "o_ui_restock_session"
    normalized["draft_status"] = DRAFT_STATUS
    normalized["creates_live_action"] = "0"
    return normalized


def validate_restock_session_draft_decision(row: dict[str, object]) -> list[str]:
    normalized = normalize_restock_session_draft_decision(row)
    errors: list[str] = []
    raw_creates_live_action = _normalize_text(row.get("creates_live_action", "0")) or "0"
    raw_draft_status = _normalize_text(row.get("draft_status", DRAFT_STATUS)) or DRAFT_STATUS
    if normalized["session_id"] != SESSION_ID:
        errors.append("session_id_not_supported")
    if normalized["row_id"] == "":
        errors.append("missing_row_id")
    if normalized["seller_sku"] == "" and normalized["asin"] == "":
        errors.append("missing_sku_or_asin")
    if normalized["source_class"] not in SOURCE_CLASSES:
        errors.append("unsupported_source_class")
    if normalized["decision_code"] not in ALLOWED_DRAFT_DECISION_CODES:
        errors.append("unsupported_decision_code")
    if normalized["decision_code"] == "order_qty_draft" and normalized["draft_order_qty"] == "":
        errors.append("order_qty_draft_requires_positive_whole_quantity")
    if normalized["decision_code"] != "order_qty_draft" and _normalize_text(row.get("draft_order_qty", "")) != "":
        errors.append("quantity_only_allowed_for_order_qty_draft")
    if normalized["decision_code"] == "snooze" and normalized["snooze_until_utc"] == "":
        errors.append("snooze_requires_valid_date")
    if normalized["decision_code"] != "snooze" and _normalize_text(row.get("snooze_until_utc", "")) != "":
        errors.append("snooze_date_only_allowed_for_snooze")
    if raw_draft_status != DRAFT_STATUS:
        errors.append("draft_status_must_be_draft")
    if raw_creates_live_action != "0":
        errors.append("creates_live_action_must_be_zero")
    return errors


def build_restock_session_draft_row(
    *,
    session_row: dict[str, object],
    decision_code: object,
    draft_order_qty: object = "",
    snooze_until_utc: object = "",
    decision_note: object = "",
    actor: str = "operator_ui",
    event_source_reference: str = "o_ui_restock_session",
) -> dict[str, str]:
    source = {key: _normalize_text(value) for key, value in dict(session_row).items()}
    row = {
        "event_utc": _utc_now_iso(),
        "draft_id": f"o-session-draft-{uuid.uuid4().hex[:12]}",
        "session_id": source.get("session_id", "") or SESSION_ID,
        "row_id": source.get("row_id", ""),
        "seller_sku": source.get("seller_sku", ""),
        "asin": source.get("asin", ""),
        "supplier_name": source.get("supplier_name", ""),
        "supplier_code": source.get("supplier_code", ""),
        "source_class": source.get("source_class", ""),
        "row_source_reference": source.get("source_reference", ""),
        "decision_code": decision_code,
        "draft_order_qty": draft_order_qty,
        "snooze_until_utc": snooze_until_utc,
        "decision_note": decision_note,
        "actor": actor,
        "event_source_reference": event_source_reference,
        "draft_status": DRAFT_STATUS,
        "creates_live_action": "0",
        "title": source.get("title", ""),
        "supplier_sku": source.get("supplier_sku", ""),
        "barcode": source.get("barcode", ""),
        "current_supplier_cost_gbp": source.get("current_supplier_cost_gbp", ""),
        "current_amazon_price_gbp": source.get("current_amazon_price_gbp", ""),
    }
    normalized = normalize_restock_session_draft_decision(row)
    errors = validate_restock_session_draft_decision(normalized)
    if errors:
        raise ValueError(";".join(errors))
    return normalized


def submit_restock_session_draft_decision(
    *,
    root: Path | None = None,
    session_row: dict[str, object],
    decision_code: object,
    draft_order_qty: object = "",
    snooze_until_utc: object = "",
    decision_note: object = "",
    actor: str = "operator_ui",
    event_source_reference: str = "o_ui_restock_session",
) -> dict[str, str]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    row = build_restock_session_draft_row(
        session_row=session_row,
        decision_code=decision_code,
        draft_order_qty=draft_order_qty,
        snooze_until_utc=snooze_until_utc,
        decision_note=decision_note,
        actor=actor,
        event_source_reference=event_source_reference,
    )
    return append_o_contract_row(root_path, DRAFT_DECISION_CONTRACT, row)


def latest_restock_session_draft_decisions(events_df: pd.DataFrame) -> pd.DataFrame:
    if events_df.empty:
        return pd.DataFrame(columns=o_contract_columns(DRAFT_DECISION_CONTRACT))
    work = events_df.copy()
    for column in o_contract_columns(DRAFT_DECISION_CONTRACT):
        if column not in work.columns:
            work[column] = ""
        work[column] = work[column].map(_normalize_text)
    work = work[
        (work["creates_live_action"] == "0")
        & (work["draft_status"] == DRAFT_STATUS)
        & (work["decision_code"].isin(ALLOWED_DRAFT_DECISION_CODES))
        & (work["row_id"].map(_normalize_text) != "")
    ].copy()
    if work.empty:
        return work.drop(columns=["_event_sort"], errors="ignore")
    work["_event_sort"] = pd.to_datetime(work["event_utc"], errors="coerce", utc=True)
    work = work.sort_values(by=["_event_sort", "draft_id"], ascending=[False, False], kind="stable")
    work = work.drop_duplicates(subset=["row_id"], keep="first")
    return work.drop(columns=["_event_sort"], errors="ignore").reset_index(drop=True)


def ensure_restock_session_draft_decision_file(root: Path | None = None) -> Path:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    contract_path = root_path / "out" / "systems" / "O" / "live" / "restock_session_draft_decision_events.csv"
    if not contract_path.exists():
        write_o_contract_df(root_path, DRAFT_DECISION_CONTRACT, pd.DataFrame(columns=o_contract_columns(DRAFT_DECISION_CONTRACT)))
    return contract_path


def main() -> int:
    root_path = get_o_path_contract().root
    ensure_restock_session_draft_decision_file(root_path)
    events_df = read_o_contract_df(root_path, DRAFT_DECISION_CONTRACT)
    invalid = 0
    for _, row in events_df.iterrows():
        if validate_restock_session_draft_decision(row.to_dict()):
            invalid += 1
    print(f"draft_decision_rows={len(events_df.index)}")
    print(f"invalid_rows={invalid}")
    return 0 if invalid == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
