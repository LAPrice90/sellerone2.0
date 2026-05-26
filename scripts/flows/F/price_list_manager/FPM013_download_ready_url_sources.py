from __future__ import annotations

import argparse
import hashlib
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager.FPM010_check_acquisition_sources import _remote_response_is_price_file
from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import ensure_manager_test_mode_dir
from scripts.flows.F.price_list_manager._schemas import MANAGER_HEALTH_COLUMNS, SOURCE_ACQUISITION_COLUMNS


DownloadFunc = Callable[[str, Path, int], dict[str, object]]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _file_mtime_utc(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha1_bytes(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_filename(supplier_id: str, url: str, downloaded_at_utc: str) -> str:
    parsed = urllib.parse.urlparse(url)
    suffix = Path(parsed.path).suffix or ".csv"
    stamp = downloaded_at_utc.replace("-", "").replace(":", "")
    return f"{supplier_id}_{stamp}{suffix}"


def _download_request_headers(url: str) -> dict[str, str]:
    headers = {"User-Agent": "SellerOne-FPM/1.0"}
    host = urllib.parse.urlparse(url).netloc.lower()
    cookie = normalize_text(os.environ.get("FPM_DOWNLOAD_COOKIE", ""))
    if "westocklots.com" in host:
        cookie = normalize_text(os.environ.get("WE_STOCK_LOTS_COOKIE", "")) or cookie
    if cookie:
        headers["Cookie"] = cookie
    authorization = normalize_text(os.environ.get("FPM_DOWNLOAD_AUTHORIZATION", ""))
    if authorization:
        headers["Authorization"] = authorization
    return headers


def _download_url_to_path(url: str, destination: Path, timeout_seconds: int) -> dict[str, object]:
    request = urllib.request.Request(url, headers=_download_request_headers(url))
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status = int(getattr(response, "status", 0))
            content_type = response.headers.get("content-type", "")
            body = response.read()
    except urllib.error.HTTPError as exc:
        return {"ok": False, "notes": f"http_status={exc.code};reason={exc.reason}", "bytes": 0}
    except Exception as exc:
        return {"ok": False, "notes": f"download_error={type(exc).__name__}", "bytes": 0}

    ok, reason = _remote_response_is_price_file(content_type=content_type, sample=body[:4096])
    if not (200 <= status < 400):
        return {"ok": False, "notes": f"http_status={status};content_type={content_type}", "bytes": len(body)}
    if not ok:
        return {
            "ok": False,
            "notes": f"http_status={status};content_type={content_type};remote_type={reason}",
            "bytes": len(body),
        }

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(body)
    return {
        "ok": True,
        "notes": f"http_status={status};content_type={content_type};remote_type={reason}",
        "bytes": len(body),
    }


def _eligible_download_sources(acquisition: pd.DataFrame, supplier_id: str = "") -> pd.DataFrame:
    work = acquisition.copy()
    work = work[work["source_state"].map(lambda value: normalize_text(value).lower()) == "download_ready"].copy()
    work = work[work["source_location"].map(normalize_text) != ""].copy()
    if supplier_id:
        key = normalize_text(supplier_id).lower()
        work = work[work["supplier_id"].map(lambda value: normalize_text(value).lower()) == key].copy()
    return work.sort_values(["supplier_id", "checked_at_utc"], kind="stable").reset_index(drop=True)


def download_ready_url_sources(
    root: Path | None = None,
    *,
    supplier_id: str = "",
    downloaded_at_utc: str | None = None,
    timeout_seconds: int = 60,
    download_func: DownloadFunc | None = None,
) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=root)
    downloaded_at = downloaded_at_utc or _utc_now_iso()
    acquisition_path = paths.test_mode_dir / "source_acquisition_status.csv"
    health_path = paths.test_mode_dir / "health.csv"
    acquisition = read_csv(acquisition_path, SOURCE_ACQUISITION_COLUMNS)
    if acquisition.empty:
        raise FileNotFoundError("source_acquisition_status.csv is required before downloading URL sources")

    downloader = download_func or _download_url_to_path
    ready_sources = _eligible_download_sources(acquisition, supplier_id=supplier_id)
    downloaded_rows = 0
    failed_rows = 0
    bytes_total = 0
    updated = acquisition.copy()

    for _, source_row in ready_sources.iterrows():
        source_supplier_id = normalize_text(source_row.get("supplier_id", ""))
        url = normalize_text(source_row.get("source_location", ""))
        inbox_dir = paths.test_mode_dir / "downloaded_sources" / source_supplier_id / "Inbox"
        target = inbox_dir / _download_filename(source_supplier_id, url, downloaded_at)
        result = downloader(url, target, timeout_seconds)
        notes = normalize_text(result.get("notes", ""))
        bytes_written = int(result.get("bytes", 0) or 0)
        bytes_total += bytes_written
        mask = updated["supplier_id"].map(lambda value: normalize_text(value).lower()) == source_supplier_id.lower()
        if bool(result.get("ok", False)) and target.exists():
            downloaded_rows += 1
            file_count = len([path for path in inbox_dir.iterdir() if path.is_file()])
            source_hash = _sha1_bytes(target)
            updated.loc[mask, "source_state"] = "ready"
            updated.loc[mask, "status"] = "ok"
            updated.loc[mask, "latest_source_path"] = str(target)
            updated.loc[mask, "latest_source_name"] = target.name
            updated.loc[mask, "latest_source_mtime_utc"] = _file_mtime_utc(target)
            updated.loc[mask, "file_count"] = str(file_count)
            updated.loc[mask, "operator_action"] = "Import latest file"
            updated.loc[mask, "checked_at_utc"] = downloaded_at
            updated.loc[mask, "notes"] = f"{notes};bytes={bytes_written};sha1={source_hash}"
            continue

        failed_rows += 1
        if target.exists():
            target.unlink()
        updated.loc[mask, "source_state"] = "error"
        updated.loc[mask, "status"] = "fail"
        updated.loc[mask, "latest_source_path"] = ""
        updated.loc[mask, "latest_source_name"] = ""
        updated.loc[mask, "latest_source_mtime_utc"] = ""
        updated.loc[mask, "file_count"] = "0"
        updated.loc[mask, "operator_action"] = "Investigate CSV link"
        updated.loc[mask, "checked_at_utc"] = downloaded_at
        updated.loc[mask, "notes"] = notes or "download_failed"

    acquisition = write_csv(acquisition_path, updated, SOURCE_ACQUISITION_COLUMNS)
    existing_health = read_csv(health_path, MANAGER_HEALTH_COLUMNS)
    health_row = pd.DataFrame(
        [
            {
                "check": "url_source_download_reconciliation",
                "status": "ok" if failed_rows == 0 else "fail",
                "value": str(downloaded_rows),
                "notes": f"download_ready_sources={len(ready_sources.index)};downloaded={downloaded_rows};failed={failed_rows};bytes={bytes_total}",
                "observed_utc": downloaded_at,
                "source_path": str(acquisition_path),
            }
        ]
    )
    health = write_csv(health_path, pd.concat([existing_health, health_row], ignore_index=True), MANAGER_HEALTH_COLUMNS)

    summary = {
        "status": "success",
        "download_ready_sources": int(len(ready_sources.index)),
        "downloaded_sources": int(downloaded_rows),
        "failed_sources": int(failed_rows),
        "bytes": int(bytes_total),
        "health_fail_rows": int((health["status"].map(lambda value: normalize_text(value).lower()) == "fail").sum()),
        "acquisition_path": str(acquisition_path),
    }
    print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Download URL-based price-list sources into test-mode inboxes.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--supplier-id", default="")
    parser.add_argument("--downloaded-at-utc", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    download_ready_url_sources(
        root=root,
        supplier_id=args.supplier_id,
        downloaded_at_utc=args.downloaded_at_utc,
        timeout_seconds=args.timeout_seconds,
    )


if __name__ == "__main__":
    main()
