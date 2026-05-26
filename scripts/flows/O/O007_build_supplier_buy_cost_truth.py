from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from scripts.flows.O._contract_io import write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract
from scripts.flows.O._schemas import get_o_output_contract
from scripts.flows.O._source_contracts import get_phase1_source_contracts


PRICE_MATCH_TOLERANCE_GBP = 0.005
PRICE_CHANGE_MIN_ABS_GBP = 0.05
PRICE_CHANGE_MIN_PCT = 0.02
PAID_HISTORY_LOOKBACK_MONTHS = 24
PAID_HISTORY_SAMPLE_LIMIT = 5
PAID_HISTORY_THIN_SAMPLE_COUNT = 3


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _slug(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", _normalize_text(value).lower())


def _num(value: object) -> float | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    cleaned = re.sub(r"[^0-9.+-]", "", raw.replace(",", "")).strip()
    if cleaned == "":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _money(value: float | None) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{float(value):.4f}".rstrip("0").rstrip(".")


def _ratio_text(value: float | None) -> str:
    if value is None:
        return ""
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


def _pct_text(value: float | None) -> str:
    if value is None:
        return ""
    return f"{float(value):.4f}".rstrip("0").rstrip(".")


def _delta_text(left: float | None, right: float | None) -> str:
    if left is None or right is None:
        return ""
    return _money(left - right)


def _positive(value: object) -> float | None:
    parsed = _num(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed


def _read_csv_safe(path: Path, columns: Iterable[str] = ()) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=list(columns))
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=list(columns))
    return df


def _parse_sort_utc(value: object) -> pd.Timestamp:
    parsed = pd.to_datetime(_normalize_text(value), errors="coerce", utc=True)
    if pd.isna(parsed):
        return pd.Timestamp("1970-01-01T00:00:00Z")
    return parsed


def _asof_timestamp(value: object) -> pd.Timestamp:
    parsed = pd.to_datetime(_normalize_text(value), errors="coerce", utc=True)
    if pd.isna(parsed):
        return pd.Timestamp(_utc_now_iso())
    return parsed


def _looks_like_standalone_number(value: object) -> bool:
    raw = _normalize_text(value)
    if raw == "":
        return False
    cleaned = re.sub(r"[^0-9.+-]", "", raw.replace(",", "")).strip()
    return bool(re.fullmatch(r"[+-]?\d+(?:\.\d+)?", cleaned))


def _f_row_shape_ok(row: pd.Series) -> bool:
    supplier_id = _normalize_text(row.get("supplier_id", ""))
    unit_cost = _positive(row.get("unit_cost", ""))
    if unit_cost is None:
        return False
    if supplier_id == "td_synnex" and _looks_like_standalone_number(row.get("supplier_title", "")):
        return False
    return True


def _build_registry_map(root_path: Path) -> dict[str, str]:
    registry_path = root_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "supplier_registry.csv"
    registry = _read_csv_safe(registry_path)
    if registry.empty or "supplier_id" not in registry.columns:
        return {}
    out: dict[str, str] = {}
    for _, row in registry.iterrows():
        supplier_id = _normalize_text(row.get("supplier_id", ""))
        if supplier_id:
            out[supplier_id] = _normalize_text(row.get("supplier_name", "")) or supplier_id
    return out


