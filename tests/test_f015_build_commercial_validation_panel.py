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

from scripts.one_off.F015_build_commercial_validation_panel import build_commercial_validation_panel


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _seed_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    groups = [("big_pass", 5), ("big_fail", 5), ("on_the_line", 5)]
    asin_idx = 1
    for group_name, count in groups:
        for rank in range(1, count + 1):
            asin = f"BTEST{asin_idx:05d}"
            rows.append(
                {
                    "panel_group": group_name,
                    "panel_rank": str(rank),
                    "asin": asin,
                    "seller_sku": f"OPER::{asin}",
                    "truth_decision_state": "pass" if group_name == "big_pass" else "fail",
                    "actual_units_30d": str(asin_idx),
                    "actual_profit_30d_gbp": str(asin_idx),
                    "model_expected_units_next_30d": str(asin_idx + 1),
                    "model_expected_profit_next_30d_gbp": "0",
                    "demand_alignment_state": "aligned",
                    "profit_alignment_state": "aligned",
                    "model_side_evidence_state": "estimate_only",
                    "in_sold_capture_pack": "1",
                    "selection_reason": "test_seed",
                }
            )
            asin_idx += 1
    return rows


def _accuracy_rows_from_seed(seed_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for idx, seed in enumerate(seed_rows, start=1):
        rows.append(
            {
                "observed_utc": "2026-04-21T15:55:00Z",
                "asin": seed["asin"],
                "seller_sku": seed["seller_sku"],
                "truth_decision_state": seed["truth_decision_state"],
                "actual_units_30d": str(idx + 2),
                "actual_profit_30d_gbp": str(10 + idx),
                "model_expected_units_next_30d": str(idx + 3),
                "model_expected_profit_next_30d_gbp": str(idx),
                "demand_alignment_state": "moderate_model_overestimate",
                "profit_alignment_state": "severe_model_underestimate",
                "model_side_evidence_state": "estimate_only",
                "in_sold_capture_pack": "1",
            }
        )
    return rows


def _metric(summary_df: pd.DataFrame, metric: str) -> str:
    rows = summary_df.loc[summary_df["metric"] == metric]
    if rows.empty:
        return ""
    return str(rows.iloc[0]["value"])


def test_f015_builds_panel_with_expected_group_counts(tmp_path: Path) -> None:
    seed_path = tmp_path / "panel_seed.csv"
    accuracy_path = tmp_path / "accuracy.csv"
    output_dir = tmp_path / "out"

    seed_rows = _seed_rows()
    _write_csv(seed_path, seed_rows)
    _write_csv(accuracy_path, _accuracy_rows_from_seed(seed_rows))

    result = build_commercial_validation_panel(
        accuracy_path=accuracy_path,
        panel_seed_path=seed_path,
        output_dir=output_dir,
        observed_utc="2026-04-21T16:20:00Z",
    )

    assert len(result.panel_df.index) == 15
    assert _metric(result.summary_df, "panel_rows_total") == "15"
    assert _metric(result.summary_df, "panel_missing_rows") == "0"
    assert _metric(result.summary_df, "big_pass_rows") == "5"
    assert _metric(result.summary_df, "big_fail_rows") == "5"
    assert _metric(result.summary_df, "on_the_line_rows") == "5"
    assert (result.panel_df["row_present_in_accuracy"] == "1").all()
    assert result.panel_latest_path.exists()
    assert result.summary_latest_path.exists()


def test_f015_flags_missing_panel_row_when_accuracy_row_absent(tmp_path: Path) -> None:
    seed_path = tmp_path / "panel_seed.csv"
    accuracy_path = tmp_path / "accuracy.csv"
    output_dir = tmp_path / "out"

    seed_rows = _seed_rows()
    accuracy_rows = _accuracy_rows_from_seed(seed_rows)
    accuracy_rows = [row for row in accuracy_rows if row["asin"] != "BTEST00015"]
    _write_csv(seed_path, seed_rows)
    _write_csv(accuracy_path, accuracy_rows)

    result = build_commercial_validation_panel(
        accuracy_path=accuracy_path,
        panel_seed_path=seed_path,
        output_dir=output_dir,
        observed_utc="2026-04-21T16:21:00Z",
    )

    missing_rows = result.panel_df.loc[result.panel_df["row_present_in_accuracy"] == "0"]
    assert len(missing_rows.index) == 1
    assert str(missing_rows.iloc[0]["asin"]) == "BTEST00015"
    assert _metric(result.summary_df, "panel_missing_rows") == "1"
