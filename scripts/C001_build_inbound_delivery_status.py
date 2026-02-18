from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

INBOUND_CONTENTS = Path("out/inbound_shipment_contents.csv")
LEDGER = Path("out/inventory_ledger_raw.csv")
OUT_STATUS = Path("out/inbound_delivery_status.csv")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def main() -> None:
    contents = _read_csv(INBOUND_CONTENTS)
    ledger = _read_csv(LEDGER)

    if contents.empty and ledger.empty:
        OUT_STATUS.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(OUT_STATUS, index=False)
        print({"status": "success", "rows": 0, "snapshot": str(OUT_STATUS)})
        return

    # Expected quantities by shipment and SKU
    if not contents.empty:
        contents["quantity"] = _to_num(contents.get("quantity", 0))
        expected = contents.groupby(["inbound_shipment_id", "sku"], dropna=False)["quantity"].sum().reset_index()
    else:
        expected = pd.DataFrame(columns=["inbound_shipment_id", "sku", "quantity"])

    # Received quantities by shipment and SKU from ledger (Receipt events)
    recv = pd.DataFrame(columns=["inbound_shipment_id", "sku", "received_qty"])
    if not ledger.empty:
        ref_col = "Reference ID" if "Reference ID" in ledger.columns else "ReferenceId"
        sku_col = "MSKU" if "MSKU" in ledger.columns else "sku"
        event_col = "Event Type" if "Event Type" in ledger.columns else "event_type"
        qty_col = "Quantity" if "Quantity" in ledger.columns else "quantity"

        led = ledger.copy()
        led["__event"] = led.get(event_col, "").astype(str)
        led = led[led["__event"].str.contains("receipt", case=False, na=False)]
        if not led.empty:
            led["__qty"] = _to_num(led.get(qty_col, 0))
            recv = (
                led.groupby([ref_col, sku_col], dropna=False)["__qty"].sum().reset_index()
                .rename(columns={ref_col: "inbound_shipment_id", sku_col: "sku", "__qty": "received_qty"})
            )

    # Merge expected and received
    if expected.empty and not recv.empty:
        merged = recv.copy()
        merged["expected_qty"] = 0
    elif recv.empty and not expected.empty:
        merged = expected.rename(columns={"quantity": "expected_qty"}).copy()
        merged["received_qty"] = 0
    else:
        merged = expected.rename(columns={"quantity": "expected_qty"}).merge(
            recv, on=["inbound_shipment_id", "sku"], how="outer"
        )
        merged["expected_qty"] = _to_num(merged.get("expected_qty", 0))
        merged["received_qty"] = _to_num(merged.get("received_qty", 0))

    merged["missing_qty"] = (merged["expected_qty"] - merged["received_qty"]).clip(lower=0)

    # Shipment-level rollup
    ship = merged.groupby("inbound_shipment_id", dropna=False).agg(
        expected_qty=("expected_qty", "sum"),
        received_qty=("received_qty", "sum"),
        missing_qty=("missing_qty", "sum"),
    ).reset_index()
    ship["pct_received"] = ship.apply(
        lambda r: (r["received_qty"] / r["expected_qty"] * 100.0) if r["expected_qty"] else None, axis=1
    )
    ship["status"] = ship["pct_received"].apply(lambda v: "unknown" if v is None else ("complete" if v >= 100 else "receiving"))
    ship["updated_at_utc"] = datetime.now(timezone.utc).isoformat()

    OUT_STATUS.parent.mkdir(parents=True, exist_ok=True)
    ship.to_csv(OUT_STATUS, index=False)
    print({"status": "success", "rows": len(ship), "snapshot": str(OUT_STATUS)})


if __name__ == "__main__":
    main()
