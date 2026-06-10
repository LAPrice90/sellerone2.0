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
from scripts.flows.B.B049_build_legacy_baseline_gap_preview import (
    PREVIEW_COLUMNS,
    PREVIEW_PATH,
    build_legacy_baseline_gap_preview,
    write_legacy_baseline_gap_preview_outputs,
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
B_MAINTENANCE_FLAG = OUT / "locks" / "b_cycle.maintenance"
MAINTENANCE_READY = OUT / "locks" / "maintenance.ready"
REPAIR_DIR = OUT / "systems" / "B" / "token_shortage_repair"
SNAPSHOT_DIR = REPAIR_DIR / "b050_legacy_baseline_gap_snapshots"
APPLIED_PATH = REPAIR_DIR / "b_legacy_baseline_gap_applied.csv"
MANIFEST_PATH = REPAIR_DIR / "b_legacy_baseline_gap_manifest.json"

APPROVAL_REFERENCE = "LEGACY_BASELINE_20260603_LUKE_APPROVED_MW_9K5M_VKW8_ONE_TOKEN"
APPROVED_SKU = "MW-9K5M-VKW8"
APPROVED_ORDER_ID = "204-5340430-7253949"

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
    "sku",
    "order_id",
    "new_token_id",
    "new_token_status",
    "basis_cost_per_unit",
    "basis_currency",
    "basis_token_id",
    "approval_reference",
    "action",
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


def _active_paths(root: Path, paths: list[Path]) -> list[str]:
    return [str(path) for path in paths if (root / path).exists()]


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


def _write_manifest(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{Path.cwd().name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _empty_applied() -> pd.DataFrame:
    return pd.DataFrame(columns=APPLIED_COLUMNS)


def _manifest_payload(result: ApplyResult, observed_utc: str, maintenance_request_id: str | None) -> dict[str, object]:
    return {
        "status": result.status,
        "approved": result.approved,
        "observed_utc": observed_utc,
        "approval_reference": APPROVAL_REFERENCE,
        "approved_sku": APPROVED_SKU,
        "approved_order_id": APPROVED_ORDER_ID,
        "maintenance_request_id": maintenance_request_id or "",
        "preview_rows": result.preview_rows,
        "created_token_rows": result.created_token_rows,
        "allocated_token_rows": result.allocated_token_rows,
        "cogs_rows": result.cogs_rows,
        "shortage_rows_removed": result.shortage_rows_removed,
        "missing_order_rows_removed": result.missing_order_rows_removed,
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
            "roi_or_restock_use": "not_allowed",
            "repair_scope": "MW-9K5M-VKW8 one-token legacy baseline correction only",
        },
    }


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


def _final_token_id() -> str:
    return "MANAGER-CORR-MW-9K5M-VKW8-LEGACY_BASELINE_20260603-0001"


def _validate_preview(preview: pd.DataFrame, ledger: pd.DataFrame, allocations: pd.DataFrame) -> list[str]:
    reasons: list[str] = []
    if preview.empty:
        return ["Legacy baseline preview is empty."]
    missing_columns = sorted(set(PREVIEW_COLUMNS) - set(preview.columns))
    if missing_columns:
        return [f"Preview missing columns: {','.join(missing_columns)}"]
    if len(preview) != 1:
        reasons.append("Preview must contain exactly one approved MW row.")
    row = preview.iloc[0]
    if _text(row.get("sku", "")) != APPROVED_SKU:
        reasons.append("Preview SKU is outside the approved MW boundary.")
    if _text(row.get("order_id", "")) != APPROVED_ORDER_ID:
        reasons.append("Preview order is outside the approved MW boundary.")
    if _text(row.get("quantity", "")) != "1":
        reasons.append("Preview quantity must be 1.")
    if _text(row.get("review_readiness", "")) != "decision_ready_named_protected_window":
        reasons.append("Preview is not decision-ready.")
    if _text(row.get("proposed_repair_lane", "")) != "legacy_baseline_sale_token_correction":
        reasons.append("Preview is not a legacy baseline sale-token correction.")
    if _text(row.get("proposed_token_status", "")) != "allocated":
        reasons.append("Preview token status is not allocated.")
    for column in ["preview_live_write_allowed", "roi_or_restock_use_allowed", "sellerboard_final_truth_allowed"]:
        if _text(row.get(column, "")) != "0":
            reasons.append(f"Preview safety flag {column} is not locked to 0.")
    if _text(row.get("duplicate_allocation_count", "")) != "0":
        reasons.append("Preview reports an existing duplicate allocation.")
    if _as_float(row.get("basis_cost_per_unit", "")) <= 0:
        reasons.append("Preview has no positive cost basis.")
    token_id = _final_token_id()
    ledger = _ensure_columns(ledger, ["token_id"])
    if token_id in set(ledger["token_id"].astype(str).str.strip()):
        reasons.append("Final correction token ID already exists.")
    allocations = _ensure_columns(allocations, ["order_id", "seller_sku"])
    duplicate_allocations = (
        (allocations["order_id"].astype(str).str.strip() == APPROVED_ORDER_ID)
        & (allocations["seller_sku"].astype(str).str.strip() == APPROVED_SKU)
    )
    if int(duplicate_allocations.sum()) > 0:
        reasons.append("Order already has a token allocation.")
    return reasons


def _new_ledger_rows(preview: pd.DataFrame, observed_utc: str) -> pd.DataFrame:
    row = preview.iloc[0]
    token_id = _final_token_id()
    return pd.DataFrame(
        [
            {
                "token_id": token_id,
                "seller_sku": APPROVED_SKU,
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
                "allocated_order_id": APPROVED_ORDER_ID,
                "allocated_date": _text(row.get("order_date", "")),
                "return_order_id": "",
                "return_date": "",
                "notes": (
                    f"manual_approved_correction:{APPROVAL_REFERENCE};"
                    f"class=legacy_baseline_sale_token_correction;"
                    f"basis_token_id={_text(row.get('basis_token_id', ''))}"
                ),
                "return_event_id": "",
                "last_return_order_id": "",
                "last_return_date": "",
                "last_return_event_id": "",
                "disposed_event_id": "",
                "disposed_date": "",
                "disposed_reason": "",
                "source": "manager_approved_legacy_baseline_gap_repair",
                "source_batch_id": APPROVAL_REFERENCE,
                "created_at": observed_utc,
                "lot_rank": "",
                "lot_rank_num": "",
                "sort_rank": "",
                "source_order_key": "",
            }
        ],
        columns=LEDGER_REQUIRED_COLUMNS,
    ).fillna("")


def _new_allocation_rows(preview: pd.DataFrame, observed_utc: str) -> pd.DataFrame:
    row = preview.iloc[0]
    return pd.DataFrame(
        [
            {
                "order_id": APPROVED_ORDER_ID,
                "order_date": _text(row.get("order_date", "")),
                "seller_sku": APPROVED_SKU,
                "quantity": "1",
                "token_id": _final_token_id(),
                "token_cost": _text(row.get("basis_cost_per_unit", "")),
                "currency": _text(row.get("basis_currency", "")) or "GBP",
                "allocation_date": observed_utc,
                "source_level": _text(row.get("source_level", "")),
                "notes": "manager_approved_legacy_baseline_gap_repair",
            }
        ],
        columns=ALLOC_COLUMNS,
    ).fillna("")


def _new_cogs_rows(allocation_rows: pd.DataFrame, observed_utc: str) -> pd.DataFrame:
    row = allocation_rows.iloc[0]
    exvat = round(_as_float(row.get("token_cost", "")), 2)
    vat = round(exvat * 0.20, 2)
    total = round(exvat + vat, 2)
    return pd.DataFrame(
        [
            {
                "order_id": APPROVED_ORDER_ID,
                "order_date": _text(row.get("order_date", "")),
                "seller_sku": APPROVED_SKU,
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
        ],
        columns=COGS_COLUMNS,
    ).fillna("")


def _new_manual_event_rows(observed_utc: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "event_id": f"B050-{APPROVAL_REFERENCE}",
                "event_ts": observed_utc,
                "seller_sku": APPROVED_SKU,
                "quantity": "1",
                "applied_qty": "1",
                "status": "ok",
                "correction_class": "approved_legacy_baseline_gap_repair",
                "approval_reference": APPROVAL_REFERENCE,
                "reason": "one_token_mw_legacy_baseline_gap",
                "note": "created_by_b050_protected_apply",
            }
        ],
        columns=MANUAL_EVENT_COLUMNS,
    ).fillna("")


def _drop_repaired_shortage_rows(shortages: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if shortages.empty:
        return shortages, 0
    work = _ensure_columns(shortages, ["seller_sku", "shortage_class"])
    mask = (
        (work["seller_sku"].astype(str).str.strip() == APPROVED_SKU)
        & (work["shortage_class"].astype(str).str.strip() == "legacy_baseline_gap")
    )
    return work.loc[~mask].copy(), int(mask.sum())


def _drop_repaired_missing_order_rows(missing_orders: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if missing_orders.empty:
        return missing_orders, 0
    work = _ensure_columns(missing_orders, ["Order ID", "SKU"])
    mask = (
        (work["Order ID"].astype(str).str.strip() == APPROVED_ORDER_ID)
        & (work["SKU"].astype(str).str.strip() == APPROVED_SKU)
    )
    return work.loc[~mask].copy(), int(mask.sum())


def _blocked_result(
    *,
    root: Path,
    observed: str,
    approved: bool,
    status: str,
    reasons: list[str],
    preview_rows: int = 0,
    blocked_rows: int = 0,
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
        blocked_rows=blocked_rows,
        snapshot_dir=None,
        applied_path=root / APPLIED_PATH,
        manifest_path=root / MANIFEST_PATH,
        reasons=reasons,
    )
    safe_to_csv(_empty_applied(), result.applied_path, index=False)
    _write_manifest(result.manifest_path, _manifest_payload(result, observed, maintenance_request_id))
    return result


def apply_legacy_baseline_gap_repair(
    *,
    root: Path | str | None = None,
    approve_protected_legacy_baseline_repair: bool = False,
    observed_utc: str | None = None,
    maintenance_request_id: str | None = None,
) -> ApplyResult:
    root_path = Path(root or ".")
    observed = observed_utc or _utc_now_text()

    if not approve_protected_legacy_baseline_repair:
        return _blocked_result(
            root=root_path,
            observed=observed,
            approved=False,
            status="blocked_needs_approval",
            reasons=["Protected legacy baseline repair approval flag was not supplied."],
            maintenance_request_id=maintenance_request_id,
        )

    worker_locks = _active_paths(root_path, B_WORKER_LOCKS)
    supervisor_locks = _active_paths(root_path, B_SUPERVISOR_LOCKS)
    maintenance_ready = _maintenance_ready_for_request(root_path, maintenance_request_id)
    if (worker_locks or supervisor_locks) and not maintenance_ready:
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

    preview_result = build_legacy_baseline_gap_preview(root=root_path, observed_utc=observed)
    write_legacy_baseline_gap_preview_outputs(preview_result, root=root_path)
    preview = preview_result["preview"].copy()
    ledger = _ensure_columns(_read_csv(root_path / TOKEN_LEDGER), LEDGER_REQUIRED_COLUMNS)
    allocations = _ensure_columns(_read_csv(root_path / TOKEN_ALLOCATIONS), ALLOC_COLUMNS)
    shortages = _read_csv(root_path / TOKEN_SHORTAGES)
    missing_orders = _read_csv(root_path / ORDERS_MISSING_TOKENS)
    cogs = _ensure_columns(_read_csv(root_path / TOKEN_COGS_LEDGER), COGS_COLUMNS)
    manual_events = _ensure_columns(_read_csv(root_path / MANUAL_CORRECTION_EVENTS), MANUAL_EVENT_COLUMNS)

    reasons = _validate_preview(preview, ledger, allocations)
    if reasons:
        return _blocked_result(
            root=root_path,
            observed=observed,
            approved=True,
            status="blocked",
            reasons=reasons,
            preview_rows=len(preview),
            blocked_rows=len(preview),
            maintenance_request_id=maintenance_request_id,
        )

    snapshot_dir = _snapshot_files(root_path, observed)
    try:
        new_ledger = _new_ledger_rows(preview, observed)
        new_allocations = _new_allocation_rows(preview, observed)
        new_cogs = _new_cogs_rows(new_allocations, observed)
        new_manual_events = _new_manual_event_rows(observed)

        updated_ledger = pd.concat([ledger, new_ledger], ignore_index=True)[ledger.columns]
        updated_allocations = pd.concat([allocations, new_allocations], ignore_index=True)[allocations.columns]
        updated_cogs = pd.concat([cogs, new_cogs], ignore_index=True)[cogs.columns]
        updated_manual_events = pd.concat([manual_events, new_manual_events], ignore_index=True)[manual_events.columns]
        updated_shortages, shortage_rows_removed = _drop_repaired_shortage_rows(shortages)
        updated_missing_orders, missing_order_rows_removed = _drop_repaired_missing_order_rows(missing_orders)

        safe_to_csv(updated_ledger, root_path / TOKEN_LEDGER, index=False)
        safe_to_csv(updated_ledger, root_path / TOKEN_LEDGER_LIVE_COPY, index=False)
        safe_to_csv(updated_allocations, root_path / TOKEN_ALLOCATIONS, index=False)
        safe_to_csv(updated_allocations, root_path / TOKEN_ALLOCATIONS_LIVE_COPY, index=False)
        safe_to_csv(updated_shortages, root_path / TOKEN_SHORTAGES, index=False)
        safe_to_csv(updated_shortages, root_path / TOKEN_SHORTAGES_LIVE_COPY, index=False)
        safe_to_csv(updated_missing_orders, root_path / ORDERS_MISSING_TOKENS, index=False)
        safe_to_csv(updated_cogs, root_path / TOKEN_COGS_LEDGER, index=False)
        safe_to_csv(updated_manual_events, root_path / MANUAL_CORRECTION_EVENTS, index=False)

        applied = pd.DataFrame(
            [
                {
                    "sku": APPROVED_SKU,
                    "order_id": APPROVED_ORDER_ID,
                    "new_token_id": _final_token_id(),
                    "new_token_status": "allocated",
                    "basis_cost_per_unit": _text(preview.iloc[0].get("basis_cost_per_unit", "")),
                    "basis_currency": _text(preview.iloc[0].get("basis_currency", "")) or "GBP",
                    "basis_token_id": _text(preview.iloc[0].get("basis_token_id", "")),
                    "approval_reference": APPROVAL_REFERENCE,
                    "action": "protected_legacy_baseline_gap_repair_applied",
                }
            ],
            columns=APPLIED_COLUMNS,
        ).fillna("")
        safe_to_csv(applied, root_path / APPLIED_PATH, index=False)
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
        blocked_rows=0,
        snapshot_dir=snapshot_dir,
        applied_path=root_path / APPLIED_PATH,
        manifest_path=root_path / MANIFEST_PATH,
        reasons=[],
    )
    _write_manifest(result.manifest_path, _manifest_payload(result, observed, maintenance_request_id))
    return result


def main() -> None:
    result = apply_legacy_baseline_gap_repair()
    print(
        {
            "status": result.status,
            "preview_rows": result.preview_rows,
            "created_token_rows": result.created_token_rows,
            "allocated_token_rows": result.allocated_token_rows,
            "cogs_rows": result.cogs_rows,
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
