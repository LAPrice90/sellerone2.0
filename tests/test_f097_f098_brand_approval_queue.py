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

from scripts.flows.F.F096_reconcile_amazon_listing_submissions import reconcile_amazon_listing_submissions
from scripts.flows.F.F097_check_amazon_listing_restrictions import run_amazon_listing_restriction_check
from scripts.flows.F.F098_build_brand_approval_queue import (
    build_brand_approval_queue,
    record_brand_approval_decisions,
)
from scripts.flows.F._contract_io import read_f_contract_df, write_f_contract_df


OBSERVED = "2026-05-01T13:00:00Z"


def _draft_row(
    *,
    draft_id: str = "draft-brand",
    asin: str = "B000000001",
    sku: str = "NP-SUP-BRAND",
    brand: str = "Brand A",
) -> dict[str, str]:
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
        "amazon_title": "Brand Approval Product",
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
        "vat_source_value": "standard",
        "profile_event_id": "profile_1",
        "profile_utc": OBSERVED,
        "profile_note": "",
        "brand": brand,
    }


def _seed_drafts(tmp_path: Path, rows: list[dict[str, str]]) -> None:
    write_f_contract_df(tmp_path, "amazon_listing_drafts_live", pd.DataFrame(rows))


def test_f097_records_clear_restriction_status(tmp_path: Path) -> None:
    _seed_drafts(tmp_path, [_draft_row()])

    def fake_restriction(_row: dict[str, str]) -> dict[str, object]:
        return {"http_status": "200", "payload": {"restrictions": []}}

    result = run_amazon_listing_restriction_check(
        root=tmp_path,
        observed_utc=OBSERVED,
        restriction_client=fake_restriction,
        run_check=True,
    )

    assert result["clear_rows"] == 1
    live = read_f_contract_df(tmp_path, "amazon_listing_restrictions_live")
    assert live.iloc[0]["restriction_status"] == "clear"
    assert live.iloc[0]["approval_required_flag"] == "0"


def test_f097_records_approval_required_status_and_link(tmp_path: Path) -> None:
    _seed_drafts(tmp_path, [_draft_row()])

    def fake_restriction(_row: dict[str, str]) -> dict[str, object]:
        return {
            "http_status": "200",
            "payload": {
                "restrictions": [
                    {
                        "marketplaceId": "A1F83G8C2ARO7P",
                        "conditionType": "new_new",
                        "reasons": [
                            {
                                "reasonCode": "APPROVAL_REQUIRED",
                                "message": "You need approval to list this brand.",
                                "links": [{"resource": "https://sellercentral.amazon.co.uk/approval"}],
                            }
                        ],
                    }
                ]
            },
        }

    result = run_amazon_listing_restriction_check(
        root=tmp_path,
        observed_utc=OBSERVED,
        restriction_client=fake_restriction,
        run_check=True,
    )

    assert result["approval_required_rows"] == 1
    live = read_f_contract_df(tmp_path, "amazon_listing_restrictions_live")
    row = live.iloc[0]
    assert row["restriction_status"] == "approval_required"
    assert row["approval_required_flag"] == "1"
    assert row["reason_code"] == "APPROVAL_REQUIRED"
    assert row["approval_link"] == "https://sellercentral.amazon.co.uk/approval"


def test_f098_builds_queue_and_applies_invoice_decision(tmp_path: Path) -> None:
    _seed_drafts(tmp_path, [_draft_row()])
    write_f_contract_df(
        tmp_path,
        "amazon_listing_restrictions_live",
        pd.DataFrame(
            [
                {
                    "observed_utc": OBSERVED,
                    "restriction_id": "restriction_1",
                    "draft_id": "draft-brand",
                    "candidate_id": "cand_1",
                    "expected_seller_sku": "NP-SUP-BRAND",
                    "asin": "B000000001",
                    "marketplace_id": "A1F83G8C2ARO7P",
                    "condition_type": "new_new",
                    "restriction_status": "approval_required",
                    "approval_required_flag": "1",
                    "reason_code": "APPROVAL_REQUIRED",
                    "reason_message": "You need approval to list this brand.",
                    "approval_link": "https://sellercentral.amazon.co.uk/approval",
                    "http_status": "200",
                    "source_reference": "amazon_listing_restriction_events",
                    "updated_at_utc": OBSERVED,
                    "brand": "Brand A",
                    "amazon_title": "Brand Approval Product",
                    "supplier_id": "supplier_a",
                    "supplier_sku": "SUP-1",
                    "latest_restriction_event_id": "restriction-event-1",
                    "latest_restriction_utc": OBSERVED,
                }
            ]
        ),
    )

    first = build_brand_approval_queue(root=tmp_path, observed_utc=OBSERVED)
    assert first.iloc[0]["approval_status"] == "approval_required"
    queue_id = first.iloc[0]["queue_id"]

    record_brand_approval_decisions(
        root=tmp_path,
        observed_utc=OBSERVED,
        actor="tester",
        decision_rows=[
            {
                "queue_id": queue_id,
                "draft_id": "draft-brand",
                "candidate_id": "cand_1",
                "expected_seller_sku": "NP-SUP-BRAND",
                "asin": "B000000001",
                "marketplace_id": "A1F83G8C2ARO7P",
                "operator_decision": "invoice_planned",
                "decision_reason": "10 units is acceptable for approval test",
                "invoice_required_quantity": "10",
                "invoice_unit_cost_gbp": "7.00",
            }
        ],
    )
    second = build_brand_approval_queue(root=tmp_path, observed_utc=OBSERVED)
    row = second.iloc[0]
    assert row["approval_status"] == "invoice_required"
    assert row["operator_decision"] == "invoice_planned"
    assert row["invoice_required_quantity"] == "10"
    assert row["invoice_total_risk_gbp"] == "70.00"
    assert row["recheck_trigger"] == "invoice_uploaded"


