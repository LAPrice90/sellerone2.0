from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from scripts.flows.F._contract_io import write_f_contract_df
from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract
from scripts.flows.F._profit_model import calculate_fee_based_profit_per_unit
from scripts.flows.F._schemas import get_f_output_column_types, get_f_output_contract
from scripts.flows.F._source_contracts import get_source_contract


MANDATORY_SOURCE_KEYS: tuple[str, ...] = (
    "feeder_legacy_chart_daily_raw_live",
    "feeder_backtest_policy_live",
)

OPTIONAL_SOURCE_KEYS: tuple[str, ...] = (
    "supplier_price_list_universal_live",
    "product_db_preview",
    "sku_sales_velocity",
    "sku_performance_summary",
    "listing_offer_snapshot_latest",
    "feeder_legacy_scrape_evidence_live",
    "feeder_legacy_first_checks_live",
)

PRICE_COLUMNS: tuple[str, ...] = (
    "amazon_price_raw",
    "fba_price_raw",
    "fbm_price_raw",
    "buy_box_price_raw",
    "price_chosen_processed",
)

ASIN_RESOLUTION_REL_PATH = Path("config") / "f_backtest_asin_resolution.csv"
ASIN_RESOLUTION_REQUIRED_COLUMNS: tuple[str, ...] = (
    "asin",
    "seller_sku",
    "resolution_status",
    "resolution_reason",
    "resolution_source",
    "approved_utc",
)

CONFIDENCE_ORDER: dict[str, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
}


@dataclass(frozen=True)
class SourceReadResult:
    key: str
    path: Path
    df: pd.DataFrame
    file_missing: bool
    missing_columns: tuple[str, ...]


@dataclass(frozen=True)
class PriceQualificationResult:
    qualified_units_monthly: float | None
    qualified_profit_monthly_gbp: float | None
    price_qualification_reason_codes: str
    qualification_market_gate_state: str
    qualification_market_gate_factor: float | None
    qualification_amazon_pressure_factor: float | None
    qualification_buy_box_coverage_factor: float | None
    qualification_maturity_factor: float | None
    qualification_final_factor: float | None
    qualification_zero_or_block_reason: str


