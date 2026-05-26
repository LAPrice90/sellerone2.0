from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_id_for_cycle(cycle: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = f"{int(time.time_ns() % 100000):05d}"
    return f"{cycle.upper()}_{stamp}_{suffix}"


def new_manifest(*, cycle: str, run_id: str, start_time: str | None = None) -> dict:
    return {
        "run_id": str(run_id).strip(),
        "cycle": str(cycle).strip().upper(),
        "start_time": start_time or utc_now_iso(),
        "end_time": "",
        "duration_seconds": 0.0,
        "configured_step_count": 0,
        "recorded_step_count": 0,
        "launched_step_count": 0,
        "completed_step_count": 0,
        "verified_step_count": 0,
        "final_state": "running",
        "steps": [],
        "health_summary": {
            "source": "",
            "status": "missing",
            "current_cycle_evidence": False,
            "fail_count": None,
            "warn_count": None,
            "ok_count": None,
            "notes": "",
        },
    }


def append_step(
    manifest: dict,
    *,
    name: str,
    script_or_function: str,
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
    rc: int = 0,
    notes: str = "",
    started_at: str | None = None,
    ended_at: str | None = None,
    launched: bool = True,
    completed: bool = True,
    outputs_verified: bool = False,
    step_status: str = "",
    verification_status: str = "",
    required_outputs: list[str] | None = None,
    optional_outputs: list[str] | None = None,
    fresh_outputs: list[str] | None = None,
    missing_outputs: list[str] | None = None,
    stale_outputs: list[str] | None = None,
    stdout_tail: str = "",
    stderr_tail: str = "",
) -> None:
    start_ts = started_at or utc_now_iso()
    end_ts = ended_at or utc_now_iso()
    duration = _duration_seconds(start_ts, end_ts)
    step = {
        "name": str(name).strip(),
        "script_or_function": str(script_or_function).strip(),
        "inputs": [str(x).strip() for x in (inputs or []) if str(x).strip()],
        "outputs": [str(x).strip() for x in (outputs or []) if str(x).strip()],
        "rc": int(rc),
        "notes": str(notes).strip(),
        "launched": bool(launched),
        "completed": bool(completed),
        "outputs_verified": bool(outputs_verified),
        "step_status": str(step_status).strip() or _default_step_status(
            rc=int(rc),
            launched=bool(launched),
            completed=bool(completed),
            outputs_verified=bool(outputs_verified),
        ),
        "verification_status": str(verification_status).strip(),
        "required_outputs": [str(x).strip() for x in (required_outputs or []) if str(x).strip()],
        "optional_outputs": [str(x).strip() for x in (optional_outputs or []) if str(x).strip()],
        "fresh_outputs": [str(x).strip() for x in (fresh_outputs or []) if str(x).strip()],
        "missing_outputs": [str(x).strip() for x in (missing_outputs or []) if str(x).strip()],
        "stale_outputs": [str(x).strip() for x in (stale_outputs or []) if str(x).strip()],
        "start_time": start_ts,
        "end_time": end_ts,
        "duration_seconds": duration,
    }
    if str(stdout_tail or "").strip():
        step["stdout_tail"] = str(stdout_tail).strip()
    if str(stderr_tail or "").strip():
        step["stderr_tail"] = str(stderr_tail).strip()
    manifest.setdefault("steps", []).append(step)
    _refresh_manifest_counts(manifest)


def finalize_manifest(
    manifest: dict,
    *,
    health_checklist_path: Path | None = None,
    end_time: str | None = None,
    final_state: str | None = None,
    health_summary: dict | None = None,
) -> dict:
    end_ts = end_time or utc_now_iso()
    manifest["end_time"] = end_ts
    manifest["duration_seconds"] = _duration_seconds(str(manifest.get("start_time", "")), end_ts)
    _refresh_manifest_counts(manifest)
    if final_state is not None:
        manifest["final_state"] = str(final_state).strip() or str(manifest.get("final_state", "")).strip() or "unknown"
    else:
        manifest["final_state"] = _derive_final_state(manifest)
    manifest["health_summary"] = (
        _normalize_health_summary(health_summary)
        if health_summary is not None
        else _health_summary(health_checklist_path)
    )
    return manifest


def write_manifest(root: Path, manifest: dict) -> Path:
    cycle = str(manifest.get("cycle", "")).strip().upper() or "UNKNOWN"
    run_id = str(manifest.get("run_id", "")).strip() or run_id_for_cycle(cycle)
    start_time = str(manifest.get("start_time", "")).strip()
    day = start_time[:10] if len(start_time) >= 10 else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = root / "out" / "manifests" / cycle / day / f"{run_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8")
    return out_path


