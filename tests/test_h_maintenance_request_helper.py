from __future__ import annotations

import json

import pytest

from scripts.one_off import H200_request_h_maintenance as h200


def test_build_request_payload_is_bounded_to_h_actions() -> None:
    payload = h200.build_request_payload(
        action="pause",
        reason="o_market_proof",
        request_id="REQ_1",
        requested_by="codex_test",
        requested_utc="2026-05-27T12:00:00Z",
    )

    assert payload["flow"] == "H"
    assert payload["action"] == "pause"
    assert payload["request_id"] == "REQ_1"
    assert "pause" in payload["allowed_controller_actions"]
    assert "no price changes" in payload["forbidden_actions"]


def test_build_request_payload_rejects_non_controller_actions() -> None:
    with pytest.raises(ValueError, match="action_must_be_status_pause_or_resume"):
        h200.build_request_payload(action="run_market_scan", reason="bad")


def test_build_request_payload_rejects_unsafe_request_id() -> None:
    with pytest.raises(ValueError, match="request_id_has_unsafe_characters"):
        h200.build_request_payload(action="status", reason="check", request_id="bad/slash")


def test_write_request_creates_atomic_request_file(tmp_path) -> None:
    payload = h200.build_request_payload(
        action="status",
        reason="controller_probe",
        request_id="REQ_STATUS",
        requested_utc="2026-05-27T12:00:00Z",
    )

    path = h200.write_request(tmp_path, payload)

    assert path == tmp_path / "out" / "locks" / "h_maintenance_request.json"
    data = json.loads(path.read_text(encoding="ascii"))
    assert data["flow"] == "H"
    assert data["action"] == "status"
    assert data["request_id"] == "REQ_STATUS"


def test_write_request_refuses_to_overwrite_active_request_without_replace(tmp_path) -> None:
    first = h200.build_request_payload(
        action="status",
        reason="first",
        request_id="REQ_FIRST",
        requested_utc="2026-05-27T12:00:00Z",
    )
    second = h200.build_request_payload(
        action="resume",
        reason="second",
        request_id="REQ_SECOND",
        requested_utc="2026-05-27T12:00:00Z",
    )
    h200.write_request(tmp_path, first)

    with pytest.raises(FileExistsError):
        h200.write_request(tmp_path, second)

    path = h200.write_request(tmp_path, second, replace=True)
    data = json.loads(path.read_text(encoding="ascii"))
    assert data["request_id"] == "REQ_SECOND"
