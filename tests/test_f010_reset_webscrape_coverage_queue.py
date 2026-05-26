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

from scripts.flows.F._schemas import get_f_output_contract
from scripts.one_off.F010_reset_webscrape_coverage_queue import reset_webscrape_coverage_queue


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


def _seed_supplier_config(root: Path) -> None:
    config_dir = root / "config" / "feeder" / "suppliers"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "stocklist_supplier.json").write_text(
        json.dumps(
            {
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "source_url": "local://stocklist.xlsx",
            }
        ),
        encoding="utf-8",
    )


def _seed_canonical(root: Path) -> None:
    supplier_dir = root / "out" / "systems" / "F" / "inbox" / "suppliers" / "stocklist_supplier"
    supplier_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "supplier_sku": "SKU-100",
                "supplier_title": "Item 100",
                "barcode": "111",
                "unit_cost": "10.00",
                "currency": "GBP",
                "vat_rate": "20",
                "source_url": "local://stocklist.xlsx",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-04-14T10:00:00Z",
                "row_hash": "hash-100",
                "is_valid_source_row": "1",
                "normalized_utc": "2026-04-14T10:00:00Z",
            },
            {
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "supplier_sku": "SKU-200",
                "supplier_title": "Item 200",
                "barcode": "222",
                "unit_cost": "11.00",
                "currency": "GBP",
                "vat_rate": "20",
                "source_url": "local://stocklist.xlsx",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-04-14T10:00:00Z",
                "row_hash": "hash-200",
                "is_valid_source_row": "1",
                "normalized_utc": "2026-04-14T10:00:00Z",
            },
            {
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "supplier_sku": "SKU-300",
                "supplier_title": "Item 300",
                "barcode": "333",
                "unit_cost": "12.00",
                "currency": "GBP",
                "vat_rate": "20",
                "source_url": "local://stocklist.xlsx",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-04-14T10:00:00Z",
                "row_hash": "hash-300",
                "is_valid_source_row": "1",
                "normalized_utc": "2026-04-14T10:00:00Z",
            },
            {
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "supplier_sku": "SKU-400",
                "supplier_title": "Item 400",
                "barcode": "444",
                "unit_cost": "13.00",
                "currency": "GBP",
                "vat_rate": "20",
                "source_url": "local://stocklist.xlsx",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-04-14T10:00:00Z",
                "row_hash": "hash-400",
                "is_valid_source_row": "1",
                "normalized_utc": "2026-04-14T10:00:00Z",
            },
        ]
    ).to_csv(supplier_dir / "canonical_current.csv", index=False)