def _build_price_list_records(root_path: Path) -> list[dict[str, str]]:
    contracts = get_phase1_source_contracts()
    batch_rows_path = root_path / contracts["f_price_list_manager_batch_rows"].source_path
    batches_path = root_path / contracts["f_price_list_manager_batches"].source_path
    batch_rows = _read_csv_safe(batch_rows_path, contracts["f_price_list_manager_batch_rows"].required_columns)
    batches = _read_csv_safe(batches_path, contracts["f_price_list_manager_batches"].required_columns)
    registry_map = _build_registry_map(root_path)

    batch_meta: dict[str, dict[str, str]] = {}
    if not batches.empty and "batch_id" in batches.columns:
        for _, row in batches.iterrows():
            batch_id = _normalize_text(row.get("batch_id", ""))
            if batch_id:
                sort_utc = str(
                    _parse_sort_utc(
                        _normalize_text(row.get("source_received_at_utc", ""))
                        or _normalize_text(row.get("updated_at_utc", ""))
                    )
                )
                batch_meta[batch_id] = {
                    "supplier_id": _normalize_text(row.get("supplier_id", "")),
                    "source_received_at_utc": _normalize_text(row.get("source_received_at_utc", "")),
                    "source_file_path": _normalize_text(row.get("source_file_path", "")),
                    "converted_file_path": _normalize_text(row.get("converted_file_path", "")),
                    "batch_status": _normalize_text(row.get("batch_status", "")),
                    "updated_at_utc": _normalize_text(row.get("updated_at_utc", "")),
                    "_sort_utc": sort_utc,
                }

    kept_batch_ids: set[str] = set()
    batches_by_supplier: dict[str, list[tuple[pd.Timestamp, str]]] = {}
    for batch_id, meta in batch_meta.items():
        supplier_id = _normalize_text(meta.get("supplier_id", ""))
        if supplier_id == "":
            continue
        sort_ts = pd.Timestamp(meta.get("_sort_utc", "1970-01-01 00:00:00+00:00"))
        batches_by_supplier.setdefault(supplier_id, []).append((sort_ts, batch_id))
    for supplier_batches in batches_by_supplier.values():
        ordered = sorted(supplier_batches, key=lambda item: (item[0], item[1]))
        kept_batch_ids.update(batch_id for _, batch_id in ordered[-2:])
    if kept_batch_ids and "batch_id" in batch_rows.columns:
        batch_rows = batch_rows[batch_rows["batch_id"].map(_normalize_text).isin(kept_batch_ids)].copy()

    records: list[dict[str, str]] = []
    for row_index, row in batch_rows.iterrows():
        if not _f_row_shape_ok(row):
            continue
        batch_id = _normalize_text(row.get("batch_id", ""))
        if kept_batch_ids and batch_id not in kept_batch_ids:
            continue
        meta = batch_meta.get(batch_id, {})
        supplier_id = _normalize_text(row.get("supplier_id", ""))
        unit_cost = _positive(row.get("unit_cost", ""))
        if unit_cost is None:
            continue
        records.append(
            {
                "batch_id": batch_id,
                "supplier_id": supplier_id,
                "supplier_name": registry_map.get(supplier_id, supplier_id),
                "row_key": _normalize_text(row.get("row_key", "")),
                "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                "supplier_title": _normalize_text(row.get("supplier_title", "")),
                "barcode": _normalize_text(row.get("barcode", "")),
                "unit_cost": _money(unit_cost),
                "currency": _normalize_text(row.get("currency", "")) or "GBP",
                "vat_rate": _normalize_text(row.get("vat_rate", "")),
                "unit_code": _normalize_text(row.get("unit_code", "")),
                "pack_size": _normalize_text(row.get("pack_size", "")) or "1",
                "pack_cost": _normalize_text(row.get("pack_cost", "")),
                "moq": _normalize_text(row.get("moq", "")) or _normalize_text(row.get("pack_size", "")) or "1",
                "row_change_status": _normalize_text(row.get("row_change_status", "")),
                "source_received_at_utc": meta.get("source_received_at_utc", ""),
                "source_file_path": meta.get("source_file_path", ""),
                "converted_file_path": meta.get("converted_file_path", ""),
                "batch_status": meta.get("batch_status", ""),
                "updated_at_utc": meta.get("updated_at_utc", ""),
                "_sort_utc": meta.get("_sort_utc", "1970-01-01 00:00:00+00:00"),
                "_row_index": str(row_index),
            }
        )
    records.sort(key=lambda item: (item["_sort_utc"], int(item["_row_index"])))
    return records


def _add_record(mapping: dict[str, list[dict[str, str]]], key: object, record: dict[str, str]) -> None:
    clean = _normalize_key(key)
    if clean == "":
        return
    mapping.setdefault(clean, []).append(record)


def _build_price_maps(records: list[dict[str, str]]) -> tuple[dict[str, list[dict[str, str]]], dict[str, list[dict[str, str]]]]:
    by_sku: dict[str, list[dict[str, str]]] = {}
    by_barcode: dict[str, list[dict[str, str]]] = {}
    for record in records:
        _add_record(by_sku, record.get("supplier_sku", ""), record)
        _add_record(by_barcode, record.get("barcode", ""), record)
    return by_sku, by_barcode


def _supplier_matches(product_row: pd.Series, record: dict[str, str]) -> bool:
    product_tokens = {
        _slug(product_row.get("supplier_code", "")),
        _slug(product_row.get("supplier_name", "")),
    }
    product_tokens.discard("")
    record_tokens = {
        _slug(record.get("supplier_id", "")),
        _slug(record.get("supplier_name", "")),
    }
    record_tokens.discard("")
    return bool(product_tokens and record_tokens and product_tokens.intersection(record_tokens))


def _latest(records: list[dict[str, str]]) -> dict[str, str] | None:
    if not records:
        return None
    return records[-1]


