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


DEFAULT_OUTPUT_DIR = ROOT / "out" / "sql_migration" / "product_db_contract"
DEFAULT_PLAN_DIR = ROOT / "plans" / "active" / "sql-product-db-ui-authority-phase2-2026-05-01"
DEFAULT_CHECKS_PATH = DEFAULT_OUTPUT_DIR / "sql_product_db_ui_authority_phase2_signoff.csv"
DEFAULT_SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "sql_product_db_ui_authority_phase2_signoff_summary.json"
DEFAULT_REPORT_PATH = DEFAULT_PLAN_DIR / "COMPLETION_REPORT.md"

SUMMARY_PATHS = {
    "p015_sql_authority": DEFAULT_OUTPUT_DIR / "product_db_sql_authority_rehearsal_summary.json",
    "p016_tracker_cutover": DEFAULT_OUTPUT_DIR / "repricer_tracker_ui_cutover_summary.json",
    "p017_tracker_parity": DEFAULT_OUTPUT_DIR / "repricer_tracker_ui_parity_summary.json",
    "p018_mirror_drift": DEFAULT_OUTPUT_DIR / "product_db_mirror_drift_guard_summary.json",
    "p019_reader_map": DEFAULT_OUTPUT_DIR / "product_db_reader_dependency_summary.json",
    "p020_postgres_rehearsal": DEFAULT_OUTPUT_DIR / "product_db_postgres_promotion_rehearsal_summary.json",
}

CHECK_COLUMNS: tuple[str, ...] = ("check", "status", "value", "notes", "observed_utc", "source_path")


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


def _check(check: str, status: str, value: object, notes: str, observed_utc: str, source_path: Path) -> dict[str, str]:
    return {
        "check": check,
        "status": status,
        "value": _text(value),
        "notes": notes,
        "observed_utc": observed_utc,
        "source_path": str(source_path),
    }


def _status_ok(payload: dict[str, Any], allowed: set[str]) -> bool:
    return _text(payload.get("status")) in allowed