def _seed_shared_inputs(root: Path) -> None:
    _write_contract(
        root,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "stocklist_supplier_old",
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "row_key": "hash-100",
                "supplier_sku": "SKU-100",
                "barcode": "111",
                "supplier_title": "Item 100",
                "unit_cost": "10.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-14T10:00:00Z",
            }
        ],
    )
    _write_contract(
        root,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "run_id": "stocklist_supplier_old",
                "run_status": "running",
                "source_url": "local://stocklist.xlsx",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-04-14T10:00:00Z",
                "normalized_utc": "2026-04-14T10:00:00Z",
                "total_rows": "4",
                "pending_rows": "4",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-04-14T10:00:00Z",
                "completed_at_utc": "",
            }
        ],
    )
    _write_contract(
        root,
        "feeder_legacy_scrape_evidence_live",
        [
            {
                "observed_utc": "2026-04-14T11:00:00Z",
                "candidate_id": "hash-100",
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "supplier_sku": "SKU-100",
                "barcode": "111",
                "asin": "B00AAA100",
                "scrape_attempted": "True",
            },
            {
                "observed_utc": "2026-04-14T11:01:00Z",
                "candidate_id": "hash-200",
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "supplier_sku": "SKU-200",
                "barcode": "222",
                "asin": "B00AAA200",
                "scrape_attempted": "True",
            },
            {
                "observed_utc": "2026-04-14T11:02:00Z",
                "candidate_id": "hash-999",
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "supplier_sku": "SKU-999",
                "barcode": "999",
                "asin": "B00AAA999",
                "scrape_attempted": "True",
            },
        ],
    )
    _write_contract(
        root,
        "f_screening_row_state_live",
        [
            {
                "observed_utc": "2026-04-14T12:00:00Z",
                "run_id": "stocklist_supplier_old",
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "supplier_sku": "SKU-100",
                "barcode": "111",
                "candidate_id": "hash-100",
                "asin": "B00AAA100",
                "row_status": "pass",
                "last_stage": "webscrape",
                "fail_code": "",
                "attempt_count": "1",
                "timeout_until_utc": "",
                "mode": "screening",
                "updated_at_utc": "2026-04-14T12:00:00Z",
                "source_seen_at_utc": "2026-04-14T10:00:00Z",
                "pf": "PASS",
                "status_reason": "PASS",
                "recommendation_status": "",
                "recommended_test_qty": "",
            },
            {
                "observed_utc": "2026-04-14T12:01:00Z",
                "run_id": "stocklist_supplier_old",
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "supplier_sku": "SKU-200",
                "barcode": "222",
                "candidate_id": "hash-200",
                "asin": "B00AAA200",
                "row_status": "timeout",
                "last_stage": "webscrape",
                "fail_code": "LOWROI",
                "attempt_count": "1",
                "timeout_until_utc": "",
                "mode": "screening",
                "updated_at_utc": "2026-04-14T12:01:00Z",
                "source_seen_at_utc": "2026-04-14T10:00:00Z",
                "pf": "FAIL",
                "status_reason": "LOWROI",
                "recommendation_status": "",
                "recommended_test_qty": "",
            },
            {
                "observed_utc": "2026-04-14T12:02:00Z",
                "run_id": "stocklist_supplier_old",
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "supplier_sku": "SKU-300",
                "barcode": "333",
                "candidate_id": "hash-300",
                "asin": "",
                "row_status": "timeout",
                "last_stage": "catalog",
                "fail_code": "NOASIN",
                "attempt_count": "1",
                "timeout_until_utc": "",
                "mode": "screening",
                "updated_at_utc": "2026-04-14T12:02:00Z",
                "source_seen_at_utc": "2026-04-14T10:00:00Z",
                "pf": "FAIL",
                "status_reason": "NOASIN",
                "recommendation_status": "",
                "recommended_test_qty": "",
            },
            {
                "observed_utc": "2026-04-14T12:03:00Z",
                "run_id": "stocklist_supplier_old",
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "supplier_sku": "SKU-400",
                "barcode": "444",
                "candidate_id": "hash-400",
                "asin": "",
                "row_status": "pending",
                "last_stage": "start",
                "fail_code": "",
                "attempt_count": "0",
                "timeout_until_utc": "",
                "mode": "screening",
                "updated_at_utc": "2026-04-14T12:03:00Z",
                "source_seen_at_utc": "2026-04-14T10:00:00Z",
                "pf": "",
                "status_reason": "",
                "recommendation_status": "",
                "recommended_test_qty": "",
            },
        ],
    )
    _write_contract(
        root,
        "feeder_backtest_input_view_live",
        [
            {
                "observed_utc": "2026-04-14T11:41:34Z",
                "policy_id": "f_backtest_policy_v1",
                "seller_sku": "SKU-100",
                "asin": "B00AAA100",
                "supplier_code": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "mapping_status": "legacy_asin_match",
                "input_status": "ready",
                "input_reason_codes": "",
                "history_days": "365",
                "paired_buy_box_bsr_days": "365",
                "paired_fba_bsr_days": "365",
                "buy_box_coverage_share": "1",
                "amazon_presence_share_30d": "0",
                "amazon_presence_share_90d": "0",
                "price_median_30d_gbp": "25",
                "price_median_90d_gbp": "25",
                "price_median_180d_gbp": "25",
                "price_median_365d_gbp": "25",
                "bsr_median_30d": "1000",
                "bsr_median_90d": "1000",
                "demand_basis_source": "bbp_last_completed_month",
                "demand_basis_units_monthly": "4",
                "demand_basis_month_label": "2026-03",
                "bbp_sales_last_completed_month_label": "2026-03",
                "bbp_sales_last_completed_month_units": "4",
                "bbp_sales_current_month_label": "",
                "bbp_sales_current_month_units": "",
                "bbp_sales_future_month_count_ignored": "2",
                "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
                "bbp_sales_replay_demand_basis_label": "2026-03",
                "bbp_sales_replay_demand_basis_units": "4",
                "base_velocity_30d_units_per_day": "0.1",
                "current_supplier_buy_cost_gbp": "10",
                "break_even_price_gbp": "20",
                "market_price_gbp": "25",
                "seasonality_state": "full_year_history",
                "history_confidence": "medium",
                "manual_review_flag": "0",
            }
        ],
    )


def test_f010_dry_run_reports_priority_and_exclusions_without_modifying(tmp_path: Path) -> None:
    _seed_supplier_config(tmp_path)
    _seed_canonical(tmp_path)
    _seed_shared_inputs(tmp_path)

    output_dir = tmp_path / "out" / "analysis_reports"
    result = reset_webscrape_coverage_queue(
        root=tmp_path,
        supplier_id="stocklist_supplier",
        apply_changes=False,
        output_dir=output_dir,
    )

    assert result.summary["applied"] is False
    assert result.summary["priority_rows_selected"] == 2
    assert result.summary["processed_rows_excluded_from_remainder"] == 1
    assert result.summary["queue_rows_final"] == 3
    assert result.summary["queue_order"] == "priority-first"
    assert result.report_path.exists()
    assert result.latest_path.exists()

    active_df = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path, dtype=str).fillna("")
    assert len(active_df) == 1
    assert active_df.iloc[0]["row_key"] == "hash-100"

    report_df = result.report_df.copy()
    assert set(report_df["group"].tolist()) == {"priority_scrape", "processed_screening"}
    assert "selected" in set(report_df["selection_status"].tolist())
    assert "excluded_known_processed" in set(report_df["selection_status"].tolist())


