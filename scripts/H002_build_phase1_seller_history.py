from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import pandas as pd

OUT = Path("out")
SELLER_HISTORY_PATH = OUT / "listing_offer_seller_observation_history.csv"
PHASE1_HISTORY_PATH = OUT / "phase1_seller_history.csv"
LISTING_HISTORY_PATH = OUT / "listing_offer_history.csv"

PHASE1_REQUIRED_COLUMNS: List[str] = [
    "timestamp_utc",
    "asof_date",
    "marketplace",
    "sku",
    "asin",
    "seller_id",
    "seller_seen_flag",
    "first_seen_timestamp",
    "last_seen_timestamp",
    "continuous_presence_hours",
    "absence_gap_hours",
    "reentry_after_absence_flag",
    "offer_price_gbp",
    "min_price_seen_gbp",
    "max_price_seen_gbp",
    "median_price_seen_gbp",
    "time_at_min_price_hours",
    "time_at_max_price_hours",
    "price_move_initiations",
    "follow_events",
    "reaction_lag_minutes",
    "directional_bias",
    "floor_set_events",
    "min_delivery_days",
    "max_delivery_days",
    "delivery_range_days",
    "is_prime",
    "delivery_delta_vs_fastest_days",
    "fulfilment_channel",
    "our_price",
    "our_price_changes",
    "our_delivery_posture",
    "manual_interventions",
    "intent_notes",
    "source",
    "notes",
]


def _to_dt(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True)


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=PHASE1_REQUIRED_COLUMNS)


def _format_float(val: float | None, decimals: int = 4) -> str:
    if val is None:
        return ""
    return f"{val:.{decimals}f}"


def _format_int(val: int | None) -> str:
    if val is None:
        return ""
    return str(int(val))


def _clean_str(value: object) -> str:
    return str(value or "").strip()


def _load_listing_context() -> pd.DataFrame:
    if not LISTING_HISTORY_PATH.exists():
        return pd.DataFrame(
            columns=["asof_date", "marketplace", "sku", "asin", "our_price", "our_price_changes"]
        )

    listing = pd.read_csv(LISTING_HISTORY_PATH, dtype=str).fillna("")
    for col in ["asof_date", "marketplace", "sku", "asin", "our_price"]:
        if col not in listing.columns:
            listing[col] = ""

    listing = listing[
        listing["asof_date"].astype(str).str.strip().ne("")
        & listing["marketplace"].astype(str).str.strip().ne("")
        & listing["sku"].astype(str).str.strip().ne("")
    ].copy()
    if listing.empty:
        return pd.DataFrame(
            columns=["asof_date", "marketplace", "sku", "asin", "our_price", "our_price_changes"]
        )

    listing = listing.sort_values(["marketplace", "sku", "asin", "asof_date"]).copy()
    listing["our_price_num"] = _to_num(listing["our_price"])
    listing["our_price_prev"] = listing.groupby(["marketplace", "sku", "asin"])["our_price_num"].shift(1)
    listing["our_price_change_flag"] = (
        listing["our_price_num"].notna()
        & listing["our_price_prev"].notna()
        & listing["our_price_num"].ne(listing["our_price_prev"])
    ).astype(int)
    listing["our_price_changes"] = (
        listing.groupby(["marketplace", "sku", "asin"])["our_price_change_flag"].cumsum()
    )
    listing["our_price_changes"] = listing["our_price_changes"].fillna(0).astype(int).astype(str)
    return listing[["asof_date", "marketplace", "sku", "asin", "our_price", "our_price_changes"]].copy()


