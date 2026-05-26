from __future__ import annotations

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
from scripts.flows.F.price_list_manager.FPM150_build_completed_review_pack import build_completed_review_pack
from scripts.flows.F.price_list_manager._schemas import REVIEW_CANDIDATE_MANIFEST_COLUMNS


def _seed_run_state(root: Path, *, completed: bool) -> None:
    write_f_contract_df(
        root,
        "supplier_price_list_run_state",
        pd.DataFrame(
            [
                {
                    "supplier_id": "entertainment_trading",
                    "supplier_name": "Entertainment Trading",
                    "run_id": "fpm_entertainment_trading_test",
                    "run_status": "completed" if completed else "running",
                    "source_url": "",
                    "source_file_path": "Stocklist.xlsx",
                    "source_seen_at_utc": "2026-04-30T14:13:50Z",
                    "normalized_utc": "2026-04-30T15:14:17Z",
                    "total_rows": "1",
                    "pending_rows": "0" if completed else "1",
                    "done_rows": "1" if completed else "0",
                    "failed_rows": "0",
                    "held_rows": "0",
                    "next_row_index": "0" if completed else "1",
                    "updated_at_utc": "2026-05-01T09:00:00Z",
                    "completed_at_utc": "2026-05-01T09:05:00Z" if completed else "",
                }
            ]
        ),
    )
    active_rows = []
    if not completed:
        active_rows.append(
            {
                "run_id": "fpm_entertainment_trading_test",
                "supplier_id": "entertainment_trading",
                "supplier_name": "Entertainment Trading",
                "row_key": "row_1",
                "supplier_sku": "ET-1",
                "barcode": "5000000000001",
                "supplier_title": "Product 1",
                "unit_cost": "1.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "source_seen_at_utc": "2026-04-30T14:13:50Z",
            }
        )
    write_f_contract_df(root, "supplier_price_list_active_run", pd.DataFrame(active_rows))


def _seed_review_pack_inputs(root: Path) -> None:
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
                    "observed_utc": "2026-05-01T09:01:00Z",
                    "run_id": "older_run_not_selected",
                    "supplier_id": "entertainment_trading",
                    "supplier_name": "Entertainment Trading",
                    "supplier_sku": "ET-OLD",
                    "barcode": "5000000000099",
                    "candidate_id": "candidate-old",
                    "asin": "B000000099",
                    "row_status": "pass",
                    "last_stage": "complete",
                    "fail_code": "",
                    "attempt_count": "1",
                    "timeout_until_utc": "",
                    "mode": "screening",
                    "updated_at_utc": "2026-05-01T09:01:00Z",
                    "source_seen_at_utc": "2026-04-30T13:00:00Z",
                    "pf": "PASS",
                    "status_reason": "PASS",
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
                    "completed": "2026-05-01T09:01:00Z",
                    "barcode": "5000000000001",
                    "cost": "10.00",
                    "vat": "20",
                    "supplier": "Entertainment Trading",
                    "asin": "B000000001",
                    "main_rank": "1200",
                    "brand": "TestBrand",
                    "scan_day": "2026-05-01",
                    "title": "Reviewable Product",
                    "sales": "20",
                    "rating": "4.5",
                    "point_score": "4.00",
                    "history_score": "4.00",
                    "pf": "PASS",
                    "status_reason": "PASS",
                    "candidate_id": "candidate-pass",
                    "supplier_sku": "ET-1",
                },
                {
                    "completed": "2026-05-01T09:01:00Z",
                    "barcode": "5000000000099",
                    "cost": "10.00",
                    "vat": "20",
                    "supplier": "Entertainment Trading",
                    "asin": "B000000099",
                    "main_rank": "1200",
                    "brand": "TestBrand",
                    "scan_day": "2026-05-01",
                    "title": "Old Product",
                    "sales": "20",
                    "rating": "4.5",
                    "point_score": "4.00",
                    "history_score": "4.00",
                    "pf": "PASS",
                    "status_reason": "PASS",
                    "candidate_id": "candidate-old",
                    "supplier_sku": "ET-OLD",
                },
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
                    "title": "Reviewable Product",
                    "first_check_status_code": "PASS",
                    "pf": "PASS",
                    "status_reason": "PASS",
                    "bbp_sales_replay_demand_basis_units": "20",
                    "estimated_monthly_profit": "60",
                    "profit_per_unit_30d": "6",
                    "avg_30_day_price": "20",
                    "break_even": "10",
                    "opportunity_recommendation": "PASS",
                    "history_recommendation": "PASS",
                    "phase_recommendation": "PASS",
                    "historical_uk_reviews": "10",
                    "variant_reviews": "100",
                    "price_hist_new_30": "2",
                    "price_hist_new_90": "2",
                    "price_hist_new_180": "2",
                    "bbp_dashboard_yes_or_no": "NO",
                    "source_seen_at_utc": "2026-04-30T14:13:50Z",
                }
            ]
        ),
    )
    write_f_contract_df(
        root,
        "feeder_backtest_summary_live",
        pd.DataFrame(
            [
                {
                    "seller_sku": "ET-1",
                    "asin": "B000000001",
                    "decision_state": "pass",
                    "decision_confidence": "high",
                    "stability_state": "stable",
                    "expected_units_next_30d": "20",
                    "expected_profit_next_30d_gbp": "60",
                    "recommendation": "Managed fit",
                    "decision_reason_codes": "meets_profit_floor",
                }
            ]
        ),
    )


