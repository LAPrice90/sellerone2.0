from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import get_manager_paths
from scripts.flows.F.price_list_manager._schemas import MANAGER_HEALTH_COLUMNS, REVIEW_HANDOFF_MANIFEST_COLUMNS


FPM_PRODUCTION_LINE_EXECUTION_MODE_ENV = "FPM_PRODUCTION_LINE_EXECUTION_MODE"
FPM_PRODUCTION_LINE_ROUTING_MODE_ENV = "FPM_PRODUCTION_LINE_ROUTING_MODE"
FPM_PRODUCTION_LINE_ENABLED_ENV = "FPM_PRODUCTION_LINE_ENABLED"
SPLIT_ROLLOUT_READINESS_COLUMNS = MANAGER_HEALTH_COLUMNS


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_any_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _int_value(value: object) -> int:
    raw = normalize_text(value)
    if raw == "":
        return 0
    try:
        return int(float(raw))
    except ValueError:
        return 0


def _env_value(name: str, default: str) -> str:
    return normalize_text(os.environ.get(name, "")) or default


def _production_line_enabled() -> bool:
    raw = _env_value(FPM_PRODUCTION_LINE_ENABLED_ENV, "true").lower()
    return raw not in {"0", "false", "no", "off", "disabled"}


def _latest_health_row(path: Path, check: str) -> dict[str, str]:
    df = _read_any_csv(path)
    if df.empty or "check" not in df.columns:
        return {}
    matches = df[df["check"].map(normalize_text).eq(check)].copy()
    if matches.empty:
        return {}
    if "observed_utc" in matches.columns:
        matches["_sort"] = matches["observed_utc"].map(normalize_text)
        matches = matches.sort_values("_sort", kind="stable")
    return {column: normalize_text(value) for column, value in matches.iloc[-1].to_dict().items()}


def _row(
    *,
    observed_utc: str,
    check: str,
    status: str,
    value: object,
    notes: str,
    source_path: Path,
) -> dict[str, str]:
    return {
        "check": check,
        "status": status,
        "value": str(value),
        "notes": notes,
        "observed_utc": observed_utc,
        "source_path": str(source_path),
    }


def _read_lock_pid(lock_path: Path) -> str:
    if not lock_path.exists():
        return ""
    raw = lock_path.read_text(encoding="utf-8", errors="ignore")
    for part in raw.replace("\n", "|").split("|"):
        if part.startswith("pid="):
            return normalize_text(part.split("=", 1)[1])
    return ""


def _live_owner_row(*, root_path: Path, live_dir: Path, observed: str, readiness_path: Path) -> dict[str, str]:
    lock_pid = _read_lock_pid(live_dir / "live_cycle.lock")
    status_df = _read_any_csv(live_dir / "live_cycle_status.csv")
    owner_pid = ""
    state = ""
    if not status_df.empty:
        row = status_df.iloc[-1].to_dict()
        owner_pid = normalize_text(row.get("owner_pid", ""))
        state = normalize_text(row.get("state", ""))
    if lock_pid and owner_pid and lock_pid == owner_pid and state:
        status = "ok"
        value = "single_owner_marker"
    elif not lock_pid and not owner_pid:
        status = "warn"
        value = "missing_owner_markers"
    else:
        status = "fail"
        value = "owner_marker_mismatch"
    return _row(
        observed_utc=observed,
        check="f_split_rollout_live_owner_marker",
        status=status,
        value=value,
        notes=f"lock_pid={lock_pid};status_owner_pid={owner_pid};state={state}",
        source_path=readiness_path,
    )


def _storage_drift_row(*, root_path: Path, live_dir: Path, observed: str, readiness_path: Path) -> dict[str, str]:
    path = live_dir / "storage_drift_report.csv"
    df = _read_any_csv(path)
    if df.empty:
        return _row(
            observed_utc=observed,
            check="f_split_rollout_storage_drift",
            status="warn",
            value="missing_report",
            notes="Storage drift report is missing, so capped split rollout should wait for a fresh drift proof.",
            source_path=readiness_path,
        )
    drift_rows = 0
    blocked_rows = 0
    for _, record in df.iterrows():
        status_after = normalize_text(record.get("status_after", ""))
        row_delta_after = _int_value(record.get("row_delta_after", 0))
        if status_after and status_after != "ok":
            blocked_rows += 1
        if row_delta_after:
            drift_rows += abs(row_delta_after)
    status = "fail" if drift_rows or blocked_rows else "ok"
    value = "blocked" if status == "fail" else "ok"
    return _row(
        observed_utc=observed,
        check="f_split_rollout_storage_drift",
        status=status,
        value=value,
        notes=f"checked_contracts={len(df.index)};drift_rows={drift_rows};blocked_contracts={blocked_rows}",
        source_path=readiness_path,
    )


