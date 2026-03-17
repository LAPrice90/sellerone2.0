"""
Build a unit-level Token COGS ledger for downstream consumers.

Source priority:
- out/token_allocations_live.csv (explicit allocations)
- fallback to out/token_ledger_live.csv allocated_* fields
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import os
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.core.out_paths import resolve_compat_path
except ModuleNotFoundError:
    from core.out_paths import resolve_compat_path


OUT_DIR = Path("out")
ALLOC_REL = "token_allocations_live.csv"
LEDGER_REL = "token_ledger_live.csv"
PRODUCT_DB = OUT_DIR / "product_db_preview.csv"

OUT_LEDGER = OUT_DIR / "token_cogs_ledger.csv"
DEFAULT_VAT_RATE = float(os.environ.get("DEFAULT_COGS_VAT_RATE", "20"))


def _compat_read_path(path_rel: str) -> Path:
    resolved = resolve_compat_path(path_rel, default_system="B")
    return resolved.live_path if resolved.live_path.exists() else resolved.legacy_path


def parse_float(value) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def load_from_allocations() -> pd.DataFrame:
    alloc_path = _compat_read_path(ALLOC_REL)
    if not alloc_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(alloc_path, dtype=str).fillna("")
    if df.empty:
        return pd.DataFrame()
    df = df.rename(
        columns={
            "order_id": "order_id",
            "order_date": "order_date",
            "seller_sku": "seller_sku",
            "token_id": "token_id",
            "token_cost": "token_cost",
            "currency": "currency",
            "allocation_date": "allocation_date",
        }
    )
    df["token_cost"] = df["token_cost"].apply(parse_float)
    df["quantity"] = 1
    df["source"] = "token_allocations_live"
    return df[
        [
            "order_id",
            "order_date",
            "seller_sku",
            "token_id",
            "token_cost",
            "currency",
            "allocation_date",
            "quantity",
            "source",
        ]
    ]


def load_from_ledger() -> pd.DataFrame:
    ledger_path = _compat_read_path(LEDGER_REL)
    if not ledger_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(ledger_path, dtype=str).fillna("")
    if df.empty:
        return pd.DataFrame()
    df = df.rename(
        columns={
            "allocated_order_id": "order_id",
            "allocated_date": "order_date",
            "seller_sku": "seller_sku",
            "token_id": "token_id",
            "cost_per_unit": "token_cost",
            "currency": "currency",
        }
    )
    df = df[df["order_id"].astype(str).str.strip() != ""]
    if df.empty:
        return pd.DataFrame()
    df["token_cost"] = df["token_cost"].apply(parse_float)
    df["allocation_date"] = df.get("allocated_date", "")
    df["quantity"] = 1
    df["source"] = "token_ledger_live"
    return df[
        [
            "order_id",
            "order_date",
            "seller_sku",
            "token_id",
            "token_cost",
            "currency",
            "allocation_date",
            "quantity",
            "source",
        ]
    ]


def _load_vat_rate_map() -> dict[str, float]:
    if not PRODUCT_DB.exists():
        return {}
    try:
        df = pd.read_csv(PRODUCT_DB, dtype=str).fillna("")
    except Exception:
        return {}
    if df.empty or "seller_sku" not in df.columns:
        return {}
    vat_map: dict[str, float] = {}
    for _, row in df.iterrows():
        sku = str(row.get("seller_sku", "")).strip()
        if not sku:
            continue
        raw = row.get("last_vat_rate_pct", "")
        if raw in ("", None, "nan"):
            raw = row.get("vat_rate", "")
        try:
            rate = float(raw)
        except Exception:
            rate = DEFAULT_VAT_RATE
        vat_map[sku] = rate
    return vat_map


def main() -> None:
    alloc_ledger = load_from_allocations()
    base_ledger = load_from_ledger()
    if base_ledger.empty and alloc_ledger.empty:
        print({"status": "skip", "reason": "no_allocations_or_ledger_allocs"})
        return
    if base_ledger.empty:
        ledger = alloc_ledger
    elif alloc_ledger.empty:
        ledger = base_ledger
    else:
        # Prefer the source with fuller coverage.
        ledger = base_ledger if len(base_ledger) >= len(alloc_ledger) else alloc_ledger

    ledger = ledger.sort_values(by=["order_date", "order_id", "seller_sku", "token_id"])
    ledger["built_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    vat_map = _load_vat_rate_map()
    if vat_map:
        ledger["vat_rate_pct"] = ledger["seller_sku"].map(vat_map).fillna(DEFAULT_VAT_RATE)
    else:
        ledger["vat_rate_pct"] = DEFAULT_VAT_RATE
    ledger["cogs_exvat"] = ledger["token_cost"].round(2)
    ledger["cogs_vat"] = (ledger["cogs_exvat"] * ledger["vat_rate_pct"] / 100.0).round(2)
    ledger["cogs_total"] = (ledger["cogs_exvat"] + ledger["cogs_vat"]).round(2)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(OUT_LEDGER, index=False)

    print({"status": "success", "rows": len(ledger), "snapshot": str(OUT_LEDGER)})


if __name__ == "__main__":
    main()

