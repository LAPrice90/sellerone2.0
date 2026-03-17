"""
Backfill Product_DB with SKU->ASIN and catalog fields using listings + catalog snapshots.

Sources:
- out/merchant_listings_latest.csv (SKU->ASIN mapping)
- out/catalog_items_flat.csv (ASIN->catalog data)
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import gspread


PRODUCT_DB_SHEET_ID = "1b7iREy92vF_a1Lw72g0SOGS7t4-IOSBeeoHetLTN43s"
PRODUCT_DB_TAB = "Product_DB"
LISTINGS_CSV = Path("out/merchant_listings_latest.csv")
CATALOG_CSV = Path("out/catalog_items_flat.csv")
OUT_MISSING = Path("out/product_db_missing_fields.csv")


def get_gspread_client() -> gspread.Client:
    cred_path = Path("secrets/sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=str(cred_path))


def load_listings_map() -> dict[str, str]:
    if not LISTINGS_CSV.exists():
        return {}
    df = pd.read_csv(LISTINGS_CSV, dtype=str).fillna("")
    # Try known column variants
    sku_col = "seller-sku" if "seller-sku" in df.columns else ("seller_sku" if "seller_sku" in df.columns else None)
    asin_col = "asin1" if "asin1" in df.columns else ("asin" if "asin" in df.columns else "product-id")
    if not sku_col or asin_col not in df.columns:
        return {}
    mapping = {}
    for _, r in df.iterrows():
        sku = str(r.get(sku_col, "")).strip()
        asin = str(r.get(asin_col, "")).strip()
        if sku and asin and sku not in mapping:
            mapping[sku] = asin
    return mapping


def load_catalog_map() -> dict[str, dict[str, str]]:
    if not CATALOG_CSV.exists():
        return {}
    df = pd.read_csv(CATALOG_CSV, dtype=str).fillna("")
    if "asin" not in df.columns:
        return {}
    fields = [
        "item_name",
        "brand_name",
        "main_image",
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
    ]
    cat_map = {}
    for _, r in df.iterrows():
        asin = str(r.get("asin", "")).strip()
        if not asin or asin in cat_map:
            continue
        cat_map[asin] = {f: str(r.get(f, "")).strip() for f in fields}
    return cat_map


def main() -> None:
    client = get_gspread_client()
    sheet = client.open_by_key(PRODUCT_DB_SHEET_ID)
    ws = sheet.worksheet(PRODUCT_DB_TAB)
    rows = ws.get_all_values()
    if not rows:
        raise RuntimeError("Product_DB is empty")

    headers = rows[0]
    idx = {h: i for i, h in enumerate(headers)}
    required_cols = [
        "seller_sku",
        "asin",
        "title",
        "brand_name",
        "main_image",
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
        "last_updated_A002",
    ]
    for col in required_cols:
        if col not in idx:
            idx[col] = len(headers)
            headers.append(col)
            for r in rows[1:]:
                while len(r) < len(headers):
                    r.append("")

    sku_idx = idx["seller_sku"]
    asin_idx = idx["asin"]
    now_iso = datetime.now(timezone.utc).isoformat()

    sku_to_asin = load_listings_map()
    cat_map = load_catalog_map()

    missing_rows = []
    updated = 0

    for r in rows[1:]:
        if len(r) < len(headers):
            r.extend([""] * (len(headers) - len(r)))
        sku = str(r[sku_idx]).strip()
        asin = str(r[asin_idx]).strip()
        if sku and not asin and sku in sku_to_asin:
            r[asin_idx] = sku_to_asin[sku]
            asin = r[asin_idx]
            updated += 1

        if asin and asin in cat_map:
            cat = cat_map[asin]
            def set_val(field: str, value: str) -> None:
                if field in idx and value:
                    r[idx[field]] = value
            set_val("title", cat.get("item_name", ""))
            set_val("brand_name", cat.get("brand_name", ""))
            set_val("main_image", cat.get("main_image", ""))
            set_val("package_weight_value", cat.get("package_weight_value", ""))
            set_val("package_weight_unit", cat.get("package_weight_unit", ""))
            set_val("package_length", cat.get("package_length", ""))
            set_val("package_width", cat.get("package_width", ""))
            set_val("package_height", cat.get("package_height", ""))
            set_val("package_dimension_unit", cat.get("package_dimension_unit", ""))
            set_val("item_length", cat.get("item_length", ""))
            set_val("item_width", cat.get("item_width", ""))
            set_val("item_height", cat.get("item_height", ""))
            set_val("item_dimension_unit", cat.get("item_dimension_unit", ""))
            set_val("size", cat.get("size", ""))
            set_val("product_type", cat.get("product_type", ""))
            r[idx["last_updated_A002"]] = now_iso

        # missing fields report
        if sku:
            missing = []
            for field in ["title", "brand_name", "main_image"]:
                if not str(r[idx[field]]).strip():
                    missing.append(field)
            if missing:
                missing_rows.append({"seller_sku": sku, "asin": asin, "missing_fields": ",".join(missing)})

    ws.clear()
    ws.update(range_name="A1", values=[headers] + rows[1:])

    OUT_MISSING.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(missing_rows).to_csv(OUT_MISSING, index=False)
    print({"status": "success", "updated": updated, "missing_report": str(OUT_MISSING)})


if __name__ == "__main__":
    main()

