from __future__ import annotations

import argparse
import importlib
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import ensure_manager_test_mode_dir
from scripts.flows.F.price_list_manager._schemas import (
    MANAGER_HEALTH_COLUMNS,
    SOURCE_ACQUISITION_COLUMNS,
    SUPPLIER_REGISTRY_COLUMNS,
)


PRICE_FILE_SUFFIXES = {".csv", ".tsv", ".xlsx", ".xls", ".txt", ".zip"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _registry_path(root_path: Path) -> Path:
    return root_path / "config" / "feeder" / "price_list_manager" / "suppliers.csv"


def _active_flag(value: object) -> bool:
    return normalize_text(value).lower() not in {"", "0", "false", "no", "off"}


def _file_mtime_utc(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _latest_price_file(folder: Path) -> tuple[Path | None, int]:
    if not folder.exists() or not folder.is_dir():
        return None, 0
    files = [
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in PRICE_FILE_SUFFIXES and not path.name.startswith("~$")
    ]
    if not files:
        return None, 0
    return max(files, key=lambda path: path.stat().st_mtime), len(files)


def _remote_response_is_price_file(*, content_type: str, sample: bytes = b"") -> tuple[bool, str]:
    lowered_type = content_type.lower()
    sample_text = sample[:4096].decode("utf-8", errors="ignore").lower()
    if "text/html" in lowered_type or "<html" in sample_text or "<!doctype html" in sample_text:
        if "login" in sample_text or "sign in" in sample_text or "resellers" in sample_text:
            return False, "auth_required_html_response"
        return False, "html_response_not_price_file"
    return True, "price_file_like_response"


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


def _check_remote_csv_link(url: str, *, timeout_seconds: int) -> tuple[bool, str]:
    def _get_sample(*, head_error: str = "") -> tuple[bool, str]:
        request_get = urllib.request.Request(
            url,
            method="GET",
            headers={**_download_request_headers(url), "Range": "bytes=0-4095"},
        )
        try:
            with urllib.request.urlopen(request_get, timeout=timeout_seconds) as response_get:
                status_get = getattr(response_get, "status", 0)
                content_type_get = response_get.headers.get("content-type", "")
                sample = response_get.read(4096)
                if 200 <= int(status_get) < 400:
                    ok_get, reason_get = _remote_response_is_price_file(content_type=content_type_get, sample=sample)
                    suffix = f";head_error={head_error}" if head_error else ""
                    if ok_get:
                        return True, f"http_status={status_get};content_type={content_type_get};remote_type={reason_get}{suffix}"
                    return False, f"http_status={status_get};content_type={content_type_get};remote_type={reason_get}{suffix}"
                suffix = f";head_error={head_error}" if head_error else ""
                return False, f"http_status={status_get};content_type={content_type_get}{suffix}"
        except Exception as get_exc:
            suffix = f";head_error={head_error}" if head_error else ""
            return False, f"get_error={type(get_exc).__name__}{suffix}"

    request = urllib.request.Request(url, method="HEAD", headers=_download_request_headers(url))
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", 0)
            content_type = response.headers.get("content-type", "")
            if 200 <= int(status) < 400:
                ok, reason = _remote_response_is_price_file(content_type=content_type)
                if ok:
                    return True, f"http_status={status};content_type={content_type};remote_type={reason}"
                if reason in {"html_response_not_price_file", "auth_required_html_response"}:
                    return _get_sample()
                return False, f"http_status={status};content_type={content_type};remote_type={reason}"
            return False, f"http_status={status};content_type={content_type}"
    except urllib.error.HTTPError as exc:
        return False, f"http_status={exc.code};reason={exc.reason}"
    except Exception as head_exc:
        return _get_sample(head_error=type(head_exc).__name__)


def _manual_row(
    *,
    supplier: dict[str, str],
    checked_at: str,
    source_state: str,
    status: str,
    source_location: str,
    operator_action: str,
    notes: str,
    latest_file: Path | None = None,
    file_count: int = 0,
) -> dict[str, str]:
    return {
        "supplier_id": supplier["supplier_id"],
        "supplier_name": supplier["supplier_name"],
        "source_type": supplier["source_type"],
        "source_subtype": supplier["source_subtype"],
        "source_state": source_state,
        "status": status,
        "source_location": source_location,
        "latest_source_path": str(latest_file) if latest_file else "",
        "latest_source_name": latest_file.name if latest_file else "",
        "latest_source_mtime_utc": _file_mtime_utc(latest_file) if latest_file else "",
        "file_count": str(file_count),
        "operator_action": operator_action,
        "checked_at_utc": checked_at,
        "notes": notes,
    }


def _check_folder_supplier(supplier: dict[str, str], *, checked_at: str) -> dict[str, str]:
    source_type = supplier["source_type"]
    folder_raw = supplier["source_folder_path"]
    if not folder_raw:
        return _manual_row(
            supplier=supplier,
            checked_at=checked_at,
            source_state="config_needed",
            status="warn",
            source_location="",
            operator_action="Add folder path",
            notes="folder_path_missing",
        )

    folder = Path(folder_raw)
    if not folder.exists() or not folder.is_dir():
        if source_type == "email_attachment":
            action = "Create email folder"
            state = "waiting"
        elif source_type == "manual_download":
            action = "Create folder / download file"
            state = "missing"
        else:
            action = "Create folder / request file"
            state = "missing"
        return _manual_row(
            supplier=supplier,
            checked_at=checked_at,
            source_state=state,
            status="warn",
            source_location=folder_raw,
            operator_action=action,
            notes="folder_missing",
        )

    latest_file, file_count = _latest_price_file(folder)
    if latest_file is not None:
        return _manual_row(
            supplier=supplier,
            checked_at=checked_at,
            source_state="ready",
            status="ok",
            source_location=folder_raw,
            operator_action="Import latest file",
            notes="latest_price_file_found",
            latest_file=latest_file,
            file_count=file_count,
        )

    if source_type == "email_attachment":
        return _manual_row(
            supplier=supplier,
            checked_at=checked_at,
            source_state="waiting",
            status="ok",
            source_location=folder_raw,
            operator_action="Await email file",
            notes="folder_empty",
        )
    if source_type == "manual_download":
        return _manual_row(
            supplier=supplier,
            checked_at=checked_at,
            source_state="missing",
            status="warn",
            source_location=folder_raw,
            operator_action="Download from website",
            notes="folder_empty",
        )
    return _manual_row(
        supplier=supplier,
        checked_at=checked_at,
        source_state="missing",
        status="warn",
        source_location=folder_raw,
        operator_action="Request price file",
        notes="folder_empty",
    )


def _check_api_supplier(
    supplier: dict[str, str],
    *,
    checked_at: str,
    check_remote: bool,
    timeout_seconds: int,
) -> dict[str, str]:
    source_url = supplier["source_url"]
    source_subtype = supplier["source_subtype"]
    if source_subtype == "csv_link":
        if not source_url:
            return _manual_row(
                supplier=supplier,
                checked_at=checked_at,
                source_state="config_needed",
                status="warn",
                source_location="",
                operator_action="Add CSV link",
                notes="csv_link_missing",
            )
        if check_remote:
            ok, notes = _check_remote_csv_link(source_url, timeout_seconds=timeout_seconds)
            return _manual_row(
                supplier=supplier,
                checked_at=checked_at,
                source_state="download_ready" if ok else "error",
                status="ok" if ok else "fail",
                source_location=source_url,
                operator_action="Auto pull when due" if ok else "Investigate CSV link",
                notes=notes,
            )
        return _manual_row(
            supplier=supplier,
            checked_at=checked_at,
            source_state="download_ready",
            status="ok",
            source_location=source_url,
            operator_action="Auto pull when due",
            notes="remote_check_skipped",
        )

    if source_subtype == "google_sheet":
        if not source_url:
            return _manual_row(
                supplier=supplier,
                checked_at=checked_at,
                source_state="config_needed",
                status="warn",
                source_location="",
                operator_action="Add Google Sheet ID",
                notes="google_sheet_id_missing",
            )
        return _manual_row(
            supplier=supplier,
            checked_at=checked_at,
            source_state="green",
            status="ok",
            source_location=source_url,
            operator_action="Auto pull when due",
            notes="google_sheet_source_configured",
        )

    notes = "api_adapter_ready" if _api_adapter_exists(supplier["converter_id"]) else "api_adapter_pending"
    return _manual_row(
        supplier=supplier,
        checked_at=checked_at,
        source_state="green",
        status="ok",
        source_location=source_url or "Not configured in test mode",
        operator_action="Auto pull when due",
        notes=notes,
    )


def _api_adapter_exists(converter_id: str) -> bool:
    if not converter_id:
        return False
    try:
        module = importlib.import_module(f"scripts.flows.F.suppliers.{converter_id}")
    except ModuleNotFoundError:
        return False
    return callable(getattr(module, "fetch_api_source", None))


def _check_supplier(
    supplier: dict[str, str],
    *,
    checked_at: str,
    check_remote: bool,
    timeout_seconds: int,
) -> dict[str, str]:
    source_type = supplier["source_type"]
    if source_type in {"manual_request", "manual_download", "email_attachment"}:
        return _check_folder_supplier(supplier, checked_at=checked_at)
    if source_type in {"api_pull", "url_download"}:
        return _check_api_supplier(
            supplier,
            checked_at=checked_at,
            check_remote=check_remote,
            timeout_seconds=timeout_seconds,
        )
    return _manual_row(
        supplier=supplier,
        checked_at=checked_at,
        source_state="config_needed",
        status="warn",
        source_location=supplier["source_url"] or supplier["source_folder_path"],
        operator_action="Add source method",
        notes="unknown_source_type",
    )


def check_acquisition_sources(
    root: Path | None = None,
    *,
    checked_at_utc: str | None = None,
    check_remote: bool = True,
    timeout_seconds: int = 8,
) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=root)
    root_path = paths.root
    checked_at = checked_at_utc or _utc_now_iso()
    registry_path = _registry_path(root_path)
    registry = read_csv(registry_path, SUPPLIER_REGISTRY_COLUMNS)
    if registry.empty:
        raise FileNotFoundError(f"price-list manager supplier registry missing or empty: {registry_path}")

    active_registry = registry[registry["active_flag"].map(_active_flag)].copy()
    write_csv(paths.test_mode_dir / "supplier_registry.csv", active_registry, SUPPLIER_REGISTRY_COLUMNS)
    rows: list[dict[str, str]] = []
    for _, raw_supplier in active_registry.iterrows():
        supplier = {column: normalize_text(raw_supplier.get(column, "")) for column in SUPPLIER_REGISTRY_COLUMNS}
        rows.append(
            _check_supplier(
                supplier,
                checked_at=checked_at,
                check_remote=check_remote,
                timeout_seconds=timeout_seconds,
            )
        )

    acquisition = write_csv(
        paths.test_mode_dir / "source_acquisition_status.csv",
        pd.DataFrame(rows),
        SOURCE_ACQUISITION_COLUMNS,
    )
    fail_rows = int((acquisition["status"].map(lambda value: normalize_text(value).lower()) == "fail").sum())
    warn_rows = int((acquisition["status"].map(lambda value: normalize_text(value).lower()) == "warn").sum())

    health_path = paths.test_mode_dir / "health.csv"
    existing_health = read_csv(health_path, MANAGER_HEALTH_COLUMNS)
    health_row = pd.DataFrame(
        [
            {
                "check": "source_acquisition_status_summary",
                "status": "ok" if fail_rows == 0 else "fail",
                "value": str(len(acquisition.index)),
                "notes": f"fail_rows={fail_rows};warn_rows={warn_rows}",
                "observed_utc": checked_at,
                "source_path": str(paths.test_mode_dir / "source_acquisition_status.csv"),
            }
        ]
    )
    health = write_csv(health_path, pd.concat([existing_health, health_row], ignore_index=True), MANAGER_HEALTH_COLUMNS)

    summary = {
        "status": "success",
        "supplier_rows": int(len(acquisition.index)),
        "ready_rows": int(
            acquisition["source_state"].map(lambda value: normalize_text(value).lower()).isin({"ready", "download_ready", "green"}).sum()
        ),
        "missing_rows": int((acquisition["source_state"].map(lambda value: normalize_text(value).lower()) == "missing").sum()),
        "waiting_rows": int((acquisition["source_state"].map(lambda value: normalize_text(value).lower()) == "waiting").sum()),
        "config_needed_rows": int(
            (acquisition["source_state"].map(lambda value: normalize_text(value).lower()) == "config_needed").sum()
        ),
        "fail_rows": fail_rows,
        "health_fail_rows": int((health["status"].map(lambda value: normalize_text(value).lower()) == "fail").sum()),
        "acquisition_path": str(paths.test_mode_dir / "source_acquisition_status.csv"),
    }
    print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Check price-list manager acquisition sources in test mode.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--checked-at-utc", default=None)
    parser.add_argument("--skip-remote-check", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=8)
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    check_acquisition_sources(
        root=root,
        checked_at_utc=args.checked_at_utc,
        check_remote=not args.skip_remote_check,
        timeout_seconds=args.timeout_seconds,
    )


if __name__ == "__main__":
    main()
