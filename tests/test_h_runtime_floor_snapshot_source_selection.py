from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.cycles import run_H_pricing_cycle as h_cycle


REQUIRED_COLS = {"sku", "event_ts_utc", "hard_floor_gbp", "final_ceiling_landed_gbp", "state", "write_status"}


def _write_exec_log(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def test_select_latest_execution_log_df_picks_newest_event(tmp_path: Path) -> None:
    preferred_path = tmp_path / "preferred.csv"
    newer_path = tmp_path / "newer.csv"

    _write_exec_log(
        preferred_path,
        [
            {
                "sku": "6V-EEC1-2S9Z",
                "event_ts_utc": "2026-04-09T16:23:16Z",
                "hard_floor_gbp": "5.85",
                "final_ceiling_landed_gbp": "10.64",
                "state": "TEMP_TRIAL_UNDERCUT",
                "write_status": "NO_WRITE_REQUIRED",
            }
        ],
    )
    _write_exec_log(
        newer_path,
        [
            {
                "sku": "6V-EEC1-2S9Z",
                "event_ts_utc": "2026-04-09T16:44:20Z",
                "hard_floor_gbp": "5.85",
                "final_ceiling_landed_gbp": "10.64",
                "state": "TEMP_TRIAL_UNDERCUT",
                "write_status": "NO_WRITE_REQUIRED",
            }
        ],
    )

    selected_df, selected_path, selected_max_dt = h_cycle._select_latest_execution_log_df(
        candidate_paths=[preferred_path, newer_path],
        required_exec_cols=REQUIRED_COLS,
    )

    assert selected_path == newer_path
    assert str(selected_df.iloc[0].get("event_ts_utc", "")) == "2026-04-09T16:44:20Z"
    assert pd.notna(selected_max_dt)


def test_select_latest_execution_log_df_ignores_invalid_schema(tmp_path: Path) -> None:
    invalid_path = tmp_path / "invalid.csv"
    valid_path = tmp_path / "valid.csv"

    pd.DataFrame([{"sku": "6V-EEC1-2S9Z", "event_ts_utc": "2026-04-09T16:44:20Z"}]).to_csv(invalid_path, index=False)
    _write_exec_log(
        valid_path,
        [
            {
                "sku": "6V-EEC1-2S9Z",
                "event_ts_utc": "2026-04-09T16:23:16Z",
                "hard_floor_gbp": "5.85",
                "final_ceiling_landed_gbp": "10.64",
                "state": "TEMP_TRIAL_UNDERCUT",
                "write_status": "NO_WRITE_REQUIRED",
            }
        ],
    )

    selected_df, selected_path, _ = h_cycle._select_latest_execution_log_df(
        candidate_paths=[invalid_path, valid_path],
        required_exec_cols=REQUIRED_COLS,
    )

    assert selected_path == valid_path
    assert len(selected_df.index) == 1
