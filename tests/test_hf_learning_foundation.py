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

from scripts.one_off import HF000_build_learning_foundation as hf


def _empty_df(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def _write_csv(path: Path, rows: list[dict[str, str]], *, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def test_build_identity_bridge_resolution_states() -> None:
    screening_df = pd.DataFrame(
        [
            {
                "candidate_id": "C_RES",
                "feeder_candidate_id": "F_RES",
                "supplier_id": "SUP-1",
                "supplier_sku": "SUPSKU-1",
                "asin": "ASIN-1",
                "observed_utc": "2026-04-17T10:00:00Z",
            },
            {
                "candidate_id": "C_NO_ASIN",
                "feeder_candidate_id": "F_NO_ASIN",
                "supplier_id": "SUP-2",
                "supplier_sku": "SUPSKU-2",
                "asin": "",
                "observed_utc": "2026-04-17T10:05:00Z",
            },
            {
                "candidate_id": "C_MULTI",
                "feeder_candidate_id": "F_MULTI",
                "supplier_id": "SUP-3",
                "supplier_sku": "SUPSKU-3",
                "asin": "ASIN-2",
                "observed_utc": "2026-04-17T10:10:00Z",
            },
            {
                "candidate_id": "C_MISSING_SCOPE",
                "feeder_candidate_id": "F_MISS",
                "supplier_id": "SUP-4",
                "supplier_sku": "SUPSKU-4",
                "asin": "ASIN-9",
                "observed_utc": "2026-04-17T10:15:00Z",
            },
            {
                "candidate_id": "C_LEGACY_FALLBACK",
                "feeder_candidate_id": "F_LEGACY",
                "supplier_id": "SUP-6",
                "supplier_sku": "SUPSKU-6",
                "asin": "",
                "observed_utc": "2026-04-17T10:30:00Z",
            },
        ]
    )
    queue_df = pd.DataFrame(
        [
            {
                "candidate_id": "C_MULTI",
                "feeder_candidate_id": "F_MULTI",
                "supplier_id": "SUP-3",
                "supplier_sku": "SUPSKU-3",
                "asin": "ASIN-3",
                "queue_utc": "2026-04-17T10:20:00Z",
            }
        ]
    )
    decision_df = _empty_df(
        [
            "candidate_id",
            "feeder_candidate_id",
            "supplier_id",
            "supplier_sku",
            "asin",
            "decision_utc",
        ]
    )
    handoff_df = _empty_df(
        [
            "candidate_id",
            "feeder_candidate_id",
            "supplier_id",
            "supplier_sku",
            "asin",
            "handoff_utc",
        ]
    )
    recommendation_df = pd.DataFrame(
        [
            {
                "candidate_id": "C_AMBIG",
                "feeder_candidate_id": "F_AMBIG",
                "supplier_id": "SUP-5",
                "supplier_sku": "SUPSKU-5",
                "asin": "ASIN-4",
                "recommendation_utc": "2026-04-17T10:25:00Z",
            }
        ]
    )
    legacy_evidence_df = pd.DataFrame(
        [
            {
                "candidate_id": "C_LEGACY_FALLBACK",
                "supplier_sku": "SUPSKU-6",
                "asin": "ASIN-6",
                "observed_utc": "2026-04-17T09:59:00Z",
            }
        ]
    )
    listing_df = pd.DataFrame(
        [
            {"asin": "ASIN-1", "sku": "SKU-1"},
            {"asin": "ASIN-4", "sku": "SKU-4A"},
            {"asin": "ASIN-4", "sku": "SKU-4B"},
            {"asin": "ASIN-6", "sku": "SKU-6"},
        ]
    )

    bridge = hf._build_identity_bridge(
        screening_df=screening_df,
        queue_df=queue_df,
        decisions_df=decision_df,
        handoff_df=handoff_df,
        recommendation_df=recommendation_df,
        legacy_evidence_df=legacy_evidence_df,
        listing_df=listing_df,
        snapshot_utc="2026-04-17T18:00:00Z",
    )

    rows = bridge.set_index("candidate_id")
    assert rows.loc["C_RES", "sku_resolution_status"] == "RESOLVED_FROM_H_SNAPSHOT"
    assert rows.loc["C_RES", "sku"] == "SKU-1"
    assert rows.loc["C_NO_ASIN", "sku_resolution_status"] == "UNRESOLVED_NO_ASIN"
    assert rows.loc["C_MULTI", "sku_resolution_status"] == "UNRESOLVED_MULTI_ASIN"
    assert rows.loc["C_MULTI", "asin_conflict_flag"] == "1"
    assert rows.loc["C_AMBIG", "sku_resolution_status"] == "UNRESOLVED_AMBIGUOUS_ASIN"
    assert rows.loc["C_MISSING_SCOPE", "sku_resolution_status"] == "UNRESOLVED_ASIN_NOT_IN_H_SCOPE"
    assert rows.loc["C_LEGACY_FALLBACK", "sku_resolution_status"] == "RESOLVED_FROM_H_SNAPSHOT"
    assert rows.loc["C_LEGACY_FALLBACK", "sku"] == "SKU-6"
    assert rows.loc["C_LEGACY_FALLBACK", "sku_resolution_source"] == "legacy_candidate"


def test_build_identity_bridge_marks_stale_no_asin_source() -> None:
    screening_df = pd.DataFrame(
        [
            {
                "candidate_id": "C_STALE_NO_ASIN",
                "feeder_candidate_id": "F_STALE_NO_ASIN",
                "supplier_id": "SUP-STALE",
                "supplier_sku": "SUPSKU-STALE",
                "asin": "",
                "observed_utc": "2026-04-01T10:00:00Z",
            }
        ]
    )
    empty_events = _empty_df(
        [
            "candidate_id",
            "feeder_candidate_id",
            "supplier_id",
            "supplier_sku",
            "asin",
            "queue_utc",
        ]
    )
    bridge = hf._build_identity_bridge(
        screening_df=screening_df,
        queue_df=empty_events,
        decisions_df=empty_events.rename(columns={"queue_utc": "decision_utc"}),
        handoff_df=empty_events.rename(columns={"queue_utc": "handoff_utc"}),
        recommendation_df=empty_events.rename(columns={"queue_utc": "recommendation_utc"}),
        legacy_evidence_df=_empty_df(["candidate_id", "supplier_sku", "asin", "observed_utc"]),
        listing_df=pd.DataFrame([{"asin": "ASIN-1", "sku": "SKU-1"}]),
        snapshot_utc="2026-04-17T18:00:00Z",
    )
    rows = bridge.set_index("candidate_id")
    assert rows.loc["C_STALE_NO_ASIN", "sku_resolution_status"] == "UNRESOLVED_NO_ASIN_SOURCE_STALE"


def test_build_assumption_snapshots_stage_precedence() -> None:
    queue_df = pd.DataFrame(
        [
            {
                "candidate_id": "C_HANDOFF",
                "feeder_candidate_id": "F_H",
                "supplier_id": "SUP-H",
                "supplier_sku": "SUPSKU-H",
                "recommendation_status": "queued",
                "recommended_test_qty": "3",
                "estimated_roi_pct": "24.5",
                "estimated_margin_gbp": "2.10",
                "estimated_demand": "11",
                "queue_utc": "2026-04-17T08:00:00Z",
            },
            {
                "candidate_id": "C_QUEUE",
                "feeder_candidate_id": "F_Q",
                "supplier_id": "SUP-Q",
                "supplier_sku": "SUPSKU-Q",
                "recommendation_status": "queued",
                "recommended_test_qty": "4",
                "estimated_roi_pct": "21.0",
                "estimated_margin_gbp": "1.70",
                "estimated_demand": "7",
                "queue_utc": "2026-04-17T08:10:00Z",
            },
        ]
    )
    decision_df = pd.DataFrame(
        [
            {
                "candidate_id": "C_HANDOFF",
                "feeder_candidate_id": "F_H",
                "supplier_id": "SUP-H",
                "supplier_sku": "SUPSKU-H",
                "decision_action": "approve",
                "final_decision_status": "approved",
                "decision_source": "operator",
                "actor": "luke",
                "recommended_test_qty": "5",
                "recommendation_status": "approved",
                "decision_utc": "2026-04-17T09:00:00Z",
                "source_row_hash": "DEC-H",
                "source_file_path": "out/systems/F/history/feeder_approval_decisions_log.csv",
                "source_seen_at_utc": "2026-04-17T09:00:02Z",
            },
            {
                "candidate_id": "C_DECISION",
                "feeder_candidate_id": "F_D",
                "supplier_id": "SUP-D",
                "supplier_sku": "SUPSKU-D",
                "decision_action": "reject",
                "final_decision_status": "rejected",
                "decision_source": "operator",
                "actor": "luke",
                "recommended_test_qty": "2",
                "recommendation_status": "rejected",
                "decision_utc": "2026-04-17T09:10:00Z",
                "source_row_hash": "DEC-D",
                "source_file_path": "out/systems/F/history/feeder_approval_decisions_log.csv",
                "source_seen_at_utc": "2026-04-17T09:10:02Z",
            },
        ]
    )
    handoff_df = pd.DataFrame(
        [
            {
                "candidate_id": "C_HANDOFF",
                "feeder_candidate_id": "F_H",
                "supplier_id": "SUP-H",
                "supplier_sku": "SUPSKU-H",
                "asin": "ASIN-H",
                "approved_test_qty": "12",
                "final_decision_status": "handoff_ready",
                "handoff_utc": "2026-04-17T09:30:00Z",
                "source_row_hash": "HO-H",
                "source_file_path": "out/systems/F/live/feeder_po_handoff_ready_live.csv",
                "source_seen_at_utc": "2026-04-17T09:30:02Z",
            }
        ]
    )
    recommendation_df = pd.DataFrame(
        [
            {
                "candidate_id": "C_QUEUE",
                "feeder_candidate_id": "F_Q",
                "supplier_id": "SUP-Q",
                "supplier_sku": "SUPSKU-Q",
                "asin": "ASIN-Q",
                "recommendation_status": "candidate",
                "recommended_test_qty": "6",
                "estimated_roi_pct": "19.0",
                "estimated_margin_gbp": "1.30",
                "estimated_demand": "5",
                "recommendation_utc": "2026-04-17T07:30:00Z",
                "source_row_hash": "REC-Q",
                "source_file_path": "out/systems/F/live/feeder_candidate_recommendations_live.csv",
                "source_seen_at_utc": "2026-04-17T07:30:05Z",
            },
            {
                "candidate_id": "C_RECOMMEND",
                "feeder_candidate_id": "F_R",
                "supplier_id": "SUP-R",
                "supplier_sku": "SUPSKU-R",
                "asin": "ASIN-R",
                "recommendation_status": "candidate",
                "recommended_test_qty": "8",
                "estimated_roi_pct": "32.0",
                "estimated_margin_gbp": "3.00",
                "estimated_demand": "14",
                "recommendation_utc": "2026-04-17T07:35:00Z",
                "source_row_hash": "REC-R",
                "source_file_path": "out/systems/F/live/feeder_candidate_recommendations_live.csv",
                "source_seen_at_utc": "2026-04-17T07:35:05Z",
            },
        ]
    )

    snapshot = hf._build_assumption_snapshots(
        queue_df=queue_df,
        decisions_df=decision_df,
        handoff_df=handoff_df,
        recommendation_df=recommendation_df,
        snapshot_utc="2026-04-17T18:00:00Z",
    ).set_index("candidate_id")

    assert snapshot.loc["C_HANDOFF", "snapshot_stage"] == "po_handoff"
    assert snapshot.loc["C_HANDOFF", "assumption_anchor_source"] == "po_handoff"
    assert snapshot.loc["C_HANDOFF", "in_scope_approval_decision_flag"] == "1"
    assert snapshot.loc["C_HANDOFF", "recommended_test_qty"] == "12"
    assert snapshot.loc["C_HANDOFF", "final_decision_status"] == "handoff_ready"

    assert snapshot.loc["C_DECISION", "snapshot_stage"] == "approval_decision"
    assert snapshot.loc["C_DECISION", "in_scope_approval_decision_flag"] == "1"
    assert snapshot.loc["C_DECISION", "decision_action"] == "reject"

    assert snapshot.loc["C_QUEUE", "snapshot_stage"] == "approval_queue"
    assert snapshot.loc["C_QUEUE", "in_scope_approval_decision_flag"] == "0"
    assert snapshot.loc["C_QUEUE", "recommended_test_qty"] == "4"

    assert snapshot.loc["C_RECOMMEND", "snapshot_stage"] == "recommendation_only"
    assert snapshot.loc["C_RECOMMEND", "in_scope_approval_decision_flag"] == "0"
    assert snapshot.loc["C_RECOMMEND", "recommended_test_qty"] == "8"


def test_build_foundation_smoke(tmp_path: Path, monkeypatch) -> None:
    screening_path = tmp_path / "out" / "systems" / "F" / "live" / "f_screening_row_state_live.csv"
    queue_path = tmp_path / "out" / "systems" / "F" / "live" / "feeder_approval_queue_live.csv"
    decisions_path = tmp_path / "out" / "systems" / "F" / "history" / "feeder_approval_decisions_log.csv"
    handoff_path = tmp_path / "out" / "systems" / "F" / "live" / "feeder_po_handoff_ready_live.csv"
    recommendation_path = tmp_path / "out" / "systems" / "F" / "live" / "feeder_candidate_recommendations_live.csv"
    listing_path = tmp_path / "out" / "listing_offer_snapshot_latest.csv"
    summary_path = tmp_path / "out" / "sku_performance_summary.csv"

    _write_csv(
        screening_path,
        [
            {
                "candidate_id": "C1",
                "feeder_candidate_id": "F1",
                "supplier_id": "SUP-1",
                "supplier_sku": "SUPSKU-1",
                "asin": "ASIN-1",
                "observed_utc": "2026-04-17T08:00:00Z",
            }
        ],
        columns=["candidate_id", "feeder_candidate_id", "supplier_id", "supplier_sku", "asin", "observed_utc"],
    )
    _write_csv(
        queue_path,
        [],
        columns=[
            "candidate_id",
            "feeder_candidate_id",
            "supplier_id",
            "supplier_sku",
            "asin",
            "recommendation_status",
            "recommended_test_qty",
            "estimated_roi_pct",
            "estimated_margin_gbp",
            "estimated_demand",
            "queue_utc",
        ],
    )
    _write_csv(
        decisions_path,
        [
            {
                "candidate_id": "C1",
                "feeder_candidate_id": "F1",
                "supplier_id": "SUP-1",
                "supplier_sku": "SUPSKU-1",
                "decision_action": "approve",
                "final_decision_status": "approved",
                "decision_source": "operator",
                "actor": "luke",
                "recommended_test_qty": "5",
                "recommendation_status": "approved",
                "decision_utc": "2026-04-17T09:00:00Z",
                "source_row_hash": "HASH-DEC-1",
                "source_file_path": "out/systems/F/history/feeder_approval_decisions_log.csv",
                "source_seen_at_utc": "2026-04-17T09:00:02Z",
            }
        ],
        columns=[
            "candidate_id",
            "feeder_candidate_id",
            "supplier_id",
            "supplier_sku",
            "decision_action",
            "final_decision_status",
            "decision_source",
            "actor",
            "recommended_test_qty",
            "recommendation_status",
            "decision_utc",
            "source_row_hash",
            "source_file_path",
            "source_seen_at_utc",
        ],
    )
    _write_csv(
        handoff_path,
        [],
        columns=[
            "candidate_id",
            "feeder_candidate_id",
            "supplier_id",
            "supplier_sku",
            "asin",
            "approved_test_qty",
            "final_decision_status",
            "handoff_utc",
            "source_row_hash",
            "source_file_path",
            "source_seen_at_utc",
        ],
    )
    _write_csv(
        recommendation_path,
        [
            {
                "candidate_id": "C2",
                "feeder_candidate_id": "F2",
                "supplier_id": "SUP-2",
                "supplier_sku": "SUPSKU-2",
                "asin": "ASIN-2",
                "recommendation_status": "candidate",
                "recommended_test_qty": "4",
                "estimated_roi_pct": "22.5",
                "estimated_margin_gbp": "1.60",
                "estimated_demand": "9",
                "recommendation_utc": "2026-04-17T07:30:00Z",
                "source_row_hash": "HASH-REC-2",
                "source_file_path": "out/systems/F/live/feeder_candidate_recommendations_live.csv",
                "source_seen_at_utc": "2026-04-17T07:30:03Z",
            }
        ],
        columns=[
            "candidate_id",
            "feeder_candidate_id",
            "supplier_id",
            "supplier_sku",
            "asin",
            "recommendation_status",
            "recommended_test_qty",
            "estimated_roi_pct",
            "estimated_margin_gbp",
            "estimated_demand",
            "recommendation_utc",
            "source_row_hash",
            "source_file_path",
            "source_seen_at_utc",
        ],
    )
    _write_csv(listing_path, [{"asin": "ASIN-1", "sku": "SKU-1"}], columns=["asin", "sku"])
    _write_csv(
        summary_path,
        [{"sku": "SKU-1", "units_30d": "10", "profit_30d_gbp": "25.0"}],
        columns=["sku", "units_30d", "profit_30d_gbp"],
    )

    monkeypatch.setattr(hf, "SCREENING_PATH", screening_path)
    monkeypatch.setattr(hf, "QUEUE_PATH", queue_path)
    monkeypatch.setattr(hf, "DECISIONS_PATH", decisions_path)
    monkeypatch.setattr(hf, "HANDOFF_PATH", handoff_path)
    monkeypatch.setattr(hf, "RECOMMENDATION_PATH", recommendation_path)
    monkeypatch.setattr(hf, "LEGACY_EVIDENCE_PATH", tmp_path / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv")
    monkeypatch.setattr(hf, "LISTING_SNAPSHOT_PATH", listing_path)
    monkeypatch.setattr(hf, "SKU_SUMMARY_PATH", summary_path)
    monkeypatch.setattr(
        hf,
        "REQUIRED_INPUTS",
        [
            screening_path,
            queue_path,
            decisions_path,
            handoff_path,
            recommendation_path,
            listing_path,
            summary_path,
        ],
    )
    monkeypatch.setattr(hf, "_utc_now_iso", lambda: "2026-04-17T18:00:00Z")

    identity_output = tmp_path / "out" / "analysis_reports" / "identity.csv"
    assumption_output = tmp_path / "out" / "analysis_reports" / "assumption.csv"
    metrics_output = tmp_path / "out" / "analysis_reports" / "metrics.csv"
    result = hf.build_foundation(
        repo_root=tmp_path,
        identity_output_path=identity_output,
        assumption_output_path=assumption_output,
        metrics_output_path=metrics_output,
    )

    assert result.identity_rows == 2
    assert result.assumption_rows == 2
    assert result.resolved_sku_rows == 1
    assert result.unresolved_sku_rows == 1
    assert result.decision_scope_rows == 1
    assert result.decision_scope_snapshot_rows == 1
    assert identity_output.exists()
    assert assumption_output.exists()
    assert metrics_output.exists()

    identity_df = pd.read_csv(identity_output, dtype=str).fillna("")
    assumption_df = pd.read_csv(assumption_output, dtype=str).fillna("")
    metrics_df = pd.read_csv(metrics_output, dtype=str).fillna("")
    assert identity_df.columns.tolist() == hf.IDENTITY_COLUMNS
    assert assumption_df.columns.tolist() == hf.ASSUMPTION_COLUMNS
    c1 = identity_df[identity_df["candidate_id"] == "C1"].iloc[0]
    c2 = identity_df[identity_df["candidate_id"] == "C2"].iloc[0]
    assert c1["sku_resolution_status"] == "RESOLVED_FROM_H_SNAPSHOT"
    assert c1["sku"] == "SKU-1"
    assert c2["sku_resolution_status"] == "UNRESOLVED_ASIN_NOT_IN_H_SCOPE"
    metric_rows = metrics_df.set_index("metric_name")
    assert metric_rows.loc["identity_rows_total", "metric_value"] == "2"
    assert metric_rows.loc["identity_rows_resolved", "metric_value"] == "1"
    assert metric_rows.loc["identity_rows_without_asin", "metric_value"] == "0"
    assert metric_rows.loc["h_scope_pair_count:listing_snapshot", "metric_value"] == "1"
    assert metric_rows.loc["assumption_stage_count:approval_decision", "metric_value"] == "1"
    assert metric_rows.loc["assumption_stage_count:recommendation_only", "metric_value"] == "1"
