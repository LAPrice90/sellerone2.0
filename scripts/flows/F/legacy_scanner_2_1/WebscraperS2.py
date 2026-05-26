# WebscraperS2.py

# ---------------------------------------------------
# 1. IMPORTS
# ---------------------------------------------------
import re
import random
import time
import logging
import os
from datetime import datetime, timedelta
from urllib.parse import urlparse

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

from dropdownSelector import test_variant_dropdown

logger = logging.getLogger("Webscraper S2")


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


_TIMING_SCALE = _env_float("F_WEBSCRAPE_TIMING_SCALE", 1.0)
_LOCATOR_WAIT_CAP = _env_float("F_WEBSCRAPE_LOCATOR_WAIT_CAP_SEC", 3.0)


def _scaled_wait(seconds, *, floor=0.4, cap=None):
    scaled = _clamp(float(seconds) * _TIMING_SCALE, floor, 60.0)
    local_cap = _LOCATOR_WAIT_CAP if cap is None else float(cap)
    if local_cap > 0:
        scaled = min(scaled, local_cap)
    return max(floor, scaled)


def _locator_wait(total_wait_seconds, locator_count, *, floor=0.9, cap=2.6):
    total = _scaled_wait(total_wait_seconds, floor=floor, cap=max(total_wait_seconds, cap))
    return _clamp(total / max(int(locator_count), 1), floor, cap)


def _human_pause(low=0.15, high=0.45):
    lo = _scaled_wait(low, floor=0.05, cap=1.2)
    hi = _scaled_wait(high, floor=lo + 0.02, cap=1.8)
    if hi < lo:
        hi = lo
    time.sleep(random.uniform(lo, hi))


def _looks_like_review_block_page(driver):
    """
    Detect common anti-bot / blocked pages that do not contain the review list.
    """
    try:
        url = (driver.current_url or "").lower()
        title = (driver.title or "").lower()
    except Exception:
        url = ""
        title = ""

    blockers = [
        "/errors/validatecaptcha",
        "captcha",
        "/sorry/",
        "robot",
        "/ap/signin",
        "signin",
    ]
    if any(tok in url for tok in blockers) or any(tok in title for tok in blockers):
        return True

    try:
        body_text = driver.execute_script(
            "return (document && document.body && document.body.innerText) ? document.body.innerText.slice(0, 6000) : '';"
        )
        body = str(body_text or "").lower()
    except Exception:
        body = ""

    body_tokens = [
        "enter the characters you see below",
        "sorry, we just need to make sure you're not a robot",
        "type the characters you see in this image",
        "automated access to amazon data",
        "sign in",
        "email or mobile phone number",
        "enter your password",
    ]
    return any(tok in body for tok in body_tokens)


def _wait_for_reviews_ready(driver, timeout_seconds):
    """
    Wait for a reviews page marker that indicates the page is usable.
    Returns (ready: bool, marker: str).
    """
    deadline = time.time() + max(float(timeout_seconds), 1.0)
    markers = [
        (By.ID, "cm_cr-review_list"),
        (By.ID, "cm-cr-dp-review-list"),
        (By.CSS_SELECTOR, "#filter-info-section"),
        (By.CSS_SELECTOR, "[data-hook='cr-filter-info-review-rating-count']"),
    ]

    while time.time() < deadline:
        if _looks_like_review_block_page(driver):
            return False, "blocked"

        for by, locator in markers:
            try:
                elements = driver.find_elements(by, locator)
                if elements:
                    return True, locator
            except Exception:
                continue

        time.sleep(0.30)

    return False, "timeout"


def _extract_asin_from_url(url):
    try:
        text = str(url or "")
    except Exception:
        text = ""
    if text == "":
        return ""
    match = re.search(r"/(?:dp|gp/product|product-reviews)/([A-Z0-9]{10})(?:[/?#]|$)", text, re.IGNORECASE)
    if not match:
        return ""
    return (match.group(1) or "").upper()


