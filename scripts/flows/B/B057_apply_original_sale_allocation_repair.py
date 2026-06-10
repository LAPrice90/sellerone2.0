from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.safe_file_writes import safe_to_csv
from scripts.flows.B.B056_build_original_sale_allocation_repair_preview import (
    OUT_PREVIEW as B056_PREVIEW,
    PREVIEW_COLUMNS as B056_PREVIEW_COLUMNS,
    build_original_sale_allocation_repair_preview,
    write_original_sale_allocation_repair_preview_outputs,
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
MANUAL_CORRECTION_EVENTS = OUT / "manual_token_correction_events.csv"
B_WORKER_LOCKS = [OUT / "B_cycle.lock", OUT / "systems" / "B" / "live" / "B_cycle.lock"]
B_SUPERVISOR_LOCKS = [OUT / "B_supervisor.lock", OUT / "systems" / "B" / "live" / "B_supervisor.lock"]
MAINTENANCE_REQUESTED = OUT / "locks" / "maintenance.requested"
MAINTENANCE_READY = OUT / "locks" / "maintenance.ready"
LEGACY_B_MAINTENANCE = OUT / "locks" / "b_cycle.maintenance"
REPAIR_DIR = OUT / "systems" / "B" / "refunds"
SNAPSHOT_DIR = REPAIR_DIR / "b057_original_sale_allocation_snapshots"
APPLIED_PATH = REPAIR_DIR / "b_original_sale_allocation_repair_applied.csv"
MANIFEST_PATH = REPAIR_DIR / "b_original_sale_allocation_repair_manifest.json"

APPROVAL_REFERENCE = "B057_ORIGINAL_SALE_ALLOCATION_20260603_LUKE_APPROVED_B056"
ALLOWED_REPAIR_LANES = {
    "protected_legacy_baseline_allocation_candidate",
    "protected_runtime_adjustment_allocation_candidate",
}

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

APPLIED_COLUMNS = [
    "order_id",
    "sku",
    "repair_lane",
    "new_token_id",
    "new_token_status",
    "basis_cost_per_unit",
    "basis_currency",
    "basis_source_token_id",
    "approval_reference",
    "action",
    "runtime_stock_adjustment_closed",
    "notes",
]


@dataclass
class ApplyResult:
    status: str
    approved: bool
    preview_rows: int
    created_token_rows: int
    allocated_token_rows: int
    cogs_rows: int
    shortage_rows_removed: int
    missing_order_rows_removed: int
    runtime_adjustment_deferred_rows: int
    blocked_rows: int
    snapshot_dir: Path | None
    applied_path: Path
    manifest_path: Path
    reasons: list[str]


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: object) -> str:
    return str(value or "").strip()


def _norm_sku(value: object) -> str:
    return _text(value).upper()


def _safe(value: object) -> str:
    raw = _text(value).upper()
    return re.sub(r"[^A-Z0-9._-]", "_", raw)[:80] or "BLANK"


def _as_int(value: object) -> int:
    try:
        return int(float(_text(value)))
    except Exception:
        return 0


def _as_float(value: object) -> float:
    try:
        return float(_text(value))
    except Exception:
        return 0.0


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, keep_default_na=False).fillna("")


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = ""
    return out


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""


def _marker_field(payload: str, key: str) -> str:
    for part in str(payload or "").split("|"):
        part = part.strip()
        if part.startswith(f"{key}="):
            return part.split("=", 1)[1].strip()
    return ""


def _active_paths(root: Path, paths: list[Path]) -> list[str]:
    return [str(path) for path in paths if (root / path).exists()]


