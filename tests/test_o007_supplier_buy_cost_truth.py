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

from scripts.flows.O.O007_build_supplier_buy_cost_truth import build_supplier_buy_cost_truth


def _write_product_db(root: Path) -> None:
    path = root / "out" / "product_db_preview.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "seller_sku": "SKU-SAME",
                "asin": "ASIN-SAME",
                "title": "Same Cost",
                "supplier_code": "alpha",
                "supplier_name": "Alpha Supplier",
                "supplier_sku": "ALPHA-SAME",
                "barcode": "1111111111111",
                "supplier_pack_size": "1",
                "moq": "1",
                "supplier_catalog_price": "2.00",
                "last_purchase_price": "2.00",
                "sale_status": "active",
                "vat_rate": "20",
            },
            {
                "seller_sku": "SKU-DISCOUNT",
                "asin": "ASIN-DISCOUNT",
                "title": "Discount Cost",
                "supplier_code": "alpha",
                "supplier_name": "Alpha Supplier",
                "supplier_sku": "ALPHA-DISCOUNT",
                "barcode": "2222222222222",
                "supplier_pack_size": "1",
                "moq": "1",
                "supplier_catalog_price": "2.00",
                "last_purchase_price": "1.80",
                "sale_status": "active",
                "vat_rate": "20",
            },
            {
                "seller_sku": "SKU-MISSING-LIST",
                "asin": "ASIN-MISSING-LIST",
                "title": "Missing List Cost",
                "supplier_code": "beta",
                "supplier_name": "Beta Supplier",
                "supplier_sku": "BETA-MISSING",
                "barcode": "3333333333333",
                "supplier_pack_size": "1",
                "moq": "1",
                "supplier_catalog_price": "3.00",
                "last_purchase_price": "",
                "sale_status": "active",
                "vat_rate": "20",
            },
            {
                "seller_sku": "SKU-CHEAPER-LIST",
                "asin": "ASIN-CHEAPER-LIST",
                "title": "Cheaper Current List",
                "supplier_code": "alpha",
                "supplier_name": "Alpha Supplier",
                "supplier_sku": "ALPHA-CHEAPER",
                "barcode": "4444444444444",
                "supplier_pack_size": "1",
                "moq": "1",
                "supplier_catalog_price": "2.00",
                "last_purchase_price": "2.00",
                "sale_status": "active",
                "vat_rate": "20",
            },
        ]
    ).to_csv(path, index=False)


def _write_f_price_lists(root: Path) -> None:
    test_dir = root / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    test_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "supplier_id": "alpha_supplier",
                "supplier_name": "Alpha Supplier",
                "source_type": "api",
                "source_subtype": "csv",
                "source_url": "",
                "source_folder_path": "",
                "existing_supplier_config_path": "",
                "converter_id": "alpha_supplier",
                "normal_refresh_days": "1",
                "minimum_rescan_days": "1",
                "large_file_flag": "0",
                "manual_request_required_flag": "0",
                "priority_band": "daily",
                "active_flag": "1",
                "notes": "",
            }
        ]
    ).to_csv(test_dir / "supplier_registry.csv", index=False)
    pd.DataFrame(
        [
            {
                "batch_id": "alpha_20260519",
                "supplier_id": "alpha_supplier",
                "source_type": "api",
                "source_subtype": "csv",
                "source_received_at_utc": "2026-05-19T09:00:00Z",
                "source_file_path": "alpha.csv",
                "source_file_hash": "hash",
                "converted_file_path": "alpha_converted.csv",
                "source_row_count": "2",
                "valid_row_count": "2",
                "held_row_count": "0",
                "new_row_count": "2",
                "changed_row_count": "0",
                "eligible_row_count": "2",
                "skipped_cooldown_row_count": "0",
                "batch_status": "imported_from_source",
                "status_reason": "ready",
                "updated_at_utc": "2026-05-19T09:01:00Z",
            }
        ]
    ).to_csv(test_dir / "price_list_batches.csv", index=False)
    pd.DataFrame(
        [
            {
                "batch_id": "alpha_20260519",
                "supplier_id": "alpha_supplier",
                "row_key": "row_same",
                "supplier_sku": "ALPHA-SAME",
                "supplier_title": "Same Product",
                "barcode": "1111111111111",
                "unit_cost": "2.50",
                "currency": "GBP",
                "vat_rate": "20",
                "source_row_hash": "row_same",
                "row_change_status": "changed",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "test",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            },
            {
                "batch_id": "alpha_20260519",
                "supplier_id": "alpha_supplier",
                "row_key": "row_discount",
                "supplier_sku": "ALPHA-DISCOUNT",
                "supplier_title": "Discount Product",
                "barcode": "2222222222222",
                "unit_cost": "2.50",
                "currency": "GBP",
                "vat_rate": "20",
                "source_row_hash": "row_discount",
                "row_change_status": "changed",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "test",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            },
            {
                "batch_id": "alpha_20260519",
                "supplier_id": "alpha_supplier",
                "row_key": "row_cheaper",
                "supplier_sku": "ALPHA-CHEAPER",
                "supplier_title": "Cheaper Product",
                "barcode": "4444444444444",
                "unit_cost": "1.50",
                "currency": "GBP",
                "vat_rate": "20",
                "unit_code": "PK12",
                "pack_size": "12",
                "pack_cost": "18.00",
                "moq": "12",
                "source_row_hash": "row_cheaper",
                "row_change_status": "changed",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "test",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            },
        ]
    ).to_csv(test_dir / "batch_rows.csv", index=False)


