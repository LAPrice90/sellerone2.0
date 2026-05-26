from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY_DIR = ROOT / "scripts" / "flows" / "F" / "legacy_scanner_2_1"
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

import amazonCatalogCall  # type: ignore  # noqa: E402
import hazmatCall  # type: ignore  # noqa: E402
import pricingCall  # type: ignore  # noqa: E402


class _Response:
    def __init__(self, payload: dict[str, object], *, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = ""

    def json(self) -> dict[str, object]:
        return self._payload


def test_legacy_pricing_call_sets_request_timeout(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_post(url: str, **kwargs: object) -> _Response:
        captured["url"] = url
        captured.update(kwargs)
        return _Response(
            {
                "responses": [
                    {
                        "body": {
                            "featuredBuyingOptions": [
                                {"segmentedFeaturedOffers": [{"listingPrice": {"amount": "12.34"}}]}
                            ],
                            "lowestPricedOffers": [{"offers": [{"listingPrice": {"amount": "10.00"}}]}],
                        }
                    }
                ]
            }
        )

    monkeypatch.setenv("F061_LEGACY_REQUEST_TIMEOUT_SECONDS", "7.5")
    monkeypatch.setattr(pricingCall.requests, "post", fake_post)

    result = pricingCall.get_pricing_details_for_asin("B000TEST", "token")

    assert result["buy_box_price"] == "12.34"
    assert captured["timeout"] == 7.5


def test_legacy_hazmat_call_sets_request_timeout(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_get(url: str, **kwargs: object) -> _Response:
        captured["url"] = url
        captured.update(kwargs)
        return _Response({"payload": {"isEligibleForProgram": True, "ineligibilityReasonList": []}})

    monkeypatch.setenv("F061_LEGACY_REQUEST_TIMEOUT_SECONDS", "9")
    monkeypatch.setattr(hazmatCall.requests, "get", fake_get)

    result = hazmatCall.check_eligibility_for_asin("B000TEST", "token")

    assert result["eligible"] is True
    assert captured["timeout"] == 9.0


def test_legacy_catalog_call_sets_request_timeout(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_get(url: str, **kwargs: object) -> _Response:
        captured["url"] = url
        captured.update(kwargs)
        return _Response(
            {
                "items": [
                    {
                        "asin": "B000TEST",
                        "dimensions": [{"package": {"weight": {"unit": "pounds", "value": 1.2}}}],
                        "attributes": {"brand": [{"value": "Brand"}]},
                        "salesRanks": [{"displayGroupRanks": [{"rank": 123}]}],
                        "summaries": [{"releaseDate": "2025-01-01"}],
                    }
                ]
            }
        )

    monkeypatch.setenv("F061_LEGACY_REQUEST_TIMEOUT_SECONDS", "11")
    monkeypatch.setattr(amazonCatalogCall.requests, "get", fake_get)

    result = amazonCatalogCall.get_catalog_details("1234567890123", "token")

    assert result["asin"] == "B000TEST"
    assert captured["timeout"] == 11.0
