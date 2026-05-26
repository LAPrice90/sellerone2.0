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
import sys
import time
from typing import Dict, Tuple
from datetime import datetime, timezone

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    import gspread
    from gspread.exceptions import APIError
except Exception:
    gspread = None
    APIError = Exception
try:
    from scripts.core.storage import StorageConfig, connect_store, parse_storage_mode, replace_table_from_dataframe
    from scripts.flows.B._finance_io import read_finance_frame
except ModuleNotFoundError:
    from core.storage import StorageConfig, connect_store, parse_storage_mode, replace_table_from_dataframe
    from flows.B._finance_io import read_finance_frame

L1_PATH = Path("out/financial_events_level1.csv")
L2_PATH = Path("out/financial_events_level2.csv")
L3_PATH = Path("out/financial_events_level3_official.csv")
OUT_PATH = Path("out/order_master.csv")
OUT_PATH_SKU = Path("out/order_master_sku_preview.csv")
OUT_PATH_PREV = Path("out/order_master_prev.csv")
LOG_PATH = Path("out/B004_build_order_master.log")
ORDERS_ALL = Path("out/orders_all.csv")
TOKEN_COGS = Path("out/token_cogs_ledger.csv")
STOCK_RECEIPTS = Path("out/stock_receipts_latest.csv")
ORDERS_SHEET_ORDERS = Path("out/orders_sheet_orders.csv")
SQL_TABLE_ORDERS_SHEET_ORDERS = "b_orders_sheet_orders"
TOKEN_SHORTAGES = Path("out/token_shortages_by_sku.csv")
L3_ORPHANS_PATH = Path("out/l3_orphans.csv")
L1_MISSING_FEE_KEYS = Path("out/l1_missing_fee_keys.csv")
MISSING_TOKEN_ORDERS = Path("out/orders_missing_tokens.csv")
SQL_TABLE_MISSING_TOKEN_ORDERS = "b_orders_missing_tokens"
SQL_TABLE_L1_MISSING_FEE_KEYS = "b_l1_missing_fee_keys"
SQL_TABLE_L3_ORPHANS = "b_l3_orphans"
SQL_TABLE_ORDER_MASTER = "b_order_master"

SHEET_ID = os.environ.get("ORDER_MASTER_SHEET_ID", "1BHueJTk4dvvhIXypzh6i2hQTgc0pB3DWj2khQ2IT6_A")
TAB_NAME = os.environ.get("ORDER_MASTER_TAB", "Order_Master")
SKIP_SHEETS = os.environ.get("ORDER_MASTER_SKIP_SHEETS", "0").strip() == "1"
if os.environ.get("B_CYCLE_QUIET", "0").strip() == "1":
    SKIP_SHEETS = True
if gspread is None:
    SKIP_SHEETS = True
PUBLISH_EXISTING_ONLY = os.environ.get("ORDER_MASTER_PUBLISH_EXISTING_ONLY", "0").strip() == "1"
SKU_FILTER = os.environ.get("ORDER_MASTER_SKU_FILTER", "").strip()
INCREMENTAL = os.environ.get("ORDER_MASTER_INCREMENTAL", "0").strip() == "1"
MASTER_MIN_DATE = os.environ.get("ORDER_MASTER_MIN_DATE", "").strip()
L1_STABLE_SECONDS = int(os.environ.get("ORDER_MASTER_L1_STABLE_SECONDS", "60").strip() or "60")
L3_MIN_ORDER_AGE_DAYS = float(
    os.environ.get("ORDER_MASTER_L3_MIN_ORDER_AGE_DAYS", "14").strip() or "14"
)
DEFAULT_PLACEHOLDER_VAT_RATE = float(
    os.environ.get("ORDER_MASTER_PLACEHOLDER_VAT_RATE", "20").strip() or "20"
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
    "COGS_Placeholder_Applied",
    "COGS_Basis_Type",
    "COGS_Basis_Source",
    "COGS_Basis_Date",
    "Missing_Token_Flag",
    "Missing_Token_Reason",
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
    if gspread is None:
        raise RuntimeError("gspread not available")
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
    try:
        return read_finance_frame(path, dtype=str)
    except KeyError:
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path, dtype=str)
    except Exception:
        return pd.DataFrame()


