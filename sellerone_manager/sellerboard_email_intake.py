from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import get_manager_paths
from .sellerboard_bridge import SELLERBOARD_REQUIRED_COLUMNS


EMAIL_INTAKE_DIR_NAME = "sellerboard_email_intake"
SUMMARY_CSV_NAME = "b_sellerboard_email_intake_summary.csv"
SUMMARY_JSON_NAME = "b_sellerboard_email_intake_summary.json"
ATTACHMENTS_CSV_NAME = "b_sellerboard_email_attachments.csv"
CLEANUP_CANDIDATES_CSV_NAME = "b_sellerboard_email_cleanup_candidates.csv"
CLEANUP_MANIFEST_JSON_NAME = "b_sellerboard_email_cleanup_manifest.json"
SOURCE_PROOF_JSON_NAME = "b_sellerboard_email_source_proof.json"
MARKDOWN_NAME = "b_sellerboard_email_intake_latest.md"

INBOX_REL_PATH = "out/systems/M/sellerboard_bridge/inbox"
POLICY_REL_PATH = "sellerone_manager/config/B_SELLERBOARD_EMAIL_CLEANUP_POLICY.json"
SOURCE_CONFIG_REL_PATH = "sellerone_manager/config/B_SELLERBOARD_EMAIL_INTAKE_SOURCE.json"
SOURCE_PROOF_REL_PATH = f"out/systems/M/{EMAIL_INTAKE_DIR_NAME}/{SOURCE_PROOF_JSON_NAME}"
DEFAULT_EXPECTED_SOURCE_MAILBOX = "admin@drjselect.co.uk"
DEFAULT_GMAIL_LABEL = "Sellerboard"
DEFAULT_SOURCE_ACCESS_METHOD = "local_gmail_oauth"
DEFAULT_GMAIL_TOKEN_REL_PATH = "secrets/price_list_manager/gmail_token.json"
DEFAULT_GMAIL_CLIENT_SECRET_REL_PATH = "secrets/price_list_manager/gmail_client_secret.json"
KEEP_LATEST_FILES = 2
FRESH_ATTACHMENT_HOURS = 36.0

SUMMARY_COLUMNS = [
    "observed_utc",
    "metric",
    "status",
    "value",
    "proof_label",
    "notes",
    "source_path",
]

ATTACHMENT_COLUMNS = [
    "observed_utc",
    "filename",
    "path",
    "size_bytes",
    "mtime_utc",
    "sha256",
    "is_orderlist",
    "is_selected_latest",
    "required_columns_missing",
    "row_count",
    "status",
    "notes",
]

CLEANUP_COLUMNS = [
    "observed_utc",
    "filename",
    "path",
    "size_bytes",
    "mtime_utc",
    "cleanup_reason",
    "delete_allowed",
    "notes",
]


@dataclass(frozen=True)
class SellerboardEmailIntakeResult:
    observed_utc: str
    status: str
    summary_rows: list[dict[str, str]]
    attachment_rows: list[dict[str, str]]
    cleanup_rows: list[dict[str, str]]
    source_paths: list[Path]


@dataclass(frozen=True)
class SellerboardCleanupResult:
    observed_utc: str
    deleted_count: int
    deleted_bytes: int
    skipped_count: int
    manifest_path: Path
    deleted_files: list[dict[str, str]]
    skipped_files: list[dict[str, str]]


def build_sellerboard_email_intake_report(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
) -> SellerboardEmailIntakeResult:
    paths = get_manager_paths(root)
    base = paths.root
    observed = observed_utc or utc_now_text()
    now = parse_utc(observed) or datetime.now(timezone.utc)
    inbox = base / INBOX_REL_PATH
    attachment_rows = _attachment_rows(inbox=inbox, observed=observed, now=now)
    policy = _load_cleanup_policy(base / POLICY_REL_PATH)
    source_config = _load_source_config(base / SOURCE_CONFIG_REL_PATH)
    source_proof = _load_source_proof(base / SOURCE_PROOF_REL_PATH)
    source_state = _source_state(source_config=source_config, source_proof=source_proof)
    cleanup_rows = _cleanup_rows(attachment_rows, observed=observed, policy=policy)
    status = _overall_status(attachment_rows, source_state=source_state)
    summary_rows = _summary_rows(
        observed=observed,
        status=status,
        base=base,
        inbox=inbox,
        source_config=source_config,
        source_state=source_state,
        attachment_rows=attachment_rows,
        cleanup_rows=cleanup_rows,
        now=now,
    )
    return SellerboardEmailIntakeResult(
        observed_utc=observed,
        status=status,
        summary_rows=summary_rows,
        attachment_rows=attachment_rows,
        cleanup_rows=cleanup_rows,
        source_paths=[inbox],
    )


