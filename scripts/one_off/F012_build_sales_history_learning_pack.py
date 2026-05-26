from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUMMARY_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv"
DEFAULT_ACTUALS_PATH = ROOT / "out" / "analysis_reports" / "f_sales_history_learning_actuals_latest.csv"
DEFAULT_LEARNING_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_sales_history_learning_live.csv"
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"
DEFAULT_ALIGNMENT_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_alignment_30d_latest.csv"
DEFAULT_DECISION_STATES = "pass"

CONTROLLED_LEARNING_OUTCOMES = {
    "right_call",
    "demand_too_high",
    "demand_too_low",
    "price_assumption_wrong",
    "amazon_suppressed",
    "seasonality_misread",
    "operational_blocker",
    "pending_outcome",
}

LEARNING_LOG_COLUMNS = [
    "observed_utc",
    "decision_snapshot_utc",
    "seller_sku",
    "asin",
    "amazon_link",
    "decision_state_at_snapshot",
    "decision_confidence_at_snapshot",
    "expected_units_next_30d",
    "expected_profit_next_30d_gbp",
    "actual_units_30d",
    "actual_profit_30d_gbp",
    "actual_units_60d",
    "actual_profit_60d_gbp",
    "actual_units_90d",
    "actual_profit_90d_gbp",
    "outcome_basis_window_days",
    "expected_units_at_basis_window",
    "actual_units_at_basis_window",
    "units_error_at_basis_window",
    "units_error_ratio_at_basis_window",
    "learning_outcome",
    "learning_reason_codes",
    "operator_check_utc",
    "operator_notes",
    "purchased_flag",
    "record_updated_utc",
]

REVIEW_COLUMNS = [
    "observed_utc",
    "decision_snapshot_utc",
    "seller_sku",
    "asin",
    "amazon_link",
    "decision_state_at_snapshot",
    "decision_confidence_at_snapshot",
    "expected_units_next_30d",
    "expected_profit_next_30d_gbp",
    "actual_units_30d",
    "actual_units_60d",
    "actual_units_90d",
    "actual_profit_30d_gbp",
    "actual_profit_60d_gbp",
    "actual_profit_90d_gbp",
    "outcome_basis_window_days",
    "expected_units_at_basis_window",
    "actual_units_at_basis_window",
    "units_error_at_basis_window",
    "units_error_ratio_at_basis_window",
    "learning_outcome",
    "learning_reason_codes",
    "operator_check_utc",
    "operator_notes",
    "purchased_flag",
]

ACTUALS_TEMPLATE_COLUMNS = [
    "decision_snapshot_utc",
    "seller_sku",
    "asin",
    "amazon_link",
    "decision_state_at_snapshot",
    "decision_confidence_at_snapshot",
    "expected_units_next_30d",
    "expected_profit_next_30d_gbp",
    "actual_units_30d",
    "actual_profit_30d_gbp",
    "actual_units_60d",
    "actual_profit_60d_gbp",
    "actual_units_90d",
    "actual_profit_90d_gbp",
    "learning_outcome",
    "learning_reason_codes",
    "operator_check_utc",
    "operator_notes",
    "purchased_flag",
]

SUMMARY_SNAPSHOT_COLUMNS = [
    "decision_snapshot_utc",
    "seller_sku",
    "asin",
    "amazon_link",
    "decision_state_at_snapshot",
    "decision_confidence_at_snapshot",
    "expected_units_next_30d",
    "expected_profit_next_30d_gbp",
]


@dataclass(frozen=True)
class SalesHistoryLearningPackResult:
    learning_df: pd.DataFrame
    review_df: pd.DataFrame
    health_df: pd.DataFrame
    template_df: pd.DataFrame
    learning_path: Path
    review_path: Path
    review_latest_path: Path
    health_path: Path
    health_latest_path: Path
    template_path: Path
    template_latest_path: Path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_timestamp_slug(observed_utc: str) -> str:
    dt = datetime.strptime(observed_utc, "%Y-%m-%dT%H:%M:%SZ")
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _normalize_decision_state(value: object) -> str:
    token = _normalize_text(value).lower().replace(" ", "_")
    if token in {"pass", "fail", "manual_review", "operational_truth_only"}:
        return token
    if token in {"manual", "manualreview", "review"}:
        return "manual_review"
    if token in {"operational_truth", "truth_only", "operational_only"}:
        return "operational_truth_only"
    return ""


