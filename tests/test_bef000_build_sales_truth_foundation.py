from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.one_off import BEF000_build_sales_truth_foundation as bef000


def _write_csv(path: Path, rows: list[dict[str, str]], *, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def test_build_sales_truth_foundation_outputs_and_health(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "out"
    monkeypatch.setattr(bef000, "ORDER_MASTER_PATH", out / "order_master.csv")
    monkeypatch.setattr(bef000, "ORDER_LEDGER_FX_PATH", out / "order_ledger_fx.csv")
    monkeypatch.setattr(bef000, "DAILY_TRUTH_PATH", out / "sku_daily_sales_truth_latest.csv")
    monkeypatch.setattr(bef000, "SALES_TRUTH_30D_PATH", out / "sales_truth_sku_30d_latest.csv")
    monkeypatch.setattr(bef000, "PERFORMANCE_PATH", out / "sku_performance_summary.csv")
    monkeypatch.setattr(bef000, "LISTING_SNAPSHOT_PATH", out / "listing_offer_snapshot_latest.csv")
    monkeypatch.setattr(bef000, "LISTING_HISTORY_PATH", out / "listing_offer_history.csv")

    _write_csv(
        out / "order_master.csv",
        [
            {"Date": "2026-04-20T13:00:00Z", "SKU": "SKU1"},
            {"Date": "2026-04-20T12:00:00Z", "SKU": "SKU2"},
        ],
        columns=["Date", "SKU"],
    )
    _write_csv(
        out / "order_ledger_fx.csv",
        [
            {"date": "2026-04-20T11:00:00Z", "SKU": "SKU1"},
            {"date": "2026-04-20T11:00:00Z", "SKU": "SKU3"},
        ],
        columns=["date", "SKU"],
    )
    _write_csv(
        out / "sku_daily_sales_truth_latest.csv",
        [
            {"sku": "SKU1", "date": "2026-04-19", "source_state": "finalized_ledger", "units": "5"},
            {"sku": "SKU1", "date": "2026-04-20", "source_state": "provisional_order_master", "units": "1"},
            {"sku": "SKU2", "date": "2026-04-20", "source_state": "provisional_order_master", "units": "2"},
            {"sku": "SKU3", "date": "2026-04-18", "source_state": "finalized_ledger", "units": "1"},
        ],
        columns=["sku", "date", "source_state", "units"],
    )
    _write_csv(
        out / "sales_truth_sku_30d_latest.csv",
        [{"sku": "SKU1", "asof_date": "2026-04-18"}],
        columns=["sku", "asof_date"],
    )
    _write_csv(
        out / "sku_performance_summary.csv",
        [{"sku": "SKU2", "asof_date": "2026-04-20"}],
        columns=["sku", "asof_date"],
    )
    _write_csv(
        out / "listing_offer_snapshot_latest.csv",
        [
            {"timestamp_utc": "2026-04-20T13:10:00Z", "sku": "SKU1", "asin": "A1"},
            {"timestamp_utc": "2026-04-20T13:10:00Z", "sku": "SKU2", "asin": "A2"},
        ],
        columns=["timestamp_utc", "sku", "asin"],
    )
    _write_csv(
        out / "listing_offer_history.csv",
        [
            {"timestamp_utc": "2026-04-19T13:10:00Z", "sku": "SKU2", "asin": "A2"},
            {"timestamp_utc": "2026-04-19T13:10:00Z", "sku": "SKU3", "asin": "A3"},
            {"timestamp_utc": "2026-04-20T12:50:00Z", "sku": "SKU3", "asin": "A4"},
        ],
        columns=["timestamp_utc", "sku", "asin"],
    )

    result = bef000.build_sales_truth_foundation(
        output_dir=tmp_path / "out" / "analysis_reports",
        observed_utc="2026-04-20T15:30:00Z",
    )

    assert result.foundation_path.exists()
    assert result.health_path.exists()

    foundation = pd.read_csv(result.foundation_path, dtype=str).fillna("")
    health = pd.read_csv(result.health_path, dtype=str).fillna("")

    rows = foundation.set_index("operational_sku")
    assert list(foundation["operational_sku"]) == ["SKU1", "SKU2", "SKU3"]

    assert rows.loc["SKU1", "operational_asin"] == "A1"
    assert rows.loc["SKU1", "asin_bridge_status"] == "resolved"
    assert rows.loc["SKU1", "latest_finalized_date"] == "2026-04-19"
    assert rows.loc["SKU1", "latest_provisional_date"] == "2026-04-20"
    assert rows.loc["SKU1", "truth_state"] == "finalized"
    assert rows.loc["SKU1", "ledger_freshness_status"] == "warn"
    assert rows.loc["SKU1", "stale_flag"] == "1"

    assert rows.loc["SKU3", "asin_bridge_status"] == "ambiguous"
    assert rows.loc["SKU3", "asin_ambiguity_flag"] == "1"
    assert rows.loc["SKU3", "asin_candidate_count"] == "2"

    metrics = health.set_index("metric")
    assert metrics.loc["foundation_rows_total", "value"] == "3"
    assert metrics.loc["bridge_resolved_count", "value"] == "2"
    assert metrics.loc["bridge_ambiguous_count", "value"] == "1"
    assert metrics.loc["bridge_unresolved_count", "value"] == "0"
    assert metrics.loc["freshness_warn_count", "value"] == "1"
    assert metrics.loc["freshness_fail_count", "value"] == "0"


def test_build_sales_truth_foundation_handles_missing_ledger_timestamp(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "out"
    monkeypatch.setattr(bef000, "ORDER_MASTER_PATH", out / "order_master.csv")
    monkeypatch.setattr(bef000, "ORDER_LEDGER_FX_PATH", out / "order_ledger_fx.csv")
    monkeypatch.setattr(bef000, "DAILY_TRUTH_PATH", out / "sku_daily_sales_truth_latest.csv")
    monkeypatch.setattr(bef000, "SALES_TRUTH_30D_PATH", out / "sales_truth_sku_30d_latest.csv")
    monkeypatch.setattr(bef000, "PERFORMANCE_PATH", out / "sku_performance_summary.csv")
    monkeypatch.setattr(bef000, "LISTING_SNAPSHOT_PATH", out / "listing_offer_snapshot_latest.csv")
    monkeypatch.setattr(bef000, "LISTING_HISTORY_PATH", out / "listing_offer_history.csv")

    _write_csv(
        out / "order_master.csv",
        [{"Date": "2026-04-20T13:00:00Z", "SKU": "SKU1"}],
        columns=["Date", "SKU"],
    )
    _write_csv(out / "order_ledger_fx.csv", [], columns=["date", "SKU"])

    result = bef000.build_sales_truth_foundation(
        output_dir=tmp_path / "out" / "analysis_reports",
        observed_utc="2026-04-20T15:35:00Z",
    )

    foundation = pd.read_csv(result.foundation_path, dtype=str).fillna("")
    health = pd.read_csv(result.health_path, dtype=str).fillna("")
    rows = foundation.set_index("operational_sku")
    metrics = health.set_index("metric")

    assert rows.loc["SKU1", "ledger_freshness_status"] == "fail"
    assert rows.loc["SKU1", "stale_flag"] == "1"
    assert metrics.loc["freshness_fail_count", "value"] == "1"
    assert "missing_order_ledger_fx_timestamp" in metrics.loc["freshness_lag_minutes", "notes"]


def test_build_sales_truth_foundation_uses_ledger_datetime_column_first(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "out"
    monkeypatch.setattr(bef000, "ORDER_MASTER_PATH", out / "order_master.csv")
    monkeypatch.setattr(bef000, "ORDER_LEDGER_FX_PATH", out / "order_ledger_fx.csv")
    monkeypatch.setattr(bef000, "DAILY_TRUTH_PATH", out / "sku_daily_sales_truth_latest.csv")
    monkeypatch.setattr(bef000, "SALES_TRUTH_30D_PATH", out / "sales_truth_sku_30d_latest.csv")
    monkeypatch.setattr(bef000, "PERFORMANCE_PATH", out / "sku_performance_summary.csv")
    monkeypatch.setattr(bef000, "LISTING_SNAPSHOT_PATH", out / "listing_offer_snapshot_latest.csv")
    monkeypatch.setattr(bef000, "LISTING_HISTORY_PATH", out / "listing_offer_history.csv")

    _write_csv(
        out / "order_master.csv",
        [{"Date": "2026-04-20T13:00:00Z", "SKU": "SKU1"}],
        columns=["Date", "SKU"],
    )
    _write_csv(
        out / "order_ledger_fx.csv",
        [
            {
                "Date": "2026-04-20T12:30:00Z",
                "date": "2026-04-20",
                "SKU": "SKU1",
            }
        ],
        columns=["Date", "date", "SKU"],
    )
    _write_csv(out / "sku_daily_sales_truth_latest.csv", [], columns=["sku", "date", "source_state", "units"])
    _write_csv(out / "sales_truth_sku_30d_latest.csv", [], columns=["sku", "asof_date"])
    _write_csv(out / "sku_performance_summary.csv", [], columns=["sku", "asof_date"])
    _write_csv(out / "listing_offer_snapshot_latest.csv", [], columns=["timestamp_utc", "sku", "asin"])
    _write_csv(out / "listing_offer_history.csv", [], columns=["timestamp_utc", "sku", "asin"])

    result = bef000.build_sales_truth_foundation(
        output_dir=tmp_path / "out" / "analysis_reports",
        observed_utc="2026-04-20T15:40:00Z",
    )

    foundation = pd.read_csv(result.foundation_path, dtype=str).fillna("")
    health = pd.read_csv(result.health_path, dtype=str).fillna("")
    rows = foundation.set_index("operational_sku")
    metrics = health.set_index("metric")

    assert rows.loc["SKU1", "order_ledger_fx_latest_utc"] == "2026-04-20T12:30:00Z"
    assert rows.loc["SKU1", "ledger_freshness_status"] == "ok"
    assert rows.loc["SKU1", "stale_flag"] == "0"
    assert metrics.loc["freshness_warn_count", "value"] == "0"
    assert metrics.loc["freshness_fail_count", "value"] == "0"
