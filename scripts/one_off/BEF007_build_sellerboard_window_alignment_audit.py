from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
DEFAULT_OUTPUT_DIR = OUT / "analysis_reports"

DEFAULT_ORDER_ITEMS_PATH = (
    ROOT
    / "reference"
    / "DRJ_Hardware_Dashboard_Order_Items_23_03_2026-21_04_2026_(2026_04_22_10_05_26_439).csv"
)
DEFAULT_PRODUCTS_PATH = (
    ROOT
    / "reference"
    / "DRJ_Hardware_Dashboard_Products_23_03_2026-21_04_2026_(2026_04_22_09_41_46_840).csv"
)

DEFAULT_WINDOW_START = "2026-03-23"
DEFAULT_WINDOW_END = "2026-04-21"
DEFAULT_FOCUS_ASIN = "B07L6H9GZ2"

LEVEL2_PATH = OUT / "financial_events_level2.csv"
LEVEL3_PATH = OUT / "financial_events_level3_official.csv"
ORDER_MASTER_PATH = OUT / "order_master.csv"
ORDER_LEDGER_PATH = OUT / "order_ledger_fx.csv"
DAILY_TRUTH_PATH = OUT / "sku_daily_sales_truth_latest.csv"
ACTUALS_PATH = DEFAULT_OUTPUT_DIR / "f_sales_history_learning_actuals_latest.csv"
VETTING_SUMMARY_LATEST_PATH = DEFAULT_OUTPUT_DIR / "f_stocked_sku_vetting_summary_latest.csv"


@dataclass(frozen=True)
class SellerboardWindowAlignmentAuditResult:
    observed_utc: str
    window_start: str
    window_end: str
    sku_audit_df: pd.DataFrame
    order_proof_df: pd.DataFrame
    summary_df: pd.DataFrame
    sku_audit_path: Path
    sku_audit_latest_path: Path
    order_proof_path: Path
    order_proof_latest_path: Path
    summary_path: Path
    summary_latest_path: Path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_timestamp_slug(observed_utc: str) -> str:
    dt = datetime.strptime(observed_utc, "%Y-%m-%dT%H:%M:%SZ")
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _to_num_series(series: pd.Series) -> pd.Series:
    text = (
        series.astype(str)
        .str.replace("\xa0", "", regex=False)
        .str.replace("£", "", regex=False)
        .str.replace(",", "", regex=False)
    )
    return pd.to_numeric(text, errors="coerce").fillna(0.0)