def test_f098_builds_queue_from_readback_18304_issue(tmp_path: Path) -> None:
    _seed_drafts(tmp_path, [_draft_row()])
    write_f_contract_df(
        tmp_path,
        "amazon_listing_readback_events",
        pd.DataFrame(
            [
                {
                    "event_utc": OBSERVED,
                    "event_id": "readback-1",
                    "draft_id": "draft-brand",
                    "expected_seller_sku": "NP-SUP-BRAND",
                    "asin": "B000000001",
                    "marketplace_id": "A1F83G8C2ARO7P",
                    "submission_id": "sub-1",
                    "readback_status": "blocking_issues",
                    "asin_match_status": "match",
                    "issue_count": "1",
                    "blocking_issue_count": "1",
                    "notes": "ERROR 18304 You need approval to list this brand.",
                    "candidate_id": "cand_1",
                    "http_status": "200",
                    "amazon_asin": "B000000001",
                    "source_reference": "amazon_listing_drafts_live",
                }
            ]
        ),
    )

    out = build_brand_approval_queue(root=tmp_path, observed_utc=OBSERVED)

    assert len(out.index) == 1
    row = out.iloc[0]
    assert row["draft_id"] == "draft-brand"
    assert row["approval_status"] == "approval_required"
    assert row["reason_code"] == "APPROVAL_REQUIRED"
    assert "18304" in row["reason_message"]


def test_f096_blocks_product_db_eligibility_when_brand_approval_queue_is_active(tmp_path: Path) -> None:
    _seed_drafts(tmp_path, [_draft_row()])
    write_f_contract_df(
        tmp_path,
        "amazon_listing_readback_events",
        pd.DataFrame(
            [
                {
                    "event_utc": OBSERVED,
                    "event_id": "readback-ok",
                    "draft_id": "draft-brand",
                    "expected_seller_sku": "NP-SUP-BRAND",
                    "asin": "B000000001",
                    "marketplace_id": "A1F83G8C2ARO7P",
                    "submission_id": "sub-1",
                    "readback_status": "confirmed",
                    "asin_match_status": "match",
                    "issue_count": "0",
                    "blocking_issue_count": "0",
                    "notes": "listing_readback_confirmed",
                }
            ]
        ),
    )
    write_f_contract_df(
        tmp_path,
        "brand_approval_queue_live",
        pd.DataFrame(
            [
                {
                    "observed_utc": OBSERVED,
                    "queue_id": "brand_approval_1",
                    "draft_id": "draft-brand",
                    "candidate_id": "cand_1",
                    "expected_seller_sku": "NP-SUP-BRAND",
                    "asin": "B000000001",
                    "marketplace_id": "A1F83G8C2ARO7P",
                    "brand": "Brand A",
                    "amazon_title": "Brand Approval Product",
                    "approval_status": "invoice_required",
                    "approval_required_flag": "1",
                    "reason_code": "APPROVAL_REQUIRED",
                    "reason_message": "You need approval to list this brand.",
                    "approval_link": "",
                    "invoice_required_quantity": "10",
                    "invoice_unit_cost_gbp": "7.00",
                    "invoice_total_risk_gbp": "70.00",
                    "operator_decision": "invoice_planned",
                    "decision_reason": "acceptable test",
                    "cooldown_until_utc": "",
                    "recheck_trigger": "invoice_uploaded",
                    "approval_application_status": "",
                    "invoice_artifact_reference": "",
                    "updated_at_utc": OBSERVED,
                    "source_reference": "test",
                }
            ]
        ),
    )

    out = reconcile_amazon_listing_submissions(root=tmp_path, observed_utc=OBSERVED)

    row = out.iloc[0]
    assert row["reconciliation_status"] == "blocked"
    assert row["block_reason"] == "invoice_required"
    assert "brand_approval_queue_live" in row["source_reference"]
