from __future__ import annotations

from typing import Mapping


AUTH_STATE_LOGGED_IN = "LOGGED_IN"
AUTH_STATE_LOGIN_REQUIRED = "LOGIN_REQUIRED"
AUTH_STATE_BBP_LOGIN_REQUIRED = "BBP_LOGIN_REQUIRED"
AUTH_STATE_DASHBOARD_LOGIN_REQUIRED = "AMAZON_DASHBOARD_LOGIN_REQUIRED"
AUTH_STATE_SELLER_CENTRAL_ELIGIBILITY_LOGIN_REQUIRED = "SELLER_CENTRAL_ELIGIBILITY_LOGIN_REQUIRED"
AUTH_STATES_REQUIRING_VISIBLE = {
    AUTH_STATE_LOGIN_REQUIRED,
    AUTH_STATE_BBP_LOGIN_REQUIRED,
    AUTH_STATE_DASHBOARD_LOGIN_REQUIRED,
    AUTH_STATE_SELLER_CENTRAL_ELIGIBILITY_LOGIN_REQUIRED,
}

BROWSER_STATE_HIDDEN = "HIDDEN"
BROWSER_STATE_VISIBLE = "VISIBLE"

DASHBOARD_YES_NO_YES = "YES"
DASHBOARD_YES_NO_NO = "NO"
DASHBOARD_YES_NO_LIKELY = "LIKELY"
DASHBOARD_YES_NO_MISSING = "MISSING"
DASHBOARD_DELIVERY_CLASSIFICATION_LIKELY_SEPARATE = "LIKELY_SELLABLE_HAZMAT_SEPARATE_DELIVERY"

ROW_QUEUE_NEEDS_LOGIN_RESCAN = "NEEDS_LOGIN_RESCAN"
ROW_QUEUE_NEEDS_YESNO_RESCAN = "NEEDS_YESNO_RESCAN"
ROW_QUEUE_PENDING = "PENDING"
ROW_QUEUE_DONE = "DONE"
ROW_QUEUE_UNRESOLVED = "UNRESOLVED"
RESCAN_RETRY_REASON = "rescan_retry_required"
RESCAN_RETRY_BLOCK_REASON = "rescan_retry_pending"

AUTH_CONFIRMED_TOKENS = (
    "bbp login skipped: already authenticated",
    "dashboard yes/no => yes",
    "dashboard yes/no => no",
    "dashboard yes/no => likely",
)

BBP_AUTH_REQUIRED_TOKENS = (
    "f061_login_option_detected selector:#loginemail",
    "f061_login_option_detected selector:#loginpassword",
    "f061_login_option_detected selector:#loginbtn",
    "f061_login_option_detected body_text:bbp_login_challenge",
    "bbp login option detected",
    "bbp manual login required",
    "manual login required",
    "bbp_login_required",
    "login_required",
    "blocked_or_signin",
    "captcha",
)

DASHBOARD_AUTH_REQUIRED_TOKENS = (
    "dashboard yes/no raw login ignored after authenticated cost field",
    "dashboard yes/no ignored non yes/no value => login",
    "dashboard yes/no ignored non yes/no/likely value => login",
)

SELLER_CENTRAL_AUTH_REQUIRED_TOKENS = (
    "seller_central_eligibility_login_required",
    "seller central eligibility login required",
    "seller_central_login_recovery status=disabled",
    "seller_central_login_recovery status=waiting_for_code",
    "seller_central_login_recovery status=blocked",
)


def _text(value: object) -> str:
    return str(value or "").strip()


def _lower(value: object) -> str:
    return _text(value).lower()


def auth_state_from_log_text(text: object) -> str:
    state = ""
    for line in str(text or "").splitlines():
        lower = line.lower()
        if any(token in lower for token in AUTH_CONFIRMED_TOKENS):
            state = AUTH_STATE_LOGGED_IN
        if any(token in lower for token in DASHBOARD_AUTH_REQUIRED_TOKENS):
            state = AUTH_STATE_DASHBOARD_LOGIN_REQUIRED
        if any(token in lower for token in BBP_AUTH_REQUIRED_TOKENS):
            state = AUTH_STATE_BBP_LOGIN_REQUIRED
        if any(token in lower for token in SELLER_CENTRAL_AUTH_REQUIRED_TOKENS):
            state = AUTH_STATE_SELLER_CENTRAL_ELIGIBILITY_LOGIN_REQUIRED
    return state


