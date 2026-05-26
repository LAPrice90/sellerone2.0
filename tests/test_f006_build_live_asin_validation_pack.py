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

from scripts.one_off.F006_build_live_asin_validation_pack import build_live_asin_validation_pack


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def test_f006_builds_mixed_case_pack_with_amazon_links(tmp_path: Path) -> None:
    scrape_path = tmp_path / "scrape.csv"
    output_dir = tmp_path / "out"
    _write_csv(
        scrape_path,
        [
            {
                "observed_utc": "2026-04-14T09:00:00Z",
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "supplier_sku": "SKU-OK-1",
                "asin": "B00OK0001",
                "bbp_sales_last_completed_month_label": "2026-03",
                "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
            },
            {
                "observed_utc": "2026-04-14T09:05:00Z",
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "supplier_sku": "SKU-OK-2",
                "asin": "B00OK0002",
                "bbp_sales_last_completed_month_label": "2026-03",
                "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
            },
            {
                "observed_utc": "2026-04-14T09:10:00Z",
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "supplier_sku": "SKU-ZERO-1",
                "asin": "B00ZERO01",
                "bbp_sales_last_completed_month_label": "",
                "bbp_sales_replay_demand_basis_source": "bbp_zero_history",
            },
            {
                "observed_utc": "2026-04-14T09:15:00Z",
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "supplier_sku": "SKU-MISS-1",
                "asin": "B00MISS01",
                "bbp_sales_last_completed_month_label": "",
                "bbp_sales_replay_demand_basis_source": "",
            },
            {
                "observed_utc": "2026-04-14T09:20:00Z",
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "supplier_sku": "SKU-MISS-2",
                "asin": "B00MISS02",
                "bbp_sales_last_completed_month_label": "",
                "bbp_sales_replay_demand_basis_source": "",
            },
        ],
    )

    result = build_live_asin_validation_pack(
        scrape_path=scrape_path,
        output_dir=output_dir,
        completed_count=2,
        zero_history_count=1,
        missing_basis_count=2,
        observed_utc="2026-04-14T09:30:00Z",
    )

    assert len(result.pack_df) == 5
    assert result.report_path.exists()
    assert result.latest_path.exists()
    assert set(result.pack_df["validation_case"].tolist()) == {
        "trusted_completed_month",
        "explicit_zero_history",
        "missing_completed_month_basis",
    }
    assert set(result.pack_df["amazon_link"].tolist()) == {
        "https://www.amazon.co.uk/dp/B00OK0001",
        "https://www.amazon.co.uk/dp/B00OK0002",
        "https://www.amazon.co.uk/dp/B00ZERO01",
        "https://www.amazon.co.uk/dp/B00MISS01",
        "https://www.amazon.co.uk/dp/B00MISS02",
    }


def test_f006_keeps_latest_row_per_asin_and_sku(tmp_path: Path) -> None:
    scrape_path = tmp_path / "scrape.csv"
    output_dir = tmp_path / "out"
    _write_csv(
        scrape_path,
        [
            {
                "observed_utc": "2026-04-14T08:00:00Z",
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "supplier_sku": "SKU-1",
                "asin": "B00DUP001",
                "bbp_sales_last_completed_month_label": "2026-02",
                "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
            },
            {
                "observed_utc": "2026-04-14T09:00:00Z",
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "supplier_sku": "SKU-1",
                "asin": "B00DUP001",
                "bbp_sales_last_completed_month_label": "2026-03",
                "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
            },
        ],
    )

    result = build_live_asin_validation_pack(
        scrape_path=scrape_path,
        output_dir=output_dir,
        completed_count=1,
        zero_history_count=0,
        missing_basis_count=0,
        observed_utc="2026-04-14T09:30:00Z",
    )

    assert len(result.pack_df) == 1
    row = result.pack_df.iloc[0]
    assert row["bbp_sales_last_completed_month_label"] == "2026-03"
