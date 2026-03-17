from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.h.h_floor_truth import compute_h_floor_for_sku, has_blocking_reason_codes, load_h_floor_context

OUT = ROOT / "out"
DATA = ROOT / "data"

PHASE1_SCOPE_PATH = OUT / "phase1_sku_scope.csv"
PARKED_SKUS_PATH = OUT / "parking" / "parked_skus.csv"
INVENTORY_SUMMARIES_PATH = OUT / "inventory_summaries.csv"
STOCK_SNAPSHOT_LATEST_PATH = OUT / "parking" / "stock_snapshot_latest.csv"
DEFAULT_OUTPUT_PATH = OUT / "phase1_floor_table_latest.csv"


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _to_float(value: Any) -> float | None:
    try:
        raw = _norm(value)
        if raw == "":
            return None
        out = float(raw)
        if not pd.notna(out):
            return None
        return out
    except Exception:
        return None


def _latest_file(directory: Path, pattern: str) -> Path | None:
    files = sorted(directory.glob(pattern))
    if not files:
        return None
    return files[-1]


def _load_parked_skus(path: Path) -> set[str]:
    parked = _read_csv(path)
    if parked.empty or "sku" not in parked.columns:
        return set()
    out: set[str] = set()
    for _, row in parked.iterrows():
        sku = _norm(row.get("sku", "")).upper()
        if sku:
            out.add(sku)
    return out


def _stock_qty_map_from_path(path: Path) -> dict[str, float]:
    df = _read_csv(path)
    if df.empty:
        return {}
    sku_col = ""
    for candidate in ("seller_sku", "sku", "seller-sku", "SKU"):
        if candidate in df.columns:
            sku_col = candidate
            break
    if not sku_col:
        return {}
    out: dict[str, float] = {}
    for _, row in df.iterrows():
        sku = _norm(row.get(sku_col, "")).upper()
        if not sku:
            continue
        available = None
        for col in ("available", "available_qty", "stock_available", "stock"):
            if col in df.columns:
                available = _to_float(row.get(col, ""))
                if available is not None:
                    break
        total_qty = None
        for col in ("total_quantity", "total_qty", "stock_total", "quantity"):
            if col in df.columns:
                total_qty = _to_float(row.get(col, ""))
                if total_qty is not None:
                    break
        qty = available
        if (qty is None or qty <= 0) and total_qty is not None:
            qty = total_qty
        if qty is None:
            continue
        prev = out.get(sku)
        if prev is None or qty > prev:
            out[sku] = float(qty)
    return out


def _load_stock_qty_by_sku() -> dict[str, float]:
    candidates: list[Path] = []
    latest_inventory_snapshot = _latest_file(OUT, "inventory_snapshot_*.csv")
    if latest_inventory_snapshot is not None:
        candidates.append(latest_inventory_snapshot)
    if INVENTORY_SUMMARIES_PATH.exists():
        candidates.append(INVENTORY_SUMMARIES_PATH)
    if STOCK_SNAPSHOT_LATEST_PATH.exists():
        candidates.append(STOCK_SNAPSHOT_LATEST_PATH)

    for path in candidates:
        qty_map = _stock_qty_map_from_path(path)
        if qty_map:
            return qty_map
    return {}


def _required_non_parked_non_dropped_skus(scope_path: Path, parked_path: Path) -> list[str]:
    scope = _read_csv(scope_path)
    if scope.empty:
        return []
    if "sku" not in scope.columns or "parked_flag" not in scope.columns:
        return []

    scoped = scope.copy()
    scoped["sku_key"] = scoped["sku"].astype(str).str.strip().str.upper()
    scoped["parked_key"] = scoped["parked_flag"].astype(str).str.strip().str.lower()
    non_parked_skus = set(scoped.loc[~scoped["parked_key"].eq("1"), "sku_key"].tolist())
    parked_skus = set(scoped.loc[scoped["parked_key"].eq("1"), "sku_key"].tolist())
    parked_skus = parked_skus.union(_load_parked_skus(parked_path))
    non_parked_skus = set([sku for sku in non_parked_skus if sku and sku not in parked_skus])

    stock_qty_by_sku = _load_stock_qty_by_sku()
    sale_status_by_sku: dict[str, str] = {}
    if "sale_status" in scoped.columns:
        scoped["sale_status_key"] = scoped["sale_status"].astype(str).str.strip().str.lower()
        sale_status_by_sku = dict(zip(scoped["sku_key"], scoped["sale_status_key"]))

    required: list[str] = []
    for sku in sorted(non_parked_skus):
        if not sku:
            continue
        stock_qty = float(stock_qty_by_sku.get(sku, 0.0))
        if stock_qty <= 0:
            continue
        sale_status = sale_status_by_sku.get(sku, "")
        if sale_status == "dropped":
            required.append(sku)
            continue
        required.append(sku)
    return required


def _latest_daily_intel_by_sku(path: Path) -> dict[str, dict[str, str]]:
    df = _read_csv(path)
    if df.empty or "sku" not in df.columns:
        return {}
    work = df.copy()
    work["sku"] = work["sku"].astype(str).str.strip().str.upper()
    if "date_utc" in work.columns:
        work = work.sort_values(["sku", "date_utc"], ascending=[True, False])
    work = work.drop_duplicates(subset=["sku"], keep="first")
    out: dict[str, dict[str, str]] = {}
    for _, row in work.iterrows():
        sku = _norm(row.get("sku", "")).upper()
        if not sku:
            continue
        out[sku] = {str(k): _norm(v) for k, v in row.to_dict().items()}
    return out


