from __future__ import annotations

import argparse
import json
import os
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.h.h_floor_truth import has_blocking_reason_codes, load_h_floor_context, resolve_h_floor_inputs
from scripts.h.h_suppression_truth import resolve_unified_truth

OUT = ROOT / "out"
DATA = ROOT / "data"
DEFAULT_SCOPE_PATH = OUT / "phase1_sku_scope.csv"
DEFAULT_RUNTIME_PATH = OUT / "phase1_runtime_floor_snapshot_latest.csv"
DEFAULT_FLOOR_TABLE_PATH = OUT / "phase1_floor_table_latest.csv"
DEFAULT_DAILY_INTEL_PATH = DATA / "sku_daily_intel.csv"
DEFAULT_OFFER_SNAPSHOT_FACTS_PATH = DATA / "offer_snapshot_facts.csv"
DEFAULT_PRODUCT_DB_PATH = OUT / "product_db_preview.csv"
DEFAULT_INVENTORY_SUMMARIES_PATH = OUT / "inventory_summaries.csv"
DEFAULT_ORDER_MASTER_PATH = OUT / "order_master.csv"
DEFAULT_SKU_SCAN_STATE_PATH = OUT / "phase1_sku_scan_state.json"
DEFAULT_EXECUTION_LOG_PATH = DATA / "execution_log.csv"
DEFAULT_SHEET_ID = "18flepYvH11078sOfEu9sBUmeF4KAl8T_iDKhxDZNPaY"
DEFAULT_CREDS = ROOT / "secrets" / "sellerone-2-0d3642b951a0.json"
VIEW_COLUMN_COUNT = 25
HIDDEN_LAST_SCAN_COLUMN_LETTER = "Y"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _today_utc_str() -> str:
    return _utc_now().strftime("%Y-%m-%d")


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        text = str(value).strip()
        if text == "":
            return None
        out = float(text)
        if not math.isfinite(out):
            return None
        return out
    except Exception:
        return None


def _safe_int_flag(value: Any) -> int:
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return 1
    return 0


def _authoritative_write_enabled(row: pd.Series) -> bool:
    write_effective = _safe_int_flag(row.get("write_effective", "0"))
    writer_mode = str(row.get("writer_mode", "")).strip().upper()
    return write_effective == 1 or writer_mode == "CODEX_H"


def _string_flag(value: bool) -> str:
    return "1" if value else "0"


def _sale_exvat_from_gross(gross_price: float, vat_rate: float, vat_registered: bool) -> float:
    price = max(float(gross_price or 0.0), 0.0)
    rate = max(float(vat_rate or 0.0), 0.0)
    if not vat_registered:
        return price
    denom = 1.0 + rate
    if denom <= 0:
        return price
    return price / denom


def _roi_on_cogs_pct_for_price(sku: str, gross_price: float | None, floor_ctx, vat_registered: bool) -> float | None:
    if gross_price is None or gross_price <= 0:
        return None
    try:
        inputs = resolve_h_floor_inputs(
            sku,
            float(gross_price),
            context=floor_ctx,
            allow_candidate_fallback=False,
        )
    except Exception:
        return None
    if has_blocking_reason_codes(inputs.reason_codes):
        return None
    cogs_ex = float(inputs.cogs_exvat_gbp)
    if cogs_ex <= 0:
        return None
    sale_ex = _sale_exvat_from_gross(float(gross_price), float(inputs.vat_rate), vat_registered)
    # Floor engine uses margin_exvat as target profit (10% of COG), not a cost line.
    break_even_cost_ex = (
        float(inputs.cogs_exvat_gbp)
        + float(inputs.fba_exvat_gbp)
        + float(inputs.referral_amount_gbp)
        + float(inputs.digital_fee_exvat_gbp)
    )
    profit_ex = sale_ex - break_even_cost_ex
    return (profit_ex / cogs_ex) * 100.0


def _cogs_available_for_sku(sku: str, floor_ctx) -> bool:
    try:
        # Use a safe positive candidate that avoids low-price floor blocks.
        inputs = resolve_h_floor_inputs(
            sku,
            999.0,
            context=floor_ctx,
            allow_candidate_fallback=False,
        )
    except Exception:
        return False
    if has_blocking_reason_codes(inputs.reason_codes):
        return False
    return float(inputs.cogs_exvat_gbp) > 0.0


def _parse_iso_utc(value: str) -> datetime | None:
    text = str(value or "").strip()
    if text == "":
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _sheet_datetime_text(value: str) -> str:
    dt = _parse_iso_utc(value)
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _latest_file(pattern: str) -> Path | None:
    files = sorted(OUT.glob(pattern))
    if not files:
        return None
    return files[-1]


def _latest_inventory_path() -> Path | None:
    latest_snapshot = _latest_file("inventory_snapshot_*.csv")
    if latest_snapshot is not None:
        return latest_snapshot
    if DEFAULT_INVENTORY_SUMMARIES_PATH.exists():
        return DEFAULT_INVENTORY_SUMMARIES_PATH
    return None


