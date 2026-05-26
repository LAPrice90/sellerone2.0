from __future__ import annotations

import json
import random
import re
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib import error as urllib_error
from urllib import request as urllib_request


TRANSIENT_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _probe_endpoint(url: str, *, timeout_seconds: float) -> dict[str, Any]:
    endpoint = str(url or "").strip()
    if endpoint == "":
        return {"url": endpoint, "ok": False, "status_code": "", "error": "blank_endpoint", "checked_utc": _utc_now_text()}
    req = urllib_request.Request(endpoint, method="GET")
    try:
        with urllib_request.urlopen(req, timeout=max(float(timeout_seconds), 1.0)) as resp:
            status_code = int(getattr(resp, "status", 0) or 0)
            return {
                "url": endpoint,
                "ok": status_code > 0,
                "status_code": str(status_code),
                "error": "",
                "checked_utc": _utc_now_text(),
            }
    except urllib_error.HTTPError as exc:
        status_code = int(getattr(exc, "code", 0) or 0)
        # HTTP response means internet path is reachable even if auth/rate errors happen.
        return {
            "url": endpoint,
            "ok": status_code > 0,
            "status_code": str(status_code),
            "error": f"http_error_{status_code}",
            "checked_utc": _utc_now_text(),
        }
    except (urllib_error.URLError, TimeoutError, socket.timeout, socket.gaierror, OSError) as exc:
        return {
            "url": endpoint,
            "ok": False,
            "status_code": "",
            "error": exc.__class__.__name__,
            "checked_utc": _utc_now_text(),
        }


def assess_network_health(endpoints: Iterable[str], *, timeout_seconds: float = 5.0) -> dict[str, Any]:
    checks = [_probe_endpoint(url, timeout_seconds=timeout_seconds) for url in endpoints]
    total = len(checks)
    success = sum(1 for row in checks if bool(row.get("ok")))
    if total <= 0:
        status = "AMBER"
    elif success == total:
        status = "GREEN"
    elif success == 0:
        status = "RED"
    else:
        status = "AMBER"
    return {
        "generated_utc": _utc_now_text(),
        "status": status,
        "success_count": success,
        "total_count": total,
        "checks": checks,
    }


def write_network_health(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def wait_for_network_recovery(
    *,
    endpoints: Iterable[str],
    max_wait_seconds: float,
    recheck_seconds: float = 30.0,
    probe_timeout_seconds: float = 5.0,
    acceptable_statuses: set[str] | None = None,
    health_path: Path | None = None,
    log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    target_statuses = acceptable_statuses or {"GREEN", "AMBER"}
    start = time.monotonic()
    attempts = 0
    while True:
        attempts += 1
        snapshot = assess_network_health(endpoints, timeout_seconds=probe_timeout_seconds)
        snapshot["wait_attempt"] = attempts
        snapshot["max_wait_seconds"] = float(max_wait_seconds)
        snapshot["elapsed_seconds"] = round(time.monotonic() - start, 2)
        if health_path is not None:
            write_network_health(health_path, snapshot)
        if str(snapshot.get("status")) in target_statuses:
            return snapshot
        elapsed = time.monotonic() - start
        remaining = float(max_wait_seconds) - elapsed
        if remaining <= 0:
            raise TimeoutError("network_recovery_timeout")
        sleep_seconds = min(max(float(recheck_seconds), 1.0), remaining)
        if log is not None:
            log(
                "network_wait "
                f"status={snapshot.get('status', '')} "
                f"success={snapshot.get('success_count', 0)}/{snapshot.get('total_count', 0)} "
                f"sleep_seconds={sleep_seconds:.1f}"
            )
        time.sleep(sleep_seconds)


def _extract_http_status_code(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    if response is not None:
        code = getattr(response, "status_code", None)
        if isinstance(code, int):
            return code
        try:
            return int(str(code).strip())
        except Exception:
            pass
    code_attr = getattr(exc, "code", None)
    if isinstance(code_attr, int):
        return code_attr
    try:
        return int(str(code_attr).strip())
    except Exception:
        pass
    text = str(exc)
    match = re.search(r"\[(\d{3})\]", text)
    if match is not None:
        try:
            return int(match.group(1))
        except Exception:
            return None
    return None


def is_transient_network_error(exc: Exception) -> tuple[bool, str]:
    code = _extract_http_status_code(exc)
    if code in TRANSIENT_HTTP_STATUS_CODES:
        return True, f"http_{code}"
    name = exc.__class__.__name__.lower()
    if "timeout" in name:
        return True, name
    if "connection" in name:
        return True, name
    if "ssl" in name:
        return True, name
    if isinstance(exc, (TimeoutError, ConnectionError, socket.timeout, socket.gaierror)):
        return True, exc.__class__.__name__
    if isinstance(exc, OSError):
        return True, exc.__class__.__name__
    return False, "non_transient"


def call_with_transient_retry(
    *,
    action: Callable[[], Any],
    operation_name: str,
    max_wait_seconds: float = 1800.0,
    initial_backoff_seconds: float = 5.0,
    max_backoff_seconds: float = 120.0,
    jitter_ratio: float = 0.2,
    log: Callable[[str], None] | None = None,
) -> Any:
    start = time.monotonic()
    attempt = 0
    while True:
        attempt += 1
        try:
            return action()
        except Exception as exc:
            transient, reason = is_transient_network_error(exc)
            elapsed = time.monotonic() - start
            if (not transient) or elapsed >= float(max_wait_seconds):
                raise
            exp_index = max(attempt - 1, 0)
            backoff = min(float(initial_backoff_seconds) * (2.0 ** exp_index), float(max_backoff_seconds))
            jitter = random.uniform(0.0, max(backoff * float(jitter_ratio), 0.0))
            sleep_seconds = min(backoff + jitter, max(float(max_wait_seconds) - elapsed, 0.1))
            if log is not None:
                log(
                    f"retry operation={operation_name} attempt={attempt} reason={reason} "
                    f"sleep_seconds={sleep_seconds:.1f} error={exc.__class__.__name__}"
                )
            time.sleep(max(sleep_seconds, 0.1))
