from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import hashlib
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


OUT = Path("out")
PREVIEW = OUT / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv"
TOKEN_LEDGER = OUT / "token_ledger_live.csv"
TOKEN_LEDGER_LIVE_COPY = OUT / "systems" / "B" / "live" / "token_ledger_live.csv"
TOKEN_RETURN_LEDGER = OUT / "token_return_ledger.csv"
STOCK_ADJUSTMENT_EVENTS = OUT / "stock_adjustment_token_events.csv"
B_WORKER_LOCKS = [OUT / "B_cycle.lock", OUT / "systems" / "B" / "live" / "B_cycle.lock"]
B_SUPERVISOR_LOCKS = [OUT / "B_supervisor.lock", OUT / "systems" / "B" / "live" / "B_supervisor.lock"]
MAINTENANCE_REQUESTED = OUT / "locks" / "maintenance.requested"
MAINTENANCE_READY = OUT / "locks" / "maintenance.ready"
LEGACY_B_MAINTENANCE = OUT / "locks" / "b_cycle.maintenance"
SNAPSHOT_DIR = OUT / "systems" / "B" / "refunds" / "b009_return_token_reuse_snapshots"
OUT_APPLIED = OUT / "systems" / "B" / "refunds" / "b009_return_token_reuse_applied.csv"
OUT_MANIFEST = OUT / "systems" / "B" / "refunds" / "b009_return_token_reuse_manifest.json"

ELIGIBLE_LANE = "b009_order_aware_sellable_return"

APPLIED_COLUMNS = [
    "order_id",
    "sku",
    "event_id",
    "original_token_id",
    "reusable_token_id",
    "previous_status",
    "original_new_status",
    "reusable_new_status",
    "return_date",
    "token_cost",
    "currency",
    "action",
]

RETURN_LEDGER_COLUMNS = [
    "return_event_id",
    "return_date",
    "seller_sku",
    "token_id",
    "token_cost",
    "currency",
    "source",
    "event_type",
]

STOCK_EVENT_COLUMNS = [
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

SNAPSHOT_RELS = [
    PREVIEW,
    TOKEN_LEDGER,
    TOKEN_LEDGER_LIVE_COPY,
    TOKEN_RETURN_LEDGER,
    STOCK_ADJUSTMENT_EVENTS,
]


@dataclass
class ApplyResult:
    status: str
    approved: bool
    eligible_rows: int
    applied_rows: int
    token_rows_updated: int
    created_token_rows: int
    return_ledger_rows: int
    stock_event_rows: int
    blocked_rows: int
    snapshot_dir: Path | None
    applied_path: Path
    manifest_path: Path
    reasons: list[str]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _text(value: object) -> str:
    return str(value or "").strip()


def _norm_sku(value: object) -> str:
    return _text(value).upper()


def _split(value: object) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for part in _text(value).split("|"):
        text = part.strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_fragment(value: object, *, max_len: int = 18) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]", "_", _text(value))
    text = text.strip("._-")
    return (text or "X")[:max_len]


def _event_id(order_id: str, sku: str, token_id: str, seq: int) -> str:
    digest = hashlib.sha1(f"{order_id}|{sku}|{token_id}|{seq}".encode("utf-8")).hexdigest()[:10]
    order_tail = _safe_fragment(order_id[-10:], max_len=10)
    sku_part = _safe_fragment(sku, max_len=18)
    return f"B009-ORDER-{order_tail}-{sku_part}-{seq:02d}-{digest}"


def _append_note(existing: object, marker: str) -> str:
    text = _text(existing)
    if not text:
        return marker
    if marker in text:
        return text
    return f"{text};{marker}"


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


def _eligible_preview_rows(preview: pd.DataFrame) -> pd.DataFrame:
    if preview.empty:
        return preview.copy()
    work = preview.copy()
    for column in [
        "order_id",
        "sku",
        "amazon_return_disposition",
        "amazon_return_date",
        "returned_pending_token_ids",
        "reusable_return_token_ids",
        "return_cogs_token_ids",
        "repair_lane",
        "repair_readiness",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
    ]:
        if column not in work.columns:
            work[column] = ""
    return work[work["repair_lane"].astype(str).str.strip() == ELIGIBLE_LANE].copy()


