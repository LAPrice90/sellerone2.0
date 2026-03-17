"""
Build a master order file using the highest available level (L3 > L2 > L1).

Inputs:
- out/financial_events_level1.csv
- out/financial_events_level2.csv
- out/financial_events_level3_official.csv

Outputs:
- out/order_master.csv
- Sheet tab Order_Master (same sheet as other outputs)
"""

from __future__ import annotations

import os
from pathlib import Path
import time
from typing import Dict, Tuple
from datetime import datetime, timezone

import pandas as pd
import gspread
from gspread.exceptions import APIError

L1_PATH = Path("out/financial_events_level1.csv")
L2_PATH = Path("out/financial_events_level2.csv")
L3_PATH = Path("out/financial_events_level3_official.csv")
OUT_PATH = Path("out/order_master.csv")
OUT_PATH_SKU = Path("out/order_master_sku_preview.csv")
OUT_PATH_PREV = Path("out/order_master_prev.csv")
LOG_PATH = Path("out/B004_build_order_master.log")
ORDERS_ALL = Path("out/orders_all.csv")
TOKEN_COGS = Path("out/token_cogs_ledger.csv")
L3_ORPHANS_PATH = Path("out/l3_orphans.csv")
L1_MISSING_FEE_KEYS = Path("out/l1_missing_fee_keys.csv")
MISSING_TOKEN_ORDERS = Path("out/orders_missing_tokens.csv")

SHEET_ID = os.environ.get("ORDER_MASTER_SHEET_ID", "1BHueJTk4dvvhIXypzh6i2hQTgc0pB3DWj2khQ2IT6_A")
TAB_NAME = os.environ.get("ORDER_MASTER_TAB", "Order_Master")
SKIP_SHEETS = os.environ.get("ORDER_MASTER_SKIP_SHEETS", "0").strip() == "1"
if os.environ.get("B_CYCLE_QUIET", "0").strip() == "1":
    SKIP_SHEETS = True
SKU_FILTER = os.environ.get("ORDER_MASTER_SKU_FILTER", "").strip()
INCREMENTAL = os.environ.get("ORDER_MASTER_INCREMENTAL", "0").strip() == "1"
MASTER_MIN_DATE = os.environ.get("ORDER_MASTER_MIN_DATE", "").strip()
L1_STABLE_SECONDS = int(os.environ.get("ORDER_MASTER_L1_STABLE_SECONDS", "60").strip() or "60")
L3_MIN_ORDER_AGE_DAYS = float(
    os.environ.get("ORDER_MASTER_L3_MIN_ORDER_AGE_DAYS", "14").strip() or "14"
)

SHEETS_MAX_RETRIES = 5
SHEETS_BACKOFF = 2.0

MASTER_COLS = [
    "Date",
    "Order ID",
    "lvl",
    "country_code",
    "SKU",
    "Quantity Ordered",
    "currency_code",
    "Price_Total",
    "Price_VAT",
    "Price_ExVAT",
    "Shipping_Total",
    "Shipping_VAT",
    "Shipping_ExVAT",
    "Gift_Total",
    "Gift_VAT",
    "Gift_ExVAT",
    "Promotion_Total",
    "Promotion_VAT",
    "Promotion_ExVAT",
    "COGS_Total",
    "COGS_VAT",
    "COGS_ExVAT",
    "FBA_Fee_Total",
    "FBA_Fee_VAT",
    "FBA_Fee_ExVAT",
    "Commission_Total",
    "Commission_VAT",
    "Commission_ExVAT",
    "Digital_Fee_Total",
    "Digital_Fee_VAT",
    "Digital_Fee_ExVAT",
    "FixedClosingFee_Total",
    "FixedClosingFee_VAT",
    "FixedClosingFee_ExVAT",
    "Margin_ExVAT",
    "Margin_Pct",
]

LOCK_ON_L3_COLS = {c for c in MASTER_COLS if c.endswith(("_Total", "_VAT", "_ExVAT"))}


def get_gspread_client() -> gspread.Client:
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        cred_path = str(Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=cred_path)


def write_tab_with_retry(sheet: gspread.Spreadsheet, tab_name: str, df: pd.DataFrame) -> None:
    payload = [list(df.columns)] + df.fillna("").astype(str).values.tolist()
    for attempt in range(1, SHEETS_MAX_RETRIES + 1):
        try:
            try:
                ws = sheet.worksheet(tab_name)
            except gspread.WorksheetNotFound:
                ws = sheet.add_worksheet(title=tab_name, rows=max(len(payload) + 10, 2000), cols=max(len(df.columns) + 5, 40))
            else:
                ws.clear()
            ws.update(range_name="A1", values=payload)
            return
        except APIError:
            if attempt == SHEETS_MAX_RETRIES:
                raise
            time.sleep(SHEETS_BACKOFF * attempt)


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str)


def _is_recently_modified(path: Path, seconds: int) -> bool:
    try:
        mtime = path.stat().st_mtime
    except Exception:
        return False
    return (time.time() - mtime) < float(seconds)


def _key(row: pd.Series) -> Tuple[str, str]:
    return (str(row.get("Order ID", "")).strip(), str(row.get("SKU", "")).strip())


def _index_by_key(df: pd.DataFrame) -> Dict[Tuple[str, str], pd.Series]:
    return {_key(row): row for _, row in df.iterrows()}


def _pick_value(row: pd.Series, col: str) -> str:
    if col not in row:
        return ""
    val = row[col]
    if pd.isna(val):
        return ""
    return str(val)


