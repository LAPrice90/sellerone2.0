from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
LEGACY_DIR = ROOT / "scripts" / "flows" / "F" / "legacy_scanner_2_1"
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.F.legacy_scanner_2_1.Webscrape import (
    _amazon_buybox_seller_evidence_fields,
    _attempt_bbp_auto_login_recovery,
    _attempt_seller_central_login_from_bbp_dashboard,
    _attempt_seller_central_login_recovery,
    _build_pre_review_fail_payload,
    _economic_pre_review_hard_stop_code,
    _extract_bbp_competition_seller_rows,
    _extract_bbp_top_seller_names,
    _format_bbp_money,
    _login_option_evidence,
    _pre_review_kill_code,
    _record_seller_central_success_from_bbp_dashboard_signal,
    _seller_evidence_fields,
    _seller_central_page_evidence,
    _set_bbp_money_input,
    _wait_for_visible_bbp_frame_or_container,
    _write_seller_central_page_pull,
    choose_units_with_amazon_guardrail,
    login_to_buybotpro,
)
from scripts.flows.F.seller_central_login_recovery import (
    SellerCentralCodeResult,
    append_seller_central_login_recovery_proof,
    read_seller_central_login_attempt_control,
    load_seller_central_login_recovery_config,
    write_seller_central_login_attempt_control,
)


@pytest.fixture(autouse=True)
def _isolate_bbp_login_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BBP_LOGIN_ENV_PATH", str(tmp_path / "missing_bbp_login.env"))
    monkeypatch.setenv("BBP_LOGIN_RECOVERY_PROOF_PATH", str(tmp_path / "bbp_login_recovery_proof.csv"))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(tmp_path / "missing_seller_central_login.env"))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ATTEMPT_MODE", "1")
    monkeypatch.setenv(
        "SELLER_CENTRAL_LOGIN_ATTEMPT_CONTROL_PATH",
        str(tmp_path / "f_login_attempt_control_state.json"),
    )
    monkeypatch.setenv("F_LOGIN_CONTROLLER_LIVE_DIR", str(tmp_path / "login_controller_live"))
    monkeypatch.setenv("F_LOGIN_CONTROLLER_PAGE_PULL_DIR", str(tmp_path / "page_pulls"))
    monkeypatch.setenv(
        "SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH",
        str(tmp_path / "seller_central_login_recovery_proof.csv"),
    )


class _FakeElement:
    def __init__(
        self,
        value: str = "00,069.63",
        *,
        text: str = "",
        attrs: dict[str, str] | None = None,
        on_click: object | None = None,
    ) -> None:
        self.value = value
        self.text = text
        self.attrs = attrs or {}
        self.on_click = on_click
        self.on_enter: object | None = None
        self.clicked = False
        self.sent: list[tuple[object, ...]] = []

    def click(self) -> None:
        self.clicked = True
        if callable(self.on_click):
            self.on_click()

    def clear(self) -> None:
        self.value = ""

    def send_keys(self, *values: object) -> None:
        self.sent.append(values)
        if any(value == "\ue007" for value in values) and callable(self.on_enter):
            self.on_enter()
            return
        if (
            len(values) == 1
            and isinstance(values[0], str)
            and not ("\ue000" <= values[0][:1] <= "\uf8ff")
        ):
            self.value += values[0]
            return
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


class _FakeNoValueElement(_FakeElement):
    js_value_blocked = True

    def send_keys(self, *values: object) -> None:
        self.sent.append(values)


class _FakeEnterBlockedElement(_FakeElement):
    def send_keys(self, *values: object) -> None:
        self.sent.append(values)
        if any(value == "\ue007" for value in values):
            raise RuntimeError("enter blocked")
        return super().send_keys(*values)


class _FakeSellerCentralPagePullDriver:
    title = "Amazon Sign In"
    current_url = "https://sellercentral.amazon.co.uk/ap/signin"

    def __init__(self) -> None:
        self.password = _FakeElement("", attrs={"id": "ap_password", "name": "password", "type": "password"})
        self.submit = _FakeElement("", attrs={"id": "signInSubmit", "type": "submit"})
        self.hidden = _FakeElement(
            "very-secret-hidden-token-value",
            attrs={"name": "appActionToken", "type": "hidden"},
        )

    def find_elements(self, _by: object, selector: str) -> list[_FakeElement]:
        if selector == "body":
            return [_FakeElement("", text="Amazon Sign in password Sign in with a passkey")]
        if selector == "input,button,select,textarea,a":
            return [self.hidden, self.password, self.submit]
        if selector in {'//*[@id="ap_password"]', "input#ap_password", "input[name='password']", "input[type='password']"}:
            return [self.password]
        if selector in {'//*[@id="signInSubmit"]', "input#signInSubmit", "input[type='submit']"}:
            return [self.submit]
        return []


class _FakeLoginDriver:
    def __init__(
        self,
        *,
        cost_ready: bool = False,
        login_fields: bool = True,
        amazon_signin_link: bool = False,
        heading_text: str | None = "Login",
        login_succeeds: bool = False,
    ) -> None:
        self.selector_calls: list[tuple[object, str]] = []
        self.email = _FakeElement("")
        self.password = _FakeElement("")
        self.button = _FakeElement("", on_click=self._complete_login if login_succeeds else None)
        self.heading = _FakeElement("", text=heading_text or "")
        self.cost_ready = cost_ready
        self.login_fields = login_fields
        self.amazon_signin_link = amazon_signin_link
        self.heading_text = heading_text
        self.frame_ready = False
        self.refresh_calls = 0
        self.surface_calls = 0
        self.current_url = "https://www.amazon.co.uk/dp/B000000000"

    def find_elements(self, _by: object, selector: str) -> list[_FakeElement]:
        self.selector_calls.append((_by, selector))
        if selector == "/html/body/div/div/div[1]/div/div[1]/h1" and self.heading_text is not None:
            return [self.heading]
        if selector == '//*[@id="loginEmail"]' and self.login_fields:
            return [self.email]
        if selector == '//*[@id="loginPassword"]' and self.login_fields:
            return [self.password]
        if selector == '//*[@id="loginBtn"]' and self.login_fields:
            return [self.button]
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

    def _complete_login(self) -> None:
        self.cost_ready = True
        self.login_fields = False
        self.heading_text = None

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


