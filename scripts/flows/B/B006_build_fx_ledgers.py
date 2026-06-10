"""
Build GBP-converted ledgers for automation.

Outputs:
- out/order_ledger_fx.csv (from Order_Master, purchase-date rates)
- out/financial_ledger_fx.csv (from Level 3 raw, posted-date rates)
"""

from __future__ import annotations

import os
from datetime import datetime
from io import StringIO
from pathlib import Path
import sys
from typing import Dict, List, Tuple

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from scripts.core.safe_file_writes import safe_to_csv
    from scripts.core.storage import StorageConfig, connect_store, parse_storage_mode, replace_table_from_dataframe
except ModuleNotFoundError:
    from core.safe_file_writes import safe_to_csv
    from core.storage import StorageConfig, connect_store, parse_storage_mode, replace_table_from_dataframe


ORDER_MASTER = Path("out/order_master.csv")
FIN_L3_RAW = Path("out/financial_events_level3_raw.csv")
FX_RATES = Path("out/fx_rates_daily.csv")

OUT_ORDER_FX = Path("out/order_ledger_fx.csv")
OUT_FIN_FX = Path("out/financial_ledger_fx.csv")
SQL_TABLE_ORDER_LEDGER_FX = "b_order_ledger_fx"
SQL_TABLE_FINANCIAL_LEDGER_FX = "b_financial_ledger_fx"
SQL_TABLE_FX_RATES = "b_fx_rates_daily"

FX_BASE = os.environ.get("FX_BASE", "GBP")
FX_SOURCE = os.environ.get("FX_SOURCE", "ECB")
FX_API_URL = "https://api.frankfurter.app"
FX_API_URL_FALLBACK = "https://api.exchangerate.host"
FX_API_URL_FALLBACK_LATEST = "https://open.er-api.com/v6/latest/EUR"
FX_STALE_DAYS = int(os.environ.get("FX_STALE_DAYS", "14"))


def _write_output_frame(df: pd.DataFrame, path: Path, sql_table: str) -> dict[str, object]:
    mode = parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE", "csv"))
    sql_rows = 0

    def write_csv() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        safe_to_csv(df, path, index=False)

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


def _date_key(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True).dt.strftime("%Y-%m-%d")


def _load_fx_table() -> pd.DataFrame:
    if not FX_RATES.exists():
        return pd.DataFrame(columns=["date", "currency", "rate_to_gbp", "source", "fx_date_used"])
    try:
        return pd.read_csv(FX_RATES, dtype=str)
    except Exception:
        return pd.DataFrame(columns=["date", "currency", "rate_to_gbp", "source", "fx_date_used"])


def _fetch_fx_timeseries(start_date: str, end_date: str, symbols: List[str]) -> pd.DataFrame:
    params = {
        "from": "EUR",
        "to": ",".join(sorted(set(symbols))),
    }
    url = f"{FX_API_URL}/{start_date}..{end_date}"
    resp = requests.get(url, params=params, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"FX download failed: {resp.status_code} {resp.text}")
    payload = resp.json() or {}
    rates = payload.get("rates") or {}
    if not rates:
        raise RuntimeError("FX rates payload empty")
    rows = []
    for d, vals in rates.items():
        row = {"Date": d}
        if isinstance(vals, dict):
            row.update(vals)
        rows.append(row)
    return pd.DataFrame(rows)


def _fetch_fx_latest_fallback(symbols: List[str]) -> Dict[str, float]:
    resp = requests.get(FX_API_URL_FALLBACK_LATEST, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"FX fallback latest failed: {resp.status_code} {resp.text}")
    payload = resp.json() or {}
    rates = payload.get("rates") or {}
    if not rates:
        raise RuntimeError("FX fallback latest rates payload empty")
    out: Dict[str, float] = {}
    for cur in symbols:
        if cur in rates:
            try:
                out[cur] = float(rates[cur])
            except Exception:
                continue
    return out


