from __future__ import annotations

import argparse
import importlib
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import ensure_manager_test_mode_dir
from scripts.flows.F.price_list_manager._schemas import (
    BATCH_ROW_COLUMNS,
    BATCH_SCAN_ELIGIBILITY_COLUMNS,
    MANAGER_HEALTH_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
    SUPPLIER_REGISTRY_COLUMNS,
)
from scripts.flows.F.price_list_manager.timeout_queue import refresh_timeout_queue_files


SKU_ALIASES = {"supplier_sku", "sku", "product_code", "code", "stock_code", "item_code", "part_number"}
TITLE_ALIASES = {"supplier_title", "title", "product_title", "product_name", "description", "product_description", "name"}
BARCODE_ALIASES = {"barcode", "bar_code", "ean", "ean13", "ean_upc", "ean / upc", "upc", "gtin"}
COST_ALIASES = {"unit_cost", "cost", "price", "net_cost", "trade_price", "wholesale_price", "buy_price"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_converter(converter_id: str):
    if not converter_id:
        return None
    try:
        module = importlib.import_module(f"scripts.flows.F.suppliers.{converter_id}")
    except ModuleNotFoundError:
        return None
    return getattr(module, "convert_supplier", None)


def _converter_can_handle_suffix(converter_id: str, suffix: str) -> bool:
    if not converter_id:
        return False
    try:
        module = importlib.import_module(f"scripts.flows.F.suppliers.{converter_id}")
    except ModuleNotFoundError:
        return False
    supported_suffixes = getattr(module, "SUPPORTED_SUFFIXES", {".xlsx", ".xls"})
    return suffix.lower() in {normalize_text(value).lower() for value in supported_suffixes}


def _registry_lookup(registry: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        normalize_text(row.get("supplier_id", "")): row
        for _, row in registry.iterrows()
        if normalize_text(row.get("supplier_id", ""))
    }


def _sha1_text(value: str) -> str:
    import hashlib

    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def _normalize_column(value: object) -> str:
    raw = normalize_text(value).lower()
    out = []
    for char in raw:
        out.append(char if char.isalnum() else "_")
    return "_".join(part for part in "".join(out).split("_") if part)


def _find_column(columns: list[str], aliases: set[str]) -> str:
    normalized = {_normalize_column(column): column for column in columns}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    return ""


def _clean_barcode(value: object) -> str:
    raw = normalize_text(value)
    if raw.endswith(".0") and raw[:-2].isdigit():
        raw = raw[:-2]
    digits = "".join(char for char in raw if char.isdigit())
    return digits or raw


def _clean_cost(value: object) -> str:
    raw = normalize_text(value).replace(",", "").replace(chr(163), "").replace("$", "").replace("EUR", "")
    return raw.strip()


def _source_lookup_from_converter(batch: pd.Series, supplier: pd.Series | None) -> dict[str, dict[str, str]]:
    source_path = Path(normalize_text(batch.get("source_file_path", "")))
    if not source_path.exists() or not source_path.is_file():
        return {}
    converter_id = normalize_text(supplier.get("converter_id", "")) if supplier is not None else ""
    converter = _resolve_converter(converter_id)
    if converter is None or not _converter_can_handle_suffix(converter_id, source_path.suffix):
        return {}

    supplier_id = normalize_text(batch.get("supplier_id", ""))
    supplier_name = normalize_text(supplier.get("supplier_name", "")) if supplier is not None else supplier_id
    valid_df, _ = converter(
        source_path,
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        source_url=normalize_text(supplier.get("source_url", "")) if supplier is not None else "",
        source_seen_at_utc=normalize_text(batch.get("source_received_at_utc", "")) or _utc_now_iso(),
        currency="GBP",
        vat_rate="20",
        skip_sku_suffixes=[],
    )

    out: dict[str, dict[str, str]] = {}
    for _, row in valid_df.iterrows():
        row_hash = normalize_text(row.get("row_hash", ""))
        if not row_hash:
            continue
        out[row_hash] = {
            "supplier_title": normalize_text(row.get("supplier_title", "")),
            "vat_rate": normalize_text(row.get("vat_rate", "")) or "20",
        }
    return out


def _source_lookup_from_generic_csv(batch: pd.Series) -> dict[str, dict[str, str]]:
    source_path = Path(normalize_text(batch.get("source_file_path", "")))
    if not source_path.exists() or not source_path.is_file() or source_path.suffix.lower() not in {".csv", ".txt"}:
        return {}
    try:
        source = pd.read_csv(source_path, dtype=str).fillna("")
    except UnicodeDecodeError:
        source = pd.read_csv(source_path, dtype=str, encoding="latin1").fillna("")
    if source.empty:
        return {}
    columns = list(source.columns)
    sku_column = _find_column(columns, SKU_ALIASES)
    title_column = _find_column(columns, TITLE_ALIASES)
    barcode_column = _find_column(columns, BARCODE_ALIASES)
    cost_column = _find_column(columns, COST_ALIASES)
    if not title_column or not barcode_column or not cost_column:
        return {}

    supplier_id = normalize_text(batch.get("supplier_id", ""))
    file_hash = normalize_text(batch.get("source_file_hash", ""))
    out: dict[str, dict[str, str]] = {}
    for index, raw_row in source.reset_index(drop=True).iterrows():
        sku = normalize_text(raw_row.get(sku_column, "")) if sku_column else f"row-{index + 1}"
        title = normalize_text(raw_row.get(title_column, ""))
        barcode = _clean_barcode(raw_row.get(barcode_column, ""))
        unit_cost = _clean_cost(raw_row.get(cost_column, ""))
        row_hash = _sha1_text("|".join([supplier_id, file_hash, str(index), sku, barcode, unit_cost]))
        if row_hash:
            out[row_hash] = {"supplier_title": title, "vat_rate": "20"}
    return out


def _source_lookup_for_batch(batch: pd.Series, supplier: pd.Series | None) -> dict[str, dict[str, str]]:
    lookup = _source_lookup_from_converter(batch, supplier)
    generic_lookup = _source_lookup_from_generic_csv(batch)
    if generic_lookup:
        lookup.update(generic_lookup)
    return lookup


def enrich_batch_rows_for_f061(root: Path | None = None, *, observed_utc: str | None = None) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=root)
    observed = observed_utc or _utc_now_iso()
    test_dir = paths.test_mode_dir
    rows_path = test_dir / "batch_rows.csv"
    batches_path = test_dir / "price_list_batches.csv"
    health_path = test_dir / "health.csv"

    rows = read_csv(rows_path, BATCH_ROW_COLUMNS)
    batches = read_csv(batches_path, PRICE_LIST_BATCH_COLUMNS)
    registry = read_csv(test_dir / "supplier_registry.csv", SUPPLIER_REGISTRY_COLUMNS)
    if rows.empty:
        raise FileNotFoundError("batch_rows.csv is required before F061 enrichment")

    refresh_timeout_queue_files(root=paths.root, observed_utc=observed)
    eligibility = read_csv(test_dir / "batch_scan_eligibility.csv", BATCH_SCAN_ELIGIBILITY_COLUMNS)
    if eligibility.empty:
        required_row_keys = set(rows[rows["scan_eligibility"].map(normalize_text) == "scan_now"]["row_key"].tolist())
    else:
        required_row_keys = set(
            eligibility[eligibility["scan_decision"].map(normalize_text) == "scan"]["row_key"].map(normalize_text).tolist()
        )
    required_mask = rows["row_key"].map(normalize_text).isin(required_row_keys)
    before_missing_title = int(
        (
            required_mask
            & (rows["supplier_title"].map(normalize_text) == "")
        ).sum()
    )
    before_missing_vat = int(
        (
            required_mask
            & (rows["vat_rate"].map(normalize_text) == "")
        ).sum()
    )

    supplier_by_id = _registry_lookup(registry)
    enriched = rows.copy()
    enriched_count = 0
    for _, batch in batches.iterrows():
        batch_id = normalize_text(batch.get("batch_id", ""))
        supplier_id = normalize_text(batch.get("supplier_id", ""))
        if not batch_id:
            continue
        source_lookup = _source_lookup_for_batch(batch, supplier_by_id.get(supplier_id))
        if not source_lookup:
            continue
        batch_mask = enriched["batch_id"].map(normalize_text) == batch_id
        for row_index in enriched[batch_mask].index:
            row_key = normalize_text(enriched.at[row_index, "row_key"])
            source_payload = source_lookup.get(row_key)
            if source_payload is None:
                continue
            if normalize_text(enriched.at[row_index, "supplier_title"]) == "":
                enriched.at[row_index, "supplier_title"] = source_payload["supplier_title"]
                enriched_count += 1
            if normalize_text(enriched.at[row_index, "vat_rate"]) == "":
                enriched.at[row_index, "vat_rate"] = source_payload["vat_rate"]

    enriched["vat_rate"] = enriched["vat_rate"].map(lambda value: normalize_text(value) or "20")
    enriched = write_csv(rows_path, enriched, BATCH_ROW_COLUMNS)
    timeout_summary = refresh_timeout_queue_files(root=paths.root, observed_utc=observed)

    enriched_required_mask = enriched["row_key"].map(normalize_text).isin(required_row_keys)
    after_missing_title = int(
        (
            enriched_required_mask
            & (enriched["supplier_title"].map(normalize_text) == "")
        ).sum()
    )
    after_missing_vat = int(
        (
            enriched_required_mask
            & (enriched["vat_rate"].map(normalize_text) == "")
        ).sum()
    )

    existing_health = read_csv(health_path, MANAGER_HEALTH_COLUMNS)
    health_row = pd.DataFrame(
        [
            {
                "check": "batch_row_f061_required_fields",
                "status": "ok" if after_missing_title == 0 and after_missing_vat == 0 else "fail",
                "value": str(len(enriched.index)),
                "notes": (
                    f"before_missing_title={before_missing_title};after_missing_title={after_missing_title};"
                    f"before_missing_vat={before_missing_vat};after_missing_vat={after_missing_vat};"
                    f"enriched_titles={enriched_count};timeout_scan_rows={timeout_summary['scan_rows']};"
                    f"timeout_skip_rows={timeout_summary['timeout_skip_rows']}"
                ),
                "observed_utc": observed,
                "source_path": str(rows_path),
            }
        ]
    )
    health = write_csv(health_path, pd.concat([existing_health, health_row], ignore_index=True), MANAGER_HEALTH_COLUMNS)

    summary = {
        "status": "success" if after_missing_title == 0 and after_missing_vat == 0 else "blocked",
        "batch_rows": int(len(enriched.index)),
        "required_f061_rows": int(len(required_row_keys)),
        "before_missing_title": before_missing_title,
        "after_missing_title": after_missing_title,
        "before_missing_vat": before_missing_vat,
        "after_missing_vat": after_missing_vat,
        "enriched_titles": int(enriched_count),
        "timeout_scan_rows": int(timeout_summary["scan_rows"]),
        "timeout_skip_rows": int(timeout_summary["timeout_skip_rows"]),
        "health_fail_rows": int((health["status"].map(lambda value: normalize_text(value).lower()) == "fail").sum()),
        "batch_rows_path": str(rows_path),
    }
    print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich price-list manager batch rows with F061 required fields.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--observed-utc", default=None)
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    enrich_batch_rows_for_f061(root=root, observed_utc=args.observed_utc)


if __name__ == "__main__":
    main()
