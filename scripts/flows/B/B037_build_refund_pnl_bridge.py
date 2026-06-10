from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.safe_file_writes import safe_to_csv


OUT = Path("out")
REFUNDS_OFFICIAL = OUT / "financial_events_refunds_official.csv"
ORDER_LEDGER_FX = OUT / "order_ledger_fx.csv"
ORDER_MASTER = OUT / "order_master.csv"
SELLERBOARD_RECONCILIATION = OUT / "systems" / "M" / "sellerboard_bridge" / "b_sellerboard_bridge_order_reconciliation.csv"
TOKEN_LEDGER = OUT / "token_ledger_live.csv"
TOKEN_RETURN_LEDGER = OUT / "token_return_ledger.csv"
AMAZON_RETURN_REPORT_RELS = [
    OUT / "systems" / "B" / "refunds" / "b_fba_customer_returns.csv",
    OUT / "systems" / "M" / "b_refund_return_api_probe" / "b_fba_customer_returns_probe.csv",
    OUT / "fba_customer_returns.csv",
]
OUT_DIR = OUT / "systems" / "B" / "refunds"
OUT_BRIDGE = OUT_DIR / "b_refund_pnl_bridge.csv"
OUT_RATE = OUT_DIR / "b_sku_refund_rate.csv"

BRIDGE_COLUMNS = [
    "order_id",
    "sku",
    "marketplace",
    "original_purchase_date",
    "refund_posted_date",
    "original_order_status",
    "original_units",
    "refund_units",
    "original_price_total",
    "original_price_exvat",
    "refund_price_total",
    "refund_price_vat",
    "refund_price_exvat",
    "refund_shipping_total",
    "refund_commission_total",
    "refund_digital_fee_total",
    "refund_fba_fee_total",
    "refund_other_fee_total",
    "return_cogs_recovered_exvat",
    "refund_profit_impact_exvat",
    "sellerboard_status",
    "sellerboard_match_state",
    "api_refund_proof_state",
    "pnl_inclusion_state",
    "notes",
]

