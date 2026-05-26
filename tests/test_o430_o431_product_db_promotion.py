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

from scripts.flows.F._contract_io import write_f_contract_df
from scripts.flows.O.O430_build_product_db_promotion_candidates import build_product_db_promotion_candidates
from scripts.flows.O.O431_stage_product_db_create_events import (
    PRODUCT_DB_PROMOTION_DESTINATION_FIELDS,
    product_db_destination_schema_status,
    stage_product_db_create_events,
)
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df


OBSERVED = "2026-05-01T14:00:00Z"


def _draft_row(*, draft_id: str = "draft-ok", sku: str = "NP-SUP-OK", asin: str = "B000000001") -> dict[str, str]:
    return {
        "observed_utc": OBSERVED,
        "draft_id": draft_id,
        "supplier_id": "supplier_a",
        "supplier_name": "Supplier A",
        "source_run_id": "run_1",
        "review_snapshot_id": "snap_1",
        "review_batch_id": "batch_1",
        "candidate_id": "cand_1",
        "supplier_sku": "SUP-1",
        "barcode": "5012345678901",
        "asin": asin,
        "amazon_title": "Promotion Product",
        "supplier_cost_gbp": "7.00",
        "expected_seller_sku": sku,
        "sku_reservation_status": "reserved",
        "sku_reservation_reason": "reserved",
        "marketplace_id": "A1F83G8C2ARO7P",
        "country_of_origin": "GB",
        "purchase_pack_size": "1",
        "sold_pack_size": "1",
        "vat_confirmed_flag": "1",
        "product_tax_code": "A_GEN_STANDARD",
        "currency_code": "GBP",
        "price_includes_tax": "1",
        "product_type": "PRODUCT",
        "condition_type": "new_new",
        "fulfillment_channel": "DEFAULT",
        "starting_price_gbp": "12.34",
        "starting_quantity": "0",
        "listing_mode": "existing_asin_offer",
        "draft_status": "submitted_to_amazon",
        "block_reason": "",
        "amazon_preview_status": "preview_passed",
        "amazon_preview_issue_count": "0",
        "amazon_submission_status": "submitted",
        "amazon_submission_id": "sub-1",
        "updated_at_utc": OBSERVED,
        "minimum_selling_price_rule": "manual_required",
        "listing_approval_status": "approved_for_preview",
        "source_intake_id": "intake_1",
        "source_reservation_id": "reservation_1",
        "vat_source_value": "20",
        "profile_event_id": "profile_1",
        "profile_utc": OBSERVED,
        "profile_note": "",
    }


def _intake_row() -> dict[str, str]:
    return {
        "observed_utc": OBSERVED,
        "intake_id": "intake_1",
        "supplier_id": "supplier_a",
        "supplier_name": "Supplier A",
        "active_run_id": "run_1",
        "review_pack_type": "passes",
        "review_snapshot_id": "snap_1",
        "review_batch_id": "batch_1",
        "candidate_id": "cand_1",
        "supplier_sku": "SUP-1",
        "barcode": "5012345678901",
        "asin": "B000000001",
        "amazon_title": "Promotion Product",
        "brand": "Brand A",
        "supplier_cost_gbp": "7.00",
        "starting_price_gbp": "12.34",
        "marketplace_id": "A1F83G8C2ARO7P",
        "country_of_origin": "GB",
        "purchase_pack_size": "1",
        "sold_pack_size": "1",
        "vat_confirmed_flag": "1",
        "product_tax_code": "A_GEN_STANDARD",
        "currency_code": "GBP",
        "price_includes_tax": "1",
        "listing_mode": "existing_asin_offer",
        "latest_review_event_id": "event_1",
        "latest_review_utc": OBSERVED,
        "intake_status": "ready_for_sku_reservation",
        "block_reason": "",
        "source_manifest_path": "",
        "source_review_pack_path": "",
        "updated_at_utc": OBSERVED,
        "vat_source_value": "20",
    }


def _reconciliation_row(
    *,
    draft_id: str = "draft-ok",
    sku: str = "NP-SUP-OK",
    asin: str = "B000000001",
    status: str = "confirmed_product_db_eligible",
    block_reason: str = "",
) -> dict[str, str]:
    return {
        "observed_utc": OBSERVED,
        "draft_id": draft_id,
        "expected_seller_sku": sku,
        "asin": asin,
        "marketplace_id": "A1F83G8C2ARO7P",
        "submission_id": "sub-1",
        "readback_status": "confirmed",
        "asin_match_status": "match",
        "blocking_issue_count": "0",
        "reconciliation_status": status,
        "block_reason": block_reason,
        "updated_at_utc": OBSERVED,
        "candidate_id": "cand_1",
    }


