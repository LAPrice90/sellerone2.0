from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._contract_io import f_contract_columns, read_f_contract_df, write_f_contract_df
from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract
from scripts.flows.F._schemas import get_f_output_contract


CONFIG_DIR = Path("config") / "feeder" / "suppliers"

ACTIVE_RUN_COLUMNS = [
    "run_id",
    "supplier_id",
    "supplier_name",
    "row_key",
    "supplier_sku",
    "barcode",
    "supplier_title",
    "unit_cost",
    "currency",
    "vat_rate",
    "scan_status",
    "scan_reason",
    "attempt_count",
    "last_attempt_utc",
    "finished_utc",
    "source_seen_at_utc",
]

RUN_STATE_COLUMNS = [
    "supplier_id",
    "supplier_name",
    "run_id",
    "run_status",
    "source_url",
    "source_file_path",
    "source_seen_at_utc",
    "normalized_utc",
    "total_rows",
    "pending_rows",
    "done_rows",
    "failed_rows",
    "held_rows",
    "next_row_index",
    "updated_at_utc",
    "completed_at_utc",
]

QUEUE_STATE_COLUMNS = [
    "queue_id",
    "current_supplier_id",
    "current_run_id",
    "last_completed_supplier_id",
    "next_supplier_id",
    "queue_index",
    "status",
    "updated_at_utc",
    "notes",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_lower(value: object) -> str:
    return _normalize_text(value).lower()


def _load_supplier_configs(root_path: Path) -> list[dict]:
    config_dir = root_path / CONFIG_DIR
    if not config_dir.exists():
        return []
    configs: list[dict] = []
    for path in sorted(config_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["config_path"] = str(path)
        configs.append(payload)
    return configs


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _write_csv(path: Path, df: pd.DataFrame, columns: Iterable[str]) -> None:
    out = df.copy()
    for col in columns:
        if col not in out.columns:
            out[col] = ""
    out = out[list(columns)]
    for col in columns:
        out[col] = out[col].map(_normalize_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)


def _contract_columns(contract_name: str) -> list[str]:
    return f_contract_columns(contract_name)


def _read_contract_df(contract_name: str, root_path: Path) -> pd.DataFrame:
    return read_f_contract_df(root_path, contract_name)


def _write_contract_df(df: pd.DataFrame, contract_name: str, root_path: Path) -> pd.DataFrame:
    ordered = _contract_columns(contract_name)
    out = df.copy()
    for column in ordered:
        if column not in out.columns:
            out[column] = ""
    out = out[ordered]
    for column in ordered:
        out[column] = out[column].map(_normalize_text)
    return write_f_contract_df(root_path, contract_name, out)


def _build_active_run(
    df_valid: pd.DataFrame,
    *,
    supplier_id: str,
    supplier_name: str,
    run_id: str,
    source_seen_at_utc: str,
) -> pd.DataFrame:
    if df_valid.empty:
        return pd.DataFrame(columns=ACTIVE_RUN_COLUMNS)

    rows = []
    for _, row in df_valid.iterrows():
        rows.append(
            {
                "run_id": run_id,
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "row_key": _normalize_text(row.get("row_hash", "")),
                "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                "barcode": _normalize_text(row.get("barcode", "")),
                "supplier_title": _normalize_text(row.get("supplier_title", "")),
                "unit_cost": _normalize_text(row.get("unit_cost", "")),
                "currency": _normalize_text(row.get("currency", "")),
                "vat_rate": _normalize_text(row.get("vat_rate", "")),
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": source_seen_at_utc,
            }
        )
    return pd.DataFrame(rows)


def _build_run_state(
    *,
    supplier_id: str,
    supplier_name: str,
    run_id: str,
    source_url: str,
    source_file_path: str,
    source_seen_at_utc: str,
    normalized_utc: str,
    active_run_rows: int,
) -> dict[str, str]:
    next_row_index = "1" if active_run_rows > 0 else "0"
    run_status = "running" if active_run_rows > 0 else "completed"
    completed_at = "" if run_status == "running" else _utc_now_iso()
    return {
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "run_id": run_id,
        "run_status": run_status,
        "source_url": source_url,
        "source_file_path": source_file_path,
        "source_seen_at_utc": source_seen_at_utc,
        "normalized_utc": normalized_utc,
        "total_rows": str(active_run_rows),
        "pending_rows": str(active_run_rows),
        "done_rows": "0",
        "failed_rows": "0",
        "held_rows": "0",
        "next_row_index": next_row_index,
        "updated_at_utc": _utc_now_iso(),
        "completed_at_utc": completed_at,
    }


def _clear_supplier_rows_by_name(df: pd.DataFrame, supplier_name: str) -> pd.DataFrame:
    if df.empty or "supplier" not in df.columns:
        return df.copy()
    supplier_key = _normalize_lower(supplier_name)
    if supplier_key == "":
        return df.copy()
    return df[df["supplier"].map(_normalize_lower) != supplier_key].copy()


def _clear_supplier_rows_by_id_or_name(df: pd.DataFrame, supplier_id: str, supplier_name: str) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    supplier_id_key = _normalize_lower(supplier_id)
    supplier_name_key = _normalize_lower(supplier_name)
    out = df.copy()

    if "supplier_id" in out.columns and supplier_id_key:
        out = out[out["supplier_id"].map(_normalize_lower) != supplier_id_key].copy()
    if "supplier" in out.columns:
        out = out[
            (~out["supplier"].map(_normalize_lower).isin({supplier_id_key, supplier_name_key}))
            if supplier_id_key or supplier_name_key
            else pd.Series([True] * len(out), index=out.index)
        ].copy()
    return out


def reset_supplier_test_mode(
    root: Path | None = None,
    *,
    supplier_id: str,
    clear_review_live: bool = True,
) -> dict[str, object]:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)

    supplier_key = _normalize_lower(supplier_id)
    if supplier_key == "":
        raise ValueError("supplier_id is required")

    configs = _load_supplier_configs(root_path)
    config = next((row for row in configs if _normalize_lower(row.get("supplier_id")) == supplier_key), None)
    if config is None:
        raise ValueError(f"supplier_id not found in config/feeder/suppliers: {supplier_id}")

    supplier_id_clean = _normalize_text(config.get("supplier_id", ""))
    supplier_name = _normalize_text(config.get("supplier_name", ""))
    source_url = _normalize_text(config.get("source_url", ""))

    supplier_dir = root_path / "out" / "systems" / "F" / "inbox" / "suppliers" / supplier_id_clean
    canonical_current = supplier_dir / "canonical_current.csv"
    if not canonical_current.exists():
        raise FileNotFoundError(
            f"canonical_current.csv missing for {supplier_id_clean}: {canonical_current}. "
            "Run F005 once to seed canonical source."
        )

    canonical_df = _read_csv(canonical_current)
    if canonical_df.empty:
        raise ValueError(f"canonical_current.csv is empty for {supplier_id_clean}: {canonical_current}")

    canonical_df = canonical_df[canonical_df["supplier_id"].map(_normalize_lower) == supplier_key].copy()
    if canonical_df.empty:
        raise ValueError(f"canonical_current.csv has no rows for supplier_id={supplier_id_clean}")

    source_seen_series = canonical_df["source_seen_at_utc"].map(_normalize_text)
    source_seen_candidates = [value for value in source_seen_series.tolist() if value]
    source_seen_at_utc = source_seen_candidates[0] if source_seen_candidates else _utc_now_iso()
    source_file_series = canonical_df["source_file_path"].map(_normalize_text)
    source_file_candidates = [value for value in source_file_series.tolist() if value]
    source_file_path = source_file_candidates[0] if source_file_candidates else str(canonical_current)

    run_id = f"{supplier_id_clean}_test_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    active_run = _build_active_run(
        canonical_df,
        supplier_id=supplier_id_clean,
        supplier_name=supplier_name,
        run_id=run_id,
        source_seen_at_utc=source_seen_at_utc,
    )
    run_state_row = _build_run_state(
        supplier_id=supplier_id_clean,
        supplier_name=supplier_name,
        run_id=run_id,
        source_url=source_url,
        source_file_path=source_file_path,
        source_seen_at_utc=source_seen_at_utc,
        normalized_utc=_utc_now_iso(),
        active_run_rows=int(len(active_run)),
    )

    active_contract_df = _read_contract_df("supplier_price_list_active_run", root_path)
    if not active_contract_df.empty and "supplier_id" in active_contract_df.columns:
        active_contract_df = active_contract_df[
            active_contract_df["supplier_id"].map(_normalize_lower) != supplier_key
        ].copy()
    active_contract_df = pd.concat([active_contract_df, active_run], ignore_index=True)
    active_written = _write_contract_df(active_contract_df, "supplier_price_list_active_run", root_path)
    _write_csv(supplier_dir / "active_run.csv", active_run, ACTIVE_RUN_COLUMNS)

    run_state_contract_df = _read_contract_df("supplier_price_list_run_state", root_path)
    if not run_state_contract_df.empty and "supplier_id" in run_state_contract_df.columns:
        run_state_contract_df = run_state_contract_df[
            run_state_contract_df["supplier_id"].map(_normalize_lower) != supplier_key
        ].copy()
    run_state_contract_df = pd.concat([run_state_contract_df, pd.DataFrame([run_state_row])], ignore_index=True)
    run_state_written = _write_contract_df(run_state_contract_df, "supplier_price_list_run_state", root_path)
    _write_csv(supplier_dir / "run_state.csv", pd.DataFrame([run_state_row]), RUN_STATE_COLUMNS)

    queue_state = pd.DataFrame(
        [
            {
                "queue_id": "default",
                "current_supplier_id": supplier_id_clean,
                "current_run_id": run_id,
                "last_completed_supplier_id": "",
                "next_supplier_id": "",
                "queue_index": "0",
                "status": "ok",
                "updated_at_utc": _utc_now_iso(),
                "notes": "test_mode_reset_from_canonical_current",
            }
        ]
    )
    queue_state_written = _write_contract_df(queue_state, "supplier_price_list_queue_state", root_path)

    first_checks_written = _read_contract_df("feeder_legacy_first_checks_live", root_path)
    screening_state_written = _read_contract_df("f_screening_row_state_live", root_path)
    scrape_evidence_written = _read_contract_df("feeder_legacy_scrape_evidence_live", root_path)
    chart_daily_raw_written = _read_contract_df("feeder_legacy_chart_daily_raw_live", root_path)
    second_checks_written = _read_contract_df("feeder_legacy_second_checks_live", root_path)
    bot_status_written = _read_contract_df("feeder_legacy_bot_status_live", root_path)
    if clear_review_live:
        first_checks_written = _clear_supplier_rows_by_name(first_checks_written, supplier_name)
        screening_state_written = _clear_supplier_rows_by_id_or_name(
            screening_state_written,
            supplier_id_clean,
            supplier_name,
        )
        scrape_evidence_written = _clear_supplier_rows_by_id_or_name(
            scrape_evidence_written,
            supplier_id_clean,
            supplier_name,
        )
        chart_daily_raw_written = _clear_supplier_rows_by_id_or_name(
            chart_daily_raw_written,
            supplier_id_clean,
            supplier_name,
        )
        second_checks_written = _clear_supplier_rows_by_name(second_checks_written, supplier_name)
        bot_status_written = _clear_supplier_rows_by_id_or_name(bot_status_written, supplier_id_clean, supplier_name)
        first_checks_written = _write_contract_df(first_checks_written, "feeder_legacy_first_checks_live", root_path)
        screening_state_written = _write_contract_df(
            screening_state_written,
            "f_screening_row_state_live",
            root_path,
        )
        scrape_evidence_written = _write_contract_df(
            scrape_evidence_written,
            "feeder_legacy_scrape_evidence_live",
            root_path,
        )
        chart_daily_raw_written = _write_contract_df(
            chart_daily_raw_written,
            "feeder_legacy_chart_daily_raw_live",
            root_path,
        )
        second_checks_written = _write_contract_df(second_checks_written, "feeder_legacy_second_checks_live", root_path)
        bot_status_written = _write_contract_df(bot_status_written, "feeder_legacy_bot_status_live", root_path)

    summary = {
        "status": "success",
        "supplier_id": supplier_id_clean,
        "supplier_name": supplier_name,
        "canonical_rows": int(len(canonical_df)),
        "active_supplier_rows": int(len(active_run)),
        "active_total_rows": int(len(active_written)),
        "run_state_total_rows": int(len(run_state_written)),
        "queue_state_rows": int(len(queue_state_written)),
        "cleared_review_live": bool(clear_review_live),
        "first_checks_rows_after": int(len(first_checks_written)),
        "screening_row_state_rows_after": int(len(screening_state_written)),
        "scrape_evidence_rows_after": int(len(scrape_evidence_written)),
        "chart_daily_raw_rows_after": int(len(chart_daily_raw_written)),
        "second_checks_rows_after": int(len(second_checks_written)),
        "bot_status_rows_after": int(len(bot_status_written)),
        "active_run_path": str(root_path / get_f_output_contract("supplier_price_list_active_run").rel_path),
        "canonical_path": str(canonical_current),
    }
    print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Temporary test mode reset for supplier scan queue using canonical_current.csv (no new download)."
    )
    parser.add_argument("--root", default=None)
    parser.add_argument("--supplier-id", required=True)
    parser.add_argument("--no-clear-review-live", action="store_true")
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    reset_supplier_test_mode(
        root=root,
        supplier_id=args.supplier_id,
        clear_review_live=not bool(args.no_clear_review_live),
    )


if __name__ == "__main__":
    main()
