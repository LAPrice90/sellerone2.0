from __future__ import annotations

import csv
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._contract_io import read_f_contract_df, write_f_contract_df
from scripts.flows.F.price_list_manager import FPM130_run_live_cycle as fpm130
from scripts.flows.F.price_list_manager.FPM130_run_live_cycle import run_live_cycle, run_live_cycle_once
from scripts.flows.F.price_list_manager._schemas import (
    BARCODE_SCAN_MEMORY_COLUMNS,
    BATCH_ROW_COLUMNS,
    BATCH_SCAN_ELIGIBILITY_COLUMNS,
    LIVE_CYCLE_EVENT_COLUMNS,
    LIVE_CYCLE_STATUS_COLUMNS,
    MANAGER_DECISION_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
    SUPPLIER_REGISTRY_COLUMNS,
)


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _seed_active_f061(root: Path, *, supplier_id: str = "entertainment_trading", rows: int = 5) -> None:
    active_rows = []
    for index in range(1, rows + 1):
        active_rows.append(
            {
                "run_id": "et_resume_run",
                "supplier_id": supplier_id,
                "supplier_name": "Entertainment Trading",
                "row_key": f"row_{index}",
                "supplier_sku": f"ET-{index}",
                "barcode": f"50000000000{index:02d}",
                "supplier_title": f"Product {index}",
                "unit_cost": "1.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-30T10:00:00Z",
            }
        )
    write_f_contract_df(root, "supplier_price_list_active_run", pd.DataFrame(active_rows))
    write_f_contract_df(
        root,
        "supplier_price_list_run_state",
        pd.DataFrame(
            [
                {
                    "supplier_id": supplier_id,
                    "supplier_name": "Entertainment Trading",
                    "run_id": "et_resume_run",
                    "run_status": "running",
                    "source_url": "",
                    "source_file_path": "Stocklist.xlsx",
                    "source_seen_at_utc": "2026-04-30T10:00:00Z",
                    "normalized_utc": "2026-04-30T10:00:00Z",
                    "total_rows": str(rows),
                    "pending_rows": str(rows),
                    "done_rows": "0",
                    "failed_rows": "0",
                    "held_rows": "0",
                    "next_row_index": "1",
                    "updated_at_utc": "2026-04-30T10:00:00Z",
                    "completed_at_utc": "",
                }
            ]
        ),
    )


def _seed_bad_td_synnex_active_f061(root: Path) -> None:
    write_f_contract_df(
        root,
        "supplier_price_list_active_run",
        pd.DataFrame(
            [
                {
                    "run_id": "fpm_td_synnex_20260519T090704Z",
                    "supplier_id": "td_synnex",
                    "supplier_name": "TD Synnex",
                    "row_key": "td_row_1",
                    "supplier_sku": "ADDON NETWORKING",
                    "barcode": "731304002727",
                    "supplier_title": "104.75",
                    "unit_cost": "177.55",
                    "currency": "GBP",
                    "vat_rate": "20",
                    "scan_status": "pending",
                    "scan_reason": "",
                    "attempt_count": "0",
                    "last_attempt_utc": "",
                    "finished_utc": "",
                    "source_seen_at_utc": "2026-05-19T09:07:04Z",
                }
            ]
        ),
    )
    write_f_contract_df(
        root,
        "supplier_price_list_run_state",
        pd.DataFrame(
            [
                {
                    "supplier_id": "td_synnex",
                    "supplier_name": "TD Synnex",
                    "run_id": "fpm_td_synnex_20260519T090704Z",
                    "run_status": "running",
                    "source_url": "",
                    "source_file_path": "td_synnex.csv",
                    "source_seen_at_utc": "2026-05-19T09:07:04Z",
                    "normalized_utc": "2026-05-19T09:07:04Z",
                    "total_rows": "1",
                    "pending_rows": "1",
                    "done_rows": "0",
                    "failed_rows": "0",
                    "held_rows": "0",
                    "next_row_index": "1",
                    "updated_at_utc": "2026-05-19T09:07:04Z",
                    "completed_at_utc": "",
                }
            ]
        ),
    )


def _fake_scanner(root: Path, *, supplier_id: str, chunk_rows: int) -> dict[str, object]:
    active = read_f_contract_df(root, "supplier_price_list_active_run")
    supplier_rows = active[active["supplier_id"] == supplier_id].copy()
    remaining = supplier_rows.iloc[min(chunk_rows, len(supplier_rows.index)) :].copy()
    write_f_contract_df(root, "supplier_price_list_active_run", remaining)
    write_f_contract_df(
        root,
        "supplier_price_list_run_state",
        pd.DataFrame(
            [
                {
                    "supplier_id": supplier_id,
                    "supplier_name": "Entertainment Trading",
                    "run_id": "et_resume_run",
                    "run_status": "running" if len(remaining.index) else "completed",
                    "source_url": "",
                    "source_file_path": "Stocklist.xlsx",
                    "source_seen_at_utc": "2026-04-30T10:00:00Z",
                    "normalized_utc": "2026-04-30T10:00:00Z",
                    "total_rows": str(len(supplier_rows.index)),
                    "pending_rows": str(len(remaining.index)),
                    "done_rows": str(min(chunk_rows, len(supplier_rows.index))),
                    "failed_rows": "0",
                    "held_rows": "0",
                    "next_row_index": "1" if len(remaining.index) else "0",
                    "updated_at_utc": "2026-04-30T12:00:00Z",
                    "completed_at_utc": "" if len(remaining.index) else "2026-04-30T12:00:00Z",
                }
            ]
        ),
    )
    return {
        "status": "success",
        "processed_rows": min(chunk_rows, len(supplier_rows.index)),
        "pending_rows": len(remaining.index),
        "notes": "fake_scanner",
    }


def _fake_scanner_with_screening(root: Path, *, supplier_id: str, chunk_rows: int) -> dict[str, object]:
    active = read_f_contract_df(root, "supplier_price_list_active_run")
    supplier_rows = active[active["supplier_id"] == supplier_id].copy()
    processed = supplier_rows.iloc[: min(chunk_rows, len(supplier_rows.index))].copy()
    screening_rows = []
    for _, row in processed.iterrows():
        screening_rows.append(
            {
                "observed_utc": "2026-04-30T12:00:00Z",
                "run_id": row.get("run_id", ""),
                "supplier_id": row.get("supplier_id", ""),
                "supplier_name": row.get("supplier_name", ""),
                "supplier_sku": row.get("supplier_sku", ""),
                "barcode": row.get("barcode", ""),
                "candidate_id": row.get("row_key", ""),
                "asin": "",
                "row_status": "timeout",
                "last_stage": "webscrape",
                "fail_code": "PRICEHISTORYFAIL",
                "attempt_count": "1",
                "timeout_until_utc": "2026-10-27T12:00:00Z",
                "mode": "legacy_module",
                "updated_at_utc": "2026-04-30T12:00:00Z",
                "source_seen_at_utc": row.get("source_seen_at_utc", ""),
                "pf": "FAIL",
                "status_reason": "PRICEHISTORYFAIL",
                "recommendation_status": "",
                "recommended_test_qty": "",
            }
        )
    write_f_contract_df(root, "f_screening_row_state_live", pd.DataFrame(screening_rows))
    return _fake_scanner(root, supplier_id=supplier_id, chunk_rows=chunk_rows)


def _seed_batch_rows_for_active(root: Path, *, supplier_id: str = "entertainment_trading", rows: int = 5) -> None:
    test_dir = root / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    batch_rows = []
    for index in range(1, rows + 1):
        batch_rows.append(
            {
                "batch_id": "et_batch",
                "supplier_id": supplier_id,
                "row_key": f"row_{index}",
                "supplier_sku": f"ET-{index}",
                "supplier_title": f"Product {index}",
                "barcode": f"50000000000{index:02d}",
                "unit_cost": "1.00",
                "currency": "GBP",
                "vat_rate": "20",
                "source_row_hash": f"source_hash_{index}",
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "valid",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            }
        )
    _write_csv(test_dir / "batch_rows.csv", batch_rows, BATCH_ROW_COLUMNS)


def _seed_next_batch(root: Path) -> None:
    test_dir = root / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(
        test_dir / "supplier_registry.csv",
        [
            {
                "supplier_id": "entertainment_trading",
                "supplier_name": "Entertainment Trading",
                "source_type": "manual_request",
                "source_subtype": "email_request",
                "source_url": "",
                "source_folder_path": "",
                "existing_supplier_config_path": "",
                "converter_id": "entertainment_trading",
                "normal_refresh_days": "30",
                "minimum_rescan_days": "30",
                "large_file_flag": "0",
                "manual_request_required_flag": "1",
                "priority_band": "recovery_priority",
                "active_flag": "1",
                "notes": "test",
            }
        ],
        SUPPLIER_REGISTRY_COLUMNS,
    )
    _write_csv(
        test_dir / "price_list_batches.csv",
        [
            {
                "batch_id": "et_batch",
                "supplier_id": "entertainment_trading",
                "source_type": "manual_request",
                "source_subtype": "email_request",
                "source_received_at_utc": "2026-04-30T10:00:00Z",
                "source_file_path": "Stocklist.xlsx",
                "source_file_hash": "hash",
                "converted_file_path": "et.csv",
                "source_row_count": "2",
                "valid_row_count": "2",
                "held_row_count": "0",
                "new_row_count": "2",
                "changed_row_count": "0",
                "eligible_row_count": "2",
                "skipped_cooldown_row_count": "0",
                "batch_status": "imported_from_source",
                "status_reason": "ready",
                "updated_at_utc": "2026-04-30T10:01:00Z",
            }
        ],
        PRICE_LIST_BATCH_COLUMNS,
    )
    rows = []
    eligibility = []
    for index in range(1, 3):
        rows.append(
            {
                "batch_id": "et_batch",
                "supplier_id": "entertainment_trading",
                "row_key": f"row_{index}",
                "supplier_sku": f"ET-{index}",
                "supplier_title": f"Product {index}",
                "barcode": f"50000000000{index:02d}",
                "unit_cost": "1.00",
                "currency": "GBP",
                "vat_rate": "20",
                "source_row_hash": f"hash-{index}",
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "valid",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            }
        )
        eligibility.append(
            {
                "batch_id": "et_batch",
                "supplier_id": "entertainment_trading",
                "row_key": f"row_{index}",
                "supplier_sku": f"ET-{index}",
                "barcode": f"50000000000{index:02d}",
                "unit_cost": "1.00",
                "base_eligibility": "scan_now",
                "scan_decision": "scan",
                "decision_reason": "recovery_pending",
                "memory_key": "",
                "cooldown_until_utc": "",
                "observed_utc": "2026-04-30T12:00:00Z",
            }
        )
    _write_csv(test_dir / "batch_rows.csv", rows, BATCH_ROW_COLUMNS)
    _write_csv(test_dir / "batch_scan_eligibility.csv", eligibility, BATCH_SCAN_ELIGIBILITY_COLUMNS)
    _write_csv(
        test_dir / "manager_decisions.csv",
        [
            {
                "decision_id": "next",
                "decided_at_utc": "2026-04-30T12:00:00Z",
                "recommended_action": "recommend_test_scan",
                "supplier_id": "entertainment_trading",
                "batch_id": "et_batch",
                "reason_code": "recovery_priority",
                "estimated_scan_rows": "2",
                "estimated_skip_rows": "0",
                "f061_owner_status": "idle",
                "safe_to_handoff_flag": "0",
                "notes": "test",
            }
        ],
        MANAGER_DECISION_COLUMNS,
    )


def test_fpm130_refresh_manager_outputs_includes_url_and_api_fetch(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def record(name: str):
        def inner(**kwargs: object) -> dict[str, object]:
            calls.append(name)
            assert kwargs["root"] == tmp_path
            return {"status": "success"}

        return inner

    monkeypatch.setattr(fpm130, "check_acquisition_sources", record("check_acquisition_sources"))
    monkeypatch.setattr(fpm130, "download_ready_url_sources", record("download_ready_url_sources"))
    monkeypatch.setattr(fpm130, "fetch_api_sources", record("fetch_api_sources"))
    monkeypatch.setattr(fpm130, "fetch_gmail_email_sources", record("fetch_gmail_email_sources"))
    monkeypatch.setattr(fpm130, "import_ready_sources", record("import_ready_sources"))
    monkeypatch.setattr(fpm130, "enrich_batch_rows_for_f061", record("enrich_batch_rows_for_f061"))
    monkeypatch.setattr(fpm130, "build_next_action", record("build_next_action"))
    monkeypatch.setattr(fpm130, "build_next_action_report", record("build_next_action_report"))
    monkeypatch.setattr(fpm130, "build_status_dashboard", record("build_status_dashboard"))

    fpm130._refresh_manager_outputs(tmp_path, "2026-05-19T11:20:00Z")

    assert calls == [
        "check_acquisition_sources",
        "download_ready_url_sources",
        "fetch_api_sources",
        "fetch_gmail_email_sources",
        "import_ready_sources",
        "enrich_batch_rows_for_f061",
        "build_next_action",
        "build_next_action_report",
        "build_status_dashboard",
    ]


def test_fpm130_resumes_existing_f061_active_run_before_selecting_next(tmp_path: Path) -> None:
    _seed_active_f061(tmp_path, rows=5)

    summary = run_live_cycle_once(
        root=tmp_path,
        chunk_rows=2,
        apply_next=True,
        auto_approve_next=True,
        refresh_before_select=False,
        scanner_func=_fake_scanner,
        observed_utc="2026-04-30T12:00:00Z",
        cycle_run_id="cycle_one",
    )

    status = pd.read_csv(
        tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "live_cycle_status.csv",
        dtype=str,
    ).fillna("")
    active = read_f_contract_df(tmp_path, "supplier_price_list_active_run")
    assert summary["action"] == "resume_f061_active_run"
    assert summary["supplier_id"] == "entertainment_trading"
    assert summary["pending_before"] == 5
    assert summary["pending_after"] == 3
    assert len(active.index) == 3
    assert list(status.columns) == LIVE_CYCLE_STATUS_COLUMNS
    assert status.iloc[0]["last_action"] == "resume_f061_active_run"


def test_fpm130_blocks_bad_td_synnex_active_rows_before_scanner(tmp_path: Path) -> None:
    _seed_bad_td_synnex_active_f061(tmp_path)
    calls: list[str] = []

    def scanner(root: Path, *, supplier_id: str, chunk_rows: int) -> dict[str, object]:
        calls.append(supplier_id)
        return {"status": "success", "processed_rows": 1, "pending_rows": 0, "notes": "should_not_run"}

    summary = run_live_cycle_once(
        root=tmp_path,
        chunk_rows=2,
        refresh_before_select=False,
        scanner_func=scanner,
        observed_utc="2026-05-19T10:10:00Z",
        cycle_run_id="cycle_shape_guard",
    )

    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    status = pd.read_csv(live_dir / "live_cycle_status.csv", dtype=str).fillna("")
    events = pd.read_csv(live_dir / "live_cycle_events.csv", dtype=str).fillna("")
    active = read_f_contract_df(tmp_path, "supplier_price_list_active_run")
    assert summary["status"] == "blocked_source_shape_guard"
    assert summary["action"] == "source_shape_guard"
    assert calls == []
    assert len(active.index) == 1
    assert status.iloc[0]["state"] == "blocked_source_shape_guard"
    assert status.iloc[0]["last_action"] == "source_shape_guard"
    assert "source_shape_guard:td_synnex_supplier_title_numeric_like" in status.iloc[0]["notes"]
    assert "source_shape_guard_blocked" in set(events["event_type"])


def test_fpm130_promotes_completed_login_backtrack_before_current_supplier_pending(tmp_path: Path) -> None:
    _seed_active_f061(tmp_path, supplier_id="stax", rows=1)
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=hidden|browser_state=HIDDEN|auth_state=LOGGED_IN|reason=auth_confirmed|updated_utc=2026-05-12T12:00:00Z\n",
        encoding="ascii",
    )
    (live_dir / "f061_login_mode.requested").write_text(
        "\n".join(
            [
                "requested_utc=2026-05-12T12:00:00Z",
                "requested_by=operator_ui",
                "mode=login_recovery",
                "supplier_id=stax",
                "run_id=et_resume_run",
                "status=authenticated_backlog_remaining",
                "hold_seconds=900",
            ]
        )
        + "\n",
        encoding="ascii",
    )
    write_f_contract_df(
        tmp_path,
        "f_login_backtrack_evidence_live",
        pd.DataFrame(
            [
                {
                    "backtrack_id": "bt-dhb",
                    "backtrack_observed_utc": "2026-05-07T13:04:53Z",
                    "original_observed_utc": "2026-05-07T13:04:53Z",
                    "original_run_id": "fpm_dhb_operator_20260507T083136Z",
                    "supplier_id": "dhb",
                    "supplier_name": "DHB",
                    "supplier_sku": "OB401",
                    "barcode": "4210201337546",
                    "candidate_id": "cf439f1080699fcf237fb7045d068f358e27c519",
                    "asin": "B094VK1733",
                    "unit_cost": "29.99",
                    "original_status_reason": "LOGIN_BACKTRACK_PENDING",
                    "backtrack_attempt_number": "3",
                    "backtrack_status": "dashboard_yes_no_unresolved",
                    "backtrack_error": "",
                    "merged_into_candidate_flag": "0",
                }
            ]
        ),
    )
    calls: list[str] = []

    def scanner(root: Path, *, supplier_id: str, chunk_rows: int) -> dict[str, object]:
        calls.append(supplier_id)
        return {"status": "success", "processed_rows": 0, "pending_rows": 2, "notes": "probe"}

    summary = run_live_cycle_once(
        root=tmp_path,
        chunk_rows=5,
        scanner_func=scanner,
        observed_utc="2026-05-12T12:05:00Z",
        cycle_run_id="cycle_promote",
    )

    assert summary["supplier_id"] == "dhb"
    assert calls == ["dhb"]
    active = read_f_contract_df(tmp_path, "supplier_price_list_active_run")
    assert set(active["supplier_id"]) == {"dhb", "stax"}
    dhb = active[active["supplier_id"] == "dhb"].iloc[0]
    assert dhb["scan_status"] == "login_backtrack_pending"
    assert dhb["completion_block_reason"] == "dashboard_yes_no_backtrack_required"
    events = pd.read_csv(live_dir / "live_cycle_events.csv", dtype=str).fillna("")
    assert "completed_backtrack_promoted" in set(events["event_type"])


