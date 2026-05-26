from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts.flows.F._contract_io import read_f_contract_df, write_f_contract_df
from scripts.flows.F.price_list_manager import FPM130_run_live_cycle as fpm130
from scripts.flows.F.price_list_manager.FPM130_run_live_cycle import run_live_cycle_once
from scripts.flows.F.price_list_manager.FPM180_build_production_line_run import (
    PIPELINE_ROW_COLUMNS,
    PIPELINE_STAGE_MANIFEST_COLUMNS,
    PRODUCTION_LINE_STAGES,
    PipelineStageNotReady,
    build_production_line_run,
    pipeline_run_dir,
    read_completed_browser_routing,
    read_completed_stage_input,
)
from scripts.flows.F.price_list_manager._io import read_csv
from scripts.flows.F.price_list_manager._schemas import MANAGER_HEALTH_COLUMNS


SUPPLIER_ID = "test_supplier"
SUPPLIER_NAME = "Test Supplier"
RUN_ID = "fpm_test_supplier_20260522T090000Z"
OBSERVED_UTC = "2026-05-22T09:00:00Z"


def _seed_run_state(root: Path) -> None:
    write_f_contract_df(
        root,
        "supplier_price_list_run_state",
        pd.DataFrame(
            [
                {
                    "supplier_id": SUPPLIER_ID,
                    "supplier_name": SUPPLIER_NAME,
                    "run_id": RUN_ID,
                    "run_status": "running",
                    "source_url": "",
                    "source_file_path": "test_supplier.csv",
                    "source_seen_at_utc": OBSERVED_UTC,
                    "normalized_utc": OBSERVED_UTC,
                    "total_rows": "3",
                    "pending_rows": "3",
                    "done_rows": "0",
                    "failed_rows": "0",
                    "held_rows": "0",
                    "next_row_index": "1",
                    "updated_at_utc": OBSERVED_UTC,
                    "completed_at_utc": "",
                }
            ]
        ),
    )


def _active_row(
    row_key: str,
    barcode: str,
    unit_cost: str,
    *,
    scan_status: str = "pending",
    scan_reason: str = "",
) -> dict[str, str]:
    return {
        "run_id": RUN_ID,
        "supplier_id": SUPPLIER_ID,
        "supplier_name": SUPPLIER_NAME,
        "row_key": row_key,
        "supplier_sku": row_key.upper(),
        "barcode": barcode,
        "supplier_title": f"Product {row_key}",
        "unit_cost": unit_cost,
        "currency": "GBP",
        "vat_rate": "20",
        "scan_status": scan_status,
        "scan_reason": scan_reason,
        "attempt_count": "0",
        "last_attempt_utc": "",
        "finished_utc": "",
        "source_seen_at_utc": OBSERVED_UTC,
    }


def _seed_pipeline_contracts(root: Path) -> None:
    _seed_run_state(root)
    write_f_contract_df(
        root,
        "supplier_price_list_active_run",
        pd.DataFrame(
            [
                _active_row("row_pass", "500000000001", "1.00", scan_reason="browser_stage_ready"),
                _active_row("row_missing_cost", "500000000002", ""),
                _active_row("row_wait_identity", "500000000003", "2.00"),
            ]
        ),
    )
    write_f_contract_df(
        root,
        "f_screening_row_state_live",
        pd.DataFrame(
            [
                {
                    "observed_utc": OBSERVED_UTC,
                    "run_id": RUN_ID,
                    "supplier_id": SUPPLIER_ID,
                    "supplier_name": SUPPLIER_NAME,
                    "supplier_sku": "ROW_PASS",
                    "barcode": "500000000001",
                    "candidate_id": "row_pass",
                    "asin": "B000000001",
                    "row_status": "done",
                    "last_stage": "webscrape",
                    "fail_code": "",
                    "attempt_count": "1",
                    "timeout_until_utc": "",
                    "mode": "legacy_module",
                    "updated_at_utc": OBSERVED_UTC,
                    "source_seen_at_utc": OBSERVED_UTC,
                    "pf": "PASS",
                    "status_reason": "",
                    "recommendation_status": "",
                    "recommended_test_qty": "",
                }
            ]
        ),
    )


