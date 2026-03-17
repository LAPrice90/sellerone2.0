"""
Fetch Catalog Items (2022-04-01) for a set of ASINs and write a flattened view to Google Sheets.

What it does:
- Reads ASINs from a CSV (default: out/merchant_listings_latest.csv), using asin1 or product-id where product-id-type == 1 (ASIN).
- Calls Catalog Items with includedData=images,attributes,summaries,productTypes,identifiers,relationships.
- Flattens richer fields: asin, status, item_name, brand_name, product_type, main_image, upc, ean, gtin, parent_asin, color, size, manufacturer, part_number, model_number, package_weight/value/unit, package_dimensions, item_dimensions, bullet_points, keywords, error.
- Writes to a sheet tab "CatalogItems_raw" (overwrites) and updates Run_Status.
- Saves a CSV snapshot to out/catalog_items_flat.csv.

No summariesâ€”just a tabular view for inspection.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Set

import gspread
import pandas as pd

# Ensure package imports work when running directly
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api.get_catalog_items import fetch_catalog_item, get_lwa_access_token
SHEET_ID = "1b7iREy92vF_a1Lw72g0SOGS7t4-IOSBeeoHetLTN43s"
TAB_NAME = "CatalogItems_raw"
SUMMARY_TAB = "Listings_focus_summary"
PRODUCT_DB_TAB = "Product_DB"
RUN_STATUS_TAB = "Run_Status"
MARKETPLACE_ID = os.environ.get("MARKETPLACE_ID", "A1F83G8C2ARO7P")
INPUT_CSV = os.environ.get("CATALOG_INPUT_CSV", "out/merchant_listings_latest.csv")
INVENTORY_CSV = os.environ.get("CATALOG_INVENTORY_CSV", "out/inventory_summaries.csv")
INCLUDE_INVENTORY = os.environ.get("CATALOG_INCLUDE_INVENTORY", "1").strip() == "1"
LIMIT = int(os.environ.get("CATALOG_LIMIT", "0"))  # 0 = no limit
SLEEP_SEC = float(os.environ.get("CATALOG_SLEEP_SEC", "1.1"))
# Simple retry for transient failures (429/5xx). Set to 3 attempts by default.
MAX_RETRIES = int(os.environ.get("CATALOG_MAX_RETRIES", "3"))
FOCUS_COLUMNS = [
    "asin",
    "main_image",
    "ean",
    "size",
    "manufacturer",
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
]


def load_prev_focus_counts(sheet: gspread.Spreadsheet) -> dict:
    try:
        ws = sheet.worksheet(SUMMARY_TAB)
    except gspread.WorksheetNotFound:
        return {}
    values = ws.get_all_values()
    if not values or len(values) < 2:
        return {}
    prev = {}
    for row in values[1:]:
        if len(row) < 3 or row[0] != "A002":
            continue
        col = row[1]
        try:
            prev_count = int(row[2])
        except Exception:
            prev_count = 0
        prev[col] = prev_count
    return prev


def summarize_focus(df: pd.DataFrame, prev_counts: dict) -> list[list[str]]:
    rows: list[list[str]] = [["script", "column", "prev_non_empty", "curr_non_empty", "delta", "percent_change", "flag"]]
    script_name = "A002"
    for col in FOCUS_COLUMNS:
        curr = int((df[col].astype(str).str.len() > 0).sum()) if col in df.columns else 0
        prev = prev_counts.get(col, 0)
        delta = curr - prev
        pct = ""
        if prev > 0:
            pct = f"{(delta / prev) * 100:.1f}%"
        if prev > 0 and curr == 0:
            flag = "drop_to_zero"
        elif prev > 0 and curr < prev * 0.8:
            flag = "drop_over_20pct"
        else:
            flag = "ok"
        rows.append([script_name, col, str(prev), str(curr), str(delta), pct, flag])
    return rows
# Default on so you donâ€™t have to set anything; toggle via env if needed.
DEBUG_ATTRS = os.environ.get("DEBUG_ATTRS", "true").lower() == "true"


def load_env(paths: List[str] | None = None) -> None:
    paths = paths or ["secrets/.env", ".env"]
    for p in paths:
        path = Path(p)
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.split("#", 1)[0].strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
        break


def load_asins(csv_path: Path, limit: int) -> List[str]:
    df = pd.read_csv(csv_path, dtype=str).fillna("")
    asins: List[str] = []
    seen: Set[str] = set()
    no_limit = limit <= 0
    if "asin" in df.columns:
        for a in df["asin"].tolist():
            if a and a not in seen:
                seen.add(a)
                asins.append(a)
                if not no_limit and len(asins) >= limit:
                    return asins
    if "asin1" in df.columns:
        for a in df["asin1"].tolist():
            if a and a not in seen:
                seen.add(a)
                asins.append(a)
                if not no_limit and len(asins) >= limit:
                    return asins
    if "product-id" in df.columns and "product-id-type" in df.columns:
        for _, row in df.iterrows():
            if not no_limit and len(asins) >= limit:
                break
            pid_type = row.get("product-id-type", "")
            if str(pid_type) != "1":  # 1 = ASIN
                continue
            asin = row.get("product-id", "")
            if asin and asin not in seen:
                seen.add(asin)
                asins.append(asin)
                if not no_limit and len(asins) >= limit:
                    break
    return asins


def extend_asins_from_inventory(asins: List[str], limit: int, csv_path: Path) -> List[str]:
    if not csv_path.exists():
        return asins
    if limit > 0 and len(asins) >= limit:
        return asins
    df = pd.read_csv(csv_path, dtype=str).fillna("")
    if "asin" not in df.columns:
        return asins
    seen = set(asins)
    no_limit = limit <= 0
    for asin in df["asin"].tolist():
        if not asin or asin in seen:
            continue
        seen.add(asin)
        asins.append(asin)
        if not no_limit and len(asins) >= limit:
            break
    return asins


def flatten_item(rec: dict) -> dict:
    asin = rec.get("asin", "")
    status = rec.get("status", "")
    data = rec.get("data") or {}
    error = rec.get("error")

    def first(lst, key):
        if not lst:
            return ""
        return lst[0].get(key, "")

    def extract_from_entry(entry: dict) -> str:
        direct = entry.get("link") or entry.get("url") or entry.get("linkUrl")
        if direct:
            return direct
        variants = entry.get("variants") or []
        if variants:
            main_variant = next((v for v in variants if v.get("variant") == "MAIN"), None)
            candidate = main_variant or variants[0]
            return candidate.get("link") or candidate.get("url") or candidate.get("linkUrl") or ""
        # Some Catalog Items responses wrap images under entry["images"]
        nested = entry.get("images") or []
        for n in nested:
            link = n.get("link") or n.get("url") or n.get("linkUrl")
            if link:
                return link
            subvars = n.get("variants") or []
            if subvars:
                mv = next((v for v in subvars if v.get("variant") == "MAIN"), None)
                cand = mv or subvars[0]
                link = cand.get("link") or cand.get("url") or cand.get("linkUrl") or ""
                if link:
                    return link
        return ""

    def main_image(images):
        if not images:
            return ""
        for img in images:
            link = extract_from_entry(img)
            if link:
                return link
        return ""

    images = data.get("images") or []
    summaries = data.get("summaries") or []
    product_types = data.get("productTypes") or []
    identifiers = data.get("identifiers") or []
    relationships = data.get("relationships") or []
    attributes = data.get("attributes") or {}

    item_name = first(summaries, "itemName")
    brand_name = first(summaries, "brandName")
    product_type = first(product_types, "productType")
    main_img = main_image(images)

    upc = ean = gtin = ""
    for ident in identifiers:
        ids = ident.get("identifiers") or []
        for entry in ids:
            typ = (entry.get("identifierType") or entry.get("type") or "").upper()
            val = entry.get("identifier") or ""
            if typ == "UPC" and not upc:
                upc = val
            if typ == "EAN" and not ean:
                ean = val
            if typ == "GTIN" and not gtin:
                gtin = val

    parent_asin = ""
    for rel in relationships:
        if rel.get("type") and str(rel.get("type")).upper() == "PARENT":
            ids = rel.get("identifiers") or []
            if ids:
                parent_asin = ids[0].get("asin", "") or parent_asin
                if parent_asin:
                    break

    def attr_value(key: str) -> str:
        if key not in attributes:
            return ""
        vals = attributes.get(key) or []
        if not vals:
            return ""
        # Attributes may be list of dicts with "value" or raw strings
        first_val = vals[0]
        if isinstance(first_val, dict):
            return str(first_val.get("value", "") or first_val.get("valueString", "") or "")
        return str(first_val)

    def attr_list(key: str) -> str:
        if key not in attributes:
            return ""
        vals = attributes.get(key) or []
        cleaned = []
        for v in vals:
            if isinstance(v, dict):
                cleaned.append(str(v.get("value", "") or v.get("valueString", "") or ""))
            else:
                cleaned.append(str(v))
        return "; ".join([c for c in cleaned if c])

    def attr_image(key: str) -> str:
        if key not in attributes:
            return ""
        vals = attributes.get(key) or []
        if not vals:
            return ""
        entry = vals[0]
        if isinstance(entry, dict):
            return entry.get("link") or entry.get("url") or entry.get("value") or entry.get("valueString") or ""
        return str(entry)

    if not main_img:
        # Fallback to attribute-based image fields if images array is empty
        for k in ("mainImage", "imageUrl", "productImage"):
            main_img = attr_image(k)
            if main_img:
                break

    color = attr_value("color")
    size = attr_value("size")
    manufacturer = attr_value("manufacturer")
    part_number = attr_value("partNumber")
    model_number = attr_value("modelNumber")
    bullet_points = attr_list("bulletPoint")
    keywords = attr_list("itemKeywords")

    def dimension_block(key: str, alt_keys: list[str] | None = None) -> tuple[str, str, str, str]:
        keys = [key] + (alt_keys or [])
        block = []
        chosen_key = ""
        for k in keys:
            block = attributes.get(k) or []
            if block:
                chosen_key = k
                break
        if not block:
            return "", "", "", ""
        entry = block[0]
        if isinstance(entry, dict):
            unit = entry.get("unit", "") or entry.get("unitOfMeasure", "")

            def extract_val(comp):
                if comp is None:
                    return "", ""
                if isinstance(comp, dict):
                    return comp.get("value", "") or "", comp.get("unit", "") or comp.get("unitOfMeasure", "") or ""
                return comp, ""

            length_val, length_unit = extract_val(entry.get("length"))
            width_val, width_unit = extract_val(entry.get("width"))
            height_val, height_unit = extract_val(entry.get("height"))
            # Prefer explicit unit on entry; otherwise fall back to component units
            unit = unit or length_unit or width_unit or height_unit
            return str(length_val or ""), str(width_val or ""), str(height_val or ""), unit
        return "", "", "", ""

    pkg_len, pkg_wid, pkg_hgt, pkg_unit = dimension_block("packageDimensions", ["item_package_dimensions", "itemDimensions", "item_package_dimensions"])
    item_len, item_wid, item_hgt, item_unit = dimension_block("itemDimensions", ["item_dimensions", "item_length_width_height"])

    def weight_block(key: str, alt_keys: list[str] | None = None) -> tuple[str, str]:
        keys = [key] + (alt_keys or [])
        block = []
        for k in keys:
            block = attributes.get(k) or []
            if block:
                break
        if not block:
            return "", ""
        entry = block[0]
        if isinstance(entry, dict):
            return str(entry.get("value", "")), str(entry.get("unit", "") or entry.get("unitOfMeasure", ""))
        return "", ""

    pkg_weight_value, pkg_weight_unit = weight_block("itemPackageWeight", ["item_package_weight"])

    return {
        "asin": asin,
        "status": status,
        "item_name": item_name,
        "brand_name": brand_name,
        "product_type": product_type,
        "main_image": main_img,
        "upc": upc,
        "ean": ean,
        "gtin": gtin,
        "parent_asin": parent_asin,
        "color": color,
        "size": size,
        "manufacturer": manufacturer,
        "part_number": part_number,
        "model_number": model_number,
        "package_weight_value": pkg_weight_value,
        "package_weight_unit": pkg_weight_unit,
        "package_length": pkg_len,
        "package_width": pkg_wid,
        "package_height": pkg_hgt,
        "package_dimension_unit": pkg_unit,
        "item_length": item_len,
        "item_width": item_wid,
        "item_height": item_hgt,
        "item_dimension_unit": item_unit,
        "bullet_points": bullet_points,
        "keywords": keywords,
        "error": json.dumps(error) if error else "",
    }


def get_gspread_client() -> gspread.Client:
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        cred_path = str(Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=cred_path)


def export_product_db(sheet: gspread.Spreadsheet) -> None:
    """Dump Product_DB sheet to out/product_db_preview.csv to keep local copy fresh."""
    try:
        ws = sheet.worksheet(PRODUCT_DB_TAB)
    except gspread.WorksheetNotFound:
        return
    rows = ws.get_all_values()
    if not rows:
        return
    Path("out").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows[1:], columns=rows[0]).to_csv("out/product_db_preview.csv", index=False)
    print("Saved Product_DB preview to out/product_db_preview.csv")


def write_raw_and_summary(df: pd.DataFrame) -> None:
    client = get_gspread_client()
    sheet = client.open_by_key(SHEET_ID)

    raw_values = [list(df.columns)] + df.fillna("").astype(str).values.tolist()
    try:
        ws_raw = sheet.worksheet(TAB_NAME)
    except gspread.WorksheetNotFound:
        ws_raw = sheet.add_worksheet(title=TAB_NAME, rows=max(len(raw_values) + 10, 2000), cols=max(len(df.columns) + 5, 40))
    else:
        ws_raw.clear()
    ws_raw.update(range_name="A1", values=raw_values)

    # Update Product_DB auto fields (preserve manual columns)
    try:
        ws_prod = sheet.worksheet(PRODUCT_DB_TAB)
        prod_rows = ws_prod.get_all_values()
        if not prod_rows:
            raise ValueError("Product_DB tab empty")
        headers_prod = prod_rows[0]
        idx_map = {h: i for i, h in enumerate(headers_prod)}
        if "last_updated_A002" not in idx_map:
            idx_map["last_updated_A002"] = len(headers_prod)
            headers_prod.append("last_updated_A002")
            for row in prod_rows[1:]:
                while len(row) < len(headers_prod):
                    row.append("")
        # Build lookups so we can match by (asin, sku) and fall back to asin-only
        prod_dict = {}
        asin_index = {}
        for idx, row in enumerate(prod_rows[1:], start=2):
            asin_val = row[idx_map.get("asin", -1)] if idx_map.get("asin", -1) >= 0 and len(row) > idx_map.get("asin") else ""
            sku_val = row[idx_map.get("seller_sku", -1)] if idx_map.get("seller_sku", -1) >= 0 and len(row) > idx_map.get("seller_sku") else ""
            key = (asin_val, sku_val)
            prod_dict[key] = [idx, row]
            if asin_val:
                asin_index.setdefault(asin_val, []).append([idx, row])
        now_iso = datetime.now(timezone.utc).isoformat()
        for _, r in df.iterrows():
            asin = str(r.get("asin", ""))
            sku = str(r.get("seller_sku", ""))
            if not asin and not sku:
                continue
            # First try exact (asin, sku), else any row with same asin.
            targets = []
            key = (asin, sku)
            if key in prod_dict:
                targets = [prod_dict[key]]
            elif asin and asin in asin_index:
                targets = asin_index[asin]
            else:
                # New row only when asin not seen at all
                row_idx, row_data = None, [""] * len(headers_prod)
                if "asin" in idx_map:
                    while len(row_data) <= idx_map["asin"]:
                        row_data.append("")
                    row_data[idx_map["asin"]] = asin
                if "seller_sku" in idx_map:
                    while len(row_data) <= idx_map["seller_sku"]:
                        row_data.append("")
                    row_data[idx_map["seller_sku"]] = sku
                target = [row_idx, row_data]
                targets = [target]
                prod_dict[key] = target
                if asin:
                    asin_index.setdefault(asin, []).append(target)

            def set_val(row_data, field, value):
                if field in idx_map and value not in (None, ""):
                    col = idx_map[field]
                    while len(row_data) <= col:
                        row_data.append("")
                    row_data[col] = str(value)

            for target in targets:
                row_idx, row_data = target
                set_val(row_data, "title", r.get("item_name", ""))
                set_val(row_data, "brand_name", r.get("brand_name", ""))
                set_val(row_data, "main_image", r.get("main_image", ""))
                set_val(row_data, "size", r.get("size", ""))
                set_val(row_data, "product_type", r.get("product_type", ""))
                set_val(row_data, "package_weight_value", r.get("package_weight_value", ""))
                set_val(row_data, "package_weight_unit", r.get("package_weight_unit", ""))
                set_val(row_data, "package_length", r.get("package_length", ""))
                set_val(row_data, "package_width", r.get("package_width", ""))
                set_val(row_data, "package_height", r.get("package_height", ""))
                set_val(row_data, "package_dimension_unit", r.get("package_dimension_unit", ""))
                set_val(row_data, "item_length", r.get("item_length", ""))
                set_val(row_data, "item_width", r.get("item_width", ""))
                set_val(row_data, "item_height", r.get("item_height", ""))
                set_val(row_data, "item_dimension_unit", r.get("item_dimension_unit", ""))
                set_val(row_data, "last_updated", now_iso)
                set_val(row_data, "last_updated_A002", now_iso)
        # rebuild rows preserving order where possible
        rows_out = [headers_prod]
        items = list(prod_dict.items())
        items.sort(key=lambda kv: kv[1][0] if kv[1][0] is not None else 10**9)
        for _, (idx, row_data) in items:
            rows_out.append(row_data)
        ws_prod.clear()
        ws_prod.update(range_name="A1", values=rows_out)
    except Exception:
        pass

    prev_counts = load_prev_focus_counts(sheet)
    summary_rows = summarize_focus(df, prev_counts)
    summary_headers = summary_rows[0]
    summary_values = summary_rows
    try:
        ws_summary = sheet.worksheet(SUMMARY_TAB)
        existing = ws_summary.get_all_values()
    except gspread.WorksheetNotFound:
        ws_summary = sheet.add_worksheet(title=SUMMARY_TAB, rows=max(len(summary_values) + 10, 2000), cols=max(len(summary_headers) + 5, 40))
        existing = []
    # Preserve other scripts' rows, replace A002 rows
    other_rows = [r for r in (existing[1:] if existing else []) if r and r[0] != "A002"]
    merged = [summary_headers] + other_rows + summary_values[1:]
    ws_summary.clear()
    ws_summary.update(range_name="A1", values=merged)
    export_product_db(sheet)


def append_run_status(sheet: gspread.Spreadsheet, row: list[str]) -> None:
    headers = [
        "script",
        "mode",
        "marketplace_id",
        "status",
        "alert",
        "run_id",
        "started_at",
        "ended_at",
        "duration_seconds",
        "attempts",
        "records_count",
        "col_count",
        "snapshot_path",
        "sheet_tabs",
        "poll_interval",
        "max_attempts",
        "consecutive_failures",
        "consecutive_successes",
        "env",
        "version",
        "last_error",
    ]
    try:
        ws = sheet.worksheet(RUN_STATUS_TAB)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=RUN_STATUS_TAB, rows=100, cols=len(headers))
        ws.update(range_name="A1", values=[headers])
    else:
        if ws.row_values(1) != headers:
            ws.clear()
            ws.update(range_name="A1", values=[headers])

    existing = ws.get_all_values()
    index = {}
    for idx, r in enumerate(existing[1:], start=2):
        if len(r) < 3:
            continue
        index[(r[0], r[1], r[2])] = idx

    key = (row[0], row[1], row[2])
    if key in index:
        ws.update(range_name=f"A{index[key]}:U{index[key]}", values=[row])
    else:
        ws.append_row(row, value_input_option="RAW")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Catalog Items and write flattened data to Sheets/CSV.")
    parser.add_argument("--input-csv", default=INPUT_CSV, help="CSV with asin1 or product-id columns.")
    parser.add_argument("--limit", type=int, default=LIMIT, help="Max ASINs to fetch.")
    parser.add_argument("--marketplace-id", default=MARKETPLACE_ID, help="Marketplace ID.")
    parser.add_argument("--sleep-sec", type=float, default=SLEEP_SEC, help="Seconds to sleep between calls.")
    args = parser.parse_args()

    load_env()
    token = get_lwa_access_token()
    if not args.marketplace_id:
        raise RuntimeError("marketplace-id is required")

    started_at = datetime.now(timezone.utc)
    script_name = "A002_run_catalog_items_to_sheet.py"
    mode = "default"
    status = "success"
    alert = ""
    last_error = ""
    env_name = os.environ.get("ENV", "prod")
    git_version = os.environ.get("GIT_COMMIT", "")
    sheet_tabs_written: List[str] = []
    snapshot_path = ""
    attempts_used = 0
    row_count = 0
    col_count = 0

    client = get_gspread_client()
    sheet = client.open_by_key(SHEET_ID)

    try:
        asins = load_asins(Path(args.input_csv), args.limit)
        if INCLUDE_INVENTORY:
            asins = extend_asins_from_inventory(asins, args.limit, Path(INVENTORY_CSV))
        attempts_used = len(asins)
        source_note = f"{args.input_csv}"
        if INCLUDE_INVENTORY and Path(INVENTORY_CSV).exists():
            source_note = f"{args.input_csv} + {INVENTORY_CSV}"
        print(f"Fetching {len(asins)} ASINs from {source_note} (limit={args.limit})")

        records = []
        for i, asin in enumerate(asins, 1):
            rec = None
            for attempt in range(1, MAX_RETRIES + 1):
                rec = fetch_catalog_item(asin, args.marketplace_id, token)
                status_code = rec.get("status")
                if status_code == 200:
                    break
                if status_code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES:
                    backoff = args.sleep_sec * attempt
                    print(f"[{i}/{len(asins)}] ASIN {asin} status {status_code}, retry {attempt}/{MAX_RETRIES} after {backoff:.1f}s")
                    time.sleep(backoff)
                    continue
                break
            records.append(rec or {})
            print(f"[{i}/{len(asins)}] ASIN {asin} status {rec.get('status') if rec else 'error'}")
            time.sleep(args.sleep_sec)

        flat = [flatten_item(r) for r in records]
        df = pd.DataFrame(flat)
        row_count = len(df)
        col_count = len(df.columns)

        if DEBUG_ATTRS:
            debug_path = Path("out/debug_catalog_attrs.jsonl")
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            with debug_path.open("a", encoding="utf-8") as fh:
                for rec, flat_row in zip(records, flat):
                    missing_dims = any(
                        not flat_row.get(k)
                        for k in [
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
                        ]
                    )
                    if missing_dims:
                        fh.write(
                            json.dumps(
                                {
                                    "asin": flat_row.get("asin"),
                                    "flattened": flat_row,
                                    "raw_attributes": (rec.get("data") or {}).get("attributes"),
                                }
                            )
                            + "\n"
                        )

        out_path = Path("out/catalog_items_flat.csv")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False)
        snapshot_path = str(out_path)
        print(f"Saved flattened catalog data to {out_path}")

        write_raw_and_summary(df)
        sheet_tabs_written = [TAB_NAME, SUMMARY_TAB]
        print(f"Wrote {len(df)} rows to sheet tabs {TAB_NAME} and {SUMMARY_TAB}")
    except Exception as exc:
        status = "error"
        alert = "error"
        last_error = str(exc)
        df = pd.DataFrame()

    ended_at = datetime.now(timezone.utc)
    duration_seconds = str(int((ended_at - started_at).total_seconds()))

    # consecutive counters
    consecutive_failures = 0
    consecutive_successes = 0
    try:
        ws_status = sheet.worksheet(RUN_STATUS_TAB)
        existing = ws_status.get_all_values()
    except gspread.WorksheetNotFound:
        existing = []
        ws_status = None
    headers = [
        "script",
        "mode",
        "marketplace_id",
        "status",
        "alert",
        "run_id",
        "started_at",
        "ended_at",
        "duration_seconds",
        "attempts",
        "records_count",
        "col_count",
        "snapshot_path",
        "sheet_tabs",
        "poll_interval",
        "max_attempts",
        "consecutive_failures",
        "consecutive_successes",
        "env",
        "version",
        "last_error",
    ]
    if existing and existing[0] == headers:
        index = {(r[0], r[1], r[2]): r for r in existing[1:] if len(r) >= 3}
        key = (script_name, mode, args.marketplace_id)
        prev = index.get(key, [])
        try:
            consecutive_failures = int(prev[16]) if len(prev) > 16 else 0
        except Exception:
            consecutive_failures = 0
        try:
            consecutive_successes = int(prev[17]) if len(prev) > 17 else 0
        except Exception:
            consecutive_successes = 0
    if status == "success":
        consecutive_successes += 1
        consecutive_failures = 0
    else:
        consecutive_failures += 1
        consecutive_successes = 0

    run_id = f"{script_name}-{started_at.isoformat()}"

    status_row = [
        script_name,
        mode,
        args.marketplace_id,
        status,
        alert,
        run_id,
        started_at.isoformat(),
        ended_at.isoformat(),
        duration_seconds,
        str(attempts_used),
        str(row_count),
        str(col_count),
        snapshot_path,
        ";".join(sheet_tabs_written),
        "",  # poll_interval (not used here)
        "",  # max_attempts (not used here)
        str(consecutive_failures),
        str(consecutive_successes),
        env_name,
        git_version,
        last_error,
    ]
    append_run_status(sheet, status_row)


if __name__ == "__main__":
    main()


