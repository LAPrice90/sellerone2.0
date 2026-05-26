from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
OUTCOME_LOG_PATH = OUT / "h_strategy_outcome_log.csv"
OUTCOME_DAILY_PATH = OUT / "h_strategy_outcome_daily.csv"

OUTCOME_DAILY_SCHEMA = [
    "asof_date",
    "scenario_type",
    "chosen_tactic",
    "decision_rows",
    "applied_rows",
    "no_write_rows",
    "resolved_rows",
    "pending_rows",
    "success_rows",
    "failed_rows",
    "expired_rows",
    "aborted_rows",
    "success_rate_pct",
    "failed_rate_pct",
    "sample_min_rows",
    "provisional_sample_flag",
    "avg_seller_count",
    "avg_price_gap_to_lowest_gbp",
    "below_break_even_rows",
    "at_floor_rows",
    "notes",
]

NON_ACTION_HOLD_STOP_RULES = {
    "UNDERCUT_NO_DOWNWARD_HEADROOM",
    "RAISE_NO_UPWARD_HEADROOM",
    "UPWARD_BLOCK_CPT_HIGH",
    "UPWARD_BLOCK_CPT_UNKNOWN",
    "UPWARD_BLOCK_CEILING_INPUTS",
    "UNDERCUT_HOLD_WINDOW_ACTIVE",
    "UNDERCUT_RETRY_BUDGET_EXHAUSTED",
    "UNDERCUT_NO_BUYBOX_GAIN_STREAK",
}

NON_ACTION_HOLD_REASON_CODES = {
    "REGAIN_MULTI_SELLER_NO_DOWNWARD_HEADROOM",
    "RAISE_MULTI_SELLER_NO_HEADROOM",
    "CPT_RISK_HIGH_UPWARD_BLOCK",
    "CPT_RISK_UNKNOWN_CONSERVATIVE_HOLD",
    "CEILING_RULE_INPUTS_MISSING_UPWARD_BLOCK",
    "UNDERCUT_HOLD_WINDOW_ACTIVE",
    "UNDERCUT_RETRY_BUDGET_EXHAUSTED",
    "UNDERCUT_NO_BUYBOX_GAIN_STREAK",
    "FAIL_CEILING_BELOW_HARD_FLOOR",
    "FLOOR_PRIORITY_CEILING_CONFLICT",
    "FLOOR_PRIORITY_ALREADY_SAFE_NO_WRITE",
    "PHASE_BEHAVIOR_SKIPPED_NOT_IN_COHORT",
}

FLOOR_BOUND_STALL_REASON_CODES = {
    "GUARDRAIL_HARD_FLOOR_CLAMP",
    "GUARDRAIL_ANCHOR_FLOOR_CLAMP",
    "FAIL_CEILING_BELOW_HARD_FLOOR",
    "FLOOR_PRIORITY_CEILING_CONFLICT",
    "FLOOR_PRIORITY_ALREADY_SAFE_NO_WRITE",
    "SUPPRESSION_PROBE_FLOOR_CLAMP",
    "SUPPRESSION_TARGET_CLAMPED_TO_ANCHOR_OR_HARD_FLOOR",
}

NON_ACTION_RISK_REASON_CODES = {
    "CPT_RISK_HIGH_UPWARD_BLOCK",
    "CPT_RISK_UNKNOWN_CONSERVATIVE_HOLD",
    "CEILING_RULE_INPUTS_MISSING_UPWARD_BLOCK",
}

NON_ACTION_RISK_STOP_RULES = {
    "UPWARD_BLOCK_CPT_HIGH",
    "UPWARD_BLOCK_CPT_UNKNOWN",
    "UPWARD_BLOCK_CEILING_INPUTS",
}


def _clean(value: object, *, upper: bool = False) -> str:
    text = str(value or "").strip()
    if text == "" or text.lower() == "nan":
        return ""
    return text.upper() if upper else text


def _safe_int(value: object) -> int:
    try:
        return int(float(_clean(value) or "0"))
    except Exception:
        return 0


