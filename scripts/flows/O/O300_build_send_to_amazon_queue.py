from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.flows.O._contract_io import empty_o_contract_df, read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract
from scripts.flows.O._schemas import get_o_output_contract


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


def build_send_to_amazon_queue(root: Path | None = None, *, queue_utc: str | None = None) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    queue_ts = _normalize_text(queue_utc) or _utc_now_iso()

    headers_path = root_path / get_o_output_contract("purchase_orders_live").rel_path
    lines_path = root_path / get_o_output_contract("purchase_order_lines_live").rel_path
    receiving_path = root_path / get_o_output_contract("receiving_events").rel_path
    handoff_log_path = root_path / get_o_output_contract("send_to_amazon_handoff_log").rel_path
    out_path = root_path / get_o_output_contract("send_to_amazon_queue").rel_path

    headers_df = _read_or_init_csv(root_path, "purchase_orders_live")
    lines_df = _read_or_init_csv(root_path, "purchase_order_lines_live")
    receiving_df = _read_or_init_csv(root_path, "receiving_events")
    handoff_df = _read_or_init_csv(root_path, "send_to_amazon_handoff_log")

    contract = get_o_output_contract("send_to_amazon_queue")
    ordered_cols = [*contract.required_columns, *contract.optional_columns]

    if lines_df.empty:
        out_df = pd.DataFrame(columns=ordered_cols)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        write_o_contract_df(root_path, "send_to_amazon_queue", out_df)
        print({"status": "success", "rows": 0, "snapshot": str(out_path), "notes": "purchase_order_lines_live empty"})
        return out_df

    header_map: dict[str, tuple[str, str]] = {}
    for _, h in headers_df.iterrows():
        po_id = _normalize_text(h.get("po_id", ""))
        if po_id == "":
            continue
        header_map[po_id] = (
            _normalize_text(h.get("supplier_code", "")),
            _normalize_text(h.get("supplier_name", "")),
        )

    received_by_line: dict[str, float] = {}
    for _, ev in receiving_df.iterrows():
        line_id = _normalize_key(ev.get("po_line_id", ""))
        if line_id == "":
            continue
        received_by_line[line_id] = received_by_line.get(line_id, 0.0) + (_num(ev.get("received_qty", "")) or 0.0)

    handed_by_line: dict[str, float] = {}
    latest_shipment_ref_by_line: dict[str, str] = {}
    if not handoff_df.empty:
        handoff_work = handoff_df.copy()
        handoff_work["_event_ts"] = pd.to_datetime(handoff_work.get("event_utc", ""), errors="coerce", utc=True)
        handoff_work = handoff_work.sort_values(by=["po_line_id", "_event_ts"], kind="stable")
        for _, ev in handoff_work.iterrows():
            line_id = _normalize_key(ev.get("po_line_id", ""))
            if line_id == "":
                continue
            handed_by_line[line_id] = handed_by_line.get(line_id, 0.0) + (_num(ev.get("handoff_qty", "")) or 0.0)
            ref = _normalize_text(ev.get("shipment_ref", ""))
            if ref != "":
                latest_shipment_ref_by_line[line_id] = ref

    rows: list[dict[str, str]] = []
    for _, line in lines_df.iterrows():
        po_id = _normalize_text(line.get("po_id", ""))
        po_line_id = _normalize_text(line.get("po_line_id", ""))
        line_key = _normalize_key(po_line_id)
        ordered_qty = _num(line.get("ordered_qty", "")) or 0.0
        if ordered_qty <= 0:
            continue

        total_received = received_by_line.get(line_key, 0.0)
        if total_received <= 0:
            # Not yet received, do not enter send queue.
            continue
        if total_received > ordered_qty:
            total_received = ordered_qty

        total_handed = handed_by_line.get(line_key, 0.0)
        if total_handed < 0:
            total_handed = 0.0
        if total_handed > total_received:
            total_handed = total_received

        available_for_send = total_received - total_handed
        if available_for_send <= 0:
            # Fully handed off already; do not duplicate on rebuild.
            continue

        supplier_code, supplier_name = header_map.get(
            po_id,
            (
                _normalize_text(line.get("supplier_code", "")),
                _normalize_text(line.get("supplier_name", "")),
            ),
        )
        send_status = "ready_to_handoff" if total_handed <= 0 else "partial_handoff_open"
        queue_note = "received_stock_ready" if total_handed <= 0 else "partial_handoff_remaining_qty"

        rows.append(
            {
                "queue_utc": queue_ts,
                "po_id": po_id,
                "po_line_id": po_line_id,
                "seller_sku": _normalize_text(line.get("seller_sku", "")),
                "asin": _normalize_text(line.get("asin", "")),
                "supplier_code": supplier_code,
                "supplier_name": supplier_name,
                "received_qty_available_for_send": _num_text(available_for_send),
                "send_status": send_status,
                "shipment_ref": latest_shipment_ref_by_line.get(line_key, ""),
                "cost_mode": _normalize_text(line.get("cost_mode", "")),
                "recommendation_basis": _normalize_text(line.get("recommendation_basis", "")),
                "source_event_id": _normalize_text(line.get("source_event_id", "")),
                "queue_note": queue_note,
                "total_received_qty": _num_text(total_received),
                "total_handed_off_qty": _num_text(total_handed),
            }
        )

    out_df = pd.DataFrame(rows)
    out_df = _ensure_columns(out_df, ordered_cols)[ordered_cols + [c for c in out_df.columns if c not in ordered_cols]]
    out_df = out_df.sort_values(by=["supplier_code", "supplier_name", "po_id", "po_line_id"], kind="stable")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_o_contract_df(root_path, "send_to_amazon_queue", out_df)
    print({"status": "success", "rows": int(len(out_df)), "snapshot": str(out_path)})
    return out_df


def main() -> None:
    build_send_to_amazon_queue()


if __name__ == "__main__":
    main()
