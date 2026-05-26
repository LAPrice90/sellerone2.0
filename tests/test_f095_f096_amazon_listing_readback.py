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

from scripts.flows.F.F095_check_amazon_listing_submission_status import run_amazon_listing_readback
from scripts.flows.F.F096_reconcile_amazon_listing_submissions import reconcile_amazon_listing_submissions
from scripts.flows.F._contract_io import read_f_contract_df, write_f_contract_df


OBSERVED = "2026-05-01T12:30:00Z"


def _draft_row(
    *,
    draft_id: str = "draft-ready",
    asin: str = "B000000001",
    sku: str = "NP-SUP-12345678",
    submission_id: str = "sub-1",
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
        "amazon_title": "Readback Product",
        "supplier_cost_gbp": "3.50",
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
        "amazon_submission_id": submission_id,
        "updated_at_utc": OBSERVED,
        "minimum_selling_price_rule": "manual_required",
        "listing_approval_status": "approved_for_preview",
        "source_intake_id": "intake_1",
        "source_reservation_id": "reservation_1",
    }


def _seed_drafts(tmp_path: Path, rows: list[dict[str, str]]) -> None:
    write_f_contract_df(tmp_path, "amazon_listing_drafts_live", pd.DataFrame(rows))


def test_f095_readback_confirmed_records_event(tmp_path: Path) -> None:
    _seed_drafts(tmp_path, [_draft_row()])

    def fake_readback(_row: dict[str, str]) -> dict[str, object]:
        return {
            "http_status": "200",
            "payload": {
                "sku": "NP-SUP-12345678",
                "summaries": [{"marketplaceId": "A1F83G8C2ARO7P", "asin": "B000000001"}],
                "issues": [],
            },
        }

    result = run_amazon_listing_readback(
        root=tmp_path,
        observed_utc=OBSERVED,
        readback_client=fake_readback,
        run_readback=True,
    )

    assert result["confirmed_rows"] == 1
    events = read_f_contract_df(tmp_path, "amazon_listing_readback_events")
    row = events.iloc[0]
    assert row["readback_status"] == "confirmed"
    assert row["asin_match_status"] == "match"
    assert row["blocking_issue_count"] == "0"


def test_f095_readback_blocking_issue_records_blocked_event(tmp_path: Path) -> None:
    _seed_drafts(tmp_path, [_draft_row()])

    def fake_readback(_row: dict[str, str]) -> dict[str, object]:
        return {
            "http_status": "200",
            "payload": {
                "summaries": [{"asin": "B000000001"}],
                "issues": [{"severity": "ERROR", "code": "90220", "message": "Listing blocked"}],
            },
        }

    result = run_amazon_listing_readback(
        root=tmp_path,
        observed_utc=OBSERVED,
        readback_client=fake_readback,
        run_readback=True,
    )

    assert result["blocked_rows"] == 1
    events = read_f_contract_df(tmp_path, "amazon_listing_readback_events")
    assert events.iloc[0]["readback_status"] == "blocking_issues"
    assert events.iloc[0]["blocking_issue_count"] == "1"


def test_f096_reconciles_confirmed_and_pending_rows(tmp_path: Path) -> None:
    _seed_drafts(
        tmp_path,
        [
            _draft_row(draft_id="draft-confirmed", asin="B000000001", sku="NP-OK", submission_id="sub-ok"),
            _draft_row(draft_id="draft-pending", asin="B000000002", sku="NP-PENDING", submission_id="sub-pending"),
        ],
    )
    write_f_contract_df(
        tmp_path,
        "amazon_listing_readback_events",
        pd.DataFrame(
            [
                {
                    "event_utc": OBSERVED,
                    "event_id": "evt-readback-ok",
                    "draft_id": "draft-confirmed",
                    "expected_seller_sku": "NP-OK",
                    "asin": "B000000001",
                    "marketplace_id": "A1F83G8C2ARO7P",
                    "submission_id": "sub-ok",
                    "readback_status": "confirmed",
                    "asin_match_status": "match",
                    "issue_count": "0",
                    "blocking_issue_count": "0",
                    "notes": "listing_readback_confirmed",
                }
            ]
        ),
    )

    out = reconcile_amazon_listing_submissions(root=tmp_path, observed_utc=OBSERVED)

    assert len(out.index) == 2
    statuses = dict(zip(out["draft_id"], out["reconciliation_status"]))
    assert statuses["draft-confirmed"] == "confirmed_product_db_eligible"
    assert statuses["draft-pending"] == "pending_readback"
    health = read_f_contract_df(tmp_path, "amazon_listing_health")
    row = health[health["check"] == "amazon_listing_reconciliation"].iloc[0]
    assert row["status"] == "warn"
    assert "confirmed_rows=1" in row["notes"]
