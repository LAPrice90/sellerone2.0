from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.flows.F.login_controller import (
    LoginControllerPaths,
    LoginControllerRequestPaths,
    BrowserSessionDurabilityPaths,
    build_browser_session_durability_report,
    build_login_controller_report,
    login_controller_request_active,
    read_login_controller_request,
    record_browser_session_durability_event,
    record_browser_session_page_pull,
    record_login_controller_attempt,
    write_login_controller_request,
)


def _paths(tmp_path: Path) -> LoginControllerPaths:
    live_dir = tmp_path / "live"
    return LoginControllerPaths(
        live_dir=live_dir,
        attempts_path=live_dir / "f_login_controller_attempts.csv",
        state_path=live_dir / "f_login_controller_state.json",
        report_path=live_dir / "f_login_controller_report_latest.md",
    )


def _session_paths(tmp_path: Path) -> BrowserSessionDurabilityPaths:
    live_dir = tmp_path / "live"
    return BrowserSessionDurabilityPaths(
        live_dir=live_dir,
        events_path=live_dir / "f_browser_session_events.csv",
        state_path=live_dir / "f_browser_session_durability_state.json",
        report_path=live_dir / "f_browser_session_durability_report_latest.md",
    )


def _request_paths(tmp_path: Path) -> LoginControllerRequestPaths:
    live_dir = tmp_path / "live"
    return LoginControllerRequestPaths(
        live_dir=live_dir,
        request_path=live_dir / "f061_login_mode.requested",
    )


