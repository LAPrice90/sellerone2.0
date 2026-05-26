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

from scripts.flows.F._schemas import get_f_output_contract
from scripts.one_off.F007_prepare_targeted_rescrape_subset import prepare_targeted_rescrape_subset


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
        ]
    ).to_csv(supplier_dir / "canonical_current.csv", index=False)


def test_f007_auto_uses_canonical_when_active_queue_has_no_match_and_applies_subset(tmp_path: Path) -> None:
    _seed_supplier_config(tmp_path)
    _seed_canonical(tmp_path)
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "stocklist_supplier_old",
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "row_key": "active-only-hash",
                "supplier_sku": "ACTIVE-ONLY",
                "barcode": "999",
                "supplier_title": "Active Only",
                "unit_cost": "9.00",
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
        tmp_path,
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
                "bbp_sales_last_completed_month_label": "",
                "bbp_sales_replay_demand_basis_source": "",
                "break_even": "20",
                "monthly_sold": "1",
                "bbp_monthly_units_chosen": "1",
            },
            {
                "observed_utc": "2026-04-14T11:01:00Z",
                "candidate_id": "hash-200",
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "supplier_sku": "SKU-200",
                "barcode": "222",
                "asin": "B00AAA200",
                "bbp_sales_last_completed_month_label": "",
                "bbp_sales_replay_demand_basis_source": "",
                "break_even": "20",
                "monthly_sold": "1",
                "bbp_monthly_units_chosen": "1",
            },
            {
                "observed_utc": "2026-04-14T11:02:00Z",
                "candidate_id": "hash-300",
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "supplier_sku": "SKU-300",
                "barcode": "333",
                "asin": "B00AAA300",
                "bbp_sales_last_completed_month_label": "2026-03",
                "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
                "break_even": "20",
                "monthly_sold": "1",
                "bbp_monthly_units_chosen": "1",
            },
        ],
    )

    output_dir = tmp_path / "out" / "analysis_reports"
    result = prepare_targeted_rescrape_subset(
        root=tmp_path,
        supplier_id="stocklist_supplier",
        queue_source="auto",
        apply_changes=True,
        output_dir=output_dir,
    )

    assert result.summary["queue_source_used"] == "canonical_current"
    assert result.summary["subset_rows_selected"] == 2
    assert result.summary["applied"] is True
    assert result.summary["matchable_rows_active_run"] == 0
    assert result.summary["matchable_rows_canonical_current"] == 2
    assert Path(str(result.summary["backup_dir"])).exists()
    assert result.report_path.exists()
    assert result.latest_path.exists()

    active_df = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path, dtype=str).fillna("")
    supplier_rows = active_df[active_df["supplier_id"] == "stocklist_supplier"].copy()
    assert len(supplier_rows) == 2
    assert set(supplier_rows["row_key"].tolist()) == {"hash-100", "hash-200"}
    assert set(supplier_rows["scan_status"].tolist()) == {"pending"}

    run_state_df = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_run_state").rel_path, dtype=str).fillna("")
    run_state = run_state_df[run_state_df["supplier_id"] == "stocklist_supplier"].iloc[0]
    assert run_state["pending_rows"] == "2"
    assert run_state["run_id"].startswith("stocklist_supplier_rescrape_subset_")

    supplier_active = pd.read_csv(
        tmp_path / "out" / "systems" / "F" / "inbox" / "suppliers" / "stocklist_supplier" / "active_run.csv",
        dtype=str,
    ).fillna("")
    assert len(supplier_active) == 2

    selected_rows = result.report_df[result.report_df["selection_status"] == "selected"].copy()
    assert len(selected_rows) == 2
    assert set(selected_rows["candidate_id"].tolist()) == {"hash-100", "hash-200"}


def test_f007_dry_run_does_not_modify_active_queue(tmp_path: Path) -> None:
    _seed_supplier_config(tmp_path)
    _seed_canonical(tmp_path)
    _write_contract(
        tmp_path,
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
        tmp_path,
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
                "bbp_sales_last_completed_month_label": "",
                "bbp_sales_replay_demand_basis_source": "",
                "break_even": "20",
                "monthly_sold": "1",
                "bbp_monthly_units_chosen": "1",
            }
        ],
    )

    output_dir = tmp_path / "out" / "analysis_reports"
    result = prepare_targeted_rescrape_subset(
        root=tmp_path,
        supplier_id="stocklist_supplier",
        queue_source="active_run",
        apply_changes=False,
        output_dir=output_dir,
    )

    assert result.summary["subset_rows_selected"] == 1
    assert result.summary["applied"] is False
    assert result.summary["backup_dir"] == ""

    active_df = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path, dtype=str).fillna("")
    assert len(active_df) == 1
    assert active_df.iloc[0]["row_key"] == "hash-100"