def _write_report(report_path: Path, payload: dict[str, Any], summaries: dict[str, dict[str, Any]]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    p016 = summaries["p016_tracker_cutover"]
    p017 = summaries["p017_tracker_parity"]
    p018 = summaries["p018_mirror_drift"]
    p019 = summaries["p019_reader_map"]
    p020 = summaries["p020_postgres_rehearsal"]
    lines = [
        "# SQL Product DB UI Authority Phase 2 Completion Report",
        "",
        f"Observed UTC: {payload['observed_utc']}",
        f"Status: {payload['status']}",
        f"Fail count: {payload['fail_count']}",
        f"Warn count: {payload['warn_count']}",
        "",
        "## Evidence",
        "",
        f"- Product DB SQL rows: {summaries['p015_sql_authority'].get('sql_rows', '')}",
        f"- Product DB SQL unique seller_sku: {summaries['p015_sql_authority'].get('sql_unique_seller_sku', '')}",
        f"- O Product DB view rows: {summaries['p015_sql_authority'].get('o_view_rows', '')}",
        f"- CSV mirror rows: {summaries['p015_sql_authority'].get('csv_mirror_rows', '')}",
        f"- CSV mirror status: {p018.get('csv_mirror_authority_status', '')}",
        f"- Repricer tracker rows: {p016.get('tracker_rows', '')}",
        f"- Repricer tracker status: {p016.get('status', '')}",
        f"- Latest H terminal run: {p016.get('terminal_run_id', '')}",
        f"- Reader references mapped: {p019.get('reader_reference_rows', '')}",
        f"- Reader files mapped: {p019.get('unique_files', '')}",
        f"- Unknown Product DB reader owners: {p019.get('unknown_owner_count', '')}",
        f"- Runtime reader changes blocked without approval: {p019.get('blocked_without_approval_count', '')}",
        f"- PostgreSQL promotion status: {p020.get('promotion_status', '')}",
        "",
        "## Verification",
        "",
        f"- P021 final status: `{payload['status']}`",
        f"- P021 fail count: `{payload['fail_count']}`",
        f"- P021 warn count: `{payload['warn_count']}`",
        f"- P017 UI parity status: `{p017.get('status', '')}`",
        f"- P016 cutover status: `{p016.get('status', '')}`",
        f"- P018 mirror drift status: `{p018.get('status', '')}`",
        f"- P019 reader map status: `{p019.get('status', '')}`",
        f"- P020 offline PostgreSQL rehearsal status: `{p020.get('status', '')}`",
        "",
        "## Local Proof Outputs",
        "",
        "- `out/sql_migration/product_db_contract/repricer_tracker_ui_parity_check.csv`",
        "- `out/sql_migration/product_db_contract/repricer_tracker_ui_parity_summary.json`",
        "- `out/sql_migration/product_db_contract/product_db_mirror_drift_guard.csv`",
        "- `out/sql_migration/product_db_contract/product_db_mirror_drift_guard_summary.json`",
        "- `out/sql_migration/product_db_contract/product_db_reader_dependency_map.csv`",
        "- `out/sql_migration/product_db_contract/product_db_reader_dependency_summary.json`",
        "- `out/sql_migration/product_db_contract/product_db_postgres_promotion_rehearsal.csv`",
        "- `out/sql_migration/product_db_contract/product_db_postgres_promotion_rehearsal_summary.json`",
        "- `out/sql_migration/product_db_contract/sql_product_db_ui_authority_phase2_signoff.csv`",
        "- `out/sql_migration/product_db_contract/sql_product_db_ui_authority_phase2_signoff_summary.json`",
        "",
        "## Boundaries Honored",
        "",
        "- No Google Sheets writes were made by this sign-off bundle.",
        "- No A scripts or A015 were run by this sign-off bundle.",
        "- No B scripts or B maintenance proof were run by this sign-off bundle.",
        "- No H controlled proof or scheduler ownership changes were made by this sign-off bundle.",
        "- No Amazon listing/pricing writes were made by this sign-off bundle.",
        "- No production PostgreSQL promotion was run.",
        "",
        "## Remaining Explicit Approvals",
        "",
        "- Operator acceptance before retiring the repricer tracker Sheet.",
        "- Approval before marking the Product DB Sheet legacy/export-only.",
        "- Flow-owned proof windows before A/B/H runtime reader changes.",
        "- Production approval before PostgreSQL promotion.",
        "",
        "## Observation Decision",
        "",
        "- Use the repricer tracker UI as the main tracker for one normal operating day.",
        "- Keep the Google Sheet as fallback during observation.",
        "- Retire the Sheet only if P017 and P016 remain fail-free and no missing UI field or usability blocker is recorded.",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def run_check(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    report_path: Path = DEFAULT_REPORT_PATH,
    observed_utc: str | None = None,
) -> dict[str, Any]:
    observed = observed_utc or utc_now_iso()
    output_dir.mkdir(parents=True, exist_ok=True)
    checks_path = output_dir / DEFAULT_CHECKS_PATH.name
    summary_path = output_dir / DEFAULT_SUMMARY_PATH.name
    summaries = {name: _load_json(path) for name, path in SUMMARY_PATHS.items()}

    rows = [
        _check("p015_sql_authority_ready", "ok" if summaries["p015_sql_authority"] and _int_text(summaries["p015_sql_authority"].get("fail_count")) == 0 else "fail", summaries["p015_sql_authority"].get("status", "missing"), "SQL authority rehearsal has no fails", observed, SUMMARY_PATHS["p015_sql_authority"]),
        _check("p016_tracker_cutover_ready", "ok" if _status_ok(summaries["p016_tracker_cutover"], {"ready", "ready_with_stale_audit_warning"}) and _int_text(summaries["p016_tracker_cutover"].get("fail_count")) == 0 else "fail", summaries["p016_tracker_cutover"].get("status", "missing"), "Repricer tracker cutover proof has no fails", observed, SUMMARY_PATHS["p016_tracker_cutover"]),
        _check("p017_tracker_parity_ready", "ok" if _status_ok(summaries["p017_tracker_parity"], {"ready", "ready_with_stale_audit_warning"}) and _int_text(summaries["p017_tracker_parity"].get("fail_count")) == 0 else "fail", summaries["p017_tracker_parity"].get("status", "missing"), "Repricer tracker UI parity proof ready", observed, SUMMARY_PATHS["p017_tracker_parity"]),
        _check("p018_mirror_drift_guard_ready", "ok" if summaries["p018_mirror_drift"] and _int_text(summaries["p018_mirror_drift"].get("fail_count")) == 0 else "fail", summaries["p018_mirror_drift"].get("status", "missing"), "Product DB mirror drift guard has no fails", observed, SUMMARY_PATHS["p018_mirror_drift"]),
        _check("p019_reader_map_complete", "ok" if summaries["p019_reader_map"] and _int_text(summaries["p019_reader_map"].get("unknown_owner_count")) == 0 else "fail", summaries["p019_reader_map"].get("reader_reference_rows", "missing"), "Product DB reader references have owner classification", observed, SUMMARY_PATHS["p019_reader_map"]),
        _check("p020_postgres_rehearsal_ready", "ok" if summaries["p020_postgres_rehearsal"].get("status") == "ok" and summaries["p020_postgres_rehearsal"].get("promotion_status") == "not_run_requires_explicit_approval" else "fail", summaries["p020_postgres_rehearsal"].get("promotion_status", "missing"), "PostgreSQL rehearsal is offline and gated", observed, SUMMARY_PATHS["p020_postgres_rehearsal"]),
    ]
    checks_df = pd.DataFrame(rows, columns=CHECK_COLUMNS)
    checks_df.to_csv(checks_path, index=False)
    fail_count = int(checks_df["status"].eq("fail").sum())
    warn_count = int(checks_df["status"].eq("warn").sum())
    status = "fail" if fail_count else "complete_locally_pending_explicit_cutover_approvals"
    payload = {
        "status": status,
        "observed_utc": observed,
        "fail_count": fail_count,
        "warn_count": warn_count,
        "checks_path": str(checks_path),
        "summary_path": str(summary_path),
        "report_path": str(report_path),
        "remaining_explicit_approvals": [
            "operator_acceptance_before_retiring_repricer_tracker_sheet",
            "approval_before_marking_product_db_sheet_legacy_export_only",
            "flow_owned_proof_before_a_b_h_runtime_reader_changes",
            "production_approval_before_postgres_promotion",
        ],
    }
    _write_report(report_path, payload, summaries)
    summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return payload


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Phase 2 SQL Product DB UI authority sign-off bundle.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    payload = run_check(output_dir=Path(args.output_dir), report_path=Path(args.report_path))
    if args.format == "json":
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    else:
        for key, value in payload.items():
            print(f"{key}={value}")
    return 0 if payload["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
