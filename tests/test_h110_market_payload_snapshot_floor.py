import csv
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.flows.H import H110_run_phase1_h_pilot as h110


class H110MarketPayloadSnapshotFloorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.seller_snapshot_path = self.root / "listing_offer_seller_snapshot_latest.csv"
        self.offer_facts_path = self.root / "offer_snapshot_facts.csv"

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k, "") for k in fieldnames})

    def test_adds_listing_floor_rival_when_seller_snapshot_is_empty_for_sku(self) -> None:
        self._write_csv(
            self.seller_snapshot_path,
            [
                "timestamp_utc",
                "asof_date",
                "marketplace",
                "sku",
                "asin",
                "seller_id",
                "seller_seen_flag",
                "offer_price_gbp",
                "offer_shipping_price_gbp",
                "offer_landed_price_gbp",
                "is_prime",
                "fulfilment_channel",
                "min_delivery_days",
                "max_delivery_days",
                "delivery_range_days",
                "source",
                "notes",
            ],
            [],
        )
        self._write_csv(
            self.offer_facts_path,
            [
                "snapshot_id",
                "snapshot_ts_utc",
                "sku",
                "asin",
                "marketplace_id",
                "seller_id",
                "seller_id_canonical",
                "offer_key",
                "fulfilment_channel",
                "condition_type",
                "listing_price_gbp",
                "shipping_gbp",
                "landed_price_gbp",
                "min_delivery_days",
                "max_delivery_days",
                "is_buy_box_eligible",
                "is_featured_offer_winner",
                "is_prime",
                "is_our_offer",
                "is_buy_box_suppressed",
                "is_live_sample",
            ],
            [
                {
                    "snapshot_id": "snap1",
                    "snapshot_ts_utc": "2026-04-05T17:13:23Z",
                    "sku": "6V-EEC1-2S9Z",
                    "asin": "B06WW79DX5",
                    "marketplace_id": "A1F83G8C2ARO7P",
                    "seller_id_canonical": "RIVAL_A",
                    "offer_key": "offer-1",
                    "fulfilment_channel": "FBA",
                    "listing_price_gbp": "7.10",
                    "shipping_gbp": "0.00",
                    "landed_price_gbp": "7.10",
                    "is_featured_offer_winner": "1",
                    "is_prime": "1",
                    "is_our_offer": "0",
                }
            ],
        )
        listing_row = {
            "sku": "6V-EEC1-2S9Z",
            "asin": "B06WW79DX5",
            "our_price": "7.05",
            "buy_box_price": "7.04",
            "lowest_fba_price": "7.04",
        }

        with mock.patch.object(h110, "_latest_seller_snapshot", return_value=self.seller_snapshot_path):
            with mock.patch.object(h110, "OFFER_SNAPSHOT_FACTS_PATH", self.offer_facts_path):
                payload, listings_observed_price = h110._phase1_market_payload_from_snapshots(
                    sku="6V-EEC1-2S9Z",
                    asin="B06WW79DX5",
                    marketplace_id="A1F83G8C2ARO7P",
                    our_seller_id="AB5OM860MS57Z",
                    listing_row=listing_row,
                )

        self.assertEqual(listings_observed_price, "7.05")
        offers = payload.get("offers", [])
        self.assertTrue(isinstance(offers, list))

        listing_floor_offer = None
        for offer in offers:
            if str(offer.get("SellerId", "")) == "LISTING_SNAPSHOT_FLOOR_RIVAL":
                listing_floor_offer = offer
                break

        self.assertIsNotNone(listing_floor_offer)
        if listing_floor_offer is None:
            return
        self.assertAlmostEqual(float(listing_floor_offer.get("ListingPrice", {}).get("Amount", 0.0)), 7.04, places=2)
        self.assertTrue(bool(listing_floor_offer.get("IsFeaturedOfferWinner", False)))

    def test_does_not_add_listing_floor_rival_when_listing_floor_is_not_lower_than_our_price(self) -> None:
        self._write_csv(
            self.seller_snapshot_path,
            [
                "timestamp_utc",
                "asof_date",
                "marketplace",
                "sku",
                "asin",
                "seller_id",
                "seller_seen_flag",
                "offer_price_gbp",
                "offer_shipping_price_gbp",
                "offer_landed_price_gbp",
                "is_prime",
                "fulfilment_channel",
                "min_delivery_days",
                "max_delivery_days",
                "delivery_range_days",
                "source",
                "notes",
            ],
            [],
        )
        self._write_csv(
            self.offer_facts_path,
            [
                "snapshot_id",
                "snapshot_ts_utc",
                "sku",
                "asin",
                "marketplace_id",
                "seller_id",
                "seller_id_canonical",
                "offer_key",
                "fulfilment_channel",
                "condition_type",
                "listing_price_gbp",
                "shipping_gbp",
                "landed_price_gbp",
                "min_delivery_days",
                "max_delivery_days",
                "is_buy_box_eligible",
                "is_featured_offer_winner",
                "is_prime",
                "is_our_offer",
                "is_buy_box_suppressed",
                "is_live_sample",
            ],
            [
                {
                    "snapshot_id": "snap1",
                    "snapshot_ts_utc": "2026-04-05T17:13:23Z",
                    "sku": "6V-EEC1-2S9Z",
                    "asin": "B06WW79DX5",
                    "marketplace_id": "A1F83G8C2ARO7P",
                    "seller_id_canonical": "RIVAL_A",
                    "offer_key": "offer-1",
                    "fulfilment_channel": "FBA",
                    "listing_price_gbp": "7.10",
                    "shipping_gbp": "0.00",
                    "landed_price_gbp": "7.10",
                    "is_featured_offer_winner": "1",
                    "is_prime": "1",
                    "is_our_offer": "0",
                }
            ],
        )
        listing_row = {
            "sku": "6V-EEC1-2S9Z",
            "asin": "B06WW79DX5",
            "our_price": "7.05",
            "buy_box_price": "7.05",
            "lowest_fba_price": "7.05",
        }

        with mock.patch.object(h110, "_latest_seller_snapshot", return_value=self.seller_snapshot_path):
            with mock.patch.object(h110, "OFFER_SNAPSHOT_FACTS_PATH", self.offer_facts_path):
                payload, _ = h110._phase1_market_payload_from_snapshots(
                    sku="6V-EEC1-2S9Z",
                    asin="B06WW79DX5",
                    marketplace_id="A1F83G8C2ARO7P",
                    our_seller_id="AB5OM860MS57Z",
                    listing_row=listing_row,
                )

        offers = payload.get("offers", [])
        listing_floor_offers = [o for o in offers if str(o.get("SellerId", "")) == "LISTING_SNAPSHOT_FLOOR_RIVAL"]
        self.assertEqual(len(listing_floor_offers), 0)


if __name__ == "__main__":
    unittest.main()
