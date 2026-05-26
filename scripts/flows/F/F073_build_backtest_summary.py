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
    "feeder_backtest_replay_daily_live",
)


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


def _longest_true_streak(flags: list[bool]) -> int:
    longest = 0
    current = 0
    for flag in flags:
        if flag:
            current += 1
            if current > longest:
                longest = current
        else:
            current = 0
    return longest


def _recovery_rate_from_modes(modes: list[str]) -> float | None:
    if not modes:
        return None
    failure_exits = 0
    recovery_hits = 0
    for idx in range(1, len(modes)):
        prev_mode = modes[idx - 1]
        curr_mode = modes[idx]
        if prev_mode == "sell_off":
            failure_exits += 1
            if curr_mode == "normal_sell":
                recovery_hits += 1
    if failure_exits == 0:
        return 1.0
    return recovery_hits / failure_exits


def _risk_levels(replay_df: pd.DataFrame) -> tuple[str, str]:
    if replay_df.empty:
        return "unknown", "unknown"
    total = float(len(replay_df.index))

    amazon_days = float(
        replay_df["competition_scenario"]
        .map(lambda v: "amazon" in _normalize_text(v))
        .sum()
    )
    amazon_share = amazon_days / total
    if amazon_share >= 0.75:
        amazon_risk = "critical"
    elif amazon_share >= 0.4:
        amazon_risk = "high"
    elif amazon_share >= 0.2:
        amazon_risk = "medium"
    else:
        amazon_risk = "low"

    stretched_days = float(
        replay_df["price_zone"]
        .map(lambda v: _normalize_text(v) in {"stretched", "probable_ceiling_breach"})
        .sum()
    )
    compression_share = stretched_days / total
    if compression_share >= 0.5:
        compression_risk = "high"
    elif compression_share >= 0.25:
        compression_risk = "medium"
    else:
        compression_risk = "low"
    return amazon_risk, compression_risk


def _sellable_ceiling_zone(replay_df: pd.DataFrame) -> str:
    if replay_df.empty:
        return "unknown"
    zones = set(replay_df["price_zone"].map(_normalize_text).tolist())
    if "probable_ceiling_breach" in zones:
        return "probable_ceiling_breach"
    if "stretched" in zones:
        return "stretched"
    return "normal"


def _summary_scores(
    *,
    replay_df: pd.DataFrame,
    total_profit: float,
    monthly_profit: float,
    failure_count: int,
    longest_failure_streak: int,
) -> tuple[float, float]:
    if replay_df.empty:
        return 0.0, 100.0
    total_days = float(len(replay_df.index))
    normal_days = float((replay_df["replay_mode"] == "normal_sell").sum())
    hold_days = float((replay_df["replay_mode"] == "hold_wait").sum())
    selloff_days = float((replay_df["replay_mode"] == "sell_off").sum())

    profit_component = max(0.0, min(100.0, 50.0 + (monthly_profit * 2.0)))
    stability_component = max(0.0, min(100.0, (normal_days / total_days) * 100.0 - (selloff_days / total_days) * 40.0))
    risk_penalty = min(40.0, (failure_count * 5.0) + (longest_failure_streak * 2.0))
    if total_profit <= 0:
        profit_component = max(0.0, profit_component - 35.0)

    viability = max(0.0, min(100.0, (profit_component * 0.6) + (stability_component * 0.4) - risk_penalty))
    exit_risk = max(
        0.0,
        min(
            100.0,
            ((selloff_days / total_days) * 60.0)
            + ((longest_failure_streak / total_days) * 40.0)
            + (10.0 if hold_days > normal_days else 0.0),
        ),
    )
    return viability, exit_risk


def _recommendation(summary_status: str, viability: float, exit_risk: float, history_confidence: str) -> str:
    if summary_status != "ready":
        return "Manual review"
    if history_confidence == "low" and viability >= 70 and exit_risk < 35:
        return "Managed fit"
    if viability >= 70 and exit_risk < 30:
        return "Normal fit"
    if viability >= 55 and exit_risk < 50:
        return "Managed fit"
    if viability >= 40:
        return "Exit-only"
    return "Avoid"


