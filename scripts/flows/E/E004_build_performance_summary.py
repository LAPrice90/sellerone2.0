from __future__ import annotations

import os
from pathlib import Path
import sys
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.core.storage import (
        StorageConfig,
        connect_store,
        parse_storage_mode,
        read_dataframe_with_sql_fallback,
        replace_table_from_dataframe,
    )
except ModuleNotFoundError:
    from core.storage import (
        StorageConfig,
        connect_store,
        parse_storage_mode,
        read_dataframe_with_sql_fallback,
        replace_table_from_dataframe,
    )

OUT = Path("out")
VELOCITY = OUT / "sku_sales_velocity.csv"
ROI = OUT / "sku_roi_snapshot.csv"
RESTOCK = OUT / "sku_restock_signals.csv"
OUT_SUMMARY = OUT / "sku_performance_summary.csv"
TOKEN_COGS = OUT / "token_cogs_ledger.csv"
REFUND_HISTORY = OUT / "refund_adjustment_history.csv"
REFUND_RATE_PROOF = OUT / "systems" / "B" / "refunds" / "b_sku_refund_rate.csv"
FIN_L3 = OUT / "financial_events_level3_official.csv"
LISTING_HISTORY = OUT / "listing_offer_history.csv"
SQL_TABLE = "e_sku_performance_summary"
SQL_TABLE_LISTING_OFFER_HISTORY = "h_listing_offer_history"
MISSING_ROI_REASON_LABELS = [
    "roi_clean",
    "velocity_only_sales_truth",
    "stock_only_no_sales_window",
    "no_recent_sales_truth",
    "missing_cogs_or_fx",
    "missing_fee_proof",
    "missing_refund_proof",
    "missing_current_price_proof",
    "b_money_bridge_labelled",
    "not_available",
]
WEAK_REFUND_PROOF_STATES = {
    "",
    "not_yet_proven",
    "sellerboard_bridge_only",
    "bridge_labelled_only",
    "not_verified",
}
WEAK_REFUND_CONFIDENCE_STATES = {
    "",
    "no_refund_rate_proof",
    "legacy_history_not_manager_proven",
    "not_verified",
}
RESTOCK_DECISION_STATES = {
    "business_ready_clean",
    "stock_signal_only",
    "blocked_missing_roi",
    "blocked_missing_profit_inputs",
    "warning_bridge_labelled_money",
    "blocked_weak_refund_proof",
    "blocked_missing_current_price",
    "not_applicable_no_stock_signal",
}
RESTOCK_EVIDENCE_ROLE = "evidence_only_not_buy_instruction"


def _read_csv(path: Path) -> pd.DataFrame:
    if path == LISTING_HISTORY:
        try:
            return read_dataframe_with_sql_fallback(path, SQL_TABLE_LISTING_OFFER_HISTORY, dtype=str).fillna("")
        except FileNotFoundError:
            return pd.DataFrame()
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _b_money_summary_path() -> Path:
    return OUT / "systems" / "M" / "sellerboard_bridge" / "b_sellerboard_bridge_summary.csv"


