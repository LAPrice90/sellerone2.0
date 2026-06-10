from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import shutil
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.safe_file_writes import safe_to_csv


OUT = Path("out")
PREVIEW = OUT / "systems" / "B" / "refunds" / "b_refund_token_reproof_preview.csv"
TOKEN_LEDGER = OUT / "token_ledger_live.csv"
TOKEN_LEDGER_LIVE_COPY = OUT / "systems" / "B" / "live" / "token_ledger_live.csv"
REFUND_EVENTS = OUT / "refund_token_events.csv"
B_WORKER_LOCKS = [OUT / "B_cycle.lock", OUT / "systems" / "B" / "live" / "B_cycle.lock"]
B_SUPERVISOR_LOCKS = [OUT / "B_supervisor.lock", OUT / "systems" / "B" / "live" / "B_supervisor.lock"]
MAINTENANCE_REQUESTED = OUT / "locks" / "maintenance.requested"
MAINTENANCE_READY = OUT / "locks" / "maintenance.ready"
LEGACY_B_MAINTENANCE = OUT / "locks" / "b_cycle.maintenance"
SNAPSHOT_DIR = OUT / "systems" / "B" / "refunds" / "b008_reproof_snapshots"
OUT_APPLIED = OUT / "systems" / "B" / "refunds" / "b008_refund_token_reproof_applied.csv"
OUT_MANIFEST = OUT / "systems" / "B" / "refunds" / "b008_refund_token_reproof_manifest.json"

ELIGIBLE_LANES = {
    "b008_refund_token_marking",
    "b008_event_ledger_state_drift",
}

APPLIED_COLUMNS = [
    "order_id",
    "sku",
    "reproof_lane",
    "refund_event_id",
    "token_id",
    "previous_status",
    "new_status",
    "return_date",
    "action",
]


@dataclass
class ApplyResult:
    status: str
    approved: bool
    eligible_rows: int
    applied_rows: int
    token_rows_updated: int
    refund_event_rows_updated: int
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


def _num(value: object) -> float:
    raw = _text(value).replace(",", "")
    if not raw:
        return 0.0
    try:
        return float(raw)
    except Exception:
        return 0.0


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


