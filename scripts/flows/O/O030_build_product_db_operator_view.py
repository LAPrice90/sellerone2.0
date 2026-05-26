from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.core.storage.product_db_contract import (
    load_product_db_for_validation,
    load_product_db_products_from_sqlite,
    validate_product_db_dataframe,
)
from scripts.core.storage.config import StorageConfig
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract
from scripts.flows.O._schemas import get_o_output_contract
from scripts.flows.O._source_contracts import get_phase1_source_contracts


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _truthy(value: object) -> bool:
    token = _normalize_text(value).lower()
    return token in {"1", "true", "yes", "y", "on"}


def _read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _resolve_sqlite_path(root: Path) -> Path:
    configured = StorageConfig.from_env().sqlite_path
    return configured if configured.is_absolute() else root / configured


def _load_product_db_authority(root: Path, product_path: Path) -> tuple[pd.DataFrame, list[str], Path, str, bool]:
    sqlite_path = _resolve_sqlite_path(root)
    sql_df = load_product_db_products_from_sqlite(sqlite_path)
    if not sql_df.empty:
        return sql_df, list(sql_df.columns), sqlite_path, "sql_product_db_products", True
    if product_path.exists():
        product_df, raw_headers = load_product_db_for_validation(product_path)
        return product_df, raw_headers, product_path, "product_db_preview_csv", True
    return pd.DataFrame(), [], product_path, "missing_product_db_source", False


def _write_product_db_source_health(
    root: Path,
    *,
    product_df: pd.DataFrame,
    raw_headers: list[str],
    source_path: Path,
    source_label: str,
    source_exists: bool,
    observed_utc: str,
) -> pd.DataFrame:
    if not source_exists:
        rows = [
            {
                "check": "product_db_source_exists",
                "status": "fail",
                "value": "0",
                "notes": "Product DB source missing",
                "observed_utc": observed_utc,
                "source_path": str(source_path),
            }
        ]
        out = pd.DataFrame(rows)
        return write_o_contract_df(root, "product_db_source_health", out)

    try:
        validation = validate_product_db_dataframe(
            product_df,
            raw_headers=raw_headers,
            source_path=str(source_path),
            observed_utc=observed_utc,
        )
        rows = [
            {
                "check": "product_db_source_exists",
                "status": "ok",
                "value": "1",
                "notes": f"{source_label} present",
                "observed_utc": observed_utc,
                "source_path": str(source_path),
            },
            *validation.checks,
        ]
    except Exception as exc:
        rows = [
            {
                "check": "product_db_source_readable",
                "status": "fail",
                "value": "0",
                "notes": f"{type(exc).__name__}: {exc}",
                "observed_utc": observed_utc,
                "source_path": str(source_path),
            }
        ]
    out = pd.DataFrame(rows)
    return write_o_contract_df(root, "product_db_source_health", out)


def _num_or_none(value: object) -> float | None:
    raw = _normalize_text(value).replace(",", "")
    if raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _num_text(value: float | None, *, allow_blank: bool = True) -> str:
    if value is None:
        return "" if allow_blank else "0"
    if value.is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _positive_int_text(value: object, *, default: str = "") -> str:
    number = _num_or_none(value)
    if number is None or number <= 0 or not number.is_integer():
        return default
    return str(int(number))


def _first_non_blank(*values: object, default: str = "") -> str:
    for value in values:
        text = _normalize_text(value)
        if text != "":
            return text
    return default


def _align_to_contract(df: pd.DataFrame, contract_name: str) -> pd.DataFrame:
    contract = get_o_output_contract(contract_name)
    ordered_columns = [*contract.required_columns, *contract.optional_columns]
    out = df.copy()
    for col in ordered_columns:
        if col not in out.columns:
            out[col] = ""
    return out[ordered_columns]


def _map_by_sku(df: pd.DataFrame, sku_column: str) -> dict[str, pd.Series]:
    if df.empty or sku_column not in df.columns:
        return {}
    work = df.copy()
    work["_sku_key"] = work[sku_column].map(_normalize_key)
    work = work[work["_sku_key"] != ""].copy()
    if work.empty:
        return {}
    work = work.drop_duplicates(subset=["_sku_key"], keep="first").set_index("_sku_key")
    return {idx: work.loc[idx] for idx in work.index}


