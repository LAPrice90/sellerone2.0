from __future__ import annotations

import sys
import time
import os
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.O.O400_operator_ui import (
    _apply_reorder_draft,
    _amazon_dp_url,
    _clear_reorder_drafts,
    _extract_reorder_draft,
    _feeder_review_done_key,
    _pad_asin_to_10,
    _latest_price_list_live_event,
    _latest_price_list_live_status,
    _price_list_child_status,
    _price_list_active_run_counts,
    _price_list_auth_state,
    _price_list_login_button_state,
    _price_list_login_counts,
    _price_list_live_result_counts,
    _price_list_live_progress_total,
    _price_list_live_eta,
    _price_list_login_badge_html,
    _price_list_manager_mode_state,
    _price_list_supervisor_badge_html,
    _price_list_supervisor_state,
    _confirmed_price_safety,
    _price_proof_chips_html,
    _price_list_recovery_counts,
    _profit_check_badge_html,
    _read_price_list_next_action_report,
    _read_price_list_queue_df,
    _read_scanner_timeout_policy_df,
    _review_widget_key,
    _reorder_row_identity,
    _reorder_widget_key,
    FEEDER_REVIEW_COLUMN_WIDTHS,
    FEEDER_REVIEW_HEADER_LABELS,
    OPERATOR_PAGE_OPTIONS,
    OPERATOR_HIDDEN_PAGE_REDIRECTS,
    apply_price_list_handoff_approval,
    apply_price_list_queue_control,
    build_ai_product_check_gate_df,
    build_amazon_listing_draft_display_df,
    build_brand_approval_queue_display_df,
    build_product_listing_profile_review_df,
    build_feeder_review_sent_df,
    build_feeder_review_window_df,
    build_price_list_queue_summary,
    build_po_draft_review_df,
    build_price_list_lookup_results,
    build_test_orders_df,
    build_recommendations_display_df,
    build_reorder_input_df,
    filter_reorder_rows,
    get_submission_targets,
    list_feeder_review_pack_options,
    load_feeder_review_summary,
    load_feeder_review_source_df,
    load_backtest_calibration_df,
    load_feeder_review_events_df,
    load_backtest_policy_live_row,
    load_feeder_review_ui_drafts_df,
    load_operator_datasets,
    save_feeder_review_ui_drafts,
    select_flagged_backtest_calibration_rows,
    clear_feeder_review_ui_drafts,
    submit_feeder_review_batch,
    submit_amazon_listing_profile_batch,
    submit_brand_approval_decision_batch,
    submit_feeder_review_reopen_batch,
    submit_backtest_policy_update_event,
    _render_recommendation_cards,
    _copy_value_html,
    validate_backtest_policy_values,
    reset_scanner_timeout_policy_from_ui,
    request_price_list_login_mode_from_ui,
    save_scanner_timeout_policy_from_ui,
    run_amazon_listing_preview_for_draft,
    submit_amazon_listing_draft_approval,
    submit_reorder_batch,
    submit_decision_event,
    submit_receiving_event,
    submit_send_handoff_event,
)
from scripts.flows.F.price_list_manager._schemas import (
    BATCH_ROW_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
    REVIEW_HANDOFF_MANIFEST_COLUMNS,
    SUPPLIER_REGISTRY_COLUMNS,
)
from scripts.flows.F._schemas import get_f_output_contract
from scripts.flows.O._schemas import get_o_output_contract
from scripts.core.storage import write_review_pack_snapshots_sql_compat


def _write_contract_rows(tmp_path: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
    contract = get_o_output_contract(contract_name)
    path = tmp_path / contract.rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = [*contract.required_columns, *contract.optional_columns]
    normalized: list[dict[str, str]] = []
    for row in rows:
        normalized.append({col: str(row.get(col, "") or "") for col in cols})
    pd.DataFrame(normalized, columns=cols).to_csv(path, index=False)


def _write_f_contract_rows(tmp_path: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
    contract = get_f_output_contract(contract_name)
    path = tmp_path / contract.rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = [*contract.required_columns, *contract.optional_columns]
    normalized: list[dict[str, str]] = []
    for row in rows:
        normalized.append({col: str(row.get(col, "") or "") for col in cols})
    pd.DataFrame(normalized, columns=cols).to_csv(path, index=False)


def test_operator_nav_keeps_ai_gate_out_of_daily_navigation() -> None:
    labels = [label for label, _ in OPERATOR_PAGE_OPTIONS]
    routes = {route: label for label, route in OPERATOR_PAGE_OPTIONS}

    assert "New Product Review" in labels
    assert "AI Gate QA" not in labels
    assert "AI Product Check Gate" not in labels
    assert "ai_product_check_gate" not in routes
    assert OPERATOR_HIDDEN_PAGE_REDIRECTS["ai_product_check_gate"] == "new_product_review"


def test_feeder_review_headers_keep_roi_in_own_column() -> None:
    assert "ROI" in FEEDER_REVIEW_HEADER_LABELS
    assert "Profit" in FEEDER_REVIEW_HEADER_LABELS
    assert "ROI / Profit" not in FEEDER_REVIEW_HEADER_LABELS
    assert FEEDER_REVIEW_HEADER_LABELS.index("ROI") < FEEDER_REVIEW_HEADER_LABELS.index("Profit")
    assert len(FEEDER_REVIEW_HEADER_LABELS) == len(FEEDER_REVIEW_COLUMN_WIDTHS)


def test_price_list_queue_loader_and_summary_reads_dashboard_csv(tmp_path: Path) -> None:
    dashboard_path = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "status_dashboard.csv"
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "queue_position": "1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "source_method": "CSV link",
                "source_location": "https://aux.shure-cosmetics.co.uk/pricelist/",
                "file_state": "Ready",
                "queue_state": "Active",
                "operator_action": "Ready for test queue",
                "control_state": "Pause and prioritise planned",
                "price_list_date": "2026-04-30T09:00:00Z",
                "bot_status": "Test Ready",
                "web_unprocessed": "10",
                "web_pass": "0",
                "web_fail": "0",
                "web_rescan": "0",
                "second_unprocessed": "0",
                "second_pass": "0",
                "second_fail": "0",
            },
            {
                "queue_position": "2",
                "supplier_id": "dhb",
                "supplier_name": "DHB",
                "source_method": "Email request",
                "source_location": r"C:\Users\Luke\Desktop\SellerOne Price Files\DHB\inbox",
                "file_state": "Missing",
                "queue_state": "Needs Manual File",
                "operator_action": "Request price file",
                "control_state": "Pause and prioritise planned",
                "price_list_date": "",
                "bot_status": "Missing",
                "web_unprocessed": "0",
                "web_pass": "0",
                "web_fail": "0",
                "web_rescan": "0",
                "second_unprocessed": "0",
                "second_pass": "0",
                "second_fail": "0",
            },
        ]
    ).to_csv(dashboard_path, index=False)

    queue_df = _read_price_list_queue_df(tmp_path)
    summary = build_price_list_queue_summary(queue_df)

    assert len(queue_df) == 2
    assert queue_df.iloc[0]["supplier_name"] == "Shure Cosmetics"
    assert summary == {
        "total_suppliers": 2,
        "active": 1,
        "manual_missing": 1,
        "blocked": 0,
        "web_unprocessed": 10,
        "web_pass": 0,
        "web_fail": 0,
        "web_rescan": 0,
    }


def test_price_list_queue_summary_can_ignore_non_active_sample_results() -> None:
    queue_df = pd.DataFrame(
        [
            {
                "supplier_id": "entertainment_trading",
                "supplier_name": "Entertainment Trading",
                "queue_state": "Recommended",
                "web_unprocessed": "19683",
                "web_pass": "124",
                "web_fail": "1977",
                "web_rescan": "0",
            },
            {
                "supplier_id": "bliss_distribution",
                "supplier_name": "Bliss Distribution",
                "queue_state": "Queued",
                "web_unprocessed": "1506",
                "web_pass": "0",
                "web_fail": "0",
                "web_rescan": "0",
            },
        ]
    )

    summary = build_price_list_queue_summary(queue_df)

    assert summary["web_unprocessed"] == 21189
    assert summary["web_pass"] == 124
    assert summary["web_fail"] == 1977
    assert summary["web_rescan"] == 0


def test_price_list_queue_report_loader_reads_markdown(tmp_path: Path) -> None:
    report_path = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "next_action_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "# Price List Next Action Report\n\n- Supplier: Bliss Distribution\n- Safe to hand off to F061: 0\n",
        encoding="utf-8",
    )

    report = _read_price_list_next_action_report(tmp_path)

    assert "Bliss Distribution" in report
    assert "Safe to hand off to F061: 0" in report


def test_scanner_timeout_policy_ui_save_writes_only_policy_file(tmp_path: Path) -> None:
    health_path = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "health.csv"
    health_path.parent.mkdir(parents=True, exist_ok=True)
    health_path.write_text("check,status,value,notes,observed_utc,source_path\nseed,ok,1,seed,2026-05-01T00:00:00Z,seed\n")

    policy = _read_scanner_timeout_policy_df(tmp_path)
    before_files = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*") if path.is_file())
    before_health = health_path.read_text()

    edited = policy.copy()
    edited.loc[edited["fail_code"] == "NOASIN", "notes"] = "operator edited note"
    result = save_scanner_timeout_policy_from_ui(
        tmp_path,
        edited,
        observed_utc="2026-05-01T10:00:00Z",
    )

    after_files = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*") if path.is_file())
    saved = pd.read_csv(tmp_path / "config" / "feeder" / "f_scanner_timeout_policy.csv", dtype=str).fillna("")

    assert result["policy_rows"] == 15
    assert before_files == after_files
    assert health_path.read_text() == before_health
    assert saved.loc[saved["fail_code"] == "NOASIN", "notes"].iloc[0] == "operator edited note"


def test_scanner_timeout_policy_ui_reset_restores_defaults(tmp_path: Path) -> None:
    edited = _read_scanner_timeout_policy_df(tmp_path)
    edited.loc[edited["fail_code"] == "NOASIN", "timeout_mode"] = "disabled"
    save_scanner_timeout_policy_from_ui(tmp_path, edited, observed_utc="2026-05-01T10:00:00Z")

    result = reset_scanner_timeout_policy_from_ui(tmp_path, observed_utc="2026-05-01T11:00:00Z")
    reset = pd.read_csv(tmp_path / "config" / "feeder" / "f_scanner_timeout_policy.csv", dtype=str).fillna("")

    assert result["policy_rows"] == 15
    assert reset.loc[reset["fail_code"] == "NOASIN", "timeout_mode"].iloc[0] == "fixed_days"
    assert reset.loc[reset["fail_code"] == "NOASIN", "updated_at_utc"].iloc[0] == "2026-05-01T11:00:00Z"


def test_price_list_login_counts_read_active_login_backtrack_rows(tmp_path: Path) -> None:
    _write_f_contract_rows(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_a",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "row_key": "normal",
                "supplier_sku": "S1",
                "barcode": "5000000000001",
                "supplier_title": "Normal Row",
                "unit_cost": "1.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-09T00:00:00Z",
            },
            {
                "run_id": "run_a",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "row_key": "login",
                "supplier_sku": "S2",
                "barcode": "5000000000002",
                "supplier_title": "Login Row",
                "unit_cost": "2.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "login_backtrack_pending",
                "scan_reason": "login_backtrack_required",
                "attempt_count": "1",
                "last_attempt_utc": "2026-05-09T01:00:00Z",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-09T00:00:00Z",
                "completion_block_reason": "bbp_login_required",
            },
            {
                "run_id": "run_a",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "row_key": "dashboard",
                "supplier_sku": "S4",
                "barcode": "5000000000004",
                "supplier_title": "Dashboard Row",
                "unit_cost": "4.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "login_backtrack_pending",
                "scan_reason": "login_backtrack_required",
                "attempt_count": "1",
                "last_attempt_utc": "2026-05-09T01:00:00Z",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-09T00:00:00Z",
                "completion_block_reason": "dashboard_yes_no_backtrack_required",
            },
            {
                "run_id": "run_a",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "row_key": "login_reason",
                "supplier_sku": "S3",
                "barcode": "5000000000003",
                "supplier_title": "Login Reason Row",
                "unit_cost": "3.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "1",
                "last_attempt_utc": "2026-05-09T01:00:00Z",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-09T00:00:00Z",
                "completion_block_reason": "bbp_login_required",
            },
            {
                "run_id": "run_b",
                "supplier_id": "heo",
                "supplier_name": "Heo",
                "row_key": "other_login",
                "supplier_sku": "H1",
                "barcode": "6000000000001",
                "supplier_title": "Other Login Row",
                "unit_cost": "4.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "login_backtrack_pending",
                "scan_reason": "login_backtrack_required",
                "attempt_count": "1",
                "last_attempt_utc": "2026-05-09T01:00:00Z",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-09T00:00:00Z",
                "completion_block_reason": "bbp_login_required",
            },
        ],
    )

    counts = _price_list_login_counts(tmp_path, "run_a")

    assert counts == {"login": 3, "bbp_login": 2, "dashboard_login": 1, "login_pending": 2, "login_running": 0}


def test_price_list_login_counts_include_unpromoted_ledger_backlog(tmp_path: Path) -> None:
    _write_f_contract_rows(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_a",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "row_key": "normal",
                "supplier_sku": "S1",
                "barcode": "5000000000001",
                "supplier_title": "Normal Row",
                "unit_cost": "1.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-09T00:00:00Z",
            },
        ],
    )
    _write_f_contract_rows(
        tmp_path,
        "f_login_backtrack_evidence_live",
        [
            {
                "backtrack_id": "bt-dashboard",
                "backtrack_observed_utc": "2026-05-09T01:00:00Z",
                "original_observed_utc": "2026-05-09T00:30:00Z",
                "original_run_id": "run_a",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "supplier_sku": "S2",
                "barcode": "5000000000002",
                "candidate_id": "dashboard-row",
                "unit_cost": "2.00",
                "backtrack_attempt_number": "1",
                "backtrack_status": "missing_dashboard_yes_no",
                "merged_into_candidate_flag": "0",
            },
            {
                "backtrack_id": "bt-unresolved",
                "backtrack_observed_utc": "2026-05-09T01:01:00Z",
                "original_observed_utc": "2026-05-09T00:31:00Z",
                "original_run_id": "run_a",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "supplier_sku": "S3",
                "barcode": "5000000000003",
                "candidate_id": "unresolved-row",
                "unit_cost": "3.00",
                "backtrack_attempt_number": "3",
                "backtrack_status": "dashboard_yes_no_unresolved",
                "merged_into_candidate_flag": "0",
            },
            {
                "backtrack_id": "bt-bbp",
                "backtrack_observed_utc": "2026-05-09T01:02:00Z",
                "original_observed_utc": "2026-05-09T00:32:00Z",
                "original_run_id": "run_a",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "supplier_sku": "S4",
                "barcode": "5000000000004",
                "candidate_id": "bbp-row",
                "unit_cost": "4.00",
                "backtrack_attempt_number": "1",
                "backtrack_status": "blocked_login",
                "merged_into_candidate_flag": "0",
            },
        ],
    )

    counts = _price_list_login_counts(tmp_path, "run_a")

    assert counts == {"login": 3, "bbp_login": 1, "dashboard_login": 2, "login_pending": 0, "login_running": 0}


def test_price_list_login_counts_ignore_stale_resolved_ledger_rows(tmp_path: Path) -> None:
    _write_f_contract_rows(
        tmp_path,
        "f_login_backtrack_evidence_live",
        [
            {
                "backtrack_id": "bt-old",
                "backtrack_observed_utc": "2026-05-13T10:00:00Z",
                "original_observed_utc": "2026-05-13T09:30:00Z",
                "original_run_id": "run_a",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "supplier_sku": "S1",
                "barcode": "5000000000001",
                "candidate_id": "row-1",
                "unit_cost": "2.00",
                "backtrack_attempt_number": "1",
                "backtrack_status": "missing_dashboard_yes_no",
                "merged_into_candidate_flag": "0",
            },
            {
                "backtrack_id": "bt-new",
                "backtrack_observed_utc": "2026-05-13T11:00:00Z",
                "original_observed_utc": "2026-05-13T09:30:00Z",
                "original_run_id": "run_a",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "supplier_sku": "S1",
                "barcode": "5000000000001",
                "candidate_id": "row-1",
                "unit_cost": "2.00",
                "backtrack_attempt_number": "2",
                "backtrack_status": "resolved",
                "merged_into_candidate_flag": "0",
            },
        ],
    )

    counts = _price_list_login_counts(tmp_path, "run_a")

    assert counts == {"login": 0, "bbp_login": 0, "dashboard_login": 0, "login_pending": 0, "login_running": 0}


def test_price_list_login_counts_ignore_stale_unresolved_when_latest_is_merged(tmp_path: Path) -> None:
    _write_f_contract_rows(
        tmp_path,
        "f_login_backtrack_evidence_live",
        [
            {
                "backtrack_id": "bt-old",
                "backtrack_observed_utc": "2026-05-13T10:00:00Z",
                "original_run_id": "run_a",
                "supplier_id": "stax",
                "candidate_id": "row-1",
                "backtrack_attempt_number": "1",
                "backtrack_status": "missing_dashboard_yes_no",
                "merged_into_candidate_flag": "0",
            },
            {
                "backtrack_id": "bt-new",
                "backtrack_observed_utc": "2026-05-13T11:00:00Z",
                "original_run_id": "run_a",
                "supplier_id": "stax",
                "candidate_id": "row-1",
                "backtrack_attempt_number": "2",
                "backtrack_status": "missing_dashboard_yes_no",
                "merged_into_candidate_flag": "1",
            },
        ],
    )

    counts = _price_list_login_counts(tmp_path, "run_a")

    assert counts == {"login": 0, "bbp_login": 0, "dashboard_login": 0, "login_pending": 0, "login_running": 0}


def test_price_list_login_counts_scope_latest_ledger_rows_by_run(tmp_path: Path) -> None:
    _write_f_contract_rows(
        tmp_path,
        "f_login_backtrack_evidence_live",
        [
            {
                "backtrack_id": "bt-run-a",
                "backtrack_observed_utc": "2026-05-13T10:00:00Z",
                "original_observed_utc": "2026-05-13T09:30:00Z",
                "original_run_id": "run_a",
                "supplier_id": "stax",
                "candidate_id": "same-row",
                "backtrack_attempt_number": "1",
                "backtrack_status": "missing_dashboard_yes_no",
                "merged_into_candidate_flag": "0",
            },
            {
                "backtrack_id": "bt-run-b",
                "backtrack_observed_utc": "2026-05-13T11:00:00Z",
                "original_observed_utc": "2026-05-13T10:30:00Z",
                "original_run_id": "run_b",
                "supplier_id": "stax",
                "candidate_id": "same-row",
                "backtrack_attempt_number": "1",
                "backtrack_status": "resolved",
                "merged_into_candidate_flag": "0",
            },
        ],
    )

    counts = _price_list_login_counts(tmp_path, "run_a")

    assert counts == {"login": 1, "bbp_login": 0, "dashboard_login": 1, "login_pending": 0, "login_running": 0}


