from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BOOT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT))

from scripts.flows.O.O410_product_database_ui import load_product_db_operator_view
from scripts.flows.O._contract_io import (
    append_o_contract_row,
    o_contract_columns,
    read_o_contract_df,
    write_o_contract_df,
)
from scripts.flows.O._pack_rules import product_pack_fields_from_purchase_sold
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract


ALLOWED_SALE_STATUSES = {"active", "live", "snoozed", "discontinued", "dropped", "inactive"}
ALLOWED_ORDER_QTY_MODES = {"raw_units", "sell_packs", "bundles"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _truthy(value: object) -> bool:
    token = _normalize_text(value).lower()
    return token in {"1", "true", "yes", "y", "on"}


def _read_contract_df(root: Path, contract_name: str) -> pd.DataFrame:
    return read_o_contract_df(root, contract_name)


def _append_contract_row(root: Path, contract_name: str, row: dict[str, str]) -> dict[str, str]:
    return append_o_contract_row(root, contract_name, row)


def _write_contract_df(root: Path, contract_name: str, df: pd.DataFrame) -> None:
    write_o_contract_df(root, contract_name, df)


def _hold_identity_mask(df: pd.DataFrame, *, seller_sku: str, asin: str) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=bool, index=df.index)
    mask = pd.Series(False, index=df.index, dtype=bool)
    sku_key = _normalize_text(seller_sku).upper()
    asin_key = _normalize_text(asin).upper()
    if sku_key != "":
        mask = mask | df.get("seller_sku", "").map(lambda v: _normalize_text(v).upper() == sku_key)
    if asin_key != "":
        mask = mask | df.get("asin", "").map(lambda v: _normalize_text(v).upper() == asin_key)
    return mask


def _clear_product_db_edit_hold(root: Path, *, payload: dict[str, object]) -> None:
    normalized = _normalized_payload(payload)
    holds_df = _read_contract_df(root, "product_db_edit_holds")
    mask = _hold_identity_mask(
        holds_df,
        seller_sku=normalized.get("seller_sku", ""),
        asin=normalized.get("asin", ""),
    )
    if mask.any():
        _write_contract_df(root, "product_db_edit_holds", holds_df[~mask].copy())


def _validate_positive_int(field_name: str, value: object, errors: list[str], *, allow_blank: bool = True) -> None:
    text = _normalize_text(value)
    if text == "":
        if allow_blank:
            return
        errors.append(f"{field_name} is required")
        return
    try:
        number = float(text)
    except ValueError:
        errors.append(f"{field_name} must be numeric")
        return
    if number <= 0 or not number.is_integer():
        errors.append(f"{field_name} must be a positive whole number")


def _validate_numeric(field_name: str, value: object, errors: list[str], *, allow_blank: bool = True) -> None:
    text = _normalize_text(value)
    if text == "":
        if allow_blank:
            return
        errors.append(f"{field_name} is required")
        return
    try:
        float(text)
    except ValueError:
        errors.append(f"{field_name} must be numeric")


def prepare_product_db_edit_payload(payload: dict[str, object]) -> dict[str, object]:
    expanded = dict(payload)
    purchase_pack_size = _normalize_text(expanded.get("purchase_pack_size", ""))
    sold_pack_size = _normalize_text(expanded.get("sold_pack_size", ""))
    if purchase_pack_size == "" and sold_pack_size == "":
        return expanded

    purchase_pack_size = purchase_pack_size or _normalize_text(expanded.get("supplier_pack_size", ""))
    sold_pack_size = (
        sold_pack_size
        or _normalize_text(expanded.get("amazon_pack_size", ""))
        or _normalize_text(expanded.get("sell_pack_qty", ""))
    )
    expanded["supplier_pack_size"] = purchase_pack_size
    expanded["amazon_pack_size"] = sold_pack_size
    expanded["sell_pack_qty"] = sold_pack_size

    pack_fields = product_pack_fields_from_purchase_sold(
        purchase_pack_size=purchase_pack_size,
        sold_pack_size=sold_pack_size,
        supplier_case_qty=expanded.get("supplier_case_qty", ""),
        supplier_case_multiple=expanded.get("supplier_case_multiple", ""),
        valid_order_step=expanded.get("valid_order_step", ""),
        moq=expanded.get("moq", ""),
        order_qty_mode=expanded.get("order_qty_mode", ""),
        pack_conversion_note=expanded.get("pack_conversion_note", ""),
        source="product_db_edit_ui",
    )
    expanded.update(pack_fields)
    return expanded


