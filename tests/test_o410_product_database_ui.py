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

from scripts.flows.O.O410_product_database_ui import (
    build_product_db_glance_df,
    filter_product_db_view,
    load_product_db_operator_view,
    product_db_status_counts,
)
from scripts.flows.O._schemas import get_o_output_contract


def _sample_view_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "seller_sku": "SKU-1",
                "asin": "ASIN-1",
                "title": "Alpha Item",
                "supplier_name": "Alpha",
                "supplier_sku": "A-1",
                "barcode": "111",
                "operational_status": "live",
                "order_qty_mode": "raw_units",
                "supplier_case_qty": "6",
                "valid_order_step": "6",
                "stock_available": "0",
                "ordered_open_qty": "4",
                "supplier_catalog_price": "2.49",
                "vat_rate": "20",
                "roi_snapshot_pct": "31.2",
                "velocity_30d": "2",
                "days_cover": "0",
                "data_issue_flags": "",
                "source_product_db_asof": "2099-01-01T00:00:00Z",
                "source_queue_asof": "2099-01-01T00:00:00Z",
                "source_ordered_asof": "2099-01-01T00:00:00Z",
                "source_velocity_asof": "2099-01-01T00:00:00Z",
                "source_performance_asof": "2099-01-01T00:00:00Z",
            },
            {
                "seller_sku": "SKU-2",
                "asin": "ASIN-2",
                "title": "Beta Item",
                "supplier_name": "Beta",
                "supplier_sku": "B-1",
                "barcode": "222",
                "operational_status": "snoozed",
                "order_qty_mode": "sell_packs",
                "sell_pack_qty": "2",
                "stock_available": "3",
                "ordered_open_qty": "0",
                "supplier_catalog_price": "3.50",
                "vat_rate": "20",
                "roi_snapshot_pct": "18.0",
                "velocity_30d": "1",
                "days_cover": "3",
                "data_issue_flags": "missing_vat",
                "source_product_db_asof": "2000-01-01T00:00:00Z",
                "source_queue_asof": "2000-01-01T00:00:00Z",
                "source_ordered_asof": "2000-01-01T00:00:00Z",
                "source_velocity_asof": "2000-01-01T00:00:00Z",
                "source_performance_asof": "2000-01-01T00:00:00Z",
            },
            {
                "seller_sku": "SKU-3",
                "asin": "ASIN-3",
                "title": "Gamma Item",
                "supplier_name": "Alpha",
                "supplier_sku": "A-3",
                "barcode": "333",
                "operational_status": "dropped",
                "order_qty_mode": "bundles",
                "sell_pack_qty": "3",
                "stock_available": "1",
                "ordered_open_qty": "0",
                "supplier_catalog_price": "4.00",
                "vat_rate": "0",
                "roi_snapshot_pct": "10.0",
                "velocity_30d": "0",
                "days_cover": "",
                "data_issue_flags": "",
                "source_product_db_asof": "2099-01-01T00:00:00Z",
                "source_queue_asof": "",
                "source_ordered_asof": "",
                "source_velocity_asof": "2099-01-01T00:00:00Z",
                "source_performance_asof": "2099-01-01T00:00:00Z",
            },
        ]
    )


def test_o410_status_counts_filters_and_glance_projection() -> None:
    view_df = _sample_view_df()

    counts = product_db_status_counts(view_df)
    assert counts == {
        "live": 1,
        "snoozed": 1,
        "discontinued": 0,
        "dropped": 1,
        "with_issues": 1,
        "rows": 3,
    }

    filtered = filter_product_db_view(
        view_df,
        search_text="SKU-1",
        supplier_filter="Alpha",
        status_filter=("live",),
        pack_mode_filter="raw_units",
        issues_only=False,
        low_stock_only=True,
    )
    assert len(filtered.index) == 1
    assert filtered.iloc[0]["seller_sku"] == "SKU-1"

    glance = build_product_db_glance_df(filtered)
    assert list(glance.columns) == [
        "Status",
        "Supplier",
        "SKU",
        "ASIN",
        "Name",
        "Packs",
        "Stock",
        "Ordered",
        "Cost",
        "VAT",
        "ROI",
        "V30",
        "Days",
        "Freshness",
        "Issues",
    ]
    assert glance.iloc[0]["Cost"] == "£2.49"
    assert glance.iloc[0]["Packs"] == "Case 6 | Step 6"
    assert glance.iloc[0]["Freshness"] == "ok"

    stale_only = filter_product_db_view(
        view_df,
        status_filter=("live", "snoozed", "discontinued", "dropped"),
        stale_only=True,
    )
    assert len(stale_only.index) == 1
    assert stale_only.iloc[0]["seller_sku"] == "SKU-2"


def test_o410_blank_optional_overlay_asof_is_not_stale() -> None:
    view_df = pd.DataFrame(
        [
            {
                "seller_sku": "SKU-OPT-1",
                "asin": "ASIN-OPT-1",
                "title": "Optional Overlay",
                "supplier_name": "Alpha",
                "operational_status": "live",
                "order_qty_mode": "raw_units",
                "supplier_case_qty": "1",
                "valid_order_step": "1",
                "stock_available": "5",
                "ordered_open_qty": "0",
                "supplier_catalog_price": "2.00",
                "vat_rate": "20",
                "roi_snapshot_pct": "25",
                "velocity_30d": "1",
                "days_cover": "5",
                "data_issue_flags": "",
                "source_product_db_asof": "2099-01-01T00:00:00Z",
                "source_queue_asof": "",
                "source_ordered_asof": "",
                "source_velocity_asof": "2099-01-01T00:00:00Z",
                "source_performance_asof": "2099-01-01T00:00:00Z",
            }
        ]
    )
    glance = build_product_db_glance_df(view_df)
    assert glance.iloc[0]["Freshness"] == "ok"


def test_o410_load_builds_view_when_snapshot_missing(tmp_path: Path) -> None:
    product_db_path = tmp_path / "out" / "product_db_preview.csv"
    product_db_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "seller_sku": "SKU-LOAD-1",
                "asin": "ASIN-LOAD-1",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "sale_status": "active",
                "supplier_pack_size": "1",
                "moq": "1",
                "supplier_catalog_price": "1.99",
                "last_purchase_price": "1.90",
                "vat_rate": "20",
            }
        ]
    ).to_csv(product_db_path, index=False)

    out_df = load_product_db_operator_view(root=tmp_path, force_refresh=True)
    assert len(out_df.index) == 1
    assert out_df.iloc[0]["seller_sku"] == "SKU-LOAD-1"

    view_path = tmp_path / get_o_output_contract("product_db_operator_view").rel_path
    assert view_path.exists()
