from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.out_paths import resolve_compat_path, write_csv_with_compat


REQUIRED_COLUMNS = [
    "seller_sku",
    "quantity",
    "correction_class",
    "approval_reference",
    "reason",
]
OUT_AUDIT = ROOT / "out" / "manual_token_correction_events.csv"
MAINTENANCE_READY = ROOT / "out" / "locks" / "maintenance.ready"


def _utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe(value: object) -> str:
    raw = str(value or "").strip()
    return re.sub(r"[^A-Za-z0-9._-]", "_", raw)[:80] or "blank"


def _as_int(value: object) -> int:
    try:
        return int(float(str(value).strip()))
    except Exception:
        return 0


def _latest_cost_basis(ledger: pd.DataFrame, sku: str) -> dict[str, str] | None:
    if ledger.empty or "seller_sku" not in ledger.columns:
        return None
    rows = ledger[ledger["seller_sku"].astype(str).str.strip() == str(sku).strip()].copy()
    if rows.empty or "cost_per_unit" not in rows.columns:
        return None
    rows["__cost"] = pd.to_numeric(rows["cost_per_unit"], errors="coerce").fillna(0.0)
    rows = rows[rows["__cost"] > 0].copy()
    if rows.empty:
        return None
    rows["__received"] = pd.to_datetime(rows.get("received_date", ""), errors="coerce", utc=True)
    rows["__created"] = pd.to_datetime(rows.get("created_at", ""), errors="coerce", utc=True)
    rows["__row"] = range(len(rows.index))
    latest = rows.sort_values(["__received", "__created", "__row"]).iloc[-1]
    return {
        "cost_per_unit": f"{float(latest['__cost']):.2f}",
        "currency": str(latest.get("currency", "") or "GBP"),
        "basis_token_id": str(latest.get("token_id", "") or ""),
        "basis_source": str(latest.get("source", "") or ""),
    }


def _required_ledger_columns() -> list[str]:
    return [
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
    ]


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"missing input: {path}")
    return pd.read_csv(path, dtype=str).fillna("")


def _existing_applied_event_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    rows = pd.read_csv(path, dtype=str).fillna("")
    if "event_id" not in rows.columns or "status" not in rows.columns:
        return set()
    applied = rows[rows["status"].astype(str).str.strip().eq("ok")].copy()
    return {str(event_id).strip() for event_id in applied["event_id"].tolist() if str(event_id).strip()}


