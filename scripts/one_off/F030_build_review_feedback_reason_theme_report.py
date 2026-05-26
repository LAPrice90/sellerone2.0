from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
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


DEFAULT_EVENTS_PATH = ROOT / get_f_output_contract("feeder_review_events").rel_path
DEFAULT_TRIAGE_PATH = ROOT / "out" / "analysis_reports" / "f_new_product_review_fail_triage_latest.csv"
DEFAULT_OUTPUT_PATH = ROOT / "out" / "analysis_reports" / "f_review_feedback_reason_theme_latest.csv"
DEFAULT_SUMMARY_PATH = ROOT / "out" / "analysis_reports" / "f_review_feedback_reason_theme_summary_latest.md"

OUTPUT_COLUMNS = [
    "observed_utc",
    "event_utc",
    "event_id",
    "active_supplier_id",
    "active_run_id",
    "review_pack_type",
    "review_batch_id",
    "candidate_id",
    "supplier_sku",
    "asin",
    "review_decision",
    "reason_themes",
    "theme_rule_candidates",
    "theme_evidence_terms",
    "triage_fail_type",
    "triage_fail_reason_code",
    "triage_evidence_source",
    "title",
    "brand",
    "review_reason_code",
    "review_reason_label",
    "review_note",
]

FAIL_THEME_KEYS = {
    "seller_ownership_risk",
    "product_identity_mismatch",
    "profit_or_upside_weak",
    "demand_signal_conflict",
    "review_or_variant_risk",
    "missing_evidence_needed",
}

STRUCTURED_REASON_THEMES = {
    "wrong_product": ("product_identity_mismatch", "hard_rule_candidate"),
    "seller_controlled": ("seller_ownership_risk", "hard_rule_candidate"),
    "profit_too_weak": ("profit_or_upside_weak", "manual_review_candidate"),
    "demand_too_weak": ("demand_signal_conflict", "manual_review_candidate"),
    "review_or_variant_risk": ("review_or_variant_risk", "manual_review_candidate"),
    "missing_evidence": ("missing_evidence_needed", "evidence_capture_gap"),
}


@dataclass(frozen=True)
class FeedbackReasonThemeReportResult:
    report_df: pd.DataFrame
    output_path: Path
    summary_path: Path
    report: dict[str, Any]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _normalize_reason_code(value: object) -> str:
    return _normalize_text(value).lower().replace(" ", "_").replace("-", "_")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _dedupe_join(values: list[str]) -> str:
    out: list[str] = []
    for value in values:
        text = _normalize_text(value)
        if text and text not in out:
            out.append(text)
    return "|".join(out)


