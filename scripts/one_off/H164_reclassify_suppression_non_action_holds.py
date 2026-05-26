from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

BOOT_ROOT = Path(__file__).resolve().parents[2]
if str(BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT))

from scripts.phase1 import phase1_storage

ROOT = BOOT_ROOT
OUT = ROOT / "out"
OUTCOME_LOG_PATH = OUT / "h_strategy_outcome_log.csv"

RISK_STOP_RULE_BY_REASON = {
    "CPT_RISK_HIGH_UPWARD_BLOCK": "UPWARD_BLOCK_CPT_HIGH",
    "CPT_RISK_UNKNOWN_CONSERVATIVE_HOLD": "UPWARD_BLOCK_CPT_UNKNOWN",
    "CEILING_RULE_INPUTS_MISSING_UPWARD_BLOCK": "UPWARD_BLOCK_CEILING_INPUTS",
}
SUPPRESSION_ACTION_CODES = {
    "SUPPRESSION_DIRECT_TARGET",
    "SUPPRESSION_PROBE_THRESHOLD_ESTIMATE",
    "SUPPRESSION_PROBE_START_FROM_INFERRED_UPPER_BOUND",
    "SUPPRESSION_PROBE_DOWNWARD_STEP",
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


def _contains_seller_detail_hold(reasons: List[str]) -> bool:
    return any(code.startswith("SELLER_DETAIL_STATUS_") for code in reasons)


def _mapped_risk_stop_rule(reasons: List[str]) -> str:
    for code in reasons:
        mapped = RISK_STOP_RULE_BY_REASON.get(code)
        if mapped:
            return mapped
    return ""


def _has_suppression_action(reasons: List[str]) -> bool:
    return any(code in SUPPRESSION_ACTION_CODES for code in reasons)


def _should_reclassify(row: Dict[str, str], reasons: List[str]) -> bool:
    scenario = _clean(row.get("scenario_type", "")).lower()
    tactic = _clean(row.get("chosen_tactic", ""), upper=True)
    writer_outcome = _clean(row.get("writer_outcome", ""), upper=True)
    if scenario != "suppression_reactivation":
        return False
    if tactic != "SUPPRESSION_REACTIVATION":
        return False
    if writer_outcome == "APPLIED":
        return False
    if _has_suppression_action(reasons):
        return False
    return _contains_seller_detail_hold(reasons) or bool(_mapped_risk_stop_rule(reasons))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reclassify suppression rows that were non-action holds into share_hold."
    )
    parser.add_argument("--dry-run", action="store_true", help="Show counts only. Do not write changes.")
    args = parser.parse_args()

    fieldnames, rows = _read_csv_rows(OUTCOME_LOG_PATH)
    if not fieldnames:
        print(f"missing_or_empty path={OUTCOME_LOG_PATH}")
        return 0

    reclassified = 0
    seller_detail_count = 0
    risk_hold_count = 0
    stop_rule_updates: Dict[str, int] = {}
    state_updates: Dict[str, int] = {}

    updates: List[Dict[str, str]] = []
    for row in rows:
        reasons = _reason_codes(row.get("reason_codes_json", ""))
        if not _should_reclassify(row, reasons):
            continue

        is_seller_detail = _contains_seller_detail_hold(reasons)
        mapped_stop = _mapped_risk_stop_rule(reasons)
        row["scenario_type"] = "share_hold"
        row["chosen_tactic"] = "SELLER_DETAIL_HOLD" if is_seller_detail else "HOLD_OBSERVE"
        row["reason_codes_json"] = _append_reason_code_json(
            row.get("reason_codes_json", ""),
            "OUTCOME_RECLASSIFIED_NON_ACTION_HOLD",
        )

        current_stop = _clean(row.get("stop_rule_code", ""), upper=True)
        if is_seller_detail:
            if current_stop in {"", "OUTCOME_WINDOW_TIMEOUT"}:
                row["stop_rule_code"] = "seller_detail_missing_or_stale"
                stop_rule_updates["seller_detail_missing_or_stale"] = stop_rule_updates.get("seller_detail_missing_or_stale", 0) + 1
            seller_detail_count += 1
        elif mapped_stop and current_stop in {"", "OUTCOME_WINDOW_TIMEOUT"}:
            row["stop_rule_code"] = mapped_stop
            stop_rule_updates[mapped_stop] = stop_rule_updates.get(mapped_stop, 0) + 1
            risk_hold_count += 1
        else:
            risk_hold_count += 1

        state = _clean(row.get("tactic_success_state", "")).lower()
        if state in {"failed", "expired"}:
            row["tactic_success_state"] = "aborted"
            state_updates[f"{state}->aborted"] = state_updates.get(f"{state}->aborted", 0) + 1

        updates.append(dict(row))
        reclassified += 1

    print(
        f"reclassify_summary dry_run={'1' if args.dry_run else '0'} "
        f"rows_total={len(rows)} reclassified={reclassified} "
        f"seller_detail={seller_detail_count} risk_hold={risk_hold_count}"
    )
    if stop_rule_updates:
        for key in sorted(stop_rule_updates):
            print(f"stop_rule_set={key} count={stop_rule_updates[key]}")
    if state_updates:
        for key in sorted(state_updates):
            print(f"state_update={key} count={state_updates[key]}")

    if args.dry_run:
        return 0

    if updates:
        phase1_storage.upsert_h_strategy_outcome_log(updates)
    print(f"upserted path={OUTCOME_LOG_PATH} rows={len(updates)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
