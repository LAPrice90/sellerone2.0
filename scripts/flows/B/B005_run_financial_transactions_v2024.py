"""
Pull Finances API v2024-06-19 transactions for account-level reconciliation.

Outputs:
- out/financial_transactions_v2024_raw.csv (per-transaction)
- out/financial_transactions_v2024_breakdowns.csv (per-breakdown)
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api.get_financial_events import (  # noqa: E402
    get_lwa_access_token,
    load_dotenv_if_missing,
)

SPAPI_BASE_URL = os.environ.get("SPAPI_BASE_URL", "https://sellingpartnerapi-eu.amazon.com")
OUT_RAW = Path("out/financial_transactions_v2024_raw.csv")
OUT_BREAKDOWNS = Path("out/financial_transactions_v2024_breakdowns.csv")
MARKER_PATH = Path("out/financial_transactions_v2024_last_posted.txt")
POSTED_AFTER_ENV = os.environ.get("FIN_L5_POSTED_AFTER")
POSTED_BEFORE_ENV = os.environ.get("FIN_L5_POSTED_BEFORE")
STATEMENT_PATH_ENV = os.environ.get("FIN_L5_STATEMENT_PATH")
DO_CLEAN = os.environ.get("FIN_L5_CLEAN", "").strip() == "1"
MAX_RETRIES = int(os.environ.get("FIN_L5_MAX_RETRIES", "5"))
BASE_SLEEP = float(os.environ.get("FIN_L5_BASE_SLEEP", "1.0"))
SEED_START = datetime(2025, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
TRANSACTION_TYPES_ENV = os.environ.get("FIN_L5_TRANSACTION_TYPES", "all")
TRANSACTION_TYPE_PARAM = os.environ.get("FIN_L5_TRANSACTION_TYPE_PARAM", "transactionType")

DEFAULT_TRANSACTION_TYPES = [
    "Shipment",
    "Refund",
    "ServiceFee",
    "FBAInventoryReimbursement",
    "Retrocharge",
    "Compensation",
    "Chargeback",
    "Adjustment",
]


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_marker() -> Optional[str]:
    if POSTED_AFTER_ENV:
        return POSTED_AFTER_ENV
    if MARKER_PATH.exists():
        txt = MARKER_PATH.read_text().strip()
        if txt:
            return txt
    return None


def _save_marker(latest_iso: str) -> None:
    try:
        dt = datetime.fromisoformat(latest_iso.replace("Z", "+00:00"))
        latest_iso = _iso(dt)
    except Exception:
        pass
    MARKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = MARKER_PATH.with_name(f".{MARKER_PATH.name}.{os.getpid()}.tmp")
    last_error: OSError | None = None
    for attempt in range(1, 4):
        try:
            tmp_path.write_text(latest_iso, encoding="utf-8")
            os.replace(tmp_path, MARKER_PATH)
            return
        except OSError as exc:
            last_error = exc
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            if attempt == 3:
                raise
            time.sleep(0.25 * attempt)
    if last_error is not None:
        raise last_error


def _statement_window(path: Path) -> Tuple[Optional[str], Optional[str]]:
    if not path.exists():
        return None, None
    try:
        df = pd.read_csv(path, sep="\t", dtype=str).fillna("")
    except Exception:
        return None, None
    if "settlement-start-date" not in df.columns or "settlement-end-date" not in df.columns:
        return None, None
    for _, row in df.iterrows():
        start = str(row.get("settlement-start-date") or "").strip()
        end = str(row.get("settlement-end-date") or "").strip()
        if start and end:
            try:
                start_dt = pd.to_datetime(start, utc=True, dayfirst=True)
                end_dt = pd.to_datetime(end, utc=True, dayfirst=True)
                return _iso(start_dt.to_pydatetime()), _iso(end_dt.to_pydatetime())
            except Exception:
                return start, end
    return None, None


def _backoff_sleep(attempt: int) -> None:
    time.sleep(min(BASE_SLEEP * (2 ** (attempt - 1)), 60))


def _build_headers(token: str) -> Dict[str, str]:
    return {
        "x-amz-access-token": token,
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }


def list_transactions(
    access_token: str,
    posted_after: Optional[str] = None,
    posted_before: Optional[str] = None,
    next_token: Optional[str] = None,
    transaction_type: Optional[str] = None,
    timeout: int = 30,
) -> Tuple[List[Dict[str, object]], Optional[str]]:
    url = f"{SPAPI_BASE_URL}/finances/2024-06-19/transactions"
    params: Dict[str, object] = {}
    if next_token:
        params["nextToken"] = next_token
    else:
        if posted_after:
            params["postedAfter"] = posted_after
        if posted_before:
            params["postedBefore"] = posted_before
        if transaction_type:
            params[TRANSACTION_TYPE_PARAM] = transaction_type
    resp = requests.get(url, headers=_build_headers(access_token), params=params, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Transactions failed: {resp.status_code} {resp.text}")
    payload = resp.json() or {}
    data = payload.get("payload") or payload
    transactions = (
        data.get("transactions")
        or data.get("Transactions")
        or data.get("financialTransactions")
        or []
    )
    next_token = data.get("nextToken") or data.get("NextToken")
    if isinstance(transactions, dict):
        transactions = [transactions]
    return transactions, next_token


def _extract_amount(amount_obj: object) -> Tuple[Optional[float], Optional[str]]:
    if not isinstance(amount_obj, dict):
        return None, None
    for amt_key in ("currencyAmount", "amount", "Amount", "CurrencyAmount"):
        if amt_key in amount_obj:
            try:
                return float(amount_obj.get(amt_key)), amount_obj.get("currencyCode") or amount_obj.get("CurrencyCode")
            except Exception:
                return None, amount_obj.get("currencyCode") or amount_obj.get("CurrencyCode")
    return None, amount_obj.get("currencyCode") or amount_obj.get("CurrencyCode")


def _iter_breakdowns(breakdowns: object) -> Iterable[Dict[str, object]]:
    if isinstance(breakdowns, list):
        return breakdowns
    if isinstance(breakdowns, dict):
        return [breakdowns]
    return []


def _find_related_id(related: object, target: str) -> Optional[str]:
    if not isinstance(related, list):
        return None
    for entry in related:
        if not isinstance(entry, dict):
            continue
        name = (entry.get("relatedIdentifierName") or entry.get("identifierType") or "").upper()
        if name == target:
            return entry.get("relatedIdentifierValue") or entry.get("identifierValue")
    return None


def _json_compact(obj: object) -> str:
    try:
        return json.dumps(obj, separators=(",", ":"), ensure_ascii=True)
    except Exception:
        return ""


def main() -> None:
    load_dotenv_if_missing()

    posted_after = _load_marker() or _iso(SEED_START)
    posted_before = POSTED_BEFORE_ENV or _iso(datetime.now(timezone.utc) - timedelta(minutes=5))
    if STATEMENT_PATH_ENV:
        start, end = _statement_window(Path(STATEMENT_PATH_ENV))
        if start and end:
            posted_after = start
            posted_before = end

    if DO_CLEAN:
        for path in (OUT_RAW, OUT_BREAKDOWNS):
            if path.exists():
                path.unlink()

    access_token = get_lwa_access_token()
    all_transactions: List[Dict[str, object]] = []
    attempt = 0

    tx_types: List[str] = []
    if TRANSACTION_TYPES_ENV.strip():
        if TRANSACTION_TYPES_ENV.strip().lower() == "all":
            tx_types = []
        else:
            tx_types = [t.strip() for t in TRANSACTION_TYPES_ENV.split(",") if t.strip()]
    else:
        tx_types = list(DEFAULT_TRANSACTION_TYPES)

    type_filters = tx_types if tx_types else [None]
    for tx_type in type_filters:
        next_token: Optional[str] = None
        while True:
            try:
                attempt += 1
                batch, next_token = list_transactions(
                    access_token,
                    posted_after=posted_after,
                    posted_before=posted_before,
                    next_token=next_token,
                    transaction_type=tx_type,
                )
                all_transactions.extend(batch)
                time.sleep(BASE_SLEEP)
                if not next_token:
                    break
            except RuntimeError as exc:
                msg = str(exc).lower()
                if "unauthorized" in msg or "invalid access token" in msg or "expired" in msg:
                    access_token = get_lwa_access_token()
                    attempt = 0
                    continue
                if "429" in msg or "quota" in msg or "too many" in msg or "5" in msg:
                    if attempt <= MAX_RETRIES:
                        _backoff_sleep(attempt)
                        continue
                raise

    rows: List[Dict[str, object]] = []
    breakdown_rows: List[Dict[str, object]] = []
    latest_posted: Optional[datetime] = None

    for txn in all_transactions:
        if not isinstance(txn, dict):
            continue
        posted_date = txn.get("postedDate") or txn.get("postedDateTime")
        if posted_date:
            try:
                dt = datetime.fromisoformat(str(posted_date).replace("Z", "+00:00"))
                if not latest_posted or dt > latest_posted:
                    latest_posted = dt
            except Exception:
                pass
        total_amount, currency = _extract_amount(txn.get("totalAmount") or txn.get("amount"))
        related = txn.get("relatedIdentifiers") or []
        inbound_id = _find_related_id(related, "FBA_SHIPMENT_ID")
        rows.append(
            {
                "posted_date": posted_date,
                "transaction_type": txn.get("transactionType"),
                "transaction_id": txn.get("transactionId"),
                "description": txn.get("description"),
                "total_amount": total_amount,
                "currency": currency,
                "status": txn.get("status"),
                "marketplace_id": txn.get("marketplaceId"),
                "inbound_shipment_id": inbound_id,
                "related_identifiers": _json_compact(related),
                "breakdowns": _json_compact(txn.get("breakdowns") or []),
            }
        )

        for br in _iter_breakdowns(txn.get("breakdowns")):
            br_amount, br_currency = _extract_amount(br.get("breakdownAmount") or br.get("amount"))
            breakdown_rows.append(
                {
                    "posted_date": posted_date,
                    "transaction_id": txn.get("transactionId"),
                    "transaction_type": txn.get("transactionType"),
                    "breakdown_type": br.get("breakdownType"),
                    "breakdown_amount": br_amount,
                    "breakdown_currency": br_currency,
                    "description": txn.get("description"),
                    "inbound_shipment_id": inbound_id,
                }
            )

    df_raw = pd.DataFrame(rows)
    if not df_raw.empty:
        df_raw = df_raw.drop_duplicates(subset=["transaction_id", "transaction_type", "posted_date", "total_amount", "currency"])
    df_breakdowns = pd.DataFrame(breakdown_rows)
    if not df_breakdowns.empty:
        df_breakdowns = df_breakdowns.drop_duplicates(
            subset=["transaction_id", "transaction_type", "breakdown_type", "breakdown_amount", "breakdown_currency", "posted_date"]
        )
    OUT_RAW.parent.mkdir(parents=True, exist_ok=True)
    df_raw.to_csv(OUT_RAW, index=False)
    df_breakdowns.to_csv(OUT_BREAKDOWNS, index=False)

    if latest_posted:
        _save_marker(_iso(latest_posted))

    print(
        {
            "status": "success",
            "posted_after": posted_after,
            "posted_before": posted_before,
            "rows_raw": len(df_raw),
            "rows_breakdowns": len(df_breakdowns),
            "latest_posted_saved": _iso(latest_posted) if latest_posted else None,
            "snapshot": f"{OUT_RAW};{OUT_BREAKDOWNS}",
        }
    )


if __name__ == "__main__":
    main()