def test_o007_builds_expected_cost_and_discount_assumption(tmp_path: Path) -> None:
    _write_product_db(tmp_path)
    _write_f_price_lists(tmp_path)

    out_df = build_supplier_buy_cost_truth(root=tmp_path, asof_utc="2026-05-19T12:00:00Z")
    by_sku = out_df.set_index("seller_sku")

    same = by_sku.loc["SKU-SAME"]
    assert same["price_list_unit_cost_gbp"] == "2.5"
    assert same["purchase_reference_list_cost_gbp"] == "2"
    assert same["actual_paid_unit_cost_gbp"] == "2"
    assert same["actual_vs_list_ratio"] == "1"
    assert same["expected_next_unit_cost_gbp"] == "2.5"
    assert same["user_price_check_required"] == "0"
    assert same["cost_confidence"] == "price_list_actual_match"

    discounted = by_sku.loc["SKU-DISCOUNT"]
    assert discounted["price_list_unit_cost_gbp"] == "2.5"
    assert discounted["actual_paid_unit_cost_gbp"] == "1.8"
    assert discounted["actual_vs_list_ratio"] == "0.9"
    assert discounted["discount_assumption_pct"] == "10"
    assert discounted["expected_next_unit_cost_gbp"] == "2.25"
    assert discounted["user_price_check_required"] == "1"
    assert "discount_assumption_needs_confirmation" in discounted["review_reason"]
    assert "price_list_changed_after_discounted_purchase" in discounted["review_reason"]

    missing_list = by_sku.loc["SKU-MISSING-LIST"]
    assert missing_list["price_list_unit_cost_gbp"] == ""
    assert missing_list["expected_next_unit_cost_gbp"] == "3"
    assert missing_list["user_price_check_required"] == "1"
    assert "missing_current_price_list_cost" in missing_list["review_reason"]

    cheaper = by_sku.loc["SKU-CHEAPER-LIST"]
    assert cheaper["price_list_unit_cost_gbp"] == "1.5"
    assert cheaper["actual_paid_unit_cost_gbp"] == "2"
    assert cheaper["expected_next_unit_cost_gbp"] == "1.5"
    assert cheaper["user_price_check_required"] == "0"
    assert cheaper["price_list_vs_actual_paid_delta_gbp"] == "-0.5"
    assert cheaper["price_list_unit_code"] == "PK12"
    assert cheaper["price_list_pack_size"] == "12"
    assert cheaper["price_list_pack_cost_gbp"] == "18.00"
    assert cheaper["price_list_moq"] == "12"


