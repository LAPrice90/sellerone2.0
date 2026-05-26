from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"
DEFAULT_READINESS_PATH = DEFAULT_OUTPUT_DIR / "f_live_test_readiness_pack_latest.csv"
DEFAULT_ACCURACY_PATH = DEFAULT_OUTPUT_DIR / "f_sales_history_accuracy_pack_latest.csv"
DEFAULT_DECISION_PROFIT_FLOOR_GBP = 20.0
DEFAULT_NEAR_FLOOR_REVIEW_LOWER_GBP = 15.0
DEFAULT_NEAR_FLOOR_REVIEW_UPPER_GBP = 25.0

REVIEW_COLUMNS = [
    "observed_utc",
    "asin",
    "seller_sku",
    "commercial_decision_state",
    "live_test_readiness_state",
    "truth_decision_state",
    "actual_units_30d",
    "actual_profit_30d_gbp",
    "recommendation_status",
    "recommended_test_qty",
    "starter_test_qty_recommended",
    "starter_order_band",
    "demand_consistency_band",
    "sales_lower_30d",
    "sales_upper_30d",
    "rank_snapshot_risk_state",
    "profit_risk_band",
    "negative_mode_truth_state",
    "model_side_evidence_state",
    "first_blocker_code",
    "blocker_codes",
    "blocker_count",
    "profitable_reject_flag",
    "false_red_candidate_flag",
    "recovery_lane_state",
    "recovery_reason",
    "pass_check_tier",
    "expanded_panel_group",
]

PANEL_COLUMNS = [
    "observed_utc",
    "expanded_panel_group",
    "recovery_lane_state",
    "pass_check_tier",
    "asin",
    "seller_sku",
    "commercial_decision_state",
    "truth_decision_state",
    "actual_units_30d",
    "actual_profit_30d_gbp",
    "demand_consistency_band",
    "profit_risk_band",
    "rank_snapshot_risk_state",
    "first_blocker_code",
    "recovery_reason",
]

SUMMARY_COLUMNS = ["observed_utc", "metric", "value"]

BLOCKER_PRIORITY = [
    "blocked_missing_model_decision",
    "blocked_negative_mode",
    "blocked_profit_floor",
    "blocked_rank_risk",
    "blocked_demand_instability",
    "blocked_legacy_recommendation_reject",
    "blocked_zero_starter_qty",
]


