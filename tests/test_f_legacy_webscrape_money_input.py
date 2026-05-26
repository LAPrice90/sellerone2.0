from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY_DIR = ROOT / "scripts" / "flows" / "F" / "legacy_scanner_2_1"
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.F.legacy_scanner_2_1.Webscrape import (
    _amazon_buybox_seller_evidence_fields,
    _build_pre_review_fail_payload,
    _economic_pre_review_hard_stop_code,
    _extract_bbp_competition_seller_rows,
    _extract_bbp_top_seller_names,
    _format_bbp_money,
    _login_option_evidence,
    _pre_review_kill_code,
    _seller_evidence_fields,
    _set_bbp_money_input,
    _wait_for_visible_bbp_frame_or_container,
    choose_units_with_amazon_guardrail,
    login_to_buybotpro,
)


class _FakeElement:
    def __init__(self, value: str = "00,069.63", *, text: str = "", attrs: dict[str, str] | None = None) -> None:
        self.value = value
        self.text = text
        self.attrs = attrs or {}
        self.clicked = False
        self.sent: list[tuple[object, ...]] = []

    def click(self) -> None:
        self.clicked = True

    def clear(self) -> None:
        self.value = ""

    def send_keys(self, *values: object) -> None:
        self.sent.append(values)
        if values == ("69.63",):
            self.value += "69.63"
        if values == ("94.99",):
            self.value += "94.99"

    def get_attribute(self, name: str) -> str:
        if name == "value":
            return self.value
        if name == "textContent":
            return self.text
        return self.attrs.get(name, "")


class _FakeDriver:
    def __init__(self) -> None:
        self.scripts: list[tuple[str, tuple[object, ...]]] = []

    def execute_script(self, script: str, *args: object) -> None:
        self.scripts.append((script, args))
        if args and isinstance(args[0], _FakeElement):
            element = args[0]
            if len(args) >= 2:
                element.value = str(args[1])
            else:
                element.value = ""


class _FakeLoginDriver:
    def __init__(
        self,
        *,
        cost_ready: bool = False,
        login_fields: bool = True,
        amazon_signin_link: bool = False,
    ) -> None:
        self.email = _FakeElement("")
        self.password = _FakeElement("")
        self.button = _FakeElement("")
        self.cost_ready = cost_ready
        self.login_fields = login_fields
        self.amazon_signin_link = amazon_signin_link
        self.frame_ready = False
        self.refresh_calls = 0
        self.surface_calls = 0
        self.current_url = "https://www.amazon.co.uk/dp/B000000000"

    def find_elements(self, _by: object, selector: str) -> list[_FakeElement]:
        if selector == "#loginEmail" and self.login_fields:
            return [self.email]
        if selector == "#loginPassword" and self.login_fields:
            return [self.password]
        if selector == "#loginBtn" and self.login_fields:
            return [self.button]
        if selector in {"a[href*='/ap/signin']", "a[href*='openid.mode=checkid_setup']"} and self.amazon_signin_link:
            return [_FakeElement(text="Hello, sign in Account & Lists", attrs={"href": "https://www.amazon.co.uk/ap/signin"})]
        if selector == "#txtBuyPrice" and self.cost_ready:
            return [_FakeElement("1")]
        if selector in {"bbp-frame", "bbp-container"} and self.frame_ready:
            return [_FakeElement("frame")]
        return []

    def refresh(self) -> None:
        self.refresh_calls += 1


class _FakeWait:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def until(self, *_args: object, **_kwargs: object) -> None:
        raise TimeoutError("not ready")


class _FakeSellerElement:
    def __init__(self, *, text: str = "", attrs: dict[str, str] | None = None) -> None:
        self.text = text
        self.attrs = attrs or {}

    def get_attribute(self, name: str) -> str:
        if name == "textContent":
            return self.text
        if name == "outerHTML":
            return self.attrs.get("outerHTML", f"<tr>{self.text}</tr>")
        return self.attrs.get(name, "")


class _FakeSellerDriver:
    def __init__(self, elements_by_selector: dict[str, list[_FakeSellerElement]]) -> None:
        self.elements_by_selector = elements_by_selector

    def find_elements(self, _by: object, selector: str) -> list[_FakeSellerElement]:
        return self.elements_by_selector.get(selector, [])


