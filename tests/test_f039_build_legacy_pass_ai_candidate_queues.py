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

from scripts.one_off.F039_build_legacy_pass_ai_candidate_queues import build_legacy_pass_ai_candidate_queues


OBSERVED = "2026-05-21T10:00:00Z"


def _write_legacy_handoff(tmp_path: Path) -> Path:
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "bliss_distribution"
        / "fpm_bliss_distribution_20260518T094415Z"
    )
    handoff_dir.mkdir(parents=True, exist_ok=True)
    pass_path = handoff_dir / "f_live_price_file_pass_review_20260518T115122Z.csv"
    near_path = handoff_dir / "f_live_price_file_near_miss_review_20260518T115122Z.csv"
    summary_path = handoff_dir / "f_live_price_file_review_summary_20260518T115122Z.csv"
    pd.DataFrame(
        [
            {
                "active_supplier_id": "bliss_distribution",
                "active_run_id": "fpm_bliss_distribution_20260518T094415Z",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "kuriboh-sleeves",
                "supplier_sku": "KONKKS",
                "asin": "B09HKZWBDN",
                "title": "Yu-Gi-Oh! Kuriboh Kollection Card Sleeves",
            },
            {
                "active_supplier_id": "bliss_distribution",
                "active_run_id": "fpm_bliss_distribution_20260518T094415Z",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "another-pass",
                "supplier_sku": "KON002",
                "asin": "B000000002",
                "title": "Another clean pass",
            },
        ]
    ).to_csv(pass_path, index=False)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "bliss_distribution",
                "active_run_id": "fpm_bliss_distribution_20260518T094415Z",
                "review_batch_id": "near_miss_batch_001",
                "candidate_id": "manual-row",
                "supplier_sku": "KONMAN",
                "asin": "B000000003",
                "title": "Manual row",
            }
        ]
    ).to_csv(near_path, index=False)
    pd.DataFrame(
        [
            {"observed_utc": OBSERVED, "metric": "pass_review_rows", "value": "2"},
            {"observed_utc": OBSERVED, "metric": "near_miss_review_rows", "value": "1"},
        ]
    ).to_csv(summary_path, index=False)
    pd.DataFrame(
        [
            {
                "built_at_utc": OBSERVED,
                "supplier_id": "bliss_distribution",
                "supplier_name": "Bliss Distribution",
                "run_id": "fpm_bliss_distribution_20260518T094415Z",
                "review_snapshot_id": "20260518T115122Z",
                "source_file_path": "Bliss.xlsx",
                "source_seen_at_utc": "2026-05-18T09:43:37Z",
                "completed_at_utc": "2026-05-18T11:51:22Z",
                "pass_review_rows": "2",
                "near_miss_review_rows": "1",
                "hard_reject_rows": "962",
                "pass_review_path": str(pass_path),
                "near_miss_review_path": str(near_path),
                "summary_path": str(summary_path),
                "handoff_dir": str(handoff_dir),
                "published_to_operator_latest_flag": "0",
                "block_reason": "",
                "notes": "legacy pre AI manifest",
            }
        ]
    ).to_csv(handoff_dir / "manifest.csv", index=False)
    return handoff_dir


def test_f039_dry_run_reports_clean_pass_conversion_without_writing(tmp_path: Path) -> None:
    handoff_dir = _write_legacy_handoff(tmp_path)

    result = build_legacy_pass_ai_candidate_queues(
        root=tmp_path,
        observed_utc=OBSERVED,
        execute=False,
    )

    assert result["status_counts"] == {"would_convert": 1}
    assert result["converted_pass_rows"] == 2
    assert result["manual_near_rows_held"] == 1
    assert not (handoff_dir / "candidate_manifest.csv").exists()
    assert not (handoff_dir / "legacy_ai_clean_pass_only_near_miss_empty.csv").exists()


def test_f039_execute_writes_candidate_manifest_for_clean_pass_only(tmp_path: Path) -> None:
    handoff_dir = _write_legacy_handoff(tmp_path)

    result = build_legacy_pass_ai_candidate_queues(
        root=tmp_path,
        observed_utc=OBSERVED,
        execute=True,
    )

    candidate_path = handoff_dir / "candidate_manifest.csv"
    empty_near_path = handoff_dir / "legacy_ai_clean_pass_only_near_miss_empty.csv"
    report_path = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "legacy_pass_ai_candidate_conversion.csv"
    candidate = pd.read_csv(candidate_path, dtype=str).fillna("")
    empty_near = pd.read_csv(empty_near_path, dtype=str).fillna("")
    report = pd.read_csv(report_path, dtype=str).fillna("")

    assert result["status_counts"] == {"converted": 1}
    assert candidate.iloc[0]["raw_pass_review_rows"] == "2"
    assert candidate.iloc[0]["raw_near_miss_review_rows"] == "0"
    assert candidate.iloc[0]["raw_near_miss_review_path"] == str(empty_near_path)
    assert "manual_near_rows_held=1" in candidate.iloc[0]["notes"]
    assert empty_near.empty
    assert list(empty_near.columns) == [
        "active_supplier_id",
        "active_run_id",
        "review_batch_id",
        "candidate_id",
        "supplier_sku",
        "asin",
        "title",
    ]
    assert (handoff_dir / "manifest.pre_ai_legacy_backup.csv").exists()
    assert report.iloc[0]["status"] == "converted"
    assert report.iloc[0]["pass_rows"] == "2"
    assert report.iloc[0]["manual_near_rows_held"] == "1"
