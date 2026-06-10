from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

from sellerone_manager.app import main
from sellerone_manager.hourly_mot import (
    build_all_hourly_mot,
    build_h_hourly_mot,
    build_hourly_mot_for_flow,
    write_hourly_mot_outputs,
)


OBSERVED = "2026-05-27T12:00:00Z"
RUN_ID = "20260527T110000Z"


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_h_storage_registry(root: Path, *, cap: int = 5) -> None:
    path = root / "project_control" / "log_housekeeping_registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "housekeeping_output_dir": "out/housekeeping",
                "rules": [
                    {
                        "id": "h_staged_publish_snapshots",
                        "owner": "H staged publish rollback",
                        "flow": "H",
                        "storage_class": "rollback",
                        "target_type": "directory",
                        "path_globs": ["out/systems/H/staged/*"],
                        "retention": {"max_file_count": cap},
                        "health": {"fail_over_cap": True},
                        "cleanup_eligible": True,
                        "safety_blockers": ["h_run_unfinalized", "block_if_state_unknown"],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_h_staged_dirs(root: Path, *, count: int = 5) -> None:
    staged_root = root / "out" / "systems" / "H" / "staged"
    if staged_root.exists():
        shutil.rmtree(staged_root)
    staged_root.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        (staged_root / f"20260527T{index:06d}Z").mkdir()


def _write_h_cleanup_ledger(root: Path, *, cap: int = 5, status: str = "ok") -> None:
    _write_text(
        root / "out" / "systems" / "H" / "live" / "H_cleanup_ledger.jsonl",
        json.dumps(
            {
                "ts_utc": "2026-05-27T11:10:00Z",
                "policy": "h_staged_retention",
                "target": str(root / "out" / "systems" / "H" / "staged"),
                "action": "deleted",
                "reason": f"age_ttl_days=7;count_cap={cap}",
                "file_count": 0,
                "bytes_removed": 0,
                "status": status,
                "sample": [],
            }
        )
        + "\n",
    )


def _write_manifest(root: Path, *, final_state: str = "finalized", run_id: str = f"H_{RUN_ID}") -> None:
    path = root / "out" / "manifests" / "H" / "2026-05-27" / f"{run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "cycle": "H",
                "final_state": final_state,
                "start_time": "2026-05-27T11:00:00Z",
                "end_time": "2026-05-27T11:10:00Z",
                "steps": [
                    {
                        "name": "h_cycle_iteration",
                        "script_or_function": "run_H_pricing_cycle.py",
                        "rc": 0 if final_state == "finalized" else 1,
                        "step_status": "completed" if final_state == "finalized" else "failed",
                        "notes": "cause_code=ok" if final_state == "finalized" else "cause_code=TEST_FAIL",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_reliability_manifests(root: Path, states: list[str], *, health_warn_count: int = 0) -> None:
    for index, state in enumerate(states):
        minute = index + 1
        run_id = f"H_20260527T10{minute:02d}00Z"
        path = root / "out" / "manifests" / "H" / "2026-05-27" / f"{run_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        health_summary = {
            "status": "current",
            "fail_count": 0,
            "warn_count": health_warn_count if state == "warned" else 0,
            "ok_count": 10,
        }
        final_state = "failed" if state == "failed" else "completed"
        path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "cycle": "H",
                    "final_state": final_state,
                    "start_time": f"2026-05-27T10:{minute:02d}:00Z",
                    "end_time": f"2026-05-27T10:{minute:02d}:30Z",
                    "steps": [
                        {
                            "name": "h_cycle_iteration",
                            "script_or_function": "run_H_pricing_cycle.py",
                            "rc": 1 if state == "failed" else 0,
                            "step_status": "failed" if state == "failed" else "completed",
                        }
                    ],
                    "health_summary": health_summary,
                }
            )
            + "\n",
            encoding="utf-8",
        )


