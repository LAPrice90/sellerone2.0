from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.F061_run_legacy_first_checks_local import (
    F061_BBP_PROFILE_DIR,
    F061_BBP_USER_DATA_DIR,
    F061_BROWSER_STAGE_READY_REASON,
    F061_BBP_IFRAME_PLUGIN_BLOCK_REASON,
    F061_KILL_SPECIALIST_CHROME_BEFORE_START_ENV,
    F061_STAGE_MODE_API_ONLY,
    F061_STAGE_MODE_BROWSER_ONLY,
    LegacyCompatibleAmazonAdapter,
    _apply_background_browser_options,
    _bbp_profile_extension_health,
    _background_browser_mode,
    _build_scrape_evidence_row,
    _cleanup_specialist_chrome_windows,
    _economic_pre_review_hard_stop_health_row,
    _force_clean_specialist_chrome_for_visible_login,
    _f061_row_queue_priority,
    _last_stage_for_fail_code,
    _map_scrape_error_to_status,
    _minimized_chrome_command,
    _minimized_chrome_startup_kwargs,
    _place_date_browser_window,
    _scrape_evidence_is_blocked,
    _scrape_evidence_has_bbp_iframe_plugin_block,
    _scrape_evidence_needs_login_backtrack,
    _place_browser_window,
    _pre_review_gate_health_row,
    _select_catalog_candidates_for_processing,
    _visible_chrome_command,
    _visible_bbp_chrome_startup_kwargs,
    run_legacy_first_checks_local,
)
from scripts.flows.F import F061_run_legacy_first_checks_local as f061_module
from scripts.flows.F._schemas import get_f_output_contract


@pytest.fixture(autouse=True)
def _isolate_seller_central_login_proof(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv(
        "F061_SELLER_CENTRAL_LOGIN_PROOF_PATH",
        str(tmp_path / "seller_central_login_recovery_proof.csv"),
    )


def _complete_scraped_payload(*, break_even_price: float, title: str, monthly_sold: str, rating: str, product_info: str, variant_reviews: str, reviews_text: str) -> dict[str, str]:
    return {
        "updated_break_even": f"{break_even_price:.2f}",
        "scan_date": "2026-04-07",
        "main_title": title,
        "monthly_sold": monthly_sold,
        "rating": rating,
        "product_info": product_info,
        "variant_reviews": variant_reviews,
        "reviews_text": reviews_text,
        "price_history_points_365d": "3",
        "chart_price_daily_series": "2026-04-05=19.00;2026-04-06=19.50;2026-04-07=20.00",
        "chart_raw_buy_box_daily_series": "2026-04-05=19.00;2026-04-06=19.50;2026-04-07=20.00",
        "history_source": "buyBotProSalesChart:chartjs",
        "bbp_dashboard_yes_or_no": "NO",
        "bbp_dashboard_delivery_classification": "",
        "bbp_dashboard_separate_delivery_required": "0",
    }


def test_f061_normal_mode_prioritises_rescan_retry_before_fresh_pending() -> None:
    rescan_retry = {
        "scan_status": "pending",
        "scan_reason": "rescan_retry_required",
        "completion_block_reason": "rescan_retry_pending",
        "last_attempt_utc": "2026-05-21T09:22:47Z",
    }
    fresh_pending = {
        "scan_status": "pending",
        "scan_reason": "",
        "completion_block_reason": "",
        "last_attempt_utc": "",
    }
    login_retry = {
        "scan_status": "login_backtrack_pending",
        "scan_reason": "login_backtrack_required",
        "completion_block_reason": "bbp_login_required",
    }

    assert _f061_row_queue_priority(rescan_retry, login_mode_active=False) == 0
    assert _f061_row_queue_priority(fresh_pending, login_mode_active=False) == 1
    assert _f061_row_queue_priority(login_retry, login_mode_active=False) == 2


def test_f061_marks_bbp_login_and_iframe_failures_without_false_login_backtrack() -> None:
    assert _scrape_evidence_is_blocked({"scrape_error": "BBP_LOGIN_REQUIRED"})
    assert _scrape_evidence_is_blocked({"scrape_error": "No BBP iframe"})
    assert _scrape_evidence_needs_login_backtrack({"scrape_error": "BBP_LOGIN_REQUIRED"})
    assert not _scrape_evidence_needs_login_backtrack({"scrape_error": "No BBP iframe"})
    assert _scrape_evidence_has_bbp_iframe_plugin_block({"scrape_error": "No BBP iframe"})
    assert _scrape_evidence_has_bbp_iframe_plugin_block(
        {"scrape_error": "BBP_IFRAME_PLUGIN_UNAVAILABLE:bbp_profile_extension_missing"}
    )
    assert _scrape_evidence_is_blocked(
        {"scrape_error": "The extension failed to load properly. It might not be able to intercept network requests."}
    )
    assert _scrape_evidence_needs_login_backtrack(
        {"scrape_error": "The extension failed to load properly. It might not be able to intercept network requests."}
    )
    assert _scrape_evidence_needs_login_backtrack({"scrape_error": "BBP unavailable"})
    assert not _scrape_evidence_is_blocked({"scrape_error": "LOWROI"})
    assert not _scrape_evidence_needs_login_backtrack({"scrape_error": "LOWROI"})


def test_f061_default_bbp_profile_matches_legacy_plugin_profile() -> None:
    assert F061_BBP_USER_DATA_DIR.endswith("Chrome_UC136")
    assert F061_BBP_PROFILE_DIR == "Profile 2"


def test_f061_scrape_evidence_preserves_product_page_text() -> None:
    active_row = pd.Series(
        {
            "run_id": "run-1",
            "supplier_id": "supplier-a",
            "supplier_name": "Supplier A",
            "supplier_title": "Supplier Price File Title",
            "source_seen_at_utc": "2026-05-20T09:00:00Z",
        }
    )
    first_row = {
        "candidate_id": "cand-1",
        "supplier_sku": "SKU-1",
        "barcode": "123",
        "asin": "B000000001",
        "title": "Amazon Title",
    }
    row = _build_scrape_evidence_row(
        active_row=active_row,
        first_row=first_row,
        observed_utc="2026-05-20T10:00:00Z",
        scraped_data={
            "main_title": "Amazon Title",
            "product_detail_text": "Technical details block",
            "product_description": "Each pack contains 50 card sleeves.",
            "product_feature_bullets": "Official sleeves",
        },
        scrape_success=True,
        scrape_error="",
    )

    assert row["product_detail_text"] == "Technical details block"
    assert row["product_description"] == "Each pack contains 50 card sleeves."
    assert row["product_feature_bullets"] == "Official sleeves"
    assert row["supplier_title"] == "Supplier Price File Title"


def test_webscraper_s2_prefers_exact_product_description_xpath(monkeypatch) -> None:
    legacy_dir = SCRIPTS_DIR / "flows" / "F" / "legacy_scanner_2_1"
    if str(legacy_dir) not in sys.path:
        sys.path.insert(0, str(legacy_dir))

    import WebscraperS2 as webscraper_s2

    captured_locator_batches: list[list[tuple[Any, str]]] = []

    def fake_read_text_with_fallback(driver, locators, **kwargs):
        captured_locator_batches.append(list(locators))
        return "Each pack contains 50 card sleeves." if len(captured_locator_batches) == 1 else "Official sleeves"

    monkeypatch.setattr(webscraper_s2, "read_text_with_fallback", fake_read_text_with_fallback)

    result = webscraper_s2.read_product_page_text_evidence(object(), "Technical details block")

    assert captured_locator_batches[0][0] == (
        webscraper_s2.By.XPATH,
        '//*[@id="productDescription"]/p[1]/span',
    )
    assert result["product_description"] == "Each pack contains 50 card sleeves."
    assert result["product_feature_bullets"] == "Official sleeves"


def test_webscraper_s2_reads_textcontent_when_element_text_is_blank(monkeypatch) -> None:
    legacy_dir = SCRIPTS_DIR / "flows" / "F" / "legacy_scanner_2_1"
    if str(legacy_dir) not in sys.path:
        sys.path.insert(0, str(legacy_dir))

    import WebscraperS2 as webscraper_s2

    class FakeElement:
        text = ""

        def get_attribute(self, name: str) -> str:
            if name == "textContent":
                return "Each pack contains 50 card sleeves."
            return ""

    class FakeDriver:
        def execute_script(self, script: str, element: FakeElement) -> str:
            return ""

    class FakeWait:
        def __init__(self, driver: FakeDriver, wait_seconds: float) -> None:
            self.driver = driver
            self.wait_seconds = wait_seconds

        def until(self, condition: Any) -> FakeElement:
            return FakeElement()

    monkeypatch.setattr(webscraper_s2, "WebDriverWait", FakeWait)
    monkeypatch.setattr(webscraper_s2.time, "sleep", lambda *_args, **_kwargs: None)

    text = webscraper_s2.read_text_with_fallback(
        FakeDriver(),
        [(webscraper_s2.By.CSS_SELECTOR, "#productDescription")],
        wait_seconds=0,
        attempts=1,
    )

    assert text == "Each pack contains 50 card sleeves."


def test_f061_bbp_profile_health_detects_buybotpro_extension(tmp_path: Path) -> None:
    manifest = tmp_path / "Chrome_UC136" / "BBPProfile" / "Extensions" / "abc" / "1.0_0" / "manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        '{"name":"BuyBotPro - Amazon FBA Deal Analyzer","description":"Analyze Amazon FBA deals"}',
        encoding="utf-8",
    )

    health = _bbp_profile_extension_health(str(tmp_path / "Chrome_UC136"), "BBPProfile")

    assert health["ok"] is True
    assert health["extension_id"] == "abc"


def test_f061_bbp_profile_health_blocks_profile_without_buybotpro(tmp_path: Path) -> None:
    manifest = tmp_path / "Chrome_UC136" / "BBPProfile" / "Extensions" / "abc" / "1.0_0" / "manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text('{"name":"PDF Viewer"}', encoding="utf-8")

    health = _bbp_profile_extension_health(str(tmp_path / "Chrome_UC136"), "BBPProfile")

    assert health["ok"] is False
    assert health["reason"] == "buybotpro_extension_missing"


def test_f061_bbp_profile_failure_is_treated_as_plugin_unavailable(tmp_path: Path) -> None:
    adapter = LegacyCompatibleAmazonAdapter(legacy_scanner_root=None, root_path=tmp_path)
    adapter._driver_init_error = "bbp_profile_extension_missing:user_data_dir=x;profile_dir=y;reason=z"

    response = adapter._driver_start_failure_response()

    assert response["success"] is False
    assert str(response["error"]).startswith("BBP_IFRAME_PLUGIN_UNAVAILABLE:bbp_profile_extension_missing")


def test_f061_specialist_cleanup_default_preserves_profile_session(monkeypatch) -> None:
    calls: list[object] = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("cleanup should not run by default")

    monkeypatch.setattr(f061_module.os, "name", "nt")
    monkeypatch.delenv(F061_KILL_SPECIALIST_CHROME_BEFORE_START_ENV, raising=False)
    monkeypatch.setattr(f061_module.subprocess, "run", fake_run)

    result = _cleanup_specialist_chrome_windows()

    assert result["cleanup_attempted"] is False
    assert result["cleanup_reason"] == "disabled_by_env"
    assert calls == []


def test_f061_specialist_cleanup_force_overrides_session_preserving_default(monkeypatch) -> None:
    class Completed:
        stdout = '{"cleanup_attempted":true,"killed_count":0,"killed_ids":[]}'
        stderr = ""
        returncode = 0

    calls: list[object] = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return Completed()

    monkeypatch.setattr(f061_module.os, "name", "nt")
    monkeypatch.delenv(F061_KILL_SPECIALIST_CHROME_BEFORE_START_ENV, raising=False)
    monkeypatch.setattr(f061_module.subprocess, "run", fake_run)

    result = _cleanup_specialist_chrome_windows(force=True)

    assert result["cleanup_attempted"] is True
    assert result["killed_count"] == 0
    assert len(calls) == 1


class _FakeAdapter:
    def __init__(self) -> None:
        self.token_calls = 0
        self.scrape_skip_date_flags: list[bool] = []

    def get_access_token(self) -> str:
        self.token_calls += 1
        return "fake-token"

    def get_catalog_details(self, barcode: str, access_token: str):
        if barcode == "1111111111111":
            return {
                "asin": "ASIN111111",
                "rank": 12000,
                "brand": "BrandOne",
                "dimensions": {
                    "height": {"value": 1.0},
                    "width": {"value": 2.0},
                    "length": {"value": 3.0},
                },
                "weight": 1.0,
                "release_date": "2020-01-01",
            }
        if barcode == "3333333333333":
            return {
                "asin": "ASIN333333",
                "rank": 60001,
                "brand": "BrandThree",
                "dimensions": {},
                "weight": 0.2,
                "release_date": "2021-01-01",
            }
        return None

    def check_hazmat(self, asin: str, access_token: str):
        return {"asin": asin, "eligible": True}

    def get_pricing(self, asin: str, access_token: str):
        return {"asin": asin, "buy_box_price": "20.00", "lowest_afn_price": "19.50"}

    def get_fees(self, asin: str, final_price: float, access_token: str):
        return {"asin": asin, "referral_fee": 3.0, "fba_fee": 4.0}

    def process_scrape(
        self,
        *,
        asin: str,
        break_even_price: float,
        min_sell_price: float,
        product_cost: float,
        row_index: int,
        brand_name: str,
        vat_rate: float,
        skip_date_scraping: bool,
        old_chrome_forced: bool,
    ):
        self.scrape_skip_date_flags.append(bool(skip_date_scraping))
        return {
            "success": True,
            "scraped_data": _complete_scraped_payload(
                break_even_price=break_even_price,
                title="Resolved Listing",
                monthly_sold="42",
                rating="4.4",
                product_info="2020-01-01",
                variant_reviews="12",
                reviews_text="8",
            ),
        }


