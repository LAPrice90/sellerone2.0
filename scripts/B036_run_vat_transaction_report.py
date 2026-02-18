"""
Request and download GET_VAT_TRANSACTION_DATA report (monthly), using RDT for document access.
Outputs raw TSV to out/reports/vat_transaction/YYYY-MM.csv and logs summary.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from io import BytesIO, StringIO
from pathlib import Path
from typing import Optional, Tuple

import gzip
import sys
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api.get_financial_events import load_dotenv_if_missing, get_lwa_access_token  # noqa: E402
from scripts.api.get_restricted_data_token import get_rdt  # noqa: E402
from scripts.api.spapi_signed import sign_spapi_request  # noqa: E402

SPAPI_BASE_URL = os.environ.get("SPAPI_BASE_URL", "https://sellingpartnerapi-eu.amazon.com")
LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
REPORT_TYPE = "GET_VAT_TRANSACTION_DATA"
DEFAULT_MARKETPLACE_ID = "A1F83G8C2ARO7P"


def create_report(access_token: str, marketplace_ids: list[str], data_start: str, data_end: str) -> str:
    url = f"{SPAPI_BASE_URL}/reports/2021-06-30/reports"
    headers = {
        "x-amz-access-token": access_token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = {
        "reportType": REPORT_TYPE,
        "marketplaceIds": marketplace_ids,
        "dataStartTime": data_start,
        "dataEndTime": data_end,
        "reportOptions": {"reportPeriod": "MONTH"},
    }
    body_str = json.dumps(body, separators=(",", ":"))
    signed = sign_spapi_request("POST", url, SPAPI_BASE_URL, headers, body=body_str)
    signed_url = signed.pop("x-signed-url", url)
    resp = requests.post(signed_url, headers=signed, data=body_str, timeout=30)
    if resp.status_code not in (200, 201, 202):
        raise RuntimeError(f"Create report failed: {resp.status_code} {resp.text}")
    payload = resp.json()
    report_id = payload.get("reportId")
    if not report_id:
        raise RuntimeError(f"reportId missing in response: {payload}")
    return report_id


def poll_report(access_token: str, report_id: str, poll_interval: int, max_attempts: int) -> Tuple[str, int]:
    url = f"{SPAPI_BASE_URL}/reports/2021-06-30/reports/{report_id}"
    headers = {"x-amz-access-token": access_token, "Accept": "application/json"}
    for attempt in range(1, max_attempts + 1):
        signed = sign_spapi_request("GET", url, SPAPI_BASE_URL, headers)
        signed_url = signed.pop("x-signed-url", url)
        resp = requests.get(signed_url, headers=signed, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"Poll failed (attempt {attempt}): {resp.status_code} {resp.text}")
        payload = resp.json()
        status = payload.get("processingStatus")
        if status == "DONE":
            doc_id = payload.get("reportDocumentId")
            if not doc_id:
                raise RuntimeError(f"reportDocumentId missing when status DONE: {payload}")
            return doc_id, attempt
        if status == "FATAL":
            raise RuntimeError(f"Report processing failed with FATAL status: {payload}")
        if attempt < max_attempts:
            time.sleep(poll_interval)
    raise TimeoutError(f"Report not DONE after {max_attempts} attempts.")


def fetch_report_document(rdt_token: str, report_document_id: str) -> Tuple[str, Optional[str]]:
    url = f"{SPAPI_BASE_URL}/reports/2021-06-30/documents/{report_document_id}"
    headers = {"x-amz-access-token": rdt_token, "Accept": "application/json"}
    signed = sign_spapi_request("GET", url, SPAPI_BASE_URL, headers)
    signed_url = signed.pop("x-signed-url", url)
    resp = requests.get(signed_url, headers=signed, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Fetch document metadata failed: {resp.status_code} {resp.text}")
    payload = resp.json()
    doc_url = payload.get("url")
    compression = payload.get("compressionAlgorithm")
    if not doc_url:
        raise RuntimeError(f"Document URL missing in response: {payload}")
    return doc_url, compression


def download_report(doc_url: str, compression: Optional[str]) -> bytes:
    resp = requests.get(doc_url, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Download failed: {resp.status_code}")
    raw_bytes = resp.content
    if compression and compression.upper() == "GZIP":
        return gzip.GzipFile(fileobj=BytesIO(raw_bytes)).read()
    if compression and compression.upper() != "GZIP":
        raise RuntimeError(f"Unsupported compressionAlgorithm: {compression}")
    return raw_bytes


def parse_tsv(raw_bytes: bytes) -> pd.DataFrame:
    last_err: Optional[Exception] = None
    for enc in ("utf-8-sig", "latin-1"):
        try:
            text = raw_bytes.decode(enc)
            df = pd.read_csv(StringIO(text), sep="\t", dtype=str, keep_default_na=False)
            break
        except Exception as exc:
            last_err = exc
            df = None
    if df is None:
        raise RuntimeError(f"Failed to parse TSV with utf-8-sig or latin-1: {last_err}")
    return df.fillna("")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch VAT Transaction Report (GET_VAT_TRANSACTION_DATA) with RDT.")
    parser.add_argument("--marketplace-id", default=os.environ.get("MARKETPLACE_ID", DEFAULT_MARKETPLACE_ID))
    parser.add_argument("--start", required=True, help="ISO start date (YYYY-MM-DD or full ISO)")
    parser.add_argument("--end", required=True, help="ISO end date (YYYY-MM-DD or full ISO)")
    parser.add_argument("--poll-interval", type=int, default=20)
    parser.add_argument("--max-attempts", type=int, default=60)
    args = parser.parse_args()

    load_dotenv_if_missing()
    access_token = get_lwa_access_token()

    # Normalize to ISO datetimes if needed
    def to_iso(d: str, end: bool = False) -> str:
        if "T" in d:
            return d
        return f"{d}T23:59:59Z" if end else f"{d}T00:00:00Z"

    data_start = to_iso(args.start, end=False)
    data_end = to_iso(args.end, end=True)

    report_id = create_report(access_token, [args.marketplace_id], data_start, data_end)
    report_document_id, attempts = poll_report(access_token, report_id, args.poll_interval, args.max_attempts)

    # RDT for document access (PII)
    rdt = get_rdt([
        {
            "method": "GET",
            "path": f"/reports/2021-06-30/documents/{report_document_id}",
        }
    ])

    doc_url, compression = fetch_report_document(rdt, report_document_id)
    raw_bytes = download_report(doc_url, compression)
    df = parse_tsv(raw_bytes)

    # Save
    out_dir = Path("out/reports/vat_transaction")
    out_dir.mkdir(parents=True, exist_ok=True)
    month_key = data_start[:7]
    out_path = out_dir / f"{month_key}.csv"
    df.to_csv(out_path, index=False)

    print(json.dumps({
        "status": "success",
        "report_id": report_id,
        "report_document_id": report_document_id,
        "attempts_used": attempts,
        "row_count": len(df),
        "snapshot": str(out_path),
    }, indent=2))


if __name__ == "__main__":
    main()
