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


OUT = Path("out")
PREVIEW = OUT / "systems" / "B" / "refunds" / "b_original_return_status_conflict_preview.csv"
TOKEN_LEDGER = OUT / "token_ledger_live.csv"
TOKEN_LEDGER_LIVE_COPY = OUT / "systems" / "B" / "live" / "token_ledger_live.csv"
B_WORKER_LOCKS = [OUT / "B_cycle.lock", OUT / "systems" / "B" / "live" / "B_cycle.lock"]
B_SUPERVISOR_LOCKS = [OUT / "B_supervisor.lock", OUT / "systems" / "B" / "live" / "B_supervisor.lock"]
MAINTENANCE_REQUESTED = OUT / "locks" / "maintenance.requested"
MAINTENANCE_READY = OUT / "locks" / "maintenance.ready"
LEGACY_B_MAINTENANCE = OUT / "locks" / "b_cycle.maintenance"
SNAPSHOT_DIR = OUT / "systems" / "B" / "refunds" / "b046_original_return_status_snapshots"
OUT_APPLIED = OUT / "systems" / "B" / "refunds" / "b_original_return_status_repair_applied.csv"
OUT_MANIFEST = OUT / "systems" / "B" / "refunds" / "b_original_return_status_repair_manifest.json"

APPLIED_COLUMNS = [
    "order_id",
    "sku",
    "unsafe_original_token_id",
    "previous_status",
    "new_status",
    "previous_notes",
    "new_notes",
    "allocated_order_id",
    "return_order_id",
    "last_return_order_id",
    "review_lane",
    "action",
]


@dataclass
class ApplyResult:
    status: str
    approved: bool
    eligible_rows: int
    applied_rows: int
    token_rows_updated: int
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


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _target_status_from_notes(notes: str) -> str:
    text = notes.lower()
    if "return_closed" in text:
        return "returned_complete"
    if "return_unsellable" in text:
        return "unsellable"
    if "return_researching" in text or "researching_negative" in text:
        return "research_pending"
    return ""


def _eligible_preview_rows(preview: pd.DataFrame) -> pd.DataFrame:
    if preview.empty:
        return preview.copy()
    work = preview.copy()
    for column in [
        "order_id",
        "sku",
        "unsafe_original_token_id",
        "unsafe_original_status",
        "review_lane",
        "review_readiness",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
    ]:
        if column not in work.columns:
            work[column] = ""
    unsafe_flags = (
        (work["preview_live_write_allowed"].astype(str).str.strip() != "0")
        | (work["roi_or_restock_use_allowed"].astype(str).str.strip() != "0")
        | (work["sellerboard_final_truth_allowed"].astype(str).str.strip() != "0")
    )
    lane = work["review_lane"].astype(str).str.contains("original_", na=False)
    readiness = work["review_readiness"].astype(str).str.strip() == "blocked_needs_protected_review"
    return work[lane & readiness & ~unsafe_flags].copy()


def _validate_inputs(preview: pd.DataFrame, ledger: pd.DataFrame) -> list[str]:
    reasons: list[str] = []
    if preview.empty:
        reasons.append("No eligible original returned-token status conflict rows found.")
        return reasons
    if ledger.empty:
        reasons.append("Token ledger is missing or empty.")
    required_ledger = {"token_id", "seller_sku", "status", "notes", "allocated_order_id", "return_order_id", "last_return_order_id"}
    missing_ledger = sorted(required_ledger - set(ledger.columns))
    if missing_ledger:
        reasons.append(f"Token ledger missing columns: {','.join(missing_ledger)}")
    duplicate_tokens = preview["unsafe_original_token_id"].astype(str).str.strip()
    duplicate_tokens = duplicate_tokens[duplicate_tokens != ""]
    if duplicate_tokens.duplicated().any():
        reasons.append("Preview contains duplicate unsafe original token IDs.")
    return reasons