class _CountingFakeAdapter(_FakeAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.catalog_calls = 0
        self.hazmat_calls = 0
        self.pricing_calls = 0
        self.fees_calls = 0

    def get_catalog_details(self, barcode: str, access_token: str):
        self.catalog_calls += 1
        return super().get_catalog_details(barcode, access_token)

    def check_hazmat(self, asin: str, access_token: str):
        self.hazmat_calls += 1
        return super().check_hazmat(asin, access_token)

    def get_pricing(self, asin: str, access_token: str):
        self.pricing_calls += 1
        return super().get_pricing(asin, access_token)

    def get_fees(self, asin: str, final_price: float, access_token: str):
        self.fees_calls += 1
        return super().get_fees(asin, final_price, access_token)


class _LoginRequiredAdapter(_FakeAdapter):
    def process_scrape(self, **kwargs):
        return {"success": False, "error": "BBP_LOGIN_REQUIRED", "scraped_data": {}}


class _BbpExtensionUnavailableAdapter(_FakeAdapter):
    def process_scrape(self, **kwargs):
        return {
            "success": False,
            "error": "The extension failed to load properly. It might not be able to intercept network requests.",
            "scraped_data": {},
        }


class _MissingDashboardYesNoAdapter(_FakeAdapter):
    def process_scrape(self, **kwargs):
        payload = _complete_scraped_payload(
            break_even_price=18.22,
            title="Resolved Listing Missing Dashboard Yes No",
            monthly_sold="42",
            rating="4.4",
            product_info="2020-01-01",
            variant_reviews="12",
            reviews_text="8",
        )
        payload["bbp_dashboard_yes_or_no"] = ""
        payload["bbp_dashboard_delivery_classification"] = ""
        payload["bbp_dashboard_separate_delivery_required"] = "0"
        return {"success": True, "scraped_data": payload}


class _LikelyDashboardAdapter(_FakeAdapter):
    def process_scrape(self, **kwargs):
        payload = _complete_scraped_payload(
            break_even_price=18.22,
            title="Resolved Listing Likely Dashboard",
            monthly_sold="42",
            rating="4.4",
            product_info="2020-01-01",
            variant_reviews="12",
            reviews_text="8",
        )
        payload["bbp_dashboard_yes_or_no"] = "LIKELY"
        payload["bbp_dashboard_delivery_classification"] = "LIKELY_SELLABLE_HAZMAT_SEPARATE_DELIVERY"
        payload["bbp_dashboard_separate_delivery_required"] = "1"
        return {"success": True, "scraped_data": payload}


class _HardFailMissingDashboardAdapter(_FakeAdapter):
    def process_scrape(self, **kwargs):
        payload = _complete_scraped_payload(
            break_even_price=18.22,
            title="Weak Listing Missing Dashboard",
            monthly_sold="1",
            rating="3.0",
            product_info="2020-01-01",
            variant_reviews="0",
            reviews_text="0",
        )
        payload["bbp_dashboard_yes_or_no"] = ""
        payload["bbp_dashboard_delivery_classification"] = ""
        payload["bbp_dashboard_separate_delivery_required"] = "0"
        payload["bbp_monthly_sales_current"] = "1"
        return {"success": True, "scraped_data": payload}


class _BacktrackSuccessDifferentPriceAdapter(_FakeAdapter):
    def get_pricing(self, asin: str, access_token: str):
        return {"asin": asin, "buy_box_price": "44.00", "lowest_afn_price": "43.00"}

    def process_scrape(self, **kwargs):
        payload = _complete_scraped_payload(
            break_even_price=18.22,
            title="Resolved Backtrack Listing",
            monthly_sold="42",
            rating="4.4",
            product_info="2020-01-01",
            variant_reviews="12",
            reviews_text="8",
        )
        payload.update(
            {
                "bbp_dashboard_yes_or_no": "NO",
                "bbp_top_seller_names": "Seller One|Seller Two",
                "bbp_top_seller_count": "2",
                "bbp_brand_match_seller": "Seller One",
                "bbp_brand_match_score": "0.9",
                "bbp_brand_match_flag": "True",
            }
        )
        return {"success": True, "scraped_data": payload}


class _FakeChromeOptions:
    def __init__(self) -> None:
        self.arguments: list[str] = []

    def add_argument(self, value: str) -> None:
        self.arguments.append(value)


class _FakeDriver:
    def __init__(self, *, minimize_fails: bool = False, rect_fails: bool = False) -> None:
        self.minimize_fails = minimize_fails
        self.rect_fails = rect_fails
        self.minimized = False
        self.maximized = False
        self.positions: list[tuple[int, int]] = []
        self.sizes: list[tuple[int, int]] = []
        self.rects: list[tuple[int, int, int, int]] = []
        self.cdp_calls: list[tuple[str, dict[str, object]]] = []
        self.current_url = "https://www.amazon.co.uk/dp/B000TEST"

    def minimize_window(self) -> None:
        if self.minimize_fails:
            raise RuntimeError("minimize failed")
        self.minimized = True

    def maximize_window(self) -> None:
        self.maximized = True

    def set_window_position(self, x: int, y: int) -> None:
        self.positions.append((x, y))

    def set_window_size(self, width: int, height: int) -> None:
        self.sizes.append((width, height))

    def set_window_rect(self, *, x: int, y: int, width: int, height: int) -> None:
        if self.rect_fails:
            raise RuntimeError("rect failed")
        self.rects.append((x, y, width, height))

    def execute_cdp_cmd(self, command: str, params: dict[str, object]) -> dict[str, object]:
        self.cdp_calls.append((command, params))
        if command == "Browser.getWindowForTarget":
            return {"windowId": 7}
        if command == "Target.getTargets":
            return {
                "targetInfos": [
                    {
                        "targetId": "target-1",
                        "type": "page",
                        "url": "https://www.amazon.co.uk/dp/B000TEST",
                    }
                ]
            }
        return {}


def test_background_browser_mode_defaults_to_minimized(monkeypatch) -> None:
    monkeypatch.delenv("F061_BACKGROUND_BROWSER_MODE", raising=False)

    options = _FakeChromeOptions()
    _apply_background_browser_options(options)

    assert _background_browser_mode() == "minimized"
    assert "--start-minimized" in options.arguments
    assert "--window-position=-32000,-32000" in options.arguments


def test_background_browser_mode_self_promotes_for_exhausted_email_continue(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "minimized")
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    monkeypatch.setenv("F061_SELLER_CENTRAL_LOGIN_PROOF_PATH", str(proof_path))
    pd.DataFrame(
        [
            {
                "observed_utc": "2026-06-07T21:29:30Z",
                "context": "dashboard_yes_no_login",
                "status": "failed",
                "reason": "email_continue_not_advanced",
                "seller_central_signin_detected": "1",
                "seller_central_otp_detected": "0",
                "notes": (
                    "page_hint=sellercentral_url|signin_url|email_field|continue_button;"
                    "email_finalize=1;click=1;js_click=1;enter=0;js_enter=1;"
                    "form_submit=1;email_value=present"
                ),
            }
        ]
    ).to_csv(proof_path, index=False)

    options = _FakeChromeOptions()
    driver = _FakeDriver()
    _apply_background_browser_options(options)
    _place_browser_window(driver, visible_x=10, visible_y=20)

    assert _background_browser_mode() == "visible"
    assert options.arguments == ["--window-size=1400,900", "--window-position=80,80"]
    assert driver.rects == [(10, 20, 1400, 900)]


def test_background_browser_visible_mode_keeps_requested_window(monkeypatch) -> None:
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "visible")

    options = _FakeChromeOptions()
    driver = _FakeDriver()
    _apply_background_browser_options(options)
    _place_browser_window(driver, visible_x=10, visible_y=20)

    assert options.arguments == ["--window-size=1400,900", "--window-position=80,80"]
    assert driver.maximized is False
    assert driver.cdp_calls[0] == ("Browser.getWindowForTarget", {})
    assert driver.cdp_calls[1] == (
        "Browser.setWindowBounds",
        {
            "windowId": 7,
            "bounds": {
                "windowState": "normal",
                "left": 10,
                "top": 20,
                "width": 1400,
                "height": 900,
            },
        },
    )
    assert driver.rects == [(10, 20, 1400, 900)]
    assert ("Target.activateTarget", {"targetId": "target-1"}) in driver.cdp_calls
    assert ("Page.bringToFront", {}) in driver.cdp_calls
    assert driver.positions == []
    assert driver.sizes == []


def test_visible_bbp_chrome_startup_forces_normal_show_state(monkeypatch) -> None:
    monkeypatch.setattr(f061_module.os, "name", "nt")
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "visible")

    kwargs = _visible_bbp_chrome_startup_kwargs(
        [r"C:\Chrome_UC136\bin\chrome.exe", r"--user-data-dir=C:\Users\Luke\AppData\Local\Chrome_UC136"],
        {"creationflags": getattr(f061_module.subprocess, "CREATE_NO_WINDOW", 0)},
    )

    startupinfo = kwargs.get("startupinfo")
    assert startupinfo is not None
    assert startupinfo.dwFlags & f061_module.subprocess.STARTF_USESHOWWINDOW
    assert startupinfo.wShowWindow == 1
    assert int(kwargs.get("creationflags", 0)) & getattr(f061_module.subprocess, "CREATE_NO_WINDOW", 0) == 0


def test_visible_chrome_command_removes_stale_tiny_or_maximized_bounds(monkeypatch) -> None:
    monkeypatch.setattr(f061_module.os, "name", "nt")
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "visible")

    command = _visible_chrome_command(
        [
            r"C:\Chrome_UC136\bin\chrome.exe",
            r"--user-data-dir=C:\Users\Luke\AppData\Local\Chrome_UC136",
            "--profile-directory=Profile 2",
            "--start-maximized",
            "--window-position=-32000,-32000",
            "--window-size=300,200",
        ]
    )

    assert "--start-maximized" not in command
    assert "--window-position=-32000,-32000" not in command
    assert "--window-size=300,200" not in command
    assert command[-2:] == ["--window-position=80,80", "--window-size=1400,900"]


def test_minimized_specialist_chrome_strips_maximized_launch(monkeypatch) -> None:
    monkeypatch.setattr(f061_module.os, "name", "nt")
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "minimized")

    command = _minimized_chrome_command(
        [
            r"C:\Chrome_UC136\bin\chrome.exe",
            "--start-minimized",
            "--window-position=80,80",
            "--start-maximized",
            r"--user-data-dir=C:\Users\Luke\AppData\Local\Chrome_UC136",
        ]
    )

    assert "--start-maximized" not in command
    assert "--window-position=80,80" not in command
    assert command[-2:] == ["--start-minimized", "--window-position=-32000,-32000"]

    kwargs = _minimized_chrome_startup_kwargs(command, {})
    startupinfo = kwargs.get("startupinfo")
    assert startupinfo is not None
    assert startupinfo.dwFlags & f061_module.subprocess.STARTF_USESHOWWINDOW
    assert startupinfo.wShowWindow == 6


def test_email_continue_exhaustion_promotes_child_env_and_stops_hider(monkeypatch, tmp_path: Path) -> None:
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    pd.DataFrame(
        [
            {
                "observed_utc": "2026-06-07T22:07:06Z",
                "context": "dashboard_yes_no_login",
                "status": "failed",
                "reason": "email_continue_not_advanced",
                "seller_central_signin_detected": "1",
                "seller_central_otp_detected": "0",
                "notes": (
                    "page_hint=sellercentral_url|signin_url|email_field|continue_button;"
                    "email_finalize=1;click=1;js_click=1;enter=0;js_enter=1;"
                    "form_submit=1;email_value=present"
                ),
            }
        ]
    ).to_csv(proof_path, index=False)
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        del kwargs
        calls.append(command)

    monkeypatch.setenv("F061_SELLER_CENTRAL_LOGIN_PROOF_PATH", str(proof_path))
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "minimized")
    monkeypatch.setenv("F061_SHOW_WINDOWS", "0")
    monkeypatch.setenv("FPM_LIVE_HIDE_SCRAPER_WINDOWS", "1")
    monkeypatch.setattr(f061_module.os, "name", "nt")
    monkeypatch.setattr(f061_module, "_F061_VISIBLE_LOGIN_HIDER_STOP_ATTEMPTED", False)
    monkeypatch.setattr(f061_module.subprocess, "run", fake_run)

    assert _background_browser_mode() == "visible"
    assert f061_module.os.environ["F061_BACKGROUND_BROWSER_MODE"] == "visible"
    assert f061_module.os.environ["F061_SHOW_WINDOWS"] == "1"
    assert f061_module.os.environ["FPM_LIVE_HIDE_SCRAPER_WINDOWS"] == "0"
    assert calls
    assert "f_hide_scraper_windows.ps1" in " ".join(str(part) for part in calls[0])


def test_visible_login_mode_preserves_specialist_chrome_by_default(monkeypatch) -> None:
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "visible")
    monkeypatch.setenv("F061_LOGIN_MODE", "1")
    monkeypatch.delenv("F061_FORCE_CLEAN_SPECIALIST_CHROME_FOR_LOGIN", raising=False)

    assert _force_clean_specialist_chrome_for_visible_login() is False


def test_visible_login_mode_cleanup_requires_explicit_recovery_flag(monkeypatch) -> None:
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "visible")
    monkeypatch.setenv("F061_LOGIN_MODE", "1")
    monkeypatch.setenv("F061_FORCE_CLEAN_SPECIALIST_CHROME_FOR_LOGIN", "1")

    assert _force_clean_specialist_chrome_for_visible_login() is True


def test_normal_visible_mode_preserves_specialist_chrome(monkeypatch) -> None:
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "visible")
    monkeypatch.delenv("F061_LOGIN_MODE", raising=False)

    assert _force_clean_specialist_chrome_for_visible_login() is False


def test_login_mode_keeps_date_support_browser_hidden(monkeypatch) -> None:
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "visible")
    monkeypatch.setenv("F061_LOGIN_MODE", "1")

    driver = _FakeDriver()
    _place_date_browser_window(driver)

    assert driver.minimized is True
    assert driver.positions == []
    assert driver.sizes == []


