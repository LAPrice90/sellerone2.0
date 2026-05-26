from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"

DEFAULT_CANDIDATE_TS_UTC = "2026-04-17T11:13:01Z"
DEFAULT_DENOMINATOR_CONTRACT = "effective_chaseable_population"

DEFAULT_OUTCOME_LOG_PATH = OUT / "h_strategy_outcome_log.csv"
DEFAULT_OUTCOME_DAILY_PATH = OUT / "h_strategy_outcome_daily.csv"
DEFAULT_CHECKLIST_PATH = OUT / "cycle_alerts" / "checklist_H.csv"
DEFAULT_HEALTH_STATUS_PATH = OUT / "health_status_H.csv"
DEFAULT_LIVE_ALERT_PATH = OUT / "systems" / "H" / "live" / "h_seller_detail_measurement_alerts_latest.csv"
DEFAULT_H_CYCLE_LOG_PATH = OUT / "systems" / "H" / "live" / "H_cycle.log"
DEFAULT_PROVENANCE_DIR = OUT / "systems" / "H" / "live"
DEFAULT_OUTPUT_DIR = OUT / "analysis_reports"

RUN_ID_RE = re.compile(r"^\d{8}T\d{6}Z$")
PROVENANCE_FILE_RE = re.compile(r"^H_owner_termination_provenance\.(?P<run_id>\d{8}T\d{6}Z)\..*\.json$")
RUN_STATE_RE = re.compile(
    r"^(?P<ts>\S+)\s+h_run_state_write\s+state=(?P<state>\S+)\s+run_id=(?P<run_id>\d{8}T\d{6}Z)\b"
)
WORKER_STATE_RE = re.compile(
    r"^(?P<ts>\S+)\s+h_worker_lifecycle_write\s+run_id=(?P<run_id>\d{8}T\d{6}Z)\s+state=(?P<state>\S+)\b"
)


