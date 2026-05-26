from __future__ import annotations

import csv
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.O.O020_build_reorder_input_coverage_report import build_reorder_input_coverage_report
from scripts.flows.O._schemas import get_o_output_contract
from scripts.flows.O._source_contracts import get_phase1_source_contracts


def _write_contract_rows(tmp_path: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
    contract = get_o_output_contract(contract_name)
    path = tmp_path / contract.rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = [*contract.required_columns, *contract.optional_columns]
    normalized: list[dict[str, str]] = []
    for row in rows:
        work = dict(row)
        if contract_name in {"restock_source_view", "restock_recommendations_live", "restock_review_queue"}:
            market = (
                str(work.get("market_price_gbp", "") or "").strip()
                or str(work.get("suggested_market_price_gbp", "") or "").strip()
            )
            cost = (
                str(work.get("current_supplier_buy_cost_gbp", "") or "").strip()
                or str(work.get("suggested_unit_cost_gbp", "") or "").strip()
            )
            refund = str(work.get("expected_refund_cost_per_unit_gbp", "") or "").strip() or "0"
            work.setdefault("market_price_ex_vat_gbp", market)
            work.setdefault("market_price_vat_rate_pct", "0")
            work.setdefault("current_token_cost_gbp", cost)
            if "break_even_price_gbp" not in work:
                try:
                    work["break_even_price_gbp"] = str(float(cost) + float(refund))
                except ValueError:
                    work["break_even_price_gbp"] = cost
            work.setdefault("net_fee_drag_per_unit_gbp", "0")
            work.setdefault("net_fee_model_status", "fresh")
            work.setdefault("net_fee_model_asof", "2026-05-19")
            work.setdefault("net_fee_model_age_hours", "12")
            work.setdefault("net_fee_model_source", "sku_performance_summary")
            work.setdefault("net_fee_model_notes", "fresh")
            work.setdefault("gross_forward_roi_pct", str(work.get("forward_roi_pct", "") or work.get("expected_forward_roi_pct", "") or ""))
            work.setdefault(
                "gross_forward_profit_per_unit_gbp",
                str(work.get("forward_profit_per_unit_gbp", "") or work.get("expected_forward_profit_per_unit_gbp", "") or ""),
            )
        normalized.append({col: str(work.get(col, "") or "") for col in cols})
    pd.DataFrame(normalized, columns=cols).to_csv(path, index=False)


def _write_upstream_rows(tmp_path: Path) -> None:
    contracts = get_phase1_source_contracts()

    product_path = tmp_path / contracts["product_db_preview"].source_path
    product_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "seller_sku": "SKU-READY",
                "asin": "ASIN-READY",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "supplier_pack_size": "1",
                "moq": "1",
                "supplier_catalog_price": "2.20",
                "last_purchase_price": "2.30",
                "sale_status": "active",
                "vat_rate": "20",
                "title": "Ready Product",
                "main_image": "https://example.com/ready.jpg",
            },
            {
                "seller_sku": "SKU-NOCOST",
                "asin": "ASIN-NOCOST",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "supplier_pack_size": "1",
                "moq": "1",
                "supplier_catalog_price": "",
                "last_purchase_price": "",
                "sale_status": "active",
                "vat_rate": "20",
                "title": "No Cost Product",
                "main_image": "https://example.com/nocost.jpg",
            },
            {
                "seller_sku": "SKU-WAIT",
                "asin": "ASIN-WAIT",
                "supplier_code": "SUP-B",
                "supplier_name": "Beta",
                "supplier_pack_size": "1",
                "moq": "1",
                "supplier_catalog_price": "1.00",
                "last_purchase_price": "1.10",
                "sale_status": "inactive",
                "vat_rate": "20",
                "title": "Wait Product",
                "main_image": "https://example.com/wait.jpg",
            },
        ]
    ).to_csv(product_path, index=False)

    velocity_path = tmp_path / contracts["sku_sales_velocity"].source_path
    pd.DataFrame(
        [
            {"sku": "SKU-READY", "v7": "1", "v30": "2", "v90": "2", "available": "10", "total_quantity": "10", "asof_date": "2026-04-04"},
            {"sku": "SKU-NOCOST", "v7": "1", "v30": "1", "v90": "1", "available": "5", "total_quantity": "5", "asof_date": "2026-04-04"},
            {"sku": "SKU-WAIT", "v7": "0", "v30": "0", "v90": "0", "available": "0", "total_quantity": "0", "asof_date": "2026-04-04"},
        ]
    ).to_csv(velocity_path, index=False)

    perf_path = tmp_path / contracts["sku_performance_summary"].source_path
    pd.DataFrame(
        [
            {
                "sku": "SKU-READY",
                "expected_refund_cost_per_unit_gbp": "0.10",
                "roi_at_our_price_pct": "20",
                "roi_at_buy_box_price_pct": "18",
                "break_even_price_gbp": "3.0",
                "current_token_cost_gbp": "2.2",
                "asof_date": "2026-04-04",
            }
        ]
    ).to_csv(perf_path, index=False)

    offer_path = tmp_path / contracts["listing_offer_snapshot_latest"].source_path
    pd.DataFrame(
        [
            {
                "timestamp_utc": "2026-04-04T00:00:00Z",
                "asof_date": "2026-04-04",
                "sku": "SKU-READY",
                "asin": "ASIN-READY",
                "our_price": "4.80",
                "buy_box_price": "4.90",
                "buy_box_present_flag": "1",
                "lowest_fba_price": "4.85",
            }
        ]
    ).to_csv(offer_path, index=False)


