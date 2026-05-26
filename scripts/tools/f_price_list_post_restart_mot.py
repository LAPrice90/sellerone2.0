from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_PATH = ROOT / "out" / "cycle_alerts" / "f_price_list_post_restart_mot.csv"
DEFAULT_JSON_PATH = ROOT / "out" / "cycle_alerts" / "f_price_list_post_restart_mot.json"

CHECK_COLUMNS = ["check", "status", "value", "notes", "observed_utc", "source_path"]
LOGIN_MODE_INACTIVE_STATUSES = {"canceled", "cancelled", "completed", "consumed", "drained", "still_required"}


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value: object) -> datetime | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _dt_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _age_seconds(value: datetime | None, *, now: datetime) -> float | None:
    if value is None:
        return None
    return max((now - value).total_seconds(), 0.0)


def _file_mtime_utc(path: Path) -> datetime | None:
    try:
        if not path.exists():
            return None
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def _read_first_line(path: Path) -> str:
    try:
        if not path.exists():
            return ""
        return _normalize_text(path.read_text(encoding="utf-8", errors="replace").splitlines()[0])
    except Exception:
        return ""


def _parse_key_values(text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in text.replace("\r", "\n").replace("|", "\n").splitlines():
        clean = _normalize_text(part)
        if clean == "" or "=" not in clean:
            continue
        key, value = clean.split("=", 1)
        parsed[_normalize_text(key).lower().lstrip("\ufeff")] = _normalize_text(value)
    return parsed


def _read_key_value_file(path: Path) -> dict[str, str]:
    try:
        if not path.exists():
            return {}
        return _parse_key_values(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            return [{str(key): _normalize_text(value) for key, value in row.items()} for row in reader]
    except Exception:
        return []


def _latest_csv_row(path: Path) -> dict[str, str]:
    rows = _read_csv_rows(path)
    return rows[-1] if rows else {}


def _int_value(value: object) -> int:
    raw = _normalize_text(value)
    if raw == "":
        return 0
    try:
        return int(float(raw))
    except ValueError:
        return 0


def _latest_a_manifest(root: Path) -> tuple[Path | None, datetime | None]:
    manifest_root = root / "out" / "manifests" / "A"
    if not manifest_root.exists():
        return None, None
    latest_path: Path | None = None
    latest_dt: datetime | None = None
    for path in manifest_root.rglob("*.json"):
        data = _read_json(path)
        manifest_dt = (
            _parse_utc(data.get("finished_utc"))
            or _parse_utc(data.get("completed_utc"))
            or _parse_utc(data.get("ended_utc"))
            or _file_mtime_utc(path)
        )
        if manifest_dt is None:
            continue
        if latest_dt is None or manifest_dt > latest_dt:
            latest_path = path
            latest_dt = manifest_dt
    return latest_path, latest_dt


def _status_rank(status: str) -> int:
    clean = _normalize_text(status).lower()
    if clean == "fail":
        return 2
    if clean == "warn":
        return 1
    return 0


def _overall_status(rows: list[dict[str, str]]) -> str:
    rank = max((_status_rank(row.get("status", "")) for row in rows), default=0)
    if rank == 2:
        return "fail"
    if rank == 1:
        return "warn"
    return "ok"


def _row(
    *,
    check: str,
    status: str,
    value: str,
    notes: str,
    observed_utc: str,
    source_path: Path,
) -> dict[str, str]:
    return {
        "check": check,
        "status": status,
        "value": value,
        "notes": notes,
        "observed_utc": observed_utc,
        "source_path": str(source_path),
    }


def _login_request_active(request: dict[str, str], *, exists: bool) -> bool:
    if not exists:
        return False
    status = _normalize_text(request.get("status", "")).lower()
    return status not in LOGIN_MODE_INACTIVE_STATUSES


def _event_after_request(events_path: Path, requested_dt: datetime | None) -> dict[str, str]:
    latest: dict[str, str] = {}
    latest_dt: datetime | None = None
    for event in _read_csv_rows(events_path):
        if _normalize_text(event.get("event_type", "")).lower() != "login_mode_child_started":
            continue
        event_dt = _parse_utc(event.get("event_utc", ""))
        if requested_dt is not None and event_dt is not None and event_dt < requested_dt:
            continue
        if latest_dt is None or (event_dt is not None and event_dt > latest_dt):
            latest = event
            latest_dt = event_dt
    return latest


def _child_login_visible(child_state: dict[str, str], *, observed_dt: datetime, stale_seconds: int) -> bool:
    mode = _normalize_text(child_state.get("browser_mode", "")).lower()
    visibility = _normalize_text(child_state.get("browser_visibility", "")).lower()
    manager_mode = _normalize_text(child_state.get("manager_mode", "")).lower()
    heartbeat_dt = _parse_utc(child_state.get("heartbeat", ""))
    heartbeat_age = _age_seconds(heartbeat_dt, now=observed_dt)
    fresh = heartbeat_age is not None and heartbeat_age <= stale_seconds
    visible = mode == "visible" or visibility == "visible" or "login" in manager_mode
    return fresh and visible


def _drain_marker_time(path: Path) -> datetime | None:
    parsed = _read_key_value_file(path)
    return _parse_utc(parsed.get("utc", "")) or _file_mtime_utc(path)


def build_f_post_restart_mot(
    *,
    root: Path = ROOT,
    observed_utc: str | None = None,
    stale_seconds: int = 900,
) -> dict[str, Any]:
    observed = observed_utc or _utc_now_iso()
    observed_dt = _parse_utc(observed) or datetime.now(timezone.utc)
    live_dir = root / "out" / "systems" / "F" / "price_list_manager" / "live"
    restart_path = root / "out" / "locks" / "restart_control" / "restart_controller.latest.json"
    supervisor_path = live_dir / "fpm_live_supervisor_state.txt"
    status_path = live_dir / "live_cycle_status.csv"
    events_path = live_dir / "live_cycle_events.csv"
    drain_path = live_dir / "F_restart_drain.ready"
    global_maintenance_path = root / "out" / "locks" / "maintenance.requested"
    f_visible_request_path = live_dir / "f061_visible_login.requested"
    login_request_path = live_dir / "f061_login_mode.requested"
    child_status_path = live_dir / "f061_child_status.txt"

    rows: list[dict[str, str]] = []
    bad_times: list[datetime] = []

    restart = _read_json(restart_path)
    restart_finished = _parse_utc(restart.get("finished_utc", ""))
    if not restart:
        rows.append(
            _row(
                check="f_restart_controller_latest",
                status="warn",
                value="missing",
                notes="No latest controlled restart evidence was found.",
                observed_utc=observed,
                source_path=restart_path,
            )
        )
    else:
        rows.append(
            _row(
                check="f_restart_controller_latest",
                status="ok",
                value=_normalize_text(restart.get("outcome", "")) or "present",
                notes=f"started_utc={_normalize_text(restart.get('started_utc', ''))};finished_utc={_normalize_text(restart.get('finished_utc', ''))};drain_cleared={_normalize_text(restart.get('drain_cleared', ''))}",
                observed_utc=observed,
                source_path=restart_path,
            )
        )

    supervisor = _read_key_value_file(supervisor_path)
    drain_exists = drain_path.exists()
    has_pause_request = global_maintenance_path.exists() or f_visible_request_path.exists()
    supervisor_updated = _parse_utc(supervisor.get("updated_utc", "")) or _file_mtime_utc(supervisor_path)
    supervisor_age = _age_seconds(supervisor_updated, now=observed_dt)
    supervisor_state = _normalize_text(supervisor.get("state", "")).lower()
    supervisor_reason = _normalize_text(supervisor.get("reason", "")).lower()

    if not supervisor:
        rows.append(
            _row(
                check="f_supervisor_state",
                status="fail",
                value="missing",
                notes="F supervisor state is missing, so MOT cannot prove ownership resumed.",
                observed_utc=observed,
                source_path=supervisor_path,
            )
        )
        bad_times.append(_file_mtime_utc(live_dir) or observed_dt)
    elif supervisor_state == "paused" and "drain_ready" in supervisor_reason and not has_pause_request:
        rows.append(
            _row(
                check="f_supervisor_state",
                status="fail",
                value="paused_orphan_drain_ready",
                notes=f"state={supervisor_state};reason={supervisor_reason};updated_utc={_dt_iso(supervisor_updated)}",
                observed_utc=observed,
                source_path=supervisor_path,
            )
        )
        bad_times.append(supervisor_updated or observed_dt)
    elif supervisor_age is None or supervisor_age > stale_seconds:
        rows.append(
            _row(
                check="f_supervisor_state",
                status="fail",
                value="stale",
                notes=f"state={supervisor_state};reason={supervisor_reason};age_seconds={supervisor_age if supervisor_age is not None else ''}",
                observed_utc=observed,
                source_path=supervisor_path,
            )
        )
        bad_times.append(supervisor_updated or observed_dt)
    elif supervisor_state in {"ok", "restart_manager"}:
        rows.append(
            _row(
                check="f_supervisor_state",
                status="ok",
                value=supervisor_state,
                notes=f"reason={supervisor_reason};age_seconds={supervisor_age:.1f}",
                observed_utc=observed,
                source_path=supervisor_path,
            )
        )
    elif supervisor_state == "paused" and has_pause_request:
        rows.append(
            _row(
                check="f_supervisor_state",
                status="warn",
                value="paused_with_request",
                notes=f"reason={supervisor_reason};maintenance_request={global_maintenance_path.exists()};f_visible_request={f_visible_request_path.exists()}",
                observed_utc=observed,
                source_path=supervisor_path,
            )
        )
    else:
        rows.append(
            _row(
                check="f_supervisor_state",
                status="warn",
                value=supervisor_state or "unknown",
                notes=f"reason={supervisor_reason};age_seconds={supervisor_age:.1f}",
                observed_utc=observed,
                source_path=supervisor_path,
            )
        )

    if drain_exists and not has_pause_request:
        rows.append(
            _row(
                check="f_orphan_restart_drain_marker",
                status="fail",
                value="orphan",
                notes="F_restart_drain.ready exists without global maintenance or F visible-login request.",
                observed_utc=observed,
                source_path=drain_path,
            )
        )
        bad_times.append(_drain_marker_time(drain_path) or observed_dt)
    elif drain_exists:
        rows.append(
            _row(
                check="f_orphan_restart_drain_marker",
                status="warn",
                value="boundary_pause",
                notes=f"matching_request_present=1;maintenance_request={global_maintenance_path.exists()};f_visible_request={f_visible_request_path.exists()}",
                observed_utc=observed,
                source_path=drain_path,
            )
        )
    else:
        rows.append(
            _row(
                check="f_orphan_restart_drain_marker",
                status="ok",
                value="absent",
                notes="No restart drain marker is present.",
                observed_utc=observed,
                source_path=drain_path,
            )
        )

    latest_status = _latest_csv_row(status_path)
    pending_rows = _int_value(latest_status.get("pending_rows", "0"))
    live_state = _normalize_text(latest_status.get("state", "")).lower()
    drain_ready = _int_value(latest_status.get("drain_ready", "0"))
    if not latest_status:
        rows.append(
            _row(
                check="f_live_cycle_status",
                status="warn",
                value="missing",
                notes="No live cycle status row was found.",
                observed_utc=observed,
                source_path=status_path,
            )
        )
    elif drain_ready and not has_pause_request:
        rows.append(
            _row(
                check="f_live_cycle_status",
                status="fail",
                value="orphan_drain_wait",
                notes=f"state={live_state};pending_rows={pending_rows};observed_utc={latest_status.get('observed_utc', '')}",
                observed_utc=observed,
                source_path=status_path,
            )
        )
        bad_times.append(_parse_utc(latest_status.get("observed_utc", "")) or observed_dt)
    else:
        rows.append(
            _row(
                check="f_live_cycle_status",
                status="ok",
                value=live_state or "present",
                notes=f"pending_rows={pending_rows};last_action={latest_status.get('last_action', '')};last_action_status={latest_status.get('last_action_status', '')}",
                observed_utc=observed,
                source_path=status_path,
            )
        )

    login_request = _read_key_value_file(login_request_path)
    login_active = _login_request_active(login_request, exists=login_request_path.exists())
    if not login_active:
        rows.append(
            _row(
                check="f_login_mode_child_started",
                status="ok",
                value="inactive",
                notes=f"request_status={login_request.get('status', '')}",
                observed_utc=observed,
                source_path=login_request_path,
            )
        )
    else:
        requested_dt = _parse_utc(login_request.get("requested_utc", "")) or _file_mtime_utc(login_request_path)
        child_state = _read_key_value_file(child_status_path)
        event = _event_after_request(events_path, requested_dt)
        if event:
            rows.append(
                _row(
                    check="f_login_mode_child_started",
                    status="ok",
                    value="event_after_request",
                    notes=f"request_status={login_request.get('status', '')};event_utc={event.get('event_utc', '')};rows={event.get('rows', '')}",
                    observed_utc=observed,
                    source_path=events_path,
                )
            )
        elif _child_login_visible(child_state, observed_dt=observed_dt, stale_seconds=stale_seconds):
            rows.append(
                _row(
                    check="f_login_mode_child_started",
                    status="warn",
                    value="visible_child_no_event",
                    notes=f"request_status={login_request.get('status', '')};child_heartbeat={child_state.get('heartbeat', '')};manager_mode={child_state.get('manager_mode', '')}",
                    observed_utc=observed,
                    source_path=child_status_path,
                )
            )
        else:
            rows.append(
                _row(
                    check="f_login_mode_child_started",
                    status="fail",
                    value="active_request_without_child",
                    notes=f"request_status={login_request.get('status', '')};requested_utc={_dt_iso(requested_dt)}",
                    observed_utc=observed,
                    source_path=login_request_path,
                )
            )
            bad_times.append(requested_dt or observed_dt)

    a_manifest_path, a_manifest_dt = _latest_a_manifest(root)
    active_failure = any(row.get("status") == "fail" for row in rows)
    earliest_bad = min(bad_times) if bad_times else None
    if not active_failure:
        cause_value = "no_active_issue"
        cause_status = "ok"
    elif a_manifest_dt is None:
        cause_value = "unknown_no_a_manifest"
        cause_status = "warn"
    elif earliest_bad is not None and earliest_bad < a_manifest_dt:
        cause_value = "post_restart_or_f_owner_issue"
        cause_status = "ok"
    else:
        cause_value = "post_a_handoff_issue"
        cause_status = "ok"

    rows.append(
        _row(
            check="f_failure_timing_anchor",
            status=cause_status,
            value=cause_value,
            notes=(
                f"restart_finished_utc={_dt_iso(restart_finished)};"
                f"earliest_bad_utc={_dt_iso(earliest_bad)};"
                f"latest_a_manifest_utc={_dt_iso(a_manifest_dt)}"
            ),
            observed_utc=observed,
            source_path=a_manifest_path or (root / "out" / "manifests" / "A"),
        )
    )

    overall = _overall_status(rows)
    return {
        "status": overall,
        "observed_utc": observed,
        "rows": rows,
        "row_count": len(rows),
        "warn_rows": sum(1 for row in rows if row.get("status") == "warn"),
        "fail_rows": sum(1 for row in rows if row.get("status") == "fail"),
        "cause_anchor": cause_value,
    }


def write_check_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CHECK_COLUMNS)
        writer.writeheader()
        writer.writerows([{column: _normalize_text(row.get(column, "")) for column in CHECK_COLUMNS} for row in rows])


def run_f_post_restart_mot(
    *,
    root: Path = ROOT,
    output_path: Path | None = None,
    json_path: Path | None = None,
    observed_utc: str | None = None,
    stale_seconds: int = 900,
) -> dict[str, Any]:
    out_csv = output_path or (root / "out" / "cycle_alerts" / "f_price_list_post_restart_mot.csv")
    out_json = json_path or (root / "out" / "cycle_alerts" / "f_price_list_post_restart_mot.json")
    summary = build_f_post_restart_mot(root=root, observed_utc=observed_utc, stale_seconds=stale_seconds)
    write_check_csv(out_csv, summary["rows"])
    serializable = {key: value for key, value in summary.items() if key != "rows"}
    serializable["output_path"] = str(out_csv)
    serializable["json_path"] = str(out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(serializable, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return serializable


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the F price-list post-restart MOT check.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--output-path", default="")
    parser.add_argument("--json-path", default="")
    parser.add_argument("--observed-utc", default="")
    parser.add_argument("--stale-seconds", type=int, default=900)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root)
    summary = run_f_post_restart_mot(
        root=root,
        output_path=Path(args.output_path) if _normalize_text(args.output_path) else None,
        json_path=Path(args.json_path) if _normalize_text(args.json_path) else None,
        observed_utc=_normalize_text(args.observed_utc) or None,
        stale_seconds=args.stale_seconds,
    )
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        for key, value in summary.items():
            print(f"{key}: {value}")
    return 1 if summary["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
