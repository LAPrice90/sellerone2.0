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
PREVIEW = OUT / "systems" / "B" / "refunds" / "b_disposition_correction_apply_preview.csv"
TOKEN_LEDGER = OUT / "token_ledger_live.csv"
TOKEN_LEDGER_LIVE_COPY = OUT / "systems" / "B" / "live" / "token_ledger_live.csv"
TOKEN_ALLOCATIONS = OUT / "token_allocations_live.csv"
TOKEN_ALLOCATIONS_LIVE_COPY = OUT / "systems" / "B" / "live" / "token_allocations_live.csv"
TOKEN_COGS = OUT / "token_cogs_ledger.csv"
B_WORKER_LOCKS = [OUT / "B_cycle.lock", OUT / "systems" / "B" / "live" / "B_cycle.lock"]
B_SUPERVISOR_LOCKS = [OUT / "B_supervisor.lock", OUT / "systems" / "B" / "live" / "B_supervisor.lock"]
MAINTENANCE_REQUESTED = OUT / "locks" / "maintenance.requested"
MAINTENANCE_READY = OUT / "locks" / "maintenance.ready"
LEGACY_B_MAINTENANCE = OUT / "locks" / "b_cycle.maintenance"
REPAIR_DIR = OUT / "systems" / "B" / "refunds"
SNAPSHOT_DIR = REPAIR_DIR / "b062_disposition_correction_swap_snapshots"
APPLIED_PATH = REPAIR_DIR / "b_disposition_correction_swap_applied.csv"
MANIFEST_PATH = REPAIR_DIR / "b_disposition_correction_swap_manifest.json"

ELIGIBLE_LANES = {
    "shipped_order_replacement_swap_preview_ready",
    "unshipped_order_replacement_swap_preview_ready",
}
APPROVAL_REFERENCE = "B062_DISPOSITION_CORRECTION_SWAP_20260603_LUKE_APPROVED_B061"

APPLIED_COLUMNS = [
    "return_order_id",
    "sku",
    "amazon_return_disposition",
    "downstream_order_id",
    "downstream_order_status",
    "reused_token_id",
    "replacement_token_id",
    "previous_reused_status",
    "new_reused_status",
    "previous_replacement_status",
    "new_replacement_status",
    "allocation_rows_updated",
    "cogs_rows_updated",
    "old_token_cost",
    "replacement_token_cost",
    "currency",
    "correction_apply_lane",
    "action",
]


@dataclass
class ApplyResult:
    status: str
    approved: bool
    eligible_rows: int
    applied_rows: int
    token_rows_updated: int
    allocation_rows_updated: int
    cogs_rows_updated: int
    blocked_rows: int
    snapshot_dir: Path | None
    applied_path: Path
    manifest_path: Path
    reasons: list[str]


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, keep_default_na=False).fillna("")


def _text(value: object) -> str:
    return str(value or "").strip()


def _norm(value: object) -> str:
    return _text(value).upper()


def _num(value: object) -> float:
    raw = _text(value).replace(",", "")
    if not raw:
        return 0.0
    try:
        return float(raw)
    except Exception:
        return 0.0


def _money(value: object) -> str:
    amount = round(_num(value), 2)
    return f"{amount:.2f}".rstrip("0").rstrip(".") if amount % 1 else f"{amount:.2f}".rstrip("0").rstrip(".")


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


def _target_rows(preview: pd.DataFrame) -> pd.DataFrame:
    if preview.empty:
        return preview.copy()
    work = preview.copy()
    for column in [
        "return_order_id",
        "sku",
        "amazon_return_disposition",
        "reused_token_id",
        "downstream_order_id",
        "downstream_order_status",
        "replacement_candidate_token_id",
        "replacement_candidate_cost",
        "replacement_candidate_currency",
        "correction_apply_lane",
        "protected_decision_required",
        "requires_luke_live_apply",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
    ]:
        if column not in work.columns:
            work[column] = ""
    return work[work["correction_apply_lane"].astype(str).str.strip().isin(ELIGIBLE_LANES)].copy()


