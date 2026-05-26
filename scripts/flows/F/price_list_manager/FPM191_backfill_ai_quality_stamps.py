from __future__ import annotations

import argparse
import json
import shutil
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

from scripts.flows.F.price_list_manager.FPM156_build_ai_gate_quality_report import build_ai_gate_quality_report
from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import get_manager_paths
from scripts.flows.F.price_list_manager._schemas import MANAGER_HEALTH_COLUMNS, REVIEW_HANDOFF_MANIFEST_COLUMNS


QUALITY_STAMP_BACKFILL_COLUMNS = [
    "observed_utc",
    "manifest_path",
    "supplier_id",
    "run_id",
    "action",
    "status",
    "operator_ready_rows",
    "updated_rows",
    "backup_path",
    "notes",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _int_value(value: object) -> int:
    raw = normalize_text(value)
    if raw == "":
        return 0
    try:
        return int(float(raw))
    except ValueError:
        return 0


def _stamp_for_path(observed_utc: str) -> str:
    return observed_utc.replace("-", "").replace(":", "").replace("Z", "Z")


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


def _quality_notes(notes: object, quality_summary: dict[str, object]) -> str:
    base_parts = [
        part
        for part in normalize_text(notes).split(";")
        if part
        and not part.startswith("quality_status=")
        and not part.startswith("quality_fail_checks=")
        and not part.startswith("quality_warn_checks=")
        and not part.startswith("quality_report_path=")
        and not part.startswith("quality_report_exception=")
    ]
    quality_bits = [
        f"quality_status={normalize_text(quality_summary.get('status', ''))}",
        f"quality_fail_checks={_int_value(quality_summary.get('fail_checks', 0))}",
        f"quality_warn_checks={_int_value(quality_summary.get('warn_checks', 0))}",
    ]
    report_path = normalize_text(quality_summary.get("report_path", ""))
    if report_path:
        quality_bits.append(f"quality_report_path={report_path}")
    return ";".join([part for part in [*base_parts, *quality_bits] if part])


def _needs_quality_stamp(row: pd.Series) -> bool:
    ai_gate_status = normalize_text(row.get("ai_gate_status", "")).lower()
    operator_ready = normalize_text(row.get("operator_ready_flag", ""))
    if ai_gate_status != "passed" or operator_ready != "1":
        return False
    quality_status = normalize_text(row.get("ai_gate_quality_status", "")).lower()
    quality_fail_checks = _int_value(row.get("ai_gate_quality_fail_checks", 0))
    quality_report_path = normalize_text(row.get("ai_gate_quality_report_path", ""))
    return quality_status == "" or quality_fail_checks != 0 or quality_report_path == ""


def _ready_row_mask(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=bool)
    return df["ai_gate_status"].map(normalize_text).str.lower().eq("passed") & df["operator_ready_flag"].map(
        normalize_text
    ).eq("1")


def _atomic_write_manifest(path: Path, df: pd.DataFrame) -> pd.DataFrame:
    finalized = df.copy()
    for column in REVIEW_HANDOFF_MANIFEST_COLUMNS:
        if column not in finalized.columns:
            finalized[column] = ""
    finalized = finalized[REVIEW_HANDOFF_MANIFEST_COLUMNS]
    for column in REVIEW_HANDOFF_MANIFEST_COLUMNS:
        finalized[column] = finalized[column].map(normalize_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp.{Path.cwd().name}.{datetime.now(timezone.utc).timestamp()}")
    finalized.to_csv(tmp_path, index=False)
    tmp_path.replace(path)
    return finalized


def _backup_manifest(path: Path, backup_dir: Path, root_path: Path) -> Path:
    try:
        relative = path.relative_to(root_path)
    except ValueError:
        relative = Path(path.name)
    target = backup_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    return target


def _write_rollout_health(
    *,
    live_dir: Path,
    observed: str,
    status: str,
    value: str,
    notes: str,
    source_path: Path,
) -> None:
    health_path = live_dir / "production_line_health.csv"
    existing = read_csv(health_path, MANAGER_HEALTH_COLUMNS)
    write_csv(
        health_path,
        pd.concat(
            [
                existing,
                pd.DataFrame(
                    [
                        {
                            "check": "f_split_rollout_manifest_quality_stamp_backfill",
                            "status": status,
                            "value": value,
                            "notes": notes,
                            "observed_utc": observed,
                            "source_path": str(source_path),
                        }
                    ]
                ),
            ],
            ignore_index=True,
        ),
        MANAGER_HEALTH_COLUMNS,
    )


def backfill_ai_quality_stamps(
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
    report_path = live_dir / "ai_quality_stamp_backfill_report.csv"
    backup_dir = root_path / "out" / "backups" / f"f_phase12_ai_quality_stamp_backfill_{_stamp_for_path(observed)}"

    quality_summary = build_ai_gate_quality_report(root=root_path, observed_utc=observed)
    quality_fail_checks = _int_value(quality_summary.get("fail_checks", 0))
    quality_warn_checks = _int_value(quality_summary.get("warn_checks", 0))
    report_rows: list[dict[str, str]] = []
    if quality_fail_checks:
        notes = (
            f"fpm156_fail_checks={quality_fail_checks};fpm156_warn_checks={quality_warn_checks};"
            "no_manifest_writes=1"
        )
        report_rows.append(
            {
                "observed_utc": observed,
                "manifest_path": "",
                "supplier_id": "",
                "run_id": "",
                "action": "blocked",
                "status": "fail",
                "operator_ready_rows": "0",
                "updated_rows": "0",
                "backup_path": "",
                "notes": notes,
            }
        )
        write_csv(report_path, pd.DataFrame(report_rows), QUALITY_STAMP_BACKFILL_COLUMNS)
        _write_rollout_health(
            live_dir=live_dir,
            observed=observed,
            status="fail",
            value="blocked",
            notes=notes,
            source_path=report_path,
        )
        summary = {
            "status": "fail",
            "updated_rows": 0,
            "checked_manifests": 0,
            "quality_fail_checks": quality_fail_checks,
            "quality_warn_checks": quality_warn_checks,
            "report_path": str(report_path),
            "backup_dir": "",
            "notes": notes,
        }
        if emit_json:
            print(json.dumps(summary, indent=2, sort_keys=True))
        return summary

    checked_manifests = 0
    updated_rows_total = 0
    operator_ready_rows_total = 0
    backup_dir_created = False
    for path in _manifest_paths(root_path):
        df = read_csv(path, REVIEW_HANDOFF_MANIFEST_COLUMNS)
        if df.empty:
            continue
        checked_manifests += 1
        ready_mask = _ready_row_mask(df)
        operator_ready_rows = int(ready_mask.sum()) if not df.empty else 0
        needs_mask = df.apply(_needs_quality_stamp, axis=1)
        updated_rows = int(needs_mask.sum())
        operator_ready_rows_total += operator_ready_rows
        backup_path = ""
        action = "skipped"
        status = "ok"
        notes = "quality_stamp_already_present"
        if updated_rows:
            if not backup_dir_created:
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup_dir_created = True
            backup_path = str(_backup_manifest(path, backup_dir, root_path))
            df.loc[needs_mask, "ai_gate_quality_status"] = normalize_text(quality_summary.get("status", ""))
            df.loc[needs_mask, "ai_gate_quality_fail_checks"] = str(quality_fail_checks)
            df.loc[needs_mask, "ai_gate_quality_warn_checks"] = str(quality_warn_checks)
            df.loc[needs_mask, "ai_gate_quality_report_path"] = normalize_text(quality_summary.get("report_path", ""))
            df.loc[needs_mask, "notes"] = df.loc[needs_mask, "notes"].map(
                lambda notes_value: _quality_notes(notes_value, quality_summary)
            )
            _atomic_write_manifest(path, df)
            updated_rows_total += updated_rows
            action = "updated"
            notes = "quality_stamp_backfilled_after_fpm156_pass"
        report_rows.append(
            {
                "observed_utc": observed,
                "manifest_path": str(path),
                "supplier_id": normalize_text(df.iloc[0].get("supplier_id", "")),
                "run_id": normalize_text(df.iloc[0].get("run_id", "")),
                "action": action,
                "status": status,
                "operator_ready_rows": str(operator_ready_rows),
                "updated_rows": str(updated_rows),
                "backup_path": backup_path,
                "notes": notes,
            }
        )

    write_csv(report_path, pd.DataFrame(report_rows), QUALITY_STAMP_BACKFILL_COLUMNS)
    notes = (
        f"checked_manifests={checked_manifests};operator_ready_rows={operator_ready_rows_total};"
        f"updated_rows={updated_rows_total};fpm156_warn_checks={quality_warn_checks}"
    )
    _write_rollout_health(
        live_dir=live_dir,
        observed=observed,
        status="ok",
        value="updated" if updated_rows_total else "no_change",
        notes=notes,
        source_path=report_path,
    )
    summary = {
        "status": "ok",
        "updated_rows": updated_rows_total,
        "checked_manifests": checked_manifests,
        "operator_ready_rows": operator_ready_rows_total,
        "quality_fail_checks": quality_fail_checks,
        "quality_warn_checks": quality_warn_checks,
        "report_path": str(report_path),
        "backup_dir": str(backup_dir) if backup_dir_created else "",
        "notes": notes,
    }
    if emit_json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill FPM156 quality stamps onto existing AI-gated review manifests.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--observed-utc", default=None)
    args = parser.parse_args()
    root = Path(args.root) if args.root else None
    summary = backfill_ai_quality_stamps(root=root, observed_utc=args.observed_utc)
    return 1 if summary["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
