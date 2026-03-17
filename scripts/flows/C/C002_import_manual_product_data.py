"""
Import manual product data into Product_DB without touching other manual fields.

Expected input: TSV/CSV with headers:
seller_sku,asin,supplier,barcode,supply_code,discontinued,drop

- Maps supplier -> supplier_name
- Maps supply_code -> supplier_code
- Sets sale_status: discontinued -> "discontinued"; drop -> "dropped"; else "active"
- Leaves other manual fields untouched; appends new rows if asin/sku not found.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Dict, List, Tuple

import gspread

SHEET_ID = "1b7iREy92vF_a1Lw72g0SOGS7t4-IOSBeeoHetLTN43s"
TAB_NAME = "Product_DB"
INPUT_PATH = Path(os.environ.get("PRODUCT_MANUAL_FILE", "reference/manual_product_data.tsv"))


def get_client() -> gspread.Client:
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        cred_path = str(Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=cred_path)


def load_input(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Manual data file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        sample = fh.read(1024)
        fh.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t")
        reader = csv.DictReader(fh, dialect=dialect)
        return [{k.strip(): (v or "").strip() for k, v in row.items()} for row in reader]


def main() -> None:
    data = load_input(INPUT_PATH)
    client = get_client()
    sheet = client.open_by_key(SHEET_ID)
    ws = sheet.worksheet(TAB_NAME)
    rows = ws.get_all_values()
    if not rows:
        raise RuntimeError("Product_DB tab is empty; run C001_seed_product_db.py first.")
    headers = rows[0]
    idx = {h: i for i, h in enumerate(headers)}
    body = rows[1:]

    # Build lookup by asin+sku
    lookup: Dict[Tuple[str, str], Tuple[int, List[str]]] = {}
    for i, row in enumerate(body, start=2):
        asin = row[idx.get("asin", -1)] if idx.get("asin", -1) >= 0 and len(row) > idx.get("asin") else ""
        sku = row[idx.get("seller_sku", -1)] if idx.get("seller_sku", -1) >= 0 and len(row) > idx.get("seller_sku") else ""
        lookup[(asin, sku)] = (i, row)

    def set_field(row: List[str], field: str, value: str):
        if field not in idx:
            return
        col = idx[field]
        while len(row) <= col:
            row.append("")
        if value != "":
            row[col] = value

    for entry in data:
        asin = entry.get("asin", "")
        sku = entry.get("seller_sku", "")
        if not asin and not sku:
            continue
        key = (asin, sku)
        if key in lookup:
            row_idx, row = lookup[key]
        else:
            row_idx, row = None, [""] * len(headers)
            set_field(row, "asin", asin)
            set_field(row, "seller_sku", sku)
        supplier = entry.get("supplier", "")
        supply_code = entry.get("supply_code", "")
        discontinued = entry.get("discontinued", "").lower() == "true"
        drop = entry.get("drop", "").lower() == "true"
        sale_status = "discontinued" if discontinued else ("dropped" if drop else "active")

        set_field(row, "supplier_name", supplier)
        set_field(row, "supplier_code", supply_code)
        set_field(row, "sale_status", sale_status)
        set_field(row, "barcode", entry.get("barcode", ""))

        lookup[key] = (row_idx, row)

    # Rebuild rows, keeping existing order when possible
    out_rows = [headers]
    items = list(lookup.items())
    items.sort(key=lambda kv: kv[1][0] if kv[1][0] is not None else 10**9)
    for _, (row_idx, row) in items:
        out_rows.append(row)
    ws.clear()
    ws.update(range_name="A1", values=out_rows)
    print(f"Updated {TAB_NAME} with {len(out_rows) - 1} rows from {INPUT_PATH}")


if __name__ == "__main__":
    main()

