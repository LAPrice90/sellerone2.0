from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.core.storage.product_db_contract import normalize_text, utc_now_iso


DEFAULT_RUNTIME_SOURCE = ROOT / "out" / "phase1_runtime_floor_snapshot_latest.csv"
DEFAULT_PRICING_SOURCE = ROOT / "out" / "pricing_output.csv"
DEFAULT_TERMINAL_INFO = ROOT / "out" / "systems" / "H" / "live" / "H_cycle_last_terminal_info.txt"
DEFAULT_PUBLISH_INFO = ROOT / "out" / "systems" / "H" / "live" / "H_cycle_last_publish_info.txt"
DEFAULT_OUTPUT_DIR = ROOT / "out" / "sql_migration" / "product_db_contract"

ALLOWED_WRITE_STATUSES: tuple[str, ...] = (
    "APPLIED",
    "NO_WRITE_REQUIRED",
    "READ_ONLY_NO_WRITE",
    "OBSERVABILITY_BLOCK_NO_WRITE",
    "NO_ATTEMPT",
    "BLOCKED",
    "ERROR",
    "WRITE_NOT_APPLIED",
)
ROOT_CAUSE_COLUMNS: tuple[str, ...] = (
    "source_name",
    "root_cause",
    "row_count",
    "example_skus",
    "truth_statuses",
    "current_cycle_decisions",
    "current_cycle_blocker_codes",
    "unified_writer_outcomes",
)