def _safe_float(value: object) -> float | None:
    text = _clean(value)
    if not text:
        return None
    try:
        out = float(text)
    except Exception:
        return None
    if out != out:
        return None
    return out


def _sample_min_rows(scenario_type: str) -> int:
    scenario = _clean(scenario_type).lower()
    if scenario == "multi_seller_ladder_cap":
        return max(_safe_int(os.environ.get("H_STRATEGY_SAMPLE_MIN_MULTI_SELLER", "150")), 1)
    if scenario == "single_rival_reset":
        return max(_safe_int(os.environ.get("H_STRATEGY_SAMPLE_MIN_SINGLE_RIVAL", "30")), 1)
    if scenario == "suppression_reactivation":
        return max(_safe_int(os.environ.get("H_STRATEGY_SAMPLE_MIN_SUPPRESSION", "20")), 1)
    return max(_safe_int(os.environ.get("H_STRATEGY_SAMPLE_MIN_DEFAULT", "30")), 1)


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


def _convert_failed_timeouts_to_expired(rows: List[Dict[str, str]]) -> int:
    converted = 0
    for row in rows:
        state = _clean(row.get("tactic_success_state", "")).lower()
        after = _clean(row.get("buy_box_state_after", ""), upper=True)
        stop_rule = _clean(row.get("stop_rule_code", ""), upper=True)
        reasons = _reason_codes(row.get("reason_codes_json", ""))
        has_timeout_reason = "OUTCOME_WINDOW_TIMEOUT" in reasons
        if state != "failed":
            continue
        if after != "OBSERVATION_TIMEOUT":
            continue
        if stop_rule != "OUTCOME_WINDOW_TIMEOUT" and not has_timeout_reason:
            continue
        row["tactic_success_state"] = "expired"
        if _clean(row.get("stop_rule_code", "")) == "":
            row["stop_rule_code"] = "OUTCOME_WINDOW_TIMEOUT"
        row["reason_codes_json"] = _append_reason_code_json(
            row.get("reason_codes_json", ""),
            "OUTCOME_WINDOW_TIMEOUT",
        )
        converted += 1
    return converted


def _convert_non_action_expired_to_aborted(rows: List[Dict[str, str]]) -> int:
    converted = 0
    for row in rows:
        state = _clean(row.get("tactic_success_state", "")).lower()
        if state != "expired":
            continue
        after = _clean(row.get("buy_box_state_after", ""), upper=True)
        if after != "OBSERVATION_TIMEOUT":
            continue
        writer = _clean(row.get("writer_outcome", ""), upper=True)
        if writer == "APPLIED":
            continue
        scenario = _clean(row.get("scenario_type", "")).lower()
        if scenario not in {"multi_seller_ladder_cap", "single_rival_reset", "raise_find_loss", "share_hold"}:
            continue
        stop_rule = _clean(row.get("stop_rule_code", ""), upper=True)
        reasons = _reason_codes(row.get("reason_codes_json", ""))
        if stop_rule not in NON_ACTION_HOLD_STOP_RULES and not any(
            code in NON_ACTION_HOLD_REASON_CODES for code in reasons
        ):
            continue
        inferred_stop_rule = _infer_non_action_stop_rule(stop_rule=stop_rule, reasons=reasons)
        row["tactic_success_state"] = "aborted"
        row["scenario_type"] = "share_hold"
        row["chosen_tactic"] = _non_action_hold_tactic(stop_rule=inferred_stop_rule, reasons=reasons)
        if inferred_stop_rule:
            row["stop_rule_code"] = inferred_stop_rule
        row["reason_codes_json"] = _append_reason_code_json(
            row.get("reason_codes_json", ""),
            "OUTCOME_RECLASSIFIED_NON_ACTION_HOLD",
        )
        converted += 1
    return converted