def apply_sellerboard_email_cleanup(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
    dry_run: bool = False,
) -> SellerboardCleanupResult:
    paths = get_manager_paths(root)
    base = paths.root
    observed = observed_utc or utc_now_text()
    report = build_sellerboard_email_intake_report(root=base, observed_utc=observed)
    inbox = (base / INBOX_REL_PATH).resolve()
    deleted: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    for row in report.cleanup_rows:
        if row.get("delete_allowed") != "1":
            skipped.append({**row, "skip_reason": "delete_not_allowed_by_policy"})
            continue
        target = Path(row.get("path", "")).resolve()
        if not _is_safe_cleanup_target(target=target, inbox=inbox):
            skipped.append({**row, "skip_reason": "outside_intake_or_not_orderlist"})
            continue
        if not target.exists():
            skipped.append({**row, "skip_reason": "already_missing"})
            continue
        if dry_run:
            skipped.append({**row, "skip_reason": "dry_run"})
            continue
        try:
            target.unlink()
        except OSError as exc:
            skipped.append({**row, "skip_reason": f"delete_failed:{exc.__class__.__name__}"})
            continue
        deleted.append(row)

    manifest_dir = paths.output_dir / EMAIL_INTAKE_DIR_NAME
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / CLEANUP_MANIFEST_JSON_NAME
    payload = {
        "observed_utc": observed,
        "dry_run": dry_run,
        "policy_path": str(base / POLICY_REL_PATH),
        "intake_folder": str(inbox),
        "deleted_count": len(deleted),
        "deleted_bytes": sum(_to_int(row.get("size_bytes")) for row in deleted),
        "skipped_count": len(skipped),
        "deleted_files": deleted,
        "skipped_files": skipped,
        "safety": {
            "gmail_deleted": False,
            "business_outputs_deleted": False,
            "outside_intake_deleted": False,
        },
    }
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return SellerboardCleanupResult(
        observed_utc=observed,
        deleted_count=len(deleted),
        deleted_bytes=sum(_to_int(row.get("size_bytes")) for row in deleted),
        skipped_count=len(skipped),
        manifest_path=manifest_path,
        deleted_files=deleted,
        skipped_files=skipped,
    )


