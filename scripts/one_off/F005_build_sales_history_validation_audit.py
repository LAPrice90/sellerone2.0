from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCRAPE_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv"
DEFAULT_INPUT_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_backtest_input_view_live.csv"
DEFAULT_SUMMARY_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv"
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"


@dataclass(frozen=True)
class SalesHistoryValidationBuildResult:
    validation_df: pd.DataFrame
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


def _parse_month_key(label: object) -> tuple[int, int] | None:
    text = _normalize_text(label).lower()
    if text == "":
        return None
    month_map = {
        "jan": 1,
        "january": 1,
        "feb": 2,
        "february": 2,
        "mar": 3,
        "march": 3,
        "apr": 4,
        "april": 4,
        "may": 5,
        "jun": 6,
        "june": 6,
        "jul": 7,
        "july": 7,
        "aug": 8,
        "august": 8,
        "sep": 9,
        "sept": 9,
        "september": 9,
        "oct": 10,
        "october": 10,
        "nov": 11,
        "november": 11,
        "dec": 12,
        "december": 12,
    }

    for sep in ("/", "-"):
        parts = text.split(sep)
        if len(parts) == 2:
            left = _num_or_none(parts[0])
            right = _num_or_none(parts[1])
            if left is not None and right is not None:
                left_int = int(left)
                right_int = int(right)
                if 1 <= left_int <= 12:
                    year = right_int + 2000 if right_int < 100 else right_int
                    return (year, left_int)
                if left_int >= 2000 and 1 <= right_int <= 12:
                    return (left_int, right_int)

    chunks = text.replace("-", " ").replace("/", " ").split()
    if len(chunks) >= 2:
        month = month_map.get(chunks[0], 0)
        year_num = _num_or_none(chunks[1])
        if month and year_num is not None:
            year = int(year_num)
            if year < 100:
                year += 2000
            return (year, month)
    return None


def _month_key_to_label(month_key: tuple[int, int] | None) -> str:
    if month_key is None:
        return ""
    year, month = month_key
    if year <= 0 or not (1 <= month <= 12):
        return ""
    return f"{year:04d}-{month:02d}"


def _split_pipe(value: object) -> list[str]:
    raw = _normalize_text(value)
    if raw == "":
        return []
    return [chunk.strip() for chunk in raw.split("|")]


def _pick_latest_scrape_rows(scrape_df: pd.DataFrame) -> pd.DataFrame:
    if scrape_df.empty:
        return scrape_df
    work = scrape_df.copy()
    work["asin_norm"] = work.get("asin", "").map(_normalize_key)
    work["supplier_sku_norm"] = work.get("supplier_sku", "").map(_normalize_key)
    work["_observed_ts"] = pd.to_datetime(work.get("observed_utc", "").map(_normalize_text), errors="coerce")
    work = work.sort_values("_observed_ts", ascending=False, kind="stable")
    deduped = work.drop_duplicates(subset=["asin_norm", "supplier_sku_norm"], keep="first")
    return deduped.drop(columns=["asin_norm", "supplier_sku_norm", "_observed_ts"], errors="ignore").reset_index(drop=True)


def _index_latest_input_rows(input_df: pd.DataFrame) -> dict[tuple[str, str], dict[str, str]]:
    if input_df.empty:
        return {}
    work = input_df.copy()
    work["asin_norm"] = work.get("asin", "").map(_normalize_key)
    work["seller_sku_norm"] = work.get("seller_sku", "").map(_normalize_key)
    work["_observed_ts"] = pd.to_datetime(work.get("observed_utc", "").map(_normalize_text), errors="coerce")
    work = work.sort_values("_observed_ts", ascending=False, kind="stable")
    out: dict[tuple[str, str], dict[str, str]] = {}
    for _, row in work.iterrows():
        key = (_normalize_key(row.get("asin", "")), _normalize_key(row.get("seller_sku", "")))
        if key in out:
            continue
        out[key] = {column: _normalize_text(value) for column, value in row.to_dict().items()}
    return out


