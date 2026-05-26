from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BOOT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT))

try:
    from scripts.core.cycle_failure_events import (
        build_failure_event_from_manifest,
        classify_failure_cause,
        upsert_cycle_failure_event,
        utc_now_iso,
    )
except ModuleNotFoundError:
    from core.cycle_failure_events import (
        build_failure_event_from_manifest,
        classify_failure_cause,
        upsert_cycle_failure_event,
        utc_now_iso,
    )


SUPPORTED_FLOWS = {"A", "B", "E", "H", "O"}


def latest_manifest_path(root: Path, flow: str) -> Path | None:
    flow_norm = str(flow or "").strip().upper()
    manifest_root = root / "out" / "manifests" / flow_norm
    if not manifest_root.exists():
        return None
    candidates = [path for path in manifest_root.glob("*/*.json") if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def manifest_path_for_run(root: Path, flow: str, run_id: str) -> Path | None:
    flow_norm = str(flow or "").strip().upper()
    run_norm = str(run_id or "").strip()
    if not run_norm or run_norm.lower() == "latest":
        return latest_manifest_path(root, flow_norm)
    manifest_root = root / "out" / "manifests" / flow_norm
    matches = list(manifest_root.glob(f"*/*{run_norm}*.json"))
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_manifest(path: Path) -> dict[str, object]:
    manifest = load_manifest(path)
    final_state = _norm(manifest.get("final_state", "")).lower()
    health = manifest.get("health_summary", {})
    if not isinstance(health, dict):
        health = {}
    issue_event = None
    has_terminal_issue = final_state in {"failed", "partial"}
    completed_with_gate_fail = bool(manifest.get("completed_with_gate_fail", False))
    if has_terminal_issue:
        issue_event = build_failure_event_from_manifest(
            manifest,
            manifest_path=path,
            health_path=_norm(health.get("source", "")),
            source_path="scripts/tools/cycle_autopsy.py",
            recovery_action="inspect manifest failed step and source artifact before rerun",
        )
    elif completed_with_gate_fail:
        issue_event = {
            "timestamp_utc": utc_now_iso(),
            "cycle": _norm(manifest.get("cycle", "")),
            "run_id": _norm(manifest.get("run_id", "")),
            "final_state": _norm(manifest.get("final_state", "")),
            "cause_code": classify_failure_cause(
                failure_code="FINALIZE_BLOCKED",
                detail=f"completed_with_gate_fail blocking_checks={','.join(manifest.get('blocking_checks', []) or [])}",
            ),
            "cause_detail": f"completed_with_gate_fail blocking_checks={','.join(manifest.get('blocking_checks', []) or [])}",
            "step_name": "flow_gate",
            "stage": "flow_gate",
            "rc": _norm(manifest.get("gate_rc", "")),
            "verification_status": _norm(manifest.get("gate_state", "")),
            "manifest_path": str(path),
            "health_path": _norm(manifest.get("gate_path", "")) or _norm(health.get("source", "")),
            "source_path": "scripts/tools/cycle_autopsy.py",
            "recovery_action": "fix the named B blocking checks before treating the completed loop as healthy",
        }

    return {
        "manifest_path": str(path),
        "cycle": _norm(manifest.get("cycle", "")),
        "run_id": _norm(manifest.get("run_id", "")),
        "start_time": _norm(manifest.get("start_time", "")),
        "end_time": _norm(manifest.get("end_time", "")),
        "final_state": _norm(manifest.get("final_state", "")),
        "recorded_step_count": manifest.get("recorded_step_count", ""),
        "configured_step_count": manifest.get("configured_step_count", ""),
        "gate_state": _norm(manifest.get("gate_state", "")),
        "completed_with_gate_fail": completed_with_gate_fail,
        "blocking_checks": manifest.get("blocking_checks", []) or [],
        "health_status": _norm(health.get("status", "")),
        "health_fail_count": health.get("fail_count", ""),
        "health_warn_count": health.get("warn_count", ""),
        "cause_code": _norm(issue_event.get("cause_code", "")) if issue_event else "",
        "cause_detail": _norm(issue_event.get("cause_detail", "")) if issue_event else "",
        "failure_event": issue_event,
    }


def run_autopsy(root: Path, flows: list[str], run_id: str, *, write_ledger: bool = False) -> dict[str, object]:
    summaries = []
    missing = []
    for flow in flows:
        path = manifest_path_for_run(root, flow, run_id)
        if path is None:
            missing.append(flow)
            continue
        summary = summarize_manifest(path)
        event = summary.get("failure_event")
        if write_ledger and isinstance(event, dict) and event.get("cause_code"):
            upsert_cycle_failure_event(event, path=root / "out" / "cycle_alerts" / "cycle_failure_events.csv")
        summaries.append(summary)
    status = "ok"
    if any(summary.get("cause_code") for summary in summaries):
        status = "issue_found"
    if missing and not summaries:
        status = "missing"
    return {
        "status": status,
        "generated_utc": utc_now_iso(),
        "root": str(root),
        "run_id": run_id,
        "flows": flows,
        "missing_flows": missing,
        "summaries": summaries,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize latest cycle manifest failure evidence.")
    parser.add_argument("--flow", default="all", help="A, B, E, H, O, or all")
    parser.add_argument("--run-id", default="latest", help="Run id substring or latest")
    parser.add_argument("--root", default=str(REPO_ROOT), help="Repo root")
    parser.add_argument("--write-ledger", action="store_true", help="Upsert detected terminal issue to failure ledger")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    flow_arg = str(args.flow or "all").strip().upper()
    flows = sorted(SUPPORTED_FLOWS) if flow_arg == "ALL" else [flow_arg]
    unknown = [flow for flow in flows if flow not in SUPPORTED_FLOWS]
    if unknown:
        print(json.dumps({"status": "error", "error": f"unsupported flow {','.join(unknown)}"}, indent=2))
        return 2
    payload = run_autopsy(Path(args.root), flows, str(args.run_id or "latest"), write_ledger=bool(args.write_ledger))
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if payload["status"] != "missing" else 1


def _norm(value: object) -> str:
    return str(value or "").strip()


if __name__ == "__main__":
    raise SystemExit(main())
