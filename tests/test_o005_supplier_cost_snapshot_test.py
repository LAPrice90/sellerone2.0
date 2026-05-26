from __future__ import annotations

import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.O.O005_build_supplier_cost_snapshot_test import build_supplier_cost_snapshot_test
from scripts.flows.O._schemas import get_o_output_contract


FIXTURE_DIR = ROOT / "tests" / "fixtures" / "o_phase1"


def test_o005_builds_normalized_test_snapshot(tmp_path: Path) -> None:
    fixture_rel = "tests/fixtures/o_phase1/supplier_cost_snapshot_test_input.csv"
    fixture_dst = tmp_path / fixture_rel
    fixture_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURE_DIR / "supplier_cost_snapshot_test_input.csv", fixture_dst)

    out_df = build_supplier_cost_snapshot_test(root=tmp_path)
    contract = get_o_output_contract("supplier_cost_snapshot_test")

    assert len(out_df) == 3
    assert list(out_df.columns) == list(contract.required_columns)
    assert set(out_df["cost_mode"]) == {"test"}
    assert set(out_df["source_type"]) == {"test_fixture"}
    assert (tmp_path / contract.rel_path).exists()


def test_o005_missing_input_writes_empty_snapshot(tmp_path: Path) -> None:
    out_df = build_supplier_cost_snapshot_test(
        root=tmp_path,
        input_rel_path="tests/fixtures/o_phase1/does_not_exist.csv",
    )
    assert out_df.empty
