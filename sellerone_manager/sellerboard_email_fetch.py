from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paths import get_manager_paths
from .sellerboard_email_intake import (
    EMAIL_INTAKE_DIR_NAME,
    INBOX_REL_PATH,
    SOURCE_CONFIG_REL_PATH,
    DEFAULT_GMAIL_CLIENT_SECRET_REL_PATH,
    DEFAULT_GMAIL_LABEL,
    DEFAULT_GMAIL_TOKEN_REL_PATH,
    _load_source_config,
    _resolve_config_path,
    utc_now_text,
)
from .sellerboard_email_source_probe import _message_ts_utc, _service_or_status, _walk_parts


FETCH_MANIFEST_NAME = "b_sellerboard_email_fetch_manifest.json"


@dataclass(frozen=True)
class SellerboardEmailFetchResult:
    observed_utc: str
    status: str
    filename: str
    path: str
    size_bytes: int
    sha256: str
    source_mailbox: str
    auth_status: str
    message_id: str
    attachment_id: str
    message_ts_utc: str
    manifest_path: Path
    notes: str


def fetch_latest_sellerboard_email_attachment(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
    service: Any | None = None,
) -> SellerboardEmailFetchResult:
    paths = get_manager_paths(root)
    base = paths.root
    observed = observed_utc or utc_now_text()
    config = _load_source_config(base / SOURCE_CONFIG_REL_PATH)
    expected_mailbox = config["expected_source_mailbox"]
    label = config["gmail_label"] or DEFAULT_GMAIL_LABEL
    token_path = _resolve_config_path(base, config.get("gmail_token_path", DEFAULT_GMAIL_TOKEN_REL_PATH))
    client_path = _resolve_config_path(base, config.get("gmail_client_secret_path", DEFAULT_GMAIL_CLIENT_SECRET_REL_PATH))
    manifest_path = paths.output_dir / EMAIL_INTAKE_DIR_NAME / FETCH_MANIFEST_NAME
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    gmail, auth_status, auth_notes = _service_or_status(
        base=base,
        token_path=token_path,
        client_path=client_path,
        service=service,
    )
    if gmail is None:
        return _write_manifest(
            manifest_path,
            observed_utc=observed,
            status="fail",
            filename="",
            path="",
            size_bytes=0,
            sha256="",
            source_mailbox="",
            auth_status=auth_status,
            message_id="",
            attachment_id="",
            message_ts_utc="",
            notes=auth_notes,
        )

    try:
        profile = gmail.users().getProfile(userId="me").execute()
        source_mailbox = str(profile.get("emailAddress") or "").strip()
        if source_mailbox.lower() != expected_mailbox.lower():
            return _write_manifest(
                manifest_path,
                observed_utc=observed,
                status="fail",
                filename="",
                path="",
                size_bytes=0,
                sha256="",
                source_mailbox=source_mailbox,
                auth_status=auth_status,
                message_id="",
                attachment_id="",
                message_ts_utc="",
                notes="Gmail token opened a different mailbox than the Sellerboard source mailbox.",
            )

        candidate = _latest_orderlist_attachment(gmail, label=label)
        if not candidate:
            return _write_manifest(
                manifest_path,
                observed_utc=observed,
                status="fail",
                filename="",
                path="",
                size_bytes=0,
                sha256="",
                source_mailbox=source_mailbox,
                auth_status=auth_status,
                message_id="",
                attachment_id="",
                message_ts_utc="",
                notes="No Sellerboard OrderList CSV attachment was found in Gmail.",
            )

        message_ts, message_id, attachment_id, filename = candidate
        attachment = (
            gmail.users()
            .messages()
            .attachments()
            .get(userId="me", messageId=message_id, id=attachment_id)
            .execute()
        )
        data = _decode_attachment_data(str(attachment.get("data") or ""))
        if not data:
            return _write_manifest(
                manifest_path,
                observed_utc=observed,
                status="fail",
                filename=filename,
                path="",
                size_bytes=0,
                sha256="",
                source_mailbox=source_mailbox,
                auth_status=auth_status,
                message_id=message_id,
                attachment_id=attachment_id,
                message_ts_utc=message_ts,
                notes="Sellerboard OrderList attachment was present but empty.",
            )

        inbox = base / INBOX_REL_PATH
        inbox.mkdir(parents=True, exist_ok=True)
        sha = hashlib.sha256(data).hexdigest()
        target = _target_path(inbox=inbox, filename=filename, observed_utc=observed, sha256=sha)
        if not target.exists():
            target.write_bytes(data)
            notes = "Sellerboard OrderList attachment copied into the manager intake folder."
        else:
            notes = "Sellerboard OrderList attachment was already present in the manager intake folder."

        return _write_manifest(
            manifest_path,
            observed_utc=observed,
            status="ok",
            filename=target.name,
            path=str(target),
            size_bytes=len(data),
            sha256=sha,
            source_mailbox=source_mailbox,
            auth_status=auth_status,
            message_id=message_id,
            attachment_id=attachment_id,
            message_ts_utc=message_ts,
            notes=notes,
        )
    except Exception as exc:
        return _write_manifest(
            manifest_path,
            observed_utc=observed,
            status="fail",
            filename="",
            path="",
            size_bytes=0,
            sha256="",
            source_mailbox="",
            auth_status=auth_status,
            message_id="",
            attachment_id="",
            message_ts_utc="",
            notes=f"gmail_attachment_fetch_error:{exc.__class__.__name__}",
        )


