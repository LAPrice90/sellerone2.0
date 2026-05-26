from __future__ import annotations

from pathlib import Path

import pandas as pd

import run_api_collection


def test_listing_offer_base_includes_o_restock_market_candidates(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "out"
    (out / "systems" / "O" / "live").mkdir(parents=True)
    monkeypatch.setattr(run_api_collection, "OUT", out)
    monkeypatch.delenv("API_COLLECTION_INCLUDE_O_RESTOCK_CANDIDATES", raising=False)

    pd.DataFrame(
        [
            {"seller-sku": "SKU-ACTIVE", "asin1": "ASIN-ACTIVE", "status": "Active"},
            {"seller-sku": "SKU-INACTIVE", "asin1": "ASIN-INACTIVE", "status": "Inactive"},
        ]
    ).to_csv(out / "merchant_listings_latest.csv", index=False)
    pd.DataFrame(
        [
            {
                "seller_sku": "SKU-RESTOCK",
                "asin": "ASIN-RESTOCK",
                "supplier_name": "Supplier",
                "candidate_status": "ready",
                "market_refresh_reason": "missing_native_max_pay|legacy_sheet_market_not_native",
                "priority": "high",
            },
            {
                "seller_sku": "SKU-NO-ASIN",
                "asin": "",
                "candidate_status": "missing_identity",
                "market_refresh_reason": "missing_current_market_price",
            },
        ]
    ).to_csv(out / "systems" / "O" / "live" / "restock_market_refresh_candidates_live.csv", index=False)

    base = run_api_collection._build_listing_offer_base("2026-05-23T10:00:00Z", "2026-05-23")
    by_sku = base.set_index("sku")

    assert set(by_sku.index) == {"SKU-ACTIVE", "SKU-RESTOCK"}
    assert by_sku.loc["SKU-RESTOCK", "asin"] == "ASIN-RESTOCK"
    assert "o_restock_market_refresh_candidate" in by_sku.loc["SKU-RESTOCK", "notes"]
    assert "legacy_sheet_market_not_native" in by_sku.loc["SKU-RESTOCK", "notes"]


def test_listing_offer_base_keeps_active_merchant_row_when_candidate_duplicates(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "out"
    (out / "systems" / "O" / "live").mkdir(parents=True)
    monkeypatch.setattr(run_api_collection, "OUT", out)

    pd.DataFrame(
        [{"seller-sku": "SKU-DUPE", "asin1": "ASIN-MERCHANT", "status": "Active"}]
    ).to_csv(out / "merchant_listings_latest.csv", index=False)
    pd.DataFrame(
        [
            {
                "seller_sku": "SKU-DUPE",
                "asin": "ASIN-CANDIDATE",
                "candidate_status": "ready",
                "market_refresh_reason": "missing_current_market_price",
                "priority": "high",
            }
        ]
    ).to_csv(out / "systems" / "O" / "live" / "restock_market_refresh_candidates_live.csv", index=False)

    base = run_api_collection._build_listing_offer_base("2026-05-23T10:00:00Z", "2026-05-23")

    assert len(base.index) == 1
    assert base.iloc[0]["sku"] == "SKU-DUPE"
    assert base.iloc[0]["asin"] == "ASIN-MERCHANT"


def test_listing_offer_base_can_run_restock_candidate_only_scope(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "out"
    (out / "systems" / "O" / "live").mkdir(parents=True)
    monkeypatch.setattr(run_api_collection, "OUT", out)
    monkeypatch.setenv("API_COLLECTION_LISTING_BASE_MODE", "restock_candidates")

    pd.DataFrame(
        [{"seller-sku": "SKU-ACTIVE", "asin1": "ASIN-ACTIVE", "status": "Active"}]
    ).to_csv(out / "merchant_listings_latest.csv", index=False)
    pd.DataFrame(
        [
            {
                "seller_sku": "SKU-RESTOCK",
                "asin": "ASIN-RESTOCK",
                "candidate_status": "ready",
                "market_refresh_reason": "missing_native_max_pay",
                "priority": "high",
            }
        ]
    ).to_csv(out / "systems" / "O" / "live" / "restock_market_refresh_candidates_live.csv", index=False)

    base = run_api_collection._build_listing_offer_base("2026-05-23T10:00:00Z", "2026-05-23")

    assert set(base["sku"].tolist()) == {"SKU-RESTOCK"}
    assert base.iloc[0]["asin"] == "ASIN-RESTOCK"
