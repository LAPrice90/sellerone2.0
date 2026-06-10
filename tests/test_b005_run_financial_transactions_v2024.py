from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.B import B005_run_financial_transactions_v2024 as b005


def test_b005_save_marker_writes_normalised_utc_marker(monkeypatch, tmp_path: Path) -> None:
    marker_path = tmp_path / "out" / "financial_transactions_v2024_last_posted.txt"
    monkeypatch.setattr(b005, "MARKER_PATH", marker_path)

    b005._save_marker("2026-05-26T18:34:33+00:00")

    assert marker_path.read_text(encoding="utf-8") == "2026-05-26T18:34:33Z"


def test_b005_save_marker_retries_transient_windows_replace_error(monkeypatch, tmp_path: Path) -> None:
    marker_path = tmp_path / "out" / "financial_transactions_v2024_last_posted.txt"
    real_replace = b005.os.replace
    attempts = {"count": 0}
    monkeypatch.setattr(b005, "MARKER_PATH", marker_path)

    def flaky_replace(src: Path, dst: Path) -> None:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise OSError(22, "Invalid argument")
        real_replace(src, dst)

    monkeypatch.setattr(b005.os, "replace", flaky_replace)

    b005._save_marker("2026-05-26T18:34:33Z")

    assert attempts["count"] == 2
    assert marker_path.read_text(encoding="utf-8") == "2026-05-26T18:34:33Z"


def test_b005_save_marker_raises_after_repeated_replace_errors(monkeypatch, tmp_path: Path) -> None:
    marker_path = tmp_path / "out" / "financial_transactions_v2024_last_posted.txt"
    monkeypatch.setattr(b005, "MARKER_PATH", marker_path)
    monkeypatch.setattr(
        b005.os,
        "replace",
        lambda src, dst: (_ for _ in ()).throw(OSError(22, "Invalid argument")),
    )

    with pytest.raises(OSError):
        b005._save_marker("2026-05-26T18:34:33Z")
