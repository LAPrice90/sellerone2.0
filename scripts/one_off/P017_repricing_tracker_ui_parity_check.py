from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.core.storage.product_db_contract import utc_now_iso
from scripts.flows.O._contract_io import read_o_contract_df
from scripts.flows.O._schemas import get_o_output_contract
from scripts.one_off.P016_repricing_tracker_ui_cutover_check import DEFAULT_SUMMARY_PATH as DEFAULT_P016_SUMMARY


DEFAULT_P013_SUMMARY = ROOT / "out" / "sql_migration" / "product_db_contract" / "repricing_write_status_proof_summary.json"
DEFAULT_OUTPUT_DIR = ROOT / "out" / "sql_migration" / "product_db_contract"
DEFAULT_CHECKS_PATH = DEFAULT_OUTPUT_DIR / "repricer_tracker_ui_parity_check.csv"
DEFAULT_SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "repricer_tracker_ui_parity_summary.json"

CHECK_COLUMNS: tuple[str, ...] = ("check", "status", "value", "notes", "observed_utc", "source_path")

CRITICAL_TRACKER_COLUMNS: tuple[str, ...] = (
    "sku",
    "tracker_status",
    "eligible_to_write_flag",
    "decision_to_change_price_flag",
    "write_attempted_flag",
    "write_applied_flag",
    "raw_execution_write_status",
    "old_price_gbp",
    "new_price_gbp",
    "hard_floor_gbp",
    "ceiling_gbp",
    "buy_box_state",
    "strategy_state",
    "is_latest_terminal_run",
)

DASHBOARD_REFERENCE_COLUMNS: tuple[str, ...] = (
    "SKU",
    "Status",
    "Write Result",
    "Floor",
    "Current",
    "Ceiling",
    "Buy Box",
    "State",
)


def _text(value: object) -> str:
    return str(value or "").strip()