def test_background_browser_minimized_falls_back_offscreen(monkeypatch) -> None:
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "minimized")

    driver = _FakeDriver(minimize_fails=True, rect_fails=True)
    _place_browser_window(driver, visible_x=10, visible_y=20)

    assert driver.cdp_calls[0] == ("Browser.getWindowForTarget", {})
    assert driver.cdp_calls[1] == (
        "Browser.setWindowBounds",
        {
            "windowId": 7,
            "bounds": {
                "windowState": "normal",
                "left": -32000,
                "top": -32000,
                "width": 1280,
                "height": 720,
            },
        },
    )
    assert driver.cdp_calls[2] == (
        "Browser.setWindowBounds",
        {
            "windowId": 7,
            "bounds": {"windowState": "minimized"},
        },
    )
    assert driver.positions == [(-32000, -32000)]
    assert driver.sizes == [(1280, 720)]


class _FakeMultiCatalogAdapter:
    def __init__(self, candidates_by_barcode: dict[str, list[dict[str, object]]]) -> None:
        self._candidates_by_barcode = candidates_by_barcode
        self.token_calls = 0
        self.scrape_calls = 0

    def get_access_token(self) -> str:
        self.token_calls += 1
        return "fake-token"

    def get_catalog_candidates(self, barcode: str, access_token: str):
        return self._candidates_by_barcode.get(barcode, [])

    def check_hazmat(self, asin: str, access_token: str):
        return {"asin": asin, "eligible": True}

    def get_pricing(self, asin: str, access_token: str):
        return {"asin": asin, "buy_box_price": "40.00", "lowest_afn_price": "39.00"}

    def get_fees(self, asin: str, final_price: float, access_token: str):
        return {"asin": asin, "referral_fee": 6.0, "fba_fee": 4.5}

    def process_scrape(
        self,
        *,
        asin: str,
        break_even_price: float,
        min_sell_price: float,
        product_cost: float,
        row_index: int,
        brand_name: str,
        vat_rate: float,
        skip_date_scraping: bool,
        old_chrome_forced: bool,
    ):
        self.scrape_calls += 1
        return {
            "success": True,
            "scraped_data": _complete_scraped_payload(
                break_even_price=break_even_price,
                title=f"Resolved {asin}",
                monthly_sold="12",
                rating="4.4",
                product_info="2020-01-01",
                variant_reviews="20",
                reviews_text="9",
            ),
        }


def test_pre_review_kill_errors_map_to_specific_fail_statuses() -> None:
    assert _map_scrape_error_to_status("LOWROI") == "LOWROI"
    assert _map_scrape_error_to_status("NO_PRICE_HISTORY_365D") == "PRICEHISTORYFAIL"
    assert _map_scrape_error_to_status("LOW_SALES_CAPITAL_IDLE_RISK") == "LOWSALESFAIL"
    assert _map_scrape_error_to_status("DASHBOARD_NO_LOW_SELLER_COUNT") == "SELLERHISTORYFAIL"
    assert _last_stage_for_fail_code(fail_code="LOWROI", pf_value="FAIL") == "webscrape"
    assert _last_stage_for_fail_code(fail_code="RESCAN", pf_value="FAIL") == "retry"
    assert _last_stage_for_fail_code(fail_code="PRICEHISTORYFAIL", pf_value="FAIL") == "webscrape"
    assert _last_stage_for_fail_code(fail_code="LOWSALESFAIL", pf_value="FAIL") == "webscrape"
    assert _last_stage_for_fail_code(fail_code="SELLERHISTORYFAIL", pf_value="FAIL") == "webscrape"


def test_pre_review_gate_health_warns_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("F061_PRE_REVIEW_KILL_GATE", "0")
    row = _pre_review_gate_health_row(
        observed_utc="2026-04-29T12:00:00Z",
        source_path=Path("out/systems/F/live/feeder_legacy_scrape_evidence_live.csv"),
    )
    assert row["check"] == "feeder_pre_review_kill_gate_runtime"
    assert row["status"] == "warn"
    assert row["value"] == "disabled"


def test_economic_pre_review_hard_stop_health_warns_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("F061_ECONOMIC_PRE_REVIEW_HARD_STOP", "0")
    row = _economic_pre_review_hard_stop_health_row(
        observed_utc="2026-04-30T09:00:00Z",
        source_path=Path("out/systems/F/live/feeder_legacy_scrape_evidence_live.csv"),
    )

    assert row["check"] == "feeder_economic_pre_review_hard_stop_runtime"
    assert row["status"] == "warn"
    assert row["value"] == "disabled"


def _write_contract(root: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
    contract = get_f_output_contract(contract_name)
    columns = [*contract.required_columns, *contract.optional_columns]
    df = pd.DataFrame(rows)
    for column in columns:
        if column not in df.columns:
            df[column] = ""
    out = df[columns]
    path = root / contract.rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)


def test_f061_runs_legacy_status_sequence_and_updates_run_state(tmp_path: Path) -> None:
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "rk_1",
                "supplier_sku": "S1",
                "barcode": "1111111111111",
                "supplier_title": "First Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            },
            {
                "run_id": "run_1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "rk_2",
                "supplier_sku": "S2",
                "barcode": "2222222222222",
                "supplier_title": "Second Product",
                "unit_cost": "6.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            },
            {
                "run_id": "run_1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "rk_3",
                "supplier_sku": "S3",
                "barcode": "3333333333333",
                "supplier_title": "Third Product",
                "unit_cost": "7.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            },
        ],
    )

    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "run_id": "run_1",
                "run_status": "running",
                "source_url": "https://aux.shure-cosmetics.co.uk/pricelist/",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
                "normalized_utc": "2026-04-07T10:00:00Z",
                "total_rows": "3",
                "pending_rows": "3",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-04-07T10:00:00Z",
                "completed_at_utc": "",
            }
        ],
    )

    _write_contract(tmp_path, "feeder_legacy_first_checks_live", [])

    adapter = _FakeAdapter()
    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        max_rows=10,
        scan_utc="2026-04-07T12:00:00Z",
        adapter=adapter,
    )

    assert summary["status"] == "success"
    assert summary["processed_rows"] == 3
    assert summary["pass_rows"] == 1
    assert summary["fail_rows"] == 2
    assert summary["pending_rows"] == 0

    active_path = tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path
    active_df = pd.read_csv(active_path, dtype=str).fillna("")
    assert active_df.empty

    first_checks_path = tmp_path / get_f_output_contract("feeder_legacy_first_checks_live").rel_path
    first_df = pd.read_csv(first_checks_path, dtype=str).fillna("")
    assert int((first_df["pf"] == "PASS").sum()) == 1
    assert int((first_df["pf"] == "FAIL").sum()) == 0

    screening_state_path = tmp_path / get_f_output_contract("f_screening_row_state_live").rel_path
    screening_state_df = pd.read_csv(screening_state_path, dtype=str).fillna("")
    assert int((screening_state_df["row_status"] == "pass").sum()) == 1
    assert int((screening_state_df["row_status"] == "timeout").sum()) == 2
    assert set(screening_state_df["mode"].tolist()) == {"screening"}
    assert set(screening_state_df["attempt_count"].tolist()) == {"1"}
    timeout_rows = screening_state_df[screening_state_df["row_status"] == "timeout"].copy()
    assert set(timeout_rows["fail_code"].tolist()) == {"NOASIN", "OVER50K"}
    assert set(timeout_rows["last_stage"].tolist()) == {"catalog", "rank_gate"}
    assert all(value.endswith("Z") for value in timeout_rows["timeout_until_utc"].tolist())
    timeout_by_code = timeout_rows.set_index("fail_code")["timeout_until_utc"].to_dict()
    assert timeout_by_code["NOASIN"] == "2026-07-06T12:00:00Z"
    assert timeout_by_code["OVER50K"] == "2026-07-06T12:00:00Z"

    run_state_path = tmp_path / get_f_output_contract("supplier_price_list_run_state").rel_path
    run_state_df = pd.read_csv(run_state_path, dtype=str).fillna("")
    assert run_state_df.iloc[0]["run_status"] == "completed"
    assert run_state_df.iloc[0]["pending_rows"] == "0"
    assert run_state_df.iloc[0]["done_rows"] == "3"
    assert run_state_df.iloc[0]["failed_rows"] == "2"
    assert adapter.token_calls == 3
    assert adapter.scrape_skip_date_flags == [True]
    assert summary["scanner_speed_ledger_rows"] == 3
    assert summary["scanner_speed_browser_blocked_rows"] == 0

    speed_path = tmp_path / get_f_output_contract("f_scanner_speed_ledger_live").rel_path
    speed_df = pd.read_csv(speed_path, dtype=str).fillna("")
    assert len(speed_df) == 3
    assert set(speed_df["run_id"].tolist()) == {"run_1"}
    assert set(speed_df["supplier_id"].tolist()) == {"shure_cosmetics"}
    assert set(speed_df["candidate_id"].tolist()) == {"rk_1", "rk_2", "rk_3"}
    assert set(speed_df["browser_attempted_flag"].tolist()) == {"0", "1"}
    assert set(speed_df["browser_blocked_flag"].tolist()) == {"0"}

    health_path = tmp_path / get_f_output_contract("feeder_legacy_sheet_health").rel_path
    health_df = pd.read_csv(health_path, dtype=str).fillna("")
    assert "f_scanner_speed_ledger_runtime" in set(health_df["check"].tolist())
    assert "f_scanner_speed_bottleneck_runtime" in set(health_df["check"].tolist())
    assert "f_scanner_timeout_policy_known_codes" in set(health_df["check"].tolist())
    assert "f_scanner_timeout_policy_fallback_fail" in set(health_df["check"].tolist())
    timeout_policy_path = tmp_path / "config" / "feeder" / "f_scanner_timeout_policy.csv"
    assert timeout_policy_path.exists()


def test_f061_allowlist_processes_only_selected_candidate_rows(tmp_path: Path) -> None:
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "rk_1",
                "supplier_sku": "S1",
                "barcode": "1111111111111",
                "supplier_title": "First Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            },
            {
                "run_id": "run_1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "rk_2",
                "supplier_sku": "S2",
                "barcode": "1111111111111",
                "supplier_title": "Second Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            },
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "run_id": "run_1",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
                "normalized_utc": "2026-04-07T10:00:00Z",
                "total_rows": "2",
                "pending_rows": "2",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-04-07T10:00:00Z",
                "completed_at_utc": "",
            }
        ],
    )
    _write_contract(tmp_path, "feeder_legacy_first_checks_live", [])
    allowlist_path = tmp_path / "browser_input.csv"
    pd.DataFrame([{"candidate_id": "rk_1"}]).to_csv(allowlist_path, index=False)

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        max_rows=10,
        scan_utc="2026-04-07T12:00:00Z",
        adapter=_FakeAdapter(),
        allowlist_path=allowlist_path,
    )

    assert summary["status"] == "success"
    assert summary["processed_rows"] == 1
    assert summary["allowlist_status"] == "loaded"
    assert summary["allowlist_selected_rows"] == 1
    active_path = tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path
    active_df = pd.read_csv(active_path, dtype=str).fillna("")
    assert active_df["row_key"].tolist() == ["rk_2"]


def test_f061_api_only_marks_browser_ready_without_scrape(tmp_path: Path) -> None:
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "rk_1",
                "supplier_sku": "S1",
                "barcode": "1111111111111",
                "supplier_title": "First Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            }
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "run_id": "run_1",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
                "normalized_utc": "2026-04-07T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-04-07T10:00:00Z",
                "completed_at_utc": "",
            }
        ],
    )
    _write_contract(tmp_path, "feeder_legacy_first_checks_live", [])
    adapter = _CountingFakeAdapter()

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        max_rows=10,
        scan_utc="2026-04-07T12:00:00Z",
        adapter=adapter,
        stage_mode=F061_STAGE_MODE_API_ONLY,
    )

    assert summary["status"] == "success"
    assert summary["stage_mode"] == F061_STAGE_MODE_API_ONLY
    assert summary["processed_rows"] == 1
    assert summary["browser_stage_ready_rows"] == 1
    assert summary["scrape_attempted_rows"] == 0
    assert adapter.scrape_skip_date_flags == []

    active_path = tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path
    active_df = pd.read_csv(active_path, dtype=str).fillna("")
    assert active_df.iloc[0]["scan_status"] == "pending"
    assert active_df.iloc[0]["scan_reason"] == F061_BROWSER_STAGE_READY_REASON

    first_path = tmp_path / get_f_output_contract("feeder_legacy_first_checks_live").rel_path
    first_df = pd.read_csv(first_path, dtype=str).fillna("")
    assert first_df.iloc[0]["candidate_id"] == "rk_1"
    assert first_df.iloc[0]["status_reason"] == F061_BROWSER_STAGE_READY_REASON
    assert first_df.iloc[0]["asin"] == "ASIN111111"


def test_f061_api_only_skips_existing_browser_ready_rows(tmp_path: Path) -> None:
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "rk_1",
                "supplier_sku": "S1",
                "barcode": "1111111111111",
                "supplier_title": "First Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": F061_BROWSER_STAGE_READY_REASON,
                "attempt_count": "1",
                "last_attempt_utc": "2026-04-07T12:00:00Z",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            }
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "run_id": "run_1",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
                "normalized_utc": "2026-04-07T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-04-07T10:00:00Z",
                "completed_at_utc": "",
            }
        ],
    )
    _write_contract(tmp_path, "feeder_legacy_first_checks_live", [])
    adapter = _CountingFakeAdapter()

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        max_rows=10,
        scan_utc="2026-04-07T12:05:00Z",
        adapter=adapter,
        stage_mode=F061_STAGE_MODE_API_ONLY,
    )

    assert summary["processed_rows"] == 0
    assert adapter.token_calls == 0
    assert adapter.catalog_calls == 0


