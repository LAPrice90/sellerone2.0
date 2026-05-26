from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.api.amazon_listings_restrictions import get_listings_restrictions


class _FakeResponse:
    status_code = 200
    text = '{"restrictions":[]}'

    def json(self) -> dict[str, object]:
        return {"restrictions": []}


def test_get_listings_restrictions_requests_asin_seller_marketplace_and_condition() -> None:
    captured: dict[str, object] = {}

    def fake_get(**kwargs):
        captured.update(kwargs)
        return _FakeResponse()

    with mock.patch("scripts.api.amazon_listings_restrictions.spapi_get", side_effect=fake_get):
        result = get_listings_restrictions(
            seller_id="SELLER1",
            asin="b000000001",
            marketplace_id="A1F83G8C2ARO7P",
            condition_type="new_new",
            access_token="token",
            reason_locale="en_GB",
            run_id="test-run",
        )

    assert result["http_status"] == "200"
    assert captured["params"]["asin"] == "B000000001"
    assert captured["params"]["sellerId"] == "SELLER1"
    assert captured["params"]["marketplaceIds"] == "A1F83G8C2ARO7P"
    assert captured["params"]["conditionType"] == "new_new"
    assert captured["params"]["reasonLocale"] == "en_GB"
    assert captured["headers"]["x-amz-access-token"] == "token"