def test_completed_stage_input_rejects_incomplete_manifest(tmp_path: Path) -> None:
    stage_dir = tmp_path / "stage"
    stage_dir.mkdir()
    manifest_path = stage_dir / "manifest.csv"
    pd.DataFrame(
        [
            {
                "stage_id": "intake_enrichment",
                "stage_status": "running",
                "supplier_id": SUPPLIER_ID,
                "run_id": RUN_ID,
                "input_rows": "1",
                "passed_rows": "1",
                "blocked_rows": "0",
                "retry_rows": "0",
                "source_hash": "abc",
                "previous_manifest_path": "",
                "rows_path": str(stage_dir / "rows.csv"),
                "next_stage_input_path": str(stage_dir / "next_stage_input.csv"),
                "status_path": str(stage_dir / "status.csv"),
                "observed_utc": OBSERVED_UTC,
                "completed_at_utc": "",
                "notes": "not_complete",
            }
        ],
        columns=PIPELINE_STAGE_MANIFEST_COLUMNS,
    ).to_csv(manifest_path, index=False)

    with pytest.raises(PipelineStageNotReady, match="incomplete_manifest"):
        read_completed_stage_input(manifest_path)


def test_production_line_builds_stage_manifests_and_preserves_blocks(tmp_path: Path) -> None:
    _seed_pipeline_contracts(tmp_path)

    summary = build_production_line_run(
        root=tmp_path,
        supplier_id=SUPPLIER_ID,
        run_id=RUN_ID,
        observed_utc=OBSERVED_UTC,
        cycle_run_id="cycle_1",
    )

    run_dir = pipeline_run_dir(tmp_path, supplier_id=SUPPLIER_ID, run_id=RUN_ID)
    assert summary["status"] == "completed"
    assert summary["stage_count"] == len(PRODUCTION_LINE_STAGES)
    assert summary["input_rows"] == 3
    assert summary["final_pass_rows"] == 1
    assert summary["browser_input_rows"] == 1
    assert not list(run_dir.rglob("*.tmp.*"))

    for stage_id in PRODUCTION_LINE_STAGES:
        assert (run_dir / stage_id / "manifest.csv").exists()
        assert (run_dir / stage_id / "rows.csv").exists()
        assert (run_dir / stage_id / "status.csv").exists()

    intake_manifest = pd.read_csv(run_dir / "intake_enrichment" / "manifest.csv", dtype=str).fillna("")
    assert intake_manifest.iloc[0]["input_rows"] == "3"
    assert intake_manifest.iloc[0]["passed_rows"] == "2"
    assert intake_manifest.iloc[0]["blocked_rows"] == "1"
    assert intake_manifest.iloc[0]["retry_rows"] == "0"

    intake_rows = pd.read_csv(run_dir / "intake_enrichment" / "rows.csv", dtype=str).fillna("")
    missing_cost = intake_rows[intake_rows["candidate_id"] == "row_missing_cost"].iloc[0]
    assert missing_cost["stage_decision"] == "blocked"
    assert missing_cost["earliest_block_stage"] == "intake_enrichment"
    assert "unit_cost" in missing_cost["earliest_block_reason"]

    catalog_rows = pd.read_csv(run_dir / "catalog_identity" / "rows.csv", dtype=str).fillna("")
    waiting_identity = catalog_rows[catalog_rows["candidate_id"] == "row_wait_identity"].iloc[0]
    assert waiting_identity["stage_decision"] == "retry_later"
    assert waiting_identity["stage_reason"] == "waiting_for_catalog_identity"

    browser_input, routing_manifest = read_completed_browser_routing(run_dir)
    assert routing_manifest["routing_status"] == "completed"
    assert routing_manifest["browser_input_rows"] == "1"
    assert browser_input["candidate_id"].tolist() == ["row_pass"]
    speed_ledger = pd.read_csv(run_dir / "production_line_speed_ledger.csv", dtype=str).fillna("")
    assert speed_ledger.iloc[0]["browser_ready_rows"] == "1"
    assert speed_ledger.iloc[0]["api_stopped_rows"] == "0"


def test_browser_routing_excludes_rows_not_still_active_pending(tmp_path: Path) -> None:
    _seed_pipeline_contracts(tmp_path)
    active = read_f_contract_df(tmp_path, "supplier_price_list_active_run")
    active.loc[active["row_key"].eq("row_pass"), "scan_status"] = "done"
    write_f_contract_df(tmp_path, "supplier_price_list_active_run", active)

    summary = build_production_line_run(
        root=tmp_path,
        supplier_id=SUPPLIER_ID,
        run_id=RUN_ID,
        observed_utc=OBSERVED_UTC,
        cycle_run_id="cycle_stale_route",
    )

    run_dir = pipeline_run_dir(tmp_path, supplier_id=SUPPLIER_ID, run_id=RUN_ID)
    browser_input, routing_manifest = read_completed_browser_routing(run_dir)
    assert summary["final_pass_rows"] == 1
    assert summary["browser_input_rows"] == 0
    assert routing_manifest["browser_input_rows"] == "0"
    assert browser_input.empty


