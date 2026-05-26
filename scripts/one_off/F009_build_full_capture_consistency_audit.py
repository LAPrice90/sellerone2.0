from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_PATH = ROOT / "out" / "analysis_reports" / "f_full_capture_manifest_latest.csv"
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"

STABLE_FIELDS = (
    "capture_status",
    "bbp_snapshot_loaded",
    "bbp_sales_chart_source",
    "bbp_sales_last_completed_month_label",
    "bbp_sales_last_completed_month_units",
    "bbp_sales_replay_demand_basis_source",
    "bbp_sales_replay_demand_basis_units",
    "completed_month_signature",
    "last_completed_signature",
)

ALLOWED_DRIFT_FIELDS = (
    "bbp_sales_current_month_units",
    "bbp_sales_current_month_label",
    "future_month_signature",
    "bbp_final_sell_price",
    "bbp_auto_sell_price",
    "monthly_sold_text",
    "estimated_monthly_profit",
)


@dataclass(frozen=True)
class FullCaptureConsistencyAuditResult:
    facts_df: pd.DataFrame
    monthly_points_df: pd.DataFrame
    discrepancies_df: pd.DataFrame
    facts_path: Path
    monthly_points_path: Path
    discrepancies_path: Path


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


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _split_pipe(value: object) -> list[str]:
    raw = _normalize_text(value)
    if raw == "":
        return []
    return [chunk.strip() for chunk in raw.split("|")]


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


def _parse_month_key(label: object) -> tuple[int, int] | None:
    text = _normalize_text(label).lower().replace("*", "")
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


def _is_predicted_label(label: str) -> bool:
    low = _normalize_text(label).lower()
    if low == "":
        return False
    if "*" in low:
        return True
    return any(token in low for token in ("predicted", "forecast", "projected", "estimate"))


def _month_classification(
    *,
    label: str,
    month_iso: str,
    month_key: tuple[int, int] | None,
    current_month_key: tuple[int, int] | None,
    last_completed_iso: str,
    future_tail_start: int,
    month_index: int,
) -> str:
    if _is_predicted_label(label):
        return "future_predicted"
    if month_iso != "" and month_iso == last_completed_iso:
        return "last_completed"
    if month_key is not None and current_month_key is not None:
        if month_key > current_month_key:
            return "future_predicted"
        if month_key == current_month_key:
            return "current_partial"
        return "completed_history"
    if month_index >= future_tail_start:
        return "future_predicted"
    return "completed_history"


def _build_monthly_rows(
    *,
    manifest_row: dict[str, str],
    scraped_data: dict[str, Any],
) -> list[dict[str, str]]:
    labels = _split_pipe(scraped_data.get("bbp_sales_chart_month_labels", ""))
    units_tokens = _split_pipe(scraped_data.get("bbp_sales_chart_month_units", ""))
    unit_values = [_num_or_none(token) for token in units_tokens]
    point_count = min(len(labels), len(unit_values))
    labels = labels[:point_count]
    unit_values = unit_values[:point_count]

    current_month_iso = _normalize_text(scraped_data.get("bbp_sales_current_month_label", ""))
    current_month_key = _parse_month_key(current_month_iso)
    if current_month_key is not None:
        current_month_iso = _month_key_to_label(current_month_key)
    last_completed_iso = _normalize_text(scraped_data.get("bbp_sales_last_completed_month_label", ""))
    if last_completed_iso != "":
        parsed_last_completed = _parse_month_key(last_completed_iso)
        if parsed_last_completed is not None:
            last_completed_iso = _month_key_to_label(parsed_last_completed)
    future_count = int(_num_or_none(scraped_data.get("bbp_sales_future_month_count_ignored", "")) or 0)
    future_count = max(future_count, 0)
    future_tail_start = max(point_count - future_count, 0)

    rows: list[dict[str, str]] = []
    for idx in range(point_count):
        label = _normalize_text(labels[idx])
        unit_value = unit_values[idx] if idx < len(unit_values) else None
        month_key = _parse_month_key(label)
        month_iso = _month_key_to_label(month_key)
        point_class = _month_classification(
            label=label,
            month_iso=month_iso,
            month_key=month_key,
            current_month_key=current_month_key,
            last_completed_iso=last_completed_iso,
            future_tail_start=future_tail_start,
            month_index=idx,
        )
        rows.append(
            {
                "observed_utc": _normalize_text(manifest_row.get("observed_utc", "")),
                "run_id": _normalize_text(manifest_row.get("run_id", "")),
                "asin": _normalize_text(manifest_row.get("asin", "")),
                "supplier_sku": _normalize_text(manifest_row.get("supplier_sku", "")),
                "validation_case": _normalize_text(manifest_row.get("validation_case", "")),
                "pass_index": _normalize_text(manifest_row.get("pass_index", "")),
                "month_index": str(idx + 1),
                "months_total": str(point_count),
                "month_label": label,
                "month_label_iso": month_iso,
                "month_units": _num_to_text(unit_value),
                "point_class": point_class,
                "trusted_for_demand_basis": "1" if point_class == "last_completed" else "0",
                "predicted_or_future_flag": "1" if point_class == "future_predicted" else "0",
            }
        )

    if point_count == 0 and last_completed_iso != "":
        rows.append(
            {
                "observed_utc": _normalize_text(manifest_row.get("observed_utc", "")),
                "run_id": _normalize_text(manifest_row.get("run_id", "")),
                "asin": _normalize_text(manifest_row.get("asin", "")),
                "supplier_sku": _normalize_text(manifest_row.get("supplier_sku", "")),
                "validation_case": _normalize_text(manifest_row.get("validation_case", "")),
                "pass_index": _normalize_text(manifest_row.get("pass_index", "")),
                "month_index": "1",
                "months_total": "1",
                "month_label": last_completed_iso,
                "month_label_iso": last_completed_iso,
                "month_units": _normalize_text(scraped_data.get("bbp_sales_last_completed_month_units", "")),
                "point_class": "last_completed",
                "trusted_for_demand_basis": "1",
                "predicted_or_future_flag": "0",
            }
        )
    return rows


