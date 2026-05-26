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

from scripts.one_off.HF006_build_alignment_missing_asin_pack import build_alignment_missing_asin_pack


def test_hf006_builds_pack_from_alignment_no_source_with_scrape_priority(tmp_path: Path) -> None:
    alignment_path = tmp_path / "out" / "analysis_reports" / "hf_learning_alignment_30d_latest.csv"
    identity_path = tmp_path / "out" / "analysis_reports" / "hf_learning_identity_bridge_latest.csv"
    scrape_path = tmp_path / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv"
    output_dir = tmp_path / "out" / "analysis_reports"

    alignment_path.parent.mkdir(parents=True, exist_ok=True)
    identity_path.parent.mkdir(parents=True, exist_ok=True)
    scrape_path.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {"alignment_window_end_utc": "2026-04-17T10:00:00Z", "sku": "SKU-1", "asin": "A1", "expected_units_source": "no_source"},
            {"alignment_window_end_utc": "2026-04-17T10:00:00Z", "sku": "SKU-2", "asin": "A2", "expected_units_source": ""},
            {"alignment_window_end_utc": "2026-04-17T10:00:00Z", "sku": "SKU-3", "asin": "A3", "expected_units_source": "sales_validation_asin"},
            {"alignment_window_end_utc": "2026-04-17T10:00:00Z", "sku": "SKU-1B", "asin": "A1", "expected_units_source": "no_source"},
        ]
    ).to_csv(alignment_path, index=False)

    pd.DataFrame(
        [
            {"candidate_id": "C1", "supplier_sku": "SUP-1", "sku": "SKU-1", "asin": "A1"},
            {"candidate_id": "C2", "supplier_sku": "SUP-2", "sku": "SKU-2", "asin": "A2"},
        ]
    ).to_csv(identity_path, index=False)

    pd.DataFrame(
        [
            {"observed_utc": "2026-04-17T09:00:00Z", "supplier_id": "stocklist_supplier", "supplier_sku": "SUP-1", "asin": "A1"},
        ]
    ).to_csv(scrape_path, index=False)

    result = build_alignment_missing_asin_pack(
        alignment_path=alignment_path,
        identity_path=identity_path,
        scrape_path=scrape_path,
        output_dir=output_dir,
        observed_utc="2026-04-17T18:00:00Z",
    )

    assert result.report_path.exists()
    assert result.latest_path.exists()
    assert result.summary["alignment_no_source_unique_asins"] == 2
    assert result.summary["pack_rows"] == 2
    assert result.summary["scrape_present_rows"] == 1
    assert result.summary["scrape_missing_rows"] == 1

    pack_df = result.pack_df.copy()
    assert list(pack_df["sample_rank"]) == ["1", "2"]
    assert pack_df.iloc[0]["asin"] == "A2"
    assert pack_df.iloc[0]["supplier_sku"] == "SUP-2"
    assert pack_df.iloc[0]["scrape_present_flag"] == "0"
    assert pack_df.iloc[1]["asin"] == "A1"
    assert pack_df.iloc[1]["supplier_sku"] == "SUP-1"
    assert pack_df.iloc[1]["scrape_present_flag"] == "1"
    assert pack_df.iloc[0]["validation_case"] == "alignment_missing_expected_baseline"


def test_hf006_only_not_in_scrape_filter(tmp_path: Path) -> None:
    alignment_path = tmp_path / "out" / "analysis_reports" / "hf_learning_alignment_30d_latest.csv"
    identity_path = tmp_path / "out" / "analysis_reports" / "hf_learning_identity_bridge_latest.csv"
    scrape_path = tmp_path / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv"
    output_dir = tmp_path / "out" / "analysis_reports"

    alignment_path.parent.mkdir(parents=True, exist_ok=True)
    scrape_path.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {"alignment_window_end_utc": "2026-04-17T10:00:00Z", "sku": "SKU-1", "asin": "A1", "expected_units_source": "no_source"},
            {"alignment_window_end_utc": "2026-04-17T10:00:00Z", "sku": "SKU-2", "asin": "A2", "expected_units_source": "no_source"},
        ]
    ).to_csv(alignment_path, index=False)
    pd.DataFrame(columns=["candidate_id", "supplier_sku", "sku", "asin"]).to_csv(identity_path, index=False)
    pd.DataFrame(
        [
            {"observed_utc": "2026-04-17T09:00:00Z", "supplier_id": "stocklist_supplier", "supplier_sku": "SUP-1", "asin": "A1"},
        ]
    ).to_csv(scrape_path, index=False)

    result = build_alignment_missing_asin_pack(
        alignment_path=alignment_path,
        identity_path=identity_path,
        scrape_path=scrape_path,
        output_dir=output_dir,
        only_not_in_scrape=True,
        observed_utc="2026-04-17T18:00:00Z",
    )
    assert result.summary["pack_rows"] == 1
    assert result.pack_df.iloc[0]["asin"] == "A2"
    assert result.pack_df.iloc[0]["scrape_present_flag"] == "0"