def _convert_non_action_failed_to_aborted(rows: List[Dict[str, str]]) -> int:
    converted = 0
    for row in rows:
        state = _clean(row.get("tactic_success_state", "")).lower()
        if state != "failed":
            continue
        writer = _clean(row.get("writer_outcome", ""), upper=True)
        if writer == "APPLIED":
            continue
        stop_rule = _clean(row.get("stop_rule_code", ""), upper=True)
        reasons = _reason_codes(row.get("reason_codes_json", ""))
        if stop_rule not in NON_ACTION_HOLD_STOP_RULES and not any(
            code in NON_ACTION_HOLD_REASON_CODES for code in reasons
        ):
            continue
        inferred_stop_rule = _infer_non_action_stop_rule(stop_rule=stop_rule, reasons=reasons)
        row["tactic_success_state"] = "aborted"
        row["scenario_type"] = "share_hold"
        row["chosen_tactic"] = _non_action_hold_tactic(stop_rule=inferred_stop_rule, reasons=reasons)
        if inferred_stop_rule:
            row["stop_rule_code"] = inferred_stop_rule
        row["reason_codes_json"] = _append_reason_code_json(
            row.get("reason_codes_json", ""),
            "OUTCOME_RECLASSIFIED_NON_ACTION_HOLD",
        )
        converted += 1
    return converted


def _convert_floor_bound_failed_to_aborted(rows: List[Dict[str, str]]) -> int:
    converted = 0
    for row in rows:
        state = _clean(row.get("tactic_success_state", "")).lower()
        if state != "failed":
            continue
        scenario = _clean(row.get("scenario_type", "")).lower()
        if scenario not in {"multi_seller_ladder_cap", "single_rival_reset", "raise_find_loss", "suppression_reactivation"}:
            continue
        after = _clean(row.get("buy_box_state_after", ""), upper=True)
        if after not in {"LOST_TO_COMPETITOR", "SUPPRESSED_ASIN", "DISQUALIFIED_SELF_PRICE", "SUPPRESSION_FLOOR_CLAMP_STALLED"}:
            continue
        reasons = _reason_codes(row.get("reason_codes_json", ""))
        if not any(code in FLOOR_BOUND_STALL_REASON_CODES for code in reasons):
            continue
        row["tactic_success_state"] = "aborted"
        if after == "SUPPRESSION_FLOOR_CLAMP_STALLED" and _clean(row.get("stop_rule_code", "")) == "":
            row["stop_rule_code"] = "SUPPRESSION_FLOOR_CLAMP_STALLED"
        row["reason_codes_json"] = _append_reason_code_json(
            row.get("reason_codes_json", ""),
            "OUTCOME_RECLASSIFIED_FLOOR_BOUND_STALL",
        )
        converted += 1
    return converted


def _infer_non_action_stop_rule(*, stop_rule: str, reasons: List[str]) -> str:
    if stop_rule:
        return stop_rule
    reason_set = {code for code in reasons if code}
    if "REGAIN_MULTI_SELLER_NO_DOWNWARD_HEADROOM" in reason_set:
        return "UNDERCUT_NO_DOWNWARD_HEADROOM"
    if "RAISE_MULTI_SELLER_NO_HEADROOM" in reason_set:
        return "RAISE_NO_UPWARD_HEADROOM"
    if "CPT_RISK_HIGH_UPWARD_BLOCK" in reason_set:
        return "UPWARD_BLOCK_CPT_HIGH"
    if "CPT_RISK_UNKNOWN_CONSERVATIVE_HOLD" in reason_set:
        return "UPWARD_BLOCK_CPT_UNKNOWN"
    if "CEILING_RULE_INPUTS_MISSING_UPWARD_BLOCK" in reason_set:
        return "UPWARD_BLOCK_CEILING_INPUTS"
    if "UNDERCUT_HOLD_WINDOW_ACTIVE" in reason_set:
        return "UNDERCUT_HOLD_WINDOW_ACTIVE"
    if "UNDERCUT_RETRY_BUDGET_EXHAUSTED" in reason_set:
        return "UNDERCUT_RETRY_BUDGET_EXHAUSTED"
    if "UNDERCUT_NO_BUYBOX_GAIN_STREAK" in reason_set:
        return "UNDERCUT_NO_BUYBOX_GAIN_STREAK"
    return ""


