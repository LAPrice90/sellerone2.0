from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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
SNAPSHOT_DIR = REPAIR_DIR / "b069_disposition_cogs_correction_snapshots"
APPLIED_PATH = REPAIR_DIR / "b_disposition_cogs_correction_applied.csv"
MANIFEST_PATH = REPAIR_DIR / "b_disposition_cogs_correction_manifest.json"

ELIGIBLE_LANES = {
    "replacement_candidate_date_validation_required",
    "no_replacement_token_protected_shortage_or_exception_review",
}
APPROVAL_REFERENCE = "B069_DISPOSITION_COGS_CORRECTION_20260604_LUKE_APPROVED"
APPROVED_KEYS = {
    ("026-9612992-1390769", "EE-KTDC-KCFY", "S02-3786353-7235452", "EE-KTDC-KCFY-101125-row941-0010-RFBA15L34VWBX-retry673"),
    ("202-9939626-9381935", "3X-EXDD-TD2K", "S02-0843126-1121711", "3X-EXDD-TD2K-090925-row861-0007-RFBA15LBGBK4F-retry913"),
    ("203-0310058-9573145", "WX-L5UA-UB1Q", "205-6755145-8637917", "WX-L5UA-UB1Q-190625-row756-0473-RFBA15K4CB8J0-retry49"),
    ("203-0504563-6267559", "6V-EEC1-2S9Z", "203-1207427-5506736", "6V-EEC1-2S9Z-101125-row938-0504-R20015284027053-retry49"),
    ("204-7722459-2601949", "3X-EXDD-TD2K", "202-5805888-5886735", "3X-EXDD-TD2K-061025-row911-0011-RFBA15LBGBK4F-retry1122"),
}

APPLIED_COLUMNS = [
    "return_order_id",
    "sku",
    "amazon_return_disposition",
    "downstream_order_id",
    "reused_token_id",
    "correction_token_id",
    "previous_reused_status",
    "new_reused_status",
    "correction_token_status",
    "allocation_rows_updated",
    "cogs_rows_updated",
    "token_cost",
    "currency",
    "correction_apply_lane",
    "action",
]


@dataclass
class ApplyResult:
    status: str
    approved: bool
    eligible_rows: int
    approved_rows: int
    applied_rows: int
    created_token_rows: int
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


def _row_key(row: pd.Series) -> tuple[str, str, str, str]:
    return (
        _text(row.get("return_order_id", "")),
        _norm(row.get("sku", "")),
        _text(row.get("downstream_order_id", "")),
        _text(row.get("reused_token_id", "")),
    )


def _target_rows(preview: pd.DataFrame, approved_keys: set[tuple[str, str, str, str]]) -> tuple[pd.DataFrame, list[str]]:
    reasons: list[str] = []
    if preview.empty:
        return preview.copy(), ["B069 preview source is missing or empty."]
    work = preview.copy()
    for column in [
        "return_order_id",
        "sku",
        "amazon_return_disposition",
        "reused_token_id",
        "downstream_order_id",
        "downstream_order_status",
        "correction_apply_lane",
        "protected_decision_required",
        "requires_luke_live_apply",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
    ]:
        if column not in work.columns:
            work[column] = ""
    eligible = work[work["correction_apply_lane"].astype(str).str.strip().isin(ELIGIBLE_LANES)].copy()
    if eligible.empty:
        return eligible, ["No approved damaged-return COGS correction preview rows found."]
    eligible_keys = {_row_key(row) for _, row in eligible.iterrows()}
    unapproved = sorted(eligible_keys - approved_keys)
    missing = sorted(approved_keys - eligible_keys)
    if unapproved:
        reasons.append(f"Preview contains {len(unapproved)} unapproved damaged-return correction rows.")
    if missing:
        reasons.append(f"Preview is missing {len(missing)} approved damaged-return correction rows.")
    approved = eligible[eligible.apply(lambda row: _row_key(row) in approved_keys, axis=1)].copy()
    return approved, reasons


def _safe_fragment(value: object, *, max_len: int = 14) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]", "_", _text(value))
    text = text.strip("._-")
    return (text or "X")[:max_len]


