from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.safe_file_writes import safe_to_csv
from scripts.flows.B.B047_build_token_shortage_repair_preview import (
    APPROVAL_REFERENCE,
    APPROVED_SKUS,
    PREVIEW_COLUMNS,
    PREVIEW_PATH,
    build_token_shortage_repair_preview,
    write_token_shortage_repair_preview_outputs,
)


OUT = Path("out")
TOKEN_LEDGER = OUT / "token_ledger_live.csv"
TOKEN_LEDGER_LIVE_COPY = OUT / "systems" / "B" / "live" / "token_ledger_live.csv"
TOKEN_ALLOCATIONS = OUT / "token_allocations_live.csv"
TOKEN_ALLOCATIONS_LIVE_COPY = OUT / "systems" / "B" / "live" / "token_allocations_live.csv"
TOKEN_SHORTAGES = OUT / "token_shortages_by_sku.csv"
TOKEN_SHORTAGES_LIVE_COPY = OUT / "systems" / "B" / "live" / "token_shortages_by_sku.csv"
ORDERS_MISSING_TOKENS = OUT / "orders_missing_tokens.csv"
TOKEN_COGS_LEDGER = OUT / "token_cogs_ledger.csv"
STOCK_ADJUSTMENT_EVENTS = OUT / "stock_adjustment_token_events.csv"
MANUAL_CORRECTION_EVENTS = OUT / "manual_token_correction_events.csv"
B_LOCK = OUT / "B_cycle.lock"
B_SUPERVISOR_LOCK = OUT / "B_supervisor.lock"
B_LIVE_LOCK = OUT / "systems" / "B" / "live" / "B_cycle.lock"
B_LIVE_SUPERVISOR_LOCK = OUT / "systems" / "B" / "live" / "B_supervisor.lock"
B_OWNER_LOCKS = [B_LOCK, B_SUPERVISOR_LOCK, B_LIVE_LOCK, B_LIVE_SUPERVISOR_LOCK]
B_MAINTENANCE_FLAG = OUT / "locks" / "b_cycle.maintenance"
MAINTENANCE_READY = OUT / "locks" / "maintenance.ready"
REPAIR_DIR = OUT / "systems" / "B" / "token_shortage_repair"
SNAPSHOT_DIR = REPAIR_DIR / "b048_token_shortage_repair_snapshots"
APPLIED_PATH = REPAIR_DIR / "b_token_shortage_repair_applied.csv"
MANIFEST_PATH = REPAIR_DIR / "b_token_shortage_repair_manifest.json"

APPLIED_COLUMNS = [
    "sku",
    "repair_lane",
    "order_id",
    "new_token_id",
    "new_token_status",
    "stock_adjustment_event_id",
    "stock_adjustment_retry_event_id",
    "basis_cost_per_unit",
    "basis_currency",
    "approval_reference",
    "action",
]

LEDGER_REQUIRED_COLUMNS = [
    "token_id",
    "seller_sku",
    "asin",
    "lot_id",
    "purchase_order_id",
    "order_confirmation_id",
    "invoice_id",
    "shipment_id",
    "cost_per_unit",
    "currency",
    "status",
    "received_date",
    "allocated_order_id",
    "allocated_date",
    "return_order_id",
    "return_date",
    "notes",
    "return_event_id",
    "last_return_order_id",
    "last_return_date",
    "last_return_event_id",
    "disposed_event_id",
    "disposed_date",
    "disposed_reason",
    "source",
    "source_batch_id",
    "created_at",
    "lot_rank",
    "lot_rank_num",
    "sort_rank",
    "source_order_key",
]

ALLOC_COLUMNS = [
    "order_id",
    "order_date",
    "seller_sku",
    "quantity",
    "token_id",
    "token_cost",
    "currency",
    "allocation_date",
    "source_level",
    "notes",
]

COGS_COLUMNS = [
    "order_id",
    "order_date",
    "seller_sku",
    "token_id",
    "token_cost",
    "currency",
    "allocation_date",
    "quantity",
    "source",
    "built_at",
    "vat_rate_pct",
    "cogs_exvat",
    "cogs_vat",
    "cogs_total",
]

ADJUSTMENT_COLUMNS = [
    "event_id",
    "sku",
    "event_date",
    "event_type",
    "disposition",
    "quantity",
    "applied_qty",
    "status",
    "note",
    "event_ts",
]

