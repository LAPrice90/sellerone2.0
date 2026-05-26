from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.flows.F._contract_io import write_f_contract_df
from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract
from scripts.flows.F._schemas import get_f_output_column_types, get_f_output_contract
from scripts.flows.F._source_contracts import get_source_contract


MANDATORY_SOURCE_KEYS: tuple[str, ...] = (
    "feeder_backtest_policy_live",
    "feeder_backtest_input_view_live",
    "feeder_legacy_chart_daily_raw_live",
)

SCENARIO_NAMES: tuple[str, ...] = (
    "sharing_with_amazon_and_fba",
    "sharing_with_amazon",
    "sharing_with_fba",
    "solo_or_no_meaningful_competition",
)

PRICE_MATCH_TOLERANCE = 0.01
MEASURED_SHARE_PRIOR_DAYS = 30
MIN_ASIN_SCENARIO_DAYS = 7

SCENARIO_SHARE_CAP_PCT: dict[str, float] = {
    "sharing_with_amazon_and_fba": 70.0,
    "sharing_with_amazon": 80.0,
    "sharing_with_fba": 90.0,
    "solo_or_no_meaningful_competition": 100.0,
}


@dataclass(frozen=True)
class SourceReadResult:
    key: str
    path: Path
    df: pd.DataFrame
    file_missing: bool
    missing_columns: tuple[str, ...]


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


def _active_policy_row(policy_df: pd.DataFrame) -> pd.Series:
    active = policy_df[policy_df.get("policy_status", "").map(lambda v: _normalize_text(v).lower() == "active")]
    if len(active.index) != 1:
        raise ValueError(f"expected exactly 1 active policy row, found {len(active.index)}")
    return active.iloc[0]


def _aggregate_chart_daily(raw_df: pd.DataFrame) -> pd.DataFrame:
    work = raw_df.copy()
    work["asin_norm"] = work.get("asin", "").map(_normalize_key)
    work["day_date"] = pd.to_datetime(work.get("day", ""), errors="coerce").dt.date
    work = work[(work["asin_norm"] != "") & work["day_date"].notna()].copy()
    if work.empty:
        return pd.DataFrame(columns=["asin_norm", "day_date"])

    for col in ("amazon_price_raw", "fba_price_raw", "fbm_price_raw", "buy_box_price_raw", "price_chosen_processed"):
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
            amazon_price_gbp=("amazon_price_raw_num", agg_min),
            lowest_fba_price_gbp=("fba_price_raw_num", agg_min),
            lowest_fbm_price_gbp=("fbm_price_raw_num", agg_min),
            buy_box_price_gbp=("buy_box_price_raw_num", agg_min),
            chosen_price_gbp=("price_chosen_processed_num", agg_median),
            bsr_value=("bsr_raw_num", agg_median),
        )
        .sort_values(["asin_norm", "day_date"], ascending=[True, True], kind="stable")
        .reset_index(drop=True)
    )

    grouped["amazon_present"] = grouped["amazon_price_gbp"].notna()
    grouped["fba_present"] = grouped["lowest_fba_price_gbp"].notna()
    grouped["market_price_gbp"] = grouped.apply(
        lambda row: row["chosen_price_gbp"]
        if pd.notna(row["chosen_price_gbp"])
        else row["buy_box_price_gbp"]
        if pd.notna(row["buy_box_price_gbp"])
        else row["lowest_fba_price_gbp"]
        if pd.notna(row["lowest_fba_price_gbp"])
        else row["lowest_fbm_price_gbp"]
        if pd.notna(row["lowest_fbm_price_gbp"])
        else row["amazon_price_gbp"]
        if pd.notna(row["amazon_price_gbp"])
        else None,
        axis=1,
    )
    return grouped


def _seasonality_multiplier(seasonality_state: str) -> float:
    state = _normalize_text(seasonality_state).lower()
    if state in {"seasonal_confirmed", "full_year_history"}:
        return 1.0
    if state in {"possible_seasonal", "partial_year_history"}:
        return 0.95
    if state == "spiky_not_proven_seasonal":
        return 0.85
    if state == "limited_history":
        return 0.9
    return 0.8


