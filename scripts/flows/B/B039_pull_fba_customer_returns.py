from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO, StringIO
from pathlib import Path
from typing import Optional

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api.get_orders import get_lwa_access_token, load_dotenv_if_missing
from scripts.api.spapi_signed import sign_spapi_request
from scripts.core.safe_file_writes import safe_to_csv


SPAPI_BASE_URL = os.environ.get("SPAPI_BASE_URL", "https://sellingpartnerapi-eu.amazon.com")
REPORT_TYPE = "GET_FBA_FULFILLMENT_CUSTOMER_RETURNS_DATA"
OUT_DIR = Path("out/systems/B/refunds")
OUT_RAW = OUT_DIR / "b_fba_customer_returns_raw.csv"
OUT_NORMALIZED = OUT_DIR / "b_fba_customer_returns.csv"
OUT_SUMMARY = OUT_DIR / "b_fba_customer_returns_summary.csv"
OUT_MANIFEST = OUT_DIR / "b_fba_customer_returns_manifest.json"
MARKETPLACES = Path("out/marketplace_participations.csv")
DEFAULT_LOOKBACK_DAYS = 90
DEFAULT_LAG_HOURS = 24

NORMALIZED_COLUMNS = [
    "pulled_utc",
    "report_type",
    "report_id",
    "requested_marketplace_ids",
    "order-id",
    "sku",
    "asin",
    "fnsku",
    "return-date",
    "quantity",
    "detailed-disposition",
    "reason",
    "status",
    "fulfillment-center-id",
    "license-plate-number",
    "customer-comments",
]

SUMMARY_COLUMNS = ["metric", "value"]


@dataclass(frozen=True)
class PullResult:
    status: str
    rows_raw: int
    rows_normalized: int
    report_id: str
    marketplace_ids: list[str]
    start_utc: str
    end_utc: str
    raw_path: Path
    normalized_path: Path
    summary_path: Path
    manifest_path: Path


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _split_ids(value: str | None) -> list[str]:
    return [part.strip() for part in str(value or "").replace(";", ",").split(",") if part.strip()]


def _resolve_marketplace_ids(explicit: str | None, *, root: Path) -> list[str]:
    explicit_ids = _split_ids(explicit)
    if explicit_ids:
        return explicit_ids
    path = root / MARKETPLACES
    if not path.exists():
        env_ids = _split_ids(os.environ.get("MARKETPLACE_ID", ""))
        return env_ids or ["A1F83G8C2ARO7P"]
    rows = pd.read_csv(path, dtype=str).fillna("")
    if rows.empty or "marketplace_id" not in rows.columns:
        return ["A1F83G8C2ARO7P"]
    work = rows.copy()
    if "is_participating" in work.columns:
        work = work[work["is_participating"].astype(str).str.lower().isin({"true", "1", "yes", "y"})]
    if "name" in work.columns:
        work = work[~work["name"].astype(str).str.lower().str.startswith("non-amazon")]
    ids = [str(value).strip() for value in work["marketplace_id"].tolist() if str(value).strip()]
    return ids or ["A1F83G8C2ARO7P"]


def _signed_request(method: str, path: str, access_token: str, *, body: str = "", params: dict[str, str] | None = None) -> requests.Response:
    url = f"{SPAPI_BASE_URL}{path}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "x-amz-access-token": access_token,
        "Accept": "application/json",
    }
    if body:
        headers["Content-Type"] = "application/json"
    signed = sign_spapi_request(method, url, SPAPI_BASE_URL, headers, body=body, params=params)
    signed_url = signed.pop("x-signed-url", url)
    return requests.request(method, signed_url, headers=signed, data=body if body else None, timeout=30)


def create_report(access_token: str, marketplace_ids: list[str], start_utc: str, end_utc: str) -> str:
    body = json.dumps(
        {
            "reportType": REPORT_TYPE,
            "marketplaceIds": marketplace_ids,
            "dataStartTime": start_utc,
            "dataEndTime": end_utc,
        },
        separators=(",", ":"),
    )
    resp = _signed_request("POST", "/reports/2021-06-30/reports", access_token, body=body)
    if resp.status_code not in (200, 201, 202):
        raise RuntimeError(f"Create returns report failed: {resp.status_code} {resp.text}")
    payload = resp.json() or {}
    report_id = payload.get("reportId")
    if not report_id:
        raise RuntimeError(f"reportId missing in response: {payload}")
    return str(report_id)