def _write_clean_h_evidence(root: Path) -> None:
    _write_manifest(root)
    _write_text(
        root / "out" / "systems" / "H" / "live" / "H_cycle_last_terminal_info.txt",
        (
            f"run_id={RUN_ID}\n"
            "utc=2026-05-27T11:10:00Z\n"
            "state=finalized\n"
            "stage=phase1_publish\n"
            "publish_status=ok\n"
            "failure_code=\n"
            "failure_detail=\n"
        ),
    )
    _write_text(
        root / "out" / "systems" / "H" / "live" / "H_cycle_last_publish_info.txt",
        f"run_id={RUN_ID}\nutc=2026-05-27T11:10:00Z\nrows=1\nstatus=ok\n",
    )
    _write_csv(
        root / "out" / "phase1_runtime_floor_snapshot_latest.csv",
        [
            "sku",
            "execution_write_status",
            "current_cycle_decision",
            "current_cycle_market_data_present",
            "write_attempted_flag",
            "execution_hard_floor_gbp",
            "execution_final_ceiling_landed_gbp",
            "true_binding_ceiling_gbp",
            "trace_floor_total_gbp",
        ],
        [
            {
                "sku": "SKU-H-1",
                "execution_write_status": "NO_WRITE_REQUIRED",
                "current_cycle_decision": "hold",
                "current_cycle_market_data_present": "1",
                "write_attempted_flag": "0",
                "execution_hard_floor_gbp": "1.00",
                "execution_final_ceiling_landed_gbp": "2.00",
                "true_binding_ceiling_gbp": "2.00",
                "trace_floor_total_gbp": "1.00",
            }
        ],
    )
    _write_csv(
        root / "data" / "decision_log.csv",
        ["event_ts_utc", "sku", "action", "writer_mode"],
        [{"event_ts_utc": "2026-05-27T11:05:00Z", "sku": "SKU-H-1", "action": "hold", "writer_mode": "read_only"}],
    )
    _write_csv(
        root / "data" / "execution_log.csv",
        ["event_ts_utc", "sku", "state", "write_status"],
        [
            {
                "event_ts_utc": "2026-05-27T11:05:00Z",
                "sku": "SKU-H-1",
                "state": "complete",
                "write_status": "NO_WRITE_REQUIRED",
            }
        ],
    )
    _write_csv(
        root / "out" / "phase1_sku_scope.csv",
        ["asof_utc", "sku", "asin", "repricing_enabled", "observe_enabled"],
        [{"asof_utc": "2026-05-27T11:00:00Z", "sku": "SKU-H-1", "asin": "ASIN1", "repricing_enabled": "1", "observe_enabled": "1"}],
    )
    _write_csv(
        root / "out" / "listing_offer_history.csv",
        ["timestamp_utc", "sku", "asin", "buy_box_price", "seller_detail_status"],
        [{"timestamp_utc": "2026-05-27T11:00:00Z", "sku": "SKU-H-1", "asin": "ASIN1", "buy_box_price": "2.50", "seller_detail_status": "ok"}],
    )
    _write_csv(
        root / "out" / "listing_offer_seller_observation_history.csv",
        ["timestamp_utc", "sku", "asin", "seller_id", "offer_landed_price_gbp"],
        [{"timestamp_utc": "2026-05-27T11:00:00Z", "sku": "SKU-H-1", "asin": "ASIN1", "seller_id": "SELLER1", "offer_landed_price_gbp": "2.50"}],
    )
    _write_csv(
        root / "out" / "h_floor_truth_trace.csv",
        [
            "asof_utc",
            "source_script",
            "sku",
            "floor_total_gbp",
            "candidate_price_gbp",
            "source_cogs",
            "cogs_source_token_id",
            "cogs_token_source",
            "cogs_source_batch_id",
            "cogs_source_order_key",
            "cogs_source_notes",
            "cogs_source_proof_state",
        ],
        [
            {
                "asof_utc": "2026-05-27T11:00:00Z",
                "source_script": "H110",
                "sku": "SKU-H-1",
                "floor_total_gbp": "1.00",
                "candidate_price_gbp": "2.00",
                "source_cogs": "token_ledger_live_next_available",
                "cogs_source_token_id": "TOK-CLEAN-1",
                "cogs_token_source": "purchase_receipt",
                "cogs_source_batch_id": "SR-20260527-001",
                "cogs_source_order_key": "PO-1",
                "cogs_source_notes": "",
                "cogs_source_proof_state": "clean",
            }
        ],
    )
    _write_csv(
        root / "out" / "cycle_alerts" / "checklist_H.csv",
        ["check", "status", "value", "notes"],
        [{"check": "h_sample", "status": "ok", "value": "1", "notes": ""}],
    )
    _write_h_storage_registry(root, cap=5)
    _write_h_staged_dirs(root, count=5)
    _write_h_cleanup_ledger(root, cap=5)


def _rows_by_check(result: dict[str, object]) -> dict[str, dict[str, str]]:
    return {row["check"]: row for row in result["rows"]}  # type: ignore[index]


def test_h_flow_builder_and_cli_accept_h(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)

    result = build_hourly_mot_for_flow("H", root=tmp_path, observed_utc=OBSERVED)
    assert result["flow"] == "H"

    assert main(["--hourly-mot", "--mot-flow", "H", "--root", str(tmp_path), "--observed-utc", OBSERVED]) == 0
    assert (tmp_path / "out" / "systems" / "M" / "hourly_mot_H.csv").exists()


def test_h_clean_evidence_is_manager_ok(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_reliability_manifests(tmp_path, ["clean"] * 10)

    rows = _rows_by_check(build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED))

    assert rows["h_latest_manifest_state"]["status"] == "ok"
    assert rows["h_terminal_publish_truth"]["status"] == "ok"
    assert rows["h_decision_execution_rows"]["status"] == "ok"
    assert rows["h_token_floor_source_guard"]["status"] == "ok"
    assert rows["h_defensive_listing_protection_mode"]["status"] == "ok"
    assert rows["h_reliability_window"]["status"] == "ok"
    assert rows["h_manager_readiness"]["status"] == "ok"


def test_h_token_floor_source_guard_warns_for_unproved_fallback_token(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_reliability_manifests(tmp_path, ["clean"] * 10)
    _write_csv(
        tmp_path / "out" / "phase1_runtime_floor_snapshot_latest.csv",
        [
            "sku",
            "execution_write_status",
            "current_cycle_decision",
            "current_cycle_market_data_present",
            "write_attempted_flag",
            "execution_hard_floor_gbp",
            "execution_final_ceiling_landed_gbp",
            "true_binding_ceiling_gbp",
            "trace_floor_total_gbp",
            "trace_cogs_exvat_gbp",
        ],
        [
            {
                "sku": "A2-T2AC-TW3L",
                "execution_write_status": "READ_ONLY_NO_WRITE",
                "current_cycle_decision": "execute",
                "current_cycle_market_data_present": "1",
                "write_attempted_flag": "0",
                "execution_hard_floor_gbp": "10.75",
                "execution_final_ceiling_landed_gbp": "14.00",
                "true_binding_ceiling_gbp": "14.00",
                "trace_floor_total_gbp": "10.75",
                "trace_cogs_exvat_gbp": "4.510",
            }
        ],
    )
    _write_csv(
        tmp_path / "out" / "h_floor_truth_trace.csv",
        ["asof_utc", "source_script", "sku", "floor_total_gbp", "candidate_price_gbp", "source_cogs"],
        [
            {
                "asof_utc": "2026-05-27T11:00:00Z",
                "source_script": "H110",
                "sku": "A2-T2AC-TW3L",
                "floor_total_gbp": "10.75",
                "candidate_price_gbp": "12.00",
                "source_cogs": "token_ledger_live_next_available",
            }
        ],
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            "token_id",
            "seller_sku",
            "cost_per_unit",
            "status",
            "received_date",
            "sort_rank",
            "source",
            "source_batch_id",
            "source_order_key",
            "notes",
        ],
        [
            {
                "token_id": "ADJ-FBA15LHNXF3Y-001",
                "seller_sku": "A2-T2AC-TW3L",
                "cost_per_unit": "4.51",
                "status": "available",
                "received_date": "2026-03-04",
                "sort_rank": "1",
                "source": "stock_adjustment_fallback",
                "source_batch_id": "",
                "source_order_key": "",
                "notes": "adjustment_fallback_create:FBA15LHNXF3Y",
            }
        ],
    )

    rows = _rows_by_check(build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED))

    assert rows["h_token_floor_source_guard"]["status"] == "warn"
    assert "fallback_rows=1" in rows["h_token_floor_source_guard"]["value"]
    assert "risky_or_unknown_rows=1" in rows["h_token_floor_source_guard"]["value"]
    assert "A2-T2AC-TW3L" in rows["h_token_floor_source_guard"]["value"]
    assert rows["h_manager_readiness"]["status"] == "warn"