def validate_product_db_edit_payload(payload: dict[str, object]) -> list[str]:
    payload = prepare_product_db_edit_payload(payload)
    errors: list[str] = []

    seller_sku = _normalize_text(payload.get("seller_sku", ""))
    sale_status = _normalize_text(payload.get("sale_status", "")).lower()
    supplier_code = _normalize_text(payload.get("supplier_code", ""))
    supplier_name = _normalize_text(payload.get("supplier_name", ""))
    order_qty_mode = _normalize_text(payload.get("order_qty_mode", "")).lower()

    if seller_sku == "":
        errors.append("seller_sku is required")
    if supplier_code == "":
        errors.append("supplier_code is required")
    if supplier_name == "":
        errors.append("supplier_name is required")
    if sale_status == "":
        errors.append("sale_status is required")
    elif sale_status not in ALLOWED_SALE_STATUSES:
        errors.append("sale_status is invalid")

    if order_qty_mode == "":
        errors.append("order_qty_mode is required")
    elif order_qty_mode not in ALLOWED_ORDER_QTY_MODES:
        errors.append("order_qty_mode is invalid")

    _validate_positive_int("supplier_pack_size", payload.get("supplier_pack_size", ""), errors, allow_blank=False)
    _validate_positive_int("amazon_pack_size", payload.get("amazon_pack_size", ""), errors, allow_blank=False)
    _validate_positive_int("supplier_case_qty", payload.get("supplier_case_qty", ""), errors, allow_blank=False)
    _validate_positive_int("valid_order_step", payload.get("valid_order_step", ""), errors, allow_blank=False)
    _validate_positive_int("moq", payload.get("moq", ""), errors, allow_blank=False)

    if order_qty_mode in {"sell_packs", "bundles"}:
        _validate_positive_int("sell_pack_qty", payload.get("sell_pack_qty", ""), errors, allow_blank=False)
    else:
        _validate_positive_int("sell_pack_qty", payload.get("sell_pack_qty", ""), errors, allow_blank=True)

    _validate_numeric("supplier_catalog_price", payload.get("supplier_catalog_price", ""), errors, allow_blank=True)
    _validate_numeric("last_purchase_price", payload.get("last_purchase_price", ""), errors, allow_blank=True)
    _validate_numeric("target_margin", payload.get("target_margin", ""), errors, allow_blank=True)
    _validate_numeric("vat_rate", payload.get("vat_rate", ""), errors, allow_blank=True)

    if _truthy(payload.get("supplier_case_multiple", "")) and _normalize_text(payload.get("supplier_case_qty", "")) == "":
        errors.append("supplier_case_qty is required when supplier_case_multiple is enabled")

    return errors


def _normalized_payload(payload: dict[str, object]) -> dict[str, str]:
    payload = prepare_product_db_edit_payload(payload)
    normalized = {key: _normalize_text(value) for key, value in payload.items()}
    normalized["sale_status"] = _normalize_text(payload.get("sale_status", "")).lower()
    normalized["order_qty_mode"] = _normalize_text(payload.get("order_qty_mode", "")).lower()
    normalized["supplier_case_multiple"] = "1" if _truthy(payload.get("supplier_case_multiple", "")) else "0"
    normalized["repack_required"] = "1" if _truthy(payload.get("repack_required", "")) else "0"
    normalized["bundle_required"] = "1" if _truthy(payload.get("bundle_required", "")) else "0"
    return normalized


