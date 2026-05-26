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
F_SUMMARY_PATH = OUT / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv"

SEED_COLUMNS = [
    "observed_utc",
    "operational_asin",
    "operational_sku",
    "bridge_status",
    "ambiguity_flag",
    "recent_sales_presence_flag",
    "units_last_30d",
    "latest_truth_date",
    "truth_state",
    "in_f_universe_flag",
    "seed_priority",
    "seed_reason_codes",
]


@dataclass(frozen=True)
class FeedbackSeedBuildResult:
    seed_df: pd.DataFrame
    seed_path: Path


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


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def _num_to_text(value: object) -> str:
    num = _to_num(pd.Series([value])).iloc[0]
    if float(num).is_integer():
        return str(int(num))
    return f"{float(num):.6f}".rstrip("0").rstrip(".")


def _daily_recent_rollup(daily_truth_df: pd.DataFrame) -> pd.DataFrame:
    if daily_truth_df.empty:
        return pd.DataFrame(columns=["operational_sku", "units_last_30d", "latest_truth_date"])

    work = pd.DataFrame()
    work["operational_sku"] = _column_as_text(daily_truth_df, "sku").str.upper()
    work["date"] = _column_as_text(daily_truth_df, "date")
    work["units"] = _to_num(_column_as_text(daily_truth_df, "units"))
    work["date_dt"] = pd.to_datetime(work["date"], errors="coerce", utc=True)
    work = work[(work["operational_sku"] != "") & work["date_dt"].notna()].copy()
    if work.empty:
        return pd.DataFrame(columns=["operational_sku", "units_last_30d", "latest_truth_date"])

    max_dt = work["date_dt"].max()
    cutoff = max_dt - pd.Timedelta(days=29)
    recent = work[work["date_dt"] >= cutoff].copy()
    grouped = recent.groupby("operational_sku", dropna=False)["units"].sum().reset_index()
    grouped["units_last_30d"] = grouped["units"].round(6)
    grouped = grouped.drop(columns=["units"])

    latest_truth = work.groupby("operational_sku", dropna=False)["date"].max().reset_index()
    latest_truth = latest_truth.rename(columns={"date": "latest_truth_date"})
    out = grouped.merge(latest_truth, on="operational_sku", how="outer").fillna("")
    out["units_last_30d"] = _to_num(_column_as_text(out, "units_last_30d")).round(6)
    return out[["operational_sku", "units_last_30d", "latest_truth_date"]]


def _priority_and_reasons(
    *,
    bridge_status: str,
    recent_sales_presence_flag: str,
    in_f_universe_flag: str,
    operational_asin: str,
) -> tuple[str, str]:
    reasons: list[str] = []
    if bridge_status == "resolved":
        reasons.append("bridge_resolved")
    elif bridge_status == "ambiguous":
        reasons.append("bridge_ambiguous")
    else:
        reasons.append("bridge_unresolved")

    if recent_sales_presence_flag == "1":
        reasons.append("recent_sales_present")
    else:
        reasons.append("recent_sales_absent")

    if in_f_universe_flag == "1":
        reasons.append("in_f_universe")
    else:
        reasons.append("not_in_f_universe")

    if _normalize_text(operational_asin) == "":
        reasons.append("no_asin")

    if bridge_status == "resolved" and recent_sales_presence_flag == "1":
        return "high", "|".join(reasons)
    if bridge_status in {"resolved", "ambiguous"} and (recent_sales_presence_flag == "1" or in_f_universe_flag == "1"):
        return "medium", "|".join(reasons)
    return "low", "|".join(reasons)


