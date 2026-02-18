"""
One-off 24h pull of posted financial events for inspection.

- No markers, no sheet writes.
- Paces under 2 RPS, retries on 429/5xx, refreshes token on 401.
- Outputs:
    out/financial_events_test_raw.csv   (flattened charges/fees with tax fields)
    out/financial_events_test_summary.csv (per order amount_type totals, with tax-present flags)
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api.get_financial_events import (  # noqa: E402
    get_lwa_access_token,
    list_financial_events,
    load_dotenv_if_missing,
)

OUT_RAW = Path("out/financial_events_test_raw.csv")
OUT_SUM = Path("out/financial_events_test_summary.csv")
MAX_RETRIES = 5
BASE_SLEEP = 1.0  # seconds between pages to stay <2 RPS


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _backoff_sleep(attempt: int) -> None:
    time.sleep(min(BASE_SLEEP * (2 ** (attempt - 1)), 60))


def flatten_events(events: Dict[str, object]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []

    def add_row(order_id: str, asin: str, sku: str, posted: str, kind: str, amt: Dict[str, object], is_fee: bool, tax: Optional[Dict[str, object]] = None) -> None:
        rows.append(
            {
                "order_id": order_id,
                "asin": asin,
                "sku": sku,
                "posted_date": posted,
                "amount_type": kind,
                "is_fee": is_fee,
                "amount": (amt or {}).get("Amount", ""),
                "currency": (amt or {}).get("CurrencyCode", ""),
                "tax_amount": (tax or {}).get("Amount", ""),
                "tax_currency": (tax or {}).get("CurrencyCode", ""),
            }
        )

    shipments = events.get("ShipmentEventList") or []
    for ev in shipments:
        order_id = ev.get("AmazonOrderId", "")
        posted_date = ev.get("PostedDate", "")
        for item in ev.get("ShipmentItemList") or []:
            asin = item.get("ASIN", "")
            sku = item.get("SellerSKU", "")
            for charge in item.get("ItemChargeList") or []:
                add_row(order_id, asin, sku, posted_date, charge.get("ChargeType", ""), charge.get("ChargeAmount"), False)
            for charge_adj in item.get("ItemChargeAdjustmentList") or []:
                add_row(order_id, asin, sku, posted_date, charge_adj.get("ChargeType", ""), charge_adj.get("ChargeAmount"), False)
            for fee in item.get("ItemFeeList") or []:
                add_row(order_id, asin, sku, posted_date, fee.get("FeeType", ""), fee.get("FeeAmount"), True)
            for fee_adj in item.get("ItemFeeAdjustmentList") or []:
                add_row(order_id, asin, sku, posted_date, fee_adj.get("FeeType", ""), fee_adj.get("FeeAmount"), True)
            # ItemTax withheld separately in some cases
            for tax in item.get("ItemTaxWithheldList") or []:
                add_row(order_id, asin, sku, posted_date, tax.get("TaxType", ""), tax.get("Amount"), False)

    refunds = events.get("RefundEventList") or []
    for ev in refunds:
        order_id = ev.get("AmazonOrderId", "")
        posted_date = ev.get("PostedDate", "")
        for item in ev.get("ShipmentItemAdjustmentList") or []:
            asin = item.get("ASIN", "")
            sku = item.get("SellerSKU", "")
            for charge in item.get("ItemChargeAdjustmentList") or []:
                add_row(order_id, asin, sku, posted_date, f"Refund_{charge.get('ChargeType', '')}", charge.get("ChargeAmount"), False)
            for fee in item.get("ItemFeeAdjustmentList") or []:
                add_row(order_id, asin, sku, posted_date, f"Refund_{fee.get('FeeType', '')}", fee.get("FeeAmount"), True)
            for tax in item.get("ItemTaxWithheldList") or []:
                add_row(order_id, asin, sku, posted_date, f"Refund_{tax.get('TaxType', '')}", tax.get("Amount"), False)

    return rows


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["order_id", "amount_type", "is_fee", "total_amount", "tax_present", "currency"])
    df["tax_present"] = df["tax_amount"].apply(lambda v: str(v).strip() not in ("", "nan", "None"))
    group = df.groupby(["order_id", "amount_type", "is_fee", "currency"], dropna=False)
    agg = group.agg(
        total_amount=pd.NamedAgg(column="amount", aggfunc=lambda s: sum(float(x) for x in s if str(x).strip() not in ("", "nan", "None"))),
        tax_present=pd.NamedAgg(column="tax_present", aggfunc=lambda s: any(s)),
    ).reset_index()
    return agg[["order_id", "amount_type", "is_fee", "total_amount", "tax_present", "currency"]]


def fetch_window(posted_after: str, posted_before: Optional[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    load_dotenv_if_missing()
    token = get_lwa_access_token()

    raw_rows: List[Dict[str, object]] = []
    next_token = None
    page = 0
    while True:
        page += 1
        attempt = 0
        while True:
            attempt += 1
            try:
                events_batch, next_token = list_financial_events(
                    access_token=token,
                    posted_after=posted_after,
                    posted_before=posted_before,
                    next_token=next_token,
                )
                break
            except Exception as exc:
                msg = str(exc).lower()
                if any(code in msg for code in ["unauthorized", "invalid access token", "expired"]):
                    token = get_lwa_access_token()
                if attempt >= MAX_RETRIES:
                    raise
                _backoff_sleep(attempt)
                continue
        # pace to stay under 2 RPS
        time.sleep(BASE_SLEEP)

        raw_rows.extend(flatten_events(events_batch))
        if not next_token:
            break

    df_raw = pd.DataFrame(raw_rows)
    df_sum = summarize(df_raw)
    return df_raw, df_sum


def main() -> None:
    now = datetime.now(timezone.utc)
    # SP-API requires posted_before not to exceed "now"; keep a small safety buffer
    posted_before_dt = now - timedelta(minutes=5)
    posted_after_dt = posted_before_dt - timedelta(days=1)
    posted_before = _iso(posted_before_dt)
    posted_after = _iso(posted_after_dt)

    df_raw, df_sum = fetch_window(posted_after, posted_before)
    OUT_RAW.parent.mkdir(parents=True, exist_ok=True)
    df_raw.to_csv(OUT_RAW, index=False)
    df_sum.to_csv(OUT_SUM, index=False)
    print(
        {
            "status": "success",
            "posted_after": posted_after,
            "posted_before": posted_before,
            "rows_raw": len(df_raw),
            "rows_summary": len(df_sum),
            "snapshot": f"{OUT_RAW};{OUT_SUM}",
        }
    )


if __name__ == "__main__":
    main()