def _sum_ordered_open_by_sku(ordered_df: pd.DataFrame) -> dict[str, str]:
    if ordered_df.empty or "seller_sku" not in ordered_df.columns:
        return {}
    work = ordered_df.copy()
    if "remaining_open_qty" not in work.columns:
        work["remaining_open_qty"] = work.get("ordered_qty", "")
    work["_sku_key"] = work["seller_sku"].map(_normalize_key)
    work = work[work["_sku_key"] != ""].copy()
    if work.empty:
        return {}
    work["_open_qty_num"] = work["remaining_open_qty"].map(_num_or_none).fillna(0.0)
    grouped = work.groupby("_sku_key", sort=False)["_open_qty_num"].sum()
    return {sku: _num_text(total, allow_blank=False) for sku, total in grouped.items()}


def _latest_ordered_asof_by_sku(ordered_df: pd.DataFrame) -> dict[str, str]:
    if ordered_df.empty or "seller_sku" not in ordered_df.columns:
        return {}
    work = ordered_df.copy()
    work["_sku_key"] = work["seller_sku"].map(_normalize_key)
    work = work[work["_sku_key"] != ""].copy()
    if work.empty:
        return {}
    if "asof_utc" not in work.columns:
        work["asof_utc"] = ""
    work["_asof_sort"] = pd.to_datetime(work["asof_utc"], errors="coerce", utc=True)
    work = work.sort_values(by=["_sku_key", "_asof_sort"], ascending=[True, False], kind="stable")
    work = work.drop_duplicates(subset=["_sku_key"], keep="first")
    return {
        _normalize_text(row.get("_sku_key", "")): _normalize_text(row.get("asof_utc", ""))
        for _, row in work.iterrows()
    }


def _normalize_order_qty_mode(value: object) -> str:
    token = _normalize_text(value).lower()
    if token in {"raw_units", "sell_packs", "bundles"}:
        return token
    return ""


def _derive_pack_fields(row: pd.Series) -> dict[str, str]:
    supplier_pack_size = _positive_int_text(row.get("supplier_pack_size", ""), default="1")
    amazon_pack_size = _positive_int_text(row.get("amazon_pack_size", ""), default=supplier_pack_size or "1")

    order_qty_mode = _normalize_order_qty_mode(row.get("order_qty_mode", ""))
    if order_qty_mode == "":
        if _truthy(row.get("bundle_required", "")):
            order_qty_mode = "bundles"
        elif _truthy(row.get("repack_required", "")):
            order_qty_mode = "sell_packs"
        else:
            order_qty_mode = "raw_units"

    sell_pack_qty = _positive_int_text(row.get("sell_pack_qty", ""), default=amazon_pack_size or "1")
    supplier_case_qty = _positive_int_text(row.get("supplier_case_qty", ""), default=supplier_pack_size or "1")

    supplier_case_multiple_raw = _normalize_text(row.get("supplier_case_multiple", ""))
    if supplier_case_multiple_raw == "":
        supplier_case_multiple = "1" if (order_qty_mode == "raw_units" and supplier_case_qty not in {"", "1"}) else "0"
    else:
        supplier_case_multiple = "1" if _truthy(supplier_case_multiple_raw) else "0"

    valid_order_step = _positive_int_text(row.get("valid_order_step", ""))
    if valid_order_step == "":
        if supplier_case_multiple == "1" and supplier_case_qty not in {"", "1"}:
            valid_order_step = supplier_case_qty
        else:
            valid_order_step = _positive_int_text(row.get("moq", ""), default="1")

    pack_note = _normalize_text(row.get("pack_conversion_note", ""))

    if order_qty_mode == "bundles":
        pack_profile = f"Bundle {amazon_pack_size}"
    elif order_qty_mode == "sell_packs":
        pack_profile = f"Pack {sell_pack_qty}"
    elif supplier_case_multiple == "1" and supplier_case_qty not in {"", "1"}:
        pack_profile = f"Case {supplier_case_qty}"
    else:
        pack_profile = "Unit"

    if supplier_case_qty not in {"", "1"} and f"Case {supplier_case_qty}" not in pack_profile:
        pack_profile = f"{pack_profile} | Case {supplier_case_qty}"
    if valid_order_step not in {"", "1"} and f"Step {valid_order_step}" not in pack_profile:
        pack_profile = f"{pack_profile} | Step {valid_order_step}"

    return {
        "supplier_pack_size": supplier_pack_size,
        "amazon_pack_size": amazon_pack_size,
        "order_qty_mode": order_qty_mode,
        "sell_pack_qty": sell_pack_qty,
        "supplier_case_qty": supplier_case_qty,
        "supplier_case_multiple": supplier_case_multiple,
        "valid_order_step": valid_order_step,
        "pack_conversion_note": pack_note,
        "pack_profile_label": pack_profile,
    }


