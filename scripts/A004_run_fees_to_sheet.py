"""
Fetch fee estimates at fixed price points (£10 and £100) and update Product_DB with fees.

What it does:
- Reads SKUs from Product_DB.
- Calls SP-API FeesEstimate for each SKU at £10 and £100 (GBP, FBA).
- Writes fee_total_10, fee_total_100, last_updated_A004 back to Product_DB.
- Saves a CSV snapshot to out/fees_estimates.csv.
"""


from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, TypedDict

import gspread
import pandas as pd
import requests
from requests.exceptions import RequestException

# Paths for auto-adding SKUs seen in orders
ORDER_ITEMS_ALL = Path("out/order_items_all.csv")
MERCHANT_LISTINGS = Path("out/merchant_listings_latest.csv")

# Ensure project root is on path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SHEET_ID = "1b7iREy92vF_a1Lw72g0SOGS7t4-IOSBeeoHetLTN43s"
PRODUCT_DB_TAB = "Product_DB"
MARKETPLACE_ID = os.environ.get("MARKETPLACE_ID", "A1F83G8C2ARO7P")
PRICE_POINTS = [10.0, 100.0]
CURRENCY = "GBP"
SLEEP_SEC = float(os.environ.get("FEES_SLEEP_SEC", "0.05"))
LIMIT = int(os.environ.get("FEES_LIMIT", "0"))  # 0 = no limit
MAX_RETRIES = int(os.environ.get("FEES_MAX_RETRIES", "3"))
BACKOFF = float(os.environ.get("FEES_BACKOFF", "0.5"))
MIN_INTERVAL = float(os.environ.get("FEES_MIN_INTERVAL", "1.0"))
MAX_INTERVAL = float(os.environ.get("FEES_MAX_INTERVAL", "6.0"))
FEES_REQUEUE_MAX_PASSES = int(os.environ.get("FEES_REQUEUE_MAX_PASSES", "2"))
FEES_REQUEUE_PASS_BACKOFF_SEC = float(os.environ.get("FEES_REQUEUE_PASS_BACKOFF_SEC", "15"))

_throttle_next_allowed = 0.0
_throttle_last_fail_delay = 0.0
_throttle_429_count = 0


class FeeEstimateResult(TypedDict):
    fees: Dict[float, Optional[float]]
    referrals: Dict[float, Optional[float]]
    errors: Dict[float, str]
    attempt_counts: Dict[float, int]
    requeue_passes_used: int
    unresolved_points: List[float]


def load_env(paths: Optional[List[str]] = None) -> None:
    paths = paths or ["secrets/.env", ".env"]
    for p in paths:
        path = Path(p)
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.split("#", 1)[0].strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
        break


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing env var: {name}")
    return value


def get_lwa_access_token(timeout: int = 30) -> str:
    refresh_token = require_env("LWA_REFRESH_TOKEN")
    client_id = require_env("LWA_CLIENT_ID")
    client_secret = require_env("LWA_CLIENT_SECRET")
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}
    resp = requests.post("https://api.amazon.com/auth/o2/token", data=data, headers=headers, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"LWA token failed: {resp.status_code} {resp.text}")
    payload = resp.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError(f"LWA token missing in response: {payload}")
    return token


def _await_slot(minimum: Optional[float] = None) -> None:
    global _throttle_next_allowed
    now = time.monotonic()
    target = _throttle_next_allowed
    if minimum is not None:
        target = max(target, now + minimum)
    delay = max(0.0, target - now)
    if delay > 0:
        time.sleep(delay)


def _record_success(headers: Dict[str, str], minimum: float, maximum: float) -> None:
    global _throttle_next_allowed, _throttle_429_count, _throttle_last_fail_delay
    _throttle_429_count = 0
    _throttle_last_fail_delay = 0.0
    interval = max(minimum, 0.0)
    limit_hdr = headers.get("x-amzn-RateLimit-Limit")
    reset_hdr = headers.get("x-amzn-RateLimit-Reset")
    try:
        if limit_hdr:
            rps = float(limit_hdr)
            if rps > 0:
                interval = max(interval, 1.0 / rps)
    except Exception:
        pass
    try:
        if reset_hdr:
            reset = float(reset_hdr)
            if reset >= 0:
                interval = max(interval, reset)
    except Exception:
        pass
    interval = min(max(interval, minimum), maximum)
    interval *= 1.02  # small jitter
    base = max(time.monotonic(), _throttle_next_allowed)
    _throttle_next_allowed = base + interval


