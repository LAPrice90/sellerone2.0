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

from scripts.flows.O._contract_io import read_o_contract_df
from scripts.flows.O._schemas import get_o_output_contract
from scripts.core.storage.product_db_contract import utc_now_iso


DEFAULT_PROOF_SUMMARY = ROOT / "out" / "sql_migration" / "product_db_contract" / "repricing_write_status_proof_summary.json"
DEFAULT_OUTPUT_DIR = ROOT / "out" / "sql_migration" / "product_db_contract"
DEFAULT_CHECKS_PATH = DEFAULT_OUTPUT_DIR / "repricer_tracker_ui_cutover_check.csv"
DEFAULT_SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "repricer_tracker_ui_cutover_summary.json"

ALLOWED_STALE_AUDIT_WARNINGS = {
    "repricer_tracker_pricing_output_freshness",
    "repricer_tracker_pricing_output_blank_execution_write_status",
}

CHECK_COLUMNS: tuple[str, ...] = (
    "check",
    "status",
    "value",
    "notes",
    "observed_utc",
    "source_path",
)


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _int_text(value: object) -> int:
    text = _text(value)
    if text == "":
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def _boolish(value: object) -> bool:
    return _text(value).lower() in {"1", "true", "yes", "y"}


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


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def run_check(
    *,
    root: Path = ROOT,
    proof_summary_path: Path = DEFAULT_PROOF_SUMMARY,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    observed_utc: str | None = None,
) -> dict[str, Any]:
    observed = observed_utc or utc_now_iso()
    output_dir.mkdir(parents=True, exist_ok=True)
    checks_path = output_dir / DEFAULT_CHECKS_PATH.name
    summary_path = output_dir / DEFAULT_SUMMARY_PATH.name

    proof = _load_json(proof_summary_path)
    health = read_o_contract_df(root, "repricer_tracker_health")
    view = read_o_contract_df(root, "repricer_tracker_view")
    health_path = root / get_o_output_contract("repricer_tracker_health").rel_path
    view_path = root / get_o_output_contract("repricer_tracker_view").rel_path

    rows: list[dict[str, str]] = []
    rows.append(
        _check(
            check="p013_proof_summary_present",
            status="ok" if proof else "fail",
            value=1 if proof else 0,
            notes="P013 proof summary present" if proof else "P013 proof summary missing",
            observed_utc=observed,
            source_path=proof_summary_path,
        )
    )
    rows.append(
        _check(
            check="p013_terminal_finalized",
            status="ok" if _text(proof.get("terminal_state")) == "finalized" else "fail",
            value=proof.get("terminal_state", ""),
            notes="latest terminal run finalized",
            observed_utc=observed,
            source_path=proof_summary_path,
        )
    )
    publish_status = _text(proof.get("terminal_publish_status") or proof.get("publish_status"))
    rows.append(
        _check(
            check="p013_publish_ok",
            status="ok" if publish_status == "ok" else "fail",
            value=publish_status,
            notes="latest terminal publish status",
            observed_utc=observed,
            source_path=proof_summary_path,
        )
    )
    rows.append(
        _check(
            check="p013_runtime_blank_write_status_zero",
            status="ok" if _int_text(proof.get("runtime_blank_execution_write_status_rows")) == 0 else "fail",
            value=proof.get("runtime_blank_execution_write_status_rows", ""),
            notes="current runtime source has no blank execution_write_status rows",
            observed_utc=observed,
            source_path=proof_summary_path,
        )
    )
    rows.append(
        _check(
            check="p013_invalid_write_status_zero",
            status="ok" if _int_text(proof.get("invalid_execution_write_status_rows")) == 0 else "fail",
            value=proof.get("invalid_execution_write_status_rows", ""),
            notes="current runtime/pricing sources have no invalid write status values",
            observed_utc=observed,
            source_path=proof_summary_path,
        )
    )
    rows.append(
        _check(
            check="pricing_output_stale_audit_classified",
            status="warn" if _boolish(proof.get("pricing_output_stale")) else "ok",
            value=proof.get("pricing_output_stale_reason", ""),
            notes=(
                "stale pricing_output is classified as audit-only warning"
                if _boolish(proof.get("pricing_output_stale"))
                else "compact pricing output is not stale"
            ),
            observed_utc=observed,
            source_path=proof_summary_path,
        )
    )

    if health.empty:
        rows.append(
            _check(
                check="o050_tracker_health_present",
                status="fail",
                value=0,
                notes="repricer tracker health missing",
                observed_utc=observed,
                source_path=health_path,
            )
        )
    else:
        fail_rows = health[health["status"].astype(str).str.lower().eq("fail")]
        warn_rows = health[health["status"].astype(str).str.lower().eq("warn")]
        unexpected_warns = sorted(set(warn_rows["check"].astype(str)) - ALLOWED_STALE_AUDIT_WARNINGS)
        rows.append(
            _check(
                check="o050_tracker_health_no_fail",
                status="ok" if fail_rows.empty else "fail",
                value=len(fail_rows.index),
                notes="O050 health has no fail rows" if fail_rows.empty else "O050 health has fail rows",
                observed_utc=observed,
                source_path=health_path,
            )
        )
        rows.append(
            _check(
                check="o050_tracker_health_only_allowed_warnings",
                status="ok" if not unexpected_warns else "fail",
                value="|".join(unexpected_warns),
                notes="only stale compact pricing audit warnings are present",
                observed_utc=observed,
                source_path=health_path,
            )
        )

    rows.append(
        _check(
            check="o050_tracker_view_present",
            status="ok" if not view.empty else "fail",
            value=len(view.index),
            notes="repricer tracker view has rows" if not view.empty else "repricer tracker view missing or empty",
            observed_utc=observed,
            source_path=view_path,
        )
    )

    checks_df = pd.DataFrame(rows, columns=CHECK_COLUMNS)
    checks_df.to_csv(checks_path, index=False)
    fail_count = int(checks_df["status"].eq("fail").sum())
    warn_count = int(checks_df["status"].eq("warn").sum())
    status = "fail" if fail_count else ("ready_with_stale_audit_warning" if warn_count else "ready")
    payload = {
        "status": status,
        "observed_utc": observed,
        "fail_count": fail_count,
        "warn_count": warn_count,
        "tracker_rows": int(len(view.index)),
        "terminal_run_id": _text(proof.get("terminal_run_id", "")),
        "terminal_state": _text(proof.get("terminal_state", "")),
        "terminal_publish_status": publish_status,
        "pricing_output_stale": _boolish(proof.get("pricing_output_stale")),
        "pricing_output_stale_reason": _text(proof.get("pricing_output_stale_reason", "")),
        "sheet_status": "temporary_fallback_until_explicit_operator_cutover",
        "checks_path": str(checks_path),
        "summary_path": str(summary_path),
    }
    summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return payload


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check whether the O repricer tracker UI is ready with Sheet fallback.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--proof-summary", default=str(DEFAULT_PROOF_SUMMARY))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    payload = run_check(
        root=Path(args.root),
        proof_summary_path=Path(args.proof_summary),
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