def _normalize_sale_status(value: object) -> str:
    token = _normalize_text(value).lower()
    if token in {"active", "live", "enabled"}:
        return "live"
    if token in {"dropped", "drop"} or "drop" in token:
        return "dropped"
    if token in {"discontinued", "inactive", "archived"} or "discontinu" in token:
        return "discontinued"
    return "live"


def _derive_operational_status(*, sale_status: str, queue_status: str) -> tuple[str, str]:
    queue_token = _normalize_text(queue_status).lower()
    if queue_token == "snoozed":
        return "snoozed", "queue_snoozed"
    sale_token = _normalize_sale_status(sale_status)
    if sale_token == "dropped":
        return "dropped", "sale_status_dropped"
    if sale_token == "discontinued":
        return "discontinued", "sale_status_discontinued"
    return "live", "sale_status_live"


def _build_data_issue_flags(*, row: dict[str, str], pack_fields: dict[str, str]) -> str:
    flags: list[str] = []

    if _normalize_text(row.get("supplier_code", "")) == "" or _normalize_text(row.get("supplier_name", "")) == "":
        flags.append("missing_supplier")

    supplier_price = _num_or_none(row.get("supplier_catalog_price", ""))
    last_purchase = _num_or_none(row.get("last_purchase_price", ""))
    if (supplier_price is None or supplier_price <= 0) and (last_purchase is None or last_purchase <= 0):
        flags.append("missing_cost")

    if _normalize_text(row.get("vat_rate", "")) == "":
        flags.append("missing_vat")

    if pack_fields["order_qty_mode"] in {"sell_packs", "bundles"} and _num_or_none(pack_fields["sell_pack_qty"]) is None:
        flags.append("missing_sell_pack_qty")
    if _num_or_none(pack_fields["supplier_case_qty"]) is None:
        flags.append("missing_supplier_case_qty")
    if _num_or_none(pack_fields["valid_order_step"]) is None:
        flags.append("missing_valid_order_step")

    return "|".join(flags)


