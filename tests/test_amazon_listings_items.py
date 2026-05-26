from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.api.amazon_listings_items import (
    VALIDATION_PREVIEW_MODE,
    build_offer_only_listing_payload,
    get_listings_item,
    preview_put_listings_item,
    submit_put_listings_item,
)


class _FakeResponse:
    status_code = 200
    text = '{"status":"ACCEPTED","issues":[]}'

    def json(self) -> dict[str, object]:
        return {"status": "ACCEPTED", "issues": []}


def _draft_row() -> dict[str, str]:
    return {
        "asin": "B000000001",
        "expected_seller_sku": "NP-SUP-12345678",
        "marketplace_id": "A1F83G8C2ARO7P",
        "product_type": "PRODUCT",
        "condition_type": "new_new",
        "fulfillment_channel": "DEFAULT",
        "starting_price_gbp": "12.34",
        "starting_quantity": "5",
        "country_of_origin": "GB",
        "product_tax_code": "A_GEN_STANDARD",
        "currency_code": "GBP",
        "price_includes_tax": "1",
    }


def test_build_offer_only_listing_payload_uses_existing_asin_offer_shape() -> None:
    payload = build_offer_only_listing_payload(_draft_row())

    assert payload["productType"] == "PRODUCT"
    assert payload["requirements"] == "LISTING_OFFER_ONLY"
    attrs = payload["attributes"]
    assert attrs["condition_type"][0]["value"] == "new_new"
    assert attrs["merchant_suggested_asin"][0]["value"] == "B000000001"
    assert attrs["country_of_origin"][0]["value"] == "GB"
    assert attrs["product_tax_code"][0]["value"] == "A_GEN_STANDARD"
    assert attrs["fulfillment_availability"][0]["fulfillment_channel_code"] == "DEFAULT"
    assert attrs["fulfillment_availability"][0]["quantity"] == 5
    assert attrs["purchasable_offer"][0]["currency"] == "GBP"
    assert attrs["purchasable_offer"][0]["our_price"][0]["schedule"][0]["value_with_tax"] == 12.34


def test_build_offer_only_listing_payload_requires_country_of_origin() -> None:
    row = _draft_row()
    row["country_of_origin"] = ""

    try:
        build_offer_only_listing_payload(row)
    except ValueError as exc:
        assert "country_of_origin" in str(exc)
    else:
        raise AssertionError("expected country_of_origin validation error")


def test_preview_put_listings_item_forces_validation_preview_mode() -> None:
    captured: dict[str, object] = {}

    def fake_put_json(**kwargs):
        captured.update(kwargs)
        return _FakeResponse()

    with mock.patch("scripts.api.amazon_listings_items.spapi_put_json", side_effect=fake_put_json):
        result = preview_put_listings_item(
            seller_id="SELLER1",
            sku="NP-SUP-12345678",
            marketplace_id="A1F83G8C2ARO7P",
            access_token="token",
            payload=build_offer_only_listing_payload(_draft_row()),
            issue_locale="en_GB",
            run_id="test-run",
        )

    assert result["http_status"] == "200"
    assert captured["params"]["mode"] == VALIDATION_PREVIEW_MODE
    assert captured["params"]["marketplaceIds"] == "A1F83G8C2ARO7P"
    assert captured["params"]["includedData"] == "issues,identifiers"
    assert json.loads(captured["body"])["requirements"] == "LISTING_OFFER_ONLY"


def test_submit_put_listings_item_omits_validation_preview_mode() -> None:
    captured: dict[str, object] = {}

    def fake_put_json(**kwargs):
        captured.update(kwargs)
        return _FakeResponse()

    with mock.patch("scripts.api.amazon_listings_items.spapi_put_json", side_effect=fake_put_json):
        result = submit_put_listings_item(
            seller_id="SELLER1",
            sku="NP-SUP-12345678",
            marketplace_id="A1F83G8C2ARO7P",
            access_token="token",
            payload=build_offer_only_listing_payload(_draft_row()),
            issue_locale="en_GB",
            run_id="test-run",
        )

    assert result["http_status"] == "200"
    assert "mode" not in captured["params"]
    assert "includedData" not in captured["params"]
    assert captured["params"]["marketplaceIds"] == "A1F83G8C2ARO7P"
    assert json.loads(captured["body"])["requirements"] == "LISTING_OFFER_ONLY"


def test_get_listings_item_requests_readback_data() -> None:
    captured: dict[str, object] = {}

    def fake_get(**kwargs):
        captured.update(kwargs)
        return _FakeResponse()

    with mock.patch("scripts.api.amazon_listings_items.spapi_get", side_effect=fake_get):
        result = get_listings_item(
            seller_id="SELLER1",
            sku="NP-SUP-12345678",
            marketplace_id="A1F83G8C2ARO7P",
            access_token="token",
            issue_locale="en_GB",
            run_id="test-run",
        )

    assert result["http_status"] == "200"
    assert captured["params"]["marketplaceIds"] == "A1F83G8C2ARO7P"
    assert "summaries" in captured["params"]["includedData"]
    assert "issues" in captured["params"]["includedData"]
