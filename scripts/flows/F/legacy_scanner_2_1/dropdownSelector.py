from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import logging
import os
import random
import time

logger = logging.getLogger("Dropdown Selector")


def _clamp(value, lo, hi):
    try:
        return max(lo, min(hi, float(value)))
    except Exception:
        return lo


def _env_float(name, default):
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return float(default)


_TIMING_SCALE = _env_float("F_REVIEWS_TIMING_SCALE", 1.0)
_DROPDOWN_WAIT_CAP = _env_float("F_REVIEWS_DROPDOWN_WAIT_CAP_SEC", 3.0)


def _scaled_wait(seconds, *, floor=0.4, cap=None):
    scaled = _clamp(float(seconds) * _TIMING_SCALE, floor, 60.0)
    local_cap = _DROPDOWN_WAIT_CAP if cap is None else float(cap)
    if local_cap > 0:
        scaled = min(scaled, local_cap)
    return max(floor, scaled)


def _per_path_wait(total_wait_seconds, path_count, *, floor=0.7, cap=2.4):
    total = _scaled_wait(total_wait_seconds, floor=floor, cap=max(total_wait_seconds, cap))
    return _clamp(total / max(int(path_count), 1), floor, cap)


def _human_pause(low=0.10, high=0.30):
    lo = _scaled_wait(low, floor=0.05, cap=1.2)
    hi = _scaled_wait(high, floor=lo + 0.02, cap=1.8)
    if hi < lo:
        hi = lo
    time.sleep(random.uniform(lo, hi))


def _read_filter_info_text(driver):
    try:
        return driver.find_element(By.XPATH, "//*[@id='filter-info-section']/div").text.strip()
    except Exception:
        return ""


def _reviews_page_ready(driver):
    markers = [
        (By.ID, "cm_cr-review_list"),
        (By.ID, "cm-cr-dp-review-list"),
        (By.CSS_SELECTOR, "#filter-info-section"),
        (By.CSS_SELECTOR, "[data-hook='cr-filter-info-review-rating-count']"),
    ]
    for by, locator in markers:
        try:
            if driver.find_elements(by, locator):
                return True
        except Exception:
            continue
    return False


def _wait_for_filter_refresh(driver, logger, *, before_text, timeout_seconds=6):
    """
    Wait until filter-info text changes after selecting a variant option.
    Returns one of: changed, steady, missing.
    """
    before_norm = str(before_text or "").strip()
    try:
        wait_seconds = _scaled_wait(timeout_seconds, floor=2.5, cap=10.0)
        WebDriverWait(driver, wait_seconds).until(
            lambda d: (_read_filter_info_text(d) != before_norm and _read_filter_info_text(d) != "")
        )
        after_text = _read_filter_info_text(driver)
        logger.info(f"Filter info refreshed after dropdown selection: {after_text[:120]}")
        return "changed"
    except TimeoutException:
        after_text = _read_filter_info_text(driver)
        after_norm = str(after_text or "").strip()
        if after_norm == "":
            logger.warning("Variant dropdown selection did not refresh filter info before timeout.")
            return "missing"
        if after_norm != before_norm:
            logger.info(f"Filter info changed late after timeout window: {after_text[:120]}")
            return "changed"
        logger.info("Variant dropdown selection left filter info unchanged; continuing in soft-selected mode.")
        return "steady"


def _find_native_select(driver, ids):
    for select_id in ids:
        try:
            el = driver.find_element(By.ID, select_id)
            if el.is_displayed():
                return el
        except Exception:
            continue
    return None


def _set_native_select_option(driver, logger, *, ids, skip_texts=(), prefer_texts=()):
    """
    Select an option from a native <select> filter control.
    Returns a tuple: (found_select, changed_or_selected)
    """
    select_el = _find_native_select(driver, ids)
    if select_el is None:
        return False, False

    select_ctl = Select(select_el)
    options = select_ctl.options
    if len(options) <= 1:
        return True, False

    skip_norm = {str(v).strip().lower() for v in skip_texts if str(v).strip()}
    prefer_norm = [str(v).strip().lower() for v in prefer_texts if str(v).strip()]

    # Prefer explicit targets first (for example "Most recent").
    for pref in prefer_norm:
        for opt in options:
            text = (opt.text or "").strip()
            if not text:
                continue
            if pref in text.lower():
                select_ctl.select_by_visible_text(text)
                logger.info(f"Selected native dropdown option by preference: {text}")
                _human_pause(0.08, 0.20)
                return True, True

    # Otherwise pick first option that is not in skip list.
    for opt in options:
        text = (opt.text or "").strip()
        if not text:
            continue
        if text.lower() in skip_norm:
            continue
        select_ctl.select_by_visible_text(text)
        logger.info(f"Selected native dropdown option: {text}")
        _human_pause(0.08, 0.20)
        return True, True

    return True, False


