from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
CONFIG = ROOT / "config"

PRODUCT_DB_PATH = OUT / "product_db_preview.csv"
MERCHANT_LISTINGS_PATH = OUT / "merchant_listings_latest.csv"
WRITER_MODES_PATH = CONFIG / "phase1_writer_modes.csv"
SCOPE_OUTPUT_PATH = OUT / "phase1_sku_scope.csv"

ALLOWED_WRITER_MODES = {"PPP", "CODEX_H", "READ_ONLY"}
TRUTHY = {"1", "true", "yes", "y", "on"}


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm(value: object) -> str:
    return str(value or "").strip()


def _to_float(value: object) -> float | None:
    raw = _norm(value)
    if not raw:
        return None
    try:
        return float(raw)
    except Exception:
        return None


def _latest_listing_snapshot_path() -> Path | None:
    files = sorted(OUT.glob("listing_offer_snapshot_*.csv"))
    if not files:
        return None
    return files[-1]


def _load_product_db_map(path: Path = PRODUCT_DB_PATH) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return {}

    out: dict[str, dict[str, str]] = {}
    for _, row in df.iterrows():
        rec = {str(k): _norm(v) for k, v in row.to_dict().items()}
        sku = _norm(rec.get("seller_sku", "")).upper() or _norm(rec.get("sku", "")).upper()
        if not sku:
            continue
        if sku in out:
            continue
        out[sku] = rec
    return out


def _load_merchant_map(path: Path = MERCHANT_LISTINGS_PATH) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return {}

    sku_col = "seller-sku" if "seller-sku" in df.columns else ("seller_sku" if "seller_sku" in df.columns else "")
    if not sku_col:
        return {}

    out: dict[str, dict[str, str]] = {}
    for _, row in df.iterrows():
        rec = {str(k): _norm(v) for k, v in row.to_dict().items()}
        sku = _norm(rec.get(sku_col, "")).upper()
        if not sku:
            continue
        if sku in out:
            continue
        out[sku] = rec
    return out


def _load_listing_map(path: Path | None = None) -> dict[str, dict[str, str]]:
    target = path or _latest_listing_snapshot_path()
    if target is None or not target.exists():
        return {}
    try:
        df = pd.read_csv(target, dtype=str).fillna("")
    except Exception:
        return {}

    out: dict[str, dict[str, str]] = {}
    for _, row in df.iterrows():
        rec = {str(k): _norm(v) for k, v in row.to_dict().items()}
        sku = _norm(rec.get("sku", "")).upper()
        if not sku:
            continue
        if sku in out:
            continue
        out[sku] = rec
    return out


