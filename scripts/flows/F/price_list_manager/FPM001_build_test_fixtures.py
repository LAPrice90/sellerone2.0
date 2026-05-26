from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
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
    BATCH_ROW_COLUMNS,
    MANAGER_DECISION_COLUMNS,
    MANAGER_HEALTH_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
    SUPPLIER_REGISTRY_COLUMNS,
)


DEFAULT_SUPPLIER_ID = "shure_cosmetics"

SHURE_TEST_PRODUCTS = [
    ("SCS-FPM-001", "5012345678901", "5.50", "Shure Test Product 01"),
    ("SCS-FPM-002", "5012345678902", "6.25", "Shure Test Product 02"),
    ("SCS-FPM-003", "5012345678903", "7.10", "Shure Test Product 03"),
    ("SCS-FPM-004", "5012345678904", "8.00", "Shure Test Product 04"),
    ("SCS-FPM-005", "5012345678905", "9.45", "Shure Test Product 05"),
    ("SCS-FPM-006", "5012345678906", "10.20", "Shure Test Product 06"),
    ("SCS-FPM-007", "5012345678907", "11.05", "Shure Test Product 07"),
    ("SCS-FPM-008", "5012345678908", "12.75", "Shure Test Product 08"),
    ("SCS-FPM-009", "5012345678909", "13.30", "Shure Test Product 09"),
    ("SCS-FPM-010", "5012345678910", "14.15", "Shure Test Product 10"),
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha1_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def _active_flag(value: object) -> bool:
    return normalize_text(value).lower() not in {"", "0", "false", "no", "off"}


def _registry_path(root_path: Path) -> Path:
    return root_path / "config" / "feeder" / "price_list_manager" / "suppliers.csv"


def _load_supplier_registry(root_path: Path) -> pd.DataFrame:
    path = _registry_path(root_path)
    if not path.exists():
        raise FileNotFoundError(f"price-list manager supplier registry missing: {path}")
    registry = read_csv(path, SUPPLIER_REGISTRY_COLUMNS)
    if registry.empty:
        raise ValueError("price-list manager supplier registry is empty")
    return registry


def _select_supplier(registry: pd.DataFrame, supplier_id: str) -> dict[str, str]:
    supplier_key = normalize_text(supplier_id).lower()
    matches = registry[registry["supplier_id"].map(lambda value: normalize_text(value).lower()) == supplier_key]
    if matches.empty:
        raise ValueError(f"supplier_id not registered for price-list manager: {supplier_id}")
    row = {column: normalize_text(matches.iloc[0].get(column, "")) for column in SUPPLIER_REGISTRY_COLUMNS}
    if not _active_flag(row.get("active_flag", "")):
        raise ValueError(f"supplier_id is not active in price-list manager registry: {supplier_id}")
    return row


def _build_batch_id(supplier_id: str, observed_utc: str) -> str:
    stamp = observed_utc.replace("-", "").replace(":", "")
    return f"{supplier_id}_fpm_test_{stamp}"


def _build_batch_rows(*, supplier: dict[str, str], batch_id: str) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for sku, barcode, unit_cost, title in SHURE_TEST_PRODUCTS:
        source_row_hash = _sha1_text("|".join([supplier["supplier_id"], sku, barcode, unit_cost, title]))
        rows.append(
            {
                "batch_id": batch_id,
                "supplier_id": supplier["supplier_id"],
                "row_key": source_row_hash,
                "supplier_sku": sku,
                "barcode": barcode,
                "unit_cost": unit_cost,
                "currency": "GBP",
                "source_row_hash": source_row_hash,
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "phase1_test_fixture_new_row",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            }
        )
    return pd.DataFrame(rows)


def _health_row(
    *,
    check: str,
    status: str,
    value: str,
    notes: str,
    observed_utc: str,
    source_path: Path | str,
) -> dict[str, str]:
    return {
        "check": check,
        "status": status,
        "value": value,
        "notes": notes,
        "observed_utc": observed_utc,
        "source_path": str(source_path),
    }


def build_test_fixtures(
    root: Path | None = None,
    *,
    supplier_id: str = DEFAULT_SUPPLIER_ID,
    observed_utc: str | None = None,
) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=root)
    root_path = paths.root
    observed = observed_utc or _utc_now_iso()
    registry_path = _registry_path(root_path)
    registry = _load_supplier_registry(root_path)
    supplier = _select_supplier(registry, supplier_id)
    batch_id = _build_batch_id(supplier["supplier_id"], observed)

    active_registry = registry[registry["active_flag"].map(_active_flag)].copy()
    selected_registry = active_registry if not active_registry.empty else pd.DataFrame([supplier])
    batch_rows = _build_batch_rows(supplier=supplier, batch_id=batch_id)
    source_file_hash = _sha1_text("|".join(batch_rows["source_row_hash"].tolist()))

    source_file_path = paths.test_mode_dir / f"{batch_id}_source_fixture.csv"
    converted_file_path = paths.test_mode_dir / f"{batch_id}_converted_fixture.csv"

    batches = pd.DataFrame(
        [
            {
                "batch_id": batch_id,
                "supplier_id": supplier["supplier_id"],
                "source_type": supplier["source_type"],
                "source_subtype": supplier["source_subtype"],
                "source_received_at_utc": observed,
                "source_file_path": str(source_file_path),
                "source_file_hash": source_file_hash,
                "converted_file_path": str(converted_file_path),
                "source_row_count": str(len(batch_rows)),
                "valid_row_count": str(len(batch_rows)),
                "held_row_count": "0",
                "new_row_count": str(len(batch_rows)),
                "changed_row_count": "0",
                "eligible_row_count": str(len(batch_rows)),
                "skipped_cooldown_row_count": "0",
                "batch_status": "recommendation_ready",
                "status_reason": "phase1_test_fixture_ready",
                "updated_at_utc": observed,
            }
        ]
    )

    decisions = pd.DataFrame(
        [
            {
                "decision_id": f"{batch_id}_decision_001",
                "decided_at_utc": observed,
                "recommended_action": "run_test_scan",
                "supplier_id": supplier["supplier_id"],
                "batch_id": batch_id,
                "reason_code": "phase1_test_batch_has_10_eligible_rows",
                "estimated_scan_rows": str(len(batch_rows)),
                "estimated_skip_rows": "0",
                "f061_owner_status": "not_checked_test_mode",
                "safe_to_handoff_flag": "0",
                "notes": "test-mode only; live F061 handoff disabled",
            }
        ]
    )

    health = pd.DataFrame(
        [
            _health_row(
                check="supplier_registry_unique_ids",
                status="ok" if registry["supplier_id"].nunique() == len(registry) else "fail",
                value=str(registry["supplier_id"].nunique()),
                notes="registry_loaded",
                observed_utc=observed,
                source_path=registry_path,
            ),
            _health_row(
                check="supplier_registry_active_methods_present",
                status="ok" if supplier["source_type"] and supplier["converter_id"] else "fail",
                value=supplier["source_type"],
                notes=f"source_subtype={supplier['source_subtype']};converter={supplier['converter_id']}",
                observed_utc=observed,
                source_path=registry_path,
            ),
            _health_row(
                check="batch_row_count_reconciliation",
                status="ok" if len(batch_rows) == 10 else "fail",
                value=str(len(batch_rows)),
                notes="source_rows=10;valid_rows=10;eligible_rows=10;held_rows=0",
                observed_utc=observed,
                source_path=converted_file_path,
            ),
            _health_row(
                check="f061_handoff_disabled_in_test_mode",
                status="ok",
                value="0",
                notes="no live F061 inbox or live files written",
                observed_utc=observed,
                source_path=paths.test_mode_dir,
            ),
        ]
    )

    write_csv(paths.test_mode_dir / "supplier_registry.csv", selected_registry, SUPPLIER_REGISTRY_COLUMNS)
    written_batches = write_csv(paths.test_mode_dir / "price_list_batches.csv", batches, PRICE_LIST_BATCH_COLUMNS)
    written_batch_rows = write_csv(paths.test_mode_dir / "batch_rows.csv", batch_rows, BATCH_ROW_COLUMNS)
    written_decisions = write_csv(paths.test_mode_dir / "manager_decisions.csv", decisions, MANAGER_DECISION_COLUMNS)
    written_health = write_csv(paths.test_mode_dir / "health.csv", health, MANAGER_HEALTH_COLUMNS)
    write_csv(source_file_path, written_batch_rows, BATCH_ROW_COLUMNS)
    write_csv(converted_file_path, written_batch_rows, BATCH_ROW_COLUMNS)

    summary = {
        "status": "success",
        "supplier_id": supplier["supplier_id"],
        "source_type": supplier["source_type"],
        "source_subtype": supplier["source_subtype"],
        "batch_id": batch_id,
        "source_rows": int(len(written_batch_rows)),
        "valid_rows": int(len(written_batch_rows)),
        "eligible_rows": int((written_batch_rows["scan_eligibility"] == "scan_now").sum()),
        "held_rows": 0,
        "decision_rows": int(len(written_decisions)),
        "health_fail_rows": int((written_health["status"].map(lambda value: normalize_text(value).lower()) == "fail").sum()),
        "test_mode_dir": str(paths.test_mode_dir),
        "batch_rows_path": str(paths.test_mode_dir / "batch_rows.csv"),
        "price_list_batches_path": str(paths.test_mode_dir / "price_list_batches.csv"),
    }
    print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build price-list manager test fixtures.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--supplier-id", default=DEFAULT_SUPPLIER_ID)
    parser.add_argument("--observed-utc", default=None)
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    build_test_fixtures(root=root, supplier_id=args.supplier_id, observed_utc=args.observed_utc)


if __name__ == "__main__":
    main()
