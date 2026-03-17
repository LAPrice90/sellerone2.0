from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime, timezone
from typing import Callable, Iterable, Mapping

from scripts.phase1 import phase1_storage
from scripts.api.spapi_owner import SpApiCallContext, spapi_patch_json

SPAPI_BASE_URL = os.environ.get("SPAPI_BASE_URL", "https://sellingpartnerapi-eu.amazon.com")


@dataclass(frozen=True)
class WriteVerifyResult:
    write_status: str
    write_error: str
    intended_price_gbp: str
    submitted_price_gbp: str
    observed_price_gbp: str
    verification_source: str
    probe_started: bool
    probe_id: str
    http_status: str
    submission_id: str
    reason_codes: list[str]


def _to_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    raw = str(value).strip()
    if raw == "":
        return None
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


def _money(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"{value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_patch_listings_item_body(
    *,
    product_type: str,
    marketplace_id: str,
    target_price_gbp: object,
    currency: str = "GBP",
) -> dict:
    target = _to_decimal(target_price_gbp) or Decimal("0")
    return {
        "productType": str(product_type or "PRODUCT"),
        "patches": [
            {
                "op": "replace",
                "path": "/attributes/purchasable_offer",
                "value": [
                    {
                        "currency": currency,
                        "marketplace_id": marketplace_id,
                        "our_price": [{"schedule": [{"value_with_tax": float(_money(target))}]}],
                    }
                ],
            }
        ],
    }


