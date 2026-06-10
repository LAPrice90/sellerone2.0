from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from .paths import get_manager_paths


SELLERBOARD_REQUIRED_COLUMNS = [
    "AmazonOrderId",
    "PurchaseDate(UTC)",
    "OrderTotalCurrencyCode",
    "OrderTotalAmount",
    "Shipping",
    "Gift wrap",
    "Tax",
    "Item promotion",
    "Ship Promotion",
    "Products",
    "Comission",
    "FBAPerUnitFulfillmentFee",
    "OrderStatus",
    "NumberOfItems",
    "SalesChannel",
    "FulfillmentChannel",
    "ShippingCost",
]

SUMMARY_COLUMNS = [
    "observed_utc",
    "metric",
    "status",
    "value",
    "proof_label",
    "notes",
    "source_path",
]

ORDER_RECONCILIATION_COLUMNS = [
    "amazon_order_id",
    "sellerboard_status",
    "sellerboard_purchase_utc",
    "sellerboard_sales_channel",
    "sellerboard_currency",
    "sellerboard_asin",
    "mapped_sku",
    "local_order_status",
    "local_purchase_utc",
    "local_marketplace_id",
    "local_sales_channel",
    "sellerboard_units",
    "sellerboard_order_total",
    "sellerboard_shipping",
    "sellerboard_commission",
    "sellerboard_fba_fee",
    "local_order_total",
    "match_status",
    "proof_label",
]

SKU_GAP_COLUMNS = [
    "sku",
    "sellerboard_asin",
    "sellerboard_rows",
    "sellerboard_shipped_units",
    "sellerboard_return_rows",
    "sellerboard_order_total",
    "sellerboard_shipping_paid",
    "sellerboard_shipping_cost",
    "sellerboard_commission",
    "sellerboard_fba_fee",
    "local_refund_rows",
    "local_refund_amount",
    "expected_refund_cost_per_unit_gbp",
    "refund_connection_state",
    "fee_connection_state",
    "bridge_label",
]

MARKDOWN_NAME = "b_sellerboard_bridge_latest.md"
SUMMARY_NAME = "b_sellerboard_bridge_summary.csv"
SUMMARY_JSON_NAME = "b_sellerboard_bridge_summary.json"
ORDER_RECONCILIATION_NAME = "b_sellerboard_bridge_order_reconciliation.csv"
SKU_GAP_NAME = "b_sellerboard_bridge_sku_gap_report.csv"


@dataclass(frozen=True)
class SellerboardBridgeResult:
    observed_utc: str
    status: str
    source_path: Path
    window_start_utc: datetime
    window_end_utc: datetime
    summary_rows: list[dict[str, str]]
    order_rows: list[dict[str, str]]
    sku_gap_rows: list[dict[str, str]]


def build_sellerboard_bridge_report(
    *,
    root: Path | str | None = None,
    sellerboard_path: Path | str | None = None,
    observed_utc: str | None = None,
    window_start: str | None = None,
    window_end: str | None = None,
) -> SellerboardBridgeResult:
    paths = get_manager_paths(root)
    base = paths.root
    observed = observed_utc or utc_now_text()
    source_path = _resolve_sellerboard_path(base, sellerboard_path)
    source_hash = _sha256_text(source_path)

    raw_rows, headers = _read_csv(source_path)
    missing_columns = [column for column in SELLERBOARD_REQUIRED_COLUMNS if column not in headers]
    sellerboard_rows = [_normalise_sellerboard_row(row) for row in raw_rows]
    inferred_start, inferred_end = _infer_window(source_path, sellerboard_rows)
    start_utc = _parse_window_start(window_start) if window_start else inferred_start
    end_utc = _parse_window_end(window_end) if window_end else inferred_end

    orders = _load_local_orders(base)
    items = _load_local_items(base)
    order_master = _load_order_master(base)
    refunds = _load_refunds(base, start_utc, end_utc)
    fee_detail_counts = _load_fee_detail_proof_counts(base)
    fee_detail_rows = fee_detail_counts["total"]
    performance = _load_performance(base)

    item_map = _build_item_map(items)
    sellerboard_purchase_window = [
        row for row in sellerboard_rows if _in_window(row.get("purchase_dt"), start_utc, end_utc)
    ]
    sellerboard_shipped_window = [
        row for row in sellerboard_purchase_window if _status(row.get("OrderStatus")) == "shipped"
    ]
    sellerboard_returns_all = [row for row in sellerboard_rows if _status(row.get("OrderStatus")) == "return"]

    local_orders_window = {
        order_id: row
        for order_id, row in orders.items()
        if _in_window(row.get("purchase_dt"), start_utc, end_utc)
    }
    local_order_ids_all = set(orders)
    local_order_ids_window = set(local_orders_window)
    sellerboard_purchase_ids = {_text(row.get("AmazonOrderId")) for row in sellerboard_purchase_window}
    sellerboard_shipped_ids = {_text(row.get("AmazonOrderId")) for row in sellerboard_shipped_window}

    mapped_sellerboard_rows: list[dict[str, Any]] = []
    for row in sellerboard_rows:
        order_id = _text(row.get("AmazonOrderId"))
        asin = _text(row.get("Products"))
        mapped_sku = item_map.get((order_id, asin), "")
        mapped = dict(row)
        mapped["mapped_sku"] = mapped_sku
        mapped["mapped_to_sku"] = bool(mapped_sku)
        mapped_sellerboard_rows.append(mapped)

    mapped_shipped_window = [
        row
        for row in mapped_sellerboard_rows
        if _in_window(row.get("purchase_dt"), start_utc, end_utc)
        and _status(row.get("OrderStatus")) == "shipped"
    ]

    sellerboard_shipped_missing = sorted(sellerboard_shipped_ids - local_order_ids_all)
    sellerone_missing_from_sellerboard = sorted(local_order_ids_window - sellerboard_purchase_ids)
    sellerboard_unmapped_rows = [row for row in mapped_sellerboard_rows if not row.get("mapped_to_sku")]
    sellerboard_shipped_unmapped_rows = [row for row in mapped_shipped_window if not row.get("mapped_to_sku")]

    refund_order_ids = {row["order_id"] for row in refunds}
    sellerboard_return_ids = {_text(row.get("AmazonOrderId")) for row in sellerboard_returns_all}
    sellerboard_return_missing_refund = sorted(sellerboard_return_ids - refund_order_ids)
    refund_missing_sellerboard_return = sorted(refund_order_ids - sellerboard_return_ids)

    order_rows = _build_order_reconciliation_rows(
        sellerboard_rows=mapped_sellerboard_rows,
        sellerboard_purchase_ids=sellerboard_purchase_ids,
        local_orders_window=local_orders_window,
        local_orders_all=orders,
        window_start=start_utc,
        window_end=end_utc,
    )
    sku_gap_rows = _build_sku_gap_rows(
        sellerboard_rows=mapped_sellerboard_rows,
        refunds=refunds,
        performance=performance,
        fee_detail_rows=fee_detail_rows,
    )
    fee_totals = _fee_comparison_totals(mapped_shipped_window, order_master)

    fail_conditions = [
        bool(missing_columns),
        bool(sellerboard_shipped_missing),
        bool(sellerboard_shipped_unmapped_rows),
    ]
    warn_conditions = [
        bool(sellerboard_return_missing_refund),
        fee_detail_rows == 0,
        _performance_refund_nonzero_rows(performance) == 0 and bool(sellerboard_returns_all),
    ]
    status = "fail" if any(fail_conditions) else "warn" if any(warn_conditions) else "ok"

    summary_rows = _build_summary_rows(
        observed_utc=observed,
        source_path=source_path,
        source_hash=source_hash,
        status=status,
        missing_columns=missing_columns,
        sellerboard_rows=sellerboard_rows,
        sellerboard_purchase_window=sellerboard_purchase_window,
        sellerboard_shipped_window=sellerboard_shipped_window,
        sellerboard_returns_all=sellerboard_returns_all,
        local_orders_window=local_orders_window,
        sellerboard_shipped_missing=sellerboard_shipped_missing,
        sellerone_missing_from_sellerboard=sellerone_missing_from_sellerboard,
        sellerboard_unmapped_rows=sellerboard_unmapped_rows,
        sellerboard_shipped_unmapped_rows=sellerboard_shipped_unmapped_rows,
        refunds=refunds,
        sellerboard_return_missing_refund=sellerboard_return_missing_refund,
        refund_missing_sellerboard_return=refund_missing_sellerboard_return,
        fee_detail_rows=fee_detail_rows,
        fee_detail_counts=fee_detail_counts,
        performance=performance,
        fee_totals=fee_totals,
        window_start=start_utc,
        window_end=end_utc,
    )
    return SellerboardBridgeResult(
        observed_utc=observed,
        status=status,
        source_path=source_path,
        window_start_utc=start_utc,
        window_end_utc=end_utc,
        summary_rows=summary_rows,
        order_rows=order_rows,
        sku_gap_rows=sku_gap_rows,
    )


