from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.flows.O._contract_io import empty_o_contract_df, read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract
from scripts.flows.O._schemas import get_o_output_contract


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


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    return df


def _empty_contract_df(contract_name: str) -> pd.DataFrame:
    return empty_o_contract_df(contract_name)


def _read_or_init_csv(root_path: Path, contract_name: str) -> pd.DataFrame:
    return read_o_contract_df(root_path, contract_name)


def _line_identity(po_id: str, po_line_id: str, seller_sku: str) -> str:
    if po_line_id != "":
        return f"line:{_normalize_key(po_line_id)}"
    if po_id != "" and seller_sku != "":
        return f"po_sku:{_normalize_key(po_id)}::{_normalize_key(seller_sku)}"
    return ""


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
            key = f"{po_key}::{sku_key}"
            by_po_sku.setdefault(key, []).append(line)
    return by_line_id, by_po_sku


def apply_receiving_events(root: Path | None = None, *, applied_utc: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    applied_iso = _normalize_text(applied_utc) or _utc_now_iso()

    inbox_path = root_path / get_o_output_contract("receiving_events_inbox").rel_path
    live_log_path = root_path / get_o_output_contract("receiving_events").rel_path
    holds_path = root_path / get_o_output_contract("receiving_event_holds").rel_path
    lines_path = root_path / get_o_output_contract("purchase_order_lines_live").rel_path

    inbox_df = _read_or_init_csv(root_path, "receiving_events_inbox")
    live_df = _read_or_init_csv(root_path, "receiving_events")
    lines_df = _read_or_init_csv(root_path, "purchase_order_lines_live")
    holds_df = _empty_contract_df("receiving_event_holds")

    # Ensure operator intake file exists with schema.
    if not inbox_path.exists():
        write_o_contract_df(root_path, "receiving_events_inbox", inbox_df)

    if inbox_df.empty or lines_df.empty:
        write_o_contract_df(root_path, "receiving_events", live_df)
        write_o_contract_df(root_path, "receiving_event_holds", holds_df)
        print(
            {
                "status": "success",
                "events_seen": int(len(inbox_df)),
                "events_applied": 0,
                "holds": 0,
                "notes": "no inbox events or no purchase order lines",
            }
        )
        return _empty_contract_df("receiving_events"), live_df, holds_df

    line_by_id, lines_by_po_sku = _build_line_maps(lines_df)
    existing_event_ids = {
        _normalize_text(v)
        for v in live_df.get("event_id", pd.Series(dtype=str)).astype(str).tolist()
        if _normalize_text(v) != ""
    }
    seen_event_ids: set[str] = set()

    received_by_identity: dict[str, float] = {}
    for _, row in live_df.iterrows():
        identity = _line_identity(
            _normalize_text(row.get("po_id", "")),
            _normalize_text(row.get("po_line_id", "")),
            _normalize_text(row.get("seller_sku", "")),
        )
        if identity == "":
            continue
        received_by_identity[identity] = received_by_identity.get(identity, 0.0) + (_num(row.get("received_qty", "")) or 0.0)

    append_rows: list[dict[str, str]] = []
    hold_rows: list[dict[str, str]] = []

    inbox_work = inbox_df.copy()
    inbox_work["_event_ts"] = pd.to_datetime(inbox_work.get("event_utc", ""), errors="coerce", utc=True)
    inbox_work = inbox_work.sort_values(by=["_event_ts", "event_id"], kind="stable")

    for _, event in inbox_work.iterrows():
        event_id = _normalize_text(event.get("event_id", ""))
        po_id = _normalize_text(event.get("po_id", ""))
        po_line_id = _normalize_text(event.get("po_line_id", ""))
        seller_sku = _normalize_text(event.get("seller_sku", ""))
        qty = _num(event.get("received_qty", ""))
        warehouse_ref = _normalize_text(event.get("warehouse_ref", ""))
        event_source = _normalize_text(event.get("event_source", ""))
        event_utc = _normalize_text(event.get("event_utc", "")) or applied_iso
        note = _normalize_text(event.get("note", ""))
        actor = _normalize_text(event.get("actor", ""))

        def hold(reason: str, note_text: str) -> None:
            hold_rows.append(
                {
                    "hold_utc": applied_iso,
                    "event_utc": event_utc,
                    "event_id": event_id,
                    "po_id": po_id,
                    "po_line_id": po_line_id,
                    "seller_sku": seller_sku,
                    "received_qty": _normalize_text(event.get("received_qty", "")),
                    "hold_reason": reason,
                    "hold_note": note_text,
                    "warehouse_ref": warehouse_ref,
                    "event_source": event_source,
                    "actor": actor,
                    "note": note,
                }
            )

        if event_id == "":
            hold("missing_event_id", "event_id is required")
            continue

        if event_id in existing_event_ids or event_id in seen_event_ids:
            hold("duplicate_event_id", "event_id already exists in live receiving log or current apply batch")
            continue

        if qty is None or qty <= 0:
            hold("invalid_received_qty", "received_qty must be numeric and > 0")
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

        if matched_line is None:
            hold("missing_po_line", "no matching po line")
            continue

        ordered_qty = _num(matched_line.get("ordered_qty", "")) or 0.0
        if ordered_qty <= 0:
            hold("invalid_ordered_qty", "matched po line has non-positive ordered_qty")
            continue

        identity = _line_identity(
            _normalize_text(matched_line.get("po_id", "")),
            _normalize_text(matched_line.get("po_line_id", "")),
            _normalize_text(matched_line.get("seller_sku", "")),
        )
        already_received = received_by_identity.get(identity, 0.0)
        if already_received + float(qty) > ordered_qty:
            hold("over_receipt", "received_qty exceeds remaining open quantity for po line")
            continue

        seen_event_ids.add(event_id)
        received_by_identity[identity] = already_received + float(qty)
        append_rows.append(
            {
                "event_utc": event_utc,
                "event_id": event_id,
                "po_id": _normalize_text(matched_line.get("po_id", "")),
                "po_line_id": _normalize_text(matched_line.get("po_line_id", "")),
                "seller_sku": _normalize_text(matched_line.get("seller_sku", "")),
                "asin": _normalize_text(matched_line.get("asin", "")),
                "received_qty": _num_text(qty),
                "warehouse_ref": warehouse_ref,
                "event_source": event_source,
                "note": note,
                "actor": actor,
            }
        )

    append_df = pd.DataFrame(append_rows)
    if append_df.empty:
        updated_live_df = live_df.copy()
    else:
        append_df = _ensure_columns(
            append_df,
            [*get_o_output_contract("receiving_events").required_columns, *get_o_output_contract("receiving_events").optional_columns],
        )
        updated_live_df = pd.concat([live_df, append_df], ignore_index=True)

    ordered_live_cols = [*get_o_output_contract("receiving_events").required_columns, *get_o_output_contract("receiving_events").optional_columns]
    updated_live_df = _ensure_columns(updated_live_df, ordered_live_cols)[ordered_live_cols + [c for c in updated_live_df.columns if c not in ordered_live_cols]]

    holds_df = pd.DataFrame(hold_rows)
    hold_cols = [*get_o_output_contract("receiving_event_holds").required_columns, *get_o_output_contract("receiving_event_holds").optional_columns]
    holds_df = _ensure_columns(holds_df, hold_cols)[hold_cols + [c for c in holds_df.columns if c not in hold_cols]]

    write_o_contract_df(root_path, "receiving_events", updated_live_df)
    write_o_contract_df(root_path, "receiving_event_holds", holds_df)

    print(
        {
            "status": "success",
            "events_seen": int(len(inbox_df)),
            "events_applied": int(len(append_df)),
            "live_receiving_rows": int(len(updated_live_df)),
            "holds": int(len(holds_df)),
            "receiving_events": str(live_log_path),
            "receiving_event_holds": str(holds_path),
        }
    )
    return append_df, updated_live_df, holds_df


def main() -> None:
    apply_receiving_events()


if __name__ == "__main__":
    main()
