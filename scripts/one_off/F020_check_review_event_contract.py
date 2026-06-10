from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._schemas import get_f_output_contract


VALID_REVIEW_DECISIONS = {"", "pass", "fail", "rescan"}
VALID_REVIEW_REASON_CODES = {
    "",
    "wrong_product",
    "seller_controlled",
    "profit_too_weak",
    "demand_too_weak",
    "review_or_variant_risk",
    "missing_evidence",
    "other",
}


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


def check_review_event_contract(*, root: Path | None = None) -> dict[str, Any]:
    root_path = Path(root) if root is not None else ROOT
    contract = get_f_output_contract("feeder_review_events")
    target_path = root_path / contract.rel_path
    errors: list[str] = []

    if not target_path.exists():
        errors.append(f"missing contract file: {target_path}")
        return {
            "status": "fail",
            "path": str(target_path),
            "row_count": 0,
            "errors": errors,
            "missing_columns": list(contract.required_columns),
        }

    try:
        frame = _read_csv(target_path)
    except pd.errors.EmptyDataError:
        errors.append(f"contract file is empty and has no header: {target_path}")
        return {
            "status": "fail",
            "path": str(target_path),
            "row_count": 0,
            "errors": errors,
            "missing_columns": list(contract.required_columns),
        }
    except Exception as exc:
        errors.append(f"unable to read contract file: {type(exc).__name__}: {exc}")
        return {
            "status": "fail",
            "path": str(target_path),
            "row_count": 0,
            "errors": errors,
            "missing_columns": list(contract.required_columns),
        }

    missing_columns = [col for col in contract.required_columns if col not in frame.columns]
    if missing_columns:
        errors.append("missing required columns: " + ", ".join(missing_columns))

    duplicate_columns = sorted({col for col in frame.columns if list(frame.columns).count(col) > 1})
    if duplicate_columns:
        errors.append("duplicate columns found: " + ", ".join(duplicate_columns))

    invalid_review_decision_rows = 0
    invalid_review_reason_code_rows = 0
    invalid_event_utc_rows = 0
    duplicate_event_id_rows = 0
    non_string_cells = 0

    for col in frame.columns:
        non_string_cells += int((~frame[col].map(lambda value: isinstance(value, str))).sum())

    if "review_decision" in frame.columns:
        invalid_review_decision_rows = int(
            frame["review_decision"]
            .map(lambda value: _normalize_text(value).lower())
            .map(lambda value: value not in VALID_REVIEW_DECISIONS)
            .sum()
        )
        if invalid_review_decision_rows > 0:
            errors.append(f"invalid review_decision values: {invalid_review_decision_rows}")

    if "review_reason_code" in frame.columns:
        invalid_review_reason_code_rows = int(
            frame["review_reason_code"]
            .map(lambda value: _normalize_text(value).lower().replace(" ", "_").replace("-", "_"))
            .map(lambda value: value not in VALID_REVIEW_REASON_CODES)
            .sum()
        )
        if invalid_review_reason_code_rows > 0:
            errors.append(f"invalid review_reason_code values: {invalid_review_reason_code_rows}")

    if "event_utc" in frame.columns:
        non_empty_utc = frame["event_utc"].map(_normalize_text)
        parsed_utc = pd.to_datetime(non_empty_utc, errors="coerce", utc=True, format="mixed")
        invalid_event_utc_rows = int(((non_empty_utc != "") & parsed_utc.isna()).sum())
        if invalid_event_utc_rows > 0:
            errors.append(f"invalid event_utc values: {invalid_event_utc_rows}")

    if "event_id" in frame.columns:
        event_id_series = frame["event_id"].map(_normalize_text)
        duplicate_event_id_rows = int(event_id_series[event_id_series != ""].duplicated(keep=False).sum())
        if duplicate_event_id_rows > 0:
            errors.append(f"duplicate event_id rows: {duplicate_event_id_rows}")

    if non_string_cells > 0:
        errors.append(f"non-string cells detected: {non_string_cells}")

    status = "pass" if not errors else "fail"
    return {
        "status": status,
        "path": str(target_path),
        "row_count": int(len(frame.index)),
        "checked_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "missing_columns": missing_columns,
        "invalid_review_decision_rows": invalid_review_decision_rows,
        "invalid_review_reason_code_rows": invalid_review_reason_code_rows,
        "invalid_event_utc_rows": invalid_event_utc_rows,
        "duplicate_event_id_rows": duplicate_event_id_rows,
        "errors": errors,
    }


def assert_review_event_contract(*, root: Path | None = None) -> dict[str, Any]:
    report = check_review_event_contract(root=root)
    if report["status"] != "pass":
        raise ValueError(" ; ".join(report["errors"]))
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail-loud contract checker for feeder_review_events.")
    parser.add_argument("--root", type=Path, default=ROOT)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = check_review_event_contract(root=args.root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