def _is_recently_modified(path: Path, seconds: int) -> bool:
    if float(seconds) <= 0:
        return False
    try:
        mtime = path.stat().st_mtime
    except Exception:
        return False
    return (time.time() - mtime) < float(seconds)


def _key(row: pd.Series) -> Tuple[str, str]:
    return (str(row.get("Order ID", "")).strip(), str(row.get("SKU", "")).strip())


def _row_quality_score(row: pd.Series) -> tuple:
    qty = _to_float(_pick_value(row, "Quantity Ordered"))
    monetary_nonzero = 0
    monetary_abs_total = 0.0
    for col in row.index:
        if not str(col).endswith(("_Total", "_VAT", "_ExVAT")):
            continue
        amount = _to_float(_pick_value(row, str(col)))
        if abs(amount) <= 0:
            continue
        monetary_nonzero += 1
        monetary_abs_total += abs(amount)
    date_raw = _pick_value(row, "Date").strip()
    date_val = pd.to_datetime(date_raw, errors="coerce", utc=True)
    has_date = 0 if pd.isna(date_val) else 1
    date_ts = float("-inf") if pd.isna(date_val) else float(date_val.timestamp())
    fingerprint = "|".join(f"{col}={_pick_value(row, str(col)).strip()}" for col in sorted(row.index.astype(str)))
    return (
        1 if qty > 0 else 0,
        qty,
        monetary_nonzero,
        monetary_abs_total,
        has_date,
        date_ts,
        fingerprint,
    )


def _index_by_key(df: pd.DataFrame, *, source: str = "") -> tuple[Dict[Tuple[str, str], pd.Series], Dict[str, int | str]]:
    if df.empty:
        return {}, {"source": source, "duplicate_groups": 0, "duplicate_rows": 0}
    best_rows: Dict[Tuple[str, str], pd.Series] = {}
    best_scores: Dict[Tuple[str, str], tuple] = {}
    key_counts: Dict[Tuple[str, str], int] = {}
    for _, row in df.iterrows():
        key = _key(row)
        key_counts[key] = key_counts.get(key, 0) + 1
        score = _row_quality_score(row)
        if key not in best_rows:
            best_rows[key] = row
            best_scores[key] = score
            continue
        if score > best_scores[key]:
            best_rows[key] = row
            best_scores[key] = score
    duplicate_groups = sum(1 for count in key_counts.values() if count > 1)
    duplicate_rows = sum((count - 1) for count in key_counts.values() if count > 1)
    return best_rows, {
        "source": source,
        "duplicate_groups": int(duplicate_groups),
        "duplicate_rows": int(duplicate_rows),
    }


def _pick_value(row: pd.Series, col: str) -> str:
    if col not in row:
        return ""
    val = row[col]
    if pd.isna(val):
        return ""
    return str(val)


def _to_float(value: object) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _l2_row_is_viable(l2_row: pd.Series, l1_row: pd.Series | None) -> bool:
    """
    Guard against promoting an order to lvl=2 when the L2 row is effectively empty.
    If L1 shows sold quantity but L2 reports zero quantity with no financial payload,
    keep the row on Level 1 truth.
    """
    l2_qty = _to_float(_pick_value(l2_row, "Quantity Ordered"))
    l1_qty = _to_float(_pick_value(l1_row, "Quantity Ordered")) if l1_row is not None else 0.0

    if l1_qty <= 0:
        return True
    if l2_qty > 0:
        return True

    payload_cols = [
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
    for col in payload_cols:
        if col not in l2_row:
            continue
        raw = _pick_value(l2_row, col).strip()
        if raw == "":
            continue
        if abs(_to_float(raw)) > 0:
            return True
    return False


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
    try:
        df = _load_csv(ORDERS_ALL)
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


def _truthy_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"1", "true", "yes", "y"})


def _parse_datetime_series(series: pd.Series, *, dayfirst: bool = False) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce", utc=True, dayfirst=dayfirst)
    if parsed.notna().any():
        return parsed
    return pd.to_datetime(series, errors="coerce", utc=True, dayfirst=not dayfirst)