def submit_product_db_edit_event(
    *,
    root: Path | None = None,
    payload: dict[str, object],
    actor: str = "operator_ui",
    source_reference: str = "o_ui_product_db_edit",
    edit_note: str = "",
) -> dict[str, str]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    normalized = _normalized_payload(payload)
    row = {
        "event_utc": _utc_now_iso(),
        "event_id": f"o-ui-product-edit-{uuid.uuid4().hex[:12]}",
        "seller_sku": normalized.get("seller_sku", ""),
        "asin": normalized.get("asin", ""),
        "actor": _normalize_text(actor),
        "source_reference": _normalize_text(source_reference) or "o_ui_product_db_edit",
        "edit_note": _normalize_text(edit_note),
        "sale_status": normalized.get("sale_status", ""),
        "supplier_code": normalized.get("supplier_code", ""),
        "supplier_name": normalized.get("supplier_name", ""),
        "supplier_sku": normalized.get("supplier_sku", ""),
        "barcode": normalized.get("barcode", ""),
        "supplier_pack_size": normalized.get("supplier_pack_size", ""),
        "amazon_pack_size": normalized.get("amazon_pack_size", ""),
        "order_qty_mode": normalized.get("order_qty_mode", ""),
        "sell_pack_qty": normalized.get("sell_pack_qty", ""),
        "supplier_case_qty": normalized.get("supplier_case_qty", ""),
        "supplier_case_multiple": normalized.get("supplier_case_multiple", ""),
        "valid_order_step": normalized.get("valid_order_step", ""),
        "repack_required": normalized.get("repack_required", ""),
        "bundle_required": normalized.get("bundle_required", ""),
        "pack_conversion_note": normalized.get("pack_conversion_note", ""),
        "moq": normalized.get("moq", ""),
        "supplier_catalog_price": normalized.get("supplier_catalog_price", ""),
        "last_purchase_price": normalized.get("last_purchase_price", ""),
        "target_margin": normalized.get("target_margin", ""),
        "vat_rate": normalized.get("vat_rate", ""),
        "notes": normalized.get("notes", ""),
    }
    return _append_contract_row(root_path, "product_db_edit_events", row)


def _write_product_db_edit_hold(
    *,
    root: Path,
    payload: dict[str, object],
    hold_reason: str,
    hold_note: str,
    actor: str,
    source_reference: str,
    edit_note: str,
) -> dict[str, str]:
    normalized = _normalized_payload(payload)
    hold_row = {
        "hold_utc": _utc_now_iso(),
        "event_utc": _utc_now_iso(),
        "event_id": f"o-ui-product-hold-{uuid.uuid4().hex[:12]}",
        "seller_sku": normalized.get("seller_sku", ""),
        "asin": normalized.get("asin", ""),
        "hold_reason": hold_reason,
        "hold_note": hold_note,
        "actor": _normalize_text(actor),
        "source_reference": _normalize_text(source_reference) or "o_ui_product_db_edit",
        "edit_note": _normalize_text(edit_note),
    }
    holds_df = _read_contract_df(root, "product_db_edit_holds")
    mask = _hold_identity_mask(
        holds_df,
        seller_sku=normalized.get("seller_sku", ""),
        asin=normalized.get("asin", ""),
    )
    remaining_df = holds_df[~mask].copy()
    ordered = o_contract_columns("product_db_edit_holds")
    normalized_row = {col: _normalize_text(hold_row.get(col, "")) for col in ordered}
    out_df = pd.concat([remaining_df, pd.DataFrame([normalized_row])], ignore_index=True)
    _write_contract_df(root, "product_db_edit_holds", out_df)
    return normalized_row


def submit_product_db_edit(
    *,
    root: Path | None = None,
    payload: dict[str, object],
    actor: str = "operator_ui",
    source_reference: str = "o_ui_product_db_edit",
    edit_note: str = "",
) -> tuple[bool, list[str], dict[str, str]]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    errors = validate_product_db_edit_payload(payload)
    if errors:
        hold = _write_product_db_edit_hold(
            root=root_path,
            payload=payload,
            hold_reason="validation_failed",
            hold_note="; ".join(errors),
            actor=actor,
            source_reference=source_reference,
            edit_note=edit_note,
        )
        return False, errors, hold
    event = submit_product_db_edit_event(
        root=root_path,
        payload=payload,
        actor=actor,
        source_reference=source_reference,
        edit_note=edit_note,
    )
    _clear_product_db_edit_hold(root_path, payload=payload)
    return True, [], event


