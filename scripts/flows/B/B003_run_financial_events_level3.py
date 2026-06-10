"""
Posted financial events pull for Level 3 (truth).

Rules:
- Marker-based window: PostedAfter from marker (or env override), PostedBefore = now - 5 minutes.
- Fetches all event types (shipments, refunds/adjustments) with line-level charges/fees.
- Token refresh on 401, backoff on 429/5xx, paced < ~2 RPS.
- Outputs CSVs for raw lines + per-order/amount_type summary + account-level ledger.
"""

from __future__ import annotations

import os
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api.get_financial_events import (  # noqa: E402
    get_lwa_access_token,
    list_financial_events,
    load_dotenv_if_missing,
)
try:
    from scripts.core.storage import (
        StorageConfig,
        connect_store,
        coalesce_duplicate_header_rows,
        dataframe_from_product_db_sheet_rows,
        parse_storage_mode,
        replace_table_from_dataframe,
        write_dataframe_with_sql_compat,
    )
    from scripts.flows.B._finance_io import read_finance_frame, replace_finance_table, write_finance_frame
except ModuleNotFoundError:
    from core.storage import (
        StorageConfig,
        connect_store,
        coalesce_duplicate_header_rows,
        dataframe_from_product_db_sheet_rows,
        parse_storage_mode,
        replace_table_from_dataframe,
        write_dataframe_with_sql_compat,
    )
    from flows.B._finance_io import read_finance_frame, replace_finance_table, write_finance_frame

if TYPE_CHECKING:
    import gspread