def _snapshot_files(root: Path, observed_utc: str) -> Path:
    safe_stamp = observed_utc.replace(":", "").replace("-", "").replace("T", "_").replace("Z", "Z")
    snapshot_dir = root / SNAPSHOT_DIR / safe_stamp
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    for rel_path in [PREVIEW, TOKEN_LEDGER, TOKEN_LEDGER_LIVE_COPY]:
        source = root / rel_path
        if source.exists():
            shutil.copy2(source, snapshot_dir / rel_path.name)
    return snapshot_dir


def _restore_snapshot(root: Path, snapshot_dir: Path) -> None:
    for rel_path in [TOKEN_LEDGER, TOKEN_LEDGER_LIVE_COPY]:
        source = snapshot_dir / rel_path.name
        target = root / rel_path
        if source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def _manifest_payload(result: ApplyResult, observed_utc: str, maintenance_request_id: str | None = None) -> dict[str, object]:
    return {
        "status": result.status,
        "approved": result.approved,
        "observed_utc": observed_utc,
        "maintenance_request_id": maintenance_request_id or "",
        "eligible_rows": result.eligible_rows,
        "applied_rows": result.applied_rows,
        "token_rows_updated": result.token_rows_updated,
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
            "repair_scope": "B original returned-token status repair only",
        },
    }