def test_format_bbp_money_uses_plain_decimal_without_commas() -> None:
    assert _format_bbp_money(69.63) == "69.63"
    assert _format_bbp_money("94.99") == "94.99"


def test_set_bbp_money_input_force_clears_masked_existing_value() -> None:
    driver = _FakeDriver()
    element = _FakeElement("00,069.63")

    written = _set_bbp_money_input(driver, element, 69.63, field_name="cost")

    assert written == "69.63"
    assert element.clicked is True
    assert element.value == "69.63"
    assert any("el.value = ''" in script for script, _args in driver.scripts)
    assert any("const value = arguments[1]" in script for script, _args in driver.scripts)


def test_visible_bbp_login_waits_for_manual_login(monkeypatch) -> None:
    driver = _FakeLoginDriver(cost_ready=False)
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "visible")
    monkeypatch.setenv("F061_MANUAL_BBP_LOGIN_WAIT_SECONDS", "10")

    def fake_sleep(*_args: object, **_kwargs: object) -> None:
        driver.cost_ready = True

    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._human_sleep",
        fake_sleep,
    )

    status = login_to_buybotpro(driver, "user@example.com", "password")

    assert status == "already_authenticated"
    assert driver.button.clicked is False
    assert driver.email.sent == []
    assert driver.password.sent == []


def test_visible_bbp_login_refreshes_once_before_reporting_required(monkeypatch) -> None:
    driver = _FakeLoginDriver(cost_ready=False)
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "visible")
    monkeypatch.setenv("F061_MANUAL_BBP_LOGIN_WAIT_SECONDS", "0.01")
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._human_sleep",
        lambda *_args, **_kwargs: None,
    )

    status = login_to_buybotpro(driver, "user@example.com", "password")

    assert status == "login_required"
    assert driver.refresh_calls == 1
    assert driver.button.clicked is False


def test_visible_missing_bbp_iframe_waits_for_manual_login(monkeypatch) -> None:
    driver = _FakeLoginDriver(cost_ready=False, login_fields=True)
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._human_sleep",
        lambda *_args, **_kwargs: setattr(driver, "frame_ready", True),
    )
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._surface_visible_login_browser",
        lambda *_args, **_kwargs: setattr(driver, "surface_calls", driver.surface_calls + 1),
    )

    assert _wait_for_visible_bbp_frame_or_container(driver, 10) is True
    assert driver.refresh_calls == 0
    assert driver.surface_calls == 1


def test_missing_bbp_iframe_without_real_login_option_stays_hidden(monkeypatch) -> None:
    driver = _FakeLoginDriver(cost_ready=False, login_fields=False)
    monkeypatch.delenv("F061_LOGIN_MODE", raising=False)
    monkeypatch.delenv("F061_MANUAL_BBP_LOGIN_WAIT_SECONDS", raising=False)
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._human_sleep",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._surface_visible_login_browser",
        lambda *_args, **_kwargs: setattr(driver, "surface_calls", driver.surface_calls + 1),
    )

    assert _wait_for_visible_bbp_frame_or_container(driver, 0.01) is False
    assert driver.refresh_calls == 0
    assert driver.surface_calls == 0


def test_amazon_signin_link_does_not_count_as_bbp_login_option() -> None:
    driver = _FakeLoginDriver(cost_ready=False, login_fields=False, amazon_signin_link=True)

    assert _login_option_evidence(driver) == ""


def test_login_mode_missing_bbp_iframe_without_bbp_login_stays_hidden(monkeypatch) -> None:
    driver = _FakeLoginDriver(cost_ready=False, login_fields=False)
    monkeypatch.setenv("F061_LOGIN_MODE", "1")
    monkeypatch.setenv("F061_MANUAL_BBP_LOGIN_WAIT_SECONDS", "10")
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._human_sleep",
        lambda *_args, **_kwargs: setattr(driver, "frame_ready", True),
    )
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._surface_visible_login_browser",
        lambda *_args, **_kwargs: setattr(driver, "surface_calls", driver.surface_calls + 1),
    )

    assert _wait_for_visible_bbp_frame_or_container(driver, 10) is False
    assert driver.refresh_calls == 0
    assert driver.surface_calls == 0


