from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
CONFIG = ROOT / "config"

PRODUCT_DB_PATH = OUT / "product_db_preview.csv"
MERCHANT_LISTINGS_PATH = OUT / "merchant_listings_latest.csv"
INVENTORY_SUMMARIES_PATH = OUT / "inventory_summaries.csv"
STOCK_SNAPSHOT_LATEST_PATH = OUT / "parking" / "stock_snapshot_latest.csv"
SKU_SWITCHES_PATH = CONFIG / "h_sku_switches.csv"
LEGACY_WRITER_MODES_PATH = CONFIG / "phase1_writer_modes.csv"
SCOPE_OUTPUT_PATH = OUT / "phase1_sku_scope.csv"

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


def _latest_inventory_snapshot_path() -> Path | None:
    files = sorted(OUT.glob("inventory_snapshot_*.csv"))
    if not files:
        return None
    return files[-1]


def _first_numeric(row: dict[str, str], candidates: list[str]) -> float | None:
    for col in candidates:
        if col not in row:
            continue
        parsed = _to_float(row.get(col, ""))
        if parsed is not None:
            return parsed
    return None


def _load_inventory_qty_map() -> dict[str, float]:
    candidates: list[Path] = []
    latest_inventory = _latest_inventory_snapshot_path()
    if latest_inventory is not None:
        candidates.append(latest_inventory)
    if INVENTORY_SUMMARIES_PATH.exists():
        candidates.append(INVENTORY_SUMMARIES_PATH)
    if STOCK_SNAPSHOT_LATEST_PATH.exists():
        candidates.append(STOCK_SNAPSHOT_LATEST_PATH)

    sku_cols = ["seller_sku", "sku", "seller-sku", "SKU", "SellerSKU"]
    available_cols = ["available", "available_qty", "stock_available", "stock"]
    total_cols = ["total_quantity", "total_qty", "stock_total", "quantity"]

    for path in candidates:
        try:
            df = pd.read_csv(path, dtype=str).fillna("")
        except Exception:
            continue
        if df.empty:
            continue

        sku_col = ""
        for candidate in sku_cols:
            if candidate in df.columns:
                sku_col = candidate
                break
        if not sku_col:
            continue

        qty_by_sku: dict[str, float] = {}
        for _, src in df.iterrows():
            row = {str(k): _norm(v) for k, v in src.to_dict().items()}
            sku = _norm(row.get(sku_col, "")).upper()
            if not sku:
                continue
            available_qty = _first_numeric(row, available_cols)
            total_qty = _first_numeric(row, total_cols)
            qty = available_qty
            if (qty is None or qty <= 0) and total_qty is not None:
                qty = total_qty
            if qty is None:
                continue
            prev = qty_by_sku.get(sku)
            if prev is None or float(qty) > float(prev):
                qty_by_sku[sku] = float(qty)
        if qty_by_sku:
            return qty_by_sku
    return {}


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


def _parse_switch_bool(value: object, default: str) -> str:
    text = _norm(value).lower()
    if text in TRUTHY:
        return "1"
    if text in {"0", "false", "no", "n", "off"}:
        return "0"
    return default


def _load_switch_map(path: Path = SKU_SWITCHES_PATH) -> dict[str, dict[str, str]]:
    if not path.exists():
        return _load_legacy_switch_map(LEGACY_WRITER_MODES_PATH)
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return {}
    if "sku" not in df.columns:
        return {}
    if "pricing_writer_mode" in df.columns and "observe_enabled" not in df.columns and "write_enabled" not in df.columns:
        return _load_legacy_switch_map(path)

    out: dict[str, dict[str, str]] = {}
    for _, row in df.iterrows():
        sku = _norm(row.get("sku", "")).upper()
        if not sku:
            continue
        out[sku] = {
            "observe_enabled": _parse_switch_bool(row.get("observe_enabled", ""), "1"),
            "write_enabled": _parse_switch_bool(row.get("write_enabled", ""), "0"),
            "manual_disable": _parse_switch_bool(row.get("manual_disable", ""), "0"),
        }
    return out


def _load_legacy_switch_map(path: Path = LEGACY_WRITER_MODES_PATH) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return {}
    if "sku" not in df.columns or "pricing_writer_mode" not in df.columns:
        return {}

    out: dict[str, dict[str, str]] = {}
    for _, row in df.iterrows():
        sku = _norm(row.get("sku", "")).upper()
        if not sku:
            continue
        mode = _norm(row.get("pricing_writer_mode", "")).upper()
        out[sku] = {
            "observe_enabled": "1",
            "write_enabled": "1" if mode == "CODEX_H" else "0",
            "manual_disable": "0",
        }
    return out