def test_h_token_floor_source_guard_accepts_receipt_proved_fallback_token(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_reliability_manifests(tmp_path, ["clean"] * 10)
    _write_csv(
        tmp_path / "out" / "h_floor_truth_trace.csv",
        [
            "asof_utc",
            "source_script",
            "sku",
            "floor_total_gbp",
            "candidate_price_gbp",
            "source_cogs",
            "cogs_source_token_id",
            "cogs_token_source",
            "cogs_source_batch_id",
            "cogs_source_order_key",
            "cogs_source_notes",
            "cogs_source_proof_state",
        ],
        [
            {
                "asof_utc": "2026-05-27T11:00:00Z",
                "source_script": "H110",
                "sku": "SKU-H-1",
                "floor_total_gbp": "1.00",
                "candidate_price_gbp": "2.00",
                "source_cogs": "token_ledger_live_next_available",
                "cogs_source_token_id": "ADJ-PROVED-1",
                "cogs_token_source": "stock_adjustment_fallback",
                "cogs_source_batch_id": "SR-20260209-001",
                "cogs_source_order_key": "PO-1",
                "cogs_source_notes": "adjustment_fallback_create:FBA1;cost_source=receipt_proved",
                "cogs_source_proof_state": "receipt_proved",
            }
        ],
    )

    rows = _rows_by_check(build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED))

    assert rows["h_token_floor_source_guard"]["status"] == "ok"
    assert "fallback_rows=1" in rows["h_token_floor_source_guard"]["value"]
    assert "risky_or_unknown_rows=0" in rows["h_token_floor_source_guard"]["value"]


def test_h_token_floor_source_guard_warns_for_source_token_proved_fallback(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_reliability_manifests(tmp_path, ["clean"] * 10)
    _write_csv(
        tmp_path / "out" / "h_floor_truth_trace.csv",
        [
            "asof_utc",
            "source_script",
            "sku",
            "floor_total_gbp",
            "candidate_price_gbp",
            "source_cogs",
            "cogs_source_token_id",
            "cogs_token_source",
            "cogs_source_notes",
            "cogs_source_proof_state",
        ],
        [
            {
                "asof_utc": "2026-05-27T11:00:00Z",
                "source_script": "H110",
                "sku": "SKU-H-1",
                "floor_total_gbp": "1.00",
                "candidate_price_gbp": "2.00",
                "source_cogs": "token_ledger_live_next_available",
                "cogs_source_token_id": "ADJ-SOURCE-PROVED-1",
                "cogs_token_source": "stock_adjustment_fallback",
                "cogs_source_notes": "adjustment_fallback_create:FBA1;cost_source=source_token_proved",
                "cogs_source_proof_state": "source_token_proved",
            }
        ],
    )

    rows = _rows_by_check(build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED))

    assert rows["h_token_floor_source_guard"]["status"] == "warn"
    assert "fallback_rows=1" in rows["h_token_floor_source_guard"]["value"]
    assert "risky_or_unknown_rows=1" in rows["h_token_floor_source_guard"]["value"]
    assert rows["h_manager_readiness"]["status"] == "warn"


def test_h_token_floor_source_guard_uses_b071_batch_link_reconciliation(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_reliability_manifests(tmp_path, ["clean"] * 10)
    _write_csv(
        tmp_path / "out" / "h_floor_truth_trace.csv",
        [
            "asof_utc",
            "source_script",
            "sku",
            "floor_total_gbp",
            "candidate_price_gbp",
            "source_cogs",
            "cogs_source_token_id",
            "cogs_token_source",
            "cogs_source_notes",
            "cogs_source_proof_state",
        ],
        [
            {
                "asof_utc": "2026-05-27T11:00:00Z",
                "source_script": "H110",
                "sku": "SKU-H-1",
                "floor_total_gbp": "1.00",
                "candidate_price_gbp": "2.00",
                "source_cogs": "token_ledger_live_next_available",
                "cogs_source_token_id": "ADJ-BATCH-GAP-1",
                "cogs_token_source": "stock_adjustment_fallback",
                "cogs_source_notes": "adjustment_fallback_create:FBA1;cost_source=source_token_proved",
                "cogs_source_proof_state": "source_token_proved",
            }
        ],
    )
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_fallback_token_cost_audit.csv",
        [
            "token_id",
            "seller_sku",
            "cost_per_unit",
            "cost_proof_state",
            "manager_label",
            "roi_or_restock_use_allowed",
        ],
        [
            {
                "token_id": "ADJ-BATCH-GAP-1",
                "seller_sku": "SKU-H-1",
                "cost_per_unit": "1.00",
                "cost_proof_state": "fallback_cost_source_token_proved",
                "manager_label": "source_token_proved",
                "roi_or_restock_use_allowed": "0",
            }
        ],
    )
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_fallback_cost_proof_reconciliation.csv",
        ["token_id", "seller_sku", "reconciliation_rule", "clean_h_o_trust_allowed"],
        [
            {
                "token_id": "ADJ-BATCH-GAP-1",
                "seller_sku": "SKU-H-1",
                "reconciliation_rule": "requires_batch_link_proof",
                "clean_h_o_trust_allowed": "0",
            }
        ],
    )

    rows = _rows_by_check(build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED))

    assert rows["h_token_floor_source_guard"]["status"] == "warn"
    assert "fallback_rows=1" in rows["h_token_floor_source_guard"]["value"]
    assert "batch_link_proof_needed_rows=1" in rows["h_token_floor_source_guard"]["value"]
    assert "risky_or_unknown_rows=1" in rows["h_token_floor_source_guard"]["value"]
    assert rows["h_manager_readiness"]["status"] == "warn"