def _read_csv(path: Path, *, sep: str = ",") -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str, sep=sep, encoding="utf-8", encoding_errors="replace").fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _parse_sellerboard_order_items(path: Path, *, window_start: str, window_end: str) -> pd.DataFrame:
    df = _read_csv(path, sep=";")
    if df.empty:
        return pd.DataFrame(
            columns=[
                "asin",
                "sku",
                "order_id",
                "order_date",
                "order_status",
                "sellerboard_units",
                "sellerboard_sales_gross",
            ]
        )
    required = ["Order number", "Order date", "ASIN", "SKU", "Units", "Sales"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Sellerboard order-items file missing required column: {col}")

    work = pd.DataFrame()
    work["asin"] = df["ASIN"].map(_normalize_key)
    work["sku"] = df["SKU"].map(_normalize_key)
    work["order_number"] = df["Order number"].map(_normalize_text)
    work["order_id"] = work["order_number"].str.split(" / ").str[0].str.strip()
    work["order_status"] = work["order_number"].str.split(" / ").str[1].fillna("").str.strip()
    work["order_date"] = pd.to_datetime(df["Order date"], format="%d.%m.%Y", errors="coerce").dt.strftime("%Y-%m-%d")
    work["sellerboard_units"] = _to_num_series(df["Units"])
    work["sellerboard_sales_gross"] = _to_num_series(df["Sales"])
    work = work[
        (work["asin"] != "")
        & (work["sku"] != "")
        & (work["order_date"] >= window_start)
        & (work["order_date"] <= window_end)
    ].copy()
    return work.reset_index(drop=True)


def _parse_sellerboard_products(path: Path) -> pd.DataFrame:
    df = _read_csv(path, sep=";")
    if df.empty:
        return pd.DataFrame(columns=["asin", "sku", "sellerboard_products_units", "sellerboard_products_sales_gross"])
    required = ["ASIN", "SKU", "Units", "Sales"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Sellerboard products file missing required column: {col}")

    work = pd.DataFrame()
    work["asin"] = df["ASIN"].map(_normalize_key)
    work["sku"] = df["SKU"].map(_normalize_key)
    work["sellerboard_products_units"] = _to_num_series(df["Units"])
    work["sellerboard_products_sales_gross"] = _to_num_series(df["Sales"])
    work = work[(work["asin"] != "") & (work["sku"] != "")].copy()
    return work.reset_index(drop=True)


def _aggregate_local_level2(*, window_start: str, window_end: str) -> pd.DataFrame:
    df = _read_csv(LEVEL2_PATH)
    if df.empty:
        return pd.DataFrame(columns=["sku", "level2_units", "level2_revenue_exvat"])
    if "Date" not in df.columns or "SKU" not in df.columns:
        return pd.DataFrame(columns=["sku", "level2_units", "level2_revenue_exvat"])

    work = pd.DataFrame()
    work["date"] = pd.to_datetime(df["Date"], errors="coerce", utc=True).dt.strftime("%Y-%m-%d")
    work["sku"] = df["SKU"].map(_normalize_key)
    work["units"] = _to_num_series(df.get("Quantity Ordered", pd.Series([""] * len(df))))
    work["revenue"] = (
        _to_num_series(df.get("Price_ExVAT", pd.Series([""] * len(df))))
        + _to_num_series(df.get("Shipping_ExVAT", pd.Series([""] * len(df))))
        + _to_num_series(df.get("Gift_ExVAT", pd.Series([""] * len(df))))
        + _to_num_series(df.get("Promotion_ExVAT", pd.Series([""] * len(df))))
    )
    work = work[(work["sku"] != "") & (work["date"] >= window_start) & (work["date"] <= window_end)].copy()
    if work.empty:
        return pd.DataFrame(columns=["sku", "level2_units", "level2_revenue_exvat"])

    return (
        work.groupby("sku", as_index=False)[["units", "revenue"]]
        .sum()
        .rename(columns={"units": "level2_units", "revenue": "level2_revenue_exvat"})
    )


def _aggregate_local_order_master(*, window_start: str, window_end: str) -> pd.DataFrame:
    df = _read_csv(ORDER_MASTER_PATH)
    if df.empty:
        return pd.DataFrame(columns=["sku", "order_master_units", "order_master_revenue_exvat"])
    if "Date" not in df.columns or "SKU" not in df.columns:
        return pd.DataFrame(columns=["sku", "order_master_units", "order_master_revenue_exvat"])

    work = pd.DataFrame()
    work["date"] = pd.to_datetime(df["Date"], errors="coerce", utc=True).dt.strftime("%Y-%m-%d")
    work["sku"] = df["SKU"].map(_normalize_key)
    work["units"] = _to_num_series(df.get("Quantity Ordered", pd.Series([""] * len(df))))
    work["revenue"] = (
        _to_num_series(df.get("Price_ExVAT", pd.Series([""] * len(df))))
        + _to_num_series(df.get("Shipping_ExVAT", pd.Series([""] * len(df))))
        + _to_num_series(df.get("Gift_ExVAT", pd.Series([""] * len(df))))
        + _to_num_series(df.get("Promotion_ExVAT", pd.Series([""] * len(df))))
    )
    work = work[(work["sku"] != "") & (work["date"] >= window_start) & (work["date"] <= window_end)].copy()
    if work.empty:
        return pd.DataFrame(columns=["sku", "order_master_units", "order_master_revenue_exvat"])

    return (
        work.groupby("sku", as_index=False)[["units", "revenue"]]
        .sum()
        .rename(columns={"units": "order_master_units", "revenue": "order_master_revenue_exvat"})
    )


def _aggregate_local_order_ledger(*, window_start: str, window_end: str) -> pd.DataFrame:
    df = _read_csv(ORDER_LEDGER_PATH)
    if df.empty:
        return pd.DataFrame(columns=["sku", "order_ledger_units", "order_ledger_revenue_exvat_gbp"])

    date_col = "date" if "date" in df.columns else "Date" if "Date" in df.columns else ""
    sku_col = "SKU" if "SKU" in df.columns else "sku" if "sku" in df.columns else ""
    if date_col == "" or sku_col == "":
        return pd.DataFrame(columns=["sku", "order_ledger_units", "order_ledger_revenue_exvat_gbp"])

    work = pd.DataFrame()
    work["date"] = pd.to_datetime(df[date_col], errors="coerce", utc=True).dt.strftime("%Y-%m-%d")
    work["sku"] = df[sku_col].map(_normalize_key)
    work["units"] = _to_num_series(df.get("Quantity Ordered", pd.Series([""] * len(df))))
    work["revenue"] = (
        _to_num_series(df.get("Price_ExVAT_GBP", pd.Series([""] * len(df))))
        + _to_num_series(df.get("Shipping_ExVAT_GBP", pd.Series([""] * len(df))))
        + _to_num_series(df.get("Gift_ExVAT_GBP", pd.Series([""] * len(df))))
        + _to_num_series(df.get("Promotion_ExVAT_GBP", pd.Series([""] * len(df))))
    )
    work = work[(work["sku"] != "") & (work["date"] >= window_start) & (work["date"] <= window_end)].copy()
    if work.empty:
        return pd.DataFrame(columns=["sku", "order_ledger_units", "order_ledger_revenue_exvat_gbp"])

    return (
        work.groupby("sku", as_index=False)[["units", "revenue"]]
        .sum()
        .rename(columns={"units": "order_ledger_units", "revenue": "order_ledger_revenue_exvat_gbp"})
    )


def _aggregate_local_daily_truth(*, window_start: str, window_end: str) -> pd.DataFrame:
    df = _read_csv(DAILY_TRUTH_PATH)
    if df.empty:
        return pd.DataFrame(columns=["sku", "daily_truth_units", "daily_truth_revenue_gbp"])
    if "sku" not in df.columns or "date" not in df.columns:
        return pd.DataFrame(columns=["sku", "daily_truth_units", "daily_truth_revenue_gbp"])

    work = pd.DataFrame()
    work["sku"] = df["sku"].map(_normalize_key)
    work["date"] = df["date"].map(_normalize_text)
    work["units"] = _to_num_series(df.get("units", pd.Series([""] * len(df))))
    work["revenue"] = _to_num_series(df.get("revenue_gbp", pd.Series([""] * len(df))))
    work = work[(work["sku"] != "") & (work["date"] >= window_start) & (work["date"] <= window_end)].copy()
    if work.empty:
        return pd.DataFrame(columns=["sku", "daily_truth_units", "daily_truth_revenue_gbp"])

    return (
        work.groupby("sku", as_index=False)[["units", "revenue"]]
        .sum()
        .rename(columns={"units": "daily_truth_units", "revenue": "daily_truth_revenue_gbp"})
    )


def _actuals_units_by_asin() -> pd.DataFrame:
    df = _read_csv(ACTUALS_PATH)
    if df.empty:
        return pd.DataFrame(columns=["asin", "actuals_units_30d", "actuals_profit_30d_gbp", "actuals_source_state_30d"])
    if "asin" not in df.columns:
        return pd.DataFrame(columns=["asin", "actuals_units_30d", "actuals_profit_30d_gbp", "actuals_source_state_30d"])

    work = df.copy()
    work["asin"] = work["asin"].map(_normalize_key)
    if "actuals_basis" in work.columns:
        work = work[work["actuals_basis"].map(_normalize_text).str.lower() == "operational_baseline"].copy()
    if work.empty:
        return pd.DataFrame(columns=["asin", "actuals_units_30d", "actuals_profit_30d_gbp", "actuals_source_state_30d"])

    if "actuals_observed_utc" in work.columns:
        work["_ts"] = pd.to_datetime(work["actuals_observed_utc"], errors="coerce", utc=True)
        work = work.sort_values("_ts", ascending=False, kind="stable")
    work = work.drop_duplicates(subset=["asin"], keep="first")
    out = pd.DataFrame()
    out["asin"] = work["asin"]
    out["actuals_units_30d"] = _to_num_series(work.get("actual_units_30d", pd.Series([""] * len(work))))
    out["actuals_profit_30d_gbp"] = _to_num_series(work.get("actual_profit_30d_gbp", pd.Series([""] * len(work))))
    out["actuals_source_state_30d"] = work.get("actuals_source_state_30d", pd.Series([""] * len(work))).map(_normalize_text)
    return out.reset_index(drop=True)


def _eq(left: float, right: float, tol: float = 1e-6) -> bool:
    return abs(float(left) - float(right)) <= tol


def _classify_row(row: pd.Series) -> str:
    sb_units = float(row.get("sellerboard_order_item_units", 0.0))
    level2_units = float(row.get("level2_units", 0.0))
    order_master_units = float(row.get("order_master_units", 0.0))
    daily_truth_units = float(row.get("daily_truth_units", 0.0))
    sb_sales_gross = float(row.get("sellerboard_order_item_sales_gross", 0.0))
    daily_truth_revenue = float(row.get("daily_truth_revenue_gbp", 0.0))

    level2_match = _eq(sb_units, level2_units)
    order_master_match = _eq(sb_units, order_master_units)
    daily_truth_match = _eq(sb_units, daily_truth_units)
    units_nonzero = sb_units > 0
    value_gap = abs(sb_sales_gross - daily_truth_revenue) > 0.5

    if not units_nonzero and _eq(level2_units, 0.0) and _eq(order_master_units, 0.0) and _eq(daily_truth_units, 0.0):
        return "no_window_sales"
    if level2_match and daily_truth_match and not order_master_match:
        return "recovered_from_level2_gap"
    if level2_match and order_master_match and daily_truth_match and value_gap:
        return "units_aligned_value_basis_gap"
    if level2_match and order_master_match and not daily_truth_match:
        return "daily_truth_window_or_filter_gap"
    if not level2_match:
        return "upstream_level2_vs_sellerboard_mismatch"
    if level2_match and (not order_master_match) and (not daily_truth_match):
        return "post_level2_truth_shortfall"
    if level2_match and order_master_match and daily_truth_match:
        return "aligned_exact"
    return "other"


def _build_order_proof(
    *,
    sellerboard_items: pd.DataFrame,
    focus_asin: str,
    focus_sku: str,
    window_start: str,
    window_end: str,
) -> pd.DataFrame:
    sb_focus = sellerboard_items[
        sellerboard_items["asin"].eq(focus_asin) & sellerboard_items["sku"].eq(focus_sku)
    ].copy()
    if sb_focus.empty:
        return pd.DataFrame(
            columns=[
                "window_start",
                "window_end",
                "asin",
                "sku",
                "order_id",
                "order_date",
                "sellerboard_status",
                "sellerboard_units",
                "sellerboard_sales_gross",
                "has_level2",
                "has_level3",
                "has_order_master",
                "has_order_ledger",
            ]
        )

    def _order_set(path: Path, *, date_col: str, sku_col: str, order_col: str) -> set[str]:
        df = _read_csv(path)
        if df.empty:
            return set()
        if date_col not in df.columns or sku_col not in df.columns or order_col not in df.columns:
            return set()
        work = pd.DataFrame()
        work["date"] = pd.to_datetime(df[date_col], errors="coerce", utc=True).dt.strftime("%Y-%m-%d")
        work["sku"] = df[sku_col].map(_normalize_key)
        work["order_id"] = df[order_col].map(_normalize_text)
        qty_col = "Quantity Ordered" if "Quantity Ordered" in df.columns else ""
        if qty_col:
            work["qty"] = _to_num_series(df[qty_col])
            work = work[work["qty"] > 0].copy()
        work = work[
            (work["sku"] == focus_sku)
            & (work["date"] >= window_start)
            & (work["date"] <= window_end)
            & (work["order_id"] != "")
        ].copy()
        return set(work["order_id"].tolist())

    level2_orders = _order_set(LEVEL2_PATH, date_col="Date", sku_col="SKU", order_col="Order ID")
    level3_orders = _order_set(LEVEL3_PATH, date_col="Date", sku_col="SKU", order_col="Order ID")
    order_master_orders = _order_set(ORDER_MASTER_PATH, date_col="Date", sku_col="SKU", order_col="Order ID")
    ledger_orders = _order_set(ORDER_LEDGER_PATH, date_col="date", sku_col="SKU", order_col="Order ID")

    proof = pd.DataFrame()
    proof["window_start"] = window_start
    proof["window_end"] = window_end
    proof["asin"] = focus_asin
    proof["sku"] = focus_sku
    proof["order_id"] = sb_focus["order_id"].map(_normalize_text)
    proof["order_date"] = sb_focus["order_date"].map(_normalize_text)
    proof["sellerboard_status"] = sb_focus["order_status"].map(_normalize_text)
    proof["sellerboard_units"] = sb_focus["sellerboard_units"]
    proof["sellerboard_sales_gross"] = sb_focus["sellerboard_sales_gross"]
    proof["has_level2"] = proof["order_id"].map(lambda value: value in level2_orders)
    proof["has_level3"] = proof["order_id"].map(lambda value: value in level3_orders)
    proof["has_order_master"] = proof["order_id"].map(lambda value: value in order_master_orders)
    proof["has_order_ledger"] = proof["order_id"].map(lambda value: value in ledger_orders)
    return proof.sort_values(["order_date", "order_id"], kind="stable").reset_index(drop=True)


def _vetting_counts() -> dict[str, str]:
    if not VETTING_SUMMARY_LATEST_PATH.exists():
        return {}
    df = _read_csv(VETTING_SUMMARY_LATEST_PATH)
    if df.empty or "metric" not in df.columns:
        return {}
    return {
        _normalize_text(row.get("metric", "")): _normalize_text(row.get("value", ""))
        for _, row in df.iterrows()
        if _normalize_text(row.get("metric", "")) != ""
    }


def build_sellerboard_window_alignment_audit(
    *,
    order_items_path: Path = DEFAULT_ORDER_ITEMS_PATH,
    products_path: Path = DEFAULT_PRODUCTS_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    window_start: str = DEFAULT_WINDOW_START,
    window_end: str = DEFAULT_WINDOW_END,
    focus_asin: str = DEFAULT_FOCUS_ASIN,
    observed_utc: str | None = None,
) -> SellerboardWindowAlignmentAuditResult:
    snapshot_utc = observed_utc or _utc_now_iso()
    ts_slug = _to_timestamp_slug(snapshot_utc)
    output_dir.mkdir(parents=True, exist_ok=True)

    sku_audit_path = output_dir / f"bef_sellerboard_window_alignment_sku_audit_{ts_slug}.csv"
    sku_audit_latest_path = output_dir / "bef_sellerboard_window_alignment_sku_audit_latest.csv"
    order_proof_path = output_dir / f"bef_sellerboard_window_alignment_order_proof_{ts_slug}.csv"
    order_proof_latest_path = output_dir / "bef_sellerboard_window_alignment_order_proof_latest.csv"
    summary_path = output_dir / f"bef_sellerboard_window_alignment_summary_{ts_slug}.csv"
    summary_latest_path = output_dir / "bef_sellerboard_window_alignment_summary_latest.csv"

    sb_items = _parse_sellerboard_order_items(order_items_path, window_start=window_start, window_end=window_end)
    sb_products = _parse_sellerboard_products(products_path)

    sb_items_agg = (
        sb_items.groupby(["asin", "sku"], as_index=False)[["sellerboard_units", "sellerboard_sales_gross"]]
        .sum()
        .rename(
            columns={
                "sellerboard_units": "sellerboard_order_item_units",
                "sellerboard_sales_gross": "sellerboard_order_item_sales_gross",
            }
        )
    ) if not sb_items.empty else pd.DataFrame(columns=["asin", "sku", "sellerboard_order_item_units", "sellerboard_order_item_sales_gross"])

    sb_products_agg = sb_products.copy()

    sku_universe = pd.concat(
        [
            sb_items_agg[["asin", "sku"]],
            sb_products_agg[["asin", "sku"]],
        ],
        ignore_index=True,
    ).drop_duplicates()
    if sku_universe.empty:
        sku_universe = pd.DataFrame(columns=["asin", "sku"])

    local_level2 = _aggregate_local_level2(window_start=window_start, window_end=window_end)
    local_order_master = _aggregate_local_order_master(window_start=window_start, window_end=window_end)
    local_order_ledger = _aggregate_local_order_ledger(window_start=window_start, window_end=window_end)
    local_daily_truth = _aggregate_local_daily_truth(window_start=window_start, window_end=window_end)
    actuals_by_asin = _actuals_units_by_asin()

    sku_audit = sku_universe.merge(sb_items_agg, on=["asin", "sku"], how="left")
    sku_audit = sku_audit.merge(sb_products_agg, on=["asin", "sku"], how="left")
    sku_audit = sku_audit.merge(local_level2, on="sku", how="left")
    sku_audit = sku_audit.merge(local_order_master, on="sku", how="left")
    sku_audit = sku_audit.merge(local_order_ledger, on="sku", how="left")
    sku_audit = sku_audit.merge(local_daily_truth, on="sku", how="left")
    sku_audit = sku_audit.merge(actuals_by_asin, on="asin", how="left")

    numeric_cols = [
        "sellerboard_order_item_units",
        "sellerboard_order_item_sales_gross",
        "sellerboard_products_units",
        "sellerboard_products_sales_gross",
        "level2_units",
        "level2_revenue_exvat",
        "order_master_units",
        "order_master_revenue_exvat",
        "order_ledger_units",
        "order_ledger_revenue_exvat_gbp",
        "daily_truth_units",
        "daily_truth_revenue_gbp",
        "actuals_units_30d",
        "actuals_profit_30d_gbp",
    ]
    for col in numeric_cols:
        if col not in sku_audit.columns:
            sku_audit[col] = 0.0
        sku_audit[col] = pd.to_numeric(sku_audit[col], errors="coerce").fillna(0.0)

    sku_audit["window_start"] = window_start
    sku_audit["window_end"] = window_end
    sku_audit["observed_utc"] = snapshot_utc
    sku_audit["units_delta_level2_vs_sellerboard"] = sku_audit["level2_units"] - sku_audit["sellerboard_order_item_units"]
    sku_audit["units_delta_order_master_vs_sellerboard"] = sku_audit["order_master_units"] - sku_audit["sellerboard_order_item_units"]
    sku_audit["units_delta_daily_truth_vs_sellerboard"] = sku_audit["daily_truth_units"] - sku_audit["sellerboard_order_item_units"]
    sku_audit["sales_delta_daily_truth_vs_sellerboard"] = sku_audit["daily_truth_revenue_gbp"] - sku_audit["sellerboard_order_item_sales_gross"]
    sku_audit["discrepancy_class"] = sku_audit.apply(_classify_row, axis=1)
    sku_audit = sku_audit.sort_values(["sellerboard_order_item_units", "asin", "sku"], ascending=[False, True, True], kind="stable")
    sku_audit = sku_audit.reset_index(drop=True)

    focus_asin_norm = _normalize_key(focus_asin)
    focus_row = sku_audit[sku_audit["asin"] == focus_asin_norm].head(1)
    focus_sku = _normalize_key(focus_row.iloc[0]["sku"]) if not focus_row.empty else ""
    order_proof = _build_order_proof(
        sellerboard_items=sb_items,
        focus_asin=focus_asin_norm,
        focus_sku=focus_sku,
        window_start=window_start,
        window_end=window_end,
    )

    class_counts = sku_audit["discrepancy_class"].value_counts().to_dict() if not sku_audit.empty else {}
    exact_level2 = int((sku_audit["units_delta_level2_vs_sellerboard"].abs() <= 1e-6).sum()) if not sku_audit.empty else 0
    exact_order_master = int((sku_audit["units_delta_order_master_vs_sellerboard"].abs() <= 1e-6).sum()) if not sku_audit.empty else 0
    exact_daily_truth = int((sku_audit["units_delta_daily_truth_vs_sellerboard"].abs() <= 1e-6).sum()) if not sku_audit.empty else 0
    vetting = _vetting_counts()

    summary_rows: list[dict[str, str]] = [
        {"observed_utc": snapshot_utc, "metric": "window_start", "value": window_start},
        {"observed_utc": snapshot_utc, "metric": "window_end", "value": window_end},
        {"observed_utc": snapshot_utc, "metric": "sku_rows_total", "value": str(int(len(sku_audit.index)))},
        {"observed_utc": snapshot_utc, "metric": "sellerboard_units_total", "value": str(float(sku_audit["sellerboard_order_item_units"].sum()))},
        {"observed_utc": snapshot_utc, "metric": "level2_units_total", "value": str(float(sku_audit["level2_units"].sum()))},
        {"observed_utc": snapshot_utc, "metric": "order_master_units_total", "value": str(float(sku_audit["order_master_units"].sum()))},
        {"observed_utc": snapshot_utc, "metric": "daily_truth_units_total", "value": str(float(sku_audit["daily_truth_units"].sum()))},
        {"observed_utc": snapshot_utc, "metric": "exact_match_level2_count", "value": str(exact_level2)},
        {"observed_utc": snapshot_utc, "metric": "exact_match_order_master_count", "value": str(exact_order_master)},
        {"observed_utc": snapshot_utc, "metric": "exact_match_daily_truth_count", "value": str(exact_daily_truth)},
    ]
    for class_name, count in sorted(class_counts.items()):
        summary_rows.append({"observed_utc": snapshot_utc, "metric": f"class::{class_name}", "value": str(int(count))})

    if not focus_row.empty:
        row = focus_row.iloc[0]
        summary_rows.extend(
            [
                {"observed_utc": snapshot_utc, "metric": "focus_asin", "value": focus_asin_norm},
                {"observed_utc": snapshot_utc, "metric": "focus_sku", "value": str(row.get("sku", ""))},
                {"observed_utc": snapshot_utc, "metric": "focus_sellerboard_units", "value": str(float(row.get("sellerboard_order_item_units", 0.0)))},
                {"observed_utc": snapshot_utc, "metric": "focus_level2_units", "value": str(float(row.get("level2_units", 0.0)))},
                {"observed_utc": snapshot_utc, "metric": "focus_order_master_units", "value": str(float(row.get("order_master_units", 0.0)))},
                {"observed_utc": snapshot_utc, "metric": "focus_daily_truth_units", "value": str(float(row.get("daily_truth_units", 0.0)))},
                {"observed_utc": snapshot_utc, "metric": "focus_discrepancy_class", "value": str(row.get("discrepancy_class", ""))},
            ]
        )

    for metric in ["current_test_buy_rows", "current_watch_rows", "current_reject_rows", "current_ready_for_live_test_rows"]:
        if metric in vetting:
            summary_rows.append({"observed_utc": snapshot_utc, "metric": f"vetting::{metric}", "value": vetting[metric]})

    summary_df = pd.DataFrame(summary_rows, columns=["observed_utc", "metric", "value"])

    sku_audit.to_csv(sku_audit_path, index=False)
    sku_audit.to_csv(sku_audit_latest_path, index=False)
    order_proof.to_csv(order_proof_path, index=False)
    order_proof.to_csv(order_proof_latest_path, index=False)
    summary_df.to_csv(summary_path, index=False)
    summary_df.to_csv(summary_latest_path, index=False)

    report = {
        "status": "success",
        "observed_utc": snapshot_utc,
        "window_start": window_start,
        "window_end": window_end,
        "sku_rows": int(len(sku_audit.index)),
        "sellerboard_units_total": float(sku_audit["sellerboard_order_item_units"].sum()) if not sku_audit.empty else 0.0,
        "daily_truth_units_total": float(sku_audit["daily_truth_units"].sum()) if not sku_audit.empty else 0.0,
        "focus_asin": focus_asin_norm,
        "focus_units": float(focus_row.iloc[0]["daily_truth_units"]) if not focus_row.empty else 0.0,
        "focus_class": _normalize_text(focus_row.iloc[0]["discrepancy_class"]) if not focus_row.empty else "",
        "class_counts": class_counts,
        "sku_audit_latest": str(sku_audit_latest_path),
        "order_proof_latest": str(order_proof_latest_path),
        "summary_latest": str(summary_latest_path),
    }
    print(json.dumps(report))

    return SellerboardWindowAlignmentAuditResult(
        observed_utc=snapshot_utc,
        window_start=window_start,
        window_end=window_end,
        sku_audit_df=sku_audit,
        order_proof_df=order_proof,
        summary_df=summary_df,
        sku_audit_path=sku_audit_path,
        sku_audit_latest_path=sku_audit_latest_path,
        order_proof_path=order_proof_path,
        order_proof_latest_path=order_proof_latest_path,
        summary_path=summary_path,
        summary_latest_path=summary_latest_path,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build fixed-window Sellerboard vs local alignment audit.")
    parser.add_argument("--order-items-path", default=str(DEFAULT_ORDER_ITEMS_PATH))
    parser.add_argument("--products-path", default=str(DEFAULT_PRODUCTS_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--window-start", default=DEFAULT_WINDOW_START)
    parser.add_argument("--window-end", default=DEFAULT_WINDOW_END)
    parser.add_argument("--focus-asin", default=DEFAULT_FOCUS_ASIN)
    parser.add_argument("--observed-utc", default="")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_sellerboard_window_alignment_audit(
        order_items_path=Path(args.order_items_path),
        products_path=Path(args.products_path),
        output_dir=Path(args.output_dir),
        window_start=args.window_start,
        window_end=args.window_end,
        focus_asin=args.focus_asin,
        observed_utc=args.observed_utc or None,
    )


if __name__ == "__main__":
    main()