def write_sellerboard_bridge_outputs(result: SellerboardBridgeResult, output_dir: Path) -> dict[str, Path]:
    bridge_dir = output_dir / "sellerboard_bridge"
    bridge_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary_csv": bridge_dir / SUMMARY_NAME,
        "summary_json": bridge_dir / SUMMARY_JSON_NAME,
        "order_reconciliation_csv": bridge_dir / ORDER_RECONCILIATION_NAME,
        "sku_gap_csv": bridge_dir / SKU_GAP_NAME,
        "latest_md": bridge_dir / MARKDOWN_NAME,
    }
    _write_csv(paths["summary_csv"], SUMMARY_COLUMNS, result.summary_rows)
    _write_csv(paths["order_reconciliation_csv"], ORDER_RECONCILIATION_COLUMNS, result.order_rows)
    _write_csv(paths["sku_gap_csv"], SKU_GAP_COLUMNS, result.sku_gap_rows)
    payload = {
        "observed_utc": result.observed_utc,
        "status": result.status,
        "source_path": str(result.source_path),
        "window_start_utc": _iso(result.window_start_utc),
        "window_end_utc": _iso(result.window_end_utc),
        "summary": {row["metric"]: row for row in result.summary_rows},
    }
    paths["summary_json"].write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths["latest_md"].write_text(_build_markdown(result), encoding="utf-8")
    return paths


def utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve_sellerboard_path(base: Path, sellerboard_path: Path | str | None) -> Path:
    candidates: list[Path] = []
    if sellerboard_path:
        candidates.append(Path(sellerboard_path))
    env_path = os.environ.get("SELLERBOARD_ORDER_LIST_PATH", "").strip()
    if env_path:
        candidates.append(Path(env_path))
    inbox = base / "out" / "systems" / "M" / "sellerboard_bridge" / "inbox"
    candidates.extend(sorted(inbox.glob("DRJ_Hardware_OrderList_*.csv"), key=_mtime, reverse=True))
    candidates.extend(sorted((base / "reference").glob("DRJ_Hardware_OrderList_*.csv"), key=_mtime, reverse=True))
    for candidate in candidates:
        path = candidate if candidate.is_absolute() else base / candidate
        if path.exists():
            return path
    raise FileNotFoundError("No Sellerboard OrderList CSV was found.")


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
        reader = csv.DictReader(handle, dialect=dialect)
        rows = [{key: value or "" for key, value in row.items() if key is not None} for row in reader]
        return rows, list(reader.fieldnames or [])


