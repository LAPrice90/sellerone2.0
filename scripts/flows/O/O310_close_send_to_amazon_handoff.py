from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.flows.O.O300_build_send_to_amazon_queue import build_send_to_amazon_queue
from scripts.flows.O._contract_io import empty_o_contract_df, read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract
from scripts.flows.O._schemas import get_o_output_contract


ALLOWED_HANDOFF_STATUSES = {"handoff_closed", "queued_for_shipment", "ready_for_shipment"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    return df


def _empty_contract_df(contract_name: str) -> pd.DataFrame:
    return empty_o_contract_df(contract_name)


def _read_or_init_csv(root_path: Path, contract_name: str) -> pd.DataFrame:
    return read_o_contract_df(root_path, contract_name)


def _build_line_maps(lines_df: pd.DataFrame) -> tuple[dict[str, pd.Series], dict[str, list[pd.Series]]]:
    by_line_id: dict[str, pd.Series] = {}
    by_po_sku: dict[str, list[pd.Series]] = {}
    for _, line in lines_df.iterrows():
        line_id = _normalize_key(line.get("po_line_id", ""))
        po_key = _normalize_key(line.get("po_id", ""))
        sku_key = _normalize_key(line.get("seller_sku", ""))
        if line_id != "" and line_id not in by_line_id:
            by_line_id[line_id] = line
        if po_key != "" and sku_key != "":
            by_po_sku.setdefault(f"{po_key}::{sku_key}", []).append(line)
    return by_line_id, by_po_sku


def close_send_to_amazon_handoff(root: Path | None = None, *, applied_utc: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    applied_ts = _normalize_text(applied_utc) or _utc_now_iso()

    inbox_path = root_path / get_o_output_contract("send_to_amazon_handoff_events").rel_path
    log_path = root_path / get_o_output_contract("send_to_amazon_handoff_log").rel_path
    holds_path = root_path / get_o_output_contract("send_to_amazon_handoff_holds").rel_path
    lines_path = root_path / get_o_output_contract("purchase_order_lines_live").rel_path
    receiving_path = root_path / get_o_output_contract("receiving_events").rel_path

    inbox_df = _read_or_init_csv(root_path, "send_to_amazon_handoff_events")
    log_df = _read_or_init_csv(root_path, "send_to_amazon_handoff_log")
    lines_df = _read_or_init_csv(root_path, "purchase_order_lines_live")
    receiving_df = _read_or_init_csv(root_path, "receiving_events")

    if not inbox_path.exists():
        write_o_contract_df(root_path, "send_to_amazon_handoff_events", inbox_df)

    if inbox_df.empty or lines_df.empty:
        write_o_contract_df(root_path, "send_to_amazon_handoff_log", log_df)
        holds_df = _empty_contract_df("send_to_amazon_handoff_holds")
        write_o_contract_df(root_path, "send_to_amazon_handoff_holds", holds_df)
        queue_df = build_send_to_amazon_queue(root=root_path, queue_utc=applied_ts)
        print(
            {
                "status": "success",
                "events_seen": int(len(inbox_df)),
                "events_applied": 0,
                "holds": 0,
                "queue_rows": int(len(queue_df)),
                "notes": "no handoff inbox events or no purchase order lines",
            }
        )
        return _empty_contract_df("send_to_amazon_handoff_log"), log_df, holds_df, queue_df

    line_by_id, lines_by_po_sku = _build_line_maps(lines_df)

    received_by_line: dict[str, float] = {}
    for _, ev in receiving_df.iterrows():
        line_id = _normalize_key(ev.get("po_line_id", ""))
        if line_id == "":
            continue
        received_by_line[line_id] = received_by_line.get(line_id, 0.0) + (_num(ev.get("received_qty", "")) or 0.0)

    existing_event_ids = {
        _normalize_text(v)
        for v in log_df.get("event_id", pd.Series(dtype=str)).astype(str).tolist()
        if _normalize_text(v) != ""
    }
    seen_event_ids: set[str] = set()

    handed_by_line: dict[str, float] = {}
    for _, ev in log_df.iterrows():
        line_id = _normalize_key(ev.get("po_line_id", ""))
        if line_id == "":
            continue
        handed_by_line[line_id] = handed_by_line.get(line_id, 0.0) + (_num(ev.get("handoff_qty", "")) or 0.0)

    append_rows: list[dict[str, str]] = []
    hold_rows: list[dict[str, str]] = []

    inbox_work = inbox_df.copy()
    inbox_work["_event_ts"] = pd.to_datetime(inbox_work.get("event_utc", ""), errors="coerce", utc=True)
    inbox_work = inbox_work.sort_values(by=["_event_ts", "event_id"], kind="stable")

    for _, event in inbox_work.iterrows():
        event_utc = _normalize_text(event.get("event_utc", "")) or applied_ts
        event_id = _normalize_text(event.get("event_id", ""))
        po_id = _normalize_text(event.get("po_id", ""))
        po_line_id = _normalize_text(event.get("po_line_id", ""))
        seller_sku = _normalize_text(event.get("seller_sku", ""))
        handoff_qty = _num(event.get("handoff_qty", ""))
        shipment_ref = _normalize_text(event.get("shipment_ref", ""))
        handoff_status = _normalize_text(event.get("handoff_status", "")).lower() or "handoff_closed"
        note = _normalize_text(event.get("note", ""))
        actor = _normalize_text(event.get("actor", ""))

        def hold(reason: str, hold_note: str) -> None:
            hold_rows.append(
                {
                    "hold_utc": applied_ts,
                    "event_utc": event_utc,
                    "event_id": event_id,
                    "po_id": po_id,
                    "po_line_id": po_line_id,
                    "seller_sku": seller_sku,
                    "handoff_qty": _normalize_text(event.get("handoff_qty", "")),
                    "hold_reason": reason,
                    "hold_note": hold_note,
                    "shipment_ref": shipment_ref,
                    "handoff_status": handoff_status,
                    "actor": actor,
                    "note": note,
                }
            )

        if event_id == "":
            hold("missing_event_id", "event_id is required")
            continue
        if event_id in existing_event_ids or event_id in seen_event_ids:
            hold("duplicate_event_id", "event_id already exists in handoff log or current apply batch")
            continue
        if handoff_qty is None or handoff_qty <= 0:
            hold("invalid_handoff_qty", "handoff_qty must be numeric and > 0")
            continue
        if handoff_status not in ALLOWED_HANDOFF_STATUSES:
            hold("invalid_handoff_status", "handoff_status is not supported")
            continue

        matched_line: pd.Series | None = None
        line_key = _normalize_key(po_line_id)
        if line_key != "":
            matched_line = line_by_id.get(line_key)
            if matched_line is None:
                hold("missing_po_line", "po_line_id not found in purchase_order_lines_live")
                continue
            if po_id != "" and _normalize_key(po_id) != _normalize_key(matched_line.get("po_id", "")):
                hold("po_id_mismatch", "po_id does not match po_line_id owner")
                continue
        else:
            po_key = _normalize_key(po_id)
            sku_key = _normalize_key(seller_sku)
            if po_key == "" or sku_key == "":
                hold("missing_po_line", "provide po_line_id or both po_id + seller_sku")
                continue
            candidates = lines_by_po_sku.get(f"{po_key}::{sku_key}", [])
            if len(candidates) == 0:
                hold("missing_po_line", "no po line matched by po_id + seller_sku")
                continue
            if len(candidates) > 1:
                hold("ambiguous_po_line_match", "multiple po lines matched po_id + seller_sku, provide po_line_id")
                continue
            matched_line = candidates[0]
            po_line_id = _normalize_text(matched_line.get("po_line_id", ""))
            po_id = _normalize_text(matched_line.get("po_id", ""))

        if matched_line is None:
            hold("missing_po_line", "no matching po line")
            continue

        ordered_qty = _num(matched_line.get("ordered_qty", "")) or 0.0
        if ordered_qty <= 0:
            hold("invalid_ordered_qty", "matched po line has non-positive ordered_qty")
            continue

        line_id_key = _normalize_key(matched_line.get("po_line_id", ""))
        total_received = received_by_line.get(line_id_key, 0.0)
        if total_received > ordered_qty:
            total_received = ordered_qty
        already_handed = handed_by_line.get(line_id_key, 0.0)
        if already_handed < 0:
            already_handed = 0.0
        if already_handed > total_received:
            already_handed = total_received

        available_before = total_received - already_handed
        if available_before <= 0:
            hold("no_available_received_qty", "no received qty available for handoff")
            continue
        if handoff_qty > available_before:
            hold("over_handoff_qty", "handoff_qty exceeds available received qty")
            continue

        available_after = available_before - handoff_qty
        seen_event_ids.add(event_id)
        handed_by_line[line_id_key] = already_handed + float(handoff_qty)
        append_rows.append(
            {
                "event_utc": event_utc,
                "event_id": event_id,
                "po_id": _normalize_text(matched_line.get("po_id", "")),
                "po_line_id": _normalize_text(matched_line.get("po_line_id", "")),
                "seller_sku": _normalize_text(matched_line.get("seller_sku", "")),
                "asin": _normalize_text(matched_line.get("asin", "")),
                "handoff_qty": _num_text(handoff_qty),
                "shipment_ref": shipment_ref,
                "handoff_status": handoff_status,
                "actor": actor,
                "cost_mode": _normalize_text(matched_line.get("cost_mode", "")),
                "recommendation_basis": _normalize_text(matched_line.get("recommendation_basis", "")),
                "source_event_id": _normalize_text(matched_line.get("source_event_id", "")),
                "note": note,
                "available_before_handoff": _num_text(available_before),
                "available_after_handoff": _num_text(available_after),
            }
        )

    append_df = pd.DataFrame(append_rows)
    if append_df.empty:
        updated_log_df = log_df.copy()
    else:
        log_cols = [*get_o_output_contract("send_to_amazon_handoff_log").required_columns, *get_o_output_contract("send_to_amazon_handoff_log").optional_columns]
        append_df = _ensure_columns(append_df, log_cols)
        updated_log_df = pd.concat([log_df, append_df], ignore_index=True)

    log_cols = [*get_o_output_contract("send_to_amazon_handoff_log").required_columns, *get_o_output_contract("send_to_amazon_handoff_log").optional_columns]
    updated_log_df = _ensure_columns(updated_log_df, log_cols)[log_cols + [c for c in updated_log_df.columns if c not in log_cols]]

    holds_df = pd.DataFrame(hold_rows)
    hold_cols = [*get_o_output_contract("send_to_amazon_handoff_holds").required_columns, *get_o_output_contract("send_to_amazon_handoff_holds").optional_columns]
    holds_df = _ensure_columns(holds_df, hold_cols)[hold_cols + [c for c in holds_df.columns if c not in hold_cols]]

    write_o_contract_df(root_path, "send_to_amazon_handoff_log", updated_log_df)
    write_o_contract_df(root_path, "send_to_amazon_handoff_holds", holds_df)

    queue_df = build_send_to_amazon_queue(root=root_path, queue_utc=applied_ts)

    print(
        {
            "status": "success",
            "events_seen": int(len(inbox_df)),
            "events_applied": int(len(append_df)),
            "live_handoff_rows": int(len(updated_log_df)),
            "holds": int(len(holds_df)),
            "queue_rows": int(len(queue_df)),
            "handoff_log": str(log_path),
            "handoff_holds": str(holds_path),
        }
    )
    return append_df, updated_log_df, holds_df, queue_df


def main() -> None:
    close_send_to_amazon_handoff()


if __name__ == "__main__":
    main()