def _validate_inputs(preview: pd.DataFrame, ledger: pd.DataFrame) -> list[str]:
    reasons: list[str] = []
    if preview.empty:
        reasons.append("No eligible B009 order-aware return-token reuse rows found.")
        return reasons
    unsafe = preview[
        (preview["preview_live_write_allowed"].astype(str).str.strip() != "0")
        | (preview["roi_or_restock_use_allowed"].astype(str).str.strip() != "0")
        | (preview["sellerboard_final_truth_allowed"].astype(str).str.strip() != "0")
    ]
    if not unsafe.empty:
        reasons.append(f"Preview contains unsafe live/ROI/Sellerboard flags on {len(unsafe)} eligible rows.")
    wrong_disposition = preview[preview["amazon_return_disposition"].astype(str).str.upper().str.strip() != "SELLABLE"]
    if not wrong_disposition.empty:
        reasons.append(f"Preview contains {len(wrong_disposition)} non-sellable rows in the B009 sellable lane.")
    if ledger.empty:
        reasons.append("Token ledger is missing or empty.")
    required_ledger = {"token_id", "seller_sku", "status", "return_order_id", "return_date", "return_event_id"}
    missing_ledger = sorted(required_ledger - set(ledger.columns))
    if missing_ledger:
        reasons.append(f"Token ledger missing columns: {','.join(missing_ledger)}")
    return reasons


def _validate_ledger_only(ledger: pd.DataFrame) -> list[str]:
    if ledger.empty:
        return ["Token ledger is missing or empty."]
    required_ledger = {"token_id", "seller_sku", "status"}
    missing_ledger = sorted(required_ledger - set(ledger.columns))
    if missing_ledger:
        return [f"Token ledger missing columns: {','.join(missing_ledger)}"]
    return []


def _manifest_closure_drift_rows(root: Path, ledger: pd.DataFrame) -> pd.DataFrame:
    prior = _read_csv(root / OUT_APPLIED)
    if prior.empty:
        return pd.DataFrame(columns=APPLIED_COLUMNS)
    for column in APPLIED_COLUMNS:
        if column not in prior.columns:
            prior[column] = ""
    if ledger.empty or "token_id" not in ledger.columns:
        return pd.DataFrame(columns=APPLIED_COLUMNS)
    work = ledger.copy()
    for column in ["token_id", "status"]:
        if column not in work.columns:
            work[column] = ""
    token_status = {
        _text(row.get("token_id", "")): _text(row.get("status", "")).lower()
        for _, row in work.iterrows()
        if _text(row.get("token_id", ""))
    }
    drift_rows: list[dict[str, str]] = []
    for _, row in prior.iterrows():
        original_token_id = _text(row.get("original_token_id", ""))
        reusable_token_id = _text(row.get("reusable_token_id", ""))
        if not original_token_id or not reusable_token_id:
            continue
        original_status = token_status.get(original_token_id, "")
        reusable_status = token_status.get(reusable_token_id, "")
        if original_status == "returned_complete":
            continue
        if reusable_status not in {"available", "allocated", "warehouse"}:
            continue
        drift_rows.append({column: _text(row.get(column, "")) for column in APPLIED_COLUMNS})
    return pd.DataFrame(drift_rows, columns=APPLIED_COLUMNS).fillna("")