def _validate(
    *,
    preview: pd.DataFrame,
    ledger: pd.DataFrame,
    allocations: pd.DataFrame,
    cogs: pd.DataFrame,
) -> list[str]:
    reasons: list[str] = []
    if preview.empty:
        return ["No B062 replacement-swap preview-ready rows found."]
    unsafe = preview[
        (preview["protected_decision_required"].astype(str).str.strip() != "1")
        | (preview["requires_luke_live_apply"].astype(str).str.strip() != "1")
        | (preview["preview_live_write_allowed"].astype(str).str.strip() != "0")
        | (preview["roi_or_restock_use_allowed"].astype(str).str.strip() != "0")
        | (preview["sellerboard_final_truth_allowed"].astype(str).str.strip() != "0")
    ]
    if not unsafe.empty:
        reasons.append(f"Preview contains unsafe or unprotected rows: {len(unsafe)}.")
    if ledger.empty:
        reasons.append("Token ledger is missing or empty.")
    if allocations.empty:
        reasons.append("Token allocations file is missing or empty.")
    if cogs.empty:
        reasons.append("Token COGS ledger is missing or empty.")
    ledger = _ensure_columns(ledger, ["token_id", "seller_sku", "status", "allocated_order_id"])
    allocations = _ensure_columns(allocations, ["order_id", "seller_sku", "token_id"])
    cogs = _ensure_columns(cogs, ["order_id", "seller_sku", "token_id"])
    used_replacements: set[str] = set()
    for _, row in preview.iterrows():
        return_order = _text(row.get("return_order_id", ""))
        sku = _norm(row.get("sku", ""))
        downstream_order = _text(row.get("downstream_order_id", ""))
        reused_token = _text(row.get("reused_token_id", ""))
        replacement = _text(row.get("replacement_candidate_token_id", ""))
        label = f"{return_order}|{sku}|{downstream_order}"
        if not all([return_order, sku, downstream_order, reused_token, replacement]):
            reasons.append(f"{label}: missing return order, SKU, downstream order, reused token, or replacement token.")
            continue
        if replacement in used_replacements:
            reasons.append(f"{label}: replacement token {replacement} is used more than once in the preview.")
        used_replacements.add(replacement)
        reused_rows = ledger[ledger["token_id"].map(_text) == reused_token]
        replacement_rows = ledger[ledger["token_id"].map(_text) == replacement]
        if len(reused_rows) != 1:
            reasons.append(f"{label}: reused token {reused_token} is not present exactly once.")
        else:
            reused = reused_rows.iloc[0]
            if _norm(reused.get("seller_sku", "")) != sku:
                reasons.append(f"{label}: reused token belongs to SKU {_text(reused.get('seller_sku', ''))}.")
            if _text(reused.get("status", "")).lower() != "allocated":
                reasons.append(f"{label}: reused token is not allocated.")
            if _text(reused.get("allocated_order_id", "")) != downstream_order:
                reasons.append(f"{label}: reused token is not allocated to the downstream order.")
        if len(replacement_rows) != 1:
            reasons.append(f"{label}: replacement token {replacement} is not present exactly once.")
        else:
            replacement_row = replacement_rows.iloc[0]
            if _norm(replacement_row.get("seller_sku", "")) != sku:
                reasons.append(f"{label}: replacement token belongs to SKU {_text(replacement_row.get('seller_sku', ''))}.")
            if _text(replacement_row.get("status", "")).lower() != "available":
                reasons.append(f"{label}: replacement token is not available.")
            if _text(replacement_row.get("allocated_order_id", "")):
                reasons.append(f"{label}: replacement token is already allocated.")
        allocation_rows = allocations[
            (allocations["order_id"].map(_text) == downstream_order)
            & (allocations["seller_sku"].map(_norm) == sku)
            & (allocations["token_id"].map(_text) == reused_token)
        ]
        replacement_allocation_rows = allocations[
            (allocations["order_id"].map(_text) == downstream_order)
            & (allocations["seller_sku"].map(_norm) == sku)
            & (allocations["token_id"].map(_text) == replacement)
        ]
        if len(allocation_rows) != 1:
            reasons.append(f"{label}: reused allocation row count is {len(allocation_rows)}, expected 1.")
        if len(replacement_allocation_rows) != 0:
            reasons.append(f"{label}: replacement allocation row already exists.")
        cogs_rows = cogs[
            (cogs["order_id"].map(_text) == downstream_order)
            & (cogs["seller_sku"].map(_norm) == sku)
            & (cogs["token_id"].map(_text) == reused_token)
        ]
        replacement_cogs_rows = cogs[
            (cogs["order_id"].map(_text) == downstream_order)
            & (cogs["seller_sku"].map(_norm) == sku)
            & (cogs["token_id"].map(_text) == replacement)
        ]
        if len(cogs_rows) != 1:
            reasons.append(f"{label}: reused COGS row count is {len(cogs_rows)}, expected 1.")
        if len(replacement_cogs_rows) != 0:
            reasons.append(f"{label}: replacement COGS row already exists.")
    return sorted(set(reasons))


