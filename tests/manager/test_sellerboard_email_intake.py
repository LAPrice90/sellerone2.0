from __future__ import annotations

import csv
import json
import os
import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sellerone_manager.hourly_mot import build_b_hourly_mot, write_hourly_mot_outputs
from sellerone_manager.sellerboard_bridge import SELLERBOARD_REQUIRED_COLUMNS
from sellerone_manager.sellerboard_email_intake import (
    INBOX_REL_PATH,
    POLICY_REL_PATH,
    SOURCE_PROOF_REL_PATH,
    apply_sellerboard_email_cleanup,
    build_sellerboard_email_intake_report,
    write_sellerboard_email_intake_outputs,
)
from sellerone_manager.sellerboard_email_fetch import fetch_latest_sellerboard_email_attachment
from sellerone_manager.sellerboard_email_source_probe import build_sellerboard_email_source_proof


OBSERVED = "2026-05-27T12:30:00Z"


class _FakeExecute:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def execute(self) -> dict:
        return self.payload


class _FakeMessages:
    attachments_called = False

    def list(self, **_kwargs) -> _FakeExecute:
        return _FakeExecute({"messages": [{"id": "msg-1"}]})

    def get(self, **_kwargs) -> _FakeExecute:
        return _FakeExecute(
            {
                "id": "msg-1",
                "internalDate": "1779878400000",
                "payload": {
                    "parts": [
                        {
                            "filename": "DRJ_Hardware_OrderList_20_05_2026-26_05_2026.csv",
                            "body": {"attachmentId": "att-1"},
                        }
                    ]
                },
            }
        )

    def attachments(self) -> "_FakeMessages":
        self.attachments_called = True
        raise AssertionError("source proof must not download attachments")


class _FakeUsers:
    def __init__(self) -> None:
        self.messages_api = _FakeMessages()

    def getProfile(self, **_kwargs) -> _FakeExecute:
        return _FakeExecute({"emailAddress": "admin@drjselect.co.uk"})

    def messages(self) -> _FakeMessages:
        return self.messages_api


class _FakeGmail:
    def __init__(self) -> None:
        self.users_api = _FakeUsers()

    def users(self) -> _FakeUsers:
        return self.users_api


class _FakeFetchAttachments:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def get(self, **_kwargs) -> _FakeExecute:
        encoded = base64.urlsafe_b64encode(self.data).decode("ascii").rstrip("=")
        return _FakeExecute({"data": encoded})


class _FakeFetchMessages(_FakeMessages):
    def __init__(self, data: bytes) -> None:
        self.attachments_api = _FakeFetchAttachments(data)

    def attachments(self) -> _FakeFetchAttachments:
        return self.attachments_api


class _FakeFetchUsers(_FakeUsers):
    def __init__(self, data: bytes) -> None:
        self.messages_api = _FakeFetchMessages(data)


class _FakeFetchGmail(_FakeGmail):
    def __init__(self, data: bytes) -> None:
        self.users_api = _FakeFetchUsers(data)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _sellerboard_row() -> dict[str, str]:
    return {column: "1" for column in SELLERBOARD_REQUIRED_COLUMNS}


def _sellerboard_csv_bytes() -> bytes:
    header = ",".join(SELLERBOARD_REQUIRED_COLUMNS)
    row = ",".join("1" for _column in SELLERBOARD_REQUIRED_COLUMNS)
    return f"{header}\n{row}\n".encode("utf-8")


def _write_policy(root: Path) -> None:
    path = root / POLICY_REL_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "scope": "local Sellerboard manager intake folder only",
                "intake_folder": INBOX_REL_PATH,
                "keep_latest_orderlist_files": 2,
                "delete_allowed": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_local_gmail_oauth(root: Path) -> None:
    secrets = root / "secrets" / "price_list_manager"
    secrets.mkdir(parents=True, exist_ok=True)
    (secrets / "gmail_token.json").write_text("{}", encoding="utf-8")
    (secrets / "gmail_client_secret.json").write_text("{}", encoding="utf-8")


def _write_source_proof(
    root: Path,
    filename: str = "DRJ_Hardware_OrderList_20_05_2026-26_05_2026.csv",
) -> None:
    path = root / SOURCE_PROOF_REL_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "observed_utc": OBSERVED,
                "source_access_method": "local_gmail_oauth",
                "source_mailbox": "admin@drjselect.co.uk",
                "gmail_label": "Sellerboard",
                "latest_message_seen": True,
                "latest_attachment_filename": filename,
                "proof_status": "ok",
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_orderlist(
    root: Path,
    filename: str = "DRJ_Hardware_OrderList_20_05_2026-26_05_2026.csv",
    *,
    minutes_old: int = 0,
) -> Path:
    path = root / INBOX_REL_PATH / filename
    _write_csv(path, SELLERBOARD_REQUIRED_COLUMNS, [_sellerboard_row()])
    path.parent.mkdir(parents=True, exist_ok=True)
    fixed = (datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc) - timedelta(minutes=minutes_old)).timestamp()
    os.utime(path, (fixed, fixed))
    return path


