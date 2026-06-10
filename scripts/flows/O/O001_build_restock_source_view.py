from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Iterable

import pandas as pd

from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract
from scripts.flows.O._schemas import get_o_output_contract
from scripts.flows.O._source_contracts import SourceContract, get_phase1_source_contracts


NUMERIC_DEFAULT_ZERO_COLUMNS: tuple[str, ...] = (
    "available_now",
    "total_quantity_now",
    "amazon_inbound_working",
    "amazon_inbound_shipped",
    "amazon_inbound_receiving",
    "velocity_7d",
    "velocity_30d",
    "velocity_90d",
    "expected_refund_cost_per_unit_gbp",
    "refund_unit_rate_30d",
    "refund_unit_rate_90d",
    "refund_units_30d",
    "sales_units_30d",
    "roi_at_market_price_pct",
    "supplier_pack_size",
    "moq",
    "lead_time_days",
    "out_of_stock_days",
)

DEMAND_INPUT_MIN_UNITS_PER_DAY = 0.05
TEST_COST_MODE_ENV = "O_RESTOCK_COST_MODE"
NET_FEE_MODEL_MAX_AGE_HOURS = 48.0
WEAK_REFUND_PROOF_STATES = {
    "",
    "missing",
    "unknown",
    "weak",
    "not_yet_proven",
    "sellerboard_bridge_only",
    "bridge_labelled_only",
}
WEAK_REFUND_CONFIDENCE_STATES = {
    "",
    "missing",
    "unknown",
    "weak",
    "not_yet_proven",
}
WEAK_INBOUND_COST_CONFIDENCE_STATES = {
    "",
    "missing",
    "unknown",
    "weak",
    "not_yet_proven",
    "missing_inbound_cost_confidence",
    "unsupported_currency",
}
BACKTEST_FIELD_MAP: tuple[tuple[str, str], ...] = (
    ("policy_id", "backtest_policy_id"),
    ("history_confidence", "backtest_history_confidence"),
    ("market_viability_score", "backtest_market_viability_score"),
    ("exit_risk_score", "backtest_exit_risk_score"),
    ("estimated_total_profit_gbp", "backtest_estimated_total_profit_gbp"),
    ("estimated_monthly_profit_gbp", "backtest_estimated_monthly_profit_gbp"),
    ("capital_lockup_days", "backtest_capital_lockup_days"),
    ("sellable_ceiling_zone", "backtest_sellable_ceiling_zone"),
    ("amazon_risk_level", "backtest_amazon_risk_level"),
    ("compression_risk_level", "backtest_compression_risk_level"),
    ("recommendation", "backtest_recommendation"),
    ("manual_review_reason", "backtest_manual_review_reason"),
)


@dataclass(frozen=True)
class SourceReadResult:
    name: str
    contract: SourceContract
    path: Path
    df: pd.DataFrame
    file_missing: bool
    missing_columns: tuple[str, ...]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_key(value: object) -> str:
    return str(value or "").strip().upper()


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _num_or_none(value: object) -> float | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return None


def _num_to_text(value: float | None, *, allow_blank: bool = True) -> str:
    if value is None:
        return "" if allow_blank else "0"
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _truthy(value: object) -> bool:
    token = str(value or "").strip().lower()
    return token in {"1", "true", "yes", "y", "on"}


def _normalize_mode(value: object) -> str:
    token = str(value or "").strip().lower()
    if token == "test":
        return "test"
    return "live"


def _normalize_sale_status(value: object) -> str:
    token = str(value or "").strip().lower()
    if token == "":
        return "unknown"
    if token in {"active", "live", "enabled"}:
        return "active"
    if token in {"dropped", "inactive", "discontinued", "archived"}:
        return "inactive"
    if "drop" in token or "discontinu" in token or "inactive" in token:
        return "inactive"
    if "active" in token:
        return "active"
    return "unknown"


def _positive_int_text(value: object, *, default: str = "") -> str:
    number = _num_or_none(value)
    if number is None or number <= 0 or not number.is_integer():
        return default
    return str(int(number))


def _normalize_order_qty_mode(value: object) -> str:
    token = _normalize_text(value).lower()
    if token in {"raw_units", "sell_packs", "bundles"}:
        return token
    return ""


def _flag_text(value: object) -> str:
    return "1" if _truthy(value) else "0"


def _build_display_qtys_label(
    *,
    order_qty_mode: str,
    sell_pack_qty: str,
    amazon_pack_size: str,
    supplier_case_qty: str,
    supplier_case_multiple: str,
    valid_order_step: str,
) -> str:
    parts: list[str] = []

    if order_qty_mode == "bundles":
        bundle_qty = amazon_pack_size or sell_pack_qty or "1"
        parts.append(f"Bundle {bundle_qty}")
    elif order_qty_mode == "sell_packs":
        parts.append(f"Pack {sell_pack_qty or '1'}")
    elif supplier_case_multiple == "1" and supplier_case_qty not in {"", "1"}:
        parts.append(f"Case {supplier_case_qty}")
    else:
        parts.append("Unit")

    if order_qty_mode in {"sell_packs", "bundles"} and supplier_case_qty not in {"", "1"}:
        parts.append(f"Case {supplier_case_qty}")

    if valid_order_step not in {"", "1"}:
        skip_step = (
            order_qty_mode == "raw_units"
            and supplier_case_multiple == "1"
            and supplier_case_qty not in {"", "1"}
            and valid_order_step == supplier_case_qty
        )
        if not skip_step:
            parts.append(f"Step {valid_order_step}")

    return " | ".join(parts)


def _build_quantity_profile_fields(*, product_row: pd.Series | None, base_row: dict[str, str]) -> dict[str, str]:
    supplier_sku = _value_from_any(
        product_row,
        ("supplier_sku", "supply_code"),
        default=base_row.get("supplier_code", ""),
    )
    barcode = _value_from_any(product_row, ("barcode", "ean", "upc", "ean13"))
    repack_required = _flag_text(_value_from_any(product_row, ("repack_required",)))
    bundle_required = _flag_text(_value_from_any(product_row, ("bundle_required",)))

    order_qty_mode = _normalize_order_qty_mode(
        _value_from_any(product_row, ("order_qty_mode",), default=base_row.get("order_qty_mode", ""))
    )
    if order_qty_mode == "":
        if bundle_required == "1":
            order_qty_mode = "bundles"
        elif repack_required == "1":
            order_qty_mode = "sell_packs"
        else:
            order_qty_mode = "raw_units"

    base_order_qty_mode = _normalize_order_qty_mode(base_row.get("order_qty_mode", ""))
    base_sell_pack_qty = _positive_int_text(base_row.get("sell_pack_qty", ""))
    explicit_sell_pack_qty = _positive_int_text(_value_from_any(product_row, ("sell_pack_qty",)))
    if explicit_sell_pack_qty:
        sell_pack_qty = explicit_sell_pack_qty
    elif base_order_qty_mode == "sell_packs" and base_sell_pack_qty:
        sell_pack_qty = base_sell_pack_qty
    else:
        sell_pack_qty = _positive_int_text(
            _value_from_any(
                product_row,
                ("sell_pack_qty", "amazon_pack_size"),
                default=base_row.get("sell_pack_qty", "1"),
            ),
            default="1",
        )
    amazon_pack_size = _positive_int_text(
        _value_from_any(product_row, ("amazon_pack_size",), default=base_row.get("amazon_pack_size", sell_pack_qty)),
        default=sell_pack_qty,
    )
    supplier_case_qty = _positive_int_text(
        _value_from_any(product_row, ("supplier_case_qty",), default=base_row.get("supplier_pack_size", "1")),
        default="1",
    )

    supplier_case_multiple_raw = _value_from_any(product_row, ("supplier_case_multiple",))
    if _normalize_text(supplier_case_multiple_raw) == "":
        supplier_case_multiple = "1" if (order_qty_mode == "raw_units" and supplier_case_qty not in {"", "1"}) else "0"
    else:
        supplier_case_multiple = _flag_text(supplier_case_multiple_raw)

    valid_order_step = _positive_int_text(_value_from_any(product_row, ("valid_order_step",)))
    if valid_order_step == "":
        if order_qty_mode == "raw_units":
            if supplier_case_multiple == "1" and supplier_case_qty not in {"", "1"}:
                valid_order_step = supplier_case_qty
            else:
                valid_order_step = _positive_int_text(base_row.get("moq", ""), default="1")

    order_qty_unit_label = _normalize_text(_value_from_any(product_row, ("order_qty_unit_label",)))
    if order_qty_unit_label == "":
        order_qty_unit_label = {
            "raw_units": "Units",
            "sell_packs": "Packs",
            "bundles": "Bundles",
        }.get(order_qty_mode, "Units")

    display_qtys_label = _normalize_text(_value_from_any(product_row, ("display_qtys_label",)))
    if display_qtys_label == "":
        display_qtys_label = _build_display_qtys_label(
            order_qty_mode=order_qty_mode,
            sell_pack_qty=sell_pack_qty,
            amazon_pack_size=amazon_pack_size,
            supplier_case_qty=supplier_case_qty,
            supplier_case_multiple=supplier_case_multiple,
            valid_order_step=valid_order_step,
        )

    return {
        "supplier_sku": supplier_sku,
        "barcode": barcode,
        "amazon_pack_size": amazon_pack_size,
        "pack_conversion_note": _value_from_any(
            product_row,
            ("pack_conversion_note",),
            default=base_row.get("pack_conversion_note", ""),
        ),
        "order_qty_mode": order_qty_mode,
        "order_qty_unit_label": order_qty_unit_label,
        "sell_pack_qty": sell_pack_qty,
        "supplier_case_qty": supplier_case_qty,
        "supplier_case_multiple": supplier_case_multiple,
        "valid_order_step": valid_order_step,
        "repack_required": repack_required,
        "bundle_required": bundle_required,
        "display_qtys_label": display_qtys_label,
    }


