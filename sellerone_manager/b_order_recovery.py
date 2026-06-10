from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import get_manager_paths
from .sellerboard_bridge import ORDER_RECONCILIATION_NAME


RECOVERY_DIR_NAME = "b_order_recovery"
MARKETPLACE_PLAN_CSV_NAME = "b_order_recovery_marketplace_plan.csv"
SUMMARY_CSV_NAME = "b_order_recovery_summary.csv"
SUMMARY_JSON_NAME = "b_order_recovery_summary.json"
MARKDOWN_NAME = "b_order_recovery_latest.md"

RECOVERY_START_UTC = "2025-11-01T00:00:00Z"
CURSOR_FRESH_HOURS = 30.0

EXPECTED_CURSOR_REL_PATH = "out/systems/B/order_cursors/b_marketplace_order_cursors.csv"
EXPECTED_QUARANTINE_REL_PATH = "out/systems/B/recovery_quarantine/b_order_recovery_quarantine.csv"

ALLOWED_PROOF_LABELS = {"API proved", "Sellerboard bridge estimate", "not yet proven"}

MARKETPLACE_PLAN_COLUMNS = [
    "observed_utc",
    "marketplace_id",
    "marketplace_name",
    "country_code",
    "sales_channel",
    "is_amazon_marketplace",
    "participating",
    "backdate_start_utc",
    "shared_marker_utc",
    "local_order_rows",
    "local_latest_order_utc",
    "sellerboard_missing_order_count",
    "sellerboard_missing_order_ids",
    "quarantine_api_proved_order_count",
    "quarantine_estimate_order_count",
    "future_cursor_state",
    "future_cursor_utc",
    "future_cursor_age_hours",
    "duplicate_risk_orders",
    "merge_ready_without_approval_orders",
    "recovery_status",
    "proof_label",
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

QUARANTINE_REQUIRED_COLUMNS = [
    "amazon_order_id",
    "marketplace_id",
    "purchase_utc",
    "order_status",
    "sku",
    "asin",
    "order_item_ids",
    "quantity",
    "currency",
    "order_total",
    "last_update_utc",
    "sales_channel",
    "fulfillment_channel",
    "order_payload_json",
    "items_payload_json",
    "source",
    "proof_label",
    "duplicate_state",
    "ready_for_live_merge",
]


@dataclass(frozen=True)
class BOrderRecoveryResult:
    observed_utc: str
    status: str
    plan_rows: list[dict[str, str]]
    summary_rows: list[dict[str, str]]
    source_paths: list[Path]


def build_b_order_recovery_plan(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
) -> BOrderRecoveryResult:
    paths = get_manager_paths(root)
    base = paths.root
    observed = observed_utc or utc_now_text()
    now = parse_utc(observed) or datetime.now(timezone.utc)

    marketplace_path = base / "out" / "marketplace_participations.csv"
    orders_path = base / "out" / "orders_all.csv"
    marker_path = base / "out" / "orders_last_updated.txt"
    sellerboard_path = base / "out" / "systems" / "M" / "sellerboard_bridge" / ORDER_RECONCILIATION_NAME
    cursor_path = base / EXPECTED_CURSOR_REL_PATH
    quarantine_path = base / EXPECTED_QUARANTINE_REL_PATH

    marketplaces = _load_marketplaces(marketplace_path)
    orders = _read_csv_rows(orders_path)
    sellerboard = _read_csv_rows(sellerboard_path)
    cursors = _read_csv_rows(cursor_path)
    quarantine = _read_csv_rows(quarantine_path)

    marker_utc = _read_marker(marker_path)
    order_stats = _order_stats(orders)
    local_order_ids = {_text(row.get("amazon_order_id")) for row in orders if _text(row.get("amazon_order_id"))}
    channel_to_marketplace = _sales_channel_map(marketplaces)
    missing_by_marketplace = _sellerboard_missing_by_marketplace(sellerboard, channel_to_marketplace)
    quarantine_by_order = _quarantine_by_order(quarantine)
    cursor_by_marketplace = _cursor_by_marketplace(cursors)

    marketplace_ids = set(marketplaces) | set(order_stats) | set(missing_by_marketplace) | set(cursor_by_marketplace)
    plan_rows = [
        _marketplace_row(
            observed=observed,
            now=now,
            marketplace_id=marketplace_id,
            marketplaces=marketplaces,
            order_stats=order_stats,
            missing_by_marketplace=missing_by_marketplace,
            quarantine_by_order=quarantine_by_order,
            local_order_ids=local_order_ids,
            cursor_by_marketplace=cursor_by_marketplace,
            marker_utc=marker_utc,
        )
        for marketplace_id in sorted(marketplace_ids, key=lambda value: (value.startswith("sellerboard:"), value))
    ]
    status = _overall_status(plan_rows, marketplaces, missing_by_marketplace)
    summary_rows = _summary_rows(
        observed=observed,
        status=status,
        plan_rows=plan_rows,
        marketplaces=marketplaces,
        sellerboard=sellerboard,
        quarantine=quarantine,
        quarantine_path=quarantine_path,
        cursor_path=cursor_path,
        marker_path=marker_path,
    )
    return BOrderRecoveryResult(
        observed_utc=observed,
        status=status,
        plan_rows=plan_rows,
        summary_rows=summary_rows,
        source_paths=[
            marketplace_path,
            orders_path,
            marker_path,
            sellerboard_path,
            cursor_path,
            quarantine_path,
        ],
    )


def write_b_order_recovery_outputs(result: BOrderRecoveryResult, output_dir: Path) -> dict[str, Path]:
    out_dir = output_dir / RECOVERY_DIR_NAME
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "marketplace_plan_csv": out_dir / MARKETPLACE_PLAN_CSV_NAME,
        "summary_csv": out_dir / SUMMARY_CSV_NAME,
        "summary_json": out_dir / SUMMARY_JSON_NAME,
        "markdown": out_dir / MARKDOWN_NAME,
    }
    _write_csv(paths["marketplace_plan_csv"], MARKETPLACE_PLAN_COLUMNS, result.plan_rows)
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
    text = str(value or "").strip()
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
    out: dict[str, dict[str, str]] = {}
    for row in _read_csv_rows(path):
        marketplace_id = _text(row.get("marketplace_id"))
        if not marketplace_id:
            continue
        out[marketplace_id] = {
            "marketplace_id": marketplace_id,
            "marketplace_name": _text(row.get("name")),
            "country_code": _text(row.get("country_code")),
            "domain_name": _text(row.get("domain_name")),
            "participating": _text(row.get("is_participating") or "1") or "1",
        }
    return out


