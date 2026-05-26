from __future__ import annotations

import re
from typing import Any

import pandas as pd


VALID_DECISION_BUCKETS = {
    "clear_breach_remove_from_clean_pass",
    "pack_size_or_quantity_breach",
    "pack_size_or_quantity_needs_user_guidance",
    "accessory_or_consumable_vs_device_breach",
    "same_brand_different_product_breach",
    "high_roi_identity_suspicion",
    "needs_user_guidance",
    "title_match_clear",
}

VALID_ACTIONS = {
    "remove_from_clean_pass",
    "manual_review",
    "allow_if_other_checks_pass",
}

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "black",
    "blue",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "new",
    "of",
    "on",
    "one",
    "or",
    "the",
    "to",
    "uk",
    "with",
}

ACCESSORY_TERMS = {
    "accessory",
    "adapter",
    "blade",
    "blades",
    "cartridge",
    "cartridges",
    "clearmax",
    "cover",
    "filter cartridge",
    "head",
    "heads",
    "poly",
    "refill",
    "refills",
    "replacement",
    "spare",
}

DEVICE_TERMS = {
    "appliance",
    "boombox",
    "console",
    "controller",
    "device",
    "external filter",
    "filter system",
    "machine",
    "printer",
    "radio",
    "shaver",
    "speaker",
    "system",
    "unit",
}

PACK_UNITS = (
    "pack",
    "packs",
    "pc",
    "pcs",
    "piece",
    "pieces",
    "capsule",
    "capsules",
    "tablet",
    "tablets",
    "sachet",
    "sachets",
    "can",
    "cans",
    "bottle",
    "bottles",
    "refill",
    "refills",
    "cartridge",
    "cartridges",
)

SIZE_UNITS = (
    "ml",
    "l",
    "litre",
    "litres",
    "g",
    "kg",
    "mm",
    "cm",
    "gb",
    "tb",
)


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def normalize_simple(value: object) -> str:
    text = normalize_text(value).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9.]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_number_token(value: str) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def infer_brand_from_supplier_title(supplier_title: str) -> str:
    title = normalize_text(supplier_title)
    if " - " in title:
        prefix = title.split(" - ", 1)[0].strip()
        if prefix:
            return prefix
    if "-" in title:
        prefix = title.split("-", 1)[0].strip()
        if prefix:
            return prefix
    tokens = title.split()
    return " ".join(tokens[:2]).strip() if tokens else ""