def _read_source(root: Path, name: str, contract: SourceContract) -> SourceReadResult:
    source_path = root / contract.source_path
    if not source_path.exists():
        return SourceReadResult(
            name=name,
            contract=contract,
            path=source_path,
            df=pd.DataFrame(),
            file_missing=True,
            missing_columns=tuple(contract.required_columns),
        )
    df = pd.read_csv(source_path, dtype=str).fillna("")
    missing = tuple(col for col in contract.required_columns if col not in df.columns)
    return SourceReadResult(
        name=name,
        contract=contract,
        path=source_path,
        df=df,
        file_missing=False,
        missing_columns=missing,
    )


def _build_market_context(
    offer_row: pd.Series | None,
    perf_row: pd.Series | None,
    product_row: pd.Series,
    notes: list[str],
) -> tuple[str, str]:
    offer_candidates: tuple[tuple[str, str], ...] = (
        ("buy_box_price", "BUY_BOX_PRICE"),
        ("lowest_fba_price", "LOWEST_FBA_PRICE"),
        ("our_price", "OUR_PRICE"),
    )
    if offer_row is not None:
        for source_col, basis in offer_candidates:
            value = _num_or_none(offer_row.get(source_col, ""))
            if value is not None and value > 0:
                return _num_to_text(value), basis

    perf_fallback_candidates: tuple[tuple[str, str], ...] = (
        ("market_price_gbp", "PERFORMANCE_MARKET_PRICE"),
        ("buy_box_price_gbp", "PERFORMANCE_BUY_BOX_PRICE"),
        ("our_price_gbp", "PERFORMANCE_OUR_PRICE"),
    )
    if perf_row is not None:
        for source_col, basis in perf_fallback_candidates:
            value = _num_or_none(perf_row.get(source_col, ""))
            if value is not None and value > 0:
                notes.append("REDUCED_CONFIDENCE_MISSING_H_PRICE_CONTEXT")
                return _num_to_text(value), basis

    product_live_listing_price = _num_or_none(product_row.get("live_listing_price", ""))
    if product_live_listing_price is not None and product_live_listing_price > 0:
        notes.append("REDUCED_CONFIDENCE_PRODUCT_DB_MARKET_CONTEXT")
        return _num_to_text(product_live_listing_price), "PRODUCT_DB_LIVE_LISTING_PRICE"

    notes.append("REDUCED_CONFIDENCE_MISSING_H_PRICE_CONTEXT")
    return "", "MISSING_MARKET_CONTEXT"