MANUAL_EVENT_COLUMNS = [
    "event_id",
    "event_ts",
    "seller_sku",
    "quantity",
    "applied_qty",
    "status",
    "correction_class",
    "approval_reference",
    "reason",
    "note",
]


@dataclass
class ApplyResult:
    status: str
    approved: bool
    preview_rows: int
    created_token_rows: int
    allocated_token_rows: int
    disposed_token_rows: int
    stock_event_rows: int
    shortage_rows_removed: int
    missing_order_rows_removed: int
    blocked_rows: int
    snapshot_dir: Path | None
    applied_path: Path
    manifest_path: Path
    reasons: list[str]


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: object) -> str:
    return str(value or "").strip()


def _as_float(value: object) -> float:
    try:
        return float(_text(value))
    except Exception:
        return 0.0


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = ""
    return out


def _snapshot_files(root: Path, observed_utc: str) -> Path:
    safe_stamp = observed_utc.replace(":", "").replace("-", "").replace("T", "_").replace("Z", "Z")
    snapshot_dir = root / SNAPSHOT_DIR / safe_stamp
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    for rel_path in [
        PREVIEW_PATH,
        TOKEN_LEDGER,
        TOKEN_LEDGER_LIVE_COPY,
        TOKEN_ALLOCATIONS,
        TOKEN_ALLOCATIONS_LIVE_COPY,
        TOKEN_SHORTAGES,
        TOKEN_SHORTAGES_LIVE_COPY,
        ORDERS_MISSING_TOKENS,
        TOKEN_COGS_LEDGER,
        STOCK_ADJUSTMENT_EVENTS,
        MANUAL_CORRECTION_EVENTS,
    ]:
        source = root / rel_path
        if source.exists():
            target = snapshot_dir / rel_path.name
            suffix = 1
            while target.exists():
                target = snapshot_dir / f"{rel_path.stem}.{suffix}{rel_path.suffix}"
                suffix += 1
            shutil.copy2(source, target)
    return snapshot_dir


def _restore_snapshot(root: Path, snapshot_dir: Path) -> None:
    restore_map = {
        TOKEN_LEDGER.name: TOKEN_LEDGER,
        TOKEN_ALLOCATIONS.name: TOKEN_ALLOCATIONS,
        TOKEN_SHORTAGES.name: TOKEN_SHORTAGES,
        ORDERS_MISSING_TOKENS.name: ORDERS_MISSING_TOKENS,
        TOKEN_COGS_LEDGER.name: TOKEN_COGS_LEDGER,
        STOCK_ADJUSTMENT_EVENTS.name: STOCK_ADJUSTMENT_EVENTS,
        MANUAL_CORRECTION_EVENTS.name: MANUAL_CORRECTION_EVENTS,
    }
    for source in snapshot_dir.iterdir():
        rel = restore_map.get(source.name)
        if rel is None:
            continue
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for live_source, live_target in [
        (TOKEN_LEDGER.name, TOKEN_LEDGER_LIVE_COPY),
        (TOKEN_ALLOCATIONS.name, TOKEN_ALLOCATIONS_LIVE_COPY),
        (TOKEN_SHORTAGES.name, TOKEN_SHORTAGES_LIVE_COPY),
    ]:
        source = snapshot_dir / live_source
        target = root / live_target
        if source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def _empty_applied() -> pd.DataFrame:
    return pd.DataFrame(columns=APPLIED_COLUMNS)


