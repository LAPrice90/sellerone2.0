from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import pandas as pd

OUT = Path("out")
PERF_PATH = OUT / "sku_performance_summary.csv"

REQUIRED_COLUMNS: List[str] = [
    "asof_date",
    "marketplace",
    "sku",
    "asin",
    "our_price_gross",
    "buy_box_price_gross",
    "buy_box_price_used_gross",
    "buy_box_channel",
    "lowest_fba_price_gross",
    "lowest_fbm_price_gross",
    "offer_count_fba",
    "offer_count_fbm",
    "current_token_cost_gbp",
    "break_even_price_gbp",
    "expected_refund_cost_per_unit_gbp",
    "roi_at_our_price_pct",
    "roi_at_buy_box_price_pct",
    "min_price_gross",
    "max_price_gross",
    "posture",
    "reason_codes",
    "review_triggers",
    "notes",
]


def _norm_sku(value: object) -> str:
    return str(value or "").strip().upper()


def _to_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        s = str(value).strip()
        if not s:
            return None
        return float(s)
    except (TypeError, ValueError):
        return None


def _append_pipe_code(existing: object, code: str) -> str:
    if not code:
        return str(existing or "")
    tokens = [t for t in str(existing or "").split("|") if t]
    if code not in tokens:
        tokens.append(code)
    return "|".join(tokens)


def _pick_first_price(row: pd.Series, fields: List[str]) -> tuple[float | None, str]:
    for field in fields:
        value = _to_float(row.get(field, ""))
        if value is not None:
            return value, field
    return None, ""


def _vat_rate_pct_from_row(row: pd.Series) -> float:
    # Match E-cycle fallback behavior when VAT context is unavailable.
    return 20.0


def _posture_from_roi(roi_at_buy_box_pct: float | None) -> str:
    if roi_at_buy_box_pct is None:
        return "investigate"
    if roi_at_buy_box_pct < 10.0:
        return "step_back"
    return "compete"


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _latest_listing_snapshot_path() -> Path | None:
    files = sorted(OUT.glob("listing_offer_snapshot_*.csv"))
    if not files:
        return None
    return files[-1]


def _latest_market_snapshot_path() -> Path | None:
    files = sorted(OUT.glob("hos_daily_market_snapshot_*.csv"))
    if not files:
        return None
    return files[-1]