def test_f061_browser_only_uses_existing_api_evidence_without_api_calls(tmp_path: Path) -> None:
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "rk_1",
                "supplier_sku": "S1",
                "barcode": "1111111111111",
                "supplier_title": "First Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": F061_BROWSER_STAGE_READY_REASON,
                "attempt_count": "1",
                "last_attempt_utc": "2026-04-07T12:00:00Z",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            }
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "run_id": "run_1",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
                "normalized_utc": "2026-04-07T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-04-07T10:00:00Z",
                "completed_at_utc": "",
            }
        ],
    )
    _write_contract(
        tmp_path,
        "feeder_legacy_first_checks_live",
        [
            {
                "completed": "S1",
                "barcode": "1111111111111",
                "cost": "5.00",
                "vat": "20",
                "supplier": "Shure Cosmetics",
                "asin": "ASIN111111",
                "main_rank": "12000",
                "start_date": "2020-01-01",
                "brand": "BrandOne",
                "size_1": "25",
                "size_2": "51",
                "size_3": "76",
                "weight": "453.59",
                "dg_ok": "Yes",
                "hazmat": "Yes",
                "buy_box_price": "20.00",
                "lowest_afn_price": "19.50",
                "lowest_mfn_price": "",
                "reasonable_price": "20.00",
                "api_live_price": "20.00",
                "bbp_live_sell_price": "",
                "bbp_30d_avg_price": "",
                "fba_fee": "4.00",
                "referral_fee": "3.00",
                "digital_fee": "0.14",
                "est_shipping": "0.09",
                "vat_adjusted_price": "16.67",
                "break_even": "12.00",
                "min_sell_price": "14.40",
                "scan_day": "2026-04-07T12:00:00Z",
                "title": "First Product",
                "sales": "",
                "rating": "",
                "date": "",
                "variant_reviews": "",
                "reviews_list": "",
                "point_score": "",
                "history_score": "100|LIKELY|seeded",
                "pf": "",
                "status_reason": F061_BROWSER_STAGE_READY_REASON,
                "candidate_id": "rk_1",
                "supplier_sku": "S1",
                "recommendation_status": "",
                "recommended_test_qty": "",
            }
        ],
    )
    allowlist_path = tmp_path / "browser_input.csv"
    pd.DataFrame([{"candidate_id": "rk_1"}]).to_csv(allowlist_path, index=False)
    adapter = _CountingFakeAdapter()

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        max_rows=10,
        scan_utc="2026-04-07T12:10:00Z",
        adapter=adapter,
        allowlist_path=allowlist_path,
        stage_mode=F061_STAGE_MODE_BROWSER_ONLY,
    )

    assert summary["status"] == "success"
    assert summary["stage_mode"] == F061_STAGE_MODE_BROWSER_ONLY
    assert summary["processed_rows"] == 1
    assert summary["scrape_attempted_rows"] == 1
    assert summary["allowlist_selected_rows"] == 1
    assert adapter.catalog_calls == 0
    assert adapter.hazmat_calls == 0
    assert adapter.pricing_calls == 0
    assert adapter.fees_calls == 0
    assert len(adapter.scrape_skip_date_flags) == 1


def test_f061_login_rows_stay_in_original_queue_with_backtrack_ledger(tmp_path: Path) -> None:
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_login",
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "row_key": "cand-login-1",
                "supplier_sku": "LOGIN-1",
                "barcode": "1111111111111",
                "supplier_title": "Login Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
            }
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "run_id": "run_login",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
                "normalized_utc": "2026-05-07T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-05-07T10:00:00Z",
                "completed_at_utc": "",
            }
        ],
    )

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="login_supplier",
        max_rows=1,
        scan_utc="2026-05-07T10:05:00Z",
        adapter=_LoginRequiredAdapter(),
    )

    assert summary["processed_rows"] == 1
    assert summary["pending_rows"] == 1
    assert summary["login_backtrack_pending_rows"] == 1
    assert summary["bbp_iframe_plugin_blocked_rows"] == 0
    assert summary["login_mode_runtime_status"] == "inactive"

    active = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path, dtype=str).fillna("")
    assert len(active) == 1
    assert active.iloc[0]["row_key"] == "cand-login-1"
    assert active.iloc[0]["scan_status"] == "login_backtrack_pending"
    assert active.iloc[0]["scan_reason"] == "login_backtrack_required"
    assert active.iloc[0]["completion_block_reason"] == "bbp_login_required"

    screening = pd.read_csv(tmp_path / get_f_output_contract("f_screening_row_state_live").rel_path, dtype=str).fillna("")
    assert screening.iloc[0]["candidate_id"] == "cand-login-1"
    assert screening.iloc[0]["row_status"] == "login_backtrack_pending"

    ledger = pd.read_csv(tmp_path / get_f_output_contract("f_login_backtrack_evidence_live").rel_path, dtype=str).fillna("")
    assert len(ledger) == 1
    assert ledger.iloc[0]["candidate_id"] == "cand-login-1"
    assert ledger.iloc[0]["api_live_price"] == "20.00"
    assert ledger.iloc[0]["backtrack_status"] == "blocked_login"
    assert ledger.iloc[0]["merged_into_candidate_flag"] == "0"


def test_f061_login_backtrack_write_preserves_other_supplier_active_rows(tmp_path: Path) -> None:
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_login",
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "row_key": "cand-login-1",
                "supplier_sku": "LOGIN-1",
                "barcode": "1111111111111",
                "supplier_title": "Login Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
            },
            {
                "run_id": "run_stax",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "row_key": "stax-row-1",
                "supplier_sku": "STAX-1",
                "barcode": "2222222222222",
                "supplier_title": "Stax Product",
                "unit_cost": "3.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
            },
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "run_id": "run_login",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "raw_login.csv",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
                "normalized_utc": "2026-05-07T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-05-07T10:00:00Z",
                "completed_at_utc": "",
            },
            {
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "run_id": "run_stax",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "raw_stax.csv",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
                "normalized_utc": "2026-05-07T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-05-07T10:00:00Z",
                "completed_at_utc": "",
            },
        ],
    )

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="login_supplier",
        max_rows=1,
        scan_utc="2026-05-07T10:05:00Z",
        adapter=_LoginRequiredAdapter(),
    )

    assert summary["login_backtrack_pending_rows"] == 1
    active = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path, dtype=str).fillna("")
    assert set(active["supplier_id"]) == {"login_supplier", "stax"}
    assert active[active["supplier_id"] == "stax"].iloc[0]["row_key"] == "stax-row-1"
    run_state = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_run_state").rel_path, dtype=str).fillna("")
    assert set(run_state["supplier_id"]) == {"login_supplier", "stax"}


def test_f061_bbp_extension_unavailable_rows_stay_pending_for_backtrack(tmp_path: Path) -> None:
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_extension_unavailable",
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "row_key": "cand-extension-1",
                "supplier_sku": "LOGIN-EXT-1",
                "barcode": "1111111111111",
                "supplier_title": "Extension Unavailable Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
            }
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "run_id": "run_extension_unavailable",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
                "normalized_utc": "2026-05-07T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-05-07T10:00:00Z",
                "completed_at_utc": "",
            }
        ],
    )

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="login_supplier",
        max_rows=1,
        scan_utc="2026-05-07T10:05:00Z",
        adapter=_BbpExtensionUnavailableAdapter(),
    )

    assert summary["processed_rows"] == 1
    assert summary["pending_rows"] == 1
    assert summary["login_backtrack_pending_rows"] == 1
    assert summary["bbp_iframe_plugin_blocked_rows"] == 1

    active = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path, dtype=str).fillna("")
    assert len(active) == 1
    assert active.iloc[0]["row_key"] == "cand-extension-1"
    assert active.iloc[0]["scan_status"] == "login_backtrack_pending"
    assert active.iloc[0]["scan_reason"] == "login_backtrack_required"
    assert active.iloc[0]["completion_block_reason"] == F061_BBP_IFRAME_PLUGIN_BLOCK_REASON

    ledger = pd.read_csv(tmp_path / get_f_output_contract("f_login_backtrack_evidence_live").rel_path, dtype=str).fillna("")
    assert len(ledger) == 1
    assert ledger.iloc[0]["candidate_id"] == "cand-extension-1"
    assert ledger.iloc[0]["backtrack_status"] == "blocked_bbp_iframe_plugin"
    assert ledger.iloc[0]["merged_into_candidate_flag"] == "0"


def test_f061_missing_dashboard_yes_no_stays_pending_without_browser_login_block(tmp_path: Path) -> None:
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_dashboard",
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "row_key": "cand-dashboard-1",
                "supplier_sku": "DASH-1",
                "barcode": "1111111111111",
                "supplier_title": "Dashboard Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
            }
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "run_id": "run_dashboard",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
                "normalized_utc": "2026-05-07T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-05-07T10:00:00Z",
                "completed_at_utc": "",
            }
        ],
    )

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="login_supplier",
        max_rows=1,
        scan_utc="2026-05-07T10:05:00Z",
        adapter=_MissingDashboardYesNoAdapter(),
    )

    assert summary["processed_rows"] == 1
    assert summary["pending_rows"] == 1
    assert summary["login_backtrack_pending_rows"] == 1
    assert summary["scanner_speed_browser_blocked_rows"] == 0

    active = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path, dtype=str).fillna("")
    assert len(active) == 1
    assert active.iloc[0]["row_key"] == "cand-dashboard-1"
    assert active.iloc[0]["scan_status"] == "login_backtrack_pending"
    assert active.iloc[0]["scan_reason"] == "login_backtrack_required"
    assert active.iloc[0]["completion_block_reason"] == "dashboard_yes_no_backtrack_required"

    ledger = pd.read_csv(tmp_path / get_f_output_contract("f_login_backtrack_evidence_live").rel_path, dtype=str).fillna("")
    assert len(ledger) == 1
    assert ledger.iloc[0]["candidate_id"] == "cand-dashboard-1"
    assert ledger.iloc[0]["backtrack_status"] == "missing_dashboard_yes_no"
    assert ledger.iloc[0]["backtrack_bbp_dashboard_yes_or_no"] == ""


def test_f061_likely_dashboard_is_named_and_not_backtracked(tmp_path: Path) -> None:
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_likely",
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "row_key": "cand-likely-1",
                "supplier_sku": "LIKELY-1",
                "barcode": "1111111111111",
                "supplier_title": "Likely Dashboard Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
            }
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "run_id": "run_likely",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
                "normalized_utc": "2026-05-07T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-05-07T10:00:00Z",
                "completed_at_utc": "",
            }
        ],
    )

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="login_supplier",
        max_rows=1,
        scan_utc="2026-05-07T10:05:00Z",
        adapter=_LikelyDashboardAdapter(),
    )

    assert summary["processed_rows"] == 1
    assert summary["pending_rows"] == 0
    assert summary["login_backtrack_pending_rows"] == 0
    assert summary["dashboard_yes_no_unresolved_rows"] == 0
    assert summary["scanner_speed_browser_blocked_rows"] == 0

    active = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path, dtype=str).fillna("")
    assert active.empty

    scrape = pd.read_csv(tmp_path / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path, dtype=str).fillna("")
    row = scrape.iloc[0]
    assert row["candidate_id"] == "cand-likely-1"
    assert row["bbp_dashboard_yes_or_no"] == "LIKELY"
    assert row["bbp_dashboard_delivery_classification"] == "LIKELY_SELLABLE_HAZMAT_SEPARATE_DELIVERY"
    assert row["bbp_dashboard_separate_delivery_required"] == "1"

    ledger = pd.read_csv(tmp_path / get_f_output_contract("f_login_backtrack_evidence_live").rel_path, dtype=str).fillna("")
    assert ledger.empty


def test_f061_repeated_missing_dashboard_yes_no_is_held_not_completed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("F061_LOGIN_MODE", "1")
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "visible")
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_dashboard",
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "row_key": "cand-dashboard-1",
                "supplier_sku": "DASH-1",
                "barcode": "1111111111111",
                "supplier_title": "Dashboard Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "login_backtrack_pending",
                "scan_reason": "login_backtrack_required",
                "attempt_count": "0",
                "last_attempt_utc": "2026-05-07T10:05:00Z",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
                "completion_block_reason": "dashboard_yes_no_backtrack_required",
                "backtrack_original_observed_utc": "2026-05-07T10:05:00Z",
                "backtrack_attempt_count": "2",
            }
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "run_id": "run_dashboard",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
                "normalized_utc": "2026-05-07T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-05-07T10:05:00Z",
                "completed_at_utc": "",
            }
        ],
    )

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="login_supplier",
        max_rows=1,
        scan_utc="2026-05-07T10:15:00Z",
        adapter=_MissingDashboardYesNoAdapter(),
    )

    assert summary["pending_rows"] == 0
    assert summary["login_backtrack_pending_rows"] == 0
    assert summary["dashboard_yes_no_unresolved_rows"] == 1

    active = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path, dtype=str).fillna("")
    assert active.empty

    screening = pd.read_csv(tmp_path / get_f_output_contract("f_screening_row_state_live").rel_path, dtype=str).fillna("")
    assert screening.iloc[0]["candidate_id"] == "cand-dashboard-1"
    assert screening.iloc[0]["row_status"] == "login_backtrack_pending"

    ledger = pd.read_csv(tmp_path / get_f_output_contract("f_login_backtrack_evidence_live").rel_path, dtype=str).fillna("")
    assert len(ledger) == 1
    assert ledger.iloc[0]["backtrack_status"] == "dashboard_yes_no_unresolved"
    assert ledger.iloc[0]["merged_into_candidate_flag"] == "0"

    events = pd.read_csv(
        tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "live_cycle_events.csv",
        dtype=str,
    ).fillna("")
    hold_event = events[events["event_type"] == "login_mode_hold_started"].iloc[0]
    assert hold_event["rows"] == "1"
    assert "bbp_selected_rows=0" in hold_event["notes"]

    health = pd.read_csv(tmp_path / get_f_output_contract("feeder_legacy_sheet_health").rel_path, dtype=str).fillna("")
    row = health[health["check"] == "dashboard_yes_no_unresolved_rows"].iloc[0]
    assert row["status"] == "warn"
    assert row["value"] == "1"


def test_f061_hard_fail_with_missing_dashboard_is_audited_not_backtracked(tmp_path: Path) -> None:
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_hard_fail_dashboard",
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "row_key": "cand-hardfail-1",
                "supplier_sku": "HARD-1",
                "barcode": "1111111111111",
                "supplier_title": "Weak Dashboard Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
            }
        ],
    )
    _write_contract(tmp_path, "feeder_legacy_first_checks_live", [])

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="login_supplier",
        max_rows=1,
        scan_utc="2026-05-07T10:15:00Z",
        adapter=_HardFailMissingDashboardAdapter(),
    )

    assert summary["status_counts"] == {"FAIL": 1}
    assert summary["dashboard_yes_no_unresolved_rows"] == 0
    assert summary["dashboard_missing_on_hard_fail_rows"] == 1
    assert summary["login_backtrack_pending_rows"] == 0

    scrape = pd.read_csv(
        tmp_path / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path,
        dtype=str,
    ).fillna("")
    assert scrape.iloc[0]["first_check_status_code"] == "FAIL"
    assert scrape.iloc[0]["dashboard_yes_no_source"] == "dashboard_missing_on_hard_fail"

    active = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path, dtype=str).fillna("")
    assert active.empty

    health = pd.read_csv(tmp_path / get_f_output_contract("feeder_legacy_sheet_health").rel_path, dtype=str).fillna("")
    row = health[health["check"] == "dashboard_missing_on_hard_fail_rows"].iloc[0]
    assert row["status"] == "warn"
    assert row["value"] == "1"