def test_completed_review_pack_does_not_build_for_running_scan(tmp_path: Path) -> None:
    _seed_run_state(tmp_path, completed=False)

    summary = build_completed_review_pack(
        root=tmp_path,
        supplier_id="entertainment_trading",
        run_id="fpm_entertainment_trading_test",
        observed_utc="2026-05-01T09:06:00Z",
    )

    manifest_path = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "entertainment_trading"
        / "fpm_entertainment_trading_test"
        / "manifest.csv"
    )
    assert summary["status"] == "blocked"
    assert summary["ready_to_publish_flag"] == "0"
    assert not manifest_path.exists()


def test_completed_review_pack_builds_raw_candidate_manifest_for_ready_run(tmp_path: Path) -> None:
    _seed_run_state(tmp_path, completed=True)
    _seed_review_pack_inputs(tmp_path)

    summary = build_completed_review_pack(
        root=tmp_path,
        supplier_id="entertainment_trading",
        run_id="fpm_entertainment_trading_test",
        observed_utc="2026-05-01T09:06:00Z",
    )

    manifest = pd.read_csv(summary["candidate_manifest_path"], dtype=str).fillna("")
    live_manifest_path = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "review_handoff_manifest.csv"
    operator_manifest_path = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "entertainment_trading"
        / "fpm_entertainment_trading_test"
        / "manifest.csv"
    )
    pass_df = pd.read_csv(manifest.iloc[0]["raw_pass_review_path"], dtype=str).fillna("")
    near_df = pd.read_csv(manifest.iloc[0]["raw_near_miss_review_path"], dtype=str).fillna("")
    assert summary["status"] == "built"
    assert list(manifest.columns) == REVIEW_CANDIDATE_MANIFEST_COLUMNS
    assert not live_manifest_path.exists()
    assert not operator_manifest_path.exists()
    assert manifest.iloc[0]["supplier_id"] == "entertainment_trading"
    assert manifest.iloc[0]["run_id"] == "fpm_entertainment_trading_test"
    assert manifest.iloc[0]["operator_ready_flag"] == "0"
    candidate_ids = set(pass_df["candidate_id"].tolist()) | set(near_df["candidate_id"].tolist())
    assert candidate_ids == {"candidate-pass"}
    assert "candidate-old" not in candidate_ids


def test_completed_review_pack_is_idempotent_for_existing_manifest(tmp_path: Path) -> None:
    _seed_run_state(tmp_path, completed=True)
    _seed_review_pack_inputs(tmp_path)

    first = build_completed_review_pack(
        root=tmp_path,
        supplier_id="entertainment_trading",
        run_id="fpm_entertainment_trading_test",
        observed_utc="2026-05-01T09:06:00Z",
    )
    second = build_completed_review_pack(
        root=tmp_path,
        supplier_id="entertainment_trading",
        run_id="fpm_entertainment_trading_test",
        observed_utc="2026-05-01T09:07:00Z",
    )

    assert first["status"] == "built"
    assert second["status"] == "already_built"
    assert second["candidate_manifest_path"] == first["candidate_manifest_path"]
