from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.flows.F._contract_io import write_f_contract_df
from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract
from scripts.flows.F._schemas import get_f_output_column_types, get_f_output_contract
from scripts.flows.F._source_contracts import get_source_contract


APPROVAL_STATUSES = {"approved", "approved_for_test_buy", "approved_for_po", "approved_test_buy"}


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


def _parse_positive_int(value: object) -> int | None:
    raw = _normalize_text(value).replace(",", "")
    if raw == "":
        return None
    try:
        num = int(float(raw))
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


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _source_missing_health_rows(observed_utc: str, queue_path: Path, decisions_path: Path) -> list[dict[str, str]]:
    notes = []
    if not queue_path.exists():
        notes.append("approval_queue_missing")
    if not decisions_path.exists():
        notes.append("decision_log_missing")
    note_text = "|".join(notes) if notes else "source_missing"
    return [
        {
            "check": "feeder_po_handoff_source_contract",
            "status": "warn",
            "value": "0",
            "notes": note_text,
            "observed_utc": observed_utc,
            "source_path": str(queue_path),
        },
        {
            "check": "feeder_po_handoff_quality",
            "status": "warn",
            "value": "0",
            "notes": "no_rows_processed",
            "observed_utc": observed_utc,
            "source_path": str(queue_path),
        },
    ]