def _read_csv_len(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.reader(handle)
            next(reader, None)
            return sum(1 for _row in reader)
    except OSError:
        return 0


def _load_fee_detail_proof_counts(base: Path) -> dict[str, int]:
    rows, _headers = _read_optional_csv(base / "out" / "fee_detail_ledger_api.csv")
    counts = {
        "total": 0,
        "commission": 0,
        "fba_fee": 0,
        "shipping_fee": 0,
        "other_fee": 0,
    }
    for row in rows:
        counts["total"] += 1
        counts[_fee_detail_category(row)] += 1
    return counts


def _fee_detail_category(row: dict[str, str]) -> str:
    text = " ".join(
        _text(row.get(column))
        for column in [
            "fee_type",
            "amount_type",
            "charge_type",
            "amount_description",
            "description",
        ]
    ).lower()
    compact = re.sub(r"[^a-z0-9]+", "", text)
    if "commission" in compact or "comission" in compact:
        return "commission"
    if "fba" in compact or "fulfillment" in compact or "perunitfulfillment" in compact:
        return "fba_fee"
    if "shipping" in compact or "postage" in compact or "carrier" in compact:
        return "shipping_fee"
    return "other_fee"


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def _normalise_sellerboard_row(row: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = dict(row)
    out["purchase_dt"] = _parse_sellerboard_datetime(row.get("PurchaseDate(UTC)", ""))
    for column in [
        "OrderTotalAmount",
        "Shipping",
        "Gift wrap",
        "Tax",
        "Item promotion",
        "Ship Promotion",
        "Comission",
        "FBAPerUnitFulfillmentFee",
        "NumberOfItems",
        "Coupons",
        "ShippingCost",
    ]:
        out[column] = _money(row.get(column, ""))
    return out


def _parse_sellerboard_datetime(value: str) -> datetime | None:
    text = _text(value)
    for fmt in ("%d/%m/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return parsed.replace(tzinfo=timezone.utc)
    return None


def _parse_iso_datetime(value: str) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _infer_window(source_path: Path, rows: list[dict[str, Any]]) -> tuple[datetime, datetime]:
    match = re.search(r"(\d{2})_(\d{2})_(\d{4})-(\d{2})_(\d{2})_(\d{4})", source_path.name)
    if match:
        day1, month1, year1, day2, month2, year2 = match.groups()
        start = datetime(int(year1), int(month1), int(day1), tzinfo=timezone.utc)
        end_day = date(int(year2), int(month2), int(day2)) + timedelta(days=1)
        end = datetime.combine(end_day, time.min, tzinfo=timezone.utc)
        return start, end
    dates = [row.get("purchase_dt") for row in rows if isinstance(row.get("purchase_dt"), datetime)]
    if dates:
        min_day = min(dates).date()
        max_day = max(dates).date() + timedelta(days=1)
        return datetime.combine(min_day, time.min, tzinfo=timezone.utc), datetime.combine(max_day, time.min, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return now - timedelta(days=7), now


def _parse_window_start(value: str) -> datetime:
    parsed = _parse_iso_datetime(value)
    if parsed:
        return parsed
    return datetime.combine(date.fromisoformat(value), time.min, tzinfo=timezone.utc)


def _parse_window_end(value: str) -> datetime:
    parsed = _parse_iso_datetime(value)
    if parsed:
        return parsed
    return datetime.combine(date.fromisoformat(value) + timedelta(days=1), time.min, tzinfo=timezone.utc)


def _in_window(value: Any, start: datetime, end: datetime) -> bool:
    return isinstance(value, datetime) and start <= value < end


def _load_local_orders(base: Path) -> dict[str, dict[str, Any]]:
    rows, _headers = _read_optional_csv(base / "out" / "orders_all.csv")
    orders: dict[str, dict[str, Any]] = {}
    for row in rows:
        order_id = _text(row.get("amazon_order_id"))
        if not order_id:
            continue
        enriched = dict(row)
        enriched["purchase_dt"] = _parse_iso_datetime(row.get("purchase_date", ""))
        enriched["order_total_amount_num"] = _money(row.get("order_total_amount", ""))
        orders[order_id] = enriched
    return orders


def _load_local_items(base: Path) -> list[dict[str, str]]:
    rows, _headers = _read_optional_csv(base / "out" / "order_items_all.csv")
    return rows


def _load_order_master(base: Path) -> dict[str, dict[str, float]]:
    rows, _headers = _read_optional_csv(base / "out" / "order_master.csv")
    grouped: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))  # type: ignore[assignment]
    for row in rows:
        order_id = _text(row.get("Order ID"))
        if not order_id:
            continue
        grouped[order_id]["Quantity Ordered"] += _money(row.get("Quantity Ordered", ""))
        for column in [
            "Price_Total",
            "Shipping_Total",
            "Price_VAT",
            "Shipping_VAT",
            "Price_ExVAT",
            "Shipping_ExVAT",
            "FBA_Fee_Total",
            "FBA_Fee_ExVAT",
            "Commission_Total",
            "Commission_ExVAT",
        ]:
            grouped[order_id][column] += _money(row.get(column, ""))
    return {order_id: dict(values) for order_id, values in grouped.items()}


def _load_refunds(base: Path, start: datetime, end: datetime) -> list[dict[str, Any]]:
    rows, _headers = _read_optional_csv(base / "out" / "financial_events_refunds.csv")
    out: list[dict[str, Any]] = []
    for row in rows:
        posted = _parse_iso_datetime(row.get("posted_date", ""))
        if not _in_window(posted, start, end):
            continue
        out.append(
            {
                "order_id": _text(row.get("order_id")),
                "sku": _text(row.get("sku")),
                "amount_type": _text(row.get("amount_type")),
                "amount": _money(row.get("amount", "")),
                "posted_dt": posted,
            }
        )
    return out


def _load_performance(base: Path) -> dict[str, dict[str, Any]]:
    rows, _headers = _read_optional_csv(base / "out" / "sku_performance_summary.csv")
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        sku = _text(row.get("sku"))
        if not sku:
            continue
        enriched = dict(row)
        enriched["expected_refund_cost_per_unit_gbp_num"] = _money(row.get("expected_refund_cost_per_unit_gbp", ""))
        out[sku] = enriched
    return out


def _read_optional_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], []
    try:
        return _read_csv(path)
    except (OSError, csv.Error):
        return [], []


def _build_item_map(items: list[dict[str, str]]) -> dict[tuple[str, str], str]:
    item_map: dict[tuple[str, str], str] = {}
    for row in items:
        order_id = _text(row.get("amazon_order_id") or row.get("AmazonOrderId"))
        asin = _text(row.get("asin") or row.get("ASIN"))
        sku = _text(row.get("seller_sku") or row.get("SellerSKU"))
        if order_id and asin and sku and (order_id, asin) not in item_map:
            item_map[(order_id, asin)] = sku
    return item_map


def _build_order_reconciliation_rows(
    *,
    sellerboard_rows: list[dict[str, Any]],
    sellerboard_purchase_ids: set[str],
    local_orders_window: dict[str, dict[str, Any]],
    local_orders_all: dict[str, dict[str, Any]],
    window_start: datetime,
    window_end: datetime,
) -> list[dict[str, str]]:
    rows_by_id: dict[str, dict[str, Any]] = {}
    for row in sellerboard_rows:
        order_id = _text(row.get("AmazonOrderId"))
        if order_id:
            rows_by_id[order_id] = row
    all_ids = sorted(set(rows_by_id) | set(local_orders_window))
    out: list[dict[str, str]] = []
    for order_id in all_ids:
        sb = rows_by_id.get(order_id, {})
        local = local_orders_window.get(order_id) or local_orders_all.get(order_id, {})
        sb_status = _status(sb.get("OrderStatus"))
        local_status = _status(local.get("order_status"))
        mapped_sku = _text(sb.get("mapped_sku"))
        if sb and local:
            if sb_status in {"shipped", "unshipped", "return"} and not mapped_sku:
                match_status = "sku_mapping_missing"
                label = "not yet proven"
            elif _statuses_compatible(sb_status, local_status):
                match_status = "matched"
                label = "API proved"
            elif sb_status == "return":
                match_status = "return_seen_original_order_present"
                label = "Sellerboard bridge estimate"
            else:
                match_status = "status_difference"
                label = "not yet proven"
        elif sb:
            if sb_status == "return":
                match_status = "return_original_order_not_in_local_file"
            elif sb_status == "shipped" and _in_window(sb.get("purchase_dt"), window_start, window_end):
                match_status = "sellerboard_shipped_missing_in_sellerone"
            else:
                match_status = "sellerboard_only"
            label = "Sellerboard bridge estimate"
        else:
            match_status = "sellerone_only"
            label = "not yet proven" if order_id not in sellerboard_purchase_ids else "API proved"
        out.append(
            {
                "amazon_order_id": order_id,
                "sellerboard_status": _text(sb.get("OrderStatus")),
                "sellerboard_purchase_utc": _iso_or_blank(sb.get("purchase_dt")),
                "sellerboard_sales_channel": _text(sb.get("SalesChannel")),
                "sellerboard_currency": _text(sb.get("OrderTotalCurrencyCode")),
                "sellerboard_asin": _text(sb.get("Products")),
                "mapped_sku": mapped_sku,
                "local_order_status": _text(local.get("order_status")),
                "local_purchase_utc": _iso_or_blank(local.get("purchase_dt")),
                "local_marketplace_id": _text(local.get("marketplace_id")),
                "local_sales_channel": _text(local.get("sales_channel")),
                "sellerboard_units": _num_text(sb.get("NumberOfItems")),
                "sellerboard_order_total": _num_text(sb.get("OrderTotalAmount")),
                "sellerboard_shipping": _num_text(sb.get("Shipping")),
                "sellerboard_commission": _num_text(sb.get("Comission")),
                "sellerboard_fba_fee": _num_text(sb.get("FBAPerUnitFulfillmentFee")),
                "local_order_total": _num_text(local.get("order_total_amount_num")),
                "match_status": match_status,
                "proof_label": label,
            }
        )
    return out


def _build_sku_gap_rows(
    *,
    sellerboard_rows: list[dict[str, Any]],
    refunds: list[dict[str, Any]],
    performance: dict[str, dict[str, Any]],
    fee_detail_rows: int,
) -> list[dict[str, str]]:
    by_sku: dict[str, dict[str, Any]] = defaultdict(lambda: defaultdict(float))  # type: ignore[assignment]
    asin_by_sku: dict[str, str] = {}
    for row in sellerboard_rows:
        sku = _text(row.get("mapped_sku")) or "UNMAPPED"
        asin = _text(row.get("Products"))
        if asin and sku not in asin_by_sku:
            asin_by_sku[sku] = asin
        bucket = by_sku[sku]
        bucket["rows"] += 1
        if _status(row.get("OrderStatus")) == "shipped":
            bucket["shipped_units"] += _money(row.get("NumberOfItems"))
        if _status(row.get("OrderStatus")) == "return":
            bucket["return_rows"] += 1
        bucket["order_total"] += _money(row.get("OrderTotalAmount"))
        bucket["shipping_paid"] += _money(row.get("Shipping"))
        bucket["shipping_cost"] += _money(row.get("ShippingCost"))
        bucket["commission"] += _money(row.get("Comission"))
        bucket["fba_fee"] += _money(row.get("FBAPerUnitFulfillmentFee"))
    refund_by_sku: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))  # type: ignore[assignment]
    for row in refunds:
        sku = _text(row.get("sku")) or "UNMAPPED"
        refund_by_sku[sku]["rows"] += 1
        refund_by_sku[sku]["amount"] += float(row.get("amount", 0.0) or 0.0)
    out: list[dict[str, str]] = []
    for sku in sorted(set(by_sku) | set(refund_by_sku)):
        sb = by_sku.get(sku, {})
        refund = refund_by_sku.get(sku, {})
        expected_refund = _money(performance.get(sku, {}).get("expected_refund_cost_per_unit_gbp", ""))
        return_rows = int(float(sb.get("return_rows", 0.0) or 0.0))
        local_refund_rows = int(float(refund.get("rows", 0.0) or 0.0))
        if expected_refund != 0:
            refund_state = "API proved"
        elif local_refund_rows:
            refund_state = "not yet proven"
        elif return_rows:
            refund_state = "Sellerboard bridge estimate"
        else:
            refund_state = "not applicable"
        fee_state = "API proved" if fee_detail_rows > 0 else "not yet proven"
        if sku == "UNMAPPED":
            bridge_label = "not yet proven"
        elif return_rows and not local_refund_rows:
            bridge_label = "Sellerboard bridge estimate"
        elif fee_state == "not yet proven":
            bridge_label = "not yet proven"
        else:
            bridge_label = "API proved"
        out.append(
            {
                "sku": sku,
                "sellerboard_asin": asin_by_sku.get(sku, ""),
                "sellerboard_rows": str(int(float(sb.get("rows", 0.0) or 0.0))),
                "sellerboard_shipped_units": _num_text(sb.get("shipped_units")),
                "sellerboard_return_rows": str(return_rows),
                "sellerboard_order_total": _num_text(sb.get("order_total")),
                "sellerboard_shipping_paid": _num_text(sb.get("shipping_paid")),
                "sellerboard_shipping_cost": _num_text(sb.get("shipping_cost")),
                "sellerboard_commission": _num_text(sb.get("commission")),
                "sellerboard_fba_fee": _num_text(sb.get("fba_fee")),
                "local_refund_rows": str(local_refund_rows),
                "local_refund_amount": _num_text(refund.get("amount")),
                "expected_refund_cost_per_unit_gbp": _num_text(expected_refund),
                "refund_connection_state": refund_state,
                "fee_connection_state": fee_state,
                "bridge_label": bridge_label,
            }
        )
    return out