def _b_money_context() -> dict[str, str]:
    context = {
        "b_money_confidence_state": "not_verified",
        "b_bridge_values_safe_for_live_roi": "0",
    }
    bridge = _read_csv(_b_money_summary_path())
    if bridge.empty or "metric" not in bridge.columns or "value" not in bridge.columns:
        return context
    metrics = {
        str(row.get("metric", "") or "").strip(): str(row.get("value", "") or "").strip()
        for _idx, row in bridge.iterrows()
    }
    context["b_money_confidence_state"] = metrics.get("roi_money_confidence_state") or "not_verified"
    context["b_bridge_values_safe_for_live_roi"] = metrics.get("bridge_values_safe_for_live_roi") or "0"
    return context


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _series_or_default(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col in df.columns:
        return df[col]
    return pd.Series([default] * len(df), index=df.index)


def _norm_sku(value: object) -> str:
    return str(value or "").strip().upper()


def _write_summary_output(df: pd.DataFrame) -> dict[str, object]:
    mode = parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE", "csv"))
    sql_rows = 0

    def write_csv() -> None:
        OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(OUT_SUMMARY, index=False)

    def write_sql() -> None:
        nonlocal sql_rows
        store = connect_store(StorageConfig.from_env())
        try:
            result = replace_table_from_dataframe(store, SQL_TABLE, df)
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

    return {"mode": mode, "sql_table": SQL_TABLE if sql_rows or mode != "csv" else "", "sql_rows": sql_rows}


def _latest_listing_snapshot_path() -> Path | None:
    files = sorted(OUT.glob("listing_offer_snapshot_*.csv"))
    if not files:
        return None
    return files[-1]


def _prepare_listing_maps() -> tuple[dict[str, float], dict[str, float], dict[str, float], dict[str, float], dict[str, float]]:
    latest_our: dict[str, float] = {}
    latest_buy_box: dict[str, float] = {}
    latest_lowest_fba: dict[str, float] = {}
    hist_last_our: dict[str, float] = {}
    hist_last_buy_box: dict[str, float] = {}

    snap_path = _latest_listing_snapshot_path()
    if snap_path and snap_path.exists():
        snap = _read_csv(snap_path)
        if not snap.empty:
            snap["sku_norm"] = snap.get("sku", "").map(_norm_sku)
            snap["our_price_num"] = _to_num(_series_or_default(snap, "our_price", np.nan))
            snap["buy_box_price_num"] = _to_num(_series_or_default(snap, "buy_box_price", np.nan))
            snap["lowest_fba_price_num"] = _to_num(_series_or_default(snap, "lowest_fba_price", np.nan))
            for _, row in snap.iterrows():
                sku = row.get("sku_norm", "")
                if not sku:
                    continue
                our = row.get("our_price_num")
                bb = row.get("buy_box_price_num")
                lfa = row.get("lowest_fba_price_num")
                if pd.notna(our):
                    latest_our[sku] = float(our)
                if pd.notna(bb):
                    latest_buy_box[sku] = float(bb)
                if pd.notna(lfa):
                    latest_lowest_fba[sku] = float(lfa)

    if LISTING_HISTORY.exists():
        hist = _read_csv(LISTING_HISTORY)
        if not hist.empty:
            hist["sku_norm"] = hist.get("sku", "").map(_norm_sku)
            hist["our_price_num"] = _to_num(_series_or_default(hist, "our_price", np.nan))
            hist["buy_box_price_num"] = _to_num(_series_or_default(hist, "buy_box_price", np.nan))
            hist["asof_dt"] = pd.to_datetime(hist.get("asof_date", ""), errors="coerce")
            hist["timestamp_dt"] = pd.to_datetime(hist.get("timestamp_utc", ""), errors="coerce", utc=True)
            hist = hist.sort_values(["asof_dt", "timestamp_dt"], kind="stable")
            hist_our_valid = hist[pd.notna(hist["our_price_num"])]
            for _, row in hist_our_valid.iterrows():
                sku = row.get("sku_norm", "")
                if not sku:
                    continue
                hist_last_our[sku] = float(row["our_price_num"])
            hist_valid = hist[pd.notna(hist["buy_box_price_num"])]
            for _, row in hist_valid.iterrows():
                sku = row.get("sku_norm", "")
                if not sku:
                    continue
                hist_last_buy_box[sku] = float(row["buy_box_price_num"])

    return latest_our, latest_buy_box, latest_lowest_fba, hist_last_our, hist_last_buy_box


def _prepare_token_df() -> pd.DataFrame:
    token = _read_csv(TOKEN_COGS)
    if token.empty:
        return token
    token["sku_norm"] = token.get("seller_sku", "").map(_norm_sku)
    token["order_dt"] = pd.to_datetime(token.get("order_date", ""), errors="coerce", utc=True)
    token["cogs_exvat_num"] = _to_num(_series_or_default(token, "cogs_exvat", np.nan))
    token["vat_rate_pct_num"] = _to_num(_series_or_default(token, "vat_rate_pct", np.nan))
    token = token[(token["sku_norm"] != "") & pd.notna(token["order_dt"]) & pd.notna(token["cogs_exvat_num"])]
    return token


def _prepare_fin_df() -> pd.DataFrame:
    fin = _read_csv(FIN_L3)
    if fin.empty:
        return fin
    fin["sku_norm"] = fin.get("SKU", "").map(_norm_sku)
    fin["date_dt"] = pd.to_datetime(fin.get("Date", ""), errors="coerce", utc=True)
    fin["fba_fee_exvat_num"] = _to_num(_series_or_default(fin, "FBA_Fee_ExVAT", np.nan))
    fin["commission_exvat_num"] = _to_num(_series_or_default(fin, "Commission_ExVAT", np.nan))
    fin["digital_fee_exvat_num"] = _to_num(_series_or_default(fin, "Digital_Fee_ExVAT", np.nan))
    fin = fin[(fin["sku_norm"] != "") & pd.notna(fin["date_dt"])]
    return fin


def _prepare_refund_df() -> pd.DataFrame:
    ref = _read_csv(REFUND_HISTORY)
    if ref.empty:
        return ref
    ref["sku_norm"] = ref.get("sku", "").map(_norm_sku)
    ref["asof_dt"] = pd.to_datetime(ref.get("asof_date", ""), errors="coerce")
    ref["refund_amount_num"] = _to_num(_series_or_default(ref, "refund_amount_gbp", 0.0)).fillna(0.0)
    ref["adjustment_amount_num"] = _to_num(_series_or_default(ref, "adjustment_amount_gbp", 0.0)).fillna(0.0)
    ref = ref[(ref["sku_norm"] != "") & pd.notna(ref["asof_dt"])]
    return ref


def _prepare_refund_rate_df() -> pd.DataFrame:
    rates = _read_csv(REFUND_RATE_PROOF)
    if rates.empty:
        return rates
    rates["sku_norm"] = rates.get("sku", "").map(_norm_sku)
    rates["window_days_num"] = _to_num(_series_or_default(rates, "window_days", np.nan))
    rates["sales_units_num"] = _to_num(_series_or_default(rates, "sales_units", 0.0)).fillna(0.0)
    rates["refund_units_num"] = _to_num(_series_or_default(rates, "refund_units", 0.0)).fillna(0.0)
    rates["refund_unit_rate_num"] = _to_num(_series_or_default(rates, "refund_unit_rate", 0.0)).fillna(0.0)
    rates["expected_refund_cost_num"] = _to_num(_series_or_default(rates, "expected_refund_cost_per_unit_gbp", 0.0)).fillna(0.0)
    rates = rates[(rates["sku_norm"] != "") & rates["window_days_num"].isin([30, 90])]
    return rates


def _select_window(df: pd.DataFrame, sku: str, dt_col: str, amount_col: str, asof_dt: pd.Timestamp) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=float)
    sku_df = df[df["sku_norm"] == sku]
    if sku_df.empty:
        return pd.Series(dtype=float)
    asof_utc = asof_dt.tz_localize("UTC") if asof_dt.tzinfo is None else asof_dt.tz_convert("UTC")
    for days in (30, 90):
        cutoff = asof_utc - pd.Timedelta(days=days)
        win = sku_df[(sku_df[dt_col] >= cutoff) & (sku_df[dt_col] <= asof_utc)][amount_col].dropna()
        if not win.empty:
            return win
    return sku_df[amount_col].dropna()