def _canonical_reviews_url(raw_reviews_url, fallback_page_url):
    raw = str(raw_reviews_url or "").strip()
    fallback = str(fallback_page_url or "").strip()
    source_for_asin = raw or fallback
    asin = _extract_asin_from_url(source_for_asin)
    if asin == "":
        return raw

    preferred = raw if raw else fallback
    host = "www.amazon.co.uk"
    scheme = "https"
    try:
        parsed = urlparse(preferred)
        if parsed.netloc:
            host = parsed.netloc
        if parsed.scheme:
            scheme = parsed.scheme
    except Exception:
        pass
    return f"{scheme}://{host}/product-reviews/{asin}/ref=cm_cr_dp_d_show_all_btm?ie=UTF8&reviewerType=all_reviews"

# ---------------------------------------------------
# 2. HELPER FUNCTIONS
# ---------------------------------------------------
def extract_3_month_uk_reviews(review_text):
    """
    Returns the count of UK reviews within the last 3 months.
    If NO UK reviews are found, returns "No UK".
    """
    today = datetime.now()
    three_months_ago = today - timedelta(days=90)

    pattern = re.compile(r"Reviewed in the United Kingdom on (\d{1,2} [A-Za-z]+ \d{4})", re.IGNORECASE)
    has_any_uk = False
    recent_count = 0

    for match in pattern.finditer(review_text):
        has_any_uk = True
        date_str = match.group(1)
        # parse date
        try:
            review_date = datetime.strptime(date_str, "%d %B %Y")
            if review_date >= three_months_ago:
                recent_count += 1
        except:
            pass

    if not has_any_uk:
        return "No UK"
    return recent_count

def extract_historical_uk_reviews(review_text):
    """
    Returns the TOTAL count of UK reviews historically (any date).
    If none at all, returns 0.
    """
    pattern = re.compile(r"Reviewed in the United Kingdom on (\d{1,2} [A-Za-z]+ \d{4})", re.IGNORECASE)
    matches = pattern.findall(review_text)
    return len(matches)

def extract_date(product_info_text):
    """
    Extracts a date from the provided text using multiple regex patterns.
    Returns the date as YYYY-MM-DD (str) or None if not found.
    """
    date_patterns = [
        r"\b(\d{1,2} [A-Za-z]{3,9}\.? \d{4})\b",  # e.g., 5 Oct. 2011
        r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b",         # e.g., 05/10/2011
        r"\b(\d{4}-\d{1,2}-\d{1,2})\b"            # e.g., 2011-10-05
    ]
    for pattern in date_patterns:
        match = re.search(pattern, product_info_text)
        if match:
            raw_date = match.group(1)
            try:
                return datetime.strptime(raw_date, "%d %b. %Y").strftime("%Y-%m-%d")
            except ValueError:
                try:
                    return datetime.strptime(raw_date, "%d %B %Y").strftime("%Y-%m-%d")
                except ValueError:
                    try:
                        return datetime.strptime(raw_date, "%d/%m/%Y").strftime("%Y-%m-%d")
                    except ValueError:
                        try:
                            return datetime.strptime(raw_date, "%Y-%m-%d").strftime("%Y-%m-%d")
                        except ValueError:
                            continue
    return None

def validate_scraped_data(data):
    """
    Validates scraped data to ensure all required keys are present.
    Missing keys are assigned 'N/A'.
    """
    required_keys = [
        "scan_date",
        "main_title",
        "monthly_sold",
        "rating",
        "product_info",
        "product_detail_text",
        "product_description",
        "product_feature_bullets",
        "review_page_status",
        "variant_reviews",
        "reviews_text",
        "historical_uk_reviews",
        "parent_total_reviews",
        "estimated_variant_ratings",   # <-- added key
        "variant_mode",
        "total_reviews_before_filter",
        "variant_filter_reviews",
        "matching_variant_reviews",
        "global_ratings",
    ]
    return {k: data.get(k, "N/A") for k in required_keys}