class _FakeSellerCentralDriver:
    def __init__(self, *, state: str = "signin") -> None:
        self.state = state
        self.current_url = "https://sellercentral.amazon.co.uk/ap/signin"
        self.email = _FakeElement("")
        self.password = _FakeElement("")
        self.hidden_password_hint = _FakeElement(
            "",
            attrs={"id": "ap-credential-autofill-hint", "name": "password", "type": "password"},
        )
        self.otp = _FakeElement("")
        self.continue_button = _FakeElement("", on_click=self._show_password)
        self.signin_button = _FakeElement("", on_click=self._show_otp)
        self.otp_button = _FakeElement("", on_click=self._show_success)
        self.sms_button = _FakeElement("Send a text message", text="Send a text message", on_click=self._show_otp)
        self.authenticator_button = _FakeElement(
            "Send via code authenticator",
            text="Send via code authenticator",
        )
        self.dashboard = _FakeElement("", text="YES")
        self.js_click_advances = False
        self.js_enter_advances = False
        self.form_submit_advances = False
        self.scripts: list[tuple[str, tuple[object, ...]]] = []

    def _show_password(self) -> None:
        if self.state in {"email", "email_hidden_autofill"}:
            self.state = "password"

    def _show_otp(self) -> None:
        if self.state == "signin_choice":
            self.state = "mfa_choice_sms"
            return
        if self.state == "signin_authenticator_only":
            self.state = "mfa_choice_authenticator_only"
            return
        self.state = "otp"

    def _show_success(self) -> None:
        self.state = "success"

    def execute_script(self, script: str, *args: object) -> bool:
        self.scripts.append((script, args))
        if args and isinstance(args[0], _FakeElement) and len(args) >= 2 and isinstance(args[1], str):
            if getattr(args[0], "js_value_blocked", False):
                return False
            args[0].value = args[1]
            return True
        if "MouseEvent" in script:
            if self.js_click_advances:
                self._show_password()
                return True
            return False
        if "KeyboardEvent" in script:
            if self.js_enter_advances:
                self._show_password()
                return True
            return False
        if "requestSubmit" in script or "form.submit" in script:
            if self.form_submit_advances:
                self._show_password()
                return True
            return False
        return False

    def find_elements(self, _by: object, selector: str) -> list[_FakeElement]:
        if selector == "body":
            if self.state == "phone_sms_blocked":
                return [
                    _FakeElement(
                        "",
                        text=(
                            "For added security, we need to verify your phone number. "
                            "We are unable to send an SMS to the phone number ending with 598 at this time."
                        ),
                    )
                ]
            if self.state == "captcha":
                return [_FakeElement("", text="Amazon captcha enter the characters")]
            if self.state == "password_script_noise":
                return [_FakeElement("", text="Amazon Sign in password auth-mfa otp code")]
            if self.state == "password_rejected":
                return [_FakeElement("", text="Amazon Sign in There was a problem Your password is incorrect")]
            if self.state == "mfa_choice_sms":
                return [_FakeElement("", text="Choose how to receive your code. Send a text message. Send via code authenticator.")]
            if self.state == "mfa_choice_authenticator_only":
                return [_FakeElement("", text="Choose how to receive your code. Send via code authenticator.")]
            if self.state == "otp_alt":
                return [_FakeElement("", text="Authentication required. Enter your security code.")]
            if self.state == "otp":
                return [_FakeElement("", text="Two-Step Verification Enter the code")]
            if self.state == "email_hidden_autofill":
                return [_FakeElement("", text="Amazon Sign in Enter mobile number or email Continue")]
            return [_FakeElement("", text="Amazon Sign in password")]
        if selector == "input,button,a,label":
            if self.state == "mfa_choice_sms":
                return [self.authenticator_button, self.sms_button]
            if self.state == "mfa_choice_authenticator_only":
                return [self.authenticator_button]
            return []
        if selector == '//*[@id="ap_email"]' and self.state in {
            "signin",
            "email",
            "email_hidden_autofill",
            "signin_choice",
            "signin_authenticator_only",
        }:
            return [self.email]
        if selector in {"input#ap_email", "input[name='email']", "input[type='email']"} and self.state in {
            "signin",
            "email",
            "email_hidden_autofill",
            "signin_choice",
            "signin_authenticator_only",
        }:
            return [self.email]
        if selector == '//*[@id="continue"]' and self.state in {"email", "email_hidden_autofill"}:
            return [self.continue_button]
        if selector in {"input#continue", "button#continue", "input[name='continue']", "button[name='continue']"} and self.state in {
            "email",
            "email_hidden_autofill",
        }:
            return [self.continue_button]
        if selector == '//*[@id="ap_password"]' and self.state == "email_hidden_autofill":
            return [self.hidden_password_hint]
        if selector in {"input#ap_password", "input[name='password']", "input[type='password']"} and self.state == "email_hidden_autofill":
            return [self.hidden_password_hint]
        if selector == '//*[@id="ap_password"]' and self.state in {
            "signin",
            "password",
            "password_script_noise",
            "password_rejected",
            "signin_choice",
            "signin_authenticator_only",
        }:
            return [self.password]
        if selector == '//*[@id="signInSubmit"]' and self.state in {
            "signin",
            "password",
            "password_script_noise",
            "password_rejected",
            "signin_choice",
            "signin_authenticator_only",
        }:
            return [self.signin_button]
        if selector == '//*[@id="auth-mfa-otpcode"]' and self.state == "otp":
            return [self.otp]
        if selector == "input[name='otpCode']" and self.state == "otp_alt":
            return [self.otp]
        if selector == '//*[@id="auth-signin-button"]' and self.state == "otp":
            return [self.otp_button]
        if selector == "button[type='submit']" and self.state == "otp_alt":
            return [self.otp_button]
        if selector == "#dashboardYesOrNo" and self.state == "success":
            return [self.dashboard]
        return []


