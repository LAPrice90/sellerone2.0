from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._title_match_agent import (
    VALID_ACTIONS as SHARED_VALID_ACTIONS,
    VALID_DECISION_BUCKETS as SHARED_VALID_DECISION_BUCKETS,
    classify_title_match as shared_classify_title_match,
)


DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"
DEFAULT_PASS_REVIEW_PATH = DEFAULT_OUTPUT_DIR / "f_live_price_file_pass_review_latest.csv"
DEFAULT_NEAR_MISS_REVIEW_PATH = DEFAULT_OUTPUT_DIR / "f_live_price_file_near_miss_review_latest.csv"
DEFAULT_SUPPLIER_INBOX_DIR = ROOT / "out" / "systems" / "F" / "inbox" / "suppliers"
DEFAULT_PLAN_DIR = ROOT / "plans" / "active" / "f-new-product-review-fail-automation-v1"
DEFAULT_SAMPLE_COLLECTION_PATH = DEFAULT_PLAN_DIR / "TITLE_MATCH_AGENT_SAMPLE_COLLECTION.csv"

DEFAULT_BACKLOG_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "f_title_match_agent_backlog_latest.csv"
DEFAULT_DECISION_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "f_title_match_agent_decisions_latest.csv"
DEFAULT_HEALTH_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "f_title_match_agent_health_latest.csv"
DEFAULT_SUMMARY_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "f_title_match_agent_summary_latest.md"
DEFAULT_SAMPLE_CALIBRATION_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "f_title_match_agent_sample_calibration_latest.csv"

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


