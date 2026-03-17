from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

OUT = Path("out")
ORDERS = OUT / "order_master.csv"
INVENTORY = OUT / "inventory_summaries.csv"
OUT_VELOCITY = OUT / "sku_sales_velocity.csv"

WINDOW_DAYS = [7, 30, 90]


def _read_csv(path: Path, usecols=None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, usecols=usecols).fillna("")


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def main() -> None:
    orders = _read_csv(ORDERS, usecols=["Date", "SKU", "Quantity Ordered"])
    if orders.empty:
        OUT_VELOCITY.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(OUT_VELOCITY, index=False)
        print({"status": "success", "rows": 0, "snapshot": str(OUT_VELOCITY)})
        return

    orders["Date"] = pd.to_datetime(orders["Date"], errors="coerce", utc=True)
    orders["qty"] = _to_num(orders.get("Quantity Ordered", 0))
    orders = orders.dropna(subset=["Date"])

    max_dt = orders["Date"].max()
    asof_date = max_dt.date().isoformat() if pd.notna(max_dt) else ""

    inventory = _read_csv(INVENTORY, usecols=["seller_sku", "available", "total_quantity"])
    if not inventory.empty:
        inventory["available"] = _to_num(inventory.get("available", 0))
        inventory["total_quantity"] = _to_num(inventory.get("total_quantity", 0))
        inv_map = inventory.set_index("seller_sku")[["available", "total_quantity"]].to_dict("index")
    else:
        inv_map = {}

    rows = []
    for sku, df_sku in orders.groupby("SKU", dropna=False):
        sku = str(sku).strip()
        if not sku:
            continue
        inv = inv_map.get(sku, {"available": 0, "total_quantity": 0})

        for window in WINDOW_DAYS:
            if pd.isna(max_dt):
                df_w = df_sku
            else:
                start = max_dt - pd.Timedelta(days=window)
                df_w = df_sku[df_sku["Date"] >= start]

            units_sold = float(df_w["qty"].sum()) if not df_w.empty else 0.0
            if df_w.empty:
                days_in_stock_est = 0
                first_dt = ""
                last_dt = ""
            else:
                first_dt = df_w["Date"].min().date().isoformat()
                last_dt = df_w["Date"].max().date().isoformat()
                days_in_stock_est = int((df_w["Date"].max().date() - df_w["Date"].min().date()).days + 1)
                if days_in_stock_est < 1:
                    days_in_stock_est = 1

            velocity = units_sold / days_in_stock_est if days_in_stock_est else 0.0

            rows.append({
                "sku": sku,
                "window_days": window,
                "units_sold": round(units_sold, 4),
                "days_in_stock_est": days_in_stock_est,
                "velocity_units_per_day": round(velocity, 6),
                "v7": round(velocity, 6) if window == 7 else "",
                "v30": round(velocity, 6) if window == 30 else "",
                "v90": round(velocity, 6) if window == 90 else "",
                "v_blended": "",
                "available": int(inv.get("available", 0)),
                "total_quantity": int(inv.get("total_quantity", 0)),
                "first_order_date": first_dt,
                "last_order_date": last_dt,
                "asof_date": asof_date,
            })

    OUT_VELOCITY.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT_VELOCITY, index=False)
    print({"status": "success", "rows": len(rows), "snapshot": str(OUT_VELOCITY)})


if __name__ == "__main__":
    main()