def _select_refund_window(df: pd.DataFrame, sku: str, asof_dt: pd.Timestamp) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    sku_df = df[df["sku_norm"] == sku]
    if sku_df.empty:
        return pd.DataFrame()
    asof_date = asof_dt.tz_localize(None).normalize() if asof_dt.tzinfo is not None else asof_dt.normalize()
    for days in (30, 90):
        cutoff = asof_date - pd.Timedelta(days=days)
        win = sku_df[(sku_df["asof_dt"] >= cutoff) & (sku_df["asof_dt"] <= asof_date)]
        if not win.empty:
            return win
    return sku_df


def _refund_rate_context(rates: pd.DataFrame, sku: str) -> dict[str, object]:
    context: dict[str, object] = {
        "refund_unit_rate_30d": "",
        "refund_unit_rate_90d": "",
        "refund_units_30d": "",
        "sales_units_30d": "",
        "expected_refund_cost_per_unit_gbp": 0.0,
        "refund_cost_basis": "",
        "refund_proof_state": "not_yet_proven",
        "refund_sample_confidence": "no_refund_rate_proof",
    }
    if rates.empty:
        return context
    sku_rows = rates[rates["sku_norm"] == sku]
    if sku_rows.empty:
        return context

    def pick(window_days: int, basis: str = "sale_cohort") -> pd.Series | None:
        basis_series = _series_or_default(sku_rows, "basis", "").astype(str)
        rows = sku_rows[(sku_rows["window_days_num"] == window_days) & (basis_series == basis)]
        if rows.empty and basis == "sale_cohort":
            rows = sku_rows[(sku_rows["window_days_num"] == window_days) & (basis_series == "posted_window")]
        if rows.empty:
            return None
        return rows.iloc[0]

    row30 = pick(30)
    row90 = pick(90)
    chosen = row90 if row90 is not None and float(row90.get("sales_units_num") or 0.0) > 0 else row30
    if row30 is not None:
        context["refund_unit_rate_30d"] = round(float(row30.get("refund_unit_rate_num") or 0.0), 6)
        context["refund_units_30d"] = round(float(row30.get("refund_units_num") or 0.0), 6)
        context["sales_units_30d"] = round(float(row30.get("sales_units_num") or 0.0), 6)
    if row90 is not None:
        context["refund_unit_rate_90d"] = round(float(row90.get("refund_unit_rate_num") or 0.0), 6)
    if chosen is not None:
        context["expected_refund_cost_per_unit_gbp"] = round(float(chosen.get("expected_refund_cost_num") or 0.0), 6)
        context["refund_cost_basis"] = f"{chosen.get('basis', '')}_{int(float(chosen.get('window_days_num') or 0))}d"
        context["refund_proof_state"] = str(chosen.get("proof_state", "") or "not_yet_proven")
        context["refund_sample_confidence"] = str(chosen.get("sample_confidence", "") or "no_refund_rate_proof")
    return context