def test_f061_login_backtrack_merges_yes_no_onto_original_price_context(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("F061_LOGIN_MODE", "1")
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_login",
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "row_key": "cand-login-1",
                "supplier_sku": "LOGIN-1",
                "barcode": "1111111111111",
                "supplier_title": "Login Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "login_backtrack_pending",
                "scan_reason": "login_backtrack_required",
                "attempt_count": "0",
                "last_attempt_utc": "2026-05-07T10:05:00Z",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
                "completion_block_reason": "bbp_login_required",
                "backtrack_original_observed_utc": "2026-05-07T10:05:00Z",
                "backtrack_attempt_count": "1",
            }
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "run_id": "run_login",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
                "normalized_utc": "2026-05-07T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-05-07T10:05:00Z",
                "completed_at_utc": "",
            }
        ],
    )
    _write_contract(
        tmp_path,
        "f_login_backtrack_evidence_live",
        [
            {
                "backtrack_id": "bt-original",
                "backtrack_observed_utc": "2026-05-07T10:05:00Z",
                "original_observed_utc": "2026-05-07T10:05:00Z",
                "original_run_id": "run_login",
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "supplier_sku": "LOGIN-1",
                "barcode": "1111111111111",
                "candidate_id": "cand-login-1",
                "asin": "ASIN111111",
                "unit_cost": "5.00",
                "api_live_price": "20.00",
                "bbp_live_sell_price": "21.00",
                "bbp_30d_avg_price": "19.50",
                "break_even": "10.00",
                "min_sell_price": "12.00",
                "original_pf": "",
                "original_status_reason": "LOGIN_BACKTRACK_PENDING",
                "original_scrape_error": "BBP_LOGIN_REQUIRED",
                "backtrack_attempt_number": "1",
                "backtrack_status": "blocked_login",
                "backtrack_error": "BBP_LOGIN_REQUIRED",
                "backtrack_bbp_dashboard_yes_or_no": "",
                "backtrack_bbp_top_seller_names": "",
                "backtrack_bbp_top_seller_count": "",
                "backtrack_bbp_brand_match_seller": "",
                "backtrack_bbp_brand_match_score": "",
                "backtrack_bbp_brand_match_flag": "",
                "backtrack_profile_mode": "login_backtrack_required",
                "merged_into_candidate_flag": "0",
                "merge_observed_utc": "",
            }
        ],
    )

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="login_supplier",
        max_rows=1,
        scan_utc="2026-05-07T10:10:00Z",
        adapter=_BacktrackSuccessDifferentPriceAdapter(),
    )

    assert summary["pending_rows"] == 0
    assert summary["login_backtrack_merged_rows"] == 1

    scrape = pd.read_csv(tmp_path / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path, dtype=str).fillna("")
    row = scrape.iloc[0].to_dict()
    assert row["candidate_id"] == "cand-login-1"
    assert row["bbp_dashboard_yes_or_no"] == "NO"
    assert row["api_live_price"] == "20.00"
    assert row["bbp_live_sell_price"] == "21.00"
    assert row["dashboard_yes_no_source"] == "login_backtrack"

    ledger = pd.read_csv(tmp_path / get_f_output_contract("f_login_backtrack_evidence_live").rel_path, dtype=str).fillna("")
    assert len(ledger) == 2
    assert ledger.iloc[-1]["backtrack_status"] == "merged"
    assert ledger.iloc[-1]["merged_into_candidate_flag"] == "1"


def test_f061_login_backtrack_resolves_without_repromote_when_api_gate_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("F061_LOGIN_MODE", "1")
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_login",
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "row_key": "cand-login-overrank",
                "supplier_sku": "LOGIN-OVER",
                "barcode": "3333333333333",
                "supplier_title": "Over Rank Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "login_backtrack_pending",
                "scan_reason": "login_backtrack_required",
                "attempt_count": "0",
                "last_attempt_utc": "2026-05-07T10:05:00Z",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
                "completion_block_reason": "bbp_login_required",
                "backtrack_original_observed_utc": "2026-05-07T10:05:00Z",
                "backtrack_attempt_count": "1",
            }
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "run_id": "run_login",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
                "normalized_utc": "2026-05-07T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-05-07T10:05:00Z",
                "completed_at_utc": "",
            }
        ],
    )
    _write_contract(
        tmp_path,
        "f_login_backtrack_evidence_live",
        [
            {
                "backtrack_id": "bt-original",
                "backtrack_observed_utc": "2026-05-07T10:05:00Z",
                "original_observed_utc": "2026-05-07T10:05:00Z",
                "original_run_id": "run_login",
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "supplier_sku": "LOGIN-OVER",
                "barcode": "3333333333333",
                "candidate_id": "cand-login-overrank",
                "asin": "ASIN333333",
                "unit_cost": "5.00",
                "api_live_price": "",
                "bbp_live_sell_price": "",
                "bbp_30d_avg_price": "",
                "break_even": "",
                "min_sell_price": "",
                "original_pf": "",
                "original_status_reason": "LOGIN_BACKTRACK_PENDING",
                "original_scrape_error": "BBP_LOGIN_REQUIRED",
                "backtrack_attempt_number": "1",
                "backtrack_status": "blocked_login",
                "backtrack_error": "BBP_LOGIN_REQUIRED",
                "backtrack_bbp_dashboard_yes_or_no": "",
                "backtrack_bbp_top_seller_names": "",
                "backtrack_bbp_top_seller_count": "",
                "backtrack_bbp_brand_match_seller": "",
                "backtrack_bbp_brand_match_score": "",
                "backtrack_bbp_brand_match_flag": "",
                "backtrack_profile_mode": "login_backtrack_required",
                "merged_into_candidate_flag": "0",
                "merge_observed_utc": "",
            }
        ],
    )

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="login_supplier",
        max_rows=1,
        scan_utc="2026-05-07T10:10:00Z",
        adapter=_FakeAdapter(),
    )

    assert summary["pending_rows"] == 0
    assert summary["login_backtrack_pending_rows"] == 0
    assert summary["login_backtrack_merged_rows"] == 1
    assert summary["status_counts"] == {"OVER50K": 1}

    ledger = pd.read_csv(tmp_path / get_f_output_contract("f_login_backtrack_evidence_live").rel_path, dtype=str).fillna("")
    assert len(ledger) == 2
    assert ledger.iloc[-1]["backtrack_status"] == "merged"
    assert ledger.iloc[-1]["merged_into_candidate_flag"] == "1"


def test_f061_normal_mode_processes_pending_before_login_backtrack(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("F061_LOGIN_MODE", raising=False)
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_login",
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "row_key": "cand-login-1",
                "supplier_sku": "LOGIN-1",
                "barcode": "1111111111111",
                "supplier_title": "Login Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "login_backtrack_pending",
                "scan_reason": "login_backtrack_required",
                "attempt_count": "0",
                "last_attempt_utc": "2026-05-07T10:05:00Z",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
                "completion_block_reason": "bbp_login_required",
                "backtrack_original_observed_utc": "2026-05-07T10:05:00Z",
                "backtrack_attempt_count": "1",
            },
            {
                "run_id": "run_login",
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "row_key": "cand-normal-1",
                "supplier_sku": "NORMAL-1",
                "barcode": "1111111111111",
                "supplier_title": "Normal Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
            },
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "run_id": "run_login",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
                "normalized_utc": "2026-05-07T10:00:00Z",
                "total_rows": "2",
                "pending_rows": "2",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-05-07T10:05:00Z",
                "completed_at_utc": "",
            }
        ],
    )

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="login_supplier",
        max_rows=1,
        scan_utc="2026-05-07T10:10:00Z",
        adapter=_FakeAdapter(),
    )

    active = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path, dtype=str).fillna("")
    assert summary["processed_rows"] == 1
    assert summary["login_mode_active"] is False
    assert summary["login_backtrack_skipped_rows"] == 1
    assert len(active) == 1
    assert active.iloc[0]["row_key"] == "cand-login-1"


def test_f061_normal_mode_does_not_retry_only_login_rows_without_request(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("F061_LOGIN_MODE", raising=False)
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_login",
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "row_key": "cand-login-1",
                "supplier_sku": "LOGIN-1",
                "barcode": "1111111111111",
                "supplier_title": "Login Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "login_backtrack_pending",
                "scan_reason": "login_backtrack_required",
                "attempt_count": "0",
                "last_attempt_utc": "2026-05-07T10:05:00Z",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
                "completion_block_reason": "bbp_login_required",
                "backtrack_original_observed_utc": "2026-05-07T10:05:00Z",
                "backtrack_attempt_count": "1",
            }
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "run_id": "run_login",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
                "normalized_utc": "2026-05-07T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-05-07T10:05:00Z",
                "completed_at_utc": "",
            }
        ],
    )
    adapter = _FakeAdapter()

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="login_supplier",
        max_rows=1,
        scan_utc="2026-05-07T10:10:00Z",
        adapter=adapter,
    )

    active = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path, dtype=str).fillna("")
    health = pd.read_csv(tmp_path / get_f_output_contract("feeder_legacy_sheet_health").rel_path, dtype=str).fillna("")
    login_mode_health = health[health["check"] == "f061_login_mode_runtime"].iloc[0]

    assert summary["processed_rows"] == 0
    assert summary["pending_rows"] == 1
    assert summary["login_backtrack_skipped_rows"] == 1
    assert adapter.token_calls == 0
    assert len(active) == 1
    assert active.iloc[0]["scan_status"] == "login_backtrack_pending"
    assert login_mode_health["status"] == "warn"
    assert login_mode_health["value"] == "login_backtrack_waiting"


def test_f061_login_mode_selects_login_backtrack_first_and_drains_request(tmp_path: Path, monkeypatch) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    request_path = live_dir / "f061_login_mode.requested"
    request_path.parent.mkdir(parents=True, exist_ok=True)
    request_path.write_text(
        "\n".join(
            [
                "requested_utc=2026-05-09T11:20:00Z",
                "requested_by=operator_ui",
                "mode=login_recovery",
                "supplier_id=login_supplier",
                "run_id=run_login",
                "status=requested",
                "hold_seconds=60",
                "reason=operator_login_button",
            ]
        )
        + "\n",
        encoding="ascii",
    )
    monkeypatch.setenv("F061_LOGIN_MODE", "1")
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "visible")
    monkeypatch.setenv("F061_LOGIN_HOLD_SECONDS", "60")
    monkeypatch.setenv("F061_LOGIN_MODE_REQUEST_PATH", str(request_path))
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_login",
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "row_key": "cand-normal-1",
                "supplier_sku": "NORMAL-1",
                "barcode": "1111111111111",
                "supplier_title": "Normal Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
            },
            {
                "run_id": "run_login",
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "row_key": "cand-login-1",
                "supplier_sku": "LOGIN-1",
                "barcode": "1111111111111",
                "supplier_title": "Login Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "login_backtrack_pending",
                "scan_reason": "login_backtrack_required",
                "attempt_count": "0",
                "last_attempt_utc": "2026-05-07T10:05:00Z",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
                "completion_block_reason": "bbp_login_required",
                "backtrack_original_observed_utc": "2026-05-07T10:05:00Z",
                "backtrack_attempt_count": "1",
            },
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "run_id": "run_login",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
                "normalized_utc": "2026-05-07T10:00:00Z",
                "total_rows": "2",
                "pending_rows": "2",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-05-07T10:05:00Z",
                "completed_at_utc": "",
            }
        ],
    )
    _write_contract(
        tmp_path,
        "f_login_backtrack_evidence_live",
        [
            {
                "backtrack_id": "bt-original",
                "backtrack_observed_utc": "2026-05-07T10:05:00Z",
                "original_observed_utc": "2026-05-07T10:05:00Z",
                "original_run_id": "run_login",
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "supplier_sku": "LOGIN-1",
                "barcode": "1111111111111",
                "candidate_id": "cand-login-1",
                "asin": "ASIN111111",
                "unit_cost": "5.00",
                "api_live_price": "20.00",
                "bbp_live_sell_price": "21.00",
                "bbp_30d_avg_price": "19.50",
                "break_even": "10.00",
                "min_sell_price": "12.00",
                "original_pf": "",
                "original_status_reason": "LOGIN_BACKTRACK_PENDING",
                "original_scrape_error": "BBP_LOGIN_REQUIRED",
                "backtrack_attempt_number": "1",
                "backtrack_status": "blocked_login",
                "backtrack_error": "BBP_LOGIN_REQUIRED",
                "backtrack_bbp_dashboard_yes_or_no": "",
                "backtrack_bbp_top_seller_names": "",
                "backtrack_bbp_top_seller_count": "",
                "backtrack_bbp_brand_match_seller": "",
                "backtrack_bbp_brand_match_score": "",
                "backtrack_bbp_brand_match_flag": "",
                "backtrack_profile_mode": "login_backtrack_required",
                "merged_into_candidate_flag": "0",
                "merge_observed_utc": "",
            }
        ],
    )

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="login_supplier",
        max_rows=1,
        scan_utc="2026-05-09T11:25:00Z",
        adapter=_BacktrackSuccessDifferentPriceAdapter(),
    )

    active = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path, dtype=str).fillna("")
    events = pd.read_csv(live_dir / "live_cycle_events.csv", dtype=str).fillna("")
    request_text = request_path.read_text(encoding="ascii")

    assert summary["login_mode_active"] is True
    assert summary["login_mode_selected_rows"] == 1
    assert summary["login_backtrack_merged_rows"] == 1
    assert summary["login_mode_runtime_status"] == "backlog_drained"
    assert len(active) == 1
    assert active.iloc[0]["row_key"] == "cand-normal-1"
    assert "status=drained" in request_text
    assert "login_mode_hold_started" in set(events["event_type"].tolist())
    assert "login_mode_authenticated" in set(events["event_type"].tolist())
    assert "login_mode_backlog_drained" in set(events["event_type"].tolist())