def test_h_token_floor_source_guard_warns_when_source_metadata_unknown(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_reliability_manifests(tmp_path, ["clean"] * 10)
    _write_csv(
        tmp_path / "out" / "h_floor_truth_trace.csv",
        ["asof_utc", "source_script", "sku", "floor_total_gbp", "candidate_price_gbp", "source_cogs"],
        [
            {
                "asof_utc": "2026-05-27T11:00:00Z",
                "source_script": "H110",
                "sku": "SKU-H-1",
                "floor_total_gbp": "1.00",
                "candidate_price_gbp": "2.00",
                "source_cogs": "token_ledger_live_next_available",
            }
        ],
    )

    rows = _rows_by_check(build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED))

    assert rows["h_token_floor_source_guard"]["status"] == "warn"
    assert "unknown_source_rows=1" in rows["h_token_floor_source_guard"]["value"]
    assert rows["h_manager_readiness"]["status"] == "warn"


def test_h_defensive_listing_preview_config_is_manager_visible(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_reliability_manifests(tmp_path, ["clean"] * 10)
    _write_csv(
        tmp_path / "config" / "h_defensive_listing_protection.csv",
        [
            "sku",
            "asin",
            "enabled",
            "mode",
            "live_write_enabled",
            "pressure_days",
            "undercut_gbp",
            "after_pressure_action",
            "reset_after_absent_hours",
            "min_margin_guard",
            "notes",
        ],
        [
            {
                "sku": "6V-EEC1-2S9Z",
                "asin": "B06WW79DX5",
                "enabled": "1",
                "mode": "pressure_then_match",
                "live_write_enabled": "0",
                "pressure_days": "30",
                "undercut_gbp": "0.01",
                "after_pressure_action": "match",
                "reset_after_absent_hours": "24",
                "min_margin_guard": "0.00",
                "notes": "test",
            }
        ],
    )

    rows = _rows_by_check(build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED))

    assert rows["h_defensive_listing_protection_mode"]["status"] == "ok"
    assert "preview_rows=1" in rows["h_defensive_listing_protection_mode"]["value"]
    assert rows["h_manager_readiness"]["status"] == "ok"


def test_h_defensive_listing_live_enabled_without_proof_warns(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_reliability_manifests(tmp_path, ["clean"] * 10)
    _write_csv(
        tmp_path / "config" / "h_defensive_listing_protection.csv",
        [
            "sku",
            "asin",
            "enabled",
            "mode",
            "live_write_enabled",
            "pressure_days",
            "undercut_gbp",
            "after_pressure_action",
            "reset_after_absent_hours",
            "min_margin_guard",
            "notes",
        ],
        [
            {
                "sku": "6V-EEC1-2S9Z",
                "asin": "B06WW79DX5",
                "enabled": "1",
                "mode": "pressure_then_match",
                "live_write_enabled": "1",
                "pressure_days": "30",
                "undercut_gbp": "0.01",
                "after_pressure_action": "match",
                "reset_after_absent_hours": "24",
                "min_margin_guard": "0.00",
                "notes": "test",
            }
        ],
    )

    rows = _rows_by_check(build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED))

    assert rows["h_defensive_listing_protection_mode"]["status"] == "warn"
    assert "live_enabled_waiting_proof" in rows["h_defensive_listing_protection_mode"]["value"]
    assert rows["h_manager_readiness"]["status"] == "warn"


def test_h_defensive_listing_live_proof_is_manager_visible(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_reliability_manifests(tmp_path, ["clean"] * 10)
    _write_csv(
        tmp_path / "config" / "h_defensive_listing_protection.csv",
        [
            "sku",
            "asin",
            "enabled",
            "mode",
            "live_write_enabled",
            "pressure_days",
            "undercut_gbp",
            "after_pressure_action",
            "reset_after_absent_hours",
            "min_margin_guard",
            "notes",
        ],
        [
            {
                "sku": "6V-EEC1-2S9Z",
                "asin": "B06WW79DX5",
                "enabled": "1",
                "mode": "pressure_then_match",
                "live_write_enabled": "1",
                "pressure_days": "30",
                "undercut_gbp": "0.01",
                "after_pressure_action": "match",
                "reset_after_absent_hours": "24",
                "min_margin_guard": "0.00",
                "notes": "test",
            }
        ],
    )
    _write_csv(
        tmp_path / "out" / "h_defensive_listing_action_log.csv",
        [
            "event_ts_utc",
            "run_id",
            "sku",
            "asin",
            "mode",
            "phase",
            "buy_box_state",
            "seller_count",
            "lowest_rival_price_gbp",
            "current_price_gbp",
            "target_price_gbp",
            "hard_floor_gbp",
            "final_ceiling_gbp",
            "write_required",
            "live_write_enabled",
            "write_status",
            "write_error",
            "attempted_write",
            "wrote",
            "reason_codes_json",
        ],
        [
            {
                "event_ts_utc": OBSERVED,
                "run_id": RUN_ID,
                "sku": "6V-EEC1-2S9Z",
                "asin": "B06WW79DX5",
                "mode": "pressure_then_match",
                "phase": "pressure_hold",
                "buy_box_state": "NORMAL",
                "seller_count": "1",
                "lowest_rival_price_gbp": "6.98",
                "current_price_gbp": "6.97",
                "target_price_gbp": "6.97",
                "hard_floor_gbp": "5.90",
                "final_ceiling_gbp": "10.64",
                "write_required": "0",
                "live_write_enabled": "1",
                "write_status": "NO_WRITE_REQUIRED",
                "write_error": "",
                "attempted_write": "0",
                "wrote": "0",
                "reason_codes_json": "[]",
            }
        ],
    )
    _write_csv(
        tmp_path / "out" / "h_defensive_listing_daily.csv",
        ["asof_date", "sku", "asin", "mode", "enabled", "live_write_enabled", "phase", "action_rows"],
        [
            {
                "asof_date": "2026-05-27",
                "sku": "6V-EEC1-2S9Z",
                    "asin": "B06WW79DX5",
                    "mode": "pressure_then_match",
                    "enabled": "1",
                    "live_write_enabled": "1",
                    "phase": "pressure_hold",
                    "action_rows": "1",
                }
            ],
    )

    rows = _rows_by_check(build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED))

    assert rows["h_defensive_listing_protection_mode"]["status"] == "ok"
    assert "proof_rows=1" in rows["h_defensive_listing_protection_mode"]["value"]
    assert "daily_rows=1" in rows["h_defensive_listing_protection_mode"]["value"]
    assert "b06_proof_rows=1" in rows["h_defensive_listing_protection_mode"]["actual_proof"]


