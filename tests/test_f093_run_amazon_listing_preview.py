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

from scripts.flows.F.F093_run_amazon_listing_preview import run_amazon_listing_preview
from scripts.flows.F._contract_io import read_f_contract_df, write_f_contract_df


OBSERVED = "2026-05-01T11:10:00Z"


def _draft_row(
    *,
    draft_id: str = "draft-ready",
    draft_status: str = "ready_for_amazon_preview",
    approval_status: str = "approved_for_preview",
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
        "asin": "B000000001",
        "amazon_title": "Preview Product",
        "supplier_cost_gbp": "3.50",
        "expected_seller_sku": "NP-SUP-12345678",
        "sku_reservation_status": "reserved",
        "sku_reservation_reason": "new_reservation",
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
        "draft_status": draft_status,
        "block_reason": "",
        "amazon_preview_status": "not_run",
        "amazon_preview_issue_count": "0",
        "amazon_submission_status": "not_submitted",
        "amazon_submission_id": "",
        "updated_at_utc": OBSERVED,
        "minimum_selling_price_rule": "manual_required",
        "listing_approval_status": approval_status,
        "source_intake_id": "intake_1",
        "source_reservation_id": "reservation_1",
    }


def _seed_drafts(tmp_path: Path, rows: list[dict[str, str]]) -> None:
    write_f_contract_df(tmp_path, "amazon_listing_drafts_live", pd.DataFrame(rows))


def test_f093_preview_pass_marks_draft_ready_for_live_submit(tmp_path: Path) -> None:
    _seed_drafts(tmp_path, [_draft_row()])

    def fake_preview(_row: dict[str, str]) -> dict[str, object]:
        return {"http_status": "200", "payload": {"status": "ACCEPTED", "issues": []}}

    result = run_amazon_listing_preview(
        root=tmp_path,
        observed_utc=OBSERVED,
        preview_client=fake_preview,
        run_preview=True,
    )

    assert result == {
        "eligible_rows": 1,
        "attempted_rows": 1,
        "passed_rows": 1,
        "rejected_rows": 0,
        "failed_rows": 0,
    }
    drafts = read_f_contract_df(tmp_path, "amazon_listing_drafts_live")
    row = drafts.iloc[0]
    assert row["draft_status"] == "ready_for_live_submit"
    assert row["amazon_preview_status"] == "preview_passed"
    assert row["amazon_preview_issue_count"] == "0"
    assert read_f_contract_df(tmp_path, "amazon_listing_preview_issues_live").empty
    assert read_f_contract_df(tmp_path, "amazon_listing_holds_live").empty
    events = read_f_contract_df(tmp_path, "amazon_listing_preview_events")
    assert len(events.index) == 1
    assert events.iloc[0]["preview_status"] == "preview_passed"


def test_f093_preview_rejection_records_issue_and_hold(tmp_path: Path) -> None:
    _seed_drafts(tmp_path, [_draft_row()])

    def fake_preview(_row: dict[str, str]) -> dict[str, object]:
        return {
            "http_status": "200",
            "payload": {
                "status": "INVALID",
                "issues": [
                    {
                        "code": "4000001",
                        "severity": "ERROR",
                        "message": "Price is invalid",
                        "attributeNames": ["purchasable_offer"],
                    }
                ],
            },
        }

    result = run_amazon_listing_preview(
        root=tmp_path,
        observed_utc=OBSERVED,
        preview_client=fake_preview,
        run_preview=True,
    )

    assert result["rejected_rows"] == 1
    drafts = read_f_contract_df(tmp_path, "amazon_listing_drafts_live")
    row = drafts.iloc[0]
    assert row["draft_status"] == "blocked_amazon_preview"
    assert row["amazon_preview_status"] == "preview_rejected"
    assert row["amazon_preview_issue_count"] == "1"
    issues = read_f_contract_df(tmp_path, "amazon_listing_preview_issues_live")
    assert len(issues.index) == 1
    assert issues.iloc[0]["issue_code"] == "4000001"
    assert issues.iloc[0]["issue_severity"] == "ERROR"
    holds = read_f_contract_df(tmp_path, "amazon_listing_holds_live")
    assert len(holds.index) == 1
    assert holds.iloc[0]["hold_stage"] == "amazon_preview"
    assert holds.iloc[0]["hold_reason"] == "amazon_preview_rejected"


def test_f093_ignores_drafts_without_operator_preview_approval(tmp_path: Path) -> None:
    _seed_drafts(
        tmp_path,
        [
            _draft_row(
                draft_id="draft-not-approved",
                draft_status="ready_for_listing_approval",
                approval_status="pending_operator_approval",
            )
        ],
    )

    def fake_preview(_row: dict[str, str]) -> dict[str, object]:
        raise AssertionError("preview client should not be called")

    result = run_amazon_listing_preview(
        root=tmp_path,
        observed_utc=OBSERVED,
        preview_client=fake_preview,
        run_preview=True,
    )

    assert result["eligible_rows"] == 0
    assert result["attempted_rows"] == 0
    drafts = read_f_contract_df(tmp_path, "amazon_listing_drafts_live")
    assert drafts.iloc[0]["draft_status"] == "ready_for_listing_approval"
    assert read_f_contract_df(tmp_path, "amazon_listing_preview_events").empty
