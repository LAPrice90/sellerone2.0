from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY_DIR = ROOT / "scripts" / "flows" / "F" / "legacy_scanner_2_1"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

token_call_stub = types.ModuleType("tokenCall")
token_call_stub.get_access_token = lambda: "fake-token"
sys.modules["tokenCall"] = token_call_stub

import amazonCatalogCall as amazonCatalogCall


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object] | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self) -> dict[str, object]:
        return self._payload


def test_catalog_lookup_uses_upc_identifier_type(monkeypatch) -> None:
    captured = {}

    def fake_get(url, headers=None, params=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers or {}
        captured["params"] = params or {}
        return _FakeResponse(
            200,
            {
                "items": [
                    {
                        "asin": "B00UPC1234",
                        "salesRanks": [{"displayGroupRanks": [{"rank": 1200}]}],
                        "attributes": {"brand": [{"value": "BrandOne"}]},
                        "dimensions": [{}],
                        "summaries": [{"releaseDate": "2024-01-01"}],
                    }
                ]
            },
        )

    monkeypatch.setattr(amazonCatalogCall.requests, "get", fake_get)

    result = amazonCatalogCall.get_catalog_details("123456789012", "token")

    assert result is not None
    assert result["asin"] == "B00UPC1234"
    assert "identifiersType=UPC" in captured["url"]
