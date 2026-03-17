"""
Allocate available tokens to Order_Master rows (all SKUs) and write to sheet.
Idempotent: only allocates when order quantity exceeds existing allocations.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, UTC
from pathlib import Path
import csv

import pandas as pd
try:
    import gspread
except Exception:  # pragma: no cover - optional dependency for degraded local mode
    gspread = None

import os
import sys
from scripts.core.out_paths import resolve_compat_path, write_csv_with_compat


TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
TOKENS_TAB = "Token_Ledger"
ALLOC_TAB = "Token_Allocations"
LOG_TAB = "Token_Log"
LEVEL1_SHEET_ID = "1BHueJTk4dvvhIXypzh6i2hQTgc0pB3DWj2khQ2IT6_A"
LEVEL1_TAB = "Level_1_Immediate"
ORDER_MASTER_PATH = Path("out/order_master.csv")
INVENTORY_SNAPSHOT_PATH = Path("out/inventory_summaries.csv")
LEVEL1_PATH = Path("out/financial_events_level1.csv")
MISSING_TOKEN_ORDERS = Path("out/orders_missing_tokens.csv")
SKIPPED_PATH = Path("out/token_allocation_skipped.csv")
B_SHEET_SYNC_STATUS_PATH = Path("out/b_sheet_sync_status.csv")

LEVEL1_SYNC_COGS = os.getenv("LEVEL1_SYNC_COGS", "1") == "1"
if os.environ.get("B_CYCLE_QUIET", "0") == "1":
    LEVEL1_SYNC_COGS = False
SKIP_TOKEN_SHEETS = os.environ.get("B_CYCLE_QUIET", "0") == "1"
PRODUCT_DB = Path("out/product_db_preview.csv")
DEFAULT_VAT_RATE = float(os.environ.get("DEFAULT_COGS_VAT_RATE", "20"))


def parse_date(value: str | float) -> datetime | None:
    if value is None or pd.isna(value):
        return None
    value = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def load_sheet_df(ws: gspread.Worksheet) -> pd.DataFrame:
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()
    header, rows = values[0], values[1:]
    return pd.DataFrame(rows, columns=header)


def _append_sync_status(
    *,
    step: str,
    status: str,
    severity: str,
    mode: str,
    note: str,
    local_rows: int = -1,
    sheet_rows: int = -1,
) -> None:
    headers = [
        "timestamp_utc",
        "step",
        "status",
        "severity",
        "mode",
        "local_rows",
        "sheet_rows",
        "note",
    ]
    B_SHEET_SYNC_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    need_header = (not B_SHEET_SYNC_STATUS_PATH.exists()) or B_SHEET_SYNC_STATUS_PATH.stat().st_size == 0
    with B_SHEET_SYNC_STATUS_PATH.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        if need_header:
            writer.writeheader()
        writer.writerow(
            {
                "timestamp_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "step": step,
                "status": status,
                "severity": severity,
                "mode": mode,
                "local_rows": str(local_rows if local_rows >= 0 else ""),
                "sheet_rows": str(sheet_rows if sheet_rows >= 0 else ""),
                "note": str(note or "").strip(),
            }
        )


def _load_local_token_and_alloc() -> tuple[pd.DataFrame, pd.DataFrame]:
    token_path = resolve_compat_path("token_ledger_live.csv", default_system="B")
    alloc_path = resolve_compat_path("token_allocations_live.csv", default_system="B")
    token_local = token_path.live_path if token_path.live_path.exists() else token_path.legacy_path
    alloc_local = alloc_path.live_path if alloc_path.live_path.exists() else alloc_path.legacy_path
    token_df = pd.DataFrame()
    alloc_df = pd.DataFrame()
    if token_local.exists():
        token_df = pd.read_csv(token_local, dtype=str).fillna("")
    if alloc_local.exists():
        alloc_df = pd.read_csv(alloc_local, dtype=str).fillna("")
    return token_df, alloc_df


def get_or_create_ws(sheet: gspread.Spreadsheet, title: str) -> gspread.Worksheet:
    try:
        return sheet.worksheet(title)
    except gspread.WorksheetNotFound:
        return sheet.add_worksheet(title=title, rows=1000, cols=20)


def write_ws(ws: gspread.Worksheet, df: pd.DataFrame) -> None:
    rows = [df.columns.tolist()] + df.astype(object).where(pd.notnull(df), "").values.tolist()
    ws.clear()
    ws.update(rows, value_input_option="RAW")


def _to_num(val: object) -> float:
    try:
        return float(val)
    except Exception:
        return 0.0


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


def _load_missing_token_orders() -> pd.DataFrame:
    if not MISSING_TOKEN_ORDERS.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(MISSING_TOKEN_ORDERS, dtype=str)
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return pd.DataFrame()
    required = ["Order ID", "SKU", "Date", "Quantity Ordered"]
    for col in required:
        if col not in df.columns:
            df[col] = ""
    return df[required]


def sync_level1_cogs(token_df: pd.DataFrame, client: gspread.Client | None) -> None:
    if not LEVEL1_SYNC_COGS:
        return
    if token_df.empty:
        return
    if "allocated_order_id" not in token_df.columns or "seller_sku" not in token_df.columns:
        return

    alloc = token_df.copy()
    alloc["allocated_order_id"] = alloc["allocated_order_id"].fillna("").astype(str)
    alloc["seller_sku"] = alloc["seller_sku"].fillna("").astype(str)
    alloc = alloc[(alloc["allocated_order_id"] != "") & (alloc["seller_sku"] != "")]
    if alloc.empty:
        return

    alloc["token_cost_num"] = pd.to_numeric(alloc.get("cost_per_unit"), errors="coerce").fillna(0.0)
    grouped = (
        alloc.groupby(["allocated_order_id", "seller_sku"], as_index=False)["token_cost_num"]
        .sum()
        .rename(columns={"allocated_order_id": "Order ID", "seller_sku": "SKU"})
    )
    vat_map = _load_vat_rate_map()
    if vat_map:
        grouped["vat_rate_pct"] = grouped["SKU"].map(vat_map).fillna(DEFAULT_VAT_RATE)
    else:
        grouped["vat_rate_pct"] = DEFAULT_VAT_RATE
    grouped["COGS_ExVAT"] = (-grouped["token_cost_num"]).round(2)
    grouped["COGS_VAT"] = (grouped["COGS_ExVAT"].abs() * grouped["vat_rate_pct"] / 100.0).round(2)
    grouped["COGS_VAT"] = (-grouped["COGS_VAT"])
    grouped["COGS_Total"] = (grouped["COGS_ExVAT"] + grouped["COGS_VAT"]).round(2)

    if LEVEL1_PATH.exists():
        try:
            df_level1 = pd.read_csv(LEVEL1_PATH, dtype=str).fillna("")
        except Exception:
            df_level1 = pd.DataFrame()
    else:
        df_level1 = pd.DataFrame()

    if df_level1.empty and client is not None:
        try:
            level1_sheet = client.open_by_key(LEVEL1_SHEET_ID)
            level1_ws = level1_sheet.worksheet(LEVEL1_TAB)
            df_level1 = load_sheet_df(level1_ws)
        except Exception:
            return

    if df_level1.empty:
        return

    df_level1 = df_level1.copy()
    df_level1["Order ID"] = df_level1.get("Order ID", "").astype(str)
    df_level1["SKU"] = df_level1.get("SKU", "").astype(str)

    df_level1 = df_level1.merge(grouped[["Order ID", "SKU", "COGS_ExVAT", "COGS_VAT", "COGS_Total"]],
                                on=["Order ID", "SKU"], how="left", suffixes=("", "_new"))

    for col in ("COGS_ExVAT", "COGS_VAT", "COGS_Total"):
        new_col = f"{col}_new"
        if new_col in df_level1.columns:
            df_level1[col] = df_level1[new_col].where(df_level1[new_col].notna(), df_level1.get(col, ""))
            df_level1.drop(columns=[new_col], inplace=True, errors="ignore")

    # Recompute margin if present.
    if "Margin_ExVAT" in df_level1.columns or "Margin_Pct" in df_level1.columns:
        def _col(name: str) -> pd.Series:
            if name in df_level1.columns:
                return df_level1[name].apply(_to_num)
            return pd.Series([0.0] * len(df_level1))

        rev_ex = _col("Price_ExVAT") + _col("Shipping_ExVAT") + _col("Gift_ExVAT") + _col("Promotion_ExVAT")
        fee_ex = _col("FBA_Fee_ExVAT").abs() + _col("Commission_ExVAT").abs() + _col("Digital_Fee_ExVAT").abs()
        cogs_ex = _col("COGS_ExVAT").abs()
        margin_val = (rev_ex - fee_ex - cogs_ex).round(2)
        if "Margin_ExVAT" in df_level1.columns:
            df_level1["Margin_ExVAT"] = margin_val.astype(object).where(margin_val != 0, df_level1.get("Margin_ExVAT", ""))
        if "Margin_Pct" in df_level1.columns:
            with pd.option_context("mode.use_inf_as_na", True):
                margin_pct = (margin_val / rev_ex.replace(0, pd.NA) * 100.0).round(2)
            df_level1["Margin_Pct"] = margin_pct.astype(object).where(margin_pct.notna(), df_level1.get("Margin_Pct", ""))

    df_level1.to_csv(LEVEL1_PATH, index=False)
    if client is not None:
        try:
            level1_sheet = client.open_by_key(LEVEL1_SHEET_ID)
            level1_ws = level1_sheet.worksheet(LEVEL1_TAB)
            write_ws(level1_ws, df_level1)
        except Exception:
            pass


def main() -> None:
    repo_root = os.path.dirname(os.path.dirname(__file__))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    if not ORDER_MASTER_PATH.exists():
        raise RuntimeError("Missing out/order_master.csv")

    client = None
    sheet = None
    token_ws = None
    alloc_ws = None
    log_ws = None
    data_mode = "local_fallback"
    sheet_rows = -1
    if not SKIP_TOKEN_SHEETS:
        try:
            if gspread is None:
                raise RuntimeError("gspread_unavailable")
            try:
                from scripts.flows.A.A003_run_inventory_to_sheet import get_gspread_client
            except ModuleNotFoundError:
                from flows.A.A003_run_inventory_to_sheet import get_gspread_client

            client = get_gspread_client()
            sheet = client.open_by_key(TOKENS_SHEET_ID)
            token_ws = sheet.worksheet(TOKENS_TAB)
            alloc_ws = sheet.worksheet(ALLOC_TAB)
            log_ws = get_or_create_ws(sheet, LOG_TAB)
            token_df = load_sheet_df(token_ws)
            alloc_df = load_sheet_df(alloc_ws)
            data_mode = "sheet_sync"
            sheet_rows = len(token_df)
        except Exception as exc:
            token_df, alloc_df = _load_local_token_and_alloc()
            local_rows = len(token_df)
            if local_rows <= 0:
                _append_sync_status(
                    step="B007_allocate_tokens_live",
                    status="hard_fail",
                    severity="fail",
                    mode="sheet_required",
                    note=f"sheet_unavailable_no_local={type(exc).__name__}:{exc}",
                )
                raise RuntimeError(f"B007 sheet unavailable and no local token ledger: {type(exc).__name__}: {exc}")
            _append_sync_status(
                step="B007_allocate_tokens_live",
                status="degraded_local",
                severity="warn",
                mode="local_fallback",
                note=f"sheet_unavailable={type(exc).__name__}:{exc}",
                local_rows=local_rows,
            )
    else:
        token_df, alloc_df = _load_local_token_and_alloc()
        data_mode = "local_fallback"

    if alloc_df is None:
        alloc_df = pd.DataFrame()

    if token_df.empty:
        _append_sync_status(
            step="B007_allocate_tokens_live",
            status="ok",
            severity="ok",
            mode=data_mode,
            note="token_ledger_empty_noop",
            local_rows=len(token_df),
            sheet_rows=sheet_rows,
        )
        print("Token_Ledger empty; nothing to allocate.")
        return

    required_token_cols = ["status", "received_date", "token_id", "seller_sku", "cost_per_unit", "currency"]
    missing_token_cols = [c for c in required_token_cols if c not in token_df.columns]
    if missing_token_cols:
        _append_sync_status(
            step="B007_allocate_tokens_live",
            status="hard_fail",
            severity="fail",
            mode=data_mode,
            note="missing_token_cols=" + ",".join(missing_token_cols),
            local_rows=len(token_df),
            sheet_rows=sheet_rows,
        )
        raise RuntimeError("Token_Ledger missing required columns: " + ",".join(missing_token_cols))

    token_df = token_df.copy()
    token_df["status"] = token_df["status"].fillna("")
    token_df["received_date_dt"] = token_df["received_date"].apply(parse_date)
    token_df["lot_rank_num"] = pd.to_numeric(token_df.get("lot_rank"), errors="coerce")
    token_df["sort_rank"] = token_df["lot_rank_num"]
    token_df.loc[token_df["sort_rank"].isna(), "sort_rank"] = token_df["received_date_dt"].apply(
        lambda dt: dt.timestamp() if pd.notna(dt) else 0
    )
    token_df["token_seq"] = range(len(token_df))

    # Load inventory snapshot to reserve newest tokens for stock.
    include_inbound_available = os.environ.get("TOKEN_AVAILABLE_INCLUDE_INBOUND", "0") == "1"
    inv_available_effective = {}
    if INVENTORY_SNAPSHOT_PATH.exists():
        inv = pd.read_csv(INVENTORY_SNAPSHOT_PATH)
        inv["seller_sku"] = inv["seller_sku"].astype(str)
        inv["available"] = inv["available"].fillna(0).astype(int)
        inv["reserved_transfers"] = inv["reserved_transfers"].fillna(0).astype(int)
        inv["reserved_processing"] = inv["reserved_processing"].fillna(0).astype(int)
        inv["inbound_shipped"] = inv["inbound_shipped"].fillna(0).astype(int)
        inv["inbound_receiving"] = inv["inbound_receiving"].fillna(0).astype(int)
        inbound_total = inv["inbound_shipped"] + inv["inbound_receiving"]
        inv["available_effective"] = (
            inv["available"]
            + inv["reserved_transfers"]
            + inv["reserved_processing"]
            + (inbound_total if include_inbound_available else 0)
        )
        inv_available_effective = dict(zip(inv["seller_sku"], inv["available_effective"]))

    alloc_counts = defaultdict(int)
    alloc_counts_by_sku = defaultdict(int)
    if not alloc_df.empty:
        for _, row in alloc_df.iterrows():
            order_id = row.get("order_id", "")
            sku = row.get("seller_sku", "")
            if order_id and sku:
                alloc_counts[(order_id, sku)] += 1
                alloc_counts_by_sku[sku] += 1

    order_df = pd.read_csv(ORDER_MASTER_PATH)
    order_df = order_df.copy()
    order_df["Order ID"] = order_df.get("Order ID", "").astype(str)
    order_df["SKU"] = order_df.get("SKU", "").astype(str)
    order_df["Date"] = order_df.get("Date", "").astype(str)
    order_df["Quantity Ordered"] = order_df.get("Quantity Ordered", "")
    order_df["qty_num"] = pd.to_numeric(order_df["Quantity Ordered"], errors="coerce")

    # Include orders held back for missing tokens so allocations can resolve the gap.
    missing_orders = _load_missing_token_orders()
    if not missing_orders.empty:
        missing_orders = missing_orders.copy()
        missing_orders["Order ID"] = missing_orders.get("Order ID", "").astype(str)
        missing_orders["SKU"] = missing_orders.get("SKU", "").astype(str)
        missing_orders["Date"] = missing_orders.get("Date", "").astype(str)
        missing_orders["Quantity Ordered"] = missing_orders.get("Quantity Ordered", "")
        missing_orders["qty_num"] = pd.to_numeric(missing_orders["Quantity Ordered"], errors="coerce")
        order_df = pd.concat([order_df, missing_orders], ignore_index=True)
        order_df = order_df.drop_duplicates(subset=["Order ID", "SKU"], keep="first")

    # Skip rows with missing required order context.
    skipped_rows = []
    blank_order = order_df["Order ID"].str.strip().eq("")
    blank_sku = order_df["SKU"].str.strip().eq("")
    blank_date = order_df["Date"].str.strip().eq("")
    missing_qty = order_df["qty_num"].isna()
    non_positive_qty = order_df["qty_num"].fillna(0).le(0)

    def _add_skip(mask, reason: str) -> None:
        if not mask.any():
            return
        subset = order_df.loc[mask, ["Order ID", "SKU", "Date", "Quantity Ordered"]].copy()
        subset["reason"] = reason
        skipped_rows.append(subset)

    _add_skip(blank_order, "blank_order_id")
    _add_skip(blank_sku, "blank_sku")
    _add_skip(blank_date, "blank_date")
    _add_skip(missing_qty, "missing_qty")
    _add_skip(non_positive_qty & ~missing_qty, "non_positive_qty")

    skip_mask = blank_order | blank_sku | blank_date | missing_qty | non_positive_qty
    order_df = order_df.loc[~skip_mask].copy()
    # Compute unallocated demand per SKU to avoid reserving stock against live orders.
    order_df["allocated_qty"] = order_df.apply(
        lambda r: alloc_counts.get((r["Order ID"], r["SKU"]), 0), axis=1
    )
    order_df["remaining_qty"] = (order_df["qty_num"] - order_df["allocated_qty"]).clip(lower=0)
    unallocated_by_sku = (
        order_df.groupby("SKU")["remaining_qty"].sum().to_dict()
        if not order_df.empty
        else {}
    )

    # Persist skip log (always write header for schema stability).
    if skipped_rows:
        skipped_df = pd.concat(skipped_rows, ignore_index=True)
    else:
        skipped_df = pd.DataFrame(columns=["Order ID", "SKU", "Date", "Quantity Ordered", "reason"])
    SKIPPED_PATH.parent.mkdir(parents=True, exist_ok=True)
    skipped_df.to_csv(SKIPPED_PATH, index=False)
    # Orders should receive NEWEST remaining tokens so newest costs remain with stock.
    order_df = order_df.sort_values(by=["Date", "Order ID"], ascending=[False, False])

    available_tokens = token_df[token_df["status"] == "available"]

    if available_tokens.empty:
        print("No available tokens to allocate.")
        return

    new_allocations = []
    log_rows = []
    updated_tokens = token_df.copy()
    shortage_by_sku = defaultdict(int)
    now_iso = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

    for sku, sku_tokens in available_tokens.groupby("seller_sku"):
        sku_orders = order_df[order_df["SKU"] == sku]
        if sku_orders.empty:
            continue
        # Reserve newest tokens for stock (keep newest with stock).
        target_available = int(inv_available_effective.get(sku, 0))
        # Reduce reserved stock by unallocated demand for this SKU.
        target_available = max(target_available - int(unallocated_by_sku.get(sku, 0)), 0)
        sku_tokens = sku_tokens.sort_values(
            by=["sort_rank", "token_seq", "token_id"],
            ascending=[False, False, False],
        )
        reserve_count = min(int(target_available), len(sku_tokens))
        # Always leave enough tokens to cover unallocated demand for this SKU.
        need_for_orders = int(unallocated_by_sku.get(sku, 0))
        reserve_cap = max(len(sku_tokens) - need_for_orders, 0)
        if reserve_count > reserve_cap:
            reserve_count = reserve_cap
        sku_tokens = sku_tokens.iloc[reserve_count:]
        remaining_capacity = len(sku_tokens)
        if remaining_capacity <= 0:
            continue
        # Allocate remaining tokens oldest-first (FIFO) to orders.
        sku_tokens = sku_tokens.sort_values(
            by=["sort_rank", "token_seq", "token_id"],
            ascending=[True, True, True],
        )
        token_iter = iter(sku_tokens.itertuples(index=False))
        remaining_available = len(sku_tokens)
        out_of_tokens = False

        for _, row in sku_orders.iterrows():
            if remaining_capacity <= 0:
                break
            order_id = row["Order ID"]
            order_date = row["Date"]
            qty = int(row["qty_num"])
            allocated = alloc_counts.get((order_id, sku), 0)
            remaining = qty - allocated
            if remaining <= 0:
                continue
            for _ in range(min(remaining, remaining_capacity)):
                try:
                    token = next(token_iter)
                except StopIteration:
                    # Aggregate shortage per SKU instead of logging per row.
                    shortage_by_sku[sku] += remaining_capacity
                    remaining_capacity = 0
                    out_of_tokens = True
                    break

                new_allocations.append(
                    {
                        "order_id": order_id,
                        "order_date": order_date,
                        "seller_sku": sku,
                        "quantity": 1,
                        "token_id": token.token_id,
                        "token_cost": token.cost_per_unit,
                        "currency": token.currency,
                        "allocation_date": now_iso,
                        "source_level": str(row.get("lvl", "")),
                        "notes": "live_allocation",
                    }
                )

                idx = updated_tokens.index[updated_tokens["token_id"] == token.token_id]
                updated_tokens.loc[idx, "status"] = "allocated"
                updated_tokens.loc[idx, "allocated_order_id"] = order_id
                updated_tokens.loc[idx, "allocated_date"] = order_date

                remaining_available -= 1
                remaining_capacity -= 1
                log_rows.append(
                    [
                        now_iso,
                        order_id,
                        order_date,
                        sku,
                        token.token_id,
                        token.cost_per_unit,
                        token.currency,
                        remaining_available,
                        "allocated",
                    ]
                )
            if out_of_tokens:
                break

    try:
        if shortage_by_sku:
            pending_counts = (
                token_df[token_df["status"] == "research_pending"]
                .groupby("seller_sku")
                .size()
                .to_dict()
            )
            adjusted = {}
            for sku, count in shortage_by_sku.items():
                pending = int(pending_counts.get(sku, 0))
                adjusted_count = max(int(count) - pending, 0)
                if adjusted_count > 0:
                    adjusted[sku] = adjusted_count

            if adjusted:
                summary = ", ".join(
                    [f"{sku} x {count}" for sku, count in sorted(adjusted.items())]
                )
                print(f"Short by tokens (SKU x missing_qty): {summary}")
                out_rows = [
                    {
                        "timestamp": now_iso,
                        "seller_sku": sku,
                        "missing_qty": int(count),
                    }
                    for sku, count in sorted(adjusted.items())
                ]
                write_csv_with_compat(
                    pd.DataFrame(out_rows),
                    path_or_rel="token_shortages_by_sku.csv",
                    default_system="B",
                    index=False,
                    mirror_legacy=True,
                )
            else:
                write_csv_with_compat(
                    pd.DataFrame(columns=["timestamp", "seller_sku", "missing_qty"]),
                    path_or_rel="token_shortages_by_sku.csv",
                    default_system="B",
                    index=False,
                    mirror_legacy=True,
                )
        else:
            # Write empty file to avoid stale shortage alerts.
            write_csv_with_compat(
                pd.DataFrame(columns=["timestamp", "seller_sku", "missing_qty"]),
                path_or_rel="token_shortages_by_sku.csv",
                default_system="B",
                index=False,
                mirror_legacy=True,
            )
    except Exception as exc:
        print(f"[B007] WARNING: failed to write token_shortages_by_sku.csv: {exc}")

    if data_mode == "sheet_sync" and not SKIP_TOKEN_SHEETS and log_ws is not None:
        if log_ws.get_all_values() == []:
            log_ws.append_row(
                [
                    "timestamp",
                    "order_id",
                    "order_date",
                    "seller_sku",
                    "token_id",
                    "token_cost",
                    "currency",
                    "tokens_remaining",
                    "status",
                ],
                value_input_option="RAW",
            )

    if not new_allocations:
        print("No new allocations needed.")
        # Persist current allocations so downstream COGS uses the full set.
        if alloc_df is not None and not alloc_df.empty:
            alloc_out = alloc_df.copy()
        else:
            alloc_out = pd.DataFrame(
                columns=[
                    "order_id",
                    "order_date",
                    "seller_sku",
                    "quantity",
                    "token_id",
                    "token_cost",
                    "currency",
                    "allocation_date",
                    "source_level",
                    "notes",
                ]
            )
        write_csv_with_compat(
            alloc_out,
            path_or_rel="token_allocations_live.csv",
            default_system="B",
            index=False,
            mirror_legacy=True,
        )
        # Still sync Level 1 COGS from existing allocations.
        token_out = updated_tokens.drop(columns=["received_date_dt", "token_seq"], errors="ignore")
        sync_level1_cogs(token_out, client)
        _append_sync_status(
            step="B007_allocate_tokens_live",
            status="ok",
            severity="ok",
            mode=data_mode,
            note="no_new_allocations",
            local_rows=len(token_out),
            sheet_rows=sheet_rows,
        )
        return

    new_alloc_df = pd.DataFrame(new_allocations)
    expected_cols = list(new_alloc_df.columns)
    if alloc_df is None or alloc_df.empty:
        combined_alloc = new_alloc_df
    else:
        alloc_df = alloc_df.copy()
        for col in expected_cols:
            if col not in alloc_df.columns:
                alloc_df[col] = ""
        alloc_df = alloc_df[expected_cols]
        combined_alloc = pd.concat([alloc_df, new_alloc_df], ignore_index=True)
        if "token_id" in combined_alloc.columns:
            combined_alloc = combined_alloc.drop_duplicates(subset=["token_id"], keep="first")
    write_csv_with_compat(
        combined_alloc,
        path_or_rel="token_allocations_live.csv",
        default_system="B",
        index=False,
        mirror_legacy=True,
    )
    write_csv_with_compat(
        updated_tokens.drop(columns=["received_date_dt", "token_seq"], errors="ignore"),
        path_or_rel="token_ledger_live.csv",
        default_system="B",
        index=False,
        mirror_legacy=True,
    )

    token_out = updated_tokens.drop(columns=["received_date_dt", "token_seq"], errors="ignore")
    if data_mode == "sheet_sync" and not SKIP_TOKEN_SHEETS and alloc_ws is not None and token_ws is not None:
        alloc_ws.append_rows(new_alloc_df.values.tolist(), value_input_option="RAW")

        rows = [token_out.columns.tolist()] + token_out.astype(object).where(pd.notnull(token_out), "").values.tolist()
        token_ws.clear()
        token_ws.update(rows, value_input_option="RAW")

    # Sync Level 1 COGS from allocated tokens so Level_1_Immediate shows real token costs.
    sync_level1_cogs(token_out, client)

    if log_rows and data_mode == "sheet_sync" and not SKIP_TOKEN_SHEETS and log_ws is not None:
        try:
            log_ws.append_rows(log_rows, value_input_option="RAW")
        except Exception as exc:
            # Sheet can hit the 10M cell limit; don't fail allocation because of logging
            print(f"[B007] WARNING: log append failed: {exc}. Logs written locally only.")

    _append_sync_status(
        step="B007_allocate_tokens_live",
        status="ok",
        severity="ok",
        mode=data_mode,
        note="allocation_complete",
        local_rows=len(token_out),
        sheet_rows=sheet_rows,
    )
    print(f"Allocated {len(new_alloc_df)} units across {new_alloc_df['seller_sku'].nunique()} SKUs.")


if __name__ == "__main__":
    main()


