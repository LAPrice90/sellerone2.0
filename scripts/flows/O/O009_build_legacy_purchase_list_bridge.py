from __future__ import annotations

import argparse
import csv
import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

BOOT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT))

try:
    from scripts.flows.O._contract_io import write_o_contract_df
    from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract
except ModuleNotFoundError:
    from flows.O._contract_io import write_o_contract_df
    from flows.O._paths import ensure_o_directories, get_o_path_contract


DEFAULT_SHEET_ID = "1H_EDAYfB_xgGvnW1esOMwWsHs2wBXYoOABcMs7SWcrY"
DEFAULT_SHEET_TITLE = "Amazon Supplier Process"
DEFAULT_TAB = "Purchase List"
DEFAULT_SERVICE_ACCOUNT_PATH = Path("secrets") / "sellerone-2-0d3642b951a0.json"

SOURCE_SYSTEM = "legacy_purchase_list"
REQUIRED_PURCHASE_LIST_HEADERS = (
    "Supplier",
    "SKU",
    "ASIN",
    "Name",
    "Qtys",
    "Barcode",
    "Supply Code",
    "CPU",
    "Ordrd",
    "Stock",
    "ROI",
    "Vlcity",
    "Days",
    "Recomend",
    "Restk",
    "Ordered",
    "Price",
    "Done",
    "Text",
    "Resk Val",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_header(value: object) -> str:
    return " ".join(_normalize_text(value).lower().split())


def _num(value: object) -> float | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    lowered = raw.lower()
    if lowered in {"false", "true", "n/a", "na", "none", "-"}:
        return None
    cleaned = (
        raw.replace("£", "")
        .replace("$", "")
        .replace(",", "")
        .replace("%", "")
        .replace(" ", "")
    )
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1]}"
    try:
        return float(cleaned)
    except ValueError:
        return None


def _num_text(value: float | None) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


def _money_text(value: object) -> str:
    return _num_text(_num(value))


def _percent_text(value: object) -> str:
    return _num_text(_num(value))


def _bool_flag(value: object) -> bool:
    token = _normalize_text(value).lower()
    return token in {"1", "true", "yes", "y", "on", "checked"}


def _row_hash(values: Sequence[object]) -> str:
    raw = "|".join(_normalize_text(value) for value in values)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _find_header_index(rows: Sequence[Sequence[object]]) -> int:
    for index, row in enumerate(rows):
        normalized = {_normalize_header(value) for value in row}
        if {"supplier", "sku", "asin"}.issubset(normalized):
            return index
    raise ValueError("Purchase List header row not found")


def _record_from_row(headers: Sequence[str], row: Sequence[object]) -> dict[str, str]:
    out: dict[str, str] = {}
    for index, header in enumerate(headers):
        key = _normalize_text(header)
        if key == "":
            continue
        out[key] = _normalize_text(row[index] if index < len(row) else "")
    return out


def _map_recommendation(record: dict[str, str]) -> tuple[str, str, str, str, bool]:
    label = _normalize_text(record.get("Recomend", ""))
    token = label.lower()
    sheet_drop = _bool_flag(record.get("Drop", ""))
    if token == "restock":
        return "full_restock", "full_restock", "legacy_purchase_list_restock", "LEGACY_PURCHASE_LIST_RESTOCK", sheet_drop
    if token == "no data":
        return "test_restock", "test_restock", "legacy_purchase_list_no_data", "LEGACY_PURCHASE_LIST_NO_DATA", sheet_drop
    if token == "drop":
        return "wait", "wait", "legacy_purchase_list_drop", "LEGACY_PURCHASE_LIST_DROP", True
    if token == "wait":
        return "wait", "wait", "legacy_purchase_list_wait", "LEGACY_PURCHASE_LIST_WAIT", sheet_drop
    if token == "":
        return "wait", "wait", "legacy_purchase_list_blank_recommendation", "LEGACY_PURCHASE_LIST_BLANK_RECOMMENDATION", sheet_drop
    reason = "LEGACY_PURCHASE_LIST_UNMAPPED_RECOMMENDATION"
    return "wait", "wait", "legacy_purchase_list_unmapped_recommendation", reason, sheet_drop


def _backsolve_market_and_profit(cost_text: str, roi_text: str) -> tuple[str, str, str]:
    cost = _num(cost_text)
    roi = _num(roi_text)
    if cost is None or cost <= 0 or roi is None:
        return "", "", ""
    market = cost * (1.0 + (roi / 100.0))
    profit = market - cost
    return _num_text(market), _num_text(profit), "LEGACY_PURCHASE_LIST_ROI_BACKSOLVE"