def _load_csv(path: Path | None) -> pd.DataFrame:
    if path is None or not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _load_last_scan_utc_by_sku(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    raw = payload.get("last_scan_utc", {})
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for sku, ts in raw.items():
        sku_key = str(sku or "").strip()
        ts_text = str(ts or "").strip()
        if sku_key == "" or ts_text == "":
            continue
        if _parse_iso_utc(ts_text) is None:
            continue
        out[sku_key] = ts_text
    return out


def _latest_execution_probe_df(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["sku", "probe_event_ts_utc", "probe_state", "probe_reason_codes_json"])
    df = _load_csv(path)
    if df.empty or "sku" not in df.columns:
        return pd.DataFrame(columns=["sku", "probe_event_ts_utc", "probe_state", "probe_reason_codes_json"])
    work = df.copy()
    work["sku"] = work.get("sku", "").astype(str).str.strip()
    work["event_ts_utc"] = work.get("event_ts_utc", "").astype(str).str.strip()
    work = work.loc[work["sku"].ne("") & work["event_ts_utc"].ne("")].copy()
    if work.empty:
        return pd.DataFrame(columns=["sku", "probe_event_ts_utc", "probe_state", "probe_reason_codes_json"])
    work["event_dt"] = pd.to_datetime(work["event_ts_utc"], errors="coerce", utc=True)
    work = work.loc[work["event_dt"].notna()].copy()
    if work.empty:
        return pd.DataFrame(columns=["sku", "probe_event_ts_utc", "probe_state", "probe_reason_codes_json"])
    work = work.sort_values(["sku", "event_dt"], ascending=[True, False]).drop_duplicates(subset=["sku"], keep="first")
    out = pd.DataFrame(
        {
            "sku": work["sku"].astype(str),
            "probe_event_ts_utc": work["event_ts_utc"].astype(str),
            "probe_state": work.get("state", "").astype(str),
            "probe_reason_codes_json": work.get("reason_codes_json", "").astype(str),
        }
    )
    return out


def _build_product_stock_df(product_df: pd.DataFrame) -> pd.DataFrame:
    if product_df.empty:
        return pd.DataFrame(columns=["sku", "stock_qty"])
    sku_col = "seller_sku" if "seller_sku" in product_df.columns else ("sku" if "sku" in product_df.columns else "")
    if sku_col == "":
        return pd.DataFrame(columns=["sku", "stock_qty"])

    rows: list[dict[str, Any]] = []
    for _, row in product_df.iterrows():
        sku = str(row.get(sku_col, "")).strip()
        if sku == "":
            continue
        stock_available = _safe_float(row.get("stock_available", ""))
        stock_total = _safe_float(row.get("stock_total", ""))
        stock_qty = stock_available if stock_available is not None else stock_total
        rows.append({"sku": sku, "stock_qty": stock_qty})

    out = pd.DataFrame.from_records(rows)
    if out.empty:
        return pd.DataFrame(columns=["sku", "stock_qty"])
    out = out.sort_values(["sku"]).drop_duplicates(subset=["sku"], keep="first")
    return out


def _build_inventory_stock_df(inventory_df: pd.DataFrame) -> pd.DataFrame:
    if inventory_df.empty:
        return pd.DataFrame(columns=["sku", "stock_qty"])
    sku_col = "sku" if "sku" in inventory_df.columns else ("seller_sku" if "seller_sku" in inventory_df.columns else "")
    if sku_col == "":
        return pd.DataFrame(columns=["sku", "stock_qty"])

    rows: list[dict[str, Any]] = []
    for _, row in inventory_df.iterrows():
        sku = str(row.get(sku_col, "")).strip()
        if sku == "":
            continue
        available = _safe_float(row.get("available", ""))
        total_qty = _safe_float(row.get("total_quantity", ""))
        # Some inventory exports leave `available` at 0 even when on-hand stock
        # exists in `total_quantity`. Prefer real available stock when positive,
        # otherwise fall back to total quantity so the dashboard does not show a
        # false zero.
        stock_qty = available if available is not None else total_qty
        if (stock_qty is None or stock_qty <= 0) and total_qty is not None and total_qty > 0:
            stock_qty = total_qty
        rows.append({"sku": sku, "stock_qty": stock_qty})

    out = pd.DataFrame.from_records(rows)
    if out.empty:
        return pd.DataFrame(columns=["sku", "stock_qty"])
    out = out.sort_values(["sku"]).drop_duplicates(subset=["sku"], keep="first")
    return out


def _build_inventory_activity_df(inventory_summaries_df: pd.DataFrame) -> pd.DataFrame:
    if inventory_summaries_df.empty:
        return pd.DataFrame(columns=["sku", "available_stock_qty", "inbound_total_qty"])
    sku_col = "seller_sku" if "seller_sku" in inventory_summaries_df.columns else ("sku" if "sku" in inventory_summaries_df.columns else "")
    if sku_col == "":
        return pd.DataFrame(columns=["sku", "available_stock_qty", "inbound_total_qty"])

    rows: list[dict[str, Any]] = []
    for _, row in inventory_summaries_df.iterrows():
        sku = str(row.get(sku_col, "")).strip()
        if sku == "":
            continue
        available = _safe_float(row.get("available", ""))
        total_qty = _safe_float(row.get("total_quantity", ""))
        in_working = _safe_float(row.get("inbound_working", "")) or 0.0
        in_shipped = _safe_float(row.get("inbound_shipped", "")) or 0.0
        in_receiving = _safe_float(row.get("inbound_receiving", "")) or 0.0
        inbound_total = in_working + in_shipped + in_receiving
        if (available is None or available <= 0) and total_qty is not None and total_qty > 0:
            available = total_qty
        rows.append(
            {
                "sku": sku,
                "available_stock_qty": available,
                "inbound_total_qty": inbound_total,
            }
        )

    out = pd.DataFrame.from_records(rows)
    if out.empty:
        return pd.DataFrame(columns=["sku", "available_stock_qty", "inbound_total_qty"])
    out = out.sort_values(["sku"]).drop_duplicates(subset=["sku"], keep="first")
    return out


def _build_sales_velocity_df(order_df: pd.DataFrame, now_utc: datetime) -> pd.DataFrame:
    if order_df.empty:
        return pd.DataFrame(columns=["sku", "sales_units_30d", "sales_per_day_30d", "sales_units_today"])
    if "SKU" not in order_df.columns or "Quantity Ordered" not in order_df.columns or "Date" not in order_df.columns:
        return pd.DataFrame(columns=["sku", "sales_units_30d", "sales_per_day_30d", "sales_units_today"])

    work = order_df.copy()
    work["sku"] = work["SKU"].astype(str).str.strip()
    work = work.loc[work["sku"].ne("")].copy()
    if work.empty:
        return pd.DataFrame(columns=["sku", "sales_units_30d", "sales_per_day_30d", "sales_units_today"])

    work["qty"] = pd.to_numeric(work["Quantity Ordered"], errors="coerce").fillna(0.0)
    # order_master Date is ISO-8601 UTC (for example 2026-02-20T12:57:08Z).
    # dayfirst=True breaks this and can zero-out today's sales.
    work["date_dt"] = pd.to_datetime(work["Date"], errors="coerce", utc=True)
    today_start = datetime(now_utc.year, now_utc.month, now_utc.day, tzinfo=timezone.utc)
    today_end = today_start + pd.Timedelta(days=1)
    scoped_today = work.loc[work["date_dt"].notna() & work["date_dt"].ge(today_start) & work["date_dt"].lt(today_end)].copy()
    sales_today = scoped_today.groupby("sku", as_index=False)["qty"].sum() if not scoped_today.empty else pd.DataFrame(columns=["sku", "qty"])
    if not sales_today.empty:
        sales_today["sales_units_today"] = sales_today["qty"].round(2)
        sales_today = sales_today.drop(columns=["qty"])

    cutoff = now_utc - pd.Timedelta(days=30)
    scoped = work.loc[work["date_dt"].notna() & work["date_dt"].ge(cutoff)].copy()
    if scoped.empty:
        base = pd.DataFrame(columns=["sku", "sales_units_30d", "sales_per_day_30d"])
        if not sales_today.empty:
            out = base.merge(sales_today, on="sku", how="outer")
            out["sales_units_today"] = pd.to_numeric(out.get("sales_units_today", 0), errors="coerce").fillna(0.0).round(2)
            return out
        return pd.DataFrame(columns=["sku", "sales_units_30d", "sales_per_day_30d", "sales_units_today"])

    grouped = scoped.groupby("sku", as_index=False)["qty"].sum()
    grouped["sales_units_30d"] = grouped["qty"].round(2)
    grouped["sales_per_day_30d"] = (grouped["sales_units_30d"] / 30.0).round(3)
    grouped = grouped.drop(columns=["qty"])
    if not sales_today.empty:
        grouped = grouped.merge(sales_today, on="sku", how="outer")
    else:
        grouped["sales_units_today"] = 0.0
    grouped["sales_units_today"] = pd.to_numeric(grouped.get("sales_units_today", 0), errors="coerce").fillna(0.0).round(2)
    return grouped


def _latest_daily_intel_by_sku(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "sku" not in df.columns:
        return pd.DataFrame(columns=["sku"])
    work = df.copy()
    work["sku"] = work["sku"].astype(str).str.strip()
    if "date_utc" in work.columns:
        work = work.sort_values(["sku", "date_utc"], ascending=[True, False])
    return work.drop_duplicates(subset=["sku"], keep="first")


def _latest_rival_prices_by_sku(offers_df: pd.DataFrame) -> dict[str, float]:
    if offers_df.empty:
        return {}
    latest_ts = offers_df.groupby("sku")["snapshot_dt"].transform("max")
    latest_rows = offers_df.loc[offers_df["snapshot_dt"].eq(latest_ts)].copy()
    latest_rows = latest_rows.sort_values(["sku", "landed_price_gbp"], ascending=[True, True])
    latest_rows = latest_rows.drop_duplicates(subset=["sku"], keep="first")
    out: dict[str, float] = {}
    for _, row in latest_rows.iterrows():
        sku = str(row.get("sku", "")).strip()
        landed = _safe_float(row.get("landed_price_gbp", ""))
        if sku != "" and landed is not None and landed > 0:
            out[sku] = float(landed)
    return out


def _build_rival_fallback_maps(runtime_df: pd.DataFrame, now_utc: datetime) -> tuple[dict[str, float], dict[str, float]]:
    if not DEFAULT_OFFER_SNAPSHOT_FACTS_PATH.exists():
        return {}, {}
    offers_df = _load_csv(DEFAULT_OFFER_SNAPSHOT_FACTS_PATH)
    if offers_df.empty:
        return {}, {}
    offers_df["sku"] = offers_df.get("sku", "").astype(str).str.strip()
    offers_df["landed_price_gbp"] = pd.to_numeric(offers_df.get("landed_price_gbp", ""), errors="coerce")
    offers_df["is_our_offer_num"] = pd.to_numeric(offers_df.get("is_our_offer", "0"), errors="coerce").fillna(0)
    offers_df["snapshot_dt"] = pd.to_datetime(offers_df.get("snapshot_ts_utc", ""), errors="coerce", utc=True)
    offers_df = offers_df.loc[
        offers_df["sku"].ne("")
        & offers_df["snapshot_dt"].notna()
        & offers_df["landed_price_gbp"].notna()
        & offers_df["landed_price_gbp"].gt(0)
        & offers_df["is_our_offer_num"].ne(1)
    ].copy()
    if offers_df.empty:
        return {}, {}

    run_times: list[datetime] = []
    if not runtime_df.empty:
        for col in ["snapshot_utc", "execution_event_ts_utc", "trace_asof_utc"]:
            if col not in runtime_df.columns:
                continue
            parsed = pd.to_datetime(runtime_df[col], errors="coerce", utc=True)
            run_times.extend([ts.to_pydatetime() for ts in parsed.dropna().tolist()])
    run_window_map: dict[str, float] = {}
    if run_times:
        run_start = min(run_times) - pd.Timedelta(minutes=30)
        run_end = max(run_times) + pd.Timedelta(minutes=30)
        in_window = offers_df.loc[offers_df["snapshot_dt"].ge(run_start) & offers_df["snapshot_dt"].le(run_end)].copy()
        run_window_map = _latest_rival_prices_by_sku(in_window)

    cutoff_24h = now_utc - pd.Timedelta(hours=24)
    within_24h = offers_df.loc[offers_df["snapshot_dt"].ge(cutoff_24h)].copy()
    last_24h_map = _latest_rival_prices_by_sku(within_24h)
    return run_window_map, last_24h_map


def _build_listing_derived(listing_df: pd.DataFrame) -> pd.DataFrame:
    if listing_df.empty or "sku" not in listing_df.columns:
        return pd.DataFrame(columns=["sku", "listing_asof_ts_utc", "current_price_gbp", "next_comp_gbp", "has_buy_box"])

    rows: list[dict[str, Any]] = []
    for _, row in listing_df.iterrows():
        sku = str(row.get("sku", "")).strip()
        if sku == "":
            continue
        our_price = _safe_float(row.get("our_price", ""))
        low_fba = _safe_float(row.get("lowest_fba_price", ""))
        low_fbm = _safe_float(row.get("lowest_fbm_price", ""))
        buy_box = _safe_float(row.get("buy_box_price", ""))
        buy_box_present = _safe_int_flag(row.get("buy_box_present_flag", "0")) == 1

        comp_candidates = [x for x in [low_fba, low_fbm] if x is not None and x > 0]
        next_comp = min(comp_candidates) if comp_candidates else None

        has_buy_box = False
        if buy_box_present and buy_box is not None and our_price is not None:
            has_buy_box = abs(our_price - buy_box) <= 0.001

        rows.append(
            {
                "sku": sku,
                "listing_asof_ts_utc": str(row.get("timestamp_utc", "")).strip(),
                "current_price_gbp": our_price,
                "next_comp_gbp": next_comp,
                "has_buy_box": 1 if has_buy_box else 0,
            }
        )

    out = pd.DataFrame.from_records(rows)
    if out.empty:
        return pd.DataFrame(columns=["sku", "listing_asof_ts_utc", "current_price_gbp", "next_comp_gbp", "has_buy_box"])
    out = out.sort_values(["sku", "listing_asof_ts_utc"], ascending=[True, False])
    return out.drop_duplicates(subset=["sku"], keep="first")


def _build_combined_df(
    scope_df: pd.DataFrame,
    runtime_df: pd.DataFrame,
    floor_table_df: pd.DataFrame,
    daily_intel_df: pd.DataFrame,
    listing_df: pd.DataFrame,
    product_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
    order_master_df: pd.DataFrame,
    last_scan_utc_by_sku: dict[str, str] | None = None,
) -> pd.DataFrame:
    scope = scope_df.copy()
    scope["sku"] = scope.get("sku", "").astype(str).str.strip()
    scope["asin"] = scope.get("asin", "").astype(str).str.strip()

    runtime = runtime_df.copy()
    if not runtime.empty:
        runtime["sku"] = runtime.get("sku", "").astype(str).str.strip()
        runtime = runtime.sort_values(["sku", "snapshot_utc"], ascending=[True, False]) if "snapshot_utc" in runtime.columns else runtime
        runtime = runtime.drop_duplicates(subset=["sku"], keep="first")

    floor_table = floor_table_df.copy()
    if not floor_table.empty:
        floor_table["sku"] = floor_table.get("sku", "").astype(str).str.strip()
        keep_floor = [c for c in ["sku", "floor_gbp", "floor_reason_code"] if c in floor_table.columns]
        floor_table = floor_table[keep_floor].drop_duplicates(subset=["sku"], keep="first")

    daily_latest = _latest_daily_intel_by_sku(daily_intel_df)
    if not daily_latest.empty:
        daily_latest = daily_latest.rename(
            columns={
                "cpt_gbp": "cpt_gbp",
                "cpt_status": "cpt_status",
                "ceiling_rule_value_gbp": "ceiling_rule_value_gbp",
            }
        )

    listing_derived = _build_listing_derived(listing_df)
    latest_probe = _latest_execution_probe_df(DEFAULT_EXECUTION_LOG_PATH)
    product_stock = _build_product_stock_df(product_df)
    inventory_stock = _build_inventory_stock_df(inventory_df)
    inventory_activity = _build_inventory_activity_df(inventory_df)
    sales_velocity = _build_sales_velocity_df(order_master_df, _utc_now())
    now_utc = _utc_now()
    run_window_rival_map, recent_rival_map = _build_rival_fallback_maps(runtime, now_utc)
    floor_ctx = load_h_floor_context()
    vat_registered = bool(floor_ctx.vat_policy.get("vat_registered", True))

    combined = scope[
        [
            "sku",
            "asin",
            "asof_utc",
            "sale_status",
            "merchant_status",
            "in_stock_flag",
            "writer_mode",
            "write_effective",
            "parked_flag",
            "park_reason_codes",
        ]
    ].copy()
    if not runtime.empty:
        keep_runtime = [
            "sku",
            "snapshot_utc",
            "trace_asof_utc",
            "execution_event_ts_utc",
            "execution_state",
            "execution_write_status",
            "execution_write_error",
            "execution_old_price_gbp",
            "execution_new_price_gbp",
            "execution_hard_floor_gbp",
            "execution_final_ceiling_landed_gbp",
            "execution_binding_ceiling_type",
            "execution_reason_codes_json",
            "suppression_last_event_ts_utc",
            "suppression_buy_box_state",
            "suppression_strategy_state",
            "suppression_write_status",
            "suppression_target_price_gbp",
            "suppression_threshold_upper_bound_gbp",
            "suppression_ceiling_landed_temp",
            "suppression_ceiling_expiry_utc",
            "suppression_active_flag",
            "suppression_resolved_flag",
            "observed_our_price_gbp",
            "observed_our_price_ts_utc",
            "unified_buy_box_state",
            "unified_strategy_state",
            "unified_writer_outcome",
            "write_attempted_flag",
            "write_applied_flag",
            "true_binding_ceiling_gbp",
            "true_binding_ceiling_type",
            "truth_status",
            "trace_floor_total_gbp",
        ]
        keep_runtime = [c for c in keep_runtime if c in runtime.columns]
        combined = combined.merge(runtime[keep_runtime], on="sku", how="left")
    if not floor_table.empty:
        floor_table = floor_table.rename(
            columns={
                "floor_gbp": "floor_table_gbp",
                "floor_reason_code": "floor_table_reason_code",
            }
        )
        combined = combined.merge(floor_table, on="sku", how="left")

    if not daily_latest.empty:
        keep_daily = [
            c
            for c in [
                "sku",
                "cpt_gbp",
                "cpt_status",
                "ceiling_rule_value_gbp",
                "cpt_last_refresh_utc",
                "foep_last_refresh_utc",
            ]
            if c in daily_latest.columns
        ]
        combined = combined.merge(daily_latest[keep_daily], on="sku", how="left")

    if not listing_derived.empty:
        combined = combined.merge(listing_derived, on="sku", how="left")
    if not latest_probe.empty:
        combined = combined.merge(latest_probe, on="sku", how="left")
    if not inventory_stock.empty:
        combined = combined.merge(inventory_stock, on="sku", how="left")
    if not inventory_activity.empty:
        combined = combined.merge(inventory_activity, on="sku", how="left")
    if not product_stock.empty:
        product_stock = product_stock.rename(columns={"stock_qty": "stock_qty_product_db"})
        combined = combined.merge(product_stock, on="sku", how="left")
        if "stock_qty" not in combined.columns:
            combined["stock_qty"] = combined.get("stock_qty_product_db", "")
        else:
            left = pd.to_numeric(combined.get("stock_qty", ""), errors="coerce")
            right = pd.to_numeric(combined.get("stock_qty_product_db", ""), errors="coerce")
            combined["stock_qty"] = left.where(left.notna(), right)
    if not sales_velocity.empty:
        combined = combined.merge(sales_velocity, on="sku", how="left")
    if "sales_units_today" in combined.columns:
        combined["sales_units_today"] = pd.to_numeric(combined["sales_units_today"], errors="coerce").fillna(0.0).round(2)

    last_scan_values: list[str] = []
    minutes_values: list[float | str] = []
    floor_values: list[float | str] = []
    floor_display_values: list[float | str] = []
    floor_reason_values: list[str] = []
    ceiling_values: list[float | str] = []
    next_comp_values: list[float | str] = []
    stock_values: list[int] = []
    actionable_values: list[int] = []
    buy_box_values: list[int] = []
    can_fight_values: list[int] = []
    floor_gt_ceiling_values: list[int] = []
    automation_status_values: list[str] = []
    capability_status_values: list[str] = []
    truth_buy_box_values: list[str] = []
    truth_state_values: list[str] = []
    truth_writer_outcome_values: list[str] = []
    truth_ceiling_type_values: list[str] = []
    truth_model_ceiling_values: list[float | str] = []
    roi_floor_values: list[float | str] = []
    roi_cpt_values: list[float | str] = []
    roi_our_values: list[float | str] = []
    roi_next_values: list[float | str] = []
    roi_ceiling_values: list[float | str] = []
    sales_units_30d_values: list[float | str] = []
    sales_per_day_values: list[float | str] = []
    days_of_stock_values: list[float | str] = []
    compet_reason_values: list[str] = []
    compet_missing_initial_values: list[int] = []
    compet_fallback_added_values: list[int] = []
    compet_no_rival_data_values: list[int] = []
    cost_missing_values: list[int] = []
    ceiling_missing_values: list[int] = []
    publish_reason_codes_values: list[str] = []
    probe_values: list[str] = []
    sort_scores: list[float] = []
    cogs_available_cache: dict[str, bool] = {}

    for _, row in combined.iterrows():
        sku_key = str(row.get("sku", "")).strip()
        last_scan_ts = ""
        if last_scan_utc_by_sku:
            last_scan_ts = str(last_scan_utc_by_sku.get(sku_key, "")).strip()
        last_scan_values.append(last_scan_ts)

        dt = _parse_iso_utc(last_scan_ts)
        if dt is None:
            age_minutes = ""
            age_for_score = 9999.0
        else:
            age_for_score = max((now_utc - dt).total_seconds() / 60.0, 0.0)
            age_minutes = round(age_for_score, 2)
        minutes_values.append(age_minutes)

        floor_reason_code = str(row.get("floor_table_reason_code", "")).strip()
        floor = _safe_float(row.get("floor_table_gbp", ""))
        if floor is None:
            floor = _safe_float(row.get("execution_hard_floor_gbp", ""))
        if floor is None:
            floor = _safe_float(row.get("trace_floor_total_gbp", ""))
        floor_values.append("" if floor is None else round(floor, 2))
        if floor is None:
            visible_reason = floor_reason_code or "RUNTIME_FLOOR_MISSING"
            floor_display_values.append(visible_reason)
            floor_reason_values.append(visible_reason)
        else:
            floor_display_values.append(round(floor, 2))
            floor_reason_values.append("")

        ceiling = _safe_float(row.get("execution_final_ceiling_landed_gbp", ""))
        if ceiling is None:
            ceiling = _safe_float(row.get("ceiling_rule_value_gbp", ""))
        model_ceiling = ceiling
        unified_truth = resolve_unified_truth(
            suppression_active_flag=row.get("suppression_active_flag", ""),
            parked_flag=row.get("parked_flag", "0"),
            write_capable=_authoritative_write_enabled(row),
            execution_state=row.get("execution_state", ""),
            execution_write_status=row.get("execution_write_status", ""),
            execution_reason_codes_json=row.get("execution_reason_codes_json", ""),
            execution_final_ceiling_landed_gbp=row.get("execution_final_ceiling_landed_gbp", ""),
            execution_binding_ceiling_type=row.get("execution_binding_ceiling_type", ""),
            suppression_buy_box_state=row.get("suppression_buy_box_state", ""),
            suppression_strategy_state=row.get("suppression_strategy_state", ""),
            suppression_write_status=row.get("suppression_write_status", ""),
            suppression_ceiling_landed_temp=row.get("suppression_ceiling_landed_temp", ""),
            execution_old_price_gbp=row.get("execution_old_price_gbp", ""),
            execution_new_price_gbp=row.get("execution_new_price_gbp", ""),
            execution_hard_floor_gbp=row.get("execution_hard_floor_gbp", ""),
            observed_our_price_gbp=row.get("observed_our_price_gbp", ""),
            trace_candidate_price_gbp=row.get("trace_candidate_price_gbp", ""),
            trace_floor_total_gbp=row.get("trace_floor_total_gbp", ""),
            execution_event_ts_utc=row.get("execution_event_ts_utc", ""),
            trace_asof_utc=row.get("trace_asof_utc", ""),
        )
        active_ceiling = _safe_float(row.get("true_binding_ceiling_gbp", ""))
        if active_ceiling is None:
            active_ceiling = _safe_float(unified_truth.get("true_binding_ceiling_gbp", ""))
        if active_ceiling is None:
            active_ceiling = model_ceiling
        ceiling_values.append("" if active_ceiling is None else round(active_ceiling, 2))
        truth_model_ceiling_values.append("" if model_ceiling is None else round(model_ceiling, 2))

        available_qty = _safe_float(row.get("available_stock_qty", ""))
        stock_qty = available_qty if available_qty is not None else _safe_float(row.get("stock_qty", ""))
        inbound_total_qty = _safe_float(row.get("inbound_total_qty", "")) or 0.0
        if stock_qty is not None:
            stock = int(stock_qty) if float(stock_qty).is_integer() else round(stock_qty, 2)
            in_stock_from_qty = 1 if stock_qty > 0 else 0
        else:
            in_stock_from_qty = _safe_int_flag(row.get("in_stock_flag", "0"))
            stock = in_stock_from_qty
        stock_values.append(stock)

        parked = _safe_int_flag(row.get("parked_flag", "0"))
        merchant_status = str(row.get("merchant_status", "")).strip().lower()
        actionable = 1 if (in_stock_from_qty == 1 and parked == 0 and (merchant_status == "" or merchant_status == "active")) else 0
        actionable_values.append(actionable)

        probe_label = "INBOUND" if ((stock_qty is not None and stock_qty <= 0) and inbound_total_qty > 0) else ""
        probe_values.append(probe_label)
        live_write_enabled = _authoritative_write_enabled(row)
        if parked == 1:
            capability_status = "PARKED"
        elif live_write_enabled:
            capability_status = "WRITE_CAPABLE"
        else:
            capability_status = "READ_ONLY"
        capability_status_values.append(capability_status)
        if parked == 1:
            automation_status = "PARKED"
        else:
            automation_status = unified_truth["truth_status"]
        automation_status_values.append(automation_status)

        has_buy_box = _safe_int_flag(row.get("has_buy_box", "0"))
        buy_box_values.append(has_buy_box)
        truth_buy_box = str(row.get("unified_buy_box_state", "")).strip().upper() or unified_truth["unified_buy_box_state"] or ("NORMAL" if has_buy_box == 1 else "")
        truth_state = str(row.get("unified_strategy_state", "")).strip() or unified_truth["unified_strategy_state"]
        truth_writer_outcome = str(row.get("unified_writer_outcome", "")).strip() or unified_truth["unified_writer_outcome"]
        truth_ceiling_type = str(row.get("true_binding_ceiling_type", "")).strip().upper() or unified_truth["true_binding_ceiling_type"]
        truth_buy_box_values.append(truth_buy_box)
        truth_state_values.append(truth_state)
        truth_writer_outcome_values.append(truth_writer_outcome)
        truth_ceiling_type_values.append(truth_ceiling_type)

        sku = str(row.get("sku", "")).strip()
        next_comp = _safe_float(row.get("next_comp_gbp", ""))
        missing_initial = 0
        fallback_added = 0
        reason_code = ""
        if in_stock_from_qty == 1 and next_comp is None:
            missing_initial = 1
            fallback_price = run_window_rival_map.get(sku)
            if fallback_price is None:
                fallback_price = recent_rival_map.get(sku)
            if fallback_price is not None and fallback_price > 0:
                next_comp = float(fallback_price)
                fallback_added = 1
                reason_code = "RIVAL_FALLBACK_FROM_SNAPSHOT_FACTS"
        if in_stock_from_qty == 1 and next_comp is None:
            current_for_default = _safe_float(row.get("current_price_gbp", ""))
            floor_for_default = floor
            cpt_for_default = _safe_float(row.get("cpt_gbp", ""))
            ceiling_for_default = ceiling
            for candidate in [current_for_default, floor_for_default, cpt_for_default, ceiling_for_default]:
                if candidate is not None and candidate > 0:
                    next_comp = float(candidate)
                    break
            if next_comp is None:
                next_comp = 0.0
            reason_code = "NO_RIVAL_DATA"
        next_comp_values.append("" if next_comp is None else round(next_comp, 2))
        compet_reason_values.append(reason_code)
        compet_missing_initial_values.append(missing_initial)
        compet_fallback_added_values.append(fallback_added)
        compet_no_rival_data_values.append(1 if reason_code == "NO_RIVAL_DATA" else 0)
        can_fight = 1 if (floor is not None and next_comp is not None and floor <= next_comp) else 0
        can_fight_values.append(can_fight)

        floor_gt_ceiling = 1 if (floor is not None and ceiling is not None and floor > ceiling) else 0
        floor_gt_ceiling_values.append(floor_gt_ceiling)

        cpt = _safe_float(row.get("cpt_gbp", ""))
        current = _safe_float(row.get("current_price_gbp", ""))
        roi_floor = _roi_on_cogs_pct_for_price(sku, floor, floor_ctx, vat_registered)
        roi_cpt = _roi_on_cogs_pct_for_price(sku, cpt, floor_ctx, vat_registered)
        roi_our = _roi_on_cogs_pct_for_price(sku, current, floor_ctx, vat_registered)
        roi_next = _roi_on_cogs_pct_for_price(sku, next_comp, floor_ctx, vat_registered)
        roi_ceiling = _roi_on_cogs_pct_for_price(sku, ceiling, floor_ctx, vat_registered)
        roi_floor_values.append("" if roi_floor is None else round(roi_floor, 2))
        roi_cpt_values.append("" if roi_cpt is None else round(roi_cpt, 2))
        roi_our_values.append("" if roi_our is None else round(roi_our, 2))
        roi_next_values.append("" if roi_next is None else round(roi_next, 2))
        roi_ceiling_values.append("" if roi_ceiling is None else round(roi_ceiling, 2))
        cogs_available = cogs_available_cache.get(sku)
        if cogs_available is None:
            cogs_available = _cogs_available_for_sku(sku, floor_ctx)
            cogs_available_cache[sku] = cogs_available
        cost_missing = 1 if (next_comp is not None and roi_next is None and not cogs_available) else 0
        ceiling_missing = 1 if ceiling is None else 0
        reason_codes: list[str] = []
        if reason_code != "":
            reason_codes.append(reason_code)
        if cost_missing == 1:
            reason_codes.append("COST_MISSING")
        if ceiling_missing == 1:
            reason_codes.append("CEILING_MISSING")
        reconcile_action = str(unified_truth.get("suppression_reconcile_action", "")).strip()
        if reconcile_action:
            reason_codes.append(reconcile_action)
        cost_missing_values.append(cost_missing)
        ceiling_missing_values.append(ceiling_missing)
        publish_reason_codes_values.append("|".join(reason_codes))

        sales_units_30d = _safe_float(row.get("sales_units_30d", ""))
        sales_per_day = _safe_float(row.get("sales_per_day_30d", ""))
        stock_num = _safe_float(stock)
        days_of_stock = None
        if stock_num is not None and sales_per_day is not None and sales_per_day > 0:
            days_of_stock = stock_num / sales_per_day
        elif stock_num is not None:
            # No velocity yet: show an explicit long-hold sentinel instead of blank.
            days_of_stock = 999.0
        sales_units_30d_values.append("" if sales_units_30d is None else round(sales_units_30d, 2))
        sales_per_day_values.append(0.0 if sales_per_day is None else round(sales_per_day, 3))
        days_of_stock_values.append("" if days_of_stock is None else round(days_of_stock, 2))

        score = (
            in_stock_from_qty * 100000
            + has_buy_box * 10000
            + can_fight * 1000
            - floor_gt_ceiling * 500
            - age_for_score
        )
        sort_scores.append(score)

    combined["last_scan_utc"] = last_scan_values
    combined["age_minutes"] = minutes_values
    combined["stock"] = stock_values
    combined["floor_gbp"] = floor_values
    combined["floor_display"] = floor_display_values
    combined["floor_reason_code"] = floor_reason_values
    combined["cpt_gbp"] = combined.get("cpt_gbp", "")
    observed_current = combined["observed_our_price_gbp"] if "observed_our_price_gbp" in combined.columns else pd.Series([""] * len(combined.index))
    observed_current_ts = combined["observed_our_price_ts_utc"] if "observed_our_price_ts_utc" in combined.columns else pd.Series([""] * len(combined.index))
    listing_current = combined["current_price_gbp"] if "current_price_gbp" in combined.columns else pd.Series([""] * len(combined.index))
    listing_current_ts = combined["listing_asof_ts_utc"] if "listing_asof_ts_utc" in combined.columns else pd.Series([""] * len(combined.index))
    execution_current = combined["execution_new_price_gbp"] if "execution_new_price_gbp" in combined.columns else pd.Series([""] * len(combined.index))
    execution_write_status = combined["execution_write_status"] if "execution_write_status" in combined.columns else pd.Series([""] * len(combined.index))
    execution_current_ts = combined["execution_event_ts_utc"] if "execution_event_ts_utc" in combined.columns else pd.Series([""] * len(combined.index))
    observed_current_num = pd.to_numeric(observed_current, errors="coerce")
    listing_current_num = pd.to_numeric(listing_current, errors="coerce")
    execution_current_num = pd.to_numeric(execution_current, errors="coerce")
    observed_current_dt = pd.to_datetime(observed_current_ts, errors="coerce", utc=True)
    listing_current_dt = pd.to_datetime(listing_current_ts, errors="coerce", utc=True)
    execution_current_dt = pd.to_datetime(execution_current_ts, errors="coerce", utc=True)
    execution_applied_mask = execution_write_status.astype(str).str.upper().eq("APPLIED")
    execution_applied_num = execution_current_num.where(execution_applied_mask)
    execution_is_freshest = execution_applied_num.notna() & (
        (observed_current_dt.isna() | execution_current_dt.ge(observed_current_dt))
        & (listing_current_dt.isna() | execution_current_dt.ge(listing_current_dt))
    )
    current_price_num = execution_applied_num.where(execution_is_freshest, observed_current_num)
    combined["current_price_gbp"] = current_price_num.where(current_price_num.notna(), listing_current_num)
    combined["next_comp_gbp"] = next_comp_values
    combined["ceiling_gbp"] = ceiling_values
    combined["is_actionable"] = actionable_values
    combined["has_buy_box"] = buy_box_values
    combined["can_fight"] = can_fight_values
    combined["floor_gt_ceiling"] = floor_gt_ceiling_values
    combined["automation_status"] = automation_status_values
    # Keep combined truth_status aligned with reconciled automation status.
    combined["truth_status"] = automation_status_values
    combined["capability_status"] = capability_status_values
    combined["truth_buy_box_state"] = truth_buy_box_values
    combined["truth_strategy_state"] = truth_state_values
    combined["truth_writer_outcome"] = truth_writer_outcome_values
    combined["truth_ceiling_type"] = truth_ceiling_type_values
    combined["model_ceiling_gbp"] = truth_model_ceiling_values
    combined["roi_floor_pct"] = roi_floor_values
    combined["roi_cpt_pct"] = roi_cpt_values
    combined["roi_our_price_pct"] = roi_our_values
    combined["roi_next_comp_pct"] = roi_next_values
    combined["roi_ceiling_pct"] = roi_ceiling_values
    combined["sales_units_30d"] = sales_units_30d_values
    combined["sales_per_day_30d"] = sales_per_day_values
    combined["days_of_stock_est"] = days_of_stock_values
    combined["compet_reason_code"] = compet_reason_values
    combined["compet_missing_initial_flag"] = compet_missing_initial_values
    combined["compet_fallback_added_flag"] = compet_fallback_added_values
    combined["compet_no_rival_data_flag"] = compet_no_rival_data_values
    combined["cost_missing_flag"] = cost_missing_values
    combined["ceiling_missing_flag"] = ceiling_missing_values
    combined["publish_reason_codes"] = publish_reason_codes_values
    combined["probe_label"] = probe_values
    combined["sort_score"] = sort_scores

    combined = combined.sort_values(["sort_score", "age_minutes", "sku"], ascending=[False, True, True]).reset_index(drop=True)
    return combined


def _build_view_df(combined_df: pd.DataFrame) -> pd.DataFrame:
    if combined_df.empty:
        return pd.DataFrame(
            columns=[
                "Status",
                "PROBE",
                "Minutes",
                "SKU",
                "Stock",
                "Floor",
                "CPT",
                "Current",
                "Compet",
                "Ceiling",
                "Floor %",
                "CPT %",
                "Current %",
                "Compet %",
                "Ceiling %",
                "Today Units",
                "Per Day",
                "Stock Days",
                "Buy Box",
                "State",
                "Write Result",
                "Capability",
                "Ceiling Type",
                "Model Ceiling",
                "_last_scan_utc",
            ]
        )

    # Human viewer intent: show in-stock inventory in one place.
    # Include SKU when merchant is active and stock quantity is positive.
    merchant_active = combined_df.get("merchant_status", "").astype(str).str.lower().eq("active")
    available_pos = pd.to_numeric(combined_df.get("available_stock_qty", ""), errors="coerce").fillna(0).gt(0)
    inbound_pos = pd.to_numeric(combined_df.get("inbound_total_qty", ""), errors="coerce").fillna(0).gt(0)
    inventory_active = available_pos | inbound_pos
    sku_present = combined_df.get("sku", "").astype(str).str.strip().ne("")
    view_source = combined_df.loc[merchant_active & inventory_active & sku_present].copy()
    if view_source.empty:
        view_source = combined_df.head(0).copy()
    cpt_display = view_source["cpt_gbp"].astype(str).str.strip().replace({"nan": "", "NaN": ""})
    cpt_display = cpt_display.mask(cpt_display.eq(""), "--")

    view = pd.DataFrame(
        {
            "Status": view_source["automation_status"],
            "PROBE": view_source["probe_label"],
            "Minutes": view_source["age_minutes"],
            "SKU": view_source["sku"],
            "Stock": view_source["stock"],
            "Floor": view_source["floor_display"],
            "CPT": cpt_display,
            "Current": view_source["current_price_gbp"],
            "Compet": view_source["next_comp_gbp"],
            "Ceiling": view_source["ceiling_gbp"],
            "Floor %": view_source["roi_floor_pct"],
            "CPT %": view_source["roi_cpt_pct"],
            "Current %": view_source["roi_our_price_pct"],
            "Compet %": view_source["roi_next_comp_pct"],
            "Ceiling %": view_source["roi_ceiling_pct"],
            "Today Units": view_source["sales_units_today"],
            "Per Day": view_source["sales_per_day_30d"],
            "Stock Days": view_source["days_of_stock_est"],
            "Buy Box": view_source["truth_buy_box_state"],
            "State": view_source["truth_strategy_state"],
            "Write Result": view_source["truth_writer_outcome"],
            "Capability": view_source["capability_status"],
            "Ceiling Type": view_source["truth_ceiling_type"],
            "Model Ceiling": view_source["model_ceiling_gbp"],
            "_last_scan_utc": view_source["last_scan_utc"].astype(str).map(_sheet_datetime_text),
        }
    )
    cpt_roi_display = view["CPT %"].astype(str).str.strip().replace({"nan": "", "NaN": ""})
    view["CPT %"] = cpt_roi_display.mask(cpt_roi_display.eq(""), "--")
    return view


def _sheet_payload(df: pd.DataFrame) -> list[list[str]]:
    if df.empty:
        return [df.columns.tolist()]
    rows = [df.columns.tolist()]
    for _, row in df.iterrows():
        values: list[Any] = []
        for v in row.tolist():
            if v is None:
                values.append("")
            elif pd.isna(v):
                values.append("")
            elif isinstance(v, float) and (v == float("inf") or v == float("-inf")):
                values.append("")
            else:
                values.append(v)
        rows.append(values)
    return rows


def _get_gspread_client(creds_path: Path):
    import gspread

    return gspread.service_account(filename=str(creds_path))


def _resolve_creds_path(raw_creds_path: str) -> Path:
    env_creds = str(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")).strip()
    chosen = env_creds or str(raw_creds_path or "").strip()
    return Path(chosen).expanduser()


def _ensure_creds_readable(creds_path: Path) -> Path:
    # Avoid metadata-only probes like Path.exists(), which can fail on some
    # Windows permission setups even when direct file reads succeed.
    with creds_path.open("r", encoding="utf-8") as fh:
        fh.read(1)
    return creds_path


def _upsert_tab(sheet, tab_name: str, values: list[list[Any]], *, start_cell: str = "A1"):
    import gspread

    rows = max(len(values) + 10, 2000)
    cols = max((len(values[0]) if values else 8) + 5, 20)
    try:
        ws = sheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=tab_name, rows=rows, cols=cols)
    else:
        try:
            ws.resize(rows=rows, cols=cols)
        except Exception:
            pass
        ws.clear()
    if values:
        ws.update(range_name=start_cell, values=values, value_input_option="USER_ENTERED")
    return ws


def _ensure_sheet_grid(sheet, ws, *, rows: int, cols: int):
    target_rows = max(int(rows), 1)
    target_cols = max(int(cols), 1)
    sheet.batch_update(
        {
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": int(ws._properties["sheetId"]),
                            "gridProperties": {
                                "rowCount": target_rows,
                                "columnCount": target_cols,
                            },
                        },
                        "fields": "gridProperties.rowCount,gridProperties.columnCount",
                    }
                }
            ]
        }
    )
    refreshed = sheet.worksheet(ws.title)
    if int(getattr(refreshed, "row_count", 0) or 0) < target_rows or int(getattr(refreshed, "col_count", 0) or 0) < target_cols:
        raise RuntimeError(
            f"worksheet_grid_resize_failed title={ws.title} rows={getattr(refreshed, 'row_count', 0)} cols={getattr(refreshed, 'col_count', 0)}"
        )
    return refreshed


