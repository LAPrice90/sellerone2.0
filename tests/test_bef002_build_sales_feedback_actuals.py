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

from scripts.one_off import BEF002_build_sales_feedback_actuals as bef002


def _write_csv(path: Path, rows: list[dict[str, str]], *, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def test_build_sales_feedback_actuals_writes_summary_and_baseline_rows(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "out"
    analysis_dir = out / "analysis_reports"

    monkeypatch.setattr(bef002, "FOUNDATION_PATH", analysis_dir / "bef_sales_truth_foundation_latest.csv")
    monkeypatch.setattr(bef002, "DAILY_TRUTH_PATH", out / "sku_daily_sales_truth_latest.csv")
    monkeypatch.setattr(bef002, "SUMMARY_PATH", out / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv")
    monkeypatch.setattr(bef002, "SEED_PATH", analysis_dir / "bef_operational_feedback_seed_latest.csv")
    monkeypatch.setattr(bef002, "ALIGNMENT_PATH", analysis_dir / "hf_learning_alignment_30d_latest.csv")
    monkeypatch.setattr(bef002, "IDENTITY_BRIDGE_PATH", analysis_dir / "hf_learning_identity_bridge_latest.csv")

    _write_csv(
        analysis_dir / "bef_sales_truth_foundation_latest.csv",
        [
            {"operational_sku": "SKU1", "operational_asin": "A1", "asin_bridge_status": "resolved"},
            {"operational_sku": "SKU2", "operational_asin": "A2", "asin_bridge_status": "resolved"},
            {"operational_sku": "SKU3", "operational_asin": "A3", "asin_bridge_status": "unresolved"},
        ],
        columns=["operational_sku", "operational_asin", "asin_bridge_status"],
    )
    _write_csv(
        out / "sku_daily_sales_truth_latest.csv",
        [
            {"sku": "SKU1", "date": "2026-04-20", "source_state": "finalized_ledger", "units": "2", "profit_gbp": "4.5"},
            {"sku": "SKU1", "date": "2026-04-19", "source_state": "provisional_order_master", "units": "1", "profit_gbp": "1.5"},
            {"sku": "SKU2", "date": "2026-04-18", "source_state": "finalized_ledger", "units": "3", "profit_gbp": "6.0"},
        ],
        columns=["sku", "date", "source_state", "units", "profit_gbp"],
    )
    _write_csv(
        out / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv",
        [
            {"observed_utc": "2026-04-20T10:00:00Z", "seller_sku": "SUP-1", "asin": "A1"},
            {"observed_utc": "2026-04-20T10:10:00Z", "seller_sku": "SUP-2", "asin": "AX"},
        ],
        columns=["observed_utc", "seller_sku", "asin"],
    )
    _write_csv(
        analysis_dir / "bef_operational_feedback_seed_latest.csv",
        [],
        columns=["observed_utc", "operational_asin", "operational_sku", "bridge_status", "seed_priority"],
    )
    _write_csv(
        analysis_dir / "hf_learning_alignment_30d_latest.csv",
        [],
        columns=["alignment_window_end_utc", "sku", "asin", "expected_units_30d", "expected_profit_30d_gbp"],
    )
    _write_csv(
        analysis_dir / "hf_learning_identity_bridge_latest.csv",
        [],
        columns=["snapshot_utc", "supplier_sku", "asin", "sku"],
    )

    result = bef002.build_sales_feedback_actuals(
        output_dir=analysis_dir,
        observed_utc="2026-04-20T15:50:00Z",
    )

    assert result.actuals_path.exists()
    out_df = pd.read_csv(result.actuals_path, dtype=str).fillna("")
    assert not out_df.empty

    summary_rows = out_df[out_df["actuals_basis"] == "summary_asin_map"].copy()
    baseline_rows = out_df[out_df["actuals_basis"] == "operational_baseline"].copy()

    assert len(summary_rows) == 1
    summary = summary_rows.iloc[0]
    assert summary["decision_snapshot_utc"] == "2026-04-20T10:00:00Z"
    assert summary["seller_sku"] == "SUP-1"
    assert summary["asin"] == "A1"
    assert summary["actual_units_30d"] == "3"
    assert summary["actual_profit_30d_gbp"] == "6"
    assert summary["actuals_source_state_30d"] == "finalized_plus_provisional"
    assert summary["purchased_flag"] == "auto_summary_asin_match"

    assert len(baseline_rows) == 2
    assert set(baseline_rows["asin"].tolist()) == {"A1", "A2"}
    assert all(v == "auto_operational_baseline" for v in baseline_rows["purchased_flag"].tolist())


def test_build_sales_feedback_actuals_handles_missing_inputs(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "out"
    analysis_dir = out / "analysis_reports"
    monkeypatch.setattr(bef002, "FOUNDATION_PATH", analysis_dir / "bef_sales_truth_foundation_latest.csv")
    monkeypatch.setattr(bef002, "DAILY_TRUTH_PATH", out / "sku_daily_sales_truth_latest.csv")
    monkeypatch.setattr(bef002, "SUMMARY_PATH", out / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv")
    monkeypatch.setattr(bef002, "SEED_PATH", analysis_dir / "bef_operational_feedback_seed_latest.csv")
    monkeypatch.setattr(bef002, "ALIGNMENT_PATH", analysis_dir / "hf_learning_alignment_30d_latest.csv")
    monkeypatch.setattr(bef002, "IDENTITY_BRIDGE_PATH", analysis_dir / "hf_learning_identity_bridge_latest.csv")

    _write_csv(analysis_dir / "bef_sales_truth_foundation_latest.csv", [], columns=["operational_sku"])
    _write_csv(out / "sku_daily_sales_truth_latest.csv", [], columns=["sku", "date", "source_state", "units", "profit_gbp"])
    _write_csv(out / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv", [], columns=["observed_utc", "seller_sku", "asin"])
    _write_csv(
        analysis_dir / "bef_operational_feedback_seed_latest.csv",
        [],
        columns=["observed_utc", "operational_asin", "operational_sku", "bridge_status", "seed_priority"],
    )
    _write_csv(
        analysis_dir / "hf_learning_alignment_30d_latest.csv",
        [],
        columns=["alignment_window_end_utc", "sku", "asin", "expected_units_30d", "expected_profit_30d_gbp"],
    )
    _write_csv(
        analysis_dir / "hf_learning_identity_bridge_latest.csv",
        [],
        columns=["snapshot_utc", "supplier_sku", "asin", "sku"],
    )

    result = bef002.build_sales_feedback_actuals(
        output_dir=analysis_dir,
        observed_utc="2026-04-20T15:51:00Z",
    )

    out_df = pd.read_csv(result.actuals_path, dtype=str).fillna("")
    assert list(out_df.columns) == bef002.ACTUALS_COLUMNS
    assert out_df.empty


def test_build_sales_feedback_actuals_adds_seed_replay_rows_when_summary_overlap_is_zero(
    tmp_path: Path, monkeypatch
) -> None:
    out = tmp_path / "out"
    analysis_dir = out / "analysis_reports"

    monkeypatch.setattr(bef002, "FOUNDATION_PATH", analysis_dir / "bef_sales_truth_foundation_latest.csv")
    monkeypatch.setattr(bef002, "DAILY_TRUTH_PATH", out / "sku_daily_sales_truth_latest.csv")
    monkeypatch.setattr(bef002, "SUMMARY_PATH", out / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv")
    monkeypatch.setattr(bef002, "SEED_PATH", analysis_dir / "bef_operational_feedback_seed_latest.csv")
    monkeypatch.setattr(bef002, "ALIGNMENT_PATH", analysis_dir / "hf_learning_alignment_30d_latest.csv")
    monkeypatch.setattr(bef002, "IDENTITY_BRIDGE_PATH", analysis_dir / "hf_learning_identity_bridge_latest.csv")

    _write_csv(
        analysis_dir / "bef_sales_truth_foundation_latest.csv",
        [
            {"operational_sku": "SKU2", "operational_asin": "A2", "asin_bridge_status": "resolved"},
        ],
        columns=["operational_sku", "operational_asin", "asin_bridge_status"],
    )
    _write_csv(
        out / "sku_daily_sales_truth_latest.csv",
        [
            {"sku": "SKU2", "date": "2026-04-20", "source_state": "finalized_ledger", "units": "3", "profit_gbp": "6.0"},
        ],
        columns=["sku", "date", "source_state", "units", "profit_gbp"],
    )
    _write_csv(
        out / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv",
        [
            {"observed_utc": "2026-04-20T10:00:00Z", "seller_sku": "SUP-X", "asin": "AX"},
        ],
        columns=["observed_utc", "seller_sku", "asin"],
    )
    _write_csv(
        analysis_dir / "bef_operational_feedback_seed_latest.csv",
        [
            {
                "observed_utc": "2026-04-20T15:49:00Z",
                "operational_asin": "A2",
                "operational_sku": "SKU2",
                "bridge_status": "resolved",
                "seed_priority": "high",
            }
        ],
        columns=["observed_utc", "operational_asin", "operational_sku", "bridge_status", "seed_priority"],
    )
    _write_csv(
        analysis_dir / "hf_learning_alignment_30d_latest.csv",
        [],
        columns=["alignment_window_end_utc", "sku", "asin", "expected_units_30d", "expected_profit_30d_gbp"],
    )
    _write_csv(
        analysis_dir / "hf_learning_identity_bridge_latest.csv",
        [],
        columns=["snapshot_utc", "supplier_sku", "asin", "sku"],
    )

    result = bef002.build_sales_feedback_actuals(
        output_dir=analysis_dir,
        observed_utc="2026-04-20T15:50:00Z",
    )

    out_df = pd.read_csv(result.actuals_path, dtype=str).fillna("")
    seed_rows = out_df[out_df["actuals_basis"] == "operational_seed_replay"].copy()
    assert len(seed_rows) == 1
    row = seed_rows.iloc[0]
    assert row["seller_sku"] == "SKU2"
    assert row["asin"] == "A2"
    assert row["decision_snapshot_utc"] == "2026-04-20T15:49:00Z"
    assert row["purchased_flag"] == "auto_operational_seed_replay"


def test_build_sales_feedback_actuals_adds_alignment_native_rows_when_expected_baseline_exists(
    tmp_path: Path, monkeypatch
) -> None:
    out = tmp_path / "out"
    analysis_dir = out / "analysis_reports"

    monkeypatch.setattr(bef002, "FOUNDATION_PATH", analysis_dir / "bef_sales_truth_foundation_latest.csv")
    monkeypatch.setattr(bef002, "DAILY_TRUTH_PATH", out / "sku_daily_sales_truth_latest.csv")
    monkeypatch.setattr(bef002, "SUMMARY_PATH", out / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv")
    monkeypatch.setattr(bef002, "SEED_PATH", analysis_dir / "bef_operational_feedback_seed_latest.csv")
    monkeypatch.setattr(bef002, "ALIGNMENT_PATH", analysis_dir / "hf_learning_alignment_30d_latest.csv")
    monkeypatch.setattr(bef002, "IDENTITY_BRIDGE_PATH", analysis_dir / "hf_learning_identity_bridge_latest.csv")

    _write_csv(
        analysis_dir / "bef_sales_truth_foundation_latest.csv",
        [
            {"operational_sku": "SKU2", "operational_asin": "A2", "asin_bridge_status": "resolved"},
        ],
        columns=["operational_sku", "operational_asin", "asin_bridge_status"],
    )
    _write_csv(
        out / "sku_daily_sales_truth_latest.csv",
        [
            {"sku": "SKU2", "date": "2026-04-20", "source_state": "finalized_ledger", "units": "3", "profit_gbp": "6.0"},
        ],
        columns=["sku", "date", "source_state", "units", "profit_gbp"],
    )
    _write_csv(
        out / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv",
        [],
        columns=["observed_utc", "seller_sku", "asin"],
    )
    _write_csv(
        analysis_dir / "bef_operational_feedback_seed_latest.csv",
        [],
        columns=["observed_utc", "operational_asin", "operational_sku", "bridge_status", "seed_priority"],
    )
    _write_csv(
        analysis_dir / "hf_learning_alignment_30d_latest.csv",
        [
            {
                "alignment_window_end_utc": "2026-04-20T09:00:00Z",
                "sku": "ALIGN-SKU-2",
                "asin": "A2",
                "expected_units_30d": "10",
                "expected_profit_30d_gbp": "5",
            }
        ],
        columns=["alignment_window_end_utc", "sku", "asin", "expected_units_30d", "expected_profit_30d_gbp"],
    )
    _write_csv(
        analysis_dir / "hf_learning_identity_bridge_latest.csv",
        [],
        columns=["snapshot_utc", "supplier_sku", "asin", "sku"],
    )

    result = bef002.build_sales_feedback_actuals(
        output_dir=analysis_dir,
        observed_utc="2026-04-20T15:50:00Z",
    )

    out_df = pd.read_csv(result.actuals_path, dtype=str).fillna("")
    alignment_rows = out_df[out_df["actuals_basis"] == "alignment_asin_map"].copy()
    assert len(alignment_rows) == 1
    row = alignment_rows.iloc[0]
    assert row["seller_sku"] == "ALIGN-SKU-2"
    assert row["asin"] == "A2"
    assert row["decision_snapshot_utc"] == "2026-04-20T09:00:00Z"
    assert row["purchased_flag"] == "auto_alignment_asin_match"


def test_build_sales_feedback_actuals_adds_direct_bridge_rows_when_identity_resolution_exists(
    tmp_path: Path, monkeypatch
) -> None:
    out = tmp_path / "out"
    analysis_dir = out / "analysis_reports"

    monkeypatch.setattr(bef002, "FOUNDATION_PATH", analysis_dir / "bef_sales_truth_foundation_latest.csv")
    monkeypatch.setattr(bef002, "DAILY_TRUTH_PATH", out / "sku_daily_sales_truth_latest.csv")
    monkeypatch.setattr(bef002, "SUMMARY_PATH", out / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv")
    monkeypatch.setattr(bef002, "SEED_PATH", analysis_dir / "bef_operational_feedback_seed_latest.csv")
    monkeypatch.setattr(bef002, "ALIGNMENT_PATH", analysis_dir / "hf_learning_alignment_30d_latest.csv")
    monkeypatch.setattr(bef002, "IDENTITY_BRIDGE_PATH", analysis_dir / "hf_learning_identity_bridge_latest.csv")

    _write_csv(
        analysis_dir / "bef_sales_truth_foundation_latest.csv",
        [
            {"operational_sku": "SKU-OP-1", "operational_asin": "A1", "asin_bridge_status": "resolved"},
        ],
        columns=["operational_sku", "operational_asin", "asin_bridge_status"],
    )
    _write_csv(
        out / "sku_daily_sales_truth_latest.csv",
        [
            {"sku": "SKU-OP-1", "date": "2026-04-20", "source_state": "finalized_ledger", "units": "5", "profit_gbp": "10.0"},
        ],
        columns=["sku", "date", "source_state", "units", "profit_gbp"],
    )
    _write_csv(
        out / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv",
        [
            {"observed_utc": "2026-04-20T10:00:00Z", "seller_sku": "SUP-100", "asin": "LEGACY-ASIN-1"},
        ],
        columns=["observed_utc", "seller_sku", "asin"],
    )
    _write_csv(
        analysis_dir / "bef_operational_feedback_seed_latest.csv",
        [],
        columns=["observed_utc", "operational_asin", "operational_sku", "bridge_status", "seed_priority"],
    )
    _write_csv(
        analysis_dir / "hf_learning_alignment_30d_latest.csv",
        [],
        columns=["alignment_window_end_utc", "sku", "asin", "expected_units_30d", "expected_profit_30d_gbp"],
    )
    _write_csv(
        analysis_dir / "hf_learning_identity_bridge_latest.csv",
        [
            {
                "snapshot_utc": "2026-04-20T09:30:00Z",
                "supplier_sku": "SUP-100",
                "asin": "LEGACY-ASIN-1",
                "sku": "SKU-OP-1",
            }
        ],
        columns=["snapshot_utc", "supplier_sku", "asin", "sku"],
    )

    result = bef002.build_sales_feedback_actuals(
        output_dir=analysis_dir,
        observed_utc="2026-04-20T15:52:00Z",
    )

    out_df = pd.read_csv(result.actuals_path, dtype=str).fillna("")
    direct_rows = out_df[out_df["actuals_basis"] == "summary_direct_bridge"].copy()
    assert len(direct_rows) == 1
    row = direct_rows.iloc[0]
    assert row["seller_sku"] == "SUP-100"
    assert row["asin"] == "A1"
    assert row["decision_snapshot_utc"] == "2026-04-20T10:00:00Z"
    assert row["purchased_flag"] == "auto_summary_direct_bridge"
