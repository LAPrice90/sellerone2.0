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

FOUNDATION_PATH = DEFAULT_OUTPUT_DIR / "bef_sales_truth_foundation_latest.csv"
DAILY_TRUTH_PATH = OUT / "sku_daily_sales_truth_latest.csv"
SUMMARY_PATH = OUT / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv"
SEED_PATH = DEFAULT_OUTPUT_DIR / "bef_operational_feedback_seed_latest.csv"
ALIGNMENT_PATH = DEFAULT_OUTPUT_DIR / "hf_learning_alignment_30d_latest.csv"
IDENTITY_BRIDGE_PATH = DEFAULT_OUTPUT_DIR / "hf_learning_identity_bridge_latest.csv"
DEFAULT_ACTUALS_PATH = DEFAULT_OUTPUT_DIR / "f_sales_history_learning_actuals_latest.csv"

WINDOWS = (30, 60, 90)

ACTUALS_COLUMNS = [
    "decision_snapshot_utc",
    "seller_sku",
    "asin",
    "actual_units_30d",
    "actual_profit_30d_gbp",
    "actual_units_60d",
    "actual_profit_60d_gbp",
    "actual_units_90d",
    "actual_profit_90d_gbp",
    "learning_outcome",
    "learning_reason_codes",
    "operator_check_utc",
    "operator_notes",
    "purchased_flag",
    "actuals_source_state_30d",
    "actuals_source_state_60d",
    "actuals_source_state_90d",
    "actuals_observed_utc",
    "bridge_status",
    "actuals_basis",
]


