from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = ROOT / "out" / "reports" / "hf_learning_operator_report_latest.csv"

ACTION_OUTCOMES_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_action_outcomes_latest.csv"
SCRAPE_GAP_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_scrape_gap_report_latest.csv"
ALIGNMENT_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_alignment_30d_latest.csv"
FACTOR_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_factor_impacts_latest.csv"
HEALTH_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_health_checklist_latest.csv"

REQUIRED_INPUTS = [ACTION_OUTCOMES_PATH, SCRAPE_GAP_PATH, ALIGNMENT_PATH, FACTOR_PATH, HEALTH_PATH]


@dataclass(frozen=True)
class OperatorReportResult:
    output_path: Path
    rows: int
    health_fail_count: int
    health_warn_count: int


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _read_csv_required(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"required phase-5 input missing: {path}")
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _to_float(value: object) -> float | None:
    text = _normalize_text(value)
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _column_as_text(df: pd.DataFrame, column: str) -> pd.Series:
    if column in df.columns:
        return df[column].map(_normalize_text)
    return pd.Series([""] * len(df.index), index=df.index, dtype=str)


def _pct(numerator: float, denominator: float) -> str:
    if denominator <= 0:
        return "0.0000"
    return f"{(numerator / denominator):.4f}"


def _metric_row(
    *,
    observed_utc: str,
    section: str,
    metric_key: str,
    metric_value: str,
    metric_text: str,
    source_path: Path,
) -> dict[str, str]:
    return {
        "observed_utc": observed_utc,
        "section": section,
        "metric_key": metric_key,
        "metric_value": metric_value,
        "metric_text": metric_text,
        "source_path": str(source_path),
    }


def _ensure_required_inputs() -> None:
    for path in REQUIRED_INPUTS:
        if not path.exists():
            raise FileNotFoundError(f"required phase-5 input missing: {path}")


