from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import get_manager_paths
from .b_order_recovery import EXPECTED_QUARANTINE_REL_PATH
from .sellerboard_bridge import ORDER_RECONCILIATION_NAME


COVERAGE_DIR_NAME = "b_marketplace_coverage"
COVERAGE_CSV_NAME = "b_marketplace_coverage_by_marketplace.csv"
SUMMARY_CSV_NAME = "b_marketplace_coverage_summary.csv"
SUMMARY_JSON_NAME = "b_marketplace_coverage_summary.json"
MARKDOWN_NAME = "b_marketplace_coverage_latest.md"

COVERAGE_COLUMNS = [
    "observed_utc",
    "marketplace_id",
    "marketplace_name",
    "country_code",
    "sales_channel",
    "participating",
    "local_order_rows",
    "local_first_order_utc",
    "local_latest_order_utc",
    "local_latest_order_age_days",
    "local_item_order_count",
    "local_item_rows",
    "level1_order_count",
    "order_master_order_count",
    "level3_order_count",
    "refund_order_count",
    "sellerboard_rows",
    "sellerboard_shipped_rows",
    "sellerboard_missing_shipped_orders",
    "sellerboard_api_proved_quarantine_orders",
    "sellerboard_unrecovered_shipped_orders",
    "sellerboard_status_difference_rows",
    "sellerboard_unmapped_shipped_rows",
    "shared_cursor_risk",
    "coverage_status",
    "proof_label",
    "manager_coverage_label",
    "manager_next_step",
    "notes",
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


@dataclass(frozen=True)
class MarketplaceCoverageResult:
    observed_utc: str
    status: str
    coverage_rows: list[dict[str, str]]
    summary_rows: list[dict[str, str]]
    source_paths: list[Path]


def build_b_marketplace_coverage_report(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
) -> MarketplaceCoverageResult:
    paths = get_manager_paths(root)
    base = paths.root
    observed = observed_utc or utc_now_text()
    now = parse_utc(observed) or datetime.now(timezone.utc)

    marketplace_path = base / "out" / "marketplace_participations.csv"
    orders_path = base / "out" / "orders_all.csv"
    items_path = base / "out" / "order_items_all.csv"
    level1_path = base / "out" / "financial_events_level1.csv"
    order_master_path = base / "out" / "order_master.csv"
    level3_path = base / "out" / "financial_events_level3_official.csv"
    refunds_path = base / "out" / "financial_events_refunds.csv"
    marker_path = base / "out" / "orders_last_updated.txt"
    sellerboard_path = base / "out" / "systems" / "M" / "sellerboard_bridge" / ORDER_RECONCILIATION_NAME
    quarantine_path = base / EXPECTED_QUARANTINE_REL_PATH

    marketplaces = _load_marketplaces(marketplace_path)
    raw_orders = _read_csv_rows(orders_path)
    raw_items = _read_csv_rows(items_path)
    level1 = _read_csv_rows(level1_path)
    order_master = _read_csv_rows(order_master_path)
    level3 = _read_csv_rows(level3_path)
    refunds = _read_csv_rows(refunds_path)
    sellerboard = _read_csv_rows(sellerboard_path)
    quarantine = _read_csv_rows(quarantine_path)
    marker_dt = _read_marker(marker_path)

    orders = [
        row
        for row in raw_orders
        if _text(row.get("amazon_order_id")) and _text(row.get("marketplace_id"))
    ]
    items = [row for row in raw_items if _text(row.get("amazon_order_id"))]

    orders_by_id = {_text(row.get("amazon_order_id")): row for row in orders if _text(row.get("amazon_order_id"))}
    channel_to_marketplace = _sales_channel_map(marketplaces)
    market_ids = set(marketplaces)

    order_stats = _order_stats_by_marketplace(orders, now)
    item_stats = _joined_order_stats(items, orders_by_id, "amazon_order_id")
    level1_stats = _level1_stats(level1, orders_by_id)
    master_stats = _joined_order_stats(order_master, orders_by_id, "Order ID")
    level3_stats = _joined_order_stats(level3, orders_by_id, "Order ID")
    refund_stats = _refund_stats(refunds, orders_by_id)
    api_proved_quarantine_ids = _api_proved_quarantine_order_ids(quarantine)
    sellerboard_stats = _sellerboard_stats(sellerboard, orders_by_id, channel_to_marketplace, marker_dt, api_proved_quarantine_ids)

    market_ids.update(order_stats)
    market_ids.update(item_stats)
    market_ids.update(level1_stats)
    market_ids.update(master_stats)
    market_ids.update(level3_stats)
    market_ids.update(refund_stats)
    market_ids.update(sellerboard_stats)

    coverage_rows = [
        _coverage_row(
            observed=observed,
            market_id=market_id,
            marketplaces=marketplaces,
            order_stats=order_stats,
            item_stats=item_stats,
            level1_stats=level1_stats,
            master_stats=master_stats,
            level3_stats=level3_stats,
            refund_stats=refund_stats,
            sellerboard_stats=sellerboard_stats,
        )
        for market_id in sorted(market_ids, key=lambda value: (value.startswith("sellerboard:"), value))
    ]
    status = _overall_status(coverage_rows, orders, sellerboard)
    summary_rows = _summary_rows(
        observed=observed,
        status=status,
        coverage_rows=coverage_rows,
        marketplaces=marketplaces,
        orders=orders,
        sellerboard=sellerboard,
        marker_dt=marker_dt,
        source_path=sellerboard_path,
    )
    return MarketplaceCoverageResult(
        observed_utc=observed,
        status=status,
        coverage_rows=coverage_rows,
        summary_rows=summary_rows,
        source_paths=[
            marketplace_path,
            orders_path,
            items_path,
            level1_path,
            order_master_path,
            level3_path,
            refunds_path,
            marker_path,
            sellerboard_path,
            quarantine_path,
        ],
    )


def write_b_marketplace_coverage_outputs(result: MarketplaceCoverageResult, output_dir: Path) -> dict[str, Path]:
    out_dir = output_dir / COVERAGE_DIR_NAME
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "coverage_csv": out_dir / COVERAGE_CSV_NAME,
        "summary_csv": out_dir / SUMMARY_CSV_NAME,
        "summary_json": out_dir / SUMMARY_JSON_NAME,
        "markdown": out_dir / MARKDOWN_NAME,
    }
    _write_csv(paths["coverage_csv"], COVERAGE_COLUMNS, result.coverage_rows)
    _write_csv(paths["summary_csv"], SUMMARY_COLUMNS, result.summary_rows)
    paths["summary_json"].write_text(
        json.dumps(_summary_json(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths["markdown"].write_text(_markdown(result), encoding="utf-8")
    return paths


def utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open("r", newline="", encoding="utf-8-sig", errors="ignore") as handle:
            reader = csv.DictReader(handle)
            return [{key: value or "" for key, value in row.items() if key is not None} for row in reader]
    except (OSError, csv.Error):
        return []


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _status(value: Any) -> str:
    return _text(value).lower().replace(" ", "_")


def _load_marketplaces(path: Path) -> dict[str, dict[str, str]]:
    rows = _read_csv_rows(path)
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        market_id = _text(row.get("marketplace_id"))
        if not market_id:
            continue
        out[market_id] = {
            "marketplace_id": market_id,
            "marketplace_name": _text(row.get("name")),
            "country_code": _text(row.get("country_code")),
            "domain_name": _text(row.get("domain_name")),
            "participating": _text(row.get("is_participating") or "1") or "1",
        }
    return out


def _sales_channel_map(marketplaces: dict[str, dict[str, str]]) -> dict[str, str]:
    out: dict[str, str] = {}
    non_amazon_fallback = ""
    for market_id, row in marketplaces.items():
        name = _text(row.get("marketplace_name"))
        domain = _text(row.get("domain_name"))
        if name:
            out[name.lower()] = market_id
        if domain:
            out[domain.lower()] = market_id
        if name.lower().startswith("non-amazon") and not non_amazon_fallback:
            non_amazon_fallback = market_id
    if non_amazon_fallback:
        out["non-amazon"] = non_amazon_fallback
    return out


def _read_marker(path: Path) -> datetime | None:
    try:
        return parse_utc(path.read_text(encoding="utf-8").strip())
    except OSError:
        return None


def _order_stats_by_marketplace(rows: list[dict[str, str]], now: datetime) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = defaultdict(_new_stats)
    for row in rows:
        market_id = _text(row.get("marketplace_id")) or "<blank>"
        order_id = _text(row.get("amazon_order_id"))
        purchase = parse_utc(_text(row.get("purchase_date")))
        bucket = stats[market_id]
        bucket["row_count"] += 1
        if order_id:
            bucket["order_ids"].add(order_id)
        if purchase:
            _update_dates(bucket, purchase, now)
        sales_channel = _text(row.get("sales_channel"))
        if sales_channel:
            bucket["sales_channels"][sales_channel] += 1
    return stats


def _joined_order_stats(
    rows: list[dict[str, str]],
    orders_by_id: dict[str, dict[str, str]],
    order_column: str,
) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = defaultdict(_new_stats)
    for row in rows:
        order_id = _text(row.get(order_column))
        market_id = _text(orders_by_id.get(order_id, {}).get("marketplace_id")) or "<missing_order>"
        bucket = stats[market_id]
        bucket["row_count"] += 1
        if order_id:
            bucket["order_ids"].add(order_id)
    return stats


def _level1_stats(rows: list[dict[str, str]], orders_by_id: dict[str, dict[str, str]]) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = defaultdict(_new_stats)
    for row in rows:
        order_id = _text(row.get("Order ID"))
        market_id = _text(row.get("marketplace_id")) or _text(orders_by_id.get(order_id, {}).get("marketplace_id")) or "<blank>"
        bucket = stats[market_id]
        bucket["row_count"] += 1
        if order_id:
            bucket["order_ids"].add(order_id)
    return stats


def _refund_stats(rows: list[dict[str, str]], orders_by_id: dict[str, dict[str, str]]) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = defaultdict(_new_stats)
    for row in rows:
        order_id = _text(row.get("order_id") or row.get("Order ID") or row.get("amazon_order_id"))
        market_id = _text(orders_by_id.get(order_id, {}).get("marketplace_id")) or "<missing_order>"
        bucket = stats[market_id]
        bucket["row_count"] += 1
        if order_id:
            bucket["order_ids"].add(order_id)
    return stats


def _api_proved_quarantine_order_ids(rows: list[dict[str, str]]) -> set[str]:
    return {
        _text(row.get("amazon_order_id") or row.get("AmazonOrderId") or row.get("order_id"))
        for row in rows
        if _text(row.get("proof_label")) == "API proved"
    }


def _sellerboard_stats(
    rows: list[dict[str, str]],
    orders_by_id: dict[str, dict[str, str]],
    channel_to_marketplace: dict[str, str],
    marker_dt: datetime | None,
    api_proved_quarantine_ids: set[str],
) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = defaultdict(_new_stats)
    for row in rows:
        channel = _text(row.get("sellerboard_sales_channel"))
        order_id = _text(row.get("amazon_order_id"))
        local_market = _text(row.get("local_marketplace_id")) or _text(orders_by_id.get(order_id, {}).get("marketplace_id"))
        market_id = local_market or channel_to_marketplace.get(channel.lower()) or f"sellerboard:{channel or 'unknown'}"
        bucket = stats[market_id]
        bucket["row_count"] += 1
        if order_id:
            bucket["order_ids"].add(order_id)
        if channel:
            bucket["sales_channels"][channel] += 1
        status = _status(row.get("sellerboard_status"))
        if status == "shipped":
            bucket["sellerboard_shipped"] += 1
        if row.get("match_status") == "sellerboard_shipped_missing_in_sellerone":
            if order_id in api_proved_quarantine_ids:
                bucket["sellerboard_api_proved_quarantine"] += 1
            else:
                bucket["sellerboard_missing_shipped"] += 1
            purchase = parse_utc(_text(row.get("sellerboard_purchase_utc")))
            if order_id not in api_proved_quarantine_ids and marker_dt and purchase and marker_dt > purchase:
                bucket["shared_cursor_risk"] += 1
        if row.get("match_status") == "status_difference":
            bucket["sellerboard_status_difference"] += 1
        if status == "shipped" and not _text(row.get("mapped_sku")):
            bucket["sellerboard_unmapped_shipped"] += 1
    return stats


def _new_stats() -> dict[str, Any]:
    return {
        "row_count": 0,
        "order_ids": set(),
        "first_dt": None,
        "latest_dt": None,
        "latest_age_days": "",
        "sales_channels": Counter(),
        "sellerboard_shipped": 0,
        "sellerboard_missing_shipped": 0,
        "sellerboard_api_proved_quarantine": 0,
        "sellerboard_status_difference": 0,
        "sellerboard_unmapped_shipped": 0,
        "shared_cursor_risk": 0,
    }


def _update_dates(bucket: dict[str, Any], purchase: datetime, now: datetime) -> None:
    first = bucket.get("first_dt")
    latest = bucket.get("latest_dt")
    if first is None or purchase < first:
        bucket["first_dt"] = purchase
    if latest is None or purchase > latest:
        bucket["latest_dt"] = purchase
        bucket["latest_age_days"] = f"{max((now - purchase).total_seconds() / 86400.0, 0.0):.2f}"


def _coverage_row(
    *,
    observed: str,
    market_id: str,
    marketplaces: dict[str, dict[str, str]],
    order_stats: dict[str, dict[str, Any]],
    item_stats: dict[str, dict[str, Any]],
    level1_stats: dict[str, dict[str, Any]],
    master_stats: dict[str, dict[str, Any]],
    level3_stats: dict[str, dict[str, Any]],
    refund_stats: dict[str, dict[str, Any]],
    sellerboard_stats: dict[str, dict[str, Any]],
) -> dict[str, str]:
    market = marketplaces.get(market_id, {})
    orders = order_stats.get(market_id, _new_stats())
    items = item_stats.get(market_id, _new_stats())
    level1 = level1_stats.get(market_id, _new_stats())
    master = master_stats.get(market_id, _new_stats())
    level3 = level3_stats.get(market_id, _new_stats())
    refunds = refund_stats.get(market_id, _new_stats())
    sellerboard = sellerboard_stats.get(market_id, _new_stats())
    status, proof_label, manager_label, next_step, notes = _coverage_status(
        market_id,
        market,
        orders,
        items,
        level1,
        master,
        sellerboard,
    )
    return {
        "observed_utc": observed,
        "marketplace_id": market_id,
        "marketplace_name": market.get("marketplace_name", ""),
        "country_code": market.get("country_code", ""),
        "sales_channel": _top_sales_channel(orders, sellerboard),
        "participating": "1" if market else "0",
        "local_order_rows": str(int(orders.get("row_count", 0))),
        "local_first_order_utc": _iso_or_blank(orders.get("first_dt")),
        "local_latest_order_utc": _iso_or_blank(orders.get("latest_dt")),
        "local_latest_order_age_days": str(orders.get("latest_age_days", "")),
        "local_item_order_count": str(len(items.get("order_ids", set()))),
        "local_item_rows": str(int(items.get("row_count", 0))),
        "level1_order_count": str(len(level1.get("order_ids", set()))),
        "order_master_order_count": str(len(master.get("order_ids", set()))),
        "level3_order_count": str(len(level3.get("order_ids", set()))),
        "refund_order_count": str(len(refunds.get("order_ids", set()))),
        "sellerboard_rows": str(int(sellerboard.get("row_count", 0))),
        "sellerboard_shipped_rows": str(int(sellerboard.get("sellerboard_shipped", 0))),
        "sellerboard_missing_shipped_orders": str(int(sellerboard.get("sellerboard_missing_shipped", 0))),
        "sellerboard_api_proved_quarantine_orders": str(int(sellerboard.get("sellerboard_api_proved_quarantine", 0))),
        "sellerboard_unrecovered_shipped_orders": str(int(sellerboard.get("sellerboard_missing_shipped", 0))),
        "sellerboard_status_difference_rows": str(int(sellerboard.get("sellerboard_status_difference", 0))),
        "sellerboard_unmapped_shipped_rows": str(int(sellerboard.get("sellerboard_unmapped_shipped", 0))),
        "shared_cursor_risk": str(int(sellerboard.get("shared_cursor_risk", 0))),
        "coverage_status": status,
        "proof_label": proof_label,
        "manager_coverage_label": manager_label,
        "manager_next_step": next_step,
        "notes": notes,
    }


def _coverage_status(
    market_id: str,
    market: dict[str, str],
    orders: dict[str, Any],
    items: dict[str, Any],
    level1: dict[str, Any],
    master: dict[str, Any],
    sellerboard: dict[str, Any],
) -> tuple[str, str, str, str, str]:
    order_rows = int(orders.get("row_count", 0))
    item_orders = len(items.get("order_ids", set()))
    sellerboard_rows = int(sellerboard.get("row_count", 0))
    sellerboard_shipped = int(sellerboard.get("sellerboard_shipped", 0))
    missing_shipped = int(sellerboard.get("sellerboard_missing_shipped", 0))
    api_proved_quarantine = int(sellerboard.get("sellerboard_api_proved_quarantine", 0))
    status_diff = int(sellerboard.get("sellerboard_status_difference", 0))
    shared_cursor = int(sellerboard.get("shared_cursor_risk", 0))
    if market_id == "sellerboard:unknown" and sellerboard_rows:
        return (
            "not_checked",
            "not yet proven",
            "not_yet_proven",
            "Map Sellerboard sales channel before judging marketplace coverage.",
            "Sellerboard bridge rows do not yet expose a marketplace sales channel.",
        )
    if missing_shipped:
        return (
            "fail",
            "not yet proven",
            "missing_shipped_order_gap",
            "Create a bounded recovery task; do not backfill or promote from this report.",
            f"Sellerboard has {missing_shipped} shipped order(s) missing from local B proof."
            + (" Shared cursor risk is visible." if shared_cursor else ""),
        )
    if sellerboard_shipped and order_rows == 0:
        return (
            "fail",
            "not yet proven",
            "missing_marketplace_local_orders",
            "Create a bounded recovery task; do not backfill or promote from this report.",
            "Sellerboard has shipped activity but local B has no orders for this marketplace.",
        )
    if order_rows and item_orders == 0:
        return (
            "warn",
            "not yet proven",
            "warning_labelled_item_gap",
            "Create a bounded item-proof task if this warning persists.",
            "Local orders exist but no matching item rows were found for this marketplace.",
        )
    if order_rows and len(level1.get("order_ids", set())) == 0 and len(master.get("order_ids", set())) == 0:
        return (
            "warn",
            "not yet proven",
            "warning_labelled_downstream_proof_gap",
            "Create a bounded downstream-proof task if this warning persists.",
            "Local orders exist but no level 1 or order-master proof was found.",
        )
    if status_diff:
        return (
            "warn",
            "not yet proven",
            "warning_labelled_status_difference",
            "Compare Sellerboard status rows only; do not recover or rewrite orders from this warning.",
            f"Sellerboard and local B status differ on {status_diff} row(s).",
        )
    if api_proved_quarantine:
        return (
            "ok",
            "API proved",
            "checked_api_proved_in_quarantine",
            "Keep quarantined until a separately approved promotion window.",
            "Sellerboard missing order activity is API-proved in recovery quarantine.",
        )
    if sellerboard_rows:
        return (
            "ok",
            "API proved",
            "checked_api_proved",
            "Keep under daily comparison.",
            "Sellerboard activity is matched to local B proof.",
        )
    if order_rows:
        if market_id in {"A1F83G8C2ARO7P", "A28R8C7NBKEWEA"}:
            return (
                "ok",
                "API proved",
                "checked_local_api_proved",
                "Keep under daily comparison.",
                "Local B proof has recent marketplace activity.",
            )
        return (
            "not_checked",
            "not yet proven",
            "skipped_no_current_sellerboard_check",
            "Keep per-market cursor proof active; outside Sellerboard proof is absent for this quiet marketplace.",
            "Local history exists, but no current Sellerboard outside check is present.",
        )
    if market and market.get("marketplace_name", "").lower().startswith("non-amazon"):
        return (
            "not_checked",
            "not yet proven",
            "unsupported_non_amazon_no_activity",
            "Do not treat this as an Amazon API gap unless local or Sellerboard activity appears.",
            "Non-Amazon marketplace has no local or Sellerboard activity in the current proof.",
        )
    return (
        "not_checked",
        "not yet proven",
        "skipped_no_current_activity",
        "Keep per-market cursor proof active; no recovery task is needed without activity.",
        "No local or Sellerboard activity was available for this marketplace in the current proof.",
    )


def _top_sales_channel(*stats: dict[str, Any]) -> str:
    combined: Counter[str] = Counter()
    for stat in stats:
        combined.update(stat.get("sales_channels", Counter()))
    if not combined:
        return ""
    return combined.most_common(1)[0][0]


def _iso_or_blank(value: Any) -> str:
    if not isinstance(value, datetime):
        return ""
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _overall_status(coverage_rows: list[dict[str, str]], orders: list[dict[str, str]], sellerboard: list[dict[str, str]]) -> str:
    if not orders and not sellerboard:
        return "not_checked"
    if any(row["coverage_status"] == "fail" for row in coverage_rows):
        return "fail"
    if any(row["coverage_status"] == "warn" for row in coverage_rows):
        return "warn"
    return "ok"


def _summary_rows(
    *,
    observed: str,
    status: str,
    coverage_rows: list[dict[str, str]],
    marketplaces: dict[str, dict[str, str]],
    orders: list[dict[str, str]],
    sellerboard: list[dict[str, str]],
    marker_dt: datetime | None,
    source_path: Path,
) -> list[dict[str, str]]:
    def metric(name: str, value: Any, row_status: str, label: str, notes: str = "") -> dict[str, str]:
        return {
            "observed_utc": observed,
            "metric": name,
            "status": row_status,
            "value": str(value),
            "proof_label": label,
            "notes": notes,
            "source_path": str(source_path),
        }

    fail_rows = [row for row in coverage_rows if row["coverage_status"] == "fail"]
    warn_rows = [row for row in coverage_rows if row["coverage_status"] == "warn"]
    warning_labels = Counter(row.get("manager_coverage_label", "") for row in warn_rows)
    missing_shipped = sum(_to_int(row["sellerboard_missing_shipped_orders"]) for row in coverage_rows)
    api_proved_quarantine = sum(_to_int(row["sellerboard_api_proved_quarantine_orders"]) for row in coverage_rows)
    cursor_risk = sum(_to_int(row["shared_cursor_risk"]) for row in coverage_rows)
    sellerboard_marketplaces = sum(1 for row in coverage_rows if _to_int(row["sellerboard_rows"]) > 0)
    local_marketplaces = sum(1 for row in coverage_rows if _to_int(row["local_order_rows"]) > 0)
    return [
        metric("overall_status", status, status, "not yet proven" if status == "fail" else "API proved"),
        metric("participating_marketplaces", len(marketplaces), "ok" if marketplaces else "not_checked", "API proved" if marketplaces else "not yet proven"),
        metric("local_order_marketplaces", local_marketplaces, "ok" if orders else "not_checked", "API proved" if orders else "not yet proven"),
        metric("sellerboard_marketplaces", sellerboard_marketplaces, "ok" if sellerboard else "not_checked", "Sellerboard bridge estimate" if sellerboard else "not yet proven"),
        metric("sellerboard_missing_shipped_orders", missing_shipped, "fail" if missing_shipped else "ok", "not yet proven" if missing_shipped else "API proved"),
        metric("sellerboard_api_proved_quarantine_orders", api_proved_quarantine, "ok", "API proved" if api_proved_quarantine else "not yet proven"),
        metric("marketplace_fail_rows", len(fail_rows), "fail" if fail_rows else "ok", "not yet proven" if fail_rows else "API proved"),
        metric(
            "marketplace_warn_rows",
            len(warn_rows),
            "warn" if warn_rows else "ok",
            "not yet proven" if warn_rows else "API proved",
            ";".join(f"{key}={value}" for key, value in sorted(warning_labels.items()) if key),
        ),
        metric(
            "marketplace_status_difference_warn_rows",
            warning_labels.get("warning_labelled_status_difference", 0),
            "warn" if warning_labels.get("warning_labelled_status_difference", 0) else "ok",
            "not yet proven" if warning_labels.get("warning_labelled_status_difference", 0) else "API proved",
            "Sellerboard/local status comparison warning only; no shipped order is missing.",
        ),
        metric("shared_cursor_risk_rows", cursor_risk, "fail" if cursor_risk else "ok", "not yet proven" if cursor_risk else "API proved", "UK/global marker may have advanced past missing non-UK activity." if cursor_risk else ""),
        metric("orders_marker_utc", _iso_or_blank(marker_dt), "ok" if marker_dt else "not_checked", "API proved" if marker_dt else "not yet proven"),
    ]


def _to_int(value: str) -> int:
    try:
        return int(float(value or "0"))
    except ValueError:
        return 0


def _summary_json(result: MarketplaceCoverageResult) -> dict[str, Any]:
    metrics = {row["metric"]: row["value"] for row in result.summary_rows}
    return {
        "observed_utc": result.observed_utc,
        "status": result.status,
        "metrics": metrics,
        "source_paths": [str(path) for path in result.source_paths],
    }


def _markdown(result: MarketplaceCoverageResult) -> str:
    metrics = {row["metric"]: row["value"] for row in result.summary_rows}
    lines = [
        "# B Marketplace Coverage",
        "",
        f"Observed UTC: {result.observed_utc}",
        f"Status: {result.status}",
        "",
        "## Summary",
        f"- Participating marketplaces: {metrics.get('participating_marketplaces', '0')}",
        f"- Local order marketplaces: {metrics.get('local_order_marketplaces', '0')}",
        f"- Sellerboard marketplaces: {metrics.get('sellerboard_marketplaces', '0')}",
        f"- Sellerboard shipped orders missing locally: {metrics.get('sellerboard_missing_shipped_orders', '0')}",
        f"- Shared cursor risk rows: {metrics.get('shared_cursor_risk_rows', '0')}",
        "",
        "## Problem Rows",
    ]
    problem_rows = [row for row in result.coverage_rows if row["coverage_status"] in {"fail", "warn"}]
    if not problem_rows:
        lines.append("- None")
    else:
        for row in problem_rows:
            lines.append(
                f"- {row['marketplace_id']} {row['sales_channel']}: {row['coverage_status']} - {row['notes']}"
            )
    lines.extend(
        [
            "",
            "## Safety",
            "- This report is read-only.",
            "- It did not run B.",
            "- It did not write Sheets, change orders, edit markers, change locks, change prices, or edit queues.",
        ]
    )
    return "\n".join(lines) + "\n"
