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
    assert fpm130._live_loop_sleep_seconds("blocked", 10) == 10
    assert fpm130._live_loop_sleep_seconds("blocked_state_regression", 10) == 10
    assert fpm130._live_loop_sleep_seconds("blocked_source_shape_guard", 10) == 10
    assert fpm130._live_loop_sleep_seconds("blocked_source_shape_guard", 0) == 1
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


def test_fpm130_still_required_login_request_is_inactive(monkeypatch, tmp_path: Path) -> None:
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

    assert env["F061_BACKGROUND_BROWSER_MODE"] == "minimized"
    assert "F061_LOGIN_MODE" not in env


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


def test_fpm130_does_not_repeat_show_for_login_mode_after_marker(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(fpm130, "_show_scraper_windows_once", lambda root, **kwargs: calls.append(f"show:{kwargs.get('login_mode')}"))
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_login_mode_window_shown.marker").write_text("2026-05-09T13:00:00Z\n", encoding="utf-8")
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
    events_path = live_dir / "live_cycle_events.csv"
    assert not events_path.exists() or "auth_required_scanner_owned" not in events_path.read_text(encoding="utf-8")


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
    assert "BBPProfile1" not in command_text


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

    def fake_review_pack_builder(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {
            "status": "built",
            "pass_review_rows": "2",
            "near_miss_review_rows": "3",
            "notes": "fake_builder",
        }

    monkeypatch.setattr(
        "scripts.flows.F.price_list_manager.FPM130_run_live_cycle.build_completed_review_pack",
        fake_review_pack_builder,
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
    assert calls[0]["supplier_id"] == "entertainment_trading"
    assert calls[0]["run_id"] == "et_resume_run"
    assert calls[0]["emit_json"] is False
    assert list(events.columns) == LIVE_CYCLE_EVENT_COLUMNS
    review_event = events[events["event_type"] == "review_pack_build"].iloc[0]
    assert review_event["status"] == "built"
    assert review_event["rows"] == "5"
    assert review_event["notes"] == "pass_review_rows=2;near_miss_review_rows=3"
