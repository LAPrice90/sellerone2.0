from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import ensure_manager_test_mode_dir
from scripts.flows.F.price_list_manager._schemas import (
    BARCODE_SCAN_MEMORY_COLUMNS,
    BATCH_ROW_COLUMNS,
    MANAGER_HEALTH_COLUMNS,
    PLACEHOLDER_SCANNER_RESULT_COLUMNS,
)


def _parse_utc(value: object) -> datetime:
    raw = normalize_text(value)
    if raw:
        try:
            return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _cooldown_until(scanned_at_utc: str, cooldown_days: str) -> str:
    try:
        days = int(float(normalize_text(cooldown_days) or "0"))
    except ValueError:
        days = 0
    if days <= 0:
        return ""
    return (_parse_utc(scanned_at_utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _memory_key(row: pd.Series, batch_row: pd.Series | None) -> str:
    scope = normalize_text(row.get("memory_scope", ""))
    supplier_id = normalize_text(row.get("supplier_id", ""))
    barcode = normalize_text(row.get("barcode", ""))
    if scope == "global_barcode":
        return f"barcode:{barcode}"
    unit_cost = normalize_text(batch_row.get("unit_cost", "")) if batch_row is not None else ""
    return f"supplier_offer:{supplier_id}:{barcode}:{unit_cost}"


def _batch_row_lookup(batch_rows: pd.DataFrame) -> dict[tuple[str, str], pd.Series]:
    out: dict[tuple[str, str], pd.Series] = {}
    for _, row in batch_rows.iterrows():
        out[(normalize_text(row.get("batch_id", "")), normalize_text(row.get("row_key", "")))] = row
    return out


def _health_row(*, check: str, status: str, value: str, notes: str, observed_utc: str, source_path: Path) -> dict[str, str]:
    return {
        "check": check,
        "status": status,
        "value": value,
        "notes": notes,
        "observed_utc": observed_utc,
        "source_path": str(source_path),
    }


def update_memory_from_results(root: Path | None = None, *, observed_utc: str | None = None) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=root)
    observed = observed_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    results_path = paths.test_mode_dir / "placeholder_scanner_results.csv"
    batch_rows_path = paths.test_mode_dir / "batch_rows.csv"
    memory_path = paths.test_mode_dir / "barcode_scan_memory.csv"
    health_path = paths.test_mode_dir / "health.csv"

    results = read_csv(results_path, PLACEHOLDER_SCANNER_RESULT_COLUMNS)
    batch_rows = read_csv(batch_rows_path, BATCH_ROW_COLUMNS)
    if results.empty:
        raise FileNotFoundError("placeholder_scanner_results.csv is required before memory update")

    batch_lookup = _batch_row_lookup(batch_rows)
    memory_rows: list[dict[str, str]] = []
    unresolved_rows = 0
    for _, row in results.iterrows():
        batch_id = normalize_text(row.get("batch_id", ""))
        row_key = normalize_text(row.get("row_key", ""))
        batch_row = batch_lookup.get((batch_id, row_key))
        if batch_row is None:
            unresolved_rows += 1
        scanned_at = normalize_text(row.get("scanned_at_utc", "")) or observed
        cooldown_until = _cooldown_until(scanned_at, normalize_text(row.get("cooldown_days", "")))
        memory_rows.append(
            {
                "memory_key": _memory_key(row, batch_row),
                "memory_scope": normalize_text(row.get("memory_scope", "")),
                "supplier_id": normalize_text(row.get("supplier_id", "")),
                "barcode": normalize_text(row.get("barcode", "")),
                "asin": "",
                "last_result_status": normalize_text(row.get("result_status", "")),
                "last_fail_code": normalize_text(row.get("fail_code", "")),
                "last_stage": normalize_text(row.get("last_stage", "")),
                "last_scanned_at_utc": scanned_at,
                "cooldown_until_utc": cooldown_until,
                "cooldown_basis": normalize_text(row.get("placeholder_outcome", "")),
                "attempt_count": "1",
                "last_batch_id": batch_id,
                "last_row_hash": row_key,
                "updated_at_utc": observed,
            }
        )

    memory = write_csv(memory_path, pd.DataFrame(memory_rows), BARCODE_SCAN_MEMORY_COLUMNS)
    existing_health = read_csv(health_path, MANAGER_HEALTH_COLUMNS)
    new_health = pd.DataFrame(
        [
            _health_row(
                check="placeholder_result_count_reconciliation",
                status="ok" if len(results.index) > 0 and len(results.index) % 10 == 0 else "fail",
                value=str(len(results.index)),
                notes="expected_placeholder_results_in_multiples_of_10",
                observed_utc=observed,
                source_path=results_path,
            ),
            _health_row(
                check="barcode_memory_update_reconciliation",
                status="ok" if len(memory.index) == len(results.index) and unresolved_rows == 0 else "fail",
                value=str(len(memory.index)),
                notes=f"result_rows={len(results.index)};unresolved_rows={unresolved_rows}",
                observed_utc=observed,
                source_path=memory_path,
            ),
        ]
    )
    health = write_csv(health_path, pd.concat([existing_health, new_health], ignore_index=True), MANAGER_HEALTH_COLUMNS)

    summary = {
        "status": "success",
        "result_rows": int(len(results.index)),
        "memory_rows": int(len(memory.index)),
        "unresolved_rows": int(unresolved_rows),
        "health_fail_rows": int((health["status"].map(lambda value: normalize_text(value).lower()) == "fail").sum()),
        "memory_path": str(memory_path),
    }
    print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Update price-list manager memory from placeholder results.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--observed-utc", default=None)
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    update_memory_from_results(root=root, observed_utc=args.observed_utc)


if __name__ == "__main__":
    main()
