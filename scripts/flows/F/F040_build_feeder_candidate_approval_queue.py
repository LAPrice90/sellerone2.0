from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.flows.F._contract_io import write_f_contract_df
from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract
from scripts.flows.F._schemas import get_f_output_column_types, get_f_output_contract
from scripts.flows.F._source_contracts import get_source_contract


DEFAULT_INPUT_REL_PATH = get_source_contract("feeder_shared_pass_logic_live").source_path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_lower(value: object) -> str:
    return _normalize_text(value).lower()


def _normalize_digits(value: object) -> str:
    return "".join(ch for ch in _normalize_text(value) if ch.isdigit())


def _parse_positive_float(value: object) -> float | None:
    raw = _normalize_text(value).replace(",", "")
    if raw == "":
        return None
    try:
        num = float(raw)
    except ValueError:
        return None
    if num <= 0:
        return None
    return num


def _contract_columns(contract_name: str) -> list[str]:
    contract = get_f_output_contract(contract_name)
    return [*contract.required_columns, *contract.optional_columns]


def _empty_contract_df(contract_name: str) -> pd.DataFrame:
    return pd.DataFrame(columns=_contract_columns(contract_name))


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


def _read_contract_df(contract_name: str, root_path: Path) -> pd.DataFrame:
    path = root_path / get_f_output_contract(contract_name).rel_path
    if not path.exists():
        return _empty_contract_df(contract_name)
    return pd.read_csv(path, dtype=str).fillna("")


def _source_missing_health_rows(observed_utc: str, source_path: Path) -> list[dict[str, str]]:
    return [
        {
            "check": "feeder_approval_source_contract",
            "status": "warn",
            "value": "0",
            "notes": "feeder_shared_pass_logic_live_missing",
            "observed_utc": observed_utc,
            "source_path": str(source_path),
        },
        {
            "check": "feeder_approval_quality",
            "status": "warn",
            "value": "0",
            "notes": "no_rows_processed",
            "observed_utc": observed_utc,
            "source_path": str(source_path),
        },
        {
            "check": "feeder_approval_manual_review_pressure",
            "status": "warn",
            "value": "0",
            "notes": "manual_review_ratio=0.00",
            "observed_utc": observed_utc,
            "source_path": str(source_path),
        },
    ]


def _estimate_roi_pct(cost: float) -> float:
    if cost <= 5:
        return 60.0
    if cost <= 20:
        return 35.0
    if cost <= 60:
        return 20.0
    if cost <= 120:
        return 14.0
    if cost <= 180:
        return 9.0
    return 6.0


def _estimate_demand(title: str, barcode: str) -> str:
    has_barcode = _normalize_digits(barcode) != ""
    title_len = len(_normalize_text(title))
    if has_barcode and title_len >= 16:
        return "high"
    if has_barcode or title_len >= 10:
        return "medium"
    return "low"


def _recommend_qty(demand: str, recommendation_status: str) -> int:
    if recommendation_status == "approve_test_buy":
        if demand == "high":
            return 8
        if demand == "medium":
            return 5
        return 3
    if recommendation_status == "watch":
        return 1
    return 0