def _path_mtime_utc(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        return None


def _path_mtime_iso(path: Path) -> str:
    mtime = _path_mtime_utc(path)
    if mtime is None:
        return ""
    return pd.Timestamp(mtime, unit="s", tz="UTC").isoformat().replace("+00:00", "Z")


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame()


def _read_key_value_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[normalize_text(key)] = normalize_text(value)
    return out


def _series(df: pd.DataFrame, column: str) -> pd.Series:
    if column in df.columns:
        return df[column].map(normalize_text)
    return pd.Series([""] * len(df.index), index=df.index, dtype=str)


def _status_counts(df: pd.DataFrame) -> dict[str, int]:
    if df.empty or "execution_write_status" not in df.columns:
        return {}
    counts = Counter(_series(df, "execution_write_status").map(lambda value: value.upper()))
    return {key: int(value) for key, value in sorted(counts.items())}


def _blank_root_cause(row: pd.Series) -> str:
    truth_status = normalize_text(row.get("truth_status", "")).upper()
    decision = normalize_text(row.get("current_cycle_decision", "")).lower()
    blocker = normalize_text(row.get("current_cycle_blocker_code", "")).upper()
    writer_outcome = normalize_text(row.get("unified_writer_outcome", "")).upper()
    if blocker == "MARKET_DATA_MISSING_CURRENT_CYCLE" or decision == "skip_no_market_data":
        return "no_market_data_execution_context_cleared"
    if truth_status == "PARKED":
        return "parked_execution_context_cleared"
    if writer_outcome:
        return "writer_outcome_present_but_execution_status_blank"
    return "unknown_blank_execution_write_status"


def _compact_values(values: pd.Series) -> str:
    cleaned = sorted({normalize_text(value) for value in values.tolist() if normalize_text(value)})
    return "|".join(cleaned)


def _root_cause_rows(df: pd.DataFrame, *, source_name: str) -> list[dict[str, str]]:
    if df.empty or "execution_write_status" not in df.columns:
        return []
    work = df.copy()
    blank_mask = _series(work, "execution_write_status").eq("")
    work = work.loc[blank_mask].copy()
    if work.empty:
        return []
    work["_root_cause"] = work.apply(_blank_root_cause, axis=1)
    rows: list[dict[str, str]] = []
    for root_cause, group in work.groupby("_root_cause", sort=True):
        rows.append(
            {
                "source_name": source_name,
                "root_cause": root_cause,
                "row_count": str(int(len(group.index))),
                "example_skus": "|".join(_series(group, "sku").head(5).tolist()),
                "truth_statuses": _compact_values(_series(group, "truth_status")),
                "current_cycle_decisions": _compact_values(_series(group, "current_cycle_decision")),
                "current_cycle_blocker_codes": _compact_values(_series(group, "current_cycle_blocker_code")),
                "unified_writer_outcomes": _compact_values(_series(group, "unified_writer_outcome")),
            }
        )
    return rows


def _invalid_write_status_count(df: pd.DataFrame) -> int:
    if df.empty or "execution_write_status" not in df.columns:
        return 0
    allowed = set(ALLOWED_WRITE_STATUSES)
    normalized = _series(df, "execution_write_status").map(lambda value: value.upper())
    return int((normalized.ne("") & ~normalized.isin(allowed)).sum())


def _terminal_rows(df: pd.DataFrame, terminal_run_id: str) -> int:
    if df.empty or not terminal_run_id or "current_cycle_run_id" not in df.columns:
        return 0
    return int(_series(df, "current_cycle_run_id").eq(terminal_run_id).sum())


def _rows_for_run(df: pd.DataFrame, run_id: str) -> pd.DataFrame:
    if df.empty or not run_id or "current_cycle_run_id" not in df.columns:
        return df.iloc[0:0].copy()
    return df.loc[_series(df, "current_cycle_run_id").eq(run_id)].copy()


def _latest_nonblank_run_id(df: pd.DataFrame) -> str:
    if df.empty or "current_cycle_run_id" not in df.columns:
        return ""
    run_ids = sorted({run_id for run_id in _series(df, "current_cycle_run_id").tolist() if run_id})
    return run_ids[-1] if run_ids else ""


def _pricing_output_stale_reason(
    *,
    runtime_source: Path,
    pricing_source: Path,
    runtime_df: pd.DataFrame,
    pricing_df: pd.DataFrame,
    proof_run_id: str,
) -> str:
    if pricing_df.empty or not pricing_source.exists():
        return ""
    runtime_mtime = _path_mtime_utc(runtime_source)
    pricing_mtime = _path_mtime_utc(pricing_source)
    if runtime_mtime is None or pricing_mtime is None or pricing_mtime >= runtime_mtime:
        return ""
    runtime_proof_rows = _terminal_rows(runtime_df, proof_run_id)
    pricing_proof_rows = _terminal_rows(pricing_df, proof_run_id)
    if runtime_proof_rows > 0 and pricing_proof_rows == 0:
        return "pricing_output_older_than_runtime_and_missing_latest_runtime_run"
    if "current_cycle_run_id" not in pricing_df.columns:
        return "pricing_output_older_than_runtime_and_has_no_run_id_column"
    return ""


def run_repricing_write_status_proof(
    *,
    runtime_source: Path = DEFAULT_RUNTIME_SOURCE,
    pricing_source: Path = DEFAULT_PRICING_SOURCE,
    terminal_info_path: Path = DEFAULT_TERMINAL_INFO,
    publish_info_path: Path = DEFAULT_PUBLISH_INFO,
    observed_utc: str | None = None,
) -> dict[str, Any]:
    observed = observed_utc or utc_now_iso()
    runtime_df = _read_csv(runtime_source)
    pricing_df = _read_csv(pricing_source)
    terminal_info = _read_key_value_file(terminal_info_path)
    publish_info = _read_key_value_file(publish_info_path)
    terminal_run_id = normalize_text(terminal_info.get("run_id", ""))
    terminal_state = normalize_text(terminal_info.get("state", ""))
    publish_status = normalize_text(publish_info.get("status", ""))
    runtime_terminal_run_rows = _terminal_rows(runtime_df, terminal_run_id)
    pricing_terminal_run_rows = _terminal_rows(pricing_df, terminal_run_id)
    latest_runtime_run_id = _latest_nonblank_run_id(runtime_df)
    proof_run_id = terminal_run_id if runtime_terminal_run_rows else latest_runtime_run_id
    proof_run_source = (
        "terminal_run_id"
        if runtime_terminal_run_rows
        else "latest_runtime_run_id_fallback"
        if latest_runtime_run_id
        else ""
    )

    runtime_blank = int(_series(runtime_df, "execution_write_status").eq("").sum()) if not runtime_df.empty else 0
    pricing_blank = int(_series(pricing_df, "execution_write_status").eq("").sum()) if not pricing_df.empty else 0
    pricing_stale_reason = _pricing_output_stale_reason(
        runtime_source=runtime_source,
        pricing_source=pricing_source,
        runtime_df=runtime_df,
        pricing_df=pricing_df,
        proof_run_id=proof_run_id,
    )
    pricing_output_stale = pricing_stale_reason != ""
    root_cause_rows = [
        *_root_cause_rows(runtime_df, source_name="runtime_floor_snapshot"),
        *_root_cause_rows(
            pricing_df,
            source_name="pricing_output_stale" if pricing_output_stale else "pricing_output",
        ),
    ]
    unknown_root_cause_rows = sum(
        int(row["row_count"])
        for row in root_cause_rows
        if row["root_cause"] == "unknown_blank_execution_write_status"
        and (row["source_name"] != "pricing_output_stale")
    )
    runtime_invalid_count = _invalid_write_status_count(runtime_df)
    pricing_invalid_count = _invalid_write_status_count(pricing_df)
    invalid_count = runtime_invalid_count + (0 if pricing_output_stale else pricing_invalid_count)
    current_pricing_blank = 0 if pricing_output_stale else pricing_blank
    terminal_blocker_reason = ""
    terminal_state_norm = terminal_state.lower()
    terminal_publish_status_norm = normalize_text(terminal_info.get("publish_status", "")).lower()
    if terminal_state_norm and terminal_state_norm != "finalized":
        terminal_blocker_reason = "terminal_state_not_finalized"
    elif terminal_state_norm == "finalized" and terminal_publish_status_norm not in {"", "ok"}:
        terminal_blocker_reason = "terminal_publish_status_not_ok"
    status = (
        "fail"
        if terminal_blocker_reason or unknown_root_cause_rows or invalid_count
        else "warn"
        if runtime_blank or current_pricing_blank or pricing_output_stale
        else "ok"
    )

    return {
        "status": status,
        "observed_utc": observed,
        "runtime_source": str(runtime_source),
        "pricing_source": str(pricing_source),
        "runtime_source_mtime_utc": _path_mtime_iso(runtime_source),
        "pricing_source_mtime_utc": _path_mtime_iso(pricing_source),
        "pricing_output_stale": pricing_output_stale,
        "pricing_output_stale_reason": pricing_stale_reason,
        "terminal_blocker_reason": terminal_blocker_reason,
        "terminal_run_id": terminal_run_id,
        "latest_runtime_run_id": latest_runtime_run_id,
        "proof_run_id": proof_run_id,
        "proof_run_source": proof_run_source,
        "terminal_state": terminal_state,
        "terminal_publish_status": normalize_text(terminal_info.get("publish_status", "")),
        "terminal_utc": normalize_text(terminal_info.get("utc", "")),
        "publish_run_id": normalize_text(publish_info.get("run_id", "")),
        "publish_status": publish_status,
        "publish_rows": normalize_text(publish_info.get("rows", "")),
        "runtime_rows": int(len(runtime_df.index)),
        "pricing_rows": int(len(pricing_df.index)),
        "runtime_terminal_run_rows": runtime_terminal_run_rows,
        "pricing_terminal_run_rows": pricing_terminal_run_rows,
        "runtime_proof_run_rows": _terminal_rows(runtime_df, proof_run_id),
        "pricing_proof_run_rows": _terminal_rows(pricing_df, proof_run_id),
        "runtime_write_status_counts": _status_counts(runtime_df),
        "pricing_write_status_counts": _status_counts(pricing_df),
        "runtime_proof_run_write_status_counts": _status_counts(_rows_for_run(runtime_df, proof_run_id)),
        "pricing_proof_run_write_status_counts": _status_counts(_rows_for_run(pricing_df, proof_run_id)),
        "runtime_blank_execution_write_status_rows": runtime_blank,
        "pricing_blank_execution_write_status_rows": pricing_blank,
        "current_pricing_blank_execution_write_status_rows": current_pricing_blank,
        "runtime_invalid_execution_write_status_rows": runtime_invalid_count,
        "pricing_invalid_execution_write_status_rows": pricing_invalid_count,
        "invalid_execution_write_status_rows": invalid_count,
        "unknown_blank_root_cause_rows": int(unknown_root_cause_rows),
        "root_cause_rows": root_cause_rows,
    }


def write_outputs(payload: dict[str, Any], *, output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    detail_path = output_dir / "repricing_write_status_root_cause.csv"
    summary_path = output_dir / "repricing_write_status_proof_summary.json"
    pd.DataFrame(payload["root_cause_rows"], columns=ROOT_CAUSE_COLUMNS).to_csv(detail_path, index=False)
    summary = {key: value for key, value in payload.items() if key != "root_cause_rows"}
    summary["outputs"] = {
        "root_cause": str(detail_path),
        "summary": str(summary_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return summary["outputs"]


def _output_payload(payload: dict[str, Any], *, include_rows: bool) -> dict[str, Any]:
    if include_rows:
        return payload
    return {key: value for key, value in payload.items() if key != "root_cause_rows"}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only repricer write-status proof summary.")
    parser.add_argument("--runtime-source", default=str(DEFAULT_RUNTIME_SOURCE))
    parser.add_argument("--pricing-source", default=str(DEFAULT_PRICING_SOURCE))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--include-rows", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    payload = run_repricing_write_status_proof(
        runtime_source=Path(args.runtime_source),
        pricing_source=Path(args.pricing_source),
    )
    outputs: dict[str, str] = {}
    if not args.no_write:
        outputs = write_outputs(payload, output_dir=Path(args.output_dir))
    payload_with_outputs = {**payload, "outputs": outputs}
    if args.format == "json":
        print(json.dumps(_output_payload(payload_with_outputs, include_rows=bool(args.include_rows)), indent=2, ensure_ascii=True))
    else:
        print(f"status={payload['status']}")
        print(f"terminal_run_id={payload['terminal_run_id']}")
        print(f"terminal_state={payload['terminal_state']}")
        print(f"publish_status={payload['publish_status']}")
        print(f"runtime_rows={payload['runtime_rows']}")
        print(f"pricing_rows={payload['pricing_rows']}")
        print(f"runtime_blank_execution_write_status_rows={payload['runtime_blank_execution_write_status_rows']}")
        print(f"pricing_blank_execution_write_status_rows={payload['pricing_blank_execution_write_status_rows']}")
        print(f"pricing_output_stale={payload['pricing_output_stale']}")
        print(f"pricing_output_stale_reason={payload['pricing_output_stale_reason']}")
        print(f"unknown_blank_root_cause_rows={payload['unknown_blank_root_cause_rows']}")
        print(f"outputs={json.dumps(outputs, ensure_ascii=True, sort_keys=True)}")
    return 0 if payload["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
