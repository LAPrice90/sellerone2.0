from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import get_manager_paths
from .sellerboard_email_intake import (
    DEFAULT_GMAIL_CLIENT_SECRET_REL_PATH,
    DEFAULT_GMAIL_LABEL,
    DEFAULT_GMAIL_TOKEN_REL_PATH,
    DEFAULT_SOURCE_ACCESS_METHOD,
    SOURCE_CONFIG_REL_PATH,
    SOURCE_PROOF_REL_PATH,
    _load_source_config,
    _resolve_config_path,
)


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_sellerboard_email_source_proof(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
    service: Any | None = None,
    write: bool = True,
) -> dict[str, Any]:
    paths = get_manager_paths(root)
    base = paths.root
    observed = observed_utc or utc_now_text()
    config = _load_source_config(base / SOURCE_CONFIG_REL_PATH)
    expected_mailbox = config["expected_source_mailbox"]
    label = config["gmail_label"] or DEFAULT_GMAIL_LABEL
    token_path = _resolve_config_path(base, config.get("gmail_token_path", DEFAULT_GMAIL_TOKEN_REL_PATH))
    client_path = _resolve_config_path(base, config.get("gmail_client_secret_path", DEFAULT_GMAIL_CLIENT_SECRET_REL_PATH))

    gmail, auth_status, auth_notes = _service_or_status(
        base=base,
        token_path=token_path,
        client_path=client_path,
        service=service,
    )
    proof = {
        "observed_utc": observed,
        "source_access_method": config.get("source_access_method", DEFAULT_SOURCE_ACCESS_METHOD),
        "expected_source_mailbox": expected_mailbox,
        "source_mailbox": "",
        "gmail_label": label,
        "proof_status": "fail",
        "latest_message_seen": False,
        "latest_attachment_filename": "",
        "latest_message_id": "",
        "latest_message_ts_utc": "",
        "attachment_metadata_seen": False,
        "attachment_downloaded": False,
        "gmail_deleted": False,
        "local_file_deleted": False,
        "auth_status": auth_status,
        "notes": auth_notes,
    }
    if gmail is None:
        return _write_if_requested(base, proof, write=write)

    try:
        profile = gmail.users().getProfile(userId="me").execute()
        proof["source_mailbox"] = str(profile.get("emailAddress") or "").strip()
        query = f'label:"{label}" has:attachment -in:trash -in:spam'
        search = gmail.users().messages().list(userId="me", q=query, maxResults=10).execute()
        candidates = []
        for item in search.get("messages", []) or []:
            message_id = str(item.get("id") or "").strip()
            if not message_id:
                continue
            message = gmail.users().messages().get(userId="me", id=message_id, format="full").execute()
            message_ts = _message_ts_utc(message)
            for part in _walk_parts(message.get("payload", {}) or {}):
                filename = str(part.get("filename") or "").strip()
                if not filename or "orderlist" not in filename.lower():
                    continue
                attachment_id = str((part.get("body", {}) or {}).get("attachmentId") or "").strip()
                if not attachment_id:
                    continue
                candidates.append((message_ts, message_id, filename))
        if candidates:
            message_ts, message_id, filename = sorted(candidates)[-1]
            proof.update(
                {
                    "latest_message_seen": True,
                    "latest_attachment_filename": filename,
                    "latest_message_id": message_id,
                    "latest_message_ts_utc": message_ts,
                    "attachment_metadata_seen": True,
                }
            )
        mailbox_ok = str(proof["source_mailbox"]).lower() == expected_mailbox.lower()
        proof_ok = mailbox_ok and bool(proof["latest_message_seen"]) and bool(proof["latest_attachment_filename"])
        proof["proof_status"] = "ok" if proof_ok else "fail"
        proof["notes"] = (
            "Read-only local Gmail metadata proof succeeded."
            if proof_ok
            else "Read-only local Gmail metadata proof did not find the expected mailbox, label, and OrderList attachment."
        )
    except Exception as exc:
        proof["proof_status"] = "fail"
        proof["notes"] = f"read_only_gmail_metadata_error:{exc.__class__.__name__}"

    return _write_if_requested(base, proof, write=write)


def _service_or_status(
    *,
    base: Path,
    token_path: Path,
    client_path: Path,
    service: Any | None,
) -> tuple[Any | None, str, str]:
    if service is not None:
        return service, "injected_test_service", "Using injected read-only Gmail test service."
    if not token_path.exists() or not client_path.exists():
        return None, "missing_oauth_files", "Local Gmail OAuth files are missing."
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ModuleNotFoundError:
        return None, "missing_python_dependencies", "Gmail API Python dependencies are not installed."
    try:
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    except Exception as exc:
        return None, "token_unreadable", f"Local Gmail token could not be read:{exc.__class__.__name__}"
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                from google.auth.transport.requests import Request

                creds.refresh(Request())
            except Exception as exc:
                return None, "oauth_refresh_failed", f"Local Gmail token refresh failed:{exc.__class__.__name__}"
        if not creds.valid:
            return None, "oauth_not_valid", "Local Gmail token exists but is not currently valid. This proof does not start an OAuth browser."
        auth_status = "refreshed_in_memory"
        auth_notes = "Local Gmail OAuth token refreshed in memory. No OAuth browser was opened."
    else:
        auth_status = "ok"
        auth_notes = "Local Gmail OAuth token is valid."
    try:
        return build("gmail", "v1", credentials=creds), auth_status, auth_notes
    except Exception as exc:
        return None, "gmail_service_build_failed", f"Gmail service could not be built:{exc.__class__.__name__}"


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


def _message_ts_utc(message: dict[str, Any]) -> str:
    raw = str(message.get("internalDate") or "").strip()
    if raw:
        try:
            seconds = int(raw) / 1000
            return datetime.fromtimestamp(seconds, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        except ValueError:
            pass
    return ""


def _write_if_requested(base: Path, proof: dict[str, Any], *, write: bool) -> dict[str, Any]:
    if write:
        path = base / SOURCE_PROOF_REL_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        proof["source_proof_path"] = str(path)
    return proof
