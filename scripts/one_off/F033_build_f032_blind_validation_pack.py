from __future__ import annotations

import argparse
import json
import sys
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

from scripts.flows.F._title_match_agent import classify_title_match


DEFAULT_PLAN_DIR = ROOT / "plans" / "active" / "f-new-product-review-fail-automation-v1"
DEFAULT_SAMPLE_PATH = DEFAULT_PLAN_DIR / "TITLE_MATCH_AGENT_SAMPLE_COLLECTION.csv"
DEFAULT_BLIND_INPUT_PATH = DEFAULT_PLAN_DIR / "f032_blind_validation_inputs.csv"
DEFAULT_EXPECTED_PATH = DEFAULT_PLAN_DIR / "f032_blind_validation_expected.csv"
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"
DEFAULT_HEALTH_PATH = DEFAULT_OUTPUT_DIR / "f032_blind_validation_health_latest.csv"
DEFAULT_SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "f032_blind_validation_summary_latest.md"

FORBIDDEN_BLIND_COLUMNS = {
    "agent_expected_action",
    "evidence_source",
    "fail_reason_code",
    "fail_type",
    "review_note",
    "training_label_seed",
}

BLIND_INPUT_COLUMNS = [
    "observed_utc",
    "blind_case_id",
    "active_supplier_id",
    "active_run_id",
    "supplier_sku",
    "asin",
    "brand",
    "supplier_brand_guess",
    "amazon_brand",
    "supplier_title",
    "amazon_title",
    "unit_cost_gbp",
    "currency",
    "roi_check_value",
    "fallback_roi",
    "profit_per_unit_30d_gbp",
    "estimated_monthly_profit_gbp",
    "phase_profit_pct",
    "bbp_final_sell_price_gbp",
    "break_even_gbp",
    "title_overlap_ratio",
    "quantity_alignment_status",
    "pack_size_guidance",
    "title_match_rule_action",
    "title_match_rule_bucket",
    "title_match_rule_reason",
    "title_match_evidence",
]

EXPECTED_COLUMNS = [
    "observed_utc",
    "blind_case_id",
    "supplier_sku",
    "asin",
    "expected_action",
    "acceptable_actions",
    "expected_bucket",
    "source_training_label",
    "hidden_review_note",
]


@dataclass(frozen=True)
class F033Result:
    blind_input_df: pd.DataFrame
    expected_df: pd.DataFrame
    health_df: pd.DataFrame
    report: dict[str, Any]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _case_id(row: pd.Series, index: int) -> str:
    sku = _normalize_text(row.get("supplier_sku", ""))
    asin = _normalize_text(row.get("asin", ""))
    if sku or asin:
        return f"f032-blind-{sku}-{asin}".strip("-")
    return f"f032-blind-row-{index + 1:04d}"


def _expected_action(row: pd.Series) -> str:
    expected = _normalize_text(row.get("agent_expected_action", ""))
    label = _normalize_text(row.get("training_label_seed", ""))
    if expected == "allow_if_other_checks_pass":
        return "allow_if_other_checks_pass"
    if expected in {"remove_from_clean_pass", "clear_breach_remove_from_clean_pass"}:
        return "remove_from_clean_pass"
    if expected == "needs_user_guidance_or_source_check":
        return "manual_review"
    if label in {"wrong_product_title_mismatch", "high_roi_identity_suspicion"}:
        return "remove_from_clean_pass"
    if label.startswith("title_match_clear"):
        return "allow_if_other_checks_pass"
    return "manual_review"


def _acceptable_actions(row: pd.Series, expected_action: str) -> str:
    expected = _normalize_text(row.get("agent_expected_action", ""))
    label = _normalize_text(row.get("training_label_seed", ""))
    if expected == "needs_user_guidance_or_source_check" or label == "price_file_presence_or_mapping_issue":
        return "manual_review|rescan_needed"
    return expected_action