def test_login_controller_attempted_credentials_are_not_proof_and_secrets_are_redacted(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    record_login_controller_attempt(
        context="dashboard_yes_no_login",
        page_type="seller_central_signin",
        action="seller_central_submit_credentials",
        status="attempted",
        reason="credentials_submitted",
        attempted=True,
        source="test",
        notes="email=user@example.com;otp=123456;password=secret-password",
        extra_secrets=("secret-password",),
        paths=paths,
    )

    with paths.attempts_path.open("r", newline="", encoding="utf-8") as handle:
        row = list(csv.DictReader(handle))[-1]
    state = json.loads(paths.state_path.read_text(encoding="utf-8"))
    report = paths.report_path.read_text(encoding="utf-8")

    assert row["proof_status"] == "attempted_not_proved"
    assert state["status"] == "attempted_not_proved"
    assert "user@example.com" not in report
    assert "123456" not in report
    assert "secret-password" not in report
    assert "<redacted-email>" in row["notes"]
    assert "<redacted-code>" in row["notes"]


def test_login_controller_dashboard_yes_no_is_seller_central_proof(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    row = record_login_controller_attempt(
        context="dashboard_yes_no_login",
        page_type="authenticated",
        action="seller_central_prove_dashboard",
        status="succeeded",
        reason="eligibility_signal_visible",
        dashboard_yes_no="YES",
        succeeded=True,
        source="test",
        paths=paths,
    )
    state = json.loads(paths.state_path.read_text(encoding="utf-8"))

    assert row["proof_status"] == "dashboard_yes_no_proved"
    assert state["dashboard_proved"] is True


def test_login_controller_manual_challenge_and_waiting_code_are_visible_statuses(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    waiting = record_login_controller_attempt(
        context="dashboard_yes_no_login",
        page_type="seller_central_otp",
        action="seller_central_wait_for_code",
        status="waiting_for_code",
        reason="otp_page_detected",
        paths=paths,
    )
    challenge = record_login_controller_attempt(
        context="dashboard_yes_no_login",
        page_type="manual_challenge",
        action="manual_fallback_required",
        status="blocked",
        reason="manual_challenge_required",
        paths=paths,
    )
    report = build_login_controller_report(paths)

    assert waiting["proof_status"] == "waiting_for_code"
    assert challenge["proof_status"] == "manual_challenge_required"
    assert "Amazon showed a manual challenge" in report


def test_login_controller_owns_login_mode_request_file(tmp_path: Path) -> None:
    paths = _request_paths(tmp_path)

    request = write_login_controller_request(
        requested_by="operator_ui",
        supplier_id="stax",
        run_id="fpm_stax_20260507T151124Z",
        hold_seconds=45,
        reason="operator_login_button",
        observed_utc="2026-05-09T09:15:00Z",
        paths=paths,
    )
    read_back = read_login_controller_request(paths)
    text = paths.request_path.read_text(encoding="ascii")

    assert request["status"] == "requested"
    assert request["controller_owner"] == "F_LOGIN_CONTROLLER_REWRITE_V1"
    assert login_controller_request_active(read_back) is True
    assert "controller_owner=F_LOGIN_CONTROLLER_REWRITE_V1" in text
    assert "requested_by=operator_ui" in text


def test_browser_session_durability_logs_reason_labels_and_redacts_secrets(tmp_path: Path) -> None:
    paths = _session_paths(tmp_path)

    row = record_browser_session_durability_event(
        event_type="seller_central_login",
        page_type="seller_central_signin",
        status="blocked",
        reason="signin_or_passkey_page_after_credentials",
        result="blocked",
        blocker="signin_or_passkey_page_after_credentials",
        source="test",
        notes=(
            "email=user@example.com;otp=123456;password=secret-password;"
            r"path=C:\Users\Luke\Desktop\SellerOne 2.0\secrets\profile"
        ),
        extra_secrets=("secret-password",),
        paths=paths,
    )

    with paths.events_path.open("r", newline="", encoding="utf-8") as handle:
        event = list(csv.DictReader(handle))[-1]
    state = json.loads(paths.state_path.read_text(encoding="utf-8"))
    report = paths.report_path.read_text(encoding="utf-8")

    assert row["reason_code"] == "unknown"
    assert event["reason"] == "signin_or_passkey_page_after_credentials"
    assert state["latest_reason_code"] == "unknown"
    assert "signin_or_passkey_page_after_credentials" in report
    assert "user@example.com" not in report
    assert "123456" not in report
    assert "secret-password" not in report
    assert "C:\\Users\\Luke" not in report


def test_browser_session_page_pull_records_current_otp_state_once(tmp_path: Path) -> None:
    paths = _session_paths(tmp_path)
    page_pull = {
        "observed_utc": "2026-06-07T11:19:29Z",
        "context": "dashboard_yes_no_login",
        "reason": "otp_page_detected",
        "page_state": "otp_code_page",
        "page_hint": "sellercentral_url|signin_url|otp_field|otp_text",
        "body": "two-step verification enter the code 123456",
    }

    row = record_browser_session_page_pull(page_pull, paths=paths)
    duplicate = record_browser_session_page_pull(page_pull, paths=paths)

    with paths.events_path.open("r", newline="", encoding="utf-8") as handle:
        events = list(csv.DictReader(handle))
    state = json.loads(paths.state_path.read_text(encoding="utf-8"))
    report = paths.report_path.read_text(encoding="utf-8")

    assert len(events) == 1
    assert row == duplicate
    assert row["observed_utc"] == "2026-06-07T11:19:29Z"
    assert row["page_type"] == "seller_central_otp"
    assert row["status"] == "waiting_for_code"
    assert row["reason_code"] == "amazon_forced_mfa"
    assert state["latest_reason_code"] == "amazon_forced_mfa"
    assert "Amazon asked for multi-factor verification" in report
    assert "123456" not in report


def test_browser_session_report_names_approved_scanner_profile_without_raw_path(monkeypatch, tmp_path: Path) -> None:
    paths = _session_paths(tmp_path)
    monkeypatch.setenv("F061_BBP_USER_DATA_DIR", r"C:\Users\Luke\AppData\Local\Chrome_UC136")
    monkeypatch.setenv("F061_BBP_PROFILE_DIR", "Profile 2")

    row = record_browser_session_durability_event(
        event_type="seller_central_login",
        page_type="authenticated",
        status="succeeded",
        reason="dashboard_yes_no_visible",
        result="succeeded",
        auth_state="logged_in",
        source="test",
        paths=paths,
    )
    state = json.loads(paths.state_path.read_text(encoding="utf-8"))
    report = paths.report_path.read_text(encoding="utf-8")

    assert row["profile_state"] == "approved"
    assert row["cookie_state"] == "present"
    assert state["profile_source"] == "scanner-owned F061/BBP Chrome profile"
    assert state["profile_state"] == "approved"
    assert state["profile_path_stable"] == "yes"
    assert state["cookie_state"] == "present"
    assert state["reset_risk"] == "low"
    assert "Profile source: scanner-owned F061/BBP Chrome profile" in report
    assert "Profile state: approved" in report
    assert "Profile path stable: yes" in report
    assert "Cookie/session state: present" in report
    assert "C:\\Users\\Luke" not in report


def test_browser_session_report_blocks_temporary_profile_fallback_when_auto_login_available(monkeypatch, tmp_path: Path) -> None:
    paths = _session_paths(tmp_path)
    monkeypatch.setenv("F061_BBP_USER_DATA_DIR", r"C:\Users\Luke\AppData\Local\Temp\scoped_dir123")
    monkeypatch.setenv("F061_BBP_PROFILE_DIR", "Default")

    row = record_browser_session_durability_event(
        event_type="seller_central_login",
        page_type="seller_central_signin",
        status="blocked",
        reason="temporary_profile",
        result="blocked",
        auth_state="login_required",
        source="test",
        paths=paths,
    )
    state = json.loads(paths.state_path.read_text(encoding="utf-8"))
    report = paths.report_path.read_text(encoding="utf-8")

    assert row["reason_code"] == "temporary_profile"
    assert row["profile_state"] == "temporary"
    assert row["cookie_state"] == "reset-risk"
    assert state["profile_state"] == "temporary"
    assert state["profile_path_stable"] == "no"
    assert state["cookie_state"] == "reset-risk"
    assert state["reset_risk"] == "reset-risk"
    assert "Profile state: temporary" in report
    assert "Profile path stable: no" in report
    assert "Reset risk: reset-risk" in report
    assert "scoped_dir123" not in report


def test_browser_session_report_includes_profile_proof_without_events(monkeypatch, tmp_path: Path) -> None:
    paths = _session_paths(tmp_path)
    monkeypatch.setenv("F061_BBP_USER_DATA_DIR", r"C:\Users\Luke\AppData\Local\Chrome_UC136")
    monkeypatch.setenv("F061_BBP_PROFILE_DIR", "Profile 2")

    report = build_browser_session_durability_report(paths)

    assert "No browser-session durability events have been recorded yet." in report
    assert "Profile source: scanner-owned F061/BBP Chrome profile" in report
    assert "Profile state: approved" in report
    assert "Profile path stable: yes" in report
    assert "C:\\Users\\Luke" not in report