def _health_row(
    check: str,
    status: str,
    value: object,
    notes: str,
    observed_utc: str,
    source_path: str,
) -> dict[str, str]:
    value_text = "" if value is None else str(value).strip()
    return {
        "check": check,
        "status": status,
        "value": value_text,
        "notes": notes,
        "observed_utc": observed_utc,
        "source_path": source_path,
    }


def get_gspread_client(root: Path | None = None, credentials_path: str | Path | None = None):
    try:
        import gspread
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError("gspread is required for --source google bridge imports") from exc

    root_path = Path(root) if root is not None else REPO_ROOT
    configured_path = credentials_path or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    service_account_path = Path(configured_path) if configured_path else root_path / DEFAULT_SERVICE_ACCOUNT_PATH
    if not service_account_path.is_absolute():
        service_account_path = root_path / service_account_path
    return gspread.service_account(filename=str(service_account_path))


def load_purchase_list_rows_from_google(
    *,
    root: Path | None = None,
    sheet_id: str = DEFAULT_SHEET_ID,
    tab: str = DEFAULT_TAB,
    credentials_path: str | Path | None = None,
) -> list[list[str]]:
    client = get_gspread_client(root=root, credentials_path=credentials_path)
    worksheet = client.open_by_key(sheet_id).worksheet(tab)
    values = worksheet.get_all_values()
    return [[_normalize_text(cell) for cell in row] for row in values]


