from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import phase1_main_loop, phase1_storage  # noqa: E402
from scripts.api.get_financial_events import get_lwa_access_token, load_dotenv_if_missing  # noqa: E402
from scripts.h_floor_policy import load_h_floor_vat_policy  # noqa: E402
from scripts.h_floor_truth import (  # noqa: E402
    HFloorContext,
    append_h_floor_trace_rows,
    build_h_floor_trace_row,
    compute_h_floor_for_sku,
    has_blocking_reason_codes,
    load_h_floor_context,
)
from scripts.phase1_target_universe import resolve_target_universe  # noqa: E402
from scripts.phase1_write_verify import patch_listings_item_price  # noqa: E402

SOURCE = "H110_run_phase1_h_pilot"
SPAPI_BASE_URL = os.environ.get("SPAPI_BASE_URL", "https://sellingpartnerapi-eu.amazon.com")
MARKETPLACE_CODE_TO_ID = {"UK": "A1F83G8C2ARO7P"}
SKU_SCAN_STATE_PATH = OUT / "phase1_sku_scan_state.json"
MANUAL_CAPS_PATH = ROOT / "config" / "phase1_manual_max_caps.csv"
PRODUCT_DB_PATH = OUT / "product_db_preview.csv"
TOKEN_COGS_LEDGER_PATH = OUT / "token_cogs_ledger.csv"
TOKEN_LEDGER_PATH = OUT / "token_ledger_live.csv"
TEMP_FLOOR_SNAPSHOT_PATH = OUT / "sku_temp_floor_snapshot.csv"
MIN_REFERRAL_FEE_GBP = 0.25
# Terminology: "commission" in this repricer equals Amazon referral fee.
ALLOWED_WRITER_MODES = {"PPP", "CODEX_H", "READ_ONLY"}
H_FLOOR_VAT_POLICY = load_h_floor_vat_policy()


def _norm(value: object) -> str:
    return str(value or "").strip()


def _to_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _to_float(value: object) -> float | None:
    try:
        raw = _norm(value)
        if not raw:
            return None
        out = float(raw)
        if not math.isfinite(out):
            return None
        return out
    except Exception:
        return None


def _resolve_vat_rate(row: pd.Series, fee_row: dict[str, str]) -> float:
    # Repricer VAT must be based on product/market VAT rates, not settlement withheld flags.
    vat_raw = _to_float(fee_row.get("last_vat_rate_pct", ""))
    if vat_raw is None:
        vat_raw = _to_float(fee_row.get("vat_rate", ""))
    if vat_raw is not None:
        if vat_raw > 1:
            vat_raw = vat_raw / 100.0
        if vat_raw < 0:
            vat_raw = 0.0
        return vat_raw

    price_ex = _to_float(row.get("Price_ExVAT_num", ""))
    price_vat = _to_float(row.get("Price_VAT_num", ""))
    if price_ex is not None and price_ex > 0 and price_vat is not None:
        candidate = abs(price_vat) / abs(price_ex)
        if candidate >= 0:
            return candidate
    return 0.2


def _to_int(value: object) -> int | None:
    try:
        raw = _norm(value)
        if not raw:
            return None
        return int(float(raw))
    except Exception:
        return None


def _round_half_up(value: float, ndigits: int = 2) -> float:
    q = Decimal("1").scaleb(-ndigits)
    return float(Decimal(str(value)).quantize(q, rounding=ROUND_HALF_UP))