def test_hidden_bbp_login_reports_required_when_auto_submit_does_not_clear_form(monkeypatch) -> None:
    driver = _FakeLoginDriver(cost_ready=False)
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "minimized")
    monkeypatch.delenv("F061_MANUAL_BBP_LOGIN_WAIT_SECONDS", raising=False)
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape.WebDriverWait",
        _FakeWait,
    )
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._human_sleep",
        lambda *_args, **_kwargs: None,
    )

    status = login_to_buybotpro(driver, "user@example.com", "password")

    assert status == "login_required"
    assert driver.button.clicked is True


def test_pre_review_low_sales_gate_respects_amazon_guardrail() -> None:
    units, _score, _note = choose_units_with_amazon_guardrail(amazon_floor=None, bbp_units=2)
    assert _pre_review_kill_code(chosen_units=units, dashboard_yes_or_no="", new_seller_counts=[10, 10, 10]) == (
        "LOW_SALES_CAPITAL_IDLE_RISK"
    )

    units, _score, _note = choose_units_with_amazon_guardrail(amazon_floor=50, bbp_units=2)
    assert _pre_review_kill_code(chosen_units=units, dashboard_yes_or_no="", new_seller_counts=[10, 10, 10]) == ""


def test_pre_review_dashboard_no_low_seller_gate() -> None:
    assert _pre_review_kill_code(chosen_units=20, dashboard_yes_or_no="NO", new_seller_counts=[1, 1, 1]) == (
        "DASHBOARD_NO_LOW_SELLER_COUNT"
    )
    assert _pre_review_kill_code(chosen_units=20, dashboard_yes_or_no="NO", new_seller_counts=[1, 2, 2]) == ""


def test_economic_pre_review_hard_stop_prefers_low_roi() -> None:
    assert _economic_pre_review_hard_stop_code(["NO_PRICE_HISTORY_365D", "LOWROI"]) == "LOWROI"


def test_economic_pre_review_hard_stop_catches_missing_price_history() -> None:
    assert _economic_pre_review_hard_stop_code(["NO_PRICE_HISTORY_365D"]) == "NO_PRICE_HISTORY_365D"


def test_economic_pre_review_hard_stop_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setenv("F061_ECONOMIC_PRE_REVIEW_HARD_STOP", "0")

    assert _economic_pre_review_hard_stop_code(["LOWROI"]) == ""


def test_seller_evidence_fields_identify_brand_like_seller() -> None:
    evidence = _seller_evidence_fields(
        "Plus-Plus",
        ["FBA Prime Plus Plus", "Toy Store UK", "Plus Plus"],
    )

    assert evidence["bbp_top_seller_names"] == "Plus Plus|Toy Store UK"
    assert evidence["bbp_top_seller_count"] == "2"
    assert evidence["bbp_brand_match_seller"] == "Plus Plus"
    assert evidence["bbp_brand_match_flag"] == "True"


def test_extract_bbp_top_seller_names_falls_back_to_cell_text() -> None:
    driver = _FakeSellerDriver(
        {
            "#competitionAnalysisDataTable > tbody > tr td:nth-child(1)": [
                _FakeSellerElement(text="FBA Prime Plus Plus"),
                _FakeSellerElement(text="£17.99"),
                _FakeSellerElement(text="15 - 16 May"),
                _FakeSellerElement(text="15 - 16..."),
                _FakeSellerElement(text="Reviews:431Positive Feedback:87%"),
                _FakeSellerElement(text="Toy Store UK"),
            ]
        }
    )

    assert _extract_bbp_top_seller_names(driver, max_sellers=3) == ["Plus Plus", "Toy Store UK"]


def test_extract_bbp_competition_seller_rows_structures_top_rows() -> None:
    driver = _FakeSellerDriver(
        {
            "#competitionAnalysisDataTable > tbody > tr": [
                _FakeSellerElement(
                    text="FBA Prime Plus Plus\n£17.99\n15 - 16 May\nReviews:431Positive Feedback:87%",
                    attrs={"outerHTML": "<tr><td>FBA Prime Plus Plus</td><td>£17.99</td></tr>"},
                ),
                _FakeSellerElement(
                    text="MF Miller Rock\n£18.49\n17 - 19 May\nReviews:12Positive Feedback:99%",
                ),
            ]
        }
    )

    rows = _extract_bbp_competition_seller_rows(driver, max_rows=3)

    assert rows[0]["name"] == "Plus Plus"
    assert rows[0]["price"] == "£17.99"
    assert rows[0]["fulfilment"] == "FBA|Prime"
    assert rows[0]["delivery"] == "15 - 16 May"
    assert rows[0]["reviews"] == "431"
    assert rows[0]["feedback_pct"] == "87%"
    assert rows[1]["name"] == "Miller Rock"


