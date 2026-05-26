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

from scripts.one_off.F009_build_full_capture_consistency_audit import build_full_capture_consistency_audit


def _write_raw(path: Path, *, pass_index: int, current_units: int, chart_source: str) -> None:
    payload = {
        "run_metadata": {
            "pass_index": pass_index,
            "capture_status": "success",
            "capture_error": "",
        },
        "scraped_data": {
            "bbp_sales_chart_source": chart_source,
            "bbp_sales_chart_series": "01/26=8;02/26=9;03/26=10;04/26=11;05/26*=12[pred]",
            "bbp_sales_chart_month_labels": "01/26|02/26|03/26|04/26|05/26*",
            "bbp_sales_chart_month_units": "8|9|10|11|12",
            "bbp_sales_last_completed_month_label": "2026-03",
            "bbp_sales_last_completed_month_units": "10",
            "bbp_sales_current_month_label": "2026-04",
            "bbp_sales_current_month_units": str(current_units),
            "bbp_sales_future_month_count_ignored": "1",
            "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
            "bbp_sales_replay_demand_basis_units": "10",
            "monthly_sold": "10+ bought in past month",
            "estimated_monthly_profit": "21.50",
            "bbp_auto_sell_price": "28.00",
            "bbp_final_sell_price": "28.50",
        },
        "bbp_section_snapshot_json": {"node_count": 321},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_f009_builds_monthly_points_and_discrepancy_rows(tmp_path: Path) -> None:
    raw1 = tmp_path / "raw_pass1.json"
    raw2 = tmp_path / "raw_pass2.json"
    raw3 = tmp_path / "raw_pass3.json"
    _write_raw(raw1, pass_index=1, current_units=11, chart_source="estSalesMonthlyChart:chartjs")
    _write_raw(raw2, pass_index=2, current_units=13, chart_source="estSalesMonthlyChart:chartjs")
    _write_raw(raw3, pass_index=3, current_units=13, chart_source="")

    manifest_path = tmp_path / "manifest.csv"
    pd.DataFrame(
        [
            {
                "observed_utc": "2026-04-14T18:00:00Z",
                "run_id": "run_1",
                "asin": "B000TEST01",
                "supplier_sku": "SKU-1",
                "validation_case": "trusted_completed_month",
                "sample_rank": "1",
                "pass_index": "1",
                "capture_status": "success",
                "capture_error": "",
                "bbp_snapshot_loaded": "1",
                "raw_json_path": str(raw1),
            },
            {
                "observed_utc": "2026-04-14T18:00:00Z",
                "run_id": "run_2",
                "asin": "B000TEST01",
                "supplier_sku": "SKU-1",
                "validation_case": "trusted_completed_month",
                "sample_rank": "1",
                "pass_index": "2",
                "capture_status": "success",
                "capture_error": "",
                "bbp_snapshot_loaded": "1",
                "raw_json_path": str(raw2),
            },
            {
                "observed_utc": "2026-04-14T18:00:00Z",
                "run_id": "run_3",
                "asin": "B000TEST01",
                "supplier_sku": "SKU-1",
                "validation_case": "trusted_completed_month",
                "sample_rank": "1",
                "pass_index": "3",
                "capture_status": "success",
                "capture_error": "",
                "bbp_snapshot_loaded": "1",
                "raw_json_path": str(raw3),
            },
        ]
    ).to_csv(manifest_path, index=False)

    result = build_full_capture_consistency_audit(
        manifest_path=manifest_path,
        output_dir=tmp_path / "out",
        observed_utc="2026-04-14T18:05:00Z",
    )

    assert result.facts_path.exists()
    assert result.monthly_points_path.exists()
    assert result.discrepancies_path.exists()
    assert len(result.facts_df) == 3
    assert len(result.monthly_points_df) == 15

    predicted_rows = result.monthly_points_df[result.monthly_points_df["point_class"] == "future_predicted"]
    assert not predicted_rows.empty
    assert (predicted_rows["month_label"] == "05/26*").any()

    last_completed_rows = result.monthly_points_df[result.monthly_points_df["point_class"] == "last_completed"]
    assert not last_completed_rows.empty
    assert (last_completed_rows["trusted_for_demand_basis"] == "1").all()

    drift_rows = result.discrepancies_df[
        (result.discrepancies_df["field_name"] == "bbp_sales_current_month_units")
        & (result.discrepancies_df["allowed_drift_flag"] == "1")
    ]
    assert not drift_rows.empty
    assert (drift_rows["discrepancy_class"] == "current_month_drift").all()

    chart_rows = result.discrepancies_df[
        (result.discrepancies_df["field_name"] == "bbp_sales_chart_source")
        & (result.discrepancies_df["compare_run_id"] == "run_3")
    ]
    assert not chart_rows.empty
    assert chart_rows.iloc[0]["discrepancy_class"] == "chart_not_loaded"
