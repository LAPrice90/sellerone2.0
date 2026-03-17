from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
INVENTORY_SUMMARIES_PATH = OUT / "inventory_summaries.csv"
STOCK_SNAPSHOT_LATEST_PATH = OUT / "parking" / "stock_snapshot_latest.csv"
PARKED_SKUS_PATH = OUT / "parking" / "parked_skus.csv"


def _norm(value: object) -> str:
    return str(value or "").strip()


def _to_float(value: object) -> float | None:
    raw = _norm(value)
    if not raw:
        return None
    try:
        out = float(raw)
    except Exception:
        return None
    return out if out == out else None


def _mtime_iso(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return ""


def _stock_qty_map_from_path(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return {}
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
        available_qty = None
        for col in ("available", "available_qty", "stock_available", "stock"):
            if col in df.columns:
                available_qty = _to_float(row.get(col, ""))
                if available_qty is not None:
                    break
        total_qty = None
        for col in ("total_quantity", "total_qty", "stock_total", "quantity"):
            if col in df.columns:
                total_qty = _to_float(row.get(col, ""))
                if total_qty is not None:
                    break
        qty = available_qty
        if (qty is None or qty <= 0) and total_qty is not None:
            qty = total_qty
        if qty is None:
            continue
        prev = out.get(sku)
        if prev is None or qty > prev:
            out[sku] = float(qty)
    return out


def resolve_stock_qty_by_sku(
    *,
    out_dir: Path = OUT,
    inventory_summaries_path: Path = INVENTORY_SUMMARIES_PATH,
    stock_snapshot_latest_path: Path = STOCK_SNAPSHOT_LATEST_PATH,
) -> tuple[dict[str, float], Path | None, list[Path]]:
    candidates: list[Path] = []
    inventory_snapshots = sorted(out_dir.glob("inventory_snapshot_*.csv"))
    if inventory_snapshots:
        candidates.append(inventory_snapshots[-1])
    if inventory_summaries_path.exists():
        candidates.append(inventory_summaries_path)
    if stock_snapshot_latest_path.exists():
        candidates.append(stock_snapshot_latest_path)

    for path in candidates:
        qty_map = _stock_qty_map_from_path(path)
        if qty_map:
            return qty_map, path, candidates
    return {}, None, candidates


def _parked_override_skus(path: Path = PARKED_SKUS_PATH) -> set[str]:
    if not path.exists():
        return set()
    try:
        parked = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return set()
    if parked.empty or "sku" not in parked.columns:
        return set()
    return {str(v).strip().upper() for v in parked["sku"].tolist() if str(v).strip()}


def derive_required_daily_skus(
    scope_df: pd.DataFrame,
    *,
    scope_path: Path | None = None,
    parked_skus_path: Path = PARKED_SKUS_PATH,
    out_dir: Path = OUT,
    inventory_summaries_path: Path = INVENTORY_SUMMARIES_PATH,
    stock_snapshot_latest_path: Path = STOCK_SNAPSHOT_LATEST_PATH,
) -> tuple[list[str], dict[str, Any]]:
    meta: dict[str, Any] = {
        "required": 0,
        "non_parked": 0,
        "dropped": 0,
        "stock_positive": 0,
        "dropped_included_stock_positive": 0,
        "excluded_stock_zero_or_missing": 0,
        "excluded_dropped_stock_zero": 0,
        "scope_rows": int(len(scope_df.index)) if isinstance(scope_df, pd.DataFrame) else 0,
        "stock_source_path": "",
        "stock_source_mtime_utc": "",
        "stock_candidates": "",
        "scope_mtime_utc": _mtime_iso(scope_path),
        "parked_override_count": 0,
        "error": "",
    }
    if scope_df.empty or "sku" not in scope_df.columns or "parked_flag" not in scope_df.columns:
        meta["error"] = "missing_scope_or_required_columns"
        return [], meta

    scoped = scope_df.copy()
    scoped["sku_key"] = scoped["sku"].astype(str).str.strip().str.upper()
    scoped["parked_key"] = scoped["parked_flag"].astype(str).str.strip()

    non_parked_skus = set(scoped.loc[~scoped["parked_key"].eq("1"), "sku_key"].tolist())
    parked_skus = set(scoped.loc[scoped["parked_key"].eq("1"), "sku_key"].tolist())

    overrides = _parked_override_skus(parked_skus_path)
    if overrides:
        parked_skus = parked_skus.union(overrides)
        non_parked_skus = {sku for sku in non_parked_skus if sku not in parked_skus}
        meta["parked_override_count"] = len(overrides)

    dropped_skus: set[str] = set()
    sale_status_by_sku: dict[str, str] = {}
    if "sale_status" in scoped.columns:
        scoped["sale_status_key"] = scoped["sale_status"].astype(str).str.strip().str.lower()
        dropped_skus = set(scoped.loc[scoped["sale_status_key"].eq("dropped"), "sku_key"].tolist())
        sale_status_by_sku = dict(zip(scoped["sku_key"], scoped["sale_status_key"]))

    stock_qty_by_sku, stock_source_path, candidates = resolve_stock_qty_by_sku(
        out_dir=out_dir,
        inventory_summaries_path=inventory_summaries_path,
        stock_snapshot_latest_path=stock_snapshot_latest_path,
    )
    if stock_source_path is not None:
        meta["stock_source_path"] = str(stock_source_path)
        meta["stock_source_mtime_utc"] = _mtime_iso(stock_source_path)
    meta["stock_candidates"] = ",".join(str(path) for path in candidates)

    required_daily_skus: list[str] = []
    stock_positive = 0
    dropped_included_stock_positive = 0
    excluded_stock_zero_or_missing = 0
    excluded_dropped_stock_zero = 0
    for sku in sorted(non_parked_skus):
        if not sku:
            continue
        qty = float(stock_qty_by_sku.get(sku, 0.0))
        if qty <= 0:
            excluded_stock_zero_or_missing += 1
            if sale_status_by_sku.get(sku, "") == "dropped":
                excluded_dropped_stock_zero += 1
            continue
        stock_positive += 1
        required_daily_skus.append(sku)
        if sale_status_by_sku.get(sku, "") == "dropped":
            dropped_included_stock_positive += 1

    meta.update(
        {
            "required": len(required_daily_skus),
            "non_parked": len(non_parked_skus),
            "dropped": len(dropped_skus),
            "stock_positive": stock_positive,
            "dropped_included_stock_positive": dropped_included_stock_positive,
            "excluded_stock_zero_or_missing": excluded_stock_zero_or_missing,
            "excluded_dropped_stock_zero": excluded_dropped_stock_zero,
        }
    )
    return required_daily_skus, meta
