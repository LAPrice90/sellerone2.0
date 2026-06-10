from __future__ import annotations

import csv
import sys
from pathlib import Path

from scripts.one_off import H162_rebuild_strategy_outcome_daily as h162


LOG_FIELDS = [
    "event_ts_utc",
    "scenario_type",
    "chosen_tactic",
    "tactic_case_id",
    "writer_outcome",
    "tactic_success_state",
    "seller_count",
    "our_price_before_gbp",
    "lowest_price_1_gbp",
    "buy_box_state_after",
    "stop_rule_code",
    "reason_codes_json",
]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_rebuild_daily_rows_rebuilds_known_53_row_group_from_source_log() -> None:
    asof_date = "2026-05-13"
    scenario_type = "multi_seller_ladder_cap"
    chosen_tactic = "MULTI_SELLER_LADDER_CAP"
    states = ["success"] * 11 + ["failed"] * 10 + ["expired"] * 32
    rows: list[dict[str, str]] = []
    for idx, state in enumerate(states):
        writer_outcome = "APPLIED" if idx < 34 else "NO_WRITE_REQUIRED"
        event_ts = f"{asof_date}T{idx // 3:02d}:{(idx * 7) % 60:02d}:00Z"
        rows.append(
            {
                "event_ts_utc": event_ts,
                "scenario_type": scenario_type,
                "chosen_tactic": chosen_tactic,
                "tactic_case_id": f"SKU_KNOWN_{idx:02d}-{event_ts.replace(':', '').replace('-', '')}",
                "writer_outcome": writer_outcome,
                "tactic_success_state": state,
                "seller_count": "4",
                "our_price_before_gbp": "10.40",
                "lowest_price_1_gbp": "10.00",
            }
        )

    rebuilt = h162._rebuild_daily_rows(
        rows,
        {
            (asof_date, scenario_type, chosen_tactic): {
                "below_break_even_rows": "0",
                "at_floor_rows": "9",
                "notes": "",
            }
        },
    )

    assert len(rebuilt) == 1
    row = rebuilt[0]
    assert row["decision_rows"] == "53"
    assert row["applied_rows"] == "34"
    assert row["no_write_rows"] == "19"
    assert row["resolved_rows"] == "53"
    assert row["pending_rows"] == "0"
    terminal_rows = sum(
        int(row[name])
        for name in ["success_rows", "failed_rows", "expired_rows", "aborted_rows"]
    )
    assert terminal_rows == int(row["decision_rows"])


def test_daily_only_main_does_not_normalize_source_log(tmp_path: Path, monkeypatch, capsys) -> None:
    log_path = tmp_path / "h_strategy_outcome_log.csv"
    daily_path = tmp_path / "h_strategy_outcome_daily.csv"
    _write_csv(
        log_path,
        LOG_FIELDS,
        [
            {
                "event_ts_utc": "2026-05-13T09:00:00Z",
                "scenario_type": "multi_seller_ladder_cap",
                "chosen_tactic": "MULTI_SELLER_LADDER_CAP",
                "tactic_case_id": "CASE-001",
                "writer_outcome": "NO_WRITE_REQUIRED",
                "tactic_success_state": "failed",
                "seller_count": "4",
                "our_price_before_gbp": "10.40",
                "lowest_price_1_gbp": "10.00",
                "buy_box_state_after": "OBSERVATION_TIMEOUT",
                "stop_rule_code": "UNDERCUT_NO_DOWNWARD_HEADROOM",
                "reason_codes_json": "[]",
            }
        ],
    )
    monkeypatch.setattr(h162, "OUTCOME_LOG_PATH", log_path)
    monkeypatch.setattr(h162, "OUTCOME_DAILY_PATH", daily_path)
    monkeypatch.setattr(sys, "argv", ["H162_rebuild_strategy_outcome_daily.py", "--daily-only"])

    assert h162.main() == 0

    output = capsys.readouterr().out
    source_row = _read_csv(log_path)[0]
    daily_row = _read_csv(daily_path)[0]
    assert "daily_only=1" in output
    assert source_row["tactic_success_state"] == "failed"
    assert source_row["scenario_type"] == "multi_seller_ladder_cap"
    assert daily_row["decision_rows"] == "1"
    assert daily_row["failed_rows"] == "1"