def _apply_critical_amazon_recommendation_cap(
    *,
    summary_status: str,
    amazon_risk_level: str,
    recommendation: str,
) -> str:
    # Governance cap: critical Amazon risk must not present as Normal/Managed fit in ready rows.
    if summary_status != "ready":
        return recommendation
    if _normalize_text(amazon_risk_level).lower() != "critical":
        return recommendation
    if recommendation in {"Normal fit", "Managed fit"}:
        return "Exit-only"
    return recommendation


def _attribution_reason_tags(input_reason_codes: str) -> list[str]:
    if _normalize_text(input_reason_codes) == "":
        return []
    tags: list[str] = []
    seen: set[str] = set()
    for token in _normalize_text(input_reason_codes).split("|"):
        t = _normalize_text(token)
        if t == "":
            continue
        if t.startswith("attribution_") or t == "history_confidence_downgraded_by_attribution":
            if t not in seen:
                seen.add(t)
                tags.append(t)
    return tags


def _share_reason_tags(replay_df: pd.DataFrame) -> list[str]:
    if replay_df.empty or "reason_codes" not in replay_df.columns:
        return []
    allowed = {
        "share_source_global_prior",
        "share_source_sparse_asin_blend",
        "share_sparse_asin_history",
        "share_governance_cap_applied",
    }
    tags: list[str] = []
    seen: set[str] = set()
    for raw_codes in replay_df.get("reason_codes", "").map(_normalize_text).tolist():
        if raw_codes == "":
            continue
        for token in raw_codes.split("|"):
            tag = _normalize_text(token)
            if tag in allowed and tag not in seen:
                seen.add(tag)
                tags.append(tag)
    return tags


def _split_reason_codes(raw_codes: object) -> list[str]:
    raw = _normalize_text(raw_codes)
    if raw == "":
        return []
    return [token for token in raw.split("|") if _normalize_text(token) != ""]


def _default_classifier_state(kind: str) -> tuple[str, str]:
    kind_norm = _normalize_text(kind).lower()
    if kind_norm == "seasonality":
        return "insufficient_history", "classifier_input_missing_defaulted|insufficient_history"
    if kind_norm == "stability":
        return "too_new", "classifier_input_missing_defaulted|insufficient_history"
    return "insufficient_history", "classifier_input_missing_defaulted|insufficient_history"


