from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
DEFAULT_OUTPUT_DIR = OUT / "analysis_reports"

ORDER_MASTER_PATH = OUT / "order_master.csv"
ORDER_LEDGER_FX_PATH = OUT / "order_ledger_fx.csv"
DAILY_TRUTH_PATH = OUT / "sku_daily_sales_truth_latest.csv"
SALES_TRUTH_30D_PATH = OUT / "sales_truth_sku_30d_latest.csv"
PERFORMANCE_PATH = OUT / "sku_performance_summary.csv"
LISTING_SNAPSHOT_PATH = OUT / "listing_offer_snapshot_latest.csv"
LISTING_HISTORY_PATH = OUT / "listing_offer_history.csv"

LAG_WARN_MINUTES = 90.0
LAG_FAIL_MINUTES = 240.0

FOUNDATION_COLUMNS = [
    "observed_utc",
    "operational_sku",
    "operational_asin",
    "asin_bridge_status",
    "asin_ambiguity_flag",
    "asin_candidate_count",
    "latest_finalized_date",
    "latest_provisional_date",
    "truth_state",
    "daily_truth_row_count",
    "in_order_master_flag",
    "in_daily_truth_flag",
    "in_performance_flag",
    "in_listing_scope_flag",
    "order_master_latest_utc",
    "order_ledger_fx_latest_utc",
    "order_master_to_ledger_lag_minutes",
    "ledger_freshness_status",
    "stale_flag",
    "sales_truth_30d_asof_date",
    "performance_asof_date",
]

HEALTH_COLUMNS = ["observed_utc", "metric", "value", "status", "notes"]


@dataclass(frozen=True)
class FoundationBuildResult:
    foundation_df: pd.DataFrame
    health_df: pd.DataFrame
    foundation_path: Path
    health_path: Path


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


def _column_as_text(df: pd.DataFrame, column: str) -> pd.Series:
    if column in df.columns:
        return df[column].map(_normalize_text)
    return pd.Series([""] * len(df.index), index=df.index, dtype=str)


def _to_float(value: object) -> float:
    text = _normalize_text(value)
    if text == "":
        return 0.0
    try:
        return float(text)
    except Exception:
        return 0.0


def _parse_utc_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True)


def _max_ts_iso(df: pd.DataFrame, column: str) -> str:
    if df.empty or column not in df.columns:
        return ""
    ts = _parse_utc_series(df[column])
    ts = ts.dropna()
    if ts.empty:
        return ""
    return ts.max().strftime("%Y-%m-%dT%H:%M:%SZ")


def _max_ts_from_candidates(df: pd.DataFrame, columns: tuple[str, ...]) -> str:
    if df.empty:
        return ""
    parsed_series: list[pd.Series] = []
    for column in columns:
        if column not in df.columns:
            continue
        parsed = _parse_utc_series(df[column]).dropna()
        if parsed.empty:
            continue
        parsed_series.append(parsed)
    if not parsed_series:
        return ""
    combined = pd.concat(parsed_series, ignore_index=True)
    if combined.empty:
        return ""
    return combined.max().strftime("%Y-%m-%dT%H:%M:%SZ")


def _max_date_text(df: pd.DataFrame, column: str) -> str:
    if df.empty or column not in df.columns:
        return ""
    values = [str(v).strip() for v in df[column].tolist() if str(v).strip()]
    return max(values) if values else ""


def _lag_status(order_master_latest_utc: str, order_ledger_latest_utc: str) -> tuple[str, str, str]:
    master_dt = _parse_utc_series(pd.Series([order_master_latest_utc])).iloc[0]
    ledger_dt = _parse_utc_series(pd.Series([order_ledger_latest_utc])).iloc[0]

    if pd.isna(master_dt) and pd.isna(ledger_dt):
        return "", "fail", "missing_order_master_and_order_ledger_fx_timestamps"
    if pd.isna(master_dt):
        return "", "warn", "missing_order_master_timestamp"
    if pd.isna(ledger_dt):
        return "", "fail", "missing_order_ledger_fx_timestamp"

    lag_minutes = float((master_dt - ledger_dt).total_seconds() / 60.0)
    if lag_minutes < 0:
        lag_minutes = 0.0
    lag_text = f"{lag_minutes:.2f}"
    if lag_minutes > LAG_FAIL_MINUTES:
        return lag_text, "fail", "lag_gt_fail_threshold"
    if lag_minutes > LAG_WARN_MINUTES:
        return lag_text, "warn", "lag_gt_warn_threshold"
    return lag_text, "ok", "lag_within_threshold"