def poll_report(access_token: str, report_id: str, *, poll_interval: int, max_attempts: int) -> str:
    for attempt in range(1, max_attempts + 1):
        resp = _signed_request("GET", f"/reports/2021-06-30/reports/{report_id}", access_token)
        if resp.status_code != 200:
            raise RuntimeError(f"Poll returns report failed: {resp.status_code} {resp.text}")
        payload = resp.json() or {}
        status = payload.get("processingStatus")
        if status == "DONE":
            doc_id = payload.get("reportDocumentId")
            if not doc_id:
                raise RuntimeError(f"reportDocumentId missing when DONE: {payload}")
            return str(doc_id)
        if status in {"FATAL", "CANCELLED"}:
            raise RuntimeError(f"Returns report did not complete: {payload}")
        if attempt < max_attempts:
            time.sleep(poll_interval)
    raise TimeoutError(f"Returns report not DONE after {max_attempts} attempts.")


def fetch_report_document(access_token: str, report_document_id: str) -> tuple[str, Optional[str]]:
    resp = _signed_request("GET", f"/reports/2021-06-30/documents/{report_document_id}", access_token)
    if resp.status_code != 200:
        raise RuntimeError(f"Fetch returns report document failed: {resp.status_code} {resp.text}")
    payload = resp.json() or {}
    doc_url = payload.get("url")
    compression = payload.get("compressionAlgorithm")
    if not doc_url:
        raise RuntimeError(f"Document URL missing in response: {payload}")
    return str(doc_url), str(compression or "") or None


def download_report(doc_url: str, compression: Optional[str]) -> bytes:
    resp = requests.get(doc_url, timeout=90)
    if resp.status_code != 200:
        raise RuntimeError(f"Download returns report failed: {resp.status_code}")
    raw_bytes = resp.content
    if compression and compression.upper() == "GZIP":
        return gzip.GzipFile(fileobj=BytesIO(raw_bytes)).read()
    if compression and compression.upper() != "GZIP":
        raise RuntimeError(f"Unsupported compressionAlgorithm: {compression}")
    return raw_bytes


def parse_report(raw_bytes: bytes) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "latin-1"):
        for sep in ("\t", ","):
            try:
                text = raw_bytes.decode(encoding)
                df = pd.read_csv(StringIO(text), sep=sep, dtype=str, keep_default_na=False)
                if len(df.columns) > 1:
                    return df.fillna("")
            except Exception as exc:
                last_error = exc
    raise RuntimeError(f"Failed to parse FBA customer returns report: {last_error}")


def _first_present(df: pd.DataFrame, names: list[str]) -> pd.Series:
    for name in names:
        if name in df.columns:
            return df[name].astype(str)
    return pd.Series([""] * len(df), index=df.index, dtype=str)


