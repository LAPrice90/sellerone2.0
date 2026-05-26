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

from scripts.flows.F.F005_build_supplier_price_list_universal import build_supplier_price_list_universal
from scripts.flows.F._schemas import get_f_output_contract


FIXTURE_PATH = ROOT / "tests" / "fixtures" / "f_phase1" / "shure_cosmetics_raw_fixture.csv"
TD_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "f_phase1" / "td_synnex_raw_fixture.tsv"


def _write_contract_rows(root: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
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


def test_f005_builds_universal_output_and_queue_state(tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "feeder" / "suppliers"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "shure_cosmetics.json"
    config_path.write_text(
        json.dumps(
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "source_url": "https://aux.shure-cosmetics.co.uk/pricelist/",
                "source_type": "csv",
                "default_vat_rate": "20",
                "currency": "GBP",
                "skip_sku_suffixes": ["DD"],
                "source_path_override": str(FIXTURE_PATH),
            }
        ),
        encoding="utf-8",
    )

    build_supplier_price_list_universal(root=tmp_path, supplier_id="shure_cosmetics")

    universal_contract = get_f_output_contract("supplier_price_list_universal_live")
    holds_contract = get_f_output_contract("supplier_price_list_universal_holds")
    active_contract = get_f_output_contract("supplier_price_list_active_run")
    run_state_contract = get_f_output_contract("supplier_price_list_run_state")
    queue_contract = get_f_output_contract("supplier_price_list_queue_state")
    health_contract = get_f_output_contract("supplier_price_list_health")

    universal_path = tmp_path / universal_contract.rel_path
    holds_path = tmp_path / holds_contract.rel_path
    active_path = tmp_path / active_contract.rel_path
    run_state_path = tmp_path / run_state_contract.rel_path
    queue_path = tmp_path / queue_contract.rel_path
    health_path = tmp_path / health_contract.rel_path

    assert universal_path.exists()
    assert holds_path.exists()
    assert active_path.exists()
    assert run_state_path.exists()
    assert queue_path.exists()
    assert health_path.exists()

    universal_df = Path(universal_path).read_text(encoding="utf-8").strip().splitlines()
    holds_df = Path(holds_path).read_text(encoding="utf-8").strip().splitlines()
    active_df = Path(active_path).read_text(encoding="utf-8").strip().splitlines()

    assert len(universal_df) == 3  # header + 2 valid rows
    assert len(holds_df) == 1  # header only; skipped rows are dropped by converter
    assert len(active_df) == 3  # header + 2 queued rows


def test_f005_supports_second_supplier_converter_without_manager_changes(tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "feeder" / "suppliers"
    config_dir.mkdir(parents=True, exist_ok=True)

    shure_config = config_dir / "shure_cosmetics.json"
    shure_config.write_text(
        json.dumps(
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "source_url": "https://aux.shure-cosmetics.co.uk/pricelist/",
                "source_type": "csv",
                "default_vat_rate": "20",
                "currency": "GBP",
                "skip_sku_suffixes": ["DD"],
                "source_path_override": str(FIXTURE_PATH),
            }
        ),
        encoding="utf-8",
    )

    td_config = config_dir / "td_synnex.json"
    td_config.write_text(
        json.dumps(
            {
                "supplier_id": "td_synnex",
                "supplier_name": "TD Synnex",
                "source_url": "https://tdsynnex.example/pricelist/enhanced-gb.tsv",
                "source_type": "tsv",
                "default_vat_rate": "20",
                "currency": "GBP",
                "skip_sku_suffixes": [],
                "source_path_override": str(TD_FIXTURE_PATH),
            }
        ),
        encoding="utf-8",
    )

    build_supplier_price_list_universal(root=tmp_path, supplier_id="shure_cosmetics")
    build_supplier_price_list_universal(root=tmp_path, supplier_id="td_synnex")

    universal_contract = get_f_output_contract("supplier_price_list_universal_live")
    queue_contract = get_f_output_contract("supplier_price_list_queue_state")

    universal_path = tmp_path / universal_contract.rel_path
    queue_path = tmp_path / queue_contract.rel_path

    assert universal_path.exists()
    assert queue_path.exists()

    lines = universal_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 4  # header + 3 td rows (latest single-supplier run only)

    supplier_ids = {line.split(",")[0] for line in lines[1:]}
    assert supplier_ids == {"td_synnex"}

    queue_rows = queue_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(queue_rows) == 2  # header + current state row


def test_f005_requires_explicit_supplier_id(tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "feeder" / "suppliers"
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
                "source_path_override": str(FIXTURE_PATH),
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="supplier_id is required"):
        build_supplier_price_list_universal(root=tmp_path, supplier_id="")


def test_f005_clears_legacy_review_live_files_for_fresh_single_supplier_run(tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "feeder" / "suppliers"
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
                "source_path_override": str(FIXTURE_PATH),
            }
        ),
        encoding="utf-8",
    )

    _write_contract_rows(
        tmp_path,
        "feeder_legacy_second_checks_live",
        [{"supplier": "TD Synnex", "sku": "TD1", "barcode": "9999999999999"}],
    )
    _write_contract_rows(
        tmp_path,
        "feeder_legacy_bot_status_live",
        [{"supplier": "TD Synnex", "run_utc": "2026-04-08T00:00:00Z", "status": "running"}],
    )

    build_supplier_price_list_universal(root=tmp_path, supplier_id="shure_cosmetics")

    second_path = tmp_path / get_f_output_contract("feeder_legacy_second_checks_live").rel_path
    bot_path = tmp_path / get_f_output_contract("feeder_legacy_bot_status_live").rel_path
    second_df = pd.read_csv(second_path, dtype=str).fillna("")
    bot_df = pd.read_csv(bot_path, dtype=str).fillna("")

    assert second_df.empty
    assert bot_df.empty
