from __future__ import annotations

import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sellerone_manager.app import main as app_main
from sellerone_manager.custodian_dry_run_manifest import (
    MANIFEST_COLUMNS,
    build_custodian_dry_run_manifest,
    write_custodian_dry_run_manifest,
)


INDEX_COLUMNS = [
    "path",
    "retention_class",
    "owner",
    "role",
    "size_mb",
    "file_count",
    "auto_delete_allowed",
    "default_action",
    "archive_after_days",
    "purge_after_days",
    "proof_or_blocker",
    "notes",
]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_fixture(root: Path) -> None:
    _write_csv(
        root / "sellerone_manager" / "CONTROL" / "STORAGE_INDEX_OUT_SUBTREE.csv",
        INDEX_COLUMNS,
        [
            {
                "path": "out/systems",
                "retention_class": "current_runtime",
                "size_mb": "140000",
                "file_count": "1000",
                "notes": "protected live runtime or proof area",
            },
            {
                "path": "out/tmp",
                "retention_class": "temp_debug",
                "size_mb": "1.25",
                "file_count": "12",
                "notes": "candidate only after manifest and active-owner check",
            },
            {
                "path": "out/reports",
                "retention_class": "audit_history",
                "size_mb": "5.5",
                "file_count": "50",
                "notes": "proof or operational history, not bulk delete",
            },
            {
                "path": "out/backups",
                "retention_class": "rollback",
                "size_mb": "9",
                "file_count": "3",
                "notes": "rollback protected until keep-count policy exists",
            },
            {
                "path": "out/_root_files",
                "retention_class": "mixed_current_and_history",
                "size_mb": "2",
                "file_count": "4",
                "notes": "top-level files are mixed runtime/proof/history",
            },
        ],
    )


def test_custodian_dry_run_manifest_classifies_protected_and_candidate_rows(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    result = build_custodian_dry_run_manifest(root=tmp_path, generated_utc="2026-06-08T14:00:00Z")
    rows_by_path = {row["path"]: row for row in result.rows}

    assert rows_by_path["out/systems"]["manifest_action"] == "exclude_keep"
    assert rows_by_path["out/systems"]["protected_exclusion"] == "yes"
    assert rows_by_path["out/systems"]["approval_required"] == "no"
    assert rows_by_path["out/tmp"]["manifest_action"] == "preview_purge_candidate"
    assert rows_by_path["out/tmp"]["approval_required"] == "yes"
    assert rows_by_path["out/reports"]["manifest_action"] == "preview_archive_candidate"
    assert rows_by_path["out/backups"]["manifest_action"] == "manifest_keep_count_review"
    assert rows_by_path["out/_root_files"]["manifest_action"] == "manifest_grouping_required"
    assert rows_by_path["out/_root_files"]["protected_exclusion"] == "yes"
    assert result.preview_candidate_size_mb == 6.75
    assert result.protected_size_mb == 140002
    assert "No cleanup was performed" in result.markdown
    assert "SO21-DEAD-AUTOMATION-AND-SCHEDULER-REVIEW" in result.markdown


def test_write_custodian_dry_run_manifest_writes_csv_and_markdown(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    result = write_custodian_dry_run_manifest(root=tmp_path, generated_utc="2026-06-08T14:00:00Z")

    assert result.csv_path.exists()
    assert result.markdown_path.exists()
    with result.csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == MANIFEST_COLUMNS
        rows = list(reader)
    assert len(rows) == 5
    assert "preview-only cleanup manifest" in result.markdown_path.read_text(encoding="utf-8")


def test_custodian_dry_run_manifest_cli_writes_outputs(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    exit_code = app_main(
        ["--root", str(tmp_path), "--custodian-dry-run-manifest", "--observed-utc", "2026-06-08T14:00:00Z"]
    )

    assert exit_code == 0
    assert (tmp_path / "sellerone_manager" / "CONTROL" / "CUSTODIAN_DRY_RUN_MANIFEST.csv").exists()
    assert (tmp_path / "sellerone_manager" / "CONTROL" / "CUSTODIAN_DRY_RUN_MANIFEST.md").exists()
