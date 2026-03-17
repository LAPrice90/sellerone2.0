from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

try:
    from scripts.api.get_financial_events import get_lwa_access_token, load_dotenv_if_missing
    from scripts.api.spapi_owner import SpApiCallContext, spapi_post_json
except ModuleNotFoundError:
    from api.get_financial_events import get_lwa_access_token, load_dotenv_if_missing
    from api.spapi_owner import SpApiCallContext, spapi_post_json

SPAPI_BASE_URL = os.environ.get("SPAPI_BASE_URL", "https://sellingpartnerapi-eu.amazon.com")
CPT_LWA_TIMEOUT_SECONDS = max(float(os.environ.get("CPT_LWA_TIMEOUT_SECONDS", "15") or "15"), 5.0)
CPT_CONNECT_TIMEOUT_SECONDS = max(float(os.environ.get("CPT_CONNECT_TIMEOUT_SECONDS", "5") or "5"), 1.0)
CPT_READ_TIMEOUT_SECONDS = max(float(os.environ.get("CPT_READ_TIMEOUT_SECONDS", "20") or "20"), 5.0)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _status_code_from_resp(resp: dict[str, Any]) -> int | None:
    status = resp.get("status")
    if isinstance(status, dict):
        status = status.get("statusCode") or status.get("code")
    if status is None:
        return None
    try:
        return int(float(str(status).strip()))
    except Exception:
        return None


def _money_amount_ccy(obj: object) -> tuple[float | None, str]:
    if not isinstance(obj, dict):
        return None, ""
    if "amount" in obj:
        try:
            return float(obj.get("amount")), str(obj.get("currencyCode") or "")
        except Exception:
            return None, str(obj.get("currencyCode") or "")
    listing = obj.get("listingPrice")
    if isinstance(listing, dict) and "amount" in listing:
        try:
            return float(listing.get("amount")), str(listing.get("currencyCode") or "")
        except Exception:
            return None, str(listing.get("currencyCode") or "")
    return None, ""