def _with_aligned_unit_truth(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    velocity_units = _to_num(_series_or_default(summary, "units_sold", np.nan))
    roi_units = _to_num(_series_or_default(summary, "units_sold_roi", np.nan))
    use_roi = roi_units.notna()
    truth_units = roi_units.where(use_roi, velocity_units)
    source = pd.Series(
        np.where(use_roi, "roi", np.where(velocity_units.notna(), "velocity", "")),
        index=summary.index,
        dtype=object,
    )

    summary["units_sold_velocity_30d"] = velocity_units.round(4)
    summary["units_sold_truth_30d"] = truth_units.round(4)
    summary["units_sold_source"] = source
    summary["units_sold"] = truth_units.round(4)
    return summary


def _yes_no_from_reorder(value: object) -> str:
    text = str(value or "").strip().lower()
    return "yes" if text in {"yes", "true", "1", "y"} else "no"


def _blankish(value: object) -> bool:
    text = str(value or "").strip().lower()
    return text in {"", "nan", "none", "null"}


def _numeric_value(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _has_restock_context(row: pd.Series) -> bool:
    for col in ("available", "total_quantity", "days_of_stock_left", "reorder_flag", "suggested_reorder_qty"):
        if not _blankish(row.get(col, "")):
            return True
    return False


def _missing_roi_reason_parts(row: pd.Series) -> tuple[str, list[str]]:
    profit_confidence = str(row.get("profit_confidence", "") or "").strip().lower()
    units_source = str(row.get("units_sold_source", "") or "").strip().lower()
    sales_truth_state = str(row.get("sales_truth_state", "") or "").strip().lower()
    price_confidence = str(row.get("latest_price_confidence", "") or "").strip().lower()
    refund_state = str(row.get("refund_proof_state", "") or "").strip().lower()
    refund_confidence = str(row.get("refund_sample_confidence", "") or "").strip().lower()
    units_truth = _numeric_value(row.get("units_sold_truth_30d", row.get("units_sold", "")))
    missing_cogs = _numeric_value(row.get("missing_cogs_units", 0))
    missing_fx = _numeric_value(row.get("fx_missing_units", 0))
    token_cost_missing = _blankish(row.get("current_token_cost_gbp", ""))
    break_even_missing = _blankish(row.get("break_even_price_gbp", ""))

    details: list[str] = []
    if profit_confidence == "profit_clean" and units_source == "roi":
        primary = "roi_clean"
    elif profit_confidence == "profit_limited" or missing_cogs > 0 or missing_fx > 0 or (units_source == "roi" and token_cost_missing):
        primary = "missing_cogs_or_fx"
    elif units_source == "velocity" and (pd.isna(units_truth) or units_truth <= 0) and _has_restock_context(row):
        primary = "stock_only_no_sales_window"
    elif units_source == "velocity" and not pd.isna(units_truth) and units_truth > 0:
        primary = "velocity_only_sales_truth"
    elif sales_truth_state in {"not_available", ""} or pd.isna(units_truth) or units_truth <= 0:
        primary = "no_recent_sales_truth"
    else:
        primary = "not_available"

    if price_confidence == "listing_price_unproven":
        details.append("missing_current_price_proof")
    if refund_state in WEAK_REFUND_PROOF_STATES or refund_confidence in WEAK_REFUND_CONFIDENCE_STATES:
        details.append("missing_refund_proof")
    if break_even_missing and primary not in {"missing_cogs_or_fx", "stock_only_no_sales_window", "no_recent_sales_truth"}:
        details.append("missing_fee_proof")
    if primary != "roi_clean" and primary not in details:
        details.insert(0, primary)
    return primary, list(dict.fromkeys(details))


def _row_missing_reasons(row: pd.Series) -> str:
    reasons: list[str] = []
    primary, details = _missing_roi_reason_parts(row)
    if primary != "roi_clean":
        reasons.extend(details or [primary])
    return ";".join(reasons)


def _restock_price_is_missing(row: pd.Series) -> bool:
    price_confidence = str(row.get("latest_price_confidence", "") or "").strip().lower()
    return price_confidence in {"", "listing_price_unproven", "not_verified"}


def _restock_refund_is_weak(row: pd.Series) -> bool:
    refund_state = str(row.get("refund_proof_state", "") or "").strip().lower()
    refund_confidence = str(row.get("refund_sample_confidence", "") or "").strip().lower()
    return refund_state in WEAK_REFUND_PROOF_STATES or refund_confidence in WEAK_REFUND_CONFIDENCE_STATES


def _restock_missing_proof(row: pd.Series) -> list[str]:
    reasons: list[str] = []
    stock_signal = str(row.get("stock_signal", "") or "").strip().lower()
    profit_confidence = str(row.get("profit_confidence", "") or "").strip().lower()
    missing_roi_reason = str(row.get("missing_roi_reason", "") or "").strip().lower()
    missing_roi_detail = str(row.get("missing_roi_reason_detail", "") or "").strip().lower()
    b_money_state = str(row.get("b_money_confidence_state", "") or "").strip().lower()
    b_live_safe = str(row.get("b_bridge_values_safe_for_live_roi", "") or "").strip()

    if stock_signal != "yes":
        reasons.append("no_stock_signal")
    if missing_roi_reason != "roi_clean" or profit_confidence != "profit_clean":
        reasons.append("missing_roi")
        if missing_roi_reason in {"missing_cogs_or_fx", "missing_fee_proof"}:
            reasons.append(missing_roi_reason)
        elif missing_roi_reason in {"stock_only_no_sales_window", "velocity_only_sales_truth", "no_recent_sales_truth"}:
            reasons.append(missing_roi_reason)
        for part in missing_roi_detail.split(";"):
            part = part.strip()
            if part:
                reasons.append(part)
    if _restock_price_is_missing(row):
        reasons.append("missing_current_price")
    if _restock_refund_is_weak(row):
        reasons.append("weak_refund_proof")
    if b_money_state != "api_backed_safe" or b_live_safe != "1":
        reasons.append("bridge_labelled_money")
    return list(dict.fromkeys(reasons))


def _restock_decision(row: pd.Series) -> tuple[str, str, str]:
    stock_signal = str(row.get("stock_signal", "") or "").strip().lower()
    profit_confidence = str(row.get("profit_confidence", "") or "").strip().lower()
    missing_roi_reason = str(row.get("missing_roi_reason", "") or "").strip().lower()
    b_money_state = str(row.get("b_money_confidence_state", "") or "").strip().lower()
    b_live_safe = str(row.get("b_bridge_values_safe_for_live_roi", "") or "").strip()
    missing_proof = _restock_missing_proof(row)

    if stock_signal != "yes":
        return "not_applicable_no_stock_signal", "not_applicable", ";".join(missing_proof)
    if profit_confidence != "profit_clean" or missing_roi_reason != "roi_clean":
        if missing_roi_reason in {"missing_cogs_or_fx", "missing_fee_proof"} or "missing_cogs_or_fx" in missing_proof or "missing_fee_proof" in missing_proof:
            return "blocked_missing_profit_inputs", "blocked", ";".join(missing_proof)
        return "blocked_missing_roi", "blocked", ";".join(missing_proof)
    if _restock_price_is_missing(row):
        return "blocked_missing_current_price", "blocked", ";".join(missing_proof)
    if _restock_refund_is_weak(row):
        return "blocked_weak_refund_proof", "blocked", ";".join(missing_proof)
    if b_money_state != "api_backed_safe" or b_live_safe != "1":
        return "warning_bridge_labelled_money", "warning", ";".join(missing_proof)
    return "business_ready_clean", "clean", ""


def _with_confidence_fields(summary: pd.DataFrame, b_money_context: dict[str, str] | None = None) -> pd.DataFrame:
    b_money_context = b_money_context or {
        "b_money_confidence_state": "api_backed_safe",
        "b_bridge_values_safe_for_live_roi": "1",
    }
    if summary.empty:
        for col in [
            "profit_confidence",
            "sales_truth_state",
            "stock_signal",
            "restock_business_ready",
            "latest_price_confidence",
            "b_money_confidence_state",
            "b_bridge_values_safe_for_live_roi",
            "restock_decision_state",
            "restock_readiness_confidence",
            "restock_missing_proof",
            "restock_evidence_role",
            "missing_reason",
            "missing_roi_reason",
            "missing_roi_reason_detail",
        ]:
            if col not in summary.columns:
                summary[col] = ""
        return summary

    units_source = _series_or_default(summary, "units_sold_source", "").astype(str).str.strip().str.lower()
    units_roi = _to_num(_series_or_default(summary, "units_sold_roi", np.nan))
    profit = _to_num(_series_or_default(summary, "profit_exvat_gbp", np.nan))
    roi = _to_num(_series_or_default(summary, "roi_exvat", np.nan))
    missing_cogs = _to_num(_series_or_default(summary, "missing_cogs_units", 0.0)).fillna(0.0)
    missing_fx = _to_num(_series_or_default(summary, "fx_missing_units", 0.0)).fillna(0.0)
    has_profit_proof = units_source.eq("roi") & units_roi.fillna(0).gt(0) & (profit.notna() | roi.notna())
    clean_profit = has_profit_proof & missing_cogs.le(0) & missing_fx.le(0)
    limited_profit = has_profit_proof & ~clean_profit

    summary["profit_confidence"] = np.select(
        [clean_profit, limited_profit, units_source.eq("velocity")],
        ["profit_clean", "profit_limited", "profit_missing"],
        default="profit_missing",
    )
    summary["sales_truth_state"] = np.select(
        [units_source.eq("roi"), units_source.eq("velocity")],
        ["roi_sales_truth", "velocity_only"],
        default="not_available",
    )
    summary["stock_signal"] = _series_or_default(summary, "reorder_flag", "").map(_yes_no_from_reorder)
    if "latest_price_confidence" not in summary.columns:
        summary["latest_price_confidence"] = "listing_price_current"
    summary["b_money_confidence_state"] = str(b_money_context.get("b_money_confidence_state") or "not_verified")
    summary["b_bridge_values_safe_for_live_roi"] = str(b_money_context.get("b_bridge_values_safe_for_live_roi") or "0")
    reason_parts = summary.apply(_missing_roi_reason_parts, axis=1)
    summary["missing_roi_reason"] = [primary for primary, _details in reason_parts]
    summary["missing_roi_reason_detail"] = [";".join(details) for _primary, details in reason_parts]
    summary["missing_reason"] = summary.apply(_row_missing_reasons, axis=1)
    restock_decisions = summary.apply(_restock_decision, axis=1)
    summary["restock_decision_state"] = [state for state, _confidence, _proof in restock_decisions]
    summary["restock_readiness_confidence"] = [confidence for _state, confidence, _proof in restock_decisions]
    summary["restock_missing_proof"] = [proof for _state, _confidence, proof in restock_decisions]
    summary["restock_evidence_role"] = RESTOCK_EVIDENCE_ROLE
    summary["restock_business_ready"] = np.where(
        summary["restock_decision_state"].eq("business_ready_clean"),
        "yes",
        "no",
    )
    return summary


def main() -> None:
    vel = _read_csv(VELOCITY)
    roi = _read_csv(ROI)
    restock = _read_csv(RESTOCK)

    if vel.empty and roi.empty and restock.empty:
        empty = _with_confidence_fields(pd.DataFrame(columns=["sku"]))
        output = _write_summary_output(empty)
        print({"status": "success", "rows": 0, "snapshot": str(OUT_SUMMARY), **output})
        return

    if not vel.empty:
        vel = vel[vel.get("window_days", "").astype(str) == "30"]

    summary = vel
    if not roi.empty:
        summary = summary.merge(roi, on="sku", how="outer", suffixes=("", "_roi"))
    if not restock.empty:
        summary = summary.merge(restock, on="sku", how="outer", suffixes=("", "_restock"))

    summary = _with_aligned_unit_truth(summary)

    buy_box_fallback_used = 0

    if not summary.empty:
        summary["sku_norm"] = summary.get("sku", "").map(_norm_sku)
        summary["asof_dt"] = pd.to_datetime(
            _series_or_default(summary, "asof_date", ""),
            errors="coerce",
        )
        if "asof_date_roi" in summary.columns:
            asof_roi = pd.to_datetime(summary["asof_date_roi"], errors="coerce")
            summary["asof_dt"] = summary["asof_dt"].fillna(asof_roi)
        if "asof_date_restock" in summary.columns:
            asof_restock = pd.to_datetime(summary["asof_date_restock"], errors="coerce")
            summary["asof_dt"] = summary["asof_dt"].fillna(asof_restock)
        if summary["asof_dt"].isna().all():
            summary["asof_dt"] = pd.Timestamp.utcnow().normalize()

        projected_cols = [
            "current_token_cost_gbp",
            "break_even_price_gbp",
            "expected_refund_cost_per_unit_gbp",
            "refund_unit_rate_30d",
            "refund_unit_rate_90d",
            "refund_units_30d",
            "sales_units_30d",
            "refund_cost_basis",
            "refund_proof_state",
            "refund_sample_confidence",
            "roi_at_our_price_pct",
            "roi_at_buy_box_price_pct",
            "latest_price_confidence",
        ]
        for col in projected_cols:
            if col not in summary.columns:
                summary[col] = ""

        token = _prepare_token_df()
        fin = _prepare_fin_df()
        refund = _prepare_refund_df()
        refund_rates = _prepare_refund_rate_df()
        latest_our, latest_buy_box, latest_lowest_fba, hist_last_our, hist_last_buy_box = _prepare_listing_maps()
        units_roi_num = _to_num(_series_or_default(summary, "units_sold_roi", 0.0)).fillna(0.0)

        for idx, row in summary.iterrows():
            sku = row.get("sku_norm", "")
            if not sku:
                continue
            asof_dt = row.get("asof_dt")
            if pd.isna(asof_dt):
                asof_dt = pd.Timestamp.utcnow().normalize()

            token_cost = np.nan
            vat_rate = np.nan
            if not token.empty:
                token_cost_series = _select_window(token, sku, "order_dt", "cogs_exvat_num", asof_dt)
                if not token_cost_series.empty:
                    token_cost = float(token_cost_series.mean())
                vat_series = _select_window(token, sku, "order_dt", "vat_rate_pct_num", asof_dt)
                if not vat_series.empty:
                    vat_rate = float(vat_series.median())
            if pd.isna(vat_rate):
                vat_rate = 20.0

            refund_unit_cost = 0.0
            refund_context = _refund_rate_context(refund_rates, sku)
            refund_rows = _select_refund_window(refund, sku, asof_dt)
            units = float(units_roi_num.iloc[idx]) if idx in units_roi_num.index else 0.0
            if refund_context["refund_cost_basis"]:
                refund_unit_cost = float(refund_context["expected_refund_cost_per_unit_gbp"] or 0.0)
            elif units > 0 and not refund_rows.empty:
                refund_total = float(refund_rows["refund_amount_num"].abs().sum()) + float(refund_rows["adjustment_amount_num"].abs().sum())
                refund_unit_cost = refund_total / units
                refund_context["expected_refund_cost_per_unit_gbp"] = round(float(refund_unit_cost), 6)
                refund_context["refund_cost_basis"] = "legacy_refund_adjustment_history"
                refund_context["refund_proof_state"] = "not_yet_proven"
                refund_context["refund_sample_confidence"] = "legacy_history_not_manager_proven"

            fee_drag = np.nan
            if not fin.empty:
                fba_s = _select_window(fin, sku, "date_dt", "fba_fee_exvat_num", asof_dt)
                comm_s = _select_window(fin, sku, "date_dt", "commission_exvat_num", asof_dt)
                dig_s = _select_window(fin, sku, "date_dt", "digital_fee_exvat_num", asof_dt)
                if not fba_s.empty and not comm_s.empty and not dig_s.empty:
                    fee_drag = -(float(fba_s.mean()) + float(comm_s.mean()) + float(dig_s.mean()))

            if pd.isna(fee_drag) and not fin.empty:
                asof_utc = asof_dt.tz_localize("UTC") if asof_dt.tzinfo is None else asof_dt.tz_convert("UTC")
                selected = pd.DataFrame()
                for days in (30, 90):
                    cutoff = asof_utc - pd.Timedelta(days=days)
                    win = fin[(fin["date_dt"] >= cutoff) & (fin["date_dt"] <= asof_utc)]
                    if not win.empty:
                        selected = win
                        break
                if selected.empty:
                    selected = fin
                if not selected.empty:
                    fee_drag = -(
                        float(selected["fba_fee_exvat_num"].mean()) +
                        float(selected["commission_exvat_num"].mean()) +
                        float(selected["digital_fee_exvat_num"].mean())
                    )

            break_even = np.nan
            if pd.notna(token_cost) and pd.notna(fee_drag):
                break_even = float(token_cost) + float(fee_drag) + float(refund_unit_cost)

            price_confidence = "listing_price_current"
            our_price = latest_our.get(sku, np.nan)
            if pd.isna(our_price):
                our_price = hist_last_our.get(sku, np.nan)
                if pd.notna(our_price):
                    price_confidence = "listing_price_fallback"
            buy_box_used = latest_buy_box.get(sku, np.nan)
            if pd.isna(buy_box_used):
                buy_box_used = hist_last_buy_box.get(sku, np.nan)
                if pd.notna(buy_box_used):
                    price_confidence = "listing_price_fallback"
                    buy_box_fallback_used += 1
            if pd.isna(buy_box_used):
                buy_box_used = latest_lowest_fba.get(sku, np.nan)
                if pd.notna(buy_box_used):
                    price_confidence = "listing_price_fallback"
                    buy_box_fallback_used += 1
            if pd.isna(buy_box_used):
                buy_box_used = our_price
                if pd.notna(buy_box_used):
                    price_confidence = "listing_price_fallback"
                    buy_box_fallback_used += 1
            if pd.isna(our_price) and pd.isna(buy_box_used):
                price_confidence = "listing_price_unproven"

            roi_our = np.nan
            roi_buy_box = np.nan
            vat_factor = 1.0 + (float(vat_rate) / 100.0)
            if vat_factor <= 0:
                vat_factor = 1.2
            if pd.notna(token_cost) and token_cost > 0 and pd.notna(break_even):
                if pd.notna(our_price):
                    our_exvat = float(our_price) / vat_factor
                    roi_our = ((our_exvat - float(break_even)) / float(token_cost)) * 100.0
                if pd.notna(buy_box_used):
                    buy_exvat = float(buy_box_used) / vat_factor
                    roi_buy_box = ((buy_exvat - float(break_even)) / float(token_cost)) * 100.0

            summary.at[idx, "current_token_cost_gbp"] = "" if pd.isna(token_cost) else round(float(token_cost), 6)
            summary.at[idx, "expected_refund_cost_per_unit_gbp"] = round(float(refund_unit_cost), 6)
            summary.at[idx, "refund_unit_rate_30d"] = refund_context["refund_unit_rate_30d"]
            summary.at[idx, "refund_unit_rate_90d"] = refund_context["refund_unit_rate_90d"]
            summary.at[idx, "refund_units_30d"] = refund_context["refund_units_30d"]
            summary.at[idx, "sales_units_30d"] = refund_context["sales_units_30d"]
            summary.at[idx, "refund_cost_basis"] = refund_context["refund_cost_basis"]
            summary.at[idx, "refund_proof_state"] = refund_context["refund_proof_state"]
            summary.at[idx, "refund_sample_confidence"] = refund_context["refund_sample_confidence"]
            summary.at[idx, "break_even_price_gbp"] = "" if pd.isna(break_even) else round(float(break_even), 6)
            summary.at[idx, "roi_at_our_price_pct"] = "" if pd.isna(roi_our) else round(float(roi_our), 6)
            summary.at[idx, "roi_at_buy_box_price_pct"] = "" if pd.isna(roi_buy_box) else round(float(roi_buy_box), 6)
            summary.at[idx, "latest_price_confidence"] = price_confidence

        profit = _to_num(_series_or_default(summary, "profit_exvat_gbp"))
        units_roi = _to_num(_series_or_default(summary, "units_sold_roi"))
        units_roi = units_roi.where(units_roi > 0)
        profit_per_unit = profit / units_roi
        summary["profit_per_unit_gbp_30d"] = profit_per_unit.round(6)

        if "velocity_30d" in summary.columns:
            velocity_used = _to_num(_series_or_default(summary, "velocity_30d"))
        else:
            velocity_used = _to_num(_series_or_default(summary, "velocity_units_per_day"))
        value_velocity = profit_per_unit * velocity_used
        summary["value_velocity_gbp_per_day"] = value_velocity.round(6)
        summary = _with_confidence_fields(summary, _b_money_context())
        summary = summary.drop(columns=["sku_norm", "asof_dt"], errors="ignore")
    else:
        summary = _with_confidence_fields(summary, _b_money_context())

    output = _write_summary_output(summary)
    print({
        "status": "success",
        "rows": len(summary),
        "snapshot": str(OUT_SUMMARY),
        "buy_box_fallback_used": int(buy_box_fallback_used),
        **output,
    })


if __name__ == "__main__":
    main()