def build_operator_report(*, output_path: Path) -> OperatorReportResult:
    _ensure_required_inputs()
    observed_utc = _utc_now_iso()

    actions = _read_csv_required(ACTION_OUTCOMES_PATH)
    scrape_gap = _read_csv_required(SCRAPE_GAP_PATH)
    alignment = _read_csv_required(ALIGNMENT_PATH)
    factors = _read_csv_required(FACTOR_PATH)
    health = _read_csv_required(HEALTH_PATH)

    rows: list[dict[str, str]] = []

    action_total = float(len(actions.index))
    write_applied = float((_column_as_text(actions, "write_applied_flag") == "1").sum()) if not actions.empty else 0.0
    change_decision = float((_column_as_text(actions, "decision_to_change_price_flag") == "1").sum()) if not actions.empty else 0.0
    readonly_rows = float((_column_as_text(actions, "writer_outcome") == "READ_ONLY_NO_WRITE").sum()) if not actions.empty else 0.0
    seller_values = [_to_float(value) for value in actions.get("seller_count", pd.Series([], dtype=str)).tolist()]
    seller_values = [value for value in seller_values if value is not None]
    avg_seller = sum(seller_values) / len(seller_values) if seller_values else 0.0

    rows.append(_metric_row(observed_utc=observed_utc, section="h_action", metric_key="action_total_rows", metric_value=str(int(action_total)), metric_text="Total action outcome rows", source_path=ACTION_OUTCOMES_PATH))
    rows.append(_metric_row(observed_utc=observed_utc, section="h_action", metric_key="write_applied_rows", metric_value=str(int(write_applied)), metric_text="Rows where write_applied_flag=1", source_path=ACTION_OUTCOMES_PATH))
    rows.append(_metric_row(observed_utc=observed_utc, section="h_action", metric_key="write_applied_rate", metric_value=_pct(write_applied, action_total), metric_text="Applied writes / action rows", source_path=ACTION_OUTCOMES_PATH))
    rows.append(_metric_row(observed_utc=observed_utc, section="h_action", metric_key="decision_change_rate", metric_value=_pct(change_decision, action_total), metric_text="Decision-to-change / action rows", source_path=ACTION_OUTCOMES_PATH))
    rows.append(_metric_row(observed_utc=observed_utc, section="h_action", metric_key="read_only_rows", metric_value=str(int(readonly_rows)), metric_text="Rows with writer_outcome=READ_ONLY_NO_WRITE", source_path=ACTION_OUTCOMES_PATH))
    rows.append(_metric_row(observed_utc=observed_utc, section="h_action", metric_key="avg_seller_count", metric_value=f"{avg_seller:.4f}", metric_text="Average seller_count in action outcomes", source_path=ACTION_OUTCOMES_PATH))

    scrape_total = float(len(scrape_gap.index))
    missing_rows = float((_column_as_text(scrape_gap, "scrape_coverage_status") == "missing").sum()) if not scrape_gap.empty else 0.0
    stale_rows = float((_column_as_text(scrape_gap, "scrape_coverage_status") == "stale").sum()) if not scrape_gap.empty else 0.0
    thin_rows = float((_column_as_text(scrape_gap, "scrape_coverage_status") == "thin").sum()) if not scrape_gap.empty else 0.0
    ok_rows = float((_column_as_text(scrape_gap, "scrape_coverage_status") == "ok").sum()) if not scrape_gap.empty else 0.0
    rows.append(_metric_row(observed_utc=observed_utc, section="scrape_coverage", metric_key="coverage_rows_total", metric_value=str(int(scrape_total)), metric_text="Total scrape-gap rows", source_path=SCRAPE_GAP_PATH))
    rows.append(_metric_row(observed_utc=observed_utc, section="scrape_coverage", metric_key="missing_rate", metric_value=_pct(missing_rows, scrape_total), metric_text="Missing status share", source_path=SCRAPE_GAP_PATH))
    rows.append(_metric_row(observed_utc=observed_utc, section="scrape_coverage", metric_key="stale_rate", metric_value=_pct(stale_rows, scrape_total), metric_text="Stale status share", source_path=SCRAPE_GAP_PATH))
    rows.append(_metric_row(observed_utc=observed_utc, section="scrape_coverage", metric_key="thin_rate", metric_value=_pct(thin_rows, scrape_total), metric_text="Thin status share", source_path=SCRAPE_GAP_PATH))
    rows.append(_metric_row(observed_utc=observed_utc, section="scrape_coverage", metric_key="ok_rate", metric_value=_pct(ok_rows, scrape_total), metric_text="OK status share", source_path=SCRAPE_GAP_PATH))

    alignment_total = float(len(alignment.index))
    missing_expected_rows = float((_column_as_text(alignment, "dominant_discrepancy_class") == "missing_expected_baseline").sum()) if not alignment.empty else 0.0
    expected_units_non_blank = float((_column_as_text(alignment, "expected_units_30d") != "").sum()) if not alignment.empty else 0.0
    expected_units_coverage = _pct(expected_units_non_blank, alignment_total)
    expected_primary_coverage = "0.0000"
    expected_no_source_rate = "0.0000"
    if not alignment.empty and "expected_units_source" in alignment.columns:
        source_series = _column_as_text(alignment, "expected_units_source")
        primary_sources = {"assumption_candidate_sku_asin", "sales_validation_asin", "full_capture_asin"}
        primary_rows = float(
            ((_column_as_text(alignment, "expected_units_30d") != "") & source_series.isin(primary_sources)).sum()
        )
        no_source_rows = float(source_series.isin({"", "no_source"}).sum())
        expected_primary_coverage = _pct(primary_rows, alignment_total)
        expected_no_source_rate = _pct(no_source_rows, alignment_total)
    rows.append(_metric_row(observed_utc=observed_utc, section="alignment", metric_key="alignment_rows_total", metric_value=str(int(alignment_total)), metric_text="Total alignment rows", source_path=ALIGNMENT_PATH))
    rows.append(_metric_row(observed_utc=observed_utc, section="alignment", metric_key="missing_expected_class_rate", metric_value=_pct(missing_expected_rows, alignment_total), metric_text="Share of alignment rows in missing_expected_baseline", source_path=ALIGNMENT_PATH))
    rows.append(_metric_row(observed_utc=observed_utc, section="alignment", metric_key="expected_units_coverage_rate", metric_value=expected_units_coverage, metric_text="Share of alignment rows with expected_units_30d populated", source_path=ALIGNMENT_PATH))
    rows.append(_metric_row(observed_utc=observed_utc, section="alignment", metric_key="expected_units_primary_coverage_rate", metric_value=expected_primary_coverage, metric_text="Share of alignment rows with primary-source expected units (assumption/sales/full-capture)", source_path=ALIGNMENT_PATH))
    rows.append(_metric_row(observed_utc=observed_utc, section="alignment", metric_key="expected_units_no_source_rate", metric_value=expected_no_source_rate, metric_text="Share of alignment rows with expected_units_source blank or no_source", source_path=ALIGNMENT_PATH))

    trigger_flag = "0"
    trigger_reason = "none"
    if not factors.empty:
        flags = set(_column_as_text(factors, "rescrape_trigger_flag").tolist())
        trigger_flag = "1" if "1" in flags else "0"
        reasons = [
            _normalize_text(value)
            for value in _column_as_text(factors, "rescrape_trigger_reason").tolist()
            if _normalize_text(value) not in {"", "none"}
        ]
        if reasons:
            trigger_reason = sorted(set(reasons))[0]
    rows.append(_metric_row(observed_utc=observed_utc, section="factor", metric_key="rescrape_trigger_flag", metric_value=trigger_flag, metric_text="Any factor bucket requested rescrape trigger", source_path=FACTOR_PATH))
    rows.append(_metric_row(observed_utc=observed_utc, section="factor", metric_key="rescrape_trigger_reason", metric_value=trigger_reason, metric_text="Primary trigger reason", source_path=FACTOR_PATH))

    fail_count = int((_column_as_text(health, "status") == "fail").sum()) if not health.empty else 0
    warn_count = int((_column_as_text(health, "status") == "warn").sum()) if not health.empty else 0
    ok_count = int((_column_as_text(health, "status") == "ok").sum()) if not health.empty else 0
    rows.append(_metric_row(observed_utc=observed_utc, section="health", metric_key="health_fail_count", metric_value=str(fail_count), metric_text="Count of fail checks in health checklist", source_path=HEALTH_PATH))
    rows.append(_metric_row(observed_utc=observed_utc, section="health", metric_key="health_warn_count", metric_value=str(warn_count), metric_text="Count of warn checks in health checklist", source_path=HEALTH_PATH))
    rows.append(_metric_row(observed_utc=observed_utc, section="health", metric_key="health_ok_count", metric_value=str(ok_count), metric_text="Count of ok checks in health checklist", source_path=HEALTH_PATH))

    out_df = pd.DataFrame(rows, columns=["observed_utc", "section", "metric_key", "metric_value", "metric_text", "source_path"]).fillna("")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(output_path, index=False)

    return OperatorReportResult(
        output_path=output_path,
        rows=int(len(out_df.index)),
        health_fail_count=fail_count,
        health_warn_count=warn_count,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build HF operator report (Phase 5).")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output CSV path")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = build_operator_report(output_path=Path(args.output))
    print(f"operator_report_output_path={result.output_path}")
    print(f"operator_report_rows={result.rows}")
    print(f"operator_report_health_fail_count={result.health_fail_count}")
    print(f"operator_report_health_warn_count={result.health_warn_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
