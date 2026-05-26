from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.O.O009_build_legacy_purchase_list_bridge import build_legacy_purchase_list_bridge_from_rows


def _purchase_list_rows() -> list[list[str]]:
    return [
        ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
        [
            "Supplier",
            "SKU",
            "ASIN",
            "Name",
            "Qtys",
            "Barcode",
            "Supply Code",
            "CPU",
            "Ordrd",
            "Stock",
            "ROI",
            "Vlcity",
            "Days",
            "Recomend",
            "Restk",
            "Disc",
            "Drop",
            "Snze",
            "Ordered",
            "Price",
            "Done",
            "Text",
            "Resk Val",
        ],
        [
            "Alpha",
            "SKU-RESTOCK",
            "ASIN-RESTOCK",
            "Restock Product",
            "Unit",
            "1234567890123",
            "SUP-001",
            "£5.50",
            "2",
            "3",
            "36%",
            "1.5",
            "4",
            "Restock",
            "12",
            "FALSE",
            "FALSE",
            "FALSE",
            "",
            "",
            "FALSE",
            "buy",
            "£66.00",
        ],
        [
            "Beta",
            "SKU-NODATA",
            "ASIN-NODATA",
            "No Data Product",
            "Pack 2",
            "999",
            "BETA-9",
            "£3",
            "",
            "0",
            "",
            "",
            "",
            "No Data",
            "1",
            "FALSE",
            "FALSE",
            "FALSE",
            "",
            "",
            "FALSE",
            "",
            "FALSE",
        ],
        [
            "Gamma",
            "SKU-DROP",
            "ASIN-DROP",
            "Drop Product",
            "Unit",
            "",
            "",
            "£2",
            "",
            "8",
            "0%",
            "",
            "",
            "Drop",
            "0",
            "FALSE",
            "FALSE",
            "FALSE",
            "",
            "",
            "FALSE",
            "",
            "",
        ],
        [
            "Done Supplier",
            "SKU-DONE",
            "ASIN-DONE",
            "Done Product",
            "Unit",
            "",
            "",
            "£9",
            "",
            "",
            "20%",
            "",
            "",
            "Restock",
            "5",
            "FALSE",
            "FALSE",
            "FALSE",
            "",
            "",
            "TRUE",
            "",
            "",
        ],
        ["Blank Supplier", "", "", "", "", "", "", "", "", "", "", "", "", "Restock", "", "", "", "", "", "", "FALSE", "", ""],
    ]


def test_o009_parses_purchase_list_headers_values_and_filters_done_rows() -> None:
    bridge_df, health_df = build_legacy_purchase_list_bridge_from_rows(
        _purchase_list_rows(),
        bridge_utc="2026-05-22T10:00:00Z",
        source_path="test_rows",
    )

    assert len(bridge_df) == 3
    assert set(bridge_df["seller_sku"]) == {"SKU-RESTOCK", "SKU-NODATA", "SKU-DROP"}

    restock = bridge_df[bridge_df["seller_sku"] == "SKU-RESTOCK"].iloc[0]
    assert restock["supplier_name"] == "Alpha"
    assert restock["supplier_sku"] == "SUP-001"
    assert restock["barcode"] == "1234567890123"
    assert restock["suggested_action"] == "full_restock"
    assert restock["recommendation_status"] == "full_restock"
    assert restock["current_supplier_buy_cost_gbp"] == "5.5"
    assert restock["expected_forward_roi_pct"] == "36"
    assert restock["market_price_basis_used"] == "LEGACY_PURCHASE_LIST_ROI_BACKSOLVE"
    assert restock["suggested_market_price_gbp"] == "7.48"
    assert restock["suggested_qty"] == "12"
    assert restock["reorder_value_gbp"] == "66"
    assert restock["source_reference"].endswith(":row3")

    no_data = bridge_df[bridge_df["seller_sku"] == "SKU-NODATA"].iloc[0]
    assert no_data["suggested_action"] == "test_restock"
    assert no_data["recommendation_basis"] == "legacy_purchase_list_no_data"
    assert "NO_DATA_TEST_CANDIDATE" in no_data["bridge_note"]

    drop = bridge_df[bridge_df["seller_sku"] == "SKU-DROP"].iloc[0]
    assert drop["suggested_action"] == "wait"
    assert drop["drop_flag"] == "1"
    assert "DROP_VISIBLE_NOT_BUYABLE_BY_DEFAULT" in drop["bridge_note"]

    health = health_df.set_index("check")
    assert health.loc["headers_present", "status"] == "ok"
    assert health.loc["bridge_rows", "value"] == "3"
    assert health.loc["excluded_done_rows", "value"] == "1"
    assert health.loc["blank_sku_rows", "value"] == "1"
    assert health.loc["sheet_no_data_rows", "value"] == "1"


def test_o009_fails_when_required_purchase_list_headers_are_missing() -> None:
    rows = [["Supplier", "SKU", "ASIN", "Name"], ["Alpha", "SKU-1", "ASIN-1", "Missing fields"]]

    with pytest.raises(ValueError, match="missing required headers"):
        build_legacy_purchase_list_bridge_from_rows(rows, bridge_utc="2026-05-22T10:00:00Z")