class _FakeSwitchTo:
    def __init__(self, driver: "_FakeTabbedSellerCentralDriver") -> None:
        self.driver = driver

    def window(self, handle: str) -> None:
        if handle not in self.driver.window_handles:
            raise ValueError(f"unknown handle {handle}")
        self.driver.current_window_handle = handle
        self.driver.in_frame = False

    def default_content(self) -> None:
        self.driver.in_frame = False

    def frame(self, _frame: object) -> None:
        self.driver.in_frame = True


class _FakeTabbedSellerCentralDriver:
    def __init__(self, *, seller_state: str = "signin", open_tab: bool = True) -> None:
        self.window_handles = ["bbp"]
        self.current_window_handle = "bbp"
        self.in_frame = True
        self.open_tab = open_tab
        self.seller_state = seller_state
        self.switch_to = _FakeSwitchTo(self)
        self.frame = _FakeElement("frame")
        self.cost = _FakeElement("1")
        self.dashboard = _FakeElement("LOGIN", text="LOGIN", on_click=self._open_seller_tab)
        self.email = _FakeElement("")
        self.password = _FakeElement("")
        self.otp = _FakeElement("")
        self.signin_button = _FakeElement("", on_click=self._show_otp)
        self.otp_button = _FakeElement("", on_click=self._show_success)
        self.seller_dashboard = _FakeElement("YES", text="YES")

    @property
    def current_url(self) -> str:
        if self.current_window_handle == "seller":
            if self.seller_state == "success":
                return "https://sellercentral.amazon.co.uk/home"
            return "https://sellercentral.amazon.co.uk/ap/signin"
        return "https://www.amazon.co.uk/dp/B000000000"

    def _open_seller_tab(self) -> None:
        if self.open_tab and "seller" not in self.window_handles:
            self.window_handles.append("seller")

    def _show_otp(self) -> None:
        self.seller_state = "otp"

    def _show_success(self) -> None:
        self.seller_state = "success"
        self.dashboard.value = "YES"
        self.dashboard.text = "YES"

    def execute_script(self, _script: str, *_args: object) -> bool:
        return False

    def find_element(self, by: object, selector: str) -> _FakeElement:
        elements = self.find_elements(by, selector)
        if not elements:
            raise LookupError(selector)
        return elements[0]

    def find_elements(self, _by: object, selector: str) -> list[_FakeElement]:
        if self.current_window_handle == "bbp":
            if selector == "body":
                return [_FakeElement("", text="BBP dashboard")]
            if selector == "bbp-frame":
                return [self.frame]
            if not self.in_frame:
                return []
            if selector == "#txtBuyPrice":
                return [self.cost]
            if selector == "#dashboardYesOrNo":
                return [self.dashboard]
            return []

        if selector == "body":
            if self.seller_state == "captcha":
                return [_FakeElement("", text="Amazon captcha enter the characters")]
            if self.seller_state == "otp":
                return [_FakeElement("", text="Two-Step Verification Enter the code")]
            if self.seller_state == "success":
                return [_FakeElement("", text="Seller Central dashboard")]
            return [_FakeElement("", text="Amazon Sign in password")]
        if selector == '//*[@id="ap_email"]' and self.seller_state == "signin":
            return [self.email]
        if selector == '//*[@id="ap_password"]' and self.seller_state == "signin":
            return [self.password]
        if selector == '//*[@id="signInSubmit"]' and self.seller_state == "signin":
            return [self.signin_button]
        if selector == '//*[@id="auth-mfa-otpcode"]' and self.seller_state == "otp":
            return [self.otp]
        if selector == '//*[@id="auth-signin-button"]' and self.seller_state == "otp":
            return [self.otp_button]
        if selector == "#dashboardYesOrNo" and self.seller_state == "success":
            return [self.seller_dashboard]
        return []


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


def test_set_bbp_money_input_falls_back_when_typing_not_interactable() -> None:
    class NotInteractableInput(_FakeElement):
        def send_keys(self, *values: object) -> None:
            self.sent.append(values)
            raise RuntimeError("element not interactable")

    driver = _FakeDriver()
    element = NotInteractableInput("00,069.63")

    written = _set_bbp_money_input(driver, element, 69.63, field_name="cost")

    assert written == "69.63"
    assert element.clicked is True
    assert element.value == "69.63"
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


def test_hidden_bbp_login_reports_required_when_secret_file_missing(monkeypatch, tmp_path: Path) -> None:
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
    assert driver.button.clicked is False
    proof_text = (tmp_path / "bbp_login_recovery_proof.csv").read_text(encoding="utf-8")
    assert "missing_secret_file" in proof_text