def _load_placeholder_cost_basis_by_sku() -> dict[str, dict[str, object]]:
    cols = ["SKU", "cost_per_unit", "basis_source", "basis_date", "basis_rank", "basis_dt"]
    frames: list[pd.DataFrame] = []

    if TOKEN_COGS.exists():
        try:
            token_rows = pd.read_csv(TOKEN_COGS, dtype=str).fillna("")
        except Exception:
            token_rows = pd.DataFrame()
        if not token_rows.empty and "seller_sku" in token_rows.columns:
            token_rows = token_rows.copy()
            token_rows["SKU"] = token_rows["seller_sku"].astype(str).str.strip().str.upper()
            token_rows["cost_per_unit"] = pd.to_numeric(token_rows.get("cogs_exvat"), errors="coerce")
            date_source = token_rows.get("order_date", pd.Series([""] * len(token_rows), index=token_rows.index)).astype(str)
            date_source = date_source.where(
                date_source.str.strip().ne(""),
                token_rows.get("allocation_date", pd.Series([""] * len(token_rows), index=token_rows.index)).astype(str),
            )
            token_rows["basis_dt"] = _parse_datetime_series(date_source)
            token_rows = token_rows[
                token_rows["SKU"].ne("")
                & token_rows["cost_per_unit"].gt(0)
                & token_rows["basis_dt"].notna()
            ].copy()
            if not token_rows.empty:
                token_rows = token_rows.sort_values(["SKU", "basis_dt"], kind="stable")
                token_rows = token_rows.drop_duplicates(subset=["SKU"], keep="last")
                token_rows["basis_source"] = "token_cogs_ledger_last_actual"
                token_rows["basis_date"] = token_rows["basis_dt"].dt.strftime("%Y-%m-%d")
                token_rows["basis_rank"] = 1
                frames.append(token_rows[cols])

    if STOCK_RECEIPTS.exists():
        try:
            receipt_rows = pd.read_csv(STOCK_RECEIPTS, dtype=str).fillna("")
        except Exception:
            receipt_rows = pd.DataFrame()
        if not receipt_rows.empty and "seller_sku" in receipt_rows.columns:
            receipt_rows = receipt_rows.copy()
            receipt_rows["SKU"] = receipt_rows["seller_sku"].astype(str).str.strip().str.upper()
            receipt_rows["cost_per_unit"] = pd.to_numeric(receipt_rows.get("cost_per_unit"), errors="coerce")
            status = receipt_rows.get("status", pd.Series([""] * len(receipt_rows), index=receipt_rows.index)).astype(str).str.strip().str.upper()
            receipt_rows["basis_dt"] = _parse_datetime_series(
                receipt_rows.get("intake_date", pd.Series([""] * len(receipt_rows), index=receipt_rows.index)).astype(str),
                dayfirst=True,
            )
            receipt_rows = receipt_rows[
                receipt_rows["SKU"].ne("")
                & receipt_rows["cost_per_unit"].gt(0)
                & receipt_rows["basis_dt"].notna()
                & (status.isin({"", "APPLIED"}))
            ].copy()
            if not receipt_rows.empty:
                receipt_rows = receipt_rows.sort_values(["SKU", "basis_dt"], kind="stable")
                receipt_rows = receipt_rows.drop_duplicates(subset=["SKU"], keep="last")
                receipt_rows["basis_source"] = "stock_receipts_latest"
                receipt_rows["basis_date"] = receipt_rows["basis_dt"].dt.strftime("%Y-%m-%d")
                receipt_rows["basis_rank"] = 2
                frames.append(receipt_rows[cols])

    try:
        purchase_rows = read_finance_frame(
            ORDERS_SHEET_ORDERS,
            SQL_TABLE_ORDERS_SHEET_ORDERS,
            dtype=str,
        ).fillna("")
    except Exception:
        purchase_rows = pd.DataFrame()
    if not purchase_rows.empty:
        if not purchase_rows.empty and "SKU" in purchase_rows.columns:
            purchase_rows = purchase_rows.copy()
            purchase_rows["SKU"] = purchase_rows["SKU"].astype(str).str.strip().str.upper()
            cost_raw = purchase_rows.get("Cost PU", pd.Series([""] * len(purchase_rows), index=purchase_rows.index)).astype(str)
            purchase_rows["cost_per_unit"] = pd.to_numeric(cost_raw.str.replace(r"[^0-9.\-]", "", regex=True), errors="coerce")
            delivered = pd.to_numeric(
                purchase_rows.get("Delivered", pd.Series([""] * len(purchase_rows), index=purchase_rows.index)).astype(str).str.replace(r"[^0-9.\-]", "", regex=True),
                errors="coerce",
            ).fillna(0.0)
            sent_to_fba = pd.to_numeric(
                purchase_rows.get("Sent to FBA", pd.Series([""] * len(purchase_rows), index=purchase_rows.index)).astype(str).str.replace(r"[^0-9.\-]", "", regex=True),
                errors="coerce",
            ).fillna(0.0)
            purchase_rows["basis_dt"] = _parse_datetime_series(
                purchase_rows.get("Order Date", pd.Series([""] * len(purchase_rows), index=purchase_rows.index)).astype(str),
                dayfirst=True,
            )
            purchase_rows = purchase_rows[
                purchase_rows["SKU"].ne("")
                & purchase_rows["cost_per_unit"].gt(0)
                & purchase_rows["basis_dt"].notna()
                & ((delivered > 0) | (sent_to_fba > 0))
            ].copy()
            if not purchase_rows.empty:
                purchase_rows = purchase_rows.sort_values(["SKU", "basis_dt"], kind="stable")
                purchase_rows = purchase_rows.drop_duplicates(subset=["SKU"], keep="last")
                purchase_rows["basis_source"] = "orders_sheet_receipted"
                purchase_rows["basis_date"] = purchase_rows["basis_dt"].dt.strftime("%Y-%m-%d")
                purchase_rows["basis_rank"] = 3
                frames.append(purchase_rows[cols])

    if not frames:
        return {}

    merged = pd.concat(frames, ignore_index=True)
    merged["basis_rank"] = pd.to_numeric(merged["basis_rank"], errors="coerce").fillna(99).astype(int)
    merged = merged.sort_values(["SKU", "basis_rank", "basis_dt"], ascending=[True, True, False], kind="stable")
    merged = merged.drop_duplicates(subset=["SKU"], keep="first")
    out: dict[str, dict[str, object]] = {}
    for _, row in merged.iterrows():
        sku = str(row.get("SKU", "")).strip().upper()
        if not sku:
            continue
        out[sku] = {
            "cost_per_unit": float(pd.to_numeric(pd.Series([row.get("cost_per_unit")]), errors="coerce").fillna(0.0).iloc[0]),
            "basis_source": str(row.get("basis_source", "")).strip(),
            "basis_date": str(row.get("basis_date", "")).strip(),
        }
    return out


