from __future__ import annotations

import json
import os
import signal
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests

try:
    from scripts.api.spapi_signed import sign_spapi_request
except ModuleNotFoundError:
    from api.spapi_signed import sign_spapi_request

OUT = Path("out")
LOCK_PATH = OUT / "locks" / "spapi.lock"
RATE_STATE_PATH = OUT / "api_rate_state.json"
CALL_LOG_PATH = OUT / "api_call_log.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def acquire_spapi_lock(run_id: str, script_name: str) -> bool:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"run_id": run_id, "script_name": script_name, "acquired_utc": _utc_now(), "pid": os.getpid()}
    lock_text = json.dumps(payload, ensure_ascii=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(LOCK_PATH), flags)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(lock_text)
        return True
    except FileExistsError:
        existing = _read_lock_payload()
        pid = existing.get("pid")
        try:
            pid = int(pid)
        except Exception:
            pid = None

        if pid is not None and not _pid_alive(pid):
            # stale lock: clear and retry once
            try:
                LOCK_PATH.unlink()
            except Exception:
                return False
            try:
                fd = os.open(str(LOCK_PATH), flags)
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(lock_text)
                return True
            except Exception:
                return False

        if pid is not None and os.environ.get("SPAPI_STEAL_LOCK", "0").strip() == "1":
            if _terminate_pid(pid):
                try:
                    LOCK_PATH.unlink()
                except Exception:
                    return False
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
            LOCK_PATH.unlink()
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
    timeout: int = 30,
    min_interval_sec: float = 1.0,
    max_retries: int = 2,
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
    timeout: int = 30,
    min_interval_sec: float = 1.0,
    max_retries: int = 2,
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


def spapi_post_json(
    *,
    ctx: SpApiCallContext,
    url: str,
    spapi_base_url: str,
    headers: Dict[str, str],
    body: str,
    params: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    min_interval_sec: float = 1.0,
    max_retries: int = 2,
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
    timeout: int,
    min_interval_sec: float,
    max_retries: int,
    body: str,
) -> requests.Response:
    state = load_rate_state()
    endpoint_state = state.get(ctx.endpoint, {})

    last_call_time = float(endpoint_state.get("last_call_time", 0.0) or 0.0)
    backoff_until = float(endpoint_state.get("backoff_until", 0.0) or 0.0)

    now = time.time()
    if backoff_until > now:
        time.sleep(backoff_until - now)
    now = time.time()
    if last_call_time > 0:
        wait_for_interval = (last_call_time + float(min_interval_sec)) - now
        if wait_for_interval > 0:
            time.sleep(wait_for_interval)

    retries = 0
    while True:
        throttled = False
        backoff_seconds = 0.0
        signed = sign_spapi_request(method, url, spapi_base_url, headers.copy(), params=params, body=body)
        signed_url = signed.pop("x-signed-url")
        if method.upper() == "GET":
            resp = requests.get(signed_url, headers=signed, timeout=timeout)
        elif method.upper() == "POST":
            resp = requests.post(signed_url, headers=signed, data=body, timeout=timeout)
        elif method.upper() == "PATCH":
            resp = requests.patch(signed_url, headers=signed, data=body, timeout=timeout)
        else:
            raise ValueError(f"Unsupported SP-API method: {method}")

        now_after = time.time()
        endpoint_state["last_call_time"] = now_after
        endpoint_state["recent_request_count"] = int(endpoint_state.get("recent_request_count", 0) or 0) + 1
        endpoint_state["backoff_until"] = float(endpoint_state.get("backoff_until", 0.0) or 0.0)

        status = int(resp.status_code)
        if status in (429, 500, 502, 503, 504) and retries < max_retries:
            throttled = status == 429
            retries += 1
            backoff_seconds = min(60.0, 2.0 * retries)
            endpoint_state["backoff_until"] = time.time() + backoff_seconds
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
                    "error_code": f"HTTP_{status}",
                }
            )
            time.sleep(backoff_seconds)
            continue

        if status >= 400:
            error_code = f"HTTP_{status}"
        else:
            error_code = ""
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
            }
        )
        return resp