def _index_latest_summary_rows(summary_df: pd.DataFrame) -> dict[tuple[str, str], dict[str, str]]:
    if summary_df.empty:
        return {}
    work = summary_df.copy()
    work["asin_norm"] = work.get("asin", "").map(_normalize_key)
    work["seller_sku_norm"] = work.get("seller_sku", "").map(_normalize_key)
    work["_observed_ts"] = pd.to_datetime(work.get("observed_utc", "").map(_normalize_text), errors="coerce")
    work = work.sort_values("_observed_ts", ascending=False, kind="stable")
    out: dict[tuple[str, str], dict[str, str]] = {}
    for _, row in work.iterrows():
        key = (_normalize_key(row.get("asin", "")), _normalize_key(row.get("seller_sku", "")))
        if key in out:
            continue
        out[key] = {column: _normalize_text(value) for column, value in row.to_dict().items()}
    return out


def _month_classification(
    *,
    month_iso: str,
    month_key: tuple[int, int] | None,
    current_key: tuple[int, int] | None,
    last_completed_iso: str,
    future_tail_start: int,
    point_index: int,
) -> str:
    if month_iso != "" and month_iso == last_completed_iso:
        return "last_completed"
    if month_key is not None and current_key is not None:
        if month_key > current_key:
            return "future_predicted"
        if month_key == current_key:
            return "current_partial"
        return "completed_history"
    if point_index >= future_tail_start:
        return "future_predicted"
    return "completed_history"