def browser_state_for_auth_state(auth_state: str) -> str:
    if auth_state == AUTH_STATE_LOGGED_IN:
        return BROWSER_STATE_HIDDEN
    if auth_state in AUTH_STATES_REQUIRING_VISIBLE:
        return BROWSER_STATE_VISIBLE
    return ""


def browser_visibility_value(browser_state: str) -> str:
    if browser_state == BROWSER_STATE_HIDDEN:
        return "hidden"
    if browser_state == BROWSER_STATE_VISIBLE:
        return "visible"
    return ""


def auth_state_for_browser_visibility(visibility: str) -> str:
    normalized = _lower(visibility)
    if normalized == "hidden":
        return AUTH_STATE_LOGGED_IN
    if normalized == "visible":
        return AUTH_STATE_LOGIN_REQUIRED
    return ""


def dashboard_yes_no_state(value: object) -> str:
    normalized = _text(value).upper()
    if normalized == DASHBOARD_YES_NO_YES:
        return DASHBOARD_YES_NO_YES
    if normalized == DASHBOARD_YES_NO_NO:
        return DASHBOARD_YES_NO_NO
    if normalized == DASHBOARD_YES_NO_LIKELY:
        return DASHBOARD_YES_NO_LIKELY
    return DASHBOARD_YES_NO_MISSING


def has_binary_dashboard_yes_no(value: object) -> bool:
    return dashboard_yes_no_state(value) in {DASHBOARD_YES_NO_YES, DASHBOARD_YES_NO_NO}


def has_required_dashboard_signal(value: object) -> bool:
    return dashboard_yes_no_state(value) in {
        DASHBOARD_YES_NO_YES,
        DASHBOARD_YES_NO_NO,
        DASHBOARD_YES_NO_LIKELY,
    }


def dashboard_separate_delivery_required(value: object) -> bool:
    return dashboard_yes_no_state(value) == DASHBOARD_YES_NO_LIKELY


def dashboard_delivery_classification(value: object) -> str:
    if dashboard_separate_delivery_required(value):
        return DASHBOARD_DELIVERY_CLASSIFICATION_LIKELY_SEPARATE
    return ""


def active_row_queue_state(row: Mapping[str, object]) -> str:
    scan_status = _lower(row.get("scan_status", ""))
    block_reason = _lower(row.get("completion_block_reason", ""))
    scan_reason = _lower(row.get("scan_reason", ""))
    if scan_status == "dashboard_yes_no_unresolved" or "dashboard_yes_no_backtrack_unresolved" in block_reason:
        return ROW_QUEUE_UNRESOLVED
    if scan_status in {"completed", "done"}:
        return ROW_QUEUE_DONE
    if scan_status in {"login_backtrack_pending", "login_backtrack_running"}:
        if "seller_central_eligibility_login" in block_reason:
            return ROW_QUEUE_NEEDS_LOGIN_RESCAN
        if "dashboard_yes_no" in block_reason:
            return ROW_QUEUE_NEEDS_YESNO_RESCAN
        if block_reason in {"bbp_login_required", "login_required"} or "bbp_login_required" in block_reason:
            return ROW_QUEUE_NEEDS_LOGIN_RESCAN
        if scan_reason == "login_backtrack_required":
            return ROW_QUEUE_NEEDS_LOGIN_RESCAN
        return ROW_QUEUE_NEEDS_YESNO_RESCAN
    return ROW_QUEUE_PENDING if scan_status == "pending" else ""


def active_row_is_rescan_retry(row: Mapping[str, object]) -> bool:
    scan_status = _lower(row.get("scan_status", ""))
    block_reason = _lower(row.get("completion_block_reason", ""))
    scan_reason = _lower(row.get("scan_reason", ""))
    return scan_status == "pending" and (
        scan_reason == RESCAN_RETRY_REASON
        or block_reason == RESCAN_RETRY_BLOCK_REASON
    )


def active_row_requires_visible_browser(row: Mapping[str, object]) -> bool:
    return active_row_queue_state(row) == ROW_QUEUE_NEEDS_LOGIN_RESCAN


def active_row_queue_priority(row: Mapping[str, object]) -> int:
    state = active_row_queue_state(row)
    if state == ROW_QUEUE_NEEDS_LOGIN_RESCAN:
        return 0
    if state == ROW_QUEUE_NEEDS_YESNO_RESCAN:
        return 1
    if active_row_is_rescan_retry(row):
        return 2
    if state == ROW_QUEUE_PENDING:
        return 3
    return 9