def test_seller_evidence_fields_include_structured_competition_rows() -> None:
    evidence = _seller_evidence_fields(
        "Plus Plus",
        ["Plus Plus", "Miller Rock"],
        competition_rows=[
            {
                "name": "Plus Plus",
                "price": "£17.99",
                "fulfilment": "FBA|Prime",
                "delivery": "15 - 16 May",
                "reviews": "431",
                "feedback_pct": "87%",
                "row_text": "FBA Prime Plus Plus £17.99",
                "row_html": "<tr>Plus Plus</tr>",
            }
        ],
    )

    assert evidence["bbp_seller_rank_1_name"] == "Plus Plus"
    assert evidence["bbp_seller_rank_1_price"] == "£17.99"
    assert evidence["bbp_seller_rank_1_brand_match_flag"] == "True"
    assert evidence["bbp_seller_rank_2_name"] == ""


def test_amazon_buybox_seller_evidence_fields_identify_brand_match() -> None:
    evidence = _amazon_buybox_seller_evidence_fields("Plus Plus", "Plus Plus")

    assert evidence["amazon_buybox_seller_name"] == "Plus Plus"
    assert evidence["amazon_buybox_brand_match_flag"] == "True"


def test_pre_review_fail_payload_preserves_bbp_evidence() -> None:
    payload = _build_pre_review_fail_payload(
        fail_code="LOW_SALES_CAPITAL_IDLE_RISK",
        monthly_sold="",
        amazon_floor=None,
        chosen_units=2,
        confidence_score=66,
        confidence_note="amazon_missing_bbp_under_50",
        bbp_sales_current=2,
        bbp_sales_recent_avg=2.0,
        bbp_sales_history=[2, 1],
        bbp_sales_history_text="",
        bbp_dashboard_yes_or_no="NO",
        bbp_sales_chart_source="unit",
        bbp_sales_chart_month_labels=["Apr"],
        bbp_sales_chart_month_units=[2],
        bbp_sales_chart_series="Apr=2",
        bbp_sales_last_completed_month_label="Mar",
        bbp_sales_last_completed_month_units=1,
        bbp_sales_current_month_label="Apr",
        bbp_sales_current_month_units=2,
        bbp_sales_future_month_count_ignored=0,
        bbp_sales_replay_demand_basis_source="chart",
        bbp_sales_replay_demand_basis_label="Apr",
        bbp_sales_replay_demand_basis_units=2,
        bbp_section_snapshot_path="",
        bbp_section_snapshot_nodes=0,
        bbp_section_snapshot_error="",
        seller_evidence={
            "bbp_top_seller_names": "Plus Plus",
            "bbp_top_seller_count": "1",
            "bbp_brand_match_seller": "Plus Plus",
            "bbp_brand_match_score": "1.0000",
            "bbp_brand_match_flag": "True",
            "amazon_buybox_seller_name": "Plus Plus",
            "amazon_buybox_brand_match_score": "1.0000",
            "amazon_buybox_brand_match_flag": "True",
        },
        lane_history={"new": {30: 1, 90: 1, 180: 1}},
        hist_raw_rows={"New": [1, 1, 1]},
        phase_snapshot={"price_history_span_days": 365, "price_history_points_365d": 10},
        pricing_plan={"pricing_mode": "live"},
        current_auto_price=39.99,
        final_sell_price_used=39.99,
        avg_30_day_price=38.0,
        roi_check_source="bbp_live",
        roi_check_value=63.0,
        webscrape_mode="data",
    )

    assert payload["review_page_status"] == "pre_review_kill"
    assert payload["bbp_monthly_units_chosen"] == "2"
    assert payload["bbp_dashboard_yes_or_no"] == "NO"
    assert payload["bbp_top_seller_names"] == "Plus Plus"
    assert payload["bbp_brand_match_flag"] == "True"
    assert payload["amazon_buybox_seller_name"] == "Plus Plus"
    assert payload["price_hist_new_30"] == "1.00"
    assert payload["fail_codes"] == "LOW_SALES_CAPITAL_IDLE_RISK"
    assert payload["hard_stop"] == "True"
