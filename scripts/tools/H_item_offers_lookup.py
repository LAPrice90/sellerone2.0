from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api.get_pricing import run_market_context_lookup_with_offers_detail


def _norm(value: object) -> str:
    return str(value or "").strip()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guarded subprocess for item_offers lookup")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--marketplace-id", required=True)
    parser.add_argument("--snapshot-ts", required=True)
    parser.add_argument("--snapshot-date", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--script-name", default="run_H_pricing_cycle")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    in_path = Path(args.input)
    out_path = Path(args.output)
    payload = json.loads(in_path.read_text(encoding="utf-8"))
    rows_raw = payload.get("sku_asins", [])
    sku_asins: list[tuple[str, str]] = []
    if isinstance(rows_raw, list):
        for row in rows_raw:
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                continue
            sku = _norm(row[0])
            asin = _norm(row[1])
            if not sku or not asin:
                continue
            sku_asins.append((sku, asin))

    prioritized_asins_raw = payload.get("prioritized_asins", [])
    prioritized_asins: list[str] = []
    if isinstance(prioritized_asins_raw, list):
        for value in prioritized_asins_raw:
            asin = _norm(value)
            if asin:
                prioritized_asins.append(asin)

    bb_map, offer_rows, detail_meta = run_market_context_lookup_with_offers_detail(
        sku_asin_rows=sku_asins,
        marketplace_id=_norm(args.marketplace_id),
        snapshot_timestamp_utc=_norm(args.snapshot_ts),
        snapshot_asof_date=_norm(args.snapshot_date),
        run_id=_norm(args.run_id),
        script_name=_norm(args.script_name) or "run_H_pricing_cycle",
        progress_callback=None,
        prioritized_asins=prioritized_asins,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "bb_map": bb_map,
                "offer_rows": offer_rows,
                "detail_meta_by_asin": detail_meta,
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
