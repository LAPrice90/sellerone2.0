from __future__ import annotations

import os
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.E.e_sales_truth_common import WINDOW_DAYS, build_truth_rows
from scripts.core.storage import StorageConfig, connect_store, parse_storage_mode, replace_tables_from_dataframes

OUT = Path("out")
ORDERS = OUT / "order_master.csv"
ORDER_LEDGER_FX = OUT / "order_ledger_fx.csv"
FINANCIAL_EVENTS_LEVEL2 = OUT / "financial_events_level2.csv"
TOKEN_COGS = OUT / "token_cogs_ledger.csv"
OUT_ROI = OUT / "sku_roi_snapshot.csv"
OUT_ROI_UK = OUT / "sku_roi_snapshot_uk.csv"
OUT_ROI_NON_UK = OUT / "sku_roi_snapshot_non_uk.csv"
OUT_ROI_BY_COUNTRY = OUT / "sku_roi_snapshot_by_country.csv"
FX_RATES = OUT / "fx_rates_daily.csv"
MARKETPLACE_PARTICIPATIONS = OUT / "marketplace_participations.csv"
SQL_TABLE_ROI = "e_sku_roi_snapshot"
SQL_TABLE_ROI_UK = "e_sku_roi_snapshot_uk"
SQL_TABLE_ROI_NON_UK = "e_sku_roi_snapshot_non_uk"
SQL_TABLE_ROI_BY_COUNTRY = "e_sku_roi_snapshot_by_country"

ROI_COLUMNS = [
    "sku",
    "window_days",
    "units_sold",
    "revenue_exvat_gbp",
    "cogs_exvat_gbp",
    "profit_exvat_gbp",
    "roi_exvat",
    "missing_cogs_units",
    "fx_missing_units",
    "asof_date",
]

ROI_BY_COUNTRY_COLUMNS = [*ROI_COLUMNS[:2], "country_code", *ROI_COLUMNS[2:]]


def _write_empty_outputs() -> dict[str, object]:
    return _write_roi_outputs(
        pd.DataFrame(columns=ROI_COLUMNS),
        pd.DataFrame(columns=ROI_COLUMNS),
        pd.DataFrame(columns=ROI_COLUMNS),
        pd.DataFrame(columns=ROI_BY_COUNTRY_COLUMNS),
    )


def _write_roi_outputs(
    roi: pd.DataFrame,
    roi_uk: pd.DataFrame,
    roi_non_uk: pd.DataFrame,
    roi_by_country: pd.DataFrame,
) -> dict[str, object]:
    mode = parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE", "csv"))
    sql_rows = {
        SQL_TABLE_ROI: 0,
        SQL_TABLE_ROI_UK: 0,
        SQL_TABLE_ROI_NON_UK: 0,
        SQL_TABLE_ROI_BY_COUNTRY: 0,
    }

    def write_csv_outputs() -> None:
        OUT_ROI.parent.mkdir(parents=True, exist_ok=True)
        roi.to_csv(OUT_ROI, index=False)
        roi_uk.to_csv(OUT_ROI_UK, index=False)
        roi_non_uk.to_csv(OUT_ROI_NON_UK, index=False)
        roi_by_country.to_csv(OUT_ROI_BY_COUNTRY, index=False)

    def write_sql_outputs() -> None:
        config = StorageConfig.from_env()
        store = connect_store(config)
        try:
            results = replace_tables_from_dataframes(
                store,
                {
                    SQL_TABLE_ROI: roi,
                    SQL_TABLE_ROI_UK: roi_uk,
                    SQL_TABLE_ROI_NON_UK: roi_non_uk,
                    SQL_TABLE_ROI_BY_COUNTRY: roi_by_country,
                },
            )
        finally:
            store.close()
        for result in results:
            sql_rows[str(result["table"])] = int(result["rows"])

    if mode == "sql_primary_csv_export":
        write_sql_outputs()
        write_csv_outputs()
    elif mode == "sql_shadow":
        write_csv_outputs()
        write_sql_outputs()
    else:
        write_csv_outputs()

    return {
        "mode": mode,
        "sql_tables": list(sql_rows.keys()) if any(sql_rows.values()) or mode != "csv" else [],
        "sql_roi_rows": sql_rows[SQL_TABLE_ROI],
        "sql_roi_uk_rows": sql_rows[SQL_TABLE_ROI_UK],
        "sql_roi_non_uk_rows": sql_rows[SQL_TABLE_ROI_NON_UK],
        "sql_roi_by_country_rows": sql_rows[SQL_TABLE_ROI_BY_COUNTRY],
    }


