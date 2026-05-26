from __future__ import annotations


def normalize_text(value: object) -> str:
    text = str(value or "").strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def positive_int_text(value: object, *, default: str = "") -> str:
    text = normalize_text(value).replace(",", "")
    if text == "":
        return default
    try:
        parsed = int(float(text))
    except Exception:
        return default
    if parsed <= 0:
        return default
    try:
        if float(text) != parsed:
            return default
    except Exception:
        return default
    return str(parsed)


def flag_text(value: object) -> str:
    token = normalize_text(value).lower()
    return "1" if token in {"1", "true", "yes", "y", "on"} else "0"


def normalize_order_qty_mode(value: object) -> str:
    token = normalize_text(value).lower()
    if token in {"raw_units", "sell_packs", "bundles"}:
        return token
    return ""


def product_pack_fields_from_purchase_sold(
    *,
    purchase_pack_size: object,
    sold_pack_size: object,
    supplier_case_qty: object = "",
    supplier_case_multiple: object = "",
    valid_order_step: object = "",
    moq: object = "",
    order_qty_mode: object = "",
    pack_conversion_note: object = "",
    source: str = "",
) -> dict[str, str]:
    purchase = positive_int_text(purchase_pack_size)
    sold = positive_int_text(sold_pack_size)
    if not purchase or not sold:
        return {}

    case_qty = positive_int_text(supplier_case_qty, default=purchase)
    moq_text = positive_int_text(moq, default="1")
    step = positive_int_text(valid_order_step)
    if not step:
        step = case_qty if case_qty not in {"", "1"} else moq_text

    mode = normalize_order_qty_mode(order_qty_mode)
    if not mode:
        mode = "sell_packs" if sold not in {"", "1"} else "raw_units"

    case_multiple_raw = normalize_text(supplier_case_multiple)
    if case_multiple_raw:
        case_multiple = flag_text(case_multiple_raw)
    else:
        case_multiple = "1" if case_qty not in {"", "1"} else "0"

    note = normalize_text(pack_conversion_note)
    if not note:
        note_parts = [
            f"purchase_pack_size={purchase}",
            f"sold_pack_size={sold}",
        ]
        if source:
            note_parts.append(f"source={source}")
        note = "; ".join(note_parts)

    return {
        "supplier_pack_size": purchase,
        "amazon_pack_size": sold,
        "order_qty_mode": mode,
        "sell_pack_qty": sold,
        "supplier_case_qty": case_qty,
        "supplier_case_multiple": case_multiple,
        "valid_order_step": step,
        "repack_required": "1" if purchase != sold else "0",
        "bundle_required": "1" if sold not in {"", "1"} else "0",
        "pack_conversion_note": note,
        "moq": moq_text,
    }
