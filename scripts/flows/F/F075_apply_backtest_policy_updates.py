from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.flows.F._contract_io import write_f_contract_df
from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract
from scripts.flows.F._schemas import get_f_output_column_types, get_f_output_contract


EDITABLE_POLICY_COLUMNS = (
    "minimum_expected_profit_gbp",
    "entry_target_roi_pct",
    "working_floor_roi_pct",
    "exit_floor_roi_pct",
    "emergency_floor_roi_pct",
)

VALID_POLICY_ACTIONS = {
    "apply",
    "approve",
    "approved",
    "set",
    "update",
    "update_policy",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _number_text(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _contract_columns(contract_name: str) -> list[str]:
    contract = get_f_output_contract(contract_name)
    return [*contract.required_columns, *contract.optional_columns]


def _empty_contract_df(contract_name: str) -> pd.DataFrame:
    return pd.DataFrame(columns=_contract_columns(contract_name))


def _read_contract_df(root_path: Path, contract_name: str) -> pd.DataFrame:
    in_path = root_path / get_f_output_contract(contract_name).rel_path
    if not in_path.exists():
        return _empty_contract_df(contract_name)
    df = pd.read_csv(in_path, dtype=str).fillna("")
    ordered = _contract_columns(contract_name)
    for col in ordered:
        if col not in df.columns:
            df[col] = ""
    return df


def _finalize_contract_df(df: pd.DataFrame, contract_name: str) -> pd.DataFrame:
    ordered = _contract_columns(contract_name)
    out = df.copy()
    for col in ordered:
        if col not in out.columns:
            out[col] = ""
    out = out[ordered]
    for col in ordered:
        out[col] = out[col].map(_normalize_text)
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


def _active_policy_row(policy_df: pd.DataFrame) -> pd.Series:
    if policy_df.empty:
        raise ValueError("active policy row required but feeder_backtest_policy_live.csv is empty")
    active = policy_df[policy_df.get("policy_status", "").map(lambda v: _normalize_text(v).lower() == "active")]
    if len(active.index) != 1:
        raise ValueError(f"expected exactly one active policy row, found {len(active.index)}")
    return active.iloc[0]


def _parse_numeric(name: str, value: object) -> float:
    raw = _normalize_text(value)
    if raw == "":
        raise ValueError(f"{name} is blank")
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric") from exc


def _validated_policy_values(event_row: pd.Series) -> dict[str, str]:
    parsed: dict[str, str] = {}
    numeric: dict[str, float] = {}
    for col in EDITABLE_POLICY_COLUMNS:
        number = _parse_numeric(col, event_row.get(col, ""))
        numeric[col] = number
        parsed[col] = _number_text(number)

    entry = numeric["entry_target_roi_pct"]
    working = numeric["working_floor_roi_pct"]
    exit_floor = numeric["exit_floor_roi_pct"]
    emergency = numeric["emergency_floor_roi_pct"]
    if not (entry >= working >= exit_floor >= emergency):
        raise ValueError(
            "policy ordering invalid: entry_target_roi_pct >= working_floor_roi_pct >= "
            "exit_floor_roi_pct >= emergency_floor_roi_pct is required"
        )
    return parsed


def _sorted_event_rows(events_df: pd.DataFrame) -> pd.DataFrame:
    work = events_df.copy()
    work["__event_utc_sort"] = work.get("event_utc", "").map(_normalize_text)
    work["__row_idx"] = list(range(len(work.index)))
    work = work.sort_values(by=["__event_utc_sort", "__row_idx"], kind="stable")
    return work


def _find_latest_valid_event(events_df: pd.DataFrame) -> tuple[pd.Series, dict[str, str], str]:
    failures: list[str] = []
    sorted_events = _sorted_event_rows(events_df)
    for _, row in sorted_events.iloc[::-1].iterrows():
        event_id = _normalize_text(row.get("event_id", "")) or "<blank_event_id>"
        action = _normalize_text(row.get("action", "")).lower()
        policy_id = _normalize_text(row.get("policy_id", ""))
        try:
            if action not in VALID_POLICY_ACTIONS:
                raise ValueError(f"unsupported action '{_normalize_text(row.get('action', ''))}'")
            if policy_id == "":
                raise ValueError("policy_id is blank")
            validated = _validated_policy_values(row)
            return row, validated, policy_id
        except ValueError as exc:
            failures.append(f"{event_id}: {exc}")
            continue
    details = " | ".join(failures[:6]) if failures else "no_events_found"
    raise ValueError(f"no valid policy update events found ({details})")


def apply_backtest_policy_updates(
    root: Path | None = None,
    *,
    observed_utc: str | None = None,
) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)
    snapshot_utc = observed_utc or _utc_now_iso()

    policy_df = _read_contract_df(root_path, "feeder_backtest_policy_live")
    active_policy = _active_policy_row(policy_df)
    events_df = _read_contract_df(root_path, "feeder_backtest_policy_update_events")

    if events_df.empty:
        print(
            json.dumps(
                {
                    "status": "no_change",
                    "reason": "no_policy_update_events",
                    "live_policy_path": str(root_path / get_f_output_contract("feeder_backtest_policy_live").rel_path),
                }
            )
        )
        return _finalize_contract_df(pd.DataFrame([active_policy.to_dict()]), "feeder_backtest_policy_live")

    selected_event, validated_values, selected_policy_id = _find_latest_valid_event(events_df)

    out_row = {col: _normalize_text(active_policy.get(col, "")) for col in _contract_columns("feeder_backtest_policy_live")}
    out_row["observed_utc"] = snapshot_utc
    out_row["policy_id"] = selected_policy_id
    out_row["policy_status"] = "active"
    for col, value in validated_values.items():
        out_row[col] = value

    event_id = _normalize_text(selected_event.get("event_id", ""))
    actor = _normalize_text(selected_event.get("actor", ""))
    source_reference = _normalize_text(selected_event.get("source_reference", ""))
    decision_note = _normalize_text(selected_event.get("decision_note", ""))
    policy_source_parts = [f"policy_update_event:{event_id}"]
    if source_reference:
        policy_source_parts.append(f"source:{source_reference}")
    out_row["policy_source"] = "|".join(policy_source_parts)

    note_parts: list[str] = []
    if decision_note:
        note_parts.append(decision_note)
    if actor:
        note_parts.append(f"actor={actor}")
    if source_reference:
        note_parts.append(f"source={source_reference}")
    if note_parts:
        out_row["notes"] = " ; ".join(note_parts)

    out_df = _write_contract_df(pd.DataFrame([out_row]), "feeder_backtest_policy_live", root_path)
    print(
        json.dumps(
            {
                "status": "success",
                "applied_event_id": event_id,
                "policy_id": out_row["policy_id"],
                "rows": int(len(out_df.index)),
                "live_policy_path": str(root_path / get_f_output_contract("feeder_backtest_policy_live").rel_path),
            }
        )
    )
    return out_df


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply latest valid backtest policy update event to live F policy.")
    parser.add_argument("--observed-utc", default=None, help="Override observed_utc in YYYY-MM-DDTHH:MM:SSZ.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    apply_backtest_policy_updates(observed_utc=args.observed_utc)


if __name__ == "__main__":
    main()