def _build_recommendation_row(row: pd.Series, recommendation_utc: str) -> dict[str, str]:
    feeder_candidate_id = _normalize_text(row.get("feeder_candidate_id", ""))
    pass_logic_status = _normalize_lower(row.get("pass_logic_status", ""))
    pass_logic_reason_codes = _normalize_text(row.get("pass_logic_reason_codes", ""))
    supplier_title = _normalize_text(row.get("supplier_title", ""))
    barcode = _normalize_digits(row.get("barcode", ""))
    cost_num = _parse_positive_float(row.get("unit_cost", ""))

    viability_status = "review"
    recommendation_status = "manual_review"
    viability_reasons: list[str] = []
    recommendation_reasons: list[str] = []

    estimated_demand = _estimate_demand(supplier_title, barcode)
    estimated_roi_pct = ""
    estimated_margin_gbp = ""

    if pass_logic_status == "hold":
        viability_status = "non_viable"
        recommendation_status = "reject"
        viability_reasons.append("pass_logic_hold")
        recommendation_reasons.append("reject_upstream_hold")
    elif pass_logic_status == "manual_review":
        viability_status = "review"
        recommendation_status = "manual_review"
        viability_reasons.append("pass_logic_manual_review")
        recommendation_reasons.append("manual_review_upstream")
    elif cost_num is None:
        viability_status = "review"
        recommendation_status = "manual_review"
        viability_reasons.append("missing_cost")
        recommendation_reasons.append("manual_review_missing_cost")
    elif cost_num > 220:
        viability_status = "non_viable"
        recommendation_status = "reject"
        viability_reasons.append("cost_above_limit")
        recommendation_reasons.append("reject_cost_above_limit")
    else:
        roi_num = _estimate_roi_pct(cost_num)
        margin_num = round(cost_num * (roi_num / 100.0), 2)
        estimated_roi_pct = f"{roi_num:.2f}"
        estimated_margin_gbp = f"{margin_num:.2f}"
        if roi_num < 10:
            viability_status = "borderline"
            recommendation_status = "watch"
            viability_reasons.append("low_roi")
            recommendation_reasons.append("watch_low_roi")
        else:
            viability_status = "viable"
            recommendation_status = "approve_test_buy"
            viability_reasons.append("baseline_viable")
            recommendation_reasons.append("approve_baseline_viable")

    if pass_logic_reason_codes != "":
        viability_reasons.append(f"upstream:{pass_logic_reason_codes}")

    qty = _recommend_qty(estimated_demand, recommendation_status)
    approval_required = "1"

    return {
        "candidate_id": feeder_candidate_id,
        "feeder_candidate_id": feeder_candidate_id,
        "supplier_id": _normalize_text(row.get("supplier_id", "")),
        "supplier_name": _normalize_text(row.get("supplier_name", "")),
        "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
        "supplier_title": supplier_title,
        "barcode": barcode,
        "unit_cost": "" if cost_num is None else f"{cost_num:.2f}",
        "currency": _normalize_text(row.get("currency", "")),
        "vat_rate": _normalize_text(row.get("vat_rate", "")),
        "viability_status": viability_status,
        "viability_reason_codes": "|".join(viability_reasons),
        "estimated_demand": estimated_demand,
        "estimated_roi_pct": estimated_roi_pct,
        "estimated_margin_gbp": estimated_margin_gbp,
        "recommended_test_qty": str(qty),
        "recommendation_status": recommendation_status,
        "recommendation_reason_codes": "|".join(recommendation_reasons),
        "approval_required_flag": approval_required,
        "decision_status": "pending_review",
        "recommendation_utc": recommendation_utc,
        "source_row_hash": _normalize_text(row.get("source_row_hash", "")),
        "source_file_path": _normalize_text(row.get("source_file_path", "")),
        "source_seen_at_utc": _normalize_text(row.get("source_seen_at_utc", "")),
        "source_url": _normalize_text(row.get("source_url", "")),
        "pass_logic_status": pass_logic_status,
        "pass_logic_reason_codes": pass_logic_reason_codes,
        "notes": "",
    }


def _build_queue_row(recommendation_row: dict[str, str], queue_utc: str) -> dict[str, str]:
    recommendation_status = recommendation_row.get("recommendation_status", "")
    queue_status_map = {
        "approve_test_buy": "needs_review",
        "reject": "needs_review",
        "watch": "watch",
        "manual_review": "manual_review",
    }
    queue_status = queue_status_map.get(recommendation_status, "needs_review")
    return {
        "queue_utc": queue_utc,
        "candidate_id": recommendation_row.get("candidate_id", ""),
        "feeder_candidate_id": recommendation_row.get("feeder_candidate_id", ""),
        "supplier_id": recommendation_row.get("supplier_id", ""),
        "supplier_name": recommendation_row.get("supplier_name", ""),
        "supplier_sku": recommendation_row.get("supplier_sku", ""),
        "supplier_title": recommendation_row.get("supplier_title", ""),
        "recommendation_status": recommendation_status,
        "recommended_test_qty": recommendation_row.get("recommended_test_qty", ""),
        "queue_status": queue_status,
        "decision_status": recommendation_row.get("decision_status", ""),
        "approval_required_flag": recommendation_row.get("approval_required_flag", ""),
        "owner": "feeder_operator",
        "snooze_until_utc": "",
        "source_row_hash": recommendation_row.get("source_row_hash", ""),
        "source_file_path": recommendation_row.get("source_file_path", ""),
        "source_seen_at_utc": recommendation_row.get("source_seen_at_utc", ""),
        "estimated_roi_pct": recommendation_row.get("estimated_roi_pct", ""),
        "estimated_margin_gbp": recommendation_row.get("estimated_margin_gbp", ""),
        "estimated_demand": recommendation_row.get("estimated_demand", ""),
        "recommendation_reason_codes": recommendation_row.get("recommendation_reason_codes", ""),
        "notes": "",
    }