@dataclass(frozen=True)
class ProofPackResult:
    payload: Dict[str, Any]
    json_path: Path
    csv_path: Path
    latest_json_path: Path
    latest_csv_path: Path


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _parse_iso_utc(value: object) -> datetime | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    raw_for_parse = raw
    if raw_for_parse.endswith("Z"):
        raw_for_parse = raw_for_parse[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw_for_parse)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_run_id_utc(run_id: str) -> datetime | None:
    text = _normalize_text(run_id)
    if not RUN_ID_RE.match(text):
        return None
    return datetime.strptime(text, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def _to_timestamp_slug(utc_iso: str) -> str:
    parsed = _parse_iso_utc(utc_iso)
    if parsed is None:
        raise ValueError(f"invalid utc timestamp: {utc_iso}")
    return parsed.strftime("%Y%m%dT%H%M%SZ")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                return []
            rows: List[Dict[str, str]] = []
            for row in reader:
                rows.append({name: _normalize_text(row.get(name, "")) for name in reader.fieldnames})
            return rows
    except (OSError, csv.Error):
        return []


def _parse_decimal(value: object) -> Decimal | None:
    text = _normalize_text(value)
    if text == "":
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return float(Decimal(numerator) * Decimal("100") / Decimal(denominator))


def _parse_reason_codes(value: object) -> List[str]:
    raw = _normalize_text(value)
    if raw == "":
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    out: List[str] = []
    for item in parsed:
        code = _normalize_text(item).upper()
        if code:
            out.append(code)
    return out


def _scenario_bucket() -> Dict[str, int]:
    return {
        "rows": 0,
        "pending": 0,
        "success": 0,
        "failed": 0,
        "expired": 0,
        "aborted": 0,
        "applied": 0,
        "no_write": 0,
    }


def _summarize_outcomes(
    outcome_rows: Sequence[Mapping[str, str]],
    *,
    candidate_dt: datetime,
) -> Dict[str, Any]:
    filtered_rows: List[Dict[str, str]] = []
    for row in outcome_rows:
        event_dt = _parse_iso_utc(row.get("event_ts_utc", ""))
        if event_dt is None or event_dt < candidate_dt:
            continue
        filtered_rows.append(dict(row))

    by_scenario: Dict[str, Dict[str, int]] = {}
    same_target_rows = 0
    same_target_applied = 0
    reclassified_non_action_hold_rows = 0

    for row in filtered_rows:
        scenario = _normalize_text(row.get("scenario_type", "")).lower()
        if scenario == "":
            scenario = "unknown"
        bucket = by_scenario.setdefault(scenario, _scenario_bucket())
        bucket["rows"] += 1

        state = _normalize_text(row.get("tactic_success_state", "")).lower()
        if state in {"pending", "success", "failed", "expired", "aborted"}:
            bucket[state] += 1

        writer_outcome = _normalize_text(row.get("writer_outcome", "")).upper()
        if writer_outcome == "APPLIED":
            bucket["applied"] += 1
        else:
            bucket["no_write"] += 1

        current_price = _parse_decimal(row.get("our_price_before_gbp", ""))
        target_price = _parse_decimal(row.get("target_price_gbp", ""))
        if current_price is not None and target_price is not None and current_price == target_price:
            same_target_rows += 1
            if writer_outcome == "APPLIED":
                same_target_applied += 1

        reason_codes = _parse_reason_codes(row.get("reason_codes_json", ""))
        if "OUTCOME_RECLASSIFIED_NON_ACTION_HOLD" in reason_codes:
            reclassified_non_action_hold_rows += 1

    multi = by_scenario.get("multi_seller_ladder_cap", _scenario_bucket())
    suppression = by_scenario.get("suppression_reactivation", _scenario_bucket())
    controlled_exit = by_scenario.get("controlled_exit", _scenario_bucket())

    raw_legacy_multi_seller_population = multi["rows"] + reclassified_non_action_hold_rows
    effective_chaseable_multi_seller_population = multi["rows"]

    return {
        "rows_since_candidate": len(filtered_rows),
        "same_target_rows": same_target_rows,
        "same_target_applied": same_target_applied,
        "reclassified_non_action_hold_rows": reclassified_non_action_hold_rows,
        "raw_legacy_multi_seller_population": raw_legacy_multi_seller_population,
        "effective_chaseable_multi_seller_population": effective_chaseable_multi_seller_population,
        "scenario_counts": by_scenario,
        "multi_seller": multi,
        "suppression_reactivation": suppression,
        "controlled_exit": controlled_exit,
    }


def _summarize_daily(outcome_daily_rows: Sequence[Mapping[str, str]], *, candidate_dt: datetime) -> Dict[str, Any]:
    target_date = candidate_dt.date().isoformat()
    key_map = {
        ("multi_seller_ladder_cap", "REGAIN_LADDER_CAP"): "multi_seller_ladder_cap_regain_ladder_cap",
        ("suppression_reactivation", "SUPPRESSION_REACTIVATION"): "suppression_reactivation",
        ("controlled_exit", "CONTROLLED_EXIT_TO_FLOOR"): "controlled_exit_to_floor",
        ("share_hold", "HOLD_OBSERVE"): "share_hold_observe",
    }
    out: Dict[str, Any] = {}
    for row in outcome_daily_rows:
        if _normalize_text(row.get("asof_date", "")) != target_date:
            continue
        scenario = _normalize_text(row.get("scenario_type", "")).lower()
        tactic = _normalize_text(row.get("chosen_tactic", "")).upper()
        mapped = key_map.get((scenario, tactic))
        if mapped is None:
            continue
        out[mapped] = {
            "decision_rows": int(_parse_decimal(row.get("decision_rows", "")) or 0),
            "resolved_rows": int(_parse_decimal(row.get("resolved_rows", "")) or 0),
            "pending_rows": int(_parse_decimal(row.get("pending_rows", "")) or 0),
            "success_rows": int(_parse_decimal(row.get("success_rows", "")) or 0),
            "failed_rows": int(_parse_decimal(row.get("failed_rows", "")) or 0),
            "expired_rows": int(_parse_decimal(row.get("expired_rows", "")) or 0),
            "aborted_rows": int(_parse_decimal(row.get("aborted_rows", "")) or 0),
            "at_floor_rows": int(_parse_decimal(row.get("at_floor_rows", "")) or 0),
        }
    return out


def _summarize_health(
    checklist_rows: Sequence[Mapping[str, str]],
    health_rows: Sequence[Mapping[str, str]],
    *,
    candidate_dt: datetime,
) -> Dict[str, Any]:
    latest_health: Dict[str, Any] = {
        "timestamp_utc": "",
        "status": "",
        "fail_count": 0,
        "warn_count": 0,
        "newer_than_candidate": False,
    }
    latest_health_dt: datetime | None = None
    for row in health_rows:
        row_dt = _parse_iso_utc(row.get("timestamp_utc", ""))
        if row_dt is None:
            continue
        if latest_health_dt is None or row_dt > latest_health_dt:
            latest_health_dt = row_dt
            latest_health = {
                "timestamp_utc": row_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "status": _normalize_text(row.get("status", "")),
                "fail_count": int(_parse_decimal(row.get("fail_count", "")) or 0),
                "warn_count": int(_parse_decimal(row.get("warn_count", "")) or 0),
                "newer_than_candidate": row_dt > candidate_dt,
            }

    latest_integrity_row: Dict[str, str] = {}
    for row in checklist_rows:
        if _normalize_text(row.get("check", "")) == "h_ceiling_effective_floor_integrity":
            latest_integrity_row = dict(row)
    integrity_status = _normalize_text(latest_integrity_row.get("status", "")).lower()
    integrity_value = _normalize_text(latest_integrity_row.get("value", ""))
    integrity_value_decimal = _parse_decimal(integrity_value)
    integrity_pass = integrity_status == "ok" and integrity_value_decimal == Decimal("0")

    checklist_warns = [
        {
            "check": _normalize_text(row.get("check", "")),
            "value": _normalize_text(row.get("value", "")),
            "notes": _normalize_text(row.get("notes", "")),
        }
        for row in checklist_rows
        if _normalize_text(row.get("status", "")).lower() == "warn"
    ]
    checklist_fails = [
        {
            "check": _normalize_text(row.get("check", "")),
            "value": _normalize_text(row.get("value", "")),
            "notes": _normalize_text(row.get("notes", "")),
        }
        for row in checklist_rows
        if _normalize_text(row.get("status", "")).lower() == "fail"
    ]

    return {
        "latest_health": latest_health,
        "integrity_check": {
            "status": integrity_status,
            "value": integrity_value,
            "pass": integrity_pass,
        },
        "checklist_warns": checklist_warns,
        "checklist_fails": checklist_fails,
    }


def _parse_run_states_from_log(log_path: Path, *, candidate_dt: datetime) -> Dict[str, Dict[str, Any]]:
    run_map: Dict[str, Dict[str, Any]] = {}
    if not log_path.exists():
        return run_map

    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line_text = line.rstrip("\r\n")

            run_match = RUN_STATE_RE.match(line_text)
            if run_match:
                run_id = run_match.group("run_id")
                run_dt = _parse_run_id_utc(run_id)
                if run_dt is None or run_dt < candidate_dt:
                    continue
                entry = run_map.setdefault(
                    run_id,
                    {"run_id": run_id, "run_utc": run_dt.strftime("%Y-%m-%dT%H:%M:%SZ"), "h_states": set(), "worker_states": set()},
                )
                entry["h_states"].add(_normalize_text(run_match.group("state")).lower())
                continue

            worker_match = WORKER_STATE_RE.match(line_text)
            if worker_match:
                run_id = worker_match.group("run_id")
                run_dt = _parse_run_id_utc(run_id)
                if run_dt is None or run_dt < candidate_dt:
                    continue
                entry = run_map.setdefault(
                    run_id,
                    {"run_id": run_id, "run_utc": run_dt.strftime("%Y-%m-%dT%H:%M:%SZ"), "h_states": set(), "worker_states": set()},
                )
                entry["worker_states"].add(_normalize_text(worker_match.group("state")).lower())
                continue
    return run_map


def _parse_provenance(provenance_dir: Path, *, candidate_dt: datetime) -> Dict[str, Dict[str, Any]]:
    by_run_id: Dict[str, Dict[str, Any]] = {}
    if not provenance_dir.exists():
        return by_run_id

    for path in sorted(provenance_dir.glob("H_owner_termination_provenance.*.json")):
        match = PROVENANCE_FILE_RE.match(path.name)
        if not match:
            continue
        run_id = match.group("run_id")
        run_dt = _parse_run_id_utc(run_id)
        if run_dt is None or run_dt < candidate_dt:
            continue
        existing = by_run_id.get(run_id)
        if existing is not None and path.stat().st_mtime <= existing["mtime"]:
            continue

        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue

        command_lines: List[str] = []
        chain = payload.get("observed", {}).get("creator_chain_start", [])
        if isinstance(chain, list):
            for item in chain:
                if not isinstance(item, dict):
                    continue
                node = item.get("node", {})
                if not isinstance(node, dict):
                    continue
                cmd = _normalize_text(node.get("command_line", ""))
                if cmd:
                    command_lines.append(cmd)

        normalized_cmds = [cmd.lower() for cmd in command_lines]
        scheduler_owned = not any("--run-once" in cmd for cmd in normalized_cmds)
        owner_chain_valid = (
            any("run_h_cycle.bat" in cmd for cmd in normalized_cmds)
            and any("run_h_pricing_cycle_guarded.py" in cmd for cmd in normalized_cmds)
            and any("run_h_pricing_cycle.py" in cmd for cmd in normalized_cmds)
        )

        by_run_id[run_id] = {
            "run_id": run_id,
            "scheduler_owned": scheduler_owned,
            "owner_chain_valid": owner_chain_valid,
            "command_lines": command_lines,
            "source_file": str(path),
            "mtime": path.stat().st_mtime,
        }

    for record in by_run_id.values():
        record.pop("mtime", None)
    return by_run_id


def _build_run_records(
    run_state_map: Mapping[str, Dict[str, Any]],
    provenance_map: Mapping[str, Dict[str, Any]],
) -> Dict[str, Any]:
    run_ids = sorted(set(run_state_map.keys()) | set(provenance_map.keys()))
    records: List[Dict[str, Any]] = []
    for run_id in run_ids:
        from_log = run_state_map.get(run_id, {})
        h_states = set(from_log.get("h_states", set()))
        worker_states = set(from_log.get("worker_states", set()))

        finalized_seen = "finalized" in h_states
        failed_seen = "failed" in h_states
        succeeded_seen = "succeeded" in worker_states
        worker_failed_seen = "failed" in worker_states
        terminal_status = "incomplete"
        if finalized_seen and succeeded_seen:
            terminal_status = "succeeded"
        elif failed_seen or worker_failed_seen:
            terminal_status = "failed"
        elif finalized_seen:
            terminal_status = "finalized_without_success_marker"

        provenance = provenance_map.get(run_id, {})
        record = {
            "run_id": run_id,
            "run_utc": from_log.get("run_utc", _parse_run_id_utc(run_id).strftime("%Y-%m-%dT%H:%M:%SZ")),
            "terminal_status": terminal_status,
            "finalized_seen": finalized_seen,
            "worker_succeeded_seen": succeeded_seen,
            "scheduler_owned": provenance.get("scheduler_owned", False),
            "owner_chain_valid": provenance.get("owner_chain_valid", False),
            "source_file": provenance.get("source_file", ""),
        }
        records.append(record)

    scheduler_records = [row for row in records if row.get("scheduler_owned") is True]
    streak = 0
    max_streak = 0
    tail_streak = 0
    for row in scheduler_records:
        if row["terminal_status"] == "succeeded":
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    for row in reversed(scheduler_records):
        if row["terminal_status"] == "succeeded":
            tail_streak += 1
        else:
            break

    return {
        "all_runs": records,
        "scheduler_runs": scheduler_records,
        "scheduler_owned_runs_count": len(scheduler_records),
        "scheduler_owned_succeeded_count": sum(1 for row in scheduler_records if row["terminal_status"] == "succeeded"),
        "scheduler_owned_consecutive_success_max": max_streak,
        "scheduler_owned_consecutive_success_tail": tail_streak,
        "ten_scheduler_success_chain_met": max_streak >= 10,
        "latest_ten_scheduler_runs": scheduler_records[-10:],
    }


def _summarize_live_alerts(rows: Sequence[Mapping[str, str]]) -> Dict[str, Any]:
    alerts: Dict[str, Dict[str, str]] = {}
    snapshot_utc = ""
    run_id = ""
    for row in rows:
        key = _normalize_text(row.get("alert_key", ""))
        if key == "":
            continue
        snapshot_utc = _normalize_text(row.get("snapshot_utc", "")) or snapshot_utc
        run_id = _normalize_text(row.get("run_id", "")) or run_id
        alerts[key] = {
            "status": _normalize_text(row.get("status", "")).lower(),
            "current_value": _normalize_text(row.get("current_value", "")),
            "previous_value": _normalize_text(row.get("previous_value", "")),
            "threshold": _normalize_text(row.get("threshold", "")),
            "notes": _normalize_text(row.get("notes", "")),
        }
    non_ok = {key: value for key, value in alerts.items() if value.get("status") not in {"ok"}}
    return {
        "snapshot_utc": snapshot_utc,
        "run_id": run_id,
        "alerts": alerts,
        "non_ok_alerts": non_ok,
        "all_ok": len(non_ok) == 0 and len(alerts) > 0,
    }


def _gate(pass_value: bool, value: Any, threshold: str, detail: str = "") -> Dict[str, Any]:
    return {"pass": bool(pass_value), "value": value, "threshold": threshold, "detail": detail}


def _build_summary_rows(payload: Mapping[str, Any]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    rows.append(
        {
            "section": "meta",
            "metric": "candidate_timestamp_utc",
            "value": _normalize_text(payload.get("candidate_timestamp_utc", "")),
            "threshold": "",
            "pass": "",
            "notes": "",
        }
    )
    rows.append(
        {
            "section": "meta",
            "metric": "denominator_contract",
            "value": _normalize_text(payload.get("denominator_contract", "")),
            "threshold": "",
            "pass": "",
            "notes": "",
        }
    )

    gates = payload.get("gates", {})
    if isinstance(gates, dict):
        for key in sorted(gates.keys()):
            gate = gates[key]
            rows.append(
                {
                    "section": "gate",
                    "metric": key,
                    "value": _normalize_text(gate.get("value", "")),
                    "threshold": _normalize_text(gate.get("threshold", "")),
                    "pass": "1" if bool(gate.get("pass")) else "0",
                    "notes": _normalize_text(gate.get("detail", "")),
                }
            )

    metrics = payload.get("metrics", {})
    if isinstance(metrics, dict):
        for metric_key in [
            "rows_since_candidate",
            "same_target_rows",
            "same_target_applied",
            "raw_legacy_multi_seller_population",
            "effective_chaseable_multi_seller_population",
            "multi_seller_denominator_used",
            "multi_seller_success_per_100",
            "multi_seller_expired_aborted_share_pct",
            "suppression_rows",
            "suppression_success_rows",
            "suppression_expired_share_pct",
            "controlled_exit_rows",
            "controlled_exit_success_rows",
        ]:
            if metric_key not in metrics:
                continue
            rows.append(
                {
                    "section": "metric",
                    "metric": metric_key,
                    "value": _normalize_text(metrics.get(metric_key, "")),
                    "threshold": "",
                    "pass": "",
                    "notes": "",
                }
            )

    run_chain = payload.get("run_chain", {})
    if isinstance(run_chain, dict):
        run_rows = run_chain.get("all_runs", [])
        if isinstance(run_rows, list):
            for record in run_rows:
                rows.append(
                    {
                        "section": "run",
                        "metric": _normalize_text(record.get("run_id", "")),
                        "value": _normalize_text(record.get("terminal_status", "")),
                        "threshold": "scheduler_owned_succeeded",
                        "pass": "1" if bool(record.get("scheduler_owned")) and _normalize_text(record.get("terminal_status", "")) == "succeeded" else "0",
                        "notes": (
                            f"scheduler_owned={1 if bool(record.get('scheduler_owned')) else 0};"
                            f"owner_chain_valid={1 if bool(record.get('owner_chain_valid')) else 0};"
                            f"finalized_seen={1 if bool(record.get('finalized_seen')) else 0};"
                            f"worker_succeeded_seen={1 if bool(record.get('worker_succeeded_seen')) else 0}"
                        ),
                    }
                )
    return rows


def build_h_signoff_proof_pack(
    *,
    candidate_ts_utc: str = DEFAULT_CANDIDATE_TS_UTC,
    denominator_contract: str = DEFAULT_DENOMINATOR_CONTRACT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    outcome_log_path: Path = DEFAULT_OUTCOME_LOG_PATH,
    outcome_daily_path: Path = DEFAULT_OUTCOME_DAILY_PATH,
    checklist_path: Path = DEFAULT_CHECKLIST_PATH,
    health_status_path: Path = DEFAULT_HEALTH_STATUS_PATH,
    h_cycle_log_path: Path = DEFAULT_H_CYCLE_LOG_PATH,
    provenance_dir: Path = DEFAULT_PROVENANCE_DIR,
    live_alert_path: Path = DEFAULT_LIVE_ALERT_PATH,
    observed_utc: str | None = None,
) -> ProofPackResult:
    if denominator_contract not in {"raw_legacy_population", "effective_chaseable_population"}:
        raise ValueError(f"unsupported denominator_contract: {denominator_contract}")

    candidate_dt = _parse_iso_utc(candidate_ts_utc)
    if candidate_dt is None:
        raise ValueError(f"invalid candidate timestamp: {candidate_ts_utc}")
    observed = observed_utc or _utc_now_iso()
    observed_dt = _parse_iso_utc(observed)
    if observed_dt is None:
        raise ValueError(f"invalid observed timestamp: {observed}")
    observed = observed_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    outcome_rows = _read_csv_rows(outcome_log_path)
    outcome_daily_rows = _read_csv_rows(outcome_daily_path)
    checklist_rows = _read_csv_rows(checklist_path)
    health_rows = _read_csv_rows(health_status_path)
    live_alert_rows = _read_csv_rows(live_alert_path)

    outcome = _summarize_outcomes(outcome_rows, candidate_dt=candidate_dt)
    daily = _summarize_daily(outcome_daily_rows, candidate_dt=candidate_dt)
    health = _summarize_health(checklist_rows, health_rows, candidate_dt=candidate_dt)
    run_state_map = _parse_run_states_from_log(h_cycle_log_path, candidate_dt=candidate_dt)
    provenance = _parse_provenance(provenance_dir, candidate_dt=candidate_dt)
    run_chain = _build_run_records(run_state_map, provenance)
    live_alerts = _summarize_live_alerts(live_alert_rows)

    if denominator_contract == "raw_legacy_population":
        denominator_used = int(outcome["raw_legacy_multi_seller_population"])
    else:
        denominator_used = int(outcome["effective_chaseable_multi_seller_population"])

    multi_success = int(outcome["multi_seller"]["success"])
    multi_expired_aborted = int(outcome["multi_seller"]["expired"]) + int(outcome["multi_seller"]["aborted"])
    multi_success_per_100 = round(_percent(multi_success, denominator_used), 2)
    multi_expired_aborted_share_pct = round(_percent(multi_expired_aborted, denominator_used), 2)

    suppression_rows = int(outcome["suppression_reactivation"]["rows"])
    suppression_success = int(outcome["suppression_reactivation"]["success"])
    suppression_expired = int(outcome["suppression_reactivation"]["expired"])
    suppression_expired_share_pct = round(_percent(suppression_expired, suppression_rows), 2)

    controlled_rows = int(outcome["controlled_exit"]["rows"])
    controlled_success = int(outcome["controlled_exit"]["success"])

    gates = {
        "health_snapshot_newer_than_candidate": _gate(
            health["latest_health"]["newer_than_candidate"],
            health["latest_health"]["timestamp_utc"],
            f">{candidate_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            f"status={health['latest_health']['status']}; fail={health['latest_health']['fail_count']}; warn={health['latest_health']['warn_count']}",
        ),
        "h_ceiling_effective_floor_integrity_ok_zero": _gate(
            health["integrity_check"]["pass"],
            f"status={health['integrity_check']['status']}; value={health['integrity_check']['value']}",
            "status=ok and value=0",
        ),
        "ten_scheduler_owned_runs_succeeded": _gate(
            run_chain["ten_scheduler_success_chain_met"],
            run_chain["scheduler_owned_consecutive_success_max"],
            ">=10 consecutive scheduler-owned succeeded runs",
            f"scheduler_owned_runs={run_chain['scheduler_owned_runs_count']}; scheduler_owned_succeeded={run_chain['scheduler_owned_succeeded_count']}",
        ),
        "same_target_applied_zero": _gate(
            int(outcome["same_target_applied"]) == 0,
            int(outcome["same_target_applied"]),
            "==0",
            f"same_target_rows={outcome['same_target_rows']}",
        ),
        "multi_seller_threshold_on_chosen_contract": _gate(
            denominator_used >= 150 and multi_success_per_100 >= 2.0 and multi_expired_aborted_share_pct <= 95.0,
            f"denominator={denominator_used}; success_per_100={multi_success_per_100}; expired_aborted_share_pct={multi_expired_aborted_share_pct}",
            "denominator>=150 and success_per_100>=2.0 and expired_aborted_share_pct<=95.0",
        ),
        "suppression_threshold": _gate(
            suppression_rows >= 30 and suppression_success >= 2 and suppression_expired_share_pct <= 55.0,
            f"rows={suppression_rows}; success={suppression_success}; expired_share_pct={suppression_expired_share_pct}",
            "rows>=30 and success>=2 and expired_share_pct<=55.0",
        ),
        "controlled_exit_threshold": _gate(
            controlled_rows >= 10 and controlled_success >= 1,
            f"rows={controlled_rows}; success={controlled_success}",
            "rows>=10 and success>=1",
        ),
        "live_seller_detail_alerts_green": _gate(
            live_alerts["all_ok"],
            len(live_alerts["non_ok_alerts"]),
            "0 non-ok alerts",
            f"snapshot_utc={live_alerts['snapshot_utc']}",
        ),
    }
    overall_ready_to_archive = all(bool(gate["pass"]) for gate in gates.values())

    metrics = {
        "rows_since_candidate": int(outcome["rows_since_candidate"]),
        "same_target_rows": int(outcome["same_target_rows"]),
        "same_target_applied": int(outcome["same_target_applied"]),
        "raw_legacy_multi_seller_population": int(outcome["raw_legacy_multi_seller_population"]),
        "effective_chaseable_multi_seller_population": int(outcome["effective_chaseable_multi_seller_population"]),
        "reclassified_non_action_hold_rows": int(outcome["reclassified_non_action_hold_rows"]),
        "multi_seller_denominator_used": denominator_used,
        "multi_seller_success_per_100": multi_success_per_100,
        "multi_seller_expired_aborted_share_pct": multi_expired_aborted_share_pct,
        "suppression_rows": suppression_rows,
        "suppression_success_rows": suppression_success,
        "suppression_expired_share_pct": suppression_expired_share_pct,
        "controlled_exit_rows": controlled_rows,
        "controlled_exit_success_rows": controlled_success,
        "scenario_counts": outcome["scenario_counts"],
        "daily_candidate_date": daily,
    }

    payload: Dict[str, Any] = {
        "generated_utc": observed,
        "candidate_timestamp_utc": candidate_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "denominator_contract": denominator_contract,
        "inputs": {
            "outcome_log_path": str(outcome_log_path),
            "outcome_daily_path": str(outcome_daily_path),
            "checklist_path": str(checklist_path),
            "health_status_path": str(health_status_path),
            "h_cycle_log_path": str(h_cycle_log_path),
            "provenance_dir": str(provenance_dir),
            "live_alert_path": str(live_alert_path),
        },
        "health": health,
        "metrics": metrics,
        "run_chain": run_chain,
        "live_alerts": live_alerts,
        "gates": gates,
        "overall_ready_to_archive": overall_ready_to_archive,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    slug = _to_timestamp_slug(observed)
    json_path = output_dir / f"h_signoff_proof_pack_{slug}.json"
    csv_path = output_dir / f"h_signoff_proof_pack_{slug}.csv"
    latest_json_path = output_dir / "h_signoff_proof_pack_latest.json"
    latest_csv_path = output_dir / "h_signoff_proof_pack_latest.csv"

    json_text = json.dumps(payload, indent=2, ensure_ascii=True)
    json_path.write_text(json_text, encoding="utf-8")
    latest_json_path.write_text(json_text, encoding="utf-8")

    summary_rows = _build_summary_rows(payload)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["section", "metric", "value", "threshold", "pass", "notes"])
        writer.writeheader()
        writer.writerows(summary_rows)
    with latest_csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["section", "metric", "value", "threshold", "pass", "notes"])
        writer.writeheader()
        writer.writerows(summary_rows)

    return ProofPackResult(
        payload=payload,
        json_path=json_path,
        csv_path=csv_path,
        latest_json_path=latest_json_path,
        latest_csv_path=latest_csv_path,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build H sign-off proof pack from live/runtime artifacts.")
    parser.add_argument("--candidate-ts-utc", default=DEFAULT_CANDIDATE_TS_UTC)
    parser.add_argument(
        "--denominator-contract",
        default=DEFAULT_DENOMINATOR_CONTRACT,
        choices=["raw_legacy_population", "effective_chaseable_population"],
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--outcome-log-path", default=str(DEFAULT_OUTCOME_LOG_PATH))
    parser.add_argument("--outcome-daily-path", default=str(DEFAULT_OUTCOME_DAILY_PATH))
    parser.add_argument("--checklist-path", default=str(DEFAULT_CHECKLIST_PATH))
    parser.add_argument("--health-status-path", default=str(DEFAULT_HEALTH_STATUS_PATH))
    parser.add_argument("--h-cycle-log-path", default=str(DEFAULT_H_CYCLE_LOG_PATH))
    parser.add_argument("--provenance-dir", default=str(DEFAULT_PROVENANCE_DIR))
    parser.add_argument("--live-alert-path", default=str(DEFAULT_LIVE_ALERT_PATH))
    parser.add_argument("--observed-utc", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = build_h_signoff_proof_pack(
        candidate_ts_utc=args.candidate_ts_utc,
        denominator_contract=args.denominator_contract,
        output_dir=Path(args.output_dir),
        outcome_log_path=Path(args.outcome_log_path),
        outcome_daily_path=Path(args.outcome_daily_path),
        checklist_path=Path(args.checklist_path),
        health_status_path=Path(args.health_status_path),
        h_cycle_log_path=Path(args.h_cycle_log_path),
        provenance_dir=Path(args.provenance_dir),
        live_alert_path=Path(args.live_alert_path),
        observed_utc=args.observed_utc,
    )
    print(
        json.dumps(
            {
                "status": "success",
                "ready_to_archive": bool(result.payload.get("overall_ready_to_archive", False)),
                "candidate_timestamp_utc": result.payload.get("candidate_timestamp_utc", ""),
                "denominator_contract": result.payload.get("denominator_contract", ""),
                "output_json": str(result.json_path),
                "output_csv": str(result.csv_path),
                "latest_json": str(result.latest_json_path),
                "latest_csv": str(result.latest_csv_path),
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
