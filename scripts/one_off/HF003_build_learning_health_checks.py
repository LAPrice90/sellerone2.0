from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_health_checklist_latest.csv"

IDENTITY_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_identity_bridge_latest.csv"
ASSUMPTION_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_assumption_snapshots_latest.csv"
FOUNDATION_METRICS_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_foundation_metrics_latest.csv"
MARKET_FACTS_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_market_facts_latest.csv"
ACTION_OUTCOMES_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_action_outcomes_latest.csv"
SCRAPE_GAP_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_scrape_gap_report_latest.csv"
ALIGNMENT_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_alignment_30d_latest.csv"
FACTOR_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_factor_impacts_latest.csv"

REQUIRED_PATHS = {
    "identity": IDENTITY_PATH,
    "assumption": ASSUMPTION_PATH,
    "foundation_metrics": FOUNDATION_METRICS_PATH,
    "market_facts": MARKET_FACTS_PATH,
    "action_outcomes": ACTION_OUTCOMES_PATH,
    "scrape_gap": SCRAPE_GAP_PATH,
    "alignment": ALIGNMENT_PATH,
    "factor": FACTOR_PATH,
}

REQUIRED_COLUMNS = {
    "identity": ["snapshot_utc", "candidate_id", "sku_resolution_status", "sku_resolution_source"],
    "assumption": ["snapshot_utc", "candidate_id", "snapshot_stage", "assumption_anchor_source"],
    "foundation_metrics": ["snapshot_utc", "metric_name", "metric_value"],
    "market_facts": ["observation_utc", "asof_date", "sku", "asin", "amazon_present_flag", "delivery_parity_flag"],
    "action_outcomes": ["event_ts_utc", "run_id", "sku", "asin", "eligible_to_write_flag", "write_applied_flag"],
    "scrape_gap": ["observed_utc", "candidate_id", "scrape_coverage_status", "rescrape_needed_flag", "queue_owner_path"],
    "alignment": ["alignment_window_end_utc", "sku", "asin", "dominant_discrepancy_class", "rescrape_signal_flag"],
    "factor": ["snapshot_utc", "factor_bucket", "sample_rows", "rescrape_trigger_flag", "rescrape_trigger_reason"],
}


@dataclass(frozen=True)
class HealthResult:
    checklist_path: Path
    rows: int
    fail_count: int
    warn_count: int
    ok_count: int


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


def _status_row(check: str, status: str, value: object, notes: str) -> dict[str, str]:
    return {
        "observed_utc": _utc_now_iso(),
        "check": check,
        "status": status,
        "value": _normalize_text(value),
        "notes": notes,
    }


