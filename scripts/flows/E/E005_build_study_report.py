from __future__ import annotations

import os
from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.core.storage import StorageConfig, connect_store, parse_storage_mode, replace_table_from_dataframe
except ModuleNotFoundError:
    from core.storage import StorageConfig, connect_store, parse_storage_mode, replace_table_from_dataframe

OUT = Path("out")
SUMMARY = OUT / "sku_performance_summary.csv"
DAILY_TRUTH = OUT / "sku_daily_sales_truth_latest.csv"
OUT_STUDY = OUT / "e_study_report.csv"
SQL_TABLE = "e_study_report"


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _write_study_output(df: pd.DataFrame) -> dict[str, object]:
    mode = parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE", "csv"))
    sql_rows = 0

    def write_csv() -> None:
        OUT_STUDY.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(OUT_STUDY, index=False)

    def write_sql() -> None:
        nonlocal sql_rows
        store = connect_store(StorageConfig.from_env())
        try:
            result = replace_table_from_dataframe(store, SQL_TABLE, df)
        finally:
            store.close()
        sql_rows = int(result["rows"])

    if mode == "sql_primary_csv_export":
        write_sql()
        write_csv()
    elif mode == "sql_shadow":
        write_csv()
        write_sql()
    else:
        write_csv()

    return {"mode": mode, "sql_table": SQL_TABLE if sql_rows or mode != "csv" else "", "sql_rows": sql_rows}


def _series_or_blank(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return df[col].astype(str)
    return pd.Series([""] * len(df), index=df.index, dtype=str)


def _latest_daily_truth_by_sku(daily_truth: pd.DataFrame) -> pd.DataFrame:
    if daily_truth.empty:
        return pd.DataFrame(
            columns=[
                "sku",
                "latest_daily_truth_date",
                "latest_daily_truth_state",
                "latest_daily_truth_units",
                "latest_daily_truth_profit_gbp",
            ]
        )
    required = {"sku", "date", "source_state", "units", "profit_gbp"}
    if not required.issubset(set(daily_truth.columns)):
        return pd.DataFrame(
            columns=[
                "sku",
                "latest_daily_truth_date",
                "latest_daily_truth_state",
                "latest_daily_truth_units",
                "latest_daily_truth_profit_gbp",
            ]
        )

    latest = daily_truth.copy()
    latest["sku"] = latest["sku"].astype(str)
    latest["date_dt"] = pd.to_datetime(latest["date"], errors="coerce")
    latest["state_rank"] = latest["source_state"].astype(str).map(
        {
            "finalized_ledger": 0,
            "provisional_order_master": 1,
        }
    ).fillna(-1)
    latest = latest.sort_values(["date_dt", "state_rank"], ascending=[True, True], kind="stable")
    latest = latest.groupby("sku", as_index=False).tail(1).copy()
    latest = latest.rename(
        columns={
            "date": "latest_daily_truth_date",
            "source_state": "latest_daily_truth_state",
            "units": "latest_daily_truth_units",
            "profit_gbp": "latest_daily_truth_profit_gbp",
        }
    )
    return latest[
        [
            "sku",
            "latest_daily_truth_date",
            "latest_daily_truth_state",
            "latest_daily_truth_units",
            "latest_daily_truth_profit_gbp",
        ]
    ].copy()


def main() -> None:
    summary = _read_csv(SUMMARY)
    daily_truth = _read_csv(DAILY_TRUTH)

    if summary.empty:
        output = _write_study_output(pd.DataFrame(columns=["study_rank", "sku"]))
        print({"status": "success", "rows": 0, "snapshot": str(OUT_STUDY), **output})
        return

    latest_daily_truth = _latest_daily_truth_by_sku(daily_truth)
    if not latest_daily_truth.empty:
        summary = summary.merge(latest_daily_truth, on="sku", how="left")

    report = pd.DataFrame({
        "sku": _series_or_blank(summary, "sku"),
        "asof_date": _series_or_blank(summary, "asof_date"),
        "reorder_flag": _series_or_blank(summary, "reorder_flag"),
        "days_of_stock_left": _series_or_blank(summary, "days_of_stock_left"),
        "suggested_reorder_qty": _series_or_blank(summary, "suggested_reorder_qty"),
        "velocity_30d": _series_or_blank(summary, "velocity_30d"),
        "units_sold_30d": _series_or_blank(summary, "units_sold"),
        "units_sold_truth_30d": _series_or_blank(summary, "units_sold_truth_30d"),
        "units_sold_velocity_30d": _series_or_blank(summary, "units_sold_velocity_30d"),
        "units_sold_source": _series_or_blank(summary, "units_sold_source"),
        "revenue_exvat_gbp_30d": _series_or_blank(summary, "revenue_exvat_gbp"),
        "profit_exvat_gbp_30d": _series_or_blank(summary, "profit_exvat_gbp"),
        "roi_exvat_30d": _series_or_blank(summary, "roi_exvat"),
        "profit_per_unit_gbp_30d": _series_or_blank(summary, "profit_per_unit_gbp_30d"),
        "value_velocity_gbp_per_day": _series_or_blank(summary, "value_velocity_gbp_per_day"),
        "missing_cogs_units": _series_or_blank(summary, "missing_cogs_units"),
        "fx_missing_units": _series_or_blank(summary, "fx_missing_units"),
        "current_token_cost_gbp": _series_or_blank(summary, "current_token_cost_gbp"),
        "break_even_price_gbp": _series_or_blank(summary, "break_even_price_gbp"),
        "expected_refund_cost_per_unit_gbp": _series_or_blank(summary, "expected_refund_cost_per_unit_gbp"),
        "roi_at_our_price_pct": _series_or_blank(summary, "roi_at_our_price_pct"),
        "roi_at_buy_box_price_pct": _series_or_blank(summary, "roi_at_buy_box_price_pct"),
        "latest_daily_truth_date": _series_or_blank(summary, "latest_daily_truth_date"),
        "latest_daily_truth_state": _series_or_blank(summary, "latest_daily_truth_state"),
        "latest_daily_truth_units": _series_or_blank(summary, "latest_daily_truth_units"),
        "latest_daily_truth_profit_gbp": _series_or_blank(summary, "latest_daily_truth_profit_gbp"),
    })

    reorder_rank = report["reorder_flag"].astype(str).str.strip().str.lower().eq("yes").astype(int)
    value_rank = _to_num(report["value_velocity_gbp_per_day"]).fillna(-10**18)
    stock_rank = _to_num(report["days_of_stock_left"]).fillna(10**18)

    report = report.assign(
        _reorder_rank=reorder_rank,
        _value_rank=value_rank,
        _stock_rank=stock_rank,
    ).sort_values(
        by=["_reorder_rank", "_value_rank", "_stock_rank", "sku"],
        ascending=[False, False, True, True],
    )
    report.insert(0, "study_rank", range(1, len(report) + 1))
    report = report.drop(columns=["_reorder_rank", "_value_rank", "_stock_rank"])

    output = _write_study_output(report)
    print({"status": "success", "rows": len(report), "snapshot": str(OUT_STUDY), **output})


if __name__ == "__main__":
    main()