@dataclass(frozen=True)
class TitleMatchAgentResult:
    backlog_df: pd.DataFrame
    decision_df: pd.DataFrame
    health_df: pd.DataFrame
    sample_calibration_df: pd.DataFrame
    report: dict[str, Any]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _timestamp_for_file(observed_utc: str) -> str:
    return observed_utc.replace("-", "").replace(":", "").replace("Z", "Z")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _normalize_simple(value: object) -> str:
    text = _normalize_text(value).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9.]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _clean_number_token(value: str) -> str:
    text = _normalize_text(value)
    if not text:
        return ""
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _infer_brand_from_supplier_title(supplier_title: str) -> str:
    title = _normalize_text(supplier_title)
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


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _to_float(value: object) -> float | None:
    text = _normalize_text(value)
    if not text:
        return None
    text = text.replace(",", "").replace("£", "").replace("%", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _first_float(row: pd.Series | dict[str, Any], fields: list[str]) -> tuple[float | None, str]:
    for field in fields:
        value = row.get(field, "")
        parsed = _to_float(value)
        if parsed is not None:
            return parsed, field
    return None, ""


def _extract_profit_likely(text: str) -> float | None:
    match = re.search(r"profit_likely_gbp\s*=\s*([0-9.,]+)", _normalize_text(text), flags=re.IGNORECASE)
    if not match:
        return None
    return _to_float(match.group(1))


def _tokens(text: str) -> set[str]:
    out: set[str] = set()
    for token in re.findall(r"[a-z0-9]+", _normalize_simple(text)):
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


def _contains_term(text: str, terms: set[str]) -> bool:
    haystack = f" {_normalize_simple(text)} "
    for term in terms:
        needle = f" {_normalize_simple(term)} "
        if needle in haystack:
            return True
    return False


def _extract_quantity_tokens(text: str) -> set[str]:
    normalized = _normalize_simple(text)
    tokens: set[str] = set()
    unit_pattern = "|".join(re.escape(unit) for unit in PACK_UNITS)
    for match in re.finditer(rf"\b(\d+(?:\.\d+)?)\s*(?:{unit_pattern})\b", normalized):
        tokens.add(_clean_number_token(match.group(1)))
    for match in re.finditer(r"\bpack\s+of\s+(\d+(?:\.\d+)?)\b", normalized):
        tokens.add(_clean_number_token(match.group(1)))
    for match in re.finditer(r"\b(\d+(?:\.\d+)?)\s*x\b", normalized):
        tokens.add(_clean_number_token(match.group(1)))
    return tokens


def _extract_size_tokens(text: str) -> set[str]:
    normalized = _normalize_simple(text)
    tokens: set[str] = set()
    unit_pattern = "|".join(re.escape(unit) for unit in SIZE_UNITS)
    for match in re.finditer(rf"\b(\d+(?:\.\d+)?)\s*({unit_pattern})\b", normalized):
        value = _clean_number_token(match.group(1))
        unit = match.group(2)
        tokens.add(f"{value}{unit}")
    return tokens


def _brand_mismatch(supplier_brand: str, amazon_brand: str, supplier_title: str, amazon_title: str) -> bool:
    left = _normalize_simple(supplier_brand)
    right = _normalize_simple(amazon_brand)
    if not left or not right:
        return False
    if left == right or left in right or right in left:
        return False
    supplier_lower = _normalize_simple(supplier_title)
    amazon_lower = _normalize_simple(amazon_title)
    if left and left in amazon_lower:
        return False
    if right and right in supplier_lower:
        return False
    return True


def _profit_snapshot(row: pd.Series | dict[str, Any]) -> dict[str, Any]:
    unit_cost, unit_cost_source = _first_float(row, ["unit_cost", "supplier_unit_cost", "cost"])
    profit_per_unit, profit_per_unit_source = _first_float(
        row,
        [
            "corrected_profit_per_unit_gbp",
            "profit_per_unit_30d_gbp",
            "profit_per_unit_30d",
            "profit_per_unit",
        ],
    )
    expected_profit, expected_profit_source = _first_float(
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
        expected_profit = _extract_profit_likely(str(row.get("why_data_summary", "")))
        expected_profit_source = "why_data_summary:profit_likely_gbp" if expected_profit is not None else ""

    roi_value, roi_source = _first_float(row, ["roi_check_value", "fallback_roi", "phase_profit_pct"])
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
    supplier_title = _normalize_text(row.get("supplier_title", ""))
    amazon_title = _normalize_text(row.get("amazon_title", row.get("title", "")))
    supplier_brand = _normalize_text(row.get("supplier_brand", row.get("brand_supplier", "")))
    amazon_brand = _normalize_text(row.get("amazon_brand", row.get("brand", "")))
    if not supplier_brand:
        supplier_brand = _infer_brand_from_supplier_title(supplier_title)
    profit = _profit_snapshot(row)

    reasons: list[str] = []
    evidence: list[str] = []
    bucket = "needs_user_guidance"
    action = "manual_review"
    confidence = "low"

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
        }

    supplier_tokens = _tokens(supplier_title)
    amazon_tokens = _tokens(amazon_title)
    common_tokens = supplier_tokens & amazon_tokens
    denominator = max(1, min(len(supplier_tokens), len(amazon_tokens)))
    overlap_ratio = len(common_tokens) / denominator
    low_overlap = overlap_ratio < 0.30

    supplier_quantities = _extract_quantity_tokens(supplier_title)
    amazon_quantities = _extract_quantity_tokens(amazon_title)
    quantity_mismatch = False
    if supplier_quantities and amazon_quantities:
        quantity_mismatch = supplier_quantities.isdisjoint(amazon_quantities)
    elif supplier_quantities or amazon_quantities:
        # One side mentioning a pack/count and the other side staying silent is a review risk.
        quantity_mismatch = True

    supplier_sizes = _extract_size_tokens(supplier_title)
    amazon_sizes = _extract_size_tokens(amazon_title)
    size_mismatch = bool(supplier_sizes and amazon_sizes and supplier_sizes.isdisjoint(amazon_sizes))

    supplier_accessory = _contains_term(supplier_title, ACCESSORY_TERMS)
    amazon_accessory = _contains_term(amazon_title, ACCESSORY_TERMS)
    supplier_device = _contains_term(supplier_title, DEVICE_TERMS)
    amazon_device = _contains_term(amazon_title, DEVICE_TERMS)
    accessory_device_conflict = (supplier_accessory and amazon_device and not amazon_accessory) or (
        amazon_accessory and supplier_device and not supplier_accessory
    )

    brand_conflict = _brand_mismatch(supplier_brand, amazon_brand, supplier_title, amazon_title)
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
    }


classify_title_match = shared_classify_title_match
VALID_ACTIONS = SHARED_VALID_ACTIONS
VALID_DECISION_BUCKETS = SHARED_VALID_DECISION_BUCKETS