def _write_manifest(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{Path.cwd().name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _marker_field(payload: str, key: str) -> str:
    for part in str(payload or "").split("|"):
        part = part.strip()
        if part.startswith(f"{key}="):
            return part.split("=", 1)[1].strip()
    return ""


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""


def _maintenance_ready_for_request(root: Path, maintenance_request_id: str | None) -> bool:
    ready_text = _read_text(root / MAINTENANCE_READY)
    flag_text = _read_text(root / B_MAINTENANCE_FLAG)
    if not ready_text or not flag_text:
        return False
    if not maintenance_request_id:
        return True
    return (
        _marker_field(ready_text, "request_id") == maintenance_request_id
        and _marker_field(flag_text, "request_id") == maintenance_request_id
    )


def _manifest_payload(
    result: ApplyResult,
    observed_utc: str,
    maintenance_request_id: str | None,
) -> dict[str, object]:
    return {
        "status": result.status,
        "approved": result.approved,
        "observed_utc": observed_utc,
        "approval_reference": APPROVAL_REFERENCE,
        "approved_skus": sorted(APPROVED_SKUS),
        "maintenance_request_id": maintenance_request_id or "",
        "preview_rows": result.preview_rows,
        "created_token_rows": result.created_token_rows,
        "allocated_token_rows": result.allocated_token_rows,
        "disposed_token_rows": result.disposed_token_rows,
        "stock_event_rows": result.stock_event_rows,
        "shortage_rows_removed": result.shortage_rows_removed,
        "missing_order_rows_removed": result.missing_order_rows_removed,
        "blocked_rows": result.blocked_rows,
        "snapshot_dir": str(result.snapshot_dir or ""),
        "applied_path": str(result.applied_path),
        "manifest_path": str(result.manifest_path),
        "reasons": result.reasons,
        "safety_boundary": {
            "b_run_or_restart": "not_allowed_by_this_script",
            "sheets_write": "not_allowed",
            "local_db_alignment": "not_allowed",
            "order_master_or_level1_write": "not_allowed",
            "roi_or_restock_use": "not_allowed",
            "repair_scope": "approved B token shortage repair for AK-OB6V-HIYD only",
        },
    }


def _validate_preview(preview: pd.DataFrame, ledger: pd.DataFrame, allocations: pd.DataFrame) -> list[str]:
    reasons: list[str] = []
    if preview.empty:
        return ["Token shortage repair preview is empty."]
    missing_preview_cols = sorted(set(PREVIEW_COLUMNS) - set(preview.columns))
    if missing_preview_cols:
        reasons.append(f"Preview missing columns: {','.join(missing_preview_cols)}")
        return reasons
    if set(preview["sku"].astype(str).str.strip()) - APPROVED_SKUS:
        reasons.append("Preview contains a SKU outside the approved repair boundary.")
    if not set(preview["review_readiness"].astype(str).str.strip()).issubset({"ready_for_protected_apply"}):
        reasons.append("Preview contains rows that are not ready for protected apply.")
    for flag_col in ["preview_live_write_allowed", "roi_or_restock_use_allowed", "sellerboard_final_truth_allowed"]:
        if not set(preview[flag_col].astype(str).str.strip()).issubset({"0"}):
            reasons.append(f"Preview safety flag {flag_col} is not locked to 0.")
    token_ids = preview["new_token_id"].astype(str).str.strip()
    if token_ids.eq("").any():
        reasons.append("Preview contains blank new token IDs.")
    if token_ids.duplicated().any():
        reasons.append("Preview contains duplicate new token IDs.")
    if not ledger.empty and "token_id" in ledger.columns:
        existing = set(ledger["token_id"].astype(str).str.strip())
        duplicates = sorted(existing & set(token_ids))
        if duplicates:
            reasons.append(f"New token IDs already exist: {','.join(duplicates[:3])}")
    if not allocations.empty:
        allocations = _ensure_columns(allocations, ALLOC_COLUMNS)
        allocation_keys = {
            (_text(row.get("order_id", "")), _text(row.get("seller_sku", "")))
            for _, row in allocations.iterrows()
            if _text(row.get("order_id", "")) and _text(row.get("seller_sku", ""))
        }
        sale_rows = preview[preview["new_token_role"].astype(str).str.strip() == "SALE"].copy()
        for _, row in sale_rows.iterrows():
            key = (_text(row.get("order_id", "")), _text(row.get("sku", "")))
            if key in allocation_keys:
                reasons.append(f"Order {key[0]} SKU {key[1]} already has a token allocation.")
    sale_rows = preview[preview["new_token_role"].astype(str).str.strip() == "SALE"].copy()
    if sale_rows["order_id"].astype(str).str.strip().eq("").any():
        reasons.append("A sale repair row is missing an order ID.")
    adjustment_rows = preview[preview["new_token_role"].astype(str).str.strip() == "ADJUSTMENT"].copy()
    if adjustment_rows["stock_adjustment_event_id"].astype(str).str.strip().eq("").any():
        reasons.append("An adjustment repair row is missing the Amazon stock adjustment event ID.")
    return reasons


def _new_ledger_rows(preview: pd.DataFrame, observed_utc: str) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for _, row in preview.iterrows():
        role = _text(row.get("new_token_role", ""))
        status = _text(row.get("new_token_status", ""))
        order_id = _text(row.get("order_id", ""))
        event_id = _text(row.get("stock_adjustment_event_id", ""))
        event_date = _text(row.get("stock_adjustment_event_date", ""))
        notes = (
            f"manual_approved_correction:{APPROVAL_REFERENCE};"
            f"class=approved_b_token_shortage_repair;role={role};basis_token_id={_text(row.get('basis_token_id', ''))}"
        )
        if role == "ADJUSTMENT":
            notes = f"{notes};amazon_stock_adjustment_event_id={event_id}"
        rows.append(
            {
                "token_id": _text(row.get("new_token_id", "")),
                "seller_sku": _text(row.get("sku", "")),
                "asin": "",
                "lot_id": "",
                "purchase_order_id": "",
                "order_confirmation_id": "",
                "invoice_id": "",
                "shipment_id": "",
                "cost_per_unit": _text(row.get("basis_cost_per_unit", "")),
                "currency": _text(row.get("basis_currency", "")) or "GBP",
                "status": status,
                "received_date": observed_utc[:10],
                "allocated_order_id": order_id if role == "SALE" else "",
                "allocated_date": _text(row.get("order_date", "")) if role == "SALE" else "",
                "return_order_id": "",
                "return_date": "",
                "notes": notes,
                "return_event_id": "",
                "last_return_order_id": "",
                "last_return_date": "",
                "last_return_event_id": "",
                "disposed_event_id": event_id if role == "ADJUSTMENT" else "",
                "disposed_date": event_date if role == "ADJUSTMENT" else "",
                "disposed_reason": "approved_stock_adjustment_close" if role == "ADJUSTMENT" else "",
                "source": "manager_approved_token_shortage_repair",
                "source_batch_id": APPROVAL_REFERENCE,
                "created_at": observed_utc,
                "lot_rank": "",
                "lot_rank_num": "",
                "sort_rank": "",
                "source_order_key": "",
            }
        )
    return pd.DataFrame(rows, columns=LEDGER_REQUIRED_COLUMNS).fillna("")


def _new_allocation_rows(preview: pd.DataFrame, observed_utc: str) -> pd.DataFrame:
    sale_rows = preview[preview["new_token_role"].astype(str).str.strip() == "SALE"].copy()
    rows: list[dict[str, str]] = []
    for _, row in sale_rows.iterrows():
        rows.append(
            {
                "order_id": _text(row.get("order_id", "")),
                "order_date": _text(row.get("order_date", "")),
                "seller_sku": _text(row.get("sku", "")),
                "quantity": "1",
                "token_id": _text(row.get("new_token_id", "")),
                "token_cost": _text(row.get("basis_cost_per_unit", "")),
                "currency": _text(row.get("basis_currency", "")) or "GBP",
                "allocation_date": observed_utc,
                "source_level": _text(row.get("source_level", "")),
                "notes": "manager_approved_token_shortage_repair",
            }
        )
    return pd.DataFrame(rows, columns=ALLOC_COLUMNS).fillna("")


def _new_cogs_rows(allocation_rows: pd.DataFrame, observed_utc: str) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for _, row in allocation_rows.iterrows():
        exvat = round(_as_float(row.get("token_cost", "")), 2)
        vat = round(exvat * 0.20, 2)
        total = round(exvat + vat, 2)
        rows.append(
            {
                "order_id": _text(row.get("order_id", "")),
                "order_date": _text(row.get("order_date", "")),
                "seller_sku": _text(row.get("seller_sku", "")),
                "token_id": _text(row.get("token_id", "")),
                "token_cost": f"{exvat:.2f}",
                "currency": _text(row.get("currency", "")) or "GBP",
                "allocation_date": observed_utc,
                "quantity": "1",
                "source": "token_allocations_live",
                "built_at": observed_utc,
                "vat_rate_pct": "20.0",
                "cogs_exvat": f"{exvat:.2f}",
                "cogs_vat": f"{vat:.2f}",
                "cogs_total": f"{total:.2f}",
            }
        )
    return pd.DataFrame(rows, columns=COGS_COLUMNS).fillna("")


def _new_adjustment_event_rows(preview: pd.DataFrame, observed_utc: str) -> pd.DataFrame:
    adjustment_rows = preview[preview["new_token_role"].astype(str).str.strip() == "ADJUSTMENT"].copy()
    rows: list[dict[str, str]] = []
    for _, row in adjustment_rows.iterrows():
        retry_event_id = ""
        notes = _text(row.get("notes", ""))
        marker = "approved_stock_adjustment_close:"
        if marker in notes:
            retry_event_id = notes.split(marker, 1)[1].split(";", 1)[0].strip()
        rows.append(
            {
                "event_id": retry_event_id or f"{_text(row.get('stock_adjustment_event_id', ''))}-retry",
                "sku": _text(row.get("sku", "")),
                "event_date": _text(row.get("stock_adjustment_event_date", "")),
                "event_type": "Adjustments",
                "disposition": "SELLABLE",
                "quantity": _text(row.get("stock_adjustment_quantity", "")) or "-1",
                "applied_qty": "1",
                "status": "ok",
                "note": "manager_approved_token_shortage_repair_disposed_correction_token",
                "event_ts": observed_utc,
            }
        )
    return pd.DataFrame(rows, columns=ADJUSTMENT_COLUMNS).fillna("")


def _new_manual_event_rows(preview: pd.DataFrame, observed_utc: str) -> pd.DataFrame:
    grouped = preview.groupby(["sku", "repair_lane"], dropna=False).size().reset_index(name="qty")
    rows: list[dict[str, str]] = []
    for _, row in grouped.iterrows():
        sku = _text(row.get("sku", ""))
        lane = _text(row.get("repair_lane", ""))
        qty = int(row.get("qty", 0) or 0)
        rows.append(
            {
                "event_id": f"B048-{APPROVAL_REFERENCE}-{sku}-{lane}",
                "event_ts": observed_utc,
                "seller_sku": sku,
                "quantity": str(qty),
                "applied_qty": str(qty),
                "status": "ok",
                "correction_class": "approved_b_token_shortage_repair",
                "approval_reference": APPROVAL_REFERENCE,
                "reason": lane,
                "note": "created_by_b048_protected_apply",
            }
        )
    return pd.DataFrame(rows, columns=MANUAL_EVENT_COLUMNS).fillna("")


def _drop_repaired_shortage_rows(shortages: pd.DataFrame, repaired_skus: set[str]) -> tuple[pd.DataFrame, int]:
    if shortages.empty:
        return shortages, 0
    work = shortages.copy()
    if "seller_sku" not in work.columns:
        return work, 0
    mask = work["seller_sku"].astype(str).str.strip().isin(repaired_skus)
    return work.loc[~mask].copy(), int(mask.sum())


def _drop_repaired_missing_order_rows(missing_orders: pd.DataFrame, sale_preview: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if missing_orders.empty or sale_preview.empty:
        return missing_orders, 0
    work = missing_orders.copy()
    for column in ["Order ID", "SKU"]:
        if column not in work.columns:
            work[column] = ""
    repaired = {
        (_text(row.get("order_id", "")), _text(row.get("sku", "")))
        for _, row in sale_preview.iterrows()
    }
    mask = work.apply(lambda row: (_text(row.get("Order ID", "")), _text(row.get("SKU", ""))) in repaired, axis=1)
    return work.loc[~mask].copy(), int(mask.sum())


def apply_token_shortage_repair(
    *,
    root: Path | str | None = None,
    approve_protected_token_shortage_repair: bool = False,
    observed_utc: str | None = None,
    maintenance_request_id: str | None = None,
) -> ApplyResult:
    root_path = Path(root or ".")
    observed = observed_utc or _utc_now_text()
    applied_path = root_path / APPLIED_PATH
    manifest_path = root_path / MANIFEST_PATH

    if not approve_protected_token_shortage_repair:
        result = ApplyResult(
            status="blocked_needs_approval",
            approved=False,
            preview_rows=0,
            created_token_rows=0,
            allocated_token_rows=0,
            disposed_token_rows=0,
            stock_event_rows=0,
            shortage_rows_removed=0,
            missing_order_rows_removed=0,
            blocked_rows=0,
            snapshot_dir=None,
            applied_path=applied_path,
            manifest_path=manifest_path,
            reasons=["Protected token shortage repair approval flag was not supplied."],
        )
        safe_to_csv(_empty_applied(), applied_path, index=False)
        _write_manifest(manifest_path, _manifest_payload(result, observed, maintenance_request_id))
        return result

    active_locks = [str(path) for path in B_OWNER_LOCKS if (root_path / path).exists()]
    maintenance_ready = _maintenance_ready_for_request(root_path, maintenance_request_id)
    if active_locks and not maintenance_ready:
        result = ApplyResult(
            status="blocked_active_b_lock",
            approved=True,
            preview_rows=0,
            created_token_rows=0,
            allocated_token_rows=0,
            disposed_token_rows=0,
            stock_event_rows=0,
            shortage_rows_removed=0,
            missing_order_rows_removed=0,
            blocked_rows=0,
            snapshot_dir=None,
            applied_path=applied_path,
            manifest_path=manifest_path,
            reasons=[
                "B lock or supervisor lock exists and matching maintenance.ready is not present.",
                "active_locks=" + ";".join(active_locks),
            ],
        )
        safe_to_csv(_empty_applied(), applied_path, index=False)
        _write_manifest(manifest_path, _manifest_payload(result, observed, maintenance_request_id))
        return result

    preview_result = build_token_shortage_repair_preview(root=root_path)
    write_token_shortage_repair_preview_outputs(preview_result, root=root_path)
    preview = preview_result["preview"].copy()
    summary = preview_result["summary"].copy()
    summary_status = ""
    if not summary.empty:
        values = {row["metric"]: row["value"] for _, row in summary.iterrows()}
        summary_status = values.get("status", "")
        blocked_summary = values.get("blocked_reasons", "")
    else:
        blocked_summary = ""

    ledger = _ensure_columns(_read_csv(root_path / TOKEN_LEDGER), LEDGER_REQUIRED_COLUMNS)
    allocations = _ensure_columns(_read_csv(root_path / TOKEN_ALLOCATIONS), ALLOC_COLUMNS)
    shortages = _read_csv(root_path / TOKEN_SHORTAGES)
    missing_orders = _read_csv(root_path / ORDERS_MISSING_TOKENS)
    cogs = _ensure_columns(_read_csv(root_path / TOKEN_COGS_LEDGER), COGS_COLUMNS)
    adjustment_events = _ensure_columns(_read_csv(root_path / STOCK_ADJUSTMENT_EVENTS), ADJUSTMENT_COLUMNS)
    manual_events = _ensure_columns(_read_csv(root_path / MANUAL_CORRECTION_EVENTS), MANUAL_EVENT_COLUMNS)

    reasons = _validate_preview(preview, ledger, allocations)
    if summary_status == "blocked" and blocked_summary:
        reasons.append(blocked_summary)
    if reasons:
        result = ApplyResult(
            status="blocked",
            approved=True,
            preview_rows=len(preview),
            created_token_rows=0,
            allocated_token_rows=0,
            disposed_token_rows=0,
            stock_event_rows=0,
            shortage_rows_removed=0,
            missing_order_rows_removed=0,
            blocked_rows=len(preview),
            snapshot_dir=None,
            applied_path=applied_path,
            manifest_path=manifest_path,
            reasons=reasons,
        )
        safe_to_csv(_empty_applied(), applied_path, index=False)
        _write_manifest(manifest_path, _manifest_payload(result, observed, maintenance_request_id))
        return result

    snapshot_dir = _snapshot_files(root_path, observed)
    try:
        new_ledger = _new_ledger_rows(preview, observed)
        new_allocations = _new_allocation_rows(preview, observed)
        new_cogs = _new_cogs_rows(new_allocations, observed)
        new_adjustments = _new_adjustment_event_rows(preview, observed)
        new_manual_events = _new_manual_event_rows(preview, observed)
        sale_preview = preview[preview["new_token_role"].astype(str).str.strip() == "SALE"].copy()
        repaired_skus = set(preview["sku"].astype(str).str.strip())

        updated_ledger = pd.concat([ledger, new_ledger], ignore_index=True)[ledger.columns]
        updated_allocations = pd.concat([allocations, new_allocations], ignore_index=True)[allocations.columns]
        updated_cogs = pd.concat([cogs, new_cogs], ignore_index=True)[cogs.columns]
        updated_adjustments = pd.concat([adjustment_events, new_adjustments], ignore_index=True)[adjustment_events.columns]
        updated_manual_events = pd.concat([manual_events, new_manual_events], ignore_index=True)[manual_events.columns]
        updated_shortages, shortage_rows_removed = _drop_repaired_shortage_rows(shortages, repaired_skus)
        updated_missing_orders, missing_order_rows_removed = _drop_repaired_missing_order_rows(missing_orders, sale_preview)

        safe_to_csv(updated_ledger, root_path / TOKEN_LEDGER, index=False)
        safe_to_csv(updated_ledger, root_path / TOKEN_LEDGER_LIVE_COPY, index=False)
        safe_to_csv(updated_allocations, root_path / TOKEN_ALLOCATIONS, index=False)
        safe_to_csv(updated_allocations, root_path / TOKEN_ALLOCATIONS_LIVE_COPY, index=False)
        safe_to_csv(updated_shortages, root_path / TOKEN_SHORTAGES, index=False)
        safe_to_csv(updated_shortages, root_path / TOKEN_SHORTAGES_LIVE_COPY, index=False)
        safe_to_csv(updated_missing_orders, root_path / ORDERS_MISSING_TOKENS, index=False)
        safe_to_csv(updated_cogs, root_path / TOKEN_COGS_LEDGER, index=False)
        safe_to_csv(updated_adjustments, root_path / STOCK_ADJUSTMENT_EVENTS, index=False)
        safe_to_csv(updated_manual_events, root_path / MANUAL_CORRECTION_EVENTS, index=False)

        applied_rows: list[dict[str, str]] = []
        adjustment_retry_by_base = {
            _text(row.get("stock_adjustment_event_id", "")): _text(row.get("event_id", ""))
            for _, row in new_adjustments.iterrows()
        }
        for _, row in preview.iterrows():
            base_event = _text(row.get("stock_adjustment_event_id", ""))
            applied_rows.append(
                {
                    "sku": _text(row.get("sku", "")),
                    "repair_lane": _text(row.get("repair_lane", "")),
                    "order_id": _text(row.get("order_id", "")),
                    "new_token_id": _text(row.get("new_token_id", "")),
                    "new_token_status": _text(row.get("new_token_status", "")),
                    "stock_adjustment_event_id": base_event,
                    "stock_adjustment_retry_event_id": adjustment_retry_by_base.get(base_event, ""),
                    "basis_cost_per_unit": _text(row.get("basis_cost_per_unit", "")),
                    "basis_currency": _text(row.get("basis_currency", "")),
                    "approval_reference": APPROVAL_REFERENCE,
                    "action": "protected_token_shortage_repair_applied",
                }
            )
        applied = pd.DataFrame(applied_rows, columns=APPLIED_COLUMNS).fillna("")
        safe_to_csv(applied, applied_path, index=False)
    except Exception:
        _restore_snapshot(root_path, snapshot_dir)
        raise

    result = ApplyResult(
        status="applied",
        approved=True,
        preview_rows=len(preview),
        created_token_rows=len(new_ledger),
        allocated_token_rows=len(new_allocations),
        disposed_token_rows=len(new_adjustments),
        stock_event_rows=len(new_adjustments),
        shortage_rows_removed=shortage_rows_removed,
        missing_order_rows_removed=missing_order_rows_removed,
        blocked_rows=0,
        snapshot_dir=snapshot_dir,
        applied_path=applied_path,
        manifest_path=manifest_path,
        reasons=[],
    )
    _write_manifest(manifest_path, _manifest_payload(result, observed, maintenance_request_id))
    return result


def main() -> None:
    result = apply_token_shortage_repair()
    print(
        {
            "status": result.status,
            "preview_rows": result.preview_rows,
            "created_token_rows": result.created_token_rows,
            "allocated_token_rows": result.allocated_token_rows,
            "disposed_token_rows": result.disposed_token_rows,
            "stock_event_rows": result.stock_event_rows,
            "shortage_rows_removed": result.shortage_rows_removed,
            "missing_order_rows_removed": result.missing_order_rows_removed,
            "blocked_rows": result.blocked_rows,
            "snapshot_dir": str(result.snapshot_dir or ""),
            "applied": str(result.applied_path),
            "manifest": str(result.manifest_path),
        }
    )


if __name__ == "__main__":
    main()