def _fee_comparison_totals(
    sellerboard_shipped_window: list[dict[str, Any]],
    order_master: dict[str, dict[str, float]],
) -> dict[str, float]:
    matched = [row for row in sellerboard_shipped_window if _text(row.get("AmazonOrderId")) in order_master]
    sellerboard_units = sum(_money(row.get("NumberOfItems")) for row in matched)
    sellerboard_price = sum(_money(row.get("OrderTotalAmount")) for row in matched)
    sellerboard_shipping = sum(_money(row.get("Shipping")) for row in matched)
    sellerboard_shipping_cost = sum(_money(row.get("ShippingCost")) for row in matched)
    sellerboard_commission = sum(_money(row.get("Comission")) for row in matched)
    sellerboard_fba = sum(_money(row.get("FBAPerUnitFulfillmentFee")) for row in matched)
    master_units = sum(order_master[_text(row.get("AmazonOrderId"))].get("Quantity Ordered", 0.0) for row in matched)
    master_price = sum(order_master[_text(row.get("AmazonOrderId"))].get("Price_Total", 0.0) for row in matched)
    master_shipping = sum(order_master[_text(row.get("AmazonOrderId"))].get("Shipping_Total", 0.0) for row in matched)
    master_commission = sum(order_master[_text(row.get("AmazonOrderId"))].get("Commission_ExVAT", 0.0) for row in matched)
    master_fba = sum(order_master[_text(row.get("AmazonOrderId"))].get("FBA_Fee_ExVAT", 0.0) for row in matched)
    return {
        "matched_shipped_orders": float(len(matched)),
        "sellerboard_units": sellerboard_units,
        "master_units": master_units,
        "sellerboard_price": sellerboard_price,
        "master_price": master_price,
        "sellerboard_shipping": sellerboard_shipping,
        "sellerboard_shipping_cost": sellerboard_shipping_cost,
        "master_shipping": master_shipping,
        "sellerboard_commission": sellerboard_commission,
        "master_commission_exvat": master_commission,
        "sellerboard_fba": sellerboard_fba,
        "master_fba_exvat": master_fba,
    }


