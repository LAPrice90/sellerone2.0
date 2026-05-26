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

from scripts.flows.F.F094_submit_amazon_listing_drafts import run_amazon_listing_submit
from scripts.flows.F._contract_io import read_f_contract_df, write_f_contract_df


OBSERVED = "2026-05-01T12:00:00Z"


def _draft_row(
    *,
    draft_id: str = "draft-ready",
    draft_status: str = "ready_for_live_submit",
    preview_status: str = "preview_passed",
    submission_status: str = "not_submitted",
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
        "amazon_title": "Submit Product",
        "supplier_cost_gbp": "3.50",
        "expected_seller_sku": "NP-SUP-12345678",
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
        "draft_status": draft_status,
        "block_reason": "",
        "amazon_preview_status": preview_status,
        "amazon_preview_issue_count": "0",
        "amazon_submission_status": submission_status,
        "amazon_submission_id": "",
        "updated_at_utc": OBSERVED,
        "minimum_selling_price_rule": "manual_required",
        "listing_approval_status": "approved_for_preview",
        "source_intake_id": "intake_1",
        "source_reservation_id": "reservation_1",
    }


def _seed_drafts(tmp_path: Path, rows: list[dict[str, str]]) -> None:
    write_f_contract_df(tmp_path, "amazon_listing_drafts_live", pd.DataFrame(rows))


def test_f094_dry_run_requires_live_flags_and_does_not_submit(tmp_path: Path) -> None:
    _seed_drafts(tmp_path, [_draft_row()])

    def fake_submit(_row: dict[str, str]) -> dict[str, object]:
        raise AssertionError("submit client should not be called")

    result = run_amazon_listing_submit(
        root=tmp_path,
        observed_utc=OBSERVED,
        submit_client=fake_submit,
        run_submit=False,
        confirm_live_submit=False,
    )

    assert result["eligible_rows"] == 1
    assert result["attempted_rows"] == 0
    assert read_f_contract_df(tmp_path, "amazon_listing_submission_events").empty


def test_f094_submit_success_marks_draft_submitted(tmp_path: Path) -> None:
    _seed_drafts(tmp_path, [_draft_row()])

    def fake_submit(_row: dict[str, str]) -> dict[str, object]:
        return {"http_status": "200", "payload": {"status": "ACCEPTED", "submissionId": "sub-1", "issues": []}}

    result = run_amazon_listing_submit(
        root=tmp_path,
        observed_utc=OBSERVED,
        submit_client=fake_submit,
        run_submit=True,
        confirm_live_submit=True,
    )

    assert result["submitted_rows"] == 1
    drafts = read_f_contract_df(tmp_path, "amazon_listing_drafts_live")
    row = drafts.iloc[0]
    assert row["draft_status"] == "submitted_to_amazon"
    assert row["amazon_submission_status"] == "submitted"
    assert row["amazon_submission_id"] == "sub-1"
    events = read_f_contract_df(tmp_path, "amazon_listing_submission_events")
    assert len(events.index) == 1
    assert events.iloc[0]["submission_status"] == "submitted"
    assert events.iloc[0]["response_status"] == "ACCEPTED"


def test_f094_submit_rejection_records_hold(tmp_path: Path) -> None:
    _seed_drafts(tmp_path, [_draft_row()])

    def fake_submit(_row: dict[str, str]) -> dict[str, object]:
        return {
            "http_status": "200",
            "payload": {
                "status": "INVALID",
                "issues": [{"code": "4000001", "severity": "ERROR", "message": "Invalid price"}],
            },
        }

    result = run_amazon_listing_submit(
        root=tmp_path,
        observed_utc=OBSERVED,
        submit_client=fake_submit,
        run_submit=True,
        confirm_live_submit=True,
    )

    assert result["rejected_rows"] == 1
    drafts = read_f_contract_df(tmp_path, "amazon_listing_drafts_live")
    assert drafts.iloc[0]["draft_status"] == "blocked_amazon_submit"
    assert drafts.iloc[0]["block_reason"] == "amazon_submit_rejected"
    holds = read_f_contract_df(tmp_path, "amazon_listing_holds_live")
    assert len(holds.index) == 1
    assert holds.iloc[0]["hold_stage"] == "amazon_submit"
    assert holds.iloc[0]["hold_reason"] == "amazon_submit_rejected"


