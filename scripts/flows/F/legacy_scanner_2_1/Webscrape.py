# Webscrape.py

# ---------------------------------------------------
# 1. IMPORTS
# ---------------------------------------------------
# Standard libraries
import time
import random
import logging
import os
import json
import subprocess
from datetime import datetime, timedelta
from difflib import SequenceMatcher
import re
from pathlib import Path
import sys
import urllib.request

# Third-party libraries
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup

# Local modules
from WebscraperS2 import scrape_main_page, extract_date
from turnover_gate import build_turnover_profit_history, evaluate_turnover_gate

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scripts.flows.F._profit_model import calculate_fee_based_profit_per_unit
from scripts.flows.F._scanner_state import (
    dashboard_delivery_classification,
    dashboard_separate_delivery_required,
    has_required_dashboard_signal,
)

# ---------------------------------------------------
# 2. LOGGER SETUP
# ---------------------------------------------------
logger = logging.getLogger("Webscrape Bybot")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

PRE_REVIEW_LOW_SALES_MAX_UNITS = 2
F061_MANUAL_BBP_LOGIN_WAIT_SECONDS_ENV = "F061_MANUAL_BBP_LOGIN_WAIT_SECONDS"


def _apply_dashboard_delivery_fields(data, dashboard_value):
    data["bbp_dashboard_delivery_classification"] = dashboard_delivery_classification(dashboard_value)
    data["bbp_dashboard_separate_delivery_required"] = (
        "1" if dashboard_separate_delivery_required(dashboard_value) else "0"
    )
    return data


def _env_flag_enabled(name):
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _resolve_file_log_path(*, default_prefix: str) -> str:
    explicit_path = os.getenv("BBP_FILE_LOG_PATH") or os.getenv("F061_LOG_PATH") or ""
    explicit_path = explicit_path.strip()
    if explicit_path:
        os.makedirs(os.path.dirname(explicit_path), exist_ok=True)
        return explicit_path

    explicit_dir = os.getenv("BBP_FILE_LOG_DIR") or os.getenv("F061_LOG_DIR") or ""
    explicit_dir = explicit_dir.strip()
    log_dir = explicit_dir or os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(log_dir, f"{default_prefix}_{ts}.log")

def _setup_file_logging():
    """
    Adds a timestamped file log per run when enabled.
    Toggle with env var BBP_FILE_LOG=0/false/no to disable.
    """
    raw = os.getenv("BBP_FILE_LOG", "1").strip().lower()
    if raw in ("0", "false", "no"):
        logger.info("File logging disabled via BBP_FILE_LOG.")
        return

    root_logger = logging.getLogger()
    if any(isinstance(h, logging.FileHandler) for h in root_logger.handlers):
        return

    log_path = _resolve_file_log_path(default_prefix="webscrape")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    root_logger.addHandler(file_handler)
    logger.info(f"File logging enabled => {log_path}")


def _format_bbp_money(value) -> str:
    try:
        amount = float(value)
    except Exception:
        amount = 0.0
    return f"{amount:.2f}"


def _set_bbp_money_input(driver, element, value, *, field_name: str) -> str:
    formatted = _format_bbp_money(value)
    try:
        element.click()
    except Exception:
        pass
    try:
        element.send_keys(Keys.CONTROL, "a")
        element.send_keys(Keys.BACKSPACE)
    except Exception:
        try:
            element.clear()
        except Exception:
            pass
    try:
        driver.execute_script(
            """
            const el = arguments[0];
            el.value = '';
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            """,
            element,
        )
    except Exception:
        pass
    element.send_keys(formatted)
    try:
        observed = str(element.get_attribute("value") or "").strip()
    except Exception:
        observed = ""
    if observed and observed != formatted:
        logger.warning(f"[Profile5] {field_name} input mismatch after typing => expected={formatted}, observed={observed}")
    try:
        driver.execute_script(
            """
            const el = arguments[0];
            const value = arguments[1];
            el.value = value;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            el.dispatchEvent(new Event('blur', { bubbles: true }));
            """,
            element,
            formatted,
        )
    except Exception:
        pass
    return formatted

_setup_file_logging()

def _load_local_env_defaults():
    """
    Best-effort load of secrets/.env for legacy standalone runs.
    Existing environment variables are preserved.
    """
    try:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
        env_path = os.path.join(repo_root, "secrets", ".env")
        if not os.path.exists(env_path):
            return
        with open(env_path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                if not key or key in os.environ:
                    continue
                os.environ[key] = val.strip()
    except Exception:
        pass

_load_local_env_defaults()

# ---------------------------------------------------
# 3. HELPER FUNCTIONS
# ---------------------------------------------------
def handle_overlays(driver):
    """
    Attempts to close/hide any pop-up overlays on the page.
    """
    try:
        overlay = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "newUserDiv"))
        )
        driver.execute_script("arguments[0].style.display = 'none';", overlay)
        logger.info("Overlay hidden.")
    except:
        logger.info("No overlay or ignoring.")


def clean_seller_name(raw_name):
    """
    Strips HTML tags, removes prefixes like 'FBA Prime', 'MF Prime', etc.
    and returns a clean seller name.
    """
    try:
        soup = BeautifulSoup(raw_name, "html.parser")
        text = soup.get_text(strip=True)
        for prefix in ["FBA Prime", "MF Prime", "FBA ", "FBM ", "MF "]:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        return text
    except:
        return raw_name


def is_similar(brand_name, seller_name, threshold=0.8):
    """
    Returns True if brand_name and seller_name are at least 'threshold' similar.
    """
    ratio = SequenceMatcher(None, brand_name.lower(), clean_seller_name(seller_name).lower()).ratio()
    logger.info(f"similar => {brand_name} vs {seller_name}, ratio => {ratio:.2f}")
    return ratio >= threshold


def _seller_similarity_score(brand_name, seller_name):
    brand = str(brand_name or "").strip().lower()
    seller = clean_seller_name(seller_name or "").strip().lower()
    if not brand or not seller:
        return 0.0
    return SequenceMatcher(None, brand, seller).ratio()


BBP_COMPETITION_SELLER_RANKS = (1, 2, 3)


def _empty_bbp_competition_rank_fields():
    fields = {}
    for rank in BBP_COMPETITION_SELLER_RANKS:
        prefix = f"bbp_seller_rank_{rank}"
        fields.update(
            {
                f"{prefix}_name": "",
                f"{prefix}_price": "",
                f"{prefix}_fulfilment": "",
                f"{prefix}_delivery": "",
                f"{prefix}_reviews": "",
                f"{prefix}_feedback_pct": "",
                f"{prefix}_brand_match_flag": "False",
                f"{prefix}_row_text": "",
                f"{prefix}_row_html": "",
            }
        )
    return fields


def _seller_evidence_fields(brand_name, sellers, threshold=0.8, competition_rows=None):
    clean_names = []
    seen = set()
    for raw in sellers or []:
        name = clean_seller_name(raw or "").strip()
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        clean_names.append(name)

    best_name = ""
    best_score = 0.0
    for name in clean_names:
        score = _seller_similarity_score(brand_name, name)
        if score > best_score:
            best_name = name
            best_score = score

    fields = {
        "bbp_top_seller_names": "|".join(clean_names),
        "bbp_top_seller_count": str(len(clean_names)),
        "bbp_brand_match_seller": best_name if best_score >= threshold else "",
        "bbp_brand_match_score": f"{best_score:.4f}" if best_score > 0 else "0",
        "bbp_brand_match_flag": "True" if best_score >= threshold else "False",
    }
    fields.update(_empty_bbp_competition_rank_fields())
    for idx, row in enumerate(competition_rows or [], start=1):
        if idx not in BBP_COMPETITION_SELLER_RANKS:
            continue
        prefix = f"bbp_seller_rank_{idx}"
        seller_name = clean_seller_name(row.get("name", "")).strip()
        row_score = _seller_similarity_score(brand_name, seller_name)
        fields.update(
            {
                f"{prefix}_name": seller_name,
                f"{prefix}_price": str(row.get("price", "") or ""),
                f"{prefix}_fulfilment": str(row.get("fulfilment", "") or ""),
                f"{prefix}_delivery": str(row.get("delivery", "") or ""),
                f"{prefix}_reviews": str(row.get("reviews", "") or ""),
                f"{prefix}_feedback_pct": str(row.get("feedback_pct", "") or ""),
                f"{prefix}_brand_match_flag": "True" if seller_name and row_score >= threshold else "False",
                f"{prefix}_row_text": str(row.get("row_text", "") or "")[:1000],
                f"{prefix}_row_html": str(row.get("row_html", "") or "")[:1000],
            }
        )
    return fields


def _is_bbp_seller_noise(raw):
    name = clean_seller_name(raw or "").strip()
    low = name.lower()
    return (
        not name
        or low in {"-", "n/a", "na"}
        or re.fullmatch(r"\d+", low)
        or re.fullmatch(r"[£Ł]?\s*\d+(?:\.\d{1,2})?", name)
        or re.fullmatch(r"\d{1,2}\s*-\s*\d{1,2}(?:\s+[a-z]{3,9})?(?:\.{1,3})?", low)
        or low.startswith("reviews:")
        or "positive feedback" in low
        or "learn more about the seller" in low
        or low in {"stock", "price", "profit", "roi", "deliv", "rvw"}
        or "no data available" in low
        or low.startswith("# stock")
        or low.startswith("seller stock")
        or low.startswith("top 10 prime sellers")
    )


def _parse_bbp_competition_row_text(raw_text):
    text = re.sub(r"\s+", " ", str(raw_text or "")).strip()
    if not text:
        return {}

    parts = [part.strip() for part in re.split(r"[\n\r\t|]+", str(raw_text or "")) if part.strip()]
    if len(parts) <= 1:
        parts = [part.strip() for part in re.split(r"\s{2,}", str(raw_text or "")) if part.strip()]
    compact_parts = parts or [text]

    price = ""
    delivery = ""
    reviews = ""
    feedback_pct = ""
    fulfilment_tokens = []
    seller_candidates = []

    price_pattern = re.compile(r"[£Ł]\s*\d+(?:\.\d{1,2})?")
    delivery_pattern = re.compile(r"\b\d{1,2}\s*-\s*\d{1,2}(?:\s+[A-Za-z]{3,9})?\b")
    reviews_pattern = re.compile(r"Reviews:\s*([0-9,]+)", re.I)
    feedback_pattern = re.compile(r"Positive Feedback:\s*([0-9]+%)", re.I)

    for part in compact_parts:
        clean = re.sub(r"\s+", " ", part).strip()
        low = clean.lower()
        if price == "":
            match = price_pattern.search(clean)
            if match:
                price = match.group(0).replace("Ł", "£")
        if delivery == "":
            match = delivery_pattern.search(clean)
            if match:
                delivery = match.group(0)
        if reviews == "":
            match = reviews_pattern.search(clean)
            if match:
                reviews = match.group(1).replace(",", "")
        if feedback_pct == "":
            match = feedback_pattern.search(clean)
            if match:
                feedback_pct = match.group(1)
        for token in ("FBA", "FBM", "MF", "Prime"):
            if re.search(rf"\b{token}\b", clean, flags=re.I) and token not in fulfilment_tokens:
                fulfilment_tokens.append(token)
        if _is_bbp_seller_noise(clean):
            continue
        # Seller text often carries fulfilment prefixes; clean_seller_name removes the common ones.
        if price_pattern.search(clean) or delivery_pattern.search(clean) or "positive feedback" in low:
            continue
        seller_candidates.append(clean_seller_name(clean))

    seller_name = ""
    for candidate in seller_candidates:
        candidate = candidate.strip()
        if candidate and not _is_bbp_seller_noise(candidate):
            seller_name = candidate
            break

    if seller_name == "":
        return {}

    return {
        "name": seller_name,
        "price": price,
        "fulfilment": "|".join(fulfilment_tokens),
        "delivery": delivery,
        "reviews": reviews,
        "feedback_pct": feedback_pct,
        "row_text": text[:1000],
    }


def _extract_bbp_competition_seller_rows(driver, max_rows=3):
    rows = []
    seen = set()
    selectors = [
        "#competitionAnalysisDataTable > tbody > tr",
        "#competitionAnalysisDataTable tbody tr",
    ]
    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            elements = []
        for element in elements:
            try:
                row_text = element.text or element.get_attribute("textContent") or ""
            except Exception:
                row_text = ""
            parsed = _parse_bbp_competition_row_text(row_text)
            if not parsed:
                continue
            try:
                parsed["row_html"] = str(element.get_attribute("outerHTML") or "")[:1000]
            except Exception:
                parsed["row_html"] = ""
            key = parsed.get("name", "").lower()
            if not key or key in seen:
                continue
            seen.add(key)
            rows.append(parsed)
            if len(rows) >= max_rows:
                return rows[:max_rows]
        if rows:
            return rows[:max_rows]
    return rows[:max_rows]


def _extract_bbp_top_seller_names(driver, max_sellers=3):
    structured_rows = _extract_bbp_competition_seller_rows(driver, max_rows=max_sellers)
    if structured_rows:
        return [row.get("name", "") for row in structured_rows if row.get("name", "")][:max_sellers]

    names = []

    def _add(raw):
        name = clean_seller_name(raw or "").strip()
        if _is_bbp_seller_noise(name):
            return
        if name.lower() not in {existing.lower() for existing in names}:
            names.append(name)

    selectors = [
        "#competitionAnalysisDataTable > tbody > tr td:nth-child(1) > a",
        "#competitionAnalysisDataTable > tbody > tr td:nth-child(1)",
        "#competitionAnalysisDataTable tbody tr [data-original-title]",
        "#competitionAnalysisDataTable tbody tr a",
    ]
    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            elements = []
        for element in elements:
            for attr in ("data-original-title", "title", "aria-label", "textContent", "innerText"):
                try:
                    value = element.text if attr == "textContent" else element.get_attribute(attr)
                except Exception:
                    value = ""
                _add(value)
                if len(names) >= max_sellers:
                    return names[:max_sellers]
        if names:
            return names[:max_sellers]
    return names[:max_sellers]


def _extract_amazon_buybox_seller_name(driver):
    selectors = [
        "#sellerProfileTriggerId",
        "#merchant-info a",
        "#merchant-info",
        "#tabular-buybox .tabular-buybox-text",
        "#tabular-buybox",
    ]
    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            elements = []
        for element in elements:
            try:
                text = _normalize_text(element.text or element.get_attribute("textContent") or "")
            except Exception:
                text = ""
            text = re.sub(r"\s+", " ", text).strip()
            if not text:
                continue
            if selector in {"#merchant-info", "#tabular-buybox", "#tabular-buybox .tabular-buybox-text"}:
                match = re.search(r"(?:sold by|dispatches from and sold by)\s+([^.\n]+)", text, flags=re.I)
                if match:
                    text = match.group(1).strip()
            text = clean_seller_name(text)
            low = text.lower()
            if "learn more about the seller" in low or low == "seller profile":
                continue
            if text and "amazon" not in low and "secure transaction" not in low:
                return text
            if text and "amazon" in low:
                return text
    return ""


def _amazon_buybox_seller_evidence_fields(brand_name, seller_name, threshold=0.8):
    seller = clean_seller_name(seller_name or "").strip()
    score = _seller_similarity_score(brand_name, seller)
    return {
        "amazon_buybox_seller_name": seller,
        "amazon_buybox_brand_match_score": f"{score:.4f}" if score > 0 else "0",
        "amazon_buybox_brand_match_flag": "True" if seller and score >= threshold else "False",
    }


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        cleaned = str(value).replace(",", "").replace("Â£", "").replace("Ã‚Â£", "").strip()
        if not cleaned:
            return default
        return float(cleaned)
    except Exception:
        return default


def _safe_int(value, default=0):
    try:
        if value is None:
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(round(value))
        cleaned = re.sub(r"[^\d]", "", str(value))
        if not cleaned:
            return default
        return int(cleaned)
    except Exception:
        return default


def _normalize_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _normalize_lower(value):
    return _normalize_text(value).lower()


def _mean(values):
    vals = [float(v) for v in values if _safe_float(v, 0.0) > 0]
    if not vals:
        return 0.0
    return sum(vals) / len(vals)


def parse_amazon_monthly_bought_floor(text):
    """
    Parse lower bound from Amazon text like "50+ bought in past month".
    Returns None when no useful floor can be extracted.
    """
    raw = (text or "").strip()
    if not raw:
        return None

    # Most common pattern: "50+ bought in past month"
    plus_match = re.search(r"(\d[\d,]*)\s*\+", raw)
    if plus_match:
        return _safe_int(plus_match.group(1), None)

    # Fallback pattern with explicit "bought"
    bought_match = re.search(r"(\d[\d,]*)\s+bought", raw, re.IGNORECASE)
    if bought_match:
        return _safe_int(bought_match.group(1), None)

    return None


def _env_flag_enabled(name, default=False):
    raw = os.getenv(name, "1" if default else "0").strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


def _safe_filename_piece(value, fallback="na"):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    cleaned = cleaned.strip("._")
    if cleaned == "":
        return fallback
    return cleaned[:80]


