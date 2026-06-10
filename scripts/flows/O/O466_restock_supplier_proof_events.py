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

from scripts.flows.O.O460_build_restock_session_view import SESSION_ID, SOURCE_CLASSES
from scripts.flows.O._contract_io import append_o_contract_row, o_contract_columns, read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract


SUPPLIER_PROOF_CONTRACT = "restock_session_supplier_proof_events"
PROOF_STATUS = "draft_proof"
ALLOWED_SUPPLIER_STOCK_STATES = {
    "supplier_stock_verified_in_stock",
    "supplier_stock_verified_zero",
    "supplier_stock_not_verified",
}
ALLOWED_BACKORDER_STATES = {
    "backorder_none_confirmed",
    "backorder_wait",
    "backorder_not_verified",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_token(value: object) -> str:
    return "_".join(_normalize_text(value).lower().replace("-", "_").split())


def _normalize_supplier_stock_state(value: object) -> str:
    token = _normalize_token(value)
    aliases = {
        "in_stock": "supplier_stock_verified_in_stock",
        "stock_verified": "supplier_stock_verified_in_stock",
        "verified_in_stock": "supplier_stock_verified_in_stock",
        "out_of_stock": "supplier_stock_verified_zero",
        "zero": "supplier_stock_verified_zero",
        "verified_zero": "supplier_stock_verified_zero",
        "not_verified": "supplier_stock_not_verified",
        "unknown": "supplier_stock_not_verified",
    }
    token = aliases.get(token, token)
    return token if token in ALLOWED_SUPPLIER_STOCK_STATES else ""


def _normalize_backorder_state(value: object) -> str:
    token = _normalize_token(value)
    aliases = {
        "none": "backorder_none_confirmed",
        "no_backorder": "backorder_none_confirmed",
        "none_confirmed": "backorder_none_confirmed",
        "wait": "backorder_wait",
        "on_backorder": "backorder_wait",
        "not_verified": "backorder_not_verified",
        "unknown": "backorder_not_verified",
    }
    token = aliases.get(token, token)
    return token if token in ALLOWED_BACKORDER_STATES else ""


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


def _normalize_utc(value: object) -> str:
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


def normalize_restock_session_supplier_proof_event(row: dict[str, object]) -> dict[str, str]:
    normalized = {column: _normalize_text(row.get(column, "")) for column in o_contract_columns(SUPPLIER_PROOF_CONTRACT)}
    normalized["event_utc"] = _normalize_utc(normalized["event_utc"]) or _utc_now_iso()
    normalized["proof_id"] = normalized["proof_id"] or f"o-session-supplier-proof-{uuid.uuid4().hex[:12]}"
    normalized["session_id"] = normalized["session_id"] or SESSION_ID
    normalized["supplier_stock_state"] = _normalize_supplier_stock_state(normalized["supplier_stock_state"])
    normalized["supplier_stock_qty"] = _nonnegative_int_text(normalized["supplier_stock_qty"])
    normalized["backorder_state"] = _normalize_backorder_state(normalized["backorder_state"])
    normalized["backorder_eta_utc"] = _normalize_utc(normalized["backorder_eta_utc"])
    normalized["supplier_file_asof_utc"] = _normalize_utc(normalized["supplier_file_asof_utc"])
    normalized["actor"] = normalized["actor"] or "operator_ui"
    normalized["event_source_reference"] = normalized["event_source_reference"] or "o_ui_restock_supplier_proof"
    normalized["proof_status"] = PROOF_STATUS
    normalized["creates_live_action"] = "0"
    return normalized


def validate_restock_session_supplier_proof_event(row: dict[str, object]) -> list[str]:
    normalized = normalize_restock_session_supplier_proof_event(row)
    errors: list[str] = []
    raw_creates_live_action = _normalize_text(row.get("creates_live_action", "0")) or "0"
    raw_proof_status = _normalize_text(row.get("proof_status", PROOF_STATUS)) or PROOF_STATUS
    raw_stock_state = _normalize_text(row.get("supplier_stock_state", ""))
    raw_stock_qty = _normalize_text(row.get("supplier_stock_qty", ""))
    raw_backorder_state = _normalize_text(row.get("backorder_state", ""))
    raw_backorder_eta = _normalize_text(row.get("backorder_eta_utc", ""))
    raw_supplier_file_asof = _normalize_text(row.get("supplier_file_asof_utc", ""))
    if normalized["session_id"] != SESSION_ID:
        errors.append("session_id_not_supported")
    if normalized["row_id"] == "":
        errors.append("missing_row_id")
    if normalized["seller_sku"] == "" and normalized["asin"] == "":
        errors.append("missing_sku_or_asin")
    if normalized["source_class"] not in SOURCE_CLASSES:
        errors.append("unsupported_source_class")
    if raw_stock_state and normalized["supplier_stock_state"] == "":
        errors.append("unsupported_supplier_stock_state")
    if normalized["supplier_stock_state"] not in ALLOWED_SUPPLIER_STOCK_STATES:
        errors.append("missing_supplier_stock_state")
    if raw_stock_qty and normalized["supplier_stock_qty"] == "":
        errors.append("invalid_supplier_stock_qty")
    if normalized["supplier_stock_state"] == "supplier_stock_not_verified" and normalized["supplier_stock_qty"] != "":
        errors.append("stock_qty_not_allowed_when_stock_not_verified")
    if normalized["supplier_stock_state"] == "supplier_stock_verified_zero" and normalized["supplier_stock_qty"] not in {"", "0"}:
        errors.append("verified_zero_stock_qty_must_be_zero")
    if normalized["supplier_stock_state"] == "supplier_stock_verified_in_stock" and normalized["supplier_stock_qty"] == "0":
        errors.append("verified_in_stock_qty_cannot_be_zero")
    if raw_backorder_state and normalized["backorder_state"] == "":
        errors.append("unsupported_backorder_state")
    if normalized["backorder_state"] not in ALLOWED_BACKORDER_STATES:
        errors.append("missing_backorder_state")
    if raw_backorder_eta and normalized["backorder_eta_utc"] == "":
        errors.append("invalid_backorder_eta")
    if normalized["backorder_state"] != "backorder_wait" and normalized["backorder_eta_utc"] != "":
        errors.append("backorder_eta_only_allowed_for_backorder_wait")
    if raw_supplier_file_asof and normalized["supplier_file_asof_utc"] == "":
        errors.append("invalid_supplier_file_asof")
    if raw_proof_status != PROOF_STATUS:
        errors.append("proof_status_must_be_draft_proof")
    if raw_creates_live_action != "0":
        errors.append("creates_live_action_must_be_zero")
    return errors


def build_restock_session_supplier_proof_row(
    *,
    session_row: dict[str, object],
    supplier_stock_state: object,
    supplier_stock_qty: object = "",
    backorder_state: object,
    backorder_eta_utc: object = "",
    supplier_file_asof_utc: object = "",
    supplier_file_reference: object = "",
    proof_note: object = "",
    actor: str = "operator_ui",
    event_source_reference: str = "o_ui_restock_supplier_proof",
) -> dict[str, str]:
    source = {key: _normalize_text(value) for key, value in dict(session_row).items()}
    row = {
        "event_utc": _utc_now_iso(),
        "proof_id": f"o-session-supplier-proof-{uuid.uuid4().hex[:12]}",
        "session_id": source.get("session_id", "") or SESSION_ID,
        "row_id": source.get("row_id", ""),
        "seller_sku": source.get("seller_sku", ""),
        "asin": source.get("asin", ""),
        "supplier_name": source.get("supplier_name", ""),
        "supplier_code": source.get("supplier_code", ""),
        "source_class": source.get("source_class", ""),
        "row_source_reference": source.get("row_source_reference", "") or source.get("source_reference", ""),
        "supplier_stock_state": supplier_stock_state,
        "supplier_stock_qty": supplier_stock_qty,
        "backorder_state": backorder_state,
        "backorder_eta_utc": backorder_eta_utc,
        "supplier_file_asof_utc": supplier_file_asof_utc,
        "supplier_file_reference": supplier_file_reference,
        "proof_note": proof_note,
        "actor": actor,
        "event_source_reference": event_source_reference,
        "proof_status": PROOF_STATUS,
        "creates_live_action": "0",
        "title": source.get("title", ""),
        "supplier_sku": source.get("supplier_sku", ""),
        "barcode": source.get("barcode", ""),
    }
    normalized = normalize_restock_session_supplier_proof_event(row)
    errors = validate_restock_session_supplier_proof_event(normalized)
    if errors:
        raise ValueError(";".join(errors))
    return normalized


def submit_restock_session_supplier_proof_event(
    *,
    root: Path | None = None,
    session_row: dict[str, object],
    supplier_stock_state: object,
    supplier_stock_qty: object = "",
    backorder_state: object,
    backorder_eta_utc: object = "",
    supplier_file_asof_utc: object = "",
    supplier_file_reference: object = "",
    proof_note: object = "",
    actor: str = "operator_ui",
    event_source_reference: str = "o_ui_restock_supplier_proof",
) -> dict[str, str]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    row = build_restock_session_supplier_proof_row(
        session_row=session_row,
        supplier_stock_state=supplier_stock_state,
        supplier_stock_qty=supplier_stock_qty,
        backorder_state=backorder_state,
        backorder_eta_utc=backorder_eta_utc,
        supplier_file_asof_utc=supplier_file_asof_utc,
        supplier_file_reference=supplier_file_reference,
        proof_note=proof_note,
        actor=actor,
        event_source_reference=event_source_reference,
    )
    return append_o_contract_row(root_path, SUPPLIER_PROOF_CONTRACT, row)


def latest_restock_session_supplier_proof_events(events_df: pd.DataFrame) -> pd.DataFrame:
    if events_df.empty:
        return pd.DataFrame(columns=o_contract_columns(SUPPLIER_PROOF_CONTRACT))
    work = events_df.copy()
    for column in o_contract_columns(SUPPLIER_PROOF_CONTRACT):
        if column not in work.columns:
            work[column] = ""
        work[column] = work[column].map(_normalize_text)
    good_mask = []
    for _, row in work.iterrows():
        good_mask.append(validate_restock_session_supplier_proof_event(row.to_dict()) == [])
    work = work[pd.Series(good_mask, index=work.index)].copy()
    if work.empty:
        return work.drop(columns=["_event_sort"], errors="ignore")
    work["_event_sort"] = pd.to_datetime(work["event_utc"], errors="coerce", utc=True)
    work = work.sort_values(by=["_event_sort", "proof_id"], ascending=[False, False], kind="stable")
    work = work.drop_duplicates(subset=["row_id"], keep="first")
    return work.drop(columns=["_event_sort"], errors="ignore").reset_index(drop=True)


def ensure_restock_session_supplier_proof_event_file(root: Path | None = None) -> Path:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    contract_path = root_path / "out" / "systems" / "O" / "live" / "restock_session_supplier_proof_events.csv"
    if not contract_path.exists():
        write_o_contract_df(root_path, SUPPLIER_PROOF_CONTRACT, pd.DataFrame(columns=o_contract_columns(SUPPLIER_PROOF_CONTRACT)))
    return contract_path


def main() -> int:
    root_path = get_o_path_contract().root
    ensure_restock_session_supplier_proof_event_file(root_path)
    events_df = read_o_contract_df(root_path, SUPPLIER_PROOF_CONTRACT)
    invalid = 0
    for _, row in events_df.iterrows():
        if validate_restock_session_supplier_proof_event(row.to_dict()):
            invalid += 1
    print(f"supplier_proof_event_rows={len(events_df.index)}")
    print(f"invalid_rows={invalid}")
    return 0 if invalid == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
