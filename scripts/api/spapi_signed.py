"""
Signed SP-API request helpers (SigV4).
"""

from __future__ import annotations

import os
import platform
import random
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional
import hashlib
from urllib.parse import urlencode, urlparse, urlunparse

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.config import Config
from botocore.credentials import Credentials
from botocore.exceptions import ClientError, ConnectTimeoutError, EndpointConnectionError, ReadTimeoutError, SSLError


REGION_MAP = {
    "sellingpartnerapi-na.amazon.com": "us-east-1",
    "sellingpartnerapi-eu.amazon.com": "eu-west-1",
    "sellingpartnerapi-fe.amazon.com": "us-west-2",
}
OUT = Path("out")
AUTH_LOG_PATH = OUT / "api_auth.log"
STS_CONNECT_TIMEOUT_SECONDS = 10
STS_READ_TIMEOUT_SECONDS = 30
STS_MAX_ATTEMPTS = 3
STS_REFRESH_MARGIN_MINUTES = 5
STS_ASSUME_OUTER_ATTEMPTS = 3
STS_ASSUME_BACKOFF_BASE_SECONDS = 0.5
STS_MIN_REFRESH_INTERVAL_SECONDS = 5
_STS_CONFIG = Config(
    connect_timeout=STS_CONNECT_TIMEOUT_SECONDS,
    read_timeout=STS_READ_TIMEOUT_SECONDS,
    retries={"max_attempts": STS_MAX_ATTEMPTS, "mode": "standard"},
)
_ASSUMED_ROLE_CACHE: dict[str, Any] = {}
_ASSUMED_ROLE_LOCK = threading.Lock()
_STS_CLIENT_CACHE: dict[str, Any] = {}
_STS_CLIENT_LOCK = threading.Lock()


def _region_from_base(spapi_base_url: str) -> str:
    for host, region in REGION_MAP.items():
        if host in spapi_base_url:
            return region
    return os.environ.get("AWS_REGION", "eu-west-1")


@dataclass
class SpApiAuth:
    access_key: str
    secret_key: str
    session_token: Optional[str]
    region: str


def _append_auth_log(message: str) -> None:
    AUTH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUTH_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n")


def _to_utc_datetime(value: object) -> Optional[datetime]:
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except Exception:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _sts_client():
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "eu-west-1"
    with _STS_CLIENT_LOCK:
        cached = _STS_CLIENT_CACHE.get(region)
        if cached is not None:
            return cached
        try:
            client = boto3.client("sts", config=_STS_CONFIG, region_name=region)
        except KeyboardInterrupt as exc:
            # Narrow bootstrap fallback for Windows platform detection interruptions.
            _append_auth_log("STS_CLIENT_BOOTSTRAP_INTERRUPTED using_safe_user_agent_fallback=1")
            client = _sts_client_safe_user_agent(region)
        _STS_CLIENT_CACHE[region] = client
        return client


def _sts_client_safe_user_agent(region: str):
    import botocore.useragent as botocore_useragent

    original = botocore_useragent.UserAgentString.__dict__["from_environment"]

    @classmethod
    def _safe_from_environment(cls):
        # Avoid Windows WMI probing during emergency bootstrap fallback.
        return cls(
            platform_name=str(os.environ.get("OS", "Windows_NT")),
            platform_version="",
            platform_machine="",
            python_version=platform.python_version(),
            python_implementation=platform.python_implementation(),
            execution_env=os.environ.get("AWS_EXECUTION_ENV"),
            crt_version=None,
        )

    botocore_useragent.UserAgentString.from_environment = _safe_from_environment
    try:
        return boto3.session.Session().client("sts", config=_STS_CONFIG, region_name=region)
    finally:
        botocore_useragent.UserAgentString.from_environment = original