def _group_level1(l1: pd.DataFrame) -> pd.DataFrame:
    if l1.empty:
        return l1
    group_cols = ["Order ID", "SKU"]
    for col in group_cols:
        if col not in l1.columns:
            l1[col] = ""
    numeric_cols = [c for c in l1.columns if c == "Quantity Ordered" or c.endswith(("_Total", "_VAT", "_ExVAT"))]
    rows = []
    for (order_id, sku), grp in l1.groupby(group_cols):
        base: Dict[str, str] = {"Order ID": order_id, "SKU": sku}
        if "Date" in grp.columns:
            dates = grp["Date"].astype(str)
            base["Date"] = next((v for v in dates if v and v not in ("nan", "None")), "")
        for col in numeric_cols:
            if col not in grp.columns:
                continue
            vals = pd.to_numeric(grp[col], errors="coerce")
            if not vals.notna().any():
                continue
            total = float(vals.fillna(0).sum())
            if col == "Quantity Ordered":
                base[col] = str(int(round(total)))
            else:
                base[col] = f"{total:.2f}"
        for col in grp.columns:
            if col in base or col in group_cols:
                continue
            series = grp[col].astype(str)
            base[col] = next((v for v in series if v and v not in ("nan", "None")), "")
        rows.append(base)
    return pd.DataFrame(rows)


def _load_marketplace_map() -> Dict[str, Dict[str, str]]:
    path = Path("out/marketplace_participations.csv")
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path, dtype=str)
    except Exception:
        return {}
    if df.empty:
        return {}
    if "marketplace_id" not in df.columns:
        return {}
    return {
        str(r.get("marketplace_id")): {
            "country_code": str(r.get("country_code") or ""),
            "currency_code": str(r.get("default_currency") or ""),
        }
        for _, r in df.iterrows()
    }


def _load_orders_marketplace_map() -> Dict[str, Dict[str, str]]:
    if not ORDERS_ALL.exists():
        return {}
    try:
        df = pd.read_csv(ORDERS_ALL, dtype=str)
    except Exception:
        return {}
    if df.empty or "amazon_order_id" not in df.columns:
        return {}
    return {
        str(r.get("amazon_order_id")): {
            "marketplace_id": str(r.get("marketplace_id") or ""),
            "ship_country_code": str(r.get("ship_country_code") or ""),
        }
        for _, r in df.iterrows()
    }


def _load_token_cogs() -> pd.DataFrame:
    if not TOKEN_COGS.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(TOKEN_COGS, dtype=str)
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return pd.DataFrame()
    df = df.rename(columns={"order_id": "Order ID", "seller_sku": "SKU"})
    if "cogs_exvat" in df.columns:
        df["cogs_exvat"] = pd.to_numeric(df.get("cogs_exvat"), errors="coerce").fillna(0.0)
        df["cogs_vat"] = pd.to_numeric(df.get("cogs_vat"), errors="coerce").fillna(0.0)
        df["cogs_total"] = pd.to_numeric(df.get("cogs_total"), errors="coerce").fillna(0.0)
        df = df.groupby(["Order ID", "SKU"], as_index=False)[["cogs_exvat", "cogs_vat", "cogs_total"]].sum()
    else:
        df["token_cost"] = pd.to_numeric(df.get("token_cost"), errors="coerce").fillna(0.0)
        df = df.groupby(["Order ID", "SKU"], as_index=False)["token_cost"].sum()
        df.rename(columns={"token_cost": "cogs_exvat"}, inplace=True)
        df["cogs_vat"] = 0.0
        df["cogs_total"] = df["cogs_exvat"]
    return df