def _duration_seconds(start_iso: str, end_iso: str) -> float:
    start_dt = _parse_iso(start_iso)
    end_dt = _parse_iso(end_iso)
    if start_dt is None or end_dt is None:
        return 0.0
    return max((end_dt - start_dt).total_seconds(), 0.0)


def _parse_iso(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _health_summary(path: Path | None) -> dict:
    out = {
        "source": str(path) if path is not None else "",
        "status": "missing",
        "current_cycle_evidence": False,
        "fail_count": None,
        "warn_count": None,
        "ok_count": None,
        "notes": "",
    }
    if path is None or not path.exists():
        return out
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        out["status"] = "invalid"
        out["notes"] = "checklist_read_error"
        return out
    if "status" not in df.columns:
        out["status"] = "invalid"
        out["notes"] = "missing_status_column"
        return out
    status = df["status"].astype(str).str.lower()
    out["status"] = "current"
    out["current_cycle_evidence"] = True
    out["fail_count"] = int(status.eq("fail").sum())
    out["warn_count"] = int(status.eq("warn").sum())
    out["ok_count"] = int(status.eq("ok").sum())
    return out


def _default_step_status(*, rc: int, launched: bool, completed: bool, outputs_verified: bool) -> str:
    if not launched:
        return "not_launched"
    if not completed:
        return "interrupted"
    if rc != 0:
        return "failed"
    if outputs_verified:
        return "completed"
    return "completed_unverified"


def _refresh_manifest_counts(manifest: dict) -> None:
    steps = manifest.get("steps", [])
    if not isinstance(steps, list):
        steps = []
    manifest["launched_step_count"] = sum(1 for step in steps if isinstance(step, dict) and bool(step.get("launched", False)))
    manifest["completed_step_count"] = sum(1 for step in steps if isinstance(step, dict) and bool(step.get("completed", False)))
    manifest["verified_step_count"] = sum(1 for step in steps if isinstance(step, dict) and bool(step.get("outputs_verified", False)))
    manifest["recorded_step_count"] = sum(1 for step in steps if isinstance(step, dict))
    configured = manifest.get("configured_step_count", 0)
    try:
        manifest["configured_step_count"] = int(configured)
    except Exception:
        manifest["configured_step_count"] = len(steps)


def _derive_final_state(manifest: dict) -> str:
    steps = manifest.get("steps", [])
    if not isinstance(steps, list):
        steps = []
    configured = int(manifest.get("configured_step_count", 0) or 0)
    recorded = int(manifest.get("recorded_step_count", 0) or 0)
    launched = int(manifest.get("launched_step_count", 0) or 0)
    completed = int(manifest.get("completed_step_count", 0) or 0)
    failed = False
    degraded = False
    for step in steps:
        if not isinstance(step, dict):
            continue
        status = str(step.get("step_status", "")).strip().lower()
        if status in {"failed", "verification_failed", "interrupted"}:
            failed = True
        elif status in {"skipped", "degraded", "warning"}:
            degraded = True
    if configured > 0 and recorded < configured:
        return "partial"
    if failed:
        return "failed"
    if degraded:
        return "degraded"
    if configured > 0 and completed >= configured:
        return "completed"
    return "running"


def _normalize_health_summary(health_summary: dict) -> dict:
    if not isinstance(health_summary, dict):
        return _health_summary(None)
    out = {
        "source": str(health_summary.get("source", "")).strip(),
        "status": str(health_summary.get("status", "")).strip() or "missing",
        "current_cycle_evidence": bool(health_summary.get("current_cycle_evidence", False)),
        "fail_count": health_summary.get("fail_count"),
        "warn_count": health_summary.get("warn_count"),
        "ok_count": health_summary.get("ok_count"),
        "notes": str(health_summary.get("notes", "")).strip(),
    }
    return out

