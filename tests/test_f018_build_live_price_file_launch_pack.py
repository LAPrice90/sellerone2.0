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

from scripts.one_off.F018_build_live_price_file_launch_pack import build_live_price_file_launch_pack


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _metric(summary_df: pd.DataFrame, metric: str) -> str:
    rows = summary_df.loc[summary_df["metric"] == metric]
    if rows.empty:
        return ""
    return str(rows.iloc[0]["value"])


def test_f018_builds_active_supplier_launch_baseline_and_stale_flags(tmp_path: Path) -> None:
    queue_state_path = tmp_path / "queue_state.csv"
    row_state_path = tmp_path / "row_state.csv"
    first_checks_path = tmp_path / "first_checks.csv"
    scrape_path = tmp_path / "scrape.csv"
    recommendations_path = tmp_path / "recommendations.csv"
    approval_path = tmp_path / "approval.csv"
    output_dir = tmp_path / "analysis"

    _write_csv(
        queue_state_path,
        [
            {
                "queue_id": "default",
                "current_supplier_id": "stocklist_supplier",
                "current_run_id": "stocklist_supplier_20260422T120000Z",
                "updated_at_utc": "2026-04-22T12:00:00Z",
            }
        ],
    )

    supplier_dir = queue_state_path.parent / "suppliers" / "stocklist_supplier"
    _write_csv(
        supplier_dir / "raw_current.csv",
        [
            {"supplier_sku": "A1"},
            {"supplier_sku": "A2"},
            {"supplier_sku": "A3"},
        ],
    )
    _write_csv(
        supplier_dir / "canonical_current.csv",
        [
            {"supplier_sku": "A1"},
            {"supplier_sku": "A2"},
        ],
    )

    _write_csv(
        row_state_path,
        [
            {
                "supplier_id": "stocklist_supplier",
                "row_status": "pending",
                "pf": "",
                "status_reason": "",
                "updated_at_utc": "2026-04-22T13:00:00Z",
            },
            {
                "supplier_id": "stocklist_supplier",
                "row_status": "pending",
                "pf": "",
                "status_reason": "",
                "updated_at_utc": "2026-04-22T13:00:00Z",
            },
            {
                "supplier_id": "stocklist_supplier",
                "row_status": "timeout",
                "pf": "FAIL",
                "status_reason": "ROIFAIL",
                "updated_at_utc": "2026-04-22T13:00:00Z",
            },
            {
                "supplier_id": "stocklist_supplier",
                "row_status": "pass",
                "pf": "PASS",
                "status_reason": "PASS",
                "updated_at_utc": "2026-04-22T13:00:00Z",
            },
            {
                "supplier_id": "other_supplier",
                "row_status": "pass",
                "pf": "PASS",
                "status_reason": "PASS",
                "updated_at_utc": "2026-04-22T13:00:00Z",
            },
        ],
    )

    _write_csv(
        first_checks_path,
        [
            {"pf": "PASS"},
            {"pf": "PASS"},
            {"pf": "FAIL"},
        ],
    )

    _write_csv(
        scrape_path,
        [
            {"pf": "PASS"},
            {"pf": "FAIL"},
            {"pf": "FAIL"},
            {"pf": "RESCAN"},
        ],
    )

    _write_csv(
        recommendations_path,
        [
            {"supplier_id": "shure_cosmetics", "recommendation_utc": "2026-04-07T18:35:00Z"},
            {"supplier_id": "shure_cosmetics", "recommendation_utc": "2026-04-07T18:35:00Z"},
        ],
    )

    _write_csv(
        approval_path,
        [
            {"supplier_id": "shure_cosmetics", "queue_utc": "2026-04-07T18:35:00Z"},
            {"supplier_id": "shure_cosmetics", "queue_utc": "2026-04-07T18:35:00Z"},
        ],
    )

    result = build_live_price_file_launch_pack(
        queue_state_path=queue_state_path,
        row_state_path=row_state_path,
        first_checks_path=first_checks_path,
        scrape_evidence_path=scrape_path,
        recommendations_path=recommendations_path,
        approval_queue_path=approval_path,
        output_dir=output_dir,
        observed_utc="2026-04-22T14:00:00Z",
    )

    baseline = result.baseline_df.iloc[0].to_dict()
    assert baseline["active_supplier_id"] == "stocklist_supplier"
    assert baseline["raw_rows"] == "3"
    assert baseline["canonical_rows"] == "2"
    assert baseline["row_state_rows_active_supplier"] == "4"
    assert baseline["row_state_completed_rows"] == "2"
    assert baseline["row_state_pending_rows"] == "2"
    assert baseline["row_state_timeout_rows"] == "1"
    assert baseline["row_state_pass_rows"] == "1"
    assert baseline["row_state_fail_rows"] == "1"
    assert baseline["recommendations_rows"] == "2"
    assert baseline["recommendations_active_supplier_rows"] == "0"
    assert baseline["recommendations_supplier_mismatch_flag"] == "1"
    assert baseline["recommendations_stale_vs_row_state_flag"] == "1"
    assert baseline["approval_supplier_mismatch_flag"] == "1"
    assert baseline["approval_stale_vs_row_state_flag"] == "1"
    assert baseline["derived_launch_surface_safe_flag"] == "0"
    assert baseline["launch_readiness_state"] == "ready_for_pass_review_with_stale_derived_surfaces"

    assert _metric(result.summary_df, "row_state_rows_active_supplier") == "4"
    assert _metric(result.summary_df, "row_state_completed_rows") == "2"
    assert _metric(result.summary_df, "row_state_pending_rows") == "2"
    assert _metric(result.summary_df, "launch_readiness_state") == "ready_for_pass_review_with_stale_derived_surfaces"
    assert result.baseline_latest_path.exists()
    assert result.summary_latest_path.exists()