def _summarize(df_in: pd.DataFrame, *, asof_date: str, by_country: bool) -> list[dict[str, object]]:
    rows = []
    if by_country:
        group_iter = df_in.groupby(["sku", "country_code"], dropna=False)
    else:
        group_iter = df_in.groupby("sku", dropna=False)
    for key, df_sku in group_iter:
        if by_country:
            sku = str(key[0]).strip()
            country = str(key[1]).strip()
        else:
            sku = str(key).strip()
            country = ""
        if not sku:
            continue
        units = float(df_sku["units"].sum())
        revenue = float(df_sku["revenue_gbp"].sum())
        profit = float(df_sku["profit_gbp"].sum())
        missing_cogs_units = int(round(float(df_sku["missing_cogs_units"].sum())))
        fx_missing_units = int(round(float(df_sku["fx_missing_units"].sum())))
        cogs_only = float(df_sku["cogs_gbp"].sum())
        cogs_base = abs(cogs_only)
        roi = (profit / cogs_base) if cogs_base > 0 else None
        row = {
            "sku": sku,
            "window_days": WINDOW_DAYS,
            "units_sold": round(units, 4),
            "revenue_exvat_gbp": round(revenue, 4),
            "cogs_exvat_gbp": round(cogs_only, 4),
            "profit_exvat_gbp": round(profit, 4),
            "roi_exvat": None if roi is None else round(roi, 6),
            "missing_cogs_units": missing_cogs_units,
            "fx_missing_units": fx_missing_units,
            "asof_date": asof_date,
        }
        if by_country:
            row["country_code"] = country
        rows.append(row)
    return rows


def main() -> None:
    truth_rows, asof_date = build_truth_rows(
        order_ledger_fx_path=ORDER_LEDGER_FX,
        financial_events_level2_path=FINANCIAL_EVENTS_LEVEL2,
        token_cogs_path=TOKEN_COGS,
        order_master_path=ORDERS,
        fx_rates_path=FX_RATES,
        marketplace_participations_path=MARKETPLACE_PARTICIPATIONS,
        window_days=WINDOW_DAYS,
    )
    if truth_rows.empty:
        output = _write_empty_outputs()
        print({"status": "success", "rows": 0, "snapshot": str(OUT_ROI), **output})
        return

    rows_all = _summarize(truth_rows, asof_date=asof_date, by_country=False)
    country_col = truth_rows["country_code"].astype(str).str.upper()
    rows_uk = _summarize(truth_rows[country_col == "GB"], asof_date=asof_date, by_country=False)
    rows_non_uk = _summarize(truth_rows[country_col != "GB"], asof_date=asof_date, by_country=False)
    rows_by_country = _summarize(truth_rows, asof_date=asof_date, by_country=True)

    OUT_ROI.parent.mkdir(parents=True, exist_ok=True)
    roi = pd.DataFrame(rows_all, columns=ROI_COLUMNS)
    roi_uk = pd.DataFrame(rows_uk, columns=ROI_COLUMNS)
    roi_non_uk = pd.DataFrame(rows_non_uk, columns=ROI_COLUMNS)
    roi_by_country = pd.DataFrame(rows_by_country, columns=ROI_BY_COUNTRY_COLUMNS)
    output = _write_roi_outputs(roi, roi_uk, roi_non_uk, roi_by_country)
    print({"status": "success", "rows": len(rows_all), "snapshot": str(OUT_ROI), "source": "combined_sales_truth", **output})


if __name__ == "__main__":
    main()