def test_price_list_auth_state_and_login_button_state(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=visible|browser_state=VISIBLE|auth_state=LOGIN_REQUIRED|reason=auth_required|updated_utc=2026-05-09T09:00:00Z\n",
        encoding="utf-8",
    )

    auth = _price_list_auth_state(tmp_path)
    button = _price_list_login_button_state(
        login_rows=3,
        auth_state=auth["auth_state"],
        request_exists=auth["login_mode_request_exists"] == "1",
    )

    assert auth["auth_state"] == "LOGIN_REQUIRED"
    assert auth["login_mode_request_exists"] == "0"
    assert button["badge_state"] == "required"
    assert button["disabled"] is False

    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=visible|browser_state=VISIBLE|auth_state=AMAZON_DASHBOARD_LOGIN_REQUIRED|reason=amazon_dashboard_login_required|updated_utc=2026-05-09T09:01:00Z\n",
        encoding="utf-8",
    )
    auth = _price_list_auth_state(tmp_path)
    button = _price_list_login_button_state(
        login_rows=3,
        auth_state=auth["auth_state"],
        request_exists=auth["login_mode_request_exists"] == "1",
    )

    assert auth["auth_state"] == "AMAZON_DASHBOARD_LOGIN_REQUIRED"
    assert button["badge_state"] == "dashboard_required"
    assert button["label"] == "YES/NO Login"
    assert button["disabled"] is False

    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=visible|browser_state=VISIBLE|auth_state=BBP_LOGIN_REQUIRED|reason=bbp_login_required|updated_utc=2026-05-09T09:02:00Z\n",
        encoding="utf-8",
    )
    auth = _price_list_auth_state(tmp_path)
    button = _price_list_login_button_state(
        login_rows=3,
        auth_state=auth["auth_state"],
        request_exists=auth["login_mode_request_exists"] == "1",
    )

    assert auth["auth_state"] == "BBP_LOGIN_REQUIRED"
    assert button["badge_state"] == "bbp_required"
    assert button["label"] == "BBP Login"
    assert button["disabled"] is False

    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=visible|browser_state=VISIBLE|auth_state=LOGIN_REQUIRED|reason=auth_required|updated_utc=2026-05-09T09:03:00Z\n",
        encoding="utf-8",
    )
    (live_dir / "f061_login_mode.requested").write_text("status=requested\n", encoding="ascii")
    auth = _price_list_auth_state(tmp_path)
    button = _price_list_login_button_state(
        login_rows=3,
        auth_state=auth["auth_state"],
        request_exists=auth["login_mode_request_exists"] == "1",
    )

    assert auth["login_mode_request_exists"] == "1"
    assert button["badge_state"] == "required"
    assert button["label"] == "Login"
    assert button["disabled"] is False

    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=hidden|browser_state=HIDDEN|auth_state=LOGGED_IN|reason=child_started_minimized|updated_utc=2026-05-09T09:05:00Z\n",
        encoding="utf-8",
    )
    (live_dir / "f061_login_mode.requested").write_text("status=holding\n", encoding="ascii")
    auth = _price_list_auth_state(tmp_path)
    button = _price_list_login_button_state(
        login_rows=3,
        auth_state=auth["auth_state"],
        request_exists=auth["login_mode_request_exists"] == "1",
        request_status=auth["login_mode_request_status"],
    )

    assert auth["login_mode_request_exists"] == "1"
    assert auth["login_mode_request_status"] == "holding"
    assert auth["auth_state"] == ""
    assert button["badge_state"] == "requested"
    assert button["label"] == "Login Requested"
    assert button["disabled"] is True

    (live_dir / "f061_login_mode.requested").write_text("status=drained\n", encoding="ascii")
    auth = _price_list_auth_state(tmp_path)
    button = _price_list_login_button_state(
        login_rows=0,
        auth_state="LOGGED_IN",
        request_exists=auth["login_mode_request_exists"] == "1",
    )

    assert auth["login_mode_request_exists"] == "0"
    assert auth["login_mode_request_status"] == "drained"
    assert button["badge_state"] == "logged_in"
    assert button["disabled"] is True

    button = _price_list_login_button_state(
        login_rows=2,
        auth_state="LOGGED_IN",
        request_exists=auth["login_mode_request_exists"] == "1",
    )

    assert button["badge_state"] == "catching_up"
    assert button["label"] == "Catching Up"
    assert button["disabled"] is True

    (live_dir / "f061_login_mode.requested").write_text("status=still_required\n", encoding="ascii")
    auth = _price_list_auth_state(tmp_path)
    button = _price_list_login_button_state(
        login_rows=2,
        auth_state="LOGIN_REQUIRED",
        request_exists=auth["login_mode_request_exists"] == "1",
    )

    assert auth["login_mode_request_exists"] == "0"
    assert auth["login_mode_request_status"] == "still_required"
    assert button["badge_state"] == "required"
    assert button["disabled"] is False

    button = _price_list_login_button_state(
        login_rows=2,
        auth_state="AMAZON_DASHBOARD_LOGIN_REQUIRED",
        request_exists=True,
    )

    assert button["badge_state"] == "dashboard_required"
    assert button["label"] == "YES/NO Login"
    assert button["disabled"] is False


def test_price_list_manager_mode_state_drives_operator_badge(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_manager_mode_state.txt").write_text(
        "mode=Catching Up|auth_state=LOGGED_IN|browser_mode=minimized|browser_visibility=hidden|updated_utc=2026-05-14T10:00:00Z\n",
        encoding="ascii",
    )

    state = _price_list_manager_mode_state(tmp_path)
    badge = _price_list_login_badge_html(
        {"badge_state": "logged_in"},
        login_rows=9,
        auth_state="LOGGED_IN",
        manager_mode=state["mode"],
    )

    assert state["mode"] == "Catching Up"
    assert "CATCHING UP" in badge
    assert "9 rows" in badge


def test_price_list_supervisor_state_drives_visible_badge(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "fpm_live_supervisor_state.txt").write_text(
        "state=ok|reason=freshest_live_state_seconds=2.0|manager_pids=123|child_pids=456|updated_utc=2026-05-14T14:31:23Z\n",
        encoding="ascii",
    )

    state = _price_list_supervisor_state(tmp_path)
    badge = _price_list_supervisor_badge_html(state)

    assert state["state"] == "ok"
    assert state["badge_state"] == "ok"
    assert "SUPERVISOR OK" in badge
    assert "freshest_live_state_seconds=2.0" in badge


def test_price_list_login_mode_request_writes_control_file_and_event_only(tmp_path: Path) -> None:
    result = request_price_list_login_mode_from_ui(
        tmp_path,
        supplier_id="stax",
        run_id="fpm_stax_20260507T151124Z",
        observed_utc="2026-05-09T09:15:00Z",
    )

    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    request_path = live_dir / "f061_login_mode.requested"
    event_path = live_dir / "live_cycle_events.csv"
    event_df = pd.read_csv(event_path, dtype=str).fillna("")

    assert result["status"] == "requested"
    assert request_path.exists()
    assert "requested_by=operator_ui" in request_path.read_text(encoding="ascii")
    assert "mode=login_recovery" in request_path.read_text(encoding="ascii")
    assert "hold_seconds=900" in request_path.read_text(encoding="ascii")
    assert result["hold_seconds"] == "900"
    assert not (live_dir / "f061_visible_login.requested").exists()
    assert event_df.iloc[-1]["event_type"] == "login_mode_requested"
    assert event_df.iloc[-1]["supplier_id"] == "stax"
    assert event_df.iloc[-1]["f061_run_id"] == "fpm_stax_20260507T151124Z"


def test_price_list_live_progress_helpers_read_runtime_files(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "observed_utc": "2026-04-30T20:00:00Z",
                "loop_run_id": "fpm_live_old",
                "pid": "111",
                "state": "running",
                "supplier_id": "old_supplier",
                "f061_run_id": "old_run",
                "pending_before": "12",
                "action": "resume_f061_active_run",
                "action_status": "success",
                "chunk_rows": "5",
                "safe_to_handoff_flag": "0",
                "detail": "old",
            },
            {
                "observed_utc": "2026-04-30T20:02:00Z",
                "loop_run_id": "fpm_live_new",
                "pid": "222",
                "state": "running",
                "supplier_id": "entertainment_trading",
                "f061_run_id": "fpm_entertainment_trading_20260430T151417Z",
                "pending_before": "7",
                "action": "resume_f061_active_run",
                "action_status": "success",
                "chunk_rows": "5",
                "safe_to_handoff_flag": "0",
                "detail": "f061_subprocess_completed",
            },
        ]
    ).to_csv(live_dir / "live_cycle_status.csv", index=False)
    (live_dir / "live_cycle_events.csv").write_text(
        "observed_utc,run_id,event_type,active_supplier_id,active_f061_run_id,status,chunk_rows,detail\n"
        "2026-04-30T20:02:30Z,fpm_live_new,scanner_chunk,entertainment_trading,"
        "fpm_entertainment_trading_20260430T151417Z,success,5,pending_after=7\n",
        encoding="utf-8",
    )

    active_run = tmp_path / "out" / "systems" / "F" / "inbox" / "supplier_price_list_active_run.csv"
    active_run.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"barcode": "111", "scan_status": "done"},
            {"barcode": "222", "scan_status": "pending"},
            {"barcode": "333", "scan_status": "pending"},
        ]
    ).to_csv(active_run, index=False)

    status = _latest_price_list_live_status(tmp_path)
    counts = _price_list_active_run_counts(tmp_path)
    event = _latest_price_list_live_event(tmp_path)
    progress_total = _price_list_live_progress_total(tmp_path, "fpm_entertainment_trading_20260430T151417Z")

    assert status["supplier_id"] == "entertainment_trading"
    assert status["pending_before"] == "7"
    assert counts == {"total": 3, "pending": 2, "done": 1, "held": 0}
    assert event == (
        "2026-04-30T20:02:30Z,fpm_live_new,scanner_chunk,entertainment_trading,"
        "fpm_entertainment_trading_20260430T151417Z,success,5,pending_after=7"
    )
    assert progress_total == 12


def test_price_list_child_status_reads_live_heartbeat(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_child_status.txt").write_text(
        "pid=19600|supplier_id=entertainment_trading|chunk_rows=5|heartbeat=2026-04-30T20:27:19Z",
        encoding="utf-8",
    )

    assert "pid=19600" in _price_list_child_status(tmp_path)


def test_price_list_child_status_flags_stale_child_output(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_child_status.txt").write_text(
        "pid=19600|supplier_id=entertainment_trading|chunk_rows=5|heartbeat=2026-04-30T20:27:19Z",
        encoding="utf-8",
    )
    stdout = live_dir / "f061_child_stdout.log"
    stdout.write_text("stale output\n", encoding="utf-8")
    stale_epoch = time.time() - 3600
    stdout.touch()

    os.utime(stdout, (stale_epoch, stale_epoch))

    status = _price_list_child_status(tmp_path)

    assert "pid=19600" in status
    assert "warning=no_child_output_30m" in status


def test_price_list_live_progress_total_reads_runtime_event_columns(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "live_cycle_events.csv").write_text(
        "event_utc,cycle_run_id,event_type,supplier_id,f061_run_id,status,rows,notes\n"
        "2026-04-30T15:14:17Z,fpm_live,scanner_chunk,entertainment_trading,"
        "fpm_entertainment_trading_20260430T151417Z,success,50,pending_after=20033\n",
        encoding="utf-8",
    )

    progress_total = _price_list_live_progress_total(tmp_path, "fpm_entertainment_trading_20260430T151417Z")

    assert progress_total == 20083


def test_price_list_live_eta_uses_current_run_speed(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "live_cycle_events.csv").write_text(
        "event_utc,cycle_run_id,event_type,supplier_id,f061_run_id,status,rows,notes\n"
        "2026-04-30T20:00:00Z,fpm_live,scanner_chunk,entertainment_trading,"
        "fpm_entertainment_trading_20260430T151417Z,success,5,pending_after=95\n"
        "2026-04-30T21:00:00Z,fpm_live,scanner_chunk,entertainment_trading,"
        "fpm_entertainment_trading_20260430T151417Z,success,5,pending_after=55\n",
        encoding="utf-8",
    )

    eta = _price_list_live_eta(tmp_path, "fpm_entertainment_trading_20260430T151417Z", 80)

    assert round(float(eta["rows_per_hour"]), 1) == 45.0
    assert eta["eta_label"] == "1h 47m"
    assert eta["sample_rows"] == 45


def test_price_list_live_result_counts_read_current_run_state(tmp_path: Path) -> None:
    inbox_dir = tmp_path / "out" / "systems" / "F" / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "supplier_id": "entertainment_trading",
                "supplier_name": "Entertainment Trading",
                "run_id": "fpm_entertainment_trading_20260430T151417Z",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "Stocklist.xlsx",
                "source_seen_at_utc": "2026-04-30T14:13:50Z",
                "normalized_utc": "2026-04-30T15:14:17Z",
                "total_rows": "20083",
                "pending_rows": "19693",
                "done_rows": "390",
                "failed_rows": "383",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-04-30T20:09:59Z",
                "completed_at_utc": "",
            }
        ]
    ).to_csv(inbox_dir / "supplier_price_list_run_state.csv", index=False)
    screening_dir = tmp_path / "out" / "systems" / "F" / "live"
    screening_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"run_id": "fpm_entertainment_trading_20260430T151417Z", "row_status": "pass", "pf": "PASS"},
            {"run_id": "fpm_entertainment_trading_20260430T151417Z", "row_status": "timeout", "pf": "FAIL"},
            {"run_id": "fpm_entertainment_trading_20260430T151417Z", "row_status": "rescan", "pf": "RESCAN"},
            {"run_id": "other_run", "row_status": "rescan"},
        ]
    ).to_csv(screening_dir / "f_screening_row_state_live.csv", index=False)

    counts = _price_list_live_result_counts(tmp_path, "fpm_entertainment_trading_20260430T151417Z")

    assert counts == {"pass": 1, "fail": 1, "rescan": 1, "done": 390, "pending": 19693, "held": 0}


def test_price_list_live_counts_are_scoped_to_active_run(tmp_path: Path) -> None:
    inbox_dir = tmp_path / "out" / "systems" / "F" / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "supplier_id": "dhb",
                "supplier_name": "DHB",
                "run_id": "dhb_run",
                "run_status": "running",
                "total_rows": "959",
                "pending_rows": "914",
                "done_rows": "45",
                "failed_rows": "45",
                "held_rows": "0",
            },
            {
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "run_id": "stax_run",
                "run_status": "paused",
                "total_rows": "24205",
                "pending_rows": "0",
                "done_rows": "3943",
                "failed_rows": "3616",
                "held_rows": "20262",
            },
        ]
    ).to_csv(inbox_dir / "supplier_price_list_run_state.csv", index=False)
    pd.DataFrame(
        [
            {"run_id": "dhb_run", "scan_status": "pending"},
            {"run_id": "dhb_run", "scan_status": "pending"},
            {"run_id": "dhb_run", "scan_status": "done"},
            {"run_id": "stax_run", "scan_status": "held"},
            {"run_id": "stax_run", "scan_status": "held"},
        ]
    ).to_csv(inbox_dir / "supplier_price_list_active_run.csv", index=False)

    active_counts = _price_list_active_run_counts(tmp_path, "dhb_run")
    result_counts = _price_list_live_result_counts(tmp_path, "dhb_run")

    assert active_counts == {"total": 3, "pending": 2, "done": 1, "held": 0}
    assert result_counts["done"] == 45
    assert result_counts["pending"] == 914
    assert result_counts["held"] == 0


def test_price_list_recovery_counts_read_legacy_import_progress(tmp_path: Path) -> None:
    progress_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    progress_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "imported_at_utc": "2026-04-30T14:50:01Z",
                "supplier_id": "entertainment_trading",
                "batch_id": "entertainment_trading_source",
                "legacy_run_id": "stocklist_supplier_webscrape_reset_20260429T164504Z",
                "legacy_total_rows": "21817",
                "legacy_pending_rows": "20116",
                "legacy_done_rows": "1701",
                "legacy_failed_rows": "1584",
                "pending_source_rows": "20116",
                "pending_matched_rows": "20083",
                "pending_held_rows": "33",
                "pending_unmatched_rows": "0",
                "manager_valid_rows": "20083",
                "manager_scan_now_rows": "20083",
                "manager_recovery_skipped_rows": "22366",
                "manager_held_rows": "268",
                "legacy_active_run_path": "active_run.csv",
                "legacy_run_state_path": "run_state.csv",
            }
        ]
    ).to_csv(progress_dir / "f061_recovery_progress.csv", index=False)

    counts = _price_list_recovery_counts(tmp_path, "entertainment_trading")

    assert counts == {
        "legacy_done": 1701,
        "legacy_pass": 117,
        "legacy_fail": 1584,
        "legacy_pending": 20116,
        "matched_pending": 20083,
    }


def test_price_list_queue_control_helper_prioritises_supplier_and_rebuilds_dashboard(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    test_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "source_type": "api_pull",
                "source_subtype": "csv_link",
                "source_url": "https://example.test/stax.csv",
                "source_folder_path": "",
                "existing_supplier_config_path": "",
                "converter_id": "stax",
                "normal_refresh_days": "1",
                "minimum_rescan_days": "1",
                "large_file_flag": "1",
                "manual_request_required_flag": "0",
                "priority_band": "api",
                "active_flag": "1",
                "notes": "test",
            },
            {
                "supplier_id": "heo",
                "supplier_name": "Heo",
                "source_type": "api_pull",
                "source_subtype": "api",
                "source_url": "https://example.test/heo",
                "source_folder_path": "",
                "existing_supplier_config_path": "",
                "converter_id": "heo",
                "normal_refresh_days": "1",
                "minimum_rescan_days": "1",
                "large_file_flag": "0",
                "manual_request_required_flag": "0",
                "priority_band": "api",
                "active_flag": "1",
                "notes": "test",
            },
        ],
        columns=SUPPLIER_REGISTRY_COLUMNS,
    ).to_csv(test_dir / "supplier_registry.csv", index=False)
    pd.DataFrame(
        [
            {
                "batch_id": "stax_batch",
                "supplier_id": "stax",
                "source_type": "api_pull",
                "source_subtype": "csv_link",
                "source_received_at_utc": "2026-04-30T10:00:00Z",
                "source_file_path": "stax.csv",
                "source_file_hash": "hash_s",
                "converted_file_path": "stax_converted.csv",
                "source_row_count": "2",
                "valid_row_count": "2",
                "held_row_count": "0",
                "new_row_count": "2",
                "changed_row_count": "0",
                "eligible_row_count": "2",
                "skipped_cooldown_row_count": "0",
                "batch_status": "imported_from_source",
                "status_reason": "ready_source_file_imported",
                "updated_at_utc": "2026-04-30T10:01:00Z",
            },
            {
                "batch_id": "heo_batch",
                "supplier_id": "heo",
                "source_type": "api_pull",
                "source_subtype": "api",
                "source_received_at_utc": "2026-04-30T10:05:00Z",
                "source_file_path": "heo.csv",
                "source_file_hash": "hash_h",
                "converted_file_path": "heo_converted.csv",
                "source_row_count": "1",
                "valid_row_count": "1",
                "held_row_count": "0",
                "new_row_count": "1",
                "changed_row_count": "0",
                "eligible_row_count": "1",
                "skipped_cooldown_row_count": "0",
                "batch_status": "imported_from_source",
                "status_reason": "ready_source_file_imported",
                "updated_at_utc": "2026-04-30T10:06:00Z",
            },
        ],
        columns=PRICE_LIST_BATCH_COLUMNS,
    ).to_csv(test_dir / "price_list_batches.csv", index=False)
    pd.DataFrame(
        [
            {
                "batch_id": "stax_batch",
                "supplier_id": "stax",
                "row_key": "s1",
                "supplier_sku": "S1",
                "supplier_title": "Stax 1",
                "barcode": "5000000000001",
                "unit_cost": "1.00",
                "currency": "GBP",
                "vat_rate": "20",
                "source_row_hash": "s1",
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "valid",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            },
            {
                "batch_id": "stax_batch",
                "supplier_id": "stax",
                "row_key": "s2",
                "supplier_sku": "S2",
                "supplier_title": "Stax 2",
                "barcode": "5000000000002",
                "unit_cost": "2.00",
                "currency": "GBP",
                "vat_rate": "20",
                "source_row_hash": "s2",
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "valid",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            },
            {
                "batch_id": "heo_batch",
                "supplier_id": "heo",
                "row_key": "h1",
                "supplier_sku": "H1",
                "supplier_title": "Heo 1",
                "barcode": "6000000000001",
                "unit_cost": "3.00",
                "currency": "GBP",
                "vat_rate": "20",
                "source_row_hash": "h1",
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "valid",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            },
        ],
        columns=BATCH_ROW_COLUMNS,
    ).to_csv(test_dir / "batch_rows.csv", index=False)

    result = apply_price_list_queue_control(
        root=tmp_path,
        supplier_id="heo",
        control_state="prioritised",
        priority_rank="1",
        reason="operator test",
        observed_utc="2026-04-30T12:00:00Z",
    )

    dashboard = pd.read_csv(test_dir / "status_dashboard.csv", dtype=str).fillna("")
    decisions = pd.read_csv(test_dir / "manager_decisions.csv", dtype=str).fillna("")
    preview = pd.read_csv(test_dir / "f061_handoff_preview.csv", dtype=str).fillna("")
    by_supplier = dashboard.set_index("supplier_id")
    assert result["status"] == "success"
    assert result["decision"]["selected_supplier_id"] == "heo"
    assert decisions.iloc[-1]["reason_code"] == "operator_prioritised_supplier"
    assert by_supplier.loc["heo", "queue_position"] == "1"
    assert by_supplier.loc["heo", "queue_state"] == "Recommended"
    assert by_supplier.loc["heo", "control_state"] == "Prioritised #1"
    assert preview.iloc[-1]["supplier_id"] == "heo"
    assert preview.iloc[-1]["technical_ready_flag"] == "1"
    assert preview.iloc[-1]["approval_state"] == "required"
    assert preview.iloc[-1]["live_apply_allowed"] == "0"