def _parse_utc_or_date(value: object) -> datetime | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    parsed = pd.to_datetime(raw, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def _build_net_fee_context(
    *,
    performance_row: pd.Series | None,
    product_row: pd.Series,
    market_price_gbp: str,
    asof_utc: str,
    notes: list[str],
) -> dict[str, str]:
    model_notes: list[str] = []
    status = "fresh"

    market_price = _num_or_none(market_price_gbp)
    vat_rate = _num_or_none(
        _value_from_any(
            product_row,
            ("vat_rate", "vat_rate_pct", "market_price_vat_rate_pct"),
        )
    )
    current_token_cost = _num_or_none(_value_from_any(performance_row, ("current_token_cost_gbp",)))
    break_even_price = _num_or_none(_value_from_any(performance_row, ("break_even_price_gbp",)))
    refund_drag = _num_or_none(_value_from_any(performance_row, ("expected_refund_cost_per_unit_gbp",), default="0")) or 0.0
    model_asof = _value_from_any(performance_row, ("asof_date",))

    market_price_ex_vat: float | None = None
    if market_price is None or market_price <= 0:
        model_notes.append("missing_market_price")
    elif vat_rate is None:
        vat_rate = 20.0
        model_notes.append("vat_rate_defaulted_20")
        notes.append("NET_FEE_VAT_RATE_DEFAULTED_20")
        market_price_ex_vat = market_price / (1.0 + (vat_rate / 100.0))
    elif vat_rate < 0:
        model_notes.append("invalid_vat_rate")
    else:
        market_price_ex_vat = market_price / (1.0 + (vat_rate / 100.0))

    net_fee_drag: float | None = None
    if performance_row is None:
        model_notes.append("missing_performance_row")
    if current_token_cost is None or current_token_cost <= 0:
        model_notes.append("missing_current_token_cost")
    if break_even_price is None or break_even_price <= 0:
        model_notes.append("missing_break_even_price")
    if current_token_cost is not None and break_even_price is not None:
        net_fee_drag = break_even_price - current_token_cost - refund_drag
        if net_fee_drag < -0.000001:
            model_notes.append("negative_net_fee_drag")

    model_age_hours: float | None = None
    asof_dt = _parse_utc_or_date(asof_utc)
    model_dt = _parse_utc_or_date(model_asof)
    if model_dt is None:
        model_notes.append("missing_model_asof")
    elif asof_dt is not None:
        model_age_hours = max(0.0, (asof_dt - model_dt).total_seconds() / 3600.0)
        if model_age_hours > NET_FEE_MODEL_MAX_AGE_HOURS:
            model_notes.append("stale_model_asof")

    missing_markers = {
        "missing_market_price",
        "missing_performance_row",
        "missing_current_token_cost",
        "missing_break_even_price",
        "missing_model_asof",
    }
    invalid_markers = {"negative_net_fee_drag", "invalid_vat_rate"}
    if any(marker in model_notes for marker in missing_markers):
        status = "missing"
    elif any(marker in model_notes for marker in invalid_markers):
        status = "invalid"
    elif "stale_model_asof" in model_notes:
        status = "stale"

    if status == "fresh":
        model_notes.append("fresh")
    else:
        notes.append(f"NET_FEE_MODEL_{status.upper()}")

    return {
        "market_price_ex_vat_gbp": _num_to_text(market_price_ex_vat),
        "market_price_vat_rate_pct": _num_to_text(vat_rate),
        "current_token_cost_gbp": _num_to_text(current_token_cost),
        "break_even_price_gbp": _num_to_text(break_even_price),
        "net_fee_drag_per_unit_gbp": _num_to_text(net_fee_drag),
        "net_fee_model_status": status,
        "net_fee_model_asof": model_asof,
        "net_fee_model_age_hours": _num_to_text(model_age_hours),
        "net_fee_model_source": "sku_performance_summary" if performance_row is not None else "",
        "net_fee_model_notes": "|".join(sorted(set(model_notes))),
    }


def _build_current_supplier_cost(product_row: pd.Series, notes: list[str]) -> dict[str, str]:
    catalog_raw = str(product_row.get("supplier_catalog_price", "")).strip()
    last_purchase_raw = str(product_row.get("last_purchase_price", "")).strip()
    catalog_price = _num_or_none(catalog_raw)
    last_purchase_price = _num_or_none(last_purchase_raw)

    if catalog_price is not None and catalog_price > 0:
        return {
            "current_supplier_buy_cost_gbp": _num_to_text(catalog_price),
            "current_supplier_cost_source": "supplier_catalog_price",
            "current_cost_value_gbp": _num_to_text(catalog_price),
            "current_cost_source": "supplier_catalog_price",
            "current_cost_confidence": "high",
            "current_cost_class": "current_supplier_cost",
        }

    if catalog_raw and (catalog_price is None or catalog_price <= 0):
        notes.append("COST_AMBIGUOUS_SUPPLIER_CATALOG")

    if last_purchase_price is not None and last_purchase_price > 0:
        notes.append("COST_FALLBACK_LAST_PURCHASE_PRICE")
        return {
            "current_supplier_buy_cost_gbp": _num_to_text(last_purchase_price),
            "current_supplier_cost_source": "last_purchase_price",
            "current_cost_value_gbp": _num_to_text(last_purchase_price),
            "current_cost_source": "last_purchase_price",
            "current_cost_confidence": "medium",
            "current_cost_class": "last_purchase_fallback",
        }

    if last_purchase_raw and (last_purchase_price is None or last_purchase_price <= 0):
        notes.append("COST_AMBIGUOUS_LAST_PURCHASE")

    if catalog_raw or last_purchase_raw:
        notes.append("BLOCKED_AMBIGUOUS_COST_INPUT")
        return {
            "current_supplier_buy_cost_gbp": "",
            "current_supplier_cost_source": "ambiguous_cost",
            "current_cost_value_gbp": "",
            "current_cost_source": "ambiguous_cost",
            "current_cost_confidence": "low",
            "current_cost_class": "ambiguous_cost",
        }

    notes.append("BLOCKED_MISSING_COST_INPUT")
    return {
        "current_supplier_buy_cost_gbp": "",
        "current_supplier_cost_source": "missing_cost",
        "current_cost_value_gbp": "",
        "current_cost_source": "missing_cost",
        "current_cost_confidence": "none",
        "current_cost_class": "no_cost",
    }


def _build_test_supplier_cost(test_row: pd.Series, notes: list[str]) -> dict[str, str]:
    unit_cost = _num_or_none(test_row.get("current_unit_cost", ""))
    currency = str(test_row.get("currency", "")).strip().upper()
    if currency and currency != "GBP":
        notes.append("TEST_COST_NON_GBP_BLOCKED")
        return {
            "current_supplier_buy_cost_gbp": "",
            "current_supplier_cost_source": "supplier_cost_snapshot_test_invalid_currency",
            "current_cost_value_gbp": "",
            "current_cost_source": "supplier_cost_snapshot_test_invalid_currency",
            "current_cost_confidence": "none",
            "current_cost_class": "ambiguous_cost",
            "cost_mode": "test",
            "cost_source_type": str(test_row.get("source_type", "")).strip() or "test_fixture",
            "cost_source_reference": str(test_row.get("source_reference", "")).strip(),
        }

    if unit_cost is None or unit_cost <= 0:
        notes.append("TEST_COST_MISSING_OR_INVALID")
        return {
            "current_supplier_buy_cost_gbp": "",
            "current_supplier_cost_source": "supplier_cost_snapshot_test_missing_cost",
            "current_cost_value_gbp": "",
            "current_cost_source": "supplier_cost_snapshot_test_missing_cost",
            "current_cost_confidence": "none",
            "current_cost_class": "no_cost",
            "cost_mode": "test",
            "cost_source_type": str(test_row.get("source_type", "")).strip() or "test_fixture",
            "cost_source_reference": str(test_row.get("source_reference", "")).strip(),
        }

    notes.append("TEST_COST_SOURCE_APPLIED")
    return {
        "current_supplier_buy_cost_gbp": _num_to_text(unit_cost),
        "current_supplier_cost_source": "supplier_cost_snapshot_test",
        "current_cost_value_gbp": _num_to_text(unit_cost),
        "current_cost_source": "supplier_cost_snapshot_test",
        "current_cost_confidence": "test",
        "current_cost_class": "current_supplier_cost",
        "cost_mode": "test",
        "cost_source_type": str(test_row.get("source_type", "")).strip() or "test_fixture",
        "cost_source_reference": str(test_row.get("source_reference", "")).strip(),
    }


def _value_from_any(row: pd.Series | None, candidates: Iterable[str], default: str = "") -> str:
    if row is None:
        return default
    for candidate in candidates:
        value = str(row.get(candidate, "")).strip()
        if value:
            return value
    return default


def _select_velocity_rows(velocity_df: pd.DataFrame) -> dict[str, pd.Series]:
    if velocity_df.empty:
        return {}
    work = velocity_df.copy()
    work["sku_norm"] = work.get("sku", "").map(_normalize_key)
    work = work[work["sku_norm"] != ""]
    if work.empty:
        return {}
    v30_series = work["v30"] if "v30" in work.columns else pd.Series([""] * len(work), index=work.index)
    window_series = work["window_days"] if "window_days" in work.columns else pd.Series([""] * len(work), index=work.index)
    work["_has_v30"] = v30_series.astype(str).str.strip().ne("")
    work["_window_is_30"] = window_series.astype(str).str.strip().eq("30")
    work = work.sort_values(
        by=["sku_norm", "_has_v30", "_window_is_30"],
        ascending=[True, False, False],
        kind="stable",
    )
    work = work.drop_duplicates(subset=["sku_norm"], keep="first")
    work = work.set_index("sku_norm")
    return {idx: work.loc[idx] for idx in work.index}


def _select_inbound_cost_rows(inbound_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    if inbound_df.empty or "sku" not in inbound_df.columns:
        return {}

    totals: dict[str, dict[str, object]] = {}
    for _, row in inbound_df.iterrows():
        sku_norm = _normalize_key(row.get("sku", ""))
        if not sku_norm:
            continue
        bucket = totals.setdefault(
            sku_norm,
            {
                "received_qty": 0.0,
                "allocated_total": 0.0,
                "unsupported_currency": "",
                "shipment_ids": [],
            },
        )
        currency = _normalize_text(row.get("currency", "")).upper()
        if currency and currency != "GBP":
            bucket["unsupported_currency"] = currency

        received_qty = _num_or_none(row.get("received_qty", ""))
        allocated_total = _num_or_none(row.get("allocated_total", ""))
        if allocated_total is None:
            allocated_amount = _num_or_none(row.get("allocated_amount", "")) or 0.0
            allocated_tax = _num_or_none(row.get("allocated_tax", "")) or 0.0
            allocated_total = allocated_amount + allocated_tax

        if received_qty is not None and received_qty > 0:
            bucket["received_qty"] = float(bucket["received_qty"]) + received_qty
        if allocated_total is not None and allocated_total != 0:
            bucket["allocated_total"] = float(bucket["allocated_total"]) + abs(allocated_total)

        shipment_id = _normalize_text(row.get("shipment_id", ""))
        if shipment_id:
            shipment_ids = bucket["shipment_ids"]
            if isinstance(shipment_ids, list) and shipment_id not in shipment_ids:
                shipment_ids.append(shipment_id)

    out: dict[str, dict[str, str]] = {}
    for sku_norm, bucket in totals.items():
        received_qty = float(bucket["received_qty"])
        allocated_total = float(bucket["allocated_total"])
        unit_cost = allocated_total / received_qty if received_qty > 0 and allocated_total > 0 else None
        shipment_ids = bucket["shipment_ids"] if isinstance(bucket["shipment_ids"], list) else []
        out[sku_norm] = {
            "received_qty": _num_to_text(received_qty),
            "allocated_total": _num_to_text(allocated_total),
            "unit_cost": _num_to_text(unit_cost),
            "unsupported_currency": _normalize_text(bucket["unsupported_currency"]),
            "source_reference": "|".join(str(value) for value in shipment_ids[:5]),
        }
    return out


def _build_inbound_cost_context(inbound_row: dict[str, str] | None, notes: list[str]) -> dict[str, str]:
    if inbound_row is None:
        notes.append("INBOUND_COST_CONFIDENCE_MISSING")
        return {
            "expected_inbound_cost_per_unit_gbp": "",
            "inbound_cost_basis": "missing_sku_inbound_cost_allocation",
            "inbound_cost_confidence": "missing",
            "inbound_cost_source_asof": "",
            "inbound_cost_source_reference": "",
        }

    unsupported_currency = _normalize_text(inbound_row.get("unsupported_currency", ""))
    unit_cost = _num_or_none(inbound_row.get("unit_cost", ""))
    if unsupported_currency:
        notes.append("INBOUND_COST_UNSUPPORTED_CURRENCY")
        return {
            "expected_inbound_cost_per_unit_gbp": "",
            "inbound_cost_basis": f"unsupported_currency_{unsupported_currency}",
            "inbound_cost_confidence": "unsupported_currency",
            "inbound_cost_source_asof": "",
            "inbound_cost_source_reference": _normalize_text(inbound_row.get("source_reference", "")),
        }
    if unit_cost is None or unit_cost <= 0:
        notes.append("INBOUND_COST_CONFIDENCE_MISSING")
        return {
            "expected_inbound_cost_per_unit_gbp": "",
            "inbound_cost_basis": "missing_sku_inbound_cost_allocation",
            "inbound_cost_confidence": "missing",
            "inbound_cost_source_asof": "",
            "inbound_cost_source_reference": _normalize_text(inbound_row.get("source_reference", "")),
        }

    return {
        "expected_inbound_cost_per_unit_gbp": _num_to_text(unit_cost),
        "inbound_cost_basis": "allocated_inbound_cost_per_received_unit",
        "inbound_cost_confidence": "sku_allocated",
        "inbound_cost_source_asof": "out/inbound_costs_allocated_sku.csv",
        "inbound_cost_source_reference": _normalize_text(inbound_row.get("source_reference", "")),
    }


def _refund_confidence_is_weak(*, proof_state: str, sample_confidence: str) -> bool:
    proof = _normalize_text(proof_state).lower()
    confidence = _normalize_text(sample_confidence).lower()
    return proof in WEAK_REFUND_PROOF_STATES or confidence in WEAK_REFUND_CONFIDENCE_STATES


def _build_profit_input_confidence(row: dict[str, str], notes: list[str]) -> dict[str, str]:
    blockers: list[str] = []

    if _refund_confidence_is_weak(
        proof_state=row.get("refund_proof_state", ""),
        sample_confidence=row.get("refund_sample_confidence", ""),
    ):
        blockers.append("missing_refund_confidence")

    inbound_confidence = _normalize_text(row.get("inbound_cost_confidence", "")).lower()
    if inbound_confidence in WEAK_INBOUND_COST_CONFIDENCE_STATES:
        blockers.append("missing_inbound_cost_confidence")

    net_fee_status = _normalize_text(row.get("net_fee_model_status", "")).lower()
    if net_fee_status != "fresh":
        blockers.append("missing_net_fee_model" if net_fee_status in {"", "missing"} else f"{net_fee_status}_net_fee_model")

    token_cost_trust_state = _normalize_text(row.get("token_cost_trust_state", "")).lower()
    if token_cost_trust_state != "trusted":
        blockers.append("token_cost_not_trusted" if token_cost_trust_state else "token_cost_not_verified")

    if (_num_or_none(row.get("market_price_gbp", "")) or 0.0) <= 0:
        blockers.append("missing_market_price")
    if (_num_or_none(row.get("current_supplier_buy_cost_gbp", "")) or 0.0) <= 0:
        blockers.append("missing_supplier_cost")

    unique_blockers = list(dict.fromkeys(blockers))
    if unique_blockers:
        notes.append("PROFIT_INPUT_CONFIDENCE_MISSING")
        return {
            "profit_input_confidence": "missing_profit_inputs",
            "profit_input_blockers": "|".join(unique_blockers),
        }
    return {
        "profit_input_confidence": "profit_inputs_verified",
        "profit_input_blockers": "",
    }


def _backtest_status_priority(value: object) -> int:
    token = str(value or "").strip().lower()
    if token == "ready":
        return 0
    if token == "manual_review":
        return 1
    if token == "no_history":
        return 2
    return 9


def _select_backtest_rows(backtest_df: pd.DataFrame) -> tuple[dict[tuple[str, str], pd.Series], dict[str, pd.Series]]:
    if backtest_df.empty:
        return {}, {}
    work = backtest_df.copy()
    work["seller_sku_norm"] = work.get("seller_sku", "").map(_normalize_key)
    work["asin_norm"] = work.get("asin", "").map(_normalize_key)
    work = work[work["seller_sku_norm"] != ""]
    if work.empty:
        return {}, {}
    work["summary_status_priority"] = work.get("summary_status", "").map(_backtest_status_priority)
    work["observed_utc_sort"] = work.get("observed_utc", "").astype(str)

    by_pair = work.sort_values(
        by=["seller_sku_norm", "asin_norm", "summary_status_priority", "observed_utc_sort"],
        ascending=[True, True, True, False],
        kind="stable",
    )
    by_pair = by_pair.drop_duplicates(subset=["seller_sku_norm", "asin_norm"], keep="first")
    by_pair = by_pair.set_index(["seller_sku_norm", "asin_norm"])
    pair_map: dict[tuple[str, str], pd.Series] = {idx: by_pair.loc[idx] for idx in by_pair.index}

    by_sku = work.sort_values(
        by=["seller_sku_norm", "summary_status_priority", "observed_utc_sort"],
        ascending=[True, True, False],
        kind="stable",
    )
    by_sku = by_sku.drop_duplicates(subset=["seller_sku_norm"], keep="first").set_index("seller_sku_norm")
    sku_map: dict[str, pd.Series] = {idx: by_sku.loc[idx] for idx in by_sku.index}

    return pair_map, sku_map


def _select_supplier_buy_cost_truth_rows(cost_truth_df: pd.DataFrame) -> dict[str, pd.Series]:
    if cost_truth_df.empty:
        return {}
    work = cost_truth_df.copy()
    work["seller_sku_norm"] = work.get("seller_sku", "").map(_normalize_key)
    work = work[work["seller_sku_norm"] != ""]
    if work.empty:
        return {}
    work["_asof_sort"] = pd.to_datetime(work.get("asof_utc", ""), errors="coerce", utc=True)
    work = work.sort_values(
        by=["seller_sku_norm", "_asof_sort"],
        ascending=[True, False],
        kind="stable",
    )
    work = work.drop_duplicates(subset=["seller_sku_norm"], keep="first").set_index("seller_sku_norm")
    return {idx: work.loc[idx] for idx in work.index}


def _select_token_cost_trust_rows(trust_df: pd.DataFrame) -> dict[str, pd.Series]:
    if trust_df.empty or "seller_sku" not in trust_df.columns:
        return {}
    work = trust_df.copy()
    work["seller_sku_norm"] = work.get("seller_sku", "").map(_normalize_key)
    work = work[work["seller_sku_norm"] != ""]
    if work.empty:
        return {}
    if "proof_utc" in work.columns:
        work["_proof_sort"] = pd.to_datetime(work.get("proof_utc", ""), errors="coerce", utc=True)
        work = work.sort_values(by=["seller_sku_norm", "_proof_sort"], ascending=[True, False], kind="stable")
    work = work.drop_duplicates(subset=["seller_sku_norm"], keep="first").set_index("seller_sku_norm")
    return {idx: work.loc[idx] for idx in work.index}


def _build_token_cost_trust_context(trust_row: pd.Series | None, notes: list[str]) -> dict[str, str]:
    if trust_row is None:
        notes.append("TOKEN_COST_TRUST_NOT_VERIFIED")
        return {
            "token_cost_trust_state": "not_verified",
            "token_cost_trust_basis": "restock_token_cost_trust_gate_missing_or_no_sku_row",
            "token_cost_trust_source": "out/systems/O/live/restock_token_cost_trust_gate_live.csv",
            "token_cost_trust_blockers": "missing_token_cost_trust_gate",
        }
    state = _normalize_text(trust_row.get("token_cost_trust_state", "")).lower() or "not_verified"
    if state != "trusted":
        notes.append(f"TOKEN_COST_TRUST_{state.upper()}")
    return {
        "token_cost_trust_state": state,
        "token_cost_trust_basis": _normalize_text(trust_row.get("token_cost_trust_basis", "")),
        "token_cost_trust_source": _normalize_text(trust_row.get("token_cost_trust_source", "")),
        "token_cost_trust_blockers": _normalize_text(trust_row.get("token_cost_trust_blockers", "")),
    }


def _select_profile_rows(profile_df: pd.DataFrame) -> dict[str, pd.Series]:
    if profile_df.empty or "seller_sku" not in profile_df.columns:
        return {}
    work = profile_df.copy()
    work["seller_sku_norm"] = work.get("seller_sku", "").map(_normalize_key)
    work = work[work["seller_sku_norm"] != ""]
    if work.empty:
        return {}
    work = work.drop_duplicates(subset=["seller_sku_norm"], keep="first").set_index("seller_sku_norm")
    return {idx: work.loc[idx] for idx in work.index}


def _build_backtest_context(backtest_row: pd.Series | None) -> dict[str, str]:
    context: dict[str, str] = {target_col: "" for _, target_col in BACKTEST_FIELD_MAP}
    if backtest_row is None:
        return context
    for source_col, target_col in BACKTEST_FIELD_MAP:
        context[target_col] = str(backtest_row.get(source_col, "")).strip()
    return context


def _build_supplier_buy_cost_context(cost_truth_row: pd.Series, notes: list[str]) -> dict[str, str]:
    expected_cost = _num_or_none(cost_truth_row.get("expected_next_unit_cost_gbp", ""))
    confidence = _normalize_text(cost_truth_row.get("cost_confidence", "")) or "none"
    expected_source = _normalize_text(cost_truth_row.get("expected_cost_source", "")) or "supplier_buy_cost_truth"
    user_check_required = _flag_text(cost_truth_row.get("user_price_check_required", ""))
    review_reason = _normalize_text(cost_truth_row.get("review_reason", ""))
    price_list_pack_size = _positive_int_text(cost_truth_row.get("price_list_pack_size", ""))
    price_list_moq = _positive_int_text(cost_truth_row.get("price_list_moq", ""), default=price_list_pack_size or "")
    price_list_unit_code = _normalize_text(cost_truth_row.get("price_list_unit_code", ""))
    price_list_pack_cost = _normalize_text(cost_truth_row.get("price_list_pack_cost_gbp", ""))
    context = {
        "price_list_unit_cost_gbp": _normalize_text(cost_truth_row.get("price_list_unit_cost_gbp", "")),
        "price_list_currency": _normalize_text(cost_truth_row.get("price_list_currency", "")),
        "price_list_unit_code": price_list_unit_code,
        "price_list_pack_size": price_list_pack_size,
        "price_list_pack_cost_gbp": price_list_pack_cost,
        "price_list_moq": price_list_moq,
        "price_list_source_batch_id": _normalize_text(cost_truth_row.get("price_list_source_batch_id", "")),
        "price_list_source_received_at_utc": _normalize_text(cost_truth_row.get("price_list_source_received_at_utc", "")),
        "price_list_source_row_key": _normalize_text(cost_truth_row.get("price_list_source_row_key", "")),
        "purchase_reference_list_cost_gbp": _normalize_text(cost_truth_row.get("purchase_reference_list_cost_gbp", "")),
        "actual_paid_unit_cost_gbp": _normalize_text(cost_truth_row.get("actual_paid_unit_cost_gbp", "")),
        "actual_paid_source": _normalize_text(cost_truth_row.get("actual_paid_source", "")),
        "actual_vs_list_ratio": _normalize_text(cost_truth_row.get("actual_vs_list_ratio", "")),
        "discount_assumption_pct": _normalize_text(cost_truth_row.get("discount_assumption_pct", "")),
        "usual_paid_unit_cost_gbp": _normalize_text(cost_truth_row.get("usual_paid_unit_cost_gbp", "")),
        "usual_paid_cost_basis": _normalize_text(cost_truth_row.get("usual_paid_cost_basis", "")),
        "usual_paid_cost_confidence": _normalize_text(cost_truth_row.get("usual_paid_cost_confidence", "")),
        "usual_paid_sample_count": _normalize_text(cost_truth_row.get("usual_paid_sample_count", "")),
        "usual_paid_discount_vs_list_pct": _normalize_text(cost_truth_row.get("usual_paid_discount_vs_list_pct", "")),
        "usual_paid_vs_list_delta_gbp": _normalize_text(cost_truth_row.get("usual_paid_vs_list_delta_gbp", "")),
        "price_list_vs_actual_paid_delta_gbp": _normalize_text(cost_truth_row.get("price_list_vs_actual_paid_delta_gbp", "")),
        "price_list_vs_purchase_reference_delta_gbp": _normalize_text(
            cost_truth_row.get("price_list_vs_purchase_reference_delta_gbp", "")
        ),
        "price_list_change_status": _normalize_text(cost_truth_row.get("price_list_change_status", "")),
        "price_list_previous_unit_cost_gbp": _normalize_text(cost_truth_row.get("price_list_previous_unit_cost_gbp", "")),
        "price_list_previous_pack_size": _normalize_text(cost_truth_row.get("price_list_previous_pack_size", "")),
        "price_list_previous_seen_at_utc": _normalize_text(cost_truth_row.get("price_list_previous_seen_at_utc", "")),
        "price_list_change_delta_gbp": _normalize_text(cost_truth_row.get("price_list_change_delta_gbp", "")),
        "price_list_change_pct": _normalize_text(cost_truth_row.get("price_list_change_pct", "")),
        "expected_next_unit_cost_gbp": _normalize_text(cost_truth_row.get("expected_next_unit_cost_gbp", "")),
        "expected_cost_source": expected_source,
        "user_price_check_required": user_check_required,
        "supplier_cost_review_reason": review_reason,
        "cost_source_type": "supplier_buy_cost_truth",
        "cost_source_reference": get_o_output_contract("supplier_buy_cost_truth").rel_path,
    }
    if price_list_pack_size not in {"", "1"}:
        notes.append("PRICE_LIST_PACK_SIZE_APPLIED")
        context.update(
            {
                "supplier_pack_size": price_list_pack_size,
                "moq": price_list_moq or price_list_pack_size,
                "order_qty_mode": "sell_packs",
                "order_qty_unit_label": "Packs",
                "sell_pack_qty": price_list_pack_size,
                "pack_conversion_note": (
                    f"Supplier list {price_list_unit_code or 'pack'}: price GBP {price_list_pack_cost} "
                    f"covers {price_list_pack_size} units; profit uses per-unit cost"
                ).strip(),
            }
        )
    if expected_cost is not None and expected_cost > 0:
        notes.append("SUPPLIER_BUY_COST_TRUTH_APPLIED")
        if user_check_required == "1":
            notes.append("SUPPLIER_COST_USER_CHECK_REQUIRED")
        return {
            **context,
            "current_supplier_buy_cost_gbp": _num_to_text(expected_cost),
            "current_supplier_cost_source": "supplier_buy_cost_truth",
            "current_cost_value_gbp": _num_to_text(expected_cost),
            "current_cost_source": expected_source,
            "current_cost_confidence": confidence,
            "current_cost_class": "expected_supplier_cost",
            "current_cost_truth_type": "supplier_buy_cost_truth",
        }
    notes.append("SUPPLIER_BUY_COST_TRUTH_NO_USABLE_EXPECTED_COST")
    return context


def _looks_like_sika_special_candidate(row: dict[str, str]) -> bool:
    supplier_name = _normalize_text(row.get("supplier_name", "")).lower()
    supplier_sku = _normalize_text(row.get("supplier_sku", ""))
    title = _normalize_text(row.get("title", "")).lower()
    if supplier_sku in {"484651", "484652"}:
        return True
    supplier_or_title_sika = "sika" in supplier_name or "sika" in title
    glue_terms = ("glue", "superglue", "super glue", "cyn", "everbuild")
    multi_pack_terms = ("pack", "pcs", " x ", "2x", "3x", "2 x", "3 x")
    size_terms = ("20g", "20 g", "50g", "50 g")
    return (
        supplier_or_title_sika
        and any(term in title for term in glue_terms)
        and any(term in title for term in multi_pack_terms)
        and any(term in title for term in size_terms)
    )


def _title_mentions_pack_size(title: object, pack_size: int) -> bool:
    text = f" {str(title or '').lower().replace('-', ' ')} "
    patterns = (
        f"{pack_size} pack",
        f"pack of {pack_size}",
        f"{pack_size} x",
        f"x {pack_size}",
        f"{pack_size}x",
    )
    return any(pattern in text for pattern in patterns)


def _build_pack_profile_fields(
    *,
    row: dict[str, str],
    quantity_profile_row: pd.Series | None,
    special_profile_row: pd.Series | None,
    notes: list[str],
) -> dict[str, str]:
    base_cost = _num_or_none(row.get("current_supplier_buy_cost_gbp", ""))
    quantity_status = _normalize_text(quantity_profile_row.get("profile_status", "") if quantity_profile_row is not None else "")
    special_status = _normalize_text(special_profile_row.get("profile_status", "") if special_profile_row is not None else "")
    quantity_status_l = quantity_status.lower()
    special_status_l = special_status.lower()
    has_quantity_profile = quantity_profile_row is not None
    has_special_profile = special_profile_row is not None
    special_candidate = _looks_like_sika_special_candidate(row)

    components = 1
    supplier_cost_basis = "sell_pack"
    component_unit_label = "unit"
    pack_status = "default_normal"

    if has_quantity_profile:
        component_value = _num_or_none(quantity_profile_row.get("components_per_sell_pack", ""))
        if component_value is not None and component_value > 0 and component_value.is_integer():
            components = int(component_value)
        else:
            notes.append("invalid_component_conversion")
            pack_status = "invalid"
        supplier_cost_basis = _normalize_text(quantity_profile_row.get("supplier_cost_basis", "")).lower()
        component_unit_label = _normalize_text(quantity_profile_row.get("component_unit_label", "")) or component_unit_label
        if supplier_cost_basis == "":
            notes.append("missing_supplier_cost_basis")
            pack_status = "invalid"
        elif supplier_cost_basis not in {"sell_pack", "component_unit", "supplier_box"}:
            notes.append("invalid_component_conversion")
            pack_status = "invalid"
        elif pack_status != "invalid":
            pack_status = quantity_status or "unconfirmed_pack_profile"
        if quantity_status_l not in {"confirmed", "approved"}:
            notes.append("unconfirmed_pack_profile")
            if pack_status != "invalid":
                pack_status = quantity_status or "unconfirmed_pack_profile"
    elif special_candidate:
        notes.append("missing_pack_profile")
        pack_status = "missing_pack_profile"

    supplier_box_components = _normalize_text(
        special_profile_row.get("supplier_box_components", "") if special_profile_row is not None else ""
    )
    quantity_strategy = _normalize_text(
        special_profile_row.get("quantity_strategy", "") if special_profile_row is not None else ""
    )
    preferred_order_sell_packs = _normalize_text(
        special_profile_row.get("preferred_order_sell_packs", "") if special_profile_row is not None else ""
    )
    preferred_order_components = _normalize_text(
        special_profile_row.get("preferred_order_components", "") if special_profile_row is not None else ""
    )
    preferred_supplier_boxes = _normalize_text(
        special_profile_row.get("preferred_supplier_boxes", "") if special_profile_row is not None else ""
    )
    target_carton_weight_kg = _normalize_text(
        special_profile_row.get("target_carton_weight_kg", "") if special_profile_row is not None else ""
    )
    hazmat_group = _normalize_text(
        special_profile_row.get("hazmat_group", "") if special_profile_row is not None else ""
    )
    isolate_from_normal_po = _flag_text(
        special_profile_row.get("isolate_from_normal_po", "") if special_profile_row is not None else ""
    )

    special_required = has_special_profile or special_candidate
    if special_required:
        if not has_special_profile:
            notes.append("special_order_profile_required")
            if pack_status not in {"invalid", "missing_pack_profile"}:
                pack_status = "special_order_profile_required"
        elif special_status_l not in {"confirmed", "approved"}:
            notes.append("special_order_profile_required")
            if pack_status not in {"invalid", "missing_pack_profile"}:
                pack_status = special_status or "unconfirmed_pack_profile"
        if hazmat_group == "" or isolate_from_normal_po != "1":
            notes.append("special_order_profile_required")
            if pack_status not in {"invalid", "missing_pack_profile"}:
                pack_status = "special_order_profile_required"

    expected_sell_pack_cost = base_cost
    expected_component_cost = base_cost
    box_components = _num_or_none(supplier_box_components)
    if base_cost is not None and base_cost > 0:
        if supplier_cost_basis == "component_unit":
            expected_component_cost = base_cost
            expected_sell_pack_cost = base_cost * components
        elif supplier_cost_basis == "sell_pack":
            expected_sell_pack_cost = base_cost
            expected_component_cost = base_cost / components if components > 0 else None
        elif supplier_cost_basis == "supplier_box":
            if box_components is None or box_components <= 0:
                expected_sell_pack_cost = None
                expected_component_cost = None
                notes.append("invalid_component_conversion")
                pack_status = "invalid"
            else:
                expected_component_cost = base_cost / box_components
                expected_sell_pack_cost = expected_component_cost * components
        if expected_sell_pack_cost is not None and expected_sell_pack_cost > 0:
            row["current_supplier_buy_cost_gbp"] = _num_to_text(expected_sell_pack_cost)
            row["expected_next_unit_cost_gbp"] = _num_to_text(expected_sell_pack_cost)
            if supplier_cost_basis != "sell_pack":
                notes.append("SUPPLIER_COST_CONVERTED_TO_SELL_PACK")
                for source_field in ("current_supplier_cost_source", "current_cost_source", "expected_cost_source"):
                    source_value = _normalize_text(row.get(source_field, ""))
                    if source_value and not source_value.endswith("_converted_to_sell_pack"):
                        row[source_field] = f"{source_value}_converted_to_sell_pack"
                row["current_cost_value_gbp"] = _num_to_text(expected_sell_pack_cost)
                row["current_cost_class"] = "sell_pack_converted_supplier_cost"

    preferred_packs_n = _num_or_none(preferred_order_sell_packs)
    preferred_components_n = _num_or_none(preferred_order_components)
    preferred_boxes_n = _num_or_none(preferred_supplier_boxes)
    if has_special_profile and quantity_strategy:
        box_ok = box_components is not None and box_components > 0
        carton_math_ok = (
            preferred_packs_n is not None
            and preferred_components_n is not None
            and preferred_boxes_n is not None
            and preferred_packs_n * components == preferred_components_n
            and box_ok
            and preferred_boxes_n * box_components == preferred_components_n
        )
        if not carton_math_ok:
            notes.append("invalid_supplier_box_alignment")
            pack_status = "invalid"

    if has_quantity_profile and components > 1:
        title = row.get("title", "")
        if _title_mentions_pack_size(title, 2) and components != 2:
            notes.append("pack_title_profile_mismatch")
            pack_status = "invalid"
        elif _title_mentions_pack_size(title, 3) and components != 3:
            notes.append("pack_title_profile_mismatch")
            pack_status = "invalid"

    return {
        "component_unit_label": component_unit_label,
        "components_per_sell_pack": str(components),
        "supplier_cost_basis": supplier_cost_basis,
        "expected_sell_pack_cost_gbp": _num_to_text(expected_sell_pack_cost),
        "expected_component_cost_gbp": _num_to_text(expected_component_cost),
        "quantity_strategy": quantity_strategy,
        "preferred_order_sell_packs": preferred_order_sell_packs,
        "preferred_order_components": preferred_order_components,
        "preferred_supplier_boxes": preferred_supplier_boxes,
        "supplier_box_components": supplier_box_components,
        "hazmat_group": hazmat_group,
        "isolate_from_normal_po": isolate_from_normal_po,
        "target_carton_weight_kg": target_carton_weight_kg,
        "pack_profile_status": pack_status,
    }


def _finalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    contract = get_o_output_contract("restock_source_view")
    required_cols = list(contract.required_columns)
    optional_cols = list(contract.optional_columns)
    for col in required_cols + optional_cols:
        if col not in df.columns:
            df[col] = ""
    for col in NUMERIC_DEFAULT_ZERO_COLUMNS:
        if col not in df.columns:
            df[col] = "0"
        else:
            df[col] = df[col].map(lambda v: "0" if str(v).strip() == "" else str(v).strip())
    for col in ("asof_utc", "seller_sku", "asin", "supplier_code", "supplier_name"):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    return df


def _build_coverage_fields(row: dict[str, str]) -> dict[str, str]:
    sale_status_normalized = _normalize_sale_status(row.get("sale_status", ""))
    is_active_candidate = sale_status_normalized == "active"
    velocity_30d = _num_or_none(row.get("velocity_30d", "")) or 0.0
    has_demand_input = velocity_30d > DEMAND_INPUT_MIN_UNITS_PER_DAY
    has_current_cost_input = (_num_or_none(row.get("current_supplier_buy_cost_gbp", "")) or 0.0) > 0
    has_current_market_price_input = (_num_or_none(row.get("market_price_gbp", "")) or 0.0) > 0
    cost_mode = _normalize_mode(row.get("cost_mode", ""))

    if not is_active_candidate:
        if sale_status_normalized == "unknown":
            coverage_block_reason = "inactive_or_unknown_status"
        else:
            coverage_block_reason = "inactive_status"
    else:
        missing: list[str] = []
        if not has_current_cost_input:
            missing.append("cost")
        if not has_current_market_price_input:
            missing.append("market")
        if not has_demand_input:
            missing.append("demand")
        if not missing:
            coverage_block_reason = "ready_minimum_inputs"
        elif len(missing) == 1:
            coverage_block_reason = f"missing_{missing[0]}_only"
        else:
            coverage_block_reason = "missing_" + "_and_".join(missing)

    return {
        "sale_status_normalized": sale_status_normalized,
        "is_active_candidate": "1" if is_active_candidate else "0",
        "has_current_cost_input": "1" if has_current_cost_input else "0",
        "has_current_market_price_input": "1" if has_current_market_price_input else "0",
        "has_demand_input": "1" if has_demand_input else "0",
        "has_minimum_restock_inputs": "1" if (is_active_candidate and has_current_cost_input and has_current_market_price_input and has_demand_input) else "0",
        "coverage_block_reason": coverage_block_reason,
        "current_cost_truth_type": (
            "test_cost_truth"
            if has_current_cost_input and cost_mode == "test"
            else "live_cost_truth"
            if has_current_cost_input
            else "no_cost_truth"
        ),
    }


def _select_test_cost_row(
    *,
    test_cost_map_by_sku: dict[str, pd.Series],
    test_cost_map_by_asin: dict[str, pd.Series],
    sku_norm: str,
    asin_norm: str,
) -> pd.Series | None:
    row = test_cost_map_by_sku.get(sku_norm)
    if row is not None:
        return row
    return test_cost_map_by_asin.get(asin_norm)


def build_restock_source_view(
    root: Path | None = None,
    *,
    asof_utc: str | None = None,
    cost_mode: str | None = None,
) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    timestamp_utc = asof_utc or _utc_now_iso()
    effective_cost_mode = _normalize_mode(cost_mode if cost_mode is not None else os.environ.get(TEST_COST_MODE_ENV, "live"))
    contracts = get_phase1_source_contracts()
    source_data: dict[str, SourceReadResult] = {
        name: _read_source(root_path, name, contract) for name, contract in contracts.items()
    }

    product_source = source_data["product_db_preview"]
    inventory_source = source_data["inventory_summaries"]
    velocity_source = source_data["sku_sales_velocity"]
    performance_source = source_data["sku_performance_summary"]
    inbound_cost_source = source_data["inbound_costs_allocated_sku"]
    offer_source = source_data["listing_offer_snapshot_latest"]
    backtest_source = source_data["feeder_backtest_summary_live"]

    if product_source.df.empty:
        out_df = _finalize_columns(pd.DataFrame())
        out_path = root_path / get_o_output_contract("restock_source_view").rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        write_o_contract_df(root_path, "restock_source_view", out_df)
        print(
            {
                "status": "success",
                "rows": 0,
                "snapshot": str(out_path),
                "notes": "product_db_preview missing or empty",
            }
        )
        return out_df

    product_df = product_source.df.copy()
    product_df["seller_sku_norm"] = product_df.get("seller_sku", "").map(_normalize_key)
    product_df = product_df[product_df["seller_sku_norm"] != ""]
    if product_df.empty:
        out_df = _finalize_columns(pd.DataFrame())
        out_path = root_path / get_o_output_contract("restock_source_view").rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        write_o_contract_df(root_path, "restock_source_view", out_df)
        print(
            {
                "status": "success",
                "rows": 0,
                "snapshot": str(out_path),
                "notes": "no product rows with seller_sku",
            }
        )
        return out_df
    product_df = product_df.drop_duplicates(subset=["seller_sku_norm"], keep="first")

    inventory_map: dict[str, pd.Series] = {}
    if not inventory_source.df.empty:
        inv = inventory_source.df.copy()
        inv["seller_sku_norm"] = inv.get("seller_sku", "").map(_normalize_key)
        inv = inv[inv["seller_sku_norm"] != ""]
        inv = inv.drop_duplicates(subset=["seller_sku_norm"], keep="first").set_index("seller_sku_norm")
        inventory_map = {idx: inv.loc[idx] for idx in inv.index}

    velocity_map: dict[str, pd.Series] = {}
    if not velocity_source.df.empty:
        velocity_map = _select_velocity_rows(velocity_source.df)

    perf_map: dict[str, pd.Series] = {}
    if not performance_source.df.empty:
        perf = performance_source.df.copy()
        perf["sku_norm"] = perf.get("sku", "").map(_normalize_key)
        perf = perf[perf["sku_norm"] != ""]
        perf = perf.drop_duplicates(subset=["sku_norm"], keep="first").set_index("sku_norm")
        perf_map = {idx: perf.loc[idx] for idx in perf.index}

    inbound_cost_map = _select_inbound_cost_rows(inbound_cost_source.df)

    offer_map: dict[str, pd.Series] = {}
    if not offer_source.df.empty:
        offer = offer_source.df.copy()
        offer["sku_norm"] = offer.get("sku", "").map(_normalize_key)
        offer = offer[offer["sku_norm"] != ""]
        offer = offer.drop_duplicates(subset=["sku_norm"], keep="first").set_index("sku_norm")
        offer_map = {idx: offer.loc[idx] for idx in offer.index}

    backtest_map_by_pair: dict[tuple[str, str], pd.Series] = {}
    backtest_map_by_sku: dict[str, pd.Series] = {}
    if not backtest_source.df.empty:
        backtest_map_by_pair, backtest_map_by_sku = _select_backtest_rows(backtest_source.df)

    supplier_buy_cost_truth_map = _select_supplier_buy_cost_truth_rows(
        read_o_contract_df(root_path, "supplier_buy_cost_truth")
    )
    token_cost_trust_map = _select_token_cost_trust_rows(
        read_o_contract_df(root_path, "restock_token_cost_trust_gate_live")
    )
    sku_quantity_profile_map = _select_profile_rows(read_o_contract_df(root_path, "sku_quantity_profiles"))
    special_order_profile_map = _select_profile_rows(read_o_contract_df(root_path, "special_order_profiles"))

    missing_source_notes: list[str] = []
    test_cost_map_by_sku: dict[str, pd.Series] = {}
    test_cost_map_by_asin: dict[str, pd.Series] = {}
    if effective_cost_mode == "test":
        test_cost_df = read_o_contract_df(root_path, "supplier_cost_snapshot_test")
        if test_cost_df.empty:
            missing_source_notes.append("TEST_COST_SNAPSHOT_MISSING")
        else:
            current_only = test_cost_df[test_cost_df.get("is_current", "").map(_truthy)]
            if current_only.empty and "is_current" not in test_cost_df.columns:
                current_only = test_cost_df
            current_only = current_only.copy()
            current_only["seller_sku_norm"] = current_only.get("seller_sku", "").map(_normalize_key)
            current_only["asin_norm"] = current_only.get("asin", "").map(_normalize_key)
            if not current_only.empty:
                current_only = current_only.drop_duplicates(subset=["seller_sku_norm", "asin_norm"], keep="first")
                for _, test_row in current_only.iterrows():
                    sku_norm = str(test_row.get("seller_sku_norm", "")).strip()
                    asin_norm = str(test_row.get("asin_norm", "")).strip()
                    if sku_norm:
                        test_cost_map_by_sku[sku_norm] = test_row
                    if asin_norm:
                        test_cost_map_by_asin[asin_norm] = test_row

    for name, result in source_data.items():
        if result.file_missing:
            missing_source_notes.append(f"SOURCE_FILE_MISSING:{name}")
        elif result.missing_columns:
            missing_source_notes.append(f"SOURCE_COLUMNS_MISSING:{name}:{'|'.join(result.missing_columns)}")

    rows: list[dict[str, str]] = []
    for _, product_row in product_df.iterrows():
        sku_norm = str(product_row["seller_sku_norm"])
        asin_norm = _normalize_key(product_row.get("asin", ""))
        notes = list(missing_source_notes)
        inventory_row = inventory_map.get(sku_norm)
        velocity_row = velocity_map.get(sku_norm)
        performance_row = perf_map.get(sku_norm)
        inbound_cost_row = inbound_cost_map.get(sku_norm)
        offer_row = offer_map.get(sku_norm)
        backtest_row = backtest_map_by_pair.get((sku_norm, asin_norm))
        if backtest_row is None:
            backtest_row = backtest_map_by_sku.get(sku_norm)
        backtest_context = _build_backtest_context(backtest_row)

        if inventory_row is None:
            notes.append("MISSING_INVENTORY_CONTEXT")
        if velocity_row is None:
            notes.append("MISSING_VELOCITY_CONTEXT")
        if performance_row is None:
            notes.append("MISSING_PERFORMANCE_CONTEXT")

        market_price_gbp, market_price_basis = _build_market_context(offer_row, performance_row, product_row, notes)
        cost_context = _build_current_supplier_cost(product_row, notes)
        cost_context["cost_mode"] = "live"
        cost_context["cost_source_type"] = "live_product_inputs"
        cost_context["cost_source_reference"] = "out/product_db_preview.csv"
        cost_truth_row = supplier_buy_cost_truth_map.get(sku_norm)
        if effective_cost_mode != "test" and cost_truth_row is not None:
            cost_context.update(_build_supplier_buy_cost_context(cost_truth_row, notes))

        if effective_cost_mode == "test":
            notes.append("TEST_COST_MODE_ACTIVE")
            test_cost_row = _select_test_cost_row(
                test_cost_map_by_sku=test_cost_map_by_sku,
                test_cost_map_by_asin=test_cost_map_by_asin,
                sku_norm=sku_norm,
                asin_norm=asin_norm,
            )
            if test_cost_row is not None:
                cost_context = _build_test_supplier_cost(test_cost_row, notes)
            else:
                notes.append("TEST_COST_NO_MATCH")

        roi_context = ""
        if performance_row is not None:
            if market_price_basis == "BUY_BOX_PRICE":
                roi_context = _value_from_any(performance_row, ("roi_at_buy_box_price_pct",))
            elif market_price_basis == "OUR_PRICE":
                roi_context = _value_from_any(performance_row, ("roi_at_our_price_pct",))
            else:
                roi_context = _value_from_any(
                    performance_row,
                    ("roi_at_buy_box_price_pct", "roi_at_our_price_pct"),
                )

        net_fee_context = _build_net_fee_context(
            performance_row=performance_row,
            product_row=product_row,
            market_price_gbp=market_price_gbp,
            asof_utc=timestamp_utc,
            notes=notes,
        )
        token_cost_trust_context = _build_token_cost_trust_context(token_cost_trust_map.get(sku_norm), notes)
        inbound_cost_context = _build_inbound_cost_context(inbound_cost_row, notes)
        refund_proof_state = _value_from_any(performance_row, ("refund_proof_state",), default="not_yet_proven")
        refund_sample_confidence = _value_from_any(performance_row, ("refund_sample_confidence",))
        if _refund_confidence_is_weak(
            proof_state=refund_proof_state,
            sample_confidence=refund_sample_confidence,
        ):
            notes.append("REFUND_PROOF_WEAK")

        row = {
            "asof_utc": timestamp_utc,
            "seller_sku": str(product_row.get("seller_sku", "")).strip(),
            "asin": _value_from_any(product_row, ("asin",), default=_value_from_any(inventory_row, ("asin",))),
            "title": str(product_row.get("title", "")).strip(),
            "main_image": str(product_row.get("main_image", "")).strip(),
            "supplier_code": str(product_row.get("supplier_code", "")).strip(),
            "supplier_name": str(product_row.get("supplier_name", "")).strip(),
            "sale_status": str(product_row.get("sale_status", "")).strip(),
            "supplier_catalog_price": _value_from_any(product_row, ("supplier_catalog_price",)),
            "last_purchase_price": _value_from_any(product_row, ("last_purchase_price",)),
            "supplier_pack_size": _value_from_any(product_row, ("supplier_pack_size",), default="1"),
            "moq": _value_from_any(product_row, ("moq",), default="1"),
            "lead_time_days": _value_from_any(
                product_row,
                ("lead_time_days", "supplier_lead_time_days"),
                default=_value_from_any(performance_row, ("lead_time_days",), default="0"),
            ),
            "bulk_long_lead_flag": _value_from_any(product_row, ("bulk_long_lead_flag",), default="0"),
            "out_of_stock_days": _value_from_any(product_row, ("out_of_stock_days",), default="0"),
            "snooze_until_utc": _value_from_any(product_row, ("snooze_until_utc",)),
            "available_now": _value_from_any(inventory_row, ("available",), default="0"),
            "total_quantity_now": _value_from_any(inventory_row, ("total_quantity",), default="0"),
            "amazon_inbound_working": _value_from_any(inventory_row, ("inbound_working",), default="0"),
            "amazon_inbound_shipped": _value_from_any(inventory_row, ("inbound_shipped",), default="0"),
            "amazon_inbound_receiving": _value_from_any(inventory_row, ("inbound_receiving",), default="0"),
            "velocity_7d": _value_from_any(velocity_row, ("v7",), default="0"),
            "velocity_30d": _value_from_any(velocity_row, ("v30",), default="0"),
            "velocity_90d": _value_from_any(velocity_row, ("v90",), default="0"),
            "market_price_gbp": market_price_gbp,
            "market_price_basis_used": market_price_basis,
            "expected_refund_cost_per_unit_gbp": _value_from_any(
                performance_row,
                ("expected_refund_cost_per_unit_gbp",),
                default="0",
            ),
            "refund_unit_rate_30d": _value_from_any(performance_row, ("refund_unit_rate_30d",), default="0"),
            "refund_unit_rate_90d": _value_from_any(performance_row, ("refund_unit_rate_90d",), default="0"),
            "refund_units_30d": _value_from_any(performance_row, ("refund_units_30d",), default="0"),
            "sales_units_30d": _value_from_any(performance_row, ("sales_units_30d",), default="0"),
            "refund_cost_basis": _value_from_any(performance_row, ("refund_cost_basis",)),
            "refund_proof_state": refund_proof_state or "not_yet_proven",
            "refund_sample_confidence": refund_sample_confidence,
            "profit_confidence": _value_from_any(performance_row, ("profit_confidence",)),
            "sales_truth_state": _value_from_any(performance_row, ("sales_truth_state",)),
            "stock_signal": _value_from_any(performance_row, ("stock_signal",)),
            "restock_business_ready": _value_from_any(performance_row, ("restock_business_ready",), default="no"),
            "restock_decision_state": _value_from_any(performance_row, ("restock_decision_state",)),
            "restock_missing_proof": _value_from_any(performance_row, ("restock_missing_proof",)),
            "missing_roi_reason": _value_from_any(performance_row, ("missing_roi_reason",)),
            "missing_roi_reason_detail": _value_from_any(performance_row, ("missing_roi_reason_detail",)),
            "roi_at_market_price_pct": roi_context,
            "source_inventory_asof": _value_from_any(inventory_row, ("last_updated_time",)),
            "source_velocity_asof": _value_from_any(velocity_row, ("asof_date",)),
            "source_performance_asof": _value_from_any(performance_row, ("asof_date",)),
            "source_offer_timestamp_utc": _value_from_any(offer_row, ("timestamp_utc",)),
            "source_notes": "|".join(sorted(set(note for note in notes if note))),
        }
        row.update(net_fee_context)
        row.update(token_cost_trust_context)
        row.update(inbound_cost_context)
        row.update(cost_context)
        row.update(backtest_context)
        if effective_cost_mode == "test":
            test_cost_row = _select_test_cost_row(
                test_cost_map_by_sku=test_cost_map_by_sku,
                test_cost_map_by_asin=test_cost_map_by_asin,
                sku_norm=sku_norm,
                asin_norm=asin_norm,
            )
            if test_cost_row is not None:
                test_pack = _num_or_none(test_cost_row.get("pack_size", ""))
                test_moq = _num_or_none(test_cost_row.get("moq", ""))
                if test_pack is not None and test_pack > 0:
                    row["supplier_pack_size"] = _num_to_text(test_pack, allow_blank=False)
                if test_moq is not None and test_moq > 0:
                    row["moq"] = _num_to_text(test_moq, allow_blank=False)

        row.update(_build_quantity_profile_fields(product_row=product_row, base_row=row))
        quantity_profile_row = sku_quantity_profile_map.get(sku_norm)
        if quantity_profile_row is not None:
            row["supplier_sku"] = _normalize_text(quantity_profile_row.get("supplier_sku", "")) or row.get("supplier_sku", "")
            row["amazon_pack_size"] = _positive_int_text(
                quantity_profile_row.get("amazon_pack_size", ""),
                default=row.get("amazon_pack_size", "1"),
            )
            row["sell_pack_qty"] = row["amazon_pack_size"]
            row["order_qty_mode"] = _normalize_order_qty_mode(quantity_profile_row.get("order_qty_mode", "")) or row.get("order_qty_mode", "")
            row["pack_conversion_note"] = _normalize_text(quantity_profile_row.get("pack_profile_note", "")) or row.get("pack_conversion_note", "")
            row["order_qty_unit_label"] = "Packs" if row["order_qty_mode"] == "sell_packs" else row.get("order_qty_unit_label", "Units")
        row.update(
            _build_pack_profile_fields(
                row=row,
                quantity_profile_row=quantity_profile_row,
                special_profile_row=special_order_profile_map.get(sku_norm),
                notes=notes,
            )
        )
        row.update(_build_profit_input_confidence(row, notes))
        row["source_notes"] = "|".join(sorted(set(note for note in notes if note)))
        if row["market_price_basis_used"] == "MISSING_MARKET_CONTEXT" and not row["source_notes"]:
            row["source_notes"] = "REDUCED_CONFIDENCE_MISSING_H_PRICE_CONTEXT"
        row.update(_build_coverage_fields(row))
        rows.append(row)

    out_df = _finalize_columns(pd.DataFrame(rows))
    out_path = root_path / get_o_output_contract("restock_source_view").rel_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_o_contract_df(root_path, "restock_source_view", out_df)
    print({"status": "success", "rows": len(out_df), "snapshot": str(out_path)})
    return out_df


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build O restock source view.")
    parser.add_argument(
        "--cost-mode",
        choices=("live", "test"),
        default=None,
        help=f"Override cost mode. Default uses env {TEST_COST_MODE_ENV}=test for test mode, otherwise live.",
    )
    parser.add_argument(
        "--asof-utc",
        default=None,
        help="Optional fixed asof_utc for deterministic runs.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_restock_source_view(
        asof_utc=args.asof_utc,
        cost_mode=args.cost_mode,
    )


if __name__ == "__main__":
    main()