def _seed_complete_sources(tmp_path: Path) -> None:
    write_f_contract_df(tmp_path, "amazon_listing_drafts_live", pd.DataFrame([_draft_row()]))
    write_f_contract_df(tmp_path, "amazon_listing_intake_live", pd.DataFrame([_intake_row()]))
    write_f_contract_df(tmp_path, "amazon_listing_reconciliation_live", pd.DataFrame([_reconciliation_row()]))


def _seed_product_db_destination_schema(tmp_path: Path, *, missing_fields: tuple[str, ...] = ()) -> None:
    path = tmp_path / "out" / "product_db_preview.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [field for field in PRODUCT_DB_PROMOTION_DESTINATION_FIELDS if field not in set(missing_fields)]
    pd.DataFrame(columns=columns).to_csv(path, index=False)


def test_o430_builds_ready_candidate_from_confirmed_listing(tmp_path: Path) -> None:
    _seed_complete_sources(tmp_path)

    out = build_product_db_promotion_candidates(root=tmp_path, observed_utc=OBSERVED)

    assert len(out.index) == 1
    row = out.iloc[0]
    assert row["promotion_status"] == "ready_for_product_db_event"
    assert row["seller_sku"] == "NP-SUP-OK"
    assert row["supplier_pack_size"] == "1"
    assert row["amazon_pack_size"] == "1"
    assert row["vat_rate"] == "20"
    assert row["sale_status"] == "inactive"
    assert read_o_contract_df(tmp_path, "product_db_promotion_holds_live").empty


def test_o430_maps_sold_pack_profile_to_product_db_pack_fields(tmp_path: Path) -> None:
    draft = _draft_row()
    draft["purchase_pack_size"] = "1"
    draft["sold_pack_size"] = "3"
    intake = _intake_row()
    intake["purchase_pack_size"] = "1"
    intake["sold_pack_size"] = "3"
    write_f_contract_df(tmp_path, "amazon_listing_drafts_live", pd.DataFrame([draft]))
    write_f_contract_df(tmp_path, "amazon_listing_intake_live", pd.DataFrame([intake]))
    write_f_contract_df(tmp_path, "amazon_listing_reconciliation_live", pd.DataFrame([_reconciliation_row()]))

    out = build_product_db_promotion_candidates(root=tmp_path, observed_utc=OBSERVED)

    row = out.iloc[0]
    assert row["promotion_status"] == "ready_for_product_db_event"
    assert row["supplier_pack_size"] == "1"
    assert row["amazon_pack_size"] == "3"
    assert row["sell_pack_qty"] == "3"
    assert row["supplier_case_qty"] == "1"
    assert row["valid_order_step"] == "1"
    assert row["order_qty_mode"] == "sell_packs"
    assert row["repack_required"] == "1"
    assert row["bundle_required"] == "1"


def test_o430_holds_confirmed_listing_missing_pack_and_vat_profile(tmp_path: Path) -> None:
    draft = _draft_row()
    draft["purchase_pack_size"] = ""
    draft["sold_pack_size"] = ""
    draft["vat_confirmed_flag"] = ""
    draft["vat_source_value"] = ""
    intake = _intake_row()
    intake["purchase_pack_size"] = ""
    intake["sold_pack_size"] = ""
    intake["vat_confirmed_flag"] = ""
    intake["vat_source_value"] = ""
    write_f_contract_df(tmp_path, "amazon_listing_drafts_live", pd.DataFrame([draft]))
    write_f_contract_df(tmp_path, "amazon_listing_intake_live", pd.DataFrame([intake]))
    write_f_contract_df(tmp_path, "amazon_listing_reconciliation_live", pd.DataFrame([_reconciliation_row()]))

    out = build_product_db_promotion_candidates(root=tmp_path, observed_utc=OBSERVED)

    row = out.iloc[0]
    assert row["promotion_status"] == "held"
    assert "missing_purchase_pack_size" in row["block_reason_codes"]
    assert "missing_sold_pack_size" in row["block_reason_codes"]
    assert "missing_vat_confirmation" in row["block_reason_codes"]
    holds = read_o_contract_df(tmp_path, "product_db_promotion_holds_live")
    assert len(holds.index) == 1