def normalize_returns(df: pd.DataFrame, *, pulled_utc: str, report_id: str, marketplace_ids: list[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=NORMALIZED_COLUMNS)
    out = pd.DataFrame(
        {
            "pulled_utc": pulled_utc,
            "report_type": REPORT_TYPE,
            "report_id": report_id,
            "requested_marketplace_ids": ",".join(marketplace_ids),
            "order-id": _first_present(df, ["order-id", "order_id", "amazon-order-id", "amazon_order_id"]),
            "sku": _first_present(df, ["sku", "seller-sku", "seller_sku"]),
            "asin": _first_present(df, ["asin"]),
            "fnsku": _first_present(df, ["fnsku"]),
            "return-date": _first_present(df, ["return-date", "return_date"]),
            "quantity": _first_present(df, ["quantity", "qty"]),
            "detailed-disposition": _first_present(df, ["detailed-disposition", "detailed_disposition", "disposition"]),
            "reason": _first_present(df, ["reason", "return-reason", "return_reason"]),
            "status": _first_present(df, ["status", "return-status", "return_status"]),
            "fulfillment-center-id": _first_present(df, ["fulfillment-center-id", "fulfillment_center_id"]),
            "license-plate-number": _first_present(df, ["license-plate-number", "license_plate_number"]),
            "customer-comments": _first_present(df, ["customer-comments", "customer_comments"]),
        }
    )
    out["order-id"] = out["order-id"].astype(str).str.strip()
    out["sku"] = out["sku"].astype(str).str.strip()
    out = out[(out["order-id"] != "") & (out["sku"] != "")].copy()
    out = out.drop_duplicates(
        subset=["order-id", "sku", "return-date", "quantity", "detailed-disposition", "reason"],
        keep="last",
    ).reset_index(drop=True)
    return out[NORMALIZED_COLUMNS].fillna("")


def _summary_rows(result: PullResult) -> pd.DataFrame:
    values = {
        "status": result.status,
        "report_type": REPORT_TYPE,
        "report_id": result.report_id,
        "start_utc": result.start_utc,
        "end_utc": result.end_utc,
        "marketplace_count": str(len(result.marketplace_ids)),
        "marketplace_ids": ",".join(result.marketplace_ids),
        "rows_raw": str(result.rows_raw),
        "rows_normalized": str(result.rows_normalized),
        "raw_path": str(result.raw_path),
        "normalized_path": str(result.normalized_path),
    }
    return pd.DataFrame([{"metric": key, "value": value} for key, value in values.items()], columns=SUMMARY_COLUMNS)


def pull_fba_customer_returns(
    *,
    root: Path | str | None = None,
    marketplace_ids: str | None = None,
    start_utc: str | None = None,
    end_utc: str | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    lag_hours: int = DEFAULT_LAG_HOURS,
    poll_interval: int = 20,
    max_attempts: int = 60,
) -> PullResult:
    root_path = Path(root or ".")
    load_dotenv_if_missing()
    access_token = get_lwa_access_token()
    now = _utc_now()
    end_dt = _parse_utc(end_utc) or (now - timedelta(hours=lag_hours))
    start_dt = _parse_utc(start_utc) or (end_dt - timedelta(days=lookback_days))
    start_text = _utc_text(start_dt)
    end_text = _utc_text(end_dt)
    ids = _resolve_marketplace_ids(marketplace_ids, root=root_path)
    pulled_utc = _utc_text(now)
    report_id = create_report(access_token, ids, start_text, end_text)
    doc_id = poll_report(access_token, report_id, poll_interval=poll_interval, max_attempts=max_attempts)
    doc_url, compression = fetch_report_document(access_token, doc_id)
    raw_bytes = download_report(doc_url, compression)
    raw = parse_report(raw_bytes)
    normalized = normalize_returns(raw, pulled_utc=pulled_utc, report_id=report_id, marketplace_ids=ids)

    raw_path = root_path / OUT_RAW
    normalized_path = root_path / OUT_NORMALIZED
    summary_path = root_path / OUT_SUMMARY
    manifest_path = root_path / OUT_MANIFEST
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_with_meta = raw.copy()
    raw_with_meta.insert(0, "pulled_utc", pulled_utc)
    raw_with_meta.insert(1, "report_type", REPORT_TYPE)
    raw_with_meta.insert(2, "report_id", report_id)
    raw_with_meta.insert(3, "requested_marketplace_ids", ",".join(ids))
    safe_to_csv(raw_with_meta, raw_path, index=False)
    safe_to_csv(normalized, normalized_path, index=False)
    result = PullResult(
        status="success",
        rows_raw=int(len(raw.index)),
        rows_normalized=int(len(normalized.index)),
        report_id=report_id,
        marketplace_ids=ids,
        start_utc=start_text,
        end_utc=end_text,
        raw_path=raw_path,
        normalized_path=normalized_path,
        summary_path=summary_path,
        manifest_path=manifest_path,
    )
    safe_to_csv(_summary_rows(result), summary_path, index=False)
    manifest_path.write_text(
        json.dumps(
            {
                "status": result.status,
                "safety": {
                    "ran_b": False,
                    "restarted_b": False,
                    "wrote_sheets": False,
                    "aligned_local_db": False,
                    "corrected_tokens": False,
                    "fed_roi_or_restocking": False,
                },
                "report_type": REPORT_TYPE,
                "report_id": result.report_id,
                "start_utc": result.start_utc,
                "end_utc": result.end_utc,
                "marketplace_ids": result.marketplace_ids,
                "rows_raw": result.rows_raw,
                "rows_normalized": result.rows_normalized,
                "outputs": {
                    "raw": str(result.raw_path),
                    "normalized": str(result.normalized_path),
                    "summary": str(result.summary_path),
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only B FBA customer returns proof pull")
    parser.add_argument("--marketplace-ids", default=None, help="Comma-separated marketplace IDs. Defaults to participating Amazon marketplaces.")
    parser.add_argument("--start-utc", default=None)
    parser.add_argument("--end-utc", default=None)
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--lag-hours", type=int, default=DEFAULT_LAG_HOURS)
    parser.add_argument("--poll-interval", type=int, default=20)
    parser.add_argument("--max-attempts", type=int, default=60)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = pull_fba_customer_returns(
        marketplace_ids=args.marketplace_ids,
        start_utc=args.start_utc,
        end_utc=args.end_utc,
        lookback_days=args.lookback_days,
        lag_hours=args.lag_hours,
        poll_interval=args.poll_interval,
        max_attempts=args.max_attempts,
    )
    print(
        json.dumps(
            {
                "status": result.status,
                "rows_raw": result.rows_raw,
                "rows_normalized": result.rows_normalized,
                "marketplace_count": len(result.marketplace_ids),
                "start_utc": result.start_utc,
                "end_utc": result.end_utc,
                "normalized": str(result.normalized_path),
                "summary": str(result.summary_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
