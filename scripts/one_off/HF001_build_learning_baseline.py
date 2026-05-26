from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"
MARKET_FACTS_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "hf_learning_market_facts_latest.csv"
ACTION_OUTCOMES_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "hf_learning_action_outcomes_latest.csv"
SCRAPE_GAP_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "hf_learning_scrape_gap_report_latest.csv"

IDENTITY_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_identity_bridge_latest.csv"
ASSUMPTION_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_assumption_snapshots_latest.csv"
H_OUTCOME_LOG_PATH = ROOT / "out" / "h_strategy_outcome_log.csv"
H_OUTCOME_DAILY_PATH = ROOT / "out" / "h_strategy_outcome_daily.csv"
LISTING_SNAPSHOT_PATH = ROOT / "out" / "listing_offer_snapshot_latest.csv"
LISTING_SELLER_SNAPSHOT_PATH = ROOT / "out" / "listing_offer_seller_snapshot_latest.csv"
LISTING_HISTORY_PATH = ROOT / "out" / "listing_offer_history.csv"
LISTING_SELLER_HISTORY_PATH = ROOT / "out" / "listing_offer_seller_observation_history.csv"
HOS_MARKET_PATH = ROOT / "out" / "hos_daily_market_snapshot_latest.csv"
SKU_PERF_PATH = ROOT / "out" / "sku_performance_summary.csv"
SKU_VELOCITY_PATH = ROOT / "out" / "sku_sales_velocity.csv"
F_SALES_VALIDATION_PATH = ROOT / "out" / "analysis_reports" / "f_sales_history_validation_latest.csv"
F_CALIBRATION_PATH = ROOT / "out" / "analysis_reports" / "f_backtest_calibration_set_latest.csv"
F_LEGACY_EVIDENCE_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv"
F_LEGACY_CHART_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_legacy_chart_daily_raw_live.csv"
F_FULL_CAPTURE_FACTS_PATH = ROOT / "out" / "analysis_reports" / "f_full_capture_normalized_facts_latest.csv"

SCANNER_OWNED_INPUTS = [F_LEGACY_EVIDENCE_PATH, F_LEGACY_CHART_PATH]

REQUIRED_INPUTS = [
    IDENTITY_PATH,
    ASSUMPTION_PATH,
    H_OUTCOME_LOG_PATH,
    H_OUTCOME_DAILY_PATH,
    LISTING_SNAPSHOT_PATH,
    LISTING_SELLER_SNAPSHOT_PATH,
    LISTING_HISTORY_PATH,
    LISTING_SELLER_HISTORY_PATH,
    HOS_MARKET_PATH,
    SKU_PERF_PATH,
    SKU_VELOCITY_PATH,
    F_SALES_VALIDATION_PATH,
    F_CALIBRATION_PATH,
    F_LEGACY_EVIDENCE_PATH,
    F_LEGACY_CHART_PATH,
]

SCRAPE_OWNER_PATH = (
    "scripts/one_off/F007_prepare_targeted_rescrape_subset.py|"
    "scripts/flows/F/F061_run_legacy_first_checks_local.py"
)
FULL_CAPTURE_OWNER_PATH = (
    "scripts/one_off/HF006_build_alignment_missing_asin_pack.py|"
    "scripts/one_off/F008_capture_full_bbp_evidence_pack.py|"
    "scripts/one_off/F009_build_full_capture_consistency_audit.py"
)
SCRAPE_STALE_DAYS = 30
SCRAPE_THIN_MIN_ROWS = 30


@dataclass(frozen=True)
class BaselineBuildResult:
    market_facts_path: Path
    market_facts_rows: int
    action_outcomes_path: Path
    action_outcomes_rows: int
    scrape_gap_path: Path
    scrape_gap_rows: int
    scrape_gap_missing_rows: int
    scrape_gap_stale_rows: int
    scrape_gap_thin_rows: int
    scrape_gap_ok_rows: int
    scanner_source_hash_verified: bool


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _column_as_text(df: pd.DataFrame, column: str) -> pd.Series:
    if column in df.columns:
        return df[column].map(_normalize_text)
    return pd.Series([""] * len(df.index), index=df.index, dtype=str)