def test_h_defensive_listing_equal_rival_valid_undercut_passes_mot(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_reliability_manifests(tmp_path, ["clean"] * 10)
    _write_csv(
        tmp_path / "config" / "h_defensive_listing_protection.csv",
        [
            "sku",
            "asin",
            "enabled",
            "mode",
            "live_write_enabled",
            "pressure_days",
            "undercut_gbp",
            "after_pressure_action",
            "reset_after_absent_hours",
            "min_margin_guard",
            "notes",
        ],
        [
            {
                "sku": "6V-EEC1-2S9Z",
                "asin": "B06WW79DX5",
                "enabled": "1",
                "mode": "pressure_then_match",
                "live_write_enabled": "1",
                "pressure_days": "30",
                "undercut_gbp": "0.01",
                "after_pressure_action": "match",
                "reset_after_absent_hours": "24",
                "min_margin_guard": "0.00",
                "notes": "test",
            }
        ],
    )
    _write_csv(
        tmp_path / "out" / "h_defensive_listing_action_log.csv",
        [
            "event_ts_utc",
            "run_id",
            "sku",
            "asin",
            "mode",
            "phase",
            "buy_box_state",
            "seller_count",
            "lowest_rival_price_gbp",
            "current_price_gbp",
            "target_price_gbp",
            "hard_floor_gbp",
            "final_ceiling_gbp",
            "write_required",
            "live_write_enabled",
            "write_status",
            "write_error",
            "attempted_write",
            "wrote",
            "reason_codes_json",
        ],
        [
            {
                "event_ts_utc": OBSERVED,
                "run_id": RUN_ID,
                "sku": "6V-EEC1-2S9Z",
                "asin": "B06WW79DX5",
                "mode": "pressure_then_match",
                "phase": "pressure_undercut",
                "buy_box_state": "NORMAL",
                "seller_count": "8",
                "lowest_rival_price_gbp": "6.98",
                "current_price_gbp": "6.98",
                "target_price_gbp": "6.97",
                "hard_floor_gbp": "5.90",
                "final_ceiling_gbp": "10.64",
                "write_required": "1",
                "live_write_enabled": "1",
                "write_status": "APPLIED",
                "write_error": "",
                "attempted_write": "1",
                "wrote": "1",
                "reason_codes_json": "[]",
            }
        ],
    )

    rows = _rows_by_check(build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED))

    assert rows["h_defensive_listing_protection_mode"]["status"] == "ok"
    assert "proof_rows=1" in rows["h_defensive_listing_protection_mode"]["value"]


def test_h_defensive_listing_normal_h_control_with_rival_present_fails_mot(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_reliability_manifests(tmp_path, ["clean"] * 10)
    _write_csv(
        tmp_path / "config" / "h_defensive_listing_protection.csv",
        [
            "sku",
            "asin",
            "enabled",
            "mode",
            "live_write_enabled",
            "pressure_days",
            "undercut_gbp",
            "after_pressure_action",
            "reset_after_absent_hours",
            "min_margin_guard",
            "notes",
        ],
        [
            {
                "sku": "6V-EEC1-2S9Z",
                "asin": "B06WW79DX5",
                "enabled": "1",
                "mode": "pressure_then_match",
                "live_write_enabled": "1",
                "pressure_days": "30",
                "undercut_gbp": "0.01",
                "after_pressure_action": "match",
                "reset_after_absent_hours": "24",
                "min_margin_guard": "0.00",
                "notes": "test",
            }
        ],
    )
    _write_csv(
        tmp_path / "out" / "h_defensive_listing_action_log.csv",
        [
            "event_ts_utc",
            "run_id",
            "sku",
            "asin",
            "mode",
            "phase",
            "buy_box_state",
            "seller_count",
            "lowest_rival_price_gbp",
            "current_price_gbp",
            "target_price_gbp",
            "hard_floor_gbp",
            "final_ceiling_gbp",
            "write_required",
            "live_write_enabled",
            "write_status",
            "write_error",
            "attempted_write",
            "wrote",
            "reason_codes_json",
        ],
        [
            {
                "event_ts_utc": OBSERVED,
                "run_id": RUN_ID,
                "sku": "6V-EEC1-2S9Z",
                "asin": "B06WW79DX5",
                "mode": "pressure_then_match",
                "phase": "normal_h_control",
                "buy_box_state": "NORMAL",
                "seller_count": "8",
                "lowest_rival_price_gbp": "6.98",
                "current_price_gbp": "6.97",
                "target_price_gbp": "",
                "hard_floor_gbp": "5.90",
                "final_ceiling_gbp": "10.64",
                "write_required": "0",
                "live_write_enabled": "1",
                "write_status": "DEFENSIVE_NOT_TRIGGERED_NORMAL_H_CONTROL",
                "write_error": "",
                "attempted_write": "0",
                "wrote": "0",
                "reason_codes_json": "[]",
            }
        ],
    )

    rows = _rows_by_check(build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED))

    assert rows["h_defensive_listing_protection_mode"]["status"] == "fail"
    assert "latest_strategy_ownership_violation=1" in rows["h_defensive_listing_protection_mode"]["value"]
    assert rows["h_manager_readiness"]["status"] == "fail"