def _environment_rows(*, observed: str, readiness_path: Path) -> list[dict[str, str]]:
    execution_mode = _env_value(FPM_PRODUCTION_LINE_EXECUTION_MODE_ENV, "legacy_full").lower()
    routing_mode = _env_value(FPM_PRODUCTION_LINE_ROUTING_MODE_ENV, "shadow").lower()
    enabled = _production_line_enabled()
    execution_status = "ok" if execution_mode == "legacy_full" else "warn"
    if execution_mode not in {"legacy_full", "split_enforced"}:
        execution_status = "fail"
    routing_status = "ok" if routing_mode in {"shadow", "off", "disabled", "0", "false", "no"} else "warn"
    if routing_mode not in {"shadow", "off", "disabled", "0", "false", "no", "enforced"}:
        routing_status = "warn"
    enabled_status = "ok" if enabled else "warn"
    return [
        _row(
            observed_utc=observed,
            check="f_split_rollout_execution_default_off",
            status=execution_status,
            value=execution_mode,
            notes=(
                "Execution is default-off when mode is legacy_full. "
                "split_enforced should be used only inside a capped proof window."
            ),
            source_path=readiness_path,
        ),
        _row(
            observed_utc=observed,
            check="f_split_rollout_routing_default_safe",
            status=routing_status,
            value=routing_mode,
            notes="Routing is default-safe when mode is shadow or off. Enforced routing is for capped proof only.",
            source_path=readiness_path,
        ),
        _row(
            observed_utc=observed,
            check="f_split_rollout_production_line_enabled",
            status=enabled_status,
            value="1" if enabled else "0",
            notes="Production-line snapshots should remain enabled for shadow evidence during default-off rollout.",
            source_path=readiness_path,
        ),
    ]


def _production_line_health_rows(*, live_dir: Path, observed: str, readiness_path: Path) -> list[dict[str, str]]:
    health_path = live_dir / "production_line_health.csv"
    stage_row = _latest_health_row(health_path, "f_production_line_stage_contract_runtime")
    routing_row = _latest_health_row(health_path, "f_production_line_routing_runtime")
    rows: list[dict[str, str]] = []
    if stage_row:
        stage_status = normalize_text(stage_row.get("status", "")) or "warn"
        rows.append(
            _row(
                observed_utc=observed,
                check="f_split_rollout_latest_stage_contract",
                status=stage_status if stage_status in {"ok", "fail"} else "warn",
                value=normalize_text(stage_row.get("value", "")),
                notes=normalize_text(stage_row.get("notes", "")),
                source_path=readiness_path,
            )
        )
    else:
        rows.append(
            _row(
                observed_utc=observed,
                check="f_split_rollout_latest_stage_contract",
                status="warn",
                value="missing",
                notes="No production-line stage health row exists yet.",
                source_path=readiness_path,
            )
        )
    if routing_row:
        routing_status = normalize_text(routing_row.get("status", "")) or "warn"
        rows.append(
            _row(
                observed_utc=observed,
                check="f_split_rollout_latest_routing_health",
                status="ok" if routing_status == "ok" else "warn",
                value=normalize_text(routing_row.get("value", "")),
                notes=normalize_text(routing_row.get("notes", "")),
                source_path=readiness_path,
            )
        )
    else:
        rows.append(
            _row(
                observed_utc=observed,
                check="f_split_rollout_latest_routing_health",
                status="warn",
                value="missing",
                notes="No routing health row exists yet; run capped proof only after a completed browser route exists.",
                source_path=readiness_path,
            )
        )
    return rows


def _manifest_paths(root_path: Path) -> list[Path]:
    base = root_path / "out" / "systems" / "F" / "price_list_manager"
    paths: list[Path] = [base / "live" / "review_handoff_manifest.csv"]
    handoff_root = base / "review_handoffs"
    if handoff_root.exists():
        paths.extend(handoff_root.glob("*/*/manifest.csv"))
    seen: set[str] = set()
    out: list[Path] = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        if path.exists():
            out.append(path)
    return out


def _manifest_quality_row(*, root_path: Path, observed: str, readiness_path: Path) -> dict[str, str]:
    ready_rows = 0
    blocked_rows = 0
    checked_manifests = 0
    examples: list[str] = []
    for path in _manifest_paths(root_path):
        df = read_csv(path, REVIEW_HANDOFF_MANIFEST_COLUMNS)
        if df.empty:
            continue
        checked_manifests += 1
        for _, record in df.iterrows():
            ai_gate_status = normalize_text(record.get("ai_gate_status", "")).lower()
            operator_ready = normalize_text(record.get("operator_ready_flag", ""))
            if ai_gate_status != "passed" or operator_ready != "1":
                continue
            ready_rows += 1
            quality_status = normalize_text(record.get("ai_gate_quality_status", "")).lower()
            fail_checks = _int_value(record.get("ai_gate_quality_fail_checks", 0))
            report_path = normalize_text(record.get("ai_gate_quality_report_path", ""))
            if quality_status == "" or fail_checks != 0 or report_path == "":
                blocked_rows += 1
                if len(examples) < 3:
                    examples.append(
                        f"{normalize_text(record.get('supplier_id', ''))}/{normalize_text(record.get('run_id', ''))}"
                    )
    status = "fail" if blocked_rows else "ok"
    value = "blocked" if blocked_rows else "ok"
    notes = (
        f"checked_manifests={checked_manifests};operator_ready_rows={ready_rows};"
        f"missing_or_failed_quality_rows={blocked_rows}"
    )
    if examples:
        notes = f"{notes};examples={';'.join(examples)}"
    return _row(
        observed_utc=observed,
        check="f_split_rollout_manifest_quality_gate",
        status=status,
        value=value,
        notes=notes,
        source_path=readiness_path,
    )


