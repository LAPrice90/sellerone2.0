from __future__ import annotations

from pathlib import Path
import pandas as pd

OUT = Path("out")
ORDERS = OUT / "order_master.csv"
OUT_ROI = OUT / "sku_roi_snapshot.csv"
OUT_ROI_UK = OUT / "sku_roi_snapshot_uk.csv"
OUT_ROI_NON_UK = OUT / "sku_roi_snapshot_non_uk.csv"
OUT_ROI_BY_COUNTRY = OUT / "sku_roi_snapshot_by_country.csv"
FX_RATES = OUT / "fx_rates_daily.csv"

WINDOW_DAYS = 30


def _read_csv(path: Path, usecols=None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, usecols=usecols).fillna("")


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)

def _load_fx_map() -> pd.Series:
    if not FX_RATES.exists():
        return pd.Series(dtype=float)
    try:
        fx = pd.read_csv(FX_RATES, dtype=str).fillna("")
    except Exception:
        return pd.Series(dtype=float)
    if fx.empty:
        return pd.Series(dtype=float)
    fx["rate_to_gbp"] = pd.to_numeric(fx.get("rate_to_gbp"), errors="coerce")
    return fx.set_index(["date", "currency"]).sort_index()["rate_to_gbp"]


def main() -> None:
    cols = [
        "Date",
        "SKU",
        "Quantity Ordered",
        "currency_code",
        "country_code",
        "Price_ExVAT",
        "Shipping_ExVAT",
        "Gift_ExVAT",
        "Promotion_ExVAT",
        "COGS_ExVAT",
        "FBA_Fee_ExVAT",
        "Commission_ExVAT",
        "Digital_Fee_ExVAT",
        "FixedClosingFee_ExVAT",
    ]
    orders = _read_csv(ORDERS, usecols=cols)
    if orders.empty:
        OUT_ROI.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(OUT_ROI, index=False)
        pd.DataFrame().to_csv(OUT_ROI_UK, index=False)
        pd.DataFrame().to_csv(OUT_ROI_NON_UK, index=False)
        pd.DataFrame().to_csv(OUT_ROI_BY_COUNTRY, index=False)
        print({"status": "success", "rows": 0, "snapshot": str(OUT_ROI)})
        return

    orders["Date"] = pd.to_datetime(orders["Date"], errors="coerce", utc=True)
    orders = orders.dropna(subset=["Date"])
    if orders.empty:
        OUT_ROI.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(OUT_ROI, index=False)
        pd.DataFrame().to_csv(OUT_ROI_UK, index=False)
        pd.DataFrame().to_csv(OUT_ROI_NON_UK, index=False)
        pd.DataFrame().to_csv(OUT_ROI_BY_COUNTRY, index=False)
        print({"status": "success", "rows": 0, "snapshot": str(OUT_ROI)})
        return

    max_dt = orders["Date"].max()
    start = max_dt - pd.Timedelta(days=WINDOW_DAYS)
    orders = orders[orders["Date"] >= start]

    fx_map = _load_fx_map()
    order_dates = orders["Date"].dt.strftime("%Y-%m-%d")
    order_ccy = orders.get("currency_code", "").astype(str).str.strip().str.upper()
    rate_to_gbp = [
        fx_map.get((d, c), None) if d and c else None
        for d, c in zip(order_dates, order_ccy)
    ]
    rate_to_gbp = pd.to_numeric(pd.Series(rate_to_gbp), errors="coerce")
    fx_missing = (order_ccy.ne("GBP")) & (rate_to_gbp.isna() | (rate_to_gbp <= 0))

    orders["qty"] = _to_num(orders.get("Quantity Ordered", 0))
    price = _to_num(orders.get("Price_ExVAT", 0))
    ship = _to_num(orders.get("Shipping_ExVAT", 0))
    gift = _to_num(orders.get("Gift_ExVAT", 0))
    promo = _to_num(orders.get("Promotion_ExVAT", 0))
    cogs = _to_num(orders.get("COGS_ExVAT", 0))
    fba_fee = _to_num(orders.get("FBA_Fee_ExVAT", 0))
    comm = _to_num(orders.get("Commission_ExVAT", 0))
    digital = _to_num(orders.get("Digital_Fee_ExVAT", 0))
    fixed = _to_num(orders.get("FixedClosingFee_ExVAT", 0))

    revenue_order = price + ship + gift + promo
    fee_order = fba_fee + comm + digital + fixed
    # Convert order-currency amounts to GBP (COGS already GBP).
    rate = rate_to_gbp.copy()
    rate = rate.where(rate.notna() & rate.gt(0), 1.0)
    revenue_gbp = revenue_order * rate
    fee_gbp = fee_order * rate
    orders["revenue_exvat"] = revenue_gbp
    orders["cost_exvat"] = cogs + fee_gbp
    orders["profit_exvat"] = orders["revenue_exvat"] - orders["cost_exvat"]
    orders["missing_cogs"] = (cogs <= 0).astype(int)
    orders["fx_missing"] = fx_missing.astype(int)

    def _summarize(df_in: pd.DataFrame, by_country: bool = False) -> list[dict]:
        rows = []
        if by_country:
            group_iter = df_in.groupby(["SKU", "country_code"], dropna=False)
        else:
            group_iter = df_in.groupby("SKU", dropna=False)
        for key, df_sku in group_iter:
            if by_country:
                sku = str(key[0]).strip()
                country = str(key[1]).strip()
            else:
                sku = str(key).strip()
                country = ""
            if not sku:
                continue
            units = float(df_sku["qty"].sum())
            revenue = float(df_sku["revenue_exvat"].sum())
            profit = float(df_sku["profit_exvat"].sum())
            missing_cogs_units = int((df_sku["missing_cogs"] * df_sku["qty"]).sum())
            fx_missing_units = int((df_sku["fx_missing"] * df_sku["qty"]).sum())
            if "COGS_ExVAT" in df_sku.columns:
                cogs_only = float(_to_num(df_sku["COGS_ExVAT"]).sum())
            else:
                cogs_only = 0.0
            cogs_base = abs(cogs_only)
            roi = (profit / cogs_base) if cogs_base > 0 else None
            row = {
                "sku": sku,
                "window_days": WINDOW_DAYS,
                "units_sold": round(units, 4),
                "revenue_exvat_gbp": round(revenue, 4),
                "cogs_exvat_gbp": round(cogs_only, 4),
                "profit_exvat_gbp": round(profit, 4),
                "roi_exvat": None if roi is None else round(roi, 6),
                "missing_cogs_units": missing_cogs_units,
                "fx_missing_units": fx_missing_units,
                "asof_date": max_dt.date().isoformat() if pd.notna(max_dt) else "",
            }
            if by_country:
                row["country_code"] = country
            rows.append(row)
        return rows

    rows_all = _summarize(orders, by_country=False)
    rows_uk = _summarize(orders[orders.get("country_code", "").astype(str).str.upper() == "GB"], by_country=False)
    rows_non_uk = _summarize(orders[orders.get("country_code", "").astype(str).str.upper() != "GB"], by_country=False)
    rows_by_country = _summarize(orders, by_country=True)

    OUT_ROI.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows_all).to_csv(OUT_ROI, index=False)
    pd.DataFrame(rows_uk).to_csv(OUT_ROI_UK, index=False)
    pd.DataFrame(rows_non_uk).to_csv(OUT_ROI_NON_UK, index=False)
    pd.DataFrame(rows_by_country).to_csv(OUT_ROI_BY_COUNTRY, index=False)
    print({"status": "success", "rows": len(rows_all), "snapshot": str(OUT_ROI)})


if __name__ == "__main__":
    main()

