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


def build_ordered_stock_state(root: Path | None = None, *, asof_utc: str | None = None) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    asof = _normalize_text(asof_utc) or _utc_now_iso()

    po_headers_path = root_path / get_o_output_contract("purchase_orders_live").rel_path
    po_lines_path = root_path / get_o_output_contract("purchase_order_lines_live").rel_path
    receiving_events_path = root_path / get_o_output_contract("receiving_events").rel_path
    out_path = root_path / get_o_output_contract("ordered_stock_state").rel_path

    headers_df = _read_or_init_csv(root_path, "purchase_orders_live")
    lines_df = _read_or_init_csv(root_path, "purchase_order_lines_live")
    receiving_df = _read_or_init_csv(root_path, "receiving_events")

    contract = get_o_output_contract("ordered_stock_state")
    ordered_cols = [*contract.required_columns, *contract.optional_columns]

    if lines_df.empty:
        out_df = pd.DataFrame(columns=ordered_cols)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        write_o_contract_df(root_path, "ordered_stock_state", out_df)
        print({"status": "success", "rows": 0, "snapshot": str(out_path), "notes": "purchase_order_lines_live empty"})
        return out_df

    header_map: dict[str, tuple[str, str]] = {}
    for _, header in headers_df.iterrows():
        po_id = _normalize_text(header.get("po_id", ""))
        if po_id == "":
            continue
        header_map[po_id] = (
            _normalize_text(header.get("supplier_code", "")),
            _normalize_text(header.get("supplier_name", "")),
        )

    received_by_line: dict[str, float] = {}
    for _, ev in receiving_df.iterrows():
        line_key = _normalize_key(ev.get("po_line_id", ""))
        if line_key == "":
            continue
        received_by_line[line_key] = received_by_line.get(line_key, 0.0) + (_num(ev.get("received_qty", "")) or 0.0)

    rows: list[dict[str, str]] = []
    total_po_lines = 0
    fully_received_lines = 0
    for _, line in lines_df.iterrows():
        total_po_lines += 1
        po_id = _normalize_text(line.get("po_id", ""))
        po_line_id = _normalize_text(line.get("po_line_id", ""))
        seller_sku = _normalize_text(line.get("seller_sku", ""))
        asin = _normalize_text(line.get("asin", ""))

        ordered_qty = _num(line.get("ordered_qty", "")) or 0.0
        if ordered_qty < 0:
            ordered_qty = 0.0

        received_qty = received_by_line.get(_normalize_key(po_line_id), 0.0)
        if received_qty < 0:
            received_qty = 0.0
        if received_qty > ordered_qty:
            received_qty = ordered_qty

        remaining_open_qty = max(0.0, ordered_qty - received_qty)
        if remaining_open_qty <= 0:
            fully_received_lines += 1
            continue

        if received_qty <= 0:
            receipt_status = "not_received"
        else:
            receipt_status = "partial_received"

        supplier_code, supplier_name = header_map.get(
            po_id,
            (
                _normalize_text(line.get("supplier_code", "")),
                _normalize_text(line.get("supplier_name", "")),
            ),
        )

        rows.append(
            {
                "po_id": po_id,
                "po_line_id": po_line_id,
                "seller_sku": seller_sku,
                "asin": asin,
                "supplier_code": supplier_code,
                "supplier_name": supplier_name,
                "ordered_qty": _num_text(ordered_qty),
                "received_qty": _num_text(received_qty),
                "remaining_open_qty": _num_text(remaining_open_qty),
                "receipt_status": receipt_status,
                "expected_arrival_utc": _normalize_text(line.get("expected_arrival_utc", "")),
                "backorder_flag": _normalize_text(line.get("backorder_flag", "")),
                "cost_mode": _normalize_text(line.get("cost_mode", "")),
                "recommendation_basis": _normalize_text(line.get("recommendation_basis", "")),
                "source_event_id": _normalize_text(line.get("source_event_id", "")),
                "asof_utc": asof,
            }
        )

    out_df = pd.DataFrame(rows)
    out_df = _ensure_columns(out_df, ordered_cols)[ordered_cols + [c for c in out_df.columns if c not in ordered_cols]]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_o_contract_df(root_path, "ordered_stock_state", out_df)

    print(
        {
            "status": "success",
            "rows": int(len(out_df)),
            "open_lines": int(len(out_df)),
            "fully_received_lines_excluded": int(fully_received_lines),
            "source_po_lines": int(total_po_lines),
            "snapshot": str(out_path),
        }
    )
    return out_df


def main() -> None:
    build_ordered_stock_state()


if __name__ == "__main__":
    main()
