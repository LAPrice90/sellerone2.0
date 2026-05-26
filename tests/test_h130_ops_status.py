from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.H import H130_build_phase1_observation_sheet as h130
from scripts.flows.H.H130_build_phase1_observation_sheet import (
    _build_inventory_activity_df,
    _build_ops_alerts_df,
    _build_ops_status_df,
    _build_sales_today_from_live_orders_df,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")


def _write_split(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _metric_value(df: pd.DataFrame, metric: str) -> str:
    row = df.loc[df["metric"].astype(str).str.strip().eq(metric)]
    assert not row.empty
    return str(row.iloc[0].get("value", "")).strip()


def _metric_notes(df: pd.DataFrame, metric: str) -> str:
    row = df.loc[df["metric"].astype(str).str.strip().eq(metric)]
    assert not row.empty
    return str(row.iloc[0].get("notes", "")).strip()


def test_build_ops_status_df_reads_runtime_and_split_counts(tmp_path: Path) -> None:
    runtime_path = tmp_path / "H_runtime_status.json"
    run_state_path = tmp_path / "H_run_state.json"
    worker_path = tmp_path / "H_worker_lifecycle.json"
    publish_info_path = tmp_path / "H_cycle_last_publish_info.txt"
    publish_run_path = tmp_path / "H_cycle_last_publish_run_id.txt"
    a_split_path = tmp_path / "checklist_A_split.csv"
    b_split_path = tmp_path / "checklist_B_split.csv"
    e_split_path = tmp_path / "checklist_E_split.csv"
    h_split_path = tmp_path / "checklist_H_split.csv"

    _write_json(
        runtime_path,
        {
            "mode": "loop",
            "run_id": "RID123",
            "stage": "phase1_publish",
            "detail": "publish_start",
            "error": "runtime_err",
        },
    )
    _write_json(
        run_state_path,
        {
            "state": "failed",
            "stage": "phase1_publish",
            "failure_detail": "gate_blocked",
        },
    )
    _write_json(
        worker_path,
        {
            "state": "failed",
            "reason_code": "PUBLISH_BLOCKED",
            "reason_detail": "worker_reason",
        },
    )
    publish_info_path.write_text(
        "\n".join(
            [
                "utc=2026-03-30T09:45:00Z",
                "view_tab=2026-03-30",
                "rows=42",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    publish_run_path.write_text("RID123\n", encoding="utf-8")

    _write_split(
        a_split_path,
        [
            {"check": "a1", "status": "ok", "value": "1", "notes": ""},
            {"check": "a2", "status": "warn", "value": "1", "notes": ""},
            {"check": "a3", "status": "fail", "value": "1", "notes": ""},
        ],
    )
    _write_split(
        b_split_path,
        [
            {"check": "b1", "status": "ok", "value": "1", "notes": ""},
        ],
    )
    _write_split(
        e_split_path,
        [
            {"check": "e1", "status": "fail", "value": "1", "notes": ""},
            {"check": "e2", "status": "fail", "value": "1", "notes": ""},
        ],
    )
    _write_split(
        h_split_path,
        [
            {"check": "h1", "status": "warn", "value": "1", "notes": ""},
        ],
    )

    now_utc = datetime(2026, 3, 30, 10, 0, 0, tzinfo=timezone.utc)
    df = _build_ops_status_df(
        now_utc=now_utc,
        runtime_status_path=runtime_path,
        run_state_path=run_state_path,
        worker_lifecycle_path=worker_path,
        publish_info_path=publish_info_path,
        publish_run_path=publish_run_path,
        a_split_path=a_split_path,
        b_split_path=b_split_path,
        e_split_path=e_split_path,
        h_split_path=h_split_path,
    )

    assert _metric_value(df, "runtime_mode") == "loop"
    assert _metric_value(df, "runtime_run_id") == "RID123"
    assert _metric_value(df, "run_state") == "failed"
    assert _metric_value(df, "worker_state") == "failed"
    assert _metric_value(df, "last_publish_run_id") == "RID123"
    assert _metric_value(df, "last_publish_view_tab") == "2026-03-30"
    assert _metric_value(df, "last_publish_rows") == "42"
    assert _metric_value(df, "last_publish_age_minutes") == "15.00"
    assert _metric_value(df, "active_blocker") == "gate_blocked"
    assert _metric_value(df, "a_split_fail_count") == "1"
    assert _metric_value(df, "e_split_fail_count") == "2"
    assert _metric_value(df, "h_split_fail_count") == "0"
    assert "warn=1" in _metric_notes(df, "a_split_fail_count")
    assert "warn=0" in _metric_notes(df, "e_split_fail_count")
    assert "warn=1" in _metric_notes(df, "h_split_fail_count")


def test_build_ops_alerts_df_keeps_only_non_ok_rows(tmp_path: Path) -> None:
    a_split_path = tmp_path / "checklist_A_split.csv"
    h_split_path = tmp_path / "checklist_H_split.csv"
    missing_path = tmp_path / "missing.csv"

    _write_split(
        a_split_path,
        [
            {"check": "a_ok", "status": "ok", "value": "1", "notes": "none"},
            {"check": "a_warn", "status": "WARN", "value": "2", "notes": "warn note"},
            {"check": "a_fail", "status": "fail", "value": "0", "notes": "fail note"},
        ],
    )
    _write_split(
        h_split_path,
        [
            {"check": "h_ok", "status": "ok", "value": "1", "notes": "none"},
        ],
    )

    df = _build_ops_alerts_df(
        checklist_paths=[
            ("A", a_split_path),
            ("H", h_split_path),
            ("MISSING", missing_path),
        ]
    )

    assert len(df.index) == 2
    assert set(df["flow"].astype(str)) == {"A"}
    assert set(df["check"].astype(str)) == {"a_warn", "a_fail"}
    assert set(df["status"].astype(str)) == {"warn", "fail"}
    assert set(df["status_origin"].astype(str)) == {"warn", "fail"}
    assert set(df["source_path"].astype(str)) == {str(a_split_path)}
    assert all(str(value).strip() != "" for value in df["source_mtime_utc"].tolist())


def test_build_ops_alerts_df_marks_stale_non_ok_as_pending_recheck(tmp_path: Path) -> None:
    h_split_path = tmp_path / "checklist_H_split.csv"
    _write_split(
        h_split_path,
        [
            {"check": "h_warn", "status": "warn", "value": "1", "notes": "old warning"},
            {"check": "h_fail", "status": "fail", "value": "0", "notes": "old failure"},
        ],
    )
    old_ts = datetime(2026, 3, 30, 10, 0, 0, tzinfo=timezone.utc).timestamp()
    os.utime(h_split_path, (old_ts, old_ts))

    now_utc = datetime(2026, 3, 30, 12, 0, 0, tzinfo=timezone.utc)
    df = _build_ops_alerts_df(
        checklist_paths=[("H", h_split_path)],
        now_utc=now_utc,
        active_age_seconds=1800.0,
    )

    assert len(df.index) == 2
    assert set(df["status"].astype(str)) == {"pending_recheck"}
    assert set(df["status_origin"].astype(str)) == {"warn", "fail"}
    assert all("pending_from=" in str(v) for v in df["notes"].tolist())


def test_build_sales_today_from_live_orders_df_counts_same_day_pending_orders() -> None:
    now_utc = datetime(2026, 4, 3, 13, 0, 0, tzinfo=timezone.utc)
    orders_df = pd.DataFrame(
        [
            {"amazon_order_id": "O1", "purchase_date": "2026-04-03T09:35:09Z", "order_status": "Pending"},
            {"amazon_order_id": "O2", "purchase_date": "2026-04-03T10:50:02Z", "order_status": "Pending"},
            {"amazon_order_id": "O3", "purchase_date": "2026-04-03T11:55:03Z", "order_status": "Pending"},
            {"amazon_order_id": "O4", "purchase_date": "2026-04-03T12:58:18Z", "order_status": "Pending"},
            {"amazon_order_id": "OLD", "purchase_date": "2026-04-02T12:58:18Z", "order_status": "Pending"},
            {"amazon_order_id": "CANCEL", "purchase_date": "2026-04-03T08:00:00Z", "order_status": "Canceled"},
        ]
    )
    order_items_df = pd.DataFrame(
        [
            {"amazon_order_id": "O1", "seller_sku": "6V-EEC1-2S9Z", "quantity_ordered": "1"},
            {"amazon_order_id": "O2", "seller_sku": "6V-EEC1-2S9Z", "quantity_ordered": "1"},
            {"amazon_order_id": "O3", "seller_sku": "6V-EEC1-2S9Z", "quantity_ordered": "1"},
            {"amazon_order_id": "O4", "seller_sku": "6V-EEC1-2S9Z", "quantity_ordered": "1"},
            {"amazon_order_id": "OLD", "seller_sku": "6V-EEC1-2S9Z", "quantity_ordered": "5"},
            {"amazon_order_id": "CANCEL", "seller_sku": "6V-EEC1-2S9Z", "quantity_ordered": "7"},
        ]
    )

    df = _build_sales_today_from_live_orders_df(orders_df, order_items_df, now_utc)

    row = df.loc[df["sku"].astype(str).str.strip().eq("6V-EEC1-2S9Z")]
    assert not row.empty
    assert float(row.iloc[0].get("sales_units_today", 0)) == 4.0


def test_build_inventory_activity_df_applies_stale_sales_override(tmp_path: Path, monkeypatch) -> None:
    token_path = tmp_path / "token_ledger_live.csv"
    pd.DataFrame(columns=["seller_sku", "status"]).to_csv(token_path, index=False)
    monkeypatch.setattr(h130, "DEFAULT_TOKEN_LEDGER_PATH", token_path)

    inventory_df = pd.DataFrame(
        [
            {
                "seller_sku": "2T-07RT-8IMX",
                "available": "8",
                "total_quantity": "9",
                "inbound_working": "0",
                "inbound_shipped": "0",
                "inbound_receiving": "0",
                "last_updated_time": "2020-01-01T00:00:00Z",
            }
        ]
    )
    order_master_df = pd.DataFrame(
        [
            {"SKU": "2T-07RT-8IMX", "Quantity Ordered": "8", "Date": "2026-04-06T15:48:15Z"},
        ]
    )

    out = _build_inventory_activity_df(inventory_df, order_master_df)

    assert len(out.index) == 1
    row = out.iloc[0]
    assert str(row.get("sku", "")) == "2T-07RT-8IMX"
    assert float(row.get("available_stock_qty", 0) or 0) == 0.0