def test_price_list_handoff_approval_helper_records_exact_batch_and_rebuilds_preview(tmp_path: Path) -> None:
    test_price_list_queue_control_helper_prioritises_supplier_and_rebuilds_dashboard(tmp_path)
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"

    approve = apply_price_list_handoff_approval(
        root=tmp_path,
        supplier_id="heo",
        batch_id="heo_batch",
        approval_state="approved",
        reason="operator ui test approval",
        observed_utc="2026-04-30T12:10:00Z",
    )

    approvals = pd.read_csv(test_dir / "f061_handoff_approvals.csv", dtype=str).fillna("")
    preview = pd.read_csv(test_dir / "f061_handoff_preview.csv", dtype=str).fillna("")
    assert approve["status"] == "success"
    assert approve["approval"]["approval_state"] == "approved"
    assert approve["handoff"]["approval_state"] == "approved"
    assert approve["handoff"]["technical_ready_flag"] == "1"
    assert approve["handoff"]["live_apply_allowed"] == "1"
    assert approvals.iloc[-1]["supplier_id"] == "heo"
    assert approvals.iloc[-1]["batch_id"] == "heo_batch"
    assert approvals.iloc[-1]["approved_by"] == "operator_ui"
    assert preview.iloc[-1]["approval_id"] == approve["approval"]["approval_id"]

    revoke = apply_price_list_handoff_approval(
        root=tmp_path,
        supplier_id="heo",
        batch_id="heo_batch",
        approval_state="revoked",
        reason="operator ui test revoke",
        observed_utc="2026-04-30T12:15:00Z",
    )

    preview = pd.read_csv(test_dir / "f061_handoff_preview.csv", dtype=str).fillna("")
    assert revoke["handoff"]["approval_state"] == "revoked"
    assert revoke["handoff"]["live_apply_allowed"] == "0"
    assert preview.iloc[-1]["approval_state"] == "revoked"


def test_copy_value_html_builds_click_to_copy_button() -> None:
    html = _copy_value_html("ABC-123")
    assert "navigator.clipboard.writeText(" in html
    assert "ABC-123" in html
    assert ">ABC-123<" in html


def test_reorder_draft_uses_stable_identity_and_clears_after_send() -> None:
    row = {
        "seller_sku": "SKU-KEEP",
        "asin": "ASIN-KEEP",
        "supplier_name": "Alpha",
        "title": "Draft Product",
        "send": False,
        "snze": False,
        "disc": False,
        "drop": False,
        "order_qty": "",
        "confirmed_price": "",
        "snooze_date": "",
    }
    identity = _reorder_row_identity(row)
    drafts = {
        identity: {
            "send": True,
            "snze": True,
            "disc": False,
            "drop": False,
            "order_qty": "12",
            "confirmed_price": "4.50",
            "snooze_date": "2026-04-20",
        }
    }

    applied_identity, merged = _apply_reorder_draft(row, drafts)

    assert applied_identity == identity
    assert merged["send"] is True
    assert merged["snze"] is True
    assert merged["order_qty"] == "12"
    assert merged["confirmed_price"] == "4.50"
    assert _extract_reorder_draft(merged)["snooze_date"] == "2026-04-20"

    row_key = _reorder_widget_key(merged)
    session_state = {
        "o_reorder_drafts": {identity: _extract_reorder_draft(merged)},
        f"qty_{row_key}": "12",
        f"price_{row_key}": "4.50",
        f"send_{row_key}": True,
        f"snze_{row_key}": True,
        f"snooze_{row_key}": "2026-04-20",
    }
    _clear_reorder_drafts(session_state, [merged])

    assert identity not in session_state["o_reorder_drafts"]
    assert f"qty_{row_key}" not in session_state
    assert f"price_{row_key}" not in session_state
    assert f"send_{row_key}" not in session_state