def _extract_reference_prices(body: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(body.get("referencePrices"), list):
        return body.get("referencePrices") or []
    summaries = body.get("summaries")
    if isinstance(summaries, list) and summaries and isinstance(summaries[0], dict):
        ref = summaries[0].get("referencePrices")
        if isinstance(ref, list):
            return ref
    return []


def _extract_cpt_from_body(body: dict[str, Any]) -> tuple[str, float | None]:
    for ref in _extract_reference_prices(body):
        if not isinstance(ref, dict):
            continue
        name = str(ref.get("name") or "").strip().lower()
        if name not in {"competitivepricethreshold", "competitive_price_threshold", "competitiveprice"}:
            continue
        price_obj = ref.get("price") if isinstance(ref.get("price"), dict) else ref
        amount, ccy = _money_amount_ccy(price_obj)
        if amount is None:
            continue
        if str(ccy).strip().upper() != "GBP":
            continue
        return "OK", float(amount)
    return "MISSING", None


def _extract_batch_error_summary(resp_item: object) -> str:
    if not isinstance(resp_item, dict):
        return ""
    body = resp_item.get("body")
    if isinstance(body, dict):
        body_errors = body.get("errors")
        if isinstance(body_errors, list) and body_errors:
            first = body_errors[0] if isinstance(body_errors[0], dict) else {}
            code = str(first.get("code") or "").strip()
            message = str(first.get("message") or "").strip()
            detail = ": ".join([x for x in [code, message] if x])
            if detail:
                return detail[:200]
        message = str(body.get("message") or "").strip()
        if message:
            return message[:200]
    top_errors = resp_item.get("errors")
    if isinstance(top_errors, list) and top_errors:
        first = top_errors[0] if isinstance(top_errors[0], dict) else {}
        code = str(first.get("code") or "").strip()
        message = str(first.get("message") or "").strip()
        detail = ": ".join([x for x in [code, message] if x])
        if detail:
            return detail[:200]
    return ""


def fetch_cpt_for_asin(
    *,
    asin: str,
    marketplace_id: str,
    run_id: str,
    script_name: str,
    lwa_timeout_seconds: float | None = None,
    connect_timeout_seconds: float | None = None,
    read_timeout_seconds: float | None = None,
) -> dict[str, object]:
    now_utc = _utc_now_iso()
    asin_clean = str(asin or "").strip()
    if not asin_clean:
        return {
            "cpt_gbp": "",
            "cpt_status": "ERROR",
            "cpt_last_refresh_utc": now_utc,
            "reason_codes": ["CPT_ERROR", "CPT_ASIN_MISSING"],
            "error_summary": "asin_missing",
        }

    try:
        load_dotenv_if_missing()
        token_timeout = max(float(lwa_timeout_seconds or CPT_LWA_TIMEOUT_SECONDS), 1.0)
        connect_timeout = max(float(connect_timeout_seconds or CPT_CONNECT_TIMEOUT_SECONDS), 1.0)
        read_timeout = max(float(read_timeout_seconds or CPT_READ_TIMEOUT_SECONDS), 1.0)
        token = get_lwa_access_token(timeout=int(token_timeout))
        body_obj = {
            "requests": [
                {
                    "method": "GET",
                    "uri": "/products/pricing/2022-05-01/items/competitiveSummary",
                    "asin": asin_clean,
                    "marketplaceId": str(marketplace_id or "").strip(),
                    "includedData": ["referencePrices"],
                }
            ]
        }
        headers = {
            "x-amz-access-token": token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        ctx = SpApiCallContext(
            run_id=run_id,
            script_name=script_name,
            endpoint="products_pricing_post_competitive_summary_batch",
            marketplace=str(marketplace_id or ""),
            sku_count=1,
        )
        resp = spapi_post_json(
            ctx=ctx,
            url=f"{SPAPI_BASE_URL}/batches/products/pricing/2022-05-01/items/competitiveSummary",
            spapi_base_url=SPAPI_BASE_URL,
            headers=headers,
            body=json.dumps(body_obj, ensure_ascii=True, separators=(",", ":")),
            timeout=(connect_timeout, read_timeout),
            min_interval_sec=1.0,
            max_retries=2,
        )
        if int(resp.status_code) != 200:
            outer_message = ""
            try:
                payload = resp.json() or {}
                if isinstance(payload, dict):
                    outer_message = str(payload.get("message") or "").strip()
            except Exception:
                outer_message = (resp.text or "").strip()[:200]
            summary = f"http_{resp.status_code}"
            if outer_message:
                summary = f"{summary}:{outer_message}"[:200]
            return {
                "cpt_gbp": "",
                "cpt_status": "ERROR",
                "cpt_last_refresh_utc": now_utc,
                "reason_codes": ["CPT_ERROR"],
                "error_summary": summary,
            }
        payload = resp.json() or {}
        responses = payload.get("responses") or []
        if not responses:
            return {
                "cpt_gbp": "",
                "cpt_status": "NO_CPT",
                "cpt_last_refresh_utc": now_utc,
                "reason_codes": ["CPT_NO_VALUE_200"],
                "error_summary": "",
            }
        first = responses[0] if isinstance(responses[0], dict) else {}
        status_code = _status_code_from_resp(first)
        if status_code is None or status_code < 200 or status_code >= 300:
            inner_error = _extract_batch_error_summary(first)
            summary = f"batch_status_{status_code if status_code is not None else 'unknown'}"
            if inner_error:
                summary = f"{summary}:{inner_error}"[:200]
            return {
                "cpt_gbp": "",
                "cpt_status": "ERROR",
                "cpt_last_refresh_utc": now_utc,
                "reason_codes": ["CPT_ERROR"],
                "error_summary": summary,
            }
        body = first.get("body") if isinstance(first.get("body"), dict) else {}
        status, cpt_amount = _extract_cpt_from_body(body)
        if status == "OK" and cpt_amount is not None:
            return {
                "cpt_gbp": f"{cpt_amount:.2f}",
                "cpt_status": "OK",
                "cpt_last_refresh_utc": now_utc,
                "reason_codes": [],
                "error_summary": "",
            }
        return {
            "cpt_gbp": "",
            "cpt_status": "NO_CPT",
            "cpt_last_refresh_utc": now_utc,
            "reason_codes": ["CPT_NO_VALUE_200"],
            "error_summary": "",
        }
    except Exception as exc:
        return {
            "cpt_gbp": "",
            "cpt_status": "ERROR",
            "cpt_last_refresh_utc": now_utc,
            "reason_codes": ["CPT_ERROR"],
            "error_summary": str(exc)[:200],
        }

