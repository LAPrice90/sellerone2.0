from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.core.storage import read_dataframe_with_sql_fallback
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract
from scripts.flows.O._schemas import get_o_output_contract


SQL_TABLE_H_RUNTIME_FLOOR = "h_phase1_runtime_floor_snapshot_latest"

RUNTIME_REL_PATH = Path("out") / "phase1_runtime_floor_snapshot_latest.csv"
PRICING_OUTPUT_REL_PATH = Path("out") / "pricing_output.csv"
H_TERMINAL_INFO_REL_PATH = Path("out") / "systems" / "H" / "live" / "H_cycle_last_terminal_info.txt"
H_PUBLISH_INFO_REL_PATH = Path("out") / "systems" / "H" / "live" / "H_cycle_last_publish_info.txt"

ALLOWED_WRITE_STATUSES = {
    "APPLIED",
    "NO_WRITE_REQUIRED",
    "READ_ONLY_NO_WRITE",
    "OBSERVABILITY_BLOCK_NO_WRITE",
    "NO_ATTEMPT",
    "BLOCKED",
    "ERROR",
    "WRITE_NOT_APPLIED",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _truthy(value: object) -> bool:
    return _normalize_text(value).lower() in {"1", "true", "yes", "y", "on"}


def _safe_float(value: object) -> float | None:
    text = _normalize_text(value).replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _flag_text(value: bool) -> str:
    return "1" if value else "0"


def _read_key_value_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[_normalize_text(key)] = _normalize_text(value)
    return out


def _dashboard_view_rows_for_publish_marker(root: Path, publish_info: dict[str, str]) -> tuple[int | None, Path | None]:
    publish_utc = _normalize_text(publish_info.get("utc", ""))
    publish_date = ""
    if publish_utc:
        publish_date = publish_utc[:10]
    if not publish_date:
        return None, None
    view_path = root / "out" / "analysis_reports" / f"phase1_observation_view_{publish_date}.csv"
    if not view_path.exists():
        return None, view_path
    try:
        return int(len(pd.read_csv(view_path, dtype=str).index)), view_path
    except Exception:
        return None, view_path


def _read_runtime_df(root: Path) -> pd.DataFrame:
    path = root / RUNTIME_REL_PATH
    try:
        return read_dataframe_with_sql_fallback(path, SQL_TABLE_H_RUNTIME_FLOOR, dtype=str).fillna("")
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame()


def _read_pricing_output_df(root: Path) -> pd.DataFrame:
    path = root / PRICING_OUTPUT_REL_PATH
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame()


def _path_mtime_utc(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        return None


def _terminal_run_rows(df: pd.DataFrame, terminal_run_id: str) -> int:
    if df.empty or terminal_run_id == "" or "current_cycle_run_id" not in df.columns:
        return 0
    return int(df["current_cycle_run_id"].map(_normalize_text).eq(terminal_run_id).sum())


def _latest_nonblank_run_id(df: pd.DataFrame) -> str:
    if df.empty or "current_cycle_run_id" not in df.columns:
        return ""
    run_ids = sorted({run_id for run_id in df["current_cycle_run_id"].map(_normalize_text).tolist() if run_id})
    return run_ids[-1] if run_ids else ""


def _pricing_output_stale_reason(
    *,
    runtime_path: Path,
    pricing_path: Path,
    runtime_df: pd.DataFrame,
    pricing_df: pd.DataFrame,
    proof_run_id: str,
) -> str:
    if pricing_df.empty or not pricing_path.exists():
        return ""
    runtime_mtime = _path_mtime_utc(runtime_path)
    pricing_mtime = _path_mtime_utc(pricing_path)
    if runtime_mtime is None or pricing_mtime is None or pricing_mtime >= runtime_mtime:
        return ""
    runtime_proof_rows = _terminal_run_rows(runtime_df, proof_run_id)
    pricing_proof_rows = _terminal_run_rows(pricing_df, proof_run_id)
    if runtime_proof_rows > 0 and pricing_proof_rows == 0:
        return "pricing_output_older_than_runtime_and_missing_latest_runtime_run"
    if "current_cycle_run_id" not in pricing_df.columns:
        return "pricing_output_older_than_runtime_and_has_no_run_id_column"
    return ""


def _required_missing(df: pd.DataFrame) -> list[str]:
    required = [
        "snapshot_utc",
        "sku",
        "current_cycle_run_id",
        "execution_state",
        "execution_write_status",
        "execution_old_price_gbp",
        "execution_new_price_gbp",
        "execution_hard_floor_gbp",
        "execution_final_ceiling_landed_gbp",
        "write_attempted_flag",
        "write_applied_flag",
        "truth_status",
    ]
    return [column for column in required if column not in df.columns]


def _derive_tracker_status(row: pd.Series, write_status: str) -> str:
    truth_status = _normalize_text(row.get("truth_status", "")).upper()
    if truth_status:
        return truth_status
    if write_status == "":
        return "MISSING_WRITE_STATUS"
    if write_status == "APPLIED":
        return "WRITE_APPLIED"
    if _truthy(row.get("write_attempted_flag", "")):
        return "WRITE_ATTEMPTED"
    if write_status in {"READ_ONLY_NO_WRITE", "OBSERVABILITY_BLOCK_NO_WRITE"}:
        return "READ_ONLY"
    return write_status


def _decision_to_change_price(row: pd.Series, write_status: str) -> bool:
    if write_status == "APPLIED" or _truthy(row.get("write_attempted_flag", "")):
        return True
    old_price = _safe_float(row.get("execution_old_price_gbp", ""))
    new_price = _safe_float(row.get("execution_new_price_gbp", ""))
    if old_price is None or new_price is None:
        return False
    return abs(old_price - new_price) > 0.0001


def _health_row(
    *,
    check: str,
    status: str,
    value: object,
    notes: str,
    observed_utc: str,
    source_path: Path,
) -> dict[str, str]:
    return {
        "check": check,
        "status": status,
        "value": _normalize_text(value),
        "notes": notes,
        "observed_utc": observed_utc,
        "source_path": str(source_path),
    }


def _build_health_rows(
    *,
    runtime_df: pd.DataFrame,
    pricing_df: pd.DataFrame,
    terminal_info: dict[str, str],
    publish_info: dict[str, str],
    observed_utc: str,
    source_path: Path,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    rows.append(
        _health_row(
            check="repricer_tracker_runtime_source_present",
            status="ok" if not runtime_df.empty else "fail",
            value=len(runtime_df.index),
            notes="runtime floor snapshot rows available" if not runtime_df.empty else "runtime floor snapshot missing or empty",
            observed_utc=observed_utc,
            source_path=source_path,
        )
    )
    missing = _required_missing(runtime_df) if not runtime_df.empty else []
    rows.append(
        _health_row(
            check="repricer_tracker_required_columns",
            status="fail" if missing else "ok",
            value=len(missing),
            notes="missing required columns: " + "|".join(missing) if missing else "required columns present",
            observed_utc=observed_utc,
            source_path=source_path,
        )
    )
    blank_write_count = 0
    invalid_write_count = 0
    if "execution_write_status" in runtime_df.columns:
        normalized = runtime_df["execution_write_status"].map(lambda v: _normalize_text(v).upper())
        blank_write_count = int(normalized.eq("").sum())
        invalid_write_count = int((~normalized.isin(ALLOWED_WRITE_STATUSES) & normalized.ne("")).sum())
    rows.append(
        _health_row(
            check="repricer_tracker_blank_execution_write_status",
            status="fail" if blank_write_count else "ok",
            value=blank_write_count,
            notes="blank execution_write_status rows in source output" if blank_write_count else "no blank execution_write_status rows",
            observed_utc=observed_utc,
            source_path=source_path,
        )
    )
    rows.append(
        _health_row(
            check="repricer_tracker_invalid_execution_write_status",
            status="fail" if invalid_write_count else "ok",
            value=invalid_write_count,
            notes="unexpected execution_write_status values" if invalid_write_count else "all nonblank write statuses are allowed",
            observed_utc=observed_utc,
            source_path=source_path,
        )
    )
    latest_run_id = _normalize_text(terminal_info.get("run_id", ""))
    terminal_state = _normalize_text(terminal_info.get("state", ""))
    terminal_state_norm = terminal_state.lower()
    rows.append(
        _health_row(
            check="repricer_tracker_latest_terminal_state",
            status="fail" if terminal_state_norm == "failed" else ("ok" if terminal_state_norm == "finalized" else "warn"),
            value=terminal_state or "missing",
            notes=f"latest terminal run id: {latest_run_id or 'missing'}",
            observed_utc=observed_utc,
            source_path=source_path,
        )
    )
    latest_run_rows = 0
    newer_runtime_rows = 0
    newest_runtime_run_id = _latest_nonblank_run_id(runtime_df)
    if latest_run_id and "current_cycle_run_id" in runtime_df.columns:
        run_ids = runtime_df["current_cycle_run_id"].map(_normalize_text)
        latest_run_rows = int(run_ids.eq(latest_run_id).sum())
        nonblank_run_ids = sorted({run_id for run_id in run_ids.tolist() if run_id})
        newest_runtime_run_id = nonblank_run_ids[-1] if nonblank_run_ids else ""
        if newest_runtime_run_id and newest_runtime_run_id > latest_run_id:
            newer_runtime_rows = int(run_ids.eq(newest_runtime_run_id).sum())
    rows.append(
        _health_row(
            check="repricer_tracker_latest_terminal_run_rows",
            status="ok" if latest_run_rows else ("warn" if latest_run_id else "fail"),
            value=latest_run_rows,
            notes=f"latest terminal run id: {latest_run_id or 'missing'}",
            observed_utc=observed_utc,
            source_path=source_path,
        )
    )
    rows.append(
        _health_row(
            check="repricer_tracker_newer_runtime_than_terminal",
            status="warn" if newer_runtime_rows else "ok",
            value=newer_runtime_rows,
            notes=(
                f"newest runtime run id {newest_runtime_run_id} is newer than terminal run id {latest_run_id}"
                if newer_runtime_rows
                else "no newer runtime run than latest terminal marker"
            ),
            observed_utc=observed_utc,
            source_path=source_path,
        )
    )
    publish_rows = _normalize_text(publish_info.get("rows", ""))
    publish_status = _normalize_text(publish_info.get("status", ""))
    publish_rows_num = int(float(publish_rows)) if publish_rows.replace(".", "", 1).isdigit() else None
    root_path = source_path.parent.parent
    dashboard_rows, dashboard_path = _dashboard_view_rows_for_publish_marker(root_path, publish_info)
    rows.append(
        _health_row(
            check="repricer_tracker_publish_marker",
            status="ok" if publish_status == "ok" else "warn",
            value=publish_rows,
            notes=f"publish_status={publish_status or 'missing'}",
            observed_utc=observed_utc,
            source_path=root_relative_or_str(source_path),
        )
    )
    rows.append(
        _health_row(
            check="repricer_tracker_terminal_rows_vs_publish_rows",
            status="ok",
            value=f"{latest_run_rows}/{publish_rows or ''}",
            notes=(
                "terminal runtime rows are raw processed SKUs; publish rows are filtered dashboard-visible rows"
                if publish_rows_num is not None and latest_run_rows != publish_rows_num
                else "latest terminal rows match publish marker rows"
            ),
            observed_utc=observed_utc,
            source_path=source_path,
        )
    )
    rows.append(
        _health_row(
            check="repricer_tracker_publish_rows_vs_dashboard_view_rows",
            status=(
                "ok"
                if publish_rows_num is None or dashboard_rows is None or publish_rows_num == dashboard_rows
                else "warn"
            ),
            value=f"{publish_rows or ''}/{'' if dashboard_rows is None else dashboard_rows}",
            notes=(
                "publish marker rows match the filtered H130 dashboard view rows"
                if publish_rows_num is not None and dashboard_rows is not None and publish_rows_num == dashboard_rows
                else "dashboard view rows unavailable for publish marker comparison"
                if dashboard_rows is None
                else "publish marker rows differ from filtered H130 dashboard view rows"
            ),
            observed_utc=observed_utc,
            source_path=dashboard_path or root_path / "out" / "analysis_reports",
        )
    )
    if not pricing_df.empty and "execution_write_status" in pricing_df.columns:
        pricing_path = source_path.parent / "pricing_output.csv"
        pricing_stale_reason = _pricing_output_stale_reason(
            runtime_path=source_path,
            pricing_path=pricing_path,
            runtime_df=runtime_df,
            pricing_df=pricing_df,
            proof_run_id=latest_run_id if latest_run_rows else newest_runtime_run_id,
        )
        pricing_output_stale = pricing_stale_reason != ""
        rows.append(
            _health_row(
                check="repricer_tracker_pricing_output_freshness",
                status="warn" if pricing_output_stale else "ok",
                value=pricing_stale_reason,
                notes=(
                    "out/pricing_output.csv is stale audit evidence, not the latest H runtime source"
                    if pricing_output_stale
                    else "compact pricing output is not older than the runtime source"
                ),
                observed_utc=observed_utc,
                source_path=pricing_path,
            )
        )
        compact_blank = int(pricing_df["execution_write_status"].map(_normalize_text).eq("").sum())
        rows.append(
            _health_row(
                check="repricer_tracker_pricing_output_blank_execution_write_status",
                status="warn" if pricing_output_stale and compact_blank else ("fail" if compact_blank else "ok"),
                value=compact_blank,
                notes=(
                    "stale audit pricing_output has blank execution_write_status rows"
                    if pricing_output_stale and compact_blank
                    else "blank execution_write_status rows in out/pricing_output.csv"
                    if compact_blank
                    else "compact pricing output has no blank write statuses"
                ),
                observed_utc=observed_utc,
                source_path=pricing_path,
            )
        )
    return rows


def root_relative_or_str(path: Path) -> Path:
    return path


def build_repricing_tracker_view(root: Path | None = None, *, asof_utc: str | None = None) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    observed = asof_utc or _utc_now_iso()
    runtime_path = root_path / RUNTIME_REL_PATH
    terminal_info = _read_key_value_file(root_path / H_TERMINAL_INFO_REL_PATH)
    publish_info = _read_key_value_file(root_path / H_PUBLISH_INFO_REL_PATH)
    runtime_df = _read_runtime_df(root_path)
    pricing_df = _read_pricing_output_df(root_path)

    missing = _required_missing(runtime_df) if not runtime_df.empty else []
    out_rows: list[dict[str, str]] = []
    latest_terminal_run_id = _normalize_text(terminal_info.get("run_id", ""))
    publish_status = _normalize_text(publish_info.get("status", ""))
    last_publish_rows = _normalize_text(publish_info.get("rows", ""))

    if not runtime_df.empty and not missing:
        work = runtime_df.copy()
        work["_snapshot_sort"] = pd.to_datetime(work.get("snapshot_utc", ""), errors="coerce", utc=True)
        work = work.sort_values(["_snapshot_sort", "sku"], ascending=[False, True], kind="stable")
        for _, row in work.iterrows():
            sku = _normalize_text(row.get("sku", ""))
            if sku == "":
                continue
            write_status = _normalize_text(row.get("execution_write_status", "")).upper()
            write_issue = ""
            if write_status == "":
                write_issue = "blank_execution_write_status"
            elif write_status not in ALLOWED_WRITE_STATUSES:
                write_issue = "invalid_execution_write_status"
            eligible = (
                _normalize_text(row.get("current_cycle_decision", "")).lower() == "execute"
                and _normalize_text(row.get("current_cycle_decision_reason_code", "")).lower() == "eligible"
            )
            out_rows.append(
                {
                    "asof_utc": observed,
                    "source_snapshot_utc": _normalize_text(row.get("snapshot_utc", "")),
                    "source_run_id": _normalize_text(row.get("current_cycle_run_id", "")),
                    "latest_terminal_run_id": latest_terminal_run_id,
                    "sku": sku,
                    "asin": _normalize_text(row.get("asin", "")),
                    "tracker_status": _derive_tracker_status(row, write_status),
                    "capability_status": "WRITE_CAPABLE" if eligible else "READ_ONLY_OR_BLOCKED",
                    "eligible_to_write_flag": _flag_text(eligible),
                    "decision_to_change_price_flag": _flag_text(_decision_to_change_price(row, write_status)),
                    "write_attempted_flag": _normalize_text(row.get("write_attempted_flag", "")) or "0",
                    "write_applied_flag": _normalize_text(row.get("write_applied_flag", "")) or "0",
                    "raw_execution_write_status": write_status,
                    "write_status_issue": write_issue,
                    "execution_state": _normalize_text(row.get("execution_state", "")),
                    "current_cycle_decision": _normalize_text(row.get("current_cycle_decision", "")),
                    "current_cycle_decision_reason_code": _normalize_text(row.get("current_cycle_decision_reason_code", "")),
                    "current_cycle_blocker_code": _normalize_text(row.get("current_cycle_blocker_code", "")),
                    "old_price_gbp": _normalize_text(row.get("execution_old_price_gbp", "")),
                    "new_price_gbp": _normalize_text(row.get("execution_new_price_gbp", "")),
                    "hard_floor_gbp": _normalize_text(row.get("execution_hard_floor_gbp", "")),
                    "ceiling_gbp": _normalize_text(row.get("execution_final_ceiling_landed_gbp", "")),
                    "true_binding_ceiling_gbp": _normalize_text(row.get("true_binding_ceiling_gbp", "")),
                    "buy_box_state": _normalize_text(row.get("unified_buy_box_state", "")),
                    "strategy_state": _normalize_text(row.get("unified_strategy_state", "")),
                    "writer_outcome": _normalize_text(row.get("unified_writer_outcome", "")),
                    "truth_status": _normalize_text(row.get("truth_status", "")),
                    "source_path": str(runtime_path),
                    "execution_write_error": _normalize_text(row.get("execution_write_error", "")),
                    "model_ceiling_gbp": _normalize_text(row.get("execution_final_ceiling_landed_gbp", "")),
                    "trace_asof_utc": _normalize_text(row.get("trace_asof_utc", "")),
                    "trace_floor_total_gbp": _normalize_text(row.get("trace_floor_total_gbp", "")),
                    "reason_codes": _normalize_text(row.get("execution_reason_codes_json", "")),
                    "is_latest_terminal_run": _flag_text(latest_terminal_run_id != "" and _normalize_text(row.get("current_cycle_run_id", "")) == latest_terminal_run_id),
                    "publish_status": publish_status,
                    "last_publish_rows": last_publish_rows,
                }
            )

    out_df = pd.DataFrame(out_rows)
    if not out_df.empty:
        out_df = out_df.sort_values(
            by=["is_latest_terminal_run", "write_status_issue", "write_applied_flag", "sku"],
            ascending=[False, False, False, True],
            kind="stable",
        )
    out_df = write_o_contract_df(root_path, "repricer_tracker_view", out_df)

    health_rows = _build_health_rows(
        runtime_df=runtime_df,
        pricing_df=pricing_df,
        terminal_info=terminal_info,
        publish_info=publish_info,
        observed_utc=observed,
        source_path=runtime_path,
    )
    write_o_contract_df(root_path, "repricer_tracker_health", pd.DataFrame(health_rows))

    out_path = root_path / get_o_output_contract("repricer_tracker_view").rel_path
    print({"status": "success", "rows": int(len(out_df.index)), "snapshot": str(out_path)})
    return out_df


def load_repricing_tracker_view(root: Path | None = None, *, force_refresh: bool = False) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    view_df = read_o_contract_df(root_path, "repricer_tracker_view")
    if force_refresh or view_df.empty:
        view_df = build_repricing_tracker_view(root=root_path)
    return view_df


def repricer_tracker_counts(view_df: pd.DataFrame) -> dict[str, int]:
    if view_df.empty:
        return {
            "rows": 0,
            "latest_run_rows": 0,
            "write_applied": 0,
            "write_attempted": 0,
            "eligible_to_write": 0,
            "missing_write_status": 0,
        }
    return {
        "rows": int(len(view_df.index)),
        "latest_run_rows": int(view_df.get("is_latest_terminal_run", "").map(_truthy).sum()),
        "write_applied": int(view_df.get("write_applied_flag", "").map(_truthy).sum()),
        "write_attempted": int(view_df.get("write_attempted_flag", "").map(_truthy).sum()),
        "eligible_to_write": int(view_df.get("eligible_to_write_flag", "").map(_truthy).sum()),
        "missing_write_status": int(view_df.get("write_status_issue", "").map(lambda v: _normalize_text(v) == "blank_execution_write_status").sum()),
    }


def filter_repricing_tracker_view(
    view_df: pd.DataFrame,
    *,
    search_text: str = "",
    status_filter: str = "All statuses",
    current_run_only: bool = True,
    issues_only: bool = False,
    writes_only: bool = False,
) -> pd.DataFrame:
    if view_df.empty:
        return view_df.copy()
    out = view_df.copy()
    if current_run_only and "is_latest_terminal_run" in out.columns:
        out = out[out["is_latest_terminal_run"].map(_truthy)].copy()
    status = _normalize_text(status_filter)
    if status not in {"", "All statuses"}:
        out = out[out.get("tracker_status", "").map(_normalize_text) == status].copy()
    query = _normalize_text(search_text).lower()
    if query:
        mask = pd.Series(False, index=out.index)
        for column in ("sku", "asin", "execution_state", "writer_outcome", "truth_status"):
            if column in out.columns:
                mask = mask | out[column].astype(str).str.lower().str.contains(query, na=False)
        out = out[mask].copy()
    if issues_only:
        out = out[out.get("write_status_issue", "").map(_normalize_text).ne("")].copy()
    if writes_only:
        attempted = out.get("write_attempted_flag", "").map(_truthy)
        applied = out.get("write_applied_flag", "").map(_truthy)
        out = out[attempted | applied].copy()
    return out.reset_index(drop=True)


def build_repricing_tracker_glance_df(view_df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "Status",
        "SKU",
        "Old",
        "New",
        "Floor",
        "Ceiling",
        "Eligible",
        "Attempted",
        "Applied",
        "Write Result",
        "Issue",
        "State",
        "Buy Box",
        "Run",
    ]
    if view_df.empty:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(
        {
            "Status": view_df.get("tracker_status", ""),
            "SKU": view_df.get("sku", ""),
            "Old": view_df.get("old_price_gbp", ""),
            "New": view_df.get("new_price_gbp", ""),
            "Floor": view_df.get("hard_floor_gbp", ""),
            "Ceiling": view_df.get("ceiling_gbp", ""),
            "Eligible": view_df.get("eligible_to_write_flag", ""),
            "Attempted": view_df.get("write_attempted_flag", ""),
            "Applied": view_df.get("write_applied_flag", ""),
            "Write Result": view_df.get("raw_execution_write_status", ""),
            "Issue": view_df.get("write_status_issue", ""),
            "State": view_df.get("strategy_state", ""),
            "Buy Box": view_df.get("buy_box_state", ""),
            "Run": view_df.get("source_run_id", ""),
        }
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the O repricer tracker UI read model from read-only H outputs.")
    parser.add_argument("--root", default="", help="Optional root path override.")
    parser.add_argument("--asof-utc", default="", help="Optional asof UTC override.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    root = Path(args.root) if _normalize_text(args.root) else None
    asof = _normalize_text(args.asof_utc) or None
    build_repricing_tracker_view(root=root, asof_utc=asof)


if __name__ == "__main__":
    main()