def random_scroll(driver):
    """
    Performs random scrolling on the page to simulate user behavior.
    """
    scroll_height = driver.execute_script("return document.body.scrollHeight")
    for _ in range(random.randint(1, 3)):
        random_scroll_position = random.randint(100, scroll_height // 2)
        driver.execute_script(f"window.scrollTo(0, {random_scroll_position});")
        _human_pause(0.18, 0.55)

def find_dynamic_element(driver, locators, wait_time=10):
    """
    Attempts to find an element dynamically using multiple locator strategies.
    Returns the first WebElement found or None if no element is located.
    """
    from selenium.common.exceptions import TimeoutException
    if not locators:
        return None

    per_locator_wait = _locator_wait(wait_time, len(locators), floor=0.8, cap=2.4)
    for strategy, locator in locators:
        try:
            logger.info(f"Trying to locate element using {strategy}: {locator}")
            elem = WebDriverWait(driver, per_locator_wait).until(
                EC.presence_of_element_located((strategy, locator))
            )
            if elem.is_displayed():
                logger.info(f"Element located using {strategy}: {locator}")
                return elem
        except TimeoutException:
            logger.warning(f"Timeout while trying {strategy}: {locator}")
        except Exception as e:
            logger.warning(f"Exception while trying {strategy}: {locator} => {e}")
    logger.error("Failed to locate element with all provided locators.")
    return None

# We'll import test_variant_dropdown from 'dropdownSelector'
from dropdownSelector import test_variant_dropdown

def clean_number(text):
    """
    Extract digits from the provided text.
    If no digits are found, returns 'N/A' instead of '0'.
    """
    import re
    cleaned = re.sub(r"[^\d]", "", text)
    return cleaned if cleaned else "N/A"


def parse_int_or_none(value):
    """
    Parse integer-like values from string/number input.
    Returns None when the value is empty or non-numeric.
    """
    try:
        text = str(value).strip()
        if text == "" or text.upper() == "N/A":
            return None
        return int(text)
    except Exception:
        return None


def read_text_with_fallback(driver, locators, wait_seconds=10, attempts=3, visible=False):
    """
    Read text from a list of locator candidates with stale-element retries.
    Returns empty string on failure.
    """
    wait_condition = EC.visibility_of_element_located if visible else EC.presence_of_element_located
    for attempt in range(1, attempts + 1):
        for strategy, locator in locators:
            try:
                element = WebDriverWait(driver, wait_seconds).until(
                    wait_condition((strategy, locator))
                )
                text_candidates = []
                try:
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
                        element,
                    )
                except Exception:
                    pass

                for value in (
                    getattr(element, "text", ""),
                    element.get_attribute("innerText"),
                    element.get_attribute("textContent"),
                ):
                    value = (value or "").strip()
                    if value:
                        text_candidates.append(value)

                try:
                    js_text = driver.execute_script(
                        "return (arguments[0].innerText || arguments[0].textContent || '').trim();",
                        element,
                    )
                    js_text = (js_text or "").strip()
                    if js_text:
                        text_candidates.append(js_text)
                except Exception:
                    pass

                for text in text_candidates:
                    if text:
                        return text
            except (TimeoutException, StaleElementReferenceException):
                continue
            except Exception:
                continue
        if attempt < attempts:
            time.sleep(0.35)
    return ""


def compact_scrape_text(value, *, limit=2000):
    text = str(value or "").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    if not text or text.upper() == "N/A":
        return "N/A"
    if len(text) > limit:
        return text[: limit - 3].rstrip() + "..."
    return text


def read_product_page_text_evidence(driver, product_info_text):
    description = read_text_with_fallback(
        driver,
        [
            (By.XPATH, '//*[@id="productDescription"]/p[1]/span'),
            (By.CSS_SELECTOR, "#productDescription p span"),
            (By.CSS_SELECTOR, "#productDescription span"),
            (By.CSS_SELECTOR, "#productDescription"),
            (By.CSS_SELECTOR, "#productDescription_feature_div"),
            (By.CSS_SELECTOR, "#aplus"),
            (By.CSS_SELECTOR, "#aplus_feature_div"),
            (By.CSS_SELECTOR, "[data-feature-name='aplus']"),
        ],
        wait_seconds=_scaled_wait(6, floor=3, cap=8),
        attempts=2,
    )
    feature_bullets = read_text_with_fallback(
        driver,
        [
            (By.CSS_SELECTOR, "#feature-bullets"),
            (By.CSS_SELECTOR, "#feature-bullets ul"),
            (By.CSS_SELECTOR, "#featurebullets_feature_div"),
            (By.CSS_SELECTOR, "#feature-bullets .a-list-item"),
        ],
        wait_seconds=_scaled_wait(5, floor=3, cap=8),
        attempts=2,
    )
    return {
        "product_detail_text": compact_scrape_text(product_info_text),
        "product_description": compact_scrape_text(description),
        "product_feature_bullets": compact_scrape_text(feature_bullets),
    }