def _build_group_rows(
    group: pd.DataFrame,
    gap_threshold_hours: float,
    listing_ctx_map: Dict[str, Dict[str, str]],
    fastest_delivery_map: Dict[str, int],
) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    if group.empty:
        return rows

    group = group.sort_values(["timestamp_dt", "asof_date"]).copy()
    ts_vals = group["timestamp_dt"].tolist()
    price_vals = _to_num(group["offer_price_gbp"])

    first_seen = ts_vals[0]
    first_seen_iso = first_seen.isoformat().replace("+00:00", "Z") if pd.notna(first_seen) else ""

    streak_start = ts_vals[0]
    min_so_far: List[float] = []
    max_so_far: List[float] = []
    med_so_far: List[float] = []
    seen_prices: List[float] = []
    cum_time_at_min = 0.0
    cum_time_at_max = 0.0
    price_move_initiations = 0
    floor_set_events = 0
    upward_moves = 0
    downward_moves = 0
    prev_ts = None
    prev_price = None
    prev_min = None
    prev_max = None

    for i, (_, rec) in enumerate(group.iterrows()):
        ts = rec["timestamp_dt"]
        price = price_vals.iloc[i]
        gap_hours = None
        reentry = 0
        if prev_ts is not None and pd.notna(ts) and pd.notna(prev_ts):
            gap_hours = max((ts - prev_ts).total_seconds() / 3600.0, 0.0)
            if gap_hours > gap_threshold_hours:
                reentry = 1
                streak_start = ts
        elif streak_start is None:
            streak_start = ts

        if prev_ts is not None and pd.notna(prev_ts) and pd.notna(ts) and prev_price is not None:
            delta_h = max((ts - prev_ts).total_seconds() / 3600.0, 0.0)
            if prev_min is not None and prev_price == prev_min:
                cum_time_at_min += delta_h
            if prev_max is not None and prev_price == prev_max:
                cum_time_at_max += delta_h

        if pd.notna(price):
            seen_prices.append(float(price))

        cur_min = min(seen_prices) if seen_prices else None
        cur_max = max(seen_prices) if seen_prices else None
        cur_median = float(pd.Series(seen_prices, dtype=float).median()) if seen_prices else None
        if prev_min is not None and cur_min is not None and cur_min < prev_min:
            floor_set_events += 1

        if prev_price is not None and pd.notna(price):
            cur_price = float(price)
            if cur_price != prev_price:
                price_move_initiations += 1
                if cur_price > prev_price:
                    upward_moves += 1
                elif cur_price < prev_price:
                    downward_moves += 1

        min_so_far.append(cur_min if cur_min is not None else float("nan"))
        max_so_far.append(cur_max if cur_max is not None else float("nan"))
        med_so_far.append(cur_median if cur_median is not None else float("nan"))

        continuous_h = None
        if streak_start is not None and pd.notna(streak_start) and pd.notna(ts):
            continuous_h = max((ts - streak_start).total_seconds() / 3600.0, 0.0)

        ts_iso = ts.isoformat().replace("+00:00", "Z") if pd.notna(ts) else str(rec.get("timestamp_utc", ""))
        row_notes = str(rec.get("notes", "") or "").strip()
        if str(rec.get("seller_id", "")).startswith("unknown_"):
            row_notes = (row_notes + " | seller_id_missing").strip(" |")
        direction = "flat"
        if upward_moves > downward_moves:
            direction = "up"
        elif downward_moves > upward_moves:
            direction = "down"

        delivery_min = _to_num(pd.Series([rec.get("min_delivery_days", "")], dtype=object)).iloc[0]
        delivery_min_int = int(delivery_min) if pd.notna(delivery_min) else None
        fastest_key = "||".join(
            [
                _clean_str(rec.get("asof_date", "")),
                _clean_str(rec.get("marketplace", "")),
                _clean_str(rec.get("sku", "")),
                _clean_str(rec.get("asin", "")),
            ]
        )
        fastest_delivery = fastest_delivery_map.get(fastest_key)
        delivery_delta = None
        if delivery_min_int is not None and fastest_delivery is not None:
            delivery_delta = delivery_min_int - fastest_delivery

        listing_key = fastest_key
        listing_ctx = listing_ctx_map.get(listing_key, {})

        rows.append(
            {
                "timestamp_utc": ts_iso,
                "asof_date": str(rec.get("asof_date", "")),
                "marketplace": str(rec.get("marketplace", "")),
                "sku": str(rec.get("sku", "")),
                "asin": str(rec.get("asin", "")),
                "seller_id": str(rec.get("seller_id", "")),
                "seller_seen_flag": "1",
                "first_seen_timestamp": first_seen_iso,
                "last_seen_timestamp": ts_iso,
                "continuous_presence_hours": _format_float(continuous_h),
                "absence_gap_hours": _format_float(gap_hours),
                "reentry_after_absence_flag": str(reentry),
                "offer_price_gbp": str(rec.get("offer_price_gbp", "")),
                "min_price_seen_gbp": _format_float(cur_min),
                "max_price_seen_gbp": _format_float(cur_max),
                "median_price_seen_gbp": _format_float(cur_median),
                "time_at_min_price_hours": _format_float(cum_time_at_min),
                "time_at_max_price_hours": _format_float(cum_time_at_max),
                "price_move_initiations": _format_int(price_move_initiations),
                "follow_events": "",
                "reaction_lag_minutes": "",
                "directional_bias": direction,
                "floor_set_events": _format_int(floor_set_events),
                "min_delivery_days": _clean_str(rec.get("min_delivery_days", "")),
                "max_delivery_days": _clean_str(rec.get("max_delivery_days", "")),
                "delivery_range_days": _clean_str(rec.get("delivery_range_days", "")),
                "is_prime": _clean_str(rec.get("is_prime", "")),
                "delivery_delta_vs_fastest_days": _format_int(delivery_delta),
                "fulfilment_channel": _clean_str(rec.get("fulfilment_channel", "")),
                "our_price": _clean_str(listing_ctx.get("our_price", "")),
                "our_price_changes": _clean_str(listing_ctx.get("our_price_changes", "")),
                "our_delivery_posture": "",
                "manual_interventions": "",
                "intent_notes": "",
                "source": "DERIVED_FROM_SELLER_OBSERVATION_HISTORY",
                "notes": row_notes,
            }
        )

        prev_ts = ts
        prev_price = float(price) if pd.notna(price) else None
        prev_min = cur_min
        prev_max = cur_max

    return rows