def render_product_database_edit_ui(root: Path | None = None) -> None:
    import streamlit as st

    root_path = Path(root) if root is not None else get_o_path_contract().root
    view_df = load_product_db_operator_view(root=root_path)

    st.subheader("Product DB Edit")
    st.caption("Update fixed product and supplier values here. Derived values stay read-only.")

    if view_df.empty:
        st.info("No product database rows available.")
        return

    sku_options = sorted(view_df.get("seller_sku", pd.Series(dtype=str)).astype(str).tolist())
    selected_sku = st.selectbox("SKU", options=sku_options, key="o_product_edit_sku")
    row = view_df[view_df["seller_sku"].astype(str) == selected_sku].iloc[0].to_dict()

    with st.form("o_product_db_edit_form"):
        c1, c2 = st.columns(2)
        seller_sku = c1.text_input("seller_sku", value=_normalize_text(row.get("seller_sku", "")))
        asin = c2.text_input("asin", value=_normalize_text(row.get("asin", "")))
        sale_status = c1.selectbox(
            "sale_status",
            options=["active", "live", "snoozed", "discontinued", "dropped", "inactive"],
            index=max(["active", "live", "snoozed", "discontinued", "dropped", "inactive"].index(_normalize_text(row.get("sale_status", "")).lower()) if _normalize_text(row.get("sale_status", "")).lower() in {"active", "live", "snoozed", "discontinued", "dropped", "inactive"} else 0, 0),
        )
        supplier_code = c2.text_input("supplier_code", value=_normalize_text(row.get("supplier_code", "")))
        supplier_name = c1.text_input("supplier_name", value=_normalize_text(row.get("supplier_name", "")))
        supplier_sku = c2.text_input("supplier_sku", value=_normalize_text(row.get("supplier_sku", "")))
        barcode = c1.text_input("barcode", value=_normalize_text(row.get("barcode", "")))

        st.markdown("**Pack Rules**")
        p1, p2, p3 = st.columns(3)
        purchase_pack_size = p1.text_input("Purchase pack", value=_normalize_text(row.get("supplier_pack_size", "")) or "1")
        sold_pack_size = p2.text_input(
            "Sold pack",
            value=_normalize_text(row.get("amazon_pack_size", "")) or _normalize_text(row.get("sell_pack_qty", "")) or "1",
        )
        moq = p3.text_input("MOQ", value=_normalize_text(row.get("moq", "")) or "1")
        supplier_case_qty = p1.text_input("Case qty", value=_normalize_text(row.get("supplier_case_qty", "")))
        valid_order_step = p2.text_input("Order step", value=_normalize_text(row.get("valid_order_step", "")))
        pack_conversion_note = p3.text_input("Pack note", value=_normalize_text(row.get("pack_conversion_note", "")))

        st.markdown("**Commercial**")
        q1, q2, q3, q4 = st.columns(4)
        supplier_catalog_price = q1.text_input("supplier_catalog_price", value=_normalize_text(row.get("supplier_catalog_price", "")))
        last_purchase_price = q2.text_input("last_purchase_price", value=_normalize_text(row.get("last_purchase_price", "")))
        target_margin = q3.text_input("target_margin", value=_normalize_text(row.get("target_margin", "")))
        vat_rate = q4.text_input("vat_rate", value=_normalize_text(row.get("vat_rate", "")))
        notes = st.text_input("notes", value=_normalize_text(row.get("notes", "")))
        edit_note = st.text_input("edit_note", value="")

        submitted = st.form_submit_button("Submit Product DB Edit")

    if not submitted:
        st.caption("Read-only context: Stock, Ordered, Velocity, and ROI come from live overlays.")
        return

    payload = {
        "seller_sku": seller_sku,
        "asin": asin,
        "sale_status": sale_status,
        "supplier_code": supplier_code,
        "supplier_name": supplier_name,
        "supplier_sku": supplier_sku,
        "barcode": barcode,
        "purchase_pack_size": purchase_pack_size,
        "sold_pack_size": sold_pack_size,
        "supplier_case_qty": supplier_case_qty,
        "valid_order_step": valid_order_step,
        "pack_conversion_note": pack_conversion_note,
        "moq": moq,
        "supplier_catalog_price": supplier_catalog_price,
        "last_purchase_price": last_purchase_price,
        "target_margin": target_margin,
        "vat_rate": vat_rate,
        "notes": notes,
    }
    ok, errors, out_row = submit_product_db_edit(
        root=root_path,
        payload=payload,
        actor="operator_ui",
        source_reference="o_ui_product_db_edit",
        edit_note=edit_note,
    )
    if ok:
        st.info(f"Edit submitted for {seller_sku}. Event: {out_row['event_id']}")
    else:
        st.info(f"Edit held for {seller_sku}. Hold: {out_row['event_id']}")
        st.caption(" ; ".join(errors))


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="Product DB Edit", layout="wide")
    st.title("Product DB Edit")
    render_product_database_edit_ui()


if __name__ == "__main__":
    main()
