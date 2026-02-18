from __future__ import annotations

from pathlib import Path
from datetime import datetime, timedelta, timezone
import pandas as pd

IN_STATUS = Path("out/inbound_delivery_status.csv")
IN_CONTENTS = Path("out/inbound_shipment_contents.csv")
OUT_SHIP = Path("out/token_maturity_window.csv")
OUT_SKU = Path("out/token_maturity_window_sku.csv")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def main() -> None:
    status = _read_csv(IN_STATUS)
    contents = _read_csv(IN_CONTENTS)

    if status.empty:
        OUT_SHIP.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(OUT_SHIP, index=False)
        pd.DataFrame().to_csv(OUT_SKU, index=False)
        print({"status": "success", "rows_ship": 0, "rows_sku": 0})
        return

    status = status.copy()
    status["expected_qty"] = _num(status.get("expected_qty", 0))
    status["received_qty"] = _num(status.get("received_qty", 0))
    status["missing_qty"] = _num(status.get("missing_qty", 0))

    now = datetime.now(timezone.utc)
    updated = pd.to_datetime(status.get("updated_at_utc", ""), errors="coerce", utc=True)
    status["updated_at_utc"] = updated
    status["mature_on_utc"] = status["updated_at_utc"] + pd.to_timedelta(14, unit="D")
    status["is_mature"] = status["mature_on_utc"] <= now
    status["in_flight_qty"] = (status["expected_qty"] - status["received_qty"]).clip(lower=0)

    ship_out = status[
        [
            "inbound_shipment_id",
            "expected_qty",
            "received_qty",
            "missing_qty",
            "in_flight_qty",
            "status",
            "updated_at_utc",
            "mature_on_utc",
            "is_mature",
        ]
    ].copy()

    # SKU-level view if contents exist
    sku_out = pd.DataFrame()
    if not contents.empty and "inbound_shipment_id" in contents.columns and "sku" in contents.columns:
        contents = contents.copy()
        contents["quantity"] = _num(contents.get("quantity", 0))
        sku_out = contents.groupby(["inbound_shipment_id", "sku"], as_index=False).agg(expected_qty=("quantity", "sum"))
        sku_out = sku_out.merge(
            ship_out[["inbound_shipment_id", "received_qty", "in_flight_qty", "status", "updated_at_utc", "mature_on_utc", "is_mature"]],
            on="inbound_shipment_id",
            how="left",
        )

    OUT_SHIP.parent.mkdir(parents=True, exist_ok=True)
    ship_out.to_csv(OUT_SHIP, index=False)
    if sku_out.empty:
        pd.DataFrame(
            columns=["inbound_shipment_id", "sku", "expected_qty", "received_qty", "in_flight_qty", "status", "updated_at_utc", "mature_on_utc", "is_mature"]
        ).to_csv(OUT_SKU, index=False)
    else:
        sku_out.to_csv(OUT_SKU, index=False)

    print({"status": "success", "rows_ship": len(ship_out), "rows_sku": len(sku_out), "snapshot": str(OUT_SHIP)})


if __name__ == "__main__":
    main()