def _normalize_outcome(value: object) -> str:
    token = _normalize_text(value).lower().replace(" ", "_")
    if token in CONTROLLED_LEARNING_OUTCOMES:
        return token
    return ""


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


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _amazon_link(asin: str) -> str:
    asin_key = _normalize_text(asin)
    if asin_key == "":
        return ""
    return f"https://www.amazon.co.uk/dp/{asin_key}"


def _latest_row_index(df: pd.DataFrame, *, sku_col: str, asin_col: str, snapshot_col: str) -> dict[tuple[str, str, str], dict[str, str]]:
    if df.empty:
        return {}
    work = df.copy()
    work["_sku"] = work.get(sku_col, "").map(_normalize_key)
    work["_asin"] = work.get(asin_col, "").map(_normalize_key)
    work["_snapshot"] = work.get(snapshot_col, "").map(_normalize_text)
    work = work[(work["_sku"] != "") | (work["_asin"] != "")].copy()
    if work.empty:
        return {}

    ts_col = ""
    for candidate in ("operator_check_utc", "record_updated_utc", "observed_utc"):
        if candidate in work.columns:
            ts_col = candidate
            break
    if ts_col != "":
        work["_ts"] = pd.to_datetime(work.get(ts_col, "").map(_normalize_text), errors="coerce")
        work = work.sort_values("_ts", ascending=False, kind="stable")

    out: dict[tuple[str, str, str], dict[str, str]] = {}
    for _, row in work.iterrows():
        key = (
            _normalize_key(row.get(sku_col, "")),
            _normalize_key(row.get(asin_col, "")),
            _normalize_text(row.get(snapshot_col, "")),
        )
        if key in out:
            continue
        out[key] = {column: _normalize_text(value) for column, value in row.to_dict().items()}
    return out


def _latest_pair_index(df: pd.DataFrame, *, sku_col: str, asin_col: str) -> dict[tuple[str, str], dict[str, str]]:
    if df.empty:
        return {}
    work = df.copy()
    work["_sku"] = work.get(sku_col, "").map(_normalize_key)
    work["_asin"] = work.get(asin_col, "").map(_normalize_key)
    work = work[(work["_sku"] != "") | (work["_asin"] != "")].copy()
    if work.empty:
        return {}

    ts_col = ""
    for candidate in ("operator_check_utc", "record_updated_utc", "observed_utc", "decision_snapshot_utc"):
        if candidate in work.columns:
            ts_col = candidate
            break
    if ts_col != "":
        work["_ts"] = pd.to_datetime(work.get(ts_col, "").map(_normalize_text), errors="coerce")
        work = work.sort_values("_ts", ascending=False, kind="stable")

    out: dict[tuple[str, str], dict[str, str]] = {}
    for _, row in work.iterrows():
        key = (
            _normalize_key(row.get(sku_col, "")),
            _normalize_key(row.get(asin_col, "")),
        )
        if key in out:
            continue
        out[key] = {column: _normalize_text(value) for column, value in row.to_dict().items()}
    return out


def _parse_allowed_decision_states(raw: str) -> set[str]:
    tokens = [_normalize_decision_state(token) for token in str(raw).split(",")]
    allowed = {token for token in tokens if token != ""}
    if not allowed:
        return {"pass"}
    return allowed


def _select_window(actual_30d: float | None, actual_60d: float | None, actual_90d: float | None) -> tuple[int, float | None]:
    if actual_90d is not None:
        return 90, actual_90d
    if actual_60d is not None:
        return 60, actual_60d
    if actual_30d is not None:
        return 30, actual_30d
    return 0, None