def capture_bbp_section_snapshot(driver, *, asin="", row_index=0, context=None):
    """
    Optional debug capture of the BBP section structure.
    Enabled only when BBP_SECTION_SNAPSHOT_ENABLED=1.

    Writes one JSON file per captured page and returns a small summary dict.
    """
    if not _env_flag_enabled("BBP_SECTION_SNAPSHOT_ENABLED", False):
        return {}

    max_depth = int(_clamp(_safe_int(os.getenv("BBP_SECTION_SNAPSHOT_MAX_DEPTH", "6"), 6), 1, 12))
    max_nodes = int(_clamp(_safe_int(os.getenv("BBP_SECTION_SNAPSHOT_MAX_NODES", "500"), 500), 50, 2000))
    max_text = int(_clamp(_safe_int(os.getenv("BBP_SECTION_SNAPSHOT_MAX_TEXT", "180"), 180), 40, 800))
    include_outer_html = _env_flag_enabled("BBP_SECTION_SNAPSHOT_INCLUDE_OUTER_HTML", False)

    anchors_raw = os.getenv(
        "BBP_SECTION_SNAPSHOT_ANCHORS",
        "#quickInfoEstSales|#quickInfoRoi|#quickInfoBsr|#estSalesMonthlyChart|#asinAverageStatisticsDataTable|#calculatorSellPrice",
    )
    anchor_selectors = [part.strip() for part in anchors_raw.split("|") if part.strip()]
    if not anchor_selectors:
        anchor_selectors = ["#estSalesMonthlyChart"]

    try:
        payload = driver.execute_script(
            """
            const selectors = Array.isArray(arguments[0]) ? arguments[0] : [];
            const maxDepth = Number(arguments[1] || 6);
            const maxNodes = Number(arguments[2] || 500);
            const maxText = Number(arguments[3] || 180);
            const includeOuterHtml = !!arguments[4];

            const normalizeText = (value) => String(value || "").replace(/\\s+/g, " ").trim();
            const shortText = (value) => {
              const txt = normalizeText(value);
              if (txt.length <= maxText) return txt;
              return txt.slice(0, maxText - 3) + "...";
            };

            const cssPath = (node) => {
              const parts = [];
              let cur = node;
              while (cur && cur.nodeType === 1 && parts.length < 20) {
                const tag = (cur.tagName || "").toLowerCase();
                if (!tag) break;
                if (cur.id) {
                  parts.unshift(tag + "#" + cur.id);
                  break;
                }
                let idx = 1;
                let sib = cur;
                while ((sib = sib.previousElementSibling)) {
                  if ((sib.tagName || "").toLowerCase() === tag) idx += 1;
                }
                parts.unshift(tag + ":nth-of-type(" + idx + ")");
                cur = cur.parentElement;
              }
              return parts.join(" > ");
            };

            const ancestors = (node) => {
              const out = [];
              let cur = node;
              while (cur && cur.nodeType === 1) {
                out.push(cur);
                cur = cur.parentElement;
              }
              return out;
            };

            const commonAncestor = (nodes) => {
              if (!nodes.length) return null;
              let shared = ancestors(nodes[0]);
              for (let i = 1; i < nodes.length; i += 1) {
                const candidate = new Set(ancestors(nodes[i]));
                shared = shared.filter((node) => candidate.has(node));
                if (!shared.length) return null;
              }
              return shared[0] || null;
            };

            const anchorResults = selectors.map((selector) => {
              let node = null;
              try { node = document.querySelector(selector); } catch (e) { node = null; }
              return {
                selector,
                found: !!node,
                tag: node ? (node.tagName || "").toLowerCase() : "",
                id: node ? (node.id || "") : "",
                classes: node ? ((node.className || "").toString().trim()) : "",
                path: node ? cssPath(node) : "",
                text: node ? shortText(node.innerText || node.textContent || "") : "",
              };
            });

            const foundNodes = [];
            for (const hit of anchorResults) {
              if (!hit.found) continue;
              try {
                const node = document.querySelector(hit.selector);
                if (node) foundNodes.push(node);
              } catch (e) {}
            }

            let root = commonAncestor(foundNodes);
            if (!root && foundNodes.length) {
              root = foundNodes[0].closest("section,article,div") || foundNodes[0];
            }
            if (!root) root = document.body || document.documentElement;

            const nodes = [];
            const queue = [{ node: root, depth: 0 }];
            while (queue.length && nodes.length < maxNodes) {
              const item = queue.shift();
              const node = item.node;
              if (!node || node.nodeType !== 1) continue;
              const tag = (node.tagName || "").toLowerCase();
              const record = {
                depth: item.depth,
                tag,
                id: node.id || "",
                classes: ((node.className || "").toString().trim()),
                name: node.getAttribute("name") || "",
                path: cssPath(node),
                child_count: node.children ? node.children.length : 0,
                text: shortText(node.innerText || node.textContent || ""),
              };
              if (includeOuterHtml) {
                record.outer_html = shortText(node.outerHTML || "");
              }
              nodes.push(record);
              if (item.depth >= maxDepth) continue;
              const children = Array.from(node.children || []);
              for (const child of children) {
                if (nodes.length + queue.length >= maxNodes) break;
                queue.push({ node: child, depth: item.depth + 1 });
              }
            }

            const fieldCandidates = Array.from(root.querySelectorAll("[id], [name], [data-original-title], [aria-label]"))
              .slice(0, 250)
              .map((node) => ({
                tag: (node.tagName || "").toLowerCase(),
                id: node.id || "",
                name: node.getAttribute("name") || "",
                aria_label: node.getAttribute("aria-label") || "",
                data_original_title: node.getAttribute("data-original-title") || "",
                classes: ((node.className || "").toString().trim()),
                path: cssPath(node),
                text: shortText(node.innerText || node.textContent || ""),
              }));

            return {
              page_url: window.location.href || "",
              anchors: anchorResults,
              root_path: cssPath(root),
              root_tag: root && root.tagName ? root.tagName.toLowerCase() : "",
              root_id: root && root.id ? root.id : "",
              nodes,
              node_count: nodes.length,
              field_candidates: fieldCandidates,
              chart_ids_found: ["estSalesMonthlyChart", "buyBotProSalesChart"]
                .filter((id) => !!document.getElementById(id)),
            };
            """,
            anchor_selectors,
            max_depth,
            max_nodes,
            max_text,
            include_outer_html,
        )
    except Exception as exc:
        logger.warning(f"BBP section snapshot capture failed in-browser => {exc}")
        return {"error": f"browser_capture_failed:{type(exc).__name__}"}

    if not isinstance(payload, dict):
        payload = {"error": "invalid_snapshot_payload"}

    observed_utc = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    ts_slug = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    asin_slug = _safe_filename_piece(asin, fallback="unknown_asin")
    row_slug = _safe_filename_piece(str(row_index), fallback="row")

    snapshot_dir_raw = os.getenv("BBP_SECTION_SNAPSHOT_DIR", "").strip()
    if snapshot_dir_raw:
        snapshot_dir = snapshot_dir_raw
    else:
        snapshot_dir = os.path.join(os.path.dirname(__file__), "logs", "bbp_section_snapshots")
    os.makedirs(snapshot_dir, exist_ok=True)

    file_path = os.path.join(snapshot_dir, f"bbp_section_{ts_slug}_{asin_slug}_{row_slug}.json")
    payload["observed_utc"] = observed_utc
    payload["asin"] = str(asin or "")
    payload["row_index"] = str(row_index)
    if isinstance(context, dict):
        safe_context = {}
        for key, value in context.items():
            safe_context[str(key)] = str(value)[:500]
        payload["context"] = safe_context

    try:
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2)
        logger.info(f"BBP section snapshot written => {file_path}")
    except Exception as exc:
        logger.warning(f"BBP section snapshot write failed => {exc}")
        return {"error": f"snapshot_write_failed:{type(exc).__name__}"}

    return {
        "file_path": file_path,
        "node_count": _safe_int(payload.get("node_count", 0), 0),
        "root_path": str(payload.get("root_path", "") or ""),
        "root_tag": str(payload.get("root_tag", "") or ""),
    }


def extract_bbp_monthly_sales_snapshot(driver):
    """
    Read BBP monthly sales quick info and attempt to parse popup history values.
    Returns:
      {
        "current_units": int,
        "history_values": [int, ...],  # newest-first best effort
        "history_text": str,
        "chart_source": str,
        "chart_month_labels": [str, ...],
        "chart_month_units": [int, ...],
        "chart_series": str,
        "last_completed_month_label": str,
        "last_completed_month_units": int,
        "current_month_label": str,
        "current_month_units": int,
        "future_month_count_ignored": int,
        "replay_demand_basis_source": str,
        "replay_demand_basis_label": str,
        "replay_demand_basis_units": int,
      }
    """
    current_units = 0
    history_values = []
    history_text = ""
    chart_source = ""
    chart_month_labels = []
    chart_month_units = []
    chart_series = ""
    last_completed_month_label = ""
    last_completed_month_units = 0
    current_month_label = ""
    current_month_units = 0
    future_month_count_ignored = 0
    replay_demand_basis_source = "missing"
    replay_demand_basis_label = ""
    replay_demand_basis_units = 0
    predicted_point_count_ignored = 0

    def _normalize_label(label):
        return re.sub(r"\s+", " ", str(label or "").strip())

    def _safe_label_for_series(label, idx):
        clean = _normalize_label(label)
        if clean == "":
            return f"point_{idx + 1}"
        return clean.replace(";", " ").replace("=", " ")

    def _is_predicted_text(value):
        txt = _normalize_label(value).lower()
        if txt == "":
            return False
        if "*" in txt:
            return True
        prediction_tokens = (
            "predicted",
            "prediction",
            "forecast",
            "projected",
            "projection",
            "estimated",
            "estimate",
        )
        return any(token in txt for token in prediction_tokens)

    def _to_bool(value):
        if isinstance(value, bool):
            return value
        txt = _normalize_label(value).lower()
        if txt in {"1", "true", "yes", "y"}:
            return True
        if txt in {"0", "false", "no", "n"}:
            return False
        return _is_predicted_text(txt)

    def _parse_month_key(label):
        txt = _normalize_label(label).lower()
        if txt == "":
            return None

        month_map = {
            "jan": 1, "january": 1,
            "feb": 2, "february": 2,
            "mar": 3, "march": 3,
            "apr": 4, "april": 4,
            "may": 5,
            "jun": 6, "june": 6,
            "jul": 7, "july": 7,
            "aug": 8, "august": 8,
            "sep": 9, "sept": 9, "september": 9,
            "oct": 10, "october": 10,
            "nov": 11, "november": 11,
            "dec": 12, "december": 12,
        }

        # Handles MM/YY and MM/YYYY labels such as 03/26.
        m = re.search(r"\b(\d{1,2})[/-](\d{2,4})\b", txt)
        if m:
            month = _safe_int(m.group(1), 0)
            year = _safe_int(m.group(2), 0)
            if 1 <= month <= 12 and year > 0:
                year = year + 2000 if year < 100 else year
                return (year, month)

        # Handles "Mar 26", "March 2026".
        m = re.search(r"\b([a-z]{3,9})\s+(\d{2,4})\b", txt)
        if m:
            month = month_map.get(m.group(1), 0)
            year = _safe_int(m.group(2), 0)
            if month and year > 0:
                year = year + 2000 if year < 100 else year
                return (year, month)

        # Handles YYYY-MM and YYYY/MM labels.
        m = re.search(r"\b(\d{4})[/-](\d{1,2})\b", txt)
        if m:
            year = _safe_int(m.group(1), 0)
            month = _safe_int(m.group(2), 0)
            if year > 0 and 1 <= month <= 12:
                return (year, month)

        return None

    def _month_key_to_label(month_key):
        if not month_key:
            return ""
        year, month = month_key
        return f"{year:04d}-{month:02d}"

    def _order_values_newest_first(labels, values):
        if not labels or not values:
            return [_safe_int(v, 0) for v in values if _safe_int(v, 0) >= 0]

        parsed = []
        for lbl, val in zip(labels, values):
            qty = _safe_int(val, None)
            if qty is None:
                continue
            dt_key = _parse_month_key(lbl)
            if dt_key is not None:
                parsed.append((dt_key, qty))

        if parsed:
            parsed.sort(key=lambda x: x[0], reverse=True)
            return [qty for _, qty in parsed]

        return [_safe_int(v, 0) for v in values if _safe_int(v, 0) >= 0]

    try:
        sales_el = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="quickInfoEstSales"]'))
        )
        sales_text = (sales_el.text or "").strip()
        current_units = _safe_int(sales_text, 0)

        # Quick-info popup parse
        try:
            sales_el.click()
            time.sleep(0.6)
        except Exception:
            pass

        popup_candidates = [
            (By.XPATH, "//div[contains(., 'Monthly Sales') and string-length(normalize-space()) > 0]"),
            (By.XPATH, "//div[contains(@class,'popover') and contains(., 'Monthly Sales')]"),
            (By.XPATH, "//div[contains(@class,'tooltip') and contains(., 'Monthly Sales')]"),
        ]

        popup_text = ""
        for by, locator in popup_candidates:
            try:
                pop = WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((by, locator))
                )
                popup_text = (pop.text or "").strip()
                if popup_text:
                    break
            except Exception:
                continue

        if popup_text:
            history_text = popup_text
            popup_lines = [line.strip() for line in popup_text.splitlines() if line.strip()]
            month_rows = []
            for line in popup_lines:
                if _is_predicted_text(line):
                    continue
                match = re.search(r"\b([A-Za-z]{3})\s+(\d{2})\s+(\d[\d,]*)\b", line)
                if match:
                    month_rows.append((match.group(1), match.group(2), match.group(3)))
            if month_rows:
                month_map = {
                    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
                    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
                }
                parsed_rows = []
                for mon, yy, val in month_rows:
                    mon_idx = month_map.get(mon.lower(), 0)
                    year_full = 2000 + _safe_int(yy, 0)
                    qty = _safe_int(val, 0)
                    if mon_idx and qty >= 0:
                        parsed_rows.append((year_full, mon_idx, qty))
                parsed_rows.sort(reverse=True)
                history_values = [qty for _, _, qty in parsed_rows]

        # Chart parse while still inside BBP iframe (timing-sensitive path)
        chart_payload = driver.execute_script(
            """
            const ids = ["estSalesMonthlyChart", "buyBotProSalesChart"];
            const toNum = (v) => {
              if (v === null || v === undefined) return null;
              if (typeof v === "number") return Number.isFinite(v) ? v : null;
              const n = Number(String(v).replace(/,/g, "").replace(/[^\\d.-]/g, ""));
              return Number.isFinite(n) ? n : null;
            };
            const hasPredictionToken = (v) => {
              if (v === null || v === undefined) return false;
              const txt = String(v).trim().toLowerCase();
              if (!txt) return false;
              const tokens = ["predicted", "prediction", "forecast", "projected", "projection", "estimated", "estimate"];
              return tokens.some(t => txt.includes(t));
            };
            const truthy = (v) => {
              if (v === true) return true;
              if (v === false || v === null || v === undefined) return false;
              if (typeof v === "number") return Number.isFinite(v) && v !== 0;
              const txt = String(v).trim().toLowerCase();
              if (!txt) return false;
              return ["1", "true", "yes", "y"].includes(txt) || hasPredictionToken(txt);
            };
            const isPredictedPoint = (label, point) => {
              if (hasPredictionToken(label)) return true;
              if (!point || typeof point !== "object") return false;
              const explicitKeys = ["predicted", "isPredicted", "forecast", "isForecast", "projection", "isProjection", "estimated", "isEstimated", "future", "isFuture"];
              for (const key of explicitKeys) {
                if (key in point && truthy(point[key])) return true;
              }
              for (const [k, v] of Object.entries(point)) {
                if (hasPredictionToken(k) && truthy(v)) return true;
                if (typeof v === "string" && hasPredictionToken(v)) return true;
              }
              return false;
            };

            for (const id of ids) {
              const elem = document.getElementById(id);
              if (!elem) continue;

              // Chart.js path
              if (typeof Chart !== "undefined" && Chart.getChart) {
                const chart = Chart.getChart(elem);
                if (chart && chart.data && Array.isArray(chart.data.datasets) && chart.data.datasets.length) {
                  const ds = chart.data.datasets.find(x => String(x.label || "").toLowerCase().includes("sale")) || chart.data.datasets[0];
                  const labels = Array.isArray(chart.data.labels) ? chart.data.labels : [];
                  const rawData = Array.isArray(ds.data) ? ds.data : [];
                  const values = rawData.map(p => (p && typeof p === "object" && ("y" in p)) ? toNum(p.y) : toNum(p));
                  const predicted_flags = rawData.map((p, idx) => isPredictedPoint((idx < labels.length ? labels[idx] : ""), p));
                  if (values.some(v => v !== null)) {
                    return { source: id + ":chartjs", labels, values, predicted_flags };
                  }
                }
              }

              // ApexCharts fallback
              if (window.Apex && Array.isArray(window.Apex._chartInstances)) {
                for (const inst of window.Apex._chartInstances) {
                  try {
                    const cfg = inst && inst.w && inst.w.config ? inst.w.config : null;
                    if (!cfg || !Array.isArray(cfg.series) || !cfg.series.length) continue;
                    const ds = cfg.series.find(x => String(x.name || "").toLowerCase().includes("sale")) || cfg.series[0];
                    const raw = Array.isArray(ds.data) ? ds.data : [];
                    const labels = raw.map(p => (p && typeof p === "object" && ("x" in p)) ? String(p.x) : "");
                    const values = raw
                      .map(p => (p && typeof p === "object" && ("y" in p)) ? toNum(p.y) : toNum(p));
                    const predicted_flags = raw.map((p, idx) => isPredictedPoint((idx < labels.length ? labels[idx] : ""), p));
                    if (values.some(v => v !== null)) {
                      return { source: id + ":apex", labels, values, predicted_flags };
                    }
                  } catch (e) {}
                }
              }
            }
            return { source: "", labels: [], values: [], predicted_flags: [] };
            """
        )

        chart_labels = chart_payload.get("labels", []) if isinstance(chart_payload, dict) else []
        chart_values_raw = chart_payload.get("values", []) if isinstance(chart_payload, dict) else []
        chart_predicted_flags = chart_payload.get("predicted_flags", []) if isinstance(chart_payload, dict) else []
        chart_source = chart_payload.get("source", "") if isinstance(chart_payload, dict) else ""

        chart_points = []
        if isinstance(chart_values_raw, list):
            for idx, raw_val in enumerate(chart_values_raw):
                units = _safe_int(raw_val, None)
                if units is None or units < 0:
                    continue
                label = chart_labels[idx] if isinstance(chart_labels, list) and idx < len(chart_labels) else ""
                is_predicted = False
                if isinstance(chart_predicted_flags, list) and idx < len(chart_predicted_flags):
                    is_predicted = _to_bool(chart_predicted_flags[idx])
                if _is_predicted_text(label):
                    is_predicted = True
                chart_points.append(
                    {
                        "label": _normalize_label(label),
                        "units": units,
                        "is_predicted": is_predicted,
                    }
                )

        if chart_points:
            chart_month_labels = [point["label"] for point in chart_points]
            chart_month_units = [point["units"] for point in chart_points]
            chart_series = ";".join(
                f"{_safe_label_for_series(point['label'], idx)}={point['units']}{'[pred]' if point['is_predicted'] else ''}"
                for idx, point in enumerate(chart_points)
            )

            current_month_key = (datetime.utcnow().year, datetime.utcnow().month)
            past_points = []
            current_points = []
            future_points = []
            unknown_points = []
            predicted_points = []

            for point in chart_points:
                label = point["label"]
                units = point["units"]
                month_key = _parse_month_key(label)
                payload = {
                    "label": label,
                    "units": units,
                    "month_key": month_key,
                    "is_predicted": bool(point.get("is_predicted", False)),
                }
                if payload["is_predicted"]:
                    predicted_points.append(payload)
                    continue
                if month_key is None:
                    unknown_points.append(payload)
                elif month_key < current_month_key:
                    past_points.append(payload)
                elif month_key == current_month_key:
                    current_points.append(payload)
                else:
                    future_points.append(payload)

            if past_points:
                past_points.sort(key=lambda p: p["month_key"], reverse=True)
                history_values = [int(p["units"]) for p in past_points][:12]
                last_completed_month_label = _month_key_to_label(past_points[0]["month_key"])
                last_completed_month_units = int(past_points[0]["units"])

            if current_points:
                current_point = current_points[-1]
                current_month_label = _month_key_to_label(current_point["month_key"])
                current_month_units = int(current_point["units"])

            predicted_point_count_ignored = len(predicted_points)
            future_month_count_ignored = len(future_points) + predicted_point_count_ignored

            if current_units <= 0 and current_month_units > 0:
                current_units = current_month_units

            if not history_values and unknown_points:
                ordered_unknown = _order_values_newest_first(
                    [p["label"] for p in unknown_points],
                    [p["units"] for p in unknown_points],
                )
                if len(ordered_unknown) >= 2:
                    history_values = ordered_unknown[:12]

            if not history_text:
                history_text = f"chart_source={chart_source}"
    except Exception as e:
        logger.info(f"BBP monthly sales capture skipped: {e}")

    if last_completed_month_units > 0:
        replay_demand_basis_source = "bbp_last_completed_month"
        replay_demand_basis_label = last_completed_month_label
        replay_demand_basis_units = last_completed_month_units
    elif history_values:
        history_recent_avg = _safe_int(round(_mean(history_values[:3])), 0)
        if history_recent_avg > 0:
            replay_demand_basis_source = "bbp_recent_history_fallback"
            replay_demand_basis_label = "history_recent_avg"
            replay_demand_basis_units = history_recent_avg
        else:
            replay_demand_basis_source = "bbp_zero_history"
            replay_demand_basis_label = "zero_history"
            replay_demand_basis_units = 0
    elif current_units > 0:
        replay_demand_basis_source = "bbp_current_month_fallback"
        replay_demand_basis_label = current_month_label or "current_month_quickinfo"
        replay_demand_basis_units = current_units
    else:
        replay_demand_basis_source = "bbp_zero_history"
        replay_demand_basis_label = "zero_history"
        replay_demand_basis_units = 0

    if chart_source:
        logger.info(
            f"BBP sales history source => {chart_source}, current={current_units}, "
            f"last_completed={last_completed_month_label}:{last_completed_month_units}, "
            f"future_ignored={future_month_count_ignored}, predicted_ignored={predicted_point_count_ignored}, "
            f"points={len(history_values)}"
        )

    return {
        "current_units": current_units,
        "history_values": history_values,
        "history_text": history_text,
        "chart_source": chart_source,
        "chart_month_labels": chart_month_labels,
        "chart_month_units": chart_month_units,
        "chart_series": chart_series,
        "last_completed_month_label": last_completed_month_label,
        "last_completed_month_units": last_completed_month_units,
        "current_month_label": current_month_label,
        "current_month_units": current_month_units,
        "future_month_count_ignored": future_month_count_ignored,
        "replay_demand_basis_source": replay_demand_basis_source,
        "replay_demand_basis_label": replay_demand_basis_label,
        "replay_demand_basis_units": replay_demand_basis_units,
    }