def _record_failure(headers: Dict[str, str], attempt: int, base_delay: float, maximum: float, status_code: Optional[int] = None) -> None:
    global _throttle_next_allowed, _throttle_429_count, _throttle_last_fail_delay
    delay = None
    for hdr in ("Retry-After", "x-amzn-RateLimit-Reset"):
        val = headers.get(hdr) if headers else None
        if val is None:
            continue
        try:
            parsed = float(val)
        except Exception:
            continue
        if parsed >= 0:
            delay = parsed
            break
    if delay is None:
        delay = min(base_delay * (2 ** max(0, attempt - 1)), maximum)
    delay = max(delay, base_delay)
    if status_code == 429:
        _throttle_429_count += 1
        if _throttle_429_count >= 3:
            delay = max(delay, (_throttle_last_fail_delay or delay) * 2)
    else:
        _throttle_429_count = 0
    _throttle_last_fail_delay = delay
    delay *= 1.05  # jitter
    base = max(time.monotonic(), _throttle_next_allowed)
    _throttle_next_allowed = base + delay


def call_fee_api(
    access_token: str,
    marketplace_id: str,
    id_value: str,
    price: float,
    timeout: int = 30,
    use_asin: bool = False,
) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    if use_asin:
        url = f"https://sellingpartnerapi-eu.amazon.com/products/fees/v0/items/{id_value}/feesEstimate"
    else:
        url = f"https://sellingpartnerapi-eu.amazon.com/products/fees/v0/listings/{id_value}/feesEstimate"
    body = {
        "FeesEstimateRequest": {
            "MarketplaceId": marketplace_id,
            "IsAmazonFulfilled": True,
            "Identifier": id_value,
            "PriceToEstimateFees": {
                "ListingPrice": {"CurrencyCode": CURRENCY, "Amount": price},
            },
        }
    }
    headers = {
        "x-amz-access-token": access_token,
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    last_err: Optional[str] = None
    for attempt in range(1, MAX_RETRIES + 1):
        _await_slot(MIN_INTERVAL)
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=timeout)
            if resp.status_code != 200:
                try:
                    err_txt = resp.json()
                except Exception:
                    err_txt = resp.text
                last_err = str(err_txt)
                _record_failure(resp.headers or {}, attempt, MIN_INTERVAL, MAX_INTERVAL, status_code=resp.status_code)
            else:
                payload = resp.json() or {}
                result = (payload.get("payload") or {}).get("FeesEstimateResult") or {}
                status = (result.get("Status") or "").lower()
                if status and status != "success":
                    err_obj = result.get("Error") or {}
                    msg = err_obj.get("Message") or err_obj or "FeesEstimateResult error"
                    last_err = str(msg)
                    _record_failure(resp.headers or {}, attempt, MIN_INTERVAL, MAX_INTERVAL, status_code=resp.status_code)
                else:
                    total_node = (result.get("TotalFeesEstimate") or {})
                    if not total_node:
                        total_node = (result.get("FeesEstimate") or {}).get("TotalFeesEstimate") or {}
                    total = total_node.get("Amount")
                    # Extract FBA-only fee and referral fee components if present
                    fba_fee = None
                    referral_fee = None
                    try:
                        details = ((result.get("FeesEstimate") or {}).get("FeeDetailList")) or (result.get("FeeDetailList") or [])
                        for d in details:
                            if (d.get("FeeType") or "").lower() == "fbafees":
                                amt = (d.get("FeeAmount") or {}).get("Amount")
                                if amt is not None:
                                    fba_fee = float(amt)
                            if (d.get("FeeType") or "").lower() == "referralfee":
                                amt = (d.get("FeeAmount") or {}).get("Amount")
                                if amt is not None:
                                    referral_fee = float(amt)
                    except Exception:
                        fba_fee = None
                        referral_fee = None
                    amount = None
                    try:
                        amount = float(total)
                    except Exception:
                        amount = None
                    if fba_fee is not None:
                        amount = fba_fee
                    if amount is None:
                        last_err = "No fee returned"
                        _record_failure(resp.headers or {}, attempt, MIN_INTERVAL, MAX_INTERVAL, status_code=resp.status_code)
                    else:
                        _record_success(resp.headers or {}, MIN_INTERVAL, MAX_INTERVAL)
                        referral_pct = None
                        if referral_fee is not None and price > 0:
                            referral_pct = round((referral_fee / price) * 100.0, 4)
                        return amount, referral_pct, None
        except RequestException as exc:
            last_err = str(exc)
            _record_failure({}, attempt, MIN_INTERVAL, MAX_INTERVAL, status_code=None)
        if attempt < MAX_RETRIES:
            time.sleep(BACKOFF * attempt)
    return None, None, last_err


