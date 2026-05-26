from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager.FPM155_apply_review_intelligence_gate import apply_review_intelligence_gate
from scripts.flows.F.price_list_manager._io import normalize_text, write_csv
from scripts.flows.F.price_list_manager._paths import get_manager_paths
from scripts.flows.F.price_list_manager._schemas import REVIEW_CANDIDATE_MANIFEST_COLUMNS


REPORT_COLUMNS = [
    "observed_utc",
    "supplier_id",
    "run_id",
    "status",
    "pass_rows",
    "manual_near_rows_held",
    "hard_reject_rows",
    "candidate_manifest_path",
    "raw_pass_review_path",
    "raw_near_miss_review_path",
    "backup_manifest_path",
    "ai_gate_apply_status",
    "notes",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_any_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _resolve_path(root: Path, path_text: object) -> Path:
    clean = normalize_text(path_text)
    if clean == "":
        return Path()
    path = Path(clean)
    if path.is_absolute():
        return path
    return root / path


def _first_value(row: dict[str, object], *keys: str) -> str:
    for key in keys:
        value = normalize_text(row.get(key, ""))
        if value:
            return value
    return ""


def _manifest_row(manifest_path: Path) -> dict[str, str]:
    df = _read_any_csv(manifest_path)
    if df.empty:
        return {}
    return {column: normalize_text(value) for column, value in df.iloc[0].to_dict().items()}


def _empty_near_path(run_dir: Path) -> Path:
    return run_dir / "legacy_ai_clean_pass_only_near_miss_empty.csv"


def _report_row(**values: object) -> dict[str, str]:
    return {column: normalize_text(values.get(column, "")) for column in REPORT_COLUMNS}


def build_legacy_pass_ai_candidate_queues(
    *,
    root: Path | None = None,
    observed_utc: str | None = None,
    execute: bool = False,
    apply_gate: bool = False,
    force: bool = False,
    supplier_id: str = "",
    run_id: str = "",
) -> dict[str, object]:
    paths = get_manager_paths(root=root)
    root_path = paths.root
    observed = observed_utc or _utc_now_iso()
    handoff_root = paths.system_dir / "review_handoffs"
    live_dir = paths.system_dir / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    report_path = live_dir / "legacy_pass_ai_candidate_conversion.csv"

    rows: list[dict[str, str]] = []
    manifest_paths = sorted(handoff_root.glob("*/*/manifest.csv")) if handoff_root.exists() else []
    for manifest_path in manifest_paths:
        run_dir = manifest_path.parent
        manifest = _manifest_row(manifest_path)
        selected_supplier = _first_value(manifest, "supplier_id") or run_dir.parent.name
        selected_run = _first_value(manifest, "run_id") or run_dir.name
        if supplier_id and selected_supplier != supplier_id:
            continue
        if run_id and selected_run != run_id:
            continue

        candidate_manifest_path = run_dir / "candidate_manifest.csv"
        ai_gate_status = normalize_text(manifest.get("ai_gate_status", ""))
        operator_ready_flag = normalize_text(manifest.get("operator_ready_flag", ""))
        if ai_gate_status == "passed" and operator_ready_flag == "1":
            rows.append(
                _report_row(
                    observed_utc=observed,
                    supplier_id=selected_supplier,
                    run_id=selected_run,
                    status="skipped_already_ai_gated",
                    candidate_manifest_path=candidate_manifest_path,
                    notes="Already has a passed AI-gated operator manifest.",
                )
            )
            continue
        if candidate_manifest_path.exists() and not force:
            rows.append(
                _report_row(
                    observed_utc=observed,
                    supplier_id=selected_supplier,
                    run_id=selected_run,
                    status="skipped_candidate_manifest_exists",
                    candidate_manifest_path=candidate_manifest_path,
                    notes="Candidate manifest already exists.",
                )
            )
            continue

        pass_path = _resolve_path(root_path, _first_value(manifest, "raw_pass_review_path", "pass_review_path"))
        near_path = _resolve_path(root_path, _first_value(manifest, "raw_near_miss_review_path", "near_miss_review_path"))
        summary_path = _resolve_path(root_path, _first_value(manifest, "raw_summary_path", "summary_path"))
        pass_df = _read_any_csv(pass_path)
        near_df = _read_any_csv(near_path)
        pass_rows = len(pass_df.index)
        near_rows = len(near_df.index)
        hard_reject_rows = _first_value(manifest, "hard_reject_rows") or "0"
        if pass_rows == 0:
            rows.append(
                _report_row(
                    observed_utc=observed,
                    supplier_id=selected_supplier,
                    run_id=selected_run,
                    status="skipped_no_clean_pass_rows",
                    pass_rows=pass_rows,
                    manual_near_rows_held=near_rows,
                    hard_reject_rows=hard_reject_rows,
                    raw_pass_review_path=pass_path,
                    raw_near_miss_review_path=near_path,
                    candidate_manifest_path=candidate_manifest_path,
                    notes="Legacy pack has no clean pass rows to convert.",
                )
            )
            continue
        if not pass_path.exists():
            rows.append(
                _report_row(
                    observed_utc=observed,
                    supplier_id=selected_supplier,
                    run_id=selected_run,
                    status="skipped_missing_pass_file",
                    pass_rows=pass_rows,
                    manual_near_rows_held=near_rows,
                    hard_reject_rows=hard_reject_rows,
                    raw_pass_review_path=pass_path,
                    raw_near_miss_review_path=near_path,
                    candidate_manifest_path=candidate_manifest_path,
                    notes="Legacy manifest points at a missing pass review file.",
                )
            )
            continue

        empty_near_path = _empty_near_path(run_dir)
        backup_manifest_path = run_dir / "manifest.pre_ai_legacy_backup.csv"
        ai_gate_apply_status = ""
        if execute:
            if manifest_path.exists() and not backup_manifest_path.exists():
                shutil.copy2(manifest_path, backup_manifest_path)
            pd.DataFrame(columns=list(pass_df.columns)).to_csv(empty_near_path, index=False)
            candidate_row = {
                "built_at_utc": observed,
                "supplier_id": selected_supplier,
                "supplier_name": _first_value(manifest, "supplier_name") or selected_supplier,
                "run_id": selected_run,
                "review_snapshot_id": _first_value(manifest, "review_snapshot_id"),
                "source_file_path": _first_value(manifest, "source_file_path"),
                "source_seen_at_utc": _first_value(manifest, "source_seen_at_utc"),
                "completed_at_utc": _first_value(manifest, "completed_at_utc", "built_at_utc"),
                "raw_pass_review_rows": str(pass_rows),
                "raw_near_miss_review_rows": "0",
                "hard_reject_rows": hard_reject_rows,
                "raw_pass_review_path": str(pass_path),
                "raw_near_miss_review_path": str(empty_near_path),
                "raw_summary_path": str(summary_path),
                "handoff_dir": str(run_dir),
                "operator_ready_flag": "0",
                "block_reason": "",
                "notes": f"legacy_clean_pass_only_candidate_for_ai_gate;manual_near_rows_held={near_rows}",
            }
            write_csv(candidate_manifest_path, pd.DataFrame([candidate_row]), REVIEW_CANDIDATE_MANIFEST_COLUMNS)
            if apply_gate:
                gate_summary = apply_review_intelligence_gate(
                    root=root_path,
                    supplier_id=selected_supplier,
                    run_id=selected_run,
                    observed_utc=observed,
                    force_rebuild=False,
                    emit_json=False,
                )
                ai_gate_apply_status = normalize_text(gate_summary.get("status", ""))

        rows.append(
            _report_row(
                observed_utc=observed,
                supplier_id=selected_supplier,
                run_id=selected_run,
                status="converted" if execute else "would_convert",
                pass_rows=pass_rows,
                manual_near_rows_held=near_rows,
                hard_reject_rows=hard_reject_rows,
                candidate_manifest_path=candidate_manifest_path,
                raw_pass_review_path=pass_path,
                raw_near_miss_review_path=empty_near_path if execute else near_path,
                backup_manifest_path=backup_manifest_path if execute else "",
                ai_gate_apply_status=ai_gate_apply_status,
                notes="Only old clean-pass rows are converted. Manual/near rows are held out.",
            )
        )

    report_df = pd.DataFrame(rows, columns=REPORT_COLUMNS).fillna("")
    if execute:
        report_df.to_csv(report_path, index=False)

    status_counts = report_df["status"].value_counts().to_dict() if not report_df.empty else {}
    result = {
        "observed_utc": observed,
        "execute": execute,
        "apply_gate": apply_gate,
        "report_path": str(report_path) if execute else "",
        "rows_seen": len(rows),
        "status_counts": status_counts,
        "converted_pass_rows": int(
            pd.to_numeric(
                report_df.loc[report_df["status"].isin(["converted", "would_convert"]), "pass_rows"],
                errors="coerce",
            )
            .fillna(0)
            .sum()
        )
        if not report_df.empty
        else 0,
        "manual_near_rows_held": int(
            pd.to_numeric(
                report_df.loc[report_df["status"].isin(["converted", "would_convert"]), "manual_near_rows_held"],
                errors="coerce",
            )
            .fillna(0)
            .sum()
        )
        if not report_df.empty
        else 0,
        "rows": rows,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert legacy clean-pass handoff rows into AI candidate queues.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--observed-utc", default=None)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--apply-gate", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--supplier-id", default="")
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()

    result = build_legacy_pass_ai_candidate_queues(
        root=Path(args.root) if args.root else None,
        observed_utc=args.observed_utc,
        execute=bool(args.execute),
        apply_gate=bool(args.apply_gate),
        force=bool(args.force),
        supplier_id=args.supplier_id,
        run_id=args.run_id,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