def _clamp(value, lo, hi):
    try:
        return max(lo, min(hi, value))
    except Exception:
        return lo


def _env_float(name, default):
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return float(default)


def _env_flag(name, default=False):
    raw = os.getenv(name, "1" if default else "0").strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


_WEBSCRAPE_TIMING_SCALE = _env_float("F_WEBSCRAPE_TIMING_SCALE", 1.0)
_WEBSCRAPE_SLEEP_CAP = _env_float("F_WEBSCRAPE_SLEEP_CAP_SEC", 2.2)


def _scaled_wait_seconds(seconds, *, floor=0.4, cap=None):
    scaled = _clamp(float(seconds) * _WEBSCRAPE_TIMING_SCALE, floor, 60.0)
    local_cap = _WEBSCRAPE_SLEEP_CAP if cap is None else float(cap)
    if local_cap > 0:
        scaled = min(scaled, local_cap)
    return max(floor, scaled)


def _human_sleep(low=0.2, high=0.6, *, cap=None):
    lo = _scaled_wait_seconds(low, floor=0.05, cap=cap if cap is not None else 1.4)
    hi = _scaled_wait_seconds(high, floor=lo + 0.02, cap=cap if cap is not None else 1.9)
    if hi < lo:
        hi = lo
    time.sleep(random.uniform(lo, hi))


def _parse_chart_timestamp(raw_ts):
    """
    Convert BBP chart timestamp variants into a naive datetime.
    Supports:
    - unix milliseconds / seconds
    - ISO date strings
    - common calendar labels
    """
    if raw_ts is None:
        return None

    if isinstance(raw_ts, (int, float)):
        ts = float(raw_ts)
        try:
            if ts > 10_000_000_000:
                return datetime.fromtimestamp(ts / 1000.0)
            if ts > 100_000_000:
                return datetime.fromtimestamp(ts)
        except Exception:
            return None
        return None

    txt = str(raw_ts).strip()
    if not txt:
        return None

    if re.fullmatch(r"\d+(\.\d+)?", txt):
        return _parse_chart_timestamp(float(txt))

    iso_try = txt.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso_try)
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt
    except Exception:
        pass

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%b %d %Y", "%d %b %Y", "%b %Y", "%b %y"):
        try:
            return datetime.strptime(txt, fmt)
        except Exception:
            continue

    return None


def _classify_chart_label(label):
    low = (label or "").strip().lower()
    if not low:
        return None
    if "buy box" in low or "buybox" in low:
        return "buy_box"
    if "amazon" in low:
        return "amazon"
    if re.search(r"\bfba\b", low):
        return "fba"
    if re.search(r"\bfbm\b", low) or "merchant fulfilled" in low:
        return "fbm"
    if "bsr" in low or "sales rank" in low or low == "rank":
        return "bsr"
    return None


def _classify_history_lane(label):
    low = (label or "").strip().lower()
    if not low:
        return None
    if "buybox" in low or "buy box" in low:
        return "buy_box"
    if "amazon" in low:
        return "amazon"
    if re.search(r"\bfba\b", low):
        return "fba"
    if re.search(r"\bfbm\b", low) or "merchant fulfilled" in low:
        return "fbm"
    if "lowest new" in low or low == "new" or low.startswith("new "):
        return "new"
    return None


def _parse_window_days_from_header(text):
    raw = (text or "").strip().lower()
    if not raw:
        return None

    if "1 year" in raw or "12 month" in raw or "365" in raw:
        return 365
    if "180" in raw:
        return 180
    if "90" in raw:
        return 90
    if "30" in raw:
        return 30
    if "current" in raw or "now" in raw:
        return 0
    return None


def _default_history_windows(col_count):
    if col_count == 4:
        return [30, 90, 180, 365]
    if col_count == 3:
        return [30, 90, 180]
    if col_count == 5:
        return [0, 30, 90, 180, 365]
    return [0] * max(col_count, 0)


def _extract_lane_history_from_table(hist_table):
    """
    Parse BBP average-statistics table into lane->window map.
    Returns:
      {
        "lanes": {"amazon": {30: x, ...}, ...},
        "raw_rows": {"Amazon (£)": [..], ...},
        "window_columns": [30, 90, 180, 365],
      }
    """
    lanes = {
        "amazon": {},
        "fba": {},
        "fbm": {},
        "buy_box": {},
        "new": {},
    }
    raw_rows = {}
    window_columns = []

    try:
        header_cells = hist_table.find_elements(By.CSS_SELECTOR, "thead tr th")
        if not header_cells:
            first_row_headers = hist_table.find_elements(By.CSS_SELECTOR, "tr:first-child th")
            header_cells = first_row_headers
        if header_cells and len(header_cells) > 1:
            for h in header_cells[1:]:
                window_columns.append(_parse_window_days_from_header(h.text))
    except Exception:
        window_columns = []

    rows = hist_table.find_elements(By.TAG_NAME, "tr")
    for r in rows:
        tds = r.find_elements(By.TAG_NAME, "td")
        if len(tds) < 2:
            continue

        key = (tds[0].text or "").strip()
        vals = []
        for c in tds[1:]:
            raw = (c.text or "").strip()
            vals.append(_safe_float(raw, 0.0) if raw and raw != "-" else 0.0)
        raw_rows[key] = vals

        lane = _classify_history_lane(key)
        if not lane:
            continue

        if not window_columns or len(window_columns) != len(vals):
            col_windows = _default_history_windows(len(vals))
        else:
            col_windows = []
            defaults = _default_history_windows(len(vals))
            for idx, w in enumerate(window_columns):
                if w in (0, 30, 90, 180, 365):
                    col_windows.append(w)
                else:
                    col_windows.append(defaults[idx] if idx < len(defaults) else 0)

        lane_map = lanes.get(lane, {})
        for idx, val in enumerate(vals):
            win = col_windows[idx] if idx < len(col_windows) else 0
            if win <= 0 or val <= 0:
                continue
            lane_map[win] = val
        lanes[lane] = lane_map
        if col_windows:
            window_columns = col_windows

    return {
        "lanes": lanes,
        "raw_rows": raw_rows,
        "window_columns": window_columns if window_columns else [30, 90, 180, 365],
    }


def _choose_unavailable_pricing_plan(lane_history, current_auto_price, break_even_price, history_has_365_override=None):
    """
    Build lane-aware pricing decision when BBP live pricing is unavailable/unreliable.
    """
    primary_lanes = ("amazon", "fba", "buy_box")
    support_lanes = ("fbm", "new")
    window_pref = (30, 90, 180, 365)

    def _get(lane, days):
        return _safe_float((lane_history.get(lane, {}) or {}).get(days, 0.0), 0.0)

    primary_values = []
    all_values = []
    for lane in (*primary_lanes, *support_lanes):
        lane_map = lane_history.get(lane, {}) or {}
        for days, value in lane_map.items():
            val = _safe_float(value, 0.0)
            if val <= 0:
                continue
            all_values.append(val)
            if lane in primary_lanes:
                primary_values.append(val)

    history_low = min(primary_values) if primary_values else (min(all_values) if all_values else 0.0)
    history_high = max(primary_values) if primary_values else (max(all_values) if all_values else 0.0)

    market_30_candidates = [_get(lane, 30) for lane in primary_lanes if _get(lane, 30) > 0]
    market_30_min = min(market_30_candidates) if market_30_candidates else 0.0

    chosen_lane = ""
    chosen_window = 0
    chosen_price = 0.0
    for days in window_pref:
        for lane in primary_lanes:
            val = _get(lane, days)
            if val > 0:
                chosen_lane = lane
                chosen_window = days
                chosen_price = val
                break
        if chosen_price > 0:
            break

    if chosen_price <= 0:
        for days in window_pref:
            for lane in support_lanes:
                val = _get(lane, days)
                if val > 0:
                    chosen_lane = lane
                    chosen_window = days
                    chosen_price = val
                    break
            if chosen_price > 0:
                break

    if chosen_price > 0 and history_low > 0 and history_high >= history_low:
        chosen_price = _clamp(chosen_price, history_low, history_high)

    has_365_from_table = any(_get(lane, 365) > 0 for lane in (*primary_lanes, *support_lanes))
    has_365_history = bool(history_has_365_override) if history_has_365_override is not None else has_365_from_table
    placeholder_price = _safe_float(os.getenv("BBP_UNAVAILABLE_PLACEHOLDER_PRICE", "49.99"), 49.99)
    unreliable_ratio = _safe_float(os.getenv("BBP_UNAVAILABLE_RATIO_THRESHOLD", "1.8"), 1.8)

    unavailable_detected = False
    if current_auto_price <= 0:
        unavailable_detected = True
    elif market_30_min > 0 and current_auto_price >= max(placeholder_price, market_30_min * unreliable_ratio):
        unavailable_detected = True
    elif market_30_min <= 0 and current_auto_price >= placeholder_price and chosen_price > 0:
        unavailable_detected = True

    pricing_mode = "fallback_history" if unavailable_detected and chosen_price > 0 else "live"

    fallback_roi = 0.0
    break_even = _safe_float(break_even_price, 0.0)
    if chosen_price > 0 and break_even > 0:
        fallback_roi = ((chosen_price - break_even) / break_even) * 100.0

    if chosen_window in (30, 90):
        confidence = "HIGH"
    elif chosen_window == 180:
        confidence = "MEDIUM"
    elif chosen_window == 365:
        confidence = "LOW"
    else:
        confidence = "LOW"

    fbm_30 = _get("fbm", 30)
    if fbm_30 <= 0:
        fbm_30 = _get("new", 30)
    fbm_undercut_flag = bool(fbm_30 > 0 and chosen_price > 0 and fbm_30 <= (chosen_price * 0.85))

    decision_note = "live_price_mode"
    if unavailable_detected and chosen_price <= 0:
        decision_note = "unavailable_detected_no_history_price"
    elif unavailable_detected and not has_365_history:
        decision_note = "unavailable_detected_no_365_history"
    elif unavailable_detected:
        decision_note = "unavailable_detected_using_history_fallback"

    return {
        "pricing_mode": pricing_mode,
        "unavailable_detected": unavailable_detected,
        "price_history_365d_exists": has_365_history,
        "fallback_lane_used": chosen_lane,
        "fallback_window_used": chosen_window,
        "fallback_price": round(chosen_price, 2) if chosen_price > 0 else 0.0,
        "fallback_roi": round(fallback_roi, 2),
        "fallback_confidence": confidence,
        "fbm_undercut_flag": fbm_undercut_flag,
        "history_low": round(history_low, 2) if history_low > 0 else 0.0,
        "history_high": round(history_high, 2) if history_high > 0 else 0.0,
        "market_30_min": round(market_30_min, 2) if market_30_min > 0 else 0.0,
        "pricing_decision_note": decision_note,
    }


def _daily_reduce_series(points, agg="last"):
    """
    points: [(datetime, value), ...]
    Returns dict: {YYYY-MM-DD: value}
    """
    if not points:
        return {}
    ordered = sorted(points, key=lambda x: x[0])
    bucket = {}
    for dt, val in ordered:
        key = dt.strftime("%Y-%m-%d")
        bucket.setdefault(key, []).append((dt, val))

    out = {}
    for key, vals in bucket.items():
        nums = [v for _, v in vals if _safe_float(v, 0.0) > 0]
        if not nums:
            continue
        if agg == "avg":
            out[key] = sum(nums) / len(nums)
        elif agg == "min":
            out[key] = min(nums)
        else:
            out[key] = vals[-1][1]
    return out


def _fill_series_nearest(daily_map, ordered_days, max_gap_days=3):
    """
    Fill missing day values by nearest known value within max_gap_days.
    Returns (filled_map, synthetic_points_count).
    """
    existing = {d: _safe_float(v, 0.0) for d, v in (daily_map or {}).items() if _safe_float(v, 0.0) > 0}
    filled = dict(existing)
    if not ordered_days:
        return filled, 0
    if not existing:
        return filled, 0

    known_idx = [i for i, d in enumerate(ordered_days) if d in existing]
    synthetic = 0
    for i, day in enumerate(ordered_days):
        if day in filled:
            continue
        prev_i = next((k for k in reversed(known_idx) if k < i), None)
        next_i = next((k for k in known_idx if k > i), None)

        cand = []
        if prev_i is not None:
            cand.append((abs(i - prev_i), prev_i))
        if next_i is not None:
            cand.append((abs(next_i - i), next_i))
        if not cand:
            continue
        cand.sort(key=lambda x: x[0])
        dist, src_i = cand[0]
        if dist <= max_gap_days:
            src_day = ordered_days[src_i]
            src_val = _safe_float(existing.get(src_day, 0.0), 0.0)
            if src_val > 0:
                filled[day] = src_val
                synthetic += 1
    return filled, synthetic


def _longest_phase_streak(phases, target):
    best = 0
    cur = 0
    for p in phases:
        if p == target:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def _phase_for_roi(roi, target_roi, breakeven_band):
    if roi < (-1.0 * breakeven_band):
        return "loss"
    if roi <= breakeven_band:
        return "break_even"
    if roi < target_roi:
        return "low_roi"
    return "profit"


def _avg_positive(values):
    vals = [float(v) for v in values if _safe_float(v, 0.0) > 0]
    if not vals:
        return 0.0
    return sum(vals) / len(vals)