def _load_writer_mode_map(path: Path = WRITER_MODES_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return {}
    if "sku" not in df.columns or "pricing_writer_mode" not in df.columns:
        return {}

    out: dict[str, str] = {}
    for _, row in df.iterrows():
        sku = _norm(row.get("sku", "")).upper()
        if not sku:
            continue
        mode = _norm(row.get("pricing_writer_mode", "")).upper()
        if mode not in ALLOWED_WRITER_MODES:
            mode = "READ_ONLY"
        out[sku] = mode
    return out


def _listing_in_stock_flag(row: dict[str, str] | None) -> tuple[str, list[str]]:
    if row is None:
        return "0", ["PARK_NO_LISTING_ROW", "PARK_OUT_OF_STOCK"]
    reasons: list[str] = []
    we_present = _norm(row.get("we_present_flag", "")).lower() in TRUTHY
    our_price = _to_float(row.get("our_price", ""))
    if we_present or (our_price is not None and our_price > 0):
        return "1", reasons
    reasons.append("PARK_OUT_OF_STOCK")
    return "0", reasons


def _merchant_status(rec: dict[str, str] | None) -> str:
    if rec is None:
        return ""
    return _norm(rec.get("status", "")).lower()


def _sale_status(rec: dict[str, str] | None) -> str:
    if rec is None:
        return ""
    return _norm(rec.get("sale_status", "")).lower()


def _build_scope_rows(
    *,
    asof_utc: str,
    product_db: dict[str, dict[str, str]],
    merchant: dict[str, dict[str, str]],
    listing: dict[str, dict[str, str]],
    writer_modes: dict[str, str],
) -> list[dict[str, str]]:
    universe = sorted(set(product_db.keys()) | set(merchant.keys()) | set(listing.keys()))
    rows: list[dict[str, str]] = []
    for sku in universe:
        pdb = product_db.get(sku)
        mrec = merchant.get(sku)
        lrec = listing.get(sku)

        asin = _norm((lrec or {}).get("asin", "")) or _norm((mrec or {}).get("asin1", "")) or _norm((pdb or {}).get("asin", ""))
        sale_status = _sale_status(pdb)
        merchant_status = _merchant_status(mrec)
        writer_mode = writer_modes.get(sku, "READ_ONLY")
        in_stock_flag, stock_reasons = _listing_in_stock_flag(lrec)
        parked_reasons: list[str] = []
        if sale_status == "dropped":
            parked_reasons.append("PARK_SALE_STATUS_DROPPED")
        if sale_status == "discontinued":
            parked_reasons.append("PARK_SALE_STATUS_DISCONTINUED")
        if merchant_status != "active":
            parked_reasons.append("PARK_MERCHANT_INACTIVE")
        parked_reasons.extend(stock_reasons)
        parked_flag = "1" if parked_reasons else "0"

        if parked_flag == "1":
            cpt_tier = "PARKED"
        elif writer_mode == "CODEX_H":
            cpt_tier = "ACTIVE_WRITE"
        else:
            cpt_tier = "ACTIVE_READONLY"

        rows.append(
            {
                "asof_utc": asof_utc,
                "sku": sku,
                "asin": asin,
                "sale_status": sale_status,
                "merchant_status": merchant_status,
                "in_stock_flag": in_stock_flag,
                "writer_mode": writer_mode,
                "parked_flag": parked_flag,
                "park_reason_codes": "|".join(sorted(set(parked_reasons))),
                "cpt_tier": cpt_tier,
            }
        )
    return rows


def build_scope_df(
    *,
    asof_utc: str | None = None,
    product_db_path: Path = PRODUCT_DB_PATH,
    merchant_path: Path = MERCHANT_LISTINGS_PATH,
    listing_snapshot_path: Path | None = None,
    writer_modes_path: Path = WRITER_MODES_PATH,
) -> pd.DataFrame:
    asof = _norm(asof_utc) or _now_utc_iso()
    product_db = _load_product_db_map(product_db_path)
    merchant = _load_merchant_map(merchant_path)
    listing = _load_listing_map(listing_snapshot_path)
    writer_modes = _load_writer_mode_map(writer_modes_path)
    rows = _build_scope_rows(
        asof_utc=asof,
        product_db=product_db,
        merchant=merchant,
        listing=listing,
        writer_modes=writer_modes,
    )
    cols = [
        "asof_utc",
        "sku",
        "asin",
        "sale_status",
        "merchant_status",
        "in_stock_flag",
        "writer_mode",
        "parked_flag",
        "park_reason_codes",
        "cpt_tier",
    ]
    return pd.DataFrame(rows, columns=cols, dtype=str).fillna("")


def write_scope_csv(df: pd.DataFrame, output_path: Path = SCOPE_OUTPUT_PATH) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path


def build_and_write_scope(
    *,
    asof_utc: str | None = None,
    output_path: Path = SCOPE_OUTPUT_PATH,
    product_db_path: Path = PRODUCT_DB_PATH,
    merchant_path: Path = MERCHANT_LISTINGS_PATH,
    listing_snapshot_path: Path | None = None,
    writer_modes_path: Path = WRITER_MODES_PATH,
) -> tuple[pd.DataFrame, Path]:
    df = build_scope_df(
        asof_utc=asof_utc,
        product_db_path=product_db_path,
        merchant_path=merchant_path,
        listing_snapshot_path=listing_snapshot_path,
        writer_modes_path=writer_modes_path,
    )
    path = write_scope_csv(df, output_path=output_path)
    return df, path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build phase1 SKU scope with parked classifier")
    parser.add_argument("--output", default=str(SCOPE_OUTPUT_PATH), help="Output CSV path")
    parser.add_argument("--asof-utc", default="", help="Optional as-of timestamp")
    args = parser.parse_args()

    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    df, path = build_and_write_scope(asof_utc=_norm(args.asof_utc), output_path=output)

    parked = int(df["parked_flag"].astype(str).eq("1").sum()) if not df.empty else 0
    active = int(df["parked_flag"].astype(str).eq("0").sum()) if not df.empty else 0
    print(f"phase1_scope_rows={len(df.index)}")
    print(f"phase1_scope_non_parked={active}")
    print(f"phase1_scope_parked={parked}")
    print(f"phase1_scope_path={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
