from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"
DEFAULT_ACCURACY_PATH = DEFAULT_OUTPUT_DIR / "f_sales_history_accuracy_pack_latest.csv"
DEFAULT_PANEL_SEED_PATH = ROOT / "plans" / "active" / "b-e-f-sales-feedback-loop-v1" / "COMMERCIAL_VALIDATION_PANEL_15.csv"
DEFAULT_EXPECTED_GROUP_COUNTS = {"big_pass": 5, "big_fail": 5, "on_the_line": 5}
DEFAULT_EXPECTED_TOTAL_ROWS = 15

GROUP_ORDER = {"big_pass": 0, "big_fail": 1, "on_the_line": 2}


@dataclass(frozen=True)
class CommercialValidationPanelResult:
    panel_df: pd.DataFrame
    summary_df: pd.DataFrame
    panel_path: Path
    panel_latest_path: Path
    summary_path: Path
    summary_latest_path: Path


PANEL_COLUMNS = [
    "observed_utc",
    "panel_group",
    "panel_rank",
    "asin",
    "seller_sku",
    "truth_decision_state",
    "actual_units_30d",
    "actual_profit_30d_gbp",
    "model_expected_units_next_30d",
    "model_expected_profit_next_30d_gbp",
    "demand_alignment_state",
    "profit_alignment_state",
    "model_side_evidence_state",
    "in_sold_capture_pack",
    "row_present_in_accuracy",
    "selection_reason",
]

SUMMARY_COLUMNS = ["observed_utc", "metric", "value"]


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


def _validate_seed_panel(
    panel_seed_df: pd.DataFrame,
    *,
    expected_group_counts: Mapping[str, int],
    expected_total_rows: int,
) -> None:
    if panel_seed_df.empty:
        raise ValueError("Validation panel seed is empty.")

    required_columns = {"panel_group", "panel_rank", "asin"}
    missing_columns = sorted(required_columns - set(panel_seed_df.columns))
    if missing_columns:
        raise ValueError(f"Validation panel seed missing required columns: {', '.join(missing_columns)}")

    if len(panel_seed_df.index) != expected_total_rows:
        raise ValueError(
            f"Validation panel seed row count mismatch: expected {expected_total_rows}, got {len(panel_seed_df.index)}."
        )

    asin_keys = panel_seed_df["asin"].map(_normalize_key)
    if (asin_keys == "").any():
        raise ValueError("Validation panel seed contains blank ASIN values.")
    if asin_keys.duplicated().any():
        raise ValueError("Validation panel seed contains duplicate ASIN values.")

    for group_name, expected_count in expected_group_counts.items():
        actual_count = int((panel_seed_df["panel_group"].map(_normalize_text) == group_name).sum())
        if actual_count != int(expected_count):
            raise ValueError(
                f"Validation panel seed group count mismatch for {group_name}: expected {expected_count}, got {actual_count}."
            )