def extract_bbp_price_phase_snapshot(driver, break_even_price, max_days=None):
    """
    Build a timestamp-aligned daily history from buyBotProSalesChart and
    classify each day into practical trading phases.

    Output is non-gating for now. It provides score + recommendation data.
    """
    target_roi = _safe_float(os.getenv("BBP_TARGET_ROI_PERCENT", "20"), 20.0)
    breakeven_band = _safe_float(os.getenv("BBP_BREAK_EVEN_BAND_PERCENT", "1"), 1.0)

    result = {
        "history_window_days": 0,
        "history_data_points": 0,
        "history_gap_fill_rate": 0.0,
        "pricing_history_score": 50,
        "ranking_history_score": 50,
        "history_operational_score": 50,
        "phase_profit_pct": 0.0,
        "phase_low_roi_pct": 0.0,
        "phase_break_even_pct": 0.0,
        "phase_loss_pct": 0.0,
        "phase_longest_profit_days": 0,
        "phase_longest_low_roi_days": 0,
        "phase_longest_break_even_days": 0,
        "phase_longest_loss_days": 0,
        "phase_current": "unknown",
        "phase_recommendation": "UNKNOWN",
        "exit_strategy": "REVIEW",
        "bsr_recent_avg": 0.0,
        "bsr_prev_avg": 0.0,
        "bsr_trend": "unknown",
        "chosen_price_recent_avg": 0.0,
        "chosen_price_prev_avg": 0.0,
        "price_trend_pct": 0.0,
        "history_source": "",
        "price_history_span_days": 0,
        "price_history_365d_exists": False,
        "price_history_points_365d": 0,
        "price_hist_table_raw": "",
        "chart_price_daily_series": "",
        "chart_bsr_daily_series": "",
        "chart_phase_daily_series": "",
        "chart_raw_amazon_daily_series": "",
        "chart_raw_fba_daily_series": "",
        "chart_raw_fbm_daily_series": "",
        "chart_raw_buy_box_daily_series": "",
        "chart_raw_bsr_daily_series": "",
    }

    try:
        payload = driver.execute_script(
            """
            const chartId = "buyBotProSalesChart";
            const elem = document.getElementById(chartId);
            if (!elem) {
              return { success: false, source: "", error: "chart_element_missing", datasets: [] };
            }

            const norm = (point, idx, labels) => {
              if (point && typeof point === "object") {
                const xVal = ("x" in point) ? point.x : ((labels && labels[idx] !== undefined) ? labels[idx] : idx);
                const yVal = ("y" in point) ? point.y : null;
                return { x: xVal, y: yVal };
              }
              const xVal = (labels && labels[idx] !== undefined) ? labels[idx] : idx;
              return { x: xVal, y: point };
            };

            // Chart.js path
            if (typeof Chart !== "undefined" && Chart.getChart) {
              const chart = Chart.getChart(elem);
              if (chart && chart.data && Array.isArray(chart.data.datasets) && chart.data.datasets.length) {
                const labels = Array.isArray(chart.data.labels) ? chart.data.labels : [];
                const datasets = chart.data.datasets.map(ds => ({
                  label: String(ds.label || ""),
                  data: (Array.isArray(ds.data) ? ds.data : []).map((p, i) => norm(p, i, labels))
                }));
                return { success: true, source: chartId + ":chartjs", error: "", datasets };
              }
            }

            // ApexCharts fallback
            if (window.Apex && Array.isArray(window.Apex._chartInstances)) {
              for (const inst of window.Apex._chartInstances) {
                try {
                  const cfg = inst && inst.w && inst.w.config ? inst.w.config : null;
                  if (!cfg || !Array.isArray(cfg.series) || !cfg.series.length) continue;
                  const datasets = cfg.series.map(ds => ({
                    label: String(ds.name || ds.label || ""),
                    data: (Array.isArray(ds.data) ? ds.data : []).map((p, i) => {
                      if (p && typeof p === "object") {
                        return { x: ("x" in p) ? p.x : i, y: ("y" in p) ? p.y : null };
                      }
                      return { x: i, y: p };
                    })
                  }));
                  if (datasets.length) {
                    return { success: true, source: chartId + ":apex", error: "", datasets };
                  }
                } catch (e) {}
              }
            }

            return { success: false, source: "", error: "chart_instance_missing", datasets: [] };
            """
        )
    except Exception as e:
        logger.info(f"[PhaseHistory] chart script failed: {e}")
        return result

    if not isinstance(payload, dict) or not payload.get("success"):
        err = payload.get("error", "unknown") if isinstance(payload, dict) else "invalid_payload"
        logger.info(f"[PhaseHistory] chart payload unavailable: {err}")
        return result

    datasets = payload.get("datasets", [])
    result["history_source"] = payload.get("source", "")
    if not isinstance(datasets, list) or not datasets:
        return result

    seen_labels = []
    series_points = {
        "amazon": [],
        "fba": [],
        "fbm": [],
        "buy_box": [],
        "bsr": [],
    }

    total_points = 0
    for ds in datasets:
        label_txt = ds.get("label", "") if isinstance(ds, dict) else ""
        if label_txt:
            seen_labels.append(str(label_txt))
        kind = _classify_chart_label(label_txt)
        if not kind:
            continue
        raw_data = ds.get("data", []) if isinstance(ds, dict) else []
        if not isinstance(raw_data, list):
            continue
        for p in raw_data:
            if not isinstance(p, dict):
                continue
            dt = _parse_chart_timestamp(p.get("x"))
            val = _safe_float(p.get("y"), 0.0)
            if dt is None or val <= 0:
                continue
            series_points[kind].append((dt, val))
            total_points += 1

    result["history_data_points"] = total_points
    if total_points == 0:
        return result

    price_datetimes = []
    for key in ("amazon", "fba", "fbm", "buy_box"):
        for dt, val in series_points[key]:
            if _safe_float(val, 0.0) > 0:
                price_datetimes.append(dt)
    if price_datetimes:
        first_dt = min(price_datetimes).date()
        last_dt = max(price_datetimes).date()
        span_days = max((last_dt - first_dt).days + 1, 0)
        result["price_history_span_days"] = span_days
        today_utc = datetime.utcnow().date()
        cutoff_365 = today_utc - timedelta(days=365)
        recent_points = [dt for dt in price_datetimes if dt.date() >= cutoff_365]
        result["price_history_points_365d"] = len(recent_points)
        result["price_history_365d_exists"] = bool(recent_points)

    if not series_points["bsr"]:
        logger.warning(
            "[PhaseHistory] BSR series missing for chart parse. "
            f"source={result.get('history_source', '')}, labels={seen_labels[:12]}"
        )

    daily_raw = {
        "amazon": _daily_reduce_series(series_points["amazon"], agg="last"),
        "fba": _daily_reduce_series(series_points["fba"], agg="last"),
        "fbm": _daily_reduce_series(series_points["fbm"], agg="last"),
        "buy_box": _daily_reduce_series(series_points["buy_box"], agg="last"),
        "bsr": _daily_reduce_series(series_points["bsr"], agg="avg"),
    }

    all_days = set()
    for mp in daily_raw.values():
        all_days.update(mp.keys())
    if not all_days:
        return result

    max_dt = datetime.strptime(max(all_days), "%Y-%m-%d").date()
    min_available_dt = datetime.strptime(min(all_days), "%Y-%m-%d").date()
    max_days_cap = _safe_int(max_days, 0)
    if max_days_cap > 0:
        min_dt = max(max_dt - timedelta(days=max(max_days_cap - 1, 0)), min_available_dt)
    else:
        min_dt = min_available_dt
    ordered_days = []
    cur = min_dt
    while cur <= max_dt:
        ordered_days.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)

    result["history_window_days"] = len(ordered_days)

    filled = {}
    synthetic_total = 0
    for key in ("amazon", "fba", "fbm", "buy_box"):
        filled[key], syn = _fill_series_nearest(daily_raw[key], ordered_days, max_gap_days=3)
        synthetic_total += syn
    filled["bsr"], syn_bsr = _fill_series_nearest(daily_raw["bsr"], ordered_days, max_gap_days=7)
    synthetic_total += syn_bsr

    denom = max(len(ordered_days) * 5, 1)
    result["history_gap_fill_rate"] = round((synthetic_total / denom) * 100.0, 2)

    break_even = _safe_float(break_even_price, 0.0)
    if break_even <= 0:
        return result

    day_rows = []
    for day in ordered_days:
        a = _safe_float(filled["amazon"].get(day, 0.0), 0.0)
        f = _safe_float(filled["fba"].get(day, 0.0), 0.0)
        m = _safe_float(filled["fbm"].get(day, 0.0), 0.0)
        b = _safe_float(filled["buy_box"].get(day, 0.0), 0.0)
        bsr = _safe_float(filled["bsr"].get(day, 0.0), 0.0)

        candidates = []
        if a > 0:
            candidates.append(("amazon", a))
        if f > 0:
            candidates.append(("fba", f))
        if m > 0:
            candidates.append(("fbm", m))
        if b > 0:
            candidates.append(("buy_box", b))
        if not candidates:
            continue

        candidates.sort(key=lambda x: x[1])
        chosen_source, chosen_price = candidates[0]
        roi = ((chosen_price - break_even) / break_even) * 100.0
        phase = _phase_for_roi(roi, target_roi=target_roi, breakeven_band=breakeven_band)

        day_rows.append({
            "day": day,
            "chosen_source": chosen_source,
            "chosen_price": chosen_price,
            "roi": roi,
            "phase": phase,
            "bsr": bsr,
        })

    if not day_rows:
        return result

    result["chart_price_daily_series"] = ";".join(
        f"{row['day']}={_safe_float(row.get('chosen_price', 0.0), 0.0):.2f}" for row in day_rows
    )
    result["chart_bsr_daily_series"] = ";".join(
        f"{row['day']}={_safe_float(row.get('bsr', 0.0), 0.0):.2f}" for row in day_rows
    )
    result["chart_phase_daily_series"] = ";".join(
        f"{row['day']}={row.get('phase', '')}" for row in day_rows
    )

    def _series_from_daily_map(day_map):
        if not isinstance(day_map, dict):
            return ""
        parts = []
        for day in sorted(day_map.keys()):
            val = _safe_float(day_map.get(day, 0.0), 0.0)
            if val <= 0:
                continue
            parts.append(f"{day}={val:.2f}")
        return ";".join(parts)

    result["chart_raw_amazon_daily_series"] = _series_from_daily_map(daily_raw.get("amazon", {}))
    result["chart_raw_fba_daily_series"] = _series_from_daily_map(daily_raw.get("fba", {}))
    result["chart_raw_fbm_daily_series"] = _series_from_daily_map(daily_raw.get("fbm", {}))
    result["chart_raw_buy_box_daily_series"] = _series_from_daily_map(daily_raw.get("buy_box", {}))
    result["chart_raw_bsr_daily_series"] = _series_from_daily_map(daily_raw.get("bsr", {}))

    phase_counts = {"profit": 0, "low_roi": 0, "break_even": 0, "loss": 0}
    phase_series = []
    for row in day_rows:
        ph = row["phase"]
        phase_counts[ph] = phase_counts.get(ph, 0) + 1
        phase_series.append(ph)

    n = float(len(day_rows))
    profit_pct = (phase_counts["profit"] / n) * 100.0
    low_pct = (phase_counts["low_roi"] / n) * 100.0
    break_pct = (phase_counts["break_even"] / n) * 100.0
    loss_pct = (phase_counts["loss"] / n) * 100.0

    result["phase_profit_pct"] = round(profit_pct, 2)
    result["phase_low_roi_pct"] = round(low_pct, 2)
    result["phase_break_even_pct"] = round(break_pct, 2)
    result["phase_loss_pct"] = round(loss_pct, 2)
    result["phase_longest_profit_days"] = _longest_phase_streak(phase_series, "profit")
    result["phase_longest_low_roi_days"] = _longest_phase_streak(phase_series, "low_roi")
    result["phase_longest_break_even_days"] = _longest_phase_streak(phase_series, "break_even")
    result["phase_longest_loss_days"] = _longest_phase_streak(phase_series, "loss")
    result["phase_current"] = phase_series[-1] if phase_series else "unknown"

    last_30 = day_rows[-30:]
    prev_30 = day_rows[-60:-30] if len(day_rows) >= 60 else []

    price_recent = _avg_positive([r["chosen_price"] for r in last_30])
    price_prev = _avg_positive([r["chosen_price"] for r in prev_30])
    result["chosen_price_recent_avg"] = round(price_recent, 2)
    result["chosen_price_prev_avg"] = round(price_prev, 2)
    if price_prev > 0:
        result["price_trend_pct"] = round(((price_recent - price_prev) / price_prev) * 100.0, 2)
    else:
        result["price_trend_pct"] = 0.0

    bsr_recent = _avg_positive([r["bsr"] for r in last_30])
    bsr_prev = _avg_positive([r["bsr"] for r in prev_30])
    result["bsr_recent_avg"] = round(bsr_recent, 2)
    result["bsr_prev_avg"] = round(bsr_prev, 2)

    bsr_trend = "unknown"
    if bsr_recent > 0 and bsr_prev > 0:
        change = ((bsr_recent - bsr_prev) / bsr_prev) * 100.0
        if change <= -10.0:
            bsr_trend = "improving"
        elif change >= 10.0:
            bsr_trend = "worsening"
        else:
            bsr_trend = "stable"
    result["bsr_trend"] = bsr_trend

    pricing_score = 100.0
    pricing_score -= low_pct * 0.35
    pricing_score -= break_pct * 0.80
    pricing_score -= loss_pct * 1.25
    if result["phase_longest_loss_days"] >= 5:
        pricing_score -= 12.0
    if result["phase_longest_break_even_days"] >= 10:
        pricing_score -= 8.0
    if result["price_trend_pct"] <= -8.0:
        pricing_score -= 8.0
    elif result["price_trend_pct"] >= 8.0:
        pricing_score += 4.0
    result["pricing_history_score"] = int(round(_clamp(pricing_score, 0.0, 100.0)))

    ranking_score = 50.0
    if bsr_recent > 0:
        if bsr_recent <= 20_000:
            ranking_score += 28.0
        elif bsr_recent <= 50_000:
            ranking_score += 15.0
        elif bsr_recent <= 100_000:
            ranking_score += 5.0
        else:
            ranking_score -= 12.0
    else:
        ranking_score -= 6.0

    if bsr_trend == "improving":
        ranking_score += 18.0
    elif bsr_trend == "stable":
        ranking_score += 6.0
    elif bsr_trend == "worsening":
        ranking_score -= 18.0

    bsr_coverage = (
        len([r for r in day_rows if _safe_float(r.get("bsr"), 0.0) > 0]) / max(len(day_rows), 1)
    )
    if bsr_coverage < 0.4:
        ranking_score -= 10.0
    elif bsr_coverage < 0.7:
        ranking_score -= 4.0

    result["ranking_history_score"] = int(round(_clamp(ranking_score, 0.0, 100.0)))
    result["history_operational_score"] = int(
        round(_clamp((result["pricing_history_score"] * 0.60) + (result["ranking_history_score"] * 0.40), 0.0, 100.0))
    )

    if loss_pct >= 25.0 or result["phase_longest_loss_days"] >= 10:
        phase_reco = "AVOID"
        exit_strategy = "SELL_OFF_ALLOWED"
    elif loss_pct >= 10.0 or (low_pct + break_pct) >= 70.0:
        phase_reco = "RISKY_HOLD"
        exit_strategy = "ALLOW_LOW_ROI_EXIT"
    elif profit_pct >= 55.0 and loss_pct <= 5.0:
        phase_reco = "STRONG_HOLD"
        exit_strategy = "TARGET_ROI_ONLY"
    elif profit_pct >= 35.0:
        phase_reco = "HOLD_WITH_PATIENCE"
        exit_strategy = "ALLOW_LOW_ROI_EXIT"
    else:
        phase_reco = "MIXED"
        exit_strategy = "ALLOW_LOW_ROI_EXIT"

    # Trend downgrade guard: avoid over-confident labels when direction is deteriorating.
    if bsr_trend == "worsening" and result["price_trend_pct"] <= -8.0:
        if phase_reco == "STRONG_HOLD":
            phase_reco = "HOLD_WITH_PATIENCE"
            exit_strategy = "ALLOW_LOW_ROI_EXIT"
        elif phase_reco == "HOLD_WITH_PATIENCE":
            phase_reco = "RISKY_HOLD"
            exit_strategy = "ALLOW_LOW_ROI_EXIT"

    result["phase_recommendation"] = phase_reco
    result["exit_strategy"] = exit_strategy
    return result


def choose_units_with_amazon_guardrail(amazon_floor, bbp_units, cap_multiplier=1.5):
    """
    Demand arbitration rules:
    - If Amazon floor exists, Amazon is primary guardrail.
    - BBP can refine inside a reasonable cap.
    - If Amazon clue is missing, treat demand lane as <50 and use BBP only within that lane.
    Returns (chosen_units, confidence_score, note).
    """
    bbp_units_i = max(_safe_int(bbp_units, 0), 0)
    floor = None if amazon_floor is None else max(_safe_int(amazon_floor, 0), 0)

    if floor is not None and floor > 0:
        cap = int(round(floor * max(_safe_float(cap_multiplier, 1.0), 1.0)))
        if bbp_units_i <= 0:
            return floor, 55, "amazon_floor_only"
        if bbp_units_i < floor:
            return floor, 72, "bbp_below_amazon_floor"
        if bbp_units_i <= cap:
            return bbp_units_i, 88, "bbp_within_amazon_band"
        return floor, 48, "bbp_above_amazon_cap"

    # No Amazon monthly clue shown => assumed lane under 50.
    if bbp_units_i <= 50:
        return bbp_units_i, 66, "amazon_missing_bbp_under_50"
    return 50, 40, "amazon_missing_bbp_capped_to_50"


def _pre_review_kill_code(*, chosen_units, dashboard_yes_or_no, new_seller_counts):
    units = max(_safe_int(chosen_units, 0), 0)
    if units <= PRE_REVIEW_LOW_SALES_MAX_UNITS:
        return "LOW_SALES_CAPITAL_IDLE_RISK"

    dashboard = _normalize_text(dashboard_yes_or_no).upper()
    seller_values = [_safe_float(v, 0.0) for v in (new_seller_counts or [])]
    seller_values = [v for v in seller_values if v >= 0]
    if dashboard == "NO" and seller_values and max(seller_values) < 2.0:
        return "DASHBOARD_NO_LOW_SELLER_COUNT"
    return ""


def _extract_amazon_monthly_sold_signal(driver):
    selectors = [
        "#social-proofing-faceout-title-tk_bought",
        "#socialProofingAsinFaceout_feature_div",
        "#zeitgeistBadge_feature_div",
    ]
    pattern = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?\s*[Kk]?\+?\s+bought\s+in\s+past\s+month", re.I)
    for selector in selectors:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, selector):
                text = _normalize_text(el.text)
                match = pattern.search(text)
                if match:
                    return match.group(0)
        except Exception:
            continue
    try:
        body_text = _normalize_text(driver.find_element(By.TAG_NAME, "body").text)
        match = pattern.search(body_text)
        if match:
            return match.group(0)
    except Exception:
        pass
    return ""


def _build_pre_review_fail_payload(
    *,
    fail_code,
    monthly_sold,
    amazon_floor,
    chosen_units,
    confidence_score,
    confidence_note,
    bbp_sales_current,
    bbp_sales_recent_avg,
    bbp_sales_history,
    bbp_sales_history_text,
    bbp_dashboard_yes_or_no,
    bbp_sales_chart_source,
    bbp_sales_chart_month_labels,
    bbp_sales_chart_month_units,
    bbp_sales_chart_series,
    bbp_sales_last_completed_month_label,
    bbp_sales_last_completed_month_units,
    bbp_sales_current_month_label,
    bbp_sales_current_month_units,
    bbp_sales_future_month_count_ignored,
    bbp_sales_replay_demand_basis_source,
    bbp_sales_replay_demand_basis_label,
    bbp_sales_replay_demand_basis_units,
    bbp_section_snapshot_path,
    bbp_section_snapshot_nodes,
    bbp_section_snapshot_error,
    seller_evidence,
    lane_history,
    hist_raw_rows,
    phase_snapshot,
    pricing_plan,
    current_auto_price,
    final_sell_price_used,
    avg_30_day_price,
    roi_check_source,
    roi_check_value,
    webscrape_mode,
):
    data = validate_scraped_data(
        {
            "scan_date": datetime.now().strftime("%Y-%m-%d"),
            "main_title": "",
            "monthly_sold": monthly_sold,
            "product_info": "N/A",
            "review_page_status": "pre_review_kill",
            "historical_uk_reviews": "N/A",
        }
    )
    data["amazon_bought_floor"] = "" if amazon_floor is None else str(amazon_floor)
    data["bbp_monthly_sales_current"] = str(_safe_int(bbp_sales_current, 0))
    data["bbp_monthly_sales_recent_avg"] = str(int(round(_safe_float(bbp_sales_recent_avg, 0.0))))
    data["bbp_monthly_sales_history"] = (
        ",".join(str(_safe_int(v, 0)) for v in bbp_sales_history) if bbp_sales_history else bbp_sales_history_text
    )
    data["bbp_monthly_units_chosen"] = str(_safe_int(chosen_units, 0))
    data["bbp_dashboard_yes_or_no"] = bbp_dashboard_yes_or_no
    _apply_dashboard_delivery_fields(data, bbp_dashboard_yes_or_no)
    data["bbp_sales_chart_source"] = bbp_sales_chart_source
    data["bbp_sales_chart_month_labels"] = "|".join(str(v) for v in bbp_sales_chart_month_labels)
    data["bbp_sales_chart_month_units"] = "|".join(str(_safe_int(v, 0)) for v in bbp_sales_chart_month_units)
    data["bbp_sales_chart_series"] = bbp_sales_chart_series
    data["bbp_sales_last_completed_month_label"] = bbp_sales_last_completed_month_label
    data["bbp_sales_last_completed_month_units"] = str(_safe_int(bbp_sales_last_completed_month_units, 0))
    data["bbp_sales_current_month_label"] = bbp_sales_current_month_label
    data["bbp_sales_current_month_units"] = str(_safe_int(bbp_sales_current_month_units, 0))
    data["bbp_sales_future_month_count_ignored"] = str(_safe_int(bbp_sales_future_month_count_ignored, 0))
    data["bbp_sales_replay_demand_basis_source"] = bbp_sales_replay_demand_basis_source
    data["bbp_sales_replay_demand_basis_label"] = bbp_sales_replay_demand_basis_label
    data["bbp_sales_replay_demand_basis_units"] = str(_safe_int(bbp_sales_replay_demand_basis_units, 0))
    data["bbp_section_snapshot_path"] = bbp_section_snapshot_path
    data["bbp_section_snapshot_nodes"] = str(_safe_int(bbp_section_snapshot_nodes, 0))
    data["bbp_section_snapshot_error"] = bbp_section_snapshot_error
    for key, value in (seller_evidence or {}).items():
        data[key] = value
    data["demand_confidence_score"] = str(_safe_int(confidence_score, 0))
    data["demand_confidence_note"] = confidence_note
    data["avg_30_day_price"] = f"{_safe_float(avg_30_day_price, 0.0):.2f}"
    data["price_history_span_days"] = str(_safe_int(phase_snapshot.get("price_history_span_days", 0), 0))
    data["price_history_points_365d"] = str(_safe_int(phase_snapshot.get("price_history_points_365d", 0), 0))
    data["price_hist_table_raw"] = json.dumps(hist_raw_rows, ensure_ascii=True, separators=(",", ":"))
    data["price_hist_windows"] = "30,90,180,365"
    for lane in ("amazon", "fba", "buy_box", "fbm", "new"):
        lane_points = lane_history.get(lane, {}) if isinstance(lane_history.get(lane, {}), dict) else {}
        for win in (30, 90, 180, 365):
            lane_value = _safe_float(lane_points.get(win, 0.0), 0.0)
            data[f"price_hist_{lane}_{win}"] = f"{lane_value:.2f}" if lane_value > 0 else "0"
    data["pricing_mode"] = str(pricing_plan.get("pricing_mode", "live"))
    data["unavailable_detected"] = str(bool(pricing_plan.get("unavailable_detected", False)))
    data["price_history_365d_exists"] = str(bool(pricing_plan.get("price_history_365d_exists", False)))
    data["fallback_lane_used"] = str(pricing_plan.get("fallback_lane_used", ""))
    data["fallback_window_used"] = str(_safe_int(pricing_plan.get("fallback_window_used", 0), 0))
    data["fallback_price"] = str(_safe_float(pricing_plan.get("fallback_price", 0.0), 0.0))
    data["fallback_roi"] = str(_safe_float(pricing_plan.get("fallback_roi", 0.0), 0.0))
    data["fallback_confidence"] = str(pricing_plan.get("fallback_confidence", "LOW"))
    data["fbm_undercut_flag"] = str(bool(pricing_plan.get("fbm_undercut_flag", False)))
    data["pricing_decision_note"] = str(pricing_plan.get("pricing_decision_note", ""))
    data["bbp_auto_sell_price"] = str(_safe_float(current_auto_price, 0.0))
    data["bbp_final_sell_price"] = str(_safe_float(final_sell_price_used, 0.0))
    data["roi_check_source"] = roi_check_source
    data["roi_check_value"] = str(_safe_float(roi_check_value, 0.0))
    data["webscrape_mode"] = webscrape_mode
    data["checks_failed"] = "1"
    data["fail_codes"] = fail_code
    data["hard_stop"] = "True"
    return data


def _economic_pre_review_hard_stop_code(check_fail_codes):
    if os.getenv("F061_ECONOMIC_PRE_REVIEW_HARD_STOP", "1").strip().lower() in {"0", "false", "no", "off"}:
        return ""
    for code in ("LOWROI", "NO_PRICE_HISTORY_365D"):
        if code in check_fail_codes:
            return code
    return ""