def _contains_any(text: str, terms: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    lowered = text.lower()
    for term in terms:
        if term in lowered:
            found.append(term)
    return found


def _classify_feedback(
    *,
    decision: str,
    title: str,
    brand: str,
    note: str,
    review_reason_code: str = "",
) -> tuple[str, str, str]:
    text = " ".join([title, brand, note]).lower()
    themes: list[str] = []
    candidates: list[str] = []
    evidence_terms: list[str] = []

    structured_code = _normalize_reason_code(review_reason_code)
    structured_theme = STRUCTURED_REASON_THEMES.get(structured_code)
    if structured_theme is not None:
        theme, rule_candidate = structured_theme
        themes.append(theme)
        candidates.append(f"{theme}:{rule_candidate}")
        evidence_terms.append(f"{theme}:structured_reason_code:{structured_code}")

    seller_terms = (
        "only sold by amazon",
        "1 seller",
        "one seller",
        "average 1 seller",
        "brand",
        "private product",
        "seller dropped",
        "dropped off a cliff",
        "restricted",
        "regulated",
        "sellable",
        "number one supplier",
    )
    identity_terms = (
        "wrong product",
        "different product",
        "real product",
        "price list",
        "price file",
        "not on the price file",
        "match",
    )
    profit_terms = (
        "not enough profit",
        "profit",
        "vat",
        "upside",
        "sales gain",
        "break even",
        "spending this much",
    )
    demand_terms = (
        "50+ sold",
        "low sales",
        "low selling",
        "stock of",
        "sales",
        "sold",
    )
    review_terms = (
        "reviews",
        "review",
        "variant",
        "1 star",
        "faulty",
        "doesnt work",
        "doesn't work",
        "poor",
    )
    missing_terms = (
        "no idea",
        "not sure",
        "maybe",
        "wonder",
        "missing",
        "not accounting",
    )

    for theme, terms, rule_candidate in [
        ("seller_ownership_risk", seller_terms, "hard_rule_candidate"),
        ("product_identity_mismatch", identity_terms, "hard_rule_candidate"),
        ("profit_or_upside_weak", profit_terms, "manual_review_candidate"),
        ("demand_signal_conflict", demand_terms, "manual_review_candidate"),
        ("review_or_variant_risk", review_terms, "manual_review_candidate"),
        ("missing_evidence_needed", missing_terms, "evidence_capture_gap"),
    ]:
        found = _contains_any(text, terms)
        if found:
            themes.append(theme)
            candidates.append(f"{theme}:{rule_candidate}")
            evidence_terms.extend([f"{theme}:{term}" for term in found[:4]])

    if _normalize_text(decision).lower() == "pass":
        if not themes:
            themes.append("pass_calibration")
            candidates.append("pass_calibration:allow_if_other_checks_pass")
        else:
            candidates = [value.replace("hard_rule_candidate", "pass_caution_signal") for value in candidates]
            candidates = [value.replace("manual_review_candidate", "pass_caution_signal") for value in candidates]
            candidates = [value.replace("evidence_capture_gap", "pass_caution_signal") for value in candidates]
    elif not themes:
        themes.append("manual_fail_unclassified")
        candidates.append("manual_fail_unclassified:needs_user_review")

    return _dedupe_join(themes), _dedupe_join(candidates), _dedupe_join(evidence_terms)


def _latest_triage_index(triage_df: pd.DataFrame) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    by_candidate: dict[str, dict[str, str]] = {}
    by_asin: dict[str, dict[str, str]] = {}
    if triage_df.empty:
        return by_candidate, by_asin
    for _, row in triage_df.iterrows():
        record = {column: _normalize_text(value) for column, value in row.to_dict().items()}
        candidate = _normalize_key(record.get("candidate_id", ""))
        asin = _normalize_key(record.get("asin", ""))
        if candidate and candidate not in by_candidate:
            by_candidate[candidate] = record
        if asin and asin not in by_asin:
            by_asin[asin] = record
    return by_candidate, by_asin


def _summary_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Review Feedback Reason Theme Summary",
        "",
        f"Observed UTC: `{report['observed_utc']}`",
        "",
        "## Counts",
        f"- feedback rows: `{report['feedback_rows']}`",
        f"- manual fail rows: `{report['manual_fail_rows']}`",
        f"- manual pass rows: `{report['manual_pass_rows']}`",
        f"- unclassified manual fail rows: `{report['unclassified_manual_fail_rows']}`",
        "",
        "## Theme Counts",
    ]
    for key, value in report["theme_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Candidate Type Counts"])
    for key, value in report["candidate_type_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Structured Reason Code Counts"])
    for key, value in report["review_reason_code_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Notes",
            "- This is a read-only theme report.",
            "- It does not change pass routing, queue files, Google Sheets, or Product DB.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_review_feedback_reason_theme_report(
    *,
    review_events_path: Path = DEFAULT_EVENTS_PATH,
    triage_path: Path = DEFAULT_TRIAGE_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    summary_path: Path = DEFAULT_SUMMARY_PATH,
    observed_utc: str | None = None,
) -> FeedbackReasonThemeReportResult:
    observed = _normalize_text(observed_utc) or _utc_now_iso()
    events_df = _read_csv(review_events_path)
    triage_df = _read_csv(triage_path)
    triage_by_candidate, triage_by_asin = _latest_triage_index(triage_df)

    rows: list[dict[str, str]] = []
    for _, event in events_df.iterrows():
        event_record = {column: _normalize_text(value) for column, value in event.to_dict().items()}
        candidate_id = event_record.get("candidate_id", "")
        asin = event_record.get("asin_padded", "") or event_record.get("asin_raw", "")
        triage = triage_by_candidate.get(_normalize_key(candidate_id), {})
        if not triage:
            triage = triage_by_asin.get(_normalize_key(asin), {})
        themes, candidates, evidence_terms = _classify_feedback(
            decision=event_record.get("review_decision", ""),
            title=event_record.get("title", ""),
            brand=event_record.get("brand", ""),
            note=event_record.get("review_note", ""),
            review_reason_code=event_record.get("review_reason_code", ""),
        )
        rows.append(
            {
                "observed_utc": observed,
                "event_utc": event_record.get("event_utc", ""),
                "event_id": event_record.get("event_id", ""),
                "active_supplier_id": event_record.get("active_supplier_id", ""),
                "active_run_id": event_record.get("active_run_id", ""),
                "review_pack_type": event_record.get("review_pack_type", ""),
                "review_batch_id": event_record.get("review_batch_id", ""),
                "candidate_id": candidate_id,
                "supplier_sku": event_record.get("supplier_sku", ""),
                "asin": asin,
                "review_decision": event_record.get("review_decision", "").lower(),
                "reason_themes": themes,
                "theme_rule_candidates": candidates,
                "theme_evidence_terms": evidence_terms,
                "triage_fail_type": triage.get("fail_type", ""),
                "triage_fail_reason_code": triage.get("fail_reason_code", ""),
                "triage_evidence_source": triage.get("evidence_source", ""),
                "title": event_record.get("title", ""),
                "brand": event_record.get("brand", ""),
                "review_reason_code": _normalize_reason_code(event_record.get("review_reason_code", "")),
                "review_reason_label": event_record.get("review_reason_label", ""),
                "review_note": event_record.get("review_note", ""),
            }
        )

    report_df = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_df.to_csv(output_path, index=False)

    theme_counter: Counter[str] = Counter()
    candidate_counter: Counter[str] = Counter()
    reason_code_counter: Counter[str] = Counter()
    for row in rows:
        for theme in row["reason_themes"].split("|"):
            if theme:
                theme_counter[theme] += 1
        for candidate in row["theme_rule_candidates"].split("|"):
            if ":" in candidate:
                candidate_counter[candidate.split(":", 1)[1]] += 1
        reason_code = _normalize_reason_code(row.get("review_reason_code", ""))
        if reason_code:
            reason_code_counter[reason_code] += 1

    manual_fail_rows = [row for row in rows if row["review_decision"] == "fail"]
    unclassified_manual_fail_rows = [
        row
        for row in manual_fail_rows
        if row["reason_themes"] == "manual_fail_unclassified"
    ]
    report = {
        "observed_utc": observed,
        "review_events_path": str(review_events_path),
        "triage_path": str(triage_path),
        "output_path": str(output_path),
        "summary_path": str(summary_path),
        "feedback_rows": int(len(rows)),
        "manual_fail_rows": int(len(manual_fail_rows)),
        "manual_pass_rows": int(sum(1 for row in rows if row["review_decision"] == "pass")),
        "unclassified_manual_fail_rows": int(len(unclassified_manual_fail_rows)),
        "theme_counts": {key: int(value) for key, value in sorted(theme_counter.items())},
        "candidate_type_counts": {key: int(value) for key, value in sorted(candidate_counter.items())},
        "review_reason_code_counts": {key: int(value) for key, value in sorted(reason_code_counter.items())},
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(_summary_markdown(report), encoding="utf-8")
    return FeedbackReasonThemeReportResult(
        report_df=report_df,
        output_path=output_path,
        summary_path=summary_path,
        report=report,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build read-only New Product Review feedback reason-theme report.")
    parser.add_argument("--review-events-path", type=Path, default=DEFAULT_EVENTS_PATH)
    parser.add_argument("--triage-path", type=Path, default=DEFAULT_TRIAGE_PATH)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--summary-path", type=Path, default=DEFAULT_SUMMARY_PATH)
    parser.add_argument("--observed-utc", default="")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = build_review_feedback_reason_theme_report(
        review_events_path=args.review_events_path,
        triage_path=args.triage_path,
        output_path=args.output_path,
        summary_path=args.summary_path,
        observed_utc=_normalize_text(args.observed_utc) or None,
    )
    print(json.dumps(result.report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