def test_f010_apply_archives_clears_stale_outputs_and_rebuilds_queue(tmp_path: Path) -> None:
    _seed_supplier_config(tmp_path)
    _seed_canonical(tmp_path)
    _seed_shared_inputs(tmp_path)

    output_dir = tmp_path / "out" / "analysis_reports"
    result = reset_webscrape_coverage_queue(
        root=tmp_path,
        supplier_id="stocklist_supplier",
        apply_changes=True,
        output_dir=output_dir,
    )

    assert result.summary["applied"] is True
    assert result.summary["priority_rows_selected"] == 2
    assert result.summary["processed_rows_excluded_from_remainder"] == 1
    assert result.summary["queue_rows_final"] == 3
    assert result.summary["queue_order"] == "priority-first"
    assert Path(str(result.summary["archive_dir"])).exists()

    active_df = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path, dtype=str).fillna("")
    supplier_rows = active_df[active_df["supplier_id"] == "stocklist_supplier"].copy()
    assert supplier_rows["row_key"].tolist()[2] == "hash-400"
    assert set(supplier_rows["row_key"].tolist()[:2]) == {"hash-100", "hash-200"}
    assert set(supplier_rows["scan_status"].tolist()) == {"pending"}

    run_state_df = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_run_state").rel_path, dtype=str).fillna("")
    run_state = run_state_df[run_state_df["supplier_id"] == "stocklist_supplier"].iloc[0]
    assert run_state["pending_rows"] == "3"
    assert run_state["run_id"].startswith("stocklist_supplier_webscrape_reset_")

    screening_df = pd.read_csv(tmp_path / get_f_output_contract("f_screening_row_state_live").rel_path, dtype=str).fillna("")
    supplier_screening = screening_df[screening_df["supplier_id"] == "stocklist_supplier"].copy()
    assert sorted(supplier_screening["candidate_id"].tolist()) == ["hash-100", "hash-200", "hash-300", "hash-400"]
    assert supplier_screening[supplier_screening["candidate_id"] == "hash-300"].iloc[0]["row_status"] == "timeout"
    for row_key in ["hash-100", "hash-200", "hash-400"]:
        assert supplier_screening[supplier_screening["candidate_id"] == row_key].iloc[0]["row_status"] == "pending"

    scrape_df = pd.read_csv(tmp_path / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path, dtype=str).fillna("")
    assert scrape_df.empty

    backtest_input_df = pd.read_csv(tmp_path / get_f_output_contract("feeder_backtest_input_view_live").rel_path, dtype=str).fillna("")
    assert backtest_input_df.empty

    archived_rel_paths = {str(path).replace("\\", "/") for path in result.summary["archived_paths"]}
    assert "out/systems/F/live/feeder_legacy_scrape_evidence_live.csv" in archived_rel_paths
    assert "out/systems/F/inbox/supplier_price_list_active_run.csv" in archived_rel_paths


def test_f010_remaining_first_queue_order_scans_unprocessed_rows_before_rescrape(tmp_path: Path) -> None:
    _seed_supplier_config(tmp_path)
    _seed_canonical(tmp_path)
    _seed_shared_inputs(tmp_path)

    output_dir = tmp_path / "out" / "analysis_reports"
    result = reset_webscrape_coverage_queue(
        root=tmp_path,
        supplier_id="stocklist_supplier",
        apply_changes=True,
        output_dir=output_dir,
        queue_order="remaining-first",
    )

    assert result.summary["applied"] is True
    assert result.summary["queue_order"] == "remaining-first"
    assert result.summary["queue_rows_priority"] == 2
    assert result.summary["queue_rows_remaining"] == 1

    active_df = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path, dtype=str).fillna("")
    supplier_rows = active_df[active_df["supplier_id"] == "stocklist_supplier"].copy()
    assert supplier_rows["row_key"].tolist()[0] == "hash-400"
    assert set(supplier_rows["row_key"].tolist()[1:]) == {"hash-100", "hash-200"}

    queue_state_df = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_queue_state").rel_path, dtype=str).fillna("")
    assert queue_state_df.iloc[0]["notes"] == "webscrape_coverage_reset_remaining_first"