def _load_supplier_titles(supplier_inbox_dir: Path) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    if not supplier_inbox_dir.exists():
        return pd.DataFrame()
    for path in supplier_inbox_dir.glob("*/canonical_current.csv"):
        df = _read_csv(path)
        if df.empty or "supplier_sku" not in df.columns:
            continue
        work = df.copy()
        if "supplier_id" not in work.columns:
            work["supplier_id"] = path.parent.name
        if "supplier_title" not in work.columns:
            work["supplier_title"] = ""
        if "brand" not in work.columns:
            work["brand"] = ""
        if "unit_cost" not in work.columns:
            work["unit_cost"] = ""
        if "currency" not in work.columns:
            work["currency"] = ""
        work["_supplier_sku_key"] = work["supplier_sku"].map(_normalize_key)
        work["_supplier_id_key"] = work["supplier_id"].map(_normalize_key)
        rows.append(
            work[
                [
                    "_supplier_id_key",
                    "_supplier_sku_key",
                    "supplier_id",
                    "supplier_sku",
                    "supplier_title",
                    "brand",
                    "unit_cost",
                    "currency",
                ]
            ].copy()
        )
    if not rows:
        return pd.DataFrame()
    combined = pd.concat(rows, ignore_index=True).fillna("")
    combined = combined[combined["_supplier_sku_key"] != ""].copy()
    return combined.drop_duplicates(subset=["_supplier_id_key", "_supplier_sku_key"], keep="last")


def _combine_review_inputs(review_paths: list[Path]) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for path in review_paths:
        df = _read_csv(path)
        if df.empty:
            continue
        work = df.copy()
        work["source_file"] = str(path)
        if "review_pack_type" not in work.columns:
            work["review_pack_type"] = "passes" if "pass_review" in path.name else "near_misses"
        if "amazon_title" not in work.columns:
            work["amazon_title"] = work.get("title", "")
        if "amazon_brand" not in work.columns:
            work["amazon_brand"] = work.get("brand", "")
        for col in ["active_supplier_id", "active_run_id", "supplier_sku", "asin", "candidate_id"]:
            if col not in work.columns:
                work[col] = ""
        rows.append(work)
    if not rows:
        return pd.DataFrame()
    combined = pd.concat(rows, ignore_index=True).fillna("")
    combined["_supplier_sku_key"] = combined["supplier_sku"].map(_normalize_key)
    combined["_supplier_id_key"] = combined["active_supplier_id"].map(_normalize_key)
    return combined


def _merge_supplier_titles(review_df: pd.DataFrame, supplier_df: pd.DataFrame) -> pd.DataFrame:
    if review_df.empty:
        return review_df
    work = review_df.copy()
    for col in ["supplier_title", "supplier_brand", "unit_cost", "currency", "supplier_title_source", "supplier_title_source_supplier_id"]:
        if col not in work.columns:
            work[col] = ""
    if supplier_df.empty:
        work["supplier_title_source"] = "missing_supplier_canonical"
        return work

    exact = supplier_df.rename(
        columns={
            "supplier_title": "_exact_supplier_title",
            "brand": "_exact_supplier_brand",
            "unit_cost": "_exact_unit_cost",
            "currency": "_exact_currency",
            "supplier_id": "_exact_supplier_id",
        }
    )
    work = work.merge(
        exact[
            [
                "_supplier_id_key",
                "_supplier_sku_key",
                "_exact_supplier_title",
                "_exact_supplier_brand",
                "_exact_unit_cost",
                "_exact_currency",
                "_exact_supplier_id",
            ]
        ],
        on=["_supplier_id_key", "_supplier_sku_key"],
        how="left",
    )

    fallback = supplier_df.sort_values(["_supplier_sku_key", "_supplier_id_key"]).drop_duplicates(
        subset=["_supplier_sku_key"], keep="last"
    )
    fallback = fallback.rename(
        columns={
            "supplier_title": "_fallback_supplier_title",
            "brand": "_fallback_supplier_brand",
            "unit_cost": "_fallback_unit_cost",
            "currency": "_fallback_currency",
            "supplier_id": "_fallback_supplier_id",
        }
    )
    work = work.merge(
        fallback[
            [
                "_supplier_sku_key",
                "_fallback_supplier_title",
                "_fallback_supplier_brand",
                "_fallback_unit_cost",
                "_fallback_currency",
                "_fallback_supplier_id",
            ]
        ],
        on="_supplier_sku_key",
        how="left",
    )

    exact_title = work["_exact_supplier_title"].fillna("").map(_normalize_text)
    fallback_title = work["_fallback_supplier_title"].fillna("").map(_normalize_text)
    work["supplier_title"] = exact_title.where(exact_title != "", fallback_title)
    work["supplier_brand"] = work["_exact_supplier_brand"].fillna("").where(
        exact_title != "", work["_fallback_supplier_brand"].fillna("")
    )
    work["unit_cost"] = work["_exact_unit_cost"].fillna("").where(exact_title != "", work["_fallback_unit_cost"].fillna(""))
    work["currency"] = work["_exact_currency"].fillna("").where(exact_title != "", work["_fallback_currency"].fillna(""))
    work["supplier_title_source_supplier_id"] = work["_exact_supplier_id"].fillna("").where(
        exact_title != "", work["_fallback_supplier_id"].fillna("")
    )
    work["supplier_title_source"] = "active_supplier_canonical"
    work.loc[(exact_title == "") & (fallback_title != ""), "supplier_title_source"] = "supplier_sku_fallback"
    work.loc[work["supplier_title"].map(_normalize_text) == "", "supplier_title_source"] = "missing_supplier_title"
    drop_cols = [c for c in work.columns if c.startswith("_exact_") or c.startswith("_fallback_")]
    return work.drop(columns=drop_cols)


