from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._title_match_agent import (
    classify_title_match,
    extract_quantity_tokens,
    extract_size_tokens,
    infer_brand_from_supplier_title,
    title_tokens,
    to_float,
)


DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"
DEFAULT_PASS_REVIEW_PATH = DEFAULT_OUTPUT_DIR / "f_live_price_file_pass_review_latest.csv"
DEFAULT_NEAR_MISS_REVIEW_PATH = DEFAULT_OUTPUT_DIR / "f_live_price_file_near_miss_review_latest.csv"
DEFAULT_TITLE_MATCH_PATH = DEFAULT_OUTPUT_DIR / "f_title_match_agent_decisions_latest.csv"
DEFAULT_SUPPLIER_INBOX_DIR = ROOT / "out" / "systems" / "F" / "inbox" / "suppliers"

DEFAULT_EVIDENCE_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "f032_review_intelligence_evidence_pack_latest.csv"
DEFAULT_DECISION_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "f032_review_intelligence_decisions_latest.csv"
DEFAULT_FAIL_CATEGORY_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "f032_review_intelligence_fail_categories_latest.csv"
DEFAULT_CHECKLIST_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "f032_review_intelligence_checklist_latest.csv"
DEFAULT_RULE_SUGGESTION_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "f032_rule_tightening_suggestions_latest.csv"
DEFAULT_HEALTH_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "f032_review_intelligence_health_latest.csv"
DEFAULT_SUMMARY_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "f032_review_intelligence_summary_latest.md"

VALID_F032_ACTIONS = {
    "remove_from_clean_pass",
    "manual_review",
    "rescan_needed",
    "allow_if_other_checks_pass",
}

SOURCE_SKU_ALIASES = (
    "supplier_sku",
    "sku",
    "no.",
    "no",
    "inventory id",
    "productnumber",
    "product number",
    "productcode",
    "product code",
    "item",
    "item code",
)
SOURCE_TITLE_ALIASES = (
    "supplier_title",
    "suppliertitle",
    "supplier title",
    "description",
    "product description",
    "product_title",
    "product name",
    "title",
    "name",
)
SOURCE_COST_ALIASES = (
    "unit_cost",
    "supplier_unit_cost",
    "supplier unit cost",
    "cost",
    "price",
    "trade price",
    "clearance price",
    "basepriceperunit",
    "base price per unit",
)

ACTION_PRIORITY = {
    "remove_from_clean_pass": 10,
    "rescan_needed": 20,
    "manual_review": 30,
    "allow_if_other_checks_pass": 90,
}

EVIDENCE_COLUMNS = [
    "observed_utc",
    "source_review_pack_type",
    "active_supplier_id",
    "active_run_id",
    "review_batch_id",
    "candidate_id",
    "supplier_sku",
    "asin",
    "supplier_title",
    "amazon_title",
    "amazon_product_detail_text",
    "amazon_product_description",
    "amazon_feature_bullets",
    "supplier_brand",
    "amazon_brand",
    "supplier_unit_cost_gbp",
    "amazon_sell_price_gbp",
    "profit_per_unit_gbp",
    "expected_profit_gbp",
    "profit_on_cost_pct",
    "review_priority_score",
    "main_rank",
    "expected_units_next_30d",
    "sales_lower_30d",
    "sales_upper_30d",
    "current_review_state",
    "current_gate_result",
    "near_miss_type",
    "reviewability_state",
    "screening_fail_code",
    "screening_status_reason",
    "title_match_action",
    "title_match_decision_bucket",
    "title_match_reason_code",
    "title_match_confidence",
    "title_match_evidence",
    "title_match_high_roi_flag",
    "seller_history_code",
    "seller_history_recommended_action",
    "seller_history_supporting_codes",
    "seller_history_evidence_source",
    "seller_history_new_30",
    "seller_history_new_90",
    "seller_history_new_180",
    "seller_history_dashboard_yes_or_no",
    "seller_history_top_seller_names",
    "seller_history_rank_1_seller_name",
    "seller_history_buybox_seller_name",
    "profit_formula_code",
    "profit_recommended_action",
    "profit_evidence_source",
    "demand_conflict_code",
    "demand_recommended_action",
    "demand_supporting_codes",
    "demand_evidence_source",
    "history_risk_code",
    "history_recommended_action",
    "history_supporting_codes",
    "history_evidence_source",
    "uk_review_code",
    "uk_review_recommended_action",
    "uk_review_supporting_codes",
    "uk_review_evidence_source",
    "review_memory_decision",
    "review_memory_note",
    "why_data_summary",
    "watch_data_summary",
    "commercial_note",
]

DECISION_COLUMNS = [
    "observed_utc",
    "f032_decision_id",
    "source_review_pack_type",
    "active_supplier_id",
    "active_run_id",
    "review_batch_id",
    "candidate_id",
    "supplier_sku",
    "asin",
    "supplier_title",
    "amazon_title",
    "f032_action",
    "f032_decision_bucket",
    "f032_fail_category",
    "f032_confidence",
    "f032_needs_user_guidance",
    "f032_rescan_needed",
    "f032_rule_tightening_candidate",
    "f032_reason",
    "f032_evidence",
]

CHECKLIST_COLUMNS = [
    "observed_utc",
    "source_review_pack_type",
    "active_supplier_id",
    "active_run_id",
    "review_batch_id",
    "candidate_id",
    "supplier_sku",
    "asin",
    "title_identity_status",
    "title_identity_reason",
    "pack_size_quantity_status",
    "pack_size_quantity_reason",
    "accessory_device_status",
    "accessory_device_reason",
    "roi_suspicion_status",
    "roi_suspicion_reason",
    "seller_control_status",
    "seller_control_reason",
    "demand_evidence_status",
    "demand_evidence_reason",
    "review_variant_status",
    "review_variant_reason",
    "missing_evidence_status",
    "missing_evidence_reason",
]

RULE_SUGGESTION_COLUMNS = [
    "observed_utc",
    "f032_fail_category",
    "row_count",
    "example_supplier_sku",
    "example_asin",
    "evidence_that_caught_it",
    "proposed_earlier_rule",
    "expected_benefit",
    "false_fail_risk",
    "automation_readiness",
    "needs_more_examples",
]


@dataclass(frozen=True)
class F032Result:
    evidence_df: pd.DataFrame
    decision_df: pd.DataFrame
    fail_category_df: pd.DataFrame
    checklist_df: pd.DataFrame
    rule_suggestion_df: pd.DataFrame
    health_df: pd.DataFrame
    report: dict[str, Any]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _timestamp_for_file(observed_utc: str) -> str:
    return observed_utc.replace("-", "").replace(":", "").replace("Z", "Z")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _normalize_column_key(value: object) -> str:
    return _normalize_text(value).lower().strip()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _read_source_tables(path: Path) -> list[pd.DataFrame]:
    if not path.exists():
        return []
    suffix = path.suffix.lower()
    try:
        if suffix in {".xlsx", ".xlsm", ".xls"}:
            sheets = pd.read_excel(path, sheet_name=None, dtype=str, engine="openpyxl").values()
            return [df.fillna("") for df in sheets if not df.empty]
        if suffix in {".csv", ".txt"}:
            frames: list[pd.DataFrame] = []
            for header in (0, 1):
                try:
                    df = pd.read_csv(path, dtype=str, header=header).fillna("")
                except pd.errors.EmptyDataError:
                    continue
                if not df.empty:
                    frames.append(df)
            return frames
    except (OSError, ValueError, pd.errors.EmptyDataError):
        return []
    return []


def _find_source_column(columns: list[str], aliases: tuple[str, ...]) -> str:
    by_key = {_normalize_column_key(column): column for column in columns}
    for alias in aliases:
        column = by_key.get(_normalize_column_key(alias))
        if column:
            return column
    return ""


