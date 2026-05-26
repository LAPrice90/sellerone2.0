from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
OUTCOME_LOG_PATH = OUT / "h_strategy_outcome_log.csv"

SOURCE_SCENARIOS = {"single_rival_reset", "multi_seller_ladder_cap"}
RISK_STOP_RULE_BY_REASON = {
    "CPT_RISK_HIGH_UPWARD_BLOCK": "UPWARD_BLOCK_CPT_HIGH",
    "CPT_RISK_UNKNOWN_CONSERVATIVE_HOLD": "UPWARD_BLOCK_CPT_UNKNOWN",
    "CEILING_RULE_INPUTS_MISSING_UPWARD_BLOCK": "UPWARD_BLOCK_CEILING_INPUTS",
}


def _clean(value: object, *, upper: bool = False) -> str:
    text = str(value or "").strip()
    if text == "" or text.lower() == "nan":
        return ""
    return text.upper() if upper else text


def _read_csv_rows(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [{name: _clean(raw.get(name, "")) for name in fieldnames} for raw in reader]
    return fieldnames, rows


def _write_csv_rows(path: Path, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _reason_codes(reason_codes_json: object) -> List[str]:
    raw = _clean(reason_codes_json)
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    out: List[str] = []
    for item in payload:
        code = _clean(item, upper=True)
        if code:
            out.append(code)
    return out


def _mapped_stop_rule(reasons: List[str]) -> str:
    for code in reasons:
        mapped = RISK_STOP_RULE_BY_REASON.get(code)
        if mapped:
            return mapped
    return ""


def _should_reclassify(row: Dict[str, str], reasons: List[str]) -> bool:
    scenario = _clean(row.get("scenario_type", "")).lower()
    writer_outcome = _clean(row.get("writer_outcome", ""), upper=True)
    if scenario not in SOURCE_SCENARIOS:
        return False
    if writer_outcome == "APPLIED":
        return False
    return any(code in RISK_STOP_RULE_BY_REASON for code in reasons)


def _append_reason_code_json(reason_codes_json: object, code: str) -> str:
    code_text = _clean(code, upper=True)
    if not code_text:
        return "[]"
    raw = _clean(reason_codes_json)
    parsed: List[str] = []
    if raw:
        try:
            payload = json.loads(raw)
            if isinstance(payload, list):
                parsed = [_clean(item, upper=True) for item in payload if _clean(item)]
        except Exception:
            parsed = []
    if code_text not in parsed:
        parsed.append(code_text)
    return json.dumps(parsed, ensure_ascii=True, separators=(",", ":"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reclassify legacy risk-gated no-write strategy rows from active strategy scenarios into share_hold."
    )
    parser.add_argument("--dry-run", action="store_true", help="Show counts only. Do not write changes.")
    args = parser.parse_args()

    fieldnames, rows = _read_csv_rows(OUTCOME_LOG_PATH)
    if not fieldnames:
        print(f"missing_or_empty path={OUTCOME_LOG_PATH}")
        return 0

    reclassified = 0
    by_source: Dict[str, int] = {}
    by_stop_rule: Dict[str, int] = {}
    by_state: Dict[str, int] = {}
    state_updates: Dict[str, int] = {}

    for row in rows:
        reasons = _reason_codes(row.get("reason_codes_json", ""))
        if not _should_reclassify(row, reasons):
            continue
        source = _clean(row.get("scenario_type", "")).lower() or "unknown"
        by_source[source] = by_source.get(source, 0) + 1

        row["scenario_type"] = "share_hold"
        row["chosen_tactic"] = "RISK_GATED_HOLD"
        row["reason_codes_json"] = _append_reason_code_json(
            row.get("reason_codes_json", ""),
            "OUTCOME_RECLASSIFIED_NON_ACTION_HOLD",
        )

        mapped_stop = _mapped_stop_rule(reasons)
        stop_rule_before = _clean(row.get("stop_rule_code", ""), upper=True)
        if mapped_stop and stop_rule_before in {"", "OUTCOME_WINDOW_TIMEOUT"}:
            row["stop_rule_code"] = mapped_stop
            by_stop_rule[mapped_stop] = by_stop_rule.get(mapped_stop, 0) + 1

        state = _clean(row.get("tactic_success_state", "")).lower() or "unknown"
        if state in {"failed", "expired"}:
            row["tactic_success_state"] = "aborted"
            state_updates[f"{state}->aborted"] = state_updates.get(f"{state}->aborted", 0) + 1
            state = "aborted"
        by_state[state] = by_state.get(state, 0) + 1
        reclassified += 1

    print(
        f"reclassify_summary dry_run={'1' if args.dry_run else '0'} "
        f"rows_total={len(rows)} reclassified={reclassified}"
    )
    if by_source:
        for key in sorted(by_source):
            print(f"source_scenario={key} count={by_source[key]}")
    if by_stop_rule:
        for key in sorted(by_stop_rule):
            print(f"stop_rule_set={key} count={by_stop_rule[key]}")
    if by_state:
        for key in sorted(by_state):
            print(f"state_seen={key} count={by_state[key]}")
    if state_updates:
        for key in sorted(state_updates):
            print(f"state_update={key} count={state_updates[key]}")

    if args.dry_run:
        return 0

    _write_csv_rows(OUTCOME_LOG_PATH, fieldnames, rows)
    print(f"wrote path={OUTCOME_LOG_PATH} rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