def _build_decisions(backlog_df: pd.DataFrame, observed_utc: str) -> pd.DataFrame:
    if backlog_df.empty:
        return pd.DataFrame()
    decision_rows: list[dict[str, Any]] = []
    for _, row in backlog_df.iterrows():
        decision = classify_title_match(row)
        decision_rows.append(
            {
                "observed_utc": observed_utc,
                "active_supplier_id": _normalize_text(row.get("active_supplier_id", "")),
                "active_run_id": _normalize_text(row.get("active_run_id", "")),
                "source_file": _normalize_text(row.get("source_file", "")),
                "review_pack_type": _normalize_text(row.get("review_pack_type", "")),
                "review_batch_id": _normalize_text(row.get("review_batch_id", "")),
                "candidate_id": _normalize_text(row.get("candidate_id", "")),
                "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                "asin": _normalize_text(row.get("asin", "")),
                "supplier_title": decision["supplier_title"],
                "amazon_title": decision["amazon_title"],
                "supplier_brand": decision["supplier_brand"],
                "amazon_brand": decision["amazon_brand"],
                "supplier_title_source": _normalize_text(row.get("supplier_title_source", "")),
                "supplier_title_source_supplier_id": _normalize_text(row.get("supplier_title_source_supplier_id", "")),
                "unit_cost_gbp": decision["unit_cost_gbp"],
                "profit_per_unit_gbp": decision["profit_per_unit_gbp"],
                "expected_profit_gbp": decision["expected_profit_gbp"],
                "profit_on_cost_pct": decision["profit_on_cost_pct"],
                "profit_on_cost_source": decision["profit_on_cost_source"],
                "high_roi_flag": decision["high_roi_flag"],
                "high_roi_reasons": decision["high_roi_reasons"],
                "title_overlap_ratio": decision["title_overlap_ratio"],
                "suspicious_title_flag": decision["suspicious_title_flag"],
                "agent_decision_bucket": decision["agent_decision_bucket"],
                "title_match_action": decision["title_match_action"],
                "agent_confidence": decision["agent_confidence"],
                "agent_reason_code": decision["agent_reason_code"],
                "agent_evidence": decision["agent_evidence"],
                "user_override_status": "",
            }
        )
    return pd.DataFrame(decision_rows)


def _expected_matches(row: pd.Series) -> bool:
    expected = _normalize_text(row.get("agent_expected_action", "")).lower()
    if not expected:
        return True
    bucket = _normalize_text(row.get("agent_decision_bucket", "")).lower()
    action = _normalize_text(row.get("title_match_action", "")).lower()
    if expected == bucket or expected == action:
        return True
    if expected == "clear_breach_remove_from_clean_pass" and action == "remove_from_clean_pass":
        return True
    if expected.startswith("needs_user_guidance") and action == "manual_review":
        return True
    if expected in {"title_match_clear", "allow_if_other_checks_pass"} and action == "allow_if_other_checks_pass":
        return True
    return False


def _build_sample_calibration(sample_path: Path, observed_utc: str) -> pd.DataFrame:
    sample = _read_csv(sample_path)
    if sample.empty:
        return pd.DataFrame()
    work = sample.copy()
    if "amazon_title" not in work.columns:
        work["amazon_title"] = work.get("title", "")
    if "amazon_brand" not in work.columns:
        work["amazon_brand"] = work.get("brand", "")
    if "supplier_brand" not in work.columns:
        work["supplier_brand"] = work.get("brand_supplier", "")
    decisions = _build_decisions(work, observed_utc)
    if decisions.empty:
        return decisions
    for col in ["training_label_seed", "agent_expected_action", "review_note"]:
        decisions[col] = work.get(col, "")
    decisions["calibration_match"] = decisions.apply(lambda row: "1" if _expected_matches(row) else "0", axis=1)
    return decisions