def to_float(value: object) -> float | None:
    text = normalize_text(value)
    if not text:
        return None
    text = text.replace(",", "").replace("£", "").replace("Â£", "").replace("%", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def first_float(row: pd.Series | dict[str, Any], fields: list[str]) -> tuple[float | None, str]:
    for field in fields:
        value = row.get(field, "")
        parsed = to_float(value)
        if parsed is not None:
            return parsed, field
    return None, ""


def extract_profit_likely(text: str) -> float | None:
    match = re.search(r"profit_likely_gbp\s*=\s*([0-9.,]+)", normalize_text(text), flags=re.IGNORECASE)
    if not match:
        return None
    return to_float(match.group(1))


def title_tokens(text: str) -> set[str]:
    out: set[str] = set()
    for token in re.findall(r"[a-z0-9]+", normalize_simple(text)):
        if len(token) < 2:
            continue
        if token in STOP_WORDS:
            continue
        if token in set(PACK_UNITS) | set(SIZE_UNITS):
            continue
        if token.isdigit():
            continue
        out.add(token)
    return out


def contains_term(text: str, terms: set[str]) -> bool:
    haystack = f" {normalize_simple(text)} "
    for term in terms:
        needle = f" {normalize_simple(term)} "
        if needle in haystack:
            return True
    return False


def extract_quantity_tokens(text: str) -> set[str]:
    normalized = normalize_simple(text)
    tokens: set[str] = set()
    unit_pattern = "|".join(re.escape(unit) for unit in PACK_UNITS)
    for match in re.finditer(rf"\b(\d+(?:\.\d+)?)\s*(?:{unit_pattern})\b", normalized):
        tokens.add(clean_number_token(match.group(1)))
    for match in re.finditer(r"\bpack\s+of\s+(\d+(?:\.\d+)?)\b", normalized):
        tokens.add(clean_number_token(match.group(1)))
    for match in re.finditer(r"\b(\d+(?:\.\d+)?)\s*x\b", normalized):
        tokens.add(clean_number_token(match.group(1)))
    return tokens


def extract_size_tokens(text: str) -> set[str]:
    normalized = normalize_simple(text)
    tokens: set[str] = set()
    unit_pattern = "|".join(re.escape(unit) for unit in SIZE_UNITS)
    for match in re.finditer(rf"\b(\d+(?:\.\d+)?)\s*({unit_pattern})\b", normalized):
        value = clean_number_token(match.group(1))
        unit = match.group(2)
        tokens.add(f"{value}{unit}")
    return tokens


def brand_mismatch(supplier_brand: str, amazon_brand: str, supplier_title: str, amazon_title: str) -> bool:
    left = normalize_simple(supplier_brand)
    right = normalize_simple(amazon_brand)
    if not left or not right:
        return False
    if left == right or left in right or right in left:
        return False
    supplier_lower = normalize_simple(supplier_title)
    amazon_lower = normalize_simple(amazon_title)
    if left and left in amazon_lower:
        return False
    if right and right in supplier_lower:
        return False
    return True


def profit_snapshot(row: pd.Series | dict[str, Any]) -> dict[str, Any]:
    unit_cost, unit_cost_source = first_float(row, ["unit_cost", "supplier_unit_cost", "cost"])
    profit_per_unit, profit_per_unit_source = first_float(
        row,
        [
            "corrected_profit_per_unit_gbp",
            "profit_per_unit_30d_gbp",
            "profit_per_unit_30d",
            "profit_per_unit",
        ],
    )
    expected_profit, expected_profit_source = first_float(
        row,
        [
            "corrected_expected_profit_next_30d_gbp",
            "expected_profit_next_30d_gbp",
            "estimated_monthly_profit_gbp",
            "estimated_monthly_profit",
            "review_priority_score",
        ],
    )
    if expected_profit is None:
        expected_profit = extract_profit_likely(str(row.get("why_data_summary", "")))
        expected_profit_source = "why_data_summary:profit_likely_gbp" if expected_profit is not None else expected_profit_source

    roi_value, roi_source = first_float(row, ["roi_check_value", "fallback_roi", "phase_profit_pct"])
    profit_on_cost_pct: float | None = None
    profit_on_cost_source = ""
    if unit_cost is not None and unit_cost > 0 and profit_per_unit is not None:
        profit_on_cost_pct = (profit_per_unit / unit_cost) * 100.0
        profit_on_cost_source = f"{profit_per_unit_source}/{unit_cost_source}"
    elif roi_value is not None:
        profit_on_cost_pct = roi_value
        profit_on_cost_source = roi_source

    high_roi = False
    high_roi_reasons: list[str] = []
    if profit_on_cost_pct is not None and profit_on_cost_pct >= 300.0:
        high_roi = True
        high_roi_reasons.append("profit_on_cost_pct_300_plus")
    if expected_profit is not None and expected_profit >= 1000.0 and profit_per_unit is not None and profit_per_unit >= 25.0:
        high_roi = True
        high_roi_reasons.append("expected_profit_1000_plus_and_profit_per_unit_25_plus")

    return {
        "unit_cost_gbp": unit_cost,
        "profit_per_unit_gbp": profit_per_unit,
        "expected_profit_gbp": expected_profit,
        "profit_on_cost_pct": profit_on_cost_pct,
        "profit_on_cost_source": profit_on_cost_source,
        "high_roi_flag": "1" if high_roi else "0",
        "high_roi_reasons": "|".join(high_roi_reasons),
    }


def classify_title_match(row: pd.Series | dict[str, Any]) -> dict[str, Any]:
    supplier_title = normalize_text(row.get("supplier_title", ""))
    amazon_title = normalize_text(row.get("amazon_title", row.get("title", "")))
    supplier_brand = normalize_text(row.get("supplier_brand", row.get("brand_supplier", "")))
    amazon_brand = normalize_text(row.get("amazon_brand", row.get("brand", "")))
    if not supplier_brand:
        supplier_brand = infer_brand_from_supplier_title(supplier_title)
    profit = profit_snapshot(row)

    reasons: list[str] = []
    evidence: list[str] = []

    if not supplier_title:
        reasons.append("missing_supplier_title")
    if not amazon_title:
        reasons.append("missing_amazon_title")
    if reasons:
        return {
            **profit,
            "supplier_title": supplier_title,
            "amazon_title": amazon_title,
            "supplier_brand": supplier_brand,
            "amazon_brand": amazon_brand,
            "title_overlap_ratio": "",
            "suspicious_title_flag": "1",
            "agent_decision_bucket": "needs_user_guidance",
            "title_match_action": "manual_review",
            "agent_confidence": "low",
            "agent_reason_code": "missing_title_evidence",
            "agent_evidence": "|".join(reasons),
            "quantity_alignment_status": "not_checked_missing_title",
            "pack_size_guidance": "Missing title evidence means the row needs user guidance or rescan, not a clean pass.",
        }

    supplier_tokens = title_tokens(supplier_title)
    amazon_tokens = title_tokens(amazon_title)
    common_tokens = supplier_tokens & amazon_tokens
    denominator = max(1, min(len(supplier_tokens), len(amazon_tokens)))
    overlap_ratio = len(common_tokens) / denominator
    low_overlap = overlap_ratio < 0.30

    supplier_quantities = extract_quantity_tokens(supplier_title)
    amazon_quantities = extract_quantity_tokens(amazon_title)
    quantity_mismatch = False
    quantity_alignment_status = "no_quantity_wording"
    pack_size_guidance = "No pack or quantity wording was detected in the title comparison."
    if supplier_quantities and amazon_quantities:
        quantity_mismatch = supplier_quantities.isdisjoint(amazon_quantities)
        if quantity_mismatch:
            quantity_alignment_status = "quantity_tokens_conflict"
            pack_size_guidance = "Supplier and Amazon titles show different pack or quantity numbers; treat as pack-size risk."
        else:
            quantity_alignment_status = "quantity_tokens_match"
            pack_size_guidance = "Supplier and Amazon titles show the same quantity number; do not flag pack-size risk from wording alone."
    elif supplier_quantities or amazon_quantities:
        quantity_mismatch = True
        quantity_alignment_status = "one_sided_quantity_wording"
        pack_size_guidance = "Only one title shows pack or quantity wording; treat as pack-size risk unless other evidence proves it is the same retail unit."

    supplier_sizes = extract_size_tokens(supplier_title)
    amazon_sizes = extract_size_tokens(amazon_title)
    size_mismatch = bool(supplier_sizes and amazon_sizes and supplier_sizes.isdisjoint(amazon_sizes))

    supplier_accessory = contains_term(supplier_title, ACCESSORY_TERMS)
    amazon_accessory = contains_term(amazon_title, ACCESSORY_TERMS)
    supplier_device = contains_term(supplier_title, DEVICE_TERMS)
    amazon_device = contains_term(amazon_title, DEVICE_TERMS)
    accessory_device_conflict = (supplier_accessory and amazon_device and not amazon_accessory) or (
        amazon_accessory and supplier_device and not supplier_accessory
    )

    brand_conflict = brand_mismatch(supplier_brand, amazon_brand, supplier_title, amazon_title)
    high_roi = profit["high_roi_flag"] == "1"

    if brand_conflict:
        reasons.append("brand_mismatch")
        evidence.append(f"supplier_brand={supplier_brand}")
        evidence.append(f"amazon_brand={amazon_brand}")
    if low_overlap:
        reasons.append("low_title_overlap")
        evidence.append(f"overlap_ratio={overlap_ratio:.2f}")
    if quantity_mismatch:
        reasons.append("pack_or_quantity_mismatch")
        evidence.append(f"supplier_quantities={','.join(sorted(supplier_quantities))}")
        evidence.append(f"amazon_quantities={','.join(sorted(amazon_quantities))}")
    elif quantity_alignment_status == "quantity_tokens_match":
        evidence.append(f"quantity_tokens_aligned={','.join(sorted(supplier_quantities))}")
    if size_mismatch:
        reasons.append("size_mismatch")
        evidence.append(f"supplier_sizes={','.join(sorted(supplier_sizes))}")
        evidence.append(f"amazon_sizes={','.join(sorted(amazon_sizes))}")
    if accessory_device_conflict:
        reasons.append("accessory_or_consumable_vs_device")
    if high_roi and reasons:
        reasons.append("high_roi_with_title_suspicion")
        evidence.append(f"profit_on_cost_pct={profit['profit_on_cost_pct']}")
        evidence.append(f"expected_profit_gbp={profit['expected_profit_gbp']}")

    if high_roi and reasons:
        bucket = "high_roi_identity_suspicion"
        action = "remove_from_clean_pass"
        confidence = "high"
        reason_code = "suspicious_title_high_roi_auto_fail"
    elif brand_conflict and (low_overlap or size_mismatch):
        bucket = "clear_breach_remove_from_clean_pass"
        action = "remove_from_clean_pass"
        confidence = "high"
        reason_code = "clear_brand_or_product_title_breach"
    elif quantity_mismatch:
        bucket = "pack_size_or_quantity_needs_user_guidance"
        action = "manual_review"
        confidence = "medium"
        reason_code = "pack_or_quantity_mismatch_needs_user_guidance"
    elif size_mismatch:
        bucket = "pack_size_or_quantity_needs_user_guidance"
        action = "manual_review"
        confidence = "medium"
        reason_code = "size_mismatch_needs_user_guidance"
    elif accessory_device_conflict:
        bucket = "needs_user_guidance"
        action = "manual_review"
        confidence = "medium"
        reason_code = "accessory_or_device_wording_needs_user_guidance"
    elif low_overlap:
        bucket = "needs_user_guidance"
        action = "manual_review"
        confidence = "medium"
        reason_code = "low_title_overlap_needs_user_guidance"
    else:
        bucket = "title_match_clear"
        action = "allow_if_other_checks_pass"
        confidence = "medium"
        reason_code = "supplier_and_amazon_titles_look_aligned"
        evidence.append(f"overlap_ratio={overlap_ratio:.2f}")

    suspicious = "1" if bucket != "title_match_clear" else "0"
    return {
        **profit,
        "supplier_title": supplier_title,
        "amazon_title": amazon_title,
        "supplier_brand": supplier_brand,
        "amazon_brand": amazon_brand,
        "title_overlap_ratio": f"{overlap_ratio:.4f}",
        "suspicious_title_flag": suspicious,
        "agent_decision_bucket": bucket,
        "title_match_action": action,
        "agent_confidence": confidence,
        "agent_reason_code": reason_code,
        "agent_evidence": "|".join(reasons + evidence),
        "quantity_alignment_status": quantity_alignment_status,
        "pack_size_guidance": pack_size_guidance,
    }