def test_h_defensive_listing_new_clean_proof_overrides_old_bad_receipt(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_reliability_manifests(tmp_path, ["clean"] * 10)
    _write_csv(
        tmp_path / "config" / "h_defensive_listing_protection.csv",
        [
            "sku",
            "asin",
            "enabled",
            "mode",
            "live_write_enabled",
            "pressure_days",
            "undercut_gbp",
            "after_pressure_action",
            "reset_after_absent_hours",
            "min_margin_guard",
            "notes",
        ],
        [
            {
                "sku": "6V-EEC1-2S9Z",
                "asin": "B06WW79DX5",
                "enabled": "1",
                "mode": "pressure_then_match",
                "live_write_enabled": "1",
                "pressure_days": "30",
                "undercut_gbp": "0.01",
                "after_pressure_action": "match",
                "reset_after_absent_hours": "24",
                "min_margin_guard": "0.00",
                "notes": "test",
            }
        ],
    )
    _write_csv(
        tmp_path / "out" / "h_defensive_listing_action_log.csv",
        [
            "event_ts_utc",
            "run_id",
            "sku",
            "asin",
            "mode",
            "phase",
            "buy_box_state",
            "seller_count",
            "lowest_rival_price_gbp",
            "current_price_gbp",
            "target_price_gbp",
            "hard_floor_gbp",
            "final_ceiling_gbp",
            "write_required",
            "live_write_enabled",
            "write_status",
            "write_error",
            "attempted_write",
            "wrote",
            "reason_codes_json",
        ],
        [
            {
                "event_ts_utc": "2026-06-04T10:48:46Z",
                "run_id": "20260604T104846Z",
                "sku": "6V-EEC1-2S9Z",
                "asin": "B06WW79DX5",
                "mode": "balanced_defend",
                "phase": "balanced_defend",
                "buy_box_state": "NORMAL",
                "seller_count": "8",
                "lowest_rival_price_gbp": "6.98",
                "current_price_gbp": "6.98",
                "target_price_gbp": "6.97",
                "hard_floor_gbp": "5.90",
                "final_ceiling_gbp": "10.64",
                "write_required": "1",
                "live_write_enabled": "1",
                "write_status": "APPLIED",
                "write_error": "",
                "attempted_write": "1",
                "wrote": "1",
                "reason_codes_json": "[]",
            },
            {
                "event_ts_utc": "2026-06-04T12:40:59Z",
                "run_id": "20260604T124059Z",
                "sku": "6V-EEC1-2S9Z",
                "asin": "B06WW79DX5",
                "mode": "pressure_then_match",
                "phase": "pressure_hold",
                "buy_box_state": "NORMAL",
                "seller_count": "8",
                "lowest_rival_price_gbp": "6.98",
                "current_price_gbp": "6.97",
                "target_price_gbp": "6.97",
                "hard_floor_gbp": "5.90",
                "final_ceiling_gbp": "10.64",
                "write_required": "0",
                "live_write_enabled": "1",
                "write_status": "NO_WRITE_REQUIRED",
                "write_error": "",
                "attempted_write": "0",
                "wrote": "0",
                "reason_codes_json": "[]",
            },
        ],
    )

    rows = _rows_by_check(build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED))

    assert rows["h_defensive_listing_protection_mode"]["status"] == "ok"
    assert "latest_b06_status=NO_WRITE_REQUIRED" in rows["h_defensive_listing_protection_mode"]["actual_proof"]
    assert "historical_strategy_ownership_violation_rows=0" in rows["h_defensive_listing_protection_mode"]["actual_proof"]


def test_h_reliability_window_warns_when_ten_run_window_is_not_available(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)

    rows = _rows_by_check(build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED))

    assert rows["h_reliability_window"]["status"] == "warn"
    assert "window_runs=1" in rows["h_reliability_window"]["value"]
    assert rows["h_manager_readiness"]["status"] == "warn"


def test_h_reliability_window_warns_when_recent_runs_are_warning_quality(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_reliability_manifests(tmp_path, ["warned"] * 10, health_warn_count=2)

    rows = _rows_by_check(build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED))

    assert rows["h_reliability_window"]["status"] == "warn"
    assert "warned_runs=9" in rows["h_reliability_window"]["value"]
    assert rows["h_manager_readiness"]["status"] == "warn"


def test_h_reliability_window_failed_run_creates_bounded_work_item(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_reliability_manifests(tmp_path, ["clean"] * 8 + ["failed", "clean"])

    result = build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = _rows_by_check(result)
    worklist = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))

    assert rows["h_reliability_window"]["status"] == "fail"
    item = next(row for row in worklist if row["check"] == "h_reliability_window")
    assert "no H run" in item["forbidden_actions"]
    assert "no scheduler ownership changes" in item["forbidden_actions"]
    assert "no publish" in item["forbidden_actions"]
    assert "no price changes" in item["forbidden_actions"]
    assert "no queue edits" in item["forbidden_actions"]
    assert "no Google Sheets writes" in item["forbidden_actions"]
    assert "no local DB alignment" in item["forbidden_actions"]
    assert "no output deletion" in item["forbidden_actions"]
    assert "no worker restart" in item["forbidden_actions"]


def test_h_known_reliability_failed_run_is_parked_until_window_ages_out(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    run_states = [
        ("H_20260604T075221Z", "completed"),
        ("H_20260604T081505Z", "completed"),
        ("H_20260604T085245Z", "completed"),
        ("H_20260604T092150Z", "completed"),
        ("H_20260604T101005Z", "failed"),
        ("H_20260604T104846Z", "completed"),
        ("H_20260604T115527Z", "completed"),
        ("H_20260604T124059Z", "completed"),
        ("H_20260604T132114Z", "completed"),
        ("H_20260604T135804Z", "completed"),
    ]
    for run_id, final_state in run_states:
        path = tmp_path / "out" / "manifests" / "H" / "2026-06-04" / f"{run_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        health_summary = {
            "status": "current",
            "fail_count": 1 if final_state == "completed" else 0,
            "warn_count": 4 if final_state == "completed" else 0,
            "ok_count": 102,
        }
        path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "cycle": "H",
                    "final_state": final_state,
                    "steps": [
                        {
                            "name": "h_cycle_iteration",
                            "script_or_function": "run_H_pricing_cycle.py",
                            "rc": 1 if final_state == "failed" else 0,
                            "step_status": "failed" if final_state == "failed" else "completed",
                        }
                    ],
                    "health_summary": health_summary,
                }
            )
            + "\n",
            encoding="utf-8",
        )

    result = build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = _rows_by_check(result)
    worklist = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))

    assert rows["h_reliability_window"]["status"] == "fail"
    item = next(row for row in worklist if row["check"] == "h_reliability_window")
    assert item["status"] == "parked"
    assert "H_20260604T101005Z" in item["notes"]
    assert "until newer normal H receipts age it out" in item["notes"]
    assert item["luke_action_required"] == "0"


