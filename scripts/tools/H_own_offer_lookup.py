from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api.get_listing_item_price import run_own_offer_price_lookup


def _norm(value: object) -> str:
    return str(value or "").strip()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guarded subprocess for own offer lookup")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--marketplace-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--script-name", default="run_H_pricing_cycle")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    in_path = Path(args.input)
    out_path = Path(args.output)
    payload = json.loads(in_path.read_text(encoding="utf-8"))
    skus_raw = payload.get("skus", [])
    skus: list[str] = []
    if isinstance(skus_raw, list):
        for sku in skus_raw:
            sku_norm = _norm(sku).upper()
            if sku_norm:
                skus.append(sku_norm)
    own_map = run_own_offer_price_lookup(
        skus=skus,
        marketplace_id=_norm(args.marketplace_id),
        run_id=_norm(args.run_id),
        script_name=_norm(args.script_name) or "run_H_pricing_cycle",
        progress_callback=None,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"own_map": own_map}, ensure_ascii=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