def test_fpm130_promotes_ai_rescan_before_current_supplier_pending(tmp_path: Path) -> None:
    _seed_active_f061(tmp_path, supplier_id="td_synnex", rows=1)
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(
        test_dir / "batch_rows.csv",
        [
            {
                "batch_id": "entertainment_trading_source_1",
                "supplier_id": "entertainment_trading",
                "row_key": "et-row-1",
                "supplier_sku": "1284307",
                "supplier_title": "Thomson Streaming 4K UHD",
                "barcode": "9120106661682",
                "unit_cost": "36.82",
                "currency": "GBP",
                "vat_rate": "20",
                "source_row_hash": "et-row-1",
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "test",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            }
        ],
        BATCH_ROW_COLUMNS,
    )
    handoff = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "entertainment_trading"
        / "fpm_entertainment_trading_test"
    )
    handoff.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "supplier_id": "entertainment_trading",
                "supplier_name": "Entertainment Trading",
                "run_id": "fpm_entertainment_trading_test",
                "source_seen_at_utc": "2026-05-21T10:00:00Z",
                "source_file_path": "",
            }
        ]
    ).to_csv(handoff / "candidate_manifest.csv", index=False)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "entertainment_trading",
                "active_run_id": "fpm_entertainment_trading_test",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "et-row-1",
                "supplier_sku": "1284307",
                "asin": "B0CTKNYJP3",
                "supplier_title": "Thomson Streaming 4K UHD",
                "codex_ai_action": "rescan_needed",
            }
        ]
    ).to_csv(handoff / "ai_rescan_queue.csv", index=False)
    calls: list[str] = []

    def scanner(root: Path, *, supplier_id: str, chunk_rows: int) -> dict[str, object]:
        calls.append(supplier_id)
        return {"status": "success", "processed_rows": 0, "pending_rows": 2, "notes": "probe"}

    summary = run_live_cycle_once(
        root=tmp_path,
        chunk_rows=5,
        refresh_before_select=False,
        scanner_func=scanner,
        observed_utc="2026-05-21T12:15:00Z",
        cycle_run_id="cycle_ai_rescan",
    )

    assert summary["supplier_id"] == "entertainment_trading"
    assert calls == ["entertainment_trading"]
    active = read_f_contract_df(tmp_path, "supplier_price_list_active_run")
    promoted = active[active["supplier_id"] == "entertainment_trading"].iloc[0]
    assert promoted["scan_status"] == "pending"
    assert promoted["scan_reason"] == "rescan_retry_required"
    assert promoted["completion_block_reason"] == "rescan_retry_pending"
    assert promoted["barcode"] == "9120106661682"
    audit = pd.read_csv(handoff / "ai_rescan_promotion_audit.csv", dtype=str).fillna("")
    assert list(audit["status"]) == ["promoted"]


def test_fpm130_promotes_operator_rescan_event_before_normal_pending_rows(tmp_path: Path) -> None:
    _seed_active_f061(tmp_path, supplier_id="td_synnex", rows=3)
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(
        test_dir / "batch_rows.csv",
        [
            {
                "batch_id": "entertainment_trading_source_1",
                "supplier_id": "entertainment_trading",
                "row_key": "et-row-1",
                "supplier_sku": "KONKKS",
                "supplier_title": "Yu-Gi-Oh! Kuriboh Kollection Card Sleeves",
                "barcode": "9120106661682",
                "unit_cost": "12.34",
                "currency": "GBP",
                "vat_rate": "20",
                "source_row_hash": "et-row-1",
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "operator_rescan",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            }
        ],
        BATCH_ROW_COLUMNS,
    )
    handoff = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "entertainment_trading"
        / "fpm_entertainment_trading_test"
    )
    handoff.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "supplier_id": "entertainment_trading",
                "supplier_name": "Entertainment Trading",
                "run_id": "fpm_entertainment_trading_test",
                "source_seen_at_utc": "2026-05-21T10:00:00Z",
                "source_file_path": "",
            }
        ]
    ).to_csv(handoff / "candidate_manifest.csv", index=False)
    write_f_contract_df(
        tmp_path,
        "feeder_review_events",
        pd.DataFrame(
            [
                {
                    "event_utc": "2026-05-21T12:10:00Z",
                    "event_id": "operator-rescan-1",
                    "active_supplier_id": "entertainment_trading",
                    "active_run_id": "fpm_entertainment_trading_test",
                    "review_pack_type": "near_misses",
                    "review_batch_id": "near_miss_batch_001",
                    "candidate_id": "et-row-1",
                    "supplier_sku": "KONKKS",
                    "asin_raw": "B09HKZWBDN",
                    "asin_padded": "B09HKZWBDN",
                    "amazon_dp_url": "https://www.amazon.co.uk/dp/B09HKZWBDN",
                    "review_decision": "rescan",
                    "review_reason_code": "",
                    "review_note": "needs fresh scanner evidence before ordering",
                    "actor": "tester",
                    "source_reference": "unit_test",
                    "title": "Yu-Gi-Oh! Kuriboh Kollection Card Sleeves",
                }
            ]
        ),
    )
    calls: list[str] = []

    def scanner(root: Path, *, supplier_id: str, chunk_rows: int) -> dict[str, object]:
        calls.append(supplier_id)
        return {"status": "success", "processed_rows": 0, "pending_rows": 3, "notes": "probe"}

    summary = run_live_cycle_once(
        root=tmp_path,
        chunk_rows=5,
        refresh_before_select=False,
        scanner_func=scanner,
        observed_utc="2026-05-21T12:15:00Z",
        cycle_run_id="cycle_operator_rescan",
    )

    assert summary["supplier_id"] == "entertainment_trading"
    assert calls == ["entertainment_trading"]
    active = read_f_contract_df(tmp_path, "supplier_price_list_active_run")
    promoted = active[active["supplier_id"] == "entertainment_trading"].iloc[0]
    assert promoted["scan_status"] == "pending"
    assert promoted["scan_reason"] == "rescan_retry_required"
    assert promoted["completion_block_reason"] == "rescan_retry_pending"
    assert promoted["supplier_sku"] == "KONKKS"
    assert promoted["barcode"] == "9120106661682"
    audit = pd.read_csv(handoff / "ai_rescan_promotion_audit.csv", dtype=str).fillna("")
    assert list(audit["status"]) == ["promoted"]
    assert list(audit["notes"]) == ["source_queue=operator_rescan_events.csv"]
    status = pd.read_csv(
        tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "ai_rescan_promotion_status.csv",
        dtype=str,
    ).fillna("")
    assert status.iloc[-1]["queue_rows"] == "1"
    assert status.iloc[-1]["promoted_rows"] == "1"


def test_fpm130_ai_rescan_promotion_is_idempotent(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(
        test_dir / "batch_rows.csv",
        [
            {
                "batch_id": "entertainment_trading_source_1",
                "supplier_id": "entertainment_trading",
                "row_key": "et-row-1",
                "supplier_sku": "1284307",
                "supplier_title": "Thomson Streaming 4K UHD",
                "barcode": "9120106661682",
                "unit_cost": "36.82",
                "currency": "GBP",
                "vat_rate": "20",
                "source_row_hash": "et-row-1",
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "test",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            }
        ],
        BATCH_ROW_COLUMNS,
    )
    handoff = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "entertainment_trading"
        / "fpm_entertainment_trading_test"
    )
    handoff.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "supplier_id": "entertainment_trading",
                "supplier_name": "Entertainment Trading",
                "run_id": "fpm_entertainment_trading_test",
                "source_seen_at_utc": "2026-05-21T10:00:00Z",
                "source_file_path": "",
            }
        ]
    ).to_csv(handoff / "candidate_manifest.csv", index=False)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "entertainment_trading",
                "active_run_id": "fpm_entertainment_trading_test",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "et-row-1",
                "supplier_sku": "1284307",
                "asin": "B0CTKNYJP3",
                "supplier_title": "Thomson Streaming 4K UHD",
                "codex_ai_action": "rescan_needed",
            }
        ]
    ).to_csv(handoff / "ai_rescan_queue.csv", index=False)
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    first = fpm130._promote_ai_rescan_queue_rows(
        root=tmp_path,
        live_dir=live_dir,
        observed_utc="2026-05-21T12:15:00Z",
        cycle_run_id="cycle_ai_rescan",
    )
    second = fpm130._promote_ai_rescan_queue_rows(
        root=tmp_path,
        live_dir=live_dir,
        observed_utc="2026-05-21T12:16:00Z",
        cycle_run_id="cycle_ai_rescan",
    )

    active = read_f_contract_df(tmp_path, "supplier_price_list_active_run")
    audit = pd.read_csv(handoff / "ai_rescan_promotion_audit.csv", dtype=str).fillna("")
    assert first["promoted_rows"] == 1
    assert second["promoted_rows"] == 0
    assert second["skipped_rows"] == 1
    assert len(active.index) == 1
    assert len(audit.index) == 1


def test_fpm130_promotes_backtrack_when_auth_confirmed_even_if_request_was_still_required(tmp_path: Path) -> None:
    _seed_active_f061(tmp_path, supplier_id="stax", rows=1)
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=hidden|browser_state=HIDDEN|auth_state=LOGGED_IN|reason=auth_confirmed|updated_utc=2026-05-12T12:00:00Z\n",
        encoding="ascii",
    )
    (live_dir / "f061_login_mode.requested").write_text(
        "\n".join(
            [
                "requested_utc=2026-05-12T12:00:00Z",
                "requested_by=operator_ui",
                "mode=login_recovery",
                "supplier_id=stax",
                "run_id=et_resume_run",
                "status=still_required",
                "hold_seconds=900",
            ]
        )
        + "\n",
        encoding="ascii",
    )
    write_f_contract_df(
        tmp_path,
        "f_login_backtrack_evidence_live",
        pd.DataFrame(
            [
                {
                    "backtrack_id": "bt-stax",
                    "backtrack_observed_utc": "2026-05-12T11:04:53Z",
                    "original_observed_utc": "2026-05-12T11:04:53Z",
                    "original_run_id": "et_resume_run",
                    "supplier_id": "stax",
                    "supplier_name": "Stax",
                    "supplier_sku": "STX-LOGIN",
                    "barcode": "5000000000009",
                    "candidate_id": "stax-login-row",
                    "asin": "B000000001",
                    "unit_cost": "9.99",
                    "original_status_reason": "LOGIN_BACKTRACK_PENDING",
                    "backtrack_attempt_number": "1",
                    "backtrack_status": "missing_dashboard_yes_no",
                    "backtrack_error": "",
                    "merged_into_candidate_flag": "0",
                }
            ]
        ),
    )
    calls: list[str] = []

    def scanner(root: Path, *, supplier_id: str, chunk_rows: int) -> dict[str, object]:
        calls.append(supplier_id)
        return {"status": "success", "processed_rows": 0, "pending_rows": 2, "notes": "probe"}

    summary = run_live_cycle_once(
        root=tmp_path,
        chunk_rows=5,
        scanner_func=scanner,
        observed_utc="2026-05-12T12:05:00Z",
        cycle_run_id="cycle_promote_still_required",
    )

    assert summary["supplier_id"] == "stax"
    assert calls == ["stax"]
    active = read_f_contract_df(tmp_path, "supplier_price_list_active_run")
    promoted = active[active["row_key"] == "stax-login-row"].iloc[0]
    assert promoted["scan_status"] == "login_backtrack_pending"
    assert promoted["completion_block_reason"] == "dashboard_yes_no_backtrack_required"
    events = pd.read_csv(live_dir / "live_cycle_events.csv", dtype=str).fillna("")
    assert "completed_backtrack_promoted" in set(events["event_type"])