def _non_action_hold_tactic(*, stop_rule: str, reasons: List[str]) -> str:
    if stop_rule in NON_ACTION_RISK_STOP_RULES:
        return "RISK_GATED_HOLD"
    reason_set = {code for code in reasons if code}
    if any(code in NON_ACTION_RISK_REASON_CODES for code in reason_set):
        return "RISK_GATED_HOLD"
    return "HOLD_OBSERVE"


def _daily_derived_fields(
    scenario_type: str,
    decision: int,
    success: int,
    failed: int,
    expired: int,
    aborted: int,
) -> Dict[str, str]:
    resolved = max(success + failed + expired + aborted, 0)
    pending = max(decision - resolved, 0)
    judged = max(success + failed, 0)
    if judged > 0:
        success_rate = success / judged * 100.0
        failed_rate = failed / judged * 100.0
    else:
        success_rate = 0.0
        failed_rate = 0.0
    sample_min = _sample_min_rows(scenario_type)
    provisional = 1 if decision < sample_min else 0
    return {
        "resolved_rows": str(resolved),
        "pending_rows": str(pending),
        "success_rate_pct": f"{success_rate:.2f}",
        "failed_rate_pct": f"{failed_rate:.2f}",
        "sample_min_rows": str(sample_min),
        "provisional_sample_flag": str(provisional),
    }


def _existing_daily_sidecar(path: Path) -> Dict[Tuple[str, str, str], Dict[str, str]]:
    _, rows = _read_csv_rows(path)
    sidecar: Dict[Tuple[str, str, str], Dict[str, str]] = {}
    for row in rows:
        key = (
            _clean(row.get("asof_date", "")),
            _clean(row.get("scenario_type", "")),
            _clean(row.get("chosen_tactic", "")),
        )
        if not all(key):
            continue
        decision_rows = max(_safe_int(row.get("decision_rows", "0")), 0)
        below_break_even_rows = max(_safe_int(row.get("below_break_even_rows", "0")), 0)
        at_floor_rows = max(_safe_int(row.get("at_floor_rows", "0")), 0)
        sidecar[key] = {
            "below_break_even_rows": str(min(below_break_even_rows, decision_rows)),
            "at_floor_rows": str(min(at_floor_rows, decision_rows)),
            "notes": _clean(row.get("notes", "")),
        }
    return sidecar