def compute_history_score(units_history):
    """
    Turnover-history style score (0-100), with short-term weighted harshest.
    """
    values = [max(_safe_float(v, 0.0), 0.0) for v in (units_history or []) if _safe_float(v, 0.0) > 0]
    if not values:
        return 40, "history_missing"

    recent = values[:3]
    medium = values[3:6]
    long_term = values[6:12]

    recent_avg = _mean(recent) if recent else _mean(values)
    medium_avg = _mean(medium) if medium else recent_avg
    long_avg = _mean(long_term) if long_term else medium_avg

    # Penalties: short-term most harsh, then medium, then long.
    penalty = 0.0
    if medium_avg > 0 and recent_avg < (medium_avg * 0.7):
        penalty += 25.0
    if long_avg > 0 and medium_avg < (long_avg * 0.75):
        penalty += 15.0

    if recent_avg > 0 and len(recent) >= 2:
        rmin = min(recent)
        rmax = max(recent)
        swing = (rmax - rmin) / recent_avg
        if swing > 0.9:
            penalty += 22.0
        elif swing > 0.5:
            penalty += 12.0

    base = 100.0 - penalty
    score = int(round(max(0.0, min(100.0, base))))

    seasonal = "seasonal_candidate" if (long_avg > recent_avg * 1.25 and medium_avg >= recent_avg) else "stable_or_nonseasonal"
    return score, seasonal


def compute_economics_score(monthly_turnover, monthly_profit, profit_per_unit, profit_threshold):
    """
    Economics score focused on monthly profit with turnover + margin support.
    """
    threshold = max(_safe_float(profit_threshold, 20.0), 1.0)
    turnover_target = max(_safe_float(os.getenv("BBP_TURNOVER_TARGET_GBP", "200"), 200.0), 50.0)

    profit_ratio = monthly_profit / threshold
    if profit_ratio <= 0:
        profit_score = 0.0
    elif profit_ratio < 1:
        profit_score = profit_ratio * 40.0
    elif profit_ratio < 3:
        profit_score = 40.0 + ((profit_ratio - 1.0) / 2.0) * 20.0
    else:
        profit_score = 60.0

    turnover_score = min(20.0, (monthly_turnover / turnover_target) * 20.0) if monthly_turnover > 0 else 0.0
    margin_score = min(20.0, max(0.0, (profit_per_unit / 2.0) * 20.0))

    total = int(round(max(0.0, min(100.0, profit_score + turnover_score + margin_score))))
    return total


def build_opportunity_recommendation(monthly_profit, profit_threshold, economics_score, history_score, confidence_score):
    combined = (economics_score * 0.55) + (history_score * 0.30) + (confidence_score * 0.15)
    threshold = max(_safe_float(profit_threshold, 20.0), 1.0)

    if monthly_profit >= threshold and combined >= 65:
        rec = "PASS"
    elif monthly_profit <= (threshold * 0.5) or combined < 45:
        rec = "FAIL"
    else:
        rec = "REVIEW"
    return int(round(max(0.0, min(100.0, combined)))), rec


def _manual_bbp_login_wait_seconds():
    raw = os.getenv(F061_MANUAL_BBP_LOGIN_WAIT_SECONDS_ENV, "").strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            return 0.0
    browser_mode = os.getenv("F061_BACKGROUND_BROWSER_MODE", "").strip().lower()
    show_windows = os.getenv("F061_SHOW_WINDOWS", "").strip().lower()
    if browser_mode == "visible" or show_windows in {"1", "true", "yes", "on"}:
        return 900.0
    return 0.0


def _login_mode_manual_hold_enabled():
    return _env_flag_enabled("F061_LOGIN_MODE") and _manual_bbp_login_wait_seconds() > 0


def _bbp_cost_field_present(driver):
    return bool(driver.find_elements(By.CSS_SELECTOR, "#txtBuyPrice"))


def _refresh_and_recheck_bbp_cost_field(driver):
    try:
        switch_to = getattr(driver, "switch_to", None)
        default_content = getattr(switch_to, "default_content", None)
        if callable(default_content):
            default_content()
    except Exception:
        pass
    try:
        refresh = getattr(driver, "refresh", None)
        if callable(refresh):
            refresh()
        else:
            return False
        _human_sleep(0.75, 1.25, cap=1.5)
    except Exception:
        return False
    try:
        frames = driver.find_elements(By.ID, "bbp-frame")
        if frames:
            driver.switch_to.frame(frames[0])
    except Exception:
        pass
    return _bbp_cost_field_present(driver)


def _bbp_frame_or_container_present(driver):
    try:
        switch_to = getattr(driver, "switch_to", None)
        default_content = getattr(switch_to, "default_content", None)
        if callable(default_content):
            default_content()
    except Exception:
        pass
    try:
        return bool(driver.find_elements(By.ID, "bbp-frame") or driver.find_elements(By.ID, "bbp-container"))
    except Exception:
        return False


def _login_option_evidence(driver):
    selectors = [
        "#loginEmail",
        "#loginPassword",
        "#loginBtn",
    ]
    for selector in selectors:
        try:
            if driver.find_elements(By.CSS_SELECTOR, selector):
                return f"selector:{selector}"
        except Exception:
            continue
    try:
        body_nodes = driver.find_elements(By.TAG_NAME, "body")
        body_text = " ".join(_normalize_text(getattr(node, "text", "")) for node in body_nodes).lower()
    except Exception:
        body_text = ""
    if "buybotpro" in body_text and any(token in body_text for token in ("login", "log in", "sign in")):
        return "body_text:bbp_login_challenge"
    return ""


def _surface_visible_login_browser(driver):
    if _manual_bbp_login_wait_seconds() <= 0:
        return
    try:
        chrome_options = (getattr(driver, "capabilities", {}) or {}).get("goog:chromeOptions", {}) or {}
        debugger_address = str(chrome_options.get("debuggerAddress", "") or "").strip()
        if debugger_address:
            import websocket  # type: ignore

            version_url = f"http://{debugger_address}/json/version"
            with urllib.request.urlopen(version_url, timeout=2) as response:
                version = json.loads(response.read().decode("utf-8", errors="replace"))
            ws = websocket.create_connection(
                version.get("webSocketDebuggerUrl", ""),
                timeout=2,
                suppress_origin=True,
            )
            command_id = 0

            def _cdp(method, params=None, session_id=""):
                nonlocal command_id
                command_id += 1
                payload = {"id": command_id, "method": method, "params": params or {}}
                if session_id:
                    payload["sessionId"] = session_id
                ws.send(json.dumps(payload))
                while True:
                    message = json.loads(ws.recv())
                    if message.get("id") == command_id:
                        return message

            targets = _cdp("Target.getTargets").get("result", {}).get("targetInfos", [])
            pages = [info for info in targets if isinstance(info, dict) and info.get("type") == "page"]
            current_url = _normalize_text(getattr(driver, "current_url", ""))
            selected = pages[0] if pages else {}
            if current_url:
                selected = next((info for info in pages if _normalize_text(info.get("url", "")) == current_url), selected)
            target_id_ws = _normalize_text(selected.get("targetId", "")) if isinstance(selected, dict) else ""
            if target_id_ws:
                window_info = _cdp("Browser.getWindowForTarget", {"targetId": target_id_ws}).get("result", {})
                window_id = window_info.get("windowId")
                if window_id is not None:
                    _cdp(
                        "Browser.setWindowBounds",
                        {
                            "windowId": window_id,
                            "bounds": {
                                "windowState": "normal",
                                "left": 80,
                                "top": 80,
                                "width": 1400,
                                "height": 900,
                            },
                        },
                    )
                _cdp("Target.activateTarget", {"targetId": target_id_ws})
                session = _cdp("Target.attachToTarget", {"targetId": target_id_ws, "flatten": True}).get("result", {}).get("sessionId", "")
                if session:
                    _cdp("Page.bringToFront", {}, session_id=session)
            try:
                ws.close()
            except Exception:
                pass
    except Exception:
        pass
    target_id = ""
    try:
        targets = driver.execute_cdp_cmd("Target.getTargets", {})
        target_infos = targets.get("targetInfos", []) if isinstance(targets, dict) else []
        pages = [info for info in target_infos if isinstance(info, dict) and info.get("type") == "page"]
        current_url = _normalize_text(getattr(driver, "current_url", ""))
        selected = pages[0] if pages else {}
        if current_url:
            selected = next((info for info in pages if _normalize_text(info.get("url", "")) == current_url), selected)
        target_id = _normalize_text(selected.get("targetId", "")) if isinstance(selected, dict) else ""
    except Exception:
        target_id = ""
    try:
        window_info = driver.execute_cdp_cmd(
            "Browser.getWindowForTarget",
            {"targetId": target_id} if target_id else {},
        )
        window_id = window_info.get("windowId") if isinstance(window_info, dict) else None
        if window_id is not None:
            driver.execute_cdp_cmd(
                "Browser.setWindowBounds",
                {
                    "windowId": window_id,
                    "bounds": {
                        "windowState": "normal",
                        "left": 80,
                        "top": 80,
                        "width": 1400,
                        "height": 900,
                    },
                },
            )
    except Exception:
        pass
    try:
        if target_id:
            driver.execute_cdp_cmd("Target.activateTarget", {"targetId": target_id})
    except Exception:
        pass
    try:
        switch_to = getattr(driver, "switch_to", None)
        window = getattr(switch_to, "window", None)
        current_handle = getattr(driver, "current_window_handle", "")
        if callable(window) and current_handle:
            window(current_handle)
    except Exception:
        pass
    try:
        driver.maximize_window()
    except Exception:
        pass
    try:
        driver.set_window_rect(x=80, y=80, width=1400, height=900)
    except Exception:
        pass
    try:
        driver.execute_script("window.focus()")
    except Exception:
        pass
    _surface_bbp_profile_windows_via_powershell()


def _surface_bbp_profile_windows_via_powershell():
    if os.name != "nt":
        return False
    user_data_dir = _normalize_text(os.getenv("F061_BBP_USER_DATA_DIR") or r"C:\Users\Luke\AppData\Local\Chrome_UC136")
    profile_dir = _normalize_text(os.getenv("F061_BBP_PROFILE_DIR") or "BBPProfile")
    if not user_data_dir or not profile_dir:
        return False
    user_data_literal = user_data_dir.replace("'", "''")
    profile_literal = profile_dir.replace("'", "''")
    ps_command = rf'''
$userData = '{user_data_literal}'
$profileDir = '{profile_literal}'
$rootPids = Get-CimInstance Win32_Process |
  Where-Object {{
    $_.Name -eq "chrome.exe" -and
    $_.CommandLine -and
    $_.CommandLine -notmatch " --type=" -and
    $_.CommandLine -like "*$userData*" -and
    $_.CommandLine -like "*--profile-directory=$profileDir*"
  }} |
  Select-Object -ExpandProperty ProcessId
if (-not $rootPids) {{ exit 0 }}
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class F061LoginShowApi {{
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [StructLayout(LayoutKind.Sequential)]
  public struct RECT {{ public int Left; public int Top; public int Right; public int Bottom; }}
  [StructLayout(LayoutKind.Sequential)]
  public struct POINT {{ public int X; public int Y; }}
  [StructLayout(LayoutKind.Sequential)]
  public struct WINDOWPLACEMENT {{
    public int length;
    public int flags;
    public int showCmd;
    public POINT ptMinPosition;
    public POINT ptMaxPosition;
    public RECT rcNormalPosition;
  }}
  [DllImport("user32.dll")]
  public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")]
  public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);
  [DllImport("user32.dll")]
  public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")]
  public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")]
  public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")]
  public static extern bool SetWindowPlacement(IntPtr hWnd, ref WINDOWPLACEMENT lpwndpl);
  [DllImport("user32.dll")]
  public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
  [DllImport("user32.dll")]
  public static extern bool BringWindowToTop(IntPtr hWnd);
  [DllImport("user32.dll")]
  public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll", EntryPoint="GetWindowLongPtr", SetLastError=true)]
  public static extern IntPtr GetWindowLongPtr(IntPtr hWnd, int nIndex);
  [DllImport("user32.dll", EntryPoint="SetWindowLongPtr", SetLastError=true)]
  public static extern IntPtr SetWindowLongPtr(IntPtr hWnd, int nIndex, IntPtr dwNewLong);
}}
"@
$script:rootPids = @($rootPids | ForEach-Object {{ [int]$_ }})
$callback = [F061LoginShowApi+EnumWindowsProc]{{
  param([IntPtr]$hWnd, [IntPtr]$lParam)
  [uint32]$windowProcessId = 0
  [F061LoginShowApi]::GetWindowThreadProcessId($hWnd, [ref]$windowProcessId) | Out-Null
  if ($script:rootPids -contains [int]$windowProcessId) {{
    $titleBuilder = New-Object System.Text.StringBuilder 512
    [F061LoginShowApi]::GetWindowText($hWnd, $titleBuilder, $titleBuilder.Capacity) | Out-Null
    $title = $titleBuilder.ToString()
    if ($title -match "Chromium|Chrome|Amazon|Restore pages") {{
      $style = [F061LoginShowApi]::GetWindowLongPtr($hWnd, -16).ToInt64()
      $newStyle = ($style -bor 0x10000000L) -band (-bnot 0x20000000L)
      [F061LoginShowApi]::SetWindowLongPtr($hWnd, -16, [IntPtr]::new($newStyle)) | Out-Null
      $placement = New-Object F061LoginShowApi+WINDOWPLACEMENT
      $placement.length = [System.Runtime.InteropServices.Marshal]::SizeOf([type][F061LoginShowApi+WINDOWPLACEMENT])
      $placement.flags = 0
      $placement.showCmd = 1
      $placement.ptMinPosition = New-Object F061LoginShowApi+POINT
      $placement.ptMaxPosition = New-Object F061LoginShowApi+POINT
      $placement.rcNormalPosition = New-Object F061LoginShowApi+RECT
      $placement.rcNormalPosition.Left = 20
      $placement.rcNormalPosition.Top = 20
      $placement.rcNormalPosition.Right = 1620
      $placement.rcNormalPosition.Bottom = 970
      [F061LoginShowApi]::SetWindowPlacement($hWnd, [ref]$placement) | Out-Null
      foreach ($cmd in @(9, 1, 5, 3)) {{
        [F061LoginShowApi]::ShowWindow($hWnd, $cmd) | Out-Null
        [F061LoginShowApi]::ShowWindowAsync($hWnd, $cmd) | Out-Null
      }}
      [F061LoginShowApi]::SetWindowPos($hWnd, [IntPtr](-1), 20, 20, 1600, 950, 0x0040 -bor 0x0020) | Out-Null
      Start-Sleep -Milliseconds 100
      [F061LoginShowApi]::BringWindowToTop($hWnd) | Out-Null
      [F061LoginShowApi]::SetForegroundWindow($hWnd) | Out-Null
      [F061LoginShowApi]::SetWindowPos($hWnd, [IntPtr](-2), 20, 20, 1600, 950, 0x0040 -bor 0x0020) | Out-Null
    }}
  }}
  return $true
}}
[F061LoginShowApi]::EnumWindows($callback, [IntPtr]::Zero) | Out-Null
'''
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
        return int(completed.returncode or 0) == 0
    except Exception:
        return False


def _wait_for_visible_bbp_frame_or_container(driver, wait_seconds):
    wait_seconds = max(0.0, float(wait_seconds or 0.0))
    if wait_seconds <= 0:
        return False
    if _bbp_frame_or_container_present(driver) or _bbp_cost_field_present(driver):
        return True
    evidence = _login_option_evidence(driver)
    if not evidence:
        logger.info("BBP iframe missing, but no real login option was detected; keeping scanner browser on normal hidden path.")
        return False
    logger.warning(f"F061_LOGIN_OPTION_DETECTED {evidence}")
    _surface_visible_login_browser(driver)
    logger.warning(
        "BBP login option detected; keeping the scanner-owned browser open for up to "
        f"{wait_seconds:.0f} seconds."
    )
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if _bbp_frame_or_container_present(driver) or _bbp_cost_field_present(driver):
            logger.info("BBP iframe/container became available during manual login hold.")
            return True
        _human_sleep(0.75, 1.25, cap=1.5)
    try:
        driver.refresh()
        logger.info("Refreshed Amazon page once before reporting BBP iframe still missing.")
    except Exception:
        pass
    if _bbp_frame_or_container_present(driver) or _bbp_cost_field_present(driver):
        logger.info("BBP iframe/container became available after final refresh.")
        return True
    logger.warning("BBP iframe/container manual hold timed out; login is still required.")
    return False


def login_to_buybotpro(driver, email, password):
    """
    Logs into BuyBotPro if login fields are present.
    Returns one of: submitted, already_authenticated, not_required, login_required, skipped_error.
    """
    try:
        email_fields = driver.find_elements(By.CSS_SELECTOR, "#loginEmail")
        pass_fields = driver.find_elements(By.CSS_SELECTOR, "#loginPassword")
        login_buttons = driver.find_elements(By.CSS_SELECTOR, "#loginBtn")
        if email_fields and pass_fields and login_buttons:
            manual_wait_seconds = _manual_bbp_login_wait_seconds()
            if manual_wait_seconds > 0:
                logger.warning("F061_LOGIN_OPTION_DETECTED selector:#loginEmail,#loginPassword,#loginBtn")
                _surface_visible_login_browser(driver)
                logger.warning(
                    "BBP manual login required; keeping the scanner-owned browser open for up to "
                    f"{manual_wait_seconds:.0f} seconds."
                )
                deadline = time.monotonic() + manual_wait_seconds
                while time.monotonic() < deadline:
                    if _bbp_cost_field_present(driver):
                        logger.info("BBP manual login completed.")
                        return "already_authenticated"
                    _human_sleep(0.75, 1.25, cap=1.5)
                if _refresh_and_recheck_bbp_cost_field(driver):
                    logger.info("BBP manual login completed after refresh.")
                    return "already_authenticated"
                logger.warning("BBP manual login timed out; login is still required.")
                return "login_required"

            email_f = email_fields[0]
            pass_f = pass_fields[0]
            login_b = login_buttons[0]
            email_f.clear()
            email_f.send_keys(email)
            pass_f.clear()
            pass_f.send_keys(password)
            login_b.click()
            logger.info("Submitted BBP login.")
            try:
                WebDriverWait(driver, _scaled_wait_seconds(5.0, floor=2.0, cap=6.5)).until(
                    lambda d: d.find_elements(By.CSS_SELECTOR, "#txtBuyPrice")
                    or not d.find_elements(By.CSS_SELECTOR, "#loginBtn")
                )
            except Exception:
                _human_sleep(0.6, 1.1, cap=1.6)
            if _bbp_cost_field_present(driver):
                return "submitted"
            if driver.find_elements(By.CSS_SELECTOR, "#loginBtn"):
                logger.warning("BBP login form still present after automatic login attempt.")
                return "login_required"
            return "submitted"

        # No login form. If the BBP cost field exists, the session is already authenticated.
        if _bbp_cost_field_present(driver):
            logger.info("BBP login skipped: already authenticated.")
            return "already_authenticated"

        logger.info("BBP login skipped: login form not present on current panel.")
        return "not_required"
    except Exception as e:
        logger.warning(f"BBP login step skipped due to non-fatal issue => {e}")
        return "skipped_error"


def update_vat_rate(driver, vat_rate):
    """
    Sets VAT on BuyBotPro only when non-standard.
    Standard VAT (20) is treated as default and skipped.
    """
    try:
        vat_val = _safe_float(vat_rate, 20.0)
        if abs(vat_val - 20.0) < 0.01:
            logger.info("VAT is standard 20% => skipping VAT field update.")
            return

        vat_f = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="txtVatRate"]'))
        )
        logger.info(f"Setting non-standard VAT => {vat_val}%")
        vat_f.clear()
        vat_f.send_keys(str(vat_val))  # e.g. "0" or custom rate
        _human_sleep(0.45, 0.90, cap=1.3)  # let BBP recalc
        logger.info(f"Set VAT => {vat_val}% complete.")
    except Exception as e:
        logger.error(f"update_vat_rate => {e}")