def build_product_db_operator_view(root: Path | None = None, *, asof_utc: str | None = None) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)

    now_utc = asof_utc or _utc_now_iso()
    source_contracts = get_phase1_source_contracts()

    product_path = root_path / source_contracts["product_db_preview"].source_path
    product_df, product_headers, product_source_path, product_source_label, product_source_exists = _load_product_db_authority(
        root_path,
        product_path,
    )
    _write_product_db_source_health(
        root_path,
        product_df=product_df,
        raw_headers=product_headers,
        source_path=product_source_path,
        source_label=product_source_label,
        source_exists=product_source_exists,
        observed_utc=now_utc,
    )
    queue_df = read_o_contract_df(root_path, "restock_review_queue")
    ordered_df = read_o_contract_df(root_path, "ordered_stock_state")
    velocity_df = _read_csv_safe(root_path / source_contracts["sku_sales_velocity"].source_path)
    performance_df = _read_csv_safe(root_path / source_contracts["sku_performance_summary"].source_path)

    out_path = root_path / get_o_output_contract("product_db_operator_view").rel_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if product_df.empty:
        empty = _align_to_contract(pd.DataFrame(), "product_db_operator_view")
        write_o_contract_df(root_path, "product_db_operator_view", empty)
        print({"status": "success", "rows": 0, "snapshot": str(out_path), "notes": "product_db_preview missing or empty"})
        return empty

    product_work = product_df.copy()
    if "seller_sku" not in product_work.columns:
        empty = _align_to_contract(pd.DataFrame(), "product_db_operator_view")
        write_o_contract_df(root_path, "product_db_operator_view", empty)
        print({"status": "success", "rows": 0, "snapshot": str(out_path), "notes": "seller_sku missing in product_db_preview"})
        return empty
    product_work["_sku_key"] = product_work["seller_sku"].map(_normalize_key)
    product_work = product_work[product_work["_sku_key"] != ""].copy()
    product_work = product_work.drop_duplicates(subset=["_sku_key"], keep="first")

    queue_map = _map_by_sku(queue_df, "seller_sku")
    velocity_map = _map_by_sku(velocity_df, "sku")
    performance_map = _map_by_sku(performance_df, "sku")
    ordered_open_by_sku = _sum_ordered_open_by_sku(ordered_df)
    ordered_asof_by_sku = _latest_ordered_asof_by_sku(ordered_df)

    rows: list[dict[str, str]] = []
    for _, product_row in product_work.iterrows():
        sku = _normalize_text(product_row.get("seller_sku", ""))
        sku_key = _normalize_key(sku)
        queue_row = queue_map.get(sku_key)
        velocity_row = velocity_map.get(sku_key)
        perf_row = performance_map.get(sku_key)

        sale_status = _normalize_text(product_row.get("sale_status", ""))
        queue_status = _normalize_text(queue_row.get("queue_status", "") if queue_row is not None else "")
        operational_status, status_reason = _derive_operational_status(
            sale_status=sale_status,
            queue_status=queue_status,
        )
        pack_fields = _derive_pack_fields(product_row)

        stock_available = _first_non_blank(
            product_row.get("stock_available", ""),
            product_row.get("available", ""),
            velocity_row.get("available", "") if velocity_row is not None else "",
            default="0",
        )
        stock_total = _first_non_blank(
            product_row.get("stock_total", ""),
            product_row.get("total_quantity", ""),
            velocity_row.get("total_quantity", "") if velocity_row is not None else "",
            default=stock_available or "0",
        )
        velocity_30d = _first_non_blank(
            velocity_row.get("v30", "") if velocity_row is not None else "",
            product_row.get("velocity_30d", ""),
            default="0",
        )

        days_cover = _first_non_blank(queue_row.get("days_cover_available_only", "") if queue_row is not None else "")
        if days_cover == "":
            stock_num = _num_or_none(stock_available) or 0.0
            velocity_num = _num_or_none(velocity_30d) or 0.0
            if velocity_num > 0:
                days_cover = _num_text(stock_num / velocity_num)
            else:
                days_cover = ""

        roi_snapshot = _first_non_blank(
            perf_row.get("roi_at_our_price_pct", "") if perf_row is not None else "",
            perf_row.get("roi_at_buy_box_price_pct", "") if perf_row is not None else "",
            queue_row.get("expected_forward_roi_pct", "") if queue_row is not None else "",
            default="",
        )

        merged_row: dict[str, str] = {
            "asof_utc": now_utc,
            "seller_sku": sku,
            "asin": _first_non_blank(product_row.get("asin", ""), queue_row.get("asin", "") if queue_row is not None else ""),
            "title": _first_non_blank(product_row.get("title", ""), queue_row.get("title", "") if queue_row is not None else ""),
            "main_image": _first_non_blank(product_row.get("main_image", ""), queue_row.get("main_image", "") if queue_row is not None else ""),
            "supplier_code": _first_non_blank(product_row.get("supplier_code", ""), queue_row.get("supplier_code", "") if queue_row is not None else ""),
            "supplier_name": _first_non_blank(product_row.get("supplier_name", ""), queue_row.get("supplier_name", "") if queue_row is not None else ""),
            "supplier_sku": _first_non_blank(product_row.get("supplier_sku", ""), product_row.get("supply_code", "")),
            "barcode": _first_non_blank(product_row.get("barcode", ""), product_row.get("ean", ""), product_row.get("upc", "")),
            "sale_status": sale_status,
            "queue_status": queue_status,
            "operational_status": operational_status,
            "status_reason": status_reason,
            "supplier_pack_size": pack_fields["supplier_pack_size"],
            "amazon_pack_size": pack_fields["amazon_pack_size"],
            "order_qty_mode": pack_fields["order_qty_mode"],
            "sell_pack_qty": pack_fields["sell_pack_qty"],
            "supplier_case_qty": pack_fields["supplier_case_qty"],
            "supplier_case_multiple": pack_fields["supplier_case_multiple"],
            "valid_order_step": pack_fields["valid_order_step"],
            "pack_conversion_note": pack_fields["pack_conversion_note"],
            "moq": _positive_int_text(product_row.get("moq", ""), default="1"),
            "supplier_catalog_price": _normalize_text(product_row.get("supplier_catalog_price", "")),
            "last_purchase_price": _normalize_text(product_row.get("last_purchase_price", "")),
            "vat_rate": _normalize_text(product_row.get("vat_rate", "")),
            "stock_available": _normalize_text(stock_available) or "0",
            "stock_total": _normalize_text(stock_total) or "0",
            "ordered_open_qty": ordered_open_by_sku.get(sku_key, "0"),
            "velocity_30d": _normalize_text(velocity_30d) or "0",
            "days_cover": _normalize_text(days_cover),
            "roi_snapshot_pct": _normalize_text(roi_snapshot),
            "data_issue_flags": "",
            "target_margin": _normalize_text(product_row.get("target_margin", "")),
            "notes": _normalize_text(product_row.get("notes", "")),
            "recommendation_status": _normalize_text(queue_row.get("recommendation_status", "") if queue_row is not None else ""),
            "suggested_qty": _normalize_text(queue_row.get("suggested_qty", "") if queue_row is not None else ""),
            "suggested_unit_cost_gbp": _normalize_text(queue_row.get("suggested_unit_cost_gbp", "") if queue_row is not None else ""),
            "suggested_market_price_gbp": _normalize_text(queue_row.get("suggested_market_price_gbp", "") if queue_row is not None else ""),
            "expected_forward_roi_pct": _normalize_text(queue_row.get("expected_forward_roi_pct", "") if queue_row is not None else ""),
            "days_cover_available_only": _normalize_text(queue_row.get("days_cover_available_only", "") if queue_row is not None else ""),
            "snooze_until_utc": _normalize_text(queue_row.get("snooze_until_utc", "") if queue_row is not None else ""),
            "current_token_cost_gbp": _normalize_text(perf_row.get("current_token_cost_gbp", "") if perf_row is not None else ""),
            "expected_refund_cost_per_unit_gbp": _normalize_text(perf_row.get("expected_refund_cost_per_unit_gbp", "") if perf_row is not None else ""),
            "roi_at_buy_box_price_pct": _normalize_text(perf_row.get("roi_at_buy_box_price_pct", "") if perf_row is not None else ""),
            "roi_at_our_price_pct": _normalize_text(perf_row.get("roi_at_our_price_pct", "") if perf_row is not None else ""),
            "live_listing_price": _normalize_text(product_row.get("live_listing_price", "")),
            "last_sold_price": _normalize_text(product_row.get("last_sold_price", "")),
            "pack_profile_label": pack_fields["pack_profile_label"],
            "source_product_db_asof": _first_non_blank(
                product_row.get("last_updated_A003", ""),
                product_row.get("last_updated", ""),
                product_row.get("last_updated_A001", ""),
            ),
            "source_queue_asof": _normalize_text(queue_row.get("queue_utc", "") if queue_row is not None else ""),
            "source_ordered_asof": ordered_asof_by_sku.get(sku_key, ""),
            "source_velocity_asof": _normalize_text(velocity_row.get("asof_date", "") if velocity_row is not None else ""),
            "source_performance_asof": _normalize_text(perf_row.get("asof_date", "") if perf_row is not None else ""),
        }
        merged_row["data_issue_flags"] = _build_data_issue_flags(row=merged_row, pack_fields=pack_fields)
        rows.append(merged_row)

    out_df = pd.DataFrame(rows)
    if not out_df.empty:
        out_df = out_df.sort_values(by=["supplier_name", "seller_sku"], ascending=[True, True], kind="stable")
    out_df = _align_to_contract(out_df, "product_db_operator_view")
    write_o_contract_df(root_path, "product_db_operator_view", out_df)
    print({"status": "success", "rows": int(len(out_df.index)), "snapshot": str(out_path)})
    return out_df


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build O product database operator view snapshot.")
    parser.add_argument("--root", default="", help="Optional root path override.")
    parser.add_argument("--asof-utc", default="", help="Optional asof UTC override.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    root = Path(args.root) if _normalize_text(args.root) else None
    asof = _normalize_text(args.asof_utc) or None
    build_product_db_operator_view(root=root, asof_utc=asof)


if __name__ == "__main__":
    main()