def _append_temp_floor_snapshot(rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    headers = [
        "asof_utc",
        "sku",
        "order_id",
        "order_date_utc",
        "candidate_price_gbp",
        "vat_rate_market",
        "cogs_total_gbp",
        "fba_total_gbp",
        "commission_total_gbp",
        "digital_fee_total_gbp",
        "fixed_total_gbp",
        "break_even_total_gbp",
        "temp_floor_10roi_gbp",
        "source_script",
    ]
    TEMP_FLOOR_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    exists = TEMP_FLOOR_SNAPSHOT_PATH.exists()
    with TEMP_FLOOR_SNAPSHOT_PATH.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({k: _norm(row.get(k, "")) for k in headers})


def _to_dt(value: object) -> datetime | None:
    text = _norm(value)
    if not text:
        return None
    try:
        raw = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _parse_scalar(text: str) -> object:
    raw = str(text).strip()
    if raw == "":
        return ""
    low = raw.lower()
    if low in {"true", "yes", "on"}:
        return True
    if low in {"false", "no", "off"}:
        return False
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except Exception:
        return raw.strip("\"'")


def _simple_yaml_load(path: Path) -> dict:
    root: dict[str, object] = {}
    stack: list[tuple[int, dict[str, object]]] = [(-1, root)]
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        text = line.strip()
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if ":" not in text:
            continue
        key, value = text.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            child: dict[str, object] = {}
            parent[key] = child
            stack.append((indent, child))
            continue
        parent[key] = _parse_scalar(value)
    return root


def _cfg_get(cfg: dict, *keys: str, default: object = "") -> object:
    cur: object = cfg
    for key in keys:
        if not isinstance(cur, dict):
            return default
        if key not in cur:
            return default
        cur = cur[key]
    return cur


def _cfg_sku_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip().upper() for v in value if str(v).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    if "," in text:
        return [part.strip().upper() for part in text.split(",") if part.strip()]
    return [text.upper()]


def _to_num_text(value: object, default: str) -> str:
    text = str(value or "").strip()
    return text if text else default


def _is_truthy_text(value: object) -> bool:
    text = _norm(value).lower()
    return text in {"1", "true", "yes", "y", "on"}


def _is_in_stock_listing_row(row: dict[str, str]) -> bool:
    # Use the same listing snapshot signal the repricer already relies on.
    # If our offer is present (or we have a positive current price), treat as in stock.
    if _is_truthy_text(row.get("we_present_flag", "")):
        return True
    our_price = _to_float(row.get("our_price", ""))
    return our_price is not None and our_price > 0


def _read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return payload if isinstance(payload, dict) else default


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _latest_listing_snapshot() -> Path:
    files = sorted(OUT.glob("listing_offer_snapshot_*.csv"))
    if not files:
        raise RuntimeError("No listing snapshot found in out/")
    return files[-1]


def _latest_seller_snapshot() -> Path:
    files = sorted(OUT.glob("listing_offer_seller_snapshot_*.csv"))
    if not files:
        raise RuntimeError("No seller snapshot found in out/")
    return files[-1]


def _latest_listing_row_for_sku(sku: str) -> dict[str, str]:
    path = _latest_listing_snapshot()
    df = pd.read_csv(path, dtype=str).fillna("")
    sku_col = df.get("sku", "").astype(str).str.strip().str.upper()
    one = df.loc[sku_col.eq(sku.upper())]
    if one.empty:
        raise RuntimeError(f"pilot SKU missing from listing snapshot: {path.name}")
    return {k: _norm(v) for k, v in one.iloc[0].to_dict().items()}


def _load_manual_caps() -> tuple[dict[str, str], dict[str, str]]:
    by_sku: dict[str, str] = {}
    by_asin: dict[str, str] = {}
    if not MANUAL_CAPS_PATH.exists():
        return by_sku, by_asin
    try:
        df = pd.read_csv(MANUAL_CAPS_PATH, dtype=str).fillna("")
    except Exception:
        return by_sku, by_asin
    for _, row in df.iterrows():
        cap_raw = _norm(row.get("manual_max_price_gbp", ""))
        cap_val = _to_float(cap_raw)
        if cap_val is None or cap_val <= 0:
            continue
        cap_text = f"{cap_val:.2f}"
        sku_key = _norm(row.get("sku", "")).upper()
        asin_key = _norm(row.get("asin", "")).upper()
        if sku_key and sku_key not in by_sku:
            by_sku[sku_key] = cap_text
        if asin_key and asin_key not in by_asin:
            by_asin[asin_key] = cap_text
    return by_sku, by_asin


def _load_temp_floor_by_sku() -> tuple[dict[str, str], dict[str, str]]:
    floor_by_sku: dict[str, str] = {}
    blocked_by_sku: dict[str, str] = {}
    snapshot_rows: list[dict[str, str]] = []
    trace_rows: list[dict[str, str]] = []
    asof_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        context = load_h_floor_context(
            product_db_path=PRODUCT_DB_PATH,
            token_ledger_path=TOKEN_LEDGER_PATH,
            token_cogs_path=TOKEN_COGS_LEDGER_PATH,
        )
    except Exception:
        context = HFloorContext(product_db_rows={}, token_cogs_by_sku={}, vat_policy=load_h_floor_vat_policy())

    for sku_key, row in context.product_db_rows.items():
        if not sku_key:
            continue
        candidate_price = _to_float(row.get("live_listing_price", ""))
        if candidate_price is None or candidate_price <= 0:
            candidate_price = _to_float(row.get("last_sold_price", ""))
        if candidate_price is None:
            candidate_price = 0.0

        inputs, result = compute_h_floor_for_sku(sku_key, candidate_price, context=context)
        blocking = has_blocking_reason_codes(inputs.reason_codes)
        floor_total = _round_half_up(result.floor_total_gbp, 2)
        if (not blocking) and floor_total > 0:
            floor_by_sku[sku_key] = f"{floor_total:.2f}"
        elif blocking:
            blocked_by_sku[sku_key] = ",".join(inputs.reason_codes)

        snapshot_rows.append(
            {
                "asof_utc": asof_utc,
                "sku": sku_key,
                "order_id": "",
                "order_date_utc": "",
                "candidate_price_gbp": f"{_round_half_up(inputs.candidate_price_gbp, 2):.2f}",
                "vat_rate_market": f"{inputs.vat_rate:.6f}",
                "cogs_total_gbp": f"{_round_half_up(inputs.cogs_exvat_gbp, 2):.2f}",
                "fba_total_gbp": f"{_round_half_up(inputs.fba_exvat_gbp, 2):.2f}",
                "commission_total_gbp": f"{_round_half_up(inputs.referral_amount_gbp, 2):.2f}",
                "digital_fee_total_gbp": f"{_round_half_up(inputs.digital_fee_exvat_gbp, 2):.2f}",
                "fixed_total_gbp": "0.00",
                "break_even_total_gbp": f"{_round_half_up(result.break_even_total_gbp, 2):.2f}",
                "temp_floor_10roi_gbp": f"{floor_total:.2f}" if (not blocking and floor_total > 0) else "",
                "source_script": SOURCE,
            }
        )
        trace_rows.append(
            build_h_floor_trace_row(
                inputs=inputs,
                result=result,
                source_script=SOURCE,
                asof_utc=asof_utc,
            )
        )

    _append_temp_floor_snapshot(snapshot_rows)
    append_h_floor_trace_rows(trace_rows)
    return floor_by_sku, blocked_by_sku


def _resolve_marketplace_id(listing_row: dict[str, str], cfg_marketplace_id: str) -> str:
    explicit = _norm(cfg_marketplace_id) or _norm(listing_row.get("marketplace_id", ""))
    if explicit:
        return explicit
    code = _norm(listing_row.get("marketplace", "")).upper()
    mapped = MARKETPLACE_CODE_TO_ID.get(code, "")
    if mapped:
        return mapped
    return os.environ.get("MARKETPLACE_ID", "A1F83G8C2ARO7P")


def _phase1_market_payload_from_snapshots(
    *,
    sku: str,
    asin: str,
    marketplace_id: str,
    our_seller_id: str,
) -> tuple[dict[str, object], str]:
    listing_row = _latest_listing_row_for_sku(sku)
    seller_path = _latest_seller_snapshot()
    df = pd.read_csv(seller_path, dtype=str).fillna("")
    scoped = df.loc[df.get("sku", "").astype(str).str.strip().str.upper().eq(sku.upper())].copy()
    offers: list[dict[str, object]] = []
    for _, rec in scoped.iterrows():
        seller_id = _norm(rec.get("seller_id", ""))
        if not seller_id:
            continue
        listing_price = _to_float(rec.get("offer_price_gbp", ""))
        shipping_price = _to_float(rec.get("offer_shipping_price_gbp", ""))
        landed_price = _to_float(rec.get("offer_landed_price_gbp", ""))
        if listing_price is None and landed_price is not None and shipping_price is not None:
            listing_price = landed_price - shipping_price
        listing_price = listing_price if listing_price is not None else 0.0
        shipping_price = shipping_price if shipping_price is not None else 0.0
        min_days = _to_int(rec.get("min_delivery_days", ""))
        max_days = _to_int(rec.get("max_delivery_days", ""))
        fulf = _norm(rec.get("fulfilment_channel", "")).upper()
        offers.append(
            {
                "SellerId": seller_id,
                "ListingPrice": {"Amount": listing_price},
                "Shipping": {"Amount": shipping_price},
                "ShippingTime": {"minimumDays": min_days or 0, "maximumDays": max_days or (min_days or 0)},
                "IsFulfilledByAmazon": fulf in {"FBA", "AFN", "AMAZON"},
                "IsPrime": _to_bool(rec.get("is_prime", "")),
                "IsFeaturedOfferWinner": False,
            }
        )

    our_price = _to_float(listing_row.get("our_price", ""))
    if our_price is not None and not any(_norm(o.get("SellerId", "")).upper() == our_seller_id.upper() for o in offers):
        offers.append(
            {
                "SellerId": our_seller_id,
                "ListingPrice": {"Amount": our_price},
                "Shipping": {"Amount": 0.0},
                "ShippingTime": {"minimumDays": 1, "maximumDays": 2},
                "IsFulfilledByAmazon": True,
                "IsPrime": True,
                "IsFeaturedOfferWinner": False,
            }
        )

    buy_box_price = _to_float(listing_row.get("buy_box_price", ""))
    if buy_box_price is not None and offers:
        winner_idx = None
        winner_gap = 999999.0
        for idx, offer in enumerate(offers):
            listing_amt = _to_float((offer.get("ListingPrice", {}) or {}).get("Amount"))
            shipping_amt = _to_float((offer.get("Shipping", {}) or {}).get("Amount"))
            landed = (listing_amt or 0.0) + (shipping_amt or 0.0)
            gap = abs(landed - buy_box_price)
            if gap < winner_gap:
                winner_gap = gap
                winner_idx = idx
        if winner_idx is not None and winner_gap <= 0.02:
            offers[winner_idx]["IsFeaturedOfferWinner"] = True

    payload = {"asin": asin, "marketplaceId": marketplace_id, "offers": offers}
    listings_observed_price = _to_num_text(listing_row.get("our_price", ""), "")
    return payload, listings_observed_price


def _seller_id_from_env() -> str:
    return (
        os.environ.get("SELLER_ID")
        or os.environ.get("SELLER_PARTNER_ID")
        or os.environ.get("MERCHANT_ID")
        or os.environ.get("SELLING_PARTNER_ID")
        or ""
    ).strip()


def _phase1_write_submitter(*, sku: str, marketplace_id: str, run_id: str):
    def _submit(target_price_gbp: str) -> dict[str, str]:
        try:
            load_dotenv_if_missing()
            access_token = get_lwa_access_token()
            seller_id = _seller_id_from_env()
            if not seller_id:
                raise RuntimeError("SELLER_ID missing from environment")
            result = patch_listings_item_price(
                access_token=access_token,
                seller_id=seller_id,
                sku=sku,
                marketplace_id=marketplace_id,
                product_type=os.environ.get("H_DEFAULT_PRODUCT_TYPE", "PRODUCT"),
                target_price_gbp=target_price_gbp,
                run_id=run_id,
                source_script=SOURCE,
                spapi_base_url=SPAPI_BASE_URL,
            )
            return {
                "ok": _norm(result.get("ok", "0")),
                "http_status": _norm(result.get("http_status", "")),
                "submission_id": _norm(result.get("submission_id", "")),
                "response_text": _norm(result.get("response_text", "")),
            }
        except Exception as exc:
            return {"ok": "0", "http_status": "", "submission_id": "", "response_text": str(exc)}

    return _submit


def _run_one_sku(
    *,
    cfg: dict,
    sku: str,
    read_only: bool,
    run_id: str,
    now_utc: datetime,
    manual_cap_by_sku: dict[str, str],
    manual_cap_by_asin: dict[str, str],
    temp_floor_by_sku: dict[str, str],
    temp_floor_blockers_by_sku: dict[str, str],
    daily_boundary_lock_by_sku: dict[str, dict[str, str]],
    boundary_lock_date_utc: str,
    live_allowlist: set[str] | None = None,
    force_live_for_sku: bool = False,
) -> dict[str, str]:
    sku = _norm(sku).upper()
    if not sku:
        raise RuntimeError("[H110] empty sku in run_one_sku")

    listing_row = _latest_listing_row_for_sku(sku)
    asin_override = _norm(_cfg_get(cfg, "asin", default="")).upper()
    asin = asin_override if asin_override and _norm(_cfg_get(cfg, "sku", default="")).upper() == sku else _norm(listing_row.get("asin", ""))
    marketplace_id = _resolve_marketplace_id(listing_row, _norm(_cfg_get(cfg, "marketplace_id", default="")))
    seller_id = _norm(_cfg_get(cfg, "seller_id", default="")) or _seller_id_from_env()
    if not seller_id:
        raise SystemExit("[H110] phase1 pilot config missing seller_id and no seller id found in environment")

    default_hard_floor = _to_num_text(_cfg_get(cfg, "boundaries", "hard_floor_gbp", default="0.00"), "0.00")
    default_manual_cap = _to_num_text(_cfg_get(cfg, "boundaries", "manual_cap_gbp", default="9999.99"), "9999.99")
    manual_cap_candidate = manual_cap_by_sku.get(sku) or manual_cap_by_asin.get(asin) or default_manual_cap
    temp_floor_resolved = temp_floor_by_sku.get(sku, "")
    floor_blockers_csv = _norm(temp_floor_blockers_by_sku.get(sku, ""))
    if temp_floor_resolved:
        temp_floor_num = _to_float(temp_floor_resolved) or 0.0
        hard_floor_candidate = f"{temp_floor_num:.2f}"
    else:
        hard_floor_candidate = default_hard_floor

    lock_entry = daily_boundary_lock_by_sku.get(sku)
    lock_hard_floor = _norm((lock_entry or {}).get("hard_floor_gbp", ""))
    lock_manual_cap = _norm((lock_entry or {}).get("manual_cap_gbp", ""))
    using_daily_lock = bool(lock_hard_floor and lock_manual_cap)
    if using_daily_lock:
        hard_floor_resolved = lock_hard_floor
        manual_cap_resolved = lock_manual_cap
    else:
        hard_floor_resolved = hard_floor_candidate
        manual_cap_resolved = manual_cap_candidate

    writer_mode = _norm(_cfg_get(cfg, "pricing_writer_mode", default="READ_ONLY")).upper()
    if writer_mode not in ALLOWED_WRITER_MODES:
        _ = phase1_main_loop.run_h_cycle(
            sku=sku,
            asin=asin,
            marketplace_id=marketplace_id,
            our_seller_id=seller_id,
            pricing_writer_mode=writer_mode,
            enabled_live_writes=False,
            current_price_gbp=_to_num_text(listing_row.get("our_price", ""), "0.00"),
            hard_floor_gbp=hard_floor_resolved,
            manual_cap_gbp=manual_cap_resolved,
            max_step_down_gbp="0.00",
            max_step_up_gbp="0.00",
            max_daily_drop_gbp="0.00",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=1,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload={"offers": []},
            now_utc=now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        raise SystemExit("[H110] WRITER_LOCK_BLOCK")

    today = now_utc.strftime("%Y-%m-%d")
    if floor_blockers_csv:
        latest_daily_after = phase1_storage.read_latest("sku_daily_intel", {"sku": sku}) or {}
        daily_missing = "1" if _norm(latest_daily_after.get("date_utc", "")) != today else "0"
        return {
            "phase1_pilot": "1",
            "phase1_sku": sku,
            "phase1_asin": asin,
            "daily_intel_missing_for_today": daily_missing,
            "last_executioner_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "executioner_ran_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "executioner_probe_type": "hold",
            "executioner_live_write_attempted": "0",
            "executioner_live_write_success": "0",
            "write_status": "FLOOR_INPUT_MISSING_HOLD",
            "writer_mode": writer_mode,
            "hard_floor_applied_gbp": "",
            "manual_cap_applied_gbp": manual_cap_resolved,
            "final_ceiling_landed_gbp": "",
            "reason_codes_csv": ",".join([floor_blockers_csv, "H_FLOOR_INPUT_BLOCKED_NO_WRITE"]).strip(","),
            "phase1_boundary_lock_mode": "reused" if using_daily_lock else "set_pending",
            "phase1_boundary_lock_date": boundary_lock_date_utc,
            "blocked_due_to_missing_intel": "0",
            "blocked_due_to_stale_intel": "0",
            "refresh_attempted_count": "0",
            "refresh_throttled_count": "0",
        }

    def _refresh_daily_intel_once() -> None:
        now_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        phase1_main_loop.run_a_cycle(
            sku=sku,
            now_utc=now_iso,
            compliance_anchor_gbp=_cfg_get(
                cfg,
                "daily_intel",
                "compliance_anchor_gbp",
                default=_cfg_get(cfg, "boundaries", "manual_cap_gbp", default=listing_row.get("our_price", "0.00")),
            ),
            policy_buffer_pct=_cfg_get(cfg, "boundaries", "policy_buffer_pct", default="0.03"),
            manual_cap_gbp=manual_cap_resolved,
            foep_price_gbp=_cfg_get(cfg, "daily_intel", "foep_price_gbp", default=listing_row.get("buy_box_price", "")),
            foep_status=_cfg_get(cfg, "daily_intel", "foep_status", default="MISSING"),
            foep_last_refresh_utc=_cfg_get(cfg, "daily_intel", "foep_last_refresh_utc", default=now_iso),
            cpt_gbp=_cfg_get(cfg, "daily_intel", "cpt_gbp", default=""),
            cpt_last_refresh_utc=_cfg_get(cfg, "daily_intel", "cpt_last_refresh_utc", default=now_iso),
            cpt_status=_cfg_get(cfg, "daily_intel", "cpt_status", default="MISSING"),
            last_known_safe_gbp=_cfg_get(cfg, "daily_intel", "last_known_safe_gbp", default=listing_row.get("our_price", "")),
            foep_stale_hours=int(float(_cfg_get(cfg, "eligibility", "foep_stale_hours", default=48))),
            foep_sanity_min_mult=_cfg_get(cfg, "eligibility", "foep_sanity_min_mult", default="0.50"),
            foep_sanity_max_mult=_cfg_get(cfg, "eligibility", "foep_sanity_max_mult", default="2.00"),
            market_reference_price_gbp=_cfg_get(cfg, "daily_intel", "market_reference_price_gbp", default=listing_row.get("buy_box_price", "")),
        )

    allow_intraday_intel_refresh = _to_bool(
        _cfg_get(cfg, "allow_h_intraday_intel_refresh", default=False),
        default=False,
    )

    payload, listings_observed_price = _phase1_market_payload_from_snapshots(
        sku=sku,
        asin=asin,
        marketplace_id=marketplace_id,
        our_seller_id=seller_id,
    )
    cfg_live = _to_bool(_cfg_get(cfg, "enabled_live_writes", default=False), default=False)
    allowlist = {s.upper() for s in (live_allowlist or set()) if _norm(s)}
    allowlist_enabled = bool(allowlist)
    allowlisted_sku = sku in allowlist
    effective_live = bool(
        writer_mode == "CODEX_H"
        and not read_only
        and cfg_live
        and (allowlisted_sku if allowlist_enabled else force_live_for_sku)
    )
    submitter = _phase1_write_submitter(sku=sku, marketplace_id=marketplace_id, run_id=run_id) if effective_live else None
    h_out = phase1_main_loop.run_h_cycle(
        sku=sku,
        asin=asin,
        marketplace_id=marketplace_id,
        our_seller_id=seller_id,
        pricing_writer_mode=writer_mode,
        enabled_live_writes=effective_live,
        current_price_gbp=_to_num_text(listing_row.get("our_price", ""), "0.00"),
        hard_floor_gbp=hard_floor_resolved,
        manual_cap_gbp=manual_cap_resolved,
        max_step_down_gbp=_cfg_get(cfg, "guardrails", "max_step_down_gbp", default="0.20"),
        max_step_up_gbp=_cfg_get(cfg, "guardrails", "max_step_up_gbp", default="0.20"),
        max_daily_drop_gbp=_cfg_get(cfg, "guardrails", "max_daily_drop_gbp", default="0.60"),
        daily_drop_used_gbp=_cfg_get(cfg, "guardrails", "daily_drop_used_gbp", default="0.00"),
        delta_tolerance_gbp=_cfg_get(cfg, "learning", "delta_tolerance_gbp", default="0.02"),
        stable_buffer_gbp=_cfg_get(cfg, "learning", "stable_buffer_gbp", default="0.02"),
        min_clean_tests_for_confidence=int(float(_cfg_get(cfg, "learning", "min_clean_tests_for_confidence", default=5))),
        price_apply_tolerance_gbp=_cfg_get(cfg, "guardrails", "price_apply_tolerance_gbp", default="0.01"),
        policy_buffer_pct=_cfg_get(cfg, "boundaries", "policy_buffer_pct", default="0.03"),
        market_payload=payload,
        listings_observed_price_gbp=listings_observed_price,
        write_submitter=submitter,
        now_utc=now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        daily_intel_refresher=_refresh_daily_intel_once if allow_intraday_intel_refresh else None,
    )
    if not using_daily_lock:
        daily_boundary_lock_by_sku[sku] = {
            "hard_floor_gbp": hard_floor_resolved,
            "manual_cap_gbp": manual_cap_resolved,
            "final_ceiling_landed_gbp": _norm(h_out.final_ceiling_landed_gbp),
            "locked_at_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    latest_daily_after = phase1_storage.read_latest("sku_daily_intel", {"sku": sku}) or {}
    daily_missing = "1" if _norm(latest_daily_after.get("date_utc", "")) != today else "0"

    return {
        "phase1_pilot": "1",
        "phase1_sku": sku,
        "phase1_asin": asin,
        "daily_intel_missing_for_today": daily_missing,
        "last_executioner_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "executioner_ran_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "executioner_probe_type": _norm(h_out.state),
        "executioner_live_write_attempted": "1" if effective_live else "0",
        "executioner_live_write_success": "1" if _norm(h_out.write_status) == "APPLIED" else "0",
        "write_status": _norm(h_out.write_status),
        "writer_mode": writer_mode,
        "hard_floor_applied_gbp": hard_floor_resolved,
        "manual_cap_applied_gbp": manual_cap_resolved,
        "final_ceiling_landed_gbp": _norm(h_out.final_ceiling_landed_gbp),
        "reason_codes_csv": ",".join(h_out.reason_codes),
        "phase1_boundary_lock_mode": "reused" if using_daily_lock else "set",
        "phase1_boundary_lock_date": boundary_lock_date_utc,
        "phase1_boundary_lock_final_ceiling_gbp": _norm((daily_boundary_lock_by_sku.get(sku) or {}).get("final_ceiling_landed_gbp", "")),
        "blocked_due_to_missing_intel": _norm(h_out.blocked_due_to_missing_intel),
        "blocked_due_to_stale_intel": _norm(h_out.blocked_due_to_stale_intel),
        "refresh_attempted_count": _norm(h_out.refresh_attempted_count),
        "refresh_throttled_count": _norm(h_out.refresh_throttled_count),
    }


def _run_once(*, cfg: dict, read_only: bool, run_id: str, now_utc: datetime) -> dict[str, str]:
    target_universe = resolve_target_universe(cfg, out_dir=OUT)
    target_skus = [s.upper() for s in (target_universe.get("skus") or []) if _norm(s)]
    if not target_skus:
        raise SystemExit("[H110] no target SKUs resolved from config or active cohort")

    scan_state = _read_json(SKU_SCAN_STATE_PATH, default={"last_scan_utc": {}, "daily_boundary_lock": {}})
    last_scan_utc = scan_state.get("last_scan_utc", {})
    if not isinstance(last_scan_utc, dict):
        last_scan_utc = {}
    today_utc = now_utc.strftime("%Y-%m-%d")
    boundary_lock = scan_state.get("daily_boundary_lock", {})
    if not isinstance(boundary_lock, dict):
        boundary_lock = {}
    if _norm(boundary_lock.get("date_utc", "")) != today_utc:
        boundary_lock = {"date_utc": today_utc, "by_sku": {}}
    boundary_lock_by_sku = boundary_lock.get("by_sku", {})
    if not isinstance(boundary_lock_by_sku, dict):
        boundary_lock_by_sku = {}

    cooldown_minutes = max(int(float(_cfg_get(cfg, "scan_cooldown_minutes", default=15))), 0)
    spacing_seconds = max(float(_cfg_get(cfg, "sku_call_spacing_seconds", default=2.0)), 0.0)
    max_skus_raw = float(_cfg_get(cfg, "max_skus_per_run", default=0) or 0)
    # max_skus_per_run <= 0 means "no cap": process all due in-stock SKUs.
    max_skus_per_run = int(max_skus_raw) if max_skus_raw > 0 else 0
    live_allowlist = set(
        s.upper()
        for s in _cfg_sku_list(_cfg_get(cfg, "live_sku_allowlist", default=""))
        if _norm(s)
    )
    now_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    manual_cap_by_sku, manual_cap_by_asin = _load_manual_caps()
    temp_floor_by_sku, temp_floor_blockers_by_sku = _load_temp_floor_by_sku()

    due_skus: list[str] = []
    skipped_cooldown: list[str] = []
    cooldown_wait_candidates: list[tuple[int, str]] = []
    skipped_out_of_stock: list[str] = []
    skipped_parked_count = int(_to_int(target_universe.get("skipped_parked_count", 0)) or 0)
    for sku in target_skus:
        try:
            listing_row = _latest_listing_row_for_sku(sku)
        except RuntimeError:
            continue
        if not _is_in_stock_listing_row(listing_row):
            skipped_out_of_stock.append(sku)
            continue
        last_dt = _to_dt(last_scan_utc.get(sku, ""))
        if last_dt is None:
            due_skus.append(sku)
            continue
        elapsed_seconds = max((now_utc - last_dt).total_seconds(), 0.0)
        if elapsed_seconds >= float(cooldown_minutes) * 60.0:
            due_skus.append(sku)
        else:
            skipped_cooldown.append(sku)
            remaining_seconds = max(int(math.ceil(float(cooldown_minutes) * 60.0 - elapsed_seconds)), 1)
            cooldown_wait_candidates.append((remaining_seconds, sku))

    if max_skus_per_run > 0:
        due_skus = due_skus[:max_skus_per_run]
    run_rows: list[dict[str, str]] = []
    for idx, sku in enumerate(due_skus):
        try:
            row = _run_one_sku(
                cfg=cfg,
                sku=sku,
                read_only=read_only,
                run_id=f"{run_id}_{idx+1:02d}",
                now_utc=now_utc,
                manual_cap_by_sku=manual_cap_by_sku,
                manual_cap_by_asin=manual_cap_by_asin,
                temp_floor_by_sku=temp_floor_by_sku,
                temp_floor_blockers_by_sku=temp_floor_blockers_by_sku,
                daily_boundary_lock_by_sku=boundary_lock_by_sku,
                boundary_lock_date_utc=today_utc,
                live_allowlist=live_allowlist,
                force_live_for_sku=(sku in live_allowlist),
            )
        except RuntimeError as exc:
            msg = str(exc)
            if "pilot SKU missing from listing snapshot" in msg:
                row = {
                    "phase1_pilot": "1",
                    "phase1_sku": sku,
                    "phase1_asin": "",
                    "daily_intel_missing_for_today": "0",
                    "last_executioner_utc": now_iso,
                    "executioner_ran_utc": "",
                    "executioner_probe_type": "SKIP_NO_LISTING_ROW",
                    "executioner_live_write_attempted": "0",
                    "executioner_live_write_success": "0",
                    "write_status": "SKIP_NO_LISTING_SNAPSHOT",
                    "writer_mode": _norm(_cfg_get(cfg, "pricing_writer_mode", default="READ_ONLY")).upper(),
                    "hard_floor_applied_gbp": "",
                    "manual_cap_applied_gbp": "",
                    "final_ceiling_landed_gbp": "",
                    "reason_codes_csv": "SKIP_NO_LISTING_SNAPSHOT",
                }
            else:
                raise
        run_rows.append(row)
        last_scan_utc[sku] = now_iso
        if idx < len(due_skus) - 1 and spacing_seconds > 0:
            time.sleep(spacing_seconds)

    scan_state["last_scan_utc"] = last_scan_utc
    scan_state["daily_boundary_lock"] = {
        "date_utc": today_utc,
        "by_sku": boundary_lock_by_sku,
    }
    _write_json(SKU_SCAN_STATE_PATH, scan_state)

    next_due_sleep_seconds = 0
    next_due_sku = ""
    if cooldown_wait_candidates:
        next_due_sleep_seconds, next_due_sku = min(cooldown_wait_candidates, key=lambda pair: pair[0])

    if not run_rows:
        return {
            "phase1_pilot": "1",
            "phase1_sku": "",
            "phase1_skus_processed_csv": "",
            "phase1_skus_processed_count": "0",
            "phase1_skus_skipped_cooldown_count": str(len(skipped_cooldown)),
            "phase1_skus_skipped_parked_count": str(skipped_parked_count),
            "phase1_skus_skipped_out_of_stock_count": str(len(skipped_out_of_stock)),
            "phase1_scan_cooldown_minutes": str(cooldown_minutes),
            "phase1_next_due_sleep_seconds": str(next_due_sleep_seconds),
            "phase1_next_due_sku": next_due_sku,
            "phase1_target_universe_mode": _norm(target_universe.get("mode", "")),
            "phase1_target_universe_source": _norm(target_universe.get("source", "")),
            "phase1_target_universe_mode_source": _norm(target_universe.get("mode_source", "")),
            "phase1_target_universe_candidate_count": str(_to_int(target_universe.get("candidate_count", 0)) or 0),
            "phase1_target_universe_resolved_count": str(_to_int(target_universe.get("resolved_count", 0)) or 0),
            "phase1_target_universe_skipped_no_listing_count": str(
                _to_int(target_universe.get("skipped_no_listing_count", 0)) or 0
            ),
            "phase1_target_universe_skipped_out_of_stock_count": str(
                _to_int(target_universe.get("skipped_out_of_stock_count", 0)) or 0
            ),
            "phase1_target_universe_notes_csv": _norm(target_universe.get("notes_csv", "")),
            "phase1_boundary_lock_date": today_utc,
            "phase1_boundary_lock_sku_count": str(len(boundary_lock_by_sku)),
            "phase1_boundary_lock_mode": "",
            "phase1_boundary_lock_final_ceiling_gbp": "",
            "daily_intel_missing_for_today": "0",
            "last_executioner_utc": now_iso,
            "executioner_ran_utc": "",
            "executioner_probe_type": "NO_SKU_DUE",
            "executioner_live_write_attempted": "0",
            "executioner_live_write_success": "0",
            "write_status": "NO_SKU_DUE_COOLDOWN",
            "final_ceiling_landed_gbp": "",
            "reason_codes_csv": "NO_SKU_DUE_COOLDOWN",
            "blocked_due_to_missing_intel": "0",
            "blocked_due_to_stale_intel": "0",
            "refresh_attempted_count": "0",
            "refresh_throttled_count": "0",
        }

    missing_count = sum(1 for row in run_rows if row.get("daily_intel_missing_for_today", "0") == "1")
    blocked_missing_count = sum(1 for row in run_rows if row.get("blocked_due_to_missing_intel", "0") == "1")
    blocked_stale_count = sum(1 for row in run_rows if row.get("blocked_due_to_stale_intel", "0") == "1")
    refresh_attempted_count = sum(int(_norm(row.get("refresh_attempted_count", "0")) or "0") for row in run_rows)
    refresh_throttled_count = sum(int(_norm(row.get("refresh_throttled_count", "0")) or "0") for row in run_rows)
    last = run_rows[-1]
    return {
        "phase1_pilot": "1",
        "phase1_sku": _norm(last.get("phase1_sku", "")),
        "phase1_skus_processed_csv": ",".join([_norm(r.get("phase1_sku", "")) for r in run_rows]),
        "phase1_skus_processed_count": str(len(run_rows)),
        "phase1_skus_skipped_cooldown_count": str(len(skipped_cooldown)),
        "phase1_skus_skipped_parked_count": str(skipped_parked_count),
        "phase1_skus_skipped_out_of_stock_count": str(len(skipped_out_of_stock)),
        "phase1_scan_cooldown_minutes": str(cooldown_minutes),
        "phase1_next_due_sleep_seconds": str(next_due_sleep_seconds),
        "phase1_next_due_sku": next_due_sku,
        "phase1_target_universe_mode": _norm(target_universe.get("mode", "")),
        "phase1_target_universe_source": _norm(target_universe.get("source", "")),
        "phase1_target_universe_mode_source": _norm(target_universe.get("mode_source", "")),
        "phase1_target_universe_candidate_count": str(_to_int(target_universe.get("candidate_count", 0)) or 0),
        "phase1_target_universe_resolved_count": str(_to_int(target_universe.get("resolved_count", 0)) or 0),
        "phase1_target_universe_skipped_no_listing_count": str(
            _to_int(target_universe.get("skipped_no_listing_count", 0)) or 0
        ),
        "phase1_target_universe_skipped_out_of_stock_count": str(
            _to_int(target_universe.get("skipped_out_of_stock_count", 0)) or 0
        ),
        "phase1_target_universe_notes_csv": _norm(target_universe.get("notes_csv", "")),
        "phase1_boundary_lock_date": today_utc,
        "phase1_boundary_lock_sku_count": str(len(boundary_lock_by_sku)),
        "phase1_boundary_lock_mode": _norm(last.get("phase1_boundary_lock_mode", "")),
        "phase1_boundary_lock_final_ceiling_gbp": _norm(last.get("phase1_boundary_lock_final_ceiling_gbp", "")),
        "daily_intel_missing_for_today": "1" if missing_count > 0 else "0",
        "daily_intel_missing_count": str(missing_count),
        "last_executioner_utc": now_iso,
        "executioner_ran_utc": _norm(last.get("executioner_ran_utc", "")),
        "executioner_probe_type": _norm(last.get("executioner_probe_type", "")),
        "executioner_live_write_attempted": _norm(last.get("executioner_live_write_attempted", "0")),
        "executioner_live_write_success": _norm(last.get("executioner_live_write_success", "0")),
        "write_status": _norm(last.get("write_status", "")),
        "final_ceiling_landed_gbp": _norm(last.get("final_ceiling_landed_gbp", "")),
        "reason_codes_csv": _norm(last.get("reason_codes_csv", "")),
        "blocked_due_to_missing_intel": str(blocked_missing_count),
        "blocked_due_to_stale_intel": str(blocked_stale_count),
        "refresh_attempted_count": str(refresh_attempted_count),
        "refresh_throttled_count": str(refresh_throttled_count),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="H110 - Run one Phase 1 H pilot step")
    parser.add_argument("--phase1-config", required=True, help="Path to Phase 1 pilot YAML config")
    parser.add_argument("--read-only", action="store_true", help="Force read-only mode")
    parser.add_argument("--run-id", default="", help="Optional run id from orchestrator")
    parser.add_argument("--now-utc", default="", help="Optional fixed UTC timestamp, ISO")
    args = parser.parse_args()

    cfg_path = Path(args.phase1_config)
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    if not cfg_path.exists():
        raise SystemExit(f"[H110] phase1 config not found: {cfg_path}")
    cfg = _simple_yaml_load(cfg_path)
    run_id = _norm(args.run_id) or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    if _norm(args.now_utc):
        try:
            raw = _norm(args.now_utc).replace("Z", "+00:00")
            parsed = datetime.fromisoformat(raw)
            now_utc = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except Exception:
            pass

    state = _run_once(cfg=cfg, read_only=bool(args.read_only), run_id=run_id, now_utc=now_utc)
    print(json.dumps(state, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
