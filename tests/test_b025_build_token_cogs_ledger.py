from __future__ import annotations

import sqlite3

import pandas as pd

from scripts.flows.B import B025_build_token_cogs_ledger as b025


def test_b025_prefers_explicit_allocations_when_both_sources_exist(monkeypatch, tmp_path):
    alloc_path = tmp_path / "token_allocations_live.csv"
    ledger_path = tmp_path / "token_ledger_live.csv"
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    pd.DataFrame(
        [
            {
                "order_id": "ORDER-1",
                "order_date": "2026-04-03T12:00:00Z",
                "seller_sku": "SKU-1",
                "token_id": "ALLOC-TOKEN-1",
                "token_cost": "2.22",
                "currency": "GBP",
                "allocation_date": "2026-04-03T12:01:00Z",
                "quantity": "1",
                "source": "token_allocations_live",
            }
        ]
    ).to_csv(alloc_path, index=False)

    pd.DataFrame(
        [
            {
                "order_id": "ORDER-1",
                "order_date": "2026-04-03T12:00:00Z",
                "seller_sku": "SKU-1",
                "token_id": "LEDGER-TOKEN-1",
                "token_cost": "99.99",
                "currency": "GBP",
                "allocation_date": "2026-04-03T12:01:00Z",
                "quantity": "1",
                "source": "token_ledger_live",
            }
        ]
    ).to_csv(ledger_path, index=False)

    monkeypatch.setattr(
        b025,
        "_compat_read_path",
        lambda rel: alloc_path if rel == b025.ALLOC_REL else ledger_path,
    )
    monkeypatch.setattr(b025, "OUT_LEDGER", out_dir / "token_cogs_ledger.csv")
    monkeypatch.setattr(b025, "PRODUCT_DB", tmp_path / "missing_product_db.csv")

    b025.main()

    built = pd.read_csv(out_dir / "token_cogs_ledger.csv", dtype=str).fillna("")
    assert len(built) == 1
    assert built.loc[0, "token_id"] == "ALLOC-TOKEN-1"
    assert built.loc[0, "source"] == "token_allocations_live"


def test_b025_supplements_missing_alloc_rows_from_ledger(monkeypatch, tmp_path):
    alloc_path = tmp_path / "token_allocations_live.csv"
    ledger_path = tmp_path / "token_ledger_live.csv"
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    pd.DataFrame(
        [
            {
                "order_id": "ORDER-1",
                "order_date": "2026-04-03T12:00:00Z",
                "seller_sku": "SKU-1",
                "token_id": "TOKEN-1",
                "token_cost": "2.22",
                "currency": "GBP",
                "allocation_date": "2026-04-03T12:01:00Z",
                "quantity": "1",
                "source": "token_allocations_live",
            }
        ]
    ).to_csv(alloc_path, index=False)

    pd.DataFrame(
        [
            {
                "order_id": "ORDER-1",
                "order_date": "2026-04-03T12:00:00Z",
                "seller_sku": "SKU-1",
                "token_id": "TOKEN-1",
                "token_cost": "2.22",
                "currency": "GBP",
                "allocation_date": "2026-04-03T12:01:00Z",
                "quantity": "1",
                "source": "token_ledger_live",
            },
            {
                "order_id": "ORDER-2",
                "order_date": "2026-04-04T12:00:00Z",
                "seller_sku": "SKU-1",
                "token_id": "TOKEN-2",
                "token_cost": "3.33",
                "currency": "GBP",
                "allocation_date": "2026-04-04T12:01:00Z",
                "quantity": "1",
                "source": "token_ledger_live",
            },
        ]
    ).to_csv(ledger_path, index=False)

    monkeypatch.setattr(
        b025,
        "_compat_read_path",
        lambda rel: alloc_path if rel == b025.ALLOC_REL else ledger_path,
    )
    monkeypatch.setattr(b025, "OUT_LEDGER", out_dir / "token_cogs_ledger.csv")
    monkeypatch.setattr(b025, "PRODUCT_DB", tmp_path / "missing_product_db.csv")

    b025.main()

    built = pd.read_csv(out_dir / "token_cogs_ledger.csv", dtype=str).fillna("")
    assert set(built["token_id"]) == {"TOKEN-1", "TOKEN-2"}
    assert built.loc[built["token_id"] == "TOKEN-1", "source"].iloc[0] == "token_allocations_live"
    assert built.loc[built["token_id"] == "TOKEN-2", "source"].iloc[0] == "token_ledger_live"


def test_b025_sql_primary_writes_sql_before_csv_export(monkeypatch, tmp_path):
    alloc_path = tmp_path / "token_allocations_live.csv"
    ledger_path = tmp_path / "missing_token_ledger_live.csv"
    out_dir = tmp_path / "out"
    sqlite_path = tmp_path / "pilot.sqlite3"
    out_dir.mkdir()

    pd.DataFrame(
        [
            {
                "order_id": "ORDER-1",
                "order_date": "2026-04-03T12:00:00Z",
                "seller_sku": "SKU-1",
                "token_id": "ALLOC-TOKEN-1",
                "token_cost": "2.22",
                "currency": "GBP",
                "allocation_date": "2026-04-03T12:01:00Z",
            }
        ]
    ).to_csv(alloc_path, index=False)

    monkeypatch.setattr(
        b025,
        "_compat_read_path",
        lambda rel: alloc_path if rel == b025.ALLOC_REL else ledger_path,
    )
    monkeypatch.setattr(b025, "OUT_LEDGER", out_dir / "token_cogs_ledger.csv")
    monkeypatch.setattr(b025, "PRODUCT_DB", tmp_path / "missing_product_db.csv")
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(sqlite_path))

    b025.main()

    built = pd.read_csv(out_dir / "token_cogs_ledger.csv", dtype=str).fillna("")
    assert len(built) == 1
    assert built.loc[0, "token_id"] == "ALLOC-TOKEN-1"

    connection = sqlite3.connect(sqlite_path)
    try:
        rows = connection.execute(
            "SELECT order_id, seller_sku, token_id FROM b_token_cogs_ledger"
        ).fetchall()
    finally:
        connection.close()
    assert rows == [("ORDER-1", "SKU-1", "ALLOC-TOKEN-1")]