def _estimate_prices_with_requeue(
    *,
    price_points: List[float],
    fetch_price_fn: Callable[[float], Tuple[Optional[float], Optional[float], Optional[str]]],
    sleep_between_calls_sec: float,
    requeue_max_passes: int,
    requeue_pass_backoff_sec: float,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> FeeEstimateResult:
    fees: Dict[float, Optional[float]] = {price: None for price in price_points}
    referrals: Dict[float, Optional[float]] = {price: None for price in price_points}
    errors: Dict[float, str] = {price: "" for price in price_points}
    attempt_counts: Dict[float, int] = {price: 0 for price in price_points}
    requeue_passes_used = 0

    def _call_price(price: float) -> None:
        fee, referral_pct, err = fetch_price_fn(price)
        attempt_counts[price] = int(attempt_counts.get(price, 0)) + 1
        if fee is not None:
            fees[price] = fee
        if referral_pct is not None:
            referrals[price] = referral_pct
        errors[price] = str(err or "").strip()
        if sleep_between_calls_sec > 0:
            sleep_fn(sleep_between_calls_sec)

    for price in price_points:
        _call_price(price)

    max_passes = max(int(requeue_max_passes), 0)
    pass_backoff = max(float(requeue_pass_backoff_sec), 0.0)
    for pass_idx in range(1, max_passes + 1):
        pending = [price for price in price_points if str(errors.get(price, "")).strip()]
        if not pending:
            break
        requeue_passes_used = pass_idx
        if pass_backoff > 0:
            sleep_fn(pass_backoff)
        for price in pending:
            _call_price(price)

    unresolved_points = [price for price in price_points if str(errors.get(price, "")).strip()]
    return {
        "fees": fees,
        "referrals": referrals,
        "errors": errors,
        "attempt_counts": attempt_counts,
        "requeue_passes_used": requeue_passes_used,
        "unresolved_points": unresolved_points,
    }


def calc_margin(price: float, fba_fee: Optional[float], referral_fee: Optional[float], cost: Optional[float]) -> Optional[float]:
    # Margin based on gross price (do not strip VAT here). Uses FBA fee + referral fee + cost.
    if fba_fee is None and referral_fee is None:
        return None
    try:
        c = float(cost) if cost not in (None, "",) else 0.0
    except Exception:
        c = 0.0
    if price <= 0:
        return None
    fba = float(fba_fee) if fba_fee not in (None, "",) else 0.0
    ref = float(referral_fee) if referral_fee not in (None, "",) else 0.0
    margin = (price - ref - fba - c) / price * 100.0
    return round(margin, 2)


def main() -> None:
    load_env()
    try:
        client = gspread.service_account(filename=str(Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json"))
        sheet = client.open_by_key(SHEET_ID)
        ws = sheet.worksheet(PRODUCT_DB_TAB)
    except Exception as exc:
        print(f"[A004] Sheets access failed: {exc}")
        return
    rows = ws.get_all_values()
    if not rows:
        print("Product_DB empty")
        return
    headers = rows[0]
    idx = {h: i for i, h in enumerate(headers)}

    # Build active listings set from merchant_listings_latest.csv (if present).
    active_listings = set()
    if MERCHANT_LISTINGS.exists():
        try:
            mdf = pd.read_csv(MERCHANT_LISTINGS, dtype=str).fillna("")
            if "seller-sku" in mdf.columns:
                if "status" in mdf.columns:
                    active = mdf[mdf["status"].str.strip().str.lower() == "active"]
                else:
                    active = mdf
                active_listings = set(active["seller-sku"].astype(str).str.strip())
        except Exception:
            active_listings = set()

    # Ensure columns exist
    for col in [
        "fba_fee_10",
        "fba_fee_100",
        "referral_fee_10",
        "referral_fee_100",
        "last_updated_A004",
    ]:
        if col not in idx:
            idx[col] = len(headers)
            headers.append(col)
            for r in rows[1:]:
                while len(r) < len(headers):
                    r.append("")

    sku_idx = idx.get("seller_sku", -1)
    cost_idx = idx.get("last_purchase_price", -1)
    asin_idx = idx.get("asin", -1)
    vat_idx = idx.get("vat_rate", -1)
    status_idx = idx.get("sale_status", -1)

    # Auto-add SKUs seen in order_items_all but missing in Product_DB
    try:
        if ORDER_ITEMS_ALL.exists():
            items_df = pd.read_csv(ORDER_ITEMS_ALL, dtype=str).fillna("")
            sheet_skus = set(r[sku_idx] for r in rows[1:] if sku_idx >= 0 and len(r) > sku_idx and r[sku_idx])
            for _, it_row in items_df.iterrows():
                sku_val = it_row.get("seller_sku") or ""
                if active_listings and sku_val not in active_listings:
                    continue
                if not sku_val or sku_val in sheet_skus:
                    continue
                asin_val = it_row.get("asin") or ""
                title_val = it_row.get("title") or ""
                new_row = [""] * len(headers)
                if sku_idx >= 0:
                    new_row[sku_idx] = sku_val
                if asin_idx >= 0:
                    new_row[asin_idx] = asin_val
                # optional title column if present
                title_idx = idx.get("title", -1)
                if title_idx >= 0:
                    new_row[title_idx] = title_val
                # defaults
                if status_idx >= 0:
                    new_row[status_idx] = "active"
                if vat_idx >= 0:
                    new_row[vat_idx] = "20"
                supplier_pack_idx = idx.get("supplier_pack_size", -1)
                if supplier_pack_idx >= 0:
                    new_row[supplier_pack_idx] = "1"
                amazon_pack_idx = idx.get("amazon_pack_size", -1)
                if amazon_pack_idx >= 0:
                    new_row[amazon_pack_idx] = "1"
                moq_idx = idx.get("moq", -1)
                if moq_idx >= 0:
                    new_row[moq_idx] = "1"
            rows.append(new_row)
            sheet_skus.add(sku_val)
    except Exception:
        pass

    # Collect rows eligible for fee refresh:
    # - Explicitly active rows.
    # - Blank status rows (legacy/missing data) so automation does not stall.
    # - Never include explicitly discontinued/dropped rows.
    # If merchant_listings_latest.csv exists, still require the SKU to be active there.
    target_rows = []
    for rid, r in enumerate(rows[1:], start=1):
        if sku_idx < 0 or len(r) <= sku_idx:
            continue
        if not r[sku_idx]:
            continue
        status = r[status_idx].strip().lower() if status_idx >= 0 and len(r) > status_idx else ""
        if status in {"dropped", "discontinued"}:
            continue
        if status in {"", "active"}:
            if active_listings and r[sku_idx] not in active_listings:
                continue
            target_rows.append(rid)

    access_token = get_lwa_access_token()
    updates = 0
    out_records = []
    now_iso = datetime.now(timezone.utc).isoformat()
    processed = 0
    errors = 0
    total_skus = len(target_rows)
    print(f"[A004] Processing up to {('all' if LIMIT == 0 else LIMIT)} active SKUs (rows: {total_skus})")
    for rid in target_rows:
        if LIMIT > 0 and processed >= LIMIT:
            break
        r = rows[rid]
        sku = r[sku_idx]
        asin = r[asin_idx].strip() if asin_idx >= 0 and len(r) > asin_idx else ""

        # prefer ASIN when present, otherwise SKU
        id_attempts = []
        if asin:
            id_attempts.append((asin, True))
        if sku:
            id_attempts.append((sku, False))

        if not id_attempts:
            fees = {price: None for price in PRICE_POINTS}
            referrals = {price: None for price in PRICE_POINTS}
            errs = {price: "Missing ASIN/SKU" for price in PRICE_POINTS}
            attempt_counts = {price: 1 for price in PRICE_POINTS}
            requeue_passes_used = 0
            unresolved_points = [price for price in PRICE_POINTS]
        else:
            def _fetch_price(price: float) -> Tuple[Optional[float], Optional[float], Optional[str]]:
                fee = None
                referral_pct = None
                err = None
                for id_val, use_asin in id_attempts:
                    fee, referral_pct, err = call_fee_api(access_token, MARKETPLACE_ID, id_val, price, use_asin=use_asin)
                    if fee is not None or referral_pct is not None:
                        break
                referral = round(referral_pct, 4) if referral_pct is not None else None
                return fee, referral, err

            estimate: FeeEstimateResult = _estimate_prices_with_requeue(
                price_points=PRICE_POINTS,
                fetch_price_fn=_fetch_price,
                sleep_between_calls_sec=SLEEP_SEC,
                requeue_max_passes=FEES_REQUEUE_MAX_PASSES,
                requeue_pass_backoff_sec=FEES_REQUEUE_PASS_BACKOFF_SEC,
            )
            fees = estimate["fees"]
            referrals = estimate["referrals"]
            errs = estimate["errors"]
            attempt_counts = estimate["attempt_counts"]
            requeue_passes_used = int(estimate["requeue_passes_used"])
            unresolved_points = estimate["unresolved_points"]
        errors += len(unresolved_points)

        def set_val(field: str, value) -> None:
            col = idx[field]
            while len(rows[rid]) < len(headers):
                rows[rid].append("")
            # Keep any existing value if the API gave us nothing.
            if value is None or value == "":
                return
            rows[rid][col] = str(value)

        has_fee = any(v is not None for v in fees.values())
        has_err = any(errs.values())
        set_val("fba_fee_10", fees.get(10.0))
        set_val("fba_fee_100", fees.get(100.0))
        set_val("referral_fee_10", referrals.get(10.0))
        set_val("referral_fee_100", referrals.get(100.0))
        if has_fee and not has_err:
            set_val("last_updated_A004", now_iso)
        else:
            # Explicitly clear stale timestamp when we couldn't fetch a fee.
            col = idx["last_updated_A004"]
            while len(rows[rid]) < len(headers):
                rows[rid].append("")
            rows[rid][col] = ""
        updates += 1
        processed += 1
        out_records.append(
            {
                "seller_sku": sku,
                "fba_fee_10": fees.get(10.0),
                "fba_fee_100": fees.get(100.0),
                "referral_fee_10": referrals.get(10.0),
                "referral_fee_100": referrals.get(100.0),
                "error_10": errs.get(10.0) or "",
                "error_100": errs.get(100.0) or "",
                "attempt_count_10": int(attempt_counts.get(10.0, 0)),
                "attempt_count_100": int(attempt_counts.get(100.0, 0)),
                "requeue_passes_used": requeue_passes_used,
                "failed_price_points": "|".join([f"{price:g}" for price in unresolved_points]),
                "failure_recorded_utc": now_iso,
            }
        )
        if processed % 50 == 0:
            print(f"[A004] Progress: {processed} SKUs processed...")

    ws.clear()
    ws.update("A1", [headers] + rows[1:])
    Path("out").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(out_records).to_csv("out/fees_estimates.csv", index=False)
    pd.DataFrame(rows[1:], columns=headers).to_csv("out/product_db_preview.csv", index=False)
    failed_cols = [
        "seller_sku",
        "fba_fee_10",
        "fba_fee_100",
        "referral_fee_10",
        "referral_fee_100",
        "error_10",
        "error_100",
        "attempt_count_10",
        "attempt_count_100",
        "requeue_passes_used",
        "failed_price_points",
        "failure_recorded_utc",
    ]
    failed = [r for r in out_records if (r.get("error_10") or r.get("error_100"))]
    failed_df = pd.DataFrame(failed, columns=failed_cols)
    failed_df.to_csv("out/fees_failed.csv", index=False)
    if failed:
        reasons = {}
        for r in failed:
            for key in ("error_10", "error_100"):
                err = r.get(key) or ""
                if err:
                    reasons[err] = reasons.get(err, 0) + 1
        top_reasons = sorted(reasons.items(), key=lambda x: x[1], reverse=True)[:5]
        print(f"[A004] Failed SKUs: {len(failed)}")
        for err, cnt in top_reasons:
            print(f"[A004] Reason x{cnt}: {err}")
        print("[A004] Saved failed SKUs to out/fees_failed.csv")
    print({"updated_rows": updates, "errors": errors, "snapshot": "out/fees_estimates.csv"})


if __name__ == "__main__":
    main()
