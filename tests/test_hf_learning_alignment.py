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

from scripts.one_off import HF002_build_learning_alignment as hf002


def _write_csv(path: Path, rows: list[dict[str, str]], *, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def test_build_alignment_outputs_and_rescrape_trigger(tmp_path: Path, monkeypatch) -> None:
    paths = {
        "MARKET_FACTS_PATH": tmp_path / "out" / "analysis_reports" / "hf_learning_market_facts_latest.csv",
        "ACTION_OUTCOMES_PATH": tmp_path / "out" / "analysis_reports" / "hf_learning_action_outcomes_latest.csv",
        "SCRAPE_GAP_PATH": tmp_path / "out" / "analysis_reports" / "hf_learning_scrape_gap_report_latest.csv",
        "SKU_PERFORMANCE_PATH": tmp_path / "out" / "sku_performance_summary.csv",
        "IDENTITY_PATH": tmp_path / "out" / "analysis_reports" / "hf_learning_identity_bridge_latest.csv",
        "ASSUMPTION_PATH": tmp_path / "out" / "analysis_reports" / "hf_learning_assumption_snapshots_latest.csv",
        "F_SALES_VALIDATION_PATH": tmp_path / "out" / "analysis_reports" / "f_sales_history_validation_latest.csv",
        "F_CALIBRATION_PATH": tmp_path / "out" / "analysis_reports" / "f_backtest_calibration_set_latest.csv",
        "F_FULL_CAPTURE_FACTS_PATH": tmp_path / "out" / "analysis_reports" / "f_full_capture_normalized_facts_latest.csv",
    }

    _write_csv(
        paths["MARKET_FACTS_PATH"],
        [
            {
                "observation_utc": "2026-04-17T10:00:00Z",
                "asof_date": "2026-04-17",
                "sku": "SKU1",
                "asin": "A1",
                "our_price_gbp": "10.5",
                "buy_box_price_gbp": "10.0",
                "lowest_fba_price_gbp": "9.8",
                "lowest_fbm_price_gbp": "10.2",
                "offer_count_fba": "3",
                "offer_count_fbm": "2",
                "amazon_present_flag": "0",
                "seller_entry_count_today": "1",
                "seller_exit_count_today": "0",
                "delivery_parity_flag": "1",
                "break_even_gross_gbp": "9.9",
                "bsr": "1000",
            },
            {
                "observation_utc": "2026-04-17T10:00:00Z",
                "asof_date": "2026-04-17",
                "sku": "SKU2",
                "asin": "A2",
                "our_price_gbp": "11.0",
                "buy_box_price_gbp": "10.8",
                "lowest_fba_price_gbp": "10.5",
                "lowest_fbm_price_gbp": "10.9",
                "offer_count_fba": "4",
                "offer_count_fbm": "1",
                "amazon_present_flag": "1",
                "seller_entry_count_today": "0",
                "seller_exit_count_today": "0",
                "delivery_parity_flag": "0",
                "break_even_gross_gbp": "10.1",
                "bsr": "2000",
            },
            {
                "observation_utc": "2026-04-17T10:00:00Z",
                "asof_date": "2026-04-17",
                "sku": "SKU3",
                "asin": "A3",
                "our_price_gbp": "9.5",
                "buy_box_price_gbp": "9.2",
                "lowest_fba_price_gbp": "9.1",
                "lowest_fbm_price_gbp": "9.3",
                "offer_count_fba": "2",
                "offer_count_fbm": "1",
                "amazon_present_flag": "0",
                "seller_entry_count_today": "0",
                "seller_exit_count_today": "0",
                "delivery_parity_flag": "1",
                "break_even_gross_gbp": "8.8",
                "bsr": "1500",
            },
        ],
        columns=[
            "observation_utc",
            "asof_date",
            "sku",
            "asin",
            "our_price_gbp",
            "buy_box_price_gbp",
            "lowest_fba_price_gbp",
            "lowest_fbm_price_gbp",
            "offer_count_fba",
            "offer_count_fbm",
            "amazon_present_flag",
            "seller_entry_count_today",
            "seller_exit_count_today",
            "delivery_parity_flag",
            "break_even_gross_gbp",
            "bsr",
        ],
    )

    _write_csv(
        paths["ACTION_OUTCOMES_PATH"],
        [
            {"event_ts_utc": "2026-04-17T10:05:00Z", "run_id": "RUN-1", "sku": "SKU1", "asin": "A1", "seller_count": "2"},
            {"event_ts_utc": "2026-04-17T10:06:00Z", "run_id": "RUN-1", "sku": "SKU2", "asin": "A2", "seller_count": "5"},
            {"event_ts_utc": "2026-04-17T10:07:00Z", "run_id": "RUN-1", "sku": "SKU3", "asin": "A3", "seller_count": "2"},
        ],
        columns=["event_ts_utc", "run_id", "sku", "asin", "seller_count"],
    )

    gap_rows = [
        {
            "observed_utc": "2026-04-17T10:00:00Z",
            "candidate_id": "C1",
            "supplier_id": "SUP-1",
            "supplier_sku": "SS1",
            "sku": "SKU1",
            "asin": "A1",
            "scrape_coverage_status": "ok",
            "rescrape_needed_flag": "0",
            "rescrape_reason_codes": "COVERAGE_OK",
            "queue_owner_path": "scripts/one_off/F007_prepare_targeted_rescrape_subset.py|scripts/flows/F/F061_run_legacy_first_checks_local.py",
        },
        {
            "observed_utc": "2026-04-17T10:00:00Z",
            "candidate_id": "C2",
            "supplier_id": "SUP-2",
            "supplier_sku": "SS2",
            "sku": "SKU2",
            "asin": "A2",
            "scrape_coverage_status": "thin",
            "rescrape_needed_flag": "1",
            "rescrape_reason_codes": "THIN_CHART_POINTS",
            "queue_owner_path": "scripts/one_off/F007_prepare_targeted_rescrape_subset.py|scripts/flows/F/F061_run_legacy_first_checks_local.py",
        },
    ]
    for idx in range(9):
        gap_rows.append(
            {
                "observed_utc": "2026-04-17T10:00:00Z",
                "candidate_id": f"CM-{idx}",
                "supplier_id": "SUP-M",
                "supplier_sku": f"SM-{idx}",
                "sku": "",
                "asin": "",
                "scrape_coverage_status": "missing",
                "rescrape_needed_flag": "1",
                "rescrape_reason_codes": "MISSING_ASIN",
                "queue_owner_path": "scripts/one_off/F007_prepare_targeted_rescrape_subset.py|scripts/flows/F/F061_run_legacy_first_checks_local.py",
            }
        )
    _write_csv(
        paths["SCRAPE_GAP_PATH"],
        gap_rows,
        columns=[
            "observed_utc",
            "candidate_id",
            "supplier_id",
            "supplier_sku",
            "sku",
            "asin",
            "scrape_coverage_status",
            "rescrape_needed_flag",
            "rescrape_reason_codes",
            "queue_owner_path",
        ],
    )

    _write_csv(
        paths["SKU_PERFORMANCE_PATH"],
        [
            {"sku": "SKU1", "window_days": "30", "units_sold": "7", "profit_exvat_gbp": "14"},
            {"sku": "SKU2", "window_days": "30", "units_sold": "9", "profit_exvat_gbp": "15"},
            {"sku": "SKU3", "window_days": "30", "units_sold": "4", "profit_exvat_gbp": "7"},
        ],
        columns=["sku", "window_days", "units_sold", "profit_exvat_gbp"],
    )

    _write_csv(
        paths["IDENTITY_PATH"],
        [{"snapshot_utc": "2026-04-17T10:00:00Z", "candidate_id": "C1", "supplier_sku": "SS1", "sku": "SKU1", "asin": "A1"}],
        columns=["snapshot_utc", "candidate_id", "supplier_sku", "sku", "asin"],
    )
    _write_csv(
        paths["ASSUMPTION_PATH"],
        [{"candidate_id": "C1", "estimated_demand": "10", "estimated_margin_gbp": "2.0"}],
        columns=["candidate_id", "estimated_demand", "estimated_margin_gbp"],
    )

    _write_csv(
        paths["F_SALES_VALIDATION_PATH"],
        [
            {"asin": "A2", "month_units": "5", "trusted_for_demand_basis": "1"},
        ],
        columns=["asin", "month_units", "trusted_for_demand_basis"],
    )
    _write_csv(
        paths["F_CALIBRATION_PATH"],
        [{"asin": "A2", "estimated_monthly_profit_gbp": "12"}],
        columns=["asin", "estimated_monthly_profit_gbp"],
    )
    _write_csv(
        paths["F_FULL_CAPTURE_FACTS_PATH"],
        [
            {
                "asin": "A3",
                "capture_status": "success",
                "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
                "bbp_sales_replay_demand_basis_units": "4",
                "estimated_monthly_profit": "7",
            }
        ],
        columns=[
            "asin",
            "capture_status",
            "bbp_sales_replay_demand_basis_source",
            "bbp_sales_replay_demand_basis_units",
            "estimated_monthly_profit",
        ],
    )

    for attr, path in paths.items():
        monkeypatch.setattr(hf002, attr, path)
    monkeypatch.setattr(hf002, "REQUIRED_INPUTS", list(paths.values()))
    monkeypatch.setattr(hf002, "_utc_now_iso", lambda: "2026-04-17T18:00:00Z")

    alignment_output = tmp_path / "out" / "analysis_reports" / "alignment.csv"
    factor_output = tmp_path / "out" / "analysis_reports" / "factor.csv"
    result = hf002.build_alignment(
        repo_root=tmp_path,
        alignment_output_path=alignment_output,
        factor_output_path=factor_output,
    )

    assert result.alignment_rows == 3
    assert result.factor_rows >= 1
    assert result.rescrape_trigger_flag is True
    assert "missing_rate_gt_80pct" in result.rescrape_trigger_reason

    alignment_df = pd.read_csv(alignment_output, dtype=str).fillna("")
    assert not alignment_df.astype(str).apply(lambda col: col.str.strip().str.lower().eq("nan")).any().any()
    alignment_df = alignment_df.set_index("sku")
    sku1 = alignment_df.loc["SKU1"]
    sku2 = alignment_df.loc["SKU2"]
    sku3 = alignment_df.loc["SKU3"]
    assert sku1["dominant_discrepancy_class"] == "underperform_vs_expected"
    assert sku2["dominant_discrepancy_class"] == "outperform_vs_expected"
    assert sku1["expected_units_source"] == "assumption_candidate_sku_asin"
    assert sku2["expected_units_source"] == "sales_validation_asin"
    assert sku1["expected_profit_source"] == "assumption_candidate_sku_asin"
    assert sku2["expected_profit_source"] == "calibration_asin"
    assert sku3["expected_units_source"] == "full_capture_asin"
    assert sku3["expected_profit_source"] == "full_capture_asin"
    assert sku2["rescrape_signal_flag"] == "1"
    assert sku2["rescrape_signal_reason"] == "asin_scrape_status:thin"

    factor_df = pd.read_csv(factor_output, dtype=str).fillna("")
    assert not factor_df.astype(str).apply(lambda col: col.str.strip().str.lower().eq("nan")).any().any()
    assert (factor_df["rescrape_trigger_flag"] == "1").any()
    assert (factor_df["recommended_collection_mode"] == "F061_MODE=data_collection").any()
