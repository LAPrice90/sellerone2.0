from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._contract_io import write_f_contract_df
from scripts.flows.F.price_list_manager.FPM140_check_review_handoff_ready import check_review_handoff_ready
from scripts.flows.F.price_list_manager._schemas import MANAGER_HEALTH_COLUMNS, REVIEW_HANDOFF_STATUS_COLUMNS


def _seed_run_state(
    root: Path,
    *,
    run_status: str,
    pending_rows: str,
    completed_at_utc: str = "",
) -> None:
    write_f_contract_df(
        root,
        "supplier_price_list_run_state",
        pd.DataFrame(
            [
                {
                    "supplier_id": "entertainment_trading",
                    "supplier_name": "Entertainment Trading",
                    "run_id": "fpm_entertainment_trading_test",
                    "run_status": run_status,
                    "source_url": "",
                    "source_file_path": "Stocklist.xlsx",
                    "source_seen_at_utc": "2026-04-30T14:13:50Z",
                    "normalized_utc": "2026-04-30T15:14:17Z",
                    "total_rows": "3",
                    "pending_rows": pending_rows,
                    "done_rows": str(3 - int(pending_rows)),
                    "failed_rows": "1",
                    "held_rows": "0",
                    "next_row_index": "1" if pending_rows != "0" else "0",
                    "updated_at_utc": "2026-05-01T09:00:00Z",
                    "completed_at_utc": completed_at_utc,
                }
            ]
        ),
    )


def _seed_active_rows(root: Path, *, pending_rows: int) -> None:
    rows = []
    for index in range(1, pending_rows + 1):
        rows.append(
            {
                "run_id": "fpm_entertainment_trading_test",
                "supplier_id": "entertainment_trading",
                "supplier_name": "Entertainment Trading",
                "row_key": f"row_{index}",
                "supplier_sku": f"ET-{index}",
                "barcode": f"500000000000{index}",
                "supplier_title": f"Product {index}",
                "unit_cost": "1.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-30T14:13:50Z",
            }
        )
    write_f_contract_df(root, "supplier_price_list_active_run", pd.DataFrame(rows))


def _seed_scanner_evidence(root: Path) -> None:
    write_f_contract_df(
        root,
        "f_screening_row_state_live",
        pd.DataFrame(
            [
                {
                    "observed_utc": "2026-05-01T09:01:00Z",
                    "run_id": "fpm_entertainment_trading_test",
                    "supplier_id": "entertainment_trading",
                    "supplier_name": "Entertainment Trading",
                    "supplier_sku": "ET-1",
                    "barcode": "5000000000001",
                    "candidate_id": "candidate-pass",
                    "asin": "B000000001",
                    "row_status": "pass",
                    "last_stage": "complete",
                    "fail_code": "",
                    "attempt_count": "1",
                    "timeout_until_utc": "",
                    "mode": "screening",
                    "updated_at_utc": "2026-05-01T09:01:00Z",
                    "source_seen_at_utc": "2026-04-30T14:13:50Z",
                    "pf": "PASS",
                    "status_reason": "PASS",
                },
                {
                    "observed_utc": "2026-05-01T09:02:00Z",
                    "run_id": "fpm_entertainment_trading_test",
                    "supplier_id": "entertainment_trading",
                    "supplier_name": "Entertainment Trading",
                    "supplier_sku": "ET-2",
                    "barcode": "5000000000002",
                    "candidate_id": "candidate-timeout",
                    "asin": "B000000002",
                    "row_status": "timeout",
                    "last_stage": "roi_gate",
                    "fail_code": "ROIFAIL",
                    "attempt_count": "1",
                    "timeout_until_utc": "2026-05-02T09:02:00Z",
                    "mode": "screening",
                    "updated_at_utc": "2026-05-01T09:02:00Z",
                    "source_seen_at_utc": "2026-04-30T14:13:50Z",
                    "pf": "FAIL",
                    "status_reason": "ROIFAIL",
                },
            ]
        ),
    )
    write_f_contract_df(
        root,
        "feeder_legacy_first_checks_live",
        pd.DataFrame(
            [
                {
                    "candidate_id": "candidate-pass",
                    "supplier_sku": "ET-1",
                    "barcode": "5000000000001",
                    "supplier": "Entertainment Trading",
                    "asin": "B000000001",
                    "pf": "PASS",
                    "status_reason": "PASS",
                }
            ]
        ),
    )
    write_f_contract_df(
        root,
        "feeder_legacy_scrape_evidence_live",
        pd.DataFrame(
            [
                {
                    "observed_utc": "2026-05-01T09:01:00Z",
                    "scan_day": "2026-05-01",
                    "run_id": "fpm_entertainment_trading_test",
                    "candidate_id": "candidate-pass",
                    "supplier_id": "entertainment_trading",
                    "supplier_name": "Entertainment Trading",
                    "supplier_sku": "ET-1",
                    "barcode": "5000000000001",
                    "asin": "B000000001",
                    "title": "Product 1",
                    "first_check_status_code": "PASS",
                    "pf": "PASS",
                    "status_reason": "PASS",
                    "source_seen_at_utc": "2026-04-30T14:13:50Z",
                }
            ]
        ),
    )