def test_f061_login_backtrack_stress_100_rows_are_prioritized_and_not_completed(tmp_path: Path) -> None:
    active_rows = []
    for idx in range(100):
        active_rows.append(
            {
                "run_id": "run_stress",
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "row_key": f"cand-login-{idx:03d}",
                "supplier_sku": f"LOGIN-{idx:03d}",
                "barcode": "1111111111111",
                "supplier_title": f"Login Product {idx:03d}",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
            }
        )
    _write_contract(tmp_path, "supplier_price_list_active_run", active_rows)
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "login_supplier",
                "supplier_name": "Login Supplier",
                "run_id": "run_stress",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-05-07T10:00:00Z",
                "normalized_utc": "2026-05-07T10:00:00Z",
                "total_rows": "100",
                "pending_rows": "100",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-05-07T10:00:00Z",
                "completed_at_utc": "",
            }
        ],
    )

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="login_supplier",
        max_rows=100,
        scan_utc="2026-05-07T10:15:00Z",
        adapter=_LoginRequiredAdapter(),
    )

    assert summary["processed_rows"] == 100
    assert summary["pending_rows"] == 100
    assert summary["login_backtrack_pending_rows"] == 100
    active = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path, dtype=str).fillna("")
    assert len(active) == 100
    assert set(active["scan_status"]) == {"login_backtrack_pending"}
    assert active.iloc[0]["row_key"] == "cand-login-000"
    ledger = pd.read_csv(tmp_path / get_f_output_contract("f_login_backtrack_evidence_live").rel_path, dtype=str).fillna("")
    assert len(ledger) == 100
    assert set(ledger["backtrack_status"]) == {"blocked_login"}


def test_f061_rewrites_current_supplier_state_while_preserving_other_supplier_rows(tmp_path: Path) -> None:
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "rk_1",
                "supplier_sku": "S1",
                "barcode": "1111111111111",
                "supplier_title": "First Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            },
            {
                "run_id": "run_2",
                "supplier_id": "td_synnex",
                "supplier_name": "TD Synnex",
                "row_key": "rk_td_1",
                "supplier_sku": "TD1",
                "barcode": "9999999999999",
                "supplier_title": "TD Product",
                "unit_cost": "9.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            },
        ],
    )

    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "run_id": "run_1",
                "run_status": "running",
                "source_url": "https://aux.shure-cosmetics.co.uk/pricelist/",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
                "normalized_utc": "2026-04-07T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-04-07T10:00:00Z",
                "completed_at_utc": "",
            },
            {
                "supplier_id": "td_synnex",
                "supplier_name": "TD Synnex",
                "run_id": "run_2",
                "run_status": "running",
                "source_url": "https://tdsynnex.example/pricelist/enhanced-gb.tsv",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
                "normalized_utc": "2026-04-07T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-04-07T10:00:00Z",
                "completed_at_utc": "",
            },
        ],
    )

    _write_contract(
        tmp_path,
        "feeder_legacy_first_checks_live",
        [
            {
                "completed": "TD1",
                "barcode": "9999999999999",
                "cost": "9.00",
                "vat": "20",
                "supplier": "TD Synnex",
                "asin": "ASINTD1",
                "main_rank": "1000",
                "start_date": "2024-01-01",
                "brand": "BrandTD",
                "size_1": "1",
                "size_2": "1",
                "size_3": "1",
                "weight": "10",
                "dg_ok": "Yes",
                "hazmat": "Yes",
                "buy_box_price": "20.00",
                "lowest_afn_price": "19.00",
                "lowest_mfn_price": "",
                "reasonable_price": "20.00",
                "fba_fee": "4.00",
                "referral_fee": "3.00",
                "digital_fee": "0.14",
                "est_shipping": "0.20",
                "vat_adjusted_price": "16.67",
                "break_even": "15.00",
                "min_sell_price": "18.00",
                "scan_day": "2026-04-07T11:00:00Z",
                "title": "TD title",
                "sales": "10",
                "rating": "4.0",
                "date": "2024-01-01",
                "variant_reviews": "10",
                "reviews_list": "10",
                "point_score": "4.00",
                "history_score": "",
                "pf": "PASS",
                "status_reason": "PASS",
                "candidate_id": "rk_td_1",
                "supplier_sku": "TD1",
                "recommendation_status": "",
                "recommended_test_qty": "",
            }
        ],
    )

    adapter = _FakeAdapter()
    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        max_rows=10,
        scan_utc="2026-04-07T12:00:00Z",
        adapter=adapter,
    )

    assert summary["status"] == "success"
    assert summary["pass_rows"] == 1

    active_path = tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path
    active_df = pd.read_csv(active_path, dtype=str).fillna("")
    assert len(active_df) == 1
    assert active_df.iloc[0]["supplier_id"] == "td_synnex"
    assert active_df.iloc[0]["row_key"] == "rk_td_1"

    run_state_path = tmp_path / get_f_output_contract("supplier_price_list_run_state").rel_path
    run_state_df = pd.read_csv(run_state_path, dtype=str).fillna("")
    assert set(run_state_df["supplier_id"]) == {"shure_cosmetics", "td_synnex"}

    first_checks_path = tmp_path / get_f_output_contract("feeder_legacy_first_checks_live").rel_path
    first_df = pd.read_csv(first_checks_path, dtype=str).fillna("")
    assert set(first_df["supplier"]) == {"Shure Cosmetics", "TD Synnex"}


def test_f061_reprocessed_failure_removes_stale_pass_row(tmp_path: Path) -> None:
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "rk_1",
                "supplier_sku": "S1",
                "barcode": "1111111111111",
                "supplier_title": "First Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            },
        ],
    )

    _write_contract(
        tmp_path,
        "feeder_legacy_first_checks_live",
        [
            {
                "completed": "S1",
                "barcode": "1111111111111",
                "supplier": "Shure Cosmetics",
                "asin": "ASIN111111",
                "pf": "PASS",
                "status_reason": "PASS",
                "candidate_id": "rk_1",
                "supplier_sku": "S1",
            },
        ],
    )

    class _FailingAdapter(_FakeAdapter):
        def process_scrape(
            self,
            *,
            asin: str,
            break_even_price: float,
            min_sell_price: float,
            product_cost: float,
            row_index: int,
            brand_name: str,
            vat_rate: float,
            skip_date_scraping: bool,
            old_chrome_forced: bool,
        ):
            return {"success": False, "error": "REVIEWS_NO_UK"}

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        max_rows=1,
        scrape_mode="legacy_module",
        adapter=_FailingAdapter(),
    )

    assert summary["processed_rows"] == 1
    assert summary["pass_rows"] == 0
    assert summary["fail_rows"] == 1

    live_path = tmp_path / get_f_output_contract("feeder_legacy_first_checks_live").rel_path
    live_df = pd.read_csv(live_path, dtype=str).fillna("")
    assert live_df.empty


def test_f061_summary_includes_price_source_and_interval(tmp_path: Path) -> None:
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "rk_1",
                "supplier_sku": "S1",
                "barcode": "1111111111111",
                "supplier_title": "First Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            },
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "run_id": "run_1",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
                "normalized_utc": "2026-04-07T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-04-07T10:00:00Z",
                "completed_at_utc": "",
            }
        ],
    )
    _write_contract(tmp_path, "feeder_legacy_first_checks_live", [])

    adapter = _FakeAdapter()
    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        max_rows=1,
        scan_utc="2026-04-07T12:00:00Z",
        price_source="native_comp_summary",
        pricing_min_interval_seconds=0.5,
        adapter=adapter,
    )
    assert summary["status"] == "success"
    assert summary["price_source"] == "native_comp_summary"
    assert summary["pricing_min_interval_seconds"] == 0.5


def test_f061_data_collection_mode_scrapes_even_when_roi_gate_fails(tmp_path: Path, monkeypatch) -> None:
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "rk_roi_data_mode",
                "supplier_sku": "S_ROI",
                "barcode": "1111111111111",
                "supplier_title": "ROI Data Collection Product",
                "unit_cost": "8.50",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            },
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "run_id": "run_1",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
                "normalized_utc": "2026-04-07T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-04-07T10:00:00Z",
                "completed_at_utc": "",
            },
        ],
    )
    _write_contract(tmp_path, "feeder_legacy_first_checks_live", [])

    class _RoiFailDataAdapter(_FakeAdapter):
        def get_pricing(self, asin: str, access_token: str):
            return {"asin": asin, "buy_box_price": "9.00", "lowest_afn_price": "8.50"}

    monkeypatch.setenv("F061_MODE", "data_collection")
    adapter = _RoiFailDataAdapter()
    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        max_rows=1,
        scan_utc="2026-04-07T12:00:00Z",
        adapter=adapter,
    )

    assert summary["processed_rows"] == 1
    assert summary["scrape_attempted_rows"] == 1
    assert summary["scrape_success_rows"] == 1
    assert summary["status_counts"] == {"ROIFAIL": 1}
    assert summary["mode"] == "data_collection"

    scrape_path = tmp_path / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path
    scrape_df = pd.read_csv(scrape_path, dtype=str).fillna("")
    assert len(scrape_df) == 1
    assert scrape_df.iloc[0]["first_check_status_code"] == "ROIFAIL"
    assert scrape_df.iloc[0]["scrape_attempted"] == "True"
    assert scrape_df.iloc[0]["scrape_success"] == "True"

    screening_state_path = tmp_path / get_f_output_contract("f_screening_row_state_live").rel_path
    screening_state_df = pd.read_csv(screening_state_path, dtype=str).fillna("")
    row = screening_state_df.iloc[0]
    assert row["row_status"] == "timeout"
    assert row["last_stage"] == "roi_gate"
    assert row["fail_code"] == "ROIFAIL"
    assert row["timeout_until_utc"].endswith("Z")


def test_f061_generic_fail_rows_record_webscrape_stage_and_timeout(tmp_path: Path) -> None:
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "rk_fail_webscrape",
                "supplier_sku": "S_FAIL",
                "barcode": "1111111111111",
                "supplier_title": "Weak Reviews Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            },
        ],
    )
    _write_contract(tmp_path, "feeder_legacy_first_checks_live", [])

    class _GenericFailAdapter(_FakeAdapter):
        def process_scrape(
            self,
            *,
            asin: str,
            break_even_price: float,
            min_sell_price: float,
            product_cost: float,
            row_index: int,
            brand_name: str,
            vat_rate: float,
            skip_date_scraping: bool,
            old_chrome_forced: bool,
        ):
            return {
                "success": True,
                "scraped_data": _complete_scraped_payload(
                    break_even_price=break_even_price,
                    title="Weak Listing",
                    monthly_sold="1",
                    rating="3.0",
                    product_info="2020-01-01",
                    variant_reviews="0",
                    reviews_text="0",
                ),
            }

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        max_rows=1,
        scan_utc="2026-04-07T12:00:00Z",
        adapter=_GenericFailAdapter(),
    )

    assert summary["processed_rows"] == 1
    assert summary["status_counts"] == {"FAIL": 1}

    screening_state_path = tmp_path / get_f_output_contract("f_screening_row_state_live").rel_path
    screening_state_df = pd.read_csv(screening_state_path, dtype=str).fillna("")
    row = screening_state_df.iloc[0]
    assert row["row_status"] == "timeout"
    assert row["fail_code"] == "FAIL"
    assert row["last_stage"] == "webscrape"
    assert row["timeout_until_utc"].endswith("Z")


def test_f061_incomplete_price_history_capture_maps_to_rescan(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("F061_RESCAN_MAX_ACTIVE_ATTEMPTS", "2")
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "rk_incomplete_history",
                "supplier_sku": "S_INCOMPLETE",
                "barcode": "1111111111111",
                "supplier_title": "Incomplete History Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            },
        ],
    )
    _write_contract(tmp_path, "feeder_legacy_first_checks_live", [])

    class _IncompleteHistoryAdapter(_FakeAdapter):
        def process_scrape(
            self,
            *,
            asin: str,
            break_even_price: float,
            min_sell_price: float,
            product_cost: float,
            row_index: int,
            brand_name: str,
            vat_rate: float,
            skip_date_scraping: bool,
            old_chrome_forced: bool,
        ):
            return {
                "success": True,
                "scraped_data": {
                    "updated_break_even": f"{break_even_price:.2f}",
                    "scan_date": "2026-04-07",
                    "main_title": "Incomplete History Product",
                    "monthly_sold": "3",
                    "rating": "4.2",
                    "product_info": "2020-01-01",
                    "variant_reviews": "6",
                    "reviews_text": "3",
                    "price_history_points_365d": "0",
                    "chart_price_daily_series": "",
                    "chart_raw_amazon_daily_series": "",
                    "chart_raw_fba_daily_series": "",
                    "chart_raw_fbm_daily_series": "",
                    "chart_raw_buy_box_daily_series": "",
                    "history_source": "",
                },
            }

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        max_rows=1,
        scan_utc="2026-04-07T12:00:00Z",
        adapter=_IncompleteHistoryAdapter(),
    )

    assert summary["status"] == "success"
    assert summary["retry_rows"] == 1
    assert summary["rescan_retry_pending_rows"] == 1
    assert summary["rescan_retry_exhausted_rows"] == 0
    assert summary["pending_rows"] == 1
    assert summary["status_counts"].get("RESCAN", 0) == 1

    active_path = tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path
    active_df = pd.read_csv(active_path, dtype=str).fillna("")
    assert len(active_df.index) == 1
    active_row = active_df.iloc[0]
    assert active_row["scan_status"] == "pending"
    assert active_row["scan_reason"] == "rescan_retry_required"
    assert active_row["completion_block_reason"] == "rescan_retry_pending"
    assert active_row["attempt_count"] == "1"
    assert active_row["last_attempt_utc"] == "2026-04-07T12:00:00Z"

    evidence_path = tmp_path / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path
    evidence_df = pd.read_csv(evidence_path, dtype=str).fillna("")
    evidence_row = evidence_df.iloc[0]
    assert evidence_row["first_check_status_code"] == "RESCAN"
    assert evidence_row["scrape_success"] == "False"
    assert evidence_row["scrape_error"] == "INCOMPLETE_PRICE_HISTORY_CAPTURE"

    state_path = tmp_path / get_f_output_contract("f_screening_row_state_live").rel_path
    state_df = pd.read_csv(state_path, dtype=str).fillna("")
    state_row = state_df.iloc[0]
    assert state_row["row_status"] == "retry"
    assert state_row["fail_code"] == "RESCAN"
    assert state_row["status_reason"] == "RESCAN|retry_pending"
    assert state_row["timeout_until_utc"] == ""