OUT_RAW = Path("out/financial_events_level3_raw.csv")
SQL_TABLE_RAW = "b_financial_events_level3_raw"
OUT_RAW_DEDUP = Path("out/financial_events_level3_raw_dedup.csv")
SQL_TABLE_RAW_DEDUP = "b_financial_events_level3_raw_dedup"
OUT_SUM = Path("out/financial_events_level3_summary.csv")
SQL_TABLE_SUMMARY = "b_financial_events_level3_summary"
OUT_OFFICIAL = Path("out/financial_events_level3_official.csv")
SQL_TABLE_OFFICIAL = "b_financial_events_level3_official"
PRODUCT_DB_PREVIEW = Path("out/product_db_preview.csv")
SQL_TABLE_PRODUCT_DB_PREVIEW = "sys_product_db_preview"
OUT_ACCOUNT = Path("out/financial_events_account_ledger.csv")
SQL_TABLE_ACCOUNT = "b_financial_events_account_ledger"
OUT_REFUNDS = Path("out/financial_events_refunds.csv")
SQL_TABLE_REFUNDS = "b_financial_events_refunds"
OUT_REFUNDS_OFFICIAL = Path("out/financial_events_refunds_official.csv")
SQL_TABLE_REFUNDS_OFFICIAL = "b_financial_events_refunds_official"
OUT_SHIPMENTS = Path("out/financial_events_shipments.csv")
SQL_TABLE_SHIPMENTS = "b_financial_events_shipments"
OUT_INBOUND_SUM = Path("out/financial_events_inbound_summary.csv")
SQL_TABLE_INBOUND_SUMMARY = "b_financial_events_inbound_summary"
OUT_STORAGE = Path("out/financial_events_storage.csv")
SQL_TABLE_STORAGE = "b_financial_events_storage"
OUT_STORAGE_SUM = Path("out/financial_events_storage_summary.csv")
SQL_TABLE_STORAGE_SUMMARY = "b_financial_events_storage_summary"
OUT_ACCOUNT_SUM = Path("out/financial_events_account_summary.csv")
SQL_TABLE_ACCOUNT_SUMMARY = "b_financial_events_account_summary"
OUT_L2_VS_L3 = Path("out/l2_vs_l3_discrepancies.csv")
SQL_TABLE_L2_VS_L3 = "b_l2_vs_l3_discrepancies"
OUT_VAT_MODEL = Path("out/vat_country_model.csv")
SQL_TABLE_VAT_MODEL = "b_vat_country_model"
FEE_RULES_PATH = Path("reference/fee_vat_rules.csv")
OUT_FEE_MODEL = Path("out/fee_country_model.csv")
SQL_TABLE_FEE_MODEL = "b_fee_country_model"
MARKER_PATH = Path("out/financial_events_level3_last_posted.txt")
ITEMS_ALL = Path("out/order_items_all.csv")
ORDERS_ALL = Path("out/orders_all.csv")
POSTED_AFTER_ENV = os.environ.get("FIN_L3_POSTED_AFTER")
POSTED_BEFORE_ENV = os.environ.get("FIN_L3_POSTED_BEFORE")
DO_CLEAN = os.environ.get("FIN_L3_CLEAN", "").strip() == "1"
DEBUG_ORDER_ID = os.environ.get("FIN_L3_DEBUG_ORDER_ID")
DEBUG_SERVICE_FEE = os.environ.get("FIN_L3_DEBUG_SERVICE_FEE", "").strip() == "1"
MAX_RETRIES = int(os.environ.get("FIN_L3_MAX_RETRIES", "5"))
BASE_SLEEP = float(os.environ.get("FIN_L3_BASE_SLEEP", "1.0"))  # seconds, base pacing
SHEET_ID = os.environ.get("FIN_L3_SHEET_ID", "1BHueJTk4dvvhIXypzh6i2hQTgc0pB3DWj2khQ2IT6_A")
RAW_TAB = os.environ.get("FIN_L3_RAW_TAB", "FinancialEvents_L3_raw")
SUMMARY_TAB = os.environ.get("FIN_L3_SUMMARY_TAB", "FinancialEvents_L3_summary")
OFFICIAL_TAB = os.environ.get("FIN_L3_OFFICIAL_TAB", "FinancialEvents_L3_official")
ACCOUNT_TAB = os.environ.get("FIN_L3_ACCOUNT_TAB", "FinancialEvents_account_ledger")
REFUNDS_TAB = os.environ.get("FIN_L3_REFUNDS_TAB", "FinancialEvents_refunds")
REFUNDS_OFFICIAL_TAB = os.environ.get("FIN_L3_REFUNDS_OFFICIAL_TAB", "FinancialEvents_refunds_official")
SHIPMENTS_TAB = os.environ.get("FIN_L3_SHIPMENTS_TAB", "FinancialEvents_shipments")
INBOUND_SUM_TAB = os.environ.get("FIN_L3_INBOUND_SUM_TAB", "FinancialEvents_inbound_summary")
STORAGE_TAB = os.environ.get("FIN_L3_STORAGE_TAB", "FinancialEvents_storage")
STORAGE_SUM_TAB = os.environ.get("FIN_L3_STORAGE_SUM_TAB", "FinancialEvents_storage_summary")
ACCOUNT_SUM_TAB = os.environ.get("FIN_L3_ACCOUNT_SUM_TAB", "FinancialEvents_account_summary")
L2_VS_L3_TAB = os.environ.get("FIN_L3_L2_VS_L3_TAB", "L2_vs_L3_discrepancies")
PRODUCT_DB_SHEET_ID = os.environ.get("PRODUCT_DB_SHEET_ID", "1b7iREy92vF_a1Lw72g0SOGS7t4-IOSBeeoHetLTN43s")
PRODUCT_DB_TAB = "Product_DB"
UK_MARKETPLACE_ID = "A1F83G8C2ARO7P"
SHEETS_MAX_RETRIES = 5
SHEETS_BACKOFF = 2.0  # seconds
SEED_START = datetime(2025, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
SHEETS_MAX_CELLS = 10_000_000
FIN_L3_SKIP_SHEETS = os.environ.get("FIN_L3_SKIP_SHEETS", "0") == "1"
FIN_L3_SHEETS_MODE = os.environ.get("FIN_L3_SHEETS_MODE", "official_only").strip().lower()
DEDUP_CAP_TYPES = {
    "Principal",
    "Tax",
    "FBAPerUnitFulfillmentFee",
    "Commission",
    "DigitalServicesFee",
    "DigitalServicesFeeFBA",
}

VAT_TYPES = {
    "Tax",
    "ShippingTax",
    "GiftWrapTax",
    "MarketplaceFacilitatorVAT-Principal",
    "MarketplaceFacilitatorVAT-Shipping",
}
BASE_TYPES = {
    "Principal",
    "ShippingCharge",
    "GiftWrap",
}


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_output_frame(df: pd.DataFrame, path: Path, sql_table: str) -> dict[str, object]:
    return write_finance_frame(df, path, sql_table)


def _load_marker() -> Optional[str]:
    if POSTED_AFTER_ENV:
        return POSTED_AFTER_ENV
    if MARKER_PATH.exists():
        txt = MARKER_PATH.read_text().strip()
        if txt:
            return txt
    return None


def _save_marker(latest_iso: str) -> None:
    try:
        dt = datetime.fromisoformat(latest_iso.replace("Z", "+00:00"))
        latest_iso = _iso(dt)
    except Exception:
        pass
    MARKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = MARKER_PATH.with_name(f".{MARKER_PATH.name}.{os.getpid()}.tmp")
    last_error: OSError | None = None
    for attempt in range(1, 4):
        try:
            tmp_path.write_text(latest_iso, encoding="utf-8")
            os.replace(tmp_path, MARKER_PATH)
            return
        except OSError as exc:
            last_error = exc
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            if attempt == 3:
                raise
            time.sleep(0.25 * attempt)
    if last_error is not None:
        raise last_error


def _backoff_sleep(attempt: int) -> None:
    time.sleep(min(BASE_SLEEP * (2 ** (attempt - 1)), 60))


def get_gspread_client() -> "gspread.Client":
    import gspread

    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        cred_path = str(Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=cred_path)


def write_tab_with_retry(sheet: "gspread.Spreadsheet", tab_name: str, df: pd.DataFrame) -> None:
    import gspread
    from gspread.exceptions import APIError

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


def _too_big_for_sheets(df: pd.DataFrame) -> bool:
    if df is None or df.empty:
        return False
    rows = len(df) + 1
    cols = len(df.columns)
    return rows * max(cols, 1) > SHEETS_MAX_CELLS


def export_product_db(sheet: "gspread.Spreadsheet") -> None:
    """Dump Product_DB to out/product_db_preview.csv so downstream jobs see latest overrides."""
    import gspread

    try:
        ws = sheet.worksheet(PRODUCT_DB_TAB)
    except gspread.WorksheetNotFound:
        return
    rows = ws.get_all_values()
    if not rows:
        return
    df, repaired_headers = dataframe_from_product_db_sheet_rows(rows)
    Path("out").mkdir(parents=True, exist_ok=True)
    write_dataframe_with_sql_compat(
        df,
        PRODUCT_DB_PREVIEW,
        SQL_TABLE_PRODUCT_DB_PREVIEW,
    )
    if repaired_headers:
        print("Repaired duplicate Product_DB headers for export: " + ",".join(repaired_headers))


def update_product_db_last_fba_fee(df_official: pd.DataFrame, df_raw: Optional[pd.DataFrame] = None) -> None:
    """
    Update Product_DB with confirmed FBA fee (ex-VAT) from Level 3 only.
    Rule:
    - Look at last 10 non-zero fees per SKU.
    - Use the most common fee if it appears at least twice.
    - Otherwise, keep existing confirmed fee and store as candidate.
    """
    if df_official.empty:
        return
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(PRODUCT_DB_SHEET_ID)
        ws = sheet.worksheet(PRODUCT_DB_TAB)
    except Exception:
        return

    prod_rows = ws.get_all_values()
    if not prod_rows:
        return
    prod_rows, repaired_headers = coalesce_duplicate_header_rows(prod_rows)
    if repaired_headers:
        print("Repaired duplicate Product_DB headers before B003 update: " + ",".join(repaired_headers))
    headers = prod_rows[0]
    idx_map = {h: i for i, h in enumerate(headers)}
    required_cols = [
        "last_fba_fee_ex_vat",
        "last_fba_fee_ex_vat_10",
        "last_fba_fee_ex_vat_100",
        "last_fba_fee_updated",
        "last_fba_fee_source",
        "last_fba_fee_candidate",
        "last_fba_fee_candidate_seen",
        "last_commission_pct",
        "last_commission_updated",
        "last_commission_source",
        "last_commission_pct_10",
        "last_commission_pct_100",
        "last_vat_rate_pct",
        "last_vat_rate_updated",
        "last_vat_rate_source",
        "last_vat_rate_candidate",
        "last_vat_rate_candidate_seen",
        "last_withheld_vat_flag",
        "last_withheld_vat_updated",
        "last_withheld_vat_source",
    ]
    for col in required_cols:
        if col not in idx_map:
            idx_map[col] = len(headers)
            headers.append(col)
            for row in prod_rows[1:]:
                while len(row) < len(headers):
                    row.append("")

    sku_idx = idx_map.get("seller_sku", -1)
    if sku_idx < 0:
        return
    sku_lookup = {}
    for i, row in enumerate(prod_rows[1:], start=1):
        if len(row) < len(headers):
            row.extend([""] * (len(headers) - len(row)))
        sku_val = row[sku_idx]
        if sku_val:
            sku_lookup[sku_val] = i

    df = df_official.copy()
    if ORDERS_ALL.exists():
        try:
            orders = read_finance_frame(ORDERS_ALL, dtype=str)[["amazon_order_id", "marketplace_id"]].rename(
                columns={"amazon_order_id": "Order ID"}
            )
            df = df.merge(orders, on="Order ID", how="left")
        except Exception:
            pass
    # Backfill Quantity Ordered from archived items when missing.
    if "Quantity Ordered" in df.columns and ITEMS_ALL.exists():
        try:
            items = read_finance_frame(ITEMS_ALL, dtype=str)[["amazon_order_id", "seller_sku", "quantity_ordered"]].rename(
                columns={"amazon_order_id": "Order ID", "seller_sku": "SKU", "quantity_ordered": "Quantity Ordered_src"}
            )
            df = df.merge(items, on=["Order ID", "SKU"], how="left")
            df["Quantity Ordered"] = df["Quantity Ordered"].fillna(df["Quantity Ordered_src"])
            df = df.drop(columns=[c for c in df.columns if c.endswith("_src")])
        except Exception:
            pass
    df["__date"] = pd.to_datetime(df.get("Date"), errors="coerce", utc=True)
    df = df[df["SKU"].astype(str).str.len() > 0]
    df = df[df["__date"].notna()]
    if df.empty:
        return
    if "marketplace_id" not in df.columns:
        df["marketplace_id"] = ""
    else:
        df["marketplace_id"] = df["marketplace_id"].astype(str).fillna("").str.strip()
    df["__qty"] = pd.to_numeric(df.get("Quantity Ordered"), errors="coerce").fillna(1)
    df.loc[df["__qty"] <= 0, "__qty"] = 1
    df["__fba_ex"] = pd.to_numeric(df.get("FBA_Fee_ExVAT"), errors="coerce")
    df["__price_total"] = pd.to_numeric(df.get("Price_Total"), errors="coerce")
    df["__comm_ex"] = pd.to_numeric(df.get("Commission_ExVAT"), errors="coerce")
    df["__unit_price_total"] = (df["__price_total"].abs() / df["__qty"]).round(2)
    df = df[df["__fba_ex"].notna()]
    df["__unit_fba_ex"] = (df["__fba_ex"].abs() / df["__qty"]).round(2)
    df = df[df["__unit_fba_ex"] > 0]
    df = df.sort_values(by=["SKU", "__date"])
    uk_counts_by_sku = (
        df.loc[df["marketplace_id"] == UK_MARKETPLACE_ID]
        .groupby("SKU")
        .size()
        .to_dict()
    )
    df = df[df["marketplace_id"] == UK_MARKETPLACE_ID]

    def round_pct(val: float) -> str:
        try:
            return str(int(Decimal(str(val)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
        except Exception:
            return ""

    def _modal_value_with_recent_tiebreak(window: pd.DataFrame, value_col: str) -> tuple[str, str, int]:
        """Return (value_str, value_dt, count) for modal value in a window."""
        if window.empty or value_col not in window.columns:
            return ("", "", 0)
        counts = window[value_col].value_counts()
        if counts.empty:
            return ("", "", 0)
        top_count = int(counts.iloc[0])
        top_values = counts[counts == top_count].index.tolist()
        best_value = top_values[0]
        best_dt = None
        for val in top_values:
            recent_dt = window.loc[window[value_col] == val, "__date"].max()
            if best_dt is None or (pd.notna(recent_dt) and recent_dt > best_dt):
                best_value = val
                best_dt = recent_dt
        dt_str = best_dt.strftime("%Y-%m-%dT%H:%M:%SZ") if pd.notna(best_dt) else ""
        return (str(best_value), dt_str, top_count)

    for sku, grp in df.groupby("SKU"):
        if sku not in sku_lookup:
            continue
        window = grp.tail(10)
        fee_counts = window["__unit_fba_ex"].value_counts()
        if fee_counts.empty:
            continue
        # Most common fee; tie-breaker by most recent occurrence.
        top_fee = fee_counts.index[0]
        top_count = int(fee_counts.iloc[0])
        recent_dt = window[window["__unit_fba_ex"] == top_fee]["__date"].max()
        fee_str = f"{float(top_fee):.2f}"
        fee_dt = recent_dt.strftime("%Y-%m-%dT%H:%M:%SZ") if pd.notna(recent_dt) else ""

        idx = sku_lookup[sku]
        row = prod_rows[idx]
        fba_band_confirmed = False
        comm_band_confirmed = False

        # Learn FBA fee per-unit by unit price band.
        # This prevents multi-qty total fees from being treated as >10 unit-price fees.
        try:
            fee_rows = grp.copy()
            fee_rows = fee_rows[
                fee_rows["__unit_price_total"].notna()
                & fee_rows["__unit_fba_ex"].notna()
                & fee_rows["__unit_price_total"].gt(0)
                & fee_rows["__unit_fba_ex"].gt(0)
            ].copy()
            if not fee_rows.empty:
                band_10 = fee_rows.loc[fee_rows["__unit_price_total"] <= 10].tail(10)
                v10_str, _, v10_count = _modal_value_with_recent_tiebreak(band_10, "__unit_fba_ex")
                if v10_count >= 2 and v10_str:
                    row[idx_map["last_fba_fee_ex_vat_10"]] = f"{float(v10_str):.2f}"
                    fba_band_confirmed = True
                else:
                    row[idx_map["last_fba_fee_ex_vat_10"]] = ""
                # For >10 band, fail closed: clear stale value if there is no valid repeat evidence.
                band_100 = fee_rows.loc[fee_rows["__unit_price_total"] > 10].tail(10)
                v100_str, _, v100_count = _modal_value_with_recent_tiebreak(band_100, "__unit_fba_ex")
                if v100_count >= 2 and v100_str:
                    row[idx_map["last_fba_fee_ex_vat_100"]] = f"{float(v100_str):.2f}"
                    fba_band_confirmed = True
                else:
                    row[idx_map["last_fba_fee_ex_vat_100"]] = ""
            else:
                row[idx_map["last_fba_fee_ex_vat_10"]] = ""
                row[idx_map["last_fba_fee_ex_vat_100"]] = ""
        except Exception:
            pass

        if top_count >= 2:
            row[idx_map["last_fba_fee_ex_vat"]] = fee_str
            row[idx_map["last_fba_fee_updated"]] = fee_dt
            row[idx_map["last_fba_fee_source"]] = "Level3"
            row[idx_map["last_fba_fee_candidate"]] = ""
            row[idx_map["last_fba_fee_candidate_seen"]] = ""
        else:
            row[idx_map["last_fba_fee_candidate"]] = fee_str
            row[idx_map["last_fba_fee_candidate_seen"]] = fee_dt
            # Fail closed: no repeat evidence means no active Level3 fee source.
            row[idx_map["last_fba_fee_ex_vat"]] = ""
            row[idx_map["last_fba_fee_updated"]] = ""
            row[idx_map["last_fba_fee_source"]] = ""
        if not fba_band_confirmed:
            row[idx_map["last_fba_fee_ex_vat"]] = ""
            row[idx_map["last_fba_fee_updated"]] = ""
            row[idx_map["last_fba_fee_source"]] = ""

        # Commission % (GB only): learn per price band with the same "most common in last 10" rule.
        # <=10 orders update only _10, and >10 orders update only _100.
        try:
            comm_rows = grp.copy()
            comm_rows = comm_rows[
                comm_rows["__price_total"].notna()
                & comm_rows["__comm_ex"].notna()
                & comm_rows["__price_total"].gt(0)
                & comm_rows["__unit_price_total"].gt(0)
            ].copy()
            if not comm_rows.empty:
                comm_rows["__comm_pct"] = (
                    (comm_rows["__comm_ex"].abs() / comm_rows["__price_total"].abs()) * 100.0
                ).apply(round_pct)
                comm_rows = comm_rows[comm_rows["__comm_pct"].astype(str).str.len() > 0]
                if not comm_rows.empty:
                    band_updates: list[tuple[pd.Timestamp, str]] = []
                    for mask, out_col in [
                        (comm_rows["__unit_price_total"] <= 10, "last_commission_pct_10"),
                        (comm_rows["__unit_price_total"] > 10, "last_commission_pct_100"),
                    ]:
                        band = comm_rows.loc[mask].tail(10)
                        value_str, value_dt_str, value_count = _modal_value_with_recent_tiebreak(
                            band, "__comm_pct"
                        )
                        if value_count >= 2 and value_str:
                            row[idx_map[out_col]] = value_str
                            comm_band_confirmed = True
                            if value_dt_str:
                                band_updates.append((pd.to_datetime(value_dt_str, utc=True), value_str))
                        else:
                            row[idx_map[out_col]] = ""
                    if band_updates:
                        band_updates.sort(key=lambda x: x[0])
                        latest_dt, latest_val = band_updates[-1]
                        row[idx_map["last_commission_pct"]] = latest_val
                        row[idx_map["last_commission_updated"]] = latest_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                        row[idx_map["last_commission_source"]] = "Level3"
                    else:
                        # Fail closed: no repeat band evidence means no active Level3 commission source.
                        row[idx_map["last_commission_pct"]] = ""
                        row[idx_map["last_commission_updated"]] = ""
                        row[idx_map["last_commission_source"]] = ""
                else:
                    row[idx_map["last_commission_pct_10"]] = ""
                    row[idx_map["last_commission_pct_100"]] = ""
                    row[idx_map["last_commission_pct"]] = ""
                    row[idx_map["last_commission_updated"]] = ""
                    row[idx_map["last_commission_source"]] = ""
        except Exception:
            pass
        if not comm_band_confirmed:
            row[idx_map["last_commission_pct"]] = ""
            row[idx_map["last_commission_updated"]] = ""
            row[idx_map["last_commission_source"]] = ""

    # Global fail-closed pass:
    # If a SKU has fewer than 2 UK L3 rows, it cannot keep active L3 fee/commission fields.
    for sku, idx in sku_lookup.items():
        if int(uk_counts_by_sku.get(sku, 0)) >= 2:
            continue
        row = prod_rows[idx]
        row[idx_map["last_fba_fee_ex_vat"]] = ""
        row[idx_map["last_fba_fee_ex_vat_10"]] = ""
        row[idx_map["last_fba_fee_ex_vat_100"]] = ""
        row[idx_map["last_fba_fee_updated"]] = ""
        row[idx_map["last_fba_fee_source"]] = ""
        row[idx_map["last_commission_pct"]] = ""
        row[idx_map["last_commission_pct_10"]] = ""
        row[idx_map["last_commission_pct_100"]] = ""
        row[idx_map["last_commission_updated"]] = ""
        row[idx_map["last_commission_source"]] = ""

        # VAT rate % (GB only): Price_VAT / Price_ExVAT, rounded to whole percent.
        try:
            vat_window = window.copy()
            vat_window["__price_ex"] = pd.to_numeric(vat_window.get("Price_ExVAT"), errors="coerce").fillna(0.0)
            vat_window["__price_vat"] = pd.to_numeric(vat_window.get("Price_VAT"), errors="coerce").fillna(0.0)
            vat_window = vat_window[vat_window["__price_ex"] > 0]
            if not vat_window.empty:
                vat_window["__vat_rate"] = (vat_window["__price_vat"] / vat_window["__price_ex"] * 100.0).round(2)
                vat_counts = vat_window["__vat_rate"].round(0).value_counts()
                if not vat_counts.empty:
                    top_rate = vat_counts.index[0]
                    top_count = int(vat_counts.iloc[0])
                    recent_dt = vat_window[vat_window["__vat_rate"].round(0) == top_rate]["__date"].max()
                    rate_str = round_pct(float(top_rate))
                    rate_dt = recent_dt.strftime("%Y-%m-%dT%H:%M:%SZ") if pd.notna(recent_dt) else ""
                    if top_count >= 2:
                        row[idx_map["last_vat_rate_pct"]] = rate_str
                        row[idx_map["last_vat_rate_updated"]] = rate_dt
                        row[idx_map["last_vat_rate_source"]] = "Level3"
                        row[idx_map["last_vat_rate_candidate"]] = ""
                        row[idx_map["last_vat_rate_candidate_seen"]] = ""
                    else:
                        row[idx_map["last_vat_rate_candidate"]] = rate_str
                        row[idx_map["last_vat_rate_candidate_seen"]] = rate_dt
        except Exception:
            pass

    # Withheld VAT flag (GB only): MarketplaceFacilitatorVAT-Principal/Shipping in raw lines.
    if df_raw is not None and not df_raw.empty:
        try:
            raw = df_raw.copy()
            raw = raw[raw["sku"].astype(str).str.len() > 0]
            raw = raw[raw["amount_type"].isin(["MarketplaceFacilitatorVAT-Principal", "MarketplaceFacilitatorVAT-Shipping"])]
            raw["__date"] = pd.to_datetime(raw.get("posted_date"), errors="coerce", utc=True)
            raw = raw[raw["__date"].notna()]
            if not raw.empty:
                for sku, grp in raw.groupby("sku"):
                    if sku not in sku_lookup:
                        continue
                    recent_dt = grp["__date"].max()
                    fee_dt = recent_dt.strftime("%Y-%m-%dT%H:%M:%SZ") if pd.notna(recent_dt) else ""
                    idx = sku_lookup[sku]
                    row = prod_rows[idx]
                    row[idx_map["last_withheld_vat_flag"]] = "1"
                    row[idx_map["last_withheld_vat_updated"]] = fee_dt
                    row[idx_map["last_withheld_vat_source"]] = "Level3"
        except Exception:
            pass

        # Clear any legacy margin fields if present.
        for col in ["last_margin_pct", "last_margin_updated", "last_margin_source"]:
            if col in idx_map:
                row[idx_map[col]] = ""

    ws.clear()
    ws.update(range_name="A1", values=[headers] + prod_rows[1:])
    export_product_db(sheet)


def write_l2_vs_l3_discrepancies(df_official: pd.DataFrame) -> pd.DataFrame:
    empty_cols = [
        "Order ID",
        "SKU",
        "Date_l2",
        "Date_l3",
        "field",
        "l2_value",
        "l3_value",
        "delta",
    ]
    if df_official.empty:
        out = pd.DataFrame(columns=empty_cols)
        _write_output_frame(out, OUT_L2_VS_L3, SQL_TABLE_L2_VS_L3)
        return out
    l2_path = Path("out/financial_events_level2.csv")
    try:
        df_l2 = read_finance_frame(l2_path, "b_financial_events_level2", dtype=str)
    except Exception:
        out = pd.DataFrame(columns=empty_cols)
        _write_output_frame(out, OUT_L2_VS_L3, SQL_TABLE_L2_VS_L3)
        return out
    if df_l2.empty:
        out = pd.DataFrame(columns=empty_cols)
        _write_output_frame(out, OUT_L2_VS_L3, SQL_TABLE_L2_VS_L3)
        return out
    key_cols = ["Order ID", "SKU"]
    if any(c not in df_official.columns for c in key_cols):
        out = pd.DataFrame(columns=empty_cols)
        _write_output_frame(out, OUT_L2_VS_L3, SQL_TABLE_L2_VS_L3)
        return out
    if any(c not in df_l2.columns for c in key_cols):
        out = pd.DataFrame(columns=empty_cols)
        _write_output_frame(out, OUT_L2_VS_L3, SQL_TABLE_L2_VS_L3)
        return out
    fields = [
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
    df_l2 = df_l2[key_cols + ["Date"] + [c for c in fields if c in df_l2.columns]].copy()
    df_l3 = df_official[key_cols + ["Date"] + [c for c in fields if c in df_official.columns]].copy()
    df = df_l2.merge(df_l3, on=key_cols, how="inner", suffixes=("_l2", "_l3"))
    if df.empty:
        out = pd.DataFrame(columns=empty_cols)
        _write_output_frame(out, OUT_L2_VS_L3, SQL_TABLE_L2_VS_L3)
        return out
    rows = []
    for field in fields:
        l2_col = f"{field}_l2"
        l3_col = f"{field}_l3"
        if l2_col not in df.columns or l3_col not in df.columns:
            continue
        l2_vals = pd.to_numeric(df[l2_col], errors="coerce")
        l3_vals = pd.to_numeric(df[l3_col], errors="coerce")
        delta = (l3_vals - l2_vals).round(2)
        mask = delta.abs() > 0.01
        if not mask.any():
            continue
        sub = df.loc[mask, ["Order ID", "SKU", "Date_l2", "Date_l3"]].copy()
        sub["field"] = field
        sub["l2_value"] = l2_vals[mask].round(2)
        sub["l3_value"] = l3_vals[mask].round(2)
        sub["delta"] = delta[mask].round(2)
        rows.append(sub)
    if not rows:
        out = pd.DataFrame(columns=empty_cols)
        _write_output_frame(out, OUT_L2_VS_L3, SQL_TABLE_L2_VS_L3)
        return out
    out = pd.concat(rows, ignore_index=True)
    out["date_l3"] = pd.to_datetime(out["Date_l3"], errors="coerce", utc=True)
    today = datetime.now(timezone.utc).date()
    out = out[out["date_l3"].dt.date >= today]
    if out.empty:
        out = pd.DataFrame(columns=empty_cols)
        _write_output_frame(out, OUT_L2_VS_L3, SQL_TABLE_L2_VS_L3)
        return out
    out = out.sort_values(by=["date_l3", "Order ID", "SKU", "field"]).drop(columns=["date_l3"])
    _write_output_frame(out, OUT_L2_VS_L3, SQL_TABLE_L2_VS_L3)
    return out


def build_official(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Map raw Level 3 lines into a Level_2_Official-style per order/SKU row.
    """
    cols = [
        "Date",
        "Order ID",
        "SKU",
        "Quantity Ordered",
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
    if df_raw.empty:
        return pd.DataFrame(columns=cols)

    items_map = {}
    if ITEMS_ALL.exists():
        try:
            items = read_finance_frame(ITEMS_ALL, dtype=str)[
                [
                    "amazon_order_id",
                    "seller_sku",
                    "item_price_amount",
                    "item_tax_amount",
                    "shipping_price_amount",
                    "shipping_tax_amount",
                ]
            ]
            # Sum per order+sku so multi-line items are combined.
            def _safe_float(x):
                try:
                    return float(x)
                except Exception:
                    return 0.0

            items["item_price_amount"] = items["item_price_amount"].apply(_safe_float)
            items["item_tax_amount"] = items["item_tax_amount"].apply(_safe_float)
            items["shipping_price_amount"] = items["shipping_price_amount"].apply(_safe_float)
            items["shipping_tax_amount"] = items["shipping_tax_amount"].apply(_safe_float)

            grouped_items = items.groupby(["amazon_order_id", "seller_sku"], dropna=False).sum().reset_index()
            for _, r in grouped_items.iterrows():
                key = (r.get("amazon_order_id"), r.get("seller_sku"))
                items_map[key] = {
                    "item_price_amount": r.get("item_price_amount"),
                    "item_tax_amount": r.get("item_tax_amount"),
                    "shipping_price_amount": r.get("shipping_price_amount"),
                    "shipping_tax_amount": r.get("shipping_tax_amount"),
                }
        except Exception:
            items_map = {}

    # Order -> country map for fee VAT rules
    orders_map = {}
    try:
        orders_df = read_finance_frame(ORDERS_ALL, dtype=str).fillna("")
        orders_map = {
            str(r.get("amazon_order_id", "")).strip(): str(r.get("ship_country_code", "")).strip().upper()
            for _, r in orders_df.iterrows()
        }
    except Exception:
        orders_map = {}

    # Fee VAT rules by country (if present)
    fee_rules = {}
    if FEE_RULES_PATH.exists():
        try:
            rules_df = pd.read_csv(FEE_RULES_PATH, dtype=str).fillna("")
            for _, r in rules_df.iterrows():
                cc = str(r.get("country_code", "")).strip().upper()
                if not cc:
                    continue
                def _rate(val):
                    try:
                        return float(val)
                    except Exception:
                        return 0.0
                fee_rules[cc] = {
                    "fba_vat_rate": _rate(r.get("fba_vat_rate", 0)),
                    "commission_vat_rate": _rate(r.get("commission_vat_rate", 0)),
                    "dsf_vat_rate": _rate(r.get("dsf_vat_rate", 0)),
                }
        except Exception:
            fee_rules = {}

    def safe_float(x):
        try:
            return float(x)
        except Exception:
            return 0.0

    fee_map = {
        "FBA_Fee": ["FBAPerUnitFulfillmentFee"],
        "Commission": ["Commission"],
        "Digital_Fee": ["DigitalServicesFee", "DigitalServicesFeeFBA"],
        "FixedClosingFee": ["FixedClosingFee"],
    }

    # Exclude refund rows for now (handled later)
    df_off = df_raw[~df_raw["amount_type"].str.startswith("Refund", na=False)]
    grouped = df_off.groupby(["order_id", "sku"], dropna=False)
    rows = []
    for (oid, sku), grp in grouped:
        out = {k: "" for k in cols}
        out["Order ID"] = oid
        out["SKU"] = sku or ""
        items_row = items_map.get((oid, sku or ""))
        # Date: use max posted_date in group
        dates = [d for d in grp["posted_date"].tolist() if isinstance(d, str) and d]
        out["Date"] = max(dates) if dates else ""
        # Amount aggregations (net + VAT -> total)
        def sum_types(types, col):
            return grp.loc[grp["amount_type"].isin(types), col].apply(safe_float).sum()

        price_net = sum_types(["Principal"], "amount")
        price_vat = sum_types(["Tax"], "amount")
        price_total = price_net + price_vat
        if items_row:
            exp_total = safe_float(items_row.get("item_price_amount"))
            exp_vat = safe_float(items_row.get("item_tax_amount"))
            if exp_total > 0:
                price_total = exp_total
                price_vat = exp_vat
                price_net = exp_total - exp_vat
        if price_total:
            out["Price_Total"] = f"{price_total:.2f}"
            out["Price_VAT"] = f"{price_vat:.2f}"
            out["Price_ExVAT"] = f"{price_net:.2f}"

        ship_net = sum_types(["Shipping", "ShippingCharge"], "amount")
        ship_vat = sum_types(["ShippingTax"], "amount")
        ship_total = ship_net + ship_vat
        if items_row:
            exp_ship = safe_float(items_row.get("shipping_price_amount"))
            exp_ship_vat = safe_float(items_row.get("shipping_tax_amount"))
            if exp_ship > 0 or exp_ship_vat > 0:
                # item_price_amount / shipping_price_amount are VAT-inclusive in order_items_all
                ship_total = exp_ship
                ship_vat = exp_ship_vat
                ship_net = exp_ship - exp_ship_vat
        if ship_total:
            out["Shipping_Total"] = f"{ship_total:.2f}"
            out["Shipping_VAT"] = f"{ship_vat:.2f}"
            out["Shipping_ExVAT"] = f"{ship_net:.2f}"

        gift_net = sum_types(["GiftWrap"], "amount")
        gift_vat = sum_types(["GiftWrapTax"], "amount")
        gift_total = gift_net + gift_vat
        if gift_total:
            out["Gift_Total"] = f"{gift_total:.2f}"
            out["Gift_VAT"] = f"{gift_vat:.2f}"
            out["Gift_ExVAT"] = f"{gift_net:.2f}"

        promo_net = sum_types(["Promotion", "FBAPromotionAmount"], "amount")
        promo_vat = sum_types(["PromotionTax"], "amount")
        promo_total = promo_net + promo_vat
        if promo_total:
            out["Promotion_Total"] = f"{promo_total:.2f}"
            out["Promotion_VAT"] = f"{promo_vat:.2f}"
            out["Promotion_ExVAT"] = f"{promo_net:.2f}"

        # Fees with tax split; use country rules when tax not provided
        for label, types in fee_map.items():
            total_amt = 0.0
            tax_amt = 0.0
            for t in types:
                total_amt += grp.loc[grp["amount_type"] == t, "amount"].apply(safe_float).sum()
                tax_amt += grp.loc[grp["amount_type"] == t, "tax_amount"].apply(safe_float).sum()
            if total_amt != 0.0:
                if tax_amt == 0.0:
                    cc = orders_map.get(str(oid).strip(), "")
                    rate = 0.0
                    if cc and cc in fee_rules:
                        if label == "FBA_Fee":
                            rate = fee_rules[cc].get("fba_vat_rate", 0.0)
                        elif label == "Commission":
                            rate = fee_rules[cc].get("commission_vat_rate", 0.0)
                        elif label == "Digital_Fee":
                            rate = fee_rules[cc].get("dsf_vat_rate", 0.0)
                    if rate and rate > 0:
                        ex = round(total_amt / (1 + rate), 2)
                        vat = round(total_amt - ex, 2)
                    else:
                        ex = round(total_amt, 2)
                        vat = 0.0
                else:
                    ex = round(total_amt - tax_amt, 2)
                    vat = round(tax_amt, 2)
                out[f"{label}_Total"] = f"{total_amt:.2f}"
                out[f"{label}_VAT"] = f"{vat:.2f}"
                out[f"{label}_ExVAT"] = f"{ex:.2f}"

        rows.append(out)
    return pd.DataFrame(rows, columns=cols)


def _trim_duplicate_lines_by_qty(df_raw: pd.DataFrame, qty_map: dict) -> pd.DataFrame:
    """
    Some marketplaces return duplicate line items without unique IDs.
    Cap identical line repetitions to a single line for per-order amount types
    to avoid double counting when the API repeats the same line.
    """
    if df_raw.empty or not qty_map:
        return df_raw
    key_cols = ["order_id", "sku", "transaction_type", "amount_type", "amount", "posted_date"]
    # Build a stable duplicate key from the columns we trust.
    dup_key = df_raw[key_cols].astype(str).agg("||".join, axis=1)
    df = df_raw.copy()
    df["_dup_key"] = dup_key
    def _lookup_qty(row):
        oid = row.get("order_id")
        sku = row.get("sku") or ""
        qty = qty_map.get((oid, sku))
        if qty is None and sku == "":
            qty = qty_map.get((oid, ""))
        return qty

    df["_qty"] = df.apply(_lookup_qty, axis=1)
    mask = df["amount_type"].isin(DEDUP_CAP_TYPES)
    if mask.any():
        df["_dup_rank"] = -1
        df.loc[mask, "_dup_rank"] = df.loc[mask].groupby("_dup_key").cumcount()
        # Keep up to ordered qty when known; otherwise keep only the first occurrence.
        qty_int = pd.to_numeric(df["_qty"], errors="coerce").fillna(0).astype(int)
        keep_mask = ~mask | ((qty_int > 0) & (df["_dup_rank"] < qty_int)) | ((qty_int <= 0) & (df["_dup_rank"] < 1))
        df = df[keep_mask]
    return df.drop(columns=[c for c in ["_dup_key", "_qty", "_dup_rank"] if c in df.columns])


def build_refunds_official(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Map refund lines into a Level_2_Official-style per order/SKU row.
    """
    cols = [
        "Date",
        "Order ID",
        "SKU",
        "Quantity Ordered",
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
    if df_raw.empty:
        return pd.DataFrame(columns=cols)

    def safe_float(x):
        try:
            return float(x)
        except Exception:
            return 0.0

    fee_map = {
        "FBA_Fee": ["Refund_FBAPerUnitFulfillmentFee"],
        "Commission": ["Refund_Commission", "Refund_RefundCommission", "Refund_CommissionTax"],
        "Digital_Fee": ["Refund_DigitalServicesFee", "Refund_DigitalServicesFeeFBA", "Refund_DigitalServicesFeeTax"],
        "FixedClosingFee": ["Refund_FixedClosingFee"],
    }

    df_ref = df_raw[df_raw["amount_type"].str.startswith("Refund", na=False)]
    grouped = df_ref.groupby(["order_id", "sku"], dropna=False)
    rows = []
    for (oid, sku), grp in grouped:
        out = {k: "" for k in cols}
        out["Order ID"] = oid
        out["SKU"] = sku or ""
        dates = [d for d in grp["posted_date"].tolist() if isinstance(d, str) and d]
        out["Date"] = max(dates) if dates else ""

        def sum_types(types, col):
            return grp.loc[grp["amount_type"].isin(types), col].apply(safe_float).sum()

        price_net = sum_types(["Refund_Principal"], "amount")
        price_vat = sum_types(["Refund_Tax"], "amount")
        price_total = price_net + price_vat
        if price_total:
            out["Price_Total"] = f"{price_total:.2f}"
            out["Price_VAT"] = f"{price_vat:.2f}"
            out["Price_ExVAT"] = f"{price_net:.2f}"

        ship_net = sum_types(["Refund_Shipping", "Refund_ShippingCharge"], "amount")
        ship_vat = sum_types(["Refund_ShippingTax"], "amount")
        ship_total = ship_net + ship_vat
        if ship_total:
            out["Shipping_Total"] = f"{ship_total:.2f}"
            out["Shipping_VAT"] = f"{ship_vat:.2f}"
            out["Shipping_ExVAT"] = f"{ship_net:.2f}"

        gift_net = sum_types(["Refund_GiftWrap"], "amount")
        gift_vat = sum_types(["Refund_GiftWrapTax"], "amount")
        gift_total = gift_net + gift_vat
        if gift_total:
            out["Gift_Total"] = f"{gift_total:.2f}"
            out["Gift_VAT"] = f"{gift_vat:.2f}"
            out["Gift_ExVAT"] = f"{gift_net:.2f}"

        promo_net = sum_types(["Refund_Promotion", "Refund_FBAPromotionAmount"], "amount")
        promo_vat = sum_types(["Refund_PromotionTax"], "amount")
        promo_total = promo_net + promo_vat
        if promo_total:
            out["Promotion_Total"] = f"{promo_total:.2f}"
            out["Promotion_VAT"] = f"{promo_vat:.2f}"
            out["Promotion_ExVAT"] = f"{promo_net:.2f}"

        for label, types in fee_map.items():
            total_amt = 0.0
            tax_amt = 0.0
            for t in types:
                total_amt += grp.loc[grp["amount_type"] == t, "amount"].apply(safe_float).sum()
                tax_amt += grp.loc[grp["amount_type"] == t, "tax_amount"].apply(safe_float).sum()
            if total_amt != 0.0:
                if tax_amt == 0.0:
                    ex = round(total_amt / 1.2, 2)
                    vat = round(total_amt - ex, 2)
                else:
                    ex = round(total_amt - tax_amt, 2)
                    vat = round(tax_amt, 2)
                out[f"{label}_Total"] = f"{total_amt:.2f}"
                out[f"{label}_VAT"] = f"{vat:.2f}"
                out[f"{label}_ExVAT"] = f"{ex:.2f}"

        rows.append(out)
    return pd.DataFrame(rows, columns=cols)


def build_vat_country_model(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Build a rolling VAT model per country/marketplace from Level 3 raw.
    Uses last 10 orders (by posted_date) and averages VAT rates from taxable orders only.
    """
    cols = [
        "country_code",
        "marketplace_id",
        "currency",
        "sample_orders",
        "taxable_orders",
        "pct_taxable",
        "avg_vat_rate",
        "last_order_date",
        "built_at",
    ]
    if df_raw is None or df_raw.empty:
        return pd.DataFrame(columns=cols)
    for col in ["order_id", "amount_type", "amount", "currency", "posted_date"]:
        if col not in df_raw.columns:
            return pd.DataFrame(columns=cols)

    raw = df_raw.copy()
    raw["amount"] = pd.to_numeric(raw["amount"], errors="coerce").fillna(0.0).abs()
    raw["posted_date"] = pd.to_datetime(raw["posted_date"], errors="coerce", utc=True)
    raw["currency"] = raw["currency"].astype(str).str.strip()
    raw["amount_type"] = raw["amount_type"].astype(str).str.strip()

    base = raw[raw["amount_type"].isin(BASE_TYPES)].groupby("order_id")["amount"].sum().rename("base_sum")
    tax = raw[raw["amount_type"].isin(VAT_TYPES)].groupby("order_id")["amount"].sum().rename("tax_sum")
    latest_date = raw.groupby("order_id")["posted_date"].max().rename("last_posted")
    currency = raw.groupby("order_id")["currency"].agg(lambda s: next((v for v in s if v), "")).rename("currency")
    orders = pd.concat([base, tax, latest_date, currency], axis=1).reset_index()
    orders["base_sum"] = orders["base_sum"].fillna(0.0)
    orders["tax_sum"] = orders["tax_sum"].fillna(0.0)
    orders["vat_rate"] = 0.0
    mask = (orders["base_sum"] > 0) & (orders["tax_sum"] > 0)
    orders.loc[mask, "vat_rate"] = (orders.loc[mask, "tax_sum"] / orders.loc[mask, "base_sum"]).round(4)

    if ORDERS_ALL.exists():
        try:
            ord_map = read_finance_frame(ORDERS_ALL, dtype=str)[
                ["amazon_order_id", "marketplace_id", "ship_country_code"]
            ].rename(columns={"amazon_order_id": "order_id"})
            orders = orders.merge(ord_map, on="order_id", how="left")
        except Exception:
            orders["marketplace_id"] = ""
            orders["ship_country_code"] = ""
    else:
        orders["marketplace_id"] = ""
        orders["ship_country_code"] = ""

    orders["country_code"] = orders["ship_country_code"].astype(str).str.strip()
    orders["marketplace_id"] = orders["marketplace_id"].astype(str).str.strip()
    orders = orders[orders["last_posted"].notna()]
    if orders.empty:
        return pd.DataFrame(columns=cols)

    out_rows = []
    built_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for (country, market), grp in orders.groupby(["country_code", "marketplace_id"]):
        grp = grp.sort_values(by="last_posted", ascending=False).head(10)
        sample_orders = len(grp)
        taxable = grp[grp["vat_rate"] > 0]
        taxable_orders = len(taxable)
        pct_taxable = round(taxable_orders / sample_orders, 3) if sample_orders else 0.0
        avg_vat_rate = round(float(taxable["vat_rate"].mean()), 4) if taxable_orders else 0.0
        currency_val = next((v for v in grp["currency"].tolist() if v), "")
        last_order_date = grp["last_posted"].max()
        last_order_date_str = last_order_date.strftime("%Y-%m-%d") if pd.notna(last_order_date) else ""
        out_rows.append(
            {
                "country_code": country,
                "marketplace_id": market,
                "currency": currency_val,
                "sample_orders": sample_orders,
                "taxable_orders": taxable_orders,
                "pct_taxable": pct_taxable,
                "avg_vat_rate": avg_vat_rate,
                "last_order_date": last_order_date_str,
                "built_at": built_at,
            }
        )
    return pd.DataFrame(out_rows, columns=cols)


def build_fee_country_model(df_raw: pd.DataFrame, df_official: pd.DataFrame) -> pd.DataFrame:
    """
    Build rolling fee model per country/marketplace/currency from Level 3 raw.
    Uses last 10 orders (by posted_date) and averages:
    - FBA fee per unit (ex-VAT)
    - Commission percent of item price (ex-VAT)
    - VAT rates per fee type (FBA, Commission, DSF)
    - DSF presence percentage
    """
    cols = [
        "country_code",
        "marketplace_id",
        "currency",
        "sample_orders",
        "fba_avg_ex_per_unit",
        "fba_taxable_pct",
        "fba_vat_rate",
        "commission_pct_avg",
        "commission_taxable_pct",
        "commission_vat_rate",
        "dsf_pct",
        "dsf_vat_rate",
        "last_order_date",
        "built_at",
    ]
    if df_raw is None or df_raw.empty:
        return pd.DataFrame(columns=cols)
    for col in ["order_id", "amount_type", "amount", "currency", "posted_date", "tax_amount"]:
        if col not in df_raw.columns:
            return pd.DataFrame(columns=cols)

    raw = df_raw.copy()
    raw["amount"] = pd.to_numeric(raw["amount"], errors="coerce").fillna(0.0).abs()
    raw["tax_amount"] = pd.to_numeric(raw["tax_amount"], errors="coerce").fillna(0.0).abs()
    raw["posted_date"] = pd.to_datetime(raw["posted_date"], errors="coerce", utc=True)
    raw["currency"] = raw["currency"].astype(str).str.strip()
    raw["amount_type"] = raw["amount_type"].astype(str).str.strip()
    raw = raw[raw["posted_date"].notna()]
    if raw.empty:
        return pd.DataFrame(columns=cols)

    fee_map = {
        "FBA_Fee": ["FBAPerUnitFulfillmentFee"],
        "Commission": ["Commission"],
        "Digital_Fee": ["DigitalServicesFee", "DigitalServicesFeeFBA"],
    }

    fee_rows = []
    for order_id, grp in raw.groupby("order_id"):
        out = {
            "order_id": order_id,
            "last_posted": grp["posted_date"].max(),
            "currency": next((v for v in grp["currency"].tolist() if v), ""),
        }
        for label, types in fee_map.items():
            sub = grp[grp["amount_type"].isin(types)]
            amt = float(sub["amount"].sum())
            tax = float(sub["tax_amount"].sum())
            if amt != 0.0:
                ex = amt - tax if tax > 0 else amt
                vat_rate = (tax / ex) if (ex > 0 and tax > 0) else 0.0
                out[f"{label}_ex"] = ex
                out[f"{label}_tax"] = tax
                out[f"{label}_vat_rate"] = vat_rate
            else:
                out[f"{label}_ex"] = 0.0
                out[f"{label}_tax"] = 0.0
                out[f"{label}_vat_rate"] = 0.0
        out["dsf_present"] = 1 if out.get("Digital_Fee_ex", 0.0) != 0.0 else 0
        fee_rows.append(out)
    fees = pd.DataFrame(fee_rows)

    # Attach qty and price_total from Level 3 official
    if df_official is not None and not df_official.empty:
        off = df_official.copy()
        off["Quantity Ordered"] = pd.to_numeric(off.get("Quantity Ordered"), errors="coerce").fillna(0.0)
        off["Price_Total"] = pd.to_numeric(off.get("Price_Total"), errors="coerce").fillna(0.0)
        qty_map = off.groupby("Order ID")["Quantity Ordered"].sum().rename("qty_sum")
        price_map = off.groupby("Order ID")["Price_Total"].sum().rename("price_total_sum")
        fees = fees.merge(qty_map, left_on="order_id", right_index=True, how="left")
        fees = fees.merge(price_map, left_on="order_id", right_index=True, how="left")
    else:
        fees["qty_sum"] = 0.0
        fees["price_total_sum"] = 0.0

    # Attach marketplace and country
    if ORDERS_ALL.exists():
        try:
            ord_map = read_finance_frame(ORDERS_ALL, dtype=str)[
                ["amazon_order_id", "marketplace_id", "ship_country_code"]
            ].rename(columns={"amazon_order_id": "order_id"})
            fees = fees.merge(ord_map, on="order_id", how="left")
        except Exception:
            fees["marketplace_id"] = ""
            fees["ship_country_code"] = ""
    else:
        fees["marketplace_id"] = ""
        fees["ship_country_code"] = ""

    fees["country_code"] = fees["ship_country_code"].astype(str).str.strip()
    fees["marketplace_id"] = fees["marketplace_id"].astype(str).str.strip()
    fees = fees[fees["last_posted"].notna()]
    if fees.empty:
        return pd.DataFrame(columns=cols)

    out_rows = []
    built_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for (country, market, curr), grp in fees.groupby(["country_code", "marketplace_id", "currency"]):
        grp = grp.sort_values(by="last_posted", ascending=False).head(10)
        sample_orders = len(grp)
        if sample_orders == 0:
            continue
        # FBA fee per unit
        fba_unit = grp.apply(
            lambda r: (r.get("FBA_Fee_ex", 0.0) / r.get("qty_sum", 0.0))
            if r.get("qty_sum", 0.0) > 0 else 0.0,
            axis=1,
        )
        fba_unit = fba_unit[fba_unit > 0]
        fba_avg = float(fba_unit.mean()) if not fba_unit.empty else 0.0
        fba_taxable = grp[grp["FBA_Fee_tax"] > 0]
        fba_taxable_pct = round(len(fba_taxable) / sample_orders, 3)
        fba_vat_rate = float(fba_taxable["FBA_Fee_vat_rate"].mean()) if len(fba_taxable) else 0.0

        # Commission percent of item price
        comm_pct = grp.apply(
            lambda r: (r.get("Commission_ex", 0.0) / r.get("price_total_sum", 0.0))
            if r.get("price_total_sum", 0.0) > 0 else 0.0,
            axis=1,
        )
        comm_pct = comm_pct[comm_pct > 0]
        comm_avg = float(comm_pct.mean()) if not comm_pct.empty else 0.0
        comm_taxable = grp[grp["Commission_tax"] > 0]
        comm_taxable_pct = round(len(comm_taxable) / sample_orders, 3)
        comm_vat_rate = float(comm_taxable["Commission_vat_rate"].mean()) if len(comm_taxable) else 0.0

        # DSF presence and VAT rate
        dsf_pct = round(float(grp["dsf_present"].sum()) / sample_orders, 3)
        dsf_taxable = grp[grp["Digital_Fee_tax"] > 0]
        dsf_vat_rate = float(dsf_taxable["Digital_Fee_vat_rate"].mean()) if len(dsf_taxable) else 0.0

        last_order_date = grp["last_posted"].max()
        last_order_date_str = last_order_date.strftime("%Y-%m-%d") if pd.notna(last_order_date) else ""
        out_rows.append(
            {
                "country_code": country,
                "marketplace_id": market,
                "currency": curr,
                "sample_orders": sample_orders,
                "fba_avg_ex_per_unit": round(fba_avg, 4),
                "fba_taxable_pct": fba_taxable_pct,
                "fba_vat_rate": round(fba_vat_rate, 4),
                "commission_pct_avg": round(comm_avg, 4),
                "commission_taxable_pct": comm_taxable_pct,
                "commission_vat_rate": round(comm_vat_rate, 4),
                "dsf_pct": dsf_pct,
                "dsf_vat_rate": round(dsf_vat_rate, 4),
                "last_order_date": last_order_date_str,
                "built_at": built_at,
            }
        )
    return pd.DataFrame(out_rows, columns=cols)


def flatten_events(events: Dict[str, object]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []

    def _money_val(m: Optional[Dict[str, object]], key_amount: str = "Amount") -> Tuple[str, str]:
        if not m:
            return "", ""
        amt = m.get(key_amount)
        if amt in ("", None):
            amt = m.get("CurrencyAmount", "")
        cur = m.get("CurrencyCode", "")
        return amt or "", cur or ""

    def add_row(
        order_id: str,
        asin: str,
        sku: str,
        posted: str,
        amount_type: str,
        is_fee: bool,
        amt: Dict[str, object],
        tx_type: str,
        tax: Optional[Dict[str, object]] = None,
    ) -> None:
        rows.append(
            {
                "order_id": order_id,
                "asin": asin,
                "sku": sku,
                "posted_date": posted,
                "transaction_type": tx_type,
                "amount_type": amount_type,
                "is_fee": is_fee,
                "amount": _money_val(amt)[0],
                "currency": _money_val(amt)[1],
                "tax_amount": _money_val(tax)[0],
                "tax_currency": _money_val(tax)[1],
            }
        )

    shipments = events.get("ShipmentEventList") or []
    for ev in shipments:
        order_id = ev.get("AmazonOrderId", "")
        posted_date = ev.get("PostedDate", "")
        for item in ev.get("ShipmentItemList") or []:
            asin = item.get("ASIN", "")
            sku = item.get("SellerSKU", "")
            for charge in item.get("ItemChargeList") or []:
                add_row(order_id, asin, sku, posted_date, charge.get("ChargeType", ""), False, charge.get("ChargeAmount"), "Shipment")
            for charge_adj in item.get("ItemChargeAdjustmentList") or []:
                add_row(order_id, asin, sku, posted_date, charge_adj.get("ChargeType", ""), False, charge_adj.get("ChargeAmount"), "ShipmentAdj")
            for fee in item.get("ItemFeeList") or []:
                add_row(order_id, asin, sku, posted_date, fee.get("FeeType", ""), True, fee.get("FeeAmount"), "Shipment")
            for fee_adj in item.get("ItemFeeAdjustmentList") or []:
                add_row(order_id, asin, sku, posted_date, fee_adj.get("FeeType", ""), True, fee_adj.get("FeeAmount"), "ShipmentAdj")
            for tax in item.get("ItemTaxWithheldList") or []:
                taxes_withheld = tax.get("TaxesWithheld") or []
                if taxes_withheld:
                    for tw in taxes_withheld:
                        add_row(order_id, asin, sku, posted_date, tw.get("ChargeType", ""), False, tw.get("ChargeAmount"), "Shipment")
                else:
                    add_row(order_id, asin, sku, posted_date, tax.get("TaxType", ""), False, tax.get("Amount"), "Shipment")
            for tax in item.get("ItemTaxWithheldComponentList") or []:
                add_row(order_id, asin, sku, posted_date, tax.get("TaxType", ""), False, tax.get("Amount"), "Shipment")
            for tax in item.get("TaxWithheldComponentList") or []:
                add_row(order_id, asin, sku, posted_date, tax.get("TaxType", ""), False, tax.get("Amount"), "Shipment")

    refunds = events.get("RefundEventList") or []
    for ev in refunds:
        order_id = ev.get("AmazonOrderId", "")
        posted_date = ev.get("PostedDate", "")
        for item in ev.get("ShipmentItemAdjustmentList") or []:
            asin = item.get("ASIN", "")
            sku = item.get("SellerSKU", "")
            for charge in item.get("ItemChargeAdjustmentList") or []:
                add_row(order_id, asin, sku, posted_date, f"Refund_{charge.get('ChargeType', '')}", False, charge.get("ChargeAmount"), "Refund")
            for fee in item.get("ItemFeeAdjustmentList") or []:
                add_row(order_id, asin, sku, posted_date, f"Refund_{fee.get('FeeType', '')}", True, fee.get("FeeAmount"), "Refund")
            for tax in item.get("ItemTaxWithheldList") or []:
                taxes_withheld = tax.get("TaxesWithheld") or []
                if taxes_withheld:
                    for tw in taxes_withheld:
                        add_row(
                            order_id,
                            asin,
                            sku,
                            posted_date,
                            f"Refund_{tw.get('ChargeType', '')}",
                            False,
                            tw.get("ChargeAmount"),
                            "Refund",
                        )
                else:
                    add_row(order_id, asin, sku, posted_date, f"Refund_{tax.get('TaxType', '')}", False, tax.get("Amount"), "Refund")
            for tax in item.get("ItemTaxWithheldComponentList") or []:
                add_row(order_id, asin, sku, posted_date, f"Refund_{tax.get('TaxType', '')}", False, tax.get("Amount"), "Refund")
            for tax in item.get("TaxWithheldComponentList") or []:
                add_row(order_id, asin, sku, posted_date, f"Refund_{tax.get('TaxType', '')}", False, tax.get("Amount"), "Refund")

    adjustments = events.get("AdjustmentEventList") or []
    for ev in adjustments:
        posted_date = ev.get("PostedDate", "")
        for adj in ev.get("AdjustmentItemList") or []:
            order_id = adj.get("AmazonOrderId", "")
            asin = adj.get("ASIN", "")
            sku = adj.get("SellerSKU", "")
            for charge in adj.get("ItemChargeList") or []:
                add_row(order_id, asin, sku, posted_date, f"Adjustment_{charge.get('ChargeType', '')}", False, charge.get("ChargeAmount"), "Adjustment")
            for fee in adj.get("ItemFeeList") or []:
                add_row(order_id, asin, sku, posted_date, f"Adjustment_{fee.get('FeeType', '')}", True, fee.get("FeeAmount"), "Adjustment")
    return rows


def flatten_account_events(events: Dict[str, object]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []

    def _money_val(m: Optional[Dict[str, object]], key_amount: str = "Amount") -> Tuple[str, str]:
        if not m:
            return "", ""
        amt = m.get(key_amount)
        if amt in ("", None):
            amt = m.get("CurrencyAmount", "")
        cur = m.get("CurrencyCode", "")
        return amt or "", cur or ""

    def _tax_val(item: Optional[Dict[str, object]]) -> Tuple[str, str]:
        if not item:
            return "", ""
        for key in ["TaxAmount", "FeeTaxAmount", "Tax", "FeeTax"]:
            val = item.get(key)
            if isinstance(val, dict):
                amt = val.get("Amount")
                if amt in ("", None):
                    amt = val.get("CurrencyAmount", "")
                cur = val.get("CurrencyCode", "")
                if amt not in ("", None) or cur:
                    return amt or "", cur or ""
        return "", ""

    def add_row(
        posted: str,
        amount_type: str,
        is_fee: bool,
        amt: Dict[str, object],
        tax: Dict[str, object],
        tx_type: str,
        order_id: str,
        shipment_id: str,
        inbound_shipment_id: str,
        fee_reason: str,
        fee_description: str,
        parsed_fba_shipment_id: str,
    ) -> None:
        tax_amt, tax_cur = _tax_val(tax)
        rows.append(
            {
                "posted_date": posted,
                "transaction_type": tx_type,
                "amount_type": amount_type,
                "is_fee": is_fee,
                "amount": _money_val(amt)[0],
                "currency": _money_val(amt)[1],
                "tax_amount": tax_amt,
                "tax_currency": tax_cur,
                "order_id": order_id,
                "shipment_id": shipment_id,
                "inbound_shipment_id": inbound_shipment_id,
                "fee_reason": fee_reason,
                "fee_description": fee_description,
                "parsed_fba_shipment_id": parsed_fba_shipment_id,
            }
        )

    order_lists = {"ShipmentEventList", "RefundEventList", "AdjustmentEventList"}
    fba_id_re = re.compile(r"(FBA[A-Z0-9]{7,})")
    list_specs = [
        ("FeeList", "FeeType", "FeeAmount", True),
        ("FeeAdjustmentList", "FeeType", "FeeAmount", True),
        ("ChargeList", "ChargeType", "ChargeAmount", False),
        ("ChargeAdjustmentList", "ChargeType", "ChargeAmount", False),
        ("TaxWithheldList", "TaxType", "Amount", False),
        ("TaxWithheldComponentList", "TaxType", "Amount", False),
    ]

    for list_name, ev_list in events.items():
        if not list_name.endswith("EventList"):
            continue
        if list_name in order_lists:
            continue
        for ev in ev_list or []:
            posted = ev.get("PostedDate", "") or ev.get("TransactionDate", "") or ev.get("PostedDateTime", "")
            order_id = ev.get("AmazonOrderId", "") or ev.get("OrderId", "")
            shipment_id = ev.get("ShipmentId", "") or ev.get("ShipmentIdentifier", "")
            inbound_shipment_id = ev.get("FBAInboundShipmentId", "") or ev.get("InboundShipmentId", "")
            fee_reason = ev.get("FeeReason", "") or ev.get("FeeType", "")
            fee_description = ev.get("FeeDescription", "") or ev.get("Description", "")
            match = fba_id_re.search(str(fee_description)) if fee_description else None
            parsed_fba_shipment_id = match.group(1) if match else ""
            if isinstance(shipment_id, list):
                shipment_id = ";".join([str(x) for x in shipment_id if x])
            if isinstance(inbound_shipment_id, list):
                inbound_shipment_id = ";".join([str(x) for x in inbound_shipment_id if x])
            for list_key, type_key, amount_key, is_fee in list_specs:
                for item in ev.get(list_key) or []:
                    amt = item.get(amount_key) or item.get("ChargeAmount") or item.get("FeeAmount") or item.get("Amount")
                    if not amt:
                        continue
                    amount_type = item.get(type_key, "") or list_key.replace("List", "")
                    add_row(
                        posted,
                        amount_type,
                        is_fee,
                        amt,
                        item,
                        list_name.replace("EventList", ""),
                        order_id,
                        shipment_id,
                        inbound_shipment_id,
                        fee_reason,
                        fee_description,
                        parsed_fba_shipment_id,
                    )
    return rows


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=["order_id", "amount_type", "is_fee", "total_amount", "tax_present", "currency", "derived_ex_vat", "derived_vat"]
        )
    df["tax_present"] = df["tax_amount"].apply(lambda v: str(v).strip() not in ("", "nan", "None"))
    group = df.groupby(["order_id", "amount_type", "is_fee", "currency"], dropna=False)
    agg = group.agg(
        total_amount=pd.NamedAgg(column="amount", aggfunc=lambda s: sum(float(x) for x in s if str(x).strip() not in ("", "nan", "None"))),
        tax_present=pd.NamedAgg(column="tax_present", aggfunc=lambda s: any(s)),
    ).reset_index()
    # derive VAT split for fee lines with no tax provided
    def split_fee(row):
        if not row["is_fee"]:
            return "", ""
        if row["tax_present"]:
            return "", ""
        gross = row["total_amount"]
        ex = round(gross / 1.2, 2)
        vat = round(gross - ex, 2)
        return ex, vat

    splits = agg.apply(split_fee, axis=1)
    agg["derived_ex_vat"] = [s[0] for s in splits]
    agg["derived_vat"] = [s[1] for s in splits]
    return agg[["order_id", "amount_type", "is_fee", "total_amount", "tax_present", "currency", "derived_ex_vat", "derived_vat"]]


def main() -> None:
    load_dotenv_if_missing()
    seed_override = os.environ.get("FIN_L3_SEED_START")
    if seed_override:
        try:
            seed_dt = datetime.fromisoformat(seed_override.replace("Z", "+00:00"))
        except Exception:
            seed_dt = SEED_START
    else:
        seed_dt = SEED_START
    now = datetime.now(timezone.utc)
    default_after_dt = seed_dt
    default_before_dt = now - timedelta(minutes=5)

    if DO_CLEAN:
        for path in [
            OUT_RAW,
            OUT_SUM,
            OUT_OFFICIAL,
            OUT_ACCOUNT,
            OUT_REFUNDS,
            OUT_REFUNDS_OFFICIAL,
            OUT_SHIPMENTS,
            OUT_INBOUND_SUM,
            OUT_STORAGE,
            OUT_STORAGE_SUM,
            OUT_ACCOUNT_SUM,
        ]:
            try:
                if path.exists():
                    path.unlink()
            except Exception:
                pass

    marker = _load_marker()
    save_marker = True
    if marker:
        try:
            marker_dt = datetime.fromisoformat(marker.replace("Z", "+00:00"))
        except Exception:
            marker_dt = None
        if marker_dt and marker_dt <= default_before_dt and marker_dt >= default_after_dt:
            posted_after_dt = marker_dt
            posted_before_dt = default_before_dt
        else:
            # Marker outside window; use seed start and do not overwrite marker
            posted_after_dt = default_after_dt
            posted_before_dt = default_before_dt
            save_marker = False
    else:
        posted_after_dt = default_after_dt
        posted_before_dt = default_before_dt

    if POSTED_BEFORE_ENV:
        try:
            posted_before_dt = datetime.fromisoformat(POSTED_BEFORE_ENV.replace("Z", "+00:00"))
        except Exception:
            posted_before_dt = default_before_dt
    posted_after = _iso(posted_after_dt)
    posted_before = _iso(posted_before_dt)
    if POSTED_AFTER_ENV or POSTED_BEFORE_ENV:
        save_marker = False

    # Streaming fetch with durability: append raw per page, update marker as we go
    token = get_lwa_access_token()
    next_token = None
    latest_posted: Optional[str] = posted_after
    OUT_RAW.parent.mkdir(parents=True, exist_ok=True)
    wrote_header = OUT_RAW.exists() and OUT_RAW.stat().st_size > 0
    wrote_account_header = OUT_ACCOUNT.exists() and OUT_ACCOUNT.stat().st_size > 0
    if wrote_account_header:
        try:
            df_existing = pd.read_csv(OUT_ACCOUNT, dtype=str)
            for col in [
                "tax_amount",
                "tax_currency",
                "shipment_id",
                "inbound_shipment_id",
                "fee_reason",
                "fee_description",
                "parsed_fba_shipment_id",
            ]:
                if col not in df_existing.columns:
                    df_existing[col] = ""
            df_existing.to_csv(OUT_ACCOUNT, index=False)
        except Exception:
            pass
    while True:
        attempt = 0
        while True:
            attempt += 1
            try:
                events_batch, next_token = list_financial_events(
                    access_token=token,
                    posted_after=posted_after,
                    posted_before=posted_before,
                    next_token=next_token,
                )
                break
            except Exception as exc:
                msg = str(exc).lower()
                if any(code in msg for code in ["unauthorized", "invalid access token", "expired"]):
                    token = get_lwa_access_token()
                if attempt >= MAX_RETRIES:
                    raise
                _backoff_sleep(attempt)
                continue
        time.sleep(BASE_SLEEP)
        batch_rows = flatten_events(events_batch)
        account_rows = flatten_account_events(events_batch)
        if DEBUG_ORDER_ID:
            debug_path = Path(f"out/financial_events_level3_debug_{DEBUG_ORDER_ID}.jsonl")
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            for list_name, ev_list in events_batch.items():
                if not list_name.endswith("EventList"):
                    continue
                for ev in ev_list or []:
                    oid = ev.get("AmazonOrderId") or ev.get("OrderId") or ""
                    if str(oid).strip() != str(DEBUG_ORDER_ID).strip():
                        continue
                    debug_path.write_text("", encoding="utf-8") if not debug_path.exists() else None
                    with debug_path.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps({"event_list": list_name, "event": ev}, ensure_ascii=True) + "\n")
        if DEBUG_SERVICE_FEE:
            debug_path = Path("out/financial_events_service_fee_debug.jsonl")
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            for list_name, ev_list in events_batch.items():
                if list_name != "ServiceFeeEventList":
                    continue
                for ev in ev_list or []:
                    with debug_path.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps({"event_list": list_name, "event": ev}, ensure_ascii=True) + "\n")
        if batch_rows:
            df_batch = pd.DataFrame(batch_rows)
            df_batch.to_csv(OUT_RAW, mode="a", index=False, header=not wrote_header)
            wrote_header = True
            for r in batch_rows:
                pd_val = r.get("posted_date")
                if pd_val:
                    latest_posted = max(latest_posted or pd_val, pd_val)
            if latest_posted and save_marker:
                _save_marker(latest_posted)
        if account_rows:
            df_account_batch = pd.DataFrame(account_rows)
            df_account_batch.to_csv(OUT_ACCOUNT, mode="a", index=False, header=not wrote_account_header)
            wrote_account_header = True
        if not next_token:
            break

    # Build summary from full raw (and de-dupe in-memory only).
    if OUT_RAW.exists():
        df_raw = pd.read_csv(OUT_RAW, dtype=str)
        replace_finance_table(df_raw.fillna(""), SQL_TABLE_RAW)
        dedup_subset = [
            "order_id",
            "sku",
            "amount_type",
            "amount",
            "tax_amount",
            "posted_date",
            "transaction_type",
        ]
        extra_ids = [c for c in ("order_item_id", "shipment_id", "line_id", "shipment_event_id") if c in df_raw.columns]
        # If no unique IDs are available, cap duplicate identical lines using Quantity Ordered.
        qty_map = {}
        qty_cap_map = {}
        if ITEMS_ALL.exists():
            items = read_finance_frame(ITEMS_ALL, dtype=str)[["amazon_order_id", "seller_sku", "quantity_ordered"]]
            items["quantity_ordered"] = pd.to_numeric(items["quantity_ordered"], errors="coerce").fillna(0).astype(int)
            qty_map = (
                items.groupby(["amazon_order_id", "seller_sku"])["quantity_ordered"]
                .sum()
                .to_dict()
            )
            # Fallback per-order qty for rows where sku is missing in L3 raw.
            qty_map_order = items.groupby(["amazon_order_id"])["quantity_ordered"].sum().to_dict()
            for oid, qty in qty_map_order.items():
                qty_map[(oid, "")] = qty
            qty_cap_map = dict(qty_map)
            # If order total is available and per-line amounts already represent total,
            # cap duplicates to 1 even when qty > 1.
            if ORDERS_ALL.exists():
                orders = read_finance_frame(ORDERS_ALL, dtype=str)[["amazon_order_id", "order_total_amount"]]
                orders["order_total_amount"] = pd.to_numeric(orders["order_total_amount"], errors="coerce").fillna(0.0)
                order_total_map = orders.set_index("amazon_order_id")["order_total_amount"].to_dict()
                # Build principal/tax lookup from raw for each order+sku.
                pt = df_raw[df_raw["amount_type"].isin(["Principal", "Tax"])].copy()
                if not pt.empty:
                    pt["amount"] = pd.to_numeric(pt["amount"], errors="coerce").fillna(0.0)
                    pt_sum = (
                        pt.groupby(["order_id", "sku", "amount_type"])["amount"]
                        .first()
                        .unstack(fill_value=0.0)
                    )
                    for (oid, sku), row in pt_sum.iterrows():
                        qty = qty_map.get((oid, sku)) or qty_map.get((oid, "")) or 0
                        if qty and qty > 1:
                            order_total = order_total_map.get(oid, 0.0)
                            expected = (row.get("Principal", 0.0) + row.get("Tax", 0.0)) * qty
                            # If expected is materially above order total, treat line as order-total and cap to 1.
                            if order_total and expected > order_total * 1.01:
                                qty_cap_map[(oid, sku)] = 1
                                qty_cap_map[(oid, "")] = 1
        if qty_map:
            # Keep up to ordered qty; this also prevents double-counting from repeated pulls.
            df_raw = _trim_duplicate_lines_by_qty(df_raw, qty_cap_map or qty_map)
        else:
            if extra_ids:
                df_raw = df_raw.drop_duplicates(subset=dedup_subset + extra_ids)
            else:
                df_raw = df_raw.drop_duplicates(subset=dedup_subset)
                print({"status": "warn", "reason": "dedup_limited_no_unique_id", "rows": len(df_raw)})
        # Keep raw append-only; write de-duplicated view to a separate file.
        _write_output_frame(df_raw, OUT_RAW_DEDUP, SQL_TABLE_RAW_DEDUP)
    else:
        df_raw = pd.DataFrame()
    df_sum = summarize(df_raw)
    _write_output_frame(df_sum, OUT_SUM, SQL_TABLE_SUMMARY)
    if OUT_ACCOUNT.exists():
        df_shipments = pd.read_csv(OUT_ACCOUNT, dtype=str)
        for col in [
            "tax_amount",
            "tax_currency",
            "shipment_id",
            "inbound_shipment_id",
            "fee_reason",
            "fee_description",
            "parsed_fba_shipment_id",
        ]:
            if col not in df_shipments.columns:
                df_shipments[col] = ""
        mask_inbound = (
            df_shipments["amount_type"].astype(str).str.contains("InboundTransportation", case=False, na=False)
            | df_shipments["fee_reason"].astype(str).str.contains("Inbound", case=False, na=False)
            | df_shipments["fee_description"].astype(str).str.contains("Inbound", case=False, na=False)
        )
        df_shipments = df_shipments[mask_inbound].copy()
        if not df_shipments.empty:
            df_shipments = df_shipments.drop_duplicates(
                subset=[
                    "posted_date",
                    "transaction_type",
                    "amount_type",
                    "amount",
                    "currency",
                    "order_id",
                    "shipment_id",
                    "inbound_shipment_id",
                    "fee_reason",
                    "fee_description",
                    "parsed_fba_shipment_id",
                ]
            )
    else:
        df_shipments = pd.DataFrame()
    if df_shipments is None or df_shipments.empty:
        df_shipments = pd.DataFrame(
            columns=[
                "posted_date",
                "transaction_type",
                "amount_type",
                "is_fee",
                "amount",
                "currency",
                "tax_amount",
                "tax_currency",
                "order_id",
                "shipment_id",
                "inbound_shipment_id",
                "fee_reason",
                "fee_description",
                "parsed_fba_shipment_id",
            ]
        )
    _write_output_frame(df_shipments, OUT_SHIPMENTS, SQL_TABLE_SHIPMENTS)
    if not df_shipments.empty:
        inbound = df_shipments.copy()
        inbound["__date"] = pd.to_datetime(inbound["posted_date"], errors="coerce", utc=True).dt.strftime("%Y-%m-%d")
        fallback_date = posted_before_dt.strftime("%Y-%m-%d")
        missing_date = inbound["__date"].isna() | (inbound["__date"] == "")
        inbound.loc[missing_date, "__date"] = fallback_date
        inbound["date_source"] = "posted_date"
        inbound.loc[missing_date, "date_source"] = "estimated"
        inbound["amount"] = pd.to_numeric(inbound["amount"], errors="coerce").fillna(0.0)
        inbound_sum = (
            inbound.groupby(
                ["__date", "date_source", "amount_type", "fee_reason", "fee_description", "currency"], dropna=False
            )["amount"]
            .sum()
            .reset_index()
            .rename(columns={"__date": "date", "amount": "total_amount"})
        )
    else:
        inbound_sum = pd.DataFrame(
            columns=[
                "date",
                "date_source",
                "amount_type",
                "fee_reason",
                "fee_description",
                "currency",
                "total_amount",
            ]
        )
    _write_output_frame(inbound_sum, OUT_INBOUND_SUM, SQL_TABLE_INBOUND_SUMMARY)
    if OUT_ACCOUNT.exists():
        df_storage = pd.read_csv(OUT_ACCOUNT, dtype=str)
        for col in [
            "tax_amount",
            "tax_currency",
            "shipment_id",
            "inbound_shipment_id",
            "fee_reason",
            "fee_description",
            "parsed_fba_shipment_id",
        ]:
            if col not in df_storage.columns:
                df_storage[col] = ""
        mask_storage = df_storage["amount_type"].astype(str).str.contains("StorageFee", case=False, na=False)
        df_storage = df_storage[mask_storage].copy()
        if not df_storage.empty:
            df_storage = df_storage.drop_duplicates(
                subset=[
                    "posted_date",
                    "transaction_type",
                    "amount_type",
                    "amount",
                    "currency",
                    "order_id",
                    "shipment_id",
                    "inbound_shipment_id",
                    "fee_reason",
                    "fee_description",
                    "parsed_fba_shipment_id",
                ]
            )
    else:
        df_storage = pd.DataFrame()
    if df_storage is None or df_storage.empty:
        df_storage = pd.DataFrame(
            columns=[
                "posted_date",
                "date",
                "date_source",
                "transaction_type",
                "amount_type",
                "is_fee",
                "amount",
                "currency",
                "order_id",
                "shipment_id",
                "inbound_shipment_id",
                "fee_reason",
                "fee_description",
                "parsed_fba_shipment_id",
            ]
        )
    if not df_storage.empty:
        storage = df_storage.copy()
        storage["date"] = pd.to_datetime(storage["posted_date"], errors="coerce", utc=True).dt.strftime("%Y-%m-%d")
        fallback_date = posted_before_dt.strftime("%Y-%m-%d")
        missing_date = storage["date"].isna() | (storage["date"] == "")
        storage.loc[missing_date, "date"] = fallback_date
        storage["date_source"] = "posted_date"
        storage.loc[missing_date, "date_source"] = "estimated"
        storage["amount"] = pd.to_numeric(storage["amount"], errors="coerce").fillna(0.0)
        df_storage = storage.copy()
        storage_sum = (
            storage.groupby(
                ["date", "date_source", "amount_type", "fee_reason", "fee_description", "currency"], dropna=False
            )["amount"]
            .sum()
            .reset_index()
            .rename(columns={"amount": "total_amount"})
        )
    else:
        storage_sum = pd.DataFrame(
            columns=["date", "date_source", "amount_type", "fee_reason", "fee_description", "currency", "total_amount"]
        )
    _write_output_frame(df_storage, OUT_STORAGE, SQL_TABLE_STORAGE)
    _write_output_frame(storage_sum, OUT_STORAGE_SUM, SQL_TABLE_STORAGE_SUMMARY)
    if not df_raw.empty and "amount_type" in df_raw.columns:
        df_refunds = df_raw[df_raw["amount_type"].astype(str).str.startswith("Refund", na=False)].copy()
        if not df_refunds.empty:
            df_refunds = df_refunds.drop_duplicates(
                subset=["order_id", "sku", "amount_type", "amount", "tax_amount", "posted_date"]
            )
    else:
        df_refunds = pd.DataFrame()
    if df_refunds is None or df_refunds.empty:
        df_refunds = pd.DataFrame(
            columns=[
                "order_id",
                "asin",
                "sku",
                "posted_date",
                "transaction_type",
                "amount_type",
                "is_fee",
                "amount",
                "currency",
                "tax_amount",
                "tax_currency",
            ]
        )
    _write_output_frame(df_refunds, OUT_REFUNDS, SQL_TABLE_REFUNDS)
    df_refunds_official = build_refunds_official(df_raw)
    if not df_refunds_official.empty and ITEMS_ALL.exists():
        items = read_finance_frame(ITEMS_ALL, dtype=str)[["amazon_order_id", "seller_sku", "quantity_ordered"]].rename(
            columns={"amazon_order_id": "Order ID", "seller_sku": "SKU", "quantity_ordered": "Quantity Ordered"}
        )
        if "Quantity Ordered" in df_refunds_official.columns:
            df_refunds_official["Quantity Ordered"] = df_refunds_official["Quantity Ordered"].replace("", pd.NA)
        df_refunds_official = df_refunds_official.merge(items, on=["Order ID", "SKU"], how="left", suffixes=("", "_src"))
        df_refunds_official["Quantity Ordered"] = df_refunds_official["Quantity Ordered"].fillna(
            df_refunds_official["Quantity Ordered_src"]
        )
        df_refunds_official = df_refunds_official.drop(columns=[c for c in df_refunds_official.columns if c.endswith("_src")])
    if not df_refunds_official.empty:
        sort_key = pd.to_datetime(df_refunds_official["Date"], errors="coerce")
        df_refunds_official = df_refunds_official.assign(_sort=sort_key).sort_values(by=["_sort", "Order ID"]).drop(
            columns=["_sort"]
        )
    _write_output_frame(df_refunds_official, OUT_REFUNDS_OFFICIAL, SQL_TABLE_REFUNDS_OFFICIAL)
    if OUT_ACCOUNT.exists():
        df_account = pd.read_csv(OUT_ACCOUNT, dtype=str)
        for col in [
            "shipment_id",
            "inbound_shipment_id",
            "fee_reason",
            "fee_description",
            "parsed_fba_shipment_id",
        ]:
            if col not in df_account.columns:
                df_account[col] = ""
        df_account = df_account.drop_duplicates(
            subset=[
                "posted_date",
                "transaction_type",
                "amount_type",
                "amount",
                "currency",
                "order_id",
                "shipment_id",
                "inbound_shipment_id",
                "fee_reason",
                "fee_description",
                "parsed_fba_shipment_id",
            ]
        )
        account = df_account.copy()
        account["date"] = pd.to_datetime(account["posted_date"], errors="coerce", utc=True).dt.strftime("%Y-%m-%d")
        fallback_date = posted_before_dt.strftime("%Y-%m-%d")
        missing_date = account["date"].isna() | (account["date"] == "")
        account.loc[missing_date, "date"] = fallback_date
        account["date_source"] = "posted_date"
        account.loc[missing_date, "date_source"] = "estimated"
        account["amount"] = pd.to_numeric(account["amount"], errors="coerce").fillna(0.0)
        account_summary = (
            account.groupby(["date", "date_source", "transaction_type", "amount_type", "currency"], dropna=False)["amount"]
            .sum()
            .reset_index()
            .rename(columns={"amount": "total_amount"})
        )
    else:
        df_account = pd.DataFrame(
            columns=[
                "posted_date",
                "transaction_type",
                "amount_type",
                "is_fee",
                "amount",
                "currency",
                "tax_amount",
                "tax_currency",
                "order_id",
                "shipment_id",
                "inbound_shipment_id",
                "fee_reason",
                "fee_description",
                "parsed_fba_shipment_id",
            ]
        )
        account_summary = pd.DataFrame(
            columns=["date", "date_source", "transaction_type", "amount_type", "currency", "total_amount"]
        )
    replace_finance_table(df_account.fillna(""), SQL_TABLE_ACCOUNT)
    _write_output_frame(account_summary, OUT_ACCOUNT_SUM, SQL_TABLE_ACCOUNT_SUMMARY)
    # Build official (Level_2-like) and sort by Date then Order ID
    df_official = build_official(df_raw)
    # Backfill Quantity Ordered from archived order items if available
    if not df_official.empty and ITEMS_ALL.exists():
        items = read_finance_frame(ITEMS_ALL, dtype=str)[["amazon_order_id", "seller_sku", "quantity_ordered"]].rename(
            columns={"amazon_order_id": "Order ID", "seller_sku": "SKU", "quantity_ordered": "Quantity Ordered"}
        )
        if "Quantity Ordered" in df_official.columns:
            df_official["Quantity Ordered"] = df_official["Quantity Ordered"].replace("", pd.NA)
        df_official = df_official.merge(items, on=["Order ID", "SKU"], how="left", suffixes=("", "_src"))
        df_official["Quantity Ordered"] = df_official["Quantity Ordered"].fillna(df_official["Quantity Ordered_src"])
        df_official = df_official.drop(columns=[c for c in df_official.columns if c.endswith("_src")])
    if not df_official.empty:
        sort_key = pd.to_datetime(df_official["Date"], errors="coerce")
        df_official = df_official.assign(_sort=sort_key).sort_values(by=["_sort", "Order ID"]).drop(columns=["_sort"])
    _write_output_frame(df_official, OUT_OFFICIAL, SQL_TABLE_OFFICIAL)
    df_l2_vs_l3 = write_l2_vs_l3_discrepancies(df_official)

    df_vat_model = build_vat_country_model(df_raw)
    _write_output_frame(df_vat_model, OUT_VAT_MODEL, SQL_TABLE_VAT_MODEL)
    df_fee_model = build_fee_country_model(df_raw, df_official)
    _write_output_frame(df_fee_model, OUT_FEE_MODEL, SQL_TABLE_FEE_MODEL)

    if latest_posted and save_marker:
        _save_marker(latest_posted)
    # Sheets write (single shot to avoid quota issues)
    try:
        if FIN_L3_SKIP_SHEETS:
            raise RuntimeError("FIN_L3_SKIP_SHEETS=1")
        # Select which tabs to write to avoid workbook cell-limit failures.
        write_all = FIN_L3_SHEETS_MODE != "official_only"
        if write_all:
            # If any dataset is too large, fall back to official_only.
            if any(
                _too_big_for_sheets(df)
                for df in [
                    df_raw,
                    df_sum,
                    df_official,
                    df_account,
                    df_shipments,
                    inbound_sum,
                    df_storage,
                    storage_sum,
                    account_summary,
                    df_refunds,
                    df_refunds_official,
                    df_l2_vs_l3,
                ]
            ):
                write_all = False
        client = get_gspread_client()
        sheet = client.open_by_key(SHEET_ID)
        if write_all:
            write_tab_with_retry(sheet, RAW_TAB, df_raw)
            write_tab_with_retry(sheet, SUMMARY_TAB, df_sum)
            write_tab_with_retry(sheet, OFFICIAL_TAB, df_official)
            write_tab_with_retry(sheet, ACCOUNT_TAB, df_account)
            write_tab_with_retry(sheet, SHIPMENTS_TAB, df_shipments)
            write_tab_with_retry(sheet, INBOUND_SUM_TAB, inbound_sum)
            write_tab_with_retry(sheet, STORAGE_TAB, df_storage)
            write_tab_with_retry(sheet, STORAGE_SUM_TAB, storage_sum)
            write_tab_with_retry(sheet, ACCOUNT_SUM_TAB, account_summary)
            write_tab_with_retry(sheet, REFUNDS_TAB, df_refunds)
            write_tab_with_retry(sheet, REFUNDS_OFFICIAL_TAB, df_refunds_official)
            write_tab_with_retry(sheet, L2_VS_L3_TAB, df_l2_vs_l3)
        else:
            print({"status": "info", "sheets_mode": "official_only"})
            write_tab_with_retry(sheet, OFFICIAL_TAB, df_official)
            write_tab_with_retry(sheet, REFUNDS_OFFICIAL_TAB, df_refunds_official)
        update_product_db_last_fba_fee(df_official, df_raw)
    except Exception as exc:
        print({"status": "warning", "alert": "sheets_error", "error": str(exc)})
    print(
        {
            "status": "success",
            "posted_after": posted_after,
            "posted_before": posted_before,
            "rows_raw": len(df_raw),
            "rows_summary": len(df_sum),
            "rows_official": len(df_official),
            "latest_posted_saved": latest_posted,
            "snapshot": f"{OUT_RAW};{OUT_SUM};{OUT_OFFICIAL};{OUT_ACCOUNT};{OUT_ACCOUNT_SUM};{OUT_SHIPMENTS};{OUT_INBOUND_SUM};{OUT_STORAGE};{OUT_STORAGE_SUM};{OUT_REFUNDS};{OUT_REFUNDS_OFFICIAL};{OUT_VAT_MODEL};{OUT_FEE_MODEL}",
        }
    )


if __name__ == "__main__":
    main()
ORDERS_ALL = Path("out/orders_all.csv")