RATE_COLUMNS = [
    "sku",
    "window_days",
    "sales_units",
    "refund_units",
    "net_units",
    "refund_unit_rate",
    "refund_order_count",
    "sales_order_count",
    "refund_sales_total_gbp",
    "refund_fee_reversal_total_gbp",
    "refund_profit_impact_gbp",
    "expected_refund_cost_per_unit_gbp",
    "basis",
    "sample_confidence",
    "proof_state",
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _text(value: object) -> str:
    return str(value or "").strip()


def _norm_sku(value: object) -> str:
    return _text(value).upper()


def _num(value: object) -> float:
    raw = _text(value).replace(",", "")
    if not raw:
        return 0.0
    try:
        return float(raw)
    except Exception:
        return 0.0


def _num_text(value: object) -> str:
    number = _num(value)
    if abs(number) < 0.0000005:
        return "0"
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _parse_dt(value: object) -> pd.Timestamp | None:
    parsed = pd.to_datetime(_text(value), errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed


def _date_text(value: object) -> str:
    parsed = _parse_dt(value)
    if parsed is None:
        return ""
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _date_only(value: object) -> str:
    parsed = _parse_dt(value)
    if parsed is None:
        return ""
    return parsed.strftime("%Y-%m-%d")


def _first_non_blank(values: pd.Series) -> str:
    for value in values.tolist():
        text = _text(value)
        if text:
            return text
    return ""


def _load_order_summary() -> pd.DataFrame:
    orders = _read_csv(ORDER_LEDGER_FX if ORDER_LEDGER_FX.exists() else ORDER_MASTER)
    if orders.empty:
        return pd.DataFrame(
            columns=[
                "order_id",
                "sku",
                "marketplace",
                "original_purchase_date",
                "original_order_status",
                "original_units",
                "original_price_total",
                "original_price_exvat",
            ]
        )

    order_id_col = "Order ID" if "Order ID" in orders.columns else "order_id"
    sku_col = "SKU" if "SKU" in orders.columns else "sku"
    if order_id_col not in orders.columns or sku_col not in orders.columns:
        return pd.DataFrame()

    work = orders.copy()
    work["order_id"] = work[order_id_col].map(_text)
    work["sku"] = work[sku_col].map(_norm_sku)
    work = work[(work["order_id"] != "") & (work["sku"] != "")]
    if work.empty:
        return pd.DataFrame()

    work["purchase_dt"] = pd.to_datetime(work.get("Date", ""), errors="coerce", utc=True)
    work["units_num"] = pd.to_numeric(work.get("Quantity Ordered", 0), errors="coerce").fillna(0.0)
    total_col = "Price_Total_GBP" if "Price_Total_GBP" in work.columns else "Price_Total"
    exvat_col = "Price_ExVAT_GBP" if "Price_ExVAT_GBP" in work.columns else "Price_ExVAT"
    work["price_total_num"] = pd.to_numeric(work.get(total_col, 0), errors="coerce").fillna(0.0)
    work["price_exvat_num"] = pd.to_numeric(work.get(exvat_col, 0), errors="coerce").fillna(0.0)
    marketplace_col = "country_code" if "country_code" in work.columns else "marketplace"
    status_col = "Order Status" if "Order Status" in work.columns else "order_status"
    if marketplace_col not in work.columns:
        work[marketplace_col] = ""
    if status_col not in work.columns:
        work[status_col] = ""

    rows: list[dict[str, object]] = []
    for (order_id, sku), group in work.groupby(["order_id", "sku"], dropna=False):
        purchase_dates = group["purchase_dt"].dropna()
        rows.append(
            {
                "order_id": order_id,
                "sku": sku,
                "marketplace": _first_non_blank(group[marketplace_col]),
                "original_purchase_date": "" if purchase_dates.empty else purchase_dates.min().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "original_order_status": _first_non_blank(group[status_col]),
                "original_units": float(group.loc[group["units_num"] > 0, "units_num"].sum()),
                "original_price_total": float(group["price_total_num"].sum()),
                "original_price_exvat": float(group["price_exvat_num"].sum()),
            }
        )
    return pd.DataFrame(rows)


def _load_sellerboard_rows() -> pd.DataFrame:
    rows = _read_csv(SELLERBOARD_RECONCILIATION)
    if rows.empty:
        return pd.DataFrame()
    rows = rows.copy()
    rows["order_id"] = rows.get("amazon_order_id", "").map(_text)
    rows["sku"] = rows.get("mapped_sku", "").map(_norm_sku)
    rows["sellerboard_status_norm"] = rows.get("sellerboard_status", "").astype(str).str.strip().str.lower()
    return rows[(rows["order_id"] != "")]


def _first_present(df: pd.DataFrame, names: list[str]) -> pd.Series:
    for name in names:
        if name in df.columns:
            return df[name].astype(str)
    return pd.Series([""] * len(df), index=df.index, dtype=str)


def _find_amazon_return_report() -> Path | None:
    for path in AMAZON_RETURN_REPORT_RELS:
        if path.exists():
            return path
    return None


def _load_amazon_return_dispositions() -> dict[tuple[str, str], str]:
    path = _find_amazon_return_report()
    if path is None:
        return {}
    rows = _read_csv(path)
    if rows.empty:
        return {}
    work = rows.copy()
    work["order_id"] = _first_present(work, ["order-id", "order_id", "amazon_order_id"]).map(_text)
    work["sku"] = _first_present(work, ["sku", "seller-sku", "seller_sku", "SKU"]).map(_norm_sku)
    work["disposition"] = _first_present(work, ["detailed-disposition", "detailed_disposition", "disposition"]).map(
        lambda value: _text(value).upper()
    )
    work = work[(work["order_id"] != "") & (work["sku"] != "")]
    out: dict[tuple[str, str], str] = {}
    for (order_id, sku), group in work.groupby(["order_id", "sku"], dropna=False):
        dispositions = {_text(value).upper() for value in group["disposition"].tolist() if _text(value)}
        if "SELLABLE" in dispositions:
            out[(order_id, sku)] = "SELLABLE"
        elif "RESEARCHING" in dispositions:
            out[(order_id, sku)] = "RESEARCHING"
        elif dispositions:
            out[(order_id, sku)] = sorted(dispositions)[0]
        else:
            out[(order_id, sku)] = ""
    return out


def _load_returned_token_costs() -> dict[tuple[str, str], float]:
    ledger = _read_csv(TOKEN_LEDGER)
    returns = _read_csv(TOKEN_RETURN_LEDGER)
    if ledger.empty or returns.empty:
        return {}
    if "seller_sku" not in ledger.columns or "token_id" not in ledger.columns:
        return {}
    if "token_id" not in returns.columns:
        return {}
    returned = ledger.copy()
    for column in ["token_id", "seller_sku", "status", "last_return_order_id", "notes"]:
        if column not in returned.columns:
            returned[column] = ""
    returned["token_id"] = returned["token_id"].map(_text)
    returned["order_id"] = returned["last_return_order_id"].map(_text)
    returned["sku"] = returned["seller_sku"].map(_norm_sku)
    returned["status_norm"] = returned["status"].astype(str).str.strip().str.lower()
    returned["notes_norm"] = returned["notes"].astype(str).str.strip().str.lower()
    returned = returned[
        (returned["token_id"] != "")
        & (returned["order_id"] != "")
        & (returned["sku"] != "")
        & returned["notes_norm"].str.contains("return_sellable_dup", na=False)
        & returned["status_norm"].isin({"available", "allocated", "warehouse"})
        & ~returned["notes_norm"].str.contains("non_sellable_return_correction_blocked", na=False)
    ].copy()
    if returned.empty:
        return {}
    returns = returns.copy()
    cost_col = "token_cost" if "token_cost" in returns.columns else "cost_per_unit"
    if cost_col not in returns.columns:
        return {}
    returns["token_id"] = returns["token_id"].map(_text)
    returns["cost_num"] = returns[cost_col].map(_num)
    returns = returns[(returns["token_id"] != "") & (returns["cost_num"] > 0)].copy()
    if returns.empty:
        return {}
    returned = returned.merge(returns[["token_id", "cost_num"]], on="token_id", how="inner")
    if returned.empty:
        return {}
    out: dict[tuple[str, str], float] = {}
    for (order_id, sku), group in returned.groupby(["order_id", "sku"], dropna=False):
        out[(order_id, sku)] = float(group["cost_num"].sum())
    return out


def _sellerboard_match(order_id: str, sku: str, sellerboard: pd.DataFrame) -> tuple[str, str]:
    if sellerboard.empty:
        return "", "sellerboard_not_available"
    order_rows = sellerboard[sellerboard["order_id"] == order_id]
    if order_rows.empty:
        return "", "sellerboard_not_seen"
    sku_rows = order_rows[order_rows["sku"] == sku] if sku else pd.DataFrame()
    selected = sku_rows if not sku_rows.empty else order_rows
    status = _first_non_blank(selected.get("sellerboard_status", pd.Series(dtype=str)))
    if selected.get("sellerboard_status_norm", pd.Series(dtype=str)).str.contains("return", na=False).any():
        return status, "sellerboard_return_witness"
    return status, "sellerboard_seen_not_return"


def _official_refund_rows(refunds: pd.DataFrame, orders: pd.DataFrame, sellerboard: pd.DataFrame) -> list[dict[str, object]]:
    if refunds.empty:
        return []
    work = refunds.copy()
    work = work.rename(columns={"Order ID": "order_id", "SKU": "sku", "Date": "refund_posted_date", "Quantity Ordered": "refund_units"})
    required = {"order_id", "sku", "refund_posted_date"}
    if not required.issubset(work.columns):
        return []
    work["order_id"] = work["order_id"].map(_text)
    work["sku"] = work["sku"].map(_norm_sku)
    work = work[(work["order_id"] != "") & (work["sku"] != "")]
    for col in [
        "refund_units",
        "Price_Total",
        "Price_VAT",
        "Price_ExVAT",
        "Shipping_Total",
        "Commission_Total",
        "Digital_Fee_Total",
        "FBA_Fee_Total",
        "FixedClosingFee_Total",
    ]:
        if col not in work.columns:
            work[col] = "0"
        work[f"{col}_num"] = pd.to_numeric(work[col], errors="coerce").fillna(0.0)

    order_map = {(row["order_id"], row["sku"]): row for _, row in orders.iterrows()} if not orders.empty else {}
    returned_costs = _load_returned_token_costs()
    return_dispositions = _load_amazon_return_dispositions()
    rows: list[dict[str, object]] = []
    for (order_id, sku), group in work.groupby(["order_id", "sku"], dropna=False):
        refund_dates = group["refund_posted_date"].map(_date_text)
        refund_date = max([d for d in refund_dates.tolist() if d], default="")
        order = order_map.get((order_id, sku), {})
        refund_units = float(group["refund_units_num"].abs().sum())
        if refund_units <= 0:
            refund_units = 1.0
        fee_total = (
            float(group["Commission_Total_num"].sum())
            + float(group["Digital_Fee_Total_num"].sum())
            + float(group["FBA_Fee_Total_num"].sum())
            + float(group["FixedClosingFee_Total_num"].sum())
        )
        other_fee = float(group["FixedClosingFee_Total_num"].sum())
        raw_cogs_recovered = returned_costs.get((order_id, sku), 0.0)
        return_disposition = return_dispositions.get((order_id, sku), "")
        cogs_recovered = raw_cogs_recovered if return_disposition == "SELLABLE" else 0.0
        profit_impact = (
            float(group["Price_ExVAT_num"].sum())
            + float(group["Shipping_Total_num"].sum())
            + fee_total
            + cogs_recovered
        )
        sellerboard_status, sellerboard_state = _sellerboard_match(order_id, sku, sellerboard)
        notes = []
        if not isinstance(order, pd.Series):
            notes.append("original_order_not_found")
        if cogs_recovered == 0:
            notes.append("no_returned_token_cogs_recovered")
        if raw_cogs_recovered > 0 and return_disposition != "SELLABLE":
            if return_disposition:
                notes.append(f"return_cogs_blocked_amazon_{return_disposition.lower()}")
            else:
                notes.append("return_cogs_blocked_missing_amazon_sellable_return_proof")
        rows.append(
            {
                "order_id": order_id,
                "sku": sku,
                "marketplace": _text(order.get("marketplace", "")) if isinstance(order, pd.Series) else "",
                "original_purchase_date": _text(order.get("original_purchase_date", "")) if isinstance(order, pd.Series) else "",
                "refund_posted_date": refund_date,
                "original_order_status": _text(order.get("original_order_status", "")) if isinstance(order, pd.Series) else "",
                "original_units": _num_text(order.get("original_units", 0) if isinstance(order, pd.Series) else 0),
                "refund_units": _num_text(refund_units),
                "original_price_total": _num_text(order.get("original_price_total", 0) if isinstance(order, pd.Series) else 0),
                "original_price_exvat": _num_text(order.get("original_price_exvat", 0) if isinstance(order, pd.Series) else 0),
                "refund_price_total": _num_text(group["Price_Total_num"].sum()),
                "refund_price_vat": _num_text(group["Price_VAT_num"].sum()),
                "refund_price_exvat": _num_text(group["Price_ExVAT_num"].sum()),
                "refund_shipping_total": _num_text(group["Shipping_Total_num"].sum()),
                "refund_commission_total": _num_text(group["Commission_Total_num"].sum()),
                "refund_digital_fee_total": _num_text(group["Digital_Fee_Total_num"].sum()),
                "refund_fba_fee_total": _num_text(group["FBA_Fee_Total_num"].sum()),
                "refund_other_fee_total": _num_text(other_fee),
                "return_cogs_recovered_exvat": _num_text(cogs_recovered),
                "refund_profit_impact_exvat": _num_text(profit_impact),
                "sellerboard_status": sellerboard_status,
                "sellerboard_match_state": sellerboard_state,
                "api_refund_proof_state": "api_proved",
                "pnl_inclusion_state": "pnl_official_refund_source",
                "notes": ";".join(notes),
            }
        )
    return rows


def _sellerboard_return_only_rows(api_keys: set[tuple[str, str]], orders: pd.DataFrame, sellerboard: pd.DataFrame) -> list[dict[str, object]]:
    if sellerboard.empty:
        return []
    order_map = {(row["order_id"], row["sku"]): row for _, row in orders.iterrows()} if not orders.empty else {}
    rows: list[dict[str, object]] = []
    returns = sellerboard[sellerboard["sellerboard_status_norm"].str.contains("return", na=False)].copy()
    for _, sb in returns.iterrows():
        order_id = _text(sb.get("order_id", ""))
        sku = _norm_sku(sb.get("sku", ""))
        key = (order_id, sku)
        if not order_id or key in api_keys:
            continue
        order = order_map.get(key, {})
        rows.append(
            {
                "order_id": order_id,
                "sku": sku,
                "marketplace": _text(order.get("marketplace", "")) if isinstance(order, pd.Series) else "",
                "original_purchase_date": _text(order.get("original_purchase_date", "")) if isinstance(order, pd.Series) else _date_text(sb.get("sellerboard_purchase_utc", "")),
                "refund_posted_date": "",
                "original_order_status": _text(order.get("original_order_status", "")) if isinstance(order, pd.Series) else _text(sb.get("local_order_status", "")),
                "original_units": _num_text(order.get("original_units", 0) if isinstance(order, pd.Series) else sb.get("sellerboard_units", 0)),
                "refund_units": _num_text(sb.get("sellerboard_units", 0)),
                "original_price_total": _num_text(order.get("original_price_total", 0) if isinstance(order, pd.Series) else 0),
                "original_price_exvat": _num_text(order.get("original_price_exvat", 0) if isinstance(order, pd.Series) else 0),
                "refund_price_total": "0",
                "refund_price_vat": "0",
                "refund_price_exvat": "0",
                "refund_shipping_total": "0",
                "refund_commission_total": "0",
                "refund_digital_fee_total": "0",
                "refund_fba_fee_total": "0",
                "refund_other_fee_total": "0",
                "return_cogs_recovered_exvat": "0",
                "refund_profit_impact_exvat": "0",
                "sellerboard_status": _text(sb.get("sellerboard_status", "")),
                "sellerboard_match_state": "sellerboard_return_unmatched_to_api_refund",
                "api_refund_proof_state": "sellerboard_bridge_only",
                "pnl_inclusion_state": "not_in_pnl_no_api_refund",
                "notes": "sellerboard_return_without_api_refund",
            }
        )
    return rows


def build_refund_bridge() -> pd.DataFrame:
    refunds = _read_csv(REFUNDS_OFFICIAL)
    orders = _load_order_summary()
    sellerboard = _load_sellerboard_rows()
    rows = _official_refund_rows(refunds, orders, sellerboard)
    api_keys = {(_text(row["order_id"]), _norm_sku(row["sku"])) for row in rows if row.get("api_refund_proof_state") == "api_proved"}
    rows.extend(_sellerboard_return_only_rows(api_keys, orders, sellerboard))
    if not rows:
        return pd.DataFrame(columns=BRIDGE_COLUMNS)
    return pd.DataFrame(rows, columns=BRIDGE_COLUMNS).fillna("")


def _window_start(asof: pd.Timestamp, window_days: int) -> pd.Timestamp:
    return asof - pd.Timedelta(days=window_days)


def build_sku_refund_rate(bridge: pd.DataFrame) -> pd.DataFrame:
    orders = _load_order_summary()
    asof = pd.Timestamp.now(tz=timezone.utc).normalize()
    if not bridge.empty:
        dates = pd.to_datetime(bridge["refund_posted_date"], errors="coerce", utc=True).dropna()
        if not dates.empty:
            asof = dates.max().normalize()

    order_work = orders.copy() if not orders.empty else pd.DataFrame()
    if not order_work.empty:
        order_work["purchase_dt"] = pd.to_datetime(order_work.get("original_purchase_date", ""), errors="coerce", utc=True)
        order_work["units_num"] = pd.to_numeric(order_work.get("original_units", 0), errors="coerce").fillna(0.0)

    bridge_work = bridge.copy() if not bridge.empty else pd.DataFrame(columns=BRIDGE_COLUMNS)
    if not bridge_work.empty:
        bridge_work["refund_dt"] = pd.to_datetime(bridge_work.get("refund_posted_date", ""), errors="coerce", utc=True)
        bridge_work["purchase_dt"] = pd.to_datetime(bridge_work.get("original_purchase_date", ""), errors="coerce", utc=True)
        bridge_work["refund_units_num"] = pd.to_numeric(bridge_work.get("refund_units", 0), errors="coerce").fillna(0.0)
        bridge_work["refund_price_num"] = pd.to_numeric(bridge_work.get("refund_price_exvat", 0), errors="coerce").fillna(0.0)
        bridge_work["refund_fee_num"] = (
            pd.to_numeric(bridge_work.get("refund_commission_total", 0), errors="coerce").fillna(0.0)
            + pd.to_numeric(bridge_work.get("refund_digital_fee_total", 0), errors="coerce").fillna(0.0)
            + pd.to_numeric(bridge_work.get("refund_fba_fee_total", 0), errors="coerce").fillna(0.0)
            + pd.to_numeric(bridge_work.get("refund_other_fee_total", 0), errors="coerce").fillna(0.0)
        )
        bridge_work["profit_impact_num"] = pd.to_numeric(bridge_work.get("refund_profit_impact_exvat", 0), errors="coerce").fillna(0.0)

    skus = sorted(
        {
            *([] if order_work.empty else [sku for sku in order_work["sku"].astype(str).tolist() if sku]),
            *([] if bridge_work.empty else [sku for sku in bridge_work["sku"].astype(str).tolist() if sku]),
        }
    )
    rows: list[dict[str, object]] = []
    for sku in skus:
        sku_orders = order_work[order_work["sku"] == sku] if not order_work.empty else pd.DataFrame()
        sku_bridge = bridge_work[bridge_work["sku"] == sku] if not bridge_work.empty else pd.DataFrame()
        for basis in ("posted_window", "sale_cohort"):
            for window_days in (30, 90):
                start = _window_start(asof, window_days)
                sales_window = sku_orders[(sku_orders["purchase_dt"] >= start) & (sku_orders["purchase_dt"] <= asof)] if not sku_orders.empty else pd.DataFrame()
                if basis == "posted_window":
                    refund_window = sku_bridge[(sku_bridge["refund_dt"] >= start) & (sku_bridge["refund_dt"] <= asof)] if not sku_bridge.empty else pd.DataFrame()
                else:
                    refund_window = sku_bridge[(sku_bridge["purchase_dt"] >= start) & (sku_bridge["purchase_dt"] <= asof)] if not sku_bridge.empty else pd.DataFrame()
                sales_units = float(sales_window["units_num"].sum()) if not sales_window.empty else 0.0
                refund_units = float(refund_window.loc[refund_window["api_refund_proof_state"] == "api_proved", "refund_units_num"].sum()) if not refund_window.empty else 0.0
                refund_orders = int(refund_window.loc[refund_window["api_refund_proof_state"] == "api_proved", "order_id"].nunique()) if not refund_window.empty else 0
                sales_orders = int(sales_window["order_id"].nunique()) if not sales_window.empty else 0
                refund_sales = float(refund_window.loc[refund_window["api_refund_proof_state"] == "api_proved", "refund_price_num"].sum()) if not refund_window.empty else 0.0
                refund_fees = float(refund_window.loc[refund_window["api_refund_proof_state"] == "api_proved", "refund_fee_num"].sum()) if not refund_window.empty else 0.0
                profit_impact = float(refund_window.loc[refund_window["api_refund_proof_state"] == "api_proved", "profit_impact_num"].sum()) if not refund_window.empty else 0.0
                bridge_only = int((refund_window["api_refund_proof_state"] == "sellerboard_bridge_only").sum()) if not refund_window.empty else 0
                refund_rate = refund_units / sales_units if sales_units > 0 else 0.0
                expected_cost = max(0.0, -profit_impact) / sales_units if sales_units > 0 else 0.0
                if bridge_only:
                    proof_state = "sellerboard_bridge_only"
                elif sales_units > 0:
                    proof_state = "api_proved_or_not_applicable"
                else:
                    proof_state = "not_yet_proven"
                if sales_units >= 30:
                    confidence = "high"
                elif sales_units >= 10:
                    confidence = "medium"
                elif sales_units > 0:
                    confidence = "low_sample"
                else:
                    confidence = "no_sales"
                rows.append(
                    {
                        "sku": sku,
                        "window_days": str(window_days),
                        "sales_units": _num_text(sales_units),
                        "refund_units": _num_text(refund_units),
                        "net_units": _num_text(sales_units - refund_units),
                        "refund_unit_rate": _num_text(refund_rate),
                        "refund_order_count": str(refund_orders),
                        "sales_order_count": str(sales_orders),
                        "refund_sales_total_gbp": _num_text(refund_sales),
                        "refund_fee_reversal_total_gbp": _num_text(refund_fees),
                        "refund_profit_impact_gbp": _num_text(profit_impact),
                        "expected_refund_cost_per_unit_gbp": _num_text(expected_cost),
                        "basis": basis,
                        "sample_confidence": confidence,
                        "proof_state": proof_state,
                    }
                )
    return pd.DataFrame(rows, columns=RATE_COLUMNS).fillna("")


def main() -> None:
    bridge = build_refund_bridge()
    rate = build_sku_refund_rate(bridge)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_to_csv(bridge, OUT_BRIDGE, index=False)
    safe_to_csv(rate, OUT_RATE, index=False)
    print(
        {
            "status": "success",
            "bridge_rows": len(bridge),
            "rate_rows": len(rate),
            "api_refund_rows": int((bridge.get("api_refund_proof_state", pd.Series(dtype=str)) == "api_proved").sum()) if not bridge.empty else 0,
            "sellerboard_bridge_rows": int((bridge.get("api_refund_proof_state", pd.Series(dtype=str)) == "sellerboard_bridge_only").sum()) if not bridge.empty else 0,
            "snapshot": str(OUT_BRIDGE),
            "rate_snapshot": str(OUT_RATE),
        }
    )


if __name__ == "__main__":
    main()