def _latest_decisions(decisions_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    if decisions_df.empty:
        return {}
    ordered = decisions_df.copy()
    ordered["decision_utc"] = ordered["decision_utc"].map(_normalize_text)
    ordered["candidate_id"] = ordered["candidate_id"].map(_normalize_text)
    ordered["event_id"] = ordered["event_id"].map(_normalize_text)
    ordered = ordered.sort_values(["candidate_id", "decision_utc", "event_id"], kind="stable")
    latest = ordered.drop_duplicates(subset=["candidate_id"], keep="last")
    out: dict[str, dict[str, str]] = {}
    for _, row in latest.iterrows():
        payload = {column: _normalize_text(value) for column, value in row.to_dict().items()}
        candidate_id = payload.get("candidate_id", "")
        if candidate_id != "":
            out[candidate_id] = payload
    return out


def build_feeder_po_handoff(
    root: Path | None = None,
    *,
    supplier_id: str | None = None,
    handoff_utc: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)

    queue_contract = get_source_contract("feeder_approval_queue_live")
    decisions_contract = get_source_contract("feeder_approval_decisions_log")
    queue_path = root_path / queue_contract.source_path
    decisions_path = root_path / decisions_contract.source_path
    recommendations_path = root_path / get_f_output_contract("feeder_candidate_recommendations_live").rel_path
    observed_utc = handoff_utc or _utc_now_iso()
    handoff_batch_id = f"FPO-{observed_utc.replace('-', '').replace(':', '').replace('T', '_').replace('Z', '')}"

    queue_df = _read_csv(queue_path)
    decisions_df = _read_csv(decisions_path)
    rec_df = _read_csv(recommendations_path)

    if queue_df.empty or decisions_df.empty:
        ready_df = _write_contract_df(
            _empty_contract_df("feeder_po_handoff_ready_live"),
            "feeder_po_handoff_ready_live",
            root_path,
        )
        holds_df = _write_contract_df(
            _empty_contract_df("feeder_po_handoff_holds"),
            "feeder_po_handoff_holds",
            root_path,
        )
        health_df = _write_contract_df(
            pd.DataFrame(_source_missing_health_rows(observed_utc, queue_path, decisions_path)),
            "feeder_po_handoff_health",
            root_path,
        )
        print(
            {
                "status": "success",
                "supplier_id_filter": _normalize_text(supplier_id),
                "queue_rows": int(len(queue_df)),
                "decision_rows": int(len(decisions_df)),
                "handoff_ready_rows": 0,
                "hold_rows": 0,
                "notes": "required source missing or empty; emitted warn health state",
            }
        )
        return ready_df, holds_df, health_df

    missing_queue_columns = [column for column in queue_contract.required_columns if column not in queue_df.columns]
    missing_decision_columns = [
        column for column in decisions_contract.required_columns if column not in decisions_df.columns
    ]
    if missing_queue_columns or missing_decision_columns:
        ready_df = _write_contract_df(
            _empty_contract_df("feeder_po_handoff_ready_live"),
            "feeder_po_handoff_ready_live",
            root_path,
        )
        holds_df = _write_contract_df(
            _empty_contract_df("feeder_po_handoff_holds"),
            "feeder_po_handoff_holds",
            root_path,
        )
        notes_parts: list[str] = []
        if missing_queue_columns:
            notes_parts.append(f"queue_missing:{'|'.join(missing_queue_columns)}")
        if missing_decision_columns:
            notes_parts.append(f"decisions_missing:{'|'.join(missing_decision_columns)}")
        health_df = _write_contract_df(
            pd.DataFrame(
                [
                    {
                        "check": "feeder_po_handoff_source_contract",
                        "status": "fail",
                        "value": str(len(missing_queue_columns) + len(missing_decision_columns)),
                        "notes": ";".join(notes_parts),
                        "observed_utc": observed_utc,
                        "source_path": str(queue_path),
                    },
                    {
                        "check": "feeder_po_handoff_quality",
                        "status": "fail",
                        "value": "0",
                        "notes": "no_rows_processed_due_to_contract_failure",
                        "observed_utc": observed_utc,
                        "source_path": str(queue_path),
                    },
                ]
            ),
            "feeder_po_handoff_health",
            root_path,
        )
        print(
            {
                "status": "success",
                "supplier_id_filter": _normalize_text(supplier_id),
                "queue_rows": int(len(queue_df)),
                "decision_rows": int(len(decisions_df)),
                "handoff_ready_rows": 0,
                "hold_rows": 0,
                "notes": "source contract failed",
            }
        )
        return ready_df, holds_df, health_df

    queue_work = queue_df.copy()
    if _normalize_text(supplier_id) != "":
        queue_work = queue_work[
            queue_work["supplier_id"].map(_normalize_lower) == _normalize_lower(_normalize_text(supplier_id))
        ].copy()

    latest_by_candidate = _latest_decisions(decisions_df)

    rec_by_candidate: dict[str, dict[str, str]] = {}
    if not rec_df.empty and "candidate_id" in rec_df.columns:
        for _, row in rec_df.iterrows():
            payload = {column: _normalize_text(value) for column, value in row.to_dict().items()}
            key = payload.get("candidate_id", "")
            if key != "":
                rec_by_candidate[key] = payload

    ready_rows: list[dict[str, str]] = []
    hold_rows: list[dict[str, str]] = []
    for _, row in queue_work.iterrows():
        queue_row = {column: _normalize_text(value) for column, value in row.to_dict().items()}
        candidate_id = queue_row.get("candidate_id", "")
        feeder_candidate_id = queue_row.get("feeder_candidate_id", "")
        latest_decision = latest_by_candidate.get(candidate_id)
        rec_row = rec_by_candidate.get(candidate_id, {})

        reasons: list[str] = []
        latest_status = ""
        latest_action = ""
        latest_decision_utc = ""
        approved_qty: int | None = None

        if latest_decision is None:
            reasons.append("missing_decision_lineage")
        else:
            latest_status = _normalize_lower(latest_decision.get("final_decision_status", ""))
            latest_action = latest_decision.get("decision_action", "")
            latest_decision_utc = latest_decision.get("decision_utc", "")
            if latest_status not in APPROVAL_STATUSES:
                reasons.append(f"decision_not_approved:{latest_status or 'blank'}")
            approved_qty = _parse_positive_int(latest_decision.get("recommended_test_qty", ""))

        if _normalize_lower(queue_row.get("recommendation_status", "")) != "approve_test_buy":
            reasons.append("recommendation_not_approve_test_buy")

        if approved_qty is None:
            approved_qty = _parse_positive_int(queue_row.get("recommended_test_qty", ""))
        if approved_qty is None:
            reasons.append("non_positive_approved_qty")

        unit_cost_num = _parse_positive_float(rec_row.get("unit_cost", ""))
        if not rec_row:
            reasons.append("missing_recommendation_context")
        if unit_cost_num is None:
            reasons.append("missing_or_invalid_unit_cost")

        supplier_sku = queue_row.get("supplier_sku", "")
        if supplier_sku == "":
            reasons.append("missing_supplier_sku")

        if not reasons:
            ready_rows.append(
                {
                    "handoff_utc": observed_utc,
                    "handoff_batch_id": handoff_batch_id,
                    "candidate_id": candidate_id,
                    "feeder_candidate_id": feeder_candidate_id,
                    "supplier_id": queue_row.get("supplier_id", ""),
                    "supplier_name": queue_row.get("supplier_name", ""),
                    "supplier_sku": supplier_sku,
                    "supplier_title": queue_row.get("supplier_title", ""),
                    "barcode": _normalize_digits(rec_row.get("barcode", "")),
                    "approved_test_qty": str(approved_qty),
                    "initial_unit_cost": f"{unit_cost_num:.2f}",
                    "currency": rec_row.get("currency", ""),
                    "vat_rate": rec_row.get("vat_rate", ""),
                    "recommendation_status": queue_row.get("recommendation_status", ""),
                    "decision_action": latest_action,
                    "final_decision_status": latest_status,
                    "decision_utc": latest_decision_utc,
                    "source_row_hash": queue_row.get("source_row_hash", ""),
                    "source_file_path": queue_row.get("source_file_path", ""),
                    "source_seen_at_utc": queue_row.get("source_seen_at_utc", ""),
                    "source_url": rec_row.get("source_url", ""),
                    "notes": "",
                }
            )
            continue

        hold_rows.append(
            {
                "hold_utc": observed_utc,
                "candidate_id": candidate_id,
                "feeder_candidate_id": feeder_candidate_id,
                "supplier_id": queue_row.get("supplier_id", ""),
                "supplier_name": queue_row.get("supplier_name", ""),
                "supplier_sku": queue_row.get("supplier_sku", ""),
                "supplier_title": queue_row.get("supplier_title", ""),
                "hold_reason_codes": "|".join(reasons),
                "latest_decision_status": latest_status,
                "latest_decision_action": latest_action,
                "recommendation_status": queue_row.get("recommendation_status", ""),
                "recommended_test_qty": queue_row.get("recommended_test_qty", ""),
                "source_row_hash": queue_row.get("source_row_hash", ""),
                "source_file_path": queue_row.get("source_file_path", ""),
                "source_seen_at_utc": queue_row.get("source_seen_at_utc", ""),
                "source_url": rec_row.get("source_url", ""),
                "notes": "not_ready_for_po_handoff",
            }
        )

    ready_df = _write_contract_df(pd.DataFrame(ready_rows), "feeder_po_handoff_ready_live", root_path)
    holds_df = _write_contract_df(pd.DataFrame(hold_rows), "feeder_po_handoff_holds", root_path)

    source_status = "ok"
    quality_status = "ok"
    quality_note = (
        f"ready_rows={len(ready_df)};hold_rows={len(holds_df)};"
        f"queue_rows={len(queue_work)};decision_rows={len(decisions_df)}"
    )
    if len(queue_work) == 0:
        quality_status = "warn"
        quality_note = "no_rows_in_supplier_scope"
    elif len(ready_df) == 0:
        quality_status = "warn"
        quality_note = (
            f"no_approved_handoff_rows;hold_rows={len(holds_df)};"
            f"queue_rows={len(queue_work)};decision_rows={len(decisions_df)}"
        )

    health_df = _write_contract_df(
        pd.DataFrame(
            [
                {
                    "check": "feeder_po_handoff_source_contract",
                    "status": source_status,
                    "value": str(len(queue_work)),
                    "notes": "approval_queue_and_decision_log_contract_valid",
                    "observed_utc": observed_utc,
                    "source_path": str(queue_path),
                },
                {
                    "check": "feeder_po_handoff_quality",
                    "status": quality_status,
                    "value": str(len(ready_df)),
                    "notes": quality_note,
                    "observed_utc": observed_utc,
                    "source_path": str(queue_path),
                },
            ]
        ),
        "feeder_po_handoff_health",
        root_path,
    )

    print(
        {
            "status": "success",
            "supplier_id_filter": _normalize_text(supplier_id),
            "queue_rows": int(len(queue_work)),
            "decision_rows": int(len(decisions_df)),
            "handoff_ready_rows": int(len(ready_df)),
            "hold_rows": int(len(holds_df)),
            "health_quality_status": quality_status,
        }
    )
    return ready_df, holds_df, health_df


def main() -> None:
    parser = argparse.ArgumentParser(description="Build approved-only feeder PO handoff rows from queue and decisions.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--supplier-id", default=None)
    parser.add_argument("--handoff-utc", default=None)
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    build_feeder_po_handoff(
        root=root,
        supplier_id=args.supplier_id,
        handoff_utc=args.handoff_utc,
    )


if __name__ == "__main__":
    main()