def _series_signature(rows: list[dict[str, str]], *, point_class: str) -> str:
    values = []
    for row in rows:
        if _normalize_text(row.get("point_class", "")) != point_class:
            continue
        values.append(
            f"{_normalize_text(row.get('month_label_iso', ''))}:{_normalize_text(row.get('month_units', ''))}"
        )
    return "|".join(values)


def _discrepancy_class(field: str, *, baseline_value: str, compare_value: str) -> str:
    if field == "capture_status":
        if baseline_value != "success" or compare_value != "success":
            return "page_not_ready"
    if field == "bbp_sales_chart_source":
        if baseline_value == "" or compare_value == "":
            return "chart_not_loaded"
        return "html_shape_changed"
    if field in {"bbp_sales_current_month_units", "bbp_sales_current_month_label"}:
        return "current_month_drift"
    if field == "future_month_signature":
        return "future_prediction_drift"
    if field == "bbp_snapshot_loaded":
        return "field_missing_in_dom"
    if field == "monthly_sold_text":
        return "tooltip_dependency_unstable"
    if field in {"bbp_auto_sell_price", "bbp_final_sell_price", "estimated_monthly_profit"}:
        return "account_state_difference"
    return "unknown"


def build_full_capture_consistency_audit(
    *,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    observed_utc: str | None = None,
) -> FullCaptureConsistencyAuditResult:
    snapshot_utc = observed_utc or _utc_now_iso()
    manifest_df = _read_csv(manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    ts_slug = _to_timestamp_slug(snapshot_utc)
    facts_path = output_dir / f"f_full_capture_normalized_facts_{ts_slug}.csv"
    monthly_points_path = output_dir / f"f_full_capture_monthly_points_{ts_slug}.csv"
    discrepancies_path = output_dir / f"f_full_capture_discrepancies_{ts_slug}.csv"
    facts_latest_path = output_dir / "f_full_capture_normalized_facts_latest.csv"
    monthly_latest_path = output_dir / "f_full_capture_monthly_points_latest.csv"
    discrepancies_latest_path = output_dir / "f_full_capture_discrepancies_latest.csv"

    facts_rows: list[dict[str, str]] = []
    monthly_rows: list[dict[str, str]] = []
    per_run_month_rows: dict[str, list[dict[str, str]]] = {}

    for _, row in manifest_df.iterrows():
        manifest_row = {column: _normalize_text(value) for column, value in row.to_dict().items()}
        raw_path = Path(_normalize_text(manifest_row.get("raw_json_path", "")))
        payload = _read_json(raw_path)
        run_metadata = payload.get("run_metadata", {}) if isinstance(payload, dict) else {}
        if not isinstance(run_metadata, dict):
            run_metadata = {}
        scraped_data = payload.get("scraped_data", {}) if isinstance(payload, dict) else {}
        if not isinstance(scraped_data, dict):
            scraped_data = {}

        monthly_for_run = _build_monthly_rows(manifest_row=manifest_row, scraped_data=scraped_data)
        per_run_month_rows[_normalize_text(manifest_row.get("run_id", ""))] = monthly_for_run
        monthly_rows.extend(monthly_for_run)

        completed_signature = _series_signature(monthly_for_run, point_class="completed_history")
        last_completed_signature = _series_signature(monthly_for_run, point_class="last_completed")
        future_signature = _series_signature(monthly_for_run, point_class="future_predicted")

        facts_rows.append(
            {
                "observed_utc": _normalize_text(manifest_row.get("observed_utc", "")) or snapshot_utc,
                "run_id": _normalize_text(manifest_row.get("run_id", "")),
                "asin": _normalize_text(manifest_row.get("asin", "")),
                "supplier_sku": _normalize_text(manifest_row.get("supplier_sku", "")),
                "validation_case": _normalize_text(manifest_row.get("validation_case", "")),
                "sample_rank": _normalize_text(manifest_row.get("sample_rank", "")),
                "pass_index": _normalize_text(manifest_row.get("pass_index", "")),
                "capture_status": _normalize_text(manifest_row.get("capture_status", "")),
                "capture_error": _normalize_text(manifest_row.get("capture_error", "")),
                "bbp_snapshot_loaded": _normalize_text(manifest_row.get("bbp_snapshot_loaded", "")),
                "bbp_sales_chart_source": _normalize_text(scraped_data.get("bbp_sales_chart_source", "")),
                "bbp_sales_chart_series": _normalize_text(scraped_data.get("bbp_sales_chart_series", "")),
                "bbp_sales_last_completed_month_label": _normalize_text(
                    scraped_data.get("bbp_sales_last_completed_month_label", "")
                ),
                "bbp_sales_last_completed_month_units": _normalize_text(
                    scraped_data.get("bbp_sales_last_completed_month_units", "")
                ),
                "bbp_sales_current_month_label": _normalize_text(scraped_data.get("bbp_sales_current_month_label", "")),
                "bbp_sales_current_month_units": _normalize_text(scraped_data.get("bbp_sales_current_month_units", "")),
                "bbp_sales_future_month_count_ignored": _normalize_text(
                    scraped_data.get("bbp_sales_future_month_count_ignored", "")
                ),
                "bbp_sales_replay_demand_basis_source": _normalize_text(
                    scraped_data.get("bbp_sales_replay_demand_basis_source", "")
                ),
                "bbp_sales_replay_demand_basis_units": _normalize_text(
                    scraped_data.get("bbp_sales_replay_demand_basis_units", "")
                ),
                "monthly_sold_text": _normalize_text(scraped_data.get("monthly_sold", "")),
                "estimated_monthly_profit": _normalize_text(scraped_data.get("estimated_monthly_profit", "")),
                "bbp_auto_sell_price": _normalize_text(scraped_data.get("bbp_auto_sell_price", "")),
                "bbp_final_sell_price": _normalize_text(scraped_data.get("bbp_final_sell_price", "")),
                "completed_month_signature": completed_signature,
                "last_completed_signature": last_completed_signature,
                "future_month_signature": future_signature,
            }
        )

    facts_df = pd.DataFrame(facts_rows)
    if not facts_df.empty:
        facts_df = facts_df.sort_values(
            ["asin", "pass_index"],
            key=lambda s: s.map(lambda v: _normalize_text(v).upper()),
            kind="stable",
        ).reset_index(drop=True)
    monthly_points_df = pd.DataFrame(monthly_rows)
    if not monthly_points_df.empty:
        monthly_points_df = monthly_points_df.sort_values(
            ["asin", "pass_index", "month_index"],
            key=lambda s: s.map(lambda v: _normalize_text(v).upper()),
            kind="stable",
        ).reset_index(drop=True)

    discrepancies: list[dict[str, str]] = []
    if not facts_df.empty:
        for asin_key, group in facts_df.groupby(facts_df["asin"].map(_normalize_key), sort=False):
            if asin_key == "":
                continue
            group_sorted = group.copy()
            group_sorted["_pass_num"] = pd.to_numeric(group_sorted["pass_index"], errors="coerce")
            group_sorted = group_sorted.sort_values("_pass_num", ascending=True, kind="stable").drop(
                columns=["_pass_num"], errors="ignore"
            )
            if group_sorted.empty:
                continue
            baseline = {column: _normalize_text(value) for column, value in group_sorted.iloc[0].to_dict().items()}
            baseline_run_id = _normalize_text(baseline.get("run_id", ""))
            for idx in range(1, len(group_sorted)):
                compare = {column: _normalize_text(value) for column, value in group_sorted.iloc[idx].to_dict().items()}
                compare_run_id = _normalize_text(compare.get("run_id", ""))
                for field in [*STABLE_FIELDS, *ALLOWED_DRIFT_FIELDS]:
                    base_value = _normalize_text(baseline.get(field, ""))
                    cmp_value = _normalize_text(compare.get(field, ""))
                    if base_value == cmp_value:
                        continue
                    allowed = field in ALLOWED_DRIFT_FIELDS
                    discrepancies.append(
                        {
                            "observed_utc": snapshot_utc,
                            "asin": _normalize_text(compare.get("asin", "")),
                            "supplier_sku": _normalize_text(compare.get("supplier_sku", "")),
                            "baseline_run_id": baseline_run_id,
                            "compare_run_id": compare_run_id,
                            "baseline_pass_index": _normalize_text(baseline.get("pass_index", "")),
                            "compare_pass_index": _normalize_text(compare.get("pass_index", "")),
                            "field_name": field,
                            "baseline_value": base_value,
                            "compare_value": cmp_value,
                            "allowed_drift_flag": "1" if allowed else "0",
                            "discrepancy_class": _discrepancy_class(
                                field,
                                baseline_value=base_value,
                                compare_value=cmp_value,
                            ),
                        }
                    )

    discrepancies_df = pd.DataFrame(discrepancies)
    if not discrepancies_df.empty:
        discrepancies_df = discrepancies_df.sort_values(
            ["asin", "compare_pass_index", "field_name"],
            key=lambda s: s.map(lambda v: _normalize_text(v).upper()),
            kind="stable",
        ).reset_index(drop=True)

    facts_df.to_csv(facts_path, index=False)
    monthly_points_df.to_csv(monthly_points_path, index=False)
    discrepancies_df.to_csv(discrepancies_path, index=False)
    facts_df.to_csv(facts_latest_path, index=False)
    monthly_points_df.to_csv(monthly_latest_path, index=False)
    discrepancies_df.to_csv(discrepancies_latest_path, index=False)

    print(
        json.dumps(
            {
                "status": "success",
                "observed_utc": snapshot_utc,
                "manifest_path": str(manifest_path),
                "facts_rows": int(len(facts_df)),
                "monthly_points_rows": int(len(monthly_points_df)),
                "discrepancy_rows": int(len(discrepancies_df)),
                "facts_path": str(facts_path),
                "monthly_points_path": str(monthly_points_path),
                "discrepancies_path": str(discrepancies_path),
                "facts_latest_path": str(facts_latest_path),
                "monthly_latest_path": str(monthly_latest_path),
                "discrepancies_latest_path": str(discrepancies_latest_path),
            }
        )
    )
    return FullCaptureConsistencyAuditResult(
        facts_df=facts_df,
        monthly_points_df=monthly_points_df,
        discrepancies_df=discrepancies_df,
        facts_path=facts_path,
        monthly_points_path=monthly_points_path,
        discrepancies_path=discrepancies_path,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build normalized facts, month-level points, and 3-pass discrepancy report "
            "from full capture manifest raw JSON artifacts."
        )
    )
    parser.add_argument("--manifest-path", default=str(DEFAULT_MANIFEST_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--observed-utc", default=None, help="Override observed_utc in YYYY-MM-DDTHH:MM:SSZ.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_full_capture_consistency_audit(
        manifest_path=Path(args.manifest_path),
        output_dir=Path(args.output_dir),
        observed_utc=args.observed_utc,
    )


if __name__ == "__main__":
    main()