def _latest_speed_ledger_row(*, root_path: Path, observed: str, readiness_path: Path) -> dict[str, str]:
    base = root_path / "out" / "systems" / "F" / "price_list_manager" / "pipeline_runs"
    ledgers = sorted(base.glob("*/*/production_line_speed_ledger.csv")) if base.exists() else []
    if not ledgers:
        return _row(
            observed_utc=observed,
            check="f_split_rollout_speed_ledger",
            status="warn",
            value="missing",
            notes="No production-line speed ledger exists yet.",
            source_path=readiness_path,
        )
    latest = max(ledgers, key=lambda path: path.stat().st_mtime)
    df = _read_any_csv(latest)
    required = {
        "api_rows_checked",
        "api_stopped_rows",
        "retry_rows",
        "browser_ready_rows",
        "browser_rows_attempted",
        "api_429_count",
        "endpoint_calls",
    }
    missing = sorted(required - set(df.columns))
    status = "fail" if missing else "ok"
    value = "blocked" if missing else "ok"
    notes = f"latest_speed_ledger={latest};rows={len(df.index)}"
    if missing:
        notes = f"{notes};missing_columns={','.join(missing)}"
    return _row(
        observed_utc=observed,
        check="f_split_rollout_speed_ledger",
        status=status,
        value=value,
        notes=notes,
        source_path=readiness_path,
    )


def build_split_rollout_readiness(
    *,
    root: Path | None = None,
    observed_utc: str | None = None,
    emit_json: bool = True,
) -> dict[str, object]:
    paths = get_manager_paths(root=root)
    root_path = paths.root
    live_dir = paths.system_dir / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    observed = observed_utc or _utc_now_iso()
    readiness_path = live_dir / "split_rollout_readiness.csv"
    production_health_path = live_dir / "production_line_health.csv"

    rows: list[dict[str, str]] = []
    rows.extend(_environment_rows(observed=observed, readiness_path=readiness_path))
    rows.append(_live_owner_row(root_path=root_path, live_dir=live_dir, observed=observed, readiness_path=readiness_path))
    rows.append(_storage_drift_row(root_path=root_path, live_dir=live_dir, observed=observed, readiness_path=readiness_path))
    rows.extend(_production_line_health_rows(live_dir=live_dir, observed=observed, readiness_path=readiness_path))
    rows.append(_manifest_quality_row(root_path=root_path, observed=observed, readiness_path=readiness_path))
    rows.append(_latest_speed_ledger_row(root_path=root_path, observed=observed, readiness_path=readiness_path))

    fail_checks = sum(1 for row in rows if row["status"] == "fail")
    warn_checks = sum(1 for row in rows if row["status"] == "warn")
    if fail_checks:
        overall_status = "fail"
        value = "blocked"
        notes = f"fail_checks={fail_checks};warn_checks={warn_checks};next_action=fix_failed_readiness_checks"
    else:
        overall_status = "ok"
        value = "ready_default_off"
        notes = (
            f"fail_checks=0;warn_checks={warn_checks};"
            "next_action=use_only_capped_split_enforced_proof_windows"
        )
    rows.append(
        _row(
            observed_utc=observed,
            check="f_split_rollout_readiness",
            status=overall_status,
            value=value,
            notes=notes,
            source_path=readiness_path,
        )
    )

    readiness_df = write_csv(readiness_path, pd.DataFrame(rows), SPLIT_ROLLOUT_READINESS_COLUMNS)
    existing_health = read_csv(production_health_path, MANAGER_HEALTH_COLUMNS)
    summary_row = readiness_df[readiness_df["check"].eq("f_split_rollout_readiness")].copy()
    write_csv(
        production_health_path,
        pd.concat([existing_health, summary_row], ignore_index=True),
        MANAGER_HEALTH_COLUMNS,
    )
    summary = {
        "status": overall_status,
        "fail_checks": fail_checks,
        "warn_checks": warn_checks,
        "readiness_path": str(readiness_path),
        "production_line_health_path": str(production_health_path),
        "next_action": "fix_failed_readiness_checks" if fail_checks else "capped_split_enforced_proof_window",
    }
    if emit_json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the F scanner default-off split rollout readiness report.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--observed-utc", default=None)
    args = parser.parse_args()
    root = Path(args.root) if args.root else None
    summary = build_split_rollout_readiness(root=root, observed_utc=args.observed_utc)
    return 1 if summary["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
