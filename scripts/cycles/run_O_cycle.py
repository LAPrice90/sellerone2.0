from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

BOOT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT))

try:
    from scripts.core.run_manifest import (
        append_step,
        finalize_manifest,
        new_manifest,
        run_id_for_cycle,
        utc_now_iso,
        write_manifest,
    )
except ModuleNotFoundError:
    from core.run_manifest import (
        append_step,
        finalize_manifest,
        new_manifest,
        run_id_for_cycle,
        utc_now_iso,
        write_manifest,
    )

from scripts.flows.O.O001_build_restock_source_view import build_restock_source_view
from scripts.flows.O.O002_build_restock_recommendations import build_restock_recommendations
from scripts.flows.O.O003_build_restock_review_queue import build_restock_review_queue
from scripts.flows.O.O004_build_restock_diagnostics import build_restock_diagnostics
from scripts.flows.O.O005_build_supplier_cost_snapshot_test import build_supplier_cost_snapshot_test
from scripts.flows.O.O007_build_supplier_buy_cost_truth import build_supplier_buy_cost_truth
from scripts.flows.O.O008_build_supplier_cost_confirmation_queue import build_supplier_cost_confirmation_queue
from scripts.flows.O.O010_apply_restock_decisions import apply_restock_decisions
from scripts.flows.O.O020_build_reorder_input_coverage_report import build_reorder_input_coverage_report
from scripts.flows.O.O021_build_restock_profit_checks import build_restock_profit_checks
from scripts.flows.O.O030_build_product_db_operator_view import build_product_db_operator_view
from scripts.flows.O.O050_build_repricing_tracker_view import build_repricing_tracker_view
from scripts.flows.O.O100_build_purchase_orders import build_purchase_orders
from scripts.flows.O.O200_build_ordered_stock_state import build_ordered_stock_state
from scripts.flows.O.O210_apply_receiving_events import apply_receiving_events
from scripts.flows.O.O300_build_send_to_amazon_queue import build_send_to_amazon_queue
from scripts.flows.O.O310_close_send_to_amazon_handoff import close_send_to_amazon_handoff
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract
from scripts.flows.O._schemas import get_o_output_contract


ROOT = Path(__file__).resolve().parents[2]
LIVE_SAFE_MODE = "live_safe"
TEST_MODE = "test"


@dataclass(frozen=True)
class OStepSpec:
    name: str
    script_or_function: str
    runner: Callable[[Path, str], None]
    required_outputs: tuple[str, ...]


def _step_o005(root: Path, mode: str) -> None:
    build_supplier_cost_snapshot_test(root=root)


def _step_o007(root: Path, mode: str) -> None:
    build_supplier_buy_cost_truth(root=root)


def _step_o008(root: Path, mode: str) -> None:
    build_supplier_cost_confirmation_queue(root=root)


def _step_o001(root: Path, mode: str) -> None:
    source_cost_mode = "test" if mode == TEST_MODE else "live"
    build_restock_source_view(root=root, cost_mode=source_cost_mode)


def _step_o002(root: Path, mode: str) -> None:
    build_restock_recommendations(root=root)


def _step_o003(root: Path, mode: str) -> None:
    build_restock_review_queue(root=root)


def _step_o004(root: Path, mode: str) -> None:
    build_restock_diagnostics(root=root)


def _step_o010(root: Path, mode: str) -> None:
    apply_restock_decisions(root=root)


def _step_o020(root: Path, mode: str) -> None:
    build_reorder_input_coverage_report(root=root)


def _step_o021(root: Path, mode: str) -> None:
    build_restock_profit_checks(root=root)


def _step_o100(root: Path, mode: str) -> None:
    build_purchase_orders(root=root)


def _step_o210(root: Path, mode: str) -> None:
    apply_receiving_events(root=root)


def _step_o200(root: Path, mode: str) -> None:
    build_ordered_stock_state(root=root)


def _step_o310(root: Path, mode: str) -> None:
    close_send_to_amazon_handoff(root=root)


def _step_o300(root: Path, mode: str) -> None:
    build_send_to_amazon_queue(root=root)


def _step_o030(root: Path, mode: str) -> None:
    build_product_db_operator_view(root=root)


def _step_o050(root: Path, mode: str) -> None:
    build_repricing_tracker_view(root=root)


def _contract_rel(name: str) -> str:
    return get_o_output_contract(name).rel_path


