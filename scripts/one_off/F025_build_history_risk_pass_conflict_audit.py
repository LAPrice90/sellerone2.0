from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.core.storage import read_review_pack_dataframe


DEFAULT_PASS_PATH = ROOT / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
DEFAULT_SCRAPE_EVIDENCE_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv"
DEFAULT_BACKTEST_SUMMARY_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv"
DEFAULT_OUTPUT_PATH = ROOT / "out" / "analysis_reports" / "f_history_risk_pass_conflict_audit_latest.csv"

OUTPUT_COLUMNS = [
    "asin",
    "candidate_id",
    "supplier_sku",
    "review_pack_type",
    "history_risk_code",
    "history_recommended_action",
    "history_supporting_codes",
    "history_recommendation",
    "phase_recommendation",
    "backtest_recommendation",
    "commercial_label",
    "failure_event_count",
    "time_normal_sell_days",
    "time_selloff_days",
    "expected_units_next_30d",
    "expected_profit_next_30d_gbp",
    "evidence_source",
]

VALID_HISTORY_RISK_CODES = {
    "history_fail_phase_avoid",
    "backtest_avoid_commercial_avoid_or_exit",
    "exit_only_clean_pass",
    "failure_events_100_plus",
    "selloff_days_exceed_normal_days",
    "history_risk_clear",
}

HISTORY_RECOMMENDED_ACTIONS = {
    "history_fail_phase_avoid": "remove_from_clean_pass",
    "backtest_avoid_commercial_avoid_or_exit": "remove_from_clean_pass",
    "exit_only_clean_pass": "remove_from_clean_pass",
    "failure_events_100_plus": "manual_review",
    "selloff_days_exceed_normal_days": "manual_review",
    "history_risk_clear": "allow_if_other_checks_pass",
}

HISTORY_RULE_PRIORITY = {
    "history_fail_phase_avoid": 10,
    "exit_only_clean_pass": 20,
    "backtest_avoid_commercial_avoid_or_exit": 30,
    "failure_events_100_plus": 40,
    "selloff_days_exceed_normal_days": 50,
    "history_risk_clear": 90,
}


@dataclass(frozen=True)
class HistoryRiskPassConflictAuditResult:
    audit_df: pd.DataFrame
    output_path: Path
    report: dict[str, Any]


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _read_pass_review_pack(path: Path) -> pd.DataFrame:
    return read_review_pack_dataframe(path, pack_type="passes", dtype=str).fillna("")


