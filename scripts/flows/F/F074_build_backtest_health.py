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


@dataclass(frozen=True)
class ReadResult:
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


def _has_severe_attribution_tag(reason_codes: str) -> bool:
    severe_tags = {
        "attribution_confidence_low",
        "attribution_identity_ambiguous",
        "attribution_identity_missing",
        "attribution_buy_box_coverage_low",
        "attribution_channel_pairing_sparse",
        "attribution_amazon_dominant_90d",
    }
    tags = {_normalize_text(token) for token in _normalize_text(reason_codes).split("|") if _normalize_text(token) != ""}
    return any(tag in severe_tags for tag in tags)


def _has_reason_tag(reason_codes: str, tag: str) -> bool:
    tag_norm = _normalize_text(tag)
    if tag_norm == "":
        return False
    tags = {_normalize_text(token) for token in _normalize_text(reason_codes).split("|") if _normalize_text(token) != ""}
    return tag_norm in tags


SEASONALITY_STATES: set[str] = {
    "seasonal_confirmed",
    "possible_seasonal",
    "spiky_not_proven_seasonal",
    "insufficient_history",
    "full_year_history",
    "partial_year_history",
    "limited_history",
    "sparse_history",
}

STABILITY_STATES: set[str] = {
    "stable",
    "drifting_down",
    "drifting_up",
    "spiky",
    "too_new",
}

RECENT_STATES: set[str] = {
    "underperforming",
    "stable",
    "overperforming",
    "insufficient_history",
}