def _decision_confidence(
    *,
    summary_status: str,
    history_confidence: str,
    history_maturity_state: str,
    completed_months_count: float | None,
    seasonality_state: str,
    stability_state: str,
    recent_vs_baseline_state: str,
    expected_units_source: str,
    expected_profit_source: str,
    qualification_final_factor: float | None,
    qualification_zero_or_block_reason: str,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if summary_status != "ready":
        reasons.append("confidence_summary_not_ready")
        return "low", reasons

    if expected_units_source != "input_qualified" or expected_profit_source != "input_qualified":
        reasons.append("confidence_qualified_source_missing")
        return "low", reasons

    history_confidence_norm = _normalize_text(history_confidence).lower()
    maturity_norm = _normalize_text(history_maturity_state).lower()
    completed_months = int(completed_months_count or 0)
    stability_norm = _normalize_text(stability_state).lower()
    recent_norm = _normalize_text(recent_vs_baseline_state).lower()
    seasonality_norm = _normalize_text(seasonality_state).lower()

    if history_confidence_norm == "low":
        reasons.append("confidence_history_confidence_low")
        return "low", reasons
    if maturity_norm in {"no_history", "recent_only"} or completed_months < 3:
        reasons.append("confidence_maturity_too_new")
        return "low", reasons
    if stability_norm == "too_new":
        reasons.append("confidence_stability_too_new")
        return "low", reasons
    if recent_norm == "insufficient_history":
        reasons.append("confidence_recent_insufficient_history")
        return "low", reasons
    if _normalize_text(qualification_zero_or_block_reason) != "":
        reasons.append(f"confidence_qualification_block_{qualification_zero_or_block_reason}")
        return "low", reasons

    if history_confidence_norm == "high":
        reasons.append("confidence_history_confidence_high")
    elif history_confidence_norm == "medium":
        reasons.append("confidence_history_confidence_medium")
    else:
        reasons.append("confidence_history_confidence_unknown")

    if maturity_norm == "full_year" and completed_months >= 9:
        reasons.append("confidence_maturity_full_year")
    else:
        reasons.append("confidence_maturity_partial")

    if qualification_final_factor is not None and qualification_final_factor < 0.5:
        reasons.append("confidence_qualification_factor_reduced")
    if stability_norm == "spiky":
        reasons.append("confidence_stability_spiky")
    if seasonality_norm == "spiky_not_proven_seasonal":
        reasons.append("confidence_seasonality_unproven_spike")

    high_gate = (
        history_confidence_norm == "high"
        and maturity_norm == "full_year"
        and completed_months >= 9
        and stability_norm in {"stable", "drifting_up", "drifting_down"}
        and recent_norm in {"stable", "overperforming", "underperforming"}
        and seasonality_norm not in {"insufficient_history", "spiky_not_proven_seasonal"}
        and (qualification_final_factor is None or qualification_final_factor >= 0.5)
    )
    if high_gate:
        reasons.append("confidence_high_gate_met")
        return "high", reasons

    reasons.append("confidence_medium_gate_met")
    return "medium", reasons


def _decision_state(
    *,
    summary_status: str,
    expected_profit_next_30d_gbp: float | None,
    minimum_expected_profit_gbp: float,
    decision_confidence: str,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if summary_status != "ready":
        reasons.append("summary_not_ready")
        return "manual_review", reasons

    if expected_profit_next_30d_gbp is None:
        reasons.append("expected_profit_missing")
        return "manual_review", reasons

    if expected_profit_next_30d_gbp < minimum_expected_profit_gbp:
        reasons.append("expected_profit_below_floor")
        return "fail", reasons

    if _normalize_text(decision_confidence).lower() == "low":
        reasons.append("decision_confidence_low")
        return "manual_review", reasons

    reasons.append("meets_profit_floor")
    return "pass", reasons


def build_backtest_summary(
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
    minimum_expected_profit_gbp = _num_or_none(policy_row.get("minimum_expected_profit_gbp", "")) or 20.0

    input_df = source_data["feeder_backtest_input_view_live"].df.copy()
    replay_df = source_data["feeder_backtest_replay_daily_live"].df.copy()

    if input_df.empty:
        out_df = _write_contract_df(pd.DataFrame(), "feeder_backtest_summary_live", root_path)
        print({"status": "success", "rows": 0, "ready_inputs": 0, "notes": "input view empty"})
        return out_df

    input_df["seller_sku_norm"] = input_df.get("seller_sku", "").map(_normalize_key)
    input_df["asin_norm"] = input_df.get("asin", "").map(_normalize_key)

    if replay_df.empty:
        replay_df = pd.DataFrame(
            columns=[
                "policy_id",
                "seller_sku",
                "asin",
                "day",
                "replay_mode",
                "estimated_profit_gbp",
                "failure_event_flag",
                "competition_scenario",
                "price_zone",
            ]
        )
    replay_df["seller_sku_norm"] = replay_df.get("seller_sku", "").map(_normalize_key)
    replay_df["asin_norm"] = replay_df.get("asin", "").map(_normalize_key)
    replay_df["day_dt"] = pd.to_datetime(replay_df.get("day", ""), errors="coerce")
    replay_df = replay_df.sort_values("day_dt", ascending=True, kind="stable").reset_index(drop=True)

    rows: list[dict[str, str]] = []
    for _, input_row in input_df.iterrows():
        seller_sku = _normalize_text(input_row.get("seller_sku", ""))
        asin = _normalize_text(input_row.get("asin_norm", ""))
        history_confidence = _normalize_text(input_row.get("history_confidence", ""))
        input_status = _normalize_text(input_row.get("input_status", "")).lower()
        input_reasons = _normalize_text(input_row.get("input_reason_codes", ""))
        seasonality_state = _normalize_text(input_row.get("seasonality_state", ""))
        seasonality_reason_codes = _normalize_text(input_row.get("seasonality_reason_codes", ""))
        stability_state = _normalize_text(input_row.get("stability_state", ""))
        stability_reason_codes = _normalize_text(input_row.get("stability_reason_codes", ""))
        recent_vs_baseline_state = _normalize_text(input_row.get("recent_vs_baseline_state", ""))
        recent_vs_baseline_reason_codes = _normalize_text(input_row.get("recent_vs_baseline_reason_codes", ""))
        completed_months_count = _num_or_none(input_row.get("completed_months_count", ""))
        history_maturity_state = _normalize_text(input_row.get("history_maturity_state", ""))
        raw_monthly_units = _num_or_none(input_row.get("demand_basis_units_monthly", ""))
        qualified_monthly_units = _num_or_none(input_row.get("price_qualified_units_monthly", ""))
        qualified_monthly_profit = _num_or_none(input_row.get("price_qualified_profit_monthly_gbp", ""))
        price_qualification_reason_codes = _normalize_text(input_row.get("price_qualification_reason_codes", ""))
        qualification_final_factor = _num_or_none(input_row.get("qualification_final_factor", ""))
        qualification_zero_or_block_reason = _normalize_text(input_row.get("qualification_zero_or_block_reason", ""))

        classifier_fallback_tokens: list[str] = []
        if seasonality_state == "":
            seasonality_state, seasonality_reason_codes = _default_classifier_state("seasonality")
            classifier_fallback_tokens.append("seasonality_state_defaulted")
        if seasonality_reason_codes == "":
            _, seasonality_reason_codes = _default_classifier_state("seasonality")
            classifier_fallback_tokens.append("seasonality_reason_defaulted")
        if stability_state == "":
            stability_state, stability_reason_codes = _default_classifier_state("stability")
            classifier_fallback_tokens.append("stability_state_defaulted")
        if stability_reason_codes == "":
            _, stability_reason_codes = _default_classifier_state("stability")
            classifier_fallback_tokens.append("stability_reason_defaulted")
        if recent_vs_baseline_state == "":
            recent_vs_baseline_state, recent_vs_baseline_reason_codes = _default_classifier_state("recent")
            classifier_fallback_tokens.append("recent_state_defaulted")
        if recent_vs_baseline_reason_codes == "":
            _, recent_vs_baseline_reason_codes = _default_classifier_state("recent")
            classifier_fallback_tokens.append("recent_reason_defaulted")

        replay_slice = replay_df[
            (replay_df["seller_sku_norm"] == _normalize_key(seller_sku))
            & (replay_df["asin_norm"] == asin)
            & (replay_df.get("policy_id", "").map(_normalize_text) == policy_id)
        ].copy()

        summary_status = "ready"
        summary_reasons: list[str] = []
        manual_review_reason = ""

        if input_status != "ready":
            summary_status = "manual_review"
            summary_reasons.append("input_not_ready")
            if input_reasons:
                summary_reasons.append(input_reasons)
            manual_review_reason = input_reasons or "input_not_ready"
        elif replay_slice.empty:
            summary_status = "manual_review"
            summary_reasons.append("missing_replay_rows")
            manual_review_reason = "missing_replay_rows"

        total_days = int(len(replay_slice.index))
        profits = replay_slice.get("estimated_profit_gbp", "").map(_num_or_none) if not replay_slice.empty else pd.Series(dtype=float)
        units_ours = replay_slice.get("estimated_units_ours", "").map(_num_or_none) if not replay_slice.empty else pd.Series(dtype=float)
        total_profit = float(sum(v for v in profits if v is not None)) if not profits.empty else 0.0
        monthly_profit = (total_profit * 30.0 / total_days) if total_days > 0 else 0.0
        replay_monthly_units = (
            float(sum(v for v in units_ours if v is not None)) * 30.0 / total_days if total_days > 0 else 0.0
        )
        failure_flags = replay_slice.get("failure_event_flag", "").map(lambda v: _normalize_text(v) == "1").tolist()
        failure_count = int(sum(1 for flag in failure_flags if flag))
        longest_failure_streak = _longest_true_streak(failure_flags)
        modes = replay_slice.get("replay_mode", "").map(_normalize_text).tolist()
        normal_days = int(sum(1 for m in modes if m == "normal_sell"))
        hold_days = int(sum(1 for m in modes if m == "hold_wait"))
        selloff_days = int(sum(1 for m in modes if m == "sell_off"))
        capital_lockup_days = hold_days + selloff_days

        viability_score, exit_risk_score = _summary_scores(
            replay_df=replay_slice,
            total_profit=total_profit,
            monthly_profit=monthly_profit,
            failure_count=failure_count,
            longest_failure_streak=longest_failure_streak,
        )

        amazon_risk_level, compression_risk_level = _risk_levels(replay_slice)
        recommendation = _recommendation(summary_status, viability_score, exit_risk_score, history_confidence)
        recommendation = _apply_critical_amazon_recommendation_cap(
            summary_status=summary_status,
            amazon_risk_level=amazon_risk_level,
            recommendation=recommendation,
        )
        share_assumption_basis = "v1_measured_share_with_prior_and_scenario_caps"

        expected_units_source = "input_qualified" if qualified_monthly_units is not None else "replay_fallback"
        expected_profit_source = "input_qualified" if qualified_monthly_profit is not None else "replay_fallback"
        expected_units_next_30d = qualified_monthly_units if expected_units_source == "input_qualified" else replay_monthly_units
        expected_profit_next_30d_gbp = qualified_monthly_profit if expected_profit_source == "input_qualified" else monthly_profit

        if summary_status == "ready" and (
            expected_units_source != "input_qualified" or expected_profit_source != "input_qualified"
        ):
            summary_status = "manual_review"
            summary_reasons.append("missing_qualified_input_for_ready_row")
            manual_review_reason = "missing_qualified_input_for_ready_row"

        summary_reasons.append(f"expected_units_source_{expected_units_source}")
        summary_reasons.append(f"expected_profit_source_{expected_profit_source}")
        summary_reasons.append(f"seasonality_state_{seasonality_state}")
        summary_reasons.append(f"stability_state_{stability_state}")
        summary_reasons.append(f"recent_vs_baseline_state_{recent_vs_baseline_state}")
        summary_reasons.extend(classifier_fallback_tokens)
        summary_reasons.extend(_split_reason_codes(seasonality_reason_codes))
        summary_reasons.extend(_split_reason_codes(stability_reason_codes))
        summary_reasons.extend(_split_reason_codes(recent_vs_baseline_reason_codes))
        if qualification_zero_or_block_reason != "":
            summary_reasons.append(f"qualification_zero_or_block_{qualification_zero_or_block_reason}")
        if qualification_final_factor is not None and qualification_final_factor < 0.999:
            summary_reasons.append("qualification_factor_reduced")
        if price_qualification_reason_codes != "":
            summary_reasons.append("qualification_reason_codes_present")

        if summary_status == "ready":
            summary_reasons.append("summary_ready")
            summary_reasons.extend(_attribution_reason_tags(input_reasons))
            summary_reasons.extend(_share_reason_tags(replay_slice))
        decision_confidence, decision_confidence_reason_codes = _decision_confidence(
            summary_status=summary_status,
            history_confidence=history_confidence,
            history_maturity_state=history_maturity_state,
            completed_months_count=completed_months_count,
            seasonality_state=seasonality_state,
            stability_state=stability_state,
            recent_vs_baseline_state=recent_vs_baseline_state,
            expected_units_source=expected_units_source,
            expected_profit_source=expected_profit_source,
            qualification_final_factor=qualification_final_factor,
            qualification_zero_or_block_reason=qualification_zero_or_block_reason,
        )
        summary_reasons.append(f"decision_confidence_{decision_confidence}")
        summary_reasons.extend(decision_confidence_reason_codes)
        decision_state, decision_reason_codes = _decision_state(
            summary_status=summary_status,
            expected_profit_next_30d_gbp=expected_profit_next_30d_gbp,
            minimum_expected_profit_gbp=minimum_expected_profit_gbp,
            decision_confidence=decision_confidence,
        )
        if qualified_monthly_profit is not None:
            decision_reason_codes.append("expected_profit_source_input_qualified")
        else:
            decision_reason_codes.append("expected_profit_source_replay")
        if qualified_monthly_units is not None:
            decision_reason_codes.append("expected_units_source_input_qualified")
        else:
            decision_reason_codes.append("expected_units_source_replay")
        if qualification_zero_or_block_reason != "":
            decision_reason_codes.append(f"qualification_zero_or_block_{qualification_zero_or_block_reason}")
        if qualification_final_factor is not None and qualification_final_factor < 0.999:
            decision_reason_codes.append("qualification_factor_reduced")
        decision_reason_codes.append(f"seasonality_state_{seasonality_state}")
        decision_reason_codes.append(f"stability_state_{stability_state}")
        decision_reason_codes.append(f"recent_vs_baseline_state_{recent_vs_baseline_state}")
        decision_reason_codes.append(f"decision_confidence_{decision_confidence}")
        decision_reason_codes.extend(decision_confidence_reason_codes)
        decision_reason_codes.extend(classifier_fallback_tokens)
        decision_reason_codes = [code for code in dict.fromkeys(decision_reason_codes) if _normalize_text(code) != ""]
        summary_reasons = [code for code in dict.fromkeys(summary_reasons) if _normalize_text(code) != ""]

        recovery_rate = _recovery_rate_from_modes(modes)
        seasonality_flag = ""
        if seasonality_state in {"insufficient_history", "possible_seasonal", "spiky_not_proven_seasonal", "limited_history", "sparse_history"}:
            seasonality_flag = "seasonality_data_limited"

        row = {
            "observed_utc": snapshot_utc,
            "policy_id": policy_id,
            "seller_sku": seller_sku,
            "asin": asin,
            "summary_status": summary_status,
            "summary_reason_codes": "|".join(summary_reasons),
            "history_confidence": history_confidence,
            "history_maturity_state": history_maturity_state,
            "seasonality_state": seasonality_state,
            "seasonality_reason_codes": seasonality_reason_codes,
            "stability_state": stability_state,
            "stability_reason_codes": stability_reason_codes,
            "recent_vs_baseline_state": recent_vs_baseline_state,
            "recent_vs_baseline_reason_codes": recent_vs_baseline_reason_codes,
            "completed_months_count": _num_to_text(completed_months_count),
            "market_viability_score": _num_to_text(viability_score),
            "exit_risk_score": _num_to_text(exit_risk_score),
            "estimated_total_profit_gbp": _num_to_text(total_profit),
            "estimated_monthly_profit_gbp": _num_to_text(monthly_profit),
            "raw_monthly_units": _num_to_text(raw_monthly_units),
            "qualified_monthly_units": _num_to_text(qualified_monthly_units),
            "qualified_monthly_profit_gbp": _num_to_text(qualified_monthly_profit),
            "price_qualification_reason_codes": price_qualification_reason_codes,
            "qualification_final_factor": _num_to_text(qualification_final_factor),
            "qualification_zero_or_block_reason": qualification_zero_or_block_reason,
            "expected_units_next_30d": _num_to_text(expected_units_next_30d),
            "expected_units_source": expected_units_source,
            "expected_profit_next_30d_gbp": _num_to_text(expected_profit_next_30d_gbp),
            "expected_profit_source": expected_profit_source,
            "minimum_expected_profit_gbp": _num_to_text(minimum_expected_profit_gbp),
            "decision_state": decision_state,
            "decision_reason_codes": "|".join(decision_reason_codes),
            "decision_confidence": decision_confidence,
            "decision_confidence_reason_codes": "|".join(
                [code for code in dict.fromkeys(decision_confidence_reason_codes) if _normalize_text(code) != ""]
            ),
            "capital_lockup_days": str(capital_lockup_days),
            "sellable_ceiling_zone": _sellable_ceiling_zone(replay_slice),
            "amazon_risk_level": amazon_risk_level,
            "compression_risk_level": compression_risk_level,
            "recommendation": recommendation,
            "manual_review_reason": manual_review_reason,
            "failure_event_count": str(failure_count),
            "longest_failure_streak_days": str(longest_failure_streak),
            "time_normal_sell_days": str(normal_days),
            "time_hold_wait_days": str(hold_days),
            "time_selloff_days": str(selloff_days),
            "share_assumption_basis": share_assumption_basis,
            "recovery_rate": _num_to_text(recovery_rate),
            "seasonality_flag": seasonality_flag,
            "notes": "",
        }
        rows.append(row)

    out_df = _write_contract_df(pd.DataFrame(rows), "feeder_backtest_summary_live", root_path)
    ready_rows = int((out_df["summary_status"] == "ready").sum()) if not out_df.empty else 0
    manual_rows = int((out_df["summary_status"] == "manual_review").sum()) if not out_df.empty else 0
    print(
        {
            "status": "success",
            "rows": int(len(out_df)),
            "ready_rows": ready_rows,
            "manual_review_rows": manual_rows,
            "policy_id": policy_id,
            "snapshot": str(root_path / get_f_output_contract("feeder_backtest_summary_live").rel_path),
        }
    )
    return out_df


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build F backtest summary output from replay daily rows.")
    parser.add_argument("--observed-utc", default=None, help="Override observed_utc for deterministic runs.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_backtest_summary(observed_utc=args.observed_utc)


if __name__ == "__main__":
    main()
