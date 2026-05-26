from __future__ import annotations

import argparse
import hashlib
import importlib
import shutil
import sys
import zipfile
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
    MANAGER_HEALTH_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
    SOURCE_ACQUISITION_COLUMNS,
    SUPPLIER_REGISTRY_COLUMNS,
)
from scripts.flows.F.price_list_manager.timeout_queue import refresh_timeout_queue_files


SKU_ALIASES = {"supplier_sku", "sku", "product_code", "code", "stock_code", "item_code", "part_number"}
TITLE_ALIASES = {"supplier_title", "title", "product_title", "product_name", "description", "product_description", "name"}
BARCODE_ALIASES = {"barcode", "bar_code", "ean", "ean13", "upc", "gtin"}
COST_ALIASES = {"unit_cost", "cost", "price", "net_cost", "trade_price", "wholesale_price", "buy_price"}
CURRENCY_ALIASES = {"currency", "ccy"}
ZIP_INNER_PRICE_FILE_SUFFIXES = {".csv", ".tsv", ".txt", ".xlsx", ".xls"}
SUPERSEDABLE_BATCH_STATUSES = {
    "received",
    "converted",
    "imported_from_source",
    "recommendation_ready",
    "blocked",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha1_bytes(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha1_text(value: str) -> str:
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


def _is_valid_barcode(value: str) -> bool:
    return value.isdigit() and len(value) in {8, 12, 13, 14}


def _clean_cost(value: object) -> str:
    raw = normalize_text(value).replace(",", "").replace(chr(163), "").replace("$", "").replace("EUR", "")
    return raw.strip()


def _valid_cost(value: str) -> bool:
    try:
        return float(value) > 0
    except ValueError:
        return False


def _load_source_file(path: Path) -> pd.DataFrame:
    if path.suffix.lower() not in {".csv", ".txt"}:
        raise ValueError(f"only CSV/TXT test-mode imports are supported for now: {path}")
    return pd.read_csv(path, dtype=str).fillna("")


def _load_supplier_registry(paths) -> dict[str, dict[str, str]]:
    registry = read_csv(paths.test_mode_dir / "supplier_registry.csv", SUPPLIER_REGISTRY_COLUMNS)
    config_registry = read_csv(
        paths.root / "config" / "feeder" / "price_list_manager" / "suppliers.csv",
        SUPPLIER_REGISTRY_COLUMNS,
    )
    if registry.empty:
        registry = config_registry
    elif not config_registry.empty:
        existing_ids = {normalize_text(value).lower() for value in registry["supplier_id"].tolist()}
        missing = config_registry[
            ~config_registry["supplier_id"].map(lambda value: normalize_text(value).lower()).isin(existing_ids)
        ].copy()
        if not missing.empty:
            registry = pd.concat([registry, missing], ignore_index=True)
    out: dict[str, dict[str, str]] = {}
    for _, row in registry.iterrows():
        supplier_id = normalize_text(row.get("supplier_id", ""))
        if supplier_id:
            out[supplier_id] = {column: normalize_text(row.get(column, "")) for column in SUPPLIER_REGISTRY_COLUMNS}
    return out


def _resolve_converter(converter_id: str):
    if not converter_id:
        return None
    try:
        module = importlib.import_module(f"scripts.flows.F.suppliers.{converter_id}")
    except ModuleNotFoundError:
        return None
    converter = getattr(module, "convert_supplier", None)
    if converter is None:
        return None
    return converter


def _converter_can_handle_suffix(converter_id: str, suffix: str) -> bool:
    if not converter_id:
        return False
    try:
        module = importlib.import_module(f"scripts.flows.F.suppliers.{converter_id}")
    except ModuleNotFoundError:
        return False
    supported_suffixes = getattr(module, "SUPPORTED_SUFFIXES", {".xlsx", ".xls"})
    return suffix.lower() in {normalize_text(value).lower() for value in supported_suffixes}


def _generic_rows_to_batch_rows(
    *,
    source: pd.DataFrame,
    supplier_id: str,
    batch_id: str,
    file_hash: str,
) -> tuple[pd.DataFrame, int, int, int]:
    rows = _build_rows(source=source, supplier_id=supplier_id, batch_id=batch_id, file_hash=file_hash)
    valid_row_count = int((rows["scan_eligibility"] == "scan_now").sum())
    held_row_count = int((rows["scan_eligibility"] == "hold").sum())
    return rows, int(len(source.index)), valid_row_count, held_row_count


def _historical_barcode_lookup(existing_rows: pd.DataFrame | None, supplier_id: str) -> dict[str, str]:
    if existing_rows is None or existing_rows.empty:
        return {}
    if not {"supplier_id", "supplier_sku", "barcode"}.issubset(existing_rows.columns):
        return {}

    supplier_key = normalize_text(supplier_id)
    candidates: dict[str, set[str]] = {}
    for _, row in existing_rows.iterrows():
        if normalize_text(row.get("supplier_id", "")) != supplier_key:
            continue
        sku = normalize_text(row.get("supplier_sku", "")).upper()
        barcode = _clean_barcode(row.get("barcode", ""))
        if not sku or not _is_valid_barcode(barcode):
            continue
        candidates.setdefault(sku, set()).add(barcode)

    return {sku: next(iter(barcodes)) for sku, barcodes in candidates.items() if len(barcodes) == 1}


def _converter_rows_to_batch_rows(
    *,
    valid_df: pd.DataFrame,
    holds_df: pd.DataFrame,
    supplier_id: str,
    batch_id: str,
    barcode_lookup_by_sku: dict[str, str] | None = None,
) -> tuple[pd.DataFrame, int, int, int]:
    rows: list[dict[str, str]] = []
    barcode_lookup = barcode_lookup_by_sku or {}
    for index, row in valid_df.reset_index(drop=True).iterrows():
        row_hash = normalize_text(row.get("row_hash", "")) or _sha1_text(
            "|".join(
                [
                    supplier_id,
                    normalize_text(row.get("supplier_sku", "")),
                    normalize_text(row.get("barcode", "")),
                    normalize_text(row.get("unit_cost", "")),
                    str(index),
                ]
            )
        )
        rows.append(
            {
                "batch_id": batch_id,
                "supplier_id": supplier_id,
                "row_key": row_hash,
                "supplier_sku": normalize_text(row.get("supplier_sku", "")),
                "supplier_title": normalize_text(row.get("supplier_title", "")),
                "barcode": normalize_text(row.get("barcode", "")),
                "unit_cost": normalize_text(row.get("unit_cost", "")),
                "currency": normalize_text(row.get("currency", "")) or "GBP",
                "vat_rate": normalize_text(row.get("vat_rate", "")) or "20",
                "unit_code": normalize_text(row.get("unit_code", "")),
                "pack_size": normalize_text(row.get("pack_size", "")) or "1",
                "pack_cost": normalize_text(row.get("pack_cost", "")),
                "moq": normalize_text(row.get("moq", "")) or normalize_text(row.get("pack_size", "")) or "1",
                "source_row_hash": row_hash,
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "supplier_converter_valid_row",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            }
        )
    for index, row in holds_df.reset_index(drop=True).iterrows():
        sku = normalize_text(row.get("supplier_sku", ""))
        title = normalize_text(row.get("supplier_title", ""))
        barcode = normalize_text(row.get("barcode", ""))
        unit_cost = normalize_text(row.get("unit_cost", ""))
        reasons = [
            normalize_text(reason)
            for reason in normalize_text(row.get("hold_reason_codes", "")).split("|")
            if normalize_text(reason)
        ]
        prior_barcode = barcode_lookup.get(sku.upper())
        if "missing_barcode" in reasons and prior_barcode:
            barcode = prior_barcode
            reasons = [reason for reason in reasons if reason != "missing_barcode"]

        if not reasons:
            row_hash = _sha1_text("|".join([supplier_id, sku, barcode, unit_cost, title]))
            rows.append(
                {
                    "batch_id": batch_id,
                    "supplier_id": supplier_id,
                    "row_key": row_hash,
                    "supplier_sku": sku,
                    "supplier_title": title,
                    "barcode": barcode,
                    "unit_cost": unit_cost,
                    "currency": "GBP",
                    "vat_rate": "20",
                    "unit_code": normalize_text(row.get("unit_code", "")),
                    "pack_size": normalize_text(row.get("pack_size", "")) or "1",
                    "pack_cost": normalize_text(row.get("pack_cost", "")),
                    "moq": normalize_text(row.get("moq", "")) or normalize_text(row.get("pack_size", "")) or "1",
                    "source_row_hash": row_hash,
                    "row_change_status": "new",
                    "scan_eligibility": "scan_now",
                    "eligibility_reason": "supplier_converter_valid_row_barcode_backfilled",
                    "last_memory_key": "",
                    "cooldown_until_utc": "",
                }
            )
            continue

        reason_text = "|".join(reasons)
        row_hash = _sha1_text(
            "|".join(
                [
                    supplier_id,
                    sku,
                    barcode,
                    unit_cost,
                    reason_text,
                    str(index),
                ]
            )
        )
        rows.append(
            {
                "batch_id": batch_id,
                "supplier_id": supplier_id,
                "row_key": row_hash,
                "supplier_sku": sku,
                "supplier_title": title,
                "barcode": barcode,
                "unit_cost": unit_cost,
                "currency": "GBP",
                "vat_rate": "20",
                "unit_code": normalize_text(row.get("unit_code", "")),
                "pack_size": normalize_text(row.get("pack_size", "")) or "1",
                "pack_cost": normalize_text(row.get("pack_cost", "")),
                "moq": normalize_text(row.get("moq", "")) or normalize_text(row.get("pack_size", "")) or "1",
                "source_row_hash": row_hash,
                "row_change_status": "new",
                "scan_eligibility": "hold",
                "eligibility_reason": reason_text or "supplier_converter_hold",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            }
        )
    row_df = pd.DataFrame(rows)
    valid_row_count = int((row_df["scan_eligibility"] == "scan_now").sum()) if not row_df.empty else 0
    held_row_count = int((row_df["scan_eligibility"] == "hold").sum()) if not row_df.empty else 0
    return row_df, int(len(valid_df.index) + len(holds_df.index)), valid_row_count, held_row_count


def _source_to_batch_rows(
    *,
    source_path: Path,
    supplier: dict[str, str],
    batch_id: str,
    file_hash: str,
    imported_at: str,
    existing_rows: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, int, int, int]:
    converter_id = normalize_text(supplier.get("converter_id", ""))
    converter = _resolve_converter(converter_id)
    if converter is not None and _converter_can_handle_suffix(converter_id, source_path.suffix):
        valid_df, holds_df = converter(
            source_path,
            supplier_id=normalize_text(supplier.get("supplier_id", "")),
            supplier_name=normalize_text(supplier.get("supplier_name", "")),
            source_url=normalize_text(supplier.get("source_url", "")),
            source_seen_at_utc=imported_at,
            currency="GBP",
            vat_rate="20",
            skip_sku_suffixes=[],
        )
        return _converter_rows_to_batch_rows(
            valid_df=valid_df,
            holds_df=holds_df,
            supplier_id=normalize_text(supplier.get("supplier_id", "")),
            batch_id=batch_id,
            barcode_lookup_by_sku=_historical_barcode_lookup(
                existing_rows,
                normalize_text(supplier.get("supplier_id", "")),
            ),
        )
    source_df = _load_source_file(source_path)
    return _generic_rows_to_batch_rows(
        source=source_df,
        supplier_id=normalize_text(supplier.get("supplier_id", "")),
        batch_id=batch_id,
        file_hash=file_hash,
    )


def _safe_zip_member_name(name: str) -> str:
    raw = normalize_text(name).replace("\\", "/")
    return Path(raw).name


def _extract_single_price_file_from_zip(source_path: Path, *, batch_id: str, work_dir: Path) -> Path:
    extract_dir = work_dir / "extracted_sources" / batch_id
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source_path) as archive:
        candidates = [
            info
            for info in archive.infolist()
            if not info.is_dir()
            and not _safe_zip_member_name(info.filename).startswith("__MACOSX")
            and Path(_safe_zip_member_name(info.filename)).suffix.lower() in ZIP_INNER_PRICE_FILE_SUFFIXES
        ]
        if not candidates:
            raise ValueError(f"zip source contains no supported price file: {source_path}")
        if len(candidates) > 1:
            names = ",".join(_safe_zip_member_name(info.filename) for info in candidates)
            raise ValueError(f"zip source contains multiple supported price files: {names}")

        member = candidates[0]
        target_name = _safe_zip_member_name(member.filename)
        if not target_name:
            raise ValueError(f"zip source contains unsafe price file name: {source_path}")
        target = extract_dir / target_name
        with archive.open(member, "r") as source_handle, target.open("wb") as target_handle:
            shutil.copyfileobj(source_handle, target_handle)
    return target


def _prepare_import_source(source_path: Path, *, batch_id: str, work_dir: Path) -> Path:
    if source_path.suffix.lower() != ".zip":
        return source_path
    return _extract_single_price_file_from_zip(source_path, batch_id=batch_id, work_dir=work_dir)


def _archive_path(source_path: Path, *, imported_at_utc: str, file_hash: str, duplicate: bool = False) -> Path:
    archive_dir = source_path.parent.parent / "Processed"
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = imported_at_utc.replace("-", "").replace(":", "")
    duplicate_text = "_duplicate" if duplicate else ""
    candidate = archive_dir / f"{source_path.stem}_{stamp}_{file_hash[:10]}{duplicate_text}{source_path.suffix}"
    index = 2
    while candidate.exists():
        candidate = archive_dir / f"{source_path.stem}_{stamp}_{file_hash[:10]}{duplicate_text}_{index}{source_path.suffix}"
        index += 1
    return candidate


def _build_batch_id(supplier_id: str, imported_at_utc: str, file_hash: str) -> str:
    stamp = imported_at_utc.replace("-", "").replace(":", "")
    return f"{supplier_id}_source_{stamp}_{file_hash[:12]}"


def _build_rows(
    *,
    source: pd.DataFrame,
    supplier_id: str,
    batch_id: str,
    file_hash: str,
) -> pd.DataFrame:
    sku_column = _find_column(list(source.columns), SKU_ALIASES)
    title_column = _find_column(list(source.columns), TITLE_ALIASES)
    barcode_column = _find_column(list(source.columns), BARCODE_ALIASES)
    cost_column = _find_column(list(source.columns), COST_ALIASES)
    currency_column = _find_column(list(source.columns), CURRENCY_ALIASES)

    rows: list[dict[str, str]] = []
    for index, raw_row in source.reset_index(drop=True).iterrows():
        sku = normalize_text(raw_row.get(sku_column, "")) if sku_column else f"row-{index + 1}"
        title = normalize_text(raw_row.get(title_column, "")) if title_column else ""
        barcode = _clean_barcode(raw_row.get(barcode_column, "")) if barcode_column else ""
        unit_cost = _clean_cost(raw_row.get(cost_column, "")) if cost_column else ""
        currency = normalize_text(raw_row.get(currency_column, "")) if currency_column else "GBP"
        source_row_hash = _sha1_text("|".join([supplier_id, file_hash, str(index), sku, barcode, unit_cost]))
        missing: list[str] = []
        if not barcode:
            missing.append("barcode")
        if not _valid_cost(unit_cost):
            missing.append("unit_cost")
        rows.append(
            {
                "batch_id": batch_id,
                "supplier_id": supplier_id,
                "row_key": source_row_hash,
                "supplier_sku": sku,
                "supplier_title": title,
                "barcode": barcode,
                "unit_cost": unit_cost,
                "currency": currency or "GBP",
                "vat_rate": "20",
                "unit_code": "",
                "pack_size": "1",
                "pack_cost": "",
                "moq": "1",
                "source_row_hash": source_row_hash,
                "row_change_status": "new",
                "scan_eligibility": "hold" if missing else "scan_now",
                "eligibility_reason": "missing_" + "_and_".join(missing) if missing else "imported_ready_source_row",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            }
        )
    return pd.DataFrame(rows)


def _eligible_ready_sources(acquisition: pd.DataFrame, supplier_id: str = "") -> pd.DataFrame:
    work = acquisition.copy()
    work = work[work["source_state"].map(lambda value: normalize_text(value).lower()) == "ready"].copy()
    work = work[work["latest_source_path"].map(normalize_text) != ""].copy()
    if supplier_id:
        key = normalize_text(supplier_id).lower()
        work = work[work["supplier_id"].map(lambda value: normalize_text(value).lower()) == key].copy()
    return work.sort_values(["supplier_id", "checked_at_utc"], kind="stable").reset_index(drop=True)


def _restore_missing_new_batch_headers(
    *,
    batches_path: Path,
    new_batches: list[dict[str, str]],
) -> bool:
    if not new_batches:
        return False
    batches = read_csv(batches_path, PRICE_LIST_BATCH_COLUMNS)
    existing_ids = {normalize_text(value) for value in batches["batch_id"].tolist()}
    missing = [row for row in new_batches if normalize_text(row.get("batch_id", "")) not in existing_ids]
    if not missing:
        return False
    write_csv(
        batches_path,
        pd.concat([batches, pd.DataFrame(missing)], ignore_index=True),
        PRICE_LIST_BATCH_COLUMNS,
    )
    return True


def _supersede_prior_batches(
    *,
    existing_batches: pd.DataFrame,
    new_batches: list[dict[str, str]],
    updated_at_utc: str,
) -> tuple[pd.DataFrame, int]:
    if existing_batches.empty or not new_batches:
        return existing_batches, 0
    new_batch_ids = {normalize_text(row.get("batch_id", "")) for row in new_batches}
    new_supplier_ids = {normalize_text(row.get("supplier_id", "")) for row in new_batches}
    if not new_supplier_ids:
        return existing_batches, 0

    updated = existing_batches.copy()
    supplier_mask = updated["supplier_id"].map(lambda value: normalize_text(value) in new_supplier_ids)
    old_batch_mask = ~updated["batch_id"].map(lambda value: normalize_text(value) in new_batch_ids)
    status_mask = updated["batch_status"].map(lambda value: normalize_text(value).lower() in SUPERSEDABLE_BATCH_STATUSES)
    mask = supplier_mask & old_batch_mask & status_mask
    superseded_count = int(mask.sum())
    if superseded_count:
        updated.loc[mask, "batch_status"] = "superseded"
        updated.loc[mask, "status_reason"] = "superseded_by_newer_source_batch"
        updated.loc[mask, "updated_at_utc"] = updated_at_utc
    return updated, superseded_count


def import_ready_sources(
    root: Path | None = None,
    *,
    supplier_id: str = "",
    imported_at_utc: str | None = None,
) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=root)
    imported_at = imported_at_utc or _utc_now_iso()
    acquisition_path = paths.test_mode_dir / "source_acquisition_status.csv"
    batches_path = paths.test_mode_dir / "price_list_batches.csv"
    batch_rows_path = paths.test_mode_dir / "batch_rows.csv"
    health_path = paths.test_mode_dir / "health.csv"

    acquisition = read_csv(acquisition_path, SOURCE_ACQUISITION_COLUMNS)
    if acquisition.empty:
        raise FileNotFoundError("source_acquisition_status.csv is required before importing ready sources")

    existing_batches = read_csv(batches_path, PRICE_LIST_BATCH_COLUMNS)
    existing_rows = read_csv(batch_rows_path, BATCH_ROW_COLUMNS)
    supplier_registry = _load_supplier_registry(paths)
    ready_sources = _eligible_ready_sources(acquisition, supplier_id=supplier_id)

    new_batches: list[dict[str, str]] = []
    new_rows: list[pd.DataFrame] = []
    duplicate_rows = 0
    failed_rows = 0
    stale_rows = 0
    for _, source_row in ready_sources.iterrows():
        source_path = Path(normalize_text(source_row.get("latest_source_path", "")))
        source_supplier_id = normalize_text(source_row.get("supplier_id", ""))
        if not source_path.exists() or not source_path.is_file():
            stale_rows += 1
            continue
        file_hash = _sha1_bytes(source_path)
        supplier = supplier_registry.get(source_supplier_id, {"supplier_id": source_supplier_id, "supplier_name": source_supplier_id})
        duplicate = existing_batches[
            (existing_batches["supplier_id"].map(normalize_text) == source_supplier_id)
            & (existing_batches["source_file_hash"].map(normalize_text) == file_hash)
        ]
        if not duplicate.empty:
            archive_target = _archive_path(source_path, imported_at_utc=imported_at, file_hash=file_hash, duplicate=True)
            shutil.move(str(source_path), str(archive_target))
            duplicate_rows += 1
            continue

        batch_id = _build_batch_id(source_supplier_id, imported_at, file_hash)
        conversion_source_path = _prepare_import_source(source_path, batch_id=batch_id, work_dir=paths.test_mode_dir)
        rows, source_row_count, valid_row_count, held_row_count = _source_to_batch_rows(
            source_path=conversion_source_path,
            supplier=supplier,
            batch_id=batch_id,
            file_hash=file_hash,
            imported_at=imported_at,
            existing_rows=existing_rows,
        )
        archive_target = _archive_path(source_path, imported_at_utc=imported_at, file_hash=file_hash)
        shutil.move(str(source_path), str(archive_target))
        converted_path = paths.test_mode_dir / f"{batch_id}_converted.csv"
        write_csv(converted_path, rows, BATCH_ROW_COLUMNS)
        new_batches.append(
            {
                "batch_id": batch_id,
                "supplier_id": source_supplier_id,
                "source_type": normalize_text(source_row.get("source_type", "")),
                "source_subtype": normalize_text(source_row.get("source_subtype", "")),
                "source_received_at_utc": normalize_text(source_row.get("latest_source_mtime_utc", "")) or imported_at,
                "source_file_path": str(archive_target),
                "source_file_hash": file_hash,
                "converted_file_path": str(converted_path),
                "source_row_count": str(source_row_count),
                "valid_row_count": str(valid_row_count),
                "held_row_count": str(held_row_count),
                "new_row_count": str(valid_row_count),
                "changed_row_count": "0",
                "eligible_row_count": str(valid_row_count),
                "skipped_cooldown_row_count": "0",
                "batch_status": "imported_from_source",
                "status_reason": "ready_source_file_imported",
                "updated_at_utc": imported_at,
            }
        )
        new_rows.append(rows)

    batches = existing_batches
    batch_rows = existing_rows
    superseded_prior_batches = 0
    if new_batches:
        existing_batches, superseded_prior_batches = _supersede_prior_batches(
            existing_batches=existing_batches,
            new_batches=new_batches,
            updated_at_utc=imported_at,
        )
        batches = write_csv(
            batches_path,
            pd.concat([existing_batches, pd.DataFrame(new_batches)], ignore_index=True),
            PRICE_LIST_BATCH_COLUMNS,
        )
        batch_rows = write_csv(
            batch_rows_path,
            pd.concat([existing_rows] + new_rows, ignore_index=True),
            BATCH_ROW_COLUMNS,
        )

    timeout_summary = refresh_timeout_queue_files(root=paths.root, observed_utc=imported_at)
    if _restore_missing_new_batch_headers(batches_path=batches_path, new_batches=new_batches):
        timeout_summary = refresh_timeout_queue_files(root=paths.root, observed_utc=imported_at)
    batches = read_csv(batches_path, PRICE_LIST_BATCH_COLUMNS)

    existing_health = read_csv(health_path, MANAGER_HEALTH_COLUMNS)
    health_row = pd.DataFrame(
        [
            {
                "check": "ready_source_import_reconciliation",
                "status": "ok" if failed_rows == 0 else "fail",
                "value": str(len(new_batches)),
                "notes": (
                    f"ready_sources={len(ready_sources.index)};duplicates={duplicate_rows};stale={stale_rows};"
                    f"failed={failed_rows};superseded_prior_batches={superseded_prior_batches};"
                    f"batch_rows={len(batch_rows.index)};"
                    f"timeout_scan_rows={timeout_summary['scan_rows']};timeout_skip_rows={timeout_summary['timeout_skip_rows']}"
                ),
                "observed_utc": imported_at,
                "source_path": str(acquisition_path),
            }
        ]
    )
    health = write_csv(health_path, pd.concat([existing_health, health_row], ignore_index=True), MANAGER_HEALTH_COLUMNS)

    summary = {
        "status": "success",
        "ready_sources": int(len(ready_sources.index)),
        "imported_batches": int(len(new_batches)),
        "duplicate_sources": int(duplicate_rows),
        "stale_sources": int(stale_rows),
        "failed_sources": int(failed_rows),
        "superseded_prior_batches": int(superseded_prior_batches),
        "batch_rows": int(len(batch_rows.index)),
        "total_batches": int(len(batches.index)),
        "timeout_scan_rows": int(timeout_summary["scan_rows"]),
        "timeout_skip_rows": int(timeout_summary["timeout_skip_rows"]),
        "health_fail_rows": int((health["status"].map(lambda value: normalize_text(value).lower()) == "fail").sum()),
        "batches_path": str(batches_path),
        "batch_rows_path": str(batch_rows_path),
    }
    print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Import ready price-list sources into test-mode batches.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--supplier-id", default="")
    parser.add_argument("--imported-at-utc", default=None)
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    import_ready_sources(root=root, supplier_id=args.supplier_id, imported_at_utc=args.imported_at_utc)


if __name__ == "__main__":
    main()
