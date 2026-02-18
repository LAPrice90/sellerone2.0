from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api.get_financial_events import get_lwa_access_token, load_dotenv_if_missing
from scripts.phase1_write_verify import patch_listings_item_price

SOURCE = "H121_manual_price_drop_1p"
SPAPI_BASE_URL = os.environ.get("SPAPI_BASE_URL", "https://sellingpartnerapi-eu.amazon.com")


@dataclass(frozen=True)
class PricePushPlan:
    sku: str
    marketplace_id: str
    seller_id: str
    current_price_gbp: str
    requested_drop_gbp: str
    floor_gbp: str
    target_before_floor_gbp: str
    target_after_floor_gbp: str
    clamped_to_floor: bool


def _norm(value: object) -> str:
    return str(value or "").strip()


def _to_decimal(value: object) -> Decimal | None:
    raw = _norm(value)
    if not raw:
        return None
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


def _money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


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


def _latest_listing_row_for_sku(sku: str) -> dict[str, str]:
    files = sorted(OUT.glob("listing_offer_snapshot_*.csv"))
    if not files:
        raise RuntimeError("No listing snapshot found in out/")
    path = files[-1]
    df = pd.read_csv(path, dtype=str).fillna("")
    sku_col = df.get("sku", "").astype(str).str.strip().str.upper()
    one = df.loc[sku_col.eq(sku.upper())]
    if one.empty:
        raise RuntimeError(f"SKU missing from listing snapshot: {sku}")
    return {k: _norm(v) for k, v in one.iloc[0].to_dict().items()}


def _build_plan(
    *,
    cfg: dict,
    override_price_gbp: str,
    drop_pence: int,
) -> PricePushPlan:
    sku = _norm(_cfg_get(cfg, "sku", default="")).upper()
    if not sku:
        raise RuntimeError("Config missing sku")

    row = _latest_listing_row_for_sku(sku)
    marketplace_id = _norm(_cfg_get(cfg, "marketplace_id", default="")) or "A1F83G8C2ARO7P"
    seller_id = (
        _norm(_cfg_get(cfg, "seller_id", default=""))
        or _norm(os.environ.get("SELLER_ID", ""))
        or _norm(os.environ.get("SELLER_PARTNER_ID", ""))
        or _norm(os.environ.get("MERCHANT_ID", ""))
        or _norm(os.environ.get("SELLING_PARTNER_ID", ""))
    )
    if not seller_id:
        raise RuntimeError("Missing seller_id in config and environment")

    current = _to_decimal(override_price_gbp) or _to_decimal(row.get("our_price", ""))
    if current is None:
        raise RuntimeError("Could not resolve current price from --from-price or latest listing snapshot")
    floor = _to_decimal(_cfg_get(cfg, "boundaries", "hard_floor_gbp", default="0")) or Decimal("0")
    drop = (Decimal(drop_pence) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    target_before_floor = (current - drop).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    target_after_floor = max(target_before_floor, floor)

    return PricePushPlan(
        sku=sku,
        marketplace_id=marketplace_id,
        seller_id=seller_id,
        current_price_gbp=_money(current),
        requested_drop_gbp=_money(drop),
        floor_gbp=_money(floor),
        target_before_floor_gbp=_money(target_before_floor),
        target_after_floor_gbp=_money(target_after_floor),
        clamped_to_floor=(target_after_floor != target_before_floor),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="H121 - One-off manual 1p price drop push via Listings Items PATCH")
    parser.add_argument("--phase1-config", default="config/pilot_sku.yaml", help="Path to pilot YAML config")
    parser.add_argument("--drop-pence", type=int, default=1, help="Price drop in pence (default: 1)")
    parser.add_argument("--from-price", default="", help="Override current price instead of latest listing snapshot")
    parser.add_argument("--product-type", default="PRODUCT", help="Listings productType for PATCH")
    parser.add_argument("--currency", default="GBP", help="Currency code (default: GBP)")
    parser.add_argument("--apply", action="store_true", help="Send PATCH to Amazon; default is dry run")
    args = parser.parse_args()

    cfg_path = Path(args.phase1_config)
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    if not cfg_path.exists():
        raise SystemExit(f"[H121] missing config: {cfg_path}")
    if args.drop_pence <= 0:
        raise SystemExit("[H121] --drop-pence must be > 0")

    cfg = _simple_yaml_load(cfg_path)
    plan = _build_plan(cfg=cfg, override_price_gbp=_norm(args.from_price), drop_pence=args.drop_pence)

    out = {
        "script": SOURCE,
        "timestamp_utc": datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": "apply" if args.apply else "dry_run",
        "plan": asdict(plan),
    }

    if not args.apply:
        print(json.dumps(out, ensure_ascii=True))
        return 0

    load_dotenv_if_missing()
    token = get_lwa_access_token()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    write = patch_listings_item_price(
        access_token=token,
        seller_id=plan.seller_id,
        sku=plan.sku,
        marketplace_id=plan.marketplace_id,
        product_type=_norm(args.product_type) or "PRODUCT",
        target_price_gbp=plan.target_after_floor_gbp,
        currency=_norm(args.currency) or "GBP",
        run_id=run_id,
        source_script=SOURCE,
        spapi_base_url=SPAPI_BASE_URL,
    )
    out["write_result"] = write
    print(json.dumps(out, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