def build_o_step_plan(*, mode: str, enable_test_cost_feeder: bool = False) -> list[OStepSpec]:
    if mode not in {LIVE_SAFE_MODE, TEST_MODE}:
        raise ValueError(f"unsupported mode: {mode}")

    use_test_feeder = mode == TEST_MODE or bool(enable_test_cost_feeder)
    steps: list[OStepSpec] = []
    if use_test_feeder:
        steps.append(
            OStepSpec(
                name="O005_build_supplier_cost_snapshot_test",
                script_or_function="O005_build_supplier_cost_snapshot_test.py",
                runner=_step_o005,
                required_outputs=(_contract_rel("supplier_cost_snapshot_test"),),
            )
        )

    steps.extend(
        [
            OStepSpec(
                name="O007_build_supplier_buy_cost_truth",
                script_or_function="O007_build_supplier_buy_cost_truth.py",
                runner=_step_o007,
                required_outputs=(_contract_rel("supplier_buy_cost_truth"),),
            ),
            OStepSpec(
                name="O008_build_supplier_cost_confirmation_queue",
                script_or_function="O008_build_supplier_cost_confirmation_queue.py",
                runner=_step_o008,
                required_outputs=(_contract_rel("supplier_cost_confirmation_queue"),),
            ),
            OStepSpec(
                name="O001_build_restock_source_view",
                script_or_function="O001_build_restock_source_view.py",
                runner=_step_o001,
                required_outputs=(_contract_rel("restock_source_view"),),
            ),
            OStepSpec(
                name="O002_build_restock_recommendations",
                script_or_function="O002_build_restock_recommendations.py",
                runner=_step_o002,
                required_outputs=(_contract_rel("restock_recommendations_live"),),
            ),
            OStepSpec(
                name="O003_build_restock_review_queue",
                script_or_function="O003_build_restock_review_queue.py",
                runner=_step_o003,
                required_outputs=(_contract_rel("restock_review_queue"),),
            ),
            OStepSpec(
                name="O004_build_restock_diagnostics",
                script_or_function="O004_build_restock_diagnostics.py",
                runner=_step_o004,
                required_outputs=(
                    "out/systems/O/live/restock_diagnostics.csv",
                    "out/systems/O/live/restock_diagnostics_summary.csv",
                ),
            ),
            OStepSpec(
                name="O020_build_reorder_input_coverage_report",
                script_or_function="O020_build_reorder_input_coverage_report.py",
                runner=_step_o020,
                required_outputs=(
                    _contract_rel("reorder_input_coverage_report"),
                    _contract_rel("reorder_input_coverage_by_supplier"),
                    _contract_rel("reorder_input_block_reasons"),
                ),
            ),
            OStepSpec(
                name="O021_build_restock_profit_checks",
                script_or_function="O021_build_restock_profit_checks.py",
                runner=_step_o021,
                required_outputs=(
                    _contract_rel("restock_profit_checks_live"),
                    _contract_rel("restock_profit_check_health"),
                    _contract_rel("restock_profit_check_history"),
                ),
            ),
            OStepSpec(
                name="O010_apply_restock_decisions",
                script_or_function="O010_apply_restock_decisions.py",
                runner=_step_o010,
                required_outputs=(_contract_rel("restock_decisions_log"),),
            ),
            OStepSpec(
                name="O100_build_purchase_orders",
                script_or_function="O100_build_purchase_orders.py",
                runner=_step_o100,
                required_outputs=(
                    _contract_rel("purchase_orders_live"),
                    _contract_rel("purchase_order_lines_live"),
                    _contract_rel("purchase_order_draft_holds"),
                ),
            ),
            OStepSpec(
                name="O210_apply_receiving_events",
                script_or_function="O210_apply_receiving_events.py",
                runner=_step_o210,
                required_outputs=(
                    _contract_rel("receiving_events"),
                    _contract_rel("receiving_event_holds"),
                ),
            ),
            OStepSpec(
                name="O200_build_ordered_stock_state",
                script_or_function="O200_build_ordered_stock_state.py",
                runner=_step_o200,
                required_outputs=(_contract_rel("ordered_stock_state"),),
            ),
            OStepSpec(
                name="O310_close_send_to_amazon_handoff",
                script_or_function="O310_close_send_to_amazon_handoff.py",
                runner=_step_o310,
                required_outputs=(
                    _contract_rel("send_to_amazon_handoff_log"),
                    _contract_rel("send_to_amazon_handoff_holds"),
                    _contract_rel("send_to_amazon_queue"),
                ),
            ),
            OStepSpec(
                name="O300_build_send_to_amazon_queue",
                script_or_function="O300_build_send_to_amazon_queue.py",
                runner=_step_o300,
                required_outputs=(_contract_rel("send_to_amazon_queue"),),
            ),
            OStepSpec(
                name="O030_build_product_db_operator_view",
                script_or_function="O030_build_product_db_operator_view.py",
                runner=_step_o030,
                required_outputs=(
                    _contract_rel("product_db_operator_view"),
                    _contract_rel("product_db_source_health"),
                ),
            ),
            OStepSpec(
                name="O050_build_repricing_tracker_view",
                script_or_function="O050_build_repricing_tracker_view.py",
                runner=_step_o050,
                required_outputs=(
                    _contract_rel("repricer_tracker_view"),
                    _contract_rel("repricer_tracker_health"),
                ),
            ),
        ]
    )
    return steps


def _verify_outputs(root: Path, rel_paths: tuple[str, ...]) -> tuple[bool, list[str], list[str]]:
    fresh_outputs: list[str] = []
    missing_outputs: list[str] = []
    for rel in rel_paths:
        target = root / rel
        if target.exists():
            fresh_outputs.append(rel)
        else:
            missing_outputs.append(rel)
    return len(missing_outputs) == 0, fresh_outputs, missing_outputs