def _rebuild_daily_rows(outcome_rows: List[Dict[str, str]], sidecar: Dict[Tuple[str, str, str], Dict[str, str]]) -> List[Dict[str, str]]:
    agg: Dict[Tuple[str, str, str], Dict[str, float]] = {}
    for row in outcome_rows:
        event_ts = _clean(row.get("event_ts_utc", ""))
        if len(event_ts) < 10:
            continue
        asof_date = event_ts[:10]
        scenario = _clean(row.get("scenario_type", ""))
        tactic = _clean(row.get("chosen_tactic", ""))
        if not scenario or not tactic:
            continue
        key = (asof_date, scenario, tactic)
        if key not in agg:
            agg[key] = {
                "decision_rows": 0.0,
                "applied_rows": 0.0,
                "no_write_rows": 0.0,
                "success_rows": 0.0,
                "failed_rows": 0.0,
                "expired_rows": 0.0,
                "aborted_rows": 0.0,
                "seller_count_sum": 0.0,
                "price_gap_sum": 0.0,
            }
        entry = agg[key]
        entry["decision_rows"] += 1.0
        writer = _clean(row.get("writer_outcome", ""), upper=True)
        if writer == "APPLIED":
            entry["applied_rows"] += 1.0
        else:
            entry["no_write_rows"] += 1.0
        state = _clean(row.get("tactic_success_state", "")).lower()
        if state == "success":
            entry["success_rows"] += 1.0
        elif state == "failed":
            entry["failed_rows"] += 1.0
        elif state == "expired":
            entry["expired_rows"] += 1.0
        elif state == "aborted":
            entry["aborted_rows"] += 1.0
        entry["seller_count_sum"] += float(_safe_int(row.get("seller_count", "0")))
        our_price = _safe_float(row.get("our_price_before_gbp", ""))
        low_1 = _safe_float(row.get("lowest_price_1_gbp", ""))
        if our_price is not None and low_1 is not None:
            entry["price_gap_sum"] += (our_price - low_1)

    out_rows: List[Dict[str, str]] = []
    for key in sorted(agg.keys()):
        asof_date, scenario, tactic = key
        entry = agg[key]
        decision = int(entry["decision_rows"])
        applied = int(entry["applied_rows"])
        no_write = int(entry["no_write_rows"])
        success = int(entry["success_rows"])
        failed = int(entry["failed_rows"])
        expired = int(entry["expired_rows"])
        aborted = int(entry["aborted_rows"])
        avg_seller_count = (entry["seller_count_sum"] / decision) if decision > 0 else 0.0
        avg_price_gap = (entry["price_gap_sum"] / decision) if decision > 0 else 0.0
        derived = _daily_derived_fields(scenario, decision, success, failed, expired, aborted)
        side = sidecar.get(key, {})
        out_rows.append(
            {
                "asof_date": asof_date,
                "scenario_type": scenario,
                "chosen_tactic": tactic,
                "decision_rows": str(decision),
                "applied_rows": str(applied),
                "no_write_rows": str(no_write),
                "resolved_rows": derived["resolved_rows"],
                "pending_rows": derived["pending_rows"],
                "success_rows": str(success),
                "failed_rows": str(failed),
                "expired_rows": str(expired),
                "aborted_rows": str(aborted),
                "success_rate_pct": derived["success_rate_pct"],
                "failed_rate_pct": derived["failed_rate_pct"],
                "sample_min_rows": derived["sample_min_rows"],
                "provisional_sample_flag": derived["provisional_sample_flag"],
                "avg_seller_count": f"{avg_seller_count:.2f}",
                "avg_price_gap_to_lowest_gbp": f"{avg_price_gap:.2f}",
                "below_break_even_rows": side.get("below_break_even_rows", "0"),
                "at_floor_rows": side.get("at_floor_rows", "0"),
                "notes": side.get("notes", ""),
            }
        )
    return out_rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild h_strategy_outcome_daily.csv and normalize timeout/non-action outcome truth."
    )
    parser.add_argument("--dry-run", action="store_true", help="Show counts only. Do not write files.")
    args = parser.parse_args()

    log_fields, log_rows = _read_csv_rows(OUTCOME_LOG_PATH)
    if not log_fields:
        print(f"{OUTCOME_LOG_PATH}: missing_or_empty")
        return 0

    converted = _convert_failed_timeouts_to_expired(log_rows)
    converted_non_action = _convert_non_action_expired_to_aborted(log_rows)
    converted_non_action_failed = _convert_non_action_failed_to_aborted(log_rows)
    converted_floor_bound_failed = _convert_floor_bound_failed_to_aborted(log_rows)
    sidecar = _existing_daily_sidecar(OUTCOME_DAILY_PATH)
    rebuilt_daily_rows = _rebuild_daily_rows(log_rows, sidecar)

    if not args.dry_run:
        _write_csv_rows(OUTCOME_LOG_PATH, log_fields, log_rows)
        _write_csv_rows(OUTCOME_DAILY_PATH, OUTCOME_DAILY_SCHEMA, rebuilt_daily_rows)

    print(
        f"log_rows={len(log_rows)} converted_failed_timeouts_to_expired={converted} "
        f"converted_non_action_expired_to_aborted={converted_non_action} "
        f"converted_non_action_failed_to_aborted={converted_non_action_failed} "
        f"converted_floor_bound_failed_to_aborted={converted_floor_bound_failed} "
        f"dry_run={1 if args.dry_run else 0}"
    )
    print(
        f"daily_rows={len(rebuilt_daily_rows)} schema_cols={len(OUTCOME_DAILY_SCHEMA)} dry_run={1 if args.dry_run else 0}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
