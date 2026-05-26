from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_lock_fields(payload: object) -> Dict[str, str]:
    out: Dict[str, str] = {}
    text = str(payload or "").strip()
    if not text:
        return out
    for part in text.split("|"):
        token = str(part or "").strip()
        if not token:
            continue
        if "=" in token:
            key, value = token.split("=", 1)
            out[str(key or "").strip()] = str(value or "").strip()
            continue
        if "owner" not in out:
            out["owner"] = token
    return out


def parse_lock_pid(payload: object) -> int | None:
    fields = parse_lock_fields(payload)
    pid_text = str(fields.get("pid", "")).strip()
    if not pid_text:
        return None
    try:
        return int(pid_text)
    except Exception:
        return None


def build_lock_payload(
    *,
    owner: str,
    pid: int,
    fields: Dict[str, object] | None = None,
    start_utc: str | None = None,
    heartbeat_utc: str | None = None,
) -> str:
    start_ts = str(start_utc or "").strip() or utc_now_iso()
    heartbeat_ts = str(heartbeat_utc or "").strip() or utc_now_iso()
    parts = [
        str(owner or "").strip() or "owner",
        f"pid={int(pid)}",
        f"start={start_ts}",
        f"heartbeat={heartbeat_ts}",
    ]
    if fields:
        for key, value in fields.items():
            key_text = str(key or "").strip()
            if not key_text:
                continue
            parts.append(f"{key_text}={str(value or '').strip()}")
    return "|".join(parts) + "\n"


def replace_lock_heartbeat(payload: object, *, heartbeat_utc: str | None = None) -> str:
    fields = parse_lock_fields(payload)
    if not fields:
        return ""
    owner = str(fields.get("owner", "")).strip() or "owner"
    pid = parse_lock_pid(payload)
    if pid is None:
        return ""
    start = str(fields.get("start", "")).strip() or utc_now_iso()
    heartbeat = str(heartbeat_utc or "").strip() or utc_now_iso()
    rebuilt_fields: Dict[str, object] = {}
    for key, value in fields.items():
        if key in {"owner", "pid", "start", "heartbeat"}:
            continue
        rebuilt_fields[key] = value
    return build_lock_payload(
        owner=owner,
        pid=pid,
        fields=rebuilt_fields,
        start_utc=start,
        heartbeat_utc=heartbeat,
    )
