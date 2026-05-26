from __future__ import annotations

import sys
from pathlib import Path

from selenium.common.exceptions import TimeoutException

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.legacy_scanner_2_1 import dropdownSelector as ds


class _FakeLogger:
    def info(self, *_args, **_kwargs):
        return None

    def warning(self, *_args, **_kwargs):
        return None

    def error(self, *_args, **_kwargs):
        return None


class _WaitAlways:
    def __init__(self, *_args, **_kwargs):
        return None

    def until(self, *_args, **_kwargs):
        return True


class _WaitTimeout:
    def __init__(self, *_args, **_kwargs):
        return None

    def until(self, *_args, **_kwargs):
        raise TimeoutException("forced-timeout")


class _DummyDriver:
    def __init__(self) -> None:
        self.visited: list[str] = []

    def get(self, url: str) -> None:
        self.visited.append(url)


def test_wait_for_filter_refresh_returns_steady_when_text_unchanged(monkeypatch) -> None:
    monkeypatch.setattr(ds, "WebDriverWait", _WaitTimeout)
    monkeypatch.setattr(ds, "_read_filter_info_text", lambda _driver: "10 customer reviews")
    state = ds._wait_for_filter_refresh(
        _DummyDriver(),
        _FakeLogger(),
        before_text="10 customer reviews",
    )
    assert state == "steady"


def test_wait_for_filter_refresh_returns_missing_when_text_empty(monkeypatch) -> None:
    monkeypatch.setattr(ds, "WebDriverWait", _WaitTimeout)
    monkeypatch.setattr(ds, "_read_filter_info_text", lambda _driver: "")
    state = ds._wait_for_filter_refresh(
        _DummyDriver(),
        _FakeLogger(),
        before_text="10 customer reviews",
    )
    assert state == "missing"


def test_variant_dropdown_soft_selected_mode_on_steady_refresh(monkeypatch) -> None:
    monkeypatch.setattr(ds, "WebDriverWait", _WaitAlways)
    monkeypatch.setattr(ds, "_reviews_page_ready", lambda _driver: True)
    monkeypatch.setattr(ds, "_read_filter_info_text", lambda _driver: "10 customer reviews")
    monkeypatch.setattr(ds, "_wait_for_filter_refresh", lambda *_args, **_kwargs: "steady")

    call_index = {"value": 0}

    def _fake_set_native_select_option(*_args, **_kwargs):
        call_index["value"] += 1
        # 1st call = variants select, 2nd call = top reviews sort.
        return True, True

    monkeypatch.setattr(ds, "_set_native_select_option", _fake_set_native_select_option)
    monkeypatch.setattr(ds, "_set_dropdown_by_label", lambda *_args, **_kwargs: False)

    result = ds.test_variant_dropdown(_DummyDriver(), "https://www.amazon.co.uk/product-reviews/B000000000")
    assert result["variant_mode"] == "selected_unconfirmed"
    assert result["all_variants_selection_success"] is True
    assert result["top_reviews_selection_success"] is True