def _latest_accuracy_by_asin(accuracy_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    if accuracy_df.empty:
        return {}
    work = accuracy_df.copy()
    work["_asin_key"] = work.get("asin", "").map(_normalize_key)
    work = work[work["_asin_key"] != ""].copy()
    if work.empty:
        return {}

    if "observed_utc" in work.columns:
        work["_obs_ts"] = pd.to_datetime(work.get("observed_utc", "").map(_normalize_text), errors="coerce", utc=True)
        work = work.sort_values("_obs_ts", ascending=False, kind="stable")

    out: dict[str, dict[str, str]] = {}
    for _, row in work.iterrows():
        asin_key = _normalize_key(row.get("_asin_key", ""))
        if asin_key == "" or asin_key in out:
            continue
        out[asin_key] = {column: _normalize_text(value) for column, value in row.to_dict().items()}
    return out


def build_commercial_validation_panel(
    *,
    accuracy_path: Path = DEFAULT_ACCURACY_PATH,
    panel_seed_path: Path = DEFAULT_PANEL_SEED_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    expected_group_counts: Mapping[str, int] | None = None,
    expected_total_rows: int = DEFAULT_EXPECTED_TOTAL_ROWS,
    observed_utc: str | None = None,
) -> CommercialValidationPanelResult:
    snapshot_utc = observed_utc or _utc_now_iso()
    ts_slug = _to_timestamp_slug(snapshot_utc)
    output_dir.mkdir(parents=True, exist_ok=True)

    panel_path = output_dir / f"f_live_test_validation_panel_15_{ts_slug}.csv"
    panel_latest_path = output_dir / "f_live_test_validation_panel_15_latest.csv"
    summary_path = output_dir / f"f_live_test_validation_panel_15_summary_{ts_slug}.csv"
    summary_latest_path = output_dir / "f_live_test_validation_panel_15_summary_latest.csv"

    group_counts = dict(expected_group_counts or DEFAULT_EXPECTED_GROUP_COUNTS)
    accuracy_df = _read_csv(accuracy_path)
    panel_seed_df = _read_csv(panel_seed_path)

    _validate_seed_panel(
        panel_seed_df,
        expected_group_counts=group_counts,
        expected_total_rows=int(expected_total_rows),
    )

    accuracy_by_asin = _latest_accuracy_by_asin(accuracy_df)

    rows: list[dict[str, str]] = []
    for _, seed_row in panel_seed_df.iterrows():
        asin = _normalize_key(seed_row.get("asin", ""))
        live_row = accuracy_by_asin.get(asin, {})
        row_present = "1" if live_row else "0"

        seller_sku = _normalize_text(live_row.get("seller_sku", seed_row.get("seller_sku", "")))
        truth_decision_state = _normalize_text(
            live_row.get("truth_decision_state", seed_row.get("truth_decision_state", ""))
        )
        actual_units_30d = _normalize_text(live_row.get("actual_units_30d", seed_row.get("actual_units_30d", "")))
        actual_profit_30d_gbp = _normalize_text(
            live_row.get("actual_profit_30d_gbp", seed_row.get("actual_profit_30d_gbp", ""))
        )
        model_expected_units_next_30d = _normalize_text(
            live_row.get("model_expected_units_next_30d", seed_row.get("model_expected_units_next_30d", ""))
        )
        model_expected_profit_next_30d_gbp = _normalize_text(
            live_row.get(
                "model_expected_profit_next_30d_gbp",
                seed_row.get("model_expected_profit_next_30d_gbp", ""),
            )
        )
        demand_alignment_state = _normalize_text(
            live_row.get("demand_alignment_state", seed_row.get("demand_alignment_state", ""))
        )
        profit_alignment_state = _normalize_text(
            live_row.get("profit_alignment_state", seed_row.get("profit_alignment_state", ""))
        )
        model_side_evidence_state = _normalize_text(
            live_row.get("model_side_evidence_state", seed_row.get("model_side_evidence_state", ""))
        )
        in_sold_capture_pack = _normalize_text(
            live_row.get("in_sold_capture_pack", seed_row.get("in_sold_capture_pack", ""))
        )
        selection_reason = _normalize_text(seed_row.get("selection_reason", ""))
        if row_present == "0":
            if selection_reason == "":
                selection_reason = "missing_from_accuracy_pack"
            else:
                selection_reason = f"{selection_reason};missing_from_accuracy_pack"

        rows.append(
            {
                "observed_utc": snapshot_utc,
                "panel_group": _normalize_text(seed_row.get("panel_group", "")),
                "panel_rank": _normalize_text(seed_row.get("panel_rank", "")),
                "asin": asin,
                "seller_sku": seller_sku,
                "truth_decision_state": truth_decision_state,
                "actual_units_30d": actual_units_30d,
                "actual_profit_30d_gbp": actual_profit_30d_gbp,
                "model_expected_units_next_30d": model_expected_units_next_30d,
                "model_expected_profit_next_30d_gbp": model_expected_profit_next_30d_gbp,
                "demand_alignment_state": demand_alignment_state,
                "profit_alignment_state": profit_alignment_state,
                "model_side_evidence_state": model_side_evidence_state,
                "in_sold_capture_pack": in_sold_capture_pack,
                "row_present_in_accuracy": row_present,
                "selection_reason": selection_reason,
            }
        )

    panel_df = pd.DataFrame(rows, columns=PANEL_COLUMNS)
    panel_df["_group_order"] = panel_df["panel_group"].map(lambda value: GROUP_ORDER.get(_normalize_text(value), 99))
    panel_df["_rank_num"] = pd.to_numeric(panel_df["panel_rank"].map(_normalize_text), errors="coerce").fillna(9999)
    panel_df = panel_df.sort_values(["_group_order", "_rank_num", "asin"], kind="stable").reset_index(drop=True)
    panel_df = panel_df.drop(columns=["_group_order", "_rank_num"], errors="ignore")

    group_metric_rows: list[dict[str, str]] = []
    for group_name in ["big_pass", "big_fail", "on_the_line"]:
        group_count = int((panel_df["panel_group"].map(_normalize_text) == group_name).sum())
        group_metric_rows.append(
            {"observed_utc": snapshot_utc, "metric": f"{group_name}_rows", "value": str(group_count)}
        )
    missing_rows = int((panel_df["row_present_in_accuracy"].map(_normalize_text) == "0").sum())
    summary_df = pd.DataFrame(
        [
            {"observed_utc": snapshot_utc, "metric": "panel_rows_total", "value": str(int(len(panel_df.index)))},
            {"observed_utc": snapshot_utc, "metric": "panel_missing_rows", "value": str(missing_rows)},
        ]
        + group_metric_rows,
        columns=SUMMARY_COLUMNS,
    )

    panel_df.to_csv(panel_path, index=False)
    panel_df.to_csv(panel_latest_path, index=False)
    summary_df.to_csv(summary_path, index=False)
    summary_df.to_csv(summary_latest_path, index=False)

    print(
        json.dumps(
            {
                "status": "success",
                "observed_utc": snapshot_utc,
                "panel_rows_total": int(len(panel_df.index)),
                "panel_missing_rows": missing_rows,
                "big_pass_rows": int((panel_df["panel_group"].map(_normalize_text) == "big_pass").sum()),
                "big_fail_rows": int((panel_df["panel_group"].map(_normalize_text) == "big_fail").sum()),
                "on_the_line_rows": int((panel_df["panel_group"].map(_normalize_text) == "on_the_line").sum()),
                "panel_csv_output": str(panel_path),
                "panel_latest_csv": str(panel_latest_path),
                "summary_csv_output": str(summary_path),
                "summary_latest_csv": str(summary_latest_path),
            }
        )
    )

    return CommercialValidationPanelResult(
        panel_df=panel_df,
        summary_df=summary_df,
        panel_path=panel_path,
        panel_latest_path=panel_latest_path,
        summary_path=summary_path,
        summary_latest_path=summary_latest_path,
    )


def _parse_group_counts(raw: str) -> dict[str, int]:
    group_counts: dict[str, int] = {}
    token = _normalize_text(raw)
    if token == "":
        return dict(DEFAULT_EXPECTED_GROUP_COUNTS)
    parts = [part for part in token.split(",") if _normalize_text(part) != ""]
    for part in parts:
        if ":" not in part:
            raise ValueError(f"Invalid expected group counts token: {part}")
        key, value = part.split(":", 1)
        group_key = _normalize_text(key)
        group_value = int(float(_normalize_text(value)))
        group_counts[group_key] = group_value
    return group_counts


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build fixed 15-SKU commercial validation panel with live sold-truth values.")
    parser.add_argument("--accuracy-path", default=str(DEFAULT_ACCURACY_PATH))
    parser.add_argument("--panel-seed-path", default=str(DEFAULT_PANEL_SEED_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--expected-total-rows", default=str(DEFAULT_EXPECTED_TOTAL_ROWS))
    parser.add_argument(
        "--expected-group-counts",
        default="big_pass:5,big_fail:5,on_the_line:5",
        help="Comma-separated mapping like big_pass:5,big_fail:5,on_the_line:5",
    )
    parser.add_argument("--observed-utc", default=None, help="Override observed_utc in YYYY-MM-DDTHH:MM:SSZ.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    expected_group_counts = _parse_group_counts(args.expected_group_counts)
    build_commercial_validation_panel(
        accuracy_path=Path(args.accuracy_path),
        panel_seed_path=Path(args.panel_seed_path),
        output_dir=Path(args.output_dir),
        expected_group_counts=expected_group_counts,
        expected_total_rows=int(args.expected_total_rows),
        observed_utc=args.observed_utc,
    )


if __name__ == "__main__":
    main()
