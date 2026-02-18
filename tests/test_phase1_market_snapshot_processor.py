import unittest

from scripts import phase1_market_snapshot_processor as snapshot


class MarketSnapshotProcessorTests(unittest.TestCase):
    def test_process_competitive_summary_normalizes_rows_and_flags(self) -> None:
        payload = {
            "payload": [
                {
                    "asin": "B001TEST",
                    "offers": [
                        {
                            "sellerId": " Seller-A ",
                            "IsFulfilledByAmazon": True,
                            "condition": "New",
                            "ListingPrice": {"Amount": 10},
                            "Shipping": {"Amount": 1.25},
                            "ShippingTime": {"minimumDays": 1, "maximumDays": 2},
                            "isPrime": True,
                            "isFeaturedOfferWinner": True,
                            "shippingTemplate": "std",
                        },
                        {
                            "sellerId": "Seller-B",
                            "FulfillmentChannel": "merchant",
                            "Condition": "New",
                            "ListingPrice": {"Amount": "11.00"},
                            "Shipping": {"Amount": "0.00"},
                            "isPrime": False,
                            "isFeaturedOfferWinner": False,
                            "shippingTemplate": "std",
                        },
                    ],
                }
            ]
        }
        result = snapshot.process_competitive_summary(
            payload=payload,
            sku="SKU-1",
            asin="B001TEST",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="seller-a",
            snapshot_ts_utc="2026-02-13T12:00:00Z",
        )
        self.assertEqual(len(result.rows), 2)
        self.assertEqual(result.featured_offer_winner_seller_id, "sellera")
        self.assertEqual(result.featured_offer_price_gbp, "11.25")
        self.assertFalse(result.unknown_featured_outcome)

        first = result.rows[0]
        self.assertEqual(first["snapshot_ts_utc"], "2026-02-13T12:00:00Z")
        self.assertEqual(first["seller_id_canonical"], "sellera")
        self.assertEqual(first["fulfilment_channel"], "FBA")
        self.assertEqual(first["listing_price_gbp"], "10.00")
        self.assertEqual(first["shipping_gbp"], "1.25")
        self.assertEqual(first["landed_price_gbp"], "11.25")
        self.assertEqual(first["min_delivery_days"], "1")
        self.assertEqual(first["max_delivery_days"], "2")
        self.assertEqual(first["is_prime"], "1")
        self.assertEqual(first["is_featured_offer_winner"], "1")
        self.assertEqual(first["is_our_offer"], "1")
        self.assertEqual(first["unknown_outcome_flag"], "0")
        self.assertTrue(first["offer_snapshot_id"])
        self.assertTrue(first["offer_variant_id"].startswith("ov_"))

        second = result.rows[1]
        self.assertEqual(second["fulfilment_channel"], "FBM")
        self.assertEqual(second["is_prime"], "0")
        self.assertEqual(second["is_our_offer"], "0")

    def test_variant_mapping_is_stable_for_same_structure(self) -> None:
        variant_1 = snapshot.compute_offer_variant_id(
            marketplace_id="A1F83G8C2ARO7P",
            sku="SKU-1",
            seller_id_canonical="sellera",
            fulfilment_channel="FBA",
            condition="New",
            shipping_template="std",
        )
        variant_2 = snapshot.compute_offer_variant_id(
            marketplace_id="A1F83G8C2ARO7P",
            sku="SKU-1",
            seller_id_canonical="sellera",
            fulfilment_channel="FBA",
            condition="New",
            shipping_template="std",
        )
        variant_3 = snapshot.compute_offer_variant_id(
            marketplace_id="A1F83G8C2ARO7P",
            sku="SKU-1",
            seller_id_canonical="sellera",
            fulfilment_channel="FBM",
            condition="New",
            shipping_template="std",
        )
        self.assertEqual(variant_1, variant_2)
        self.assertNotEqual(variant_1, variant_3)

    def test_missing_featured_outcome_sets_unknown_flag(self) -> None:
        payload = {
            "offers": [
                {
                    "sellerId": "Seller-A",
                    "IsFulfilledByAmazon": True,
                    "ListingPrice": {"Amount": 10},
                    "Shipping": {"Amount": 0},
                }
            ]
        }
        result = snapshot.process_competitive_summary(
            payload=payload,
            sku="SKU-1",
            asin="B001TEST",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="seller-a",
            snapshot_ts_utc="2026-02-13T12:00:00Z",
        )
        self.assertTrue(result.unknown_featured_outcome)
        self.assertEqual(result.featured_offer_winner_seller_id, "")
        self.assertEqual(result.featured_offer_price_gbp, "")
        self.assertEqual(result.rows[0]["unknown_outcome_flag"], "1")


if __name__ == "__main__":
    unittest.main()