def _apply_missing_token_placeholders(df_master: pd.DataFrame) -> pd.DataFrame:
    if df_master.empty:
        return df_master
    for col in [
        "COGS_Placeholder_Applied",
        "COGS_Basis_Type",
        "COGS_Basis_Source",
        "COGS_Basis_Date",
        "Missing_Token_Flag",
        "Missing_Token_Reason",
    ]:
        if col not in df_master.columns:
            df_master[col] = ""

    df_master["COGS_Placeholder_Applied"] = "0"
    df_master["COGS_Basis_Type"] = ""
    df_master["COGS_Basis_Source"] = ""
    df_master["COGS_Basis_Date"] = ""
    df_master["Missing_Token_Flag"] = "0"
    df_master["Missing_Token_Reason"] = ""

    missing_mask = _missing_token_cogs_mask(df_master)
    if not missing_mask.any():
        return df_master

    basis_by_sku = _load_placeholder_cost_basis_by_sku()
    qty_abs = pd.to_numeric(df_master.get("Quantity Ordered", 0), errors="coerce").fillna(0.0).abs()
    sku_norm = df_master.get("SKU", pd.Series([""] * len(df_master), index=df_master.index)).astype(str).str.strip().str.upper()

    for idx in df_master.index[missing_mask]:
        df_master.at[idx, "Missing_Token_Flag"] = "1"
        sku = str(sku_norm.loc[idx]).strip().upper()
        basis = basis_by_sku.get(sku)
        if not basis:
            df_master.at[idx, "Missing_Token_Reason"] = "missing_token_no_placeholder_basis"
            continue
        unit_cost = float(basis.get("cost_per_unit", 0.0) or 0.0)
        qty_val = float(qty_abs.loc[idx])
        if unit_cost <= 0 or qty_val <= 0:
            df_master.at[idx, "Missing_Token_Reason"] = "missing_token_invalid_placeholder_basis"
            continue
        cogs_ex = round(qty_val * unit_cost, 2)
        cogs_vat = round(cogs_ex * (DEFAULT_PLACEHOLDER_VAT_RATE / 100.0), 2)
        cogs_total = round(cogs_ex + cogs_vat, 2)
        df_master.at[idx, "COGS_ExVAT"] = cogs_ex
        df_master.at[idx, "COGS_VAT"] = cogs_vat
        df_master.at[idx, "COGS_Total"] = cogs_total
        df_master.at[idx, "COGS_Placeholder_Applied"] = "1"
        df_master.at[idx, "COGS_Basis_Type"] = "placeholder_last_cost"
        df_master.at[idx, "COGS_Basis_Source"] = str(basis.get("basis_source", "") or "")
        df_master.at[idx, "COGS_Basis_Date"] = str(basis.get("basis_date", "") or "")
        df_master.at[idx, "Missing_Token_Reason"] = "missing_token_placeholder_applied"
    return df_master


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


