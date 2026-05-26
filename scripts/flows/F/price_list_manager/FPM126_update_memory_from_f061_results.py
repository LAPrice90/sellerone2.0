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

from scripts.flows.F._contract_io import read_f_contract_df
from scripts.flows.F._schemas import get_f_output_contract
from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import ensure_manager_test_mode_dir
from scripts.flows.F.price_list_manager._schemas import (
    BARCODE_SCAN_MEMORY_COLUMNS,
    BATCH_ROW_COLUMNS,
    MANAGER_HEALTH_COLUMNS,
)


COST_SCOPED_FAIL_CODES = {"NOCOST", "ROIFAIL", "LOWROI"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _base_candidate_id(value: object) -> str:
    raw = normalize_text(value)
    if "__alt" in raw:
        return raw.split("__alt", 1)[0]
    return raw


def _screening_result_status(row: pd.Series) -> str:
    row_status = normalize_text(row.get("row_status", "")).lower()
    pf = normalize_text(row.get("pf", "")).upper()
    fail_code = normalize_text(row.get("fail_code", "")).upper()
    if row_status == "pass" or pf == "PASS":
        return "PASS"
    if fail_code == "RESCAN" or pf == "RESCAN":
        return "RESCAN"
    if row_status == "timeout" or pf == "FAIL":
        return "FAIL"
    return ""


def _screening_fail_code(row: pd.Series, result_status: str) -> str:
    fail_code = normalize_text(row.get("fail_code", "")).upper()
    if result_status == "PASS":
        return ""
    if fail_code:
        return fail_code
    return "RESCAN" if result_status == "RESCAN" else "FAIL"


def _batch_row_lookups(batch_rows: pd.DataFrame) -> tuple[dict[tuple[str, str], pd.Series], dict[tuple[str, str, str], pd.Series], dict[tuple[str, str], pd.Series]]:
    by_candidate: dict[tuple[str, str], pd.Series] = {}
    by_sku_barcode: dict[tuple[str, str, str], pd.Series] = {}
    by_barcode: dict[tuple[str, str], pd.Series] = {}
    for _, row in batch_rows.iterrows():
        supplier_id = normalize_text(row.get("supplier_id", ""))
        row_key = normalize_text(row.get("row_key", ""))
        supplier_sku = normalize_text(row.get("supplier_sku", ""))
        barcode = normalize_text(row.get("barcode", ""))
        if supplier_id and row_key:
            by_candidate[(supplier_id, row_key)] = row
        if supplier_id and supplier_sku and barcode:
            by_sku_barcode[(supplier_id, supplier_sku, barcode)] = row
        if supplier_id and barcode:
            by_barcode[(supplier_id, barcode)] = row
    return by_candidate, by_sku_barcode, by_barcode


def _batch_row_for_screening(
    row: pd.Series,
    *,
    by_candidate: dict[tuple[str, str], pd.Series],
    by_sku_barcode: dict[tuple[str, str, str], pd.Series],
    by_barcode: dict[tuple[str, str], pd.Series],
) -> pd.Series | None:
    supplier_id = normalize_text(row.get("supplier_id", ""))
    candidate_id = _base_candidate_id(row.get("candidate_id", ""))
    supplier_sku = normalize_text(row.get("supplier_sku", ""))
    barcode = normalize_text(row.get("barcode", ""))
    if supplier_id and candidate_id:
        matched = by_candidate.get((supplier_id, candidate_id))
        if matched is not None:
            return matched
    if supplier_id and supplier_sku and barcode:
        matched = by_sku_barcode.get((supplier_id, supplier_sku, barcode))
        if matched is not None:
            return matched
    if supplier_id and barcode:
        return by_barcode.get((supplier_id, barcode))
    return None


def _memory_scopes(*, result_status: str, fail_code: str, supplier_id: str, barcode: str, unit_cost: str) -> list[tuple[str, str]]:
    if result_status == "PASS":
        scopes = [("global_barcode", f"barcode:{barcode}")]
        if unit_cost:
            scopes.append(("supplier_offer", f"supplier_offer:{supplier_id}:{barcode}:{unit_cost}"))
        return scopes
    if fail_code in COST_SCOPED_FAIL_CODES:
        return [("supplier_offer", f"supplier_offer:{supplier_id}:{barcode}:{unit_cost}")]
    return [("global_barcode", f"barcode:{barcode}")]


def _memory_rows_for_screening(row: pd.Series, batch_row: pd.Series | None, *, observed_utc: str) -> list[dict[str, str]]:
    result_status = _screening_result_status(row)
    if not result_status:
        return []
    supplier_id = normalize_text(row.get("supplier_id", ""))
    barcode = normalize_text(row.get("barcode", ""))
    if not supplier_id or not barcode:
        return []

    fail_code = _screening_fail_code(row, result_status)
    unit_cost = normalize_text(batch_row.get("unit_cost", "")) if batch_row is not None else ""
    row_key = _base_candidate_id(row.get("candidate_id", ""))
    source_row_hash = normalize_text(batch_row.get("source_row_hash", "")) if batch_row is not None else ""
    batch_id = normalize_text(batch_row.get("batch_id", "")) if batch_row is not None else ""
    scanned_at = normalize_text(row.get("updated_at_utc", "")) or normalize_text(row.get("observed_utc", "")) or observed_utc
    cooldown_until = normalize_text(row.get("timeout_until_utc", "")) if result_status != "PASS" else ""

    out: list[dict[str, str]] = []
    for memory_scope, memory_key in _memory_scopes(
        result_status=result_status,
        fail_code=fail_code,
        supplier_id=supplier_id,
        barcode=barcode,
        unit_cost=unit_cost,
    ):
        out.append(
            {
                "memory_key": memory_key,
                "memory_scope": memory_scope,
                "supplier_id": supplier_id,
                "barcode": barcode,
                "asin": normalize_text(row.get("asin", "")),
                "last_result_status": result_status,
                "last_fail_code": fail_code,
                "last_stage": normalize_text(row.get("last_stage", "")),
                "last_scanned_at_utc": scanned_at,
                "cooldown_until_utc": cooldown_until,
                "cooldown_basis": fail_code or result_status,
                "attempt_count": normalize_text(row.get("attempt_count", "")) or "1",
                "last_batch_id": batch_id or normalize_text(row.get("run_id", "")),
                "last_row_hash": source_row_hash or row_key,
                "updated_at_utc": observed_utc,
            }
        )
    return out


def _merge_memory(existing: pd.DataFrame, new_rows: pd.DataFrame) -> pd.DataFrame:
    if existing.empty:
        return new_rows.copy()
    if new_rows.empty:
        return existing.copy()
    combined = pd.concat([existing, new_rows], ignore_index=True)
    combined["_updated"] = combined["updated_at_utc"].map(normalize_text)
    combined["_order"] = range(len(combined.index))
    combined = combined.sort_values(["_updated", "_order"], ascending=[False, False], kind="stable")
    keep_rows: list[pd.Series] = []
    seen: set[str] = set()
    for _, row in combined.iterrows():
        key = normalize_text(row.get("memory_key", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        keep_rows.append(row.drop(labels=["_updated", "_order"], errors="ignore"))
    return pd.DataFrame(keep_rows, columns=BARCODE_SCAN_MEMORY_COLUMNS)


def update_memory_from_f061_results(
    root: Path | None = None,
    *,
    observed_utc: str | None = None,
    supplier_id: str = "",
    run_id: str = "",
) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=root)
    root_path = paths.root
    test_dir = paths.test_mode_dir
    observed = observed_utc or _utc_now_iso()
    memory_path = test_dir / "barcode_scan_memory.csv"
    health_path = test_dir / "health.csv"
    screening_path = root_path / get_f_output_contract("f_screening_row_state_live").rel_path

    screening = read_f_contract_df(root_path, "f_screening_row_state_live")
    batch_rows = read_csv(test_dir / "batch_rows.csv", BATCH_ROW_COLUMNS)
    memory_existing = read_csv(memory_path, BARCODE_SCAN_MEMORY_COLUMNS)

    work = screening.copy()
    if supplier_id:
        supplier_key = normalize_text(supplier_id)
        work = work[work["supplier_id"].map(normalize_text) == supplier_key].copy()
    if run_id:
        run_key = normalize_text(run_id)
        work = work[work["run_id"].map(normalize_text) == run_key].copy()

    row_status = work["row_status"].map(lambda value: normalize_text(value).lower()) if "row_status" in work.columns else pd.Series(dtype=str)
    processed = work[row_status.isin({"pass", "timeout"})].copy()
    skipped_pending_rows = int((row_status == "pending").sum()) if not work.empty else 0

    by_candidate, by_sku_barcode, by_barcode = _batch_row_lookups(batch_rows)
    memory_rows: list[dict[str, str]] = []
    imported_screening_rows = 0
    missing_barcode_rows = 0
    cost_scope_missing_cost_rows = 0
    for _, row in processed.iterrows():
        barcode = normalize_text(row.get("barcode", ""))
        if not barcode:
            missing_barcode_rows += 1
            continue
        batch_row = _batch_row_for_screening(
            row,
            by_candidate=by_candidate,
            by_sku_barcode=by_sku_barcode,
            by_barcode=by_barcode,
        )
        result_status = _screening_result_status(row)
        fail_code = _screening_fail_code(row, result_status)
        unit_cost = normalize_text(batch_row.get("unit_cost", "")) if batch_row is not None else ""
        if fail_code in COST_SCOPED_FAIL_CODES and not unit_cost:
            cost_scope_missing_cost_rows += 1
        row_memory = _memory_rows_for_screening(row, batch_row, observed_utc=observed)
        if row_memory:
            imported_screening_rows += 1
            memory_rows.extend(row_memory)

    new_memory = pd.DataFrame(memory_rows, columns=BARCODE_SCAN_MEMORY_COLUMNS)
    merged_memory = _merge_memory(memory_existing, new_memory)
    memory_written = write_csv(memory_path, merged_memory, BARCODE_SCAN_MEMORY_COLUMNS)

    duplicate_memory_keys = int(len(memory_written.index) - memory_written["memory_key"].map(normalize_text).nunique())
    import_status = "ok"
    if missing_barcode_rows:
        import_status = "fail"
    elif len(processed.index) == 0:
        import_status = "warn"
    cost_status = "ok" if cost_scope_missing_cost_rows == 0 else "warn"

    existing_health = read_csv(health_path, MANAGER_HEALTH_COLUMNS)
    health_rows = pd.DataFrame(
        [
            {
                "check": "f061_result_memory_import",
                "status": import_status,
                "value": str(imported_screening_rows),
                "notes": (
                    f"screening_rows={len(work.index)};processed_rows={len(processed.index)};"
                    f"new_memory_rows={len(new_memory.index)};skipped_pending_rows={skipped_pending_rows};"
                    f"missing_barcode_rows={missing_barcode_rows}"
                ),
                "observed_utc": observed,
                "source_path": str(screening_path),
            },
            {
                "check": "f061_result_memory_unique_keys",
                "status": "ok" if duplicate_memory_keys == 0 else "fail",
                "value": str(memory_written["memory_key"].map(normalize_text).nunique()),
                "notes": f"memory_rows={len(memory_written.index)};duplicate_memory_keys={duplicate_memory_keys}",
                "observed_utc": observed,
                "source_path": str(memory_path),
            },
            {
                "check": "f061_result_memory_cost_scope",
                "status": cost_status,
                "value": str(cost_scope_missing_cost_rows),
                "notes": "cost_sensitive_rows_missing_unit_cost",
                "observed_utc": observed,
                "source_path": str(test_dir / "batch_rows.csv"),
            },
        ]
    )
    current_health_fail_rows = int((health_rows["status"].map(lambda value: normalize_text(value).lower()) == "fail").sum())
    health = write_csv(health_path, pd.concat([existing_health, health_rows], ignore_index=True), MANAGER_HEALTH_COLUMNS)
    health_fail_rows = int((health["status"].map(lambda value: normalize_text(value).lower()) == "fail").sum())
    summary_status = (
        "success"
        if current_health_fail_rows == 0 and len(processed.index) > 0
        else ("skipped" if current_health_fail_rows == 0 else "blocked")
    )

    summary = {
        "status": summary_status,
        "screening_rows": int(len(work.index)),
        "processed_rows": int(len(processed.index)),
        "imported_screening_rows": int(imported_screening_rows),
        "new_memory_rows": int(len(new_memory.index)),
        "memory_rows": int(len(memory_written.index)),
        "unique_memory_keys": int(memory_written["memory_key"].map(normalize_text).nunique()),
        "skipped_pending_rows": int(skipped_pending_rows),
        "missing_barcode_rows": int(missing_barcode_rows),
        "cost_scope_missing_cost_rows": int(cost_scope_missing_cost_rows),
        "current_health_fail_rows": current_health_fail_rows,
        "health_fail_rows": health_fail_rows,
        "memory_path": str(memory_path),
    }
    print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Update price-list manager timeout memory from finalized live F061 results.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--observed-utc", default=None)
    parser.add_argument("--supplier-id", default="")
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    update_memory_from_f061_results(
        root=root,
        observed_utc=args.observed_utc,
        supplier_id=args.supplier_id,
        run_id=args.run_id,
    )


if __name__ == "__main__":
    main()
