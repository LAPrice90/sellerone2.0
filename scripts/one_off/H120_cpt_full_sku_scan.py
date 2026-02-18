from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
import time

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.api.get_financial_events import get_lwa_access_token, load_dotenv_if_missing
    from scripts.api.spapi_owner import SpApiCallContext, spapi_post_json
except ModuleNotFoundError:
    from api.get_financial_events import get_lwa_access_token, load_dotenv_if_missing
    from api.spapi_owner import SpApiCallContext, spapi_post_json


OUT = ROOT / "out"
PRODUCT_DB_PATH = OUT / "product_db_preview.csv"
DEFAULT_MARKETPLACE_ID = "A1F83G8C2ARO7P"
SOURCE = "H120_cpt_full_sku_scan"
SPAPI_BASE_URL = "https://sellingpartnerapi-eu.amazon.com"
DEFAULT_COMP_SUMMARY_SLEEP_SEC = float(os.environ.get("SPAPI_COMP_SUMMARY_SLEEP_SEC", "31.0"))


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _norm(value: object) -> str:
    return str(value or "").strip()


def _to_float(value: object) -> float | None:
    try:
        raw = _norm(value)
        if not raw:
            return None
        return float(raw)
    except Exception:
        return None


def _fmt2(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.2f}"


def _price_reference(row: dict[str, object]) -> tuple[float | None, str]:
    live = _to_float(row.get("live_listing_price", ""))
    if live is not None:
        return live, "live_listing_price"
    sold = _to_float(row.get("last_sold_price", ""))
    if sold is not None:
        return sold, "last_sold_price"
    return None, ""


def _build_merchant_price_maps() -> tuple[dict[str, float], dict[str, float]]:
    sku_map: dict[str, float] = {}
    asin_map: dict[str, float] = {}
    path = OUT / "merchant_listings_latest.csv"
    if not path.exists():
        return sku_map, asin_map
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return sku_map, asin_map
    sku_col = "seller-sku" if "seller-sku" in df.columns else ("seller_sku" if "seller_sku" in df.columns else "")
    asin_col = "asin1" if "asin1" in df.columns else ("asin" if "asin" in df.columns else "")
    price_col = "price" if "price" in df.columns else ""
    if not price_col:
        return sku_map, asin_map
    for _, row in df.iterrows():
        price = _to_float(row.get(price_col, ""))
        if price is None:
            continue
        sku = _norm(row.get(sku_col, "")).upper() if sku_col else ""
        asin = _norm(row.get(asin_col, "")).upper() if asin_col else ""
        if sku and sku not in sku_map:
            sku_map[sku] = float(price)
        if asin and asin not in asin_map:
            asin_map[asin] = float(price)
    return sku_map, asin_map


def _build_avg_sold_price_maps() -> tuple[dict[str, float], dict[str, float]]:
    sku_map: dict[str, float] = {}
    asin_map: dict[str, float] = {}
    path = OUT / "order_items_all.csv"
    if not path.exists():
        return sku_map, asin_map
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return sku_map, asin_map
    if "item_price_amount" not in df.columns:
        return sku_map, asin_map
    df["price_num"] = pd.to_numeric(df["item_price_amount"], errors="coerce")
    df = df[df["price_num"].notna() & (df["price_num"] > 0)].copy()
    if df.empty:
        return sku_map, asin_map
    if "seller_sku" in df.columns:
        g = df.groupby(df["seller_sku"].astype(str).str.strip().str.upper())["price_num"].mean()
        sku_map = {str(k): float(v) for k, v in g.items() if str(k).strip()}
    if "asin" in df.columns:
        g = df.groupby(df["asin"].astype(str).str.strip().str.upper())["price_num"].mean()
        asin_map = {str(k): float(v) for k, v in g.items() if str(k).strip()}
    return sku_map, asin_map


def _group_ab(cpt_gbp: float | None, reference_gbp: float | None) -> str:
    if cpt_gbp is None or reference_gbp is None:
        return "UNKNOWN"
    if cpt_gbp >= reference_gbp:
        return "A"
    return "B"


