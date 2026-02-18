from __future__ import annotations

from pathlib import Path
import pandas as pd

IN_SHIP = Path("out/financial_events_shipments.csv")
OUT_EVENTS = Path("out/inbound_cost_events.csv")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def main() -> None:
    df = _read_csv(IN_SHIP)
    if df.empty:
        OUT_EVENTS.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(OUT_EVENTS, index=False)
        print({"status": "success", "rows": 0, "snapshot": str(OUT_EVENTS)})
        return

    keep_cols = [
        "posted_date",
        "transaction_type",
        "amount_type",
        "is_fee",
        "amount",
        "currency",
        "tax_amount",
        "tax_currency",
        "order_id",
        "shipment_id",
        "inbound_shipment_id",
        "fee_reason",
        "fee_description",
        "parsed_fba_shipment_id",
    ]
    for col in keep_cols:
        if col not in df.columns:
            df[col] = ""

    out = df[keep_cols].copy()

    OUT_EVENTS.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_EVENTS, index=False)
    print({"status": "success", "rows": len(out), "snapshot": str(OUT_EVENTS)})


if __name__ == "__main__":
    main()