@dataclass(frozen=True)
class SalesFeedbackActualsResult:
    actuals_df: pd.DataFrame
    actuals_path: Path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _num_to_text(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


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


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def _latest_summary_rows(summary_df: pd.DataFrame) -> pd.DataFrame:
    if summary_df.empty:
        return pd.DataFrame(columns=["decision_snapshot_utc", "seller_sku", "asin", "row_source"])
    work = pd.DataFrame()
    work["decision_snapshot_utc"] = _column_as_text(summary_df, "observed_utc")
    work["seller_sku"] = _column_as_text(summary_df, "seller_sku")
    work["asin"] = _column_as_text(summary_df, "asin").str.upper()
    work["decision_state"] = _column_as_text(summary_df, "decision_state").str.lower()
    work = work[(work["asin"] != "") & (work["seller_sku"] != "") & (work["decision_snapshot_utc"] != "")].copy()
    if work.empty:
        return pd.DataFrame(columns=["decision_snapshot_utc", "seller_sku", "asin", "row_source"])

    work["_ts"] = pd.to_datetime(work["decision_snapshot_utc"], errors="coerce", utc=True)
    work = work.sort_values(["asin", "seller_sku", "_ts"], ascending=[True, True, False], kind="stable")
    work = work.drop_duplicates(subset=["asin", "seller_sku"], keep="first")
    work["row_source"] = "summary_live"
    return work[["decision_snapshot_utc", "seller_sku", "asin", "row_source"]].reset_index(drop=True)


def _seed_replay_rows(seed_df: pd.DataFrame) -> pd.DataFrame:
    if seed_df.empty:
        return pd.DataFrame(columns=["decision_snapshot_utc", "seller_sku", "asin", "row_source"])
    work = pd.DataFrame()
    work["decision_snapshot_utc"] = _column_as_text(seed_df, "observed_utc")
    work["seller_sku"] = _column_as_text(seed_df, "operational_sku").str.upper()
    work["asin"] = _column_as_text(seed_df, "operational_asin").str.upper()
    work["bridge_status"] = _column_as_text(seed_df, "bridge_status").str.lower()
    work["seed_priority"] = _column_as_text(seed_df, "seed_priority").str.lower()
    work = work[(work["seller_sku"] != "") & (work["asin"] != "")].copy()
    work = work[work["bridge_status"] == "resolved"].copy()
    work = work[work["seed_priority"].isin({"high", "medium"})].copy()
    if work.empty:
        return pd.DataFrame(columns=["decision_snapshot_utc", "seller_sku", "asin", "row_source"])
    work["_ts"] = pd.to_datetime(work["decision_snapshot_utc"], errors="coerce", utc=True)
    work = work.sort_values(["asin", "seller_sku", "_ts"], ascending=[True, True, False], kind="stable")
    work = work.drop_duplicates(subset=["asin", "seller_sku"], keep="first")
    work["row_source"] = "operational_seed_replay"
    return work[["decision_snapshot_utc", "seller_sku", "asin", "row_source"]].reset_index(drop=True)


def _alignment_native_rows(alignment_df: pd.DataFrame) -> pd.DataFrame:
    if alignment_df.empty:
        return pd.DataFrame(columns=["decision_snapshot_utc", "seller_sku", "asin", "row_source"])
    work = pd.DataFrame()
    work["decision_snapshot_utc"] = _column_as_text(alignment_df, "alignment_window_end_utc")
    work["seller_sku"] = _column_as_text(alignment_df, "sku").str.upper()
    work["asin"] = _column_as_text(alignment_df, "asin").str.upper()
    work["expected_units_30d"] = _column_as_text(alignment_df, "expected_units_30d")
    work["seller_sku"] = work.apply(
        lambda row: _normalize_text(row["seller_sku"]) if _normalize_text(row["seller_sku"]) != "" else f"OPER::{_normalize_text(row['asin'])}",
        axis=1,
    )
    work = work[
        (work["asin"] != "")
        & (work["seller_sku"] != "")
        & (work["expected_units_30d"] != "")
    ].copy()
    if work.empty:
        return pd.DataFrame(columns=["decision_snapshot_utc", "seller_sku", "asin", "row_source"])
    work["_ts"] = pd.to_datetime(work["decision_snapshot_utc"], errors="coerce", utc=True)
    work = work.sort_values(["asin", "seller_sku", "_ts"], ascending=[True, True, False], kind="stable")
    work = work.drop_duplicates(subset=["asin", "seller_sku"], keep="first")
    work["row_source"] = "alignment_native_map"
    return work[["decision_snapshot_utc", "seller_sku", "asin", "row_source"]].reset_index(drop=True)


def _summary_direct_bridge_rows(
    summary_df: pd.DataFrame,
    identity_bridge_df: pd.DataFrame,
    sku_asin_df: pd.DataFrame,
) -> pd.DataFrame:
    if summary_df.empty or identity_bridge_df.empty or sku_asin_df.empty:
        return pd.DataFrame(columns=["decision_snapshot_utc", "seller_sku", "asin", "row_source"])

    summary_rows = _latest_summary_rows(summary_df).copy()
    if summary_rows.empty:
        return pd.DataFrame(columns=["decision_snapshot_utc", "seller_sku", "asin", "row_source"])

    bridge = pd.DataFrame()
    bridge["supplier_sku"] = _column_as_text(identity_bridge_df, "supplier_sku").str.upper()
    bridge["asin"] = _column_as_text(identity_bridge_df, "asin").str.upper()
    bridge["operational_sku"] = _column_as_text(identity_bridge_df, "sku").str.upper()
    bridge["snapshot_utc"] = _column_as_text(identity_bridge_df, "snapshot_utc")
    bridge = bridge[(bridge["supplier_sku"] != "") & (bridge["asin"] != "")].copy()
    if bridge.empty:
        return pd.DataFrame(columns=["decision_snapshot_utc", "seller_sku", "asin", "row_source"])

    bridge["_ts"] = pd.to_datetime(bridge["snapshot_utc"], errors="coerce", utc=True)
    bridge = bridge.sort_values(["supplier_sku", "asin", "_ts"], ascending=[True, True, False], kind="stable")
    bridge = bridge.drop_duplicates(subset=["supplier_sku", "asin"], keep="first").reset_index(drop=True)

    summary_rows["seller_sku_norm"] = summary_rows["seller_sku"].map(_normalize_text).str.upper()
    summary_rows["asin_norm"] = summary_rows["asin"].map(_normalize_text).str.upper()
    direct = summary_rows.merge(
        bridge,
        left_on=["seller_sku_norm", "asin_norm"],
        right_on=["supplier_sku", "asin"],
        how="inner",
    )
    if direct.empty:
        return pd.DataFrame(columns=["decision_snapshot_utc", "seller_sku", "asin", "row_source"])

    sku_to_asin = sku_asin_df.set_index("operational_sku")["asin"].to_dict()
    known_operational_asins = set(sku_asin_df["asin"].map(_normalize_text).str.upper().tolist())
    direct["mapped_asin"] = direct["operational_sku"].map(lambda v: _normalize_text(sku_to_asin.get(_normalize_text(v).upper(), ""))).str.upper()
    direct["mapped_asin"] = direct.apply(
        lambda row: row["mapped_asin"] if row["mapped_asin"] != "" else (row["asin_norm"] if row["asin_norm"] in known_operational_asins else ""),
        axis=1,
    )
    direct = direct[direct["mapped_asin"] != ""].copy()
    if direct.empty:
        return pd.DataFrame(columns=["decision_snapshot_utc", "seller_sku", "asin", "row_source"])

    out = pd.DataFrame()
    out["decision_snapshot_utc"] = direct["decision_snapshot_utc"].map(_normalize_text)
    out["seller_sku"] = direct["seller_sku"].map(_normalize_text)
    out["asin"] = direct["mapped_asin"].map(_normalize_text).str.upper()
    out["_ts"] = pd.to_datetime(out["decision_snapshot_utc"], errors="coerce", utc=True)
    out = out.sort_values(["asin", "seller_sku", "_ts"], ascending=[True, True, False], kind="stable")
    out = out.drop_duplicates(subset=["asin", "seller_sku"], keep="first")
    out["row_source"] = "summary_direct_bridge"
    return out[["decision_snapshot_utc", "seller_sku", "asin", "row_source"]].reset_index(drop=True)


def _combined_summary_rows(
    summary_df: pd.DataFrame,
    seed_df: pd.DataFrame,
    alignment_df: pd.DataFrame,
    identity_bridge_df: pd.DataFrame,
    sku_asin_df: pd.DataFrame,
    *,
    fallback_snapshot_utc: str,
) -> pd.DataFrame:
    direct_rows = _summary_direct_bridge_rows(summary_df, identity_bridge_df, sku_asin_df)
    summary_rows = _latest_summary_rows(summary_df)
    alignment_rows = _alignment_native_rows(alignment_df)
    seed_rows = _seed_replay_rows(seed_df)
    if direct_rows.empty and summary_rows.empty and seed_rows.empty and alignment_rows.empty:
        return pd.DataFrame(columns=["decision_snapshot_utc", "seller_sku", "asin", "row_source"])
    combined = pd.concat([direct_rows, summary_rows, alignment_rows, seed_rows], ignore_index=True)
    combined["decision_snapshot_utc"] = combined["decision_snapshot_utc"].map(_normalize_text)
    combined["decision_snapshot_utc"] = combined["decision_snapshot_utc"].map(
        lambda v: v if v != "" else fallback_snapshot_utc
    )
    # Preserve direct bridge rows over live summary and fallback overlap rows when keys collide.
    def _priority(source: object) -> int:
        token = _normalize_text(source).lower()
        if token == "summary_direct_bridge":
            return 0
        if token == "summary_live":
            return 1
        if token == "alignment_native_map":
            return 2
        return 3

    combined["_priority"] = combined["row_source"].map(_priority)
    combined = combined.sort_values(["asin", "seller_sku", "_priority"], ascending=[True, True, True], kind="stable")
    combined = combined.drop_duplicates(subset=["asin", "seller_sku"], keep="first")
    combined = combined.drop(columns=["_priority"])
    return combined.reset_index(drop=True)


def _resolved_sku_to_asin(foundation_df: pd.DataFrame) -> pd.DataFrame:
    if foundation_df.empty:
        return pd.DataFrame(columns=["operational_sku", "asin", "bridge_status"])
    work = pd.DataFrame()
    work["operational_sku"] = _column_as_text(foundation_df, "operational_sku").str.upper()
    work["asin"] = _column_as_text(foundation_df, "operational_asin").str.upper()
    work["bridge_status"] = _column_as_text(foundation_df, "asin_bridge_status").str.lower()
    work = work[(work["operational_sku"] != "") & (work["asin"] != "")].copy()
    work = work[work["bridge_status"] == "resolved"].copy()
    if work.empty:
        return pd.DataFrame(columns=["operational_sku", "asin", "bridge_status"])
    work = work.drop_duplicates(subset=["operational_sku"], keep="first")
    return work.reset_index(drop=True)


def _window_state(finalized_rows: int, provisional_rows: int) -> str:
    if finalized_rows > 0 and provisional_rows > 0:
        return "finalized_plus_provisional"
    if finalized_rows > 0:
        return "finalized_only"
    if provisional_rows > 0:
        return "provisional_only"
    return "no_data"


def _build_asin_metrics(daily_truth_df: pd.DataFrame, sku_asin_df: pd.DataFrame) -> tuple[dict[str, dict[str, str]], str]:
    if daily_truth_df.empty or sku_asin_df.empty:
        return {}, ""

    work = pd.DataFrame()
    work["operational_sku"] = _column_as_text(daily_truth_df, "sku").str.upper()
    work["date"] = _column_as_text(daily_truth_df, "date")
    work["source_state"] = _column_as_text(daily_truth_df, "source_state")
    work["units"] = _to_num(_column_as_text(daily_truth_df, "units"))
    work["profit"] = _to_num(_column_as_text(daily_truth_df, "profit_gbp"))
    work["date_dt"] = pd.to_datetime(work["date"], errors="coerce", utc=True)
    work = work[(work["operational_sku"] != "") & work["date_dt"].notna()].copy()
    if work.empty:
        return {}, ""

    sku_map = sku_asin_df.set_index("operational_sku")["asin"].to_dict()
    bridge_map = sku_asin_df.set_index("operational_sku")["bridge_status"].to_dict()
    work["asin"] = work["operational_sku"].map(lambda s: _normalize_text(sku_map.get(s, "")))
    work["bridge_status"] = work["operational_sku"].map(lambda s: _normalize_text(bridge_map.get(s, "")))
    work = work[work["asin"] != ""].copy()
    if work.empty:
        return {}, ""

    max_dt = work["date_dt"].max()
    metrics: dict[str, dict[str, str]] = {}
    for asin, asin_df in work.groupby("asin", dropna=False):
        asin_row: dict[str, str] = {"bridge_status": _normalize_text(asin_df["bridge_status"].iloc[0]) or "resolved"}
        latest_date = asin_df["date"].max()
        asin_row["latest_truth_date"] = _normalize_text(latest_date)
        for window in WINDOWS:
            cutoff = max_dt - pd.Timedelta(days=window - 1)
            wdf = asin_df[asin_df["date_dt"] >= cutoff].copy()
            units = float(wdf["units"].sum()) if not wdf.empty else 0.0
            profit = float(wdf["profit"].sum()) if not wdf.empty else 0.0
            finalized_rows = int((wdf["source_state"] == "finalized_ledger").sum()) if not wdf.empty else 0
            provisional_rows = int((wdf["source_state"] == "provisional_order_master").sum()) if not wdf.empty else 0
            asin_row[f"actual_units_{window}d"] = _num_to_text(units)
            asin_row[f"actual_profit_{window}d_gbp"] = _num_to_text(profit)
            asin_row[f"actuals_source_state_{window}d"] = _window_state(finalized_rows, provisional_rows)
        metrics[_normalize_text(asin).upper()] = asin_row
    return metrics, max_dt.strftime("%Y-%m-%d")


def _empty_actuals_df() -> pd.DataFrame:
    return pd.DataFrame(columns=ACTUALS_COLUMNS)


def build_sales_feedback_actuals(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    observed_utc: str | None = None,
) -> SalesFeedbackActualsResult:
    snapshot_utc = observed_utc or _utc_now_iso()
    output_dir.mkdir(parents=True, exist_ok=True)

    foundation_df = _read_csv(FOUNDATION_PATH)
    daily_truth_df = _read_csv(DAILY_TRUTH_PATH)
    summary_df = _read_csv(SUMMARY_PATH)
    seed_df = _read_csv(SEED_PATH)
    alignment_df = _read_csv(ALIGNMENT_PATH)
    identity_bridge_df = _read_csv(IDENTITY_BRIDGE_PATH)

    sku_asin_df = _resolved_sku_to_asin(foundation_df)
    asin_metrics, metrics_asof_date = _build_asin_metrics(daily_truth_df, sku_asin_df)
    summary_rows = _combined_summary_rows(
        summary_df,
        seed_df,
        alignment_df,
        identity_bridge_df,
        sku_asin_df,
        fallback_snapshot_utc=snapshot_utc,
    )

    out_rows: list[dict[str, str]] = []

    # Rows keyed to current F summary snapshots so F012 can consume automatically.
    matched_direct_bridge_rows = 0
    matched_summary_rows = 0
    matched_seed_replay_rows = 0
    matched_alignment_rows = 0
    for _, row in summary_rows.iterrows():
        asin = _normalize_text(row.get("asin", "")).upper()
        metrics = asin_metrics.get(asin)
        if not metrics:
            continue
        row_source = _normalize_text(row.get("row_source", "summary_live")).lower()
        if row_source == "summary_direct_bridge":
            matched_direct_bridge_rows += 1
            purchased_flag = "auto_summary_direct_bridge"
            actuals_basis = "summary_direct_bridge"
        elif row_source == "operational_seed_replay":
            matched_seed_replay_rows += 1
            purchased_flag = "auto_operational_seed_replay"
            actuals_basis = "operational_seed_replay"
        elif row_source == "alignment_native_map":
            matched_alignment_rows += 1
            purchased_flag = "auto_alignment_asin_match"
            actuals_basis = "alignment_asin_map"
        else:
            matched_summary_rows += 1
            purchased_flag = "auto_summary_asin_match"
            actuals_basis = "summary_asin_map"
        out_rows.append(
            {
                "decision_snapshot_utc": _normalize_text(row.get("decision_snapshot_utc", "")),
                "seller_sku": _normalize_text(row.get("seller_sku", "")),
                "asin": asin,
                "actual_units_30d": _normalize_text(metrics.get("actual_units_30d", "")),
                "actual_profit_30d_gbp": _normalize_text(metrics.get("actual_profit_30d_gbp", "")),
                "actual_units_60d": _normalize_text(metrics.get("actual_units_60d", "")),
                "actual_profit_60d_gbp": _normalize_text(metrics.get("actual_profit_60d_gbp", "")),
                "actual_units_90d": _normalize_text(metrics.get("actual_units_90d", "")),
                "actual_profit_90d_gbp": _normalize_text(metrics.get("actual_profit_90d_gbp", "")),
                "learning_outcome": "",
                "learning_reason_codes": "",
                "operator_check_utc": "",
                "operator_notes": "",
                "purchased_flag": purchased_flag,
                "actuals_source_state_30d": _normalize_text(metrics.get("actuals_source_state_30d", "")),
                "actuals_source_state_60d": _normalize_text(metrics.get("actuals_source_state_60d", "")),
                "actuals_source_state_90d": _normalize_text(metrics.get("actuals_source_state_90d", "")),
                "actuals_observed_utc": snapshot_utc,
                "bridge_status": _normalize_text(metrics.get("bridge_status", "")),
                "actuals_basis": actuals_basis,
            }
        )

    # Baseline operational rows so coverage remains explicit even when F overlap is thin.
    for asin, metrics in sorted(asin_metrics.items()):
        out_rows.append(
            {
                "decision_snapshot_utc": "",
                "seller_sku": f"OPER::{asin}",
                "asin": asin,
                "actual_units_30d": _normalize_text(metrics.get("actual_units_30d", "")),
                "actual_profit_30d_gbp": _normalize_text(metrics.get("actual_profit_30d_gbp", "")),
                "actual_units_60d": _normalize_text(metrics.get("actual_units_60d", "")),
                "actual_profit_60d_gbp": _normalize_text(metrics.get("actual_profit_60d_gbp", "")),
                "actual_units_90d": _normalize_text(metrics.get("actual_units_90d", "")),
                "actual_profit_90d_gbp": _normalize_text(metrics.get("actual_profit_90d_gbp", "")),
                "learning_outcome": "",
                "learning_reason_codes": "",
                "operator_check_utc": "",
                "operator_notes": "",
                "purchased_flag": "auto_operational_baseline",
                "actuals_source_state_30d": _normalize_text(metrics.get("actuals_source_state_30d", "")),
                "actuals_source_state_60d": _normalize_text(metrics.get("actuals_source_state_60d", "")),
                "actuals_source_state_90d": _normalize_text(metrics.get("actuals_source_state_90d", "")),
                "actuals_observed_utc": snapshot_utc,
                "bridge_status": _normalize_text(metrics.get("bridge_status", "")),
                "actuals_basis": "operational_baseline",
            }
        )

    if out_rows:
        actuals_df = pd.DataFrame(out_rows, columns=ACTUALS_COLUMNS)
        actuals_df = actuals_df.sort_values(
            by=["actuals_basis", "asin", "seller_sku", "decision_snapshot_utc"],
            key=lambda s: s.map(lambda v: _normalize_text(v).upper()),
            kind="stable",
        ).reset_index(drop=True)
    else:
        actuals_df = _empty_actuals_df()

    actuals_path = output_dir / "f_sales_history_learning_actuals_latest.csv"
    actuals_df.to_csv(actuals_path, index=False)

    print(
        json.dumps(
            {
                "status": "success",
                "observed_utc": snapshot_utc,
                "rows_total": int(len(actuals_df.index)),
                "summary_rows_total": int(len(summary_rows.index)),
                "summary_direct_bridge_rows_matched": int(matched_direct_bridge_rows),
                "summary_rows_matched": int(matched_summary_rows),
                "seed_replay_rows_matched": int(matched_seed_replay_rows),
                "alignment_rows_matched": int(matched_alignment_rows),
                "operational_baseline_rows": int((actuals_df.get("actuals_basis", "") == "operational_baseline").sum()) if not actuals_df.empty else 0,
                "metrics_asof_date": metrics_asof_date,
                "actuals_output": str(actuals_path),
            }
        )
    )

    return SalesFeedbackActualsResult(actuals_df=actuals_df, actuals_path=actuals_path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build automatic sales-feedback actuals for F learning outputs.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--observed-utc", default=None, help="Override observed UTC timestamp in ISO format.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_sales_feedback_actuals(
        output_dir=Path(args.output_dir),
        observed_utc=args.observed_utc,
    )


if __name__ == "__main__":
    main()
