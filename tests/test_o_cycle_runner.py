from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.cycles import run_O_cycle as runner_mod
from scripts.flows.O._schemas import get_o_output_contract


def _write_minimal_product_db(root: Path) -> None:
    path = root / "out" / "product_db_preview.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "seller_sku": "SKU-O-RUNNER-1",
                "asin": "ASIN-O-RUNNER-1",
                "supplier_code": "SUP-O",
                "supplier_name": "Supplier O",
                "supplier_pack_size": "1",
                "moq": "1",
                "supplier_catalog_price": "4.0",
                "last_purchase_price": "3.8",
                "sale_status": "active",
                "vat_rate": "0.2",
            }
        ]
    ).to_csv(path, index=False)


def _write_test_cost_input(root: Path) -> None:
    path = root / "tests" / "fixtures" / "o_phase1" / "supplier_cost_snapshot_test_input.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "supplier_code": "SUP-O",
                "supplier_name": "Supplier O",
                "supplier_sku": "SUPSKU-1",
                "seller_sku": "SKU-O-RUNNER-1",
                "asin": "ASIN-O-RUNNER-1",
                "current_unit_cost": "2.5",
                "currency": "GBP",
                "availability_status": "in_stock",
                "supplier_stock": "100",
                "moq": "1",
                "pack_size": "1",
                "source_type": "test_fixture",
                "source_reference": "runner_test",
                "captured_at_utc": "2026-04-03T10:00:00Z",
                "is_current": "1",
            }
        ]
    ).to_csv(path, index=False)


def test_o_runner_step_order_mode_behavior_and_o400_excluded() -> None:
    live_plan = runner_mod.build_o_step_plan(mode=runner_mod.LIVE_SAFE_MODE, enable_test_cost_feeder=False)
    live_names = [s.name for s in live_plan]
    assert live_names == [
        "O007_build_supplier_buy_cost_truth",
        "O008_build_supplier_cost_confirmation_queue",
        "O001_build_restock_source_view",
        "O002_build_restock_recommendations",
        "O003_build_restock_review_queue",
        "O004_build_restock_diagnostics",
        "O020_build_reorder_input_coverage_report",
        "O021_build_restock_profit_checks",
        "O010_apply_restock_decisions",
        "O100_build_purchase_orders",
        "O210_apply_receiving_events",
        "O200_build_ordered_stock_state",
        "O310_close_send_to_amazon_handoff",
        "O300_build_send_to_amazon_queue",
        "O030_build_product_db_operator_view",
        "O050_build_repricing_tracker_view",
    ]
    assert all("O400" not in name for name in live_names)

    test_plan = runner_mod.build_o_step_plan(mode=runner_mod.TEST_MODE, enable_test_cost_feeder=False)
    test_names = [s.name for s in test_plan]
    assert test_names[0] == "O005_build_supplier_cost_snapshot_test"
    assert test_names[1:] == live_names
    assert all("O400" not in name for name in test_names)

    explicit_live_plan = runner_mod.build_o_step_plan(mode=runner_mod.LIVE_SAFE_MODE, enable_test_cost_feeder=True)
    explicit_live_names = [s.name for s in explicit_live_plan]
    assert explicit_live_names[0] == "O005_build_supplier_cost_snapshot_test"
    assert explicit_live_names[1:] == live_names


