"""
Build VAT control reports (daily + monthly) from existing ledgers.

Outputs:
- out/vat_report_daily.csv
- out/vat_report_monthly.csv
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

import pandas as pd
from scripts.core.safe_file_writes import safe_to_csv
try:
    import gspread
    from gspread.exceptions import APIError
except Exception:
    gspread = None
    APIError = Exception
from pandas.errors import EmptyDataError

ORDER_LEDGER_FX = Path("out/order_ledger_fx.csv")
REFUNDS_OFFICIAL = Path("out/financial_events_refunds_official.csv")
FEE_VAT_LEDGER = Path("out/fee_vat_ledger.csv")
FEE_DETAIL_LEDGER_API = Path("out/fee_detail_ledger_api.csv")
L3_RAW = Path("out/financial_events_level3_raw.csv")

OUT_DAILY = Path("out/vat_report_daily.csv")
OUT_MONTHLY = Path("out/vat_report_monthly.csv")

PNL_START_DATE = os.environ.get("PNL_START_DATE", "2025-11-01")
SHEET_ID = os.environ.get("PNL_SHEET_ID", "1aT26UYnTBP6-oNz0RIWVCRbuuN1RmP4_VwHEeiNzxKc")
TAB_DAILY = os.environ.get("VAT_REPORT_DAILY_TAB", "VAT_Report_Daily")
TAB_MONTHLY = os.environ.get("VAT_REPORT_MONTHLY_TAB", "VAT_Report_Monthly")
SETTLEMENT_PATH_ENV = os.environ.get("VAT_SETTLEMENT_PATH", "")
VAT_REPORT_WRITE_SHEETS = os.environ.get("VAT_REPORT_WRITE_SHEETS", "1").strip() == "1"

SHEETS_MAX_RETRIES = 5
SHEETS_BACKOFF = 2.0


def _date_key(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True).dt.strftime("%Y-%m-%d")


def _to_num(series: pd.Series) -> pd.Series:
    if series is None:
        return pd.Series(dtype=float)
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def _add(mapper: Dict[str, Dict[str, float]], key: str, date_str: str, val: float) -> None:
    if key not in mapper:
        mapper[key] = {}
    mapper[key][date_str] = mapper[key].get(date_str, 0.0) + val


def _write_tab_with_retry(sheet: gspread.Spreadsheet, tab_name: str, df: pd.DataFrame) -> None:
    payload = [list(df.columns)] + df.where(pd.notnull(df), "").values.tolist()
    for attempt in range(1, SHEETS_MAX_RETRIES + 1):
        try:
            try:
                ws = sheet.worksheet(tab_name)
            except gspread.WorksheetNotFound:
                ws = sheet.add_worksheet(title=tab_name, rows=max(len(payload) + 10, 2000), cols=max(len(df.columns) + 5, 40))
            else:
                ws.clear()
            ws.update(range_name="A1", values=payload, value_input_option="USER_ENTERED")
            return
        except APIError:
            if attempt == SHEETS_MAX_RETRIES:
                raise
            import time

            time.sleep(SHEETS_BACKOFF * attempt)


def _apply_settlement_vat(data: Dict[str, Dict[str, float]], path: Path) -> None:
    if not path.exists():
        return
    df = pd.read_csv(path, sep="\t", dtype=str).fillna("")
    if df.empty:
        return
    df["posted_date"] = pd.to_datetime(
        df["posted-date-time"].where(df["posted-date-time"] != "", df["posted-date"]),
        errors="coerce",
        dayfirst=True,
        utc=True,
    ).dt.strftime("%Y-%m-%d")
    df = df[df["posted_date"].astype(str) >= PNL_START_DATE]
    df["amount"] = _to_num(df.get("amount"))

    vat_lines = df[
        (df["amount-type"] == "ItemPrice")
        & (df["amount-description"].isin(["Tax", "ShippingTax"]))
    ]
    promo_lines = df[
        (df["amount-type"] == "Promotion")
        & (df["amount-description"] == "TaxDiscount")
    ]
    vat_lines = pd.concat([vat_lines, promo_lines], ignore_index=True)

    order_vat = vat_lines[vat_lines["transaction-type"] == "Order"]
    refund_vat = vat_lines[vat_lines["transaction-type"] == "Refund"]
    withheld = df[
        df["amount-description"].str.contains("MarketplaceFacilitatorVAT", case=False, na=False)
    ]

    settlement_dates = set(vat_lines["posted_date"].dropna().unique())
    settlement_dates |= set(withheld["posted_date"].dropna().unique())

    for d in settlement_dates:
        if d:
            data.setdefault("Output_VAT", {})[d] = 0.0
            data.setdefault("Refund_VAT", {})[d] = 0.0
            data.setdefault("Withheld_VAT", {})[d] = 0.0

    for date_str, val in order_vat["amount"].groupby(order_vat["posted_date"]).sum().items():
        data.setdefault("Output_VAT", {})[date_str] = float(val)
    for date_str, val in refund_vat["amount"].groupby(refund_vat["posted_date"]).sum().items():
        data.setdefault("Refund_VAT", {})[date_str] = float(val)
    for date_str, val in withheld["amount"].groupby(withheld["posted_date"]).sum().items():
        data.setdefault("Withheld_VAT", {})[date_str] = float(val)


def main() -> None:
    data: Dict[str, Dict[str, float]] = {}

    used_l3_output_vat = False

    if L3_RAW.exists() and not SETTLEMENT_PATH_ENV:
        raw = pd.read_csv(L3_RAW, dtype=str).fillna("")
        if not raw.empty:
            raw["date"] = _date_key(raw.get("posted_date"))
            raw = raw[raw["date"].astype(str) >= PNL_START_DATE]
            raw["amount"] = _to_num(raw.get("amount"))
            raw = raw[raw.get("currency") == "GBP"]

            tax_types = ["Tax", "ShippingTax", "GiftWrapTax"]
            refund_tax_types = ["Refund_Tax", "Refund_ShippingTax", "Refund_GiftWrapTax"]

            output = raw[raw["amount_type"].isin(tax_types)]
            refunds = raw[raw["amount_type"].isin(refund_tax_types)]

            if not output.empty or not refunds.empty:
                used_l3_output_vat = True
                for date_str, val in output["amount"].groupby(output["date"]).sum().items():
                    _add(data, "Output_VAT", date_str, float(val))
                for date_str, val in refunds["amount"].groupby(refunds["date"]).sum().items():
                    _add(data, "Refund_VAT", date_str, float(val))

    if ORDER_LEDGER_FX.exists() and not used_l3_output_vat:
        df = pd.read_csv(ORDER_LEDGER_FX, dtype=str).fillna("")
        df["date"] = _date_key(df["Date"])
        df = df[df["date"].astype(str) >= PNL_START_DATE]
        df["Price_VAT_GBP"] = _to_num(df.get("Price_VAT_GBP"))
        df["Shipping_VAT_GBP"] = _to_num(df.get("Shipping_VAT_GBP"))
        df["Gift_VAT_GBP"] = _to_num(df.get("Gift_VAT_GBP"))
        df["Promotion_VAT_GBP"] = _to_num(df.get("Promotion_VAT_GBP"))
        df["FBA_Fee_VAT_GBP"] = _to_num(df.get("FBA_Fee_VAT_GBP"))
        df["Commission_VAT_GBP"] = _to_num(df.get("Commission_VAT_GBP"))
        df["Digital_Fee_VAT_GBP"] = _to_num(df.get("Digital_Fee_VAT_GBP"))
        df["FixedClosingFee_VAT_GBP"] = _to_num(df.get("FixedClosingFee_VAT_GBP"))

        output_vat = df["Price_VAT_GBP"] + df["Shipping_VAT_GBP"] + df["Gift_VAT_GBP"] + df["Promotion_VAT_GBP"]
        input_vat = (
            df["FBA_Fee_VAT_GBP"]
            + df["Commission_VAT_GBP"]
            + df["Digital_Fee_VAT_GBP"]
            + df["FixedClosingFee_VAT_GBP"]
        )
        for date_str, val in output_vat.groupby(df["date"]).sum().items():
            _add(data, "Output_VAT", date_str, float(val))
        for date_str, val in input_vat.groupby(df["date"]).sum().items():
            _add(data, "Input_VAT_Order_Fees", date_str, float(val))

    if REFUNDS_OFFICIAL.exists() and not used_l3_output_vat:
        ref = pd.read_csv(REFUNDS_OFFICIAL, dtype=str).fillna("")
        if not ref.empty:
            ref["date"] = _date_key(ref["Date"])
            ref = ref[ref["date"].astype(str) >= PNL_START_DATE]
            ref["Price_VAT"] = _to_num(ref.get("Price_VAT"))
            ref["Shipping_VAT"] = _to_num(ref.get("Shipping_VAT"))
            ref["Gift_VAT"] = _to_num(ref.get("Gift_VAT"))
            ref["Promotion_VAT"] = _to_num(ref.get("Promotion_VAT"))
            refund_vat = ref["Price_VAT"] + ref["Shipping_VAT"] + ref["Gift_VAT"] + ref["Promotion_VAT"]
            for date_str, val in refund_vat.groupby(ref["date"]).sum().items():
                _add(data, "Refund_VAT", date_str, float(val))

    if FEE_VAT_LEDGER.exists():
        fee = pd.read_csv(FEE_VAT_LEDGER, dtype=str).fillna("")
        if not fee.empty:
            fee["date"] = _date_key(fee.get("posted_date"))
            fee = fee[fee["date"].astype(str) >= PNL_START_DATE]
            fee["amount_vat"] = _to_num(fee.get("amount_vat"))
            for date_str, val in fee["amount_vat"].groupby(fee["date"]).sum().items():
                _add(data, "Input_VAT_Service_Fees", date_str, float(val))
            if "vat_source" in fee.columns:
                missing = fee[fee["vat_source"].astype(str).str.lower() == "missing"].copy()
                missing["amount_total"] = _to_num(missing.get("amount_total"))
                for date_str, val in missing["amount_total"].groupby(missing["date"]).sum().items():
                    _add(data, "VAT_Missing_Bucket", date_str, float(val))

    if FEE_DETAIL_LEDGER_API.exists():
        try:
            api_fee = pd.read_csv(FEE_DETAIL_LEDGER_API, dtype=str).fillna("")
        except EmptyDataError:
            api_fee = pd.DataFrame()
        if not api_fee.empty:
            api_fee["date"] = _date_key(api_fee.get("posted_date"))
            api_fee = api_fee[api_fee["date"].astype(str) >= PNL_START_DATE]
            api_fee["amount_total"] = _to_num(api_fee.get("amount_total"))
            api_fee["non_gbp_api_only"] = api_fee.get("non_gbp_api_only").astype(str).str.lower().eq("true")
            non_gbp = api_fee[api_fee["non_gbp_api_only"]]
            for date_str, val in non_gbp["amount_total"].groupby(non_gbp["date"]).sum().items():
                _add(data, "Non_GBP_Service_Fees", date_str, float(val))

    if SETTLEMENT_PATH_ENV:
        _apply_settlement_vat(data, Path(SETTLEMENT_PATH_ENV))

    if L3_RAW.exists() and not SETTLEMENT_PATH_ENV:
        raw = pd.read_csv(L3_RAW, dtype=str).fillna("")
        if not raw.empty:
            raw["date"] = _date_key(raw.get("posted_date"))
            raw = raw[raw["date"].astype(str) >= PNL_START_DATE]
            raw = raw[raw["amount_type"].isin(["MarketplaceFacilitatorVAT-Principal", "MarketplaceFacilitatorVAT-Shipping"])]
            raw["amount"] = _to_num(raw.get("amount"))
            raw = raw[raw.get("currency") == "GBP"]
            for date_str, val in raw["amount"].groupby(raw["date"]).sum().items():
                _add(data, "Withheld_VAT", date_str, float(val))

    all_dates = sorted({d for row in data.values() for d in row.keys()})
    rows: List[Dict[str, object]] = []
    for key in [
        "Output_VAT",
        "Refund_VAT",
        "Input_VAT_Order_Fees",
        "Input_VAT_Service_Fees",
        "VAT_Missing_Bucket",
        "Non_GBP_Service_Fees",
        "Withheld_VAT",
    ]:
        row: Dict[str, object] = {"Parameter/Date": key}
        total = 0.0
        for d in all_dates:
            val = data.get(key, {}).get(d, 0.0)
            row[d] = round(val, 2)
            total += val
        row["Total"] = round(total, 2)
        rows.append(row)

    net_row = {"Parameter/Date": "Net_VAT_Payable"}
    total_net = 0.0
    for d in all_dates:
        def v(k: str) -> float:
            return float(data.get(k, {}).get(d, 0.0))
        net = v("Output_VAT") + v("Refund_VAT") - v("Input_VAT_Order_Fees") - v("Input_VAT_Service_Fees") + v("Withheld_VAT")
        net_row[d] = round(net, 2)
        total_net += net
    net_row["Total"] = round(total_net, 2)
    rows.append(net_row)

    daily = pd.DataFrame(rows, columns=["Parameter/Date"] + all_dates + ["Total"])
    OUT_DAILY.parent.mkdir(parents=True, exist_ok=True)
    safe_to_csv(daily, OUT_DAILY, index=False)

    # Monthly rollup
    month_cols = sorted({d[:7] for d in all_dates})
    month_rows: List[Dict[str, object]] = []
    for _, row in daily.iterrows():
        out_row: Dict[str, object] = {"Line Item": row.get("Parameter/Date", "")}
        total = 0.0
        for month in month_cols:
            val = 0.0
            for d in all_dates:
                if d.startswith(month):
                    val += float(row.get(d, 0.0) or 0.0)
            out_row[month] = round(val, 2)
            total += val
        out_row["Total"] = round(total, 2)
        month_rows.append(out_row)
    monthly = pd.DataFrame(month_rows, columns=["Line Item"] + month_cols + ["Total"])
    safe_to_csv(monthly, OUT_MONTHLY, index=False)

    if VAT_REPORT_WRITE_SHEETS:
        try:
            if gspread is None:
                raise RuntimeError("gspread not available")
            client = gspread.service_account(filename=str(Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json"))
            sheet = client.open_by_key(SHEET_ID)
            _write_tab_with_retry(sheet, TAB_DAILY, daily)
            _write_tab_with_retry(sheet, TAB_MONTHLY, monthly)
        except Exception as exc:
            print({"status": "warning", "alert": "sheets_error", "error": str(exc)})

    print({"status": "success", "daily": str(OUT_DAILY), "monthly": str(OUT_MONTHLY), "write_sheets": VAT_REPORT_WRITE_SHEETS})


if __name__ == "__main__":
    main()

