from __future__ import annotations

from pathlib import Path
import pandas as pd

OUT = Path("out")
SUMMARY = OUT / "sku_performance_summary.csv"
OUT_STUDY = OUT / "e_study_report.csv"


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _series_or_blank(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return df[col].astype(str)
    return pd.Series([""] * len(df), index=df.index, dtype=str)


def main() -> None:
    summary = _read_csv(SUMMARY)

    if summary.empty:
        OUT_STUDY.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(OUT_STUDY, index=False)
        print({"status": "success", "rows": 0, "snapshot": str(OUT_STUDY)})
        return

    report = pd.DataFrame({
        "sku": _series_or_blank(summary, "sku"),
        "asof_date": _series_or_blank(summary, "asof_date"),
        "reorder_flag": _series_or_blank(summary, "reorder_flag"),
        "days_of_stock_left": _series_or_blank(summary, "days_of_stock_left"),
        "suggested_reorder_qty": _series_or_blank(summary, "suggested_reorder_qty"),
        "velocity_30d": _series_or_blank(summary, "velocity_30d"),
        "units_sold_30d": _series_or_blank(summary, "units_sold"),
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

    OUT_STUDY.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(OUT_STUDY, index=False)
    print({"status": "success", "rows": len(report), "snapshot": str(OUT_STUDY)})


if __name__ == "__main__":
    main()