def _manifest_payload(result: ApplyResult, observed_utc: str, maintenance_request_id: str | None = None) -> dict[str, object]:
    return {
        "status": result.status,
        "approved": result.approved,
        "observed_utc": observed_utc,
        "maintenance_request_id": maintenance_request_id or "",
        "eligible_rows": result.eligible_rows,
        "applied_rows": result.applied_rows,
        "token_rows_updated": result.token_rows_updated,
        "created_token_rows": result.created_token_rows,
        "return_ledger_rows": result.return_ledger_rows,
        "stock_event_rows": result.stock_event_rows,
        "blocked_rows": result.blocked_rows,
        "snapshot_dir": str(result.snapshot_dir or ""),
        "applied_path": str(result.applied_path),
        "manifest_path": str(result.manifest_path),
        "reasons": result.reasons,
        "safety_boundary": {
            "b_run_or_restart": "not_allowed_by_this_script",
            "sheets_write": "not_allowed",
            "local_db_alignment": "not_allowed",
            "roi_or_restock_use": "not_allowed",
            "sellerboard_final_truth": "not_allowed",
            "repair_scope": "B009 local order-aware returned-token reuse proof only",
        },
    }


def _write_manifest(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{Path.cwd().name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _snapshot_files(root: Path, observed_utc: str) -> Path:
    safe_stamp = observed_utc.replace(":", "").replace("-", "").replace("T", "_").replace("Z", "Z")
    snapshot_dir = root / SNAPSHOT_DIR / safe_stamp
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    existed: list[str] = []
    for rel_path in SNAPSHOT_RELS:
        source = root / rel_path
        if source.exists():
            existed.append(str(rel_path).replace("\\", "/"))
            target = snapshot_dir / rel_path.name
            shutil.copy2(source, target)
    (snapshot_dir / "_snapshot_manifest.json").write_text(
        json.dumps({"existed": existed}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return snapshot_dir


def _restore_snapshot(root: Path, snapshot_dir: Path) -> None:
    try:
        payload = json.loads((snapshot_dir / "_snapshot_manifest.json").read_text(encoding="utf-8"))
    except Exception:
        payload = {"existed": []}
    existed = {str(item) for item in payload.get("existed", [])}
    for rel_path in SNAPSHOT_RELS:
        source = snapshot_dir / rel_path.name
        target = root / rel_path
        key = str(rel_path).replace("\\", "/")
        if source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        elif key not in existed and target.exists():
            target.unlink(missing_ok=True)


def _empty_result(
    *,
    root: Path,
    status: str,
    approved: bool,
    eligible_rows: int,
    blocked_rows: int,
    reasons: list[str],
    observed: str,
    maintenance_request_id: str | None = None,
) -> ApplyResult:
    result = ApplyResult(
        status=status,
        approved=approved,
        eligible_rows=eligible_rows,
        applied_rows=0,
        token_rows_updated=0,
        created_token_rows=0,
        return_ledger_rows=0,
        stock_event_rows=0,
        blocked_rows=blocked_rows,
        snapshot_dir=None,
        applied_path=root / OUT_APPLIED,
        manifest_path=root / OUT_MANIFEST,
        reasons=reasons,
    )
    safe_to_csv(pd.DataFrame(columns=APPLIED_COLUMNS), result.applied_path, index=False)
    _write_manifest(result.manifest_path, _manifest_payload(result, observed, maintenance_request_id))
    return result


def apply_return_token_reuse_repair(
    *,
    root: Path | str | None = None,
    approve_protected_b009_repair: bool = False,
    observed_utc: str | None = None,
    maintenance_request_id: str | None = None,
) -> ApplyResult:
    root_path = Path(root or ".")
    observed = observed_utc or _utc_now_text()

    if not approve_protected_b009_repair:
        return _empty_result(
            root=root_path,
            status="blocked_needs_approval",
            approved=False,
            eligible_rows=0,
            blocked_rows=0,
            reasons=["Protected B009 local repair approval flag was not supplied."],
            observed=observed,
            maintenance_request_id=maintenance_request_id,
        )

    worker_locks = _active_paths(root_path, B_WORKER_LOCKS)
    supervisor_locks = _active_paths(root_path, B_SUPERVISOR_LOCKS)
    if (worker_locks or supervisor_locks) and not _maintenance_ready_for_request(root_path, maintenance_request_id):
        return _empty_result(
            root=root_path,
            status="blocked_active_b_owner",
            approved=True,
            eligible_rows=0,
            blocked_rows=0,
            reasons=[
                "B owner lock exists and matching maintenance.ready is not present.",
                "active_worker_locks=" + ";".join(worker_locks),
                "active_supervisor_locks=" + ";".join(supervisor_locks),
            ],
            observed=observed,
            maintenance_request_id=maintenance_request_id,
        )

    preview = _eligible_preview_rows(_read_csv(root_path / PREVIEW))
    ledger = _read_csv(root_path / TOKEN_LEDGER)
    if preview.empty:
        reasons = _validate_ledger_only(ledger)
        if reasons:
            return _empty_result(
                root=root_path,
                status="blocked_validation_failed",
                approved=True,
                eligible_rows=0,
                blocked_rows=0,
                reasons=reasons,
                observed=observed,
                maintenance_request_id=maintenance_request_id,
            )
        ledger = _ensure_columns(
            ledger,
            [
                "token_id",
                "seller_sku",
                "cost_per_unit",
                "currency",
                "status",
                "received_date",
                "notes",
                "source",
                "source_batch_id",
                "source_order_key",
                "created_at",
                "allocated_order_id",
                "allocated_date",
                "return_order_id",
                "return_date",
                "return_event_id",
                "last_return_order_id",
                "last_return_date",
                "last_return_event_id",
                "disposed_event_id",
                "disposed_date",
                "disposed_reason",
            ],
        )
        drift = _manifest_closure_drift_rows(root_path, ledger)
        if drift.empty:
            return _empty_result(
                root=root_path,
                status="blocked_validation_failed",
                approved=True,
                eligible_rows=0,
                blocked_rows=0,
                reasons=["No eligible B009 preview rows and no prior B009 closure drift rows found."],
                observed=observed,
                maintenance_request_id=maintenance_request_id,
            )
        ledger["token_id_norm"] = ledger["token_id"].map(_text)
        applied_rows: list[dict[str, str]] = []
        blocked_reasons: list[str] = []
        for _, row in drift.iterrows():
            order_id = _text(row.get("order_id", ""))
            event_id = _text(row.get("event_id", ""))
            original_token_id = _text(row.get("original_token_id", ""))
            matches = ledger.index[ledger["token_id_norm"] == original_token_id]
            if matches.empty:
                blocked_reasons.append(f"{order_id}: original token {original_token_id} is missing.")
                continue
            idx = int(matches[0])
            previous_status = _text(ledger.at[idx, "status"])
            if previous_status.lower() == "returned_complete":
                continue
            return_date = _text(row.get("return_date", "")) or _text(ledger.at[idx, "return_date"]) or observed
            ledger.at[idx, "status"] = "returned_complete"
            ledger.at[idx, "notes"] = _append_note(ledger.at[idx, "notes"], f"return_closed:{event_id}")
            if order_id:
                ledger.at[idx, "last_return_order_id"] = order_id
            ledger.at[idx, "last_return_date"] = return_date
            if _text(ledger.at[idx, "return_event_id"]):
                ledger.at[idx, "last_return_event_id"] = _text(ledger.at[idx, "return_event_id"])
            applied = {column: _text(row.get(column, "")) for column in APPLIED_COLUMNS}
            applied["previous_status"] = previous_status
            applied["original_new_status"] = "returned_complete"
            applied["reusable_new_status"] = _text(applied.get("reusable_new_status", "")) or "existing_reusable_token"
            applied["return_date"] = return_date
            applied["action"] = "restored_returned_complete_from_prior_b009_manifest"
            applied_rows.append(applied)
        if not applied_rows:
            return _empty_result(
                root=root_path,
                status="blocked_no_rows_applied",
                approved=True,
                eligible_rows=len(drift),
                blocked_rows=len(drift),
                reasons=blocked_reasons or ["Prior B009 manifest drift rows were already closed."],
                observed=observed,
                maintenance_request_id=maintenance_request_id,
            )
        snapshot_dir = _snapshot_files(root_path, observed)
        applied = pd.DataFrame(applied_rows, columns=APPLIED_COLUMNS)
        ledger = ledger.drop(columns=["token_id_norm"], errors="ignore")
        try:
            safe_to_csv(ledger, root_path / TOKEN_LEDGER, index=False)
            if (root_path / TOKEN_LEDGER_LIVE_COPY).exists():
                safe_to_csv(ledger, root_path / TOKEN_LEDGER_LIVE_COPY, index=False)
            safe_to_csv(applied, root_path / OUT_APPLIED, index=False)
        except Exception:
            _restore_snapshot(root_path, snapshot_dir)
            raise
        result = ApplyResult(
            status="applied",
            approved=True,
            eligible_rows=len(drift),
            applied_rows=len(applied_rows),
            token_rows_updated=len(applied_rows),
            created_token_rows=0,
            return_ledger_rows=0,
            stock_event_rows=0,
            blocked_rows=len(blocked_reasons),
            snapshot_dir=snapshot_dir,
            applied_path=root_path / OUT_APPLIED,
            manifest_path=root_path / OUT_MANIFEST,
            reasons=blocked_reasons,
        )
        _write_manifest(result.manifest_path, _manifest_payload(result, observed, maintenance_request_id))
        return result

    reasons = _validate_inputs(preview, ledger)
    if reasons:
        return _empty_result(
            root=root_path,
            status="blocked_validation_failed",
            approved=True,
            eligible_rows=len(preview),
            blocked_rows=len(preview),
            reasons=reasons,
            observed=observed,
            maintenance_request_id=maintenance_request_id,
        )

    ledger = _ensure_columns(
        ledger,
        [
            "token_id",
            "seller_sku",
            "cost_per_unit",
            "currency",
            "status",
            "received_date",
            "notes",
            "source",
            "source_batch_id",
            "source_order_key",
            "created_at",
            "allocated_order_id",
            "allocated_date",
            "return_order_id",
            "return_date",
            "return_event_id",
            "last_return_order_id",
            "last_return_date",
            "last_return_event_id",
            "disposed_event_id",
            "disposed_date",
            "disposed_reason",
        ],
    )
    return_ledger = _ensure_columns(_read_csv(root_path / TOKEN_RETURN_LEDGER), RETURN_LEDGER_COLUMNS)
    stock_events = _ensure_columns(_read_csv(root_path / STOCK_ADJUSTMENT_EVENTS), STOCK_EVENT_COLUMNS)

    ledger["sku_norm"] = ledger["seller_sku"].map(_norm_sku)
    ledger["status_norm"] = ledger["status"].map(lambda value: _text(value).lower())
    existing_token_ids = set(ledger["token_id"].astype(str).map(_text).tolist())
    existing_return_events = set(return_ledger["return_event_id"].astype(str).map(_text).tolist())
    existing_stock_events = set(stock_events["event_id"].astype(str).map(_text).tolist())
    return_event_token_ids = {
        _text(row.get("return_event_id", "")): _text(row.get("token_id", ""))
        for _, row in return_ledger.iterrows()
        if _text(row.get("return_event_id", "")) and _text(row.get("token_id", ""))
    }

    applied_rows: list[dict[str, str]] = []
    return_rows: list[dict[str, str]] = []
    stock_rows: list[dict[str, str]] = []
    blocked_reasons: list[str] = []

    for _, row in preview.iterrows():
        order_id = _text(row.get("order_id", ""))
        sku = _norm_sku(row.get("sku", ""))
        pending_ids = _split(row.get("returned_pending_token_ids", ""))
        if not order_id or not sku or not pending_ids:
            blocked_reasons.append(f"{order_id}|{sku}: missing order, SKU, or returned-pending token proof.")
            continue
        if _split(row.get("reusable_return_token_ids", "")) or _split(row.get("return_cogs_token_ids", "")):
            blocked_reasons.append(f"{order_id}|{sku}: duplicate reuse or return COGS proof already exists.")
            continue
        amazon_return_date = _text(row.get("amazon_return_date", ""))
        for seq, token_id in enumerate(pending_ids, start=1):
            matches = ledger.index[ledger["token_id"].astype(str).map(_text) == token_id]
            if matches.empty:
                blocked_reasons.append(f"{order_id}|{sku}: token {token_id} is missing from token ledger.")
                continue
            idx = int(matches[0])
            token_sku = _norm_sku(ledger.at[idx, "seller_sku"])
            if token_sku != sku:
                blocked_reasons.append(f"{order_id}|{sku}: token {token_id} belongs to SKU {token_sku}.")
                continue
            status = _text(ledger.at[idx, "status"]).lower()
            if status != "returned_pending":
                blocked_reasons.append(f"{order_id}|{sku}: token {token_id} status is {status or 'blank'}, not returned_pending.")
                continue
            token_return_order = _text(ledger.at[idx, "return_order_id"]) or _text(ledger.at[idx, "last_return_order_id"])
            if token_return_order != order_id:
                blocked_reasons.append(f"{order_id}|{sku}: token {token_id} is tied to return order {token_return_order or 'blank'}.")
                continue
            event_id = _event_id(order_id, sku, token_id, seq)
            event_exists_in_return_ledger = event_id in existing_return_events
            event_exists_in_stock_events = event_id in existing_stock_events
            if event_exists_in_return_ledger:
                new_id = return_event_token_ids.get(event_id, "")
                if not new_id:
                    blocked_reasons.append(
                        f"{order_id}|{sku}: repair event {event_id} exists in the return ledger but has no reusable token id."
                    )
                    continue
                if new_id in existing_token_ids:
                    blocked_reasons.append(
                        f"{order_id}|{sku}: repair event {event_id} already has reusable token {new_id} in the token ledger."
                    )
                    continue
            else:
                base_new_id = f"{token_id}-R{event_id}"
                new_id = base_new_id
                new_seq = 1
                while new_id in existing_token_ids:
                    new_seq += 1
                    new_id = f"{base_new_id}-{new_seq}"
            existing_token_ids.add(new_id)
            existing_return_events.add(event_id)
            if not event_exists_in_stock_events:
                existing_stock_events.add(event_id)

            previous_status = _text(ledger.at[idx, "status"])
            return_date = _text(ledger.at[idx, "return_date"]) or amazon_return_date or observed
            refund_event_id = _text(ledger.at[idx, "return_event_id"])
            ledger.at[idx, "status"] = "returned_complete"
            ledger.at[idx, "notes"] = _append_note(ledger.at[idx, "notes"], f"return_closed:{event_id}")
            ledger.at[idx, "last_return_order_id"] = order_id
            ledger.at[idx, "last_return_date"] = return_date
            ledger.at[idx, "last_return_event_id"] = refund_event_id

            new_row = {column: ledger.at[idx, column] for column in ledger.columns if column not in {"sku_norm", "status_norm"}}
            new_row["token_id"] = new_id
            new_row["status"] = "available"
            new_row["allocated_order_id"] = ""
            new_row["allocated_date"] = ""
            new_row["return_order_id"] = ""
            new_row["return_date"] = ""
            new_row["return_event_id"] = ""
            new_row["disposed_event_id"] = ""
            new_row["disposed_date"] = ""
            new_row["disposed_reason"] = ""
            new_row["notes"] = f"return_sellable_dup:{event_id}"
            ledger = pd.concat([ledger, pd.DataFrame([new_row])], ignore_index=True)

            token_cost = _text(ledger.at[idx, "cost_per_unit"])
            currency = _text(ledger.at[idx, "currency"]) or "GBP"
            if not event_exists_in_return_ledger:
                return_rows.append(
                    {
                        "return_event_id": event_id,
                        "return_date": return_date,
                        "seller_sku": sku,
                        "token_id": new_id,
                        "token_cost": token_cost,
                        "currency": currency,
                        "source": "amazon_customer_return_order_aware",
                        "event_type": "CustomerReturns",
                    }
                )
            if not event_exists_in_stock_events:
                stock_rows.append(
                    {
                        "event_id": event_id,
                        "sku": sku,
                        "event_date": return_date,
                        "event_type": "CustomerReturns",
                        "disposition": "SELLABLE",
                        "quantity": "1",
                        "applied_qty": "1",
                        "status": "ok",
                        "note": f"order_aware_customer_return:{order_id}",
                        "event_ts": observed,
                    }
                )
            applied_rows.append(
                {
                    "order_id": order_id,
                    "sku": sku,
                    "event_id": event_id,
                    "original_token_id": token_id,
                    "reusable_token_id": new_id,
                    "previous_status": previous_status,
                    "original_new_status": "returned_complete",
                    "reusable_new_status": "available",
                    "return_date": return_date,
                    "token_cost": token_cost,
                    "currency": currency,
                    "action": "closed_pending_token_and_created_reusable_return_token",
                }
            )

    if not applied_rows:
        return _empty_result(
            root=root_path,
            status="blocked_no_rows_applied",
            approved=True,
            eligible_rows=len(preview),
            blocked_rows=len(preview),
            reasons=blocked_reasons or ["No rows were eligible after validation."],
            observed=observed,
            maintenance_request_id=maintenance_request_id,
        )

    snapshot_dir = _snapshot_files(root_path, observed)
    applied = pd.DataFrame(applied_rows, columns=APPLIED_COLUMNS)
    return_rows_df = pd.DataFrame(return_rows, columns=RETURN_LEDGER_COLUMNS)
    stock_rows_df = pd.DataFrame(stock_rows, columns=STOCK_EVENT_COLUMNS)
    ledger = ledger.drop(columns=["sku_norm", "status_norm"], errors="ignore")
    return_ledger_out = pd.concat([return_ledger[RETURN_LEDGER_COLUMNS], return_rows_df], ignore_index=True)
    stock_events_out = pd.concat([stock_events[STOCK_EVENT_COLUMNS], stock_rows_df], ignore_index=True)

    try:
        safe_to_csv(ledger, root_path / TOKEN_LEDGER, index=False)
        if (root_path / TOKEN_LEDGER_LIVE_COPY).exists():
            safe_to_csv(ledger, root_path / TOKEN_LEDGER_LIVE_COPY, index=False)
        safe_to_csv(return_ledger_out, root_path / TOKEN_RETURN_LEDGER, index=False)
        safe_to_csv(stock_events_out, root_path / STOCK_ADJUSTMENT_EVENTS, index=False)
        safe_to_csv(applied, root_path / OUT_APPLIED, index=False)
    except Exception:
        _restore_snapshot(root_path, snapshot_dir)
        raise

    result = ApplyResult(
        status="applied",
        approved=True,
        eligible_rows=len(preview),
        applied_rows=len(applied_rows),
        token_rows_updated=len(applied_rows),
        created_token_rows=len(applied_rows),
        return_ledger_rows=len(return_rows),
        stock_event_rows=len(stock_rows),
        blocked_rows=len(blocked_reasons),
        snapshot_dir=snapshot_dir,
        applied_path=root_path / OUT_APPLIED,
        manifest_path=root_path / OUT_MANIFEST,
        reasons=blocked_reasons,
    )
    _write_manifest(result.manifest_path, _manifest_payload(result, observed, maintenance_request_id))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply approved local B009 order-aware returned-token reuse repair")
    parser.add_argument("--approve-protected-b009-repair", action="store_true")
    args = parser.parse_args()
    result = apply_return_token_reuse_repair(approve_protected_b009_repair=args.approve_protected_b009_repair)
    print(
        {
            "status": result.status,
            "eligible_rows": result.eligible_rows,
            "applied_rows": result.applied_rows,
            "token_rows_updated": result.token_rows_updated,
            "created_token_rows": result.created_token_rows,
            "return_ledger_rows": result.return_ledger_rows,
            "stock_event_rows": result.stock_event_rows,
            "blocked_rows": result.blocked_rows,
            "snapshot_dir": str(result.snapshot_dir or ""),
            "manifest": str(result.manifest_path),
        }
    )


if __name__ == "__main__":
    main()
