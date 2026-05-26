import os
import unittest
from unittest import mock

from scripts.api import get_pricing


class _Resp:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = ""

    def json(self) -> dict:
        return dict(self._payload)


class GetPricingDetailMetaTests(unittest.TestCase):
    def test_prioritized_asin_is_selected_and_non_selected_are_flagged_skipped(self) -> None:
        called_asins: list[str] = []

        def fake_spapi_get(*, url: str, **_kwargs):
            asin = url.split("/items/", 1)[1].split("/offers", 1)[0]
            called_asins.append(asin)
            if asin == "A4":
                return _Resp(
                    200,
                    {
                        "payload": {
                            "Summary": {
                                "BuyBoxPrices": [{"LandedPrice": {"Amount": 7.04, "CurrencyCode": "GBP"}}],
                            },
                            "Offers": [
                                {
                                    "SellerId": "RIVAL_A4",
                                    "ListingPrice": {"Amount": 7.04, "CurrencyCode": "GBP"},
                                    "Shipping": {"Amount": 0.0, "CurrencyCode": "GBP"},
                                    "IsFulfilledByAmazon": True,
                                }
                            ],
                        }
                    },
                )
            return _Resp(200, {"payload": {"Summary": {}, "Offers": []}})

        with mock.patch.dict(os.environ, {"SPAPI_ITEM_OFFERS_MAX_ASINS_PER_RUN": "2"}, clear=False):
            with mock.patch.object(get_pricing, "spapi_get", side_effect=fake_spapi_get):
                ctx, offer_rows, detail = get_pricing.fetch_market_context_for_sku_asin(
                    sku_asin_rows=[("S1", "A1"), ("S2", "A2"), ("S3", "A3"), ("S4", "A4")],
                    marketplace_id="A1F83G8C2ARO7P",
                    access_token="token",
                    run_id="RUN123",
                    include_offer_rows=True,
                    include_detail_meta=True,
                    prioritized_asins=["A4"],
                )

        self.assertEqual(len(called_asins), 2)
        self.assertIn("A4", called_asins)
        self.assertEqual(detail["A4"]["detail_status"], get_pricing.DETAIL_STATUS_OK)
        self.assertEqual(detail["A4"]["selected_flag"], "1")
        self.assertEqual(detail["A4"]["offer_row_count"], "1")
        skipped_asins = [asin for asin, meta in detail.items() if meta.get("detail_status") == get_pricing.DETAIL_STATUS_SKIPPED_ROTATION]
        self.assertGreaterEqual(len(skipped_asins), 2)
        self.assertTrue(any(row.get("asin") == "A4" for row in offer_rows))
        self.assertIn("S4", ctx)

    def test_summary_only_response_sets_detail_empty_response(self) -> None:
        def fake_spapi_get(**_kwargs):
            return _Resp(
                200,
                {
                    "payload": {
                        "Summary": {
                            "BuyBoxPrices": [{"LandedPrice": {"Amount": 7.10, "CurrencyCode": "GBP"}}],
                            "NumberOfOffers": [{"fulfillmentChannel": "Amazon", "OfferCount": 1}],
                        },
                        "Offers": [],
                    }
                },
            )

        with mock.patch.object(get_pricing, "spapi_get", side_effect=fake_spapi_get):
            ctx, offer_rows, detail = get_pricing.fetch_market_context_for_sku_asin(
                sku_asin_rows=[("S1", "A1")],
                marketplace_id="A1F83G8C2ARO7P",
                access_token="token",
                run_id="RUN124",
                include_offer_rows=True,
                include_detail_meta=True,
            )

        self.assertEqual(ctx["S1"]["price"], "7.1")
        self.assertEqual(len(offer_rows), 0)
        self.assertEqual(detail["A1"]["detail_status"], get_pricing.DETAIL_STATUS_EMPTY_RESPONSE)
        self.assertEqual(detail["A1"]["summary_present_flag"], "1")
        self.assertEqual(detail["A1"]["attempted_flag"], "1")


if __name__ == "__main__":
    unittest.main()
