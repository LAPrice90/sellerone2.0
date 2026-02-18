from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

OUT = Path("out")
PERF_PATH = OUT / "sku_performance_summary.csv"
LISTING_HISTORY_PATH = OUT / "listing_offer_history.csv"
HISTORY_OUTPUT_PATH = OUT / "hos_daily_market_history.csv"

REQUIRED_COLUMNS: List[str] = [
    "asof_date",
    "marketplace",
    "sku",
    "asin",
    "buy_box_price_raw_gross",
    "buy_box_price_used_gross",
    "buy_box_channel",
    "buy_box_seller_id",
    "buy_box_missing_flag",
    "buy_box_fallback_used_flag",
    "lowest_offer_price_gross",
    "lowest_fba_price_gross",
    "lowest_fbm_price_gross",
    "highest_offer_price_gross",
    "median_offer_price_gross",
    "price_spread_gross",
    "offer_count_total",
    "offer_count_fba",
    "offer_count_fbm",
    "amazon_present_flag",
    "seller_entry_count_today",
    "seller_exit_count_today",
    "our_delivery_days",
    "buy_box_delivery_days",
    "delivery_parity_flag",
    "prime_eligible_flag",
    "break_even_exvat_gbp",
    "break_even_gross_gbp",
    "token_cost_exvat_gbp",
    "min_price_gross_10pct",
    "max_price_gross_current",
]


def _to_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return float(text)
    except Exception:
        return None


def _to_int(value: object) -> int | None:
    try:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return int(float(text))
    except Exception:
        return None


def _norm(value: object) -> str:
    return str(value or "").strip()


def _norm_upper(value: object) -> str:
    return _norm(value).upper()


def _fmt_num(value: float | None, decimals: int = 6) -> str:
    if value is None:
        return ""
    return f"{round(value, decimals):.{decimals}f}"


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _snapshot_date() -> str:
    override = os.environ.get("H_SNAPSHOT_DATE", "").strip()
    if override:
        return override
    return datetime.now(timezone.utc).date().isoformat()


def _listing_snapshot_path(asof_date: str) -> Path | None:
    wanted = OUT / f"listing_offer_snapshot_{asof_date}.csv"
    if wanted.exists():
        return wanted
    files = sorted(OUT.glob("listing_offer_snapshot_*.csv"))
    if not files:
        return None
    return files[-1]


def _seller_snapshot_path(asof_date: str) -> Path | None:
    wanted = OUT / f"listing_offer_seller_snapshot_{asof_date}.csv"
    if wanted.exists():
        return wanted
    files = sorted(OUT.glob("listing_offer_seller_snapshot_*.csv"))
    if not files:
        return None
    return files[-1]


def _seller_snapshot_prev_path(asof_date: str) -> Path | None:
    try:
        d = datetime.strptime(asof_date, "%Y-%m-%d").date()
    except ValueError:
        return None
    prev = (d - timedelta(days=1)).isoformat()
    path = OUT / f"listing_offer_seller_snapshot_{prev}.csv"
    if path.exists():
        return path
    return None


def _infer_our_seller_id(listing: pd.DataFrame, seller_today: pd.DataFrame) -> str:
    if seller_today.empty or listing.empty:
        return ""

    listing = listing.copy()
    listing["k"] = (
        listing.get("asof_date", "").astype(str)
        + "||"
        + listing.get("marketplace", "").astype(str)
        + "||"
        + listing.get("sku", "").astype(str)
        + "||"
        + listing.get("asin", "").astype(str)
    )
    price_map: Dict[str, str] = {}
    for _, rec in listing.iterrows():
        price_map[_norm(rec.get("k", ""))] = _norm(rec.get("our_price", ""))

    hits: Dict[str, int] = {}
    for _, rec in seller_today.iterrows():
        key = (
            _norm(rec.get("asof_date", ""))
            + "||"
            + _norm(rec.get("marketplace", ""))
            + "||"
            + _norm(rec.get("sku", ""))
            + "||"
            + _norm(rec.get("asin", ""))
        )
        our_price = price_map.get(key, "")
        if not our_price:
            continue
        p_offer = _to_float(rec.get("offer_price_gbp", ""))
        p_our = _to_float(our_price)
        if p_offer is None or p_our is None:
            continue
        if abs(p_offer - p_our) <= 0.01:
            seller_id = _norm(rec.get("seller_id", ""))
            if seller_id:
                hits[seller_id] = hits.get(seller_id, 0) + 1

    if not hits:
        return ""
    return sorted(hits.items(), key=lambda x: (-x[1], x[0]))[0][0]


