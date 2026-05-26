from __future__ import annotations

import sys
import os
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.E.e_sales_truth_common import WINDOW_DAYS, build_truth_rows
try:
    from scripts.core.storage import StorageConfig, connect_store, parse_storage_mode, replace_tables_from_dataframes
except ModuleNotFoundError:
    from core.storage import StorageConfig, connect_store, parse_storage_mode, replace_tables_from_dataframes

OUT = Path("out")
ORDER_MASTER = OUT / "order_master.csv"
ORDER_LEDGER_FX = OUT / "order_ledger_fx.csv"
FINANCIAL_EVENTS_LEVEL2 = OUT / "financial_events_level2.csv"
TOKEN_COGS = OUT / "token_cogs_ledger.csv"
FX_RATES = OUT / "fx_rates_daily.csv"
MARKETPLACE_PARTICIPATIONS = OUT / "marketplace_participations.csv"
ROI = OUT / "sku_roi_snapshot.csv"
OUT_B_TRUTH = OUT / "sales_truth_sku_30d_latest.csv"
OUT_RECON = OUT / "sales_truth_reconciliation_latest.csv"
SQL_TABLE_B_TRUTH = "e_sales_truth_sku_30d"
SQL_TABLE_RECON = "e_sales_truth_reconciliation"

DELTA_TOLERANCE_GBP = 0.5
B_TRUTH_COLUMNS = [
    "sku",
    "window_days",
    "asof_date",
    "units_b_source",
    "revenue_b_source_gbp",
    "profit_b_source_gbp",
]
RECON_COLUMNS = [
    "sku",
    "window_days",
    "asof_date",
    "units_b_source",
    "revenue_b_source_gbp",
    "profit_b_source_gbp",
    "units_e_output",
    "revenue_e_output_gbp",
    "profit_e_output_gbp",
    "units_delta",
    "revenue_delta_gbp",
    "profit_delta_gbp",
    "confidence_status",
    "root_cause_hint",
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _norm_sku(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip()


def _series_or_default(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col in df.columns:
        return df[col]
    return pd.Series([default] * len(df), index=df.index)


def _write_outputs(b_truth: pd.DataFrame, recon: pd.DataFrame) -> dict[str, object]:
    mode = parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE", "csv"))
    sql_rows = 0

    def write_csv() -> None:
        OUT_B_TRUTH.parent.mkdir(parents=True, exist_ok=True)
        b_truth.to_csv(OUT_B_TRUTH, index=False)
        recon.to_csv(OUT_RECON, index=False)

    def write_sql() -> None:
        nonlocal sql_rows
        store = connect_store(StorageConfig.from_env())
        try:
            results = replace_tables_from_dataframes(
                store,
                {
                    SQL_TABLE_B_TRUTH: b_truth,
                    SQL_TABLE_RECON: recon,
                },
            )
        finally:
            store.close()
        sql_rows = sum(int(result["rows"]) for result in results)

    if mode == "sql_primary_csv_export":
        write_sql()
        write_csv()
    elif mode == "sql_shadow":
        write_csv()
        write_sql()
    else:
        write_csv()

    return {
        "mode": mode,
        "sql_tables": f"{SQL_TABLE_B_TRUTH},{SQL_TABLE_RECON}" if mode != "csv" else "",
        "sql_rows": sql_rows,
    }


def _build_b_truth() -> tuple[pd.DataFrame, str]:
    truth_rows, asof_date = build_truth_rows(
        order_ledger_fx_path=ORDER_LEDGER_FX,
        financial_events_level2_path=FINANCIAL_EVENTS_LEVEL2,
        token_cogs_path=TOKEN_COGS,
        order_master_path=ORDER_MASTER,
        fx_rates_path=FX_RATES,
        marketplace_participations_path=MARKETPLACE_PARTICIPATIONS,
        window_days=WINDOW_DAYS,
    )
    if truth_rows.empty:
        return pd.DataFrame(columns=B_TRUTH_COLUMNS), asof_date

    grouped = (
        truth_rows.groupby("sku", dropna=False)[["units", "revenue_gbp", "profit_gbp"]]
        .sum()
        .reset_index()
        .rename(
            columns={
                "units": "units_b_source",
                "revenue_gbp": "revenue_b_source_gbp",
                "profit_gbp": "profit_b_source_gbp",
            }
        )
    )
    grouped["window_days"] = WINDOW_DAYS
    grouped["asof_date"] = asof_date
    return grouped[B_TRUTH_COLUMNS], asof_date


def _build_e_view() -> pd.DataFrame:
    roi = _read_csv(ROI)
    if roi.empty:
        return pd.DataFrame(columns=["sku", "units_e_output", "revenue_e_output_gbp", "profit_e_output_gbp"])
    roi["sku"] = _norm_sku(roi.get("sku", pd.Series([""] * len(roi), index=roi.index)))
    roi = roi[roi["sku"] != ""].copy()
    if roi.empty:
        return pd.DataFrame(columns=["sku", "units_e_output", "revenue_e_output_gbp", "profit_e_output_gbp"])
    roi["units_e_output"] = _to_num(_series_or_default(roi, "units_sold"))
    roi["revenue_e_output_gbp"] = _to_num(_series_or_default(roi, "revenue_exvat_gbp"))
    roi["profit_e_output_gbp"] = _to_num(_series_or_default(roi, "profit_exvat_gbp"))
    return roi[["sku", "units_e_output", "revenue_e_output_gbp", "profit_e_output_gbp"]].copy()


def _classify_rows(df: pd.DataFrame) -> pd.DataFrame:
    df["units_delta"] = df["units_e_output"] - df["units_b_source"]
    df["revenue_delta_gbp"] = df["revenue_e_output_gbp"] - df["revenue_b_source_gbp"]
    df["profit_delta_gbp"] = df["profit_e_output_gbp"] - df["profit_b_source_gbp"]

    def _classify(row: pd.Series) -> tuple[str, str]:
        b_units = float(row["units_b_source"])
        e_units = float(row["units_e_output"])
        revenue_delta = float(abs(row["revenue_delta_gbp"]))
        profit_delta = float(abs(row["profit_delta_gbp"]))
        units_delta = float(abs(row["units_delta"]))
        if b_units > 0 and e_units <= 0:
            return "mismatch", "e_missing_sku"
        if b_units <= 0 and e_units > 0:
            return "mismatch", "b_missing_sku"
        if units_delta > 0:
            return "mismatch", "unit_delta"
        if revenue_delta > DELTA_TOLERANCE_GBP:
            return "mismatch", "revenue_delta"
        if profit_delta > DELTA_TOLERANCE_GBP:
            return "mismatch", "profit_delta"
        return "match", ""

    classes = df.apply(_classify, axis=1)
    df["confidence_status"] = classes.map(lambda x: x[0])
    df["root_cause_hint"] = classes.map(lambda x: x[1])
    return df


def main() -> None:
    b_truth, asof_date = _build_b_truth()
    e_view = _build_e_view()

    if b_truth.empty and e_view.empty:
        output = _write_outputs(pd.DataFrame(columns=B_TRUTH_COLUMNS), pd.DataFrame(columns=RECON_COLUMNS))
        print({"status": "success", "rows": 0, "b_truth": str(OUT_B_TRUTH), "reconciliation": str(OUT_RECON), **output})
        return

    if b_truth.empty:
        b_truth = pd.DataFrame(columns=B_TRUTH_COLUMNS)
    if e_view.empty:
        e_view = pd.DataFrame(columns=["sku", "units_e_output", "revenue_e_output_gbp", "profit_e_output_gbp"])
    if "asof_date" not in b_truth.columns:
        b_truth["asof_date"] = asof_date
    if "window_days" not in b_truth.columns:
        b_truth["window_days"] = WINDOW_DAYS
    b_truth = b_truth[B_TRUTH_COLUMNS].copy()

    recon = b_truth.merge(e_view, on="sku", how="outer")
    for col in [
        "units_b_source",
        "revenue_b_source_gbp",
        "profit_b_source_gbp",
        "units_e_output",
        "revenue_e_output_gbp",
        "profit_e_output_gbp",
    ]:
        recon[col] = _to_num(recon.get(col, 0))
    recon["window_days"] = _to_num(recon.get("window_days", WINDOW_DAYS)).replace(0, WINDOW_DAYS).astype(int)
    recon["asof_date"] = recon.get("asof_date", "").astype(str)
    recon = _classify_rows(recon)
    recon = recon[
        RECON_COLUMNS
    ].copy()

    output = _write_outputs(b_truth, recon)

    mismatch_count = int((recon["confidence_status"] != "match").sum())
    print(
        {
            "status": "success",
            "rows": int(len(recon)),
            "mismatch_rows": mismatch_count,
            "b_truth": str(OUT_B_TRUTH),
            "reconciliation": str(OUT_RECON),
            **output,
        }
    )


if __name__ == "__main__":
    main()
