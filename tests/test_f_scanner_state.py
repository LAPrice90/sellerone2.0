from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._scanner_state import (
    AUTH_STATE_BBP_AUTHENTICATED,
    AUTH_STATE_BBP_LOGIN_REQUIRED,
    AUTH_STATE_DASHBOARD_LOGIN_REQUIRED,
    AUTH_STATE_LOGGED_IN,
    AUTH_STATE_LOGIN_REQUIRED,
    AUTH_STATE_SELLER_CENTRAL_ELIGIBILITY_LOGIN_REQUIRED,
    BROWSER_STATE_HIDDEN,
    BROWSER_STATE_VISIBLE,
    DASHBOARD_DELIVERY_CLASSIFICATION_LIKELY_SEPARATE,
    DASHBOARD_YES_NO_LIKELY,
    DASHBOARD_YES_NO_MISSING,
    DASHBOARD_YES_NO_NO,
    DASHBOARD_YES_NO_YES,
    ROW_QUEUE_NEEDS_LOGIN_RESCAN,
    ROW_QUEUE_NEEDS_YESNO_RESCAN,
    active_row_queue_state,
    active_row_is_rescan_retry,
    active_row_queue_priority,
    auth_state_from_log_text,
    browser_state_for_auth_state,
    dashboard_delivery_classification,
    dashboard_separate_delivery_required,
    dashboard_yes_no_state,
    has_binary_dashboard_yes_no,
    has_required_dashboard_signal,
)


def test_scanner_state_maps_auth_logs_to_binary_browser_state() -> None:
    assert auth_state_from_log_text("BBP login skipped: already authenticated.") == AUTH_STATE_BBP_AUTHENTICATED
    assert browser_state_for_auth_state(AUTH_STATE_LOGGED_IN) == BROWSER_STATE_HIDDEN
    assert browser_state_for_auth_state(AUTH_STATE_BBP_AUTHENTICATED) == BROWSER_STATE_HIDDEN
    assert auth_state_from_log_text("[Profile5] Dashboard yes/no => LIKELY") == AUTH_STATE_BBP_AUTHENTICATED

    assert auth_state_from_log_text("{'error': 'BBP_LOGIN_REQUIRED'}") == AUTH_STATE_BBP_LOGIN_REQUIRED
    assert auth_state_from_log_text("No BBP iframe") == ""
    assert browser_state_for_auth_state(AUTH_STATE_LOGIN_REQUIRED) == BROWSER_STATE_VISIBLE
    assert browser_state_for_auth_state(AUTH_STATE_BBP_LOGIN_REQUIRED) == BROWSER_STATE_VISIBLE
    assert browser_state_for_auth_state(AUTH_STATE_DASHBOARD_LOGIN_REQUIRED) == BROWSER_STATE_VISIBLE
    assert auth_state_from_log_text("F061_LOGIN_OPTION_DETECTED selector:#loginEmail") == AUTH_STATE_BBP_LOGIN_REQUIRED
    assert auth_state_from_log_text("F061_LOGIN_OPTION_DETECTED login_mode_missing_bbp_iframe") == ""
    assert auth_state_from_log_text("BBP/Amazon login option detected") == ""
    assert auth_state_from_log_text("BBP login option detected") == AUTH_STATE_BBP_LOGIN_REQUIRED
    assert (
        auth_state_from_log_text("SELLER_CENTRAL_LOGIN_RECOVERY status=waiting_for_code")
        == AUTH_STATE_SELLER_CENTRAL_ELIGIBILITY_LOGIN_REQUIRED
    )
    assert browser_state_for_auth_state(AUTH_STATE_SELLER_CENTRAL_ELIGIBILITY_LOGIN_REQUIRED) == BROWSER_STATE_VISIBLE

    mixed_log = "\n".join(
        [
            "BBP login skipped: already authenticated.",
            "[Profile5] Dashboard yes/no ignored non yes/no value => LOGIN",
        ]
    )
    assert auth_state_from_log_text(mixed_log) == AUTH_STATE_DASHBOARD_LOGIN_REQUIRED

    authenticated_dashboard_missing_log = "\n".join(
        [
            "Submitted BBP login.",
            "[Profile5] cost => 7.77",
            "[Profile5] Dashboard yes/no raw LOGIN ignored after authenticated cost field; treating dashboard as missing.",
        ]
    )
    assert auth_state_from_log_text(authenticated_dashboard_missing_log) == AUTH_STATE_DASHBOARD_LOGIN_REQUIRED


def test_scanner_state_maps_dashboard_values_to_required_signal_and_delivery_classification() -> None:
    assert dashboard_yes_no_state("YES") == DASHBOARD_YES_NO_YES
    assert dashboard_yes_no_state("no") == DASHBOARD_YES_NO_NO
    assert dashboard_yes_no_state("LIKELY") == DASHBOARD_YES_NO_LIKELY
    assert dashboard_yes_no_state("") == DASHBOARD_YES_NO_MISSING
    assert has_binary_dashboard_yes_no("LIKELY") is False
    assert has_required_dashboard_signal("LIKELY") is True
    assert dashboard_separate_delivery_required("LIKELY") is True
    assert dashboard_delivery_classification("LIKELY") == DASHBOARD_DELIVERY_CLASSIFICATION_LIKELY_SEPARATE
    assert dashboard_delivery_classification("YES") == ""


def test_scanner_state_splits_login_rescan_from_yesno_rescan() -> None:
    assert (
        active_row_queue_state(
            {
                "scan_status": "login_backtrack_pending",
                "scan_reason": "login_backtrack_required",
                "completion_block_reason": "bbp_login_required",
            }
        )
        == ROW_QUEUE_NEEDS_LOGIN_RESCAN
    )

    assert (
        active_row_queue_state(
            {
                "scan_status": "login_backtrack_pending",
                "scan_reason": "login_backtrack_required",
                "completion_block_reason": "dashboard_yes_no_backtrack_required",
            }
        )
        == ROW_QUEUE_NEEDS_YESNO_RESCAN
    )

    assert (
        active_row_queue_state(
            {
                "scan_status": "login_backtrack_pending",
                "scan_reason": "login_backtrack_required",
                "completion_block_reason": "seller_central_eligibility_login_required",
            }
        )
        == ROW_QUEUE_NEEDS_LOGIN_RESCAN
    )


def test_scanner_state_prioritises_rescan_retry_before_fresh_pending() -> None:
    login_retry = {
        "scan_status": "login_backtrack_pending",
        "scan_reason": "login_backtrack_required",
        "completion_block_reason": "bbp_login_required",
    }
    yesno_retry = {
        "scan_status": "login_backtrack_pending",
        "scan_reason": "login_backtrack_required",
        "completion_block_reason": "dashboard_yes_no_backtrack_required",
    }
    rescan_retry = {
        "scan_status": "pending",
        "scan_reason": "rescan_retry_required",
        "completion_block_reason": "rescan_retry_pending",
        "last_attempt_utc": "2026-05-21T09:22:47Z",
    }
    fresh_pending = {
        "scan_status": "pending",
        "scan_reason": "",
        "completion_block_reason": "",
        "last_attempt_utc": "",
    }

    assert active_row_queue_state(rescan_retry) == "PENDING"
    assert active_row_is_rescan_retry(rescan_retry) is True
    assert active_row_is_rescan_retry(fresh_pending) is False
    assert active_row_queue_priority(login_retry) < active_row_queue_priority(yesno_retry)
    assert active_row_queue_priority(yesno_retry) < active_row_queue_priority(rescan_retry)
    assert active_row_queue_priority(rescan_retry) < active_row_queue_priority(fresh_pending)