def _build_health(decision_df: pd.DataFrame, sample_calibration_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, str]] = []

    def add(metric: str, value: int | float | str, status: str, detail: str = "") -> None:
        rows.append({"metric": metric, "value": str(value), "status": status, "detail": detail})

    backlog_rows = len(decision_df)
    add("backlog_rows", backlog_rows, "PASS")
    if decision_df.empty:
        add("missing_supplier_title_rows", 0, "PASS")
        add("missing_amazon_title_rows", 0, "PASS")
        add("invalid_decision_bucket_rows", 0, "PASS")
        add("invalid_action_rows", 0, "PASS")
    else:
        missing_supplier = int(decision_df["supplier_title"].map(_normalize_text).eq("").sum())
        missing_amazon = int(decision_df["amazon_title"].map(_normalize_text).eq("").sum())
        missing_amazon_with_asin = int(
            (
                decision_df["amazon_title"].map(_normalize_text).eq("")
                & decision_df["asin"].map(_normalize_text).ne("")
            ).sum()
        )
        invalid_bucket = int((~decision_df["agent_decision_bucket"].isin(VALID_DECISION_BUCKETS)).sum())
        invalid_action = int((~decision_df["title_match_action"].isin(VALID_ACTIONS)).sum())
        add("missing_supplier_title_rows", missing_supplier, "WARN" if missing_supplier else "PASS")
        add("missing_amazon_title_rows", missing_amazon, "WARN" if missing_amazon else "PASS")
        add(
            "missing_amazon_title_with_asin_rows",
            missing_amazon_with_asin,
            "FAIL" if missing_amazon_with_asin else "PASS",
        )
        add("invalid_decision_bucket_rows", invalid_bucket, "FAIL" if invalid_bucket else "PASS")
        add("invalid_action_rows", invalid_action, "FAIL" if invalid_action else "PASS")
        add(
            "high_roi_identity_suspicion_rows",
            int(decision_df["agent_decision_bucket"].eq("high_roi_identity_suspicion").sum()),
            "PASS",
        )
        add("remove_from_clean_pass_rows", int(decision_df["title_match_action"].eq("remove_from_clean_pass").sum()), "PASS")
        add("manual_review_rows", int(decision_df["title_match_action"].eq("manual_review").sum()), "PASS")
        add(
            "allow_if_other_checks_pass_rows",
            int(decision_df["title_match_action"].eq("allow_if_other_checks_pass").sum()),
            "PASS",
        )

    sample_rows = len(sample_calibration_df)
    sample_mismatches = 0
    if sample_rows:
        sample_mismatches = int(sample_calibration_df["calibration_match"].ne("1").sum())
    add("sample_calibration_rows", sample_rows, "PASS")
    add("sample_calibration_mismatch_rows", sample_mismatches, "FAIL" if sample_mismatches else "PASS")
    return pd.DataFrame(rows)


def _write_snapshot(latest_path: Path, df: pd.DataFrame, observed_utc: str) -> Path:
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(latest_path, index=False)
    stamp = _timestamp_for_file(observed_utc)
    snapshot_path = latest_path.with_name(latest_path.name.replace("_latest", f"_{stamp}"))
    df.to_csv(snapshot_path, index=False)
    return snapshot_path