def _source_supplier_title(source_row: pd.Series, title_column: str) -> str:
    title = _normalize_text(source_row.get(title_column, ""))
    if not title:
        return ""
    brand = _normalize_text(source_row.get("Brand", ""))
    variant = _normalize_text(source_row.get("Variant", ""))
    parts: list[str] = []
    title_lower = title.lower()
    if brand and brand.lower() not in title_lower:
        parts.append(brand)
    parts.append(title)
    if variant and variant.lower() not in title_lower:
        parts.append(variant)
    return " ".join(parts).strip()


def _source_unit_cost(source_row: pd.Series, cost_column: str) -> str:
    if not cost_column:
        return ""
    parsed = to_float(source_row.get(cost_column, ""))
    if parsed is None:
        return ""
    return _num_to_text(parsed)


def _num_to_text(value: float | int | None) -> str:
    if value is None:
        return ""
    as_float = float(value)
    if as_float.is_integer():
        return str(int(as_float))
    return f"{as_float:.6f}".rstrip("0").rstrip(".")


def _first_text(row: pd.Series | dict[str, Any], fields: list[str]) -> str:
    for field in fields:
        value = _normalize_text(row.get(field, ""))
        if value:
            return value
    return ""


def _first_float_text(row: pd.Series | dict[str, Any], fields: list[str]) -> str:
    for field in fields:
        parsed = to_float(row.get(field, ""))
        if parsed is not None:
            return _num_to_text(parsed)
    return ""


def _quantity_tokens_from_match_evidence(value: object) -> set[str]:
    text = _normalize_text(value)
    if not text:
        return set()
    tokens: set[str] = set()
    for piece in re.split(r"[|;]", text):
        key, _, raw_values = piece.partition("=")
        if key.strip() != "supplier_quantities":
            continue
        for raw_value in raw_values.split(","):
            cleaned = _normalize_text(raw_value)
            if cleaned:
                tokens.add(cleaned)
    return tokens


def _quantity_page_text(value: object) -> str:
    text = _normalize_text(value).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9.]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _page_text_confirms_supplier_quantity(evidence: pd.Series | dict[str, Any]) -> tuple[str, str]:
    supplier_quantities = _quantity_tokens_from_match_evidence(evidence.get("title_match_evidence", ""))
    supplier_quantities.update(extract_quantity_tokens(_normalize_text(evidence.get("supplier_title", ""))))
    supplier_quantities = {quantity for quantity in supplier_quantities if quantity}
    if not supplier_quantities:
        return "", ""

    page_text = _quantity_page_text(
        " ".join(
            [
                _normalize_text(evidence.get("amazon_product_description", "")),
                _normalize_text(evidence.get("amazon_feature_bullets", "")),
                _normalize_text(evidence.get("amazon_product_detail_text", "")),
            ]
        )
    )
    if not page_text:
        return "", ""

    quantity_unit_words = (
        "sleeve",
        "sleeves",
        "piece",
        "pieces",
        "pc",
        "pcs",
        "item",
        "items",
        "unit",
        "units",
        "card",
        "cards",
        "tablet",
        "tablets",
        "capsule",
        "capsules",
        "can",
        "cans",
        "bottle",
        "bottles",
        "refill",
        "refills",
        "cartridge",
        "cartridges",
    )
    unit_pattern = "|".join(re.escape(unit) for unit in quantity_unit_words)
    for quantity in sorted(supplier_quantities):
        q = re.escape(quantity)
        patterns = [
            rf"\beach pack contains {q}\b",
            rf"\bpack contains {q}\b",
            rf"\bcontains {q}\b",
            rf"\bpack of {q}\b",
            rf"\b{q} pack\b",
            rf"\b{q} (?:card )?(?:{unit_pattern})\b",
        ]
        if any(re.search(pattern, page_text) for pattern in patterns):
            return quantity, f"amazon_page_text_confirms_supplier_quantity={quantity}"
    return "", ""


def _combined_amazon_identity_text(evidence: pd.Series | dict[str, Any]) -> str:
    return " ".join(
        [
            _normalize_text(evidence.get("amazon_title", "")),
            _normalize_text(evidence.get("amazon_product_description", "")),
            _normalize_text(evidence.get("amazon_feature_bullets", "")),
            _normalize_text(evidence.get("amazon_product_detail_text", "")),
        ]
    ).strip()


def _combined_amazon_text_confirms_same_product(evidence: pd.Series | dict[str, Any]) -> tuple[bool, str]:
    supplier_title = _normalize_text(evidence.get("supplier_title", ""))
    amazon_text = _combined_amazon_identity_text(evidence)
    if not supplier_title or not amazon_text:
        return False, ""

    supplier_quantities = _quantity_tokens_from_match_evidence(evidence.get("title_match_evidence", ""))
    supplier_quantities.update(extract_quantity_tokens(supplier_title))
    supplier_quantities = {quantity for quantity in supplier_quantities if quantity}
    confirmed_quantity, quantity_evidence = _page_text_confirms_supplier_quantity(evidence)
    if supplier_quantities and not confirmed_quantity:
        return False, ""

    supplier_sizes = extract_size_tokens(supplier_title)
    amazon_sizes = extract_size_tokens(amazon_text)
    if supplier_sizes and amazon_sizes and supplier_sizes.isdisjoint(amazon_sizes):
        return False, ""

    supplier_words = title_tokens(supplier_title)
    amazon_words = title_tokens(amazon_text)
    if not supplier_words or not amazon_words:
        return False, ""
    common_words = supplier_words & amazon_words
    required_common = 2 if len(supplier_words) <= 3 else 3
    if len(common_words) < required_common:
        return False, ""
    overlap_ratio = len(common_words) / max(1, len(supplier_words))
    if overlap_ratio < 0.60:
        return False, ""

    evidence_parts = [
        f"combined_amazon_text_overlap={overlap_ratio:.2f}",
        f"common_tokens={','.join(sorted(common_words)[:12])}",
    ]
    if quantity_evidence:
        evidence_parts.append(quantity_evidence)
    return True, "|".join(evidence_parts)


def _load_supplier_title_index(supplier_inbox_dir: Path) -> dict[tuple[str, str], dict[str, str]]:
    out: dict[tuple[str, str], dict[str, str]] = {}
    if not supplier_inbox_dir.exists():
        return out
    for path in supplier_inbox_dir.glob("*/canonical_current.csv"):
        df = _read_csv(path)
        if df.empty or "supplier_sku" not in df.columns:
            continue
        if "supplier_id" not in df.columns:
            df["supplier_id"] = path.parent.name
        for _, row in df.iterrows():
            supplier_id = _normalize_text(row.get("supplier_id", "")) or path.parent.name
            supplier_sku = _normalize_text(row.get("supplier_sku", ""))
            if not supplier_sku:
                continue
            record = {
                "supplier_title": _normalize_text(row.get("supplier_title", "")),
                "supplier_brand": _normalize_text(row.get("brand", "")),
                "unit_cost": _normalize_text(row.get("unit_cost", "")),
                "currency": _normalize_text(row.get("currency", "")),
                "supplier_id": supplier_id,
            }
            out[(_normalize_key(supplier_id), _normalize_key(supplier_sku))] = record
            out.setdefault(("", _normalize_key(supplier_sku)), record)
    return out


def _merge_supplier_title_indexes(
    primary: dict[tuple[str, str], dict[str, str]],
    fallback: dict[tuple[str, str], dict[str, str]],
) -> dict[tuple[str, str], dict[str, str]]:
    merged = {key: dict(value) for key, value in primary.items()}
    for key, fallback_record in fallback.items():
        existing = merged.get(key)
        if existing is None:
            merged[key] = dict(fallback_record)
            continue
        for field in ("supplier_title", "supplier_brand", "unit_cost", "currency", "supplier_id"):
            if not _normalize_text(existing.get(field, "")) and _normalize_text(fallback_record.get(field, "")):
                existing[field] = _normalize_text(fallback_record.get(field, ""))
    return merged