def _expected_bucket(row: pd.Series, expected_action: str) -> str:
    label = _normalize_text(row.get("training_label_seed", ""))
    if label == "high_roi_identity_suspicion":
        return "high_roi_identity_suspicion"
    if label == "wrong_product_title_mismatch":
        return "clear_breach_remove_from_clean_pass"
    if label == "price_file_presence_or_mapping_issue":
        return "needs_user_guidance"
    if label.startswith("title_match_clear"):
        return "ai_review_clear"
    if expected_action == "remove_from_clean_pass":
        return "clear_breach_remove_from_clean_pass"
    if expected_action == "allow_if_other_checks_pass":
        return "ai_review_clear"
    return "needs_user_guidance"


def _build_rows(sample_df: pd.DataFrame, observed_utc: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    input_rows: list[dict[str, str]] = []
    expected_rows: list[dict[str, str]] = []
    for index, row in sample_df.fillna("").iterrows():
        case_id = _case_id(row, index)
        expected_action = _expected_action(row)
        title_decision = classify_title_match(
            {
                "supplier_title": _normalize_text(row.get("supplier_title", "")),
                "amazon_title": _normalize_text(row.get("title", "")),
                "supplier_brand": "",
                "amazon_brand": _normalize_text(row.get("brand", "")),
                "unit_cost": _normalize_text(row.get("unit_cost", "")),
                "roi_check_value": _normalize_text(row.get("roi_check_value", "")),
                "fallback_roi": _normalize_text(row.get("fallback_roi", "")),
                "phase_profit_pct": _normalize_text(row.get("phase_profit_pct", "")),
                "profit_per_unit_30d_gbp": _normalize_text(row.get("profit_per_unit_30d", "")),
                "estimated_monthly_profit_gbp": _normalize_text(row.get("estimated_monthly_profit", "")),
            }
        )
        input_rows.append(
            {
                "observed_utc": observed_utc,
                "blind_case_id": case_id,
                "active_supplier_id": _normalize_text(row.get("active_supplier_id", "")),
                "active_run_id": _normalize_text(row.get("active_run_id", "")),
                "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                "asin": _normalize_text(row.get("asin", "")),
                "brand": _normalize_text(row.get("brand", "")),
                "supplier_brand_guess": _normalize_text(title_decision.get("supplier_brand", "")),
                "amazon_brand": _normalize_text(title_decision.get("amazon_brand", "")),
                "supplier_title": _normalize_text(row.get("supplier_title", "")),
                "amazon_title": _normalize_text(row.get("title", "")),
                "unit_cost_gbp": _normalize_text(row.get("unit_cost", "")),
                "currency": _normalize_text(row.get("currency", "")),
                "roi_check_value": _normalize_text(row.get("roi_check_value", "")),
                "fallback_roi": _normalize_text(row.get("fallback_roi", "")),
                "profit_per_unit_30d_gbp": _normalize_text(row.get("profit_per_unit_30d", "")),
                "estimated_monthly_profit_gbp": _normalize_text(row.get("estimated_monthly_profit", "")),
                "phase_profit_pct": _normalize_text(row.get("phase_profit_pct", "")),
                "bbp_final_sell_price_gbp": _normalize_text(row.get("bbp_final_sell_price", "")),
                "break_even_gbp": _normalize_text(row.get("break_even", "")),
                "title_overlap_ratio": _normalize_text(title_decision.get("title_overlap_ratio", "")),
                "quantity_alignment_status": _normalize_text(title_decision.get("quantity_alignment_status", "")),
                "pack_size_guidance": _normalize_text(title_decision.get("pack_size_guidance", "")),
                "title_match_rule_action": _normalize_text(title_decision.get("title_match_action", "")),
                "title_match_rule_bucket": _normalize_text(title_decision.get("agent_decision_bucket", "")),
                "title_match_rule_reason": _normalize_text(title_decision.get("agent_reason_code", "")),
                "title_match_evidence": _normalize_text(title_decision.get("agent_evidence", "")),
            }
        )
        expected_rows.append(
            {
                "observed_utc": observed_utc,
                "blind_case_id": case_id,
                "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                "asin": _normalize_text(row.get("asin", "")),
                "expected_action": expected_action,
                "acceptable_actions": _acceptable_actions(row, expected_action),
                "expected_bucket": _expected_bucket(row, expected_action),
                "source_training_label": _normalize_text(row.get("training_label_seed", "")),
                "hidden_review_note": _normalize_text(row.get("review_note", "")),
            }
        )
    return (
        pd.DataFrame(input_rows, columns=BLIND_INPUT_COLUMNS).fillna(""),
        pd.DataFrame(expected_rows, columns=EXPECTED_COLUMNS).fillna(""),
    )


def _build_health(blind_df: pd.DataFrame, expected_df: pd.DataFrame, observed_utc: str) -> pd.DataFrame:
    rows: list[dict[str, str]] = []

    def add(metric: str, value: int | str, status: str, detail: str = "") -> None:
        rows.append({"observed_utc": observed_utc, "metric": metric, "value": str(value), "status": status, "detail": detail})

    input_rows = len(blind_df.index)
    expected_rows = len(expected_df.index)
    clear_pass = int(expected_df["expected_action"].eq("allow_if_other_checks_pass").sum()) if not expected_df.empty else 0
    clear_fail = int(expected_df["expected_action"].eq("remove_from_clean_pass").sum()) if not expected_df.empty else 0
    manual = int(expected_df["expected_action"].eq("manual_review").sum()) if not expected_df.empty else 0
    leaked_columns = sorted(FORBIDDEN_BLIND_COLUMNS & set(blind_df.columns))
    missing_supplier_title = int(blind_df["supplier_title"].map(_normalize_text).eq("").sum()) if not blind_df.empty else 0
    missing_amazon_with_asin = (
        int((blind_df["amazon_title"].map(_normalize_text).eq("") & blind_df["asin"].map(_normalize_text).ne("")).sum())
        if not blind_df.empty
        else 0
    )

    add("blind_input_rows", input_rows, "PASS" if input_rows else "FAIL")
    add("hidden_expected_rows", expected_rows, "PASS" if expected_rows == input_rows else "FAIL")
    add("leaked_answer_columns_in_blind_input", len(leaked_columns), "FAIL" if leaked_columns else "PASS", "|".join(leaked_columns))
    add("missing_supplier_title_rows", missing_supplier_title, "WARN" if missing_supplier_title else "PASS")
    add("missing_amazon_title_with_asin_rows", missing_amazon_with_asin, "FAIL" if missing_amazon_with_asin else "PASS")
    add("clear_pass_seed_rows", clear_pass, "PASS" if clear_pass >= 20 else "WARN", "target is 20 for acceptance")
    add("clear_fail_seed_rows", clear_fail, "PASS" if clear_fail >= 20 else "WARN", "target is 20 for acceptance")
    add("manual_seed_rows", manual, "PASS" if manual >= 20 else "WARN", "target is 20 for acceptance")
    add("minimum_seed_set_ready", "yes" if clear_pass >= 20 and clear_fail >= 20 and manual >= 20 else "no", "PASS" if clear_pass >= 20 and clear_fail >= 20 and manual >= 20 else "WARN")
    return pd.DataFrame(rows)


def _write_outputs(blind_input_path: Path, expected_path: Path, health_path: Path, summary_path: Path, result: F033Result) -> None:
    blind_input_path.parent.mkdir(parents=True, exist_ok=True)
    expected_path.parent.mkdir(parents=True, exist_ok=True)
    health_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    result.blind_input_df.to_csv(blind_input_path, index=False)
    result.expected_df.to_csv(expected_path, index=False)
    result.health_df.to_csv(health_path, index=False)
    lines = [
        "# F032 Blind Validation Pack Summary",
        "",
        f"- observed_utc: `{result.report['observed_utc']}`",
        f"- blind_input_rows: `{result.report['blind_input_rows']}`",
        f"- hidden_expected_rows: `{result.report['hidden_expected_rows']}`",
        f"- clear_pass_seed_rows: `{result.report['clear_pass_seed_rows']}`",
        f"- clear_fail_seed_rows: `{result.report['clear_fail_seed_rows']}`",
        f"- manual_seed_rows: `{result.report['manual_seed_rows']}`",
        f"- minimum_seed_set_ready: `{result.report['minimum_seed_set_ready']}`",
        "",
        "## Health",
        "",
    ]
    for row in result.health_df.to_dict("records"):
        lines.append(f"- {row['metric']}: `{row['value']}` ({row['status']})")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_f032_blind_validation_pack(
    *,
    sample_path: Path = DEFAULT_SAMPLE_PATH,
    blind_input_path: Path = DEFAULT_BLIND_INPUT_PATH,
    expected_path: Path = DEFAULT_EXPECTED_PATH,
    health_path: Path = DEFAULT_HEALTH_PATH,
    summary_path: Path = DEFAULT_SUMMARY_PATH,
    observed_utc: str | None = None,
    write_outputs: bool = True,
) -> F033Result:
    observed = observed_utc or _utc_now_iso()
    sample_df = _read_csv(sample_path)
    blind_df, expected_df = _build_rows(sample_df, observed)
    health_df = _build_health(blind_df, expected_df, observed)
    report = {
        "observed_utc": observed,
        "blind_input_rows": int(len(blind_df.index)),
        "hidden_expected_rows": int(len(expected_df.index)),
        "clear_pass_seed_rows": int(expected_df["expected_action"].eq("allow_if_other_checks_pass").sum()) if not expected_df.empty else 0,
        "clear_fail_seed_rows": int(expected_df["expected_action"].eq("remove_from_clean_pass").sum()) if not expected_df.empty else 0,
        "manual_seed_rows": int(expected_df["expected_action"].eq("manual_review").sum()) if not expected_df.empty else 0,
        "minimum_seed_set_ready": "yes"
        if (
            not expected_df.empty
            and int(expected_df["expected_action"].eq("allow_if_other_checks_pass").sum()) >= 20
            and int(expected_df["expected_action"].eq("remove_from_clean_pass").sum()) >= 20
            and int(expected_df["expected_action"].eq("manual_review").sum()) >= 20
        )
        else "no",
        "health_fail_rows": int(health_df["status"].eq("FAIL").sum()) if not health_df.empty else 0,
        "health_warn_rows": int(health_df["status"].eq("WARN").sum()) if not health_df.empty else 0,
    }
    result = F033Result(blind_input_df=blind_df, expected_df=expected_df, health_df=health_df, report=report)
    if write_outputs:
        _write_outputs(blind_input_path, expected_path, health_path, summary_path, result)
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the F032 blind validation input and hidden expected-answer split.")
    parser.add_argument("--sample-path", type=Path, default=DEFAULT_SAMPLE_PATH)
    parser.add_argument("--blind-input-path", type=Path, default=DEFAULT_BLIND_INPUT_PATH)
    parser.add_argument("--expected-path", type=Path, default=DEFAULT_EXPECTED_PATH)
    parser.add_argument("--health-path", type=Path, default=DEFAULT_HEALTH_PATH)
    parser.add_argument("--summary-path", type=Path, default=DEFAULT_SUMMARY_PATH)
    parser.add_argument("--observed-utc", default="")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = build_f032_blind_validation_pack(
        sample_path=args.sample_path,
        blind_input_path=args.blind_input_path,
        expected_path=args.expected_path,
        health_path=args.health_path,
        summary_path=args.summary_path,
        observed_utc=_normalize_text(args.observed_utc) or None,
    )
    print(json.dumps(result.report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