def run_o_cycle(
    *,
    root: Path | None = None,
    mode: str = LIVE_SAFE_MODE,
    enable_test_cost_feeder: bool = False,
    verify_outputs: bool = True,
    run_id: str | None = None,
    step_plan_override: list[OStepSpec] | None = None,
) -> tuple[int, dict, Path]:
    root_path = Path(root) if root is not None else ROOT
    ensure_o_directories(root=root_path)

    if mode not in {LIVE_SAFE_MODE, TEST_MODE}:
        raise ValueError(f"unsupported mode: {mode}")

    use_test_feeder = mode == TEST_MODE or bool(enable_test_cost_feeder)
    plan = list(step_plan_override) if step_plan_override is not None else build_o_step_plan(
        mode=mode,
        enable_test_cost_feeder=enable_test_cost_feeder,
    )

    cycle_run_id = run_id or run_id_for_cycle("O")
    manifest = new_manifest(cycle="O", run_id=cycle_run_id, start_time=utc_now_iso())
    manifest["configured_step_count"] = len(plan)
    manifest["mode"] = mode
    manifest["test_cost_feeder_enabled"] = bool(use_test_feeder)
    manifest["verify_outputs"] = bool(verify_outputs)
    manifest["notes"] = "isolated_o_cycle_runner"

    cycle_rc = 0
    for step in plan:
        started_at = utc_now_iso()
        step_rc = 0
        step_notes = ""
        launched = True
        completed = False
        outputs_verified = False
        verification_status = "not_checked"
        fresh_outputs: list[str] = []
        missing_outputs: list[str] = []

        try:
            step.runner(root_path, mode)
            completed = True
            if verify_outputs:
                outputs_verified, fresh_outputs, missing_outputs = _verify_outputs(root_path, step.required_outputs)
                verification_status = "verified" if outputs_verified else "missing_required_outputs"
                if not outputs_verified:
                    step_rc = 2
                    step_notes = "required_output_missing"
            else:
                outputs_verified = False
                verification_status = "verification_skipped"
        except Exception as exc:
            step_rc = 1
            completed = True
            step_notes = f"{type(exc).__name__}:{exc}"

        if step_rc == 0:
            step_status = "completed" if (outputs_verified or not verify_outputs) else "completed_unverified"
        elif step_rc == 2:
            step_status = "verification_failed"
        else:
            step_status = "failed"

        append_step(
            manifest,
            name=step.name,
            script_or_function=step.script_or_function,
            inputs=[],
            outputs=list(step.required_outputs),
            rc=step_rc,
            notes=step_notes,
            started_at=started_at,
            ended_at=utc_now_iso(),
            launched=launched,
            completed=completed,
            outputs_verified=outputs_verified,
            step_status=step_status,
            verification_status=verification_status,
            required_outputs=list(step.required_outputs),
            fresh_outputs=fresh_outputs,
            missing_outputs=missing_outputs,
        )

        if step_rc != 0:
            cycle_rc = step_rc
            break

    final_state = "completed" if cycle_rc == 0 else "failed"
    finalize_manifest(
        manifest,
        end_time=utc_now_iso(),
        final_state=final_state,
        health_summary={
            "source": "",
            "status": "not_applicable",
            "current_cycle_evidence": False,
            "fail_count": None,
            "warn_count": None,
            "ok_count": None,
            "notes": "isolated_runner_no_shared_gate",
        },
    )
    manifest_path = write_manifest(root_path, manifest)

    print(
        json.dumps(
            {
                "cycle": "O",
                "run_id": cycle_run_id,
                "mode": mode,
                "test_cost_feeder_enabled": use_test_feeder,
                "verify_outputs": verify_outputs,
                "rc": cycle_rc,
                "manifest": str(manifest_path),
                "steps_recorded": int(manifest.get("recorded_step_count", 0)),
                "final_state": manifest.get("final_state", ""),
            },
            ensure_ascii=True,
        )
    )
    return cycle_rc, manifest, manifest_path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run isolated O cycle orchestration in dependency order.")
    parser.add_argument(
        "--mode",
        choices=(LIVE_SAFE_MODE, TEST_MODE),
        default=LIVE_SAFE_MODE,
        help="O cycle mode. live_safe skips O005 unless --enable-test-cost-feeder is set. test enables O005 + test cost mode.",
    )
    parser.add_argument(
        "--enable-test-cost-feeder",
        action="store_true",
        help="Run O005 test supplier cost feeder even in live_safe mode.",
    )
    parser.add_argument(
        "--no-verify-outputs",
        action="store_true",
        help="Skip expected output existence verification after each step.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Optional explicit run id for manifest naming.",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Optional root path for isolated test runs (defaults to repo root).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    root = Path(args.root) if args.root else None
    rc, _, _ = run_o_cycle(
        root=root,
        mode=args.mode,
        enable_test_cost_feeder=bool(args.enable_test_cost_feeder),
        verify_outputs=not bool(args.no_verify_outputs),
        run_id=args.run_id,
    )
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