def _maintenance_ready_for_request(root: Path, maintenance_request_id: str | None) -> bool:
    ready_text = _read_text(root / MAINTENANCE_READY)
    if not ready_text or "B_READY" not in ready_text:
        return False
    request_text = _read_text(root / MAINTENANCE_REQUESTED)
    legacy_text = _read_text(root / LEGACY_B_MAINTENANCE)
    if not maintenance_request_id:
        return bool(request_text or legacy_text)
    ready_matches = _marker_field(ready_text, "request_id") == maintenance_request_id
    request_matches = _marker_field(request_text, "request_id") == maintenance_request_id
    legacy_matches = _marker_field(legacy_text, "request_id") == maintenance_request_id
    return ready_matches and (request_matches or legacy_matches)


def _empty_applied() -> pd.DataFrame:
    return pd.DataFrame(columns=APPLIED_COLUMNS)


def _write_manifest(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{Path.cwd().name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _manifest_payload(result: ApplyResult, observed_utc: str, maintenance_request_id: str | None) -> dict[str, object]:
    return {
        "status": result.status,
        "approved": result.approved,
        "observed_utc": observed_utc,
        "approval_reference": APPROVAL_REFERENCE,
        "maintenance_request_id": maintenance_request_id or "",
        "preview_rows": result.preview_rows,
        "created_token_rows": result.created_token_rows,
        "allocated_token_rows": result.allocated_token_rows,
        "cogs_rows": result.cogs_rows,
        "shortage_rows_removed": result.shortage_rows_removed,
        "missing_order_rows_removed": result.missing_order_rows_removed,
        "runtime_adjustment_deferred_rows": result.runtime_adjustment_deferred_rows,
        "blocked_rows": result.blocked_rows,
        "snapshot_dir": str(result.snapshot_dir or ""),
        "applied_path": str(result.applied_path),
        "manifest_path": str(result.manifest_path),
        "reasons": result.reasons,
        "safety_boundary": {
            "b_run_or_restart": "not_performed_by_this_script",
            "sheets_write": "not_allowed",
            "local_db_alignment": "not_allowed",
            "order_master_or_level1_write": "not_allowed",
            "stock_adjustment_close": "not_performed_by_this_script",
            "roi_or_restock_use": "not_allowed",
            "repair_scope": "B056 original sale allocation rows only",
        },
    }


def _blocked_result(
    *,
    root: Path,
    observed: str,
    approved: bool,
    status: str,
    reasons: list[str],
    preview_rows: int = 0,
    blocked_rows: int = 0,
    runtime_adjustment_deferred_rows: int = 0,
    maintenance_request_id: str | None = None,
) -> ApplyResult:
    result = ApplyResult(
        status=status,
        approved=approved,
        preview_rows=preview_rows,
        created_token_rows=0,
        allocated_token_rows=0,
        cogs_rows=0,
        shortage_rows_removed=0,
        missing_order_rows_removed=0,
        runtime_adjustment_deferred_rows=runtime_adjustment_deferred_rows,
        blocked_rows=blocked_rows,
        snapshot_dir=None,
        applied_path=root / APPLIED_PATH,
        manifest_path=root / MANIFEST_PATH,
        reasons=reasons,
    )
    safe_to_csv(_empty_applied(), result.applied_path, index=False)
    _write_manifest(result.manifest_path, _manifest_payload(result, observed, maintenance_request_id))
    return result


def _snapshot_files(root: Path, observed_utc: str) -> Path:
    safe_stamp = observed_utc.replace(":", "").replace("-", "").replace("T", "_").replace("Z", "Z")
    snapshot_dir = root / SNAPSHOT_DIR / safe_stamp
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    for rel_path in [
        B056_PREVIEW,
        TOKEN_LEDGER,
        TOKEN_LEDGER_LIVE_COPY,
        TOKEN_ALLOCATIONS,
        TOKEN_ALLOCATIONS_LIVE_COPY,
        TOKEN_SHORTAGES,
        TOKEN_SHORTAGES_LIVE_COPY,
        ORDERS_MISSING_TOKENS,
        TOKEN_COGS_LEDGER,
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


def _token_id(sku: str, order_id: str, sequence: int) -> str:
    return f"MANAGER-CORR-{_safe(sku)}-B057-{_safe(order_id)}-{sequence:04d}"


def _target_rows(preview: pd.DataFrame) -> pd.DataFrame:
    if preview.empty:
        return preview
    work = _ensure_columns(preview, B056_PREVIEW_COLUMNS)
    work["order_id_norm"] = work["order_id"].map(_text)
    work["sku_norm"] = work["sku"].map(_norm_sku)
    return work[
        (work["order_id_norm"] != "")
        & (work["sku_norm"] != "")
        & work["repair_lane"].astype(str).str.strip().isin(ALLOWED_REPAIR_LANES)
    ].copy()


def _validate_preview(preview: pd.DataFrame, ledger: pd.DataFrame, allocations: pd.DataFrame) -> list[str]:
    reasons: list[str] = []
    missing_cols = sorted(set(B056_PREVIEW_COLUMNS) - set(preview.columns))
    if missing_cols:
        return [f"Preview missing columns: {','.join(missing_cols)}"]
    if preview.empty:
        return ["B056 original sale allocation repair preview is empty."]
    targets = _target_rows(preview)
    if len(targets) != len(preview):
        reasons.append("Preview contains rows outside the approved B056 allocation repair lanes.")
    if not set(preview["repair_readiness"].astype(str).str.strip()).issubset({"blocked_needs_protected_stock_decision"}):
        reasons.append("Preview contains rows not marked for protected stock/token decision.")
    for flag_col in ["preview_live_write_allowed", "roi_or_restock_use_allowed", "sellerboard_final_truth_allowed"]:
        if not set(preview[flag_col].astype(str).str.strip()).issubset({"0"}):
            reasons.append(f"Preview safety flag {flag_col} is not locked to 0.")
    if not set(preview["protected_before_apply"].astype(str).str.strip()).issubset({"1"}):
        reasons.append("Preview rows are not all marked protected_before_apply=1.")
    if (preview["missing_token_quantity"].map(_as_int) <= 0).any():
        reasons.append("Preview contains a row with no missing token quantity.")
    if (preview["basis_cost_per_unit"].map(_as_float) <= 0).any():
        reasons.append("Preview contains a row with no positive cost basis.")

    ledger = _ensure_columns(ledger, ["token_id", "seller_sku", "allocated_order_id"])
    allocations = _ensure_columns(allocations, ["order_id", "seller_sku"])
    existing_token_ids = set(ledger["token_id"].astype(str).str.strip())
    seen_token_ids: set[str] = set()
    for sequence, (_, row) in enumerate(preview.iterrows(), start=1):
        order_id = _text(row.get("order_id", ""))
        sku = _norm_sku(row.get("sku", ""))
        token_id = _token_id(sku, order_id, sequence)
        if token_id in seen_token_ids:
            reasons.append(f"Duplicate generated token ID: {token_id}")
        seen_token_ids.add(token_id)
        if token_id in existing_token_ids:
            reasons.append(f"Generated token ID already exists: {token_id}")
        allocation_exists = (
            (allocations["order_id"].astype(str).str.strip() == order_id)
            & (allocations["seller_sku"].astype(str).str.strip().str.upper() == sku)
        )
        if int(allocation_exists.sum()) > 0:
            reasons.append(f"Order {order_id} SKU {sku} already has a token allocation.")
        ledger_allocated = (
            (ledger["allocated_order_id"].astype(str).str.strip() == order_id)
            & (ledger["seller_sku"].astype(str).str.strip().str.upper() == sku)
        )
        if int(ledger_allocated.sum()) > 0:
            reasons.append(f"Order {order_id} SKU {sku} already has an allocated ledger token.")
    return sorted(set(reasons))


def _new_ledger_rows(preview: pd.DataFrame, observed_utc: str) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for sequence, (_, row) in enumerate(preview.iterrows(), start=1):
        order_id = _text(row.get("order_id", ""))
        sku = _norm_sku(row.get("sku", ""))
        lane = _text(row.get("repair_lane", ""))
        rows.append(
            {
                "token_id": _token_id(sku, order_id, sequence),
                "seller_sku": sku,
                "asin": "",
                "lot_id": "",
                "purchase_order_id": "",
                "order_confirmation_id": "",
                "invoice_id": "",
                "shipment_id": "",
                "cost_per_unit": _text(row.get("basis_cost_per_unit", "")),
                "currency": _text(row.get("basis_currency", "")) or "GBP",
                "status": "allocated",
                "received_date": observed_utc[:10],
                "allocated_order_id": order_id,
                "allocated_date": _text(row.get("refund_posted_date", "")) or observed_utc,
                "return_order_id": "",
                "return_date": "",
                "notes": (
                    f"manual_approved_correction:{APPROVAL_REFERENCE};"
                    f"class=original_sale_allocation_repair;lane={lane};"
                    f"basis_token_id={_text(row.get('basis_source_token_id', ''))};"
                    "stock_adjustment_closed=0"
                ),
                "return_event_id": "",
                "last_return_order_id": "",
                "last_return_date": "",
                "last_return_event_id": "",
                "disposed_event_id": "",
                "disposed_date": "",
                "disposed_reason": "",
                "source": "manager_approved_original_sale_allocation_repair",
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
    rows: list[dict[str, str]] = []
    for sequence, (_, row) in enumerate(preview.iterrows(), start=1):
        order_id = _text(row.get("order_id", ""))
        sku = _norm_sku(row.get("sku", ""))
        rows.append(
            {
                "order_id": order_id,
                "order_date": _text(row.get("order_date", "")),
                "seller_sku": sku,
                "quantity": "1",
                "token_id": _token_id(sku, order_id, sequence),
                "token_cost": _text(row.get("basis_cost_per_unit", "")),
                "currency": _text(row.get("basis_currency", "")) or "GBP",
                "allocation_date": observed_utc,
                "source_level": _text(row.get("source_level", "")),
                "notes": "manager_approved_original_sale_allocation_repair",
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
                "seller_sku": _norm_sku(row.get("seller_sku", "")),
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


def _new_manual_event_rows(preview: pd.DataFrame, observed_utc: str) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for _, row in preview.iterrows():
        order_id = _text(row.get("order_id", ""))
        sku = _norm_sku(row.get("sku", ""))
        lane = _text(row.get("repair_lane", ""))
        rows.append(
            {
                "event_id": f"B057-{APPROVAL_REFERENCE}-{_safe(sku)}-{_safe(order_id)}",
                "event_ts": observed_utc,
                "seller_sku": sku,
                "quantity": "1",
                "applied_qty": "1",
                "status": "ok",
                "correction_class": "approved_original_sale_allocation_repair",
                "approval_reference": APPROVAL_REFERENCE,
                "reason": lane,
                "note": "sale_allocation_only_stock_adjustment_not_closed",
            }
        )
    return pd.DataFrame(rows, columns=MANUAL_EVENT_COLUMNS).fillna("")


def _drop_repaired_missing_order_rows(missing_orders: pd.DataFrame, preview: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if missing_orders.empty:
        return missing_orders, 0
    work = _ensure_columns(missing_orders, ["Order ID", "SKU"])
    repaired = {
        (_text(row.get("order_id", "")), _norm_sku(row.get("sku", "")))
        for _, row in preview.iterrows()
    }
    mask = work.apply(lambda row: (_text(row.get("Order ID", "")), _norm_sku(row.get("SKU", ""))) in repaired, axis=1)
    return work.loc[~mask].copy(), int(mask.sum())


def _drop_repaired_shortage_rows(shortages: pd.DataFrame, preview: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if shortages.empty:
        return shortages, 0
    work = _ensure_columns(shortages, ["seller_sku"])
    repaired_skus = {_norm_sku(row.get("sku", "")) for _, row in preview.iterrows()}
    mask = work["seller_sku"].astype(str).str.strip().str.upper().isin(repaired_skus)
    return work.loc[~mask].copy(), int(mask.sum())


def apply_original_sale_allocation_repair(
    *,
    root: Path | str | None = None,
    approve_protected_original_sale_allocation_repair: bool = False,
    observed_utc: str | None = None,
    maintenance_request_id: str | None = None,
) -> ApplyResult:
    root_path = Path(root or ".")
    observed = observed_utc or _utc_now_text()

    if not approve_protected_original_sale_allocation_repair:
        return _blocked_result(
            root=root_path,
            observed=observed,
            approved=False,
            status="blocked_needs_approval",
            reasons=["Protected original sale allocation repair approval flag was not supplied."],
            maintenance_request_id=maintenance_request_id,
        )

    worker_locks = _active_paths(root_path, B_WORKER_LOCKS)
    supervisor_locks = _active_paths(root_path, B_SUPERVISOR_LOCKS)
    if (worker_locks or supervisor_locks) and not _maintenance_ready_for_request(root_path, maintenance_request_id):
        return _blocked_result(
            root=root_path,
            observed=observed,
            approved=True,
            status="blocked_active_b_owner",
            reasons=[
                "B owner lock exists and matching maintenance.ready is not present.",
                "active_worker_locks=" + ";".join(worker_locks),
                "active_supervisor_locks=" + ";".join(supervisor_locks),
            ],
            maintenance_request_id=maintenance_request_id,
        )

    preview_result = build_original_sale_allocation_repair_preview(root=root_path, observed_utc=observed)
    write_original_sale_allocation_repair_preview_outputs(preview_result, root=root_path)
    preview = _target_rows(preview_result["preview"].copy())
    ledger = _ensure_columns(_read_csv(root_path / TOKEN_LEDGER), LEDGER_REQUIRED_COLUMNS)
    allocations = _ensure_columns(_read_csv(root_path / TOKEN_ALLOCATIONS), ALLOC_COLUMNS)
    shortages = _read_csv(root_path / TOKEN_SHORTAGES)
    missing_orders = _read_csv(root_path / ORDERS_MISSING_TOKENS)
    cogs = _ensure_columns(_read_csv(root_path / TOKEN_COGS_LEDGER), COGS_COLUMNS)
    manual_events = _ensure_columns(_read_csv(root_path / MANUAL_CORRECTION_EVENTS), MANUAL_EVENT_COLUMNS)
    reasons = _validate_preview(preview, ledger, allocations)
    runtime_deferred = int((preview["repair_lane"] == "protected_runtime_adjustment_allocation_candidate").sum()) if not preview.empty else 0
    if reasons:
        return _blocked_result(
            root=root_path,
            observed=observed,
            approved=True,
            status="blocked",
            reasons=reasons,
            preview_rows=len(preview),
            blocked_rows=len(preview),
            runtime_adjustment_deferred_rows=runtime_deferred,
            maintenance_request_id=maintenance_request_id,
        )

    snapshot_dir = _snapshot_files(root_path, observed)
    try:
        new_ledger = _new_ledger_rows(preview, observed)
        new_allocations = _new_allocation_rows(preview, observed)
        new_cogs = _new_cogs_rows(new_allocations, observed)
        new_manual_events = _new_manual_event_rows(preview, observed)
        updated_ledger = pd.concat([ledger, new_ledger], ignore_index=True)[ledger.columns].fillna("")
        updated_allocations = pd.concat([allocations, new_allocations], ignore_index=True)[allocations.columns].fillna("")
        updated_cogs = pd.concat([cogs, new_cogs], ignore_index=True)[cogs.columns].fillna("")
        updated_manual_events = pd.concat([manual_events, new_manual_events], ignore_index=True)[manual_events.columns].fillna("")
        updated_shortages, shortage_rows_removed = _drop_repaired_shortage_rows(shortages, preview)
        updated_missing_orders, missing_order_rows_removed = _drop_repaired_missing_order_rows(missing_orders, preview)

        safe_to_csv(updated_ledger, root_path / TOKEN_LEDGER, index=False)
        safe_to_csv(updated_ledger, root_path / TOKEN_LEDGER_LIVE_COPY, index=False)
        safe_to_csv(updated_allocations, root_path / TOKEN_ALLOCATIONS, index=False)
        safe_to_csv(updated_allocations, root_path / TOKEN_ALLOCATIONS_LIVE_COPY, index=False)
        safe_to_csv(updated_shortages, root_path / TOKEN_SHORTAGES, index=False)
        safe_to_csv(updated_shortages, root_path / TOKEN_SHORTAGES_LIVE_COPY, index=False)
        safe_to_csv(updated_missing_orders, root_path / ORDERS_MISSING_TOKENS, index=False)
        safe_to_csv(updated_cogs, root_path / TOKEN_COGS_LEDGER, index=False)
        safe_to_csv(updated_manual_events, root_path / MANUAL_CORRECTION_EVENTS, index=False)

        applied_rows: list[dict[str, str]] = []
        for sequence, (_, row) in enumerate(preview.iterrows(), start=1):
            lane = _text(row.get("repair_lane", ""))
            order_id = _text(row.get("order_id", ""))
            sku = _norm_sku(row.get("sku", ""))
            applied_rows.append(
                {
                    "order_id": order_id,
                    "sku": sku,
                    "repair_lane": lane,
                    "new_token_id": _token_id(sku, order_id, sequence),
                    "new_token_status": "allocated",
                    "basis_cost_per_unit": _text(row.get("basis_cost_per_unit", "")),
                    "basis_currency": _text(row.get("basis_currency", "")) or "GBP",
                    "basis_source_token_id": _text(row.get("basis_source_token_id", "")),
                    "approval_reference": APPROVAL_REFERENCE,
                    "action": "protected_original_sale_allocation_repair_applied",
                    "runtime_stock_adjustment_closed": "0",
                    "notes": (
                        "sale_allocation_only"
                        if lane != "protected_runtime_adjustment_allocation_candidate"
                        else "sale_allocation_only_runtime_stock_adjustment_left_visible"
                    ),
                }
            )
        safe_to_csv(pd.DataFrame(applied_rows, columns=APPLIED_COLUMNS).fillna(""), root_path / APPLIED_PATH, index=False)
    except Exception:
        _restore_snapshot(root_path, snapshot_dir)
        raise

    result = ApplyResult(
        status="applied",
        approved=True,
        preview_rows=len(preview),
        created_token_rows=len(new_ledger),
        allocated_token_rows=len(new_allocations),
        cogs_rows=len(new_cogs),
        shortage_rows_removed=shortage_rows_removed,
        missing_order_rows_removed=missing_order_rows_removed,
        runtime_adjustment_deferred_rows=runtime_deferred,
        blocked_rows=0,
        snapshot_dir=snapshot_dir,
        applied_path=root_path / APPLIED_PATH,
        manifest_path=root_path / MANIFEST_PATH,
        reasons=[],
    )
    _write_manifest(result.manifest_path, _manifest_payload(result, observed, maintenance_request_id))
    return result


def main() -> None:
    result = apply_original_sale_allocation_repair()
    print(
        {
            "status": result.status,
            "preview_rows": result.preview_rows,
            "created_token_rows": result.created_token_rows,
            "allocated_token_rows": result.allocated_token_rows,
            "cogs_rows": result.cogs_rows,
            "shortage_rows_removed": result.shortage_rows_removed,
            "missing_order_rows_removed": result.missing_order_rows_removed,
            "runtime_adjustment_deferred_rows": result.runtime_adjustment_deferred_rows,
            "blocked_rows": result.blocked_rows,
            "snapshot_dir": str(result.snapshot_dir or ""),
            "applied": str(result.applied_path),
            "manifest": str(result.manifest_path),
        }
    )


if __name__ == "__main__":
    main()
