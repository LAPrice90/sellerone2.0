from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import ensure_manager_test_mode_dir
from scripts.flows.F.price_list_manager._schemas import (
    BATCH_ROW_COLUMNS,
    F061_LIVE_TRIAL_SAMPLE_COLUMNS,
    F061_STAGED_ACTIVE_RUN_COLUMNS,
    F061_STAGED_RUN_STATE_COLUMNS,
    MANAGER_HEALTH_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
    SUPPLIER_REGISTRY_COLUMNS,
)


DEFAULT_SUPPLIERS = [
    "stax",
    "heo",
    "shure_cosmetics",
    "bliss_distribution",
    "dhb",
]

REQUIRED_F061_FIELDS = ["supplier_sku", "supplier_title", "barcode", "unit_cost", "currency", "vat_rate"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _trial_safe_stamp(value: str) -> str:
    return value.replace("-", "").replace(":", "")


def _supplier_rows(registry: pd.DataFrame, supplier_ids: list[str]) -> list[pd.Series]:
    rows: list[pd.Series] = []
    for supplier_id in supplier_ids:
        supplier = registry[registry["supplier_id"].map(normalize_text) == supplier_id]
        if not supplier.empty:
            rows.append(supplier.iloc[0])
    return rows


def _latest_batch(batches: pd.DataFrame, supplier_id: str) -> pd.Series | None:
    supplier_batches = batches[
        (batches["supplier_id"].map(normalize_text) == supplier_id)
        & (batches["batch_status"].map(normalize_text) != "failed")
    ].copy()
    if supplier_batches.empty:
        return None
    supplier_batches["_received"] = supplier_batches["source_received_at_utc"].map(normalize_text)
    supplier_batches["_updated"] = supplier_batches["updated_at_utc"].map(normalize_text)
    supplier_batches = supplier_batches.sort_values(["_received", "_updated"], ascending=False, kind="stable")
    return supplier_batches.iloc[0]


def _ready_rows(batch_rows: pd.DataFrame, batch_id: str) -> pd.DataFrame:
    rows = batch_rows[batch_rows["batch_id"].map(normalize_text) == batch_id].copy()
    if rows.empty:
        return rows
    ready = rows[rows["scan_eligibility"].map(normalize_text).isin(["scan_now", "scan"])].copy()
    for column in REQUIRED_F061_FIELDS:
        if column not in ready.columns:
            ready[column] = ""
        ready = ready[ready[column].map(normalize_text) != ""]
    ready["_row_key"] = ready["row_key"].map(normalize_text)
    ready = ready.sort_values("_row_key", kind="stable")
    return ready.drop(columns=["_row_key"], errors="ignore").reset_index(drop=True)


def _build_active_run(
    *,
    rows: pd.DataFrame,
    run_id: str,
    supplier_name: str,
    source_seen_at_utc: str,
) -> pd.DataFrame:
    out_rows: list[dict[str, str]] = []
    for _, row in rows.iterrows():
        out_rows.append(
            {
                "run_id": run_id,
                "supplier_id": normalize_text(row.get("supplier_id", "")),
                "supplier_name": supplier_name,
                "row_key": normalize_text(row.get("row_key", "")),
                "supplier_sku": normalize_text(row.get("supplier_sku", "")),
                "barcode": normalize_text(row.get("barcode", "")),
                "supplier_title": normalize_text(row.get("supplier_title", "")),
                "unit_cost": normalize_text(row.get("unit_cost", "")),
                "currency": normalize_text(row.get("currency", "")) or "GBP",
                "vat_rate": normalize_text(row.get("vat_rate", "")) or "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": source_seen_at_utc,
            }
        )
    return pd.DataFrame(out_rows)


def build_f061_live_trial_samples(
    root: Path | None = None,
    *,
    trial_id: str | None = None,
    built_at_utc: str | None = None,
    sample_rows: int = 50,
    supplier_ids: list[str] | None = None,
) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=root)
    test_dir = paths.test_mode_dir
    built_at = built_at_utc or _utc_now_iso()
    trial = trial_id or f"f061_live_trial_{_trial_safe_stamp(built_at)}"
    suppliers_to_sample = supplier_ids or DEFAULT_SUPPLIERS

    registry = read_csv(test_dir / "supplier_registry.csv", SUPPLIER_REGISTRY_COLUMNS)
    batches = read_csv(test_dir / "price_list_batches.csv", PRICE_LIST_BATCH_COLUMNS)
    batch_rows = read_csv(test_dir / "batch_rows.csv", BATCH_ROW_COLUMNS)

    trial_dir = paths.system_dir / "live_trial" / trial
    sample_summary_rows: list[dict[str, str]] = []

    for supplier in _supplier_rows(registry, suppliers_to_sample):
        supplier_id = normalize_text(supplier.get("supplier_id", ""))
        supplier_name = normalize_text(supplier.get("supplier_name", "")) or supplier_id
        batch = _latest_batch(batches, supplier_id)
        if batch is None:
            sample_summary_rows.append(
                {
                    "trial_id": trial,
                    "built_at_utc": built_at,
                    "supplier_id": supplier_id,
                    "supplier_name": supplier_name,
                    "batch_id": "",
                    "source_received_at_utc": "",
                    "selected_rows": "0",
                    "held_reason": "no_imported_batch",
                    "sample_active_run_path": "",
                    "sample_run_state_path": "",
                }
            )
            continue

        batch_id = normalize_text(batch.get("batch_id", ""))
        source_seen_at_utc = normalize_text(batch.get("source_received_at_utc", "")) or built_at
        source_file_path = normalize_text(batch.get("source_file_path", ""))
        source_url = normalize_text(supplier.get("source_url", ""))
        selected = _ready_rows(batch_rows, batch_id).head(max(sample_rows, 0)).copy()
        run_id = f"{trial}_{supplier_id}"
        supplier_dir = trial_dir / supplier_id
        active_path = supplier_dir / "supplier_price_list_active_run.csv"
        state_path = supplier_dir / "supplier_price_list_run_state.csv"

        active = _build_active_run(
            rows=selected,
            run_id=run_id,
            supplier_name=supplier_name,
            source_seen_at_utc=source_seen_at_utc,
        )
        active = write_csv(active_path, active, F061_STAGED_ACTIVE_RUN_COLUMNS)

        held_reason = ""
        if len(active.index) < sample_rows:
            held_reason = f"only_{len(active.index)}_ready_rows"
        state = pd.DataFrame(
            [
                {
                    "supplier_id": supplier_id,
                    "supplier_name": supplier_name,
                    "run_id": run_id,
                    "run_status": "running" if len(active.index) else "blocked",
                    "source_url": source_url,
                    "source_file_path": source_file_path,
                    "source_seen_at_utc": source_seen_at_utc,
                    "normalized_utc": built_at,
                    "total_rows": str(len(active.index)),
                    "pending_rows": str(len(active.index)),
                    "done_rows": "0",
                    "failed_rows": "0",
                    "held_rows": "0",
                    "next_row_index": "1" if len(active.index) else "0",
                    "updated_at_utc": built_at,
                    "completed_at_utc": "",
                }
            ]
        )
        write_csv(state_path, state, F061_STAGED_RUN_STATE_COLUMNS)

        sample_summary_rows.append(
            {
                "trial_id": trial,
                "built_at_utc": built_at,
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "batch_id": batch_id,
                "source_received_at_utc": source_seen_at_utc,
                "selected_rows": str(len(active.index)),
                "held_reason": held_reason,
                "sample_active_run_path": str(active_path),
                "sample_run_state_path": str(state_path),
            }
        )

    summary_path = test_dir / "f061_live_trial_samples.csv"
    summary_df = write_csv(summary_path, pd.DataFrame(sample_summary_rows), F061_LIVE_TRIAL_SAMPLE_COLUMNS)

    missing_or_short = summary_df[summary_df["selected_rows"].map(lambda value: int(float(value or 0))) < sample_rows]
    health_status = "ok" if missing_or_short.empty and not summary_df.empty else "warn"
    health_path = test_dir / "health.csv"
    existing_health = read_csv(health_path, MANAGER_HEALTH_COLUMNS)
    health_row = pd.DataFrame(
        [
            {
                "check": "f061_live_trial_sample_build",
                "status": health_status,
                "value": str(len(summary_df.index)),
                "notes": f"trial_id={trial};sample_rows={sample_rows};short_suppliers={len(missing_or_short.index)}",
                "observed_utc": built_at,
                "source_path": str(summary_path),
            }
        ]
    )
    write_csv(health_path, pd.concat([existing_health, health_row], ignore_index=True), MANAGER_HEALTH_COLUMNS)

    result = {
        "status": "built" if not summary_df.empty else "blocked",
        "trial_id": trial,
        "sample_rows": sample_rows,
        "supplier_rows": int(len(summary_df.index)),
        "short_suppliers": int(len(missing_or_short.index)),
        "summary_path": str(summary_path),
        "trial_dir": str(trial_dir),
    }
    print(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Build 50-row F061 live trial samples from manager batches.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--trial-id", default=None)
    parser.add_argument("--built-at-utc", default=None)
    parser.add_argument("--sample-rows", type=int, default=50)
    parser.add_argument("--supplier-id", action="append", default=None)
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    build_f061_live_trial_samples(
        root=root,
        trial_id=args.trial_id,
        built_at_utc=args.built_at_utc,
        sample_rows=args.sample_rows,
        supplier_ids=args.supplier_id,
    )


if __name__ == "__main__":
    main()
