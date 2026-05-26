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
    from scripts.core.storage import StorageConfig, connect_store, parse_storage_mode, replace_table_from_dataframe
except ModuleNotFoundError:
    from core.storage import StorageConfig, connect_store, parse_storage_mode, replace_table_from_dataframe

OUT = Path("out")
ORDER_MASTER = OUT / "order_master.csv"
ORDER_LEDGER_FX = OUT / "order_ledger_fx.csv"
FINANCIAL_EVENTS_LEVEL2 = OUT / "financial_events_level2.csv"
TOKEN_COGS = OUT / "token_cogs_ledger.csv"
FX_RATES = OUT / "fx_rates_daily.csv"
MARKETPLACE_PARTICIPATIONS = OUT / "marketplace_participations.csv"
OUT_DAILY = OUT / "sku_daily_sales_truth_latest.csv"
SQL_TABLE = "e_sku_daily_sales_truth"

COLUMNS = [
    "sku",
    "date",
    "source_state",
    "units",
    "revenue_gbp",
    "profit_gbp",
    "fees_gbp",
    "cogs_gbp",
    "confidence_status",
    "notes",
]


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def _write_daily_output(df: pd.DataFrame) -> dict[str, object]:
    mode = parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE", "csv"))
    sql_rows = 0

    def write_csv() -> None:
        OUT_DAILY.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(OUT_DAILY, index=False)

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

    return {"mode": mode, "sql_table": SQL_TABLE if mode != "csv" else "", "sql_rows": sql_rows}


CONFIDENCE_PRIORITY = {
    "finalized": 0,
    "provisional": 1,
    "provisional_cogs_placeholder": 2,
    "provisional_fx_missing": 3,
    "provisional_fx_and_cogs_placeholder": 4,
    "provisional_cogs_missing": 5,
    "provisional_fx_and_cogs_missing": 6,
}


def _pick_confidence(series: pd.Series) -> str:
    best = "finalized"
    best_rank = -1
    for value in series.astype(str):
        rank = CONFIDENCE_PRIORITY.get(value, -1)
        if rank > best_rank:
            best = value
            best_rank = rank
    return best


def _build_notes(group: pd.DataFrame) -> str:
    basis_tokens = sorted({str(value).strip() for value in group["basis"].astype(str) if str(value).strip()})
    fx_missing_units = int(round(float(group["fx_missing_units"].sum())))
    missing_cogs_units = int(round(float(group["missing_cogs_units"].sum())))
    placeholder_cogs_units = int(
        round(
            float(
                _to_num(
                    group["placeholder_cogs_units"]
                    if "placeholder_cogs_units" in group.columns
                    else pd.Series([0.0] * len(group), index=group.index)
                ).sum()
            )
        )
    )
    placeholder_sources = (
        sorted({str(value).strip() for value in group["placeholder_basis_source"].astype(str) if str(value).strip()})
        if "placeholder_basis_source" in group.columns
        else []
    )
    placeholder_dates = (
        sorted({str(value).strip() for value in group["placeholder_basis_date"].astype(str) if str(value).strip()})
        if "placeholder_basis_date" in group.columns
        else []
    )
    profit_excluded_rows = int(round(float(group["profit_excluded_rows"].sum())))

    parts: list[str] = []
    if basis_tokens:
        parts.append(f"basis={','.join(basis_tokens)}")
    if fx_missing_units > 0:
        parts.append(f"fx_missing_units={fx_missing_units}")
    if missing_cogs_units > 0:
        parts.append(f"cogs_missing_units={missing_cogs_units}")
    if placeholder_cogs_units > 0:
        parts.append(f"cogs_placeholder_units={placeholder_cogs_units}")
    if placeholder_sources:
        parts.append(f"placeholder_source={','.join(placeholder_sources)}")
    if placeholder_dates:
        parts.append(f"placeholder_date={','.join(placeholder_dates)}")
    if profit_excluded_rows > 0:
        parts.append(f"profit_excluded_rows={profit_excluded_rows}")
    return ";".join(parts)


def main() -> None:
    truth_rows, _ = build_truth_rows(
        order_ledger_fx_path=ORDER_LEDGER_FX,
        financial_events_level2_path=FINANCIAL_EVENTS_LEVEL2,
        token_cogs_path=TOKEN_COGS,
        order_master_path=ORDER_MASTER,
        fx_rates_path=FX_RATES,
        marketplace_participations_path=MARKETPLACE_PARTICIPATIONS,
        window_days=WINDOW_DAYS,
    )

    if truth_rows.empty:
        output = _write_daily_output(pd.DataFrame(columns=COLUMNS))
        print({"status": "success", "rows": 0, "snapshot": str(OUT_DAILY), **output})
        return

    grouped_rows: list[dict[str, object]] = []
    for (sku, day, source_state), group in truth_rows.groupby(["sku", "date", "source_state"], dropna=False):
        grouped_rows.append(
            {
                "sku": str(sku),
                "date": str(day),
                "source_state": str(source_state),
                "units": round(float(group["units"].sum()), 6),
                "revenue_gbp": round(float(group["revenue_gbp"].sum()), 6),
                "profit_gbp": round(float(group["profit_gbp"].sum()), 6),
                "fees_gbp": round(float(group["fees_gbp"].sum()), 6),
                "cogs_gbp": round(float(group["cogs_gbp"].sum()), 6),
                "confidence_status": _pick_confidence(group["confidence_status"]),
                "notes": "" if str(source_state) == "finalized_ledger" else _build_notes(group),
            }
        )

    out_df = pd.DataFrame(grouped_rows, columns=COLUMNS)
    out_df = out_df.sort_values(["date", "sku", "source_state"], kind="stable").reset_index(drop=True)

    output = _write_daily_output(out_df)
    print(
        {
            "status": "success",
            "rows": int(len(out_df)),
            "finalized_rows": int((out_df["source_state"] == "finalized_ledger").sum()),
            "provisional_rows": int((out_df["source_state"] == "provisional_order_master").sum()),
            "snapshot": str(OUT_DAILY),
            **output,
        }
    )


if __name__ == "__main__":
    main()
