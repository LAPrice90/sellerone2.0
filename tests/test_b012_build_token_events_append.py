from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.B import B012_build_token_events_append as b012


EVENT_COLUMNS = ["event_id", "event_ts", "event_type", "token_id", "order_id", "sku", "qty", "notes"]


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def _patch_paths(monkeypatch, tmp_path: Path) -> Path:
    out = tmp_path / "out"
    alloc_live = out / "systems" / "B" / "live" / "token_allocations_live.csv"
    alloc_legacy = out / "token_allocations_live.csv"
    monkeypatch.setattr(b012, "OUT_EVENTS", out / "token_events.csv")
    monkeypatch.setattr(b012, "OUT_REFUND_EVENTS", out / "refund_token_events.csv")
    monkeypatch.setattr(b012, "OUT_ADJUST_EVENTS", out / "stock_adjustment_token_events.csv")
    monkeypatch.setattr(
        b012,
        "resolve_compat_path",
        lambda *_args, **_kwargs: SimpleNamespace(live_path=alloc_live, legacy_path=alloc_legacy),
    )
    return out


def test_b012_sql_primary_writes_combined_event_log_and_csv_export(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    sqlite_path = tmp_path / "pilot.sqlite3"
    alloc_live = out / "systems" / "B" / "live" / "token_allocations_live.csv"
    _write_csv(
        alloc_live,
        [
            {
                "allocation_date": "2026-04-28",
                "order_id": "ORDER-1",
                "seller_sku": "SKU-A",
                "token_id": "TOKEN-1",
                "quantity": "1",
                "notes": "new allocation",
            }
        ],
        ["allocation_date", "order_id", "seller_sku", "token_id", "quantity", "notes"],
    )
    _write_csv(
        out / "token_events.csv",
        [
            {
                "event_id": "existing-event",
                "event_ts": "2026-04-27",
                "event_type": "Allocation",
                "token_id": "TOKEN-0",
                "order_id": "ORDER-0",
                "sku": "SKU-Z",
                "qty": "1",
                "notes": "already exported",
            }
        ],
        EVENT_COLUMNS,
    )
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(sqlite_path))
    monkeypatch.setenv("TOKEN_EVENTS_WRITE_SHEETS", "0")

    b012.main()

    csv_df = pd.read_csv(out / "token_events.csv", dtype=str).fillna("")
    assert len(csv_df) == 2
    assert set(csv_df["event_type"]) == {"Allocation"}
    assert "existing-event" in set(csv_df["event_id"])
    assert "TOKEN-1" in set(csv_df["token_id"])

    connection = sqlite3.connect(sqlite_path)
    try:
        rows = connection.execute(
            "SELECT event_id, token_id, order_id, sku FROM b_token_events ORDER BY token_id"
        ).fetchall()
    finally:
        connection.close()

    assert rows[0] == ("existing-event", "TOKEN-0", "ORDER-0", "SKU-Z")
    assert rows[1][1:] == ("TOKEN-1", "ORDER-1", "SKU-A")


def test_b012_csv_mode_still_appends_new_events(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    alloc_live = out / "systems" / "B" / "live" / "token_allocations_live.csv"
    _write_csv(
        alloc_live,
        [
            {
                "allocation_date": "2026-04-28",
                "order_id": "ORDER-1",
                "seller_sku": "SKU-A",
                "token_id": "TOKEN-1",
                "quantity": "1",
                "notes": "",
            }
        ],
        ["allocation_date", "order_id", "seller_sku", "token_id", "quantity", "notes"],
    )
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "csv")
    monkeypatch.setenv("TOKEN_EVENTS_WRITE_SHEETS", "0")

    b012.main()

    csv_df = pd.read_csv(out / "token_events.csv", dtype=str).fillna("")
    assert len(csv_df) == 1
    assert csv_df.loc[0, "token_id"] == "TOKEN-1"