def test_o020_builds_row_and_supplier_coverage_outputs(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_source_view",
        [
            {
                "asof_utc": "2026-04-04T00:00:00Z",
                "seller_sku": "SKU-READY",
                "asin": "ASIN-READY",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "sale_status": "active",
                "available_now": "8",
                "total_quantity_now": "8",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_7d": "1",
                "velocity_30d": "2",
                "velocity_90d": "2",
                "current_supplier_buy_cost_gbp": "2.20",
                "current_supplier_cost_source": "supplier_catalog_price",
                "market_price_gbp": "4.90",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "expected_refund_cost_per_unit_gbp": "0.10",
                "roi_at_market_price_pct": "18",
                "source_inventory_asof": "2026-04-04T00:00:00Z",
                "source_velocity_asof": "2026-04-04",
                "source_performance_asof": "2026-04-04",
                "title": "Ready Product",
                "main_image": "https://example.com/ready.jpg",
                "is_active_candidate": "1",
                "has_current_cost_input": "1",
                "has_current_market_price_input": "1",
                "has_demand_input": "1",
                "has_minimum_restock_inputs": "1",
                "coverage_block_reason": "ready_minimum_inputs",
                "cost_mode": "live",
            },
            {
                "asof_utc": "2026-04-04T00:00:00Z",
                "seller_sku": "SKU-NOCOST",
                "asin": "ASIN-NOCOST",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "sale_status": "active",
                "available_now": "5",
                "total_quantity_now": "5",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_7d": "1",
                "velocity_30d": "1",
                "velocity_90d": "1",
                "current_supplier_buy_cost_gbp": "",
                "current_supplier_cost_source": "missing_cost",
                "market_price_gbp": "3.60",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "expected_refund_cost_per_unit_gbp": "0.10",
                "roi_at_market_price_pct": "",
                "source_inventory_asof": "2026-04-04T00:00:00Z",
                "source_velocity_asof": "2026-04-04",
                "source_performance_asof": "2026-04-04",
                "title": "No Cost Product",
                "main_image": "https://example.com/nocost.jpg",
                "is_active_candidate": "1",
                "has_current_cost_input": "0",
                "has_current_market_price_input": "1",
                "has_demand_input": "1",
                "has_minimum_restock_inputs": "0",
                "coverage_block_reason": "missing_cost_only",
                "cost_mode": "live",
            },
            {
                "asof_utc": "2026-04-04T00:00:00Z",
                "seller_sku": "SKU-WAIT",
                "asin": "ASIN-WAIT",
                "supplier_code": "SUP-B",
                "supplier_name": "Beta",
                "sale_status": "inactive",
                "available_now": "0",
                "total_quantity_now": "0",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_7d": "0",
                "velocity_30d": "0",
                "velocity_90d": "0",
                "current_supplier_buy_cost_gbp": "1.00",
                "current_supplier_cost_source": "supplier_catalog_price",
                "market_price_gbp": "1.60",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "expected_refund_cost_per_unit_gbp": "0.10",
                "roi_at_market_price_pct": "0",
                "source_inventory_asof": "2026-04-04T00:00:00Z",
                "source_velocity_asof": "2026-04-04",
                "source_performance_asof": "2026-04-04",
                "title": "Wait Product",
                "main_image": "https://example.com/wait.jpg",
                "is_active_candidate": "0",
                "has_current_cost_input": "1",
                "has_current_market_price_input": "1",
                "has_demand_input": "0",
                "has_minimum_restock_inputs": "0",
                "coverage_block_reason": "inactive_status",
                "cost_mode": "live",
            },
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_recommendations_live",
        [
            {
                "asof_utc": "2026-04-04T00:00:00Z",
                "seller_sku": "SKU-READY",
                "asin": "ASIN-READY",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "recommendation_status": "full_restock",
                "reason_codes": "ROI_OK",
                "recommended_qty_raw": "20",
                "recommended_qty_rounded": "20",
                "target_days_cover": "30",
                "days_cover_available_only": "4",
                "days_cover_total_pipeline": "4",
                "current_supplier_buy_cost_gbp": "2.20",
                "current_supplier_cost_source": "supplier_catalog_price",
                "market_price_gbp": "4.90",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "forward_roi_pct": "18",
                "forward_profit_per_unit_gbp": "1.2",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            },
            {
                "asof_utc": "2026-04-04T00:00:00Z",
                "seller_sku": "SKU-NOCOST",
                "asin": "ASIN-NOCOST",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "recommendation_status": "test_restock",
                "reason_codes": "BLOCKED_MISSING_COST_INPUT",
                "recommended_qty_raw": "10",
                "recommended_qty_rounded": "10",
                "target_days_cover": "30",
                "days_cover_available_only": "5",
                "days_cover_total_pipeline": "5",
                "current_supplier_buy_cost_gbp": "",
                "current_supplier_cost_source": "missing_cost",
                "market_price_gbp": "3.60",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "forward_roi_pct": "",
                "forward_profit_per_unit_gbp": "",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            },
            {
                "asof_utc": "2026-04-04T00:00:00Z",
                "seller_sku": "SKU-WAIT",
                "asin": "ASIN-WAIT",
                "supplier_code": "SUP-B",
                "supplier_name": "Beta",
                "recommendation_status": "wait",
                "reason_codes": "SALE_STATUS_NOT_ACTIVE",
                "recommended_qty_raw": "0",
                "recommended_qty_rounded": "0",
                "target_days_cover": "30",
                "days_cover_available_only": "0",
                "days_cover_total_pipeline": "0",
                "current_supplier_buy_cost_gbp": "1.00",
                "current_supplier_cost_source": "supplier_catalog_price",
                "market_price_gbp": "1.60",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "forward_roi_pct": "0",
                "forward_profit_per_unit_gbp": "0",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            },
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_review_queue",
        [
            {
                "queue_utc": "2026-04-04T00:00:00Z",
                "seller_sku": "SKU-READY",
                "asin": "ASIN-READY",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "recommendation_status": "full_restock",
                "suggested_qty": "20",
                "suggested_unit_cost_gbp": "2.20",
                "suggested_market_price_gbp": "4.90",
                "expected_forward_roi_pct": "18",
                "expected_forward_profit_per_unit_gbp": "1.2",
                "days_cover_available_only": "4",
                "days_cover_total_pipeline": "4",
                "reason_codes": "ROI_OK",
                "queue_status": "needs_review",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                "title": "Ready Product",
                "main_image": "https://example.com/ready.jpg",
            },
            {
                "queue_utc": "2026-04-04T00:00:00Z",
                "seller_sku": "SKU-NOCOST",
                "asin": "ASIN-NOCOST",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "recommendation_status": "test_restock",
                "suggested_qty": "10",
                "suggested_unit_cost_gbp": "",
                "suggested_market_price_gbp": "3.60",
                "expected_forward_roi_pct": "",
                "expected_forward_profit_per_unit_gbp": "",
                "days_cover_available_only": "5",
                "days_cover_total_pipeline": "5",
                "reason_codes": "BLOCKED_MISSING_COST_INPUT",
                "queue_status": "needs_review",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                "title": "No Cost Product",
                "main_image": "https://example.com/nocost.jpg",
            },
            {
                "queue_utc": "2026-04-04T00:00:00Z",
                "seller_sku": "SKU-WAIT",
                "asin": "ASIN-WAIT",
                "supplier_code": "SUP-B",
                "supplier_name": "Beta",
                "recommendation_status": "wait",
                "suggested_qty": "0",
                "suggested_unit_cost_gbp": "1.00",
                "suggested_market_price_gbp": "1.60",
                "expected_forward_roi_pct": "0",
                "expected_forward_profit_per_unit_gbp": "0",
                "days_cover_available_only": "0",
                "days_cover_total_pipeline": "0",
                "reason_codes": "SALE_STATUS_NOT_ACTIVE",
                "queue_status": "snoozed",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                "title": "Wait Product",
                "main_image": "https://example.com/wait.jpg",
            },
        ],
    )
    _write_upstream_rows(tmp_path)

    detail_df, supplier_df, block_df = build_reorder_input_coverage_report(
        root=tmp_path,
        report_utc="2026-04-04T01:00:00Z",
    )

    assert len(detail_df) == 3
    ready_row = detail_df[detail_df["seller_sku"] == "SKU-READY"].iloc[0]
    no_cost_row = detail_df[detail_df["seller_sku"] == "SKU-NOCOST"].iloc[0]
    wait_row = detail_df[detail_df["seller_sku"] == "SKU-WAIT"].iloc[0]

    assert ready_row["action_ready_now"] == "1"
    assert "missing_cost_truth" in no_cost_row["block_reason_codes"]
    assert no_cost_row["action_ready_now"] == "0"
    assert "wait_or_non_action_suggestion" in wait_row["block_reason_codes"]
    assert "snoozed" in wait_row["block_reason_codes"]

    alpha_row = supplier_df[supplier_df["supplier_name"] == "Alpha"].iloc[0]
    assert alpha_row["rows_total"] == "2"
    assert alpha_row["rows_action_ready"] == "1"
    assert alpha_row["rows_missing_cost_truth"] == "1"

    missing_cost_reason = block_df[block_df["block_reason"] == "missing_cost_truth"].iloc[0]
    assert missing_cost_reason["rows_count"] == "1"

    report_path = tmp_path / get_o_output_contract("reorder_input_coverage_report").rel_path
    supplier_path = tmp_path / get_o_output_contract("reorder_input_coverage_by_supplier").rel_path
    block_path = tmp_path / get_o_output_contract("reorder_input_block_reasons").rel_path
    summary_path = tmp_path / "out" / "systems" / "O" / "live" / "reorder_input_readiness_summary.md"
    assert report_path.exists()
    assert supplier_path.exists()
    assert block_path.exists()
    assert summary_path.exists()


def test_o020_blocks_action_ready_when_supplier_cost_confirmation_is_required(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_source_view",
        [
            {
                "asof_utc": "2026-05-19T12:10:00Z",
                "seller_sku": "SKU-CHECK",
                "asin": "ASIN-CHECK",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "sale_status": "active",
                "available_now": "0",
                "total_quantity_now": "0",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_7d": "1",
                "velocity_30d": "1",
                "velocity_90d": "1",
                "current_supplier_buy_cost_gbp": "2.25",
                "current_supplier_cost_source": "supplier_buy_cost_truth",
                "market_price_gbp": "3.00",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "expected_refund_cost_per_unit_gbp": "0.10",
                "is_active_candidate": "1",
                "has_current_cost_input": "1",
                "has_current_market_price_input": "1",
                "has_demand_input": "1",
                "has_minimum_restock_inputs": "1",
                "coverage_block_reason": "ready_minimum_inputs",
                "cost_mode": "live",
                "user_price_check_required": "1",
                "supplier_cost_review_reason": "discount_assumption_needs_confirmation",
                "max_break_even_purchase_price_gbp": "2.9",
                "max_target_roi_purchase_price_gbp": "2.636364",
                "target_roi_pct": "10",
                "purchase_price_safety_status": "within_target_roi_max",
                "expected_next_unit_cost_gbp": "2.25",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_recommendations_live",
        [
            {
                "asof_utc": "2026-05-19T12:20:00Z",
                "seller_sku": "SKU-CHECK",
                "asin": "ASIN-CHECK",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "recommendation_status": "full_restock",
                "reason_codes": "SUPPLIER_COST_USER_CONFIRMATION_REQUIRED",
                "recommended_qty_raw": "30",
                "recommended_qty_rounded": "30",
                "target_days_cover": "30",
                "days_cover_available_only": "0",
                "days_cover_total_pipeline": "0",
                "current_supplier_buy_cost_gbp": "2.25",
                "current_supplier_cost_source": "supplier_buy_cost_truth",
                "market_price_gbp": "3.00",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "forward_roi_pct": "28.888889",
                "forward_profit_per_unit_gbp": "0.65",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                "user_price_check_required": "1",
                "supplier_cost_review_reason": "discount_assumption_needs_confirmation",
                "max_break_even_purchase_price_gbp": "2.9",
                "max_target_roi_purchase_price_gbp": "2.636364",
                "target_roi_pct": "10",
                "purchase_price_safety_status": "within_target_roi_max",
                "expected_next_unit_cost_gbp": "2.25",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_review_queue",
        [
            {
                "queue_utc": "2026-05-19T12:30:00Z",
                "seller_sku": "SKU-CHECK",
                "asin": "ASIN-CHECK",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "recommendation_status": "full_restock",
                "suggested_qty": "30",
                "suggested_unit_cost_gbp": "2.25",
                "suggested_market_price_gbp": "3.00",
                "expected_forward_roi_pct": "28.888889",
                "expected_forward_profit_per_unit_gbp": "0.65",
                "queue_status": "needs_review",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                "user_price_check_required": "1",
                "supplier_cost_review_reason": "discount_assumption_needs_confirmation",
                "max_break_even_purchase_price_gbp": "2.9",
                "max_target_roi_purchase_price_gbp": "2.636364",
                "target_roi_pct": "10",
                "purchase_price_safety_status": "within_target_roi_max",
                "expected_next_unit_cost_gbp": "2.25",
            }
        ],
    )

    detail_df, _supplier_df, block_df = build_reorder_input_coverage_report(
        root=tmp_path,
        report_utc="2026-05-19T12:35:00Z",
    )
    row = detail_df.iloc[0]

    assert row["action_ready_now"] == "0"
    assert row["user_price_check_required"] == "1"
    assert "supplier_cost_confirmation_required" in row["block_reason_codes"]
    assert block_df[block_df["block_reason"] == "supplier_cost_confirmation_required"].iloc[0]["rows_count"] == "1"


def test_o020_blocks_action_ready_when_net_fee_truth_is_stale(tmp_path: Path) -> None:
    stale_fields = {
        "market_price_ex_vat_gbp": "2.083333",
        "market_price_vat_rate_pct": "20",
        "current_token_cost_gbp": "0.63",
        "break_even_price_gbp": "2.21",
        "net_fee_drag_per_unit_gbp": "1.58",
        "net_fee_model_status": "stale",
        "net_fee_model_asof": "2026-05-15",
        "net_fee_model_age_hours": "108",
        "net_fee_model_source": "sku_performance_summary",
        "net_fee_model_notes": "stale_model_asof",
        "gross_forward_roi_pct": "296.825397",
        "gross_forward_profit_per_unit_gbp": "1.87",
    }
    _write_contract_rows(
        tmp_path,
        "restock_source_view",
        [
            {
                "asof_utc": "2026-05-19T12:10:00Z",
                "seller_sku": "SKU-STALE-FEE",
                "asin": "ASIN-STALE-FEE",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "sale_status": "active",
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
                "expected_refund_cost_per_unit_gbp": "0",
                "is_active_candidate": "1",
                "has_current_cost_input": "1",
                "has_current_market_price_input": "1",
                "has_demand_input": "1",
                "has_minimum_restock_inputs": "1",
                "coverage_block_reason": "ready_minimum_inputs",
                "cost_mode": "live",
                **stale_fields,
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_recommendations_live",
        [
            {
                "asof_utc": "2026-05-19T12:20:00Z",
                "seller_sku": "SKU-STALE-FEE",
                "asin": "ASIN-STALE-FEE",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "recommendation_status": "full_restock",
                "reason_codes": "",
                "recommended_qty_raw": "30",
                "recommended_qty_rounded": "30",
                "target_days_cover": "30",
                "days_cover_available_only": "0",
                "days_cover_total_pipeline": "0",
                "current_supplier_buy_cost_gbp": "0.63",
                "current_supplier_cost_source": "supplier_buy_cost_truth",
                "market_price_gbp": "2.50",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "forward_roi_pct": "-20.105873",
                "forward_profit_per_unit_gbp": "-0.126667",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                **stale_fields,
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_review_queue",
        [
            {
                "queue_utc": "2026-05-19T12:30:00Z",
                "seller_sku": "SKU-STALE-FEE",
                "asin": "ASIN-STALE-FEE",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "recommendation_status": "full_restock",
                "suggested_qty": "30",
                "suggested_unit_cost_gbp": "0.63",
                "suggested_market_price_gbp": "2.50",
                "expected_forward_roi_pct": "-20.105873",
                "expected_forward_profit_per_unit_gbp": "-0.126667",
                "queue_status": "needs_review",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                **stale_fields,
            }
        ],
    )

    detail_df, _supplier_df, block_df = build_reorder_input_coverage_report(
        root=tmp_path,
        report_utc="2026-05-19T12:35:00Z",
    )
    row = detail_df.iloc[0]

    assert row["action_candidate"] == "1"
    assert row["action_ready_now"] == "0"
    assert row["net_fee_model_status"] == "stale"
    assert "stale_net_fee_truth" in row["block_reason_codes"]
    assert block_df[block_df["block_reason"] == "stale_net_fee_truth"].iloc[0]["rows_count"] == "1"


def test_o020_blocks_action_ready_when_pack_profile_is_invalid(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_source_view",
        [
            {
                "asof_utc": "2026-05-19T12:10:00Z",
                "seller_sku": "PE-G94Y-4PYO",
                "asin": "ASIN-PE",
                "supplier_code": "SIKA",
                "supplier_name": "Sika",
                "sale_status": "active",
                "available_now": "0",
                "total_quantity_now": "0",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_7d": "1",
                "velocity_30d": "1",
                "velocity_90d": "1",
                "current_supplier_buy_cost_gbp": "6.30",
                "current_supplier_cost_source": "supplier_catalog_price",
                "market_price_gbp": "12.00",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "expected_refund_cost_per_unit_gbp": "0",
                "is_active_candidate": "1",
                "has_current_cost_input": "1",
                "has_current_market_price_input": "1",
                "has_demand_input": "1",
                "has_minimum_restock_inputs": "1",
                "coverage_block_reason": "ready_minimum_inputs",
                "cost_mode": "live",
                "components_per_sell_pack": "3",
                "supplier_cost_basis": "component_unit",
                "expected_sell_pack_cost_gbp": "6.30",
                "expected_component_cost_gbp": "2.10",
                "quantity_strategy": "preferred_carton_multiple",
                "preferred_order_sell_packs": "120",
                "preferred_order_components": "360",
                "preferred_supplier_boxes": "18",
                "supplier_box_components": "20",
                "hazmat_group": "sika_glue",
                "isolate_from_normal_po": "1",
                "target_carton_weight_kg": "23",
                "pack_profile_status": "invalid",
                "source_notes": "pack_title_profile_mismatch",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_recommendations_live",
        [
            {
                "asof_utc": "2026-05-19T12:20:00Z",
                "seller_sku": "PE-G94Y-4PYO",
                "asin": "ASIN-PE",
                "supplier_code": "SIKA",
                "supplier_name": "Sika",
                "recommendation_status": "full_restock",
                "reason_codes": "",
                "recommended_qty_raw": "30",
                "recommended_qty_rounded": "30",
                "target_days_cover": "30",
                "days_cover_available_only": "0",
                "days_cover_total_pipeline": "0",
                "current_supplier_buy_cost_gbp": "6.30",
                "current_supplier_cost_source": "supplier_catalog_price",
                "market_price_gbp": "12.00",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "forward_roi_pct": "90.47619",
                "forward_profit_per_unit_gbp": "5.70",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                "components_per_sell_pack": "3",
                "supplier_cost_basis": "component_unit",
                "expected_sell_pack_cost_gbp": "6.30",
                "expected_component_cost_gbp": "2.10",
                "pack_profile_status": "invalid",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_review_queue",
        [
            {
                "queue_utc": "2026-05-19T12:30:00Z",
                "seller_sku": "PE-G94Y-4PYO",
                "asin": "ASIN-PE",
                "supplier_code": "SIKA",
                "supplier_name": "Sika",
                "recommendation_status": "full_restock",
                "suggested_qty": "30",
                "suggested_unit_cost_gbp": "6.30",
                "suggested_market_price_gbp": "12.00",
                "expected_forward_roi_pct": "90.47619",
                "expected_forward_profit_per_unit_gbp": "5.70",
                "reason_codes": "",
                "queue_status": "needs_review",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            }
        ],
    )

    detail_df, _supplier_df, block_df = build_reorder_input_coverage_report(
        root=tmp_path,
        report_utc="2026-05-19T12:35:00Z",
    )
    row = detail_df.iloc[0]

    assert row["action_candidate"] == "1"
    assert row["action_ready_now"] == "0"
    assert "invalid_component_conversion" in row["block_reason_codes"]
    assert "pack_title_profile_mismatch" in row["block_reason_codes"]
    assert block_df[block_df["block_reason"] == "pack_title_profile_mismatch"].iloc[0]["rows_count"] == "1"


def test_reorder_input_sample_fixture_has_required_categories() -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "o_phase_ui" / "reorder_input_sample.csv"
    assert fixture_path.exists()
    with fixture_path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    categories = {row["scenario_tag"] for row in rows}
    assert categories == {
        "actionable_full_restock",
        "actionable_test_restock",
        "wait",
        "snoozed",
        "missing_cost",
        "missing_market_price",
        "missing_supplier_identity",
        "long_lead_bulk",
    }