def _supplier_latest_previous_records(records: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    batches_by_supplier: dict[str, dict[str, tuple[str, str]]] = {}
    for record in records:
        supplier_id = _normalize_text(record.get("supplier_id", ""))
        batch_id = _normalize_text(record.get("batch_id", ""))
        if supplier_id == "" or batch_id == "":
            continue
        sort_ts = _normalize_text(record.get("_sort_utc", "")) or _normalize_text(record.get("source_received_at_utc", "")) or _normalize_text(record.get("updated_at_utc", ""))
        supplier_batches = batches_by_supplier.setdefault(supplier_id, {})
        previous = supplier_batches.get(batch_id)
        if previous is None or sort_ts > previous[0]:
            supplier_batches[batch_id] = (sort_ts, batch_id)

    latest_batch_by_supplier: dict[str, str] = {}
    previous_batch_by_supplier: dict[str, str] = {}
    for supplier_id, batches in batches_by_supplier.items():
        ordered = sorted(batches.values(), key=lambda item: (item[0], item[1]))
        if ordered:
            latest_batch_by_supplier[supplier_id] = ordered[-1][1]
        if len(ordered) >= 2:
            previous_batch_by_supplier[supplier_id] = ordered[-2][1]

    latest_records: list[dict[str, str]] = []
    previous_records: list[dict[str, str]] = []
    for record in records:
        supplier_id = _normalize_text(record.get("supplier_id", ""))
        batch_id = _normalize_text(record.get("batch_id", ""))
        if batch_id and latest_batch_by_supplier.get(supplier_id) == batch_id:
            latest_records.append(record)
        elif batch_id and previous_batch_by_supplier.get(supplier_id) == batch_id:
            previous_records.append(record)
    return latest_records, previous_records


def _select_price_list_match(
    product_row: pd.Series,
    *,
    by_sku: dict[str, list[dict[str, str]]],
    by_barcode: dict[str, list[dict[str, str]]],
) -> tuple[dict[str, str] | None, str]:
    supplier_sku = _normalize_text(product_row.get("supplier_sku", ""))
    supplier_code_as_sku = _normalize_text(product_row.get("supplier_code", ""))
    barcode = _normalize_text(product_row.get("barcode", ""))

    candidate_groups: list[tuple[str, list[dict[str, str]]]] = []
    if supplier_sku:
        candidate_groups.append(("supplier_sku", by_sku.get(_normalize_key(supplier_sku), [])))
    if supplier_code_as_sku:
        candidate_groups.append(("supplier_code_as_supplier_sku", by_sku.get(_normalize_key(supplier_code_as_sku), [])))
    if barcode:
        candidate_groups.append(("barcode", by_barcode.get(_normalize_key(barcode), [])))

    for method, records in candidate_groups:
        matched = [record for record in records if _supplier_matches(product_row, record)]
        latest = _latest(matched)
        if latest is not None:
            return latest, f"{method}_supplier_matched"
    for method, records in candidate_groups:
        latest = _latest(records)
        if latest is not None:
            return latest, method
    return None, ""


def _record_primary_key(record: dict[str, str]) -> str:
    supplier_id = _normalize_key(record.get("supplier_id", ""))
    supplier_sku = _normalize_key(record.get("supplier_sku", ""))
    barcode = _normalize_key(record.get("barcode", ""))
    row_key = _normalize_key(record.get("row_key", ""))
    title = _slug(record.get("supplier_title", ""))
    if supplier_sku:
        item_key = f"sku:{supplier_sku}"
    elif barcode:
        item_key = f"barcode:{barcode}"
    elif row_key:
        item_key = f"row:{row_key}"
    else:
        item_key = f"title:{title}"
    return f"{supplier_id}|{item_key}"


def _record_barcode_key(record: dict[str, str]) -> str:
    supplier_id = _normalize_key(record.get("supplier_id", ""))
    barcode = _normalize_key(record.get("barcode", ""))
    if supplier_id == "" or barcode == "":
        return ""
    return f"{supplier_id}|barcode:{barcode}"


def _record_cost(record: dict[str, str] | None) -> float | None:
    if record is None:
        return None
    return _positive(record.get("unit_cost", ""))


def _change_threshold(previous_cost: float | None) -> float:
    if previous_cost is None:
        return PRICE_CHANGE_MIN_ABS_GBP
    return max(PRICE_CHANGE_MIN_ABS_GBP, abs(previous_cost) * PRICE_CHANGE_MIN_PCT)


def _same_identifier(current: dict[str, str], previous: dict[str, str]) -> bool:
    return (
        _normalize_key(current.get("supplier_sku", "")) == _normalize_key(previous.get("supplier_sku", ""))
        and _normalize_key(current.get("barcode", "")) == _normalize_key(previous.get("barcode", ""))
    )


def _price_change_status(current: dict[str, str] | None, previous: dict[str, str] | None) -> str:
    if current is None and previous is None:
        return ""
    if current is None:
        return "removed"
    if previous is None:
        return "new"
    if not _same_identifier(current, previous):
        return "identifier_changed"
    current_pack_size = _normalize_text(current.get("pack_size", "")) or "1"
    previous_pack_size = _normalize_text(previous.get("pack_size", "")) or "1"
    if current_pack_size != previous_pack_size:
        return "pack_changed"
    current_cost = _record_cost(current)
    previous_cost = _record_cost(previous)
    if current_cost is None or previous_cost is None:
        return "unchanged"
    delta = current_cost - previous_cost
    if abs(delta) <= _change_threshold(previous_cost):
        return "unchanged"
    return "cost_up" if delta > 0 else "cost_down"


def _change_delta(current: dict[str, str] | None, previous: dict[str, str] | None) -> tuple[str, str]:
    current_cost = _record_cost(current)
    previous_cost = _record_cost(previous)
    delta = None if current_cost is None or previous_cost is None else current_cost - previous_cost
    pct = None if delta is None or previous_cost is None or previous_cost <= 0 else (delta / previous_cost) * 100.0
    return _money(delta), _pct_text(pct)


def _change_log_row(
    *,
    asof_utc: str,
    current: dict[str, str] | None,
    previous: dict[str, str] | None,
    match_key: str,
) -> dict[str, str]:
    base = current or previous or {}
    delta, pct = _change_delta(current, previous)
    return {
        "asof_utc": asof_utc,
        "supplier_name": _normalize_text(base.get("supplier_name", "")),
        "supplier_id": _normalize_text(base.get("supplier_id", "")),
        "supplier_sku": _normalize_text((current or {}).get("supplier_sku", "")) or _normalize_text((previous or {}).get("supplier_sku", "")),
        "barcode": _normalize_text((current or {}).get("barcode", "")) or _normalize_text((previous or {}).get("barcode", "")),
        "title": _normalize_text((current or {}).get("supplier_title", "")) or _normalize_text((previous or {}).get("supplier_title", "")),
        "change_status": _price_change_status(current, previous),
        "current_unit_cost_gbp": _money(_record_cost(current)),
        "previous_unit_cost_gbp": _money(_record_cost(previous)),
        "current_pack_size": _normalize_text((current or {}).get("pack_size", "")),
        "previous_pack_size": _normalize_text((previous or {}).get("pack_size", "")),
        "current_pack_cost_gbp": _normalize_text((current or {}).get("pack_cost", "")),
        "previous_pack_cost_gbp": _normalize_text((previous or {}).get("pack_cost", "")),
        "current_source_batch_id": _normalize_text((current or {}).get("batch_id", "")),
        "previous_source_batch_id": _normalize_text((previous or {}).get("batch_id", "")),
        "current_seen_at_utc": _normalize_text((current or {}).get("source_received_at_utc", "")),
        "previous_seen_at_utc": _normalize_text((previous or {}).get("source_received_at_utc", "")),
        "change_delta_gbp": delta,
        "change_pct": pct,
        "match_key": match_key,
        "current_row_key": _normalize_text((current or {}).get("row_key", "")),
        "previous_row_key": _normalize_text((previous or {}).get("row_key", "")),
        "current_unit_code": _normalize_text((current or {}).get("unit_code", "")),
        "previous_unit_code": _normalize_text((previous or {}).get("unit_code", "")),
    }


def _build_change_maps_and_log(
    records: list[dict[str, str]],
    *,
    asof_utc: str,
) -> tuple[dict[str, dict[str, str]], list[dict[str, str]]]:
    latest_records, previous_records = _supplier_latest_previous_records(records)
    current_by_key = {_record_primary_key(record): record for record in latest_records if _record_primary_key(record)}
    previous_by_key = {_record_primary_key(record): record for record in previous_records if _record_primary_key(record)}
    previous_by_barcode = {
        _record_barcode_key(record): record
        for record in previous_records
        if _record_barcode_key(record) != ""
    }

    status_by_current_key: dict[str, dict[str, str]] = {}
    rows: list[dict[str, str]] = []
    consumed_previous_keys: set[str] = set()
    previous_override_by_current_key: dict[str, dict[str, str]] = {}
    for current_key, current in current_by_key.items():
        if current_key in previous_by_key:
            continue
        barcode_key = _record_barcode_key(current)
        previous_by_same_barcode = previous_by_barcode.get(barcode_key) if barcode_key else None
        if previous_by_same_barcode is None:
            continue
        previous_key = _record_primary_key(previous_by_same_barcode)
        if previous_key and previous_key not in consumed_previous_keys:
            previous_override_by_current_key[current_key] = previous_by_same_barcode
            consumed_previous_keys.add(previous_key)

    all_keys = sorted(set(current_by_key) | set(previous_by_key))
    for key in all_keys:
        current = current_by_key.get(key)
        if current is None and key in consumed_previous_keys:
            continue
        previous = previous_by_key.get(key)
        if current is not None and previous is None:
            previous = previous_override_by_current_key.get(key)
        row = _change_log_row(asof_utc=asof_utc, current=current, previous=previous, match_key=key)
        rows.append(row)
        if previous is not None:
            consumed_previous_keys.add(_record_primary_key(previous))
        if current is not None:
            status_by_current_key[key] = row

    for key, previous in previous_by_key.items():
        if key in consumed_previous_keys or key in current_by_key:
            continue
        rows.append(_change_log_row(asof_utc=asof_utc, current=None, previous=previous, match_key=key))

    return status_by_current_key, rows


def _build_paid_cost_profile_map(root_path: Path, product_df: pd.DataFrame, asof_utc: str) -> tuple[dict[str, dict[str, str]], pd.DataFrame]:
    asof_ts = _asof_timestamp(asof_utc)
    min_ts = asof_ts - pd.DateOffset(months=PAID_HISTORY_LOOKBACK_MONTHS)
    decision_log = _read_csv_safe(root_path / get_o_output_contract("restock_decisions_log").rel_path)
    po_lines = _read_csv_safe(root_path / get_o_output_contract("purchase_order_lines_live").rel_path)
    po_headers = _read_csv_safe(root_path / get_o_output_contract("purchase_orders_live").rel_path)

    header_created: dict[str, str] = {}
    if not po_headers.empty and "po_id" in po_headers.columns:
        for _, header in po_headers.iterrows():
            po_id = _normalize_text(header.get("po_id", ""))
            if po_id:
                header_created[po_id] = _normalize_text(header.get("created_utc", ""))

    decision_event_dates: dict[str, str] = {}
    if not decision_log.empty and "event_id" in decision_log.columns:
        for _, decision in decision_log.iterrows():
            event_id = _normalize_text(decision.get("event_id", ""))
            if event_id:
                decision_event_dates[event_id] = _normalize_text(decision.get("decision_utc", "")) or _normalize_text(
                    decision.get("event_utc", "")
                )

    samples_by_sku: dict[str, list[dict[str, str]]] = {}

    def add_sample(
        *,
        seller_sku: object,
        asin: object,
        cost: object,
        observed_utc: object,
        source_reference: object,
        supplier_name: object = "",
        supplier_sku: object = "",
        barcode: object = "",
    ) -> None:
        sku = _normalize_text(seller_sku)
        cost_num = _positive(cost)
        if sku == "" or cost_num is None:
            return
        observed = _parse_sort_utc(observed_utc)
        if observed < min_ts or observed > asof_ts + pd.Timedelta(days=1):
            return
        samples_by_sku.setdefault(sku.upper(), []).append(
            {
                "seller_sku": sku,
                "asin": _normalize_text(asin),
                "supplier_name": _normalize_text(supplier_name),
                "supplier_sku": _normalize_text(supplier_sku),
                "barcode": _normalize_text(barcode),
                "cost": _money(cost_num),
                "observed_utc": observed.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source_reference": _normalize_text(source_reference),
            }
        )

    if not decision_log.empty:
        for _, decision in decision_log.iterrows():
            action = _normalize_text(decision.get("decision_action", "")).lower()
            final_status = _normalize_text(decision.get("final_decision_status", "")).lower()
            if action not in {"approve_full_restock", "approve_test_restock"} or final_status not in {"full_restock", "test_restock"}:
                continue
            add_sample(
                seller_sku=decision.get("seller_sku", ""),
                asin=decision.get("asin", ""),
                cost=decision.get("confirmed_unit_cost", ""),
                observed_utc=_normalize_text(decision.get("decision_utc", "")) or decision.get("event_utc", ""),
                source_reference=f"restock_decisions_log:{_normalize_text(decision.get('event_id', ''))}",
            )

    if not po_lines.empty:
        for _, line in po_lines.iterrows():
            event_id = _normalize_text(line.get("source_event_id", ""))
            po_id = _normalize_text(line.get("po_id", ""))
            observed_utc = decision_event_dates.get(event_id, "") or header_created.get(po_id, "") or line.get("expected_arrival_utc", "")
            add_sample(
                seller_sku=line.get("seller_sku", ""),
                asin=line.get("asin", ""),
                cost=line.get("ordered_unit_cost_gbp", ""),
                observed_utc=observed_utc,
                source_reference=f"purchase_order_lines_live:{_normalize_text(line.get('po_line_id', ''))}",
                supplier_sku=line.get("supplier_sku", ""),
                barcode=line.get("barcode", ""),
            )

    product_meta: dict[str, pd.Series] = {}
    for _, product in product_df.iterrows():
        sku = _normalize_text(product.get("seller_sku", "")).upper()
        if sku:
            product_meta[sku] = product

    profile_by_sku: dict[str, dict[str, str]] = {}
    rows: list[dict[str, str]] = []
    for sku_key, samples in samples_by_sku.items():
        samples = sorted(samples, key=lambda item: _parse_sort_utc(item.get("observed_utc", "")), reverse=True)
        recent_samples = samples[:PAID_HISTORY_SAMPLE_LIMIT]
        costs = [_positive(sample.get("cost", "")) for sample in recent_samples]
        costs = [cost for cost in costs if cost is not None]
        if not costs:
            continue
        sample_count = len(costs)
        usual_cost = float(pd.Series(costs).median()) if sample_count >= PAID_HISTORY_THIN_SAMPLE_COUNT else costs[0]
        latest_sample = recent_samples[0]
        product = product_meta.get(sku_key)
        row = {
            "asof_utc": asof_utc,
            "seller_sku": _normalize_text(latest_sample.get("seller_sku", "")),
            "asin": _normalize_text(latest_sample.get("asin", "")) or (_normalize_text(product.get("asin", "")) if product is not None else ""),
            "supplier_name": _normalize_text(latest_sample.get("supplier_name", "")) or (_normalize_text(product.get("supplier_name", "")) if product is not None else ""),
            "supplier_sku": _normalize_text(latest_sample.get("supplier_sku", "")) or (_normalize_text(product.get("supplier_sku", "")) if product is not None else ""),
            "barcode": _normalize_text(latest_sample.get("barcode", "")) or (_normalize_text(product.get("barcode", "")) if product is not None else ""),
            "usual_paid_unit_cost_gbp": _money(usual_cost),
            "usual_paid_cost_basis": "median_last_5_confirmed_costs_24m" if sample_count >= PAID_HISTORY_THIN_SAMPLE_COUNT else "latest_confirmed_cost_thin_history",
            "usual_paid_cost_confidence": "confirmed_history" if sample_count >= PAID_HISTORY_THIN_SAMPLE_COUNT else "low_confirmed_history",
            "usual_paid_sample_count": str(sample_count),
            "usual_paid_lookback_months": str(PAID_HISTORY_LOOKBACK_MONTHS),
            "usual_paid_last_paid_utc": _normalize_text(latest_sample.get("observed_utc", "")),
            "usual_paid_min_cost_gbp": _money(min(costs)),
            "usual_paid_max_cost_gbp": _money(max(costs)),
            "latest_paid_unit_cost_gbp": _money(costs[0]),
            "usual_paid_source_reference": "|".join(
                _normalize_text(sample.get("source_reference", "")) for sample in recent_samples if _normalize_text(sample.get("source_reference", ""))
            ),
        }
        rows.append(row)
        profile_by_sku[sku_key] = row

    profile_df = pd.DataFrame(rows)
    if profile_df.empty:
        profile_df = pd.DataFrame(columns=get_o_output_contract("supplier_paid_cost_profiles_live").required_columns)
    profile_df = write_o_contract_df(root_path, "supplier_paid_cost_profiles_live", profile_df)
    profile_by_sku = {row["seller_sku"].upper(): row for row in profile_df.to_dict("records") if _normalize_text(row.get("seller_sku", ""))}
    return profile_by_sku, profile_df


def _build_cost_decision(
    *,
    price_list_cost: float | None,
    product_catalog_cost: float | None,
    actual_paid_cost: float | None,
) -> dict[str, str]:
    purchase_reference = product_catalog_cost or price_list_cost
    current_basis = price_list_cost or product_catalog_cost or actual_paid_cost
    changed_since_purchase = (
        product_catalog_cost is not None
        and price_list_cost is not None
        and abs(product_catalog_cost - price_list_cost) > PRICE_MATCH_TOLERANCE_GBP
    )

    ratio: float | None = None
    discount_pct: float | None = None
    expected = current_basis
    expected_source = "missing_cost"
    confidence = "none"
    user_check = "0"
    review_reasons: list[str] = []

    if current_basis is None:
        return {
            "purchase_reference_list_cost_gbp": _money(purchase_reference),
            "actual_vs_list_ratio": "",
            "discount_assumption_pct": "",
            "expected_next_unit_cost_gbp": "",
            "expected_cost_source": "missing_cost",
            "cost_confidence": "none",
            "user_price_check_required": "1",
            "review_reason": "missing_all_cost_inputs",
            "price_list_changed_since_purchase": "0",
            "price_list_vs_actual_paid_delta_gbp": _delta_text(price_list_cost, actual_paid_cost),
            "price_list_vs_purchase_reference_delta_gbp": _delta_text(price_list_cost, purchase_reference),
        }

    if price_list_cost is not None:
        expected_source = "supplier_price_list"
        confidence = "price_list_only"
        if actual_paid_cost is None:
            review_reasons.append("price_list_only_no_purchase_reference")
    elif product_catalog_cost is not None:
        expected_source = "product_catalog_price"
        confidence = "product_catalog_only"
        review_reasons.append("missing_current_price_list_cost")
        user_check = "1"
    else:
        expected_source = "last_purchase_price"
        confidence = "last_purchase_only"
        review_reasons.append("missing_current_price_list_cost")
        user_check = "1"

    if actual_paid_cost is not None and purchase_reference is not None and purchase_reference > 0:
        ratio = actual_paid_cost / purchase_reference
        if abs(actual_paid_cost - purchase_reference) <= PRICE_MATCH_TOLERANCE_GBP:
            ratio = 1.0
            expected = current_basis
            expected_source = "supplier_price_list_no_discount" if price_list_cost is not None else expected_source
            confidence = "price_list_actual_match"
            review_reasons = [reason for reason in review_reasons if reason != "price_list_only_no_purchase_reference"]
        elif actual_paid_cost < purchase_reference:
            expected = current_basis * ratio
            discount_pct = max(0.0, (1.0 - ratio) * 100.0)
            expected_source = "discount_assumption_from_actual_paid"
            confidence = "discount_assumption_needs_confirmation"
            user_check = "1"
            review_reasons.append("discount_assumption_needs_confirmation")
            if changed_since_purchase:
                review_reasons.append("price_list_changed_after_discounted_purchase")
        else:
            expected = max(current_basis, actual_paid_cost)
            expected_source = "actual_paid_above_list_review"
            confidence = "actual_paid_above_list_needs_review"
            user_check = "1"
            review_reasons.append("actual_paid_above_list_needs_review")
    elif actual_paid_cost is not None and purchase_reference is None:
        expected = max(current_basis, actual_paid_cost)
        confidence = "actual_paid_without_list_reference"
        user_check = "1"
        review_reasons.append("actual_paid_without_list_reference")

    return {
        "purchase_reference_list_cost_gbp": _money(purchase_reference),
        "actual_vs_list_ratio": _ratio_text(ratio),
        "discount_assumption_pct": _money(discount_pct),
        "expected_next_unit_cost_gbp": _money(expected),
        "expected_cost_source": expected_source,
        "cost_confidence": confidence,
        "user_price_check_required": user_check,
        "review_reason": "|".join(dict.fromkeys(review_reasons)),
        "price_list_changed_since_purchase": "1" if changed_since_purchase else "0",
        "price_list_vs_actual_paid_delta_gbp": _delta_text(price_list_cost, actual_paid_cost),
        "price_list_vs_purchase_reference_delta_gbp": _delta_text(price_list_cost, purchase_reference),
    }


def _discount_fields(usual_paid_cost: float | None, price_list_cost: float | None) -> tuple[str, str]:
    if usual_paid_cost is None or price_list_cost is None or price_list_cost <= 0:
        return "", ""
    delta = usual_paid_cost - price_list_cost
    pct = ((price_list_cost - usual_paid_cost) / price_list_cost) * 100.0
    return _pct_text(pct), _money(delta)


def build_supplier_buy_cost_truth(
    root: Path | None = None,
    *,
    asof_utc: str | None = None,
) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    timestamp_utc = asof_utc or _utc_now_iso()
    contracts = get_phase1_source_contracts()

    product_path = root_path / contracts["product_db_preview"].source_path
    product_df = _read_csv_safe(product_path, contracts["product_db_preview"].required_columns)
    product_df = product_df.copy()
    if "seller_sku" in product_df.columns:
        product_df = product_df[product_df["seller_sku"].map(_normalize_text).ne("")]

    price_records = _build_price_list_records(root_path)
    current_price_records, previous_price_records = _supplier_latest_previous_records(price_records)
    by_sku, by_barcode = _build_price_maps(current_price_records)
    previous_by_sku, previous_by_barcode = _build_price_maps(previous_price_records)
    change_by_key, change_rows = _build_change_maps_and_log(price_records, asof_utc=timestamp_utc)
    change_df = pd.DataFrame(change_rows)
    if change_df.empty:
        change_df = pd.DataFrame(columns=get_o_output_contract("supplier_price_list_change_log_live").required_columns)
    write_o_contract_df(root_path, "supplier_price_list_change_log_live", change_df)
    paid_profile_by_sku, _ = _build_paid_cost_profile_map(root_path, product_df, timestamp_utc)

    rows: list[dict[str, str]] = []
    for _, product_row in product_df.iterrows():
        price_match, match_method = _select_price_list_match(product_row, by_sku=by_sku, by_barcode=by_barcode)
        previous_price_match, _previous_match_method = _select_price_list_match(
            product_row,
            by_sku=previous_by_sku,
            by_barcode=previous_by_barcode,
        )
        change_info: dict[str, str] = {}
        if price_match is not None:
            change_info = change_by_key.get(_record_primary_key(price_match), {})
        elif previous_price_match is not None:
            change_info = _change_log_row(
                asof_utc=timestamp_utc,
                current=None,
                previous=previous_price_match,
                match_key=_record_primary_key(previous_price_match),
            )
        price_list_cost = _positive(price_match.get("unit_cost", "")) if price_match is not None else None
        product_catalog_cost = _positive(product_row.get("supplier_catalog_price", ""))
        product_last_purchase_cost = _positive(product_row.get("last_purchase_price", ""))
        paid_profile = paid_profile_by_sku.get(_normalize_key(product_row.get("seller_sku", "")), {})
        usual_paid_cost = _positive(paid_profile.get("usual_paid_unit_cost_gbp", ""))
        actual_paid_cost = usual_paid_cost if usual_paid_cost is not None else product_last_purchase_cost
        actual_paid_source = (
            "local_paid_cost_profile"
            if usual_paid_cost is not None
            else ("product_db_last_purchase_price" if product_last_purchase_cost is not None else "")
        )
        usual_discount, usual_delta = _discount_fields(usual_paid_cost, price_list_cost)
        decision = _build_cost_decision(
            price_list_cost=price_list_cost,
            product_catalog_cost=product_catalog_cost,
            actual_paid_cost=actual_paid_cost,
        )
        source_lineage_parts = ["product_db_preview"]
        if price_match is not None:
            source_lineage_parts.append(f"f_price_list_batch:{price_match.get('batch_id', '')}")
        row = {
            "asof_utc": timestamp_utc,
            "seller_sku": _normalize_text(product_row.get("seller_sku", "")),
            "asin": _normalize_text(product_row.get("asin", "")),
            "title": _normalize_text(product_row.get("title", "")),
            "supplier_code": _normalize_text(product_row.get("supplier_code", "")),
            "supplier_name": _normalize_text(product_row.get("supplier_name", "")),
            "supplier_sku": _normalize_text(product_row.get("supplier_sku", "")) or _normalize_text((price_match or {}).get("supplier_sku", "")),
            "barcode": _normalize_text(product_row.get("barcode", "")) or _normalize_text((price_match or {}).get("barcode", "")),
            "price_list_unit_cost_gbp": _money(price_list_cost),
            "price_list_currency": _normalize_text((price_match or {}).get("currency", "")) or ("GBP" if price_list_cost is not None else ""),
            "price_list_unit_code": _normalize_text((price_match or {}).get("unit_code", "")),
            "price_list_pack_size": _normalize_text((price_match or {}).get("pack_size", "")) or ("1" if price_list_cost is not None else ""),
            "price_list_pack_cost_gbp": _normalize_text((price_match or {}).get("pack_cost", "")),
            "price_list_moq": _normalize_text((price_match or {}).get("moq", "")) or _normalize_text((price_match or {}).get("pack_size", "")),
            "price_list_source_batch_id": _normalize_text((price_match or {}).get("batch_id", "")),
            "price_list_source_received_at_utc": _normalize_text((price_match or {}).get("source_received_at_utc", "")),
            "price_list_source_row_key": _normalize_text((price_match or {}).get("row_key", "")),
            "actual_paid_unit_cost_gbp": _money(actual_paid_cost),
            "actual_paid_source": actual_paid_source,
            "source_lineage": "|".join(part for part in source_lineage_parts if part),
            "price_list_supplier_id": _normalize_text((price_match or {}).get("supplier_id", "")),
            "price_list_supplier_sku": _normalize_text((price_match or {}).get("supplier_sku", "")),
            "price_list_barcode": _normalize_text((price_match or {}).get("barcode", "")),
            "product_catalog_cost_gbp": _money(product_catalog_cost),
            "cost_match_method": match_method,
            "usual_paid_unit_cost_gbp": _normalize_text(paid_profile.get("usual_paid_unit_cost_gbp", "")),
            "usual_paid_cost_basis": _normalize_text(paid_profile.get("usual_paid_cost_basis", "")),
            "usual_paid_cost_confidence": _normalize_text(paid_profile.get("usual_paid_cost_confidence", "")),
            "usual_paid_sample_count": _normalize_text(paid_profile.get("usual_paid_sample_count", "")),
            "usual_paid_lookback_months": _normalize_text(paid_profile.get("usual_paid_lookback_months", "")),
            "usual_paid_last_paid_utc": _normalize_text(paid_profile.get("usual_paid_last_paid_utc", "")),
            "usual_paid_source_reference": _normalize_text(paid_profile.get("usual_paid_source_reference", "")),
            "usual_paid_discount_vs_list_pct": usual_discount,
            "usual_paid_vs_list_delta_gbp": usual_delta,
            "price_list_change_status": _normalize_text(change_info.get("change_status", "")) or ("removed" if previous_price_match is not None and price_match is None else ""),
            "price_list_previous_unit_cost_gbp": _normalize_text(change_info.get("previous_unit_cost_gbp", "")),
            "price_list_previous_pack_size": _normalize_text(change_info.get("previous_pack_size", "")),
            "price_list_previous_pack_cost_gbp": _normalize_text(change_info.get("previous_pack_cost_gbp", "")),
            "price_list_previous_seen_at_utc": _normalize_text(change_info.get("previous_seen_at_utc", "")),
            "price_list_change_delta_gbp": _normalize_text(change_info.get("change_delta_gbp", "")),
            "price_list_change_pct": _normalize_text(change_info.get("change_pct", "")),
        }
        row.update(decision)
        rows.append(row)

    out_df = pd.DataFrame(rows)
    out_path = root_path / get_o_output_contract("supplier_buy_cost_truth").rel_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df = write_o_contract_df(root_path, "supplier_buy_cost_truth", out_df)
    print({"status": "success", "rows": len(out_df), "snapshot": str(out_path)})
    return out_df


def main() -> None:
    parser = argparse.ArgumentParser(description="Build O supplier buy-cost truth from collected price lists and actual purchase costs.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--asof-utc", default=None)
    args = parser.parse_args()
    build_supplier_buy_cost_truth(
        root=Path(args.root) if args.root else None,
        asof_utc=args.asof_utc,
    )


if __name__ == "__main__":
    main()