def extract_first_count(text):
    """
    Extract first integer-looking value from text. Returns "N/A" when missing.
    """
    if not text:
        return "N/A"
    match = re.search(r"(\d[\d,]*)", str(text))
    if not match:
        return "N/A"
    return match.group(1).replace(",", "")


def extract_review_count_from_filter_text(text):
    """
    Extract the meaningful review count from filter-info style text.
    Handles patterns like:
    - "1-16 of 341 reviews"
    - "13 matching customer reviews"
    - "341 customer reviews"
    """
    if not text:
        return "N/A"
    text_value = str(text)

    patterns = [
        r"\bof\s+(\d[\d,]*)\s+review(?:s)?\b",
        r"(\d[\d,]*)\s+matching customer review(?:s)?",
        r"(\d[\d,]*)\s+customer review(?:s)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text_value, re.IGNORECASE)
        if match:
            return match.group(1).replace(",", "")

    return extract_first_count(text_value)


# ---------------------------------------------------
# MAIN SCRAPE FUNCTION
# ---------------------------------------------------
def scrape_main_page(driver):
    logger.info("Starting main page scraping with existing driver session.")

    try:
        # 1) Valid driver check
        if not driver.service.is_connectable():
            logger.error("Driver session is invalid. No scraping done.")
            return validate_scraped_data({})

        # 2) Basic data
        scan_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"Scrape date: {scan_date}")

        # 3) Title
        try:
            title_el = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "productTitle"))
            )
            main_title = title_el.text.strip()
        except Exception as e:
            main_title = "N/A"
            logger.error(f"Error finding productTitle => {e}")

        # 4) Monthly sold
        try:
            sold_el = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="socialProofingAsinFaceout_feature_div"]'))
            )
            monthly_sold = sold_el.text.strip()
        except Exception as e:
            monthly_sold = "0"
            logger.error(f"Error scraping monthly_sold => {e}")

        # 5) Rating
        rating_txt = read_text_with_fallback(
            driver,
            [
                (By.XPATH, '//*[@id="acrPopover"]/span[1]/a/span'),
                (By.CSS_SELECTOR, "#acrPopover span.a-size-base"),
            ],
            wait_seconds=8,
            attempts=2,
        ) or "N/A"

        # 5.5) Parent-level total reviews
        parent_reviews_txt = read_text_with_fallback(
            driver,
            [
                (By.XPATH, '//*[@id="acrCustomerReviewText"]'),
                (By.CSS_SELECTOR, "#acrCustomerReviewText"),
            ],
            wait_seconds=8,
            attempts=2,
        )
        parent_total_reviews = extract_first_count(parent_reviews_txt)

        # 6) Product info containing date
        product_info_text = "N/A"
        try:
            details_el = WebDriverWait(driver, _scaled_wait(9, floor=4.5, cap=10.0)).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="productDetailsWithModules_feature_div"]'))
            )
            product_info_text = details_el.text.strip()
            logger.info("Found product details (modules).")
        except TimeoutException:
            logger.info("Primary product details block not found, trying fallback blocks.")
            fallback_blocks = [
                ("detail bullets", '//*[@id="detailBullets_feature_div"]', _scaled_wait(5, floor=2.5, cap=6.5)),
                ("legacy details", '//*[@id="productDetails_feature_div"]', _scaled_wait(8, floor=4.0, cap=9.0)),
            ]
            for block_name, block_xpath, wait_seconds in fallback_blocks:
                try:
                    details_el = WebDriverWait(driver, wait_seconds).until(
                        EC.presence_of_element_located((By.XPATH, block_xpath))
                    )
                    product_info_text = details_el.text.strip()
                    logger.info(f"Found product info ({block_name}).")
                    break
                except Exception:
                    continue
            if product_info_text == "N/A":
                logger.error("No product info found => all fallback blocks failed.")

        extracted_date = extract_date(product_info_text)
        if not extracted_date:
            extracted_date = "N/A"
            logger.info("No date found in product info.")
        product_page_evidence = read_product_page_text_evidence(driver, product_info_text)

        # 7) Random scroll
        random_scroll(driver)

        # 8) Find reviews link
        reviews_link = find_dynamic_element(
            driver,
            [
                (By.CSS_SELECTOR, '#acrCustomerReviewLink'),
                (By.CSS_SELECTOR, "#reviews-medley-footer a[data-hook='see-all-reviews-link-foot']"),
                (By.XPATH, '//*[@id="reviews-medley-footer"]/div[2]/a'),
                (By.XPATH, '//*[@id="reviews-medley-footer"]/div/a'),
                (By.CSS_SELECTOR, '#reviews-medley-footer a'),
            ],
            wait_time=5
        )
        if not reviews_link:
            logger.error("No reviews link found. Skipping reviews part.")
            partial = {
                "scan_date": scan_date,
                "main_title": main_title,
                "monthly_sold": monthly_sold,
                "rating": rating_txt,
                "product_info": extracted_date,
                **product_page_evidence,
                "review_page_status": "link_missing",
                "variant_reviews": "N/A",
                "reviews_text": "N/A",
                "historical_uk_reviews": "N/A",
                "parent_total_reviews": parent_total_reviews,
                "total_reviews": "N/A"
            }
            return validate_scraped_data(partial)

        rev_url = reviews_link.get_attribute("href")
        if not rev_url:
            logger.error("Review link has no href. Skipping reviews.")
            partial2 = {
                "scan_date": scan_date,
                "main_title": main_title,
                "monthly_sold": monthly_sold,
                "rating": rating_txt,
                "product_info": extracted_date,
                **product_page_evidence,
                "review_page_status": "href_missing",
                "variant_reviews": "N/A",
                "reviews_text": "N/A",
                "historical_uk_reviews": "N/A",
                "parent_total_reviews": parent_total_reviews,
                "total_reviews": "N/A"
            }
            return validate_scraped_data(partial2)

        canonical_rev_url = _canonical_reviews_url(rev_url, driver.current_url)
        if canonical_rev_url and canonical_rev_url != rev_url:
            logger.info(f"Normalized review URL => {canonical_rev_url}")
            rev_url = canonical_rev_url

        # Navigate to reviews page with one controlled retry if load fails.
        review_wait_seconds = _scaled_wait(9, floor=5.5, cap=11.5)
        reviews_ready = False
        last_reviews_error = None
        blocked_page_detected = False

        for attempt in range(1, 3):
            try:
                if attempt == 1:
                    driver.get(rev_url)
                    logger.info("Navigated to reviews page.")
                else:
                    logger.warning("Reviews page load timeout - retrying once with page reset.")
                    try:
                        driver.execute_script("window.stop();")
                    except Exception:
                        pass
                    _human_pause(0.45, 1.05)
                    driver.get("about:blank")
                    _human_pause(0.20, 0.50)
                    driver.get(rev_url)
                    logger.info("Navigated to reviews page (retry).")

                ready, marker = _wait_for_reviews_ready(driver, review_wait_seconds)
                if ready:
                    logger.info(f"Reviews page loaded fully (attempt {attempt}/2, marker={marker}).")
                    reviews_ready = True
                    break

                if marker == "blocked":
                    blocked_page_detected = True
                    last_reviews_error = "blocked_or_signin_page"
                    logger.warning("Reviews page appears blocked/sign-in/captcha; skipping further retries.")
                    break

                last_reviews_error = marker
            except Exception as e:
                last_reviews_error = e

        if not reviews_ready:
            if blocked_page_detected:
                logger.warning("Reviews page blocked by anti-bot checks, returning partial scrape.")
            logger.warning(f"Reviews page did not load after retry, returning partial scrape => {last_reviews_error}")
            partial_reviews = {
                "scan_date": scan_date,
                "main_title": main_title,
                "monthly_sold": monthly_sold,
                "rating": rating_txt,
                "product_info": extracted_date,
                **product_page_evidence,
                "review_page_status": "blocked" if blocked_page_detected else "timeout",
                "variant_reviews": "N/A",
                "reviews_text": "N/A",
                "historical_uk_reviews": "N/A",
                "parent_total_reviews": parent_total_reviews,
                "estimated_variant_ratings": "0",
                "variant_mode": "failed",
                "total_reviews_before_filter": "N/A",
                "variant_filter_reviews": "N/A",
                "matching_variant_reviews": "N/A",
                "global_ratings": parent_total_reviews,
            }
            return validate_scraped_data(partial_reviews)
        
        # Extract Total Reviews (unfiltered, before dropdown)
        total_reviews_txt = read_text_with_fallback(
            driver,
            [
                (By.XPATH, "//*[@id='filter-info-section']/div"),
                (By.CSS_SELECTOR, "#filter-info-section > div"),
            ],
            wait_seconds=8,
            attempts=2,
            visible=True,
        )
        total_reviews = extract_review_count_from_filter_text(total_reviews_txt)
        logger.info(f"Extracted Total Reviews (before filter): {total_reviews}")


        # Proceed with variant dropdown operation to sort by most recent reviews
        dropdown_status = test_variant_dropdown(driver, rev_url) or {}
        variant_mode = str(dropdown_status.get("variant_mode", "unknown")).strip().lower()
        logger.info(f"test_variant_dropdown done (variant_mode={variant_mode})")
        
        # NEW: Extract Historical UK Reviews from full review text
        historical_uk_reviews = "N/A"
        full_reviews_text = read_text_with_fallback(
            driver,
            [
                (By.ID, "cm_cr-review_list"),
                (By.ID, "cm-cr-dp-review-list"),
                (By.XPATH, "//*[@id='cm_cr-review_list']"),
                (By.XPATH, "//*[@id='cm-cr-dp-review-list']"),
                (By.CSS_SELECTOR, "[data-hook='review']"),
            ],
            wait_seconds=8,
            attempts=3,
            visible=True,
        )
        if full_reviews_text:
            hist_count = extract_historical_uk_reviews(full_reviews_text)
            historical_uk_reviews = str(hist_count)
            logger.info(f"Extracted historical UK reviews count: {historical_uk_reviews}")
        else:
            logger.error("Error extracting historical UK reviews: review list text missing.")

        # NEW: Now extract 3-month UK reviews after sorting by most recent
        three_month_reviews = "N/A"
        review_list_text = read_text_with_fallback(
            driver,
            [
                (By.XPATH, "//*[@id='cm_cr-review_list']/ul[1]"),
                (By.XPATH, "//*[@id='cm-cr-dp-review-list']/ul[1]"),
                (By.ID, "cm_cr-review_list"),
                (By.ID, "cm-cr-dp-review-list"),
            ],
            wait_seconds=8,
            attempts=3,
            visible=True,
        )
        if review_list_text:
            three_month_count = extract_3_month_uk_reviews(review_list_text)
            three_month_reviews = str(three_month_count)
            logger.info(f"Extracted 3-month UK review count: {three_month_reviews}")
        else:
            logger.error("Error extracting 3-month UK reviews: reviews text missing.")

        # Extract Variant Filter information (after dropdown)
        filter_info_text = read_text_with_fallback(
            driver,
            [
                (By.XPATH, "//*[@id='filter-info-section']/div"),
                (By.XPATH, "//*[@id='filter-info-section']"),
                (By.CSS_SELECTOR, "#filter-info-section"),
                (By.CSS_SELECTOR, "[data-hook='cr-filter-info-review-rating-count']"),
            ],
            wait_seconds=8,
            attempts=3,
            visible=True,
        )

        variant_filter = extract_review_count_from_filter_text(filter_info_text)
        logger.info(f"Extracted Variant Filter: {variant_filter}")

        # Extract variant reviews (if present)
        variant_reviews = "N/A"
        if filter_info_text:
            logger.info(f"raw variant => {filter_info_text}")
            match = re.search(r'(\d[\d,]*)\s+matching customer review(?:s)?', filter_info_text, re.IGNORECASE)
            if not match:
                match = re.search(r'(\d[\d,]*)\s+customer review(?:s)?', filter_info_text, re.IGNORECASE)
            if match:
                variant_reviews = match.group(1).replace(',', '')
        else:
            logger.error("Variant reviews extraction => filter info missing")

        # Extract Global Ratings
        global_rating = read_text_with_fallback(
            driver,
            [
                (By.XPATH, "//*[@id='cm_cr-product_info']/div/div[1]/div[3]/span"),
                (By.CSS_SELECTOR, "#cm_cr-product_info span[data-hook='cr-filter-info-review-rating-count']"),
                (By.CSS_SELECTOR, "#cm_cr-product_info .a-size-base"),
            ],
            wait_seconds=8,
            attempts=2,
            visible=True,
        )
        if global_rating:
            logger.info(f"Extracted Global Ratings: {global_rating}")
        else:
            logger.error("Global Ratings element not found; falling back to parent total reviews.")
            global_rating = parent_total_reviews

        # Estimate variant rating count
        try:
            global_rating_count = parse_int_or_none(clean_number(global_rating)) or 0
            total_reviews_count = parse_int_or_none(total_reviews)
            variant_reviews_count = parse_int_or_none(variant_reviews)
            variant_filter_count = parse_int_or_none(variant_filter)

            if variant_reviews_count is None and variant_filter_count is not None:
                variant_reviews_count = variant_filter_count
                logger.info(
                    f"Using variant filter count as review count fallback: {variant_reviews_count}"
                )

            if variant_mode == "single":
                # Single-ASIN product: use product-level global ratings directly.
                variant_estimate = global_rating_count
                logger.info(
                    f"Single-variant product detected. Using global ratings as variant ratings: {variant_estimate}"
                )
            elif variant_mode in ("failed", "unknown"):
                # Do not trust parent-level fallback when variant selection is uncertain.
                variant_estimate = 0
                logger.warning(
                    "Variant selection state is uncertain; setting estimated variant ratings to 0."
                )
            elif variant_reviews_count is not None and total_reviews_count and total_reviews_count > 0:
                # Keep full precision here. Early rounding inflated low-share variants.
                proportion = variant_reviews_count / total_reviews_count
                variant_estimate = int(round(proportion * global_rating_count))
                logger.info(
                    f"Estimation inputs - Total Reviews: {total_reviews_count}, Variant Reviews: {variant_reviews_count}, Global Ratings: {global_rating_count}"
                )
                logger.info(f"Calculated proportion: {proportion}")
                logger.info(f"Resulting estimated variant ratings: {variant_estimate}")
            else:
                # Last-resort fallback when we still cannot parse variant counts in a non-failed state.
                variant_estimate = global_rating_count
                logger.info(
                    "Variant reviews unavailable in a non-failed state; using global ratings fallback."
                )
        except Exception as e:
            logger.error(f"Error during variant ratings estimation: {e}")
            variant_estimate = 0



        # Build scraped_data and use reviews_text to carry the estimated variant ratings.
        # NOTE: Changed "variant_reviews" key to use the extracted variant_reviews value (from 'matching customer review(s)')
        scraped_data = {
            "scan_date": scan_date,
            "main_title": main_title,
            "monthly_sold": monthly_sold,
            "rating": rating_txt,
            "product_info": extracted_date,
            **product_page_evidence,
            "review_page_status": "ok",
            "variant_reviews": str(variant_estimate),
            "reviews_text": three_month_reviews,
            "historical_uk_reviews": historical_uk_reviews,
            "parent_total_reviews": clean_number(parent_total_reviews),
            "estimated_variant_ratings": str(variant_estimate),
            "variant_mode": variant_mode,
            "total_reviews_before_filter": str(total_reviews),
            "variant_filter_reviews": str(variant_filter),
            "matching_variant_reviews": str(variant_reviews),
            "global_ratings": clean_number(global_rating),
        }


        return validate_scraped_data(scraped_data)

    except Exception as e:
        logger.error(f"Fatal error => {e}")
        return validate_scraped_data({})
    finally:
        logger.info("WebscraperS2 => scrape_main_page done.")