def _build_listing_bridge(listing_snapshot_df: pd.DataFrame, listing_history_df: pd.DataFrame) -> pd.DataFrame:
    snapshot = pd.DataFrame()
    snapshot["sku"] = _column_as_text(listing_snapshot_df, "sku").str.upper()
    snapshot["asin"] = _column_as_text(listing_snapshot_df, "asin").str.upper()
    snapshot["event_utc"] = _column_as_text(listing_snapshot_df, "timestamp_utc")

    history = pd.DataFrame()
    history["sku"] = _column_as_text(listing_history_df, "sku").str.upper()
    history["asin"] = _column_as_text(listing_history_df, "asin").str.upper()
    history["event_utc"] = _column_as_text(listing_history_df, "timestamp_utc")

    combined = pd.concat([snapshot, history], ignore_index=True)
    combined = combined[(combined["sku"] != "") & (combined["asin"] != "")].copy()
    if combined.empty:
        return pd.DataFrame(columns=["sku", "operational_asin", "asin_bridge_status", "asin_ambiguity_flag", "asin_candidate_count"])

    combined["event_dt"] = _parse_utc_series(combined["event_utc"])
    combined = combined.sort_values(["sku", "event_dt"], ascending=[True, False], kind="stable")

    rows: list[dict[str, str]] = []
    for sku, sku_df in combined.groupby("sku", dropna=False):
        unique_asins = []
        seen = set()
        for asin in sku_df["asin"].tolist():
            asin_text = _normalize_text(asin).upper()
            if asin_text == "" or asin_text in seen:
                continue
            seen.add(asin_text)
            unique_asins.append(asin_text)
        latest_asin = unique_asins[0] if unique_asins else ""
        candidate_count = len(unique_asins)
        if candidate_count <= 0:
            status = "unresolved"
            ambiguity = "0"
        elif candidate_count == 1:
            status = "resolved"
            ambiguity = "0"
        else:
            status = "ambiguous"
            ambiguity = "1"
        rows.append(
            {
                "sku": _normalize_text(sku).upper(),
                "operational_asin": latest_asin,
                "asin_bridge_status": status,
                "asin_ambiguity_flag": ambiguity,
                "asin_candidate_count": str(candidate_count),
            }
        )
    return pd.DataFrame(rows)


def _build_daily_truth_rollup(daily_truth_df: pd.DataFrame) -> pd.DataFrame:
    if daily_truth_df.empty:
        return pd.DataFrame(columns=["sku", "latest_finalized_date", "latest_provisional_date", "daily_truth_row_count"])
    work = pd.DataFrame()
    work["sku"] = _column_as_text(daily_truth_df, "sku").str.upper()
    work["date"] = _column_as_text(daily_truth_df, "date")
    work["source_state"] = _column_as_text(daily_truth_df, "source_state")
    work = work[work["sku"] != ""].copy()
    if work.empty:
        return pd.DataFrame(columns=["sku", "latest_finalized_date", "latest_provisional_date", "daily_truth_row_count"])

    rows: list[dict[str, str]] = []
    for sku, sku_df in work.groupby("sku", dropna=False):
        finalized_dates = sku_df.loc[sku_df["source_state"] == "finalized_ledger", "date"].tolist()
        provisional_dates = sku_df.loc[sku_df["source_state"] == "provisional_order_master", "date"].tolist()
        finalized = max([d for d in finalized_dates if d], default="")
        provisional = max([d for d in provisional_dates if d], default="")
        rows.append(
            {
                "sku": _normalize_text(sku).upper(),
                "latest_finalized_date": finalized,
                "latest_provisional_date": provisional,
                "daily_truth_row_count": str(len(sku_df.index)),
            }
        )
    return pd.DataFrame(rows)


def _truth_state(latest_finalized_date: str, latest_provisional_date: str) -> str:
    if _normalize_text(latest_finalized_date) != "":
        return "finalized"
    if _normalize_text(latest_provisional_date) != "":
        return "provisional_only"
    return "no_truth_rows"