def test_ui_loads_decision_event_inbox_dataset(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_decision_events",
        [
            {
                "event_utc": "2026-04-17T10:00:00Z",
                "event_id": "evt-1",
                "seller_sku": "SKU-1",
                "asin": "ASIN-1",
                "action": "approve_full_restock",
                "confirmed_unit_cost": "5.5",
                "confirmed_qty": "12",
                "snooze_until_utc": "",
                "decision_note": "",
                "actor": "operator_ui",
                "cost_mode": "live",
                "source_reference": "o_ui_supplier_batch:Alpha",
            }
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)
    assert "restock_decision_events" in datasets
    assert len(datasets["restock_decision_events"]) == 1
    assert "product_db_operator_view" in datasets
    assert "product_db_edit_events" in datasets
    assert "product_db_edit_holds" in datasets
    assert "amazon_listing_drafts_live" in datasets
    assert "amazon_listing_preview_events" in datasets
    assert "amazon_listing_preview_issues_live" in datasets
    assert "amazon_listing_holds_live" in datasets


def test_build_amazon_listing_draft_display_df_merges_hold_reason(tmp_path: Path) -> None:
    _write_f_contract_rows(
        tmp_path,
        "amazon_listing_drafts_live",
        [
            {
                "observed_utc": "2026-05-01T10:50:00Z",
                "draft_id": "draft-1",
                "supplier_id": "supplier_a",
                "supplier_name": "Supplier A",
                "source_run_id": "run-1",
                "review_snapshot_id": "snap-1",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-1",
                "supplier_sku": "SUP-1",
                "barcode": "5012345678901",
                "asin": "B000000001",
                "amazon_title": "Review Product",
                "supplier_cost_gbp": "",
                "expected_seller_sku": "NP-SUP-ABC12345",
                "sku_reservation_status": "reserved",
                "sku_reservation_reason": "reserved",
                "marketplace_id": "A1F83G8C2ARO7P",
                "product_type": "",
                "condition_type": "new_new",
                "fulfillment_channel": "AFN",
                "starting_price_gbp": "",
                "starting_quantity": "0",
                "listing_mode": "existing_asin_offer",
                "draft_status": "blocked_missing_local_data",
                "block_reason": "missing_local_data:supplier_cost_gbp,product_type,starting_price_gbp",
                "amazon_preview_status": "not_run",
                "amazon_preview_issue_count": "0",
                "amazon_submission_status": "not_submitted",
                "amazon_submission_id": "",
                "updated_at_utc": "2026-05-01T10:50:00Z",
                "source_intake_id": "intake-1",
            }
        ],
    )
    _write_f_contract_rows(
        tmp_path,
        "amazon_listing_holds_live",
        [
            {
                "hold_utc": "2026-05-01T10:50:00Z",
                "hold_id": "hold-1",
                "hold_stage": "draft_builder",
                "supplier_id": "supplier_a",
                "active_run_id": "run-1",
                "candidate_id": "cand-1",
                "asin": "B000000001",
                "expected_seller_sku": "NP-SUP-ABC12345",
                "hold_reason": "missing_local_data:supplier_cost_gbp,product_type,starting_price_gbp",
                "hold_note": "Draft is blocked",
                "source_reference": "test",
                "intake_id": "intake-1",
                "draft_id": "draft-1",
                "marketplace_id": "A1F83G8C2ARO7P",
            }
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)
    display_df = build_amazon_listing_draft_display_df(datasets)

    assert len(display_df.index) == 1
    assert display_df.iloc[0]["expected_seller_sku"] == "NP-SUP-ABC12345"
    assert display_df.iloc[0]["hold_reason"] == "missing_local_data:supplier_cost_gbp,product_type,starting_price_gbp"


def test_submit_amazon_listing_draft_approval_marks_ready_for_preview(tmp_path: Path) -> None:
    _write_f_contract_rows(
        tmp_path,
        "amazon_listing_drafts_live",
        [
            {
                "observed_utc": "2026-05-01T10:50:00Z",
                "draft_id": "draft-approve",
                "supplier_id": "supplier_a",
                "supplier_name": "Supplier A",
                "source_run_id": "run-1",
                "review_snapshot_id": "snap-1",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-1",
                "supplier_sku": "SUP-1",
                "barcode": "5012345678901",
                "asin": "B000000001",
                "amazon_title": "Review Product",
                "supplier_cost_gbp": "3.50",
                "expected_seller_sku": "NP-SUP-ABC12345",
                "sku_reservation_status": "reserved",
                "sku_reservation_reason": "reserved",
                "marketplace_id": "A1F83G8C2ARO7P",
                "product_type": "PRODUCT",
                "condition_type": "new_new",
                "fulfillment_channel": "AFN",
                "starting_price_gbp": "9.99",
                "starting_quantity": "0",
                "listing_mode": "existing_asin_offer",
                "draft_status": "ready_for_listing_approval",
                "block_reason": "",
                "amazon_preview_status": "not_run",
                "amazon_preview_issue_count": "0",
                "amazon_submission_status": "not_submitted",
                "amazon_submission_id": "",
                "updated_at_utc": "2026-05-01T10:50:00Z",
                "listing_approval_status": "pending_operator_approval",
            }
        ],
    )

    ok, status, row = submit_amazon_listing_draft_approval(
        root=tmp_path,
        draft_id="draft-approve",
        actor="tester",
    )

    assert ok is True
    assert status == "approved_for_preview"
    assert row["draft_status"] == "ready_for_amazon_preview"
    drafts = load_operator_datasets(root=tmp_path)["amazon_listing_drafts_live"]
    assert drafts.iloc[0]["listing_approval_status"] == "approved_for_preview"
    events = load_operator_datasets(root=tmp_path)["amazon_listing_draft_events"]
    assert len(events.index) == 1
    assert events.iloc[0]["event_type"] == "listing_draft_approved"


def test_submit_amazon_listing_draft_approval_refuses_blocked_draft(tmp_path: Path) -> None:
    _write_f_contract_rows(
        tmp_path,
        "amazon_listing_drafts_live",
        [
            {
                "observed_utc": "2026-05-01T10:50:00Z",
                "draft_id": "draft-blocked",
                "candidate_id": "cand-1",
                "asin": "B000000001",
                "expected_seller_sku": "NP-SUP-ABC12345",
                "marketplace_id": "A1F83G8C2ARO7P",
                "draft_status": "blocked_missing_local_data",
                "block_reason": "missing_local_data:product_type",
            }
        ],
    )

    ok, status, _ = submit_amazon_listing_draft_approval(root=tmp_path, draft_id="draft-blocked")

    assert ok is False
    assert status == "draft_blocked"
    events = load_operator_datasets(root=tmp_path)["amazon_listing_draft_events"]
    assert len(events.index) == 0


def test_run_amazon_listing_preview_for_draft_calls_f093(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_run_amazon_listing_preview(**kwargs):
        captured.update(kwargs)
        return {
            "eligible_rows": 1,
            "attempted_rows": 1,
            "passed_rows": 1,
            "rejected_rows": 0,
            "failed_rows": 0,
        }

    monkeypatch.setattr(
        "scripts.flows.F.F093_run_amazon_listing_preview.run_amazon_listing_preview",
        fake_run_amazon_listing_preview,
    )

    result = run_amazon_listing_preview_for_draft(root=tmp_path, draft_id="draft-1")

    assert result["passed_rows"] == 1
    assert captured["root"] == tmp_path
    assert captured["draft_ids"] == ["draft-1"]
    assert captured["run_preview"] is True
    assert captured["max_rows"] == 1


def test_build_test_orders_df_groups_latest_sample_submissions(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_source_view",
        [
            {
                "asof_utc": "2026-04-17T09:00:00Z",
                "seller_sku": "SKU-T1",
                "asin": "ASIN-T1",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "sale_status": "active",
                "available_now": "0",
                "total_quantity_now": "0",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_7d": "1",
                "velocity_30d": "1",
                "velocity_90d": "1",
                "current_supplier_buy_cost_gbp": "2.5",
                "current_supplier_cost_source": "supplier_catalog_price",
                "market_price_gbp": "5.0",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "expected_refund_cost_per_unit_gbp": "0",
                "roi_at_market_price_pct": "30",
                "source_inventory_asof": "2026-04-17T09:00:00Z",
                "source_velocity_asof": "2026-04-17",
                "source_performance_asof": "2026-04-17",
                "title": "Alpha Test Item",
                "supplier_sku": "ALPHA-SUP-1",
                "barcode": "123456",
            },
            {
                "asof_utc": "2026-04-17T09:00:00Z",
                "seller_sku": "SKU-T2",
                "asin": "ASIN-T2",
                "supplier_code": "SUP-B",
                "supplier_name": "Beta",
                "sale_status": "active",
                "available_now": "0",
                "total_quantity_now": "0",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_7d": "1",
                "velocity_30d": "1",
                "velocity_90d": "1",
                "current_supplier_buy_cost_gbp": "3.0",
                "current_supplier_cost_source": "supplier_catalog_price",
                "market_price_gbp": "6.0",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "expected_refund_cost_per_unit_gbp": "0",
                "roi_at_market_price_pct": "30",
                "source_inventory_asof": "2026-04-17T09:00:00Z",
                "source_velocity_asof": "2026-04-17",
                "source_performance_asof": "2026-04-17",
                "title": "Beta Test Item",
                "supplier_sku": "BETA-SUP-2",
                "barcode": "654321",
            },
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_decision_events",
        [
            {
                "event_utc": "2026-04-17T10:00:00Z",
                "event_id": "evt-old",
                "seller_sku": "SKU-T1",
                "asin": "ASIN-T1",
                "action": "approve_full_restock",
                "confirmed_unit_cost": "2.4",
                "confirmed_qty": "10",
                "snooze_until_utc": "",
                "decision_note": "",
                "actor": "operator_ui",
                "cost_mode": "live",
                "source_reference": "o_ui_supplier_batch:Alpha",
            },
            {
                "event_utc": "2026-04-17T10:05:00Z",
                "event_id": "evt-new",
                "seller_sku": "SKU-T1",
                "asin": "ASIN-T1",
                "action": "approve_full_restock",
                "confirmed_unit_cost": "2.5",
                "confirmed_qty": "12",
                "snooze_until_utc": "",
                "decision_note": "",
                "actor": "operator_ui",
                "cost_mode": "live",
                "source_reference": "o_ui_supplier_batch:Alpha",
            },
            {
                "event_utc": "2026-04-17T10:06:00Z",
                "event_id": "evt-beta",
                "seller_sku": "SKU-T2",
                "asin": "ASIN-T2",
                "action": "approve_test_restock",
                "confirmed_unit_cost": "3.0",
                "confirmed_qty": "8",
                "snooze_until_utc": "",
                "decision_note": "",
                "actor": "operator_ui",
                "cost_mode": "live",
                "source_reference": "o_ui_supplier_batch:Beta",
            },
            {
                "event_utc": "2026-04-17T10:07:00Z",
                "event_id": "evt-ignore",
                "seller_sku": "SKU-X",
                "asin": "ASIN-X",
                "action": "snooze",
                "confirmed_unit_cost": "",
                "confirmed_qty": "",
                "snooze_until_utc": "2026-04-21T00:00:00Z",
                "decision_note": "",
                "actor": "operator_ui",
                "cost_mode": "live",
                "source_reference": "o_ui_supplier_batch:Other",
            },
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)
    test_orders_df = build_test_orders_df(datasets)
    assert len(test_orders_df) == 2
    alpha = test_orders_df[test_orders_df["seller_sku"] == "SKU-T1"].iloc[0]
    beta = test_orders_df[test_orders_df["seller_sku"] == "SKU-T2"].iloc[0]
    assert alpha["supplier_name"] == "Alpha"
    assert alpha["title"] == "Alpha Test Item"
    assert alpha["supply_code"] == "ALPHA-SUP-1"
    assert alpha["ordered_qty"] == "12"
    assert alpha["ordered_unit_cost_gbp"] == "2.5"
    assert alpha["line_value_gbp"] == "30"
    assert beta["supplier_name"] == "Beta"
    assert beta["ordered_qty"] == "8"
    assert beta["action"] == "approve_test_restock"


def test_build_po_draft_review_df_presents_operator_fields() -> None:
    datasets = {
        "purchase_orders_live": pd.DataFrame(
            [
                {
                    "po_id": "PO-DRAFT-1",
                    "supplier_name": "ABGee",
                    "po_status": "draft",
                    "total_lines": "1",
                    "total_units": "2",
                    "total_value_gbp": "15.18",
                }
            ]
        ),
        "purchase_order_lines_live": pd.DataFrame(
            [
                {
                    "po_id": "PO-DRAFT-1",
                    "po_line_id": "PO-DRAFT-1-L001",
                    "seller_sku": "12-749B-9EB5",
                    "asin": "B084HZRR8G",
                    "title": "Leatherface Funko Pop",
                    "ordered_qty": "2",
                    "ordered_unit_cost_gbp": "7.59",
                    "supplier_sku": "985 49830",
                    "barcode": "889698498302",
                    "source_bridge_reference": "legacy_purchase_list:sheet:Purchase List:row3",
                }
            ]
        ),
        "product_db_operator_view": pd.DataFrame(
            [
                {
                    "seller_sku": "12-749B-9EB5",
                    "asin": "B084HZRR8G",
                    "main_image": "https://example.com/leatherface.jpg",
                }
            ]
        ),
    }

    review_df = build_po_draft_review_df(datasets)

    assert len(review_df) == 1
    row = review_df.iloc[0]
    assert row["supplier_name"] == "ABGee"
    assert row["seller_sku"] == "12-749B-9EB5"
    assert row["ordered_qty"] == "2"
    assert row["ordered_unit_cost_gbp"] == "7.59"
    assert row["line_value_gbp"] == "15.18"
    assert row["supplier_sku"] == "985 49830"
    assert row["barcode"] == "889698498302"
    assert row["main_image"] == "https://example.com/leatherface.jpg"
    assert row["source_label"] == "Google Sheet bridge"


def test_ui_loads_current_o_outputs_and_builds_recommendation_display(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_review_queue",
        [
            {
                "queue_utc": "2026-04-03T10:00:00Z",
                "seller_sku": "SKU-1",
                "asin": "ASIN-1",
                "title": "Example Product",
                "main_image": "https://example.com/image.jpg",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "recommendation_status": "full_restock",
                "suggested_qty": "12",
                "suggested_unit_cost_gbp": "5",
                "suggested_market_price_gbp": "8",
                "expected_forward_roi_pct": "60",
                "expected_forward_profit_per_unit_gbp": "3",
                "days_cover_available_only": "1",
                "days_cover_total_pipeline": "1",
                "reason_codes": "ROI_OK",
                "queue_status": "needs_review",
                "suggested_action": "full_restock",
                "key_reason": "ROI_OK",
                "confidence_note": "",
                "cost_mode": "test",
                "recommendation_basis": "test_cost_snapshot",
                "snooze_until_utc": "",
            }
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)
    assert "restock_review_queue" in datasets
    assert len(datasets["restock_review_queue"]) == 1

    display_df = build_recommendations_display_df(datasets)
    assert len(display_df) == 1
    row = display_df.iloc[0]
    assert row["title"] == "Example Product"
    assert row["main_image"] == "https://example.com/image.jpg"
    assert row["seller_sku"] == "SKU-1"
    assert row["suggested_action"] == "full_restock"
    assert row["recommendation_reason"] == "ROI_OK"
    assert row["cost_mode"] == "test"
    assert row["recommendation_basis"] == "test_cost_snapshot"
    assert row["queue_status"] == "needs_review"

    card_html = _render_recommendation_cards(display_df)
    assert "Example Product" in card_html
    assert "SKU: SKU-1" in card_html
    assert "ASIN: ASIN-1" in card_html
    assert "https://example.com/image.jpg" in card_html


def test_ui_recommendation_cards_render_backtest_section_from_source_view(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_review_queue",
        [
            {
                "queue_utc": "2026-04-03T10:00:00Z",
                "seller_sku": "SKU-BT1",
                "asin": "ASIN-BT1",
                "title": "Backtest Product",
                "main_image": "",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "recommendation_status": "full_restock",
                "suggested_qty": "8",
                "suggested_unit_cost_gbp": "4.2",
                "suggested_market_price_gbp": "7.9",
                "expected_forward_roi_pct": "40",
                "expected_forward_profit_per_unit_gbp": "1.5",
                "days_cover_available_only": "3",
                "days_cover_total_pipeline": "3",
                "reason_codes": "ROI_OK",
                "queue_status": "needs_review",
                "suggested_action": "full_restock",
                "key_reason": "ROI_OK",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_source_view",
        [
            {
                "asof_utc": "2026-04-03T10:00:00Z",
                "seller_sku": "SKU-BT1",
                "asin": "ASIN-BT1",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "sale_status": "active",
                "available_now": "3",
                "total_quantity_now": "3",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_7d": "1",
                "velocity_30d": "1",
                "velocity_90d": "1",
                "current_supplier_buy_cost_gbp": "4.2",
                "current_supplier_cost_source": "supplier_catalog_price",
                "market_price_gbp": "7.9",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "expected_refund_cost_per_unit_gbp": "0.1",
                "roi_at_market_price_pct": "40",
                "source_inventory_asof": "2026-04-03T09:00:00Z",
                "source_velocity_asof": "2026-04-03",
                "source_performance_asof": "2026-04-03",
                "backtest_policy_id": "policy_live_default",
                "backtest_history_confidence": "high",
                "backtest_market_viability_score": "81.2",
                "backtest_exit_risk_score": "22.0",
                "backtest_estimated_total_profit_gbp": "250.0",
                "backtest_estimated_monthly_profit_gbp": "35.7",
                "backtest_capital_lockup_days": "18",
                "backtest_sellable_ceiling_zone": "normal",
                "backtest_amazon_risk_level": "low",
                "backtest_compression_risk_level": "medium",
                "backtest_recommendation": "Normal fit",
                "backtest_manual_review_reason": "",
            }
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)
    display_df = build_recommendations_display_df(datasets)
    row = display_df.iloc[0]
    assert row["backtest_recommendation"] == "Normal fit"
    assert row["backtest_estimated_monthly_profit_gbp"] == "35.7"
    assert row["backtest_market_viability_score"] == "81.2"

    card_html = _render_recommendation_cards(display_df)
    assert "Backtest:" in card_html
    assert "Normal fit" in card_html
    assert "Monthly:" in card_html
    assert "Viability:" in card_html


def test_ui_decision_submission_writes_to_decision_inbox(tmp_path: Path) -> None:
    out_row = submit_decision_event(
        root=tmp_path,
        seller_sku="SKU-2",
        asin="ASIN-2",
        action="snooze",
        snooze_until_utc="2026-04-10T00:00:00Z",
        decision_note="wait for supplier confirmation",
        actor="tester",
        cost_mode="test",
        source_reference="o_ui_test",
    )

    inbox_path = tmp_path / get_o_output_contract("restock_decision_events").rel_path
    inbox_df = pd.read_csv(inbox_path, dtype=str).fillna("")
    assert len(inbox_df) == 1
    row = inbox_df.iloc[0]
    assert row["event_id"].startswith("o-ui-decision-")
    assert row["seller_sku"] == "SKU-2"
    assert row["action"] == "snooze"
    assert row["snooze_until_utc"] == "2026-04-10T00:00:00Z"
    assert row["actor"] == "tester"
    assert row["source_reference"] == "o_ui_test"
    assert out_row["event_id"] == row["event_id"]


def test_ui_receiving_submission_writes_to_receiving_inbox(tmp_path: Path) -> None:
    out_row = submit_receiving_event(
        root=tmp_path,
        po_id="PO-1",
        po_line_id="PO-1-L001",
        seller_sku="SKU-REC",
        received_qty="3",
        warehouse_ref="WH-A",
        note="partial receive",
        actor="tester",
    )

    inbox_path = tmp_path / get_o_output_contract("receiving_events_inbox").rel_path
    inbox_df = pd.read_csv(inbox_path, dtype=str).fillna("")
    assert len(inbox_df) == 1
    row = inbox_df.iloc[0]
    assert row["event_id"].startswith("o-ui-receive-")
    assert row["po_id"] == "PO-1"
    assert row["po_line_id"] == "PO-1-L001"
    assert row["seller_sku"] == "SKU-REC"
    assert row["received_qty"] == "3"
    assert row["actor"] == "tester"
    assert out_row["event_id"] == row["event_id"]


def test_ui_handoff_submission_writes_to_handoff_inbox(tmp_path: Path) -> None:
    out_row = submit_send_handoff_event(
        root=tmp_path,
        po_id="PO-2",
        po_line_id="PO-2-L001",
        seller_sku="SKU-HND",
        handoff_qty="2",
        shipment_ref="SHIP-1",
        handoff_status="handoff_closed",
        note="close line",
        actor="tester",
    )

    inbox_path = tmp_path / get_o_output_contract("send_to_amazon_handoff_events").rel_path
    inbox_df = pd.read_csv(inbox_path, dtype=str).fillna("")
    assert len(inbox_df) == 1
    row = inbox_df.iloc[0]
    assert row["event_id"].startswith("o-ui-handoff-")
    assert row["po_id"] == "PO-2"
    assert row["po_line_id"] == "PO-2-L001"
    assert row["seller_sku"] == "SKU-HND"
    assert row["handoff_qty"] == "2"
    assert row["shipment_ref"] == "SHIP-1"
    assert row["handoff_status"] == "handoff_closed"
    assert out_row["event_id"] == row["event_id"]


def test_ui_submission_targets_are_inbox_only_and_no_direct_apply_imports(tmp_path: Path) -> None:
    targets = get_submission_targets(root=tmp_path)
    assert set(targets.keys()) == {"decision_events", "receiving_events", "send_handoff_events", "feeder_review_events"}
    for target in targets.values():
        assert "\\inbox\\" in str(target)

    module_text = (ROOT / "scripts" / "flows" / "O" / "O400_operator_ui.py").read_text(encoding="utf-8")
    assert "O010_apply_restock_decisions" not in module_text
    assert "O210_apply_receiving_events" not in module_text
    assert "O310_close_send_to_amazon_handoff" not in module_text


def test_feeder_review_asin_padding_and_url_builder() -> None:
    assert _pad_asin_to_10("B006SYGN9O") == "B006SYGN9O"
    assert _pad_asin_to_10("6SYGN9O") == "0006SYGN9O"
    assert _amazon_dp_url("6SYGN9O") == "https://www.amazon.co.uk/dp/0006SYGN9O"


def test_feeder_review_window_shows_only_first_10_undecided_rows(tmp_path: Path) -> None:
    report_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    for idx in range(12):
        rows.append(
            {
                "observed_utc": "2026-04-22T14:43:41Z",
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": str(100 - idx),
                "candidate_id": f"cand-{idx}",
                "supplier_sku": f"SKU-{idx}",
                "asin": f"B0000000{idx:02d}"[-10:],
                "title": f"Product {idx}",
                "brand": "Brand",
                "main_rank": str(idx + 1),
                "screening_status_reason": "PASS",
                "backtest_decision_state": "pass",
                "expected_units_next_30d": "50",
                "sales_lower_30d": "30",
                "sales_upper_30d": "70",
                "expected_profit_next_30d_gbp": "25",
                "estimated_monthly_profit_gbp": "25",
                "profit_per_unit_30d_gbp": "2.5",
                "conservative_starter_qty": "8",
                "pass_reason_summary": "profit_floor_met",
                "commercial_note": "Looks fine",
            }
        )
    pd.DataFrame(rows).to_csv(report_path, index=False)
    _write_f_contract_rows(
        tmp_path,
        "feeder_review_events",
        [
            {
                "event_utc": "2026-04-22T15:00:00Z",
                "event_id": "evt-1",
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-0",
                "supplier_sku": "SKU-0",
                "asin_raw": "B000000000",
                "asin_padded": "B000000000",
                "amazon_dp_url": "https://www.amazon.co.uk/dp/B000000000",
                "review_decision": "pass",
                "review_note": "approved",
                "actor": "tester",
                "source_reference": "test",
                "title": "Product 0",
                "brand": "Brand",
                "main_rank": "1",
                "review_priority_score": "100",
            }
        ],
    )

    window_df, meta = build_feeder_review_window_df("passes", root=tmp_path)

    assert len(window_df.index) == 10
    assert "cand-0" not in set(window_df["candidate_id"])
    assert window_df.iloc[0]["candidate_id"] == "cand-1"
    assert meta["undecided_rows"] == 11
    assert meta["visible_rows"] == 10


def test_feeder_review_submission_writes_f_inbox_events(tmp_path: Path) -> None:
    out = submit_feeder_review_batch(
        root=tmp_path,
        reviewed_rows=[
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-10",
                "supplier_sku": "SKU-10",
                "asin": "6SYGN9O",
                "title": "Example title",
                "brand": "Brand",
                "main_rank": "5000",
                "review_priority_score": "123.4",
                "review_decision": "pass",
                "review_reason_code": "wrong product",
                "review_note": "Good enough for a first test",
                "country_of_origin": "gb",
                "product_tax_code": "A_GEN_STANDARD",
                "currency_code": "gbp",
                "price_includes_tax": "1",
                "starting_price_gbp": "12.34",
            }
        ],
        actor="tester",
        source_reference="o_ui_feeder_review:test",
    )

    inbox_path = tmp_path / get_f_output_contract("feeder_review_events").rel_path
    inbox_df = pd.read_csv(inbox_path, dtype=str).fillna("")

    assert out["events_applied"] == 1
    assert len(inbox_df.index) == 1
    row = inbox_df.iloc[0]
    assert row["event_id"].startswith("o-ui-f-review-")
    assert row["candidate_id"] == "cand-10"
    assert row["review_decision"] == "pass"
    assert row["asin_padded"] == "0006SYGN9O"
    assert row["amazon_dp_url"] == "https://www.amazon.co.uk/dp/0006SYGN9O"
    assert row["review_reason_code"] == "wrong_product"
    assert row["review_reason_label"] == "Wrong product"
    assert row["review_note"] == "Good enough for a first test"
    assert row["source_reference"] == "o_ui_feeder_review:test"
    assert row["country_of_origin"] == "GB"
    assert row["product_tax_code"] == "A_GEN_STANDARD"
    assert row["currency_code"] == "GBP"
    assert row["price_includes_tax"] == "1"
    assert row["starting_price_gbp"] == "12.34"


def test_feeder_review_pass_without_country_of_origin_routes_to_profile_review(tmp_path: Path) -> None:
    out = submit_feeder_review_batch(
        root=tmp_path,
        reviewed_rows=[
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-10",
                "supplier_sku": "SKU-10",
                "asin": "B000000001",
                "review_decision": "pass",
                "review_note": "Good enough for a first test",
                "starting_price_gbp": "12.34",
            }
        ],
        actor="tester",
        source_reference="o_ui_feeder_review:test",
    )

    inbox_path = tmp_path / get_f_output_contract("feeder_review_events").rel_path
    inbox_df = pd.read_csv(inbox_path, dtype=str).fillna("")

    assert out["events_applied"] == 1
    assert out["skipped_rows"] == []
    assert len(inbox_df.index) == 1
    assert inbox_df.iloc[0]["review_decision"] == "pass"
    pending = build_product_listing_profile_review_df(root=tmp_path)
    assert len(pending.index) == 1
    assert pending.iloc[0]["candidate_id"] == "cand-10"


def test_product_listing_profile_requires_profile_fields(tmp_path: Path) -> None:
    out = submit_feeder_review_batch(
        root=tmp_path,
        reviewed_rows=[
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-11",
                "supplier_sku": "SKU-11",
                "asin": "B000000011",
                "review_decision": "pass",
                "review_note": "Good enough for a first test",
            }
        ],
        actor="tester",
        source_reference="o_ui_feeder_review:test",
    )
    assert out["events_applied"] == 1

    result = submit_amazon_listing_profile_batch(
        root=tmp_path,
        profile_rows=[
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-11",
                "supplier_sku": "SKU-11",
                "asin": "B000000011",
                "country_of_origin": "GB",
                "purchase_pack_size": "1",
                "sold_pack_size": "1",
                "supplier_case_qty": "1",
                "supplier_case_multiple": "0",
                "valid_order_step": "1",
                "moq": "1",
                "target_margin": "30",
                "vat_confirmed_flag": "0",
                "vat_source_value": "",
                "product_tax_code": "A_GEN_STANDARD",
                "currency_code": "GBP",
                "price_includes_tax": "1",
                "starting_price_gbp": "",
            }
        ],
        actor="tester",
        source_reference="o_ui_profile_review:test",
    )

    assert result["events_applied"] == 0
    assert result["skipped_rows"] == ["cand-11:missing_listing_profile:vat_source_value,vat_confirmed_flag,starting_price_gbp"]


def test_product_listing_profile_completion_writes_profile_event(tmp_path: Path) -> None:
    submit_feeder_review_batch(
        root=tmp_path,
        reviewed_rows=[
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-12",
                "supplier_sku": "SKU-12",
                "asin": "B000000012",
                "title": "Profile product",
                "review_decision": "pass",
            }
        ],
        actor="tester",
        source_reference="o_ui_feeder_review:test",
    )

    result = submit_amazon_listing_profile_batch(
        root=tmp_path,
        profile_rows=[
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-12",
                "supplier_sku": "SKU-12",
                "asin": "B000000012",
                "country_of_origin": "gb",
                "purchase_pack_size": "6",
                "sold_pack_size": "2",
                "supplier_case_qty": "12",
                "supplier_case_multiple": "1",
                "valid_order_step": "12",
                "moq": "12",
                "target_margin": "30%",
                "vat_source_value": "20%",
                "vat_confirmed_flag": "1",
                "product_tax_code": "A_GEN_STANDARD",
                "currency_code": "gbp",
                "price_includes_tax": "1",
                "starting_price_gbp": "19.99",
                "starting_quantity": "0",
                "condition_type": "new_new",
            }
        ],
        actor="tester",
        source_reference="o_ui_profile_review:test",
    )

    profile_path = tmp_path / get_f_output_contract("amazon_listing_profile_events").rel_path
    profile_df = pd.read_csv(profile_path, dtype=str).fillna("")

    assert result["events_applied"] == 1
    row = profile_df.iloc[0]
    assert row["profile_status"] == "complete"
    assert row["country_of_origin"] == "GB"
    assert row["purchase_pack_size"] == "6"
    assert row["sold_pack_size"] == "2"
    assert row["supplier_case_qty"] == "12"
    assert row["supplier_case_multiple"] == "1"
    assert row["valid_order_step"] == "12"
    assert row["moq"] == "12"
    assert row["target_margin"] == "30"
    assert row["vat_source_value"] == "20"
    assert row["vat_confirmed_flag"] == "1"
    assert row["currency_code"] == "GBP"
    assert row["starting_price_gbp"] == "19.99"
    pending = build_product_listing_profile_review_df(root=tmp_path)
    assert pending.empty


def test_brand_approval_queue_decision_writes_event(tmp_path: Path) -> None:
    _write_f_contract_rows(
        tmp_path,
        "brand_approval_queue_live",
        [
            {
                "observed_utc": "2026-05-01T13:00:00Z",
                "queue_id": "brand_approval_1",
                "draft_id": "draft-1",
                "candidate_id": "cand-approval",
                "expected_seller_sku": "NP-SUP-APPROVAL",
                "asin": "B000000099",
                "marketplace_id": "A1F83G8C2ARO7P",
                "brand": "Brand A",
                "amazon_title": "Approval product",
                "approval_status": "approval_required",
                "approval_required_flag": "1",
                "reason_code": "APPROVAL_REQUIRED",
                "reason_message": "You need approval to list this brand.",
                "approval_link": "https://sellercentral.amazon.co.uk/approval",
                "invoice_unit_cost_gbp": "7.00",
                "recheck_trigger": "operator_decision_required",
                "updated_at_utc": "2026-05-01T13:00:00Z",
                "source_reference": "test",
            }
        ],
    )

    display = build_brand_approval_queue_display_df(root=tmp_path)
    assert len(display.index) == 1
    assert display.iloc[0]["brand"] == "Brand A"

    result = submit_brand_approval_decision_batch(
        root=tmp_path,
        actor="tester",
        decision_rows=[
            {
                "queue_id": "brand_approval_1",
                "draft_id": "draft-1",
                "candidate_id": "cand-approval",
                "expected_seller_sku": "NP-SUP-APPROVAL",
                "asin": "B000000099",
                "marketplace_id": "A1F83G8C2ARO7P",
                "brand": "Brand A",
                "operator_decision": "invoice_planned",
                "decision_reason": "10 units is acceptable",
                "invoice_required_quantity": "10",
                "invoice_unit_cost_gbp": "7.00",
            }
        ],
    )

    assert result["events_applied"] == 1
    decision_path = tmp_path / get_f_output_contract("brand_approval_decision_events").rel_path
    decisions = pd.read_csv(decision_path, dtype=str).fillna("")
    row = decisions.iloc[0]
    assert row["operator_decision"] == "invoice_planned"
    assert row["invoice_required_quantity"] == "10"
    assert row["invoice_total_risk_gbp"] == "70.00"


def test_feeder_review_source_loader_normalizes_pass_and_near_miss_reports(tmp_path: Path) -> None:
    pass_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
    pass_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "candidate_id": "cand-pass",
                "asin": "6SYGN9O",
                "why_data_summary": "units_likely_30d=40 | profit_likely_gbp=25",
                "watch_data_summary": "decision_confidence=medium",
                "pass_reason_summary": "screening_pass|profit_floor_met",
                "commercial_note": "Avoid|qualification_factor_reduced|stability_state_drifting_up|decision_confidence_medium|PASS",
                "profit_on_cost_pct": "42.25",
                "estimated_monthly_profit_gbp": "25",
                "profit_per_unit_30d_gbp": "2.50",
                "original_point_score": "4.0",
                "original_test_result": "PASS",
                "original_test_status_reason": "PASS_SCORE",
                "original_test_gate": "3.5",
            }
        ]
    ).to_csv(pass_path, index=False)
    near_miss_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_near_miss_review_latest.csv"
    pd.DataFrame(
        [
            {
                "candidate_id": "cand-near",
                "asin": "B006SYGN9O",
                "why_data_summary": "fail_code=ROIFAIL | profit_likely_gbp=12",
                "watch_data_summary": "recovery_hint=economics_below_pass_floor_but_close_enough_for_manual_review",
                "estimated_monthly_profit_gbp": "12",
                "profit_per_unit_30d_gbp": "1.20",
                "screening_fail_code": "ROIFAIL",
                "recovery_hint": "close enough",
                "original_point_score": "2.5",
                "original_test_result": "FAIL",
                "original_test_status_reason": "PRICE_TOO_HIGH",
                "original_test_gate": "3.5",
            },
            {
                "candidate_id": "cand-near-empty",
                "asin": "B000000001",
                "screening_fail_code": "EVIDENCE_MISSING",
                "recovery_hint": "",
            }
        ]
    ).to_csv(near_miss_path, index=False)

    pass_df = load_feeder_review_source_df("passes", root=tmp_path)
    near_df = load_feeder_review_source_df("near_misses", root=tmp_path)
    near_by_candidate = {row["candidate_id"]: row for row in near_df.to_dict("records")}

    assert pass_df.iloc[0]["asin_padded"] == "0006SYGN9O"
    assert pass_df.iloc[0]["why_label"] == "Why it passed"
    assert pass_df.iloc[0]["why_text"] == "units_likely_30d=40 | profit_likely_gbp=25"
    assert pass_df.iloc[0]["helper_label"] == "What to watch"
    assert pass_df.iloc[0]["helper_text"] == "decision_confidence=medium"
    assert pass_df.iloc[0]["original_point_score"] == "4.0"
    assert pass_df.iloc[0]["original_test_result"] == "PASS"
    assert pass_df.iloc[0]["original_test_status_reason"] == "PASS_SCORE"
    assert pass_df.iloc[0]["original_test_gate"] == "3.5"
    assert pass_df.iloc[0]["review_roi_pct"] == "42.25"
    assert pass_df.iloc[0]["review_roi_text"] == "42%"
    assert pass_df.iloc[0]["review_profit_signal_text"] == "unit_profit=GBP 2.5 | 30d_profit=GBP 25"

    near = near_by_candidate["cand-near"]
    assert near["why_label"] == "Why it nearly failed"
    assert near["why_text"] == "fail_code=ROIFAIL | profit_likely_gbp=12"
    assert near["helper_text"] == "recovery_hint=economics_below_pass_floor_but_close_enough_for_manual_review"
    assert near["original_point_score"] == "2.5"
    assert near["original_test_result"] == "FAIL"
    assert near["original_test_status_reason"] == "PRICE_TOO_HIGH"
    assert near["original_test_gate"] == "3.5"
    assert near["review_roi_pct"] == ""
    assert near["review_roi_text"] == "-"
    assert near["review_profit_signal_text"] == "unit_profit=GBP 1.2 | 30d_profit=GBP 12"

    near_empty = near_by_candidate["cand-near-empty"]
    assert near_empty["helper_text"] == ""
    assert near_empty["original_point_score"] == ""
    assert near_empty["original_test_result"] == ""
    assert near_empty["original_test_status_reason"] == ""
    assert near_empty["original_test_gate"] == ""