def _latest_orderlist_attachment(gmail: Any, *, label: str) -> tuple[str, str, str, str] | None:
    query = f'label:"{label}" has:attachment -in:trash -in:spam'
    search = gmail.users().messages().list(userId="me", q=query, maxResults=10).execute()
    candidates: list[tuple[str, str, str, str]] = []
    for item in search.get("messages", []) or []:
        message_id = str(item.get("id") or "").strip()
        if not message_id:
            continue
        message = gmail.users().messages().get(userId="me", id=message_id, format="full").execute()
        message_ts = _message_ts_utc(message)
        for part in _walk_parts(message.get("payload", {}) or {}):
            filename = str(part.get("filename") or "").strip()
            if not filename or "orderlist" not in filename.lower() or Path(filename).suffix.lower() != ".csv":
                continue
            attachment_id = str((part.get("body", {}) or {}).get("attachmentId") or "").strip()
            if attachment_id:
                candidates.append((message_ts, message_id, attachment_id, filename))
    return sorted(candidates)[-1] if candidates else None


def _decode_attachment_data(value: str) -> bytes:
    padded = value + ("=" * (-len(value) % 4))
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _safe_filename(value: str) -> str:
    raw = value.replace("\\", "/").split("/")[-1]
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", raw).strip(" .")
    return cleaned or "Sellerboard_OrderList.csv"


def _target_path(*, inbox: Path, filename: str, observed_utc: str, sha256: str) -> Path:
    safe_name = _safe_filename(filename)
    target = inbox / safe_name
    if not target.exists():
        return target
    try:
        if hashlib.sha256(target.read_bytes()).hexdigest() == sha256:
            return target
    except OSError:
        pass
    stem = Path(safe_name).stem
    suffix = Path(safe_name).suffix or ".csv"
    stamp = observed_utc.replace("-", "").replace(":", "").replace("Z", "")
    return inbox / f"{stem}_{stamp}_{sha256[:10]}{suffix}"


def _write_manifest(
    manifest_path: Path,
    *,
    observed_utc: str,
    status: str,
    filename: str,
    path: str,
    size_bytes: int,
    sha256: str,
    source_mailbox: str,
    auth_status: str,
    message_id: str,
    attachment_id: str,
    message_ts_utc: str,
    notes: str,
) -> SellerboardEmailFetchResult:
    payload = {
        "observed_utc": observed_utc,
        "status": status,
        "filename": filename,
        "path": path,
        "size_bytes": size_bytes,
        "sha256": sha256,
        "source_mailbox": source_mailbox,
        "auth_status": auth_status,
        "message_id": message_id,
        "attachment_id": attachment_id,
        "message_ts_utc": message_ts_utc,
        "notes": notes,
        "safety": {
            "gmail_deleted": False,
            "local_file_deleted": False,
            "b_run_started": False,
            "business_outputs_changed": False,
        },
    }
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return SellerboardEmailFetchResult(
        observed_utc=observed_utc,
        status=status,
        filename=filename,
        path=path,
        size_bytes=size_bytes,
        sha256=sha256,
        source_mailbox=source_mailbox,
        auth_status=auth_status,
        message_id=message_id,
        attachment_id=attachment_id,
        message_ts_utc=message_ts_utc,
        manifest_path=manifest_path,
        notes=notes,
    )
