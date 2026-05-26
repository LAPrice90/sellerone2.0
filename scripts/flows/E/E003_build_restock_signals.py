from __future__ import annotations

import os
from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.core.storage import (
        StorageConfig,
        connect_store,
        parse_storage_mode,
        read_dataframe_with_sql_fallback,
        replace_table_from_dataframe,
    )
except ModuleNotFoundError:
    from core.storage import (
        StorageConfig,
        connect_store,
        parse_storage_mode,
        read_dataframe_with_sql_fallback,
        replace_table_from_dataframe,
    )

OUT = Path("out")
VELOCITY = OUT / "sku_sales_velocity.csv"
INVENTORY = OUT / "inventory_summaries.csv"
OUT_RESTOCK = OUT / "sku_restock_signals.csv"
SQL_TABLE = "e_sku_restock_signals"
SQL_TABLE_INVENTORY_SUMMARIES = "a_inventory_summaries"

RESTOCK_COLUMNS = [
    "sku",
    "velocity_30d",
    "available",
    "total_quantity",
    "days_of_stock_left",
    "reorder_flag",
    "suggested_reorder_qty",
    "asof_date",
]


def _read_csv(path: Path) -> pd.DataFrame:
    if path == INVENTORY:
        try:
            return read_dataframe_with_sql_fallback(path, SQL_TABLE_INVENTORY_SUMMARIES, dtype=str).fillna("")
        except FileNotFoundError:
            return pd.DataFrame()
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _write_restock_output(df: pd.DataFrame) -> dict[str, object]:
    mode = parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE", "csv"))
    sql_rows = 0

    def write_csv() -> None:
        OUT_RESTOCK.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(OUT_RESTOCK, index=False)

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


def main() -> None:
    vel = _read_csv(VELOCITY)
    inv = _read_csv(INVENTORY)

    if vel.empty:
        output = _write_restock_output(pd.DataFrame(columns=RESTOCK_COLUMNS))
        print({"status": "success", "rows": 0, "snapshot": str(OUT_RESTOCK), **output})
        return

    vel = vel[vel.get("window_days", "").astype(str) == "30"]
    if vel.empty:
        output = _write_restock_output(pd.DataFrame(columns=RESTOCK_COLUMNS))
        print({"status": "success", "rows": 0, "snapshot": str(OUT_RESTOCK), **output})
        return

    vel["velocity_units_per_day"] = _to_num(vel.get("velocity_units_per_day", 0))
    vel["available"] = _to_num(vel.get("available", 0))
    vel["total_quantity"] = _to_num(vel.get("total_quantity", 0))

    threshold = float(os.environ.get("RESTOCK_DAYS_THRESHOLD", "14") or "14")
    target_days = float(os.environ.get("RESTOCK_TARGET_DAYS", "30") or "30")

    rows = []
    for _, r in vel.iterrows():
        sku = str(r.get("sku", "")).strip()
        if not sku:
            continue
        velocity = float(r.get("velocity_units_per_day", 0))
        available = float(r.get("available", 0))
        total_qty = float(r.get("total_quantity", 0))
        if velocity > 0:
            days_left = available / velocity
            reorder_flag = "yes" if days_left <= threshold else "no"
            suggested = max(0.0, (velocity * target_days) - available)
        else:
            days_left = None
            reorder_flag = "no"
            suggested = 0.0

        rows.append({
            "sku": sku,
            "velocity_30d": round(velocity, 6),
            "available": int(available),
            "total_quantity": int(total_qty),
            "days_of_stock_left": None if days_left is None else round(days_left, 2),
            "reorder_flag": reorder_flag,
            "suggested_reorder_qty": int(round(suggested)),
            "asof_date": r.get("asof_date", ""),
        })

    out = pd.DataFrame(rows, columns=RESTOCK_COLUMNS)
    output = _write_restock_output(out)
    print({"status": "success", "rows": len(out), "snapshot": str(OUT_RESTOCK), **output})


if __name__ == "__main__":
    main()

