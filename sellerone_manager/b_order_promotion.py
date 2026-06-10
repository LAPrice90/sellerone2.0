from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from scripts.flows.B.B001_run_orders_to_sheet import (
    _compiled_items_dedupe_key,
    build_level1,
    flatten_items,
    flatten_orders,
)
from scripts.flows.B._finance_io import read_finance_frame, sync_csv_to_finance_table, table_for_path, write_finance_frame

from .b_order_recovery import EXPECTED_QUARANTINE_REL_PATH, QUARANTINE_REQUIRED_COLUMNS
from .paths import get_manager_paths


PROMOTION_DIR_NAME = "b_order_promotion"
PREVIEW_CSV_NAME = "b_order_promotion_preview.csv"
SUMMARY_CSV_NAME = "b_order_promotion_summary.csv"
MANIFEST_JSON_NAME = "b_order_promotion_manifest.json"
MARKDOWN_NAME = "b_order_promotion_latest.md"

LIVE_PROMOTION_ROOT_REL_PATH = "out/systems/B/order_promotion"
LIVE_MANIFEST_REL_PATH = f"{LIVE_PROMOTION_ROOT_REL_PATH}/{MANIFEST_JSON_NAME}"

ORDERS_ALL_REL_PATH = "out/orders_all.csv"
ITEMS_ALL_REL_PATH = "out/order_items_all.csv"
LEVEL1_REL_PATH = "out/financial_events_level1.csv"
ORDER_MASTER_REL_PATH = "out/order_master.csv"

PROMOTION_PREVIEW_COLUMNS = [
    "observed_utc",
    "amazon_order_id",
    "marketplace_id",
    "purchase_utc",
    "order_status",
    "sku",
    "asin",
    "order_item_ids",
    "quantity",
    "currency",
    "promotion_status",
    "proof_label",
    "live_order_present",
    "live_item_rows_present",
    "validation_errors",
    "notes",
]

SUMMARY_COLUMNS = [
    "observed_utc",
    "metric",
    "status",
    "value",
    "proof_label",
    "notes",
]


@dataclass(frozen=True)
class BOrderPromotionResult:
    observed_utc: str
    status: str
    preview_rows: list[dict[str, str]]
    summary_rows: list[dict[str, str]]
    manifest: dict[str, Any]


def build_b_order_promotion_plan(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
) -> BOrderPromotionResult:
    paths = get_manager_paths(root)
    base = paths.root
    observed = observed_utc or utc_now_text()

    quarantine_rows = _read_csv_rows(base / EXPECTED_QUARANTINE_REL_PATH)
    live_orders = _read_frame(base / ORDERS_ALL_REL_PATH)
    live_items = _read_frame(base / ITEMS_ALL_REL_PATH)
    manifest = _read_json(base / LIVE_MANIFEST_REL_PATH)

    grouped = _api_quarantine_rows_by_order(quarantine_rows)
    preview_rows = [
        _preview_row(
            observed=observed,
            row=row,
            live_orders=live_orders,
            live_items=live_items,
        )
        for _order_id, row in sorted(grouped.items())
    ]
    status = _overall_status(preview_rows)
    summary_rows = _summary_rows(observed=observed, status=status, preview_rows=preview_rows, manifest=manifest)
    return BOrderPromotionResult(
        observed_utc=observed,
        status=status,
        preview_rows=preview_rows,
        summary_rows=summary_rows,
        manifest=manifest,
    )


