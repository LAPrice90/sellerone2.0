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

from scripts.flows.F.F091_reserve_amazon_listing_skus import (
    generate_expected_seller_sku,
    reserve_amazon_listing_skus,
)
from scripts.flows.F._contract_io import read_f_contract_df, write_f_contract_df


OBSERVED = "2026-05-01T10:40:00Z"


def _seed_intake(tmp_path: Path, *, asin: str = "B000000001") -> None:
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
                    "asin": asin,
                    "amazon_title": "Review Product",
                    "brand": "Brand A",
                    "supplier_cost_gbp": "3.50",
                    "starting_price_gbp": "9.99",
                    "marketplace_id": "A1F83G8C2ARO7P",
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


def _expected_sku() -> str:
    return generate_expected_seller_sku(
        supplier_id="supplier_a",
        active_run_id="run_1",
        candidate_id="cand_1",
        asin="B000000001",
        marketplace_id="A1F83G8C2ARO7P",
    )


def test_f091_reservation_is_stable_across_reruns(tmp_path: Path) -> None:
    _seed_intake(tmp_path)

    first = reserve_amazon_listing_skus(root=tmp_path, observed_utc=OBSERVED)
    second = reserve_amazon_listing_skus(root=tmp_path, observed_utc="2026-05-01T10:41:00Z")

    assert len(first.index) == 1
    assert len(second.index) == 1
    assert first.iloc[0]["expected_seller_sku"] == second.iloc[0]["expected_seller_sku"]
    assert second.iloc[0]["sku_reservation_status"] == "reserved"


def test_f091_product_db_sku_collision_blocks_reservation(tmp_path: Path) -> None:
    _seed_intake(tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"seller_sku": _expected_sku(), "asin": "B000000001"}]).to_csv(
        out_dir / "product_db_preview.csv",
        index=False,
    )

    out = reserve_amazon_listing_skus(root=tmp_path, observed_utc=OBSERVED)

    assert out.iloc[0]["sku_reservation_status"] == "held"
    assert out.iloc[0]["sku_reservation_reason"] == "sku_collision_product_db"
    holds = read_f_contract_df(tmp_path, "amazon_listing_holds_live")
    assert holds.iloc[0]["hold_stage"] == "sku_reservation"


def test_f091_listing_snapshot_sku_collision_blocks_reservation(tmp_path: Path) -> None:
    _seed_intake(tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"sku": _expected_sku(), "asin": "B000000001"}]).to_csv(
        out_dir / "listing_offer_snapshot_latest.csv",
        index=False,
    )

    out = reserve_amazon_listing_skus(root=tmp_path, observed_utc=OBSERVED)

    assert out.iloc[0]["sku_reservation_status"] == "held"
    assert out.iloc[0]["sku_reservation_reason"] == "sku_collision_listing_snapshot"
