from __future__ import annotations

import csv
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping


CONTROLLER_VERSION = "F_LOGIN_CONTROLLER_REWRITE_V1"
ATTEMPTS_NAME = "f_login_controller_attempts.csv"
STATE_NAME = "f_login_controller_state.json"
REPORT_NAME = "f_login_controller_report_latest.md"
SESSION_EVENTS_NAME = "f_browser_session_events.csv"
SESSION_STATE_NAME = "f_browser_session_durability_state.json"
SESSION_REPORT_NAME = "f_browser_session_durability_report_latest.md"
LOGIN_MODE_REQUEST_NAME = "f061_login_mode.requested"
LOGIN_MODE_INACTIVE_STATUSES = {"canceled", "cancelled", "completed", "consumed", "drained"}
APPROVED_BBP_PROFILE_SOURCE = "scanner-owned F061/BBP Chrome profile"
APPROVED_BBP_USER_DATA_DIR = r"C:\Users\Luke\AppData\Local\Chrome_UC136"
APPROVED_BBP_PROFILE_DIR = "Profile 2"
TEMP_PROFILE_MARKERS = ("\\temp\\", "\\tmp\\", "\\scoped_dir", "\\temporary", "temp_profile", "temporary_profile")

ATTEMPT_COLUMNS = [
    "observed_utc",
    "controller_version",
    "context",
    "page_type",
    "action",
    "status",
    "reason",
    "proof_status",
    "dashboard_yes_no",
    "attempted_flag",
    "succeeded_flag",
    "manual_challenge_flag",
    "code_seen_flag",
    "fresh_code_flag",
    "blocked_reason",
    "source",
    "notes",
]
SESSION_EVENT_COLUMNS = [
    "observed_utc",
    "controller_version",
    "event_type",
    "page_type",
    "status",
    "reason",
    "reason_code",
    "profile_state",
    "cookie_state",
    "auth_state",
    "result",
    "blocker",
    "source",
    "notes",
]

SELLER_CENTRAL_PAGE_TYPES = {
    "seller_central_signin",
    "seller_central_otp",
    "manual_challenge",
    "authenticated",
    "seller_central_unknown",
}
PROVED_DASHBOARD_VALUES = {"YES", "NO", "LIKELY"}
WAITING_STATUSES = {"waiting_for_code", "expired"}
BLOCKED_STATUSES = {"blocked", "disabled", "failed", "missing_secret_file", "missing_credentials"}


@dataclass(frozen=True)
class LoginControllerPaths:
    live_dir: Path
    attempts_path: Path
    state_path: Path
    report_path: Path


@dataclass(frozen=True)
class BrowserSessionDurabilityPaths:
    live_dir: Path
    events_path: Path
    state_path: Path
    report_path: Path


@dataclass(frozen=True)
class LoginControllerRequestPaths:
    live_dir: Path
    request_path: Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_login_controller_paths(*, live_dir: str | Path | None = None) -> LoginControllerPaths:
    raw_dir = str(live_dir or os.getenv("F_LOGIN_CONTROLLER_LIVE_DIR", "")).strip()
    resolved_live_dir = (
        Path(raw_dir)
        if raw_dir
        else _repo_root() / "out" / "systems" / "F" / "price_list_manager" / "live"
    )
    return LoginControllerPaths(
        live_dir=resolved_live_dir,
        attempts_path=resolved_live_dir / ATTEMPTS_NAME,
        state_path=resolved_live_dir / STATE_NAME,
        report_path=resolved_live_dir / REPORT_NAME,
    )


def default_browser_session_durability_paths(
    *,
    live_dir: str | Path | None = None,
) -> BrowserSessionDurabilityPaths:
    raw_dir = str(live_dir or os.getenv("F_LOGIN_CONTROLLER_LIVE_DIR", "")).strip()
    resolved_live_dir = (
        Path(raw_dir)
        if raw_dir
        else _repo_root() / "out" / "systems" / "F" / "price_list_manager" / "live"
    )
    return BrowserSessionDurabilityPaths(
        live_dir=resolved_live_dir,
        events_path=resolved_live_dir / SESSION_EVENTS_NAME,
        state_path=resolved_live_dir / SESSION_STATE_NAME,
        report_path=resolved_live_dir / SESSION_REPORT_NAME,
    )