def _build_seed_decision_row(recommendation_row: dict[str, str], decision_utc: str) -> dict[str, str]:
    candidate_id = recommendation_row.get("candidate_id", "")
    decision_action = "seed_pending_review"
    final_decision_status = "pending_review"
    event_key = "|".join([candidate_id, decision_action, final_decision_status])
    event_id = hashlib.sha1(event_key.encode("utf-8")).hexdigest()[:16]
    return {
        "decision_utc": decision_utc,
        "event_id": f"FDEC-{event_id}",
        "candidate_id": candidate_id,
        "feeder_candidate_id": recommendation_row.get("feeder_candidate_id", ""),
        "decision_action": decision_action,
        "final_decision_status": final_decision_status,
        "decision_source": "system_seed",
        "recommendation_status": recommendation_row.get("recommendation_status", ""),
        "recommended_test_qty": recommendation_row.get("recommended_test_qty", ""),
        "actor": "system",
        "decision_note": "initial_pending_review_seed",
        "source_row_hash": recommendation_row.get("source_row_hash", ""),
        "source_file_path": recommendation_row.get("source_file_path", ""),
        "source_seen_at_utc": recommendation_row.get("source_seen_at_utc", ""),
        "supplier_id": recommendation_row.get("supplier_id", ""),
        "supplier_sku": recommendation_row.get("supplier_sku", ""),
    }