def test_f061_rescan_retry_allows_configured_second_active_attempt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("F061_RESCAN_MAX_ACTIVE_ATTEMPTS", "2")
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "rk_retry_second_attempt",
                "supplier_sku": "S_RETRY_SECOND",
                "barcode": "4444444444444",
                "supplier_title": "Retry Second Attempt Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "rescan_retry_required",
                "attempt_count": "1",
                "last_attempt_utc": "2026-04-07T12:00:00Z",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            },
        ],
    )
    _write_contract(tmp_path, "feeder_legacy_first_checks_live", [])

    class _CatalogRescanAdapter(_FakeAdapter):
        def get_catalog_details(self, barcode: str, access_token: str):
            return {"error": "http_429"}

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        max_rows=1,
        scan_utc="2026-04-07T12:30:00Z",
        adapter=_CatalogRescanAdapter(),
    )

    assert summary["retry_rows"] == 1
    assert summary["rescan_retry_pending_rows"] == 1
    assert summary["rescan_retry_exhausted_rows"] == 0
    assert summary["pending_rows"] == 1

    active_path = tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path
    active_df = pd.read_csv(active_path, dtype=str).fillna("")
    assert len(active_df.index) == 1
    active_row = active_df.iloc[0]
    assert active_row["scan_status"] == "pending"
    assert active_row["scan_reason"] == "rescan_retry_required"
    assert active_row["completion_block_reason"] == "rescan_retry_pending"
    assert active_row["attempt_count"] == "2"

    state_path = tmp_path / get_f_output_contract("f_screening_row_state_live").rel_path
    state_df = pd.read_csv(state_path, dtype=str).fillna("")
    state_row = state_df.iloc[0]
    assert state_row["row_status"] == "retry"
    assert state_row["fail_code"] == "RESCAN"
    assert state_row["status_reason"] == "RESCAN|retry_pending"
    assert state_row["timeout_until_utc"] == ""


def test_f061_rescan_retry_exhausts_after_configured_active_attempts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("F061_RESCAN_MAX_ACTIVE_ATTEMPTS", "2")
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "rk_retry_exhausted",
                "supplier_sku": "S_RETRY_EXHAUSTED",
                "barcode": "4444444444444",
                "supplier_title": "Retry Exhausted Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "rescan_retry_required",
                "attempt_count": "2",
                "last_attempt_utc": "2026-04-07T12:00:00Z",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            },
        ],
    )
    _write_contract(tmp_path, "feeder_legacy_first_checks_live", [])

    class _CatalogRescanAdapter(_FakeAdapter):
        def get_catalog_details(self, barcode: str, access_token: str):
            return {"error": "http_429"}

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        max_rows=1,
        scan_utc="2026-04-07T12:30:00Z",
        adapter=_CatalogRescanAdapter(),
    )

    assert summary["retry_rows"] == 1
    assert summary["rescan_retry_pending_rows"] == 0
    assert summary["rescan_retry_exhausted_rows"] == 1
    assert summary["pending_rows"] == 0

    active_path = tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path
    active_df = pd.read_csv(active_path, dtype=str).fillna("")
    assert active_df.empty

    state_path = tmp_path / get_f_output_contract("f_screening_row_state_live").rel_path
    state_df = pd.read_csv(state_path, dtype=str).fillna("")
    state_row = state_df.iloc[0]
    assert state_row["row_status"] == "timeout"
    assert state_row["fail_code"] == "RESCAN"
    assert state_row["status_reason"] == "RESCAN|retry_exhausted"
    assert state_row["timeout_until_utc"] == ""


def test_f061_writes_explicit_price_source_columns_on_scrape_success(tmp_path: Path) -> None:
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "rk_price_cols",
                "supplier_sku": "S_PRICE",
                "barcode": "1111111111111",
                "supplier_title": "Price Source Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            },
        ],
    )
    _write_contract(tmp_path, "feeder_legacy_first_checks_live", [])

    class _PriceColumnAdapter(_FakeAdapter):
        def get_pricing(self, asin: str, access_token: str):
            return {"asin": asin, "buy_box_price": "20.00", "lowest_afn_price": "19.50"}

        def process_scrape(
            self,
            *,
            asin: str,
            break_even_price: float,
            min_sell_price: float,
            product_cost: float,
            row_index: int,
            brand_name: str,
            vat_rate: float,
            skip_date_scraping: bool,
            old_chrome_forced: bool,
        ):
            payload = _complete_scraped_payload(
                break_even_price=break_even_price,
                title="Resolved Listing",
                monthly_sold="42",
                rating="4.4",
                product_info="2020-01-01",
                variant_reviews="12",
                reviews_text="8",
            )
            payload.update(
                {
                    "bbp_final_sell_price": "19.99",
                    "avg_30_day_price": "18.70",
                }
            )
            return {
                "success": True,
                "scraped_data": payload,
            }

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        max_rows=1,
        scan_utc="2026-04-07T12:00:00Z",
        adapter=_PriceColumnAdapter(),
    )
    assert summary["status"] == "success"
    assert summary["processed_rows"] == 1

    first_checks_path = tmp_path / get_f_output_contract("feeder_legacy_first_checks_live").rel_path
    first_df = pd.read_csv(first_checks_path, dtype=str).fillna("")
    row = first_df.iloc[0]
    assert row["api_live_price"] == "20.00"
    assert row["bbp_live_sell_price"] == "19.99"
    assert row["bbp_30d_avg_price"] == "18.70"


def test_f061_uses_non_top_catalog_candidate_when_top_is_over50k(tmp_path: Path) -> None:
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "rk_multi_1",
                "supplier_sku": "S1",
                "barcode": "085805390600",
                "supplier_title": "Fifth Avenue",
                "unit_cost": "10.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            },
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "run_id": "run_1",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
                "normalized_utc": "2026-04-07T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-04-07T10:00:00Z",
                "completed_at_utc": "",
            }
        ],
    )
    _write_contract(tmp_path, "feeder_legacy_first_checks_live", [])

    adapter = _FakeMultiCatalogAdapter(
        {
            "085805390600": [
                {
                    "asin": "B00TOPRANK",
                    "rank": 501407,
                    "brand": "Brand A",
                    "dimensions": {},
                    "weight": 0.5,
                    "release_date": "2020-01-01",
                    "identifiers": [
                        {
                            "marketplaceId": "A1F83G8C2ARO7P",
                            "identifiers": [{"identifierType": "UPC", "identifier": "9788073697"}],
                        }
                    ],
                },
                {
                    "asin": "B00GOODRANK",
                    "rank": 4426,
                    "brand": "Brand A",
                    "dimensions": {},
                    "weight": 0.5,
                    "release_date": "2020-01-01",
                    "identifiers": [
                        {
                            "marketplaceId": "A1F83G8C2ARO7P",
                            "identifiers": [{"identifierType": "EAN", "identifier": "085805390600"}],
                        }
                    ],
                },
            ]
        }
    )

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        max_rows=1,
        scan_utc="2026-04-07T12:00:00Z",
        catalog_max_candidates=3,
        adapter=adapter,
    )

    assert summary["status"] == "success"
    assert summary["processed_rows"] == 1
    assert summary["expanded_candidate_rows"] == 1
    assert summary["pass_rows"] == 1
    assert summary["fail_rows"] == 0

    first_checks_path = tmp_path / get_f_output_contract("feeder_legacy_first_checks_live").rel_path
    first_df = pd.read_csv(first_checks_path, dtype=str).fillna("")
    assert len(first_df) == 1
    assert first_df.iloc[0]["asin"] == "B00GOODRANK"

    run_state_path = tmp_path / get_f_output_contract("supplier_price_list_run_state").rel_path
    run_state_df = pd.read_csv(run_state_path, dtype=str).fillna("")
    assert run_state_df.iloc[0]["failed_rows"] == "0"


def test_f061_writes_multiple_pass_rows_when_multiple_catalog_candidates_pass(tmp_path: Path) -> None:
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "rk_multi_2",
                "supplier_sku": "S2",
                "barcode": "123456789012",
                "supplier_title": "Duplicate Listings",
                "unit_cost": "8.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            },
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "run_id": "run_1",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
                "normalized_utc": "2026-04-07T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-04-07T10:00:00Z",
                "completed_at_utc": "",
            }
        ],
    )
    _write_contract(tmp_path, "feeder_legacy_first_checks_live", [])

    adapter = _FakeMultiCatalogAdapter(
        {
            "123456789012": [
                {
                    "asin": "B00ALTONE1",
                    "rank": 2300,
                    "brand": "Brand B",
                    "dimensions": {},
                    "weight": 0.3,
                    "release_date": "2021-01-01",
                    "identifiers": [
                        {
                            "marketplaceId": "A1F83G8C2ARO7P",
                            "identifiers": [{"identifierType": "UPC", "identifier": "123456789012"}],
                        }
                    ],
                },
                {
                    "asin": "B00ALTTWO2",
                    "rank": 5100,
                    "brand": "Brand B",
                    "dimensions": {},
                    "weight": 0.4,
                    "release_date": "2021-01-01",
                    "identifiers": [
                        {
                            "marketplaceId": "A1F83G8C2ARO7P",
                            "identifiers": [{"identifierType": "EAN", "identifier": "123456789012"}],
                        }
                    ],
                },
            ]
        }
    )

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        max_rows=1,
        scan_utc="2026-04-07T12:00:00Z",
        catalog_max_candidates=2,
        adapter=adapter,
    )

    assert summary["status"] == "success"
    assert summary["processed_rows"] == 1
    assert summary["expanded_candidate_rows"] == 2
    assert summary["pass_rows"] == 2
    assert summary["fail_rows"] == 0
    assert summary["retry_rows"] == 0
    assert adapter.scrape_calls == 2

    first_checks_path = tmp_path / get_f_output_contract("feeder_legacy_first_checks_live").rel_path
    first_df = pd.read_csv(first_checks_path, dtype=str).fillna("")
    assert len(first_df) == 2
    assert set(first_df["asin"]) == {"B00ALTONE1", "B00ALTTWO2"}
    assert len(set(first_df["candidate_id"])) == 2
    assert any(candidate_id.startswith("rk_multi_2__alt2_") for candidate_id in first_df["candidate_id"])

    run_state_path = tmp_path / get_f_output_contract("supplier_price_list_run_state").rel_path
    run_state_df = pd.read_csv(run_state_path, dtype=str).fillna("")
    assert run_state_df.iloc[0]["done_rows"] == "1"
    assert run_state_df.iloc[0]["failed_rows"] == "0"


def test_f061_records_weak_match_score_without_blocking_pass(tmp_path: Path) -> None:
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "rk_weak_1",
                "supplier_sku": "S3",
                "barcode": "3607340213267",
                "supplier_title": "Beauty Ladies 100ml EDP Calvin Klein",
                "unit_cost": "8.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            },
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "run_id": "run_1",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
                "normalized_utc": "2026-04-07T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-04-07T10:00:00Z",
                "completed_at_utc": "",
            }
        ],
    )
    _write_contract(tmp_path, "feeder_legacy_first_checks_live", [])

    adapter = _FakeMultiCatalogAdapter(
        {
            "3607340213267": [
                {
                    "asin": "B00WEAK001",
                    "rank": 27784,
                    "brand": "CALVIN KLEIN",
                    "title": "CALVIN KLEIN Beauty Eau de Parfum for Women 100ml",
                    "dimensions": {},
                    "weight": 0.4,
                    "release_date": "2021-01-01",
                    "identifiers": [
                        {
                            "marketplaceId": "A1F83G8C2ARO7P",
                            "identifiers": [{"identifierType": "UPC", "identifier": "768826075847"}],
                        }
                    ],
                }
            ]
        }
    )

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        max_rows=1,
        scan_utc="2026-04-07T12:00:00Z",
        catalog_max_candidates=3,
        adapter=adapter,
    )

    assert summary["status"] == "success"
    assert summary["pass_rows"] == 1

    first_checks_path = tmp_path / get_f_output_contract("feeder_legacy_first_checks_live").rel_path
    first_df = pd.read_csv(first_checks_path, dtype=str).fillna("")
    assert len(first_df) == 1
    assert first_df.iloc[0]["pf"] == "PASS"
    assert "WEAK" in first_df.iloc[0]["history_score"]
    assert "MATCH_WEAK" in first_df.iloc[0]["status_reason"]


class _DummyResponse:
    def __init__(self, status_code: int, payload: dict[str, object]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, object]:
        return self._payload


def test_native_comp_summary_pricing_path_returns_prices(monkeypatch) -> None:
    def _fake_post(*args, **kwargs):
        return _DummyResponse(
            200,
            {
                "responses": [
                    {
                        "status": {"statusCode": 200},
                        "body": {
                            "featuredBuyingOptions": [
                                {
                                    "segmentedFeaturedOffers": [
                                        {"listingPrice": {"amount": "22.34"}}
                                    ]
                                }
                            ],
                            "lowestPricedOffers": [
                                {
                                    "offers": [
                                        {"listingPrice": {"amount": "21.99"}}
                                    ]
                                }
                            ],
                        },
                    }
                ]
            },
        )

    monkeypatch.setattr("scripts.flows.F.F061_run_legacy_first_checks_local.requests.post", _fake_post)
    adapter = LegacyCompatibleAmazonAdapter(
        legacy_scanner_root=None,
        scrape_mode="disabled",
        price_source="native_comp_summary",
    )
    result = adapter.get_pricing("B000TEST001", "fake-token")
    assert result["buy_box_price"] == "22.34"
    assert result["lowest_afn_price"] == "21.99"
    stats = adapter.pricing_stats()
    assert stats["source"] == "native_comp_summary"
    assert stats["calls_total"] == 1