def _chunked(values: list[str], size: int) -> list[list[str]]:
    out: list[list[str]] = []
    buf: list[str] = []
    for value in values:
        buf.append(value)
        if len(buf) >= size:
            out.append(buf)
            buf = []
    if buf:
        out.append(buf)
    return out


def _status_code_from_resp(resp: dict[str, object]) -> int | None:
    status = resp.get("status") if isinstance(resp, dict) else None
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


def _extract_reference_prices(body: dict[str, object]) -> list[dict[str, object]]:
    if isinstance(body.get("referencePrices"), list):
        return [x for x in body.get("referencePrices", []) if isinstance(x, dict)]
    summaries = body.get("summaries")
    if isinstance(summaries, list) and summaries and isinstance(summaries[0], dict):
        ref = summaries[0].get("referencePrices")
        if isinstance(ref, list):
            return [x for x in ref if isinstance(x, dict)]
    return []


def _extract_cpt_from_body(body: dict[str, object]) -> tuple[str, float | None]:
    for ref in _extract_reference_prices(body):
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


def _fetch_cpt_batch(
    *,
    asins: list[str],
    marketplace_id: str,
    run_id: str,
    token: str,
    batch_idx: int,
) -> dict[str, dict[str, object]]:
    now_utc = _now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
    body_obj = {
        "requests": [
            {
                "method": "GET",
                "uri": "/products/pricing/2022-05-01/items/competitiveSummary",
                "asin": asin,
                "marketplaceId": marketplace_id,
                "includedData": ["referencePrices"],
            }
            for asin in asins
        ]
    }
    headers = {
        "x-amz-access-token": token,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    ctx = SpApiCallContext(
        run_id=run_id,
        script_name=SOURCE,
        endpoint="products_pricing_post_competitive_summary_batch",
        marketplace=marketplace_id,
        sku_count=len(asins),
    )
    resp = spapi_post_json(
        ctx=ctx,
        url=f"{SPAPI_BASE_URL}/batches/products/pricing/2022-05-01/items/competitiveSummary",
        spapi_base_url=SPAPI_BASE_URL,
        headers=headers,
        body=json.dumps(body_obj, ensure_ascii=True, separators=(",", ":")),
        timeout=90,
        min_interval_sec=1.0,
        max_retries=2,
    )
    out: dict[str, dict[str, object]] = {}
    if int(resp.status_code) != 200:
        summary = f"http_{resp.status_code}"
        try:
            payload = resp.json() or {}
            if isinstance(payload, dict):
                msg = str(payload.get("message") or "").strip()
                if msg:
                    summary = f"{summary}:{msg}"[:200]
        except Exception:
            raw = (resp.text or "").strip()
            if raw:
                summary = f"{summary}:{raw[:180]}"[:200]
        for asin in asins:
            out[asin] = {
                "cpt_gbp": "",
                "cpt_status": "ERROR",
                "cpt_last_refresh_utc": now_utc,
                "error_summary": summary,
                "batch_idx": str(batch_idx),
            }
        return out

    payload = resp.json() or {}
    responses = payload.get("responses") if isinstance(payload, dict) else []
    by_asin: dict[str, dict[str, object]] = {}
    if isinstance(responses, list):
        for item in responses:
            if not isinstance(item, dict):
                continue
            body = item.get("body") if isinstance(item.get("body"), dict) else {}
            asin = _norm(body.get("asin", "")).upper()
            if not asin:
                continue
            status_code = _status_code_from_resp(item)
            if status_code is None or status_code < 200 or status_code >= 300:
                err = _extract_batch_error_summary(item)
                summary = f"batch_status_{status_code if status_code is not None else 'unknown'}"
                if err:
                    summary = f"{summary}:{err}"[:200]
                by_asin[asin] = {
                    "cpt_gbp": "",
                    "cpt_status": "ERROR",
                    "cpt_last_refresh_utc": now_utc,
                    "error_summary": summary,
                    "batch_idx": str(batch_idx),
                }
                continue
            status, cpt_amount = _extract_cpt_from_body(body)
            if status == "OK" and cpt_amount is not None:
                by_asin[asin] = {
                    "cpt_gbp": f"{cpt_amount:.2f}",
                    "cpt_status": "OK",
                    "cpt_last_refresh_utc": now_utc,
                    "error_summary": "",
                    "batch_idx": str(batch_idx),
                }
            else:
                by_asin[asin] = {
                    "cpt_gbp": "",
                    "cpt_status": "MISSING",
                    "cpt_last_refresh_utc": now_utc,
                    "error_summary": "",
                    "batch_idx": str(batch_idx),
                }
    for asin in asins:
        if asin not in by_asin:
            by_asin[asin] = {
                "cpt_gbp": "",
                "cpt_status": "MISSING",
                "cpt_last_refresh_utc": now_utc,
                "error_summary": "batch_response_missing_asin",
                "batch_idx": str(batch_idx),
            }
    return by_asin


def main() -> int:
    parser = argparse.ArgumentParser(description="H120 - One-off CPT scan for all Product_DB SKUs/ASINs")
    parser.add_argument("--product-db", default=str(PRODUCT_DB_PATH), help="Path to local Product_DB preview csv")
    parser.add_argument("--marketplace-id", default=DEFAULT_MARKETPLACE_ID, help="SP-API marketplace id")
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=DEFAULT_COMP_SUMMARY_SLEEP_SEC,
        help="Delay between batch CPT calls to reduce throttle pressure",
    )
    parser.add_argument("--batch-size", type=int, default=20, help="ASINs per batch request (max 20)")
    parser.add_argument(
        "--max-unique-asins",
        type=int,
        default=0,
        help="Optional cap for debugging. 0 means no cap.",
    )
    args = parser.parse_args()

    product_db_path = Path(args.product_db)
    if not product_db_path.is_absolute():
        product_db_path = ROOT / product_db_path
    if not product_db_path.exists():
        raise SystemExit(f"[H120] product db not found: {product_db_path}")

    df = pd.read_csv(product_db_path, dtype=str).fillna("")
    if "seller_sku" not in df.columns or "asin" not in df.columns:
        raise SystemExit("[H120] product db missing required columns: seller_sku, asin")

    for col in ["cpt_gbp", "cpt_status", "cpt_last_refresh_utc", "cpt_error_summary"]:
        if col not in df.columns:
            df[col] = ""

    asin_order: list[str] = []
    seen: set[str] = set()
    for asin in df["asin"].astype(str).str.strip():
        asin_key = asin.upper()
        if not asin_key or asin_key in seen:
            continue
        seen.add(asin_key)
        asin_order.append(asin_key)

    if args.max_unique_asins > 0:
        asin_order = asin_order[: int(args.max_unique_asins)]

    run_id = _now_utc().strftime("%Y%m%dT%H%M%SZ")
    asof_utc = _now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
    merchant_price_by_sku, merchant_price_by_asin = _build_merchant_price_maps()
    avg_sold_by_sku, avg_sold_by_asin = _build_avg_sold_price_maps()
    result_by_asin: dict[str, dict[str, object]] = {}
    load_dotenv_if_missing()
    token = get_lwa_access_token()
    batch_size = max(1, min(int(args.batch_size), 20))
    asin_batches = _chunked(asin_order, batch_size)

    for idx, batch in enumerate(asin_batches, start=1):
        batch_payload = _fetch_cpt_batch(
            asins=batch,
            marketplace_id=_norm(args.marketplace_id),
            run_id=run_id,
            token=token,
            batch_idx=idx,
        )
        result_by_asin.update(batch_payload)
        if idx < len(asin_batches):
            time.sleep(max(float(args.sleep_seconds), 0.0))

    enriched_rows: list[dict[str, str]] = []
    for ridx, row in df.iterrows():
        rec = {k: _norm(v) for k, v in row.to_dict().items()}
        sku = _norm(rec.get("seller_sku", "")).upper()
        asin = _norm(rec.get("asin", "")).upper()
        payload = result_by_asin.get(asin, {})
        cpt_status = _norm(payload.get("cpt_status", "")) if asin else ""
        cpt_gbp_text = _norm(payload.get("cpt_gbp", "")) if asin else ""
        cpt_last = _norm(payload.get("cpt_last_refresh_utc", asof_utc)) if asin else ""
        cpt_err = _norm(payload.get("error_summary", "")) if asin else ""

        # Persist CPT back into local Product_DB preview.
        df.at[ridx, "cpt_status"] = cpt_status
        df.at[ridx, "cpt_gbp"] = cpt_gbp_text
        df.at[ridx, "cpt_last_refresh_utc"] = cpt_last
        df.at[ridx, "cpt_error_summary"] = cpt_err

        direct_live = _to_float(rec.get("live_listing_price", ""))
        direct_sold = _to_float(rec.get("last_sold_price", ""))
        merchant_live = merchant_price_by_sku.get(sku)
        if merchant_live is None:
            merchant_live = merchant_price_by_asin.get(asin)
        avg_sold = avg_sold_by_sku.get(sku)
        if avg_sold is None:
            avg_sold = avg_sold_by_asin.get(asin)

        our_listing_price = direct_live if direct_live is not None else merchant_live
        if avg_sold is not None:
            ref_gbp, ref_source = avg_sold, "avg_sold_price"
        elif our_listing_price is not None:
            ref_gbp, ref_source = our_listing_price, "our_listing_price"
        else:
            ref_gbp, ref_source = _price_reference(rec)
        cpt_gbp = _to_float(cpt_gbp_text)
        delta = None if cpt_gbp is None or ref_gbp is None else (cpt_gbp - ref_gbp)
        group = _group_ab(cpt_gbp, ref_gbp)

        enriched_rows.append(
            {
                "asof_utc": asof_utc,
                "seller_sku": sku,
                "asin": asin,
                "cpt_status": cpt_status,
                "cpt_gbp": _fmt2(cpt_gbp),
                "our_live_price_gbp": _fmt2(our_listing_price),
                "last_sold_price_gbp": _fmt2(avg_sold),
                "price_reference_gbp": _fmt2(ref_gbp),
                "price_reference_source": ref_source,
                "delta_cpt_minus_reference_gbp": _fmt2(delta),
                "group_ab": group,
                "cpt_error_summary": cpt_err,
            }
        )

    # Persist CPT columns into local Product_DB preview.
    df.to_csv(product_db_path, index=False)

    export_name = f"cpt_vs_our_price_{run_id}.csv"
    export_path = OUT / export_name
    pd.DataFrame(enriched_rows, dtype=str).to_csv(export_path, index=False)

    total_rows = len(enriched_rows)
    with_asin = int(sum(1 for r in enriched_rows if _norm(r.get("asin", ""))))
    ok_rows = int(sum(1 for r in enriched_rows if _norm(r.get("cpt_status", "")).upper() == "OK"))
    group_a = int(sum(1 for r in enriched_rows if _norm(r.get("group_ab", "")) == "A"))
    group_b = int(sum(1 for r in enriched_rows if _norm(r.get("group_ab", "")) == "B"))
    group_unknown = int(sum(1 for r in enriched_rows if _norm(r.get("group_ab", "")) == "UNKNOWN"))

    print(f"h120_product_db={product_db_path}")
    print(f"h120_export={export_path}")
    print(f"h120_total_rows={total_rows}")
    print(f"h120_rows_with_asin={with_asin}")
    print(f"h120_unique_asins_scanned={len(asin_order)}")
    print(f"h120_batch_size={batch_size}")
    print(f"h120_batches_sent={len(asin_batches)}")
    print(f"h120_cpt_ok_rows={ok_rows}")
    print(f"h120_group_A={group_a}")
    print(f"h120_group_B={group_b}")
    print(f"h120_group_UNKNOWN={group_unknown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