def build_feeder_candidate_approval_queue(
    root: Path | None = None,
    *,
    input_rel_path: str | None = None,
    recommendation_utc: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)

    source_contract = get_source_contract("feeder_shared_pass_logic_live")
    source_path = root_path / (input_rel_path or source_contract.source_path)
    observed_utc = recommendation_utc or _utc_now_iso()

    if not source_path.exists():
        rec_df = _write_contract_df(_empty_contract_df("feeder_candidate_recommendations_live"), "feeder_candidate_recommendations_live", root_path)
        queue_df = _write_contract_df(_empty_contract_df("feeder_approval_queue_live"), "feeder_approval_queue_live", root_path)
        decisions_df = _write_contract_df(_empty_contract_df("feeder_approval_decisions_log"), "feeder_approval_decisions_log", root_path)
        health_df = _write_contract_df(
            pd.DataFrame(_source_missing_health_rows(observed_utc, source_path)),
            "feeder_approval_health",
            root_path,
        )
        print(
            {
                "status": "success",
                "source_rows": 0,
                "recommendation_rows": 0,
                "queue_rows": 0,
                "decision_log_rows": int(len(decisions_df)),
                "notes": "source file missing; emitted warn health state",
            }
        )
        return rec_df, queue_df, decisions_df, health_df

    source_df = pd.read_csv(source_path, dtype=str).fillna("")
    missing_columns = [column for column in source_contract.required_columns if column not in source_df.columns]
    if missing_columns:
        rec_df = _write_contract_df(_empty_contract_df("feeder_candidate_recommendations_live"), "feeder_candidate_recommendations_live", root_path)
        queue_df = _write_contract_df(_empty_contract_df("feeder_approval_queue_live"), "feeder_approval_queue_live", root_path)
        decisions_df = _write_contract_df(_empty_contract_df("feeder_approval_decisions_log"), "feeder_approval_decisions_log", root_path)
        missing_text = "|".join(missing_columns)
        health_df = _write_contract_df(
            pd.DataFrame(
                [
                    {
                        "check": "feeder_approval_source_contract",
                        "status": "fail",
                        "value": str(len(missing_columns)),
                        "notes": f"missing_columns:{missing_text}",
                        "observed_utc": observed_utc,
                        "source_path": str(source_path),
                    },
                    {
                        "check": "feeder_approval_quality",
                        "status": "fail",
                        "value": "0",
                        "notes": "no_rows_processed_due_to_contract_failure",
                        "observed_utc": observed_utc,
                        "source_path": str(source_path),
                    },
                    {
                        "check": "feeder_approval_manual_review_pressure",
                        "status": "warn",
                        "value": "0",
                        "notes": "manual_review_ratio=0.00",
                        "observed_utc": observed_utc,
                        "source_path": str(source_path),
                    },
                ]
            ),
            "feeder_approval_health",
            root_path,
        )
        print(
            {
                "status": "success",
                "source_rows": int(len(source_df)),
                "recommendation_rows": 0,
                "queue_rows": 0,
                "decision_log_rows": int(len(decisions_df)),
                "notes": f"source contract failed: {missing_text}",
            }
        )
        return rec_df, queue_df, decisions_df, health_df

    recommendation_rows = [_build_recommendation_row(row, observed_utc) for _, row in source_df.iterrows()]
    queue_rows = [_build_queue_row(row, observed_utc) for row in recommendation_rows]
    seed_decision_rows = [_build_seed_decision_row(row, observed_utc) for row in recommendation_rows]

    rec_df = _write_contract_df(pd.DataFrame(recommendation_rows), "feeder_candidate_recommendations_live", root_path)
    queue_df = _write_contract_df(pd.DataFrame(queue_rows), "feeder_approval_queue_live", root_path)

    existing_decisions = _read_contract_df("feeder_approval_decisions_log", root_path)
    existing_keys = set(
        (
            existing_decisions.get("candidate_id", "").map(_normalize_text)
            + "|"
            + existing_decisions.get("decision_action", "").map(_normalize_text)
            + "|"
            + existing_decisions.get("final_decision_status", "").map(_normalize_text)
        ).tolist()
    ) if not existing_decisions.empty else set()

    append_rows: list[dict[str, str]] = []
    for decision in seed_decision_rows:
        key = "|".join(
            [
                _normalize_text(decision.get("candidate_id", "")),
                _normalize_text(decision.get("decision_action", "")),
                _normalize_text(decision.get("final_decision_status", "")),
            ]
        )
        if key not in existing_keys:
            append_rows.append(decision)
            existing_keys.add(key)

    decisions_combined = existing_decisions
    if append_rows:
        decisions_combined = pd.concat([existing_decisions, pd.DataFrame(append_rows)], ignore_index=True)
    decisions_df = _write_contract_df(decisions_combined, "feeder_approval_decisions_log", root_path)

    recommendation_rows_count = int(len(rec_df))
    manual_count = int((rec_df["recommendation_status"] == "manual_review").sum()) if recommendation_rows_count else 0
    hold_like_count = int((rec_df["recommendation_status"] == "reject").sum()) if recommendation_rows_count else 0
    approve_count = int((rec_df["recommendation_status"] == "approve_test_buy").sum()) if recommendation_rows_count else 0

    source_status = "ok"
    quality_status = "ok"
    quality_notes = (
        f"approve_rows={approve_count};manual_review_rows={manual_count};"
        f"reject_rows={hold_like_count};source_rows={len(source_df)}"
    )
    if recommendation_rows_count == 0:
        quality_status = "warn"
        quality_notes = "no_rows_recommended"
    elif approve_count == 0:
        quality_status = "warn"
        quality_notes = (
            f"no_approve_rows;manual_review_rows={manual_count};"
            f"reject_rows={hold_like_count};source_rows={len(source_df)}"
        )

    manual_ratio = (manual_count / recommendation_rows_count) if recommendation_rows_count else 0.0
    manual_pressure_status = "ok"
    if recommendation_rows_count == 0:
        manual_pressure_status = "warn"
    elif manual_ratio >= 0.25:
        manual_pressure_status = "warn"

    health_df = _write_contract_df(
        pd.DataFrame(
            [
                {
                    "check": "feeder_approval_source_contract",
                    "status": source_status,
                    "value": str(len(source_df)),
                    "notes": "feeder_shared_pass_logic_contract_valid",
                    "observed_utc": observed_utc,
                    "source_path": str(source_path),
                },
                {
                    "check": "feeder_approval_quality",
                    "status": quality_status,
                    "value": str(recommendation_rows_count),
                    "notes": quality_notes,
                    "observed_utc": observed_utc,
                    "source_path": str(source_path),
                },
                {
                    "check": "feeder_approval_manual_review_pressure",
                    "status": manual_pressure_status,
                    "value": str(manual_count),
                    "notes": f"manual_review_ratio={manual_ratio:.2f}",
                    "observed_utc": observed_utc,
                    "source_path": str(source_path),
                },
            ]
        ),
        "feeder_approval_health",
        root_path,
    )

    print(
        {
            "status": "success",
            "source_rows": int(len(source_df)),
            "recommendation_rows": recommendation_rows_count,
            "queue_rows": int(len(queue_df)),
            "decision_log_rows": int(len(decisions_df)),
            "approve_rows": approve_count,
            "manual_review_rows": manual_count,
            "reject_rows": hold_like_count,
            "health_quality_status": quality_status,
        }
    )
    return rec_df, queue_df, decisions_df, health_df


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build feeder candidate recommendations and approval queue from shared pass-logic output."
    )
    parser.add_argument("--root", default=None)
    parser.add_argument("--input-rel-path", default=None)
    parser.add_argument("--recommendation-utc", default=None)
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    build_feeder_candidate_approval_queue(
        root=root,
        input_rel_path=args.input_rel_path,
        recommendation_utc=args.recommendation_utc,
    )


if __name__ == "__main__":
    main()
