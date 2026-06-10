from __future__ import annotations

import base64
from pathlib import Path

from scripts.flows.F.seller_central_login_recovery import (
    SellerCentralCodeResult,
    append_seller_central_login_recovery_proof,
    extract_seller_central_code,
    fetch_latest_seller_central_code,
    load_seller_central_login_recovery_config,
    mark_seller_central_code_message_used,
    run_read_only_otp_intake_proof,
)


class _FakeExecute:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def execute(self) -> dict:
        return self.payload


class _FakeMessages:
    def __init__(self, messages: dict[str, dict]) -> None:
        self.messages = messages

    def list(self, **_kwargs: object) -> _FakeExecute:
        return _FakeExecute({"messages": [{"id": message_id} for message_id in self.messages]})

    def get(self, *, id: str, **_kwargs: object) -> _FakeExecute:
        return _FakeExecute(self.messages[id])


class _FakeUsers:
    def __init__(self, messages: dict[str, dict]) -> None:
        self.messages_api = _FakeMessages(messages)

    def messages(self) -> _FakeMessages:
        return self.messages_api


class _FakeGmail:
    def __init__(self, messages: dict[str, dict]) -> None:
        self.users_api = _FakeUsers(messages)

    def users(self) -> _FakeUsers:
        return self.users_api


def _gmail_message(*, internal_ms: int, text: str) -> dict:
    encoded = base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")
    return {
        "internalDate": str(internal_ms),
        "snippet": "",
        "payload": {
            "mimeType": "text/plain",
            "body": {"data": encoded},
        },
    }


def test_seller_central_env_and_proof_redact_secret_values(tmp_path: Path) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_proof.csv"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
                "SELLER_CENTRAL_CODE_GMAIL_LABEL=AmazonOTP",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    config = load_seller_central_login_recovery_config(env_path=env_path)

    append_seller_central_login_recovery_proof(
        config,
        status="waiting_for_code",
        reason="seller@example.test secret-password 123456",
        context="unit_test",
        code_seen=True,
        proof_path=proof_path,
    )

    proof_text = proof_path.read_text(encoding="utf-8")
    assert "seller@example.test" not in proof_text
    assert "secret-password" not in proof_text
    assert "123456" not in proof_text
    assert "waiting_for_code" in proof_text


def test_seller_central_code_label_defaults_to_amazon_otp(tmp_path: Path) -> None:
    env_path = tmp_path / "seller_central_login.env"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=0",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    config = load_seller_central_login_recovery_config(env_path=env_path)

    assert config.code_gmail_label == "AmazonOTP"


def test_seller_central_code_extraction_accepts_six_digit_code() -> None:
    assert extract_seller_central_code("Your Amazon verification code is 123456.") == "123456"
    assert extract_seller_central_code("Reference 12345 is not long enough.") == ""


def test_fetch_latest_seller_central_code_accepts_only_fresh_messages() -> None:
    service = _FakeGmail(
        {
            "old": _gmail_message(internal_ms=1_767_225_600_000, text="Amazon code 111111"),
            "fresh": _gmail_message(internal_ms=1_767_225_660_000, text="Amazon code 222222"),
        }
    )

    result = fetch_latest_seller_central_code(
        root=Path("."),
        label="AmazonOTP",
        requested_after_utc="2026-01-01T00:00:30Z",
        max_age_seconds=120,
        service=service,
        now_utc="2026-01-01T00:01:10Z",
    )

    assert isinstance(result, SellerCentralCodeResult)
    assert result.status == "found"
    assert result.code == "222222"
    assert result.message_id == "fresh"


def test_fetch_latest_seller_central_code_rejects_stale_messages() -> None:
    service = _FakeGmail(
        {
            "stale": _gmail_message(internal_ms=1_767_225_600_000, text="Amazon code 333333"),
        }
    )

    result = fetch_latest_seller_central_code(
        root=Path("."),
        label="AmazonOTP",
        requested_after_utc="2026-01-01T00:00:00Z",
        max_age_seconds=10,
        service=service,
        now_utc="2026-01-01T00:01:00Z",
    )

    assert result.status == "not_found"
    assert result.code == ""


def test_fetch_latest_seller_central_code_rejects_used_message(tmp_path: Path) -> None:
    service = _FakeGmail(
        {
            "fresh": _gmail_message(internal_ms=1_767_225_660_000, text="Amazon code 444444"),
        }
    )
    used_path = tmp_path / "used_messages.csv"
    mark_seller_central_code_message_used(
        SellerCentralCodeResult(
            status="found",
            reason="fresh_code_found",
            code="444444",
            message_id="fresh",
            message_ts_utc="2026-01-01T00:01:00Z",
            age_seconds=10,
        ),
        context="unit_test",
        used_path=used_path,
    )

    result = fetch_latest_seller_central_code(
        root=Path("."),
        label="AmazonOTP",
        requested_after_utc="2026-01-01T00:00:30Z",
        max_age_seconds=120,
        service=service,
        now_utc="2026-01-01T00:01:10Z",
        used_path=used_path,
    )

    assert result.status == "not_found"
    assert result.reason == "fresh_code_already_used"


def test_read_only_otp_intake_proof_marks_message_used_and_redacts(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    used_path = tmp_path / "used_messages.csv"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=0",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
                "SELLER_CENTRAL_CODE_GMAIL_LABEL=AmazonOTP",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    service = _FakeGmail(
        {
            "fresh": _gmail_message(internal_ms=1_767_225_660_000, text="Amazon code 555555"),
        }
    )

    row = run_read_only_otp_intake_proof(
        requested_after_utc="2026-01-01T00:00:30Z",
        proof_path=proof_path,
        used_path=used_path,
        service=service,
        now_utc="2026-01-01T00:01:10Z",
    )

    assert row["status"] == "otp_intake_proved"
    assert row["gmail_label"] == "AmazonOTP"
    assert row["code_seen_flag"] == "1"
    assert row["fresh_code_flag"] == "1"
    assert used_path.exists()
    proof_text = proof_path.read_text(encoding="utf-8")
    assert "555555" not in proof_text
    assert "secret-password" not in proof_text