def _load_handoff_source_title_index(review_paths: list[Path]) -> dict[tuple[str, str], dict[str, str]]:
    out: dict[tuple[str, str], dict[str, str]] = {}
    seen_sources: set[tuple[str, str]] = set()
    for review_path in review_paths:
        manifest_path = review_path.parent / "candidate_manifest.csv"
        manifest_df = _read_csv(manifest_path)
        if manifest_df.empty:
            continue
        for _, manifest_row in manifest_df.iterrows():
            supplier_id = _normalize_text(manifest_row.get("supplier_id", ""))
            source_path_text = _normalize_text(manifest_row.get("source_file_path", ""))
            if not supplier_id or not source_path_text:
                continue
            source_path = Path(source_path_text)
            source_key = (_normalize_key(supplier_id), str(source_path.resolve()) if source_path.exists() else source_path_text)
            if source_key in seen_sources:
                continue
            seen_sources.add(source_key)
            for table in _read_source_tables(source_path):
                sku_column = _find_source_column(list(table.columns), SOURCE_SKU_ALIASES)
                title_column = _find_source_column(list(table.columns), SOURCE_TITLE_ALIASES)
                cost_column = _find_source_column(list(table.columns), SOURCE_COST_ALIASES)
                if not sku_column or not title_column:
                    continue
                for _, source_row in table.iterrows():
                    supplier_sku = _normalize_text(source_row.get(sku_column, "")).upper()
                    supplier_title = _source_supplier_title(source_row, title_column)
                    if not supplier_sku or not supplier_title:
                        continue
                    record = {
                        "supplier_title": supplier_title,
                        "supplier_brand": "",
                        "unit_cost": _source_unit_cost(source_row, cost_column),
                        "currency": "",
                        "supplier_id": supplier_id,
                    }
                    out[(_normalize_key(supplier_id), _normalize_key(supplier_sku))] = record
                    out.setdefault(("", _normalize_key(supplier_sku)), record)
    return out


