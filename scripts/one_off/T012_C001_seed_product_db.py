"""
Seed a Product_DB tab with manual + auto fields. Creates the tab with headers if missing; does not overwrite existing data.
"""

from __future__ import annotations

import os
from pathlib import Path

import gspread

SHEET_ID = "1b7iREy92vF_a1Lw72g0SOGS7t4-IOSBeeoHetLTN43s"
TAB_NAME = "Product_DB"

# Final column order (core identity first, then dimensions, supplier info, listing health, stock)
TARGET_HEADERS = [
    # Core product identity
    "asin",
    "seller_sku",
    "title",
    "brand_name",
    "main_image",
    # Physical: package then item, then type
    "package_weight_value",
    "package_weight_unit",
    "package_length",
    "package_width",
    "package_height",
    "package_dimension_unit",
    "item_length",
    "item_width",
    "item_height",
    "item_dimension_unit",
    "size",
    "product_type",
    # Supplier / purchasing info
    "supplier_code",
    "supplier_name",
    "supplier_pack_size",
    "amazon_pack_size",
    "pack_conversion_note",
    "moq",
    "supplier_catalog_price",
    "last_purchase_price",
    "target_margin",
    # Listing health / sales
    "sale_status",
    "vat_rate",
    "notes",
    # Stock / operational
    "stock_total",
    "stock_available",
    "stock_reserved",
    "stock_inbound",
    "last_updated",
]


def get_client() -> gspread.Client:
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        cred_path = str(Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=cred_path)


def main() -> None:
    client = get_client()
    sheet = client.open_by_key(SHEET_ID)
    try:
        ws = sheet.worksheet(TAB_NAME)
        rows = ws.get_all_values()
        current_headers = rows[0] if rows else []
        if current_headers == TARGET_HEADERS:
            print(f"Tab {TAB_NAME} already exists; no changes made.")
            return

        # Reorder existing data into the target header order (keeps values where names match)
        lookup = {h: i for i, h in enumerate(current_headers)}
        reordered = [TARGET_HEADERS]
        for row in rows[1:]:
            new_row = []
            for h in TARGET_HEADERS:
                idx = lookup.get(h)
                new_row.append(row[idx] if idx is not None and idx < len(row) else "")
            reordered.append(new_row)
        ws.clear()
        ws.update(range_name="A1", values=reordered)
        print(f"Reordered {TAB_NAME} to target headers; rows preserved: {len(reordered) - 1}")
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=TAB_NAME, rows=2000, cols=len(TARGET_HEADERS) + 5)
        ws.update(range_name="A1", values=[TARGET_HEADERS])
        print(f"Created {TAB_NAME} with headers.")


if __name__ == "__main__":
    main()