def _build_key_series(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series([], dtype=str)
    if "Order ID" not in df.columns or "SKU" not in df.columns:
        return pd.Series([""] * len(df), index=df.index, dtype=str)
    return df["Order ID"].astype(str).str.strip() + "||" + df["SKU"].astype(str).str.strip()


def _parse_utc(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _missing_token_cogs_mask(df_master: pd.DataFrame) -> pd.Series:
    if "Quantity Ordered" not in df_master.columns or "COGS_ExVAT" not in df_master.columns:
        return pd.Series([False] * len(df_master), index=df_master.index)

    qty_raw = df_master["Quantity Ordered"].astype(str).str.strip()
    qty_vals = pd.to_numeric(qty_raw, errors="coerce").fillna(0.0)
    has_qty = qty_raw.ne("") & qty_vals.gt(0)
    cogs_ex = pd.to_numeric(df_master["COGS_ExVAT"], errors="coerce").fillna(0.0)
    master_keys = _build_key_series(df_master)

    token_cogs_latest = _load_token_cogs()
    if token_cogs_latest.empty:
        return has_qty & cogs_ex.eq(0.0)

    token_cogs_latest = token_cogs_latest.copy()
    token_cogs_latest["__key"] = _build_key_series(token_cogs_latest)
    token_cogs_latest["__cogs_ex"] = pd.to_numeric(token_cogs_latest.get("cogs_exvat"), errors="coerce").fillna(0.0)
    token_valid_keys = set(token_cogs_latest.loc[token_cogs_latest["__cogs_ex"].gt(0.0), "__key"].tolist())

    # A row is missing token COGS only when it has quantity but no valid token key.
    # Do not treat it as missing just because COGS_ExVAT is currently zero/blank
    # if a valid token allocation exists for the same Order ID + SKU.
    return has_qty & (~master_keys.isin(token_valid_keys))


def _write_missing_token_orders_from_l1(l1_grouped: pd.DataFrame) -> None:
    detail_cols = ["Order ID", "SKU", "Date", "lvl", "Quantity Ordered", "currency_code"]
    if l1_grouped.empty:
        MISSING_TOKEN_ORDERS.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=detail_cols).to_csv(MISSING_TOKEN_ORDERS, index=False)
        return

    scan = l1_grouped.copy()
    for col in detail_cols + ["COGS_ExVAT"]:
        if col not in scan.columns:
            scan[col] = ""
    scan["lvl"] = scan["lvl"].astype(str).where(scan["lvl"].astype(str).str.strip().ne(""), "1")
    missing = _missing_token_cogs_mask(scan)
    if missing.any():
        out = scan.loc[missing, detail_cols].copy()
    else:
        out = pd.DataFrame(columns=detail_cols)
    MISSING_TOKEN_ORDERS.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(MISSING_TOKEN_ORDERS, index=False)


def _index_rows(df: pd.DataFrame) -> Dict[Tuple[str, str], pd.Series]:
    if df.empty:
        return {}
    return {_key(row): row for _, row in df.iterrows()}


def _get_existing_master() -> pd.DataFrame:
    if not OUT_PATH.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(OUT_PATH, dtype=str)
        # Drop any unexpected columns to avoid corrupt headers carrying forward.
        keep_cols = [c for c in df.columns if c in MASTER_COLS]
        if keep_cols:
            df = df[keep_cols]
        # Drop fully blank rows and rows with no Order ID / SKU to avoid polluting incremental keys.
        if "Order ID" in df.columns and "SKU" in df.columns:
            df = df[~(df["Order ID"].isna() & df["SKU"].isna())]
            df = df[~(df["Order ID"].astype(str).str.strip() == "")]
            df = df[~(df["SKU"].astype(str).str.strip() == "")]
        return df
    except Exception:
        return pd.DataFrame()


def main() -> None:
    start_ts = time.monotonic()

    def _log(stage: str, extra: Dict[str, object] | None = None) -> None:
        payload: Dict[str, object] = {
            "status": "info",
            "stage": stage,
            "elapsed_s": round(time.monotonic() - start_ts, 2),
        }
        if extra:
            payload.update(extra)
        print(payload)
        try:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with LOG_PATH.open("a", encoding="utf-8") as fh:
                fh.write(str(payload) + "\n")
        except Exception:
            pass

    _log("load_inputs")
    if L1_PATH.exists() and _is_recently_modified(L1_PATH, L1_STABLE_SECONDS):
        print(
            {
                "status": "warning",
                "reason": "level1_recently_modified",
                "path": str(L1_PATH),
                "stable_seconds_required": L1_STABLE_SECONDS,
            }
        )
        print({"status": "error", "error": "Level 1 file still updating. Retry after it stabilizes."})
        raise SystemExit(1)
    l1 = _load_csv(L1_PATH)
    l2 = _load_csv(L2_PATH)
    l3 = _load_csv(L3_PATH)

    if l1.empty:
        print({"status": "error", "error": "Level 1 file missing or empty", "path": str(L1_PATH)})
        raise SystemExit(1)

    _log("group_level1", {"l1_rows": len(l1), "l2_rows": len(l2), "l3_rows": len(l3)})
    l1_grouped = _group_level1(l1)
    if SKU_FILTER:
        l1_grouped = l1_grouped[l1_grouped.get("SKU", "").astype(str) == SKU_FILTER]
        l2 = l2[l2.get("SKU", "").astype(str) == SKU_FILTER] if not l2.empty else l2
        l3 = l3[l3.get("SKU", "").astype(str) == SKU_FILTER] if not l3.empty else l3
    l2_map = _index_by_key(l2)
    l3_map = _index_by_key(l3)
    mp_map = _load_marketplace_map()
    orders_map = _load_orders_marketplace_map()
    now_utc = datetime.now(timezone.utc)

    def _l3_allowed(key: Tuple[str, str], l1_row: pd.Series | None) -> bool:
        if key not in l3_map:
            return False
        # Keep recent orders on Level 2 until they age into Level 3 eligibility.
        if L3_MIN_ORDER_AGE_DAYS <= 0:
            return True
        date_val = _pick_value(l1_row, "Date") if l1_row is not None else ""
        order_dt = _parse_utc(date_val)
        if order_dt is None:
            # If order date is unavailable, preserve previous behavior.
            return True
        age_days = (now_utc - order_dt).total_seconds() / 86400.0
        return age_days >= L3_MIN_ORDER_AGE_DAYS

    existing_master = pd.DataFrame()
    existing_index: Dict[Tuple[str, str], pd.Series] = {}
    if INCREMENTAL:
        existing_master = _get_existing_master()
        if SKU_FILTER and not existing_master.empty:
            existing_master = existing_master[existing_master.get("SKU", "").astype(str) == SKU_FILTER]
        existing_index = _index_rows(existing_master)

    l1_index = _index_rows(l1_grouped)
    base_keys = set(l1_index.keys())
    _log("index_ready", {"l1_keys": len(l1_index), "all_keys": len(base_keys), "incremental": INCREMENTAL})

    # In incremental mode, Order_Master must remain a strict subset of current L1 keys.
    # If a key disappears from L1 (for example canceled order now filtered out), purge it
    # from existing master so health checks do not retain stale orphan rows.
    if INCREMENTAL and not existing_master.empty:
        stale_existing_keys = set(existing_index.keys()) - base_keys
        if stale_existing_keys:
            existing_master = existing_master[
                ~existing_master.apply(
                    lambda r: (
                        str(r.get("Order ID", "")).strip(),
                        str(r.get("SKU", "")).strip(),
                    )
                    in stale_existing_keys,
                    axis=1,
                )
            ].copy()
            existing_index = _index_rows(existing_master)
            print(
                {
                    "status": "warning",
                    "reason": "dropped_master_keys_not_in_l1",
                    "rows": len(stale_existing_keys),
                }
            )

    # L3 orphans: L3 keys not in L1 (should never enter Order_Master).
    if l3_map and l1_index:
        l3_only_keys = sorted(set(l3_map.keys()) - set(l1_index.keys()))
    else:
        l3_only_keys = []
    if l3_only_keys:
        orphan_rows = [{"Order ID": k[0], "SKU": k[1]} for k in l3_only_keys]
        L3_ORPHANS_PATH.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(orphan_rows).to_csv(L3_ORPHANS_PATH, index=False)
    else:
        # Always write a header-only file to keep downstream checks stable.
        L3_ORPHANS_PATH.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["Order ID", "SKU"]).to_csv(L3_ORPHANS_PATH, index=False)

    # Determine which keys actually need rebuilding in incremental mode.
    keys_to_update = set(base_keys)
    if INCREMENTAL and existing_index:
        # If master is missing any L1 keys, force a full rebuild to avoid blank rows.
        missing_keys = base_keys - set(existing_index.keys())
        if missing_keys:
            print({"status": "warning", "reason": "incremental_missing_l1_keys", "missing": len(missing_keys)})
            keys_to_update = set(base_keys)
        else:
            keys_to_update = set()
        # New orders not in master.
        if keys_to_update:
            # already full rebuild
            pass
        else:
            keys_to_update |= {k for k in base_keys if k not in existing_index}
        # Orders that just got Level 2 or Level 3 data.
        for k in l2_map.keys():
            if k in existing_index and str(existing_index[k].get("lvl", "")) in ("0", "1"):
                keys_to_update.add(k)
        for k in l3_map.keys():
            l1_row = l1_index.get(k)
            if not _l3_allowed(k, l1_row):
                continue
            if k in existing_index and str(existing_index[k].get("lvl", "")) != "3":
                keys_to_update.add(k)
        # Orders that now have token COGS but were blank before.
        token_cogs = _load_token_cogs()
        if SKU_FILTER and not token_cogs.empty:
            token_cogs = token_cogs[token_cogs.get("SKU", "").astype(str) == SKU_FILTER]
        if not token_cogs.empty:
            token_idx = {(str(r.get("Order ID", "")).strip(), str(r.get("SKU", "")).strip()) for _, r in token_cogs.iterrows()}
            for k in token_idx:
                if k in existing_index:
                    existing_cogs = str(existing_index[k].get("COGS_ExVAT", "") or "").strip()
                    if existing_cogs in ("", "0", "0.0", "0.00"):
                        keys_to_update.add(k)
        # Orders where L1 now has values but master is still zeroed.
        l1_value_cols = [c for c in MASTER_COLS if c == "Quantity Ordered" or c.endswith(("_Total", "_VAT", "_ExVAT"))]

        def _row_has_nonzero(r: pd.Series) -> bool:
            for col in l1_value_cols:
                val = r.get(col, "")
                try:
                    if float(val) > 0:
                        return True
                except Exception:
                    if str(val).strip() not in ("", "0", "0.0", "0.00"):
                        return True
            return False

        for k, l1_row in l1_index.items():
            if k in existing_index:
                if _row_has_nonzero(l1_row) and not _row_has_nonzero(existing_index[k]):
                    keys_to_update.add(k)
        # Backfill derived country/currency when existing master is blank.
        for k, existing_row in existing_index.items():
            if k not in l1_index:
                continue
            existing_country = _pick_value(existing_row, "country_code").strip()
            existing_currency = _pick_value(existing_row, "currency_code").strip()
            if existing_country and existing_currency:
                continue
            l1_row = l1_index.get(k)
            if l1_row is None:
                continue
            l1_market_id = _pick_value(l1_row, "marketplace_id").strip()
            if l1_market_id:
                keys_to_update.add(k)
                continue
            order_id = _pick_value(l1_row, "Order ID").strip()
            if order_id and order_id in orders_map:
                keys_to_update.add(k)
        # If nothing changed, skip heavy rebuild when we are not writing sheets.
        if not keys_to_update and SKIP_SHEETS:
            print({"status": "skipped", "reason": "no_changes_incremental", "rows": len(existing_master)})
            return

    _log("keys_to_update", {"keys": len(keys_to_update)})

    rows = []
    # Use L1 as the default base when present; otherwise create a blank base row.
    for key in (keys_to_update if INCREMENTAL and existing_index else base_keys):
        row = l1_index.get(key)
        if row is None:
            row = pd.Series({"Order ID": key[0], "SKU": key[1]})
        market_id = _pick_value(row, "marketplace_id")
        market_meta = mp_map.get(market_id, {})
        country = market_meta.get("country_code", "")
        currency = market_meta.get("currency_code", "")
        # Use L1 quantity only for cancel detection; blank is unknown.
        qty_for_level = _pick_value(row, "Quantity Ordered")
        try:
            is_canceled = (str(qty_for_level).strip() != "") and (float(qty_for_level) <= 0)
        except Exception:
            is_canceled = False

        if is_canceled:
            use = row
            level = "0"
        elif _l3_allowed(key, row):
            use = l3_map[key]
            level = "3"
        elif key in l2_map:
            use = l2_map[key]
            level = "2"
        else:
            use = row
            level = "1"

        if not market_id:
            market_id = _pick_value(use, "marketplace_id")
            market_meta = mp_map.get(market_id, {})
            country = market_meta.get("country_code", "") or country
            currency = market_meta.get("currency_code", "") or currency
        if not market_id:
            order_id = _pick_value(row, "Order ID")
            market_id = orders_map.get(order_id, {}).get("marketplace_id", "")
            market_meta = mp_map.get(market_id, {})
            country = market_meta.get("country_code", "") or country
            currency = market_meta.get("currency_code", "") or currency
            if not country:
                country = orders_map.get(order_id, {}).get("ship_country_code", "") or country

        out = {c: "" for c in MASTER_COLS}
        out["lvl"] = level
        out["country_code"] = country
        out["currency_code"] = currency

        # If L3 lacks promo breakdowns, backfill from L2 to preserve discounts.
        if level == "3" and key in l2_map:
            l2_row = l2_map[key]
            for col in ["Promotion_Total", "Promotion_VAT", "Promotion_ExVAT"]:
                if _pick_value(use, col) in ("", None):
                    use = use.copy()
                    use[col] = _pick_value(l2_row, col)
        for col in MASTER_COLS:
            if col == "Date":
                # Order date must always come from L1.
                out[col] = _pick_value(row, col)
                continue
            if col == "lvl":
                continue
            if col == "country_code":
                continue
            if col == "currency_code":
                continue
            if col.startswith("COGS_"):
                out[col] = _pick_value(row, col)
                continue
            if col == "Quantity Ordered":
                # Quantity must always come from L1.
                out[col] = _pick_value(row, col)
                continue
            if level == "3" and col in LOCK_ON_L3_COLS:
                out[col] = _pick_value(use, col)
            else:
                out[col] = _pick_value(use, col) or _pick_value(row, col)
        rows.append(out)

    df_master = pd.DataFrame(rows, columns=MASTER_COLS)

    # Backfill any missing L1 keys into master (safe guard for blank/omitted rows).
    # IMPORTANT: In incremental mode we already have a full master; backfilling here
    # would overwrite existing country/currency with blanks for untouched rows.
    if not l1_grouped.empty and not INCREMENTAL:
        l1_grouped = l1_grouped.copy()
        # Ensure required cols exist in L1 grouped.
        for col in MASTER_COLS:
            if col not in l1_grouped.columns:
                l1_grouped[col] = ""
        l1_keys = set((l1_grouped["Order ID"].astype(str).str.strip() + "||" + l1_grouped["SKU"].astype(str).str.strip()).tolist())
        master_keys = set((df_master["Order ID"].astype(str).str.strip() + "||" + df_master["SKU"].astype(str).str.strip()).tolist())
        missing_keys = l1_keys - master_keys
        if missing_keys:
            add_rows = []
            for _, r in l1_grouped.iterrows():
                key = f"{str(r.get('Order ID', '')).strip()}||{str(r.get('SKU', '')).strip()}"
                if key in missing_keys:
                    out = {c: "" for c in MASTER_COLS}
                    out["lvl"] = "1"
                    for col in MASTER_COLS:
                        if col in ("lvl",):
                            continue
                        if col in l1_grouped.columns:
                            out[col] = _pick_value(r, col)
                    add_rows.append(out)
            if add_rows:
                df_master = pd.concat([df_master, pd.DataFrame(add_rows, columns=MASTER_COLS)], ignore_index=True)
    if INCREMENTAL and existing_index:
        # If nothing to update, keep the existing master.
        if df_master.empty:
            df_master = existing_master.copy()
        else:
            # Merge updated rows into existing master.
            if not existing_master.empty:
                # Ensure existing master only has expected columns.
                existing_master = existing_master[[c for c in existing_master.columns if c in MASTER_COLS]].copy()
                # Ensure all expected columns exist.
                for col in MASTER_COLS:
                    if col not in existing_master.columns:
                        existing_master[col] = ""
                existing_master = existing_master.set_index(["Order ID", "SKU"])
                df_master = df_master.set_index(["Order ID", "SKU"])
                existing_master.update(df_master)
                # Add brand new keys from df_master.
                # Use concat instead of `loc[idx] = row` because tuple indices on a
                # MultiIndex DataFrame can be interpreted as (row, col) selectors.
                new_rows = df_master.loc[~df_master.index.isin(existing_master.index)]
                if not new_rows.empty:
                    existing_master = pd.concat([existing_master, new_rows], axis=0)
                df_master = existing_master.reset_index()
                # Enforce column order.
                df_master = df_master[[c for c in MASTER_COLS if c in df_master.columns]]
    token_cogs = _load_token_cogs()
    if SKU_FILTER and not token_cogs.empty:
        token_cogs = token_cogs[token_cogs.get("SKU", "").astype(str) == SKU_FILTER]
    if not token_cogs.empty:
        # Normalize keys and apply token COGS via explicit key maps.
        # This avoids fragile frame merge behavior when index/column state drifts in incremental runs.
        for key_col in ["Order ID", "SKU"]:
            if key_col in df_master.columns:
                df_master[key_col] = df_master[key_col].astype(str).str.strip()
            if key_col in token_cogs.columns:
                token_cogs[key_col] = token_cogs[key_col].astype(str).str.strip()
        df_master["__key"] = _build_key_series(df_master)
        token_cogs["__key"] = _build_key_series(token_cogs)
        cogs_ex_map = pd.to_numeric(token_cogs.get("cogs_exvat"), errors="coerce")
        cogs_vat_map = pd.to_numeric(token_cogs.get("cogs_vat"), errors="coerce")
        cogs_total_map = pd.to_numeric(token_cogs.get("cogs_total"), errors="coerce")
        cogs_ex_lookup = pd.Series(cogs_ex_map.values, index=token_cogs["__key"]).to_dict()
        cogs_vat_lookup = pd.Series(cogs_vat_map.values, index=token_cogs["__key"]).to_dict()
        cogs_total_lookup = pd.Series(cogs_total_map.values, index=token_cogs["__key"]).to_dict()
        mapped_ex = pd.to_numeric(df_master["__key"].map(cogs_ex_lookup), errors="coerce")
        mapped_vat = pd.to_numeric(df_master["__key"].map(cogs_vat_lookup), errors="coerce")
        mapped_total = pd.to_numeric(df_master["__key"].map(cogs_total_lookup), errors="coerce")
        if "COGS_Total" in df_master.columns:
            existing_total = pd.to_numeric(df_master["COGS_Total"], errors="coerce")
            df_master["COGS_Total"] = mapped_total.where(mapped_total.gt(0), existing_total).fillna(0.0).round(2)
        if "COGS_ExVAT" in df_master.columns:
            existing_ex = pd.to_numeric(df_master["COGS_ExVAT"], errors="coerce")
            df_master["COGS_ExVAT"] = mapped_ex.where(mapped_ex.gt(0), existing_ex).fillna(0.0).round(2)
        if "COGS_VAT" in df_master.columns:
            existing_vat = pd.to_numeric(df_master["COGS_VAT"], errors="coerce")
            df_master["COGS_VAT"] = mapped_vat.where(mapped_ex.gt(0), existing_vat).fillna(0.0).round(2)
        df_master.drop(columns=["__key"], inplace=True, errors="ignore")

    # If quantity is explicitly zero (cancelled), force COGS to zero to avoid phantom costs.
    # Do NOT treat blank/missing quantity as cancelled.
    if "Quantity Ordered" in df_master.columns:
        qty_raw = df_master["Quantity Ordered"].astype(str).str.strip()
        qty_vals = pd.to_numeric(qty_raw, errors="coerce")
        cancelled = qty_raw.ne("") & qty_vals.fillna(0.0).le(0)
        for col in ["COGS_Total", "COGS_ExVAT", "COGS_VAT"]:
            if col in df_master.columns:
                df_master.loc[cancelled, col] = 0.0
    fee_cols = [
        "FBA_Fee_Total",
        "FBA_Fee_VAT",
        "FBA_Fee_ExVAT",
        "Commission_Total",
        "Commission_VAT",
        "Commission_ExVAT",
        "Digital_Fee_Total",
        "Digital_Fee_VAT",
        "Digital_Fee_ExVAT",
        "FixedClosingFee_Total",
        "FixedClosingFee_VAT",
        "FixedClosingFee_ExVAT",
    ]
    for col in fee_cols:
        if col in df_master.columns:
            vals = pd.to_numeric(df_master[col], errors="coerce")
            df_master[col] = vals.where(vals.isna() | (vals <= 0), -vals).astype(object)
    cogs_cols = ["COGS_Total", "COGS_VAT", "COGS_ExVAT"]
    for col in cogs_cols:
        if col in df_master.columns:
            vals = pd.to_numeric(df_master[col], errors="coerce")
            df_master[col] = vals.where(vals.isna() | (vals <= 0), -vals).astype(object)
    promo_cols = ["Promotion_Total", "Promotion_VAT", "Promotion_ExVAT"]
    for col in promo_cols:
        if col in df_master.columns:
            vals = pd.to_numeric(df_master[col], errors="coerce")
            df_master[col] = vals.where(vals.isna() | (vals <= 0), -vals).astype(object)

    # Enforce rule: do not include Level 1 rows unless fee fields are fully populated.
    if "lvl" in df_master.columns and "Quantity Ordered" in df_master.columns:
        qty_raw = df_master["Quantity Ordered"].astype(str).str.strip()
        qty_vals = pd.to_numeric(qty_raw, errors="coerce")
        has_qty = qty_raw.ne("") & qty_vals.fillna(0.0).gt(0)
        is_l1 = df_master["lvl"].astype(str).str.strip().eq("1")
        # Required Level 1 fee groups. Digital fee is optional and can be validly zero.
        fee_groups = [
            ["FBA_Fee_Total", "FBA_Fee_VAT", "FBA_Fee_ExVAT"],
            ["Commission_Total", "Commission_VAT", "Commission_ExVAT"],
        ]
        missing_fee = pd.Series(False, index=df_master.index)
        for cols in fee_groups:
            existing = [c for c in cols if c in df_master.columns]
            if not existing:
                continue
            vals = df_master[existing].apply(pd.to_numeric, errors="coerce")
            any_nan = vals.isna().any(axis=1)
            all_zero = vals.fillna(0).abs().eq(0).all(axis=1)
            missing_fee |= (any_nan | all_zero)
        token_cogs_latest = _load_token_cogs()
        has_token_cogs = pd.Series(False, index=df_master.index)
        if not token_cogs_latest.empty:
            token_cogs_latest = token_cogs_latest.copy()
            token_cogs_latest["__key"] = _build_key_series(token_cogs_latest)
            token_cogs_latest["__cogs_ex"] = pd.to_numeric(
                token_cogs_latest.get("cogs_exvat"), errors="coerce"
            ).fillna(0.0)
            token_valid_keys = set(
                token_cogs_latest.loc[token_cogs_latest["__cogs_ex"].gt(0.0), "__key"].tolist()
            )
            master_keys = _build_key_series(df_master)
            has_token_cogs = master_keys.isin(token_valid_keys)
        else:
            cogs_vals = pd.to_numeric(df_master.get("COGS_ExVAT", 0.0), errors="coerce").fillna(0.0)
            has_token_cogs = cogs_vals.abs().gt(0.0)
        drop_mask = is_l1 & has_qty & missing_fee & (~has_token_cogs)
        if drop_mask.any():
            print({"status": "warning", "reason": "dropped_l1_missing_fees", "rows": int(drop_mask.sum())})
            try:
                drop_rows = df_master.loc[drop_mask, ["Order ID", "SKU"]].copy()
                L1_MISSING_FEE_KEYS.parent.mkdir(parents=True, exist_ok=True)
                drop_rows.to_csv(L1_MISSING_FEE_KEYS, index=False)
            except Exception:
                pass
            df_master = df_master.loc[~drop_mask].copy()
        else:
            # Keep an empty file for schema stability.
            try:
                L1_MISSING_FEE_KEYS.parent.mkdir(parents=True, exist_ok=True)
                pd.DataFrame(columns=["Order ID", "SKU"]).to_csv(L1_MISSING_FEE_KEYS, index=False)
            except Exception:
                pass

    # If quantity is explicitly zero (cancelled), force level=0 and zero out all monetary fields.
    # Do NOT treat blank/missing quantity as cancelled.
    if "Quantity Ordered" in df_master.columns:
        qty_raw = df_master["Quantity Ordered"].astype(str).str.strip()
        qty_vals = pd.to_numeric(qty_raw, errors="coerce")
        cancelled = qty_raw.ne("") & qty_vals.fillna(0.0).le(0)
        df_master.loc[cancelled, "lvl"] = "0"
        money_cols = [c for c in df_master.columns if c.endswith(("_Total", "_VAT", "_ExVAT"))]
        for col in money_cols:
            df_master.loc[cancelled, col] = 0.0

    # Hold back orders missing token COGS (qty > 0 and COGS_ExVAT missing or zero).
    # This prevents publish from halting while keeping token-backed COGS only.
    if "Quantity Ordered" in df_master.columns and "COGS_ExVAT" in df_master.columns:
        missing_cogs = _missing_token_cogs_mask(df_master)
        if missing_cogs.any():
            print({"status": "warning", "reason": "held_back_missing_token_cogs", "rows": int(missing_cogs.sum())})
            df_master = df_master.loc[~missing_cogs].copy()

    # Final guard: recheck for missing token COGS immediately before write.
    # This catches any late-arriving rows that slipped through earlier transforms.
    if "Quantity Ordered" in df_master.columns and "COGS_ExVAT" in df_master.columns:
        missing_cogs = _missing_token_cogs_mask(df_master)
        if missing_cogs.any():
            print({"status": "warning", "reason": "held_back_missing_token_cogs_final", "rows": int(missing_cogs.sum())})
            df_master = df_master.loc[~missing_cogs].copy()

    # Margin (ex-VAT): revenue ex-VAT minus fee/cogs ex-VAT (use absolute fee values).
    # Important: revenue/fees are in order currency, COGS are in GBP.
    # Convert COGS to order currency for margin calc using fx_rates_daily.
    def _to_num(series_name: str) -> pd.Series:
        return pd.to_numeric(df_master.get(series_name, 0.0), errors="coerce").fillna(0.0)

    rev_ex = _to_num("Price_ExVAT") + _to_num("Shipping_ExVAT") + _to_num("Gift_ExVAT") + _to_num("Promotion_ExVAT")
    fee_ex = (
        _to_num("FBA_Fee_ExVAT").abs()
        + _to_num("Commission_ExVAT").abs()
        + _to_num("Digital_Fee_ExVAT").abs()
        + _to_num("FixedClosingFee_ExVAT").abs()
    )
    cogs_ex_gbp = _to_num("COGS_ExVAT").abs()
    cogs_ex_order = cogs_ex_gbp.copy()
    fx_missing = 0
    try:
        fx = pd.read_csv(OUT / "fx_rates_daily.csv", dtype=str).fillna("")
        fx["rate_to_gbp"] = pd.to_numeric(fx.get("rate_to_gbp"), errors="coerce")
        # Join by order date and currency_code
        fx_map = fx.set_index(["date", "currency"])["rate_to_gbp"]
        order_dates = pd.to_datetime(df_master.get("Date", ""), errors="coerce", utc=True).dt.strftime("%Y-%m-%d")
        order_ccy = df_master.get("currency_code", "").astype(str).str.strip().str.upper()
        rate_to_gbp = [
            fx_map.get((d, c), None) if d and c else None
            for d, c in zip(order_dates, order_ccy)
        ]
        rate_to_gbp = pd.to_numeric(pd.Series(rate_to_gbp), errors="coerce")
        # GBP -> order currency conversion: GBP / rate_to_gbp (since rate_to_gbp is 1 CCY in GBP)
        mask = (order_ccy.ne("GBP")) & rate_to_gbp.notna() & rate_to_gbp.gt(0)
        cogs_ex_order = cogs_ex_gbp.where(~mask, cogs_ex_gbp / rate_to_gbp)
        fx_missing = int(((order_ccy.ne("GBP")) & (~mask)).sum())
    except Exception:
        fx_missing = -1
    if fx_missing > 0:
        print({"status": "warning", "reason": "fx_missing_for_margin", "rows": fx_missing})
    margin_ex = rev_ex - fee_ex - cogs_ex_order
    df_master["Margin_ExVAT"] = margin_ex.round(2)
    df_master["Margin_Pct"] = (margin_ex / rev_ex.replace(0, pd.NA) * 100.0).round(2)
    df_master["__date"] = pd.to_datetime(df_master["Date"], errors="coerce", utc=True)
    if MASTER_MIN_DATE:
        try:
            min_dt = pd.to_datetime(MASTER_MIN_DATE + "T00:00:00Z", utc=True)
            df_master = df_master[df_master["__date"] >= min_dt]
        except Exception:
            pass
    df_master = df_master.sort_values(by=["__date", "Order ID", "SKU"], kind="mergesort").drop(columns=["__date"])
    # Clean stale blank-SKU rows if a real SKU exists for the same order.
    if "Order ID" in df_master.columns and "SKU" in df_master.columns:
        has_sku = df_master["SKU"].astype(str).str.strip().ne("")
        orders_with_real_sku = set(df_master.loc[has_sku, "Order ID"].astype(str))
        blank_sku = df_master["SKU"].astype(str).str.strip().eq("")
        if orders_with_real_sku:
            df_master = df_master[~(blank_sku & df_master["Order ID"].astype(str).isin(orders_with_real_sku))]
        # If blank SKU rows remain, try to fill from L1 grouped when the order has exactly one SKU.
        if blank_sku.any() and not l1_grouped.empty:
            l1_counts = l1_grouped.groupby("Order ID")["SKU"].nunique()
            single_sku_orders = set(l1_counts[l1_counts == 1].index.astype(str))
            if single_sku_orders:
                fillable = blank_sku & df_master["Order ID"].astype(str).isin(single_sku_orders)
                if fillable.any():
                    l1_lookup = l1_grouped.set_index("Order ID")
                    for idx, row in df_master[fillable].iterrows():
                        order_id = str(row.get("Order ID", "")).strip()
                        if order_id in l1_lookup.index:
                            l1_row = l1_lookup.loc[order_id]
                            if isinstance(l1_row, pd.DataFrame):
                                l1_row = l1_row.iloc[0]
                            df_master.at[idx, "SKU"] = _pick_value(l1_row, "SKU")
                            df_master.at[idx, "Date"] = _pick_value(l1_row, "Date")
                            df_master.at[idx, "Quantity Ordered"] = _pick_value(l1_row, "Quantity Ordered")
                            df_master.at[idx, "lvl"] = "1"
    # Drop rows with blank SKU or blank Date to avoid phantom orders.
    if "SKU" in df_master.columns and "Date" in df_master.columns:
        sku_blank = df_master["SKU"].astype(str).str.strip().eq("")
        date_blank = df_master["Date"].astype(str).str.strip().eq("")
        df_master = df_master[~(sku_blank | date_blank)]
    # Strict final guard: never keep qty>0 rows with zero/blank token COGS.
    # This catches any late transformations that might reintroduce zero-cogs rows.
    if "Quantity Ordered" in df_master.columns and "COGS_ExVAT" in df_master.columns:
        missing_cogs = _missing_token_cogs_mask(df_master)
        if missing_cogs.any():
            print({"status": "warning", "reason": "held_back_missing_token_cogs_prewrite", "rows": int(missing_cogs.sum())})
            df_master = df_master.loc[~missing_cogs].copy()
    # Always publish a deterministic missing-token key list from current L1 scope.
    _write_missing_token_orders_from_l1(l1_grouped)
    _log("write_local")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    skip_sheets = SKIP_SHEETS
    if SKU_FILTER:
        # Never overwrite the main Order_Master with a SKU-only build.
        df_master.to_csv(OUT_PATH_SKU, index=False)
        skip_sheets = True
    else:
        # Keep a simple previous snapshot for shrink detection.
        if OUT_PATH.exists():
            try:
                OUT_PATH_PREV.write_bytes(OUT_PATH.read_bytes())
            except Exception:
                pass
        df_master.to_csv(OUT_PATH, index=False)

    if not skip_sheets:
        _log("write_sheet_start", {"rows": len(df_master)})
        try:
            client = get_gspread_client()
            sheet = client.open_by_key(SHEET_ID)
            write_tab_with_retry(sheet, TAB_NAME, df_master)
        except Exception as exc:
            print({"status": "warning", "alert": "sheets_error", "error": str(exc)})
        _log("write_sheet_end")

    snapshot_path = OUT_PATH_SKU if SKU_FILTER else OUT_PATH
    print({"status": "success", "rows": len(df_master), "snapshot": str(snapshot_path)})


if __name__ == "__main__":
    main()