def _manifest_payload(result: ApplyResult, observed_utc: str, maintenance_request_id: str | None = None) -> dict[str, object]:
    return {
        "status": result.status,
        "approved": result.approved,
        "observed_utc": observed_utc,
        "approval_reference": APPROVAL_REFERENCE,
        "maintenance_request_id": maintenance_request_id or "",
        "eligible_rows": result.eligible_rows,
        "applied_rows": result.applied_rows,
        "token_rows_updated": result.token_rows_updated,
        "allocation_rows_updated": result.allocation_rows_updated,
        "cogs_rows_updated": result.cogs_rows_updated,
        "blocked_rows": result.blocked_rows,
        "snapshot_dir": str(result.snapshot_dir or ""),
        "applied_path": str(result.applied_path),
        "manifest_path": str(result.manifest_path),
        "reasons": result.reasons,
        "safety_boundary": {
            "b_run_or_restart": "not_performed_by_this_script",
            "sheets_write": "not_allowed",
            "local_db_alignment": "not_allowed",
            "output_deletion": "not_allowed",
            "roi_or_restock_use": "not_allowed",
            "repair_scope": "B062 four replacement-swap ready disposition correction rows only",
        },
    }


def _write_manifest(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{Path.cwd().name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _snapshot_files(root: Path, observed_utc: str) -> Path:
    safe_stamp = observed_utc.replace(":", "").replace("-", "").replace("T", "_").replace("Z", "Z")
    snapshot_dir = root / SNAPSHOT_DIR / safe_stamp
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    for rel_path in [
        PREVIEW,
        TOKEN_LEDGER,
        TOKEN_LEDGER_LIVE_COPY,
        TOKEN_ALLOCATIONS,
        TOKEN_ALLOCATIONS_LIVE_COPY,
        TOKEN_COGS,
    ]:
        source = root / rel_path
        if source.exists():
            shutil.copy2(source, snapshot_dir / rel_path.name)
    return snapshot_dir


def _restore_snapshot(root: Path, snapshot_dir: Path) -> None:
    for rel_path in [TOKEN_LEDGER, TOKEN_LEDGER_LIVE_COPY, TOKEN_ALLOCATIONS, TOKEN_ALLOCATIONS_LIVE_COPY, TOKEN_COGS]:
        source = snapshot_dir / rel_path.name
        if source.exists():
            target = root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def _blocked_result(
    *,
    root: Path,
    observed_utc: str,
    approved: bool,
    status: str,
    reasons: list[str],
    eligible_rows: int = 0,
    blocked_rows: int = 0,
    maintenance_request_id: str | None = None,
) -> ApplyResult:
    result = ApplyResult(
        status=status,
        approved=approved,
        eligible_rows=eligible_rows,
        applied_rows=0,
        token_rows_updated=0,
        allocation_rows_updated=0,
        cogs_rows_updated=0,
        blocked_rows=blocked_rows,
        snapshot_dir=None,
        applied_path=root / APPLIED_PATH,
        manifest_path=root / MANIFEST_PATH,
        reasons=reasons,
    )
    safe_to_csv(pd.DataFrame(columns=APPLIED_COLUMNS), result.applied_path, index=False)
    _write_manifest(result.manifest_path, _manifest_payload(result, observed_utc, maintenance_request_id))
    return result


def _recalculate_cogs_fields(row: pd.Series, token_cost: str, currency: str, observed_utc: str) -> dict[str, str]:
    exvat = round(_num(token_cost), 2)
    vat = round(exvat * 0.20, 2)
    total = round(exvat + vat, 2)
    updates = {
        "token_cost": _money(exvat),
        "currency": currency or _text(row.get("currency", "")) or "GBP",
        "built_at": observed_utc,
        "cogs_exvat": _money(exvat),
        "cogs_vat": _money(vat),
        "cogs_total": _money(total),
    }
    return updates


def apply_disposition_correction_swap(
    *,
    root: Path | str | None = None,
    approve_protected_disposition_correction_swap: bool = False,
    observed_utc: str | None = None,
    maintenance_request_id: str | None = None,
) -> ApplyResult:
    root_path = Path(root or ".")
    observed = observed_utc or _utc_now_text()

    if not approve_protected_disposition_correction_swap:
        return _blocked_result(
            root=root_path,
            observed_utc=observed,
            approved=False,
            status="blocked_needs_approval",
            reasons=["Protected B062 disposition correction swap approval flag was not supplied."],
            maintenance_request_id=maintenance_request_id,
        )

    worker_locks = _active_paths(root_path, B_WORKER_LOCKS)
    supervisor_locks = _active_paths(root_path, B_SUPERVISOR_LOCKS)
    if (worker_locks or supervisor_locks) and not _maintenance_ready_for_request(root_path, maintenance_request_id):
        return _blocked_result(
            root=root_path,
            observed_utc=observed,
            approved=True,
            status="blocked_active_b_owner",
            reasons=[
                "B owner lock exists and matching maintenance.ready is not present.",
                "active_worker_locks=" + ";".join(worker_locks),
                "active_supervisor_locks=" + ";".join(supervisor_locks),
            ],
            maintenance_request_id=maintenance_request_id,
        )

    preview = _target_rows(_read_csv(root_path / PREVIEW))
    ledger = _ensure_columns(
        _read_csv(root_path / TOKEN_LEDGER),
        [
            "token_id",
            "seller_sku",
            "status",
            "allocated_order_id",
            "allocated_date",
            "last_return_order_id",
            "last_return_date",
            "notes",
            "disposed_date",
            "disposed_reason",
            "cost_per_unit",
            "currency",
        ],
    )
    allocations = _ensure_columns(
        _read_csv(root_path / TOKEN_ALLOCATIONS),
        ["order_id", "order_date", "seller_sku", "token_id", "token_cost", "currency", "allocation_date", "source_level", "notes"],
    )
    cogs = _ensure_columns(
        _read_csv(root_path / TOKEN_COGS),
        [
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
        ],
    )
    reasons = _validate(preview=preview, ledger=ledger, allocations=allocations, cogs=cogs)
    if reasons:
        return _blocked_result(
            root=root_path,
            observed_utc=observed,
            approved=True,
            status="blocked_validation_failed",
            reasons=reasons,
            eligible_rows=len(preview),
            blocked_rows=len(preview),
            maintenance_request_id=maintenance_request_id,
        )

    snapshot_dir = _snapshot_files(root_path, observed)
    applied_rows: list[dict[str, str]] = []
    token_rows_updated = 0
    allocation_rows_updated = 0
    cogs_rows_updated = 0

    try:
        for _, preview_row in preview.iterrows():
            return_order = _text(preview_row.get("return_order_id", ""))
            sku = _norm(preview_row.get("sku", ""))
            downstream_order = _text(preview_row.get("downstream_order_id", ""))
            reused_token = _text(preview_row.get("reused_token_id", ""))
            replacement_token = _text(preview_row.get("replacement_candidate_token_id", ""))
            replacement_cost = _text(preview_row.get("replacement_candidate_cost", ""))
            replacement_currency = _text(preview_row.get("replacement_candidate_currency", "")) or "GBP"
            reused_idx = int(ledger.index[ledger["token_id"].map(_text) == reused_token][0])
            replacement_idx = int(ledger.index[ledger["token_id"].map(_text) == replacement_token][0])
            previous_reused_status = _text(ledger.at[reused_idx, "status"])
            previous_replacement_status = _text(ledger.at[replacement_idx, "status"])
            old_token_cost = _text(ledger.at[reused_idx, "cost_per_unit"])
            allocation_idx = int(
                allocations.index[
                    (allocations["order_id"].map(_text) == downstream_order)
                    & (allocations["seller_sku"].map(_norm) == sku)
                    & (allocations["token_id"].map(_text) == reused_token)
                ][0]
            )
            cogs_idx = int(
                cogs.index[
                    (cogs["order_id"].map(_text) == downstream_order)
                    & (cogs["seller_sku"].map(_norm) == sku)
                    & (cogs["token_id"].map(_text) == reused_token)
                ][0]
            )
            allocation_date = _text(allocations.at[allocation_idx, "allocation_date"]) or observed

            ledger.at[reused_idx, "status"] = "unsellable"
            ledger.at[reused_idx, "allocated_order_id"] = ""
            ledger.at[reused_idx, "allocated_date"] = ""
            ledger.at[reused_idx, "disposed_date"] = observed
            ledger.at[reused_idx, "disposed_reason"] = _text(preview_row.get("amazon_return_disposition", "")) or "NON_SELLABLE_RETURN"
            ledger.at[reused_idx, "notes"] = _append_note(
                ledger.at[reused_idx, "notes"],
                f"non_sellable_return_correction_blocked:{APPROVAL_REFERENCE}:{return_order}",
            )

            ledger.at[replacement_idx, "status"] = "allocated"
            ledger.at[replacement_idx, "allocated_order_id"] = downstream_order
            ledger.at[replacement_idx, "allocated_date"] = allocation_date
            ledger.at[replacement_idx, "notes"] = _append_note(
                ledger.at[replacement_idx, "notes"],
                f"non_sellable_return_replacement_swap:{APPROVAL_REFERENCE}:{return_order}:{reused_token}",
            )

            allocations.at[allocation_idx, "token_id"] = replacement_token
            allocations.at[allocation_idx, "token_cost"] = replacement_cost
            allocations.at[allocation_idx, "currency"] = replacement_currency
            allocations.at[allocation_idx, "notes"] = _append_note(
                allocations.at[allocation_idx, "notes"],
                f"non_sellable_return_replacement_swap:{APPROVAL_REFERENCE}:{return_order}:{reused_token}",
            )

            cogs.at[cogs_idx, "token_id"] = replacement_token
            for column, value in _recalculate_cogs_fields(cogs.loc[cogs_idx], replacement_cost, replacement_currency, observed).items():
                if column in cogs.columns:
                    cogs.at[cogs_idx, column] = value

            applied_rows.append(
                {
                    "return_order_id": return_order,
                    "sku": sku,
                    "amazon_return_disposition": _text(preview_row.get("amazon_return_disposition", "")),
                    "downstream_order_id": downstream_order,
                    "downstream_order_status": _text(preview_row.get("downstream_order_status", "")),
                    "reused_token_id": reused_token,
                    "replacement_token_id": replacement_token,
                    "previous_reused_status": previous_reused_status,
                    "new_reused_status": "unsellable",
                    "previous_replacement_status": previous_replacement_status,
                    "new_replacement_status": "allocated",
                    "allocation_rows_updated": "1",
                    "cogs_rows_updated": "1",
                    "old_token_cost": old_token_cost,
                    "replacement_token_cost": replacement_cost,
                    "currency": replacement_currency,
                    "correction_apply_lane": _text(preview_row.get("correction_apply_lane", "")),
                    "action": "protected_non_sellable_return_replacement_swap_applied",
                }
            )
            token_rows_updated += 2
            allocation_rows_updated += 1
            cogs_rows_updated += 1

        safe_to_csv(ledger, root_path / TOKEN_LEDGER, index=False)
        if (root_path / TOKEN_LEDGER_LIVE_COPY).exists():
            safe_to_csv(ledger, root_path / TOKEN_LEDGER_LIVE_COPY, index=False)
        safe_to_csv(allocations, root_path / TOKEN_ALLOCATIONS, index=False)
        if (root_path / TOKEN_ALLOCATIONS_LIVE_COPY).exists():
            safe_to_csv(allocations, root_path / TOKEN_ALLOCATIONS_LIVE_COPY, index=False)
        safe_to_csv(cogs, root_path / TOKEN_COGS, index=False)
        safe_to_csv(pd.DataFrame(applied_rows, columns=APPLIED_COLUMNS), root_path / APPLIED_PATH, index=False)
    except Exception:
        _restore_snapshot(root_path, snapshot_dir)
        raise

    result = ApplyResult(
        status="applied",
        approved=True,
        eligible_rows=len(preview),
        applied_rows=len(applied_rows),
        token_rows_updated=token_rows_updated,
        allocation_rows_updated=allocation_rows_updated,
        cogs_rows_updated=cogs_rows_updated,
        blocked_rows=0,
        snapshot_dir=snapshot_dir,
        applied_path=root_path / APPLIED_PATH,
        manifest_path=root_path / MANIFEST_PATH,
        reasons=[],
    )
    _write_manifest(result.manifest_path, _manifest_payload(result, observed, maintenance_request_id))
    return result


def main() -> None:
    result = apply_disposition_correction_swap(approve_protected_disposition_correction_swap=False)
    print(
        {
            "status": result.status,
            "eligible_rows": result.eligible_rows,
            "applied_rows": result.applied_rows,
            "token_rows_updated": result.token_rows_updated,
            "allocation_rows_updated": result.allocation_rows_updated,
            "cogs_rows_updated": result.cogs_rows_updated,
            "blocked_rows": result.blocked_rows,
            "snapshot_dir": str(result.snapshot_dir or ""),
            "manifest": str(result.manifest_path),
        }
    )


if __name__ == "__main__":
    main()