def test_email_intake_fails_when_daily_attachment_missing(tmp_path: Path) -> None:
    result = build_sellerboard_email_intake_report(root=tmp_path, observed_utc=OBSERVED)
    metrics = {row["metric"]: row["value"] for row in result.summary_rows}

    assert result.status == "fail"
    assert metrics["source_mailbox_visible"] == "0"
    assert metrics["latest_attachment_present"] == "0"


def test_email_intake_accepts_latest_orderlist_and_writes_outputs(tmp_path: Path) -> None:
    filename = "DRJ_Hardware_OrderList_20_05_2026-26_05_2026.csv"
    _write_source_proof(tmp_path, filename)
    _write_orderlist(tmp_path, filename)

    result = build_sellerboard_email_intake_report(root=tmp_path, observed_utc=OBSERVED)
    paths = write_sellerboard_email_intake_outputs(result, tmp_path / "out" / "systems" / "M")
    metrics = {row["metric"]: row["value"] for row in result.summary_rows}

    assert result.status == "ok"
    assert metrics["source_mailbox_visible"] == "1"
    assert metrics["latest_attachment_present"] == "1"
    assert metrics["required_columns_missing"] == "0"
    assert paths["summary_csv"].exists()


def test_source_probe_writes_local_gmail_metadata_proof_without_downloading(tmp_path: Path) -> None:
    proof = build_sellerboard_email_source_proof(
        root=tmp_path,
        observed_utc=OBSERVED,
        service=_FakeGmail(),
    )
    source_proof = json.loads((tmp_path / SOURCE_PROOF_REL_PATH).read_text(encoding="utf-8"))

    assert proof["proof_status"] == "ok"
    assert source_proof["source_access_method"] == "local_gmail_oauth"
    assert source_proof["source_mailbox"] == "admin@drjselect.co.uk"
    assert source_proof["latest_attachment_filename"].endswith(".csv")
    assert source_proof["attachment_downloaded"] is False
    assert source_proof["gmail_deleted"] is False


def test_source_probe_refreshes_expired_local_token_without_oauth_browser(tmp_path: Path, monkeypatch) -> None:
    _write_local_gmail_oauth(tmp_path)

    class _FakeCreds:
        valid = False
        expired = True
        refresh_token = "refresh-token"

        def refresh(self, _request) -> None:
            self.valid = True

    fake_creds = _FakeCreds()

    from google.oauth2.credentials import Credentials
    import googleapiclient.discovery

    monkeypatch.setattr(Credentials, "from_authorized_user_file", lambda *_args, **_kwargs: fake_creds)
    monkeypatch.setattr(googleapiclient.discovery, "build", lambda *_args, **_kwargs: _FakeGmail())

    proof = build_sellerboard_email_source_proof(root=tmp_path, observed_utc=OBSERVED)

    assert proof["proof_status"] == "ok"
    assert proof["auth_status"] == "refreshed_in_memory"
    assert proof["attachment_downloaded"] is False
    assert proof["gmail_deleted"] is False


def test_email_fetch_copies_latest_orderlist_without_deleting_gmail(tmp_path: Path) -> None:
    _write_source_proof(tmp_path)
    result = fetch_latest_sellerboard_email_attachment(
        root=tmp_path,
        observed_utc=OBSERVED,
        service=_FakeFetchGmail(_sellerboard_csv_bytes()),
    )
    report = build_sellerboard_email_intake_report(root=tmp_path, observed_utc=OBSERVED)
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert result.status == "ok"
    assert Path(result.path).exists()
    assert result.filename.endswith(".csv")
    assert manifest["safety"]["gmail_deleted"] is False
    assert manifest["safety"]["business_outputs_changed"] is False
    assert report.status == "ok"


def test_email_intake_lists_cleanup_candidates_with_narrow_delete_permission(tmp_path: Path) -> None:
    _write_policy(tmp_path)
    _write_source_proof(tmp_path)
    latest = _write_orderlist(tmp_path, "DRJ_Hardware_OrderList_20_05_2026-26_05_2026.csv", minutes_old=0)
    second = _write_orderlist(tmp_path, "DRJ_Hardware_OrderList_13_05_2026-19_05_2026.csv", minutes_old=10)
    older = _write_orderlist(tmp_path, "DRJ_Hardware_OrderList_06_05_2026-12_05_2026.csv", minutes_old=20)
    _write_csv(tmp_path / INBOX_REL_PATH / "random.csv", ["id"], [{"id": "1"}])

    result = build_sellerboard_email_intake_report(root=tmp_path, observed_utc=OBSERVED)

    assert result.status == "ok"
    assert older.exists()
    assert second.exists()
    assert latest.exists()
    assert any(row["cleanup_reason"] == "not_orderlist_attachment" for row in result.cleanup_rows)
    assert any(
        row["cleanup_reason"] == "older_than_latest_kept_files" and row["delete_allowed"] == "1"
        for row in result.cleanup_rows
    )
    assert all(
        row["delete_allowed"] == "0"
        for row in result.cleanup_rows
        if row["cleanup_reason"] == "not_orderlist_attachment"
    )


