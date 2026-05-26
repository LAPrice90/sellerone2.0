from __future__ import annotations

import json
import os
import random
import signal
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests
from requests.exceptions import ConnectionError, ConnectTimeout, ReadTimeout, SSLError

try:
    from scripts.api.spapi_signed import sign_spapi_request
except ModuleNotFoundError:
    from api.spapi_signed import sign_spapi_request

OUT = Path("out")
LOCK_PATH = OUT / "locks" / "spapi.lock"
LOCK_ARCHIVE_DIR = OUT / "locks" / "archive"
RATE_STATE_PATH = OUT / "api_rate_state.json"
CALL_LOG_PATH = OUT / "api_call_log.jsonl"
THROTTLE_LOG_PATH = OUT / "api_throttle.log"
DEFAULT_TIMEOUT = (10.0, 30.0)  # connect, read
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_BASE_SECONDS = 1.0
ITEM_OFFERS_ENDPOINT = "products_pricing_get_item_offers"
ITEM_OFFERS_MIN_INTERVAL_SEC = float(os.environ.get("SPAPI_ITEM_OFFERS_MIN_INTERVAL_SEC", "2.5") or 2.5)
ITEM_OFFERS_LOCK_STALE_SECONDS = 120.0
ITEM_OFFERS_LOCK_WAIT_SECONDS = 180.0
ITEM_OFFERS_LOCK_POLL_SECONDS = 0.1
SPAPI_LOCK_STALE_SECONDS = float(os.environ.get("SPAPI_LOCK_STALE_SECONDS", "600") or 600.0)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_time_time() -> float:
    # Rare CPython/system-level glitches can raise SystemError from time.time().
    # Retry briefly so one transient does not abort an H cycle.
    for attempt in range(3):
        try:
            return time.time()
        except SystemError:
            if attempt >= 2:
                raise
            time.sleep(0.05)
    return time.time()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def load_rate_state() -> Dict[str, Dict[str, Any]]:
    state = _read_json(RATE_STATE_PATH, default={})
    if isinstance(state, dict):
        return state
    return {}


def save_rate_state(state: Dict[str, Dict[str, Any]]) -> None:
    _write_json(RATE_STATE_PATH, state)


def append_call_log(entry: Dict[str, Any]) -> None:
    CALL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CALL_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=True) + "\n")


def append_throttle_log_line(line: str) -> None:
    THROTTLE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with THROTTLE_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line.strip() + "\n")


def _target_from_url(url: str) -> str:
    try:
        path = urlparse(url).path
    except Exception:
        return ""
    marker = "/products/pricing/v0/items/"
    if marker not in path:
        return ""
    tail = path.split(marker, 1)[1]
    return tail.split("/", 1)[0].strip()


def _header_value(headers: Dict[str, Any], key: str) -> str:
    for k, v in headers.items():
        if str(k).lower() == key.lower():
            return str(v)
    return ""


def _parse_retry_after_seconds(raw: str) -> float | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        val = float(text)
    except Exception:
        return None
    if val <= 0:
        return None
    return val


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def _read_lock_payload() -> Dict[str, Any]:
    raw = _read_json(LOCK_PATH, default={})
    if isinstance(raw, dict):
        return raw
    return {}


def _archive_spapi_lock(payload: Dict[str, Any], reason: str) -> None:
    try:
        if not LOCK_PATH.exists():
            return
        LOCK_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive = LOCK_ARCHIVE_DIR / f"spapi.lock.{stamp}"
        suffix = 1
        while archive.exists():
            suffix += 1
            archive = LOCK_ARCHIVE_DIR / f"spapi.lock.{stamp}.{suffix}"
        archive_payload = dict(payload or {})
        archive_payload.setdefault("archived_utc", _utc_now())
        archive_payload.setdefault("archive_reason", str(reason or "unknown"))
        archive.write_text(json.dumps(archive_payload, ensure_ascii=True, indent=2), encoding="utf-8")
        LOCK_PATH.unlink(missing_ok=True)
    except Exception:
        # Best effort only; lock lifecycle must not break call paths.
        try:
            LOCK_PATH.unlink(missing_ok=True)
        except Exception:
            pass