def test_review_handoff_ready_after_completed_run_with_scanner_evidence(tmp_path: Path) -> None:
    _seed_run_state(tmp_path, run_status="completed", pending_rows="0", completed_at_utc="2026-05-01T09:05:00Z")
    _seed_active_rows(tmp_path, pending_rows=0)
    _seed_scanner_evidence(tmp_path)

    summary = check_review_handoff_ready(
        root=tmp_path,
        supplier_id="entertainment_trading",
        run_id="fpm_entertainment_trading_test",
        observed_utc="2026-05-01T09:06:00Z",
    )

    status_path = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "review_handoff_status.csv"
    health_path = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "review_handoff_health.csv"
    status = pd.read_csv(status_path, dtype=str).fillna("")
    health = pd.read_csv(health_path, dtype=str).fillna("")
    assert summary["handoff_state"] == "ready"
    assert summary["ready_to_publish_flag"] == "1"
    assert summary["screening_rows"] == "2"
    assert summary["first_check_pass_rows"] == "1"
    assert list(status.columns) == REVIEW_HANDOFF_STATUS_COLUMNS
    assert list(health.columns) == MANAGER_HEALTH_COLUMNS
    assert health.iloc[-1]["status"] == "ok"


def test_review_handoff_blocks_running_supplier_without_warning_health(tmp_path: Path) -> None:
    _seed_run_state(tmp_path, run_status="running", pending_rows="2")
    _seed_active_rows(tmp_path, pending_rows=2)
    _seed_scanner_evidence(tmp_path)

    summary = check_review_handoff_ready(
        root=tmp_path,
        supplier_id="entertainment_trading",
        run_id="fpm_entertainment_trading_test",
        observed_utc="2026-05-01T09:06:00Z",
    )

    assert summary["handoff_state"] == "not_ready"
    assert summary["ready_to_publish_flag"] == "0"
    assert "run_not_completed" in summary["block_reason"]
    assert "run_pending_rows_not_zero" in summary["block_reason"]
    assert "active_pending_rows_not_zero" in summary["block_reason"]
    assert summary["health_status"] == "ok"


def test_review_handoff_warns_when_completed_run_has_no_scanner_evidence(tmp_path: Path) -> None:
    _seed_run_state(tmp_path, run_status="completed", pending_rows="0", completed_at_utc="2026-05-01T09:05:00Z")
    _seed_active_rows(tmp_path, pending_rows=0)

    summary = check_review_handoff_ready(
        root=tmp_path,
        supplier_id="entertainment_trading",
        run_id="fpm_entertainment_trading_test",
        observed_utc="2026-05-01T09:06:00Z",
    )

    assert summary["handoff_state"] == "blocked"
    assert summary["ready_to_publish_flag"] == "0"
    assert summary["block_reason"] == "scanner_evidence_missing"
    assert summary["health_status"] == "warn"