def test_hidden_bbp_login_disabled_prevents_auto_submit(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / "bbp_login.env"
    env_path.write_text(
        "\n".join(
            [
                "BBP_AUTO_LOGIN_ENABLED=0",
                "BBP_LOGIN_EMAIL=fake.user@example.test",
                "BBP_LOGIN_PASSWORD=fake-password",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BBP_LOGIN_ENV_PATH", str(env_path))
    driver = _FakeLoginDriver(cost_ready=False)
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "minimized")

    status = login_to_buybotpro(driver)

    assert status == "login_required"
    assert driver.button.clicked is False
    proof_text = (tmp_path / "bbp_login_recovery_proof.csv").read_text(encoding="utf-8")
    assert "disabled" in proof_text
    assert "fake.user@example.test" not in proof_text
    assert "fake-password" not in proof_text


def test_hidden_bbp_login_missing_credentials_blocks_safely(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / "bbp_login.env"
    env_path.write_text(
        "\n".join(
            [
                "BBP_AUTO_LOGIN_ENABLED=1",
                "BBP_LOGIN_EMAIL=",
                "BBP_LOGIN_PASSWORD=",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BBP_LOGIN_ENV_PATH", str(env_path))
    driver = _FakeLoginDriver(cost_ready=False)
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "minimized")

    status = login_to_buybotpro(driver)

    assert status == "login_required"
    assert driver.button.clicked is False
    proof_text = (tmp_path / "bbp_login_recovery_proof.csv").read_text(encoding="utf-8")
    assert "missing_credentials" in proof_text


def test_enabled_bbp_auto_login_uses_selectors_after_heading_only(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / "bbp_login.env"
    env_path.write_text(
        "\n".join(
            [
                "BBP_AUTO_LOGIN_ENABLED=1",
                "BBP_LOGIN_EMAIL=fake.user@example.test",
                "BBP_LOGIN_PASSWORD=fake-password",
                "BBP_LOGIN_HEADING_XPATH=/html/body/div/div/div[1]/div/div[1]/h1",
                'BBP_LOGIN_EMAIL_XPATH=//*[@id="loginEmail"]',
                'BBP_LOGIN_PASSWORD_XPATH=//*[@id="loginPassword"]',
                'BBP_LOGIN_BUTTON_XPATH=//*[@id="loginBtn"]',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    proof_path = tmp_path / "proof.csv"
    monkeypatch.setenv("BBP_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("BBP_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    driver = _FakeLoginDriver(cost_ready=False, login_succeeds=True)
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "minimized")

    status = login_to_buybotpro(driver)

    assert status == "submitted"
    assert driver.button.clicked is True
    assert driver.email.sent == [("fake.user@example.test",)]
    assert driver.password.sent == [("fake-password",)]
    proof_text = proof_path.read_text(encoding="utf-8")
    assert "fake.user@example.test" not in proof_text
    assert "fake-password" not in proof_text
    assert "succeeded" in proof_text


def test_bbp_auto_login_does_not_touch_login_selectors_without_heading(tmp_path: Path, monkeypatch) -> None:
    env_path = tmp_path / "bbp_login.env"
    env_path.write_text(
        "\n".join(
            [
                "BBP_AUTO_LOGIN_ENABLED=1",
                "BBP_LOGIN_EMAIL=fake.user@example.test",
                "BBP_LOGIN_PASSWORD=fake-password",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BBP_LOGIN_ENV_PATH", str(env_path))
    driver = _FakeLoginDriver(cost_ready=False, heading_text=None)

    status = _attempt_bbp_auto_login_recovery(driver, context="unit_test")

    assert status == "not_login_page"
    assert driver.button.clicked is False
    touched_selectors = [selector for _by, selector in driver.selector_calls]
    assert '//*[@id="loginEmail"]' not in touched_selectors
    assert '//*[@id="loginPassword"]' not in touched_selectors
    assert '//*[@id="loginBtn"]' not in touched_selectors


def test_seller_central_login_disabled_writes_redacted_proof(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=0",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ATTEMPT_MODE", "0")
    driver = _FakeSellerCentralDriver(state="signin")

    status = _attempt_seller_central_login_recovery(driver, context="unit_test")

    assert status == "normal_scan_only"
    assert driver.signin_button.clicked is False
    assert driver.email.sent == []
    assert driver.password.sent == []
    proof_text = proof_path.read_text(encoding="utf-8")
    assert "normal_scan_only" in proof_text
    assert "seller@example.test" not in proof_text
    assert "secret-password" not in proof_text
    control = read_seller_central_login_attempt_control()
    assert control.mode == "normal_scan_only"


def test_seller_central_manual_visible_login_wait_is_blocked_when_auto_login_is_off(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=0",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    monkeypatch.setenv("F061_LOGIN_MODE", "1")
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "visible")
    monkeypatch.setenv("F061_MANUAL_BBP_LOGIN_WAIT_SECONDS", "60")
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ATTEMPT_MODE", "0")

    def fake_wait(driver: _FakeSellerCentralDriver, _config: object, _seconds: float) -> bool:
        driver.state = "success"
        return True

    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._wait_for_seller_central_eligibility_success",
        fake_wait,
    )
    driver = _FakeSellerCentralDriver(state="signin")

    status = _attempt_seller_central_login_recovery(driver, context="dashboard_yes_no_login")

    assert status == "normal_scan_only"
    assert driver.signin_button.clicked is False
    assert driver.email.sent == []
    assert driver.password.sent == []
    proof_text = proof_path.read_text(encoding="utf-8")
    assert "manual_seller_central_login_wait" not in proof_text
    assert "manual_eligibility_signal_visible" not in proof_text
    assert "normal_scan_only" in proof_text
    assert "seller@example.test" not in proof_text
    assert "secret-password" not in proof_text


def test_seller_central_active_cooldown_prevents_login_attempt(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    config = load_seller_central_login_recovery_config()
    write_seller_central_login_attempt_control(
        config,
        mode="login_cooldown",
        reason="amazon_phone_sms_cooldown",
        source="unit_test",
        cooldown_hours=2,
    )
    driver = _FakeSellerCentralDriver(state="signin")

    status = _attempt_seller_central_login_recovery(driver, context="unit_test")

    assert status == "login_cooldown"
    assert driver.signin_button.clicked is False
    assert driver.email.sent == []
    assert driver.password.sent == []
    proof_text = proof_path.read_text(encoding="utf-8")
    assert "login_cooldown" in proof_text
    control = read_seller_central_login_attempt_control()
    assert control.mode == "login_cooldown"
    assert control.cooldown_until_utc


def test_seller_central_phone_sms_security_message_enters_cooldown(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    driver = _FakeSellerCentralDriver(state="phone_sms_blocked")

    status = _attempt_seller_central_login_recovery(driver, context="unit_test")

    assert status == "amazon_phone_sms_cooldown"
    assert driver.signin_button.clicked is False
    assert driver.email.sent == []
    assert driver.password.sent == []
    control = read_seller_central_login_attempt_control()
    assert control.mode == "login_cooldown"
    assert control.reason == "amazon_phone_sms_cooldown"
    assert control.cooldown_until_utc
    proof_text = proof_path.read_text(encoding="utf-8")
    assert "amazon_phone_sms_cooldown" in proof_text
    assert "598" not in proof_text


def test_seller_central_dashboard_signal_reconciles_manual_timeout_proof(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=0",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    config = load_seller_central_login_recovery_config()
    append_seller_central_login_recovery_proof(
        config,
        status="blocked",
        reason="manual_seller_central_login_wait_timeout",
        context="dashboard_yes_no_login",
        proof_path=proof_path,
    )

    reconciled = _record_seller_central_success_from_bbp_dashboard_signal("YES")

    proof_text = proof_path.read_text(encoding="utf-8")
    assert reconciled is True
    assert "bbp_dashboard_signal_visible_after_manual_login" in proof_text
    assert "prior_status=blocked" in proof_text
    assert "prior_reason=manual_seller_central_login_wait_timeout" in proof_text
    assert "succeeded" in proof_text
    assert "seller@example.test" not in proof_text
    assert "secret-password" not in proof_text


def test_seller_central_dashboard_signal_does_not_repeat_after_success(
    monkeypatch,
    tmp_path: Path,
) -> None:
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    config = load_seller_central_login_recovery_config()
    append_seller_central_login_recovery_proof(
        config,
        status="succeeded",
        reason="eligibility_signal_visible",
        context="dashboard_yes_no_login",
        succeeded=True,
        proof_path=proof_path,
    )

    reconciled = _record_seller_central_success_from_bbp_dashboard_signal("YES")

    assert reconciled is False
    assert len(proof_path.read_text(encoding="utf-8").splitlines()) == 2


def test_seller_central_login_submits_fresh_forwarded_code(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
                "SELLER_CENTRAL_CODE_GMAIL_LABEL=AmazonOTP",
                "SELLER_CENTRAL_CODE_WAIT_SECONDS=120",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape.wait_for_seller_central_code",
        lambda *_args, **_kwargs: SellerCentralCodeResult(
            status="found",
            reason="fresh_code_found",
            code="123456",
            message_id="msg-1",
            message_ts_utc="2026-06-01T10:00:05Z",
            age_seconds=5,
        ),
    )
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._human_sleep",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._wait_for_seller_central_eligibility_success",
        lambda driver, _config, _seconds: driver.state == "success",
    )
    marked_messages: list[str] = []
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape.mark_seller_central_code_message_used",
        lambda result, **_kwargs: marked_messages.append(result.message_id),
    )
    driver = _FakeSellerCentralDriver(state="signin")

    status = _attempt_seller_central_login_recovery(driver, context="unit_test")

    assert status == "succeeded"
    assert driver.signin_button.clicked is True
    assert driver.otp_button.clicked is True
    assert driver.email.sent == [("seller@example.test",)]
    assert driver.password.sent == [("secret-password",)]
    assert driver.otp.sent == [("123456",)]
    assert marked_messages == ["msg-1"]
    proof_text = proof_path.read_text(encoding="utf-8")
    assert "succeeded" in proof_text
    assert "seller@example.test" not in proof_text
    assert "secret-password" not in proof_text
    assert "123456" not in proof_text


def test_seller_central_page_evidence_detects_alternate_otp_page(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / "seller_central_login.env"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    config = load_seller_central_login_recovery_config()
    driver = _FakeSellerCentralDriver(state="otp_alt")

    evidence = _seller_central_page_evidence(driver, config)

    assert evidence["otp_detected"] is True
    assert "otp_text" in evidence["page_hint"]
    assert "otp_field" in evidence["page_hint"]


def test_seller_central_page_evidence_does_not_treat_password_script_noise_as_otp(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "seller_central_login.env"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    config = load_seller_central_login_recovery_config()
    driver = _FakeSellerCentralDriver(state="password_script_noise")

    evidence = _seller_central_page_evidence(driver, config)

    assert evidence["otp_detected"] is False
    assert "otp_text" not in evidence["page_hint"]
    assert "password_field" in evidence["page_hint"]


def test_seller_central_page_pull_redacts_hidden_values_and_labels_passkey_page(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "seller_central_login.env"
    pull_dir = tmp_path / "page_pulls"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("F_LOGIN_CONTROLLER_PAGE_PULL_DIR", str(pull_dir))
    config = load_seller_central_login_recovery_config()
    driver = _FakeSellerCentralPagePullDriver()

    paths = _write_seller_central_page_pull(driver, config, context="unit_test", reason="no_fresh_code")

    payload = (Path(paths["latest_json_path"]).read_text(encoding="utf-8"))
    assert "password_or_passkey_page" in payload
    assert "passkey_option" in payload
    assert "very-secret-hidden-token-value" not in payload
    assert "<redacted-hidden>" in payload


def test_seller_central_email_continue_page_ignores_hidden_password_hint(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "seller_central_login.env"
    pull_dir = tmp_path / "page_pulls"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("F_LOGIN_CONTROLLER_PAGE_PULL_DIR", str(pull_dir))
    config = load_seller_central_login_recovery_config()
    driver = _FakeSellerCentralDriver(state="email_hidden_autofill")

    evidence = _seller_central_page_evidence(driver, config)
    paths = _write_seller_central_page_pull(
        driver,
        config,
        context="unit_test",
        reason="email_continue_not_advanced",
    )

    payload = Path(paths["latest_json_path"]).read_text(encoding="utf-8")
    assert "email_field" in evidence["page_hint"]
    assert "continue_button" in evidence["page_hint"]
    assert "password_field" not in evidence["page_hint"]
    assert "email_continue_page" in payload
    assert "password_page" not in payload
    assert "secret-password" not in payload


def test_seller_central_login_selects_sms_delivery_before_waiting_for_code(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
                "SELLER_CENTRAL_CODE_GMAIL_LABEL=AmazonOTP",
                "SELLER_CENTRAL_CODE_WAIT_SECONDS=120",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape.wait_for_seller_central_code",
        lambda *_args, **_kwargs: SellerCentralCodeResult(
            status="found",
            reason="fresh_code_found",
            code="123456",
            message_id="msg-1",
            message_ts_utc="2026-06-01T10:00:05Z",
            age_seconds=5,
        ),
    )
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._human_sleep",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._wait_for_seller_central_eligibility_success",
        lambda driver, _config, _seconds: driver.state == "success",
    )
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape.mark_seller_central_code_message_used",
        lambda *_args, **_kwargs: None,
    )
    driver = _FakeSellerCentralDriver(state="signin_choice")

    status = _attempt_seller_central_login_recovery(driver, context="unit_test")

    assert status == "succeeded"
    assert driver.sms_button.clicked is True
    assert driver.authenticator_button.clicked is False
    proof_text = proof_path.read_text(encoding="utf-8")
    assert "sms_delivery_option_selected" in proof_text
    assert "otp_code_submitted" in proof_text
    assert "succeeded" in proof_text
    assert "123456" not in proof_text


def test_seller_central_login_blocks_authenticator_only_without_guessing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    pull_dir = tmp_path / "page_pulls"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    monkeypatch.setenv("F_LOGIN_CONTROLLER_PAGE_PULL_DIR", str(pull_dir))
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._human_sleep",
        lambda *_args, **_kwargs: None,
    )
    driver = _FakeSellerCentralDriver(state="signin_authenticator_only")

    status = _attempt_seller_central_login_recovery(driver, context="unit_test")

    assert status == "authenticator_only_no_sms_option"
    assert driver.authenticator_button.clicked is False
    proof_text = proof_path.read_text(encoding="utf-8")
    assert "authenticator_only_no_sms_option" in proof_text
    control = read_seller_central_login_attempt_control()
    assert control.mode == "login_cooldown"
    assert control.reason == "authenticator_only_no_sms_option"
    assert control.cooldown_until_utc


def test_seller_central_login_labels_signin_page_after_credentials(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    pull_dir = tmp_path / "page_pulls"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
                "SELLER_CENTRAL_CODE_WAIT_SECONDS=0.01",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    monkeypatch.setenv("F_LOGIN_CONTROLLER_PAGE_PULL_DIR", str(pull_dir))
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._human_sleep",
        lambda *_args, **_kwargs: None,
    )
    driver = _FakeSellerCentralDriver(state="signin")
    driver.signin_button.on_click = lambda: setattr(driver, "state", "password_script_noise")

    status = _attempt_seller_central_login_recovery(driver, context="unit_test")

    assert status == "submit_not_accepted"
    proof_text = proof_path.read_text(encoding="utf-8")
    assert "submit_not_accepted" in proof_text
    assert "otp_page_not_detected" not in proof_text
    latest_pull = (pull_dir / "latest_seller_central_page_pull.json").read_text(encoding="utf-8")
    assert "password_or_passkey_page" in latest_pull or "password_page" in latest_pull


def test_seller_central_login_records_password_not_entered_before_submit(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    pull_dir = tmp_path / "page_pulls"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
                "SELLER_CENTRAL_CODE_WAIT_SECONDS=0.01",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    monkeypatch.setenv("F_LOGIN_CONTROLLER_PAGE_PULL_DIR", str(pull_dir))
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._human_sleep",
        lambda *_args, **_kwargs: None,
    )
    driver = _FakeSellerCentralDriver(state="signin")
    driver.password = _FakeNoValueElement("")

    status = _attempt_seller_central_login_recovery(driver, context="unit_test")

    assert status == "password_not_entered"
    assert driver.signin_button.clicked is False
    proof_text = proof_path.read_text(encoding="utf-8")
    assert "password_not_entered" in proof_text
    assert "password_value_before_submit=empty" in proof_text
    assert "secret-password" not in proof_text


def test_seller_central_login_records_email_continue_not_advanced(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    pull_dir = tmp_path / "page_pulls"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
                "SELLER_CENTRAL_CODE_WAIT_SECONDS=0.01",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    monkeypatch.setenv("F_LOGIN_CONTROLLER_PAGE_PULL_DIR", str(pull_dir))
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._human_sleep",
        lambda *_args, **_kwargs: None,
    )
    driver = _FakeSellerCentralDriver(state="email_hidden_autofill")
    driver.continue_button.on_click = lambda: None

    status = _attempt_seller_central_login_recovery(driver, context="unit_test")

    assert status == "email_continue_not_advanced"
    proof_text = proof_path.read_text(encoding="utf-8")
    assert "email_continue_not_advanced" in proof_text
    assert "password_not_entered" not in proof_text
    latest_pull = (pull_dir / "latest_seller_central_page_pull.json").read_text(encoding="utf-8")
    assert "email_continue_page" in latest_pull
    assert "secret-password" not in proof_text


def test_seller_central_login_finalizes_email_before_continue(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    pull_dir = tmp_path / "page_pulls"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
                "SELLER_CENTRAL_CODE_WAIT_SECONDS=0.01",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    monkeypatch.setenv("F_LOGIN_CONTROLLER_PAGE_PULL_DIR", str(pull_dir))
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._human_sleep",
        lambda *_args, **_kwargs: None,
    )
    driver = _FakeSellerCentralDriver(state="email_hidden_autofill")
    driver.continue_button.on_click = lambda: None

    status = _attempt_seller_central_login_recovery(driver, context="unit_test")

    assert status == "email_continue_not_advanced"
    proof_text = proof_path.read_text(encoding="utf-8")
    assert "email_finalize=1" in proof_text
    assert any("blur && el.blur" in script for script, _args in driver.scripts)
    assert "secret-password" not in proof_text


def test_seller_central_login_uses_enter_when_continue_click_stays_on_email_page(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    pull_dir = tmp_path / "page_pulls"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
                "SELLER_CENTRAL_CODE_WAIT_SECONDS=0.01",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    monkeypatch.setenv("F_LOGIN_CONTROLLER_PAGE_PULL_DIR", str(pull_dir))
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._human_sleep",
        lambda *_args, **_kwargs: None,
    )
    driver = _FakeSellerCentralDriver(state="email_hidden_autofill")
    driver.continue_button.on_click = lambda: None
    driver.email.on_enter = driver._show_password

    status = _attempt_seller_central_login_recovery(driver, context="unit_test")

    assert status != "email_continue_not_advanced"
    assert driver.continue_button.clicked is True
    assert any("\ue007" in values for values in driver.email.sent)
    assert driver.signin_button.clicked is True
    proof_text = proof_path.read_text(encoding="utf-8")
    assert "email_continue_not_advanced" not in proof_text
    assert "secret-password" not in proof_text


def test_seller_central_login_uses_js_click_when_normal_continue_click_sticks(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    pull_dir = tmp_path / "page_pulls"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
                "SELLER_CENTRAL_CODE_WAIT_SECONDS=0.01",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    monkeypatch.setenv("F_LOGIN_CONTROLLER_PAGE_PULL_DIR", str(pull_dir))
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._human_sleep",
        lambda *_args, **_kwargs: None,
    )
    driver = _FakeSellerCentralDriver(state="email_hidden_autofill")
    driver.continue_button.on_click = lambda: None
    driver.js_click_advances = True

    status = _attempt_seller_central_login_recovery(driver, context="unit_test")

    assert status != "email_continue_not_advanced"
    assert driver.continue_button.clicked is True
    assert driver.signin_button.clicked is True
    proof_text = proof_path.read_text(encoding="utf-8")
    assert "email_continue_not_advanced" not in proof_text
    assert "secret-password" not in proof_text


def test_seller_central_login_uses_js_enter_when_normal_enter_is_blocked(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    pull_dir = tmp_path / "page_pulls"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
                "SELLER_CENTRAL_CODE_WAIT_SECONDS=0.01",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    monkeypatch.setenv("F_LOGIN_CONTROLLER_PAGE_PULL_DIR", str(pull_dir))
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._human_sleep",
        lambda *_args, **_kwargs: None,
    )
    driver = _FakeSellerCentralDriver(state="email_hidden_autofill")
    driver.email = _FakeEnterBlockedElement("")
    driver.continue_button.on_click = lambda: None
    driver.js_enter_advances = True

    status = _attempt_seller_central_login_recovery(driver, context="unit_test")

    assert status != "email_continue_not_advanced"
    assert driver.continue_button.clicked is True
    assert driver.signin_button.clicked is True
    proof_text = proof_path.read_text(encoding="utf-8")
    assert "email_continue_not_advanced" not in proof_text
    assert "secret-password" not in proof_text


def test_seller_central_login_records_password_rejected_when_amazon_says_incorrect(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    pull_dir = tmp_path / "page_pulls"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
                "SELLER_CENTRAL_CODE_WAIT_SECONDS=0.01",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    monkeypatch.setenv("F_LOGIN_CONTROLLER_PAGE_PULL_DIR", str(pull_dir))
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._human_sleep",
        lambda *_args, **_kwargs: None,
    )
    driver = _FakeSellerCentralDriver(state="signin")
    driver.signin_button.on_click = lambda: setattr(driver, "state", "password_rejected")

    status = _attempt_seller_central_login_recovery(driver, context="unit_test")

    assert status == "password_rejected"
    proof_text = proof_path.read_text(encoding="utf-8")
    assert "password_rejected" in proof_text
    assert "secret-password" not in proof_text


def test_seller_central_login_submits_code_on_alternate_otp_page(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
                "SELLER_CENTRAL_CODE_GMAIL_LABEL=AmazonOTP",
                "SELLER_CENTRAL_CODE_WAIT_SECONDS=120",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape.wait_for_seller_central_code",
        lambda *_args, **_kwargs: SellerCentralCodeResult(
            status="found",
            reason="fresh_code_found",
            code="123456",
            message_id="msg-1",
            message_ts_utc="2026-06-01T10:00:05Z",
            age_seconds=5,
        ),
    )
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._human_sleep",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._wait_for_seller_central_eligibility_success",
        lambda driver, _config, _seconds: driver.state == "success",
    )
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape.mark_seller_central_code_message_used",
        lambda *_args, **_kwargs: None,
    )
    driver = _FakeSellerCentralDriver(state="otp_alt")

    status = _attempt_seller_central_login_recovery(driver, context="unit_test")

    assert status == "succeeded"
    assert driver.otp_button.clicked is True
    assert driver.otp.sent == [("123456",)]
    proof_text = proof_path.read_text(encoding="utf-8")
    assert "otp_code_submitted" in proof_text
    assert "succeeded" in proof_text
    assert "123456" not in proof_text


def test_seller_central_login_records_signin_page_after_code_wait(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
                "SELLER_CENTRAL_CODE_GMAIL_LABEL=AmazonOTP",
                "SELLER_CENTRAL_CODE_WAIT_SECONDS=120",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._human_sleep",
        lambda *_args, **_kwargs: None,
    )
    driver = _FakeSellerCentralDriver(state="signin")

    def fake_wait(*_args, **_kwargs):
        driver.state = "signin"
        return SellerCentralCodeResult(status="expired", reason="no_fresh_code")

    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape.wait_for_seller_central_code",
        fake_wait,
    )

    status = _attempt_seller_central_login_recovery(driver, context="unit_test")

    assert status == "expired"
    proof_text = proof_path.read_text(encoding="utf-8")
    assert "signin_or_passkey_page_after_code_wait" in proof_text


def test_bbp_dashboard_login_handoff_uses_existing_browser_tab(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
                "SELLER_CENTRAL_CODE_GMAIL_LABEL=AmazonOTP",
                "SELLER_CENTRAL_CODE_WAIT_SECONDS=120",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape.wait_for_seller_central_code",
        lambda *_args, **_kwargs: SellerCentralCodeResult(
            status="found",
            reason="fresh_code_found",
            code="123456",
            message_id="msg-1",
            message_ts_utc="2026-06-01T10:00:05Z",
            age_seconds=5,
        ),
    )
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._human_sleep",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._wait_for_seller_central_eligibility_success",
        lambda driver, _config, _seconds: driver.seller_state == "success",
    )
    marked_messages: list[str] = []
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape.mark_seller_central_code_message_used",
        lambda result, **_kwargs: marked_messages.append(result.message_id),
    )
    driver = _FakeTabbedSellerCentralDriver()

    status, dashboard_value = _attempt_seller_central_login_from_bbp_dashboard(
        driver,
        driver.dashboard,
        context="dashboard_yes_no_login",
    )

    assert status == "succeeded"
    assert dashboard_value == "YES"
    assert driver.current_window_handle == "bbp"
    assert driver.in_frame is True
    assert "seller" in driver.window_handles
    assert driver.signin_button.clicked is True
    assert driver.otp_button.clicked is True
    assert driver.email.sent == [("seller@example.test",)]
    assert driver.password.sent == [("secret-password",)]
    assert driver.otp.sent == [("123456",)]
    assert marked_messages == ["msg-1"]
    proof_text = proof_path.read_text(encoding="utf-8")
    assert "succeeded" in proof_text
    assert "seller@example.test" not in proof_text
    assert "secret-password" not in proof_text
    assert "123456" not in proof_text


def test_bbp_dashboard_login_handoff_stays_scan_only_when_auto_login_is_off(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=0",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    monkeypatch.setenv("F061_LOGIN_MODE", "1")
    monkeypatch.setenv("F061_BACKGROUND_BROWSER_MODE", "visible")
    monkeypatch.setenv("F061_MANUAL_BBP_LOGIN_WAIT_SECONDS", "0.01")
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ATTEMPT_MODE", "0")
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._human_sleep",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._wait_for_seller_central_eligibility_success",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._wait_for_bbp_dashboard_signal_after_seller_central",
        lambda *_args, **_kwargs: "YES",
    )
    driver = _FakeTabbedSellerCentralDriver()

    status, dashboard_value = _attempt_seller_central_login_from_bbp_dashboard(
        driver,
        driver.dashboard,
        context="dashboard_yes_no_login",
    )

    proof_text = proof_path.read_text(encoding="utf-8")
    assert status == "normal_scan_only"
    assert dashboard_value == ""
    assert "manual_seller_central_login_wait_timeout" not in proof_text
    assert "bbp_dashboard_signal_visible_after_seller_central_return" not in proof_text
    assert "normal_scan_only" in proof_text
    assert "seller@example.test" not in proof_text
    assert "secret-password" not in proof_text


def test_bbp_dashboard_login_handoff_records_missing_seller_tab(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ATTEMPT_MODE", "1")
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._human_sleep",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._seller_central_browser_wait_seconds",
        lambda *_args, **_kwargs: 0.0,
    )
    driver = _FakeTabbedSellerCentralDriver(open_tab=False)

    status, dashboard_value = _attempt_seller_central_login_from_bbp_dashboard(
        driver,
        driver.dashboard,
        context="dashboard_yes_no_login",
    )

    assert status == "seller_central_tab_missing"
    assert dashboard_value == ""
    assert driver.current_window_handle == "bbp"
    assert driver.in_frame is True
    proof_text = proof_path.read_text(encoding="utf-8")
    assert "seller_central_tab_missing" in proof_text


def test_bbp_dashboard_login_handoff_freezes_before_click_when_attempt_mode_off(monkeypatch, tmp_path: Path) -> None:
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    monkeypatch.delenv("SELLER_CENTRAL_LOGIN_ATTEMPT_MODE", raising=False)
    driver = _FakeTabbedSellerCentralDriver(open_tab=True)

    status, dashboard_value = _attempt_seller_central_login_from_bbp_dashboard(
        driver,
        driver.dashboard,
        context="dashboard_yes_no_login",
    )

    assert status == "normal_scan_only"
    assert dashboard_value == ""
    assert driver.current_window_handle == "bbp"
    assert driver.in_frame is True
    assert getattr(driver.dashboard, "clicked", False) is False
    proof_text = proof_path.read_text(encoding="utf-8")
    assert "controller_freeze_before_bbp_login_click=1" in proof_text
    assert "normal_scan_only" in proof_text


def test_bbp_dashboard_login_handoff_returns_to_bbp_on_manual_challenge(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / "seller_central_login.env"
    proof_path = tmp_path / "seller_central_login_recovery_proof.csv"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_RECOVERY_PROOF_PATH", str(proof_path))
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ATTEMPT_MODE", "1")
    monkeypatch.setattr(
        "scripts.flows.F.legacy_scanner_2_1.Webscrape._human_sleep",
        lambda *_args, **_kwargs: None,
    )
    driver = _FakeTabbedSellerCentralDriver(seller_state="captcha")

    status, dashboard_value = _attempt_seller_central_login_from_bbp_dashboard(
        driver,
        driver.dashboard,
        context="dashboard_yes_no_login",
    )

    assert status == "manual_challenge_required"
    assert dashboard_value == ""
    assert driver.current_window_handle == "bbp"
    assert driver.in_frame is True
    assert driver.email.sent == []
    assert driver.password.sent == []
    proof_text = proof_path.read_text(encoding="utf-8")
    assert "manual_challenge_required" in proof_text
    assert "seller@example.test" not in proof_text
    assert "secret-password" not in proof_text


def test_seller_central_manual_challenge_blocks_without_credentials(monkeypatch, tmp_path: Path) -> None:
    env_path = tmp_path / "seller_central_login.env"
    env_path.write_text(
        "\n".join(
            [
                "SELLER_CENTRAL_AUTO_LOGIN_ENABLED=1",
                "SELLER_CENTRAL_LOGIN_EMAIL=seller@example.test",
                "SELLER_CENTRAL_LOGIN_PASSWORD=secret-password",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SELLER_CENTRAL_LOGIN_ENV_PATH", str(env_path))
    driver = _FakeSellerCentralDriver(state="captcha")

    status = _attempt_seller_central_login_recovery(driver, context="unit_test")

    assert status == "manual_challenge_required"


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