def _manifest_payload(result: ApplyResult, observed_utc: str, maintenance_request_id: str | None = None) -> dict[str, object]:
    return {
        "status": result.status,
        "approved": result.approved,
        "observed_utc": observed_utc,
        "maintenance_request_id": maintenance_request_id or "",
        "eligible_rows": result.eligible_rows,
        "applied_rows": result.applied_rows,
        "token_rows_updated": result.token_rows_updated,
        "refund_event_rows_updated": result.refund_event_rows_updated,
        "blocked_rows": result.blocked_rows,
        "snapshot_dir": str(result.snapshot_dir or ""),
        "applied_path": str(result.applied_path),
        "manifest_path": str(result.manifest_path),
        "reasons": result.reasons,
        "safety_boundary": {
            "b_run_or_restart": "not_allowed",
            "sheets_write": "not_allowed",
            "local_db_alignment": "not_allowed",
            "roi_or_restock_use": "not_allowed",
            "token_correction_scope": "B008 local refund-token proof only",
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
    for rel_path in [PREVIEW, TOKEN_LEDGER, TOKEN_LEDGER_LIVE_COPY, REFUND_EVENTS]:
        source = root / rel_path
        if source.exists():
            target = snapshot_dir / rel_path.name
            shutil.copy2(source, target)
    return snapshot_dir


def _eligible_preview_rows(preview: pd.DataFrame) -> pd.DataFrame:
    if preview.empty:
        return preview.copy()
    work = preview.copy()
    for column in [
        "order_id",
        "sku",
        "reproof_lane",
        "reproof_readiness",
        "ledger_allocated_token_ids",
        "b008_event_ids",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
    ]:
        if column not in work.columns:
            work[column] = ""
    return work[work["reproof_lane"].isin(ELIGIBLE_LANES)].copy()


def _validate_inputs(preview: pd.DataFrame, ledger: pd.DataFrame, events: pd.DataFrame) -> list[str]:
    reasons: list[str] = []
    if preview.empty:
        reasons.append("No eligible B008 reproof rows found.")
        return reasons
    unsafe = preview[
        (preview["preview_live_write_allowed"].astype(str).str.strip() != "0")
        | (preview["roi_or_restock_use_allowed"].astype(str).str.strip() != "0")
        | (preview["sellerboard_final_truth_allowed"].astype(str).str.strip() != "0")
    ]
    if not unsafe.empty:
        reasons.append(f"Preview contains unsafe live/ROI/Sellerboard flags on {len(unsafe)} eligible rows.")
    if ledger.empty:
        reasons.append("Token ledger is missing or empty.")
    if events.empty:
        reasons.append("Refund token events file is missing or empty.")
    required_ledger = {"token_id", "seller_sku", "status", "allocated_order_id"}
    required_events = {"order_id", "sku", "refund_event_id", "refund_date", "requested_qty", "applied_qty", "status"}
    missing_ledger = sorted(required_ledger - set(ledger.columns))
    missing_events = sorted(required_events - set(events.columns))
    if missing_ledger:
        reasons.append(f"Token ledger missing columns: {','.join(missing_ledger)}")
    if missing_events:
        reasons.append(f"Refund token events missing columns: {','.join(missing_events)}")
    return reasons


def apply_refund_token_reproof(
    *,
    root: Path | str | None = None,
    approve_protected_b008_repair: bool = False,
    observed_utc: str | None = None,
    maintenance_request_id: str | None = None,
) -> ApplyResult:
    root_path = Path(root or ".")
    observed = observed_utc or _utc_now_text()
    applied_path = root_path / OUT_APPLIED
    manifest_path = root_path / OUT_MANIFEST
    empty_applied = pd.DataFrame(columns=APPLIED_COLUMNS)

    if not approve_protected_b008_repair:
        result = ApplyResult(
            status="blocked_needs_approval",
            approved=False,
            eligible_rows=0,
            applied_rows=0,
            token_rows_updated=0,
            refund_event_rows_updated=0,
            blocked_rows=0,
            snapshot_dir=None,
            applied_path=applied_path,
            manifest_path=manifest_path,
            reasons=["Protected B008 local repair approval flag was not supplied."],
        )
        safe_to_csv(empty_applied, applied_path, index=False)
        _write_manifest(manifest_path, _manifest_payload(result, observed, maintenance_request_id))
        return result

    worker_locks = _active_paths(root_path, B_WORKER_LOCKS)
    supervisor_locks = _active_paths(root_path, B_SUPERVISOR_LOCKS)
    if (worker_locks or supervisor_locks) and not _maintenance_ready_for_request(root_path, maintenance_request_id):
        result = ApplyResult(
            status="blocked_active_b_owner",
            approved=True,
            eligible_rows=0,
            applied_rows=0,
            token_rows_updated=0,
            refund_event_rows_updated=0,
            blocked_rows=0,
            snapshot_dir=None,
            applied_path=applied_path,
            manifest_path=manifest_path,
            reasons=[
                "B owner lock exists and matching maintenance.ready is not present.",
                "active_worker_locks=" + ";".join(worker_locks),
                "active_supervisor_locks=" + ";".join(supervisor_locks),
            ],
        )
        safe_to_csv(empty_applied, applied_path, index=False)
        _write_manifest(manifest_path, _manifest_payload(result, observed, maintenance_request_id))
        return result

    preview = _eligible_preview_rows(_read_csv(root_path / PREVIEW))
    ledger = _read_csv(root_path / TOKEN_LEDGER)
    events = _read_csv(root_path / REFUND_EVENTS)
    reasons = _validate_inputs(preview, ledger, events)
    if reasons:
        result = ApplyResult(
            status="blocked_validation_failed",
            approved=True,
            eligible_rows=len(preview),
            applied_rows=0,
            token_rows_updated=0,
            refund_event_rows_updated=0,
            blocked_rows=len(preview),
            snapshot_dir=None,
            applied_path=applied_path,
            manifest_path=manifest_path,
            reasons=reasons,
        )
        safe_to_csv(empty_applied, applied_path, index=False)
        _write_manifest(manifest_path, _manifest_payload(result, observed, maintenance_request_id))
        return result

    ledger = _ensure_columns(
        ledger,
        [
            "token_id",
            "seller_sku",
            "status",
            "allocated_order_id",
            "return_order_id",
            "return_date",
            "return_event_id",
            "last_return_order_id",
            "last_return_date",
            "last_return_event_id",
            "notes",
        ],
    )
    events = _ensure_columns(
        events,
        [
            "order_id",
            "sku",
            "refund_date",
            "requested_qty",
            "applied_qty",
            "status",
            "note",
            "refund_event_id",
            "event_ts",
        ],
    )
    ledger["sku_norm"] = ledger["seller_sku"].map(_norm_sku)
    events["order_id_norm"] = events["order_id"].map(_text)
    events["sku_norm"] = events["sku"].map(_norm_sku)

    applied_rows: list[dict[str, str]] = []
    event_updates: dict[str, int] = {}
    blocked_reasons: list[str] = []

    for _, row in preview.iterrows():
        order_id = _text(row.get("order_id", ""))
        sku = _norm_sku(row.get("sku", ""))
        event_ids = _split(row.get("b008_event_ids", ""))
        token_ids = _split(row.get("ledger_allocated_token_ids", ""))
        if not order_id or not sku or not event_ids or not token_ids:
            blocked_reasons.append(f"{order_id}|{sku}: missing order, sku, refund event, or ledger token proof.")
            continue
        event_id = event_ids[0]
        event_match = events.index[events["refund_event_id"].astype(str) == event_id]
        if event_match.empty:
            blocked_reasons.append(f"{order_id}|{sku}: refund event {event_id} is not present.")
            continue
        event_idx = int(event_match[0])
        refund_date = _text(events.at[event_idx, "refund_date"]) or observed
        updated_for_row = 0
        for token_id in token_ids:
            token_match = ledger.index[ledger["token_id"].astype(str) == token_id]
            if token_match.empty:
                blocked_reasons.append(f"{order_id}|{sku}: token {token_id} is not present in token ledger.")
                continue
            token_idx = int(token_match[0])
            token_sku = _norm_sku(ledger.at[token_idx, "seller_sku"])
            if token_sku != sku:
                blocked_reasons.append(f"{order_id}|{sku}: token {token_id} belongs to SKU {token_sku}.")
                continue
            status = _text(ledger.at[token_idx, "status"]).lower()
            if status in {"returned_complete", "available", "warehouse", "research_pending", "unsellable", "disposed"}:
                blocked_reasons.append(f"{order_id}|{sku}: token {token_id} has protected status {status}.")
                continue
            previous_status = _text(ledger.at[token_idx, "status"])
            ledger.at[token_idx, "status"] = "returned_pending"
            ledger.at[token_idx, "return_order_id"] = order_id
            ledger.at[token_idx, "return_date"] = refund_date
            ledger.at[token_idx, "return_event_id"] = event_id
            applied_rows.append(
                {
                    "order_id": order_id,
                    "sku": sku,
                    "reproof_lane": _text(row.get("reproof_lane", "")),
                    "refund_event_id": event_id,
                    "token_id": token_id,
                    "previous_status": previous_status,
                    "new_status": "returned_pending",
                    "return_date": refund_date,
                    "action": "marked_returned_pending",
                }
            )
            updated_for_row += 1
        if updated_for_row:
            event_updates[event_id] = event_updates.get(event_id, 0) + updated_for_row

    for event_id, added_qty in event_updates.items():
        event_match = events.index[events["refund_event_id"].astype(str) == event_id]
        if event_match.empty:
            continue
        idx = int(event_match[0])
        prior_applied = _num(events.at[idx, "applied_qty"])
        requested = _num(events.at[idx, "requested_qty"])
        new_applied = max(prior_applied, added_qty)
        events.at[idx, "applied_qty"] = str(int(new_applied)) if float(new_applied).is_integer() else str(new_applied)
        events.at[idx, "status"] = "ok" if requested <= 0 or new_applied >= requested else "partial"
        note = _text(events.at[idx, "note"])
        marker = "controlled_b008_local_reproof"
        events.at[idx, "note"] = marker if not note else note if marker in note else f"{note};{marker}"

    if not applied_rows:
        result = ApplyResult(
            status="blocked_no_rows_applied",
            approved=True,
            eligible_rows=len(preview),
            applied_rows=0,
            token_rows_updated=0,
            refund_event_rows_updated=0,
            blocked_rows=len(preview),
            snapshot_dir=None,
            applied_path=applied_path,
            manifest_path=manifest_path,
            reasons=blocked_reasons or ["No rows were eligible after validation."],
        )
        safe_to_csv(empty_applied, applied_path, index=False)
        _write_manifest(manifest_path, _manifest_payload(result, observed, maintenance_request_id))
        return result

    snapshot_dir = _snapshot_files(root_path, observed)
    applied = pd.DataFrame(applied_rows, columns=APPLIED_COLUMNS)
    ledger = ledger.drop(columns=["sku_norm"], errors="ignore")
    events = events.drop(columns=["order_id_norm", "sku_norm"], errors="ignore")
    try:
        safe_to_csv(ledger, root_path / TOKEN_LEDGER, index=False)
        if (root_path / TOKEN_LEDGER_LIVE_COPY).exists():
            safe_to_csv(ledger, root_path / TOKEN_LEDGER_LIVE_COPY, index=False)
        safe_to_csv(events, root_path / REFUND_EVENTS, index=False)
        safe_to_csv(applied, applied_path, index=False)
    except Exception:
        for rel_path in [TOKEN_LEDGER, TOKEN_LEDGER_LIVE_COPY, REFUND_EVENTS]:
            source = snapshot_dir / rel_path.name
            target = root_path / rel_path
            if source.exists():
                shutil.copy2(source, target)
        raise

    result = ApplyResult(
        status="applied",
        approved=True,
        eligible_rows=len(preview),
        applied_rows=len(applied_rows),
        token_rows_updated=len(applied_rows),
        refund_event_rows_updated=len(event_updates),
        blocked_rows=len(blocked_reasons),
        snapshot_dir=snapshot_dir,
        applied_path=applied_path,
        manifest_path=manifest_path,
        reasons=blocked_reasons,
    )
    _write_manifest(manifest_path, _manifest_payload(result, observed, maintenance_request_id))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply approved local B008 refund-token reproof repair")
    parser.add_argument("--approve-protected-b008-repair", action="store_true")
    args = parser.parse_args()
    result = apply_refund_token_reproof(approve_protected_b008_repair=args.approve_protected_b008_repair)
    print(
        {
            "status": result.status,
            "eligible_rows": result.eligible_rows,
            "applied_rows": result.applied_rows,
            "token_rows_updated": result.token_rows_updated,
            "refund_event_rows_updated": result.refund_event_rows_updated,
            "blocked_rows": result.blocked_rows,
            "snapshot_dir": str(result.snapshot_dir or ""),
            "manifest": str(result.manifest_path),
        }
    )


if __name__ == "__main__":
    main()
