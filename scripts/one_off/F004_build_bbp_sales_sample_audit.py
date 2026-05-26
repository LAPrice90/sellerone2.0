from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SAMPLE_PATH = ROOT / "out" / "analysis_reports" / "f_backtest_calibration_set_latest.csv"
DEFAULT_SCRAPE_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv"
DEFAULT_INPUT_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_backtest_input_view_live.csv"
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"


@dataclass(frozen=True)
class SampleAuditBuildResult:
    audit_df: pd.DataFrame
    report_path: Path
    latest_path: Path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_timestamp_slug(observed_utc: str) -> str:
    dt = datetime.strptime(observed_utc, "%Y-%m-%dT%H:%M:%SZ")
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _num_or_none(value: object) -> float | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    cleaned = raw.replace(",", "").replace("GBP", "").replace("gbp", "").replace("PS", "").replace("ps", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _num_to_text(value: float | None) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _amazon_link(asin: str) -> str:
    asin_key = _normalize_text(asin)
    if asin_key == "":
        return ""
    return f"https://www.amazon.co.uk/dp/{asin_key}"


def _sort_by_observed_utc_desc(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    work["_observed_ts"] = pd.to_datetime(work.get("observed_utc", "").map(_normalize_text), errors="coerce")
    work = work.sort_values("_observed_ts", ascending=False, kind="stable").drop(columns=["_observed_ts"], errors="ignore")
    return work


def _pick_scrape_row(scrape_df: pd.DataFrame, *, asin: str, seller_sku: str) -> pd.Series | None:
    if scrape_df.empty:
        return None
    asin_norm = _normalize_key(asin)
    sku_norm = _normalize_key(seller_sku)
    work = scrape_df.copy()
    work["asin_norm"] = work.get("asin", "").map(_normalize_key)
    work["supplier_sku_norm"] = work.get("supplier_sku", "").map(_normalize_key)
    work = work[work["asin_norm"] == asin_norm].copy()
    if work.empty:
        return None
    if sku_norm != "":
        match = work[work["supplier_sku_norm"] == sku_norm].copy()
        if not match.empty:
            return _sort_by_observed_utc_desc(match).iloc[0]
    return _sort_by_observed_utc_desc(work).iloc[0]


def _pick_input_row(input_df: pd.DataFrame, *, asin: str, seller_sku: str) -> pd.Series | None:
    if input_df.empty:
        return None
    asin_norm = _normalize_key(asin)
    sku_norm = _normalize_key(seller_sku)
    work = input_df.copy()
    work["asin_norm"] = work.get("asin", "").map(_normalize_key)
    work["seller_sku_norm"] = work.get("seller_sku", "").map(_normalize_key)
    work = work[work["asin_norm"] == asin_norm].copy()
    if work.empty:
        return None
    if sku_norm != "":
        match = work[work["seller_sku_norm"] == sku_norm].copy()
        if not match.empty:
            return _sort_by_observed_utc_desc(match).iloc[0]
    return _sort_by_observed_utc_desc(work).iloc[0]


def _mismatch_reason_codes(
    *,
    has_scrape_row: bool,
    has_input_row: bool,
    demand_basis_source: str,
    demand_basis_units_monthly: float | None,
    last_completed_units: float | None,
    future_month_count_ignored: float | None,
) -> list[str]:
    reasons: list[str] = []
    source = _normalize_text(demand_basis_source)
    last_completed = last_completed_units or 0.0
    future_ignored = future_month_count_ignored or 0.0

    if not has_scrape_row:
        reasons.append("missing_scrape_evidence_row")
    if not has_input_row:
        reasons.append("missing_input_view_row")
        return reasons

    if source == "":
        reasons.append("missing_demand_basis_source")
    if "future" in source:
        reasons.append("future_source_leak")

    if last_completed > 0:
        if source != "bbp_last_completed_month":
            reasons.append("demand_basis_not_last_completed_month")
        if demand_basis_units_monthly is None:
            reasons.append("demand_basis_units_missing")
        elif abs(demand_basis_units_monthly - last_completed) > 0.5:
            reasons.append("demand_basis_units_mismatch_last_completed")
        if source == "bbp_units_chosen_fallback":
            reasons.append("helper_chosen_leak")
    else:
        if source == "bbp_zero_history":
            if demand_basis_units_monthly is None:
                reasons.append("zero_history_units_missing")
            elif abs(demand_basis_units_monthly) > 0.5:
                reasons.append("zero_history_units_not_zero")
        if source == "bbp_units_chosen_fallback":
            reasons.append("helper_chosen_fallback_no_trusted_month")
        if source in {"bbp_current_month_fallback", "bbp_recent_history_fallback", "missing"}:
            reasons.append("fallback_basis_no_trusted_month")
        if future_ignored > 0 and source == "bbp_current_month_fallback":
            reasons.append("current_month_basis_with_future_present")

    deduped: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        if reason in seen:
            continue
        seen.add(reason)
        deduped.append(reason)
    return deduped


def build_bbp_sales_sample_audit(
    *,
    sample_path: Path = DEFAULT_SAMPLE_PATH,
    scrape_path: Path = DEFAULT_SCRAPE_PATH,
    input_path: Path = DEFAULT_INPUT_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    observed_utc: str | None = None,
) -> SampleAuditBuildResult:
    snapshot_utc = observed_utc or _utc_now_iso()
    sample_df = _read_csv(sample_path)
    scrape_df = _read_csv(scrape_path)
    input_df = _read_csv(input_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    ts_slug = _to_timestamp_slug(snapshot_utc)
    report_path = output_dir / f"f_backtest_bbp_sales_sample_audit_{ts_slug}.csv"
    latest_path = output_dir / "f_backtest_bbp_sales_sample_audit_latest.csv"

    if sample_df.empty:
        empty_cols = [
            "observed_utc",
            "sample_rank",
            "calibration_bucket",
            "seller_sku",
            "asin",
            "amazon_link",
            "mismatch_flag",
            "mismatch_reason_codes",
        ]
        empty_df = pd.DataFrame(columns=empty_cols)
        empty_df.to_csv(report_path, index=False)
        empty_df.to_csv(latest_path, index=False)
        print(
            json.dumps(
                {
                    "status": "success",
                    "observed_utc": snapshot_utc,
                    "sample_rows": 0,
                    "audit_rows": 0,
                    "mismatch_rows": 0,
                    "csv_output": str(report_path),
                    "latest_csv": str(latest_path),
                }
            )
        )
        return SampleAuditBuildResult(audit_df=empty_df, report_path=report_path, latest_path=latest_path)

    rows: list[dict[str, str]] = []
    for _, sample_row in sample_df.iterrows():
        seller_sku = _normalize_text(sample_row.get("seller_sku", ""))
        asin = _normalize_text(sample_row.get("asin", ""))

        scrape_row = _pick_scrape_row(scrape_df, asin=asin, seller_sku=seller_sku)
        input_row = _pick_input_row(input_df, asin=asin, seller_sku=seller_sku)

        has_scrape_row = scrape_row is not None
        has_input_row = input_row is not None

        demand_basis_source = _normalize_text(input_row.get("demand_basis_source", "")) if has_input_row else ""
        demand_basis_units_monthly = (
            _num_or_none(input_row.get("demand_basis_units_monthly", "")) if has_input_row else None
        )
        last_completed_units = (
            _num_or_none(input_row.get("bbp_sales_last_completed_month_units", "")) if has_input_row else None
        )
        future_month_count_ignored = (
            _num_or_none(input_row.get("bbp_sales_future_month_count_ignored", "")) if has_input_row else None
        )

        mismatch_reasons = _mismatch_reason_codes(
            has_scrape_row=has_scrape_row,
            has_input_row=has_input_row,
            demand_basis_source=demand_basis_source,
            demand_basis_units_monthly=demand_basis_units_monthly,
            last_completed_units=last_completed_units,
            future_month_count_ignored=future_month_count_ignored,
        )

        row = {
            "observed_utc": snapshot_utc,
            "sample_rank": _normalize_text(sample_row.get("calibration_rank", "")),
            "calibration_bucket": _normalize_text(sample_row.get("calibration_bucket", "")),
            "seller_sku": seller_sku,
            "asin": asin,
            "amazon_link": _amazon_link(asin),
            "scrape_observed_utc": _normalize_text(scrape_row.get("observed_utc", "")) if has_scrape_row else "",
            "bbp_sales_chart_source": _normalize_text(scrape_row.get("bbp_sales_chart_source", "")) if has_scrape_row else "",
            "bbp_sales_chart_series": _normalize_text(scrape_row.get("bbp_sales_chart_series", "")) if has_scrape_row else "",
            "bbp_sales_chart_month_labels": _normalize_text(scrape_row.get("bbp_sales_chart_month_labels", "")) if has_scrape_row else "",
            "bbp_sales_chart_month_units": _normalize_text(scrape_row.get("bbp_sales_chart_month_units", "")) if has_scrape_row else "",
            "bbp_sales_last_completed_month_label": _normalize_text(
                scrape_row.get("bbp_sales_last_completed_month_label", "")
            )
            if has_scrape_row
            else "",
            "bbp_sales_last_completed_month_units": _normalize_text(
                scrape_row.get("bbp_sales_last_completed_month_units", "")
            )
            if has_scrape_row
            else "",
            "bbp_sales_current_month_label": _normalize_text(scrape_row.get("bbp_sales_current_month_label", ""))
            if has_scrape_row
            else "",
            "bbp_sales_current_month_units": _normalize_text(scrape_row.get("bbp_sales_current_month_units", ""))
            if has_scrape_row
            else "",
            "bbp_sales_future_month_count_ignored": _normalize_text(
                scrape_row.get("bbp_sales_future_month_count_ignored", "")
            )
            if has_scrape_row
            else "",
            "bbp_monthly_units_chosen": _normalize_text(scrape_row.get("bbp_monthly_units_chosen", "")) if has_scrape_row else "",
            "bbp_monthly_sales_current": _normalize_text(scrape_row.get("bbp_monthly_sales_current", "")) if has_scrape_row else "",
            "bbp_monthly_sales_recent_avg": _normalize_text(scrape_row.get("bbp_monthly_sales_recent_avg", "")) if has_scrape_row else "",
            "demand_basis_source": demand_basis_source,
            "demand_basis_units_monthly": _num_to_text(demand_basis_units_monthly),
            "demand_basis_month_label": _normalize_text(input_row.get("demand_basis_month_label", "")) if has_input_row else "",
            "input_last_completed_month_units": _num_to_text(last_completed_units),
            "input_future_month_count_ignored": _num_to_text(future_month_count_ignored),
            "bbp_sales_replay_demand_basis_source": _normalize_text(
                input_row.get("bbp_sales_replay_demand_basis_source", "")
            )
            if has_input_row
            else "",
            "bbp_sales_replay_demand_basis_label": _normalize_text(
                input_row.get("bbp_sales_replay_demand_basis_label", "")
            )
            if has_input_row
            else "",
            "bbp_sales_replay_demand_basis_units": _normalize_text(
                input_row.get("bbp_sales_replay_demand_basis_units", "")
            )
            if has_input_row
            else "",
            "mismatch_flag": "1" if mismatch_reasons else "0",
            "mismatch_reason_codes": "|".join(mismatch_reasons),
        }
        rows.append(row)

    audit_df = pd.DataFrame(rows)
    audit_df = audit_df.sort_values(
        by=["sample_rank", "asin", "seller_sku"],
        key=lambda s: s.map(lambda v: _normalize_text(v).upper()),
    ).reset_index(drop=True)
    audit_df.to_csv(report_path, index=False)
    audit_df.to_csv(latest_path, index=False)

    mismatch_rows = int((audit_df.get("mismatch_flag", "").map(_normalize_text) == "1").sum())
    print(
        json.dumps(
            {
                "status": "success",
                "observed_utc": snapshot_utc,
                "sample_rows": int(len(sample_df)),
                "audit_rows": int(len(audit_df)),
                "mismatch_rows": mismatch_rows,
                "csv_output": str(report_path),
                "latest_csv": str(latest_path),
            }
        )
    )
    return SampleAuditBuildResult(audit_df=audit_df, report_path=report_path, latest_path=latest_path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a sampled-ASIN BBP sales chart audit export.")
    parser.add_argument("--sample-path", default=str(DEFAULT_SAMPLE_PATH))
    parser.add_argument("--scrape-path", default=str(DEFAULT_SCRAPE_PATH))
    parser.add_argument("--input-path", default=str(DEFAULT_INPUT_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--observed-utc", default=None, help="Override observed_utc in YYYY-MM-DDTHH:MM:SSZ.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_bbp_sales_sample_audit(
        sample_path=Path(args.sample_path),
        scrape_path=Path(args.scrape_path),
        input_path=Path(args.input_path),
        output_dir=Path(args.output_dir),
        observed_utc=args.observed_utc,
    )


if __name__ == "__main__":
    main()
