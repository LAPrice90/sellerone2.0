from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np

OUT = Path("out")
VELOCITY = OUT / "sku_sales_velocity.csv"
ROI = OUT / "sku_roi_snapshot.csv"
RESTOCK = OUT / "sku_restock_signals.csv"
OUT_SUMMARY = OUT / "sku_performance_summary.csv"
TOKEN_COGS = OUT / "token_cogs_ledger.csv"
REFUND_HISTORY = OUT / "refund_adjustment_history.csv"
FIN_L3 = OUT / "financial_events_level3_official.csv"
LISTING_HISTORY = OUT / "listing_offer_history.csv"


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _series_or_default(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col in df.columns:
        return df[col]
    return pd.Series([default] * len(df), index=df.index)


def _norm_sku(value: object) -> str:
    return str(value or "").strip().upper()


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


def main() -> None:
    vel = _read_csv(VELOCITY)
    roi = _read_csv(ROI)
    restock = _read_csv(RESTOCK)

    if vel.empty and roi.empty and restock.empty:
        OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(OUT_SUMMARY, index=False)
        print({"status": "success", "rows": 0, "snapshot": str(OUT_SUMMARY)})
        return

    if not vel.empty:
        vel = vel[vel.get("window_days", "").astype(str) == "30"]

    summary = vel
    if not roi.empty:
        summary = summary.merge(roi, on="sku", how="outer", suffixes=("", "_roi"))
    if not restock.empty:
        summary = summary.merge(restock, on="sku", how="outer", suffixes=("", "_restock"))

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
            "roi_at_our_price_pct",
            "roi_at_buy_box_price_pct",
        ]
        for col in projected_cols:
            if col not in summary.columns:
                summary[col] = ""

        token = _prepare_token_df()
        fin = _prepare_fin_df()
        refund = _prepare_refund_df()
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
            refund_rows = _select_refund_window(refund, sku, asof_dt)
            units = float(units_roi_num.iloc[idx]) if idx in units_roi_num.index else 0.0
            if units > 0 and not refund_rows.empty:
                refund_total = float(refund_rows["refund_amount_num"].abs().sum()) + float(refund_rows["adjustment_amount_num"].abs().sum())
                refund_unit_cost = refund_total / units

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

            our_price = latest_our.get(sku, np.nan)
            if pd.isna(our_price):
                our_price = hist_last_our.get(sku, np.nan)
            buy_box_used = latest_buy_box.get(sku, np.nan)
            if pd.isna(buy_box_used):
                buy_box_used = hist_last_buy_box.get(sku, np.nan)
                if pd.notna(buy_box_used):
                    buy_box_fallback_used += 1
            if pd.isna(buy_box_used):
                buy_box_used = latest_lowest_fba.get(sku, np.nan)
                if pd.notna(buy_box_used):
                    buy_box_fallback_used += 1
            if pd.isna(buy_box_used):
                buy_box_used = our_price
                if pd.notna(buy_box_used):
                    buy_box_fallback_used += 1

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
            summary.at[idx, "break_even_price_gbp"] = "" if pd.isna(break_even) else round(float(break_even), 6)
            summary.at[idx, "roi_at_our_price_pct"] = "" if pd.isna(roi_our) else round(float(roi_our), 6)
            summary.at[idx, "roi_at_buy_box_price_pct"] = "" if pd.isna(roi_buy_box) else round(float(roi_buy_box), 6)

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
        summary = summary.drop(columns=["sku_norm", "asof_dt"], errors="ignore")

    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUT_SUMMARY, index=False)
    print({
        "status": "success",
        "rows": len(summary),
        "snapshot": str(OUT_SUMMARY),
        "buy_box_fallback_used": int(buy_box_fallback_used),
    })


if __name__ == "__main__":
    main()