def _build_rates_for_dates(dates: List[str], currencies: List[str]) -> pd.DataFrame:
    if FX_BASE != "GBP":
        raise RuntimeError(f"FX_BASE={FX_BASE} not supported yet")
    if not dates or not currencies:
        return pd.DataFrame(columns=["date", "currency", "rate_to_gbp", "source", "fx_date_used"])
    df_ecb = _fetch_fx_timeseries(min(dates), max(dates), ["GBP"] + currencies)
    missing = [c for c in ["GBP"] + currencies if c not in df_ecb.columns]
    if missing:
        latest_rates = _fetch_fx_latest_fallback(missing)
        if latest_rates:
            for cur, val in latest_rates.items():
                df_ecb[cur] = val
    if "Date" not in df_ecb.columns or "GBP" not in df_ecb.columns:
        raise RuntimeError("FX data missing Date/GBP columns")
    df_ecb["Date"] = df_ecb["Date"].astype(str)
    df_ecb = df_ecb.sort_values(by="Date")
    available_dates = df_ecb["Date"].tolist()

    def _find_fx_date(d: str) -> str:
        if d in df_ecb["Date"].values:
            return d
        prior = [ad for ad in available_dates if ad <= d]
        return prior[-1] if prior else ""

    rows = []
    for d in dates:
        fx_date = _find_fx_date(d)
        if not fx_date:
            continue
        row = df_ecb[df_ecb["Date"] == fx_date].iloc[0]
        try:
            gbp_rate = float(row["GBP"])
        except Exception:
            continue
        for cur in currencies:
            if cur == "GBP":
                rate_to_gbp = 1.0
            else:
                if cur == "EUR":
                    cur_rate = 1.0
                else:
                    if cur not in df_ecb.columns:
                        continue
                    try:
                        cur_rate = float(row[cur])
                    except Exception:
                        continue
                rate_to_gbp = gbp_rate / cur_rate
            rows.append(
                {
                    "date": d,
                    "currency": cur,
                    "rate_to_gbp": f"{rate_to_gbp:.8f}",
                    "source": FX_SOURCE,
                    "fx_date_used": fx_date,
                }
            )
    return pd.DataFrame(rows)


def _ensure_fx_rates(dates: List[str], currencies: List[str]) -> pd.DataFrame:
    fx = _load_fx_table()
    if not fx.empty:
        fx_dates = pd.to_datetime(fx.get("date"), errors="coerce")
        fx_used = pd.to_datetime(fx.get("fx_date_used"), errors="coerce")
        stale_mask = (fx_dates.notna() & fx_used.notna()) & ((fx_dates - fx_used).dt.days > FX_STALE_DAYS)
        fx = fx[~stale_mask]
    fx["date"] = fx.get("date", "").astype(str)
    fx["currency"] = fx.get("currency", "").astype(str)
    existing = set(zip(fx["date"], fx["currency"]))
    need = [(d, c) for d in dates for c in currencies if (d, c) not in existing]
    if not need:
        return fx
    add = _build_rates_for_dates(sorted({d for d, _ in need}), sorted({c for _, c in need}))
    if add.empty:
        return fx
    fx = pd.concat([fx, add], ignore_index=True)
    _write_output_frame(fx, FX_RATES, SQL_TABLE_FX_RATES)
    return fx


def _rate_lookup(fx: pd.DataFrame) -> Dict[Tuple[str, str], float]:
    lookup: Dict[Tuple[str, str], float] = {}
    if fx.empty:
        return lookup
    for _, r in fx.iterrows():
        d = str(r.get("date") or "")
        c = str(r.get("currency") or "")
        try:
            rate = float(r.get("rate_to_gbp") or "")
        except Exception:
            continue
        if d and c:
            lookup[(d, c)] = rate
    return lookup