def _infer_outcome(
    *,
    expected_units_30d: float | None,
    actual_units_30d: float | None,
    actual_units_60d: float | None,
    actual_units_90d: float | None,
) -> tuple[str, str, float | None, float | None, float | None, int]:
    basis_window, actual_units_basis = _select_window(actual_units_30d, actual_units_60d, actual_units_90d)
    if basis_window == 0 or actual_units_basis is None:
        return "pending_outcome", "missing_actual_units", None, None, None, 0
    if expected_units_30d is None:
        return "pending_outcome", "missing_expected_units", None, None, None, basis_window

    expected_units_30d_num = expected_units_30d if expected_units_30d is not None else 0.0
    expected_units_basis = expected_units_30d_num * (basis_window / 30.0)
    units_error = actual_units_basis - expected_units_basis
    units_error_ratio = units_error / max(abs(expected_units_basis), 1.0)

    if expected_units_basis <= 0 and actual_units_basis > 0:
        return "demand_too_low", f"inferred_from_{basis_window}d_units", expected_units_basis, units_error, units_error_ratio, basis_window
    if abs(units_error_ratio) <= 0.2:
        return "right_call", f"inferred_from_{basis_window}d_units", expected_units_basis, units_error, units_error_ratio, basis_window
    if units_error_ratio < -0.2:
        return "demand_too_high", f"inferred_from_{basis_window}d_units", expected_units_basis, units_error, units_error_ratio, basis_window
    return "demand_too_low", f"inferred_from_{basis_window}d_units", expected_units_basis, units_error, units_error_ratio, basis_window