def _correction_token_id(row: pd.Series) -> str:
    sku = _norm(row.get("sku", ""))
    return_order = _text(row.get("return_order_id", ""))
    downstream_order = _text(row.get("downstream_order_id", ""))
    reused_token = _text(row.get("reused_token_id", ""))
    digest = hashlib.sha1(f"{return_order}|{sku}|{downstream_order}|{reused_token}".encode("utf-8")).hexdigest()[:10]
    return (
        f"B069-CORR-{_safe_fragment(sku)}-"
        f"{_safe_fragment(return_order[-8:], max_len=8)}-"
        f"{_safe_fragment(downstream_order[-8:], max_len=8)}-{digest}"
    )


def _validate(
    *,
    preview: pd.DataFrame,
    ledger: pd.DataFrame,
    allocations: pd.DataFrame,
    cogs: pd.DataFrame,
    pre_reasons: list[str],
) -> list[str]:
    reasons: list[str] = list(pre_reasons)
    if preview.empty:
        return sorted(set(reasons or ["No approved damaged-return COGS correction rows found."]))
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
    ledger = _ensure_columns(
        ledger,
        ["token_id", "seller_sku", "status", "allocated_order_id", "allocated_date", "cost_per_unit", "currency"],
    )
    allocations = _ensure_columns(allocations, ["order_id", "seller_sku", "token_id", "token_cost", "currency"])
    cogs = _ensure_columns(cogs, ["order_id", "seller_sku", "token_id", "token_cost", "currency"])
    used_correction_ids: set[str] = set()
    for _, row in preview.iterrows():
        return_order, sku, downstream_order, reused_token = _row_key(row)
        label = f"{return_order}|{sku}|{downstream_order}"
        disposition = _norm(row.get("amazon_return_disposition", ""))
        if not all([return_order, sku, downstream_order, reused_token]):
            reasons.append(f"{label}: missing return order, SKU, downstream order, or reused token.")
            continue
        if disposition in {"", "SELLABLE"}:
            reasons.append(f"{label}: disposition is not a non-sellable return.")
        correction_token = _correction_token_id(row)
        if correction_token in used_correction_ids:
            reasons.append(f"{label}: correction token id {correction_token} is duplicated in preview.")
        used_correction_ids.add(correction_token)
        if (ledger["token_id"].map(_text) == correction_token).any():
            reasons.append(f"{label}: correction token {correction_token} already exists in the token ledger.")
        if (allocations["token_id"].map(_text) == correction_token).any():
            reasons.append(f"{label}: correction token {correction_token} already exists in allocations.")
        if (cogs["token_id"].map(_text) == correction_token).any():
            reasons.append(f"{label}: correction token {correction_token} already exists in COGS.")
        reused_rows = ledger[ledger["token_id"].map(_text) == reused_token]
        if len(reused_rows) != 1:
            reasons.append(f"{label}: reused token {reused_token} is not present exactly once.")
        else:
            reused = reused_rows.iloc[0]
            if _norm(reused.get("seller_sku", "")) != sku:
                reasons.append(f"{label}: reused token belongs to SKU {_text(reused.get('seller_sku', ''))}.")
            if _text(reused.get("status", "")).lower() != "allocated":
                reasons.append(f"{label}: reused token is not currently allocated.")
            if _text(reused.get("allocated_order_id", "")) != downstream_order:
                reasons.append(f"{label}: reused token is not allocated to the downstream order.")
        allocation_rows = allocations[
            (allocations["order_id"].map(_text) == downstream_order)
            & (allocations["seller_sku"].map(_norm) == sku)
            & (allocations["token_id"].map(_text) == reused_token)
        ]
        if len(allocation_rows) != 1:
            reasons.append(f"{label}: reused allocation row count is {len(allocation_rows)}, expected 1.")
        cogs_rows = cogs[
            (cogs["order_id"].map(_text) == downstream_order)
            & (cogs["seller_sku"].map(_norm) == sku)
            & (cogs["token_id"].map(_text) == reused_token)
        ]
        if len(cogs_rows) != 1:
            reasons.append(f"{label}: reused COGS row count is {len(cogs_rows)}, expected 1.")
    return sorted(set(reasons))