def _latest_non_null_buy_box_from_history(asof_date: str) -> Dict[str, str]:
    history = _read_csv(LISTING_HISTORY_PATH)
    if history.empty:
        return {}
    for c in ["asof_date", "marketplace", "sku", "asin", "buy_box_price"]:
        if c not in history.columns:
            history[c] = ""

    hist = history.copy()
    hist["asof_dt"] = pd.to_datetime(hist["asof_date"], errors="coerce")
    cutoff = pd.to_datetime(asof_date, errors="coerce")
    if pd.notna(cutoff):
        hist = hist[(hist["asof_dt"].isna()) | (hist["asof_dt"] <= cutoff)]

    hist = hist.sort_values(["asof_dt"], kind="stable")
    out: Dict[str, str] = {}
    for _, rec in hist.iterrows():
        bb = _norm(rec.get("buy_box_price", ""))
        if not bb:
            continue
        key = (
            _norm(rec.get("marketplace", ""))
            + "||"
            + _norm(rec.get("sku", ""))
            + "||"
            + _norm(rec.get("asin", ""))
        )
        out[key] = bb
    return out


def _ensure_columns(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    return df[columns].copy()


def main() -> None:
    asof_date = _snapshot_date()

    listing_path = _listing_snapshot_path(asof_date)
    if listing_path is None:
        raise FileNotFoundError("No listing snapshot found: out/listing_offer_snapshot_YYYY-MM-DD.csv")
    listing = _read_csv(listing_path)
    if listing.empty:
        raise RuntimeError(f"Listing snapshot is empty: {listing_path.as_posix()}")

    for col in [
        "asof_date",
        "marketplace",
        "sku",
        "asin",
        "our_price",
        "buy_box_price",
        "buy_box_channel",
        "lowest_fba_price",
        "lowest_fbm_price",
        "offer_count_fba",
        "offer_count_fbm",
    ]:
        if col not in listing.columns:
            listing[col] = ""

    seller_today_path = _seller_snapshot_path(asof_date)
    seller_prev_path = _seller_snapshot_prev_path(asof_date)
    seller_today = _read_csv(seller_today_path) if seller_today_path else pd.DataFrame()
    seller_prev = _read_csv(seller_prev_path) if seller_prev_path else pd.DataFrame()
    perf = _read_csv(PERF_PATH)
    perf_map: Dict[str, Dict[str, str]] = {}
    if not perf.empty:
        for col in [
            "sku",
            "asof_date",
            "current_token_cost_gbp",
            "break_even_price_gbp",
        ]:
            if col not in perf.columns:
                perf[col] = ""
        perf = perf.sort_values(["asof_date"], kind="stable")
        for _, rec in perf.iterrows():
            key = _norm_upper(rec.get("sku", ""))
            if not key:
                continue
            perf_map[key] = {
                "current_token_cost_gbp": _norm(rec.get("current_token_cost_gbp", "")),
                "break_even_price_gbp": _norm(rec.get("break_even_price_gbp", "")),
            }

    for df in [seller_today, seller_prev]:
        if df.empty:
            continue
        for col in [
            "asof_date",
            "marketplace",
            "sku",
            "asin",
            "seller_id",
            "offer_price_gbp",
            "offer_landed_price_gbp",
            "offer_shipping_price_gbp",
            "is_prime",
            "fulfilment_channel",
            "min_delivery_days",
        ]:
            if col not in df.columns:
                df[col] = ""

    our_seller_id = _norm(os.environ.get("SELLER_ID", "")) or _infer_our_seller_id(listing, seller_today)
    latest_bb_from_history = _latest_non_null_buy_box_from_history(asof_date)

    seller_today_by_key: Dict[str, pd.DataFrame] = {}
    if not seller_today.empty:
        seller_today["k"] = (
            seller_today["asof_date"].astype(str)
            + "||"
            + seller_today["marketplace"].astype(str)
            + "||"
            + seller_today["sku"].astype(str)
            + "||"
            + seller_today["asin"].astype(str)
        )
        for k, grp in seller_today.groupby("k", dropna=False):
            seller_today_by_key[str(k)] = grp.copy()

    seller_prev_ids_by_key: Dict[str, set[str]] = {}
    if not seller_prev.empty:
        seller_prev["k"] = (
            seller_prev["marketplace"].astype(str)
            + "||"
            + seller_prev["sku"].astype(str)
            + "||"
            + seller_prev["asin"].astype(str)
        )
        for k, grp in seller_prev.groupby("k", dropna=False):
            ids = set([_norm(x) for x in grp.get("seller_id", "").astype(str).tolist() if _norm(x)])
            seller_prev_ids_by_key[str(k)] = ids

    output_rows: List[Dict[str, str]] = []
    fallback_count = 0
    missing_buy_box_count = 0

    for _, rec in listing.iterrows():
        row_asof = _norm(rec.get("asof_date", "")) or asof_date
        row_market = _norm(rec.get("marketplace", ""))
        row_sku = _norm(rec.get("sku", ""))
        row_asin = _norm(rec.get("asin", ""))
        key_full = row_asof + "||" + row_market + "||" + row_sku + "||" + row_asin
        key_hist = row_market + "||" + row_sku + "||" + row_asin

        our_price = _norm(rec.get("our_price", ""))
        buy_box_raw = _norm(rec.get("buy_box_price", ""))
        lowest_fba = _norm(rec.get("lowest_fba_price", ""))
        lowest_fbm = _norm(rec.get("lowest_fbm_price", ""))
        buy_box_channel = _norm(rec.get("buy_box_channel", ""))

        buy_box_used = ""
        fallback_source = "none"
        if buy_box_raw:
            buy_box_used = buy_box_raw
            fallback_source = "raw"
        else:
            hist_bb = latest_bb_from_history.get(key_hist, "")
            if hist_bb:
                buy_box_used = hist_bb
                fallback_source = "history"
            elif lowest_fba:
                buy_box_used = lowest_fba
                fallback_source = "lowest_fba"
            elif our_price:
                buy_box_used = our_price
                fallback_source = "our_price"
            else:
                buy_box_used = ""
                fallback_source = "missing"

        buy_box_missing_flag = "1" if not buy_box_raw else "0"
        buy_box_fallback_used_flag = "1" if fallback_source != "raw" else "0"
        if buy_box_fallback_used_flag == "1":
            fallback_count += 1
        if buy_box_missing_flag == "1":
            missing_buy_box_count += 1

        grp_today = seller_today_by_key.get(key_full, pd.DataFrame())
        offer_prices: List[float] = []
        offer_fba_prices: List[float] = []
        offer_fbm_prices: List[float] = []
        seller_ids_today: set[str] = set()
        amazon_present = False
        buy_box_seller_id = ""
        buy_box_delivery_days = ""
        prime_eligible_flag = "0"
        our_delivery_days = ""

        bb_used_num = _to_float(buy_box_used)
        bb_channel_upper = _norm_upper(buy_box_channel)
        our_price_num = _to_float(our_price)

        if not grp_today.empty:
            for _, srec in grp_today.iterrows():
                seller_id = _norm(srec.get("seller_id", ""))
                if seller_id:
                    seller_ids_today.add(seller_id)
                    if "AMAZON" in _norm_upper(seller_id):
                        amazon_present = True

                p = _to_float(srec.get("offer_landed_price_gbp", ""))
                if p is None:
                    p = _to_float(srec.get("offer_price_gbp", ""))
                channel = _norm_upper(srec.get("fulfilment_channel", ""))
                if p is not None:
                    offer_prices.append(p)
                    if channel == "FBA":
                        offer_fba_prices.append(p)
                    elif channel == "FBM":
                        offer_fbm_prices.append(p)

            # Determine buy box seller based on price and channel fit.
            candidate_rows: List[Tuple[str, str, str]] = []
            if bb_used_num is not None:
                for _, srec in grp_today.iterrows():
                    p = _to_float(srec.get("offer_landed_price_gbp", ""))
                    if p is None:
                        p = _to_float(srec.get("offer_price_gbp", ""))
                    if p is None or abs(p - bb_used_num) > 0.01:
                        continue
                    sid = _norm(srec.get("seller_id", ""))
                    ch = _norm_upper(srec.get("fulfilment_channel", ""))
                    d = _norm(srec.get("min_delivery_days", ""))
                    candidate_rows.append((sid, ch, d))
            if candidate_rows:
                preferred = [t for t in candidate_rows if t[1] == bb_channel_upper] if bb_channel_upper else []
                chosen = sorted(preferred or candidate_rows, key=lambda x: (x[0], x[2]))[0]
                buy_box_seller_id = chosen[0]
                buy_box_delivery_days = chosen[2]
                if chosen[1] == "FBA":
                    prime_eligible_flag = "1"
                else:
                    # fallback to explicit is_prime marker on matching rows
                    for _, srec in grp_today.iterrows():
                        p = _to_float(srec.get("offer_landed_price_gbp", ""))
                        if p is None:
                            p = _to_float(srec.get("offer_price_gbp", ""))
                        sid = _norm(srec.get("seller_id", ""))
                        if p is not None and abs(p - bb_used_num) <= 0.01 and sid == buy_box_seller_id:
                            if _norm(srec.get("is_prime", "")) == "1":
                                prime_eligible_flag = "1"
                                break

            # Determine our delivery days.
            if our_seller_id:
                ours = grp_today[
                    grp_today["seller_id"].astype(str).str.strip().eq(our_seller_id)
                ]
                if not ours.empty:
                    vals = [
                        _to_int(v) for v in ours.get("min_delivery_days", "").astype(str).tolist()
                    ]
                    vals = [v for v in vals if v is not None]
                    if vals:
                        our_delivery_days = str(min(vals))
            if not our_delivery_days and our_price_num is not None:
                matches = []
                for _, srec in grp_today.iterrows():
                    p = _to_float(srec.get("offer_price_gbp", ""))
                    if p is not None and abs(p - our_price_num) <= 0.01:
                        d = _to_int(srec.get("min_delivery_days", ""))
                        if d is not None:
                            matches.append(d)
                if matches:
                    our_delivery_days = str(min(matches))

        if _norm_upper(buy_box_channel) == "AMAZON":
            amazon_present = True

        lowest_offer = min(offer_prices) if offer_prices else None
        highest_offer = max(offer_prices) if offer_prices else None
        median_offer = float(pd.Series(offer_prices, dtype=float).median()) if offer_prices else None
        if lowest_offer is None:
            lowest_offer = _to_float(lowest_fba) if _to_float(lowest_fba) is not None else _to_float(lowest_fbm)
        lowest_fba_num = min(offer_fba_prices) if offer_fba_prices else _to_float(lowest_fba)
        lowest_fbm_num = min(offer_fbm_prices) if offer_fbm_prices else _to_float(lowest_fbm)
        spread = (highest_offer - lowest_offer) if (highest_offer is not None and lowest_offer is not None) else None

        offer_count_fba_num = _to_int(rec.get("offer_count_fba", "")) or (len(offer_fba_prices) if offer_fba_prices else 0)
        offer_count_fbm_num = _to_int(rec.get("offer_count_fbm", "")) or (len(offer_fbm_prices) if offer_fbm_prices else 0)
        offer_count_total_num = offer_count_fba_num + offer_count_fbm_num
        if offer_count_total_num == 0 and seller_ids_today:
            offer_count_total_num = len(seller_ids_today)

        prev_ids = seller_prev_ids_by_key.get(key_hist, set())
        entry_count = len(seller_ids_today - prev_ids)
        exit_count = len(prev_ids - seller_ids_today)

        delivery_parity_flag = "0"
        if our_delivery_days and buy_box_delivery_days and our_delivery_days == buy_box_delivery_days:
            delivery_parity_flag = "1"

        perf_key = _norm_upper(row_sku)
        perf_rec = perf_map.get(perf_key, {})
        token_cost_exvat = _to_float(perf_rec.get("current_token_cost_gbp", ""))
        break_even_exvat = _to_float(perf_rec.get("break_even_price_gbp", ""))
        break_even_gross = (break_even_exvat * 1.2) if break_even_exvat is not None else None
        min_price_gross_10 = None
        if break_even_exvat is not None and token_cost_exvat is not None:
            min_price_gross_10 = (break_even_exvat + (0.1 * token_cost_exvat)) * 1.2
        max_price_gross_current = (_to_float(buy_box_used) * 1.15) if _to_float(buy_box_used) is not None else None

        output_rows.append(
            {
                "asof_date": row_asof,
                "marketplace": row_market,
                "sku": row_sku,
                "asin": row_asin,
                "buy_box_price_raw_gross": buy_box_raw,
                "buy_box_price_used_gross": buy_box_used,
                "buy_box_channel": buy_box_channel,
                "buy_box_seller_id": buy_box_seller_id,
                "buy_box_missing_flag": buy_box_missing_flag,
                "buy_box_fallback_used_flag": buy_box_fallback_used_flag,
                "lowest_offer_price_gross": _fmt_num(lowest_offer),
                "lowest_fba_price_gross": _fmt_num(lowest_fba_num),
                "lowest_fbm_price_gross": _fmt_num(lowest_fbm_num),
                "highest_offer_price_gross": _fmt_num(highest_offer),
                "median_offer_price_gross": _fmt_num(median_offer),
                "price_spread_gross": _fmt_num(spread),
                "offer_count_total": str(offer_count_total_num),
                "offer_count_fba": str(offer_count_fba_num),
                "offer_count_fbm": str(offer_count_fbm_num),
                "amazon_present_flag": "1" if amazon_present else "0",
                "seller_entry_count_today": str(entry_count),
                "seller_exit_count_today": str(exit_count),
                "our_delivery_days": our_delivery_days,
                "buy_box_delivery_days": buy_box_delivery_days,
                "delivery_parity_flag": delivery_parity_flag,
                "prime_eligible_flag": prime_eligible_flag,
                "break_even_exvat_gbp": _fmt_num(break_even_exvat),
                "break_even_gross_gbp": _fmt_num(break_even_gross),
                "token_cost_exvat_gbp": _fmt_num(token_cost_exvat),
                "min_price_gross_10pct": _fmt_num(min_price_gross_10),
                "max_price_gross_current": _fmt_num(max_price_gross_current),
            }
        )

    snapshot = pd.DataFrame(output_rows, dtype=str).fillna("")
    snapshot = _ensure_columns(snapshot, REQUIRED_COLUMNS)
    snapshot = snapshot.sort_values(["marketplace", "sku", "asin"], kind="stable")

    snapshot_path = OUT / f"hos_daily_market_snapshot_{asof_date}.csv"
    OUT.mkdir(parents=True, exist_ok=True)
    snapshot.to_csv(snapshot_path, index=False)

    existing = _read_csv(HISTORY_OUTPUT_PATH)
    existing = _ensure_columns(existing, REQUIRED_COLUMNS) if not existing.empty else pd.DataFrame(columns=REQUIRED_COLUMNS)
    combined = pd.concat([existing, snapshot], ignore_index=True)
    key = (
        combined["asof_date"].astype(str)
        + "||"
        + combined["marketplace"].astype(str)
        + "||"
        + combined["sku"].astype(str)
        + "||"
        + combined["asin"].astype(str)
    )
    combined = combined.assign(_k=key).drop_duplicates(subset=["_k"], keep="last").drop(columns=["_k"])
    combined = _ensure_columns(combined, REQUIRED_COLUMNS)
    combined = combined.sort_values(["asof_date", "marketplace", "sku", "asin"], kind="stable")
    combined.to_csv(HISTORY_OUTPUT_PATH, index=False)

    print(f"created_snapshot={snapshot_path.as_posix()}")
    print(f"snapshot_rows={len(snapshot)}")
    print(f"history_file={HISTORY_OUTPUT_PATH.as_posix()}")
    print(f"history_rows={len(combined)}")
    print(f"buy_box_fallback_used_count={fallback_count}")
    print(f"buy_box_missing_count={missing_buy_box_count}")
    print(f"inferred_our_seller_id={our_seller_id}")


if __name__ == "__main__":
    main()