def _delete_tab_if_exists(sheet, tab_name: str) -> bool:
    import gspread

    name = str(tab_name or "").strip()
    if name == "":
        return False
    try:
        ws = sheet.worksheet(name)
    except gspread.WorksheetNotFound:
        return False
    sheet.del_worksheet(ws)
    return True


def _set_minute_recalc(sheet) -> None:
    # Keep NOW() freshness timers live without requiring manual edits.
    sheet.batch_update(
        {
            "requests": [
                {
                    "updateSpreadsheetProperties": {
                        "properties": {"autoRecalc": "MINUTE"},
                        "fields": "autoRecalc",
                    }
                }
            ]
        }
    )


def _rgb(r: int, g: int, b: int) -> dict[str, float]:
    return {"red": r / 255.0, "green": g / 255.0, "blue": b / 255.0}


def _cf_rule(sheet_id: int, formula: str, start_col: int, end_col: int, color: dict[str, float], start_row: int = 1):
    return {
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [
                    {
                        "sheetId": sheet_id,
                        "startRowIndex": start_row,
                        "startColumnIndex": start_col,
                        "endColumnIndex": end_col,
                    }
                ],
                "booleanRule": {
                    "condition": {
                        "type": "CUSTOM_FORMULA",
                        "values": [{"userEnteredValue": formula}],
                    },
                    "format": {"backgroundColor": color},
                },
            },
            "index": 0,
        }
    }