def _build_summary_rows(
    *,
    observed_utc: str,
    source_path: Path,
    source_hash: str,
    status: str,
    missing_columns: list[str],
    sellerboard_rows: list[dict[str, Any]],
    sellerboard_purchase_window: list[dict[str, Any]],
    sellerboard_shipped_window: list[dict[str, Any]],
    sellerboard_returns_all: list[dict[str, Any]],
    local_orders_window: dict[str, dict[str, Any]],
    sellerboard_shipped_missing: list[str],
    sellerone_missing_from_sellerboard: list[str],
    sellerboard_unmapped_rows: list[dict[str, Any]],
    sellerboard_shipped_unmapped_rows: list[dict[str, Any]],
    refunds: list[dict[str, Any]],
    sellerboard_return_missing_refund: list[str],
    refund_missing_sellerboard_return: list[str],
    fee_detail_rows: int,
    fee_detail_counts: dict[str, int],
    performance: dict[str, dict[str, Any]],
    fee_totals: dict[str, float],
    window_start: datetime,
    window_end: datetime,
) -> list[dict[str, str]]:
    source = str(source_path)
    rows: list[dict[str, str]] = []

    def add(metric: str, metric_status: str, value: Any, label: str, notes: str = "") -> None:
        rows.append(
            {
                "observed_utc": observed_utc,
                "metric": metric,
                "status": metric_status,
                "value": _num_text(value) if isinstance(value, float) else str(value),
                "proof_label": label,
                "notes": notes,
                "source_path": source,
            }
        )

    add("overall_status", status, status, _label_for_status(status), "Read-only manager comparison status.")
    add("source_sha256", "ok", source_hash, "API proved", "Source file hash for audit trace.")
    add("window_start_utc", "ok", _iso(window_start), "API proved", "Comparison purchase-window start.")
    add("window_end_utc", "ok", _iso(window_end), "API proved", "Comparison purchase-window end, exclusive.")
    add(
        "required_columns_missing",
        "fail" if missing_columns else "ok",
        len(missing_columns),
        "not yet proven" if missing_columns else "API proved",
        ";".join(missing_columns),
    )
    add("sellerboard_rows_total", "ok", len(sellerboard_rows), "Sellerboard bridge estimate")
    add("sellerboard_purchase_window_rows", "ok", len(sellerboard_purchase_window), "Sellerboard bridge estimate")
    add("sellerboard_shipped_rows", "ok", len(sellerboard_shipped_window), "Sellerboard bridge estimate")
    add("sellerboard_return_rows", "ok", len(sellerboard_returns_all), "Sellerboard bridge estimate")
    add("sellerone_purchase_window_orders", "ok", len(local_orders_window), "API proved")
    add(
        "sellerboard_shipped_missing_from_sellerone_orders",
        "fail" if sellerboard_shipped_missing else "ok",
        len(sellerboard_shipped_missing),
        "not yet proven" if sellerboard_shipped_missing else "API proved",
        ";".join(sellerboard_shipped_missing[:20]),
    )
    add(
        "sellerone_orders_missing_from_sellerboard_purchase_window",
        "warn" if sellerone_missing_from_sellerboard else "ok",
        len(sellerone_missing_from_sellerboard),
        "not yet proven" if sellerone_missing_from_sellerboard else "API proved",
        ";".join(sellerone_missing_from_sellerboard[:20]),
    )
    add(
        "sellerboard_rows_unmapped_to_sku",
        "fail" if sellerboard_shipped_unmapped_rows else "warn" if sellerboard_unmapped_rows else "ok",
        len(sellerboard_unmapped_rows),
        "not yet proven" if sellerboard_unmapped_rows else "API proved",
        ";".join(_text(row.get("AmazonOrderId")) for row in sellerboard_unmapped_rows[:20]),
    )
    add("sellerboard_shipped_rows_unmapped_to_sku", "fail" if sellerboard_shipped_unmapped_rows else "ok", len(sellerboard_shipped_unmapped_rows), "not yet proven" if sellerboard_shipped_unmapped_rows else "API proved")
    add("local_refund_rows_posted_window", "ok", len(refunds), "API proved")
    add("local_refund_orders_posted_window", "ok", len({row["order_id"] for row in refunds}), "API proved")
    add(
        "sellerboard_return_orders_missing_local_refund_posted_window",
        "warn" if sellerboard_return_missing_refund else "ok",
        len(sellerboard_return_missing_refund),
        "Sellerboard bridge estimate" if sellerboard_return_missing_refund else "API proved",
        ";".join(sellerboard_return_missing_refund[:20]),
    )
    add(
        "local_refund_orders_missing_sellerboard_return",
        "warn" if refund_missing_sellerboard_return else "ok",
        len(refund_missing_sellerboard_return),
        "not yet proven" if refund_missing_sellerboard_return else "API proved",
        ";".join(refund_missing_sellerboard_return[:20]),
    )
    add(
        "fee_detail_ledger_api_rows",
        "warn" if fee_detail_rows == 0 else "ok",
        fee_detail_rows,
        "not yet proven" if fee_detail_rows == 0 else "API proved",
        "Direct fee detail API evidence is empty." if fee_detail_rows == 0 else "",
    )
    add(
        "fee_detail_commission_api_rows",
        "warn" if _needs_fee_proof(fee_totals, "commission") and fee_detail_counts.get("commission", 0) == 0 else "ok",
        fee_detail_counts.get("commission", 0),
        "API proved" if fee_detail_counts.get("commission", 0) else "not yet proven",
        "No direct commission API rows were found." if _needs_fee_proof(fee_totals, "commission") and fee_detail_counts.get("commission", 0) == 0 else "",
    )
    add(
        "fee_detail_fba_fee_api_rows",
        "warn" if _needs_fee_proof(fee_totals, "fba_fee") and fee_detail_counts.get("fba_fee", 0) == 0 else "ok",
        fee_detail_counts.get("fba_fee", 0),
        "API proved" if fee_detail_counts.get("fba_fee", 0) else "not yet proven",
        "No direct FBA fee API rows were found." if _needs_fee_proof(fee_totals, "fba_fee") and fee_detail_counts.get("fba_fee", 0) == 0 else "",
    )
    add(
        "fee_detail_shipping_fee_api_rows",
        "warn" if _needs_fee_proof(fee_totals, "shipping_fee") and fee_detail_counts.get("shipping_fee", 0) == 0 else "ok",
        fee_detail_counts.get("shipping_fee", 0),
        "API proved" if fee_detail_counts.get("shipping_fee", 0) else "not yet proven",
        "No direct shipping fee API rows were found." if _needs_fee_proof(fee_totals, "shipping_fee") and fee_detail_counts.get("shipping_fee", 0) == 0 else "",
    )
    add(
        "fee_detail_other_fee_api_rows",
        "ok",
        fee_detail_counts.get("other_fee", 0),
        "API proved" if fee_detail_counts.get("other_fee", 0) else "API proved",
        "Other fee rows are optional unless a downstream check names a required fee type.",
    )
    refund_nonzero = _performance_refund_nonzero_rows(performance)
    add(
        "roi_expected_refund_nonzero_rows",
        "warn" if refund_nonzero == 0 and sellerboard_returns_all else "ok",
        refund_nonzero,
        "not yet proven" if refund_nonzero == 0 and sellerboard_returns_all else "API proved",
        "Current SKU performance has no non-zero expected refund cost rows." if refund_nonzero == 0 and sellerboard_returns_all else "",
    )
    refund_api_proof_state = _refund_api_proof_state(
        sellerboard_return_missing_refund=sellerboard_return_missing_refund,
        refund_missing_sellerboard_return=refund_missing_sellerboard_return,
        sellerboard_returns_all=sellerboard_returns_all,
        refunds=refunds,
    )
    commission_api_proof_state = _fee_api_proof_state(
        fee_detail_counts.get("commission", 0),
        _fee_need_value(fee_totals, "commission"),
    )
    fba_fee_api_proof_state = _fee_api_proof_state(
        fee_detail_counts.get("fba_fee", 0),
        _fee_need_value(fee_totals, "fba_fee"),
    )
    other_fee_api_proof_state = "api_proved" if fee_detail_counts.get("other_fee", 0) else "api_proved_or_not_applicable"
    shipping_income_api_proof_state = _shipping_income_api_proof_state(fee_totals)
    shipping_fee_api_proof_state = _fee_api_proof_state(
        fee_detail_counts.get("shipping_fee", 0),
        _fee_need_value(fee_totals, "shipping_fee"),
    )
    fee_component_states = [
        commission_api_proof_state,
        fba_fee_api_proof_state,
        shipping_income_api_proof_state,
        shipping_fee_api_proof_state,
    ]
    refund_proof_state = (
        "not_yet_proven"
        if refund_api_proof_state in {"sellerboard_bridge_only", "not_yet_proven"}
        else "api_proved_or_not_applicable"
    )
    if fee_detail_rows == 0:
        fee_shipping_proof_state = "not_yet_proven"
    elif any(_proof_state_needs_warning(state) for state in fee_component_states):
        fee_shipping_proof_state = "not_yet_proven"
    elif any(state == "api_proved" for state in fee_component_states):
        fee_shipping_proof_state = "api_proved"
    else:
        fee_shipping_proof_state = "api_proved_or_not_applicable"
    roi_refund_proof_state = (
        "not_yet_proven"
        if refund_nonzero == 0 and sellerboard_returns_all
        else "api_proved_or_not_applicable"
    )
    live_roi_safe = (
        refund_proof_state == "api_proved_or_not_applicable"
        and fee_shipping_proof_state == "api_proved"
        and roi_refund_proof_state == "api_proved_or_not_applicable"
    )
    roi_money_confidence_state = (
        "api_backed_safe"
        if live_roi_safe
        else "bridge_labelled_only"
        if refund_api_proof_state == "sellerboard_bridge_only" or shipping_income_api_proof_state == "sellerboard_bridge_only"
        else "not_yet_proven"
    )
    add(
        "refund_api_proof_state",
        "warn" if _proof_state_needs_warning(refund_api_proof_state) else "ok",
        refund_api_proof_state,
        _proof_label_for_state(refund_api_proof_state),
        "Sellerboard return evidence is not fully matched to local refund API rows." if _proof_state_needs_warning(refund_api_proof_state) else "",
    )
    add(
        "commission_api_proof_state",
        "warn" if _proof_state_needs_warning(commission_api_proof_state) else "ok",
        commission_api_proof_state,
        _proof_label_for_state(commission_api_proof_state),
        "Commission needs direct API proof before it can be treated as final ROI truth." if _proof_state_needs_warning(commission_api_proof_state) else "",
    )
    add(
        "fba_fee_api_proof_state",
        "warn" if _proof_state_needs_warning(fba_fee_api_proof_state) else "ok",
        fba_fee_api_proof_state,
        _proof_label_for_state(fba_fee_api_proof_state),
        "FBA fee needs direct API proof before it can be treated as final ROI truth." if _proof_state_needs_warning(fba_fee_api_proof_state) else "",
    )
    add(
        "other_fee_api_proof_state",
        "warn" if _proof_state_needs_warning(other_fee_api_proof_state) else "ok",
        other_fee_api_proof_state,
        _proof_label_for_state(other_fee_api_proof_state),
    )
    add(
        "shipping_income_api_proof_state",
        "warn" if _proof_state_needs_warning(shipping_income_api_proof_state) else "ok",
        shipping_income_api_proof_state,
        _proof_label_for_state(shipping_income_api_proof_state),
        "Sellerboard shipping income exists but local API shipping income proof is missing." if _proof_state_needs_warning(shipping_income_api_proof_state) else "",
    )
    add(
        "shipping_fee_api_proof_state",
        "warn" if _proof_state_needs_warning(shipping_fee_api_proof_state) else "ok",
        shipping_fee_api_proof_state,
        _proof_label_for_state(shipping_fee_api_proof_state),
        "Shipping fee needs direct API proof before it can be treated as final ROI truth." if _proof_state_needs_warning(shipping_fee_api_proof_state) else "",
    )
    add(
        "roi_money_confidence_state",
        "ok" if roi_money_confidence_state == "api_backed_safe" else "warn",
        roi_money_confidence_state,
        _proof_label_for_state(roi_money_confidence_state),
        "ROI must stay warning-labelled until refund, fee, and shipping proof is API-backed." if roi_money_confidence_state != "api_backed_safe" else "",
    )
    add(
        "refund_proof_state",
        "warn" if refund_proof_state == "not_yet_proven" else "ok",
        refund_proof_state,
        "not yet proven" if refund_proof_state == "not_yet_proven" else "API proved",
        "Refund rows have a Sellerboard/local mismatch." if refund_proof_state == "not_yet_proven" else "",
    )
    add(
        "fee_shipping_proof_state",
        "warn" if fee_shipping_proof_state == "not_yet_proven" else "ok",
        fee_shipping_proof_state,
        "not yet proven" if fee_shipping_proof_state == "not_yet_proven" else "API proved",
        "Direct fee detail API evidence is empty." if fee_shipping_proof_state == "not_yet_proven" else "",
    )
    add(
        "roi_refund_proof_state",
        "warn" if roi_refund_proof_state == "not_yet_proven" else "ok",
        roi_refund_proof_state,
        "not yet proven" if roi_refund_proof_state == "not_yet_proven" else "API proved",
        "ROI refund support is not proved for visible Sellerboard returns." if roi_refund_proof_state == "not_yet_proven" else "",
    )
    add(
        "bridge_values_safe_for_live_roi",
        "ok" if live_roi_safe else "warn",
        "1" if live_roi_safe else "0",
        "API proved" if live_roi_safe else "not yet proven",
        "0 means Sellerboard bridge values must stay out of live ROI and restocking decisions." if not live_roi_safe else "",
    )
    for metric, value in sorted(fee_totals.items()):
        add(f"fee_compare_{metric}", "ok", value, "Sellerboard bridge estimate")
    return rows