def test_h_failed_manifest_creates_bounded_work_item(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_manifest(tmp_path, final_state="failed", run_id="H_20260527T111500Z")

    result = build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = _rows_by_check(result)
    worklist = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))

    assert rows["h_latest_manifest_state"]["status"] == "fail"
    assert rows["h_manager_readiness"]["status"] == "fail"
    assert not any(row["check"] == "h_manager_readiness" for row in worklist)
    item = next(row for row in worklist if row["check"] == "h_latest_manifest_state")
    assert "no H run" in item["forbidden_actions"]
    assert "no scheduler ownership changes" in item["forbidden_actions"]
    assert "no price changes" in item["forbidden_actions"]
    assert "no queue edits" in item["forbidden_actions"]
    assert "no Google Sheets writes" in item["forbidden_actions"]
    assert "no local DB alignment" in item["forbidden_actions"]
    assert "no output deletion" in item["forbidden_actions"]
    assert "no worker restart" in item["forbidden_actions"]


def test_h_terminal_publish_run_mismatch_fails(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_text(
        tmp_path / "out" / "systems" / "H" / "live" / "H_cycle_last_publish_info.txt",
        "run_id=20260527T120000Z\nutc=2026-05-27T12:00:00Z\nrows=1\nstatus=ok\n",
    )

    rows = _rows_by_check(build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED))

    assert rows["h_terminal_publish_truth"]["status"] == "fail"
    assert "terminal_run" in rows["h_terminal_publish_truth"]["value"]


def test_h_blank_write_status_fails(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_csv(
        tmp_path / "out" / "phase1_runtime_floor_snapshot_latest.csv",
        [
            "sku",
            "execution_write_status",
            "current_cycle_decision",
            "current_cycle_market_data_present",
            "write_attempted_flag",
            "execution_hard_floor_gbp",
            "execution_final_ceiling_landed_gbp",
        ],
        [
            {
                "sku": "SKU-H-1",
                "execution_write_status": "",
                "current_cycle_decision": "hold",
                "current_cycle_market_data_present": "1",
                "write_attempted_flag": "0",
                "execution_hard_floor_gbp": "1.00",
                "execution_final_ceiling_landed_gbp": "2.00",
            }
        ],
    )

    rows = _rows_by_check(build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED))

    assert rows["h_decision_execution_rows"]["status"] == "fail"
    assert "blank_write_status_rows=1" in rows["h_decision_execution_rows"]["value"]


def test_h_floor_ceiling_ignores_no_write_skip_rows(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_csv(
        tmp_path / "out" / "phase1_runtime_floor_snapshot_latest.csv",
        [
            "sku",
            "execution_write_status",
            "current_cycle_decision",
            "current_cycle_market_data_present",
            "write_attempted_flag",
            "execution_hard_floor_gbp",
            "execution_final_ceiling_landed_gbp",
            "true_binding_ceiling_gbp",
            "trace_floor_total_gbp",
            "truth_status",
        ],
        [
            {
                "sku": "SKU-H-SKIP-MARKET",
                "execution_write_status": "READ_ONLY_NO_WRITE",
                "current_cycle_decision": "skip_no_market_data",
                "current_cycle_market_data_present": "0",
                "write_attempted_flag": "0",
                "execution_hard_floor_gbp": "",
                "execution_final_ceiling_landed_gbp": "",
                "true_binding_ceiling_gbp": "",
                "trace_floor_total_gbp": "1.00",
                "truth_status": "READ_ONLY",
            },
            {
                "sku": "SKU-H-SKIP-OFFER",
                "execution_write_status": "READ_ONLY_NO_WRITE",
                "current_cycle_decision": "skip_no_active_offer",
                "current_cycle_market_data_present": "1",
                "write_attempted_flag": "0",
                "execution_hard_floor_gbp": "1.00",
                "execution_final_ceiling_landed_gbp": "",
                "true_binding_ceiling_gbp": "",
                "trace_floor_total_gbp": "1.00",
                "truth_status": "READ_ONLY",
            },
        ],
    )

    rows = _rows_by_check(build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED))

    assert rows["h_floor_ceiling_safety_fields"]["status"] == "ok"


def test_h_floor_ceiling_still_fails_missing_write_ceiling(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_csv(
        tmp_path / "out" / "phase1_runtime_floor_snapshot_latest.csv",
        [
            "sku",
            "execution_write_status",
            "current_cycle_decision",
            "current_cycle_market_data_present",
            "write_attempted_flag",
            "execution_hard_floor_gbp",
            "execution_final_ceiling_landed_gbp",
            "true_binding_ceiling_gbp",
            "trace_floor_total_gbp",
            "truth_status",
        ],
        [
            {
                "sku": "SKU-H-WRITE",
                "execution_write_status": "APPLIED",
                "current_cycle_decision": "execute",
                "current_cycle_market_data_present": "1",
                "write_attempted_flag": "1",
                "execution_hard_floor_gbp": "1.00",
                "execution_final_ceiling_landed_gbp": "",
                "true_binding_ceiling_gbp": "",
                "trace_floor_total_gbp": "1.00",
                "truth_status": "WRITE_APPLIED",
            }
        ],
    )

    rows = _rows_by_check(build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED))

    assert rows["h_floor_ceiling_safety_fields"]["status"] == "fail"
    assert "blank_ceiling_rows=1" in rows["h_floor_ceiling_safety_fields"]["value"]