def patch_listings_item_price(
    *,
    access_token: str,
    seller_id: str,
    sku: str,
    marketplace_id: str,
    product_type: str,
    target_price_gbp: object,
    currency: str = "GBP",
    run_id: str,
    source_script: str = "phase1_write_verify",
    spapi_base_url: str = SPAPI_BASE_URL,
    sender: Callable[..., object] = spapi_patch_json,
) -> dict[str, str]:
    body_obj = build_patch_listings_item_body(
        product_type=product_type,
        marketplace_id=marketplace_id,
        target_price_gbp=target_price_gbp,
        currency=currency,
    )
    body = json.dumps(body_obj, ensure_ascii=True, separators=(",", ":"))
    url = f"{spapi_base_url}/listings/2021-08-01/items/{seller_id}/{sku}"
    params = {"marketplaceIds": marketplace_id}
    headers = {
        "x-amz-access-token": access_token,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    ctx = SpApiCallContext(
        run_id=run_id,
        script_name=source_script,
        endpoint="listings_items_patch_item",
        marketplace=marketplace_id,
        sku_count=1,
    )
    response = sender(
        ctx=ctx,
        url=url,
        spapi_base_url=spapi_base_url,
        headers=headers,
        params=params,
        body=body,
        timeout=30,
        min_interval_sec=1.0,
        max_retries=2,
    )
    payload = {}
    try:
        payload = response.json() or {}
    except Exception:
        payload = {}
    return {
        "ok": "1" if int(getattr(response, "status_code", 0)) in (200, 202) else "0",
        "http_status": str(getattr(response, "status_code", "")),
        "submission_id": str(payload.get("submissionId", "") or ""),
        "response_text": str(getattr(response, "text", "") or ""),
    }


def _extract_snapshot_our_price(snapshot_rows: Iterable[Mapping[str, object]]) -> Decimal | None:
    for row in snapshot_rows:
        if str(row.get("is_our_offer", "")).strip() != "1":
            continue
        landed = _to_decimal(row.get("landed_price_gbp"))
        if landed is not None:
            return landed
        listing = _to_decimal(row.get("listing_price_gbp"))
        if listing is not None:
            return listing
    return None


def _verify_applied_price(
    *,
    intended_price_gbp: Decimal,
    tolerance_gbp: Decimal,
    listings_observed_price_gbp: object,
    snapshot_rows: Iterable[Mapping[str, object]],
) -> tuple[bool, str, Decimal | None]:
    primary = _to_decimal(listings_observed_price_gbp)
    if primary is not None:
        if abs(primary - intended_price_gbp) <= tolerance_gbp:
            return True, "LISTINGS_ITEMS", primary
    fallback = _extract_snapshot_our_price(snapshot_rows)
    if fallback is not None:
        if abs(fallback - intended_price_gbp) <= tolerance_gbp:
            return True, "SNAPSHOT_FALLBACK", fallback
    return False, "NONE", primary if primary is not None else fallback


def execute_write_verify_and_start_probe(
    *,
    sku: str,
    state_at_start: str,
    proposed_price_gbp: object,
    hard_floor_gbp: object,
    price_apply_tolerance_gbp: object,
    start_snapshot_id: str,
    start_featured_seller_id: str,
    market_structure_hash_start: str,
    listings_observed_price_gbp: object,
    latest_snapshot_rows: Iterable[Mapping[str, object]],
    write_submitter: Callable[[str], Mapping[str, object]],
    post_write_observed_price_lookup: Callable[[], object] | None = None,
    storage_append: Callable[[str, Iterable[dict[str, object]]], None] = phase1_storage.append,
    post_write_settle_minutes: float = 0.0,
    post_write_verify_attempts: int = 3,
    post_write_verify_sleep_seconds: float = 2.0,
    sleep_fn: Callable[[float], None] = time.sleep,
    now_utc: str | None = None,
) -> WriteVerifyResult:
    reason_codes: list[str] = []
    now = str(now_utc or _utc_now())
    proposed = _to_decimal(proposed_price_gbp) or Decimal("0")
    floor = _to_decimal(hard_floor_gbp) or Decimal("0")
    tolerance = _to_decimal(price_apply_tolerance_gbp) or Decimal("0.01")

    submitted = proposed
    if submitted < floor:
        submitted = floor
        reason_codes.append("GUARDRAIL_HARD_FLOOR_CLAMP")

    write_result = write_submitter(_money(submitted))
    write_ok = str(write_result.get("ok", "0")).strip() == "1"
    http_status = str(write_result.get("http_status", "") or "")
    submission_id = str(write_result.get("submission_id", "") or "")
    write_error = str(write_result.get("response_text", "") or "")

    if not write_ok:
        return WriteVerifyResult(
            write_status="WRITE_REJECTED",
            write_error=write_error,
            intended_price_gbp=_money(proposed),
            submitted_price_gbp=_money(submitted),
            observed_price_gbp="",
            verification_source="NONE",
            probe_started=False,
            probe_id="",
            http_status=http_status,
            submission_id=submission_id,
            reason_codes=reason_codes,
        )

    if post_write_settle_minutes > 0:
        sleep_fn(float(post_write_settle_minutes) * 60.0)

    observed_lookup_price = listings_observed_price_gbp
    lookup_attempts = max(int(post_write_verify_attempts), 1)
    for attempt_idx in range(lookup_attempts):
        if post_write_observed_price_lookup is not None:
            try:
                refreshed = post_write_observed_price_lookup()
            except Exception:
                refreshed = ""
            if _to_decimal(refreshed) is not None:
                observed_lookup_price = refreshed
        applied, verification_source, observed = _verify_applied_price(
            intended_price_gbp=submitted,
            tolerance_gbp=tolerance,
            listings_observed_price_gbp=observed_lookup_price,
            snapshot_rows=latest_snapshot_rows,
        )
        if applied:
            break
        if attempt_idx + 1 < lookup_attempts:
            sleep_seconds = max(float(post_write_verify_sleep_seconds), 0.0)
            if sleep_seconds > 0:
                sleep_fn(sleep_seconds)

    if not applied:
        return WriteVerifyResult(
            write_status="WRITE_NOT_APPLIED",
            write_error="WRITE_NOT_APPLIED",
            intended_price_gbp=_money(proposed),
            submitted_price_gbp=_money(submitted),
            observed_price_gbp=_money(observed),
            verification_source=verification_source,
            probe_started=False,
            probe_id="",
            http_status=http_status,
            submission_id=submission_id,
            reason_codes=reason_codes,
        )

    probe_id = str(uuid.uuid4())
    storage_append(
        "probe_windows",
        [
            {
                "probe_id": probe_id,
                "sku": sku,
                "state_at_start": state_at_start,
                "start_ts_utc": now,
                "start_snapshot_id": start_snapshot_id,
                "start_featured_seller_id": start_featured_seller_id,
                "market_structure_hash_start": market_structure_hash_start,
                "oas_result": "PENDING",
            }
        ],
    )
    return WriteVerifyResult(
        write_status="APPLIED",
        write_error="",
        intended_price_gbp=_money(proposed),
        submitted_price_gbp=_money(submitted),
        observed_price_gbp=_money(observed),
        verification_source=verification_source,
        probe_started=True,
        probe_id=probe_id,
        http_status=http_status,
        submission_id=submission_id,
        reason_codes=reason_codes,
    )

