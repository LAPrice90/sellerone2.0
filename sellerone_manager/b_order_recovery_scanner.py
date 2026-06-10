from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

from .b_order_recovery import (
    EXPECTED_CURSOR_REL_PATH,
    EXPECTED_QUARANTINE_REL_PATH,
    QUARANTINE_REQUIRED_COLUMNS,
    RECOVERY_START_UTC,
    _load_marketplaces,
    _read_csv_rows,
    _sales_channel_map,
    _text,
    parse_utc,
    utc_now_text,
)
from .paths import get_manager_paths
from .sellerboard_bridge import ORDER_RECONCILIATION_NAME


SCAN_MANIFEST_NAME = "b_order_recovery_scan_manifest.json"
SCAN_RESULTS_NAME = "b_order_recovery_scan_results.csv"
CURSOR_COLUMNS = [
    "observed_utc",
    "marketplace_id",
    "marketplace_name",
    "country_code",
    "status",
    "scan_scope",
    "backdate_start_utc",
    "scan_window_start_utc",
    "scan_window_end_utc",
    "orders_seen",
    "pages_checked",
    "last_success_utc",
    "cursor_utc",
    "error",
    "source",
    "proof_label",
]
SCAN_RESULT_COLUMNS = [
    "observed_utc",
    "scan_type",
    "marketplace_id",
    "amazon_order_id",
    "status",
    "proof_label",
    "notes",
]