@dataclass(frozen=True)
class PassGateReviewResult:
    review_df: pd.DataFrame
    panel_df: pd.DataFrame
    summary_df: pd.DataFrame
    review_path: Path
    review_latest_path: Path
    panel_path: Path
    panel_latest_path: Path
    summary_path: Path
    summary_latest_path: Path
    report: dict[str, Any]


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


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _num_or_none(value: object) -> float | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    cleaned = raw.replace(",", "").replace("GBP", "").replace("gbp", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _num_to_text(value: float | int | None) -> str:
    if value is None:
        return ""
    as_float = float(value)
    if as_float.is_integer():
        return str(int(as_float))
    return f"{as_float:.6f}".rstrip("0").rstrip(".")


def _int_or_none(value: object) -> int | None:
    num = _num_or_none(value)
    if num is None:
        return None
    return int(round(num))


def _latest_accuracy_by_asin(accuracy_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    if accuracy_df.empty or "asin" not in accuracy_df.columns:
        return {}
    work = accuracy_df.copy()
    work["_asin_key"] = work.get("asin", "").map(_normalize_key)
    work = work[work["_asin_key"] != ""].copy()
    if work.empty:
        return {}
    if "observed_utc" in work.columns:
        work["_obs_ts"] = pd.to_datetime(work.get("observed_utc", "").map(_normalize_text), errors="coerce", utc=True)
        work = work.sort_values("_obs_ts", ascending=False, kind="stable")

    out: dict[str, dict[str, str]] = {}
    for _, row in work.iterrows():
        asin = _normalize_key(row.get("_asin_key", ""))
        if asin == "" or asin in out:
            continue
        out[asin] = {column: _normalize_text(value) for column, value in row.to_dict().items()}
    return out


def _blocker_codes(
    *,
    commercial_decision_state: str,
    recommendation_status: str,
    starter_order_band: str,
    starter_qty: int | None,
    demand_consistency_band: str,
    profit_risk_band: str,
    negative_mode_truth_state: str,
    rank_snapshot_risk_state: str,
    model_side_evidence_state: str,
) -> list[str]:
    if commercial_decision_state == "test_buy":
        return []

    codes: list[str] = []
    if model_side_evidence_state != "full_decision_and_estimate" or recommendation_status == "":
        codes.append("blocked_missing_model_decision")
    if negative_mode_truth_state == "negative_mode_active":
        codes.append("blocked_negative_mode")
    if profit_risk_band in {"negative", "near_floor", "unknown"}:
        codes.append("blocked_profit_floor")
    if rank_snapshot_risk_state in {"high_rank_risk", "untrusted_rank_window"}:
        codes.append("blocked_rank_risk")
    if demand_consistency_band == "unstable":
        codes.append("blocked_demand_instability")
    if recommendation_status == "reject":
        codes.append("blocked_legacy_recommendation_reject")
    if starter_order_band == "hold" or starter_qty is None or starter_qty <= 0:
        codes.append("blocked_zero_starter_qty")
    if not codes:
        codes.append("blocked_other")
    return codes


def _first_blocker_code(codes: list[str]) -> str:
    for token in BLOCKER_PRIORITY:
        if token in codes:
            return token
    if codes:
        return codes[0]
    return ""


def _is_profitable_reject(
    *,
    commercial_decision_state: str,
    actual_profit_30d: float | None,
    decision_profit_floor_gbp: float,
) -> bool:
    if commercial_decision_state != "reject":
        return False
    if actual_profit_30d is None:
        return False
    return actual_profit_30d >= decision_profit_floor_gbp


def _is_false_red_candidate(
    *,
    profitable_reject_flag: bool,
    negative_mode_truth_state: str,
    profit_risk_band: str,
    rank_snapshot_risk_state: str,
    first_blocker_code: str,
) -> bool:
    if not profitable_reject_flag:
        return False
    if negative_mode_truth_state != "negative_mode_clear":
        return False
    if profit_risk_band not in {"healthy", "strong"}:
        return False
    if rank_snapshot_risk_state not in {"low_rank_risk", "moderate_rank_risk"}:
        return False
    return first_blocker_code in {"blocked_legacy_recommendation_reject", "blocked_zero_starter_qty"}


def _recovery_lane(
    *,
    commercial_decision_state: str,
    profitable_reject_flag: bool,
    false_red_candidate_flag: bool,
    profit_risk_band: str,
    demand_consistency_band: str,
    rank_snapshot_risk_state: str,
    first_blocker_code: str,
) -> tuple[str, str]:
    if commercial_decision_state == "test_buy":
        return "current_test_buy", "already_live_test_ready"
    if commercial_decision_state == "watch":
        return "current_watch", "already_in_watch_lane"

    if false_red_candidate_flag:
        if (
            profit_risk_band == "strong"
            and demand_consistency_band == "stable"
            and rank_snapshot_risk_state == "low_rank_risk"
        ):
            return "promote_to_test_buy", "strong_profit_stable_demand_rank_safe"
        return "promote_to_watch", "profit_rank_safe_but_needs_second_pass_review"

    if profitable_reject_flag and first_blocker_code in {
        "blocked_demand_instability",
        "blocked_rank_risk",
    }:
        return "review_only_profitable_reject", "profit_is_good_but_primary_blocker_still_needs_manual_judgement"

    return "keep_reject", "current_blocker_not_recoverable_in_second_pass"


def _pass_check_tier(recovery_lane_state: str, profitable_reject_flag: bool) -> str:
    if recovery_lane_state in {"current_test_buy", "promote_to_test_buy"}:
        return "tier_a"
    if recovery_lane_state in {"current_watch", "promote_to_watch"}:
        return "tier_b"
    if profitable_reject_flag or recovery_lane_state == "review_only_profitable_reject":
        return "tier_c"
    return "tier_d"


def _expanded_panel_group(
    *,
    recovery_lane_state: str,
    actual_profit_30d: float | None,
    near_floor_review_lower_gbp: float,
    near_floor_review_upper_gbp: float,
    profitable_reject_flag: bool,
) -> str:
    if recovery_lane_state == "current_test_buy":
        return "current_test_buy"
    if recovery_lane_state == "current_watch":
        return "current_watch"
    if profitable_reject_flag:
        return "profitable_reject_gbp20_plus"
    if actual_profit_30d is not None and near_floor_review_lower_gbp <= actual_profit_30d <= near_floor_review_upper_gbp:
        return "near_floor_review"
    return ""


def build_pass_gate_review_pack(
    *,
    readiness_path: Path = DEFAULT_READINESS_PATH,
    accuracy_path: Path = DEFAULT_ACCURACY_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    decision_profit_floor_gbp: float = DEFAULT_DECISION_PROFIT_FLOOR_GBP,
    near_floor_review_lower_gbp: float = DEFAULT_NEAR_FLOOR_REVIEW_LOWER_GBP,
    near_floor_review_upper_gbp: float = DEFAULT_NEAR_FLOOR_REVIEW_UPPER_GBP,
    observed_utc: str | None = None,
) -> PassGateReviewResult:
    snapshot_utc = observed_utc or _utc_now_iso()
    ts_slug = _to_timestamp_slug(snapshot_utc)
    output_dir.mkdir(parents=True, exist_ok=True)

    review_path = output_dir / f"f_pass_gate_review_pack_{ts_slug}.csv"
    review_latest_path = output_dir / "f_pass_gate_review_pack_latest.csv"
    panel_path = output_dir / f"f_pass_gate_review_panel_{ts_slug}.csv"
    panel_latest_path = output_dir / "f_pass_gate_review_panel_latest.csv"
    summary_path = output_dir / f"f_pass_gate_review_summary_{ts_slug}.csv"
    summary_latest_path = output_dir / "f_pass_gate_review_summary_latest.csv"

    readiness_df = _read_csv(readiness_path)
    accuracy_df = _read_csv(accuracy_path)
    accuracy_by_asin = _latest_accuracy_by_asin(accuracy_df)

    rows: list[dict[str, str]] = []
    for _, row in readiness_df.iterrows():
        asin = _normalize_key(row.get("asin", ""))
        if asin == "":
            continue

        accuracy_row = accuracy_by_asin.get(asin, {})
        seller_sku = _normalize_text(row.get("seller_sku", ""))
        commercial_decision_state = _normalize_text(row.get("commercial_decision_state", ""))
        recommendation_status = _normalize_text(row.get("recommendation_status", "")).lower()
        starter_order_band = _normalize_text(row.get("starter_order_band", ""))
        starter_qty = _int_or_none(row.get("starter_test_qty_recommended", ""))
        demand_consistency_band = _normalize_text(row.get("demand_consistency_band", ""))
        profit_risk_band = _normalize_text(row.get("profit_risk_band", ""))
        negative_mode_truth_state = _normalize_text(row.get("negative_mode_truth_state", ""))
        rank_snapshot_risk_state = _normalize_text(row.get("rank_snapshot_risk_state", ""))
        model_side_evidence_state = _normalize_text(accuracy_row.get("model_side_evidence_state", ""))
        actual_profit_30d = _num_or_none(row.get("actual_profit_30d_gbp", ""))

        blocker_codes = _blocker_codes(
            commercial_decision_state=commercial_decision_state,
            recommendation_status=recommendation_status,
            starter_order_band=starter_order_band,
            starter_qty=starter_qty,
            demand_consistency_band=demand_consistency_band,
            profit_risk_band=profit_risk_band,
            negative_mode_truth_state=negative_mode_truth_state,
            rank_snapshot_risk_state=rank_snapshot_risk_state,
            model_side_evidence_state=model_side_evidence_state,
        )
        first_blocker_code = _first_blocker_code(blocker_codes)
        profitable_reject_flag = _is_profitable_reject(
            commercial_decision_state=commercial_decision_state,
            actual_profit_30d=actual_profit_30d,
            decision_profit_floor_gbp=decision_profit_floor_gbp,
        )
        false_red_candidate_flag = _is_false_red_candidate(
            profitable_reject_flag=profitable_reject_flag,
            negative_mode_truth_state=negative_mode_truth_state,
            profit_risk_band=profit_risk_band,
            rank_snapshot_risk_state=rank_snapshot_risk_state,
            first_blocker_code=first_blocker_code,
        )
        recovery_lane_state, recovery_reason = _recovery_lane(
            commercial_decision_state=commercial_decision_state,
            profitable_reject_flag=profitable_reject_flag,
            false_red_candidate_flag=false_red_candidate_flag,
            profit_risk_band=profit_risk_band,
            demand_consistency_band=demand_consistency_band,
            rank_snapshot_risk_state=rank_snapshot_risk_state,
            first_blocker_code=first_blocker_code,
        )
        pass_check_tier = _pass_check_tier(recovery_lane_state, profitable_reject_flag)
        expanded_panel_group = _expanded_panel_group(
            recovery_lane_state=recovery_lane_state,
            actual_profit_30d=actual_profit_30d,
            near_floor_review_lower_gbp=near_floor_review_lower_gbp,
            near_floor_review_upper_gbp=near_floor_review_upper_gbp,
            profitable_reject_flag=profitable_reject_flag,
        )

        rows.append(
            {
                "observed_utc": snapshot_utc,
                "asin": asin,
                "seller_sku": seller_sku,
                "commercial_decision_state": commercial_decision_state,
                "live_test_readiness_state": _normalize_text(row.get("live_test_readiness_state", "")),
                "truth_decision_state": _normalize_text(row.get("truth_decision_state", "")),
                "actual_units_30d": _normalize_text(row.get("actual_units_30d", "")),
                "actual_profit_30d_gbp": _normalize_text(row.get("actual_profit_30d_gbp", "")),
                "recommendation_status": recommendation_status,
                "recommended_test_qty": _normalize_text(row.get("recommended_test_qty", "")),
                "starter_test_qty_recommended": _normalize_text(row.get("starter_test_qty_recommended", "")),
                "starter_order_band": starter_order_band,
                "demand_consistency_band": demand_consistency_band,
                "sales_lower_30d": _normalize_text(row.get("sales_lower_30d", "")),
                "sales_upper_30d": _normalize_text(row.get("sales_upper_30d", "")),
                "rank_snapshot_risk_state": rank_snapshot_risk_state,
                "profit_risk_band": profit_risk_band,
                "negative_mode_truth_state": negative_mode_truth_state,
                "model_side_evidence_state": model_side_evidence_state,
                "first_blocker_code": first_blocker_code,
                "blocker_codes": "|".join(blocker_codes),
                "blocker_count": str(len(blocker_codes)),
                "profitable_reject_flag": "1" if profitable_reject_flag else "0",
                "false_red_candidate_flag": "1" if false_red_candidate_flag else "0",
                "recovery_lane_state": recovery_lane_state,
                "recovery_reason": recovery_reason,
                "pass_check_tier": pass_check_tier,
                "expanded_panel_group": expanded_panel_group,
            }
        )

    review_df = pd.DataFrame(rows, columns=REVIEW_COLUMNS).fillna("")
    if not review_df.empty:
        review_df = review_df.sort_values(
            by=["pass_check_tier", "recovery_lane_state", "first_blocker_code", "asin"],
            ascending=[True, True, True, True],
            kind="stable",
        ).reset_index(drop=True)

    panel_df = review_df.loc[
        review_df.get("expanded_panel_group", pd.Series(dtype=str)).map(_normalize_text) != "",
        PANEL_COLUMNS,
    ].copy()
    if not panel_df.empty:
        panel_df = panel_df.sort_values(
            by=["expanded_panel_group", "pass_check_tier", "actual_profit_30d_gbp", "asin"],
            ascending=[True, True, False, True],
            kind="stable",
        ).reset_index(drop=True)

    summary_rows = [
        {"observed_utc": snapshot_utc, "metric": "rows_total", "value": str(int(len(review_df.index)))},
        {
            "observed_utc": snapshot_utc,
            "metric": "current_test_buy_rows",
            "value": str(int((review_df.get("recovery_lane_state", pd.Series(dtype=str)) == "current_test_buy").sum())),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "current_watch_rows",
            "value": str(int((review_df.get("recovery_lane_state", pd.Series(dtype=str)) == "current_watch").sum())),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "profitable_reject_rows",
            "value": str(int((review_df.get("profitable_reject_flag", pd.Series(dtype=str)) == "1").sum())),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "false_red_candidate_rows",
            "value": str(int((review_df.get("false_red_candidate_flag", pd.Series(dtype=str)) == "1").sum())),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "promote_to_test_buy_rows",
            "value": str(int((review_df.get("recovery_lane_state", pd.Series(dtype=str)) == "promote_to_test_buy").sum())),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "promote_to_watch_rows",
            "value": str(int((review_df.get("recovery_lane_state", pd.Series(dtype=str)) == "promote_to_watch").sum())),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "review_only_profitable_reject_rows",
            "value": str(
                int((review_df.get("recovery_lane_state", pd.Series(dtype=str)) == "review_only_profitable_reject").sum())
            ),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "keep_reject_rows",
            "value": str(int((review_df.get("recovery_lane_state", pd.Series(dtype=str)) == "keep_reject").sum())),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "tier_a_rows",
            "value": str(int((review_df.get("pass_check_tier", pd.Series(dtype=str)) == "tier_a").sum())),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "tier_b_rows",
            "value": str(int((review_df.get("pass_check_tier", pd.Series(dtype=str)) == "tier_b").sum())),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "tier_c_rows",
            "value": str(int((review_df.get("pass_check_tier", pd.Series(dtype=str)) == "tier_c").sum())),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "tier_d_rows",
            "value": str(int((review_df.get("pass_check_tier", pd.Series(dtype=str)) == "tier_d").sum())),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "expanded_panel_rows_total",
            "value": str(int(len(panel_df.index))),
        },
    ]

    for blocker_code in BLOCKER_PRIORITY + ["blocked_other"]:
        summary_rows.append(
            {
                "observed_utc": snapshot_utc,
                "metric": f"blocker::{blocker_code}",
                "value": str(
                    int(
                        review_df.get("blocker_codes", pd.Series(dtype=str))
                        .map(lambda raw: blocker_code in _normalize_text(raw).split("|"))
                        .sum()
                    )
                ),
            }
        )

    for panel_group in [
        "current_test_buy",
        "current_watch",
        "profitable_reject_gbp20_plus",
        "near_floor_review",
    ]:
        summary_rows.append(
            {
                "observed_utc": snapshot_utc,
                "metric": f"expanded_panel::{panel_group}",
                "value": str(
                    int((panel_df.get("expanded_panel_group", pd.Series(dtype=str)).map(_normalize_text) == panel_group).sum())
                ),
            }
        )

    summary_df = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS)

    review_df.to_csv(review_path, index=False)
    review_df.to_csv(review_latest_path, index=False)
    panel_df.to_csv(panel_path, index=False)
    panel_df.to_csv(panel_latest_path, index=False)
    summary_df.to_csv(summary_path, index=False)
    summary_df.to_csv(summary_latest_path, index=False)

    report = {
        "rows_total": int(len(review_df.index)),
        "false_red_candidate_rows": int((review_df.get("false_red_candidate_flag", pd.Series(dtype=str)) == "1").sum()),
        "promote_to_test_buy_rows": int(
            (review_df.get("recovery_lane_state", pd.Series(dtype=str)) == "promote_to_test_buy").sum()
        ),
        "promote_to_watch_rows": int(
            (review_df.get("recovery_lane_state", pd.Series(dtype=str)) == "promote_to_watch").sum()
        ),
        "expanded_panel_rows_total": int(len(panel_df.index)),
    }

    return PassGateReviewResult(
        review_df=review_df,
        panel_df=panel_df,
        summary_df=summary_df,
        review_path=review_path,
        review_latest_path=review_latest_path,
        panel_path=panel_path,
        panel_latest_path=panel_latest_path,
        summary_path=summary_path,
        summary_latest_path=summary_latest_path,
        report=report,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build pass-gate decomposition and false-red recovery review pack.")
    parser.add_argument("--readiness-path", default=str(DEFAULT_READINESS_PATH))
    parser.add_argument("--accuracy-path", default=str(DEFAULT_ACCURACY_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--decision-profit-floor-gbp", type=float, default=DEFAULT_DECISION_PROFIT_FLOOR_GBP)
    parser.add_argument("--near-floor-review-lower-gbp", type=float, default=DEFAULT_NEAR_FLOOR_REVIEW_LOWER_GBP)
    parser.add_argument("--near-floor-review-upper-gbp", type=float, default=DEFAULT_NEAR_FLOOR_REVIEW_UPPER_GBP)
    parser.add_argument("--observed-utc", default="")
    args = parser.parse_args()

    result = build_pass_gate_review_pack(
        readiness_path=Path(args.readiness_path),
        accuracy_path=Path(args.accuracy_path),
        output_dir=Path(args.output_dir),
        decision_profit_floor_gbp=float(args.decision_profit_floor_gbp),
        near_floor_review_lower_gbp=float(args.near_floor_review_lower_gbp),
        near_floor_review_upper_gbp=float(args.near_floor_review_upper_gbp),
        observed_utc=args.observed_utc or None,
    )
    print(
        json.dumps(
            {
                "review_path": str(result.review_path),
                "rows_total": int(len(result.review_df.index)),
                "summary_path": str(result.summary_path),
                "panel_path": str(result.panel_path),
                "report": result.report,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