def _write_summary(path: Path, report: dict[str, Any], health_df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Title Match Agent Summary",
        "",
        f"- observed_utc: `{report['observed_utc']}`",
        f"- backlog_rows: `{report['backlog_rows']}`",
        f"- decision_rows: `{report['decision_rows']}`",
        f"- sample_calibration_rows: `{report['sample_calibration_rows']}`",
        f"- sample_calibration_mismatch_rows: `{report['sample_calibration_mismatch_rows']}`",
        "",
        "## Health",
        "",
    ]
    for row in health_df.to_dict("records"):
        lines.append(f"- {row['metric']}: `{row['value']}` ({row['status']})")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_title_match_agent_backlog(
    *,
    review_paths: list[Path] | None = None,
    supplier_inbox_dir: Path = DEFAULT_SUPPLIER_INBOX_DIR,
    sample_collection_path: Path = DEFAULT_SAMPLE_COLLECTION_PATH,
    backlog_output_path: Path = DEFAULT_BACKLOG_OUTPUT_PATH,
    decision_output_path: Path = DEFAULT_DECISION_OUTPUT_PATH,
    health_output_path: Path = DEFAULT_HEALTH_OUTPUT_PATH,
    summary_output_path: Path = DEFAULT_SUMMARY_OUTPUT_PATH,
    sample_calibration_output_path: Path = DEFAULT_SAMPLE_CALIBRATION_OUTPUT_PATH,
    observed_utc: str | None = None,
    write_outputs: bool = True,
) -> TitleMatchAgentResult:
    observed = observed_utc or _utc_now_iso()
    input_paths = review_paths or [DEFAULT_PASS_REVIEW_PATH, DEFAULT_NEAR_MISS_REVIEW_PATH]
    review_df = _combine_review_inputs(input_paths)
    supplier_df = _load_supplier_titles(supplier_inbox_dir)
    backlog_df = _merge_supplier_titles(review_df, supplier_df)
    decision_df = _build_decisions(backlog_df, observed)
    sample_calibration_df = _build_sample_calibration(sample_collection_path, observed)
    health_df = _build_health(decision_df, sample_calibration_df)

    report = {
        "observed_utc": observed,
        "backlog_rows": int(len(backlog_df)),
        "decision_rows": int(len(decision_df)),
        "sample_calibration_rows": int(len(sample_calibration_df)),
        "sample_calibration_mismatch_rows": int(sample_calibration_df["calibration_match"].ne("1").sum())
        if not sample_calibration_df.empty
        else 0,
        "remove_from_clean_pass_rows": int(decision_df["title_match_action"].eq("remove_from_clean_pass").sum())
        if not decision_df.empty
        else 0,
        "manual_review_rows": int(decision_df["title_match_action"].eq("manual_review").sum()) if not decision_df.empty else 0,
        "allow_if_other_checks_pass_rows": int(decision_df["title_match_action"].eq("allow_if_other_checks_pass").sum())
        if not decision_df.empty
        else 0,
    }

    if write_outputs:
        _write_snapshot(backlog_output_path, backlog_df, observed)
        _write_snapshot(decision_output_path, decision_df, observed)
        _write_snapshot(health_output_path, health_df, observed)
        _write_snapshot(sample_calibration_output_path, sample_calibration_df, observed)
        _write_summary(summary_output_path, report, health_df)

    return TitleMatchAgentResult(
        backlog_df=backlog_df,
        decision_df=decision_df,
        health_df=health_df,
        sample_calibration_df=sample_calibration_df,
        report=report,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build title-match agent backlog and decision outputs.")
    parser.add_argument("--pass-review-path", type=Path, default=DEFAULT_PASS_REVIEW_PATH)
    parser.add_argument("--near-miss-review-path", type=Path, default=DEFAULT_NEAR_MISS_REVIEW_PATH)
    parser.add_argument("--supplier-inbox-dir", type=Path, default=DEFAULT_SUPPLIER_INBOX_DIR)
    parser.add_argument("--sample-collection-path", type=Path, default=DEFAULT_SAMPLE_COLLECTION_PATH)
    parser.add_argument("--backlog-output-path", type=Path, default=DEFAULT_BACKLOG_OUTPUT_PATH)
    parser.add_argument("--decision-output-path", type=Path, default=DEFAULT_DECISION_OUTPUT_PATH)
    parser.add_argument("--health-output-path", type=Path, default=DEFAULT_HEALTH_OUTPUT_PATH)
    parser.add_argument("--summary-output-path", type=Path, default=DEFAULT_SUMMARY_OUTPUT_PATH)
    parser.add_argument("--sample-calibration-output-path", type=Path, default=DEFAULT_SAMPLE_CALIBRATION_OUTPUT_PATH)
    parser.add_argument("--observed-utc", default="")
    args = parser.parse_args()

    result = build_title_match_agent_backlog(
        review_paths=[args.pass_review_path, args.near_miss_review_path],
        supplier_inbox_dir=args.supplier_inbox_dir,
        sample_collection_path=args.sample_collection_path,
        backlog_output_path=args.backlog_output_path,
        decision_output_path=args.decision_output_path,
        health_output_path=args.health_output_path,
        summary_output_path=args.summary_output_path,
        sample_calibration_output_path=args.sample_calibration_output_path,
        observed_utc=args.observed_utc or None,
    )
    print(json.dumps(result.report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