def validate_scraped_data(data):
    """
    Ensures the returned dictionary has all required keys.
    Missing keys are set to 'N/A'.
    """
    req = [
        "scan_date",
        "main_title",
        "monthly_sold",
        "rating",
        "product_info",   # Usually release date or product details
        "product_detail_text",
        "product_description",
        "product_feature_bullets",
        "review_page_status",
        "variant_reviews",
        "reviews_text",
        "historical_uk_reviews",
        "amazon_bought_floor",
        "bbp_monthly_sales_current",
        "bbp_monthly_sales_recent_avg",
        "bbp_monthly_sales_history",
        "bbp_monthly_units_chosen",
        "bbp_dashboard_yes_or_no",
        "bbp_dashboard_delivery_classification",
        "bbp_dashboard_separate_delivery_required",
        "bbp_top_seller_names",
        "bbp_top_seller_count",
        "bbp_brand_match_seller",
        "bbp_brand_match_score",
        "bbp_brand_match_flag",
        "bbp_seller_rank_1_name",
        "bbp_seller_rank_1_price",
        "bbp_seller_rank_1_fulfilment",
        "bbp_seller_rank_1_delivery",
        "bbp_seller_rank_1_reviews",
        "bbp_seller_rank_1_feedback_pct",
        "bbp_seller_rank_1_brand_match_flag",
        "bbp_seller_rank_1_row_text",
        "bbp_seller_rank_1_row_html",
        "bbp_seller_rank_2_name",
        "bbp_seller_rank_2_price",
        "bbp_seller_rank_2_fulfilment",
        "bbp_seller_rank_2_delivery",
        "bbp_seller_rank_2_reviews",
        "bbp_seller_rank_2_feedback_pct",
        "bbp_seller_rank_2_brand_match_flag",
        "bbp_seller_rank_2_row_text",
        "bbp_seller_rank_2_row_html",
        "bbp_seller_rank_3_name",
        "bbp_seller_rank_3_price",
        "bbp_seller_rank_3_fulfilment",
        "bbp_seller_rank_3_delivery",
        "bbp_seller_rank_3_reviews",
        "bbp_seller_rank_3_feedback_pct",
        "bbp_seller_rank_3_brand_match_flag",
        "bbp_seller_rank_3_row_text",
        "bbp_seller_rank_3_row_html",
        "amazon_buybox_seller_name",
        "amazon_buybox_brand_match_score",
        "amazon_buybox_brand_match_flag",
        "demand_confidence_score",
        "demand_confidence_note",
        "avg_30_day_price",
        "profit_per_unit_30d",
        "estimated_monthly_turnover",
        "estimated_monthly_profit",
        "turnover_profit_history",
        "turnover_history_months",
        "turnover_current_month_profit",
        "turnover_short_avg_profit",
        "turnover_medium_avg_profit",
        "turnover_long_avg_profit",
        "turnover_history_score",
        "turnover_history_recommendation",
        "turnover_fail_code",
        "turnover_fail_reason",
        "economics_score",
        "history_score",
        "opportunity_score",
        "opportunity_recommendation",
        "history_pattern_note",
        "history_window_days",
        "history_data_points",
        "history_gap_fill_rate",
        "pricing_history_score",
        "ranking_history_score",
        "history_operational_score",
        "phase_profit_pct",
        "phase_low_roi_pct",
        "phase_break_even_pct",
        "phase_loss_pct",
        "phase_longest_profit_days",
        "phase_longest_low_roi_days",
        "phase_longest_break_even_days",
        "phase_longest_loss_days",
        "phase_current",
        "phase_recommendation",
        "exit_strategy",
        "bsr_recent_avg",
        "bsr_prev_avg",
        "bsr_trend",
        "chosen_price_recent_avg",
        "chosen_price_prev_avg",
        "price_trend_pct",
        "history_source",
        "history_recommendation",
        "history_blended_score",
        "price_history_span_days",
        "price_history_points_365d",
        "price_hist_table_raw",
        "chart_price_daily_series",
        "chart_bsr_daily_series",
        "chart_phase_daily_series",
        "chart_raw_amazon_daily_series",
        "chart_raw_fba_daily_series",
        "chart_raw_fbm_daily_series",
        "chart_raw_buy_box_daily_series",
        "chart_raw_bsr_daily_series",
        "price_hist_windows",
        "price_hist_amazon_30",
        "price_hist_amazon_90",
        "price_hist_amazon_180",
        "price_hist_amazon_365",
        "price_hist_fba_30",
        "price_hist_fba_90",
        "price_hist_fba_180",
        "price_hist_fba_365",
        "price_hist_buy_box_30",
        "price_hist_buy_box_90",
        "price_hist_buy_box_180",
        "price_hist_buy_box_365",
        "price_hist_fbm_30",
        "price_hist_fbm_90",
        "price_hist_fbm_180",
        "price_hist_fbm_365",
        "price_hist_new_30",
        "price_hist_new_90",
        "price_hist_new_180",
        "price_hist_new_365",
        "pricing_mode",
        "unavailable_detected",
        "price_history_365d_exists",
        "fallback_lane_used",
        "fallback_window_used",
        "fallback_price",
        "fallback_roi",
        "fallback_confidence",
        "fbm_undercut_flag",
        "pricing_decision_note",
        "bbp_auto_sell_price",
        "bbp_final_sell_price",
        "roi_check_source",
        "roi_check_value",
        "webscrape_mode",
        "checks_failed",
        "fail_codes",
        "hard_stop",
    ]
    return {k: data.get(k, "N/A") for k in req}


def fallback_scrape_date_with_driver(driver, asin):
    """
    Reuse an already-open Chrome 91 driver to scrape the product info section and extract release date.
    """
    try:
        if driver is None:
            logger.error("[Chrome91] No driver provided to fallback_scrape_date_with_driver.")
            return "N/A"

        url = f"https://www.amazon.co.uk/dp/{asin}"
        logger.info(f"[Chrome91] Navigating => {url}")
        driver.get(url)
        _human_sleep(0.45, 0.90, cap=1.4)

        # âœ… Accept cookies if the button is present
        try:
            cookie_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="sp-cc-accept"]'))
            )
            cookie_button.click()
            logger.info("[Chrome91] Accepted cookies popup.")
        except Exception as e:
            logger.info(f"[Chrome91] No cookie accept popup found or not clickable => {e}")

        driver.delete_all_cookies()
        dist = random.randint(100, 500)
        driver.execute_script(f"window.scrollBy(0,{dist})")
        _human_sleep(0.30, 0.75, cap=1.1)

        product_info_text = "N/A"

        # Primary + fallback blocks
        try:
            product_info_element = WebDriverWait(driver, _scaled_wait_seconds(8.0, floor=3.5, cap=9.5)).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="productDetailsWithModules_feature_div"]'))
            )
            product_info_text = product_info_element.text.strip()
            logger.info("[Chrome91] Product info extracted using primary XPath.")
        except Exception:
            logger.info("[Chrome91] Primary details block failed. Trying fallback blocks...")
            fallback_blocks = [
                ("detail bullets", '//*[@id="detailBullets_feature_div"]', _scaled_wait_seconds(4.5, floor=2.0, cap=6.0)),
                ("legacy details", '//*[@id="productDetails_feature_div"]', _scaled_wait_seconds(7.0, floor=3.0, cap=8.5)),
            ]
            for block_name, block_xpath, wait_seconds in fallback_blocks:
                try:
                    product_info_element = WebDriverWait(driver, wait_seconds).until(
                        EC.presence_of_element_located((By.XPATH, block_xpath))
                    )
                    product_info_text = product_info_element.text.strip()
                    logger.info(f"[Chrome91] Product info extracted using {block_name} block.")
                    break
                except Exception:
                    continue
            if product_info_text == "N/A":
                logger.error("[Chrome91] All product info blocks failed.")

        logger.info(f"[Chrome91] Full product info text:\n{product_info_text}")

        extracted = extract_date(product_info_text)
        if not extracted:
            if "Sept." in product_info_text:
                logger.info("[Chrome91] Detected 'Sept.' => attempting fallback parse by replacing 'Sept.' with 'Sep.'")
                replaced_text = product_info_text.replace("Sept.", "Sep.")
                extracted = extract_date(replaced_text)
                if extracted:
                    logger.info(f"[Chrome91] extracted_date after 'Sept.' replacement => {extracted}")

        if extracted:
            logger.info(f"[Chrome91] extracted_date => {extracted}")
            return extracted
        else:
            logger.warning("[Chrome91] No date found in product info text => returning N/A")
            return "N/A"

    except Exception as e:
        logger.error(f"[Chrome91] error => {e}")
        return "N/A"


