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

from scripts.one_off import BEF001_build_operational_feedback_seed as bef001


def _write_csv(path: Path, rows: list[dict[str, str]], *, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def test_build_operational_feedback_seed_priority_and_flags(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "out"
    analysis_dir = out / "analysis_reports"
    monkeypatch.setattr(bef001, "FOUNDATION_PATH", analysis_dir / "bef_sales_truth_foundation_latest.csv")
    monkeypatch.setattr(bef001, "DAILY_TRUTH_PATH", out / "sku_daily_sales_truth_latest.csv")
    monkeypatch.setattr(bef001, "F_SUMMARY_PATH", out / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv")

    _write_csv(
        analysis_dir / "bef_sales_truth_foundation_latest.csv",
        [
            {
                "operational_sku": "SKU1",
                "operational_asin": "A1",
                "asin_bridge_status": "resolved",
                "asin_ambiguity_flag": "0",
                "truth_state": "finalized",
            },
            {
                "operational_sku": "SKU2",
                "operational_asin": "A2",
                "asin_bridge_status": "ambiguous",
                "asin_ambiguity_flag": "1",
                "truth_state": "provisional_only",
            },
            {
                "operational_sku": "SKU3",
                "operational_asin": "",
                "asin_bridge_status": "unresolved",
                "asin_ambiguity_flag": "0",
                "truth_state": "no_truth_rows",
            },
        ],
        columns=["operational_sku", "operational_asin", "asin_bridge_status", "asin_ambiguity_flag", "truth_state"],
    )
    _write_csv(
        out / "sku_daily_sales_truth_latest.csv",
        [
            {"sku": "SKU1", "date": "2026-04-20", "units": "2"},
            {"sku": "SKU1", "date": "2026-04-10", "units": "1"},
            {"sku": "SKU2", "date": "2026-04-20", "units": "0"},
        ],
        columns=["sku", "date", "units"],
    )
    _write_csv(
        out / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv",
        [{"asin": "A1"}, {"asin": "AX"}],
        columns=["asin"],
    )

    result = bef001.build_operational_feedback_seed(
        output_dir=analysis_dir,
        observed_utc="2026-04-20T15:40:00Z",
    )

    assert result.seed_path.exists()
    seed = pd.read_csv(result.seed_path, dtype=str).fillna("")
    rows = seed.set_index("operational_sku")

    assert seed.iloc[0]["operational_sku"] == "SKU1"
    assert rows.loc["SKU1", "recent_sales_presence_flag"] == "1"
    assert rows.loc["SKU1", "units_last_30d"] == "3"
    assert rows.loc["SKU1", "in_f_universe_flag"] == "1"
    assert rows.loc["SKU1", "seed_priority"] == "high"
    assert "bridge_resolved" in rows.loc["SKU1", "seed_reason_codes"]
    assert "in_f_universe" in rows.loc["SKU1", "seed_reason_codes"]

    assert rows.loc["SKU2", "bridge_status"] == "ambiguous"
    assert rows.loc["SKU2", "ambiguity_flag"] == "1"
    assert rows.loc["SKU2", "recent_sales_presence_flag"] == "0"
    assert rows.loc["SKU2", "seed_priority"] == "low"

    assert rows.loc["SKU3", "bridge_status"] == "unresolved"
    assert rows.loc["SKU3", "seed_priority"] == "low"
    assert "no_asin" in rows.loc["SKU3", "seed_reason_codes"]


def test_build_operational_feedback_seed_empty_foundation(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "out"
    analysis_dir = out / "analysis_reports"
    monkeypatch.setattr(bef001, "FOUNDATION_PATH", analysis_dir / "bef_sales_truth_foundation_latest.csv")
    monkeypatch.setattr(bef001, "DAILY_TRUTH_PATH", out / "sku_daily_sales_truth_latest.csv")
    monkeypatch.setattr(bef001, "F_SUMMARY_PATH", out / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv")

    _write_csv(analysis_dir / "bef_sales_truth_foundation_latest.csv", [], columns=["operational_sku"])

    result = bef001.build_operational_feedback_seed(
        output_dir=analysis_dir,
        observed_utc="2026-04-20T15:41:00Z",
    )

    out_df = pd.read_csv(result.seed_path, dtype=str).fillna("")
    assert list(out_df.columns) == bef001.SEED_COLUMNS
    assert out_df.empty
