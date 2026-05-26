from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import requests

logger = logging.getLogger("tokenCall")

LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
TOKEN_FILE_NAME = "token.json"
TOKEN_REFRESH_BUFFER_SECONDS = 300
REQUEST_TIMEOUT_SECONDS = 15
MAX_RETRIES = 3


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for raw in raw_lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.split("#", 1)[0].strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _load_env_if_missing() -> None:
    here = Path(__file__).resolve()
    repo_root = here.parents[4] if len(here.parents) >= 5 else Path.cwd()
    search_paths = [
        repo_root / "secrets" / ".env",
        repo_root / ".env",
        Path.cwd() / "secrets" / ".env",
        Path.cwd() / ".env",
    ]
    seen: set[str] = set()
    for path in search_paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        _load_env_file(path)


def _token_cache_path() -> Path:
    return Path(__file__).resolve().parent / TOKEN_FILE_NAME


def _read_cached_token() -> str:
    token_file = _token_cache_path()
    current_time = int(time.time())
    if not token_file.exists():
        return ""
    try:
        payload = json.loads(token_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""

    access_token = str(payload.get("access_token", "")).strip()
    expiry_epoch = int(payload.get("token_expiry_time", 0) or 0)
    if access_token and current_time < (expiry_epoch - TOKEN_REFRESH_BUFFER_SECONDS):
        return access_token
    return ""


def _write_cached_token(access_token: str, expiry_epoch: int) -> None:
    payload = {
        "access_token": access_token,
        "token_expiry_time": int(expiry_epoch),
    }
    token_file = _token_cache_path()
    token_file.write_text(json.dumps(payload), encoding="utf-8")


def _env(name: str) -> str:
    return str(os.environ.get(name, "")).strip()


def get_access_token():
    _load_env_if_missing()

    cached = _read_cached_token()
    if cached:
        logger.info("Reusing cached access token.")
        return cached

    refresh_token = _env("LWA_REFRESH_TOKEN")
    client_id = _env("LWA_CLIENT_ID")
    client_secret = _env("LWA_CLIENT_SECRET")
    if not refresh_token or not client_id or not client_secret:
        logger.error("Missing one or more env vars: LWA_REFRESH_TOKEN, LWA_CLIENT_ID, LWA_CLIENT_SECRET")
        return None

    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(
                LWA_TOKEN_URL,
                data=payload,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            logger.error("Token request failed on attempt %s/%s: %s", attempt, MAX_RETRIES, exc)
            continue

        if response.status_code != 200:
            logger.warning(
                "Token request returned HTTP %s on attempt %s/%s",
                response.status_code,
                attempt,
                MAX_RETRIES,
            )
            continue

        body = response.json()
        access_token = str(body.get("access_token", "")).strip()
        expires_in = int(body.get("expires_in", 1800) or 1800)
        if not access_token:
            logger.warning("Token response was missing access_token on attempt %s/%s", attempt, MAX_RETRIES)
            continue

        expiry_epoch = int(time.time()) + max(expires_in, 300)
        try:
            _write_cached_token(access_token, expiry_epoch)
        except OSError as exc:
            logger.warning("Token cache write failed: %s", exc)
        return access_token

    logger.error("Failed to obtain access token after %s attempts.", MAX_RETRIES)
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    token = get_access_token()
    if token:
        logger.info("Token obtained successfully.")
    else:
        logger.error("Failed to retrieve token.")