def test_feeder_review_source_loader_merges_roi_from_ai_queue_for_human_review(tmp_path: Path) -> None:
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "sample_supplier"
        / "run_001"
    )
    handoff_dir.mkdir(parents=True, exist_ok=True)
    pass_path = handoff_dir / "f_live_price_file_pass_review_latest.csv"
    queue_path = handoff_dir / "ai_review_queue.csv"
    pd.DataFrame(
        [
            {
                "supplier_id": "sample_supplier",
                "supplier_name": "Sample Supplier",
                "run_id": "run_001",
            }
        ]
    ).to_csv(handoff_dir / "candidate_manifest.csv", index=False)
    pd.DataFrame(
        [
            {
                "supplier_id": "sample_supplier",
                "supplier_name": "Sample Supplier",
                "run_id": "run_001",
                "ai_gate_status": "passed",
                "operator_ready_flag": "1",
                "pass_review_path": str(pass_path),
                "ai_review_queue_path": str(queue_path),
            }
        ]
    ).to_csv(handoff_dir / "manifest.csv", index=False)
    pd.DataFrame(
        [
            {
                "candidate_id": "cand-roi",
                "f032_decision_id": "f032-roi",
                "supplier_sku": "SKU-ROI",
                "asin": "B000ROI001",
                "title": "ROI visible product",
                "estimated_monthly_profit_gbp": "30",
                "profit_per_unit_30d_gbp": "3",
            }
        ]
    ).to_csv(pass_path, index=False)
    pd.DataFrame(
        [
            {
                "candidate_id": "cand-roi",
                "f032_decision_id": "f032-roi",
                "supplier_sku": "SKU-ROI",
                "asin": "B000ROI001",
                "profit_on_cost_pct": "145.333333",
                "supplier_unit_cost_gbp": "2.50",
                "amazon_sell_price_gbp": "9.99",
            }
        ]
    ).to_csv(queue_path, index=False)

    review_df = load_feeder_review_source_df(
        "passes",
        root=tmp_path,
        review_pack_snapshot="handoff|sample_supplier|run_001",
    )

    row = review_df.iloc[0]
    assert row["review_roi_pct"] == "145.333333"
    assert row["review_roi_text"] == "145%"
    assert row["supplier_unit_cost_gbp"] == "2.50"
    assert row["amazon_sell_price_gbp"] == "9.99"


def test_feeder_review_pass_row_adds_ai_compare_note_to_what_to_watch(tmp_path: Path) -> None:
    pass_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
    pass_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "candidate_id": "cand-ai-pass",
                "asin": "B000000010",
                "title": "Minecraft Plastic Replica Enchanted Sword 51 cm",
                "watch_data_summary": "decision_confidence=medium",
                "codex_ai_action": "allow_if_other_checks_pass",
                "codex_ai_confidence": "high",
                "codex_ai_reason": "Same Minecraft enchanted toy sword; 51cm vs 50cm is normal rounding.",
            }
        ]
    ).to_csv(pass_path, index=False)

    pass_df = load_feeder_review_source_df("passes", root=tmp_path)

    row = pass_df.iloc[0]
    assert row["helper_label"] == "What to watch"
    assert row["helper_text"] == (
        "decision_confidence=medium | ai_match_confidence=high | "
        "ai_compare=Same Minecraft enchanted toy sword; 51cm vs 50cm is normal rounding."
    )
    assert row["ai_compare_watch_note"] == (
        "ai_match_confidence=high | "
        "ai_compare=Same Minecraft enchanted toy sword; 51cm vs 50cm is normal rounding."
    )


def test_feeder_review_manual_review_lane_splits_near_miss_pack(tmp_path: Path) -> None:
    report_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_near_miss_review_latest.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "batch-1",
                "review_priority_score": "90",
                "candidate_id": "manual-seller-history",
                "supplier_sku": "SKU-MAN-1",
                "asin": "B000000001",
                "title": "NO with enough sellers",
                "near_miss_type": "seller_history_manual_review",
                "seller_history_recommended_action": "manual_review",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "batch-1",
                "review_priority_score": "80",
                "candidate_id": "manual-demand",
                "supplier_sku": "SKU-MAN-2",
                "asin": "B000000002",
                "title": "Demand warning",
                "near_miss_type": "demand_range_warning",
                "demand_recommended_action": "manual_review",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "batch-1",
                "review_priority_score": "70",
                "candidate_id": "standard-near",
                "supplier_sku": "SKU-NEAR",
                "asin": "B000000003",
                "title": "Standard near miss",
                "near_miss_type": "commercial_near_miss",
                "seller_history_recommended_action": "allow_if_other_checks_pass",
            },
        ]
    ).to_csv(report_path, index=False)

    all_df, all_meta = build_feeder_review_window_df("near_misses", root=tmp_path, page_size=10)
    manual_df, manual_meta = build_feeder_review_window_df(
        "near_misses",
        root=tmp_path,
        lane_filter="manual_review",
        page_size=10,
    )
    near_df, near_meta = build_feeder_review_window_df(
        "near_misses",
        root=tmp_path,
        lane_filter="near_misses",
        page_size=10,
    )

    assert all_meta["available_rows"] == 3
    assert set(all_df["candidate_id"]) == {"manual-seller-history", "manual-demand", "standard-near"}
    assert manual_meta["available_rows"] == 2
    assert set(manual_df["candidate_id"]) == {"manual-seller-history", "manual-demand"}
    assert near_meta["available_rows"] == 1
    assert list(near_df["candidate_id"]) == ["standard-near"]
    assert set(manual_df["review_pack_type"]) == {"near_misses"}


def test_feeder_review_manual_row_prefers_ai_check_note(tmp_path: Path) -> None:
    report_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_near_miss_review_latest.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "bliss_distribution",
                "active_run_id": "run-1",
                "review_batch_id": "batch-1",
                "review_priority_score": "90",
                "candidate_id": "kuriboh-sleeves",
                "supplier_sku": "KONKKS",
                "asin": "B09HKZWBDN",
                "title": "Yu-Gi-Oh! Kuriboh Kollection Card Sleeves",
                "near_miss_type": "f032_manual_review",
                "watch_data_summary": "old scanner watch note",
                "f032_action": "manual_review",
                "codex_ai_action": "manual_review",
                "codex_ai_decision_bucket": "pack_size_or_quantity_needs_user_guidance",
                "codex_ai_reason": "Supplier title says Sleeves 50 Pack, but Amazon title does not confirm the count.",
                "codex_ai_evidence": "supplier_quantities=50|amazon_quantities=",
            }
        ]
    ).to_csv(report_path, index=False)

    manual_df, meta = build_feeder_review_window_df(
        "near_misses",
        root=tmp_path,
        lane_filter="manual_review",
        page_size=10,
    )

    assert meta["available_rows"] == 1
    row = manual_df.iloc[0]
    assert row["helper_label"] == "What to watch"
    assert row["helper_text"] == (
        "old scanner watch note | ai_compare=confirm the Amazon listing is for 50 units per pack."
    )
    assert row["f032_operator_check_note"] == "AI check: confirm the Amazon listing is for 50 units per pack."
    assert row["ai_compare_watch_note"] == "ai_compare=confirm the Amazon listing is for 50 units per pack."


def test_feeder_review_can_load_timestamped_pack_without_latest(tmp_path: Path) -> None:
    reports_dir = tmp_path / "out" / "analysis_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    profiles_dir = tmp_path / "out" / "systems" / "O" / "live"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "supplier_code": "stocklist_supplier",
                "supplier_name": "Entertainment Trading",
            }
        ]
    ).to_csv(profiles_dir / "supplier_profiles.csv", index=False)
    pd.DataFrame(
        [
            {
                "observed_utc": "2026-04-23T15:13:40Z",
                "metric": "active_supplier_id",
                "value": "stocklist_supplier",
            },
            {
                "observed_utc": "2026-04-23T15:13:40Z",
                "metric": "active_run_id",
                "value": "entertainment_trading_20260423",
            },
            {
                "observed_utc": "2026-04-23T15:13:40Z",
                "metric": "source_seen_at_utc",
                "value": "2026-04-21T09:30:00Z",
            },
            {"observed_utc": "2026-04-23T15:13:40Z", "metric": "pass_review_rows", "value": "47"},
            {"observed_utc": "2026-04-23T15:13:40Z", "metric": "near_miss_review_rows", "value": "3276"},
        ]
    ).to_csv(reports_dir / "f_live_price_file_review_summary_20260423T151340Z.csv", index=False)
    pd.DataFrame(
        [
            {
                "observed_utc": "2026-04-29T07:22:19Z",
                "metric": "active_supplier_id",
                "value": "stocklist_supplier",
            },
            {
                "observed_utc": "2026-04-29T07:22:19Z",
                "metric": "active_run_id",
                "value": "stocklist_20260429",
            },
            {
                "observed_utc": "2026-04-29T07:22:19Z",
                "metric": "source_seen_at_utc",
                "value": "2026-04-29T07:00:00Z",
            },
            {"observed_utc": "2026-04-29T07:22:19Z", "metric": "pass_review_rows", "value": "26"},
            {"observed_utc": "2026-04-29T07:22:19Z", "metric": "near_miss_review_rows", "value": "1568"},
        ]
    ).to_csv(reports_dir / "f_live_price_file_review_summary_latest.csv", index=False)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "entertainment_trading_20260423",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "100",
                "candidate_id": "game-cand",
                "supplier_sku": "SKU-GAME",
                "asin": "B000000123",
                "title": "Nintendo Switch game",
            }
        ]
    ).to_csv(reports_dir / "f_live_price_file_pass_review_20260423T151340Z.csv", index=False)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "stocklist_20260429",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "50",
                "candidate_id": "fragrance-cand",
                "supplier_sku": "SKU-FRAG",
                "asin": "B000000456",
                "title": "BOSS fragrance",
            }
        ]
    ).to_csv(reports_dir / "f_live_price_file_pass_review_latest.csv", index=False)

    default_options = list_feeder_review_pack_options(root=tmp_path)
    options = list_feeder_review_pack_options(root=tmp_path, include_history=True)
    snapshot_df = load_feeder_review_source_df(
        "passes",
        root=tmp_path,
        review_pack_snapshot="20260423T151340Z",
    )
    latest_df = load_feeder_review_source_df("passes", root=tmp_path)

    assert any(option["id"] == "20260423T151340Z" for option in default_options)
    assert any(option["id"] == "20260423T151340Z" for option in options)
    assert any(option["label"] == "Entertainment Trading - 21 Apr 09:30" for option in options)
    assert [option["id"] for option in default_options] == ["20260423T151340Z", "latest"]
    assert snapshot_df.iloc[0]["candidate_id"] == "game-cand"
    assert latest_df.iloc[0]["candidate_id"] == "fragrance-cand"


def test_feeder_review_can_load_completed_handoff_pack(tmp_path: Path) -> None:
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "entertainment_trading"
        / "fpm_entertainment_trading_test"
    )
    handoff_dir.mkdir(parents=True, exist_ok=True)
    pass_path = handoff_dir / "f_live_price_file_pass_review_20260501T090600Z.csv"
    near_path = handoff_dir / "f_live_price_file_near_miss_review_20260501T090600Z.csv"
    summary_path = handoff_dir / "f_live_price_file_review_summary_20260501T090600Z.csv"
    pd.DataFrame(
        [
            {
                "active_supplier_id": "entertainment_trading",
                "active_run_id": "fpm_entertainment_trading_test",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "60",
                "candidate_id": "handoff-pass",
                "supplier_sku": "ET-1",
                "asin": "B000000001",
                "title": "Completed handoff product",
                "f032_decision_id": "f032_handoff_pass",
                "f032_action": "allow_if_other_checks_pass",
            }
        ]
    ).to_csv(pass_path, index=False)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "entertainment_trading",
                "active_run_id": "fpm_entertainment_trading_test",
                "review_batch_id": "near_miss_batch_001",
                "review_priority_score": "40",
                "candidate_id": "handoff-near",
                "supplier_sku": "ET-2",
                "asin": "B000000002",
                "title": "Completed handoff near miss",
                "near_miss_type": "commercial_near_miss",
                "f032_decision_id": "f032_handoff_near",
                "f032_action": "allow_if_other_checks_pass",
            }
        ]
    ).to_csv(near_path, index=False)
    pd.DataFrame(
        [
            {"observed_utc": "2026-05-01T09:06:00Z", "metric": "active_supplier_id", "value": "entertainment_trading"},
            {
                "observed_utc": "2026-05-01T09:06:00Z",
                "metric": "active_run_id",
                "value": "fpm_entertainment_trading_test",
            },
            {"observed_utc": "2026-05-01T09:06:00Z", "metric": "source_seen_at_utc", "value": "2026-04-30T14:13:50Z"},
            {"observed_utc": "2026-05-01T09:06:00Z", "metric": "pass_review_rows", "value": "1"},
            {"observed_utc": "2026-05-01T09:06:00Z", "metric": "near_miss_review_rows", "value": "1"},
        ]
    ).to_csv(summary_path, index=False)
    pd.DataFrame(
        [
            {
                "built_at_utc": "2026-05-01T09:06:00Z",
                "supplier_id": "entertainment_trading",
                "supplier_name": "Entertainment Trading",
                "run_id": "fpm_entertainment_trading_test",
                "review_snapshot_id": "20260501T090600Z",
                "source_file_path": "Stocklist.xlsx",
                "source_seen_at_utc": "2026-04-30T14:13:50Z",
                "completed_at_utc": "2026-05-01T09:05:00Z",
                "pass_review_rows": "1",
                "near_miss_review_rows": "1",
                "hard_reject_rows": "0",
                "pass_review_path": str(pass_path),
                "near_miss_review_path": str(near_path),
                "summary_path": str(summary_path),
                "handoff_dir": str(handoff_dir),
                "published_to_operator_latest_flag": "0",
                "ai_gate_status": "passed",
                "ai_gate_observed_utc": "2026-05-01T09:06:00Z",
                "ai_gate_version": "F032_review_intelligence_v1",
                "ai_gate_health_path": str(handoff_dir / "ai_review_intelligence_gate_health.csv"),
                "ai_gate_decision_path": str(handoff_dir / "ai_review_intelligence_decisions.csv"),
                "ai_gate_checklist_path": str(handoff_dir / "ai_review_intelligence_checklist.csv"),
                "ai_gate_rule_suggestion_path": str(handoff_dir / "ai_rule_tightening_suggestions.csv"),
                "ai_gate_rescan_queue_path": str(handoff_dir / "ai_rescan_queue.csv"),
                "ai_gate_removed_audit_path": str(handoff_dir / "ai_removed_from_clean_pass_audit.csv"),
                "ai_gate_manual_review_path": str(handoff_dir / "ai_manual_review.csv"),
                "raw_candidate_manifest_path": str(handoff_dir / "candidate_manifest.csv"),
                "raw_pass_review_path": str(handoff_dir / "raw_pass.csv"),
                "raw_near_miss_review_path": str(handoff_dir / "raw_near.csv"),
                "ai_gate_fail_rows": "0",
                "ai_gate_warn_rows": "0",
                "ai_gate_clear_rows": "1",
                "ai_gate_manual_rows": "0",
                "ai_gate_rescan_rows": "0",
                "ai_gate_removed_rows": "0",
                "operator_ready_flag": "1",
                "block_reason": "",
                "notes": "test",
            }
        ],
        columns=REVIEW_HANDOFF_MANIFEST_COLUMNS,
    ).to_csv(handoff_dir / "manifest.csv", index=False)

    snapshot_id = "handoff|entertainment_trading|fpm_entertainment_trading_test"
    options = list_feeder_review_pack_options(root=tmp_path)
    summary = load_feeder_review_summary(root=tmp_path, review_pack_snapshot=snapshot_id)
    pass_df = load_feeder_review_source_df("passes", root=tmp_path, review_pack_snapshot=snapshot_id)
    near_df = load_feeder_review_source_df("near_misses", root=tmp_path, review_pack_snapshot=snapshot_id)

    assert any(option["id"] == snapshot_id for option in options)
    assert any(option["label"] == "Entertainment Trading - completed 01 May 09:05" for option in options)
    assert summary["active_supplier_id"] == "entertainment_trading"
    assert summary["active_supplier_label"] == "Entertainment Trading"
    assert summary["active_run_id"] == "fpm_entertainment_trading_test"
    assert summary["completed_at_utc"] == "2026-05-01T09:05:00Z"
    assert pass_df.iloc[0]["candidate_id"] == "handoff-pass"
    assert near_df.iloc[0]["candidate_id"] == "handoff-near"


def test_feeder_review_pack_options_are_lane_todo_lists(tmp_path: Path) -> None:
    handoff_root = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "review_handoffs"

    def write_handoff(
        *,
        supplier_id: str,
        supplier_name: str,
        run_id: str,
        pass_rows: list[dict[str, str]],
        near_rows: list[dict[str, str]],
        completed_at: str,
    ) -> str:
        handoff_dir = handoff_root / supplier_id / run_id
        handoff_dir.mkdir(parents=True, exist_ok=True)
        pass_path = handoff_dir / "ai_operator_pass_review.csv"
        near_path = handoff_dir / "ai_operator_near_miss_review.csv"
        pass_columns = [
            "active_supplier_id",
            "active_run_id",
            "review_batch_id",
            "candidate_id",
            "supplier_sku",
            "asin",
            "title",
            "f032_action",
        ]
        near_columns = [*pass_columns, "near_miss_type"]
        pd.DataFrame(pass_rows, columns=pass_columns).to_csv(pass_path, index=False)
        pd.DataFrame(near_rows, columns=near_columns).to_csv(near_path, index=False)
        pd.DataFrame(
            [
                {
                    "built_at_utc": completed_at,
                    "supplier_id": supplier_id,
                    "supplier_name": supplier_name,
                    "run_id": run_id,
                    "review_snapshot_id": completed_at.replace("-", "").replace(":", "").replace("Z", "Z"),
                    "completed_at_utc": completed_at,
                    "pass_review_rows": str(len(pass_rows)),
                    "near_miss_review_rows": str(len(near_rows)),
                    "pass_review_path": str(pass_path),
                    "near_miss_review_path": str(near_path),
                    "handoff_dir": str(handoff_dir),
                    "ai_gate_status": "passed",
                    "operator_ready_flag": "1",
                }
            ],
            columns=REVIEW_HANDOFF_MANIFEST_COLUMNS,
        ).to_csv(handoff_dir / "manifest.csv", index=False)
        return f"handoff|{supplier_id}|{run_id}"

    bliss_id = write_handoff(
        supplier_id="bliss_distribution",
        supplier_name="Bliss Distribution",
        run_id="run_bliss",
        completed_at="2026-05-17T09:16:00Z",
        pass_rows=[
            {
                "active_supplier_id": "bliss_distribution",
                "active_run_id": "run_bliss",
                "review_batch_id": "pass_batch",
                "candidate_id": f"bliss-{idx}",
                "supplier_sku": f"BLISS-{idx}",
                "asin": f"B000BLISS{idx}",
                "title": f"Bliss product {idx}",
                "f032_action": "allow_if_other_checks_pass",
            }
            for idx in range(3)
        ],
        near_rows=[],
    )
    entertainment_id = write_handoff(
        supplier_id="entertainment_trading",
        supplier_name="Entertainment Trading",
        run_id="run_entertainment",
        completed_at="2026-05-21T12:25:00Z",
        pass_rows=[],
        near_rows=[
            {
                "active_supplier_id": "entertainment_trading",
                "active_run_id": "run_entertainment",
                "review_batch_id": "manual_batch",
                "candidate_id": f"manual-{idx}",
                "supplier_sku": f"ET-{idx}",
                "asin": f"B000ETMAN{idx}",
                "title": f"Entertainment manual product {idx}",
                "f032_action": "manual_review",
                "near_miss_type": "manual_review",
            }
            for idx in range(4)
        ],
    )
    completed_id = write_handoff(
        supplier_id="completed_supplier",
        supplier_name="Completed Supplier",
        run_id="run_completed",
        completed_at="2026-05-18T08:00:00Z",
        pass_rows=[
            {
                "active_supplier_id": "completed_supplier",
                "active_run_id": "run_completed",
                "review_batch_id": "pass_batch",
                "candidate_id": "completed-pass",
                "supplier_sku": "DONE-1",
                "asin": "B000DONE01",
                "title": "Already reviewed product",
                "f032_action": "allow_if_other_checks_pass",
            }
        ],
        near_rows=[],
    )
    _write_f_contract_rows(
        tmp_path,
        "feeder_review_events",
        [
            {
                "event_utc": "2026-05-18T09:00:00Z",
                "event_id": "evt-completed",
                "active_supplier_id": "completed_supplier",
                "active_run_id": "run_completed",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch",
                "candidate_id": "completed-pass",
                "supplier_sku": "DONE-1",
                "asin_raw": "B000DONE01",
                "asin_padded": "B000DONE01",
                "amazon_dp_url": "",
                "review_decision": "pass",
                "review_note": "",
                "actor": "test",
                "source_reference": "test",
            }
        ],
    )

    pass_options = list_feeder_review_pack_options(
        root=tmp_path,
        pack_type="passes",
        lane_filter="passes",
        lane_label="Passes",
    )
    manual_options = list_feeder_review_pack_options(
        root=tmp_path,
        pack_type="near_misses",
        lane_filter="manual_review",
        lane_label="Manual review",
    )
    history_options = list_feeder_review_pack_options(
        root=tmp_path,
        include_history=True,
        pack_type="passes",
        lane_filter="passes",
        lane_label="Passes",
    )

    assert {option["id"] for option in pass_options} == {bliss_id}
    assert pass_options[0]["label"] == "Bliss Distribution - 3 passes to review"
    assert {option["id"] for option in manual_options} == {entertainment_id}
    assert manual_options[0]["label"] == "Entertainment Trading - 4 manual review"
    assert completed_id not in {option["id"] for option in pass_options}
    assert completed_id in {option["id"] for option in history_options}
    assert any(option["label"] == "Completed Supplier - 0 passes to review" for option in history_options)