def _alignment_expected_by_asin(alignment_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    if alignment_df.empty:
        return {}
    def _col(name: str) -> pd.Series:
        if name in alignment_df.columns:
            return alignment_df[name].map(_normalize_text)
        return pd.Series([""] * len(alignment_df.index), index=alignment_df.index, dtype=str)

    work = pd.DataFrame()
    work["asin"] = _col("asin").str.upper()
    work["expected_units_30d"] = _col("expected_units_30d")
    work["expected_profit_30d_gbp"] = _col("expected_profit_30d_gbp")
    work["alignment_window_end_utc"] = _col("alignment_window_end_utc")
    work = work[work["asin"] != ""].copy()
    if work.empty:
        return {}
    work["_ts"] = pd.to_datetime(work["alignment_window_end_utc"], errors="coerce", utc=True)
    work = work.sort_values(["asin", "_ts"], ascending=[True, False], kind="stable")
    work = work.drop_duplicates(subset=["asin"], keep="first")
    out: dict[str, dict[str, str]] = {}
    for _, row in work.iterrows():
        asin = _normalize_text(row.get("asin", "")).upper()
        if asin == "":
            continue
        out[asin] = {
            "expected_units_next_30d": _normalize_text(row.get("expected_units_30d", "")),
            "expected_profit_next_30d_gbp": _normalize_text(row.get("expected_profit_30d_gbp", "")),
        }
    return out


def _build_operational_truth_rows(
    *,
    actuals_index: dict[tuple[str, str, str], dict[str, str]],
    existing_summary_keys: set[tuple[str, str, str]],
    alignment_expected_by_asin: dict[str, dict[str, str]],
    snapshot_utc: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for actuals_row in actuals_index.values():
        actuals_basis = _normalize_text(actuals_row.get("actuals_basis", "")).lower()
        if actuals_basis != "operational_baseline":
            continue
        seller_sku = _normalize_text(actuals_row.get("seller_sku", ""))
        asin = _normalize_text(actuals_row.get("asin", ""))
        if seller_sku == "" and asin == "":
            continue
        decision_snapshot_utc = _normalize_text(actuals_row.get("decision_snapshot_utc", "")) or snapshot_utc
        key = (_normalize_key(seller_sku), _normalize_key(asin), _normalize_text(decision_snapshot_utc))
        if key in existing_summary_keys or key in seen_keys:
            continue
        seen_keys.add(key)
        expected_row = alignment_expected_by_asin.get(asin, {})
        rows.append(
            {
                "decision_snapshot_utc": decision_snapshot_utc,
                "seller_sku": seller_sku,
                "asin": asin,
                "amazon_link": _normalize_text(actuals_row.get("amazon_link", "")) or _amazon_link(asin),
                "decision_state_at_snapshot": "operational_truth_only",
                "decision_confidence_at_snapshot": "",
                "expected_units_next_30d": _normalize_text(expected_row.get("expected_units_next_30d", "")),
                "expected_profit_next_30d_gbp": _normalize_text(expected_row.get("expected_profit_next_30d_gbp", "")),
            }
        )
    return rows


def _build_health_df(*, observed_utc: str, review_df: pd.DataFrame) -> pd.DataFrame:
    if review_df.empty:
        return pd.DataFrame(
            [
                {"observed_utc": observed_utc, "metric": "rows_total", "value": "0"},
                {"observed_utc": observed_utc, "metric": "rows_with_outcome", "value": "0"},
                {"observed_utc": observed_utc, "metric": "rows_pending_outcome", "value": "0"},
            ]
        )

    outcomes = review_df.get("learning_outcome", "").map(_normalize_outcome)
    pending = int((outcomes == "pending_outcome").sum())
    with_outcome = int(((outcomes != "") & (outcomes != "pending_outcome")).sum())

    health_rows: list[dict[str, str]] = [
        {"observed_utc": observed_utc, "metric": "rows_total", "value": str(len(review_df))},
        {
            "observed_utc": observed_utc,
            "metric": "rows_with_actuals_30d",
            "value": str(int((review_df.get("actual_units_30d", "").map(_normalize_text) != "").sum())),
        },
        {
            "observed_utc": observed_utc,
            "metric": "rows_with_actuals_60d",
            "value": str(int((review_df.get("actual_units_60d", "").map(_normalize_text) != "").sum())),
        },
        {
            "observed_utc": observed_utc,
            "metric": "rows_with_actuals_90d",
            "value": str(int((review_df.get("actual_units_90d", "").map(_normalize_text) != "").sum())),
        },
        {
            "observed_utc": observed_utc,
            "metric": "rows_operational_truth_only",
            "value": str(
                int(
                    (
                        review_df.get("decision_state_at_snapshot", "")
                        .map(_normalize_text)
                        .str.lower()
                        == "operational_truth_only"
                    ).sum()
                )
            ),
        },
        {
            "observed_utc": observed_utc,
            "metric": "rows_operational_truth_with_expected",
            "value": str(
                int(
                    (
                        (review_df.get("decision_state_at_snapshot", "").map(_normalize_text).str.lower() == "operational_truth_only")
                        & (review_df.get("expected_units_next_30d", "").map(_normalize_text) != "")
                    ).sum()
                )
            ),
        },
        {"observed_utc": observed_utc, "metric": "rows_with_outcome", "value": str(with_outcome)},
        {"observed_utc": observed_utc, "metric": "rows_pending_outcome", "value": str(pending)},
    ]
    for outcome in sorted(CONTROLLED_LEARNING_OUTCOMES):
        health_rows.append(
            {
                "observed_utc": observed_utc,
                "metric": f"outcome::{outcome}",
                "value": str(int((outcomes == outcome).sum())),
            }
        )
    return pd.DataFrame(health_rows)


def _empty_df(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def build_sales_history_learning_pack(
    *,
    summary_path: Path = DEFAULT_SUMMARY_PATH,
    actuals_path: Path = DEFAULT_ACTUALS_PATH,
    alignment_path: Path = DEFAULT_ALIGNMENT_PATH,
    learning_path: Path = DEFAULT_LEARNING_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    observed_utc: str | None = None,
    decision_states: str = DEFAULT_DECISION_STATES,
) -> SalesHistoryLearningPackResult:
    snapshot_utc = observed_utc or _utc_now_iso()
    summary_df = _read_csv(summary_path)
    actuals_df = _read_csv(actuals_path)
    alignment_df = _read_csv(alignment_path)
    existing_learning_df = _read_csv(learning_path)
    allowed_decision_states = _parse_allowed_decision_states(decision_states)

    output_dir.mkdir(parents=True, exist_ok=True)
    learning_path.parent.mkdir(parents=True, exist_ok=True)

    ts_slug = _to_timestamp_slug(snapshot_utc)
    review_path = output_dir / f"f_sales_history_learning_review_{ts_slug}.csv"
    review_latest_path = output_dir / "f_sales_history_learning_review_latest.csv"
    health_path = output_dir / f"f_sales_history_learning_health_{ts_slug}.csv"
    health_latest_path = output_dir / "f_sales_history_learning_health_latest.csv"
    template_path = output_dir / f"f_sales_history_learning_actuals_template_{ts_slug}.csv"
    template_latest_path = output_dir / "f_sales_history_learning_actuals_template_latest.csv"

    if summary_df.empty:
        learning_df = _empty_df(LEARNING_LOG_COLUMNS)
        review_df = _empty_df(REVIEW_COLUMNS)
        health_df = _build_health_df(observed_utc=snapshot_utc, review_df=review_df)
        template_df = _empty_df(ACTUALS_TEMPLATE_COLUMNS)
    else:
        summary_latest_index = _latest_row_index(
            summary_df,
            sku_col="seller_sku",
            asin_col="asin",
            snapshot_col="observed_utc",
        )
        summary_rows: list[dict[str, str]] = []
        for row in summary_latest_index.values():
            decision_state = _normalize_decision_state(row.get("decision_state", ""))
            if decision_state not in allowed_decision_states:
                continue
            seller_sku = _normalize_text(row.get("seller_sku", ""))
            asin = _normalize_text(row.get("asin", ""))
            if seller_sku == "" and asin == "":
                continue
            decision_snapshot_utc = _normalize_text(row.get("observed_utc", "")) or snapshot_utc
            summary_rows.append(
                {
                    "decision_snapshot_utc": decision_snapshot_utc,
                    "seller_sku": seller_sku,
                    "asin": asin,
                    "amazon_link": _normalize_text(row.get("amazon_link", "")) or _amazon_link(asin),
                    "decision_state_at_snapshot": decision_state,
                    "decision_confidence_at_snapshot": _normalize_text(row.get("decision_confidence", "")).lower(),
                    "expected_units_next_30d": _normalize_text(row.get("expected_units_next_30d", "")),
                    "expected_profit_next_30d_gbp": _normalize_text(row.get("expected_profit_next_30d_gbp", "")),
                }
            )

        summary_snapshot_df = pd.DataFrame(summary_rows, columns=SUMMARY_SNAPSHOT_COLUMNS)
        summary_snapshot_df = summary_snapshot_df.sort_values(
            by=["decision_snapshot_utc", "asin", "seller_sku"],
            key=lambda s: s.map(lambda v: _normalize_text(v).upper()),
            kind="stable",
        ).reset_index(drop=True)

        actuals_index = _latest_row_index(
            actuals_df,
            sku_col="seller_sku",
            asin_col="asin",
            snapshot_col="decision_snapshot_utc",
        )
        actuals_pair_index = _latest_pair_index(
            actuals_df,
            sku_col="seller_sku",
            asin_col="asin",
        )
        expected_by_asin = _alignment_expected_by_asin(alignment_df)
        existing_index = _latest_row_index(
            existing_learning_df,
            sku_col="seller_sku",
            asin_col="asin",
            snapshot_col="decision_snapshot_utc",
        )
        existing_pair_index = _latest_pair_index(
            existing_learning_df,
            sku_col="seller_sku",
            asin_col="asin",
        )

        summary_keys = {
            (
                _normalize_key(row.get("seller_sku", "")),
                _normalize_key(row.get("asin", "")),
                _normalize_text(row.get("decision_snapshot_utc", "")),
            )
            for row in summary_snapshot_df.to_dict("records")
        }
        operational_truth_rows = _build_operational_truth_rows(
            actuals_index=actuals_index,
            existing_summary_keys=summary_keys,
            alignment_expected_by_asin=expected_by_asin,
            snapshot_utc=snapshot_utc,
        )
        if operational_truth_rows:
            summary_snapshot_df = pd.concat(
                [
                    summary_snapshot_df,
                    pd.DataFrame(operational_truth_rows, columns=SUMMARY_SNAPSHOT_COLUMNS),
                ],
                ignore_index=True,
            )
            summary_snapshot_df = summary_snapshot_df.sort_values(
                by=["decision_snapshot_utc", "asin", "seller_sku"],
                key=lambda s: s.map(lambda v: _normalize_text(v).upper()),
                kind="stable",
            ).reset_index(drop=True)

        review_rows: list[dict[str, str]] = []
        template_rows: list[dict[str, str]] = []
        learning_rows: list[dict[str, str]] = []

        for _, base in summary_snapshot_df.iterrows():
            seller_sku = _normalize_text(base.get("seller_sku", ""))
            asin = _normalize_text(base.get("asin", ""))
            decision_snapshot_utc = _normalize_text(base.get("decision_snapshot_utc", ""))
            key = (_normalize_key(seller_sku), _normalize_key(asin), decision_snapshot_utc)
            pair_key = (_normalize_key(seller_sku), _normalize_key(asin))
            actuals_row = actuals_index.get(key, {}) or actuals_pair_index.get(pair_key, {})
            existing_row = existing_index.get(key, {}) or existing_pair_index.get(pair_key, {})

            expected_units_30d = _num_or_none(base.get("expected_units_next_30d", ""))
            expected_profit_30d = _num_or_none(base.get("expected_profit_next_30d_gbp", ""))
            actual_units_30d = _num_or_none(actuals_row.get("actual_units_30d", existing_row.get("actual_units_30d", "")))
            actual_profit_30d = _num_or_none(actuals_row.get("actual_profit_30d_gbp", existing_row.get("actual_profit_30d_gbp", "")))
            actual_units_60d = _num_or_none(actuals_row.get("actual_units_60d", existing_row.get("actual_units_60d", "")))
            actual_profit_60d = _num_or_none(actuals_row.get("actual_profit_60d_gbp", existing_row.get("actual_profit_60d_gbp", "")))
            actual_units_90d = _num_or_none(actuals_row.get("actual_units_90d", existing_row.get("actual_units_90d", "")))
            actual_profit_90d = _num_or_none(actuals_row.get("actual_profit_90d_gbp", existing_row.get("actual_profit_90d_gbp", "")))

            operator_outcome = _normalize_outcome(actuals_row.get("learning_outcome", existing_row.get("learning_outcome", "")))
            inferred_outcome, inferred_reason, expected_units_basis, units_error, units_error_ratio, basis_window = _infer_outcome(
                expected_units_30d=expected_units_30d,
                actual_units_30d=actual_units_30d,
                actual_units_60d=actual_units_60d,
                actual_units_90d=actual_units_90d,
            )
            learning_outcome = operator_outcome or inferred_outcome
            learning_reason_codes = _normalize_text(
                actuals_row.get("learning_reason_codes", existing_row.get("learning_reason_codes", ""))
            ) or inferred_reason

            _, actual_units_basis = _select_window(actual_units_30d, actual_units_60d, actual_units_90d)
            if basis_window == 0:
                expected_units_basis = None
                actual_units_basis = None
                units_error = None
                units_error_ratio = None

            operator_check_utc = _normalize_text(actuals_row.get("operator_check_utc", existing_row.get("operator_check_utc", "")))
            operator_notes = _normalize_text(actuals_row.get("operator_notes", existing_row.get("operator_notes", "")))
            purchased_flag = _normalize_text(actuals_row.get("purchased_flag", existing_row.get("purchased_flag", "")))

            common = {
                "observed_utc": snapshot_utc,
                "decision_snapshot_utc": decision_snapshot_utc,
                "seller_sku": seller_sku,
                "asin": asin,
                "amazon_link": _normalize_text(base.get("amazon_link", "")) or _amazon_link(asin),
                "decision_state_at_snapshot": _normalize_decision_state(base.get("decision_state_at_snapshot", "")),
                "decision_confidence_at_snapshot": _normalize_text(base.get("decision_confidence_at_snapshot", "")).lower(),
                "expected_units_next_30d": _num_to_text(expected_units_30d),
                "expected_profit_next_30d_gbp": _num_to_text(expected_profit_30d),
                "actual_units_30d": _num_to_text(actual_units_30d),
                "actual_profit_30d_gbp": _num_to_text(actual_profit_30d),
                "actual_units_60d": _num_to_text(actual_units_60d),
                "actual_profit_60d_gbp": _num_to_text(actual_profit_60d),
                "actual_units_90d": _num_to_text(actual_units_90d),
                "actual_profit_90d_gbp": _num_to_text(actual_profit_90d),
                "outcome_basis_window_days": _num_to_text(float(basis_window) if basis_window else None),
                "expected_units_at_basis_window": _num_to_text(expected_units_basis),
                "actual_units_at_basis_window": _num_to_text(actual_units_basis),
                "units_error_at_basis_window": _num_to_text(units_error),
                "units_error_ratio_at_basis_window": _num_to_text(units_error_ratio),
                "learning_outcome": learning_outcome,
                "learning_reason_codes": learning_reason_codes,
                "operator_check_utc": operator_check_utc,
                "operator_notes": operator_notes,
                "purchased_flag": purchased_flag,
            }
            review_rows.append({column: common.get(column, "") for column in REVIEW_COLUMNS})
            learning_row = {column: common.get(column, "") for column in LEARNING_LOG_COLUMNS}
            learning_row["record_updated_utc"] = snapshot_utc
            learning_rows.append(learning_row)

            template_rows.append(
                {
                    "decision_snapshot_utc": decision_snapshot_utc,
                    "seller_sku": seller_sku,
                    "asin": asin,
                    "amazon_link": _normalize_text(base.get("amazon_link", "")) or _amazon_link(asin),
                    "decision_state_at_snapshot": _normalize_decision_state(base.get("decision_state_at_snapshot", "")),
                    "decision_confidence_at_snapshot": _normalize_text(base.get("decision_confidence_at_snapshot", "")).lower(),
                    "expected_units_next_30d": _num_to_text(expected_units_30d),
                    "expected_profit_next_30d_gbp": _num_to_text(expected_profit_30d),
                    "actual_units_30d": _num_to_text(actual_units_30d),
                    "actual_profit_30d_gbp": _num_to_text(actual_profit_30d),
                    "actual_units_60d": _num_to_text(actual_units_60d),
                    "actual_profit_60d_gbp": _num_to_text(actual_profit_60d),
                    "actual_units_90d": _num_to_text(actual_units_90d),
                    "actual_profit_90d_gbp": _num_to_text(actual_profit_90d),
                    "learning_outcome": _normalize_outcome(actuals_row.get("learning_outcome", "")),
                    "learning_reason_codes": _normalize_text(actuals_row.get("learning_reason_codes", "")),
                    "operator_check_utc": operator_check_utc,
                    "operator_notes": operator_notes,
                    "purchased_flag": purchased_flag,
                }
            )

        review_df = pd.DataFrame(review_rows, columns=REVIEW_COLUMNS)
        review_df = review_df.sort_values(
            by=["decision_snapshot_utc", "asin", "seller_sku"],
            key=lambda s: s.map(lambda v: _normalize_text(v).upper()),
            kind="stable",
        ).reset_index(drop=True)

        template_df = pd.DataFrame(template_rows, columns=ACTUALS_TEMPLATE_COLUMNS)
        template_df = template_df.sort_values(
            by=["decision_snapshot_utc", "asin", "seller_sku"],
            key=lambda s: s.map(lambda v: _normalize_text(v).upper()),
            kind="stable",
        ).reset_index(drop=True)

        incoming_learning_df = pd.DataFrame(learning_rows, columns=LEARNING_LOG_COLUMNS)
        existing_trimmed = existing_learning_df.copy()
        for column in LEARNING_LOG_COLUMNS:
            if column not in existing_trimmed.columns:
                existing_trimmed[column] = ""
        existing_trimmed = existing_trimmed[LEARNING_LOG_COLUMNS]

        combined = pd.concat([existing_trimmed, incoming_learning_df], ignore_index=True)
        combined["_sku"] = combined.get("seller_sku", "").map(_normalize_key)
        combined["_asin"] = combined.get("asin", "").map(_normalize_key)
        combined["_snapshot"] = combined.get("decision_snapshot_utc", "").map(_normalize_text)
        combined["_rank_ts"] = pd.to_datetime(combined.get("record_updated_utc", "").map(_normalize_text), errors="coerce")
        combined = combined.sort_values("_rank_ts", ascending=False, kind="stable")
        combined = combined.drop_duplicates(subset=["_sku", "_asin", "_snapshot"], keep="first")
        combined = combined.drop(columns=["_sku", "_asin", "_snapshot", "_rank_ts"])
        learning_df = combined[LEARNING_LOG_COLUMNS].copy()
        learning_df = learning_df.sort_values(
            by=["decision_snapshot_utc", "asin", "seller_sku"],
            key=lambda s: s.map(lambda v: _normalize_text(v).upper()),
            kind="stable",
        ).reset_index(drop=True)

        health_df = _build_health_df(observed_utc=snapshot_utc, review_df=review_df)

    learning_df.to_csv(learning_path, index=False)
    review_df.to_csv(review_path, index=False)
    review_df.to_csv(review_latest_path, index=False)
    health_df.to_csv(health_path, index=False)
    health_df.to_csv(health_latest_path, index=False)
    template_df.to_csv(template_path, index=False)
    template_df.to_csv(template_latest_path, index=False)

    pending_outcome_rows = int(
        (review_df.get("learning_outcome", "").map(_normalize_outcome) == "pending_outcome").sum()
    ) if not review_df.empty else 0
    print(
        json.dumps(
            {
                "status": "success",
                "observed_utc": snapshot_utc,
                "rows_total": int(len(review_df)),
                "rows_pending_outcome": pending_outcome_rows,
                "learning_live_csv": str(learning_path),
                "review_csv_output": str(review_path),
                "review_latest_csv": str(review_latest_path),
                "health_csv_output": str(health_path),
                "health_latest_csv": str(health_latest_path),
                "template_csv_output": str(template_path),
                "template_latest_csv": str(template_latest_path),
            }
        )
    )

    return SalesHistoryLearningPackResult(
        learning_df=learning_df,
        review_df=review_df,
        health_df=health_df,
        template_df=template_df,
        learning_path=learning_path,
        review_path=review_path,
        review_latest_path=review_latest_path,
        health_path=health_path,
        health_latest_path=health_latest_path,
        template_path=template_path,
        template_latest_path=template_latest_path,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build one-off post-purchase sales-history learning pack from summary assumptions and outcome checks."
        )
    )
    parser.add_argument("--summary-path", default=str(DEFAULT_SUMMARY_PATH))
    parser.add_argument("--actuals-path", default=str(DEFAULT_ACTUALS_PATH))
    parser.add_argument("--alignment-path", default=str(DEFAULT_ALIGNMENT_PATH))
    parser.add_argument("--learning-path", default=str(DEFAULT_LEARNING_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--observed-utc", default=None, help="Override observed_utc in YYYY-MM-DDTHH:MM:SSZ.")
    parser.add_argument(
        "--decision-states",
        default=DEFAULT_DECISION_STATES,
        help="Comma-separated decision states to include from summary (default: pass).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_sales_history_learning_pack(
        summary_path=Path(args.summary_path),
        actuals_path=Path(args.actuals_path),
        alignment_path=Path(args.alignment_path),
        learning_path=Path(args.learning_path),
        output_dir=Path(args.output_dir),
        observed_utc=args.observed_utc,
        decision_states=args.decision_states,
    )


if __name__ == "__main__":
    main()