def build_order_ledger_fx() -> None:
    if not ORDER_MASTER.exists():
        raise RuntimeError("missing out/order_master.csv")
    df = pd.read_csv(ORDER_MASTER, dtype=str)
    if df.empty:
        OUT_ORDER_FX.write_text("")
        return
    if "currency_code" not in df.columns:
        raise RuntimeError("Order_Master missing currency_code column")
    df = df.copy()
    df["date"] = _date_key(df["Date"])
    df["currency_code"] = df["currency_code"].astype(str)
    currencies = {c for c in df["currency_code"].dropna().tolist() if c}
    if not currencies:
        OUT_ORDER_FX.write_text("")
        return

    date_list = sorted({d for d in df["date"].dropna().tolist() if d})
    cur_list = sorted(currencies)
    fx_lookup: Dict[Tuple[str, str], float] = {}
    gbp_only = cur_list == ["GBP"]
    if not gbp_only:
        fx = _ensure_fx_rates(date_list, cur_list)
        fx_lookup = _rate_lookup(fx)

    fx_cols = [
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
    ]
    for col in fx_cols:
        df[col] = pd.to_numeric(df.get(col), errors="coerce").fillna(0.0)
        df[f"{col}_GBP"] = 0.0

    df["fx_rate_to_gbp"] = ""
    for idx, row in df.iterrows():
        d = row.get("date") or ""
        c = row.get("currency_code") or ""
        rate = 1.0 if gbp_only else fx_lookup.get((d, c))
        if rate is None:
            continue
        df.at[idx, "fx_rate_to_gbp"] = f"{rate:.8f}"
        for col in fx_cols:
            df.at[idx, f"{col}_GBP"] = float(row.get(col) or 0.0) * rate

    _write_output_frame(df, OUT_ORDER_FX, SQL_TABLE_ORDER_LEDGER_FX)


def build_financial_ledger_fx() -> None:
    if not FIN_L3_RAW.exists():
        raise RuntimeError("missing out/financial_events_level3_raw.csv")
    df = pd.read_csv(FIN_L3_RAW, dtype=str)
    if df.empty:
        OUT_FIN_FX.write_text("")
        return
    df = df.copy()
    df["date"] = _date_key(df["posted_date"])
    df["currency"] = df.get("currency", "").astype(str)
    df["tax_currency"] = df.get("tax_currency", "").astype(str)
    currencies = {c for c in df["currency"].dropna().tolist() if c}
    if not currencies:
        OUT_FIN_FX.write_text("")
        return

    date_list = sorted({d for d in df["date"].dropna().tolist() if d})
    cur_list = sorted(currencies)
    fx = _ensure_fx_rates(date_list, cur_list)
    fx_lookup = _rate_lookup(fx)

    df["amount"] = pd.to_numeric(df.get("amount"), errors="coerce").fillna(0.0)
    df["tax_amount"] = pd.to_numeric(df.get("tax_amount"), errors="coerce").fillna(0.0)
    df["amount_gbp"] = 0.0
    df["tax_amount_gbp"] = 0.0
    df["fx_rate_to_gbp"] = ""

    for idx, row in df.iterrows():
        d = row.get("date") or ""
        c = row.get("currency") or ""
        rate = fx_lookup.get((d, c))
        if rate is None:
            continue
        df.at[idx, "fx_rate_to_gbp"] = f"{rate:.8f}"
        df.at[idx, "amount_gbp"] = float(row.get("amount") or 0.0) * rate
        df.at[idx, "tax_amount_gbp"] = float(row.get("tax_amount") or 0.0) * rate

    _write_output_frame(df, OUT_FIN_FX, SQL_TABLE_FINANCIAL_LEDGER_FX)


def _has_non_gbp_currency(path: Path, currency_col: str) -> bool:
    if not path.exists():
        return False
    try:
        df = pd.read_csv(path, dtype=str)
    except Exception:
        return False
    if df.empty or currency_col not in df.columns:
        return False
    currencies = {c for c in df[currency_col].dropna().tolist() if c}
    return any(c != "GBP" for c in currencies)


def main() -> None:
    # Always build order ledger; only build financial ledger when non-GBP appears.
    has_non_gbp = _has_non_gbp_currency(ORDER_MASTER, "currency_code") or _has_non_gbp_currency(FIN_L3_RAW, "currency")
    build_order_ledger_fx()
    if has_non_gbp:
        build_financial_ledger_fx()
    if FX_RATES.exists():
        fx = _load_fx_table()
        if not fx.empty:
            _write_output_frame(fx, FX_RATES, SQL_TABLE_FX_RATES)
    print(
        {
            "status": "success",
            "order_ledger_fx": str(OUT_ORDER_FX),
            "financial_ledger_fx": str(OUT_FIN_FX),
            "fx_rates": str(FX_RATES),
        }
    )


if __name__ == "__main__":
    main()