def test_feeder_review_latest_is_blocked_while_ai_gate_is_pending(tmp_path: Path) -> None:
    reports_dir = tmp_path / "out" / "analysis_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "entertainment_trading",
                "active_run_id": "fpm_entertainment_trading_test",
                "candidate_id": "raw-latest-pass",
                "supplier_sku": "ET-RAW",
                "asin": "B000000999",
                "title": "Raw latest product",
            }
        ]
    ).to_csv(reports_dir / "f_live_price_file_pass_review_latest.csv", index=False)
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "entertainment_trading"
        / "fpm_entertainment_trading_test"
    )
    handoff_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "supplier_id": "entertainment_trading",
                "run_id": "fpm_entertainment_trading_test",
                "operator_ready_flag": "0",
            }
        ]
    ).to_csv(handoff_dir / "candidate_manifest.csv", index=False)

    latest_df = load_feeder_review_source_df("passes", root=tmp_path)

    assert latest_df.empty


def test_ai_product_check_gate_builds_statuses_from_queue_and_decisions(tmp_path: Path) -> None:
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "sample_supplier"
        / "run_001"
    )
    handoff_dir.mkdir(parents=True, exist_ok=True)
    queue_path = handoff_dir / "ai_review_queue.csv"
    decision_path = handoff_dir / "codex_ai_review_decisions.csv"
    manifest_path = handoff_dir / "manifest.csv"
    pd.DataFrame(
        [
            {"supplier_id": "sample_supplier", "supplier_name": "Sample Supplier", "run_id": "run_001"},
        ]
    ).to_csv(handoff_dir / "candidate_manifest.csv", index=False)
    pd.DataFrame(
        [
            {
                "supplier_id": "sample_supplier",
                "supplier_name": "Sample Supplier",
                "run_id": "run_001",
                "ai_gate_status": "passed",
                "operator_ready_flag": "1",
                "ai_review_queue_path": str(queue_path),
                "codex_ai_decision_path": str(decision_path),
            }
        ]
    ).to_csv(manifest_path, index=False)
    pd.DataFrame(
        [
            {
                "f032_decision_id": "pending",
                "supplier_sku": "SKU-P",
                "asin": "B000PENDING",
                "supplier_title": "Supplier pending product",
                "amazon_title": "Amazon pending product",
                "profit_on_cost_pct": "45.5",
            },
            {
                "f032_decision_id": "clear",
                "supplier_sku": "SKU-C",
                "asin": "B000CLEAR1",
                "supplier_title": "Supplier clear product",
                "amazon_title": "Amazon clear product",
                "amazon_product_description": "Each pack contains 50 card sleeves.",
                "profit_on_cost_pct": "22",
            },
            {
                "f032_decision_id": "manual",
                "supplier_sku": "SKU-M",
                "asin": "B000MANUAL",
                "supplier_title": "Supplier filter",
                "amazon_title": "Amazon machine",
                "profit_on_cost_pct": "240",
            },
            {
                "f032_decision_id": "rescan",
                "supplier_sku": "SKU-R",
                "asin": "B000RESCAN",
                "supplier_title": "Supplier rescan product",
                "amazon_title": "Amazon rescan product",
            },
            {
                "f032_decision_id": "missing-page-clear",
                "supplier_sku": "SKU-MPC",
                "asin": "B000PAGECLR",
                "supplier_title": "One Piece World Seeker PS4",
                "amazon_title": "One Piece World Seeker (PS4)",
                "f032_rule_action": "allow_if_other_checks_pass",
                "f032_rule_bucket": "ai_review_clear",
                "f032_rule_confidence": "medium",
                "f032_rule_reason": "F032 found no interpretive blocker in the available evidence.",
            },
            {
                "f032_decision_id": "missing-page-manual",
                "supplier_sku": "SKU-MPM",
                "asin": "B000PAGEMAN",
                "supplier_title": "Yu-Gi-Oh! Kuriboh Kollection Sleeves 50 Pack",
                "amazon_title": "Yu-Gi-Oh! Kuriboh Kollection Card Sleeves",
                "f032_rule_action": "manual_review",
                "f032_rule_bucket": "needs_user_guidance",
                "f032_rule_confidence": "medium",
                "f032_rule_fail_category": "pack_size_or_quantity",
                "f032_rule_reason": "pack_or_quantity_mismatch_needs_user_guidance",
            },
            {
                "f032_decision_id": "reject",
                "supplier_sku": "SKU-X",
                "asin": "B000REJECT",
                "supplier_title": "Supplier refill",
                "amazon_title": "Amazon device",
            },
        ]
    ).to_csv(queue_path, index=False)
    pd.DataFrame(
        [
            {
                "f032_decision_id": "clear",
                "codex_ai_action": "allow_if_other_checks_pass",
                "codex_ai_decision_bucket": "ai_review_clear",
                "codex_ai_confidence": "high",
                "codex_ai_reason": "Titles describe the same product.",
                "codex_ai_reviewed_utc": "2026-05-21T07:00:00Z",
            },
            {
                "f032_decision_id": "manual",
                "codex_ai_action": "manual_review",
                "codex_ai_decision_bucket": "possible_wrong_product",
                "codex_ai_confidence": "medium",
                "codex_ai_reason": "Same brand but supplier says filter and Amazon says device.",
                "codex_ai_reviewed_utc": "2026-05-21T07:01:00Z",
            },
            {
                "f032_decision_id": "rescan",
                "codex_ai_action": "rescan_needed",
                "codex_ai_decision_bucket": "missing_page_evidence",
                "codex_ai_confidence": "low",
                "codex_ai_reason": "Page evidence is incomplete.",
                "codex_ai_reviewed_utc": "2026-05-21T07:02:00Z",
            },
            {
                "f032_decision_id": "missing-page-clear",
                "codex_ai_action": "rescan_needed",
                "codex_ai_decision_bucket": "missing_page_evidence",
                "codex_ai_fail_category": "missing_page_evidence",
                "codex_ai_confidence": "low",
                "codex_ai_reason": "Page evidence is incomplete.",
                "codex_ai_reviewed_utc": "2026-05-21T07:02:30Z",
            },
            {
                "f032_decision_id": "missing-page-manual",
                "codex_ai_action": "rescan_needed",
                "codex_ai_decision_bucket": "missing_page_evidence",
                "codex_ai_fail_category": "missing_page_evidence",
                "codex_ai_confidence": "low",
                "codex_ai_reason": "Page evidence is incomplete.",
                "codex_ai_reviewed_utc": "2026-05-21T07:02:45Z",
            },
            {
                "f032_decision_id": "reject",
                "codex_ai_action": "remove_from_clean_pass",
                "codex_ai_decision_bucket": "clear_breach",
                "codex_ai_confidence": "high",
                "codex_ai_reason": "Supplier title is a refill and Amazon title is a device.",
                "codex_ai_reviewed_utc": "2026-05-21T07:03:00Z",
            },
        ]
    ).to_csv(decision_path, index=False)

    gate_df = build_ai_product_check_gate_df(root=tmp_path)
    by_id = gate_df.set_index("f032_decision_id").to_dict("index")

    assert by_id["pending"]["queue_state"] == "pending_ai_check"
    assert by_id["clear"]["queue_state"] == "ai_cleared"
    assert by_id["clear"]["operator_visible_flag"] == "1"
    assert by_id["clear"]["amazon_description_snippet"] == "Each pack contains 50 card sleeves."
    assert by_id["manual"]["queue_state"] == "needs_user_guidance"
    assert by_id["manual"]["operator_visible_flag"] == "1"
    assert by_id["rescan"]["queue_state"] == "rescan_needed"
    assert by_id["rescan"]["operator_visible_flag"] == "0"
    assert by_id["missing-page-clear"]["queue_state"] == "ai_cleared"
    assert by_id["missing-page-clear"]["operator_visible_flag"] == "1"
    assert "secondary evidence" in by_id["missing-page-clear"]["codex_ai_reason"]
    assert by_id["missing-page-manual"]["queue_state"] == "needs_user_guidance"
    assert by_id["missing-page-manual"]["operator_visible_flag"] == "1"
    assert by_id["missing-page-manual"]["codex_ai_confidence"] == "medium"
    assert by_id["reject"]["queue_state"] == "ai_rejected"
    assert by_id["reject"]["operator_visible_flag"] == "0"


def test_ai_product_check_gate_shows_waiting_row_when_queue_is_missing(tmp_path: Path) -> None:
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "sample_supplier"
        / "run_002"
    )
    handoff_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"supplier_id": "sample_supplier", "supplier_name": "Sample Supplier", "run_id": "run_002"},
        ]
    ).to_csv(handoff_dir / "candidate_manifest.csv", index=False)

    gate_df = build_ai_product_check_gate_df(root=tmp_path)

    assert len(gate_df.index) == 1
    assert gate_df.iloc[0]["queue_state"] == "waiting_for_ai_queue"
    assert gate_df.iloc[0]["operator_visible_flag"] == "0"


def test_legacy_handoff_is_blocked_from_new_product_review_and_shown_in_ai_gate(tmp_path: Path) -> None:
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "bliss_distribution"
        / "fpm_bliss_distribution_20260518T094415Z"
    )
    handoff_dir.mkdir(parents=True, exist_ok=True)
    pass_path = handoff_dir / "f_live_price_file_pass_review_20260518T115122Z.csv"
    pd.DataFrame(
        [
            {
                "active_supplier_id": "bliss_distribution",
                "active_run_id": "fpm_bliss_distribution_20260518T094415Z",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "18.6",
                "candidate_id": "kuriboh-sleeves",
                "supplier_sku": "KONKKS",
                "asin": "B09HKZWBDN",
                "title": "Yu-Gi-Oh! Kuriboh Kollection Card Sleeves",
            }
        ]
    ).to_csv(pass_path, index=False)
    near_path = handoff_dir / "f_live_price_file_near_miss_review_20260518T115122Z.csv"
    pd.DataFrame(
        [
            {
                "active_supplier_id": "bliss_distribution",
                "active_run_id": "fpm_bliss_distribution_20260518T094415Z",
                "review_batch_id": "near_miss_batch_001",
                "review_priority_score": "11.2",
                "candidate_id": "kuriboh-near",
                "supplier_sku": "KONKKS-NEAR",
                "asin": "B09HKZWBD0",
                "title": "Yu-Gi-Oh! Kuriboh Kollection Card Sleeves near miss",
            }
        ]
    ).to_csv(near_path, index=False)
    pd.DataFrame(
        [
            {
                "built_at_utc": "2026-05-18T11:51:22Z",
                "supplier_id": "bliss_distribution",
                "supplier_name": "Bliss Distribution",
                "run_id": "fpm_bliss_distribution_20260518T094415Z",
                "review_snapshot_id": "20260518T115122Z",
                "completed_at_utc": "2026-05-18T11:51:22Z",
                "pass_review_rows": "1",
                "near_miss_review_rows": "1",
                "pass_review_path": str(pass_path),
                "near_miss_review_path": str(near_path),
                "summary_path": "",
                "handoff_dir": str(handoff_dir),
                "published_to_operator_latest_flag": "0",
                "block_reason": "",
                "notes": "legacy pre AI gate",
            }
        ]
    ).to_csv(handoff_dir / "manifest.csv", index=False)

    snapshot_id = "handoff|bliss_distribution|fpm_bliss_distribution_20260518T094415Z"
    options = list_feeder_review_pack_options(root=tmp_path, include_history=True)
    pass_df = load_feeder_review_source_df("passes", root=tmp_path, review_pack_snapshot=snapshot_id)
    gate_df = build_ai_product_check_gate_df(root=tmp_path)

    assert not any(option["id"] == snapshot_id for option in options)
    assert pass_df.empty
    assert "B09HKZWBDN" in set(gate_df["asin"])
    row = gate_df[gate_df["asin"] == "B09HKZWBDN"].iloc[0]
    assert row["queue_state"] == "legacy_needs_ai_gate"
    assert row["source_review_pack_type"] == "passes"
    assert row["operator_visible_flag"] == "0"
    near_row = gate_df[gate_df["asin"] == "B09HKZWBD0"].iloc[0]
    assert near_row["queue_state"] == "legacy_manual_near_backlog"
    assert near_row["source_review_pack_type"] == "near_misses"


def test_legacy_timestamped_snapshot_is_hidden_when_ai_gate_is_active(tmp_path: Path) -> None:
    reports_dir = tmp_path / "out" / "analysis_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    handoff_root = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "review_handoffs"
    handoff_root.mkdir(parents=True, exist_ok=True)
    snapshot = "20260518T115122Z"
    pd.DataFrame(
        [
            {"observed_utc": "2026-05-18T11:51:22Z", "metric": "active_supplier_id", "value": "bliss_distribution"},
            {
                "observed_utc": "2026-05-18T11:51:22Z",
                "metric": "active_run_id",
                "value": "fpm_bliss_distribution_20260518T094415Z",
            },
            {"observed_utc": "2026-05-18T11:51:22Z", "metric": "pass_review_rows", "value": "1"},
        ]
    ).to_csv(reports_dir / f"f_live_price_file_review_summary_{snapshot}.csv", index=False)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "bliss_distribution",
                "active_run_id": "fpm_bliss_distribution_20260518T094415Z",
                "candidate_id": "kuriboh-sleeves",
                "supplier_sku": "KONKKS",
                "asin": "B09HKZWBDN",
                "title": "Yu-Gi-Oh! Kuriboh Kollection Card Sleeves",
            }
        ]
    ).to_csv(reports_dir / f"f_live_price_file_pass_review_{snapshot}.csv", index=False)

    options = list_feeder_review_pack_options(root=tmp_path, include_history=True)
    snapshot_df = load_feeder_review_source_df("passes", root=tmp_path, review_pack_snapshot=snapshot)

    assert not any(option["id"] == snapshot for option in options)
    assert snapshot_df.empty


def test_feeder_review_ui_loads_sql_review_pack_without_csv(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    snapshot = "20260429T150000Z"
    pass_df = pd.DataFrame(
        [
            {
                "observed_utc": "2026-04-29T15:00:00Z",
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "stocklist_20260429",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "50",
                "candidate_id": "sql-cand",
                "supplier_sku": "SKU-SQL",
                "asin": "B000000789",
                "title": "SQL only row",
            }
        ]
    )
    near_df = pd.DataFrame(columns=pass_df.columns)
    summary_df = pd.DataFrame(
        [
            {
                "observed_utc": "2026-04-29T15:00:00Z",
                "metric": "active_supplier_id",
                "value": "stocklist_supplier",
            },
            {
                "observed_utc": "2026-04-29T15:00:00Z",
                "metric": "active_run_id",
                "value": "stocklist_20260429",
            },
            {
                "observed_utc": "2026-04-29T15:00:00Z",
                "metric": "source_seen_at_utc",
                "value": "2026-04-29T14:45:00Z",
            },
        ]
    )
    write_review_pack_snapshots_sql_compat(
        pass_df=pass_df,
        near_miss_df=near_df,
        summary_df=summary_df,
        snapshot_id=snapshot,
    )

    options = list_feeder_review_pack_options(root=tmp_path, include_history=True)
    latest_summary = load_feeder_review_summary(root=tmp_path)
    latest_df = load_feeder_review_source_df("passes", root=tmp_path)
    historical_df = load_feeder_review_source_df("passes", root=tmp_path, review_pack_snapshot=snapshot)

    assert not (tmp_path / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv").exists()
    assert any(option["id"] == snapshot for option in options)
    assert latest_summary["active_run_id"] == "stocklist_20260429"
    assert latest_df.iloc[0]["candidate_id"] == "sql-cand"
    assert historical_df.iloc[0]["candidate_id"] == "sql-cand"


def test_latest_ai_gated_manifest_csv_overrides_stale_sql_latest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    stale_sql_pass_df = pd.DataFrame(
        [
            {
                "observed_utc": "2026-05-18T11:51:22Z",
                "active_supplier_id": "bliss_distribution",
                "active_run_id": "fpm_bliss_distribution_20260518T094415Z",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "kuriboh-sleeves",
                "supplier_sku": "KONKKS",
                "asin": "B09HKZWBDN",
                "title": "Yu-Gi-Oh! Kuriboh Kollection Card Sleeves",
            }
        ]
    )
    write_review_pack_snapshots_sql_compat(
        pass_df=stale_sql_pass_df,
        near_miss_df=pd.DataFrame(columns=stale_sql_pass_df.columns),
        summary_df=pd.DataFrame(
            [
                {"observed_utc": "2026-05-18T11:51:22Z", "metric": "active_supplier_id", "value": "bliss_distribution"},
                {
                    "observed_utc": "2026-05-18T11:51:22Z",
                    "metric": "active_run_id",
                    "value": "fpm_bliss_distribution_20260518T094415Z",
                },
            ]
        ),
        snapshot_id="sql_stale_bliss_snapshot",
    )

    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "stocklist_supplier"
        / "legacy_latest_pass_page_evidence_20260520T210352Z"
    )
    handoff_dir.mkdir(parents=True, exist_ok=True)
    pass_path = handoff_dir / "ai_operator_pass_review.csv"
    near_path = handoff_dir / "ai_operator_near_miss_review.csv"
    summary_path = handoff_dir / "ai_operator_review_summary.csv"
    live_manifest_path = (
        tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "review_handoff_manifest.csv"
    )
    live_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "stocklist_supplier_rescrape_subset_20260421T103451Z",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "stocklist-ai-cleared",
                "supplier_sku": "1144846",
                "asin": "B082NMTZC2",
                "title": "JVC Boombox",
                "f032_decision_id": "f032-stocklist",
                "f032_action": "allow_if_other_checks_pass",
                "codex_ai_action": "allow_if_other_checks_pass",
            }
        ]
    ).to_csv(pass_path, index=False)
    pd.DataFrame(columns=pd.read_csv(pass_path, dtype=str).columns).to_csv(near_path, index=False)
    pd.DataFrame(
        [
            {"observed_utc": "2026-05-20T21:03:52Z", "metric": "active_supplier_id", "value": "stocklist_supplier"},
            {
                "observed_utc": "2026-05-20T21:03:52Z",
                "metric": "active_run_id",
                "value": "legacy_latest_pass_page_evidence_20260520T210352Z",
            },
            {"observed_utc": "2026-05-20T21:03:52Z", "metric": "pass_review_rows", "value": "1"},
        ]
    ).to_csv(summary_path, index=False)
    pd.DataFrame(
        [
            {
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "run_id": "legacy_latest_pass_page_evidence_20260520T210352Z",
                "review_snapshot_id": "20260520T210352Z",
                "pass_review_path": str(pass_path),
                "near_miss_review_path": str(near_path),
                "summary_path": str(summary_path),
                "ai_gate_status": "passed",
                "operator_ready_flag": "1",
            }
        ]
    ).to_csv(live_manifest_path, index=False)

    latest_summary = load_feeder_review_summary(root=tmp_path)
    latest_df = load_feeder_review_source_df("passes", root=tmp_path)

    assert latest_summary["active_supplier_id"] == "stocklist_supplier"
    assert set(latest_df["asin"]) == {"B082NMTZC2"}
    assert "B09HKZWBDN" not in set(latest_df["asin"])


def test_feeder_review_window_scopes_latest_decisions_by_run_and_pack(tmp_path: Path) -> None:
    report_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "50",
                "candidate_id": "cand-shared",
                "supplier_sku": "SKU-1",
                "asin": "B000000001",
                "title": "Run 1 row",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-2",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "40",
                "candidate_id": "cand-shared",
                "supplier_sku": "SKU-2",
                "asin": "B000000002",
                "title": "Run 2 row",
            },
        ]
    ).to_csv(report_path, index=False)
    _write_f_contract_rows(
        tmp_path,
        "feeder_review_events",
        [
            {
                "event_utc": "2026-04-22T15:00:00Z",
                "event_id": "evt-run1",
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-shared",
                "supplier_sku": "SKU-1",
                "asin_raw": "B000000001",
                "asin_padded": "B000000001",
                "amazon_dp_url": "https://www.amazon.co.uk/dp/B000000001",
                "review_decision": "pass",
                "review_note": "done",
                "actor": "tester",
                "source_reference": "test",
                "title": "Run 1 row",
                "brand": "",
                "main_rank": "",
                "review_priority_score": "50",
            }
        ],
    )

    window_df, meta = build_feeder_review_window_df("passes", root=tmp_path)

    assert meta["undecided_rows"] == 1
    assert len(window_df.index) == 1
    assert window_df.iloc[0]["candidate_id"] == "cand-shared"
    assert window_df.iloc[0]["active_run_id"] == "run-2"