def _sales_channel_map(marketplaces: dict[str, dict[str, str]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for marketplace_id, row in marketplaces.items():
        for key in ("marketplace_name", "domain_name"):
            value = _text(row.get(key))
            if value:
                out[value.lower()] = marketplace_id
        name = _text(row.get("marketplace_name")).lower()
        if name.startswith("non-amazon"):
            out["non-amazon"] = marketplace_id
    return out


def _read_marker(path: Path) -> str:
    try:
        return _iso_or_blank(parse_utc(path.read_text(encoding="utf-8").strip()))
    except OSError:
        return ""


def _order_stats(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"rows": 0, "latest": None, "channels": Counter()})
    for row in rows:
        marketplace_id = _text(row.get("marketplace_id"))
        if not marketplace_id:
            continue
        bucket = stats[marketplace_id]
        bucket["rows"] += 1
        purchase = parse_utc(row.get("purchase_date"))
        if purchase and (bucket["latest"] is None or purchase > bucket["latest"]):
            bucket["latest"] = purchase
        channel = _text(row.get("sales_channel"))
        if channel:
            bucket["channels"][channel] += 1
    return stats


def _sellerboard_missing_by_marketplace(
    rows: list[dict[str, str]],
    channel_to_marketplace: dict[str, str],
) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if _status(row.get("match_status")) != "sellerboard_shipped_missing_in_sellerone":
            continue
        channel = _text(row.get("sellerboard_sales_channel"))
        marketplace_id = _text(row.get("local_marketplace_id")) or channel_to_marketplace.get(channel.lower())
        if not marketplace_id:
            marketplace_id = f"sellerboard:{channel or 'unknown'}"
        out[marketplace_id].append(row)
    return out


def _quarantine_by_order(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        order_id = _text(row.get("amazon_order_id") or row.get("AmazonOrderId") or row.get("order_id"))
        if order_id:
            out[order_id].append(row)
    return out


def _cursor_by_marketplace(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        marketplace_id = _text(row.get("marketplace_id"))
        if marketplace_id and marketplace_id not in out:
            out[marketplace_id] = row
    return out


def _marketplace_row(
    *,
    observed: str,
    now: datetime,
    marketplace_id: str,
    marketplaces: dict[str, dict[str, str]],
    order_stats: dict[str, dict[str, Any]],
    missing_by_marketplace: dict[str, list[dict[str, str]]],
    quarantine_by_order: dict[str, list[dict[str, str]]],
    local_order_ids: set[str],
    cursor_by_marketplace: dict[str, dict[str, str]],
    marker_utc: str,
) -> dict[str, str]:
    market = marketplaces.get(marketplace_id, {})
    stats = order_stats.get(marketplace_id, {})
    missing_rows = missing_by_marketplace.get(marketplace_id, [])
    missing_ids = [_text(row.get("amazon_order_id")) for row in missing_rows if _text(row.get("amazon_order_id"))]
    recovered_api = 0
    recovered_estimate = 0
    duplicate_risk = 0
    merge_ready = 0
    for order_id in missing_ids:
        quarantine_rows = quarantine_by_order.get(order_id, [])
        if any(_text(row.get("proof_label")) == "API proved" for row in quarantine_rows):
            recovered_api += 1
        if any(_text(row.get("proof_label")) == "Sellerboard bridge estimate" for row in quarantine_rows):
            recovered_estimate += 1
        if order_id in local_order_ids or len(quarantine_rows) > 1:
            duplicate_risk += 1
        if any(_looks_merge_ready(row) for row in quarantine_rows):
            merge_ready += 1
    cursor_state, cursor_utc, cursor_age = _cursor_state(
        cursor_by_marketplace.get(marketplace_id, {}),
        now=now,
        required=_is_amazon_marketplace(marketplace_id, market),
    )
    status, label, notes = _row_status(
        marketplace_id=marketplace_id,
        market=market,
        missing_count=len(missing_ids),
        recovered_api=recovered_api,
        cursor_state=cursor_state,
        duplicate_risk=duplicate_risk,
        merge_ready=merge_ready,
    )
    return {
        "observed_utc": observed,
        "marketplace_id": marketplace_id,
        "marketplace_name": _text(market.get("marketplace_name")),
        "country_code": _text(market.get("country_code")),
        "sales_channel": _top_channel(stats, missing_rows),
        "is_amazon_marketplace": "1" if _is_amazon_marketplace(marketplace_id, market) else "0",
        "participating": "1" if market else "0",
        "backdate_start_utc": RECOVERY_START_UTC,
        "shared_marker_utc": marker_utc,
        "local_order_rows": str(int(stats.get("rows", 0) or 0)),
        "local_latest_order_utc": _iso_or_blank(stats.get("latest")),
        "sellerboard_missing_order_count": str(len(missing_ids)),
        "sellerboard_missing_order_ids": ";".join(missing_ids[:25]),
        "quarantine_api_proved_order_count": str(recovered_api),
        "quarantine_estimate_order_count": str(recovered_estimate),
        "future_cursor_state": cursor_state,
        "future_cursor_utc": cursor_utc,
        "future_cursor_age_hours": cursor_age,
        "duplicate_risk_orders": str(duplicate_risk),
        "merge_ready_without_approval_orders": str(merge_ready),
        "recovery_status": status,
        "proof_label": label,
        "notes": notes,
    }


def _top_channel(stats: dict[str, Any], missing_rows: list[dict[str, str]]) -> str:
    channels = Counter(stats.get("channels", Counter()))
    for row in missing_rows:
        channel = _text(row.get("sellerboard_sales_channel"))
        if channel:
            channels[channel] += 1
    if not channels:
        return ""
    return channels.most_common(1)[0][0]


def _is_amazon_marketplace(marketplace_id: str, market: dict[str, str]) -> bool:
    if marketplace_id.startswith("sellerboard:"):
        return "amazon." in marketplace_id.lower()
    name = _text(market.get("marketplace_name")).lower()
    domain = _text(market.get("domain_name")).lower()
    if name.startswith("non-amazon"):
        return False
    return "amazon" in name or "amazon." in domain


def _cursor_state(cursor_row: dict[str, str], *, now: datetime, required: bool) -> tuple[str, str, str]:
    if not required:
        return ("not_required", "", "")
    if not cursor_row:
        return ("missing", "", "")
    proof_status = _status(cursor_row.get("status"))
    if proof_status in {"fail", "failed", "error", "partial_page_limit"}:
        return (proof_status or "fail", "", "")
    if proof_status in {"unsupported", "skipped", "skipped_with_reason"}:
        return (proof_status, _text(cursor_row.get("last_success_utc") or cursor_row.get("last_checked_utc") or cursor_row.get("cursor_utc")), "")
    cursor_utc = (
        _text(cursor_row.get("last_success_utc"))
        or _text(cursor_row.get("last_checked_utc"))
        or _text(cursor_row.get("cursor_utc"))
    )
    parsed = parse_utc(cursor_utc)
    if not parsed:
        return ("missing_timestamp", cursor_utc, "")
    age = max((now - parsed).total_seconds() / 3600.0, 0.0)
    state = "fresh" if age <= CURSOR_FRESH_HOURS else "stale"
    return (state, _iso_or_blank(parsed), f"{age:.2f}")


def _looks_merge_ready(row: dict[str, str]) -> bool:
    values = [
        _status(row.get("ready_for_live_merge")),
        _status(row.get("live_merge_state")),
        _status(row.get("merge_state")),
    ]
    return any(value in {"1", "yes", "true", "ready", "applied", "merged"} for value in values)


def _row_status(
    *,
    marketplace_id: str,
    market: dict[str, str],
    missing_count: int,
    recovered_api: int,
    cursor_state: str,
    duplicate_risk: int,
    merge_ready: int,
) -> tuple[str, str, str]:
    if merge_ready:
        return ("decision_needed", "not yet proven", "Recovered data appears ready for live merge, which needs Luke approval.")
    if duplicate_risk:
        return ("fail", "not yet proven", "Quarantine proof has duplicate risk before any merge can be considered.")
    if missing_count and recovered_api < missing_count:
        return ("fail", "not yet proven", "Sellerboard shows shipped orders that are not API-proved in quarantine.")
    if cursor_state in {"missing", "missing_timestamp", "stale", "fail", "failed", "error", "partial_page_limit"}:
        return ("fail", "not yet proven", "This Amazon marketplace does not have fresh per-marketplace cursor proof.")
    if not market and marketplace_id.startswith("sellerboard:"):
        return ("fail", "not yet proven", "Sellerboard showed activity for a marketplace that is not mapped to participation proof.")
    if cursor_state == "fresh" or recovered_api:
        return ("ok", "API proved", "Marketplace has independent future cursor proof and no unrecovered Sellerboard shipped gap.")
    return ("not_checked", "not yet proven", "No current recovery or cursor proof is available for this marketplace.")


def _overall_status(
    plan_rows: list[dict[str, str]],
    marketplaces: dict[str, dict[str, str]],
    missing_by_marketplace: dict[str, list[dict[str, str]]],
) -> str:
    if any(row["recovery_status"] == "decision_needed" for row in plan_rows):
        return "decision_needed"
    if any(row["recovery_status"] == "fail" for row in plan_rows):
        return "fail"
    if not marketplaces and not missing_by_marketplace:
        return "not_checked"
    if any(row["recovery_status"] == "ok" for row in plan_rows):
        return "ok"
    return "not_checked"


def _summary_rows(
    *,
    observed: str,
    status: str,
    plan_rows: list[dict[str, str]],
    marketplaces: dict[str, dict[str, str]],
    sellerboard: list[dict[str, str]],
    quarantine: list[dict[str, str]],
    quarantine_path: Path,
    cursor_path: Path,
    marker_path: Path,
) -> list[dict[str, str]]:
    source_path = str(quarantine_path)

    def metric(name: str, value: Any, row_status: str, label: str, notes: str = "", source: Path | str | None = None) -> dict[str, str]:
        return {
            "observed_utc": observed,
            "metric": name,
            "status": row_status,
            "value": str(value),
            "proof_label": label,
            "notes": notes,
            "source_path": str(source or source_path),
        }

    amazon_rows = [row for row in plan_rows if row.get("is_amazon_marketplace") == "1"]
    cursor_missing = sum(1 for row in amazon_rows if row.get("future_cursor_state") in {"missing", "missing_timestamp", "fail", "failed", "error", "partial_page_limit"})
    cursor_stale = sum(1 for row in amazon_rows if row.get("future_cursor_state") == "stale")
    missing_orders = sum(_to_int(row.get("sellerboard_missing_order_count")) for row in plan_rows)
    api_recovered = sum(_to_int(row.get("quarantine_api_proved_order_count")) for row in plan_rows)
    unrecovered = sum(
        max(_to_int(row.get("sellerboard_missing_order_count")) - _to_int(row.get("quarantine_api_proved_order_count")), 0)
        for row in plan_rows
    )
    duplicate_risk = sum(_to_int(row.get("duplicate_risk_orders")) for row in plan_rows)
    merge_ready = sum(_to_int(row.get("merge_ready_without_approval_orders")) for row in plan_rows)
    invalid_labels = _invalid_quarantine_labels(quarantine)
    quarantine_missing_schema = _missing_quarantine_columns(quarantine_path)

    return [
        metric("overall_status", status, status, "not yet proven" if status in {"fail", "decision_needed"} else "API proved"),
        metric("backdate_start_utc", RECOVERY_START_UTC, "ok", "API proved", "Approved first recovery window start."),
        metric("participating_marketplaces", len(marketplaces), "ok" if marketplaces else "not_checked", "API proved" if marketplaces else "not yet proven"),
        metric("amazon_marketplaces_in_scope", len(amazon_rows), "ok" if amazon_rows else "not_checked", "API proved" if amazon_rows else "not yet proven"),
        metric("per_marketplace_cursor_missing_count", cursor_missing, "fail" if cursor_missing else "ok", "not yet proven" if cursor_missing else "API proved", source=cursor_path),
        metric("per_marketplace_cursor_stale_count", cursor_stale, "fail" if cursor_stale else "ok", "not yet proven" if cursor_stale else "API proved", source=cursor_path),
        metric("sellerboard_missing_orders", missing_orders, "fail" if missing_orders else "ok", "not yet proven" if missing_orders else "API proved"),
        metric("quarantine_rows", len(quarantine), "ok" if quarantine else "not_checked", "API proved" if quarantine else "not yet proven"),
        metric("quarantine_api_proved_missing_orders", api_recovered, "ok" if api_recovered or not missing_orders else "fail", "API proved" if api_recovered else "not yet proven"),
        metric("unrecovered_missing_sellerboard_orders", unrecovered, "fail" if unrecovered else "ok", "not yet proven" if unrecovered else "API proved"),
        metric("duplicate_risk_orders", duplicate_risk, "fail" if duplicate_risk else "ok", "not yet proven" if duplicate_risk else "API proved"),
        metric("merge_ready_without_approval_orders", merge_ready, "decision_needed" if merge_ready else "ok", "not yet proven" if merge_ready else "API proved"),
        metric("invalid_quarantine_proof_label_rows", invalid_labels, "fail" if invalid_labels else "ok", "not yet proven" if invalid_labels else "API proved"),
        metric("quarantine_required_columns_missing", len(quarantine_missing_schema), "fail" if quarantine_missing_schema else "ok" if quarantine_path.exists() else "not_checked", "not yet proven" if quarantine_missing_schema or not quarantine_path.exists() else "API proved", ";".join(quarantine_missing_schema[:20])),
        metric("sellerboard_reconciliation_rows", len(sellerboard), "ok" if sellerboard else "not_checked", "Sellerboard bridge estimate" if sellerboard else "not yet proven"),
        metric("shared_marker_path", marker_path, "ok" if marker_path.exists() else "not_checked", "API proved" if marker_path.exists() else "not yet proven", source=marker_path),
    ]


def _invalid_quarantine_labels(rows: list[dict[str, str]]) -> int:
    return sum(1 for row in rows if _text(row.get("proof_label")) and _text(row.get("proof_label")) not in ALLOWED_PROOF_LABELS)


def _missing_quarantine_columns(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
    except OSError:
        return QUARANTINE_REQUIRED_COLUMNS
    return [column for column in QUARANTINE_REQUIRED_COLUMNS if column not in headers]


def _to_int(value: Any) -> int:
    try:
        return int(float(str(value or "0")))
    except ValueError:
        return 0


def _iso_or_blank(value: Any) -> str:
    if not isinstance(value, datetime):
        return ""
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _summary_json(result: BOrderRecoveryResult) -> dict[str, Any]:
    return {
        "observed_utc": result.observed_utc,
        "status": result.status,
        "metrics": {row["metric"]: row["value"] for row in result.summary_rows},
        "source_paths": [str(path) for path in result.source_paths],
    }


def _markdown(result: BOrderRecoveryResult) -> str:
    metrics = {row["metric"]: row["value"] for row in result.summary_rows}
    problem_rows = [row for row in result.plan_rows if row["recovery_status"] in {"fail", "decision_needed"}]
    lines = [
        "# B Order Recovery Control",
        "",
        f"Observed UTC: {result.observed_utc}",
        f"Status: {result.status}",
        "",
        "## Plain English",
        "This is manager proof for backdating missing orders and preventing future marketplace gaps. It is read-only and keeps recovered orders quarantined until approval.",
        "",
        "## Summary",
        f"- Backdate start: {metrics.get('backdate_start_utc', RECOVERY_START_UTC)}",
        f"- Amazon marketplaces in scope: {metrics.get('amazon_marketplaces_in_scope', '0')}",
        f"- Missing per-marketplace cursors: {metrics.get('per_marketplace_cursor_missing_count', '0')}",
        f"- Stale per-marketplace cursors: {metrics.get('per_marketplace_cursor_stale_count', '0')}",
        f"- Sellerboard missing orders: {metrics.get('sellerboard_missing_orders', '0')}",
        f"- Unrecovered missing orders: {metrics.get('unrecovered_missing_sellerboard_orders', '0')}",
        f"- Duplicate-risk orders: {metrics.get('duplicate_risk_orders', '0')}",
        "",
        "## Problem Rows",
    ]
    if not problem_rows:
        lines.append("- None")
    else:
        for row in problem_rows[:20]:
            lines.append(
                f"- {row['marketplace_id']} {row['sales_channel']}: {row['recovery_status']} - {row['notes']}"
            )
    lines.extend(
        [
            "",
            "## Safety",
            "- This report did not run B.",
            "- This report did not call Amazon.",
            "- This report did not write Sheets.",
            "- This report did not edit markers, locks, orders, local DB facts, ROI, prices, or queues.",
        ]
    )
    return "\n".join(lines) + "\n"