def test_fpm130_upgrades_existing_active_pending_row_to_login_backtrack(tmp_path: Path) -> None:
    _seed_active_f061(tmp_path, supplier_id="stax", rows=2)
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=hidden|browser_state=HIDDEN|auth_state=LOGGED_IN|reason=auth_confirmed|updated_utc=2026-05-12T12:00:00Z\n",
        encoding="ascii",
    )
    write_f_contract_df(
        tmp_path,
        "f_login_backtrack_evidence_live",
        pd.DataFrame(
            [
                {
                    "backtrack_id": "bt-existing-stax",
                    "backtrack_observed_utc": "2026-05-12T11:04:53Z",
                    "original_observed_utc": "2026-05-12T11:04:53Z",
                    "original_run_id": "et_resume_run",
                    "supplier_id": "stax",
                    "supplier_name": "Stax",
                    "supplier_sku": "ET-2",
                    "barcode": "5000000000002",
                    "candidate_id": "row_2",
                    "asin": "B000000002",
                    "unit_cost": "9.99",
                    "original_status_reason": "LOGIN_BACKTRACK_PENDING",
                    "backtrack_attempt_number": "1",
                    "backtrack_status": "missing_dashboard_yes_no",
                    "backtrack_error": "",
                    "merged_into_candidate_flag": "0",
                }
            ]
        ),
    )
    calls: list[str] = []

    def scanner(root: Path, *, supplier_id: str, chunk_rows: int) -> dict[str, object]:
        calls.append(supplier_id)
        return {"status": "success", "processed_rows": 0, "pending_rows": 2, "notes": "probe"}

    run_live_cycle_once(
        root=tmp_path,
        chunk_rows=5,
        scanner_func=scanner,
        observed_utc="2026-05-12T12:05:00Z",
        cycle_run_id="cycle_upgrade_existing",
    )

    active = read_f_contract_df(tmp_path, "supplier_price_list_active_run")
    assert len(active.index) == 2
    upgraded = active[active["row_key"] == "row_2"].iloc[0]
    assert upgraded["scan_status"] == "login_backtrack_pending"
    assert upgraded["scan_reason"] == "login_backtrack_required"
    assert upgraded["completion_block_reason"] == "dashboard_yes_no_backtrack_required"
    assert calls == ["stax"]


def test_fpm130_latest_backtrack_is_scoped_by_supplier_run_and_candidate(tmp_path: Path) -> None:
    ledger = pd.DataFrame(
        [
            {
                "backtrack_observed_utc": "2026-05-13T10:00:00Z",
                "original_run_id": "run_a",
                "supplier_id": "stax",
                "candidate_id": "same-row",
                "backtrack_attempt_number": "1",
                "backtrack_status": "missing_dashboard_yes_no",
                "merged_into_candidate_flag": "0",
            },
            {
                "backtrack_observed_utc": "2026-05-13T11:00:00Z",
                "original_run_id": "run_b",
                "supplier_id": "stax",
                "candidate_id": "same-row",
                "backtrack_attempt_number": "1",
                "backtrack_status": "resolved",
                "merged_into_candidate_flag": "0",
            },
        ]
    )

    rows = fpm130._latest_unmerged_login_backtrack_rows(ledger)

    assert len(rows) == 1
    assert rows[0]["original_run_id"] == "run_a"


def test_fpm130_live_loop_sleeps_for_blocked_statuses() -> None:
    assert fpm130._live_loop_sleep_seconds("blocked", 10) == 60
    assert fpm130._live_loop_sleep_seconds("blocked_state_regression", 10) == 60
    assert fpm130._live_loop_sleep_seconds("blocked_source_shape_guard", 10) == 60
    assert fpm130._live_loop_sleep_seconds("blocked_source_shape_guard", 0) == 60
    assert fpm130._live_loop_sleep_seconds("already_running", 0) == 1
    assert fpm130._live_loop_sleep_seconds("success", 10) == 10
    assert fpm130._live_loop_sleep_seconds("success", 0) == 0


def test_fpm130_imports_f061_memory_after_successful_chunk(tmp_path: Path) -> None:
    _seed_active_f061(tmp_path, rows=2)
    _seed_batch_rows_for_active(tmp_path, rows=2)

    summary = run_live_cycle_once(
        root=tmp_path,
        chunk_rows=1,
        apply_next=True,
        auto_approve_next=True,
        refresh_before_select=False,
        scanner_func=_fake_scanner_with_screening,
        observed_utc="2026-04-30T12:00:00Z",
        cycle_run_id="cycle_memory",
    )

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    memory = pd.read_csv(test_dir / "barcode_scan_memory.csv", dtype=str).fillna("")
    events = pd.read_csv(
        tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "live_cycle_events.csv",
        dtype=str,
    ).fillna("")
    by_key = memory.set_index("memory_key")
    memory_event = events[events["event_type"] == "f061_memory_import"].iloc[0]

    assert summary["status"] == "success"
    assert summary["memory_import_status"] == "success"
    assert list(memory.columns) == BARCODE_SCAN_MEMORY_COLUMNS
    assert by_key.loc["barcode:5000000000001", "last_fail_code"] == "PRICEHISTORYFAIL"
    assert by_key.loc["barcode:5000000000001", "last_row_hash"] == "source_hash_1"
    assert memory_event["status"] == "success"
    assert memory_event["rows"] == "1"


def test_fpm130_scanner_child_defaults_to_minimized_browser(monkeypatch) -> None:
    monkeypatch.delenv("F061_BACKGROUND_BROWSER_MODE", raising=False)
    monkeypatch.delenv("F061_SHOW_WINDOWS", raising=False)
    monkeypatch.delenv("FPM_LIVE_HIDE_SCRAPER_WINDOWS", raising=False)

    env = fpm130._build_scanner_child_env()

    assert env["F061_BACKGROUND_BROWSER_MODE"] == "minimized"
    assert env["F061_SHOW_WINDOWS"] == "0"
    assert env["FPM_LIVE_HIDE_SCRAPER_WINDOWS"] == "1"


def test_fpm130_scanner_child_timeout_default_and_override(monkeypatch) -> None:
    monkeypatch.delenv("FPM_F061_CHILD_TIMEOUT_SECONDS", raising=False)
    assert fpm130._scanner_child_timeout_seconds(5) == 1800.0
    assert fpm130._scanner_child_timeout_seconds(50) == 18000.0

    monkeypatch.setenv("FPM_F061_CHILD_TIMEOUT_SECONDS", "45")
    assert fpm130._scanner_child_timeout_seconds(50) == 45.0


def test_fpm130_scanner_child_stall_default_and_override(monkeypatch) -> None:
    monkeypatch.delenv("FPM_F061_CHILD_STALL_SECONDS", raising=False)
    assert fpm130._scanner_child_stall_seconds() == 600.0

    monkeypatch.setenv("FPM_F061_CHILD_STALL_SECONDS", "30")
    assert fpm130._scanner_child_stall_seconds() == 30.0


def test_fpm130_manager_mode_prioritizes_login_catchup_and_restart() -> None:
    assert (
        fpm130._manager_mode_for_child(
            auth_state="AMAZON_DASHBOARD_LOGIN_REQUIRED",
            browser_mode="visible",
            browser_visibility_state="visible",
            login_mode_child=True,
        )
        == "Login Window Open"
    )
    assert (
        fpm130._manager_mode_for_child(
            auth_state="LOGGED_IN",
            browser_mode="minimized",
            browser_visibility_state="hidden",
            login_mode_child=True,
        )
        == "Catching Up"
    )
    assert (
        fpm130._manager_mode_for_child(
            auth_state="LOGGED_IN",
            browser_mode="minimized",
            browser_visibility_state="hidden",
            login_mode_child=False,
            child_status="stalled",
        )
        == "Restarting Scanner"
    )


def test_fpm130_scanner_child_turns_visible_after_auth_attention(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("F061_BACKGROUND_BROWSER_MODE", raising=False)
    monkeypatch.delenv("F061_SHOW_WINDOWS", raising=False)
    monkeypatch.delenv("FPM_LIVE_HIDE_SCRAPER_WINDOWS", raising=False)
    monkeypatch.setenv("FPM_F061_AUTO_VISIBLE_AUTH_ATTENTION", "1")
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    _write_csv(
        live_dir / "live_cycle_events.csv",
        [
            {
                "event_utc": "2026-04-30T12:00:00Z",
                "cycle_run_id": "cycle",
                "event_type": "f061_auth_attention",
                "supplier_id": "",
                "f061_run_id": "",
                "status": "attention_needed",
                "rows": "1",
                "notes": "browser_block_signal_seen",
            }
        ],
        LIVE_CYCLE_EVENT_COLUMNS,
    )

    env = fpm130._build_scanner_child_env(tmp_path)

    assert env["F061_BACKGROUND_BROWSER_MODE"] == "visible"
    assert env["F061_SHOW_WINDOWS"] == "1"
    assert env["FPM_LIVE_HIDE_SCRAPER_WINDOWS"] == "0"


def test_fpm130_login_mode_request_forces_visible_child_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "minimized")
    monkeypatch.delenv("F061_SHOW_WINDOWS", raising=False)
    monkeypatch.delenv("FPM_LIVE_HIDE_SCRAPER_WINDOWS", raising=False)
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    request_path = live_dir / "f061_login_mode.requested"
    request_path.write_text(
        "\n".join(
            [
                "requested_utc=2026-05-09T11:20:00Z",
                "requested_by=operator_ui",
                "controller_owner=F_LOGIN_CONTROLLER_REWRITE_V1",
                "mode=login_recovery",
                "supplier_id=stax",
                "run_id=fpm_stax_20260507T151124Z",
                "status=requested",
                "hold_seconds=45",
                "reason=operator_login_button",
            ]
        )
        + "\n",
        encoding="ascii",
    )
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=visible|browser_state=VISIBLE|auth_state=LOGIN_REQUIRED|reason=auth_attention_required|updated_utc=2026-05-09T11:21:00Z\n",
        encoding="utf-8",
    )

    env = fpm130._build_scanner_child_env(tmp_path)

    assert env["F061_BACKGROUND_BROWSER_MODE"] == "visible"
    assert env["F061_SHOW_WINDOWS"] == "1"
    assert env["FPM_LIVE_HIDE_SCRAPER_WINDOWS"] == "0"
    assert env["F061_LOGIN_MODE"] == "1"
    assert env["F061_LOGIN_HOLD_SECONDS"] == "45"
    assert env["F061_MANUAL_BBP_LOGIN_WAIT_SECONDS"] == "45"
    assert env["F061_LOGIN_MODE_REQUEST_PATH"] == str(request_path)


def test_fpm130_login_mode_request_minimizes_child_when_auth_is_saved(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "visible")
    monkeypatch.delenv("F061_SHOW_WINDOWS", raising=False)
    monkeypatch.delenv("FPM_LIVE_HIDE_SCRAPER_WINDOWS", raising=False)
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    request_path = live_dir / "f061_login_mode.requested"
    request_path.write_text(
        "\n".join(
            [
                "requested_utc=2026-05-09T11:20:00Z",
                "requested_by=operator_ui",
                "controller_owner=F_LOGIN_CONTROLLER_REWRITE_V1",
                "mode=login_recovery",
                "supplier_id=stax",
                "run_id=fpm_stax_20260507T151124Z",
                "status=requested",
                "hold_seconds=45",
                "reason=operator_login_button",
            ]
        )
        + "\n",
        encoding="ascii",
    )
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=hidden|browser_state=HIDDEN|auth_state=LOGGED_IN|reason=login_mode_authenticated|updated_utc=2026-05-09T11:21:00Z\n",
        encoding="utf-8",
    )

    env = fpm130._build_scanner_child_env(tmp_path)

    assert env["F061_BACKGROUND_BROWSER_MODE"] == "minimized"
    assert env["F061_SHOW_WINDOWS"] == "0"
    assert env["FPM_LIVE_HIDE_SCRAPER_WINDOWS"] == "1"
    assert env["F061_LOGIN_MODE"] == "1"
    assert env["F061_LOGIN_HOLD_SECONDS"] == "45"
    assert env["F061_MANUAL_BBP_LOGIN_WAIT_SECONDS"] == "45"
    assert env["F061_LOGIN_MODE_REQUEST_PATH"] == str(request_path)


def test_fpm130_still_required_seller_central_proof_keeps_scanner_browser_visible(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("F061_BACKGROUND_BROWSER_MODE", raising=False)
    monkeypatch.delenv("F061_SHOW_WINDOWS", raising=False)
    monkeypatch.delenv("FPM_LIVE_HIDE_SCRAPER_WINDOWS", raising=False)
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    request_path = live_dir / "f061_login_mode.requested"
    request_path.write_text(
        "\n".join(
            [
                "requested_utc=2026-06-02T09:40:00Z",
                "requested_by=operator_ui",
                "mode=login_recovery",
                "supplier_id=td_synnex",
                "run_id=fpm_td_synnex_20260519T095000Z",
                "status=still_required",
                "hold_seconds=45",
                "reason=operator_login_button",
            ]
        )
        + "\n",
        encoding="ascii",
    )
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=hidden|browser_state=HIDDEN|auth_state=LOGGED_IN|reason=login_mode_authenticated|updated_utc=2026-06-02T09:41:00Z\n",
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "observed_utc": "2026-06-02T09:41:26Z",
                "context": "dashboard_yes_no_login",
                "status": "disabled",
                "reason": "auto_login_disabled",
                "seller_central_signin_detected": "1",
                "seller_central_otp_detected": "0",
            }
        ]
    ).to_csv(live_dir / "seller_central_login_recovery_proof.csv", index=False)

    env = fpm130._build_scanner_child_env(tmp_path)

    assert fpm130._scanner_browser_mode_for_next_child(tmp_path) == "visible"
    assert env["F061_BACKGROUND_BROWSER_MODE"] == "visible"
    assert env["F061_SHOW_WINDOWS"] == "1"
    assert env["FPM_LIVE_HIDE_SCRAPER_WINDOWS"] == "0"
    assert env["F061_LOGIN_MODE"] == "1"
    assert env["F061_LOGIN_HOLD_SECONDS"] == "45"
    assert env["F061_MANUAL_BBP_LOGIN_WAIT_SECONDS"] == "45"
    assert env["F061_LOGIN_MODE_REQUEST_PATH"] == str(request_path)


def test_fpm130_auto_capable_seller_central_proof_does_not_force_manual_visible_mode(
    tmp_path: Path,
) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    request_path = live_dir / "f061_login_mode.requested"
    request_path.write_text(
        "\n".join(
            [
                "requested_utc=2026-06-06T14:30:00Z",
                "requested_by=operator_ui",
                "mode=login_recovery",
                "status=still_required",
                "hold_seconds=45",
                "reason=operator_login_button",
            ]
        )
        + "\n",
        encoding="ascii",
    )
    pd.DataFrame(
        [
            {
                "observed_utc": "2026-06-06T14:31:00Z",
                "context": "dashboard_yes_no_login",
                "status": "waiting_for_code",
                "reason": "otp_page_detected",
                "seller_central_signin_detected": "0",
                "seller_central_otp_detected": "1",
                "auto_login_enabled": "1",
                "secret_file_exists": "1",
                "credentials_present": "1",
            }
        ]
    ).to_csv(live_dir / "seller_central_login_recovery_proof.csv", index=False)

    request = fpm130._read_login_mode_request(live_dir)
    env = fpm130._build_scanner_child_env(tmp_path)

    assert fpm130._seller_central_eligibility_login_pending(live_dir) is True
    assert fpm130._seller_central_eligibility_login_requires_visible(live_dir) is False
    assert fpm130._login_mode_request_active_for_child(live_dir=live_dir, request=request) is False
    assert env["F061_BACKGROUND_BROWSER_MODE"] == "minimized"
    assert env["F061_SHOW_WINDOWS"] == "0"
    assert "F061_LOGIN_MODE" not in env