def _clear_conditional_rules(sheet, target_sheet_id: int) -> None:
    meta = sheet.fetch_sheet_metadata()
    sheets = meta.get("sheets", [])
    delete_requests: list[dict[str, Any]] = []
    for s in sheets:
        props = s.get("properties", {})
        sid = props.get("sheetId")
        if sid != target_sheet_id:
            continue
        rules = s.get("conditionalFormats", [])
        for idx in range(len(rules) - 1, -1, -1):
            delete_requests.append(
                {
                    "deleteConditionalFormatRule": {
                        "sheetId": sid,
                        "index": idx,
                    }
                }
            )
    if delete_requests:
        sheet.batch_update({"requests": delete_requests})


def _apply_view_formatting(sheet, view_ws) -> None:
    view_ws = _ensure_sheet_grid(sheet, view_ws, rows=2000, cols=VIEW_COLUMN_COUNT)
    sheet_id = int(view_ws._properties["sheetId"])
    _clear_conditional_rules(sheet, sheet_id)

    # Pastel palette for better readability during long manual review sessions.
    green = _rgb(198, 239, 206)
    amber = _rgb(255, 235, 156)
    red = _rgb(244, 204, 204)
    grey = _rgb(230, 230, 230)

    requests = [
        # Status first.
        _cf_rule(sheet_id, '=$A2="WRITE_APPLIED"', 0, 1, green, start_row=1),
        _cf_rule(sheet_id, '=$A2="WRITE_CAPABLE"', 0, 1, amber, start_row=1),
        _cf_rule(sheet_id, '=$A2="READ_ONLY"', 0, 1, amber, start_row=1),
        _cf_rule(sheet_id, '=$A2="SUPP_APPLIED"', 0, 1, amber, start_row=1),
        _cf_rule(sheet_id, '=OR($A2="SUPPRESSED",$A2="SUPP_BLOCKED")', 0, 1, red, start_row=1),
        _cf_rule(sheet_id, '=$A2="PARKED"', 0, 1, grey, start_row=1),
        # Minutes in front section.
        _cf_rule(sheet_id, '=AND($C2<>"",$C2<15)', 2, 3, green, start_row=1),
        _cf_rule(sheet_id, '=AND($C2>=15,$C2<30)', 2, 3, amber, start_row=1),
        _cf_rule(sheet_id, '=AND($C2<>"",$C2>=30)', 2, 3, red, start_row=1),
        # SKU color follows stock.
        _cf_rule(sheet_id, "=AND($E2<>\"\",$E2>0)", 3, 4, green, start_row=1),
        _cf_rule(sheet_id, "=AND($E2<>\"\",$E2<=0)", 3, 4, red, start_row=1),
        _cf_rule(sheet_id, "=AND($E2<>\"\",$E2>0)", 4, 5, green, start_row=1),
        _cf_rule(sheet_id, "=AND($E2<>\"\",$E2<=0)", 4, 5, red, start_row=1),
        _cf_rule(sheet_id, '=$G2="--"', 6, 7, grey, start_row=1),
        _cf_rule(sheet_id, '=AND($F2<>"",$I2<>"",$F2<=$I2)', 5, 6, green, start_row=1),
        _cf_rule(sheet_id, '=AND($F2<>"",$I2<>"",$F2>$I2,$F2<=$I2*1.02)', 5, 6, amber, start_row=1),
        _cf_rule(sheet_id, '=AND($F2<>"",$I2<>"",$F2>$I2*1.02)', 5, 6, red, start_row=1),
        _cf_rule(sheet_id, '=AND($G2<>"",$G2<>"--",$H2<>"",$H2<=$G2)', 6, 7, green, start_row=1),
        _cf_rule(sheet_id, '=AND($G2<>"",$G2<>"--",$H2<>"",$H2>$G2,$H2<=$G2*1.05)', 6, 7, amber, start_row=1),
        _cf_rule(sheet_id, '=AND($G2<>"",$G2<>"--",$H2<>"",$H2>$G2*1.05)', 6, 7, red, start_row=1),
        _cf_rule(sheet_id, '=AND($H2<>"",$I2<>"",$H2<=$I2)', 7, 8, green, start_row=1),
        _cf_rule(sheet_id, '=AND($H2<>"",$I2<>"",$H2>$I2,$H2<=$I2*1.01)', 7, 8, amber, start_row=1),
        _cf_rule(sheet_id, '=AND($H2<>"",$I2<>"",$H2>$I2*1.01)', 7, 8, red, start_row=1),
        _cf_rule(sheet_id, '=AND($H2<>"",$I2<>"",$I2>$H2*1.01)', 8, 9, green, start_row=1),
        _cf_rule(sheet_id, '=AND($H2<>"",$I2<>"",ABS($I2-$H2)<=($H2*0.01))', 8, 9, amber, start_row=1),
        _cf_rule(sheet_id, '=AND($H2<>"",$I2<>"",$I2<$H2*0.99)', 8, 9, red, start_row=1),
        _cf_rule(sheet_id, '=AND($H2<>"",$J2<>"",$H2<=$J2*0.95)', 9, 10, green, start_row=1),
        _cf_rule(sheet_id, '=AND($H2<>"",$J2<>"",$H2>$J2*0.95,$H2<=$J2)', 9, 10, amber, start_row=1),
        _cf_rule(sheet_id, '=AND($H2<>"",$J2<>"",$H2>$J2)', 9, 10, red, start_row=1),
        # ROI traffic lights: <9.8 red, 9.8-20 amber, >=20 green.
        _cf_rule(sheet_id, '=AND(K2<>"",K2<9.8)', 10, 15, red, start_row=1),
        _cf_rule(sheet_id, '=AND(K2<>"",K2>=9.8,K2<20)', 10, 15, amber, start_row=1),
        _cf_rule(sheet_id, '=AND(K2<>"",K2>=20)', 10, 15, green, start_row=1),
        _cf_rule(sheet_id, '=$L2="--"', 11, 12, grey, start_row=1),
        # Today Units: red=0, amber=>0, green=above daily average (Per Day).
        _cf_rule(sheet_id, '=AND($P2<>"",$Q2<>"",$P2>$Q2)', 15, 16, green, start_row=1),
        _cf_rule(sheet_id, '=AND($P2<>"",$P2>0,OR($Q2="",$P2<=$Q2))', 15, 16, amber, start_row=1),
        _cf_rule(sheet_id, '=AND($P2<>"",$P2=0)', 15, 16, red, start_row=1),
        # Per Day: red=0, amber=>0 and <1, green>=1.
        _cf_rule(sheet_id, '=AND($Q2<>"",$Q2>=1)', 16, 17, green, start_row=1),
        _cf_rule(sheet_id, '=AND($Q2<>"",$Q2>0,$Q2<1)', 16, 17, amber, start_row=1),
        _cf_rule(sheet_id, '=AND($Q2<>"",$Q2=0)', 16, 17, red, start_row=1),
        # Days of stock: <7 red, 7-14 amber, 14-90 green, >90 red.
        _cf_rule(sheet_id, '=AND($R2<>"",$R2<7)', 17, 18, red, start_row=1),
        _cf_rule(sheet_id, '=AND($R2>=7,$R2<=14)', 17, 18, amber, start_row=1),
        _cf_rule(sheet_id, '=AND($R2>14,$R2<=90)', 17, 18, green, start_row=1),
        _cf_rule(sheet_id, '=AND($R2<>"",$R2>90)', 17, 18, red, start_row=1),
    ]

    sheet.batch_update({"requests": requests})

    # Header rows are written explicitly each publish; do not insert rows.
    view_ws.update(
        range_name="A1",
        values=[[
            "SKU INFO",
            "",
            "",
            "",
            "",
            "LIVE FIGURES",
            "",
            "",
            "",
            "",
            "ROI INSIGHTS",
            "",
            "",
            "",
            "",
            "SALES VELOCITY",
            "",
            "",
            "",
            "TRUTH",
            "",
            "",
            "",
            "",
            "",
            "",
        ]],
        value_input_option="USER_ENTERED",
    )
    # Force row 2 subheaders every publish (protects against old merged-header artifacts).
    view_ws.update(
        range_name="A2",
        values=[[
            "Status",
            "PROBE",
            "Minutes",
            "SKU",
            "Stock",
            "Floor",
            "CPT",
            "Current",
            "Compet",
            "Ceiling",
            "Floor %",
            "CPT %",
            "Current %",
            "Compet %",
            "Ceiling %",
            "Today Units",
            "Per Day",
            "Stock Days",
            "Buy Box",
            "State",
            "Write Result",
            "Capability",
            "Ceiling Type",
            "Model Ceiling",
            "",
        ]],
        value_input_option="USER_ENTERED",
    )

    # Hide helper last-scan timestamp column so user sees only the viewer columns.
    sheet.batch_update(
        {
            "requests": [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 2,
                            "startColumnIndex": 2,
                            "endColumnIndex": 3,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {
                                    "type": "NUMBER",
                                    "pattern": "0.00",
                                }
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 2,
                            "startColumnIndex": 10,
                            "endColumnIndex": 18,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {
                                    "type": "NUMBER",
                                    "pattern": "0.00",
                                }
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 2,
                            "startColumnIndex": 16,
                            "endColumnIndex": 17,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {
                                    "type": "NUMBER",
                                    "pattern": "0.0",
                                }
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 2,
                            "startColumnIndex": 23,
                            "endColumnIndex": 24,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {
                                    "type": "NUMBER",
                                    "pattern": "0.00",
                                }
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                },
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": 24,
                            "endIndex": 25,
                        },
                        "properties": {"hiddenByUser": True},
                        "fields": "hiddenByUser",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startColumnIndex": 0,
                            "endColumnIndex": 25,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "horizontalAlignment": "CENTER",
                            }
                        },
                        "fields": "userEnteredFormat.horizontalAlignment",
                    }
                },
                {
                    "autoResizeDimensions": {
                        "dimensions": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": 0,
                            "endIndex": 25,
                        }
                    }
                },
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": 5,
                            "endIndex": 24,
                        },
                        "properties": {"pixelSize": 80},
                        "fields": "pixelSize",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 2000,
                            "startColumnIndex": 4,
                            "endColumnIndex": 5,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "borders": {
                                    "right": {
                                        "style": "SOLID",
                                        "color": _rgb(0, 0, 0),
                                    }
                                }
                            }
                        },
                        "fields": "userEnteredFormat.borders.right",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 2000,
                            "startColumnIndex": 9,
                            "endColumnIndex": 10,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "borders": {
                                    "right": {
                                        "style": "SOLID",
                                        "color": _rgb(0, 0, 0),
                                    }
                                }
                            }
                        },
                        "fields": "userEnteredFormat.borders.right",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 2000,
                            "startColumnIndex": 14,
                            "endColumnIndex": 15,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "borders": {
                                    "right": {
                                        "style": "SOLID",
                                        "color": _rgb(0, 0, 0),
                                    }
                                }
                            }
                        },
                        "fields": "userEnteredFormat.borders.right",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 2000,
                            "startColumnIndex": 17,
                            "endColumnIndex": 18,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "borders": {
                                    "right": {
                                        "style": "SOLID",
                                        "color": _rgb(0, 0, 0),
                                    }
                                }
                            }
                        },
                        "fields": "userEnteredFormat.borders.right",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 2000,
                            "startColumnIndex": 23,
                            "endColumnIndex": 24,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "borders": {
                                    "right": {
                                        "style": "SOLID",
                                        "color": _rgb(0, 0, 0),
                                    }
                                }
                            }
                        },
                        "fields": "userEnteredFormat.borders.right",
                    }
                },
                {
                    "unmergeCells": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 2000,
                            "startColumnIndex": 0,
                            "endColumnIndex": 25,
                        }
                    }
                },
                {
                    "mergeCells": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": 5,
                        },
                        "mergeType": "MERGE_ALL",
                    }
                },
                {
                    "mergeCells": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": 5,
                            "endColumnIndex": 10,
                        },
                        "mergeType": "MERGE_ALL",
                    }
                },
                {
                    "mergeCells": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": 10,
                            "endColumnIndex": 15,
                        },
                        "mergeType": "MERGE_ALL",
                    }
                },
                {
                    "mergeCells": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": 15,
                            "endColumnIndex": 18,
                        },
                        "mergeType": "MERGE_ALL",
                    }
                },
                {
                    "mergeCells": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": 18,
                            "endColumnIndex": 24,
                        },
                        "mergeType": "MERGE_ALL",
                    }
                },
                {
                    "unmergeCells": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 1,
                            "endRowIndex": 2,
                            "startColumnIndex": 0,
                            "endColumnIndex": 5,
                        }
                    }
                },
                {
                    "unmergeCells": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 1,
                            "endRowIndex": 2,
                            "startColumnIndex": 5,
                            "endColumnIndex": 10,
                        }
                    }
                },
                {
                    "unmergeCells": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 1,
                            "endRowIndex": 2,
                            "startColumnIndex": 10,
                            "endColumnIndex": 15,
                        }
                    }
                },
                {
                    "unmergeCells": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 1,
                            "endRowIndex": 2,
                            "startColumnIndex": 15,
                            "endColumnIndex": 18,
                        }
                    }
                },
                {
                    "unmergeCells": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 1,
                            "endRowIndex": 2,
                            "startColumnIndex": 18,
                            "endColumnIndex": 24,
                        }
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": 25,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": _rgb(242, 242, 242),
                                "textFormat": {"bold": True},
                                "horizontalAlignment": "CENTER",
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 1,
                            "endRowIndex": 2,
                            "startColumnIndex": 0,
                            "endColumnIndex": 25,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": True},
                            }
                        },
                        "fields": "userEnteredFormat.textFormat.bold",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 2,
                            "startColumnIndex": 0,
                            "endColumnIndex": 25,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": _rgb(255, 255, 255),
                            }
                        },
                        "fields": "userEnteredFormat.backgroundColor",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 2,
                            "endRowIndex": 2000,
                            "startColumnIndex": 0,
                            "endColumnIndex": 25,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": False},
                            }
                        },
                        "fields": "userEnteredFormat.textFormat.bold",
                    }
                }
            ]
        }
    )

    # Write subheaders again at the end so they are never lost by merge/batch side effects.
    view_ws.update(
        range_name="A2",
        values=[[
            "Status",
            "PROBE",
            "Minutes",
            "SKU",
            "Stock",
            "Floor",
            "CPT",
            "Current",
            "Compet",
            "Ceiling",
            "Floor %",
            "CPT %",
            "Current %",
            "Compet %",
            "Ceiling %",
            "Today Units",
            "Per Day",
            "Stock Days",
            "Buy Box",
            "State",
            "Write Result",
            "Capability",
            "Ceiling Type",
            "Model Ceiling",
            "",
        ]],
        value_input_option="USER_ENTERED",
    )

    view_ws.freeze(rows=2)
    _ensure_sheet_grid(sheet, view_ws, rows=2000, cols=VIEW_COLUMN_COUNT)