def _dedupe_perf(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if "sku" not in df.columns:
        df["sku"] = ""
    df["sku_norm"] = df["sku"].map(_norm_sku)
    df = df[df["sku_norm"] != ""].copy()
    if df.empty:
        return pd.DataFrame(columns=["sku_norm"])
    if "asof_date" in df.columns:
        df["asof_dt"] = pd.to_datetime(df["asof_date"], errors="coerce")
    else:
        df["asof_dt"] = pd.NaT
    df = df.sort_values(["asof_dt"], kind="stable")
    df = df.drop_duplicates(subset=["sku_norm"], keep="last")
    return df


def _ensure_required_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[REQUIRED_COLUMNS].copy()


def _validate_required_columns(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise RuntimeError(f"Missing required output columns: {missing}")


def _sample_rows(df: pd.DataFrame, n: int = 3) -> List[Dict[str, str]]:
    cols = [
        "sku",
        "asof_date",
        "our_price_gross",
        "buy_box_price_gross",
        "current_token_cost_gbp",
        "break_even_price_gbp",
        "roi_at_buy_box_price_pct",
        "posture",
        "reason_codes",
    ]
    out: List[Dict[str, str]] = []
    for _, rec in df.head(n).iterrows():
        item: Dict[str, str] = {}
        for col in cols:
            item[col] = str(rec.get(col, "") or "")
        out.append(item)
    return out


def main() -> None:
    listing_path = _latest_listing_snapshot_path()
    if listing_path is None:
        raise FileNotFoundError("No listing snapshot found: out/listing_offer_snapshot_*.csv")

    listing = _read_csv(listing_path)
    perf = _dedupe_perf(_read_csv(PERF_PATH))
    market = _read_csv(_latest_market_snapshot_path() or Path(""))

    if listing.empty:
        out_date = datetime.now(timezone.utc).date().isoformat()
        out_path = OUT / f"hos_guidelines_snapshot_{out_date}.csv"
        empty = _ensure_required_columns(pd.DataFrame(columns=REQUIRED_COLUMNS))
        _validate_required_columns(empty)
        OUT.mkdir(parents=True, exist_ok=True)
        empty.to_csv(out_path, index=False)
        print(f"created_file={out_path.as_posix()}")
        print("row_count=0")
        print("sample_rows=[]")
        return

    listing["sku_norm"] = listing.get("sku", "").map(_norm_sku)
    merged = listing.copy()
    if not market.empty:
        if "sku" not in market.columns:
            market["sku"] = ""
        market["sku_norm"] = market["sku"].map(_norm_sku)
        market_keep = [
            "sku_norm",
            "buy_box_price_used_gross",
            "lowest_fba_price_gross",
            "lowest_fbm_price_gross",
            "offer_count_fba",
            "offer_count_fbm",
        ]
        for col in market_keep:
            if col not in market.columns:
                market[col] = ""
        market = market.sort_values(["asof_date"], kind="stable") if "asof_date" in market.columns else market
        market = market.drop_duplicates(subset=["sku_norm"], keep="last")
        merged = merged.merge(market[market_keep], on="sku_norm", how="left")
        merged = merged.fillna("")

    if not perf.empty:
        keep_cols = [
            "sku_norm",
            "current_token_cost_gbp",
            "break_even_price_gbp",
            "expected_refund_cost_per_unit_gbp",
            "roi_at_our_price_pct",
            "roi_at_buy_box_price_pct",
        ]
        for col in keep_cols:
            if col not in perf.columns:
                perf[col] = ""
        merged = merged.merge(perf[keep_cols], on="sku_norm", how="left")
        merged = merged.fillna("")
    else:
        for col in [
            "current_token_cost_gbp",
            "break_even_price_gbp",
            "expected_refund_cost_per_unit_gbp",
            "roi_at_our_price_pct",
            "roi_at_buy_box_price_pct",
        ]:
            merged[col] = ""

    merged["our_price_gross"] = merged.get("our_price", "")
    merged["buy_box_price_gross"] = merged.get("buy_box_price", "")
    merged["buy_box_price_used_gross"] = merged.get("buy_box_price_used_gross", "")
    if "buy_box_price_used_gross" in merged.columns:
        merged["buy_box_price_used_gross"] = merged["buy_box_price_used_gross"].where(
            merged["buy_box_price_used_gross"].astype(str).str.strip() != "",
            merged.get("buy_box_price", ""),
        )
    merged["lowest_fba_price_gross"] = merged.get("lowest_fba_price_gross", "")
    if "lowest_fba_price_gross" in merged.columns:
        merged["lowest_fba_price_gross"] = merged["lowest_fba_price_gross"].where(
            merged["lowest_fba_price_gross"].astype(str).str.strip() != "",
            merged.get("lowest_fba_price", ""),
        )
    merged["lowest_fbm_price_gross"] = merged.get("lowest_fbm_price_gross", "")
    if "lowest_fbm_price_gross" in merged.columns:
        merged["lowest_fbm_price_gross"] = merged["lowest_fbm_price_gross"].where(
            merged["lowest_fbm_price_gross"].astype(str).str.strip() != "",
            merged.get("lowest_fbm_price", ""),
        )
    merged["min_price_gross"] = ""
    merged["max_price_gross"] = ""
    merged["posture"] = ""
    merged["reason_codes"] = ""
    merged["review_triggers"] = ""

    if "notes" not in merged.columns:
        merged["notes"] = ""

    min_values: List[str] = []
    buy_box_used_values: List[str] = []
    max_values: List[str] = []
    reason_values: List[str] = []
    posture_values: List[str] = []
    trigger_values: List[str] = []
    for _, row in merged.iterrows():
        token_cost = _to_float(row.get("current_token_cost_gbp", ""))
        break_even = _to_float(row.get("break_even_price_gbp", ""))
        reasons = str(row.get("reason_codes", "") or "")
        posture = str(row.get("posture", "") or "")
        triggers = str(row.get("review_triggers", "") or "")
        min_price_text = ""
        max_price_text = ""
        if token_cost is not None and break_even is not None:
            vat_rate_pct = _vat_rate_pct_from_row(row)
            min_exvat = break_even + (0.10 * token_cost)
            min_gross = min_exvat * (1.0 + (vat_rate_pct / 100.0))
            min_price_text = f"{round(min_gross, 6):.6f}"
        else:
            reasons = _append_pipe_code(reasons, "missing_cost")

        anchor_price, source_field = _pick_first_price(
            row, ["buy_box_price_used_gross", "buy_box_price_gross", "lowest_fba_price_gross", "our_price_gross"]
        )
        if anchor_price is not None:
            buy_box_used_text = f"{round(anchor_price, 6):.6f}"
            max_gross = anchor_price * 1.15
            max_price_text = f"{round(max_gross, 6):.6f}"
            if source_field != "buy_box_price_used_gross":
                reasons = _append_pipe_code(reasons, "buy_box_fallback_used")
        else:
            buy_box_used_text = ""
            posture = "investigate"
            triggers = _append_pipe_code(triggers, "missing_market_price")

        roi_buy_box = _to_float(row.get("roi_at_buy_box_price_pct", ""))
        posture = _posture_from_roi(roi_buy_box) if not posture else posture

        buy_box_raw = _to_float(row.get("buy_box_price_gross", ""))
        buy_box_used = _to_float(buy_box_used_text)
        min_price_val = _to_float(min_price_text)
        max_price_val = _to_float(max_price_text)

        if buy_box_raw is None:
            triggers = _append_pipe_code(triggers, "buy_box_missing")
            reasons = _append_pipe_code(reasons, "buy_box_missing")

        if buy_box_used is not None and min_price_val is not None and buy_box_used < min_price_val:
            triggers = _append_pipe_code(triggers, "buy_box_below_floor")
        if buy_box_used is not None and max_price_val is not None and buy_box_used > max_price_val:
            triggers = _append_pipe_code(triggers, "buy_box_above_ceiling")

        min_values.append(min_price_text)
        buy_box_used_values.append(buy_box_used_text)
        max_values.append(max_price_text)
        reason_values.append(reasons)
        posture_values.append(posture)
        trigger_values.append(triggers)

    merged["min_price_gross"] = min_values
    merged["buy_box_price_used_gross"] = buy_box_used_values
    merged["max_price_gross"] = max_values
    merged["reason_codes"] = reason_values
    merged["posture"] = posture_values
    merged["review_triggers"] = trigger_values

    output = pd.DataFrame(
        {
            "asof_date": merged.get("asof_date", ""),
            "marketplace": merged.get("marketplace", ""),
            "sku": merged.get("sku", ""),
            "asin": merged.get("asin", ""),
            "our_price_gross": merged.get("our_price_gross", ""),
            "buy_box_price_gross": merged.get("buy_box_price_gross", ""),
            "buy_box_price_used_gross": merged.get("buy_box_price_used_gross", ""),
            "buy_box_channel": merged.get("buy_box_channel", ""),
            "lowest_fba_price_gross": merged.get("lowest_fba_price_gross", ""),
            "lowest_fbm_price_gross": merged.get("lowest_fbm_price_gross", ""),
            "offer_count_fba": merged.get("offer_count_fba", ""),
            "offer_count_fbm": merged.get("offer_count_fbm", ""),
            "current_token_cost_gbp": merged.get("current_token_cost_gbp", ""),
            "break_even_price_gbp": merged.get("break_even_price_gbp", ""),
            "expected_refund_cost_per_unit_gbp": merged.get("expected_refund_cost_per_unit_gbp", ""),
            "roi_at_our_price_pct": merged.get("roi_at_our_price_pct", ""),
            "roi_at_buy_box_price_pct": merged.get("roi_at_buy_box_price_pct", ""),
            "min_price_gross": merged.get("min_price_gross", ""),
            "max_price_gross": merged.get("max_price_gross", ""),
            "posture": merged.get("posture", ""),
            "reason_codes": merged.get("reason_codes", ""),
            "review_triggers": merged.get("review_triggers", ""),
            "notes": merged.get("notes", ""),
        }
    )

    if not market.empty:
        market_map: Dict[str, Dict[str, str]] = {}
        for _, rec in market.iterrows():
            sku_norm = _norm_sku(rec.get("sku_norm", rec.get("sku", "")))
            if not sku_norm:
                continue
            market_map[sku_norm] = {
                "buy_box_price_used_gross": str(rec.get("buy_box_price_used_gross", "") or ""),
                "lowest_fba_price_gross": str(rec.get("lowest_fba_price_gross", "") or ""),
                "lowest_fbm_price_gross": str(rec.get("lowest_fbm_price_gross", "") or ""),
                "offer_count_fba": str(rec.get("offer_count_fba", "") or ""),
                "offer_count_fbm": str(rec.get("offer_count_fbm", "") or ""),
            }
        sku_norm_series = output.get("sku", "").map(_norm_sku)
        for idx in output.index:
            key = sku_norm_series.iloc[idx]
            m = market_map.get(key)
            if not m:
                continue
            for col, val in m.items():
                if val:
                    output.at[idx, col] = val

    output = _ensure_required_columns(output)
    _validate_required_columns(output)

    out_date = datetime.now(timezone.utc).date().isoformat()
    out_path = OUT / f"hos_guidelines_snapshot_{out_date}.csv"
    OUT.mkdir(parents=True, exist_ok=True)
    output.to_csv(out_path, index=False)

    print(f"created_file={out_path.as_posix()}")
    print(f"row_count={len(output)}")
    print("sample_rows=")
    for row in _sample_rows(output, n=3):
        print(row)


if __name__ == "__main__":
    main()

