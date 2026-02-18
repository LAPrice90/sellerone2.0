"""
Run inbound shipment contents report (wrapper around B030).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd


def _build_from_inventory_ledger() -> int:
    ledger_path = Path("out/inventory_ledger_raw.csv")
    if not ledger_path.exists():
        print({"status": "error", "error": "missing_inventory_ledger", "path": str(ledger_path)})
        return 1
    df = pd.read_csv(ledger_path, dtype=str).fillna("")
    required = {"Event Type", "Reference ID", "MSKU", "Quantity"}
    missing = required - set(df.columns)
    if missing:
        print({"status": "error", "error": "missing_columns", "missing": sorted(missing)})
        return 1
    receipts = df[
        (df["Event Type"].str.strip().str.lower() == "receipts")
        & (df["Reference ID"].str.strip().str.startswith("FBA"))
    ].copy()
    if receipts.empty:
        out_map = Path("out/inbound_shipment_contents.csv")
        out_raw = Path("out/inbound_shipment_contents_raw.csv")
        out_map.write_text("inbound_shipment_id,sku,quantity\n")
        out_raw.write_text("inbound_shipment_id,sku,quantity\n")
        print({"status": "warning", "source": "inventory_ledger", "rows": 0})
        return 0
    receipts["qty_num"] = pd.to_numeric(receipts["Quantity"], errors="coerce").fillna(0)
    grouped = (
        receipts.groupby(["Reference ID", "MSKU"], as_index=False)["qty_num"]
        .sum()
        .rename(columns={"Reference ID": "inbound_shipment_id", "MSKU": "sku", "qty_num": "quantity"})
    )
    out_map = Path("out/inbound_shipment_contents.csv")
    out_raw = Path("out/inbound_shipment_contents_raw.csv")
    grouped.to_csv(out_map, index=False)
    grouped.to_csv(out_raw, index=False)
    print({"status": "success", "source": "inventory_ledger", "rows": int(grouped.shape[0]), "snapshot": str(out_map)})
    return 0


def main() -> int:
    script = Path(__file__).resolve().parent / "B030_run_inbound_shipment_contents_report.py"
    if not script.exists():
        print({"status": "error", "error": "missing_script", "path": str(script)})
        return 1
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    if result.returncode == 0:
        return 0
    err_tail = (result.stderr or result.stdout or "").strip().splitlines()[-1:]
    print({"status": "warning", "action": "fallback_to_inventory_ledger", "last_error": err_tail})
    return _build_from_inventory_ledger()


if __name__ == "__main__":
    raise SystemExit(main())
