"""
Convert manual comparison amounts to GBP using order_ledger_fx rates.

Updates:
- out/amazon_manual_vs_system_comparison.csv (adds manual_*_gbp, recalculates deltas)
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd


COMP_PATH = Path("out/amazon_manual_vs_system_comparison.csv")
LEDGER_FX = Path("out/order_ledger_fx.csv")
MANUAL_PATH = Path("out/amazon_profitandloss_2026_01_manual.csv")


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def main() -> None:
    if not COMP_PATH.exists():
        raise FileNotFoundError(f"Missing {COMP_PATH}")
    if not LEDGER_FX.exists():
        raise FileNotFoundError(f"Missing {LEDGER_FX}")

    comp = pd.read_csv(COMP_PATH, dtype=str).fillna("")
    if MANUAL_PATH.exists():
        manual = pd.read_csv(MANUAL_PATH, dtype=str).fillna("")
        manual = manual[["Order ID", "Shipping_Total", "Shipping_VAT", "Shipping_ExVAT"]].drop_duplicates()
        comp = comp.merge(manual, on="Order ID", how="left", suffixes=("", "_manual"))
        for src, dst in {
            "Shipping_Total": "manual_shipping_total",
            "Shipping_VAT": "manual_shipping_vat",
            "Shipping_ExVAT": "manual_shipping_exvat",
        }.items():
            src_col = src if src in comp.columns else f"{src}_manual"
            if src_col in comp.columns:
                override = _to_num(comp[src_col])
                comp[dst] = override.where(override.ne(0), _to_num(comp.get(dst)))
        comp.drop(columns=[c for c in comp.columns if c.endswith("_manual") or c in {"Shipping_Total", "Shipping_VAT", "Shipping_ExVAT"}], inplace=True, errors="ignore")
    fx = pd.read_csv(LEDGER_FX, dtype=str).fillna("")

    fx = fx[["Order ID", "date", "currency_code", "fx_rate_to_gbp"]].drop_duplicates()
    fx["fx_rate_to_gbp"] = _to_num(fx["fx_rate_to_gbp"])

    # Drop any prior FX/GBP columns to keep the output stable across reruns.
    drop_cols = [
        c
        for c in comp.columns
        if c.startswith("manual_fx_")
        or c.endswith("_gbp")
        or "_gbp_" in c
        or c in {"fx_rate_to_gbp"}
        or c.endswith(".1")
        or c.endswith(".2")
    ]
    comp.drop(columns=drop_cols, inplace=True, errors="ignore")

    comp = comp.merge(fx, on="Order ID", how="left", suffixes=("", "_fx"))
    comp.rename(
        columns={"date": "manual_fx_date", "currency_code": "manual_fx_currency"},
        inplace=True,
    )

    manual_cols: List[str] = [c for c in comp.columns if c.startswith("manual_") and c not in ["manual_currency", "manual_fx_date", "manual_fx_currency", "manual_fx_rate_to_gbp"]]
    sys_cols = {c.replace("manual_", "sys_") for c in manual_cols}

    comp["manual_fx_rate_to_gbp"] = _to_num(comp.get("fx_rate_to_gbp"))
    comp.drop(columns=["fx_rate_to_gbp"], inplace=True, errors="ignore")

    for col in manual_cols:
        num = _to_num(comp[col])
        gbp_col = f"{col}_gbp"
        # default: manual in GBP stays the same
        comp[gbp_col] = num
        # convert non-GBP manual using ledger FX rate
        mask = comp["manual_currency"].ne("GBP") & comp["manual_fx_rate_to_gbp"].gt(0)
        comp.loc[mask, gbp_col] = (num[mask] * comp.loc[mask, "manual_fx_rate_to_gbp"]).round(6)

        sys_col = col.replace("manual_", "sys_")
        delta_col = col.replace("manual_", "delta_manual_")
        if sys_col in comp.columns and delta_col in comp.columns:
            comp[delta_col] = (comp[gbp_col] - _to_num(comp[sys_col])).round(6)

    # Align manual price to system gross (exclude promo from Price_* by adding it back).
    for base_col in ["manual_price_total", "manual_price_vat", "manual_price_exvat"]:
        promo_col = base_col.replace("manual_price", "manual_promo")
        base_gbp = f"{base_col}_gbp"
        promo_gbp = f"{promo_col}_gbp"
        if base_gbp in comp.columns and promo_gbp in comp.columns:
            comp[base_gbp] = (comp[base_gbp] - _to_num(comp[promo_gbp])).round(6)
            delta_col = base_col.replace("manual_", "delta_manual_")
            sys_col = base_col.replace("manual_", "sys_")
            if sys_col in comp.columns and delta_col in comp.columns:
                comp[delta_col] = (comp[base_gbp] - _to_num(comp[sys_col])).round(6)

    comp.to_csv(COMP_PATH, index=False)
    print({"status": "success", "rows": len(comp), "out": str(COMP_PATH)})


if __name__ == "__main__":
    main()