# ---------------------------------------------------
# 4. MAIN PIPELINE FUNCTION
# ---------------------------------------------------
def process_passed_product(
    asin,
    break_even_price,
    min_sell_price,
    product_cost,
    row_index,
    brand_name,
    vat_rate,
    skip_date_scraping=False,
    old_chrome_forced=False,
    bbp_driver=None,
    date_driver=None,
    fba_fee=None,
    referral_fee=None,
    digital_fee=None,
    est_shipping=None,
    referral_fee_basis_price=None,
):
    """
    Main pipeline for scraping.
    Launches modern Chrome by default, optionally uses fallback Chrome 91,
    sets cost and VAT in BuyBotPro, then calculates a realistic Sell Price
    from historical data to override the BBP auto-filled price if needed.
    """
    if old_chrome_forced and not skip_date_scraping:
        logger.info("User requested old Chrome approach (score >= 2.5).")
        use_old_for_date = True
    else:
        use_old_for_date = False

    options = uc.ChromeOptions()
    options.binary_location = r"C:\Chrome_UC136\bin\chrome.exe"
    options.add_argument(r"--user-data-dir=C:\Users\Luke\AppData\Local\Chrome_UC136")
    options.add_argument(r"--profile-directory=BBPProfile")
    options.add_argument("--flag-switches-begin")
    options.add_argument("--flag-switches-end")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-infobars")
    options.add_argument("--remote-debugging-port=9222")
    if not _env_flag("F061_SHOW_WINDOWS", False):
        options.add_argument("--window-size=1280,720")
        options.add_argument("--window-position=-32000,-32000")
        options.add_argument("--start-minimized")

    try:
        monthly_profit_threshold = _safe_float(os.getenv("BBP_MONTHLY_PROFIT_THRESHOLD_GBP", "20"), 20.0)
        amazon_cap_multiplier = _safe_float(os.getenv("BBP_AMAZON_CAP_MULTIPLIER", "1.5"), 1.5)
        webscrape_mode = (os.getenv("F061_WEBSCRAPE_MODE", "decision") or "decision").strip().lower()
        data_mode = webscrape_mode == "data"
        check_fail_codes = []

        def _record_business_fail(code, note):
            if code not in check_fail_codes:
                check_fail_codes.append(code)
            logger.warning(f"[Profile5][data_mode] business fail captured => {code}: {note}")

        bbp_sales_current = 0
        bbp_sales_history = []
        bbp_sales_recent_avg = 0.0
        bbp_sales_history_text = ""
        bbp_sales_chart_source = ""
        bbp_dashboard_yes_or_no = ""
        bbp_sales_chart_month_labels = []
        bbp_sales_chart_month_units = []
        bbp_sales_chart_series = ""
        bbp_sales_last_completed_month_label = ""
        bbp_sales_last_completed_month_units = 0
        bbp_sales_current_month_label = ""
        bbp_sales_current_month_units = 0
        bbp_sales_future_month_count_ignored = 0
        bbp_sales_replay_demand_basis_source = "missing"
        bbp_sales_replay_demand_basis_label = ""
        bbp_sales_replay_demand_basis_units = 0
        bbp_section_snapshot_path = ""
        bbp_section_snapshot_nodes = 0
        bbp_section_snapshot_error = ""
        seller_evidence = _seller_evidence_fields(brand_name, [])
        avg_30_day_price = 0.0
        final_sell_price_used = 0.0
        smart_price = 0.0
        phase_snapshot = {}
        lane_history = {"amazon": {}, "fba": {}, "fbm": {}, "buy_box": {}, "new": {}}
        pricing_plan = {
            "pricing_mode": "live",
            "unavailable_detected": False,
            "price_history_365d_exists": False,
            "fallback_lane_used": "",
            "fallback_window_used": 0,
            "fallback_price": 0.0,
            "fallback_roi": 0.0,
            "fallback_confidence": "LOW",
            "fbm_undercut_flag": False,
            "pricing_decision_note": "live_price_mode",
        }
        roi_check_source = "bbp_live"
        roi_check_value = 0.0
        current_auto_price = 0.0
        turnover_profit_history = []
        turnover_eval = {
            "history_months": 0,
            "current_month_profit": 0.0,
            "short_avg_profit": 0.0,
            "medium_avg_profit": 0.0,
            "long_avg_profit": 0.0,
            "score": 0,
            "recommendation": "REVIEW",
            "fail_code": "",
            "fail_reason": "",
        }

        if not bbp_driver:
            logger.error("No bbp_driver passed to process_passed_product.")
            return {"success": False, "scraped_data": {}, "error": "No BBP driver provided"}

        driver = bbp_driver
        logger.info("[BBP] Using existing BBP Chrome driver passed from firstCheck.py")

        url = f"https://www.amazon.co.uk/dp/{asin}"
        logger.info(f"[Profile5] Going => {url}")
        driver.get(url)
        _human_sleep(0.85, 1.45, cap=1.9)
        driver.refresh()
        _human_sleep(0.85, 1.45, cap=1.9)

        preflight_detected = False
        preflight_error = None
        for attempt in range(1, 4):
            try:
                WebDriverWait(driver, _scaled_wait_seconds(2.2, floor=1.0, cap=3.0)).until(
                    lambda d: d.find_elements(By.ID, "bbp-frame") or d.find_elements(By.ID, "bbp-container")
                )
                preflight_detected = True
                logger.info(f"[Profile5] BBP iframe/container detected after refresh (attempt {attempt}/3).")
                break
            except Exception as e:
                preflight_error = e
                if attempt < 3:
                    logger.info(f"[Profile5] BBP iframe preflight retry {attempt}/3.")
                    _human_sleep(0.25, 0.55, cap=0.85)
                else:
                    logger.warning(f"[Profile5] BBP iframe preflight failed after refresh => {preflight_error}")

        if not preflight_detected:
            manual_wait_seconds = _manual_bbp_login_wait_seconds()
            if manual_wait_seconds > 0:
                preflight_detected = _wait_for_visible_bbp_frame_or_container(driver, manual_wait_seconds)
                if not preflight_detected:
                    return {"success": False, "scraped_data": {}, "error": "BBP_LOGIN_REQUIRED"}

        handle_overlays(driver)
        for _ in range(2):
            dist = random.randint(100, 500)
            driver.execute_script(f"window.scrollBy(0,{dist})")
            _human_sleep(0.18, 0.45, cap=0.85)

        try:
            iframe = WebDriverWait(driver, _scaled_wait_seconds(9.0, floor=4.0, cap=10.0)).until(
                EC.presence_of_element_located((By.ID, "bbp-frame"))
            )
            driver.switch_to.frame(iframe)
            logger.info("[Profile5] Found BBP iframe.")

            login_status = login_to_buybotpro(driver, "dan@drjhardware.co.uk", "Systembox-60811963")
            if login_status == "login_required":
                return {"success": False, "scraped_data": {}, "error": "BBP_LOGIN_REQUIRED"}
            _human_sleep(0.55, 1.05, cap=1.5)

            try:
                cost_f = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#txtBuyPrice"))
                )
                cost_text = _set_bbp_money_input(driver, cost_f, product_cost, field_name="cost")
                logger.info(f"[Profile5] cost => {cost_text}")

                _human_sleep(0.55, 1.05, cap=1.5)
                update_vat_rate(driver, vat_rate)
                _human_sleep(0.40, 0.85, cap=1.2)

                bbp_sales_snapshot = extract_bbp_monthly_sales_snapshot(driver)
                bbp_sales_current = max(_safe_int(bbp_sales_snapshot.get("current_units", 0), 0), 0)
                bbp_sales_history = bbp_sales_snapshot.get("history_values", []) or []
                bbp_sales_history_text = bbp_sales_snapshot.get("history_text", "") or ""
                bbp_sales_chart_source = str(bbp_sales_snapshot.get("chart_source", "") or "")
                bbp_sales_chart_month_labels = bbp_sales_snapshot.get("chart_month_labels", []) or []
                bbp_sales_chart_month_units = bbp_sales_snapshot.get("chart_month_units", []) or []
                bbp_sales_chart_series = str(bbp_sales_snapshot.get("chart_series", "") or "")
                bbp_sales_last_completed_month_label = str(
                    bbp_sales_snapshot.get("last_completed_month_label", "") or ""
                )
                bbp_sales_last_completed_month_units = max(
                    _safe_int(bbp_sales_snapshot.get("last_completed_month_units", 0), 0),
                    0,
                )
                bbp_sales_current_month_label = str(bbp_sales_snapshot.get("current_month_label", "") or "")
                bbp_sales_current_month_units = max(_safe_int(bbp_sales_snapshot.get("current_month_units", 0), 0), 0)
                bbp_sales_future_month_count_ignored = max(
                    _safe_int(bbp_sales_snapshot.get("future_month_count_ignored", 0), 0),
                    0,
                )
                bbp_sales_replay_demand_basis_source = str(
                    bbp_sales_snapshot.get("replay_demand_basis_source", "missing") or "missing"
                )
                bbp_sales_replay_demand_basis_label = str(
                    bbp_sales_snapshot.get("replay_demand_basis_label", "") or ""
                )
                bbp_sales_replay_demand_basis_units = max(
                    _safe_int(bbp_sales_snapshot.get("replay_demand_basis_units", 0), 0),
                    0,
                )
                bbp_sales_recent_avg = _mean(bbp_sales_history[:3]) if bbp_sales_history else float(bbp_sales_current)
                logger.info(
                    f"[Profile5] BBP sales snapshot => current={bbp_sales_current}, "
                    f"recent_avg={bbp_sales_recent_avg:.2f}, points={len(bbp_sales_history)}"
                )

                try:
                    dashboard_yes_or_no_el = driver.find_element(By.CSS_SELECTOR, "#dashboardYesOrNo")
                    dashboard_yes_or_no_raw = (
                        dashboard_yes_or_no_el.text or dashboard_yes_or_no_el.get_attribute("value") or ""
                    ).strip().upper()
                    if has_required_dashboard_signal(dashboard_yes_or_no_raw):
                        bbp_dashboard_yes_or_no = dashboard_yes_or_no_raw
                        delivery_classification = dashboard_delivery_classification(bbp_dashboard_yes_or_no)
                        delivery_note = (
                            f"; delivery_classification={delivery_classification}"
                            if delivery_classification
                            else ""
                        )
                        logger.info(f"[Profile5] Dashboard yes/no => {bbp_dashboard_yes_or_no}{delivery_note}")
                    elif dashboard_yes_or_no_raw == "LOGIN" and _bbp_cost_field_present(driver):
                        bbp_dashboard_yes_or_no = ""
                        logger.info(
                            "[Profile5] Dashboard yes/no raw LOGIN ignored after authenticated cost field; "
                            "treating dashboard as missing."
                        )
                    else:
                        bbp_dashboard_yes_or_no = ""
                        logger.info(
                            f"[Profile5] Dashboard yes/no ignored non yes/no/likely value => "
                            f"{dashboard_yes_or_no_raw or 'missing'}"
                        )
                        if dashboard_yes_or_no_raw == "LOGIN":
                            return {"success": False, "scraped_data": {}, "error": "BBP_LOGIN_REQUIRED"}
                except Exception as e:
                    bbp_dashboard_yes_or_no = ""
                    logger.info(f"[Profile5] Dashboard yes/no missing => {type(e).__name__}")

                hist_table = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#asinAverageStatisticsDataTable"))
                )
                hist_extract = _extract_lane_history_from_table(hist_table)
                lane_history = hist_extract.get("lanes", lane_history)
                hist_raw_rows = hist_extract.get("raw_rows", {})

                logger.info("[Profile5] Price hist =>")
                for k, v in hist_raw_rows.items():
                    logger.info(f"{k}: {v}")

                phase_history_max_days = _safe_int(os.getenv("BBP_CHART_HISTORY_MAX_DAYS", "0"), 0)
                phase_snapshot = extract_bbp_price_phase_snapshot(
                    driver=driver,
                    break_even_price=break_even_price,
                    max_days=phase_history_max_days if phase_history_max_days > 0 else None
                )
                logger.info(
                    "[Profile5] Phase history => "
                    f"src={phase_snapshot.get('history_source', '')}, "
                    f"window={phase_snapshot.get('history_window_days', 0)}d, "
                    f"pts={phase_snapshot.get('history_data_points', 0)}, "
                    f"phase={phase_snapshot.get('phase_recommendation', 'UNKNOWN')}, "
                    f"exit={phase_snapshot.get('exit_strategy', 'REVIEW')}"
                )

                section_snapshot = capture_bbp_section_snapshot(
                    driver,
                    asin=asin,
                    row_index=row_index,
                    context={
                        "chart_source": bbp_sales_chart_source,
                        "last_completed_month": bbp_sales_last_completed_month_label,
                        "replay_demand_basis_source": bbp_sales_replay_demand_basis_source,
                    },
                )
                bbp_section_snapshot_path = str(section_snapshot.get("file_path", "") or "")
                bbp_section_snapshot_nodes = _safe_int(section_snapshot.get("node_count", 0), 0)
                bbp_section_snapshot_error = str(section_snapshot.get("error", "") or "")
                if bbp_section_snapshot_path:
                    logger.info(
                        f"[Profile5] BBP section snapshot => path={bbp_section_snapshot_path}, "
                        f"nodes={bbp_section_snapshot_nodes}"
                    )
                elif bbp_section_snapshot_error:
                    logger.warning(f"[Profile5] BBP section snapshot error => {bbp_section_snapshot_error}")

                try:
                    prime_check = WebDriverWait(driver, _scaled_wait_seconds(8.0, floor=3.0, cap=9.0)).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "#primeOnly"))
                    )
                    if not prime_check.is_selected():
                        ActionChains(driver).move_to_element(prime_check).click().perform()
                        _human_sleep(0.40, 0.85, cap=1.2)
                        logger.info("Filtered prime only.")
                except Exception as e:
                    logger.info(f"Error prime check => {e}")

                try:
                    WebDriverWait(driver, _scaled_wait_seconds(3.5, floor=1.4, cap=4.5)).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "#competitionAnalysisDataTable")
                        )
                    )
                except Exception:
                    pass

                competition_seller_rows = _extract_bbp_competition_seller_rows(driver, max_rows=3)
                sellers = [row.get("name", "") for row in competition_seller_rows if row.get("name", "")]
                if not sellers:
                    sellers = _extract_bbp_top_seller_names(driver, max_sellers=3)
                for i, sn in enumerate(sellers, start=1):
                    logger.info(f"Seller {i} => {sn}")

                seller_evidence = _seller_evidence_fields(brand_name, sellers, competition_rows=competition_seller_rows)
                logger.info(
                    "[Profile5] seller evidence => "
                    f"names={seller_evidence.get('bbp_top_seller_names', '') or 'missing'}, "
                    f"brand_match={seller_evidence.get('bbp_brand_match_seller', '') or 'none'}, "
                    f"score={seller_evidence.get('bbp_brand_match_score', '0')}"
                )

                for s in sellers:
                    if is_similar(brand_name, s):
                        if data_mode:
                            _record_business_fail("BRANDFAIL", f"Seller {s} ~ brand")
                        else:
                            logger.info(f"Seller {s} ~ brand => fail.")
                            return {"success": False, "scraped_data": {}, "error": "Seller ~ brand"}

                logger.info("[Profile5] brand check done => now set final Sell Price if needed.")

                try:
                    auto_fill_el = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="calculatorSellPrice"]'))
                    )
                    value = auto_fill_el.get_attribute("value")
                    current_auto_price_str = value.strip() if value is not None else ""
                    current_auto_price = _safe_float(current_auto_price_str, 999999.0)
                except Exception as e:
                    logger.warning(f"Could not read auto-filled Sell Price => {e}")
                    current_auto_price = 999999.0

                pricing_plan = _choose_unavailable_pricing_plan(
                    lane_history=lane_history,
                    current_auto_price=current_auto_price,
                    break_even_price=break_even_price,
                    history_has_365_override=phase_snapshot.get("price_history_365d_exists", None),
                )
                smart_price = _safe_float(pricing_plan.get("fallback_price", 0.0), 0.0)

                amazon_30 = _safe_float((lane_history.get("amazon", {}) or {}).get(30, 0.0), 0.0)
                fba_30 = _safe_float((lane_history.get("fba", {}) or {}).get(30, 0.0), 0.0)
                buy_box_30 = _safe_float((lane_history.get("buy_box", {}) or {}).get(30, 0.0), 0.0)
                day_30_candidates = [p for p in (amazon_30, fba_30, buy_box_30) if p > 0]
                avg_30_day_price = min(day_30_candidates) if day_30_candidates else 0.0
                logger.info(
                    "[Profile5] pricing decision seed => "
                    f"auto={current_auto_price:.2f}, "
                    f"smart={smart_price:.2f}, "
                    f"avg30={avg_30_day_price:.2f}, "
                    f"mode={pricing_plan.get('pricing_mode')}, "
                    f"note={pricing_plan.get('pricing_decision_note')}"
                )

                if pricing_plan.get("unavailable_detected") and not pricing_plan.get("price_history_365d_exists"):
                    if data_mode:
                        _record_business_fail("NO_PRICE_HISTORY_365D", "Unavailable detected with no 365-day price history.")
                    else:
                        logger.info("Unavailable detected and no 365-day price history => fail.")
                        return {"success": False, "scraped_data": {}, "error": "NO_PRICE_HISTORY_365D"}

                if pricing_plan.get("pricing_mode") == "fallback_history" and smart_price > 0:
                    final_price = smart_price
                    logger.info(
                        "[Profile5] Using history fallback pricing => "
                        f"lane={pricing_plan.get('fallback_lane_used')}, "
                        f"window={pricing_plan.get('fallback_window_used')}d, "
                        f"price={final_price:.2f}, confidence={pricing_plan.get('fallback_confidence')}"
                    )
                elif smart_price > 0:
                    final_price = min(smart_price, current_auto_price)
                    if final_price < current_auto_price:
                        logger.info(f"Overriding Sell Price => from {current_auto_price} down to {final_price}")
                    else:
                        logger.info("Keeping BBP auto-filled price.")
                else:
                    logger.info("No valid historical price => no override. (BBP price stands)")
                    final_price = current_auto_price if current_auto_price < 999999 else 0.0

                if final_price > 0 and abs(final_price - current_auto_price) > 0.009:
                    try:
                        _set_bbp_money_input(driver, auto_fill_el, final_price, field_name="sell price")
                        _human_sleep(0.50, 0.95, cap=1.4)
                    except Exception as e:
                        logger.warning(f"Could not override Sell Price => {e}")

                final_sell_price_used = _safe_float(final_price, 0.0)

                def _read_roi_value():
                    locators = [
                        (By.CSS_SELECTOR, "#quickInfoRoi"),
                        (By.XPATH, '//*[@id="detailsRoi"]'),
                    ]
                    for by, loc in locators:
                        try:
                            roi_el = WebDriverWait(driver, _scaled_wait_seconds(4.0, floor=1.5, cap=5.0)).until(
                                EC.presence_of_element_located((by, loc))
                            )
                            roi_text = roi_el.text.strip().replace("%", "").strip()
                            if roi_text:
                                return roi_text
                        except Exception:
                            continue
                    return ""

                roi_text = ""
                for _ in range(3):
                    roi_text = _read_roi_value()
                    if roi_text:
                        break
                    _human_sleep(0.18, 0.40, cap=0.70)

                roi_val = None
                if pricing_plan.get("pricing_mode") == "fallback_history" and _safe_float(pricing_plan.get("fallback_roi", 0.0), 0.0) != 0.0:
                    roi_check_source = "fallback_history"
                    roi_val = _safe_float(pricing_plan.get("fallback_roi", 0.0), 0.0)
                    logger.info(f"ROI (fallback history) => {roi_val:.2f}%")
                elif roi_text:
                    roi_check_source = "bbp_live"
                    roi_val = _safe_float(roi_text, 0.0)
                    logger.info(f"ROI (bbp live) => {roi_val:.2f}%")
                else:
                    logger.warning("Could not read ROI after final price (empty). Skipping ROI check.")

                if roi_val is not None:
                    roi_check_value = roi_val
                    if roi_val < 20:
                        if data_mode:
                            _record_business_fail("LOWROI", f"ROI {roi_val:.2f}% < 20 (source={roi_check_source})")
                        else:
                            logger.info(f"ROI < 20 => fail. source={roi_check_source}")
                            return {"success": False, "scraped_data": {}, "error": "ROI < 20%"}

                logger.info("[Profile5] done brand+ROI => now pre-review kill gate.")

            except Exception as e:
                logger.error(f"BuyBotPro checks => {e}")
                return {"success": False, "scraped_data": {}, "error": "BuyBotPro error"}

        except Exception as e:
            logger.error(f"No BBP iframe => {e}")
            return {"success": False, "scraped_data": {}, "error": "No BBP iframe"}

        driver.switch_to.default_content()
        amazon_buybox_seller = _extract_amazon_buybox_seller_name(driver)
        seller_evidence.update(_amazon_buybox_seller_evidence_fields(brand_name, amazon_buybox_seller))
        if amazon_buybox_seller:
            logger.info(
                "[Profile5] amazon buybox seller evidence => "
                f"seller={amazon_buybox_seller}, "
                f"brand_match={seller_evidence.get('amazon_buybox_brand_match_flag', 'False')}, "
                f"score={seller_evidence.get('amazon_buybox_brand_match_score', '0')}"
            )
        pre_review_gate_enabled = os.getenv("F061_PRE_REVIEW_KILL_GATE", "1").strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }
        if pre_review_gate_enabled:
            pre_review_monthly_sold = _extract_amazon_monthly_sold_signal(driver)
            pre_review_amazon_floor = parse_amazon_monthly_bought_floor(pre_review_monthly_sold)
            pre_review_bbp_units_reference = (
                _safe_int(round(bbp_sales_recent_avg), 0) if bbp_sales_recent_avg > 0 else bbp_sales_current
            )
            pre_review_chosen_units, pre_review_confidence_score, pre_review_confidence_note = (
                choose_units_with_amazon_guardrail(
                    amazon_floor=pre_review_amazon_floor,
                    bbp_units=pre_review_bbp_units_reference,
                    cap_multiplier=amazon_cap_multiplier,
                )
            )
            new_seller_counts = [
                (lane_history.get("new", {}) or {}).get(30, 0.0),
                (lane_history.get("new", {}) or {}).get(90, 0.0),
                (lane_history.get("new", {}) or {}).get(180, 0.0),
            ]
            pre_review_fail_code = _pre_review_kill_code(
                chosen_units=pre_review_chosen_units,
                dashboard_yes_or_no=bbp_dashboard_yes_or_no,
                new_seller_counts=new_seller_counts,
            )
            if pre_review_fail_code:
                logger.info(
                    "[Profile5] pre-review kill gate => "
                    f"{pre_review_fail_code}; units={pre_review_chosen_units}; "
                    f"amazon='{pre_review_monthly_sold or 'missing'}'; "
                    f"dashboard={bbp_dashboard_yes_or_no or 'missing'}; sellers={new_seller_counts}"
                )
                validated_pre_review = _build_pre_review_fail_payload(
                    fail_code=pre_review_fail_code,
                    monthly_sold=pre_review_monthly_sold,
                    amazon_floor=pre_review_amazon_floor,
                    chosen_units=pre_review_chosen_units,
                    confidence_score=pre_review_confidence_score,
                    confidence_note=pre_review_confidence_note,
                    bbp_sales_current=bbp_sales_current,
                    bbp_sales_recent_avg=bbp_sales_recent_avg,
                    bbp_sales_history=bbp_sales_history,
                    bbp_sales_history_text=bbp_sales_history_text,
                    bbp_dashboard_yes_or_no=bbp_dashboard_yes_or_no,
                    bbp_sales_chart_source=bbp_sales_chart_source,
                    bbp_sales_chart_month_labels=bbp_sales_chart_month_labels,
                    bbp_sales_chart_month_units=bbp_sales_chart_month_units,
                    bbp_sales_chart_series=bbp_sales_chart_series,
                    bbp_sales_last_completed_month_label=bbp_sales_last_completed_month_label,
                    bbp_sales_last_completed_month_units=bbp_sales_last_completed_month_units,
                    bbp_sales_current_month_label=bbp_sales_current_month_label,
                    bbp_sales_current_month_units=bbp_sales_current_month_units,
                    bbp_sales_future_month_count_ignored=bbp_sales_future_month_count_ignored,
                    bbp_sales_replay_demand_basis_source=bbp_sales_replay_demand_basis_source,
                    bbp_sales_replay_demand_basis_label=bbp_sales_replay_demand_basis_label,
                    bbp_sales_replay_demand_basis_units=bbp_sales_replay_demand_basis_units,
                    bbp_section_snapshot_path=bbp_section_snapshot_path,
                    bbp_section_snapshot_nodes=bbp_section_snapshot_nodes,
                    bbp_section_snapshot_error=bbp_section_snapshot_error,
                    seller_evidence=seller_evidence,
                    lane_history=lane_history,
                    hist_raw_rows=hist_raw_rows,
                    phase_snapshot=phase_snapshot,
                    pricing_plan=pricing_plan,
                    current_auto_price=current_auto_price,
                    final_sell_price_used=final_sell_price_used,
                    avg_30_day_price=avg_30_day_price,
                    roi_check_source=roi_check_source,
                    roi_check_value=roi_check_value,
                    webscrape_mode=webscrape_mode,
                )
                return {"success": False, "scraped_data": validated_pre_review, "error": pre_review_fail_code}

            economic_hard_stop_code = _economic_pre_review_hard_stop_code(check_fail_codes)
            if economic_hard_stop_code:
                logger.info(
                    "[Profile5] economic pre-review hard stop => "
                    f"{economic_hard_stop_code}; checks={check_fail_codes}; units={pre_review_chosen_units}; "
                    f"amazon='{pre_review_monthly_sold or 'missing'}'; "
                    f"dashboard={bbp_dashboard_yes_or_no or 'missing'}; sellers={new_seller_counts}"
                )
                validated_economic = _build_pre_review_fail_payload(
                    fail_code=economic_hard_stop_code,
                    monthly_sold=pre_review_monthly_sold,
                    amazon_floor=pre_review_amazon_floor,
                    chosen_units=pre_review_chosen_units,
                    confidence_score=pre_review_confidence_score,
                    confidence_note=pre_review_confidence_note,
                    bbp_sales_current=bbp_sales_current,
                    bbp_sales_recent_avg=bbp_sales_recent_avg,
                    bbp_sales_history=bbp_sales_history,
                    bbp_sales_history_text=bbp_sales_history_text,
                    bbp_dashboard_yes_or_no=bbp_dashboard_yes_or_no,
                    bbp_sales_chart_source=bbp_sales_chart_source,
                    bbp_sales_chart_month_labels=bbp_sales_chart_month_labels,
                    bbp_sales_chart_month_units=bbp_sales_chart_month_units,
                    bbp_sales_chart_series=bbp_sales_chart_series,
                    bbp_sales_last_completed_month_label=bbp_sales_last_completed_month_label,
                    bbp_sales_last_completed_month_units=bbp_sales_last_completed_month_units,
                    bbp_sales_current_month_label=bbp_sales_current_month_label,
                    bbp_sales_current_month_units=bbp_sales_current_month_units,
                    bbp_sales_future_month_count_ignored=bbp_sales_future_month_count_ignored,
                    bbp_sales_replay_demand_basis_source=bbp_sales_replay_demand_basis_source,
                    bbp_sales_replay_demand_basis_label=bbp_sales_replay_demand_basis_label,
                    bbp_sales_replay_demand_basis_units=bbp_sales_replay_demand_basis_units,
                    bbp_section_snapshot_path=bbp_section_snapshot_path,
                    bbp_section_snapshot_nodes=bbp_section_snapshot_nodes,
                    bbp_section_snapshot_error=bbp_section_snapshot_error,
                    seller_evidence=seller_evidence,
                    lane_history=lane_history,
                    hist_raw_rows=hist_raw_rows,
                    phase_snapshot=phase_snapshot,
                    pricing_plan=pricing_plan,
                    current_auto_price=current_auto_price,
                    final_sell_price_used=final_sell_price_used,
                    avg_30_day_price=avg_30_day_price,
                    roi_check_source=roi_check_source,
                    roi_check_value=roi_check_value,
                    webscrape_mode=webscrape_mode,
                )
                return {"success": False, "scraped_data": validated_economic, "error": economic_hard_stop_code}

        logger.info("[Profile5] pre-review kill gate passed => now main page scraping.")

        if skip_date_scraping:
            logger.info("Skipping date scraping, still reading main page metrics.")
            temp_data = scrape_main_page(driver)
            temp_data["product_info"] = "N/A"
            data = temp_data
        else:
            logger.info("Normal date scraping with new Chrome.")
            data = scrape_main_page(driver)

        review_page_status = _normalize_lower(data.get("review_page_status", ""))
        if review_page_status in {"timeout", "blocked", "link_missing", "href_missing"}:
            logger.warning(f"Review page capture incomplete ({review_page_status}) => technical rescan.")
            validated_timeout = validate_scraped_data(data)
            for key, value in seller_evidence.items():
                validated_timeout[key] = value
            # Preserve BBP evidence that was already scraped before the Amazon review page failed.
            validated_timeout["bbp_dashboard_yes_or_no"] = bbp_dashboard_yes_or_no
            _apply_dashboard_delivery_fields(validated_timeout, bbp_dashboard_yes_or_no)
            validated_timeout["bbp_sales_chart_source"] = bbp_sales_chart_source
            validated_timeout["bbp_sales_chart_month_labels"] = "|".join(str(v) for v in bbp_sales_chart_month_labels)
            validated_timeout["bbp_sales_chart_month_units"] = "|".join(
                str(_safe_int(v, 0)) for v in bbp_sales_chart_month_units
            )
            validated_timeout["bbp_sales_chart_series"] = bbp_sales_chart_series
            validated_timeout["bbp_monthly_sales_current"] = str(bbp_sales_current)
            validated_timeout["bbp_monthly_sales_recent_avg"] = (
                str(int(round(bbp_sales_recent_avg))) if bbp_sales_recent_avg > 0 else "0"
            )
            validated_timeout["bbp_monthly_sales_history"] = (
                ",".join(str(_safe_int(v, 0)) for v in bbp_sales_history) if bbp_sales_history else ""
            )
            validated_timeout["bbp_sales_last_completed_month_label"] = bbp_sales_last_completed_month_label
            validated_timeout["bbp_sales_last_completed_month_units"] = str(bbp_sales_last_completed_month_units)
            validated_timeout["price_hist_windows"] = "30,90,180,365"
            for lane in ("amazon", "fba", "buy_box", "fbm", "new"):
                lane_points = lane_history.get(lane, {}) if isinstance(lane_history.get(lane, {}), dict) else {}
                for win in (30, 90, 180, 365):
                    lane_value = _safe_float(lane_points.get(win, 0.0), 0.0)
                    validated_timeout[f"price_hist_{lane}_{win}"] = f"{lane_value:.2f}" if lane_value > 0 else "0"
            validated_timeout["history_source"] = str(phase_snapshot.get("history_source", ""))
            validated_timeout["pricing_mode"] = str(pricing_plan.get("pricing_mode", "live"))
            validated_timeout["pricing_decision_note"] = str(pricing_plan.get("pricing_decision_note", ""))
            validated_timeout["bbp_auto_sell_price"] = str(current_auto_price)
            validated_timeout["bbp_final_sell_price"] = str(_safe_float(final_sell_price_used, 0.0))
            validated_timeout["roi_check_source"] = roi_check_source
            validated_timeout["roi_check_value"] = str(_safe_float(roi_check_value, 0.0))
            validated_timeout["webscrape_mode"] = webscrape_mode
            return {"success": False, "scraped_data": validated_timeout, "error": "REVIEWS_TIMEOUT"}

        validated = validate_scraped_data(data)
        for key, value in seller_evidence.items():
            validated[key] = value
        validated["updated_break_even"] = 0
        found_date = validated.get("product_info", "N/A")

        amazon_bought_text = validated.get("monthly_sold", "")
        amazon_floor = parse_amazon_monthly_bought_floor(amazon_bought_text)
        bbp_units_reference = _safe_int(round(bbp_sales_recent_avg), 0) if bbp_sales_recent_avg > 0 else bbp_sales_current
        chosen_units, confidence_score, confidence_note = choose_units_with_amazon_guardrail(
            amazon_floor=amazon_floor,
            bbp_units=bbp_units_reference,
            cap_multiplier=amazon_cap_multiplier,
        )

        if avg_30_day_price <= 0:
            avg_30_day_price = final_sell_price_used if final_sell_price_used > 0 else smart_price

        fee_profit = calculate_fee_based_profit_per_unit(
            sale_price_gbp=avg_30_day_price,
            vat_rate_pct=vat_rate,
            product_cost_gbp=product_cost,
            fba_fee_gbp=fba_fee,
            referral_fee_gbp=referral_fee,
            digital_fee_gbp=digital_fee,
            est_shipping_gbp=est_shipping,
            referral_fee_basis_price_gbp=referral_fee_basis_price,
            recalculate_referral_fee=True,
            recalculate_digital_fee=True,
        )
        if fee_profit.profit_per_unit_gbp is None:
            logger.warning(
                "Fee-based profit inputs missing; setting profit_per_unit_30d to 0. "
                f"missing={','.join(fee_profit.missing_inputs)}"
            )
            profit_per_unit_30d = 0.0
        else:
            profit_per_unit_30d = round(float(fee_profit.profit_per_unit_gbp), 2)
        est_monthly_turnover = max(0.0, chosen_units * avg_30_day_price)
        est_monthly_profit = float(chosen_units) * float(profit_per_unit_30d)

        turnover_profit_history = build_turnover_profit_history(
            bbp_sales_history=bbp_sales_history,
            bbp_units_reference=bbp_units_reference,
            chosen_units=chosen_units,
            profit_per_unit=profit_per_unit_30d,
            max_months=12,
        )
        turnover_eval = evaluate_turnover_gate(
            monthly_profit_history=turnover_profit_history,
            monthly_profit_threshold=monthly_profit_threshold,
            current_multiplier=_safe_float(os.getenv("BBP_TURNOVER_FAIL_CURRENT_MULTIPLIER", "1.0"), 1.0),
            short_multiplier=_safe_float(os.getenv("BBP_TURNOVER_FAIL_SHORT_MULTIPLIER", "0.9"), 0.9),
            medium_multiplier=_safe_float(os.getenv("BBP_TURNOVER_FAIL_MEDIUM_MULTIPLIER", "0.65"), 0.65),
            long_multiplier=_safe_float(os.getenv("BBP_TURNOVER_FAIL_LONG_MULTIPLIER", "0.5"), 0.5),
        )
        turnover_fail_code = str(turnover_eval.get("fail_code", "") or "")
        turnover_fail_reason = str(turnover_eval.get("fail_reason", "") or "")
        if turnover_fail_code:
            if data_mode:
                _record_business_fail(turnover_fail_code, turnover_fail_reason)
            else:
                logger.info(f"Turnover gate failed => {turnover_fail_code}: {turnover_fail_reason}")
                validated["webscrape_mode"] = webscrape_mode
                validated["checks_failed"] = "1"
                validated["fail_codes"] = turnover_fail_code
                validated["hard_stop"] = "True"
                validated["turnover_profit_history"] = ",".join(f"{_safe_float(v, 0.0):.2f}" for v in turnover_profit_history)
                validated["turnover_history_months"] = str(_safe_int(turnover_eval.get("history_months", 0), 0))
                validated["turnover_current_month_profit"] = str(_safe_float(turnover_eval.get("current_month_profit", 0.0), 0.0))
                validated["turnover_short_avg_profit"] = str(_safe_float(turnover_eval.get("short_avg_profit", 0.0), 0.0))
                validated["turnover_medium_avg_profit"] = str(_safe_float(turnover_eval.get("medium_avg_profit", 0.0), 0.0))
                validated["turnover_long_avg_profit"] = str(_safe_float(turnover_eval.get("long_avg_profit", 0.0), 0.0))
                validated["turnover_history_score"] = str(_safe_int(turnover_eval.get("score", 0), 0))
                validated["turnover_history_recommendation"] = str(turnover_eval.get("recommendation", "FAIL"))
                validated["turnover_fail_code"] = turnover_fail_code
                validated["turnover_fail_reason"] = turnover_fail_reason
                return {"success": False, "scraped_data": validated, "error": "TURNOVERFAIL"}

        if use_old_for_date and not skip_date_scraping:
            old_date = fallback_scrape_date_with_driver(date_driver, asin)
            if old_date != "N/A":
                validated["product_info"] = old_date
            else:
                if data_mode:
                    _record_business_fail("NODATE", "Chrome91 fallback also returned N/A.")
                else:
                    logger.info("[Chrome91] no date => NODATE_OLDCHROME.")
                    return {"success": False, "scraped_data": validated, "error": "NODATE_OLDCHROME"}

        historical_uk_raw = _normalize_text(validated.get("historical_uk_reviews", ""))
        if _normalize_lower(historical_uk_raw) in {"", "n/a", "na", "unknown"}:
            logger.warning("Historical UK review evidence unavailable => technical rescan.")
            validated["webscrape_mode"] = webscrape_mode
            return {"success": False, "scraped_data": validated, "error": "REVIEWS_TIMEOUT"}

        historical_uk_val = _safe_int(historical_uk_raw, 0)
        if historical_uk_val == 0:
            if data_mode:
                _record_business_fail("REVIEWFAIL", "No historical UK reviews.")
            else:
                logger.info("No historical UK reviews => fail.")
                return {"success": False, "scraped_data": validated, "error": "REVIEWS_NO_UK"}

        if (not skip_date_scraping) and (not use_old_for_date) and found_date == "N/A":
            logger.info("[Profile5] date is N/A => fallback to Chrome91.")
            old_date = fallback_scrape_date_with_driver(date_driver, asin)
            if old_date == "N/A":
                if data_mode:
                    _record_business_fail("NODATE", "New Chrome date missing and Chrome91 fallback missing.")
                else:
                    logger.info("[Chrome91] no date => NODATE_OLDCHROME.")
                    return {"success": False, "scraped_data": validated, "error": "NODATE_OLDCHROME"}
            validated["product_info"] = old_date

        history_score, history_pattern_note = compute_history_score(bbp_sales_history)
        economics_score = compute_economics_score(
            monthly_turnover=est_monthly_turnover,
            monthly_profit=est_monthly_profit,
            profit_per_unit=profit_per_unit_30d,
            profit_threshold=monthly_profit_threshold,
        )
        opportunity_score, opportunity_recommendation = build_opportunity_recommendation(
            monthly_profit=est_monthly_profit,
            profit_threshold=monthly_profit_threshold,
            economics_score=economics_score,
            history_score=history_score,
            confidence_score=confidence_score,
        )

        pricing_hist_score = _safe_int(phase_snapshot.get("pricing_history_score", 50), 50)
        ranking_hist_score = _safe_int(phase_snapshot.get("ranking_history_score", 50), 50)
        ops_hist_score = _safe_int(
            phase_snapshot.get("history_operational_score", int(round((pricing_hist_score + ranking_hist_score) / 2))),
            50
        )
        history_blended_score = int(round(_clamp((opportunity_score * 0.55) + (ops_hist_score * 0.45), 0.0, 100.0)))

        phase_rec = str(phase_snapshot.get("phase_recommendation", "UNKNOWN")).upper()
        if phase_rec == "AVOID":
            history_recommendation = "FAIL"
        elif history_blended_score >= 68 and opportunity_recommendation == "PASS":
            if phase_rec in ("STRONG_HOLD", "HOLD_WITH_PATIENCE"):
                history_recommendation = "PASS"
            else:
                history_recommendation = "REVIEW"
        elif history_blended_score < 45:
            history_recommendation = "FAIL"
        else:
            history_recommendation = "REVIEW"

        validated["amazon_bought_floor"] = "" if amazon_floor is None else str(amazon_floor)
        validated["bbp_monthly_sales_current"] = str(bbp_sales_current)
        validated["bbp_monthly_sales_recent_avg"] = str(int(round(bbp_sales_recent_avg))) if bbp_sales_recent_avg > 0 else "0"
        validated["bbp_monthly_sales_history"] = ",".join(str(_safe_int(v, 0)) for v in bbp_sales_history) if bbp_sales_history else ""
        validated["bbp_monthly_units_chosen"] = str(_safe_int(chosen_units, 0))
        validated["bbp_dashboard_yes_or_no"] = bbp_dashboard_yes_or_no
        _apply_dashboard_delivery_fields(validated, bbp_dashboard_yes_or_no)
        validated["bbp_sales_chart_source"] = bbp_sales_chart_source
        validated["bbp_sales_chart_month_labels"] = "|".join(str(v) for v in bbp_sales_chart_month_labels)
        validated["bbp_sales_chart_month_units"] = "|".join(str(_safe_int(v, 0)) for v in bbp_sales_chart_month_units)
        validated["bbp_sales_chart_series"] = bbp_sales_chart_series
        validated["bbp_sales_last_completed_month_label"] = bbp_sales_last_completed_month_label
        validated["bbp_sales_last_completed_month_units"] = str(bbp_sales_last_completed_month_units)
        validated["bbp_sales_current_month_label"] = bbp_sales_current_month_label
        validated["bbp_sales_current_month_units"] = str(bbp_sales_current_month_units)
        validated["bbp_sales_future_month_count_ignored"] = str(bbp_sales_future_month_count_ignored)
        validated["bbp_sales_replay_demand_basis_source"] = bbp_sales_replay_demand_basis_source
        validated["bbp_sales_replay_demand_basis_label"] = bbp_sales_replay_demand_basis_label
        validated["bbp_sales_replay_demand_basis_units"] = str(bbp_sales_replay_demand_basis_units)
        validated["bbp_section_snapshot_path"] = bbp_section_snapshot_path
        validated["bbp_section_snapshot_nodes"] = str(_safe_int(bbp_section_snapshot_nodes, 0))
        validated["bbp_section_snapshot_error"] = bbp_section_snapshot_error
        validated["demand_confidence_score"] = str(_safe_int(confidence_score, 0))
        validated["demand_confidence_note"] = confidence_note
        validated["avg_30_day_price"] = f"{avg_30_day_price:.2f}" if avg_30_day_price > 0 else "0"
        validated["profit_per_unit_30d"] = f"{profit_per_unit_30d:.2f}" if profit_per_unit_30d > 0 else "0"
        validated["estimated_monthly_turnover"] = f"{est_monthly_turnover:.2f}" if est_monthly_turnover > 0 else "0"
        validated["estimated_monthly_profit"] = f"{est_monthly_profit:.2f}" if est_monthly_profit > 0 else "0"
        validated["turnover_profit_history"] = ",".join(f"{_safe_float(v, 0.0):.2f}" for v in turnover_profit_history)
        validated["turnover_history_months"] = str(_safe_int(turnover_eval.get("history_months", 0), 0))
        validated["turnover_current_month_profit"] = str(_safe_float(turnover_eval.get("current_month_profit", 0.0), 0.0))
        validated["turnover_short_avg_profit"] = str(_safe_float(turnover_eval.get("short_avg_profit", 0.0), 0.0))
        validated["turnover_medium_avg_profit"] = str(_safe_float(turnover_eval.get("medium_avg_profit", 0.0), 0.0))
        validated["turnover_long_avg_profit"] = str(_safe_float(turnover_eval.get("long_avg_profit", 0.0), 0.0))
        validated["turnover_history_score"] = str(_safe_int(turnover_eval.get("score", 0), 0))
        validated["turnover_history_recommendation"] = str(turnover_eval.get("recommendation", "REVIEW"))
        validated["turnover_fail_code"] = str(turnover_eval.get("fail_code", "") or "")
        validated["turnover_fail_reason"] = str(turnover_eval.get("fail_reason", "") or "")
        validated["economics_score"] = str(_safe_int(economics_score, 0))
        validated["history_score"] = str(_safe_int(history_score, 0))
        validated["opportunity_score"] = str(_safe_int(opportunity_score, 0))
        validated["opportunity_recommendation"] = opportunity_recommendation
        validated["history_window_days"] = str(_safe_int(phase_snapshot.get("history_window_days", 0), 0))
        validated["history_data_points"] = str(_safe_int(phase_snapshot.get("history_data_points", 0), 0))
        validated["history_gap_fill_rate"] = str(_safe_float(phase_snapshot.get("history_gap_fill_rate", 0.0), 0.0))
        validated["pricing_history_score"] = str(pricing_hist_score)
        validated["ranking_history_score"] = str(ranking_hist_score)
        validated["history_operational_score"] = str(ops_hist_score)
        validated["phase_profit_pct"] = str(_safe_float(phase_snapshot.get("phase_profit_pct", 0.0), 0.0))
        validated["phase_low_roi_pct"] = str(_safe_float(phase_snapshot.get("phase_low_roi_pct", 0.0), 0.0))
        validated["phase_break_even_pct"] = str(_safe_float(phase_snapshot.get("phase_break_even_pct", 0.0), 0.0))
        validated["phase_loss_pct"] = str(_safe_float(phase_snapshot.get("phase_loss_pct", 0.0), 0.0))
        validated["phase_longest_profit_days"] = str(_safe_int(phase_snapshot.get("phase_longest_profit_days", 0), 0))
        validated["phase_longest_low_roi_days"] = str(_safe_int(phase_snapshot.get("phase_longest_low_roi_days", 0), 0))
        validated["phase_longest_break_even_days"] = str(_safe_int(phase_snapshot.get("phase_longest_break_even_days", 0), 0))
        validated["phase_longest_loss_days"] = str(_safe_int(phase_snapshot.get("phase_longest_loss_days", 0), 0))
        validated["phase_current"] = str(phase_snapshot.get("phase_current", "unknown"))
        validated["phase_recommendation"] = str(phase_snapshot.get("phase_recommendation", "UNKNOWN"))
        validated["exit_strategy"] = str(phase_snapshot.get("exit_strategy", "REVIEW"))
        validated["bsr_recent_avg"] = str(_safe_float(phase_snapshot.get("bsr_recent_avg", 0.0), 0.0))
        validated["bsr_prev_avg"] = str(_safe_float(phase_snapshot.get("bsr_prev_avg", 0.0), 0.0))
        validated["bsr_trend"] = str(phase_snapshot.get("bsr_trend", "unknown"))
        validated["chosen_price_recent_avg"] = str(_safe_float(phase_snapshot.get("chosen_price_recent_avg", 0.0), 0.0))
        validated["chosen_price_prev_avg"] = str(_safe_float(phase_snapshot.get("chosen_price_prev_avg", 0.0), 0.0))
        validated["price_trend_pct"] = str(_safe_float(phase_snapshot.get("price_trend_pct", 0.0), 0.0))
        validated["history_source"] = str(phase_snapshot.get("history_source", ""))
        validated["history_recommendation"] = history_recommendation
        validated["history_blended_score"] = str(history_blended_score)
        validated["price_history_span_days"] = str(_safe_int(phase_snapshot.get("price_history_span_days", 0), 0))
        validated["price_history_points_365d"] = str(_safe_int(phase_snapshot.get("price_history_points_365d", 0), 0))
        validated["price_hist_table_raw"] = json.dumps(hist_raw_rows, ensure_ascii=True, separators=(",", ":"))
        validated["chart_price_daily_series"] = str(phase_snapshot.get("chart_price_daily_series", ""))
        validated["chart_bsr_daily_series"] = str(phase_snapshot.get("chart_bsr_daily_series", ""))
        validated["chart_phase_daily_series"] = str(phase_snapshot.get("chart_phase_daily_series", ""))
        validated["chart_raw_amazon_daily_series"] = str(phase_snapshot.get("chart_raw_amazon_daily_series", ""))
        validated["chart_raw_fba_daily_series"] = str(phase_snapshot.get("chart_raw_fba_daily_series", ""))
        validated["chart_raw_fbm_daily_series"] = str(phase_snapshot.get("chart_raw_fbm_daily_series", ""))
        validated["chart_raw_buy_box_daily_series"] = str(phase_snapshot.get("chart_raw_buy_box_daily_series", ""))
        validated["chart_raw_bsr_daily_series"] = str(phase_snapshot.get("chart_raw_bsr_daily_series", ""))

        validated["price_hist_windows"] = "30,90,180,365"
        for lane in ("amazon", "fba", "buy_box", "fbm", "new"):
            lane_points = lane_history.get(lane, {}) if isinstance(lane_history.get(lane, {}), dict) else {}
            for win in (30, 90, 180, 365):
                lane_value = _safe_float(lane_points.get(win, 0.0), 0.0)
                validated[f"price_hist_{lane}_{win}"] = f"{lane_value:.2f}" if lane_value > 0 else "0"

        validated["pricing_mode"] = str(pricing_plan.get("pricing_mode", "live"))
        validated["unavailable_detected"] = str(bool(pricing_plan.get("unavailable_detected", False)))
        validated["price_history_365d_exists"] = str(bool(pricing_plan.get("price_history_365d_exists", False)))
        validated["fallback_lane_used"] = str(pricing_plan.get("fallback_lane_used", ""))
        validated["fallback_window_used"] = str(_safe_int(pricing_plan.get("fallback_window_used", 0), 0))
        validated["fallback_price"] = str(_safe_float(pricing_plan.get("fallback_price", 0.0), 0.0))
        validated["fallback_roi"] = str(_safe_float(pricing_plan.get("fallback_roi", 0.0), 0.0))
        validated["fallback_confidence"] = str(pricing_plan.get("fallback_confidence", "LOW"))
        validated["fbm_undercut_flag"] = str(bool(pricing_plan.get("fbm_undercut_flag", False)))
        validated["pricing_decision_note"] = str(pricing_plan.get("pricing_decision_note", ""))
        validated["bbp_auto_sell_price"] = str(current_auto_price)
        validated["bbp_final_sell_price"] = str(_safe_float(final_sell_price_used, 0.0))
        validated["roi_check_source"] = roi_check_source
        validated["roi_check_value"] = str(_safe_float(roi_check_value, 0.0))
        validated["webscrape_mode"] = webscrape_mode
        validated["checks_failed"] = str(len(check_fail_codes))
        validated["fail_codes"] = "|".join(check_fail_codes)
        validated["hard_stop"] = "False"

        base_history_note = history_pattern_note if bbp_sales_history else "history_missing"
        phase_note = validated["phase_recommendation"]
        exit_note = validated["exit_strategy"]
        validated["history_pattern_note"] = f"{base_history_note}|phase={phase_note}|exit={exit_note}"
        if bbp_sales_history_text and not validated["bbp_monthly_sales_history"]:
            validated["bbp_monthly_sales_history"] = bbp_sales_history_text

        logger.info(
            f"[Profile5] Opportunity => rec={opportunity_recommendation}, score={opportunity_score}, "
            f"profit_m={est_monthly_profit:.2f}, turnover_m={est_monthly_turnover:.2f}, units={chosen_units}, "
            f"history_rec={history_recommendation}, history_score={history_blended_score}"
        )

        return {"success": True, "scraped_data": validated}

    except Exception as e:
        logger.error(f"unexpected => {e}")
        return {"success": False, "scraped_data": {}, "error": str(e)}