def _combine_review_inputs(pass_review_path: Path, near_miss_review_path: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path, pack_type in [(pass_review_path, "passes"), (near_miss_review_path, "near_misses")]:
        df = _read_csv(path)
        if df.empty:
            continue
        work = df.copy()
        work["source_review_pack_type"] = pack_type
        work["source_file"] = str(path)
        for col in ["candidate_id", "supplier_sku", "asin", "active_supplier_id", "active_run_id"]:
            if col not in work.columns:
                work[col] = ""
        frames.append(work)
    if not frames:
        return pd.DataFrame()
    work = pd.concat(frames, ignore_index=True).fillna("")
    work["_candidate_key"] = work["candidate_id"].map(_normalize_key)
    work["_supplier_sku_key"] = work["supplier_sku"].map(_normalize_key)
    work["_asin_key"] = work["asin"].map(_normalize_key)
    work["_supplier_id_key"] = work["active_supplier_id"].map(_normalize_key)
    return work


def _title_match_indexes(title_match_df: pd.DataFrame) -> tuple[dict[tuple[str, str, str], dict[str, str]], dict[tuple[str, str], dict[str, str]]]:
    by_candidate: dict[tuple[str, str, str], dict[str, str]] = {}
    by_supplier_asin: dict[tuple[str, str], dict[str, str]] = {}
    if title_match_df.empty:
        return by_candidate, by_supplier_asin
    work = title_match_df.copy().fillna("")
    for _, row in work.iterrows():
        record = {col: _normalize_text(value) for col, value in row.to_dict().items()}
        pack = _normalize_key(record.get("review_pack_type", ""))
        candidate = _normalize_key(record.get("candidate_id", ""))
        supplier_sku = _normalize_key(record.get("supplier_sku", ""))
        asin = _normalize_key(record.get("asin", ""))
        if pack and candidate:
            by_candidate[(pack, candidate, asin)] = record
            by_candidate[(pack, candidate, "")] = record
        if supplier_sku and asin:
            by_supplier_asin[(supplier_sku, asin)] = record
    return by_candidate, by_supplier_asin


def _find_title_match(
    row: pd.Series,
    by_candidate: dict[tuple[str, str, str], dict[str, str]],
    by_supplier_asin: dict[tuple[str, str], dict[str, str]],
) -> dict[str, str]:
    pack = _normalize_key(row.get("source_review_pack_type", ""))
    candidate = _normalize_key(row.get("candidate_id", ""))
    supplier_sku = _normalize_key(row.get("supplier_sku", ""))
    asin = _normalize_key(row.get("asin", ""))
    return (
        by_candidate.get((pack, candidate, asin))
        or by_candidate.get((pack, candidate, ""))
        or by_supplier_asin.get((supplier_sku, asin))
        or {}
    )


def _supplier_record(row: pd.Series, supplier_index: dict[tuple[str, str], dict[str, str]]) -> dict[str, str]:
    supplier_id = _normalize_key(row.get("active_supplier_id", ""))
    sku = _normalize_key(row.get("supplier_sku", ""))
    return supplier_index.get((supplier_id, sku)) or supplier_index.get(("", sku)) or {}


def _current_review_state(row: pd.Series | dict[str, Any]) -> str:
    pack_type = _normalize_text(row.get("source_review_pack_type", ""))
    near_type = _normalize_text(row.get("near_miss_type", ""))
    reviewability = _normalize_text(row.get("reviewability_state", ""))
    if pack_type == "passes":
        return "candidate_clean_pass"
    if near_type == "review_memory_fail" or reviewability == "known_fail":
        return "known_fail"
    if reviewability == "remove_from_clean_pass":
        return "already_removed_from_clean_pass"
    if near_type == "evidence_gap_near_miss":
        return "evidence_gap_or_rescan"
    return "near_miss_or_reviewable"


def _current_gate_result(row: pd.Series | dict[str, Any]) -> str:
    if _normalize_text(row.get("source_review_pack_type", "")) == "passes":
        return _normalize_text(row.get("screening_status_reason", "")) or "PASS"
    return _first_text(row, ["screening_fail_code", "screening_status_reason", "near_miss_type"])


def _title_match_fields(row: pd.Series, title_match: dict[str, str], supplier: dict[str, str]) -> dict[str, str]:
    supplier_title = _first_text(row, ["supplier_title"]) or _normalize_text(title_match.get("supplier_title", "")) or _normalize_text(supplier.get("supplier_title", ""))
    amazon_title = _first_text(row, ["amazon_title", "title"]) or _normalize_text(title_match.get("amazon_title", ""))
    supplier_brand = _first_text(row, ["supplier_brand"]) or _normalize_text(title_match.get("supplier_brand", "")) or _normalize_text(supplier.get("supplier_brand", ""))
    amazon_brand = _first_text(row, ["amazon_brand", "brand"]) or _normalize_text(title_match.get("amazon_brand", ""))
    unit_cost = _first_float_text(row, ["supplier_unit_cost_gbp", "unit_cost"]) or _normalize_text(title_match.get("unit_cost_gbp", "")) or _normalize_text(supplier.get("unit_cost", ""))
    profit_per_unit = _first_float_text(row, ["profit_per_unit_gbp", "profit_per_unit_30d_gbp", "corrected_profit_per_unit_gbp"])
    expected_profit = _first_float_text(row, ["expected_profit_gbp", "expected_profit_next_30d_gbp", "estimated_monthly_profit_gbp", "review_priority_score"])
    if title_match:
        return {
            "supplier_title": supplier_title,
            "amazon_title": amazon_title,
            "supplier_brand": supplier_brand or infer_brand_from_supplier_title(supplier_title),
            "amazon_brand": amazon_brand,
            "supplier_unit_cost_gbp": unit_cost,
            "profit_per_unit_gbp": profit_per_unit or _normalize_text(title_match.get("profit_per_unit_gbp", "")),
            "expected_profit_gbp": expected_profit or _normalize_text(title_match.get("expected_profit_gbp", "")),
            "profit_on_cost_pct": _normalize_text(title_match.get("profit_on_cost_pct", "")),
            "title_match_action": _normalize_text(title_match.get("title_match_action", "")),
            "title_match_decision_bucket": _normalize_text(title_match.get("agent_decision_bucket", "")),
            "title_match_reason_code": _normalize_text(title_match.get("agent_reason_code", "")),
            "title_match_confidence": _normalize_text(title_match.get("agent_confidence", "")),
            "title_match_evidence": _normalize_text(title_match.get("agent_evidence", "")),
            "title_match_high_roi_flag": _normalize_text(title_match.get("high_roi_flag", "")),
        }

    decision = classify_title_match(
        {
            "supplier_title": supplier_title,
            "amazon_title": amazon_title,
            "supplier_brand": supplier_brand,
            "amazon_brand": amazon_brand,
            "unit_cost": unit_cost,
            "profit_per_unit_30d_gbp": profit_per_unit,
            "expected_profit_next_30d_gbp": expected_profit,
        }
    )
    return {
        "supplier_title": _normalize_text(decision.get("supplier_title", "")),
        "amazon_title": _normalize_text(decision.get("amazon_title", "")),
        "supplier_brand": _normalize_text(decision.get("supplier_brand", "")),
        "amazon_brand": _normalize_text(decision.get("amazon_brand", "")),
        "supplier_unit_cost_gbp": unit_cost,
        "profit_per_unit_gbp": profit_per_unit,
        "expected_profit_gbp": expected_profit,
        "profit_on_cost_pct": _num_to_text(to_float(decision.get("profit_on_cost_pct", ""))),
        "title_match_action": _normalize_text(decision.get("title_match_action", "")),
        "title_match_decision_bucket": _normalize_text(decision.get("agent_decision_bucket", "")),
        "title_match_reason_code": _normalize_text(decision.get("agent_reason_code", "")),
        "title_match_confidence": _normalize_text(decision.get("agent_confidence", "")),
        "title_match_evidence": _normalize_text(decision.get("agent_evidence", "")),
        "title_match_high_roi_flag": _normalize_text(decision.get("high_roi_flag", "")),
    }


def _build_evidence_pack(
    review_df: pd.DataFrame,
    title_match_df: pd.DataFrame,
    supplier_index: dict[tuple[str, str], dict[str, str]],
    observed_utc: str,
) -> pd.DataFrame:
    by_candidate, by_supplier_asin = _title_match_indexes(title_match_df)
    rows: list[dict[str, str]] = []
    for _, row in review_df.iterrows():
        title_match = _find_title_match(row, by_candidate, by_supplier_asin)
        supplier = _supplier_record(row, supplier_index)
        title_fields = _title_match_fields(row, title_match, supplier)
        expected_profit = title_fields["expected_profit_gbp"] or _first_float_text(row, ["expected_profit_next_30d_gbp", "estimated_monthly_profit_gbp", "review_priority_score"])
        profit_per_unit = title_fields["profit_per_unit_gbp"] or _first_float_text(row, ["profit_per_unit_30d_gbp", "corrected_profit_per_unit_gbp"])
        evidence = {
            "observed_utc": observed_utc,
            "source_review_pack_type": _normalize_text(row.get("source_review_pack_type", "")),
            "active_supplier_id": _normalize_text(row.get("active_supplier_id", "")),
            "active_run_id": _normalize_text(row.get("active_run_id", "")),
            "review_batch_id": _normalize_text(row.get("review_batch_id", "")),
            "candidate_id": _normalize_text(row.get("candidate_id", "")),
            "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
            "asin": _normalize_text(row.get("asin", "")),
            **title_fields,
            "amazon_product_detail_text": _first_text(row, ["amazon_product_detail_text", "product_detail_text"]),
            "amazon_product_description": _first_text(row, ["amazon_product_description", "product_description"]),
            "amazon_feature_bullets": _first_text(row, ["amazon_feature_bullets", "product_feature_bullets"]),
            "amazon_sell_price_gbp": _first_float_text(row, ["bbp_final_sell_price", "bbp_live_sell_price", "api_live_price"]),
            "profit_per_unit_gbp": profit_per_unit,
            "expected_profit_gbp": expected_profit,
            "review_priority_score": _normalize_text(row.get("review_priority_score", "")),
            "main_rank": _normalize_text(row.get("main_rank", "")),
            "expected_units_next_30d": _normalize_text(row.get("expected_units_next_30d", "")),
            "sales_lower_30d": _normalize_text(row.get("sales_lower_30d", "")),
            "sales_upper_30d": _normalize_text(row.get("sales_upper_30d", "")),
            "current_review_state": _current_review_state(row),
            "current_gate_result": _current_gate_result(row),
            "near_miss_type": _normalize_text(row.get("near_miss_type", "")),
            "reviewability_state": _normalize_text(row.get("reviewability_state", "")),
            "screening_fail_code": _normalize_text(row.get("screening_fail_code", "")),
            "screening_status_reason": _normalize_text(row.get("screening_status_reason", "")),
            "seller_history_code": _normalize_text(row.get("seller_history_code", "")),
            "seller_history_recommended_action": _normalize_text(row.get("seller_history_recommended_action", "")),
            "seller_history_supporting_codes": _normalize_text(row.get("seller_history_supporting_codes", "")),
            "seller_history_evidence_source": _normalize_text(row.get("seller_history_evidence_source", "")),
            "seller_history_new_30": _normalize_text(row.get("seller_history_new_30", "")),
            "seller_history_new_90": _normalize_text(row.get("seller_history_new_90", "")),
            "seller_history_new_180": _normalize_text(row.get("seller_history_new_180", "")),
            "seller_history_dashboard_yes_or_no": _normalize_text(row.get("seller_history_dashboard_yes_or_no", "")),
            "seller_history_top_seller_names": _normalize_text(row.get("seller_history_top_seller_names", "")),
            "seller_history_rank_1_seller_name": _normalize_text(row.get("seller_history_rank_1_seller_name", "")),
            "seller_history_buybox_seller_name": _normalize_text(row.get("seller_history_buybox_seller_name", "")),
            "profit_formula_code": _normalize_text(row.get("profit_formula_code", "")),
            "profit_recommended_action": _normalize_text(row.get("profit_recommended_action", "")),
            "profit_evidence_source": _normalize_text(row.get("profit_evidence_source", "")),
            "demand_conflict_code": _normalize_text(row.get("demand_conflict_code", "")),
            "demand_recommended_action": _normalize_text(row.get("demand_recommended_action", "")),
            "demand_supporting_codes": _normalize_text(row.get("demand_supporting_codes", "")),
            "demand_evidence_source": _normalize_text(row.get("demand_evidence_source", "")),
            "history_risk_code": _normalize_text(row.get("history_risk_code", "")),
            "history_recommended_action": _normalize_text(row.get("history_recommended_action", "")),
            "history_supporting_codes": _normalize_text(row.get("history_supporting_codes", "")),
            "history_evidence_source": _normalize_text(row.get("history_evidence_source", "")),
            "uk_review_code": _normalize_text(row.get("uk_review_code", "")),
            "uk_review_recommended_action": _normalize_text(row.get("uk_review_recommended_action", "")),
            "uk_review_supporting_codes": _normalize_text(row.get("uk_review_supporting_codes", "")),
            "uk_review_evidence_source": _normalize_text(row.get("uk_review_evidence_source", "")),
            "review_memory_decision": _normalize_text(row.get("review_memory_decision", "")),
            "review_memory_note": _normalize_text(row.get("review_memory_note", "")),
            "why_data_summary": _normalize_text(row.get("why_data_summary", "")),
            "watch_data_summary": _normalize_text(row.get("watch_data_summary", "")),
            "commercial_note": _normalize_text(row.get("commercial_note", "")),
        }
        rows.append(evidence)
    return pd.DataFrame(rows, columns=EVIDENCE_COLUMNS).fillna("")


def _candidate(
    action: str,
    bucket: str,
    category: str,
    confidence: str,
    reason: str,
    evidence: str,
    rule_tightening: str,
) -> dict[str, str]:
    return {
        "action": action,
        "bucket": bucket,
        "category": category,
        "confidence": confidence,
        "reason": reason,
        "evidence": evidence,
        "rule_tightening": rule_tightening,
    }


def _action_from_recommended(value: str) -> str:
    action = _normalize_text(value)
    if action in {"remove_from_clean_pass", "manual_review"}:
        return action
    if action in {"targeted_rescan_needed", "missing_evidence_only"}:
        return "rescan_needed"
    return ""


def _select_decision(evidence: pd.Series | dict[str, Any]) -> dict[str, str]:
    candidates: list[dict[str, str]] = []

    if _normalize_text(evidence.get("review_memory_decision", "")).lower() == "fail":
        candidates.append(
            _candidate(
                "remove_from_clean_pass",
                "known_user_fail",
                "known_user_feedback_fail",
                "high",
                "User already failed this product in review memory.",
                _normalize_text(evidence.get("review_memory_note", "")),
                "use_review_feedback_memory_earlier",
            )
        )

    title_action = _normalize_text(evidence.get("title_match_action", ""))
    if title_action in {"remove_from_clean_pass", "manual_review"}:
        category = "product_identity_title_or_roi"
        title_bucket = _normalize_text(evidence.get("title_match_decision_bucket", ""))
        if "pack" in title_bucket or "quantity" in title_bucket:
            category = "pack_size_or_quantity"
        confirmed_quantity, confirmed_evidence = _page_text_confirms_supplier_quantity(evidence)
        combined_clear, combined_evidence = _combined_amazon_text_confirms_same_product(evidence)
        if title_action == "manual_review" and combined_clear:
            bucket = "pack_size_confirmed_by_page_evidence" if category == "pack_size_or_quantity" and confirmed_quantity else "same_product_confirmed_by_combined_amazon_text"
            reason = (
                "Amazon title and page text describe the same product as the supplier title, so the title-only warning is cleared."
            )
            if category == "pack_size_or_quantity" and confirmed_quantity:
                reason = "Amazon page evidence confirms the supplier pack quantity, so the title-only pack warning is cleared."
            candidates.append(
                _candidate(
                    "allow_if_other_checks_pass",
                    bucket,
                    "ai_review_clear",
                    "high",
                    reason,
                    f"{combined_evidence}|title_evidence={_normalize_text(evidence.get('title_match_evidence', ''))}",
                    "",
                )
            )
        else:
            candidates.append(
                _candidate(
                    title_action,
                    title_bucket or "title_match_review",
                    category,
                    _normalize_text(evidence.get("title_match_confidence", "")) or "medium",
                    _normalize_text(evidence.get("title_match_reason_code", "")) or "Title match check needs action.",
                    _normalize_text(evidence.get("title_match_evidence", "")),
                    "tighten_title_pack_roi_rules" if title_action == "remove_from_clean_pass" else "collect_more_title_examples",
                )
            )

    for prefix, category, rule in [
        ("seller_history", "seller_control_or_brand_owner_risk", "tighten_seller_ownership_gate"),
        ("profit", "profit_or_roi_risk", "tighten_profit_or_roi_gate"),
        ("demand", "demand_or_stock_evidence_conflict", "tighten_demand_or_stock_gate"),
        ("history", "history_risk", "tighten_history_risk_gate"),
        ("uk_review", "review_or_variant_risk", "tighten_review_variant_gate"),
    ]:
        action = _action_from_recommended(evidence.get(f"{prefix}_recommended_action", ""))
        if not action:
            continue
        code_field = f"{prefix}_code" if prefix != "history" else "history_risk_code"
        if prefix == "profit":
            code_field = "profit_formula_code"
        bucket = _normalize_text(evidence.get(code_field, "")) or f"{prefix}_review"
        candidates.append(
            _candidate(
                action,
                bucket,
                category,
                "high" if action == "remove_from_clean_pass" else "medium",
                f"{prefix} check returned {action}.",
                _normalize_text(evidence.get(f"{prefix}_supporting_codes", "")) or _normalize_text(evidence.get(f"{prefix}_evidence_source", "")),
                rule,
            )
        )

    current_state = _normalize_text(evidence.get("current_review_state", ""))
    if current_state == "evidence_gap_or_rescan":
        candidates.append(
            _candidate(
                "rescan_needed",
                "missing_evidence_rescan_needed",
                "missing_evidence_rescan_needed",
                "medium",
                "Evidence is incomplete, so the product should be rescanned before user review.",
                _normalize_text(evidence.get("current_gate_result", "")),
                "improve_evidence_capture_before_review",
            )
        )
    elif current_state == "already_removed_from_clean_pass":
        candidates.append(
            _candidate(
                "remove_from_clean_pass",
                _normalize_text(evidence.get("near_miss_type", "")) or "already_removed_from_clean_pass",
                "already_removed_by_existing_gate",
                "high",
                "Existing upstream gate already removed this from clean Pass.",
                _normalize_text(evidence.get("screening_fail_code", "")),
                "review_existing_gate_for_earlier_detection",
            )
        )

    if not candidates:
        return _candidate(
            "allow_if_other_checks_pass",
            "ai_review_clear",
            "ai_review_clear",
            "medium",
            "F032 found no interpretive blocker in the available evidence.",
            "",
            "",
        )

    return min(candidates, key=lambda item: (ACTION_PRIORITY.get(item["action"], 999), item["category"], item["bucket"]))


def _build_decisions(evidence_df: pd.DataFrame, observed_utc: str) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for _, evidence in evidence_df.iterrows():
        decision = _select_decision(evidence)
        action = decision["action"]
        supplier_id = _normalize_text(evidence.get("active_supplier_id", ""))
        run_id = _normalize_text(evidence.get("active_run_id", ""))
        pack_type = _normalize_text(evidence.get("source_review_pack_type", ""))
        candidate_id = _normalize_text(evidence.get("candidate_id", ""))
        supplier_sku = _normalize_text(evidence.get("supplier_sku", ""))
        asin = _normalize_text(evidence.get("asin", ""))
        decision_id_source = "|".join(["F032", supplier_id, run_id, pack_type, candidate_id, supplier_sku, asin])
        decision_id = hashlib.sha1(decision_id_source.encode("utf-8")).hexdigest()[:16]
        rows.append(
            {
                "observed_utc": observed_utc,
                "f032_decision_id": f"f032_{decision_id}",
                "source_review_pack_type": pack_type,
                "active_supplier_id": supplier_id,
                "active_run_id": run_id,
                "review_batch_id": _normalize_text(evidence.get("review_batch_id", "")),
                "candidate_id": candidate_id,
                "supplier_sku": supplier_sku,
                "asin": asin,
                "supplier_title": _normalize_text(evidence.get("supplier_title", "")),
                "amazon_title": _normalize_text(evidence.get("amazon_title", "")),
                "f032_action": action,
                "f032_decision_bucket": decision["bucket"],
                "f032_fail_category": "" if action == "allow_if_other_checks_pass" else decision["category"],
                "f032_confidence": decision["confidence"],
                "f032_needs_user_guidance": "1" if action == "manual_review" else "0",
                "f032_rescan_needed": "1" if action == "rescan_needed" else "0",
                "f032_rule_tightening_candidate": decision["rule_tightening"],
                "f032_reason": decision["reason"],
                "f032_evidence": decision["evidence"],
            }
        )
    return pd.DataFrame(rows, columns=DECISION_COLUMNS).fillna("")


def _status_from_action(action: str) -> str:
    action = _normalize_text(action)
    if action == "remove_from_clean_pass":
        return "fail"
    if action == "manual_review":
        return "manual_review"
    if action in {"rescan_needed", "targeted_rescan_needed", "missing_evidence_only"}:
        return "rescan_needed"
    return "pass"


def _check_reason(prefix: str, evidence: pd.Series | dict[str, Any], default_pass: str) -> tuple[str, str]:
    action = _action_from_recommended(evidence.get(f"{prefix}_recommended_action", ""))
    if action:
        code_field = f"{prefix}_code"
        if prefix == "history":
            code_field = "history_risk_code"
        if prefix == "profit":
            code_field = "profit_formula_code"
        reason = _normalize_text(evidence.get(code_field, "")) or _normalize_text(evidence.get(f"{prefix}_supporting_codes", ""))
        return _status_from_action(action), reason or f"{prefix} check returned {action}."
    return "pass", default_pass


def _build_checklist(evidence_df: pd.DataFrame, observed_utc: str) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for _, evidence in evidence_df.iterrows():
        title_action = _normalize_text(evidence.get("title_match_action", ""))
        title_bucket = _normalize_text(evidence.get("title_match_decision_bucket", ""))
        title_reason = _normalize_text(evidence.get("title_match_reason_code", "")) or "Title identity check found no blocker."
        title_status = _status_from_action(title_action)
        if not title_action:
            title_status = "pass"
        confirmed_quantity, confirmed_evidence = _page_text_confirms_supplier_quantity(evidence)
        combined_clear, combined_evidence = _combined_amazon_text_confirms_same_product(evidence)
        pack_or_quantity_bucket = "pack" in title_bucket or "quantity" in title_bucket
        if title_action == "manual_review" and combined_clear:
            title_status = "pass"
            title_reason = "Amazon title and page text describe the same product as the supplier title, so the title-only warning is cleared."
            if pack_or_quantity_bucket and confirmed_quantity:
                title_reason = "Amazon page evidence confirms the supplier pack quantity, so the title-only warning is cleared."

        pack_status = "pass"
        pack_reason = "No pack-size or quantity mismatch evidence found."
        if title_action == "manual_review" and pack_or_quantity_bucket and confirmed_quantity:
            pack_status = "pass"
            pack_reason = f"{confirmed_evidence}; title-only pack-size warning cleared by Amazon page evidence."
        elif title_action == "manual_review" and combined_clear:
            pack_status = "pass"
            pack_reason = f"{combined_evidence}; title-only warning cleared by combined Amazon title and page text."
        elif pack_or_quantity_bucket:
            pack_status = title_status
            pack_reason = title_reason
        elif "quantity_tokens_aligned" in _normalize_text(evidence.get("title_match_evidence", "")):
            pack_reason = "Quantity wording is aligned across supplier and Amazon titles."

        accessory_status = "pass"
        accessory_reason = "No accessory/refill/filter-vs-device conflict found."
        if "accessory" in title_bucket or "accessory_or_consumable_vs_device" in _normalize_text(evidence.get("title_match_evidence", "")):
            accessory_status = title_status
            accessory_reason = title_reason

        roi_status = "pass"
        roi_reason = "ROI/profit evidence did not create an interpretive blocker."
        if _normalize_text(evidence.get("title_match_high_roi_flag", "")) == "1" and title_action in {"remove_from_clean_pass", "manual_review"}:
            roi_status = title_status
            roi_reason = title_reason
        else:
            profit_status, profit_reason = _check_reason("profit", evidence, roi_reason)
            roi_status = profit_status
            roi_reason = profit_reason

        seller_status, seller_reason = _check_reason("seller_history", evidence, "Seller-control evidence found no blocker.")
        demand_status, demand_reason = _check_reason("demand", evidence, "Demand and stock evidence found no blocker.")
        history_status, history_reason = _check_reason("history", evidence, "History evidence found no blocker.")
        uk_review_status, uk_review_reason = _check_reason("uk_review", evidence, "UK review and variant evidence found no blocker.")

        review_variant_status = history_status
        review_variant_reason = history_reason
        if ACTION_PRIORITY.get(_normalize_text(evidence.get("uk_review_recommended_action", "")), 999) < ACTION_PRIORITY.get(_normalize_text(evidence.get("history_recommended_action", "")), 999):
            review_variant_status = uk_review_status
            review_variant_reason = uk_review_reason
        elif uk_review_status != "pass" and history_status == "pass":
            review_variant_status = uk_review_status
            review_variant_reason = uk_review_reason

        missing_status = "pass"
        missing_reason = "Required review evidence is present for this stage."
        if _normalize_text(evidence.get("current_review_state", "")) == "evidence_gap_or_rescan":
            missing_status = "rescan_needed"
            missing_reason = "Evidence is incomplete, so this should be rescanned before user review."
        elif _normalize_text(evidence.get("asin", "")) and not _normalize_text(evidence.get("amazon_title", "")):
            missing_status = "rescan_needed"
            missing_reason = "ASIN exists but Amazon title is missing."
        elif not _normalize_text(evidence.get("supplier_title", "")):
            missing_status = "manual_review"
            missing_reason = "Supplier title is missing, so product identity cannot be safely checked."

        rows.append(
            {
                "observed_utc": observed_utc,
                "source_review_pack_type": _normalize_text(evidence.get("source_review_pack_type", "")),
                "active_supplier_id": _normalize_text(evidence.get("active_supplier_id", "")),
                "active_run_id": _normalize_text(evidence.get("active_run_id", "")),
                "review_batch_id": _normalize_text(evidence.get("review_batch_id", "")),
                "candidate_id": _normalize_text(evidence.get("candidate_id", "")),
                "supplier_sku": _normalize_text(evidence.get("supplier_sku", "")),
                "asin": _normalize_text(evidence.get("asin", "")),
                "title_identity_status": title_status,
                "title_identity_reason": title_reason,
                "pack_size_quantity_status": pack_status,
                "pack_size_quantity_reason": pack_reason,
                "accessory_device_status": accessory_status,
                "accessory_device_reason": accessory_reason,
                "roi_suspicion_status": roi_status,
                "roi_suspicion_reason": roi_reason,
                "seller_control_status": seller_status,
                "seller_control_reason": seller_reason,
                "demand_evidence_status": demand_status,
                "demand_evidence_reason": demand_reason,
                "review_variant_status": review_variant_status,
                "review_variant_reason": review_variant_reason,
                "missing_evidence_status": missing_status,
                "missing_evidence_reason": missing_reason,
            }
        )
    return pd.DataFrame(rows, columns=CHECKLIST_COLUMNS).fillna("")


def _build_fail_categories(decision_df: pd.DataFrame, observed_utc: str) -> pd.DataFrame:
    if decision_df.empty:
        return pd.DataFrame(columns=["observed_utc", "f032_fail_category", "f032_action", "row_count", "example_supplier_sku", "example_asin", "rule_tightening_candidate"])
    work = decision_df[decision_df["f032_action"] != "allow_if_other_checks_pass"].copy()
    if work.empty:
        return pd.DataFrame(columns=["observed_utc", "f032_fail_category", "f032_action", "row_count", "example_supplier_sku", "example_asin", "rule_tightening_candidate"])
    rows: list[dict[str, str]] = []
    grouped = work.groupby(["f032_fail_category", "f032_action"], dropna=False)
    for (category, action), group in grouped:
        first = group.iloc[0]
        rows.append(
            {
                "observed_utc": observed_utc,
                "f032_fail_category": _normalize_text(category),
                "f032_action": _normalize_text(action),
                "row_count": str(len(group.index)),
                "example_supplier_sku": _normalize_text(first.get("supplier_sku", "")),
                "example_asin": _normalize_text(first.get("asin", "")),
                "rule_tightening_candidate": _normalize_text(first.get("f032_rule_tightening_candidate", "")),
            }
        )
    return pd.DataFrame(rows)


def _suggestion_for_category(category: str) -> dict[str, str]:
    suggestions = {
        "known_user_feedback_fail": {
            "evidence": "review memory decision",
            "rule": "Apply latest user fail memory before clean Pass is built.",
            "benefit": "Stops previously failed SKUs reaching the user again.",
            "risk": "low when latest pass feedback can override stale fail feedback",
            "readiness": "safe_to_automate",
        },
        "product_identity_title_or_roi": {
            "evidence": "supplier title, Amazon title, and ROI/profit clue",
            "rule": "Block suspicious title matches when ROI/profit is extreme; send weaker title uncertainty to manual review.",
            "benefit": "Catches wrong-product barcode matches before user review.",
            "risk": "medium because some categories need more examples",
            "readiness": "needs_more_examples",
        },
        "pack_size_or_quantity": {
            "evidence": "pack-size and quantity wording in supplier and Amazon titles",
            "rule": "Treat conflicting pack quantities as risk, but treat equivalent wording such as pc and pieces as aligned.",
            "benefit": "Reduces false pass on multipacks and false manual review on equivalent wording.",
            "risk": "medium until CLF food/drink examples are added",
            "readiness": "needs_more_examples",
        },
        "seller_control_or_brand_owner_risk": {
            "evidence": "seller rank, buy box seller, and seller history fields",
            "rule": "Block proven brand-owner or Amazon-controlled listings earlier in F019.",
            "benefit": "Reduces products that look profitable but are controlled by the brand or Amazon.",
            "risk": "medium when ownership is inferred only from names",
            "readiness": "needs_more_examples",
        },
        "demand_or_stock_evidence_conflict": {
            "evidence": "demand range, seller count, stock, and demand support fields",
            "rule": "Require demand support and stock evidence before clean Pass.",
            "benefit": "Stops weak-demand opportunities being presented as clean.",
            "risk": "medium because missing stock evidence can be a scrape issue",
            "readiness": "needs_more_examples",
        },
        "history_risk": {
            "evidence": "sales history and Amazon price-history risk fields",
            "rule": "Apply proven poor-history and below-break-even history rules before user review.",
            "benefit": "Removes products with historically weak or risky sales patterns.",
            "risk": "low for proven below-break-even evidence, medium for borderline recovery rows",
            "readiness": "needs_more_examples",
        },
        "review_or_variant_risk": {
            "evidence": "UK review count, variant review signal, and review quality fields",
            "rule": "Hold weak UK review or risky variant evidence for review or rescan.",
            "benefit": "Avoids sending risky or poorly reviewed variants to the user as clean.",
            "risk": "medium because review interpretation can be category-specific",
            "readiness": "needs_more_examples",
        },
        "missing_evidence_rescan_needed": {
            "evidence": "missing required title, price, demand, review, or scrape evidence",
            "rule": "Send incomplete rows to targeted rescan before user review.",
            "benefit": "Prevents the user being asked to judge products without enough facts.",
            "risk": "low; main cost is extra scanning",
            "readiness": "safe_to_automate",
        },
        "already_removed_by_existing_gate": {
            "evidence": "existing gate state",
            "rule": "Keep existing removal categories auditable and avoid sending them forward.",
            "benefit": "Maintains traceability for rows already removed upstream.",
            "risk": "low",
            "readiness": "safe_to_automate",
        },
        "profit_or_roi_risk": {
            "evidence": "profit formula, cost, ROI, and expected profit fields",
            "rule": "Hold missing or suspicious profit evidence before clean Pass.",
            "benefit": "Avoids passing rows where profit is likely overstated or unproven.",
            "risk": "medium because some profit issues need source correction rather than removal",
            "readiness": "needs_more_examples",
        },
    }
    return suggestions.get(
        category,
        {
            "evidence": "F032 decision evidence",
            "rule": "Collect more examples before automating this category.",
            "benefit": "Improves future upstream routing without guessing.",
            "risk": "unknown",
            "readiness": "needs_more_examples",
        },
    )


def _build_rule_suggestions(fail_category_df: pd.DataFrame, observed_utc: str) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    if fail_category_df.empty:
        return pd.DataFrame(columns=RULE_SUGGESTION_COLUMNS)
    for _, row in fail_category_df.iterrows():
        category = _normalize_text(row.get("f032_fail_category", ""))
        suggestion = _suggestion_for_category(category)
        readiness = suggestion["readiness"]
        rows.append(
            {
                "observed_utc": observed_utc,
                "f032_fail_category": category,
                "row_count": _normalize_text(row.get("row_count", "")),
                "example_supplier_sku": _normalize_text(row.get("example_supplier_sku", "")),
                "example_asin": _normalize_text(row.get("example_asin", "")),
                "evidence_that_caught_it": suggestion["evidence"],
                "proposed_earlier_rule": suggestion["rule"],
                "expected_benefit": suggestion["benefit"],
                "false_fail_risk": suggestion["risk"],
                "automation_readiness": readiness,
                "needs_more_examples": "1" if readiness == "needs_more_examples" else "0",
            }
        )
    return pd.DataFrame(rows, columns=RULE_SUGGESTION_COLUMNS).fillna("")


def _build_health(
    evidence_df: pd.DataFrame,
    decision_df: pd.DataFrame,
    checklist_df: pd.DataFrame,
    rule_suggestion_df: pd.DataFrame,
    observed_utc: str,
) -> pd.DataFrame:
    rows: list[dict[str, str]] = []

    def add(metric: str, value: int | str, status: str, detail: str = "") -> None:
        rows.append({"observed_utc": observed_utc, "metric": metric, "value": str(value), "status": status, "detail": detail})

    evidence_rows = len(evidence_df.index)
    decision_rows = len(decision_df.index)
    add("evidence_rows", evidence_rows, "PASS")
    add("decision_rows", decision_rows, "PASS" if decision_rows == evidence_rows else "FAIL")
    add("checklist_rows", len(checklist_df.index), "PASS" if len(checklist_df.index) == evidence_rows else "FAIL")
    add("rule_suggestion_rows", len(rule_suggestion_df.index), "PASS")

    if evidence_df.empty:
        add("missing_supplier_sku_rows", 0, "PASS")
        add("missing_supplier_title_rows", 0, "PASS")
        add("missing_amazon_title_with_asin_rows", 0, "PASS")
    else:
        missing_sku = int(evidence_df["supplier_sku"].map(_normalize_text).eq("").sum())
        missing_supplier_title = int(evidence_df["supplier_title"].map(_normalize_text).eq("").sum())
        missing_amazon_with_asin = int(
            (
                evidence_df["amazon_title"].map(_normalize_text).eq("")
                & evidence_df["asin"].map(_normalize_text).ne("")
            ).sum()
        )
        add("missing_supplier_sku_rows", missing_sku, "FAIL" if missing_sku else "PASS")
        add("missing_supplier_title_rows", missing_supplier_title, "WARN" if missing_supplier_title else "PASS")
        add("missing_amazon_title_with_asin_rows", missing_amazon_with_asin, "FAIL" if missing_amazon_with_asin else "PASS")

    if decision_df.empty:
        add("blank_decision_bucket_rows", 0, "PASS")
        add("invalid_action_rows", 0, "PASS")
        add("direct_promote_rows", 0, "PASS")
        add("fail_without_category_rows", 0, "PASS")
        add("manual_without_reason_rows", 0, "PASS")
    else:
        blank_bucket = int(decision_df["f032_decision_bucket"].map(_normalize_text).eq("").sum())
        invalid_actions = int((~decision_df["f032_action"].isin(VALID_F032_ACTIONS)).sum())
        direct_promote = int(decision_df["f032_action"].eq("final_pass").sum())
        fail_without_category = int(
            (
                decision_df["f032_action"].ne("allow_if_other_checks_pass")
                & decision_df["f032_fail_category"].map(_normalize_text).eq("")
            ).sum()
        )
        manual_without_reason = int(
            (
                decision_df["f032_action"].eq("manual_review")
                & decision_df["f032_reason"].map(_normalize_text).eq("")
            ).sum()
        )
        add("blank_decision_bucket_rows", blank_bucket, "FAIL" if blank_bucket else "PASS")
        add("invalid_action_rows", invalid_actions, "FAIL" if invalid_actions else "PASS")
        add("direct_promote_rows", direct_promote, "FAIL" if direct_promote else "PASS")
        add("fail_without_category_rows", fail_without_category, "FAIL" if fail_without_category else "PASS")
        add("manual_without_reason_rows", manual_without_reason, "FAIL" if manual_without_reason else "PASS")
        for action, count in decision_df["f032_action"].value_counts(dropna=False).sort_index().items():
            add(f"action::{action}", int(count), "PASS")
    if checklist_df.empty:
        add("blank_checklist_status_rows", 0, "PASS")
        add("blank_checklist_reason_rows", 0, "PASS")
    else:
        status_cols = [col for col in checklist_df.columns if col.endswith("_status")]
        reason_cols = [col for col in checklist_df.columns if col.endswith("_reason")]
        blank_status_rows = int(checklist_df[status_cols].apply(lambda row: any(_normalize_text(value) == "" for value in row), axis=1).sum())
        blank_reason_rows = int(checklist_df[reason_cols].apply(lambda row: any(_normalize_text(value) == "" for value in row), axis=1).sum())
        add("blank_checklist_status_rows", blank_status_rows, "FAIL" if blank_status_rows else "PASS")
        add("blank_checklist_reason_rows", blank_reason_rows, "FAIL" if blank_reason_rows else "PASS")
    return pd.DataFrame(rows)


def _write_snapshot(latest_path: Path, df: pd.DataFrame, observed_utc: str) -> Path:
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(latest_path, index=False)
    stamp = _timestamp_for_file(observed_utc)
    snapshot_path = latest_path.with_name(latest_path.name.replace("_latest", f"_{stamp}"))
    df.to_csv(snapshot_path, index=False)
    return snapshot_path


def _write_summary(path: Path, report: dict[str, Any], health_df: pd.DataFrame) -> None:
    lines = [
        "# F032 Review Intelligence Summary",
        "",
        f"- observed_utc: `{report['observed_utc']}`",
        f"- evidence_rows: `{report['evidence_rows']}`",
        f"- decision_rows: `{report['decision_rows']}`",
        f"- checklist_rows: `{report['checklist_rows']}`",
        f"- rule_suggestion_rows: `{report['rule_suggestion_rows']}`",
        f"- remove_from_clean_pass_rows: `{report['remove_from_clean_pass_rows']}`",
        f"- manual_review_rows: `{report['manual_review_rows']}`",
        f"- rescan_needed_rows: `{report['rescan_needed_rows']}`",
        f"- allow_if_other_checks_pass_rows: `{report['allow_if_other_checks_pass_rows']}`",
        "",
        "## Health",
        "",
    ]
    for row in health_df.to_dict("records"):
        lines.append(f"- {row['metric']}: `{row['value']}` ({row['status']})")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_review_intelligence_cycle(
    *,
    pass_review_path: Path = DEFAULT_PASS_REVIEW_PATH,
    near_miss_review_path: Path = DEFAULT_NEAR_MISS_REVIEW_PATH,
    title_match_path: Path = DEFAULT_TITLE_MATCH_PATH,
    supplier_inbox_dir: Path = DEFAULT_SUPPLIER_INBOX_DIR,
    evidence_output_path: Path = DEFAULT_EVIDENCE_OUTPUT_PATH,
    decision_output_path: Path = DEFAULT_DECISION_OUTPUT_PATH,
    fail_category_output_path: Path = DEFAULT_FAIL_CATEGORY_OUTPUT_PATH,
    checklist_output_path: Path = DEFAULT_CHECKLIST_OUTPUT_PATH,
    rule_suggestion_output_path: Path = DEFAULT_RULE_SUGGESTION_OUTPUT_PATH,
    health_output_path: Path = DEFAULT_HEALTH_OUTPUT_PATH,
    summary_output_path: Path = DEFAULT_SUMMARY_OUTPUT_PATH,
    observed_utc: str | None = None,
    write_outputs: bool = True,
) -> F032Result:
    observed = observed_utc or _utc_now_iso()
    review_df = _combine_review_inputs(pass_review_path, near_miss_review_path)
    title_match_df = _read_csv(title_match_path)
    supplier_index = _merge_supplier_title_indexes(
        _load_supplier_title_index(supplier_inbox_dir),
        _load_handoff_source_title_index([pass_review_path, near_miss_review_path]),
    )
    evidence_df = _build_evidence_pack(review_df, title_match_df, supplier_index, observed)
    decision_df = _build_decisions(evidence_df, observed)
    fail_category_df = _build_fail_categories(decision_df, observed)
    checklist_df = _build_checklist(evidence_df, observed)
    rule_suggestion_df = _build_rule_suggestions(fail_category_df, observed)
    health_df = _build_health(evidence_df, decision_df, checklist_df, rule_suggestion_df, observed)

    report = {
        "observed_utc": observed,
        "evidence_rows": int(len(evidence_df.index)),
        "decision_rows": int(len(decision_df.index)),
        "checklist_rows": int(len(checklist_df.index)),
        "rule_suggestion_rows": int(len(rule_suggestion_df.index)),
        "remove_from_clean_pass_rows": int(decision_df["f032_action"].eq("remove_from_clean_pass").sum()) if not decision_df.empty else 0,
        "manual_review_rows": int(decision_df["f032_action"].eq("manual_review").sum()) if not decision_df.empty else 0,
        "rescan_needed_rows": int(decision_df["f032_action"].eq("rescan_needed").sum()) if not decision_df.empty else 0,
        "allow_if_other_checks_pass_rows": int(decision_df["f032_action"].eq("allow_if_other_checks_pass").sum()) if not decision_df.empty else 0,
        "health_fail_rows": int(health_df["status"].eq("FAIL").sum()) if not health_df.empty else 0,
        "health_warn_rows": int(health_df["status"].eq("WARN").sum()) if not health_df.empty else 0,
    }

    if write_outputs:
        _write_snapshot(evidence_output_path, evidence_df, observed)
        _write_snapshot(decision_output_path, decision_df, observed)
        _write_snapshot(fail_category_output_path, fail_category_df, observed)
        _write_snapshot(checklist_output_path, checklist_df, observed)
        _write_snapshot(rule_suggestion_output_path, rule_suggestion_df, observed)
        _write_snapshot(health_output_path, health_df, observed)
        _write_summary(summary_output_path, report, health_df)

    return F032Result(
        evidence_df=evidence_df,
        decision_df=decision_df,
        fail_category_df=fail_category_df,
        checklist_df=checklist_df,
        rule_suggestion_df=rule_suggestion_df,
        health_df=health_df,
        report=report,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build F032 Review Intelligence Cycle evidence and decisions.")
    parser.add_argument("--pass-review-path", type=Path, default=DEFAULT_PASS_REVIEW_PATH)
    parser.add_argument("--near-miss-review-path", type=Path, default=DEFAULT_NEAR_MISS_REVIEW_PATH)
    parser.add_argument("--title-match-path", type=Path, default=DEFAULT_TITLE_MATCH_PATH)
    parser.add_argument("--supplier-inbox-dir", type=Path, default=DEFAULT_SUPPLIER_INBOX_DIR)
    parser.add_argument("--evidence-output-path", type=Path, default=DEFAULT_EVIDENCE_OUTPUT_PATH)
    parser.add_argument("--decision-output-path", type=Path, default=DEFAULT_DECISION_OUTPUT_PATH)
    parser.add_argument("--fail-category-output-path", type=Path, default=DEFAULT_FAIL_CATEGORY_OUTPUT_PATH)
    parser.add_argument("--checklist-output-path", type=Path, default=DEFAULT_CHECKLIST_OUTPUT_PATH)
    parser.add_argument("--rule-suggestion-output-path", type=Path, default=DEFAULT_RULE_SUGGESTION_OUTPUT_PATH)
    parser.add_argument("--health-output-path", type=Path, default=DEFAULT_HEALTH_OUTPUT_PATH)
    parser.add_argument("--summary-output-path", type=Path, default=DEFAULT_SUMMARY_OUTPUT_PATH)
    parser.add_argument("--observed-utc", default="")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = build_review_intelligence_cycle(
        pass_review_path=args.pass_review_path,
        near_miss_review_path=args.near_miss_review_path,
        title_match_path=args.title_match_path,
        supplier_inbox_dir=args.supplier_inbox_dir,
        evidence_output_path=args.evidence_output_path,
        decision_output_path=args.decision_output_path,
        fail_category_output_path=args.fail_category_output_path,
        checklist_output_path=args.checklist_output_path,
        rule_suggestion_output_path=args.rule_suggestion_output_path,
        health_output_path=args.health_output_path,
        summary_output_path=args.summary_output_path,
        observed_utc=_normalize_text(args.observed_utc) or None,
    )
    print(json.dumps(result.report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