class OrderRecoveryApi(Protocol):
    def fetch_order(self, order_id: str) -> dict[str, Any]:
        ...

    def list_order_items(self, order_id: str) -> list[dict[str, Any]]:
        ...

    def list_orders_page(
        self,
        *,
        marketplace_id: str,
        created_after: str,
        created_before: str,
        next_token: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        ...


@dataclass(frozen=True)
class BOrderRecoveryScanResult:
    observed_utc: str
    status: str
    quarantine_rows_written: int
    cursor_rows_written: int
    scan_result_rows: list[dict[str, str]]
    manifest_path: Path


class SpApiOrderRecoveryClient:
    def __init__(self) -> None:
        from scripts.api.get_orders import get_lwa_access_token, load_dotenv_if_missing

        load_dotenv_if_missing()
        self.access_token = get_lwa_access_token()

    def fetch_order(self, order_id: str) -> dict[str, Any]:
        import requests
        from scripts.api.get_orders import SPAPI_BASE_URL

        url = f"{SPAPI_BASE_URL}/orders/v0/orders/{order_id}"
        headers = {
            "x-amz-access-token": self.access_token,
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"order_fetch_failed:{response.status_code}")
        payload = response.json() or {}
        order = (payload.get("payload") or {})
        if not order:
            raise RuntimeError("order_payload_missing")
        return order

    def list_order_items(self, order_id: str) -> list[dict[str, Any]]:
        from scripts.api.get_orders import list_order_items

        rows: list[dict[str, Any]] = []
        next_token: str | None = None
        while True:
            batch, next_token = list_order_items(self.access_token, order_id, next_token=next_token)
            for item in batch:
                if isinstance(item, dict):
                    item["AmazonOrderId"] = order_id
                    rows.append(item)
            if not next_token:
                return rows

    def list_orders_page(
        self,
        *,
        marketplace_id: str,
        created_after: str,
        created_before: str,
        next_token: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        from scripts.api.get_orders import list_orders

        return list_orders(
            self.access_token,
            marketplace_ids=[marketplace_id],
            created_after=created_after,
            created_before=created_before,
            next_token=next_token,
        )


def run_b_order_recovery_scan(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
    api_client: OrderRecoveryApi | None = None,
    fetch_missing_orders: bool = True,
    check_marketplace_cursors: bool = True,
    cursor_lookback_hours: float = 48.0,
    max_pages_per_marketplace: int = 1,
    orders_api_lag_minutes: float = 5.0,
    page_sleep_seconds: float = 0.0,
) -> BOrderRecoveryScanResult:
    paths = get_manager_paths(root)
    base = paths.root
    observed = observed_utc or utc_now_text()
    observed_dt = parse_utc(observed) or datetime.now(timezone.utc)
    client = api_client or SpApiOrderRecoveryClient()

    marketplaces = _load_marketplaces(base / "out" / "marketplace_participations.csv")
    sellerboard = _read_csv_rows(base / "out" / "systems" / "M" / "sellerboard_bridge" / ORDER_RECONCILIATION_NAME)
    orders = _read_csv_rows(base / "out" / "orders_all.csv")
    existing_local_order_ids = {_text(row.get("amazon_order_id")) for row in orders if _text(row.get("amazon_order_id"))}
    channel_to_marketplace = _sales_channel_map(marketplaces)
    scan_results: list[dict[str, str]] = []

    quarantine_rows = _read_csv_rows(base / EXPECTED_QUARANTINE_REL_PATH)
    if fetch_missing_orders:
        for sellerboard_row in _missing_sellerboard_rows(sellerboard):
            order_id = _text(sellerboard_row.get("amazon_order_id"))
            if not order_id:
                continue
            if order_id in existing_local_order_ids:
                scan_results.append(_scan_row(observed, "missing_order", "", order_id, "already_local", "API proved", "Order is already present in local B proof."))
                continue
            market_id = _sellerboard_marketplace_id(sellerboard_row, channel_to_marketplace)
            try:
                order = client.fetch_order(order_id)
                items = client.list_order_items(order_id)
                new_row = _quarantine_row(
                    order=order,
                    items=items,
                    sellerboard_row=sellerboard_row,
                    marketplace_id=market_id,
                    proof_label="API proved",
                    source="api_backdate",
                )
                quarantine_rows = _merge_quarantine_row(quarantine_rows, new_row)
                scan_results.append(_scan_row(observed, "missing_order", market_id, order_id, "ok", "API proved", "Order and item proof fetched into quarantine."))
            except Exception as exc:
                fallback = _quarantine_row(
                    order={},
                    items=[],
                    sellerboard_row=sellerboard_row,
                    marketplace_id=market_id,
                    proof_label="not yet proven",
                    source="api_backdate_error",
                )
                quarantine_rows = _merge_quarantine_row(quarantine_rows, fallback)
                scan_results.append(_scan_row(observed, "missing_order", market_id, order_id, "fail", "not yet proven", f"{exc.__class__.__name__}"))

    cursor_rows: list[dict[str, str]] = []
    if check_marketplace_cursors:
        window_end = (observed_dt - timedelta(minutes=max(orders_api_lag_minutes, 0.0))).replace(microsecond=0)
        window_start = (window_end - timedelta(hours=max(cursor_lookback_hours, 1.0))).replace(microsecond=0)
        for marketplace_id, marketplace in sorted(marketplaces.items()):
            if not _is_amazon_marketplace(marketplace):
                continue
            row = _cursor_probe_row(
                client=client,
                observed=observed,
                observed_dt=observed_dt,
                marketplace_id=marketplace_id,
                marketplace=marketplace,
                created_after=_iso_z(window_start),
                created_before=_iso_z(window_end),
                max_pages=max(1, int(max_pages_per_marketplace)),
                page_sleep_seconds=max(page_sleep_seconds, 0.0),
            )
            cursor_rows.append(row)
            scan_results.append(
                _scan_row(
                    observed,
                    "marketplace_cursor",
                    marketplace_id,
                    "",
                    row["status"],
                    row["proof_label"],
                    row["error"] or f"orders_seen={row['orders_seen']};pages={row['pages_checked']}",
                )
            )

    quarantine_path = base / EXPECTED_QUARANTINE_REL_PATH
    cursor_path = base / EXPECTED_CURSOR_REL_PATH
    if fetch_missing_orders:
        _write_csv(quarantine_path, QUARANTINE_REQUIRED_COLUMNS, quarantine_rows)
    if check_marketplace_cursors:
        _write_csv(cursor_path, CURSOR_COLUMNS, cursor_rows)

    status = "ok"
    if any(row["status"] == "fail" for row in scan_results):
        status = "fail"
    elif any(row["status"] == "partial_page_limit" for row in scan_results):
        status = "partial"

    manager_dir = paths.output_dir / "b_order_recovery"
    manager_dir.mkdir(parents=True, exist_ok=True)
    results_path = manager_dir / SCAN_RESULTS_NAME
    manifest_path = manager_dir / SCAN_MANIFEST_NAME
    _write_csv(results_path, SCAN_RESULT_COLUMNS, scan_results)
    manifest = {
        "observed_utc": observed,
        "status": status,
        "backdate_start_utc": RECOVERY_START_UTC,
        "fetch_missing_orders": fetch_missing_orders,
        "check_marketplace_cursors": check_marketplace_cursors,
        "cursor_lookback_hours": cursor_lookback_hours,
        "max_pages_per_marketplace": max_pages_per_marketplace,
        "quarantine_path": str(quarantine_path),
        "cursor_path": str(cursor_path),
        "scan_results_path": str(results_path),
        "quarantine_rows_written": len(quarantine_rows) if fetch_missing_orders else 0,
        "cursor_rows_written": len(cursor_rows),
        "safety": {
            "b_run_started": False,
            "business_outputs_changed": False,
            "local_db_changed": False,
            "sheets_written": False,
            "live_merge": False,
            "output_deleted": False,
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return BOrderRecoveryScanResult(
        observed_utc=observed,
        status=status,
        quarantine_rows_written=len(quarantine_rows) if fetch_missing_orders else 0,
        cursor_rows_written=len(cursor_rows),
        scan_result_rows=scan_results,
        manifest_path=manifest_path,
    )


def _missing_sellerboard_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if _text(row.get("match_status")).lower() == "sellerboard_shipped_missing_in_sellerone"
    ]


def _sellerboard_marketplace_id(row: dict[str, str], channel_to_marketplace: dict[str, str]) -> str:
    local_market = _text(row.get("local_marketplace_id"))
    if local_market:
        return local_market
    channel = _text(row.get("sellerboard_sales_channel"))
    return channel_to_marketplace.get(channel.lower(), "") if channel else ""


def _quarantine_row(
    *,
    order: dict[str, Any],
    items: list[dict[str, Any]],
    sellerboard_row: dict[str, str],
    marketplace_id: str,
    proof_label: str,
    source: str,
) -> dict[str, str]:
    order_id = _text(order.get("AmazonOrderId") or sellerboard_row.get("amazon_order_id"))
    total = order.get("OrderTotal") if isinstance(order.get("OrderTotal"), dict) else {}
    sku_values = sorted({_text(item.get("SellerSKU")) for item in items if _text(item.get("SellerSKU"))})
    asin_values = sorted({_text(item.get("ASIN") or sellerboard_row.get("sellerboard_asin")) for item in items if _text(item.get("ASIN") or sellerboard_row.get("sellerboard_asin"))})
    order_item_ids = sorted({_text(item.get("OrderItemId")) for item in items if _text(item.get("OrderItemId"))})
    quantity = sum(_to_int(item.get("QuantityOrdered")) for item in items)
    return {
        "amazon_order_id": order_id,
        "marketplace_id": _text(order.get("MarketplaceId") or marketplace_id),
        "purchase_utc": _text(order.get("PurchaseDate") or sellerboard_row.get("sellerboard_purchase_utc")),
        "order_status": _text(order.get("OrderStatus") or sellerboard_row.get("sellerboard_status")),
        "sku": ";".join(sku_values) or _text(sellerboard_row.get("mapped_sku")),
        "asin": ";".join(asin_values) or _text(sellerboard_row.get("sellerboard_asin")),
        "order_item_ids": ";".join(order_item_ids),
        "quantity": str(quantity or _to_int(sellerboard_row.get("sellerboard_units")) or 1),
        "currency": _text(total.get("CurrencyCode") or sellerboard_row.get("sellerboard_currency")),
        "order_total": _text(total.get("Amount") or sellerboard_row.get("sellerboard_order_total")),
        "last_update_utc": _text(order.get("LastUpdateDate")),
        "sales_channel": _text(order.get("SalesChannel") or sellerboard_row.get("sellerboard_sales_channel")),
        "fulfillment_channel": _text(order.get("FulfillmentChannel")),
        "order_payload_json": json.dumps(order, sort_keys=True, separators=(",", ":"), default=str),
        "items_payload_json": json.dumps(items, sort_keys=True, separators=(",", ":"), default=str),
        "source": source,
        "proof_label": proof_label,
        "duplicate_state": "unique_in_quarantine",
        "ready_for_live_merge": "0",
    }


def _merge_quarantine_row(rows: list[dict[str, str]], new_row: dict[str, str]) -> list[dict[str, str]]:
    order_id = _text(new_row.get("amazon_order_id"))
    if not order_id:
        return rows
    merged: list[dict[str, str]] = []
    replaced = False
    for row in rows:
        if _text(row.get("amazon_order_id")) != order_id:
            merged.append(row)
            continue
        if _text(row.get("ready_for_live_merge")).lower() in {"1", "yes", "true", "ready"}:
            merged.append(row)
        else:
            merged.append({**row, **{key: value for key, value in new_row.items() if value != ""}})
        replaced = True
    if not replaced:
        merged.append(new_row)
    return merged


def _cursor_probe_row(
    *,
    client: OrderRecoveryApi,
    observed: str,
    observed_dt: datetime,
    marketplace_id: str,
    marketplace: dict[str, str],
    created_after: str,
    created_before: str,
    max_pages: int,
    page_sleep_seconds: float,
) -> dict[str, str]:
    orders_seen = 0
    pages = 0
    next_token: str | None = None
    try:
        while True:
            batch, next_token = client.list_orders_page(
                marketplace_id=marketplace_id,
                created_after=created_after,
                created_before=created_before,
                next_token=next_token,
            )
            pages += 1
            orders_seen += len(batch)
            if not next_token:
                return _cursor_row(
                    observed=observed,
                    marketplace_id=marketplace_id,
                    marketplace=marketplace,
                    status="ok",
                    created_after=created_after,
                    created_before=created_before,
                    orders_seen=orders_seen,
                    pages=pages,
                    last_success_utc=observed,
                    cursor_utc=observed,
                    error="",
                    proof_label="API proved",
                )
            if pages >= max_pages:
                return _cursor_row(
                    observed=observed,
                    marketplace_id=marketplace_id,
                    marketplace=marketplace,
                    status="partial_page_limit",
                    created_after=created_after,
                    created_before=created_before,
                    orders_seen=orders_seen,
                    pages=pages,
                    last_success_utc="",
                    cursor_utc="",
                    error="next_token_remaining",
                    proof_label="not yet proven",
                )
            if page_sleep_seconds:
                time.sleep(page_sleep_seconds)
    except Exception as exc:
        return _cursor_row(
            observed=observed,
            marketplace_id=marketplace_id,
            marketplace=marketplace,
            status="fail",
            created_after=created_after,
            created_before=created_before,
            orders_seen=orders_seen,
            pages=pages,
            last_success_utc="",
            cursor_utc="",
            error=exc.__class__.__name__,
            proof_label="not yet proven",
        )


def _cursor_row(
    *,
    observed: str,
    marketplace_id: str,
    marketplace: dict[str, str],
    status: str,
    created_after: str,
    created_before: str,
    orders_seen: int,
    pages: int,
    last_success_utc: str,
    cursor_utc: str,
    error: str,
    proof_label: str,
) -> dict[str, str]:
    return {
        "observed_utc": observed,
        "marketplace_id": marketplace_id,
        "marketplace_name": _text(marketplace.get("marketplace_name")),
        "country_code": _text(marketplace.get("country_code")),
        "status": status,
        "scan_scope": "future_cursor",
        "backdate_start_utc": RECOVERY_START_UTC,
        "scan_window_start_utc": created_after,
        "scan_window_end_utc": created_before,
        "orders_seen": str(orders_seen),
        "pages_checked": str(pages),
        "last_success_utc": last_success_utc,
        "cursor_utc": cursor_utc,
        "error": error,
        "source": "sellerone_manager.b_order_recovery_scanner",
        "proof_label": proof_label,
    }


def _scan_row(
    observed: str,
    scan_type: str,
    marketplace_id: str,
    order_id: str,
    status: str,
    proof_label: str,
    notes: str,
) -> dict[str, str]:
    return {
        "observed_utc": observed,
        "scan_type": scan_type,
        "marketplace_id": marketplace_id,
        "amazon_order_id": order_id,
        "status": status,
        "proof_label": proof_label,
        "notes": notes,
    }


def _is_amazon_marketplace(marketplace: dict[str, str]) -> bool:
    name = _text(marketplace.get("marketplace_name")).lower()
    domain = _text(marketplace.get("domain_name")).lower()
    if name.startswith("non-amazon"):
        return False
    return "amazon" in name or "amazon." in domain


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def _to_int(value: Any) -> int:
    try:
        return int(float(str(value or "0")))
    except ValueError:
        return 0


def _iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