def write_sellerboard_email_intake_outputs(
    result: SellerboardEmailIntakeResult,
    output_dir: Path,
) -> dict[str, Path]:
    out_dir = output_dir / EMAIL_INTAKE_DIR_NAME
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary_csv": out_dir / SUMMARY_CSV_NAME,
        "summary_json": out_dir / SUMMARY_JSON_NAME,
        "attachments_csv": out_dir / ATTACHMENTS_CSV_NAME,
        "cleanup_candidates_csv": out_dir / CLEANUP_CANDIDATES_CSV_NAME,
        "markdown": out_dir / MARKDOWN_NAME,
    }
    _write_csv(paths["summary_csv"], SUMMARY_COLUMNS, result.summary_rows)
    _write_csv(paths["attachments_csv"], ATTACHMENT_COLUMNS, result.attachment_rows)
    _write_csv(paths["cleanup_candidates_csv"], CLEANUP_COLUMNS, result.cleanup_rows)
    paths["summary_json"].write_text(
        json.dumps(_summary_json(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths["markdown"].write_text(_markdown(result), encoding="utf-8")
    return paths


def utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _attachment_rows(*, inbox: Path, observed: str, now: datetime) -> list[dict[str, str]]:
    files = sorted(
        [path for path in inbox.glob("*.csv") if path.is_file()],
        key=lambda path: _mtime(path),
        reverse=True,
    ) if inbox.exists() else []
    order_files = [path for path in files if _is_orderlist(path)]
    selected = order_files[0] if order_files else None
    rows: list[dict[str, str]] = []
    for path in files:
        headers, row_count = _csv_shape(path)
        missing = [column for column in SELLERBOARD_REQUIRED_COLUMNS if column not in headers]
        is_orderlist = _is_orderlist(path)
        mtime = _mtime_utc(path)
        age_hours = _age_hours(mtime, now)
        if not is_orderlist:
            status = "ignored"
            notes = "Not a Sellerboard OrderList CSV."
        elif missing:
            status = "fail"
            notes = "Sellerboard OrderList CSV is missing required columns."
        elif age_hours is not None and age_hours > FRESH_ATTACHMENT_HOURS and path == selected:
            status = "stale"
            notes = "Latest Sellerboard attachment is older than the daily freshness target."
        else:
            status = "ok"
            notes = "Sellerboard OrderList CSV has the expected shape."
        rows.append(
            {
                "observed_utc": observed,
                "filename": path.name,
                "path": str(path),
                "size_bytes": str(_size(path)),
                "mtime_utc": _iso_or_blank(mtime),
                "sha256": _sha256(path),
                "is_orderlist": "1" if is_orderlist else "0",
                "is_selected_latest": "1" if selected and path == selected else "0",
                "required_columns_missing": ";".join(missing),
                "row_count": "" if row_count is None else str(row_count),
                "status": status,
                "notes": notes,
            }
        )
    return rows


def _cleanup_rows(
    attachment_rows: list[dict[str, str]],
    *,
    observed: str,
    policy: dict[str, Any],
) -> list[dict[str, str]]:
    orderlist_rows = [row for row in attachment_rows if row.get("is_orderlist") == "1"]
    keep_latest = _policy_keep_count(policy)
    keep_paths = {row.get("path", "") for row in orderlist_rows[:keep_latest]}
    policy_allows_delete = _policy_allows_delete(policy)
    cleanup: list[dict[str, str]] = []
    for row in attachment_rows:
        reason = ""
        delete_allowed = "0"
        if row.get("is_orderlist") != "1":
            reason = "not_orderlist_attachment"
        elif row.get("path", "") not in keep_paths:
            reason = "older_than_latest_kept_files"
            delete_allowed = "1" if policy_allows_delete else "0"
        if not reason:
            continue
        cleanup.append(
            {
                "observed_utc": observed,
                "filename": row.get("filename", ""),
                "path": row.get("path", ""),
                "size_bytes": row.get("size_bytes", ""),
                "mtime_utc": row.get("mtime_utc", ""),
                "cleanup_reason": reason,
                "delete_allowed": delete_allowed,
                "notes": (
                    "Approved for deletion by local intake cleanup policy."
                    if delete_allowed == "1"
                    else "Candidate only. Deletion is not allowed by the current policy."
                ),
            }
        )
    return cleanup


def _overall_status(
    attachment_rows: list[dict[str, str]],
    *,
    source_state: dict[str, str],
) -> str:
    if source_state.get("source_mailbox_visible") != "1":
        return "fail"
    selected = next((row for row in attachment_rows if row.get("is_selected_latest") == "1"), None)
    if not selected:
        return "fail"
    if selected.get("status") == "fail":
        return "fail"
    if selected.get("status") == "stale":
        return "warn"
    return "ok"


def _summary_rows(
    *,
    observed: str,
    status: str,
    base: Path,
    inbox: Path,
    source_config: dict[str, str],
    source_state: dict[str, str],
    attachment_rows: list[dict[str, str]],
    cleanup_rows: list[dict[str, str]],
    now: datetime,
) -> list[dict[str, str]]:
    selected = next((row for row in attachment_rows if row.get("is_selected_latest") == "1"), {})
    cleanup_bytes = sum(_to_int(row.get("size_bytes")) for row in cleanup_rows)
    cleanup_allowed = sum(1 for row in cleanup_rows if row.get("delete_allowed") == "1")
    selected_mtime = parse_utc(selected.get("mtime_utc"))
    latest_age = _age_hours(selected_mtime, now)
    token_path = _resolve_config_path(base, source_config["gmail_token_path"])
    client_path = _resolve_config_path(base, source_config["gmail_client_secret_path"])
    local_oauth_present = token_path.exists() and client_path.exists()

    def metric(name: str, value: Any, row_status: str, label: str, notes: str = "", source: str | Path | None = None) -> dict[str, str]:
        return {
            "observed_utc": observed,
            "metric": name,
            "status": row_status,
            "value": str(value),
            "proof_label": label,
            "notes": notes,
            "source_path": str(source or inbox),
        }

    missing_columns = selected.get("required_columns_missing", "")
    return [
        metric("overall_status", status, status, "not yet proven" if status == "fail" else "API proved"),
        metric("expected_source_mailbox", source_config["expected_source_mailbox"], "ok", "API proved", "Configured source mailbox for Sellerboard daily email intake."),
        metric("source_access_method", source_config["source_access_method"], "ok", "API proved", "Configured email access route for Sellerboard daily email intake."),
        metric(
            "local_gmail_oauth_files_present",
            "1" if local_oauth_present else "0",
            "ok" if local_oauth_present else "fail",
            "API proved" if local_oauth_present else "not yet proven",
            "Local OAuth files are the same email access doorway used by FPM016.",
        ),
        metric("gmail_label", source_config["gmail_label"], "not_checked", "not yet proven", "Configured Gmail label. Local Gmail visibility is proved by the source proof file."),
        metric(
            "source_mailbox_visible",
            source_state["source_mailbox_visible"],
            "ok" if source_state["source_mailbox_visible"] == "1" else "fail",
            "API proved" if source_state["source_mailbox_visible"] == "1" else "not yet proven",
            source_state["source_notes"],
            source_state["source_proof_path"],
        ),
        metric("source_mailbox_status", source_state["source_mailbox_status"], source_state["source_mailbox_status"], "API proved" if source_state["source_mailbox_visible"] == "1" else "not yet proven", source_state["source_notes"], source_state["source_proof_path"]),
        metric("source_auth_status", source_state["source_auth_status"], "ok" if source_state["source_auth_status"] in {"", "ok", "injected_test_service", "refreshed_in_memory"} else "fail", "API proved" if source_state["source_auth_status"] in {"ok", "injected_test_service", "refreshed_in_memory"} else "not yet proven", source_state["source_notes"], source_state["source_proof_path"]),
        metric("source_mailbox_last_proved_utc", source_state["source_last_proved_utc"], "ok" if source_state["source_mailbox_visible"] == "1" else "not_checked", "API proved" if source_state["source_mailbox_visible"] == "1" else "not yet proven", source_state["source_notes"], source_state["source_proof_path"]),
        metric("source_latest_message_seen", source_state["source_latest_message_seen"], "ok" if source_state["source_mailbox_visible"] == "1" else "not_checked", "API proved" if source_state["source_mailbox_visible"] == "1" else "not yet proven", source_state["source_notes"], source_state["source_proof_path"]),
        metric("source_latest_attachment_filename", source_state["source_latest_attachment_filename"], "ok" if source_state["source_mailbox_visible"] == "1" else "not_checked", "API proved" if source_state["source_mailbox_visible"] == "1" else "not yet proven", source_state["source_notes"], source_state["source_proof_path"]),
        metric("intake_folder_exists", "1" if inbox.exists() else "0", "ok" if inbox.exists() else "fail", "API proved" if inbox.exists() else "not yet proven"),
        metric("latest_attachment_present", "1" if selected else "0", "ok" if selected else "fail", "API proved" if selected else "not yet proven"),
        metric("latest_attachment_filename", selected.get("filename", ""), "ok" if selected else "fail", "API proved" if selected else "not yet proven"),
        metric("latest_attachment_age_hours", "" if latest_age is None else f"{latest_age:.2f}", "ok" if selected and (latest_age or 0.0) <= FRESH_ATTACHMENT_HOURS else "warn" if selected else "fail", "API proved" if selected else "not yet proven"),
        metric("required_columns_missing", len([part for part in missing_columns.split(";") if part]), "fail" if missing_columns else "ok" if selected else "not_checked", "not yet proven" if missing_columns or not selected else "API proved", missing_columns),
        metric("latest_attachment_row_count", selected.get("row_count", ""), "ok" if selected.get("row_count", "") not in {"", "0"} else "fail" if selected else "not_checked", "API proved" if selected else "not yet proven"),
        metric("intake_file_count", len(attachment_rows), "ok", "API proved"),
        metric("cleanup_policy_approved", "1" if cleanup_allowed else "0", "ok", "API proved" if cleanup_allowed else "not yet proven"),
        metric("cleanup_candidate_count", len(cleanup_rows), "warn" if cleanup_rows else "ok", "API proved" if cleanup_allowed or not cleanup_rows else "not yet proven", "Only rows marked delete_allowed=1 may be removed."),
        metric("cleanup_delete_allowed_count", cleanup_allowed, "ok", "API proved" if cleanup_allowed or not cleanup_rows else "not yet proven"),
        metric("cleanup_candidate_bytes", cleanup_bytes, "warn" if cleanup_bytes else "ok", "not yet proven" if cleanup_bytes else "API proved"),
    ]


def _csv_shape(path: Path) -> tuple[list[str], int | None]:
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;")
            except csv.Error:
                dialect = csv.excel
            reader = csv.DictReader(handle, dialect=dialect)
            row_count = sum(1 for _row in reader)
            return list(reader.fieldnames or []), row_count
    except (OSError, csv.Error):
        return [], None


def _is_orderlist(path: Path) -> bool:
    return "orderlist" in path.name.lower() and path.suffix.lower() == ".csv"


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _mtime_utc(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def _size(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except OSError:
        return 0


def _sha256(path: Path) -> str:
    try:
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return ""


def _age_hours(value: datetime | None, now: datetime) -> float | None:
    if not value:
        return None
    return max((now - value).total_seconds() / 3600.0, 0.0)


def _iso_or_blank(value: datetime | None) -> str:
    if not value:
        return ""
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _to_int(value: Any) -> int:
    try:
        return int(float(str(value or "0")))
    except ValueError:
        return 0


def _resolve_config_path(base: Path, value: str) -> Path:
    path = Path(str(value or ""))
    if path.is_absolute():
        return path
    return base / path


def _load_cleanup_policy(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_source_config(path: Path) -> dict[str, str]:
    payload: dict[str, Any] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = {}
        if isinstance(loaded, dict):
            payload = loaded
    expected = str(payload.get("expected_source_mailbox") or DEFAULT_EXPECTED_SOURCE_MAILBOX).strip()
    label = str(payload.get("gmail_label") or DEFAULT_GMAIL_LABEL).strip()
    access_method = str(payload.get("source_access_method") or DEFAULT_SOURCE_ACCESS_METHOD).strip()
    token_path = str(payload.get("gmail_token_path") or DEFAULT_GMAIL_TOKEN_REL_PATH).strip()
    client_path = str(payload.get("gmail_client_secret_path") or DEFAULT_GMAIL_CLIENT_SECRET_REL_PATH).strip()
    return {
        "expected_source_mailbox": expected or DEFAULT_EXPECTED_SOURCE_MAILBOX,
        "gmail_label": label or DEFAULT_GMAIL_LABEL,
        "source_access_method": access_method or DEFAULT_SOURCE_ACCESS_METHOD,
        "gmail_token_path": token_path or DEFAULT_GMAIL_TOKEN_REL_PATH,
        "gmail_client_secret_path": client_path or DEFAULT_GMAIL_CLIENT_SECRET_REL_PATH,
    }


def _load_source_proof(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _source_state(
    *,
    source_config: dict[str, str],
    source_proof: dict[str, Any],
) -> dict[str, str]:
    expected_mailbox = _normalize_text(source_config.get("expected_source_mailbox"))
    expected_label = _normalize_text(source_config.get("gmail_label"))
    expected_method = _normalize_text(source_config.get("source_access_method") or DEFAULT_SOURCE_ACCESS_METHOD)
    proved_mailbox = _normalize_text(
        source_proof.get("source_mailbox")
        or source_proof.get("mailbox")
        or source_proof.get("email_address")
    )
    proved_label = _normalize_text(source_proof.get("gmail_label") or source_proof.get("label"))
    proved_method = _normalize_text(
        source_proof.get("source_access_method")
        or source_proof.get("access_method")
        or expected_method
    )
    proof_status = _normalize_text(source_proof.get("proof_status") or source_proof.get("status"))
    latest_message_seen = _truthy(source_proof.get("latest_message_seen") or source_proof.get("message_seen"))
    latest_attachment = str(
        source_proof.get("latest_attachment_filename")
        or source_proof.get("attachment_filename")
        or ""
    ).strip()
    label_ok = not expected_label or proved_label == expected_label
    method_ok = not expected_method or proved_method == expected_method
    visible = (
        bool(expected_mailbox)
        and proved_mailbox == expected_mailbox
        and proof_status in {"ok", "proved", "visible", "success"}
        and latest_message_seen
        and bool(latest_attachment)
        and label_ok
        and method_ok
    )
    if visible:
        notes = "Local Gmail source proof has seen the Sellerboard mailbox, label, message, and attachment metadata."
        status = "ok"
    elif not source_proof:
        notes = "No source proof file exists yet. Local Gmail access is only a clue until the Sellerboard label and attachment metadata are proved."
        status = "fail"
    elif proved_mailbox != expected_mailbox:
        notes = "Source proof exists, but it is for a different mailbox."
        status = "fail"
    elif proof_status not in {"ok", "proved", "visible", "success"}:
        notes = "Source proof exists, but the connector status is not ok."
        status = "fail"
    elif not latest_message_seen or not latest_attachment:
        notes = "Source proof exists, but it has not proved the latest Sellerboard message and attachment."
        status = "fail"
    elif not method_ok:
        notes = "Source proof exists, but it was made through a different email access method than the manager expects."
        status = "fail"
    else:
        notes = "Source proof exists, but it does not match the expected Sellerboard label."
        status = "fail"
    return {
        "source_mailbox_visible": "1" if visible else "0",
        "source_mailbox_status": status,
        "source_access_method": expected_method,
        "source_proved_access_method": proved_method,
        "source_auth_status": str(source_proof.get("auth_status") or "").strip(),
        "source_last_proved_utc": str(source_proof.get("observed_utc") or source_proof.get("proved_utc") or "").strip(),
        "source_latest_message_seen": "1" if latest_message_seen else "0",
        "source_latest_attachment_filename": latest_attachment,
        "source_proof_path": SOURCE_PROOF_REL_PATH,
        "source_notes": notes,
    }


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "ok"}


def _policy_allows_delete(policy: dict[str, Any]) -> bool:
    return (
        bool(policy.get("delete_allowed"))
        and str(policy.get("scope", "")).lower() == "local sellerboard manager intake folder only"
        and str(policy.get("intake_folder", "")).replace("\\", "/") == INBOX_REL_PATH
    )


def _policy_keep_count(policy: dict[str, Any]) -> int:
    try:
        count = int(policy.get("keep_latest_orderlist_files", KEEP_LATEST_FILES))
    except (TypeError, ValueError):
        return KEEP_LATEST_FILES
    return max(count, KEEP_LATEST_FILES)


def _is_safe_cleanup_target(*, target: Path, inbox: Path) -> bool:
    try:
        target.relative_to(inbox)
    except ValueError:
        return False
    return target.is_file() and _is_orderlist(target)


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def _summary_json(result: SellerboardEmailIntakeResult) -> dict[str, Any]:
    return {
        "observed_utc": result.observed_utc,
        "status": result.status,
        "summary": {row["metric"]: row["value"] for row in result.summary_rows},
        "source_paths": [str(path) for path in result.source_paths],
    }


def _markdown(result: SellerboardEmailIntakeResult) -> str:
    metrics = {row["metric"]: row["value"] for row in result.summary_rows}
    lines = [
        "# B Sellerboard Email Intake",
        "",
        f"Observed UTC: {result.observed_utc}",
        f"Status: {result.status}",
        "",
        "## Plain English",
        "This checks whether the daily Sellerboard email attachment has been saved into the manager intake area and whether old intake files are only cleanup candidates.",
        "",
        "## Summary",
        f"- Expected source mailbox: {metrics.get('expected_source_mailbox', DEFAULT_EXPECTED_SOURCE_MAILBOX)}",
        f"- Source mailbox visible: {metrics.get('source_mailbox_visible', '0')}",
        f"- Latest attachment present: {metrics.get('latest_attachment_present', '0')}",
        f"- Latest attachment: {metrics.get('latest_attachment_filename', '')}",
        f"- Missing required columns: {metrics.get('required_columns_missing', '0')}",
        f"- Cleanup candidates: {metrics.get('cleanup_candidate_count', '0')}",
        f"- Cleanup allowed: {metrics.get('cleanup_delete_allowed_count', '0')}",
        f"- Cleanup candidate bytes: {metrics.get('cleanup_candidate_bytes', '0')}",
        "",
        "## Safety",
        "- This report did not read Gmail directly.",
        "- This report did not delete email or local files.",
        "- Only older local OrderList copies marked delete_allowed=1 may be removed by the separate cleanup command.",
    ]
    return "\n".join(lines) + "\n"
