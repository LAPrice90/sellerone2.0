from __future__ import annotations

import csv
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sellerone_manager.hourly_mot import (
    A_PROOF_ONLY_SQL_TABLES,
    A_REQUIRED_OUTPUTS,
    A_SQL_TABLES,
    B_REQUIRED_OUTPUTS,
    E_CORE_OUTPUTS,
    E_INPUT_PROOFS,
    O_ACTIVE_PROOF_OUTPUTS,
    build_a_hourly_mot,
    build_all_hourly_mot,
    build_b_hourly_mot,
    build_e_hourly_mot,
    build_f_hourly_mot,
    build_mot_worklist,
    build_o_hourly_mot,
    update_mot_work_item_status,
    write_all_hourly_mot_outputs,
    write_hourly_mot_outputs,
)
from sellerone_manager.b_order_recovery import EXPECTED_QUARANTINE_REL_PATH, QUARANTINE_REQUIRED_COLUMNS
from sellerone_manager.sellerboard_bridge import (
    ORDER_RECONCILIATION_COLUMNS,
    ORDER_RECONCILIATION_NAME,
    SELLERBOARD_REQUIRED_COLUMNS,
    SKU_GAP_COLUMNS,
    SKU_GAP_NAME,
    SUMMARY_COLUMNS,
    SUMMARY_NAME,
)
from sellerone_manager.sellerboard_email_intake import SOURCE_PROOF_REL_PATH


OBSERVED = "2026-05-26T10:00:00Z"


def test_b_warn_rows_fill_manager_board_lanes() -> None:
    result = {
        "observed_utc": OBSERVED,
        "flow": "B",
        "quiet_autonomy_active": False,
        "rows": [
            {
                "flow": "B",
                "check": "b_pnl_daily",
                "status": "warn",
                "manager_action": "Keep P and L warning-labelled.",
                "safe_repair_boundary": "B P and L proof only.",
            },
            {
                "flow": "B",
                "check": "b_marketplace_coverage_report",
                "status": "warn",
                "manager_action": "Create a bounded B manager task for marketplace coverage proof.",
                "safe_repair_boundary": "B marketplace coverage reporting only.",
            },
            {
                "flow": "B",
                "check": "b_management_ready_for_maintenance",
                "status": "warn",
                "value": "ready_with_visible_order_truth_gaps",
                "manager_action": "B can be watched by the manager.",
                "safe_repair_boundary": "B manager readiness proof only.",
            },
        ],
    }

    rows = {row["check"]: row for row in build_mot_worklist(result)}

    assert rows["b_pnl_daily"]["status"] == "parked"
    assert rows["b_marketplace_coverage_report"]["status"] == "new"
    assert rows["b_management_ready_for_maintenance"]["status"] == "parked"
    assert rows["b_pnl_daily"]["luke_action_required"] == "0"
    assert rows["b_management_ready_for_maintenance"]["luke_action_required"] == "0"


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _write_csv(path: Path, rows: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "value"])
        for index in range(rows):
            writer.writerow([index, f"value_{index}"])


def _set_age(path: Path, hours: float) -> None:
    mtime = (_dt(OBSERVED) - timedelta(hours=hours)).timestamp()
    os.utime(path, (mtime, mtime))


def _write_manifest(
    root: Path,
    *,
    final_state: str = "completed",
    age_hours: float = 1.0,
    configured_step_count: int = 13,
    recorded_step_count: int = 13,
    steps: list[dict[str, object]] | None = None,
) -> Path:
    end_time = (_dt(OBSERVED) - timedelta(hours=age_hours)).isoformat().replace("+00:00", "Z")
    path = root / "out" / "manifests" / "A" / "2026-05-26" / "A_test.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "run_id": "A_test",
                "cycle": "A",
                "final_state": final_state,
                "end_time": end_time,
                "configured_step_count": configured_step_count,
                "recorded_step_count": recorded_step_count,
                "steps": steps or [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _set_age(path, age_hours)
    return path


def _write_b_manifest(
    root: Path,
    *,
    final_state: str = "completed",
    gate_state: str = "pass",
    gate_fail_count: int = 0,
    gate_warn_count: int = 0,
    age_hours: float = 0.25,
) -> Path:
    end_time = (_dt(OBSERVED) - timedelta(hours=age_hours)).isoformat().replace("+00:00", "Z")
    path = root / "out" / "manifests" / "B" / "2026-05-26" / "B_test.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "run_id": "B_test",
                "cycle": "B",
                "final_state": final_state,
                "end_time": end_time,
                "gate_state": gate_state,
                "gate_fail_count": gate_fail_count,
                "gate_warn_count": gate_warn_count,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _set_age(path, age_hours)
    return path


def _write_e_manifest(root: Path, *, final_state: str = "completed", age_hours: float = 0.25) -> Path:
    end_time = (_dt(OBSERVED) - timedelta(hours=age_hours)).isoformat().replace("+00:00", "Z")
    steps = [
        {
            "name": str(step),
            "script_or_function": str(step).split(":", 1)[0],
            "rc": 0,
            "step_status": "completed",
            "notes": "split_mode=split;split_fresh=1" if str(step).startswith("A015_") else "",
        }
        for step in [
            "E001_build_sales_velocity.py",
            "E002_build_roi_snapshot.py",
            "E003_build_restock_signals.py",
            "E004_build_performance_summary.py",
            "E005_build_study_report.py",
            "E006_build_sales_truth_reconciliation.py",
            "E007_build_sku_daily_sales_truth.py",
            "A015_build_system_health_check.py:profile=e",
        ]
    ]
    path = root / "out" / "manifests" / "E" / "2026-05-26" / "E_test.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "run_id": "E_test",
                "cycle": "E",
                "final_state": final_state,
                "end_time": end_time,
                "steps": steps,
                "health_summary": {
                    "source": str(root / "out" / "cycle_alerts" / "checklist_E_split.csv"),
                    "status": "current",
                    "current_cycle_evidence": True,
                    "fail_count": 0,
                    "warn_count": 0,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _set_age(path, age_hours)
    return path


def _write_e_run_log(root: Path, *, age_hours: float = 0.20, status: str = "success", run_id: str = "E_test") -> None:
    finished = (_dt(OBSERVED) - timedelta(hours=age_hours)).isoformat().replace("+00:00", "Z")
    path = root / "out" / "systems" / "E" / "live" / "e_run_log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "started_utc": finished,
                "finished_utc": finished,
                "status": status,
                "tasks_run": "E001_build_sales_velocity.py;E002_build_roi_snapshot.py",
                "elapsed_seconds": "2.000",
                "expected_input_asof": "2026-05-26",
                "output_asof": "2026-05-26",
                "asof_rerun_trigger": "0",
                "error": "",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _set_age(path, age_hours)


def _write_required_outputs(root: Path, *, stale_check: str | None = None) -> None:
    for item in A_REQUIRED_OUTPUTS:
        path = root / str(item["path"])
        _write_csv(path)
        _set_age(path, 40.0 if item["check"] == stale_check else 1.0)


def _write_b_required_outputs(root: Path, *, stale_check: str | None = None) -> None:
    for item in B_REQUIRED_OUTPUTS:
        path = root / str(item["path"])
        _write_csv(path, rows=max(int(item.get("min_rows", 1) or 0), 1))
        stale_hours = float(item.get("fail_hours", 3.0)) + 1.0
        _set_age(path, stale_hours if item["check"] == stale_check else 0.25)
    _write_b_stock_receipt_token_sync_clean_inputs(root)
    _write_b_email_intake(root)


def _write_b_stock_receipt_token_sync_clean_inputs(root: Path) -> None:
    _write_csv_rows(
        root / "out" / "token_allocations_live.csv",
        ["order_id", "order_date", "seller_sku", "quantity", "token_id", "token_cost", "currency", "allocation_date", "source_level", "notes"],
        [
            {
                "order_id": "205-1111111-1111111",
                "order_date": "2026-05-26T09:30:00Z",
                "seller_sku": "SKU-UK",
                "quantity": "1",
                "token_id": "TOKEN-001",
                "token_cost": "2.00",
                "currency": "GBP",
                "allocation_date": "2026-05-26T09:45:00Z",
                "source_level": "1",
                "notes": "test",
            }
        ],
    )
    _write_csv_rows(
        root / "out" / "order_master.csv",
        ["Date", "Order ID", "SKU", "Missing_Token_Flag", "COGS_Placeholder_Applied"],
        [
            {
                "Date": "2026-05-26T09:30:00Z",
                "Order ID": "205-1111111-1111111",
                "SKU": "SKU-UK",
                "Missing_Token_Flag": "0",
                "COGS_Placeholder_Applied": "0",
            }
        ],
    )
    _write_csv_rows(
        root / "out" / "orders_missing_tokens.csv",
        ["Order ID", "SKU", "Date", "Quantity Ordered", "placeholder_applied_flag"],
        [],
    )
    _write_csv_rows(
        root / "out" / "stock_receipts_latest.csv",
        ["row_num", "intake_date", "seller_sku", "qty", "cost_per_unit", "status", "batch_id", "tokens_created", "order_key", "error_message"],
        [
            {
                "row_num": "88",
                "intake_date": "2026-05-26",
                "seller_sku": "SKU-UK",
                "qty": "1",
                "cost_per_unit": "2.00",
                "status": "APPLIED",
                "batch_id": "SR-20260526-001",
                "tokens_created": "1",
                "order_key": "receipt-001",
                "error_message": "",
            }
        ],
    )
    for path in [
        root / "out" / "token_allocations_live.csv",
        root / "out" / "order_master.csv",
        root / "out" / "orders_missing_tokens.csv",
        root / "out" / "stock_receipts_latest.csv",
    ]:
        _set_age(path, 0.25)


def _write_b_sellerboard_bridge_outputs(
    root: Path,
    *,
    missing_orders: int = 0,
    unmapped_shipped: int = 0,
    return_gap: int = 0,
    fee_detail_rows: int = 1,
    refund_nonzero_rows: int = 1,
) -> None:
    bridge_dir = root / "out" / "systems" / "M" / "sellerboard_bridge"
    summary_rows = [
        {"observed_utc": OBSERVED, "metric": "overall_status", "status": "ok", "value": "ok", "proof_label": "API proved", "notes": "", "source_path": "sellerboard.csv"},
        {"observed_utc": OBSERVED, "metric": "required_columns_missing", "status": "ok", "value": "0", "proof_label": "API proved", "notes": "", "source_path": "sellerboard.csv"},
        {"observed_utc": OBSERVED, "metric": "sellerboard_shipped_missing_from_sellerone_orders", "status": "fail" if missing_orders else "ok", "value": str(missing_orders), "proof_label": "not yet proven" if missing_orders else "API proved", "notes": "", "source_path": "sellerboard.csv"},
        {"observed_utc": OBSERVED, "metric": "sellerboard_shipped_rows_unmapped_to_sku", "status": "fail" if unmapped_shipped else "ok", "value": str(unmapped_shipped), "proof_label": "not yet proven" if unmapped_shipped else "API proved", "notes": "", "source_path": "sellerboard.csv"},
        {"observed_utc": OBSERVED, "metric": "sellerboard_return_orders_missing_local_refund_posted_window", "status": "warn" if return_gap else "ok", "value": str(return_gap), "proof_label": "Sellerboard bridge estimate" if return_gap else "API proved", "notes": "", "source_path": "sellerboard.csv"},
        {"observed_utc": OBSERVED, "metric": "fee_detail_ledger_api_rows", "status": "warn" if fee_detail_rows == 0 else "ok", "value": str(fee_detail_rows), "proof_label": "not yet proven" if fee_detail_rows == 0 else "API proved", "notes": "", "source_path": "sellerboard.csv"},
        {"observed_utc": OBSERVED, "metric": "refund_api_proof_state", "status": "warn" if return_gap else "ok", "value": "sellerboard_bridge_only" if return_gap else "api_proved", "proof_label": "Sellerboard bridge estimate" if return_gap else "API proved", "notes": "", "source_path": "sellerboard.csv"},
        {"observed_utc": OBSERVED, "metric": "commission_api_proof_state", "status": "warn" if fee_detail_rows == 0 else "ok", "value": "not_yet_proven" if fee_detail_rows == 0 else "api_proved", "proof_label": "not yet proven" if fee_detail_rows == 0 else "API proved", "notes": "", "source_path": "sellerboard.csv"},
        {"observed_utc": OBSERVED, "metric": "fba_fee_api_proof_state", "status": "warn" if fee_detail_rows == 0 else "ok", "value": "not_yet_proven" if fee_detail_rows == 0 else "api_proved", "proof_label": "not yet proven" if fee_detail_rows == 0 else "API proved", "notes": "", "source_path": "sellerboard.csv"},
        {"observed_utc": OBSERVED, "metric": "other_fee_api_proof_state", "status": "ok", "value": "api_proved_or_not_applicable", "proof_label": "API proved", "notes": "", "source_path": "sellerboard.csv"},
        {"observed_utc": OBSERVED, "metric": "shipping_income_api_proof_state", "status": "ok", "value": "api_proved_or_not_applicable", "proof_label": "API proved", "notes": "", "source_path": "sellerboard.csv"},
        {"observed_utc": OBSERVED, "metric": "shipping_fee_api_proof_state", "status": "ok", "value": "api_proved_or_not_applicable", "proof_label": "API proved", "notes": "", "source_path": "sellerboard.csv"},
        {"observed_utc": OBSERVED, "metric": "roi_money_confidence_state", "status": "warn" if return_gap or fee_detail_rows == 0 or refund_nonzero_rows == 0 else "ok", "value": "not_yet_proven" if return_gap or fee_detail_rows == 0 or refund_nonzero_rows == 0 else "api_backed_safe", "proof_label": "not yet proven" if return_gap or fee_detail_rows == 0 or refund_nonzero_rows == 0 else "API proved", "notes": "", "source_path": "sellerboard.csv"},
        {"observed_utc": OBSERVED, "metric": "roi_expected_refund_nonzero_rows", "status": "warn" if refund_nonzero_rows == 0 else "ok", "value": str(refund_nonzero_rows), "proof_label": "not yet proven" if refund_nonzero_rows == 0 else "API proved", "notes": "", "source_path": "sellerboard.csv"},
        {"observed_utc": OBSERVED, "metric": "sellerboard_return_rows", "status": "ok", "value": "1", "proof_label": "Sellerboard bridge estimate", "notes": "", "source_path": "sellerboard.csv"},
        {"observed_utc": OBSERVED, "metric": "refund_proof_state", "status": "warn" if return_gap else "ok", "value": "not_yet_proven" if return_gap else "api_proved_or_not_applicable", "proof_label": "not yet proven" if return_gap else "API proved", "notes": "", "source_path": "sellerboard.csv"},
        {"observed_utc": OBSERVED, "metric": "fee_shipping_proof_state", "status": "warn" if fee_detail_rows == 0 else "ok", "value": "not_yet_proven" if fee_detail_rows == 0 else "api_proved", "proof_label": "not yet proven" if fee_detail_rows == 0 else "API proved", "notes": "", "source_path": "sellerboard.csv"},
        {"observed_utc": OBSERVED, "metric": "roi_refund_proof_state", "status": "warn" if refund_nonzero_rows == 0 else "ok", "value": "not_yet_proven" if refund_nonzero_rows == 0 else "api_proved_or_not_applicable", "proof_label": "not yet proven" if refund_nonzero_rows == 0 else "API proved", "notes": "", "source_path": "sellerboard.csv"},
        {"observed_utc": OBSERVED, "metric": "bridge_values_safe_for_live_roi", "status": "warn" if return_gap or fee_detail_rows == 0 or refund_nonzero_rows == 0 else "ok", "value": "0" if return_gap or fee_detail_rows == 0 or refund_nonzero_rows == 0 else "1", "proof_label": "not yet proven" if return_gap or fee_detail_rows == 0 or refund_nonzero_rows == 0 else "API proved", "notes": "", "source_path": "sellerboard.csv"},
    ]
    _write_csv_rows(bridge_dir / SUMMARY_NAME, SUMMARY_COLUMNS, summary_rows)
    _write_csv_rows(
        bridge_dir / ORDER_RECONCILIATION_NAME,
        ORDER_RECONCILIATION_COLUMNS,
        [
            {
                "amazon_order_id": "205-1111111-1111111",
                "sellerboard_status": "Shipped",
                "sellerboard_purchase_utc": "2026-05-20T10:00:00Z",
                "sellerboard_asin": "B000000001",
                "mapped_sku": "SKU1",
                "local_order_status": "Shipped",
                "local_purchase_utc": "2026-05-20T10:00:00Z",
                "sellerboard_units": "1",
                "sellerboard_order_total": "10",
                "sellerboard_shipping": "0",
                "sellerboard_commission": "-1",
                "sellerboard_fba_fee": "-2",
                "local_order_total": "10",
                "match_status": "matched",
                "proof_label": "API proved",
            }
        ],
    )
    _write_csv_rows(
        bridge_dir / SKU_GAP_NAME,
        SKU_GAP_COLUMNS,
        [
            {
                "sku": "SKU1",
                "sellerboard_asin": "B000000001",
                "sellerboard_rows": "1",
                "sellerboard_shipped_units": "1",
                "sellerboard_return_rows": "0",
                "sellerboard_order_total": "10",
                "sellerboard_shipping_paid": "0",
                "sellerboard_shipping_cost": "0",
                "sellerboard_commission": "-1",
                "sellerboard_fba_fee": "-2",
                "local_refund_rows": "0",
                "local_refund_amount": "0",
                "expected_refund_cost_per_unit_gbp": "0",
                "refund_connection_state": "not applicable",
                "fee_connection_state": "API proved",
                "bridge_label": "API proved",
            }
        ],
    )
    for path in [bridge_dir / SUMMARY_NAME, bridge_dir / ORDER_RECONCILIATION_NAME, bridge_dir / SKU_GAP_NAME]:
        _set_age(path, 0.25)


def _write_b_refund_fee_shipping_gap_review(root: Path, *, safe_for_live_roi: bool = False) -> None:
    refund_dir = root / "out" / "systems" / "B" / "refunds"
    review_columns = [
        "money_area",
        "manager_money_label",
        "source_metric",
        "source_value",
        "api_proof_state",
        "sellerboard_witness_rows",
        "gap_rows",
        "downstream_warning_rows",
        "live_roi_use_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "manager_expectation",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
        "source_path",
    ]
    review_rows = [
        {
            "money_area": "api_refund_money",
            "manager_money_label": "api_proved",
            "source_metric": "b_refund_pnl_bridge.api_refund_proof_state",
            "source_value": "api_rows=1;bridge_rows=0;total_rows=1",
            "api_proof_state": "api_proved",
            "sellerboard_witness_rows": "0",
            "gap_rows": "0",
            "downstream_warning_rows": "0",
            "live_roi_use_allowed": "0",
            "roi_or_restock_use_allowed": "0",
            "sellerboard_final_truth_allowed": "0",
            "manager_expectation": "label money proof",
            "bounded_worker_task": "manager proof only",
            "retest_rule": "rerun MOT",
            "protected_stop_rule": "stop before live ROI",
            "source_path": "b_refund_pnl_bridge.csv",
        },
        {
            "money_area": "sellerboard_return_refund_gap",
            "manager_money_label": "api_proved" if safe_for_live_roi else "sellerboard_bridge_estimate",
            "source_metric": "sellerboard_return_orders_missing_local_refund_posted_window",
            "source_value": "0" if safe_for_live_roi else "1",
            "api_proof_state": "api_proved" if safe_for_live_roi else "sellerboard_bridge_only",
            "sellerboard_witness_rows": "0" if safe_for_live_roi else "1",
            "gap_rows": "0" if safe_for_live_roi else "1",
            "downstream_warning_rows": "0",
            "live_roi_use_allowed": "0",
            "roi_or_restock_use_allowed": "0",
            "sellerboard_final_truth_allowed": "0",
            "manager_expectation": "label money proof",
            "bounded_worker_task": "manager proof only",
            "retest_rule": "rerun MOT",
            "protected_stop_rule": "stop before live ROI",
            "source_path": "sellerboard_summary.csv",
        },
        {
            "money_area": "commission_fee",
            "manager_money_label": "api_proved",
            "source_metric": "b_level3_fee_shipping_api_proof_map.commission",
            "source_value": "level3_label=api_source_available",
            "api_proof_state": "level3_api_source_available",
            "sellerboard_witness_rows": "0",
            "gap_rows": "0",
            "downstream_warning_rows": "0",
            "live_roi_use_allowed": "0",
            "roi_or_restock_use_allowed": "0",
            "sellerboard_final_truth_allowed": "0",
            "manager_expectation": "label money proof",
            "bounded_worker_task": "manager proof only",
            "retest_rule": "rerun MOT",
            "protected_stop_rule": "stop before live ROI",
            "source_path": "b_level3_fee_shipping_api_proof_map.csv",
        },
        {
            "money_area": "fba_fee",
            "manager_money_label": "api_proved",
            "source_metric": "b_level3_fee_shipping_api_proof_map.fba_fee",
            "source_value": "level3_label=api_source_available",
            "api_proof_state": "level3_api_source_available",
            "sellerboard_witness_rows": "0",
            "gap_rows": "0",
            "downstream_warning_rows": "0",
            "live_roi_use_allowed": "0",
            "roi_or_restock_use_allowed": "0",
            "sellerboard_final_truth_allowed": "0",
            "manager_expectation": "label money proof",
            "bounded_worker_task": "manager proof only",
            "retest_rule": "rerun MOT",
            "protected_stop_rule": "stop before live ROI",
            "source_path": "b_level3_fee_shipping_api_proof_map.csv",
        },
        {
            "money_area": "shipping_income",
            "manager_money_label": "api_proved",
            "source_metric": "b_level3_fee_shipping_api_proof_map.shipping_income",
            "source_value": "level3_label=api_source_available",
            "api_proof_state": "level3_api_source_available",
            "sellerboard_witness_rows": "0",
            "gap_rows": "0",
            "downstream_warning_rows": "0",
            "live_roi_use_allowed": "0",
            "roi_or_restock_use_allowed": "0",
            "sellerboard_final_truth_allowed": "0",
            "manager_expectation": "label money proof",
            "bounded_worker_task": "manager proof only",
            "retest_rule": "rerun MOT",
            "protected_stop_rule": "stop before live ROI",
            "source_path": "b_level3_fee_shipping_api_proof_map.csv",
        },
        {
            "money_area": "shipping_fee",
            "manager_money_label": "api_proved" if safe_for_live_roi else "not_yet_proven",
            "source_metric": "b_level3_fee_shipping_api_proof_map.shipping_chargeback_or_cost",
            "source_value": "level3_label=repo_path_unclear",
            "api_proof_state": "api_proved" if safe_for_live_roi else "repo_path_unclear",
            "sellerboard_witness_rows": "0",
            "gap_rows": "0" if safe_for_live_roi else "1",
            "downstream_warning_rows": "0",
            "live_roi_use_allowed": "0",
            "roi_or_restock_use_allowed": "0",
            "sellerboard_final_truth_allowed": "0",
            "manager_expectation": "label money proof",
            "bounded_worker_task": "manager proof only",
            "retest_rule": "rerun MOT",
            "protected_stop_rule": "stop before live ROI",
            "source_path": "b_level3_fee_shipping_api_proof_map.csv",
        },
    ]
    _write_csv_rows(refund_dir / "b_refund_fee_shipping_gap_review.csv", review_columns, review_rows)
    summary_columns = ["metric", "value"]
    _write_csv_rows(
        refund_dir / "b_refund_fee_shipping_gap_review_summary.csv",
        summary_columns,
        [
            {"metric": "api_proved_rows", "value": "6" if safe_for_live_roi else "4"},
            {"metric": "sellerboard_bridge_estimate_rows", "value": "0" if safe_for_live_roi else "1"},
            {"metric": "not_yet_proven_rows", "value": "0" if safe_for_live_roi else "1"},
            {"metric": "bridge_values_safe_for_live_roi", "value": "1" if safe_for_live_roi else "0"},
            {"metric": "b_source_handoff_ready", "value": "1" if safe_for_live_roi else "0"},
        ],
    )
    for path in [
        refund_dir / "b_refund_fee_shipping_gap_review.csv",
        refund_dir / "b_refund_fee_shipping_gap_review_summary.csv",
    ]:
        _set_age(path, 0.25)


def _write_b_marketplace_gap_inputs(root: Path) -> None:
    _write_csv_rows(
        root / "out" / "marketplace_participations.csv",
        ["marketplace_id", "name", "country_code", "domain_name", "is_participating"],
        [
            {"marketplace_id": "A1F83G8C2ARO7P", "name": "Amazon.co.uk", "country_code": "GB", "domain_name": "www.amazon.co.uk", "is_participating": "1"},
            {"marketplace_id": "A2VIGQ35RCS4UG", "name": "Amazon.ae", "country_code": "AE", "domain_name": "www.amazon.ae", "is_participating": "1"},
        ],
    )
    _write_csv_rows(
        root / "out" / "orders_all.csv",
        ["amazon_order_id", "purchase_date", "order_status", "marketplace_id", "sales_channel", "order_total_currency"],
        [
            {"amazon_order_id": "205-1111111-1111111", "purchase_date": "2026-05-26T10:00:00Z", "order_status": "Shipped", "marketplace_id": "A1F83G8C2ARO7P", "sales_channel": "Amazon.co.uk", "order_total_currency": "GBP"},
            {"amazon_order_id": "404-7471611-6464300", "purchase_date": "2026-02-13T06:10:10Z", "order_status": "Shipped", "marketplace_id": "A2VIGQ35RCS4UG", "sales_channel": "Amazon.ae", "order_total_currency": "AED"},
        ],
    )
    _write_csv_rows(
        root / "out" / "order_items_all.csv",
        ["amazon_order_id", "asin", "seller_sku", "quantity_ordered"],
        [
            {"amazon_order_id": "205-1111111-1111111", "asin": "B1", "seller_sku": "SKU-UK", "quantity_ordered": "1"},
            {"amazon_order_id": "404-7471611-6464300", "asin": "B3", "seller_sku": "SKU-AE-OLD", "quantity_ordered": "1"},
        ],
    )
    _write_csv_rows(
        root / "out" / "financial_events_level1.csv",
        ["Date", "Order ID", "marketplace_id", "SKU"],
        [
            {"Date": "2026-05-26T10:00:00Z", "Order ID": "205-1111111-1111111", "marketplace_id": "A1F83G8C2ARO7P", "SKU": "SKU-UK"},
            {"Date": "2026-02-13T06:10:10Z", "Order ID": "404-7471611-6464300", "marketplace_id": "A2VIGQ35RCS4UG", "SKU": "SKU-AE-OLD"},
        ],
    )
    _write_csv_rows(
        root / "out" / "order_master.csv",
        ["Date", "Order ID", "SKU", "country_code", "currency_code"],
        [
            {"Date": "2026-05-26T10:00:00Z", "Order ID": "205-1111111-1111111", "SKU": "SKU-UK", "country_code": "GB", "currency_code": "GBP"},
            {"Date": "2026-02-13T06:10:10Z", "Order ID": "404-7471611-6464300", "SKU": "SKU-AE-OLD", "country_code": "AE", "currency_code": "AED"},
        ],
    )
    _write_csv_rows(root / "out" / "financial_events_level3_official.csv", ["Order ID", "SKU", "FBA_Fee_ExVAT"], [])
    _write_csv_rows(root / "out" / "financial_events_refunds.csv", ["order_id", "sku", "amount"], [])
    (root / "out" / "orders_last_updated.txt").write_text("2026-05-27T10:00:00Z", encoding="utf-8")
    _write_csv_rows(
        root / "out" / "systems" / "M" / "sellerboard_bridge" / ORDER_RECONCILIATION_NAME,
        ORDER_RECONCILIATION_COLUMNS,
        [
            {
                "amazon_order_id": "171-1388771-2409132",
                "sellerboard_status": "Shipped",
                "sellerboard_purchase_utc": "2026-05-23T11:59:20Z",
                "sellerboard_sales_channel": "Amazon.ae",
                "sellerboard_currency": "GBP",
                "sellerboard_asin": "B072K2PG11",
                "match_status": "sellerboard_shipped_missing_in_sellerone",
                "proof_label": "Sellerboard bridge estimate",
            }
        ],
    )
    for path in [
        root / "out" / "orders_all.csv",
        root / "out" / "order_items_all.csv",
        root / "out" / "order_master.csv",
        root / "out" / "systems" / "M" / "sellerboard_bridge" / ORDER_RECONCILIATION_NAME,
    ]:
        _set_age(path, 0.25)


def _write_b_recovery_quarantine(root: Path) -> None:
    order_payload = {
        "AmazonOrderId": "171-1388771-2409132",
        "PurchaseDate": "2026-05-23T11:59:20Z",
        "LastUpdateDate": "2026-05-23T12:02:00Z",
        "OrderStatus": "Shipped",
        "MarketplaceId": "A2VIGQ35RCS4UG",
        "SalesChannel": "Amazon.ae",
        "FulfillmentChannel": "AFN",
        "OrderTotal": {"Amount": "41.19", "CurrencyCode": "AED"},
    }
    item_payload = {
        "AmazonOrderId": "171-1388771-2409132",
        "OrderItemId": "63511800911762",
        "ASIN": "B072K2PG11",
        "SellerSKU": "GH-XAAE-HRU7",
        "QuantityOrdered": 1,
        "QuantityShipped": 1,
        "ItemPrice": {"Amount": "41.19", "CurrencyCode": "AED"},
    }
    _write_csv_rows(
        root / EXPECTED_QUARANTINE_REL_PATH,
        QUARANTINE_REQUIRED_COLUMNS,
        [
            {
                "amazon_order_id": "171-1388771-2409132",
                "marketplace_id": "A2VIGQ35RCS4UG",
                "purchase_utc": "2026-05-23T11:59:20Z",
                "order_status": "Shipped",
                "sku": "GH-XAAE-HRU7",
                "asin": "B072K2PG11",
                "order_item_ids": "63511800911762",
                "quantity": "1",
                "currency": "AED",
                "order_total": "41.19",
                "last_update_utc": "2026-05-23T12:02:00Z",
                "sales_channel": "Amazon.ae",
                "fulfillment_channel": "AFN",
                "order_payload_json": json.dumps(order_payload),
                "items_payload_json": json.dumps([item_payload]),
                "source": "api_backdate",
                "proof_label": "API proved",
                "duplicate_state": "unique_in_quarantine",
                "ready_for_live_merge": "0",
            }
        ],
    )


def _write_b_cursor_proof(root: Path) -> None:
    _write_csv_rows(
        root / "out" / "systems" / "B" / "order_cursors" / "b_marketplace_order_cursors.csv",
        ["marketplace_id", "last_success_utc", "cursor_utc", "status"],
        [
            {"marketplace_id": "A1F83G8C2ARO7P", "last_success_utc": "2026-05-26T09:45:00Z", "cursor_utc": "2026-05-26T09:45:00Z", "status": "ok"},
            {"marketplace_id": "A2VIGQ35RCS4UG", "last_success_utc": "2026-05-26T09:45:00Z", "cursor_utc": "2026-05-26T09:45:00Z", "status": "ok"},
        ],
    )


def _write_b_completion_clean_inputs(root: Path) -> None:
    _write_b_sellerboard_bridge_outputs(root)
    _write_csv_rows(
        root / "out" / "marketplace_participations.csv",
        ["marketplace_id", "name", "country_code", "domain_name", "is_participating"],
        [
            {"marketplace_id": "A1F83G8C2ARO7P", "name": "Amazon.co.uk", "country_code": "GB", "domain_name": "www.amazon.co.uk", "is_participating": "1"},
            {"marketplace_id": "A2VIGQ35RCS4UG", "name": "Amazon.ae", "country_code": "AE", "domain_name": "www.amazon.ae", "is_participating": "1"},
        ],
    )
    _write_csv_rows(
        root / "out" / "orders_all.csv",
        ["amazon_order_id", "purchase_date", "order_status", "marketplace_id", "sales_channel", "order_total_currency"],
        [
            {"amazon_order_id": "205-1111111-1111111", "purchase_date": "2026-05-26T10:00:00Z", "order_status": "Shipped", "marketplace_id": "A1F83G8C2ARO7P", "sales_channel": "Amazon.co.uk", "order_total_currency": "GBP"},
            {"amazon_order_id": "171-1388771-2409132", "purchase_date": "2026-05-23T11:59:20Z", "order_status": "Shipped", "marketplace_id": "A2VIGQ35RCS4UG", "sales_channel": "Amazon.ae", "order_total_currency": "AED"},
        ],
    )
    _write_csv_rows(
        root / "out" / "order_items_all.csv",
        ["amazon_order_id", "asin", "seller_sku", "quantity_ordered"],
        [
            {"amazon_order_id": "205-1111111-1111111", "asin": "B000000001", "seller_sku": "SKU-UK", "quantity_ordered": "1"},
            {"amazon_order_id": "171-1388771-2409132", "asin": "B072K2PG11", "seller_sku": "GH-XAAE-HRU7", "quantity_ordered": "1"},
        ],
    )
    _write_csv_rows(
        root / "out" / "financial_events_level1.csv",
        ["Date", "Order ID", "marketplace_id", "SKU"],
        [
            {"Date": "2026-05-26T10:00:00Z", "Order ID": "205-1111111-1111111", "marketplace_id": "A1F83G8C2ARO7P", "SKU": "SKU-UK"},
            {"Date": "2026-05-23T11:59:20Z", "Order ID": "171-1388771-2409132", "marketplace_id": "A2VIGQ35RCS4UG", "SKU": "GH-XAAE-HRU7"},
        ],
    )
    _write_csv_rows(
        root / "out" / "order_master.csv",
        ["Date", "Order ID", "SKU", "country_code", "currency_code"],
        [
            {"Date": "2026-05-26T10:00:00Z", "Order ID": "205-1111111-1111111", "SKU": "SKU-UK", "country_code": "GB", "currency_code": "GBP"},
            {"Date": "2026-05-23T11:59:20Z", "Order ID": "171-1388771-2409132", "SKU": "GH-XAAE-HRU7", "country_code": "AE", "currency_code": "AED"},
        ],
    )
    _write_csv_rows(root / "out" / "financial_events_level3_official.csv", ["Order ID", "SKU", "FBA_Fee_ExVAT"], [])
    _write_csv_rows(root / "out" / "financial_events_refunds.csv", ["order_id", "sku", "amount"], [])
    (root / "out" / "orders_last_updated.txt").write_text("2026-05-27T10:00:00Z", encoding="utf-8")
    _write_csv_rows(
        root / "out" / "systems" / "M" / "sellerboard_bridge" / ORDER_RECONCILIATION_NAME,
        ORDER_RECONCILIATION_COLUMNS,
        [
            {
                "amazon_order_id": "205-1111111-1111111",
                "sellerboard_status": "Shipped",
                "sellerboard_purchase_utc": "2026-05-26T10:00:00Z",
                "sellerboard_sales_channel": "Amazon.co.uk",
                "sellerboard_asin": "B000000001",
                "mapped_sku": "SKU-UK",
                "local_marketplace_id": "A1F83G8C2ARO7P",
                "match_status": "matched",
                "proof_label": "API proved",
            },
            {
                "amazon_order_id": "171-1388771-2409132",
                "sellerboard_status": "Shipped",
                "sellerboard_purchase_utc": "2026-05-23T11:59:20Z",
                "sellerboard_sales_channel": "Amazon.ae",
                "sellerboard_asin": "B072K2PG11",
                "mapped_sku": "GH-XAAE-HRU7",
                "local_marketplace_id": "A2VIGQ35RCS4UG",
                "match_status": "matched",
                "proof_label": "API proved",
            },
        ],
    )
    _write_csv_rows(
        root / "out" / "systems" / "B" / "order_cursors" / "b_marketplace_order_cursors.csv",
        ["marketplace_id", "last_success_utc", "cursor_utc", "status"],
        [
            {"marketplace_id": "A1F83G8C2ARO7P", "last_success_utc": "2026-05-26T09:45:00Z", "cursor_utc": "2026-05-26T09:45:00Z", "status": "ok"},
            {"marketplace_id": "A2VIGQ35RCS4UG", "last_success_utc": "2026-05-26T09:45:00Z", "cursor_utc": "2026-05-26T09:45:00Z", "status": "ok"},
        ],
    )
    _write_csv_rows(
        root / "out" / "systems" / "B" / "refunds" / "b_refund_return_token_bridge.csv",
        [
            "order_id",
            "sku",
            "api_refund_proof_state",
            "amazon_return_proof_state",
            "token_return_state",
            "return_cogs_recovered_exvat",
            "blocked_return_cogs_exvat",
            "sellerboard_match_state",
            "proof_label",
            "roi_stock_recovery_state",
            "mismatch_state",
        ],
        [],
    )
    _write_csv_rows(
        root / "out" / "systems" / "B" / "refunds" / "b_return_cogs_residual_review.csv",
        [
            "order_id",
            "sku",
            "amazon_return_disposition",
            "token_return_state",
            "recovered_cogs_allowed_exvat",
            "blocked_return_cogs_exvat",
            "residual_review_state",
            "manager_expectation",
            "mot_proof_check",
            "bounded_worker_task",
            "retest_rule",
            "preview_live_write_allowed",
            "roi_or_restock_use_allowed",
            "sellerboard_final_truth_allowed",
            "protected_before_apply",
        ],
        [],
    )
    _write_csv_rows(
        root / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            "order_id",
            "sku",
            "proof_label",
            "diagnosis",
            "repair_lane",
            "repair_readiness",
            "preview_action",
            "preview_live_write_allowed",
            "protected_before_apply",
            "sellerboard_final_truth_allowed",
            "roi_or_restock_use_allowed",
            "bounded_worker_task",
            "retest_rule",
            "protected_stop_rule",
        ],
        [],
    )
    _write_csv_rows(
        root / "out" / "systems" / "B" / "refunds" / "b_refund_token_reproof_preview.csv",
        [
            "order_id",
            "sku",
            "source_repair_lane",
            "reproof_lane",
            "reproof_readiness",
            "preview_action",
            "preview_live_write_allowed",
            "protected_before_apply",
            "roi_or_restock_use_allowed",
            "sellerboard_final_truth_allowed",
            "bounded_worker_task",
            "retest_rule",
            "protected_stop_rule",
        ],
        [],
    )
    _write_csv_rows(
        root / "out" / "systems" / "B" / "refunds" / "b_original_return_status_conflict_preview.csv",
        [
            "order_id",
            "sku",
            "unsafe_original_token_id",
            "unsafe_original_status",
            "reusable_return_token_ids",
            "has_reusable_duplicate_token",
            "review_lane",
            "review_readiness",
            "preview_action",
            "preview_live_write_allowed",
            "protected_before_apply",
            "roi_or_restock_use_allowed",
            "sellerboard_final_truth_allowed",
            "bounded_worker_task",
            "retest_rule",
            "protected_stop_rule",
        ],
        [],
    )
    _write_csv_rows(
        root / "out" / "systems" / "B" / "refunds" / "b_original_return_status_apply_preview.csv",
        [
            "order_id",
            "sku",
            "unsafe_original_token_id",
            "current_status",
            "target_status",
            "target_status_source",
            "apply_preview_lane",
            "apply_preview_readiness",
            "block_reason",
            "maintenance_required_before_apply",
            "requires_luke_live_apply",
            "preview_live_write_allowed",
            "protected_before_apply",
            "roi_or_restock_use_allowed",
            "sellerboard_final_truth_allowed",
            "bounded_worker_task",
            "retest_rule",
            "protected_stop_rule",
        ],
        [],
    )
    _write_csv_rows(
        root / "out" / "systems" / "B" / "refunds" / "b_disposition_conflict_preview.csv",
        [
            "order_id",
            "sku",
            "amazon_return_disposition",
            "unsafe_original_token_ids",
            "reusable_return_token_ids",
            "reusable_return_token_allocated_order_ids",
            "return_cogs_token_ids",
            "conflict_lane",
            "review_readiness",
            "preview_action",
            "preview_live_write_allowed",
            "protected_before_apply",
            "roi_or_restock_use_allowed",
            "sellerboard_final_truth_allowed",
            "bounded_worker_task",
            "retest_rule",
            "protected_stop_rule",
        ],
        [],
    )
    _write_csv_rows(
        root / "out" / "systems" / "B" / "refunds" / "b_disposition_conflict_decision_preview.csv",
        [
            "order_id",
            "sku",
            "decision_lane",
            "recommended_manager_position",
            "correction_option",
            "exception_option",
            "impact_summary",
            "protected_decision_required",
            "preview_live_write_allowed",
            "protected_before_apply",
            "roi_or_restock_use_allowed",
            "sellerboard_final_truth_allowed",
            "bounded_worker_task",
            "retest_rule",
            "protected_stop_rule",
        ],
        [],
    )
    _write_csv_rows(
        root / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_impact_preview.csv",
        [
            "return_order_id",
            "sku",
            "amazon_return_disposition",
            "reusable_return_token_ids",
            "reusable_token_statuses",
            "downstream_allocated_order_ids",
            "downstream_order_statuses",
            "downstream_order_header_seen_rows",
            "downstream_order_item_match_rows",
            "return_cogs_rows",
            "correction_impact_lane",
            "correction_preview_action",
            "correction_blocker",
            "future_apply_scope",
            "protected_decision_required",
            "would_touch_live_outputs",
            "preview_live_write_allowed",
            "protected_before_apply",
            "roi_or_restock_use_allowed",
            "sellerboard_final_truth_allowed",
            "bounded_worker_task",
            "retest_rule",
            "protected_stop_rule",
        ],
        [],
    )
    _write_csv_rows(
        root / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_apply_preview.csv",
        [
            "return_order_id",
            "sku",
            "amazon_return_disposition",
            "reused_token_id",
            "downstream_order_id",
            "downstream_order_status",
            "downstream_order_date",
            "reused_token_allocation_rows",
            "reused_token_cogs_rows",
            "replacement_candidate_token_id",
            "replacement_candidate_date_relation",
            "replacement_candidate_days_after_order",
            "replacement_date_validation_reason",
            "replacement_available_token_count",
            "replacement_before_order_count",
            "replacement_unknown_date_count",
            "correction_apply_lane",
            "correction_preview_action",
            "protected_decision_required",
            "requires_luke_live_apply",
            "preview_live_write_allowed",
            "protected_before_apply",
            "roi_or_restock_use_allowed",
            "sellerboard_final_truth_allowed",
            "bounded_worker_task",
            "retest_rule",
            "protected_stop_rule",
        ],
        [],
    )
    _write_csv_rows(
        root / "out" / "systems" / "B" / "refunds" / "b_historical_replacement_stock_proof.csv",
        _historical_replacement_stock_proof_columns(),
        [],
    )
    _write_csv_rows(
        root / "out" / "systems" / "B" / "refunds" / "b_no_replacement_shortage_exception_review.csv",
        _no_replacement_shortage_exception_review_columns(),
        [],
    )
    _write_csv_rows(
        root / "out" / "systems" / "B" / "refunds" / "b_refund_fee_shipping_gap_review.csv",
        _refund_fee_shipping_gap_review_columns(),
        [],
    )
    _write_csv_rows(
        root / "out" / "systems" / "B" / "refunds" / "b_fallback_token_cost_audit.csv",
        [
            "token_id",
            "seller_sku",
            "cost_per_unit",
            "cost_proof_state",
            "manager_label",
            "manager_expectation",
            "bounded_worker_task",
            "retest_rule",
            "preview_live_write_allowed",
            "roi_or_restock_use_allowed",
            "protected_before_apply",
        ],
        [],
    )
    _write_csv_rows(
        root / "out" / "systems" / "B" / "refunds" / "b_fallback_token_cost_audit_summary.csv",
        ["metric", "value"],
        [
            {"metric": "fallback_token_rows", "value": "0"},
            {"metric": "receipt_proved_rows", "value": "0"},
            {"metric": "source_token_proved_rows", "value": "0"},
            {"metric": "weak_or_unproved_rows", "value": "0"},
        ],
    )
    _write_csv_rows(
        root / "out" / "systems" / "B" / "refunds" / "b_fallback_cost_proof_reconciliation.csv",
        [
            "token_id",
            "seller_sku",
            "b070_cost_proof_state",
            "sheet_issue",
            "reconciliation_rule",
            "clean_h_o_trust_allowed",
            "manager_expectation",
            "bounded_worker_task",
            "retest_rule",
            "preview_live_write_allowed",
            "roi_or_restock_use_allowed",
            "protected_before_apply",
        ],
        [],
    )
    _write_csv_rows(
        root / "out" / "systems" / "B" / "refunds" / "b_fallback_cost_proof_reconciliation_summary.csv",
        ["metric", "value"],
        [
            {"metric": "reconciliation_rows", "value": "0"},
            {"metric": "source_token_cost_is_valid_rows", "value": "0"},
            {"metric": "requires_batch_link_proof_rows", "value": "0"},
            {"metric": "h_next_available_blocked_skus", "value": ""},
        ],
    )
    _write_csv_rows(
        root / "out" / "systems" / "B" / "refunds" / "b_refund_fee_shipping_gap_review_summary.csv",
        ["metric", "value"],
        [{"metric": "bridge_values_safe_for_live_roi", "value": "1"}],
    )
    _write_csv_rows(
        root / "out" / "systems" / "B" / "refunds" / "b_level3_fee_shipping_api_proof_map.csv",
        _level3_fee_shipping_api_proof_map_columns(),
        [],
    )
    _write_csv_rows(
        root / "out" / "systems" / "B" / "refunds" / "b_level3_fee_shipping_api_proof_map_summary.csv",
        ["metric", "value"],
        [
            {"metric": "level3_raw_rows", "value": "0"},
            {"metric": "level3_official_rows", "value": "0"},
        ],
    )
    _write_b_refund_fee_shipping_gap_review(root, safe_for_live_roi=True)
    for path in [
        root / "out" / "orders_all.csv",
        root / "out" / "order_items_all.csv",
        root / "out" / "order_master.csv",
        root / "out" / "systems" / "M" / "sellerboard_bridge" / ORDER_RECONCILIATION_NAME,
        root / "out" / "systems" / "B" / "order_cursors" / "b_marketplace_order_cursors.csv",
        root / "out" / "systems" / "B" / "refunds" / "b_refund_return_token_bridge.csv",
        root / "out" / "systems" / "B" / "refunds" / "b_return_cogs_residual_review.csv",
        root / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        root / "out" / "systems" / "B" / "refunds" / "b_refund_token_reproof_preview.csv",
        root / "out" / "systems" / "B" / "refunds" / "b_original_return_status_conflict_preview.csv",
        root / "out" / "systems" / "B" / "refunds" / "b_original_return_status_apply_preview.csv",
        root / "out" / "systems" / "B" / "refunds" / "b_disposition_conflict_preview.csv",
        root / "out" / "systems" / "B" / "refunds" / "b_disposition_conflict_decision_preview.csv",
        root / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_impact_preview.csv",
        root / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_apply_preview.csv",
        root / "out" / "systems" / "B" / "refunds" / "b_historical_replacement_stock_proof.csv",
        root / "out" / "systems" / "B" / "refunds" / "b_no_replacement_shortage_exception_review.csv",
        root / "out" / "systems" / "B" / "refunds" / "b_fallback_token_cost_audit.csv",
        root / "out" / "systems" / "B" / "refunds" / "b_fallback_token_cost_audit_summary.csv",
        root / "out" / "systems" / "B" / "refunds" / "b_fallback_cost_proof_reconciliation.csv",
        root / "out" / "systems" / "B" / "refunds" / "b_fallback_cost_proof_reconciliation_summary.csv",
        root / "out" / "systems" / "B" / "refunds" / "b_refund_fee_shipping_gap_review.csv",
        root / "out" / "systems" / "B" / "refunds" / "b_refund_fee_shipping_gap_review_summary.csv",
        root / "out" / "systems" / "B" / "refunds" / "b_level3_fee_shipping_api_proof_map.csv",
        root / "out" / "systems" / "B" / "refunds" / "b_level3_fee_shipping_api_proof_map_summary.csv",
    ]:
        _set_age(path, 0.25)


def _write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_b_email_intake(root: Path) -> None:
    filename = "DRJ_Hardware_OrderList_20_05_2026-26_05_2026.csv"
    proof_path = root / SOURCE_PROOF_REL_PATH
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text(
        json.dumps(
            {
                "observed_utc": OBSERVED,
                "source_mailbox": "admin@drjselect.co.uk",
                "gmail_label": "Sellerboard",
                "latest_message_seen": True,
                "latest_attachment_filename": filename,
                "proof_status": "ok",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    path = root / "out" / "systems" / "M" / "sellerboard_bridge" / "inbox" / filename
    _write_csv_rows(path, SELLERBOARD_REQUIRED_COLUMNS, [{column: "1" for column in SELLERBOARD_REQUIRED_COLUMNS}])
    _set_age(path, 0.25)


def _columns(name: str) -> list[str]:
    return list(next(item for item in E_CORE_OUTPUTS if item["name"] == name)["columns"])


def _write_e_required_outputs(root: Path, *, stale_name: str | None = None, bad_schema_name: str | None = None) -> None:
    output_rows = {
        "sales_velocity": [
            {"sku": "SKU1", "window_days": "30", "units_sold": "2", "velocity_units_per_day": "0.1", "asof_date": "2026-05-26"},
            {"sku": "SKU2", "window_days": "30", "units_sold": "0", "velocity_units_per_day": "0", "asof_date": "2026-05-26"},
        ],
        "roi_snapshot": [
            {"sku": "SKU1", "window_days": "30", "units_sold": "2", "revenue_exvat_gbp": "20", "cogs_exvat_gbp": "10", "profit_exvat_gbp": "10", "roi_exvat": "1", "asof_date": "2026-05-26"},
        ],
        "roi_snapshot_by_country": [
            {"sku": "SKU1", "window_days": "30", "country_code": "UK", "units_sold": "2", "revenue_exvat_gbp": "20", "cogs_exvat_gbp": "10", "profit_exvat_gbp": "10", "roi_exvat": "1", "asof_date": "2026-05-26"},
        ],
        "restock_signals": [
            {"sku": "SKU1", "velocity_30d": "0.1", "available": "5", "total_quantity": "5", "days_of_stock_left": "50", "reorder_flag": "0", "suggested_reorder_qty": "0", "asof_date": "2026-05-26"},
            {"sku": "SKU2", "velocity_30d": "0", "available": "3", "total_quantity": "3", "days_of_stock_left": "", "reorder_flag": "0", "suggested_reorder_qty": "0", "asof_date": "2026-05-26"},
        ],
        "performance_summary": [
            {"sku": "SKU1", "window_days": "30", "units_sold": "2", "velocity_units_per_day": "0.1", "revenue_exvat_gbp": "20", "profit_exvat_gbp": "10", "roi_exvat": "1", "days_of_stock_left": "50", "reorder_flag": "0", "units_sold_roi": "2", "units_sold_truth_30d": "2", "units_sold_velocity_30d": "2", "units_sold_source": "roi", "value_velocity_gbp_per_day": "1", "profit_confidence": "profit_clean", "sales_truth_state": "roi_sales_truth", "stock_signal": "no", "restock_business_ready": "no", "latest_price_confidence": "listing_price_current", "refund_proof_state": "api_proved_or_not_applicable", "refund_sample_confidence": "enough_sales", "b_money_confidence_state": "api_backed_safe", "b_bridge_values_safe_for_live_roi": "1", "restock_decision_state": "not_applicable_no_stock_signal", "restock_readiness_confidence": "not_applicable", "restock_missing_proof": "no_stock_signal", "restock_evidence_role": "evidence_only_not_buy_instruction", "missing_reason": "", "missing_roi_reason": "roi_clean", "missing_roi_reason_detail": ""},
            {"sku": "SKU2", "window_days": "30", "units_sold": "0", "velocity_units_per_day": "0", "revenue_exvat_gbp": "0", "profit_exvat_gbp": "0", "roi_exvat": "", "days_of_stock_left": "", "reorder_flag": "0", "units_sold_roi": "", "units_sold_truth_30d": "0", "units_sold_velocity_30d": "0", "units_sold_source": "velocity", "value_velocity_gbp_per_day": "0", "profit_confidence": "profit_missing", "sales_truth_state": "velocity_only", "stock_signal": "no", "restock_business_ready": "no", "latest_price_confidence": "listing_price_current", "refund_proof_state": "api_proved_or_not_applicable", "refund_sample_confidence": "enough_sales", "b_money_confidence_state": "api_backed_safe", "b_bridge_values_safe_for_live_roi": "1", "restock_decision_state": "not_applicable_no_stock_signal", "restock_readiness_confidence": "not_applicable", "restock_missing_proof": "no_stock_signal;missing_roi;stock_only_no_sales_window", "restock_evidence_role": "evidence_only_not_buy_instruction", "missing_reason": "stock_only_no_sales_window", "missing_roi_reason": "stock_only_no_sales_window", "missing_roi_reason_detail": "stock_only_no_sales_window"},
        ],
        "study_report": [
            {"study_rank": "1", "sku": "SKU1", "asof_date": "2026-05-26", "reorder_flag": "0", "days_of_stock_left": "50", "suggested_reorder_qty": "0", "velocity_30d": "0.1", "units_sold_30d": "2", "units_sold_truth_30d": "2", "revenue_exvat_gbp_30d": "20", "profit_exvat_gbp_30d": "10", "roi_exvat_30d": "1", "latest_daily_truth_state": "finalized", "profit_confidence": "profit_clean", "sales_truth_state": "roi_sales_truth", "stock_signal": "no", "restock_business_ready": "no", "latest_price_confidence": "listing_price_current", "b_money_confidence_state": "api_backed_safe", "b_bridge_values_safe_for_live_roi": "1", "restock_decision_state": "not_applicable_no_stock_signal", "restock_readiness_confidence": "not_applicable", "restock_missing_proof": "no_stock_signal", "restock_evidence_role": "evidence_only_not_buy_instruction", "missing_reason": "", "missing_roi_reason": "roi_clean", "missing_roi_reason_detail": ""},
            {"study_rank": "2", "sku": "SKU2", "asof_date": "2026-05-26", "reorder_flag": "0", "days_of_stock_left": "", "suggested_reorder_qty": "0", "velocity_30d": "0", "units_sold_30d": "0", "units_sold_truth_30d": "0", "revenue_exvat_gbp_30d": "0", "profit_exvat_gbp_30d": "0", "roi_exvat_30d": "", "latest_daily_truth_state": "no_sales", "profit_confidence": "profit_missing", "sales_truth_state": "velocity_only", "stock_signal": "no", "restock_business_ready": "no", "latest_price_confidence": "listing_price_current", "b_money_confidence_state": "api_backed_safe", "b_bridge_values_safe_for_live_roi": "1", "restock_decision_state": "not_applicable_no_stock_signal", "restock_readiness_confidence": "not_applicable", "restock_missing_proof": "no_stock_signal;missing_roi;stock_only_no_sales_window", "restock_evidence_role": "evidence_only_not_buy_instruction", "missing_reason": "stock_only_no_sales_window", "missing_roi_reason": "stock_only_no_sales_window", "missing_roi_reason_detail": "stock_only_no_sales_window"},
        ],
        "sales_truth_sku_30d": [
            {"sku": "SKU1", "window_days": "30", "asof_date": "2026-05-26", "units_b_source": "2", "revenue_b_source_gbp": "20", "profit_b_source_gbp": "10"},
        ],
        "sales_truth_reconciliation": [
            {"sku": "SKU1", "window_days": "30", "asof_date": "2026-05-26", "units_b_source": "2", "revenue_b_source_gbp": "20", "profit_b_source_gbp": "10", "units_e_output": "2", "revenue_e_output_gbp": "20", "profit_e_output_gbp": "10", "units_delta": "0", "revenue_delta_gbp": "0", "profit_delta_gbp": "0", "confidence_status": "ok", "root_cause_hint": ""},
        ],
        "sku_daily_sales_truth": [
            {"sku": "SKU1", "date": "2026-05-26", "source_state": "finalized", "units": "2", "revenue_gbp": "20", "profit_gbp": "10", "confidence_status": "ok"},
        ],
    }
    for item in E_CORE_OUTPUTS:
        name = str(item["name"])
        columns = _columns(name)
        if name in {"performance_summary", "study_report"}:
            columns = columns + [
                column for column in [
                "profit_confidence",
                "sales_truth_state",
                "stock_signal",
                "restock_business_ready",
                "latest_price_confidence",
                "refund_proof_state",
                "refund_sample_confidence",
                "b_money_confidence_state",
                "b_bridge_values_safe_for_live_roi",
                "restock_decision_state",
                "restock_readiness_confidence",
                "restock_missing_proof",
                "restock_evidence_role",
                "missing_reason",
                "missing_roi_reason",
                "missing_roi_reason_detail",
                ] if column not in columns
            ]
        if name == bad_schema_name:
            columns = [column for column in columns if column != "sku"]
        path = root / str(item["path"])
        _write_csv_rows(path, columns, output_rows[name])
        _set_age(path, 40.0 if name == stale_name else 0.25)


def _write_e_input_proofs(root: Path, *, stale_name: str | None = None) -> None:
    for item in E_INPUT_PROOFS:
        path = root / str(item["path"])
        _write_csv(path, rows=max(int(item.get("min_rows", 1) or 0), 1))
        stale_hours = float(item.get("fail_hours", 12.0)) + 1.0
        _set_age(path, stale_hours if item["name"] == stale_name else 0.25)


def _write_e_coverage_summary(root: Path) -> None:
    _write_csv_rows(
        root / "out" / "e_coverage_summary.csv",
        [
            "asof_date",
            "total_skus",
            "skus_with_velocity",
            "skus_with_roi",
            "skus_with_finalized_daily_truth",
            "skus_with_provisional_daily_truth",
            "skus_with_restock_flags",
            "skus_with_stock_signal",
            "skus_missing_profit_proof",
            "velocity_only_skus",
            "restock_business_ready_skus",
            "restock_flagged_missing_roi_skus",
            "blank_latest_daily_truth_state_rows",
            "missing_roi_reason_roi_clean_skus",
            "missing_roi_reason_velocity_only_sales_truth_skus",
            "missing_roi_reason_stock_only_no_sales_window_skus",
            "missing_roi_reason_no_recent_sales_truth_skus",
            "missing_roi_reason_missing_cogs_or_fx_skus",
            "missing_roi_reason_missing_fee_proof_skus",
            "missing_roi_reason_missing_refund_proof_skus",
            "missing_roi_reason_missing_current_price_proof_skus",
            "missing_roi_reason_b_money_bridge_labelled_skus",
            "missing_roi_reason_not_available_skus",
            "restock_decision_state_business_ready_clean_skus",
            "restock_decision_state_stock_signal_only_skus",
            "restock_decision_state_blocked_missing_roi_skus",
            "restock_decision_state_blocked_missing_profit_inputs_skus",
            "restock_decision_state_warning_bridge_labelled_money_skus",
            "restock_decision_state_blocked_weak_refund_proof_skus",
            "restock_decision_state_blocked_missing_current_price_skus",
            "restock_decision_state_not_applicable_no_stock_signal_skus",
            "restock_blocked_missing_roi_skus",
            "restock_blocked_weak_refund_proof_skus",
            "restock_blocked_missing_current_price_skus",
            "restock_warning_bridge_labelled_money_skus",
        ],
        [
            {
                "asof_date": "2026-05-26",
                "total_skus": "2",
                "skus_with_velocity": "2",
                "skus_with_roi": "1",
                "skus_with_finalized_daily_truth": "1",
                "skus_with_provisional_daily_truth": "0",
                "skus_with_restock_flags": "0",
                "skus_with_stock_signal": "0",
                "skus_missing_profit_proof": "1",
                "velocity_only_skus": "1",
                "restock_business_ready_skus": "0",
                "restock_flagged_missing_roi_skus": "0",
                "blank_latest_daily_truth_state_rows": "0",
                "missing_roi_reason_roi_clean_skus": "1",
                "missing_roi_reason_velocity_only_sales_truth_skus": "0",
                "missing_roi_reason_stock_only_no_sales_window_skus": "1",
                "missing_roi_reason_no_recent_sales_truth_skus": "0",
                "missing_roi_reason_missing_cogs_or_fx_skus": "0",
                "missing_roi_reason_missing_fee_proof_skus": "0",
                "missing_roi_reason_missing_refund_proof_skus": "0",
                "missing_roi_reason_missing_current_price_proof_skus": "0",
                "missing_roi_reason_b_money_bridge_labelled_skus": "0",
                "missing_roi_reason_not_available_skus": "0",
                "restock_decision_state_business_ready_clean_skus": "0",
                "restock_decision_state_stock_signal_only_skus": "0",
                "restock_decision_state_blocked_missing_roi_skus": "0",
                "restock_decision_state_blocked_missing_profit_inputs_skus": "0",
                "restock_decision_state_warning_bridge_labelled_money_skus": "0",
                "restock_decision_state_blocked_weak_refund_proof_skus": "0",
                "restock_decision_state_blocked_missing_current_price_skus": "0",
                "restock_decision_state_not_applicable_no_stock_signal_skus": "2",
                "restock_blocked_missing_roi_skus": "1",
                "restock_blocked_weak_refund_proof_skus": "0",
                "restock_blocked_missing_current_price_skus": "0",
                "restock_warning_bridge_labelled_money_skus": "0",
            }
        ],
    )


def _write_e_health(root: Path, *, status: str = "ok") -> None:
    _write_csv_rows(
        root / "out" / "cycle_alerts" / "checklist_E_split.csv",
        ["check", "status", "value", "notes"],
        [{"check": "e_schema_sales_velocity", "status": status, "value": "ok", "notes": ""}],
    )
    _set_age(root / "out" / "cycle_alerts" / "checklist_E_split.csv", 0.20)


def _write_lock(path: Path, *, label: str, heartbeat_age_minutes: float = 1.0, pid: int | None = None) -> None:
    heartbeat = (_dt(OBSERVED) - timedelta(minutes=heartbeat_age_minutes)).isoformat().replace("+00:00", "Z")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"{label}|pid={pid or os.getpid()}|start=2026-05-26T08:00:00Z|heartbeat={heartbeat}\n",
        encoding="utf-8",
    )


def _write_b_locks(root: Path, *, worker_heartbeat_age_minutes: float = 1.0, duplicate: bool = False) -> None:
    _write_lock(
        root / "out" / "systems" / "B" / "live" / "B_cycle.lock",
        label="B",
        heartbeat_age_minutes=worker_heartbeat_age_minutes,
    )
    _write_lock(
        root / "out" / "systems" / "B" / "live" / "B_supervisor.lock",
        label="B_SUPERVISOR",
        heartbeat_age_minutes=1.0,
    )
    if duplicate:
        _write_lock(root / "out" / "B_cycle.lock", label="B", heartbeat_age_minutes=1.0)


def _write_sql_tables(root: Path) -> None:
    db_path = root / "out" / "sql" / "sellerone_dev.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    try:
        for _check, table in A_SQL_TABLES:
            con.execute(f'CREATE TABLE "{table}" (id TEXT)')
            con.execute(f'INSERT INTO "{table}" VALUES ("1")')
        con.commit()
    finally:
        con.close()


def _write_optional_sql_tables(root: Path) -> None:
    db_path = root / "out" / "sql" / "sellerone_dev.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    try:
        for _check, table in A_PROOF_ONLY_SQL_TABLES:
            con.execute(f'CREATE TABLE "{table}" (id TEXT)')
            con.execute(f'INSERT INTO "{table}" VALUES ("1")')
        con.commit()
    finally:
        con.close()


def _write_floor_table(root: Path, *, age_hours: float = 1.0, rows: int = 1) -> None:
    path = root / "out" / "phase1_floor_table_latest.csv"
    _write_csv(path, rows=rows)
    _set_age(path, age_hours)


def _write_handoff_proof(
    root: Path,
    *,
    final_run_id: str = "A_test",
    proof_status: str = "ok",
    final_state: str | None = None,
    final_exit_code: int | None = None,
    include_handoff_evidence: bool = False,
) -> None:
    path = root / "out" / "systems" / "A" / "live" / "a_maintenance_handoff_latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "proof_status": proof_status,
                "request_id": "REQ_A",
                "handoff_mode": "b_ready",
                "final_run_id": final_run_id,
                "final_state": final_state or ("completed" if proof_status == "ok" else "failed"),
                "final_exit_code": final_exit_code if final_exit_code is not None else (0 if proof_status == "ok" else 3),
                "cleanup_evidence": {"all_clear": True},
                **(
                    {
                        "b_ready_evidence": {"exists": True},
                        "a_active_evidence": {"exists": True},
                    }
                    if include_handoff_evidence
                    else {}
                ),
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _observed_minus(hours: float = 0.0, minutes: float = 0.0) -> str:
    return (_dt(OBSERVED) - timedelta(hours=hours, minutes=minutes)).isoformat().replace("+00:00", "Z")


def _write_f_outputs(
    root: Path,
    *,
    parked_decision: bool = False,
    stale_child: bool = False,
    live_owner_state: str = "running",
    live_owner_notes: str = "f061_subprocess_completed",
    supervisor_state: str = "ok",
    supervisor_progress_state: str = "scanner_progressing",
    supervisor_scanner_progress_age_seconds: str = "60",
    email_source_state: str = "ready",
    email_batch_imported: bool = True,
    email_batch_age_hours: float = 2.0,
    missing_email_source: bool = False,
    url_source_state: str = "download_ready",
    missing_url_source: bool = False,
    missing_gmail_oauth: bool = False,
    rescan_policy_cooldown: bool = False,
    parked_rescan_timeout: bool = False,
    live_active_supplier_id: str = "td_synnex",
    live_active_f061_run_id: str = "fpm_td_synnex_test",
) -> None:
    manager_dir = root / "out" / "systems" / "M"
    live_dir = root / "out" / "systems" / "F" / "price_list_manager" / "live"
    test_dir = root / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    f_live_dir = root / "out" / "systems" / "F" / "live"

    _write_csv_rows(
        manager_dir / "f_price_list_manager_snapshot.csv",
        [
            "observed_utc",
            "flow",
            "module_id",
            "status",
            "queue_supplier_id",
            "queue_supplier_name",
            "queue_state",
            "queue_position",
            "queue_web_unprocessed",
            "live_state",
            "live_last_action",
            "live_last_action_status",
            "live_pending_rows",
            "live_active_supplier_id",
            "active_blocker_code",
            "active_blocker_summary",
            "needs_user",
            "user_action",
            "safe_to_do_nothing",
            "stale_evidence",
            "evidence_paths",
            "notes",
        ],
        [
            {
                "observed_utc": OBSERVED,
                "flow": "F",
                "module_id": "F_price_list_manager",
                "status": "ok",
                "queue_supplier_id": "clf",
                "queue_supplier_name": "CLF",
                "queue_state": "Recommended",
                "queue_position": "1",
                "queue_web_unprocessed": "10",
                "live_state": "running",
                "live_last_action": "resume_f061_active_run",
                "live_last_action_status": "success",
                "live_pending_rows": "20",
                "live_active_supplier_id": live_active_supplier_id,
                "needs_user": "0",
                "user_action": "No user action.",
                "safe_to_do_nothing": "1",
                "stale_evidence": "0",
                "notes": "live_owner_state_clear",
            }
        ],
    )
    _set_age(manager_dir / "f_price_list_manager_snapshot.csv", 0.25)

    _write_csv_rows(
        live_dir / "live_cycle_status.csv",
        ["observed_utc", "run_id", "owner_pid", "state", "active_supplier_id", "active_f061_run_id", "pending_rows", "last_action", "last_action_status", "chunk_rows", "drain_ready", "notes"],
        [
            {
                "observed_utc": OBSERVED,
                "run_id": "fpm_live_test",
                "owner_pid": "123",
                "state": live_owner_state,
                "active_supplier_id": live_active_supplier_id,
                "active_f061_run_id": live_active_f061_run_id,
                "pending_rows": "20",
                "last_action": "source_shape_guard" if live_owner_state.startswith("blocked_") else "resume_f061_active_run",
                "last_action_status": "blocked" if live_owner_state.startswith("blocked_") else "success",
                "chunk_rows": "25",
                "drain_ready": "0",
                "notes": live_owner_notes,
            }
        ],
    )
    _set_age(live_dir / "live_cycle_status.csv", 0.25)
    (live_dir / "fpm_live_supervisor_state.txt").parent.mkdir(parents=True, exist_ok=True)
    (live_dir / "fpm_live_supervisor_state.txt").write_text(
        f"state={supervisor_state}|reason=test|manager_pids=123|child_pids=456|"
        f"progress_state={supervisor_progress_state}|"
        f"scanner_progress_age_seconds={supervisor_scanner_progress_age_seconds}|updated_utc={OBSERVED}\n",
        encoding="utf-8",
    )
    child_heartbeat = _observed_minus(minutes=40 if stale_child else 5)
    (live_dir / "f061_child_status.txt").write_text(
        f"pid=456|supplier_id={live_active_supplier_id}|heartbeat={child_heartbeat}|last_output_utc={child_heartbeat}\n",
        encoding="utf-8",
    )
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        f"state=hidden|browser_state=HIDDEN|auth_state=LOGGED_IN|updated_utc={OBSERVED}\n",
        encoding="utf-8",
    )
    (live_dir / "f061_login_mode.requested").write_text(
        f"requested_utc={_observed_minus(hours=1)}\nstatus=drained\nlast_observed_utc={OBSERVED}\n",
        encoding="utf-8",
    )
    _write_csv_rows(
        live_dir / "seller_central_login_recovery_proof.csv",
        [
            "observed_utc",
            "context",
            "status",
            "reason",
            "seller_central_signin_detected",
            "seller_central_otp_detected",
            "requested_utc",
            "message_ts_utc",
            "code_seen_flag",
            "fresh_code_flag",
            "used_message_flag",
            "attempted_flag",
            "succeeded_flag",
            "auto_login_enabled",
            "secret_file_exists",
            "credentials_present",
            "gmail_label",
            "code_age_seconds",
            "source_message_id",
            "notes",
        ],
        [
            {
                "observed_utc": OBSERVED,
                "context": "unit_test",
                "status": "succeeded",
                "reason": "eligibility_signal_visible",
                "seller_central_signin_detected": "1",
                "seller_central_otp_detected": "1",
                "requested_utc": _observed_minus(minutes=1),
                "message_ts_utc": _observed_minus(minutes=1),
                "code_seen_flag": "1",
                "fresh_code_flag": "1",
                "used_message_flag": "0",
                "attempted_flag": "1",
                "succeeded_flag": "1",
                "auto_login_enabled": "1",
                "secret_file_exists": "1",
                "credentials_present": "1",
                "gmail_label": "AmazonOTP",
                "code_age_seconds": "5.00",
                "source_message_id": "msg-1",
                "notes": "redacted_test_proof",
            }
        ],
    )
    _set_age(live_dir / "seller_central_login_recovery_proof.csv", 0.25)
    diagnostics_dir = root / "out" / "systems" / "F" / "diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    (diagnostics_dir / "fpm160_visible_login_launch_status.json").write_text(
        json.dumps({"status": "not_requested", "updated_utc": OBSERVED}) + "\n",
        encoding="utf-8",
    )
    _set_age(diagnostics_dir / "fpm160_visible_login_launch_status.json", 1.0)

    _write_csv_rows(
        live_dir / "storage_drift_report.csv",
        ["observed_utc", "contract_name", "status_before", "row_delta_before", "status_after", "row_delta_after", "notes"],
        [
            {
                "observed_utc": OBSERVED,
                "contract_name": "supplier_price_list_active_run",
                "status_before": "ok",
                "row_delta_before": "0",
                "status_after": "ok",
                "row_delta_after": "0",
                "notes": "sql_aligned_or_newer",
            }
        ],
    )
    _set_age(live_dir / "storage_drift_report.csv", 0.25)

    _write_csv_rows(
        root / "config" / "feeder" / "f_scanner_timeout_policy.csv",
        [
            "fail_code",
            "enabled",
            "timeout_mode",
            "timeout_days",
            "max_timeout_days",
            "cost_change_resets_flag",
            "source_change_resets_flag",
            "manual_review_required_flag",
            "notes",
            "updated_at_utc",
        ],
        [
            {
                "fail_code": "RESCAN",
                "enabled": "1" if rescan_policy_cooldown else "0",
                "timeout_mode": "fixed_days" if rescan_policy_cooldown else "disabled",
                "timeout_days": "30" if rescan_policy_cooldown else "",
                "max_timeout_days": "30" if rescan_policy_cooldown else "0",
                "cost_change_resets_flag": "0",
                "source_change_resets_flag": "0",
                "manual_review_required_flag": "0",
                "notes": "test policy",
                "updated_at_utc": OBSERVED,
            }
        ],
    )
    _write_csv_rows(
        root / "out" / "systems" / "F" / "inbox" / "supplier_price_list_active_run.csv",
        [
            "run_id",
            "supplier_id",
            "supplier_name",
            "row_key",
            "supplier_sku",
            "barcode",
            "supplier_title",
            "unit_cost",
            "currency",
            "vat_rate",
            "scan_status",
            "scan_reason",
            "completion_block_reason",
            "attempt_count",
            "last_attempt_utc",
            "finished_utc",
            "source_seen_at_utc",
        ],
        [
            {
                "run_id": "fpm_td_synnex_test",
                "supplier_id": "td_synnex",
                "supplier_name": "TD Synnex",
                "row_key": "td-1",
                "supplier_sku": "TD-1",
                "barcode": "1234567890123",
                "supplier_title": "Normal Pending Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "completion_block_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": OBSERVED,
            }
        ],
    )
    screening_rows = [
        {
            "observed_utc": OBSERVED,
            "run_id": "fpm_td_synnex_test",
            "supplier_id": "td_synnex",
            "supplier_name": "TD Synnex",
            "supplier_sku": "TD-1",
            "supplier_title": "Normal Pending Product",
            "barcode": "1234567890123",
            "candidate_id": "td-1",
            "asin": "",
            "row_status": "pending",
            "last_stage": "start",
            "fail_code": "",
            "attempt_count": "0",
            "timeout_until_utc": "",
            "mode": "screening",
            "updated_at_utc": OBSERVED,
            "source_seen_at_utc": OBSERVED,
            "pf": "",
            "status_reason": "",
        }
    ]
    if parked_rescan_timeout:
        screening_rows.append(
            {
                "observed_utc": OBSERVED,
                "run_id": "fpm_td_synnex_test",
                "supplier_id": "td_synnex",
                "supplier_name": "TD Synnex",
                "supplier_sku": "TD-RESCAN",
                "supplier_title": "Parked Rescan Product",
                "barcode": "4444444444444",
                "candidate_id": "td-rescan",
                "asin": "",
                "row_status": "timeout",
                "last_stage": "retry",
                "fail_code": "RESCAN",
                "attempt_count": "1",
                "timeout_until_utc": "2026-06-18T10:00:00Z",
                "mode": "screening",
                "updated_at_utc": OBSERVED,
                "source_seen_at_utc": OBSERVED,
                "pf": "RESCAN",
                "status_reason": "RESCAN",
            }
        )
    _write_csv_rows(
        root / "out" / "systems" / "F" / "live" / "f_screening_row_state_live.csv",
        list(screening_rows[0].keys()),
        screening_rows,
    )

    if not missing_gmail_oauth:
        secrets_dir = root / "secrets" / "price_list_manager"
        secrets_dir.mkdir(parents=True, exist_ok=True)
        (secrets_dir / "gmail_token.json").write_text("{}", encoding="utf-8")
        (secrets_dir / "gmail_client_secret.json").write_text("{}", encoding="utf-8")

    abgee_source_file = root / "price_files" / "ABGee" / "Processed" / "ABGee_Stock_Feed.xlsx"
    abgee_source_file.parent.mkdir(parents=True, exist_ok=True)
    abgee_source_file.write_text("source proof", encoding="utf-8")
    _set_age(abgee_source_file, 1.0)
    stax_source_file = root / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "downloaded_sources" / "stax" / "Processed" / "stax.csv"
    stax_source_file.parent.mkdir(parents=True, exist_ok=True)
    stax_source_file.write_text("sku,barcode,cost\nSTAX-1,1234567890123,1.23\n", encoding="utf-8")
    _set_age(stax_source_file, 1.0)

    _write_csv_rows(
        root / "config" / "feeder" / "price_list_manager" / "suppliers.csv",
        [
            "supplier_id",
            "supplier_name",
            "source_type",
            "source_subtype",
            "source_url",
            "source_folder_path",
            "existing_supplier_config_path",
            "converter_id",
            "normal_refresh_days",
            "minimum_rescan_days",
            "large_file_flag",
            "manual_request_required_flag",
            "priority_band",
            "active_flag",
            "notes",
        ],
        [
            {
                "supplier_id": "abgee",
                "supplier_name": "ABGee",
                "source_type": "email_attachment",
                "source_subtype": "daily_email",
                "source_folder_path": str(root / "price_files" / "ABGee" / "inbox"),
                "converter_id": "abgee",
                "active_flag": "1",
            },
            {
                "supplier_id": "td_synnex",
                "supplier_name": "TD Synnex",
                "source_type": "email_attachment",
                "source_subtype": "daily_email",
                "source_folder_path": str(root / "price_files" / "TD Synnex" / "inbox"),
                "converter_id": "td_synnex",
                "active_flag": "0",
            },
            {
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "source_type": "api_pull",
                "source_subtype": "csv_link",
                "source_url": "https://example.test/stax.csv",
                "converter_id": "stax",
                "active_flag": "1",
            },
        ],
    )
    email_source_ready = email_source_state == "ready"
    email_fetch_error = email_source_state == "fetch_error"
    email_source_visible = email_source_ready or email_fetch_error
    source_rows = []
    if not missing_email_source:
        source_rows.append(
            {
                "supplier_id": "abgee",
                "supplier_name": "ABGee",
                "source_type": "email_attachment",
                "source_subtype": "daily_email",
                "source_state": "error" if email_fetch_error else email_source_state,
                "status": "fail" if email_fetch_error else "ok",
                "source_location": "gmail_label:ABGee" if email_source_visible else str(root / "price_files" / "ABGee" / "inbox"),
                "latest_source_path": str(abgee_source_file) if email_source_visible else "",
                "latest_source_name": "ABGee_Stock_Feed.xlsx" if email_source_visible else "",
                "latest_source_mtime_utc": _observed_minus(hours=2) if email_source_visible else "",
                "file_count": "1" if email_source_visible else "0",
                "operator_action": "Investigate Gmail pull" if email_fetch_error else ("Import latest file" if email_source_ready else "Await email file"),
                "checked_at_utc": _observed_minus(hours=2),
                "notes": (
                    "gmail_fetch_error=RuntimeError;label=ABGee"
                    if email_fetch_error
                    else ("gmail_attachment_downloaded;label=ABGee;bytes=551602" if email_source_ready else "gmail_no_matching_attachment;label=ABGee")
                ),
            }
        )
    if not missing_url_source:
        source_rows.append(
            {
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "source_type": "api_pull",
                "source_subtype": "csv_link",
                "source_state": url_source_state,
                "status": "fail" if url_source_state == "error" else "ok",
                "source_location": "https://example.test/stax.csv",
                "latest_source_path": str(stax_source_file) if url_source_state == "ready" else "",
                "latest_source_name": "stax.csv" if url_source_state == "ready" else "",
                "latest_source_mtime_utc": _observed_minus(hours=2) if url_source_state == "ready" else "",
                "file_count": "1" if url_source_state == "ready" else "0",
                "operator_action": "Import latest file" if url_source_state == "ready" else "Auto pull when due",
                "checked_at_utc": _observed_minus(hours=2),
                "notes": "remote_check_skipped" if url_source_state == "download_ready" else "http_status=200;bytes=123",
            }
        )
    _write_csv_rows(
        test_dir / "source_acquisition_status.csv",
        [
            "supplier_id",
            "supplier_name",
            "source_type",
            "source_subtype",
            "source_state",
            "status",
            "source_location",
            "latest_source_path",
            "latest_source_name",
            "latest_source_mtime_utc",
            "file_count",
            "operator_action",
            "checked_at_utc",
            "notes",
        ],
        source_rows,
    )
    _set_age(test_dir / "source_acquisition_status.csv", 0.25)

    _write_csv_rows(
        test_dir / "price_list_batches.csv",
        [
            "batch_id",
            "supplier_id",
            "source_type",
            "source_subtype",
            "source_received_at_utc",
            "source_file_path",
            "source_file_hash",
            "converted_file_path",
            "source_row_count",
            "valid_row_count",
            "held_row_count",
            "new_row_count",
            "changed_row_count",
            "eligible_row_count",
            "skipped_cooldown_row_count",
            "batch_status",
            "status_reason",
            "updated_at_utc",
        ],
        [
            {
                "batch_id": "abgee_test",
                "supplier_id": "abgee",
                "source_type": "email_attachment",
                "source_subtype": "daily_email",
                "source_received_at_utc": _observed_minus(hours=email_batch_age_hours),
                "source_file_path": str(abgee_source_file) if email_batch_imported else "",
                "source_file_hash": "testhash" if email_batch_imported else "",
                "source_row_count": "8745" if email_batch_imported else "0",
                "valid_row_count": "5770" if email_batch_imported else "0",
                "held_row_count": "2975" if email_batch_imported else "0",
                "new_row_count": "5304" if email_batch_imported else "0",
                "eligible_row_count": "5307" if email_batch_imported else "0",
                "skipped_cooldown_row_count": "463" if email_batch_imported else "0",
                "batch_status": "imported_from_source" if email_batch_imported else "pending_source",
                "status_reason": "ready_source_file_imported" if email_batch_imported else "source_not_imported",
                "updated_at_utc": _observed_minus(hours=email_batch_age_hours),
            },
            {
                "batch_id": "stax_test",
                "supplier_id": "stax",
                "source_type": "api_pull",
                "source_subtype": "csv_link",
                "source_received_at_utc": _observed_minus(hours=2),
                "source_file_path": str(stax_source_file),
                "source_file_hash": "staxhash",
                "source_row_count": "27201",
                "valid_row_count": "24231",
                "held_row_count": "2970",
                "new_row_count": "24231",
                "eligible_row_count": "24231",
                "skipped_cooldown_row_count": "0",
                "batch_status": "imported_from_source",
                "status_reason": "ready_source_file_imported",
                "updated_at_utc": _observed_minus(hours=2),
            }
        ],
    )
    _set_age(test_dir / "price_list_batches.csv", 0.25)

    _write_csv_rows(
        test_dir / "queue_controls.csv",
        ["supplier_id", "control_state", "priority_rank", "reason", "updated_at_utc"],
        [
            {
                "supplier_id": "clf",
                "control_state": "prioritised",
                "priority_rank": "1",
                "reason": "test queue proof",
                "updated_at_utc": OBSERVED,
            }
        ],
    )
    _write_csv_rows(
        test_dir / "f061_handoff_approvals.csv",
        ["approval_id", "supplier_id", "batch_id", "approval_state", "approved_by", "approved_at_utc", "expires_at_utc", "reason"],
        [
            {
                "approval_id": "handoff_approval_clf_test",
                "supplier_id": "clf",
                "batch_id": "clf_test",
                "approval_state": "approved",
                "approved_by": "FPM130_live_cycle",
                "approved_at_utc": OBSERVED,
                "reason": "test proof",
            }
        ],
    )
    _write_csv_rows(
        test_dir / "manager_decisions.csv",
        [
            "decision_id",
            "observed_utc",
            "supplier_id",
            "batch_id",
            "decision",
            "decision_reason",
            "f061_owner_status",
            "safe_to_handoff_flag",
            "notes",
        ],
        [
            {
                "decision_id": "decision_clf_test",
                "observed_utc": OBSERVED,
                "supplier_id": "clf",
                "batch_id": "clf_test",
                "decision": "scan_next",
                "decision_reason": "test proof",
                "f061_owner_status": "not_checked_test_mode",
                "safe_to_handoff_flag": "0",
                "notes": "handoff_disabled",
            }
        ],
    )
    _write_csv_rows(
        test_dir / "f061_recovery_progress.csv",
        [
            "imported_at_utc",
            "supplier_id",
            "batch_id",
            "legacy_run_id",
            "legacy_total_rows",
            "legacy_pending_rows",
            "legacy_done_rows",
            "legacy_failed_rows",
            "pending_source_rows",
            "pending_matched_rows",
            "pending_held_rows",
            "pending_unmatched_rows",
            "manager_valid_rows",
            "manager_scan_now_rows",
            "manager_recovery_skipped_rows",
            "manager_held_rows",
            "legacy_active_run_path",
            "legacy_run_state_path",
        ],
        [
            {
                "imported_at_utc": OBSERVED,
                "supplier_id": "entertainment_trading",
                "batch_id": "entertainment_trading_test",
                "legacy_run_id": "legacy_test",
                "legacy_total_rows": "10",
                "legacy_pending_rows": "4",
                "legacy_done_rows": "6",
                "legacy_failed_rows": "0",
                "pending_source_rows": "4",
                "pending_matched_rows": "3",
                "pending_held_rows": "1",
                "pending_unmatched_rows": "0",
                "manager_valid_rows": "9",
                "manager_scan_now_rows": "3",
                "manager_recovery_skipped_rows": "1",
                "manager_held_rows": "1",
            }
        ],
    )
    _set_age(test_dir / "queue_controls.csv", 0.25)
    _set_age(test_dir / "f061_handoff_approvals.csv", 0.25)
    _set_age(test_dir / "manager_decisions.csv", 0.25)
    _set_age(test_dir / "f061_recovery_progress.csv", 0.25)

    _write_csv_rows(
        test_dir / "batch_rows.csv",
        [
            "batch_id",
            "supplier_id",
            "row_key",
            "supplier_sku",
            "supplier_title",
            "barcode",
            "unit_cost",
            "currency",
            "vat_rate",
            "unit_code",
            "pack_size",
            "pack_cost",
            "moq",
            "source_row_hash",
            "row_change_status",
            "scan_eligibility",
            "eligibility_reason",
            "last_memory_key",
            "cooldown_until_utc",
        ],
        [
            {
                "batch_id": "abgee_test",
                "supplier_id": "abgee",
                "row_key": "row_1",
                "supplier_sku": "ABG-1",
                "supplier_title": "ABGee Item 1",
                "barcode": "1234567890123",
                "unit_cost": "1.23",
                "currency": "GBP",
                "vat_rate": "20",
                "pack_size": "1",
                "moq": "1",
                "source_row_hash": "hash_1",
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "supplier_converter_valid_row",
            }
        ],
    )
    _set_age(test_dir / "batch_rows.csv", 0.25)

    _write_csv_rows(
        test_dir / "status_dashboard.csv",
        ["queue_position", "supplier_id", "supplier_name", "source_method", "source_location", "file_state", "queue_state", "operator_action", "control_state", "price_list_date", "bot_status", "web_unprocessed", "web_pass", "web_fail", "web_rescan", "second_unprocessed", "second_pass", "second_fail"],
        [
            {
                "queue_position": "1",
                "supplier_id": "clf",
                "supplier_name": "CLF",
                "source_method": "API",
                "source_location": "api",
                "file_state": "Ready",
                "queue_state": "Recommended",
                "operator_action": "Recommended next scan",
                "control_state": "Prioritised #1",
                "price_list_date": OBSERVED,
                "bot_status": "Next Scan",
                "web_unprocessed": "10",
            }
        ],
    )
    (test_dir / "next_action_report.md").parent.mkdir(parents=True, exist_ok=True)
    (test_dir / "next_action_report.md").write_text("# Price List Next Action Report\n\n- Supplier: CLF\n", encoding="utf-8")
    _set_age(test_dir / "status_dashboard.csv", 1.0)
    _set_age(test_dir / "next_action_report.md", 1.0)

    _write_csv_rows(
        f_live_dir / "f_login_backtrack_evidence_live.csv",
        ["supplier_id", "supplier_sku", "asin", "backtrack_observed_utc", "backtrack_attempt_number", "backtrack_status", "original_status_reason", "merged_into_candidate_flag"],
        [
            {
                "supplier_id": "entertainment_trading",
                "supplier_sku": "1243976",
                "asin": "B0000DC4EL",
                "backtrack_observed_utc": OBSERVED,
                "backtrack_attempt_number": "5",
                "backtrack_status": "dashboard_yes_no_unresolved" if parked_decision else "merged",
                "original_status_reason": "LOGIN_BACKTRACK_PENDING" if parked_decision else "PASS",
                "merged_into_candidate_flag": "0" if parked_decision else "1",
            }
        ],
    )
    _set_age(f_live_dir / "f_login_backtrack_evidence_live.csv", 1.0)

    _write_csv_rows(
        live_dir / "review_handoff_manifest.csv",
        ["built_at_utc", "supplier_id", "run_id", "operator_ready_flag", "ai_gate_status", "ai_gate_fail_rows", "ai_gate_quality_status"],
        [
            {
                "built_at_utc": OBSERVED,
                "supplier_id": "clf",
                "run_id": "review_test",
                "operator_ready_flag": "1",
                "ai_gate_status": "passed",
                "ai_gate_fail_rows": "0",
                "ai_gate_quality_status": "ok",
            }
        ],
    )
    _write_csv_rows(
        live_dir / "ai_gate_quality_report.csv",
        ["check", "status", "value", "notes", "observed_utc", "source_path"],
        [{"check": "current_ui_rows", "status": "ok", "value": "1", "observed_utc": OBSERVED, "source_path": "ai_gate_quality_report.csv"}],
    )
    _write_csv_rows(
        live_dir / "production_line_health.csv",
        ["check", "status", "value", "notes", "observed_utc", "source_path"],
        [{"check": "f_production_line_stage_contract_runtime", "status": "ok", "value": "completed", "notes": "stage_count=5", "observed_utc": OBSERVED, "source_path": "production_line_health.csv"}],
    )
    _write_csv_rows(
        live_dir / "review_pack_build_health.csv",
        ["check", "status", "value", "notes", "observed_utc", "source_path"],
        [{"check": "scanner_to_review_pack_build", "status": "ok", "value": "built", "notes": "test proof", "observed_utc": OBSERVED, "source_path": "review_pack_build_health.csv"}],
    )
    _write_csv_rows(
        live_dir / "split_rollout_readiness.csv",
        ["check", "status", "value", "notes", "observed_utc", "source_path"],
        [
            {"check": "f_split_rollout_execution_default_off", "status": "ok", "value": "legacy_full", "notes": "default off", "observed_utc": OBSERVED, "source_path": "split_rollout_readiness.csv"},
            {"check": "f_split_rollout_readiness", "status": "ok", "value": "ready_default_off", "notes": "fail_checks=0;warn_checks=0", "observed_utc": OBSERVED, "source_path": "split_rollout_readiness.csv"},
        ],
    )
    precheck_dir = root / "out" / "systems" / "F" / "price_list_manager" / "ai_prechecks" / "clf" / "run_test"
    _write_csv_rows(
        precheck_dir / "ai_precheck_health.csv",
        ["check", "status", "value", "notes", "observed_utc", "source_path"],
        [{"check": "incremental_ai_precheck", "status": "ok", "value": "ready_hidden", "notes": "test proof", "observed_utc": OBSERVED, "source_path": "ai_review_queue.csv"}],
    )
    _set_age(live_dir / "review_handoff_manifest.csv", 1.0)
    _set_age(live_dir / "ai_gate_quality_report.csv", 1.0)
    _set_age(live_dir / "production_line_health.csv", 1.0)
    _set_age(live_dir / "review_pack_build_health.csv", 1.0)
    _set_age(live_dir / "split_rollout_readiness.csv", 1.0)
    _set_age(precheck_dir / "ai_precheck_health.csv", 1.0)

    _write_csv_rows(
        manager_dir / "self_organisation" / "latest_f_script_registration_report.csv",
        ["script_path", "classification", "manager_module_id", "missing_fields"],
        [
            {
                "script_path": "scripts/flows/F/F005_build_supplier_price_list_universal.py",
                "classification": "registered",
                "manager_module_id": "F005_build_supplier_price_list_universal",
            },
            {
                "script_path": "scripts/flows/F/F010_build_feeder_candidate_intake.py",
                "classification": "registered",
                "manager_module_id": "F010_build_feeder_candidate_intake",
            },
            {
                "script_path": "scripts/flows/F/F020_build_feeder_candidate_classification.py",
                "classification": "registered",
                "manager_module_id": "F020_build_feeder_candidate_classification",
            },
            {
                "script_path": "scripts/flows/F/F030_build_shared_feeder_pass_logic.py",
                "classification": "registered",
                "manager_module_id": "F030_build_shared_feeder_pass_logic",
            },
            {
                "script_path": "scripts/flows/F/F040_build_feeder_candidate_approval_queue.py",
                "classification": "registered",
                "manager_module_id": "F040_build_feeder_candidate_approval_queue",
            },
            {
                "script_path": "scripts/flows/F/F050_build_feeder_po_handoff.py",
                "classification": "registered",
                "manager_module_id": "F050_build_feeder_po_handoff",
            },
            {
                "script_path": "scripts/flows/F/F060_build_legacy_sheet_review_pack.py",
                "classification": "registered",
                "manager_module_id": "F060_build_legacy_sheet_review_pack",
            },
            {
                "script_path": "scripts/flows/F/F070_build_backtest_policy_snapshot.py",
                "classification": "registered",
                "manager_module_id": "F070_build_backtest_policy_snapshot",
            },
            {
                "script_path": "scripts/flows/F/F071_build_backtest_input_view.py",
                "classification": "registered",
                "manager_module_id": "F071_build_backtest_input_view",
            },
            {
                "script_path": "scripts/flows/F/F072_run_backtest_replay.py",
                "classification": "registered",
                "manager_module_id": "F072_run_backtest_replay",
            },
            {
                "script_path": "scripts/flows/F/F073_build_backtest_summary.py",
                "classification": "registered",
                "manager_module_id": "F073_build_backtest_summary",
            },
            {
                "script_path": "scripts/flows/F/F074_build_backtest_health.py",
                "classification": "registered",
                "manager_module_id": "F074_build_backtest_health",
            },
            {
                "script_path": "scripts/flows/F/F075_apply_backtest_policy_updates.py",
                "classification": "registered",
                "manager_module_id": "F075_apply_backtest_policy_updates",
            },
            {
                "script_path": "scripts/flows/F/F080_build_feedback_calibration_shadow.py",
                "classification": "registered",
                "manager_module_id": "F080_build_feedback_calibration_shadow",
            },
            {
                "script_path": "scripts/flows/F/F062_reset_supplier_test_mode.py",
                "classification": "registered",
                "manager_module_id": "F062_reset_supplier_test_mode",
            },
            {
                "script_path": "scripts/flows/F/F090_build_amazon_listing_intake.py",
                "classification": "registered",
                "manager_module_id": "F090_build_amazon_listing_intake",
            },
            {
                "script_path": "scripts/flows/F/F091_reserve_amazon_listing_skus.py",
                "classification": "registered",
                "manager_module_id": "F091_reserve_amazon_listing_skus",
            },
            {
                "script_path": "scripts/flows/F/F092_build_amazon_listing_drafts.py",
                "classification": "registered",
                "manager_module_id": "F092_build_amazon_listing_drafts",
            },
            {
                "script_path": "scripts/flows/F/F093_run_amazon_listing_preview.py",
                "classification": "registered",
                "manager_module_id": "F093_run_amazon_listing_preview",
            },
            {
                "script_path": "scripts/flows/F/F094_submit_amazon_listing_drafts.py",
                "classification": "registered",
                "manager_module_id": "F094_submit_amazon_listing_drafts",
            },
            {
                "script_path": "scripts/flows/F/F095_check_amazon_listing_submission_status.py",
                "classification": "registered",
                "manager_module_id": "F095_check_amazon_listing_submission_status",
            },
            {
                "script_path": "scripts/flows/F/F096_reconcile_amazon_listing_submissions.py",
                "classification": "registered",
                "manager_module_id": "F096_reconcile_amazon_listing_submissions",
            },
            {
                "script_path": "scripts/flows/F/F097_check_amazon_listing_restrictions.py",
                "classification": "registered",
                "manager_module_id": "F097_check_amazon_listing_restrictions",
            },
            {
                "script_path": "scripts/flows/F/F098_build_brand_approval_queue.py",
                "classification": "registered",
                "manager_module_id": "F098_build_brand_approval_queue",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM010_check_acquisition_sources.py",
                "classification": "registered",
                "manager_module_id": "FPM010_check_acquisition_sources",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM011_import_ready_sources.py",
                "classification": "registered",
                "manager_module_id": "FPM011_import_ready_sources",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM012_enrich_batch_rows_for_f061.py",
                "classification": "registered",
                "manager_module_id": "FPM012_enrich_batch_rows_for_f061",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM013_download_ready_url_sources.py",
                "classification": "registered",
                "manager_module_id": "FPM013_download_ready_url_sources",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM014_fetch_api_sources.py",
                "classification": "registered",
                "manager_module_id": "FPM014_fetch_api_sources",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM015_fetch_google_sheet_sources.py",
                "classification": "registered",
                "manager_module_id": "FPM015_fetch_google_sheet_sources",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM016_fetch_gmail_email_sources.py",
                "classification": "registered",
                "manager_module_id": "FPM016_fetch_gmail_email_sources",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM001_build_test_fixtures.py",
                "classification": "registered",
                "manager_module_id": "FPM001_build_test_fixtures",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM020_run_placeholder_scanner.py",
                "classification": "registered",
                "manager_module_id": "FPM020_run_placeholder_scanner",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM030_update_memory_from_results.py",
                "classification": "registered",
                "manager_module_id": "FPM030_update_memory_from_results",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM040_build_next_action.py",
                "classification": "registered",
                "manager_module_id": "FPM040_build_next_action",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM060_build_status_dashboard.py",
                "classification": "registered",
                "manager_module_id": "FPM060_build_status_dashboard",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM070_stage_f061_handoff.py",
                "classification": "registered",
                "manager_module_id": "FPM070_stage_f061_handoff",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM080_set_queue_control.py",
                "classification": "registered",
                "manager_module_id": "FPM080_set_queue_control",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM090_set_f061_handoff_approval.py",
                "classification": "registered",
                "manager_module_id": "FPM090_set_f061_handoff_approval",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM100_apply_f061_handoff.py",
                "classification": "registered",
                "manager_module_id": "FPM100_apply_f061_handoff",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM110_run_test_mode_cycle.py",
                "classification": "registered",
                "manager_module_id": "FPM110_run_test_mode_cycle",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM120_build_f061_live_trial_samples.py",
                "classification": "registered",
                "manager_module_id": "FPM120_build_f061_live_trial_samples",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM121_apply_f061_live_trial_supplier.py",
                "classification": "registered",
                "manager_module_id": "FPM121_apply_f061_live_trial_supplier",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM125_import_f061_recovery_progress.py",
                "classification": "registered",
                "manager_module_id": "FPM125_import_f061_recovery_progress",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM126_update_memory_from_f061_results.py",
                "classification": "registered",
                "manager_module_id": "FPM126_update_memory_from_f061_results",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM140_check_review_handoff_ready.py",
                "classification": "registered",
                "manager_module_id": "FPM140_check_review_handoff_ready",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM150_build_completed_review_pack.py",
                "classification": "registered",
                "manager_module_id": "FPM150_build_completed_review_pack",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM155_apply_review_intelligence_gate.py",
                "classification": "registered",
                "manager_module_id": "FPM155_apply_review_intelligence_gate",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM156_build_ai_gate_quality_report.py",
                "classification": "registered",
                "manager_module_id": "FPM156_build_ai_gate_quality_report",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM157_build_incremental_ai_precheck.py",
                "classification": "registered",
                "manager_module_id": "FPM157_build_incremental_ai_precheck",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM158_ai_precheck_common.py",
                "classification": "registered",
                "manager_module_id": "FPM158_ai_precheck_common",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM160_f061_visible_login_maintenance.py",
                "classification": "registered",
                "manager_module_id": "FPM160_f061_visible_login_maintenance",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM180_build_production_line_run.py",
                "classification": "registered",
                "manager_module_id": "FPM180_build_production_line_run",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM190_build_split_rollout_readiness.py",
                "classification": "registered",
                "manager_module_id": "FPM190_build_split_rollout_readiness",
            },
            {
                "script_path": "scripts/flows/F/price_list_manager/FPM191_backfill_ai_quality_stamps.py",
                "classification": "registered",
                "manager_module_id": "FPM191_backfill_ai_quality_stamps",
            },
            {
                "script_path": "run_F_price_list_manager_cycle.bat",
                "classification": "registered",
                "manager_module_id": "run_F_price_list_manager_cycle",
            },
            {
                "script_path": "run_F_shure_test_mode_scan_once.bat",
                "classification": "registered",
                "manager_module_id": "run_F_shure_test_mode_scan_once",
            },
            {
                "script_path": "run_F_supplier_test_mode_scan_once.bat",
                "classification": "registered",
                "manager_module_id": "run_F_supplier_test_mode_scan_once",
            },
            {
                "script_path": "run_F_shure_full_legacy_scan.bat",
                "classification": "registered",
                "manager_module_id": "run_F_shure_full_legacy_scan",
            },
            {
                "script_path": "run_F_supplier_full_legacy_scan.bat",
                "classification": "registered",
                "manager_module_id": "run_F_supplier_full_legacy_scan",
            },
        ],
    )


def _write_o_midbuild_outputs(
    root: Path,
    *,
    unsafe_action_ready: bool = False,
    h_active: bool = False,
    complete_claim: bool = False,
    missing_bridge_label: bool = False,
    missing_po_source: bool = False,
    send_without_receipt: bool = False,
) -> None:
    expectations_path = root / "project_control" / "EXPECTATIONS" / "operations_loop_expectations.md"
    status = "Complete" if complete_claim else "Not Started"
    expectations_path.parent.mkdir(parents=True, exist_ok=True)
    expectations_path.write_text(
        "\n".join(
            [
                "# Operations Loop Expectations",
                "",
                "| Feature | Description | Status | Notes |",
                "|---|---|---|---|",
                f"| Restock Advisor | Generates actionable restock recommendations from live data | {status} | Planned component |",
                "| Human approval gate | Human approval step exists before commitment actions | Not Started | Planned decision-control step |",
                "| Purchase order creation | Approved recommendations become tracked purchase orders | Not Started | Planned component |",
                "| Ordered stock tracking | Ordered inventory state is tracked end-to-end | Not Started | Planned component |",
                "| Inventory receiving | Received inventory is recorded and reconciled | Not Started | Planned component |",
                "| Send To Amazon flow | Send-to-Amazon preparation and state tracking are integrated | Not Started | Planned component |",
                "| Closed-loop feedback | Updated stock/order state feeds back into A/B/E foundation | Not Started | Planned loop closure requirement |",
                "| Single workflow view | Operator can follow one connected workflow, not multiple tools | Not Started | Planned usability requirement |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    for rel_path in [
        "scripts/flows/O/O400_operator_ui.py",
        "scripts/flows/O/O410_product_database_ui.py",
        "scripts/flows/O/O420_product_database_edit_ui.py",
    ]:
        script_path = root / rel_path
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text("# test ui proof\n", encoding="utf-8")

    live = root / "out" / "systems" / "O" / "live"
    ready_flag = "1" if unsafe_action_ready else "0"
    net_fee_status = "missing" if unsafe_action_ready else "fresh"
    max_safe = "" if unsafe_action_ready else "4.50"
    safety_status = "missing_net_fee_model" if unsafe_action_ready else "within_target_roi_max"
    cost_flag = "0" if unsafe_action_ready else "1"

    _write_csv_rows(
        live / "restock_source_view.csv",
        [
            "asof_utc",
            "seller_sku",
            "asin",
            "supplier_name",
            "has_minimum_restock_inputs",
            "expected_refund_cost_per_unit_gbp",
            "refund_unit_rate_30d",
            "refund_unit_rate_90d",
            "refund_units_30d",
            "sales_units_30d",
            "refund_cost_basis",
            "refund_proof_state",
            "refund_sample_confidence",
            "expected_inbound_cost_per_unit_gbp",
            "inbound_cost_basis",
            "inbound_cost_confidence",
            "inbound_cost_source_asof",
            "profit_input_confidence",
            "profit_input_blockers",
            "net_fee_model_status",
            "max_safe_unit_cost_gbp",
        ],
        [
            {
                "asof_utc": OBSERVED,
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "supplier_name": "Supplier",
                "has_minimum_restock_inputs": "0",
                "expected_refund_cost_per_unit_gbp": "0.1",
                "refund_unit_rate_30d": "0.01",
                "refund_unit_rate_90d": "0.01",
                "refund_units_30d": "1",
                "sales_units_30d": "10",
                "refund_cost_basis": "sale_cohort_90d",
                "refund_proof_state": "api_proved_or_not_applicable",
                "refund_sample_confidence": "high",
                "expected_inbound_cost_per_unit_gbp": "0.2",
                "inbound_cost_basis": "allocated_inbound_cost_per_received_unit",
                "inbound_cost_confidence": "sku_allocated",
                "inbound_cost_source_asof": OBSERVED,
                "profit_input_confidence": "profit_inputs_verified",
                "profit_input_blockers": "",
                "net_fee_model_status": net_fee_status,
                "max_safe_unit_cost_gbp": max_safe,
            }
        ],
    )
    _write_csv_rows(
        live / "restock_recommendations_live.csv",
        ["asof_utc", "seller_sku", "asin", "recommendation_status", "max_safe_unit_cost_gbp", "purchase_price_safety_status", "net_fee_model_status"],
        [{"asof_utc": OBSERVED, "seller_sku": "SKU1", "asin": "ASIN1", "recommendation_status": "wait", "max_safe_unit_cost_gbp": max_safe, "purchase_price_safety_status": safety_status, "net_fee_model_status": net_fee_status}],
    )
    _write_csv_rows(
        live / "restock_review_queue.csv",
        ["queue_utc", "seller_sku", "asin", "recommendation_status", "suggested_action"],
        [{"queue_utc": OBSERVED, "seller_sku": "SKU1", "asin": "ASIN1", "recommendation_status": "wait", "suggested_action": "wait"}],
    )
    _write_csv_rows(
        live / "reorder_input_coverage_report.csv",
        [
            "report_utc",
            "seller_sku",
            "asin",
            "action_ready_now",
            "has_current_cost_input",
            "has_current_market_price_input",
            "net_fee_model_status",
            "max_safe_unit_cost_gbp",
            "max_target_roi_purchase_price_gbp",
            "purchase_price_safety_status",
        ],
        [
            {
                "report_utc": OBSERVED,
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "action_ready_now": ready_flag,
                "has_current_cost_input": cost_flag,
                "has_current_market_price_input": cost_flag,
                "net_fee_model_status": net_fee_status,
                "max_safe_unit_cost_gbp": max_safe,
                "max_target_roi_purchase_price_gbp": max_safe,
                "purchase_price_safety_status": safety_status,
            }
        ],
    )
    _write_csv_rows(
        live / "legacy_purchase_list_bridge.csv",
        ["bridge_utc", "source_system", "seller_sku", "recommendation_status", "done_flag"],
        [
            {
                "bridge_utc": OBSERVED,
                "source_system": "" if missing_bridge_label else "legacy_purchase_list",
                "seller_sku": "SKU1",
                "recommendation_status": "full_restock",
                "done_flag": "0",
            }
        ],
    )
    _write_csv_rows(
        live / "legacy_purchase_list_bridge_health.csv",
        ["check", "status", "value", "notes", "observed_utc", "source_path"],
        [{"check": "bridge_rows", "status": "ok", "value": "1", "notes": "ok", "observed_utc": OBSERVED, "source_path": "sheet"}],
    )
    _write_csv_rows(
        live / "restock_profit_checks_live.csv",
        ["check_utc", "seller_sku", "profit_verdict", "source_system", "price_status", "max_safe_unit_cost_gbp"],
        [{"check_utc": OBSERVED, "seller_sku": "SKU1", "profit_verdict": "needs_price_check", "source_system": "native_o", "price_status": "check_price", "max_safe_unit_cost_gbp": max_safe}],
    )
    _write_csv_rows(
        live / "restock_profit_check_health.csv",
        ["check_utc", "check_type", "check_name", "status", "value", "details"],
        [{"check_utc": OBSERVED, "check_type": "summary", "check_name": "rows", "status": "ok", "value": "1", "details": "ok"}],
    )
    _write_csv_rows(
        live / "restock_market_refresh_candidates_live.csv",
        ["check_utc", "seller_sku", "asin", "candidate_status", "source_system"],
        [{"check_utc": OBSERVED, "seller_sku": "SKU1", "asin": "ASIN1", "candidate_status": "ready", "source_system": "legacy_purchase_list"}],
    )
    _write_csv_rows(
        live / "restock_session_review_live.csv",
        [
            "session_utc",
            "session_id",
            "row_id",
            "source_class",
            "source_system",
            "source_reference",
            "supplier_name",
            "supplier_code",
            "seller_sku",
            "asin",
            "row_status",
            "action_safety_state",
            "action_block_reason",
            "operator_decision_state",
        ],
        [
            {
                "session_utc": OBSERVED,
                "session_id": "o_restock_session_v1",
                "row_id": "o_restock_session_v1:supplier:sku1",
                "source_class": "native_o",
                "source_system": "native_o",
                "source_reference": "native_o:SKU1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "row_status": "blocked",
                "action_safety_state": "blocked_from_clean_buy",
                "action_block_reason": "refund:missing_refund_confidence",
                "operator_decision_state": "proof_missing",
            }
        ],
    )
    _write_csv_rows(
        live / "restock_session_supplier_summary_live.csv",
        [
            "session_utc",
            "session_id",
            "supplier_name",
            "supplier_code",
            "total_rows",
            "source_classes",
            "ready_for_review_rows",
            "blocked_rows",
            "draft_order_qty_total",
            "draft_order_value_gbp",
            "supplier_order_viability_state",
            "top_block_reasons",
            "session_state",
        ],
        [
            {
                "session_utc": OBSERVED,
                "session_id": "o_restock_session_v1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "total_rows": "1",
                "source_classes": "native_o",
                "ready_for_review_rows": "0",
                "blocked_rows": "1",
                "draft_order_qty_total": "0",
                "draft_order_value_gbp": "",
                "supplier_order_viability_state": "review_only_not_po",
                "top_block_reasons": "refund:missing_refund_confidence",
                "session_state": "review_required",
            }
        ],
    )
    _write_csv_rows(
        live / "restock_session_reason_codes.csv",
        ["reason_code", "reason_label", "decision_family", "safe_to_draft", "creates_live_action", "requires_luke", "notes"],
        [
            {
                "reason_code": "proof_missing",
                "reason_label": "Proof missing",
                "decision_family": "proof",
                "safe_to_draft": "1",
                "creates_live_action": "0",
                "requires_luke": "0",
                "notes": "local only",
            }
        ],
    )
    _write_csv_rows(
        live / "restock_session_health.csv",
        ["check_utc", "check", "status", "value", "notes", "source_path"],
        [{"check_utc": OBSERVED, "check": "source_labels", "status": "ok", "value": "rows=1", "notes": "ok", "source_path": "session"}],
    )
    _write_csv_rows(
        live / "restock_session_draft_decision_events.csv",
        [
            "event_utc",
            "draft_id",
            "session_id",
            "row_id",
            "seller_sku",
            "asin",
            "supplier_name",
            "supplier_code",
            "source_class",
            "row_source_reference",
            "decision_code",
            "draft_order_qty",
            "snooze_until_utc",
            "decision_note",
            "actor",
            "event_source_reference",
            "draft_status",
            "creates_live_action",
        ],
        [],
    )
    _write_csv_rows(
        live / "restock_session_supplier_proof_events.csv",
        [
            "event_utc",
            "proof_id",
            "session_id",
            "row_id",
            "seller_sku",
            "asin",
            "supplier_name",
            "supplier_code",
            "source_class",
            "row_source_reference",
            "supplier_stock_state",
            "supplier_stock_qty",
            "backorder_state",
            "backorder_eta_utc",
            "supplier_file_asof_utc",
            "supplier_file_reference",
            "proof_note",
            "actor",
            "event_source_reference",
            "proof_status",
            "creates_live_action",
        ],
        [],
    )
    _write_csv_rows(
        live / "restock_session_pack_moq_proof_events.csv",
        [
            "event_utc",
            "proof_id",
            "session_id",
            "row_id",
            "seller_sku",
            "asin",
            "supplier_name",
            "supplier_code",
            "source_class",
            "row_source_reference",
            "pack_moq_proof_state",
            "pack_multiple",
            "supplier_moq",
            "valid_order_step",
            "proof_file_reference",
            "proof_note",
            "actor",
            "event_source_reference",
            "proof_status",
            "creates_live_action",
        ],
        [],
    )
    _write_csv_rows(
        live / "restock_session_supplier_batch_lines_live.csv",
        [
            "batch_utc",
            "batch_id",
            "session_id",
            "row_id",
            "draft_id",
            "draft_event_utc",
            "supplier_name",
            "supplier_code",
            "source_class",
            "seller_sku",
            "asin",
            "title",
            "supplier_sku",
            "barcode",
            "draft_order_qty",
            "current_supplier_cost_gbp",
            "draft_line_value_gbp",
            "supplier_order_viability_state",
            "action_safety_state",
            "action_block_reason",
            "line_state",
            "creates_live_action",
            "supplier_proof_checklist_status",
            "supplier_proof_missing_reasons",
            "supplier_match_state",
            "supplier_proof_state",
            "supplier_stock_state",
            "backorder_state",
            "supplier_file_asof_utc",
            "supplier_cost_proof_state",
            "pack_moq_proof_state",
        ],
        [],
    )
    _write_csv_rows(
        live / "restock_session_supplier_batch_summary_live.csv",
        [
            "batch_utc",
            "batch_id",
            "supplier_name",
            "supplier_code",
            "line_count",
            "draft_order_qty_total",
            "draft_order_value_gbp",
            "source_classes",
            "blocked_line_count",
            "native_line_count",
            "legacy_bridge_line_count",
            "batch_state",
            "block_reasons",
            "creates_live_action",
        ],
        [],
    )
    _write_csv_rows(
        live / "restock_session_supplier_batch_health.csv",
        ["check_utc", "check", "status", "value", "notes", "source_path"],
        [
            {
                "check_utc": OBSERVED,
                "check": "local_only_guard",
                "status": "ok",
                "value": "live_action_lines=0;bad_summary_rows=0;live_language_rows=0",
                "notes": "ok",
                "source_path": "batch",
            }
        ],
    )
    _write_csv_rows(
        live / "restock_supplier_file_presence_probe_live.csv",
        [
            "probe_utc",
            "probe_id",
            "batch_id",
            "session_id",
            "row_id",
            "supplier_name",
            "supplier_code",
            "seller_sku",
            "asin",
            "title",
            "supplier_sku",
            "barcode",
            "draft_order_qty",
            "price_files_root",
            "supplier_folder_path",
            "latest_supplier_file_path",
            "latest_supplier_file_name",
            "latest_supplier_file_mtime_utc",
            "latest_supplier_file_state",
            "identity_match_state",
            "matched_by",
            "matched_row_count",
            "searched_row_count",
            "searched_identity_columns",
            "probe_explanation",
            "clears_supplier_proof",
            "purchase_approval_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "creates_live_action",
            "read_error",
        ],
        [],
    )
    _write_csv_rows(
        live / "restock_supplier_file_source_index_live.csv",
        [
            "index_utc",
            "supplier_key",
            "supplier_id",
            "supplier_name",
            "f_source_status",
            "f_source_state",
            "f_source_location",
            "f_latest_source_path",
            "f_latest_source_name",
            "f_latest_source_mtime_utc",
            "f_latest_source_path_exists",
            "f_checked_at_utc",
            "local_price_files_root",
            "local_supplier_folder_path",
            "local_latest_file_path",
            "local_latest_file_name",
            "local_latest_file_mtime_utc",
            "local_file_count",
            "source_handoff_state",
            "handoff_explanation",
            "can_be_used_for_presence_probe",
            "clears_supplier_proof",
            "imports_supplier_file",
            "updates_f_status",
            "creates_live_action",
            "f_notes",
            "local_search_scope",
        ],
        [],
    )
    _write_csv_rows(
        live / "restock_supplier_file_source_index_health.csv",
        ["check_utc", "check", "status", "value", "notes", "source_path"],
        [
            {
                "check_utc": OBSERVED,
                "check": "local_only_guard",
                "status": "ok",
                "value": "unsafe_rows=0",
                "notes": "ok",
                "source_path": "supplier_file_source_index",
            }
        ],
    )
    _write_csv_rows(
        live / "restock_supplier_file_presence_probe_health.csv",
        ["check_utc", "check", "status", "value", "notes", "source_path"],
        [
            {
                "check_utc": OBSERVED,
                "check": "local_only_guard",
                "status": "ok",
                "value": "unsafe_rows=0",
                "notes": "ok",
                "source_path": "supplier_file_probe",
            }
        ],
    )
    _write_csv_rows(
        live / "restock_purchase_approval_preview_lines_live.csv",
        [
            "preview_utc",
            "approval_packet_id",
            "batch_id",
            "session_id",
            "row_id",
            "supplier_name",
            "supplier_code",
            "source_class",
            "seller_sku",
            "asin",
            "title",
            "supplier_sku",
            "barcode",
            "draft_order_qty",
            "current_supplier_cost_gbp",
            "draft_line_value_gbp",
            "supplier_batch_readiness_state",
            "supplier_batch_readiness_reasons",
            "supplier_proof_checklist_status",
            "supplier_proof_missing_reasons",
            "approval_preview_state",
            "approval_block_reasons",
            "creates_live_action",
        ],
        [],
    )
    _write_csv_rows(
        live / "restock_purchase_approval_preview_summary_live.csv",
        [
            "preview_utc",
            "approval_packet_id",
            "supplier_name",
            "supplier_code",
            "line_count",
            "draft_order_qty_total",
            "draft_order_value_gbp",
            "ready_line_count",
            "blocked_line_count",
            "source_classes",
            "approval_packet_state",
            "approval_block_reasons",
            "creates_live_action",
        ],
        [],
    )
    _write_csv_rows(
        live / "restock_purchase_approval_preview_health.csv",
        ["check_utc", "check", "status", "value", "notes", "source_path"],
        [
            {
                "check_utc": OBSERVED,
                "check": "local_only_guard",
                "status": "ok",
                "value": "live_action_rows=0;bad_summary_rows=0;live_language_rows=0",
                "notes": "ok",
                "source_path": "approval_preview",
            }
        ],
    )
    _write_csv_rows(
        live / "restock_purchase_approval_decision_events.csv",
        [
            "event_utc",
            "decision_id",
            "approval_packet_id",
            "supplier_name",
            "supplier_code",
            "source_preview_utc",
            "decision_state",
            "expected_line_count",
            "expected_ready_line_count",
            "expected_blocked_line_count",
            "expected_order_value_gbp",
            "decision_note",
            "actor",
            "event_source_reference",
            "decision_status",
            "creates_live_action",
        ],
        [],
    )
    _write_csv_rows(
        live / "restock_purchase_approval_guardrails_live.csv",
        [
            "guardrail_utc",
            "approval_packet_id",
            "source_preview_utc",
            "supplier_name",
            "supplier_code",
            "line_count",
            "ready_line_count",
            "blocked_line_count",
            "draft_order_value_gbp",
            "preview_packet_state",
            "latest_decision_state",
            "latest_decision_id",
            "latest_decision_utc",
            "approval_guardrail_state",
            "approval_guardrail_reasons",
            "creates_live_action",
        ],
        [],
    )
    _write_csv_rows(
        live / "restock_purchase_approval_guardrails_health.csv",
        ["check_utc", "check", "status", "value", "notes", "source_path"],
        [
            {
                "check_utc": OBSERVED,
                "check": "local_only_guard",
                "status": "ok",
                "value": "unsafe_events=0;unsafe_guard_rows=0",
                "notes": "ok",
                "source_path": "approval_guardrails",
            }
        ],
    )
    _write_csv_rows(
        live / "restock_po_draft_readiness_preview_lines_live.csv",
        [
            "preview_utc",
            "po_readiness_preview_id",
            "approval_packet_id",
            "source_preview_utc",
            "guardrail_utc",
            "batch_id",
            "session_id",
            "row_id",
            "supplier_name",
            "supplier_code",
            "source_class",
            "seller_sku",
            "asin",
            "title",
            "supplier_sku",
            "barcode",
            "draft_order_qty",
            "current_supplier_cost_gbp",
            "draft_line_value_gbp",
            "approval_preview_state",
            "approval_guardrail_state",
            "po_draft_readiness_state",
            "po_draft_block_reasons",
            "po_creation_allowed",
            "creates_live_action",
        ],
        [],
    )
    _write_csv_rows(
        live / "restock_po_draft_readiness_preview_summary_live.csv",
        [
            "preview_utc",
            "po_readiness_preview_id",
            "approval_packet_id",
            "supplier_name",
            "supplier_code",
            "line_count",
            "ready_line_count",
            "blocked_line_count",
            "draft_order_qty_total",
            "draft_order_value_gbp",
            "approval_guardrail_state",
            "po_draft_preview_state",
            "po_draft_block_reasons",
            "po_creation_allowed",
            "creates_live_action",
        ],
        [],
    )
    _write_csv_rows(
        live / "restock_po_draft_readiness_preview_health.csv",
        ["check_utc", "check", "status", "value", "notes", "source_path"],
        [
            {
                "check_utc": OBSERVED,
                "check": "local_only_guard",
                "status": "ok",
                "value": "live_action_rows=0;bad_summary_rows=0;live_language_rows=0",
                "notes": "ok",
                "source_path": "po_readiness",
            }
        ],
    )
    _write_csv_rows(
        live / "restock_po_line_design_preview_lines_live.csv",
        [
            "preview_utc",
            "po_line_design_id",
            "po_line_design_packet_id",
            "po_readiness_preview_id",
            "approval_packet_id",
            "source_readiness_utc",
            "batch_id",
            "session_id",
            "row_id",
            "supplier_name",
            "supplier_code",
            "source_class",
            "seller_sku",
            "asin",
            "title",
            "supplier_sku",
            "barcode",
            "designed_order_qty",
            "designed_unit_cost_gbp",
            "designed_line_value_gbp",
            "source_po_draft_readiness_state",
            "line_design_state",
            "line_design_block_reasons",
            "po_file_write_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "receiving_allowed",
            "send_to_amazon_allowed",
            "creates_live_action",
        ],
        [],
    )
    _write_csv_rows(
        live / "restock_po_line_design_preview_summary_live.csv",
        [
            "preview_utc",
            "po_line_design_packet_id",
            "approval_packet_id",
            "supplier_name",
            "supplier_code",
            "line_count",
            "ready_line_count",
            "blocked_line_count",
            "designed_order_qty_total",
            "designed_order_value_gbp",
            "line_design_packet_state",
            "line_design_block_reasons",
            "po_file_write_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "receiving_allowed",
            "send_to_amazon_allowed",
            "creates_live_action",
        ],
        [],
    )
    _write_csv_rows(
        live / "restock_po_line_design_preview_health.csv",
        ["check_utc", "check", "status", "value", "notes", "source_path"],
        [
            {
                "check_utc": OBSERVED,
                "check": "local_only_guard",
                "status": "ok",
                "value": "live_action_rows=0;bad_summary_rows=0;live_language_rows=0",
                "notes": "ok",
                "source_path": "po_line_design",
            }
        ],
    )
    _write_csv_rows(
        live / "restock_po_draft_packet_review_lines_live.csv",
        [
            "review_utc",
            "po_draft_packet_review_id",
            "po_line_design_id",
            "po_line_design_packet_id",
            "approval_packet_id",
            "source_design_utc",
            "batch_id",
            "session_id",
            "row_id",
            "supplier_name",
            "supplier_code",
            "source_class",
            "seller_sku",
            "asin",
            "title",
            "supplier_sku",
            "barcode",
            "review_order_qty",
            "review_unit_cost_gbp",
            "review_line_value_gbp",
            "source_line_design_state",
            "source_po_file_write_allowed",
            "source_po_creation_allowed",
            "source_purchase_commitment_allowed",
            "source_receiving_allowed",
            "source_send_to_amazon_allowed",
            "source_creates_live_action",
            "packet_review_line_state",
            "packet_review_block_reasons",
            "po_file_write_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "receiving_allowed",
            "send_to_amazon_allowed",
            "creates_live_action",
        ],
        [],
    )
    _write_csv_rows(
        live / "restock_po_draft_packet_review_summary_live.csv",
        [
            "review_utc",
            "po_draft_packet_review_id",
            "po_line_design_packet_id",
            "approval_packet_id",
            "supplier_name",
            "supplier_code",
            "line_count",
            "ready_line_count",
            "blocked_line_count",
            "review_order_qty_total",
            "review_order_value_gbp",
            "packet_review_state",
            "packet_review_block_reasons",
            "po_file_write_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "receiving_allowed",
            "send_to_amazon_allowed",
            "creates_live_action",
        ],
        [],
    )
    _write_csv_rows(
        live / "restock_po_draft_packet_review_health.csv",
        ["check_utc", "check", "status", "value", "notes", "source_path"],
        [
            {
                "check_utc": OBSERVED,
                "check": "local_only_guard",
                "status": "ok",
                "value": "source_action_rows=0;live_action_rows=0;bad_summary_rows=0;live_language_rows=0",
                "notes": "ok",
                "source_path": "po_draft_packet_review",
            }
        ],
    )
    _write_csv_rows(
        live / "restock_po_draft_hold_review_lines_live.csv",
        [
            "hold_utc",
            "po_draft_hold_review_id",
            "po_draft_packet_review_id",
            "po_line_design_packet_id",
            "approval_packet_id",
            "source_packet_review_utc",
            "batch_id",
            "session_id",
            "row_id",
            "supplier_name",
            "supplier_code",
            "source_class",
            "seller_sku",
            "asin",
            "title",
            "supplier_sku",
            "barcode",
            "hold_order_qty",
            "hold_unit_cost_gbp",
            "hold_line_value_gbp",
            "source_packet_review_line_state",
            "source_po_file_write_allowed",
            "source_po_creation_allowed",
            "source_purchase_commitment_allowed",
            "source_receiving_allowed",
            "source_send_to_amazon_allowed",
            "source_creates_live_action",
            "hold_review_line_state",
            "hold_review_reasons",
            "po_file_write_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "receiving_allowed",
            "send_to_amazon_allowed",
            "creates_live_action",
        ],
        [],
    )
    _write_csv_rows(
        live / "restock_po_draft_hold_review_summary_live.csv",
        [
            "hold_utc",
            "po_draft_hold_review_id",
            "po_draft_packet_review_id",
            "po_line_design_packet_id",
            "approval_packet_id",
            "supplier_name",
            "supplier_code",
            "line_count",
            "held_line_count",
            "blocked_line_count",
            "hold_order_qty_total",
            "hold_order_value_gbp",
            "hold_review_state",
            "hold_review_reasons",
            "po_file_write_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "receiving_allowed",
            "send_to_amazon_allowed",
            "creates_live_action",
        ],
        [],
    )
    _write_csv_rows(
        live / "restock_po_draft_hold_review_health.csv",
        ["check_utc", "check", "status", "value", "notes", "source_path"],
        [
            {
                "check_utc": OBSERVED,
                "check": "local_only_guard",
                "status": "ok",
                "value": "source_action_rows=0;live_action_rows=0;bad_summary_rows=0;live_language_rows=0",
                "notes": "ok",
                "source_path": "po_draft_hold_review",
            }
        ],
    )
    _write_csv_rows(
        live / "restock_po_draft_file_shape_preview_lines_live.csv",
        [
            "shape_utc",
            "po_draft_file_shape_preview_id",
            "po_draft_hold_review_id",
            "po_draft_packet_review_id",
            "po_line_design_packet_id",
            "approval_packet_id",
            "source_hold_utc",
            "batch_id",
            "session_id",
            "row_id",
            "supplier_name",
            "supplier_code",
            "source_class",
            "seller_sku",
            "asin",
            "title",
            "supplier_sku",
            "barcode",
            "file_shape_qty",
            "file_shape_unit_cost_gbp",
            "file_shape_line_value_gbp",
            "source_hold_review_line_state",
            "source_po_file_write_allowed",
            "source_po_creation_allowed",
            "source_purchase_commitment_allowed",
            "source_receiving_allowed",
            "source_send_to_amazon_allowed",
            "source_creates_live_action",
            "file_shape_line_state",
            "file_shape_block_reasons",
            "po_file_write_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "receiving_allowed",
            "send_to_amazon_allowed",
            "creates_live_action",
        ],
        [],
    )
    _write_csv_rows(
        live / "restock_po_draft_file_shape_preview_summary_live.csv",
        [
            "shape_utc",
            "po_draft_file_shape_preview_id",
            "po_draft_hold_review_id",
            "po_draft_packet_review_id",
            "po_line_design_packet_id",
            "approval_packet_id",
            "supplier_name",
            "supplier_code",
            "line_count",
            "ready_line_count",
            "blocked_line_count",
            "file_shape_qty_total",
            "file_shape_value_gbp",
            "file_shape_state",
            "file_shape_block_reasons",
            "po_file_write_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "receiving_allowed",
            "send_to_amazon_allowed",
            "creates_live_action",
        ],
        [],
    )
    _write_csv_rows(
        live / "restock_po_draft_file_shape_preview_health.csv",
        ["check_utc", "check", "status", "value", "notes", "source_path"],
        [
            {
                "check_utc": OBSERVED,
                "check": "local_only_guard",
                "status": "ok",
                "value": "source_action_rows=0;live_action_rows=0;bad_summary_rows=0;live_language_rows=0",
                "notes": "ok",
                "source_path": "po_draft_file_shape_preview",
            }
        ],
    )
    _write_csv_rows(
        live / "restock_po_preview_construction_summary_live.csv",
        [
            "summary_utc",
            "stage_key",
            "stage_label",
            "source_contract",
            "source_health_contract",
            "state_column",
            "line_rows",
            "ready_or_held_rows",
            "blocked_rows",
            "health_rows",
            "health_bad_rows",
            "stage_state",
            "stage_block_reasons",
            "po_file_write_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "receiving_allowed",
            "send_to_amazon_allowed",
            "creates_live_action",
        ],
        [
            {
                "summary_utc": OBSERVED,
                "stage_key": "po_draft_readiness",
                "stage_label": "PO draft readiness",
                "source_contract": "restock_po_draft_readiness_preview_lines_live",
                "source_health_contract": "restock_po_draft_readiness_preview_health",
                "state_column": "po_draft_readiness_state",
                "line_rows": "0",
                "ready_or_held_rows": "0",
                "blocked_rows": "0",
                "health_rows": "1",
                "health_bad_rows": "0",
                "stage_state": "built_waiting_for_rows",
                "stage_block_reasons": "",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            },
            {
                "summary_utc": OBSERVED,
                "stage_key": "po_line_design",
                "stage_label": "PO line design",
                "source_contract": "restock_po_line_design_preview_lines_live",
                "source_health_contract": "restock_po_line_design_preview_health",
                "state_column": "line_design_state",
                "line_rows": "0",
                "ready_or_held_rows": "0",
                "blocked_rows": "0",
                "health_rows": "1",
                "health_bad_rows": "0",
                "stage_state": "built_waiting_for_rows",
                "stage_block_reasons": "",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            },
            {
                "summary_utc": OBSERVED,
                "stage_key": "po_draft_packet_review",
                "stage_label": "PO draft packet review",
                "source_contract": "restock_po_draft_packet_review_lines_live",
                "source_health_contract": "restock_po_draft_packet_review_health",
                "state_column": "packet_review_line_state",
                "line_rows": "0",
                "ready_or_held_rows": "0",
                "blocked_rows": "0",
                "health_rows": "1",
                "health_bad_rows": "0",
                "stage_state": "built_waiting_for_rows",
                "stage_block_reasons": "",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            },
            {
                "summary_utc": OBSERVED,
                "stage_key": "po_draft_hold_review",
                "stage_label": "PO draft hold review",
                "source_contract": "restock_po_draft_hold_review_lines_live",
                "source_health_contract": "restock_po_draft_hold_review_health",
                "state_column": "hold_review_line_state",
                "line_rows": "0",
                "ready_or_held_rows": "0",
                "blocked_rows": "0",
                "health_rows": "1",
                "health_bad_rows": "0",
                "stage_state": "built_waiting_for_rows",
                "stage_block_reasons": "",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            },
            {
                "summary_utc": OBSERVED,
                "stage_key": "po_draft_file_shape",
                "stage_label": "PO draft file-shape preview",
                "source_contract": "restock_po_draft_file_shape_preview_lines_live",
                "source_health_contract": "restock_po_draft_file_shape_preview_health",
                "state_column": "file_shape_line_state",
                "line_rows": "0",
                "ready_or_held_rows": "0",
                "blocked_rows": "0",
                "health_rows": "1",
                "health_bad_rows": "0",
                "stage_state": "built_waiting_for_rows",
                "stage_block_reasons": "",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            },
        ],
    )
    _write_csv_rows(
        live / "restock_po_preview_construction_summary_health.csv",
        ["check_utc", "check", "status", "value", "notes", "source_path"],
        [
            {
                "check_utc": OBSERVED,
                "check": "local_only_guard",
                "status": "ok",
                "value": "live_action_rows=0;live_language_rows=0",
                "notes": "ok",
                "source_path": "po_preview_construction_summary",
            }
        ],
    )
    _write_csv_rows(
        live / "restock_po_draft_review_control_events.csv",
        [
            "event_utc",
            "control_event_id",
            "po_draft_file_shape_preview_id",
            "po_draft_hold_review_id",
            "po_draft_packet_review_id",
            "po_line_design_packet_id",
            "approval_packet_id",
            "supplier_name",
            "supplier_code",
            "source_shape_utc",
            "decision_state",
            "expected_line_count",
            "expected_ready_line_count",
            "expected_blocked_line_count",
            "expected_file_shape_value_gbp",
            "decision_note",
            "actor",
            "event_source_reference",
            "decision_status",
            "po_file_write_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "receiving_allowed",
            "send_to_amazon_allowed",
            "creates_live_action",
        ],
        [],
    )
    _write_csv_rows(
        live / "restock_po_draft_review_controls_live.csv",
        [
            "control_utc",
            "po_draft_file_shape_preview_id",
            "po_draft_hold_review_id",
            "po_draft_packet_review_id",
            "po_line_design_packet_id",
            "approval_packet_id",
            "source_shape_utc",
            "supplier_name",
            "supplier_code",
            "line_count",
            "ready_line_count",
            "blocked_line_count",
            "file_shape_value_gbp",
            "source_file_shape_state",
            "latest_decision_state",
            "latest_control_event_id",
            "latest_decision_utc",
            "review_control_state",
            "review_control_reasons",
            "po_file_write_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "receiving_allowed",
            "send_to_amazon_allowed",
            "creates_live_action",
        ],
        [],
    )
    _write_csv_rows(
        live / "restock_po_draft_review_controls_health.csv",
        ["check_utc", "check", "status", "value", "notes", "source_path"],
        [
            {
                "check_utc": OBSERVED,
                "check": "local_only_guard",
                "status": "ok",
                "value": "live_action_rows=0;live_language_rows=0",
                "notes": "ok",
                "source_path": "po_draft_review_controls",
            }
        ],
    )
    _write_csv_rows(
        live / "restock_po_draft_export_preview_lines_live.csv",
        _export_preview_headers(),
        [],
    )
    _write_csv_rows(
        live / "restock_po_draft_export_preview_summary_live.csv",
        _export_preview_summary_headers(),
        [],
    )
    _write_csv_rows(
        live / "restock_po_draft_export_preview_health.csv",
        ["check_utc", "check", "status", "value", "notes", "source_path"],
        [
            {
                "check_utc": OBSERVED,
                "check": "local_only_guard",
                "status": "ok",
                "value": "live_action_rows=0",
                "notes": "ok",
                "source_path": "po_draft_export_preview",
            }
        ],
    )
    _write_csv_rows(
        live / "restock_po_draft_export_gate_events.csv",
        _export_gate_event_headers(),
        [],
    )
    _write_csv_rows(
        live / "restock_po_draft_export_gate_live.csv",
        _export_gate_headers(),
        [],
    )
    _write_csv_rows(
        live / "restock_po_draft_export_gate_health.csv",
        ["check_utc", "check", "status", "value", "notes", "source_path"],
        [
            {
                "check_utc": OBSERVED,
                "check": "local_only_guard",
                "status": "ok",
                "value": "live_action_rows=0;live_language_rows=0",
                "notes": "ok",
                "source_path": "po_draft_export_gate",
            }
        ],
    )
    _write_csv_rows(
        live / "product_db_operator_view.csv",
        ["asof_utc", "seller_sku", "asin", "title", "operational_status"],
        [{"asof_utc": OBSERVED, "seller_sku": "SKU1", "asin": "ASIN1", "title": "Product", "operational_status": "Active"}],
    )

    source_event = "" if missing_po_source else "o-ui-decision-1"
    _write_csv_rows(
        live / "restock_decisions_log.csv",
        ["decision_utc", "event_id", "seller_sku", "decision_action", "final_decision_status", "confirmed_unit_cost", "confirmed_qty", "cost_mode", "recommendation_basis"],
        [{"decision_utc": OBSERVED, "event_id": "o-ui-decision-1", "seller_sku": "SKU1", "decision_action": "approve_test_restock", "final_decision_status": "test_restock", "confirmed_unit_cost": "1.00", "confirmed_qty": "1", "cost_mode": "test", "recommendation_basis": "test_cost_snapshot"}],
    )
    _write_csv_rows(
        live / "purchase_orders_live.csv",
        ["po_id", "created_utc", "supplier_name", "po_status", "total_lines"],
        [{"po_id": "PO1", "created_utc": OBSERVED, "supplier_name": "Supplier", "po_status": "draft", "total_lines": "1"}],
    )
    _write_csv_rows(
        live / "purchase_order_lines_live.csv",
        ["po_id", "po_line_id", "seller_sku", "asin", "ordered_qty", "receipt_status", "source_event_id", "cost_mode", "recommendation_basis"],
        [{"po_id": "PO1", "po_line_id": "POL1", "seller_sku": "SKU1", "asin": "ASIN1", "ordered_qty": "1", "receipt_status": "not_received", "source_event_id": source_event, "cost_mode": "test", "recommendation_basis": "test_cost_snapshot"}],
    )
    _write_csv_rows(live / "purchase_order_draft_holds.csv", ["hold_utc", "event_id", "seller_sku", "hold_reason"], [])
    _write_csv_rows(
        live / "ordered_stock_state.csv",
        ["po_id", "po_line_id", "seller_sku", "ordered_qty", "received_qty", "remaining_open_qty", "receipt_status", "asof_utc"],
        [{"po_id": "PO1", "po_line_id": "POL1", "seller_sku": "SKU1", "ordered_qty": "1", "received_qty": "0", "remaining_open_qty": "1", "receipt_status": "not_received", "asof_utc": OBSERVED}],
    )
    receiving_rows = [] if send_without_receipt else [{"event_utc": OBSERVED, "event_id": "REC1", "po_id": "PO1", "po_line_id": "POL1", "seller_sku": "SKU1", "received_qty": "1", "event_source": "phase4_test"}]
    _write_csv_rows(live / "receiving_events.csv", ["event_utc", "event_id", "po_id", "po_line_id", "seller_sku", "received_qty", "event_source"], receiving_rows)
    _write_csv_rows(live / "receiving_event_holds.csv", ["hold_utc", "event_id", "po_id", "po_line_id", "seller_sku", "received_qty", "hold_reason"], [])
    queue_rows = [{"queue_utc": OBSERVED, "po_id": "PO1", "po_line_id": "POL1", "seller_sku": "SKU1", "received_qty_available_for_send": "" if send_without_receipt else "1"}] if send_without_receipt else []
    _write_csv_rows(live / "send_to_amazon_queue.csv", ["queue_utc", "po_id", "po_line_id", "seller_sku", "received_qty_available_for_send"], queue_rows)
    _write_csv_rows(live / "send_to_amazon_handoff_log.csv", ["event_utc", "event_id", "po_id", "po_line_id", "seller_sku", "handoff_qty"], [])
    _write_csv_rows(live / "send_to_amazon_handoff_holds.csv", ["hold_utc", "event_id", "po_id", "po_line_id", "seller_sku", "hold_reason"], [])

    for path in live.glob("*.csv"):
        _set_age(path, 0.25)

    if h_active:
        for lock_path in [
            root / "out" / "systems" / "H" / "live" / "H_pricing_cycle.lock",
            root / "out" / "H_pricing_cycle.lock",
        ]:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_path.write_text(f"H|pid=999999|run_id=H_test|start={OBSERVED}|heartbeat={OBSERVED}\n", encoding="utf-8")


def _write_active_autonomy_policy(root: Path) -> None:
    path = root / "config" / "manager" / "autonomy_policy.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": "active",
                "controlled_technical_pause_resume_allowed": True,
                "business_decisions_delegated": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_quiet_autonomy_policy(root: Path) -> None:
    path = root / "config" / "manager" / "autonomy_policy.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": "active",
                "mode": "quiet_autonomy",
                "controlled_technical_pause_resume_allowed": True,
                "controlled_technical_pause_requires_controller": True,
                "business_decisions_delegated": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_h_controller_install_status(root: Path, *, installed: bool, success: bool, failure_reason: str = "") -> None:
    path = root / "out" / "locks" / "h_maintenance_controller_install_status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "installed": installed,
                "success": success,
                "failure_reason": failure_reason,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_hourly_mot_marks_fresh_a_evidence_ok(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_required_outputs(tmp_path)
    _write_sql_tables(tmp_path)

    result = build_a_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")

    assert result["status"] == "ok"
    assert result["fail_count"] == 0
    assert result["warn_count"] == 0
    assert paths["hourly_mot_a_csv"].exists()
    assert paths["hourly_mot_latest_md"].exists()


def test_hourly_mot_marks_fresh_b_evidence_ok(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "ok"
    assert result["fail_count"] == 0
    assert rows["b_sellerboard_bridge_report"]["status"] == "not_checked"
    assert rows["b_old_checklist_clue"]["status"] == "not_checked"
    assert paths["hourly_mot_b_csv"].exists()


def test_b_pnl_stale_warning_is_parked_waiting_producer_refresh(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _set_age(tmp_path / "out" / "pnl_daily.csv", 25.0)
    _write_b_locks(tmp_path)

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    work_item = next(row for row in worklist_rows if row["check"] == "b_pnl_daily")

    assert rows["b_pnl_daily"]["status"] == "warn"
    assert rows["b_pnl_daily"]["value"] == "stale"
    assert "waiting producer refresh proof" in rows["b_pnl_daily"]["root_cause_guess"]
    assert "d001_step_seen=0" in rows["b_pnl_daily"]["actual_proof"]
    assert work_item["status"] == "parked"
    assert work_item["luke_action_required"] == "0"
    assert "waiting producer refresh proof" in work_item["notes"]


def test_b_pnl_same_day_daily_output_does_not_block_management(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _set_age(tmp_path / "out" / "pnl_daily.csv", 9.0)
    _write_b_locks(tmp_path)
    _write_b_completion_clean_inputs(tmp_path)

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_pnl_daily"]["status"] == "ok"
    assert rows["b_pnl_daily"]["value"] == "fresh_enough"
    assert rows["b_management_ready_for_maintenance"]["status"] == "ok"


def test_b_pnl_stale_points_to_health_gate_when_publish_was_blocked(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path, gate_state="fail", gate_fail_count=1)
    _write_b_required_outputs(tmp_path, stale_check="b_pnl_daily")
    _write_b_locks(tmp_path)

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_pnl_daily"]["status"] == "fail"
    assert rows["b_pnl_daily"]["value"] == "blocked_by_b_health_gate"
    assert "health gate" in rows["b_pnl_daily"]["root_cause_guess"]
    assert "d001_step_seen=0" in rows["b_pnl_daily"]["actual_proof"]


def test_b_pnl_blocked_by_true_token_shortage_needs_luke_decision(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path, gate_state="fail", gate_fail_count=1)
    _write_b_required_outputs(tmp_path, stale_check="b_pnl_daily")
    _write_b_locks(tmp_path)
    shortage_path = tmp_path / "out" / "token_shortages_by_sku.csv"
    _write_csv_rows(
        shortage_path,
        ["timestamp", "seller_sku", "missing_qty", "shortage_class", "evidence_note", "next_action"],
        [
            {
                "timestamp": OBSERVED,
                "seller_sku": "AK-OB6V-HIYD",
                "missing_qty": "3",
                "shortage_class": "true_live_shortage",
                "evidence_note": "missing_qty=3;available_tokens=0",
                "next_action": "wait_for_receipt_or_approved_stock_correction",
            }
        ],
    )
    _set_age(shortage_path, 0.25)

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "decision_needed"
    assert rows["b_pnl_daily"]["status"] == "decision_needed"
    assert rows["b_pnl_daily"]["value"] == "blocked_by_protected_token_shortage"
    assert rows["b_pnl_daily"]["luke_action_required"] == "1"
    assert "AK-OB6V-HIYD" in rows["b_pnl_daily"]["actual_proof"]
    assert rows["b_management_ready_for_maintenance"]["status"] == "decision_needed"
    assert rows["b_management_ready_for_maintenance"]["luke_action_required"] == "1"
    assert "protected_decisions=1" in rows["b_management_ready_for_maintenance"]["value"]


def test_b_pnl_blocked_by_runtime_adjustment_pending_needs_luke_decision(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path, gate_state="fail", gate_fail_count=1)
    _write_b_required_outputs(tmp_path, stale_check="b_pnl_daily")
    _write_b_locks(tmp_path)
    shortage_path = tmp_path / "out" / "token_shortages_by_sku.csv"
    _write_csv_rows(
        shortage_path,
        ["timestamp", "seller_sku", "missing_qty", "shortage_class", "evidence_note", "next_action"],
        [
            {
                "timestamp": OBSERVED,
                "seller_sku": "T8-6UWL-I3E1",
                "missing_qty": "1",
                "shortage_class": "runtime_adjustment_pending",
                "evidence_note": "insufficient_tokens_to_remove",
                "next_action": "rerun_b009_when_stock_events_raw_available",
            }
        ],
    )
    _set_age(shortage_path, 0.25)

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "decision_needed"
    assert rows["b_pnl_daily"]["status"] == "decision_needed"
    assert rows["b_pnl_daily"]["value"] == "blocked_by_protected_token_shortage"
    assert rows["b_pnl_daily"]["luke_action_required"] == "1"
    assert "T8-6UWL-I3E1" in rows["b_pnl_daily"]["actual_proof"]


def test_b_stock_receipt_token_sync_warns_when_allocated_order_still_has_placeholder(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_csv_rows(
        tmp_path / "out" / "token_allocations_live.csv",
        ["order_id", "order_date", "seller_sku", "quantity", "token_id", "token_cost", "currency", "allocation_date", "source_level", "notes"],
        [
            {
                "order_id": "202-9364806-5461939",
                "order_date": "2026-05-26T09:30:00Z",
                "seller_sku": "VF-3T0K-DR5O",
                "quantity": "1",
                "token_id": "SR-20251119-001-0059",
                "token_cost": "2.05",
                "currency": "GBP",
                "allocation_date": "2026-05-26T09:45:00Z",
                "source_level": "1",
                "notes": "live_allocation",
            }
        ],
    )
    _write_csv_rows(
        tmp_path / "out" / "orders_missing_tokens.csv",
        ["Order ID", "SKU", "Date", "Quantity Ordered", "placeholder_applied_flag"],
        [
            {
                "Order ID": "202-9364806-5461939",
                "SKU": "VF-3T0K-DR5O",
                "Date": "2026-05-26T09:30:00Z",
                "Quantity Ordered": "1",
                "placeholder_applied_flag": "1",
            }
        ],
    )
    _write_csv_rows(
        tmp_path / "out" / "order_master.csv",
        ["Date", "Order ID", "SKU", "Missing_Token_Flag", "COGS_Placeholder_Applied"],
        [
            {
                "Date": "2026-05-26T09:30:00Z",
                "Order ID": "202-9364806-5461939",
                "SKU": "VF-3T0K-DR5O",
                "Missing_Token_Flag": "1",
                "COGS_Placeholder_Applied": "1",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    work_item = next(row for row in worklist_rows if row["check"] == "b_stock_receipt_token_sync")

    assert rows["b_stock_receipt_token_sync"]["status"] == "warn"
    assert "allocated_missing_token_rows=1" in rows["b_stock_receipt_token_sync"]["value"]
    assert "allocated_order_master_placeholder_rows=1" in rows["b_stock_receipt_token_sync"]["value"]
    assert work_item["status"] == "new"
    assert work_item["luke_action_required"] == "0"


def test_b_stock_receipt_token_sync_warns_when_receipt_importer_is_skipped_and_receipts_are_stale(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_manifest(
        tmp_path,
        steps=[
            {
                "name": "process_stock_receipts_sheet.py",
                "script_or_function": "scripts/tools/process_stock_receipts_sheet.py",
                "step_status": "skipped",
                "notes": "skipped because A_ENABLE_STOCK_RECEIPTS_SHEET=0",
            }
        ],
    )
    _set_age(tmp_path / "out" / "stock_receipts_latest.csv", 240.0)

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_stock_receipt_token_sync"]["status"] == "warn"
    assert rows["b_stock_receipt_token_sync"]["value"] == "receipt_intake_skipped_or_stale"
    assert "a_receipt_step=skipped" in rows["b_stock_receipt_token_sync"]["actual_proof"]


def test_b_stock_receipt_token_sync_uses_clean_preview_when_receipt_importer_is_skipped(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_manifest(
        tmp_path,
        steps=[
            {
                "name": "process_stock_receipts_sheet.py",
                "script_or_function": "scripts/tools/process_stock_receipts_sheet.py",
                "step_status": "skipped",
                "notes": "skipped because A_ENABLE_STOCK_RECEIPTS_SHEET=0",
            }
        ],
    )
    _set_age(tmp_path / "out" / "stock_receipts_latest.csv", 240.0)
    _write_csv_rows(
        tmp_path / "out" / "systems" / "M" / "b_stock_receipt_token_sync" / "b_stock_receipt_intake_preview_summary.csv",
        ["metric", "value"],
        [
            {"metric": "status", "value": "ok"},
            {"metric": "preview_rows", "value": "0"},
            {"metric": "protected_decision_rows", "value": "0"},
            {"metric": "token_creator_proof_gap_if_unprocessed_total", "value": "0"},
            {"metric": "orders_shipment_rows", "value": "5"},
            {"metric": "orders_shipment_local_gap_rows", "value": "0"},
            {"metric": "local_orders_file_stale", "value": "0"},
            {"metric": "orders_staged_refresh_rows", "value": "1653"},
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_stock_receipt_token_sync"]["status"] == "ok"
    assert rows["b_stock_receipt_token_sync"]["value"] == "in_sync"
    assert "receipt_preview_status=ok" in rows["b_stock_receipt_token_sync"]["actual_proof"]


def test_b_stock_receipt_token_sync_warns_when_preview_needs_token_creator_proof(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_csv_rows(
        tmp_path / "out" / "systems" / "M" / "b_stock_receipt_token_sync" / "b_stock_receipt_intake_preview_summary.csv",
        ["metric", "value"],
        [
            {"metric": "status", "value": "proof_needed"},
            {"metric": "preview_rows", "value": "3"},
            {"metric": "protected_decision_rows", "value": "3"},
            {"metric": "tokens_processor_would_create_total", "value": "390"},
            {"metric": "token_creator_proof_gap_if_unprocessed_total", "value": "390"},
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_stock_receipt_token_sync"]["status"] == "warn"
    assert rows["b_stock_receipt_token_sync"]["luke_action_required"] == "0"
    assert "receipt_rows_need_token_creator_proof" in rows["b_stock_receipt_token_sync"]["value"]
    assert "protected_live_action_rows=3" in rows["b_stock_receipt_token_sync"]["value"]
    assert "receipt_preview_rows=3" in rows["b_stock_receipt_token_sync"]["actual_proof"]
    assert "receipt_preview_token_creator_proof_gap_if_unprocessed=390" in rows["b_stock_receipt_token_sync"]["actual_proof"]


def test_b_completion_gates_clear_when_management_and_order_truth_are_proven(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_b_completion_clean_inputs(tmp_path)

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "ok"
    assert rows["b_management_ready_for_maintenance"]["status"] == "ok"
    assert rows["b_management_ready_for_maintenance"]["value"].startswith("ready_for_maintenance")
    assert rows["b_order_truth_completion"]["status"] == "ok"
    assert rows["b_order_truth_completion"]["value"].startswith("complete")


def test_b_management_ready_when_only_order_truth_bridge_warnings_remain(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_b_completion_clean_inputs(tmp_path)
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_return_token_bridge.csv",
        [
            "order_id",
            "sku",
            "api_refund_proof_state",
            "amazon_return_proof_state",
            "token_return_state",
            "return_cogs_recovered_exvat",
            "blocked_return_cogs_exvat",
            "sellerboard_match_state",
            "proof_label",
            "roi_stock_recovery_state",
            "mismatch_state",
        ],
        [
            {
                "order_id": "026-8741500-3853120",
                "sku": "WX-L5UA-UB1Q",
                "api_refund_proof_state": "api_proved",
                "amazon_return_proof_state": "not_yet_proven",
                "token_return_state": "reused",
                "return_cogs_recovered_exvat": "0",
                "blocked_return_cogs_exvat": "0",
                "sellerboard_match_state": "not_used_as_truth",
                "proof_label": "token_reuse_without_amazon_return_proof",
                "roi_stock_recovery_state": "blocked_from_live_roi",
                "mismatch_state": "warning",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "warn"
    assert rows["b_refund_return_token_bridge"]["status"] == "warn"
    assert rows["b_order_truth_completion"]["status"] == "warn"
    assert rows["b_management_ready_for_maintenance"]["status"] == "ok"
    assert rows["b_management_ready_for_maintenance"]["value"].startswith(
        "ready_for_maintenance_with_parked_truth_warnings"
    )
    assert "bridge_warns=b_refund_return_token_bridge" in rows["b_management_ready_for_maintenance"]["actual_proof"]


def test_b_completion_gate_needs_luke_when_admin_inbox_is_unproven(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_b_completion_clean_inputs(tmp_path)
    (tmp_path / SOURCE_PROOF_REL_PATH).unlink()

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "decision_needed"
    assert rows["b_management_ready_for_maintenance"]["status"] == "decision_needed"
    assert rows["b_management_ready_for_maintenance"]["luke_action_required"] == "1"
    assert "protected_decisions=1" in rows["b_management_ready_for_maintenance"]["value"]


def test_b_order_truth_completion_fails_when_missing_order_is_visible(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_b_sellerboard_bridge_outputs(tmp_path, missing_orders=1, unmapped_shipped=1)
    _write_b_marketplace_gap_inputs(tmp_path)

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_order_truth_completion"]["status"] == "fail"
    assert "b_sellerboard_order_reconciliation" in rows["b_order_truth_completion"]["actual_proof"]
    assert rows["b_management_ready_for_maintenance"]["status"] == "fail"


def test_b_sellerboard_gap_becomes_warning_when_order_is_api_proved_in_quarantine(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_b_sellerboard_bridge_outputs(tmp_path, missing_orders=1, unmapped_shipped=1)
    _write_b_marketplace_gap_inputs(tmp_path)
    _write_b_cursor_proof(tmp_path)
    _write_b_recovery_quarantine(tmp_path)

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    truth_item = next(row for row in worklist_rows if row["check"] == "b_order_truth_completion")
    promotion_item = next(row for row in worklist_rows if row["check"] == "b_order_promotion_live_chain")

    assert rows["b_sellerboard_order_reconciliation"]["status"] == "warn"
    assert "api_proved_quarantine=1" in rows["b_sellerboard_order_reconciliation"]["value"]
    assert rows["b_backdate_recovery_quarantine"]["status"] == "ok"
    assert rows["b_future_marketplace_order_cursors"]["status"] == "ok"
    assert rows["b_order_promotion_preview"]["status"] == "decision_needed"
    assert rows["b_order_promotion_live_chain"]["status"] == "decision_needed"
    assert rows["b_order_truth_completion"]["status"] == "decision_needed"
    assert rows["b_management_ready_for_maintenance"]["status"] == "decision_needed"
    assert truth_item["status"] == "blocked_needs_luke"
    assert "no B run or restart" in truth_item["forbidden_actions"]
    assert promotion_item["status"] == "blocked_needs_luke"


def test_hourly_mot_marks_fresh_e_evidence_ok_without_publish_proof(tmp_path: Path) -> None:
    _write_e_manifest(tmp_path)
    _write_e_run_log(tmp_path)
    _write_e_input_proofs(tmp_path)
    _write_e_required_outputs(tmp_path)
    _write_e_coverage_summary(tmp_path)
    _write_e_health(tmp_path)

    result = build_e_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "ok"
    assert result["fail_count"] == 0
    assert rows["e_latest_manifest"]["status"] == "ok"
    assert rows["e_core_outputs_fresh"]["status"] == "ok"
    assert rows["e_cross_output_alignment"]["status"] == "ok"
    assert rows["e_optional_publish_proof"]["status"] == "not_checked"
    assert paths["hourly_mot_e_csv"].exists()


def test_hourly_mot_marks_fresh_f_evidence_ok(tmp_path: Path) -> None:
    _write_f_outputs(tmp_path)

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "ok"
    assert result["fail_count"] == 0
    assert result["warn_count"] == 0
    assert rows["f_live_owner_status"]["status"] == "ok"
    assert rows["f_storage_drift_clear"]["status"] == "ok"
    assert rows["f_source_intake_chain_proof"]["status"] == "ok"
    assert "ready_imported=1" in rows["f_source_intake_chain_proof"]["actual_proof"]
    assert rows["f_url_source_download_proof"]["status"] == "ok"
    assert "stax:ok" in rows["f_url_source_download_proof"]["actual_proof"]
    assert rows["f_email_price_list_source_proof"]["status"] == "ok"
    assert "label=ABGee" in rows["f_email_price_list_source_proof"]["actual_proof"]
    assert "source_rows=8745;valid_rows=5770" in rows["f_email_price_list_source_proof"]["actual_proof"]
    assert rows["f_bbp_account_login_state"]["status"] == "ok"
    assert rows["f_seller_central_eligibility_auth_state"]["status"] == "ok"
    assert rows["f_visible_login_control_proof"]["status"] == "ok"
    assert rows["f_queue_handoff_control_proof"]["status"] == "ok"
    assert rows["f_rescan_priority_proof"]["status"] == "ok"
    assert "policy_mode=disabled" in rows["f_rescan_priority_proof"]["actual_proof"]
    assert rows["f_recovery_progress_proof"]["status"] == "ok"
    assert rows["f_review_ai_production_readiness"]["status"] == "ok"
    assert rows["f_manager_registration_coverage"]["status"] == "ok"
    assert paths["hourly_mot_f_csv"].exists()


def test_f_live_owner_warns_when_supervisor_process_is_alive_without_row_progress(tmp_path: Path) -> None:
    _write_f_outputs(
        tmp_path,
        supervisor_state="alive_no_progress",
        supervisor_progress_state="no_row_progress",
        supervisor_scanner_progress_age_seconds="1900",
    )

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "warn"
    assert result["fail_count"] == 0
    assert rows["f_live_owner_status"]["status"] == "warn"
    assert rows["f_live_owner_status"]["value"] == "running/alive_no_progress"
    assert "scanner_progress_age_seconds=1900.0" in rows["f_live_owner_status"]["actual_proof"]


def test_f_live_owner_accepts_fresh_in_batch_heartbeat_without_row_progress(tmp_path: Path) -> None:
    _write_f_outputs(
        tmp_path,
        supervisor_state="alive_inside_batch",
        supervisor_progress_state="scanner_alive_inside_batch",
        supervisor_scanner_progress_age_seconds="1900",
    )

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["f_live_owner_status"]["status"] == "ok"
    assert rows["f_live_owner_status"]["value"] == "running/scanner_alive_inside_batch"
    assert "progress_state=scanner_alive_inside_batch" in rows["f_live_owner_status"]["actual_proof"]
    assert "scanner_progress_age_seconds=1900.0" in rows["f_live_owner_status"]["actual_proof"]


def test_f_live_owner_warns_when_old_supervisor_ok_masks_stale_scanner_events(tmp_path: Path) -> None:
    _write_f_outputs(
        tmp_path,
        supervisor_state="ok",
        supervisor_progress_state="",
        supervisor_scanner_progress_age_seconds="",
    )
    events_path = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "live_cycle_events.csv"
    _write_csv_rows(
        events_path,
        ["event_utc", "event_type", "status", "supplier_id", "rows"],
        [
            {
                "event_utc": _observed_minus(hours=2),
                "event_type": "scanner_chunk",
                "status": "success",
                "supplier_id": "td_synnex",
                "rows": "25",
            }
        ],
    )

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "warn"
    assert rows["f_live_owner_status"]["status"] == "warn"
    assert rows["f_live_owner_status"]["value"] == "running/no_recent_scanner_progress"
    assert "scanner_progress_source=events" in rows["f_live_owner_status"]["actual_proof"]


def test_f_live_owner_fails_when_active_supplier_chunks_do_not_reduce_pending_work(tmp_path: Path) -> None:
    _write_f_outputs(
        tmp_path,
        live_active_supplier_id="dhb",
        live_active_f061_run_id="fpm_dhb_fresh_test",
    )
    events_path = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "live_cycle_events.csv"
    event_rows: list[dict[str, str]] = []
    for minutes_ago, rows_processed in [(35, "1"), (28, "2"), (21, "1"), (14, "2"), (7, "1")]:
        event_time = _observed_minus(minutes=minutes_ago)
        event_rows.append(
            {
                "event_utc": event_time,
                "cycle_run_id": "fpm_live_test",
                "event_type": "scanner_chunk",
                "supplier_id": "dhb",
                "f061_run_id": "fpm_dhb_fresh_test",
                "status": "success",
                "rows": rows_processed,
                "notes": "pending_after=5489",
            }
        )
        event_rows.append(
            {
                "event_utc": event_time,
                "cycle_run_id": "fpm_live_test",
                "event_type": "f061_memory_import",
                "supplier_id": "dhb",
                "f061_run_id": "fpm_dhb_fresh_test",
                "status": "blocked",
                "rows": "1684",
                "notes": "processed_rows=1724;memory_rows=113107",
            }
        )
    _write_csv_rows(
        events_path,
        ["event_utc", "cycle_run_id", "event_type", "supplier_id", "f061_run_id", "status", "rows", "notes"],
        event_rows,
    )

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    item = next(row for row in worklist_rows if row["check"] == "f_live_owner_status")

    assert result["status"] == "fail"
    assert rows["f_live_owner_status"]["status"] == "fail"
    assert rows["f_live_owner_status"]["value"] == "running/supplier_progress_stalled"
    assert "active_supplier_id=dhb" in rows["f_live_owner_status"]["actual_proof"]
    assert "scanner_forward_state=stalled" in rows["f_live_owner_status"]["actual_proof"]
    assert "recent_scanner_chunks=5" in rows["f_live_owner_status"]["actual_proof"]
    assert "pending_drop=0" in rows["f_live_owner_status"]["actual_proof"]
    assert "memory_import_blocked_recent=5" in rows["f_live_owner_status"]["actual_proof"]
    assert item["job_ref"] == "F-SCANNER-PROGRESS"
    assert "no F061 queue edit" in item["forbidden_actions"]


def test_f_live_owner_stays_ok_when_active_supplier_pending_work_drops(tmp_path: Path) -> None:
    _write_f_outputs(
        tmp_path,
        live_active_supplier_id="dhb",
        live_active_f061_run_id="fpm_dhb_fresh_test",
    )
    events_path = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "live_cycle_events.csv"
    event_rows = []
    for minutes_ago, pending_after in [(35, "5489"), (28, "5464"), (21, "5439"), (14, "5414"), (7, "5389")]:
        event_rows.append(
            {
                "event_utc": _observed_minus(minutes=minutes_ago),
                "cycle_run_id": "fpm_live_test",
                "event_type": "scanner_chunk",
                "supplier_id": "dhb",
                "f061_run_id": "fpm_dhb_fresh_test",
                "status": "success",
                "rows": "25",
                "notes": f"pending_after={pending_after}",
            }
        )
    _write_csv_rows(
        events_path,
        ["event_utc", "cycle_run_id", "event_type", "supplier_id", "f061_run_id", "status", "rows", "notes"],
        event_rows,
    )

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["f_live_owner_status"]["status"] == "ok"
    assert "scanner_forward_state=progressing" in rows["f_live_owner_status"]["actual_proof"]
    assert "pending_drop=100" in rows["f_live_owner_status"]["actual_proof"]


def test_f_bbp_iframe_plugin_state_warns_from_child_stderr(tmp_path: Path) -> None:
    _write_f_outputs(tmp_path)
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    (live_dir / "f061_child_stderr.log").write_text(
        "2026-06-05 12:17:41,481 - INFO - F061_BBP_PROFILE_HEALTH ok=False reason=buybotpro_extension_missing\n"
        "2026-06-05 12:18:31,438 - WARNING - [Profile5] BBP iframe preflight failed after refresh => Message:\n",
        encoding="utf-8",
    )

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "warn"
    assert rows["f_bbp_iframe_plugin_state"]["status"] == "warn"
    assert rows["f_bbp_iframe_plugin_state"]["value"] == "stderr_blocked"
    assert "buybotpro_extension_missing" in rows["f_bbp_iframe_plugin_state"]["actual_proof"]


def test_f_source_shape_guard_is_classified_as_blocker_without_child_heartbeat_noise(tmp_path: Path) -> None:
    _write_f_outputs(
        tmp_path,
        live_owner_state="blocked_source_shape_guard",
        live_owner_notes="source_shape_guard:unit_cost_not_positive_numeric|count=1",
        stale_child=True,
    )

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "decision_needed"
    assert rows["f_live_owner_status"]["status"] == "decision_needed"
    assert rows["f_live_owner_status"]["value"] == "blocked_source_shape_guard"
    assert "unit_cost_not_positive_numeric" in rows["f_live_owner_status"]["root_cause_guess"]
    assert rows["f_live_owner_status"]["luke_action_required"] == "1"
    assert rows["f_child_scanner_heartbeat"]["status"] == "ok"
    assert rows["f_child_scanner_heartbeat"]["value"] == "owner_not_running"


def test_f_rescan_priority_fails_if_rescan_policy_has_cooldown(tmp_path: Path) -> None:
    _write_f_outputs(tmp_path, rescan_policy_cooldown=True)

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    item = next(row for row in worklist_rows if row["check"] == "f_rescan_priority_proof")

    assert result["status"] == "fail"
    assert rows["f_rescan_priority_proof"]["status"] == "fail"
    assert rows["f_rescan_priority_proof"]["value"] == "rescan_cooldown_enabled"
    assert "policy_mode=fixed_days" in rows["f_rescan_priority_proof"]["actual_proof"]
    assert "no queue edit" in item["safe_repair_boundary"]
    assert "no F061 run" in item["forbidden_actions"]


def test_f_rescan_priority_fails_if_live_rescan_rows_have_timeout_dates(tmp_path: Path) -> None:
    _write_f_outputs(tmp_path, parked_rescan_timeout=True)

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    item = next(row for row in worklist_rows if row["check"] == "f_rescan_priority_proof")

    assert result["status"] == "decision_needed"
    assert rows["f_rescan_priority_proof"]["status"] == "fail"
    assert rows["f_rescan_priority_proof"]["luke_action_required"] == "1"
    assert rows["f_rescan_priority_proof"]["value"] == "parked_timeout=1"
    assert "rescan_timeout_rows=1" in rows["f_rescan_priority_proof"]["actual_proof"]
    assert item["status"] == "blocked_needs_luke"
    assert "no output rewrite" in item["safe_repair_boundary"]
    assert "no worker restart" in item["forbidden_actions"]


def test_f_email_source_proof_accepts_imported_email_batch_after_local_source_refresh(tmp_path: Path) -> None:
    _write_f_outputs(tmp_path)
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    source_status_path = test_dir / "source_acquisition_status.csv"
    rows = list(csv.DictReader(source_status_path.open(newline="", encoding="utf-8")))
    for row in rows:
        if row.get("supplier_id") == "abgee":
            row["source_location"] = str(tmp_path / "price_files" / "ABGee" / "inbox")
            row["latest_source_path"] = str(tmp_path / "price_files" / "ABGee" / "inbox" / "older.xlsx")
            row["latest_source_name"] = "older.xlsx"
            row["latest_source_mtime_utc"] = _observed_minus(hours=48)
            row["notes"] = "latest_price_file_found"
    _write_csv_rows(source_status_path, list(rows[0].keys()), rows)

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    mot_rows = {row["check"]: row for row in result["rows"]}

    assert mot_rows["f_email_price_list_source_proof"]["status"] == "ok"
    assert "email_attachment_import_proven_after_local_source_refresh" in mot_rows[
        "f_email_price_list_source_proof"
    ]["actual_proof"]


def test_hourly_mot_warns_when_seller_central_eligibility_proof_missing(tmp_path: Path) -> None:
    _write_f_outputs(tmp_path)
    (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "live"
        / "seller_central_login_recovery_proof.csv"
    ).unlink()

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "warn"
    assert rows["f_bbp_account_login_state"]["status"] == "ok"
    assert rows["f_seller_central_eligibility_auth_state"]["status"] == "warn"
    assert rows["f_seller_central_eligibility_auth_state"]["value"] == "missing_proof"


def test_hourly_mot_keeps_f_owned_login_classification_out_of_luke_queue(tmp_path: Path) -> None:
    _write_f_outputs(tmp_path)
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    _write_csv_rows(
        live_dir / "seller_central_login_recovery_proof.csv",
        [
            "observed_utc",
            "context",
            "status",
            "reason",
            "seller_central_signin_detected",
            "seller_central_otp_detected",
            "requested_utc",
            "message_ts_utc",
            "code_seen_flag",
            "fresh_code_flag",
            "used_message_flag",
            "attempted_flag",
            "succeeded_flag",
            "auto_login_enabled",
            "secret_file_exists",
            "credentials_present",
            "gmail_label",
            "code_age_seconds",
            "source_message_id",
            "notes",
        ],
        [
            {
                "observed_utc": OBSERVED,
                "context": "dashboard_yes_no_login",
                "status": "blocked",
                "reason": "signin_or_passkey_page_after_credentials",
                "seller_central_signin_detected": "1",
                "seller_central_otp_detected": "0",
                "requested_utc": _observed_minus(minutes=1),
                "message_ts_utc": "",
                "code_seen_flag": "0",
                "fresh_code_flag": "0",
                "used_message_flag": "0",
                "attempted_flag": "1",
                "succeeded_flag": "0",
                "auto_login_enabled": "1",
                "secret_file_exists": "1",
                "credentials_present": "1",
                "gmail_label": "AmazonOTP",
                "code_age_seconds": "",
                "source_message_id": "",
                "notes": "post_credentials_page=sellercentral_url|signin_url|password_field|signin_button|passkey_option",
            }
        ],
    )

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "warn"
    assert rows["f_seller_central_eligibility_auth_state"]["status"] == "warn"
    assert rows["f_seller_central_eligibility_auth_state"]["value"] == "signin_or_passkey_page_after_credentials"
    assert rows["f_seller_central_eligibility_auth_state"]["luke_action_required"] == "0"


def test_hourly_mot_only_asks_luke_for_real_manual_login_challenge(tmp_path: Path) -> None:
    _write_f_outputs(tmp_path)
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    _write_csv_rows(
        live_dir / "seller_central_login_recovery_proof.csv",
        [
            "observed_utc",
            "context",
            "status",
            "reason",
            "seller_central_signin_detected",
            "seller_central_otp_detected",
            "requested_utc",
            "message_ts_utc",
            "code_seen_flag",
            "fresh_code_flag",
            "used_message_flag",
            "attempted_flag",
            "succeeded_flag",
            "auto_login_enabled",
            "secret_file_exists",
            "credentials_present",
            "gmail_label",
            "code_age_seconds",
            "source_message_id",
            "notes",
        ],
        [
            {
                "observed_utc": OBSERVED,
                "context": "dashboard_yes_no_login",
                "status": "blocked",
                "reason": "authenticator_only_no_sms_option",
                "seller_central_signin_detected": "0",
                "seller_central_otp_detected": "0",
                "requested_utc": _observed_minus(minutes=1),
                "message_ts_utc": "",
                "code_seen_flag": "0",
                "fresh_code_flag": "0",
                "used_message_flag": "0",
                "attempted_flag": "1",
                "succeeded_flag": "0",
                "auto_login_enabled": "1",
                "secret_file_exists": "1",
                "credentials_present": "1",
                "gmail_label": "AmazonOTP",
                "code_age_seconds": "",
                "source_message_id": "",
                "notes": "page_hint=authenticator_option",
            }
        ],
    )

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "decision_needed"
    assert rows["f_seller_central_eligibility_auth_state"]["status"] == "decision_needed"
    assert rows["f_seller_central_eligibility_auth_state"]["value"] == "authenticator_only_no_sms_option"
    assert rows["f_seller_central_eligibility_auth_state"]["luke_action_required"] == "1"


def test_hourly_mot_keeps_otp_intake_proof_separate_from_live_eligibility(tmp_path: Path) -> None:
    _write_f_outputs(tmp_path)
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    _write_csv_rows(
        live_dir / "seller_central_login_recovery_proof.csv",
        [
            "observed_utc",
            "context",
            "status",
            "reason",
            "seller_central_signin_detected",
            "seller_central_otp_detected",
            "requested_utc",
            "message_ts_utc",
            "code_seen_flag",
            "fresh_code_flag",
            "used_message_flag",
            "attempted_flag",
            "succeeded_flag",
            "auto_login_enabled",
            "secret_file_exists",
            "credentials_present",
            "gmail_label",
            "code_age_seconds",
            "source_message_id",
            "notes",
        ],
        [
            {
                "observed_utc": OBSERVED,
                "context": "read_only_otp_intake_proof",
                "status": "otp_intake_proved",
                "reason": "fresh_code_found",
                "seller_central_signin_detected": "0",
                "seller_central_otp_detected": "0",
                "requested_utc": _observed_minus(minutes=1),
                "message_ts_utc": _observed_minus(minutes=1),
                "code_seen_flag": "1",
                "fresh_code_flag": "1",
                "used_message_flag": "0",
                "attempted_flag": "0",
                "succeeded_flag": "0",
                "auto_login_enabled": "0",
                "secret_file_exists": "1",
                "credentials_present": "1",
                "gmail_label": "AmazonOTP",
                "code_age_seconds": "5.00",
                "source_message_id": "msg-1",
                "notes": "redacted_test_proof",
            }
        ],
    )

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "warn"
    assert rows["f_seller_central_eligibility_auth_state"]["status"] == "warn"
    assert rows["f_seller_central_eligibility_auth_state"]["value"] == "otp_intake_visible_not_live_proved"


def test_hourly_mot_classifies_o_midbuild_without_calling_missing_future_work_a_fail(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "ok"
    assert rows["o_mid_build_stage_map"]["status"] == "ok"
    assert "not_started=2" in rows["o_mid_build_stage_map"]["value"]
    assert rows["o_active_restock_proof_files"]["status"] == "ok"
    assert rows["o_restock_session_readiness"]["status"] == "ok"
    assert rows["o_buy_ready_guardrails"]["value"] == "no_action_ready"
    assert rows["o_legacy_bridge_source_labels"]["status"] == "ok"
    assert rows["o_po_draft_source_separation"]["status"] == "ok"
    assert "proof_only" in rows["o_po_draft_source_separation"]["value"]
    assert rows["o_receiving_send_safety"]["status"] == "ok"
    assert rows["o_real_po_readiness_gate"]["status"] == "ok"
    assert rows["o_real_po_readiness_gate"]["value"].startswith("closed;")
    assert rows["o_real_po_gate_clearance_worklist"]["status"] == "ok"
    assert "refund_inbound=1" in rows["o_real_po_gate_clearance_worklist"]["value"]
    assert "approval_po_gates=1" in rows["o_real_po_gate_clearance_worklist"]["value"]
    assert rows["o_supplier_file_evidence_visibility"]["status"] == "ok"
    assert "review_rows=1" in rows["o_supplier_file_evidence_visibility"]["value"]
    assert "probe_rows=0" in rows["o_supplier_file_evidence_visibility"]["value"]
    assert rows["o_supplier_file_proof_coverage_map"]["status"] == "ok"
    assert "review_rows=1" in rows["o_supplier_file_proof_coverage_map"]["value"]
    assert "covered=0" in rows["o_supplier_file_proof_coverage_map"]["value"]
    assert "uncovered=1" in rows["o_supplier_file_proof_coverage_map"]["value"]
    assert rows["o_supplier_proof_work_queue"]["status"] == "ok"
    assert "uncovered=1" in rows["o_supplier_proof_work_queue"]["value"]
    assert "supplier_groups=1" in rows["o_supplier_proof_work_queue"]["value"]
    assert rows["o_supplier_proof_queue_filter"]["status"] == "ok"
    assert "uncovered=1" in rows["o_supplier_proof_queue_filter"]["value"]
    assert "options=5" in rows["o_supplier_proof_queue_filter"]["value"]
    assert rows["o_supplier_proof_action_workbench"]["status"] == "ok"
    assert "rows=1" in rows["o_supplier_proof_action_workbench"]["value"]
    assert "exact_match=1" in rows["o_supplier_proof_action_workbench"]["value"]
    assert rows["o_supplier_proof_field_focus_filter"]["status"] == "ok"
    assert "options=" in rows["o_supplier_proof_field_focus_filter"]["value"]
    assert "rows=1" in rows["o_supplier_proof_field_focus_filter"]["value"]
    assert rows["o_real_po_supplier_gate_clearance"]["status"] == "ok"
    assert "stock=1" in rows["o_real_po_supplier_gate_clearance"]["value"]
    assert "cost=1" in rows["o_real_po_supplier_gate_clearance"]["value"]
    assert "both=1" in rows["o_real_po_supplier_gate_clearance"]["value"]
    assert rows["o_completion_claim_guard"]["status"] == "ok"
    assert rows["o_h_maintenance_controller_gate"]["status"] == "not_checked"
    assert rows["o_h_market_proof_gate"]["status"] == "ok"
    assert rows["o_user_working_readiness"]["status"] == "ok"
    assert rows["o_user_working_readiness"]["value"].startswith("ready_for_user_work")
    assert paths["hourly_mot_o_csv"].exists()


def test_o_supplier_file_evidence_visibility_counts_probe_states(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_supplier_file_presence_probe_live.csv",
        [
            "probe_utc",
            "probe_id",
            "row_id",
            "seller_sku",
            "latest_supplier_file_name",
            "latest_supplier_file_state",
            "identity_match_state",
            "matched_row_count",
            "searched_row_count",
            "probe_explanation",
            "clears_supplier_proof",
            "purchase_approval_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "creates_live_action",
            "read_error",
        ],
        [
            {
                "probe_utc": OBSERVED,
                "probe_id": "probe-exact",
                "row_id": "row-exact",
                "seller_sku": "SKU-EXACT",
                "latest_supplier_file_name": "supplier_file.xlsx",
                "latest_supplier_file_state": "latest_local_supplier_file_checked",
                "identity_match_state": "exact_supplier_sku_or_barcode_found",
                "matched_row_count": "1",
                "searched_row_count": "10",
                "probe_explanation": "Exact supplier SKU/barcode found.",
                "clears_supplier_proof": "0",
                "purchase_approval_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "creates_live_action": "0",
                "read_error": "",
            },
            {
                "probe_utc": OBSERVED,
                "probe_id": "probe-missing",
                "row_id": "row-missing",
                "seller_sku": "SKU-MISSING",
                "latest_supplier_file_name": "supplier_file.xlsx",
                "latest_supplier_file_state": "latest_local_supplier_file_checked",
                "identity_match_state": "not_found_in_latest_local_supplier_file",
                "matched_row_count": "0",
                "searched_row_count": "10",
                "probe_explanation": "Exact supplier SKU/barcode not found.",
                "clears_supplier_proof": "0",
                "purchase_approval_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "creates_live_action": "0",
                "read_error": "",
            },
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["o_supplier_file_evidence_visibility"]["status"] == "ok"
    assert "probe_rows=2" in rows["o_supplier_file_evidence_visibility"]["value"]
    assert "files_checked=2" in rows["o_supplier_file_evidence_visibility"]["value"]
    assert "exact=1" in rows["o_supplier_file_evidence_visibility"]["value"]
    assert "not_found=1" in rows["o_supplier_file_evidence_visibility"]["value"]
    assert rows["o_user_working_readiness"]["status"] == "ok"


def test_o_supplier_file_evidence_visibility_fails_unsafe_probe_flag(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_supplier_file_presence_probe_live.csv",
        [
            "probe_utc",
            "probe_id",
            "row_id",
            "seller_sku",
            "latest_supplier_file_name",
            "latest_supplier_file_state",
            "identity_match_state",
            "matched_row_count",
            "searched_row_count",
            "probe_explanation",
            "clears_supplier_proof",
            "purchase_approval_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "creates_live_action",
            "read_error",
        ],
        [
            {
                "probe_utc": OBSERVED,
                "probe_id": "probe-unsafe",
                "row_id": "row-unsafe",
                "seller_sku": "SKU-UNSAFE",
                "latest_supplier_file_name": "supplier_file.xlsx",
                "latest_supplier_file_state": "latest_local_supplier_file_checked",
                "identity_match_state": "exact_supplier_sku_or_barcode_found",
                "matched_row_count": "1",
                "searched_row_count": "10",
                "probe_explanation": "Exact supplier SKU/barcode found.",
                "clears_supplier_proof": "1",
                "purchase_approval_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "creates_live_action": "0",
                "read_error": "",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["o_supplier_file_evidence_visibility"]["status"] == "fail"
    assert rows["o_supplier_file_evidence_visibility"]["value"] == "unsafe_rows=1"
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_supplier_file_proof_coverage_map_counts_covered_and_uncovered_rows(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_session_review_live.csv",
        [
            "session_utc",
            "session_id",
            "row_id",
            "source_class",
            "source_system",
            "source_reference",
            "supplier_name",
            "supplier_code",
            "seller_sku",
            "asin",
            "row_status",
            "action_safety_state",
            "action_block_reason",
            "operator_decision_state",
        ],
        [
            {
                "session_utc": OBSERVED,
                "session_id": "o_restock_session_v1",
                "row_id": "row-covered-exact",
                "source_class": "native_o",
                "source_system": "native_o",
                "source_reference": "native_o:SKU-EXACT",
                "supplier_name": "Supplier A",
                "supplier_code": "SUP-A",
                "seller_sku": "SKU-EXACT",
                "asin": "ASIN-EXACT",
                "row_status": "blocked",
                "action_safety_state": "blocked_from_clean_buy",
                "action_block_reason": "supplier:missing_supplier_match",
                "operator_decision_state": "proof_missing",
            },
            {
                "session_utc": OBSERVED,
                "session_id": "o_restock_session_v1",
                "row_id": "row-covered-missing",
                "source_class": "native_o",
                "source_system": "native_o",
                "source_reference": "native_o:SKU-MISSING",
                "supplier_name": "Supplier B",
                "supplier_code": "SUP-B",
                "seller_sku": "SKU-MISSING",
                "asin": "ASIN-MISSING",
                "row_status": "blocked",
                "action_safety_state": "blocked_from_clean_buy",
                "action_block_reason": "supplier:missing_supplier_match",
                "operator_decision_state": "proof_missing",
            },
            {
                "session_utc": OBSERVED,
                "session_id": "o_restock_session_v1",
                "row_id": "row-uncovered",
                "source_class": "native_o",
                "source_system": "native_o",
                "source_reference": "native_o:SKU-UNCOVERED",
                "supplier_name": "Supplier B",
                "supplier_code": "SUP-B",
                "seller_sku": "SKU-UNCOVERED",
                "asin": "ASIN-UNCOVERED",
                "row_status": "blocked",
                "action_safety_state": "blocked_from_clean_buy",
                "action_block_reason": "supplier:missing_supplier_match",
                "operator_decision_state": "proof_missing",
            },
        ],
    )
    _write_csv_rows(
        live / "restock_supplier_file_presence_probe_live.csv",
        [
            "probe_utc",
            "probe_id",
            "row_id",
            "seller_sku",
            "identity_match_state",
            "matched_row_count",
            "probe_explanation",
            "clears_supplier_proof",
            "purchase_approval_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "creates_live_action",
        ],
        [
            {
                "probe_utc": OBSERVED,
                "probe_id": "probe-exact",
                "row_id": "row-covered-exact",
                "seller_sku": "SKU-EXACT",
                "identity_match_state": "exact_supplier_sku_or_barcode_found",
                "matched_row_count": "1",
                "probe_explanation": "Exact supplier SKU/barcode found.",
                "clears_supplier_proof": "0",
                "purchase_approval_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "creates_live_action": "0",
            },
            {
                "probe_utc": OBSERVED,
                "probe_id": "probe-missing",
                "row_id": "row-covered-missing",
                "seller_sku": "SKU-MISSING",
                "identity_match_state": "not_found_in_latest_local_supplier_file",
                "matched_row_count": "0",
                "probe_explanation": "Exact supplier SKU/barcode not found.",
                "clears_supplier_proof": "0",
                "purchase_approval_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "creates_live_action": "0",
            },
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["o_supplier_file_proof_coverage_map"]["status"] == "ok"
    assert rows["o_supplier_file_proof_coverage_map"]["value"] == (
        "review_rows=3;covered=2;uncovered=1;suppliers=2;covered_suppliers=2;exact=1;not_found=1"
    )
    assert "top_uncovered=Supplier B:1" in rows["o_supplier_file_proof_coverage_map"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "ok"


def test_o_supplier_file_proof_coverage_map_fails_unsafe_probe_flag(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_supplier_file_presence_probe_live.csv",
        [
            "probe_utc",
            "probe_id",
            "row_id",
            "seller_sku",
            "identity_match_state",
            "matched_row_count",
            "probe_explanation",
            "clears_supplier_proof",
            "purchase_approval_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "creates_live_action",
        ],
        [
            {
                "probe_utc": OBSERVED,
                "probe_id": "probe-unsafe",
                "row_id": "o_restock_session_v1:supplier:sku1",
                "seller_sku": "SKU1",
                "identity_match_state": "exact_supplier_sku_or_barcode_found",
                "matched_row_count": "1",
                "probe_explanation": "Exact supplier SKU/barcode found.",
                "clears_supplier_proof": "0",
                "purchase_approval_allowed": "0",
                "po_creation_allowed": "1",
                "purchase_commitment_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["o_supplier_file_proof_coverage_map"]["status"] == "fail"
    assert rows["o_supplier_file_proof_coverage_map"]["value"] == "unsafe_rows=1"
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_supplier_proof_work_queue_groups_uncovered_rows(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_session_review_live.csv",
        [
            "session_utc",
            "session_id",
            "row_id",
            "source_class",
            "source_system",
            "source_reference",
            "supplier_name",
            "supplier_code",
            "seller_sku",
            "asin",
            "row_status",
            "action_safety_state",
            "action_block_reason",
            "operator_decision_state",
            "supplier_stock_state",
            "supplier_match_state",
            "supplier_cost_proof_state",
        ],
        [
            {
                "session_utc": OBSERVED,
                "session_id": "o_restock_session_v1",
                "row_id": "row-a1",
                "source_class": "native_o",
                "source_system": "native_o",
                "source_reference": "native_o:SKU-A1",
                "supplier_name": "Supplier A",
                "supplier_code": "SUP-A",
                "seller_sku": "SKU-A1",
                "asin": "ASIN-A1",
                "row_status": "blocked",
                "action_safety_state": "blocked_from_clean_buy",
                "action_block_reason": "supplier:missing_supplier_match",
                "operator_decision_state": "proof_missing",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "supplier_cost_proof_state": "missing_supplier_cost",
            },
            {
                "session_utc": OBSERVED,
                "session_id": "o_restock_session_v1",
                "row_id": "row-a2",
                "source_class": "native_o",
                "source_system": "native_o",
                "source_reference": "native_o:SKU-A2",
                "supplier_name": "Supplier A",
                "supplier_code": "SUP-A",
                "seller_sku": "SKU-A2",
                "asin": "ASIN-A2",
                "row_status": "blocked",
                "action_safety_state": "blocked_from_clean_buy",
                "action_block_reason": "supplier:missing_supplier_match",
                "operator_decision_state": "proof_missing",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "supplier_cost_proof_state": "missing_supplier_cost",
            },
            {
                "session_utc": OBSERVED,
                "session_id": "o_restock_session_v1",
                "row_id": "row-b1",
                "source_class": "native_o",
                "source_system": "native_o",
                "source_reference": "native_o:SKU-B1",
                "supplier_name": "Supplier B",
                "supplier_code": "SUP-B",
                "seller_sku": "SKU-B1",
                "asin": "ASIN-B1",
                "row_status": "blocked",
                "action_safety_state": "blocked_from_clean_buy",
                "action_block_reason": "supplier:likely_discontinued_candidate",
                "operator_decision_state": "proof_missing",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "supplier_cost_proof_state": "missing_supplier_cost",
            },
            {
                "session_utc": OBSERVED,
                "session_id": "o_restock_session_v1",
                "row_id": "row-covered",
                "source_class": "native_o",
                "source_system": "native_o",
                "source_reference": "native_o:SKU-COVERED",
                "supplier_name": "Supplier C",
                "supplier_code": "SUP-C",
                "seller_sku": "SKU-COVERED",
                "asin": "ASIN-COVERED",
                "row_status": "blocked",
                "action_safety_state": "blocked_from_clean_buy",
                "action_block_reason": "supplier:missing_supplier_match",
                "operator_decision_state": "proof_missing",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "supplier_cost_proof_state": "missing_supplier_cost",
            },
        ],
    )
    _write_csv_rows(
        live / "restock_supplier_file_presence_probe_live.csv",
        [
            "probe_utc",
            "probe_id",
            "row_id",
            "seller_sku",
            "identity_match_state",
            "matched_row_count",
            "probe_explanation",
            "clears_supplier_proof",
            "purchase_approval_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "creates_live_action",
        ],
        [
            {
                "probe_utc": OBSERVED,
                "probe_id": "probe-covered",
                "row_id": "row-covered",
                "seller_sku": "SKU-COVERED",
                "identity_match_state": "not_found_in_latest_local_supplier_file",
                "matched_row_count": "0",
                "probe_explanation": "Exact supplier SKU/barcode not found.",
                "clears_supplier_proof": "0",
                "purchase_approval_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["o_supplier_proof_work_queue"]["status"] == "ok"
    assert "uncovered=3" in rows["o_supplier_proof_work_queue"]["value"]
    assert "supplier_groups=2" in rows["o_supplier_proof_work_queue"]["value"]
    assert "top_supplier=Supplier A" in rows["o_supplier_proof_work_queue"]["value"]
    assert "top_supplier_rows=2" in rows["o_supplier_proof_work_queue"]["value"]
    assert "top_action=supplier_proof" in rows["o_supplier_proof_work_queue"]["value"]
    assert "top_action_rows=2" in rows["o_supplier_proof_work_queue"]["value"]
    assert "top_supplier_action=supplier_proof" in rows["o_supplier_proof_work_queue"]["actual_proof"]
    assert rows["o_supplier_proof_queue_filter"]["status"] == "ok"
    assert "options=5" in rows["o_supplier_proof_queue_filter"]["value"]
    assert "top_supplier=Supplier A" in rows["o_supplier_proof_queue_filter"]["value"]
    assert "top_supplier_rows=2" in rows["o_supplier_proof_queue_filter"]["value"]
    assert "top_action=supplier_proof" in rows["o_supplier_proof_queue_filter"]["value"]
    assert "top_action_rows=2" in rows["o_supplier_proof_queue_filter"]["value"]
    assert "top_supplier_action=supplier_proof" in rows["o_supplier_proof_queue_filter"]["value"]
    assert rows["o_supplier_proof_action_workbench"]["status"] == "ok"
    assert "rows=3" in rows["o_supplier_proof_action_workbench"]["value"]
    assert "exact_match=3" in rows["o_supplier_proof_action_workbench"]["value"]
    assert "stock_backorder=3" in rows["o_supplier_proof_action_workbench"]["value"]
    assert "cost=3" in rows["o_supplier_proof_action_workbench"]["value"]
    assert "file_ref=3" in rows["o_supplier_proof_action_workbench"]["value"]
    assert "drop_or_check_later=1" in rows["o_supplier_proof_action_workbench"]["value"]
    assert rows["o_supplier_proof_field_focus_filter"]["status"] == "ok"
    assert "options=6" in rows["o_supplier_proof_field_focus_filter"]["value"]
    assert "rows=3" in rows["o_supplier_proof_field_focus_filter"]["value"]
    assert "drop_or_check_later=1" in rows["o_supplier_proof_field_focus_filter"]["value"]
    assert rows["o_user_working_readiness"]["status"] == "ok"


def test_o_supplier_proof_action_workbench_counts_field_lanes(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_session_review_live.csv",
        [
            "session_utc",
            "session_id",
            "row_id",
            "source_class",
            "source_system",
            "source_reference",
            "supplier_name",
            "supplier_code",
            "seller_sku",
            "asin",
            "row_status",
            "action_safety_state",
            "action_block_reason",
            "operator_decision_state",
            "supplier_stock_state",
            "supplier_match_state",
            "backorder_state",
            "supplier_cost_proof_state",
            "current_supplier_cost_gbp",
            "supplier_file_asof_utc",
            "supplier_file_reference",
        ],
        [
            {
                "session_utc": OBSERVED,
                "session_id": "o_restock_session_v1",
                "row_id": "row-a1",
                "source_class": "native_o",
                "source_system": "native_o",
                "source_reference": "native_o:SKU-A1",
                "supplier_name": "Supplier A",
                "supplier_code": "SUP-A",
                "seller_sku": "SKU-A1",
                "asin": "ASIN-A1",
                "row_status": "blocked",
                "action_safety_state": "blocked_from_clean_buy",
                "action_block_reason": "supplier:missing_supplier_match",
                "operator_decision_state": "proof_missing",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "backorder_state": "backorder_not_verified",
                "supplier_cost_proof_state": "missing_supplier_cost",
                "current_supplier_cost_gbp": "",
                "supplier_file_asof_utc": "",
                "supplier_file_reference": "",
            },
            {
                "session_utc": OBSERVED,
                "session_id": "o_restock_session_v1",
                "row_id": "row-b1",
                "source_class": "native_o",
                "source_system": "native_o",
                "source_reference": "native_o:SKU-B1",
                "supplier_name": "Supplier B",
                "supplier_code": "SUP-B",
                "seller_sku": "SKU-B1",
                "asin": "ASIN-B1",
                "row_status": "blocked",
                "action_safety_state": "blocked_from_clean_buy",
                "action_block_reason": "supplier:likely_discontinued_candidate|missing_from_latest_supplier_file",
                "operator_decision_state": "proof_missing",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "backorder_state": "backorder_not_verified",
                "supplier_cost_proof_state": "missing_supplier_cost",
                "current_supplier_cost_gbp": "",
                "supplier_file_asof_utc": "",
                "supplier_file_reference": "",
            },
        ],
    )
    _write_csv_rows(
        live / "restock_supplier_file_presence_probe_live.csv",
        [
            "probe_utc",
            "probe_id",
            "row_id",
            "seller_sku",
            "identity_match_state",
            "matched_row_count",
            "probe_explanation",
            "clears_supplier_proof",
            "purchase_approval_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "creates_live_action",
        ],
        [],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["o_supplier_proof_action_workbench"]["status"] == "ok"
    assert rows["o_supplier_proof_action_workbench"]["value"] == (
        "rows=2;exact_match=2;stock_backorder=2;cost=2;file_ref=2;drop_or_check_later=1;top_field=cost;top_field_rows=2"
    )
    assert rows["o_supplier_proof_field_focus_filter"]["status"] == "ok"
    assert rows["o_supplier_proof_field_focus_filter"]["value"] == (
        "options=6;rows=2;exact_match=2;stock_backorder=2;cost=2;file_ref=2;drop_or_check_later=1;top_field=cost;top_field_rows=2"
    )
    assert rows["o_user_working_readiness"]["status"] == "ok"


def test_o_supplier_proof_field_focus_filter_counts_options(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["o_supplier_proof_field_focus_filter"]["status"] == "ok"
    assert "options=5" in rows["o_supplier_proof_field_focus_filter"]["value"]
    assert "rows=1" in rows["o_supplier_proof_field_focus_filter"]["value"]
    assert "exact_match=1" in rows["o_supplier_proof_field_focus_filter"]["value"]
    assert rows["o_user_working_readiness"]["status"] == "ok"


def test_o_supplier_proof_work_queue_fails_unsafe_probe_flag(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_supplier_file_presence_probe_live.csv",
        [
            "probe_utc",
            "probe_id",
            "row_id",
            "seller_sku",
            "identity_match_state",
            "matched_row_count",
            "probe_explanation",
            "clears_supplier_proof",
            "purchase_approval_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "creates_live_action",
        ],
        [
            {
                "probe_utc": OBSERVED,
                "probe_id": "probe-unsafe",
                "row_id": "o_restock_session_v1:supplier:sku1",
                "seller_sku": "SKU1",
                "identity_match_state": "exact_supplier_sku_or_barcode_found",
                "matched_row_count": "1",
                "probe_explanation": "Exact supplier SKU/barcode found.",
                "clears_supplier_proof": "0",
                "purchase_approval_allowed": "0",
                "po_creation_allowed": "1",
                "purchase_commitment_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["o_supplier_proof_work_queue"]["status"] == "fail"
    assert rows["o_supplier_proof_work_queue"]["value"] == "unsafe_rows=1"
    assert rows["o_supplier_proof_queue_filter"]["status"] == "fail"
    assert rows["o_supplier_proof_queue_filter"]["value"] == "unsafe_rows=1"
    assert rows["o_supplier_proof_action_workbench"]["status"] == "fail"
    assert rows["o_supplier_proof_action_workbench"]["value"] == "unsafe_rows=1"
    assert rows["o_supplier_proof_field_focus_filter"]["status"] == "fail"
    assert rows["o_supplier_proof_field_focus_filter"]["value"] == "unsafe_rows=1"
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_supplier_proof_action_workbench_fails_unsafe_probe_flag(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_supplier_file_presence_probe_live.csv",
        [
            "probe_utc",
            "probe_id",
            "row_id",
            "seller_sku",
            "identity_match_state",
            "matched_row_count",
            "probe_explanation",
            "clears_supplier_proof",
            "purchase_approval_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "creates_live_action",
        ],
        [
            {
                "probe_utc": OBSERVED,
                "probe_id": "probe-unsafe",
                "row_id": "o_restock_session_v1:supplier:sku1",
                "seller_sku": "SKU1",
                "identity_match_state": "exact_supplier_sku_or_barcode_found",
                "matched_row_count": "1",
                "probe_explanation": "Exact supplier SKU/barcode found.",
                "clears_supplier_proof": "1",
                "purchase_approval_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["o_supplier_proof_action_workbench"]["status"] == "fail"
    assert rows["o_supplier_proof_action_workbench"]["value"] == "unsafe_rows=1"
    assert rows["o_supplier_proof_field_focus_filter"]["status"] == "fail"
    assert rows["o_supplier_proof_field_focus_filter"]["value"] == "unsafe_rows=1"
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_real_po_supplier_gate_clearance_counts_stock_and_cost_lanes(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_session_review_live.csv",
        [
            "session_utc",
            "session_id",
            "row_id",
            "source_class",
            "source_system",
            "source_reference",
            "supplier_name",
            "supplier_code",
            "seller_sku",
            "asin",
            "row_status",
            "action_safety_state",
            "action_block_reason",
            "operator_decision_state",
            "supplier_stock_state",
            "supplier_match_state",
            "backorder_state",
            "supplier_file_asof_utc",
            "supplier_cost_proof_state",
            "current_supplier_cost_gbp",
        ],
        [
            {
                "session_utc": OBSERVED,
                "session_id": "o_restock_session_v1",
                "row_id": "row-both",
                "source_class": "native_o",
                "source_system": "native_o",
                "source_reference": "native_o:SKU-BOTH",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "seller_sku": "SKU-BOTH",
                "asin": "ASIN-BOTH",
                "row_status": "blocked",
                "action_safety_state": "blocked_from_clean_buy",
                "action_block_reason": "supplier:missing_supplier_match|supplier_cost:missing_supplier_cost",
                "operator_decision_state": "proof_missing",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "backorder_state": "backorder_not_verified",
                "supplier_file_asof_utc": "",
                "supplier_cost_proof_state": "missing_supplier_cost",
                "current_supplier_cost_gbp": "",
            },
            {
                "session_utc": OBSERVED,
                "session_id": "o_restock_session_v1",
                "row_id": "row-stock",
                "source_class": "native_o",
                "source_system": "native_o",
                "source_reference": "native_o:SKU-STOCK",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "seller_sku": "SKU-STOCK",
                "asin": "ASIN-STOCK",
                "row_status": "blocked",
                "action_safety_state": "blocked_from_clean_buy",
                "action_block_reason": "supplier:likely_discontinued_candidate",
                "operator_decision_state": "proof_missing",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "backorder_state": "backorder_not_verified",
                "supplier_file_asof_utc": "",
                "supplier_cost_proof_state": "supplier_cost_verified",
                "current_supplier_cost_gbp": "2.00",
            },
            {
                "session_utc": OBSERVED,
                "session_id": "o_restock_session_v1",
                "row_id": "row-cost",
                "source_class": "native_o",
                "source_system": "native_o",
                "source_reference": "native_o:SKU-COST",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "seller_sku": "SKU-COST",
                "asin": "ASIN-COST",
                "row_status": "blocked",
                "action_safety_state": "blocked_from_clean_buy",
                "action_block_reason": "supplier_cost:missing_supplier_cost",
                "operator_decision_state": "proof_missing",
                "supplier_stock_state": "supplier_stock_verified_in_stock",
                "supplier_match_state": "supplier_match_verified",
                "backorder_state": "backorder_not_needed",
                "supplier_file_asof_utc": OBSERVED,
                "supplier_cost_proof_state": "missing_supplier_cost",
                "current_supplier_cost_gbp": "",
            },
            {
                "session_utc": OBSERVED,
                "session_id": "o_restock_session_v1",
                "row_id": "row-clear",
                "source_class": "native_o",
                "source_system": "native_o",
                "source_reference": "native_o:SKU-CLEAR",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "seller_sku": "SKU-CLEAR",
                "asin": "ASIN-CLEAR",
                "row_status": "blocked",
                "action_safety_state": "blocked_from_clean_buy",
                "action_block_reason": "refund:missing_refund_confidence",
                "operator_decision_state": "proof_missing",
                "supplier_stock_state": "supplier_stock_verified_in_stock",
                "supplier_match_state": "supplier_match_verified",
                "backorder_state": "backorder_not_needed",
                "supplier_file_asof_utc": OBSERVED,
                "supplier_cost_proof_state": "supplier_cost_verified",
                "current_supplier_cost_gbp": "2.00",
            },
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["o_real_po_supplier_gate_clearance"]["status"] == "ok"
    assert rows["o_real_po_supplier_gate_clearance"]["value"] == "stock=2;cost=2;both=1;stock_only=1;cost_only=1;supplier_clear=1"
    assert "SKU-BOTH" in rows["o_real_po_supplier_gate_clearance"]["actual_proof"]
    assert "SKU-STOCK" in rows["o_real_po_supplier_gate_clearance"]["actual_proof"]
    assert "SKU-COST" in rows["o_real_po_supplier_gate_clearance"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "ok"


def test_o_real_po_readiness_gate_fails_unsafe_po_creation_flag(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_po_draft_export_gate_live.csv",
        [
            "gate_utc",
            "po_draft_export_gate_id",
            "po_draft_export_preview_id",
            "source_export_preview_state",
            "export_gate_state",
            "export_gate_reasons",
            "line_count",
            "ready_line_count",
            "blocked_line_count",
            "po_file_write_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "receiving_allowed",
            "send_to_amazon_allowed",
            "creates_live_action",
        ],
        [
            {
                "gate_utc": OBSERVED,
                "po_draft_export_gate_id": "gate-1",
                "po_draft_export_preview_id": "export-1",
                "source_export_preview_state": "ready_for_local_po_draft_export_preview_only",
                "export_gate_state": "local_export_candidate_ready_not_po",
                "export_gate_reasons": "",
                "line_count": "1",
                "ready_line_count": "1",
                "blocked_line_count": "0",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "1",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_real_po_readiness_gate"]["status"] == "fail"
    assert rows["o_real_po_readiness_gate"]["value"] == "unsafe_action_flags=1"
    assert "po_creation_allowed" in rows["o_real_po_readiness_gate"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_user_working_readiness_tolerates_stale_midbuild_proof_warning(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    for _name, rel_path, _stage, _min_rows in O_ACTIVE_PROOF_OUTPUTS:
        _set_age(tmp_path / rel_path, 200.0)

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "warn"
    assert rows["o_active_restock_proof_files"]["status"] == "warn"
    assert "restock_recommendations_live:built" in rows["o_active_restock_proof_files"]["actual_proof"]
    assert "legacy_purchase_list_bridge:bridge" in rows["o_active_restock_proof_files"]["actual_proof"]
    assert "local_refresh_candidates=restock_source_view,restock_recommendations_live,restock_review_queue,reorder_input_coverage_report" in rows["o_active_restock_proof_files"]["manager_action"]
    assert "bridge_stale_labelled=legacy_purchase_list_bridge,legacy_purchase_list_bridge_health,restock_market_refresh_candidates_live" in rows["o_active_restock_proof_files"]["manager_action"]
    assert rows["o_user_working_readiness"]["status"] == "ok"
    assert rows["o_user_working_readiness"]["value"].startswith("ready_for_user_work")
    assert "o_active_restock_proof_files:warn" in rows["o_user_working_readiness"]["actual_proof"]
    assert "safety_blockers=;" in rows["o_user_working_readiness"]["actual_proof"]


def test_o_restock_session_readiness_fails_unsafe_draft_decision_event(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_session_draft_decision_events.csv",
        [
            "event_utc",
            "draft_id",
            "session_id",
            "row_id",
            "seller_sku",
            "asin",
            "supplier_name",
            "supplier_code",
            "source_class",
            "row_source_reference",
            "decision_code",
            "draft_order_qty",
            "snooze_until_utc",
            "decision_note",
            "actor",
            "event_source_reference",
            "draft_status",
            "creates_live_action",
        ],
        [
            {
                "event_utc": OBSERVED,
                "draft_id": "draft-1",
                "session_id": "o_restock_session_v1",
                "row_id": "o_restock_session_v1:supplier:sku1",
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "row_source_reference": "native_o:SKU1",
                "decision_code": "order_qty_draft",
                "draft_order_qty": "1",
                "snooze_until_utc": "",
                "decision_note": "unsafe test",
                "actor": "operator_ui",
                "event_source_reference": "test",
                "draft_status": "draft",
                "creates_live_action": "1",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_restock_session_readiness"]["status"] == "fail"
    assert rows["o_restock_session_readiness"]["value"] == "bad_draft_rows=1"
    assert "creates_live_action" in rows["o_restock_session_readiness"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_supplier_batch_drafts_fail_unsafe_live_action_row(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_session_supplier_batch_lines_live.csv",
        [
            "batch_utc",
            "batch_id",
            "session_id",
            "row_id",
            "draft_id",
            "draft_event_utc",
            "supplier_name",
            "supplier_code",
            "source_class",
            "seller_sku",
            "asin",
            "title",
            "supplier_sku",
            "barcode",
            "draft_order_qty",
            "current_supplier_cost_gbp",
            "draft_line_value_gbp",
            "supplier_order_viability_state",
            "action_safety_state",
            "action_block_reason",
            "line_state",
            "creates_live_action",
        ],
        [
            {
                "batch_utc": OBSERVED,
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "o_restock_session_v1:supplier:sku1",
                "draft_id": "draft-1",
                "draft_event_utc": OBSERVED,
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "title": "Product",
                "supplier_sku": "SUP1",
                "barcode": "123",
                "draft_order_qty": "2",
                "current_supplier_cost_gbp": "3",
                "draft_line_value_gbp": "6",
                "supplier_order_viability_state": "review_only_not_po",
                "action_safety_state": "blocked_from_clean_buy",
                "action_block_reason": "refund:missing_refund_confidence",
                "line_state": "review_only_blocked",
                "creates_live_action": "1",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_restock_supplier_batch_drafts"]["status"] == "fail"
    assert "live_action_rows=1" in rows["o_restock_supplier_batch_drafts"]["value"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_supplier_batch_drafts_fail_false_supplier_proof_clear_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_session_supplier_batch_lines_live.csv",
        [
            "batch_utc",
            "batch_id",
            "session_id",
            "row_id",
            "draft_id",
            "draft_event_utc",
            "supplier_name",
            "supplier_code",
            "source_class",
            "seller_sku",
            "asin",
            "title",
            "supplier_sku",
            "barcode",
            "draft_order_qty",
            "current_supplier_cost_gbp",
            "draft_line_value_gbp",
            "supplier_order_viability_state",
            "action_safety_state",
            "action_block_reason",
            "line_state",
            "creates_live_action",
            "supplier_proof_checklist_status",
            "supplier_proof_missing_reasons",
            "supplier_match_state",
            "supplier_proof_state",
            "supplier_stock_state",
            "backorder_state",
            "supplier_file_asof_utc",
            "supplier_cost_proof_state",
            "pack_moq_proof_state",
        ],
        [
            {
                "batch_utc": OBSERVED,
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "o_restock_session_v1:supplier:sku1",
                "draft_id": "draft-1",
                "draft_event_utc": OBSERVED,
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "title": "Product",
                "supplier_sku": "SUP1",
                "barcode": "123",
                "draft_order_qty": "2",
                "current_supplier_cost_gbp": "3",
                "draft_line_value_gbp": "6",
                "supplier_order_viability_state": "review_only_not_po",
                "action_safety_state": "blocked_from_clean_buy",
                "action_block_reason": "refund:missing_refund_confidence",
                "line_state": "review_only_blocked",
                "creates_live_action": "0",
                "supplier_proof_checklist_status": "supplier_proof_clear",
                "supplier_proof_missing_reasons": "",
                "supplier_match_state": "not_verified",
                "supplier_proof_state": "not_verified",
                "supplier_stock_state": "supplier_stock_not_verified",
                "backorder_state": "backorder_not_verified",
                "supplier_file_asof_utc": "",
                "supplier_cost_proof_state": "missing_supplier_cost",
                "pack_moq_proof_state": "pack_moq_not_verified",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_restock_supplier_batch_drafts"]["status"] == "fail"
    assert rows["o_restock_supplier_batch_drafts"]["value"] == "bad_supplier_clear_rows=1;missing_supplier_reason_rows=0"
    assert "bad_supplier_clear_rows=o_restock_session_v1:supplier:sku1" in rows["o_restock_supplier_batch_drafts"]["actual_proof"]


def test_o_supplier_batch_drafts_fail_unsafe_supplier_proof_event(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_session_supplier_proof_events.csv",
        [
            "event_utc",
            "proof_id",
            "session_id",
            "row_id",
            "seller_sku",
            "asin",
            "supplier_name",
            "supplier_code",
            "source_class",
            "row_source_reference",
            "supplier_stock_state",
            "supplier_stock_qty",
            "backorder_state",
            "backorder_eta_utc",
            "supplier_file_asof_utc",
            "supplier_file_reference",
            "proof_note",
            "actor",
            "event_source_reference",
            "proof_status",
            "creates_live_action",
        ],
        [
            {
                "event_utc": OBSERVED,
                "proof_id": "proof-unsafe",
                "session_id": "o_restock_session_v1",
                "row_id": "o_restock_session_v1:supplier:sku1",
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "row_source_reference": "native_o:SKU1",
                "supplier_stock_state": "supplier_stock_verified_in_stock",
                "supplier_stock_qty": "4",
                "backorder_state": "backorder_none_confirmed",
                "backorder_eta_utc": "",
                "supplier_file_asof_utc": OBSERVED,
                "supplier_file_reference": "price-file.csv",
                "proof_note": "unsafe proof",
                "actor": "operator_ui",
                "event_source_reference": "test",
                "proof_status": "draft_proof",
                "creates_live_action": "1",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_restock_supplier_batch_drafts"]["status"] == "fail"
    assert rows["o_restock_supplier_batch_drafts"]["value"] == "bad_proof_event_rows=1"
    assert "proof-unsafe:creates_live_action" in rows["o_restock_supplier_batch_drafts"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_supplier_batch_drafts_fail_unsafe_pack_moq_proof_event(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_session_pack_moq_proof_events.csv",
        [
            "event_utc",
            "proof_id",
            "session_id",
            "row_id",
            "seller_sku",
            "asin",
            "supplier_name",
            "supplier_code",
            "source_class",
            "row_source_reference",
            "pack_moq_proof_state",
            "pack_multiple",
            "supplier_moq",
            "valid_order_step",
            "proof_file_reference",
            "proof_note",
            "actor",
            "event_source_reference",
            "proof_status",
            "creates_live_action",
        ],
        [
            {
                "event_utc": OBSERVED,
                "proof_id": "pack-proof-unsafe",
                "session_id": "o_restock_session_v1",
                "row_id": "o_restock_session_v1:supplier:sku1",
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "row_source_reference": "native_o:SKU1",
                "pack_moq_proof_state": "pack_moq_verified",
                "pack_multiple": "6",
                "supplier_moq": "12",
                "valid_order_step": "6",
                "proof_file_reference": "pack-file.csv",
                "proof_note": "unsafe pack proof",
                "actor": "operator_ui",
                "event_source_reference": "test",
                "proof_status": "draft_proof",
                "creates_live_action": "1",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_restock_supplier_batch_drafts"]["status"] == "fail"
    assert rows["o_restock_supplier_batch_drafts"]["value"] == "bad_pack_moq_event_rows=1"
    assert "pack-proof-unsafe:creates_live_action" in rows["o_restock_supplier_batch_drafts"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_supplier_batch_drafts_fail_false_ready_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_session_supplier_batch_lines_live.csv",
        [
            "batch_utc",
            "batch_id",
            "session_id",
            "row_id",
            "draft_id",
            "draft_event_utc",
            "supplier_name",
            "supplier_code",
            "source_class",
            "seller_sku",
            "asin",
            "title",
            "supplier_sku",
            "barcode",
            "draft_order_qty",
            "current_supplier_cost_gbp",
            "draft_line_value_gbp",
            "supplier_order_viability_state",
            "action_safety_state",
            "action_block_reason",
            "line_state",
            "creates_live_action",
            "supplier_proof_checklist_status",
            "supplier_proof_missing_reasons",
            "supplier_match_state",
            "supplier_proof_state",
            "supplier_stock_state",
            "backorder_state",
            "supplier_file_asof_utc",
            "supplier_cost_proof_state",
            "pack_moq_proof_state",
            "supplier_batch_readiness_state",
            "supplier_batch_readiness_reasons",
        ],
        [
            {
                "batch_utc": OBSERVED,
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "o_restock_session_v1:supplier:sku1",
                "draft_id": "draft-1",
                "draft_event_utc": OBSERVED,
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "title": "Product",
                "supplier_sku": "SUP1",
                "barcode": "123",
                "draft_order_qty": "2",
                "current_supplier_cost_gbp": "3",
                "draft_line_value_gbp": "6",
                "supplier_order_viability_state": "review_only_not_po",
                "action_safety_state": "blocked_from_clean_buy",
                "action_block_reason": "refund:missing_refund_confidence",
                "line_state": "review_only_blocked",
                "creates_live_action": "0",
                "supplier_proof_checklist_status": "supplier_proof_clear",
                "supplier_proof_missing_reasons": "",
                "supplier_match_state": "exact_supplier_sku_or_barcode_match",
                "supplier_proof_state": "supplier_exact_match_proved",
                "supplier_stock_state": "supplier_stock_verified_in_stock",
                "backorder_state": "backorder_none_confirmed",
                "supplier_file_asof_utc": OBSERVED,
                "supplier_cost_proof_state": "supplier_cost_verified",
                "pack_moq_proof_state": "pack_moq_verified",
                "supplier_batch_readiness_state": "ready_for_purchase_approval_review_only",
                "supplier_batch_readiness_reasons": "",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_restock_supplier_batch_drafts"]["status"] == "fail"
    assert rows["o_restock_supplier_batch_drafts"]["value"] == "bad_readiness_rows=1;missing_readiness_reason_rows=0"
    assert "bad_readiness_rows=o_restock_session_v1:supplier:sku1" in rows["o_restock_supplier_batch_drafts"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_supplier_file_presence_probe_allows_latest_file_not_found_proof(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_supplier_file_presence_probe_live.csv",
        _supplier_file_probe_headers(),
        [_supplier_file_probe_row()],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["o_supplier_file_presence_probe"]["status"] == "ok"
    assert rows["o_supplier_file_presence_probe"]["value"] == "probes=1;found=0;not_found=1;not_checked=0"
    assert rows["o_user_working_readiness"]["status"] == "ok"


def test_o_supplier_file_source_index_allows_failed_f_status_with_local_file(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_supplier_file_source_index_live.csv",
        _supplier_file_source_index_headers(),
        [_supplier_file_source_index_row()],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["o_supplier_file_source_index"]["status"] == "ok"
    assert rows["o_supplier_file_source_index"]["value"] == (
        "index_rows=1;local_files=1;f_failed_local_available=1;local_newer=0"
    )
    assert rows["o_user_working_readiness"]["status"] == "ok"


def test_o_supplier_file_source_index_fails_unsafe_status_rewrite_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_supplier_file_source_index_live.csv",
        _supplier_file_source_index_headers(),
        [_supplier_file_source_index_row(updates_f_status="1")],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_supplier_file_source_index"]["status"] == "fail"
    assert rows["o_supplier_file_source_index"]["value"] == "unsafe_rows=1"
    assert "unsafe_rows=abgee" in rows["o_supplier_file_source_index"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_supplier_file_presence_probe_fails_unsafe_live_action_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_supplier_file_presence_probe_live.csv",
        _supplier_file_probe_headers(),
        [_supplier_file_probe_row(creates_live_action="1")],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_supplier_file_presence_probe"]["status"] == "fail"
    assert rows["o_supplier_file_presence_probe"]["value"] == "unsafe_rows=1"
    assert "unsafe_rows=row-1" in rows["o_supplier_file_presence_probe"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_supplier_file_presence_probe_fails_false_match_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_supplier_file_presence_probe_live.csv",
        _supplier_file_probe_headers(),
        [
            _supplier_file_probe_row(
                state="exact_supplier_sku_or_barcode_found",
                matched_row_count="0",
            )
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_supplier_file_presence_probe"]["status"] == "fail"
    assert rows["o_supplier_file_presence_probe"]["value"] == (
        "unknown_state_rows=0;bad_match_claim_rows=1;missing_explanation_rows=0"
    )
    assert "bad_match_claim_rows=row-1" in rows["o_supplier_file_presence_probe"]["actual_proof"]


def test_o_purchase_approval_preview_fails_live_action_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_purchase_approval_preview_lines_live.csv",
        [
            "preview_utc",
            "approval_packet_id",
            "batch_id",
            "session_id",
            "row_id",
            "supplier_name",
            "supplier_code",
            "source_class",
            "seller_sku",
            "asin",
            "title",
            "supplier_sku",
            "barcode",
            "draft_order_qty",
            "current_supplier_cost_gbp",
            "draft_line_value_gbp",
            "supplier_batch_readiness_state",
            "supplier_batch_readiness_reasons",
            "supplier_proof_checklist_status",
            "supplier_proof_missing_reasons",
            "approval_preview_state",
            "approval_block_reasons",
            "creates_live_action",
        ],
        [
            {
                "preview_utc": OBSERVED,
                "approval_packet_id": "packet-1",
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "title": "Product",
                "supplier_sku": "SUP1",
                "barcode": "123",
                "draft_order_qty": "2",
                "current_supplier_cost_gbp": "3",
                "draft_line_value_gbp": "6",
                "supplier_batch_readiness_state": "ready_for_purchase_approval_review_only",
                "supplier_batch_readiness_reasons": "",
                "supplier_proof_checklist_status": "supplier_proof_clear",
                "supplier_proof_missing_reasons": "",
                "approval_preview_state": "ready_for_purchase_approval_review_only",
                "approval_block_reasons": "",
                "creates_live_action": "1",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_purchase_approval_preview"]["status"] == "fail"
    assert "live_action_rows=1" in rows["o_purchase_approval_preview"]["value"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_purchase_approval_preview_fails_false_ready_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_purchase_approval_preview_lines_live.csv",
        [
            "preview_utc",
            "approval_packet_id",
            "batch_id",
            "session_id",
            "row_id",
            "supplier_name",
            "supplier_code",
            "source_class",
            "seller_sku",
            "asin",
            "title",
            "supplier_sku",
            "barcode",
            "draft_order_qty",
            "current_supplier_cost_gbp",
            "draft_line_value_gbp",
            "supplier_batch_readiness_state",
            "supplier_batch_readiness_reasons",
            "supplier_proof_checklist_status",
            "supplier_proof_missing_reasons",
            "approval_preview_state",
            "approval_block_reasons",
            "creates_live_action",
        ],
        [
            {
                "preview_utc": OBSERVED,
                "approval_packet_id": "packet-1",
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "title": "Product",
                "supplier_sku": "SUP1",
                "barcode": "123",
                "draft_order_qty": "2",
                "current_supplier_cost_gbp": "3",
                "draft_line_value_gbp": "6",
                "supplier_batch_readiness_state": "blocked_from_purchase_approval",
                "supplier_batch_readiness_reasons": "supplier_proof:supplier_stock_not_verified",
                "supplier_proof_checklist_status": "needs_supplier_proof",
                "supplier_proof_missing_reasons": "supplier_stock_not_verified",
                "approval_preview_state": "ready_for_purchase_approval_review_only",
                "approval_block_reasons": "",
                "creates_live_action": "0",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_purchase_approval_preview"]["status"] == "fail"
    assert rows["o_purchase_approval_preview"]["value"] == "unknown_state_rows=0;false_ready_rows=1;missing_block_reason_rows=0"
    assert "false_ready_rows=row-1" in rows["o_purchase_approval_preview"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_purchase_approval_guardrails_fail_live_action_decision_event(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_purchase_approval_decision_events.csv",
        [
            "event_utc",
            "decision_id",
            "approval_packet_id",
            "supplier_name",
            "supplier_code",
            "source_preview_utc",
            "decision_state",
            "expected_line_count",
            "expected_ready_line_count",
            "expected_blocked_line_count",
            "expected_order_value_gbp",
            "decision_note",
            "actor",
            "event_source_reference",
            "decision_status",
            "creates_live_action",
        ],
        [
            {
                "event_utc": OBSERVED,
                "decision_id": "decision-unsafe",
                "approval_packet_id": "packet-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_preview_utc": OBSERVED,
                "decision_state": "local_review_accept_not_commitment",
                "expected_line_count": "1",
                "expected_ready_line_count": "1",
                "expected_blocked_line_count": "0",
                "expected_order_value_gbp": "6",
                "decision_note": "local review only",
                "actor": "operator_ui",
                "event_source_reference": "o_ui_purchase_approval_guardrails",
                "decision_status": "draft_guardrail_decision",
                "creates_live_action": "1",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_purchase_approval_guardrails"]["status"] == "fail"
    assert rows["o_purchase_approval_guardrails"]["value"] == (
        "live_action_events=1;live_action_guardrails=0;live_language_events=0;live_language_guardrails=0"
    )
    assert "live_action_events=decision-unsafe" in rows["o_purchase_approval_guardrails"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_purchase_approval_guardrails_fail_false_accept_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_purchase_approval_guardrails_live.csv",
        [
            "guardrail_utc",
            "approval_packet_id",
            "source_preview_utc",
            "supplier_name",
            "supplier_code",
            "line_count",
            "ready_line_count",
            "blocked_line_count",
            "draft_order_value_gbp",
            "preview_packet_state",
            "latest_decision_state",
            "latest_decision_id",
            "latest_decision_utc",
            "approval_guardrail_state",
            "approval_guardrail_reasons",
            "creates_live_action",
        ],
        [
            {
                "guardrail_utc": OBSERVED,
                "approval_packet_id": "packet-1",
                "source_preview_utc": OBSERVED,
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "line_count": "1",
                "ready_line_count": "0",
                "blocked_line_count": "1",
                "draft_order_value_gbp": "6",
                "preview_packet_state": "blocked_from_purchase_approval_review",
                "latest_decision_state": "local_review_accept_not_commitment",
                "latest_decision_id": "decision-1",
                "latest_decision_utc": OBSERVED,
                "approval_guardrail_state": "local_review_accept_not_commitment",
                "approval_guardrail_reasons": "",
                "creates_live_action": "0",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_purchase_approval_guardrails"]["status"] == "fail"
    assert rows["o_purchase_approval_guardrails"]["value"] == "unknown_guardrails=0;false_accept_rows=1"
    assert "false_accept_rows=packet-1" in rows["o_purchase_approval_guardrails"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_po_draft_readiness_preview_fails_live_action_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_po_draft_readiness_preview_lines_live.csv",
        [
            "preview_utc",
            "po_readiness_preview_id",
            "approval_packet_id",
            "source_preview_utc",
            "guardrail_utc",
            "batch_id",
            "session_id",
            "row_id",
            "supplier_name",
            "supplier_code",
            "source_class",
            "seller_sku",
            "asin",
            "title",
            "supplier_sku",
            "barcode",
            "draft_order_qty",
            "current_supplier_cost_gbp",
            "draft_line_value_gbp",
            "approval_preview_state",
            "approval_guardrail_state",
            "po_draft_readiness_state",
            "po_draft_block_reasons",
            "po_creation_allowed",
            "creates_live_action",
            "supplier_proof_checklist_status",
        ],
        [
            {
                "preview_utc": OBSERVED,
                "po_readiness_preview_id": "po-preview-1",
                "approval_packet_id": "packet-1",
                "source_preview_utc": OBSERVED,
                "guardrail_utc": OBSERVED,
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "title": "Product",
                "supplier_sku": "SUP1",
                "barcode": "123",
                "draft_order_qty": "2",
                "current_supplier_cost_gbp": "3",
                "draft_line_value_gbp": "6",
                "approval_preview_state": "ready_for_purchase_approval_review_only",
                "approval_guardrail_state": "local_review_accept_not_commitment",
                "po_draft_readiness_state": "ready_for_local_po_draft_review_only",
                "po_draft_block_reasons": "",
                "po_creation_allowed": "1",
                "creates_live_action": "0",
                "supplier_proof_checklist_status": "supplier_proof_clear",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_po_draft_readiness_preview"]["status"] == "fail"
    assert rows["o_po_draft_readiness_preview"]["value"] == "live_action_rows=1;bad_summary_rows=0;live_language_rows=0"
    assert "live_action_rows=row-1" in rows["o_po_draft_readiness_preview"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_po_draft_readiness_preview_fails_false_ready_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_po_draft_readiness_preview_lines_live.csv",
        [
            "preview_utc",
            "po_readiness_preview_id",
            "approval_packet_id",
            "source_preview_utc",
            "guardrail_utc",
            "batch_id",
            "session_id",
            "row_id",
            "supplier_name",
            "supplier_code",
            "source_class",
            "seller_sku",
            "asin",
            "title",
            "supplier_sku",
            "barcode",
            "draft_order_qty",
            "current_supplier_cost_gbp",
            "draft_line_value_gbp",
            "approval_preview_state",
            "approval_guardrail_state",
            "po_draft_readiness_state",
            "po_draft_block_reasons",
            "po_creation_allowed",
            "creates_live_action",
            "supplier_proof_checklist_status",
        ],
        [
            {
                "preview_utc": OBSERVED,
                "po_readiness_preview_id": "po-preview-1",
                "approval_packet_id": "packet-1",
                "source_preview_utc": OBSERVED,
                "guardrail_utc": OBSERVED,
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "title": "Product",
                "supplier_sku": "SUP1",
                "barcode": "123",
                "draft_order_qty": "2",
                "current_supplier_cost_gbp": "3",
                "draft_line_value_gbp": "6",
                "approval_preview_state": "ready_for_purchase_approval_review_only",
                "approval_guardrail_state": "no_local_review_decision",
                "po_draft_readiness_state": "ready_for_local_po_draft_review_only",
                "po_draft_block_reasons": "",
                "po_creation_allowed": "0",
                "creates_live_action": "0",
                "supplier_proof_checklist_status": "supplier_proof_clear",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_po_draft_readiness_preview"]["status"] == "fail"
    assert rows["o_po_draft_readiness_preview"]["value"] == (
        "unknown_state_rows=0;false_ready_rows=1;missing_block_reason_rows=0"
    )
    assert "false_ready_rows=row-1" in rows["o_po_draft_readiness_preview"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_po_line_design_preview_fails_live_action_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_po_line_design_preview_lines_live.csv",
        [
            "preview_utc",
            "po_line_design_id",
            "po_line_design_packet_id",
            "po_readiness_preview_id",
            "approval_packet_id",
            "source_readiness_utc",
            "batch_id",
            "session_id",
            "row_id",
            "supplier_name",
            "supplier_code",
            "source_class",
            "seller_sku",
            "asin",
            "title",
            "supplier_sku",
            "barcode",
            "designed_order_qty",
            "designed_unit_cost_gbp",
            "designed_line_value_gbp",
            "source_po_draft_readiness_state",
            "line_design_state",
            "line_design_block_reasons",
            "po_file_write_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "receiving_allowed",
            "send_to_amazon_allowed",
            "creates_live_action",
        ],
        [
            {
                "preview_utc": OBSERVED,
                "po_line_design_id": "line-design-1",
                "po_line_design_packet_id": "line-design-packet-1",
                "po_readiness_preview_id": "po-preview-1",
                "approval_packet_id": "packet-1",
                "source_readiness_utc": OBSERVED,
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "title": "Product",
                "supplier_sku": "SUP1",
                "barcode": "123",
                "designed_order_qty": "2",
                "designed_unit_cost_gbp": "3",
                "designed_line_value_gbp": "6",
                "source_po_draft_readiness_state": "ready_for_local_po_draft_review_only",
                "line_design_state": "ready_for_local_po_line_design_review_only",
                "line_design_block_reasons": "",
                "po_file_write_allowed": "1",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_po_line_design_preview"]["status"] == "fail"
    assert rows["o_po_line_design_preview"]["value"] == "live_action_rows=1;bad_summary_rows=0;live_language_rows=0"
    assert "live_action_rows=row-1" in rows["o_po_line_design_preview"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_po_line_design_preview_fails_false_ready_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_po_line_design_preview_lines_live.csv",
        [
            "preview_utc",
            "po_line_design_id",
            "po_line_design_packet_id",
            "po_readiness_preview_id",
            "approval_packet_id",
            "source_readiness_utc",
            "batch_id",
            "session_id",
            "row_id",
            "supplier_name",
            "supplier_code",
            "source_class",
            "seller_sku",
            "asin",
            "title",
            "supplier_sku",
            "barcode",
            "designed_order_qty",
            "designed_unit_cost_gbp",
            "designed_line_value_gbp",
            "source_po_draft_readiness_state",
            "line_design_state",
            "line_design_block_reasons",
            "po_file_write_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "receiving_allowed",
            "send_to_amazon_allowed",
            "creates_live_action",
        ],
        [
            {
                "preview_utc": OBSERVED,
                "po_line_design_id": "line-design-1",
                "po_line_design_packet_id": "line-design-packet-1",
                "po_readiness_preview_id": "po-preview-1",
                "approval_packet_id": "packet-1",
                "source_readiness_utc": OBSERVED,
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "title": "Product",
                "supplier_sku": "SUP1",
                "barcode": "123",
                "designed_order_qty": "2",
                "designed_unit_cost_gbp": "3",
                "designed_line_value_gbp": "6",
                "source_po_draft_readiness_state": "blocked_from_local_po_draft_review",
                "line_design_state": "ready_for_local_po_line_design_review_only",
                "line_design_block_reasons": "",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_po_line_design_preview"]["status"] == "fail"
    assert rows["o_po_line_design_preview"]["value"] == (
        "unknown_state_rows=0;false_ready_rows=1;missing_block_reason_rows=0"
    )
    assert "false_ready_rows=row-1" in rows["o_po_line_design_preview"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_po_draft_packet_review_fails_live_action_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_po_draft_packet_review_lines_live.csv",
        [
            "review_utc",
            "po_draft_packet_review_id",
            "po_line_design_id",
            "po_line_design_packet_id",
            "approval_packet_id",
            "source_design_utc",
            "batch_id",
            "session_id",
            "row_id",
            "supplier_name",
            "supplier_code",
            "source_class",
            "seller_sku",
            "asin",
            "title",
            "supplier_sku",
            "barcode",
            "review_order_qty",
            "review_unit_cost_gbp",
            "review_line_value_gbp",
            "source_line_design_state",
            "source_po_file_write_allowed",
            "source_po_creation_allowed",
            "source_purchase_commitment_allowed",
            "source_receiving_allowed",
            "source_send_to_amazon_allowed",
            "source_creates_live_action",
            "packet_review_line_state",
            "packet_review_block_reasons",
            "po_file_write_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "receiving_allowed",
            "send_to_amazon_allowed",
            "creates_live_action",
        ],
        [
            {
                "review_utc": OBSERVED,
                "po_draft_packet_review_id": "packet-review-1",
                "po_line_design_id": "line-design-1",
                "po_line_design_packet_id": "line-design-packet-1",
                "approval_packet_id": "packet-1",
                "source_design_utc": OBSERVED,
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "title": "Product",
                "supplier_sku": "SUP1",
                "barcode": "123",
                "review_order_qty": "2",
                "review_unit_cost_gbp": "3",
                "review_line_value_gbp": "6",
                "source_line_design_state": "ready_for_local_po_line_design_review_only",
                "source_po_file_write_allowed": "0",
                "source_po_creation_allowed": "0",
                "source_purchase_commitment_allowed": "0",
                "source_receiving_allowed": "0",
                "source_send_to_amazon_allowed": "0",
                "source_creates_live_action": "0",
                "packet_review_line_state": "ready_for_local_po_draft_packet_review_only",
                "packet_review_block_reasons": "",
                "po_file_write_allowed": "1",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_po_draft_packet_review"]["status"] == "fail"
    assert rows["o_po_draft_packet_review"]["value"] == (
        "source_action_rows=0;live_action_rows=1;bad_summary_rows=0;live_language_rows=0"
    )
    assert "live_action_rows=row-1" in rows["o_po_draft_packet_review"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_po_draft_packet_review_fails_false_ready_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_po_draft_packet_review_lines_live.csv",
        [
            "review_utc",
            "po_draft_packet_review_id",
            "po_line_design_id",
            "po_line_design_packet_id",
            "approval_packet_id",
            "source_design_utc",
            "batch_id",
            "session_id",
            "row_id",
            "supplier_name",
            "supplier_code",
            "source_class",
            "seller_sku",
            "asin",
            "title",
            "supplier_sku",
            "barcode",
            "review_order_qty",
            "review_unit_cost_gbp",
            "review_line_value_gbp",
            "source_line_design_state",
            "source_po_file_write_allowed",
            "source_po_creation_allowed",
            "source_purchase_commitment_allowed",
            "source_receiving_allowed",
            "source_send_to_amazon_allowed",
            "source_creates_live_action",
            "packet_review_line_state",
            "packet_review_block_reasons",
            "po_file_write_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "receiving_allowed",
            "send_to_amazon_allowed",
            "creates_live_action",
        ],
        [
            {
                "review_utc": OBSERVED,
                "po_draft_packet_review_id": "packet-review-1",
                "po_line_design_id": "line-design-1",
                "po_line_design_packet_id": "line-design-packet-1",
                "approval_packet_id": "packet-1",
                "source_design_utc": OBSERVED,
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "title": "Product",
                "supplier_sku": "SUP1",
                "barcode": "123",
                "review_order_qty": "2",
                "review_unit_cost_gbp": "3",
                "review_line_value_gbp": "6",
                "source_line_design_state": "blocked_from_local_po_line_design_review",
                "source_po_file_write_allowed": "0",
                "source_po_creation_allowed": "0",
                "source_purchase_commitment_allowed": "0",
                "source_receiving_allowed": "0",
                "source_send_to_amazon_allowed": "0",
                "source_creates_live_action": "0",
                "packet_review_line_state": "ready_for_local_po_draft_packet_review_only",
                "packet_review_block_reasons": "",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_po_draft_packet_review"]["status"] == "fail"
    assert rows["o_po_draft_packet_review"]["value"] == (
        "unknown_state_rows=0;false_ready_rows=1;missing_block_reason_rows=0"
    )
    assert "false_ready_rows=row-1" in rows["o_po_draft_packet_review"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_po_draft_hold_review_fails_live_action_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_po_draft_hold_review_lines_live.csv",
        [
            "hold_utc",
            "po_draft_hold_review_id",
            "po_draft_packet_review_id",
            "po_line_design_packet_id",
            "approval_packet_id",
            "source_packet_review_utc",
            "batch_id",
            "session_id",
            "row_id",
            "supplier_name",
            "supplier_code",
            "source_class",
            "seller_sku",
            "asin",
            "title",
            "supplier_sku",
            "barcode",
            "hold_order_qty",
            "hold_unit_cost_gbp",
            "hold_line_value_gbp",
            "source_packet_review_line_state",
            "source_po_file_write_allowed",
            "source_po_creation_allowed",
            "source_purchase_commitment_allowed",
            "source_receiving_allowed",
            "source_send_to_amazon_allowed",
            "source_creates_live_action",
            "hold_review_line_state",
            "hold_review_reasons",
            "po_file_write_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "receiving_allowed",
            "send_to_amazon_allowed",
            "creates_live_action",
        ],
        [
            {
                "hold_utc": OBSERVED,
                "po_draft_hold_review_id": "hold-review-1",
                "po_draft_packet_review_id": "packet-review-1",
                "po_line_design_packet_id": "line-design-packet-1",
                "approval_packet_id": "packet-1",
                "source_packet_review_utc": OBSERVED,
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "title": "Product",
                "supplier_sku": "SUP1",
                "barcode": "123",
                "hold_order_qty": "2",
                "hold_unit_cost_gbp": "3",
                "hold_line_value_gbp": "6",
                "source_packet_review_line_state": "ready_for_local_po_draft_packet_review_only",
                "source_po_file_write_allowed": "0",
                "source_po_creation_allowed": "0",
                "source_purchase_commitment_allowed": "0",
                "source_receiving_allowed": "0",
                "source_send_to_amazon_allowed": "0",
                "source_creates_live_action": "0",
                "hold_review_line_state": "held_for_local_po_draft_review_only",
                "hold_review_reasons": "local_review_hold_zero_action",
                "po_file_write_allowed": "1",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_po_draft_hold_review"]["status"] == "fail"
    assert rows["o_po_draft_hold_review"]["value"] == (
        "source_action_rows=0;live_action_rows=1;bad_summary_rows=0;live_language_rows=0"
    )
    assert "live_action_rows=row-1" in rows["o_po_draft_hold_review"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_po_draft_hold_review_fails_false_hold_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_po_draft_hold_review_lines_live.csv",
        [
            "hold_utc",
            "po_draft_hold_review_id",
            "po_draft_packet_review_id",
            "po_line_design_packet_id",
            "approval_packet_id",
            "source_packet_review_utc",
            "batch_id",
            "session_id",
            "row_id",
            "supplier_name",
            "supplier_code",
            "source_class",
            "seller_sku",
            "asin",
            "title",
            "supplier_sku",
            "barcode",
            "hold_order_qty",
            "hold_unit_cost_gbp",
            "hold_line_value_gbp",
            "source_packet_review_line_state",
            "source_po_file_write_allowed",
            "source_po_creation_allowed",
            "source_purchase_commitment_allowed",
            "source_receiving_allowed",
            "source_send_to_amazon_allowed",
            "source_creates_live_action",
            "hold_review_line_state",
            "hold_review_reasons",
            "po_file_write_allowed",
            "po_creation_allowed",
            "purchase_commitment_allowed",
            "receiving_allowed",
            "send_to_amazon_allowed",
            "creates_live_action",
        ],
        [
            {
                "hold_utc": OBSERVED,
                "po_draft_hold_review_id": "hold-review-1",
                "po_draft_packet_review_id": "packet-review-1",
                "po_line_design_packet_id": "line-design-packet-1",
                "approval_packet_id": "packet-1",
                "source_packet_review_utc": OBSERVED,
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "title": "Product",
                "supplier_sku": "SUP1",
                "barcode": "123",
                "hold_order_qty": "2",
                "hold_unit_cost_gbp": "3",
                "hold_line_value_gbp": "6",
                "source_packet_review_line_state": "blocked_from_local_po_draft_packet_review",
                "source_po_file_write_allowed": "0",
                "source_po_creation_allowed": "0",
                "source_purchase_commitment_allowed": "0",
                "source_receiving_allowed": "0",
                "source_send_to_amazon_allowed": "0",
                "source_creates_live_action": "0",
                "hold_review_line_state": "held_for_local_po_draft_review_only",
                "hold_review_reasons": "local_review_hold_zero_action",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_po_draft_hold_review"]["status"] == "fail"
    assert rows["o_po_draft_hold_review"]["value"] == (
        "unknown_state_rows=0;false_hold_rows=1;missing_hold_reason_rows=0"
    )
    assert "false_hold_rows=row-1" in rows["o_po_draft_hold_review"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def _file_shape_preview_headers() -> list[str]:
    return [
        "shape_utc",
        "po_draft_file_shape_preview_id",
        "po_draft_hold_review_id",
        "po_draft_packet_review_id",
        "po_line_design_packet_id",
        "approval_packet_id",
        "source_hold_utc",
        "batch_id",
        "session_id",
        "row_id",
        "supplier_name",
        "supplier_code",
        "source_class",
        "seller_sku",
        "asin",
        "title",
        "supplier_sku",
        "barcode",
        "file_shape_qty",
        "file_shape_unit_cost_gbp",
        "file_shape_line_value_gbp",
        "source_hold_review_line_state",
        "source_po_file_write_allowed",
        "source_po_creation_allowed",
        "source_purchase_commitment_allowed",
        "source_receiving_allowed",
        "source_send_to_amazon_allowed",
        "source_creates_live_action",
        "file_shape_line_state",
        "file_shape_block_reasons",
        "po_file_write_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "receiving_allowed",
        "send_to_amazon_allowed",
        "creates_live_action",
    ]


def _construction_summary_headers() -> list[str]:
    return [
        "summary_utc",
        "stage_key",
        "stage_label",
        "source_contract",
        "source_health_contract",
        "state_column",
        "line_rows",
        "ready_or_held_rows",
        "blocked_rows",
        "health_rows",
        "health_bad_rows",
        "stage_state",
        "stage_block_reasons",
        "po_file_write_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "receiving_allowed",
        "send_to_amazon_allowed",
        "creates_live_action",
    ]


def _construction_summary_rows(*, live_action_stage: str = "", bad_health_stage: str = "") -> list[dict[str, str]]:
    stages = [
        ("po_draft_readiness", "PO draft readiness", "restock_po_draft_readiness_preview_lines_live", "restock_po_draft_readiness_preview_health", "po_draft_readiness_state"),
        ("po_line_design", "PO line design", "restock_po_line_design_preview_lines_live", "restock_po_line_design_preview_health", "line_design_state"),
        ("po_draft_packet_review", "PO draft packet review", "restock_po_draft_packet_review_lines_live", "restock_po_draft_packet_review_health", "packet_review_line_state"),
        ("po_draft_hold_review", "PO draft hold review", "restock_po_draft_hold_review_lines_live", "restock_po_draft_hold_review_health", "hold_review_line_state"),
        ("po_draft_file_shape", "PO draft file-shape preview", "restock_po_draft_file_shape_preview_lines_live", "restock_po_draft_file_shape_preview_health", "file_shape_line_state"),
    ]
    rows: list[dict[str, str]] = []
    for stage_key, label, source_contract, health_contract, state_column in stages:
        rows.append(
            {
                "summary_utc": OBSERVED,
                "stage_key": stage_key,
                "stage_label": label,
                "source_contract": source_contract,
                "source_health_contract": health_contract,
                "state_column": state_column,
                "line_rows": "0",
                "ready_or_held_rows": "0",
                "blocked_rows": "0",
                "health_rows": "1",
                "health_bad_rows": "1" if stage_key == bad_health_stage else "0",
                "stage_state": "blocked_by_stage_health" if stage_key == bad_health_stage else "built_waiting_for_rows",
                "stage_block_reasons": "source_health_not_ok" if stage_key == bad_health_stage else "",
                "po_file_write_allowed": "1" if stage_key == live_action_stage else "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        )
    return rows


def _review_control_headers() -> list[str]:
    return [
        "control_utc",
        "po_draft_file_shape_preview_id",
        "po_draft_hold_review_id",
        "po_draft_packet_review_id",
        "po_line_design_packet_id",
        "approval_packet_id",
        "source_shape_utc",
        "supplier_name",
        "supplier_code",
        "line_count",
        "ready_line_count",
        "blocked_line_count",
        "file_shape_value_gbp",
        "source_file_shape_state",
        "latest_decision_state",
        "latest_control_event_id",
        "latest_decision_utc",
        "review_control_state",
        "review_control_reasons",
        "po_file_write_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "receiving_allowed",
        "send_to_amazon_allowed",
        "creates_live_action",
    ]


def _review_control_row(
    *,
    state: str = "local_po_draft_shape_ready_not_po",
    source_state: str = "ready_for_local_po_draft_file_shape_review_only",
    ready_count: str = "1",
    blocked_count: str = "0",
    po_file_write_allowed: str = "0",
) -> dict[str, str]:
    return {
        "control_utc": OBSERVED,
        "po_draft_file_shape_preview_id": "file-shape-1",
        "po_draft_hold_review_id": "hold-review-1",
        "po_draft_packet_review_id": "packet-review-1",
        "po_line_design_packet_id": "line-design-packet-1",
        "approval_packet_id": "packet-1",
        "source_shape_utc": OBSERVED,
        "supplier_name": "Supplier",
        "supplier_code": "SUP",
        "line_count": "1",
        "ready_line_count": ready_count,
        "blocked_line_count": blocked_count,
        "file_shape_value_gbp": "6",
        "source_file_shape_state": source_state,
        "latest_decision_state": state,
        "latest_control_event_id": "control-event-1",
        "latest_decision_utc": OBSERVED,
        "review_control_state": state,
        "review_control_reasons": "" if state == "local_po_draft_shape_ready_not_po" else "file_shape_not_ready",
        "po_file_write_allowed": po_file_write_allowed,
        "po_creation_allowed": "0",
        "purchase_commitment_allowed": "0",
        "receiving_allowed": "0",
        "send_to_amazon_allowed": "0",
        "creates_live_action": "0",
    }


def _export_preview_headers() -> list[str]:
    return [
        "export_preview_utc",
        "po_draft_export_preview_id",
        "po_draft_file_shape_preview_id",
        "po_draft_hold_review_id",
        "po_draft_packet_review_id",
        "po_line_design_packet_id",
        "approval_packet_id",
        "source_shape_utc",
        "source_control_utc",
        "batch_id",
        "session_id",
        "row_id",
        "supplier_name",
        "supplier_code",
        "source_class",
        "seller_sku",
        "asin",
        "title",
        "supplier_sku",
        "barcode",
        "export_preview_qty",
        "export_preview_unit_cost_gbp",
        "export_preview_line_value_gbp",
        "source_file_shape_line_state",
        "source_review_control_state",
        "source_po_file_write_allowed",
        "source_po_creation_allowed",
        "source_purchase_commitment_allowed",
        "source_receiving_allowed",
        "source_send_to_amazon_allowed",
        "source_creates_live_action",
        "control_po_file_write_allowed",
        "control_po_creation_allowed",
        "control_purchase_commitment_allowed",
        "control_receiving_allowed",
        "control_send_to_amazon_allowed",
        "control_creates_live_action",
        "export_preview_line_state",
        "export_preview_block_reasons",
        "po_file_write_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "receiving_allowed",
        "send_to_amazon_allowed",
        "creates_live_action",
    ]


def _export_preview_summary_headers() -> list[str]:
    return [
        "export_preview_utc",
        "po_draft_export_preview_id",
        "po_draft_file_shape_preview_id",
        "po_draft_hold_review_id",
        "po_draft_packet_review_id",
        "po_line_design_packet_id",
        "approval_packet_id",
        "supplier_name",
        "supplier_code",
        "line_count",
        "ready_line_count",
        "blocked_line_count",
        "export_preview_qty_total",
        "export_preview_value_gbp",
        "export_preview_state",
        "export_preview_block_reasons",
        "po_file_write_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "receiving_allowed",
        "send_to_amazon_allowed",
        "creates_live_action",
    ]


def _export_preview_row(
    *,
    state: str = "ready_for_local_po_draft_export_preview_only",
    source_state: str = "ready_for_local_po_draft_file_shape_review_only",
    control_state: str = "local_po_draft_shape_ready_not_po",
    po_file_write_allowed: str = "0",
    source_po_file_write_allowed: str = "0",
    control_po_file_write_allowed: str = "0",
) -> dict[str, str]:
    return {
        "export_preview_utc": OBSERVED,
        "po_draft_export_preview_id": "export-preview-1",
        "po_draft_file_shape_preview_id": "file-shape-1",
        "po_draft_hold_review_id": "hold-review-1",
        "po_draft_packet_review_id": "packet-review-1",
        "po_line_design_packet_id": "line-design-packet-1",
        "approval_packet_id": "packet-1",
        "source_shape_utc": OBSERVED,
        "source_control_utc": OBSERVED,
        "batch_id": "batch-1",
        "session_id": "o_restock_session_v1",
        "row_id": "row-1",
        "supplier_name": "Supplier",
        "supplier_code": "SUP",
        "source_class": "native_o",
        "seller_sku": "SKU1",
        "asin": "ASIN1",
        "title": "Product",
        "supplier_sku": "SUP1",
        "barcode": "123",
        "export_preview_qty": "2",
        "export_preview_unit_cost_gbp": "3",
        "export_preview_line_value_gbp": "6",
        "source_file_shape_line_state": source_state,
        "source_review_control_state": control_state,
        "source_po_file_write_allowed": source_po_file_write_allowed,
        "source_po_creation_allowed": "0",
        "source_purchase_commitment_allowed": "0",
        "source_receiving_allowed": "0",
        "source_send_to_amazon_allowed": "0",
        "source_creates_live_action": "0",
        "control_po_file_write_allowed": control_po_file_write_allowed,
        "control_po_creation_allowed": "0",
        "control_purchase_commitment_allowed": "0",
        "control_receiving_allowed": "0",
        "control_send_to_amazon_allowed": "0",
        "control_creates_live_action": "0",
        "export_preview_line_state": state,
        "export_preview_block_reasons": "" if state == "ready_for_local_po_draft_export_preview_only" else "review_control_not_shape_ready",
        "po_file_write_allowed": po_file_write_allowed,
        "po_creation_allowed": "0",
        "purchase_commitment_allowed": "0",
        "receiving_allowed": "0",
        "send_to_amazon_allowed": "0",
        "creates_live_action": "0",
    }


def _supplier_file_source_index_headers() -> list[str]:
    return [
        "index_utc",
        "supplier_key",
        "supplier_id",
        "supplier_name",
        "f_source_status",
        "f_source_state",
        "f_source_location",
        "f_latest_source_path",
        "f_latest_source_name",
        "f_latest_source_mtime_utc",
        "f_latest_source_path_exists",
        "f_checked_at_utc",
        "local_price_files_root",
        "local_supplier_folder_path",
        "local_latest_file_path",
        "local_latest_file_name",
        "local_latest_file_mtime_utc",
        "local_file_count",
        "source_handoff_state",
        "handoff_explanation",
        "can_be_used_for_presence_probe",
        "clears_supplier_proof",
        "imports_supplier_file",
        "updates_f_status",
        "creates_live_action",
        "f_notes",
        "local_search_scope",
    ]


def _supplier_file_source_index_row(
    *,
    state: str = "f_status_failed_local_file_available",
    creates_live_action: str = "0",
    updates_f_status: str = "0",
) -> dict[str, str]:
    return {
        "index_utc": OBSERVED,
        "supplier_key": "abgee",
        "supplier_id": "abgee",
        "supplier_name": "ABGee",
        "f_source_status": "fail",
        "f_source_state": "error",
        "f_source_location": "gmail_label:ABGee",
        "f_latest_source_path": "old.xlsx",
        "f_latest_source_name": "old.xlsx",
        "f_latest_source_mtime_utc": "2026-05-22T13:55:17Z",
        "f_latest_source_path_exists": "0",
        "f_checked_at_utc": OBSERVED,
        "local_price_files_root": "price-files",
        "local_supplier_folder_path": "price-files/ABGee",
        "local_latest_file_path": "price-files/ABGee/inbox/latest.xlsx",
        "local_latest_file_name": "latest.xlsx",
        "local_latest_file_mtime_utc": OBSERVED,
        "local_file_count": "1",
        "source_handoff_state": state,
        "handoff_explanation": "F source status is failed, but O found a readable local supplier file.",
        "can_be_used_for_presence_probe": "1",
        "clears_supplier_proof": "0",
        "imports_supplier_file": "0",
        "updates_f_status": updates_f_status,
        "creates_live_action": creates_live_action,
        "f_notes": "gmail_fetch_error=RuntimeError;label=ABGee",
        "local_search_scope": "supplier_folder_recursive_readable_price_files",
    }


def _supplier_file_probe_headers() -> list[str]:
    return [
        "probe_utc",
        "probe_id",
        "batch_id",
        "session_id",
        "row_id",
        "supplier_name",
        "supplier_code",
        "seller_sku",
        "asin",
        "title",
        "supplier_sku",
        "barcode",
        "draft_order_qty",
        "price_files_root",
        "supplier_folder_path",
        "latest_supplier_file_path",
        "latest_supplier_file_name",
        "latest_supplier_file_mtime_utc",
        "latest_supplier_file_state",
        "identity_match_state",
        "matched_by",
        "matched_row_count",
        "searched_row_count",
        "searched_identity_columns",
        "probe_explanation",
        "clears_supplier_proof",
        "purchase_approval_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "creates_live_action",
        "read_error",
        "source_index_handoff_state",
        "source_index_handoff_explanation",
    ]


def _supplier_file_probe_row(
    *,
    state: str = "not_found_in_latest_local_supplier_file",
    matched_row_count: str = "0",
    creates_live_action: str = "0",
    purchase_approval_allowed: str = "0",
) -> dict[str, str]:
    return {
        "probe_utc": OBSERVED,
        "probe_id": "probe-1",
        "batch_id": "batch-1",
        "session_id": "o_restock_session_v1",
        "row_id": "row-1",
        "supplier_name": "ABGee",
        "supplier_code": "ABG",
        "seller_sku": "12-749B-9EB5",
        "asin": "B084HZRR8G",
        "title": "Leatherface",
        "supplier_sku": "985 49830",
        "barcode": "889698498302",
        "draft_order_qty": "1",
        "price_files_root": "price-files",
        "supplier_folder_path": "price-files/ABGee",
        "latest_supplier_file_path": "price-files/ABGee/inbox/latest.csv",
        "latest_supplier_file_name": "latest.csv",
        "latest_supplier_file_mtime_utc": OBSERVED,
        "latest_supplier_file_state": "latest_local_supplier_file_checked",
        "identity_match_state": state,
        "matched_by": "supplier_sku" if state == "exact_supplier_sku_or_barcode_found" else "",
        "matched_row_count": matched_row_count,
        "searched_row_count": "1",
        "searched_identity_columns": "Barcode|Product Code",
        "probe_explanation": "Latest local supplier file was checked; exact supplier SKU or barcode was not found.",
        "clears_supplier_proof": "0",
        "purchase_approval_allowed": purchase_approval_allowed,
        "po_creation_allowed": "0",
        "purchase_commitment_allowed": "0",
        "creates_live_action": creates_live_action,
        "read_error": "",
        "source_index_handoff_state": "f_status_failed_local_file_available",
        "source_index_handoff_explanation": "F source status is failed, but O found a readable local supplier file.",
    }


def _export_gate_event_headers() -> list[str]:
    return [
        "event_utc",
        "gate_event_id",
        "po_draft_export_preview_id",
        "po_draft_file_shape_preview_id",
        "po_draft_hold_review_id",
        "po_draft_packet_review_id",
        "po_line_design_packet_id",
        "approval_packet_id",
        "supplier_name",
        "supplier_code",
        "source_export_preview_utc",
        "decision_state",
        "expected_line_count",
        "expected_ready_line_count",
        "expected_blocked_line_count",
        "expected_export_preview_value_gbp",
        "decision_note",
        "actor",
        "event_source_reference",
        "decision_status",
        "po_file_write_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "receiving_allowed",
        "send_to_amazon_allowed",
        "creates_live_action",
    ]


def _export_gate_headers() -> list[str]:
    return [
        "gate_utc",
        "po_draft_export_preview_id",
        "po_draft_file_shape_preview_id",
        "po_draft_hold_review_id",
        "po_draft_packet_review_id",
        "po_line_design_packet_id",
        "approval_packet_id",
        "source_export_preview_utc",
        "supplier_name",
        "supplier_code",
        "line_count",
        "ready_line_count",
        "blocked_line_count",
        "export_preview_value_gbp",
        "source_export_preview_state",
        "latest_decision_state",
        "latest_gate_event_id",
        "latest_decision_utc",
        "export_gate_state",
        "export_gate_reasons",
        "po_file_write_allowed",
        "po_creation_allowed",
        "purchase_commitment_allowed",
        "receiving_allowed",
        "send_to_amazon_allowed",
        "creates_live_action",
    ]


def _export_gate_row(
    *,
    state: str = "local_export_candidate_ready_not_po",
    source_state: str = "ready_for_local_po_draft_export_preview_only",
    ready_count: str = "1",
    blocked_count: str = "0",
    po_file_write_allowed: str = "0",
) -> dict[str, str]:
    return {
        "gate_utc": OBSERVED,
        "po_draft_export_preview_id": "export-preview-1",
        "po_draft_file_shape_preview_id": "file-shape-1",
        "po_draft_hold_review_id": "hold-review-1",
        "po_draft_packet_review_id": "packet-review-1",
        "po_line_design_packet_id": "line-design-packet-1",
        "approval_packet_id": "packet-1",
        "source_export_preview_utc": OBSERVED,
        "supplier_name": "Supplier",
        "supplier_code": "SUP",
        "line_count": "1",
        "ready_line_count": ready_count,
        "blocked_line_count": blocked_count,
        "export_preview_value_gbp": "6",
        "source_export_preview_state": source_state,
        "latest_decision_state": state,
        "latest_gate_event_id": "gate-event-1",
        "latest_decision_utc": OBSERVED,
        "export_gate_state": state,
        "export_gate_reasons": "" if state == "local_export_candidate_ready_not_po" else "export_preview_not_ready",
        "po_file_write_allowed": po_file_write_allowed,
        "po_creation_allowed": "0",
        "purchase_commitment_allowed": "0",
        "receiving_allowed": "0",
        "send_to_amazon_allowed": "0",
        "creates_live_action": "0",
    }


def test_o_po_draft_file_shape_preview_fails_live_action_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_po_draft_file_shape_preview_lines_live.csv",
        _file_shape_preview_headers(),
        [
            {
                "shape_utc": OBSERVED,
                "po_draft_file_shape_preview_id": "file-shape-1",
                "po_draft_hold_review_id": "hold-review-1",
                "po_draft_packet_review_id": "packet-review-1",
                "po_line_design_packet_id": "line-design-packet-1",
                "approval_packet_id": "packet-1",
                "source_hold_utc": OBSERVED,
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "title": "Product",
                "supplier_sku": "SUP1",
                "barcode": "123",
                "file_shape_qty": "2",
                "file_shape_unit_cost_gbp": "3",
                "file_shape_line_value_gbp": "6",
                "source_hold_review_line_state": "held_for_local_po_draft_review_only",
                "source_po_file_write_allowed": "0",
                "source_po_creation_allowed": "0",
                "source_purchase_commitment_allowed": "0",
                "source_receiving_allowed": "0",
                "source_send_to_amazon_allowed": "0",
                "source_creates_live_action": "0",
                "file_shape_line_state": "ready_for_local_po_draft_file_shape_review_only",
                "file_shape_block_reasons": "",
                "po_file_write_allowed": "1",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_po_draft_file_shape_preview"]["status"] == "fail"
    assert rows["o_po_draft_file_shape_preview"]["value"] == (
        "source_action_rows=0;live_action_rows=1;bad_summary_rows=0;live_language_rows=0"
    )
    assert "live_action_rows=row-1" in rows["o_po_draft_file_shape_preview"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_po_draft_file_shape_preview_fails_false_ready_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_po_draft_file_shape_preview_lines_live.csv",
        _file_shape_preview_headers(),
        [
            {
                "shape_utc": OBSERVED,
                "po_draft_file_shape_preview_id": "file-shape-1",
                "po_draft_hold_review_id": "hold-review-1",
                "po_draft_packet_review_id": "packet-review-1",
                "po_line_design_packet_id": "line-design-packet-1",
                "approval_packet_id": "packet-1",
                "source_hold_utc": OBSERVED,
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "title": "Product",
                "supplier_sku": "SUP1",
                "barcode": "123",
                "file_shape_qty": "2",
                "file_shape_unit_cost_gbp": "3",
                "file_shape_line_value_gbp": "6",
                "source_hold_review_line_state": "blocked_from_local_po_draft_hold_review",
                "source_po_file_write_allowed": "0",
                "source_po_creation_allowed": "0",
                "source_purchase_commitment_allowed": "0",
                "source_receiving_allowed": "0",
                "source_send_to_amazon_allowed": "0",
                "source_creates_live_action": "0",
                "file_shape_line_state": "ready_for_local_po_draft_file_shape_review_only",
                "file_shape_block_reasons": "",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_po_draft_file_shape_preview"]["status"] == "fail"
    assert rows["o_po_draft_file_shape_preview"]["value"] == (
        "unknown_state_rows=0;false_ready_rows=1;missing_block_reason_rows=0"
    )
    assert "false_ready_rows=row-1" in rows["o_po_draft_file_shape_preview"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_po_preview_construction_summary_fails_live_action_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_po_preview_construction_summary_live.csv",
        _construction_summary_headers(),
        _construction_summary_rows(live_action_stage="po_draft_file_shape"),
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_po_preview_construction_summary"]["status"] == "fail"
    assert rows["o_po_preview_construction_summary"]["value"] == "live_action_rows=1;live_language_rows=0"
    assert "live_action_rows=po_draft_file_shape" in rows["o_po_preview_construction_summary"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_po_preview_construction_summary_fails_stage_health_bad(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_po_preview_construction_summary_live.csv",
        _construction_summary_headers(),
        _construction_summary_rows(bad_health_stage="po_draft_packet_review"),
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_po_preview_construction_summary"]["status"] == "fail"
    assert rows["o_po_preview_construction_summary"]["value"] == "stage_health_bad_rows=1;health_bad=0"
    assert "stage_health_bad_rows=po_draft_packet_review" in rows["o_po_preview_construction_summary"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_po_draft_review_controls_fails_live_action_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_po_draft_review_controls_live.csv",
        _review_control_headers(),
        [_review_control_row(po_file_write_allowed="1")],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_po_draft_review_controls"]["status"] == "fail"
    assert rows["o_po_draft_review_controls"]["value"] == "live_action_rows=1;live_language_rows=0"
    assert "live_action_rows=file-shape-1" in rows["o_po_draft_review_controls"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_po_draft_review_controls_fails_false_ready_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_po_draft_review_controls_live.csv",
        _review_control_headers(),
        [
            _review_control_row(
                source_state="blocked_from_local_po_draft_file_shape_review",
                ready_count="0",
                blocked_count="1",
            )
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_po_draft_review_controls"]["status"] == "fail"
    assert rows["o_po_draft_review_controls"]["value"] == (
        "unknown_state_rows=0;false_ready_rows=1;missing_reason_rows=0"
    )
    assert "false_ready_rows=file-shape-1" in rows["o_po_draft_review_controls"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_po_draft_export_preview_fails_live_action_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_po_draft_export_preview_lines_live.csv",
        _export_preview_headers(),
        [_export_preview_row(po_file_write_allowed="1")],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_po_draft_export_preview"]["status"] == "fail"
    assert rows["o_po_draft_export_preview"]["value"] == (
        "source_action_rows=0;control_action_rows=0;live_action_rows=1;live_language_rows=0"
    )
    assert "live_action_rows=row-1" in rows["o_po_draft_export_preview"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_po_draft_export_preview_fails_false_ready_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_po_draft_export_preview_lines_live.csv",
        _export_preview_headers(),
        [
            _export_preview_row(
                source_state="ready_for_local_po_draft_file_shape_review_only",
                control_state="local_po_draft_keep_on_hold",
            )
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_po_draft_export_preview"]["status"] == "fail"
    assert rows["o_po_draft_export_preview"]["value"] == (
        "unknown_state_rows=0;false_ready_rows=1;missing_block_reason_rows=0;bad_summary_rows=0"
    )
    assert "false_ready_rows=row-1" in rows["o_po_draft_export_preview"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_po_draft_export_gate_fails_live_action_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_po_draft_export_gate_live.csv",
        _export_gate_headers(),
        [_export_gate_row(po_file_write_allowed="1")],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_po_draft_export_gate"]["status"] == "fail"
    assert rows["o_po_draft_export_gate"]["value"] == "live_action_rows=1;live_language_rows=0"
    assert "live_action_rows=export-preview-1" in rows["o_po_draft_export_gate"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_po_draft_export_gate_fails_false_ready_claim(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_po_draft_export_gate_live.csv",
        _export_gate_headers(),
        [
            _export_gate_row(
                source_state="blocked_from_local_po_draft_export_preview",
                ready_count="0",
                blocked_count="1",
            )
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["o_po_draft_export_gate"]["status"] == "fail"
    assert rows["o_po_draft_export_gate"]["value"] == (
        "unknown_state_rows=0;false_ready_rows=1;missing_reason_rows=0"
    )
    assert "false_ready_rows=export-preview-1" in rows["o_po_draft_export_gate"]["actual_proof"]
    assert rows["o_user_working_readiness"]["status"] == "fail"


def test_o_market_proof_gate_needs_luke_when_h_owns_market_files(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path, h_active=True)

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    item = next(row for row in worklist_rows if row["check"] == "o_h_market_proof_gate")

    assert result["status"] == "decision_needed"
    assert rows["o_h_market_proof_gate"]["luke_action_required"] == "1"
    assert item["status"] == "blocked_needs_luke"
    assert "no market proof scan outside a manager-approved controlled proof packet" in item["forbidden_actions"]


def test_o_market_proof_gate_becomes_approved_work_when_technical_pause_is_authorised(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path, h_active=True)
    output_dir = tmp_path / "out" / "systems" / "M"

    blocked_result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    write_hourly_mot_outputs(blocked_result, output_dir)
    _write_active_autonomy_policy(tmp_path)

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, output_dir)
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    item = next(row for row in worklist_rows if row["check"] == "o_h_market_proof_gate")

    assert result["status"] == "warn"
    assert rows["o_h_market_proof_gate"]["luke_action_required"] == "0"
    assert "prove H scheduler ownership resumed" in rows["o_h_market_proof_gate"]["manager_action"]
    assert item["status"] == "new"
    assert item["luke_action_required"] == "0"
    assert "Controlled technical H pause/resume" in item["safe_repair_boundary"]


def test_o_market_proof_gate_parks_in_quiet_autonomy_until_h_controller_is_installed(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path, h_active=True)
    output_dir = tmp_path / "out" / "systems" / "M"

    blocked_result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    write_hourly_mot_outputs(blocked_result, output_dir)
    _write_quiet_autonomy_policy(tmp_path)

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, output_dir)
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    item = next(row for row in worklist_rows if row["check"] == "o_h_market_proof_gate")

    assert result["status"] == "ok"
    assert rows["o_h_market_proof_gate"]["status"] == "not_checked"
    assert rows["o_h_market_proof_gate"]["luke_action_required"] == "0"
    assert "Park the O/H market-proof pause lane" in rows["o_h_market_proof_gate"]["manager_action"]
    assert item["status"] == "parked"
    assert item["luke_action_required"] == "0"
    assert "Quiet Autonomy" in item["notes"]


def test_o_market_proof_gate_reopens_when_quiet_autonomy_has_h_controller_proof(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path, h_active=True)
    _write_quiet_autonomy_policy(tmp_path)
    _write_h_controller_install_status(tmp_path, installed=True, success=True)

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    item = next(row for row in worklist_rows if row["check"] == "o_h_market_proof_gate")

    assert result["status"] == "warn"
    assert rows["o_h_market_proof_gate"]["luke_action_required"] == "0"
    assert "prove H scheduler ownership resumed" in rows["o_h_market_proof_gate"]["manager_action"]
    assert item["status"] == "new"


def test_o_h_maintenance_controller_gate_needs_admin_install_decision(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    install_path = tmp_path / "out" / "locks" / "h_maintenance_controller_install_status.json"
    install_path.parent.mkdir(parents=True, exist_ok=True)
    install_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "installed": False,
                "success": False,
                "failure_reason": "administrator_required",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    item = next(row for row in worklist_rows if row["check"] == "o_h_maintenance_controller_gate")

    assert result["status"] == "decision_needed"
    assert rows["o_h_maintenance_controller_gate"]["luke_action_required"] == "1"
    assert item["status"] == "blocked_needs_luke"
    assert "one-time H maintenance controller installer" in rows["o_h_maintenance_controller_gate"]["manager_action"]


def test_o_h_maintenance_controller_gate_parks_admin_install_in_quiet_autonomy(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    _write_h_controller_install_status(
        tmp_path,
        installed=False,
        success=False,
        failure_reason="administrator_required",
    )
    output_dir = tmp_path / "out" / "systems" / "M"

    blocked_result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    write_hourly_mot_outputs(blocked_result, output_dir)
    _write_quiet_autonomy_policy(tmp_path)

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, output_dir)
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    item = next(row for row in worklist_rows if row["check"] == "o_h_maintenance_controller_gate")

    assert result["status"] == "ok"
    assert rows["o_h_maintenance_controller_gate"]["status"] == "not_checked"
    assert rows["o_h_maintenance_controller_gate"]["luke_action_required"] == "0"
    assert "Park H pause/resume automation" in rows["o_h_maintenance_controller_gate"]["manager_action"]
    assert item["status"] == "parked"
    assert item["luke_action_required"] == "0"


def test_o_h_maintenance_controller_gate_parks_failed_install_in_quiet_autonomy(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    _write_h_controller_install_status(
        tmp_path,
        installed=False,
        success=False,
        failure_reason="scheduled_task_registration_failed",
    )
    output_dir = tmp_path / "out" / "systems" / "M"

    blocked_result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    write_hourly_mot_outputs(blocked_result, output_dir)
    _write_quiet_autonomy_policy(tmp_path)

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, output_dir)
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    item = next(row for row in worklist_rows if row["check"] == "o_h_maintenance_controller_gate")

    assert result["status"] == "ok"
    assert rows["o_h_maintenance_controller_gate"]["status"] == "not_checked"
    assert rows["o_h_maintenance_controller_gate"]["luke_action_required"] == "0"
    assert "controller_install_not_proven_parked_quiet_autonomy" in rows["o_h_maintenance_controller_gate"]["value"]
    assert item["status"] == "parked"
    assert item["luke_action_required"] == "0"


def test_o_buy_ready_guardrail_fails_when_action_ready_lacks_safe_proof(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path, unsafe_action_ready=True)

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    item = next(row for row in worklist_rows if row["check"] == "o_buy_ready_guardrails")

    assert result["status"] == "fail"
    assert rows["o_buy_ready_guardrails"]["status"] == "fail"
    assert rows["o_user_working_readiness"]["status"] == "fail"
    assert "missing_cost" in rows["o_buy_ready_guardrails"]["actual_proof"]
    assert "no PO creation" in item["safe_repair_boundary"]


def test_f_visible_login_request_creates_luke_decision_without_browser_action(tmp_path: Path) -> None:
    _write_f_outputs(tmp_path)
    request_path = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "f061_visible_login.requested"
    request_path.write_text(
        f"requested_by=FPM160_f061_visible_login_maintenance\nstatus=requested\nrequested_utc={OBSERVED}\n",
        encoding="utf-8",
    )

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    item = next(row for row in worklist_rows if row["check"] == "f_visible_login_control_proof")

    assert result["status"] == "decision_needed"
    assert rows["f_visible_login_control_proof"]["status"] == "decision_needed"
    assert rows["f_visible_login_control_proof"]["luke_action_required"] == "1"
    assert "no separate Chrome login window" in item["safe_repair_boundary"]
    assert "no F061 run" in item["forbidden_actions"]


def test_f_email_price_list_waiting_is_visible_without_worklist(tmp_path: Path) -> None:
    _write_f_outputs(tmp_path, email_source_state="waiting")

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))

    assert result["status"] == "warn"
    assert rows["f_email_price_list_source_proof"]["status"] == "warn"
    assert rows["f_email_price_list_source_proof"]["value"] == "warn=1"
    assert not any(row["check"] == "f_email_price_list_source_proof" for row in worklist_rows)


def test_f_email_price_list_fetch_error_with_fresh_prior_import_is_visible_as_ok(tmp_path: Path) -> None:
    _write_f_outputs(tmp_path, email_source_state="fetch_error")

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))

    assert rows["f_email_price_list_source_proof"]["status"] == "ok"
    assert rows["f_email_price_list_source_proof"]["value"] == "ready=1"
    assert "reason=gmail_fetch_error_prior_import_proven" in rows["f_email_price_list_source_proof"]["actual_proof"]
    assert "source_rows=8745;valid_rows=5770" in rows["f_email_price_list_source_proof"]["actual_proof"]
    assert not any(row["check"] == "f_email_price_list_source_proof" for row in worklist_rows)


def test_f_email_price_list_fetch_error_uses_prior_import_age_for_warning(tmp_path: Path) -> None:
    _write_f_outputs(tmp_path, email_source_state="fetch_error", email_batch_age_hours=200.0)

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))

    assert rows["f_email_price_list_source_proof"]["status"] == "warn"
    assert rows["f_email_price_list_source_proof"]["value"] == "warn=1"
    assert "reason=gmail_fetch_error_prior_import_getting_old" in rows["f_email_price_list_source_proof"]["actual_proof"]
    assert "age_hours=200.00;import_age_hours=200.00" in rows["f_email_price_list_source_proof"]["actual_proof"]
    assert not any(row["check"] == "f_email_price_list_source_proof" for row in worklist_rows)


def test_f_email_price_list_fetch_error_without_prior_import_still_fails(tmp_path: Path) -> None:
    _write_f_outputs(tmp_path, email_source_state="fetch_error", email_batch_imported=False)

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    item = next(row for row in worklist_rows if row["check"] == "f_email_price_list_source_proof")

    assert rows["f_email_price_list_source_proof"]["status"] == "fail"
    assert rows["f_email_price_list_source_proof"]["value"] == "fail=1"
    assert "reason=gmail_fetch_error" in rows["f_email_price_list_source_proof"]["actual_proof"]
    assert item["work_item_id"] == "MOT_F_F_EMAIL_PRICE_LIST_SOURCE_PROOF"


def test_f_email_price_list_missing_source_creates_bounded_worklist_item(tmp_path: Path) -> None:
    _write_f_outputs(tmp_path, missing_email_source=True)

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    item = next(row for row in worklist_rows if row["check"] == "f_email_price_list_source_proof")

    assert result["status"] == "fail"
    assert rows["f_email_price_list_source_proof"]["status"] == "fail"
    assert item["work_item_id"] == "MOT_F_F_EMAIL_PRICE_LIST_SOURCE_PROOF"
    assert "no Gmail fetch" in item["safe_repair_boundary"]
    assert "no F061 run" in item["forbidden_actions"]


def test_f_source_intake_missing_status_creates_bounded_worklist_item(tmp_path: Path) -> None:
    _write_f_outputs(tmp_path, missing_email_source=True)

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    item = next(row for row in worklist_rows if row["check"] == "f_source_intake_chain_proof")

    assert result["status"] == "fail"
    assert rows["f_source_intake_chain_proof"]["status"] == "fail"
    assert item["work_item_id"] == "MOT_F_F_SOURCE_INTAKE_CHAIN_PROOF"
    assert "no ready-source import" in item["safe_repair_boundary"]
    assert "no F061 run" in item["forbidden_actions"]


def test_f_source_intake_failed_email_source_with_prior_import_is_warning(tmp_path: Path) -> None:
    _write_f_outputs(tmp_path, email_source_state="fetch_error", email_batch_age_hours=200.0)

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))

    assert rows["f_source_intake_chain_proof"]["status"] == "warn"
    assert rows["f_source_intake_chain_proof"]["value"] == "source_failed_import_fallback=1"
    assert "source_failed_import_fallback=abgee" in rows["f_source_intake_chain_proof"]["actual_proof"]
    assert not any(row["check"] == "f_source_intake_chain_proof" for row in worklist_rows)


def test_f_source_intake_failed_email_source_without_prior_import_still_fails(tmp_path: Path) -> None:
    _write_f_outputs(tmp_path, email_source_state="fetch_error", email_batch_imported=False)

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    item = next(row for row in worklist_rows if row["check"] == "f_source_intake_chain_proof")

    assert rows["f_source_intake_chain_proof"]["status"] == "fail"
    assert rows["f_source_intake_chain_proof"]["value"] == "failed=1"
    assert "failed=abgee" in rows["f_source_intake_chain_proof"]["actual_proof"]
    assert item["work_item_id"] == "MOT_F_F_SOURCE_INTAKE_CHAIN_PROOF"


def test_f_url_source_missing_status_creates_bounded_worklist_item(tmp_path: Path) -> None:
    _write_f_outputs(tmp_path, missing_url_source=True)

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    item = next(row for row in worklist_rows if row["check"] == "f_url_source_download_proof")

    assert result["status"] == "fail"
    assert rows["f_url_source_download_proof"]["status"] == "fail"
    assert item["work_item_id"] == "MOT_F_F_URL_SOURCE_DOWNLOAD_PROOF"
    assert "no remote supplier check" in item["safe_repair_boundary"]
    assert "no F061 run" in item["forbidden_actions"]


def test_f_email_price_list_missing_oauth_needs_luke_decision(tmp_path: Path) -> None:
    _write_f_outputs(tmp_path, missing_gmail_oauth=True)

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    item = next(row for row in worklist_rows if row["check"] == "f_email_price_list_source_proof")

    assert result["status"] == "decision_needed"
    assert rows["f_email_price_list_source_proof"]["status"] == "decision_needed"
    assert rows["f_email_price_list_source_proof"]["luke_action_required"] == "1"
    assert item["status"] == "blocked_needs_luke"
    assert "no attachment download" in item["safe_repair_boundary"]


def test_f_parked_backtrack_row_creates_luke_decision(tmp_path: Path) -> None:
    _write_f_outputs(tmp_path, parked_decision=True)

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    item = next(row for row in worklist_rows if row["check"] == "f_parked_decision_rows")

    assert result["status"] == "decision_needed"
    assert rows["f_parked_decision_rows"]["status"] == "decision_needed"
    assert rows["f_parked_decision_rows"]["luke_action_required"] == "1"
    assert item["work_item_id"] == "MOT_F_F_PARKED_DECISION_ROWS"
    assert item["status"] == "blocked_needs_luke"
    assert "no F061 run" in item["forbidden_actions"]


def test_f_parked_backtrack_row_is_parked_in_quiet_autonomy(tmp_path: Path) -> None:
    _write_f_outputs(tmp_path, parked_decision=True)
    output_dir = tmp_path / "out" / "systems" / "M"

    blocked_result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    write_hourly_mot_outputs(blocked_result, output_dir)
    _write_quiet_autonomy_policy(tmp_path)

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, output_dir)
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    item = next(row for row in worklist_rows if row["check"] == "f_parked_decision_rows")

    assert result["status"] == "ok"
    assert rows["f_parked_decision_rows"]["status"] == "not_checked"
    assert rows["f_parked_decision_rows"]["luke_action_required"] == "0"
    assert "parked_quiet_autonomy" in rows["f_parked_decision_rows"]["value"]
    assert item["status"] == "parked"
    assert item["luke_action_required"] == "0"


def test_f_stale_child_heartbeat_creates_bounded_worklist_item(tmp_path: Path) -> None:
    _write_f_outputs(tmp_path, stale_child=True)

    result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    item = next(row for row in worklist_rows if row["check"] == "f_child_scanner_heartbeat")

    assert result["status"] == "fail"
    assert rows["f_child_scanner_heartbeat"]["status"] == "fail"
    assert item["work_item_id"] == "MOT_F_F_CHILD_SCANNER_HEARTBEAT"
    assert "no worker restart" in item["safe_repair_boundary"]


def test_e_stale_required_output_creates_bounded_worklist_item(tmp_path: Path) -> None:
    _write_e_manifest(tmp_path)
    _write_e_run_log(tmp_path)
    _write_e_input_proofs(tmp_path)
    _write_e_required_outputs(tmp_path, stale_name="sales_velocity")
    _write_e_coverage_summary(tmp_path)
    _write_e_health(tmp_path)

    result = build_e_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    work_item = next(row for row in worklist_rows if row["check"] == "e_core_outputs_fresh")

    assert result["status"] == "fail"
    assert work_item["work_item_id"] == "MOT_E_E_CORE_OUTPUTS_FRESH"
    assert "no E worker run" in work_item["forbidden_actions"]
    assert "no E live run" in work_item["safe_repair_boundary"]


def test_e_bad_schema_creates_schema_contract_failure(tmp_path: Path) -> None:
    _write_e_manifest(tmp_path)
    _write_e_run_log(tmp_path)
    _write_e_input_proofs(tmp_path)
    _write_e_required_outputs(tmp_path, bad_schema_name="roi_snapshot")
    _write_e_coverage_summary(tmp_path)
    _write_e_health(tmp_path)

    result = build_e_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["e_schema_contracts"]["status"] == "fail"
    assert "roi_snapshot" in rows["e_schema_contracts"]["value"]


def test_e_missing_input_creates_input_readiness_failure(tmp_path: Path) -> None:
    _write_e_manifest(tmp_path)
    _write_e_run_log(tmp_path)
    _write_e_input_proofs(tmp_path)
    _write_e_required_outputs(tmp_path)
    _write_e_coverage_summary(tmp_path)
    _write_e_health(tmp_path)
    (tmp_path / "out" / "token_cogs_ledger.csv").unlink()

    result = build_e_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["e_input_readiness"]["status"] == "fail"
    assert rows["e_input_readiness"]["value"] == "cogs:missing_or_unreadable"


def test_e_low_roi_coverage_is_a_warning_not_hidden(tmp_path: Path) -> None:
    _write_e_manifest(tmp_path)
    _write_e_run_log(tmp_path)
    _write_e_input_proofs(tmp_path)
    _write_e_required_outputs(tmp_path)
    _write_e_coverage_summary(tmp_path)
    _write_e_health(tmp_path)
    path = tmp_path / "out" / "sku_performance_summary.csv"
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    rows.append(
        {
            **rows[-1],
            "sku": "SKU3",
            "units_sold_source": "velocity",
            "profit_confidence": "profit_missing",
            "sales_truth_state": "velocity_only",
            "missing_reason": "velocity_only_sales_truth",
            "missing_roi_reason": "velocity_only_sales_truth",
            "missing_roi_reason_detail": "velocity_only_sales_truth",
        }
    )
    _write_csv_rows(path, list(rows[0].keys()), rows)

    result = build_e_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    mot_rows = {row["check"]: row for row in result["rows"]}

    assert mot_rows["e_roi_coverage"]["status"] == "warn"
    assert "velocity_only_skus=2" in mot_rows["e_roi_coverage"]["value"]
    assert mot_rows["e_missing_roi_reasons_live"]["status"] == "ok"


def test_e_missing_roi_reason_check_fails_blank_reason(tmp_path: Path) -> None:
    _write_e_manifest(tmp_path)
    _write_e_run_log(tmp_path)
    _write_e_input_proofs(tmp_path)
    _write_e_required_outputs(tmp_path)
    _write_e_coverage_summary(tmp_path)
    _write_e_health(tmp_path)
    path = tmp_path / "out" / "sku_performance_summary.csv"
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    rows[1]["missing_roi_reason"] = ""
    rows[1]["missing_roi_reason_detail"] = ""
    _write_csv_rows(path, list(rows[0].keys()), rows)

    result = build_e_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    mot_rows = {row["check"]: row for row in result["rows"]}

    assert mot_rows["e_missing_roi_reasons_live"]["status"] == "fail"
    assert "missing_reason_rows=1" in mot_rows["e_missing_roi_reasons_live"]["value"]


def test_e_warns_when_b_money_truth_is_bridge_only(tmp_path: Path) -> None:
    _write_e_manifest(tmp_path)
    _write_e_run_log(tmp_path)
    _write_e_input_proofs(tmp_path)
    _write_e_required_outputs(tmp_path)
    _write_e_coverage_summary(tmp_path)
    _write_e_health(tmp_path)
    _write_b_sellerboard_bridge_outputs(tmp_path, return_gap=1, fee_detail_rows=0, refund_nonzero_rows=0)

    result = build_e_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    mot_rows = {row["check"]: row for row in result["rows"]}

    assert mot_rows["e_b_money_truth_dependency"]["status"] == "warn"
    assert "b_roi_money_confidence_state=not_yet_proven" in mot_rows["e_b_money_truth_dependency"]["value"]
    assert "commission_api_proof_state=not_yet_proven" in mot_rows["e_b_money_truth_dependency"]["actual_proof"]
    assert "bridge_values_safe_for_live_roi=0" in mot_rows["e_b_money_truth_dependency"]["actual_proof"]


def test_e_money_truth_dependency_prefers_current_b067_money_review(tmp_path: Path) -> None:
    _write_e_manifest(tmp_path)
    _write_e_run_log(tmp_path)
    _write_e_input_proofs(tmp_path)
    _write_e_required_outputs(tmp_path)
    _write_e_coverage_summary(tmp_path)
    _write_e_health(tmp_path)
    _write_b_sellerboard_bridge_outputs(tmp_path, return_gap=1, fee_detail_rows=0, refund_nonzero_rows=0)
    _write_b_refund_fee_shipping_gap_review(tmp_path)

    result = build_e_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    mot_rows = {row["check"]: row for row in result["rows"]}
    money_row = mot_rows["e_b_money_truth_dependency"]

    assert money_row["status"] == "warn"
    assert "b_roi_money_confidence_state=bridge_labelled_only" in money_row["value"]
    assert "refund_api_proof_state=api_proved" in money_row["actual_proof"]
    assert "sellerboard_return_gap_state=sellerboard_bridge_estimate" in money_row["actual_proof"]
    assert "commission_api_proof_state=api_proved" in money_row["actual_proof"]
    assert "fba_fee_api_proof_state=api_proved" in money_row["actual_proof"]
    assert "shipping_income_api_proof_state=api_proved" in money_row["actual_proof"]
    assert "shipping_fee_api_proof_state=not_yet_proven" in money_row["actual_proof"]
    assert "b_money_source=b067_refund_fee_shipping_gap_review" in money_row["actual_proof"]


def test_e_money_truth_dependency_is_ok_when_b_money_is_api_backed(tmp_path: Path) -> None:
    _write_e_manifest(tmp_path)
    _write_e_run_log(tmp_path)
    _write_e_input_proofs(tmp_path)
    _write_e_required_outputs(tmp_path)
    _write_e_coverage_summary(tmp_path)
    _write_e_health(tmp_path)
    _write_b_sellerboard_bridge_outputs(tmp_path)

    result = build_e_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    mot_rows = {row["check"]: row for row in result["rows"]}

    assert mot_rows["e_b_money_truth_dependency"]["status"] == "ok"
    assert "b_roi_money_confidence_state=api_backed_safe" in mot_rows["e_b_money_truth_dependency"]["value"]


def test_e_blank_daily_truth_is_ok_when_sales_truth_explains_row(tmp_path: Path) -> None:
    _write_e_manifest(tmp_path)
    _write_e_run_log(tmp_path)
    _write_e_input_proofs(tmp_path)
    _write_e_required_outputs(tmp_path)
    _write_e_coverage_summary(tmp_path)
    _write_e_health(tmp_path)
    path = tmp_path / "out" / "e_study_report.csv"
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    rows[1]["latest_daily_truth_state"] = ""
    rows[1]["sales_truth_state"] = "velocity_only"
    rows[1]["missing_reason"] = "stock_only_no_sales_window"
    _write_csv_rows(path, list(rows[0].keys()), rows)

    result = build_e_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    mot_rows = {row["check"]: row for row in result["rows"]}

    assert mot_rows["e_daily_truth_coverage"]["status"] == "ok"
    assert "unexplained_truth_rows=0" in mot_rows["e_daily_truth_coverage"]["value"]


def test_e_unexplained_blank_daily_truth_remains_warning(tmp_path: Path) -> None:
    _write_e_manifest(tmp_path)
    _write_e_run_log(tmp_path)
    _write_e_input_proofs(tmp_path)
    _write_e_required_outputs(tmp_path)
    _write_e_coverage_summary(tmp_path)
    _write_e_health(tmp_path)
    path = tmp_path / "out" / "e_study_report.csv"
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    rows[1]["latest_daily_truth_state"] = ""
    rows[1]["sales_truth_state"] = ""
    rows[1]["missing_reason"] = ""
    _write_csv_rows(path, list(rows[0].keys()), rows)

    result = build_e_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    mot_rows = {row["check"]: row for row in result["rows"]}

    assert mot_rows["e_daily_truth_coverage"]["status"] == "warn"
    assert "unexplained_truth_rows=1" in mot_rows["e_daily_truth_coverage"]["value"]


def test_e_restock_ready_without_clean_profit_is_a_failure(tmp_path: Path) -> None:
    _write_e_manifest(tmp_path)
    _write_e_run_log(tmp_path)
    _write_e_input_proofs(tmp_path)
    _write_e_required_outputs(tmp_path)
    _write_e_coverage_summary(tmp_path)
    _write_e_health(tmp_path)
    path = tmp_path / "out" / "sku_performance_summary.csv"
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    rows[1]["restock_business_ready"] = "yes"
    rows[1]["profit_confidence"] = "profit_missing"
    _write_csv_rows(path, list(rows[0].keys()), rows)

    result = build_e_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    mot_rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert mot_rows["e_restock_profit_guard"]["status"] == "fail"
    assert mot_rows["e_restock_profit_guard"]["value"] == "restock_ready_without_clean_profit=1"


def test_e_restock_ready_input_model_fails_false_ready_row(tmp_path: Path) -> None:
    _write_e_manifest(tmp_path)
    _write_e_run_log(tmp_path)
    _write_e_input_proofs(tmp_path)
    _write_e_required_outputs(tmp_path)
    _write_e_coverage_summary(tmp_path)
    _write_e_health(tmp_path)
    path = tmp_path / "out" / "sku_performance_summary.csv"
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    rows[0]["reorder_flag"] = "yes"
    rows[0]["stock_signal"] = "yes"
    rows[0]["restock_business_ready"] = "yes"
    rows[0]["latest_price_confidence"] = "listing_price_unproven"
    rows[0]["restock_decision_state"] = "business_ready_clean"
    rows[0]["restock_readiness_confidence"] = "clean"
    rows[0]["restock_missing_proof"] = ""
    _write_csv_rows(path, list(rows[0].keys()), rows)

    result = build_e_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    mot_rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert mot_rows["e_restock_ready_input_model_live"]["status"] == "fail"
    assert "false_ready_rows=1" in mot_rows["e_restock_ready_input_model_live"]["value"]


def test_e_restock_ready_input_model_fails_bridge_labelled_clean_claim(tmp_path: Path) -> None:
    _write_e_manifest(tmp_path)
    _write_e_run_log(tmp_path)
    _write_e_input_proofs(tmp_path)
    _write_e_required_outputs(tmp_path)
    _write_e_coverage_summary(tmp_path)
    _write_e_health(tmp_path)
    path = tmp_path / "out" / "sku_performance_summary.csv"
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    rows[0]["reorder_flag"] = "yes"
    rows[0]["stock_signal"] = "yes"
    rows[0]["restock_business_ready"] = "yes"
    rows[0]["b_money_confidence_state"] = "bridge_labelled_only"
    rows[0]["b_bridge_values_safe_for_live_roi"] = "0"
    rows[0]["restock_decision_state"] = "business_ready_clean"
    rows[0]["restock_readiness_confidence"] = "clean"
    rows[0]["restock_missing_proof"] = ""
    _write_csv_rows(path, list(rows[0].keys()), rows)

    result = build_e_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    mot_rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert mot_rows["e_restock_ready_input_model_live"]["status"] == "fail"
    assert "bridge_clean_rows=1" in mot_rows["e_restock_ready_input_model_live"]["value"]


def test_e_restock_ready_input_model_warns_when_fields_not_live(tmp_path: Path) -> None:
    _write_e_manifest(tmp_path)
    _write_e_run_log(tmp_path)
    _write_e_input_proofs(tmp_path)
    _write_e_required_outputs(tmp_path)
    _write_e_coverage_summary(tmp_path)
    _write_e_health(tmp_path)
    path = tmp_path / "out" / "sku_performance_summary.csv"
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    columns = [column for column in rows[0].keys() if column != "restock_decision_state"]
    _write_csv_rows(path, columns, rows)

    result = build_e_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    mot_rows = {row["check"]: row for row in result["rows"]}

    assert mot_rows["e_restock_ready_input_model_live"]["status"] == "warn"
    assert mot_rows["e_restock_ready_input_model_live"]["value"] == "restock_ready_input_fields_not_live_yet"


def test_b_old_checklist_fail_is_only_a_clue(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_csv(tmp_path / "out" / "cycle_alerts" / "checklist_B_split.csv")
    checklist = tmp_path / "out" / "cycle_alerts" / "checklist_B_split.csv"
    with checklist.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["check", "status", "value", "notes"])
        writer.writeheader()
        writer.writerow({"check": "legacy_fail", "status": "fail", "value": "1", "notes": "old clue"})

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "ok"
    assert rows["b_old_checklist_clue"]["status"] == "not_checked"
    assert "fail=1" in rows["b_old_checklist_clue"]["value"]


def test_b_stale_output_creates_worklist_item(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path, stale_check="b_orders_all")
    _write_b_locks(tmp_path)

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    work_item = next(row for row in worklist_rows if row["check"] == "b_orders_all")

    assert result["status"] == "fail"
    assert work_item["work_item_id"] == "MOT_B_B_ORDERS_ALL"
    assert "no B run or restart" in work_item["forbidden_actions"]


def test_blocked_mot_item_sets_luke_action_required(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path, stale_check="b_orders_all")
    _write_b_locks(tmp_path)
    output_dir = tmp_path / "out" / "systems" / "M"

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    write_hourly_mot_outputs(result, output_dir)
    updated = update_mot_work_item_status(
        output_dir=output_dir,
        work_item_id="MOT_B_B_ORDERS_ALL",
        status="blocked_needs_luke",
        observed_utc=OBSERVED,
    )

    assert updated["status"] == "blocked_needs_luke"
    assert updated["luke_action_required"] == "1"


def test_b_stale_heartbeat_creates_worklist_item(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path, worker_heartbeat_age_minutes=60.0)

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    work_item = next(row for row in worklist_rows if row["check"] == "b_worker_owner")

    assert result["status"] == "fail"
    assert work_item["work_item_id"] == "MOT_B_B_WORKER_OWNER"
    assert "no lock deletion" in work_item["safe_repair_boundary"]


def test_b_duplicate_owner_creates_worklist_item(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path, duplicate=True)

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["b_worker_owner"]["value"] == "duplicate_owner"


def test_b_sellerboard_bridge_missing_order_creates_bounded_worklist_item(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_b_sellerboard_bridge_outputs(tmp_path, missing_orders=1)

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    work_item = next(row for row in worklist_rows if row["check"] == "b_sellerboard_order_reconciliation")

    assert result["status"] == "fail"
    assert work_item["work_item_id"] == "MOT_B_B_SELLERBOARD_ORDER_RECONCILIATION"
    assert "no B run or restart" in work_item["forbidden_actions"]
    assert "no B run" in work_item["safe_repair_boundary"]


def test_b_sellerboard_refund_fee_gap_is_warning_worklist_item(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_b_sellerboard_bridge_outputs(tmp_path, return_gap=2, fee_detail_rows=0, refund_nonzero_rows=0)

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    work_item = next(row for row in worklist_rows if row["check"] == "b_sellerboard_refund_fee_roi_bridge")

    assert result["status"] == "warn"
    assert rows["b_sellerboard_refund_fee_roi_bridge"]["status"] == "warn"
    assert "commission_api_proof_state=not_yet_proven" in rows["b_sellerboard_refund_fee_roi_bridge"]["actual_proof"]
    assert "fee_shipping_proof_state=not_yet_proven" in rows["b_sellerboard_refund_fee_roi_bridge"]["actual_proof"]
    assert "roi_money_confidence_state=not_yet_proven" in rows["b_sellerboard_refund_fee_roi_bridge"]["actual_proof"]
    assert "bridge_values_safe_for_live_roi=0" in rows["b_sellerboard_refund_fee_roi_bridge"]["actual_proof"]


def test_b_refund_fee_shipping_gap_review_warns_and_creates_worklist_item(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_b_sellerboard_bridge_outputs(tmp_path)
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_fee_shipping_gap_review.csv",
        _refund_fee_shipping_gap_review_columns(),
        [
            {
                "money_area": "api_refund_money",
                "manager_money_label": "api_proved",
                "source_metric": "b_refund_pnl_bridge.api_refund_proof_state",
                "source_value": "api_rows=1",
                "api_proof_state": "api_proved",
                "sellerboard_witness_rows": "0",
                "gap_rows": "0",
                "downstream_warning_rows": "0",
                "live_roi_use_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "manager_expectation": "label money proof",
                "bounded_worker_task": "read only",
                "retest_rule": "rerun B067 and B MOT",
                "protected_stop_rule": "stop before ROI use",
                "source_path": "refund.csv",
            },
            {
                "money_area": "commission_fee",
                "manager_money_label": "not_yet_proven",
                "source_metric": "commission_api_proof_state",
                "source_value": "not_yet_proven",
                "api_proof_state": "not_yet_proven",
                "sellerboard_witness_rows": "1",
                "gap_rows": "1",
                "downstream_warning_rows": "0",
                "live_roi_use_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "manager_expectation": "label money proof",
                "bounded_worker_task": "read only",
                "retest_rule": "rerun B067 and B MOT",
                "protected_stop_rule": "stop before ROI use",
                "source_path": "sellerboard.csv",
            },
            {
                "money_area": "e_roi_confidence",
                "manager_money_label": "sellerboard_bridge_estimate",
                "source_metric": "out/sku_performance_summary.csv",
                "source_value": "bridge_rows=2",
                "api_proof_state": "bridge_labelled_only",
                "sellerboard_witness_rows": "1",
                "gap_rows": "2",
                "downstream_warning_rows": "2",
                "live_roi_use_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "manager_expectation": "label money proof",
                "bounded_worker_task": "read only",
                "retest_rule": "rerun B067 and B MOT",
                "protected_stop_rule": "stop before ROI use",
                "source_path": "performance.csv",
            },
        ],
    )
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_fee_shipping_gap_review_summary.csv",
        ["metric", "value"],
        [
            {"metric": "bridge_values_safe_for_live_roi", "value": "0"},
            {"metric": "e_downstream_warning_rows", "value": "2"},
            {"metric": "o_downstream_warning_rows", "value": "0"},
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    work_item = next(row for row in worklist_rows if row["check"] == "b_refund_fee_shipping_gap_review")

    assert rows["b_refund_fee_shipping_gap_review"]["status"] == "warn"
    assert "sellerboard_bridge_estimate=1" in rows["b_refund_fee_shipping_gap_review"]["actual_proof"]
    assert "not_yet_proven=1" in rows["b_refund_fee_shipping_gap_review"]["actual_proof"]
    assert "bridge_values_safe_for_live_roi=0" in rows["b_refund_fee_shipping_gap_review"]["actual_proof"]
    assert work_item["status"] == "parked"
    assert "no B run" in work_item["safe_repair_boundary"]
    assert "live ROI/restock use" in work_item["safe_repair_boundary"]


def test_b_refund_fee_shipping_gap_review_ok_when_only_downstream_consumers_warn(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_b_sellerboard_bridge_outputs(tmp_path)
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_fee_shipping_gap_review.csv",
        _refund_fee_shipping_gap_review_columns(),
        [
            {
                "money_area": "api_refund_money",
                "manager_money_label": "api_proved",
                "source_metric": "b_refund_pnl_bridge.api_refund_proof_state",
                "source_value": "api_rows=1",
                "api_proof_state": "api_proved",
                "sellerboard_witness_rows": "0",
                "gap_rows": "0",
                "downstream_warning_rows": "0",
                "live_roi_use_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "manager_expectation": "label money proof",
                "bounded_worker_task": "read only",
                "retest_rule": "rerun B067 and B MOT",
                "protected_stop_rule": "stop before ROI use",
                "source_path": "refund.csv",
            },
            {
                "money_area": "commission_fee",
                "manager_money_label": "api_proved",
                "source_metric": "commission_api_proof_state",
                "source_value": "api_proved",
                "api_proof_state": "api_proved",
                "sellerboard_witness_rows": "0",
                "gap_rows": "0",
                "downstream_warning_rows": "0",
                "live_roi_use_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "manager_expectation": "label money proof",
                "bounded_worker_task": "read only",
                "retest_rule": "rerun B067 and B MOT",
                "protected_stop_rule": "stop before ROI use",
                "source_path": "level3.csv",
            },
            {
                "money_area": "e_roi_confidence",
                "manager_money_label": "sellerboard_bridge_estimate",
                "source_metric": "out/sku_performance_summary.csv",
                "source_value": "bridge_rows=2",
                "api_proof_state": "bridge_labelled_only",
                "sellerboard_witness_rows": "0",
                "gap_rows": "2",
                "downstream_warning_rows": "2",
                "live_roi_use_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "manager_expectation": "label money proof",
                "bounded_worker_task": "read only",
                "retest_rule": "rerun B067 and B MOT",
                "protected_stop_rule": "stop before ROI use",
                "source_path": "performance.csv",
            },
        ],
    )
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_fee_shipping_gap_review_summary.csv",
        ["metric", "value"],
        [
            {"metric": "bridge_values_safe_for_live_roi", "value": "0"},
            {"metric": "b_source_api_proved_rows", "value": "2"},
            {"metric": "b_source_sellerboard_bridge_estimate_rows", "value": "0"},
            {"metric": "b_source_not_yet_proven_rows", "value": "0"},
            {"metric": "b_source_chain_state", "value": "api_proved"},
            {"metric": "b_source_handoff_ready", "value": "1"},
            {"metric": "downstream_consumer_warning_rows", "value": "2"},
            {"metric": "e_downstream_warning_rows", "value": "2"},
            {"metric": "o_downstream_warning_rows", "value": "0"},
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))

    assert rows["b_refund_fee_shipping_gap_review"]["status"] == "ok"
    assert "b_source_handoff_ready=1" in rows["b_refund_fee_shipping_gap_review"]["actual_proof"]
    assert "downstream_consumer_warning_rows=2" in rows["b_refund_fee_shipping_gap_review"]["actual_proof"]
    assert not any(row["check"] == "b_refund_fee_shipping_gap_review" for row in worklist_rows)


def test_b_refund_fee_shipping_gap_review_fails_on_unsafe_live_use(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_b_sellerboard_bridge_outputs(tmp_path)
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_fee_shipping_gap_review.csv",
        _refund_fee_shipping_gap_review_columns(),
        [
            {
                "money_area": "live_roi_safety_gate",
                "manager_money_label": "api_proved",
                "source_metric": "bridge_values_safe_for_live_roi",
                "source_value": "1",
                "api_proof_state": "api_backed_safe",
                "sellerboard_witness_rows": "0",
                "gap_rows": "0",
                "downstream_warning_rows": "0",
                "live_roi_use_allowed": "1",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "manager_expectation": "label money proof",
                "bounded_worker_task": "read only",
                "retest_rule": "rerun B067 and B MOT",
                "protected_stop_rule": "stop before ROI use",
                "source_path": "summary.csv",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_refund_fee_shipping_gap_review"]["status"] == "fail"
    assert "unsafe=live_roi_safety_gate" in rows["b_refund_fee_shipping_gap_review"]["actual_proof"]


def test_b_level3_fee_shipping_api_proof_map_warns_and_parks_unclear_paths(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_b_sellerboard_bridge_outputs(tmp_path)
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_level3_fee_shipping_api_proof_map.csv",
        _level3_fee_shipping_api_proof_map_columns(),
        [
            {
                "money_field": "commission",
                "api_source_file": "out/financial_events_level3_raw.csv",
                "source_amount_types": "Commission",
                "source_row_count": "10",
                "official_output_file": "out/financial_events_level3_official.csv",
                "official_output_field": "Commission_ExVAT",
                "official_output_row_count": "8",
                "order_master_row_count": "8",
                "required_keys_present": "1",
                "missing_required_keys": "",
                "proof_label": "api_source_available",
                "proof_reason": "Level 3 source exists.",
                "live_roi_use_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "bounded_worker_task": "read only",
                "retest_rule": "rerun B068 and B MOT",
                "protected_stop_rule": "stop before live API pull or ROI use",
            },
            {
                "money_field": "shipping_chargeback_or_cost",
                "api_source_file": "out/financial_events_level3_raw.csv",
                "source_amount_types": "ShippingChargeback",
                "source_row_count": "10",
                "official_output_file": "out/financial_events_level3_official.csv",
                "official_output_field": "",
                "official_output_row_count": "0",
                "order_master_row_count": "0",
                "required_keys_present": "1",
                "missing_required_keys": "",
                "proof_label": "repo_path_unclear",
                "proof_reason": "Source exists but the official field path is unclear.",
                "live_roi_use_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "bounded_worker_task": "read only",
                "retest_rule": "rerun B068 and B MOT",
                "protected_stop_rule": "stop before live API pull or ROI use",
            },
        ],
    )
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_level3_fee_shipping_api_proof_map_summary.csv",
        ["metric", "value"],
        [
            {"metric": "level3_raw_rows", "value": "100"},
            {"metric": "level3_official_rows", "value": "80"},
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    work_item = next(row for row in worklist_rows if row["check"] == "b_level3_fee_shipping_api_proof_map")

    assert rows["b_level3_fee_shipping_api_proof_map"]["status"] == "warn"
    assert "api_source_available=1" in rows["b_level3_fee_shipping_api_proof_map"]["actual_proof"]
    assert "repo_path_unclear=1" in rows["b_level3_fee_shipping_api_proof_map"]["actual_proof"]
    assert work_item["status"] == "parked"
    assert "no live Amazon API pull" in work_item["safe_repair_boundary"]
    assert "live ROI/restock use" in work_item["safe_repair_boundary"]


def test_b_level3_fee_shipping_api_proof_map_ok_when_servicefee_path_superseded(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_b_sellerboard_bridge_outputs(tmp_path)
    proof_rows = []
    for money_field, amount_types in [
        ("commission", "Commission"),
        ("fba_fee", "FBAPerUnitFulfillmentFee"),
        ("shipping_income", "ShippingCharge|ShippingTax"),
        ("shipping_chargeback_or_cost", "ShippingChargeback"),
        ("refund_fee_reversals", "Refund_Commission|Refund_ShippingChargeback"),
    ]:
        proof_rows.append(
            {
                "money_field": money_field,
                "api_source_file": "out/financial_events_level3_raw.csv",
                "source_amount_types": amount_types,
                "source_row_count": "10",
                "official_output_file": "out/financial_events_level3_official.csv",
                "official_output_field": money_field,
                "official_output_row_count": "8",
                "order_master_row_count": "8",
                "required_keys_present": "1",
                "missing_required_keys": "",
                "proof_label": "api_source_available",
                "proof_reason": "Current Level 3 API-backed source exists.",
                "live_roi_use_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "bounded_worker_task": "read only",
                "retest_rule": "rerun B068 and B MOT",
                "protected_stop_rule": "stop before live API pull or ROI use",
            }
        )
    proof_rows.append(
        {
            "money_field": "fee_detail_ledger_api",
            "api_source_file": "out/fee_detail_ledger_api.csv",
            "source_amount_types": "ServiceFee",
            "source_row_count": "0",
            "official_output_file": "out/financial_transactions_v2024_breakdowns.csv",
            "official_output_field": "transaction_breakdown_diagnostic",
            "official_output_row_count": "20",
            "order_master_row_count": "0",
            "required_keys_present": "1",
            "missing_required_keys": "",
            "proof_label": "superseded_non_blocking",
            "proof_reason": "Old ServiceFee path is empty, but the current Level 3 API-backed fields are present.",
            "live_roi_use_allowed": "0",
            "roi_or_restock_use_allowed": "0",
            "sellerboard_final_truth_allowed": "0",
            "bounded_worker_task": "read only",
            "retest_rule": "rerun B068 and B MOT",
            "protected_stop_rule": "stop before live API pull or ROI use",
        }
    )
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_level3_fee_shipping_api_proof_map.csv",
        _level3_fee_shipping_api_proof_map_columns(),
        proof_rows,
    )
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_level3_fee_shipping_api_proof_map_summary.csv",
        ["metric", "value"],
        [
            {"metric": "status", "value": "ok"},
            {"metric": "api_source_available_rows", "value": "5"},
            {"metric": "api_source_missing_rows", "value": "0"},
            {"metric": "repo_path_unclear_rows", "value": "0"},
            {"metric": "protected_live_pull_required_rows", "value": "0"},
            {"metric": "superseded_non_blocking_rows", "value": "1"},
            {"metric": "unsafe_rows", "value": "0"},
            {"metric": "level3_raw_rows", "value": "100"},
            {"metric": "level3_official_rows", "value": "80"},
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))

    assert rows["b_level3_fee_shipping_api_proof_map"]["status"] == "ok"
    assert "api_source_available=5" in rows["b_level3_fee_shipping_api_proof_map"]["actual_proof"]
    assert "superseded_non_blocking=1" in rows["b_level3_fee_shipping_api_proof_map"]["actual_proof"]
    assert not any(row["check"] == "b_level3_fee_shipping_api_proof_map" for row in worklist_rows)


def test_b_level3_fee_shipping_api_proof_map_fails_on_unsafe_live_use(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_b_sellerboard_bridge_outputs(tmp_path)
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_level3_fee_shipping_api_proof_map.csv",
        _level3_fee_shipping_api_proof_map_columns(),
        [
            {
                "money_field": "shipping_income",
                "api_source_file": "out/financial_events_level3_raw.csv",
                "source_amount_types": "ShippingCharge",
                "source_row_count": "10",
                "official_output_file": "out/financial_events_level3_official.csv",
                "official_output_field": "Shipping_ExVAT",
                "official_output_row_count": "8",
                "order_master_row_count": "8",
                "required_keys_present": "1",
                "missing_required_keys": "",
                "proof_label": "api_source_available",
                "proof_reason": "Level 3 source exists.",
                "live_roi_use_allowed": "1",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "bounded_worker_task": "read only",
                "retest_rule": "rerun B068 and B MOT",
                "protected_stop_rule": "stop before live API pull or ROI use",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_level3_fee_shipping_api_proof_map"]["status"] == "fail"
    assert "unsafe=shipping_income" in rows["b_level3_fee_shipping_api_proof_map"]["actual_proof"]


def test_b_fallback_token_cost_audit_warns_and_creates_board_job_for_weak_costs(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_b_completion_clean_inputs(tmp_path)
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_fallback_token_cost_audit.csv",
        [
            "token_id",
            "seller_sku",
            "cost_per_unit",
            "cost_proof_state",
            "manager_label",
            "manager_expectation",
            "bounded_worker_task",
            "retest_rule",
            "preview_live_write_allowed",
            "roi_or_restock_use_allowed",
            "protected_before_apply",
        ],
        [
            {
                "token_id": "ADJ-SKU-1-EVT-1-0001",
                "seller_sku": "SKU-1",
                "cost_per_unit": "4.51",
                "cost_proof_state": "fallback_cost_weak_latest_token",
                "manager_label": "weak_fallback_cost",
                "manager_expectation": "Keep warning visible.",
                "bounded_worker_task": "Build correction preview.",
                "retest_rule": "Rerun B070 and B MOT.",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "protected_before_apply": "1",
            }
        ],
    )
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_fallback_token_cost_audit_summary.csv",
        ["metric", "value"],
        [
            {"metric": "fallback_token_rows", "value": "1"},
            {"metric": "receipt_proved_rows", "value": "0"},
            {"metric": "source_token_proved_rows", "value": "0"},
            {"metric": "weak_or_unproved_rows", "value": "1"},
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    work_item = next(row for row in worklist_rows if row["check"] == "b_fallback_token_cost_audit")

    assert rows["b_fallback_token_cost_audit"]["status"] == "warn"
    assert "weak_or_unproved=1" in rows["b_fallback_token_cost_audit"]["actual_proof"]
    assert work_item["status"] == "new"
    assert work_item["job_ref"] == "B-FALLBACK-COST-AUDIT"
    assert work_item["luke_action_required"] == "0"


def test_b_fallback_token_cost_audit_ok_when_cost_sources_are_proved(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_b_completion_clean_inputs(tmp_path)
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_fallback_token_cost_audit.csv",
        [
            "token_id",
            "seller_sku",
            "cost_per_unit",
            "cost_proof_state",
            "manager_label",
            "manager_expectation",
            "bounded_worker_task",
            "retest_rule",
            "preview_live_write_allowed",
            "roi_or_restock_use_allowed",
            "protected_before_apply",
        ],
        [
            {
                "token_id": "ADJ-SKU-1-EVT-1-0001",
                "seller_sku": "SKU-1",
                "cost_per_unit": "4.44",
                "cost_proof_state": "fallback_cost_receipt_proved",
                "manager_label": "api_or_receipt_proved",
                "manager_expectation": "No live correction needed from this audit.",
                "bounded_worker_task": "No live correction needed from this audit.",
                "retest_rule": "Rerun B070 and B MOT.",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "protected_before_apply": "0",
            },
            {
                "token_id": "ADJ-SKU-2-EVT-2-0001",
                "seller_sku": "SKU-2",
                "cost_per_unit": "2.10",
                "cost_proof_state": "fallback_cost_source_token_proved",
                "manager_label": "source_token_proved",
                "manager_expectation": "No live correction needed from this audit.",
                "bounded_worker_task": "No live correction needed from this audit.",
                "retest_rule": "Rerun B070 and B MOT.",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "protected_before_apply": "0",
            },
        ],
    )
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_fallback_token_cost_audit_summary.csv",
        ["metric", "value"],
        [
            {"metric": "fallback_token_rows", "value": "2"},
            {"metric": "receipt_proved_rows", "value": "1"},
            {"metric": "source_token_proved_rows", "value": "1"},
            {"metric": "weak_or_unproved_rows", "value": "0"},
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_fallback_token_cost_audit"]["status"] == "ok"
    assert "weak_or_unproved=0" in rows["b_fallback_token_cost_audit"]["actual_proof"]
    assert rows["b_order_truth_completion"]["status"] == "ok"


def test_b_fallback_token_cost_audit_fails_on_live_use_flags(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_b_completion_clean_inputs(tmp_path)
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_fallback_token_cost_audit.csv",
        [
            "token_id",
            "seller_sku",
            "cost_per_unit",
            "cost_proof_state",
            "manager_label",
            "manager_expectation",
            "bounded_worker_task",
            "retest_rule",
            "preview_live_write_allowed",
            "roi_or_restock_use_allowed",
            "protected_before_apply",
        ],
        [
            {
                "token_id": "ADJ-SKU-1-EVT-1-0001",
                "seller_sku": "SKU-1",
                "cost_per_unit": "4.44",
                "cost_proof_state": "fallback_cost_receipt_proved",
                "manager_label": "api_or_receipt_proved",
                "manager_expectation": "No live correction needed from this audit.",
                "bounded_worker_task": "No live correction needed from this audit.",
                "retest_rule": "Rerun B070 and B MOT.",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "1",
                "protected_before_apply": "0",
            }
        ],
    )
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_fallback_token_cost_audit_summary.csv",
        ["metric", "value"],
        [
            {"metric": "fallback_token_rows", "value": "1"},
            {"metric": "receipt_proved_rows", "value": "1"},
            {"metric": "source_token_proved_rows", "value": "0"},
            {"metric": "weak_or_unproved_rows", "value": "0"},
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_fallback_token_cost_audit"]["status"] == "fail"
    assert "unsafe_live_use_rows=1" in rows["b_fallback_token_cost_audit"]["actual_proof"]


def test_b_fallback_cost_reconciliation_warns_and_parks_when_batch_link_needed(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_b_completion_clean_inputs(tmp_path)
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_fallback_cost_proof_reconciliation.csv",
        [
            "token_id",
            "seller_sku",
            "b070_cost_proof_state",
            "sheet_issue",
            "reconciliation_rule",
            "clean_h_o_trust_allowed",
            "manager_expectation",
            "bounded_worker_task",
            "retest_rule",
            "preview_live_write_allowed",
            "roi_or_restock_use_allowed",
            "protected_before_apply",
        ],
        [
            {
                "token_id": "ADJ-1",
                "seller_sku": "A2-T2AC-TW3L",
                "b070_cost_proof_state": "fallback_cost_source_token_proved",
                "sheet_issue": "fallback_cost_differs_from_latest_prior_sheet_cost",
                "reconciliation_rule": "requires_batch_link_proof",
                "clean_h_o_trust_allowed": "0",
                "manager_expectation": "Keep H/O blocked.",
                "bounded_worker_task": "Batch-link proof needed.",
                "retest_rule": "Rerun B071 and B MOT.",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "protected_before_apply": "1",
            }
        ],
    )
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_fallback_cost_proof_reconciliation_summary.csv",
        ["metric", "value"],
        [
            {"metric": "reconciliation_rows", "value": "1"},
            {"metric": "source_token_cost_is_valid_rows", "value": "0"},
            {"metric": "requires_batch_link_proof_rows", "value": "1"},
            {"metric": "h_next_available_blocked_skus", "value": "A2-T2AC-TW3L"},
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    item = next(row for row in worklist_rows if row["check"] == "b_fallback_cost_proof_reconciliation")

    assert rows["b_fallback_cost_proof_reconciliation"]["status"] == "warn"
    assert "requires_batch_link_proof_rows=1" in rows["b_fallback_cost_proof_reconciliation"]["actual_proof"]
    assert rows["b_order_truth_completion"]["status"] == "warn"
    assert item["status"] == "parked"
    assert item["job_ref"] == "B-FALLBACK-PROOF-RECONCILE"


def test_b_fallback_cost_reconciliation_fails_on_live_use_flags(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_b_completion_clean_inputs(tmp_path)
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_fallback_cost_proof_reconciliation.csv",
        [
            "token_id",
            "seller_sku",
            "b070_cost_proof_state",
            "sheet_issue",
            "reconciliation_rule",
            "clean_h_o_trust_allowed",
            "manager_expectation",
            "bounded_worker_task",
            "retest_rule",
            "preview_live_write_allowed",
            "roi_or_restock_use_allowed",
            "protected_before_apply",
        ],
        [
            {
                "token_id": "ADJ-1",
                "seller_sku": "A2-T2AC-TW3L",
                "b070_cost_proof_state": "fallback_cost_source_token_proved",
                "sheet_issue": "ok",
                "reconciliation_rule": "source_token_cost_is_valid",
                "clean_h_o_trust_allowed": "1",
                "manager_expectation": "Clean.",
                "bounded_worker_task": "None.",
                "retest_rule": "Rerun B071 and B MOT.",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "1",
                "protected_before_apply": "0",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_fallback_cost_proof_reconciliation"]["status"] == "fail"
    assert "unsafe_rows=1" in rows["b_fallback_cost_proof_reconciliation"]["actual_proof"]


def test_b_refund_pnl_roi_api_proof_clears_with_bridge_and_rate_outputs(tmp_path: Path) -> None:
    bridge_cols = [
        "order_id",
        "sku",
        "refund_posted_date",
        "refund_units",
        "refund_profit_impact_exvat",
        "sellerboard_match_state",
        "api_refund_proof_state",
        "pnl_inclusion_state",
    ]
    rate_cols = [
        "sku",
        "window_days",
        "sales_units",
        "refund_units",
        "refund_unit_rate",
        "expected_refund_cost_per_unit_gbp",
        "basis",
        "sample_confidence",
        "proof_state",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_pnl_bridge.csv",
        bridge_cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "refund_posted_date": "2026-05-20T10:00:00Z",
                "refund_units": "1",
                "refund_profit_impact_exvat": "-7",
                "sellerboard_match_state": "sellerboard_return_witness",
                "api_refund_proof_state": "api_proved",
                "pnl_inclusion_state": "pnl_official_refund_source",
            }
        ],
    )
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_sku_refund_rate.csv",
        rate_cols,
        [
            {
                "sku": "SKU-A",
                "window_days": "30",
                "sales_units": "10",
                "refund_units": "1",
                "refund_unit_rate": "0.1",
                "expected_refund_cost_per_unit_gbp": "0.7",
                "basis": "sale_cohort",
                "sample_confidence": "medium",
                "proof_state": "api_proved_or_not_applicable",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_refund_pnl_roi_api_proof"]["status"] == "ok"
    assert "api_refund_rows=1" in rows["b_refund_pnl_roi_api_proof"]["actual_proof"]


def test_b_refund_return_token_bridge_warns_on_mismatch(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "api_refund_proof_state",
        "amazon_return_proof_state",
        "token_return_state",
        "return_cogs_recovered_exvat",
        "blocked_return_cogs_exvat",
        "sellerboard_match_state",
        "proof_label",
        "roi_stock_recovery_state",
        "mismatch_state",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_return_token_bridge.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "api_refund_proof_state": "api_proved",
                "amazon_return_proof_state": "api_return_report_pulled",
                "token_return_state": "returned_pending",
                "return_cogs_recovered_exvat": "0",
                "blocked_return_cogs_exvat": "0",
                "sellerboard_match_state": "sellerboard_return_witness",
                "proof_label": "returned_sellable_token_missing",
                "roi_stock_recovery_state": "stock_recovery_missing_token_reuse",
                "mismatch_state": "warning",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    work_item = next(row for row in worklist_rows if row["check"] == "b_refund_return_token_bridge")

    assert rows["b_refund_return_token_bridge"]["status"] == "warn"
    assert "returned_sellable_token_missing=1" in rows["b_refund_return_token_bridge"]["actual_proof"]
    assert "no B run" in work_item["safe_repair_boundary"]
    assert "no token/data correction" in work_item["forbidden_actions"]


def test_b_refund_return_token_bridge_clears_when_labels_are_clean(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "api_refund_proof_state",
        "amazon_return_proof_state",
        "token_return_state",
        "return_cogs_recovered_exvat",
        "blocked_return_cogs_exvat",
        "sellerboard_match_state",
        "proof_label",
        "roi_stock_recovery_state",
        "mismatch_state",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_return_token_bridge.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "api_refund_proof_state": "api_proved",
                "amazon_return_proof_state": "api_return_report_pulled",
                "token_return_state": "available_return_token_seen",
                "return_cogs_recovered_exvat": "2.5",
                "blocked_return_cogs_exvat": "0",
                "sellerboard_match_state": "sellerboard_return_witness",
                "proof_label": "returned_sellable_token_reused",
                "roi_stock_recovery_state": "stock_recovery_api_and_token_proved",
                "mismatch_state": "ok",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_refund_return_token_bridge"]["status"] == "ok"
    assert "returned_sellable_token_reused=1" in rows["b_refund_return_token_bridge"]["actual_proof"]


def test_b_return_token_matching_audit_clears_when_warning_rows_are_classified(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "proof_label",
        "diagnosis",
        "future_proofing_need",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
        "b008_applied_qty",
        "amazon_return_disposition",
        "token_return_state",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_matching_audit.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "proof_label": "returned_sellable_token_missing",
                "diagnosis": "B008 did not prove a returned-pending token for this refunded order/SKU.",
                "future_proofing_need": "Make B008 refund-token marking order/SKU complete before B009 matching is trusted.",
                "bounded_worker_task": "Audit B008 allocations for this order/SKU.",
                "retest_rule": "Rerun B040, B038, and B MOT.",
                "protected_stop_rule": "Stop before token correction.",
                "b008_applied_qty": "0",
                "amazon_return_disposition": "SELLABLE",
                "token_return_state": "no_token_return_state",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_return_token_matching_audit"]["status"] == "ok"
    assert "audit_rows=1" in rows["b_return_token_matching_audit"]["actual_proof"]
    assert "b008_missing_or_zero_applied=1" in rows["b_return_token_matching_audit"]["actual_proof"]


def test_b_return_token_repair_preview_clears_when_safe_and_classified(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "proof_label",
        "diagnosis",
        "repair_lane",
        "repair_readiness",
        "preview_action",
        "preview_live_write_allowed",
        "protected_before_apply",
        "sellerboard_final_truth_allowed",
        "roi_or_restock_use_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "proof_label": "returned_sellable_token_missing",
                "diagnosis": "B009 saw sellable stock movement near the Amazon return date.",
                "repair_lane": "b009_order_aware_sellable_return",
                "repair_readiness": "ready_for_b009_order_aware_preview",
                "preview_action": "Preview B009 order-aware matching only.",
                "preview_live_write_allowed": "0",
                "protected_before_apply": "1",
                "sellerboard_final_truth_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "bounded_worker_task": "Add B009 order-aware customer-return matching.",
                "retest_rule": "Rerun B041, B038, and B MOT.",
                "protected_stop_rule": "Stop before token correction.",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_return_token_repair_preview"]["status"] == "ok"
    assert "preview_rows=1" in rows["b_return_token_repair_preview"]["actual_proof"]
    assert "b009_order_aware_rows=1" in rows["b_return_token_repair_preview"]["actual_proof"]


def test_b_return_token_repair_preview_fails_if_live_write_is_allowed(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "proof_label",
        "diagnosis",
        "repair_lane",
        "repair_readiness",
        "preview_action",
        "preview_live_write_allowed",
        "protected_before_apply",
        "sellerboard_final_truth_allowed",
        "roi_or_restock_use_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "proof_label": "returned_sellable_token_missing",
                "diagnosis": "B009 saw sellable stock movement near the Amazon return date.",
                "repair_lane": "b009_order_aware_sellable_return",
                "repair_readiness": "ready_for_b009_order_aware_preview",
                "preview_action": "Unsafe live write.",
                "preview_live_write_allowed": "1",
                "protected_before_apply": "1",
                "sellerboard_final_truth_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "bounded_worker_task": "Add B009 order-aware customer-return matching.",
                "retest_rule": "Rerun B041, B038, and B MOT.",
                "protected_stop_rule": "Stop before token correction.",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_return_token_repair_preview"]["status"] == "fail"
    assert "live_write_rows=1" in rows["b_return_token_repair_preview"]["actual_proof"]


def test_b_refund_return_warning_workpack_clears_when_safe_and_classified(tmp_path: Path) -> None:
    cols = [
        "repair_lane",
        "repair_readiness",
        "row_count",
        "manager_expectation",
        "mot_proof_check",
        "bounded_worker_task",
        "retest_rule",
        "luke_decision_rule",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "protected_before_apply",
        "manager_state",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_return_warning_workpack.csv",
        cols,
        [
            {
                "repair_lane": "amazon_return_coverage_review",
                "repair_readiness": "blocked_missing_amazon_order_return_proof",
                "row_count": "15",
                "manager_expectation": "Stock recovery stays untrusted until Amazon return coverage is proved.",
                "mot_proof_check": "Rerun B039/B041/B038 and B MOT.",
                "bounded_worker_task": "Investigate Amazon customer-return coverage.",
                "retest_rule": "Rerun B MOT after proof improves.",
                "luke_decision_rule": "Luke decides only if stock recovery is proposed without Amazon return proof.",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "protected_before_apply": "15",
                "manager_state": "parked_needs_amazon_return_coverage_proof",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_refund_return_warning_workpack"]["status"] == "ok"
    assert "warning_rows=15" in rows["b_refund_return_warning_workpack"]["actual_proof"]
    assert "unclassified_lanes=0" in rows["b_refund_return_warning_workpack"]["actual_proof"]


def test_b_return_cogs_residual_review_clears_when_blocked_from_roi(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "amazon_return_disposition",
        "token_return_state",
        "recovered_cogs_allowed_exvat",
        "blocked_return_cogs_exvat",
        "residual_review_state",
        "manager_expectation",
        "mot_proof_check",
        "bounded_worker_task",
        "retest_rule",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "protected_before_apply",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_cogs_residual_review.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "amazon_return_disposition": "CUSTOMER_DAMAGED",
                "token_return_state": "returned_complete_no_available_token_seen",
                "recovered_cogs_allowed_exvat": "0",
                "blocked_return_cogs_exvat": "2.5",
                "residual_review_state": "blocked_from_roi_and_stock_recovery",
                "manager_expectation": "Non-sellable COGS stays blocked.",
                "mot_proof_check": "Rerun B064 and B MOT.",
                "bounded_worker_task": "Keep blocked.",
                "retest_rule": "Rerun B064 and B MOT.",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "protected_before_apply": "0",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_return_cogs_residual_review"]["status"] == "ok"
    assert "blocked_rows=1" in rows["b_return_cogs_residual_review"]["actual_proof"]
    assert "unsafe_rows=0" in rows["b_return_cogs_residual_review"]["actual_proof"]


def test_b_return_cogs_residual_review_fails_if_roi_use_allowed(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "amazon_return_disposition",
        "token_return_state",
        "recovered_cogs_allowed_exvat",
        "blocked_return_cogs_exvat",
        "residual_review_state",
        "manager_expectation",
        "mot_proof_check",
        "bounded_worker_task",
        "retest_rule",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "protected_before_apply",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_cogs_residual_review.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "amazon_return_disposition": "DEFECTIVE",
                "token_return_state": "returned_complete_no_available_token_seen",
                "recovered_cogs_allowed_exvat": "2.5",
                "blocked_return_cogs_exvat": "0",
                "residual_review_state": "unsafe_non_sellable_cogs_recovery",
                "manager_expectation": "Non-sellable COGS stays blocked.",
                "mot_proof_check": "Rerun B064 and B MOT.",
                "bounded_worker_task": "Keep blocked.",
                "retest_rule": "Rerun B064 and B MOT.",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "1",
                "sellerboard_final_truth_allowed": "0",
                "protected_before_apply": "0",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_return_cogs_residual_review"]["status"] == "fail"
    assert "unsafe_rows=1" in rows["b_return_cogs_residual_review"]["actual_proof"]


def test_b_refund_return_bridge_worklist_parks_when_warning_workpack_is_safe(tmp_path: Path) -> None:
    bridge_cols = [
        "order_id",
        "sku",
        "api_refund_proof_state",
        "amazon_return_proof_state",
        "token_return_state",
        "return_cogs_recovered_exvat",
        "blocked_return_cogs_exvat",
        "sellerboard_match_state",
        "proof_label",
        "roi_stock_recovery_state",
        "mismatch_state",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_return_token_bridge.csv",
        bridge_cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "api_refund_proof_state": "api_proved",
                "amazon_return_proof_state": "api_return_report_pulled",
                "token_return_state": "returned_pending",
                "return_cogs_recovered_exvat": "0",
                "blocked_return_cogs_exvat": "0",
                "sellerboard_match_state": "sellerboard_return_witness",
                "proof_label": "returned_sellable_token_missing",
                "roi_stock_recovery_state": "stock_recovery_missing_token_reuse",
                "mismatch_state": "warning",
            }
        ],
    )
    workpack_cols = [
        "repair_lane",
        "repair_readiness",
        "row_count",
        "manager_expectation",
        "mot_proof_check",
        "bounded_worker_task",
        "retest_rule",
        "luke_decision_rule",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "protected_before_apply",
        "manager_state",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_return_warning_workpack.csv",
        workpack_cols,
        [
            {
                "repair_lane": "amazon_return_coverage_review",
                "repair_readiness": "blocked_missing_amazon_order_return_proof",
                "row_count": "1",
                "manager_expectation": "Stock recovery stays untrusted until Amazon return coverage is proved.",
                "mot_proof_check": "Rerun B039/B041/B038 and B MOT.",
                "bounded_worker_task": "Investigate Amazon customer-return coverage.",
                "retest_rule": "Rerun B MOT after proof improves.",
                "luke_decision_rule": "Luke decides only if stock recovery is proposed without Amazon return proof.",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "protected_before_apply": "1",
                "manager_state": "parked_needs_amazon_return_coverage_proof",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    work_item = next(row for row in worklist_rows if row["check"] == "b_refund_return_token_bridge")

    assert rows["b_refund_return_token_bridge"]["status"] == "warn"
    assert rows["b_refund_return_warning_workpack"]["status"] == "ok"
    assert work_item["status"] == "parked"
    assert work_item["luke_action_required"] == "0"
    assert "B051 workpack classifies" in work_item["notes"]


def test_b_refund_return_warning_workpack_fails_if_roi_use_allowed(tmp_path: Path) -> None:
    cols = [
        "repair_lane",
        "repair_readiness",
        "row_count",
        "manager_expectation",
        "mot_proof_check",
        "bounded_worker_task",
        "retest_rule",
        "luke_decision_rule",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "protected_before_apply",
        "manager_state",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_return_warning_workpack.csv",
        cols,
        [
            {
                "repair_lane": "amazon_return_coverage_review",
                "repair_readiness": "blocked_missing_amazon_order_return_proof",
                "row_count": "15",
                "manager_expectation": "Unsafe.",
                "mot_proof_check": "Rerun B MOT.",
                "bounded_worker_task": "Investigate.",
                "retest_rule": "Rerun B MOT.",
                "luke_decision_rule": "Luke decides.",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "1",
                "sellerboard_final_truth_allowed": "0",
                "protected_before_apply": "15",
                "manager_state": "parked_needs_amazon_return_coverage_proof",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_refund_return_warning_workpack"]["status"] == "fail"
    assert "roi_lanes=1" in rows["b_refund_return_warning_workpack"]["actual_proof"]


def test_b_amazon_return_coverage_audit_clears_when_safe_and_classified(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "repair_lane",
        "exact_customer_return_rows",
        "customer_return_match_state",
        "stock_signal_state",
        "coverage_conclusion",
        "manager_coverage_label",
        "manager_expectation",
        "bounded_worker_task",
        "retest_rule",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_amazon_return_coverage_audit.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "repair_lane": "amazon_return_coverage_review",
                "exact_customer_return_rows": "0",
                "customer_return_match_state": "missing_order_sku_match",
                "stock_signal_state": "stock_signal_seen_but_customer_return_order_missing",
                "coverage_conclusion": "stock_adjustment_without_customer_return_order_proof",
                "manager_coverage_label": "stock_adjustment_only",
                "manager_expectation": "Keep stock recovery blocked from ROI.",
                "bounded_worker_task": "Investigate coverage.",
                "retest_rule": "Rerun B052 and B MOT.",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_amazon_return_coverage_audit"]["status"] == "ok"
    assert "stock_adjustment_without_customer_return_rows=1" in rows["b_amazon_return_coverage_audit"]["actual_proof"]
    assert "roi_rows=0" in rows["b_amazon_return_coverage_audit"]["actual_proof"]


def test_b_amazon_return_coverage_audit_fails_if_unclassified(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "repair_lane",
        "exact_customer_return_rows",
        "customer_return_match_state",
        "stock_signal_state",
        "coverage_conclusion",
        "manager_coverage_label",
        "manager_expectation",
        "bounded_worker_task",
        "retest_rule",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_amazon_return_coverage_audit.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "repair_lane": "amazon_return_coverage_review",
                "exact_customer_return_rows": "0",
                "customer_return_match_state": "missing_order_sku_match",
                "stock_signal_state": "",
                "coverage_conclusion": "",
                "manager_coverage_label": "",
                "manager_expectation": "Keep stock recovery blocked from ROI.",
                "bounded_worker_task": "Investigate coverage.",
                "retest_rule": "Rerun B052 and B MOT.",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_amazon_return_coverage_audit"]["status"] == "fail"
    assert "unclassified_rows=1" in rows["b_amazon_return_coverage_audit"]["actual_proof"]


def test_b_original_allocation_gap_audit_clears_when_safe_and_classified(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "api_refund_rows",
        "refund_bridge_original_order_state",
        "orders_all_rows",
        "order_items_all_rows",
        "token_allocation_rows",
        "token_ledger_allocated_rows",
        "allocation_gap_conclusion",
        "manager_expectation",
        "bounded_worker_task",
        "retest_rule",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_allocation_gap_audit.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "api_refund_rows": "1",
                "refund_bridge_original_order_state": "original_order_not_found",
                "orders_all_rows": "0",
                "order_items_all_rows": "0",
                "token_allocation_rows": "0",
                "token_ledger_allocated_rows": "0",
                "allocation_gap_conclusion": "refund_money_without_original_order_or_allocation_proof",
                "manager_expectation": "Keep stock recovery blocked.",
                "bounded_worker_task": "Build original-order recovery proof.",
                "retest_rule": "Rerun B053 and B MOT.",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_original_allocation_gap_audit"]["status"] == "ok"
    assert "refund_money_without_original_order_rows=1" in rows["b_original_allocation_gap_audit"]["actual_proof"]
    assert "roi_rows=0" in rows["b_original_allocation_gap_audit"]["actual_proof"]


def test_b_original_allocation_gap_audit_fails_if_unsafe(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "api_refund_rows",
        "refund_bridge_original_order_state",
        "orders_all_rows",
        "order_items_all_rows",
        "token_allocation_rows",
        "token_ledger_allocated_rows",
        "allocation_gap_conclusion",
        "manager_expectation",
        "bounded_worker_task",
        "retest_rule",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_allocation_gap_audit.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "api_refund_rows": "1",
                "refund_bridge_original_order_state": "original_order_not_found",
                "orders_all_rows": "0",
                "order_items_all_rows": "0",
                "token_allocation_rows": "0",
                "token_ledger_allocated_rows": "0",
                "allocation_gap_conclusion": "refund_money_without_original_order_or_allocation_proof",
                "manager_expectation": "Keep stock recovery blocked.",
                "bounded_worker_task": "Build original-order recovery proof.",
                "retest_rule": "Rerun B053 and B MOT.",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "1",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_original_allocation_gap_audit"]["status"] == "fail"
    assert "roi_rows=1" in rows["b_original_allocation_gap_audit"]["actual_proof"]


def test_b_original_order_recovery_proof_clears_when_safe_and_classified(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "api_refund_rows",
        "orders_raw_rows",
        "order_items_raw_rows",
        "orders_all_rows",
        "order_items_all_rows",
        "order_master_rows",
        "level1_rows",
        "token_allocation_rows",
        "quarantine_rows",
        "quarantine_api_proved_rows",
        "quarantine_required_field_gaps",
        "original_order_recovery_state",
        "manager_expectation",
        "bounded_worker_task",
        "retest_rule",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_order_recovery_proof.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "api_refund_rows": "1",
                "orders_raw_rows": "0",
                "order_items_raw_rows": "0",
                "orders_all_rows": "0",
                "order_items_all_rows": "0",
                "order_master_rows": "0",
                "level1_rows": "0",
                "token_allocation_rows": "0",
                "quarantine_rows": "0",
                "quarantine_api_proved_rows": "0",
                "quarantine_required_field_gaps": "",
                "original_order_recovery_state": "needs_api_original_order_fetch_to_quarantine",
                "manager_expectation": "Fetch original order to quarantine first.",
                "bounded_worker_task": "Build API original-order fetch proof.",
                "retest_rule": "Rerun B054 and B MOT.",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_original_order_recovery_proof"]["status"] == "ok"
    assert "needs_api_original_order_fetch_rows=1" in rows["b_original_order_recovery_proof"]["actual_proof"]
    assert "roi_rows=0" in rows["b_original_order_recovery_proof"]["actual_proof"]


def test_b_original_order_recovery_proof_fails_if_unsafe(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "api_refund_rows",
        "orders_raw_rows",
        "order_items_raw_rows",
        "orders_all_rows",
        "order_items_all_rows",
        "order_master_rows",
        "level1_rows",
        "token_allocation_rows",
        "quarantine_rows",
        "quarantine_api_proved_rows",
        "quarantine_required_field_gaps",
        "original_order_recovery_state",
        "manager_expectation",
        "bounded_worker_task",
        "retest_rule",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_order_recovery_proof.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "api_refund_rows": "1",
                "orders_raw_rows": "0",
                "order_items_raw_rows": "0",
                "orders_all_rows": "0",
                "order_items_all_rows": "0",
                "order_master_rows": "0",
                "level1_rows": "0",
                "token_allocation_rows": "0",
                "quarantine_rows": "1",
                "quarantine_api_proved_rows": "1",
                "quarantine_required_field_gaps": "",
                "original_order_recovery_state": "api_quarantine_original_order_proof_exists",
                "manager_expectation": "Proof exists in quarantine only.",
                "bounded_worker_task": "Build protected promotion preview.",
                "retest_rule": "Rerun B054 and B MOT.",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "1",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_original_order_recovery_proof"]["status"] == "fail"
    assert "roi_rows=1" in rows["b_original_order_recovery_proof"]["actual_proof"]


def test_b_original_order_recovery_fetch_clears_for_safe_preview(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "source_state",
        "action_state",
        "proof_label",
        "required_field_gaps",
        "live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_order_recovery_fetch_results.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "source_state": "needs_api_original_order_fetch_to_quarantine",
                "action_state": "planned_api_fetch_to_quarantine",
                "proof_label": "not yet proven",
                "required_field_gaps": "",
                "live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_original_order_recovery_fetch"]["status"] == "ok"
    assert "planned_api_fetch_rows=1" in rows["b_original_order_recovery_fetch"]["actual_proof"]
    assert "roi_rows=0" in rows["b_original_order_recovery_fetch"]["actual_proof"]


def test_b_original_order_recovery_fetch_fails_if_unsafe(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "source_state",
        "action_state",
        "proof_label",
        "required_field_gaps",
        "live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_order_recovery_fetch_results.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "source_state": "needs_api_original_order_fetch_to_quarantine",
                "action_state": "fetched_api_proved_to_quarantine",
                "proof_label": "API proved",
                "required_field_gaps": "",
                "live_write_allowed": "1",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_original_order_recovery_fetch"]["status"] == "fail"
    assert "live_write_rows=1" in rows["b_original_order_recovery_fetch"]["actual_proof"]


def test_b_original_sale_allocation_repair_preview_clears_when_safe(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "missing_token_rows",
        "shortage_class",
        "repair_lane",
        "repair_readiness",
        "manager_expectation",
        "bounded_worker_task",
        "retest_rule",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_sale_allocation_repair_preview.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "missing_token_rows": "1",
                "shortage_class": "legacy_baseline_gap",
                "repair_lane": "protected_legacy_baseline_allocation_candidate",
                "repair_readiness": "blocked_needs_protected_stock_decision",
                "manager_expectation": "Protected correction only.",
                "bounded_worker_task": "Build protected preview.",
                "retest_rule": "Rerun B056 and B MOT.",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_original_sale_allocation_repair_preview"]["status"] == "ok"
    assert "legacy_baseline_candidate_rows=1" in rows["b_original_sale_allocation_repair_preview"]["actual_proof"]


def test_b_original_sale_allocation_repair_preview_fails_if_unsafe(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "missing_token_rows",
        "shortage_class",
        "repair_lane",
        "repair_readiness",
        "manager_expectation",
        "bounded_worker_task",
        "retest_rule",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_sale_allocation_repair_preview.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "missing_token_rows": "1",
                "shortage_class": "runtime_adjustment_pending",
                "repair_lane": "protected_runtime_adjustment_allocation_candidate",
                "repair_readiness": "blocked_needs_protected_stock_decision",
                "manager_expectation": "Protected correction only.",
                "bounded_worker_task": "Build protected preview.",
                "retest_rule": "Rerun B056 and B MOT.",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "1",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_original_sale_allocation_repair_preview"]["status"] == "fail"
    assert "roi_rows=1" in rows["b_original_sale_allocation_repair_preview"]["actual_proof"]


def test_b_original_sale_allocation_repair_apply_clears_when_manifest_applied(tmp_path: Path) -> None:
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_sale_allocation_repair_preview.csv",
        ["order_id", "sku", "repair_lane", "preview_live_write_allowed", "roi_or_restock_use_allowed", "sellerboard_final_truth_allowed"],
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "repair_lane": "protected_legacy_baseline_allocation_candidate",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
    )
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_sale_allocation_repair_applied.csv",
        [
            "order_id",
            "sku",
            "repair_lane",
            "new_token_id",
            "new_token_status",
            "approval_reference",
            "action",
            "runtime_stock_adjustment_closed",
        ],
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "repair_lane": "protected_legacy_baseline_allocation_candidate",
                "new_token_id": "TOK-1",
                "new_token_status": "allocated",
                "approval_reference": "APPROVED",
                "action": "protected_original_sale_allocation_repair_applied",
                "runtime_stock_adjustment_closed": "0",
            }
        ],
    )
    manifest = tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_sale_allocation_repair_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "status": "applied",
                "preview_rows": 1,
                "created_token_rows": 1,
                "allocated_token_rows": 1,
                "cogs_rows": 1,
                "blocked_rows": 0,
                "runtime_adjustment_deferred_rows": 0,
            }
        ),
        encoding="utf-8",
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_original_sale_allocation_repair_apply"]["status"] == "ok"
    assert "manifest=applied" in rows["b_original_sale_allocation_repair_apply"]["value"]


def test_b_original_sale_allocation_repair_apply_needs_decision_before_apply(tmp_path: Path) -> None:
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_sale_allocation_repair_preview.csv",
        ["order_id", "sku", "repair_lane", "preview_live_write_allowed", "roi_or_restock_use_allowed", "sellerboard_final_truth_allowed"],
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "repair_lane": "protected_legacy_baseline_allocation_candidate",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_original_sale_allocation_repair_apply"]["status"] == "decision_needed"
    assert rows["b_original_sale_allocation_repair_apply"]["luke_action_required"] == "1"


def test_b_refund_token_reproof_preview_clears_when_safe_and_classified(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "source_repair_lane",
        "reproof_lane",
        "reproof_readiness",
        "preview_action",
        "preview_live_write_allowed",
        "protected_before_apply",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_token_reproof_preview.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "source_repair_lane": "b008_refund_token_marking",
                "reproof_lane": "b008_refund_token_marking",
                "reproof_readiness": "ready_for_b008_order_sku_reproof",
                "preview_action": "Preview B008 refund-token marking only.",
                "preview_live_write_allowed": "0",
                "protected_before_apply": "1",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "bounded_worker_task": "Repair B008 refund-token mapping.",
                "retest_rule": "Rerun B042, B041, B038, and B MOT.",
                "protected_stop_rule": "Stop before token correction.",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_refund_token_reproof_preview"]["status"] == "ok"
    assert "preview_rows=1" in rows["b_refund_token_reproof_preview"]["actual_proof"]
    assert "ready_b008_order_sku_reproof_rows=1" in rows["b_refund_token_reproof_preview"]["actual_proof"]


def test_b_refund_token_reproof_preview_fails_if_live_write_is_allowed(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "source_repair_lane",
        "reproof_lane",
        "reproof_readiness",
        "preview_action",
        "preview_live_write_allowed",
        "protected_before_apply",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_token_reproof_preview.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "source_repair_lane": "b008_refund_token_marking",
                "reproof_lane": "b008_refund_token_marking",
                "reproof_readiness": "ready_for_b008_order_sku_reproof",
                "preview_action": "Unsafe live write.",
                "preview_live_write_allowed": "1",
                "protected_before_apply": "1",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "bounded_worker_task": "Repair B008 refund-token mapping.",
                "retest_rule": "Rerun B042, B041, B038, and B MOT.",
                "protected_stop_rule": "Stop before token correction.",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_refund_token_reproof_preview"]["status"] == "fail"
    assert "live_write_rows=1" in rows["b_refund_token_reproof_preview"]["actual_proof"]


def test_b_b008_token_ledger_gap_review_clears_when_safe_and_classified(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "allocation_token_id",
        "allocation_row_seen",
        "ledger_token_seen",
        "gap_label",
        "manager_state",
        "protected_before_apply",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_b008_token_ledger_gap_review.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "allocation_token_id": "TOKEN-1",
                "allocation_row_seen": "1",
                "ledger_token_seen": "0",
                "gap_label": "b057_allocation_token_missing_from_ledger",
                "manager_state": "protected_ledger_alignment_needed",
                "protected_before_apply": "1",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "bounded_worker_task": "Prepare protected ledger-alignment preview.",
                "retest_rule": "Rerun B042/B041/B038/B051/B MOT.",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_b008_token_ledger_gap_review"]["status"] == "ok"
    assert "review_rows=1" in rows["b_b008_token_ledger_gap_review"]["actual_proof"]
    assert "protected_ledger_alignment_rows=1" in rows["b_b008_token_ledger_gap_review"]["actual_proof"]


def test_b_b008_token_ledger_gap_review_fails_if_live_write_is_allowed(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "allocation_token_id",
        "allocation_row_seen",
        "ledger_token_seen",
        "gap_label",
        "manager_state",
        "protected_before_apply",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_b008_token_ledger_gap_review.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "allocation_token_id": "TOKEN-1",
                "allocation_row_seen": "1",
                "ledger_token_seen": "0",
                "gap_label": "unsafe",
                "manager_state": "unsafe",
                "protected_before_apply": "1",
                "preview_live_write_allowed": "1",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "bounded_worker_task": "Unsafe.",
                "retest_rule": "Rerun.",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_b008_token_ledger_gap_review"]["status"] == "fail"
    assert "live_write_rows=1" in rows["b_b008_token_ledger_gap_review"]["actual_proof"]


def test_b_original_return_status_conflict_preview_clears_when_safe_and_classified(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "unsafe_original_token_id",
        "unsafe_original_status",
        "reusable_return_token_ids",
        "has_reusable_duplicate_token",
        "review_lane",
        "review_readiness",
        "preview_action",
        "preview_live_write_allowed",
        "protected_before_apply",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_return_status_conflict_preview.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "unsafe_original_token_id": "TOKEN-1",
                "unsafe_original_status": "allocated",
                "reusable_return_token_ids": "TOKEN-1-R",
                "has_reusable_duplicate_token": "1",
                "review_lane": "original_allocated_after_return_with_duplicate",
                "review_readiness": "blocked_needs_protected_review",
                "preview_action": "No-write preview only.",
                "preview_live_write_allowed": "0",
                "protected_before_apply": "1",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "bounded_worker_task": "Prepare protected lifecycle repair plan.",
                "retest_rule": "Rerun B045, B041, B038, and B MOT.",
                "protected_stop_rule": "Stop before token correction.",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_original_return_status_conflict_preview"]["status"] == "ok"
    assert "preview_rows=1" in rows["b_original_return_status_conflict_preview"]["actual_proof"]
    assert "with_reusable_duplicate_rows=1" in rows["b_original_return_status_conflict_preview"]["actual_proof"]


def test_b_original_return_status_conflict_preview_fails_if_live_write_is_allowed(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "unsafe_original_token_id",
        "unsafe_original_status",
        "reusable_return_token_ids",
        "has_reusable_duplicate_token",
        "review_lane",
        "review_readiness",
        "preview_action",
        "preview_live_write_allowed",
        "protected_before_apply",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_return_status_conflict_preview.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "unsafe_original_token_id": "TOKEN-1",
                "unsafe_original_status": "allocated",
                "reusable_return_token_ids": "TOKEN-1-R",
                "has_reusable_duplicate_token": "1",
                "review_lane": "original_allocated_after_return_with_duplicate",
                "review_readiness": "blocked_needs_protected_review",
                "preview_action": "Unsafe live write.",
                "preview_live_write_allowed": "1",
                "protected_before_apply": "1",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "bounded_worker_task": "Prepare protected lifecycle repair plan.",
                "retest_rule": "Rerun B045, B041, B038, and B MOT.",
                "protected_stop_rule": "Stop before token correction.",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_original_return_status_conflict_preview"]["status"] == "fail"
    assert "live_write_rows=1" in rows["b_original_return_status_conflict_preview"]["actual_proof"]


def test_b_original_return_status_apply_preview_clears_when_safe_and_classified(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "unsafe_original_token_id",
        "current_status",
        "target_status",
        "target_status_source",
        "apply_preview_lane",
        "apply_preview_readiness",
        "block_reason",
        "maintenance_required_before_apply",
        "requires_luke_live_apply",
        "preview_live_write_allowed",
        "protected_before_apply",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_return_status_apply_preview.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "unsafe_original_token_id": "TOKEN-1",
                "current_status": "allocated",
                "target_status": "unsellable",
                "target_status_source": "return_unsellable",
                "apply_preview_lane": "original_return_status_apply_preview_ready",
                "apply_preview_readiness": "ready_for_protected_b046_apply_window",
                "block_reason": "",
                "maintenance_required_before_apply": "1",
                "requires_luke_live_apply": "1",
                "preview_live_write_allowed": "0",
                "protected_before_apply": "1",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "bounded_worker_task": "Apply B046 in a protected window only.",
                "retest_rule": "Rerun B045, B063, B041, B038, B051, and B MOT.",
                "protected_stop_rule": "Stop before token correction.",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_original_return_status_apply_preview"]["status"] == "ok"
    assert "ready_apply_rows=1" in rows["b_original_return_status_apply_preview"]["actual_proof"]
    assert "missing_stop_rows=0" in rows["b_original_return_status_apply_preview"]["actual_proof"]


def test_b_original_return_status_apply_preview_fails_without_protected_stops(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "unsafe_original_token_id",
        "current_status",
        "target_status",
        "target_status_source",
        "apply_preview_lane",
        "apply_preview_readiness",
        "block_reason",
        "maintenance_required_before_apply",
        "requires_luke_live_apply",
        "preview_live_write_allowed",
        "protected_before_apply",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_return_status_apply_preview.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "unsafe_original_token_id": "TOKEN-1",
                "current_status": "allocated",
                "target_status": "unsellable",
                "target_status_source": "return_unsellable",
                "apply_preview_lane": "original_return_status_apply_preview_ready",
                "apply_preview_readiness": "ready_for_protected_b046_apply_window",
                "block_reason": "",
                "maintenance_required_before_apply": "0",
                "requires_luke_live_apply": "1",
                "preview_live_write_allowed": "0",
                "protected_before_apply": "1",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "bounded_worker_task": "Apply B046 in a protected window only.",
                "retest_rule": "Rerun B045, B063, B041, B038, B051, and B MOT.",
                "protected_stop_rule": "Stop before token correction.",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_original_return_status_apply_preview"]["status"] == "fail"
    assert "missing_stop_rows=1" in rows["b_original_return_status_apply_preview"]["actual_proof"]


def test_b_disposition_conflict_decision_preview_clears_when_safe_and_classified(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "decision_lane",
        "recommended_manager_position",
        "correction_option",
        "exception_option",
        "impact_summary",
        "protected_decision_required",
        "preview_live_write_allowed",
        "protected_before_apply",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
        "downstream_allocated_order_ids",
        "return_cogs_rows",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_disposition_conflict_decision_preview.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "decision_lane": "downstream_allocated_non_sellable_reuse_with_cogs",
                "recommended_manager_position": "Keep blocked.",
                "correction_option": "Protected correction.",
                "exception_option": "Protected exception.",
                "impact_summary": "Affects downstream sale.",
                "protected_decision_required": "1",
                "preview_live_write_allowed": "0",
                "protected_before_apply": "1",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "bounded_worker_task": "Prepare Luke decision packet.",
                "retest_rule": "Rerun B059 and B MOT.",
                "protected_stop_rule": "Stop before token correction.",
                "downstream_allocated_order_ids": "ORDER-LATER",
                "return_cogs_rows": "2",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_disposition_conflict_decision_preview"]["status"] == "ok"
    assert "preview_rows=1" in rows["b_disposition_conflict_decision_preview"]["actual_proof"]
    assert "protected_decision_rows=1" in rows["b_disposition_conflict_decision_preview"]["actual_proof"]
    assert "downstream_allocated_rows=1" in rows["b_disposition_conflict_decision_preview"]["actual_proof"]


def test_b_disposition_conflict_decision_preview_fails_if_roi_use_allowed(tmp_path: Path) -> None:
    cols = [
        "order_id",
        "sku",
        "decision_lane",
        "recommended_manager_position",
        "correction_option",
        "exception_option",
        "impact_summary",
        "protected_decision_required",
        "preview_live_write_allowed",
        "protected_before_apply",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_disposition_conflict_decision_preview.csv",
        cols,
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "decision_lane": "downstream_allocated_non_sellable_reuse_with_cogs",
                "recommended_manager_position": "Keep blocked.",
                "correction_option": "Protected correction.",
                "exception_option": "Protected exception.",
                "impact_summary": "Affects downstream sale.",
                "protected_decision_required": "1",
                "preview_live_write_allowed": "0",
                "protected_before_apply": "1",
                "roi_or_restock_use_allowed": "1",
                "sellerboard_final_truth_allowed": "0",
                "bounded_worker_task": "Prepare Luke decision packet.",
                "retest_rule": "Rerun B059 and B MOT.",
                "protected_stop_rule": "Stop before token correction.",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_disposition_conflict_decision_preview"]["status"] == "fail"
    assert "roi_rows=1" in rows["b_disposition_conflict_decision_preview"]["actual_proof"]


def test_b_disposition_correction_impact_preview_clears_when_safe_and_classified(tmp_path: Path) -> None:
    cols = [
        "return_order_id",
        "sku",
        "amazon_return_disposition",
        "reusable_return_token_ids",
        "reusable_token_statuses",
        "downstream_allocated_order_ids",
        "downstream_order_statuses",
        "downstream_order_header_seen_rows",
        "downstream_order_item_match_rows",
        "return_cogs_rows",
        "correction_impact_lane",
        "correction_preview_action",
        "correction_blocker",
        "future_apply_scope",
        "protected_decision_required",
        "would_touch_live_outputs",
        "preview_live_write_allowed",
        "protected_before_apply",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_impact_preview.csv",
        cols,
        [
            {
                "return_order_id": "RETURN-ORDER",
                "sku": "SKU-A",
                "amazon_return_disposition": "CUSTOMER_DAMAGED",
                "reusable_return_token_ids": "TOKEN-1",
                "reusable_token_statuses": "TOKEN-1:sold",
                "downstream_allocated_order_ids": "LATER-ORDER",
                "downstream_order_statuses": "LATER-ORDER:Shipped",
                "downstream_order_header_seen_rows": "1",
                "downstream_order_item_match_rows": "1",
                "return_cogs_rows": "2",
                "correction_impact_lane": "downstream_order_and_cogs_review_required",
                "correction_preview_action": "No-write correction review only.",
                "correction_blocker": "downstream_order_impact_protected",
                "future_apply_scope": "Protected preview first.",
                "protected_decision_required": "1",
                "would_touch_live_outputs": "token and COGS proof labels",
                "preview_live_write_allowed": "0",
                "protected_before_apply": "1",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "bounded_worker_task": "Prepare protected apply preview.",
                "retest_rule": "Rerun B060 and B MOT.",
                "protected_stop_rule": "Stop before live correction.",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_disposition_correction_impact_preview"]["status"] == "ok"
    assert "preview_rows=1" in rows["b_disposition_correction_impact_preview"]["actual_proof"]
    assert "protected_decision_rows=1" in rows["b_disposition_correction_impact_preview"]["actual_proof"]
    assert "downstream_allocated_rows=1" in rows["b_disposition_correction_impact_preview"]["actual_proof"]
    assert "return_cogs_rows=1" in rows["b_disposition_correction_impact_preview"]["actual_proof"]


def test_b_disposition_correction_impact_preview_fails_if_live_write_allowed(tmp_path: Path) -> None:
    cols = [
        "return_order_id",
        "sku",
        "amazon_return_disposition",
        "reusable_return_token_ids",
        "reusable_token_statuses",
        "downstream_allocated_order_ids",
        "downstream_order_statuses",
        "downstream_order_header_seen_rows",
        "downstream_order_item_match_rows",
        "return_cogs_rows",
        "correction_impact_lane",
        "correction_preview_action",
        "correction_blocker",
        "future_apply_scope",
        "protected_decision_required",
        "would_touch_live_outputs",
        "preview_live_write_allowed",
        "protected_before_apply",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_impact_preview.csv",
        cols,
        [
            {
                "return_order_id": "RETURN-ORDER",
                "sku": "SKU-A",
                "amazon_return_disposition": "DEFECTIVE",
                "reusable_return_token_ids": "TOKEN-1",
                "reusable_token_statuses": "TOKEN-1:sold",
                "downstream_allocated_order_ids": "LATER-ORDER",
                "downstream_order_statuses": "LATER-ORDER:Shipped",
                "downstream_order_header_seen_rows": "1",
                "downstream_order_item_match_rows": "1",
                "return_cogs_rows": "2",
                "correction_impact_lane": "downstream_order_and_cogs_review_required",
                "correction_preview_action": "No-write correction review only.",
                "correction_blocker": "downstream_order_impact_protected",
                "future_apply_scope": "Protected preview first.",
                "protected_decision_required": "1",
                "would_touch_live_outputs": "token and COGS proof labels",
                "preview_live_write_allowed": "1",
                "protected_before_apply": "1",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "bounded_worker_task": "Prepare protected apply preview.",
                "retest_rule": "Rerun B060 and B MOT.",
                "protected_stop_rule": "Stop before live correction.",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_disposition_correction_impact_preview"]["status"] == "fail"
    assert "live_write_rows=1" in rows["b_disposition_correction_impact_preview"]["actual_proof"]


def test_b_disposition_correction_apply_preview_clears_when_safe_and_classified(tmp_path: Path) -> None:
    cols = [
        "return_order_id",
        "sku",
        "amazon_return_disposition",
        "reused_token_id",
        "downstream_order_id",
        "downstream_order_status",
        "downstream_order_date",
        "reused_token_allocation_rows",
        "reused_token_cogs_rows",
        "replacement_candidate_token_id",
        "replacement_candidate_date_relation",
        "replacement_candidate_days_after_order",
        "replacement_date_validation_reason",
        "replacement_available_token_count",
        "replacement_before_order_count",
        "replacement_unknown_date_count",
        "correction_apply_lane",
        "correction_preview_action",
        "protected_decision_required",
        "requires_luke_live_apply",
        "preview_live_write_allowed",
        "protected_before_apply",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_apply_preview.csv",
        cols,
        [
            {
                "return_order_id": "RETURN-ORDER",
                "sku": "SKU-A",
                "amazon_return_disposition": "CUSTOMER_DAMAGED",
                "reused_token_id": "BAD-TOKEN",
                "downstream_order_id": "LATER-ORDER",
                "downstream_order_status": "Shipped",
                "downstream_order_date": "2026-02-01T10:00:00Z",
                "reused_token_allocation_rows": "1",
                "reused_token_cogs_rows": "1",
                "replacement_candidate_token_id": "CLEAN-TOKEN",
                "replacement_candidate_date_relation": "on_or_before_downstream_order",
                "replacement_candidate_days_after_order": "-31",
                "replacement_date_validation_reason": "Replacement token was available by the downstream order date.",
                "replacement_available_token_count": "3",
                "replacement_before_order_count": "1",
                "replacement_unknown_date_count": "0",
                "correction_apply_lane": "shipped_order_replacement_swap_preview_ready",
                "correction_preview_action": "No-write preview only.",
                "protected_decision_required": "1",
                "requires_luke_live_apply": "1",
                "preview_live_write_allowed": "0",
                "protected_before_apply": "1",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "bounded_worker_task": "Prepare guarded apply only after approval.",
                "retest_rule": "Rerun B061 and B MOT.",
                "protected_stop_rule": "Stop before live correction.",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_disposition_correction_apply_preview"]["status"] == "ok"
    assert "preview_rows=1" in rows["b_disposition_correction_apply_preview"]["actual_proof"]
    assert "replacement_ready_rows=1" in rows["b_disposition_correction_apply_preview"]["actual_proof"]
    assert "candidate_after_order_rows=0" in rows["b_disposition_correction_apply_preview"]["actual_proof"]
    assert "no_replacement_rows=0" in rows["b_disposition_correction_apply_preview"]["actual_proof"]


def test_b_disposition_correction_apply_preview_fails_without_luke_live_apply_stop(tmp_path: Path) -> None:
    cols = [
        "return_order_id",
        "sku",
        "amazon_return_disposition",
        "reused_token_id",
        "downstream_order_id",
        "downstream_order_status",
        "downstream_order_date",
        "reused_token_allocation_rows",
        "reused_token_cogs_rows",
        "replacement_candidate_token_id",
        "replacement_candidate_date_relation",
        "replacement_candidate_days_after_order",
        "replacement_date_validation_reason",
        "replacement_available_token_count",
        "replacement_before_order_count",
        "replacement_unknown_date_count",
        "correction_apply_lane",
        "correction_preview_action",
        "protected_decision_required",
        "requires_luke_live_apply",
        "preview_live_write_allowed",
        "protected_before_apply",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_apply_preview.csv",
        cols,
        [
            {
                "return_order_id": "RETURN-ORDER",
                "sku": "SKU-A",
                "amazon_return_disposition": "DEFECTIVE",
                "reused_token_id": "BAD-TOKEN",
                "downstream_order_id": "LATER-ORDER",
                "downstream_order_status": "Shipped",
                "downstream_order_date": "2026-02-01T10:00:00Z",
                "reused_token_allocation_rows": "1",
                "reused_token_cogs_rows": "1",
                "replacement_candidate_token_id": "",
                "replacement_candidate_date_relation": "no_replacement_candidate",
                "replacement_candidate_days_after_order": "",
                "replacement_date_validation_reason": "No clean available replacement token exists for this SKU.",
                "replacement_available_token_count": "0",
                "replacement_before_order_count": "0",
                "replacement_unknown_date_count": "0",
                "correction_apply_lane": "no_replacement_token_protected_shortage_or_exception_review",
                "correction_preview_action": "No-write preview only.",
                "protected_decision_required": "1",
                "requires_luke_live_apply": "0",
                "preview_live_write_allowed": "0",
                "protected_before_apply": "1",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "bounded_worker_task": "Prepare guarded apply only after approval.",
                "retest_rule": "Rerun B061 and B MOT.",
                "protected_stop_rule": "Stop before live correction.",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_disposition_correction_apply_preview"]["status"] == "fail"
    assert "missing_live_apply_stop_rows=1" in rows["b_disposition_correction_apply_preview"]["actual_proof"]


def _historical_replacement_stock_proof_columns() -> list[str]:
    return [
        "return_order_id",
        "sku",
        "downstream_order_id",
        "downstream_order_date",
        "reused_token_id",
        "visible_replacement_candidate_token_id",
        "visible_replacement_candidate_received_date",
        "visible_replacement_candidate_date_relation",
        "historical_replacement_label",
        "direct_replacement_swap_ready",
        "historical_candidate_token_id",
        "historical_candidate_received_date",
        "historical_candidate_status",
        "historical_candidate_allocated_order_id",
        "historical_candidate_allocation_date",
        "historical_candidate_cogs_rows",
        "historical_candidate_days_before_downstream_sale",
        "candidate_pool_currently_available_before_count",
        "candidate_pool_used_later_count",
        "candidate_pool_late_available_count",
        "candidate_pool_missing_date_count",
        "proof_reason",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "protected_before_apply",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    ]


def test_b_historical_replacement_stock_proof_clears_when_direct_ready_is_safe(tmp_path: Path) -> None:
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_historical_replacement_stock_proof.csv",
        _historical_replacement_stock_proof_columns(),
        [
            {
                "return_order_id": "RETURN-ORDER",
                "sku": "SKU-A",
                "downstream_order_id": "DOWNSTREAM-ORDER",
                "downstream_order_date": "2026-02-01T10:00:00Z",
                "reused_token_id": "BAD-TOKEN",
                "visible_replacement_candidate_token_id": "VISIBLE-CANDIDATE",
                "visible_replacement_candidate_received_date": "2026-04-01",
                "visible_replacement_candidate_date_relation": "after_downstream_order",
                "historical_replacement_label": "date_valid_currently_available",
                "direct_replacement_swap_ready": "1",
                "historical_candidate_token_id": "CLEAN-BEFORE",
                "historical_candidate_received_date": "2026-01-01",
                "historical_candidate_status": "available",
                "historical_candidate_allocated_order_id": "",
                "historical_candidate_allocation_date": "",
                "historical_candidate_cogs_rows": "0",
                "historical_candidate_days_before_downstream_sale": "31",
                "candidate_pool_currently_available_before_count": "1",
                "candidate_pool_used_later_count": "0",
                "candidate_pool_late_available_count": "1",
                "candidate_pool_missing_date_count": "0",
                "proof_reason": "A clean token existed before sale.",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "protected_before_apply": "1",
                "bounded_worker_task": "No-write proof.",
                "retest_rule": "Rerun B065 and B MOT.",
                "protected_stop_rule": "Stop before live correction.",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_historical_replacement_stock_proof"]["status"] == "ok"
    assert "date_valid_currently_available_rows=1" in rows["b_historical_replacement_stock_proof"]["actual_proof"]
    assert "unsafe_rows=0" in rows["b_historical_replacement_stock_proof"]["actual_proof"]


def test_b_historical_replacement_stock_proof_warns_when_rows_are_parked(tmp_path: Path) -> None:
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_historical_replacement_stock_proof.csv",
        _historical_replacement_stock_proof_columns(),
        [
            {
                "return_order_id": "RETURN-ORDER",
                "sku": "SKU-A",
                "downstream_order_id": "DOWNSTREAM-ORDER",
                "downstream_order_date": "2026-02-01T10:00:00Z",
                "reused_token_id": "BAD-TOKEN",
                "historical_replacement_label": "replacement_arrived_after_sale",
                "direct_replacement_swap_ready": "0",
                "historical_candidate_token_id": "CLEAN-LATE",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "protected_before_apply": "1",
                "bounded_worker_task": "Park late stock.",
                "retest_rule": "Rerun B065 and B MOT.",
                "protected_stop_rule": "Stop before live correction.",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_historical_replacement_stock_proof"]["status"] == "warn"
    assert "replacement_arrived_after_sale_rows=1" in rows["b_historical_replacement_stock_proof"]["actual_proof"]


def test_b_historical_replacement_stock_proof_fails_if_live_use_is_allowed(tmp_path: Path) -> None:
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_historical_replacement_stock_proof.csv",
        _historical_replacement_stock_proof_columns(),
        [
            {
                "return_order_id": "RETURN-ORDER",
                "sku": "SKU-A",
                "downstream_order_id": "DOWNSTREAM-ORDER",
                "downstream_order_date": "2026-02-01T10:00:00Z",
                "reused_token_id": "BAD-TOKEN",
                "historical_replacement_label": "date_valid_currently_available",
                "direct_replacement_swap_ready": "1",
                "historical_candidate_token_id": "CLEAN-BEFORE",
                "preview_live_write_allowed": "1",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "protected_before_apply": "1",
                "bounded_worker_task": "No-write proof.",
                "retest_rule": "Rerun B065 and B MOT.",
                "protected_stop_rule": "Stop before live correction.",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_historical_replacement_stock_proof"]["status"] == "fail"
    assert "unsafe_rows=1" in rows["b_historical_replacement_stock_proof"]["actual_proof"]


def test_b_historical_replacement_stock_proof_fails_on_missing_schema(tmp_path: Path) -> None:
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_historical_replacement_stock_proof.csv",
        ["return_order_id", "sku", "historical_replacement_label"],
        [
            {
                "return_order_id": "RETURN-ORDER",
                "sku": "SKU-A",
                "historical_replacement_label": "date_valid_currently_available",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_historical_replacement_stock_proof"]["status"] == "fail"
    assert "missing_schema=" in rows["b_historical_replacement_stock_proof"]["actual_proof"]


def _no_replacement_shortage_exception_review_columns() -> list[str]:
    return [
        "return_order_id",
        "sku",
        "amazon_return_disposition",
        "downstream_order_id",
        "downstream_order_date",
        "reused_token_id",
        "review_label",
        "direct_replacement_swap_ready",
        "candidate_token_id",
        "candidate_received_date",
        "candidate_status",
        "candidate_allocated_order_id",
        "candidate_allocation_date",
        "clean_same_sku_token_count",
        "clean_stock_available_before_count",
        "clean_stock_used_before_sale_count",
        "clean_stock_used_later_count",
        "clean_stock_late_available_count",
        "clean_stock_missing_date_count",
        "reused_token_allocation_rows",
        "reused_token_cogs_rows",
        "return_cogs_rows",
        "proof_reason",
        "manager_expectation",
        "mot_proof_check",
        "preview_live_write_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "protected_before_apply",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    ]


def _refund_fee_shipping_gap_review_columns() -> list[str]:
    return [
        "money_area",
        "manager_money_label",
        "source_metric",
        "source_value",
        "api_proof_state",
        "sellerboard_witness_rows",
        "gap_rows",
        "downstream_warning_rows",
        "live_roi_use_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "manager_expectation",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
        "source_path",
    ]


def _level3_fee_shipping_api_proof_map_columns() -> list[str]:
    return [
        "money_field",
        "api_source_file",
        "source_amount_types",
        "source_row_count",
        "official_output_file",
        "official_output_field",
        "official_output_row_count",
        "order_master_row_count",
        "required_keys_present",
        "missing_required_keys",
        "proof_label",
        "proof_reason",
        "live_roi_use_allowed",
        "roi_or_restock_use_allowed",
        "sellerboard_final_truth_allowed",
        "bounded_worker_task",
        "retest_rule",
        "protected_stop_rule",
    ]


def test_b_no_replacement_shortage_exception_review_warns_when_true_shortage_is_parked(tmp_path: Path) -> None:
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_no_replacement_shortage_exception_review.csv",
        _no_replacement_shortage_exception_review_columns(),
        [
            {
                "return_order_id": "RETURN-ORDER",
                "sku": "SKU-A",
                "amazon_return_disposition": "CUSTOMER_DAMAGED",
                "downstream_order_id": "DOWNSTREAM-ORDER",
                "downstream_order_date": "2026-02-23T11:23:29Z",
                "reused_token_id": "BAD-TOKEN",
                "review_label": "true_no_replacement_shortage",
                "direct_replacement_swap_ready": "0",
                "clean_same_sku_token_count": "29",
                "clean_stock_available_before_count": "0",
                "clean_stock_used_before_sale_count": "29",
                "clean_stock_used_later_count": "0",
                "clean_stock_late_available_count": "0",
                "clean_stock_missing_date_count": "0",
                "reused_token_allocation_rows": "1",
                "reused_token_cogs_rows": "1",
                "return_cogs_rows": "2",
                "proof_reason": "Clean stock already consumed.",
                "manager_expectation": "Stay parked.",
                "mot_proof_check": "B066 and B MOT.",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "protected_before_apply": "1",
                "bounded_worker_task": "Park shortage.",
                "retest_rule": "Rerun B066 and B MOT.",
                "protected_stop_rule": "Stop before live exception.",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_no_replacement_shortage_exception_review"]["status"] == "warn"
    assert "true_no_replacement_shortage_rows=1" in rows["b_no_replacement_shortage_exception_review"]["actual_proof"]
    assert "unsafe_rows=0" in rows["b_no_replacement_shortage_exception_review"]["actual_proof"]


def test_b_no_replacement_shortage_exception_review_clears_when_no_rows_are_visible(tmp_path: Path) -> None:
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_no_replacement_shortage_exception_review.csv",
        _no_replacement_shortage_exception_review_columns(),
        [],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_no_replacement_shortage_exception_review"]["status"] == "ok"
    assert "review_rows=0" in rows["b_no_replacement_shortage_exception_review"]["actual_proof"]


def test_b_no_replacement_shortage_exception_review_fails_if_roi_use_is_allowed(tmp_path: Path) -> None:
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_no_replacement_shortage_exception_review.csv",
        _no_replacement_shortage_exception_review_columns(),
        [
            {
                "return_order_id": "RETURN-ORDER",
                "sku": "SKU-A",
                "review_label": "true_no_replacement_shortage",
                "direct_replacement_swap_ready": "0",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "1",
                "sellerboard_final_truth_allowed": "0",
                "protected_before_apply": "1",
                "bounded_worker_task": "Park shortage.",
                "retest_rule": "Rerun B066 and B MOT.",
                "protected_stop_rule": "Stop before live exception.",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_no_replacement_shortage_exception_review"]["status"] == "fail"
    assert "unsafe_rows=1" in rows["b_no_replacement_shortage_exception_review"]["actual_proof"]


def test_b_no_replacement_shortage_exception_review_fails_on_missing_schema(tmp_path: Path) -> None:
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_no_replacement_shortage_exception_review.csv",
        ["return_order_id", "sku", "review_label"],
        [{"return_order_id": "RETURN-ORDER", "sku": "SKU-A", "review_label": "true_no_replacement_shortage"}],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_no_replacement_shortage_exception_review"]["status"] == "fail"
    assert "missing_schema=" in rows["b_no_replacement_shortage_exception_review"]["actual_proof"]


def test_b_disposition_correction_swap_apply_clears_when_manifest_counts_match(tmp_path: Path) -> None:
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_apply_preview.csv",
        [
            "return_order_id",
            "sku",
            "correction_apply_lane",
        ],
        [
            {
                "return_order_id": "RETURN-ORDER",
                "sku": "SKU-A",
                "correction_apply_lane": "shipped_order_replacement_swap_preview_ready",
            }
        ],
    )
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_swap_applied.csv",
        [
            "return_order_id",
            "sku",
            "downstream_order_id",
            "reused_token_id",
            "replacement_token_id",
            "previous_reused_status",
            "new_reused_status",
            "previous_replacement_status",
            "new_replacement_status",
            "allocation_rows_updated",
            "cogs_rows_updated",
            "correction_apply_lane",
            "action",
        ],
        [
            {
                "return_order_id": "RETURN-ORDER",
                "sku": "SKU-A",
                "downstream_order_id": "LATER-ORDER",
                "reused_token_id": "BAD-TOKEN",
                "replacement_token_id": "CLEAN-TOKEN",
                "previous_reused_status": "allocated",
                "new_reused_status": "unsellable",
                "previous_replacement_status": "available",
                "new_replacement_status": "allocated",
                "allocation_rows_updated": "1",
                "cogs_rows_updated": "1",
                "correction_apply_lane": "shipped_order_replacement_swap_preview_ready",
                "action": "protected_non_sellable_return_replacement_swap_applied",
            }
        ],
    )
    manifest = {
        "status": "applied",
        "eligible_rows": 1,
        "applied_rows": 1,
        "token_rows_updated": 2,
        "allocation_rows_updated": 1,
        "cogs_rows_updated": 1,
        "blocked_rows": 0,
        "reasons": [],
    }
    path = tmp_path / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_swap_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_disposition_correction_swap_apply"]["status"] == "ok"
    assert "manifest=applied" in rows["b_disposition_correction_swap_apply"]["value"]
    assert "token_rows_updated=2" in rows["b_disposition_correction_swap_apply"]["actual_proof"]


def test_b_disposition_correction_swap_apply_needs_decision_when_ready_preview_has_no_manifest(tmp_path: Path) -> None:
    _write_csv_rows(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_apply_preview.csv",
        [
            "return_order_id",
            "sku",
            "correction_apply_lane",
        ],
        [
            {
                "return_order_id": "RETURN-ORDER",
                "sku": "SKU-A",
                "correction_apply_lane": "shipped_order_replacement_swap_preview_ready",
            }
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_disposition_correction_swap_apply"]["status"] == "decision_needed"
    assert "replacement_ready=1" in rows["b_disposition_correction_swap_apply"]["value"]


def test_e_refund_roi_proof_fields_clear_when_performance_carries_api_labels(tmp_path: Path) -> None:
    cols = _columns("performance_summary")
    _write_csv_rows(
        tmp_path / "out" / "sku_performance_summary.csv",
        cols,
        [
            {
                "sku": "SKU-A",
                "window_days": "30",
                "units_sold": "10",
                "velocity_units_per_day": "1",
                "revenue_exvat_gbp": "100",
                "profit_exvat_gbp": "30",
                "roi_exvat": "50",
                "days_of_stock_left": "5",
                "reorder_flag": "yes",
                "units_sold_roi": "10",
                "units_sold_truth_30d": "10",
                "units_sold_velocity_30d": "10",
                "units_sold_source": "roi",
                "expected_refund_cost_per_unit_gbp": "0.7",
                "refund_unit_rate_30d": "0.1",
                "refund_unit_rate_90d": "0.08",
                "refund_units_30d": "1",
                "sales_units_30d": "10",
                "refund_cost_basis": "sale_cohort_90d",
                "refund_proof_state": "api_proved_or_not_applicable",
                "refund_sample_confidence": "high",
                "value_velocity_gbp_per_day": "1",
            }
        ],
    )
    result = build_e_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["e_refund_roi_proof_fields"]["status"] == "ok"


def test_o_refund_restock_confidence_fields_clear_when_source_view_carries_labels(tmp_path: Path) -> None:
    cols = [
        "seller_sku",
        "has_minimum_restock_inputs",
        "expected_refund_cost_per_unit_gbp",
        "refund_unit_rate_30d",
        "refund_unit_rate_90d",
        "refund_units_30d",
        "sales_units_30d",
        "refund_cost_basis",
        "refund_proof_state",
        "refund_sample_confidence",
        "expected_inbound_cost_per_unit_gbp",
        "inbound_cost_basis",
        "inbound_cost_confidence",
        "inbound_cost_source_asof",
        "profit_input_confidence",
        "profit_input_blockers",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "O" / "live" / "restock_source_view.csv",
        cols,
        [
            {
                "seller_sku": "SKU-A",
                "has_minimum_restock_inputs": "1",
                "expected_refund_cost_per_unit_gbp": "0.7",
                "refund_unit_rate_30d": "0.1",
                "refund_unit_rate_90d": "0.08",
                "refund_units_30d": "1",
                "sales_units_30d": "10",
                "refund_cost_basis": "sale_cohort_90d",
                "refund_proof_state": "api_proved_or_not_applicable",
                "refund_sample_confidence": "high",
                "expected_inbound_cost_per_unit_gbp": "0.2",
                "inbound_cost_basis": "allocated_inbound_cost_per_received_unit",
                "inbound_cost_confidence": "sku_allocated",
                "inbound_cost_source_asof": OBSERVED,
                "profit_input_confidence": "profit_inputs_verified",
                "profit_input_blockers": "",
            }
        ],
    )
    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["o_refund_restock_confidence_fields"]["status"] == "ok"


def test_o_expected_profit_confidence_warns_when_inbound_or_profit_inputs_are_weak(tmp_path: Path) -> None:
    cols = [
        "seller_sku",
        "has_minimum_restock_inputs",
        "expected_refund_cost_per_unit_gbp",
        "refund_unit_rate_30d",
        "refund_unit_rate_90d",
        "refund_units_30d",
        "sales_units_30d",
        "refund_cost_basis",
        "refund_proof_state",
        "refund_sample_confidence",
        "expected_inbound_cost_per_unit_gbp",
        "inbound_cost_basis",
        "inbound_cost_confidence",
        "inbound_cost_source_asof",
        "profit_input_confidence",
        "profit_input_blockers",
    ]
    _write_csv_rows(
        tmp_path / "out" / "systems" / "O" / "live" / "restock_source_view.csv",
        cols,
        [
            {
                "seller_sku": "SKU-A",
                "has_minimum_restock_inputs": "1",
                "expected_refund_cost_per_unit_gbp": "0.7",
                "refund_unit_rate_30d": "0.1",
                "refund_unit_rate_90d": "0.08",
                "refund_units_30d": "1",
                "sales_units_30d": "10",
                "refund_cost_basis": "sale_cohort_90d",
                "refund_proof_state": "api_proved_or_not_applicable",
                "refund_sample_confidence": "high",
                "expected_inbound_cost_per_unit_gbp": "",
                "inbound_cost_basis": "missing_sku_inbound_cost_allocation",
                "inbound_cost_confidence": "missing",
                "inbound_cost_source_asof": "",
                "profit_input_confidence": "missing_profit_inputs",
                "profit_input_blockers": "missing_inbound_cost_confidence",
            }
        ],
    )
    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["o_refund_restock_confidence_fields"]["status"] == "warn"
    assert "minimum_input_rows_with_weak_profit_inputs=1" in rows["o_refund_restock_confidence_fields"]["value"]
    assert "weak_inbound_rows=1" in rows["o_refund_restock_confidence_fields"]["actual_proof"]


def test_o_inbound_fba_cost_allocation_proof_warns_when_sku_attachment_is_missing(tmp_path: Path) -> None:
    _write_csv_rows(
        tmp_path / "out" / "systems" / "O" / "live" / "restock_inbound_fba_cost_proof_live.csv",
        [
            "proof_utc",
            "check_name",
            "status",
            "proof_state",
            "safe_for_profit_use",
            "source_rows",
            "linked_rows",
            "unlinked_rows",
            "restock_rows",
            "restock_rows_with_sku_cost",
            "restock_rows_missing_sku_cost",
            "source_path",
            "proof_message",
        ],
        [
            {
                "proof_utc": OBSERVED,
                "check_name": "inbound_cost_events",
                "status": "warn",
                "proof_state": "inbound_cost_events_unlinked",
                "safe_for_profit_use": "0",
                "source_rows": "32",
                "linked_rows": "0",
                "unlinked_rows": "32",
                "restock_rows": "608",
                "restock_rows_with_sku_cost": "0",
                "restock_rows_missing_sku_cost": "608",
                "source_path": "out/inbound_cost_events.csv",
                "proof_message": "Inbound/FBA cost rows exist but do not carry a shipment link.",
            },
            {
                "proof_utc": OBSERVED,
                "check_name": "sku_cost_allocation",
                "status": "warn",
                "proof_state": "sku_level_cost_proof_missing",
                "safe_for_profit_use": "0",
                "source_rows": "0",
                "linked_rows": "0",
                "unlinked_rows": "0",
                "restock_rows": "608",
                "restock_rows_with_sku_cost": "0",
                "restock_rows_missing_sku_cost": "608",
                "source_path": "out/inbound_costs_allocated_sku.csv",
                "proof_message": "No SKU-level inbound/FBA cost allocation is available for O to use.",
            },
            {
                "proof_utc": OBSERVED,
                "check_name": "restock_source_attachment",
                "status": "warn",
                "proof_state": "restock_rows_missing_sku_cost",
                "safe_for_profit_use": "0",
                "source_rows": "608",
                "linked_rows": "0",
                "unlinked_rows": "608",
                "restock_rows": "608",
                "restock_rows_with_sku_cost": "0",
                "restock_rows_missing_sku_cost": "608",
                "source_path": "out/systems/O/live/restock_source_view.csv",
                "proof_message": "O restock rows still need SKU-level inbound/FBA cost proof before profit is clean.",
            },
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["o_inbound_fba_cost_allocation_proof"]["status"] == "warn"
    assert "safe_rows=0" in rows["o_inbound_fba_cost_allocation_proof"]["value"]
    assert "event_linked_rows=0" in rows["o_inbound_fba_cost_allocation_proof"]["actual_proof"]


def test_o_profit_input_blocker_breakdown_warns_but_stays_user_working_safe(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_profit_input_blocker_breakdown_live.csv",
        [
            "proof_utc",
            "seller_sku",
            "asin",
            "supplier_name",
            "supplier_code",
            "has_minimum_restock_inputs",
            "source_class",
            "action_safety_state",
            "action_ready_now",
            "refund_proof_state",
            "refund_sample_confidence",
            "inbound_cost_confidence",
            "inbound_cost_basis",
            "expected_inbound_cost_per_unit_gbp",
            "profit_input_confidence",
            "profit_input_blockers",
            "blocker_group",
            "primary_blocker",
            "next_safe_action",
            "needs_luke_decision",
            "safe_for_clean_buy",
            "safe_for_po",
            "source_path",
        ],
        [
            {
                "proof_utc": OBSERVED,
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "has_minimum_restock_inputs": "1",
                "source_class": "native_o",
                "action_safety_state": "blocked_from_clean_buy",
                "action_ready_now": "0",
                "refund_proof_state": "api_proved_or_not_applicable",
                "refund_sample_confidence": "high",
                "inbound_cost_confidence": "missing",
                "inbound_cost_basis": "missing_sku_inbound_cost_allocation",
                "expected_inbound_cost_per_unit_gbp": "",
                "profit_input_confidence": "missing_profit_inputs",
                "profit_input_blockers": "missing_inbound_cost_confidence",
                "blocker_group": "inbound|profit",
                "primary_blocker": "inbound_fba_cost_missing",
                "next_safe_action": "build_sku_level_inbound_fba_cost_proof",
                "needs_luke_decision": "0",
                "safe_for_clean_buy": "0",
                "safe_for_po": "0",
                "source_path": "out/systems/O/live/restock_source_view.csv",
            }
        ],
    )
    _write_csv_rows(
        live / "restock_profit_input_blocker_breakdown_health.csv",
        ["proof_utc", "check", "status", "value", "notes", "source_path"],
        [
            {
                "proof_utc": OBSERVED,
                "check": "profit_input_blocker_rows",
                "status": "warn",
                "value": "minimum_input_rows=1;weak_rows=1",
                "notes": "blocked",
                "source_path": "out/systems/O/live/restock_source_view.csv",
            },
            {
                "proof_utc": OBSERVED,
                "check": "weak_input_lanes",
                "status": "warn",
                "value": "refund=0;inbound=1;profit=1;token_cost=0",
                "notes": "blocked",
                "source_path": "out/systems/O/live/restock_source_view.csv",
            },
            {
                "proof_utc": OBSERVED,
                "check": "buy_safety",
                "status": "ok",
                "value": "safe_for_clean_buy=0;safe_for_po=0;rows=1",
                "notes": "safe",
                "source_path": "out/systems/O/live/restock_profit_input_blocker_breakdown_live.csv",
            },
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["o_profit_input_blocker_breakdown"]["status"] == "warn"
    assert rows["o_profit_input_blocker_breakdown"]["value"] == "minimum_input_rows=1;weak_rows=1;refund=0;inbound=1;profit=1;token_cost=0"
    assert rows["o_user_working_readiness"]["status"] == "ok"
    assert "o_profit_input_blocker_breakdown:warn" in rows["o_user_working_readiness"]["actual_proof"]


def test_o_token_cost_trust_gate_warns_when_untrusted_rows_are_blocked(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_token_cost_trust_gate_live.csv",
        [
            "proof_utc",
            "seller_sku",
            "current_token_cost_gbp",
            "token_cost_trust_state",
            "token_cost_trust_basis",
            "token_cost_trust_source",
            "token_cost_trust_blockers",
            "b_fallback_audit_rows",
            "b_weak_fallback_rows_for_sku",
            "token_ledger_fallback_rows_for_sku",
            "safe_for_clean_buy",
            "safe_for_po",
            "source_path",
        ],
        [
            {
                "proof_utc": OBSERVED,
                "seller_sku": "6V-EEC1-2S9Z",
                "current_token_cost_gbp": "4.35",
                "token_cost_trust_state": "weak_fallback_cost",
                "token_cost_trust_basis": "b_fallback_token_cost_audit_blocks_roi_or_restock",
                "token_cost_trust_source": "out/systems/B/refunds/b_fallback_token_cost_audit.csv",
                "token_cost_trust_blockers": "weak_fallback_token_cost",
                "b_fallback_audit_rows": "1",
                "b_weak_fallback_rows_for_sku": "1",
                "token_ledger_fallback_rows_for_sku": "250",
                "safe_for_clean_buy": "0",
                "safe_for_po": "0",
                "source_path": "out/sku_performance_summary.csv",
            }
        ],
    )
    _write_csv_rows(
        live / "restock_token_cost_trust_gate_health.csv",
        ["proof_utc", "check", "status", "value", "notes", "source_path"],
        [
            {
                "proof_utc": OBSERVED,
                "check": "token_cost_trust_gate_rows",
                "status": "warn",
                "value": "rows=1;not_trusted=1;weak_fallback=1;missing_token_cost=0;not_verified=0",
                "notes": "blocked",
                "source_path": "out/sku_performance_summary.csv",
            }
        ],
    )
    _write_csv_rows(
        live / "reorder_input_coverage_report.csv",
        ["seller_sku", "action_ready_now", "token_cost_trust_state"],
        [{"seller_sku": "6V-EEC1-2S9Z", "action_ready_now": "0", "token_cost_trust_state": "weak_fallback_cost"}],
    )
    _write_csv_rows(
        live / "restock_session_review_live.csv",
        ["seller_sku", "action_safety_state", "token_cost_trust_state"],
        [{"seller_sku": "6V-EEC1-2S9Z", "action_safety_state": "blocked_from_clean_buy", "token_cost_trust_state": "weak_fallback_cost"}],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["o_token_cost_trust_gate"]["status"] == "warn"
    assert rows["o_token_cost_trust_gate"]["value"] == "rows=1;untrusted_rows=1"


def test_o_token_cost_trust_gate_fails_when_untrusted_row_is_action_ready(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_token_cost_trust_gate_live.csv",
        [
            "proof_utc",
            "seller_sku",
            "current_token_cost_gbp",
            "token_cost_trust_state",
            "token_cost_trust_basis",
            "token_cost_trust_source",
            "token_cost_trust_blockers",
            "b_fallback_audit_rows",
            "b_weak_fallback_rows_for_sku",
            "token_ledger_fallback_rows_for_sku",
            "safe_for_clean_buy",
            "safe_for_po",
            "source_path",
        ],
        [
            {
                "proof_utc": OBSERVED,
                "seller_sku": "SKU-BAD",
                "current_token_cost_gbp": "2.00",
                "token_cost_trust_state": "not_verified",
                "token_cost_trust_basis": "b_fallback_token_cost_audit_missing",
                "token_cost_trust_source": "out/sku_performance_summary.csv",
                "token_cost_trust_blockers": "missing_b_fallback_token_cost_audit",
                "b_fallback_audit_rows": "0",
                "b_weak_fallback_rows_for_sku": "0",
                "token_ledger_fallback_rows_for_sku": "0",
                "safe_for_clean_buy": "0",
                "safe_for_po": "0",
                "source_path": "out/sku_performance_summary.csv",
            }
        ],
    )
    _write_csv_rows(
        live / "restock_token_cost_trust_gate_health.csv",
        ["proof_utc", "check", "status", "value", "notes", "source_path"],
        [
            {
                "proof_utc": OBSERVED,
                "check": "token_cost_trust_gate_rows",
                "status": "warn",
                "value": "rows=1;not_trusted=1;weak_fallback=0;missing_token_cost=0;not_verified=1",
                "notes": "blocked",
                "source_path": "out/sku_performance_summary.csv",
            }
        ],
    )
    _write_csv_rows(
        live / "reorder_input_coverage_report.csv",
        ["seller_sku", "action_ready_now", "token_cost_trust_state"],
        [{"seller_sku": "SKU-BAD", "action_ready_now": "1", "token_cost_trust_state": "not_verified"}],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["o_token_cost_trust_gate"]["status"] == "fail"
    assert "unsafe_action_ready_rows=1" in rows["o_token_cost_trust_gate"]["value"]


def test_o_profit_input_blocker_breakdown_fails_if_it_claims_buy_or_po_safe(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_profit_input_blocker_breakdown_live.csv",
        [
            "proof_utc",
            "seller_sku",
            "asin",
            "primary_blocker",
            "needs_luke_decision",
            "safe_for_clean_buy",
            "safe_for_po",
        ],
        [
            {
                "proof_utc": OBSERVED,
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "primary_blocker": "inbound_fba_cost_missing",
                "needs_luke_decision": "0",
                "safe_for_clean_buy": "1",
                "safe_for_po": "0",
            }
        ],
    )
    _write_csv_rows(
        live / "restock_profit_input_blocker_breakdown_health.csv",
        ["proof_utc", "check", "status", "value", "notes", "source_path"],
        [
            {
                "proof_utc": OBSERVED,
                "check": "profit_input_blocker_rows",
                "status": "warn",
                "value": "minimum_input_rows=1;weak_rows=1",
                "notes": "blocked",
                "source_path": "out/systems/O/live/restock_source_view.csv",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["o_profit_input_blocker_breakdown"]["status"] == "fail"
    assert rows["o_profit_input_blocker_breakdown"]["value"] == "unsafe_rows=1"


def test_o_inbound_fba_source_options_warns_when_only_protected_routes_exist(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_inbound_fba_source_options_live.csv",
        [
            "proof_utc",
            "route_id",
            "route_name",
            "route_class",
            "status",
            "source_rows",
            "linked_rows",
            "safe_for_profit_use",
            "needs_luke_decision",
            "route_message",
            "next_step",
            "source_path",
        ],
        [
            {
                "proof_utc": OBSERVED,
                "route_id": "direct_fee_event_shipment_link",
                "route_name": "Fee event has shipment ID",
                "route_class": "direct",
                "status": "missing",
                "source_rows": "51",
                "linked_rows": "0",
                "safe_for_profit_use": "0",
                "needs_luke_decision": "0",
                "route_message": "missing",
                "next_step": "keep_blocked_no_direct_fee_link",
                "source_path": "out/inbound_cost_events.csv",
            },
            {
                "proof_utc": OBSERVED,
                "route_id": "inbound_fee_average_policy",
                "route_name": "Average inbound/FBA fee policy",
                "route_class": "protected_policy",
                "status": "protected_not_automatic",
                "source_rows": "2",
                "linked_rows": "0",
                "safe_for_profit_use": "0",
                "needs_luke_decision": "1",
                "route_message": "protected",
                "next_step": "needs_user_policy_if_used",
                "source_path": "out/financial_events_inbound_summary.csv",
            },
        ],
    )
    _write_csv_rows(
        live / "restock_inbound_fba_source_options_health.csv",
        ["proof_utc", "check", "status", "value", "notes", "source_path"],
        [
            {
                "proof_utc": OBSERVED,
                "check": "direct_safe_routes",
                "status": "warn",
                "value": "direct_safe_routes=0;protected_routes=1",
                "notes": "blocked",
                "source_path": "out/inbound_cost_events.csv",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["o_inbound_fba_source_options"]["status"] == "warn"
    assert rows["o_inbound_fba_source_options"]["value"] == "direct_safe_routes=0;protected_routes=1"
    assert rows["o_user_working_readiness"]["status"] == "ok"
    assert "o_inbound_fba_source_options:warn" in rows["o_user_working_readiness"]["actual_proof"]


def test_o_inbound_fba_source_options_fails_if_protected_route_is_profit_safe(tmp_path: Path) -> None:
    _write_o_midbuild_outputs(tmp_path)
    live = tmp_path / "out" / "systems" / "O" / "live"
    _write_csv_rows(
        live / "restock_inbound_fba_source_options_live.csv",
        [
            "proof_utc",
            "route_id",
            "route_class",
            "status",
            "source_rows",
            "linked_rows",
            "safe_for_profit_use",
            "needs_luke_decision",
        ],
        [
            {
                "proof_utc": OBSERVED,
                "route_id": "inbound_fee_average_policy",
                "route_class": "protected_policy",
                "status": "protected_not_automatic",
                "source_rows": "2",
                "linked_rows": "0",
                "safe_for_profit_use": "1",
                "needs_luke_decision": "1",
            }
        ],
    )
    _write_csv_rows(
        live / "restock_inbound_fba_source_options_health.csv",
        ["proof_utc", "check", "status", "value", "notes", "source_path"],
        [
            {
                "proof_utc": OBSERVED,
                "check": "direct_safe_routes",
                "status": "warn",
                "value": "direct_safe_routes=0;protected_routes=1",
                "notes": "blocked",
                "source_path": "out/inbound_cost_events.csv",
            }
        ],
    )

    result = build_o_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["o_inbound_fba_source_options"]["status"] == "fail"
    assert rows["o_inbound_fba_source_options"]["value"] == "unsafe_protected_clean=1;unsafe_direct_clean=0"


def test_b_warning_worklist_parks_in_quiet_autonomy(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_b_sellerboard_bridge_outputs(tmp_path, return_gap=2, fee_detail_rows=0, refund_nonzero_rows=0)

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    first_worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    first_item = next(row for row in first_worklist_rows if row["check"] == "b_sellerboard_refund_fee_roi_bridge")
    assert first_item["status"] == "new"

    _write_quiet_autonomy_policy(tmp_path)
    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    parked_item = next(row for row in worklist_rows if row["check"] == "b_sellerboard_refund_fee_roi_bridge")

    assert result["status"] == "warn"
    assert rows["b_sellerboard_refund_fee_roi_bridge"]["status"] == "warn"
    assert parked_item["status"] == "parked"
    assert parked_item["luke_action_required"] == "0"


def test_b_marketplace_coverage_gap_creates_bounded_worklist_item(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_b_marketplace_gap_inputs(tmp_path)

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    work_item = next(row for row in worklist_rows if row["check"] == "b_marketplace_sellerboard_gaps")

    assert result["status"] == "fail"
    assert rows["b_marketplace_coverage_report"]["status"] == "fail"
    assert rows["b_marketplace_sellerboard_gaps"]["status"] == "fail"
    assert rows["b_marketplace_shared_cursor_risk"]["status"] == "fail"
    assert work_item["work_item_id"] == "MOT_B_B_MARKETPLACE_SELLERBOARD_GAPS"
    assert "no B run" in work_item["forbidden_actions"]
    assert "no marker edit" in work_item["safe_repair_boundary"]


def test_b_marketplace_coverage_status_warning_is_parked_on_board(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_b_completion_clean_inputs(tmp_path)
    _write_csv_rows(
        tmp_path / "out" / "systems" / "M" / "sellerboard_bridge" / ORDER_RECONCILIATION_NAME,
        ORDER_RECONCILIATION_COLUMNS,
        [
            {
                "amazon_order_id": "205-1111111-1111111",
                "sellerboard_status": "Unshipped",
                "sellerboard_purchase_utc": "2026-05-26T10:00:00Z",
                "sellerboard_sales_channel": "Amazon.co.uk",
                "sellerboard_asin": "B000000001",
                "mapped_sku": "SKU-UK",
                "local_marketplace_id": "A1F83G8C2ARO7P",
                "match_status": "status_difference",
                "proof_label": "Sellerboard bridge estimate",
            },
            {
                "amazon_order_id": "171-1388771-2409132",
                "sellerboard_status": "Shipped",
                "sellerboard_purchase_utc": "2026-05-23T11:59:20Z",
                "sellerboard_sales_channel": "Amazon.ae",
                "sellerboard_asin": "B072K2PG11",
                "mapped_sku": "GH-XAAE-HRU7",
                "local_marketplace_id": "A2VIGQ35RCS4UG",
                "match_status": "matched",
                "proof_label": "API proved",
            },
        ],
    )

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    work_item = next(row for row in worklist_rows if row["check"] == "b_marketplace_coverage_report")

    assert rows["b_marketplace_coverage_report"]["status"] == "warn"
    assert rows["b_marketplace_sellerboard_gaps"]["status"] == "ok"
    assert rows["b_marketplace_shared_cursor_risk"]["status"] == "ok"
    assert "status_diff_warn_rows=1" in rows["b_marketplace_coverage_report"]["actual_proof"]
    assert "warning_labelled_status_difference=1" in rows["b_marketplace_coverage_report"]["actual_proof"]
    assert work_item["status"] == "parked"
    assert work_item["luke_action_required"] == "0"
    assert "no missing shipped-order" in work_item["notes"]


def test_b_clean_retest_marks_fixed_item_proved(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path, stale_check="b_orders_all")
    _write_b_locks(tmp_path)
    output_dir = tmp_path / "out" / "systems" / "M"
    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    write_hourly_mot_outputs(result, output_dir)
    update_mot_work_item_status(
        output_dir=output_dir,
        work_item_id="MOT_B_B_ORDERS_ALL",
        status="fixed_needs_retest",
        observed_utc=OBSERVED,
    )

    _write_b_required_outputs(tmp_path)
    clean_result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(clean_result, output_dir)
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    proved = next(row for row in worklist_rows if row["work_item_id"] == "MOT_B_B_ORDERS_ALL")

    assert clean_result["status"] == "ok"
    assert proved["status"] == "proved"


def test_other_flow_mot_does_not_mark_b_work_item_proved(tmp_path: Path) -> None:
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path, stale_check="b_orders_all")
    _write_b_locks(tmp_path)
    output_dir = tmp_path / "out" / "systems" / "M"

    b_result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    write_hourly_mot_outputs(b_result, output_dir)

    _write_e_manifest(tmp_path)
    _write_e_run_log(tmp_path)
    _write_e_input_proofs(tmp_path)
    _write_e_required_outputs(tmp_path)
    _write_e_coverage_summary(tmp_path)
    _write_e_health(tmp_path)
    e_result = build_e_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(e_result, output_dir)
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    b_item = next(row for row in worklist_rows if row["work_item_id"] == "MOT_B_B_ORDERS_ALL")

    assert e_result["status"] == "ok"
    assert b_item["flow"] == "B"
    assert b_item["status"] == "new"


def test_combined_mot_rollup_keeps_a_b_e_and_f_visible(tmp_path: Path) -> None:
    _write_manifest(tmp_path, final_state="partial")
    _write_required_outputs(tmp_path)
    _write_sql_tables(tmp_path)
    a_result = build_a_hourly_mot(root=tmp_path, observed_utc=OBSERVED)

    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    b_result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)

    _write_e_manifest(tmp_path)
    _write_e_run_log(tmp_path)
    _write_e_input_proofs(tmp_path)
    _write_e_required_outputs(tmp_path)
    _write_e_coverage_summary(tmp_path)
    _write_e_health(tmp_path)
    path = tmp_path / "out" / "sku_performance_summary.csv"
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    rows.append(
        {
            **rows[-1],
            "sku": "SKU3",
            "units_sold_source": "velocity",
            "profit_confidence": "profit_missing",
            "sales_truth_state": "velocity_only",
            "missing_reason": "velocity_only_sales_truth",
            "missing_roi_reason": "velocity_only_sales_truth",
            "missing_roi_reason_detail": "velocity_only_sales_truth",
        }
    )
    _write_csv_rows(path, list(rows[0].keys()), rows)
    e_result = build_e_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    _write_f_outputs(tmp_path)
    f_result = build_f_hourly_mot(root=tmp_path, observed_utc=OBSERVED)

    output_dir = tmp_path / "out" / "systems" / "M"
    paths = write_all_hourly_mot_outputs([a_result, b_result, e_result, f_result], output_dir)
    rollup_rows = list(csv.DictReader(paths["mot_rollup_latest_csv"].open(newline="", encoding="utf-8")))
    latest_rows = list(csv.DictReader(paths["mot_latest_csv"].open(newline="", encoding="utf-8")))
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    summary = json.loads(paths["mot_rollup_latest_json"].read_text(encoding="utf-8"))

    assert {row["flow"] for row in rollup_rows} == {"A", "B", "E", "F"}
    assert {row["flow"] for row in latest_rows} == {"A", "B", "E", "F"}
    assert summary["status"] == "fail"
    assert any(row["work_item_id"] == "MOT_A_A_LATEST_MANIFEST" for row in worklist_rows)
    assert not any(row["check"] in {"b_old_checklist_clue", "e_optional_publish_proof"} for row in worklist_rows)


def test_single_flow_run_refreshes_combined_rollup_without_proving_other_flow(tmp_path: Path) -> None:
    _write_manifest(tmp_path, final_state="partial")
    _write_required_outputs(tmp_path)
    _write_sql_tables(tmp_path)
    output_dir = tmp_path / "out" / "systems" / "M"
    a_result = build_a_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    write_hourly_mot_outputs(a_result, output_dir)

    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    b_result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(b_result, output_dir)
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    latest_rows = list(csv.DictReader(paths["mot_latest_csv"].open(newline="", encoding="utf-8")))
    a_item = next(row for row in worklist_rows if row["work_item_id"] == "MOT_A_A_LATEST_MANIFEST")

    assert a_item["status"] == "new"
    assert {row["flow"] for row in latest_rows} == {"A", "B"}


def test_flow_work_item_is_proved_only_when_that_flow_clears(tmp_path: Path) -> None:
    _write_manifest(tmp_path, final_state="partial")
    _write_required_outputs(tmp_path)
    _write_sql_tables(tmp_path)
    output_dir = tmp_path / "out" / "systems" / "M"
    a_result = build_a_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    write_hourly_mot_outputs(a_result, output_dir)

    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    b_result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    write_hourly_mot_outputs(b_result, output_dir)

    _write_manifest(tmp_path, final_state="completed")
    clean_a_result = build_a_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(clean_a_result, output_dir)
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    a_item = next(row for row in worklist_rows if row["work_item_id"] == "MOT_A_A_LATEST_MANIFEST")

    assert clean_a_result["status"] == "ok"
    assert a_item["status"] == "proved"


def test_build_all_hourly_mot_writes_flow_files_and_rollup(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_required_outputs(tmp_path)
    _write_sql_tables(tmp_path)
    _write_b_manifest(tmp_path)
    _write_b_required_outputs(tmp_path)
    _write_b_locks(tmp_path)
    _write_e_manifest(tmp_path)
    _write_e_run_log(tmp_path)
    _write_e_input_proofs(tmp_path)
    _write_e_required_outputs(tmp_path)
    _write_e_coverage_summary(tmp_path)
    _write_e_health(tmp_path)
    _write_f_outputs(tmp_path)
    _write_o_midbuild_outputs(tmp_path)

    results = build_all_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_all_hourly_mot_outputs(results, tmp_path / "out" / "systems" / "M")

    assert paths["hourly_mot_a_csv"].exists()
    assert paths["hourly_mot_b_csv"].exists()
    assert paths["hourly_mot_e_csv"].exists()
    assert paths["hourly_mot_h_csv"].exists()
    assert paths["hourly_mot_f_csv"].exists()
    assert paths["hourly_mot_o_csv"].exists()
    assert paths["mot_rollup_latest_csv"].exists()
    assert paths["mot_latest_csv"].exists()
    rollup_rows = list(csv.DictReader(paths["mot_rollup_latest_csv"].open(newline="", encoding="utf-8")))
    assert {row["flow"] for row in rollup_rows} == {"A", "B", "E", "H", "F", "O"}


def test_a018_floor_table_missing_is_not_verified_not_runtime_fail(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_required_outputs(tmp_path)
    _write_sql_tables(tmp_path)

    result = build_a_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "ok"
    assert rows["a018_phase1_floor_table"]["status"] == "not_checked"
    assert rows["a018_sql_phase1_floor_table"]["status"] == "not_checked"


def test_a018_floor_table_present_and_fresh_is_ok(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_required_outputs(tmp_path)
    _write_sql_tables(tmp_path)
    _write_optional_sql_tables(tmp_path)
    _write_floor_table(tmp_path)

    result = build_a_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["a018_phase1_floor_table"]["status"] == "ok"
    assert rows["a018_sql_phase1_floor_table"]["status"] == "ok"


def test_a_maintenance_handoff_proof_matches_latest_manifest(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_required_outputs(tmp_path)
    _write_sql_tables(tmp_path)
    _write_handoff_proof(tmp_path, final_run_id="A_test", proof_status="ok")

    result = build_a_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["a_maintenance_handoff_proof"]["status"] == "ok"
    assert rows["a_maintenance_handoff_proof"]["value"] == "matched_latest_run"


def test_a_maintenance_handoff_proof_older_than_manifest_is_not_verified(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_required_outputs(tmp_path)
    _write_sql_tables(tmp_path)
    _write_handoff_proof(tmp_path, final_run_id="OLDER_A", proof_status="ok")

    result = build_a_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["a_maintenance_handoff_proof"]["status"] == "not_checked"
    assert rows["a_maintenance_handoff_proof"]["value"] == "stale_for_latest_manifest"


def test_a_maintenance_handoff_failure_becomes_mot_fail(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_required_outputs(tmp_path)
    _write_sql_tables(tmp_path)
    _write_handoff_proof(tmp_path, final_run_id="A_test", proof_status="fail")

    result = build_a_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["a_maintenance_handoff_proof"]["status"] == "fail"


def test_a_interrupted_proof_after_safe_handoff_parks_until_next_normal_run(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path,
        final_state="partial",
        configured_step_count=11,
        recorded_step_count=8,
        steps=[
            {
                "name": "A016_refresh_phase1_daily_intel.py",
                "rc": 130,
                "step_status": "failed",
                "verification_status": "interrupted",
                "notes": "step interrupted elapsed=124.8s",
            }
        ],
    )
    _write_required_outputs(tmp_path)
    _write_sql_tables(tmp_path)
    _write_handoff_proof(
        tmp_path,
        final_run_id="A_test",
        proof_status="fail",
        final_state="partial",
        final_exit_code=130,
        include_handoff_evidence=True,
    )

    result = build_a_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    parked = {row["check"]: row for row in worklist_rows}

    assert result["status"] == "ok"
    assert rows["a_latest_manifest"]["status"] == "not_checked"
    assert rows["a_latest_manifest"]["value"] == "interrupted_pending_next_normal_a_run"
    assert rows["a_manifest_step_traversal"]["status"] == "not_checked"
    assert rows["a_maintenance_handoff_proof"]["status"] == "not_checked"
    assert "Park this A proof row" in rows["a_latest_manifest"]["manager_action"]
    assert "a_latest_manifest" not in parked


def test_hourly_mot_fails_when_real_data_file_is_old_even_if_manifest_completed(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_required_outputs(tmp_path, stale_check="a003_inventory_summaries")
    _write_sql_tables(tmp_path)

    result = build_a_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert result["status"] == "fail"
    assert rows["a_latest_manifest"]["status"] == "ok"
    assert rows["a003_inventory_summaries"]["status"] == "fail"
    assert rows["a003_inventory_summaries"]["value"] == "stale"


def test_hourly_mot_creates_worklist_and_retest_queue(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_required_outputs(tmp_path, stale_check="a003_inventory_summaries")
    _write_sql_tables(tmp_path)

    result = build_a_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    output_dir = tmp_path / "out" / "systems" / "M"
    paths = write_hourly_mot_outputs(result, output_dir)

    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    work_item = next(row for row in worklist_rows if row["check"] == "a003_inventory_summaries")
    assert work_item["work_item_id"] == "MOT_A_A003_INVENTORY_SUMMARIES"
    assert work_item["status"] == "new"
    assert "retest" in work_item["proof_required"].lower()

    updated = update_mot_work_item_status(
        output_dir=output_dir,
        work_item_id="MOT_A_A003_INVENTORY_SUMMARIES",
        status="fixed_needs_retest",
        note="Test repair ready for MOT proof.",
        observed_utc=OBSERVED,
    )
    assert updated["status"] == "fixed_needs_retest"

    retest_rows = list(csv.DictReader(paths["mot_retest_queue_csv"].open(newline="", encoding="utf-8")))
    assert retest_rows[0]["work_item_id"] == "MOT_A_A003_INVENTORY_SUMMARIES"
    assert retest_rows[0]["status"] == "pending"


def test_hourly_mot_marks_fixed_item_proved_after_clean_retest(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_required_outputs(tmp_path, stale_check="a003_inventory_summaries")
    _write_sql_tables(tmp_path)
    output_dir = tmp_path / "out" / "systems" / "M"
    result = build_a_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    write_hourly_mot_outputs(result, output_dir)
    update_mot_work_item_status(
        output_dir=output_dir,
        work_item_id="MOT_A_A003_INVENTORY_SUMMARIES",
        status="fixed_needs_retest",
        observed_utc=OBSERVED,
    )

    _write_required_outputs(tmp_path)
    clean_result = build_a_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(clean_result, output_dir)
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    proved = next(row for row in worklist_rows if row["work_item_id"] == "MOT_A_A003_INVENTORY_SUMMARIES")
    assert proved["status"] == "proved"