def _competition_scenario(amazon_present: bool, fba_present: bool) -> str:
    if amazon_present and fba_present:
        return "sharing_with_amazon_and_fba"
    if amazon_present:
        return "sharing_with_amazon"
    if fba_present:
        return "sharing_with_fba"
    return "solo_or_no_meaningful_competition"


def _price_matches(left: float | None, right: float | None, *, tolerance: float = PRICE_MATCH_TOLERANCE) -> bool:
    if left is None or right is None or right <= 0:
        return False
    return (abs(left - right) / right) <= tolerance


def _measured_share_signal(
    *,
    competition_scenario: str,
    buy_box_price: float | None,
    amazon_price: float | None,
) -> float:
    if buy_box_price is None:
        return 0.0
    if competition_scenario in {"sharing_with_amazon_and_fba", "sharing_with_amazon"}:
        if _price_matches(buy_box_price, amazon_price):
            return 0.0
    return 1.0


def _build_measured_share_maps(
    chart_daily: pd.DataFrame,
    *,
    shared_sales_default_pct: float,
) -> tuple[dict[str, float], dict[tuple[str, str], float], dict[tuple[str, str], int]]:
    work = chart_daily.copy()
    if work.empty:
        global_fallback = {
            scenario: (100.0 if scenario == "solo_or_no_meaningful_competition" else shared_sales_default_pct)
            for scenario in SCENARIO_NAMES
        }
        return global_fallback, {}, {}

    work["competition_scenario"] = work.apply(
        lambda row: _competition_scenario(bool(row.get("amazon_present", False)), bool(row.get("fba_present", False))),
        axis=1,
    )
    work["measured_share_signal"] = work.apply(
        lambda row: _measured_share_signal(
            competition_scenario=_normalize_text(row.get("competition_scenario", "")),
            buy_box_price=_num_or_none(row.get("buy_box_price_gbp", "")),
            amazon_price=_num_or_none(row.get("amazon_price_gbp", "")),
        ),
        axis=1,
    )

    global_by_scenario: dict[str, float] = {}
    global_grouped = (
        work.groupby("competition_scenario", as_index=False)
        .agg(days=("competition_scenario", "size"), measured_signal=("measured_share_signal", "mean"))
        .reset_index(drop=True)
    )
    for _, row in global_grouped.iterrows():
        scenario = _normalize_text(row.get("competition_scenario", ""))
        rate = float(row.get("measured_signal", 0.0) or 0.0)
        global_by_scenario[scenario] = max(0.0, min(100.0, rate * 100.0))

    for scenario in SCENARIO_NAMES:
        if scenario not in global_by_scenario:
            global_by_scenario[scenario] = (
                100.0 if scenario == "solo_or_no_meaningful_competition" else shared_sales_default_pct
            )

    asin_by_scenario: dict[tuple[str, str], float] = {}
    asin_days_by_scenario: dict[tuple[str, str], int] = {}
    asin_grouped = (
        work.groupby(["asin_norm", "competition_scenario"], as_index=False)
        .agg(days=("competition_scenario", "size"), measured_signal=("measured_share_signal", "mean"))
        .reset_index(drop=True)
    )
    for _, row in asin_grouped.iterrows():
        asin_norm = _normalize_text(row.get("asin_norm", ""))
        scenario = _normalize_text(row.get("competition_scenario", ""))
        if asin_norm == "" or scenario == "":
            continue
        days = int(float(row.get("days", 0) or 0))
        asin_days_by_scenario[(asin_norm, scenario)] = days
        asin_rate_pct = float(row.get("measured_signal", 0.0) or 0.0) * 100.0
        global_rate_pct = float(global_by_scenario.get(scenario, shared_sales_default_pct))
        blended_rate_pct = (
            ((asin_rate_pct * days) + (global_rate_pct * MEASURED_SHARE_PRIOR_DAYS))
            / max(1, (days + MEASURED_SHARE_PRIOR_DAYS))
        )
        asin_by_scenario[(asin_norm, scenario)] = max(0.0, min(100.0, blended_rate_pct))

    return global_by_scenario, asin_by_scenario, asin_days_by_scenario