def default_login_controller_request_paths(*, live_dir: str | Path | None = None) -> LoginControllerRequestPaths:
    raw_dir = str(live_dir or os.getenv("F_LOGIN_CONTROLLER_LIVE_DIR", "")).strip()
    resolved_live_dir = (
        Path(raw_dir)
        if raw_dir
        else _repo_root() / "out" / "systems" / "F" / "price_list_manager" / "live"
    )
    return LoginControllerRequestPaths(
        live_dir=resolved_live_dir,
        request_path=resolved_live_dir / LOGIN_MODE_REQUEST_NAME,
    )


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _clean_status(value: object) -> str:
    return _normalize_text(value).lower().replace(" ", "_")


def _path_leaf(value: object) -> str:
    text = _normalize_text(value).replace("/", "\\").rstrip("\\")
    if not text:
        return ""
    return text.split("\\")[-1]


def _redacted_profile_descriptor(user_data_dir: object, profile_dir: object) -> str:
    if _profile_is_temporary(user_data_dir, profile_dir):
        return "<redacted-temporary-profile>"
    user_leaf = _path_leaf(user_data_dir)
    profile = _normalize_text(profile_dir)
    if not user_leaf and not profile:
        return "unknown"
    if not user_leaf:
        return f"<redacted-user-data>\\{profile}"
    if not profile:
        return f"<redacted-local-profile-root>\\{user_leaf}"
    return f"<redacted-local-profile-root>\\{user_leaf}\\{profile}"


def _profile_is_temporary(user_data_dir: object, profile_dir: object) -> bool:
    text = f"{_normalize_text(user_data_dir)}\\{_normalize_text(profile_dir)}".lower().replace("/", "\\")
    return any(marker in text for marker in TEMP_PROFILE_MARKERS)


def _browser_profile_state(user_data_dir: object = "", profile_dir: object = "") -> str:
    user_data = _normalize_text(user_data_dir)
    profile = _normalize_text(profile_dir)
    if not user_data and not profile:
        return "unknown"
    if _profile_is_temporary(user_data, profile):
        return "temporary"
    if user_data.lower().rstrip("\\/") == APPROVED_BBP_USER_DATA_DIR.lower().rstrip("\\/") and profile == APPROVED_BBP_PROFILE_DIR:
        return "approved"
    return "mismatch"


def _browser_cookie_state(*, reason_code: str = "", auth_state: str = "", profile_state: str = "") -> str:
    reason = _clean_status(reason_code)
    auth = _clean_status(auth_state)
    profile = _clean_status(profile_state)
    if reason == "cookie_missing":
        return "missing"
    if reason == "cookie_expired":
        return "expired"
    if profile in {"temporary", "mismatch"}:
        return "reset-risk"
    if auth in {"logged_in", "authenticated"}:
        return "present"
    return "unknown"


def browser_session_profile_proof(
    *,
    user_data_dir: object = "",
    profile_dir: object = "",
) -> dict[str, str]:
    user_data = _normalize_text(user_data_dir) or _normalize_text(os.environ.get("F061_BBP_USER_DATA_DIR", "")) or APPROVED_BBP_USER_DATA_DIR
    profile = _normalize_text(profile_dir) or _normalize_text(os.environ.get("F061_BBP_PROFILE_DIR", "")) or APPROVED_BBP_PROFILE_DIR
    profile_state = _browser_profile_state(user_data, profile)
    return {
        "profile_source": APPROVED_BBP_PROFILE_SOURCE,
        "profile_descriptor": _redacted_profile_descriptor(user_data, profile),
        "profile_state": profile_state,
        "profile_path_stable": "yes" if profile_state == "approved" else "no" if profile_state in {"mismatch", "temporary"} else "unknown",
        "approved_profile_descriptor": _redacted_profile_descriptor(APPROVED_BBP_USER_DATA_DIR, APPROVED_BBP_PROFILE_DIR),
    }