def test_o_runner_manifest_and_output_verification_failure(tmp_path: Path) -> None:
    ok_rel = "out/systems/O/live/custom_ok.csv"
    missing_rel = "out/systems/O/live/custom_missing.csv"

    def _ok_step(root: Path, mode: str) -> None:
        target = root / ok_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("ok\n", encoding="utf-8")

    def _missing_step(root: Path, mode: str) -> None:
        return

    custom_plan = [
        runner_mod.OStepSpec(
            name="custom_ok_step",
            script_or_function="custom_ok.py",
            runner=_ok_step,
            required_outputs=(ok_rel,),
        ),
        runner_mod.OStepSpec(
            name="custom_missing_step",
            script_or_function="custom_missing.py",
            runner=_missing_step,
            required_outputs=(missing_rel,),
        ),
    ]

    rc, manifest, manifest_path = runner_mod.run_o_cycle(
        root=tmp_path,
        mode=runner_mod.LIVE_SAFE_MODE,
        verify_outputs=True,
        run_id="O_TEST_MANIFEST_FAIL",
        step_plan_override=custom_plan,
    )

    assert rc == 2
    assert manifest["cycle"] == "O"
    assert manifest["run_id"] == "O_TEST_MANIFEST_FAIL"
    assert manifest["configured_step_count"] == 2
    assert manifest["recorded_step_count"] == 2
    assert manifest["final_state"] == "failed"
    assert manifest_path.exists()

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["steps"][0]["step_status"] == "completed"
    assert payload["steps"][1]["step_status"] == "verification_failed"
    assert missing_rel in payload["steps"][1]["missing_outputs"]


def test_o_runner_rerun_safety_and_mode_difference(tmp_path: Path) -> None:
    _write_minimal_product_db(tmp_path)
    _write_test_cost_input(tmp_path)

    rc_live_1, _, _ = runner_mod.run_o_cycle(
        root=tmp_path,
        mode=runner_mod.LIVE_SAFE_MODE,
        verify_outputs=True,
        run_id="O_TEST_LIVE_1",
    )
    assert rc_live_1 == 0
    snapshot_path = tmp_path / get_o_output_contract("supplier_cost_snapshot_test").rel_path
    assert not snapshot_path.exists()

    source_path = tmp_path / get_o_output_contract("restock_source_view").rel_path
    source_live = pd.read_csv(source_path, dtype=str).fillna("")
    assert len(source_live) == 1
    assert source_live.iloc[0]["cost_mode"] == "live"

    rc_test, _, _ = runner_mod.run_o_cycle(
        root=tmp_path,
        mode=runner_mod.TEST_MODE,
        verify_outputs=True,
        run_id="O_TEST_TEST_1",
    )
    assert rc_test == 0
    assert snapshot_path.exists()

    source_test = pd.read_csv(source_path, dtype=str).fillna("")
    assert len(source_test) == 1
    assert source_test.iloc[0]["cost_mode"] == "test"
    assert source_test.iloc[0]["current_supplier_cost_source"] == "supplier_cost_snapshot_test"

    # Runner-level rerun safety: second run should not break current-state outputs or create orchestration duplicates.
    rc_test_2, _, _ = runner_mod.run_o_cycle(
        root=tmp_path,
        mode=runner_mod.TEST_MODE,
        verify_outputs=True,
        run_id="O_TEST_TEST_2",
    )
    assert rc_test_2 == 0

    source_after_rerun = pd.read_csv(source_path, dtype=str).fillna("")
    assert len(source_after_rerun) == 1
    assert source_after_rerun.iloc[0]["seller_sku"] == "SKU-O-RUNNER-1"
    operator_view_path = tmp_path / get_o_output_contract("product_db_operator_view").rel_path
    assert operator_view_path.exists()
    operator_view_df = pd.read_csv(operator_view_path, dtype=str).fillna("")
    assert len(operator_view_df) == 1
    assert operator_view_df.iloc[0]["seller_sku"] == "SKU-O-RUNNER-1"
    repricer_tracker_path = tmp_path / get_o_output_contract("repricer_tracker_view").rel_path
    repricer_health_path = tmp_path / get_o_output_contract("repricer_tracker_health").rel_path
    assert repricer_tracker_path.exists()
    assert repricer_health_path.exists()

    handoff_log_path = tmp_path / get_o_output_contract("send_to_amazon_handoff_log").rel_path
    handoff_log_df = pd.read_csv(handoff_log_path, dtype=str).fillna("")
    assert len(handoff_log_df) == 0
