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
    from scripts.core.storage import StorageConfig, connect_store, parse_storage_mode, replace_table_from_dataframe
except ModuleNotFoundError:
    from core.out_paths import resolve_compat_path
    from core.storage import StorageConfig, connect_store, parse_storage_mode, replace_table_from_dataframe


OUT_DIR = Path("out")
ALLOC_REL = "token_allocations_live.csv"
LEDGER_REL = "token_ledger_live.csv"
PRODUCT_DB = OUT_DIR / "product_db_preview.csv"

OUT_LEDGER = OUT_DIR / "token_cogs_ledger.csv"
SQL_TABLE = "b_token_cogs_ledger"
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


def _merge_allocations_with_ledger_fallback(alloc_ledger: pd.DataFrame, base_ledger: pd.DataFrame) -> pd.DataFrame:
    if alloc_ledger is None or alloc_ledger.empty:
        return base_ledger.copy()
    if base_ledger is None or base_ledger.empty:
        return alloc_ledger.copy()

    all_cols = list(dict.fromkeys(list(alloc_ledger.columns) + list(base_ledger.columns)))
    primary = alloc_ledger.reindex(columns=all_cols, fill_value="").copy()
    fallback = base_ledger.reindex(columns=all_cols, fill_value="").copy()
    if "order_id" not in primary.columns or "seller_sku" not in primary.columns:
        return primary.reset_index(drop=True)
    if "order_id" not in fallback.columns or "seller_sku" not in fallback.columns:
        return primary.reset_index(drop=True)

    primary_counts = primary.groupby(["order_id", "seller_sku"]).size().to_dict()
    existing_token_ids = (
        set(primary["token_id"].astype(str))
        if "token_id" in primary.columns
        else set()
    )

    supplement_parts = []
    for (order_id, seller_sku), group in fallback.groupby(["order_id", "seller_sku"], dropna=False):
        needed = len(group.index) - int(primary_counts.get((order_id, seller_sku), 0))
        if needed <= 0:
            continue
        candidates = group.copy()
        if "token_id" in candidates.columns:
            candidates = candidates[~candidates["token_id"].astype(str).isin(existing_token_ids)].copy()
        if candidates.empty:
            continue
        supplement = candidates.head(int(needed)).copy()
        supplement_parts.append(supplement)
        if "token_id" in supplement.columns:
            existing_token_ids.update(supplement["token_id"].astype(str).tolist())

    if not supplement_parts:
        return primary.reset_index(drop=True)

    combined = pd.concat([primary] + supplement_parts, ignore_index=True)
    return combined.reset_index(drop=True)


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


def _write_ledger_outputs(ledger: pd.DataFrame) -> dict[str, object]:
    mode = parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE", "csv"))
    sql_result: dict[str, object] | None = None

    def write_csv() -> None:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ledger.to_csv(OUT_LEDGER, index=False)

    def write_sql() -> dict[str, object]:
        config = StorageConfig.from_env()
        store = connect_store(config)
        try:
            return replace_table_from_dataframe(store, SQL_TABLE, ledger)
        finally:
            store.close()

    if mode == "sql_primary_csv_export":
        sql_result = write_sql()
        write_csv()
    elif mode == "sql_shadow":
        write_csv()
        sql_result = write_sql()
    else:
        write_csv()

    return {
        "mode": mode,
        "csv_path": str(OUT_LEDGER),
        "sql_table": SQL_TABLE if sql_result else "",
        "sql_rows": int(sql_result["rows"]) if sql_result else 0,
    }


def main() -> None:
    alloc_ledger = load_from_allocations()
    base_ledger = load_from_ledger()
    if base_ledger.empty and alloc_ledger.empty:
        print({"status": "skip", "reason": "no_allocations_or_ledger_allocs"})
        return
    if not alloc_ledger.empty:
        # Explicit allocation rows win, but supplement missing token_ids from the ledger.
        ledger = _merge_allocations_with_ledger_fallback(alloc_ledger, base_ledger)
    else:
        ledger = base_ledger

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

    output = _write_ledger_outputs(ledger)

    print({"status": "success", "rows": len(ledger), "snapshot": str(OUT_LEDGER), **output})


if __name__ == "__main__":
    main()