def build_health_checklist(*, output_path: Path) -> HealthResult:
    datasets = {name: _read_csv(path) for name, path in REQUIRED_PATHS.items()}
    rows: list[dict[str, str]] = []

    for name, path in REQUIRED_PATHS.items():
        exists = "1" if path.exists() else "0"
        status = "ok" if exists == "1" else "fail"
        rows.append(
            _status_row(
                check=f"hf_{name}_path_exists",
                status=status,
                value=exists,
                notes=str(path),
            )
        )

    for name, required in REQUIRED_COLUMNS.items():
        df = datasets[name]
        missing = [column for column in required if column not in df.columns]
        if missing:
            rows.append(
                _status_row(
                    check=f"hf_{name}_schema",
                    status="fail",
                    value=str(len(missing)),
                    notes=f"missing_columns={','.join(missing)}",
                )
            )
        else:
            rows.append(
                _status_row(
                    check=f"hf_{name}_schema",
                    status="ok",
                    value="0",
                    notes="required columns present",
                )
            )

    for name, df in datasets.items():
        row_count = int(len(df.index))
        status = "ok" if row_count > 0 else "fail"
        rows.append(
            _status_row(
                check=f"hf_{name}_nonzero_rows",
                status=status,
                value=row_count,
                notes="row_count>0 required",
            )
        )

    alignment_df = datasets["alignment"]
    if not alignment_df.empty and "alignment_window_end_utc" in alignment_df.columns:
        alignment_times = pd.to_datetime(alignment_df["alignment_window_end_utc"], errors="coerce", utc=True)
        latest = alignment_times.max()
        status = "fail"
        value = ""
        notes = "no parseable timestamps"
        if pd.notna(latest):
            age = datetime.now(timezone.utc) - latest.to_pydatetime()
            value = f"{age.total_seconds() / 86400:.2f}"
            status = "ok" if age <= timedelta(days=30) else "fail"
            notes = "alignment age days"
        rows.append(_status_row("hf_alignment_freshness_30d", status, value, notes))
    else:
        rows.append(_status_row("hf_alignment_freshness_30d", "fail", "", "alignment missing or no timestamp column"))

    scrape_df = datasets["scrape_gap"]
    if not scrape_df.empty and "scrape_coverage_status" in scrape_df.columns:
        total = float(len(scrape_df.index))
        missing_count = float((scrape_df["scrape_coverage_status"] == "missing").sum())
        stale_count = float((scrape_df["scrape_coverage_status"] == "stale").sum())
        thin_count = float((scrape_df["scrape_coverage_status"] == "thin").sum())
        non_scraper_scope_count = float((scrape_df["scrape_coverage_status"] == "non_scraper_scope").sum())
        missing_rate = missing_count / total
        stale_rate = stale_count / total
        thin_rate = thin_count / total
        non_scraper_scope_rate = non_scraper_scope_count / total
        scraper_scope_total = max(total - non_scraper_scope_count, 0.0)
        missing_rate_scope_adjusted = (missing_count / scraper_scope_total) if scraper_scope_total > 0 else 0.0
        missing_status = "warn" if missing_rate > 0.80 else "ok"
        stale_status = "warn" if stale_rate > 0.10 else "ok"
        thin_status = "warn" if thin_rate > 0.05 else "ok"
        rows.append(_status_row("hf_scrape_gap_missing_rate", missing_status, f"{missing_rate:.4f}", "warn if > 0.80"))
        rows.append(
            _status_row(
                "hf_scrape_gap_non_scraper_scope_rate",
                "ok",
                f"{non_scraper_scope_rate:.4f}",
                "rows classified as non_scraper_scope / total rows",
            )
        )
        rows.append(
            _status_row(
                "hf_scrape_gap_missing_rate_scope_adjusted",
                "warn" if missing_rate_scope_adjusted > 0.80 else "ok",
                f"{missing_rate_scope_adjusted:.4f}",
                f"missing / scraper_scope_rows where scraper_scope_rows={int(scraper_scope_total)}",
            )
        )
        rows.append(_status_row("hf_scrape_gap_stale_rate", stale_status, f"{stale_rate:.4f}", "warn if > 0.10"))
        rows.append(_status_row("hf_scrape_gap_thin_rate", thin_status, f"{thin_rate:.4f}", "warn if > 0.05"))

        expected_trigger = "1" if (missing_rate > 0.80 or stale_rate > 0.10 or thin_rate > 0.05) else "0"
        factor_df = datasets["factor"]
        observed_trigger = "0"
        if not factor_df.empty and "rescrape_trigger_flag" in factor_df.columns:
            observed_values = set(factor_df["rescrape_trigger_flag"].map(_normalize_text).tolist())
            observed_trigger = "1" if "1" in observed_values else "0"
        trigger_status = "ok" if observed_trigger == expected_trigger else "fail"
        rows.append(
            _status_row(
                "hf_rescrape_trigger_consistency",
                trigger_status,
                observed_trigger,
                f"expected_trigger={expected_trigger}",
            )
        )
    else:
        rows.append(_status_row("hf_scrape_gap_missing_rate", "fail", "", "scrape gap missing"))
        rows.append(_status_row("hf_scrape_gap_non_scraper_scope_rate", "fail", "", "scrape gap missing"))
        rows.append(_status_row("hf_scrape_gap_missing_rate_scope_adjusted", "fail", "", "scrape gap missing"))
        rows.append(_status_row("hf_scrape_gap_stale_rate", "fail", "", "scrape gap missing"))
        rows.append(_status_row("hf_scrape_gap_thin_rate", "fail", "", "scrape gap missing"))
        rows.append(_status_row("hf_rescrape_trigger_consistency", "fail", "", "scrape gap missing"))

    if not alignment_df.empty and "expected_units_30d" in alignment_df.columns:
        expected_non_blank = (alignment_df["expected_units_30d"].map(_normalize_text) != "").sum()
        rate = float(expected_non_blank) / float(len(alignment_df.index))
        status = "warn" if rate < 0.20 else "ok"
        rows.append(
            _status_row(
                "hf_alignment_expected_coverage",
                status,
                f"{rate:.4f}",
                "warn if total expected_units_30d coverage < 0.20",
            )
        )

        if "expected_units_source" in alignment_df.columns:
            source_series = alignment_df["expected_units_source"].map(_normalize_text)
            primary_sources = {"assumption_candidate_sku_asin", "sales_validation_asin", "full_capture_asin"}
            primary_non_blank = int(
                ((alignment_df["expected_units_30d"].map(_normalize_text) != "") & source_series.isin(primary_sources)).sum()
            )
            primary_rate = float(primary_non_blank) / float(len(alignment_df.index))
            primary_status = "warn" if primary_rate < 0.20 else "ok"
            rows.append(
                _status_row(
                    "hf_alignment_expected_primary_coverage",
                    primary_status,
                    f"{primary_rate:.4f}",
                    "warn if primary-source (assumption/sales/full-capture) expected coverage < 0.20",
                )
            )

            none_source_rows = int(source_series.isin({"", "no_source"}).sum())
            none_source_rate = float(none_source_rows) / float(len(alignment_df.index))
            none_source_status = "warn" if none_source_rate > 0.80 else "ok"
            rows.append(
                _status_row(
                    "hf_alignment_expected_source_none_rate",
                    none_source_status,
                    f"{none_source_rate:.4f}",
                    "warn if expected_units_source=none rate > 0.80",
                )
            )
        else:
            rows.append(
                _status_row(
                    "hf_alignment_expected_primary_coverage",
                    "ok",
                    "",
                    "expected_units_source column not present",
                )
            )
            rows.append(
                _status_row(
                    "hf_alignment_expected_source_none_rate",
                    "ok",
                    "",
                    "expected_units_source column not present",
                )
            )
    else:
        rows.append(_status_row("hf_alignment_expected_coverage", "fail", "", "alignment missing expected_units_30d"))
        rows.append(_status_row("hf_alignment_expected_primary_coverage", "fail", "", "alignment missing expected_units_30d"))
        rows.append(_status_row("hf_alignment_expected_source_none_rate", "fail", "", "alignment missing expected_units_30d"))

    checklist_df = pd.DataFrame(rows, columns=["observed_utc", "check", "status", "value", "notes"]).fillna("")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    checklist_df.to_csv(output_path, index=False)

    fail_count = int((checklist_df["status"] == "fail").sum())
    warn_count = int((checklist_df["status"] == "warn").sum())
    ok_count = int((checklist_df["status"] == "ok").sum())
    return HealthResult(
        checklist_path=output_path,
        rows=int(len(checklist_df.index)),
        fail_count=fail_count,
        warn_count=warn_count,
        ok_count=ok_count,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build HF learning health checklist (Phase 3).")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output CSV path for checklist")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = build_health_checklist(output_path=Path(args.output))
    print(f"health_checklist_output_path={result.checklist_path}")
    print(f"health_checklist_rows={result.rows}")
    print(f"health_checklist_fail_count={result.fail_count}")
    print(f"health_checklist_warn_count={result.warn_count}")
    print(f"health_checklist_ok_count={result.ok_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