def _missing_l1_fee_mask(df_master: pd.DataFrame) -> pd.Series:
    if "lvl" not in df_master.columns or "Quantity Ordered" not in df_master.columns:
        return pd.Series([False] * len(df_master), index=df_master.index)

    qty_raw = df_master["Quantity Ordered"].astype(str).str.strip()
    qty_vals = pd.to_numeric(qty_raw, errors="coerce").fillna(0.0)
    has_qty = qty_raw.ne("") & qty_vals.gt(0)
    is_l1 = df_master["lvl"].astype(str).str.strip().eq("1")
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
    return is_l1 & has_qty & missing_fee


def _load_shortage_units_by_sku() -> dict[str, int]:
    if not TOKEN_SHORTAGES.exists():
        return {}
    try:
        shortage_df = pd.read_csv(TOKEN_SHORTAGES, dtype=str).fillna("")
    except Exception:
        return {}
    if shortage_df.empty:
        return {}
    sku_col = "seller_sku" if "seller_sku" in shortage_df.columns else "SKU" if "SKU" in shortage_df.columns else ""
    units_col = (
        "missing_qty"
        if "missing_qty" in shortage_df.columns
        else "missing_units"
        if "missing_units" in shortage_df.columns
        else "shortage_units"
        if "shortage_units" in shortage_df.columns
        else ""
    )
    if not sku_col or not units_col:
        return {}
    shortage_df["__sku"] = shortage_df[sku_col].astype(str).str.strip().str.upper()
    shortage_df["__units"] = pd.to_numeric(shortage_df[units_col], errors="coerce").fillna(0.0)
    grouped = shortage_df.groupby("__sku", dropna=False)["__units"].sum()
    return {str(sku): int(round(float(units))) for sku, units in grouped.items() if str(sku).strip()}


