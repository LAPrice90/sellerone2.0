from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._schemas import get_f_output_contract
from scripts.one_off.F036_build_passed_product_page_evidence_backfill_queue import (
    BACKFILL_QUEUE_COLUMNS,
    F061_ACTIVE_RUN_COLUMNS,
    build_passed_product_page_evidence_backfill_queue,
)


OBSERVED = "2026-05-20T15:20:00Z"


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).fillna("").to_csv(path, index=False)


def _analysis_dir(root: Path) -> Path:
    return root / "out" / "analysis_reports"


def _supplier_dir(root: Path, supplier_id: str) -> Path:
    return root / "out" / "systems" / "F" / "inbox" / "suppliers" / supplier_id


def _scrape_evidence_path(root: Path) -> Path:
    return root / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path


def test_latest_scope_builds_queue_and_skips_existing_page_evidence(tmp_path: Path) -> None:
    _write_csv(
        _analysis_dir(tmp_path) / "f_live_price_file_pass_review_latest.csv",
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-latest",
                "review_batch_id": "batch-1",
                "candidate_id": "cand-new",
                "supplier_sku": "SKU-1",
                "asin": "B000000001",
                "title": "Amazon title needs page evidence",
                "brand": "Brand A",
                "review_priority_score": "80",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-latest",
                "review_batch_id": "batch-1",
                "candidate_id": "cand-existing",
                "supplier_sku": "SKU-2",
                "asin": "B000000002",
                "title": "Amazon title already has page evidence",
                "brand": "Brand B",
                "review_priority_score": "70",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-latest",
                "review_batch_id": "batch-1",
                "candidate_id": "cand-missing-asin",
                "supplier_sku": "SKU-3",
                "asin": "",
                "title": "Missing ASIN row",
                "brand": "Brand C",
                "review_priority_score": "60",
            },
        ],
    )
    _write_csv(
        _supplier_dir(tmp_path, "stocklist_supplier") / "canonical_current.csv",
        [
            {
                "supplier_id": "stocklist_supplier",
                "supplier_sku": "SKU-1",
                "supplier_title": "Supplier title one",
                "brand": "Brand A",
                "barcode": "5012345678901",
                "unit_cost": "5.00",
                "currency": "GBP",
                "vat_rate": "20",
            },
            {
                "supplier_id": "stocklist_supplier",
                "supplier_sku": "SKU-2",
                "supplier_title": "Supplier title two",
                "brand": "Brand B",
                "barcode": "5012345678902",
                "unit_cost": "6.00",
                "currency": "GBP",
                "vat_rate": "20",
            },
        ],
    )
    _write_csv(
        _scrape_evidence_path(tmp_path),
        [
            {
                "observed_utc": "2026-05-20T12:00:00Z",
                "supplier_id": "stocklist_supplier",
                "supplier_sku": "SKU-2",
                "candidate_id": "old-cand",
                "asin": "B000000002",
                "product_description": "Existing page description",
                "product_feature_bullets": "",
                "product_detail_text": "",
            }
        ],
    )

    result = build_passed_product_page_evidence_backfill_queue(root=tmp_path, scope="latest", observed_utc=OBSERVED)

    assert result.report["raw_pass_rows"] == 3
    assert result.report["missing_asin_rows"] == 1
    assert result.report["unique_pass_asins_before_skip"] == 2
    assert result.report["skipped_existing_evidence_rows"] == 1
    assert result.report["queue_rows"] == 1
    assert result.report["f061_ready_rows"] == 1
    row = result.queue_df.iloc[0]
    assert row["asin"] == "B000000001"
    assert row["supplier_title"] == "Supplier title one"
    assert row["barcode"] == "5012345678901"
    assert row["f061_ready_flag"] == "1"
    assert list(result.queue_df.columns) == BACKFILL_QUEUE_COLUMNS
    assert list(result.f061_active_run_df.columns) == F061_ACTIVE_RUN_COLUMNS
    assert (_analysis_dir(tmp_path) / "f_passed_product_page_evidence_backfill_queue_latest.csv").exists()


def test_all_scope_dedupes_asin_and_preserves_latest_and_historical_sources(tmp_path: Path) -> None:
    _write_csv(
        _analysis_dir(tmp_path) / "f_live_price_file_pass_review_latest.csv",
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-latest",
                "review_batch_id": "batch-latest",
                "candidate_id": "cand-latest",
                "supplier_sku": "SKU-1",
                "asin": "B000000001",
                "title": "Latest Amazon title",
                "review_priority_score": "50",
            }
        ],
    )
    _write_csv(
        _analysis_dir(tmp_path) / "f_live_price_file_pass_review_20260501T090000Z.csv",
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-old",
                "review_batch_id": "batch-old",
                "candidate_id": "cand-old",
                "supplier_sku": "SKU-1",
                "asin": "B000000001",
                "title": "Old Amazon title",
                "review_priority_score": "99",
            }
        ],
    )
    _write_csv(
        _supplier_dir(tmp_path, "stocklist_supplier") / "canonical_current.csv",
        [
            {
                "supplier_id": "stocklist_supplier",
                "supplier_sku": "SKU-1",
                "supplier_title": "Supplier title one",
                "barcode": "5012345678901",
            }
        ],
    )

    result = build_passed_product_page_evidence_backfill_queue(root=tmp_path, scope="all", observed_utc=OBSERVED)

    assert result.report["pass_files_inspected"] == 2
    assert result.report["raw_pass_rows"] == 2
    assert result.report["queue_rows"] == 1
    row = result.queue_df.iloc[0]
    assert row["candidate_id"] == "cand-latest"
    assert row["amazon_title"] == "Latest Amazon title"
    assert row["source_pass_row_count"] == "2"
    assert row["latest_pass_flag"] == "1"
    assert row["historical_pass_flag"] == "1"
    assert "f_live_price_file_pass_review_latest.csv" in row["source_pass_files"]
    assert "f_live_price_file_pass_review_20260501T090000Z.csv" in row["source_pass_files"]


def test_missing_supplier_barcode_is_visible_but_not_f061_ready(tmp_path: Path) -> None:
    _write_csv(
        _analysis_dir(tmp_path) / "f_live_price_file_pass_review_latest.csv",
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-latest",
                "review_batch_id": "batch-1",
                "candidate_id": "cand-no-barcode",
                "supplier_sku": "SKU-MISSING",
                "asin": "B000000003",
                "title": "Amazon title no barcode",
                "review_priority_score": "40",
            }
        ],
    )

    result = build_passed_product_page_evidence_backfill_queue(root=tmp_path, scope="latest", observed_utc=OBSERVED)

    assert result.report["queue_rows"] == 1
    assert result.report["f061_ready_rows"] == 0
    assert result.report["missing_barcode_rows"] == 1
    row = result.queue_df.iloc[0]
    assert row["f061_ready_flag"] == "0"
    assert row["recommended_next_action"] == "needs_barcode_before_f061_backfill"
    health = {record["check"]: record for record in result.health_df.to_dict("records")}
    assert health["passed_product_backfill_missing_barcode_rows"]["status"] == "warn"
    assert health["passed_product_backfill_f061_ready_rows"]["status"] == "warn"