def _num_or_none(value: object) -> float | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    cleaned = raw.replace(",", "").replace("GBP", "").replace("gbp", "").replace("PS", "").replace("ps", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


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


def _read_from_source_contract(root_path: Path, source_name: str) -> ReadResult:
    contract = get_source_contract(source_name)
    source_path = root_path / contract.source_path
    required_columns = tuple(contract.required_columns)
    if not source_path.exists():
        return ReadResult(
            path=source_path,
            df=pd.DataFrame(),
            file_missing=True,
            missing_columns=required_columns,
        )
    df = pd.read_csv(source_path, dtype=str).fillna("")
    missing_columns = tuple(col for col in required_columns if col not in df.columns)
    return ReadResult(
        path=source_path,
        df=df,
        file_missing=False,
        missing_columns=missing_columns,
    )


def _read_from_output_contract(root_path: Path, contract_name: str) -> ReadResult:
    contract = get_f_output_contract(contract_name)
    source_path = root_path / contract.rel_path
    required_columns = tuple(contract.required_columns)
    if not source_path.exists():
        return ReadResult(
            path=source_path,
            df=pd.DataFrame(),
            file_missing=True,
            missing_columns=required_columns,
        )
    df = pd.read_csv(source_path, dtype=str).fillna("")
    missing_columns = tuple(col for col in required_columns if col not in df.columns)
    return ReadResult(
        path=source_path,
        df=df,
        file_missing=False,
        missing_columns=missing_columns,
    )


def _schema_ok(result: ReadResult) -> bool:
    return (not result.file_missing) and (len(result.missing_columns) == 0)


def _summary_share(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _safe_mtime(path: Path) -> float | None:
    try:
        if path.exists():
            return float(path.stat().st_mtime)
    except OSError:
        return None
    return None


def _is_demand_basis_fallback(source: str) -> bool:
    source_norm = _normalize_text(source)
    return source_norm in {
        "bbp_recent_history_fallback",
        "bbp_current_month_fallback",
        "amazon_monthly_sold_fallback",
        "bbp_units_chosen_fallback",
        "e_velocity_30d_fallback",
        "bbp_replay_basis_units_field",
        "legacy_base_velocity",
        "missing",
    }


def _check_row_counts_by_key(df: pd.DataFrame, key_cols: list[str]) -> pd.Series:
    if df.empty:
        return pd.Series(dtype="int64")
    keys = df.copy()
    for col in key_cols:
        keys[col] = keys.get(col, "").map(_normalize_key)
    keys = keys[key_cols]
    return keys.value_counts(sort=False)


def build_backtest_health(
    root: Path | None = None,
    *,
    observed_utc: str | None = None,
) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)
    snapshot_utc = observed_utc or _utc_now_iso()

    policy_result = _read_from_source_contract(root_path, "feeder_backtest_policy_live")
    input_result = _read_from_source_contract(root_path, "feeder_backtest_input_view_live")
    replay_result = _read_from_source_contract(root_path, "feeder_backtest_replay_daily_live")
    summary_result = _read_from_output_contract(root_path, "feeder_backtest_summary_live")

    input_schema_ok = _schema_ok(input_result)
    replay_schema_ok = _schema_ok(replay_result)
    summary_schema_ok = _schema_ok(summary_result)
    policy_schema_ok = _schema_ok(policy_result)

    ready_input_rows = 0
    if input_schema_ok:
        ready_input_rows = int(
            input_result.df.get("input_status", "")
            .map(lambda v: _normalize_text(v).lower() == "ready")
            .sum()
        )

    checks: list[dict[str, str]] = []
    prior_health_path = root_path / get_f_output_contract("feeder_backtest_health").rel_path
    prior_health_mtime = _safe_mtime(prior_health_path)

    active_policy_rows = 0
    if policy_schema_ok:
        active_policy_rows = int(
            policy_result.df.get("policy_status", "")
            .map(lambda v: _normalize_text(v).lower() == "active")
            .sum()
        )
    if (not policy_schema_ok) or active_policy_rows != 1:
        policy_status = "fail"
        if policy_result.file_missing:
            policy_notes = "policy_file_missing"
        elif policy_result.missing_columns:
            policy_notes = f"missing_columns:{'|'.join(policy_result.missing_columns)}"
        else:
            policy_notes = f"active_policy_rows={active_policy_rows}"
    else:
        policy_status = "ok"
        policy_notes = "exactly_one_active_policy_row"
    checks.append(
        {
            "check": "f_backtest_policy_single_active_row",
            "status": policy_status,
            "value": str(active_policy_rows),
            "notes": policy_notes,
            "observed_utc": snapshot_utc,
            "source_path": str(policy_result.path),
        }
    )

    stale_sources: list[str] = []
    if prior_health_mtime is None:
        staleness_status = "ok"
        staleness_notes = "no_prior_health_snapshot"
    else:
        freshness_candidates = {
            "input_view": _safe_mtime(input_result.path),
            "replay_daily": _safe_mtime(replay_result.path),
            "summary": _safe_mtime(summary_result.path),
        }
        for label, mtime in freshness_candidates.items():
            if mtime is not None and mtime > prior_health_mtime:
                stale_sources.append(label)
        if stale_sources:
            staleness_status = "warn"
            staleness_notes = f"stale_sources:{'|'.join(stale_sources)}"
        else:
            staleness_status = "ok"
            staleness_notes = "prior_health_fresh_vs_current_sources"
    checks.append(
        {
            "check": "f_backtest_health_staleness",
            "status": staleness_status,
            "value": str(len(stale_sources)),
            "notes": staleness_notes,
            "observed_utc": snapshot_utc,
            "source_path": f"{input_result.path}|{replay_result.path}|{summary_result.path}",
        }
    )

    if input_schema_ok:
        input_status = "ok"
        input_notes = f"rows={len(input_result.df)};ready_rows={ready_input_rows}"
    else:
        input_status = "fail"
        if input_result.file_missing:
            input_notes = "input_view_file_missing"
        else:
            input_notes = f"missing_columns:{'|'.join(input_result.missing_columns)}"
    checks.append(
        {
            "check": "f_backtest_input_view_schema",
            "status": input_status,
            "value": str(len(input_result.missing_columns)),
            "notes": input_notes,
            "observed_utc": snapshot_utc,
            "source_path": str(input_result.path),
        }
    )

    if ready_input_rows <= 0 and replay_result.file_missing:
        replay_status = "ok"
        replay_notes = "not_required_no_ready_input_rows"
    elif replay_schema_ok:
        replay_status = "ok"
        replay_notes = f"rows={len(replay_result.df)}"
    else:
        replay_status = "fail"
        if replay_result.file_missing:
            replay_notes = "replay_daily_file_missing_with_ready_rows"
        else:
            replay_notes = f"missing_columns:{'|'.join(replay_result.missing_columns)}"
    checks.append(
        {
            "check": "f_backtest_replay_daily_schema",
            "status": replay_status,
            "value": str(len(replay_result.missing_columns)),
            "notes": replay_notes,
            "observed_utc": snapshot_utc,
            "source_path": str(replay_result.path),
        }
    )

    if ready_input_rows <= 0 and summary_result.file_missing:
        summary_schema_status = "ok"
        summary_schema_notes = "not_required_no_ready_input_rows"
    elif summary_schema_ok:
        summary_schema_status = "ok"
        summary_schema_notes = f"rows={len(summary_result.df)}"
    else:
        summary_schema_status = "fail"
        if summary_result.file_missing:
            summary_schema_notes = "summary_file_missing_with_ready_rows"
        else:
            summary_schema_notes = f"missing_columns:{'|'.join(summary_result.missing_columns)}"
    checks.append(
        {
            "check": "f_backtest_summary_schema",
            "status": summary_schema_status,
            "value": str(len(summary_result.missing_columns)),
            "notes": summary_schema_notes,
            "observed_utc": snapshot_utc,
            "source_path": str(summary_result.path),
        }
    )

    row_coverage_fail_count = 0
    if ready_input_rows <= 0:
        row_coverage_status = "ok"
        row_coverage_notes = "no_ready_input_rows"
    elif (not input_schema_ok) or (not summary_schema_ok):
        row_coverage_status = "fail"
        row_coverage_notes = "coverage_blocked_by_schema_failure"
    else:
        key_cols = ["seller_sku", "asin", "policy_id"]
        ready_df = input_result.df[
            input_result.df.get("input_status", "").map(lambda v: _normalize_text(v).lower() == "ready")
        ].copy()
        ready_key_counts = _check_row_counts_by_key(ready_df, key_cols)
        summary_key_counts = _check_row_counts_by_key(summary_result.df.copy(), key_cols)
        for key, _ in ready_key_counts.items():
            if int(summary_key_counts.get(key, 0)) != 1:
                row_coverage_fail_count += 1
        row_coverage_status = "ok" if row_coverage_fail_count == 0 else "fail"
        row_coverage_notes = (
            f"ready_keys={len(ready_key_counts)};missing_or_non_unique_summary_keys={row_coverage_fail_count}"
        )
    checks.append(
        {
            "check": "f_backtest_summary_row_coverage",
            "status": row_coverage_status,
            "value": str(row_coverage_fail_count),
            "notes": row_coverage_notes,
            "observed_utc": snapshot_utc,
            "source_path": f"{input_result.path}|{summary_result.path}",
        }
    )

    replay_coverage_fail_count = 0
    if ready_input_rows <= 0 and summary_result.file_missing:
        replay_coverage_status = "ok"
        replay_coverage_notes = "not_required_no_ready_input_rows"
    elif not summary_schema_ok:
        replay_coverage_status = "fail"
        replay_coverage_notes = "summary_schema_failed"
    elif not replay_schema_ok:
        replay_coverage_status = "fail"
        replay_coverage_notes = "replay_schema_failed"
    elif summary_result.df.empty:
        replay_coverage_status = "ok"
        replay_coverage_notes = "no_summary_rows"
    else:
        key_cols = ["seller_sku", "asin", "policy_id"]
        summary_ready_df = summary_result.df[
            summary_result.df.get("summary_status", "").map(lambda v: _normalize_text(v).lower() == "ready")
        ].copy()
        if summary_ready_df.empty:
            replay_coverage_status = "ok"
            replay_coverage_notes = "no_ready_summary_rows"
        else:
            summary_key_counts = _check_row_counts_by_key(summary_ready_df, key_cols)
            replay_key_counts = _check_row_counts_by_key(replay_result.df.copy(), key_cols)
            for key, _ in summary_key_counts.items():
                if int(replay_key_counts.get(key, 0)) <= 0:
                    replay_coverage_fail_count += 1
            replay_coverage_status = "ok" if replay_coverage_fail_count == 0 else "fail"
            replay_coverage_notes = (
                f"ready_summary_keys={len(summary_key_counts)};"
                f"ready_summary_keys_without_replay={replay_coverage_fail_count}"
            )
    checks.append(
        {
            "check": "f_backtest_replay_row_coverage",
            "status": replay_coverage_status,
            "value": str(replay_coverage_fail_count),
            "notes": replay_coverage_notes,
            "observed_utc": snapshot_utc,
            "source_path": f"{summary_result.path}|{replay_result.path}",
        }
    )

    low_confidence_rows = 0
    summary_rows = 0
    if summary_schema_ok:
        summary_rows = int(len(summary_result.df))
        low_confidence_rows = int(
            summary_result.df.get("history_confidence", "")
            .map(lambda v: _normalize_text(v).lower() == "low")
            .sum()
        )
    low_confidence_share = _summary_share(low_confidence_rows, summary_rows)
    if summary_rows <= 0:
        low_confidence_status = "ok"
        low_confidence_notes = "no_summary_rows"
    elif low_confidence_share > 0.5:
        low_confidence_status = "warn"
        low_confidence_notes = f"low_confidence_share={low_confidence_share:.4f}"
    else:
        low_confidence_status = "ok"
        low_confidence_notes = f"low_confidence_share={low_confidence_share:.4f}"
    checks.append(
        {
            "check": "f_backtest_low_confidence_share",
            "status": low_confidence_status,
            "value": f"{low_confidence_share:.6f}",
            "notes": low_confidence_notes,
            "observed_utc": snapshot_utc,
            "source_path": str(summary_result.path),
        }
    )

    manual_review_rows = 0
    if summary_schema_ok:
        manual_review_rows = int(
            summary_result.df.get("recommendation", "")
            .map(lambda v: _normalize_text(v).lower() == "manual review")
            .sum()
        )
    manual_review_share = _summary_share(manual_review_rows, summary_rows)
    if summary_rows <= 0:
        manual_review_status = "ok"
        manual_review_notes = "no_summary_rows"
    elif manual_review_share > 0.4:
        manual_review_status = "warn"
        manual_review_notes = f"manual_review_share={manual_review_share:.4f}"
    else:
        manual_review_status = "ok"
        manual_review_notes = f"manual_review_share={manual_review_share:.4f}"
    checks.append(
        {
            "check": "f_backtest_manual_review_share",
            "status": manual_review_status,
            "value": f"{manual_review_share:.6f}",
            "notes": manual_review_notes,
            "observed_utc": snapshot_utc,
            "source_path": str(summary_result.path),
        }
    )

    attribution_warn_rows = 0
    ready_rows = 0
    if not input_schema_ok:
        attribution_status = "fail"
        attribution_notes = "input_view_schema_failed"
    else:
        input_df = input_result.df.copy()
        ready_mask = input_df.get("input_status", "").map(lambda v: _normalize_text(v).lower() == "ready")
        ready_rows = int(ready_mask.sum())
        if ready_rows <= 0:
            attribution_status = "ok"
            attribution_notes = "no_ready_input_rows"
        else:
            attribution_warn_rows = int(
                input_df.get("input_reason_codes", "")
                .map(_has_severe_attribution_tag)
                .fillna(False)
                .astype(int)
                .where(ready_mask, 0)
                .sum()
            )
            attribution_share = _summary_share(attribution_warn_rows, ready_rows)
            if attribution_share > 0.2:
                attribution_status = "warn"
                attribution_notes = f"ready_rows={ready_rows};attribution_warn_rows={attribution_warn_rows}"
            else:
                attribution_status = "ok"
                attribution_notes = f"ready_rows={ready_rows};attribution_warn_rows={attribution_warn_rows}"

    checks.append(
        {
            "check": "f_backtest_attribution_confidence_share",
            "status": attribution_status,
            "value": str(attribution_warn_rows),
            "notes": attribution_notes,
            "observed_utc": snapshot_utc,
            "source_path": str(input_result.path),
        }
    )

    replay_rows = int(len(replay_result.df)) if replay_schema_ok else 0
    prior_dependency_rows = 0
    sparse_blend_rows = 0
    if not replay_schema_ok:
        prior_dependency_status = "fail"
        prior_dependency_notes = "replay_schema_failed"
    elif replay_rows <= 0:
        prior_dependency_status = "ok"
        prior_dependency_notes = "no_replay_rows"
    else:
        reason_codes = (
            replay_result.df["reason_codes"]
            if "reason_codes" in replay_result.df.columns
            else pd.Series("", index=replay_result.df.index, dtype="string")
        ).map(_normalize_text)
        prior_dependency_rows = int(
            reason_codes.map(
                lambda codes: _has_reason_tag(codes, "share_source_global_prior")
                or _has_reason_tag(codes, "share_source_sparse_asin_blend")
            ).sum()
        )
        sparse_blend_rows = int(reason_codes.map(lambda codes: _has_reason_tag(codes, "share_source_sparse_asin_blend")).sum())
        prior_dependency_share = _summary_share(prior_dependency_rows, replay_rows)
        if prior_dependency_share > 0.4:
            prior_dependency_status = "warn"
            prior_dependency_notes = (
                f"prior_dependency_rows={prior_dependency_rows};replay_rows={replay_rows};"
                f"sparse_blend_rows={sparse_blend_rows}"
            )
        else:
            prior_dependency_status = "ok"
            prior_dependency_notes = (
                f"prior_dependency_rows={prior_dependency_rows};replay_rows={replay_rows};"
                f"sparse_blend_rows={sparse_blend_rows}"
            )
    checks.append(
        {
            "check": "f_backtest_share_prior_dependency",
            "status": prior_dependency_status,
            "value": str(prior_dependency_rows),
            "notes": prior_dependency_notes,
            "observed_utc": snapshot_utc,
            "source_path": str(replay_result.path),
        }
    )

    demand_basis_fail_rows = 0
    demand_basis_warn_rows = 0
    demand_basis_non_completed_rows = 0
    demand_basis_units_mismatch_rows = 0
    demand_basis_helper_leak_rows = 0
    demand_basis_future_source_rows = 0
    if not input_schema_ok:
        demand_basis_status = "fail"
        demand_basis_notes = "input_view_schema_failed"
    else:
        input_df = input_result.df.copy()
        required_cols = (
            "demand_basis_source",
            "demand_basis_units_monthly",
            "bbp_sales_last_completed_month_units",
            "bbp_sales_future_month_count_ignored",
        )
        missing_cols = [col for col in required_cols if col not in input_df.columns]
        if missing_cols:
            demand_basis_status = "fail"
            demand_basis_notes = f"missing_columns:{'|'.join(missing_cols)}"
        else:
            ready_df = input_df[input_df.get("input_status", "").map(lambda v: _normalize_text(v).lower() == "ready")].copy()
            if ready_df.empty:
                demand_basis_status = "ok"
                demand_basis_notes = "no_ready_input_rows"
            else:
                for _, row in ready_df.iterrows():
                    source = _normalize_text(row.get("demand_basis_source", ""))
                    monthly_units = _num_or_none(row.get("demand_basis_units_monthly", ""))
                    last_completed_units = _num_or_none(row.get("bbp_sales_last_completed_month_units", "")) or 0.0

                    if source == "":
                        demand_basis_warn_rows += 1
                        source = "missing"

                    if "future" in source:
                        demand_basis_future_source_rows += 1
                        demand_basis_fail_rows += 1

                    if last_completed_units > 0:
                        if source != "bbp_last_completed_month":
                            demand_basis_non_completed_rows += 1
                            demand_basis_fail_rows += 1
                        if monthly_units is None or abs(monthly_units - last_completed_units) > 0.5:
                            demand_basis_units_mismatch_rows += 1
                            demand_basis_fail_rows += 1
                        if source == "bbp_units_chosen_fallback":
                            demand_basis_helper_leak_rows += 1
                            demand_basis_fail_rows += 1
                    else:
                        if _is_demand_basis_fallback(source):
                            demand_basis_warn_rows += 1

                if demand_basis_fail_rows > 0:
                    demand_basis_status = "fail"
                elif demand_basis_warn_rows > 0:
                    demand_basis_status = "warn"
                else:
                    demand_basis_status = "ok"

                demand_basis_notes = (
                    f"ready_rows={len(ready_df)};"
                    f"fallback_warn_rows={demand_basis_warn_rows};"
                    f"fail_rows={demand_basis_fail_rows};"
                    f"non_completed_rows={demand_basis_non_completed_rows};"
                    f"units_mismatch_rows={demand_basis_units_mismatch_rows};"
                    f"helper_leak_rows={demand_basis_helper_leak_rows};"
                    f"future_source_rows={demand_basis_future_source_rows}"
                )

    checks.append(
        {
            "check": "f_backtest_demand_basis_integrity",
            "status": demand_basis_status,
            "value": str(demand_basis_fail_rows),
            "notes": demand_basis_notes,
            "observed_utc": snapshot_utc,
            "source_path": str(input_result.path),
        }
    )

    qualified_fail_rows = 0
    qualified_warn_rows = 0
    qualified_missing_maturity_rows = 0
    qualified_missing_value_rows = 0
    qualified_gt_raw_rows = 0
    qualified_missing_component_rows = 0
    qualified_component_mismatch_rows = 0
    qualified_missing_reason_rows = 0
    qualified_missing_zero_or_block_reason_rows = 0
    if not input_schema_ok:
        qualified_status = "fail"
        qualified_notes = "input_view_schema_failed"
    else:
        input_df = input_result.df.copy()
        required_cols = (
            "history_maturity_state",
            "demand_basis_units_monthly",
            "price_qualified_units_monthly",
            "price_qualified_profit_monthly_gbp",
            "price_qualification_reason_codes",
            "qualification_market_gate_state",
            "qualification_market_gate_factor",
            "qualification_amazon_pressure_factor",
            "qualification_buy_box_coverage_factor",
            "qualification_maturity_factor",
            "qualification_final_factor",
            "qualification_zero_or_block_reason",
        )
        missing_cols = [col for col in required_cols if col not in input_df.columns]
        if missing_cols:
            qualified_status = "fail"
            qualified_notes = f"missing_columns:{'|'.join(missing_cols)}"
            qualified_fail_rows = len(input_df.index)
        else:
            ready_df = input_df[input_df.get("input_status", "").map(lambda v: _normalize_text(v).lower() == "ready")].copy()
            if ready_df.empty:
                qualified_status = "ok"
                qualified_notes = "no_ready_input_rows"
            else:
                for _, row in ready_df.iterrows():
                    maturity = _normalize_text(row.get("history_maturity_state", ""))
                    raw_units = _num_or_none(row.get("demand_basis_units_monthly", ""))
                    qualified_units = _num_or_none(row.get("price_qualified_units_monthly", ""))
                    qualified_profit = _num_or_none(row.get("price_qualified_profit_monthly_gbp", ""))
                    reason_codes = _normalize_text(row.get("price_qualification_reason_codes", ""))
                    market_gate_state = _normalize_text(row.get("qualification_market_gate_state", ""))
                    market_gate_factor = _num_or_none(row.get("qualification_market_gate_factor", ""))
                    amazon_factor = _num_or_none(row.get("qualification_amazon_pressure_factor", ""))
                    buy_box_factor = _num_or_none(row.get("qualification_buy_box_coverage_factor", ""))
                    maturity_factor = _num_or_none(row.get("qualification_maturity_factor", ""))
                    final_factor = _num_or_none(row.get("qualification_final_factor", ""))
                    zero_or_block_reason = _normalize_text(row.get("qualification_zero_or_block_reason", ""))

                    if maturity == "":
                        qualified_missing_maturity_rows += 1
                        qualified_fail_rows += 1
                    if qualified_units is None or qualified_profit is None:
                        qualified_missing_value_rows += 1
                        qualified_fail_rows += 1
                        continue
                    if reason_codes == "":
                        qualified_missing_reason_rows += 1
                        qualified_fail_rows += 1
                    if (
                        market_gate_state == ""
                        or market_gate_factor is None
                        or amazon_factor is None
                        or buy_box_factor is None
                        or maturity_factor is None
                        or final_factor is None
                    ):
                        qualified_missing_component_rows += 1
                        qualified_fail_rows += 1
                        continue
                    component_factors = [
                        market_gate_factor,
                        amazon_factor,
                        buy_box_factor,
                        maturity_factor,
                        final_factor,
                    ]
                    if any(factor < 0 or factor > 1 for factor in component_factors):
                        qualified_component_mismatch_rows += 1
                        qualified_fail_rows += 1
                    expected_final_factor = max(
                        0.0,
                        min(1.0, market_gate_factor * amazon_factor * buy_box_factor * maturity_factor),
                    )
                    if abs(final_factor - expected_final_factor) > 0.01:
                        qualified_component_mismatch_rows += 1
                        qualified_fail_rows += 1
                    if qualified_units < 0 or qualified_profit < 0:
                        qualified_fail_rows += 1
                    if raw_units is not None and qualified_units > (raw_units + 0.5):
                        qualified_gt_raw_rows += 1
                        qualified_fail_rows += 1
                    if raw_units is not None:
                        expected_units = max(0.0, min(raw_units, raw_units * final_factor))
                        if expected_units < 0.05:
                            expected_units = 0.0
                        if abs(qualified_units - expected_units) > 0.5:
                            qualified_component_mismatch_rows += 1
                            qualified_fail_rows += 1
                    if raw_units is not None and raw_units > 0 and qualified_units == 0 and zero_or_block_reason == "":
                        qualified_missing_zero_or_block_reason_rows += 1
                        qualified_fail_rows += 1
                    if market_gate_state != "market_open" and zero_or_block_reason == "":
                        qualified_missing_zero_or_block_reason_rows += 1
                        qualified_fail_rows += 1

                if qualified_fail_rows > 0:
                    qualified_status = "fail"
                elif qualified_warn_rows > 0:
                    qualified_status = "warn"
                else:
                    qualified_status = "ok"
                qualified_notes = (
                    f"ready_rows={len(ready_df)};"
                    f"fail_rows={qualified_fail_rows};"
                    f"warn_rows={qualified_warn_rows};"
                    f"missing_maturity_rows={qualified_missing_maturity_rows};"
                    f"missing_value_rows={qualified_missing_value_rows};"
                    f"qualified_gt_raw_rows={qualified_gt_raw_rows};"
                    f"missing_component_rows={qualified_missing_component_rows};"
                    f"component_mismatch_rows={qualified_component_mismatch_rows};"
                    f"missing_reason_rows={qualified_missing_reason_rows};"
                    f"missing_zero_or_block_reason_rows={qualified_missing_zero_or_block_reason_rows}"
                )
    checks.append(
        {
            "check": "f_backtest_price_qualified_demand_integrity",
            "status": qualified_status,
            "value": str(qualified_fail_rows),
            "notes": qualified_notes,
            "observed_utc": snapshot_utc,
            "source_path": str(input_result.path),
        }
    )

    source_alignment_fail_rows = 0
    source_alignment_warn_rows = 0
    source_alignment_missing_source_rows = 0
    source_alignment_fallback_rows = 0
    if not summary_schema_ok:
        source_alignment_status = "fail"
        source_alignment_notes = "summary_schema_failed"
    else:
        summary_df = summary_result.df.copy()
        required_cols = (
            "summary_status",
            "expected_units_source",
            "expected_profit_source",
            "price_qualification_reason_codes",
            "qualification_final_factor",
            "qualification_zero_or_block_reason",
            "raw_monthly_units",
            "qualified_monthly_units",
            "seasonality_state",
            "seasonality_reason_codes",
            "stability_state",
            "stability_reason_codes",
            "recent_vs_baseline_state",
            "recent_vs_baseline_reason_codes",
        )
        missing_cols = [col for col in required_cols if col not in summary_df.columns]
        if missing_cols:
            source_alignment_status = "fail" if len(summary_df.index) > 0 else "ok"
            source_alignment_notes = f"missing_columns:{'|'.join(missing_cols)}"
            source_alignment_fail_rows = len(summary_df.index)
        else:
            ready_df = summary_df[
                summary_df.get("summary_status", "").map(lambda v: _normalize_text(v).lower() == "ready")
            ].copy()
            if ready_df.empty:
                source_alignment_status = "ok"
                source_alignment_notes = "no_ready_summary_rows"
            else:
                for _, row in ready_df.iterrows():
                    expected_units_source = _normalize_text(row.get("expected_units_source", ""))
                    expected_profit_source = _normalize_text(row.get("expected_profit_source", ""))
                    reason_codes = _normalize_text(row.get("price_qualification_reason_codes", ""))
                    final_factor = _num_or_none(row.get("qualification_final_factor", ""))
                    zero_or_block_reason = _normalize_text(row.get("qualification_zero_or_block_reason", ""))
                    raw_units = _num_or_none(row.get("raw_monthly_units", ""))
                    qualified_units = _num_or_none(row.get("qualified_monthly_units", ""))
                    seasonality_state = _normalize_text(row.get("seasonality_state", ""))
                    seasonality_reason_codes = _normalize_text(row.get("seasonality_reason_codes", ""))
                    stability_state = _normalize_text(row.get("stability_state", ""))
                    stability_reason_codes = _normalize_text(row.get("stability_reason_codes", ""))
                    recent_state = _normalize_text(row.get("recent_vs_baseline_state", ""))
                    recent_reason_codes = _normalize_text(row.get("recent_vs_baseline_reason_codes", ""))

                    if expected_units_source == "" or expected_profit_source == "":
                        source_alignment_missing_source_rows += 1
                        source_alignment_fail_rows += 1
                    if expected_units_source != "input_qualified" or expected_profit_source != "input_qualified":
                        source_alignment_fallback_rows += 1
                        source_alignment_fail_rows += 1
                    if reason_codes == "":
                        source_alignment_fail_rows += 1
                    if final_factor is None:
                        source_alignment_fail_rows += 1
                    elif final_factor < 0 or final_factor > 1:
                        source_alignment_fail_rows += 1
                    if raw_units is not None and raw_units > 0 and qualified_units is not None and qualified_units == 0:
                        if zero_or_block_reason == "":
                            source_alignment_warn_rows += 1
                    if seasonality_state == "" or stability_state == "" or recent_state == "":
                        source_alignment_fail_rows += 1
                    if seasonality_reason_codes == "" or stability_reason_codes == "" or recent_reason_codes == "":
                        source_alignment_fail_rows += 1
                    if seasonality_state not in SEASONALITY_STATES:
                        source_alignment_fail_rows += 1
                    if stability_state not in STABILITY_STATES:
                        source_alignment_fail_rows += 1
                    if recent_state not in RECENT_STATES:
                        source_alignment_fail_rows += 1

                if source_alignment_fail_rows > 0:
                    source_alignment_status = "fail"
                elif source_alignment_warn_rows > 0:
                    source_alignment_status = "warn"
                else:
                    source_alignment_status = "ok"
                source_alignment_notes = (
                    f"ready_rows={len(ready_df)};"
                    f"fail_rows={source_alignment_fail_rows};"
                    f"warn_rows={source_alignment_warn_rows};"
                    f"fallback_rows={source_alignment_fallback_rows};"
                    f"missing_source_rows={source_alignment_missing_source_rows}"
                )
    checks.append(
        {
            "check": "f_backtest_qualification_source_alignment",
            "status": source_alignment_status,
            "value": str(source_alignment_fail_rows),
            "notes": source_alignment_notes,
            "observed_utc": snapshot_utc,
            "source_path": str(summary_result.path),
        }
    )

    seasonality_fail_rows = 0
    seasonality_warn_rows = 0
    if not input_schema_ok:
        seasonality_status = "fail"
        seasonality_notes = "input_view_schema_failed"
    else:
        input_df = input_result.df.copy()
        required_cols = ("seasonality_state", "seasonality_reason_codes", "completed_months_count")
        missing_cols = [col for col in required_cols if col not in input_df.columns]
        if missing_cols:
            seasonality_status = "fail" if len(input_df.index) > 0 else "ok"
            seasonality_notes = f"missing_columns:{'|'.join(missing_cols)}"
            seasonality_fail_rows = len(input_df.index)
        else:
            ready_df = input_df[input_df.get("input_status", "").map(lambda v: _normalize_text(v).lower() == "ready")].copy()
            if ready_df.empty:
                seasonality_status = "ok"
                seasonality_notes = "no_ready_input_rows"
            else:
                for _, row in ready_df.iterrows():
                    state = _normalize_text(row.get("seasonality_state", ""))
                    reasons = _normalize_text(row.get("seasonality_reason_codes", ""))
                    completed_months = int(_num_or_none(row.get("completed_months_count", "")) or 0)
                    if state == "" or reasons == "":
                        seasonality_fail_rows += 1
                        continue
                    if state not in SEASONALITY_STATES:
                        seasonality_fail_rows += 1
                    if state == "insufficient_history" and completed_months >= 6:
                        seasonality_warn_rows += 1
                    if state == "seasonal_confirmed" and completed_months < 9:
                        seasonality_fail_rows += 1
                if seasonality_fail_rows > 0:
                    seasonality_status = "fail"
                elif seasonality_warn_rows > 0:
                    seasonality_status = "warn"
                else:
                    seasonality_status = "ok"
                seasonality_notes = (
                    f"ready_rows={len(ready_df)};"
                    f"fail_rows={seasonality_fail_rows};"
                    f"warn_rows={seasonality_warn_rows}"
                )
    checks.append(
        {
            "check": "f_backtest_seasonality_classifier_integrity",
            "status": seasonality_status,
            "value": str(seasonality_fail_rows),
            "notes": seasonality_notes,
            "observed_utc": snapshot_utc,
            "source_path": str(input_result.path),
        }
    )

    stability_fail_rows = 0
    stability_warn_rows = 0
    if not input_schema_ok:
        stability_status = "fail"
        stability_notes = "input_view_schema_failed"
    else:
        input_df = input_result.df.copy()
        required_cols = ("stability_state", "stability_reason_codes", "completed_months_count")
        missing_cols = [col for col in required_cols if col not in input_df.columns]
        if missing_cols:
            stability_status = "fail" if len(input_df.index) > 0 else "ok"
            stability_notes = f"missing_columns:{'|'.join(missing_cols)}"
            stability_fail_rows = len(input_df.index)
        else:
            ready_df = input_df[input_df.get("input_status", "").map(lambda v: _normalize_text(v).lower() == "ready")].copy()
            if ready_df.empty:
                stability_status = "ok"
                stability_notes = "no_ready_input_rows"
            else:
                for _, row in ready_df.iterrows():
                    state = _normalize_text(row.get("stability_state", ""))
                    reasons = _normalize_text(row.get("stability_reason_codes", ""))
                    completed_months = int(_num_or_none(row.get("completed_months_count", "")) or 0)
                    if state == "" or reasons == "":
                        stability_fail_rows += 1
                        continue
                    if state not in STABILITY_STATES:
                        stability_fail_rows += 1
                    if state == "too_new" and completed_months >= 3:
                        stability_warn_rows += 1
                    if state != "too_new" and completed_months < 3:
                        stability_fail_rows += 1
                if stability_fail_rows > 0:
                    stability_status = "fail"
                elif stability_warn_rows > 0:
                    stability_status = "warn"
                else:
                    stability_status = "ok"
                stability_notes = (
                    f"ready_rows={len(ready_df)};"
                    f"fail_rows={stability_fail_rows};"
                    f"warn_rows={stability_warn_rows}"
                )
    checks.append(
        {
            "check": "f_backtest_stability_classifier_integrity",
            "status": stability_status,
            "value": str(stability_fail_rows),
            "notes": stability_notes,
            "observed_utc": snapshot_utc,
            "source_path": str(input_result.path),
        }
    )

    recent_fail_rows = 0
    recent_warn_rows = 0
    if not input_schema_ok:
        recent_status = "fail"
        recent_notes = "input_view_schema_failed"
    else:
        input_df = input_result.df.copy()
        required_cols = ("recent_vs_baseline_state", "recent_vs_baseline_reason_codes", "completed_months_count")
        missing_cols = [col for col in required_cols if col not in input_df.columns]
        if missing_cols:
            recent_status = "fail" if len(input_df.index) > 0 else "ok"
            recent_notes = f"missing_columns:{'|'.join(missing_cols)}"
            recent_fail_rows = len(input_df.index)
        else:
            ready_df = input_df[input_df.get("input_status", "").map(lambda v: _normalize_text(v).lower() == "ready")].copy()
            if ready_df.empty:
                recent_status = "ok"
                recent_notes = "no_ready_input_rows"
            else:
                for _, row in ready_df.iterrows():
                    state = _normalize_text(row.get("recent_vs_baseline_state", ""))
                    reasons = _normalize_text(row.get("recent_vs_baseline_reason_codes", ""))
                    completed_months = int(_num_or_none(row.get("completed_months_count", "")) or 0)
                    if state == "" or reasons == "":
                        recent_fail_rows += 1
                        continue
                    if state not in RECENT_STATES:
                        recent_fail_rows += 1
                    if state == "insufficient_history" and completed_months >= 3:
                        recent_warn_rows += 1
                    if state != "insufficient_history" and completed_months < 3:
                        recent_fail_rows += 1
                if recent_fail_rows > 0:
                    recent_status = "fail"
                elif recent_warn_rows > 0:
                    recent_status = "warn"
                else:
                    recent_status = "ok"
                recent_notes = (
                    f"ready_rows={len(ready_df)};"
                    f"fail_rows={recent_fail_rows};"
                    f"warn_rows={recent_warn_rows}"
                )
    checks.append(
        {
            "check": "f_backtest_recent_vs_baseline_integrity",
            "status": recent_status,
            "value": str(recent_fail_rows),
            "notes": recent_notes,
            "observed_utc": snapshot_utc,
            "source_path": str(input_result.path),
        }
    )

    decision_fail_rows = 0
    decision_warn_rows = 0
    if not summary_schema_ok:
        decision_status = "fail"
        decision_notes = "summary_schema_failed"
    else:
        summary_df = summary_result.df.copy()
        required_cols = (
            "decision_state",
            "expected_profit_next_30d_gbp",
            "minimum_expected_profit_gbp",
        )
        missing_cols = [col for col in required_cols if col not in summary_df.columns]
        if missing_cols:
            decision_status = "fail" if len(summary_df.index) > 0 else "ok"
            decision_notes = f"missing_columns:{'|'.join(missing_cols)}"
            decision_fail_rows = len(summary_df.index)
        else:
            ready_df = summary_df[
                summary_df.get("summary_status", "").map(lambda v: _normalize_text(v).lower() == "ready")
            ].copy()
            if ready_df.empty:
                decision_status = "ok"
                decision_notes = "no_ready_summary_rows"
            else:
                allowed_states = {"pass", "fail", "manual_review"}
                for _, row in ready_df.iterrows():
                    decision_state = _normalize_text(row.get("decision_state", "")).lower()
                    expected_profit = _num_or_none(row.get("expected_profit_next_30d_gbp", ""))
                    floor_profit = _num_or_none(row.get("minimum_expected_profit_gbp", "")) or 20.0
                    if decision_state not in allowed_states:
                        decision_fail_rows += 1
                        continue
                    if expected_profit is None:
                        decision_fail_rows += 1
                        continue
                    if decision_state == "pass" and expected_profit < floor_profit:
                        decision_fail_rows += 1
                    elif decision_state == "fail" and expected_profit >= floor_profit:
                        decision_warn_rows += 1

                if decision_fail_rows > 0:
                    decision_status = "fail"
                elif decision_warn_rows > 0:
                    decision_status = "warn"
                else:
                    decision_status = "ok"
                decision_notes = (
                    f"ready_rows={len(ready_df)};"
                    f"fail_rows={decision_fail_rows};"
                    f"warn_rows={decision_warn_rows}"
                )
    checks.append(
        {
            "check": "f_backtest_decision_floor_integrity",
            "status": decision_status,
            "value": str(decision_fail_rows),
            "notes": decision_notes,
            "observed_utc": snapshot_utc,
            "source_path": str(summary_result.path),
        }
    )

    confidence_fail_rows = 0
    confidence_warn_rows = 0
    if not summary_schema_ok:
        confidence_status = "fail"
        confidence_notes = "summary_schema_failed"
    else:
        summary_df = summary_result.df.copy()
        required_cols = (
            "summary_status",
            "decision_state",
            "decision_confidence",
            "decision_confidence_reason_codes",
        )
        missing_cols = [col for col in required_cols if col not in summary_df.columns]
        if missing_cols:
            confidence_status = "fail" if len(summary_df.index) > 0 else "ok"
            confidence_notes = f"missing_columns:{'|'.join(missing_cols)}"
            confidence_fail_rows = len(summary_df.index)
        else:
            ready_df = summary_df[
                summary_df.get("summary_status", "").map(lambda v: _normalize_text(v).lower() == "ready")
            ].copy()
            if ready_df.empty:
                confidence_status = "ok"
                confidence_notes = "no_ready_summary_rows"
            else:
                allowed_confidence = {"high", "medium", "low"}
                for _, row in ready_df.iterrows():
                    decision_state = _normalize_text(row.get("decision_state", "")).lower()
                    confidence = _normalize_text(row.get("decision_confidence", "")).lower()
                    confidence_reasons = _normalize_text(row.get("decision_confidence_reason_codes", ""))
                    if confidence not in allowed_confidence:
                        confidence_fail_rows += 1
                        continue
                    if confidence_reasons == "":
                        confidence_fail_rows += 1
                    if decision_state == "pass" and confidence == "low":
                        confidence_fail_rows += 1
                    elif decision_state == "manual_review" and confidence == "high":
                        confidence_warn_rows += 1

                if confidence_fail_rows > 0:
                    confidence_status = "fail"
                elif confidence_warn_rows > 0:
                    confidence_status = "warn"
                else:
                    confidence_status = "ok"
                confidence_notes = (
                    f"ready_rows={len(ready_df)};"
                    f"fail_rows={confidence_fail_rows};"
                    f"warn_rows={confidence_warn_rows}"
                )
    checks.append(
        {
            "check": "f_backtest_decision_confidence_integrity",
            "status": confidence_status,
            "value": str(confidence_fail_rows),
            "notes": confidence_notes,
            "observed_utc": snapshot_utc,
            "source_path": str(summary_result.path),
        }
    )

    share_value_missing_rows = 0
    share_invalid_rows = 0
    share_out_of_bounds_rows = 0
    high_amazon_share_rows = 0
    amazon_scenario_rows = 0
    if not replay_schema_ok:
        sales_share_status = "fail"
        sales_share_notes = "replay_schema_failed"
    elif replay_rows <= 0:
        sales_share_status = "ok"
        sales_share_notes = "no_replay_rows"
    else:
        raw_share = replay_result.df.get("sales_share_pct", "").map(_normalize_text)
        non_empty_share = raw_share.map(lambda v: v != "")
        share_value_missing_rows = int((~non_empty_share).sum())
        parsed_share = raw_share.map(_num_or_none)
        share_invalid_rows = int((non_empty_share & parsed_share.isna()).sum())
        share_out_of_bounds_rows = int(
            ((parsed_share < 0.0) | (parsed_share > 100.0)).fillna(False).sum()
        )
        amazon_scenario_rows = int(
            replay_result.df.get("competition_scenario", "").map(
                lambda v: _normalize_text(v) in {"sharing_with_amazon", "sharing_with_amazon_and_fba"}
            ).sum()
        )
        if amazon_scenario_rows > 0:
            amazon_mask = replay_result.df.get("competition_scenario", "").map(
                lambda v: _normalize_text(v) in {"sharing_with_amazon", "sharing_with_amazon_and_fba"}
            )
            high_amazon_share_rows = int(((parsed_share > 80.0).fillna(False) & amazon_mask).sum())

        if share_invalid_rows > 0 or share_out_of_bounds_rows > 0:
            sales_share_status = "fail"
            sales_share_notes = (
                f"invalid={share_invalid_rows};out_of_bounds={share_out_of_bounds_rows};"
                f"missing={share_value_missing_rows}"
            )
        elif int(non_empty_share.sum()) <= 0:
            sales_share_status = "warn"
            sales_share_notes = "sales_share_values_missing"
        elif amazon_scenario_rows > 0 and (high_amazon_share_rows / amazon_scenario_rows) > 0.3:
            sales_share_status = "warn"
            sales_share_notes = (
                f"high_amazon_share_rows={high_amazon_share_rows};"
                f"amazon_rows={amazon_scenario_rows}"
            )
        else:
            sales_share_status = "ok"
            sales_share_notes = (
                f"missing={share_value_missing_rows};amazon_rows={amazon_scenario_rows};"
                f"high_amazon_share_rows={high_amazon_share_rows}"
            )

    checks.append(
        {
            "check": "f_backtest_sales_share_validity",
            "status": sales_share_status,
            "value": str(share_invalid_rows + share_out_of_bounds_rows),
            "notes": sales_share_notes,
            "observed_utc": snapshot_utc,
            "source_path": str(replay_result.path),
        }
    )

    join_resolution_warn_rows = 0
    if input_schema_ok:
        input_df = input_result.df.copy()
        ready_mask = input_df.get("input_status", "").map(lambda v: _normalize_text(v).lower() == "ready")
        flagged_mask = input_df.get("mapping_status", "").map(
            lambda v: _normalize_text(v) in {"multi_sku_asin_match", "no_product_db_match"}
        )
        join_resolution_warn_rows = int((ready_mask & flagged_mask).sum())
    if join_resolution_warn_rows > 0:
        join_resolution_status = "warn"
        join_resolution_notes = f"ready_rows_with_join_resolution_flags={join_resolution_warn_rows}"
    else:
        join_resolution_status = "ok"
        join_resolution_notes = "no_ready_join_resolution_warnings"
    checks.append(
        {
            "check": "f_backtest_join_resolution",
            "status": join_resolution_status,
            "value": str(join_resolution_warn_rows),
            "notes": join_resolution_notes,
            "observed_utc": snapshot_utc,
            "source_path": str(input_result.path),
        }
    )

    health_df = _write_contract_df(pd.DataFrame(checks), "feeder_backtest_health", root_path)
    status_counts = health_df["status"].value_counts().to_dict() if not health_df.empty else {}
    print(
        {
            "status": "success",
            "rows": int(len(health_df)),
            "status_counts": status_counts,
            "snapshot": str(root_path / get_f_output_contract("feeder_backtest_health").rel_path),
        }
    )
    return health_df


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build F backtest health checks from current backtest artifacts.")
    parser.add_argument("--observed-utc", default=None, help="Override observed_utc for deterministic runs.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_backtest_health(observed_utc=args.observed_utc)


if __name__ == "__main__":
    main()