def _assume_role() -> Optional[Dict[str, Any]]:
    role_arn = os.environ.get("AWS_ROLE_ARN")
    if not role_arn:
        return None
    external_id = os.environ.get("AWS_EXTERNAL_ID") or None
    sts = _sts_client()
    params = {"RoleArn": role_arn, "RoleSessionName": "spapi-session"}
    if external_id:
        params["ExternalId"] = external_id
    duration_seconds_raw = os.environ.get("SPAPI_STS_DURATION_SECONDS", "").strip()
    if duration_seconds_raw:
        try:
            duration_seconds = int(float(duration_seconds_raw))
            duration_seconds = max(900, min(duration_seconds, 3600))
            params["DurationSeconds"] = duration_seconds
        except Exception:
            pass
    last_exc: Exception | None = None
    for attempt in range(1, STS_ASSUME_OUTER_ATTEMPTS + 1):
        try:
            resp = sts.assume_role(**params)
            creds = resp["Credentials"]
            return {
                "access_key": creds["AccessKeyId"],
                "secret_key": creds["SecretAccessKey"],
                "session_token": creds["SessionToken"],
                "expiration": _to_utc_datetime(creds.get("Expiration")),
                "cached_at_epoch": time.time(),
            }
        except (EndpointConnectionError, ConnectTimeoutError, ReadTimeoutError, SSLError, ClientError) as exc:
            last_exc = exc
            if attempt >= STS_ASSUME_OUTER_ATTEMPTS:
                break
            backoff = (STS_ASSUME_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))) + random.uniform(0.0, 0.2)
            _append_auth_log(
                f"STS_RETRY attempt={attempt}/{STS_ASSUME_OUTER_ATTEMPTS} sleep_seconds={backoff:.2f} "
                f"error={type(exc).__name__}"
            )
            time.sleep(backoff)
    if last_exc is not None:
        raise RuntimeError(f"STS assume_role failed after {STS_ASSUME_OUTER_ATTEMPTS} attempts: {last_exc}") from last_exc
    return None


def get_spapi_auth(spapi_base_url: str) -> SpApiAuth:
    region = _region_from_base(spapi_base_url)
    role_arn = os.environ.get("AWS_ROLE_ARN")
    external_id = os.environ.get("AWS_EXTERNAL_ID") or ""
    assumed = None
    if role_arn:
        cache_key = f"{role_arn}|{external_id}"
        now_utc = datetime.now(timezone.utc)
        with _ASSUMED_ROLE_LOCK:
            cached = _ASSUMED_ROLE_CACHE.get(cache_key)
            if isinstance(cached, dict):
                expires_at = _to_utc_datetime(cached.get("expiration"))
                cached_at_epoch = float(cached.get("cached_at_epoch", 0.0) or 0.0)
                too_fresh_to_refresh = (time.time() - cached_at_epoch) < STS_MIN_REFRESH_INTERVAL_SECONDS
                if expires_at is not None and (expires_at - now_utc) > timedelta(minutes=STS_REFRESH_MARGIN_MINUTES):
                    _append_auth_log("STS_CACHE_HIT")
                    assumed = cached
                elif too_fresh_to_refresh:
                    # Avoid refresh storms from concurrent callers near expiry.
                    assumed = cached
            if assumed is None:
                assumed = _assume_role()
                if assumed:
                    _ASSUMED_ROLE_CACHE[cache_key] = assumed
                    expires_at = _to_utc_datetime(assumed.get("expiration"))
                    exp_text = expires_at.isoformat() if expires_at is not None else "-"
                    _append_auth_log(f"STS_REFRESH expiration_utc={exp_text}")
    if assumed:
        return SpApiAuth(
            access_key=assumed["access_key"],
            secret_key=assumed["secret_key"],
            session_token=assumed.get("session_token"),
            region=region,
        )
    access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    session_token = os.environ.get("AWS_SESSION_TOKEN")
    if not access_key or not secret_key:
        raise RuntimeError("Missing AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY for SP-API signing")
    return SpApiAuth(access_key=access_key, secret_key=secret_key, session_token=session_token, region=region)


def sign_spapi_request(
    method: str,
    url: str,
    spapi_base_url: str,
    headers: Dict[str, str],
    body: str = "",
    params: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    auth = get_spapi_auth(spapi_base_url)
    if params:
        qs = urlencode(params, doseq=True)
        url = f"{url}?{qs}"
    # Normalize path (no trailing slash) before signing.
    parsed = urlparse(url)
    clean_path = parsed.path.rstrip("/")
    url = urlunparse(parsed._replace(path=clean_path))
    # Ensure Host header is set for signing.
    if "Host" not in headers and "host" not in headers:
        host = url.split("://", 1)[-1].split("/", 1)[0]
        headers["Host"] = host
    # Required for strict gateways; hash body when present.
    if "x-amz-content-sha256" not in headers:
        if body:
            digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        else:
            digest = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        headers["x-amz-content-sha256"] = digest
    req = AWSRequest(method=method.upper(), url=url, data=body, headers=headers)
    creds = Credentials(auth.access_key, auth.secret_key, auth.session_token)
    SigV4Auth(creds, "execute-api", auth.region).add_auth(req)
    out = dict(req.headers)
    out["x-signed-url"] = url
    return out