def _manifest_payload(result: ApplyResult, observed_utc: str, maintenance_request_id: str | None = None) -> dict[str, object]:
    return {
        "status": result.status,
        "approved": result.approved,
        "observed_utc": observed_utc,
        "approval_reference": APPROVAL_REFERENCE,
        "maintenance_request_id": maintenance_request_id or "",
        "eligible_rows": result.eligible_rows,
        "approved_rows": result.approved_rows,
        "applied_rows": result.applied_rows,
        "created_token_rows": result.created_token_rows,
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
            "repair_scope": "exact Luke-approved B069 damaged/defective return reused-token rows only",
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
    for rel_path in [PREVIEW, TOKEN_LEDGER, TOKEN_LEDGER_LIVE_COPY, TOKEN_ALLOCATIONS, TOKEN_ALLOCATIONS_LIVE_COPY, TOKEN_COGS]:
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
    approved_rows: int = 0,
    blocked_rows: int = 0,
    maintenance_request_id: str | None = None,
) -> ApplyResult:
    result = ApplyResult(
        status=status,
        approved=approved,
        eligible_rows=eligible_rows,
        approved_rows=approved_rows,
        applied_rows=0,
        created_token_rows=0,
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
    return {
        "token_cost": _money(exvat),
        "currency": currency or _text(row.get("currency", "")) or "GBP",
        "built_at": observed_utc,
        "cogs_exvat": _money(exvat),
        "cogs_vat": _money(vat),
        "cogs_total": _money(total),
    }


def apply_disposition_cogs_correction(
    *,
    root: Path | str | None = None,
    approve_protected_disposition_cogs_correction: bool = False,
    observed_utc: str | None = None,
    maintenance_request_id: str | None = None,
    approved_keys: set[tuple[str, str, str, str]] | None = None,
) -> ApplyResult:
    root_path = Path(root or ".")
    observed = observed_utc or _utc_now_text()
    allowed_keys = approved_keys if approved_keys is not None else APPROVED_KEYS

    if not approve_protected_disposition_cogs_correction:
        return _blocked_result(
            root=root_path,
            observed_utc=observed,
            approved=False,
            status="blocked_needs_approval",
            reasons=["Protected B069 damaged-return COGS correction approval flag was not supplied."],
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

    raw_preview = _read_csv(root_path / PREVIEW)
    if not raw_preview.empty and "correction_apply_lane" in raw_preview.columns:
        eligible_preview = raw_preview[
            raw_preview["correction_apply_lane"].astype(str).str.strip().isin(ELIGIBLE_LANES)
        ].copy()
    else:
        eligible_preview = pd.DataFrame()
    preview, pre_reasons = _target_rows(raw_preview, allowed_keys)
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
            "last_return_event_id",
            "return_order_id",
            "return_date",
            "return_event_id",
            "notes",
            "disposed_date",
            "disposed_reason",
            "cost_per_unit",
            "currency",
            "received_date",
            "source",
            "source_batch_id",
            "source_order_key",
            "created_at",
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
    reasons = _validate(preview=preview, ledger=ledger, allocations=allocations, cogs=cogs, pre_reasons=pre_reasons)
    if reasons:
        return _blocked_result(
            root=root_path,
            observed_utc=observed,
            approved=True,
            status="blocked_validation_failed",
            reasons=reasons,
            eligible_rows=len(eligible_preview),
            approved_rows=len(preview),
            blocked_rows=len(preview),
            maintenance_request_id=maintenance_request_id,
        )

    snapshot_dir = _snapshot_files(root_path, observed)
    applied_rows: list[dict[str, str]] = []
    token_rows_updated = 0
    allocation_rows_updated = 0
    cogs_rows_updated = 0
    created_token_rows = 0

    try:
        for _, preview_row in preview.iterrows():
            return_order, sku, downstream_order, reused_token = _row_key(preview_row)
            correction_token = _correction_token_id(preview_row)
            reused_idx = int(ledger.index[ledger["token_id"].map(_text) == reused_token][0])
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
            previous_reused_status = _text(ledger.at[reused_idx, "status"])
            token_cost = _text(allocations.at[allocation_idx, "token_cost"]) or _text(ledger.at[reused_idx, "cost_per_unit"])
            currency = _text(allocations.at[allocation_idx, "currency"]) or _text(ledger.at[reused_idx, "currency"]) or "GBP"
            allocation_date = _text(allocations.at[allocation_idx, "allocation_date"]) or _text(ledger.at[reused_idx, "allocated_date"]) or observed
            order_date = _text(allocations.at[allocation_idx, "order_date"]) or _text(cogs.at[cogs_idx, "order_date"]) or allocation_date

            correction_row = ledger.loc[reused_idx].copy()
            correction_row["token_id"] = correction_token
            correction_row["status"] = "allocated"
            correction_row["allocated_order_id"] = downstream_order
            correction_row["allocated_date"] = allocation_date
            correction_row["return_order_id"] = ""
            correction_row["return_date"] = ""
            correction_row["return_event_id"] = ""
            correction_row["last_return_order_id"] = ""
            correction_row["last_return_date"] = ""
            correction_row["last_return_event_id"] = ""
            correction_row["disposed_event_id"] = ""
            correction_row["disposed_date"] = ""
            correction_row["disposed_reason"] = ""
            correction_row["cost_per_unit"] = token_cost
            correction_row["currency"] = currency
            correction_row["source"] = "manager_approved_cogs_correction"
            correction_row["source_batch_id"] = "B069_MANAGER_APPROVED"
            correction_row["source_order_key"] = downstream_order
            correction_row["created_at"] = observed
            correction_row["notes"] = (
                f"manager_cogs_correction_token:{APPROVAL_REFERENCE}:"
                f"return_order={return_order}:reused_token={reused_token}"
            )

            ledger.at[reused_idx, "status"] = "unsellable"
            ledger.at[reused_idx, "allocated_order_id"] = ""
            ledger.at[reused_idx, "allocated_date"] = ""
            ledger.at[reused_idx, "disposed_date"] = observed
            ledger.at[reused_idx, "disposed_reason"] = _text(preview_row.get("amazon_return_disposition", "")) or "NON_SELLABLE_RETURN"
            ledger.at[reused_idx, "notes"] = _append_note(
                ledger.at[reused_idx, "notes"],
                f"non_sellable_return_correction_blocked:{APPROVAL_REFERENCE}:{return_order}:{downstream_order}",
            )
            ledger = pd.concat([ledger, pd.DataFrame([correction_row], columns=ledger.columns)], ignore_index=True)

            allocations.at[allocation_idx, "token_id"] = correction_token
            allocations.at[allocation_idx, "token_cost"] = token_cost
            allocations.at[allocation_idx, "currency"] = currency
            allocations.at[allocation_idx, "source_level"] = "manager_cogs_correction"
            allocations.at[allocation_idx, "notes"] = _append_note(
                allocations.at[allocation_idx, "notes"],
                f"manager_cogs_correction:{APPROVAL_REFERENCE}:{return_order}:{reused_token}",
            )

            cogs.at[cogs_idx, "token_id"] = correction_token
            cogs.at[cogs_idx, "order_date"] = order_date
            cogs.at[cogs_idx, "allocation_date"] = allocation_date
            for column, value in _recalculate_cogs_fields(cogs.loc[cogs_idx], token_cost, currency, observed).items():
                if column in cogs.columns:
                    cogs.at[cogs_idx, column] = value

            applied_rows.append(
                {
                    "return_order_id": return_order,
                    "sku": sku,
                    "amazon_return_disposition": _text(preview_row.get("amazon_return_disposition", "")),
                    "downstream_order_id": downstream_order,
                    "reused_token_id": reused_token,
                    "correction_token_id": correction_token,
                    "previous_reused_status": previous_reused_status,
                    "new_reused_status": "unsellable",
                    "correction_token_status": "allocated",
                    "allocation_rows_updated": "1",
                    "cogs_rows_updated": "1",
                    "token_cost": token_cost,
                    "currency": currency,
                    "correction_apply_lane": _text(preview_row.get("correction_apply_lane", "")),
                    "action": "protected_non_sellable_return_cogs_correction_applied",
                }
            )
            token_rows_updated += 1
            allocation_rows_updated += 1
            cogs_rows_updated += 1
            created_token_rows += 1

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
        eligible_rows=len(eligible_preview),
        approved_rows=len(preview),
        applied_rows=len(applied_rows),
        created_token_rows=created_token_rows,
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
    result = apply_disposition_cogs_correction(approve_protected_disposition_cogs_correction=False)
    print(
        {
            "status": result.status,
            "eligible_rows": result.eligible_rows,
            "approved_rows": result.approved_rows,
            "applied_rows": result.applied_rows,
            "created_token_rows": result.created_token_rows,
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