def test_o430_excludes_brand_approval_block_from_ready_candidates(tmp_path: Path) -> None:
    _seed_complete_sources(tmp_path)
    write_f_contract_df(
        tmp_path,
        "brand_approval_queue_live",
        pd.DataFrame(
            [
                {
                    "observed_utc": OBSERVED,
                    "queue_id": "brand_approval_1",
                    "draft_id": "draft-ok",
                    "candidate_id": "cand_1",
                    "expected_seller_sku": "NP-SUP-OK",
                    "asin": "B000000001",
                    "marketplace_id": "A1F83G8C2ARO7P",
                    "brand": "Brand A",
                    "amazon_title": "Promotion Product",
                    "approval_status": "parked_invoice_or_brand_risk",
                    "approval_required_flag": "1",
                    "reason_code": "APPROVAL_REQUIRED",
                    "reason_message": "approval required",
                    "approval_link": "",
                    "invoice_required_quantity": "",
                    "invoice_unit_cost_gbp": "",
                    "invoice_total_risk_gbp": "",
                    "operator_decision": "park",
                    "decision_reason": "too risky",
                    "cooldown_until_utc": "2027-05-01T00:00:00Z",
                    "recheck_trigger": "manual",
                    "approval_application_status": "",
                    "invoice_artifact_reference": "",
                    "updated_at_utc": OBSERVED,
                    "source_reference": "test",
                }
            ]
        ),
    )

    out = build_product_db_promotion_candidates(root=tmp_path, observed_utc=OBSERVED)

    assert out.iloc[0]["promotion_status"] == "held"
    assert "brand_approval_block" in out.iloc[0]["block_reason_codes"]


def test_o431_dry_run_does_not_write_product_db_edit_events(tmp_path: Path) -> None:
    _seed_complete_sources(tmp_path)
    build_product_db_promotion_candidates(root=tmp_path, observed_utc=OBSERVED)

    result = stage_product_db_create_events(root=tmp_path, stage_events=False, confirm_product_db_promotion=False)

    assert result["eligible_rows"] == 1
    assert result["staged_rows"] == 0
    assert read_o_contract_df(tmp_path, "product_db_edit_events").empty


def test_o431_blocks_staging_when_product_db_destination_schema_is_missing_fields(tmp_path: Path) -> None:
    _seed_complete_sources(tmp_path)
    _seed_product_db_destination_schema(tmp_path, missing_fields=("barcode", "supplier_case_qty"))
    build_product_db_promotion_candidates(root=tmp_path, observed_utc=OBSERVED)

    schema_status = product_db_destination_schema_status(tmp_path)
    result = stage_product_db_create_events(
        root=tmp_path,
        stage_events=True,
        confirm_product_db_promotion=True,
        actor="tester",
    )

    assert schema_status["ready"] is False
    assert "barcode" in schema_status["missing_fields"]
    assert "supplier_case_qty" in schema_status["missing_fields"]
    assert result["staged_rows"] == 0
    assert result["held_rows"] == 1
    assert read_o_contract_df(tmp_path, "product_db_edit_events").empty
    health = read_o_contract_df(tmp_path, "product_db_promotion_health")
    schema_health = health[health["check"] == "product_db_destination_schema"].iloc[0]
    assert schema_health["status"] == "fail"
    assert "barcode" in schema_health["notes"]


def test_o431_stages_product_db_edit_events_idempotently_with_flags(tmp_path: Path) -> None:
    _seed_complete_sources(tmp_path)
    _seed_product_db_destination_schema(tmp_path)
    build_product_db_promotion_candidates(root=tmp_path, observed_utc=OBSERVED)

    first = stage_product_db_create_events(
        root=tmp_path,
        stage_events=True,
        confirm_product_db_promotion=True,
        actor="tester",
    )
    second = stage_product_db_create_events(
        root=tmp_path,
        stage_events=True,
        confirm_product_db_promotion=True,
        actor="tester",
    )

    assert first["staged_rows"] == 1
    assert second["staged_rows"] == 0
    assert second["already_staged_rows"] == 1
    events = read_o_contract_df(tmp_path, "product_db_edit_events")
    assert len(events.index) == 1
    assert events.iloc[0]["seller_sku"] == "NP-SUP-OK"
    assert events.iloc[0]["sale_status"] == "inactive"
