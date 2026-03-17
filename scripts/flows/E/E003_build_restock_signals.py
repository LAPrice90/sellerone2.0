from __future__ import annotations

import os
from pathlib import Path
import pandas as pd

OUT = Path("out")
VELOCITY = OUT / "sku_sales_velocity.csv"
INVENTORY = OUT / "inventory_summaries.csv"
OUT_RESTOCK = OUT / "sku_restock_signals.csv"


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def main() -> None:
    vel = _read_csv(VELOCITY)
    inv = _read_csv(INVENTORY)

    if vel.empty:
        OUT_RESTOCK.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(OUT_RESTOCK, index=False)
        print({"status": "success", "rows": 0, "snapshot": str(OUT_RESTOCK)})
        return

    vel = vel[vel.get("window_days", "").astype(str) == "30"]
    if vel.empty:
        OUT_RESTOCK.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(OUT_RESTOCK, index=False)
        print({"status": "success", "rows": 0, "snapshot": str(OUT_RESTOCK)})
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

    OUT_RESTOCK.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT_RESTOCK, index=False)
    print({"status": "success", "rows": len(rows), "snapshot": str(OUT_RESTOCK)})


if __name__ == "__main__":
    main()

