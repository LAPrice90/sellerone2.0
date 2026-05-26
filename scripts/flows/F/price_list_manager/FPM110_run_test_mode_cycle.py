from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager.FPM010_check_acquisition_sources import check_acquisition_sources
from scripts.flows.F.price_list_manager.FPM011_import_ready_sources import import_ready_sources
from scripts.flows.F.price_list_manager.FPM012_enrich_batch_rows_for_f061 import enrich_batch_rows_for_f061
from scripts.flows.F.price_list_manager.FPM013_download_ready_url_sources import download_ready_url_sources
from scripts.flows.F.price_list_manager.FPM014_fetch_api_sources import fetch_api_sources
from scripts.flows.F.price_list_manager.FPM016_fetch_gmail_email_sources import fetch_gmail_email_sources
from scripts.flows.F.price_list_manager.FPM020_run_placeholder_scanner import run_placeholder_scanner
from scripts.flows.F.price_list_manager.FPM030_update_memory_from_results import update_memory_from_results
from scripts.flows.F.price_list_manager.FPM040_build_next_action import build_next_action
from scripts.flows.F.price_list_manager.FPM050_build_next_action_report import build_next_action_report
from scripts.flows.F.price_list_manager.FPM060_build_status_dashboard import build_status_dashboard
from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import ensure_manager_test_mode_dir
from scripts.flows.F.price_list_manager._schemas import (
    BATCH_SCAN_ELIGIBILITY_COLUMNS,
    MANAGER_DECISION_COLUMNS,
    MANAGER_HEALTH_COLUMNS,
    PLACEHOLDER_SCANNER_RESULT_COLUMNS,
    TEST_MODE_CYCLE_RUN_COLUMNS,
    TEST_MODE_CYCLE_STEP_COLUMNS,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value: object) -> datetime:
    raw = normalize_text(value)
    if raw:
        try:
            return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _add_seconds(started_at: str, seconds: int) -> str:
    return (_parse_utc(started_at) + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _latest_decision(decisions: pd.DataFrame) -> pd.Series | None:
    if decisions.empty:
        return None
    work = decisions.copy()
    work["_decided"] = work["decided_at_utc"].map(normalize_text)
    work = work.sort_values("_decided", ascending=False, kind="stable")
    return work.iloc[0] if not work.empty else None


def _choose_scan_batch(
    *,
    test_dir: Path,
    processed_suppliers: set[str],
    minimum_rows: int,
) -> tuple[str, str, int, str]:
    decisions = read_csv(test_dir / "manager_decisions.csv", MANAGER_DECISION_COLUMNS)
    eligibility = read_csv(test_dir / "batch_scan_eligibility.csv", BATCH_SCAN_ELIGIBILITY_COLUMNS)
    latest = _latest_decision(decisions)
    if latest is not None:
        supplier_id = normalize_text(latest.get("supplier_id", ""))
        batch_id = normalize_text(latest.get("batch_id", ""))
        rows = int(float(normalize_text(latest.get("estimated_scan_rows", "0")) or "0"))
        if supplier_id and batch_id and supplier_id not in processed_suppliers and rows >= minimum_rows:
            return supplier_id, batch_id, rows, "manager_next_action"

    if eligibility.empty:
        return "", "", 0, "no_eligibility_rows"
    candidates: list[dict[str, object]] = []
    scan_rows = eligibility[eligibility["scan_decision"].map(normalize_text) == "scan"].copy()
    for batch_id, group in scan_rows.groupby("batch_id", dropna=False):
        supplier_id = normalize_text(group.iloc[0].get("supplier_id", ""))
        row_count = int(len(group.index))
        if supplier_id in processed_suppliers or row_count < minimum_rows:
            continue
        candidates.append({"supplier_id": supplier_id, "batch_id": normalize_text(batch_id), "rows": row_count})
    if not candidates:
        return "", "", 0, "no_unprocessed_supplier_with_10_rows"
    candidates = sorted(candidates, key=lambda row: (-int(row["rows"]), normalize_text(row["supplier_id"])))
    selected = candidates[0]
    return (
        normalize_text(selected["supplier_id"]),
        normalize_text(selected["batch_id"]),
        int(selected["rows"]),
        "cycle_unique_supplier_fallback",
    )


def _append_step(
    steps: list[dict[str, str]],
    *,
    cycle_id: str,
    step_index: int,
    step_name: str,
    supplier_id: str = "",
    batch_id: str = "",
    status: str,
    rows: int | str = "",
    notes: str = "",
    observed_utc: str,
) -> None:
    steps.append(
        {
            "cycle_id": cycle_id,
            "step_index": str(step_index),
            "step_name": step_name,
            "supplier_id": supplier_id,
            "batch_id": batch_id,
            "status": status,
            "rows": str(rows),
            "notes": notes,
            "observed_utc": observed_utc,
        }
    )


def _write_cycle_outputs(
    *,
    test_dir: Path,
    run_row: dict[str, str],
    step_rows: list[dict[str, str]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    runs_path = test_dir / "test_mode_cycle_runs.csv"
    steps_path = test_dir / "test_mode_cycle_steps.csv"
    existing_runs = read_csv(runs_path, TEST_MODE_CYCLE_RUN_COLUMNS)
    existing_steps = read_csv(steps_path, TEST_MODE_CYCLE_STEP_COLUMNS)
    runs = write_csv(runs_path, pd.concat([existing_runs, pd.DataFrame([run_row])], ignore_index=True), TEST_MODE_CYCLE_RUN_COLUMNS)
    steps = write_csv(steps_path, pd.concat([existing_steps, pd.DataFrame(step_rows)], ignore_index=True), TEST_MODE_CYCLE_STEP_COLUMNS)
    return runs, steps


def run_test_mode_cycle(
    root: Path | None = None,
    *,
    started_at_utc: str | None = None,
    max_iterations: int = 5,
    run_acquisition: bool = True,
    check_remote: bool = True,
    timeout_seconds: int = 60,
    allow_repeat_suppliers: bool = False,
) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=root)
    test_dir = paths.test_mode_dir
    started_at = started_at_utc or _utc_now_iso()
    cycle_id = f"fpm_test_cycle_{started_at.replace('-', '').replace(':', '')}"
    steps: list[dict[str, str]] = []
    step_index = 1
    acquisition_ready_rows = 0
    downloaded_sources = 0
    api_fetched_sources = 0
    gmail_fetched_sources = 0
    imported_batches = 0
    notes: list[str] = []

    if run_acquisition:
        try:
            acquisition = check_acquisition_sources(
                root=paths.root,
                checked_at_utc=_add_seconds(started_at, step_index),
                check_remote=check_remote,
                timeout_seconds=timeout_seconds,
            )
            acquisition_ready_rows = int(acquisition.get("ready_rows", 0) or 0)
            _append_step(
                steps,
                cycle_id=cycle_id,
                step_index=step_index,
                step_name="check_acquisition_sources",
                status="success",
                rows=acquisition_ready_rows,
                notes=f"fail_rows={acquisition.get('fail_rows', 0)};missing_rows={acquisition.get('missing_rows', 0)}",
                observed_utc=_add_seconds(started_at, step_index),
            )
        except Exception as exc:
            notes.append(f"acquisition_error={type(exc).__name__}")
            _append_step(
                steps,
                cycle_id=cycle_id,
                step_index=step_index,
                step_name="check_acquisition_sources",
                status="blocked",
                notes=type(exc).__name__,
                observed_utc=_add_seconds(started_at, step_index),
            )
        step_index += 1

        for step_name, runner, count_key, kwargs in [
            (
                "download_ready_url_sources",
                download_ready_url_sources,
                "downloaded_sources",
                {"downloaded_at_utc": _add_seconds(started_at, step_index), "timeout_seconds": timeout_seconds},
            ),
            (
                "fetch_api_sources",
                fetch_api_sources,
                "fetched_sources",
                {"fetched_at_utc": _add_seconds(started_at, step_index + 1), "timeout_seconds": timeout_seconds},
            ),
            (
                "fetch_gmail_email_sources",
                fetch_gmail_email_sources,
                "fetched_sources",
                {"fetched_at_utc": _add_seconds(started_at, step_index + 2)},
            ),
        ]:
            try:
                summary = runner(root=paths.root, **kwargs)
                count_value = int(summary.get(count_key, 0) or 0)
                if step_name == "download_ready_url_sources":
                    downloaded_sources = count_value
                elif step_name == "fetch_api_sources":
                    api_fetched_sources = count_value
                else:
                    gmail_fetched_sources = count_value
                _append_step(
                    steps,
                    cycle_id=cycle_id,
                    step_index=step_index,
                    step_name=step_name,
                    status="success",
                    rows=count_value,
                    notes=f"failed_sources={summary.get('failed_sources', 0)}",
                    observed_utc=kwargs.get("downloaded_at_utc", kwargs.get("fetched_at_utc", started_at)),
                )
            except Exception as exc:
                notes.append(f"{step_name}_error={type(exc).__name__}")
                _append_step(
                    steps,
                    cycle_id=cycle_id,
                    step_index=step_index,
                    step_name=step_name,
                    status="blocked",
                    notes=type(exc).__name__,
                    observed_utc=_add_seconds(started_at, step_index),
                )
            step_index += 1

        try:
            imported = import_ready_sources(root=paths.root, imported_at_utc=_add_seconds(started_at, step_index))
            imported_batches = int(imported.get("imported_batches", 0) or 0)
            _append_step(
                steps,
                cycle_id=cycle_id,
                step_index=step_index,
                step_name="import_ready_sources",
                status="success",
                rows=imported_batches,
                notes=f"duplicates={imported.get('duplicate_sources', 0)};stale={imported.get('stale_sources', 0)}",
                observed_utc=_add_seconds(started_at, step_index),
            )
        except Exception as exc:
            notes.append(f"import_error={type(exc).__name__}")
            _append_step(
                steps,
                cycle_id=cycle_id,
                step_index=step_index,
                step_name="import_ready_sources",
                status="blocked",
                notes=type(exc).__name__,
                observed_utc=_add_seconds(started_at, step_index),
            )
        step_index += 1

    existing_results = read_csv(test_dir / "placeholder_scanner_results.csv", PLACEHOLDER_SCANNER_RESULT_COLUMNS)
    processed_suppliers: set[str] = set()
    if not allow_repeat_suppliers and not existing_results.empty:
        processed_suppliers.update(
            normalize_text(value)
            for value in existing_results["supplier_id"].tolist()
            if normalize_text(value)
        )
        if processed_suppliers:
            notes.append(f"pre_existing_result_suppliers_skipped={','.join(sorted(processed_suppliers))}")
    scanner_iterations = 0
    result_rows = 0
    final_selected_supplier_id = ""
    status = "success"

    try:
        build_next_action(root=paths.root, observed_utc=_add_seconds(started_at, step_index))
        enrich_batch_rows_for_f061(root=paths.root, observed_utc=_add_seconds(started_at, step_index + 1))
        _append_step(
            steps,
            cycle_id=cycle_id,
            step_index=step_index,
            step_name="prepare_fake_scan_rows",
            status="success",
            rows="",
            notes="next_action_and_f061_field_enrichment_built_once",
            observed_utc=_add_seconds(started_at, step_index + 1),
        )
    except Exception as exc:
        notes.append(f"prepare_fake_scan_rows_error={type(exc).__name__}")
        _append_step(
            steps,
            cycle_id=cycle_id,
            step_index=step_index,
            step_name="prepare_fake_scan_rows",
            status="blocked",
            notes=type(exc).__name__,
            observed_utc=_add_seconds(started_at, step_index),
        )
    step_index += 2

    for iteration in range(max(0, max_iterations)):
        observed = _add_seconds(started_at, step_index)
        try:
            next_action = build_next_action(root=paths.root, observed_utc=observed)
            final_selected_supplier_id = normalize_text(next_action.get("selected_supplier_id", ""))
            supplier_id, batch_id, estimated_rows, selection_reason = _choose_scan_batch(
                test_dir=test_dir,
                processed_suppliers=processed_suppliers,
                minimum_rows=10,
            )
            if not supplier_id or not batch_id:
                _append_step(
                    steps,
                    cycle_id=cycle_id,
                    step_index=step_index,
                    step_name="select_next_fake_scan_batch",
                    status="complete",
                    rows=0,
                    notes=selection_reason,
                    observed_utc=observed,
                )
                break
            scan = run_placeholder_scanner(
                root=paths.root,
                batch_id=batch_id,
                scanned_at_utc=_add_seconds(started_at, step_index + 1),
            )
            update_memory_from_results(root=paths.root, observed_utc=_add_seconds(started_at, step_index + 2))
            build_next_action_report(root=paths.root, built_at_utc=_add_seconds(started_at, step_index + 3))
            build_status_dashboard(root=paths.root, built_at_utc=_add_seconds(started_at, step_index + 4))
            processed_suppliers.add(supplier_id)
            scanner_iterations += 1
            result_rows += int(scan.get("result_rows", 0) or 0)
            _append_step(
                steps,
                cycle_id=cycle_id,
                step_index=step_index,
                step_name="fake_scan_supplier_batch",
                supplier_id=supplier_id,
                batch_id=batch_id,
                status="success",
                rows=scan.get("result_rows", 0),
                notes=f"estimated_rows={estimated_rows};selection={selection_reason}",
                observed_utc=observed,
            )
        except Exception as exc:
            status = "blocked"
            notes.append(f"iteration_{iteration + 1}_error={type(exc).__name__}")
            _append_step(
                steps,
                cycle_id=cycle_id,
                step_index=step_index,
                step_name="fake_scan_supplier_batch",
                status="blocked",
                rows=0,
                notes=type(exc).__name__,
                observed_utc=observed,
            )
            break
        step_index += 6

    try:
        final_report = build_next_action_report(root=paths.root, built_at_utc=_add_seconds(started_at, step_index + 1))
        final_dashboard = build_status_dashboard(root=paths.root, built_at_utc=_add_seconds(started_at, step_index + 2))
        _append_step(
            steps,
            cycle_id=cycle_id,
            step_index=step_index,
            step_name="final_dashboard",
            status="success",
            rows=final_dashboard.get("dashboard_rows", 0),
            notes=f"report_supplier={final_report.get('selected_supplier_id', '')}",
            observed_utc=_add_seconds(started_at, step_index + 2),
        )
    except Exception as exc:
        status = "blocked" if scanner_iterations == 0 else "partial"
        notes.append(f"final_dashboard_error={type(exc).__name__}")

    completed_at = _add_seconds(started_at, step_index + 3)
    run_row = {
        "cycle_id": cycle_id,
        "started_at_utc": started_at,
        "completed_at_utc": completed_at,
        "max_iterations": str(max_iterations),
        "acquisition_ready_rows": str(acquisition_ready_rows),
        "downloaded_sources": str(downloaded_sources),
        "api_fetched_sources": str(api_fetched_sources),
        "imported_batches": str(imported_batches),
        "scanner_iterations": str(scanner_iterations),
        "result_rows": str(result_rows),
        "processed_suppliers": ",".join(sorted(processed_suppliers)),
        "final_selected_supplier_id": final_selected_supplier_id,
        "status": status,
        "notes": ";".join(notes),
    }
    runs, cycle_steps = _write_cycle_outputs(test_dir=test_dir, run_row=run_row, step_rows=steps)
    health_path = test_dir / "health.csv"
    existing_health = read_csv(health_path, MANAGER_HEALTH_COLUMNS)
    expected_results = scanner_iterations * 10
    health_status = "ok"
    if status == "blocked" or result_rows != expected_results:
        health_status = "fail"
    elif scanner_iterations == 0:
        health_status = "warn"
    health_row = pd.DataFrame(
        [
            {
                "check": "test_mode_cycle_reconciliation",
                "status": health_status,
                "value": str(result_rows),
                "notes": (
                    f"scanner_iterations={scanner_iterations};expected_results={expected_results};"
                    f"processed_suppliers={run_row['processed_suppliers']};status={status}"
                ),
                "observed_utc": completed_at,
                "source_path": str(test_dir / "test_mode_cycle_runs.csv"),
            }
        ]
    )
    health = write_csv(health_path, pd.concat([existing_health, health_row], ignore_index=True), MANAGER_HEALTH_COLUMNS)
    results = read_csv(test_dir / "placeholder_scanner_results.csv", PLACEHOLDER_SCANNER_RESULT_COLUMNS)
    summary = {
        "status": status,
        "cycle_id": cycle_id,
        "scanner_iterations": scanner_iterations,
        "result_rows": result_rows,
        "total_placeholder_results": int(len(results.index)),
        "processed_suppliers": run_row["processed_suppliers"],
        "downloaded_sources": downloaded_sources,
        "api_fetched_sources": api_fetched_sources,
        "gmail_fetched_sources": gmail_fetched_sources,
        "imported_batches": imported_batches,
        "run_rows": int(len(runs.index)),
        "step_rows": int(len(cycle_steps.index)),
        "cycle_health_status": health_status,
        "health_fail_rows": int((health["status"].map(lambda value: normalize_text(value).lower()) == "fail").sum()),
        "runs_path": str(test_dir / "test_mode_cycle_runs.csv"),
        "steps_path": str(test_dir / "test_mode_cycle_steps.csv"),
    }
    print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the price-list manager test-mode acquisition and fake-scan loop.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--started-at-utc", default=None)
    parser.add_argument("--max-iterations", type=int, default=5)
    parser.add_argument("--skip-acquisition", action="store_true")
    parser.add_argument("--skip-remote-check", action="store_true")
    parser.add_argument("--allow-repeat-suppliers", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    run_test_mode_cycle(
        root=root,
        started_at_utc=args.started_at_utc,
        max_iterations=args.max_iterations,
        run_acquisition=not args.skip_acquisition,
        check_remote=not args.skip_remote_check,
        timeout_seconds=args.timeout_seconds,
        allow_repeat_suppliers=bool(args.allow_repeat_suppliers),
    )


if __name__ == "__main__":
    main()
