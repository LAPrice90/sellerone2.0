from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


BBP_LOGIN_ENV_PATH_ENV = "BBP_LOGIN_ENV_PATH"
BBP_LOGIN_RECOVERY_PROOF_PATH_ENV = "BBP_LOGIN_RECOVERY_PROOF_PATH"

DEFAULT_LOGIN_HEADING_XPATH = "/html/body/div/div/div[1]/div/div[1]/h1"
DEFAULT_LOGIN_HEADING_TEXT = "Login"
DEFAULT_LOGIN_EMAIL_XPATH = '//*[@id="loginEmail"]'
DEFAULT_LOGIN_PASSWORD_XPATH = '//*[@id="loginPassword"]'
DEFAULT_LOGIN_BUTTON_XPATH = '//*[@id="loginBtn"]'

PROOF_COLUMNS = [
    "observed_utc",
    "context",
    "status",
    "reason",
    "attempted_flag",
    "succeeded_flag",
    "auto_login_enabled",
    "secret_file_exists",
    "email_present",
    "password_present",
    "login_heading_detected",
    "heading_xpath",
    "email_xpath",
    "password_xpath",
    "button_xpath",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_bbp_login_env_path() -> Path:
    return _repo_root() / "secrets" / "price_list_manager" / "bbp_login.env"


def default_bbp_login_recovery_proof_path() -> Path:
    return (
        _repo_root()
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "live"
        / "bbp_login_recovery_proof.csv"
    )


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _truthy(value: object) -> bool:
    return _normalize_text(value).lower() in {"1", "true", "yes", "y", "on"}


def _strip_quotes(value: str) -> str:
    text = _normalize_text(value)
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1].strip()
    return text


def parse_bbp_login_env_text(text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw_line in str(text or "").replace("\r", "\n").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = _strip_quotes(value)
    return parsed


@dataclass(frozen=True)
class BBPLoginRecoveryConfig:
    env_path: Path
    file_exists: bool
    auto_login_enabled: bool
    email: str = field(default="", repr=False)
    password: str = field(default="", repr=False)
    heading_xpath: str = DEFAULT_LOGIN_HEADING_XPATH
    heading_text: str = DEFAULT_LOGIN_HEADING_TEXT
    email_xpath: str = DEFAULT_LOGIN_EMAIL_XPATH
    password_xpath: str = DEFAULT_LOGIN_PASSWORD_XPATH
    button_xpath: str = DEFAULT_LOGIN_BUTTON_XPATH

    @property
    def email_present(self) -> bool:
        return bool(_normalize_text(self.email))

    @property
    def password_present(self) -> bool:
        return bool(_normalize_text(self.password))

    @property
    def credentials_present(self) -> bool:
        return self.email_present and self.password_present


def load_bbp_login_recovery_config(
    *,
    env_path: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> BBPLoginRecoveryConfig:
    source_env = environ if environ is not None else os.environ
    raw_path = _normalize_text(env_path) or _normalize_text(source_env.get(BBP_LOGIN_ENV_PATH_ENV, ""))
    path = Path(raw_path) if raw_path else default_bbp_login_env_path()
    values: dict[str, str] = {}
    file_exists = path.exists()
    if file_exists:
        try:
            values = parse_bbp_login_env_text(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            values = {}

    return BBPLoginRecoveryConfig(
        env_path=path,
        file_exists=file_exists,
        auto_login_enabled=_truthy(values.get("BBP_AUTO_LOGIN_ENABLED", "")),
        email=_normalize_text(values.get("BBP_LOGIN_EMAIL", "")),
        password=_normalize_text(values.get("BBP_LOGIN_PASSWORD", "")),
        heading_xpath=_normalize_text(values.get("BBP_LOGIN_HEADING_XPATH", "")) or DEFAULT_LOGIN_HEADING_XPATH,
        heading_text=_normalize_text(values.get("BBP_LOGIN_HEADING_TEXT", "")) or DEFAULT_LOGIN_HEADING_TEXT,
        email_xpath=_normalize_text(values.get("BBP_LOGIN_EMAIL_XPATH", "")) or DEFAULT_LOGIN_EMAIL_XPATH,
        password_xpath=_normalize_text(values.get("BBP_LOGIN_PASSWORD_XPATH", "")) or DEFAULT_LOGIN_PASSWORD_XPATH,
        button_xpath=_normalize_text(values.get("BBP_LOGIN_BUTTON_XPATH", "")) or DEFAULT_LOGIN_BUTTON_XPATH,
    )


def redact_bbp_login_secrets(text: object, config: BBPLoginRecoveryConfig) -> str:
    redacted = _normalize_text(text)
    for secret in (config.email, config.password):
        token = _normalize_text(secret)
        if token:
            redacted = redacted.replace(token, "[redacted]")
    return redacted


def bbp_login_safe_proof_fields(
    config: BBPLoginRecoveryConfig,
    *,
    status: str,
    reason: str = "",
    context: str = "",
    attempted: bool = False,
    succeeded: bool = False,
    login_heading_detected: bool = False,
    observed_utc: str | None = None,
) -> dict[str, str]:
    return {
        "observed_utc": observed_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "context": redact_bbp_login_secrets(context, config),
        "status": redact_bbp_login_secrets(status, config),
        "reason": redact_bbp_login_secrets(reason, config),
        "attempted_flag": "1" if attempted else "0",
        "succeeded_flag": "1" if succeeded else "0",
        "auto_login_enabled": "1" if config.auto_login_enabled else "0",
        "secret_file_exists": "1" if config.file_exists else "0",
        "email_present": "1" if config.email_present else "0",
        "password_present": "1" if config.password_present else "0",
        "login_heading_detected": "1" if login_heading_detected else "0",
        "heading_xpath": config.heading_xpath,
        "email_xpath": config.email_xpath,
        "password_xpath": config.password_xpath,
        "button_xpath": config.button_xpath,
    }


def append_bbp_login_recovery_proof(
    config: BBPLoginRecoveryConfig,
    *,
    status: str,
    reason: str = "",
    context: str = "",
    attempted: bool = False,
    succeeded: bool = False,
    login_heading_detected: bool = False,
    proof_path: str | Path | None = None,
) -> dict[str, str]:
    raw_path = _normalize_text(proof_path) or _normalize_text(os.environ.get(BBP_LOGIN_RECOVERY_PROOF_PATH_ENV, ""))
    path = Path(raw_path) if raw_path else default_bbp_login_recovery_proof_path()
    row = bbp_login_safe_proof_fields(
        config,
        status=status,
        reason=reason,
        context=context,
        attempted=attempted,
        succeeded=succeeded,
        login_heading_detected=login_heading_detected,
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not path.exists()
        with path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=PROOF_COLUMNS, extrasaction="ignore")
            if write_header:
                writer.writeheader()
            writer.writerow(row)
        return {"proof_written": "1", "proof_path": str(path)}
    except Exception as exc:
        return {"proof_written": "0", "proof_error": type(exc).__name__}
