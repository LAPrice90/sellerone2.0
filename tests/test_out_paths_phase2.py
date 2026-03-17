from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from scripts.core.out_paths import resolve_compat_path, write_csv_with_compat


def test_resolve_token_ledger_maps_to_b_live() -> None:
    resolved = resolve_compat_path("token_ledger_live.csv")
    assert str(resolved.live_path).replace("\\", "/") == "out/systems/B/live/token_ledger_live.csv"
    assert str(resolved.legacy_path).replace("\\", "/") == "out/token_ledger_live.csv"
    assert resolved.system == "B"


def test_write_csv_with_compat_writes_live_and_legacy(tmp_path: Path) -> None:
    cwd = Path.cwd()
    try:
        # Execute under temp folder so test does not alter repo outputs.
        os.chdir(tmp_path)
        df = pd.DataFrame([{"a": "1"}, {"a": "2"}], dtype=str)
        resolved = write_csv_with_compat(
            df,
            path_or_rel="token_allocations_live.csv",
            default_system="B",
            index=False,
            mirror_legacy=True,
        )
        assert resolved.live_path.exists()
        assert resolved.legacy_path.exists()
        live_df = pd.read_csv(resolved.live_path, dtype=str).fillna("")
        legacy_df = pd.read_csv(resolved.legacy_path, dtype=str).fillna("")
        assert len(live_df.index) == 2
        assert live_df.equals(legacy_df)
    finally:
        os.chdir(cwd)