def apply_b_order_promotion(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
    approve_protected_promotion: bool = False,
    order_master_rebuilder: Callable[[Path], int] | None = None,
) -> BOrderPromotionResult:
    paths = get_manager_paths(root)
    base = paths.root
    observed = observed_utc or utc_now_text()
    preview = build_b_order_promotion_plan(root=base, observed_utc=observed)
    manifest_path = base / LIVE_MANIFEST_REL_PATH
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    if not approve_protected_promotion:
        manifest = _manifest(
            observed=observed,
            status="blocked",
            notes="Protected promotion approval flag was not supplied.",
            preview=preview,
        )
        _write_json(manifest_path, manifest)
        return _with_manifest(preview, manifest)

    if preview.status != "decision_needed":
        manifest = _manifest(
            observed=observed,
            status="blocked",
            notes=f"Promotion requires ready candidates only; current status is {preview.status}.",
            preview=preview,
        )
        _write_json(manifest_path, manifest)
        return _with_manifest(preview, manifest)

    if _active_b_lock_paths(base) and not _maintenance_ready_for_promotion(base):
        manifest = _manifest(
            observed=observed,
            status="blocked",
            notes="B owner lock is active. Promotion must wait for a protected repair window with B stopped or in maintenance.",
            preview=preview,
        )
        _write_json(manifest_path, manifest)
        return _with_manifest(preview, manifest)

    run_id = observed.replace(":", "").replace("-", "").replace("Z", "Z")
    promotion_root = base / LIVE_PROMOTION_ROOT_REL_PATH
    stage_dir = promotion_root / "staged" / run_id
    snapshot_dir = promotion_root / "snapshots" / run_id
    stage_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    affected = [
        base / ORDERS_ALL_REL_PATH,
        base / ITEMS_ALL_REL_PATH,
        base / LEVEL1_REL_PATH,
        base / ORDER_MASTER_REL_PATH,
    ]
    snapshots = _snapshot_files(affected, snapshot_dir)
    try:
        quarantine_rows = _read_csv_rows(base / EXPECTED_QUARANTINE_REL_PATH)
        ready_rows = [
            _api_quarantine_rows_by_order(quarantine_rows)[row["amazon_order_id"]]
            for row in preview.preview_rows
            if row.get("promotion_status") == "ready_pending_approval"
        ]
        staged = _build_staged_frames(base=base, ready_rows=ready_rows)
        _write_stage(stage_dir, staged)
        _validate_staged_outputs(staged=staged, preview_rows=preview.preview_rows)

        _write_live_frame(base, staged["orders_all"], ORDERS_ALL_REL_PATH)
        _write_live_frame(base, staged["order_items_all"], ITEMS_ALL_REL_PATH)
        _write_live_frame(base, staged["financial_events_level1"], LEVEL1_REL_PATH)

        rc = order_master_rebuilder(base) if order_master_rebuilder else _run_order_master_rebuild(base, stage_dir)
        if rc != 0:
            raise RuntimeError(f"order_master_rebuild_failed:{rc}")

        final_preview = build_b_order_promotion_plan(root=base, observed_utc=observed)
        promoted_orders = [
            row["amazon_order_id"]
            for row in final_preview.preview_rows
            if row.get("promotion_status") == "already_live"
        ]
        manifest = _manifest(
            observed=observed,
            status="promoted",
            notes="API-proved recovered orders promoted into local B order outputs.",
            preview=final_preview,
            promoted_orders=promoted_orders,
            stage_dir=stage_dir,
            snapshot_dir=snapshot_dir,
        )
        _write_json(manifest_path, manifest)
        return _with_manifest(final_preview, manifest)
    except Exception as exc:
        _restore_snapshots(snapshots)
        manifest = _manifest(
            observed=observed,
            status="rolled_back",
            notes=f"{exc.__class__.__name__}:{exc}",
            preview=preview,
            stage_dir=stage_dir,
            snapshot_dir=snapshot_dir,
        )
        _write_json(manifest_path, manifest)
        return _with_manifest(preview, manifest)