def test_fpm130_exhausted_email_continue_forces_visible_child_after_first_prompt(
    tmp_path: Path,
) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_seller_central_window_shown.marker").write_text(
        "2026-06-07T20:54:13Z\n",
        encoding="utf-8",
    )
    request_path = live_dir / "f061_login_mode.requested"
    request_path.write_text(
        "\n".join(
            [
                "requested_utc=2026-06-05T13:43:19Z",
                "requested_by=operator_ui",
                "mode=login_recovery",
                "status=authenticated_backlog_remaining",
                "hold_seconds=60",
                "reason=operator_login_button",
            ]
        )
        + "\n",
        encoding="ascii",
    )
    pd.DataFrame(
        [
            {
                "observed_utc": "2026-06-07T20:54:13Z",
                "context": "dashboard_yes_no_login",
                "status": "failed",
                "reason": "email_continue_not_advanced",
                "seller_central_signin_detected": "1",
                "seller_central_otp_detected": "0",
                "auto_login_enabled": "1",
                "secret_file_exists": "1",
                "credentials_present": "1",
                "notes": (
                    "page_hint=sellercentral_url|signin_url|email_field|continue_button;"
                    "email_finalize=1;click=1;js_click=1;enter=0;js_enter=1;"
                    "form_submit=1;email_value=present"
                ),
            }
        ]
    ).to_csv(live_dir / "seller_central_login_recovery_proof.csv", index=False)

    request = fpm130._read_login_mode_request(live_dir)
    env = fpm130._build_scanner_child_env(tmp_path)

    assert fpm130._seller_central_eligibility_login_pending(live_dir) is True
    assert fpm130._seller_central_eligibility_login_requires_visible(live_dir) is True
    assert fpm130._login_mode_request_active_for_child(live_dir=live_dir, request=request) is True
    assert fpm130._scanner_browser_mode_for_next_child(tmp_path) == "visible"
    assert env["F061_BACKGROUND_BROWSER_MODE"] == "visible"
    assert env["F061_SHOW_WINDOWS"] == "1"
    assert env["FPM_LIVE_HIDE_SCRAPER_WINDOWS"] == "0"
    assert env["F061_LOGIN_MODE"] == "1"
    assert env["F061_LOGIN_MODE_REQUEST_PATH"] == str(request_path)


def test_fpm130_inactive_request_cannot_hide_exhausted_email_continue_child(
    tmp_path: Path,
) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_login_mode.requested").write_text(
        "\n".join(
            [
                "requested_utc=2026-06-05T13:43:19Z",
                "requested_by=operator_ui",
                "mode=login_recovery",
                "status=canceled",
                "hold_seconds=0",
                "reason=old_request",
            ]
        )
        + "\n",
        encoding="ascii",
    )
    pd.DataFrame(
        [
            {
                "observed_utc": "2026-06-07T20:54:13Z",
                "context": "dashboard_yes_no_login",
                "status": "failed",
                "reason": "email_continue_not_advanced",
                "seller_central_signin_detected": "1",
                "seller_central_otp_detected": "0",
                "auto_login_enabled": "1",
                "secret_file_exists": "1",
                "credentials_present": "1",
                "notes": (
                    "page_hint=sellercentral_url|signin_url|email_field|continue_button;"
                    "email_finalize=1;click=1;js_click=1;enter=0;js_enter=1;"
                    "form_submit=1;email_value=present"
                ),
            }
        ]
    ).to_csv(live_dir / "seller_central_login_recovery_proof.csv", index=False)

    env = fpm130._build_scanner_child_env(tmp_path)

    assert fpm130._seller_central_eligibility_login_requires_visible(live_dir) is True
    assert fpm130._scanner_browser_mode_for_next_child(tmp_path) == "visible"
    assert env["F061_BACKGROUND_BROWSER_MODE"] == "visible"
    assert env["F061_SHOW_WINDOWS"] == "1"
    assert env["FPM_LIVE_HIDE_SCRAPER_WINDOWS"] == "0"
    assert env["F061_LOGIN_MODE"] == "1"