def _inventory_in_stock_flag(sku: str, stock_qty_by_sku: dict[str, float]) -> tuple[str, list[str]]:
    qty = stock_qty_by_sku.get(_norm(sku).upper())
    if qty is None:
        return "0", ["PARK_STOCK_UNKNOWN", "PARK_OUT_OF_STOCK"]
    if float(qty) > 0:
        return "1", []
    return "0", ["PARK_OUT_OF_STOCK"]


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
    stock_qty_by_sku: dict[str, float],
    sku_switches: dict[str, dict[str, str]],
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
        switches = sku_switches.get(sku, {})
        observe_enabled = _norm(switches.get("observe_enabled", "1")) or "1"
        write_enabled = _norm(switches.get("write_enabled", "0")) or "0"
        manual_disable = _norm(switches.get("manual_disable", "0")) or "0"
        in_stock_flag, stock_reasons = _inventory_in_stock_flag(sku, stock_qty_by_sku)
        parked_reasons: list[str] = []
        # Parked semantics: no stock means no monitoring; stock means keep watching.
        # Sale status and merchant status do not park by themselves.
        parked_reasons.extend(stock_reasons)
        parked_flag = "1" if parked_reasons else "0"
        repricing_reasons: list[str] = []
        if merchant_status != "active":
            repricing_reasons.append("inactive")
        if manual_disable == "1":
            repricing_reasons.append("manual_disable")
        if parked_flag == "1":
            repricing_reasons.append("parked")
            if "PARK_OUT_OF_STOCK" in stock_reasons:
                repricing_reasons.append("out_of_stock")
        repricing_enabled = "0" if repricing_reasons else "1"
        observe_effective = observe_enabled
        write_effective = "1" if (write_enabled == "1" and repricing_enabled == "1") else "0"
        writer_mode = "CODEX_H" if write_effective == "1" else "READ_ONLY"
        reason_code = "|".join(sorted(set(repricing_reasons))) if repricing_reasons else "eligible"

        if parked_flag == "1":
            cpt_tier = "PARKED"
        elif write_effective == "1":
            cpt_tier = "ACTIVE_WRITE"
        else:
            cpt_tier = "ACTIVE_READONLY"

        rows.append(
            {
                "asof_utc": asof_utc,
                "asof": asof_utc,
                "sku": sku,
                "asin": asin,
                "sale_status": sale_status,
                "merchant_status": merchant_status,
                "in_stock_flag": in_stock_flag,
                "manually_disabled": manual_disable,
                "repricing_enabled": repricing_enabled,
                "observe_enabled": observe_enabled,
                "write_enabled": write_enabled,
                "observe_effective": observe_effective,
                "write_effective": write_effective,
                "reason_code": reason_code,
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
    sku_switches_path: Path = SKU_SWITCHES_PATH,
    writer_modes_path: Path | None = None,
) -> pd.DataFrame:
    asof = _norm(asof_utc) or _now_utc_iso()
    product_db = _load_product_db_map(product_db_path)
    merchant = _load_merchant_map(merchant_path)
    listing = _load_listing_map(listing_snapshot_path)
    stock_qty_by_sku = _load_inventory_qty_map()
    switches_path = writer_modes_path if writer_modes_path is not None else sku_switches_path
    sku_switches = _load_switch_map(switches_path)
    rows = _build_scope_rows(
        asof_utc=asof,
        product_db=product_db,
        merchant=merchant,
        listing=listing,
        stock_qty_by_sku=stock_qty_by_sku,
        sku_switches=sku_switches,
    )
    cols = [
        "asof_utc",
        "asof",
        "sku",
        "asin",
        "sale_status",
        "merchant_status",
        "in_stock_flag",
        "manually_disabled",
        "repricing_enabled",
        "observe_enabled",
        "write_enabled",
        "observe_effective",
        "write_effective",
        "reason_code",
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
    sku_switches_path: Path = SKU_SWITCHES_PATH,
    writer_modes_path: Path | None = None,
) -> tuple[pd.DataFrame, Path]:
    df = build_scope_df(
        asof_utc=asof_utc,
        product_db_path=product_db_path,
        merchant_path=merchant_path,
        listing_snapshot_path=listing_snapshot_path,
        sku_switches_path=sku_switches_path,
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