def apply_corrections(
    corrections: pd.DataFrame,
    ledger: pd.DataFrame,
    *,
    now_iso: str,
    existing_event_ids: set[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in corrections.columns]
    if missing_cols:
        raise ValueError(f"correction input missing columns: {', '.join(missing_cols)}")

    ledger = ledger.copy()
    for col in _required_ledger_columns():
        if col not in ledger.columns:
            ledger[col] = ""

    existing_ids = set(ledger["token_id"].astype(str).tolist())
    existing_event_ids = set(existing_event_ids or set())
    new_rows: list[dict[str, str]] = []
    audit_rows: list[dict[str, str]] = []

    for _, row in corrections.iterrows():
        sku = str(row.get("seller_sku", "")).strip()
        qty = _as_int(row.get("quantity", ""))
        approval_reference = str(row.get("approval_reference", "")).strip()
        correction_class = str(row.get("correction_class", "")).strip()
        reason = str(row.get("reason", "")).strip()
        event_id = f"T030-{_safe(approval_reference)}-{_safe(sku)}"

        if event_id in existing_event_ids:
            audit_rows.append(
                {
                    "event_id": event_id,
                    "event_ts": now_iso,
                    "seller_sku": sku,
                    "quantity": str(qty),
                    "applied_qty": "0",
                    "status": "already_applied",
                    "correction_class": correction_class,
                    "approval_reference": approval_reference,
                    "reason": reason,
                    "note": "already_applied_event_id",
                }
            )
            continue

        status = "ok"
        note = ""
        applied = 0
        basis = _latest_cost_basis(ledger, sku)
        if not sku or qty <= 0:
            status = "skip"
            note = "invalid_sku_or_quantity"
        elif not approval_reference:
            status = "skip"
            note = "missing_approval_reference"
        elif basis is None:
            status = "skip"
            note = "missing_positive_cost_basis"
        else:
            for seq in range(1, qty + 1):
                token_id_base = f"MANUAL-CORR-{_safe(sku)}-{_safe(approval_reference)}-{seq:04d}"
                token_id = token_id_base
                duplicate_seq = 1
                while token_id in existing_ids:
                    duplicate_seq += 1
                    token_id = f"{token_id_base}-{duplicate_seq}"
                existing_ids.add(token_id)
                new_rows.append(
                    {
                        "token_id": token_id,
                        "seller_sku": sku,
                        "cost_per_unit": basis["cost_per_unit"],
                        "currency": basis["currency"],
                        "status": "available",
                        "received_date": now_iso[:10],
                        "notes": f"manual_approved_correction:{approval_reference};class={correction_class};reason={reason};basis_token_id={basis['basis_token_id']}",
                        "source": "manual_approved_correction",
                        "source_batch_id": approval_reference,
                        "source_order_key": "",
                        "created_at": now_iso,
                        "allocated_order_id": "",
                        "allocated_date": "",
                        "return_order_id": "",
                        "return_date": "",
                        "return_event_id": "",
                        "last_return_order_id": "",
                        "last_return_date": "",
                        "last_return_event_id": "",
                        "disposed_event_id": "",
                        "disposed_date": "",
                        "disposed_reason": "",
                    }
                )
                applied += 1

        audit_rows.append(
            {
                "event_id": event_id,
                "event_ts": now_iso,
                "seller_sku": sku,
                "quantity": str(qty),
                "applied_qty": str(applied),
                "status": status,
                "correction_class": correction_class,
                "approval_reference": approval_reference,
                "reason": reason,
                "note": note,
            }
        )

    if new_rows:
        ledger = pd.concat([ledger, pd.DataFrame(new_rows)], ignore_index=True)
    return ledger, pd.DataFrame(audit_rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply explicitly approved token corrections to local B token ledger.")
    parser.add_argument("--input", default="out/manual_token_corrections_approved.csv")
    parser.add_argument("--apply", action="store_true", help="write changes; otherwise dry-run only")
    parser.add_argument("--allow-without-maintenance", action="store_true")
    args = parser.parse_args()

    if args.apply and not args.allow_without_maintenance and not MAINTENANCE_READY.exists():
        raise SystemExit("refusing write: B maintenance.ready is not present")

    input_path = ROOT / args.input
    corrections = _load_csv(input_path)
    ledger_paths = resolve_compat_path("token_ledger_live.csv", default_system="B")
    ledger_path = ledger_paths.live_path if ledger_paths.live_path.exists() else ledger_paths.legacy_path
    ledger = _load_csv(ledger_path)
    if not ledger.columns.is_unique:
        ledger = ledger.loc[:, ~ledger.columns.duplicated()].copy()

    now_iso = _utc_ts()
    updated, audit = apply_corrections(
        corrections,
        ledger,
        now_iso=now_iso,
        existing_event_ids=_existing_applied_event_ids(OUT_AUDIT),
    )
    created = int(pd.to_numeric(audit["applied_qty"], errors="coerce").fillna(0).sum()) if not audit.empty else 0
    skipped = int((audit["status"].astype(str) == "skip").sum()) if not audit.empty else 0
    already_applied = int((audit["status"].astype(str) == "already_applied").sum()) if not audit.empty else 0

    if args.apply:
        backup_dir = ROOT / "out" / "backups" / f"manual_token_corrections_{now_iso.replace(':', '').replace('-', '').replace('Z', 'Z')}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ledger_path, backup_dir / "token_ledger_live.pre_correction.csv")
        shutil.copy2(input_path, backup_dir / input_path.name)
        if created > 0:
            write_csv_with_compat(updated, path_or_rel="token_ledger_live.csv", index=False, default_system="B")
        audit_to_write = audit[audit["status"].astype(str) != "already_applied"].copy()
        if not audit_to_write.empty:
            OUT_AUDIT.parent.mkdir(parents=True, exist_ok=True)
            if OUT_AUDIT.exists():
                audit_to_write.to_csv(OUT_AUDIT, mode="a", header=False, index=False)
            else:
                audit_to_write.to_csv(OUT_AUDIT, index=False)
        status = "applied"
    else:
        status = "dry_run"

    print(
        {
            "status": status,
            "input_rows": int(len(corrections.index)),
            "created_tokens": created,
            "skipped_rows": skipped,
            "already_applied_rows": already_applied,
            "ledger_before_rows": int(len(ledger.index)),
            "ledger_after_rows": int(len(updated.index)),
            "audit_path": str(OUT_AUDIT),
        }
    )
    return 0 if skipped == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
