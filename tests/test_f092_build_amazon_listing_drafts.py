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

from scripts.flows.F.F091_reserve_amazon_listing_skus import reserve_amazon_listing_skus
from scripts.flows.F.F092_build_amazon_listing_drafts import build_amazon_listing_drafts
from scripts.flows.F._contract_io import read_f_contract_df, write_f_contract_df


OBSERVED = "2026-05-01T10:50:00Z"


def _write_defaults(tmp_path: Path, *, starting_price: str = "9.99", product_type: str = "PRODUCT") -> None:
    config_dir = tmp_path / "config" / "feeder"
    config_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "marketplace_id": "A1F83G8C2ARO7P",
                "product_type": product_type,
                "condition_type": "new_new",
                "fulfillment_channel": "DEFAULT",
                "starting_quantity": "0",
                "starting_price_gbp": starting_price,
                "product_tax_code": "A_GEN_STANDARD",
                "currency_code": "GBP",
                "price_includes_tax": "1",
                "minimum_selling_price_rule": "manual_required",
                "enabled": "1",
                "notes": "test defaults",
            }
        ]
    ).to_csv(config_dir / "amazon_listing_defaults.csv", index=False)


def _seed_intake(tmp_path: Path, *, supplier_cost: str = "3.50", starting_price: str = "") -> None:
    write_f_contract_df(
        tmp_path,
        "amazon_listing_intake_live",
        pd.DataFrame(
            [
                {
                    "observed_utc": OBSERVED,
                    "intake_id": "intake_1",
                    "supplier_id": "supplier_a",
                    "supplier_name": "Supplier A",
                    "active_run_id": "run_1",
                    "review_pack_type": "passes",
                    "review_snapshot_id": "snap_1",
                    "review_batch_id": "pass_batch_001",
                    "candidate_id": "cand_1",
                    "supplier_sku": "SUP-1",
                    "barcode": "5012345678901",
                    "asin": "B000000001",
                    "amazon_title": "Review Product",
                    "brand": "Brand A",
                    "supplier_cost_gbp": supplier_cost,
                    "starting_price_gbp": starting_price,
                    "marketplace_id": "A1F83G8C2ARO7P",
                    "country_of_origin": "GB",
                    "purchase_pack_size": "1",
                    "sold_pack_size": "1",
                    "vat_confirmed_flag": "1",
                    "product_tax_code": "A_GEN_STANDARD",
                    "currency_code": "GBP",
                    "price_includes_tax": "1",
                    "listing_mode": "existing_asin_offer",
                    "latest_review_event_id": "evt-pass",
                    "latest_review_utc": OBSERVED,
                    "intake_status": "ready_for_sku_reservation",
                    "block_reason": "",
                    "source_manifest_path": "manifest.csv",
                    "source_review_pack_path": "pass.csv",
                    "updated_at_utc": OBSERVED,
                }
            ]
        ),
    )


def test_f092_valid_reserved_intake_creates_one_ready_draft_and_rerun_does_not_duplicate(tmp_path: Path) -> None:
    _write_defaults(tmp_path)
    _seed_intake(tmp_path)
    reserve_amazon_listing_skus(root=tmp_path, observed_utc=OBSERVED)

    first = build_amazon_listing_drafts(root=tmp_path, observed_utc=OBSERVED)
    second = build_amazon_listing_drafts(root=tmp_path, observed_utc="2026-05-01T10:51:00Z")

    assert len(first.index) == 1
    assert len(second.index) == 1
    assert second.iloc[0]["draft_status"] == "ready_for_listing_approval"
    assert second.iloc[0]["expected_seller_sku"] != ""
    assert second.iloc[0]["product_type"] == "PRODUCT"
    assert second.iloc[0]["fulfillment_channel"] == "DEFAULT"
    assert second.iloc[0]["country_of_origin"] == "GB"
    assert second.iloc[0]["product_tax_code"] == "A_GEN_STANDARD"
    assert second.iloc[0]["currency_code"] == "GBP"
    assert second.iloc[0]["price_includes_tax"] == "1"
    events = read_f_contract_df(tmp_path, "amazon_listing_draft_events")
    assert len(events.index) == 2
    health = read_f_contract_df(tmp_path, "amazon_listing_health")
    assert set(health["check"].tolist()) == {"amazon_listing_sku_reservation", "amazon_listing_draft_builder"}


def test_f092_missing_local_data_creates_blocked_draft_and_hold(tmp_path: Path) -> None:
    _write_defaults(tmp_path, starting_price="", product_type="")
    _seed_intake(tmp_path, supplier_cost="")
    reserve_amazon_listing_skus(root=tmp_path, observed_utc=OBSERVED)

    out = build_amazon_listing_drafts(root=tmp_path, observed_utc=OBSERVED)

    assert len(out.index) == 1
    row = out.iloc[0]
    assert row["draft_status"] == "blocked_missing_local_data"
    assert "supplier_cost_gbp" in row["block_reason"]
    assert "product_type" in row["block_reason"]
    assert "starting_price_gbp" in row["block_reason"]
    holds = read_f_contract_df(tmp_path, "amazon_listing_holds_live")
    assert len(holds.index) == 1
    assert holds.iloc[0]["hold_stage"] == "draft_builder"


def test_f092_missing_country_of_origin_blocks_draft(tmp_path: Path) -> None:
    _write_defaults(tmp_path)
    _seed_intake(tmp_path)
    intake = read_f_contract_df(tmp_path, "amazon_listing_intake_live")
    intake.loc[0, "country_of_origin"] = ""
    write_f_contract_df(tmp_path, "amazon_listing_intake_live", intake)
    reserve_amazon_listing_skus(root=tmp_path, observed_utc=OBSERVED)

    out = build_amazon_listing_drafts(root=tmp_path, observed_utc=OBSERVED)

    assert len(out.index) == 1
    row = out.iloc[0]
    assert row["draft_status"] == "blocked_missing_local_data"
    assert "country_of_origin" in row["block_reason"]