def test_h_market_context_ignores_skip_no_market_data_rows(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_csv(
        tmp_path / "out" / "phase1_runtime_floor_snapshot_latest.csv",
        [
            "sku",
            "execution_write_status",
            "current_cycle_decision",
            "current_cycle_market_data_present",
            "write_attempted_flag",
            "execution_hard_floor_gbp",
            "execution_final_ceiling_landed_gbp",
            "true_binding_ceiling_gbp",
            "trace_floor_total_gbp",
            "truth_status",
        ],
        [
            {
                "sku": "SKU-H-NO-MARKET",
                "execution_write_status": "READ_ONLY_NO_WRITE",
                "current_cycle_decision": "skip_no_market_data",
                "current_cycle_market_data_present": "0",
                "write_attempted_flag": "0",
                "execution_hard_floor_gbp": "",
                "execution_final_ceiling_landed_gbp": "",
                "true_binding_ceiling_gbp": "",
                "trace_floor_total_gbp": "1.00",
                "truth_status": "READ_ONLY",
            }
        ],
    )

    rows = _rows_by_check(build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED))

    assert rows["h_market_context_proof"]["status"] == "ok"


def test_h_market_context_still_fails_execute_without_market_data(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_csv(
        tmp_path / "out" / "phase1_runtime_floor_snapshot_latest.csv",
        [
            "sku",
            "execution_write_status",
            "current_cycle_decision",
            "current_cycle_market_data_present",
            "write_attempted_flag",
            "execution_hard_floor_gbp",
            "execution_final_ceiling_landed_gbp",
            "true_binding_ceiling_gbp",
            "trace_floor_total_gbp",
            "truth_status",
        ],
        [
            {
                "sku": "SKU-H-EXECUTE",
                "execution_write_status": "APPLIED",
                "current_cycle_decision": "execute",
                "current_cycle_market_data_present": "0",
                "write_attempted_flag": "1",
                "execution_hard_floor_gbp": "1.00",
                "execution_final_ceiling_landed_gbp": "2.00",
                "true_binding_ceiling_gbp": "2.00",
                "trace_floor_total_gbp": "1.00",
                "truth_status": "WRITE_APPLIED",
            }
        ],
    )

    rows = _rows_by_check(build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED))

    assert rows["h_market_context_proof"]["status"] == "fail"
    assert "priced_rows_missing_market_context=1" in rows["h_market_context_proof"]["value"]


def test_h_duplicate_lock_fails(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_text(
        tmp_path / "out" / "systems" / "H" / "live" / "H_pricing_cycle.lock",
        "H|pid=111|run_id=20260527T110000Z|heartbeat=2026-05-27T11:59:00Z\n",
    )
    _write_text(
        tmp_path / "out" / "H_pricing_cycle.lock",
        "H|pid=222|run_id=20260527T110001Z|heartbeat=2026-05-27T11:59:00Z\n",
    )

    rows = _rows_by_check(build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED))

    assert rows["h_lock_and_heartbeat_state"]["status"] == "fail"
    assert "duplicate_h_owners=2" in rows["h_lock_and_heartbeat_state"]["value"]


def test_h_old_checklist_fail_is_clue_not_repair_item(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_reliability_manifests(tmp_path, ["clean"] * 10)
    _write_csv(
        tmp_path / "out" / "cycle_alerts" / "checklist_H.csv",
        ["check", "status", "value", "notes"],
        [{"check": "old_h_fail", "status": "fail", "value": "1", "notes": "old clue"}],
    )

    result = build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = _rows_by_check(result)
    worklist = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))

    assert rows["h_health_snapshot_as_clue"]["status"] == "warn"
    assert rows["h_manager_readiness"]["status"] == "ok"
    assert not any(row["check"] == "h_health_snapshot_as_clue" for row in worklist)


def test_h_storage_cleanup_warns_on_registry_runtime_cap_mismatch(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    _write_reliability_manifests(tmp_path, ["clean"] * 10)
    _write_h_staged_dirs(tmp_path, count=241)
    _write_h_cleanup_ledger(tmp_path, cap=240)

    rows = _rows_by_check(build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED))

    assert rows["h_storage_cleanup_safety"]["status"] == "warn"
    assert "staged_entries=241" in rows["h_storage_cleanup_safety"]["value"]
    assert "registry_cap=5" in rows["h_storage_cleanup_safety"]["value"]
    assert "ledger_count_cap=240" in rows["h_storage_cleanup_safety"]["value"]
    assert "newest_preserved=1" in rows["h_storage_cleanup_safety"]["value"]
    assert "disagree" in rows["h_storage_cleanup_safety"]["root_cause_guess"]
    assert "separate H source-repair packet" in rows["h_storage_cleanup_safety"]["manager_action"]
    assert rows["h_manager_readiness"]["status"] == "warn"


def test_h_storage_cleanup_missing_ledger_fails_and_creates_work_item(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)
    (tmp_path / "out" / "systems" / "H" / "live" / "H_cleanup_ledger.jsonl").unlink()

    result = build_h_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = _rows_by_check(result)
    worklist = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))

    assert rows["h_storage_cleanup_safety"]["status"] == "fail"
    item = next(row for row in worklist if row["check"] == "h_storage_cleanup_safety")
    assert "no H run" in item["forbidden_actions"]
    assert "no scheduler ownership changes" in item["forbidden_actions"]
    assert "no publish" in item["forbidden_actions"]
    assert "no price changes" in item["forbidden_actions"]
    assert "no queue edits" in item["forbidden_actions"]
    assert "no Google Sheets writes" in item["forbidden_actions"]
    assert "no local DB alignment" in item["forbidden_actions"]
    assert "no output deletion" in item["forbidden_actions"]
    assert "no worker restart" in item["forbidden_actions"]


def test_all_rollup_includes_h_rows(tmp_path: Path) -> None:
    _write_clean_h_evidence(tmp_path)

    results = build_all_hourly_mot(root=tmp_path, observed_utc=OBSERVED)

    assert any(result["flow"] == "H" for result in results)

