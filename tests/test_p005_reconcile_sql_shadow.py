from __future__ import annotations

import csv
from pathlib import Path

from scripts.one_off import P004_seed_sql_shadow_from_manifest as p004
from scripts.one_off import P005_reconcile_sql_shadow as p005


def _write_bundle(root: Path) -> Path:
    bundle = root / "bundle"
    files = bundle / "files" / "out"
    files.mkdir(parents=True, exist_ok=True)
    (files / "orders_all.csv").write_text("Order ID,SKU\n1,ABC\n2,DEF\n", encoding="utf-8")
    (files / "orders_all_mirror.csv").write_text("Order ID,SKU\n1,ABC\n2,DEF\n", encoding="utf-8")
    (files / "empty.csv").write_text("", encoding="utf-8")
    (files / "notes.txt").write_text("not tabular\n", encoding="utf-8")
    manifest = bundle / "manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["path", "exists", "row_count_status", "dataset_id", "row_count", "header"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "path": "out/orders_all.csv",
                "exists": "true",
                "row_count_status": "ok",
                "dataset_id": "B.ORDERS_ALL",
                "row_count": "2",
                "header": "Order ID,SKU",
            }
        )
        writer.writerow(
            {
                "path": "out/orders_all_mirror.csv",
                "exists": "true",
                "row_count_status": "ok",
                "dataset_id": "B.ORDERS_ALL",
                "row_count": "2",
                "header": "Order ID,SKU",
            }
        )
        writer.writerow(
            {
                "path": "out/empty.csv",
                "exists": "true",
                "row_count_status": "ok",
                "dataset_id": "A.EMPTY",
                "row_count": "0",
                "header": "",
            }
        )
        writer.writerow(
            {
                "path": "out/notes.txt",
                "exists": "true",
                "row_count_status": "not_tabular",
                "dataset_id": "SYS.NOTES",
                "row_count": "",
                "header": "",
            }
        )
        writer.writerow(
            {
                "path": "out/missing.csv",
                "exists": "false",
                "row_count_status": "missing",
                "dataset_id": "E.MISSING",
                "row_count": "",
                "header": "",
            }
        )
    return manifest


def test_reconcile_shadow_classifies_expected_statuses(tmp_path: Path) -> None:
    manifest = _write_bundle(tmp_path)
    sqlite_path = tmp_path / "shadow.sqlite3"
    p004.seed_from_manifest(manifest_path=manifest, sqlite_path=sqlite_path, root=tmp_path)

    rows, summary = p005.reconcile_shadow(manifest_path=manifest, sqlite_path=sqlite_path)
    by_path = {row["path"]: row for row in rows}

    assert summary.status == "passed"
    assert summary.pass_count == 1
    assert summary.fail_count == 0
    assert summary.duplicate_skipped_count == 1
    assert summary.empty_skipped_count == 1
    assert summary.missing_source_count == 1
    assert summary.non_tabular_count == 1
    assert by_path["out/orders_all.csv"]["status"] == "pass"
    assert by_path["out/orders_all_mirror.csv"]["status"] == "duplicate_skipped"


def test_reconcile_shadow_detects_row_count_mismatch(tmp_path: Path) -> None:
    manifest = _write_bundle(tmp_path)
    sqlite_path = tmp_path / "shadow.sqlite3"
    p004.seed_from_manifest(manifest_path=manifest, sqlite_path=sqlite_path, root=tmp_path)

    # Corrupt the manifest expectation after seed so reconciliation must fail.
    text = manifest.read_text(encoding="utf-8")
    manifest.write_text(text.replace("out/orders_all.csv,true,ok,B.ORDERS_ALL,2", "out/orders_all.csv,true,ok,B.ORDERS_ALL,3"), encoding="utf-8")

    rows, summary = p005.reconcile_shadow(manifest_path=manifest, sqlite_path=sqlite_path)

    assert summary.status == "failed"
    assert summary.fail_count == 1
    failed = [row for row in rows if row["status"] == "fail"][0]
    assert "row_count_mismatch" in failed["detail"]


def test_write_reconciliation_outputs(tmp_path: Path) -> None:
    manifest = _write_bundle(tmp_path)
    sqlite_path = tmp_path / "shadow.sqlite3"
    output_dir = tmp_path / "reconcile"
    p004.seed_from_manifest(manifest_path=manifest, sqlite_path=sqlite_path, root=tmp_path)

    payload = p005.write_reconciliation_outputs(
        manifest_path=manifest,
        sqlite_path=sqlite_path,
        output_dir=output_dir,
    )

    assert payload["status"] == "passed"
    assert (output_dir / "shadow_reconciliation_report.csv").exists()
    assert (output_dir / "shadow_reconciliation_summary.json").exists()