def test_missing_legacy_modules_excludes_pricing_when_native_source(tmp_path: Path) -> None:
    adapter = LegacyCompatibleAmazonAdapter(
        legacy_scanner_root=str(tmp_path),
        scrape_mode="legacy_module",
        price_source="native_comp_summary",
    )
    missing = adapter.missing_legacy_modules()
    assert "pricingCall.get_pricing_details_for_asin" not in missing


def test_catalog_candidate_selection_scores_exact_match_above_conflict() -> None:
    adapter = LegacyCompatibleAmazonAdapter(price_source="native_comp_summary")

    payload = {
        "items": [
            {
                "asin": "B00WRONG001",
                "dimensions": [{"package": {}}],
                "salesRanks": [{"displayGroupRanks": [{"rank": 1200}]}],
                "attributes": {"brand": [{"value": "Wrong Match"}]},
                "summaries": [{"releaseDate": "2025-01-01"}],
                "identifiers": [
                    {
                        "marketplaceId": "A1F83G8C2ARO7P",
                        "identifiers": [{"identifierType": "EAN", "identifier": "9999999999999"}],
                    }
                ],
            },
            {
                "asin": "B00RIGHT001",
                "dimensions": [{"package": {}}],
                "salesRanks": [{"displayGroupRanks": [{"rank": 2200}]}],
                "attributes": {"brand": [{"value": "Right Match"}]},
                "summaries": [{"releaseDate": "2025-01-01"}],
                "identifiers": [
                    {
                        "marketplaceId": "A1F83G8C2ARO7P",
                        "identifiers": [{"identifierType": "EAN", "identifier": "3607340213267"}],
                    }
                ],
            },
        ]
    }

    candidates = adapter._catalog_payload_to_candidates(payload)
    selected = [
        candidate["asin"]
        for candidate in _select_catalog_candidates_for_processing(
            candidates=candidates,
            max_candidates=3,
            search_barcode="3607340213267",
            supplier_title="Beauty Ladies 100ml EDP Calvin Klein",
        )
    ]
    assert selected == ["B00RIGHT001", "B00WRONG001"]
    assert candidates[1]["_match_grade"] == "EXACT"
    assert candidates[0]["_match_grade"] in {"VERY_WEAK", "WEAK"}


def test_catalog_lookup_keeps_conflict_candidate_but_scores_it_weak(monkeypatch) -> None:
    adapter = LegacyCompatibleAmazonAdapter(price_source="native_comp_summary")

    class _FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "items": [
                    {
                        "asin": "B00WRONG001",
                        "dimensions": [{"package": {}}],
                        "salesRanks": [{"displayGroupRanks": [{"rank": 1200}]}],
                        "attributes": {"brand": [{"value": "Wrong Match"}]},
                        "summaries": [{"releaseDate": "2025-01-01"}],
                        "identifiers": [
                            {
                                "marketplaceId": "A1F83G8C2ARO7P",
                                "identifiers": [{"identifierType": "EAN", "identifier": "9999999999999"}],
                            }
                        ],
                    }
                ]
            }

    monkeypatch.setattr("scripts.flows.F.F061_run_legacy_first_checks_local.requests.get", lambda *args, **kwargs: _FakeResponse())

    selected = _select_catalog_candidates_for_processing(
        candidates=adapter.get_catalog_candidates("3607340213267", "fake-token") or [],
        max_candidates=3,
        search_barcode="3607340213267",
        supplier_title="Beauty Ladies 100ml EDP Calvin Klein",
    )
    assert len(selected) == 1
    assert selected[0]["asin"] == "B00WRONG001"
    assert selected[0]["_match_grade"] in {"VERY_WEAK", "WEAK"}


def test_get_catalog_details_falls_back_to_native_when_legacy_parser_raises(monkeypatch) -> None:
    adapter = LegacyCompatibleAmazonAdapter(price_source="native_comp_summary")

    def _boom(barcode: str, access_token: str):
        raise IndexError("list index out of range")

    class _FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "items": [
                    {
                        "asin": "B00TEST123",
                        "dimensions": [{"package": {"weight": {"unit": "pounds", "value": 1.2}}}],
                        "salesRanks": [{"displayGroupRanks": [{"rank": 1234}]}],
                        "attributes": {
                            "brand": [{"value": "Fallback Brand"}],
                        },
                        "summaries": [{"releaseDate": "2024-01-01"}],
                    }
                ]
            }

    adapter._legacy_catalog_func = _boom
    monkeypatch.setattr("scripts.flows.F.F061_run_legacy_first_checks_local.requests.get", lambda *args, **kwargs: _FakeResponse())

    payload = adapter.get_catalog_details("5012345678901", "fake-token")
    assert payload is not None
    assert payload["asin"] == "B00TEST123"
    assert payload["brand"] == "Fallback Brand"


def test_catalog_lookup_uses_ean_first_for_13_digit(monkeypatch) -> None:
    adapter = LegacyCompatibleAmazonAdapter(price_source="native_comp_summary")
    calls: list[str] = []

    class _FakeResponse:
        def __init__(self, status_code: int, payload: dict[str, object]) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict[str, object]:
            return self._payload

    def _fake_get(*args, **kwargs):
        identifiers_type = (kwargs.get("params") or {}).get("identifiersType")
        calls.append(str(identifiers_type))
        if identifiers_type == "EAN":
            return _FakeResponse(
                200,
                {
                    "items": [
                        {
                            "asin": "B00EANOK",
                            "dimensions": [{"package": {}}],
                            "salesRanks": [],
                            "attributes": {"brand": [{"value": "EAN Brand"}]},
                            "summaries": [{"releaseDate": "2025-01-01"}],
                        }
                    ]
                },
            )
        return _FakeResponse(200, {"items": []})

    monkeypatch.setattr("scripts.flows.F.F061_run_legacy_first_checks_local.requests.get", _fake_get)
    payload = adapter.get_catalog_details("5425017730538", "fake-token")
    assert payload is not None
    assert payload["asin"] == "B00EANOK"
    assert calls == ["EAN"]


def test_catalog_lookup_falls_back_from_upc_to_ean_for_12_digit(monkeypatch) -> None:
    adapter = LegacyCompatibleAmazonAdapter(price_source="native_comp_summary")
    calls: list[str] = []

    class _FakeResponse:
        def __init__(self, status_code: int, payload: dict[str, object]) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict[str, object]:
            return self._payload

    def _fake_get(*args, **kwargs):
        identifiers_type = (kwargs.get("params") or {}).get("identifiersType")
        calls.append(str(identifiers_type))
        if identifiers_type == "UPC":
            return _FakeResponse(200, {"items": []})
        return _FakeResponse(
            200,
            {
                "items": [
                    {
                        "asin": "B00FALLBACK",
                        "dimensions": [{"package": {}}],
                        "salesRanks": [],
                        "attributes": {"brand": [{"value": "Fallback Brand"}]},
                        "summaries": [{"releaseDate": "2025-01-01"}],
                    }
                ]
            },
        )

    monkeypatch.setattr("scripts.flows.F.F061_run_legacy_first_checks_local.requests.get", _fake_get)
    payload = adapter.get_catalog_details("123456789012", "fake-token")
    assert payload is not None
    assert payload["asin"] == "B00FALLBACK"
    assert calls == ["UPC", "EAN"]


def test_catalog_lookup_429_maps_to_rescan_in_row_processing(tmp_path: Path) -> None:
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "rk_1",
                "supplier_sku": "S1",
                "barcode": "1234567890123",
                "supplier_title": "Throttle Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            },
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "run_id": "run_1",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
                "normalized_utc": "2026-04-07T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-04-07T10:00:00Z",
                "completed_at_utc": "",
            }
        ],
    )
    _write_contract(tmp_path, "feeder_legacy_first_checks_live", [])

    class _ThrottleCatalogAdapter:
        def get_access_token(self) -> str:
            return "fake-token"

        def get_catalog_details(self, barcode: str, access_token: str):
            return {"asin": "", "error": "http_429"}

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        max_rows=1,
        scan_utc="2026-04-07T12:00:00Z",
        adapter=_ThrottleCatalogAdapter(),
    )
    assert summary["status"] == "success"
    assert summary["retry_rows"] == 1
    assert summary["fail_rows"] == 0
    assert summary["status_counts"].get("RESCAN", 0) == 1


def test_review_timeout_error_maps_to_rescan_in_row_processing(tmp_path: Path) -> None:
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "rk_1",
                "supplier_sku": "S1",
                "barcode": "1111111111111",
                "supplier_title": "Timeout Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            },
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "run_id": "run_1",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
                "normalized_utc": "2026-04-07T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-04-07T10:00:00Z",
                "completed_at_utc": "",
            }
        ],
    )
    _write_contract(tmp_path, "feeder_legacy_first_checks_live", [])

    class _ReviewTimeoutAdapter(_FakeAdapter):
        def process_scrape(
            self,
            *,
            asin: str,
            break_even_price: float,
            min_sell_price: float,
            product_cost: float,
            row_index: int,
            brand_name: str,
            vat_rate: float,
            skip_date_scraping: bool,
            old_chrome_forced: bool,
        ):
            return {
                "success": False,
                "error": "REVIEWS_TIMEOUT",
                "scraped_data": {
                    "scan_date": "2026-04-07",
                    "main_title": "Timeout Product",
                    "product_info": "2020-01-01",
                    "review_page_status": "timeout",
                    "historical_uk_reviews": "N/A",
                },
            }

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        max_rows=1,
        scan_utc="2026-04-07T12:00:00Z",
        adapter=_ReviewTimeoutAdapter(),
    )
    assert summary["status"] == "success"
    assert summary["retry_rows"] == 1
    assert summary["fail_rows"] == 0
    assert summary["status_counts"].get("RESCAN", 0) == 1

    evidence_df = pd.read_csv(tmp_path / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path, dtype=str).fillna("")
    assert len(evidence_df) == 1
    evidence_row = evidence_df.iloc[0]
    assert evidence_row["first_check_status_code"] == "RESCAN"
    assert evidence_row["scrape_success"] == "False"
    assert evidence_row["scrape_error"] == "REVIEWS_TIMEOUT"


def test_missing_rank_maps_to_over50k_gate(tmp_path: Path) -> None:
    _write_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "row_key": "rk_1",
                "supplier_sku": "S1",
                "barcode": "5555555555555",
                "supplier_title": "No Rank Product",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
            },
        ],
    )
    _write_contract(
        tmp_path,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "run_id": "run_1",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "",
                "source_seen_at_utc": "2026-04-07T10:00:00Z",
                "normalized_utc": "2026-04-07T10:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-04-07T10:00:00Z",
                "completed_at_utc": "",
            }
        ],
    )
    _write_contract(tmp_path, "feeder_legacy_first_checks_live", [])

    class _NoRankAdapter:
        def get_access_token(self) -> str:
            return "fake-token"

        def get_catalog_details(self, barcode: str, access_token: str):
            return {
                "asin": "B00NORANK1",
                "rank": "",
                "brand": "No Rank Brand",
                "dimensions": {},
                "weight": "",
                "release_date": "N/A",
            }

    summary = run_legacy_first_checks_local(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        max_rows=1,
        scan_utc="2026-04-07T12:00:00Z",
        adapter=_NoRankAdapter(),
    )
    assert summary["status"] == "success"
    assert summary["fail_rows"] == 1
    assert summary["retry_rows"] == 0
    assert summary["status_counts"].get("OVER50K", 0) == 1


def test_adapter_process_scrape_retries_once_on_window_closed_result_error() -> None:
    adapter = LegacyCompatibleAmazonAdapter(
        scrape_mode="legacy_module",
        legacy_scanner_root=None,
        price_source="native_comp_summary",
    )
    ensure_calls = 0
    close_calls = 0
    scrape_calls = 0

    def _ensure_drivers() -> bool:
        nonlocal ensure_calls
        ensure_calls += 1
        return True

    def _close() -> None:
        nonlocal close_calls
        close_calls += 1

    def _legacy_scrape_func(**kwargs):
        nonlocal scrape_calls
        scrape_calls += 1
        if scrape_calls == 1:
            return {"success": False, "error": "no such window: target window already closed"}
        return {"success": True, "scraped_data": {"asin": kwargs.get("asin", "")}}

    adapter._ensure_drivers = _ensure_drivers  # type: ignore[method-assign]
    adapter.close = _close  # type: ignore[method-assign]
    adapter._legacy_scrape_func = _legacy_scrape_func

    result = adapter.process_scrape(
        asin="B000TEST01",
        break_even_price=10.0,
        min_sell_price=11.0,
        product_cost=7.0,
        row_index=1,
        brand_name="Brand",
        vat_rate=0.2,
        skip_date_scraping=False,
        old_chrome_forced=False,
    )

    assert result["success"] is True
    assert scrape_calls == 2
    assert close_calls == 1
    assert ensure_calls == 2


def test_adapter_process_scrape_retries_once_on_window_closed_exception() -> None:
    adapter = LegacyCompatibleAmazonAdapter(
        scrape_mode="legacy_module",
        legacy_scanner_root=None,
        price_source="native_comp_summary",
    )
    ensure_calls = 0
    close_calls = 0
    scrape_calls = 0

    def _ensure_drivers() -> bool:
        nonlocal ensure_calls
        ensure_calls += 1
        return True

    def _close() -> None:
        nonlocal close_calls
        close_calls += 1

    def _legacy_scrape_func(**kwargs):
        nonlocal scrape_calls
        scrape_calls += 1
        if scrape_calls == 1:
            raise RuntimeError("no such window: target window already closed")
        return {"success": True, "scraped_data": {"asin": kwargs.get("asin", "")}}

    adapter._ensure_drivers = _ensure_drivers  # type: ignore[method-assign]
    adapter.close = _close  # type: ignore[method-assign]
    adapter._legacy_scrape_func = _legacy_scrape_func

    result = adapter.process_scrape(
        asin="B000TEST02",
        break_even_price=10.0,
        min_sell_price=11.0,
        product_cost=7.0,
        row_index=2,
        brand_name="Brand",
        vat_rate=0.2,
        skip_date_scraping=False,
        old_chrome_forced=False,
    )

    assert result["success"] is True
    assert scrape_calls == 2
    assert close_calls == 1
    assert ensure_calls == 2