def test_feeder_review_window_keeps_source_order_before_limit(tmp_path: Path) -> None:
    report_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "10",
                "candidate_id": "cand-low",
                "supplier_sku": "SKU-LOW",
                "asin": "B000000010",
                "title": "Low",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "200",
                "candidate_id": "cand-high",
                "supplier_sku": "SKU-HIGH",
                "asin": "B000000200",
                "title": "High",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "50",
                "candidate_id": "cand-mid",
                "supplier_sku": "SKU-MID",
                "asin": "B000000050",
                "title": "Mid",
            },
        ]
    ).to_csv(report_path, index=False)

    window_df, _ = build_feeder_review_window_df("passes", root=tmp_path, page_size=3)

    assert list(window_df["candidate_id"]) == ["cand-low", "cand-high", "cand-mid"]


def test_feeder_review_done_key_is_scoped_to_view_filters() -> None:
    key_a = _feeder_review_done_key(
        pack_type="passes",
        supplier_filter="stocklist_supplier",
        review_batch_id="pass_batch_001",
        search_text="",
    )
    key_b = _feeder_review_done_key(
        pack_type="passes",
        supplier_filter="stocklist_supplier",
        review_batch_id="pass_batch_002",
        search_text="",
    )
    key_c = _feeder_review_done_key(
        pack_type="passes",
        supplier_filter="another_supplier",
        review_batch_id="pass_batch_001",
        search_text="",
    )

    assert key_a != key_b
    assert key_a != key_c


def test_feeder_review_ui_draft_save_restore_and_clear(tmp_path: Path) -> None:
    save_result = save_feeder_review_ui_drafts(
        root=tmp_path,
        reviewed_rows=[
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-a",
                "supplier_sku": "SKU-A",
                "asin": "B000000001",
                "title": "Title A",
                "main_rank": "120",
                "review_priority_score": "90",
                "review_decision": "pass",
                "review_reason_code": "profit_too_weak",
                "review_note": "looks good",
                "row_done": True,
                "country_of_origin": "GB",
                "product_tax_code": "A_GEN_STANDARD",
                "currency_code": "GBP",
                "price_includes_tax": "1",
                "starting_price_gbp": "12.34",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-b",
                "supplier_sku": "SKU-B",
                "asin": "B000000002",
                "title": "Title B",
                "main_rank": "220",
                "review_priority_score": "80",
                "review_decision": "",
                "review_note": "",
                "row_done": False,
            },
        ],
        supplier_filter="stocklist_supplier",
        review_batch_id="pass_batch_001",
        search_text="controller",
    )
    assert save_result["rows_saved"] == 1
    drafts_df = load_feeder_review_ui_drafts_df(root=tmp_path)
    assert len(drafts_df.index) == 1
    row = drafts_df.iloc[0]
    assert row["candidate_id"] == "cand-a"
    assert row["draft_decision"] == "pass"
    assert row["draft_reason_code"] == "profit_too_weak"
    assert row["draft_note"] == "looks good"
    assert row["draft_done"] == "1"
    assert row["draft_country_of_origin"] == "GB"
    assert row["draft_product_tax_code"] == "A_GEN_STANDARD"
    assert row["draft_currency_code"] == "GBP"
    assert row["draft_price_includes_tax"] == "1"
    assert row["draft_starting_price_gbp"] == "12.34"

    clear_result = clear_feeder_review_ui_drafts(
        root=tmp_path,
        rows=[
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "candidate_id": "cand-a",
            }
        ],
    )
    assert clear_result["rows_removed"] == 1
    drafts_after_clear = load_feeder_review_ui_drafts_df(root=tmp_path)
    assert len(drafts_after_clear.index) == 0


def test_feeder_review_event_and_draft_logs_read_sql_when_csv_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    save_feeder_review_ui_drafts(
        root=tmp_path,
        reviewed_rows=[
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-draft",
                "supplier_sku": "SKU-D",
                "asin": "B000000001",
                "title": "Draft Title",
                "review_decision": "pass",
                "review_reason_code": "seller_controlled",
                "review_note": "draft note",
                "row_done": True,
            }
        ],
        supplier_filter="stocklist_supplier",
        review_batch_id="pass_batch_001",
        search_text="",
    )
    submit_feeder_review_batch(
        root=tmp_path,
        reviewed_rows=[
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-event",
                "supplier_sku": "SKU-E",
                "asin": "B000000002",
                "title": "Event Title",
                "review_decision": "fail",
                "review_reason_code": "missing_evidence",
                "review_note": "event note",
            }
        ],
    )
    (tmp_path / get_o_output_contract("feeder_review_ui_drafts").rel_path).unlink()
    (tmp_path / get_f_output_contract("feeder_review_events").rel_path).unlink()

    drafts_df = load_feeder_review_ui_drafts_df(root=tmp_path)
    events_df = load_feeder_review_events_df(root=tmp_path)

    assert drafts_df.iloc[0]["candidate_id"] == "cand-draft"
    assert drafts_df.iloc[0]["draft_reason_code"] == "seller_controlled"
    assert events_df.iloc[0]["candidate_id"] == "cand-event"
    assert events_df.iloc[0]["review_reason_code"] == "missing_evidence"


def test_feeder_review_widget_key_is_scoped_to_pack_and_run() -> None:
    row_a = {
        "active_supplier_id": "stocklist_supplier",
        "active_run_id": "run-1",
        "candidate_id": "cand-1",
    }
    row_b = {
        "active_supplier_id": "stocklist_supplier",
        "active_run_id": "run-2",
        "candidate_id": "cand-1",
    }
    key_a = _review_widget_key(row_a, pack_type="passes")
    key_b = _review_widget_key(row_b, pack_type="passes")
    key_c = _review_widget_key(row_a, pack_type="near_misses")
    assert key_a != key_b
    assert key_a != key_c


def test_feeder_review_sent_df_returns_latest_decisions_only(tmp_path: Path) -> None:
    report_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "90",
                "candidate_id": "cand-a",
                "supplier_sku": "SKU-A",
                "asin": "B000000001",
                "title": "A",
            }
        ]
    ).to_csv(report_path, index=False)
    _write_f_contract_rows(
        tmp_path,
        "feeder_review_events",
        [
            {
                "event_utc": "2026-04-22T15:00:00Z",
                "event_id": "evt-a",
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-a",
                "supplier_sku": "SKU-A",
                "asin_raw": "B000000001",
                "asin_padded": "B000000001",
                "amazon_dp_url": "https://www.amazon.co.uk/dp/B000000001",
                "review_decision": "fail",
                "review_note": "bad listing",
                "actor": "tester",
                "source_reference": "test",
                "title": "A",
                "brand": "",
                "main_rank": "",
                "review_priority_score": "90",
            }
        ],
    )

    sent_df = build_feeder_review_sent_df("passes", root=tmp_path, page_size=10)

    assert len(sent_df.index) == 1
    assert sent_df.iloc[0]["candidate_id"] == "cand-a"
    assert sent_df.iloc[0]["latest_review_decision"] == "fail"
    assert sent_df.iloc[0]["latest_review_note"] == "bad listing"


def test_feeder_review_reopen_batch_restores_candidate_to_undecided(tmp_path: Path) -> None:
    report_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "90",
                "candidate_id": "cand-a",
                "supplier_sku": "SKU-A",
                "asin": "B000000001",
                "title": "A",
            }
        ]
    ).to_csv(report_path, index=False)
    _write_f_contract_rows(
        tmp_path,
        "feeder_review_events",
        [
            {
                "event_utc": "2026-04-22T15:00:00Z",
                "event_id": "evt-a",
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-a",
                "supplier_sku": "SKU-A",
                "asin_raw": "B000000001",
                "asin_padded": "B000000001",
                "amazon_dp_url": "https://www.amazon.co.uk/dp/B000000001",
                "review_decision": "pass",
                "review_note": "ok",
                "actor": "tester",
                "source_reference": "test",
                "title": "A",
                "brand": "",
                "main_rank": "",
                "review_priority_score": "90",
            }
        ],
    )

    before_df, before_meta = build_feeder_review_window_df("passes", root=tmp_path)
    assert before_meta["undecided_rows"] == 0
    assert before_df.empty

    reopen_result = submit_feeder_review_reopen_batch(
        root=tmp_path,
        rows_to_reopen=[
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-a",
                "supplier_sku": "SKU-A",
                "asin": "B000000001",
                "title": "A",
                "brand": "",
                "main_rank": "",
                "review_priority_score": "90",
            }
        ],
    )
    assert reopen_result["events_applied"] == 1

    after_df, after_meta = build_feeder_review_window_df("passes", root=tmp_path)
    assert after_meta["undecided_rows"] == 1
    assert len(after_df.index) == 1
    assert after_df.iloc[0]["candidate_id"] == "cand-a"