def _terminate_pid(pid: int) -> bool:
    try:
        os.kill(int(pid), signal.SIGTERM)
    except Exception:
        return not _pid_alive(pid)
    for _ in range(20):
        if not _pid_alive(pid):
            return True
        time.sleep(0.2)
    return not _pid_alive(pid)


def _endpoint_lock_path(endpoint: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in str(endpoint).strip().lower())
    return OUT / "locks" / f"spapi_{safe}.lock"


def _acquire_endpoint_lock(endpoint: str) -> Path | None:
    if endpoint != ITEM_OFFERS_ENDPOINT:
        return None
    lock_path = _endpoint_lock_path(endpoint)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = _safe_time_time() + ITEM_OFFERS_LOCK_WAIT_SECONDS
    payload = {
        "endpoint": endpoint,
        "pid": os.getpid(),
        "acquired_utc": _utc_now(),
        "acquired_ts": _safe_time_time(),
    }
    lock_text = json.dumps(payload, ensure_ascii=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    while True:
        try:
            fd = os.open(str(lock_path), flags)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(lock_text)
            return lock_path
        except FileExistsError:
            existing = _read_json(lock_path, default={})
            pid_val = existing.get("pid") if isinstance(existing, dict) else None
            acquired_ts = existing.get("acquired_ts") if isinstance(existing, dict) else None
            try:
                existing_pid = int(pid_val)
            except Exception:
                existing_pid = None
            try:
                existing_acquired_ts = float(acquired_ts)
            except Exception:
                existing_acquired_ts = 0.0
            stale = (_safe_time_time() - existing_acquired_ts) >= ITEM_OFFERS_LOCK_STALE_SECONDS if existing_acquired_ts > 0 else False
            if existing_pid is not None and not _pid_alive(existing_pid):
                try:
                    lock_path.unlink()
                except Exception:
                    pass
                continue
            if stale:
                try:
                    lock_path.unlink()
                except Exception:
                    pass
                continue
            if _safe_time_time() >= deadline:
                raise TimeoutError(f"endpoint lock timeout endpoint={endpoint}")
            time.sleep(ITEM_OFFERS_LOCK_POLL_SECONDS)


def _release_endpoint_lock(lock_path: Path | None) -> None:
    if lock_path is None:
        return
    try:
        existing = _read_json(lock_path, default={})
        pid_val = existing.get("pid") if isinstance(existing, dict) else None
        try:
            existing_pid = int(pid_val)
        except Exception:
            existing_pid = None
        if existing_pid is None or existing_pid == os.getpid() or not _pid_alive(existing_pid):
            lock_path.unlink(missing_ok=True)
    except Exception:
        pass


def acquire_spapi_lock(run_id: str, script_name: str) -> bool:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    now_ts = _safe_time_time()
    payload = {
        "run_id": run_id,
        "script_name": script_name,
        "acquired_utc": _utc_now(),
        "pid": os.getpid(),
        "acquired_ts": now_ts,
        "heartbeat_ts": now_ts,
    }
    lock_text = json.dumps(payload, ensure_ascii=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(LOCK_PATH), flags)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(lock_text)
        return True
    except FileExistsError:
        existing = _read_lock_payload()
        if not existing:
            _archive_spapi_lock(existing, reason="invalid_or_unreadable_payload")
            try:
                fd = os.open(str(LOCK_PATH), flags)
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(lock_text)
                return True
            except Exception:
                return False
        pid = existing.get("pid")
        try:
            pid = int(pid)
        except Exception:
            pid = None

        acquired_ts_raw = existing.get("heartbeat_ts", existing.get("acquired_ts", 0.0))
        try:
            acquired_ts = float(acquired_ts_raw or 0.0)
        except Exception:
            acquired_ts = 0.0
        lock_age_seconds = max((_safe_time_time() - acquired_ts), 0.0) if acquired_ts > 0 else 0.0
        stale = bool(acquired_ts > 0 and lock_age_seconds >= max(SPAPI_LOCK_STALE_SECONDS, 60.0))

        if stale:
            _archive_spapi_lock(existing, reason=f"stale_lock age_seconds={int(lock_age_seconds)}")
            try:
                fd = os.open(str(LOCK_PATH), flags)
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(lock_text)
                return True
            except Exception:
                return False

        if pid is not None and not _pid_alive(pid):
            # dead owner: archive and retry once
            _archive_spapi_lock(existing, reason=f"dead_pid pid={pid}")
            try:
                fd = os.open(str(LOCK_PATH), flags)
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(lock_text)
                return True
            except Exception:
                return False

        steal_lock_enabled = False
        try:
            steal_lock_enabled = str(os.environ.get("SPAPI_STEAL_LOCK", "0")).strip() == "1"
        except OSError:
            steal_lock_enabled = False
        if pid is not None and steal_lock_enabled:
            if _terminate_pid(pid):
                _archive_spapi_lock(existing, reason=f"stolen_lock pid={pid}")
                try:
                    fd = os.open(str(LOCK_PATH), flags)
                    with os.fdopen(fd, "w", encoding="utf-8") as fh:
                        fh.write(lock_text)
                    return True
                except Exception:
                    return False
        return False


def release_spapi_lock() -> None:
    if LOCK_PATH.exists():
        try:
            existing = _read_lock_payload()
            pid = existing.get("pid")
            try:
                pid = int(pid)
            except Exception:
                pid = None
            if pid is None or pid == os.getpid() or not _pid_alive(pid):
                LOCK_PATH.unlink(missing_ok=True)
        except Exception:
            pass


@dataclass
class SpApiCallContext:
    run_id: str
    script_name: str
    endpoint: str
    marketplace: str
    sku_count: int


def spapi_get(
    *,
    ctx: SpApiCallContext,
    url: str,
    spapi_base_url: str,
    headers: Dict[str, str],
    params: Optional[Dict[str, str]] = None,
    timeout: float | tuple[float, float] = DEFAULT_TIMEOUT,
    min_interval_sec: float = 1.0,
    max_retries: int = DEFAULT_MAX_ATTEMPTS,
) -> requests.Response:
    return _spapi_request(
        ctx=ctx,
        method="GET",
        url=url,
        spapi_base_url=spapi_base_url,
        headers=headers,
        params=params,
        timeout=timeout,
        min_interval_sec=min_interval_sec,
        max_retries=max_retries,
        body="",
    )


def spapi_patch_json(
    *,
    ctx: SpApiCallContext,
    url: str,
    spapi_base_url: str,
    headers: Dict[str, str],
    body: str,
    params: Optional[Dict[str, str]] = None,
    timeout: float | tuple[float, float] = DEFAULT_TIMEOUT,
    min_interval_sec: float = 1.0,
    max_retries: int = DEFAULT_MAX_ATTEMPTS,
) -> requests.Response:
    return _spapi_request(
        ctx=ctx,
        method="PATCH",
        url=url,
        spapi_base_url=spapi_base_url,
        headers=headers,
        params=params,
        timeout=timeout,
        min_interval_sec=min_interval_sec,
        max_retries=max_retries,
        body=body,
    )


def spapi_put_json(
    *,
    ctx: SpApiCallContext,
    url: str,
    spapi_base_url: str,
    headers: Dict[str, str],
    body: str,
    params: Optional[Dict[str, str]] = None,
    timeout: float | tuple[float, float] = DEFAULT_TIMEOUT,
    min_interval_sec: float = 1.0,
    max_retries: int = DEFAULT_MAX_ATTEMPTS,
) -> requests.Response:
    return _spapi_request(
        ctx=ctx,
        method="PUT",
        url=url,
        spapi_base_url=spapi_base_url,
        headers=headers,
        params=params,
        timeout=timeout,
        min_interval_sec=min_interval_sec,
        max_retries=max_retries,
        body=body,
    )


def spapi_post_json(
    *,
    ctx: SpApiCallContext,
    url: str,
    spapi_base_url: str,
    headers: Dict[str, str],
    body: str,
    params: Optional[Dict[str, str]] = None,
    timeout: float | tuple[float, float] = DEFAULT_TIMEOUT,
    min_interval_sec: float = 1.0,
    max_retries: int = DEFAULT_MAX_ATTEMPTS,
) -> requests.Response:
    return _spapi_request(
        ctx=ctx,
        method="POST",
        url=url,
        spapi_base_url=spapi_base_url,
        headers=headers,
        params=params,
        timeout=timeout,
        min_interval_sec=min_interval_sec,
        max_retries=max_retries,
        body=body,
    )


def _spapi_request(
    *,
    ctx: SpApiCallContext,
    method: str,
    url: str,
    spapi_base_url: str,
    headers: Dict[str, str],
    params: Optional[Dict[str, str]],
    timeout: float | tuple[float, float] | None,
    min_interval_sec: float,
    max_retries: int,
    body: str,
) -> requests.Response:
    def _normalize_timeout(value: float | tuple[float, float] | None) -> float | tuple[float, float]:
        if value is None:
            return DEFAULT_TIMEOUT
        if isinstance(value, tuple):
            if len(value) >= 2:
                try:
                    connect = float(value[0])
                    read = float(value[1])
                    if connect > 0 and read > 0:
                        return (connect, read)
                except Exception:
                    return DEFAULT_TIMEOUT
            return DEFAULT_TIMEOUT
        try:
            scalar = float(value)
        except Exception:
            return DEFAULT_TIMEOUT
        if scalar <= 0:
            return DEFAULT_TIMEOUT
        connect_timeout = min(max(scalar, 1.0), DEFAULT_TIMEOUT[0])
        read_timeout = max(scalar, DEFAULT_TIMEOUT[1])
        return (connect_timeout, read_timeout)

    timeout = _normalize_timeout(timeout)
    max_attempts = max(int(max_retries), 1)
    if ctx.endpoint == ITEM_OFFERS_ENDPOINT:
        min_interval_sec = max(float(min_interval_sec), float(ITEM_OFFERS_MIN_INTERVAL_SEC))
    state = load_rate_state()
    endpoint_state = state.get(ctx.endpoint, {})

    target = _target_from_url(url)
    spapi_lock_acquired = acquire_spapi_lock(ctx.run_id, ctx.script_name)
    try:
        attempt = 0
        while True:
            attempt += 1
            retries = max(attempt - 1, 0)
            throttled = False
            backoff_seconds = 0.0
            now = _safe_time_time()
            backoff_until = float(endpoint_state.get("backoff_until", 0.0) or 0.0)
            if backoff_until > now:
                time.sleep(backoff_until - now)
            now = _safe_time_time()
            last_call_time = float(endpoint_state.get("last_call_time", 0.0) or 0.0)
            if last_call_time > 0:
                wait_for_interval = (last_call_time + float(min_interval_sec)) - now
                if wait_for_interval > 0:
                    time.sleep(wait_for_interval)

            signed = sign_spapi_request(method, url, spapi_base_url, headers.copy(), params=params, body=body)
            signed_url = signed.pop("x-signed-url")
            endpoint_lock_path: Path | None = None
            try:
                endpoint_lock_path = _acquire_endpoint_lock(ctx.endpoint)
                if method.upper() == "GET":
                    resp = requests.get(signed_url, headers=signed, timeout=timeout)
                elif method.upper() == "POST":
                    resp = requests.post(signed_url, headers=signed, data=body, timeout=timeout)
                elif method.upper() == "PUT":
                    resp = requests.put(signed_url, headers=signed, data=body, timeout=timeout)
                elif method.upper() == "PATCH":
                    resp = requests.patch(signed_url, headers=signed, data=body, timeout=timeout)
                else:
                    raise ValueError(f"Unsupported SP-API method: {method}")
            except (ConnectTimeout, ReadTimeout, SSLError, ConnectionError, TimeoutError) as exc:
                if attempt >= max_attempts:
                    raise
                backoff_seconds = min(
                    60.0,
                    (DEFAULT_BACKOFF_BASE_SECONDS * (2.0 ** retries)) + random.uniform(0.0, 0.25),
                )
                endpoint_state["backoff_until"] = _safe_time_time() + backoff_seconds
                state[ctx.endpoint] = endpoint_state
                save_rate_state(state)
                append_throttle_log_line(
                    f"{_utc_now()} throttle endpoint={ctx.endpoint} target={target or '-'} "
                    f"attempt={attempt}/{max_attempts} reason=REQUEST_{type(exc).__name__} "
                    f"sleep_seconds={backoff_seconds:.2f} retry_after=- rate_limit=-"
                )
                append_call_log(
                    {
                        "run_id": ctx.run_id,
                        "timestamp_utc": _utc_now(),
                        "script_name": ctx.script_name,
                        "endpoint": ctx.endpoint,
                        "marketplace": ctx.marketplace,
                        "sku_count": int(ctx.sku_count),
                        "http_status": "",
                        "retries": retries,
                        "throttled": False,
                        "backoff_seconds": backoff_seconds,
                        "error_code": f"REQUEST_{type(exc).__name__}",
                        "target": target,
                        "retry_after": "",
                        "rate_limit": "",
                    }
                )
                time.sleep(backoff_seconds)
                continue
            finally:
                _release_endpoint_lock(endpoint_lock_path)

            now_after = _safe_time_time()
            endpoint_state["last_call_time"] = now_after
            endpoint_state["recent_request_count"] = int(endpoint_state.get("recent_request_count", 0) or 0) + 1
            endpoint_state["backoff_until"] = float(endpoint_state.get("backoff_until", 0.0) or 0.0)

            status = int(resp.status_code)
            if status in (429, 500, 502, 503, 504) and attempt < max_attempts:
                throttled = status == 429
                retry_after_header = _header_value(dict(resp.headers), "Retry-After")
                rate_limit_header = _header_value(dict(resp.headers), "x-amzn-RateLimit-Limit")
                retry_after_seconds = _parse_retry_after_seconds(retry_after_header)
                if retry_after_seconds is not None:
                    backoff_seconds = retry_after_seconds
                else:
                    backoff_seconds = min(
                        60.0,
                        (DEFAULT_BACKOFF_BASE_SECONDS * (2.0 ** retries)) + random.uniform(0.0, 0.25),
                    )
                endpoint_state["backoff_until"] = _safe_time_time() + backoff_seconds
                state[ctx.endpoint] = endpoint_state
                save_rate_state(state)
                if status == 429:
                    append_throttle_log_line(
                        f"{_utc_now()} throttle endpoint={ctx.endpoint} target={target or '-'} "
                        f"attempt={attempt}/{max_attempts} reason=HTTP_429 "
                        f"sleep_seconds={backoff_seconds:.2f} "
                        f"retry_after={retry_after_header or '-'} "
                        f"rate_limit={rate_limit_header or '-'}"
                    )
                append_call_log(
                    {
                        "run_id": ctx.run_id,
                        "timestamp_utc": _utc_now(),
                        "script_name": ctx.script_name,
                        "endpoint": ctx.endpoint,
                        "marketplace": ctx.marketplace,
                        "sku_count": int(ctx.sku_count),
                        "http_status": status,
                        "retries": retries,
                        "throttled": throttled,
                        "backoff_seconds": backoff_seconds,
                        "error_code": f"HTTP_{status}",
                        "target": target,
                        "retry_after": retry_after_header,
                        "rate_limit": rate_limit_header,
                    }
                )
                time.sleep(backoff_seconds)
                continue

            if status >= 400:
                error_code = f"HTTP_{status}"
            else:
                error_code = ""
            if status == 429:
                append_throttle_log_line(
                    f"{_utc_now()} throttle endpoint={ctx.endpoint} target={target or '-'} "
                    f"attempt={attempt}/{max_attempts} reason=HTTP_429_FINAL "
                    f"sleep_seconds=0.00 "
                    f"retry_after={_header_value(dict(resp.headers), 'Retry-After') or '-'} "
                    f"rate_limit={_header_value(dict(resp.headers), 'x-amzn-RateLimit-Limit') or '-'}"
                )
            state[ctx.endpoint] = endpoint_state
            save_rate_state(state)
            append_call_log(
                {
                    "run_id": ctx.run_id,
                    "timestamp_utc": _utc_now(),
                    "script_name": ctx.script_name,
                    "endpoint": ctx.endpoint,
                    "marketplace": ctx.marketplace,
                    "sku_count": int(ctx.sku_count),
                    "http_status": status,
                    "retries": retries,
                    "throttled": throttled,
                    "backoff_seconds": backoff_seconds,
                    "error_code": error_code,
                    "target": target,
                    "retry_after": _header_value(dict(resp.headers), "Retry-After"),
                    "rate_limit": _header_value(dict(resp.headers), "x-amzn-RateLimit-Limit"),
                }
            )
            return resp
    finally:
        if spapi_lock_acquired:
            release_spapi_lock()

