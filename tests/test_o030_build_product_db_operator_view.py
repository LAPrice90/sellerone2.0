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

from scripts.flows.O.O030_build_product_db_operator_view import build_product_db_operator_view
from scripts.flows.O._schemas import get_o_output_contract
from scripts.core.storage.product_db_contract import PRODUCT_DB_REQUIRED_COLUMNS, stage_product_db_import_sqlite


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_o_contract_rows(tmp_path: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
    contract = get_o_output_contract(contract_name)
    path = tmp_path / contract.rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = [*contract.required_columns, *contract.optional_columns]
    normalized: list[dict[str, str]] = []
    for row in rows:
        normalized.append({col: str(row.get(col, "") or "") for col in cols})
    pd.DataFrame(normalized, columns=cols).to_csv(path, index=False)


def _required_product_row(seller_sku: str, asin: str) -> dict[str, str]:
    row = {column: "" for column in PRODUCT_DB_REQUIRED_COLUMNS}
    row.update(
        {
            "seller_sku": seller_sku,
            "asin": asin,
            "title": f"Title {seller_sku}",
            "brand_name": "Brand",
            "main_image": "",
            "sale_status": "active",
            "supplier_code": "SUP",
            "supplier_name": "Supplier",
            "supplier_pack_size": "1",
            "amazon_pack_size": "1",
            "supplier_catalog_price": "1.00",
            "last_purchase_price": "1.00",
            "vat_rate": "20",
            "fba_fee_10": "",
            "fba_fee_100": "",
            "referral_fee_10": "",
            "referral_fee_100": "",
            "live_listing_price": "",
            "stock_total": "0",
            "stock_available": "0",
            "stock_reserved": "0",
            "stock_inbound": "0",
            "last_updated": "2026-05-01T10:00:00Z",
        }
    )
    return row


def test_o030_builds_operator_view_with_status_precedence_and_overlays(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "product_db_preview.csv",
        [
            {
                "seller_sku": "SKU-A",
                "asin": "ASIN-A",
                "title": "Alpha Product",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "supplier_sku": "ALPHA-SUP-1",
                "barcode": "111",
                "sale_status": "active",
                "supplier_pack_size": "1",
                "amazon_pack_size": "1",
                "order_qty_mode": "raw_units",
                "sell_pack_qty": "1",
                "supplier_case_qty": "6",
                "supplier_case_multiple": "1",
                "valid_order_step": "6",
                "moq": "1",
                "supplier_catalog_price": "2.49",
                "last_purchase_price": "2.35",
                "vat_rate": "20",
                "stock_available": "4",
                "stock_total": "6",
            },
            {
                "seller_sku": "SKU-B",
                "asin": "ASIN-B",
                "title": "Beta Product",
                "supplier_code": "SUP-B",
                "supplier_name": "Beta",
                "sale_status": "dropped",
                "supplier_pack_size": "1",
                "amazon_pack_size": "1",
                "order_qty_mode": "raw_units",
                "sell_pack_qty": "1",
                "supplier_case_qty": "1",
                "supplier_case_multiple": "0",
                "valid_order_step": "1",
                "moq": "1",
            },
        ],
    )
    _write_csv(
        tmp_path / "out" / "sku_sales_velocity.csv",
        [
            {"sku": "SKU-A", "v30": "2", "available": "4", "total_quantity": "6", "asof_date": "2026-04-17"},
            {"sku": "SKU-B", "v30": "1", "available": "0", "total_quantity": "0", "asof_date": "2026-04-17"},
        ],
    )
    _write_csv(
        tmp_path / "out" / "sku_performance_summary.csv",
        [
            {
                "sku": "SKU-A",
                "roi_at_our_price_pct": "31.5",
                "roi_at_buy_box_price_pct": "29.0",
                "current_token_cost_gbp": "1.2",
                "expected_refund_cost_per_unit_gbp": "0.1",
                "asof_date": "2026-04-17",
            }
        ],
    )
    _write_o_contract_rows(
        tmp_path,
        "restock_review_queue",
        [
            {
                "queue_utc": "2026-04-17T09:00:00Z",
                "seller_sku": "SKU-A",
                "asin": "ASIN-A",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "queue_status": "snoozed",
                "recommendation_status": "full_restock",
                "suggested_qty": "12",
                "days_cover_available_only": "2.0",
                "snooze_until_utc": "2026-04-21T00:00:00Z",
            }
        ],
    )
    _write_o_contract_rows(
        tmp_path,
        "ordered_stock_state",
        [
            {
                "asof_utc": "2026-04-17T10:00:00Z",
                "seller_sku": "SKU-A",
                "remaining_open_qty": "3",
            },
            {
                "asof_utc": "2026-04-17T11:00:00Z",
                "seller_sku": "SKU-A",
                "remaining_open_qty": "2",
            },
        ],
    )

    out_df = build_product_db_operator_view(root=tmp_path, asof_utc="2026-04-17T12:00:00Z")
    assert len(out_df.index) == 2

    row_a = out_df[out_df["seller_sku"] == "SKU-A"].iloc[0]
    assert row_a["operational_status"] == "snoozed"
    assert row_a["status_reason"] == "queue_snoozed"
    assert row_a["ordered_open_qty"] == "5"
    assert row_a["days_cover"] == "2.0"
    assert row_a["pack_profile_label"] == "Case 6 | Step 6"
    assert row_a["source_ordered_asof"] == "2026-04-17T11:00:00Z"

    row_b = out_df[out_df["seller_sku"] == "SKU-B"].iloc[0]
    assert row_b["operational_status"] == "dropped"
    assert row_b["status_reason"] == "sale_status_dropped"
    assert row_b["data_issue_flags"] == "missing_cost|missing_vat"

    out_path = tmp_path / get_o_output_contract("product_db_operator_view").rel_path
    assert out_path.exists()


def test_o030_writes_empty_aligned_output_when_product_db_missing(tmp_path: Path) -> None:
    out_df = build_product_db_operator_view(root=tmp_path, asof_utc="2026-04-17T12:00:00Z")
    contract = get_o_output_contract("product_db_operator_view")
    expected_cols = [*contract.required_columns, *contract.optional_columns]
    assert list(out_df.columns) == expected_cols
    assert len(out_df.index) == 0
    health_path = tmp_path / get_o_output_contract("product_db_source_health").rel_path
    assert health_path.exists()
    health_df = pd.read_csv(health_path, dtype=str).fillna("")
    assert health_df.iloc[0]["check"] == "product_db_source_exists"
    assert health_df.iloc[0]["status"] == "fail"


def test_o030_prefers_sql_product_db_authority_when_present(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "product_db_preview.csv",
        [
            {
                "seller_sku": "SKU-CSV",
                "asin": "ASIN-CSV",
                "title": "CSV Product",
                "supplier_code": "CSV",
                "supplier_name": "CSV Supplier",
                "sale_status": "active",
            }
        ],
    )
    sql_df = pd.DataFrame(
        [
            {**_required_product_row("SKU-SQL-1", "ASIN-SQL-1"), "supplier_sku": "SQL-1"},
            {**_required_product_row("SKU-SQL-2", "ASIN-SQL-2"), "supplier_sku": "SQL-2"},
        ]
    )
    stage_product_db_import_sqlite(
        df=sql_df,
        sqlite_path=tmp_path / "out" / "sql" / "sellerone_dev.sqlite3",
        observed_utc="2026-05-01T10:00:00Z",
    )

    out_df = build_product_db_operator_view(root=tmp_path, asof_utc="2026-04-17T12:00:00Z")

    assert sorted(out_df["seller_sku"].tolist()) == ["SKU-SQL-1", "SKU-SQL-2"]
    health_path = tmp_path / get_o_output_contract("product_db_source_health").rel_path
    health_df = pd.read_csv(health_path, dtype=str).fillna("")
    assert "sql_product_db_products present" in health_df.iloc[0]["notes"]


def test_o030_reports_duplicate_product_db_source_headers_before_view_masks_them(tmp_path: Path) -> None:
    product_path = tmp_path / "out" / "product_db_preview.csv"
    product_path.parent.mkdir(parents=True, exist_ok=True)
    product_path.write_text(
        "seller_sku,asin,last_updated_A003,last_updated_A003,supplier_code,supplier_name,supplier_pack_size,moq,supplier_catalog_price,last_purchase_price,sale_status,vat_rate\n"
        "SKU-DUP,ASIN-DUP,2026-04-17T10:00:00Z,2026-04-17T11:00:00Z,SUP, Supplier,1,1,2.00,2.00,active,20\n",
        encoding="utf-8",
    )

    out_df = build_product_db_operator_view(root=tmp_path, asof_utc="2026-04-17T12:00:00Z")

    assert len(out_df.index) == 1
    health_path = tmp_path / get_o_output_contract("product_db_source_health").rel_path
    health_df = pd.read_csv(health_path, dtype=str).fillna("")
    unique_header = health_df[health_df["check"] == "product_db_unique_headers"].iloc[0]
    assert unique_header["status"] == "fail"
    assert "last_updated_A003" in unique_header["notes"]
