from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.one_off.H165_build_h_signoff_proof_pack import build_h_signoff_proof_pack


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _run_id_to_iso(run_id: str) -> str:
    dt = datetime.strptime(run_id, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _provenance_payload(run_id: str, *, run_once: bool) -> dict[str, object]:
    guarded_cmd = (
        "python.exe -u scripts/cycles/run_H_pricing_cycle_guarded.py "
        "--phase1-pilot --phase1-config config/pilot_sku.yaml --sleep-minutes 0"
    )
    if run_once:
        guarded_cmd = f"{guarded_cmd} --run-once"
    return {
        "run_id": run_id,
        "observed": {
            "creator_chain_start": [
                {
                    "depth": 1,
                    "node": {
                        "command_line": "python.exe -u scripts/cycles/run_H_pricing_cycle.py --phase1-pilot --sleep-minutes 0"
                    },
                },
                {"depth": 2, "node": {"command_line": guarded_cmd}},
                {"depth": 3, "node": {"command_line": "cmd.exe /d /c call C:\\repo\\run_H_cycle.bat"}},
            ]
        },
    }


def test_build_h_signoff_proof_pack_detects_scheduler_chain_and_excludes_run_once(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    analysis_dir = out_dir / "analysis_reports"
    candidate_ts = "2026-04-17T11:13:01Z"

    outcome_log_path = out_dir / "h_strategy_outcome_log.csv"
    _write_csv(
        outcome_log_path,
        [
            "event_ts_utc",
            "run_id",
            "sku",
            "scenario_type",
            "chosen_tactic",
            "our_price_before_gbp",
            "target_price_gbp",
            "writer_outcome",
            "tactic_success_state",
            "reason_codes_json",
        ],
        [
            {
                "event_ts_utc": "2026-04-17T12:00:00Z",
                "run_id": "20260417T120000Z",
                "sku": "SKU-1",
                "scenario_type": "share_hold",
                "chosen_tactic": "HOLD_OBSERVE",
                "our_price_before_gbp": "10.00",
                "target_price_gbp": "10.00",
                "writer_outcome": "NO_WRITE",
                "tactic_success_state": "aborted",
                "reason_codes_json": "[\"OUTCOME_RECLASSIFIED_NON_ACTION_HOLD\"]",
            },
            {
                "event_ts_utc": "2026-04-17T12:01:00Z",
                "run_id": "20260417T120500Z",
                "sku": "SKU-2",
                "scenario_type": "suppression_reactivation",
                "chosen_tactic": "SUPPRESSION_REACTIVATION",
                "our_price_before_gbp": "8.00",
                "target_price_gbp": "7.90",
                "writer_outcome": "APPLIED",
                "tactic_success_state": "success",
                "reason_codes_json": "[]",
            },
            {
                "event_ts_utc": "2026-04-17T12:02:00Z",
                "run_id": "20260417T121000Z",
                "sku": "SKU-3",
                "scenario_type": "controlled_exit",
                "chosen_tactic": "CONTROLLED_EXIT_TO_FLOOR",
                "our_price_before_gbp": "9.50",
                "target_price_gbp": "8.90",
                "writer_outcome": "APPLIED",
                "tactic_success_state": "success",
                "reason_codes_json": "[]",
            },
        ],
    )

    outcome_daily_path = out_dir / "h_strategy_outcome_daily.csv"
    _write_csv(
        outcome_daily_path,
        [
            "asof_date",
            "scenario_type",
            "chosen_tactic",
            "decision_rows",
            "resolved_rows",
            "pending_rows",
            "success_rows",
            "failed_rows",
            "expired_rows",
            "aborted_rows",
            "at_floor_rows",
        ],
        [
            {
                "asof_date": "2026-04-17",
                "scenario_type": "share_hold",
                "chosen_tactic": "HOLD_OBSERVE",
                "decision_rows": "1",
                "resolved_rows": "1",
                "pending_rows": "0",
                "success_rows": "0",
                "failed_rows": "0",
                "expired_rows": "0",
                "aborted_rows": "1",
                "at_floor_rows": "0",
            }
        ],
    )

    checklist_path = out_dir / "cycle_alerts" / "checklist_H.csv"
    _write_csv(
        checklist_path,
        ["check", "status", "value", "notes", "alert_first_seen_utc", "alert_last_seen_utc", "alert_consecutive_runs", "alert_age_hours"],
        [
            {
                "check": "h_ceiling_effective_floor_integrity",
                "status": "ok",
                "value": "0",
                "notes": "scope_run_id=20260417T120000Z",
                "alert_first_seen_utc": "",
                "alert_last_seen_utc": "",
                "alert_consecutive_runs": "",
                "alert_age_hours": "",
            }
        ],
    )

    health_status_path = out_dir / "health_status_H.csv"
    _write_csv(
        health_status_path,
        ["timestamp_utc", "status", "fail_count", "warn_count", "notes"],
        [
            {
                "timestamp_utc": "2026-04-17T12:30:00+00:00",
                "status": "WARN",
                "fail_count": "0",
                "warn_count": "1",
                "notes": "fail=0 warn=1",
            }
        ],
    )

    live_alert_path = out_dir / "systems" / "H" / "live" / "h_seller_detail_measurement_alerts_latest.csv"
    _write_csv(
        live_alert_path,
        ["snapshot_utc", "run_id", "previous_run_id", "alert_key", "status", "current_value", "previous_value", "delta", "threshold", "notes"],
        [
            {
                "snapshot_utc": "2026-04-17T12:40:00Z",
                "run_id": "20260417T124000Z",
                "previous_run_id": "20260417T123500Z",
                "alert_key": "pending_retry_growth",
                "status": "ok",
                "current_value": "0",
                "previous_value": "0",
                "delta": "0",
                "threshold": "3",
                "notes": "",
            },
            {
                "snapshot_utc": "2026-04-17T12:40:00Z",
                "run_id": "20260417T124000Z",
                "previous_run_id": "20260417T123500Z",
                "alert_key": "retry_exhausted_growth",
                "status": "ok",
                "current_value": "0",
                "previous_value": "0",
                "delta": "0",
                "threshold": "3",
                "notes": "",
            },
            {
                "snapshot_utc": "2026-04-17T12:40:00Z",
                "run_id": "20260417T124000Z",
                "previous_run_id": "20260417T123500Z",
                "alert_key": "amazon_missing_pressure",
                "status": "ok",
                "current_value": "0",
                "previous_value": "0",
                "delta": "0",
                "threshold": "3",
                "notes": "",
            },
            {
                "snapshot_utc": "2026-04-17T12:40:00Z",
                "run_id": "20260417T124000Z",
                "previous_run_id": "20260417T123500Z",
                "alert_key": "stale_pending_pressure",
                "status": "ok",
                "current_value": "0",
                "previous_value": "0",
                "delta": "0",
                "threshold": "1",
                "notes": "",
            },
        ],
    )

    h_cycle_log_path = out_dir / "systems" / "H" / "live" / "H_cycle.log"
    h_cycle_log_path.parent.mkdir(parents=True, exist_ok=True)
    scheduler_run_ids = [
        "20260417T120000Z",
        "20260417T120500Z",
        "20260417T121000Z",
        "20260417T121500Z",
        "20260417T122000Z",
        "20260417T122500Z",
        "20260417T123000Z",
        "20260417T123500Z",
        "20260417T124000Z",
        "20260417T124500Z",
    ]
    run_once_id = "20260417T115500Z"
    lines: list[str] = []
    for run_id in [run_once_id, *scheduler_run_ids]:
        ts = _run_id_to_iso(run_id)
        lines.append(f"{ts} h_run_state_write state=finalized run_id={run_id} stage=phase1_publish publish_status=ok")
        lines.append(f"{ts} h_worker_lifecycle_write run_id={run_id} state=succeeded attempt=1")
    h_cycle_log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    provenance_dir = out_dir / "systems" / "H" / "live"
    for run_id in scheduler_run_ids:
        payload = _provenance_payload(run_id, run_once=False)
        (provenance_dir / f"H_owner_termination_provenance.{run_id}.1000.20260417T130000Z.json").write_text(
            json.dumps(payload),
            encoding="utf-8",
        )
    run_once_payload = _provenance_payload(run_once_id, run_once=True)
    (provenance_dir / f"H_owner_termination_provenance.{run_once_id}.999.20260417T130000Z.json").write_text(
        json.dumps(run_once_payload),
        encoding="utf-8",
    )

    result = build_h_signoff_proof_pack(
        candidate_ts_utc=candidate_ts,
        denominator_contract="effective_chaseable_population",
        output_dir=analysis_dir,
        outcome_log_path=outcome_log_path,
        outcome_daily_path=outcome_daily_path,
        checklist_path=checklist_path,
        health_status_path=health_status_path,
        h_cycle_log_path=h_cycle_log_path,
        provenance_dir=provenance_dir,
        live_alert_path=live_alert_path,
        observed_utc="2026-04-17T13:00:00Z",
    )

    assert result.json_path.exists()
    assert result.csv_path.exists()
    assert result.latest_json_path.exists()
    assert result.latest_csv_path.exists()

    payload = result.payload
    assert payload["health"]["latest_health"]["newer_than_candidate"] is True
    assert payload["gates"]["same_target_applied_zero"]["pass"] is True
    assert payload["run_chain"]["scheduler_owned_runs_count"] == 10
    assert payload["run_chain"]["scheduler_owned_consecutive_success_max"] == 10
    assert payload["run_chain"]["ten_scheduler_success_chain_met"] is True

    scheduler_ids = [row["run_id"] for row in payload["run_chain"]["scheduler_runs"]]
    assert run_once_id not in scheduler_ids
    assert scheduler_ids == scheduler_run_ids