def _performance_refund_nonzero_rows(performance: dict[str, dict[str, Any]]) -> int:
    return sum(1 for row in performance.values() if float(row.get("expected_refund_cost_per_unit_gbp_num", 0.0) or 0.0) != 0.0)


def _needs_fee_proof(fee_totals: dict[str, float], component: str) -> bool:
    return abs(_fee_need_value(fee_totals, component)) > 0.005


def _fee_need_value(fee_totals: dict[str, float], component: str) -> float:
    if component == "commission":
        return fee_totals.get("sellerboard_commission", 0.0) or fee_totals.get("master_commission_exvat", 0.0)
    if component == "fba_fee":
        return fee_totals.get("sellerboard_fba", 0.0) or fee_totals.get("master_fba_exvat", 0.0)
    if component == "shipping_fee":
        return fee_totals.get("sellerboard_shipping_cost", 0.0)
    return 0.0


def _fee_api_proof_state(api_rows: int, value_needing_proof: float) -> str:
    if api_rows > 0:
        return "api_proved"
    if abs(value_needing_proof) <= 0.005:
        return "api_proved_or_not_applicable"
    return "not_yet_proven"


def _refund_api_proof_state(
    *,
    sellerboard_return_missing_refund: list[str],
    refund_missing_sellerboard_return: list[str],
    sellerboard_returns_all: list[dict[str, Any]],
    refunds: list[dict[str, Any]],
) -> str:
    if sellerboard_return_missing_refund:
        return "sellerboard_bridge_only"
    if refund_missing_sellerboard_return:
        return "not_yet_proven"
    if sellerboard_returns_all or refunds:
        return "api_proved"
    return "api_proved_or_not_applicable"