def _latest_listing_prices(out_dir: Path) -> dict[str, float]:
    latest = _latest_file(out_dir, "listing_offer_snapshot_*.csv")
    if latest is None:
        return {}
    df = _read_csv(latest)
    if df.empty or "sku" not in df.columns:
        return {}
    out: dict[str, float] = {}
    for _, row in df.iterrows():
        sku = _norm(row.get("sku", "")).upper()
        if not sku or sku in out:
            continue
        price = _to_float(row.get("our_price", ""))
        if price is not None and price > 0:
            out[sku] = float(price)
    return out


def _map_reason_code(raw_codes: list[str]) -> str:
    codes = [c for c in raw_codes if _norm(c) != ""]
    if not codes:
        return ""
    joined = "|".join(codes)
    if "COGS_TOKEN_MISSING" in joined:
        return "MISSING_COG"
    if "FBA_BAND_MISSING" in joined or "REFERRAL_BAND_MISSING" in joined:
        return "MISSING_FEES"
    if "CANDIDATE_PRICE_MISSING" in joined:
        return "MISSING_PRICE"
    if "VAT_RATE_MISSING_FALLBACK_USED" in joined:
        return "INVALID_VAT"
    return codes[0]


def _candidate_price_for_sku(
    sku: str,
    listing_prices: dict[str, float],
    daily_latest: dict[str, dict[str, str]],
) -> tuple[float, str]:
    from_listing = listing_prices.get(sku)
    if from_listing is not None and from_listing > 0:
        return float(from_listing), "listing_offer_snapshot.our_price"

    daily = daily_latest.get(sku, {})
    for field in ["cpt_gbp", "compliance_ceiling_landed_gbp", "ceiling_rule_value_gbp"]:
        value = _to_float(daily.get(field, ""))
        if value is not None and value > 0:
            return float(value), f"sku_daily_intel.{field}"
    return 0.0, "none"


def build_floor_table(
    *,
    scope_path: Path,
    parked_path: Path,
    daily_intel_path: Path,
    output_path: Path,
) -> tuple[pd.DataFrame, dict[str, int]]:
    required_skus = _required_non_parked_non_dropped_skus(scope_path, parked_path)
    listing_prices = _latest_listing_prices(scope_path.parent)
    daily_latest = _latest_daily_intel_by_sku(daily_intel_path)
    floor_ctx = load_h_floor_context()
    calc_ts_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    records: list[dict[str, str]] = []
    populated = 0
    reason_coded = 0
    reason_buckets: dict[str, int] = {}
    for sku in required_skus:
        candidate_price, candidate_source = _candidate_price_for_sku(sku, listing_prices, daily_latest)
        inputs, result = compute_h_floor_for_sku(sku, candidate_price, context=floor_ctx)
        raw_codes = list(inputs.reason_codes) + list(result.reason_codes)
        blocking = has_blocking_reason_codes(inputs.reason_codes)
        floor_num = float(result.floor_total_gbp or 0.0)

        floor_gbp = ""
        floor_reason_code = ""
        if (not blocking) and floor_num > 0:
            floor_gbp = f"{round(floor_num, 2):.2f}"
            populated += 1
        else:
            floor_reason_code = _map_reason_code(raw_codes) or "FLOOR_UNAVAILABLE"
            reason_coded += 1
            reason_buckets[floor_reason_code] = int(reason_buckets.get(floor_reason_code, 0)) + 1

        records.append(
            {
                "sku": sku,
                "floor_gbp": floor_gbp,
                "floor_source": "calc_v1",
                "floor_calc_ts_utc": calc_ts_utc,
                "floor_reason_code": floor_reason_code,
                "floor_reason_codes_raw": "|".join([c for c in raw_codes if _norm(c)]),
                "candidate_price_gbp": f"{round(candidate_price, 2):.2f}" if candidate_price > 0 else "",
                "candidate_price_source": candidate_source,
            }
        )

    frame = pd.DataFrame.from_records(
        records,
        columns=[
            "sku",
            "floor_gbp",
            "floor_source",
            "floor_calc_ts_utc",
            "floor_reason_code",
            "floor_reason_codes_raw",
            "candidate_price_gbp",
            "candidate_price_source",
        ],
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False)
    stats = {
        "required_skus": len(required_skus),
        "rows_written": int(len(frame.index)),
        "floors_populated": populated,
        "floors_reason_coded": reason_coded,
    }
    for code, count in sorted(reason_buckets.items()):
        stats[f"reason_{code}"] = int(count)
    return frame, stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Build portfolio-wide phase1 floor table for required non-parked SKUs.")
    parser.add_argument("--scope-path", default=str(PHASE1_SCOPE_PATH))
    parser.add_argument("--parked-path", default=str(PARKED_SKUS_PATH))
    parser.add_argument("--daily-intel-path", default=str(DATA / "sku_daily_intel.csv"))
    parser.add_argument("--out-path", default=str(DEFAULT_OUTPUT_PATH))
    args = parser.parse_args()

    frame, stats = build_floor_table(
        scope_path=Path(args.scope_path),
        parked_path=Path(args.parked_path),
        daily_intel_path=Path(args.daily_intel_path),
        output_path=Path(args.out_path),
    )
    print(f"a018_floor_table_path={Path(args.out_path)}")
    print(f"a018_floor_required_skus={stats.get('required_skus', 0)}")
    print(f"a018_floor_rows_written={stats.get('rows_written', 0)}")
    print(f"a018_floor_populated={stats.get('floors_populated', 0)}")
    print(f"a018_floor_reason_coded={stats.get('floors_reason_coded', 0)}")
    for key, value in sorted(stats.items()):
        if key.startswith("reason_"):
            print(f"a018_floor_{key}={value}")
    print(f"a018_floor_preview_rows={len(frame.index)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