def write_b_order_promotion_outputs(result: BOrderPromotionResult, output_dir: Path) -> dict[str, Path]:
    out_dir = output_dir / PROMOTION_DIR_NAME
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "preview_csv": out_dir / PREVIEW_CSV_NAME,
        "summary_csv": out_dir / SUMMARY_CSV_NAME,
        "manifest_json": out_dir / MANIFEST_JSON_NAME,
        "markdown": out_dir / MARKDOWN_NAME,
    }
    _write_csv(paths["preview_csv"], PROMOTION_PREVIEW_COLUMNS, result.preview_rows)
    _write_csv(paths["summary_csv"], SUMMARY_COLUMNS, result.summary_rows)
    _write_json(paths["manifest_json"], result.manifest or _manifest(observed=result.observed_utc, status=result.status, notes="", preview=result))
    paths["markdown"].write_text(_markdown(result), encoding="utf-8")
    return paths


def utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _api_quarantine_rows_by_order(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        order_id = _text(row.get("amazon_order_id"))
        if not order_id or _text(row.get("proof_label")) != "API proved":
            continue
        if _text(row.get("ready_for_live_merge")).lower() in {"1", "yes", "true", "ready", "applied", "merged"}:
            continue
        out[order_id] = row
    return out


def _preview_row(
    *,
    observed: str,
    row: dict[str, str],
    live_orders: pd.DataFrame,
    live_items: pd.DataFrame,
) -> dict[str, str]:
    order_id = _text(row.get("amazon_order_id"))
    errors = _validation_errors(row)
    live_order_present = _live_order_present(live_orders, order_id)
    item_ids = _order_item_ids(row)
    live_item_count = _live_item_count(live_items, order_id, item_ids)
    if live_order_present and item_ids and live_item_count >= len(item_ids):
        status = "already_live"
        notes = "Order and required item rows are already present in live local B outputs."
    elif live_order_present or live_item_count:
        status = "blocked_duplicate_partial"
        notes = "Order is partly present in live local B outputs. This needs duplicate review before promotion."
    elif errors:
        status = "blocked_validation"
        notes = "Promotion proof is missing required API-backed order or item fields."
    else:
        status = "ready_pending_approval"
        notes = "Ready for protected live promotion only after Luke approves the repair window."
    return {
        "observed_utc": observed,
        "amazon_order_id": order_id,
        "marketplace_id": _text(row.get("marketplace_id")),
        "purchase_utc": _text(row.get("purchase_utc")),
        "order_status": _text(row.get("order_status")),
        "sku": _text(row.get("sku")),
        "asin": _text(row.get("asin")),
        "order_item_ids": ";".join(item_ids),
        "quantity": _text(row.get("quantity")),
        "currency": _text(row.get("currency")),
        "promotion_status": status,
        "proof_label": _text(row.get("proof_label")),
        "live_order_present": "1" if live_order_present else "0",
        "live_item_rows_present": str(live_item_count),
        "validation_errors": ";".join(errors),
        "notes": notes,
    }


def _validation_errors(row: dict[str, str]) -> list[str]:
    errors: list[str] = []
    required = ["amazon_order_id", "marketplace_id", "purchase_utc", "order_status", "sku", "asin", "quantity", "currency"]
    for field in required:
        if not _text(row.get(field)):
            errors.append(f"missing_{field}")
    if _text(row.get("proof_label")) != "API proved":
        errors.append("proof_label_not_api_proved")
    if not _order_item_ids(row):
        errors.append("missing_order_item_id")
    order_payload, items_payload = _payloads(row)
    if not order_payload:
        errors.append("missing_order_payload_json")
    if not items_payload:
        errors.append("missing_items_payload_json")
    for item in items_payload:
        if not _text(item.get("OrderItemId")):
            errors.append("item_missing_order_item_id")
        if not _text(item.get("SellerSKU")):
            errors.append("item_missing_sku")
        if not _text(item.get("ASIN")):
            errors.append("item_missing_asin")
    return sorted(set(errors))


def _payloads(row: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    order_payload = _json_obj(row.get("order_payload_json"))
    items_payload = _json_list(row.get("items_payload_json"))
    if not order_payload:
        order_payload = _fallback_order_payload(row)
    if not items_payload:
        fallback_item = _fallback_item_payload(row)
        items_payload = [fallback_item] if fallback_item else []
    return order_payload, items_payload


def _fallback_order_payload(row: dict[str, str]) -> dict[str, Any]:
    order_id = _text(row.get("amazon_order_id"))
    if not order_id:
        return {}
    return {
        "AmazonOrderId": order_id,
        "PurchaseDate": _text(row.get("purchase_utc")),
        "LastUpdateDate": _text(row.get("last_update_utc") or row.get("purchase_utc")),
        "OrderStatus": _text(row.get("order_status")),
        "MarketplaceId": _text(row.get("marketplace_id")),
        "SalesChannel": _text(row.get("sales_channel")),
        "FulfillmentChannel": _text(row.get("fulfillment_channel")),
        "OrderTotal": {"Amount": _text(row.get("order_total")), "CurrencyCode": _text(row.get("currency"))},
        "NumberOfItemsShipped": _text(row.get("quantity")),
        "NumberOfItemsUnshipped": "0",
    }


def _fallback_item_payload(row: dict[str, str]) -> dict[str, Any]:
    item_ids = _order_item_ids(row)
    sku = _split_first(row.get("sku"))
    asin = _split_first(row.get("asin"))
    if not item_ids or not sku or not asin:
        return {}
    return {
        "AmazonOrderId": _text(row.get("amazon_order_id")),
        "OrderItemId": item_ids[0],
        "ASIN": asin,
        "SellerSKU": sku,
        "QuantityOrdered": _text(row.get("quantity") or "1"),
        "QuantityShipped": _text(row.get("quantity") or "1") if _text(row.get("order_status")).lower() == "shipped" else "",
        "ItemPrice": {"Amount": _text(row.get("order_total")), "CurrencyCode": _text(row.get("currency"))},
    }


def _build_staged_frames(*, base: Path, ready_rows: list[dict[str, str]]) -> dict[str, pd.DataFrame]:
    order_payloads: list[dict[str, Any]] = []
    item_payloads: list[dict[str, Any]] = []
    for row in ready_rows:
        order_payload, items = _payloads(row)
        order_payloads.append(order_payload)
        item_payloads.extend(items)

    incoming_orders = flatten_orders(order_payloads).fillna("").astype(str)
    incoming_items = flatten_items(item_payloads).fillna("").astype(str)
    existing_orders = _read_frame(base / ORDERS_ALL_REL_PATH)
    existing_items = _read_frame(base / ITEMS_ALL_REL_PATH)
    orders_all = _merge_unique(existing_orders, incoming_orders, ["amazon_order_id"], ["purchase_date", "amazon_order_id"])
    incoming_items["_dedupe_key"] = _compiled_items_dedupe_key(incoming_items)
    if not existing_items.empty:
        existing_items = existing_items.copy()
        existing_items["_dedupe_key"] = _compiled_items_dedupe_key(existing_items)
    order_items_all = _merge_unique(existing_items, incoming_items, ["_dedupe_key"], ["amazon_order_id", "order_item_id"])
    if "_dedupe_key" in order_items_all.columns:
        order_items_all = order_items_all.drop(columns=["_dedupe_key"])
    level1 = build_level1(orders_all, order_items_all).fillna("").astype(str)
    return {
        "orders_all": orders_all.fillna("").astype(str),
        "order_items_all": order_items_all.fillna("").astype(str),
        "financial_events_level1": level1,
    }


def _merge_unique(existing: pd.DataFrame, incoming: pd.DataFrame, key_cols: list[str], sort_cols: list[str] | None = None) -> pd.DataFrame:
    if existing.empty:
        out = incoming.copy()
    else:
        all_cols = list(dict.fromkeys(list(existing.columns) + list(incoming.columns)))
        for col in all_cols:
            if col not in existing.columns:
                existing[col] = ""
            if col not in incoming.columns:
                incoming[col] = ""
        out = pd.concat([existing[all_cols], incoming[all_cols]], ignore_index=True)
    for col in key_cols:
        if col not in out.columns:
            out[col] = ""
    out = out.drop_duplicates(subset=key_cols, keep="last")
    if sort_cols:
        for col in sort_cols:
            if col not in out.columns:
                out[col] = ""
        out = out.sort_values(by=sort_cols)
    return out.fillna("").astype(str)


def _validate_staged_outputs(*, staged: dict[str, pd.DataFrame], preview_rows: list[dict[str, str]]) -> None:
    orders = staged["orders_all"]
    items = staged["order_items_all"]
    level1 = staged["financial_events_level1"]
    for row in preview_rows:
        if row.get("promotion_status") != "ready_pending_approval":
            continue
        order_id = row["amazon_order_id"]
        item_ids = _order_item_ids(row)
        if not _live_order_present(orders, order_id):
            raise RuntimeError(f"staged_order_missing:{order_id}")
        if _live_item_count(items, order_id, item_ids) < len(item_ids):
            raise RuntimeError(f"staged_item_missing:{order_id}")
        if "Order ID" in level1.columns and order_id not in set(level1["Order ID"].astype(str)):
            raise RuntimeError(f"staged_level1_missing:{order_id}")


def _write_stage(stage_dir: Path, staged: dict[str, pd.DataFrame]) -> None:
    mapping = {
        "orders_all": "orders_all.csv",
        "order_items_all": "order_items_all.csv",
        "financial_events_level1": "financial_events_level1.csv",
    }
    for key, name in mapping.items():
        staged[key].to_csv(stage_dir / name, index=False)


def _run_order_master_rebuild(base: Path, log_dir: Path | None = None) -> int:
    env = os.environ.copy()
    env.setdefault("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    env.setdefault("SELLERONE_SQLITE_PATH", str(base / "out" / "sql" / "sellerone_dev.sqlite3"))
    env.update(
        {
            "ORDER_MASTER_SKIP_SHEETS": "1",
            "ORDER_MASTER_L1_STABLE_SECONDS": "0",
            "B_CYCLE_QUIET": "1",
            "ORDERS_WRITE_SHEETS": "0",
            "B002_WRITE_SHEETS": "0",
            "FIN_L3_SKIP_SHEETS": "1",
        }
    )
    result = subprocess.run(
        [sys.executable, str(base / "scripts" / "flows" / "B" / "B004_build_order_master.py")],
        cwd=base,
        env=env,
        timeout=1800,
        check=False,
        capture_output=True,
        text=True,
    )
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "B004_build_order_master_stdout.txt").write_text(result.stdout or "", encoding="utf-8")
        (log_dir / "B004_build_order_master_stderr.txt").write_text(result.stderr or "", encoding="utf-8")
    return int(result.returncode)


def _snapshot_files(paths: list[Path], snapshot_dir: Path) -> dict[str, dict[str, str]]:
    snapshots: dict[str, dict[str, str]] = {}
    for path in paths:
        key = path.name
        target = snapshot_dir / path.name
        if path.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            snapshots[str(path)] = {"existed": "1", "snapshot": str(target)}
        else:
            snapshots[str(path)] = {"existed": "0", "snapshot": str(target)}
    return snapshots


def _restore_snapshots(snapshots: dict[str, dict[str, str]]) -> None:
    for raw_path, info in snapshots.items():
        path = Path(raw_path)
        snapshot = Path(info.get("snapshot", ""))
        if info.get("existed") == "1" and snapshot.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(snapshot, path)
            _sync_if_registered(path)
        elif info.get("existed") == "0" and path.exists():
            path.unlink()


def _sync_if_registered(path: Path) -> None:
    try:
        sync_csv_to_finance_table(path)
    except Exception:
        pass


def _active_b_lock_paths(base: Path) -> list[Path]:
    candidates = [
        base / "out" / "systems" / "B" / "live" / "B_cycle.lock",
        base / "out" / "B_cycle.lock",
    ]
    return [path for path in candidates if path.exists()]


def _maintenance_ready_for_promotion(base: Path) -> bool:
    request = base / "out" / "locks" / "maintenance.requested"
    ready = base / "out" / "locks" / "maintenance.ready"
    if not request.exists() or not ready.exists():
        return False
    request_text = request.read_text(encoding="utf-8", errors="ignore").lower()
    ready_text = ready.read_text(encoding="utf-8", errors="ignore").lower()
    return "codex_b_order_promotion" in request_text and "b_ready" in ready_text


def _overall_status(rows: list[dict[str, str]]) -> str:
    statuses = {row.get("promotion_status", "") for row in rows}
    if not rows:
        return "not_checked"
    if "blocked_duplicate_partial" in statuses or "blocked_validation" in statuses:
        return "fail"
    if "ready_pending_approval" in statuses:
        return "decision_needed"
    return "ok"


def _summary_rows(
    *,
    observed: str,
    status: str,
    preview_rows: list[dict[str, str]],
    manifest: dict[str, Any],
) -> list[dict[str, str]]:
    def metric(name: str, value: object, row_status: str, label: str, notes: str = "") -> dict[str, str]:
        return {
            "observed_utc": observed,
            "metric": name,
            "status": row_status,
            "value": str(value),
            "proof_label": label,
            "notes": notes,
        }

    counts = {name: 0 for name in ["already_live", "ready_pending_approval", "blocked_duplicate_partial", "blocked_validation"]}
    for row in preview_rows:
        state = row.get("promotion_status", "")
        if state in counts:
            counts[state] += 1
    manifest_status = _text(manifest.get("status"))
    return [
        metric("overall_status", status, status, "not yet proven" if status in {"fail", "decision_needed"} else "API proved"),
        metric("api_proved_quarantine_orders", len(preview_rows), "ok" if preview_rows else "not_checked", "API proved" if preview_rows else "not yet proven"),
        metric("promotion_ready_orders", counts["ready_pending_approval"], "decision_needed" if counts["ready_pending_approval"] else "ok", "not yet proven" if counts["ready_pending_approval"] else "API proved"),
        metric("promotion_blocked_orders", counts["blocked_duplicate_partial"] + counts["blocked_validation"], "fail" if counts["blocked_duplicate_partial"] + counts["blocked_validation"] else "ok", "not yet proven" if counts["blocked_duplicate_partial"] + counts["blocked_validation"] else "API proved"),
        metric("already_live_orders", counts["already_live"], "ok", "API proved" if counts["already_live"] else "not yet proven"),
        metric("latest_promotion_manifest_status", manifest_status or "missing", "ok" if manifest_status == "promoted" else "not_checked", "API proved" if manifest_status == "promoted" else "not yet proven"),
    ]


def _manifest(
    *,
    observed: str,
    status: str,
    notes: str,
    preview: BOrderPromotionResult,
    promoted_orders: list[str] | None = None,
    stage_dir: Path | None = None,
    snapshot_dir: Path | None = None,
) -> dict[str, Any]:
    return {
        "observed_utc": observed,
        "status": status,
        "notes": notes,
        "promoted_orders": promoted_orders or [],
        "preview_status": preview.status,
        "preview_counts": {row["promotion_status"]: sum(1 for item in preview.preview_rows if item["promotion_status"] == row["promotion_status"]) for row in preview.preview_rows},
        "stage_dir": str(stage_dir) if stage_dir else "",
        "snapshot_dir": str(snapshot_dir) if snapshot_dir else "",
        "protected_actions_confirmed": status == "promoted",
    }


def _with_manifest(result: BOrderPromotionResult, manifest: dict[str, Any]) -> BOrderPromotionResult:
    return BOrderPromotionResult(
        observed_utc=result.observed_utc,
        status=result.status if manifest.get("status") != "promoted" else "ok",
        preview_rows=result.preview_rows,
        summary_rows=_summary_rows(
            observed=result.observed_utc,
            status=result.status if manifest.get("status") != "promoted" else "ok",
            preview_rows=result.preview_rows,
            manifest=manifest,
        ),
        manifest=manifest,
    )


def _read_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return read_finance_frame(path, dtype=str).fillna("")
    except Exception:
        return pd.read_csv(path, dtype=str).fillna("")


def _write_live_frame(base: Path, dataframe: pd.DataFrame, rel_path: str) -> None:
    path = base / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with _promotion_storage_env(base):
        write_finance_frame(dataframe, path, table_for_path(rel_path))


@contextmanager
def _promotion_storage_env(base: Path):
    previous_mode = os.environ.get("SELLERONE_STORAGE_MODE")
    previous_sqlite = os.environ.get("SELLERONE_SQLITE_PATH")
    if previous_mode is None:
        os.environ["SELLERONE_STORAGE_MODE"] = "sql_primary_csv_export"
    if previous_sqlite is None:
        os.environ["SELLERONE_SQLITE_PATH"] = str(base / "out" / "sql" / "sellerone_dev.sqlite3")
    try:
        yield
    finally:
        if previous_mode is None:
            os.environ.pop("SELLERONE_STORAGE_MODE", None)
        else:
            os.environ["SELLERONE_STORAGE_MODE"] = previous_mode
        if previous_sqlite is None:
            os.environ.pop("SELLERONE_SQLITE_PATH", None)
        else:
            os.environ["SELLERONE_SQLITE_PATH"] = previous_sqlite


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [{key: value or "" for key, value in row.items() if key is not None} for row in reader]


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _json_obj(value: object) -> dict[str, Any]:
    try:
        payload = json.loads(str(value or ""))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _json_list(value: object) -> list[dict[str, Any]]:
    try:
        payload = json.loads(str(value or ""))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _live_order_present(frame: pd.DataFrame, order_id: str) -> bool:
    if frame.empty or "amazon_order_id" not in frame.columns or not order_id:
        return False
    return order_id in set(frame["amazon_order_id"].astype(str).str.strip())


def _live_item_count(frame: pd.DataFrame, order_id: str, item_ids: list[str]) -> int:
    if frame.empty or "amazon_order_id" not in frame.columns or not order_id:
        return 0
    scoped = frame[frame["amazon_order_id"].astype(str).str.strip().eq(order_id)]
    if scoped.empty:
        return 0
    if not item_ids:
        return len(scoped.index)
    if "order_item_id" not in scoped.columns:
        return 0
    live_ids = set(scoped["order_item_id"].astype(str).str.strip())
    return sum(1 for item_id in item_ids if item_id in live_ids)


def _order_item_ids(row: dict[str, str]) -> list[str]:
    direct = [_text(part) for part in _text(row.get("order_item_ids")).split(";") if _text(part)]
    if direct:
        return direct
    _order, items = _payloads_without_fallback(row)
    return sorted({_text(item.get("OrderItemId")) for item in items if _text(item.get("OrderItemId"))})


def _payloads_without_fallback(row: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return _json_obj(row.get("order_payload_json")), _json_list(row.get("items_payload_json"))


def _split_first(value: object) -> str:
    return _text(str(value or "").split(";")[0])


def _text(value: object) -> str:
    return str(value or "").strip()


def _markdown(result: BOrderPromotionResult) -> str:
    ready = sum(1 for row in result.preview_rows if row.get("promotion_status") == "ready_pending_approval")
    blocked = sum(1 for row in result.preview_rows if row.get("promotion_status", "").startswith("blocked"))
    live = sum(1 for row in result.preview_rows if row.get("promotion_status") == "already_live")
    return "\n".join(
        [
            "# B Order Promotion",
            "",
            f"Status: {result.status}",
            f"Ready pending approval: {ready}",
            f"Blocked: {blocked}",
            f"Already live: {live}",
            "",
            "This is the controlled path from API-proved quarantine into live local B order proof. Live promotion is protected and requires explicit approval.",
            "",
        ]
    )