def load_purchase_list_rows_from_csv(path: str | Path) -> list[list[str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return [[_normalize_text(cell) for cell in row] for row in csv.reader(handle)]


def build_legacy_purchase_list_bridge_from_rows(
    rows: Sequence[Sequence[object]],
    *,
    bridge_utc: str | None = None,
    sheet_id: str = DEFAULT_SHEET_ID,
    sheet_title: str = DEFAULT_SHEET_TITLE,
    tab: str = DEFAULT_TAB,
    source_path: str = "",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    observed_utc = bridge_utc or _utc_now_iso()
    source_path_text = source_path or f"google_sheet:{sheet_id}:{tab}"
    header_index = _find_header_index(rows)
    headers = [_normalize_text(value) for value in rows[header_index]]
    normalized_headers = {_normalize_header(value): value for value in headers if _normalize_text(value)}
    missing_headers = [
        header for header in REQUIRED_PURCHASE_LIST_HEADERS if _normalize_header(header) not in normalized_headers
    ]
    if missing_headers:
        health_df = pd.DataFrame(
            [
                _health_row(
                    "headers_present",
                    "fail",
                    "0",
                    f"missing headers: {', '.join(missing_headers)}",
                    observed_utc,
                    source_path_text,
                )
            ]
        )
        raise ValueError(f"Purchase List missing required headers: {', '.join(missing_headers)}")

    bridge_rows: list[dict[str, str]] = []
    data_rows_seen = 0
    blank_sku_rows = 0
    done_rows = 0
    restock_rows = 0
    no_data_rows = 0
    drop_rows = 0
    missing_cost_rows = 0
    missing_qty_rows = 0

    for absolute_index, raw_row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        record = _record_from_row(headers, raw_row)
        if not any(_normalize_text(value) for value in record.values()):
            continue
        data_rows_seen += 1

        seller_sku = _normalize_text(record.get("SKU", ""))
        if seller_sku == "":
            blank_sku_rows += 1
            continue
        if _bool_flag(record.get("Done", "")):
            done_rows += 1
            continue

        suggested_action, recommendation_status, basis, reason_code, drop_flag = _map_recommendation(record)
        sheet_recommend = _normalize_text(record.get("Recomend", ""))
        if sheet_recommend.lower() == "restock":
            restock_rows += 1
        if sheet_recommend.lower() == "no data":
            no_data_rows += 1
        if sheet_recommend.lower() == "drop" or drop_flag:
            drop_rows += 1

        cpu = _money_text(record.get("CPU", ""))
        roi = _percent_text(record.get("ROI", ""))
        restock_qty = _num_text(_num(record.get("Restk", "")))
        ordered_qty = _num_text(_num(record.get("Ordered", "")))
        confirmed_price = _money_text(record.get("Price", ""))
        reorder_value = _money_text(record.get("Resk Val", ""))
        market_price, forward_profit, market_basis = _backsolve_market_and_profit(cpu, roi)

        if cpu == "" and suggested_action in {"full_restock", "test_restock"}:
            missing_cost_rows += 1
        if restock_qty == "" and suggested_action in {"full_restock", "test_restock"}:
            missing_qty_rows += 1

        snooze_flag = _bool_flag(record.get("Snze", ""))
        notes = [reason_code, "NATIVE_O_PARITY_PENDING"]
        if drop_flag:
            notes.append("DROP_VISIBLE_NOT_BUYABLE_BY_DEFAULT")
        if basis == "legacy_purchase_list_no_data":
            notes.append("NO_DATA_TEST_CANDIDATE")

        source_reference = f"{SOURCE_SYSTEM}:{sheet_id}:{tab}:row{absolute_index}"
        bridge_rows.append(
            {
                "bridge_utc": observed_utc,
                "source_system": SOURCE_SYSTEM,
                "source_sheet_id": sheet_id,
                "source_sheet_title": sheet_title,
                "source_tab": tab,
                "source_row_number": str(absolute_index),
                "source_reference": source_reference,
                "supplier_name": _normalize_text(record.get("Supplier", "")),
                "supplier_code": "",
                "seller_sku": seller_sku,
                "asin": _normalize_text(record.get("ASIN", "")),
                "title": _normalize_text(record.get("Name", "")),
                "display_qtys_label": _normalize_text(record.get("Qtys", "")) or "Unit",
                "barcode": _normalize_text(record.get("Barcode", "")),
                "supplier_sku": _normalize_text(record.get("Supply Code", "")),
                "suggested_action": suggested_action,
                "recommendation_status": recommendation_status,
                "sheet_recommend_label": sheet_recommend,
                "suggested_qty": restock_qty,
                "recommended_qty_rounded": restock_qty,
                "current_supplier_buy_cost_gbp": cpu,
                "suggested_unit_cost_gbp": cpu,
                "suggested_market_price_gbp": market_price,
                "market_price_gbp": market_price,
                "expected_forward_roi_pct": roi,
                "forward_roi_pct": roi,
                "forward_profit_per_unit_gbp": forward_profit,
                "ordered_open": _num_text(_num(record.get("Ordrd", ""))),
                "available_now": _num_text(_num(record.get("Stock", ""))),
                "velocity_30d": _num_text(_num(record.get("Vlcity", ""))),
                "days_cover_available_only": _num_text(_num(record.get("Days", ""))),
                "order_qty": ordered_qty,
                "confirmed_price": confirmed_price,
                "done_flag": "0",
                "operator_text": _normalize_text(record.get("Text", "")),
                "reorder_value_gbp": reorder_value,
                "queue_status": "snoozed" if snooze_flag else "needs_review",
                "cost_mode": "legacy_sheet",
                "recommendation_basis": basis,
                "bridge_status": "ready",
                "bridge_note": "|".join(notes),
                "current_supplier_cost_source": "legacy_purchase_list_cpu",
                "market_price_basis_used": market_basis,
                "reason_codes": "|".join(notes),
                "order_qty_mode": "raw_units",
                "order_qty_unit_label": "Units",
                "sell_pack_qty": "1",
                "amazon_pack_size": "1",
                "supplier_case_qty": "1",
                "supplier_case_multiple": "0",
                "valid_order_step": "1",
                "repack_required": "0",
                "bundle_required": "0",
                "pack_conversion_note": "",
                "disc_flag": "1" if _bool_flag(record.get("Disc", "")) else "0",
                "drop_flag": "1" if drop_flag else "0",
                "snooze_flag": "1" if snooze_flag else "0",
                "source_row_hash": _row_hash(raw_row),
            }
        )

    bridge_df = pd.DataFrame(bridge_rows)
    health_rows = [
        _health_row("headers_present", "ok", "1", "all required Purchase List headers found", observed_utc, source_path_text),
        _health_row("data_rows_seen", "ok", data_rows_seen, "non-empty rows after the header row", observed_utc, source_path_text),
        _health_row("bridge_rows", "ok" if bridge_rows else "warn", len(bridge_rows), "rows exported locally after Done and blank SKU filtering", observed_utc, source_path_text),
        _health_row("excluded_done_rows", "ok", done_rows, "Done=TRUE rows excluded from bridge", observed_utc, source_path_text),
        _health_row("blank_sku_rows", "ok" if blank_sku_rows == 0 else "warn", blank_sku_rows, "non-empty rows with blank SKU excluded", observed_utc, source_path_text),
        _health_row("sheet_restock_rows", "ok", restock_rows, "exported rows where Recomend=Restock", observed_utc, source_path_text),
        _health_row("sheet_no_data_rows", "ok", no_data_rows, "exported rows where Recomend=No Data", observed_utc, source_path_text),
        _health_row("sheet_drop_rows", "ok", drop_rows, "exported rows marked as Drop or with Drop flag", observed_utc, source_path_text),
        _health_row("missing_cost_rows", "ok" if missing_cost_rows == 0 else "warn", missing_cost_rows, "buy rows missing CPU", observed_utc, source_path_text),
        _health_row("missing_suggested_qty_rows", "ok" if missing_qty_rows == 0 else "warn", missing_qty_rows, "buy rows missing Restk", observed_utc, source_path_text),
    ]
    health_df = pd.DataFrame(health_rows)
    return bridge_df, health_df


def _history_stamp(bridge_utc: str) -> str:
    return (
        bridge_utc.replace("-", "")
        .replace(":", "")
        .replace("T", "T")
        .replace("Z", "Z")
    )


def build_legacy_purchase_list_bridge(
    *,
    root: Path | None = None,
    source: str = "google",
    source_csv: str | Path | None = None,
    sheet_id: str = DEFAULT_SHEET_ID,
    sheet_title: str = DEFAULT_SHEET_TITLE,
    tab: str = DEFAULT_TAB,
    bridge_utc: str | None = None,
    credentials_path: str | Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    paths = ensure_o_directories(root=root_path)
    observed_utc = bridge_utc or _utc_now_iso()

    if source == "google":
        rows = load_purchase_list_rows_from_google(
            root=root_path,
            sheet_id=sheet_id,
            tab=tab,
            credentials_path=credentials_path,
        )
        source_path = f"google_sheet:{sheet_id}:{tab}"
    elif source == "csv":
        if source_csv is None:
            raise ValueError("--source-csv is required when --source csv is used")
        rows = load_purchase_list_rows_from_csv(source_csv)
        source_path = str(source_csv)
    else:
        raise ValueError(f"unsupported source: {source}")

    bridge_df, health_df = build_legacy_purchase_list_bridge_from_rows(
        rows,
        bridge_utc=observed_utc,
        sheet_id=sheet_id,
        sheet_title=sheet_title,
        tab=tab,
        source_path=source_path,
    )

    bridge_df = write_o_contract_df(root_path, "legacy_purchase_list_bridge", bridge_df)
    health_df = write_o_contract_df(root_path, "legacy_purchase_list_bridge_health", health_df)

    stamp = _history_stamp(observed_utc)
    bridge_history_path = paths.history_dir / f"legacy_purchase_list_bridge_{stamp}.csv"
    health_history_path = paths.history_dir / f"legacy_purchase_list_bridge_health_{stamp}.csv"
    bridge_history_path.parent.mkdir(parents=True, exist_ok=True)
    bridge_df.to_csv(bridge_history_path, index=False)
    health_df.to_csv(health_history_path, index=False)

    print(
        {
            "status": "success",
            "source": source,
            "bridge_rows": int(len(bridge_df.index)),
            "health_rows": int(len(health_df.index)),
            "bridge_output": str(root_path / "out" / "systems" / "O" / "live" / "legacy_purchase_list_bridge.csv"),
            "health_output": str(root_path / "out" / "systems" / "O" / "live" / "legacy_purchase_list_bridge_health.csv"),
            "bridge_history": str(bridge_history_path),
            "health_history": str(health_history_path),
        }
    )
    return bridge_df, health_df


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build read-only O bridge from legacy Purchase List Sheet.")
    parser.add_argument("--source", choices=["google", "csv"], default="google")
    parser.add_argument("--source-csv", default="")
    parser.add_argument("--sheet-id", default=DEFAULT_SHEET_ID)
    parser.add_argument("--sheet-title", default=DEFAULT_SHEET_TITLE)
    parser.add_argument("--tab", default=DEFAULT_TAB)
    parser.add_argument("--credentials-path", default="")
    args = parser.parse_args(list(argv) if argv is not None else None)

    build_legacy_purchase_list_bridge(
        source=args.source,
        source_csv=args.source_csv or None,
        sheet_id=args.sheet_id,
        sheet_title=args.sheet_title,
        tab=args.tab,
        credentials_path=args.credentials_path or None,
    )


if __name__ == "__main__":
    main()
