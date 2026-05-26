from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.flows.F._contract_io import write_f_contract_df
from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract
from scripts.flows.F._schemas import get_f_output_column_types, get_f_output_contract


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


def build_backtest_policy_snapshot(
    root: Path | None = None,
    *,
    observed_utc: str | None = None,
    policy_id: str = "f_backtest_policy_v1",
    policy_version: str = "1.0",
    policy_status: str = "active",
    minimum_expected_profit_gbp: float = 20.0,
    entry_target_roi_pct: float = 20.0,
    working_floor_roi_pct: float = 10.0,
    exit_floor_roi_pct: float = 0.0,
    emergency_floor_roi_pct: float = -5.0,
    policy_source: str = "system_default_v1",
    notes: str = "",
) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)
    snapshot_utc = observed_utc or _utc_now_iso()

    row = {
        "observed_utc": snapshot_utc,
        "policy_id": _normalize_text(policy_id),
        "policy_version": _normalize_text(policy_version),
        "policy_status": _normalize_text(policy_status) or "active",
        "minimum_expected_profit_gbp": _number_text(minimum_expected_profit_gbp),
        "entry_target_roi_pct": _number_text(entry_target_roi_pct),
        "working_floor_roi_pct": _number_text(working_floor_roi_pct),
        "exit_floor_roi_pct": _number_text(exit_floor_roi_pct),
        "emergency_floor_roi_pct": _number_text(emergency_floor_roi_pct),
        "recency_weight_30d": "0.5",
        "recency_weight_90d": "0.3",
        "recency_weight_180d": "0.15",
        "recency_weight_365d": "0.05",
        "ceiling_warn_ratio_30d": "1.25",
        "ceiling_red_ratio_30d": "1.5",
        "ceiling_extreme_ratio_30d": "2",
        "shock_trigger_pct_1d": "20",
        "shared_sales_default_pct": "50",
        "policy_source": _normalize_text(policy_source),
        "notes": _normalize_text(notes),
    }

    out_df = _write_contract_df(
        pd.DataFrame([row]),
        "feeder_backtest_policy_live",
        root_path,
    )

    print(
        {
            "status": "success",
            "rows": int(len(out_df)),
            "active_rows": int((out_df["policy_status"] == "active").sum()),
            "snapshot": str(root_path / get_f_output_contract("feeder_backtest_policy_live").rel_path),
        }
    )
    return out_df


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build F backtest v1 policy snapshot.")
    parser.add_argument("--observed-utc", default=None, help="Override observed_utc for deterministic runs.")
    parser.add_argument("--policy-id", default="f_backtest_policy_v1")
    parser.add_argument("--policy-version", default="1.0")
    parser.add_argument("--policy-status", default="active")
    parser.add_argument("--minimum-expected-profit-gbp", type=float, default=20.0)
    parser.add_argument("--entry-target-roi-pct", type=float, default=20.0)
    parser.add_argument("--working-floor-roi-pct", type=float, default=10.0)
    parser.add_argument("--exit-floor-roi-pct", type=float, default=0.0)
    parser.add_argument("--emergency-floor-roi-pct", type=float, default=-5.0)
    parser.add_argument("--policy-source", default="system_default_v1")
    parser.add_argument("--notes", default="")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_backtest_policy_snapshot(
        observed_utc=args.observed_utc,
        policy_id=args.policy_id,
        policy_version=args.policy_version,
        policy_status=args.policy_status,
        minimum_expected_profit_gbp=args.minimum_expected_profit_gbp,
        entry_target_roi_pct=args.entry_target_roi_pct,
        working_floor_roi_pct=args.working_floor_roi_pct,
        exit_floor_roi_pct=args.exit_floor_roi_pct,
        emergency_floor_roi_pct=args.emergency_floor_roi_pct,
        policy_source=args.policy_source,
        notes=args.notes,
    )


if __name__ == "__main__":
    main()