def test_f007_selects_rows_with_missing_core_price_history_or_technical_scrape_failures(tmp_path: Path) -> None:
    _seed_supplier_config(tmp_path)
    _seed_canonical(tmp_path)
    _write_contract(
        tmp_path,
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
            },
            {
                "run_id": "stocklist_supplier_old",
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "row_key": "hash-200",
                "supplier_sku": "SKU-200",
                "barcode": "222",
                "supplier_title": "Item 200",
                "unit_cost": "11.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-14T10:00:00Z",
            },
        ],
    )
    _write_contract(
        tmp_path,
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
                "scrape_success": "True",
                "price_history_points_365d": "0",
                "chart_price_daily_series": "",
                "chart_raw_amazon_daily_series": "",
                "chart_raw_fba_daily_series": "",
                "chart_raw_fbm_daily_series": "",
                "chart_raw_buy_box_daily_series": "",
                "bbp_sales_last_completed_month_label": "2026-03",
                "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
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
                "scrape_success": "False",
                "scrape_error": "INCOMPLETE_PRICE_HISTORY_CAPTURE",
                "price_history_points_365d": "0",
                "chart_price_daily_series": "",
                "chart_raw_amazon_daily_series": "",
                "chart_raw_fba_daily_series": "",
                "chart_raw_fbm_daily_series": "",
                "chart_raw_buy_box_daily_series": "",
                "bbp_sales_last_completed_month_label": "2026-03",
                "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
            },
        ],
    )

    output_dir = tmp_path / "out" / "analysis_reports"
    result = prepare_targeted_rescrape_subset(
        root=tmp_path,
        supplier_id="stocklist_supplier",
        queue_source="active_run",
        apply_changes=False,
        output_dir=output_dir,
    )

    assert result.summary["subset_rows_selected"] == 2
    assert result.summary["targeted_rows_with_asin"] == 2
    assert result.summary["rescrape_reason_counts"]["missing_core_price_history"] == 2
    assert result.summary["rescrape_reason_counts"]["scrape_not_successful"] == 1

    selected_rows = result.report_df[result.report_df["selection_status"] == "selected"].copy()
    assert len(selected_rows) == 2
    reasons = dict(zip(selected_rows["candidate_id"], selected_rows["rescrape_reason"]))
    assert reasons["hash-100"] == "missing_core_price_history"
    assert reasons["hash-200"] == "missing_core_price_history|scrape_not_successful"


def test_f007_can_include_alignment_missing_expected_baseline_asins(tmp_path: Path) -> None:
    _seed_supplier_config(tmp_path)
    _seed_canonical(tmp_path)
    _write_contract(
        tmp_path,
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
            },
            {
                "run_id": "stocklist_supplier_old",
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "row_key": "hash-200",
                "supplier_sku": "SKU-200",
                "barcode": "222",
                "supplier_title": "Item 200",
                "unit_cost": "11.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-14T10:00:00Z",
            },
        ],
    )
    _write_contract(
        tmp_path,
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
                "scrape_success": "True",
                "price_history_points_365d": "12",
                "chart_price_daily_series": "x",
                "bbp_sales_last_completed_month_label": "2026-03",
                "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
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
                "scrape_success": "True",
                "price_history_points_365d": "8",
                "chart_price_daily_series": "y",
                "bbp_sales_last_completed_month_label": "2026-03",
                "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
            },
        ],
    )
    alignment_path = tmp_path / "out" / "analysis_reports" / "hf_learning_alignment_30d_latest.csv"
    alignment_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"sku": "SKU-100", "asin": "B00AAA100", "expected_units_source": "sales_validation_asin"},
            {"sku": "SKU-200", "asin": "B00AAA200", "expected_units_source": "no_source"},
        ]
    ).to_csv(alignment_path, index=False)

    output_dir = tmp_path / "out" / "analysis_reports"
    result = prepare_targeted_rescrape_subset(
        root=tmp_path,
        supplier_id="stocklist_supplier",
        queue_source="active_run",
        apply_changes=False,
        include_alignment_missing=True,
        alignment_missing_path=alignment_path,
        output_dir=output_dir,
    )

    assert result.summary["subset_rows_selected"] == 1
    assert result.summary["targeted_rows_with_asin"] == 1
    assert result.summary["include_alignment_missing"] is True
    assert result.summary["alignment_missing_rows_source"] == 1
    assert result.summary["alignment_missing_asins_source"] == 1
    assert result.summary["rescrape_reason_counts"]["alignment_missing_expected_baseline"] == 1

    selected_rows = result.report_df[result.report_df["selection_status"] == "selected"].copy()
    assert len(selected_rows) == 1
    assert selected_rows.iloc[0]["candidate_id"] == "hash-200"
    assert selected_rows.iloc[0]["rescrape_reason"] == "alignment_missing_expected_baseline"
