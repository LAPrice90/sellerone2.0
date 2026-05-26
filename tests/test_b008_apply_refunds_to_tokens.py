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

from scripts.flows.B import B008_apply_refunds_to_tokens as b008


EVENT_COLUMNS = [
    "order_id",
    "sku",
    "refund_date",
    "requested_qty",
    "applied_qty",
    "status",
    "note",
    "refund_event_id",
    "event_ts",
]


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def _patch_paths(monkeypatch, tmp_path: Path) -> Path:
    out = tmp_path / "out"
    ledger_live = out / "systems" / "B" / "live" / "token_ledger_live.csv"
    ledger_legacy = out / "token_ledger_live.csv"
    alloc_live = out / "systems" / "B" / "live" / "token_allocations_live.csv"
    alloc_legacy = out / "token_allocations_live.csv"
    monkeypatch.setattr(b008, "REFUNDS_CSV", out / "financial_events_refunds_official.csv")
    monkeypatch.setattr(b008, "OUT_EVENTS", out / "refund_token_events.csv")
    monkeypatch.setattr(b008, "WRITE_SHEETS", False)

    def resolve(path_or_rel: str, default_system: str = "B") -> SimpleNamespace:
        if str(path_or_rel) == "token_ledger_live.csv":
            return SimpleNamespace(live_path=ledger_live, legacy_path=ledger_legacy)
        return SimpleNamespace(live_path=alloc_live, legacy_path=alloc_legacy)

    monkeypatch.setattr(b008, "resolve_compat_path", resolve)

    def write_csv_with_compat(df: pd.DataFrame, *, path_or_rel: str, default_system: str = "B", index: bool = False, **_kwargs):
        target = resolve(path_or_rel, default_system)
        target.live_path.parent.mkdir(parents=True, exist_ok=True)
        target.legacy_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(target.live_path, index=index)
        df.to_csv(target.legacy_path, index=index)
        return target

    monkeypatch.setattr(b008, "write_csv_with_compat", write_csv_with_compat)
    return out


def test_b008_sql_primary_writes_refund_events_once_and_csv_export(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    sqlite_path = tmp_path / "pilot.sqlite3"
    _write_csv(
        out / "systems" / "B" / "live" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-1",
                "seller_sku": "SKU-A",
                "status": "allocated",
                "return_order_id": "",
                "return_date": "",
                "return_event_id": "",
            }
        ],
        ["token_id", "seller_sku", "status", "return_order_id", "return_date", "return_event_id"],
    )
    _write_csv(
        out / "systems" / "B" / "live" / "token_allocations_live.csv",
        [{"order_id": "ORDER-1", "seller_sku": "SKU-A", "token_id": "TOKEN-1"}],
        ["order_id", "seller_sku", "token_id"],
    )
    _write_csv(
        out / "financial_events_refunds_official.csv",
        [
            {
                "Order ID": "ORDER-1",
                "SKU": "SKU-A",
                "Date": "2026-04-28T10:00:00Z",
                "Quantity Ordered": "1",
                "Price_Total": "-10",
                "Shipping_Total": "0",
                "Gift_Total": "0",
                "Promotion_Total": "0",
            }
        ],
        ["Order ID", "SKU", "Date", "Quantity Ordered", "Price_Total", "Shipping_Total", "Gift_Total", "Promotion_Total"],
    )
    _write_csv(
        out / "refund_token_events.csv",
        [
            {
                "order_id": "ORDER-0",
                "sku": "SKU-Z",
                "refund_date": "2026-04-27",
                "requested_qty": "1",
                "applied_qty": "0",
                "status": "missing_allocations",
                "note": "existing",
                "refund_event_id": "prior-event",
                "event_ts": "2026-04-27T00:00:00Z",
            }
        ],
        EVENT_COLUMNS,
    )
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(sqlite_path))

    b008.main()

    events = pd.read_csv(out / "refund_token_events.csv", dtype=str).fillna("")
    assert len(events) == 2
    assert events["refund_event_id"].is_unique
    assert "prior-event" in set(events["refund_event_id"])
    assert "ok" in set(events["status"])

    ledger = pd.read_csv(out / "systems" / "B" / "live" / "token_ledger_live.csv", dtype=str).fillna("")
    assert ledger.loc[0, "status"] == "returned_pending"
    assert ledger.loc[0, "return_order_id"] == "ORDER-1"

    connection = sqlite3.connect(sqlite_path)
    try:
        rows = connection.execute(
            "SELECT order_id, sku, status FROM b_refund_token_events ORDER BY order_id"
        ).fetchall()
    finally:
        connection.close()

    assert rows == [
        ("ORDER-0", "SKU-Z", "missing_allocations"),
        ("ORDER-1", "SKU-A", "ok"),
    ]


def test_b008_csv_mode_keeps_single_new_refund_event(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    _write_csv(
        out / "systems" / "B" / "live" / "token_ledger_live.csv",
        [{"token_id": "TOKEN-1", "seller_sku": "SKU-A", "status": "allocated"}],
        ["token_id", "seller_sku", "status"],
    )
    _write_csv(
        out / "systems" / "B" / "live" / "token_allocations_live.csv",
        [{"order_id": "ORDER-1", "seller_sku": "SKU-A", "token_id": "TOKEN-1"}],
        ["order_id", "seller_sku", "token_id"],
    )
    _write_csv(
        out / "financial_events_refunds_official.csv",
        [{"Order ID": "ORDER-1", "SKU": "SKU-A", "Date": "2026-04-28", "Quantity Ordered": "1"}],
        ["Order ID", "SKU", "Date", "Quantity Ordered"],
    )
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "csv")

    b008.main()

    events = pd.read_csv(out / "refund_token_events.csv", dtype=str).fillna("")
    assert len(events) == 1
    assert events.loc[0, "order_id"] == "ORDER-1"