def test_o007_tracks_price_list_changes_and_usual_paid_profile(tmp_path: Path) -> None:
    product_path = tmp_path / "out" / "product_db_preview.csv"
    product_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"seller_sku": "SKU-UP", "asin": "ASIN-UP", "title": "Up", "supplier_code": "alpha", "supplier_name": "Alpha Supplier", "supplier_sku": "UP", "barcode": "100", "supplier_catalog_price": "1.00", "last_purchase_price": "1.00"},
            {"seller_sku": "SKU-DOWN", "asin": "ASIN-DOWN", "title": "Down", "supplier_code": "alpha", "supplier_name": "Alpha Supplier", "supplier_sku": "DOWN", "barcode": "200", "supplier_catalog_price": "2.00", "last_purchase_price": "2.00"},
            {"seller_sku": "SKU-PACK", "asin": "ASIN-PACK", "title": "Pack", "supplier_code": "alpha", "supplier_name": "Alpha Supplier", "supplier_sku": "PACK", "barcode": "300", "supplier_catalog_price": "1.00", "last_purchase_price": "1.00"},
            {"seller_sku": "SKU-REMOVED", "asin": "ASIN-REMOVED", "title": "Removed", "supplier_code": "alpha", "supplier_name": "Alpha Supplier", "supplier_sku": "REMOVED", "barcode": "400", "supplier_catalog_price": "1.00", "last_purchase_price": "1.00"},
            {"seller_sku": "SKU-NEW", "asin": "ASIN-NEW", "title": "New", "supplier_code": "alpha", "supplier_name": "Alpha Supplier", "supplier_sku": "NEW", "barcode": "500", "supplier_catalog_price": "1.00", "last_purchase_price": "1.00"},
            {"seller_sku": "SKU-SAME2", "asin": "ASIN-SAME2", "title": "Same", "supplier_code": "alpha", "supplier_name": "Alpha Supplier", "supplier_sku": "SAME2", "barcode": "600", "supplier_catalog_price": "1.00", "last_purchase_price": "1.00"},
            {"seller_sku": "SKU-HISTORY", "asin": "ASIN-HISTORY", "title": "History", "supplier_code": "alpha", "supplier_name": "Alpha Supplier", "supplier_sku": "HISTORY", "barcode": "700", "supplier_catalog_price": "2.00", "last_purchase_price": "1.90"},
        ]
    ).to_csv(product_path, index=False)

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    test_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"supplier_id": "alpha_supplier", "supplier_name": "Alpha Supplier"}]).to_csv(test_dir / "supplier_registry.csv", index=False)
    pd.DataFrame(
        [
            {"batch_id": "alpha_old", "supplier_id": "alpha_supplier", "source_received_at_utc": "2026-05-01T09:00:00Z", "updated_at_utc": "2026-05-01T09:01:00Z"},
            {"batch_id": "alpha_new", "supplier_id": "alpha_supplier", "source_received_at_utc": "2026-05-20T09:00:00Z", "updated_at_utc": "2026-05-20T09:01:00Z"},
        ]
    ).to_csv(test_dir / "price_list_batches.csv", index=False)
    batch_rows = [
        {"batch_id": "alpha_old", "supplier_id": "alpha_supplier", "row_key": "old_up", "supplier_sku": "UP", "supplier_title": "Up", "barcode": "100", "unit_cost": "1.00", "currency": "GBP", "pack_size": "1", "pack_cost": "1.00", "moq": "1"},
        {"batch_id": "alpha_old", "supplier_id": "alpha_supplier", "row_key": "old_down", "supplier_sku": "DOWN", "supplier_title": "Down", "barcode": "200", "unit_cost": "2.00", "currency": "GBP", "pack_size": "1", "pack_cost": "2.00", "moq": "1"},
        {"batch_id": "alpha_old", "supplier_id": "alpha_supplier", "row_key": "old_pack", "supplier_sku": "PACK", "supplier_title": "Pack", "barcode": "300", "unit_cost": "1.00", "currency": "GBP", "unit_code": "PK6", "pack_size": "6", "pack_cost": "6.00", "moq": "6"},
        {"batch_id": "alpha_old", "supplier_id": "alpha_supplier", "row_key": "old_removed", "supplier_sku": "REMOVED", "supplier_title": "Removed", "barcode": "400", "unit_cost": "1.00", "currency": "GBP", "pack_size": "1", "pack_cost": "1.00", "moq": "1"},
        {"batch_id": "alpha_old", "supplier_id": "alpha_supplier", "row_key": "old_same", "supplier_sku": "SAME2", "supplier_title": "Same", "barcode": "600", "unit_cost": "1.00", "currency": "GBP", "pack_size": "1", "pack_cost": "1.00", "moq": "1"},
        {"batch_id": "alpha_old", "supplier_id": "alpha_supplier", "row_key": "old_history", "supplier_sku": "HISTORY", "supplier_title": "History", "barcode": "700", "unit_cost": "2.00", "currency": "GBP", "pack_size": "1", "pack_cost": "2.00", "moq": "1"},
        {"batch_id": "alpha_new", "supplier_id": "alpha_supplier", "row_key": "new_up", "supplier_sku": "UP", "supplier_title": "Up", "barcode": "100", "unit_cost": "1.20", "currency": "GBP", "pack_size": "1", "pack_cost": "1.20", "moq": "1"},
        {"batch_id": "alpha_new", "supplier_id": "alpha_supplier", "row_key": "new_down", "supplier_sku": "DOWN", "supplier_title": "Down", "barcode": "200", "unit_cost": "1.70", "currency": "GBP", "pack_size": "1", "pack_cost": "1.70", "moq": "1"},
        {"batch_id": "alpha_new", "supplier_id": "alpha_supplier", "row_key": "new_pack", "supplier_sku": "PACK", "supplier_title": "Pack", "barcode": "300", "unit_cost": "1.00", "currency": "GBP", "unit_code": "PK12", "pack_size": "12", "pack_cost": "12.00", "moq": "12"},
        {"batch_id": "alpha_new", "supplier_id": "alpha_supplier", "row_key": "new_new", "supplier_sku": "NEW", "supplier_title": "New", "barcode": "500", "unit_cost": "1.00", "currency": "GBP", "pack_size": "1", "pack_cost": "1.00", "moq": "1"},
        {"batch_id": "alpha_new", "supplier_id": "alpha_supplier", "row_key": "new_same", "supplier_sku": "SAME2", "supplier_title": "Same", "barcode": "600", "unit_cost": "1.00", "currency": "GBP", "pack_size": "1", "pack_cost": "1.00", "moq": "1"},
        {"batch_id": "alpha_new", "supplier_id": "alpha_supplier", "row_key": "new_history", "supplier_sku": "HISTORY", "supplier_title": "History", "barcode": "700", "unit_cost": "2.00", "currency": "GBP", "pack_size": "1", "pack_cost": "2.00", "moq": "1"},
    ]
    pd.DataFrame(batch_rows).to_csv(test_dir / "batch_rows.csv", index=False)

    log_path = tmp_path / "out" / "systems" / "O" / "live" / "restock_decisions_log.csv"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"decision_utc": "2026-05-02T10:00:00Z", "event_utc": "2026-05-02T09:59:00Z", "event_id": "evt-h1", "seller_sku": "SKU-HISTORY", "asin": "ASIN-HISTORY", "decision_action": "approve_full_restock", "final_decision_status": "full_restock", "confirmed_unit_cost": "1.70", "confirmed_qty": "1"},
            {"decision_utc": "2026-05-03T10:00:00Z", "event_utc": "2026-05-03T09:59:00Z", "event_id": "evt-h2", "seller_sku": "SKU-HISTORY", "asin": "ASIN-HISTORY", "decision_action": "approve_full_restock", "final_decision_status": "full_restock", "confirmed_unit_cost": "1.80", "confirmed_qty": "1"},
            {"decision_utc": "2026-05-04T10:00:00Z", "event_utc": "2026-05-04T09:59:00Z", "event_id": "evt-h3", "seller_sku": "SKU-HISTORY", "asin": "ASIN-HISTORY", "decision_action": "approve_full_restock", "final_decision_status": "full_restock", "confirmed_unit_cost": "1.70", "confirmed_qty": "1"},
            {"decision_utc": "2026-05-05T10:00:00Z", "event_utc": "2026-05-05T09:59:00Z", "event_id": "evt-h4", "seller_sku": "SKU-HISTORY", "asin": "ASIN-HISTORY", "decision_action": "approve_full_restock", "final_decision_status": "full_restock", "confirmed_unit_cost": "5.00", "confirmed_qty": "1"},
            {"decision_utc": "2026-05-06T10:00:00Z", "event_utc": "2026-05-06T09:59:00Z", "event_id": "evt-h5", "seller_sku": "SKU-HISTORY", "asin": "ASIN-HISTORY", "decision_action": "approve_full_restock", "final_decision_status": "full_restock", "confirmed_unit_cost": "1.70", "confirmed_qty": "1"},
            {"decision_utc": "2024-01-01T10:00:00Z", "event_utc": "2024-01-01T09:59:00Z", "event_id": "evt-old", "seller_sku": "SKU-HISTORY", "asin": "ASIN-HISTORY", "decision_action": "approve_full_restock", "final_decision_status": "full_restock", "confirmed_unit_cost": "9.99", "confirmed_qty": "1"},
        ]
    ).to_csv(log_path, index=False)

    out_df = build_supplier_buy_cost_truth(root=tmp_path, asof_utc="2026-05-22T12:00:00Z")
    by_sku = out_df.set_index("seller_sku")

    assert by_sku.loc["SKU-UP", "price_list_change_status"] == "cost_up"
    assert by_sku.loc["SKU-DOWN", "price_list_change_status"] == "cost_down"
    assert by_sku.loc["SKU-PACK", "price_list_change_status"] == "pack_changed"
    assert by_sku.loc["SKU-REMOVED", "price_list_change_status"] == "removed"
    assert by_sku.loc["SKU-NEW", "price_list_change_status"] == "new"
    assert by_sku.loc["SKU-SAME2", "price_list_change_status"] == "unchanged"
    assert by_sku.loc["SKU-HISTORY", "usual_paid_unit_cost_gbp"] == "1.7"
    assert by_sku.loc["SKU-HISTORY", "usual_paid_sample_count"] == "5"
    assert by_sku.loc["SKU-HISTORY", "usual_paid_discount_vs_list_pct"] == "15"

    change_log = pd.read_csv(
        tmp_path / "out" / "systems" / "O" / "live" / "supplier_price_list_change_log_live.csv",
        dtype=str,
    ).fillna("")
    assert set(change_log["change_status"]).issuperset({"cost_up", "cost_down", "pack_changed", "removed", "new", "unchanged"})