def test_b_mot_admin_inbox_access_needs_luke_when_unproven(tmp_path: Path) -> None:
    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))

    assert rows["b_sellerboard_email_admin_inbox_access"]["status"] == "decision_needed"
    assert rows["b_sellerboard_email_admin_inbox_access"]["luke_action_required"] == "1"
    assert rows["b_sellerboard_email_attachment_arrived"]["status"] == "not_checked"
    work_item = next(row for row in worklist_rows if row["check"] == "b_sellerboard_email_admin_inbox_access")
    assert work_item["status"] == "blocked_needs_luke"
    assert "Gmail source authorization" in work_item["safe_repair_boundary"]


def test_b_mot_email_intake_creates_work_item_when_authorized_attachment_missing(tmp_path: Path) -> None:
    _write_source_proof(tmp_path)

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))

    assert rows["b_sellerboard_email_admin_inbox_access"]["status"] == "ok"
    assert rows["b_sellerboard_email_attachment_arrived"]["status"] == "fail"
    assert any(row["check"] == "b_sellerboard_email_attachment_arrived" for row in worklist_rows)
    work_item = next(row for row in worklist_rows if row["check"] == "b_sellerboard_email_attachment_arrived")
    assert "no Gmail deletion" in work_item["safe_repair_boundary"]


def test_b_mot_local_oauth_without_source_proof_creates_codex_work_item(tmp_path: Path) -> None:
    _write_local_gmail_oauth(tmp_path)

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    paths = write_hourly_mot_outputs(result, tmp_path / "out" / "systems" / "M")
    rows = {row["check"]: row for row in result["rows"]}
    worklist_rows = list(csv.DictReader(paths["mot_worklist_csv"].open(newline="", encoding="utf-8")))
    work_item = next(row for row in worklist_rows if row["check"] == "b_sellerboard_email_admin_inbox_access")

    assert rows["b_sellerboard_email_admin_inbox_access"]["status"] == "fail"
    assert rows["b_sellerboard_email_admin_inbox_access"]["luke_action_required"] == "0"
    assert work_item["status"] == "new"
    assert "no attachment download" in work_item["safe_repair_boundary"]


def test_b_mot_storage_cleanup_guard_allows_approved_orderlist_cleanup(tmp_path: Path) -> None:
    _write_policy(tmp_path)
    _write_source_proof(tmp_path)
    _write_orderlist(tmp_path, "DRJ_Hardware_OrderList_20_05_2026-26_05_2026.csv", minutes_old=0)
    _write_orderlist(tmp_path, "DRJ_Hardware_OrderList_13_05_2026-19_05_2026.csv", minutes_old=10)
    _write_orderlist(tmp_path, "DRJ_Hardware_OrderList_06_05_2026-12_05_2026.csv", minutes_old=20)

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_sellerboard_email_storage_cleanup_guard"]["status"] == "ok"
    assert rows["b_sellerboard_email_storage_cleanup_guard"]["luke_action_required"] == "0"


def test_b_mot_storage_cleanup_guard_still_needs_luke_for_non_orderlist(tmp_path: Path) -> None:
    _write_source_proof(tmp_path)
    _write_orderlist(tmp_path, "DRJ_Hardware_OrderList_20_05_2026-26_05_2026.csv")
    _write_csv(tmp_path / INBOX_REL_PATH / "random.csv", ["id"], [{"id": "1"}])

    result = build_b_hourly_mot(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["check"]: row for row in result["rows"]}

    assert rows["b_sellerboard_email_storage_cleanup_guard"]["status"] == "decision_needed"
    assert rows["b_sellerboard_email_storage_cleanup_guard"]["luke_action_required"] == "1"


def test_apply_email_cleanup_deletes_only_approved_older_orderlists(tmp_path: Path) -> None:
    _write_policy(tmp_path)
    latest = _write_orderlist(tmp_path, "DRJ_Hardware_OrderList_20_05_2026-26_05_2026.csv", minutes_old=0)
    second = _write_orderlist(tmp_path, "DRJ_Hardware_OrderList_13_05_2026-19_05_2026.csv", minutes_old=10)
    older = _write_orderlist(tmp_path, "DRJ_Hardware_OrderList_06_05_2026-12_05_2026.csv", minutes_old=20)
    random_file = tmp_path / INBOX_REL_PATH / "random.csv"
    _write_csv(random_file, ["id"], [{"id": "1"}])

    result = apply_sellerboard_email_cleanup(root=tmp_path, observed_utc=OBSERVED)

    assert result.deleted_count == 1
    assert latest.exists()
    assert second.exists()
    assert not older.exists()
    assert random_file.exists()
    assert result.manifest_path.exists()