def _parse_float(value: object) -> float | None:
    text = _normalize_text(value)
    if text == "":
        return None
    cleaned = text.replace(",", "").replace("GBP", "").replace("gbp", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _num_to_text(value: float | int | None) -> str:
    if value is None:
        return ""
    as_float = float(value)
    if as_float.is_integer():
        return str(int(as_float))
    return f"{as_float:.6f}".rstrip("0").rstrip(".")


def _parse_summary_tokens(raw_text: object) -> dict[str, str]:
    text = _normalize_text(raw_text)
    if text == "":
        return {}
    tokens: dict[str, str] = {}
    for chunk in text.split("|"):
        part = _normalize_text(chunk)
        if part == "" or "=" not in part:
            continue
        key, value = part.split("=", 1)
        key_norm = _normalize_key(key)
        if key_norm:
            tokens[key_norm] = _normalize_text(value)
    return tokens


def _latest_records(
    df: pd.DataFrame,
    *,
    key_columns: list[str],
    utc_columns: list[str],
) -> dict[tuple[str, ...], dict[str, str]]:
    if df.empty:
        return {}
    work = df.copy()
    for column in key_columns + utc_columns:
        if column not in work.columns:
            work[column] = ""
        work[column] = work[column].map(_normalize_text)

    utc_sort = None
    for column in utc_columns:
        parsed = pd.to_datetime(work[column], errors="coerce", utc=True, format="mixed")
        utc_sort = parsed if utc_sort is None else utc_sort.fillna(parsed)
    if utc_sort is not None:
        work["_utc_sort"] = utc_sort
        work = work.sort_values("_utc_sort", ascending=False, kind="stable")

    records: dict[tuple[str, ...], dict[str, str]] = {}
    for _, row in work.iterrows():
        key = tuple(_normalize_key(row.get(column, "")) for column in key_columns)
        if any(part == "" for part in key):
            continue
        if key in records:
            continue
        records[key] = {column: _normalize_text(value) for column, value in row.to_dict().items()}
    return records


def _lookup_latest(
    primary: dict[tuple[str, ...], dict[str, str]],
    primary_key: tuple[str, ...],
    secondary: dict[tuple[str, ...], dict[str, str]],
    secondary_key: tuple[str, ...],
    tertiary: dict[tuple[str, ...], dict[str, str]],
    tertiary_key: tuple[str, ...],
) -> dict[str, str]:
    if primary_key in primary:
        return primary[primary_key]
    if secondary_key in secondary:
        return secondary[secondary_key]
    if tertiary_key in tertiary:
        return tertiary[tertiary_key]
    return {}


def _recommendation_label(value: object) -> str:
    text = _normalize_key(value).replace("-", "_").replace(" ", "_")
    if text.startswith("EXIT"):
        return "EXIT_ONLY"
    if text.startswith("AVOID"):
        return "AVOID"
    if text.startswith("PASS"):
        return "PASS"
    if text.startswith("REVIEW"):
        return "REVIEW"
    if text.startswith("FAIL"):
        return "FAIL"
    return text


def _commercial_label(
    *,
    pass_row: dict[str, str],
    scrape_row: dict[str, str],
    backtest_row: dict[str, str],
) -> str:
    labels: list[str] = []
    note = _normalize_text(pass_row.get("commercial_note", ""))
    for token in note.split("|"):
        label = _recommendation_label(token)
        if label in {"EXIT_ONLY", "AVOID"}:
            labels.append(label)
    if "EXIT_ONLY" in labels:
        return "EXIT_ONLY"
    if "AVOID" in labels:
        return "AVOID"
    for candidate in (
        scrape_row.get("opportunity_recommendation", ""),
        backtest_row.get("recommendation", ""),
        note,
    ):
        label = _recommendation_label(candidate)
        if label in {"EXIT_ONLY", "AVOID"}:
            labels.append(label)
    if "EXIT_ONLY" in labels:
        return "EXIT_ONLY"
    if "AVOID" in labels:
        return "AVOID"
    return _recommendation_label(note)


def _history_recommendation(pass_row: dict[str, str], scrape_row: dict[str, str]) -> str:
    watch_tokens = _parse_summary_tokens(pass_row.get("watch_data_summary", ""))
    return _recommendation_label(watch_tokens.get("HISTORY_RECOMMENDATION", "") or scrape_row.get("history_recommendation", ""))


def _phase_recommendation(scrape_row: dict[str, str]) -> str:
    return _recommendation_label(scrape_row.get("phase_recommendation", ""))


def _history_rules(
    *,
    history_recommendation: str,
    phase_recommendation: str,
    backtest_recommendation: str,
    commercial_label: str,
    failure_event_count: float | None,
    time_normal_sell_days: float | None,
    time_selloff_days: float | None,
) -> tuple[str, tuple[str, ...]]:
    triggered_codes: list[str] = []
    if history_recommendation == "FAIL" and phase_recommendation == "AVOID":
        triggered_codes.append("history_fail_phase_avoid")
    if backtest_recommendation == "AVOID" and commercial_label in {"AVOID", "EXIT_ONLY"}:
        triggered_codes.append("backtest_avoid_commercial_avoid_or_exit")
    if backtest_recommendation == "EXIT_ONLY" or commercial_label == "EXIT_ONLY":
        triggered_codes.append("exit_only_clean_pass")
    if failure_event_count is not None and failure_event_count >= 100:
        triggered_codes.append("failure_events_100_plus")
    if (
        time_normal_sell_days is not None
        and time_selloff_days is not None
        and time_selloff_days > time_normal_sell_days
    ):
        triggered_codes.append("selloff_days_exceed_normal_days")
    if not triggered_codes:
        triggered_codes.append("history_risk_clear")

    deduped_codes: list[str] = []
    for code in sorted(triggered_codes, key=lambda item: HISTORY_RULE_PRIORITY.get(item, 999)):
        if code not in deduped_codes:
            deduped_codes.append(code)
    primary_code = deduped_codes[0]
    return primary_code, tuple(deduped_codes)


def _evidence_source(scrape_row: dict[str, str], backtest_row: dict[str, str]) -> str:
    parts = ["f_live_price_file_pass_review_latest.csv"]
    parts.append("feeder_legacy_scrape_evidence_live.csv" if scrape_row else "scrape_evidence_missing")
    parts.append("feeder_backtest_summary_live.csv" if backtest_row else "backtest_summary_missing")
    return "|".join(parts)


def _build_output_row(
    *,
    pass_row: dict[str, str],
    scrape_row: dict[str, str],
    backtest_row: dict[str, str],
) -> dict[str, str]:
    history_recommendation = _history_recommendation(pass_row, scrape_row)
    phase_recommendation = _phase_recommendation(scrape_row)
    backtest_recommendation = _recommendation_label(backtest_row.get("recommendation", ""))
    commercial_label = _commercial_label(
        pass_row=pass_row,
        scrape_row=scrape_row,
        backtest_row=backtest_row,
    )

    failure_event_count = _parse_float(backtest_row.get("failure_event_count", ""))
    time_normal_sell_days = _parse_float(backtest_row.get("time_normal_sell_days", ""))
    time_selloff_days = _parse_float(backtest_row.get("time_selloff_days", ""))

    expected_units = _parse_float(pass_row.get("expected_units_next_30d", ""))
    if expected_units is None:
        expected_units = _parse_float(backtest_row.get("expected_units_next_30d", ""))
    expected_profit = _parse_float(pass_row.get("expected_profit_next_30d_gbp", ""))
    if expected_profit is None:
        expected_profit = _parse_float(backtest_row.get("expected_profit_next_30d_gbp", ""))

    history_risk_code, supporting_codes = _history_rules(
        history_recommendation=history_recommendation,
        phase_recommendation=phase_recommendation,
        backtest_recommendation=backtest_recommendation,
        commercial_label=commercial_label,
        failure_event_count=failure_event_count,
        time_normal_sell_days=time_normal_sell_days,
        time_selloff_days=time_selloff_days,
    )
    history_recommended_action = HISTORY_RECOMMENDED_ACTIONS[history_risk_code]

    return {
        "asin": _normalize_text(pass_row.get("asin", "")),
        "candidate_id": _normalize_text(pass_row.get("candidate_id", "")),
        "supplier_sku": _normalize_text(pass_row.get("supplier_sku", "")),
        "review_pack_type": "passes",
        "history_risk_code": history_risk_code,
        "history_recommended_action": history_recommended_action,
        "history_supporting_codes": "|".join(supporting_codes),
        "history_recommendation": history_recommendation,
        "phase_recommendation": phase_recommendation,
        "backtest_recommendation": backtest_recommendation,
        "commercial_label": commercial_label,
        "failure_event_count": _num_to_text(failure_event_count),
        "time_normal_sell_days": _num_to_text(time_normal_sell_days),
        "time_selloff_days": _num_to_text(time_selloff_days),
        "expected_units_next_30d": _num_to_text(expected_units),
        "expected_profit_next_30d_gbp": _num_to_text(expected_profit),
        "evidence_source": _evidence_source(scrape_row, backtest_row),
    }


def build_history_risk_pass_conflict_audit(
    *,
    pass_path: Path = DEFAULT_PASS_PATH,
    scrape_evidence_path: Path = DEFAULT_SCRAPE_EVIDENCE_PATH,
    backtest_summary_path: Path = DEFAULT_BACKTEST_SUMMARY_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> HistoryRiskPassConflictAuditResult:
    pass_df = _read_pass_review_pack(pass_path)
    scrape_df = _read_csv(scrape_evidence_path)
    backtest_df = _read_csv(backtest_summary_path)

    scrape_by_candidate = _latest_records(scrape_df, key_columns=["candidate_id"], utc_columns=["observed_utc", "scan_day"])
    scrape_by_supplier_asin = _latest_records(
        scrape_df,
        key_columns=["supplier_sku", "asin"],
        utc_columns=["observed_utc", "scan_day"],
    )
    scrape_by_asin = _latest_records(scrape_df, key_columns=["asin"], utc_columns=["observed_utc", "scan_day"])
    backtest_by_supplier_asin = _latest_records(
        backtest_df,
        key_columns=["seller_sku", "asin"],
        utc_columns=["observed_utc"],
    )
    backtest_by_asin = _latest_records(backtest_df, key_columns=["asin"], utc_columns=["observed_utc"])

    output_rows: list[dict[str, str]] = []
    if not pass_df.empty:
        for _, row in pass_df.iterrows():
            pass_row = {column: _normalize_text(value) for column, value in row.to_dict().items()}
            candidate_key = (_normalize_key(pass_row.get("candidate_id", "")),)
            supplier_asin_key = (_normalize_key(pass_row.get("supplier_sku", "")), _normalize_key(pass_row.get("asin", "")))
            asin_key = (_normalize_key(pass_row.get("asin", "")),)
            scrape_row = _lookup_latest(
                scrape_by_candidate,
                candidate_key,
                scrape_by_supplier_asin,
                supplier_asin_key,
                scrape_by_asin,
                asin_key,
            )
            backtest_row = {}
            if supplier_asin_key in backtest_by_supplier_asin:
                backtest_row = backtest_by_supplier_asin[supplier_asin_key]
            elif asin_key in backtest_by_asin:
                backtest_row = backtest_by_asin[asin_key]
            output_rows.append(
                _build_output_row(
                    pass_row=pass_row,
                    scrape_row=scrape_row,
                    backtest_row=backtest_row,
                )
            )

    audit_df = pd.DataFrame(output_rows, columns=OUTPUT_COLUMNS)
    if not audit_df.empty:
        audit_df = audit_df.sort_values(
            by=["review_pack_type", "asin", "candidate_id", "supplier_sku"],
            ascending=[True, True, True, True],
            kind="stable",
        ).reset_index(drop=True)

    unclassified_rows = 0
    if not audit_df.empty:
        unclassified_rows += int((~audit_df["history_risk_code"].isin(VALID_HISTORY_RISK_CODES)).sum())
        unclassified_rows += int((audit_df["history_risk_code"].map(_normalize_text) == "").sum())
        unclassified_rows += int((audit_df["history_recommended_action"].map(_normalize_text) == "").sum())

    output_path.parent.mkdir(parents=True, exist_ok=True)
    audit_df.to_csv(output_path, index=False)

    code_counts = (
        {str(key): int(value) for key, value in audit_df["history_risk_code"].value_counts().sort_index().items()}
        if not audit_df.empty
        else {}
    )
    action_counts = (
        {str(key): int(value) for key, value in audit_df["history_recommended_action"].value_counts().sort_index().items()}
        if not audit_df.empty
        else {}
    )
    b0_rows = audit_df.loc[audit_df["asin"].map(_normalize_key) == "B0C8C3JF9X"].to_dict("records") if not audit_df.empty else []

    report = {
        "pass_input_rows": int(len(pass_df.index)),
        "audit_output_rows": int(len(audit_df.index)),
        "scrape_evidence_rows": int(len(scrape_df.index)),
        "backtest_summary_rows": int(len(backtest_df.index)),
        "unclassified_rows": int(unclassified_rows),
        "history_risk_code_counts": code_counts,
        "history_recommended_action_counts": action_counts,
        "b0c8c3jf9x_flagged": bool(b0_rows),
        "b0c8c3jf9x_codes": sorted({row["history_risk_code"] for row in b0_rows}),
        "output_path": str(output_path),
    }
    return HistoryRiskPassConflictAuditResult(audit_df=audit_df, output_path=output_path, report=report)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build read-only history-risk conflict audit for clean pass rows.")
    parser.add_argument("--pass-path", type=Path, default=DEFAULT_PASS_PATH)
    parser.add_argument("--scrape-evidence-path", type=Path, default=DEFAULT_SCRAPE_EVIDENCE_PATH)
    parser.add_argument("--backtest-summary-path", type=Path, default=DEFAULT_BACKTEST_SUMMARY_PATH)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = build_history_risk_pass_conflict_audit(
        pass_path=args.pass_path,
        scrape_evidence_path=args.scrape_evidence_path,
        backtest_summary_path=args.backtest_summary_path,
        output_path=args.output_path,
    )
    print(json.dumps(result.report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
