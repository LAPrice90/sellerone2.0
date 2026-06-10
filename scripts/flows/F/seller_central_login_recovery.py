from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


SELLER_CENTRAL_LOGIN_ENV_PATH_ENV = "SELLER_CENTRAL_LOGIN_ENV_PATH"
SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH_ENV = "SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH"
SELLER_CENTRAL_LOGIN_ATTEMPT_CONTROL_PATH_ENV = "SELLER_CENTRAL_LOGIN_ATTEMPT_CONTROL_PATH"
SELLER_CENTRAL_LOGIN_ATTEMPT_MODE_ENV = "SELLER_CENTRAL_LOGIN_ATTEMPT_MODE"
SELLER_CENTRAL_LOGIN_COOLDOWN_HOURS_ENV = "SELLER_CENTRAL_LOGIN_COOLDOWN_HOURS"

DEFAULT_CODE_GMAIL_LABEL = "AmazonOTP"
DEFAULT_CODE_WAIT_SECONDS = 120.0
DEFAULT_CODE_MAX_AGE_SECONDS = 120.0
DEFAULT_CODE_REGEX = r"(?<!\d)(\d{6})(?!\d)"
DEFAULT_EMAIL_XPATH = '//*[@id="ap_email"]'
DEFAULT_CONTINUE_BUTTON_XPATH = '//*[@id="continue"]'
DEFAULT_PASSWORD_XPATH = '//*[@id="ap_password"]'
DEFAULT_SIGNIN_BUTTON_XPATH = '//*[@id="signInSubmit"]'
DEFAULT_OTP_XPATH = '//*[@id="auth-mfa-otpcode"]'
DEFAULT_OTP_BUTTON_XPATH = '//*[@id="auth-signin-button"]'
DEFAULT_SUCCESS_SELECTOR = "#dashboardYesOrNo"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

PROOF_COLUMNS = [
    "observed_utc",
    "context",
    "status",
    "reason",
    "seller_central_signin_detected",
    "seller_central_otp_detected",
    "requested_utc",
    "message_ts_utc",
    "code_seen_flag",
    "fresh_code_flag",
    "used_message_flag",
    "attempted_flag",
    "succeeded_flag",
    "auto_login_enabled",
    "secret_file_exists",
    "credentials_present",
    "gmail_label",
    "code_age_seconds",
    "source_message_id",
    "notes",
]

USED_MESSAGE_COLUMNS = [
    "observed_utc",
    "message_id_hash",
    "message_ts_utc",
    "context",
    "status",
]
LOGIN_ATTEMPT_CONTROL_MODES = {
    "normal_scan_only",
    "login_attempt_mode",
    "login_cooldown",
    "manual_challenge",
}
LOGIN_ATTEMPT_COOLDOWN_REASONS = {
    "amazon_phone_sms_cooldown",
    "sms_option_not_clickable",
    "authenticator_only_no_sms_option",
}
LOGIN_ATTEMPT_MANUAL_REASONS = {
    "amazon_forced_passkey",
    "amazon_forced_mfa",
    "captcha",
    "manual_challenge_required",
    "passkey_required",
}


@dataclass(frozen=True)
class SellerCentralLoginRecoveryConfig:
    env_path: Path
    secret_file_exists: bool
    auto_login_enabled: bool
    email: str
    password: str
    code_gmail_label: str = DEFAULT_CODE_GMAIL_LABEL
    code_wait_seconds: float = DEFAULT_CODE_WAIT_SECONDS
    code_max_age_seconds: float = DEFAULT_CODE_MAX_AGE_SECONDS
    code_regex: str = DEFAULT_CODE_REGEX
    email_xpath: str = DEFAULT_EMAIL_XPATH
    continue_button_xpath: str = DEFAULT_CONTINUE_BUTTON_XPATH
    password_xpath: str = DEFAULT_PASSWORD_XPATH
    signin_button_xpath: str = DEFAULT_SIGNIN_BUTTON_XPATH
    otp_xpath: str = DEFAULT_OTP_XPATH
    otp_button_xpath: str = DEFAULT_OTP_BUTTON_XPATH
    success_selector: str = DEFAULT_SUCCESS_SELECTOR

    @property
    def credentials_present(self) -> bool:
        return bool(self.email and self.password)