def _click_labelled_dropdown_button(driver, logger, *, label_text, current_text, wait_seconds=10):
    """
    Click the dropdown button by its nearby label text.
    This avoids brittle nth-child / fixed-id lookups.
    """
    label_norm = label_text.strip()
    current_norm = current_text.strip()
    button_xpaths = [
        # Label + nearby button text in same filter row/container.
        (
            f"//span[normalize-space()='{label_norm}']"
            f"/ancestor::li[1]//span[contains(@class,'a-button-text') and normalize-space()='{current_norm}']"
        ),
        (
            f"//span[normalize-space()='{label_norm}']"
            f"/ancestor::div[1]//span[contains(@class,'a-button-text') and normalize-space()='{current_norm}']"
        ),
        # Fallback: find the label, then first matching button after it.
        (
            f"//span[normalize-space()='{label_norm}']"
            f"/following::span[contains(@class,'a-button-text') and normalize-space()='{current_norm}'][1]"
        ),
    ]

    per_xpath_wait = _per_path_wait(wait_seconds, len(button_xpaths), floor=0.7, cap=2.5)
    for xpath in button_xpaths:
        try:
            button = WebDriverWait(driver, per_xpath_wait).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            if button.is_displayed():
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                button.click()
                _human_pause(0.10, 0.25)
                logger.info(f"Clicked dropdown button '{current_norm}' near '{label_norm}' using xpath: {xpath}")
                return True
        except TimeoutException:
            continue
        except Exception as exc:
            logger.warning(f"Failed to click labelled dropdown button using xpath={xpath}: {exc}")
    return False


def _select_dropdown_option_from_open_popover(driver, logger, *, skip_texts, wait_seconds=8):
    """
    After a dropdown opens, select the first visible option that is not in skip_texts.
    """
    skip_norm = {str(text).strip().lower() for text in skip_texts if str(text).strip()}
    option_xpaths = [
        # Common Amazon popover list structure.
        "//div[contains(@class,'a-popover') and not(contains(@style,'display: none'))]"
        "//li[.//a and not(contains(@class,'a-dropdown-item-hidden')) and not(contains(@class,'a-disabled'))]//a",
        # Generic fallback for active listboxes.
        "//ul[contains(@class,'a-nostyle')]//li[.//a and not(contains(@class,'a-disabled'))]//a",
    ]

    per_xpath_wait = _per_path_wait(wait_seconds, len(option_xpaths), floor=0.7, cap=2.3)
    for xpath in option_xpaths:
        try:
            options = WebDriverWait(driver, per_xpath_wait).until(
                EC.presence_of_all_elements_located((By.XPATH, xpath))
            )
        except TimeoutException:
            continue
        except Exception as exc:
            logger.warning(f"Failed while locating dropdown options via xpath={xpath}: {exc}")
            continue

        for option in options:
            try:
                text = option.text.strip()
                text_norm = text.lower()
                if not text:
                    continue
                if text_norm in skip_norm:
                    continue
                option.click()
                _human_pause(0.10, 0.25)
                logger.info(f"Selected dropdown option: {text}")
                return True
            except StaleElementReferenceException:
                continue
            except Exception as exc:
                logger.warning(f"Failed clicking dropdown option: {exc}")
                continue

    return False


def _set_dropdown_by_label(driver, logger, *, label_text, button_text, dropdown_name):
    """
    Try dynamic labelled selection first. Fallback to legacy path list if needed.
    """
    if _click_labelled_dropdown_button(
        driver,
        logger,
        label_text=label_text,
        current_text=button_text,
    ):
        if _select_dropdown_option_from_open_popover(
            driver,
            logger,
            skip_texts=[button_text, "All variants", "Top reviews"],
        ):
            return True

    # Legacy fallback path list remains for backwards compatibility.
    if dropdown_name == "All variants":
        fallback_paths = [
            '//*[@id="a-popover-2"]/div/div/ul/li[2]',
            '//*[@id="format-type-dropdown_1"]',
            '#a-popover-2 > div > div > ul > li:nth-child(2)',
            '#format-type-dropdown_1',
        ]
    else:
        fallback_paths = [
            '//*[@id="a-popover-3"]/div/div/ul/li[2]',
            '//*[@id="sort-order-dropdown_1"]',
            '#a-popover-3 > div > div > ul > li:nth-child(2)',
            '#sort-order-dropdown_1',
        ]
    return interact_with_dropdown(driver, fallback_paths, logger, dropdown_name, wait_seconds=7)