def build_phase1_seller_history(gap_threshold_hours: float = 36.0) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if not SELLER_HISTORY_PATH.exists():
        _empty_df().to_csv(PHASE1_HISTORY_PATH, index=False)
        return 0

    src = pd.read_csv(SELLER_HISTORY_PATH, dtype=str).fillna("")
    required_src_cols = [
        "timestamp_utc",
        "asof_date",
        "marketplace",
        "sku",
        "asin",
        "seller_id",
        "offer_price_gbp",
        "min_delivery_days",
        "max_delivery_days",
        "delivery_range_days",
        "is_prime",
        "fulfilment_channel",
        "notes",
    ]
    for col in required_src_cols:
        if col not in src.columns:
            src[col] = ""
    src = src[required_src_cols + [c for c in src.columns if c not in required_src_cols]]
    src["timestamp_dt"] = _to_dt(src["timestamp_utc"])
    src = src[
        src["seller_id"].astype(str).str.strip().ne("")
        & src["sku"].astype(str).str.strip().ne("")
        & src["marketplace"].astype(str).str.strip().ne("")
    ].copy()
    if src.empty:
        _empty_df().to_csv(PHASE1_HISTORY_PATH, index=False)
        return 0

    src["min_delivery_days_num"] = _to_num(src["min_delivery_days"])
    fastest_delivery = (
        src[src["min_delivery_days_num"].notna()]
        .groupby(["asof_date", "marketplace", "sku", "asin"], dropna=False)["min_delivery_days_num"]
        .min()
        .reset_index()
    )
    fastest_delivery_map = {
        "||".join(
            [
                _clean_str(r["asof_date"]),
                _clean_str(r["marketplace"]),
                _clean_str(r["sku"]),
                _clean_str(r["asin"]),
            ]
        ): int(r["min_delivery_days_num"])
        for _, r in fastest_delivery.iterrows()
    }

    listing_ctx_df = _load_listing_context()
    listing_ctx_map = {
        "||".join(
            [
                _clean_str(r["asof_date"]),
                _clean_str(r["marketplace"]),
                _clean_str(r["sku"]),
                _clean_str(r["asin"]),
            ]
        ): {
            "our_price": _clean_str(r["our_price"]),
            "our_price_changes": _clean_str(r["our_price_changes"]),
        }
        for _, r in listing_ctx_df.iterrows()
    }

    out_rows: List[Dict[str, str]] = []
    keys = ["marketplace", "sku", "asin", "seller_id"]
    for _, grp in src.groupby(keys, dropna=False):
        out_rows.extend(_build_group_rows(grp, gap_threshold_hours, listing_ctx_map, fastest_delivery_map))

    out_df = pd.DataFrame(out_rows, dtype=str).fillna("")
    for col in PHASE1_REQUIRED_COLUMNS:
        if col not in out_df.columns:
            out_df[col] = ""
    out_df = out_df[PHASE1_REQUIRED_COLUMNS]
    out_df = out_df.drop_duplicates(
        subset=["asof_date", "marketplace", "sku", "asin", "seller_id"],
        keep="last",
    ).sort_values(["asof_date", "marketplace", "sku", "asin", "seller_id"])
    out_df.to_csv(PHASE1_HISTORY_PATH, index=False)
    return len(out_df)


def main() -> None:
    rows = build_phase1_seller_history()
    now = datetime.now(timezone.utc).isoformat()
    print(f"[H002] phase1_seller_history rows={rows} path={PHASE1_HISTORY_PATH} at {now}")


if __name__ == "__main__":
    main()
