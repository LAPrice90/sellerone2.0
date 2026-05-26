from __future__ import annotations

import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.O.O002_build_restock_recommendations import build_restock_recommendations
from scripts.flows.O.O001_build_restock_source_view import build_restock_source_view
from scripts.flows.O._contract_io import write_o_contract_df


FIXTURE_DIR = ROOT / "tests" / "fixtures" / "o_phase1"


def _apply_fresh_net_fee_defaults(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in (
        "market_price_ex_vat_gbp",
        "market_price_vat_rate_pct",
        "current_token_cost_gbp",
        "break_even_price_gbp",
        "net_fee_drag_per_unit_gbp",
        "net_fee_model_status",
        "net_fee_model_asof",
        "net_fee_model_age_hours",
        "net_fee_model_source",
        "net_fee_model_notes",
    ):
        if col not in out.columns:
            out[col] = ""
    for idx, row in out.iterrows():
        market = str(row.get("market_price_gbp", "") or "").strip()
        current_cost = str(row.get("expected_sell_pack_cost_gbp", "") or "").strip()
        if current_cost == "":
            current_cost = str(row.get("current_supplier_buy_cost_gbp", "") or "").strip()
        refund = str(row.get("expected_refund_cost_per_unit_gbp", "") or "").strip() or "0"
        if str(row.get("market_price_ex_vat_gbp", "") or "").strip() == "":
            out.at[idx, "market_price_ex_vat_gbp"] = market
        if str(row.get("market_price_vat_rate_pct", "") or "").strip() == "":
            out.at[idx, "market_price_vat_rate_pct"] = "0"
        if str(row.get("current_token_cost_gbp", "") or "").strip() == "":
            out.at[idx, "current_token_cost_gbp"] = current_cost
        if str(row.get("break_even_price_gbp", "") or "").strip() == "":
            try:
                out.at[idx, "break_even_price_gbp"] = str(float(current_cost) + float(refund))
            except ValueError:
                out.at[idx, "break_even_price_gbp"] = current_cost
        if str(row.get("net_fee_drag_per_unit_gbp", "") or "").strip() == "":
            out.at[idx, "net_fee_drag_per_unit_gbp"] = "0"
        if str(row.get("net_fee_model_status", "") or "").strip() == "":
            out.at[idx, "net_fee_model_status"] = "fresh"
        if str(row.get("net_fee_model_asof", "") or "").strip() == "":
            out.at[idx, "net_fee_model_asof"] = str(row.get("source_performance_asof", "") or "").strip() or "2026-04-03"
        if str(row.get("net_fee_model_age_hours", "") or "").strip() == "":
            out.at[idx, "net_fee_model_age_hours"] = "10"
        if str(row.get("net_fee_model_source", "") or "").strip() == "":
            out.at[idx, "net_fee_model_source"] = "sku_performance_summary"
        if str(row.get("net_fee_model_notes", "") or "").strip() == "":
            out.at[idx, "net_fee_model_notes"] = "fresh"
    return out


def _write_source_fixture(tmp_root: Path) -> None:
    source_path = tmp_root / "out" / "systems" / "O" / "live"
    source_path.mkdir(parents=True, exist_ok=True)
    src = pd.read_csv(FIXTURE_DIR / "restock_source_view_for_o002.csv", dtype=str).fillna("")
    _apply_fresh_net_fee_defaults(src).to_csv(source_path / "restock_source_view.csv", index=False)


def test_o002_applies_roi_bands_caps_rounding_and_hooks(tmp_path: Path) -> None:
    tmp_root = tmp_path
    _write_source_fixture(tmp_root)

    out_df = build_restock_recommendations(
        root=tmp_root,
        now_utc=datetime(2026, 4, 3, 11, 0, 0, tzinfo=timezone.utc),
    )
    by_sku = out_df.set_index("seller_sku")

    assert by_sku.loc["SKU-FULL", "recommendation_status"] == "full_restock"
    assert by_sku.loc["SKU-TEST", "recommendation_status"] == "test_restock"
    assert by_sku.loc["SKU-WAIT", "recommendation_status"] == "wait"

    cap = by_sku.loc["SKU-CAP"]
    assert cap["recommendation_status"] == "test_restock"
    assert cap["recommended_qty_raw"] == "7"
    assert cap["recommended_qty_rounded"] == "10"
    assert "TEST_SPEND_CAP_APPLIED" in cap["reason_codes"]

    rounded = by_sku.loc["SKU-ROUND"]
    assert rounded["recommendation_status"] == "full_restock"
    assert rounded["recommended_qty_raw"] == "31"
    assert rounded["recommended_qty_rounded"] == "36"

    stale = by_sku.loc["SKU-STALE"]
    assert stale["recommendation_status"] == "test_restock"
    assert "STALE_OUT_OF_STOCK_DOWNGRADE" in stale["reason_codes"]

    bulk = by_sku.loc["SKU-BULK"]
    assert bulk["recommendation_status"] == "full_restock"
    assert bulk["target_days_cover"] == "90"
    assert "BULK_LONG_LEAD_REVIEW" in bulk["reason_codes"]


def test_o002_preserves_title_and_main_image_from_source_view(tmp_path: Path) -> None:
    source_path = tmp_path / "out" / "systems" / "O" / "live"
    source_path.mkdir(parents=True, exist_ok=True)
    pd = __import__("pandas")
    src = pd.DataFrame(
        [
            {
                "asof_utc": "2026-04-04T10:00:00Z",
                "seller_sku": "SKU-IMG",
                "asin": "ASIN-IMG",
                "title": "Image Carry Product",
                "main_image": "https://example.com/image-carry.jpg",
                "supplier_code": "SUP-I",
                "supplier_name": "Image Supplier",
                "sale_status": "active",
                "sale_status_normalized": "active",
                "available_now": "0",
                "total_quantity_now": "0",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_7d": "1.0",
                "velocity_30d": "1.0",
                "velocity_90d": "1.0",
                "current_supplier_buy_cost_gbp": "2.00",
                "current_supplier_cost_source": "supplier_catalog_price",
                "market_price_gbp": "3.00",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "expected_refund_cost_per_unit_gbp": "0.10",
                "supplier_pack_size": "1",
                "moq": "1",
                "lead_time_days": "7",
                "bulk_long_lead_flag": "0",
                "out_of_stock_days": "0",
                "source_notes": "",
                "snooze_until_utc": "",
                "cost_mode": "live",
            }
        ]
    )
    _apply_fresh_net_fee_defaults(src).to_csv(source_path / "restock_source_view.csv", index=False)

    out_df = build_restock_recommendations(
        root=tmp_path,
        now_utc=datetime(2026, 4, 4, 10, 0, 0, tzinfo=timezone.utc),
    )
    row = out_df.loc[out_df["seller_sku"] == "SKU-IMG"].iloc[0]
    assert row["title"] == "Image Carry Product"
    assert row["main_image"] == "https://example.com/image-carry.jpg"


def test_o002_status_changes_when_velocity_30d_is_present_from_o001_fix(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "product_db_preview.csv").write_text(
        "seller_sku,asin,supplier_code,supplier_name,supplier_pack_size,moq,supplier_catalog_price,last_purchase_price,sale_status,vat_rate\n"
        "SKU-PIPE,ASINPIPE,SUP-A,Alpha,1,1,5.0,4.8,active,20\n",
        encoding="utf-8",
    )
    (out_dir / "inventory_summaries.csv").write_text(
        "seller_sku,asin,total_quantity,available,inbound_working,inbound_shipped,inbound_receiving,last_updated_time\n"
        "SKU-PIPE,ASINPIPE,2,0,0,0,0,2026-04-03T09:00:00Z\n",
        encoding="utf-8",
    )
    (out_dir / "sku_sales_velocity.csv").write_text(
        "sku,window_days,velocity_units_per_day,v7,v30,v90,available,total_quantity,asof_date\n"
        "SKU-PIPE,7,2.0,2.0,,,0,2,2026-04-03\n"
        "SKU-PIPE,30,1.0,,1.0,,0,2,2026-04-03\n"
        "SKU-PIPE,90,0.9,,,0.9,0,2,2026-04-03\n",
        encoding="utf-8",
    )
    (out_dir / "sku_performance_summary.csv").write_text(
        "sku,expected_refund_cost_per_unit_gbp,roi_at_our_price_pct,roi_at_buy_box_price_pct,break_even_price_gbp,current_token_cost_gbp,asof_date\n"
        "SKU-PIPE,0.0,80,85,6.0,5.0,2026-04-03\n",
        encoding="utf-8",
    )
    (out_dir / "listing_offer_snapshot_latest.csv").write_text(
        "timestamp_utc,asof_date,sku,asin,our_price,buy_box_price,buy_box_present_flag,lowest_fba_price\n"
        "2026-04-03T09:00:00Z,2026-04-03,SKU-PIPE,ASINPIPE,10.0,10.0,1,9.9\n",
        encoding="utf-8",
    )
    (out_dir / "order_master.csv").write_text(
        "Date,Order ID,country_code,SKU,Quantity Ordered,currency_code,Price_ExVAT,COGS_ExVAT,FBA_Fee_ExVAT\n",
        encoding="utf-8",
    )

    build_restock_source_view(root=tmp_path, asof_utc="2026-04-03T11:00:00Z")
    rec_df = build_restock_recommendations(
        root=tmp_path,
        now_utc=datetime(2026, 4, 3, 11, 0, 0, tzinfo=timezone.utc),
    )
    row = rec_df.loc[rec_df["seller_sku"] == "SKU-PIPE"].iloc[0]
    assert row["recommendation_status"] == "full_restock"


def test_o002_missing_cost_with_market_is_classified_as_cost_block(tmp_path: Path) -> None:
    source_path = tmp_path / "out" / "systems" / "O" / "live"
    source_path.mkdir(parents=True, exist_ok=True)
    pd = __import__("pandas")
    src = pd.DataFrame(
        [
            {
                "asof_utc": "2026-04-03T11:00:00Z",
                "seller_sku": "SKU-NOCOST",
                "asin": "ASIN-NOCOST",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "sale_status": "active",
                "sale_status_normalized": "active",
                "available_now": "0",
                "total_quantity_now": "0",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_7d": "1.0",
                "velocity_30d": "1.0",
                "velocity_90d": "1.0",
                "current_supplier_buy_cost_gbp": "",
                "current_supplier_cost_source": "missing_cost",
                "current_cost_source": "missing_cost",
                "current_cost_confidence": "none",
                "current_cost_value_gbp": "",
                "market_price_gbp": "10.0",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "expected_refund_cost_per_unit_gbp": "0.1",
                "supplier_pack_size": "1",
                "moq": "1",
                "lead_time_days": "7",
                "bulk_long_lead_flag": "0",
                "out_of_stock_days": "0",
                "source_notes": "",
                "snooze_until_utc": "",
            }
        ]
    )
    _apply_fresh_net_fee_defaults(src).to_csv(source_path / "restock_source_view.csv", index=False)

    out_df = build_restock_recommendations(
        root=tmp_path,
        now_utc=datetime(2026, 4, 3, 11, 0, 0, tzinfo=timezone.utc),
    )
    row = out_df.loc[out_df["seller_sku"] == "SKU-NOCOST"].iloc[0]
    assert row["recommendation_status"] == "wait"
    assert "BLOCKED_MISSING_COST_INPUT" in row["reason_codes"]
    assert "BLOCKED_MISSING_MARKET_PRICE_INPUT" not in row["reason_codes"]


def test_o002_produces_mixed_statuses_with_test_cost_mode_inputs(tmp_path: Path) -> None:
    source_path = tmp_path / "out" / "systems" / "O" / "live"
    source_path.mkdir(parents=True, exist_ok=True)
    pd = __import__("pandas")
    src = pd.DataFrame(
        [
            {
                "asof_utc": "2026-04-03T11:00:00Z",
                "seller_sku": "SKU-TFULL",
                "asin": "ASIN-TFULL",
                "supplier_code": "SUP-T1",
                "supplier_name": "Test Supplier One",
                "sale_status": "active",
                "sale_status_normalized": "active",
                "available_now": "0",
                "total_quantity_now": "0",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_7d": "1.0",
                "velocity_30d": "1.0",
                "velocity_90d": "1.0",
                "current_supplier_buy_cost_gbp": "8",
                "current_supplier_cost_source": "supplier_cost_snapshot_test",
                "market_price_gbp": "12.0",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "expected_refund_cost_per_unit_gbp": "0",
                "supplier_pack_size": "1",
                "moq": "1",
                "lead_time_days": "7",
                "bulk_long_lead_flag": "0",
                "out_of_stock_days": "0",
                "source_notes": "TEST_COST_MODE_ACTIVE|TEST_COST_SOURCE_APPLIED",
                "snooze_until_utc": "",
                "cost_mode": "test",
            },
            {
                "asof_utc": "2026-04-03T11:00:00Z",
                "seller_sku": "SKU-TTEST",
                "asin": "ASIN-TTEST",
                "supplier_code": "SUP-T2",
                "supplier_name": "Test Supplier Two",
                "sale_status": "active",
                "sale_status_normalized": "active",
                "available_now": "0",
                "total_quantity_now": "0",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_7d": "1.0",
                "velocity_30d": "1.0",
                "velocity_90d": "1.0",
                "current_supplier_buy_cost_gbp": "10",
                "current_supplier_cost_source": "supplier_cost_snapshot_test",
                "market_price_gbp": "11.2",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "expected_refund_cost_per_unit_gbp": "0",
                "supplier_pack_size": "5",
                "moq": "5",
                "lead_time_days": "7",
                "bulk_long_lead_flag": "0",
                "out_of_stock_days": "0",
                "source_notes": "TEST_COST_MODE_ACTIVE|TEST_COST_SOURCE_APPLIED",
                "snooze_until_utc": "",
                "cost_mode": "test",
            },
            {
                "asof_utc": "2026-04-03T11:00:00Z",
                "seller_sku": "SKU-TWAIT",
                "asin": "ASIN-TWAIT",
                "supplier_code": "SUP-T3",
                "supplier_name": "Test Supplier Three",
                "sale_status": "active",
                "sale_status_normalized": "active",
                "available_now": "0",
                "total_quantity_now": "0",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_7d": "1.0",
                "velocity_30d": "1.0",
                "velocity_90d": "1.0",
                "current_supplier_buy_cost_gbp": "20",
                "current_supplier_cost_source": "supplier_cost_snapshot_test",
                "market_price_gbp": "20.5",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "expected_refund_cost_per_unit_gbp": "0.7",
                "supplier_pack_size": "1",
                "moq": "1",
                "lead_time_days": "7",
                "bulk_long_lead_flag": "0",
                "out_of_stock_days": "0",
                "source_notes": "TEST_COST_MODE_ACTIVE|TEST_COST_SOURCE_APPLIED",
                "snooze_until_utc": "",
                "cost_mode": "test",
            },
        ]
    )
    _apply_fresh_net_fee_defaults(src).to_csv(source_path / "restock_source_view.csv", index=False)

    out_df = build_restock_recommendations(
        root=tmp_path,
        now_utc=datetime(2026, 4, 3, 11, 0, 0, tzinfo=timezone.utc),
    )
    by_sku = out_df.set_index("seller_sku")

    assert by_sku.loc["SKU-TFULL", "recommendation_status"] == "full_restock"
    assert by_sku.loc["SKU-TTEST", "recommendation_status"] == "test_restock"
    assert by_sku.loc["SKU-TWAIT", "recommendation_status"] == "wait"
    assert set(out_df["cost_mode"]) == {"test"}
    assert set(out_df["recommendation_basis"]) == {"test_cost_snapshot"}


def test_o002_carries_supplier_cost_confirmation_and_max_purchase_prices(tmp_path: Path) -> None:
    write_o_contract_df(
        tmp_path,
        "restock_source_view",
        _apply_fresh_net_fee_defaults(
            pd.DataFrame(
            [
                {
                    "asof_utc": "2026-05-19T12:10:00Z",
                    "seller_sku": "SKU-CHECK",
                    "asin": "ASIN-CHECK",
                    "supplier_code": "SUP-A",
                    "supplier_name": "Alpha",
                    "sale_status": "active",
                    "sale_status_normalized": "active",
                    "available_now": "0",
                    "total_quantity_now": "0",
                    "amazon_inbound_working": "0",
                    "amazon_inbound_shipped": "0",
                    "amazon_inbound_receiving": "0",
                    "velocity_7d": "1.0",
                    "velocity_30d": "1.0",
                    "velocity_90d": "1.0",
                    "current_supplier_buy_cost_gbp": "2.25",
                    "current_supplier_cost_source": "supplier_buy_cost_truth",
                    "market_price_gbp": "3.00",
                    "market_price_basis_used": "BUY_BOX_PRICE",
                    "expected_refund_cost_per_unit_gbp": "0.10",
                    "supplier_pack_size": "1",
                    "moq": "1",
                    "lead_time_days": "7",
                    "bulk_long_lead_flag": "0",
                    "out_of_stock_days": "0",
                    "source_notes": "SUPPLIER_BUY_COST_TRUTH_APPLIED|SUPPLIER_COST_USER_CHECK_REQUIRED",
                    "snooze_until_utc": "",
                    "cost_mode": "live",
                    "user_price_check_required": "1",
                    "supplier_cost_review_reason": "discount_assumption_needs_confirmation",
                    "expected_next_unit_cost_gbp": "2.25",
                    "price_list_unit_cost_gbp": "2.50",
                    "purchase_reference_list_cost_gbp": "2.00",
                    "actual_paid_unit_cost_gbp": "1.80",
                },
                {
                    "asof_utc": "2026-05-19T12:10:00Z",
                    "seller_sku": "SKU-TOOHIGH",
                    "asin": "ASIN-TOOHIGH",
                    "supplier_code": "SUP-A",
                    "supplier_name": "Alpha",
                    "sale_status": "active",
                    "sale_status_normalized": "active",
                    "available_now": "0",
                    "total_quantity_now": "0",
                    "amazon_inbound_working": "0",
                    "amazon_inbound_shipped": "0",
                    "amazon_inbound_receiving": "0",
                    "velocity_7d": "1.0",
                    "velocity_30d": "1.0",
                    "velocity_90d": "1.0",
                    "current_supplier_buy_cost_gbp": "2.20",
                    "current_supplier_cost_source": "supplier_buy_cost_truth",
                    "market_price_gbp": "2.50",
                    "market_price_basis_used": "BUY_BOX_PRICE",
                    "expected_refund_cost_per_unit_gbp": "0.25",
                    "supplier_pack_size": "1",
                    "moq": "1",
                    "lead_time_days": "7",
                    "bulk_long_lead_flag": "0",
                    "out_of_stock_days": "0",
                    "source_notes": "SUPPLIER_BUY_COST_TRUTH_APPLIED",
                    "snooze_until_utc": "",
                    "cost_mode": "live",
                    "user_price_check_required": "0",
                    "expected_next_unit_cost_gbp": "2.20",
                    "price_list_unit_cost_gbp": "2.20",
                },
            ]
            )
        ),
    )

    out_df = build_restock_recommendations(
        root=tmp_path,
        now_utc=datetime(2026, 5, 19, 12, 20, 0, tzinfo=timezone.utc),
    )
    by_sku = out_df.set_index("seller_sku")

    check = by_sku.loc["SKU-CHECK"]
    assert check["recommendation_status"] == "full_restock"
    assert "SUPPLIER_COST_USER_CONFIRMATION_REQUIRED" in check["reason_codes"]
    assert check["user_price_check_required"] == "1"
    assert check["max_break_even_purchase_price_gbp"] == "2.9"
    assert check["max_target_roi_purchase_price_gbp"] == "2.636364"
    assert check["purchase_price_safety_status"] == "within_target_roi_max"

    too_high = by_sku.loc["SKU-TOOHIGH"]
    assert too_high["recommendation_status"] == "wait"
    assert "EXPECTED_COST_ABOVE_TARGET_ROI_MAX_PURCHASE_PRICE" in too_high["reason_codes"]
    assert too_high["max_break_even_purchase_price_gbp"] == "2.25"
    assert too_high["max_target_roi_purchase_price_gbp"] == "2.045455"
    assert too_high["purchase_price_safety_status"] == "above_target_roi_max"


def test_o002_uses_net_fee_truth_instead_of_gross_roi_for_buy_decision(tmp_path: Path) -> None:
    write_o_contract_df(
        tmp_path,
        "restock_source_view",
        pd.DataFrame(
            [
                {
                    "asof_utc": "2026-05-19T12:10:00Z",
                    "seller_sku": "SKU-NET-LOSS",
                    "asin": "ASIN-NET-LOSS",
                    "supplier_code": "SUP-A",
                    "supplier_name": "Alpha",
                    "sale_status": "active",
                    "sale_status_normalized": "active",
                    "available_now": "0",
                    "total_quantity_now": "0",
                    "amazon_inbound_working": "0",
                    "amazon_inbound_shipped": "0",
                    "amazon_inbound_receiving": "0",
                    "velocity_7d": "1",
                    "velocity_30d": "1",
                    "velocity_90d": "1",
                    "current_supplier_buy_cost_gbp": "0.63",
                    "current_supplier_cost_source": "supplier_buy_cost_truth",
                    "market_price_gbp": "2.50",
                    "market_price_basis_used": "BUY_BOX_PRICE",
                    "market_price_ex_vat_gbp": "2.083333",
                    "market_price_vat_rate_pct": "20",
                    "expected_refund_cost_per_unit_gbp": "0",
                    "current_token_cost_gbp": "0.63",
                    "break_even_price_gbp": "2.21",
                    "net_fee_drag_per_unit_gbp": "1.58",
                    "net_fee_model_status": "fresh",
                    "net_fee_model_asof": "2026-05-19",
                    "net_fee_model_age_hours": "12",
                    "net_fee_model_source": "sku_performance_summary",
                    "net_fee_model_notes": "fresh",
                    "supplier_pack_size": "1",
                    "moq": "1",
                    "lead_time_days": "7",
                    "bulk_long_lead_flag": "0",
                    "out_of_stock_days": "0",
                    "snooze_until_utc": "",
                    "cost_mode": "live",
                }
            ]
        ),
    )

    out_df = build_restock_recommendations(
        root=tmp_path,
        now_utc=datetime(2026, 5, 19, 12, 20, 0, tzinfo=timezone.utc),
    )
    row = out_df.iloc[0]

    assert row["recommendation_status"] == "wait"
    assert row["gross_forward_roi_pct"] == "296.825397"
    assert row["forward_roi_pct"] == "-20.105873"
    assert row["forward_profit_per_unit_gbp"] == "-0.126667"
    assert row["max_break_even_purchase_price_gbp"] == "0.503333"
    assert row["purchase_price_safety_status"] == "above_break_even_max"
    assert "COST_ABOVE_BREAK_EVEN_MAX_PURCHASE_PRICE" in row["reason_codes"]


def test_o002_blocks_buy_when_net_fee_model_is_stale(tmp_path: Path) -> None:
    row = {
        "asof_utc": "2026-05-19T12:10:00Z",
        "seller_sku": "SKU-STALE-FEE",
        "asin": "ASIN-STALE-FEE",
        "supplier_code": "SUP-A",
        "supplier_name": "Alpha",
        "sale_status": "active",
        "sale_status_normalized": "active",
        "available_now": "0",
        "total_quantity_now": "0",
        "amazon_inbound_working": "0",
        "amazon_inbound_shipped": "0",
        "amazon_inbound_receiving": "0",
        "velocity_7d": "1",
        "velocity_30d": "1",
        "velocity_90d": "1",
        "current_supplier_buy_cost_gbp": "1.00",
        "current_supplier_cost_source": "supplier_buy_cost_truth",
        "market_price_gbp": "8.00",
        "market_price_basis_used": "BUY_BOX_PRICE",
        "market_price_ex_vat_gbp": "6.666667",
        "market_price_vat_rate_pct": "20",
        "expected_refund_cost_per_unit_gbp": "0",
        "current_token_cost_gbp": "1.00",
        "break_even_price_gbp": "2.00",
        "net_fee_drag_per_unit_gbp": "1.00",
        "net_fee_model_status": "stale",
        "net_fee_model_asof": "2026-05-15",
        "net_fee_model_age_hours": "108",
        "net_fee_model_source": "sku_performance_summary",
        "net_fee_model_notes": "stale_model_asof",
        "supplier_pack_size": "1",
        "moq": "1",
        "lead_time_days": "7",
        "bulk_long_lead_flag": "0",
        "out_of_stock_days": "0",
        "snooze_until_utc": "",
        "cost_mode": "live",
    }
    write_o_contract_df(tmp_path, "restock_source_view", pd.DataFrame([row]))

    out_df = build_restock_recommendations(
        root=tmp_path,
        now_utc=datetime(2026, 5, 19, 12, 20, 0, tzinfo=timezone.utc),
    )
    rec = out_df.iloc[0]

    assert rec["recommendation_status"] == "wait"
    assert "BLOCKED_STALE_NET_FEE_INPUT" in rec["reason_codes"]
    assert rec["purchase_price_safety_status"] == "stale_net_fee_model"
    assert rec["confidence_note"] == "net_fee_model_blocked"


def test_o002_uses_expected_sell_pack_cost_for_profit_math(tmp_path: Path) -> None:
    write_o_contract_df(
        tmp_path,
        "restock_source_view",
        _apply_fresh_net_fee_defaults(
            pd.DataFrame(
            [
                {
                    "asof_utc": "2026-05-19T12:10:00Z",
                    "seller_sku": "6V-EEC1-2S9Z",
                    "asin": "ASIN-SIKA20",
                    "supplier_code": "SIKA",
                    "supplier_name": "Sika",
                    "sale_status": "active",
                    "sale_status_normalized": "active",
                    "available_now": "0",
                    "total_quantity_now": "0",
                    "amazon_inbound_working": "0",
                    "amazon_inbound_shipped": "0",
                    "amazon_inbound_receiving": "0",
                    "velocity_7d": "10",
                    "velocity_30d": "10",
                    "velocity_90d": "10",
                    "current_supplier_buy_cost_gbp": "1.45",
                    "current_supplier_cost_source": "supplier_catalog_price",
                    "market_price_gbp": "9.00",
                    "market_price_basis_used": "BUY_BOX_PRICE",
                    "expected_refund_cost_per_unit_gbp": "0",
                    "supplier_pack_size": "1",
                    "moq": "1",
                    "lead_time_days": "7",
                    "bulk_long_lead_flag": "0",
                    "out_of_stock_days": "0",
                    "source_notes": "SUPPLIER_COST_CONVERTED_TO_SELL_PACK",
                    "snooze_until_utc": "",
                    "cost_mode": "live",
                    "components_per_sell_pack": "3",
                    "supplier_cost_basis": "component_unit",
                    "expected_sell_pack_cost_gbp": "4.35",
                    "expected_component_cost_gbp": "1.45",
                    "quantity_strategy": "preferred_carton_multiple",
                    "preferred_order_sell_packs": "250",
                    "preferred_order_components": "750",
                    "preferred_supplier_boxes": "30",
                    "supplier_box_components": "25",
                    "hazmat_group": "sika_glue",
                    "isolate_from_normal_po": "1",
                    "target_carton_weight_kg": "23",
                    "pack_profile_status": "confirmed",
                }
            ]
            )
        ),
    )

    out_df = build_restock_recommendations(
        root=tmp_path,
        now_utc=datetime(2026, 5, 19, 12, 20, 0, tzinfo=timezone.utc),
    )
    row = out_df.iloc[0]

    assert row["recommendation_status"] == "full_restock"
    assert row["current_supplier_buy_cost_gbp"] == "4.35"
    assert row["forward_profit_per_unit_gbp"] == "4.65"
    assert row["forward_roi_pct"] == "106.896552"
    assert row["max_target_roi_purchase_price_gbp"] == "8.181818"
    assert row["components_per_sell_pack"] == "3"
    assert row["expected_component_cost_gbp"] == "1.45"
    assert row["hazmat_group"] == "sika_glue"


def test_o002_blocks_buyable_recommendation_when_pack_profile_is_not_safe(tmp_path: Path) -> None:
    write_o_contract_df(
        tmp_path,
        "restock_source_view",
        _apply_fresh_net_fee_defaults(
            pd.DataFrame(
            [
                {
                    "asof_utc": "2026-05-19T12:10:00Z",
                    "seller_sku": "PE-G94Y-4PYO",
                    "asin": "ASIN-SIKA50-2PACK",
                    "supplier_code": "SIKA",
                    "supplier_name": "Sika",
                    "sale_status": "active",
                    "sale_status_normalized": "active",
                    "available_now": "0",
                    "total_quantity_now": "0",
                    "amazon_inbound_working": "0",
                    "amazon_inbound_shipped": "0",
                    "amazon_inbound_receiving": "0",
                    "velocity_7d": "10",
                    "velocity_30d": "10",
                    "velocity_90d": "10",
                    "current_supplier_buy_cost_gbp": "2.10",
                    "current_supplier_cost_source": "supplier_catalog_price",
                    "market_price_gbp": "12.00",
                    "market_price_basis_used": "BUY_BOX_PRICE",
                    "expected_refund_cost_per_unit_gbp": "0",
                    "supplier_pack_size": "1",
                    "moq": "1",
                    "lead_time_days": "7",
                    "bulk_long_lead_flag": "0",
                    "out_of_stock_days": "0",
                    "source_notes": "missing_pack_profile|special_order_profile_required",
                    "snooze_until_utc": "",
                    "cost_mode": "live",
                    "components_per_sell_pack": "1",
                    "supplier_cost_basis": "sell_pack",
                    "expected_sell_pack_cost_gbp": "2.10",
                    "expected_component_cost_gbp": "2.10",
                    "pack_profile_status": "missing_pack_profile",
                }
            ]
            )
        ),
    )

    out_df = build_restock_recommendations(
        root=tmp_path,
        now_utc=datetime(2026, 5, 19, 12, 20, 0, tzinfo=timezone.utc),
    )
    row = out_df.iloc[0]

    assert row["recommendation_status"] == "wait"
    assert row["recommended_qty_rounded"] == "0"
    assert "PACK_PROFILE_MISSING" in row["reason_codes"]
    assert "SPECIAL_ORDER_PROFILE_REQUIRED" in row["reason_codes"]
    assert row["confidence_note"] == "pack_profile_blocked"


def test_o002_blocks_unconfirmed_and_invalid_pack_profiles(tmp_path: Path) -> None:
    base = {
        "asof_utc": "2026-05-19T12:10:00Z",
        "asin": "ASIN-PACK",
        "supplier_code": "SIKA",
        "supplier_name": "Sika",
        "sale_status": "active",
        "sale_status_normalized": "active",
        "available_now": "0",
        "total_quantity_now": "0",
        "amazon_inbound_working": "0",
        "amazon_inbound_shipped": "0",
        "amazon_inbound_receiving": "0",
        "velocity_7d": "10",
        "velocity_30d": "10",
        "velocity_90d": "10",
        "current_supplier_buy_cost_gbp": "4.35",
        "current_supplier_cost_source": "supplier_catalog_price_converted_to_sell_pack",
        "market_price_gbp": "12.00",
        "market_price_basis_used": "BUY_BOX_PRICE",
        "expected_refund_cost_per_unit_gbp": "0",
        "supplier_pack_size": "1",
        "moq": "1",
        "lead_time_days": "7",
        "bulk_long_lead_flag": "0",
        "out_of_stock_days": "0",
        "snooze_until_utc": "",
        "cost_mode": "live",
        "components_per_sell_pack": "3",
        "supplier_cost_basis": "component_unit",
        "expected_sell_pack_cost_gbp": "4.35",
        "expected_component_cost_gbp": "1.45",
    }
    rows = [
        {
            **base,
            "seller_sku": "SKU-PENDING-PACK",
            "source_notes": "unconfirmed_pack_profile",
            "pack_profile_status": "pending",
        },
        {
            **base,
            "seller_sku": "SKU-INVALID-PACK",
            "source_notes": "invalid_component_conversion",
            "pack_profile_status": "invalid",
        },
    ]
    write_o_contract_df(tmp_path, "restock_source_view", _apply_fresh_net_fee_defaults(pd.DataFrame(rows)))

    out_df = build_restock_recommendations(
        root=tmp_path,
        now_utc=datetime(2026, 5, 19, 12, 20, 0, tzinfo=timezone.utc),
    )
    by_sku = out_df.set_index("seller_sku")

    pending = by_sku.loc["SKU-PENDING-PACK"]
    assert pending["recommendation_status"] == "wait"
    assert "PACK_PROFILE_UNCONFIRMED" in pending["reason_codes"]
    assert pending["confidence_note"] == "pack_profile_blocked"

    invalid = by_sku.loc["SKU-INVALID-PACK"]
    assert invalid["recommendation_status"] == "wait"
    assert "PACK_PROFILE_INVALID" in invalid["reason_codes"]
    assert invalid["confidence_note"] == "pack_profile_blocked"