def build_sales_truth_foundation(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    observed_utc: str | None = None,
) -> FoundationBuildResult:
    snapshot_utc = observed_utc or _utc_now_iso()
    output_dir.mkdir(parents=True, exist_ok=True)

    order_master_df = _read_csv(ORDER_MASTER_PATH)
    order_ledger_df = _read_csv(ORDER_LEDGER_FX_PATH)
    daily_truth_df = _read_csv(DAILY_TRUTH_PATH)
    sales_truth_30d_df = _read_csv(SALES_TRUTH_30D_PATH)
    performance_df = _read_csv(PERFORMANCE_PATH)
    listing_snapshot_df = _read_csv(LISTING_SNAPSHOT_PATH)
    listing_history_df = _read_csv(LISTING_HISTORY_PATH)

    order_master_latest_utc = _max_ts_iso(order_master_df, "Date")
    order_ledger_latest_utc = _max_ts_from_candidates(order_ledger_df, ("Date", "date"))
    lag_minutes, freshness_status, freshness_reason = _lag_status(order_master_latest_utc, order_ledger_latest_utc)
    stale_flag = "1" if freshness_status in {"warn", "fail"} else "0"
    sales_truth_30d_asof = _max_date_text(sales_truth_30d_df, "asof_date")
    performance_asof = _max_date_text(performance_df, "asof_date")

    sku_set: set[str] = set()
    sku_set |= {v for v in _column_as_text(order_master_df, "SKU").str.upper().tolist() if v}
    sku_set |= {v for v in _column_as_text(daily_truth_df, "sku").str.upper().tolist() if v}
    sku_set |= {v for v in _column_as_text(performance_df, "sku").str.upper().tolist() if v}
    sku_set |= {v for v in _column_as_text(listing_snapshot_df, "sku").str.upper().tolist() if v}
    sku_set |= {v for v in _column_as_text(listing_history_df, "sku").str.upper().tolist() if v}

    listing_bridge_df = _build_listing_bridge(listing_snapshot_df, listing_history_df)
    truth_rollup_df = _build_daily_truth_rollup(daily_truth_df)

    bridge_map = {row["sku"]: row for _, row in listing_bridge_df.iterrows()} if not listing_bridge_df.empty else {}
    truth_map = {row["sku"]: row for _, row in truth_rollup_df.iterrows()} if not truth_rollup_df.empty else {}
    order_master_skus = set(_column_as_text(order_master_df, "SKU").str.upper().tolist())
    daily_truth_skus = set(_column_as_text(daily_truth_df, "sku").str.upper().tolist())
    performance_skus = set(_column_as_text(performance_df, "sku").str.upper().tolist())
    listing_scope_skus = set(_column_as_text(listing_snapshot_df, "sku").str.upper().tolist()) | set(
        _column_as_text(listing_history_df, "sku").str.upper().tolist()
    )

    rows: list[dict[str, str]] = []
    for sku in sorted([v for v in sku_set if v]):
        bridge = bridge_map.get(sku, {})
        truth = truth_map.get(sku, {})
        latest_finalized_date = _normalize_text(truth.get("latest_finalized_date", ""))
        latest_provisional_date = _normalize_text(truth.get("latest_provisional_date", ""))
        row = {
            "observed_utc": snapshot_utc,
            "operational_sku": sku,
            "operational_asin": _normalize_text(bridge.get("operational_asin", "")),
            "asin_bridge_status": _normalize_text(bridge.get("asin_bridge_status", "unresolved")) or "unresolved",
            "asin_ambiguity_flag": _normalize_text(bridge.get("asin_ambiguity_flag", "0")) or "0",
            "asin_candidate_count": _normalize_text(bridge.get("asin_candidate_count", "0")) or "0",
            "latest_finalized_date": latest_finalized_date,
            "latest_provisional_date": latest_provisional_date,
            "truth_state": _truth_state(latest_finalized_date, latest_provisional_date),
            "daily_truth_row_count": _normalize_text(truth.get("daily_truth_row_count", "0")) or "0",
            "in_order_master_flag": "1" if sku in order_master_skus else "0",
            "in_daily_truth_flag": "1" if sku in daily_truth_skus else "0",
            "in_performance_flag": "1" if sku in performance_skus else "0",
            "in_listing_scope_flag": "1" if sku in listing_scope_skus else "0",
            "order_master_latest_utc": order_master_latest_utc,
            "order_ledger_fx_latest_utc": order_ledger_latest_utc,
            "order_master_to_ledger_lag_minutes": lag_minutes,
            "ledger_freshness_status": freshness_status,
            "stale_flag": stale_flag,
            "sales_truth_30d_asof_date": sales_truth_30d_asof,
            "performance_asof_date": performance_asof,
        }
        rows.append({column: _normalize_text(row.get(column, "")) for column in FOUNDATION_COLUMNS})

    foundation_df = pd.DataFrame(rows, columns=FOUNDATION_COLUMNS)
    bridge_status_counts = (
        foundation_df["asin_bridge_status"].value_counts().to_dict() if not foundation_df.empty else {}
    )
    resolved_count = int(bridge_status_counts.get("resolved", 0))
    ambiguous_count = int(bridge_status_counts.get("ambiguous", 0))
    unresolved_count = int(bridge_status_counts.get("unresolved", 0))
    stale_rows = int((foundation_df.get("stale_flag", "0") == "1").sum()) if not foundation_df.empty else 0

    freshness_warn_count = 1 if freshness_status == "warn" else 0
    freshness_fail_count = 1 if freshness_status == "fail" else 0
    lag_value = _to_float(lag_minutes)
    lag_notes = (
        f"order_master_latest_utc={order_master_latest_utc};"
        f"order_ledger_fx_latest_utc={order_ledger_latest_utc};"
        f"lag_minutes={lag_minutes};reason={freshness_reason}"
    )

    health_rows = [
        {"observed_utc": snapshot_utc, "metric": "foundation_rows_total", "value": str(len(foundation_df.index)), "status": "ok", "notes": ""},
        {"observed_utc": snapshot_utc, "metric": "bridge_resolved_count", "value": str(resolved_count), "status": "ok", "notes": ""},
        {"observed_utc": snapshot_utc, "metric": "bridge_ambiguous_count", "value": str(ambiguous_count), "status": "warn" if ambiguous_count > 0 else "ok", "notes": ""},
        {"observed_utc": snapshot_utc, "metric": "bridge_unresolved_count", "value": str(unresolved_count), "status": "warn" if unresolved_count > 0 else "ok", "notes": ""},
        {"observed_utc": snapshot_utc, "metric": "freshness_lag_minutes", "value": f"{lag_value:.2f}" if lag_minutes != "" else "", "status": freshness_status or "fail", "notes": lag_notes},
        {"observed_utc": snapshot_utc, "metric": "freshness_warn_count", "value": str(freshness_warn_count), "status": "ok", "notes": ""},
        {"observed_utc": snapshot_utc, "metric": "freshness_fail_count", "value": str(freshness_fail_count), "status": "ok", "notes": ""},
        {"observed_utc": snapshot_utc, "metric": "stale_row_count", "value": str(stale_rows), "status": "warn" if stale_rows > 0 else "ok", "notes": ""},
        {
            "observed_utc": snapshot_utc,
            "metric": "truth_state_finalized_rows",
            "value": str(int((foundation_df.get("truth_state", "") == "finalized").sum()) if not foundation_df.empty else 0),
            "status": "ok",
            "notes": "",
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "truth_state_provisional_only_rows",
            "value": str(int((foundation_df.get("truth_state", "") == "provisional_only").sum()) if not foundation_df.empty else 0),
            "status": "ok",
            "notes": "",
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "truth_state_no_truth_rows",
            "value": str(int((foundation_df.get("truth_state", "") == "no_truth_rows").sum()) if not foundation_df.empty else 0),
            "status": "warn" if not foundation_df.empty and int((foundation_df.get("truth_state", "") == "no_truth_rows").sum()) > 0 else "ok",
            "notes": "",
        },
    ]
    health_df = pd.DataFrame(health_rows, columns=HEALTH_COLUMNS)

    foundation_path = output_dir / "bef_sales_truth_foundation_latest.csv"
    health_path = output_dir / "bef_sales_feedback_health_latest.csv"
    foundation_df.to_csv(foundation_path, index=False)
    health_df.to_csv(health_path, index=False)

    print(
        json.dumps(
            {
                "status": "success",
                "observed_utc": snapshot_utc,
                "foundation_rows": int(len(foundation_df.index)),
                "bridge_resolved_count": resolved_count,
                "bridge_ambiguous_count": ambiguous_count,
                "bridge_unresolved_count": unresolved_count,
                "freshness_status": freshness_status,
                "freshness_lag_minutes": lag_minutes,
                "foundation_output": str(foundation_path),
                "health_output": str(health_path),
            }
        )
    )

    return FoundationBuildResult(
        foundation_df=foundation_df,
        health_df=health_df,
        foundation_path=foundation_path,
        health_path=health_path,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the B/E/F sales-truth foundation and health outputs.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--observed-utc", default=None, help="Override observed UTC timestamp in ISO format.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_sales_truth_foundation(
        output_dir=Path(args.output_dir),
        observed_utc=args.observed_utc,
    )


if __name__ == "__main__":
    main()