def build_sales_history_validation_audit(
    *,
    scrape_path: Path = DEFAULT_SCRAPE_PATH,
    input_path: Path = DEFAULT_INPUT_PATH,
    summary_path: Path = DEFAULT_SUMMARY_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    observed_utc: str | None = None,
) -> SalesHistoryValidationBuildResult:
    snapshot_utc = observed_utc or _utc_now_iso()
    scrape_df = _read_csv(scrape_path)
    input_df = _read_csv(input_path)
    summary_df = _read_csv(summary_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    ts_slug = _to_timestamp_slug(snapshot_utc)
    report_path = output_dir / f"f_sales_history_validation_{ts_slug}.csv"
    latest_path = output_dir / "f_sales_history_validation_latest.csv"

    if scrape_df.empty:
        empty_cols = [
            "observed_utc",
            "seller_sku",
            "asin",
            "amazon_link",
            "month_label",
            "month_label_iso",
            "month_units",
            "month_class",
            "trusted_for_demand_basis",
            "input_status",
            "input_reason_codes",
            "seasonality_state",
            "seasonality_reason_codes",
            "stability_state",
            "stability_reason_codes",
            "recent_vs_baseline_state",
            "recent_vs_baseline_reason_codes",
            "completed_months_count",
            "raw_observed_monthly_units",
            "price_qualified_monthly_units",
            "price_qualified_profit_monthly_gbp",
            "price_qualification_reason_codes",
            "qualification_market_gate_state",
            "qualification_market_gate_factor",
            "qualification_amazon_pressure_factor",
            "qualification_buy_box_coverage_factor",
            "qualification_maturity_factor",
            "qualification_final_factor",
            "qualification_zero_or_block_reason",
            "qualified_units_delta",
            "qualified_units_delta_share",
            "summary_status",
            "expected_units_source",
            "expected_profit_source",
            "decision_state",
            "decision_reason_codes",
            "decision_confidence",
            "decision_confidence_reason_codes",
            "summary_reason_codes",
            "summary_seasonality_state",
            "summary_seasonality_reason_codes",
            "summary_stability_state",
            "summary_stability_reason_codes",
            "summary_recent_vs_baseline_state",
            "summary_recent_vs_baseline_reason_codes",
            "summary_completed_months_count",
        ]
        empty_df = pd.DataFrame(columns=empty_cols)
        empty_df.to_csv(report_path, index=False)
        empty_df.to_csv(latest_path, index=False)
        print(
            json.dumps(
                {
                    "status": "success",
                    "observed_utc": snapshot_utc,
                    "listings_total": 0,
                    "rows_total": 0,
                    "csv_output": str(report_path),
                    "latest_csv": str(latest_path),
                }
            )
        )
        return SalesHistoryValidationBuildResult(validation_df=empty_df, report_path=report_path, latest_path=latest_path)

    latest_scrape_df = _pick_latest_scrape_rows(scrape_df)
    input_index = _index_latest_input_rows(input_df)
    summary_index = _index_latest_summary_rows(summary_df)

    rows: list[dict[str, str]] = []
    for _, scrape_row in latest_scrape_df.iterrows():
        asin = _normalize_text(scrape_row.get("asin", ""))
        seller_sku = _normalize_text(scrape_row.get("supplier_sku", ""))
        labels = _split_pipe(scrape_row.get("bbp_sales_chart_month_labels", ""))
        units_tokens = _split_pipe(scrape_row.get("bbp_sales_chart_month_units", ""))
        month_units: list[float | None] = [_num_or_none(token) for token in units_tokens]

        point_count = min(len(labels), len(month_units))
        labels = labels[:point_count]
        month_units = month_units[:point_count]

        last_completed_iso = _normalize_text(scrape_row.get("bbp_sales_last_completed_month_label", ""))
        last_completed_key = _parse_month_key(last_completed_iso)
        if last_completed_iso == "" and last_completed_key is not None:
            last_completed_iso = _month_key_to_label(last_completed_key)
        current_iso = _normalize_text(scrape_row.get("bbp_sales_current_month_label", ""))
        current_key = _parse_month_key(current_iso)
        if current_iso == "" and current_key is not None:
            current_iso = _month_key_to_label(current_key)
        future_month_count = int(_num_or_none(scrape_row.get("bbp_sales_future_month_count_ignored", "")) or 0)
        future_month_count = max(future_month_count, 0)
        future_tail_start = max(point_count - future_month_count, 0)

        input_key = (_normalize_key(asin), _normalize_key(seller_sku))
        input_row = input_index.get(input_key, {})
        summary_row = summary_index.get(input_key, {})
        raw_observed_monthly_units = _num_or_none(input_row.get("demand_basis_units_monthly", ""))
        price_qualified_monthly_units = _num_or_none(input_row.get("price_qualified_units_monthly", ""))
        qualified_units_delta = None
        qualified_units_delta_share = None
        if raw_observed_monthly_units is not None and price_qualified_monthly_units is not None:
            qualified_units_delta = raw_observed_monthly_units - price_qualified_monthly_units
            if raw_observed_monthly_units > 0:
                qualified_units_delta_share = qualified_units_delta / raw_observed_monthly_units

        if point_count == 0 and last_completed_iso != "":
            point_count = 1
            labels = [last_completed_iso]
            month_units = [_num_or_none(scrape_row.get("bbp_sales_last_completed_month_units", ""))]
            future_tail_start = 1

        for idx in range(point_count):
            month_label = _normalize_text(labels[idx]) if idx < len(labels) else ""
            month_value = month_units[idx] if idx < len(month_units) else None
            month_key = _parse_month_key(month_label)
            month_iso = _month_key_to_label(month_key)
            if month_iso == "" and month_label == last_completed_iso:
                month_iso = last_completed_iso

            month_class = _month_classification(
                month_iso=month_iso,
                month_key=month_key,
                current_key=current_key,
                last_completed_iso=last_completed_iso,
                future_tail_start=future_tail_start,
                point_index=idx,
            )
            trusted_for_basis = "1" if month_class == "last_completed" else "0"
            completed_month_flag = "1" if month_class in {"last_completed", "completed_history"} else "0"
            predicted_or_future_flag = "1" if month_class == "future_predicted" else "0"

            rows.append(
                {
                    "observed_utc": snapshot_utc,
                    "scrape_observed_utc": _normalize_text(scrape_row.get("observed_utc", "")),
                    "seller_sku": seller_sku,
                    "asin": asin,
                    "amazon_link": _amazon_link(asin),
                    "month_index": str(idx + 1),
                    "months_total": str(point_count),
                    "month_label": month_label,
                    "month_label_iso": month_iso,
                    "month_units": _num_to_text(month_value),
                    "month_class": month_class,
                    "completed_month_flag": completed_month_flag,
                    "predicted_or_future_flag": predicted_or_future_flag,
                    "trusted_for_demand_basis": trusted_for_basis,
                    "bbp_sales_chart_source": _normalize_text(scrape_row.get("bbp_sales_chart_source", "")),
                    "bbp_sales_chart_series": _normalize_text(scrape_row.get("bbp_sales_chart_series", "")),
                    "bbp_sales_last_completed_month_label": last_completed_iso,
                    "bbp_sales_last_completed_month_units": _normalize_text(
                        scrape_row.get("bbp_sales_last_completed_month_units", "")
                    ),
                    "bbp_sales_current_month_label": current_iso,
                    "bbp_sales_current_month_units": _normalize_text(scrape_row.get("bbp_sales_current_month_units", "")),
                    "bbp_sales_future_month_count_ignored": str(future_month_count),
                    "bbp_sales_replay_demand_basis_source": _normalize_text(
                        scrape_row.get("bbp_sales_replay_demand_basis_source", "")
                    ),
                    "bbp_sales_replay_demand_basis_label": _normalize_text(
                        scrape_row.get("bbp_sales_replay_demand_basis_label", "")
                    ),
                    "bbp_sales_replay_demand_basis_units": _normalize_text(
                        scrape_row.get("bbp_sales_replay_demand_basis_units", "")
                    ),
                    "break_even": _normalize_text(scrape_row.get("break_even", "")),
                    "min_sell_price": _normalize_text(scrape_row.get("min_sell_price", "")),
                    "avg_30_day_price": _normalize_text(scrape_row.get("avg_30_day_price", "")),
                    "estimated_monthly_profit": _normalize_text(scrape_row.get("estimated_monthly_profit", "")),
                    "input_observed_utc": _normalize_text(input_row.get("observed_utc", "")),
                    "input_status": _normalize_text(input_row.get("input_status", "")),
                    "input_reason_codes": _normalize_text(input_row.get("input_reason_codes", "")),
                    "seasonality_state": _normalize_text(input_row.get("seasonality_state", "")),
                    "seasonality_reason_codes": _normalize_text(input_row.get("seasonality_reason_codes", "")),
                    "stability_state": _normalize_text(input_row.get("stability_state", "")),
                    "stability_reason_codes": _normalize_text(input_row.get("stability_reason_codes", "")),
                    "recent_vs_baseline_state": _normalize_text(input_row.get("recent_vs_baseline_state", "")),
                    "recent_vs_baseline_reason_codes": _normalize_text(
                        input_row.get("recent_vs_baseline_reason_codes", "")
                    ),
                    "completed_months_count": _normalize_text(input_row.get("completed_months_count", "")),
                    "demand_basis_source": _normalize_text(input_row.get("demand_basis_source", "")),
                    "demand_basis_units_monthly": _normalize_text(input_row.get("demand_basis_units_monthly", "")),
                    "demand_basis_month_label": _normalize_text(input_row.get("demand_basis_month_label", "")),
                    "raw_observed_monthly_units": _num_to_text(raw_observed_monthly_units),
                    "price_qualified_monthly_units": _num_to_text(price_qualified_monthly_units),
                    "price_qualified_profit_monthly_gbp": _normalize_text(
                        input_row.get("price_qualified_profit_monthly_gbp", "")
                    ),
                    "price_qualification_reason_codes": _normalize_text(
                        input_row.get("price_qualification_reason_codes", "")
                    ),
                    "qualification_market_gate_state": _normalize_text(
                        input_row.get("qualification_market_gate_state", "")
                    ),
                    "qualification_market_gate_factor": _normalize_text(
                        input_row.get("qualification_market_gate_factor", "")
                    ),
                    "qualification_amazon_pressure_factor": _normalize_text(
                        input_row.get("qualification_amazon_pressure_factor", "")
                    ),
                    "qualification_buy_box_coverage_factor": _normalize_text(
                        input_row.get("qualification_buy_box_coverage_factor", "")
                    ),
                    "qualification_maturity_factor": _normalize_text(
                        input_row.get("qualification_maturity_factor", "")
                    ),
                    "qualification_final_factor": _normalize_text(input_row.get("qualification_final_factor", "")),
                    "qualification_zero_or_block_reason": _normalize_text(
                        input_row.get("qualification_zero_or_block_reason", "")
                    ),
                    "qualified_units_delta": _num_to_text(qualified_units_delta),
                    "qualified_units_delta_share": _num_to_text(qualified_units_delta_share),
                    "summary_status": _normalize_text(summary_row.get("summary_status", "")),
                    "expected_units_source": _normalize_text(summary_row.get("expected_units_source", "")),
                    "expected_profit_source": _normalize_text(summary_row.get("expected_profit_source", "")),
                    "decision_state": _normalize_text(summary_row.get("decision_state", "")),
                    "decision_reason_codes": _normalize_text(summary_row.get("decision_reason_codes", "")),
                    "decision_confidence": _normalize_text(summary_row.get("decision_confidence", "")),
                    "decision_confidence_reason_codes": _normalize_text(
                        summary_row.get("decision_confidence_reason_codes", "")
                    ),
                    "summary_reason_codes": _normalize_text(summary_row.get("summary_reason_codes", "")),
                    "summary_seasonality_state": _normalize_text(summary_row.get("seasonality_state", "")),
                    "summary_seasonality_reason_codes": _normalize_text(summary_row.get("seasonality_reason_codes", "")),
                    "summary_stability_state": _normalize_text(summary_row.get("stability_state", "")),
                    "summary_stability_reason_codes": _normalize_text(summary_row.get("stability_reason_codes", "")),
                    "summary_recent_vs_baseline_state": _normalize_text(summary_row.get("recent_vs_baseline_state", "")),
                    "summary_recent_vs_baseline_reason_codes": _normalize_text(
                        summary_row.get("recent_vs_baseline_reason_codes", "")
                    ),
                    "summary_completed_months_count": _normalize_text(summary_row.get("completed_months_count", "")),
                }
            )

    validation_df = pd.DataFrame(rows)
    validation_df = validation_df.sort_values(
        by=["seller_sku", "asin", "month_index"],
        key=lambda s: s.map(lambda v: _normalize_text(v).upper()),
    ).reset_index(drop=True)
    validation_df.to_csv(report_path, index=False)
    validation_df.to_csv(latest_path, index=False)

    listings_total = int(len(latest_scrape_df))
    rows_total = int(len(validation_df))
    predicted_rows = int((validation_df.get("predicted_or_future_flag", "").map(_normalize_text) == "1").sum())
    trusted_rows = int((validation_df.get("trusted_for_demand_basis", "").map(_normalize_text) == "1").sum())
    qualified_delta_rows = int((validation_df.get("qualified_units_delta", "").map(_normalize_text) != "").sum())

    print(
        json.dumps(
            {
                "status": "success",
                "observed_utc": snapshot_utc,
                "listings_total": listings_total,
                "rows_total": rows_total,
                "predicted_rows": predicted_rows,
                "trusted_rows": trusted_rows,
                "qualified_delta_rows": qualified_delta_rows,
                "csv_output": str(report_path),
                "latest_csv": str(latest_path),
            }
        )
    )
    return SalesHistoryValidationBuildResult(
        validation_df=validation_df,
        report_path=report_path,
        latest_path=latest_path,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a listing-level monthly sales history validation dataset.")
    parser.add_argument("--scrape-path", default=str(DEFAULT_SCRAPE_PATH))
    parser.add_argument("--input-path", default=str(DEFAULT_INPUT_PATH))
    parser.add_argument("--summary-path", default=str(DEFAULT_SUMMARY_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--observed-utc", default=None, help="Override observed_utc in YYYY-MM-DDTHH:MM:SSZ.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_sales_history_validation_audit(
        scrape_path=Path(args.scrape_path),
        input_path=Path(args.input_path),
        summary_path=Path(args.summary_path),
        output_dir=Path(args.output_dir),
        observed_utc=args.observed_utc,
    )


if __name__ == "__main__":
    main()
