"""
Fetch GET_MERCHANT_LISTINGS_ALL_DATA via SP-API, with a fast test mode.

Workflow (live mode):
1) Exchange LWA refresh token for access_token.
2) Create report (POST /reports/2021-06-30/reports).
3) Poll report until processingStatus == DONE (raise if FATAL).
4) Fetch report document metadata to get URL + compressionAlgorithm.
5) Download document, decompress if GZIP.
6) Parse TSV into a pandas DataFrame (no column drops/renames).
7) Return a dict: {"timestamp", "row_count", "columns", "data"}.

Test mode (mandatory):
- --test-mode skips API calls, loads a local TSV file, and processes the first
  10 rows for a fast validation.

No Google Sheets writes. No database writes.
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
import pandas as pd
import requests
from requests.exceptions import RequestException

SPAPI_BASE_URL = os.environ.get("SPAPI_BASE_URL", "https://sellingpartnerapi-eu.amazon.com")
LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"


class MissingEnvError(RuntimeError):
    pass


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise MissingEnvError(f"Missing required environment variable: {name}")
    return value


def load_dotenv_if_missing(env_files: Optional[list[str]] = None) -> None:
    """
    Lightweight .env loader to populate os.environ if keys are missing.
    It does not overwrite existing env vars. Comment lines and blanks are ignored.
    """
    env_files = env_files or ["secrets/.env", ".env"]
    for env_file in env_files:
        path = Path(env_file)
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            # Strip inline comments marked with #
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
        raise RuntimeError(f"LWA token request failed: {resp.status_code} {resp.text}")

    payload = resp.json()
    access_token = payload.get("access_token")
    expires_in = payload.get("expires_in")
    token_type = payload.get("token_type")
    if not access_token:
        raise RuntimeError(f"LWA token missing in response: {payload}")
    return access_token, int(expires_in or 0), token_type or ""


def get_lwa_access_token_with_retry(refresh_token: str, client_id: str, client_secret: str, attempts: int = 3, backoff: float = 2.0) -> Tuple[str, int, str]:
    last_err: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            return get_lwa_access_token(refresh_token, client_id, client_secret)
        except RequestException as exc:
            last_err = exc
            if i < attempts:
                time.sleep(backoff * i)
        except Exception as exc:
            # For non-network failures, surface immediately
            last_err = exc
            break
    raise RuntimeError(f"LWA token request failed after {attempts} attempts: {last_err}")


def create_report(access_token: str, marketplace_id: str) -> str:
    url = f"{SPAPI_BASE_URL}/reports/2021-06-30/reports"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "x-amz-access-token": access_token,
        "Content-Type": "application/json",
    }
    body = {"reportType": "GET_MERCHANT_LISTINGS_ALL_DATA", "marketplaceIds": [marketplace_id]}
    resp = requests.post(url, headers=headers, json=body, timeout=30)
    if resp.status_code not in (200, 201, 202):
        raise RuntimeError(f"Create report failed: {resp.status_code} {resp.text}")
    payload = resp.json()
    report_id = payload.get("reportId")
    if not report_id:
        raise RuntimeError(f"reportId missing in response: {payload}")
    return report_id


def poll_report(access_token: str, report_id: str, poll_interval: int, max_attempts: int) -> Tuple[str, int]:
    url = f"{SPAPI_BASE_URL}/reports/2021-06-30/reports/{report_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "x-amz-access-token": access_token,
    }

    for attempt in range(1, max_attempts + 1):
        resp = requests.get(url, headers=headers, timeout=30)
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


def fetch_report_document(access_token: str, report_document_id: str) -> Tuple[str, Optional[str]]:
    url = f"{SPAPI_BASE_URL}/reports/2021-06-30/documents/{report_document_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "x-amz-access-token": access_token,
    }
    resp = requests.get(url, headers=headers, timeout=30)
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


def parse_tsv(raw_bytes: bytes, limit_rows: Optional[int] = None) -> pd.DataFrame:
    last_err: Optional[Exception] = None
    for enc in ("utf-8-sig", "latin-1"):
        try:
            text = raw_bytes.decode(enc)
            df = pd.read_csv(StringIO(text), sep="\t", dtype=str, keep_default_na=False)
            break
        except Exception as exc:  # pragma: no cover - robustness path
            last_err = exc
            df = None
    if df is None:
        raise RuntimeError(f"Failed to parse TSV with utf-8-sig or latin-1: {last_err}")

    if limit_rows is not None:
        df = df.head(limit_rows)
    df = df.fillna("")
    return df


def load_local_sample(path: Path, limit_rows: int) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Sample TSV not found: {path}")
    raw_bytes = path.read_bytes()
    return parse_tsv(raw_bytes, limit_rows=limit_rows)


def run_live(
    marketplace_id: str,
    poll_interval: int,
    max_attempts: int,
) -> dict:
    load_dotenv_if_missing()
    refresh_token = require_env("LWA_REFRESH_TOKEN")
    client_id = require_env("LWA_CLIENT_ID")
    client_secret = require_env("LWA_CLIENT_SECRET")

    access_token, expires_in, token_type = get_lwa_access_token_with_retry(refresh_token, client_id, client_secret)
    report_id = create_report(access_token, marketplace_id)
    report_document_id, attempts_used = poll_report(access_token, report_id, poll_interval=poll_interval, max_attempts=max_attempts)
    doc_url, compression = fetch_report_document(access_token, report_document_id)
    raw_bytes = download_report(doc_url, compression)
    df = parse_tsv(raw_bytes, limit_rows=None)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "row_count": len(df),
        "columns": list(df.columns),
        "attempts_used": attempts_used,
        "data": df,
    }


def run_test(sample_path: Path) -> dict:
    df = load_local_sample(sample_path, limit_rows=10)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "row_count": len(df),
        "columns": list(df.columns),
        "data": df,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch GET_MERCHANT_LISTINGS_ALL_DATA report or process a local sample in test mode.")
    parser.add_argument("--test-mode", action="store_true", help="Use local sample TSV and skip API calls.")
    parser.add_argument(
        "--sample-path",
        default="tests/data/sample_get_merchant_listings.tsv",
        help="Path to local TSV for test mode.",
    )
    parser.add_argument("--marketplace-id", default=os.environ.get("MARKETPLACE_ID"), help="Marketplace ID (default: env MARKETPLACE_ID).")
    parser.add_argument("--poll-interval", type=int, default=20, help="Seconds between poll attempts (default: 20).")
    parser.add_argument("--max-attempts", type=int, default=40, help="Max poll attempts before timeout (default: 40).")

    args = parser.parse_args()

    if args.test_mode:
        result = run_test(Path(args.sample_path))
    else:
        if not args.marketplace_id:
            load_dotenv_if_missing()
            args.marketplace_id = os.environ.get("MARKETPLACE_ID")
        if not args.marketplace_id:
            raise MissingEnvError("MARKETPLACE_ID must be provided via --marketplace-id or env.")
        result = run_live(
            marketplace_id=args.marketplace_id,
            poll_interval=args.poll_interval,
            max_attempts=args.max_attempts,
        )

    # Minimal stdout summary; DataFrame remains in result["data"] for further use.
    print(json.dumps({
        "timestamp": result["timestamp"],
        "row_count": result["row_count"],
        "columns": result["columns"],
    }, indent=2))


if __name__ == "__main__":
    main()

