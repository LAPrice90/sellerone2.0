from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core import safe_file_writes


def test_safe_to_csv_writes_csv_atomically(tmp_path: Path) -> None:
    output_path = tmp_path / "out" / "report.csv"

    safe_file_writes.safe_to_csv(pd.DataFrame([{"sku": "SKU-1", "qty": 2}]), output_path, index=False)

    built = pd.read_csv(output_path, dtype=str).fillna("")
    assert built.loc[0, "sku"] == "SKU-1"
    assert built.loc[0, "qty"] == "2"


def test_safe_to_csv_retries_transient_windows_replace_error(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / "out" / "report.csv"
    real_replace = safe_file_writes.os.replace
    attempts = {"count": 0}

    def flaky_replace(src: str, dst: Path) -> None:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise OSError(22, "Invalid argument")
        real_replace(src, dst)

    monkeypatch.setattr(safe_file_writes.os, "replace", flaky_replace)

    safe_file_writes.safe_to_csv(pd.DataFrame([{"sku": "SKU-1"}]), output_path, index=False)

    assert attempts["count"] == 2
    assert output_path.exists()


def test_safe_to_csv_raises_after_repeated_replace_errors(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / "out" / "report.csv"
    monkeypatch.setattr(
        safe_file_writes.os,
        "replace",
        lambda src, dst: (_ for _ in ()).throw(OSError(22, "Invalid argument")),
    )

    with pytest.raises(OSError):
        safe_file_writes.safe_to_csv(pd.DataFrame([{"sku": "SKU-1"}]), output_path, index=False)