def build_operational_feedback_seed(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    observed_utc: str | None = None,
) -> FeedbackSeedBuildResult:
    snapshot_utc = observed_utc or _utc_now_iso()
    output_dir.mkdir(parents=True, exist_ok=True)

    foundation_df = _read_csv(FOUNDATION_PATH)
    daily_truth_df = _read_csv(DAILY_TRUTH_PATH)
    f_summary_df = _read_csv(F_SUMMARY_PATH)

    if foundation_df.empty:
        seed_df = pd.DataFrame(columns=SEED_COLUMNS)
        seed_path = output_dir / "bef_operational_feedback_seed_latest.csv"
        seed_df.to_csv(seed_path, index=False)
        print(
            json.dumps(
                {
                    "status": "success",
                    "observed_utc": snapshot_utc,
                    "rows": 0,
                    "seed_output": str(seed_path),
                }
            )
        )
        return FeedbackSeedBuildResult(seed_df=seed_df, seed_path=seed_path)

    base = pd.DataFrame()
    base["operational_asin"] = _column_as_text(foundation_df, "operational_asin").str.upper()
    base["operational_sku"] = _column_as_text(foundation_df, "operational_sku").str.upper()
    base["bridge_status"] = _column_as_text(foundation_df, "asin_bridge_status").str.lower()
    base["ambiguity_flag"] = _column_as_text(foundation_df, "asin_ambiguity_flag")
    base["truth_state"] = _column_as_text(foundation_df, "truth_state")
    base = base[base["operational_sku"] != ""].copy()

    recent_rollup = _daily_recent_rollup(daily_truth_df)
    base = base.merge(recent_rollup, on="operational_sku", how="left").fillna("")
    base["units_last_30d"] = _to_num(_column_as_text(base, "units_last_30d")).round(6)
    base["recent_sales_presence_flag"] = base["units_last_30d"].map(lambda v: "1" if float(v) > 0 else "0")

    f_asins = set([v for v in _column_as_text(f_summary_df, "asin").str.upper().tolist() if v])
    base["in_f_universe_flag"] = base["operational_asin"].map(lambda v: "1" if v in f_asins else "0")

    priorities = base.apply(
        lambda row: _priority_and_reasons(
            bridge_status=_normalize_text(row.get("bridge_status", "")),
            recent_sales_presence_flag=_normalize_text(row.get("recent_sales_presence_flag", "")),
            in_f_universe_flag=_normalize_text(row.get("in_f_universe_flag", "")),
            operational_asin=_normalize_text(row.get("operational_asin", "")),
        ),
        axis=1,
    )
    base["seed_priority"] = priorities.map(lambda x: x[0])
    base["seed_reason_codes"] = priorities.map(lambda x: x[1])
    base["observed_utc"] = snapshot_utc

    priority_rank = {"high": 0, "medium": 1, "low": 2}
    base["_priority_sort"] = base["seed_priority"].map(lambda v: priority_rank.get(_normalize_text(v), 9))
    base = base.sort_values(["_priority_sort", "units_last_30d", "operational_sku"], ascending=[True, False, True], kind="stable")
    base = base.drop(columns=["_priority_sort"])

    out = pd.DataFrame(columns=SEED_COLUMNS)
    for column in SEED_COLUMNS:
        if column not in base.columns:
            out[column] = ""
            continue
        if column == "units_last_30d":
            out[column] = base[column].map(_num_to_text)
        else:
            out[column] = base[column].map(_normalize_text)

    seed_path = output_dir / "bef_operational_feedback_seed_latest.csv"
    out.to_csv(seed_path, index=False)

    print(
        json.dumps(
            {
                "status": "success",
                "observed_utc": snapshot_utc,
                "rows": int(len(out.index)),
                "high_priority_rows": int((out["seed_priority"] == "high").sum()),
                "medium_priority_rows": int((out["seed_priority"] == "medium").sum()),
                "low_priority_rows": int((out["seed_priority"] == "low").sum()),
                "seed_output": str(seed_path),
            }
        )
    )

    return FeedbackSeedBuildResult(seed_df=out, seed_path=seed_path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build operational replay seed rows for sales feedback learning.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--observed-utc", default=None, help="Override observed UTC timestamp in ISO format.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_operational_feedback_seed(
        output_dir=Path(args.output_dir),
        observed_utc=args.observed_utc,
    )


if __name__ == "__main__":
    main()
