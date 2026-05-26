from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
SUPPRESSION_CASES_PATH = OUT / "h_suppression_cases.csv"
SUPPRESSION_REACTIVATION_LOG_PATH = OUT / "h_suppression_reactivation_log.csv"
TARGET_SOURCE_FALLBACK = "NONE_UNAVAILABLE"
CEILING_FALLBACK = "UNAVAILABLE"


def _clean(value: object, *, upper: bool = False) -> str:
    text = str(value or "").strip()
    if text == "" or text.lower() == "nan":
        return ""
    return text.upper() if upper else text


def _reason_code_set(row: dict[str, str]) -> set[str]:
    out: set[str] = set()
    notes = _clean(row.get("notes", ""))
    if notes:
        for part in notes.split("|"):
            code = _clean(part, upper=True)
            if code:
                out.add(code)
    raw_json = _clean(row.get("reason_codes_json", ""))
    if raw_json:
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, list):
                for item in parsed:
                    code = _clean(item, upper=True)
                    if code:
                        out.add(code)
        except Exception:
            pass
    return out


def _first_non_empty(values: Iterable[object]) -> str:
    for value in values:
        text = _clean(value)
        if text:
            return text
    return ""


def _normalized_target_source(row: dict[str, str]) -> str:
    source = _clean(row.get("suppression_target_source", ""), upper=True)
    if source:
        return source
    reason_codes = _reason_code_set(row)
    state = _clean(row.get("state", ""), upper=True)
    action = _clean(row.get("action", ""), upper=True)
    if "SUPPRESSION_THRESHOLD_UPPER_BOUND_INFERRED_LOWEST_COMPETITOR" in reason_codes:
        return "INFERRED_UPPER_BOUND"
    if "SUPPRESSION_PROBE_CEILING_USED" in reason_codes:
        return "PROBE_CEILING"
    if "SUPPRESSION_TARGET_CARRY_FORWARD_USED" in reason_codes:
        return "CARRY_FORWARD"
    if "SUPPRESSION_SELLER_DETAIL_GATE_HOLD" in reason_codes or state == "SELLER_DETAIL_HOLD" or action == "SELLER_DETAIL_HOLD":
        return "SELLER_DETAIL_GATE"
    if "SUPPRESSION_TARGET_UNAVAILABLE" in reason_codes:
        return "NONE_UNAVAILABLE"
    return TARGET_SOURCE_FALLBACK


def _normalized_ceiling(row: dict[str, str]) -> str:
    ceiling = _first_non_empty(
        [
            row.get("suppression_ceiling_landed_temp", ""),
            row.get("suppression_reactivation_target_landed_gbp", ""),
            row.get("target_price_gbp", ""),
            row.get("current_price_gbp", ""),
            row.get("anchor_floor_price", ""),
        ]
    )
    if ceiling:
        return ceiling
    return CEILING_FALLBACK


def _load_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [{name: _clean(raw.get(name, "")) for name in fieldnames} for raw in reader]
    return fieldnames, rows


def _write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _patch_rows(rows: list[dict[str, str]]) -> int:
    updated = 0
    for row in rows:
        before = (
            _clean(row.get("suppression_target_source", ""), upper=True),
            _clean(row.get("suppression_ceiling_landed_temp", "")),
            _clean(row.get("suppression_reactivation_target_landed_gbp", "")),
        )
        row["suppression_target_source"] = _normalized_target_source(row)
        row["suppression_ceiling_landed_temp"] = _normalized_ceiling(row)
        if _clean(row.get("suppression_reactivation_target_landed_gbp", "")) == "":
            row["suppression_reactivation_target_landed_gbp"] = row["suppression_ceiling_landed_temp"]
        after = (
            _clean(row.get("suppression_target_source", ""), upper=True),
            _clean(row.get("suppression_ceiling_landed_temp", "")),
            _clean(row.get("suppression_reactivation_target_landed_gbp", "")),
        )
        if before != after:
            updated += 1
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill missing required suppression output fields.")
    parser.add_argument("--dry-run", action="store_true", help="Show counts only. Do not write files.")
    args = parser.parse_args()

    total_updated = 0
    for path in [SUPPRESSION_CASES_PATH, SUPPRESSION_REACTIVATION_LOG_PATH]:
        fieldnames, rows = _load_rows(path)
        if not fieldnames:
            print(f"{path}: missing_or_empty")
            continue
        updated = _patch_rows(rows)
        total_updated += updated
        if not args.dry_run:
            _write_rows(path, fieldnames, rows)
        print(f"{path}: rows={len(rows)} updated={updated} dry_run={1 if args.dry_run else 0}")
    print(f"total_updated={total_updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
