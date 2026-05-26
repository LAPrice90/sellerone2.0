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

from scripts.one_off import HF010_build_scope_expansion_candidates as hf010


def _write_csv(path: Path, rows: list[dict[str, object]], *, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def test_hf010_build_scope_expansion_candidates(tmp_path: Path, monkeypatch) -> None:
    identity_path = tmp_path / "out" / "analysis_reports" / "hf_learning_identity_bridge_latest.csv"
    foundation_path = tmp_path / "out" / "analysis_reports" / "hf_learning_foundation_metrics_latest.csv"
    alignment_path = tmp_path / "out" / "analysis_reports" / "hf_learning_alignment_30d_latest.csv"

    _write_csv(
        identity_path,
        [
            {
                "snapshot_utc": "2026-04-18T10:00:00Z",
                "candidate_id": "C_OUT_1",
                "supplier_id": "SUP-1",
                "supplier_sku": "SKU-1",
                "asin": "ASIN-OUT",
                "sku_resolution_status": "UNRESOLVED_ASIN_NOT_IN_H_SCOPE",
                "latest_source_utc": "2026-04-18T08:01:00Z",
                "latest_source_name": "screening",
            },
            {
                "snapshot_utc": "2026-04-18T10:00:00Z",
                "candidate_id": "C_OUT_2",
                "supplier_id": "SUP-2",
                "supplier_sku": "SKU-2",
                "asin": "ASIN-OUT-2",
                "sku_resolution_status": "UNRESOLVED_ASIN_NOT_IN_H_SCOPE",
                "latest_source_utc": "2026-04-18T08:02:00Z",
                "latest_source_name": "screening",
            },
            {
                "snapshot_utc": "2026-04-18T10:00:00Z",
                "candidate_id": "C_STALE",
                "supplier_id": "SUP-3",
                "supplier_sku": "SKU-3",
                "asin": "",
                "sku_resolution_status": "UNRESOLVED_NO_ASIN_SOURCE_STALE",
                "latest_source_utc": "2026-04-17T08:00:00Z",
                "latest_source_name": "recommendation",
            },
            {
                "snapshot_utc": "2026-04-18T10:00:00Z",
                "candidate_id": "C_NO_ASIN",
                "supplier_id": "SUP-4",
                "supplier_sku": "SKU-4",
                "asin": "",
                "sku_resolution_status": "UNRESOLVED_NO_ASIN",
                "latest_source_utc": "2026-04-18T08:03:00Z",
                "latest_source_name": "screening",
            },
            {
                "snapshot_utc": "2026-04-18T10:00:00Z",
                "candidate_id": "C_IN_SCOPE",
                "supplier_id": "SUP-5",
                "supplier_sku": "SKU-5",
                "asin": "ASIN-IN",
                "sku_resolution_status": "RESOLVED_FROM_H_SNAPSHOT",
                "latest_source_utc": "2026-04-18T08:04:00Z",
                "latest_source_name": "screening",
            },
        ],
        columns=[
            "snapshot_utc",
            "candidate_id",
            "supplier_id",
            "supplier_sku",
            "asin",
            "sku_resolution_status",
            "latest_source_utc",
            "latest_source_name",
        ],
    )

    _write_csv(
        foundation_path,
        [
            {
                "snapshot_utc": "2026-04-18T10:00:00Z",
                "metric_name": "identity_rows_asin_not_in_h_scope",
                "metric_value": "2",
            },
            {
                "snapshot_utc": "2026-04-18T10:00:00Z",
                "metric_name": "identity_rows_with_asin",
                "metric_value": "3",
            },
            {
                "snapshot_utc": "2026-04-18T10:00:00Z",
                "metric_name": "identity_asin_h_scope_overlap_rate",
                "metric_value": "0.3333",
            },
        ],
        columns=["snapshot_utc", "metric_name", "metric_value"],
    )

    _write_csv(
        alignment_path,
        [
            {
                "alignment_window_end_utc": "2026-04-18T10:01:00Z",
                "sku": "SKU-X",
                "asin": "ASIN-OUT",
                "dominant_discrepancy_class": "missing_expected_baseline",
            }
        ],
        columns=["alignment_window_end_utc", "sku", "asin", "dominant_discrepancy_class"],
    )

    monkeypatch.setattr(hf010, "IDENTITY_PATH", identity_path)
    monkeypatch.setattr(hf010, "FOUNDATION_METRICS_PATH", foundation_path)
    monkeypatch.setattr(hf010, "ALIGNMENT_PATH", alignment_path)
    monkeypatch.setattr(hf010, "REQUIRED_INPUTS", [identity_path, foundation_path, alignment_path])
    monkeypatch.setattr(hf010, "_utc_now_iso", lambda: "2026-04-18T12:00:00Z")

    candidate_output = tmp_path / "out" / "analysis_reports" / "hf_scope_expansion_candidates_latest.csv"
    summary_output = tmp_path / "out" / "analysis_reports" / "hf_scope_expansion_summary_latest.csv"
    result = hf010.build_scope_expansion(
        candidate_output_path=candidate_output,
        summary_output_path=summary_output,
    )

    assert result.candidate_rows == 5
    assert result.outside_h_scope_rows == 2
    assert result.stale_source_rows == 1
    assert result.no_asin_rows == 1

    candidate_df = pd.read_csv(candidate_output, dtype=str).fillna("")
    assert candidate_df.columns.tolist() == hf010.CANDIDATE_COLUMNS
    assert not candidate_df.astype(str).apply(lambda col: col.str.strip().str.lower().eq("nan")).any().any()
    assert candidate_df.iloc[0]["route_bucket"] == "outside_h_scope_with_capture_path"
    assert candidate_df.iloc[0]["priority_rank"] == "1"
    assert (
        candidate_df[candidate_df["candidate_id"] == "C_OUT_1"]["current_alignment_class"].iloc[0]
        == "missing_expected_baseline"
    )
    assert (
        candidate_df[candidate_df["candidate_id"] == "C_IN_SCOPE"]["route_bucket"].iloc[0]
        == "already_in_h_scope"
    )

    summary_df = pd.read_csv(summary_output, dtype=str).fillna("").set_index("metric_name")
    assert summary_df.loc["route_bucket_count:outside_h_scope_with_capture_path", "metric_value"] == "2"
    assert summary_df.loc["route_bucket_count:stale_source", "metric_value"] == "1"
    assert summary_df.loc["route_bucket_count:no_asin", "metric_value"] == "1"
    assert summary_df.loc[
        "reconcile_identity_asin_not_in_scope_vs_outside_bucket",
        "metric_value",
    ] == "match"