def _apply_scenario_share_cap(share_pct: float, competition_scenario: str) -> float:
    cap = float(SCENARIO_SHARE_CAP_PCT.get(_normalize_text(competition_scenario), 100.0))
    return max(0.0, min(cap, share_pct))


def _price_zone(market_price: float | None, median_30d: float | None, warn_ratio: float, red_ratio: float, extreme_ratio: float) -> tuple[str, float | None]:
    if market_price is None or median_30d is None or median_30d <= 0:
        return "normal", None
    stretch_ratio = market_price / median_30d
    if stretch_ratio >= extreme_ratio:
        return "probable_ceiling_breach", stretch_ratio
    if stretch_ratio >= red_ratio:
        return "stretched", stretch_ratio
    if stretch_ratio >= warn_ratio:
        return "stretched", stretch_ratio
    return "normal", stretch_ratio


def _demand_state(bsr_value: float | None, bsr_median_30d: float | None) -> str:
    if bsr_value is None or bsr_median_30d is None or bsr_median_30d <= 0:
        return "stable"
    ratio = bsr_value / bsr_median_30d
    if ratio >= 1.25:
        return "deteriorating"
    if ratio >= 1.1:
        return "weakened"
    return "stable"


def _demand_multiplier(demand_state: str) -> float:
    if demand_state == "stable":
        return 1.0
    if demand_state == "weakened":
        return 0.7
    return 0.4


def _roi_pct(simulated_price_gbp: float | None, break_even_price_gbp: float | None) -> float | None:
    if simulated_price_gbp is None or break_even_price_gbp is None or break_even_price_gbp <= 0:
        return None
    return ((simulated_price_gbp / break_even_price_gbp) - 1.0) * 100.0


def _roi_band(roi_pct: float | None, entry_target: float, working_floor: float, exit_floor: float, emergency_floor: float) -> str:
    if roi_pct is None:
        return ""
    if roi_pct >= entry_target:
        return "entry_or_above"
    if roi_pct >= working_floor:
        return "working_band"
    if roi_pct >= exit_floor:
        return "exit_band"
    if roi_pct >= emergency_floor:
        return "emergency_band"
    return "deep_loss_band"


def _replay_mode(roi_pct: float | None, working_floor: float, exit_floor: float) -> str:
    if roi_pct is None:
        return "hold_wait"
    if roi_pct >= working_floor:
        return "normal_sell"
    if roi_pct >= exit_floor:
        return "hold_wait"
    return "sell_off"


def _ceiling_confidence(paired_buy_box_bsr_days: int, buy_box_coverage_share: float) -> str:
    if paired_buy_box_bsr_days >= 90 and buy_box_coverage_share >= 0.6:
        return "high"
    if paired_buy_box_bsr_days >= 30 and buy_box_coverage_share >= 0.3:
        return "medium"
    return "low"