def _write_missing_token_orders(df_master: pd.DataFrame) -> None:
    detail_cols = [
        "Order ID",
        "SKU",
        "Date",
        "lvl",
        "Quantity Ordered",
        "currency_code",
        "placeholder_applied_flag",
        "placeholder_cost_per_unit",
        "placeholder_total_cogs",
        "placeholder_basis_source",
        "placeholder_basis_date",
        "missing_token_reason_class",
        "receipt_state_class",
        "token_shortage_units",
    ]
    if df_master.empty:
        _write_output_frame(pd.DataFrame(columns=detail_cols), MISSING_TOKEN_ORDERS, SQL_TABLE_MISSING_TOKEN_ORDERS)
        return

    scan = df_master.copy()
    base_cols = [
        "Order ID",
        "SKU",
        "Date",
        "lvl",
        "Quantity Ordered",
        "currency_code",
        "COGS_ExVAT",
        "COGS_Placeholder_Applied",
        "COGS_Basis_Source",
        "COGS_Basis_Date",
        "Missing_Token_Reason",
    ]
    for col in base_cols:
        if col not in scan.columns:
            scan[col] = ""
    if "lvl" in scan.columns:
        scan["lvl"] = scan["lvl"].astype(str).where(scan["lvl"].astype(str).str.strip().ne(""), "1")
    missing = _missing_token_cogs_mask(scan)
    if not missing.any():
        out = pd.DataFrame(columns=detail_cols)
    else:
        out = scan.loc[missing, base_cols].copy()
        out["placeholder_applied_flag"] = _truthy_series(out["COGS_Placeholder_Applied"]).astype(int)
        qty_abs = pd.to_numeric(out["Quantity Ordered"], errors="coerce").fillna(0.0).abs()
        placeholder_total = pd.to_numeric(out["COGS_ExVAT"], errors="coerce").fillna(0.0).abs()
        placeholder_total = placeholder_total.where(out["placeholder_applied_flag"].eq(1), 0.0).round(2)
        out["placeholder_total_cogs"] = placeholder_total
        per_unit = (placeholder_total / qty_abs.replace(0.0, pd.NA)).round(4)
        out["placeholder_cost_per_unit"] = per_unit.where(out["placeholder_applied_flag"].eq(1), "")
        out["placeholder_basis_source"] = out["COGS_Basis_Source"].astype(str).str.strip()
        out["placeholder_basis_date"] = out["COGS_Basis_Date"].astype(str).str.strip()
        out["missing_token_reason_class"] = out["Missing_Token_Reason"].astype(str).str.strip()
        out["missing_token_reason_class"] = out["missing_token_reason_class"].where(
            out["missing_token_reason_class"].ne(""),
            "missing_token_unclassified",
        )
        shortage_map = _load_shortage_units_by_sku()
        out["token_shortage_units"] = (
            out["SKU"].astype(str).str.strip().str.upper().map(shortage_map).fillna(0).astype(int)
        )
        out["receipt_state_class"] = "token_missing_basis_unknown"
        out.loc[
            out["placeholder_applied_flag"].eq(1) & out["token_shortage_units"].gt(0),
            "receipt_state_class",
        ] = "placeholder_applied_shortage_open"
        out.loc[
            out["placeholder_applied_flag"].eq(1) & out["token_shortage_units"].eq(0),
            "receipt_state_class",
        ] = "placeholder_applied"
        out.loc[
            out["placeholder_applied_flag"].eq(0) & out["token_shortage_units"].gt(0),
            "receipt_state_class",
        ] = "shortage_open"
        out = out[detail_cols].copy()
    MISSING_TOKEN_ORDERS.parent.mkdir(parents=True, exist_ok=True)
    _write_output_frame(out, MISSING_TOKEN_ORDERS, SQL_TABLE_MISSING_TOKEN_ORDERS)


def _write_output_frame(df: pd.DataFrame, path: Path, sql_table: str) -> dict[str, object]:
    mode = parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE", "csv"))
    sql_rows = 0

    def write_csv() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)

    def write_sql() -> None:
        nonlocal sql_rows
        store = connect_store(StorageConfig.from_env())
        try:
            result = replace_table_from_dataframe(store, sql_table, df)
        finally:
            store.close()
        sql_rows = int(result["rows"])

    if mode == "sql_primary_csv_export":
        write_sql()
        write_csv()
    elif mode == "sql_shadow":
        write_csv()
        write_sql()
    else:
        write_csv()

    return {"mode": mode, "sql_table": sql_table if mode != "csv" else "", "sql_rows": sql_rows}


