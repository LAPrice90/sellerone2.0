from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.one_off.P020_product_db_postgres_promotion_rehearsal import PRODUCT_DB_POSTGRES_DDL, run_check


def test_p020_offline_rehearsal_passes_and_does_not_promote(tmp_path: Path) -> None:
    payload = run_check(output_dir=tmp_path / "proof", observed_utc="2026-05-01T11:00:00Z")

    assert payload["status"] == "ok"
    assert payload["promotion_status"] == "not_run_requires_explicit_approval"
    assert payload["required_env_vars"] == ["SELLERONE_DATABASE_URL"]
    assert "PRIMARY KEY" in PRODUCT_DB_POSTGRES_DDL
    checks = pd.read_csv(tmp_path / "proof" / "product_db_postgres_promotion_rehearsal.csv", dtype=str).fillna("")
    promotion = checks[checks["check"].eq("production_promotion_status")].iloc[0]
    assert promotion["status"] == "ok"
    assert promotion["value"] == "not_run_requires_explicit_approval"