def browser_session_reset_risk_summary(profile_state: str) -> dict[str, str]:
    profile = _clean_status(profile_state)
    startup = "uses approved scanner-owned F061/BBP Chrome profile when defaults or matching env values are active"
    recovery = "records Seller Central recovery through the scanner-owned page; no separate Chrome workaround is approved here"
    cleanup = "startup/retry cleanup removes Chrome singleton lock files only; it does not delete browser cookies, cache, or profile folders"
    if profile in {"temporary", "mismatch"}:
        risk = "reset-risk"
    elif profile == "approved":
        risk = "low"
    else:
        risk = "unknown"
    return {
        "startup_path": startup,
        "recovery_path": recovery,
        "cleanup_path": cleanup,
        "reset_risk": risk,
    }


def _parse_key_value_control_text(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        clean_key = _normalize_text(key)
        if clean_key:
            result[clean_key] = _normalize_text(value)
    return result


def read_login_controller_request(
    paths: LoginControllerRequestPaths | None = None,
) -> dict[str, str]:
    resolved = paths or default_login_controller_request_paths()
    if not resolved.request_path.exists():
        return {}
    try:
        request = _parse_key_value_control_text(resolved.request_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        request = {}
    request["request_path"] = str(resolved.request_path)
    request["request_exists"] = "1"
    request.setdefault("controller_owner", CONTROLLER_VERSION)
    return request


def login_controller_request_active(request: Mapping[str, object]) -> bool:
    if _normalize_text(request.get("request_exists", "")) != "1":
        return False
    status = _clean_status(request.get("status", "requested"))
    return status not in LOGIN_MODE_INACTIVE_STATUSES


def write_login_controller_request(
    *,
    requested_by: str,
    supplier_id: str = "",
    run_id: str = "",
    status: str = "requested",
    reason: str = "login_controller_request",
    hold_seconds: int = 900,
    observed_utc: str | None = None,
    last_status_note: str = "",
    paths: LoginControllerRequestPaths | None = None,
    existing: Mapping[str, object] | None = None,
) -> dict[str, str]:
    resolved = paths or default_login_controller_request_paths()
    resolved.live_dir.mkdir(parents=True, exist_ok=True)
    observed = _normalize_text(observed_utc) or utc_now_iso()
    previous = {str(key): _normalize_text(value) for key, value in dict(existing or {}).items()}
    request = {
        "requested_utc": previous.get("requested_utc", observed),
        "requested_by": _normalize_text(requested_by) or previous.get("requested_by", "login_controller"),
        "controller_owner": CONTROLLER_VERSION,
        "mode": "login_recovery",
        "supplier_id": _normalize_text(supplier_id) or previous.get("supplier_id", ""),
        "run_id": _normalize_text(run_id) or previous.get("run_id", ""),
        "status": _clean_status(status or previous.get("status", "requested")),
        "hold_seconds": str(max(int(hold_seconds), 1)),
        "reason": _clean_status(reason or previous.get("reason", "login_controller_request")),
        "last_observed_utc": observed,
        "last_status_note": redact_login_controller_text(last_status_note or previous.get("last_status_note", "")),
    }
    ordered_keys = [
        "requested_utc",
        "requested_by",
        "controller_owner",
        "mode",
        "supplier_id",
        "run_id",
        "status",
        "hold_seconds",
        "reason",
        "last_observed_utc",
        "last_status_note",
    ]
    lines = [f"{key}={request[key]}" for key in ordered_keys if _normalize_text(request.get(key, ""))]
    resolved.request_path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
    request["request_path"] = str(resolved.request_path)
    request["request_exists"] = "1"
    return request


def _bool_flag(value: object) -> str:
    return "1" if bool(value) else "0"


def redact_login_controller_text(text: object, *, extra_secrets: Iterable[object] = ()) -> str:
    safe = _normalize_text(text)
    for secret in extra_secrets:
        clean_secret = _normalize_text(secret)
        if clean_secret:
            safe = safe.replace(clean_secret, "<redacted>")
    safe = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "<redacted-email>", safe, flags=re.I)
    safe = re.sub(r"(?<!\d)\d{6}(?!\d)", "<redacted-code>", safe)
    safe = re.sub(r"[A-Za-z]:\\[^;\r\n]+", "<redacted-path>", safe)
    safe = re.sub(
        r"(?i)(cookie|token|credential|password)=([^;\s]+)",
        r"\1=<redacted>",
        safe,
    )
    return safe


def _dashboard_value_from_notes(notes: str) -> str:
    match = re.search(r"(?:dashboard_value|dashboard_yes_no)=([^;\s]+)", notes, flags=re.I)
    if not match:
        return ""
    return _normalize_text(match.group(1)).upper()


def login_controller_proof_status(
    *,
    page_type: str,
    status: str,
    reason: str = "",
    dashboard_yes_no: str = "",
    succeeded: bool = False,
) -> str:
    clean_page = _clean_status(page_type)
    clean_status = _clean_status(status)
    clean_reason = _clean_status(reason)
    clean_dashboard = _normalize_text(dashboard_yes_no).upper()
    if clean_page == "bbp_login" and succeeded and clean_status == "succeeded":
        return "bbp_login_proved"
    if clean_page in SELLER_CENTRAL_PAGE_TYPES and clean_dashboard in PROVED_DASHBOARD_VALUES and succeeded:
        return "dashboard_yes_no_proved"
    if clean_reason == "manual_challenge_required" or clean_page == "manual_challenge":
        return "manual_challenge_required"
    if clean_status in WAITING_STATUSES or "code" in clean_reason:
        return "waiting_for_code"
    if clean_status in BLOCKED_STATUSES or clean_status.startswith("missing_"):
        return "blocked"
    if clean_status == "attempted":
        return "attempted_not_proved"
    if clean_status == "succeeded":
        return "success_needs_dashboard_proof"
    return "observed"


def _read_recent_attempts(path: Path, *, limit: int = 50) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open("r", newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except Exception:
        return []
    clean_rows = [{str(k): _normalize_text(v) for k, v in row.items()} for row in rows]
    return clean_rows[-limit:]


def _write_state(paths: LoginControllerPaths, rows: list[dict[str, str]]) -> None:
    latest = rows[-1] if rows else {}
    proof_counts: dict[str, int] = {}
    for row in rows:
        proof = row.get("proof_status", "") or "unknown"
        proof_counts[proof] = proof_counts.get(proof, 0) + 1
    payload = {
        "updated_utc": utc_now_iso(),
        "controller_version": CONTROLLER_VERSION,
        "latest": latest,
        "recent_attempt_count": len(rows),
        "proof_counts": proof_counts,
        "status": latest.get("proof_status", "no_attempts") if latest else "no_attempts",
        "manual_challenge_required": latest.get("proof_status", "") == "manual_challenge_required",
        "waiting_for_code": latest.get("proof_status", "") == "waiting_for_code",
        "dashboard_proved": latest.get("proof_status", "") == "dashboard_yes_no_proved",
    }
    paths.state_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _plain_status(row: dict[str, str]) -> str:
    proof = row.get("proof_status", "")
    if proof == "dashboard_yes_no_proved":
        return "Seller Central login is proved because Dashboard Yes/No was visible."
    if proof == "bbp_login_proved":
        return "BBP login is proved because the BBP cost field became visible."
    if proof == "waiting_for_code":
        return "F is waiting for a fresh forwarded Seller Central code."
    if proof == "manual_challenge_required":
        return "Amazon showed a manual challenge, so Luke may be needed."
    if proof == "attempted_not_proved":
        return "Credentials were submitted, but that is not proof yet."
    if proof == "blocked":
        return "F is blocked before login proof."
    return "F has login evidence, but it is not final proof yet."


def build_login_controller_report(paths: LoginControllerPaths | None = None) -> str:
    resolved = paths or default_login_controller_paths()
    rows = _read_recent_attempts(resolved.attempts_path, limit=25)
    latest = rows[-1] if rows else {}
    lines = [
        "# F Login Controller Report",
        "",
        f"Updated UTC: {utc_now_iso()}",
        f"Controller: {CONTROLLER_VERSION}",
        "",
    ]
    if not latest:
        lines.extend(
            [
                "## Latest",
                "",
                "No login attempts have been recorded yet.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Latest",
                "",
                _plain_status(latest),
                "",
                f"- Page type: {latest.get('page_type', '')}",
                f"- Action: {latest.get('action', '')}",
                f"- Status: {latest.get('status', '')}",
                f"- Reason: {latest.get('reason', '')}",
                f"- Proof: {latest.get('proof_status', '')}",
                f"- Dashboard Yes/No: {latest.get('dashboard_yes_no', '') or 'not visible yet'}",
                f"- Blocker: {latest.get('blocked_reason', '') or 'none recorded'}",
                "",
            ]
        )

    if rows:
        lines.extend(["## Recent Timeline", ""])
        for row in rows[-10:]:
            lines.append(
                "- "
                f"{row.get('observed_utc', '')}: "
                f"{row.get('page_type', '')} -> {row.get('action', '')} -> "
                f"{row.get('proof_status', '')} ({row.get('reason', '')})"
            )
        lines.append("")

    text = "\n".join(lines).rstrip() + "\n"
    resolved.live_dir.mkdir(parents=True, exist_ok=True)
    resolved.report_path.write_text(text, encoding="utf-8", newline="\n")
    return text


def record_login_controller_attempt(
    *,
    context: str,
    page_type: str,
    action: str,
    status: str,
    reason: str = "",
    dashboard_yes_no: str = "",
    attempted: bool = False,
    succeeded: bool = False,
    manual_challenge: bool = False,
    code_seen: bool = False,
    fresh_code: bool = False,
    blocked_reason: str = "",
    source: str = "",
    notes: str = "",
    paths: LoginControllerPaths | None = None,
    extra_secrets: Iterable[object] = (),
) -> dict[str, str]:
    resolved = paths or default_login_controller_paths()
    resolved.live_dir.mkdir(parents=True, exist_ok=True)
    safe_notes = redact_login_controller_text(notes, extra_secrets=extra_secrets)
    clean_dashboard = _normalize_text(dashboard_yes_no).upper() or _dashboard_value_from_notes(safe_notes)
    proof_status = login_controller_proof_status(
        page_type=page_type,
        status=status,
        reason=reason,
        dashboard_yes_no=clean_dashboard,
        succeeded=succeeded,
    )
    if proof_status == "manual_challenge_required":
        manual_challenge = True
    row = {
        "observed_utc": utc_now_iso(),
        "controller_version": CONTROLLER_VERSION,
        "context": redact_login_controller_text(context, extra_secrets=extra_secrets),
        "page_type": _clean_status(page_type),
        "action": _clean_status(action),
        "status": _clean_status(status),
        "reason": redact_login_controller_text(reason, extra_secrets=extra_secrets),
        "proof_status": proof_status,
        "dashboard_yes_no": clean_dashboard,
        "attempted_flag": _bool_flag(attempted),
        "succeeded_flag": _bool_flag(succeeded),
        "manual_challenge_flag": _bool_flag(manual_challenge),
        "code_seen_flag": _bool_flag(code_seen),
        "fresh_code_flag": _bool_flag(fresh_code),
        "blocked_reason": redact_login_controller_text(blocked_reason, extra_secrets=extra_secrets),
        "source": redact_login_controller_text(source, extra_secrets=extra_secrets),
        "notes": safe_notes,
    }
    write_header = not resolved.attempts_path.exists()
    with resolved.attempts_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ATTEMPT_COLUMNS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(row)
    rows = _read_recent_attempts(resolved.attempts_path, limit=50)
    _write_state(resolved, rows)
    build_login_controller_report(resolved)
    return row


def browser_session_reason_code(*, reason: str, page_type: str = "", notes: str = "") -> str:
    text = " ".join([_clean_status(reason), _clean_status(page_type), _clean_status(notes)])
    if "profile_mismatch" in text or "wrong_profile" in text:
        return "profile_mismatch"
    if "temporary_profile" in text or "temp_profile" in text:
        return "temporary_profile"
    if "cookie_missing" in text or "missing_cookie" in text:
        return "cookie_missing"
    if "cookie_expired" in text or "expired_cookie" in text or "session_expired" in text:
        return "cookie_expired"
    if any(token in text for token in ("manual_challenge", "captcha", "authenticator_only", "passkey_required", "amazon_forced_passkey")):
        return "manual_challenge"
    if any(
        token in text
        for token in (
            "otp_page_detected",
            "waiting_for_code",
            "sms_delivery_option_selected",
            "fresh_code_found",
            "otp_code_submitted",
        )
    ):
        return "amazon_forced_mfa"
    return "unknown"


def _read_recent_session_events(path: Path, *, limit: int = 50) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open("r", newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except Exception:
        return []
    clean_rows = [{str(k): _normalize_text(v) for k, v in row.items()} for row in rows]
    return clean_rows[-limit:]


def _write_browser_session_state(paths: BrowserSessionDurabilityPaths, rows: list[dict[str, str]]) -> None:
    latest = rows[-1] if rows else {}
    reason_counts: dict[str, int] = {}
    for row in rows:
        reason_code = row.get("reason_code", "") or "unknown"
        reason_counts[reason_code] = reason_counts.get(reason_code, 0) + 1
    profile_proof = browser_session_profile_proof()
    latest_profile_state = latest.get("profile_state", "")
    if _clean_status(latest_profile_state) in {"", "unknown"}:
        latest_profile_state = profile_proof["profile_state"]
    latest_cookie_state = latest.get("cookie_state", "")
    if _clean_status(latest_cookie_state) in {"", "unknown"}:
        latest_cookie_state = _browser_cookie_state(
        reason_code=latest.get("reason_code", ""),
        auth_state=latest.get("auth_state", ""),
        profile_state=latest_profile_state,
    )
    reset_summary = browser_session_reset_risk_summary(latest_profile_state)
    payload = {
        "updated_utc": utc_now_iso(),
        "controller_version": CONTROLLER_VERSION,
        "latest": latest,
        "recent_event_count": len(rows),
        "reason_counts": reason_counts,
        "status": latest.get("result", "no_events") if latest else "no_events",
        "latest_reason_code": latest.get("reason_code", "") if latest else "",
        "profile_source": profile_proof["profile_source"],
        "profile_descriptor": profile_proof["profile_descriptor"],
        "approved_profile_descriptor": profile_proof["approved_profile_descriptor"],
        "profile_state": latest_profile_state or "unknown",
        "profile_path_stable": profile_proof["profile_path_stable"],
        "cookie_state": latest_cookie_state or "unknown",
        "startup_path_summary": reset_summary["startup_path"],
        "recovery_path_summary": reset_summary["recovery_path"],
        "cleanup_path_summary": reset_summary["cleanup_path"],
        "reset_risk": reset_summary["reset_risk"],
        "luke_needed": latest.get("reason_code", "") == "manual_challenge",
    }
    paths.state_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_browser_session_durability_report(paths: BrowserSessionDurabilityPaths | None = None) -> str:
    resolved = paths or default_browser_session_durability_paths()
    rows = _read_recent_session_events(resolved.events_path, limit=25)
    latest = rows[-1] if rows else {}
    profile_proof = browser_session_profile_proof()
    latest_profile_state = latest.get("profile_state", "")
    if _clean_status(latest_profile_state) in {"", "unknown"}:
        latest_profile_state = profile_proof["profile_state"]
    latest_cookie_state = latest.get("cookie_state", "")
    if _clean_status(latest_cookie_state) in {"", "unknown"}:
        latest_cookie_state = _browser_cookie_state(
        reason_code=latest.get("reason_code", ""),
        auth_state=latest.get("auth_state", ""),
        profile_state=latest_profile_state,
    )
    reset_summary = browser_session_reset_risk_summary(latest_profile_state)
    lines = [
        "# F Browser Session Durability Report",
        "",
        f"Updated UTC: {utc_now_iso()}",
        f"Controller: {CONTROLLER_VERSION}",
        "",
    ]
    if not latest:
        lines.extend(["## Latest", "", "No browser-session durability events have been recorded yet.", ""])
    else:
        reason_code = latest.get("reason_code", "") or "unknown"
        if reason_code == "manual_challenge":
            plain = "Amazon is asking for something F cannot complete safely by itself."
        elif reason_code == "amazon_forced_mfa":
            plain = "Amazon asked for multi-factor verification; F should use the approved controller path."
        elif reason_code == "profile_mismatch":
            plain = "F appears to be using a different browser profile than expected."
        elif reason_code == "temporary_profile":
            plain = "F appears to be using a temporary browser profile."
        elif reason_code in {"cookie_missing", "cookie_expired"}:
            plain = "F may have lost or expired browser session cookies."
        elif latest.get("reason", "") == "password_not_entered":
            plain = "F tried to type the Seller Central password, but the password field was still empty before submit."
        elif latest.get("reason", "") == "email_continue_not_advanced":
            plain = "F is still on the Seller Central email Continue step, so it has not reached the password box yet."
        elif latest.get("reason", "") == "password_rejected":
            plain = "Amazon rejected the submitted Seller Central password."
        elif latest.get("reason", "") == "submit_not_accepted":
            plain = "F typed the Seller Central password, but the sign-in submit did not move the page forward."
        elif latest.get("reason", "") == "amazon_forced_passkey":
            plain = "Amazon appears to be forcing a passkey-style sign-in challenge."
        else:
            plain = "F has a login/session event, but the exact session cause is still unknown."
        lines.extend(
            [
                "## Latest",
                "",
                plain,
                "",
                f"- Page type: {latest.get('page_type', '')}",
                f"- Status: {latest.get('status', '')}",
                f"- Reason: {latest.get('reason', '')}",
                f"- Reason code: {reason_code}",
                f"- Profile source: {profile_proof['profile_source']}",
                f"- Profile descriptor: {profile_proof['profile_descriptor']}",
                f"- Profile state: {latest_profile_state or 'unknown'}",
                f"- Profile path stable: {profile_proof['profile_path_stable']}",
                f"- Cookie/session state: {latest_cookie_state or 'unknown'}",
                f"- Result: {latest.get('result', '')}",
                f"- Blocker: {latest.get('blocker', '') or 'none recorded'}",
                "",
            ]
        )
    lines.extend(
        [
            "## Approved Profile Proof",
            "",
            f"- Profile source: {profile_proof['profile_source']}",
            f"- Approved profile descriptor: {profile_proof['approved_profile_descriptor']}",
            f"- Active profile descriptor: {profile_proof['profile_descriptor']}",
            f"- Profile state: {latest_profile_state or 'unknown'}",
            f"- Profile path stable: {profile_proof['profile_path_stable']}",
            f"- Cookie/session state: {latest_cookie_state or 'unknown'}",
            "",
        ]
    )
    lines.extend(
        [
            "## Startup, Recovery, And Cleanup Reset Risk",
            "",
            f"- Startup path: {reset_summary['startup_path']}",
            f"- Recovery path: {reset_summary['recovery_path']}",
            f"- Cleanup path: {reset_summary['cleanup_path']}",
            f"- Reset risk: {reset_summary['reset_risk']}",
            "",
        ]
    )
    if rows:
        lines.extend(["## Recent Timeline", ""])
        for row in rows[-10:]:
            lines.append(
                "- "
                f"{row.get('observed_utc', '')}: "
                f"{row.get('page_type', '')} -> {row.get('reason_code', '')} -> "
                f"{row.get('result', '')} ({row.get('reason', '')})"
            )
        lines.append("")
    text = "\n".join(lines).rstrip() + "\n"
    resolved.live_dir.mkdir(parents=True, exist_ok=True)
    resolved.report_path.write_text(text, encoding="utf-8", newline="\n")
    return text


def refresh_browser_session_durability_outputs(paths: BrowserSessionDurabilityPaths | None = None) -> dict[str, object]:
    resolved = paths or default_browser_session_durability_paths()
    rows = _read_recent_session_events(resolved.events_path, limit=50)
    resolved.live_dir.mkdir(parents=True, exist_ok=True)
    _write_browser_session_state(resolved, rows)
    report = build_browser_session_durability_report(resolved)
    return {
        "events_path": str(resolved.events_path),
        "state_path": str(resolved.state_path),
        "report_path": str(resolved.report_path),
        "event_count": len(rows),
        "report_length": len(report),
    }


def record_browser_session_durability_event(
    *,
    event_type: str,
    page_type: str,
    status: str,
    reason: str,
    result: str,
    context: str = "",
    profile_state: str = "unknown",
    cookie_state: str = "unknown",
    auth_state: str = "unknown",
    blocker: str = "",
    source: str = "",
    notes: str = "",
    paths: BrowserSessionDurabilityPaths | None = None,
    extra_secrets: Iterable[object] = (),
    observed_utc: str = "",
) -> dict[str, str]:
    resolved = paths or default_browser_session_durability_paths()
    resolved.live_dir.mkdir(parents=True, exist_ok=True)
    safe_notes = redact_login_controller_text(notes, extra_secrets=extra_secrets)
    safe_reason = redact_login_controller_text(reason, extra_secrets=extra_secrets)
    reason_code = browser_session_reason_code(reason=safe_reason, page_type=page_type, notes=safe_notes)
    profile_proof = browser_session_profile_proof()
    clean_profile_state = _clean_status(profile_state)
    if clean_profile_state in {"", "unknown"}:
        clean_profile_state = profile_proof["profile_state"]
    clean_cookie_state = _clean_status(cookie_state)
    if clean_cookie_state in {"", "unknown"}:
        clean_cookie_state = _browser_cookie_state(
            reason_code=reason_code,
            auth_state=auth_state,
            profile_state=clean_profile_state,
        )
    row = {
        "observed_utc": _normalize_text(observed_utc) or utc_now_iso(),
        "controller_version": CONTROLLER_VERSION,
        "event_type": _clean_status(event_type or context or "seller_central_login"),
        "page_type": _clean_status(page_type),
        "status": _clean_status(status),
        "reason": safe_reason,
        "reason_code": reason_code,
        "profile_state": clean_profile_state or "unknown",
        "cookie_state": clean_cookie_state or "unknown",
        "auth_state": _clean_status(auth_state) or "unknown",
        "result": _clean_status(result),
        "blocker": redact_login_controller_text(blocker, extra_secrets=extra_secrets),
        "source": redact_login_controller_text(source, extra_secrets=extra_secrets),
        "notes": safe_notes,
    }
    write_header = not resolved.events_path.exists()
    with resolved.events_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SESSION_EVENT_COLUMNS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(row)
    rows = _read_recent_session_events(resolved.events_path, limit=50)
    _write_browser_session_state(resolved, rows)
    build_browser_session_durability_report(resolved)
    return row


def _page_pull_session_shape(page_pull: Mapping[str, object]) -> tuple[str, str, str]:
    page_state = _clean_status(page_pull.get("page_state", ""))
    reason = _clean_status(page_pull.get("reason", ""))
    if page_state == "authenticated":
        return "authenticated", "succeeded", "succeeded"
    if page_state == "otp_code_page":
        return "seller_central_otp", "waiting_for_code", "waiting_for_code"
    if page_state == "manual_challenge":
        return "manual_challenge", "blocked", "blocked"
    if page_state in {"email_continue_page", "password_or_passkey_page", "password_page", "signin_page"}:
        result = "blocked" if reason else "observed"
        return "seller_central_signin", "blocked" if reason else "observed", result
    return "seller_central_unknown", "observed", "observed"


def record_browser_session_page_pull(
    page_pull: Mapping[str, object],
    *,
    paths: BrowserSessionDurabilityPaths | None = None,
    extra_secrets: Iterable[object] = (),
) -> dict[str, str]:
    resolved = paths or default_browser_session_durability_paths()
    observed = _normalize_text(page_pull.get("observed_utc"))
    if observed:
        for row in _read_recent_session_events(resolved.events_path, limit=200):
            if row.get("source") == "seller_central_page_pull" and f"page_pull_observed={observed}" in row.get("notes", ""):
                return row
    page_type, status, result = _page_pull_session_shape(page_pull)
    reason = _clean_status(page_pull.get("reason", "")) or _clean_status(page_pull.get("page_state", "")) or "page_pull_observed"
    notes = (
        f"page_pull_observed={observed or 'unknown'};"
        f"page_state={_clean_status(page_pull.get('page_state', ''))};"
        f"page_hint={_normalize_text(page_pull.get('page_hint'))}"
    )
    auth_state = "logged_in" if page_type == "authenticated" else "login_required"
    blocker = reason if status == "blocked" else ""
    return record_browser_session_durability_event(
        event_type="seller_central_page_pull",
        page_type=page_type,
        status=status,
        reason=reason,
        result=result,
        auth_state=auth_state,
        blocker=blocker,
        source="seller_central_page_pull",
        notes=notes,
        paths=resolved,
        extra_secrets=extra_secrets,
        observed_utc=observed,
    )