@dataclass(frozen=True)
class ClassifierStateResult:
    seasonality_state: str
    seasonality_reason_codes: str
    stability_state: str
    stability_reason_codes: str
    recent_vs_baseline_state: str
    recent_vs_baseline_reason_codes: str
    completed_months_count: int


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _num_or_none(value: object) -> float | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    cleaned = raw.replace(",", "").replace("GBP", "").replace("gbp", "").replace("PS", "").replace("ps", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _num_to_text(value: float | None) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _contract_columns(contract_name: str) -> list[str]:
    contract = get_f_output_contract(contract_name)
    return [*contract.required_columns, *contract.optional_columns]


def _finalize_contract_df(df: pd.DataFrame, contract_name: str) -> pd.DataFrame:
    ordered = _contract_columns(contract_name)
    out = df.copy()
    for column in ordered:
        if column not in out.columns:
            out[column] = ""
    out = out[ordered]
    for column in ordered:
        out[column] = out[column].map(_normalize_text)
    return out


def _type_mismatch_columns(df: pd.DataFrame, contract_name: str) -> list[str]:
    expected_types = get_f_output_column_types(contract_name)
    mismatches: list[str] = []
    for column, expected in expected_types.items():
        if expected == "string" and column in df.columns and not pd.api.types.is_object_dtype(df[column]):
            mismatches.append(column)
    return mismatches


def _write_contract_df(df: pd.DataFrame, contract_name: str, root_path: Path) -> pd.DataFrame:
    finalized = _finalize_contract_df(df, contract_name)
    mismatches = _type_mismatch_columns(finalized, contract_name)
    if mismatches:
        mismatch_text = ",".join(sorted(mismatches))
        raise ValueError(f"{contract_name} type mismatch for string columns: {mismatch_text}")
    out_path = root_path / get_f_output_contract(contract_name).rel_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_f_contract_df(root_path, contract_name, finalized)
    return finalized


def _read_source(root_path: Path, source_key: str) -> SourceReadResult:
    source_contract = get_source_contract(source_key)
    source_path = root_path / source_contract.source_path
    if not source_path.exists():
        return SourceReadResult(
            key=source_key,
            path=source_path,
            df=pd.DataFrame(),
            file_missing=True,
            missing_columns=tuple(source_contract.required_columns),
        )
    df = pd.read_csv(source_path, dtype=str).fillna("")
    missing = tuple(col for col in source_contract.required_columns if col not in df.columns)
    return SourceReadResult(
        key=source_key,
        path=source_path,
        df=df,
        file_missing=False,
        missing_columns=missing,
    )


def _validate_sources(source_data: dict[str, SourceReadResult]) -> None:
    for source_key in MANDATORY_SOURCE_KEYS:
        result = source_data[source_key]
        if result.file_missing:
            raise FileNotFoundError(f"missing mandatory source: {source_key} at {result.path}")
        if result.missing_columns:
            missing = ",".join(result.missing_columns)
            raise ValueError(f"mandatory source {source_key} missing columns: {missing}")


def _read_asin_resolution_map(root_path: Path) -> dict[str, str]:
    resolver_path = root_path / ASIN_RESOLUTION_REL_PATH
    if not resolver_path.exists():
        return {}

    resolver_df = pd.read_csv(resolver_path, dtype=str).fillna("")
    missing = [col for col in ASIN_RESOLUTION_REQUIRED_COLUMNS if col not in resolver_df.columns]
    if missing:
        missing_text = ",".join(sorted(missing))
        raise ValueError(f"asin resolver missing columns: {missing_text}")

    work = resolver_df.copy()
    work["asin_norm"] = work.get("asin", "").map(_normalize_key)
    work["seller_sku_norm"] = work.get("seller_sku", "").map(_normalize_key)
    work["resolution_status_norm"] = work.get("resolution_status", "").map(lambda v: _normalize_text(v).lower())
    work = work[(work["asin_norm"] != "") & (work["seller_sku_norm"] != "")].copy()
    work = work[~work["resolution_status_norm"].isin({"inactive", "rejected", "ignore", "ignored"})].copy()
    if work.empty:
        return {}

    resolver_map: dict[str, str] = {}
    for asin_norm, group in work.groupby("asin_norm"):
        seller_skus = sorted({_normalize_key(v) for v in group["seller_sku_norm"].tolist() if _normalize_key(v) != ""})
        if len(seller_skus) == 0:
            continue
        if len(seller_skus) > 1:
            seller_text = ",".join(seller_skus)
            raise ValueError(f"asin resolver has conflicting seller_sku rows for asin {asin_norm}: {seller_text}")
        resolver_map[asin_norm] = seller_skus[0]
    return resolver_map


def _active_policy_row(policy_df: pd.DataFrame) -> pd.Series:
    active = policy_df[policy_df.get("policy_status", "").map(lambda v: _normalize_text(v).lower() == "active")]
    if len(active.index) != 1:
        raise ValueError(f"expected exactly 1 active policy row, found {len(active.index)}")
    return active.iloc[0]


def _aggregate_asin_day(raw_df: pd.DataFrame) -> pd.DataFrame:
    work = raw_df.copy()
    work["asin_norm"] = work.get("asin", "").map(_normalize_key)
    work["day_date"] = pd.to_datetime(work.get("day", ""), errors="coerce").dt.date
    work = work[(work["asin_norm"] != "") & work["day_date"].notna()]
    if work.empty:
        return pd.DataFrame(columns=["asin_norm", "day_date"])

    for col in PRICE_COLUMNS:
        work[f"{col}_num"] = work.get(col, "").map(_num_or_none)
    work["bsr_raw_num"] = work.get("bsr_raw", "").map(_num_or_none)

    def agg_min(series: pd.Series) -> float | None:
        vals = [float(v) for v in series if pd.notna(v)]
        if not vals:
            return None
        return min(vals)

    def agg_median(series: pd.Series) -> float | None:
        vals = [float(v) for v in series if pd.notna(v)]
        if not vals:
            return None
        return float(pd.Series(vals).median())

    grouped = (
        work.groupby(["asin_norm", "day_date"], as_index=False)
        .agg(
            amazon_price_num=("amazon_price_raw_num", agg_min),
            fba_price_num=("fba_price_raw_num", agg_min),
            fbm_price_num=("fbm_price_raw_num", agg_min),
            buy_box_price_num=("buy_box_price_raw_num", agg_min),
            chosen_price_num=("price_chosen_processed_num", agg_median),
            bsr_num=("bsr_raw_num", agg_median),
        )
        .sort_values(["asin_norm", "day_date"], ascending=[True, True], kind="stable")
        .reset_index(drop=True)
    )

    grouped["amazon_present"] = grouped["amazon_price_num"].notna()
    grouped["fba_present"] = grouped["fba_price_num"].notna()
    grouped["fbm_present"] = grouped["fbm_price_num"].notna()
    grouped["buy_box_present"] = grouped["buy_box_price_num"].notna()
    grouped["market_price_day"] = grouped.apply(
        lambda row: row["chosen_price_num"]
        if pd.notna(row["chosen_price_num"])
        else row["buy_box_price_num"]
        if pd.notna(row["buy_box_price_num"])
        else row["fba_price_num"]
        if pd.notna(row["fba_price_num"])
        else row["fbm_price_num"]
        if pd.notna(row["fbm_price_num"])
        else row["amazon_price_num"]
        if pd.notna(row["amazon_price_num"])
        else None,
        axis=1,
    )
    return grouped


def _window_subset(asin_df: pd.DataFrame, days: int) -> pd.DataFrame:
    if asin_df.empty:
        return asin_df
    max_day = asin_df["day_date"].max()
    min_day = max_day - timedelta(days=days - 1)
    return asin_df[asin_df["day_date"] >= min_day]


def _window_median(asin_df: pd.DataFrame, *, days: int, column: str) -> float | None:
    window = _window_subset(asin_df, days)
    vals = [float(v) for v in window[column] if pd.notna(v)]
    if not vals:
        return None
    return float(pd.Series(vals).median())


def _presence_share(asin_df: pd.DataFrame, *, days: int, column: str) -> float:
    window = _window_subset(asin_df, days)
    if window.empty:
        return 0.0
    return float(window[column].mean())


def _seasonality_state(history_days: int) -> str:
    if history_days >= 365:
        return "full_year_history"
    if history_days >= 180:
        return "partial_year_history"
    if history_days >= 90:
        return "limited_history"
    return "sparse_history"


def _history_maturity_state(history_days: int) -> str:
    if history_days <= 0:
        return "no_history"
    if history_days < 90:
        return "recent_only"
    if history_days < 180:
        return "developing"
    if history_days < 365:
        return "stable"
    return "full_year"


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(pd.Series(values).median())


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _reason_token(reason: object) -> str:
    token = _normalize_text(reason).lower().replace(" ", "_").replace("-", "_")
    while "__" in token:
        token = token.replace("__", "_")
    return token.strip("_")


def _dedupe_reason_codes(reasons: list[str]) -> str:
    deduped: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        token = _reason_token(reason)
        if token == "" or token in seen:
            continue
        seen.add(token)
        deduped.append(token)
    return "|".join(deduped)


def _history_confidence(
    *,
    history_days: int,
    paired_buy_box_bsr_days: int,
    paired_fba_bsr_days: int,
    buy_box_coverage_share: float,
) -> str:
    if history_days >= 180 and paired_buy_box_bsr_days >= 90 and buy_box_coverage_share >= 0.6:
        return "high"
    if history_days >= 90 and (paired_buy_box_bsr_days >= 30 or paired_fba_bsr_days >= 30):
        return "medium"
    return "low"


def _clamp_confidence(value: str) -> str:
    normalized = _normalize_text(value).lower()
    if normalized in CONFIDENCE_ORDER:
        return normalized
    return "low"


def _min_confidence(left: str, right: str) -> str:
    left_norm = _clamp_confidence(left)
    right_norm = _clamp_confidence(right)
    if CONFIDENCE_ORDER[left_norm] <= CONFIDENCE_ORDER[right_norm]:
        return left_norm
    return right_norm


def _price_qualification(
    *,
    demand_basis_units_monthly: float | None,
    break_even_price_gbp: float | None,
    market_price_gbp: float | None,
    vat_rate_pct: float | None,
    product_cost_gbp: float | None,
    fba_fee_gbp: float | None,
    referral_fee_gbp: float | None,
    digital_fee_gbp: float | None,
    est_shipping_gbp: float | None,
    referral_fee_basis_price_gbp: float | None,
    amazon_presence_share_30d: float,
    buy_box_coverage_share: float,
    history_maturity_state: str,
) -> PriceQualificationResult:
    reasons: list[str] = []
    raw_units = demand_basis_units_monthly
    market_gate_state = "market_open"
    market_gate_factor = 1.0
    amazon_pressure_factor = 1.0
    buy_box_coverage_factor = 1.0
    maturity_factor = 1.0
    final_factor = 0.0
    zero_or_block_reason = ""
    if raw_units is None:
        market_gate_state = "missing_raw_demand_basis_units"
        market_gate_factor = 0.0
        zero_or_block_reason = market_gate_state
        reasons.append(market_gate_state)
        return PriceQualificationResult(
            qualified_units_monthly=None,
            qualified_profit_monthly_gbp=None,
            price_qualification_reason_codes="|".join(reasons),
            qualification_market_gate_state=market_gate_state,
            qualification_market_gate_factor=market_gate_factor,
            qualification_amazon_pressure_factor=amazon_pressure_factor,
            qualification_buy_box_coverage_factor=buy_box_coverage_factor,
            qualification_maturity_factor=maturity_factor,
            qualification_final_factor=final_factor,
            qualification_zero_or_block_reason=zero_or_block_reason,
        )

    raw_units = max(float(raw_units), 0.0)
    if raw_units <= 0:
        market_gate_state = "raw_demand_zero"
        market_gate_factor = 0.0
        zero_or_block_reason = market_gate_state
        reasons.append(market_gate_state)
        return PriceQualificationResult(
            qualified_units_monthly=0.0,
            qualified_profit_monthly_gbp=0.0,
            price_qualification_reason_codes="|".join(reasons),
            qualification_market_gate_state=market_gate_state,
            qualification_market_gate_factor=market_gate_factor,
            qualification_amazon_pressure_factor=amazon_pressure_factor,
            qualification_buy_box_coverage_factor=buy_box_coverage_factor,
            qualification_maturity_factor=maturity_factor,
            qualification_final_factor=final_factor,
            qualification_zero_or_block_reason=zero_or_block_reason,
        )

    if break_even_price_gbp is None or break_even_price_gbp <= 0:
        market_gate_state = "missing_break_even_price"
        market_gate_factor = 0.0
        zero_or_block_reason = market_gate_state
        reasons.append(market_gate_state)
        return PriceQualificationResult(
            qualified_units_monthly=None,
            qualified_profit_monthly_gbp=None,
            price_qualification_reason_codes="|".join(reasons),
            qualification_market_gate_state=market_gate_state,
            qualification_market_gate_factor=market_gate_factor,
            qualification_amazon_pressure_factor=amazon_pressure_factor,
            qualification_buy_box_coverage_factor=buy_box_coverage_factor,
            qualification_maturity_factor=maturity_factor,
            qualification_final_factor=final_factor,
            qualification_zero_or_block_reason=zero_or_block_reason,
        )
    if market_price_gbp is None or market_price_gbp <= 0:
        market_gate_state = "missing_market_price"
        market_gate_factor = 0.0
        zero_or_block_reason = market_gate_state
        reasons.append(market_gate_state)
        return PriceQualificationResult(
            qualified_units_monthly=None,
            qualified_profit_monthly_gbp=None,
            price_qualification_reason_codes="|".join(reasons),
            qualification_market_gate_state=market_gate_state,
            qualification_market_gate_factor=market_gate_factor,
            qualification_amazon_pressure_factor=amazon_pressure_factor,
            qualification_buy_box_coverage_factor=buy_box_coverage_factor,
            qualification_maturity_factor=maturity_factor,
            qualification_final_factor=final_factor,
            qualification_zero_or_block_reason=zero_or_block_reason,
        )
    if market_price_gbp <= break_even_price_gbp:
        market_gate_state = "market_below_break_even"
        market_gate_factor = 0.0
        zero_or_block_reason = market_gate_state
        reasons.append(market_gate_state)
        return PriceQualificationResult(
            qualified_units_monthly=0.0,
            qualified_profit_monthly_gbp=0.0,
            price_qualification_reason_codes="|".join(reasons),
            qualification_market_gate_state=market_gate_state,
            qualification_market_gate_factor=market_gate_factor,
            qualification_amazon_pressure_factor=amazon_pressure_factor,
            qualification_buy_box_coverage_factor=buy_box_coverage_factor,
            qualification_maturity_factor=maturity_factor,
            qualification_final_factor=final_factor,
            qualification_zero_or_block_reason=zero_or_block_reason,
        )

    fee_profit = calculate_fee_based_profit_per_unit(
        sale_price_gbp=market_price_gbp,
        vat_rate_pct=vat_rate_pct,
        product_cost_gbp=product_cost_gbp,
        fba_fee_gbp=fba_fee_gbp,
        referral_fee_gbp=referral_fee_gbp,
        digital_fee_gbp=digital_fee_gbp,
        est_shipping_gbp=est_shipping_gbp,
        referral_fee_basis_price_gbp=referral_fee_basis_price_gbp,
        recalculate_referral_fee=True,
        recalculate_digital_fee=True,
    )
    if fee_profit.profit_per_unit_gbp is None:
        market_gate_state = "missing_fee_cost_inputs"
        market_gate_factor = 0.0
        zero_or_block_reason = market_gate_state
        reasons.append(market_gate_state)
        for missing_key in fee_profit.missing_inputs:
            reasons.append(f"missing_{missing_key}")
        deduped_missing: list[str] = []
        seen_missing: set[str] = set()
        for reason in reasons:
            token = _normalize_text(reason)
            if token == "" or token in seen_missing:
                continue
            seen_missing.add(token)
            deduped_missing.append(token)
        return PriceQualificationResult(
            qualified_units_monthly=None,
            qualified_profit_monthly_gbp=None,
            price_qualification_reason_codes="|".join(deduped_missing),
            qualification_market_gate_state=market_gate_state,
            qualification_market_gate_factor=market_gate_factor,
            qualification_amazon_pressure_factor=amazon_pressure_factor,
            qualification_buy_box_coverage_factor=buy_box_coverage_factor,
            qualification_maturity_factor=maturity_factor,
            qualification_final_factor=final_factor,
            qualification_zero_or_block_reason=zero_or_block_reason,
        )

    fee_unit_profit = float(fee_profit.profit_per_unit_gbp)
    if fee_unit_profit <= 0:
        market_gate_state = "fee_based_profit_non_positive"
        market_gate_factor = 0.0
        zero_or_block_reason = market_gate_state
        reasons.append(market_gate_state)
        return PriceQualificationResult(
            qualified_units_monthly=0.0,
            qualified_profit_monthly_gbp=0.0,
            price_qualification_reason_codes="|".join(reasons),
            qualification_market_gate_state=market_gate_state,
            qualification_market_gate_factor=market_gate_factor,
            qualification_amazon_pressure_factor=amazon_pressure_factor,
            qualification_buy_box_coverage_factor=buy_box_coverage_factor,
            qualification_maturity_factor=maturity_factor,
            qualification_final_factor=final_factor,
            qualification_zero_or_block_reason=zero_or_block_reason,
        )

    if amazon_presence_share_30d >= 0.95:
        amazon_pressure_factor = 0.05
        reasons.append("amazon_dominant_30d")
    elif amazon_presence_share_30d >= 0.8:
        amazon_pressure_factor = 0.2
        reasons.append("amazon_heavy_30d")
    elif amazon_presence_share_30d >= 0.5:
        amazon_pressure_factor = 0.5
        reasons.append("amazon_moderate_30d")

    if buy_box_coverage_share < 0.3:
        buy_box_coverage_factor = 0.5
        reasons.append("buy_box_coverage_low")
    elif buy_box_coverage_share < 0.6:
        buy_box_coverage_factor = 0.8
        reasons.append("buy_box_coverage_medium")

    if history_maturity_state in {"no_history", "recent_only"}:
        maturity_factor = 0.8
        reasons.append("history_maturity_limited")

    final_factor = max(
        0.0,
        min(
            1.0,
            market_gate_factor * amazon_pressure_factor * buy_box_coverage_factor * maturity_factor,
        ),
    )
    qualified_units = max(0.0, min(raw_units, raw_units * final_factor))
    if qualified_units < 0.05:
        qualified_units = 0.0
        if raw_units > 0:
            zero_or_block_reason = "qualification_factor_reduced_to_zero"
            reasons.append(zero_or_block_reason)

    qualified_profit = qualified_units * fee_unit_profit
    if not reasons:
        reasons.append("qualified_full")
    deduped_reasons: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        token = _normalize_text(reason)
        if token == "" or token in seen:
            continue
        seen.add(token)
        deduped_reasons.append(token)
    return PriceQualificationResult(
        qualified_units_monthly=qualified_units,
        qualified_profit_monthly_gbp=qualified_profit,
        price_qualification_reason_codes="|".join(deduped_reasons),
        qualification_market_gate_state=market_gate_state,
        qualification_market_gate_factor=market_gate_factor,
        qualification_amazon_pressure_factor=amazon_pressure_factor,
        qualification_buy_box_coverage_factor=buy_box_coverage_factor,
        qualification_maturity_factor=maturity_factor,
        qualification_final_factor=final_factor,
        qualification_zero_or_block_reason=zero_or_block_reason,
    )


def _attribution_confidence(
    *,
    mapping_status: str,
    buy_box_coverage_share: float,
    amazon_presence_share_90d: float,
    paired_buy_box_bsr_days: int,
    paired_fba_bsr_days: int,
    product_row: pd.Series | None,
    legacy_row: pd.Series | None,
) -> tuple[str, list[str]]:
    level = "high"
    reasons: list[str] = []

    mapping_status_norm = _normalize_text(mapping_status)
    if mapping_status_norm == "multi_sku_asin_match":
        level = "low"
        reasons.append("attribution_identity_ambiguous")
    elif mapping_status_norm == "no_product_db_match":
        level = "low"
        reasons.append("attribution_identity_missing")
    elif mapping_status_norm == "legacy_asin_match":
        level = _min_confidence(level, "medium")
        reasons.append("attribution_identity_legacy_source")

    if product_row is None and legacy_row is not None:
        level = _min_confidence(level, "medium")
        reasons.append("attribution_identity_not_internal_sku")

    if buy_box_coverage_share < 0.3:
        level = "low"
        reasons.append("attribution_buy_box_coverage_low")
    elif buy_box_coverage_share < 0.6:
        level = _min_confidence(level, "medium")
        reasons.append("attribution_buy_box_coverage_medium")

    if paired_buy_box_bsr_days < 30 and paired_fba_bsr_days < 30:
        level = "low"
        reasons.append("attribution_channel_pairing_sparse")

    if amazon_presence_share_90d >= 0.95 and buy_box_coverage_share < 0.3:
        level = "low"
        reasons.append("attribution_amazon_dominant_90d")
    elif amazon_presence_share_90d >= 0.8 and buy_box_coverage_share < 0.6:
        level = _min_confidence(level, "medium")
        reasons.append("attribution_amazon_dominant_90d")

    deduped: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        if reason in seen:
            continue
        seen.add(reason)
        deduped.append(reason)
    return level, deduped


def _build_asin_features(asin_day_df: pd.DataFrame) -> dict[str, dict[str, object]]:
    features: dict[str, dict[str, object]] = {}
    for asin_norm, one_asin in asin_day_df.groupby("asin_norm"):
        asin_work = one_asin.sort_values("day_date", ascending=True, kind="stable").copy()
        history_days = int(len(asin_work.index))
        paired_buy_box_bsr_days = int((asin_work["buy_box_present"] & asin_work["bsr_num"].notna()).sum())
        paired_fba_bsr_days = int((asin_work["fba_present"] & asin_work["bsr_num"].notna()).sum())
        buy_box_coverage_share = float(asin_work["buy_box_present"].mean()) if history_days else 0.0

        feature_row = {
            "asin_norm": asin_norm,
            "history_days": history_days,
            "paired_buy_box_bsr_days": paired_buy_box_bsr_days,
            "paired_fba_bsr_days": paired_fba_bsr_days,
            "buy_box_coverage_share": buy_box_coverage_share,
            "amazon_presence_share_30d": _presence_share(asin_work, days=30, column="amazon_present"),
            "amazon_presence_share_90d": _presence_share(asin_work, days=90, column="amazon_present"),
            "price_median_30d_gbp": _window_median(asin_work, days=30, column="market_price_day"),
            "price_median_90d_gbp": _window_median(asin_work, days=90, column="market_price_day"),
            "price_median_180d_gbp": _window_median(asin_work, days=180, column="market_price_day"),
            "price_median_365d_gbp": _window_median(asin_work, days=365, column="market_price_day"),
            "bsr_median_30d": _window_median(asin_work, days=30, column="bsr_num"),
            "bsr_median_90d": _window_median(asin_work, days=90, column="bsr_num"),
        }
        feature_row["seasonality_state"] = _seasonality_state(history_days)
        feature_row["history_confidence"] = _history_confidence(
            history_days=history_days,
            paired_buy_box_bsr_days=paired_buy_box_bsr_days,
            paired_fba_bsr_days=paired_fba_bsr_days,
            buy_box_coverage_share=buy_box_coverage_share,
        )
        features[asin_norm] = feature_row
    return features


def _build_velocity_map(velocity_df: pd.DataFrame) -> dict[str, float | None]:
    if velocity_df.empty:
        return {}
    work = velocity_df.copy()
    work["sku_norm"] = work.get("sku", "").map(_normalize_key)
    work = work[work["sku_norm"] != ""].copy()
    if work.empty:
        return {}

    out: dict[str, float | None] = {}
    for sku_norm, one_sku in work.groupby("sku_norm"):
        one = one_sku.copy()
        one["_window_30"] = one.get("window_days", "").map(lambda v: _normalize_text(v) == "30")
        one = one.sort_values("_window_30", ascending=False, kind="stable")
        velocity = None
        for _, row in one.iterrows():
            velocity = _num_or_none(row.get("velocity_units_per_day", ""))
            if velocity is not None:
                break
            velocity = _num_or_none(row.get("v30", ""))
            if velocity is not None:
                break
        out[sku_norm] = velocity
    return out


def _build_map_by_sku(df: pd.DataFrame, sku_col: str = "sku") -> dict[str, pd.Series]:
    if df.empty:
        return {}
    work = df.copy()
    work["sku_norm"] = work.get(sku_col, "").map(_normalize_key)
    work = work[work["sku_norm"] != ""].copy()
    if work.empty:
        return {}
    work = work.drop_duplicates(subset=["sku_norm"], keep="first").set_index("sku_norm")
    return {idx: work.loc[idx] for idx in work.index}


def _build_supplier_cost_map(universal_df: pd.DataFrame) -> dict[str, float]:
    if universal_df.empty:
        return {}
    work = universal_df.copy()
    work["supplier_sku_norm"] = work.get("supplier_sku", "").map(_normalize_key)
    work = work[work["supplier_sku_norm"] != ""].copy()
    if work.empty:
        return {}

    out: dict[str, float] = {}
    for sku_norm, one_sku in work.groupby("supplier_sku_norm"):
        cost_value: float | None = None
        for _, row in one_sku.iterrows():
            candidate = _num_or_none(row.get("unit_cost", ""))
            if candidate is not None and candidate > 0:
                cost_value = candidate
                break
        if cost_value is not None:
            out[sku_norm] = cost_value
    return out


def _build_legacy_scrape_map(scrape_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if scrape_df.empty:
        return {}
    work = scrape_df.copy()
    work["asin_norm"] = work.get("asin", "").map(_normalize_key)
    work["supplier_sku_norm"] = work.get("supplier_sku", "").map(_normalize_key)
    work = work[work["asin_norm"] != ""].copy()
    if work.empty:
        return {}

    work["_observed_ts"] = pd.to_datetime(work.get("observed_utc", "").map(_normalize_text), errors="coerce")
    work = work.sort_values("_observed_ts", ascending=False, kind="stable")

    # Keep one representative row per asin+supplier_sku for stable fallback mapping.
    work = work.drop_duplicates(subset=["asin_norm", "supplier_sku_norm"], keep="first")
    work = work.drop(columns=["_observed_ts"], errors="ignore")
    out: dict[str, pd.DataFrame] = {}
    for asin_norm, group in work.groupby("asin_norm"):
        out[asin_norm] = group.reset_index(drop=True)
    return out


def _pick_legacy_row_for_seller(legacy_matches: pd.DataFrame, seller_sku: object) -> pd.Series | None:
    if legacy_matches.empty:
        return None
    seller_sku_norm = _normalize_key(seller_sku)
    if seller_sku_norm != "":
        match = legacy_matches[
            legacy_matches.get("supplier_sku_norm", "").map(_normalize_key) == seller_sku_norm
        ]
        if not match.empty:
            return match.iloc[0]
    return legacy_matches.iloc[0]


def _build_legacy_first_check_maps(first_check_df: pd.DataFrame) -> tuple[dict[tuple[str, str], pd.Series], dict[str, pd.Series]]:
    if first_check_df.empty:
        return {}, {}
    work = first_check_df.copy()
    work["asin_norm"] = work.get("asin", "").map(_normalize_key)
    work["supplier_sku_norm"] = work.get("supplier_sku", "").map(_normalize_key)
    work = work[work["asin_norm"] != ""].copy()
    if work.empty:
        return {}, {}

    by_key: dict[tuple[str, str], pd.Series] = {}
    by_asin: dict[str, pd.Series] = {}
    work = work.drop_duplicates(subset=["asin_norm", "supplier_sku_norm"], keep="first")
    for _, row in work.iterrows():
        asin_norm = _normalize_text(row.get("asin_norm", ""))
        supplier_sku_norm = _normalize_text(row.get("supplier_sku_norm", ""))
        by_key[(asin_norm, supplier_sku_norm)] = row
        if asin_norm not in by_asin:
            by_asin[asin_norm] = row
    return by_key, by_asin


def _parse_month_key(label: object) -> tuple[int, int] | None:
    txt = _normalize_text(label).lower()
    if txt == "":
        return None
    month_map = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }

    for sep in ("/", "-"):
        parts = txt.split(sep)
        if len(parts) == 2:
            left = _num_or_none(parts[0])
            right = _num_or_none(parts[1])
            if left is not None and right is not None:
                left_int = int(left)
                right_int = int(right)
                if 1 <= left_int <= 12:
                    year = right_int + 2000 if right_int < 100 else right_int
                    return (year, left_int)
                if left_int >= 2000 and 1 <= right_int <= 12:
                    return (left_int, right_int)

    chunks = txt.replace("-", " ").replace("/", " ").split()
    if len(chunks) >= 2:
        month = month_map.get(chunks[0], 0)
        year_num = _num_or_none(chunks[1])
        if month and year_num is not None:
            year = int(year_num)
            if year < 100:
                year += 2000
            return (year, month)
    return None


def _completed_month_history_from_legacy_row(
    legacy_row: pd.Series | None,
) -> list[tuple[tuple[int, int] | None, int, str, float]]:
    if legacy_row is None:
        return []
    labels = [chunk.strip() for chunk in _normalize_text(legacy_row.get("bbp_sales_chart_month_labels", "")).split("|") if chunk.strip()]
    unit_tokens = [chunk.strip() for chunk in _normalize_text(legacy_row.get("bbp_sales_chart_month_units", "")).split("|") if chunk.strip()]
    if not labels or not unit_tokens:
        fallback_label = _normalize_text(legacy_row.get("bbp_sales_last_completed_month_label", ""))
        fallback_units = _num_or_none(legacy_row.get("bbp_sales_last_completed_month_units", ""))
        if fallback_label != "" and fallback_units is not None and fallback_units >= 0:
            return [(_parse_month_key(fallback_label), 0, fallback_label, float(fallback_units))]
        return []
    point_count = min(len(labels), len(unit_tokens))
    labels = labels[:point_count]
    units = [_num_or_none(token) for token in unit_tokens[:point_count]]
    current_label = _normalize_text(legacy_row.get("bbp_sales_current_month_label", ""))
    current_key = _parse_month_key(current_label)
    future_count = int(_num_or_none(legacy_row.get("bbp_sales_future_month_count_ignored", "")) or 0)
    future_count = max(0, min(future_count, point_count))
    future_tail_start = max(0, point_count - future_count)

    candidates: list[tuple[tuple[int, int] | None, int, str, float]] = []
    for idx in range(point_count):
        month_units = units[idx]
        if month_units is None:
            continue
        month_label = _normalize_text(labels[idx])
        if month_label == "":
            continue
        if "*" in month_label:
            continue
        if idx >= future_tail_start:
            continue
        month_key = _parse_month_key(month_label)
        if current_key is not None and month_key is not None and month_key >= current_key:
            continue
        candidates.append((month_key, idx, month_label, max(float(month_units), 0.0)))

    if candidates:
        return candidates

    fallback_label = _normalize_text(legacy_row.get("bbp_sales_last_completed_month_label", ""))
    fallback_units = _num_or_none(legacy_row.get("bbp_sales_last_completed_month_units", ""))
    if fallback_label != "" and fallback_units is not None and fallback_units >= 0:
        return [(_parse_month_key(fallback_label), 0, fallback_label, float(fallback_units))]
    return []


def _derive_last_completed_month_from_chart(legacy_row: pd.Series | None) -> tuple[float | None, str]:
    candidates = _completed_month_history_from_legacy_row(legacy_row)
    if not candidates:
        return None, ""
    dated = [row for row in candidates if row[0] is not None]
    if dated:
        dated.sort(key=lambda row: row[0], reverse=True)
        chosen = dated[0]
    else:
        candidates.sort(key=lambda row: row[1], reverse=True)
        chosen = candidates[0]
    return chosen[3], chosen[2]


def _build_classifier_states(
    *,
    legacy_row: pd.Series | None,
    history_maturity_state: str,
    qualification_result: PriceQualificationResult,
    market_price_gbp: float | None,
    price_median_90d_gbp: float | None,
) -> ClassifierStateResult:
    history_rows = _completed_month_history_from_legacy_row(legacy_row)
    history_rows.sort(key=lambda row: (row[0] is None, row[0], row[1]))
    completed_month_units = [max(float(row[3]), 0.0) for row in history_rows]
    completed_months_count = len(completed_month_units)

    factor = qualification_result.qualification_final_factor
    if factor is None:
        factor = 0.0
    factor = max(0.0, min(1.0, float(factor)))
    qualified_month_units = [units * factor for units in completed_month_units]

    seasonality_reasons: list[str] = []
    maturity_norm = _normalize_text(history_maturity_state).lower()
    seasonality_state = "insufficient_history"
    peak_window_share = 0.0
    off_peak_to_peak_ratio = 1.0
    top_vs_median_ratio = 0.0
    volatility = 0.0
    if completed_months_count < 6:
        seasonality_reasons.extend(["insufficient_history", f"completed_months_{completed_months_count}"])
    else:
        total_units = sum(qualified_month_units)
        median_units = _median(qualified_month_units)
        max_units = max(qualified_month_units) if qualified_month_units else 0.0
        if median_units > 0:
            top_vs_median_ratio = max_units / median_units
        if total_units > 0:
            best_start = 0
            best_window = 0
            best_window_sum = 0.0
            for window in (2, 3, 4):
                if completed_months_count < window:
                    continue
                for idx in range(completed_months_count - window + 1):
                    window_sum = sum(qualified_month_units[idx : idx + window])
                    if window_sum > best_window_sum:
                        best_start = idx
                        best_window = window
                        best_window_sum = window_sum
            peak_window_share = _safe_ratio(best_window_sum, total_units)
            peak_avg = _safe_ratio(best_window_sum, float(best_window))
            off_peak_vals = (
                qualified_month_units[:best_start] + qualified_month_units[best_start + best_window :]
                if best_window > 0
                else qualified_month_units
            )
            off_peak_avg = _mean(off_peak_vals)
            off_peak_to_peak_ratio = _safe_ratio(off_peak_avg, peak_avg)

        mean_units = _mean(qualified_month_units)
        if mean_units > 0 and completed_months_count > 1:
            volatility = float(pd.Series(qualified_month_units).std(ddof=0) / mean_units)

        if (
            maturity_norm == "full_year"
            and completed_months_count >= 9
            and peak_window_share >= 0.5
            and off_peak_to_peak_ratio <= 0.5
        ):
            seasonality_state = "seasonal_confirmed"
            seasonality_reasons.append("peak_window_concentrated")
            seasonality_reasons.append("off_peak_materially_weaker")
        elif maturity_norm == "stable" and peak_window_share >= 0.5 and off_peak_to_peak_ratio <= 0.6:
            seasonality_state = "possible_seasonal"
            seasonality_reasons.append("seasonal_shape_present_without_full_year")
        else:
            seasonality_state = "spiky_not_proven_seasonal"
            if top_vs_median_ratio >= 2.5:
                seasonality_reasons.append("top_month_vs_median_ge_2_5x")
            else:
                seasonality_reasons.append("no_repeatable_seasonal_window")
        seasonality_reasons.append(f"peak_window_share_{peak_window_share:.3f}")
        seasonality_reasons.append(f"off_peak_to_peak_ratio_{off_peak_to_peak_ratio:.3f}")

    stability_state = "too_new"
    stability_reasons: list[str] = []
    baseline_avg = _mean(qualified_month_units)
    trailing3_avg = _mean(qualified_month_units[-3:]) if completed_months_count >= 3 else 0.0
    if completed_months_count < 3:
        stability_state = "too_new"
        stability_reasons.extend(["insufficient_history", f"completed_months_{completed_months_count}"])
    else:
        median_units = _median(qualified_month_units)
        max_units = max(qualified_month_units) if qualified_month_units else 0.0
        top_vs_median_ratio = _safe_ratio(max_units, median_units)
        if seasonality_state != "seasonal_confirmed" and median_units > 0 and top_vs_median_ratio >= 2.5:
            stability_state = "spiky"
            stability_reasons.append("top_month_vs_median_ge_2_5x")
        elif baseline_avg > 0 and trailing3_avg < (baseline_avg * 0.8):
            stability_state = "drifting_down"
            stability_reasons.append("trailing3_below_80pct_baseline")
        elif baseline_avg > 0 and trailing3_avg > (baseline_avg * 1.2):
            stability_state = "drifting_up"
            stability_reasons.append("trailing3_above_120pct_baseline")
        elif volatility >= 1.0 and seasonality_state != "seasonal_confirmed":
            stability_state = "spiky"
            stability_reasons.append("high_volatility")
        else:
            stability_state = "stable"
            stability_reasons.append("within_stability_band")
        stability_reasons.append(f"trailing3_to_baseline_ratio_{_safe_ratio(trailing3_avg, baseline_avg):.3f}")

    recent_state = "insufficient_history"
    recent_reasons: list[str] = []
    if completed_months_count < 3:
        recent_state = "insufficient_history"
        recent_reasons.append("insufficient_history")
    else:
        last_completed = qualified_month_units[-1]
        trailing3 = trailing3_avg
        baseline = baseline_avg
        last_ratio = _safe_ratio(last_completed, baseline)
        trailing3_ratio = _safe_ratio(trailing3, baseline)
        if baseline > 0 and (last_ratio < 0.8 or trailing3_ratio < 0.85):
            recent_state = "underperforming"
            recent_reasons.append("baseline_threshold_under")
        elif baseline > 0 and (last_ratio > 1.2 or trailing3_ratio > 1.15):
            recent_state = "overperforming"
            recent_reasons.append("baseline_threshold_over")
        else:
            recent_state = "stable"
            recent_reasons.append("baseline_threshold_stable")
        recent_reasons.append(f"last_to_baseline_ratio_{last_ratio:.3f}")
        recent_reasons.append(f"trailing3_to_baseline_ratio_{trailing3_ratio:.3f}")
        if seasonality_state in {"seasonal_confirmed", "possible_seasonal"}:
            recent_reasons.append("seasonal_window")
        if _normalize_text(qualification_result.qualification_market_gate_state) == "market_below_break_even":
            recent_reasons.append("market_below_floor")
        amazon_factor = qualification_result.qualification_amazon_pressure_factor
        if amazon_factor is not None and amazon_factor <= 0.05 and qualification_result.qualification_market_gate_state == "market_open":
            recent_reasons.append("amazon_below_floor")
        if (
            market_price_gbp is not None
            and price_median_90d_gbp is not None
            and price_median_90d_gbp > 0
            and market_price_gbp < (price_median_90d_gbp * 0.9)
        ):
            recent_reasons.append("recent_price_compression")
        if volatility >= 1.0 or stability_state == "spiky":
            recent_reasons.append("high_volatility")

    return ClassifierStateResult(
        seasonality_state=seasonality_state,
        seasonality_reason_codes=_dedupe_reason_codes(seasonality_reasons),
        stability_state=stability_state,
        stability_reason_codes=_dedupe_reason_codes(stability_reasons),
        recent_vs_baseline_state=recent_state,
        recent_vs_baseline_reason_codes=_dedupe_reason_codes(recent_reasons),
        completed_months_count=completed_months_count,
    )


def _velocity_from_legacy_scrape_row(
    legacy_row: pd.Series | None,
) -> tuple[float | None, str, float | None, str]:
    if legacy_row is None:
        return None, "missing", None, ""

    def _monthly_value(col: str) -> float | None:
        monthly = _num_or_none(legacy_row.get(col, ""))
        if monthly is None or monthly <= 0:
            return None
        return monthly

    replay_basis_units = _monthly_value("bbp_sales_replay_demand_basis_units")
    replay_basis_source = _normalize_text(legacy_row.get("bbp_sales_replay_demand_basis_source", ""))
    replay_basis_label = _normalize_text(legacy_row.get("bbp_sales_replay_demand_basis_label", ""))
    derived_last_completed_units, derived_last_completed_label = _derive_last_completed_month_from_chart(legacy_row)
    if derived_last_completed_units is not None and derived_last_completed_units >= 0:
        return (
            derived_last_completed_units / 30.0,
            "bbp_last_completed_month",
            derived_last_completed_units,
            derived_last_completed_label,
        )
    if replay_basis_source == "bbp_zero_history":
        return 0.0, replay_basis_source, 0.0, replay_basis_label or "zero_history"
    if replay_basis_units is not None and replay_basis_source != "":
        return replay_basis_units / 30.0, replay_basis_source, replay_basis_units, replay_basis_label

    fallback_order = (
        ("bbp_sales_last_completed_month_units", "bbp_last_completed_month", "bbp_sales_last_completed_month_label"),
        ("bbp_monthly_sales_recent_avg", "bbp_recent_history_fallback", ""),
        ("bbp_monthly_sales_current", "bbp_current_month_fallback", "bbp_sales_current_month_label"),
        ("monthly_sold", "amazon_monthly_sold_fallback", ""),
        ("bbp_monthly_units_chosen", "bbp_units_chosen_fallback", ""),
    )

    for col, source, label_col in fallback_order:
        monthly = _monthly_value(col)
        if monthly is None:
            continue
        month_label = _normalize_text(legacy_row.get(label_col, "")) if label_col else ""
        return monthly / 30.0, source, monthly, month_label

    return None, "missing", None, ""


def _cost_from_legacy_first_check_row(first_check_row: pd.Series | None) -> float | None:
    if first_check_row is None:
        return None
    cost = _num_or_none(first_check_row.get("cost", ""))
    if cost is None or cost <= 0:
        return None
    return cost


def _safe_cost_from_product(product_row: pd.Series | None) -> float | None:
    if product_row is None:
        return None
    catalog = _num_or_none(product_row.get("supplier_catalog_price", ""))
    if catalog is not None and catalog > 0:
        return catalog
    last_purchase = _num_or_none(product_row.get("last_purchase_price", ""))
    if last_purchase is not None and last_purchase > 0:
        return last_purchase
    return None


def _market_price_from_offer(offer_row: pd.Series | None) -> float | None:
    if offer_row is None:
        return None
    for col in ("buy_box_price", "lowest_fba_price", "our_price"):
        value = _num_or_none(offer_row.get(col, ""))
        if value is not None and value > 0:
            return value
    return None


def _first_numeric_from_rows(rows: tuple[pd.Series | None, ...], columns: tuple[str, ...]) -> float | None:
    for row in rows:
        if row is None:
            continue
        for column in columns:
            value = _num_or_none(row.get(column, ""))
            if value is not None:
                return value
    return None


def _build_input_status(
    *,
    mapping_status: str,
    history_days: int,
    paired_buy_box_bsr_days: int,
    paired_fba_bsr_days: int,
    history_confidence: str,
    attribution_confidence: str,
    attribution_reason_codes: list[str],
    history_confidence_downgraded: bool,
    current_supplier_buy_cost_gbp: float | None,
    break_even_price_gbp: float | None,
    base_velocity_30d_units_per_day: float | None,
    demand_basis_source: str,
    demand_basis_units_monthly: float | None,
) -> tuple[str, str, str]:
    reasons: list[str] = []
    demand_source_norm = _normalize_text(demand_basis_source)

    if mapping_status == "no_product_db_match":
        reasons.append("no_product_db_match")
    if mapping_status == "multi_sku_asin_match":
        reasons.append("multi_sku_asin_match")
    if history_days < 30:
        reasons.append("insufficient_history_days_lt_30")
    if paired_buy_box_bsr_days < 30 and paired_fba_bsr_days < 30:
        reasons.append("insufficient_paired_price_bsr_days")
    if history_confidence == "low":
        reasons.append("history_confidence_low")
    if attribution_confidence == "low":
        reasons.append("attribution_confidence_low")
    if history_confidence_downgraded:
        reasons.append("history_confidence_downgraded_by_attribution")
    reasons.extend(attribution_reason_codes)
    if current_supplier_buy_cost_gbp is None:
        reasons.append("missing_current_supplier_buy_cost")
    if break_even_price_gbp is None:
        reasons.append("missing_break_even_price")
    if base_velocity_30d_units_per_day is None:
        reasons.append("missing_velocity_30d")
    if demand_source_norm == "":
        reasons.append("missing_demand_basis_source")
    elif demand_source_norm not in {"bbp_last_completed_month", "bbp_zero_history"}:
        reasons.append("demand_basis_not_trusted_completed_month")
    elif demand_source_norm == "bbp_last_completed_month" and (
        demand_basis_units_monthly is None or demand_basis_units_monthly <= 0
    ):
        reasons.append("invalid_last_completed_demand_basis_units")
    elif demand_source_norm == "bbp_zero_history" and (
        demand_basis_units_monthly is None or abs(demand_basis_units_monthly) > 0.01
    ):
        reasons.append("invalid_zero_history_demand_basis_units")

    blocking = {
        "no_product_db_match",
        "insufficient_history_days_lt_30",
        "missing_current_supplier_buy_cost",
        "missing_break_even_price",
        "missing_velocity_30d",
        "missing_demand_basis_source",
        "demand_basis_not_trusted_completed_month",
        "invalid_last_completed_demand_basis_units",
        "invalid_zero_history_demand_basis_units",
    }
    input_status = "ready"
    for reason in reasons:
        if reason in blocking:
            input_status = "manual_review"
            break
    if input_status == "ready" and (
        "multi_sku_asin_match" in reasons or history_confidence == "low" or attribution_confidence == "low"
    ):
        input_status = "manual_review"

    manual_review_flag = "1" if input_status != "ready" else "0"
    return input_status, "|".join(reasons), manual_review_flag


def build_backtest_input_view(
    root: Path | None = None,
    *,
    observed_utc: str | None = None,
) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)
    snapshot_utc = observed_utc or _utc_now_iso()

    source_keys = [*MANDATORY_SOURCE_KEYS, *OPTIONAL_SOURCE_KEYS]
    source_data: dict[str, SourceReadResult] = {key: _read_source(root_path, key) for key in source_keys}
    _validate_sources(source_data)
    asin_resolution_map = _read_asin_resolution_map(root_path)

    policy_row = _active_policy_row(source_data["feeder_backtest_policy_live"].df)
    policy_id = _normalize_text(policy_row.get("policy_id", ""))
    if policy_id == "":
        raise ValueError("active policy row missing policy_id")

    asin_day_df = _aggregate_asin_day(source_data["feeder_legacy_chart_daily_raw_live"].df)
    if asin_day_df.empty:
        out_df = _write_contract_df(pd.DataFrame(), "feeder_backtest_input_view_live", root_path)
        print(
            {
                "status": "success",
                "rows": 0,
                "ready_rows": 0,
                "manual_review_rows": 0,
                "notes": "no valid asin/day rows in chart history",
            }
        )
        return out_df

    asin_features = _build_asin_features(asin_day_df)

    supplier_universal_df = source_data["supplier_price_list_universal_live"].df
    if source_data["supplier_price_list_universal_live"].missing_columns:
        supplier_universal_df = pd.DataFrame()
    supplier_cost_map = _build_supplier_cost_map(supplier_universal_df)

    product_df = source_data["product_db_preview"].df
    if source_data["product_db_preview"].missing_columns:
        product_df = pd.DataFrame()
    product_map: dict[str, pd.DataFrame] = {}
    if not product_df.empty:
        products = product_df.copy()
        products["asin_norm"] = products.get("asin", "").map(_normalize_key)
        products["seller_sku_norm"] = products.get("seller_sku", "").map(_normalize_key)
        products = products[(products["asin_norm"] != "") & (products["seller_sku_norm"] != "")].copy()
        if not products.empty:
            products = products.drop_duplicates(subset=["asin_norm", "seller_sku_norm"], keep="first")
            for asin_norm, group in products.groupby("asin_norm"):
                product_map[asin_norm] = group.reset_index(drop=True)

    velocity_df = source_data["sku_sales_velocity"].df
    if source_data["sku_sales_velocity"].missing_columns:
        velocity_df = pd.DataFrame()
    velocity_map = _build_velocity_map(velocity_df)

    performance_df = source_data["sku_performance_summary"].df
    if source_data["sku_performance_summary"].missing_columns:
        performance_df = pd.DataFrame()
    performance_map = _build_map_by_sku(performance_df, sku_col="sku")

    offer_df = source_data["listing_offer_snapshot_latest"].df
    if source_data["listing_offer_snapshot_latest"].missing_columns:
        offer_df = pd.DataFrame()
    offer_map = _build_map_by_sku(offer_df, sku_col="sku")

    legacy_scrape_df = source_data["feeder_legacy_scrape_evidence_live"].df
    if source_data["feeder_legacy_scrape_evidence_live"].missing_columns:
        legacy_scrape_df = pd.DataFrame()
    legacy_scrape_map = _build_legacy_scrape_map(legacy_scrape_df)

    legacy_first_checks_df = source_data["feeder_legacy_first_checks_live"].df
    if source_data["feeder_legacy_first_checks_live"].missing_columns:
        legacy_first_checks_df = pd.DataFrame()
    legacy_first_check_by_key, legacy_first_check_by_asin = _build_legacy_first_check_maps(legacy_first_checks_df)

    rows: list[dict[str, str]] = []
    for asin_norm, feature in sorted(asin_features.items()):
        product_matches = product_map.get(asin_norm, pd.DataFrame())
        legacy_matches = legacy_scrape_map.get(asin_norm, pd.DataFrame())

        candidate_rows: list[tuple[str, pd.Series | None, pd.Series | None]] = []
        if not product_matches.empty:
            mapping_status = "unique_asin_match" if len(product_matches.index) == 1 else "multi_sku_asin_match"
            for _, product_row in product_matches.iterrows():
                linked_legacy_row = _pick_legacy_row_for_seller(
                    legacy_matches,
                    _normalize_text(product_row.get("seller_sku", "")),
                )
                candidate_rows.append((mapping_status, product_row, linked_legacy_row))
        elif not legacy_matches.empty:
            mapping_status = "legacy_asin_match" if len(legacy_matches.index) == 1 else "multi_sku_asin_match"
            for _, legacy_row in legacy_matches.iterrows():
                candidate_rows.append((mapping_status, None, legacy_row))
        else:
            candidate_rows.append(("no_product_db_match", None, None))

        if len(candidate_rows) > 1:
            candidate_multi_rows = [row for row in candidate_rows if row[0] == "multi_sku_asin_match"]
            if len(candidate_multi_rows) == len(candidate_rows):
                resolved_sku_norm = asin_resolution_map.get(asin_norm, "")
                if resolved_sku_norm != "":
                    resolved_candidates: list[tuple[str, pd.Series | None, pd.Series | None]] = []
                    for _, product_row, legacy_row in candidate_rows:
                        candidate_sku = ""
                        if product_row is not None:
                            candidate_sku = _normalize_text(product_row.get("seller_sku", ""))
                        if candidate_sku == "" and legacy_row is not None:
                            candidate_sku = _normalize_text(legacy_row.get("supplier_sku", ""))
                        if _normalize_key(candidate_sku) == resolved_sku_norm:
                            resolved_candidates.append(("resolved_asin_match", product_row, legacy_row))
                    if len(resolved_candidates) == 1:
                        candidate_rows = resolved_candidates

        for mapping_status, product_row, legacy_row in candidate_rows:
            seller_sku = "" if product_row is None else _normalize_text(product_row.get("seller_sku", ""))
            if seller_sku == "" and legacy_row is not None:
                seller_sku = _normalize_text(legacy_row.get("supplier_sku", ""))
            if seller_sku == "" and legacy_row is not None:
                seller_sku = f"LEGACY-{asin_norm}"
            seller_sku_norm = _normalize_key(seller_sku)

            legacy_supplier_sku_norm = _normalize_key(legacy_row.get("supplier_sku", "")) if legacy_row is not None else ""
            first_check_row = None
            if legacy_supplier_sku_norm != "":
                first_check_row = legacy_first_check_by_key.get((asin_norm, legacy_supplier_sku_norm))
            if first_check_row is None and seller_sku_norm != "":
                first_check_row = legacy_first_check_by_key.get((asin_norm, seller_sku_norm))
            if first_check_row is None:
                first_check_row = legacy_first_check_by_asin.get(asin_norm)

            legacy_velocity, legacy_demand_source, legacy_demand_monthly, legacy_demand_month_label = _velocity_from_legacy_scrape_row(
                legacy_row
            )
            e_velocity_value = velocity_map.get(seller_sku_norm)
            if legacy_velocity is not None:
                velocity_value = legacy_velocity
                demand_basis_source = legacy_demand_source
                demand_basis_units_monthly = legacy_demand_monthly
                demand_basis_month_label = legacy_demand_month_label
            elif e_velocity_value is not None:
                velocity_value = e_velocity_value
                demand_basis_source = "e_velocity_30d_fallback"
                demand_basis_units_monthly = e_velocity_value * 30.0
                demand_basis_month_label = ""
            else:
                velocity_value = None
                demand_basis_source = "missing"
                demand_basis_units_monthly = None
                demand_basis_month_label = ""

            bbp_last_completed_month_label = _normalize_text(
                legacy_row.get("bbp_sales_last_completed_month_label", "") if legacy_row is not None else ""
            )
            bbp_last_completed_month_units = _num_or_none(
                legacy_row.get("bbp_sales_last_completed_month_units", "") if legacy_row is not None else ""
            )
            bbp_current_month_label = _normalize_text(
                legacy_row.get("bbp_sales_current_month_label", "") if legacy_row is not None else ""
            )
            bbp_current_month_units = _num_or_none(
                legacy_row.get("bbp_sales_current_month_units", "") if legacy_row is not None else ""
            )
            bbp_future_month_count_ignored = _num_or_none(
                legacy_row.get("bbp_sales_future_month_count_ignored", "") if legacy_row is not None else ""
            )
            bbp_replay_basis_source = _normalize_text(
                legacy_row.get("bbp_sales_replay_demand_basis_source", "") if legacy_row is not None else ""
            )
            bbp_replay_basis_label = _normalize_text(
                legacy_row.get("bbp_sales_replay_demand_basis_label", "") if legacy_row is not None else ""
            )
            bbp_replay_basis_units = _num_or_none(
                legacy_row.get("bbp_sales_replay_demand_basis_units", "") if legacy_row is not None else ""
            )

            perf_row = performance_map.get(seller_sku_norm)
            offer_row = offer_map.get(seller_sku_norm)

            current_supplier_cost = _safe_cost_from_product(product_row)
            if current_supplier_cost is None:
                current_supplier_cost = _cost_from_legacy_first_check_row(first_check_row)
            if current_supplier_cost is None and seller_sku_norm != "":
                current_supplier_cost = supplier_cost_map.get(seller_sku_norm)
            if current_supplier_cost is None and legacy_supplier_sku_norm != "":
                current_supplier_cost = supplier_cost_map.get(legacy_supplier_sku_norm)
            break_even_price = _num_or_none(perf_row.get("break_even_price_gbp", "")) if perf_row is not None else None
            if break_even_price is None and legacy_row is not None:
                break_even_price = _num_or_none(legacy_row.get("break_even", ""))
            if break_even_price is None and first_check_row is not None:
                break_even_price = _num_or_none(first_check_row.get("break_even", ""))
            market_price = _market_price_from_offer(offer_row)
            if market_price is None:
                market_price = feature["price_median_30d_gbp"]
            fee_rows = (first_check_row, legacy_row)
            vat_rate_pct = _first_numeric_from_rows(fee_rows, ("vat", "vat_rate"))
            fba_fee = _first_numeric_from_rows(fee_rows, ("fba_fee",))
            referral_fee = _first_numeric_from_rows(fee_rows, ("referral_fee",))
            digital_fee = _first_numeric_from_rows(fee_rows, ("digital_fee",))
            est_shipping = _first_numeric_from_rows(fee_rows, ("est_shipping",))
            referral_fee_basis_price = _first_numeric_from_rows(
                fee_rows,
                (
                    "api_live_price",
                    "reasonable_price",
                    "buy_box_price",
                    "bbp_live_sell_price",
                    "bbp_30d_avg_price",
                ),
            )
            if referral_fee_basis_price is None:
                referral_fee_basis_price = market_price

            history_days = int(feature["history_days"])
            history_maturity_state = _history_maturity_state(history_days)
            qualification_result = _price_qualification(
                demand_basis_units_monthly=demand_basis_units_monthly,
                break_even_price_gbp=break_even_price,
                market_price_gbp=market_price,
                vat_rate_pct=vat_rate_pct,
                product_cost_gbp=current_supplier_cost,
                fba_fee_gbp=fba_fee,
                referral_fee_gbp=referral_fee,
                digital_fee_gbp=digital_fee,
                est_shipping_gbp=est_shipping,
                referral_fee_basis_price_gbp=referral_fee_basis_price,
                amazon_presence_share_30d=float(feature["amazon_presence_share_30d"]),
                buy_box_coverage_share=float(feature["buy_box_coverage_share"]),
                history_maturity_state=history_maturity_state,
            )
            qualified_units_monthly = qualification_result.qualified_units_monthly
            qualified_profit_monthly_gbp = qualification_result.qualified_profit_monthly_gbp
            price_qualification_reason_codes = qualification_result.price_qualification_reason_codes
            classifier_result = _build_classifier_states(
                legacy_row=legacy_row,
                history_maturity_state=history_maturity_state,
                qualification_result=qualification_result,
                market_price_gbp=market_price,
                price_median_90d_gbp=_num_or_none(feature.get("price_median_90d_gbp")),
            )

            base_history_confidence = _normalize_text(feature["history_confidence"])
            attribution_confidence, attribution_reason_codes = _attribution_confidence(
                mapping_status=mapping_status,
                buy_box_coverage_share=float(feature["buy_box_coverage_share"]),
                amazon_presence_share_90d=float(feature["amazon_presence_share_90d"]),
                paired_buy_box_bsr_days=int(feature["paired_buy_box_bsr_days"]),
                paired_fba_bsr_days=int(feature["paired_fba_bsr_days"]),
                product_row=product_row,
                legacy_row=legacy_row,
            )
            final_history_confidence = _min_confidence(base_history_confidence, attribution_confidence)
            history_confidence_downgraded = _clamp_confidence(final_history_confidence) != _clamp_confidence(
                base_history_confidence
            )
            input_status, reason_codes, manual_review_flag = _build_input_status(
                mapping_status=mapping_status,
                history_days=history_days,
                paired_buy_box_bsr_days=int(feature["paired_buy_box_bsr_days"]),
                paired_fba_bsr_days=int(feature["paired_fba_bsr_days"]),
                history_confidence=final_history_confidence,
                attribution_confidence=attribution_confidence,
                attribution_reason_codes=attribution_reason_codes,
                history_confidence_downgraded=history_confidence_downgraded,
                current_supplier_buy_cost_gbp=current_supplier_cost,
                break_even_price_gbp=break_even_price,
                base_velocity_30d_units_per_day=velocity_value,
                demand_basis_source=demand_basis_source,
                demand_basis_units_monthly=demand_basis_units_monthly,
            )
            if input_status == "ready":
                qualification_block_reasons: list[str] = []
                if history_maturity_state == "":
                    qualification_block_reasons.append("missing_history_maturity_state")
                if qualified_units_monthly is None:
                    qualification_block_reasons.append("missing_price_qualified_units")
                if qualified_profit_monthly_gbp is None:
                    qualification_block_reasons.append("missing_price_qualified_profit")
                if qualification_result.qualification_market_gate_state == "":
                    qualification_block_reasons.append("missing_qualification_market_gate_state")
                if qualification_result.qualification_market_gate_factor is None:
                    qualification_block_reasons.append("missing_qualification_market_gate_factor")
                if qualification_result.qualification_amazon_pressure_factor is None:
                    qualification_block_reasons.append("missing_qualification_amazon_pressure_factor")
                if qualification_result.qualification_buy_box_coverage_factor is None:
                    qualification_block_reasons.append("missing_qualification_buy_box_coverage_factor")
                if qualification_result.qualification_maturity_factor is None:
                    qualification_block_reasons.append("missing_qualification_maturity_factor")
                if qualification_result.qualification_final_factor is None:
                    qualification_block_reasons.append("missing_qualification_final_factor")
                if price_qualification_reason_codes == "":
                    qualification_block_reasons.append("missing_price_qualification_reason_codes")
                if classifier_result.seasonality_state == "":
                    qualification_block_reasons.append("missing_seasonality_state")
                if classifier_result.seasonality_reason_codes == "":
                    qualification_block_reasons.append("missing_seasonality_reason_codes")
                if classifier_result.stability_state == "":
                    qualification_block_reasons.append("missing_stability_state")
                if classifier_result.stability_reason_codes == "":
                    qualification_block_reasons.append("missing_stability_reason_codes")
                if classifier_result.recent_vs_baseline_state == "":
                    qualification_block_reasons.append("missing_recent_vs_baseline_state")
                if classifier_result.recent_vs_baseline_reason_codes == "":
                    qualification_block_reasons.append("missing_recent_vs_baseline_reason_codes")
                if qualification_block_reasons:
                    input_status = "manual_review"
                    manual_review_flag = "1"
                    existing_reasons = [token for token in _normalize_text(reason_codes).split("|") if token]
                    for token in qualification_block_reasons:
                        if token not in existing_reasons:
                            existing_reasons.append(token)
                    reason_codes = "|".join(existing_reasons)

            supplier_code = ""
            supplier_name = ""
            title = ""
            if product_row is not None:
                supplier_code = _normalize_text(product_row.get("supplier_code", ""))
                supplier_name = _normalize_text(product_row.get("supplier_name", ""))
                title = _normalize_text(product_row.get("title", ""))
            if supplier_code == "" and legacy_row is not None:
                supplier_code = _normalize_text(legacy_row.get("supplier_id", ""))
            if supplier_name == "" and legacy_row is not None:
                supplier_name = _normalize_text(legacy_row.get("supplier_name", ""))
            if supplier_name == "" and first_check_row is not None:
                supplier_name = _normalize_text(first_check_row.get("supplier", ""))
            if title == "" and legacy_row is not None:
                title = _normalize_text(legacy_row.get("title", ""))

            row = {
                "observed_utc": snapshot_utc,
                "policy_id": policy_id,
                "seller_sku": seller_sku,
                "asin": asin_norm,
                "supplier_code": supplier_code,
                "supplier_name": supplier_name,
                "mapping_status": mapping_status,
                "input_status": input_status,
                "input_reason_codes": reason_codes,
                "history_days": str(history_days),
                "paired_buy_box_bsr_days": str(int(feature["paired_buy_box_bsr_days"])),
                "paired_fba_bsr_days": str(int(feature["paired_fba_bsr_days"])),
                "buy_box_coverage_share": _num_to_text(float(feature["buy_box_coverage_share"])),
                "amazon_presence_share_30d": _num_to_text(float(feature["amazon_presence_share_30d"])),
                "amazon_presence_share_90d": _num_to_text(float(feature["amazon_presence_share_90d"])),
                "price_median_30d_gbp": _num_to_text(feature["price_median_30d_gbp"]),
                "price_median_90d_gbp": _num_to_text(feature["price_median_90d_gbp"]),
                "price_median_180d_gbp": _num_to_text(feature["price_median_180d_gbp"]),
                "price_median_365d_gbp": _num_to_text(feature["price_median_365d_gbp"]),
                "bsr_median_30d": _num_to_text(feature["bsr_median_30d"]),
                "bsr_median_90d": _num_to_text(feature["bsr_median_90d"]),
                "demand_basis_source": demand_basis_source,
                "demand_basis_units_monthly": _num_to_text(demand_basis_units_monthly),
                "demand_basis_month_label": demand_basis_month_label,
                "bbp_sales_last_completed_month_label": bbp_last_completed_month_label,
                "bbp_sales_last_completed_month_units": _num_to_text(bbp_last_completed_month_units),
                "bbp_sales_current_month_label": bbp_current_month_label,
                "bbp_sales_current_month_units": _num_to_text(bbp_current_month_units),
                "bbp_sales_future_month_count_ignored": _num_to_text(bbp_future_month_count_ignored),
                "bbp_sales_replay_demand_basis_source": bbp_replay_basis_source,
                "bbp_sales_replay_demand_basis_label": bbp_replay_basis_label,
                "bbp_sales_replay_demand_basis_units": _num_to_text(bbp_replay_basis_units),
                "base_velocity_30d_units_per_day": _num_to_text(velocity_value),
                "current_supplier_buy_cost_gbp": _num_to_text(current_supplier_cost),
                "break_even_price_gbp": _num_to_text(break_even_price),
                "market_price_gbp": _num_to_text(market_price),
                "seasonality_state": classifier_result.seasonality_state,
                "seasonality_reason_codes": classifier_result.seasonality_reason_codes,
                "stability_state": classifier_result.stability_state,
                "stability_reason_codes": classifier_result.stability_reason_codes,
                "recent_vs_baseline_state": classifier_result.recent_vs_baseline_state,
                "recent_vs_baseline_reason_codes": classifier_result.recent_vs_baseline_reason_codes,
                "completed_months_count": str(classifier_result.completed_months_count),
                "history_maturity_state": history_maturity_state,
                "history_confidence": final_history_confidence,
                "price_qualified_units_monthly": _num_to_text(qualified_units_monthly),
                "price_qualified_profit_monthly_gbp": _num_to_text(qualified_profit_monthly_gbp),
                "price_qualification_reason_codes": price_qualification_reason_codes,
                "qualification_market_gate_state": qualification_result.qualification_market_gate_state,
                "qualification_market_gate_factor": _num_to_text(qualification_result.qualification_market_gate_factor),
                "qualification_amazon_pressure_factor": _num_to_text(
                    qualification_result.qualification_amazon_pressure_factor
                ),
                "qualification_buy_box_coverage_factor": _num_to_text(
                    qualification_result.qualification_buy_box_coverage_factor
                ),
                "qualification_maturity_factor": _num_to_text(qualification_result.qualification_maturity_factor),
                "qualification_final_factor": _num_to_text(qualification_result.qualification_final_factor),
                "qualification_zero_or_block_reason": qualification_result.qualification_zero_or_block_reason,
                "manual_review_flag": manual_review_flag,
                "title": title,
                "expected_refund_cost_per_unit_gbp": _num_to_text(
                    _num_or_none(perf_row.get("expected_refund_cost_per_unit_gbp", "")) if perf_row is not None else None
                ),
                "roi_at_market_price_pct": _num_to_text(
                    _num_or_none(perf_row.get("roi_at_market_price_pct", "")) if perf_row is not None else None
                ),
                "notes": "",
            }

            if row["roi_at_market_price_pct"] == "" and perf_row is not None:
                fallback_roi = _num_or_none(perf_row.get("roi_at_buy_box_price_pct", ""))
                if fallback_roi is None:
                    fallback_roi = _num_or_none(perf_row.get("roi_at_our_price_pct", ""))
                row["roi_at_market_price_pct"] = _num_to_text(fallback_roi)

            rows.append(row)

    out_df = _write_contract_df(pd.DataFrame(rows), "feeder_backtest_input_view_live", root_path)
    ready_rows = int((out_df["input_status"] == "ready").sum()) if not out_df.empty else 0
    manual_review_rows = int((out_df["manual_review_flag"] == "1").sum()) if not out_df.empty else 0
    resolved_rows = int((out_df["mapping_status"] == "resolved_asin_match").sum()) if not out_df.empty else 0
    print(
        {
            "status": "success",
            "rows": int(len(out_df)),
            "ready_rows": ready_rows,
            "manual_review_rows": manual_review_rows,
            "resolved_rows": resolved_rows,
            "policy_id": policy_id,
            "snapshot": str(root_path / get_f_output_contract("feeder_backtest_input_view_live").rel_path),
        }
    )
    return out_df


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build F backtest input view from chart history and mapped context.")
    parser.add_argument("--observed-utc", default=None, help="Override observed_utc for deterministic runs.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_backtest_input_view(observed_utc=args.observed_utc)


if __name__ == "__main__":
    main()
