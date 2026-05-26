from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import ensure_manager_test_mode_dir
from scripts.flows.F.price_list_manager._schemas import (
    MANAGER_HEALTH_COLUMNS,
    SOURCE_ACQUISITION_COLUMNS,
    SUPPLIER_REGISTRY_COLUMNS,
)


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
DEFAULT_GMAIL_LABEL_BY_SUPPLIER = {
    "abgee": "ABGee",
    "td_synnex": "TD Synnex",
    "tropicana_wholesale": "Tropicana",
}
DEFAULT_ATTACHMENT_FILENAME_QUERY_BY_SUPPLIER = {
    "abgee": "",
    "td_synnex": "zip",
    "tropicana_wholesale": "xlsx",
}
DEFAULT_ALLOWED_SUFFIXES_BY_SUPPLIER = {
    "abgee": ".xlsx,.xls,.csv,.zip",
    "td_synnex": ".zip",
    "tropicana_wholesale": ".xlsx,.xls",
}
DEFAULT_LOOKBACK_DAYS_BY_SUPPLIER = {
    "abgee": "7",
}


@dataclass(frozen=True)
class GmailAttachment:
    message_id: str
    attachment_id: str
    filename: str
    message_ts_utc: str
    data: bytes


GmailAttachmentFetcher = Callable[..., GmailAttachment | None]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _existing_download_for_hash(target_dir: Path, *, file_hash: str, suffix: str) -> Path | None:
    if not target_dir.exists():
        return None
    clean_suffix = suffix.lower() or ".zip"
    for path in sorted(target_dir.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if not path.is_file() or path.suffix.lower() != clean_suffix:
            continue
        if file_hash[:10] in path.name:
            return path
        try:
            if _sha1_file(path) == file_hash:
                return path
        except OSError:
            continue
    return None


def _safe_filename(value: object, fallback: str) -> str:
    raw = normalize_text(value)
    if not raw:
        raw = fallback
    raw = raw.replace("\\", "/").split("/")[-1]
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", raw).strip(" .")
    return cleaned or fallback


def _parse_utc_date(value: str | None, *, local_tz_name: str) -> date:
    raw = normalize_text(value)
    if raw:
        if raw.endswith("Z"):
            parsed = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            return parsed.astimezone(ZoneInfo(local_tz_name)).date()
        return datetime.strptime(raw, "%Y-%m-%d").date()
    return datetime.now(ZoneInfo(local_tz_name)).date()


def _gmail_day_query(
    *,
    label_name: str,
    target_date: date,
    filename_query: str,
    lookback_days: int | None = None,
) -> str:
    clean_lookback = max(0, int(lookback_days))
    after = (target_date - timedelta(days=clean_lookback)).strftime("%Y/%m/%d")
    before = (target_date + timedelta(days=1)).strftime("%Y/%m/%d")
    parts = [f'label:"{label_name}"', "has:attachment", f"after:{after}", f"before:{before}", "-in:trash", "-in:spam"]
    if filename_query:
        parts.insert(2, f"filename:{filename_query}")
    return " ".join(parts)


def _load_gmail_source_config(root: Path) -> dict[str, dict[str, str]]:
    config_path = root / "secrets" / "price_list_manager" / "gmail_sources.json"
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for supplier_id, payload in raw.items():
        if isinstance(payload, dict):
            out[normalize_text(supplier_id)] = {normalize_text(key): normalize_text(value) for key, value in payload.items()}
    return out


def _supplier_gmail_config(root: Path, supplier_id: str, supplier_name: str) -> dict[str, str]:
    supplier_key = normalize_text(supplier_id)
    configs = _load_gmail_source_config(root)
    config = dict(configs.get(supplier_key, {}))
    config.setdefault("label_name", DEFAULT_GMAIL_LABEL_BY_SUPPLIER.get(supplier_key, supplier_name))
    config.setdefault("filename_query", DEFAULT_ATTACHMENT_FILENAME_QUERY_BY_SUPPLIER.get(supplier_key, "zip"))
    config.setdefault("allowed_suffixes", DEFAULT_ALLOWED_SUFFIXES_BY_SUPPLIER.get(supplier_key, ".zip"))
    config.setdefault("lookback_days", DEFAULT_LOOKBACK_DAYS_BY_SUPPLIER.get(supplier_key, "0"))
    config.setdefault("local_timezone", "Europe/London")
    return config


def _allowed_suffixes_from_config(config: dict[str, str]) -> set[str]:
    raw = normalize_text(config.get("allowed_suffixes", "")) or ".zip"
    suffixes: set[str] = set()
    for item in re.split(r"[,;\s]+", raw):
        clean = normalize_text(item).lower()
        if not clean:
            continue
        suffixes.add(clean if clean.startswith(".") else f".{clean}")
    return suffixes or {".zip"}


def _read_message_timestamp_utc(message: dict) -> str:
    raw = normalize_text(message.get("internalDate", ""))
    if raw:
        try:
            seconds = int(raw) / 1000
            return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pass
    return _utc_now_iso()


def _walk_parts(payload: dict) -> list[dict]:
    parts: list[dict] = []
    stack = [payload]
    while stack:
        current = stack.pop(0)
        parts.append(current)
        for child in current.get("parts", []) or []:
            if isinstance(child, dict):
                stack.append(child)
    return parts


def _decode_attachment_data(value: str) -> bytes:
    padded = value + ("=" * (-len(value) % 4))
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _build_gmail_service(root: Path):
    credentials_path = root / "secrets" / "price_list_manager" / "gmail_client_secret.json"
    token_path = root / "secrets" / "price_list_manager" / "gmail_token.json"
    if not credentials_path.exists():
        raise FileNotFoundError(f"missing Gmail OAuth client secret: {credentials_path}")

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ModuleNotFoundError as exc:
        raise RuntimeError("missing Gmail API Python dependencies") from exc

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return build("gmail", "v1", credentials=creds)


def _fetch_latest_gmail_attachment(
    *,
    root: Path,
    label_name: str,
    filename_query: str,
    target_date: date,
    allowed_suffixes: set[str],
    lookback_days: int | None = None,
    service=None,
) -> GmailAttachment | None:
    gmail = service or _build_gmail_service(root)
    query = _gmail_day_query(
        label_name=label_name,
        target_date=target_date,
        filename_query=filename_query,
        lookback_days=lookback_days,
    )
    search = gmail.users().messages().list(userId="me", q=query, maxResults=10).execute()
    messages = search.get("messages", []) or []
    if not messages:
        return None

    newest: tuple[str, str, str, str, str] | None = None
    for result in messages:
        message_id = normalize_text(result.get("id", ""))
        if not message_id:
            continue
        message = gmail.users().messages().get(userId="me", id=message_id, format="full").execute()
        message_ts = _read_message_timestamp_utc(message)
        for part in _walk_parts(message.get("payload", {}) or {}):
            filename = normalize_text(part.get("filename", ""))
            if not filename or Path(filename).suffix.lower() not in allowed_suffixes:
                continue
            attachment_id = normalize_text((part.get("body", {}) or {}).get("attachmentId", ""))
            if not attachment_id:
                continue
            candidate = (message_ts, message_id, attachment_id, filename, message_id)
            if newest is None or candidate > newest:
                newest = candidate

    if newest is None:
        return None
    message_ts, message_id, attachment_id, filename, _ = newest
    attachment = (
        gmail.users()
        .messages()
        .attachments()
        .get(userId="me", messageId=message_id, id=attachment_id)
        .execute()
    )
    data = _decode_attachment_data(normalize_text(attachment.get("data", "")))
    return GmailAttachment(
        message_id=message_id,
        attachment_id=attachment_id,
        filename=filename,
        message_ts_utc=message_ts,
        data=data,
    )


def _eligible_email_sources(acquisition: pd.DataFrame, supplier_id: str = "") -> pd.DataFrame:
    work = acquisition.copy()
    work = work[work["source_type"].map(lambda value: normalize_text(value).lower()) == "email_attachment"].copy()
    work = work[work["source_subtype"].map(lambda value: normalize_text(value).lower()) == "daily_email"].copy()
    if supplier_id:
        key = normalize_text(supplier_id).lower()
        work = work[work["supplier_id"].map(lambda value: normalize_text(value).lower()) == key].copy()
    return work.sort_values(["supplier_id", "checked_at_utc"], kind="stable").reset_index(drop=True)


def _manual_email_source_from_registry(root: Path, supplier_id: str, checked_at: str) -> pd.DataFrame:
    registry_path = root / "config" / "feeder" / "price_list_manager" / "suppliers.csv"
    registry = read_csv(registry_path, SUPPLIER_REGISTRY_COLUMNS)
    if registry.empty:
        return pd.DataFrame(columns=SOURCE_ACQUISITION_COLUMNS)
    supplier_key = normalize_text(supplier_id).lower()
    matches = registry[registry["supplier_id"].map(lambda value: normalize_text(value).lower()) == supplier_key].copy()
    if matches.empty:
        return pd.DataFrame(columns=SOURCE_ACQUISITION_COLUMNS)
    row = matches.iloc[0]
    if normalize_text(row.get("source_type", "")).lower() != "email_attachment":
        return pd.DataFrame(columns=SOURCE_ACQUISITION_COLUMNS)
    if normalize_text(row.get("source_subtype", "")).lower() != "daily_email":
        return pd.DataFrame(columns=SOURCE_ACQUISITION_COLUMNS)
    return pd.DataFrame(
        [
            {
                "supplier_id": normalize_text(row.get("supplier_id", "")),
                "supplier_name": normalize_text(row.get("supplier_name", "")),
                "source_type": normalize_text(row.get("source_type", "")),
                "source_subtype": normalize_text(row.get("source_subtype", "")),
                "source_state": "waiting",
                "status": "ok",
                "source_location": normalize_text(row.get("source_folder_path", "")),
                "latest_source_path": "",
                "latest_source_name": "",
                "latest_source_mtime_utc": "",
                "file_count": "0",
                "operator_action": "Await email file",
                "checked_at_utc": checked_at,
                "notes": "manual_supplier_fetch_from_registry",
            }
        ]
    )


def fetch_gmail_email_sources(
    root: Path | None = None,
    *,
    supplier_id: str = "",
    fetched_at_utc: str | None = None,
    target_date: str | None = None,
    lookback_days: int | None = None,
    fetcher: GmailAttachmentFetcher | None = None,
) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=root)
    fetched_at = fetched_at_utc or _utc_now_iso()
    acquisition_path = paths.test_mode_dir / "source_acquisition_status.csv"
    health_path = paths.test_mode_dir / "health.csv"
    acquisition = read_csv(acquisition_path, SOURCE_ACQUISITION_COLUMNS)
    if acquisition.empty and not normalize_text(supplier_id):
        raise FileNotFoundError("source_acquisition_status.csv is required before fetching Gmail sources")

    email_sources = _eligible_email_sources(acquisition, supplier_id=supplier_id)
    if email_sources.empty and normalize_text(supplier_id):
        email_sources = _manual_email_source_from_registry(paths.root, supplier_id, fetched_at)
        if not email_sources.empty:
            existing_without_supplier = acquisition[
                acquisition["supplier_id"].map(lambda value: normalize_text(value).lower()) != normalize_text(supplier_id).lower()
            ].copy()
            acquisition = write_csv(
                acquisition_path,
                pd.concat([existing_without_supplier, email_sources], ignore_index=True),
                SOURCE_ACQUISITION_COLUMNS,
            )
    updated = acquisition.copy()
    fetched_rows = 0
    skipped_rows = 0
    failed_rows = 0
    bytes_total = 0

    for _, source_row in email_sources.iterrows():
        source_supplier_id = normalize_text(source_row.get("supplier_id", ""))
        source_supplier_name = normalize_text(source_row.get("supplier_name", "")) or source_supplier_id
        mask = updated["supplier_id"].map(lambda value: normalize_text(value).lower()) == source_supplier_id.lower()
        config = _supplier_gmail_config(paths.root, source_supplier_id, source_supplier_name)
        label_name = normalize_text(config.get("label_name", "")) or source_supplier_name
        filename_query = normalize_text(config.get("filename_query", "zip"))
        local_timezone = normalize_text(config.get("local_timezone", "Europe/London")) or "Europe/London"
        local_date = _parse_utc_date(target_date or fetched_at, local_tz_name=local_timezone)
        allowed_suffixes = _allowed_suffixes_from_config(config)
        configured_lookback = normalize_text(config.get("lookback_days", "0")) or "0"
        clean_lookback_days = max(0, int(lookback_days if lookback_days is not None else configured_lookback))

        try:
            attachment = (fetcher or _fetch_latest_gmail_attachment)(
                root=paths.root,
                label_name=label_name,
                filename_query=filename_query,
                target_date=local_date,
                allowed_suffixes=allowed_suffixes,
                lookback_days=clean_lookback_days,
            )
        except Exception as exc:
            failed_rows += 1
            updated.loc[mask, "source_state"] = "error"
            updated.loc[mask, "status"] = "fail"
            updated.loc[mask, "operator_action"] = "Investigate Gmail pull"
            updated.loc[mask, "checked_at_utc"] = fetched_at
            updated.loc[mask, "notes"] = f"gmail_fetch_error={type(exc).__name__};label={label_name}"
            continue

        if attachment is None:
            skipped_rows += 1
            updated.loc[mask, "source_state"] = "waiting"
            updated.loc[mask, "status"] = "ok"
            updated.loc[mask, "operator_action"] = "Await email file"
            updated.loc[mask, "checked_at_utc"] = fetched_at
            updated.loc[mask, "notes"] = (
                f"gmail_no_matching_attachment;label={label_name};date={local_date.isoformat()};"
                f"lookback_days={clean_lookback_days}"
            )
            continue

        target_dir_raw = normalize_text(source_row.get("source_location", ""))
        if not target_dir_raw:
            failed_rows += 1
            updated.loc[mask, "source_state"] = "config_needed"
            updated.loc[mask, "status"] = "warn"
            updated.loc[mask, "operator_action"] = "Add folder path"
            updated.loc[mask, "checked_at_utc"] = fetched_at
            updated.loc[mask, "notes"] = "source_folder_path_missing"
            continue
        target_dir = Path(target_dir_raw)
        target_dir.mkdir(parents=True, exist_ok=True)
        file_hash = _sha1_bytes(attachment.data)
        stamp = fetched_at.replace("-", "").replace(":", "")
        safe_name = _safe_filename(attachment.filename, f"{source_supplier_id}_{stamp}.zip")
        suffix = Path(safe_name).suffix or ".zip"
        target = _existing_download_for_hash(target_dir, file_hash=file_hash, suffix=suffix)
        if target is None:
            target = target_dir / f"{Path(safe_name).stem}_{stamp}_{file_hash[:10]}{suffix}"
            target.write_bytes(attachment.data)

        file_count = len([path for path in target_dir.iterdir() if path.is_file()])
        bytes_written = len(attachment.data)
        bytes_total += bytes_written
        fetched_rows += 1
        updated.loc[mask, "source_state"] = "ready"
        updated.loc[mask, "status"] = "ok"
        updated.loc[mask, "source_location"] = f"gmail_label:{label_name}"
        updated.loc[mask, "latest_source_path"] = str(target)
        updated.loc[mask, "latest_source_name"] = target.name
        updated.loc[mask, "latest_source_mtime_utc"] = datetime.fromtimestamp(target.stat().st_mtime, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        updated.loc[mask, "file_count"] = str(file_count)
        updated.loc[mask, "operator_action"] = "Import latest file"
        updated.loc[mask, "checked_at_utc"] = fetched_at
        updated.loc[mask, "notes"] = (
            f"gmail_attachment_downloaded;label={label_name};date={local_date.isoformat()};"
            f"lookback_days={clean_lookback_days};"
            f"message_id={attachment.message_id};attachment_id={attachment.attachment_id};"
            f"message_ts_utc={attachment.message_ts_utc};bytes={bytes_written};sha1={file_hash}"
        )

    acquisition = write_csv(acquisition_path, updated, SOURCE_ACQUISITION_COLUMNS)
    existing_health = read_csv(health_path, MANAGER_HEALTH_COLUMNS)
    health_row = pd.DataFrame(
        [
            {
                "check": "gmail_email_attachment_fetch_reconciliation",
                "status": "ok" if failed_rows == 0 else "fail",
                "value": str(fetched_rows),
                "notes": (
                    f"email_sources={len(email_sources.index)};fetched={fetched_rows};"
                    f"skipped={skipped_rows};failed={failed_rows};bytes={bytes_total}"
                ),
                "observed_utc": fetched_at,
                "source_path": str(acquisition_path),
            }
        ]
    )
    health = write_csv(health_path, pd.concat([existing_health, health_row], ignore_index=True), MANAGER_HEALTH_COLUMNS)
    summary = {
        "status": "success",
        "email_sources": int(len(email_sources.index)),
        "fetched_sources": int(fetched_rows),
        "skipped_sources": int(skipped_rows),
        "failed_sources": int(failed_rows),
        "bytes": int(bytes_total),
        "health_fail_rows": int((health["status"].map(lambda value: normalize_text(value).lower()) == "fail").sum()),
        "acquisition_path": str(acquisition_path),
    }
    print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch daily Gmail attachment price-list sources into supplier inboxes.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--supplier-id", default="")
    parser.add_argument("--fetched-at-utc", default=None)
    parser.add_argument("--target-date", default=None, help="Local date YYYY-MM-DD, or UTC timestamp ending Z.")
    parser.add_argument("--lookback-days", type=int, default=None, help="Also search this many days before target date.")
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    fetch_gmail_email_sources(
        root=root,
        supplier_id=args.supplier_id,
        fetched_at_utc=args.fetched_at_utc,
        target_date=args.target_date,
        lookback_days=args.lookback_days,
    )


if __name__ == "__main__":
    main()