def test_review_handoff_warns_when_completed_run_still_has_screening_pending(tmp_path: Path) -> None:
    _seed_run_state(tmp_path, run_status="completed", pending_rows="0", completed_at_utc="2026-05-01T09:05:00Z")
    _seed_active_rows(tmp_path, pending_rows=0)
    write_f_contract_df(
        tmp_path,
        "f_screening_row_state_live",
        pd.DataFrame(
            [
                {
                    "observed_utc": "2026-05-01T09:01:00Z",
                    "run_id": "fpm_entertainment_trading_test",
                    "supplier_id": "entertainment_trading",
                    "supplier_name": "Entertainment Trading",
                    "supplier_sku": "ET-1",
                    "barcode": "5000000000001",
                    "candidate_id": "candidate-pending",
                    "asin": "",
                    "row_status": "pending",
                    "last_stage": "",
                    "fail_code": "",
                    "attempt_count": "0",
                    "timeout_until_utc": "",
                    "mode": "screening",
                    "updated_at_utc": "2026-05-01T09:01:00Z",
                    "source_seen_at_utc": "2026-04-30T14:13:50Z",
                }
            ]
        ),
    )

    summary = check_review_handoff_ready(
        root=tmp_path,
        supplier_id="entertainment_trading",
        run_id="fpm_entertainment_trading_test",
        observed_utc="2026-05-01T09:06:00Z",
    )

    assert summary["handoff_state"] == "blocked"
    assert summary["ready_to_publish_flag"] == "0"
    assert summary["block_reason"] == "screening_pending_rows_not_zero"
    assert summary["health_status"] == "warn"


def test_review_handoff_blocks_completed_run_with_login_backtrack_pending(tmp_path: Path) -> None:
    _seed_run_state(tmp_path, run_status="completed", pending_rows="0", completed_at_utc="2026-05-01T09:05:00Z")
    _seed_active_rows(tmp_path, pending_rows=0)
    _seed_scanner_evidence(tmp_path)
    write_f_contract_df(
        tmp_path,
        "f_screening_row_state_live",
        pd.DataFrame(
            [
                {
                    "observed_utc": "2026-05-01T09:03:00Z",
                    "run_id": "fpm_entertainment_trading_test",
                    "supplier_id": "entertainment_trading",
                    "supplier_name": "Entertainment Trading",
                    "supplier_sku": "ET-3",
                    "barcode": "5000000000003",
                    "candidate_id": "candidate-login",
                    "asin": "B000000003",
                    "row_status": "login_backtrack_pending",
                    "last_stage": "webscrape",
                    "fail_code": "LOGIN_BACKTRACK",
                    "attempt_count": "1",
                    "timeout_until_utc": "",
                    "mode": "screening",
                    "updated_at_utc": "2026-05-01T09:03:00Z",
                    "source_seen_at_utc": "2026-04-30T14:13:50Z",
                    "pf": "",
                    "status_reason": "LOGIN_BACKTRACK_PENDING",
                }
            ]
        ),
    )

    summary = check_review_handoff_ready(
        root=tmp_path,
        supplier_id="entertainment_trading",
        run_id="fpm_entertainment_trading_test",
        observed_utc="2026-05-01T09:06:00Z",
    )

    assert summary["handoff_state"] == "blocked"
    assert summary["ready_to_publish_flag"] == "0"
    assert "screening_pending_rows_not_zero" in summary["block_reason"]
    assert "login_backtrack_pending_rows_not_zero" in summary["block_reason"]
    assert summary["screening_login_backtrack_rows"] == "1"
    assert summary["health_status"] == "warn"


def test_review_handoff_blocks_active_child_process_for_same_supplier(tmp_path: Path) -> None:
    _seed_run_state(tmp_path, run_status="completed", pending_rows="0", completed_at_utc="2026-05-01T09:05:00Z")
    _seed_active_rows(tmp_path, pending_rows=0)
    _seed_scanner_evidence(tmp_path)
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_child_status.txt").write_text(
        f"pid={os.getpid()}|supplier_id=entertainment_trading|started=2026-05-01T09:00:00Z|heartbeat=2026-05-01T09:06:00Z\n",
        encoding="utf-8",
    )

    summary = check_review_handoff_ready(
        root=tmp_path,
        supplier_id="entertainment_trading",
        run_id="fpm_entertainment_trading_test",
        observed_utc="2026-05-01T09:06:00Z",
    )

    assert summary["handoff_state"] == "not_ready"
    assert summary["ready_to_publish_flag"] == "0"
    assert summary["f061_child_active_flag"] == "1"
    assert summary["block_reason"] == "f061_child_active"