def test_f094_submit_http_failure_records_status_not_success_note(tmp_path: Path) -> None:
    _seed_drafts(tmp_path, [_draft_row()])

    def fake_submit(_row: dict[str, str]) -> dict[str, object]:
        return {"http_status": "400", "payload": {"errors": [{"code": "InvalidInput", "message": "Bad request"}]}}

    result = run_amazon_listing_submit(
        root=tmp_path,
        observed_utc=OBSERVED,
        submit_client=fake_submit,
        run_submit=True,
        confirm_live_submit=True,
    )

    assert result["failed_rows"] == 1
    events = read_f_contract_df(tmp_path, "amazon_listing_submission_events")
    event = events.iloc[0]
    assert event["submission_status"] == "submit_failed"
    assert event["http_status"] == "400"
    assert "http_status=400" in event["notes"]
    assert "listing_submitted" not in event["notes"]
    holds = read_f_contract_df(tmp_path, "amazon_listing_holds_live")
    assert "http_status=400" in holds.iloc[0]["hold_note"]


def test_f094_ignores_drafts_without_passed_preview(tmp_path: Path) -> None:
    _seed_drafts(
        tmp_path,
        [_draft_row(draft_status="ready_for_amazon_preview", preview_status="not_run")],
    )

    def fake_submit(_row: dict[str, str]) -> dict[str, object]:
        raise AssertionError("submit client should not be called")

    result = run_amazon_listing_submit(
        root=tmp_path,
        observed_utc=OBSERVED,
        submit_client=fake_submit,
        run_submit=True,
        confirm_live_submit=True,
    )

    assert result["eligible_rows"] == 0
    assert result["attempted_rows"] == 0


def test_f094_retry_failed_submit_selects_only_previous_http_failures(tmp_path: Path) -> None:
    _seed_drafts(
        tmp_path,
        [
            _draft_row(
                draft_id="draft-failed",
                draft_status="blocked_amazon_submit",
                submission_status="submit_failed",
            )
            | {"block_reason": "amazon_submit_failed", "amazon_submission_id": ""},
            _draft_row(
                draft_id="draft-rejected",
                draft_status="blocked_amazon_submit",
                submission_status="submit_rejected",
            )
            | {"block_reason": "amazon_submit_rejected", "amazon_submission_id": ""},
        ],
    )
    attempted: list[str] = []

    def fake_submit(row: dict[str, str]) -> dict[str, object]:
        attempted.append(row["draft_id"])
        return {"http_status": "200", "payload": {"status": "ACCEPTED", "submissionId": "sub-retry", "issues": []}}

    result = run_amazon_listing_submit(
        root=tmp_path,
        observed_utc=OBSERVED,
        submit_client=fake_submit,
        run_submit=True,
        confirm_live_submit=True,
        retry_failed_submit=True,
    )

    assert result["eligible_rows"] == 1
    assert result["submitted_rows"] == 1
    assert attempted == ["draft-failed"]


def test_f094_does_not_submit_known_brand_approval_block(tmp_path: Path) -> None:
    _seed_drafts(tmp_path, [_draft_row()])
    write_f_contract_df(
        tmp_path,
        "brand_approval_queue_live",
        pd.DataFrame(
            [
                {
                    "observed_utc": OBSERVED,
                    "queue_id": "brand-approval-1",
                    "draft_id": "draft-ready",
                    "candidate_id": "cand_1",
                    "expected_seller_sku": "NP-SUP-12345678",
                    "asin": "B000000001",
                    "marketplace_id": "A1F83G8C2ARO7P",
                    "brand": "Brand A",
                    "amazon_title": "Submit Product",
                    "approval_status": "invoice_required",
                    "approval_required_flag": "1",
                    "reason_code": "APPROVAL_REQUIRED",
                    "reason_message": "You need approval to list this brand.",
                    "approval_link": "",
                    "invoice_required_quantity": "10",
                    "invoice_unit_cost_gbp": "7.00",
                    "invoice_total_risk_gbp": "70.00",
                    "operator_decision": "invoice_planned",
                    "decision_reason": "approval test",
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

    def fake_submit(_row: dict[str, str]) -> dict[str, object]:
        raise AssertionError("submit client should not be called")

    result = run_amazon_listing_submit(
        root=tmp_path,
        observed_utc=OBSERVED,
        submit_client=fake_submit,
        run_submit=True,
        confirm_live_submit=True,
    )

    assert result["eligible_rows"] == 0
    assert result["attempted_rows"] == 0
    drafts = read_f_contract_df(tmp_path, "amazon_listing_drafts_live")
    assert drafts.iloc[0]["draft_status"] == "blocked_amazon_submit"
    assert drafts.iloc[0]["block_reason"] == "brand_approval_required"
    holds = read_f_contract_df(tmp_path, "amazon_listing_holds_live")
    assert holds.iloc[0]["hold_reason"] == "brand_approval_required"