def test_reorder_input_df_leaves_qty_and_price_blank_but_keeps_suggestions_visible(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_review_queue",
        [
            {
                "queue_utc": "2026-04-03T10:00:00Z",
                "seller_sku": "SKU-R1",
                "asin": "ASIN-R1",
                "title": "Row Product",
                "main_image": "https://example.com/r1.jpg",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "recommendation_status": "full_restock",
                "suggested_qty": "12",
                "suggested_unit_cost_gbp": "5.5",
                "suggested_market_price_gbp": "8",
                "expected_forward_roi_pct": "60",
                "expected_forward_profit_per_unit_gbp": "3",
                "days_cover_available_only": "1",
                "days_cover_total_pipeline": "1",
                "reason_codes": "ROI_OK",
                "queue_status": "needs_review",
                "suggested_action": "full_restock",
                "key_reason": "ROI_OK",
                "confidence_note": "",
                "cost_mode": "test",
                "recommendation_basis": "test_cost_snapshot",
                "snooze_until_utc": "",
            }
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)
    reorder_df = build_reorder_input_df(datasets)
    assert len(reorder_df) == 1
    row = reorder_df.iloc[0]
    assert row["seller_sku"] == "SKU-R1"
    assert row["order_qty"] == ""
    assert row["confirmed_price"] == ""
    assert row["restk"] == "12"
    assert row["cpu"] == "5.5"
    assert row["row_status"] == "needs_price"
    assert bool(row["send"]) is False


def test_reorder_input_df_uses_pack_profile_for_operator_qty_and_lookup_fields(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_review_queue",
        [
            {
                "queue_utc": "2026-04-03T10:00:00Z",
                "seller_sku": "SKU-RPACK",
                "asin": "ASIN-RPACK",
                "title": "Pack Product",
                "main_image": "https://example.com/rpack.jpg",
                "supplier_code": "SUP-P",
                "supplier_name": "Gamma",
                "recommendation_status": "full_restock",
                "suggested_qty": "60",
                "suggested_unit_cost_gbp": "5.5",
                "suggested_market_price_gbp": "8",
                "expected_forward_roi_pct": "60",
                "expected_forward_profit_per_unit_gbp": "3",
                "days_cover_available_only": "1",
                "days_cover_total_pipeline": "1",
                "reason_codes": "ROI_OK",
                "queue_status": "needs_review",
                "suggested_action": "full_restock",
                "key_reason": "ROI_OK",
                "confidence_note": "",
                "cost_mode": "test",
                "recommendation_basis": "test_cost_snapshot",
                "snooze_until_utc": "",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_source_view",
        [
            {
                "asof_utc": "2026-04-03T10:00:00Z",
                "seller_sku": "SKU-RPACK",
                "asin": "ASIN-RPACK",
                "supplier_code": "SUP-P",
                "supplier_name": "Gamma",
                "sale_status": "active",
                "available_now": "7",
                "total_quantity_now": "9",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_7d": "2.2",
                "velocity_30d": "2.0",
                "velocity_90d": "1.9",
                "current_supplier_buy_cost_gbp": "5.5",
                "current_supplier_cost_source": "supplier_catalog_price",
                "market_price_gbp": "8.0",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "expected_refund_cost_per_unit_gbp": "0.1",
                "roi_at_market_price_pct": "60",
                "source_inventory_asof": "2026-04-03T09:00:00Z",
                "source_velocity_asof": "2026-04-03",
                "source_performance_asof": "2026-04-03",
                "supplier_sku": "GAMMA-RAW-20",
                "barcode": "1234567890123",
                "amazon_pack_size": "3",
                "pack_conversion_note": "repack into packs of 3",
                "order_qty_mode": "sell_packs",
                "order_qty_unit_label": "Packs",
                "sell_pack_qty": "3",
                "supplier_case_qty": "20",
                "supplier_case_multiple": "1",
                "valid_order_step": "20",
                "repack_required": "1",
                "bundle_required": "0",
                "display_qtys_label": "Pack 3 | Case 20 | Step 20",
            }
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)
    reorder_df = build_reorder_input_df(datasets)
    assert len(reorder_df) == 1
    row = reorder_df.iloc[0]
    assert row["qtys"] == "Pack 3 | Case 20 | Step 20"
    assert row["barcode"] == "1234567890123"
    assert row["supply_code"] == "GAMMA-RAW-20"
    assert row["order_qty"] == ""
    assert row["restk"] == "20pk (60)"
    assert row["order_qty_mode"] == "sell_packs"
    assert row["order_qty_unit_label"] == "Packs"
    assert row["row_status"] == "needs_price"


def test_reorder_input_df_shows_legacy_bridge_rows_before_native_duplicates(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "legacy_purchase_list_bridge",
        [
            {
                "bridge_utc": "2026-05-22T10:00:00Z",
                "source_system": "legacy_purchase_list",
                "source_sheet_id": "sheet-1",
                "source_sheet_title": "Amazon Supplier Process",
                "source_tab": "Purchase List",
                "source_row_number": "7",
                "source_reference": "legacy_purchase_list:sheet-1:Purchase List:row7",
                "supplier_name": "Legacy Supplier",
                "seller_sku": "SKU-BRIDGE",
                "asin": "ASIN-BRIDGE",
                "title": "Bridge Product",
                "display_qtys_label": "Unit",
                "barcode": "5000000000001",
                "supplier_sku": "SUPPLY-7",
                "suggested_action": "full_restock",
                "recommendation_status": "full_restock",
                "sheet_recommend_label": "Restock",
                "suggested_qty": "8",
                "recommended_qty_rounded": "8",
                "current_supplier_buy_cost_gbp": "2.5",
                "suggested_unit_cost_gbp": "2.5",
                "suggested_market_price_gbp": "4",
                "market_price_gbp": "4",
                "expected_forward_roi_pct": "60",
                "forward_roi_pct": "60",
                "forward_profit_per_unit_gbp": "1.5",
                "ordered_open": "2",
                "available_now": "0",
                "velocity_30d": "1.2",
                "days_cover_available_only": "0",
                "queue_status": "needs_review",
                "cost_mode": "legacy_sheet",
                "recommendation_basis": "legacy_purchase_list_restock",
                "bridge_status": "ready",
                "bridge_note": "LEGACY_PURCHASE_LIST_RESTOCK|NATIVE_O_PARITY_PENDING",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_review_queue",
        [
            {
                "queue_utc": "2026-05-22T10:01:00Z",
                "seller_sku": "SKU-BRIDGE",
                "asin": "ASIN-BRIDGE",
                "supplier_code": "NATIVE",
                "supplier_name": "Native Supplier",
                "recommendation_status": "wait",
                "suggested_qty": "0",
                "suggested_unit_cost_gbp": "9",
                "suggested_market_price_gbp": "10",
                "expected_forward_roi_pct": "1",
                "expected_forward_profit_per_unit_gbp": "1",
                "days_cover_available_only": "99",
                "days_cover_total_pipeline": "99",
                "reason_codes": "NATIVE_STALE_WAIT",
                "queue_status": "needs_review",
                "suggested_action": "wait",
                "key_reason": "NATIVE_STALE_WAIT",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            },
            {
                "queue_utc": "2026-05-22T10:01:00Z",
                "seller_sku": "SKU-NATIVE",
                "asin": "ASIN-NATIVE",
                "supplier_code": "NATIVE",
                "supplier_name": "Native Supplier",
                "recommendation_status": "full_restock",
                "suggested_qty": "3",
                "suggested_unit_cost_gbp": "5",
                "suggested_market_price_gbp": "8",
                "expected_forward_roi_pct": "60",
                "expected_forward_profit_per_unit_gbp": "3",
                "days_cover_available_only": "1",
                "days_cover_total_pipeline": "1",
                "reason_codes": "ROI_OK",
                "queue_status": "needs_review",
                "suggested_action": "full_restock",
                "key_reason": "ROI_OK",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            },
        ],
    )
    _write_contract_rows(
        tmp_path,
        "product_db_operator_view",
        [
            {
                "seller_sku": "SKU-BRIDGE",
                "asin": "ASIN-BRIDGE",
                "title": "Bridge Product",
                "main_image": "https://example.com/bridge.jpg",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_source_view",
        [
            {
                "asof_utc": "2026-05-22T10:01:00Z",
                "seller_sku": "SKU-BRIDGE",
                "asin": "ASIN-BRIDGE",
                "supplier_code": "LEGACY",
                "supplier_name": "Legacy Supplier",
                "sale_status": "active",
                "current_supplier_buy_cost_gbp": "2.4",
                "price_list_unit_cost_gbp": "2.4",
                "price_list_unit_code": "PK8",
                "price_list_pack_size": "8",
                "price_list_pack_cost_gbp": "19.20",
                "price_list_moq": "8",
                "supplier_pack_size": "8",
                "moq": "8",
                "order_qty_mode": "sell_packs",
                "order_qty_unit_label": "Packs",
                "sell_pack_qty": "8",
                "supplier_case_qty": "8",
                "supplier_case_multiple": "1",
                "valid_order_step": "8",
                "display_qtys_label": "Pack 8 | Case 8",
                "pack_conversion_note": "Supplier list PK8",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_profit_checks_live",
        [
            {
                "check_utc": "2026-05-22T10:02:00Z",
                "seller_sku": "SKU-BRIDGE",
                "asin": "ASIN-BRIDGE",
                "supplier_name": "Legacy Supplier",
                "suggested_action": "full_restock",
                "profit_verdict": "safe_to_review",
                "profit_proof_source": "legacy_sheet_profit_hint",
                "profit_check_message": "Profit check: Review - Sheet ROI hint only.",
                "current_sell_price_gbp": "4",
                "sell_price_basis": "LEGACY_PURCHASE_LIST_ROI_BACKSOLVE",
                "supplier_cost_gbp": "2.5",
                "fee_drag_gbp": "",
                "refund_drag_gbp": "",
                "forward_profit_per_unit_gbp": "1.5",
                "forward_roi_pct": "60",
                "break_even_max_cost_gbp": "",
                "target_roi_max_cost_gbp": "",
                "target_roi_pct": "10",
                "demand_status": "demand_present",
                "demand_units_per_day": "1.2",
                "days_cover_available_only": "0",
                "effective_supply_units": "2",
                "recommended_qty": "8",
                "missing_input_reasons": "",
                "guardrail_flags": "legacy_sheet_profit_not_native_proof",
                "bad_economics_snapshot_count": "0",
                "bad_economics_window_days": "0",
                "drop_review_eligible": "0",
                "source_system": "legacy_purchase_list",
                "source_reference": "legacy_purchase_list:sheet-1:Purchase List:row7",
                "price_list_unit_cost_gbp": "2.4",
                "price_list_source_received_at_utc": "2026-05-22T07:30:00Z",
                "cost_match_method": "barcode_supplier_matched",
                "cost_confidence": "price_list_actual_match",
                "supplier_cost_review_reason": "",
                "expected_cost_source": "supplier_price_list_no_discount",
                "actual_paid_unit_cost_gbp": "2.5",
                "price_list_vs_actual_paid_delta_gbp": "-0.1",
                "price_list_vs_purchase_reference_delta_gbp": "-0.1",
                "price_proof_summary": "Current supplier list GBP 2.4; matched by barcode supplier matched",
            }
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)
    reorder_df = build_reorder_input_df(datasets)

    assert list(reorder_df["seller_sku"]) == ["SKU-BRIDGE", "SKU-NATIVE"]
    bridge = reorder_df.iloc[0]
    assert bridge["source_system"] == "legacy_purchase_list"
    assert bridge["source_reference"] == "legacy_purchase_list:sheet-1:Purchase List:row7"
    assert bridge["supplier_name"] == "Legacy Supplier"
    assert bridge["supply_code"] == "SUPPLY-7"
    assert bridge["barcode"] == "5000000000001"
    assert bridge["qtys"] == "Pack 8 | Case 8"
    assert bridge["restk"] == "1pk (8)"
    assert bridge["order_qty_mode"] == "sell_packs"
    assert bridge["order_qty_unit_label"] == "Packs"
    assert bridge["sell_pack_qty"] == "8"
    assert bridge["cpu"] == "2.4"
    assert bridge["recommend"] == "Restock"
    assert bridge["main_image"] == "https://example.com/bridge.jpg"
    assert bridge["profit_verdict"] == "safe_to_review"
    assert bridge["profit_proof_source"] == "legacy_sheet_profit_hint"
    assert bridge["profit_guardrail_flags"] == "legacy_sheet_profit_not_native_proof"
    assert bridge["price_list_unit_cost_gbp"] == "2.4"
    assert bridge["cost_match_method"] == "barcode_supplier_matched"
    assert "Current supplier list GBP 2.4" in bridge["price_proof_summary"]


def test_profit_check_badge_keeps_long_explanation_in_hover_panel() -> None:
    badge_html = _profit_check_badge_html(
        {
            "profit_verdict": "needs_price_check",
            "profit_proof_source": "legacy_sheet_profit_hint",
            "profit_check_message": "Needs price check before this is a clean buy.",
            "profit_guardrail_flags": (
                "legacy_sheet_profit_not_native_proof|legacy_roi_backsolved_from_sheet|"
                "supplier_cost_confirmation_required"
            ),
            "price_proof_summary": (
                "No current supplier list match; confidence actual paid without list reference; "
                "old paid GBP 7.59; check reason missing current price list cost"
            ),
            "expected_forward_roi_pct": "36",
            "forward_profit_per_unit_gbp": "2.73",
            "current_sell_price_gbp": "15.18",
            "cpu": "7.59",
        }
    )

    assert "Profit: check price" in badge_html
    assert "o-hover-wrap" in badge_html
    assert "o-hover-panel" in badge_html
    assert "Needs price check before this is a clean buy." in badge_html
    assert "Sheet ROI hint only" in badge_html
    assert "Guardrail:" in badge_html
    assert "Price proof:" in badge_html
    assert "<strong>" not in badge_html
    assert "<br>" not in badge_html


def test_reorder_input_df_adds_open_ordered_qty_from_ordered_stock_state(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_review_queue",
        [
            {
                "queue_utc": "2026-04-03T10:00:00Z",
                "seller_sku": "SKU-ONORDER",
                "asin": "ASIN-ONORDER",
                "title": "Open Ordered Product",
                "main_image": "",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "recommendation_status": "full_restock",
                "suggested_qty": "10",
                "suggested_unit_cost_gbp": "2.5",
                "suggested_market_price_gbp": "5",
                "expected_forward_roi_pct": "40",
                "expected_forward_profit_per_unit_gbp": "1",
                "days_cover_available_only": "2",
                "days_cover_total_pipeline": "3",
                "reason_codes": "ROI_OK",
                "queue_status": "needs_review",
                "suggested_action": "full_restock",
                "key_reason": "ROI_OK",
                "confidence_note": "",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                "snooze_until_utc": "",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_source_view",
        [
            {
                "asof_utc": "2026-04-03T10:00:00Z",
                "seller_sku": "SKU-ONORDER",
                "asin": "ASIN-ONORDER",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "sale_status": "active",
                "available_now": "4",
                "total_quantity_now": "4",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_7d": "1",
                "velocity_30d": "1",
                "velocity_90d": "1",
                "current_supplier_buy_cost_gbp": "2.5",
                "current_supplier_cost_source": "supplier_catalog_price",
                "market_price_gbp": "5",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "expected_refund_cost_per_unit_gbp": "0",
                "roi_at_market_price_pct": "40",
                "source_inventory_asof": "2026-04-03T09:00:00Z",
                "source_velocity_asof": "2026-04-03",
                "source_performance_asof": "2026-04-03",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "ordered_stock_state",
        [
            {
                "asof_utc": "2026-04-03T10:00:00Z",
                "po_id": "PO-1",
                "po_line_id": "PO-1-L001",
                "seller_sku": "SKU-ONORDER",
                "asin": "ASIN-ONORDER",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "ordered_qty": "7",
                "received_qty": "2",
                "remaining_open_qty": "5",
                "receipt_status": "partial_received",
                "expected_arrival_utc": "2026-04-10T00:00:00Z",
                "backorder_flag": "0",
                "source_event_id": "evt-1",
                "source_decision_action": "approve_full_restock",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            },
            {
                "asof_utc": "2026-04-03T10:00:00Z",
                "po_id": "PO-2",
                "po_line_id": "PO-2-L001",
                "seller_sku": "SKU-ONORDER",
                "asin": "ASIN-ONORDER",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "ordered_qty": "4",
                "received_qty": "0",
                "remaining_open_qty": "4",
                "receipt_status": "not_received",
                "expected_arrival_utc": "2026-04-11T00:00:00Z",
                "backorder_flag": "0",
                "source_event_id": "evt-2",
                "source_decision_action": "approve_test_restock",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            },
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)
    reorder_df = build_reorder_input_df(datasets)
    row = reorder_df.iloc[0]
    assert row["stock"] == "4"
    assert row["ordered_open"] == "9"


def test_reorder_batch_submits_selected_rows_to_decision_inbox(tmp_path: Path) -> None:
    rows_df = pd.DataFrame(
        [
            {
                "send": True,
                "seller_sku": "SKU-B1",
                "asin": "ASIN-B1",
                "suggested_action": "full_restock",
                "order_qty": "9",
                "confirmed_price": "4.2",
                "disc": False,
                "drop": False,
                "snze": False,
                "snooze_date": "",
                "cost_mode": "test",
                "recommendation_reason": "ROI_OK",
                "decision_note": "batch submit",
                "source_system": "legacy_purchase_list",
                "source_reference": "legacy_purchase_list:sheet-1:Purchase List:row7",
                "profit_verdict": "safe_to_review",
                "profit_proof_source": "legacy_sheet_profit_hint",
            },
            {
                "send": True,
                "seller_sku": "SKU-B2",
                "asin": "ASIN-B2",
                "suggested_action": "test_restock",
                "order_qty": "",
                "confirmed_price": "",
                "disc": False,
                "drop": False,
                "snze": False,
                "snooze_date": "",
                "cost_mode": "live",
                "recommendation_reason": "needs info",
                "decision_note": "",
            },
            {
                "send": True,
                "seller_sku": "SKU-B3",
                "asin": "ASIN-B3",
                "suggested_action": "wait",
                "order_qty": "",
                "confirmed_price": "",
                "disc": False,
                "drop": False,
                "snze": True,
                "snooze_date": "2026-04-10",
                "cost_mode": "live",
                "recommendation_reason": "snooze it",
                "decision_note": "",
            },
        ]
    )

    result = submit_reorder_batch(root=tmp_path, rows_df=rows_df, actor="tester", source_reference="batch_test")
    assert result["events_applied"] == 2
    assert len(result["skipped_rows"]) == 1
    assert "SKU-B2:missing_qty_or_price" in result["skipped_rows"]

    inbox_path = tmp_path / get_o_output_contract("restock_decision_events").rel_path
    inbox_df = pd.read_csv(inbox_path, dtype=str).fillna("")
    assert len(inbox_df) == 2
    first = inbox_df[inbox_df["seller_sku"] == "SKU-B1"].iloc[0]
    snoozed = inbox_df[inbox_df["seller_sku"] == "SKU-B3"].iloc[0]
    assert first["action"] == "approve_full_restock"
    assert first["confirmed_qty"] == "9"
    assert first["confirmed_unit_cost"] == "4.2"
    assert first["actor"] == "tester"
    assert first["source_reference"] == "batch_test|legacy_purchase_list|legacy_purchase_list:sheet-1:Purchase List:row7"
    assert first["profit_verdict"] == "safe_to_review"
    assert first["profit_proof_source"] == "legacy_sheet_profit_hint"
    assert snoozed["action"] == "snooze"
    assert snoozed["snooze_until_utc"] == "2026-04-10T00:00:00Z"


def test_reorder_batch_converts_operator_pack_qty_back_to_raw_units(tmp_path: Path) -> None:
    rows_df = pd.DataFrame(
        [
            {
                "send": True,
                "seller_sku": "SKU-PACK-B1",
                "asin": "ASIN-PACK-B1",
                "suggested_action": "full_restock",
                "order_qty": "20",
                "confirmed_price": "4.2",
                "disc": False,
                "drop": False,
                "snze": False,
                "snooze_date": "",
                "cost_mode": "test",
                "recommendation_reason": "ROI_OK",
                "decision_note": "pack submit",
                "order_qty_mode": "sell_packs",
                "sell_pack_qty": "3",
                "amazon_pack_size": "3",
            }
        ]
    )

    result = submit_reorder_batch(root=tmp_path, rows_df=rows_df, actor="tester", source_reference="batch_test")
    assert result["events_applied"] == 1
    assert result["skipped_rows"] == []

    inbox_path = tmp_path / get_o_output_contract("restock_decision_events").rel_path
    inbox_df = pd.read_csv(inbox_path, dtype=str).fillna("")
    assert len(inbox_df) == 1
    row = inbox_df.iloc[0]
    assert row["seller_sku"] == "SKU-PACK-B1"
    assert row["confirmed_qty"] == "60"
    assert row["confirmed_unit_cost"] == "4.2"


def test_reorder_price_safety_blocks_over_max_submit_and_renders_hover() -> None:
    row = {
        "seller_sku": "SKU-PRICE",
        "suggested_action": "full_restock",
        "max_safe_unit_cost_gbp": "1.90",
        "price_list_unit_cost_gbp": "2.00",
        "usual_paid_unit_cost_gbp": "1.70",
        "price_status": "caution_usual_paid_under_list",
        "price_status_message": "usual paid is under list",
        "price_proof_summary": "usual paid GBP 1.70; max safe buy cost GBP 1.90",
    }
    under = _confirmed_price_safety(row, "1.70")
    over = _confirmed_price_safety(row, "2.00")
    chips = _price_proof_chips_html(row, "2.00")

    assert under["status"] == "confirmed_under_max"
    assert over["status"] == "confirmed_over_max_blocked"
    assert over["blocked"] == "1"
    assert "Max pay" in chips
    assert "Blocked" in chips


def test_reorder_submit_blocks_typed_price_above_max(tmp_path: Path) -> None:
    rows_df = pd.DataFrame(
        [
            {
                "send": True,
                "seller_sku": "SKU-OVER-MAX",
                "asin": "ASIN-OVER-MAX",
                "suggested_action": "full_restock",
                "order_qty": "2",
                "confirmed_price": "2.00",
                "max_safe_unit_cost_gbp": "1.90",
                "price_list_unit_cost_gbp": "2.00",
                "usual_paid_unit_cost_gbp": "1.70",
                "price_list_change_status": "cost_up",
                "price_status": "over_max_snooze_candidate",
                "price_status_message": "Current expected cost is above Max pay.",
                "disc": False,
                "drop": False,
                "snze": False,
                "snooze_date": "",
                "cost_mode": "live",
            }
        ]
    )

    result = submit_reorder_batch(root=tmp_path, rows_df=rows_df, actor="tester", source_reference="batch_test")

    assert result["events_applied"] == 0
    assert result["skipped_rows"] == ["SKU-OVER-MAX:confirmed_price_above_max_safe_cost"]


def test_price_list_lookup_searches_change_log_and_cost_truth() -> None:
    datasets = {
        "supplier_price_list_change_log_live": pd.DataFrame(
            [
                {
                    "supplier_name": "ABGee",
                    "supplier_sku": "985 49830",
                    "barcode": "889698498302",
                    "title": "Leatherface",
                    "change_status": "cost_up",
                    "current_unit_cost_gbp": "7.59",
                    "current_pack_size": "12",
                    "current_pack_cost_gbp": "91.08",
                    "current_source_batch_id": "abgee_20260522",
                }
            ]
        ),
        "supplier_buy_cost_truth": pd.DataFrame(),
    }

    result = build_price_list_lookup_results(datasets, query="889698498302", supplier_filter="ABGee")

    assert len(result.index) == 1
    assert result.iloc[0]["supply_code"] == "985 49830"
    assert result.iloc[0]["pack_size"] == "12"


def test_filter_reorder_rows_defaults_to_actionable_and_sorts_by_supplier() -> None:
    reorder_df = pd.DataFrame(
        [
            {
                "seller_sku": "SKU-WAIT",
                "title": "Wait product",
                "asin": "ASIN-WAIT",
                "supplier_name": "Zulu",
                "suggested_action": "wait",
                "row_status": "blocked",
            },
            {
                "seller_sku": "SKU-READY-A",
                "title": "Ready A",
                "asin": "ASIN-RA",
                "supplier_name": "Alpha",
                "suggested_action": "full_restock",
                "row_status": "ready",
            },
            {
                "seller_sku": "SKU-READY-Z",
                "title": "Ready Z",
                "asin": "ASIN-RZ",
                "supplier_name": "Zulu",
                "suggested_action": "test_restock",
                "row_status": "needs_price",
            },
        ]
    )
    filtered = filter_reorder_rows(reorder_df)
    assert list(filtered["seller_sku"]) == ["SKU-READY-A", "SKU-READY-Z"]
    assert "_supplier_label" in filtered.columns
    assert filtered.iloc[0]["_supplier_label"] == "Alpha"
    assert filtered.iloc[1]["_supplier_label"] == "Zulu"


def test_filter_reorder_rows_supplier_and_search_filters() -> None:
    reorder_df = pd.DataFrame(
        [
            {
                "seller_sku": "SKU-A1",
                "title": "Toothpaste Kids",
                "asin": "ASIN-A1",
                "supplier_name": "Alpha",
                "suggested_action": "full_restock",
                "row_status": "ready",
            },
            {
                "seller_sku": "SKU-B1",
                "title": "Protein Shake",
                "asin": "ASIN-B1",
                "supplier_name": "Beta",
                "suggested_action": "test_restock",
                "row_status": "ready",
            },
        ]
    )
    filtered = filter_reorder_rows(
        reorder_df,
        supplier_filter="Beta",
        search_text="protein",
    )
    assert len(filtered.index) == 1
    row = filtered.iloc[0]
    assert row["seller_sku"] == "SKU-B1"
    assert row["_supplier_label"] == "Beta"


def test_o_ui_loads_current_backtest_policy_values(tmp_path: Path) -> None:
    _write_f_contract_rows(
        tmp_path,
        "feeder_backtest_policy_live",
        [
            {
                "observed_utc": "2026-04-10T14:40:00Z",
                "policy_id": "f_backtest_policy_v1",
                "policy_version": "1.0",
                "policy_status": "active",
                "minimum_expected_profit_gbp": "100",
                "entry_target_roi_pct": "20",
                "working_floor_roi_pct": "10",
                "exit_floor_roi_pct": "0",
                "emergency_floor_roi_pct": "-5",
                "recency_weight_30d": "0.5",
                "recency_weight_90d": "0.3",
                "recency_weight_180d": "0.15",
                "recency_weight_365d": "0.05",
                "ceiling_warn_ratio_30d": "1.25",
                "ceiling_red_ratio_30d": "1.5",
                "ceiling_extreme_ratio_30d": "2",
                "shock_trigger_pct_1d": "20",
                "shared_sales_default_pct": "50",
                "policy_source": "system_default_v1",
                "notes": "",
            }
        ],
    )
    row = load_backtest_policy_live_row(root=tmp_path)
    assert row["policy_id"] == "f_backtest_policy_v1"
    assert row["minimum_expected_profit_gbp"] == "100"
    assert row["entry_target_roi_pct"] == "20"
    assert row["working_floor_roi_pct"] == "10"
    assert row["exit_floor_roi_pct"] == "0"
    assert row["emergency_floor_roi_pct"] == "-5"


def test_o_ui_policy_update_submission_writes_f_inbox_event(tmp_path: Path) -> None:
    _write_f_contract_rows(
        tmp_path,
        "feeder_backtest_policy_live",
        [
            {
                "observed_utc": "2026-04-10T14:40:00Z",
                "policy_id": "f_backtest_policy_v1",
                "policy_version": "1.0",
                "policy_status": "active",
                "minimum_expected_profit_gbp": "100",
                "entry_target_roi_pct": "20",
                "working_floor_roi_pct": "10",
                "exit_floor_roi_pct": "0",
                "emergency_floor_roi_pct": "-5",
                "recency_weight_30d": "0.5",
                "recency_weight_90d": "0.3",
                "recency_weight_180d": "0.15",
                "recency_weight_365d": "0.05",
                "ceiling_warn_ratio_30d": "1.25",
                "ceiling_red_ratio_30d": "1.5",
                "ceiling_extreme_ratio_30d": "2",
                "shock_trigger_pct_1d": "20",
                "shared_sales_default_pct": "50",
                "policy_source": "system_default_v1",
                "notes": "",
            }
        ],
    )

    out_row = submit_backtest_policy_update_event(
        root=tmp_path,
        policy_values={
            "minimum_expected_profit_gbp": "120",
            "entry_target_roi_pct": "22",
            "working_floor_roi_pct": "12",
            "exit_floor_roi_pct": "2",
            "emergency_floor_roi_pct": "-3",
        },
        actor="tester",
        source_reference="o_ui_test",
        decision_note="manual operator update",
    )
    inbox_path = tmp_path / get_f_output_contract("feeder_backtest_policy_update_events").rel_path
    inbox_df = pd.read_csv(inbox_path, dtype=str).fillna("")
    assert len(inbox_df.index) == 1
    row = inbox_df.iloc[0]
    assert row["event_id"].startswith("o-ui-f-policy-")
    assert row["policy_id"] == "f_backtest_policy_v1"
    assert row["action"] == "apply"
    assert row["minimum_expected_profit_gbp"] == "120"
    assert row["entry_target_roi_pct"] == "22"
    assert row["working_floor_roi_pct"] == "12"
    assert row["exit_floor_roi_pct"] == "2"
    assert row["emergency_floor_roi_pct"] == "-3"
    assert row["actor"] == "tester"
    assert row["source_reference"] == "o_ui_test"
    assert row["decision_note"] == "manual operator update"
    assert out_row["event_id"] == row["event_id"]


def test_o_ui_policy_value_validation_handles_empty_and_invalid_inputs() -> None:
    _, errors = validate_backtest_policy_values(
        {
            "minimum_expected_profit_gbp": "",
            "entry_target_roi_pct": "abc",
            "working_floor_roi_pct": "10",
            "exit_floor_roi_pct": "0",
            "emergency_floor_roi_pct": "-5",
        }
    )
    assert len(errors) >= 2
    assert any("minimum_expected_profit_gbp is required" in error for error in errors)
    assert any("entry_target_roi_pct must be numeric" in error for error in errors)

    _, ordering_errors = validate_backtest_policy_values(
        {
            "minimum_expected_profit_gbp": "100",
            "entry_target_roi_pct": "10",
            "working_floor_roi_pct": "20",
            "exit_floor_roi_pct": "5",
            "emergency_floor_roi_pct": "0",
        }
    )
    assert len(ordering_errors) == 1
    assert "ROI ordering must be" in ordering_errors[0]


def test_o_ui_calibration_loader_reads_latest_and_selects_flagged_rows(tmp_path: Path) -> None:
    cal_path = tmp_path / "out" / "analysis_reports" / "f_backtest_calibration_set_latest.csv"
    cal_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "seller_sku": "SKU-A",
                "asin": "ASIN-A",
                "recommendation": "Normal fit",
                "amazon_risk_level": "low",
                "market_viability_score": "80",
                "exit_risk_score": "20",
                "calibration_review_flag": "0",
                "calibration_review_reason": "",
            },
            {
                "seller_sku": "SKU-B",
                "asin": "ASIN-B",
                "recommendation": "Exit-only",
                "amazon_risk_level": "critical",
                "market_viability_score": "42",
                "exit_risk_score": "70",
                "calibration_review_flag": "1",
                "calibration_review_reason": "critical_amazon_recommendation_mismatch",
            },
        ]
    ).to_csv(cal_path, index=False)

    cal_df = load_backtest_calibration_df(root=tmp_path)
    assert len(cal_df.index) == 2
    flagged_df = select_flagged_backtest_calibration_rows(cal_df)
    assert len(flagged_df.index) == 1
    flagged_row = flagged_df.iloc[0]
    assert flagged_row["seller_sku"] == "SKU-B"
    assert flagged_row["calibration_review_flag"] == "1"


def test_o_ui_calibration_loader_handles_missing_file_gracefully(tmp_path: Path) -> None:
    cal_df = load_backtest_calibration_df(root=tmp_path)
    assert cal_df.empty
    assert set(cal_df.columns) == {
        "seller_sku",
        "asin",
        "recommendation",
        "amazon_risk_level",
        "market_viability_score",
        "exit_risk_score",
        "calibration_review_flag",
        "calibration_review_reason",
    }
