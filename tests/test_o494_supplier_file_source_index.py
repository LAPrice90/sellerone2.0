from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.O.O494_build_supplier_file_source_index import (
    build_supplier_file_source_index,
    latest_source_for_supplier,
)
from scripts.flows.O._contract_io import read_o_contract_df


OBSERVED = "2026-06-03T19:15:00Z"


def _write_f_source_status(root: Path, rows: list[dict[str, str]]) -> None:
    path = root / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "source_acquisition_status.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_price_file(price_root: Path, supplier: str, name: str, *, mtime: int) -> Path:
    folder = price_root / supplier / "inbox"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    pd.DataFrame(
        [
            {
                "Product Code": "985 49830",
                "Barcode": "889698498302",
                "Trade": "7.59",
            }
        ]
    ).to_csv(path, index=False)
    os.utime(path, (mtime, mtime))
    return path


def test_o494_reports_local_file_available_when_f_status_failed(tmp_path: Path) -> None:
    price_root = tmp_path / "price_files"
    latest = _write_price_file(price_root, "ABGee", "ABGee_Stock_Feed_latest.csv", mtime=200)
    old = price_root / "ABGee" / "inbox" / "ABGee_Stock_Feed_old.csv"
    _write_f_source_status(
        tmp_path,
        [
            {
                "supplier_id": "abgee",
                "supplier_name": "ABGee",
                "source_type": "email_attachment",
                "source_subtype": "daily_email",
                "source_state": "error",
                "status": "fail",
                "source_location": "gmail_label:ABGee",
                "latest_source_path": str(old),
                "latest_source_name": old.name,
                "latest_source_mtime_utc": "2026-05-22T13:55:17Z",
                "file_count": "1",
                "operator_action": "Investigate Gmail pull",
                "checked_at_utc": OBSERVED,
                "notes": "gmail_fetch_error=RuntimeError;label=ABGee",
            }
        ],
    )

    index_df, health_df = build_supplier_file_source_index(
        root=tmp_path,
        index_utc=OBSERVED,
        price_files_root=price_root,
    )

    row = index_df[index_df["supplier_key"] == "abgee"].iloc[0]
    assert row["local_latest_file_path"] == str(latest)
    assert row["source_handoff_state"] == "f_status_failed_local_file_available"
    assert row["can_be_used_for_presence_probe"] == "1"
    assert row["updates_f_status"] == "0"
    assert row["imports_supplier_file"] == "0"
    assert row["creates_live_action"] == "0"
    assert set(health_df["status"].tolist()) == {"ok"}

    written = read_o_contract_df(tmp_path, "restock_supplier_file_source_index_live")
    assert written.iloc[0]["clears_supplier_proof"] == "0"


def test_o494_indexes_local_folder_without_f_status(tmp_path: Path) -> None:
    price_root = tmp_path / "price_files"
    latest = _write_price_file(price_root, "ABGee", "ABGee_Stock_Feed_latest.csv", mtime=200)

    index_df, health_df = build_supplier_file_source_index(
        root=tmp_path,
        index_utc=OBSERVED,
        price_files_root=price_root,
    )

    row = index_df.iloc[0]
    assert row["supplier_name"] == "ABGee"
    assert row["local_latest_file_path"] == str(latest)
    assert row["source_handoff_state"] == "local_file_available_no_f_status"
    assert set(health_df["status"].tolist()) == {"ok"}

    selected = latest_source_for_supplier(index_df, "ABGee")
    assert selected["local_latest_file_path"] == str(latest)
