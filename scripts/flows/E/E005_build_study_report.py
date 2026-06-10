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
OUT_COVERAGE = OUT / "e_coverage_summary.csv"
SQL_TABLE = "e_study_report"
MISSING_ROI_REASON_LABELS = [
    "roi_clean",
    "velocity_only_sales_truth",
    "stock_only_no_sales_window",
    "no_recent_sales_truth",
    "missing_cogs_or_fx",
    "missing_fee_proof",
    "missing_refund_proof",
    "missing_current_price_proof",
    "b_money_bridge_labelled",
    "not_available",
]
RESTOCK_DECISION_STATE_LABELS = [
    "business_ready_clean",
    "stock_signal_only",
    "blocked_missing_roi",
    "blocked_missing_profit_inputs",
    "warning_bridge_labelled_money",
    "blocked_weak_refund_proof",
    "blocked_missing_current_price",
    "not_applicable_no_stock_signal",
]


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


def _write_coverage_output(df: pd.DataFrame) -> None:
    OUT_COVERAGE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_COVERAGE, index=False)


def _series_or_blank(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return df[col].fillna("").astype(str).replace({"nan": "", "NaN": "", "None": ""})
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


def _sku_set(df: pd.DataFrame, col: str = "sku") -> set[str]:
    if df.empty or col not in df.columns:
        return set()
    return {str(value or "").strip().upper() for value in df[col].tolist() if str(value or "").strip()}


def _is_blankish(value: object) -> bool:
    text = str(value or "").strip().lower()
    return text in {"", "nan", "none", "null"}


def _build_coverage_summary(summary: pd.DataFrame, report: pd.DataFrame, daily_truth: pd.DataFrame) -> pd.DataFrame:
    total_skus = _sku_set(summary)
    source_state = _series_or_blank(summary, "units_sold_source").str.lower()
    profit_confidence = _series_or_blank(summary, "profit_confidence").str.lower()
    reorder_flag = _series_or_blank(summary, "reorder_flag").str.lower()
    business_ready = _series_or_blank(summary, "restock_business_ready").str.lower()
    stock_signal = _series_or_blank(summary, "stock_signal").str.lower()
    restock_decision_state = _series_or_blank(summary, "restock_decision_state").str.lower()
    restock_readiness_confidence = _series_or_blank(summary, "restock_readiness_confidence").str.lower()
    restock_missing_proof = _series_or_blank(summary, "restock_missing_proof").str.lower()
    velocity_skus = _sku_set(summary[source_state.eq("velocity")]) if not summary.empty else set()
    roi_skus = _sku_set(summary[source_state.eq("roi")]) if not summary.empty else set()
    restock_flag_skus = _sku_set(summary[reorder_flag.eq("yes")]) if not summary.empty else set()
    stock_signal_skus = _sku_set(summary[stock_signal.eq("yes")]) if not summary.empty else set()
    business_ready_skus = _sku_set(summary[business_ready.eq("yes")]) if not summary.empty else set()
    missing_profit_skus = _sku_set(summary[profit_confidence.ne("profit_clean")]) if not summary.empty else set()
    missing_roi_reason = _series_or_blank(summary, "missing_roi_reason").str.lower()
    restock_flagged_missing_roi_skus = _sku_set(
        summary[reorder_flag.eq("yes") & profit_confidence.ne("profit_clean")]
    ) if not summary.empty else set()
    reason_counts = {
        f"missing_roi_reason_{label}_skus": len(_sku_set(summary[missing_roi_reason.eq(label)]))
        for label in MISSING_ROI_REASON_LABELS
    }
    restock_state_counts = {
        f"restock_decision_state_{label}_skus": len(_sku_set(summary[restock_decision_state.eq(label)]))
        for label in RESTOCK_DECISION_STATE_LABELS
    }
    restock_block_counts = {
        "restock_blocked_missing_roi_skus": len(_sku_set(summary[restock_missing_proof.str.contains("missing_roi", regex=False)])) if not summary.empty else 0,
        "restock_blocked_weak_refund_proof_skus": len(_sku_set(summary[restock_missing_proof.str.contains("weak_refund_proof", regex=False)])) if not summary.empty else 0,
        "restock_blocked_missing_current_price_skus": len(_sku_set(summary[restock_missing_proof.str.contains("missing_current_price", regex=False)])) if not summary.empty else 0,
        "restock_warning_bridge_labelled_money_skus": len(_sku_set(summary[restock_readiness_confidence.eq("warning")])) if not summary.empty else 0,
    }

    finalized_skus: set[str] = set()
    provisional_skus: set[str] = set()
    if not daily_truth.empty and {"sku", "source_state"}.issubset(set(daily_truth.columns)):
        state = daily_truth["source_state"].astype(str).str.lower()
        finalized_skus = _sku_set(daily_truth[state.eq("finalized_ledger")])
        provisional_skus = _sku_set(daily_truth[state.eq("provisional_order_master")])

    blank_truth_rows = 0
    if not report.empty and "latest_daily_truth_state" in report.columns:
        blank_truth_rows = int(report["latest_daily_truth_state"].map(_is_blankish).sum())

    asof_date = ""
    if not summary.empty and "asof_date" in summary.columns:
        asof_values = [str(value or "").strip() for value in summary["asof_date"].tolist() if str(value or "").strip()]
        asof_date = max(asof_values) if asof_values else ""

    row = {
        "asof_date": asof_date,
        "total_skus": len(total_skus),
        "skus_with_velocity": len(velocity_skus | roi_skus),
        "skus_with_roi": len(roi_skus),
        "skus_with_finalized_daily_truth": len(finalized_skus),
        "skus_with_provisional_daily_truth": len(provisional_skus),
        "skus_with_restock_flags": len(restock_flag_skus),
        "skus_with_stock_signal": len(stock_signal_skus),
        "skus_missing_profit_proof": len(missing_profit_skus),
        "velocity_only_skus": len(velocity_skus),
        "restock_business_ready_skus": len(business_ready_skus),
        "restock_flagged_missing_roi_skus": len(restock_flagged_missing_roi_skus),
        "blank_latest_daily_truth_state_rows": blank_truth_rows,
    }
    row.update(reason_counts)
    row.update(restock_state_counts)
    row.update(restock_block_counts)
    return pd.DataFrame([row])


def main() -> None:
    summary = _read_csv(SUMMARY)
    daily_truth = _read_csv(DAILY_TRUTH)

    if summary.empty:
        _write_coverage_output(
            pd.DataFrame(
                [
                    {
                        "asof_date": "",
                        "total_skus": 0,
                        "skus_with_velocity": 0,
                        "skus_with_roi": 0,
                        "skus_with_finalized_daily_truth": 0,
                        "skus_with_provisional_daily_truth": 0,
                        "skus_with_restock_flags": 0,
                        "skus_with_stock_signal": 0,
                        "skus_missing_profit_proof": 0,
                        "velocity_only_skus": 0,
                        "restock_business_ready_skus": 0,
                        "restock_flagged_missing_roi_skus": 0,
                        "blank_latest_daily_truth_state_rows": 0,
                        **{f"missing_roi_reason_{label}_skus": 0 for label in MISSING_ROI_REASON_LABELS},
                        **{f"restock_decision_state_{label}_skus": 0 for label in RESTOCK_DECISION_STATE_LABELS},
                        "restock_blocked_missing_roi_skus": 0,
                        "restock_blocked_weak_refund_proof_skus": 0,
                        "restock_blocked_missing_current_price_skus": 0,
                        "restock_warning_bridge_labelled_money_skus": 0,
                    }
                ]
            )
        )
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
        "latest_price_confidence": _series_or_blank(summary, "latest_price_confidence"),
        "b_money_confidence_state": _series_or_blank(summary, "b_money_confidence_state"),
        "b_bridge_values_safe_for_live_roi": _series_or_blank(summary, "b_bridge_values_safe_for_live_roi"),
        "profit_confidence": _series_or_blank(summary, "profit_confidence"),
        "sales_truth_state": _series_or_blank(summary, "sales_truth_state"),
        "stock_signal": _series_or_blank(summary, "stock_signal"),
        "restock_business_ready": _series_or_blank(summary, "restock_business_ready"),
        "restock_decision_state": _series_or_blank(summary, "restock_decision_state"),
        "restock_readiness_confidence": _series_or_blank(summary, "restock_readiness_confidence"),
        "restock_missing_proof": _series_or_blank(summary, "restock_missing_proof"),
        "restock_evidence_role": _series_or_blank(summary, "restock_evidence_role"),
        "missing_reason": _series_or_blank(summary, "missing_reason"),
        "missing_roi_reason": _series_or_blank(summary, "missing_roi_reason"),
        "missing_roi_reason_detail": _series_or_blank(summary, "missing_roi_reason_detail"),
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
    _write_coverage_output(_build_coverage_summary(summary, report, daily_truth))

    output = _write_study_output(report)
    print({"status": "success", "rows": len(report), "snapshot": str(OUT_STUDY), **output})


if __name__ == "__main__":
    main()