def test_browser_routing_requires_browser_stage_ready_scan_reason(tmp_path: Path) -> None:
    _seed_pipeline_contracts(tmp_path)
    active = read_f_contract_df(tmp_path, "supplier_price_list_active_run")
    active.loc[active["row_key"].eq("row_pass"), "scan_reason"] = ""
    write_f_contract_df(tmp_path, "supplier_price_list_active_run", active)

    summary = build_production_line_run(
        root=tmp_path,
        supplier_id=SUPPLIER_ID,
        run_id=RUN_ID,
        observed_utc=OBSERVED_UTC,
        cycle_run_id="cycle_not_ready",
    )

    run_dir = pipeline_run_dir(tmp_path, supplier_id=SUPPLIER_ID, run_id=RUN_ID)
    browser_input, routing_manifest = read_completed_browser_routing(run_dir)
    assert summary["final_pass_rows"] == 1
    assert summary["browser_input_rows"] == 0
    assert routing_manifest["browser_input_rows"] == "0"
    assert "active_pending_browser_ready_rows=0" in routing_manifest["notes"]
    assert browser_input.empty


def test_fpm130_writes_production_line_snapshot_after_successful_chunk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_run_state(tmp_path)
    write_f_contract_df(
        tmp_path,
        "supplier_price_list_active_run",
        pd.DataFrame(
            [
                _active_row("row_pass", "500000000001", "1.00"),
                _active_row("row_wait_identity", "500000000003", "2.00"),
            ]
        ),
    )
    monkeypatch.setattr(
        fpm130,
        "_storage_drift_preflight",
        lambda **_: {"status": "ok", "storage_drift_status": "ok"},
    )
    monkeypatch.setenv("FPM_INCREMENTAL_AI_PRECHECK_AFTER_CHUNK", "0")

    def scanner(root: Path, *, supplier_id: str, chunk_rows: int) -> dict[str, object]:
        active = read_f_contract_df(root, "supplier_price_list_active_run")
        active.loc[active["row_key"].eq("row_pass"), "scan_status"] = "done"
        write_f_contract_df(root, "supplier_price_list_active_run", active)
        write_f_contract_df(
            root,
            "f_screening_row_state_live",
            pd.DataFrame(
                [
                    {
                        "observed_utc": OBSERVED_UTC,
                        "run_id": RUN_ID,
                        "supplier_id": supplier_id,
                        "supplier_name": SUPPLIER_NAME,
                        "supplier_sku": "ROW_PASS",
                        "barcode": "500000000001",
                        "candidate_id": "row_pass",
                        "asin": "B000000001",
                        "row_status": "done",
                        "last_stage": "webscrape",
                        "fail_code": "",
                        "attempt_count": "1",
                        "timeout_until_utc": "",
                        "mode": "legacy_module",
                        "updated_at_utc": OBSERVED_UTC,
                        "source_seen_at_utc": OBSERVED_UTC,
                        "pf": "PASS",
                        "status_reason": "",
                        "recommendation_status": "",
                        "recommended_test_qty": "",
                    }
                ]
            ),
        )
        return {"status": "success", "processed_rows": 1, "pending_rows": 1, "notes": "scanner_test"}

    summary = run_live_cycle_once(
        tmp_path,
        chunk_rows=1,
        scanner_func=scanner,
        observed_utc=OBSERVED_UTC,
        cycle_run_id="cycle_1",
    )

    assert summary["status"] == "success"
    assert summary["production_line_status"] == "completed"
    run_dir = pipeline_run_dir(tmp_path, supplier_id=SUPPLIER_ID, run_id=RUN_ID)
    assert (run_dir / "pipeline_run_status.csv").exists()
    status = pd.read_csv(run_dir / "pipeline_run_status.csv", dtype=str).fillna("")
    assert status.iloc[0]["final_pass_rows"] == "1"

    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    health = read_csv(live_dir / "production_line_health.csv", MANAGER_HEALTH_COLUMNS)
    assert health.iloc[-1]["check"] == "f_production_line_stage_contract_runtime"
    assert health.iloc[-1]["status"] == "ok"
