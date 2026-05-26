"""
Fetch inbound shipment contents via Reports API and build inbound_shipment_contents.csv.

Outputs:
- out/inbound_shipment_contents.csv (inbound_shipment_id, sku, quantity)
- out/inbound_shipment_contents_raw.csv (raw report rows)
"""

from __future__ import annotations

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

import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api.spapi_signed import sign_spapi_request
from scripts.core.storage import StorageConfig, connect_store, parse_storage_mode, replace_table_from_dataframe

SPAPI_BASE_URL = os.environ.get("SPAPI_BASE_URL", "https://sellingpartnerapi-eu.amazon.com")
LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"

REPORT_TYPE = os.environ.get("FIN_INBOUND_REPORT_TYPE", "")
ALLOWED_REPORT_TYPES = {
    "GET_FBA_INBOUND_SHIPMENT_DETAIL_DATA",
    "GET_FBA_INBOUND_SHIPMENT_DATA",
}


def _normalize_report_type(raw: str) -> str:
    cleaned = raw.strip().strip("_").upper()
    return cleaned


raw_report_types = [
    t.strip()
    for t in (
        REPORT_TYPE
        or os.environ.get("FIN_INBOUND_REPORT_TYPES", "")
        or "GET_FBA_INBOUND_SHIPMENT_DETAIL_DATA,GET_FBA_INBOUND_SHIPMENT_DATA"
    ).split(",")
    if t.strip()
]

REPORT_TYPES = [t for t in (_normalize_report_type(rt) for rt in raw_report_types) if t in ALLOWED_REPORT_TYPES]
if not REPORT_TYPES:
    REPORT_TYPES = ["GET_FBA_INBOUND_SHIPMENT_DETAIL_DATA", "GET_FBA_INBOUND_SHIPMENT_DATA"]
MARKETPLACE_ID = os.environ.get("MARKETPLACE_ID")

OUT_RAW = Path("out/inbound_shipment_contents_raw.csv")
OUT_MAP = Path("out/inbound_shipment_contents.csv")
SQL_TABLE_INBOUND_SHIPMENT_CONTENTS_RAW = "sys_inbound_shipment_contents_raw"
SQL_TABLE_INBOUND_SHIPMENT_CONTENTS = "sys_inbound_shipment_contents"


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
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
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
        raise RuntimeError(f"LWA token request failed: {resp.status_code} {resp.text}")
    payload = resp.json()
    access_token = payload.get("access_token")
    expires_in = payload.get("expires_in")
    token_type = payload.get("token_type")
    if not access_token:
        raise RuntimeError(f"LWA token missing in response: {payload}")
    return access_token, int(expires_in or 0), token_type or ""


def create_report(access_token: str, marketplace_id: str, report_type: str) -> str:
    url = f"{SPAPI_BASE_URL}/reports/2021-06-30/reports"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "x-amz-access-token": access_token,
        "Content-Type": "application/json",
    }
    body = json.dumps({"reportType": report_type, "marketplaceIds": [marketplace_id]})
    signed = sign_spapi_request("POST", url, SPAPI_BASE_URL, headers, body=body)
    signed_url = signed.pop("x-signed-url", url)
    resp = requests.post(signed_url, headers=signed, data=body, timeout=30)
    if resp.status_code not in (200, 201, 202):
        raise RuntimeError(f"Create report failed: {resp.status_code} {resp.text}")
    payload = resp.json()
    report_id = payload.get("reportId")
    if not report_id:
        raise RuntimeError(f"reportId missing in response: {payload}")
    return report_id


def poll_report(access_token: str, report_id: str, poll_interval: int, max_attempts: int) -> str:
    url = f"{SPAPI_BASE_URL}/reports/2021-06-30/reports/{report_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "x-amz-access-token": access_token,
    }
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
            return doc_id
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
            return pd.read_csv(StringIO(text), sep="\t", dtype=str, keep_default_na=False).fillna("")
        except Exception as exc:
            last_err = exc
    raise RuntimeError(f"Failed to parse TSV: {last_err}")


def _pick_col(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _write_output_frame(df: pd.DataFrame, path: Path, sql_table: str) -> dict[str, object]:
    mode = parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE"))
    sql_rows = 0
    if mode in {"sql_shadow", "sql_primary_csv_export"}:
        store = connect_store(StorageConfig.from_env())
        try:
            result = replace_table_from_dataframe(store, sql_table, df)
            sql_rows = int(result["rows"])
        finally:
            store.close()
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return {
        "mode": mode,
        "path": str(path),
        "csv_rows": int(len(df.index)),
        "sql_table": sql_table if mode != "csv" else "",
        "sql_rows": sql_rows,
    }


def main() -> None:
    load_dotenv_if_missing()
    refresh_token = require_env("LWA_REFRESH_TOKEN")
    client_id = require_env("LWA_CLIENT_ID")
    client_secret = require_env("LWA_CLIENT_SECRET")
    marketplace_id = MARKETPLACE_ID or os.environ.get("MARKETPLACE_ID")
    if not marketplace_id:
        raise MissingEnvError("MARKETPLACE_ID must be set")

    access_token, _, _ = get_lwa_access_token(refresh_token, client_id, client_secret)
    report_id = None
    used_report_type = None
    last_err = None
    for report_type in REPORT_TYPES:
        try:
            report_id = create_report(access_token, marketplace_id, report_type)
            used_report_type = report_type
            break
        except Exception as exc:
            last_err = exc
            continue
    if not report_id:
        raise RuntimeError(f"Create report failed for all types: {REPORT_TYPES}. Last error: {last_err}")

    doc_id = poll_report(access_token, report_id, poll_interval=20, max_attempts=60)
    doc_url, compression = fetch_report_document(access_token, doc_id)
    raw_bytes = download_report(doc_url, compression)
    df = parse_tsv(raw_bytes)

    OUT_RAW.parent.mkdir(parents=True, exist_ok=True)
    _write_output_frame(df, OUT_RAW, SQL_TABLE_INBOUND_SHIPMENT_CONTENTS_RAW)

    shipment_col = _pick_col(df, ["inbound-shipment-id", "shipment-id", "Shipment ID", "FBA Shipment ID"])
    sku_col = _pick_col(df, ["seller-sku", "sku", "Seller SKU"])
    qty_col = _pick_col(df, ["quantity-shipped", "quantity", "Quantity Shipped", "quantity-received"])

    if not shipment_col or not sku_col or not qty_col:
        raise RuntimeError(
            f"Missing required columns. Found shipment={shipment_col}, sku={sku_col}, qty={qty_col}"
        )

    out = pd.DataFrame(
        {
            "inbound_shipment_id": df[shipment_col],
            "sku": df[sku_col],
            "quantity": df[qty_col],
        }
    )
    out["quantity"] = pd.to_numeric(out["quantity"], errors="coerce").fillna(0.0)
    out = out[out["inbound_shipment_id"].astype(str).str.len() > 0]
    out = out[out["sku"].astype(str).str.len() > 0]
    out = out[out["quantity"] > 0]
    out = out.groupby(["inbound_shipment_id", "sku"], dropna=False)["quantity"].sum().reset_index()

    OUT_MAP.parent.mkdir(parents=True, exist_ok=True)
    _write_output_frame(out, OUT_MAP, SQL_TABLE_INBOUND_SHIPMENT_CONTENTS)

    print(
        json.dumps(
            {
                "status": "success",
                "rows_raw": len(df),
                "rows_mapped": len(out),
                "raw": str(OUT_RAW),
                "map": str(OUT_MAP),
                "report_type": used_report_type,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()


