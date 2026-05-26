from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.core.storage import StorageConfig, SqlStore, connect_store
from scripts.one_off.P004_seed_sql_shadow_from_manifest import quote_identifier


@dataclass(frozen=True)
class ReconcileSummary:
    status: str
    pass_count: int
    fail_count: int
    duplicate_skipped_count: int
    empty_skipped_count: int
    missing_source_count: int
    non_tabular_count: int
    seeded_table_count: int


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_manifest_rows(manifest_path: Path) -> list[dict[str, str]]:
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _parse_header(header_text: str) -> list[str]:
    if not header_text:
        return []
    return next(csv.reader([header_text]))


def _load_shadow_metadata(store: SqlStore) -> dict[str, dict[str, Any]]:
    rows = store.query_all(
        """
        SELECT dataset_id, table_name, source_path, source_header_json, sql_columns_json, row_count
        FROM shadow_seed_tables
        """
    )
    return {str(row["dataset_id"]): row for row in rows}


def _actual_table_count(store: SqlStore, table_name: str) -> int:
    rows = store.query_all(f"SELECT COUNT(*) AS c FROM {quote_identifier(table_name)}")
    return int(rows[0]["c"])


def reconcile_shadow(*, manifest_path: Path, sqlite_path: Path) -> tuple[list[dict[str, str]], ReconcileSummary]:
    store = connect_store(StorageConfig(mode="sql_shadow", sqlite_path=sqlite_path))
    report_rows: list[dict[str, str]] = []
    seen_seedable: set[str] = set()
    try:
        metadata = _load_shadow_metadata(store)
        for manifest_row in read_manifest_rows(manifest_path):
            dataset_id = manifest_row.get("dataset_id", "").strip()
            path = manifest_row.get("path", "").strip()
            exists = manifest_row.get("exists", "")
            row_count_status = manifest_row.get("row_count_status", "")
            manifest_row_count = manifest_row.get("row_count", "")
            manifest_header = _parse_header(manifest_row.get("header", ""))
            status = "not_seedable"
            detail = ""
            table_name = ""
            sql_metadata_row_count = ""
            sql_actual_row_count = ""

            if exists != "true":
                status = "missing_source"
                detail = "manifest source missing"
            elif row_count_status != "ok":
                status = "non_tabular"
                detail = f"row_count_status={row_count_status}"
            elif not dataset_id:
                status = "not_seedable"
                detail = "missing dataset_id"
            elif not manifest_header and str(manifest_row_count or "") == "0":
                status = "empty_skipped"
                detail = "empty source file"
            elif dataset_id in seen_seedable:
                status = "duplicate_skipped"
                detail = "duplicate dataset_id, first source is the shadow table authority"
            else:
                seen_seedable.add(dataset_id)
                meta = metadata.get(dataset_id)
                if not meta:
                    status = "fail"
                    detail = "missing shadow metadata"
                else:
                    table_name = str(meta["table_name"])
                    sql_metadata_row_count = str(meta["row_count"])
                    sql_actual_row_count = str(_actual_table_count(store, table_name))
                    sql_header = json.loads(str(meta["source_header_json"]))
                    failures: list[str] = []
                    if str(manifest_row_count) != sql_metadata_row_count:
                        failures.append("metadata_row_count_mismatch")
                    if str(manifest_row_count) != sql_actual_row_count:
                        failures.append("actual_row_count_mismatch")
                    if manifest_header != sql_header:
                        failures.append("header_mismatch")
                    if failures:
                        status = "fail"
                        detail = "|".join(failures)
                    else:
                        status = "pass"
                        detail = "row_count_and_header_match"

            report_rows.append(
                {
                    "dataset_id": dataset_id,
                    "path": path,
                    "status": status,
                    "detail": detail,
                    "manifest_row_count": str(manifest_row_count),
                    "sql_metadata_row_count": sql_metadata_row_count,
                    "sql_actual_row_count": sql_actual_row_count,
                    "table_name": table_name,
                }
            )
    finally:
        store.close()

    pass_count = sum(1 for row in report_rows if row["status"] == "pass")
    fail_count = sum(1 for row in report_rows if row["status"] == "fail")
    duplicate_skipped_count = sum(1 for row in report_rows if row["status"] == "duplicate_skipped")
    empty_skipped_count = sum(1 for row in report_rows if row["status"] == "empty_skipped")
    missing_source_count = sum(1 for row in report_rows if row["status"] == "missing_source")
    non_tabular_count = sum(1 for row in report_rows if row["status"] == "non_tabular")
    summary = ReconcileSummary(
        status="passed" if fail_count == 0 else "failed",
        pass_count=pass_count,
        fail_count=fail_count,
        duplicate_skipped_count=duplicate_skipped_count,
        empty_skipped_count=empty_skipped_count,
        missing_source_count=missing_source_count,
        non_tabular_count=non_tabular_count,
        seeded_table_count=pass_count,
    )
    return report_rows, summary


def write_reconciliation_outputs(
    *,
    manifest_path: Path,
    sqlite_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    rows, summary = reconcile_shadow(manifest_path=manifest_path, sqlite_path=sqlite_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "shadow_reconciliation_report.csv"
    summary_path = output_dir / "shadow_reconciliation_summary.json"
    with report_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "dataset_id",
            "path",
            "status",
            "detail",
            "manifest_row_count",
            "sql_metadata_row_count",
            "sql_actual_row_count",
            "table_name",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    payload = {
        "status": summary.status,
        "pass_count": summary.pass_count,
        "fail_count": summary.fail_count,
        "duplicate_skipped_count": summary.duplicate_skipped_count,
        "empty_skipped_count": summary.empty_skipped_count,
        "missing_source_count": summary.missing_source_count,
        "non_tabular_count": summary.non_tabular_count,
        "seeded_table_count": summary.seeded_table_count,
        "checked_at_utc": utc_now_iso(),
        "report_path": str(report_path),
        "summary_path": str(summary_path),
    }
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconcile SQL shadow tables against a backup manifest.")
    parser.add_argument("--manifest", required=True, help="Path to backup manifest.csv.")
    parser.add_argument("--sqlite-path", required=True, help="Path to shadow SQLite DB.")
    parser.add_argument("--output-dir", required=True, help="Directory for reconciliation report outputs.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = write_reconciliation_outputs(
        manifest_path=Path(args.manifest),
        sqlite_path=Path(args.sqlite_path),
        output_dir=Path(args.output_dir),
    )
    if args.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        for key, value in payload.items():
            print(f"{key}={value}")
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