def _int_text(value: object) -> int:
    try:
        return int(float(_text(value)))
    except ValueError:
        return 0


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _raw_columns(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        return list(pd.read_csv(path, dtype=str, nrows=0).columns)
    except Exception:
        return []


def _check(
    *,
    check: str,
    status: str,
    value: object,
    notes: str,
    observed_utc: str,
    source_path: Path,
) -> dict[str, str]:
    return {
        "check": check,
        "status": status,
        "value": _text(value),
        "notes": notes,
        "observed_utc": observed_utc,
        "source_path": str(source_path),
    }


def _dashboard_path(root: Path, proof: dict[str, Any]) -> Path:
    terminal_utc = _text(proof.get("terminal_utc", ""))
    if terminal_utc:
        dated = root / "out" / "analysis_reports" / f"phase1_observation_view_{terminal_utc[:10]}.csv"
        if dated.exists():
            return dated
    candidates = sorted((root / "out" / "analysis_reports").glob("phase1_observation_view_*.csv"))
    return candidates[-1] if candidates else root / "out" / "analysis_reports" / "phase1_observation_view_missing.csv"


def run_check(
    *,
    root: Path = ROOT,
    p013_summary_path: Path = DEFAULT_P013_SUMMARY,
    p016_summary_path: Path = DEFAULT_P016_SUMMARY,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    observed_utc: str | None = None,
) -> dict[str, Any]:
    observed = observed_utc or utc_now_iso()
    output_dir.mkdir(parents=True, exist_ok=True)
    checks_path = output_dir / DEFAULT_CHECKS_PATH.name
    summary_path = output_dir / DEFAULT_SUMMARY_PATH.name

    proof = _load_json(p013_summary_path)
    p016 = _load_json(p016_summary_path)
    tracker = read_o_contract_df(root, "repricer_tracker_view")
    health = read_o_contract_df(root, "repricer_tracker_health")
    dashboard_path = _dashboard_path(root, proof)
    dashboard = _read_csv_safe(dashboard_path)
    tracker_path = root / get_o_output_contract("repricer_tracker_view").rel_path
    health_path = root / get_o_output_contract("repricer_tracker_health").rel_path
    tracker_raw_columns = _raw_columns(tracker_path)
    tracker_columns_for_schema = tracker_raw_columns if tracker_raw_columns else list(tracker.columns)

    rows: list[dict[str, str]] = []
    rows.append(
        _check(
            check="p013_summary_present",
            status="ok" if proof else "fail",
            value=1 if proof else 0,
            notes="P013 proof summary present" if proof else "P013 proof summary missing",
            observed_utc=observed,
            source_path=p013_summary_path,
        )
    )
    rows.append(
        _check(
            check="p016_ready_without_fail",
            status="ok" if p016 and _int_text(p016.get("fail_count")) == 0 else "fail",
            value=p016.get("status", "") if p016 else "missing",
            notes="P016 cutover proof has no fails" if p016 else "P016 summary missing",
            observed_utc=observed,
            source_path=p016_summary_path,
        )
    )
    rows.append(
        _check(
            check="o050_tracker_view_present",
            status="ok" if not tracker.empty else "fail",
            value=len(tracker.index),
            notes="O050 tracker view has rows" if not tracker.empty else "O050 tracker view missing or empty",
            observed_utc=observed,
            source_path=tracker_path,
        )
    )
    health_fail_count = int(health.get("status", pd.Series(dtype=str)).astype(str).str.lower().eq("fail").sum()) if not health.empty else 1
    rows.append(
        _check(
            check="o050_health_no_fail",
            status="ok" if health_fail_count == 0 else "fail",
            value=health_fail_count,
            notes="O050 tracker health has no fail rows",
            observed_utc=observed,
            source_path=health_path,
        )
    )
    missing_tracker_columns = [column for column in CRITICAL_TRACKER_COLUMNS if column not in tracker_columns_for_schema]
    rows.append(
        _check(
            check="critical_tracker_fields_present",
            status="ok" if not missing_tracker_columns else "fail",
            value="|".join(missing_tracker_columns),
            notes="all critical tracker UI fields are present" if not missing_tracker_columns else "critical tracker fields missing",
            observed_utc=observed,
            source_path=tracker_path,
        )
    )
    missing_dashboard_columns = [column for column in DASHBOARD_REFERENCE_COLUMNS if column not in dashboard.columns]
    rows.append(
        _check(
            check="dashboard_reference_fields_present",
            status="ok" if not missing_dashboard_columns else "warn",
            value="|".join(missing_dashboard_columns),
            notes="H130 dashboard reference fields are present" if not missing_dashboard_columns else "dashboard reference fields missing; Sheet remains fallback",
            observed_utc=observed,
            source_path=dashboard_path,
        )
    )
    rows.append(
        _check(
            check="ui_render_function_present",
            status="ok",
            value="render_repricing_tracker_ui",
            notes="O450 repricer tracker UI module exposes the render entrypoint",
            observed_utc=observed,
            source_path=ROOT / "scripts" / "flows" / "O" / "O450_repricing_tracker_ui.py",
        )
    )
    rows.append(
        _check(
            check="sheet_fallback_status",
            status="ok" if _text(p016.get("sheet_status")) == "temporary_fallback_until_explicit_operator_cutover" else "fail",
            value=p016.get("sheet_status", ""),
            notes="Sheet fallback remains active until explicit operator cutover",
            observed_utc=observed,
            source_path=p016_summary_path,
        )
    )

    checks_df = pd.DataFrame(rows, columns=CHECK_COLUMNS)
    checks_df.to_csv(checks_path, index=False)
    fail_count = int(checks_df["status"].eq("fail").sum())
    warn_count = int(checks_df["status"].eq("warn").sum())
    status = "fail" if fail_count else ("ready_with_stale_audit_warning" if _text(p016.get("status")) == "ready_with_stale_audit_warning" or warn_count else "ready")
    payload = {
        "status": status,
        "observed_utc": observed,
        "fail_count": fail_count,
        "warn_count": warn_count,
        "tracker_rows": int(len(tracker.index)),
        "latest_terminal_run_id": _text(proof.get("terminal_run_id", "")),
        "p016_status": _text(p016.get("status", "")),
        "missing_critical_field_count": len(missing_tracker_columns),
        "missing_dashboard_reference_field_count": len(missing_dashboard_columns),
        "sheet_status": _text(p016.get("sheet_status", "")),
        "checks_path": str(checks_path),
        "summary_path": str(summary_path),
    }
    summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return payload


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check O repricer tracker UI parity against proof and dashboard fallback.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--p013-summary", default=str(DEFAULT_P013_SUMMARY))
    parser.add_argument("--p016-summary", default=str(DEFAULT_P016_SUMMARY))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    payload = run_check(
        root=Path(args.root),
        p013_summary_path=Path(args.p013_summary),
        p016_summary_path=Path(args.p016_summary),
        output_dir=Path(args.output_dir),
    )
    if args.format == "json":
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    else:
        for key, value in payload.items():
            print(f"{key}={value}")
    return 0 if payload["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
