from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.F062_reset_supplier_test_mode import reset_supplier_test_mode
from scripts.flows.F._schemas import get_f_output_contract


def _write_contract(root: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
    contract = get_f_output_contract(contract_name)
    columns = [*contract.required_columns, *contract.optional_columns]
    df = pd.DataFrame(rows)
    for column in columns:
        if column not in df.columns:
            df[column] = ""
    out = df[columns]
    path = root / contract.rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)


def _write_supplier_config(root: Path) -> None:
    config_dir = root / "config" / "feeder" / "suppliers"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "shure_cosmetics.json").write_text(
        json.dumps(
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "source_url": "https://aux.shure-cosmetics.co.uk/pricelist/",
                "source_type": "csv",
                "default_vat_rate": "20",
                "currency": "GBP",
                "skip_sku_suffixes": ["DD"],
            }
        ),
        encoding="utf-8",
    )


def test_f062_resets_supplier_active_run_from_canonical_and_clears_supplier_live_rows(tmp_path: Path) -> None:
    _write_supplier_config(tmp_path)
    supplier_dir = tmp_path / "out" / "systems" / "F" / "inbox" / "suppliers" / "shure_cosmetics"
    supplier_dir.mkdir(parents=True, exist_ok=True)
    canonical_path = supplier_dir / "canonical_current.csv"
    canonical_df = pd.DataFrame(
        [
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "supplier_sku": "S1",
                "supplier_title": "Product One",
                "barcode": "5012345678901",
                "unit_cost": "10.00",
                "currency": "GBP",
                "vat_rate": "20",
                "source_url": "https://aux.shure-cosmetics.co.uk/pricelist/",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-04-08T11:00:00Z",
                "row_hash": "rk_1",
                "is_valid_source_row": "1",
                "normalized_utc": "2026-04-08T11:00:00Z",
            },
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "supplier_sku": "S2",
                "supplier_title": "Product Two",
                "barcode": "5012345678902",
                "unit_cost": "11.00",
                "currency": "GBP",
                "vat_rate": "20",
                "source_url": "https://aux.shure-cosmetics.co.uk/pricelist/",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-04-08T11:00:00Z",
                "row_hash": "rk_2",
                "is_valid_source_row": "1",
                "normalized_utc": "2026-04-08T11:00:00Z",
            },
        ]
    )
    canonical_df.to_csv(canonical_path, index=False)

    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "old_run",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "old_rk",
                "supplier_sku": "OLD1",
                "barcode": "0000000000000",
                "supplier_title": "Old Row",
                "unit_cost": "9.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "done",
                "scan_reason": "",
                "attempt_count": "1",
                "last_attempt_utc": "2026-04-08T10:00:00Z",
                "finished_utc": "2026-04-08T10:01:00Z",
                "source_seen_at_utc": "2026-04-08T10:00:00Z",
            }
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "run_id": "old_run",
                "run_status": "completed",
                "source_url": "https://aux.shure-cosmetics.co.uk/pricelist/",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-04-08T10:00:00Z",
                "normalized_utc": "2026-04-08T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "0",
                "done_rows": "1",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "0",
                "updated_at_utc": "2026-04-08T10:01:00Z",
                "completed_at_utc": "2026-04-08T10:01:00Z",
            }
        ],
    )
    _write_contract(
        tmp_path,
        "feeder_legacy_first_checks_live",
        [
            {"supplier": "Shure Cosmetics", "candidate_id": "c1", "pf": "PASS"},
            {"supplier": "Other Supplier", "candidate_id": "c2", "pf": "PASS"},
        ],
    )
    _write_contract(
        tmp_path,
        "feeder_legacy_second_checks_live",
        [
            {"supplier": "Shure Cosmetics", "candidate_id": "c3", "pf": "PASS"},
            {"supplier": "Other Supplier", "candidate_id": "c4", "pf": "PASS"},
        ],
    )
    _write_contract(
        tmp_path,
        "feeder_legacy_bot_status_live",
        [
            {"supplier": "Shure Cosmetics", "run_utc": "2026-04-08T10:00:00Z", "status": "completed"},
            {"supplier": "Other Supplier", "run_utc": "2026-04-08T10:00:00Z", "status": "completed"},
        ],
    )

    summary = reset_supplier_test_mode(root=tmp_path, supplier_id="shure_cosmetics")
    assert summary["status"] == "success"
    assert summary["active_supplier_rows"] == 2

    active_df = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path, dtype=str).fillna("")
    assert len(active_df) == 2
    assert set(active_df["supplier_sku"].tolist()) == {"S1", "S2"}
    assert set(active_df["scan_status"].tolist()) == {"pending"}

    run_state_df = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_run_state").rel_path, dtype=str).fillna("")
    row = run_state_df.iloc[0]
    assert row["supplier_id"] == "shure_cosmetics"
    assert row["pending_rows"] == "2"
    assert row["done_rows"] == "0"
    assert row["failed_rows"] == "0"

    first_df = pd.read_csv(tmp_path / get_f_output_contract("feeder_legacy_first_checks_live").rel_path, dtype=str).fillna("")
    second_df = pd.read_csv(tmp_path / get_f_output_contract("feeder_legacy_second_checks_live").rel_path, dtype=str).fillna("")
    bot_df = pd.read_csv(tmp_path / get_f_output_contract("feeder_legacy_bot_status_live").rel_path, dtype=str).fillna("")
    assert set(first_df["supplier"].tolist()) == {"Other Supplier"}
    assert set(second_df["supplier"].tolist()) == {"Other Supplier"}
    assert set(bot_df["supplier"].tolist()) == {"Other Supplier"}


def test_f062_requires_canonical_file(tmp_path: Path) -> None:
    _write_supplier_config(tmp_path)
    with pytest.raises(FileNotFoundError):
        reset_supplier_test_mode(root=tmp_path, supplier_id="shure_cosmetics")


def test_f062_clears_bot_status_when_row_uses_supplier_id_not_name(tmp_path: Path) -> None:
    _write_supplier_config(tmp_path)
    supplier_dir = tmp_path / "out" / "systems" / "F" / "inbox" / "suppliers" / "shure_cosmetics"
    supplier_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "supplier_sku": "S1",
                "supplier_title": "Product One",
                "barcode": "5012345678901",
                "unit_cost": "10.00",
                "currency": "GBP",
                "vat_rate": "20",
                "source_url": "https://aux.shure-cosmetics.co.uk/pricelist/",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-04-08T11:00:00Z",
                "row_hash": "rk_1",
                "is_valid_source_row": "1",
                "normalized_utc": "2026-04-08T11:00:00Z",
            }
        ]
    ).to_csv(supplier_dir / "canonical_current.csv", index=False)

    _write_contract(
        tmp_path,
        "feeder_legacy_bot_status_live",
        [
            {"supplier": "shure_cosmetics", "run_utc": "2026-04-08T10:00:00Z", "status": "completed"},
            {"supplier": "Other Supplier", "run_utc": "2026-04-08T10:00:00Z", "status": "completed"},
        ],
    )

    reset_supplier_test_mode(root=tmp_path, supplier_id="shure_cosmetics")

    bot_df = pd.read_csv(tmp_path / get_f_output_contract("feeder_legacy_bot_status_live").rel_path, dtype=str).fillna("")
    assert set(bot_df["supplier"].tolist()) == {"Other Supplier"}