@dataclass(frozen=True)
class SellerCentralCodeResult:
    status: str
    reason: str
    code: str = ""
    message_id: str = ""
    message_ts_utc: str = ""
    age_seconds: float | None = None


@dataclass(frozen=True)
class SellerCentralLoginAttemptControl:
    mode: str
    reason: str = ""
    cooldown_until_utc: str = ""
    updated_utc: str = ""
    source: str = ""

    @property
    def allows_attempt(self) -> bool:
        return self.mode == "login_attempt_mode"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _utc_iso_from_dt(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_seller_central_login_env_path() -> Path:
    return _repo_root() / "secrets" / "price_list_manager" / "seller_central_login.env"


def default_seller_central_login_recovery_proof_path() -> Path:
    return (
        _repo_root()
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "live"
        / "seller_central_login_recovery_proof.csv"
    )


def default_seller_central_login_attempt_control_path(
    *,
    proof_path: str | Path | None = None,
) -> Path:
    raw_path = _normalize_text(proof_path) or _normalize_text(
        os.environ.get(SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH_ENV, "")
    )
    if raw_path:
        return Path(raw_path).parent / "f_login_attempt_control_state.json"
    return default_seller_central_login_recovery_proof_path().parent / "f_login_attempt_control_state.json"


def default_seller_central_otp_used_messages_path() -> Path:
    return (
        _repo_root()
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "live"
        / "seller_central_otp_used_messages.csv"
    )


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _truthy(value: object) -> bool:
    return _normalize_text(value).lower() in {"1", "true", "yes", "y", "on"}


def _float_value(value: object, default: float) -> float:
    try:
        return max(0.0, float(_normalize_text(value)))
    except ValueError:
        return default


def parse_seller_central_login_env_text(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def load_seller_central_login_recovery_config(
    *,
    env_path: str | Path | None = None,
    source_env: dict[str, str] | None = None,
) -> SellerCentralLoginRecoveryConfig:
    env = source_env if source_env is not None else os.environ
    raw_path = _normalize_text(env_path) or _normalize_text(env.get(SELLER_CENTRAL_LOGIN_ENV_PATH_ENV, ""))
    path = Path(raw_path) if raw_path else default_seller_central_login_env_path()
    values: dict[str, str] = {}
    exists = path.exists()
    if exists:
        values = parse_seller_central_login_env_text(path.read_text(encoding="utf-8", errors="replace"))

    return SellerCentralLoginRecoveryConfig(
        env_path=path,
        secret_file_exists=exists,
        auto_login_enabled=_truthy(values.get("SELLER_CENTRAL_AUTO_LOGIN_ENABLED", "")),
        email=_normalize_text(values.get("SELLER_CENTRAL_LOGIN_EMAIL", "")),
        password=_normalize_text(values.get("SELLER_CENTRAL_LOGIN_PASSWORD", "")),
        code_gmail_label=_normalize_text(values.get("SELLER_CENTRAL_CODE_GMAIL_LABEL", "")) or DEFAULT_CODE_GMAIL_LABEL,
        code_wait_seconds=_float_value(values.get("SELLER_CENTRAL_CODE_WAIT_SECONDS", ""), DEFAULT_CODE_WAIT_SECONDS),
        code_max_age_seconds=_float_value(
            values.get("SELLER_CENTRAL_CODE_MAX_AGE_SECONDS", ""),
            DEFAULT_CODE_MAX_AGE_SECONDS,
        ),
        code_regex=_normalize_text(values.get("SELLER_CENTRAL_CODE_REGEX", "")) or DEFAULT_CODE_REGEX,
        email_xpath=_normalize_text(values.get("SELLER_CENTRAL_EMAIL_XPATH", "")) or DEFAULT_EMAIL_XPATH,
        continue_button_xpath=_normalize_text(values.get("SELLER_CENTRAL_CONTINUE_BUTTON_XPATH", ""))
        or DEFAULT_CONTINUE_BUTTON_XPATH,
        password_xpath=_normalize_text(values.get("SELLER_CENTRAL_PASSWORD_XPATH", "")) or DEFAULT_PASSWORD_XPATH,
        signin_button_xpath=_normalize_text(values.get("SELLER_CENTRAL_SIGNIN_BUTTON_XPATH", ""))
        or DEFAULT_SIGNIN_BUTTON_XPATH,
        otp_xpath=_normalize_text(values.get("SELLER_CENTRAL_OTP_XPATH", "")) or DEFAULT_OTP_XPATH,
        otp_button_xpath=_normalize_text(values.get("SELLER_CENTRAL_OTP_BUTTON_XPATH", ""))
        or DEFAULT_OTP_BUTTON_XPATH,
        success_selector=_normalize_text(values.get("SELLER_CENTRAL_SUCCESS_SELECTOR", "")) or DEFAULT_SUCCESS_SELECTOR,
    )


def redact_seller_central_secrets(
    text: object,
    config: SellerCentralLoginRecoveryConfig,
    *,
    code: str = "",
) -> str:
    safe = _normalize_text(text)
    for secret in (config.email, config.password, code):
        if secret:
            safe = safe.replace(secret, "<redacted>")
    safe = re.sub(DEFAULT_CODE_REGEX, "<redacted-code>", safe)
    return safe


def _control_state_path(control_path: str | Path | None = None) -> Path:
    raw_path = _normalize_text(control_path) or _normalize_text(
        os.environ.get(SELLER_CENTRAL_LOGIN_ATTEMPT_CONTROL_PATH_ENV, "")
    )
    return Path(raw_path) if raw_path else default_seller_central_login_attempt_control_path()


def read_seller_central_login_attempt_control(
    *,
    control_path: str | Path | None = None,
    now_utc: str | None = None,
) -> SellerCentralLoginAttemptControl:
    path = _control_state_path(control_path)
    if not path.exists():
        return SellerCentralLoginAttemptControl(mode="normal_scan_only", source="missing_state")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return SellerCentralLoginAttemptControl(mode="normal_scan_only", reason="state_read_error", source="state_file")
    mode = _normalize_text(payload.get("mode", "normal_scan_only")).lower()
    if mode not in LOGIN_ATTEMPT_CONTROL_MODES:
        mode = "normal_scan_only"
    cooldown_until = _normalize_text(payload.get("cooldown_until_utc", ""))
    if mode == "login_cooldown":
        until_dt = _parse_utc(cooldown_until)
        now_dt = _parse_utc(now_utc or utc_now_iso()) or datetime.now(timezone.utc)
        if until_dt is None or until_dt <= now_dt:
            mode = "normal_scan_only"
    return SellerCentralLoginAttemptControl(
        mode=mode,
        reason=_normalize_text(payload.get("reason", "")),
        cooldown_until_utc=cooldown_until,
        updated_utc=_normalize_text(payload.get("updated_utc", "")),
        source=_normalize_text(payload.get("source", "")) or "state_file",
    )


def write_seller_central_login_attempt_control(
    config: SellerCentralLoginRecoveryConfig,
    *,
    mode: str,
    reason: str,
    source: str,
    cooldown_hours: float | None = None,
    control_path: str | Path | None = None,
    now_utc: str | None = None,
) -> dict[str, str]:
    clean_mode = _normalize_text(mode).lower()
    if clean_mode not in LOGIN_ATTEMPT_CONTROL_MODES:
        clean_mode = "normal_scan_only"
    now_dt = _parse_utc(now_utc or utc_now_iso()) or datetime.now(timezone.utc)
    cooldown_until = ""
    if clean_mode == "login_cooldown":
        hours = cooldown_hours
        if hours is None:
            hours = _float_value(os.environ.get(SELLER_CENTRAL_LOGIN_COOLDOWN_HOURS_ENV, ""), 24.0)
        cooldown_until = _utc_iso_from_dt(now_dt + timedelta(hours=max(1.0, hours)))
    payload = {
        "updated_utc": _utc_iso_from_dt(now_dt),
        "mode": clean_mode,
        "reason": redact_seller_central_secrets(reason, config),
        "cooldown_until_utc": cooldown_until,
        "auto_login_enabled": "1" if config.auto_login_enabled else "0",
        "attempt_mode_env": "1" if _truthy(os.environ.get(SELLER_CENTRAL_LOGIN_ATTEMPT_MODE_ENV, "")) else "0",
        "source": redact_seller_central_secrets(source, config),
    }
    path = _control_state_path(control_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {key: str(value) for key, value in payload.items()}


def seller_central_login_attempt_control_for_config(
    config: SellerCentralLoginRecoveryConfig,
    *,
    control_path: str | Path | None = None,
    now_utc: str | None = None,
) -> SellerCentralLoginAttemptControl:
    state = read_seller_central_login_attempt_control(control_path=control_path, now_utc=now_utc)
    if state.mode in {"login_cooldown", "manual_challenge"}:
        return state
    if config.auto_login_enabled and _truthy(os.environ.get(SELLER_CENTRAL_LOGIN_ATTEMPT_MODE_ENV, "")):
        return SellerCentralLoginAttemptControl(mode="login_attempt_mode", reason="explicit_attempt_mode", source="env")
    return SellerCentralLoginAttemptControl(mode="normal_scan_only", reason="attempt_mode_not_enabled", source="env")


def seller_central_security_message_reason(text: object) -> str:
    body = _normalize_text(text).lower()
    if "unable to send an sms" in body and "phone number" in body:
        return "amazon_phone_sms_cooldown"
    if "captcha" in body or "enter the characters" in body:
        return "captcha"
    if "passkey" in body or "security key" in body:
        return "passkey_required"
    if "authenticator" in body and "sms" not in body and "text message" not in body:
        return "authenticator_only_no_sms_option"
    return ""


def login_attempt_control_mode_for_blocker(reason: object) -> str:
    clean = _normalize_text(reason).lower()
    if clean in LOGIN_ATTEMPT_COOLDOWN_REASONS:
        return "login_cooldown"
    if clean in LOGIN_ATTEMPT_MANUAL_REASONS or "manual_challenge" in clean or "captcha" in clean or "passkey" in clean:
        return "manual_challenge"
    return ""


def seller_central_login_safe_proof_fields(
    config: SellerCentralLoginRecoveryConfig,
    *,
    status: str,
    reason: str,
    context: str,
    signin_detected: bool = False,
    otp_detected: bool = False,
    requested_utc: str = "",
    message_ts_utc: str = "",
    code_seen: bool = False,
    fresh_code: bool = False,
    used_message: bool = False,
    attempted: bool = False,
    succeeded: bool = False,
    code_age_seconds: float | None = None,
    source_message_id: str = "",
    notes: str = "",
) -> dict[str, str]:
    return {
        "observed_utc": utc_now_iso(),
        "context": redact_seller_central_secrets(context, config),
        "status": redact_seller_central_secrets(status, config),
        "reason": redact_seller_central_secrets(reason, config),
        "seller_central_signin_detected": "1" if signin_detected else "0",
        "seller_central_otp_detected": "1" if otp_detected else "0",
        "requested_utc": requested_utc,
        "message_ts_utc": message_ts_utc,
        "code_seen_flag": "1" if code_seen else "0",
        "fresh_code_flag": "1" if fresh_code else "0",
        "used_message_flag": "1" if used_message else "0",
        "attempted_flag": "1" if attempted else "0",
        "succeeded_flag": "1" if succeeded else "0",
        "auto_login_enabled": "1" if config.auto_login_enabled else "0",
        "secret_file_exists": "1" if config.secret_file_exists else "0",
        "credentials_present": "1" if config.credentials_present else "0",
        "gmail_label": redact_seller_central_secrets(config.code_gmail_label, config),
        "code_age_seconds": "" if code_age_seconds is None else f"{code_age_seconds:.2f}",
        "source_message_id": redact_seller_central_secrets(source_message_id, config),
        "notes": redact_seller_central_secrets(notes, config),
    }


def append_seller_central_login_recovery_proof(
    config: SellerCentralLoginRecoveryConfig,
    *,
    status: str,
    reason: str,
    context: str,
    signin_detected: bool = False,
    otp_detected: bool = False,
    requested_utc: str = "",
    message_ts_utc: str = "",
    code_seen: bool = False,
    fresh_code: bool = False,
    used_message: bool = False,
    attempted: bool = False,
    succeeded: bool = False,
    code_age_seconds: float | None = None,
    source_message_id: str = "",
    notes: str = "",
    proof_path: str | Path | None = None,
) -> dict[str, str]:
    raw_path = _normalize_text(proof_path) or _normalize_text(os.environ.get(SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH_ENV, ""))
    path = Path(raw_path) if raw_path else default_seller_central_login_recovery_proof_path()
    row = seller_central_login_safe_proof_fields(
        config,
        status=status,
        reason=reason,
        context=context,
        signin_detected=signin_detected,
        otp_detected=otp_detected,
        requested_utc=requested_utc,
        message_ts_utc=message_ts_utc,
        code_seen=code_seen,
        fresh_code=fresh_code,
        used_message=used_message,
        attempted=attempted,
        succeeded=succeeded,
        code_age_seconds=code_age_seconds,
        source_message_id=source_message_id,
        notes=notes,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PROOF_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)
    return row


def seller_central_code_message_id_hash(message_id: object) -> str:
    raw = _normalize_text(message_id)
    if not raw:
        return ""
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def _read_used_message_hashes(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        with path.open("r", newline="", encoding="utf-8") as handle:
            return {
                _normalize_text(row.get("message_id_hash", ""))
                for row in csv.DictReader(handle)
                if _normalize_text(row.get("message_id_hash", ""))
            }
    except OSError:
        return set()


def is_seller_central_code_message_used(message_id: object, *, used_path: str | Path | None = None) -> bool:
    message_hash = seller_central_code_message_id_hash(message_id)
    if not message_hash:
        return False
    path = Path(used_path) if used_path else default_seller_central_otp_used_messages_path()
    return message_hash in _read_used_message_hashes(path)


def mark_seller_central_code_message_used(
    result: SellerCentralCodeResult,
    *,
    context: str,
    status: str = "used",
    used_path: str | Path | None = None,
) -> None:
    message_hash = seller_central_code_message_id_hash(result.message_id)
    if not message_hash:
        return
    path = Path(used_path) if used_path else default_seller_central_otp_used_messages_path()
    if message_hash in _read_used_message_hashes(path):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=USED_MESSAGE_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(
            {
                "observed_utc": utc_now_iso(),
                "message_id_hash": message_hash,
                "message_ts_utc": result.message_ts_utc,
                "context": _normalize_text(context),
                "status": _normalize_text(status) or "used",
            }
        )


def _parse_utc(value: object) -> datetime | None:
    text = _normalize_text(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _message_ts_utc(message: dict[str, Any]) -> str:
    raw = _normalize_text(message.get("internalDate", ""))
    if raw:
        try:
            return (
                datetime.fromtimestamp(int(raw) / 1000, tz=timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
            )
        except ValueError:
            pass
    return ""


def _decode_gmail_body(value: object) -> str:
    data = _normalize_text(value)
    if not data:
        return ""
    try:
        padded = data + ("=" * (-len(data) % 4))
        return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _walk_parts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    stack = [payload]
    while stack:
        current = stack.pop(0)
        parts.append(current)
        for child in current.get("parts", []) or []:
            if isinstance(child, dict):
                stack.append(child)
    return parts


def _message_text(message: dict[str, Any]) -> str:
    payload = message.get("payload", {}) or {}
    chunks = [_normalize_text(message.get("snippet", ""))]
    for part in _walk_parts(payload):
        body = part.get("body", {}) or {}
        decoded = _decode_gmail_body(body.get("data", ""))
        if decoded:
            chunks.append(decoded)
    return "\n".join(chunk for chunk in chunks if chunk)


def extract_seller_central_code(text: object, *, regex: str = DEFAULT_CODE_REGEX) -> str:
    try:
        match = re.search(regex, str(text or ""))
    except re.error:
        match = re.search(DEFAULT_CODE_REGEX, str(text or ""))
    if not match:
        return ""
    return _normalize_text(match.group(1) if match.groups() else match.group(0))


def _build_gmail_service(root: Path):
    token_path = root / "secrets" / "price_list_manager" / "gmail_token.json"
    client_path = root / "secrets" / "price_list_manager" / "gmail_client_secret.json"
    if not token_path.exists() or not client_path.exists():
        raise FileNotFoundError("missing local Gmail OAuth files")
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        if not creds.valid:
            raise RuntimeError("local Gmail OAuth token is not valid")
    return build("gmail", "v1", credentials=creds)


def fetch_latest_seller_central_code(
    *,
    root: Path | str | None = None,
    label: str = DEFAULT_CODE_GMAIL_LABEL,
    requested_after_utc: str,
    max_age_seconds: float = DEFAULT_CODE_MAX_AGE_SECONDS,
    regex: str = DEFAULT_CODE_REGEX,
    service: Any | None = None,
    now_utc: str | None = None,
    used_path: str | Path | None = None,
) -> SellerCentralCodeResult:
    base = Path(root) if root is not None else _repo_root()
    requested_dt = _parse_utc(requested_after_utc)
    now_dt = _parse_utc(now_utc or utc_now_iso()) or datetime.now(timezone.utc)
    if requested_dt is None:
        return SellerCentralCodeResult(status="blocked", reason="missing_request_time")
    try:
        gmail = service or _build_gmail_service(base)
        query = f'label:"{label}" newer_than:1d -in:trash -in:spam'
        search = gmail.users().messages().list(userId="me", q=query, maxResults=10).execute()
        candidates: list[tuple[datetime, str, str, str, float]] = []
        saw_fresh_used_message = False
        for item in search.get("messages", []) or []:
            message_id = _normalize_text(item.get("id", ""))
            if not message_id:
                continue
            message = gmail.users().messages().get(userId="me", id=message_id, format="full").execute()
            message_ts = _message_ts_utc(message)
            message_dt = _parse_utc(message_ts)
            if message_dt is None or message_dt < requested_dt:
                continue
            age_seconds = max(0.0, (now_dt - message_dt).total_seconds())
            if age_seconds > max_age_seconds:
                continue
            if is_seller_central_code_message_used(message_id, used_path=used_path):
                saw_fresh_used_message = True
                continue
            code = extract_seller_central_code(_message_text(message), regex=regex)
            if code:
                candidates.append((message_dt, message_ts, message_id, code, age_seconds))
        if not candidates:
            reason = "fresh_code_already_used" if saw_fresh_used_message else "no_fresh_code"
            return SellerCentralCodeResult(status="not_found", reason=reason)
        _message_dt, message_ts, message_id, code, age_seconds = sorted(candidates)[-1]
        return SellerCentralCodeResult(
            status="found",
            reason="fresh_code_found",
            code=code,
            message_id=message_id,
            message_ts_utc=message_ts,
            age_seconds=age_seconds,
        )
    except Exception as exc:
        return SellerCentralCodeResult(status="blocked", reason=f"gmail_code_fetch_error:{exc.__class__.__name__}")


def wait_for_seller_central_code(
    config: SellerCentralLoginRecoveryConfig,
    *,
    requested_utc: str,
    root: Path | str | None = None,
    service: Any | None = None,
    used_path: str | Path | None = None,
    sleep_func: Callable[[float], None] = time.sleep,
    now_func: Callable[[], str] = utc_now_iso,
) -> SellerCentralCodeResult:
    deadline = time.monotonic() + config.code_wait_seconds
    last = SellerCentralCodeResult(status="not_found", reason="not_polled")
    while True:
        last = fetch_latest_seller_central_code(
            root=root,
            label=config.code_gmail_label,
            requested_after_utc=requested_utc,
            max_age_seconds=config.code_max_age_seconds,
            regex=config.code_regex,
            service=service,
            now_utc=now_func(),
            used_path=used_path,
        )
        if last.status == "found" or last.status == "blocked":
            return last
        if time.monotonic() >= deadline:
            return SellerCentralCodeResult(status="expired", reason=last.reason)
        sleep_func(min(2.0, max(0.1, deadline - time.monotonic())))


def run_read_only_otp_intake_proof(
    *,
    root: Path | str | None = None,
    requested_after_utc: str | None = None,
    wait: bool = False,
    proof_path: str | Path | None = None,
    used_path: str | Path | None = None,
    service: Any | None = None,
    now_utc: str | None = None,
) -> dict[str, str]:
    config = load_seller_central_login_recovery_config()
    requested_utc = _normalize_text(requested_after_utc) or utc_now_iso()
    if wait:
        result = wait_for_seller_central_code(
            config,
            requested_utc=requested_utc,
            root=root,
            service=service,
            used_path=used_path,
        )
    else:
        result = fetch_latest_seller_central_code(
            root=root,
            label=config.code_gmail_label,
            requested_after_utc=requested_utc,
            max_age_seconds=config.code_max_age_seconds,
            regex=config.code_regex,
            service=service,
            used_path=used_path,
            now_utc=now_utc,
        )
    found = result.status == "found"
    already_used = result.reason == "fresh_code_already_used"
    if found:
        mark_seller_central_code_message_used(
            result,
            context="read_only_otp_intake_proof",
            status="proof_seen",
            used_path=used_path,
        )
    return append_seller_central_login_recovery_proof(
        config,
        status="otp_intake_proved" if found else "otp_intake_missing",
        reason=result.reason,
        context="read_only_otp_intake_proof",
        requested_utc=requested_utc,
        message_ts_utc=result.message_ts_utc,
        code_seen=found,
        fresh_code=found,
        used_message=already_used,
        attempted=False,
        succeeded=False,
        code_age_seconds=result.age_seconds,
        source_message_id=result.message_id,
        notes="read_only_gmail_otp_probe_no_f061_no_delete",
        proof_path=proof_path,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Seller Central OTP intake proof for F.")
    parser.add_argument("--otp-proof", action="store_true", help="Read the configured Gmail OTP label and write redacted proof.")
    parser.add_argument("--requested-after-utc", default="", help="Only accept OTP messages after this UTC timestamp.")
    parser.add_argument("--wait", action="store_true", help="Wait up to the configured code window for a fresh OTP message.")
    parser.add_argument("--proof-path", default="", help="Optional proof CSV override for tests.")
    parser.add_argument("--used-path", default="", help="Optional used-message CSV override for tests.")
    args = parser.parse_args()
    if not args.otp_proof:
        parser.error("No action selected. Use --otp-proof for the read-only Gmail OTP proof.")
    row = run_read_only_otp_intake_proof(
        requested_after_utc=args.requested_after_utc,
        wait=args.wait,
        proof_path=args.proof_path or None,
        used_path=args.used_path or None,
    )
    print(
        "status={status}|reason={reason}|gmail_label={label}|code_seen={code_seen}|fresh={fresh}|used_message={used}".format(
            status=row.get("status", ""),
            reason=row.get("reason", ""),
            label=row.get("gmail_label", ""),
            code_seen=row.get("code_seen_flag", ""),
            fresh=row.get("fresh_code_flag", ""),
            used=row.get("used_message_flag", ""),
        )
    )


if __name__ == "__main__":
    main()
