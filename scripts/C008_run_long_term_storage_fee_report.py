"""
Fetch long-term storage fee (Aged Inventory Surcharge) report and write CSV.

Report type:
- GET_FBA_FULFILLMENT_LONGTERM_STORAGE_FEE_CHARGES_DATA

Defaults:
- Local output only (no sheets).
- Skips unless day >= 15 or LTSF_FORCE=1.
- Skips if output for the month already exists unless LTSF_FORCE=1.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple

import gzip
import pandas as pd
import requests


SPAPI_BASE_URL = os.environ.get("SPAPI_BASE_URL", "https://sellingpartnerapi-eu.amazon.com")
LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"

REPORT_TYPE = "GET_FBA_FULFILLMENT_LONGTERM_STORAGE_FEE_CHARGES_DATA"
DEFAULT_MARKETPLACE_ID = "A1F83G8C2ARO7P"
DEFAULT_POLL_INTERVAL = 20
DEFAULT_MAX_ATTEMPTS = 60
OUT_CSV = Path("out/fba_long_term_storage_fee_charges_monthly.csv")


class MissingEnvError(RuntimeError):
    pass


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise MissingEnvError(f"Missing required environment variable: {name}")
    return value


def load_dotenv_if_missing(env_files: Optional[list[str]] = None) -> None:
    env_files = env_files or ["secrets/.env", ".env"]
    for env_file in env_files:
        path = Path(env_file)
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if "#" in val:
                val = val.split("#", 1)[0].strip()
            if key and key not in os.environ:
                os.environ[key] = val


def get_lwa_access_token(refresh_token: str, client_id: str, client_secret: str) -> Tuple[str, int, str]:
    headers = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    resp = requests.post(LWA_TOKEN_URL, data=data, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"LWA token failed: {resp.status_code} {resp.text}")
    payload = resp.json()
    return payload["access_token"], int(payload.get("expires_in", 3600)), payload.get("token_type", "bearer")


def sign_headers(access_token: str, marketplace_id: str) -> dict[str, str]:
    return {
        "x-amz-access-token": access_token,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-amz-marketplace-id": marketplace_id,
    }


def create_report(access_token: str, marketplace_id: str, data_start: str, data_end: str) -> str:
    url = f"{SPAPI_BASE_URL}/reports/2021-06-30/reports"
    headers = sign_headers(access_token, marketplace_id)
    body = {
        "reportType": REPORT_TYPE,
        "marketplaceIds": [marketplace_id],
        "dataStartTime": data_start,
        "dataEndTime": data_end,
    }
    resp = requests.post(url, headers=headers, json=body, timeout=60)
    if resp.status_code not in (200, 201, 202):
        raise RuntimeError(f"Create report failed: {resp.status_code} {resp.text}")
    report_id = resp.json().get("reportId")
    if not report_id:
        raise RuntimeError(f"reportId missing in response: {resp.text}")
    return report_id


def poll_report(access_token: str, report_id: str, poll_interval: int, max_attempts: int) -> Tuple[str, int]:
    url = f"{SPAPI_BASE_URL}/reports/2021-06-30/reports/{report_id}"
    for attempt in range(1, max_attempts + 1):
        resp = requests.get(url, headers={"x-amz-access-token": access_token}, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"Poll report failed: {resp.status_code} {resp.text}")
        payload = resp.json()
        status = payload.get("processingStatus")
        if status == "DONE":
            doc_id = payload.get("reportDocumentId")
            if not doc_id:
                raise RuntimeError(f"reportDocumentId missing when status DONE: {payload}")
            return doc_id, attempt
        if status in ("CANCELLED", "FATAL"):
            raise RuntimeError(f"Report failed with status {status}: {payload}")
        time.sleep(poll_interval)
    raise RuntimeError("Report polling timed out")


def fetch_report_document(access_token: str, report_document_id: str) -> Tuple[str, Optional[str]]:
    url = f"{SPAPI_BASE_URL}/reports/2021-06-30/documents/{report_document_id}"
    resp = requests.get(url, headers={"x-amz-access-token": access_token}, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Fetch report document failed: {resp.status_code} {resp.text}")
    payload = resp.json()
    return payload["url"], payload.get("compressionAlgorithm")


def download_report(doc_url: str, compression: Optional[str]) -> bytes:
    resp = requests.get(doc_url, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Download failed: {resp.status_code}")
    raw = resp.content
    if compression == "GZIP":
        return gzip.decompress(raw)
    return raw


def _month_window() -> Tuple[str, str, str]:
    override_year = os.environ.get("LTSF_OVERRIDE_YEAR", "").strip()
    override_month = os.environ.get("LTSF_OVERRIDE_MONTH", "").strip()
    if override_year and override_month:
        year = int(override_year)
        month = int(override_month)
        first = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            next_month = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            next_month = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        last = next_month - pd.Timedelta(seconds=1)
        return (
            first.isoformat().replace("+00:00", "Z"),
            last.isoformat().replace("+00:00", "Z"),
            f"{first.year}-{first.month:02d}",
        )

    now = datetime.now(timezone.utc)
    first_this_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    last_prev_month = first_this_month - pd.Timedelta(seconds=1)
    first_prev_month = datetime(last_prev_month.year, last_prev_month.month, 1, tzinfo=timezone.utc)
    return (
        first_prev_month.isoformat().replace("+00:00", "Z"),
        last_prev_month.isoformat().replace("+00:00", "Z"),
        f"{first_prev_month.year}-{first_prev_month.month:02d}",
    )


def _get_env_pair(primary: str, fallback: str) -> str:
    return os.environ.get(primary) or os.environ.get(fallback) or ""


def main() -> None:
    load_dotenv_if_missing()
    force = os.environ.get("LTSF_FORCE", "0").strip() == "1"
    day = datetime.now(timezone.utc).day
    if day < 15 and not force:
        print({"status": "skipped", "reason": "too_early_in_month", "day": day})
        return

    data_start, data_end, ym = _month_window()
    if OUT_CSV.exists() and not force:
        print({"status": "skipped", "reason": "output_exists", "snapshot": str(OUT_CSV), "month": ym})
        return

    refresh = _get_env_pair("SPAPI_REFRESH_TOKEN", "LWA_REFRESH_TOKEN")
    client_id = _get_env_pair("SPAPI_CLIENT_ID", "LWA_CLIENT_ID")
    client_secret = _get_env_pair("SPAPI_CLIENT_SECRET", "LWA_CLIENT_SECRET")
    if not refresh:
        raise MissingEnvError("Missing required environment variable: SPAPI_REFRESH_TOKEN or LWA_REFRESH_TOKEN")
    if not client_id:
        raise MissingEnvError("Missing required environment variable: SPAPI_CLIENT_ID or LWA_CLIENT_ID")
    if not client_secret:
        raise MissingEnvError("Missing required environment variable: SPAPI_CLIENT_SECRET or LWA_CLIENT_SECRET")

    marketplace_id = os.environ.get("SPAPI_MARKETPLACE_ID", DEFAULT_MARKETPLACE_ID)

    access_token, _, _ = get_lwa_access_token(refresh, client_id, client_secret)
    report_id = create_report(access_token, marketplace_id, data_start, data_end)
    doc_id, attempts = poll_report(access_token, report_id, DEFAULT_POLL_INTERVAL, DEFAULT_MAX_ATTEMPTS)
    doc_url, compression = fetch_report_document(access_token, doc_id)
    raw_bytes = download_report(doc_url, compression)

    df = pd.read_csv(BytesIO(raw_bytes), dtype=str, sep="\t").fillna("")
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    print({"status": "success", "rows": len(df), "snapshot": str(OUT_CSV), "attempts": attempts, "month": ym})


if __name__ == "__main__":
    main()