def test_variant_dropdown(driver, url):
    """
    Handle dropdowns dynamically on the reviews page, trying XPaths and Selectors in order until successful.
    :param driver: Selenium WebDriver instance.
    :param url: URL of the reviews page to interact with.
    """
    logger = logging.getLogger("VariantDropdownTest")
    logger.info(f"test_variant_dropdown called with URL: {url}")
    status = {
        "variant_mode": "unknown",
        "all_variants_button_found": False,
        "all_variants_selection_success": False,
        "top_reviews_selection_success": False,
    }

    if not url:
        logger.error("URL is None or missing! Exiting function.")
        return status
    driver.get(url)

    # Step 1: Wait for the reviews page to load
    try:
        logger.info("Waiting for the reviews page to load...")
        WebDriverWait(driver, _scaled_wait(12, floor=7.0, cap=15.0)).until(
            lambda d: _reviews_page_ready(d)
        )
        logger.info("Reviews page successfully loaded.")
    except TimeoutException:
        logger.error("Timeout while waiting for the reviews page to load.")
        return status

    # Step 2: Interact with 'All variants'
    try:
        logger.info("Attempting to locate the 'All variants' button...")
        before_filter_text = _read_filter_info_text(driver)
        native_found, native_changed = _set_native_select_option(
            driver,
            logger,
            ids=["format-type-dropdown", "format-type-dropdown_1"],
            skip_texts=["All variants"],
        )

        if native_found:
            status["all_variants_button_found"] = True
            if native_changed:
                refresh_state = _wait_for_filter_refresh(
                    driver,
                    logger,
                    before_text=before_filter_text,
                )
                if refresh_state == "changed":
                    status["all_variants_selection_success"] = True
                    status["variant_mode"] = "selected"
                elif refresh_state == "steady":
                    status["all_variants_selection_success"] = True
                    status["variant_mode"] = "selected_unconfirmed"
                else:
                    status["variant_mode"] = "failed"
            else:
                status["variant_mode"] = "single"
                logger.info("Variant filter exists but has no alternate options. Treating as single-variant product.")
        else:
            # Fallback to labelled/popover logic for layouts without native <select>.
            variant_label_exists = False
            try:
                WebDriverWait(driver, _scaled_wait(3.0, floor=1.2, cap=4.0)).until(
                    EC.presence_of_element_located((By.XPATH, "//span[normalize-space()='Filter by variant type']"))
                )
                variant_label_exists = True
            except TimeoutException:
                variant_label_exists = False

            if not variant_label_exists:
                status["variant_mode"] = "single"
                logger.info("No variant filter block found. Treating as single-variant product.")
            else:
                status["all_variants_button_found"] = True
                if not _set_dropdown_by_label(
                    driver,
                    logger,
                    label_text="Filter by variant type",
                    button_text="All variants",
                    dropdown_name="All variants",
                ):
                    status["variant_mode"] = "failed"
                    logger.error("Failed to select an option from the 'All variants' dropdown.")
                else:
                    status["all_variants_selection_success"] = True
                    status["variant_mode"] = "selected"
    except TimeoutException:
        # Many products are single-ASIN and do not have an "All variants" dropdown.
        status["variant_mode"] = "single"
        logger.info("'All variants' button not found. Treating as single-variant product.")
    except NoSuchElementException:
        status["variant_mode"] = "single"
        logger.info("'All variants' button not available. Treating as single-variant product.")
    except Exception as e:
        status["variant_mode"] = "failed"
        logger.error(f"Unexpected error interacting with 'All variants': {e}")

    # Step 3: Interact with 'Top reviews'
    try:
        logger.info("Attempting to locate the 'Top reviews' button...")
        top_native_found, top_native_changed = _set_native_select_option(
            driver,
            logger,
            ids=["sort-order-dropdown", "sort-order-dropdown_1"],
            skip_texts=["Top reviews"],
            prefer_texts=["Most recent"],
        )
        if top_native_found:
            status["top_reviews_selection_success"] = top_native_changed
            if not top_native_changed:
                logger.error("Top reviews dropdown found but no alternate option selected.")
        elif _set_dropdown_by_label(
            driver,
            logger,
            label_text="Sort by reviews type",
            button_text="Top reviews",
            dropdown_name="Top reviews",
        ):
            status["top_reviews_selection_success"] = True
        else:
            logger.error("Failed to select an option from the 'Top reviews' dropdown.")
    except TimeoutException:
        logger.error("Timeout while locating or clicking the 'Top reviews' button.")
    except Exception as e:
        logger.error(f"Unexpected error interacting with 'Top reviews': {e}")

    return status


def interact_with_dropdown(driver, paths, logger, dropdown_name, wait_seconds=7):
    """
    Try multiple XPaths and CSS selectors to interact with dropdown options.
    Stops immediately after the first successful interaction.
    :param driver: Selenium WebDriver instance.
    :param paths: List of XPaths and CSS selectors to try.
    :param logger: Logger instance.
    :param dropdown_name: Name of the dropdown (e.g., 'All variants', 'Top reviews').
    :return: True if interaction succeeds, False otherwise.
    """
    per_path_wait = _per_path_wait(wait_seconds, len(paths), floor=0.7, cap=2.3)
    for path in paths:
        try:
            if path.startswith('//'):  # XPath
                element = WebDriverWait(driver, per_path_wait).until(
                    EC.presence_of_element_located((By.XPATH, path))
                )
            else:  # CSS Selector
                element = WebDriverWait(driver, per_path_wait).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, path))
                )

            if element.is_displayed():
                logger.info(f"Found {dropdown_name} option: {element.text} using {path}")
                element.click()
                _human_pause(0.10, 0.25)
                logger.info(f"Clicked {dropdown_name} option: {element.text}")
                return True  # Stop after successful interaction
        except TimeoutException:
            logger.warning(f"Timeout while trying {path} for {dropdown_name}.")
        except StaleElementReferenceException:
            logger.warning(f"Stale element reference encountered for {path}.")
        except Exception as e:
            logger.warning(f"Failed to interact with {path}: {e}")
    return False
