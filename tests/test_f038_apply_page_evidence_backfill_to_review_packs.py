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

from scripts.one_off.F038_apply_page_evidence_backfill_to_review_packs import (
    apply_page_evidence_backfill_to_review_packs,
)


OBSERVED = "2026-05-20T21:05:00Z"


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).fillna("").to_csv(path, index=False)


def _backfill_path(root: Path) -> Path:
    return root / "backfill.csv"


def _pack_path(root: Path) -> Path:
    return root / "pass.csv"


def test_dry_run_writes_preview_without_changing_review_pack(tmp_path: Path) -> None:
    _write_csv(
        _backfill_path(tmp_path),
        [
            {
                "observed_utc": OBSERVED,
                "backfill_status": "succeeded",
                "page_evidence_captured_flag": "1",
                "supplier_sku": "SKU-1",
                "asin": "B000000001",
                "resolved_asin": "B000000001",
                "product_detail_text": "Backfilled details",
                "product_description": "Backfilled description",
                "product_feature_bullets": "Backfilled bullets",
            }
        ],
    )
    _write_csv(
        _pack_path(tmp_path),
        [
            {
                "supplier_sku": "SKU-1",
                "asin": "B000000001",
                "amazon_product_detail_text": "",
                "amazon_product_description": "",
                "amazon_feature_bullets": "",
            }
        ],
    )

    result = apply_page_evidence_backfill_to_review_packs(
        backfill_results_path=_backfill_path(tmp_path),
        review_pack_paths=[_pack_path(tmp_path)],
        output_dir=tmp_path / "out",
        proof_base_dir=tmp_path / "proof",
        backup_base_dir=tmp_path / "backups",
        observed_utc=OBSERVED,
        execute=False,
    )

    live_pack = pd.read_csv(_pack_path(tmp_path), dtype=str).fillna("")
    assert live_pack.iloc[0]["amazon_product_description"] == ""
    manifest = pd.read_csv(result.manifest_path, dtype=str).fillna("")
    preview = pd.read_csv(manifest.iloc[0]["preview_path"], dtype=str).fillna("")
    assert result.updated_rows == 1
    assert result.updated_cells == 3
    assert manifest.iloc[0]["backup_path"] == ""
    assert preview.iloc[0]["amazon_product_description"] == "Backfilled description"


def test_execute_backs_up_and_fills_only_blank_fields(tmp_path: Path) -> None:
    _write_csv(
        _backfill_path(tmp_path),
        [
            {
                "observed_utc": OBSERVED,
                "backfill_status": "succeeded",
                "page_evidence_captured_flag": "1",
                "supplier_sku": "SKU-1",
                "asin": "B000000001",
                "resolved_asin": "B000000001",
                "product_detail_text": "Backfilled details",
                "product_description": "Backfilled description",
                "product_feature_bullets": "Backfilled bullets",
            },
            {
                "observed_utc": OBSERVED,
                "backfill_status": "skipped_current_scanner_fail",
                "page_evidence_captured_flag": "0",
                "supplier_sku": "SKU-2",
                "asin": "B000000002",
                "resolved_asin": "B000000002",
                "product_description": "Should not be used",
            },
        ],
    )
    _write_csv(
        _pack_path(tmp_path),
        [
            {
                "supplier_sku": "SKU-1",
                "asin": "B000000001",
                "amazon_product_detail_text": "",
                "amazon_product_description": "Keep existing description",
                "amazon_feature_bullets": "",
            },
            {
                "supplier_sku": "SKU-2",
                "asin": "B000000002",
                "amazon_product_detail_text": "",
                "amazon_product_description": "",
                "amazon_feature_bullets": "",
            },
        ],
    )

    result = apply_page_evidence_backfill_to_review_packs(
        backfill_results_path=_backfill_path(tmp_path),
        review_pack_paths=[_pack_path(tmp_path)],
        output_dir=tmp_path / "out",
        proof_base_dir=tmp_path / "proof",
        backup_base_dir=tmp_path / "backups",
        observed_utc=OBSERVED,
        execute=True,
    )

    live_pack = pd.read_csv(_pack_path(tmp_path), dtype=str).fillna("")
    assert live_pack.iloc[0]["amazon_product_detail_text"] == "Backfilled details"
    assert live_pack.iloc[0]["amazon_product_description"] == "Keep existing description"
    assert live_pack.iloc[0]["amazon_feature_bullets"] == "Backfilled bullets"
    assert live_pack.iloc[1]["amazon_product_description"] == ""
    manifest = pd.read_csv(result.manifest_path, dtype=str).fillna("")
    assert result.updated_rows == 1
    assert result.updated_cells == 2
    assert Path(manifest.iloc[0]["backup_path"]).exists()
    backup = pd.read_csv(manifest.iloc[0]["backup_path"], dtype=str).fillna("")
    assert backup.iloc[0]["amazon_product_detail_text"] == ""