def test_fpm130_manual_challenge_still_uses_manual_visible_fallback(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    request_path = live_dir / "f061_login_mode.requested"
    request_path.write_text(
        "\n".join(
            [
                "requested_utc=2026-06-06T14:30:00Z",
                "requested_by=f_login_controller",
                "mode=login_recovery",
                "status=still_required",
                "hold_seconds=45",
                "reason=manual_challenge_required",
            ]
        )
        + "\n",
        encoding="ascii",
    )
    pd.DataFrame(
        [
            {
                "observed_utc": "2026-06-06T14:31:00Z",
                "context": "dashboard_yes_no_login",
                "status": "blocked",
                "reason": "manual_challenge_required",
                "seller_central_signin_detected": "1",
                "seller_central_otp_detected": "0",
                "auto_login_enabled": "1",
                "secret_file_exists": "1",
                "credentials_present": "1",
            }
        ]
    ).to_csv(live_dir / "seller_central_login_recovery_proof.csv", index=False)

    request = fpm130._read_login_mode_request(live_dir)
    env = fpm130._build_scanner_child_env(tmp_path)

    assert fpm130._seller_central_eligibility_login_requires_visible(live_dir) is True
    assert fpm130._login_mode_request_active_for_child(live_dir=live_dir, request=request) is True
    assert env["F061_BACKGROUND_BROWSER_MODE"] == "visible"
    assert env["F061_LOGIN_MODE"] == "1"


def test_fpm130_reactivates_drained_login_mode_for_remaining_backtrack_rows(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    request_path = live_dir / "f061_login_mode.requested"
    request_path.write_text(
        "requested_utc=2026-05-09T11:20:00Z\n"
        "requested_by=operator_ui\n"
        "mode=login_recovery\n"
        "supplier_id=stax\n"
        "run_id=fpm_stax_20260507T151124Z\n"
        "status=drained\n"
        "hold_seconds=900\n"
        "reason=operator_login_button\n",
        encoding="ascii",
    )
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=hidden|browser_state=HIDDEN|auth_state=LOGGED_IN|reason=login_mode_authenticated|updated_utc=2026-05-12T14:04:37Z\n",
        encoding="utf-8",
    )
    active = pd.DataFrame(
        [
            {
                "run_id": "fpm_dhb_operator_20260507T083136Z",
                "supplier_id": "dhb",
                "row_key": "candidate-dhb",
                "scan_status": "login_backtrack_pending",
                "scan_reason": "login_backtrack_required",
                "completion_block_reason": "dashboard_yes_no_backtrack_required",
            }
        ]
    )

    request = fpm130._ensure_login_mode_request_for_active_backtrack(
        live_dir=live_dir,
        active=active,
        observed_utc="2026-05-12T14:08:56Z",
    )

    assert request["status"] == "authenticated_backlog_remaining"
    assert fpm130._login_mode_request_active(request) is True
    text = request_path.read_text(encoding="ascii")
    assert "status=authenticated_backlog_remaining" in text
    assert "reactivated_for_active_login_backtrack_rows=1" in text


def test_fpm130_clears_stale_login_mode_env_without_request(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("F061_LOGIN_MODE", "1")
    monkeypatch.setenv("F061_LOGIN_HOLD_SECONDS", "60")
    monkeypatch.setenv("F061_LOGIN_MODE_REQUEST_PATH", "stale.requested")
    monkeypatch.setenv("F061_MANUAL_BBP_LOGIN_WAIT_SECONDS", "60")
    monkeypatch.delenv("F061_BACKGROUND_BROWSER_MODE", raising=False)

    env = fpm130._build_scanner_child_env(tmp_path)

    assert env["F061_BACKGROUND_BROWSER_MODE"] == "minimized"
    assert "F061_LOGIN_MODE" not in env
    assert "F061_LOGIN_HOLD_SECONDS" not in env
    assert "F061_LOGIN_MODE_REQUEST_PATH" not in env
    assert "F061_MANUAL_BBP_LOGIN_WAIT_SECONDS" not in env


def test_fpm130_still_required_login_request_stays_active(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "visible")
    monkeypatch.delenv("F061_SHOW_WINDOWS", raising=False)
    monkeypatch.delenv("FPM_LIVE_HIDE_SCRAPER_WINDOWS", raising=False)
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_login_mode.requested").write_text(
        "status=still_required\nhold_seconds=60\n",
        encoding="ascii",
    )

    env = fpm130._build_scanner_child_env(tmp_path)

    assert env["F061_BACKGROUND_BROWSER_MODE"] == "visible"
    assert env["F061_LOGIN_MODE"] == "1"
    assert env["F061_LOGIN_HOLD_SECONDS"] == "60"
    assert env["F061_MANUAL_BBP_LOGIN_WAIT_SECONDS"] == "60"


def test_fpm130_auth_attention_overrides_stale_hidden_auth_state(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("F061_BACKGROUND_BROWSER_MODE", raising=False)
    monkeypatch.delenv("F061_SHOW_WINDOWS", raising=False)
    monkeypatch.delenv("FPM_LIVE_HIDE_SCRAPER_WINDOWS", raising=False)
    monkeypatch.setenv("FPM_F061_AUTO_VISIBLE_AUTH_ATTENTION", "1")
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=hidden|browser_state=HIDDEN|auth_state=LOGGED_IN|reason=child_started_minimized|updated_utc=2026-05-09T09:44:54Z\n",
        encoding="utf-8",
    )
    _write_csv(
        live_dir / "live_cycle_events.csv",
        [
            {
                "event_utc": "2026-05-09T09:44:52Z",
                "cycle_run_id": "cycle",
                "event_type": "f061_auth_attention",
                "supplier_id": "",
                "f061_run_id": "",
                "status": "attention_needed",
                "rows": "5",
                "notes": "browser_block_signal_seen;next_child_browser_mode=visible",
            }
        ],
        LIVE_CYCLE_EVENT_COLUMNS,
    )

    env = fpm130._build_scanner_child_env(tmp_path)

    assert env["F061_BACKGROUND_BROWSER_MODE"] == "visible"
    assert env["F061_SHOW_WINDOWS"] == "1"
    assert env["FPM_LIVE_HIDE_SCRAPER_WINDOWS"] == "0"


def test_fpm130_transient_browser_block_does_not_request_visible_after_auth_confirmed(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FPM_F061_AUTO_VISIBLE_AUTH_ATTENTION", "1")
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=hidden|browser_state=HIDDEN|auth_state=LOGGED_IN|reason=auth_confirmed|updated_utc=2026-05-12T15:17:14Z\n",
        encoding="utf-8",
    )

    result = fpm130._record_auth_attention_after_chunk(
        live_dir=live_dir,
        event_utc="2026-05-12T15:17:44Z",
        cycle_run_id="cycle",
        scanner_summary={"processed_rows": 5, "scanner_speed_browser_blocked_rows": 1},
    )

    assert result == "cleared"
    state_text = (live_dir / "f061_browser_visibility_state.txt").read_text(encoding="utf-8")
    assert "state=hidden" in state_text
    assert "reason=auth_attention_recovered" in state_text
    events = pd.read_csv(live_dir / "live_cycle_events.csv", dtype=str).fillna("")
    assert events.iloc[-1]["status"] == "cleared"
    assert "next_child_browser_mode=minimized" in events.iloc[-1]["notes"]


def test_fpm130_login_backtrack_rows_request_visible_child_by_default(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("F061_BACKGROUND_BROWSER_MODE", raising=False)
    write_f_contract_df(
        tmp_path,
        "supplier_price_list_active_run",
        pd.DataFrame(
            [
                {
                    "run_id": "run_login",
                    "supplier_id": "login_supplier",
                    "supplier_name": "Login Supplier",
                    "row_key": "normal",
                    "supplier_sku": "NORM",
                    "barcode": "111",
                    "supplier_title": "Normal",
                    "unit_cost": "1",
                    "currency": "GBP",
                    "vat_rate": "20",
                    "scan_status": "pending",
                    "scan_reason": "",
                    "attempt_count": "0",
                    "last_attempt_utc": "",
                    "finished_utc": "",
                    "source_seen_at_utc": "2026-05-07T10:00:00Z",
                    "completion_block_reason": "",
                },
                {
                    "run_id": "run_login",
                    "supplier_id": "login_supplier",
                    "supplier_name": "Login Supplier",
                    "row_key": "backtrack",
                    "supplier_sku": "BACK",
                    "barcode": "222",
                    "supplier_title": "Backtrack",
                    "unit_cost": "1",
                    "currency": "GBP",
                    "vat_rate": "20",
                    "scan_status": "login_backtrack_pending",
                    "scan_reason": "login_backtrack_required",
                    "attempt_count": "0",
                    "last_attempt_utc": "",
                    "finished_utc": "",
                    "source_seen_at_utc": "2026-05-07T10:00:00Z",
                    "completion_block_reason": "bbp_login_required",
                },
            ]
        ),
    )
    write_f_contract_df(
        tmp_path,
        "supplier_price_list_run_state",
        pd.DataFrame(
            [
                {
                    "supplier_id": "login_supplier",
                    "supplier_name": "Login Supplier",
                    "run_id": "run_login",
                    "run_status": "running",
                    "source_url": "",
                    "source_file_path": "raw.csv",
                    "source_seen_at_utc": "2026-05-07T10:00:00Z",
                    "normalized_utc": "2026-05-07T10:00:00Z",
                    "total_rows": "2",
                    "pending_rows": "2",
                    "done_rows": "0",
                    "failed_rows": "0",
                    "held_rows": "0",
                    "next_row_index": "1",
                    "updated_at_utc": "2026-05-07T10:00:00Z",
                    "completed_at_utc": "",
                }
            ]
        ),
    )

    active = fpm130._active_f061_state(tmp_path)
    env = fpm130._build_scanner_child_env(tmp_path)

    assert active["supplier_id"] == "login_supplier"
    assert active["pending_rows"] == 2
    assert env["F061_BACKGROUND_BROWSER_MODE"] == "visible"
    assert env["F061_SHOW_WINDOWS"] == "1"
    assert env["FPM_LIVE_HIDE_SCRAPER_WINDOWS"] == "0"


def test_fpm130_yes_no_backtrack_rows_stay_hidden_without_login_signal(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("F061_BACKGROUND_BROWSER_MODE", raising=False)
    monkeypatch.delenv("F061_SHOW_WINDOWS", raising=False)
    monkeypatch.delenv("FPM_LIVE_HIDE_SCRAPER_WINDOWS", raising=False)
    write_f_contract_df(
        tmp_path,
        "supplier_price_list_active_run",
        pd.DataFrame(
            [
                {
                    "run_id": "run_yesno",
                    "supplier_id": "login_supplier",
                    "supplier_name": "Login Supplier",
                    "row_key": "yesno",
                    "supplier_sku": "YESNO",
                    "barcode": "222",
                    "supplier_title": "Yes No Backtrack",
                    "unit_cost": "1",
                    "currency": "GBP",
                    "vat_rate": "20",
                    "scan_status": "login_backtrack_pending",
                    "scan_reason": "login_backtrack_required",
                    "attempt_count": "0",
                    "last_attempt_utc": "",
                    "finished_utc": "",
                    "source_seen_at_utc": "2026-05-07T10:00:00Z",
                    "completion_block_reason": "dashboard_yes_no_backtrack_required",
                },
            ]
        ),
    )

    env = fpm130._build_scanner_child_env(tmp_path)

    assert env["F061_BACKGROUND_BROWSER_MODE"] == "minimized"
    assert env["F061_SHOW_WINDOWS"] == "0"
    assert env["FPM_LIVE_HIDE_SCRAPER_WINDOWS"] == "1"


def test_fpm130_logout_signal_makes_yes_no_backtrack_visible(monkeypatch, tmp_path: Path) -> None:
    test_fpm130_yes_no_backtrack_rows_stay_hidden_without_login_signal(monkeypatch, tmp_path)
    monkeypatch.setenv("FPM_F061_AUTO_VISIBLE_AUTH_ATTENTION", "1")
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=visible|browser_state=VISIBLE|auth_state=LOGIN_REQUIRED|reason=auth_required|updated_utc=2026-05-07T10:00:00Z\n",
        encoding="utf-8",
    )

    env = fpm130._build_scanner_child_env(tmp_path)

    assert env["F061_BACKGROUND_BROWSER_MODE"] == "visible"
    assert env["F061_SHOW_WINDOWS"] == "1"
    assert env["FPM_LIVE_HIDE_SCRAPER_WINDOWS"] == "0"


def test_fpm130_hides_login_backtrack_child_when_auth_already_confirmed(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(fpm130, "_ensure_scraper_window_hider", lambda root, force=False: calls.append(f"hide:{force}"))
    monkeypatch.setattr(fpm130, "_stop_scraper_window_hider", lambda root: calls.append("stop_hider"))
    monkeypatch.setattr(fpm130, "_show_scraper_windows_once", lambda root, **kwargs: calls.append("show"))
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = live_dir / "f061_child_stdout.log"
    stderr_path = live_dir / "f061_child_stderr.log"
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text("BBP login skipped: already authenticated.\n", encoding="utf-8")

    state = fpm130._update_child_auth_visibility_from_logs(
        root=tmp_path,
        live_dir=live_dir,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        stdout_start_offset=0,
        stderr_start_offset=0,
        current_state="visible",
    )

    assert state == "hidden"
    assert calls == ["hide:True"]
    assert "state=hidden" in (live_dir / "f061_browser_visibility_state.txt").read_text(encoding="utf-8")


def test_fpm130_bbp_auth_does_not_hide_seller_central_manual_wait(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(fpm130, "_ensure_scraper_window_hider", lambda root, force=False: calls.append(f"hide:{force}"))
    monkeypatch.setattr(fpm130, "_stop_scraper_window_hider", lambda root: calls.append("stop_hider"))
    monkeypatch.setattr(fpm130, "_show_scraper_windows_once", lambda root, **kwargs: calls.append("show"))
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "observed_utc": "2026-06-02T10:13:07Z",
                "context": "dashboard_yes_no_login",
                "status": "waiting_for_code",
                "reason": "manual_seller_central_login_wait",
                "seller_central_signin_detected": "1",
                "seller_central_otp_detected": "0",
            }
        ]
    ).to_csv(live_dir / "seller_central_login_recovery_proof.csv", index=False)
    stdout_path = live_dir / "f061_child_stdout.log"
    stderr_path = live_dir / "f061_child_stderr.log"
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text("BBP login skipped: already authenticated.\n", encoding="utf-8")

    state = fpm130._update_child_auth_visibility_from_logs(
        root=tmp_path,
        live_dir=live_dir,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        stdout_start_offset=0,
        stderr_start_offset=0,
        current_state="visible",
        login_mode=True,
    )

    state_text = (live_dir / "f061_browser_visibility_state.txt").read_text(encoding="utf-8")
    assert state == "visible"
    assert calls == ["stop_hider", "show"]
    assert "state=visible" in state_text
    assert "auth_state=SELLER_CENTRAL_ELIGIBILITY_LOGIN_REQUIRED" in state_text
    assert "reason=seller_central_eligibility_login_still_required" in state_text


def test_fpm130_hidden_auth_signal_updates_stale_child_started_marker(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(fpm130, "_ensure_scraper_window_hider", lambda root, force=False: calls.append(f"hide:{force}"))
    monkeypatch.setattr(fpm130, "_stop_scraper_window_hider", lambda root: calls.append("stop_hider"))
    monkeypatch.setattr(fpm130, "_show_scraper_windows_once", lambda root, **kwargs: calls.append("show"))
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=hidden|browser_state=HIDDEN|auth_state=|reason=child_started_minimized|updated_utc=2026-05-13T11:59:05Z\n",
        encoding="utf-8",
    )
    stdout_path = live_dir / "f061_child_stdout.log"
    stderr_path = live_dir / "f061_child_stderr.log"
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text(
        "BBP login skipped: already authenticated.\n[Profile5] Dashboard yes/no => NO\n",
        encoding="utf-8",
    )

    state = fpm130._update_child_auth_visibility_from_logs(
        root=tmp_path,
        live_dir=live_dir,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        stdout_start_offset=0,
        stderr_start_offset=0,
        current_state="hidden",
    )

    assert state == "hidden"
    assert calls == ["hide:True"]
    state_text = (live_dir / "f061_browser_visibility_state.txt").read_text(encoding="utf-8")
    assert "state=hidden" in state_text
    assert "auth_state=LOGGED_IN" in state_text
    assert "reason=auth_confirmed" in state_text


def test_fpm130_auth_required_log_shows_hidden_child_by_default(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(fpm130, "_ensure_scraper_window_hider", lambda root, force=False: calls.append(f"hide:{force}"))
    monkeypatch.setattr(fpm130, "_stop_scraper_window_hider", lambda root: calls.append("stop_hider"))
    monkeypatch.setattr(fpm130, "_show_scraper_windows_once", lambda root, **kwargs: calls.append("show"))
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = live_dir / "f061_child_stdout.log"
    stderr_path = live_dir / "f061_child_stderr.log"
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text("BBP manual login required; keeping the visible scanner browser open.\n", encoding="utf-8")

    state = fpm130._update_child_auth_visibility_from_logs(
        root=tmp_path,
        live_dir=live_dir,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        stdout_start_offset=0,
        stderr_start_offset=0,
        current_state="hidden",
    )

    assert state == "visible"
    assert calls == ["stop_hider", "show"]
    state_text = (live_dir / "f061_browser_visibility_state.txt").read_text(encoding="utf-8")
    assert "state=visible" in state_text
    assert "reason=bbp_login_required" in state_text


def test_fpm130_missing_bbp_iframe_does_not_request_login_window(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(fpm130, "_show_scraper_windows_once", lambda root, **kwargs: calls.append("show"))
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = live_dir / "f061_child_stdout.log"
    stderr_path = live_dir / "f061_child_stderr.log"
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text("No BBP iframe => Message:\n", encoding="utf-8")

    state = fpm130._update_child_auth_visibility_from_logs(
        root=tmp_path,
        live_dir=live_dir,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        stdout_start_offset=0,
        stderr_start_offset=0,
        current_state="hidden",
        allow_visible_auth_required=True,
        login_mode=True,
    )

    assert state == "hidden"
    assert calls == []
    assert not (live_dir / "f061_browser_visibility_state.txt").exists()


def test_fpm130_login_mode_records_scanner_owned_visible_and_surfaces_once(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    def fake_show(root, **kwargs):
        calls.append(f"show:{kwargs.get('login_mode')}")
        return True

    monkeypatch.setattr(fpm130, "_show_scraper_windows_once", fake_show)
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = live_dir / "f061_child_stdout.log"
    stderr_path = live_dir / "f061_child_stderr.log"
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text("{'error': 'BBP_LOGIN_REQUIRED'}\n", encoding="utf-8")

    state = fpm130._update_child_auth_visibility_from_logs(
        root=tmp_path,
        live_dir=live_dir,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        stdout_start_offset=0,
        stderr_start_offset=0,
        current_state="visible",
        allow_visible_auth_required=True,
        login_mode=True,
    )

    assert state == "visible"
    assert calls == ["show:True"]
    assert (live_dir / "f061_login_mode_window_shown.marker").exists()
    state_text = (live_dir / "f061_browser_visibility_state.txt").read_text(encoding="utf-8")
    assert "state=visible" in state_text
    assert "reason=bbp_login_required_scanner_owned" in state_text


def test_fpm130_does_not_repeat_login_mode_show_after_marker(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(fpm130, "_show_scraper_windows_once", lambda root, **kwargs: calls.append(f"show:{kwargs.get('login_mode')}"))
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_login_mode_window_shown.marker").write_text("2026-05-09T13:00:00Z\n", encoding="utf-8")
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=visible|browser_state=VISIBLE|auth_state=BBP_LOGIN_REQUIRED|reason=bbp_login_required_scanner_owned|updated_utc=2026-05-09T13:00:00Z\n",
        encoding="utf-8",
    )
    stdout_path = live_dir / "f061_child_stdout.log"
    stderr_path = live_dir / "f061_child_stderr.log"
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text("BBP manual login required; keeping the visible scanner browser open.\n", encoding="utf-8")

    state = fpm130._update_child_auth_visibility_from_logs(
        root=tmp_path,
        live_dir=live_dir,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        stdout_start_offset=0,
        stderr_start_offset=0,
        current_state="visible",
        allow_visible_auth_required=True,
        login_mode=True,
    )

    assert state == "visible"
    assert calls == []
    assert not (live_dir / "live_cycle_events.csv").exists()


def test_fpm130_clears_stale_login_mode_show_marker_for_new_child(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    marker = live_dir / "f061_login_mode_window_shown.marker"
    marker.write_text("2026-05-09T13:00:00Z\n", encoding="utf-8")

    fpm130._clear_login_mode_window_shown(live_dir)

    assert not marker.exists()


def test_fpm130_does_not_repeat_show_when_same_visible_auth_reason_is_saved(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(fpm130, "_show_scraper_windows_once", lambda root, **kwargs: calls.append("show"))
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=visible|browser_state=VISIBLE|auth_state=BBP_LOGIN_REQUIRED|reason=bbp_login_required|updated_utc=2026-05-09T13:00:00Z\n",
        encoding="utf-8",
    )
    stdout_path = live_dir / "f061_child_stdout.log"
    stderr_path = live_dir / "f061_child_stderr.log"
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text("{'error': 'BBP_LOGIN_REQUIRED'}\n", encoding="utf-8")

    state = fpm130._update_child_auth_visibility_from_logs(
        root=tmp_path,
        live_dir=live_dir,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        stdout_start_offset=0,
        stderr_start_offset=0,
        current_state="visible",
        allow_visible_auth_required=True,
    )

    assert state == "visible"
    assert calls == []


def test_fpm130_hidden_auth_state_overrides_backtrack_visible_start(monkeypatch, tmp_path: Path) -> None:
    test_fpm130_login_backtrack_rows_request_visible_child_by_default(monkeypatch, tmp_path)
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "\ufeffstate=hidden|reason=auth_confirmed|updated_utc=2026-05-07T10:00:00Z\n",
        encoding="utf-8",
    )

    env = fpm130._build_scanner_child_env(tmp_path)

    assert env["F061_BACKGROUND_BROWSER_MODE"] == "minimized"
    assert env["FPM_LIVE_HIDE_SCRAPER_WINDOWS"] == "1"


def test_fpm130_hidden_child_overrides_stale_show_environment(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("F061_BACKGROUND_BROWSER_MODE", raising=False)
    monkeypatch.setenv("F061_SHOW_WINDOWS", "1")
    monkeypatch.setenv("FPM_LIVE_HIDE_SCRAPER_WINDOWS", "0")
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=hidden|reason=auth_confirmed|updated_utc=2026-05-07T10:00:00Z\n",
        encoding="utf-8",
    )

    env = fpm130._build_scanner_child_env(tmp_path)

    assert env["F061_BACKGROUND_BROWSER_MODE"] == "minimized"
    assert env["F061_SHOW_WINDOWS"] == "0"
    assert env["FPM_LIVE_HIDE_SCRAPER_WINDOWS"] == "1"


def test_fpm130_hidden_child_start_forces_hider_despite_parent_env(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    monkeypatch.setenv("FPM_LIVE_HIDE_SCRAPER_WINDOWS", "0")
    monkeypatch.setattr(fpm130, "_ensure_scraper_window_hider", lambda root, force=False: calls.append(f"hide:{force}"))
    monkeypatch.setattr(fpm130, "_stop_scraper_window_hider", lambda root: calls.append("stop_hider"))
    monkeypatch.setattr(fpm130, "_show_scraper_windows_once", lambda root, **kwargs: calls.append("show"))

    fpm130._apply_child_start_browser_visibility(tmp_path, {"FPM_LIVE_HIDE_SCRAPER_WINDOWS": "1"})

    assert calls == ["hide:True"]


def test_fpm130_visible_child_start_brings_existing_window_forward(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(fpm130, "_ensure_scraper_window_hider", lambda root, force=False: calls.append(f"hide:{force}"))
    monkeypatch.setattr(fpm130, "_stop_scraper_window_hider", lambda root: calls.append("stop_hider"))
    monkeypatch.setattr(fpm130, "_show_scraper_windows_once", lambda root, **kwargs: calls.append(f"show:{kwargs.get('login_mode')}"))

    fpm130._apply_child_start_browser_visibility(tmp_path, {"FPM_LIVE_HIDE_SCRAPER_WINDOWS": "0"})

    assert calls == ["stop_hider", "show:False"]


def test_fpm130_visible_child_uses_shownormal_startupinfo(monkeypatch) -> None:
    monkeypatch.setattr(fpm130.os, "name", "nt")

    startupinfo = fpm130._scanner_child_startupinfo("visible")

    assert startupinfo is not None
    assert startupinfo.dwFlags & fpm130.subprocess.STARTF_USESHOWWINDOW
    assert startupinfo.wShowWindow == 1


def test_fpm130_hidden_child_uses_default_startupinfo(monkeypatch) -> None:
    monkeypatch.setattr(fpm130.os, "name", "nt")

    assert fpm130._scanner_child_startupinfo("minimized") is None


def test_fpm130_login_mode_visible_child_surfaces_configured_profile(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(fpm130, "_ensure_scraper_window_hider", lambda root, force=False: calls.append(f"hide:{force}"))
    monkeypatch.setattr(fpm130, "_stop_scraper_window_hider", lambda root: calls.append("stop_hider"))
    monkeypatch.setattr(fpm130, "_show_scraper_windows_once", lambda root, **kwargs: calls.append(f"show:{kwargs.get('login_mode')}"))

    fpm130._apply_child_start_browser_visibility(
        tmp_path,
        {
            "FPM_LIVE_HIDE_SCRAPER_WINDOWS": "0",
            "F061_BACKGROUND_BROWSER_MODE": "visible",
            "F061_LOGIN_MODE": "1",
            "F061_BBP_USER_DATA_DIR": r"C:\Users\Luke\AppData\Local\Chrome_UC136",
            "F061_BBP_PROFILE_DIR": "Profile 2",
        },
    )

    assert calls == ["stop_hider", "show:True"]


def test_fpm130_login_mode_show_filter_targets_configured_profile(monkeypatch, tmp_path: Path) -> None:
    captured: list[object] = []

    def fake_run(cmd, **kwargs):
        captured.append(cmd)

        class Completed:
            returncode = 0
            stdout = "1\n"

        return Completed()

    monkeypatch.setattr(fpm130.os, "name", "nt")
    monkeypatch.setattr(fpm130.subprocess, "run", fake_run)

    fpm130._show_scraper_windows_once(
        tmp_path,
        login_mode=True,
        user_data_dir=r"C:\Users\Luke\AppData\Local\Chrome_UC136",
        profile_dir="Profile 2",
    )

    command_text = " ".join(captured[0])
    assert "Chrome_UC136" in command_text
    assert "--profile-directory=Profile\\ 2(\\s|`\"|$)" in command_text
    assert "Chrome_91_F061" in command_text
    assert "ParentProcessId" in command_text
    assert "BBPProfile1" not in command_text


def test_fpm130_default_bbp_profile_is_plugin_profile() -> None:
    assert fpm130.DEFAULT_F061_BBP_USER_DATA_DIR == r"C:\Users\Luke\AppData\Local\Chrome_UC136"
    assert fpm130.DEFAULT_F061_BBP_PROFILE_DIR == "Profile 2"


def test_fpm130_child_env_declares_approved_bbp_profile(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("F061_BBP_USER_DATA_DIR", raising=False)
    monkeypatch.delenv("F061_BBP_PROFILE_DIR", raising=False)
    monkeypatch.setattr(fpm130, "_scanner_browser_mode_for_next_child", lambda root: "minimized")
    monkeypatch.setattr(fpm130, "_read_login_mode_request", lambda live_dir: {})
    monkeypatch.setattr(fpm130, "_login_mode_request_active_for_child", lambda **kwargs: False)
    monkeypatch.setattr(fpm130, "_apply_login_mode_env", lambda env, request, force_active=False: None)
    monkeypatch.setattr(fpm130, "_apply_authenticated_login_mode_browser_policy", lambda **kwargs: None)

    env = fpm130._build_scanner_child_env(tmp_path)

    assert env["F061_BBP_USER_DATA_DIR"] == r"C:\Users\Luke\AppData\Local\Chrome_UC136"
    assert env["F061_BBP_PROFILE_DIR"] == "Profile 2"


def test_fpm130_visible_signal_records_missing_when_no_window_surfaces(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(fpm130, "_stop_scraper_window_hider", lambda root: calls.append("stop_hider"))
    monkeypatch.setattr(fpm130, "_show_scraper_windows_once", lambda root, **kwargs: False)
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    state = fpm130._apply_browser_visibility_signal(
        root=tmp_path,
        live_dir=live_dir,
        state="visible",
        reason="seller_central_eligibility_login_still_required",
    )

    state_text = (live_dir / "f061_browser_visibility_state.txt").read_text(encoding="utf-8")
    events = pd.read_csv(live_dir / "live_cycle_events.csv", dtype=str).fillna("")
    assert state == "missing"
    assert calls == ["stop_hider"]
    assert "state=missing" in state_text
    assert "auth_state=SELLER_CENTRAL_ELIGIBILITY_LOGIN_REQUIRED" in state_text
    assert "reason=seller_central_login_window_missing" in state_text
    assert events.iloc[-1]["status"] == "missing"


def test_fpm130_manager_mode_names_missing_login_window() -> None:
    mode = fpm130._manager_mode_for_child(
        auth_state=fpm130.AUTH_STATE_SELLER_CENTRAL_ELIGIBILITY_LOGIN_REQUIRED,
        browser_mode="visible",
        browser_visibility_state="missing",
        login_mode_child=True,
    )

    assert mode == "Login Window Missing"


def test_fpm130_remote_debugging_ports_from_command_lines_dedupes() -> None:
    ports = fpm130._remote_debugging_ports_from_command_lines(
        [
            r"C:\Chrome_UC136\bin\chrome.exe --remote-debugging-port=53807 --profile-directory=BBPProfile",
            r"C:\Chrome_UC136\bin\chrome.exe --remote-debugging-port=53807 --type=renderer",
            r"C:\Chrome_UC136\bin\chrome.exe --remote-debugging-port=64486 --profile-directory=BBPProfile",
        ]
    )

    assert ports == [53807, 64486]


def test_fpm130_hider_running_check_excludes_checker_process(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class Completed:
        stdout = ""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return Completed()

    monkeypatch.setattr(fpm130.os, "name", "nt")
    monkeypatch.setattr(fpm130.subprocess, "run", fake_run)

    assert fpm130._scraper_window_hider_running(tmp_path) is False

    command_text = " ".join(captured["cmd"])
    assert "$self=$PID" in command_text
    assert "$_.ProcessId -ne $self" in command_text


def test_fpm130_non_binary_dashboard_value_does_not_show_browser(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(fpm130, "_ensure_scraper_window_hider", lambda root, force=False: calls.append(f"hide:{force}"))
    monkeypatch.setattr(fpm130, "_stop_scraper_window_hider", lambda root: calls.append("stop_hider"))
    monkeypatch.setattr(fpm130, "_show_scraper_windows_once", lambda root, **kwargs: calls.append("show"))
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = live_dir / "f061_child_stdout.log"
    stderr_path = live_dir / "f061_child_stderr.log"
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text("Dashboard yes/no ignored non yes/no value => LIKELY\n", encoding="utf-8")

    state = fpm130._update_child_auth_visibility_from_logs(
        root=tmp_path,
        live_dir=live_dir,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        stdout_start_offset=0,
        stderr_start_offset=0,
        current_state="hidden",
    )

    assert state == "hidden"
    assert calls == []
    assert not (live_dir / "f061_browser_visibility_state.txt").exists()


def test_fpm130_records_auth_attention_then_clears_after_clean_chunk(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FPM_F061_AUTO_VISIBLE_AUTH_ATTENTION", "1")
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    first = fpm130._record_auth_attention_after_chunk(
        live_dir=live_dir,
        event_utc="2026-04-30T12:00:00Z",
        cycle_run_id="cycle",
        scanner_summary={"processed_rows": 5, "scanner_speed_browser_blocked_rows": 1},
    )
    second = fpm130._record_auth_attention_after_chunk(
        live_dir=live_dir,
        event_utc="2026-04-30T12:05:00Z",
        cycle_run_id="cycle",
        scanner_summary={"processed_rows": 5, "scanner_speed_browser_blocked_rows": 0},
    )
    events = pd.read_csv(live_dir / "live_cycle_events.csv", dtype=str).fillna("")

    assert first == "attention_needed"
    assert second == "cleared"
    assert events.iloc[-2]["status"] == "attention_needed"
    assert events.iloc[-1]["status"] == "cleared"
    state_text = (live_dir / "f061_browser_visibility_state.txt").read_text(encoding="utf-8")
    assert "state=hidden" in state_text
    assert "auth_state=LOGGED_IN" in state_text
    assert "reason=auth_attention_cleared" in state_text
    assert fpm130._auth_attention_active(live_dir) is False


def test_fpm130_blocked_chunk_requests_visible_child_by_default(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=hidden|browser_state=HIDDEN|auth_state=LOGGED_IN|reason=child_started_minimized|updated_utc=2026-05-09T09:44:54Z\n",
        encoding="utf-8",
    )

    result = fpm130._record_auth_attention_after_chunk(
        live_dir=live_dir,
        event_utc="2026-05-09T09:50:00Z",
        cycle_run_id="cycle",
        scanner_summary={"processed_rows": 5, "scanner_speed_browser_blocked_rows": 5},
    )

    state_text = (live_dir / "f061_browser_visibility_state.txt").read_text(encoding="utf-8")
    events = pd.read_csv(live_dir / "live_cycle_events.csv", dtype=str).fillna("")
    assert result == "attention_needed"
    assert "state=visible" in state_text
    assert "auth_state=LOGIN_REQUIRED" in state_text
    assert "reason=auth_attention_required" in state_text
    assert events.iloc[-1]["status"] == "attention_needed"
    assert "next_child_browser_mode=visible" in events.iloc[-1]["notes"]


def test_fpm130_child_started_minimized_does_not_confirm_auth(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    fpm130._write_browser_visibility_state(live_dir, state="hidden", reason="child_started_minimized")

    state_text = (live_dir / "f061_browser_visibility_state.txt").read_text(encoding="utf-8")
    assert "auth_state=|" in state_text
    assert fpm130._saved_auth_state(live_dir) == ""


def test_fpm130_hidden_child_start_preserves_previous_confirmed_auth(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=hidden|browser_state=HIDDEN|auth_state=LOGGED_IN|reason=auth_confirmed|updated_utc=2026-05-13T12:08:25Z\n",
        encoding="utf-8",
    )

    reason = fpm130._child_started_visibility_reason(
        live_dir,
        browser_visibility_state="hidden",
        browser_mode="minimized",
    )

    assert reason == "auth_confirmed"


def test_fpm130_blocked_chunk_can_be_hidden_with_explicit_opt_out(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FPM_F061_AUTO_VISIBLE_AUTH_ATTENTION", "0")
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    result = fpm130._record_auth_attention_after_chunk(
        live_dir=live_dir,
        event_utc="2026-05-09T09:50:00Z",
        cycle_run_id="cycle",
        scanner_summary={"processed_rows": 5, "scanner_speed_browser_blocked_rows": 5},
    )

    state_text = (live_dir / "f061_browser_visibility_state.txt").read_text(encoding="utf-8")
    events = pd.read_csv(live_dir / "live_cycle_events.csv", dtype=str).fillna("")
    assert result == "deferred_login_mode"
    assert "state=hidden" in state_text
    assert "reason=auth_attention_deferred_login_mode" in state_text
    assert events.iloc[-1]["status"] == "deferred_login_mode"
    assert "login_mode_button_required" in events.iloc[-1]["notes"]


def test_fpm130_login_mode_blocked_chunk_stays_on_login_mode_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FPM_F061_AUTO_VISIBLE_AUTH_ATTENTION", "1")
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    result = fpm130._record_auth_attention_after_chunk(
        live_dir=live_dir,
        event_utc="2026-05-11T11:49:38Z",
        cycle_run_id="cycle",
        scanner_summary={
            "processed_rows": 5,
            "scanner_speed_browser_blocked_rows": 4,
            "login_mode_active": True,
        },
    )

    state_text = (live_dir / "f061_browser_visibility_state.txt").read_text(encoding="utf-8")
    events = pd.read_csv(live_dir / "live_cycle_events.csv", dtype=str).fillna("")
    assert result == "deferred_login_mode"
    assert "state=hidden" in state_text
    assert "reason=auth_attention_deferred_login_mode" in state_text
    assert events.iloc[-1]["status"] == "deferred_login_mode"
    assert "login_mode_still_required" in events.iloc[-1]["notes"]
    assert "next_child_browser_mode=minimized" in events.iloc[-1]["notes"]


def test_fpm130_bbp_iframe_plugin_block_is_not_reported_as_catching_up(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    result = fpm130._record_auth_attention_after_chunk(
        live_dir=live_dir,
        event_utc="2026-06-05T11:49:38Z",
        cycle_run_id="cycle",
        scanner_summary={
            "processed_rows": 5,
            "scanner_speed_browser_blocked_rows": 4,
            "bbp_iframe_plugin_blocked_rows": 4,
            "login_mode_active": True,
            "login_mode_runtime_status": "bbp_iframe_plugin_blocked",
        },
    )
    state_text = (live_dir / "f061_browser_visibility_state.txt").read_text(encoding="utf-8")
    events = pd.read_csv(live_dir / "live_cycle_events.csv", dtype=str).fillna("")
    mode = fpm130._manager_mode_for_child(
        auth_state=fpm130._saved_auth_state(live_dir),
        browser_mode="minimized",
        browser_visibility_state="hidden",
        login_mode_child=True,
    )

    assert result == "bbp_iframe_plugin_blocked"
    assert "reason=bbp_iframe_plugin_blocked" in state_text
    assert "auth_state=BBP_IFRAME_PLUGIN_BLOCKED" in state_text
    assert events.iloc[-1]["status"] == "bbp_iframe_plugin_blocked"
    assert "bbp_iframe_plugin_blocked_rows=4" in events.iloc[-1]["notes"]
    assert mode == "BBP Plugin Blocked"


def test_fpm130_authenticated_login_mode_chunk_hides_browser(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=visible|browser_state=VISIBLE|auth_state=LOGIN_REQUIRED|reason=child_started_visible|updated_utc=2026-05-12T13:10:41Z\n",
        encoding="utf-8",
    )

    result = fpm130._record_auth_attention_after_chunk(
        live_dir=live_dir,
        event_utc="2026-05-12T13:12:00Z",
        cycle_run_id="cycle",
        scanner_summary={
            "processed_rows": 5,
            "scanner_speed_browser_blocked_rows": 0,
            "login_mode_active": True,
            "login_mode_runtime_status": "authenticated_backlog_remaining",
        },
    )

    state_text = (live_dir / "f061_browser_visibility_state.txt").read_text(encoding="utf-8")
    events = pd.read_csv(live_dir / "live_cycle_events.csv", dtype=str).fillna("")
    assert result == "cleared"
    assert "state=hidden" in state_text
    assert "auth_state=LOGGED_IN" in state_text
    assert "reason=login_mode_authenticated" in state_text
    assert events.iloc[-1]["status"] == "cleared"
    assert "login_mode_authenticated" in events.iloc[-1]["notes"]


def test_fpm130_seller_central_pending_chunk_stays_visible(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=hidden|browser_state=HIDDEN|auth_state=LOGGED_IN|reason=login_mode_authenticated|updated_utc=2026-06-02T09:41:00Z\n",
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "observed_utc": "2026-06-02T09:41:26Z",
                "context": "dashboard_yes_no_login",
                "status": "disabled",
                "reason": "auto_login_disabled",
                "seller_central_signin_detected": "1",
                "seller_central_otp_detected": "0",
            }
        ]
    ).to_csv(live_dir / "seller_central_login_recovery_proof.csv", index=False)

    result = fpm130._record_auth_attention_after_chunk(
        live_dir=live_dir,
        event_utc="2026-06-02T09:42:00Z",
        cycle_run_id="cycle",
        scanner_summary={
            "processed_rows": 5,
            "scanner_speed_browser_blocked_rows": 0,
            "login_mode_active": True,
            "login_mode_runtime_status": "authenticated_backlog_remaining",
        },
    )

    state_text = (live_dir / "f061_browser_visibility_state.txt").read_text(encoding="utf-8")
    events = pd.read_csv(live_dir / "live_cycle_events.csv", dtype=str).fillna("")
    assert result == "deferred_login_mode"
    assert "state=visible" in state_text
    assert "auth_state=SELLER_CENTRAL_ELIGIBILITY_LOGIN_REQUIRED" in state_text
    assert "reason=seller_central_eligibility_login_still_required" in state_text
    assert (live_dir / "f061_seller_central_window_shown.marker").exists()
    assert events.iloc[-1]["status"] == "deferred_login_mode"
    assert "next_child_browser_mode=visible" in events.iloc[-1]["notes"]


def test_fpm130_seller_central_pending_after_first_prompt_parks_next_child(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_seller_central_window_shown.marker").write_text(
        "2026-06-02T09:41:30Z\n",
        encoding="utf-8",
    )
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=visible|browser_state=VISIBLE|auth_state=SELLER_CENTRAL_ELIGIBILITY_LOGIN_REQUIRED|reason=seller_central_eligibility_login_still_required|updated_utc=2026-06-02T09:41:30Z\n",
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "observed_utc": "2026-06-02T09:42:26Z",
                "context": "dashboard_yes_no_login",
                "status": "disabled",
                "reason": "auto_login_disabled",
                "seller_central_signin_detected": "1",
                "seller_central_otp_detected": "0",
            }
        ]
    ).to_csv(live_dir / "seller_central_login_recovery_proof.csv", index=False)

    result = fpm130._record_auth_attention_after_chunk(
        live_dir=live_dir,
        event_utc="2026-06-02T09:43:00Z",
        cycle_run_id="cycle",
        scanner_summary={
            "processed_rows": 5,
            "scanner_speed_browser_blocked_rows": 0,
            "login_mode_active": True,
            "login_mode_runtime_status": "authenticated_backlog_remaining",
        },
    )

    state_text = (live_dir / "f061_browser_visibility_state.txt").read_text(encoding="utf-8")
    events = pd.read_csv(live_dir / "live_cycle_events.csv", dtype=str).fillna("")
    assert fpm130._seller_central_eligibility_login_pending(live_dir) is True
    assert fpm130._seller_central_eligibility_login_requires_visible(live_dir) is False
    assert fpm130._scanner_browser_mode_for_next_child(tmp_path) == "minimized"
    assert result == "deferred_login_mode"
    assert "state=hidden" in state_text
    assert "reason=seller_central_eligibility_login_waiting_parked" in state_text
    assert events.iloc[-1]["status"] == "deferred_login_mode"
    assert "next_child_browser_mode=minimized" in events.iloc[-1]["notes"]


def test_fpm130_pc_usability_pause_blocks_seller_central_visible_loop(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_login_mode.requested").write_text(
        "\n".join(
            [
                "requested_utc=2026-06-04T08:19:44Z",
                "requested_by=operator_ui",
                "mode=login_recovery",
                "status=canceled",
                "hold_seconds=0",
                "reason=user_pc_unusable_visibility_loop_paused",
                "last_status_note=operator_logged_in;visible_window_loop_paused_for_pc_usability",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=hidden|browser_state=HIDDEN|auth_state=SELLER_CENTRAL_ELIGIBILITY_LOGIN_REQUIRED|reason=user_pc_unusable_visibility_loop_paused|updated_utc=2026-06-04T08:40:42Z\n",
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "observed_utc": "2026-06-04T08:41:26Z",
                "context": "dashboard_yes_no_login",
                "status": "disabled",
                "reason": "auto_login_disabled",
                "seller_central_signin_detected": "1",
                "seller_central_otp_detected": "0",
            }
        ]
    ).to_csv(live_dir / "seller_central_login_recovery_proof.csv", index=False)

    result = fpm130._record_auth_attention_after_chunk(
        live_dir=live_dir,
        event_utc="2026-06-04T08:42:00Z",
        cycle_run_id="cycle",
        scanner_summary={
            "processed_rows": 5,
            "scanner_speed_browser_blocked_rows": 0,
            "login_mode_active": True,
            "login_mode_runtime_status": "authenticated_backlog_remaining",
        },
    )

    state_text = (live_dir / "f061_browser_visibility_state.txt").read_text(encoding="utf-8")
    events = pd.read_csv(live_dir / "live_cycle_events.csv", dtype=str).fillna("")
    assert fpm130._seller_central_eligibility_login_requires_visible(live_dir) is False
    assert fpm130._scanner_browser_mode_for_next_child(tmp_path) == "minimized"
    assert result == "cleared"
    assert "state=hidden" in state_text
    assert "reason=login_mode_authenticated" in state_text
    assert events.iloc[-1]["status"] == "cleared"
    assert "next_child_browser_mode=minimized" in events.iloc[-1]["notes"]


def test_fpm130_backtrack_pending_without_browser_block_does_not_request_visible_child(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    result = fpm130._record_auth_attention_after_chunk(
        live_dir=live_dir,
        event_utc="2026-05-07T12:00:00Z",
        cycle_run_id="cycle",
        scanner_summary={
            "processed_rows": 5,
            "scanner_speed_browser_blocked_rows": 0,
            "login_backtrack_pending_rows": 1,
        },
    )

    assert result == "unchanged"
    assert not (live_dir / "live_cycle_events.csv").exists()


def test_fpm130_parses_child_summary_from_current_stdout_slice(tmp_path: Path) -> None:
    stdout_path = tmp_path / "f061_child_stdout.log"
    stdout_path.write_text(
        "{'status': 'success', 'processed_rows': 5, 'scanner_speed_browser_blocked_rows': 0}\n",
        encoding="utf-8",
    )
    start_offset = stdout_path.stat().st_size
    with stdout_path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write("[2026-05-07T09:22:17Z] starting F061 supplier_id=dhb chunk_rows=5 browser_mode=minimized\n")
        fh.write("Quota limit hit for ASIN B0083DPLJQ. Retrying in 5 seconds... (Attempt 1/5)\n")
        fh.write(
            "{'status': 'success', 'processed_rows': 5, 'pending_rows': 688, "
            "'scanner_speed_browser_blocked_rows': 3}\n"
        )
        fh.write("[2026-05-07T09:26:57Z] finished F061 rc=0\n")

    summary = fpm130._parse_latest_child_summary(stdout_path, start_offset=start_offset)

    assert summary["status"] == "success"
    assert summary["pending_rows"] == 688
    assert summary["scanner_speed_browser_blocked_rows"] == 3


def test_fpm130_detects_dashboard_login_signal_as_visible_auth_attention(tmp_path: Path, monkeypatch) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(fpm130, "_show_scraper_windows_once", lambda *args, **kwargs: True)
    monkeypatch.setattr(fpm130, "_stop_scraper_window_hider", lambda *args, **kwargs: None)

    signal, reason = fpm130._auth_visibility_signal_from_text(
        "[Profile5] Dashboard yes/no raw LOGIN ignored after authenticated cost field; treating dashboard as missing."
    )
    fpm130._apply_browser_visibility_signal(
        root=tmp_path,
        live_dir=live_dir,
        state=signal,
        reason=reason,
        cycle_run_id="cycle_dashboard_login",
    )

    state_text = (live_dir / "f061_browser_visibility_state.txt").read_text(encoding="utf-8")
    assert signal == "visible"
    assert reason == "amazon_dashboard_login_required"
    assert "auth_state=AMAZON_DASHBOARD_LOGIN_REQUIRED" in state_text


def test_fpm130_login_mode_keeps_visible_for_specific_login_auth_states(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_login_mode.requested").write_text(
        "status=requested\nmode=login_recovery\nhold_seconds=60\n",
        encoding="ascii",
    )

    for auth_state in ("BBP_LOGIN_REQUIRED", "AMAZON_DASHBOARD_LOGIN_REQUIRED"):
        (live_dir / "f061_browser_visibility_state.txt").write_text(
            f"state=visible|browser_state=VISIBLE|auth_state={auth_state}|reason=test|updated_utc=2026-05-09T09:00:00Z\n",
            encoding="utf-8",
        )
        assert fpm130._scanner_browser_mode_for_next_child(tmp_path) == "visible"

    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=hidden|browser_state=HIDDEN|auth_state=LOGGED_IN|reason=test|updated_utc=2026-05-09T09:00:00Z\n",
        encoding="utf-8",
    )
    assert fpm130._scanner_browser_mode_for_next_child(tmp_path) == "minimized"


def test_fpm130_failed_child_timeout_with_auth_state_enters_login_wait(tmp_path: Path) -> None:
    _seed_active_f061(tmp_path, supplier_id="stax", rows=1)
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=visible|browser_state=VISIBLE|auth_state=BBP_LOGIN_REQUIRED|reason=bbp_login_required|updated_utc=2026-05-09T09:00:00Z\n",
        encoding="utf-8",
    )

    def timed_out_scanner(root: Path, *, supplier_id: str, chunk_rows: int) -> dict[str, object]:
        return {
            "status": "failed",
            "processed_rows": 0,
            "pending_rows": 1,
            "scanner_speed_browser_blocked_rows": 0,
            "notes": "f061_child_timeout_seconds=900.0;pid=1234",
        }

    summary = run_live_cycle_once(
        root=tmp_path,
        chunk_rows=1,
        apply_next=True,
        scanner_func=timed_out_scanner,
        observed_utc="2026-05-09T11:22:00Z",
        cycle_run_id="cycle_login_wait",
    )

    status = pd.read_csv(live_dir / "live_cycle_status.csv", dtype=str).fillna("").iloc[-1]
    events = pd.read_csv(live_dir / "live_cycle_events.csv", dtype=str).fillna("")

    assert summary["status"] == "login_wait"
    assert status["state"] == "login_wait"
    assert status["last_action_status"] == "attention_needed"
    assert "bbp_login_required_waiting_for_operator" in status["notes"]
    assert "f061_login_wait" in set(events["event_type"])


def test_fpm130_drain_waits_at_boundary_without_scanning(tmp_path: Path) -> None:
    _seed_active_f061(tmp_path, rows=5)
    requested = tmp_path / "out" / "locks" / "maintenance.requested"
    requested.parent.mkdir(parents=True, exist_ok=True)
    requested.write_text("requested_by=controlled_restart_gate|reason=overnight_restart_eval\n", encoding="ascii")

    summary = run_live_cycle_once(
        root=tmp_path,
        chunk_rows=2,
        apply_next=True,
        scanner_func=_fake_scanner,
        observed_utc="2026-04-30T12:00:00Z",
        cycle_run_id="cycle_drain",
    )

    ready = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "F_restart_drain.ready"
    active = read_f_contract_df(tmp_path, "supplier_price_list_active_run")
    assert summary["status"] == "drain_wait"
    assert ready.exists()
    assert len(active.index) == 5


def test_fpm130_accepts_f_only_visible_login_drain_request(tmp_path: Path) -> None:
    _seed_active_f061(tmp_path, rows=5)
    requested = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "live"
        / "f061_visible_login.requested"
    )
    requested.parent.mkdir(parents=True, exist_ok=True)
    requested.write_text(
        "requested_by=test|reason=visible_login|action=visible_login|exit_after_drain=0\n",
        encoding="ascii",
    )

    summary = run_live_cycle_once(
        root=tmp_path,
        chunk_rows=2,
        apply_next=True,
        scanner_func=_fake_scanner,
        observed_utc="2026-04-30T12:00:00Z",
        cycle_run_id="cycle_visible_login_drain",
    )

    ready = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "F_restart_drain.ready"
    active = read_f_contract_df(tmp_path, "supplier_price_list_active_run")
    assert summary["status"] == "drain_wait"
    assert ready.exists()
    assert len(active.index) == 5


def test_fpm130_blocks_same_run_pending_regression_before_scanning(tmp_path: Path) -> None:
    _seed_active_f061(tmp_path, supplier_id="stax", rows=120)
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    _write_csv(
        live_dir / "live_cycle_events.csv",
        [
            {
                "event_utc": "2026-05-15T01:08:32Z",
                "cycle_run_id": "cycle_before_restart",
                "event_type": "scanner_chunk",
                "supplier_id": "stax",
                "f061_run_id": "et_resume_run",
                "status": "success",
                "rows": "25",
                "notes": "pending_after=5",
            }
        ],
        LIVE_CYCLE_EVENT_COLUMNS,
    )

    def scanner_should_not_run(root: Path, *, supplier_id: str, chunk_rows: int) -> dict[str, object]:
        raise AssertionError("scanner should not run when pending regresses upward")

    summary = run_live_cycle_once(
        root=tmp_path,
        chunk_rows=1,
        apply_next=True,
        scanner_func=scanner_should_not_run,
        observed_utc="2026-05-15T02:21:43Z",
        cycle_run_id="cycle_after_restart",
    )

    status = pd.read_csv(live_dir / "live_cycle_status.csv", dtype=str).fillna("").iloc[-1]
    events = pd.read_csv(live_dir / "live_cycle_events.csv", dtype=str).fillna("")
    active = read_f_contract_df(tmp_path, "supplier_price_list_active_run")
    assert summary["status"] == "blocked_state_regression"
    assert status["state"] == "blocked_state_regression"
    assert status["last_action"] == "state_regression_guard"
    assert "latest_scanner_pending_after=5" in status["notes"]
    assert "state_regression_blocked" in set(events["event_type"])
    assert len(active.index) == 120


def test_fpm130_resets_repeated_stable_state_regression_after_threshold(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FPM_STATE_REGRESSION_REPEAT_RESET_THRESHOLD", "3")
    _seed_active_f061(tmp_path, supplier_id="stax", rows=120)
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    blocked_notes = "pending_rows=120;latest_scanner_pending_after=5;allowed_increase=100;run_id=et_resume_run"
    rows = [
        {
            "event_utc": "2026-05-15T01:08:32Z",
            "cycle_run_id": "cycle_before_restart",
            "event_type": "scanner_chunk",
            "supplier_id": "stax",
            "f061_run_id": "et_resume_run",
            "status": "success",
            "rows": "25",
            "notes": "pending_after=5",
        }
    ]
    for index in range(3):
        rows.append(
            {
                "event_utc": f"2026-05-15T01:1{index}:00Z",
                "cycle_run_id": f"cycle_block_{index}",
                "event_type": "state_regression_blocked",
                "supplier_id": "stax",
                "f061_run_id": "et_resume_run",
                "status": "blocked",
                "rows": "120",
                "notes": blocked_notes,
            }
        )
    _write_csv(live_dir / "live_cycle_events.csv", rows, LIVE_CYCLE_EVENT_COLUMNS)

    summary = run_live_cycle_once(
        root=tmp_path,
        chunk_rows=1,
        apply_next=True,
        scanner_func=_fake_scanner,
        observed_utc="2026-05-15T02:21:43Z",
        cycle_run_id="cycle_after_repeat_blocks",
    )

    events = pd.read_csv(live_dir / "live_cycle_events.csv", dtype=str).fillna("")
    assert summary["status"] == "success"
    assert "state_regression_guard_reset" in set(events["event_type"])
    assert "scanner_chunk" in set(events["event_type"])


def test_fpm130_does_not_reset_state_regression_when_pending_keeps_increasing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("FPM_STATE_REGRESSION_REPEAT_RESET_THRESHOLD", "3")
    _seed_active_f061(tmp_path, supplier_id="stax", rows=130)
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    rows = [
        {
            "event_utc": "2026-05-15T01:08:32Z",
            "cycle_run_id": "cycle_before_restart",
            "event_type": "scanner_chunk",
            "supplier_id": "stax",
            "f061_run_id": "et_resume_run",
            "status": "success",
            "rows": "25",
            "notes": "pending_after=5",
        }
    ]
    for pending in [100, 110, 120]:
        rows.append(
            {
                "event_utc": "2026-05-15T01:20:00Z",
                "cycle_run_id": f"cycle_block_{pending}",
                "event_type": "state_regression_blocked",
                "supplier_id": "stax",
                "f061_run_id": "et_resume_run",
                "status": "blocked",
                "rows": str(pending),
                "notes": (
                    f"pending_rows={pending};latest_scanner_pending_after=5;"
                    "allowed_increase=100;run_id=et_resume_run"
                ),
            }
        )
    _write_csv(live_dir / "live_cycle_events.csv", rows, LIVE_CYCLE_EVENT_COLUMNS)

    def scanner_should_not_run(root: Path, *, supplier_id: str, chunk_rows: int) -> dict[str, object]:
        raise AssertionError("scanner should not run while pending keeps increasing")

    summary = run_live_cycle_once(
        root=tmp_path,
        chunk_rows=1,
        apply_next=True,
        scanner_func=scanner_should_not_run,
        observed_utc="2026-05-15T02:21:43Z",
        cycle_run_id="cycle_after_increasing_blocks",
    )

    events = pd.read_csv(live_dir / "live_cycle_events.csv", dtype=str).fillna("")
    assert summary["status"] == "blocked_state_regression"
    assert "state_regression_guard_reset" not in set(events["event_type"])


def test_fpm130_reconciles_stale_sql_before_regression_guard_and_emits_scanner_chunk(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    monkeypatch.setenv(
        "FPM_STORAGE_DRIFT_CRITICAL_CONTRACTS",
        "supplier_price_list_active_run,supplier_price_list_run_state",
    )
    monkeypatch.setenv("FPM_STORAGE_DRIFT_AUTO_RECONCILE", "1")
    _seed_active_f061(tmp_path, supplier_id="stax", rows=120)
    active_csv = tmp_path / "out" / "systems" / "F" / "inbox" / "supplier_price_list_active_run.csv"
    run_state_csv = tmp_path / "out" / "systems" / "F" / "inbox" / "supplier_price_list_run_state.csv"
    active_fresher = pd.read_csv(active_csv, dtype=str).fillna("").head(5)
    active_fresher.to_csv(active_csv, index=False)
    run_state_fresher = pd.read_csv(run_state_csv, dtype=str).fillna("")
    run_state_fresher.loc[0, "pending_rows"] = "5"
    run_state_fresher.loc[0, "done_rows"] = "115"
    run_state_fresher.loc[0, "updated_at_utc"] = "2026-05-15T02:00:00Z"
    run_state_fresher.to_csv(run_state_csv, index=False)

    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    _write_csv(
        live_dir / "live_cycle_events.csv",
        [
            {
                "event_utc": "2026-05-15T01:08:32Z",
                "cycle_run_id": "cycle_before_restart",
                "event_type": "scanner_chunk",
                "supplier_id": "stax",
                "f061_run_id": "et_resume_run",
                "status": "success",
                "rows": "25",
                "notes": "pending_after=5",
            }
        ],
        LIVE_CYCLE_EVENT_COLUMNS,
    )

    summary = run_live_cycle_once(
        root=tmp_path,
        chunk_rows=1,
        apply_next=True,
        scanner_func=_fake_scanner,
        observed_utc="2026-05-15T02:21:43Z",
        cycle_run_id="cycle_after_storage_reconcile",
    )

    events = pd.read_csv(live_dir / "live_cycle_events.csv", dtype=str).fillna("")
    report = pd.read_csv(live_dir / "storage_drift_report.csv", dtype=str).fillna("")
    assert summary["status"] == "success"
    assert "storage_drift_reconciled" in set(events["event_type"])
    assert "scanner_chunk" in set(events["event_type"])
    assert set(report["status_after"]) == {"ok"}


def test_fpm130_precheck_warning_does_not_block_scanner_success(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FPM_INCREMENTAL_AI_PRECHECK_SUPPLIERS", "stax")
    _seed_active_f061(tmp_path, supplier_id="stax", rows=5)

    def failing_precheck(**kwargs) -> dict[str, object]:
        raise RuntimeError("precheck probe failure")

    monkeypatch.setattr(fpm130, "build_incremental_ai_precheck", failing_precheck)

    summary = run_live_cycle_once(
        root=tmp_path,
        chunk_rows=1,
        apply_next=True,
        scanner_func=_fake_scanner,
        observed_utc="2026-05-22T08:30:00Z",
        cycle_run_id="cycle_precheck_warn",
    )

    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    events = pd.read_csv(live_dir / "live_cycle_events.csv", dtype=str).fillna("")
    precheck_events = events[events["event_type"].eq("incremental_ai_precheck")]
    assert summary["status"] == "success"
    assert summary["incremental_ai_precheck_status"] == "warn"
    assert not precheck_events.empty
    assert precheck_events.iloc[-1]["status"] == "warn"


def test_fpm130_enforced_production_line_routing_blocks_without_completed_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _seed_active_f061(tmp_path, rows=2)
    monkeypatch.setenv("FPM_PRODUCTION_LINE_ROUTING_MODE", "enforced")

    def fake_build_production_line_run(**kwargs):
        run_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "pipeline_runs" / "broken"
        run_dir.mkdir(parents=True, exist_ok=True)
        return {"status": "completed", "pipeline_run_dir": str(run_dir), "input_rows": 2}

    def scanner_should_not_run(*args, **kwargs):
        raise AssertionError("scanner must not run when enforced routing is unsafe")

    monkeypatch.setattr(fpm130, "build_production_line_run", fake_build_production_line_run)

    summary = run_live_cycle_once(
        root=tmp_path,
        chunk_rows=2,
        apply_next=True,
        scanner_func=scanner_should_not_run,
        observed_utc="2026-05-22T10:00:00Z",
        cycle_run_id="cycle_enforced_routing",
    )

    assert summary["status"] == "blocked_production_line_routing"
    assert summary["production_line_routing_status"] == "blocked"
    health = pd.read_csv(
        tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "production_line_health.csv",
        dtype=str,
    ).fillna("")
    assert health.iloc[-1]["check"] == "f_production_line_routing_runtime"
    assert health.iloc[-1]["status"] == "warn"


def test_fpm130_login_mode_request_records_child_start_event_and_health(tmp_path: Path) -> None:
    _seed_active_f061(tmp_path, supplier_id="stax", rows=5)
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    request_path = live_dir / "f061_login_mode.requested"
    request_path.parent.mkdir(parents=True, exist_ok=True)
    request_path.write_text(
        "\n".join(
            [
                "requested_utc=2026-05-09T11:20:00Z",
                "requested_by=operator_ui",
                "mode=login_recovery",
                "supplier_id=stax",
                "run_id=et_resume_run",
                "status=requested",
                "hold_seconds=60",
                "reason=operator_login_button",
            ]
        )
        + "\n",
        encoding="ascii",
    )

    summary = run_live_cycle_once(
        root=tmp_path,
        chunk_rows=2,
        apply_next=True,
        scanner_func=_fake_scanner,
        observed_utc="2026-05-09T11:22:00Z",
        cycle_run_id="cycle_login_mode",
    )

    events = pd.read_csv(live_dir / "live_cycle_events.csv", dtype=str).fillna("")
    health = pd.read_csv(live_dir / "live_cycle_health.csv", dtype=str).fillna("")
    login_event = events[events["event_type"] == "login_mode_child_started"].iloc[0]
    login_health = health[health["check"] == "f061_login_mode_request_state"].iloc[0]

    assert summary["action"] == "resume_f061_active_run"
    assert login_event["supplier_id"] == "stax"
    assert login_event["f061_run_id"] == "et_resume_run"
    assert login_event["status"] == "started"
    assert login_event["rows"] == "5"
    assert "hold_seconds=60" in login_event["notes"]
    assert login_health["status"] == "ok"
    assert login_health["value"] == "child_starting"


def test_fpm130_drain_exit_releases_owner_for_reload(tmp_path: Path) -> None:
    _seed_active_f061(tmp_path, rows=5)
    requested = tmp_path / "out" / "locks" / "maintenance.requested"
    requested.parent.mkdir(parents=True, exist_ok=True)
    requested.write_text(
        "requested_by=test|reason=reload_fpm130|action=reload|exit_after_drain=1\n",
        encoding="ascii",
    )

    summary = run_live_cycle(
        root=tmp_path,
        chunk_rows=2,
        apply_next=True,
        run_once=False,
        sleep_seconds=0,
    )

    ready = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "F_restart_drain.ready"
    lock = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "live_cycle.lock"
    active = read_f_contract_df(tmp_path, "supplier_price_list_active_run")
    assert summary["status"] == "drain_exit"
    assert ready.exists()
    assert not lock.exists()
    assert len(active.index) == 5


def test_fpm130_can_apply_next_batch_then_scan_chunk(tmp_path: Path) -> None:
    _seed_next_batch(tmp_path)

    summary = run_live_cycle_once(
        root=tmp_path,
        chunk_rows=1,
        apply_next=True,
        auto_approve_next=True,
        refresh_before_select=False,
        scanner_func=_fake_scanner,
        observed_utc="2026-04-30T12:00:00Z",
        cycle_run_id="cycle_apply",
    )

    active = read_f_contract_df(tmp_path, "supplier_price_list_active_run")
    preview = pd.read_csv(
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "test_mode"
        / "f061_handoff_apply_preview.csv",
        dtype=str,
    ).fillna("")
    assert summary["action"] == "apply_and_scan_next_batch"
    assert summary["supplier_id"] == "entertainment_trading"
    assert summary["pending_after"] == 1
    assert len(active.index) == 1
    assert preview.iloc[0]["live_write_succeeded"] == "1"


def test_fpm130_writes_idle_status_when_apply_has_no_pending_rows(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        fpm130,
        "stage_f061_handoff",
        lambda **kwargs: {
            "status": "staged",
            "supplier_id": "",
            "batch_id": "",
            "block_reason": "no_scan_ready",
        },
    )
    monkeypatch.setattr(
        fpm130,
        "apply_f061_handoff",
        lambda **kwargs: {
            "status": "applied",
            "supplier_id": "",
            "batch_id": "",
            "run_id": "",
        },
    )

    summary = run_live_cycle_once(
        root=tmp_path,
        chunk_rows=25,
        apply_next=True,
        auto_approve_next=True,
        refresh_before_select=False,
        observed_utc="2026-05-18T08:43:00Z",
        cycle_run_id="cycle_no_scan_ready",
    )

    status = pd.read_csv(
        tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "live_cycle_status.csv",
        dtype=str,
    ).fillna("").iloc[-1]
    assert summary["status"] == "applied_no_pending"
    assert status["state"] == "idle"
    assert status["last_action"] == "apply_next_batch"
    assert status["last_action_status"] == "applied_no_pending"
    assert status["pending_rows"] == "0"


def test_fpm130_reports_no_scan_ready_as_idle_not_blocked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        fpm130,
        "stage_f061_handoff",
        lambda **kwargs: {
            "status": "blocked",
            "supplier_id": "",
            "batch_id": "",
            "staged_rows": "0",
            "block_reason": "no_rows_eligible_after_cooldown",
        },
    )
    monkeypatch.setattr(
        fpm130,
        "apply_f061_handoff",
        lambda **kwargs: {
            "status": "blocked",
            "block_reason": "preview_missing_supplier_id;staged_active_empty",
        },
    )

    summary = run_live_cycle_once(
        root=tmp_path,
        chunk_rows=25,
        apply_next=True,
        auto_approve_next=True,
        refresh_before_select=False,
        observed_utc="2026-05-18T08:53:00Z",
        cycle_run_id="cycle_no_scan_ready_blocked_apply",
    )

    status = pd.read_csv(
        tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "live_cycle_status.csv",
        dtype=str,
    ).fillna("").iloc[-1]
    events = pd.read_csv(
        tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "live_cycle_events.csv",
        dtype=str,
    ).fillna("")
    assert summary["status"] == "no_scan_ready"
    assert status["state"] == "idle"
    assert status["last_action_status"] == "no_scan_ready"
    assert status["pending_rows"] == "0"
    assert status["notes"] == "no_rows_eligible_after_cooldown"
    assert events.iloc[-1]["status"] == "no_scan_ready"


def test_fpm130_builds_review_pack_when_active_run_completes(tmp_path: Path, monkeypatch) -> None:
    _seed_active_f061(tmp_path, rows=1)
    calls: list[dict[str, object]] = []
    gate_calls: list[dict[str, object]] = []

    def fake_review_pack_builder(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {
            "status": "built",
            "pass_review_rows": "2",
            "near_miss_review_rows": "3",
            "notes": "fake_builder",
        }

    def fake_ai_gate(**kwargs: object) -> dict[str, object]:
        gate_calls.append(dict(kwargs))
        return {
            "status": "gated",
            "pass_review_rows": "1",
            "near_miss_review_rows": "2",
            "rescan_needed_rows": "1",
            "remove_from_clean_pass_rows": "1",
            "ai_gate_status": "passed",
            "operator_ready_flag": "1",
        }

    monkeypatch.setattr(
        "scripts.flows.F.price_list_manager.FPM130_run_live_cycle.build_completed_review_pack",
        fake_review_pack_builder,
    )
    monkeypatch.setattr(
        "scripts.flows.F.price_list_manager.FPM130_run_live_cycle.apply_review_intelligence_gate",
        fake_ai_gate,
    )

    summary = run_live_cycle_once(
        root=tmp_path,
        chunk_rows=1,
        apply_next=True,
        auto_approve_next=True,
        refresh_before_select=False,
        scanner_func=_fake_scanner,
        observed_utc="2026-04-30T12:00:00Z",
        cycle_run_id="cycle_review_pack",
    )

    events = pd.read_csv(
        tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "live_cycle_events.csv",
        dtype=str,
    ).fillna("")
    assert summary["pending_after"] == 0
    assert summary["review_pack_status"] == "built"
    assert summary["ai_review_gate_status"] == "gated"
    assert calls[0]["supplier_id"] == "entertainment_trading"
    assert calls[0]["run_id"] == "et_resume_run"
    assert calls[0]["force_rebuild"] is False
    assert calls[0]["emit_json"] is False
    assert gate_calls[0]["supplier_id"] == "entertainment_trading"
    assert gate_calls[0]["run_id"] == "et_resume_run"
    assert gate_calls[0]["force_rebuild"] is False
    assert gate_calls[0]["emit_json"] is False
    assert list(events.columns) == LIVE_CYCLE_EVENT_COLUMNS
    review_event = events[events["event_type"] == "review_pack_build"].iloc[0]
    assert review_event["status"] == "built"
    assert review_event["rows"] == "5"
    assert review_event["notes"] == "pass_review_rows=2;near_miss_review_rows=3"
    gate_event = events[events["event_type"] == "ai_review_gate"].iloc[0]
    assert gate_event["status"] == "gated"
    assert gate_event["rows"] == "5"
    assert gate_event["notes"] == (
        "ai_gate_status=passed;pass_review_rows=1;near_miss_review_rows=2;"
        "rescan_needed_rows=1;remove_from_clean_pass_rows=1"
    )


def test_fpm130_force_rebuilds_review_pack_when_ai_rescan_completes(tmp_path: Path, monkeypatch) -> None:
    _seed_active_f061(tmp_path, rows=1)
    active = read_f_contract_df(tmp_path, "supplier_price_list_active_run")
    active["scan_reason"] = "rescan_retry_required"
    active["completion_block_reason"] = "rescan_retry_pending"
    write_f_contract_df(tmp_path, "supplier_price_list_active_run", active)
    calls: list[dict[str, object]] = []
    gate_calls: list[dict[str, object]] = []

    def fake_review_pack_builder(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {
            "status": "built",
            "pass_review_rows": "2",
            "near_miss_review_rows": "0",
            "notes": "fake_builder",
        }

    def fake_ai_gate(**kwargs: object) -> dict[str, object]:
        gate_calls.append(dict(kwargs))
        return {
            "status": "gated",
            "pass_review_rows": "1",
            "near_miss_review_rows": "0",
            "rescan_needed_rows": "0",
            "remove_from_clean_pass_rows": "1",
            "ai_gate_status": "passed",
            "operator_ready_flag": "1",
        }

    monkeypatch.setattr(
        "scripts.flows.F.price_list_manager.FPM130_run_live_cycle.build_completed_review_pack",
        fake_review_pack_builder,
    )
    monkeypatch.setattr(
        "scripts.flows.F.price_list_manager.FPM130_run_live_cycle.apply_review_intelligence_gate",
        fake_ai_gate,
    )

    summary = run_live_cycle_once(
        root=tmp_path,
        chunk_rows=1,
        apply_next=True,
        auto_approve_next=True,
        refresh_before_select=False,
        scanner_func=_fake_scanner,
        observed_utc="2026-05-21T12:40:00Z",
        cycle_run_id="cycle_review_pack_after_ai_rescan",
    )

    events = pd.read_csv(
        tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "live_cycle_events.csv",
        dtype=str,
    ).fillna("")
    assert summary["pending_after"] == 0
    assert summary["review_pack_status"] == "built"
    assert summary["ai_review_gate_status"] == "gated"
    assert calls[0]["force_rebuild"] is True
    assert gate_calls[0]["force_rebuild"] is True
    review_event = events[events["event_type"] == "review_pack_build"].iloc[0]
    assert review_event["notes"] == "pass_review_rows=2;near_miss_review_rows=0;force_rebuild=1"
    gate_event = events[events["event_type"] == "ai_review_gate"].iloc[0]
    assert gate_event["notes"] == (
        "ai_gate_status=passed;pass_review_rows=1;near_miss_review_rows=0;"
        "rescan_needed_rows=0;remove_from_clean_pass_rows=1;force_rebuild=1"
    )