def _shipping_income_api_proof_state(fee_totals: dict[str, float]) -> str:
    sellerboard_shipping = fee_totals.get("sellerboard_shipping", 0.0)
    master_shipping = fee_totals.get("master_shipping", 0.0)
    if abs(master_shipping) > 0.005:
        return "api_proved"
    if abs(sellerboard_shipping) <= 0.005:
        return "api_proved_or_not_applicable"
    return "sellerboard_bridge_only"


def _proof_state_needs_warning(state: str) -> bool:
    return state in {"not_yet_proven", "sellerboard_bridge_only", "bridge_labelled_only"}


def _proof_label_for_state(state: str) -> str:
    if state in {"api_proved", "api_proved_or_not_applicable", "api_backed_safe"}:
        return "API proved"
    if state in {"sellerboard_bridge_only", "bridge_labelled_only"}:
        return "Sellerboard bridge estimate"
    return "not yet proven"


def _build_markdown(result: SellerboardBridgeResult) -> str:
    metrics = {row["metric"]: row for row in result.summary_rows}

    def value(metric: str) -> str:
        return metrics.get(metric, {}).get("value", "")

    lines = [
        "# B Sellerboard Bridge Report",
        "",
        f"Observed UTC: {result.observed_utc}",
        f"Status: {result.status}",
        f"Window: {_iso(result.window_start_utc)} to {_iso(result.window_end_utc)}",
        "",
        "## Plain English",
        "This is read-only outside proof. It compares SellerOne against Sellerboard and labels any bridge values so they are not mistaken for final API truth.",
        "",
        "## Key Checks",
        f"- Sellerboard rows: {value('sellerboard_rows_total')}",
        f"- Sellerboard shipped rows: {value('sellerboard_shipped_rows')}",
        f"- Sellerboard return rows: {value('sellerboard_return_rows')}",
        f"- Sellerboard shipped orders missing from SellerOne: {value('sellerboard_shipped_missing_from_sellerone_orders')}",
        f"- Sellerboard rows not mapped to SKU: {value('sellerboard_rows_unmapped_to_sku')}",
        f"- Sellerboard return orders missing local refund proof: {value('sellerboard_return_orders_missing_local_refund_posted_window')}",
        f"- Direct fee detail rows: {value('fee_detail_ledger_api_rows')}",
        f"- Non-zero expected refund rows in SKU performance: {value('roi_expected_refund_nonzero_rows')}",
        f"- Refund API proof: {value('refund_api_proof_state')}",
        f"- Commission API proof: {value('commission_api_proof_state')}",
        f"- FBA fee API proof: {value('fba_fee_api_proof_state')}",
        f"- Shipping income API proof: {value('shipping_income_api_proof_state')}",
        f"- Shipping fee API proof: {value('shipping_fee_api_proof_state')}",
        f"- ROI money confidence: {value('roi_money_confidence_state')}",
        f"- Refund proof state: {value('refund_proof_state')}",
        f"- Fee/shipping proof state: {value('fee_shipping_proof_state')}",
        f"- ROI refund proof state: {value('roi_refund_proof_state')}",
        f"- Bridge values safe for live ROI: {value('bridge_values_safe_for_live_roi')}",
        "",
        "## Safety",
        "- This report did not run B.",
        "- This report did not write Google Sheets.",
        "- This report did not change ROI, prices, queues, tokens, local DB facts, or order data.",
        "- Sellerboard values are bridge evidence only until direct API allocation is proven.",
        "",
    ]
    return "\n".join(lines)


def _sha256_text(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _money(value: Any) -> float:
    text = str(value or "").strip().replace(",", "").replace("GBP", "").replace("£", "")
    if not text or text.lower() in {"nan", "none"}:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _status(value: Any) -> str:
    text = _text(value).lower()
    if text == "cancelled":
        return "canceled"
    if text == "pending":
        return "unshipped"
    return text


def _statuses_compatible(sellerboard_status: str, local_status: str) -> bool:
    if sellerboard_status == local_status:
        return True
    return (sellerboard_status, local_status) in {
        ("unshipped", "pending"),
        ("canceled", "cancelled"),
        ("cancelled", "canceled"),
    }


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _iso_or_blank(value: Any) -> str:
    return _iso(value) if isinstance(value, datetime) else ""


def _num_text(value: Any) -> str:
    if value is None or value == "":
        return "0"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.2f}"


def _label_for_status(status: str) -> str:
    if status == "ok":
        return "API proved"
    if status == "warn":
        return "Sellerboard bridge estimate"
    return "not yet proven"