def run_backtest_replay(
    root: Path | None = None,
    *,
    observed_utc: str | None = None,
) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)
    snapshot_utc = observed_utc or _utc_now_iso()

    source_data: dict[str, SourceReadResult] = {key: _read_source(root_path, key) for key in MANDATORY_SOURCE_KEYS}
    _validate_sources(source_data)

    policy_row = _active_policy_row(source_data["feeder_backtest_policy_live"].df)
    policy_id = _normalize_text(policy_row.get("policy_id", ""))
    if policy_id == "":
        raise ValueError("active policy row missing policy_id")

    warn_ratio = _num_or_none(policy_row.get("ceiling_warn_ratio_30d", "")) or 1.25
    red_ratio = _num_or_none(policy_row.get("ceiling_red_ratio_30d", "")) or 1.5
    extreme_ratio = _num_or_none(policy_row.get("ceiling_extreme_ratio_30d", "")) or 2.0
    shared_sales_default_pct = _num_or_none(policy_row.get("shared_sales_default_pct", "")) or 50.0
    entry_target = _num_or_none(policy_row.get("entry_target_roi_pct", "")) or 20.0
    working_floor = _num_or_none(policy_row.get("working_floor_roi_pct", "")) or 10.0
    exit_floor = _num_or_none(policy_row.get("exit_floor_roi_pct", "")) or 0.0
    emergency_floor = _num_or_none(policy_row.get("emergency_floor_roi_pct", "")) or -5.0

    input_df = source_data["feeder_backtest_input_view_live"].df.copy()
    if input_df.empty:
        out_df = _write_contract_df(pd.DataFrame(), "feeder_backtest_replay_daily_live", root_path)
        print(
            {
                "status": "success",
                "rows": 0,
                "ready_inputs": 0,
                "notes": "input view is empty",
            }
        )
        return out_df

    input_df["asin_norm"] = input_df.get("asin", "").map(_normalize_key)
    input_df["seller_sku"] = input_df.get("seller_sku", "").map(_normalize_text)
    ready_df = input_df[input_df.get("input_status", "").map(lambda v: _normalize_text(v).lower() == "ready")].copy()
    if ready_df.empty:
        out_df = _write_contract_df(pd.DataFrame(), "feeder_backtest_replay_daily_live", root_path)
        print(
            {
                "status": "success",
                "rows": 0,
                "ready_inputs": 0,
                "notes": "no ready input rows",
            }
        )
        return out_df

    chart_daily = _aggregate_chart_daily(source_data["feeder_legacy_chart_daily_raw_live"].df)
    if chart_daily.empty:
        out_df = _write_contract_df(pd.DataFrame(), "feeder_backtest_replay_daily_live", root_path)
        print(
            {
                "status": "success",
                "rows": 0,
                "ready_inputs": int(len(ready_df.index)),
                "notes": "chart history empty after normalization",
            }
        )
        return out_df

    global_scenario_share_pct, asin_scenario_share_pct, asin_scenario_days = _build_measured_share_maps(
        chart_daily,
        shared_sales_default_pct=shared_sales_default_pct,
    )

    chart_by_asin: dict[str, pd.DataFrame] = {}
    for asin_norm, asin_df in chart_daily.groupby("asin_norm"):
        chart_by_asin[asin_norm] = asin_df.sort_values("day_date", ascending=True, kind="stable").reset_index(drop=True)

    rows: list[dict[str, str]] = []
    for _, input_row in ready_df.iterrows():
        asin_norm = _normalize_text(input_row.get("asin_norm", ""))
        seller_sku = _normalize_text(input_row.get("seller_sku", ""))
        if asin_norm == "":
            continue
        asin_daily = chart_by_asin.get(asin_norm)
        if asin_daily is None or asin_daily.empty:
            continue

        median_30d = _num_or_none(input_row.get("price_median_30d_gbp", ""))
        bsr_median_30d = _num_or_none(input_row.get("bsr_median_30d", ""))
        base_velocity = _num_or_none(input_row.get("base_velocity_30d_units_per_day", "")) or 0.0
        raw_demand_units_monthly = _num_or_none(input_row.get("demand_basis_units_monthly", ""))
        qualified_units_monthly = _num_or_none(input_row.get("price_qualified_units_monthly", ""))
        qualified_profit_monthly_gbp = _num_or_none(input_row.get("price_qualified_profit_monthly_gbp", ""))
        price_qualification_reason_codes = _normalize_text(input_row.get("price_qualification_reason_codes", ""))
        qualification_market_gate_state = _normalize_text(input_row.get("qualification_market_gate_state", ""))
        qualification_market_gate_factor = _num_or_none(input_row.get("qualification_market_gate_factor", ""))
        qualification_amazon_pressure_factor = _num_or_none(input_row.get("qualification_amazon_pressure_factor", ""))
        qualification_buy_box_coverage_factor = _num_or_none(input_row.get("qualification_buy_box_coverage_factor", ""))
        qualification_maturity_factor = _num_or_none(input_row.get("qualification_maturity_factor", ""))
        qualification_final_factor = _num_or_none(input_row.get("qualification_final_factor", ""))
        qualification_zero_or_block_reason = _normalize_text(input_row.get("qualification_zero_or_block_reason", ""))
        history_maturity_state = _normalize_text(input_row.get("history_maturity_state", ""))
        seasonality_state = _normalize_text(input_row.get("seasonality_state", ""))
        seasonality_reason_codes = _normalize_text(input_row.get("seasonality_reason_codes", ""))
        stability_state = _normalize_text(input_row.get("stability_state", ""))
        stability_reason_codes = _normalize_text(input_row.get("stability_reason_codes", ""))
        recent_vs_baseline_state = _normalize_text(input_row.get("recent_vs_baseline_state", ""))
        recent_vs_baseline_reason_codes = _normalize_text(input_row.get("recent_vs_baseline_reason_codes", ""))
        completed_months_count = _num_or_none(input_row.get("completed_months_count", ""))
        qualification_value_source = "input_qualified"
        if qualified_units_monthly is None or qualified_profit_monthly_gbp is None:
            qualification_value_source = "replay_fallback"
        effective_velocity = (qualified_units_monthly / 30.0) if qualified_units_monthly is not None else base_velocity
        demand_basis_source = _normalize_text(input_row.get("demand_basis_source", "")) or "legacy_base_velocity"
        demand_basis_units_monthly = _num_or_none(input_row.get("demand_basis_units_monthly", ""))
        if demand_basis_units_monthly is None and effective_velocity > 0:
            demand_basis_units_monthly = effective_velocity * 30.0
        bbp_last_completed_month_units = _num_or_none(input_row.get("bbp_sales_last_completed_month_units", "")) or 0.0
        bbp_future_month_count_ignored = _num_or_none(input_row.get("bbp_sales_future_month_count_ignored", "")) or 0.0
        cost_gbp = _num_or_none(input_row.get("current_supplier_buy_cost_gbp", ""))
        break_even_gbp = _num_or_none(input_row.get("break_even_price_gbp", ""))
        refund_cost_gbp = _num_or_none(input_row.get("expected_refund_cost_per_unit_gbp", "")) or 0.0
        seasonality_mult = _seasonality_multiplier(seasonality_state)
        manual_review_flag = _normalize_text(input_row.get("manual_review_flag", "")) or "0"
        paired_buy_box_bsr_days = int(_num_or_none(input_row.get("paired_buy_box_bsr_days", "")) or 0)
        buy_box_coverage_share = _num_or_none(input_row.get("buy_box_coverage_share", "")) or 0.0
        ceiling_confidence = _ceiling_confidence(paired_buy_box_bsr_days, buy_box_coverage_share)

        for _, day_row in asin_daily.iterrows():
            market_price = _num_or_none(day_row.get("market_price_gbp", ""))
            buy_box_price = _num_or_none(day_row.get("buy_box_price_gbp", ""))
            amazon_price = _num_or_none(day_row.get("amazon_price_gbp", ""))
            fba_price = _num_or_none(day_row.get("lowest_fba_price_gbp", ""))
            fbm_price = _num_or_none(day_row.get("lowest_fbm_price_gbp", ""))
            bsr_value = _num_or_none(day_row.get("bsr_value", ""))

            simulated_price = market_price
            price_zone, stretch_ratio = _price_zone(market_price, median_30d, warn_ratio, red_ratio, extreme_ratio)
            demand_state = _demand_state(bsr_value, bsr_median_30d)
            competition_scenario = _competition_scenario(
                bool(day_row.get("amazon_present", False)),
                bool(day_row.get("fba_present", False)),
            )
            scenario_key = (asin_norm, competition_scenario)
            base_share = asin_scenario_share_pct.get(scenario_key)
            share_source_tag = "share_source_asin_blend"
            sparse_asin_history = False
            if base_share is None:
                base_share = global_scenario_share_pct.get(competition_scenario, shared_sales_default_pct)
                share_source_tag = "share_source_global_prior"
                sparse_asin_history = True
            else:
                scenario_days = int(asin_scenario_days.get(scenario_key, 0))
                if scenario_days < MIN_ASIN_SCENARIO_DAYS:
                    share_source_tag = "share_source_sparse_asin_blend"
                    sparse_asin_history = True

            governed_share = _apply_scenario_share_cap(float(base_share), competition_scenario)
            share_cap_applied = governed_share < float(base_share)

            price_matching = False
            if simulated_price is not None and market_price is not None and market_price > 0:
                gap = abs(simulated_price - market_price) / market_price
                price_matching = gap <= PRICE_MATCH_TOLERANCE
            sales_share_pct = governed_share if price_matching else max(5.0, governed_share * 0.2)

            roi_pct = _roi_pct(simulated_price, break_even_gbp)
            roi_band = _roi_band(roi_pct, entry_target, working_floor, exit_floor, emergency_floor)
            replay_mode = _replay_mode(roi_pct, working_floor, exit_floor)

            demand_mult = _demand_multiplier(demand_state)
            estimated_listing_units = effective_velocity * seasonality_mult * demand_mult
            estimated_units_ours = estimated_listing_units * (sales_share_pct / 100.0)

            unit_profit = None
            if simulated_price is not None and cost_gbp is not None:
                unit_profit = simulated_price - cost_gbp - refund_cost_gbp
            estimated_profit = (estimated_units_ours * unit_profit) if unit_profit is not None else None

            failure_event_flag = "1" if replay_mode == "sell_off" else "0"
            reason_codes: list[str] = []
            if not price_matching:
                reason_codes.append("not_price_matching")
            if stretch_ratio is not None and stretch_ratio >= red_ratio:
                reason_codes.append("stretched_price_zone")
            if demand_state == "deteriorating":
                reason_codes.append("demand_deteriorating")
            if roi_pct is not None and roi_pct < emergency_floor:
                reason_codes.append("roi_below_emergency_floor")
            reason_codes.append(share_source_tag)
            reason_codes.append(f"demand_basis_{demand_basis_source}")
            if seasonality_state != "":
                reason_codes.append(f"seasonality_state_{seasonality_state}")
            if stability_state != "":
                reason_codes.append(f"stability_state_{stability_state}")
            if recent_vs_baseline_state != "":
                reason_codes.append(f"recent_vs_baseline_state_{recent_vs_baseline_state}")
            if sparse_asin_history:
                reason_codes.append("share_sparse_asin_history")
            if share_cap_applied:
                reason_codes.append("share_governance_cap_applied")
            if bbp_future_month_count_ignored > 0:
                reason_codes.append("bbp_future_months_ignored")
            if demand_basis_source == "bbp_units_chosen_fallback":
                reason_codes.append("demand_basis_helper_chosen_fallback")
            if qualified_units_monthly is not None:
                reason_codes.append("qualified_units_applied")
            reason_codes.append(f"qualification_value_source_{qualification_value_source}")
            if qualification_final_factor is not None and qualification_final_factor < 0.999:
                reason_codes.append("qualification_factor_reduced")
            if qualification_zero_or_block_reason != "":
                reason_codes.append(f"qualification_zero_or_block_{qualification_zero_or_block_reason}")
            if price_qualification_reason_codes != "":
                reason_codes.append("qualification_reason_codes_present")
            if "high_volatility" in recent_vs_baseline_reason_codes.split("|"):
                reason_codes.append("recent_high_volatility")
            reason_codes = [code for code in dict.fromkeys(reason_codes) if _normalize_text(code) != ""]

            rows.append(
                {
                    "observed_utc": snapshot_utc,
                    "policy_id": policy_id,
                    "seller_sku": seller_sku,
                    "asin": asin_norm,
                    "day": day_row.get("day_date").isoformat(),
                    "replay_status": "ok",
                    "competition_scenario": competition_scenario,
                    "replay_mode": replay_mode,
                    "price_zone": price_zone,
                    "demand_state": demand_state,
                    "simulated_price_gbp": _num_to_text(simulated_price),
                    "buy_box_price_gbp": _num_to_text(buy_box_price),
                    "amazon_price_gbp": _num_to_text(amazon_price),
                    "lowest_fba_price_gbp": _num_to_text(fba_price),
                    "lowest_fbm_price_gbp": _num_to_text(fbm_price),
                    "bsr_value": _num_to_text(bsr_value),
                    "sales_share_pct": _num_to_text(sales_share_pct),
                    "seasonality_multiplier": _num_to_text(seasonality_mult),
                    "estimated_listing_units": _num_to_text(estimated_listing_units),
                    "estimated_units_ours": _num_to_text(estimated_units_ours),
                    "estimated_profit_gbp": _num_to_text(estimated_profit),
                    "failure_event_flag": failure_event_flag,
                    "manual_review_flag": manual_review_flag,
                    "demand_basis_source": demand_basis_source,
                    "demand_basis_units_monthly": _num_to_text(demand_basis_units_monthly),
                    "bbp_sales_last_completed_month_units": _num_to_text(bbp_last_completed_month_units),
                    "bbp_sales_future_month_count_ignored": _num_to_text(bbp_future_month_count_ignored),
                    "seasonality_state": seasonality_state,
                    "seasonality_reason_codes": seasonality_reason_codes,
                    "stability_state": stability_state,
                    "stability_reason_codes": stability_reason_codes,
                    "recent_vs_baseline_state": recent_vs_baseline_state,
                    "recent_vs_baseline_reason_codes": recent_vs_baseline_reason_codes,
                    "completed_months_count": _num_to_text(completed_months_count),
                    "history_maturity_state": history_maturity_state,
                    "raw_demand_units_monthly": _num_to_text(raw_demand_units_monthly),
                    "price_qualified_units_monthly": _num_to_text(qualified_units_monthly),
                    "price_qualified_profit_monthly_gbp": _num_to_text(qualified_profit_monthly_gbp),
                    "price_qualification_reason_codes": price_qualification_reason_codes,
                    "qualification_market_gate_state": qualification_market_gate_state,
                    "qualification_market_gate_factor": _num_to_text(qualification_market_gate_factor),
                    "qualification_amazon_pressure_factor": _num_to_text(qualification_amazon_pressure_factor),
                    "qualification_buy_box_coverage_factor": _num_to_text(qualification_buy_box_coverage_factor),
                    "qualification_maturity_factor": _num_to_text(qualification_maturity_factor),
                    "qualification_final_factor": _num_to_text(qualification_final_factor),
                    "qualification_zero_or_block_reason": qualification_zero_or_block_reason,
                    "qualification_value_source": qualification_value_source,
                    "reason_codes": "|".join(reason_codes),
                    "roi_band": roi_band,
                    "ceiling_confidence": ceiling_confidence,
                    "notes": "",
                }
            )

    out_df = _write_contract_df(pd.DataFrame(rows), "feeder_backtest_replay_daily_live", root_path)
    failure_rows = int((out_df["failure_event_flag"] == "1").sum()) if not out_df.empty else 0
    print(
        {
            "status": "success",
            "rows": int(len(out_df)),
            "ready_inputs": int(len(ready_df.index)),
            "failure_rows": failure_rows,
            "policy_id": policy_id,
            "snapshot": str(root_path / get_f_output_contract("feeder_backtest_replay_daily_live").rel_path),
        }
    )
    return out_df


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run F backtest daily replay from prepared input view.")
    parser.add_argument("--observed-utc", default=None, help="Override observed_utc for deterministic runs.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    run_backtest_replay(observed_utc=args.observed_utc)


if __name__ == "__main__":
    main()
