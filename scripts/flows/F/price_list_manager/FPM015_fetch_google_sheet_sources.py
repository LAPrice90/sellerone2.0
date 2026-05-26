from __future__ import annotations

import argparse
import hashlib
import sys
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

from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import ensure_manager_test_mode_dir
from scripts.flows.F.price_list_manager._schemas import MANAGER_HEALTH_COLUMNS, SOURCE_ACQUISITION_COLUMNS


FetchSheetFunc = Callable[[str, str], list[list[str]]]


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


def _sheet_filename(supplier_id: str, fetched_at_utc: str) -> str:
    stamp = fetched_at_utc.replace("-", "").replace(":", "")
    return f"{supplier_id}_{stamp}.csv"


def _default_fetch_sheet_values(spreadsheet_id: str, sheet_name: str) -> list[list[str]]:
    import gspread

    creds_path = ROOT / "secrets" / "sellerone-2-0d3642b951a0.json"
    client = gspread.service_account(filename=str(creds_path))
    spreadsheet = client.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.worksheet(sheet_name)
    return worksheet.get_all_values()


def _write_values_csv(values: list[list[str]], target: Path) -> int:
    if not values:
        raise ValueError("google_sheet_raw_tab_empty")
    max_columns = max(len(row) for row in values)
    rows = [row + [""] * (max_columns - len(row)) for row in values]
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows[1:], columns=rows[0]).to_csv(target, index=False)
    return max(len(rows) - 1, 0)


def _eligible_google_sheet_sources(acquisition: pd.DataFrame, supplier_id: str = "") -> pd.DataFrame:
    work = acquisition.copy()
    work = work[work["source_type"].map(lambda value: normalize_text(value).lower()) == "api_pull"].copy()
    work = work[work["source_subtype"].map(lambda value: normalize_text(value).lower()) == "google_sheet"].copy()
    work = work[work["source_state"].map(lambda value: normalize_text(value).lower()) == "green"].copy()
    if supplier_id:
        key = normalize_text(supplier_id).lower()
        work = work[work["supplier_id"].map(lambda value: normalize_text(value).lower()) == key].copy()
    return work.sort_values(["supplier_id", "checked_at_utc"], kind="stable").reset_index(drop=True)


def fetch_google_sheet_sources(
    root: Path | None = None,
    *,
    supplier_id: str = "",
    fetched_at_utc: str | None = None,
    sheet_name: str = "Raw",
    fetch_sheet_func: FetchSheetFunc | None = None,
) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=root)
    fetched_at = fetched_at_utc or _utc_now_iso()
    acquisition_path = paths.test_mode_dir / "source_acquisition_status.csv"
    health_path = paths.test_mode_dir / "health.csv"
    acquisition = read_csv(acquisition_path, SOURCE_ACQUISITION_COLUMNS)
    if acquisition.empty:
        raise FileNotFoundError("source_acquisition_status.csv is required before fetching Google Sheet sources")

    fetcher = fetch_sheet_func or _default_fetch_sheet_values
    google_sources = _eligible_google_sheet_sources(acquisition, supplier_id=supplier_id)
    fetched_rows = 0
    failed_rows = 0
    source_rows_total = 0
    bytes_total = 0
    updated = acquisition.copy()

    for _, source_row in google_sources.iterrows():
        source_supplier_id = normalize_text(source_row.get("supplier_id", ""))
        spreadsheet_id = normalize_text(source_row.get("source_location", ""))
        mask = updated["supplier_id"].map(lambda value: normalize_text(value).lower()) == source_supplier_id.lower()
        if not spreadsheet_id:
            failed_rows += 1
            updated.loc[mask, "source_state"] = "error"
            updated.loc[mask, "status"] = "fail"
            updated.loc[mask, "operator_action"] = "Add Google Sheet ID"
            updated.loc[mask, "checked_at_utc"] = fetched_at
            updated.loc[mask, "notes"] = "google_sheet_id_missing"
            continue

        inbox_dir = paths.test_mode_dir / "downloaded_sources" / source_supplier_id / "Inbox"
        target = inbox_dir / _sheet_filename(source_supplier_id, fetched_at)
        try:
            values = fetcher(spreadsheet_id, sheet_name)
            source_rows = _write_values_csv(values, target)
        except Exception as exc:
            failed_rows += 1
            if target.exists():
                target.unlink()
            updated.loc[mask, "source_state"] = "error"
            updated.loc[mask, "status"] = "fail"
            updated.loc[mask, "latest_source_path"] = ""
            updated.loc[mask, "latest_source_name"] = ""
            updated.loc[mask, "latest_source_mtime_utc"] = ""
            updated.loc[mask, "file_count"] = "0"
            updated.loc[mask, "operator_action"] = "Grant sheet access"
            updated.loc[mask, "checked_at_utc"] = fetched_at
            updated.loc[mask, "notes"] = f"google_sheet_fetch_error={type(exc).__name__}"
            continue

        fetched_rows += 1
        source_rows_total += source_rows
        bytes_written = target.stat().st_size
        bytes_total += bytes_written
        file_count = len([path for path in inbox_dir.iterdir() if path.is_file()])
        source_hash = _sha1_bytes(target)
        updated.loc[mask, "source_state"] = "ready"
        updated.loc[mask, "status"] = "ok"
        updated.loc[mask, "latest_source_path"] = str(target)
        updated.loc[mask, "latest_source_name"] = target.name
        updated.loc[mask, "latest_source_mtime_utc"] = _file_mtime_utc(target)
        updated.loc[mask, "file_count"] = str(file_count)
        updated.loc[mask, "operator_action"] = "Import latest file"
        updated.loc[mask, "checked_at_utc"] = fetched_at
        updated.loc[mask, "notes"] = (
            f"google_sheet_tab={sheet_name};source_rows={source_rows};bytes={bytes_written};sha1={source_hash}"
        )

    acquisition = write_csv(acquisition_path, updated, SOURCE_ACQUISITION_COLUMNS)
    existing_health = read_csv(health_path, MANAGER_HEALTH_COLUMNS)
    health_row = pd.DataFrame(
        [
            {
                "check": "google_sheet_source_fetch_reconciliation",
                "status": "ok" if failed_rows == 0 else "fail",
                "value": str(fetched_rows),
                "notes": (
                    f"google_sheet_sources={len(google_sources.index)};fetched={fetched_rows};"
                    f"failed={failed_rows};source_rows={source_rows_total};bytes={bytes_total}"
                ),
                "observed_utc": fetched_at,
                "source_path": str(acquisition_path),
            }
        ]
    )
    health = write_csv(health_path, pd.concat([existing_health, health_row], ignore_index=True), MANAGER_HEALTH_COLUMNS)

    summary = {
        "status": "success",
        "google_sheet_sources": int(len(google_sources.index)),
        "fetched_sources": int(fetched_rows),
        "failed_sources": int(failed_rows),
        "source_rows": int(source_rows_total),
        "bytes": int(bytes_total),
        "health_fail_rows": int((health["status"].map(lambda value: normalize_text(value).lower()) == "fail").sum()),
        "acquisition_path": str(acquisition_path),
    }
    print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Google Sheet Raw tabs into test-mode source CSV files.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--supplier-id", default="")
    parser.add_argument("--fetched-at-utc", default=None)
    parser.add_argument("--sheet-name", default="Raw")
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    fetch_google_sheet_sources(
        root=root,
        supplier_id=args.supplier_id,
        fetched_at_utc=args.fetched_at_utc,
        sheet_name=args.sheet_name,
    )


if __name__ == "__main__":
    main()