def _write_manifest(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{Path.cwd().name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def apply_original_return_status_repair(
    *,
    root: Path | str | None = None,
    approve_protected_original_return_status_repair: bool = False,
    observed_utc: str | None = None,
    maintenance_request_id: str | None = None,
) -> ApplyResult:
    root_path = Path(root or ".")
    observed = observed_utc or _utc_now_text()
    applied_path = root_path / OUT_APPLIED
    manifest_path = root_path / OUT_MANIFEST
    empty_applied = pd.DataFrame(columns=APPLIED_COLUMNS)

    if not approve_protected_original_return_status_repair:
        result = ApplyResult(
            status="blocked_needs_approval",
            approved=False,
            eligible_rows=0,
            applied_rows=0,
            token_rows_updated=0,
            blocked_rows=0,
            snapshot_dir=None,
            applied_path=applied_path,
            manifest_path=manifest_path,
            reasons=["Protected original returned-token status repair approval flag was not supplied."],
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
    ledger = _ensure_columns(_read_csv(root_path / TOKEN_LEDGER), list(_read_csv(root_path / TOKEN_LEDGER).columns))
    reasons = _validate_inputs(preview, ledger)
    if reasons:
        result = ApplyResult(
            status="blocked",
            approved=True,
            eligible_rows=len(preview),
            applied_rows=0,
            token_rows_updated=0,
            blocked_rows=len(preview),
            snapshot_dir=None,
            applied_path=applied_path,
            manifest_path=manifest_path,
            reasons=reasons,
        )
        safe_to_csv(empty_applied, applied_path, index=False)
        _write_manifest(manifest_path, _manifest_payload(result, observed, maintenance_request_id))
        return result

    ledger = ledger.copy()
    for column in ["token_id", "seller_sku", "status", "notes", "allocated_order_id", "return_order_id", "last_return_order_id"]:
        if column not in ledger.columns:
            ledger[column] = ""
    ledger["token_id_norm"] = ledger["token_id"].map(_text)
    applied_rows: list[dict[str, str]] = []
    blocked_reasons: list[str] = []

    snapshot_dir = _snapshot_files(root_path, observed)
    try:
        for _, row in preview.iterrows():
            order_id = _text(row.get("order_id", ""))
            sku = _norm_sku(row.get("sku", ""))
            token_id = _text(row.get("unsafe_original_token_id", ""))
            matches = ledger.index[ledger["token_id_norm"] == token_id]
            if not order_id or not sku or not token_id:
                blocked_reasons.append(f"{order_id}|{sku}|{token_id}: missing order, SKU, or token ID.")
                continue
            if matches.empty:
                blocked_reasons.append(f"{order_id}|{sku}|{token_id}: token not found in ledger.")
                continue
            idx = int(matches[0])
            token_sku = _norm_sku(ledger.at[idx, "seller_sku"])
            if token_sku != sku:
                blocked_reasons.append(f"{order_id}|{sku}|{token_id}: token belongs to SKU {token_sku}.")
                continue
            previous_status = _text(ledger.at[idx, "status"])
            if previous_status.lower() not in {"allocated", "available", "warehouse"}:
                blocked_reasons.append(f"{order_id}|{sku}|{token_id}: token status is {previous_status or 'blank'}, not a live status.")
                continue
            token_return_order = _text(ledger.at[idx, "return_order_id"]) or _text(ledger.at[idx, "last_return_order_id"])
            if token_return_order != order_id:
                blocked_reasons.append(f"{order_id}|{sku}|{token_id}: token is tied to return order {token_return_order or 'blank'}.")
                continue
            previous_notes = _text(ledger.at[idx, "notes"])
            target_status = _target_status_from_notes(previous_notes)
            if not target_status:
                blocked_reasons.append(f"{order_id}|{sku}|{token_id}: no recognized return lifecycle marker in notes.")
                continue
            marker = f"b046_status_repair:{observed}"
            new_notes = _append_note(previous_notes, marker)
            ledger.at[idx, "status"] = target_status
            ledger.at[idx, "notes"] = new_notes
            if not _text(ledger.at[idx, "last_return_order_id"]):
                ledger.at[idx, "last_return_order_id"] = order_id
            applied_rows.append(
                {
                    "order_id": order_id,
                    "sku": sku,
                    "unsafe_original_token_id": token_id,
                    "previous_status": previous_status,
                    "new_status": target_status,
                    "previous_notes": previous_notes,
                    "new_notes": new_notes,
                    "allocated_order_id": _text(ledger.at[idx, "allocated_order_id"]),
                    "return_order_id": _text(ledger.at[idx, "return_order_id"]),
                    "last_return_order_id": _text(ledger.at[idx, "last_return_order_id"]),
                    "review_lane": _text(row.get("review_lane", "")),
                    "action": "restored_original_return_lifecycle_status",
                }
            )

        if blocked_reasons:
            _restore_snapshot(root_path, snapshot_dir)
            result = ApplyResult(
                status="blocked",
                approved=True,
                eligible_rows=len(preview),
                applied_rows=0,
                token_rows_updated=0,
                blocked_rows=len(blocked_reasons),
                snapshot_dir=snapshot_dir,
                applied_path=applied_path,
                manifest_path=manifest_path,
                reasons=blocked_reasons,
            )
            safe_to_csv(empty_applied, applied_path, index=False)
            _write_manifest(manifest_path, _manifest_payload(result, observed, maintenance_request_id))
            return result

        ledger_out = ledger.drop(columns=["token_id_norm"], errors="ignore")
        safe_to_csv(ledger_out, root_path / TOKEN_LEDGER, index=False)
        if (root_path / TOKEN_LEDGER_LIVE_COPY).exists():
            safe_to_csv(ledger_out, root_path / TOKEN_LEDGER_LIVE_COPY, index=False)
        applied = pd.DataFrame(applied_rows, columns=APPLIED_COLUMNS).fillna("")
        safe_to_csv(applied, applied_path, index=False)
    except Exception:
        _restore_snapshot(root_path, snapshot_dir)
        raise

    result = ApplyResult(
        status="applied",
        approved=True,
        eligible_rows=len(preview),
        applied_rows=len(applied_rows),
        token_rows_updated=len(applied_rows),
        blocked_rows=0,
        snapshot_dir=snapshot_dir,
        applied_path=applied_path,
        manifest_path=manifest_path,
        reasons=[],
    )
    _write_manifest(manifest_path, _manifest_payload(result, observed, maintenance_request_id))
    return result


def main() -> None:
    result = apply_original_return_status_repair()
    print(
        {
            "status": result.status,
            "eligible_rows": result.eligible_rows,
            "applied_rows": result.applied_rows,
            "token_rows_updated": result.token_rows_updated,
            "blocked_rows": result.blocked_rows,
            "snapshot_dir": str(result.snapshot_dir or ""),
            "applied": str(result.applied_path),
            "manifest": str(result.manifest_path),
        }
    )


if __name__ == "__main__":
    main()