def _apply_live_minutes_formula(view_ws) -> None:
    # Keep Minutes live in-sheet from the hidden last-scan timestamp helper column.
    timestamp_col = HIDDEN_LAST_SCAN_COLUMN_LETTER
    # Clear prewritten values in column C so the array formula can spill.
    try:
        view_ws.batch_clear(["C3:C2000"])
    except Exception:
        pass
    view_ws.update(
        range_name="C3",
        values=[[
            f'=ARRAYFORMULA(IF({timestamp_col}3:INDEX({timestamp_col}:{timestamp_col},COUNTA(D:D)+1)="","",IFERROR(ROUND((NOW()-VALUE({timestamp_col}3:INDEX({timestamp_col}:{timestamp_col},COUNTA(D:D)+1)))*1440,2),"")))'
        ]],
        value_input_option="USER_ENTERED",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Stage 1 human viewer sheet for Phase 1 repricer observation")
    parser.add_argument("--scope-path", default=str(DEFAULT_SCOPE_PATH))
    parser.add_argument("--runtime-path", default=str(DEFAULT_RUNTIME_PATH))
    parser.add_argument("--floor-table-path", default=str(DEFAULT_FLOOR_TABLE_PATH))
    parser.add_argument("--daily-intel-path", default=str(DEFAULT_DAILY_INTEL_PATH))
    parser.add_argument("--product-db-path", default=str(DEFAULT_PRODUCT_DB_PATH))
    parser.add_argument("--inventory-path", default="")
    parser.add_argument("--order-master-path", default=str(DEFAULT_ORDER_MASTER_PATH))
    parser.add_argument("--listing-snapshot-path", default="")
    parser.add_argument("--sku-scan-state-path", default=str(DEFAULT_SKU_SCAN_STATE_PATH))
    parser.add_argument("--out-combined-csv", default="")
    parser.add_argument("--out-view-csv", default="")
    parser.add_argument("--sheet-id", default=DEFAULT_SHEET_ID)
    parser.add_argument("--creds-path", default=str(DEFAULT_CREDS))
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--date-utc", default=_today_utc_str())
    parser.add_argument("--view-tab", default="")
    parser.add_argument("--combined-tab", default="COMBINED")
    parser.add_argument("--raw-scope-tab", default="RAW_SCOPE")
    parser.add_argument("--raw-runtime-tab", default="RAW_RUNTIME")
    parser.add_argument("--raw-daily-intel-tab", default="RAW_DAILY_INTEL")
    parser.add_argument("--raw-listing-snapshot-tab", default="RAW_LISTING_SNAPSHOT")
    parser.add_argument("--debug-tabs", action="store_true")
    args = parser.parse_args()
    date_tab = str(args.date_utc or "").strip() or _today_utc_str()
    requested_view_tab = str(args.view_tab or "").strip()
    if requested_view_tab.upper() == "VIEW":
        # Reserve VIEW as a legacy tab name and force date-based publishing.
        print(f"phase1_observation_view_tab_normalized_from=VIEW")
        print(f"phase1_observation_view_tab_normalized_to={date_tab}")
        view_tab = date_tab
    else:
        view_tab = requested_view_tab or date_tab

    scope_path = Path(args.scope_path)
    runtime_path = Path(args.runtime_path)
    floor_table_path = Path(args.floor_table_path)
    daily_intel_path = Path(args.daily_intel_path)
    product_db_path = Path(args.product_db_path)
    inventory_path = Path(args.inventory_path) if str(args.inventory_path).strip() else _latest_inventory_path()
    order_master_path = Path(args.order_master_path)
    listing_snapshot_path = Path(args.listing_snapshot_path) if str(args.listing_snapshot_path).strip() else _latest_file("listing_offer_snapshot_*.csv")
    sku_scan_state_path = Path(args.sku_scan_state_path)

    if not scope_path.exists():
        raise FileNotFoundError(f"missing scope file: {scope_path}")
    if not runtime_path.exists():
        raise FileNotFoundError(f"missing runtime file: {runtime_path}")

    scope_df = _load_csv(scope_path)
    runtime_df = _load_csv(runtime_path)
    floor_table_df = _load_csv(floor_table_path)
    daily_intel_df = _load_csv(daily_intel_path)
    listing_df = _load_csv(listing_snapshot_path)
    product_df = _load_csv(product_db_path)
    inventory_df = _load_csv(inventory_path)
    order_master_df = _load_csv(order_master_path)
    last_scan_utc_by_sku = _load_last_scan_utc_by_sku(sku_scan_state_path)

    combined_df = _build_combined_df(
        scope_df=scope_df,
        runtime_df=runtime_df,
        floor_table_df=floor_table_df,
        daily_intel_df=daily_intel_df,
        listing_df=listing_df,
        product_df=product_df,
        inventory_df=inventory_df,
        order_master_df=order_master_df,
        last_scan_utc_by_sku=last_scan_utc_by_sku,
    )
    view_df = _build_view_df(combined_df)

    out_combined = Path(args.out_combined_csv) if str(args.out_combined_csv).strip() else OUT / "analysis_reports" / f"phase1_observation_combined_{args.date_utc}.csv"
    out_view = Path(args.out_view_csv) if str(args.out_view_csv).strip() else OUT / "analysis_reports" / f"phase1_observation_view_{args.date_utc}.csv"
    out_combined.parent.mkdir(parents=True, exist_ok=True)
    out_view.parent.mkdir(parents=True, exist_ok=True)
    combined_df.to_csv(out_combined, index=False)
    view_df.to_csv(out_view, index=False)

    print(f"phase1_observation_scope_rows={len(scope_df.index)}")
    print(f"phase1_observation_combined_rows={len(combined_df.index)}")
    print(f"phase1_observation_view_rows={len(view_df.index)}")
    print(f"phase1_observation_combined_out={out_combined}")
    print(f"phase1_observation_view_out={out_view}")
    if listing_snapshot_path:
        print(f"phase1_observation_listing_snapshot={listing_snapshot_path}")
    if inventory_path:
        print(f"phase1_observation_inventory_source={inventory_path}")
    print(f"phase1_observation_daily_intel_exists={'1' if not daily_intel_df.empty else '0'}")
    missing_initial_count = int(pd.to_numeric(combined_df.get("compet_missing_initial_flag", 0), errors="coerce").fillna(0).sum())
    fallback_added_count = int(pd.to_numeric(combined_df.get("compet_fallback_added_flag", 0), errors="coerce").fillna(0).sum())
    no_rival_data_count = int(pd.to_numeric(combined_df.get("compet_no_rival_data_flag", 0), errors="coerce").fillna(0).sum())
    fallback_examples = combined_df.loc[
        pd.to_numeric(combined_df.get("compet_fallback_added_flag", 0), errors="coerce").fillna(0).eq(1),
        ["sku", "next_comp_gbp", "roi_next_comp_pct"],
    ].head(5)
    print(f"phase1_compet_fallback_missing_initial={missing_initial_count}")
    print(f"phase1_compet_fallback_added={fallback_added_count}")
    print(f"phase1_compet_no_rival_data={no_rival_data_count}")
    for _, ex in fallback_examples.iterrows():
        print(
            "phase1_compet_fallback_example "
            f"sku={str(ex.get('sku', '')).strip()} "
            f"compet={str(ex.get('next_comp_gbp', '')).strip()} "
            f"compet_roi={str(ex.get('roi_next_comp_pct', '')).strip()}"
        )

    if not args.publish:
        print("phase1_observation_publish=skipped")
        return 0

    creds_path = _ensure_creds_readable(_resolve_creds_path(args.creds_path))
    client = _get_gspread_client(creds_path)
    sheet = client.open_by_key(args.sheet_id)
    _set_minute_recalc(sheet)

    combined_ws = None
    if args.debug_tabs:
        _upsert_tab(sheet, args.raw_scope_tab, _sheet_payload(scope_df))
        _upsert_tab(sheet, args.raw_runtime_tab, _sheet_payload(runtime_df))
        if not daily_intel_df.empty:
            _upsert_tab(sheet, args.raw_daily_intel_tab, _sheet_payload(daily_intel_df))
        if not listing_df.empty:
            _upsert_tab(sheet, args.raw_listing_snapshot_tab, _sheet_payload(listing_df))
        combined_ws = _upsert_tab(sheet, args.combined_tab, _sheet_payload(combined_df))
    # Publish viewer data from row 3 so rows 1-2 remain dedicated to grouped/sub headers.
    view_payload = _sheet_payload(view_df)
    view_data_payload = view_payload[1:] if len(view_payload) > 1 else []
    view_ws = _upsert_tab(sheet, view_tab, view_data_payload, start_cell="A3")
    view_ws = _ensure_sheet_grid(sheet, view_ws, rows=2000, cols=VIEW_COLUMN_COUNT)
    _apply_view_formatting(sheet, view_ws)
    view_ws = _ensure_sheet_grid(sheet, sheet.worksheet(view_tab), rows=2000, cols=VIEW_COLUMN_COUNT)
    _apply_live_minutes_formula(view_ws)
    if combined_ws is not None:
        try:
            combined_ws.hide()
        except Exception:
            pass

    if not args.debug_tabs:
        tabs_to_prune = {
            "VIEW",
            str(args.combined_tab or "").strip(),
            str(args.raw_scope_tab or "").strip(),
            str(args.raw_runtime_tab or "").strip(),
            str(args.raw_daily_intel_tab or "").strip(),
            str(args.raw_listing_snapshot_tab or "").strip(),
        }
        tabs_to_prune.discard("")
        tabs_to_prune.discard(view_tab)
        for tab in sorted(tabs_to_prune):
            _delete_tab_if_exists(sheet, tab)

    print("phase1_observation_publish=ok")
    print(f"phase1_observation_sheet_id={args.sheet_id}")
    print(f"phase1_observation_view_tab={view_tab}")
    print(f"phase1_observation_debug_tabs={'1' if args.debug_tabs else '0'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


