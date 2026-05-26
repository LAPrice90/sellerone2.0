from __future__ import annotations

from pathlib import Path

import pandas as pd


WINDOW_DAYS = 30

TRUTH_ROW_COLUMNS = [
    "date",
    "date_dt",
    "order_key",
    "order_id",
    "sku",
    "country_code",
    "units",
    "revenue_gbp",
    "fees_gbp",
    "cogs_gbp",
    "profit_gbp",
    "fx_missing_units",
    "missing_cogs_units",
    "placeholder_cogs_units",
    "profit_excluded_rows",
    "placeholder_basis_source",
    "placeholder_basis_date",
    "source_state",
    "confidence_status",
    "basis",
    "notes",
]


def read_csv(path: Path, usecols: list[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str, usecols=usecols).fillna("")
    except ValueError:
        df = pd.read_csv(path, dtype=str).fillna("")
        if usecols is None:
            return df
        for col in usecols:
            if col not in df.columns:
                df[col] = ""
        return df[list(usecols)]


def to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def series_or_default(df: pd.DataFrame, col: str, default: object = "") -> pd.Series:
    if col in df.columns:
        return df[col]
    if isinstance(default, pd.Series):
        return default
    return pd.Series([default] * len(df), index=df.index)


def norm_sku(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.upper()


def _max_dt_from(path: Path, columns: list[str]) -> pd.Timestamp | None:
    df = read_csv(path, usecols=columns)
    if df.empty:
        return None
    for col in columns:
        if col not in df.columns:
            continue
        dt = pd.to_datetime(df[col], errors="coerce", utc=True).dropna()
        if not dt.empty:
            return dt.max()
    return None


def _resolve_window(
    *,
    order_ledger_fx_path: Path,
    financial_events_level2_path: Path,
    order_master_path: Path,
    window_days: int,
) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    candidates = [
        _max_dt_from(order_ledger_fx_path, ["date", "Date"]),
        _max_dt_from(financial_events_level2_path, ["Date"]),
        _max_dt_from(order_master_path, ["Date"]),
    ]
    active = [dt for dt in candidates if dt is not None]
    if not active:
        return None, None
    max_dt = max(active)
    return max_dt, max_dt - pd.Timedelta(days=window_days - 1)


def build_fx_lookup(fx_rates_path: Path) -> tuple[dict[tuple[str, str], float], dict[str, float]]:
    fx = read_csv(fx_rates_path, usecols=["date", "currency", "rate_to_gbp"])
    if fx.empty:
        return {}, {}
    fx["date"] = pd.to_datetime(fx["date"], errors="coerce").dt.date.astype(str)
    fx["currency"] = fx["currency"].astype(str).str.strip().str.upper()
    fx["rate_to_gbp_num"] = to_num(series_or_default(fx, "rate_to_gbp"))
    fx = fx[(fx["date"] != "NaT") & (fx["currency"] != "") & (fx["rate_to_gbp_num"] > 0)].copy()
    if fx.empty:
        return {}, {}

    exact: dict[tuple[str, str], float] = {}
    latest: dict[str, float] = {}
    for _, row in fx.iterrows():
        exact[(str(row["date"]), str(row["currency"]))] = float(row["rate_to_gbp_num"])
    fx = fx.sort_values(["currency", "date"], kind="stable")
    for _, row in fx.iterrows():
        latest[str(row["currency"])] = float(row["rate_to_gbp_num"])
    return exact, latest


def rate_to_gbp(
    day: str,
    currency: str,
    exact_fx: dict[tuple[str, str], float],
    latest_fx: dict[str, float],
) -> tuple[float, bool]:
    ccy = str(currency or "").strip().upper()
    if ccy in {"", "GBP"}:
        return 1.0, False
    key = (str(day), ccy)
    if key in exact_fx:
        return float(exact_fx[key]), False
    if ccy in latest_fx:
        return float(latest_fx[ccy]), False
    return 1.0, True


def load_marketplace_map(marketplace_participations_path: Path) -> dict[str, dict[str, str]]:
    df = read_csv(
        marketplace_participations_path,
        usecols=["marketplace_id", "country_code", "default_currency"],
    )
    if df.empty:
        return {}
    return {
        str(row.get("marketplace_id", "")).strip(): {
            "country_code": str(row.get("country_code", "")).strip().upper(),
            "currency_code": str(row.get("default_currency", "")).strip().upper(),
        }
        for _, row in df.iterrows()
        if str(row.get("marketplace_id", "")).strip()
    }


def _build_order_key(order_id: pd.Series, sku: pd.Series, date_text: pd.Series) -> pd.Series:
    order_part = order_id.astype(str).str.strip()
    fallback = date_text.astype(str).str.strip()
    base = order_part.where(order_part != "", fallback)
    return base + "|" + norm_sku(sku)


def _row_confidence(*, fx_missing_units: float, missing_cogs_units: float, placeholder_cogs_units: float) -> str:
    has_fx = float(fx_missing_units) > 0
    has_cogs = float(missing_cogs_units) > 0
    has_placeholder = float(placeholder_cogs_units) > 0
    if has_fx and has_placeholder:
        return "provisional_fx_and_cogs_placeholder"
    if has_placeholder:
        return "provisional_cogs_placeholder"
    if has_fx and has_cogs:
        return "provisional_fx_and_cogs_missing"
    if has_cogs:
        return "provisional_cogs_missing"
    if has_fx:
        return "provisional_fx_missing"
    return "provisional"


def _row_notes(
    *,
    basis: str,
    fx_missing_units: float,
    missing_cogs_units: float,
    placeholder_cogs_units: float,
    profit_excluded_rows: float,
    placeholder_basis_source: str = "",
    placeholder_basis_date: str = "",
    missing_token_flag: float = 0.0,
    missing_token_reason: str = "",
) -> str:
    parts = [f"basis={basis}"]
    if float(fx_missing_units) > 0:
        parts.append(f"fx_missing_units={int(round(float(fx_missing_units)))}")
    if float(missing_cogs_units) > 0:
        parts.append(f"cogs_missing_units={int(round(float(missing_cogs_units)))}")
    if float(placeholder_cogs_units) > 0:
        parts.append(f"cogs_placeholder_units={int(round(float(placeholder_cogs_units)))}")
        source_text = str(placeholder_basis_source or "").strip()
        date_text = str(placeholder_basis_date or "").strip()
        if source_text:
            parts.append(f"placeholder_source={source_text}")
        if date_text:
            parts.append(f"placeholder_date={date_text}")
    if float(missing_token_flag) > 0:
        parts.append("missing_token_flag=1")
    reason_text = str(missing_token_reason or "").strip()
    if reason_text:
        parts.append(f"missing_token_reason={reason_text}")
    if float(profit_excluded_rows) > 0:
        parts.append(f"profit_excluded_rows={int(round(float(profit_excluded_rows)))}")
    return ";".join(parts)


def _base_truth_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=TRUTH_ROW_COLUMNS)


def _load_order_meta(order_master_path: Path, start_dt: pd.Timestamp) -> pd.DataFrame:
    orders = read_csv(
        order_master_path,
        usecols=[
            "Date",
            "Order ID",
            "SKU",
            "currency_code",
            "country_code",
            "COGS_ExVAT",
            "COGS_Placeholder_Applied",
            "COGS_Basis_Source",
            "COGS_Basis_Date",
            "Missing_Token_Flag",
            "Missing_Token_Reason",
        ],
    )
    if orders.empty:
        return pd.DataFrame(
            columns=[
                "order_key",
                "currency_code",
                "country_code",
                "placeholder_cogs_gbp",
                "placeholder_basis_source",
                "placeholder_basis_date",
                "missing_token_flag",
                "missing_token_reason",
            ]
        )

    orders["date_dt"] = pd.to_datetime(orders["Date"], errors="coerce", utc=True)
    orders = orders[orders["date_dt"].notna()].copy()
    orders = orders[orders["date_dt"] >= start_dt].copy()
    if orders.empty:
        return pd.DataFrame(
            columns=[
                "order_key",
                "currency_code",
                "country_code",
                "placeholder_cogs_gbp",
                "placeholder_basis_source",
                "placeholder_basis_date",
                "missing_token_flag",
                "missing_token_reason",
            ]
        )

    orders["date"] = orders["date_dt"].dt.strftime("%Y-%m-%d")
    orders["order_key"] = _build_order_key(
        series_or_default(orders, "Order ID"),
        series_or_default(orders, "SKU"),
        orders["date"],
    )
    orders["currency_code"] = series_or_default(orders, "currency_code").astype(str).str.strip().str.upper()
    orders["country_code"] = series_or_default(orders, "country_code").astype(str).str.strip().str.upper()
    placeholder_flag = series_or_default(orders, "COGS_Placeholder_Applied").astype(str).str.strip().str.lower().isin({"1", "true", "yes", "y"})
    orders["placeholder_cogs_gbp"] = to_num(series_or_default(orders, "COGS_ExVAT")).where(placeholder_flag, 0.0)
    orders["placeholder_basis_source"] = series_or_default(orders, "COGS_Basis_Source").astype(str).str.strip()
    orders["placeholder_basis_date"] = series_or_default(orders, "COGS_Basis_Date").astype(str).str.strip()
    orders["missing_token_flag"] = to_num(series_or_default(orders, "Missing_Token_Flag"))
    orders["missing_token_reason"] = series_or_default(orders, "Missing_Token_Reason").astype(str).str.strip()
    orders = orders[orders["order_key"].astype(str).str.strip() != ""].copy()
    return orders[
        [
            "order_key",
            "currency_code",
            "country_code",
            "placeholder_cogs_gbp",
            "placeholder_basis_source",
            "placeholder_basis_date",
            "missing_token_flag",
            "missing_token_reason",
        ]
    ].drop_duplicates(subset=["order_key"], keep="last")


def _load_token_cogs_map(
    token_cogs_path: Path,
    exact_fx: dict[tuple[str, str], float],
    latest_fx: dict[str, float],
) -> pd.DataFrame:
    tokens = read_csv(
        token_cogs_path,
        usecols=["order_id", "seller_sku", "quantity", "currency", "cogs_exvat", "order_date", "allocation_date"],
    )
    if tokens.empty:
        return pd.DataFrame(columns=["order_key", "token_qty", "token_cogs_gbp", "token_fx_missing_rows"])

    date_source = series_or_default(tokens, "order_date")
    date_source = date_source.where(date_source.astype(str).str.strip() != "", series_or_default(tokens, "allocation_date"))
    tokens["date_dt"] = pd.to_datetime(date_source, errors="coerce", utc=True)
    tokens = tokens[tokens["date_dt"].notna()].copy()
    if tokens.empty:
        return pd.DataFrame(columns=["order_key", "token_qty", "token_cogs_gbp", "token_fx_missing_rows"])

    tokens["date"] = tokens["date_dt"].dt.strftime("%Y-%m-%d")
    tokens["order_key"] = _build_order_key(
        series_or_default(tokens, "order_id"),
        series_or_default(tokens, "seller_sku"),
        tokens["date"],
    )
    tokens["qty"] = to_num(series_or_default(tokens, "quantity"))
    tokens["cogs_exvat"] = to_num(series_or_default(tokens, "cogs_exvat"))
    tokens["currency"] = series_or_default(tokens, "currency").astype(str).str.strip().str.upper()

    cogs_gbp: list[float] = []
    fx_missing_rows: list[float] = []
    for _, row in tokens.iterrows():
        rate, missing_fx = rate_to_gbp(str(row["date"]), str(row["currency"]), exact_fx, latest_fx)
        cogs_gbp.append(-abs(float(row["cogs_exvat"])) * rate)
        fx_missing_rows.append(1.0 if missing_fx else 0.0)
    tokens["token_cogs_gbp"] = cogs_gbp
    tokens["token_fx_missing_rows"] = fx_missing_rows

    grouped = (
        tokens.groupby("order_key", dropna=False)[["qty", "token_cogs_gbp", "token_fx_missing_rows"]]
        .sum()
        .reset_index()
        .rename(columns={"qty": "token_qty"})
    )
    return grouped


def _build_finalized_rows(order_ledger_fx_path: Path, start_dt: pd.Timestamp) -> pd.DataFrame:
    ledger = read_csv(order_ledger_fx_path)
    if ledger.empty:
        return _base_truth_frame()

    date_col = "date" if "date" in ledger.columns else "Date" if "Date" in ledger.columns else ""
    if not date_col:
        return _base_truth_frame()
    ledger["date_dt"] = pd.to_datetime(ledger[date_col], errors="coerce", utc=True)
    ledger = ledger[ledger["date_dt"].notna()].copy()
    ledger = ledger[ledger["date_dt"] >= start_dt].copy()
    if ledger.empty:
        return _base_truth_frame()

    ledger["date"] = ledger["date_dt"].dt.strftime("%Y-%m-%d")
    ledger["order_id"] = series_or_default(ledger, "Order ID").astype(str).str.strip()
    ledger["sku"] = norm_sku(series_or_default(ledger, "SKU", series_or_default(ledger, "sku")))
    ledger = ledger[ledger["sku"] != ""].copy()
    if ledger.empty:
        return _base_truth_frame()

    ledger["order_key"] = _build_order_key(ledger["order_id"], ledger["sku"], ledger["date"])
    ledger["country_code"] = series_or_default(ledger, "country_code").astype(str).str.strip().str.upper()
    ledger["units"] = to_num(series_or_default(ledger, "Quantity Ordered"))
    ledger["revenue_gbp"] = (
        to_num(series_or_default(ledger, "Price_ExVAT_GBP", series_or_default(ledger, "Price_ExVAT")))
        + to_num(series_or_default(ledger, "Shipping_ExVAT_GBP", series_or_default(ledger, "Shipping_ExVAT")))
        + to_num(series_or_default(ledger, "Gift_ExVAT_GBP", series_or_default(ledger, "Gift_ExVAT")))
        + to_num(series_or_default(ledger, "Promotion_ExVAT_GBP", series_or_default(ledger, "Promotion_ExVAT")))
    )
    ledger["fees_gbp"] = (
        to_num(series_or_default(ledger, "FBA_Fee_ExVAT_GBP", series_or_default(ledger, "FBA_Fee_ExVAT")))
        + to_num(series_or_default(ledger, "Commission_ExVAT_GBP", series_or_default(ledger, "Commission_ExVAT")))
        + to_num(series_or_default(ledger, "Digital_Fee_ExVAT_GBP", series_or_default(ledger, "Digital_Fee_ExVAT")))
        + to_num(series_or_default(ledger, "FixedClosingFee_ExVAT_GBP", series_or_default(ledger, "FixedClosingFee_ExVAT")))
    )
    ledger["cogs_gbp"] = to_num(series_or_default(ledger, "COGS_ExVAT_GBP", series_or_default(ledger, "COGS_ExVAT")))
    ledger = ledger[(ledger["units"].abs() > 0) | (ledger["revenue_gbp"].abs() > 0)].copy()
    if ledger.empty:
        return _base_truth_frame()

    ledger["profit_gbp"] = ledger["revenue_gbp"] + ledger["fees_gbp"] + ledger["cogs_gbp"]
    ledger["fx_missing_units"] = 0.0
    ledger["missing_cogs_units"] = ledger["units"].abs().where(ledger["cogs_gbp"].abs() <= 0, 0.0)
    ledger["placeholder_cogs_units"] = 0.0
    ledger["profit_excluded_rows"] = 0.0
    ledger["placeholder_basis_source"] = ""
    ledger["placeholder_basis_date"] = ""
    ledger["source_state"] = "finalized_ledger"
    ledger["confidence_status"] = "finalized"
    ledger["basis"] = "order_ledger_fx"
    ledger["notes"] = ""
    return ledger[TRUTH_ROW_COLUMNS].copy()


def _build_level2_rows(
    financial_events_level2_path: Path,
    *,
    start_dt: pd.Timestamp,
    finalized_keys: set[str],
    order_meta: pd.DataFrame,
    token_map: pd.DataFrame,
    marketplace_map: dict[str, dict[str, str]],
    exact_fx: dict[tuple[str, str], float],
    latest_fx: dict[str, float],
) -> pd.DataFrame:
    level2 = read_csv(financial_events_level2_path)
    if level2.empty:
        return _base_truth_frame()

    level2["date_dt"] = pd.to_datetime(series_or_default(level2, "Date"), errors="coerce", utc=True)
    level2 = level2[level2["date_dt"].notna()].copy()
    level2 = level2[level2["date_dt"] >= start_dt].copy()
    if level2.empty:
        return _base_truth_frame()

    level2["date"] = level2["date_dt"].dt.strftime("%Y-%m-%d")
    level2["order_id"] = series_or_default(level2, "Order ID").astype(str).str.strip()
    level2["sku"] = norm_sku(series_or_default(level2, "SKU"))
    level2 = level2[level2["sku"] != ""].copy()
    if level2.empty:
        return _base_truth_frame()

    level2["order_key"] = _build_order_key(level2["order_id"], level2["sku"], level2["date"])
    level2 = level2[~level2["order_key"].isin(finalized_keys)].copy()
    if level2.empty:
        return _base_truth_frame()

    level2["units"] = to_num(series_or_default(level2, "Quantity Ordered"))
    level2["revenue_raw"] = (
        to_num(series_or_default(level2, "Price_ExVAT"))
        + to_num(series_or_default(level2, "Shipping_ExVAT"))
        + to_num(series_or_default(level2, "Gift_ExVAT"))
        + to_num(series_or_default(level2, "Promotion_ExVAT"))
    )
    level2["fees_raw"] = (
        to_num(series_or_default(level2, "FBA_Fee_ExVAT"))
        + to_num(series_or_default(level2, "Commission_ExVAT"))
        + to_num(series_or_default(level2, "Digital_Fee_ExVAT"))
        + to_num(series_or_default(level2, "FixedClosingFee_ExVAT"))
    )
    level2 = level2[(level2["units"].abs() > 0) | (level2["revenue_raw"].abs() > 0)].copy()
    if level2.empty:
        return _base_truth_frame()

    if not order_meta.empty:
        level2 = level2.merge(order_meta, on="order_key", how="left", suffixes=("", "_meta"))
    else:
        level2["currency_code"] = ""
        level2["country_code"] = ""

    level2["marketplace_id"] = series_or_default(level2, "marketplace_id").astype(str).str.strip()
    level2["country_code"] = level2.apply(
        lambda row: str(marketplace_map.get(str(row.get("marketplace_id", "")), {}).get("country_code", "")).strip().upper()
        or str(row.get("country_code", "")).strip().upper(),
        axis=1,
    )
    level2["currency_code"] = level2.apply(
        lambda row: str(marketplace_map.get(str(row.get("marketplace_id", "")), {}).get("currency_code", "")).strip().upper()
        or str(row.get("currency_code", "")).strip().upper(),
        axis=1,
    )

    revenue_gbp: list[float] = []
    fees_gbp: list[float] = []
    fx_missing_units: list[float] = []
    for _, row in level2.iterrows():
        units = abs(float(row["units"]))
        rate, missing_fx = rate_to_gbp(str(row["date"]), str(row["currency_code"]), exact_fx, latest_fx)
        revenue_gbp.append(float(row["revenue_raw"]) * rate)
        fees_gbp.append(float(row["fees_raw"]) * rate)
        fx_missing_units.append(units if missing_fx else 0.0)
    level2["revenue_gbp"] = revenue_gbp
    level2["fees_gbp"] = fees_gbp
    level2["fx_missing_units"] = fx_missing_units

    if not token_map.empty:
        level2 = level2.merge(token_map, on="order_key", how="left")
    level2["token_qty"] = to_num(series_or_default(level2, "token_qty"))
    level2["token_cogs_gbp"] = to_num(series_or_default(level2, "token_cogs_gbp"))
    level2["token_fx_missing_rows"] = to_num(series_or_default(level2, "token_fx_missing_rows"))
    level2["placeholder_cogs_gbp"] = to_num(series_or_default(level2, "placeholder_cogs_gbp"))
    level2["placeholder_basis_source"] = series_or_default(level2, "placeholder_basis_source").astype(str).str.strip()
    level2["placeholder_basis_date"] = series_or_default(level2, "placeholder_basis_date").astype(str).str.strip()
    level2["missing_token_flag"] = to_num(series_or_default(level2, "missing_token_flag"))
    level2["missing_token_reason"] = series_or_default(level2, "missing_token_reason").astype(str).str.strip()

    units_abs = level2["units"].abs()
    cogs_complete = (
        (units_abs <= 0)
        | (
            (level2["token_qty"] >= units_abs)
            & (level2["token_cogs_gbp"].abs() > 0)
            & (level2["token_fx_missing_rows"] <= 0)
        )
    )
    use_placeholder = (~cogs_complete) & level2["placeholder_cogs_gbp"].abs().gt(0.0)
    level2["placeholder_cogs_units"] = units_abs.where(use_placeholder, 0.0)
    level2["missing_cogs_units"] = units_abs.where((~cogs_complete) & (~use_placeholder), 0.0)
    level2["cogs_gbp"] = level2["token_cogs_gbp"].where(cogs_complete, 0.0)
    level2.loc[use_placeholder, "cogs_gbp"] = level2.loc[use_placeholder, "placeholder_cogs_gbp"]
    level2["profit_excluded_rows"] = ((~cogs_complete) & (~use_placeholder)).astype(float)
    level2["profit_gbp"] = (level2["revenue_gbp"] + level2["fees_gbp"] + level2["cogs_gbp"]).where(
        cogs_complete | use_placeholder,
        0.0,
    )
    level2["source_state"] = "provisional_order_master"
    level2["confidence_status"] = level2.apply(
        lambda row: _row_confidence(
            fx_missing_units=float(row["fx_missing_units"]),
            missing_cogs_units=float(row["missing_cogs_units"]),
            placeholder_cogs_units=float(row["placeholder_cogs_units"]),
        ),
        axis=1,
    )
    level2["basis"] = "financial_events_level2"
    level2["notes"] = level2.apply(
        lambda row: _row_notes(
            basis="financial_events_level2",
            fx_missing_units=float(row["fx_missing_units"]),
            missing_cogs_units=float(row["missing_cogs_units"]),
            placeholder_cogs_units=float(row["placeholder_cogs_units"]),
            profit_excluded_rows=float(row["profit_excluded_rows"]),
            placeholder_basis_source=str(row.get("placeholder_basis_source", "")),
            placeholder_basis_date=str(row.get("placeholder_basis_date", "")),
            missing_token_flag=float(row.get("missing_token_flag", 0.0)),
            missing_token_reason=str(row.get("missing_token_reason", "")),
        ),
        axis=1,
    )
    return level2[TRUTH_ROW_COLUMNS].copy()


def _build_order_master_rows(
    order_master_path: Path,
    *,
    start_dt: pd.Timestamp,
    excluded_keys: set[str],
    exact_fx: dict[tuple[str, str], float],
    latest_fx: dict[str, float],
) -> pd.DataFrame:
    orders = read_csv(order_master_path)
    if orders.empty:
        return _base_truth_frame()

    orders["date_dt"] = pd.to_datetime(series_or_default(orders, "Date"), errors="coerce", utc=True)
    orders = orders[orders["date_dt"].notna()].copy()
    orders = orders[orders["date_dt"] >= start_dt].copy()
    if orders.empty:
        return _base_truth_frame()

    orders["date"] = orders["date_dt"].dt.strftime("%Y-%m-%d")
    orders["order_id"] = series_or_default(orders, "Order ID").astype(str).str.strip()
    orders["sku"] = norm_sku(series_or_default(orders, "SKU"))
    orders = orders[orders["sku"] != ""].copy()
    if orders.empty:
        return _base_truth_frame()

    orders["order_key"] = _build_order_key(orders["order_id"], orders["sku"], orders["date"])
    orders = orders[~orders["order_key"].isin(excluded_keys)].copy()
    if orders.empty:
        return _base_truth_frame()

    orders["units"] = to_num(series_or_default(orders, "Quantity Ordered"))
    orders["country_code"] = series_or_default(orders, "country_code").astype(str).str.strip().str.upper()
    orders["currency_code"] = series_or_default(orders, "currency_code").astype(str).str.strip().str.upper()
    orders["revenue_raw"] = (
        to_num(series_or_default(orders, "Price_ExVAT"))
        + to_num(series_or_default(orders, "Shipping_ExVAT"))
        + to_num(series_or_default(orders, "Gift_ExVAT"))
        + to_num(series_or_default(orders, "Promotion_ExVAT"))
    )
    orders["fees_raw"] = (
        to_num(series_or_default(orders, "FBA_Fee_ExVAT"))
        + to_num(series_or_default(orders, "Commission_ExVAT"))
        + to_num(series_or_default(orders, "Digital_Fee_ExVAT"))
        + to_num(series_or_default(orders, "FixedClosingFee_ExVAT"))
    )
    orders["cogs_raw"] = to_num(series_or_default(orders, "COGS_ExVAT"))
    orders["placeholder_applied"] = series_or_default(orders, "COGS_Placeholder_Applied").astype(str).str.strip().str.lower().isin(
        {"1", "true", "yes", "y"}
    )
    orders["placeholder_basis_source"] = series_or_default(orders, "COGS_Basis_Source").astype(str).str.strip()
    orders["placeholder_basis_date"] = series_or_default(orders, "COGS_Basis_Date").astype(str).str.strip()
    orders["missing_token_flag"] = to_num(series_or_default(orders, "Missing_Token_Flag"))
    orders["missing_token_reason"] = series_or_default(orders, "Missing_Token_Reason").astype(str).str.strip()
    orders = orders[(orders["units"].abs() > 0) | (orders["revenue_raw"].abs() > 0)].copy()
    if orders.empty:
        return _base_truth_frame()

    revenue_gbp: list[float] = []
    fees_gbp: list[float] = []
    cogs_gbp: list[float] = []
    fx_missing_units: list[float] = []
    for _, row in orders.iterrows():
        units = abs(float(row["units"]))
        rate, missing_fx = rate_to_gbp(str(row["date"]), str(row["currency_code"]), exact_fx, latest_fx)
        revenue_gbp.append(float(row["revenue_raw"]) * rate)
        fees_gbp.append(float(row["fees_raw"]) * rate)
        cogs_gbp.append(float(row["cogs_raw"]))
        fx_missing_units.append(units if missing_fx else 0.0)

    orders["revenue_gbp"] = revenue_gbp
    orders["fees_gbp"] = fees_gbp
    orders["raw_cogs_gbp"] = cogs_gbp
    orders["fx_missing_units"] = fx_missing_units
    units_abs = orders["units"].abs()
    has_any_cogs = orders["raw_cogs_gbp"].abs() > 0
    use_placeholder = has_any_cogs & orders["placeholder_applied"]
    cogs_complete = has_any_cogs & (~orders["placeholder_applied"])
    orders["placeholder_cogs_units"] = units_abs.where(use_placeholder, 0.0)
    orders["missing_cogs_units"] = units_abs.where((~cogs_complete) & (~use_placeholder), 0.0)
    orders["cogs_gbp"] = orders["raw_cogs_gbp"].where(has_any_cogs, 0.0)
    orders["profit_excluded_rows"] = ((~cogs_complete) & (~use_placeholder)).astype(float)
    orders["profit_gbp"] = (orders["revenue_gbp"] + orders["fees_gbp"] + orders["cogs_gbp"]).where(
        has_any_cogs,
        0.0,
    )
    orders["source_state"] = "provisional_order_master"
    orders["confidence_status"] = orders.apply(
        lambda row: _row_confidence(
            fx_missing_units=float(row["fx_missing_units"]),
            missing_cogs_units=float(row["missing_cogs_units"]),
            placeholder_cogs_units=float(row["placeholder_cogs_units"]),
        ),
        axis=1,
    )
    orders["basis"] = "order_master_fallback"
    orders["notes"] = orders.apply(
        lambda row: _row_notes(
            basis="order_master_fallback",
            fx_missing_units=float(row["fx_missing_units"]),
            missing_cogs_units=float(row["missing_cogs_units"]),
            placeholder_cogs_units=float(row["placeholder_cogs_units"]),
            profit_excluded_rows=float(row["profit_excluded_rows"]),
            placeholder_basis_source=str(row.get("placeholder_basis_source", "")),
            placeholder_basis_date=str(row.get("placeholder_basis_date", "")),
            missing_token_flag=float(row.get("missing_token_flag", 0.0)),
            missing_token_reason=str(row.get("missing_token_reason", "")),
        ),
        axis=1,
    )
    return orders[TRUTH_ROW_COLUMNS].copy()


def build_truth_rows(
    *,
    order_ledger_fx_path: Path,
    financial_events_level2_path: Path,
    token_cogs_path: Path,
    order_master_path: Path,
    fx_rates_path: Path,
    marketplace_participations_path: Path,
    window_days: int = WINDOW_DAYS,
) -> tuple[pd.DataFrame, str]:
    max_dt, start_dt = _resolve_window(
        order_ledger_fx_path=order_ledger_fx_path,
        financial_events_level2_path=financial_events_level2_path,
        order_master_path=order_master_path,
        window_days=window_days,
    )
    if max_dt is None or start_dt is None:
        return _base_truth_frame(), ""

    exact_fx, latest_fx = build_fx_lookup(fx_rates_path)
    marketplace_map = load_marketplace_map(marketplace_participations_path)
    order_meta = _load_order_meta(order_master_path, start_dt)
    token_map = _load_token_cogs_map(token_cogs_path, exact_fx, latest_fx)

    finalized = _build_finalized_rows(order_ledger_fx_path, start_dt)
    finalized_keys = set(finalized["order_key"].astype(str).tolist()) if not finalized.empty else set()

    provisional_l2 = _build_level2_rows(
        financial_events_level2_path,
        start_dt=start_dt,
        finalized_keys=finalized_keys,
        order_meta=order_meta,
        token_map=token_map,
        marketplace_map=marketplace_map,
        exact_fx=exact_fx,
        latest_fx=latest_fx,
    )
    provisional_keys = set(provisional_l2["order_key"].astype(str).tolist()) if not provisional_l2.empty else set()
    excluded_keys = finalized_keys | provisional_keys

    provisional_order_master = _build_order_master_rows(
        order_master_path,
        start_dt=start_dt,
        excluded_keys=excluded_keys,
        exact_fx=exact_fx,
        latest_fx=latest_fx,
    )

    frames = [df for df in [finalized, provisional_l2, provisional_order_master] if not df.empty]
    if not frames:
        return _base_truth_frame(), max_dt.date().isoformat()

    truth_rows = pd.concat(frames, ignore_index=True)
    truth_rows = truth_rows.sort_values(["date_dt", "sku", "source_state", "order_key"], kind="stable").reset_index(drop=True)
    return truth_rows[TRUTH_ROW_COLUMNS].copy(), max_dt.date().isoformat()