def _write_l1_missing_fee_keys(df_master: pd.DataFrame) -> int:
    detail_cols = ["Order ID", "SKU", "Date", "lvl", "Quantity Ordered"]
    if df_master.empty:
        _write_output_frame(pd.DataFrame(columns=detail_cols), L1_MISSING_FEE_KEYS, SQL_TABLE_L1_MISSING_FEE_KEYS)
        return 0

    scan = df_master.copy()
    for col in detail_cols:
        if col not in scan.columns:
            scan[col] = ""
    missing = _missing_l1_fee_mask(scan)
    if missing.any():
        out = scan.loc[missing, detail_cols].copy()
    else:
        out = pd.DataFrame(columns=detail_cols)
    L1_MISSING_FEE_KEYS.parent.mkdir(parents=True, exist_ok=True)
    _write_output_frame(out, L1_MISSING_FEE_KEYS, SQL_TABLE_L1_MISSING_FEE_KEYS)
    return int(missing.sum())


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

    if PUBLISH_EXISTING_ONLY:
        _log("publish_existing_only_start")
        if not OUT_PATH.exists():
            print({"status": "error", "error": "Order_Master artifact missing", "path": str(OUT_PATH)})
            raise SystemExit(1)
        try:
            df_master = pd.read_csv(OUT_PATH, dtype=str).fillna("")
        except Exception as exc:
            print({"status": "error", "error": f"Order_Master artifact unreadable: {exc}", "path": str(OUT_PATH)})
            raise SystemExit(1)
        if SKIP_SHEETS:
            print(
                {
                    "status": "success",
                    "rows": len(df_master),
                    "snapshot": str(OUT_PATH),
                    "publish_existing_only": True,
                    "write_sheets": False,
                }
            )
            return
        _log("write_sheet_start", {"rows": len(df_master), "publish_existing_only": 1})
        try:
            client = get_gspread_client()
            sheet = client.open_by_key(SHEET_ID)
            write_tab_with_retry(sheet, TAB_NAME, df_master)
        except Exception as exc:
            print({"status": "warning", "alert": "sheets_error", "error": str(exc)})
        _log("write_sheet_end")
        print(
            {
                "status": "success",
                "rows": len(df_master),
                "snapshot": str(OUT_PATH),
                "publish_existing_only": True,
                "write_sheets": True,
            }
        )
        return

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
    l2_map, l2_dedupe = _index_by_key(l2, source="l2")
    l3_map, l3_dedupe = _index_by_key(l3, source="l3")
    for dedupe in (l2_dedupe, l3_dedupe):
        if int(dedupe.get("duplicate_groups", 0)) <= 0:
            continue
        print(
            {
                "status": "warning",
                "reason": "source_duplicate_keys_collapsed",
                "source": str(dedupe.get("source", "")),
                "duplicate_groups": int(dedupe.get("duplicate_groups", 0)),
                "duplicate_rows": int(dedupe.get("duplicate_rows", 0)),
            }
        )
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
        _write_output_frame(pd.DataFrame(orphan_rows), L3_ORPHANS_PATH, SQL_TABLE_L3_ORPHANS)
    else:
        # Always write a header-only file to keep downstream checks stable.
        _write_output_frame(pd.DataFrame(columns=["Order ID", "SKU"]), L3_ORPHANS_PATH, SQL_TABLE_L3_ORPHANS)

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
        # Re-evaluate existing lvl=2 rows; if the current L2 row is not viable,
        # force an update so they can demote back to lvl=1.
        for k, existing_row in existing_index.items():
            if str(existing_row.get("lvl", "")).strip() != "2":
                continue
            l2_row = l2_map.get(k)
            if l2_row is None:
                continue
            l1_row = l1_index.get(k)
            if not _l2_row_is_viable(l2_row, l1_row):
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
    l2_invalid_fallback_count = 0
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
        elif key in l2_map and _l2_row_is_viable(l2_map[key], row):
            use = l2_map[key]
            level = "2"
        else:
            if key in l2_map:
                l2_invalid_fallback_count += 1
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

    # Keep sold rows visible even when token COGS are missing by using a provisional
    # per-SKU placeholder cost basis. This does not create token truth.
    df_master = _apply_missing_token_placeholders(df_master)

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

    missing_l1_fee_rows = _write_l1_missing_fee_keys(df_master)
    if missing_l1_fee_rows > 0:
        print({"status": "warning", "reason": "l1_missing_fees_observed", "rows": missing_l1_fee_rows})

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
    # Publish unresolved missing-token rows from the finalized master with
    # placeholder and shortage context for operator/UI follow-up.
    _write_missing_token_orders(df_master)
    if "Quantity Ordered" in df_master.columns and "COGS_ExVAT" in df_master.columns:
        missing_cogs = _missing_token_cogs_mask(df_master)
        if missing_cogs.any():
            print({"status": "warning", "reason": "missing_token_cogs_observed", "rows": int(missing_cogs.sum())})
    if l2_invalid_fallback_count:
        print(
            {
                "status": "warning",
                "reason": "l2_not_viable_fallback_to_l1",
                "rows": int(l2_invalid_fallback_count),
            }
        )
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
        _write_output_frame(df_master, OUT_PATH, SQL_TABLE_ORDER_MASTER)

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
    print({"status": "success", "rows": len(df_master), "snapshot": str(snapshot_path), "write_sheets": not skip_sheets})


if __name__ == "__main__":
    main()