def _read_csv_required(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"required batch-001 input missing: {path}")
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _read_csv_optional(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _to_float(value: object) -> float | None:
    text = _normalize_text(value)
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _float_to_text(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _to_binary_flag(value: object) -> str:
    text = _normalize_text(value).lower()
    if text in {"1", "true", "yes", "y"}:
        return "1"
    if text in {"0", "false", "no", "n"}:
        return "0"
    return "0"


def _latest_non_empty_map(df: pd.DataFrame, *, key_col: str, value_col: str, ts_col: str) -> dict[str, str]:
    if df.empty:
        return {}
    work = pd.DataFrame()
    work["key"] = _column_as_text(df, key_col)
    work["value"] = _column_as_text(df, value_col)
    work["event_utc"] = _column_as_text(df, ts_col)
    work = work[(work["key"] != "") & (work["value"] != "")].copy()
    if work.empty:
        return {}
    work = work.sort_values(["key", "event_utc"], ascending=[True, False], kind="stable")
    latest = work.drop_duplicates(subset=["key"], keep="first")
    return {row["key"]: row["value"] for _, row in latest.iterrows()}


def _unique_values_map(df: pd.DataFrame, *, key_col: str, value_col: str) -> dict[str, list[str]]:
    if df.empty:
        return {}
    work = pd.DataFrame()
    work["key"] = _column_as_text(df, key_col)
    work["value"] = _column_as_text(df, value_col)
    work = work[(work["key"] != "") & (work["value"] != "")].copy()
    if work.empty:
        return {}
    grouped = work.groupby("key")["value"].apply(list)
    out: dict[str, list[str]] = {}
    for key, values in grouped.items():
        dedup: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = _normalize_text(value)
            if text == "" or text in seen:
                continue
            seen.add(text)
            dedup.append(text)
        out[str(key)] = dedup
    return out


def _snapshot_from_listing(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    out["observation_utc"] = _column_as_text(df, "timestamp_utc")
    out["asof_date"] = _column_as_text(df, "asof_date")
    out["sku"] = _column_as_text(df, "sku")
    out["asin"] = _column_as_text(df, "asin")
    out["our_price_gbp"] = _column_as_text(df, "our_price")
    out["buy_box_price_gbp"] = _column_as_text(df, "buy_box_price")
    out["lowest_fba_price_gbp"] = _column_as_text(df, "lowest_fba_price")
    out["lowest_fbm_price_gbp"] = _column_as_text(df, "lowest_fbm_price")
    out["offer_count_fba"] = _column_as_text(df, "offer_count_fba")
    out["offer_count_fbm"] = _column_as_text(df, "offer_count_fbm")
    out["bsr"] = _column_as_text(df, "bsr")
    out = out[(out["observation_utc"] != "") & (out["sku"] != "")].copy()
    return out


def _build_market_facts(
    *,
    listing_history_df: pd.DataFrame,
    listing_snapshot_df: pd.DataFrame,
    hos_df: pd.DataFrame,
    sku_perf_df: pd.DataFrame,
    identity_df: pd.DataFrame,
    assumption_df: pd.DataFrame,
) -> pd.DataFrame:
    history_rows = _snapshot_from_listing(listing_history_df)
    snapshot_rows = _snapshot_from_listing(listing_snapshot_df)
    market = pd.concat([history_rows, snapshot_rows], ignore_index=True)
    if market.empty:
        return pd.DataFrame(
            columns=[
                "observation_utc",
                "asof_date",
                "sku",
                "asin",
                "our_price_gbp",
                "buy_box_price_gbp",
                "lowest_fba_price_gbp",
                "lowest_fbm_price_gbp",
                "offer_count_fba",
                "offer_count_fbm",
                "amazon_present_flag",
                "seller_entry_count_today",
                "seller_exit_count_today",
                "delivery_parity_flag",
                "break_even_gross_gbp",
                "bsr",
                "foundation_identity_snapshot_utc",
                "foundation_assumption_snapshot_utc",
            ]
        )

    market = market.sort_values(["observation_utc", "sku", "asin"], ascending=[False, True, True], kind="stable")
    market = market.drop_duplicates(subset=["observation_utc", "sku", "asin"], keep="first")

    hos = pd.DataFrame()
    hos["asof_date"] = _column_as_text(hos_df, "asof_date")
    hos["sku"] = _column_as_text(hos_df, "sku")
    hos["asin"] = _column_as_text(hos_df, "asin")
    hos["amazon_present_flag"] = _column_as_text(hos_df, "amazon_present_flag")
    hos["seller_entry_count_today"] = _column_as_text(hos_df, "seller_entry_count_today")
    hos["seller_exit_count_today"] = _column_as_text(hos_df, "seller_exit_count_today")
    hos["delivery_parity_flag"] = _column_as_text(hos_df, "delivery_parity_flag")
    hos["break_even_gross_gbp_hos"] = _column_as_text(hos_df, "break_even_gross_gbp")
    hos = hos[(hos["asof_date"] != "") & (hos["sku"] != "")].copy()
    hos = hos.drop_duplicates(subset=["asof_date", "sku", "asin"], keep="last")

    market = market.merge(hos, on=["asof_date", "sku", "asin"], how="left")

    perf = pd.DataFrame()
    perf["sku"] = _column_as_text(sku_perf_df, "sku")
    perf["break_even_gross_gbp_perf"] = _column_as_text(sku_perf_df, "break_even_price_gbp")
    perf = perf[perf["sku"] != ""].drop_duplicates(subset=["sku"], keep="last")
    market = market.merge(perf, on="sku", how="left")

    market["amazon_present_flag"] = market["amazon_present_flag"].map(_to_binary_flag)
    market["delivery_parity_flag"] = market["delivery_parity_flag"].map(_to_binary_flag)
    market["seller_entry_count_today"] = market["seller_entry_count_today"].map(_normalize_text)
    market["seller_exit_count_today"] = market["seller_exit_count_today"].map(_normalize_text)
    market["break_even_gross_gbp"] = market["break_even_gross_gbp_hos"].where(
        market["break_even_gross_gbp_hos"].map(_normalize_text) != "",
        market["break_even_gross_gbp_perf"],
    )

    identity_snapshot_utc = ""
    if not identity_df.empty:
        identity_snapshot_utc = _column_as_text(identity_df, "snapshot_utc").sort_values(ascending=False).iloc[0]
    assumption_snapshot_utc = ""
    if not assumption_df.empty:
        assumption_snapshot_utc = _column_as_text(assumption_df, "snapshot_utc").sort_values(ascending=False).iloc[0]
    market["foundation_identity_snapshot_utc"] = identity_snapshot_utc
    market["foundation_assumption_snapshot_utc"] = assumption_snapshot_utc

    out = pd.DataFrame()
    out["observation_utc"] = market["observation_utc"].map(_normalize_text)
    out["asof_date"] = market["asof_date"].map(_normalize_text)
    out["sku"] = market["sku"].map(_normalize_text)
    out["asin"] = market["asin"].map(_normalize_text)
    out["our_price_gbp"] = market["our_price_gbp"].map(_normalize_text)
    out["buy_box_price_gbp"] = market["buy_box_price_gbp"].map(_normalize_text)
    out["lowest_fba_price_gbp"] = market["lowest_fba_price_gbp"].map(_normalize_text)
    out["lowest_fbm_price_gbp"] = market["lowest_fbm_price_gbp"].map(_normalize_text)
    out["offer_count_fba"] = market["offer_count_fba"].map(_normalize_text)
    out["offer_count_fbm"] = market["offer_count_fbm"].map(_normalize_text)
    out["amazon_present_flag"] = market["amazon_present_flag"].map(_normalize_text)
    out["seller_entry_count_today"] = market["seller_entry_count_today"].map(_normalize_text)
    out["seller_exit_count_today"] = market["seller_exit_count_today"].map(_normalize_text)
    out["delivery_parity_flag"] = market["delivery_parity_flag"].map(_normalize_text)
    out["break_even_gross_gbp"] = market["break_even_gross_gbp"].map(_normalize_text)
    out["bsr"] = market["bsr"].map(_normalize_text)
    out["foundation_identity_snapshot_utc"] = market["foundation_identity_snapshot_utc"].map(_normalize_text)
    out["foundation_assumption_snapshot_utc"] = market["foundation_assumption_snapshot_utc"].map(_normalize_text)
    out = out[(out["observation_utc"] != "") & (out["sku"] != "") & (out["asin"] != "")].copy()
    out = out.sort_values(["observation_utc", "sku", "asin"], ascending=[False, True, True], kind="stable")
    return out


def _build_action_outcomes(
    *,
    outcome_log_df: pd.DataFrame,
    outcome_daily_df: pd.DataFrame,
    market_facts_df: pd.DataFrame,
) -> pd.DataFrame:
    if outcome_log_df.empty:
        return pd.DataFrame(
            columns=[
                "event_ts_utc",
                "run_id",
                "sku",
                "asin",
                "scenario_type",
                "chosen_tactic",
                "eligible_to_write_flag",
                "decision_to_change_price_flag",
                "write_attempted_flag",
                "write_applied_flag",
                "our_price_before_gbp",
                "target_price_gbp",
                "price_written_gbp",
                "buy_box_state_before",
                "buy_box_state_after",
                "seller_count",
                "response_window_minutes",
                "tactic_success_state",
                "reason_codes_json",
                "writer_outcome",
                "market_observation_utc",
                "market_amazon_present_flag",
                "daily_decision_rows",
                "daily_success_rate_pct",
            ]
        )

    out = pd.DataFrame()
    out["event_ts_utc"] = _column_as_text(outcome_log_df, "event_ts_utc")
    out["run_id"] = _column_as_text(outcome_log_df, "run_id")
    out["sku"] = _column_as_text(outcome_log_df, "sku")
    out["asin"] = _column_as_text(outcome_log_df, "asin")
    out["scenario_type"] = _column_as_text(outcome_log_df, "scenario_type")
    out["chosen_tactic"] = _column_as_text(outcome_log_df, "chosen_tactic")
    out["our_price_before_gbp"] = _column_as_text(outcome_log_df, "our_price_before_gbp")
    out["target_price_gbp"] = _column_as_text(outcome_log_df, "target_price_gbp")
    out["price_written_gbp"] = _column_as_text(outcome_log_df, "price_written_gbp")
    out["buy_box_state_before"] = _column_as_text(outcome_log_df, "buy_box_state_before")
    out["buy_box_state_after"] = _column_as_text(outcome_log_df, "buy_box_state_after")
    out["seller_count"] = _column_as_text(outcome_log_df, "seller_count")
    out["response_window_minutes"] = _column_as_text(outcome_log_df, "response_window_minutes")
    out["tactic_success_state"] = _column_as_text(outcome_log_df, "tactic_success_state")
    out["reason_codes_json"] = _column_as_text(outcome_log_df, "reason_codes_json")
    out["writer_outcome"] = _column_as_text(outcome_log_df, "writer_outcome")

    def _decision_flag(row: pd.Series) -> str:
        before_value = _to_float(row["our_price_before_gbp"])
        target_value = _to_float(row["target_price_gbp"])
        if before_value is None or target_value is None:
            return "0"
        return "1" if abs(before_value - target_value) >= 0.0001 else "0"

    out["eligible_to_write_flag"] = out["writer_outcome"].map(
        lambda value: "0" if _normalize_text(value) == "READ_ONLY_NO_WRITE" else "1"
    )
    out["decision_to_change_price_flag"] = out.apply(_decision_flag, axis=1)
    out["write_attempted_flag"] = out["writer_outcome"].map(
        lambda value: "1" if _normalize_text(value) in {"APPLIED", "WRITE_REJECTED"} else "0"
    )
    out["write_applied_flag"] = out["writer_outcome"].map(
        lambda value: "1" if _normalize_text(value) == "APPLIED" else "0"
    )

    market_latest = pd.DataFrame()
    if not market_facts_df.empty:
        market_latest = market_facts_df.copy()
        market_latest["sku"] = _column_as_text(market_latest, "sku")
        market_latest["asin"] = _column_as_text(market_latest, "asin")
        market_latest["observation_utc"] = _column_as_text(market_latest, "observation_utc")
        market_latest["amazon_present_flag"] = _column_as_text(market_latest, "amazon_present_flag")
        market_latest = market_latest[(market_latest["sku"] != "") & (market_latest["asin"] != "")].copy()
        market_latest = market_latest.sort_values(
            ["sku", "asin", "observation_utc"],
            ascending=[True, True, False],
            kind="stable",
        )
        market_latest = market_latest.drop_duplicates(subset=["sku", "asin"], keep="first")
        market_latest = market_latest.rename(
            columns={
                "observation_utc": "market_observation_utc",
                "amazon_present_flag": "market_amazon_present_flag",
            }
        )[["sku", "asin", "market_observation_utc", "market_amazon_present_flag"]]

    if not market_latest.empty:
        out = out.merge(market_latest, on=["sku", "asin"], how="left")
    else:
        out["market_observation_utc"] = ""
        out["market_amazon_present_flag"] = ""

    out["asof_date"] = out["event_ts_utc"].map(lambda value: _normalize_text(value)[:10] if _normalize_text(value) else "")
    daily = pd.DataFrame()
    daily["asof_date"] = _column_as_text(outcome_daily_df, "asof_date")
    daily["scenario_type"] = _column_as_text(outcome_daily_df, "scenario_type")
    daily["chosen_tactic"] = _column_as_text(outcome_daily_df, "chosen_tactic")
    daily["daily_decision_rows"] = _column_as_text(outcome_daily_df, "decision_rows")
    daily["daily_success_rate_pct"] = _column_as_text(outcome_daily_df, "success_rate_pct")
    daily = daily[(daily["asof_date"] != "") & (daily["scenario_type"] != "") & (daily["chosen_tactic"] != "")].copy()
    daily = daily.drop_duplicates(subset=["asof_date", "scenario_type", "chosen_tactic"], keep="last")
    out = out.merge(daily, on=["asof_date", "scenario_type", "chosen_tactic"], how="left")

    keep_columns = [
        "event_ts_utc",
        "run_id",
        "sku",
        "asin",
        "scenario_type",
        "chosen_tactic",
        "eligible_to_write_flag",
        "decision_to_change_price_flag",
        "write_attempted_flag",
        "write_applied_flag",
        "our_price_before_gbp",
        "target_price_gbp",
        "price_written_gbp",
        "buy_box_state_before",
        "buy_box_state_after",
        "seller_count",
        "response_window_minutes",
        "tactic_success_state",
        "reason_codes_json",
        "writer_outcome",
        "market_observation_utc",
        "market_amazon_present_flag",
        "daily_decision_rows",
        "daily_success_rate_pct",
    ]
    out = out[keep_columns].fillna("")
    for column in out.columns:
        out[column] = out[column].map(_normalize_text)
    out = out[(out["event_ts_utc"] != "") & (out["run_id"] != "") & (out["sku"] != "") & (out["asin"] != "")].copy()
    out = out.sort_values(["event_ts_utc", "run_id", "sku"], ascending=[False, False, True], kind="stable")
    return out


def _build_scrape_gap_report(
    *,
    identity_df: pd.DataFrame,
    assumption_df: pd.DataFrame,
    legacy_evidence_df: pd.DataFrame,
    legacy_chart_df: pd.DataFrame,
    full_capture_facts_df: pd.DataFrame,
    snapshot_utc: str,
) -> pd.DataFrame:
    if identity_df.empty:
        return pd.DataFrame(
            columns=[
                "observed_utc",
                "candidate_id",
                "supplier_id",
                "supplier_sku",
                "sku",
                "asin",
                "scrape_coverage_status",
                "rescrape_needed_flag",
                "rescrape_reason_codes",
                "queue_owner_path",
                "scrape_observed_utc",
                "chart_point_rows",
                "identity_sku_resolution_status",
                "assumption_snapshot_stage",
                "in_scope_approval_decision_flag",
            ]
        )

    evidence = pd.DataFrame()
    evidence["candidate_id"] = _column_as_text(legacy_evidence_df, "candidate_id")
    evidence["supplier_sku"] = _column_as_text(legacy_evidence_df, "supplier_sku")
    evidence["asin"] = _column_as_text(legacy_evidence_df, "asin")
    evidence["observed_utc"] = _column_as_text(legacy_evidence_df, "observed_utc")
    evidence["scrape_success"] = _column_as_text(legacy_evidence_df, "scrape_success")
    evidence = evidence[
        (evidence["candidate_id"] != "") | ((evidence["supplier_sku"] != "") & (evidence["asin"] != ""))
    ].copy()

    chart = pd.DataFrame()
    chart["candidate_id"] = _column_as_text(legacy_chart_df, "candidate_id")
    chart["supplier_sku"] = _column_as_text(legacy_chart_df, "supplier_sku")
    chart["asin"] = _column_as_text(legacy_chart_df, "asin")
    chart["observed_utc"] = _column_as_text(legacy_chart_df, "observed_utc")
    chart = chart[
        (chart["candidate_id"] != "") | ((chart["supplier_sku"] != "") & (chart["asin"] != ""))
    ].copy()

    candidate_to_asin = _latest_non_empty_map(
        evidence,
        key_col="candidate_id",
        value_col="asin",
        ts_col="observed_utc",
    )
    supplier_to_asins = _unique_values_map(evidence, key_col="supplier_sku", value_col="asin")
    candidate_latest_observed = _latest_non_empty_map(
        evidence,
        key_col="candidate_id",
        value_col="observed_utc",
        ts_col="observed_utc",
    )

    supplier_asin_observed_map: dict[tuple[str, str], str] = {}
    if not evidence.empty:
        work = evidence.copy()
        work = work[(work["supplier_sku"] != "") & (work["asin"] != "") & (work["observed_utc"] != "")].copy()
        if not work.empty:
            work["pair_key"] = work["supplier_sku"] + "|" + work["asin"]
            work = work.sort_values(["pair_key", "observed_utc"], ascending=[True, False], kind="stable")
            work = work.drop_duplicates(subset=["pair_key"], keep="first")
            for _, row in work.iterrows():
                supplier_asin_observed_map[(row["supplier_sku"], row["asin"])] = row["observed_utc"]

    chart_count_by_pair: dict[tuple[str, str], int] = {}
    if not chart.empty:
        pair_rows = chart[(chart["supplier_sku"] != "") & (chart["asin"] != "")].copy()
        if not pair_rows.empty:
            grouped = pair_rows.groupby(["supplier_sku", "asin"]).size()
            for (supplier_sku, asin), count in grouped.items():
                chart_count_by_pair[(str(supplier_sku), str(asin))] = int(count)

    full_capture_observed_by_asin: dict[str, str] = {}
    if not full_capture_facts_df.empty:
        capture = pd.DataFrame()
        capture["asin"] = _column_as_text(full_capture_facts_df, "asin")
        capture["capture_status"] = _column_as_text(full_capture_facts_df, "capture_status")
        capture["basis_source"] = _column_as_text(full_capture_facts_df, "bbp_sales_replay_demand_basis_source")
        capture["observed_utc"] = _column_as_text(full_capture_facts_df, "observed_utc")
        capture = capture[
            (capture["asin"] != "")
            & (capture["capture_status"] == "success")
            & (capture["basis_source"].isin({"bbp_last_completed_month", "bbp_zero_history"}))
        ].copy()
        if not capture.empty:
            capture = capture.sort_values(["asin", "observed_utc"], ascending=[True, False], kind="stable")
            capture = capture.drop_duplicates(subset=["asin"], keep="first")
            full_capture_observed_by_asin = {
                _normalize_text(row["asin"]): _normalize_text(row["observed_utc"])
                for _, row in capture.iterrows()
            }

    assumption_map: dict[str, dict[str, str]] = {}
    if not assumption_df.empty:
        assumption = assumption_df.copy()
        assumption["candidate_id"] = _column_as_text(assumption, "candidate_id")
        assumption["assumption_anchor_utc"] = _column_as_text(assumption, "assumption_anchor_utc")
        assumption = assumption[assumption["candidate_id"] != ""].copy()
        assumption = assumption.sort_values(
            ["candidate_id", "assumption_anchor_utc"],
            ascending=[True, False],
            kind="stable",
        )
        assumption = assumption.drop_duplicates(subset=["candidate_id"], keep="first")
        for _, row in assumption.iterrows():
            assumption_map[row["candidate_id"]] = {
                "assumption_snapshot_stage": _normalize_text(row.get("snapshot_stage", "")),
                "in_scope_approval_decision_flag": _normalize_text(row.get("in_scope_approval_decision_flag", "")),
            }

    snapshot_dt = pd.to_datetime(snapshot_utc, utc=True, errors="coerce")
    rows: list[dict[str, str]] = []
    for _, identity_row in identity_df.iterrows():
        candidate_id = _normalize_text(identity_row.get("candidate_id", ""))
        supplier_id = _normalize_text(identity_row.get("supplier_id", ""))
        supplier_sku = _normalize_text(identity_row.get("supplier_sku", ""))
        sku = _normalize_text(identity_row.get("sku", ""))
        asin = _normalize_text(identity_row.get("asin", ""))
        identity_status = _normalize_text(identity_row.get("sku_resolution_status", ""))

        if asin == "":
            asin = _normalize_text(candidate_to_asin.get(candidate_id, ""))
        if asin == "":
            supplier_asins = supplier_to_asins.get(supplier_sku, [])
            if len(supplier_asins) == 1:
                asin = supplier_asins[0]

        reasons: list[str] = []
        coverage_status = "ok"
        scrape_observed_utc = ""
        queue_owner_path = SCRAPE_OWNER_PATH

        if asin == "":
            coverage_status = "non_scraper_scope"
            reasons.append("NON_SCRAPER_SCOPE_NO_ASIN")
        else:
            scrape_observed_utc = _normalize_text(supplier_asin_observed_map.get((supplier_sku, asin), ""))
            if scrape_observed_utc == "":
                scrape_observed_utc = _normalize_text(candidate_latest_observed.get(candidate_id, ""))
            if scrape_observed_utc == "":
                coverage_status = "missing"
                reasons.append("MISSING_SCRAPE_EVIDENCE")
            else:
                observed_dt = pd.to_datetime(scrape_observed_utc, utc=True, errors="coerce")
                if pd.notna(snapshot_dt) and pd.notna(observed_dt):
                    age_days = int((snapshot_dt - observed_dt).total_seconds() // 86400)
                    if age_days > SCRAPE_STALE_DAYS:
                        coverage_status = "stale"
                        reasons.append("STALE_SCRAPE_EVIDENCE")

                chart_rows = chart_count_by_pair.get((supplier_sku, asin), 0)
                if chart_rows < SCRAPE_THIN_MIN_ROWS:
                    reasons.append("THIN_CHART_POINTS")
                    if coverage_status == "ok":
                        coverage_status = "thin"

            full_capture_observed = _normalize_text(full_capture_observed_by_asin.get(asin, ""))
            if full_capture_observed != "":
                coverage_status = "ok"
                if scrape_observed_utc == "":
                    scrape_observed_utc = full_capture_observed
                queue_owner_path = f"{SCRAPE_OWNER_PATH}|{FULL_CAPTURE_OWNER_PATH}"
                reasons = [
                    reason
                    for reason in reasons
                    if reason not in {"MISSING_SCRAPE_EVIDENCE", "STALE_SCRAPE_EVIDENCE", "THIN_CHART_POINTS"}
                ]
                if "FULL_CAPTURE_COVERED" not in reasons:
                    reasons.append("FULL_CAPTURE_COVERED")

        chart_point_rows = chart_count_by_pair.get((supplier_sku, asin), 0) if asin != "" else 0
        if identity_status != "RESOLVED_FROM_H_SNAPSHOT":
            reasons.append("BRIDGE_UNRESOLVED")
        if len(reasons) == 0:
            reasons = ["COVERAGE_OK"]

        assumption = assumption_map.get(candidate_id, {})
        rows.append(
            {
                "observed_utc": snapshot_utc,
                "candidate_id": candidate_id,
                "supplier_id": supplier_id,
                "supplier_sku": supplier_sku,
                "sku": sku,
                "asin": asin,
                "scrape_coverage_status": coverage_status,
                "rescrape_needed_flag": "0" if coverage_status in {"ok", "non_scraper_scope"} else "1",
                "rescrape_reason_codes": ";".join(reasons),
                "queue_owner_path": queue_owner_path,
                "scrape_observed_utc": scrape_observed_utc,
                "chart_point_rows": str(chart_point_rows),
                "identity_sku_resolution_status": identity_status,
                "assumption_snapshot_stage": _normalize_text(assumption.get("assumption_snapshot_stage", "")),
                "in_scope_approval_decision_flag": _normalize_text(assumption.get("in_scope_approval_decision_flag", "")),
            }
        )

    out = pd.DataFrame(rows).fillna("")
    for column in out.columns:
        out[column] = out[column].map(_normalize_text)
    out = out.sort_values(["candidate_id"], ascending=[True], kind="stable")
    return out


def _ensure_required_inputs() -> None:
    for path in REQUIRED_INPUTS:
        if not path.exists():
            raise FileNotFoundError(f"required batch-001 input missing: {path}")


def build_baseline(
    *,
    repo_root: Path,
    market_facts_output_path: Path,
    action_outcomes_output_path: Path,
    scrape_gap_output_path: Path,
) -> BaselineBuildResult:
    _ = repo_root
    _ensure_required_inputs()
    snapshot_utc = _utc_now_iso()

    scanner_hash_before = {path: _sha256_file(path) for path in SCANNER_OWNED_INPUTS}

    identity_df = _read_csv_required(IDENTITY_PATH)
    assumption_df = _read_csv_required(ASSUMPTION_PATH)
    outcome_log_df = _read_csv_required(H_OUTCOME_LOG_PATH)
    outcome_daily_df = _read_csv_required(H_OUTCOME_DAILY_PATH)
    listing_snapshot_df = _read_csv_required(LISTING_SNAPSHOT_PATH)
    _ = _read_csv_required(LISTING_SELLER_SNAPSHOT_PATH)
    listing_history_df = _read_csv_required(LISTING_HISTORY_PATH)
    _ = _read_csv_required(LISTING_SELLER_HISTORY_PATH)
    hos_df = _read_csv_required(HOS_MARKET_PATH)
    sku_perf_df = _read_csv_required(SKU_PERF_PATH)
    _ = _read_csv_required(SKU_VELOCITY_PATH)
    _ = _read_csv_required(F_SALES_VALIDATION_PATH)
    _ = _read_csv_required(F_CALIBRATION_PATH)
    legacy_evidence_df = _read_csv_required(F_LEGACY_EVIDENCE_PATH)
    legacy_chart_df = _read_csv_required(F_LEGACY_CHART_PATH)
    full_capture_facts_df = _read_csv_optional(F_FULL_CAPTURE_FACTS_PATH)

    market_facts_df = _build_market_facts(
        listing_history_df=listing_history_df,
        listing_snapshot_df=listing_snapshot_df,
        hos_df=hos_df,
        sku_perf_df=sku_perf_df,
        identity_df=identity_df,
        assumption_df=assumption_df,
    )
    action_outcomes_df = _build_action_outcomes(
        outcome_log_df=outcome_log_df,
        outcome_daily_df=outcome_daily_df,
        market_facts_df=market_facts_df,
    )
    scrape_gap_df = _build_scrape_gap_report(
        identity_df=identity_df,
        assumption_df=assumption_df,
        legacy_evidence_df=legacy_evidence_df,
        legacy_chart_df=legacy_chart_df,
        full_capture_facts_df=full_capture_facts_df,
        snapshot_utc=snapshot_utc,
    )

    market_facts_output_path.parent.mkdir(parents=True, exist_ok=True)
    action_outcomes_output_path.parent.mkdir(parents=True, exist_ok=True)
    scrape_gap_output_path.parent.mkdir(parents=True, exist_ok=True)
    market_facts_df.to_csv(market_facts_output_path, index=False)
    action_outcomes_df.to_csv(action_outcomes_output_path, index=False)
    scrape_gap_df.to_csv(scrape_gap_output_path, index=False)

    scanner_hash_after = {path: _sha256_file(path) for path in SCANNER_OWNED_INPUTS}
    scanner_source_hash_verified = scanner_hash_before == scanner_hash_after

    return BaselineBuildResult(
        market_facts_path=market_facts_output_path,
        market_facts_rows=int(len(market_facts_df.index)),
        action_outcomes_path=action_outcomes_output_path,
        action_outcomes_rows=int(len(action_outcomes_df.index)),
        scrape_gap_path=scrape_gap_output_path,
        scrape_gap_rows=int(len(scrape_gap_df.index)),
        scrape_gap_missing_rows=int((scrape_gap_df["scrape_coverage_status"] == "missing").sum()) if not scrape_gap_df.empty else 0,
        scrape_gap_stale_rows=int((scrape_gap_df["scrape_coverage_status"] == "stale").sum()) if not scrape_gap_df.empty else 0,
        scrape_gap_thin_rows=int((scrape_gap_df["scrape_coverage_status"] == "thin").sum()) if not scrape_gap_df.empty else 0,
        scrape_gap_ok_rows=int((scrape_gap_df["scrape_coverage_status"] == "ok").sum()) if not scrape_gap_df.empty else 0,
        scanner_source_hash_verified=scanner_source_hash_verified,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build HF joined baseline outputs (Batch 001).")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repository root")
    parser.add_argument(
        "--market-facts-output",
        default=str(MARKET_FACTS_OUTPUT_PATH),
        help="Output CSV path for market facts",
    )
    parser.add_argument(
        "--action-outcomes-output",
        default=str(ACTION_OUTCOMES_OUTPUT_PATH),
        help="Output CSV path for action outcomes",
    )
    parser.add_argument(
        "--scrape-gap-output",
        default=str(SCRAPE_GAP_OUTPUT_PATH),
        help="Output CSV path for scrape gap report",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = build_baseline(
        repo_root=Path(args.repo_root),
        market_facts_output_path=Path(args.market_facts_output),
        action_outcomes_output_path=Path(args.action_outcomes_output),
        scrape_gap_output_path=Path(args.scrape_gap_output),
    )
    print(f"market_facts_output_path={result.market_facts_path}")
    print(f"market_facts_rows={result.market_facts_rows}")
    print(f"action_outcomes_output_path={result.action_outcomes_path}")
    print(f"action_outcomes_rows={result.action_outcomes_rows}")
    print(f"scrape_gap_output_path={result.scrape_gap_path}")
    print(f"scrape_gap_rows={result.scrape_gap_rows}")
    print(f"scrape_gap_status_missing_rows={result.scrape_gap_missing_rows}")
    print(f"scrape_gap_status_stale_rows={result.scrape_gap_stale_rows}")
    print(f"scrape_gap_status_thin_rows={result.scrape_gap_thin_rows}")
    print(f"scrape_gap_status_ok_rows={result.scrape_gap_ok_rows}")
    print(f"scanner_source_hash_verified={int(result.scanner_source_hash_verified)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
