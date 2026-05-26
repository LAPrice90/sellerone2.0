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

from scripts.flows.F.price_list_manager import FPM155_apply_review_intelligence_gate as fpm155_module
from scripts.flows.F.price_list_manager.FPM155_apply_review_intelligence_gate import (
    CURRENT_SCANNER_FAIL_EVIDENCE_COLUMNS,
    apply_review_intelligence_gate,
)
from scripts.flows.F.price_list_manager._schemas import (
    REVIEW_CANDIDATE_MANIFEST_COLUMNS,
    REVIEW_HANDOFF_MANIFEST_COLUMNS,
)
from scripts.flows.O.O400_operator_ui import load_feeder_review_source_df


OBSERVED = "2026-05-20T13:30:00Z"


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_candidate_manifest(
    tmp_path: Path,
    *,
    pass_path: Path,
    near_path: Path,
    summary_path: Path,
) -> Path:
    handoff_dir = pass_path.parent
    manifest_path = handoff_dir / "candidate_manifest.csv"
    pd.DataFrame(
        [
            {
                "built_at_utc": OBSERVED,
                "supplier_id": "supplier_a",
                "supplier_name": "Supplier A",
                "run_id": "run_1",
                "review_snapshot_id": "20260520T133000Z",
                "source_file_path": "supplier.xlsx",
                "source_seen_at_utc": "2026-05-20T12:00:00Z",
                "completed_at_utc": "2026-05-20T13:00:00Z",
                "raw_pass_review_rows": "2",
                "raw_near_miss_review_rows": "0",
                "hard_reject_rows": "0",
                "raw_pass_review_path": str(pass_path),
                "raw_near_miss_review_path": str(near_path),
                "raw_summary_path": str(summary_path),
                "handoff_dir": str(handoff_dir),
                "operator_ready_flag": "0",
                "block_reason": "",
                "notes": "test candidate manifest",
            }
        ],
        columns=REVIEW_CANDIDATE_MANIFEST_COLUMNS,
    ).to_csv(manifest_path, index=False)
    return manifest_path


def _seed_supplier_titles(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "F" / "inbox" / "suppliers" / "supplier_a" / "canonical_current.csv",
        [
            {
                "supplier_id": "supplier_a",
                "supplier_sku": "SUP-CLEAR",
                "supplier_title": "Kensington Orbit Wireless Trackball",
                "brand": "Kensington",
                "unit_cost": "10",
            },
            {
                "supplier_id": "supplier_a",
                "supplier_sku": "SUP-BLOCK",
                "supplier_title": "Brand Owner Product",
                "brand": "Brand Owner",
                "unit_cost": "20",
            },
        ],
    )


def _write_codex_decisions_from_queue(handoff_dir: Path, action_by_candidate: dict[str, str]) -> None:
    queue = pd.read_csv(handoff_dir / "ai_review_queue.csv", dtype=str).fillna("")
    rows = []
    for record in queue.to_dict("records"):
        candidate_id = record["candidate_id"]
        action = action_by_candidate[candidate_id]
        rows.append(
            {
                "f032_decision_id": record["f032_decision_id"],
                "codex_ai_action": action,
                "codex_ai_decision_bucket": f"codex_{action}",
                "codex_ai_fail_category": "" if action == "allow_if_other_checks_pass" else "codex_review_block",
                "codex_ai_confidence": "high",
                "codex_ai_needs_user_guidance": "1" if action == "manual_review" else "0",
                "codex_ai_rescan_needed": "1" if action == "rescan_needed" else "0",
                "codex_ai_reason": f"Codex reviewed {candidate_id} and selected {action}.",
                "codex_ai_evidence": "unit_test_codex_decision",
                "codex_ai_reviewed_utc": OBSERVED,
                "codex_ai_reviewer": "unit_test",
            }
        )
    pd.DataFrame(rows).to_csv(handoff_dir / "codex_ai_review_decisions.csv", index=False)


def test_fpm155_writes_only_ai_gated_operator_manifest(tmp_path: Path) -> None:
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "supplier_a"
        / "run_1"
    )
    pass_path = handoff_dir / "raw_pass.csv"
    near_path = handoff_dir / "raw_near.csv"
    summary_path = handoff_dir / "raw_summary.csv"
    _write_csv(
        pass_path,
        [
            {
                "active_supplier_id": "supplier_a",
                "active_run_id": "run_1",
                "review_batch_id": "pass_batch",
                "candidate_id": "cand-clear",
                "supplier_sku": "SUP-CLEAR",
                "asin": "B000000001",
                "title": "Kensington Orbit Wireless Trackball",
                "brand": "Kensington",
                "amazon_product_description": "Each pack contains one wireless trackball.",
                "amazon_feature_bullets": "USB receiver included",
                "seller_history_recommended_action": "allow_if_other_checks_pass",
            },
            {
                "active_supplier_id": "supplier_a",
                "active_run_id": "run_1",
                "review_batch_id": "pass_batch",
                "candidate_id": "cand-block",
                "supplier_sku": "SUP-BLOCK",
                "asin": "B000000002",
                "title": "Brand Owner Product",
                "brand": "Brand Owner",
                "seller_history_code": "brand_owner_top_seller",
                "seller_history_recommended_action": "remove_from_clean_pass",
            },
        ],
    )
    _write_csv(near_path, [])
    _write_csv(summary_path, [{"observed_utc": OBSERVED, "metric": "pass_review_rows", "value": "2"}])
    _write_candidate_manifest(tmp_path, pass_path=pass_path, near_path=near_path, summary_path=summary_path)
    _seed_supplier_titles(tmp_path)

    pending = apply_review_intelligence_gate(
        root=tmp_path,
        supplier_id="supplier_a",
        run_id="run_1",
        observed_utc=OBSERVED,
        emit_json=False,
    )
    assert pending["status"] == "pending_ai_decision"
    assert pending["operator_ready_flag"] == "0"
    assert (handoff_dir / "ai_review_queue.csv").exists()
    assert (handoff_dir / "codex_ai_review_decision_template.csv").exists()
    assert not (handoff_dir / "manifest.csv").exists()
    queue_df = pd.read_csv(handoff_dir / "ai_review_queue.csv", dtype=str).fillna("")
    clear_queue_row = queue_df[queue_df["candidate_id"].eq("cand-clear")].iloc[0]
    assert clear_queue_row["amazon_product_description"] == "Each pack contains one wireless trackball."
    assert clear_queue_row["amazon_feature_bullets"] == "USB receiver included"
    pending_health = pd.read_csv(handoff_dir / "ai_review_intelligence_gate_health.csv", dtype=str).fillna("")
    page_text_health = pending_health[pending_health["check"].eq("ai_queue_amazon_page_text_columns_present")].iloc[0]
    assert page_text_health["status"] == "ok"

    _write_codex_decisions_from_queue(
        handoff_dir,
        {
            "cand-clear": "allow_if_other_checks_pass",
            "cand-block": "remove_from_clean_pass",
        },
    )

    summary = apply_review_intelligence_gate(
        root=tmp_path,
        supplier_id="supplier_a",
        run_id="run_1",
        observed_utc=OBSERVED,
        emit_json=False,
    )

    manifest = pd.read_csv(summary["manifest_path"], dtype=str).fillna("")
    live_manifest = pd.read_csv(
        tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "review_handoff_manifest.csv",
        dtype=str,
    ).fillna("")
    pass_df = pd.read_csv(manifest.iloc[0]["pass_review_path"], dtype=str).fillna("")
    removed_df = pd.read_csv(manifest.iloc[0]["ai_gate_removed_audit_path"], dtype=str).fillna("")

    assert summary["status"] == "gated"
    assert summary["ai_gate_quality_fail_checks"] == "0"
    assert list(manifest.columns) == REVIEW_HANDOFF_MANIFEST_COLUMNS
    assert list(live_manifest.columns) == REVIEW_HANDOFF_MANIFEST_COLUMNS
    assert manifest.iloc[0]["ai_gate_status"] == "passed"
    assert manifest.iloc[0]["operator_ready_flag"] == "1"
    assert manifest.iloc[0]["ai_gate_quality_fail_checks"] == "0"
    assert "quality_fail_checks=0" in manifest.iloc[0]["notes"]
    assert manifest.iloc[0]["codex_ai_decision_path"].endswith("codex_ai_review_decisions.csv")
    assert manifest.iloc[0]["pass_review_path"] != manifest.iloc[0]["raw_pass_review_path"]
    assert set(pass_df["candidate_id"]) == {"cand-clear"}
    assert pass_df.iloc[0]["f032_decision_id"].startswith("f032_")
    assert pass_df.iloc[0]["f032_action"] == "allow_if_other_checks_pass"
    assert pass_df.iloc[0]["supplier_title"] == "Kensington Orbit Wireless Trackball"
    assert set(removed_df["candidate_id"]) == {"cand-block"}


def test_fpm155_blocks_operator_manifest_when_fpm156_quality_fails(tmp_path: Path, monkeypatch) -> None:
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "supplier_a"
        / "run_1"
    )
    pass_path = handoff_dir / "raw_pass.csv"
    near_path = handoff_dir / "raw_near.csv"
    summary_path = handoff_dir / "raw_summary.csv"
    _write_csv(
        pass_path,
        [
            {
                "active_supplier_id": "supplier_a",
                "active_run_id": "run_1",
                "review_batch_id": "pass_batch",
                "candidate_id": "cand-clear",
                "supplier_sku": "SUP-CLEAR",
                "asin": "B000000001",
                "title": "Kensington Orbit Wireless Trackball",
                "brand": "Kensington",
                "amazon_product_description": "Each pack contains one wireless trackball.",
                "amazon_feature_bullets": "USB receiver included",
                "seller_history_recommended_action": "allow_if_other_checks_pass",
            }
        ],
    )
    _write_csv(near_path, [])
    _write_csv(summary_path, [{"observed_utc": OBSERVED, "metric": "pass_review_rows", "value": "1"}])
    _write_candidate_manifest(tmp_path, pass_path=pass_path, near_path=near_path, summary_path=summary_path)
    _seed_supplier_titles(tmp_path)

    pending = apply_review_intelligence_gate(
        root=tmp_path,
        supplier_id="supplier_a",
        run_id="run_1",
        observed_utc=OBSERVED,
        emit_json=False,
    )
    assert pending["status"] == "pending_ai_decision"
    _write_codex_decisions_from_queue(handoff_dir, {"cand-clear": "allow_if_other_checks_pass"})

    def _fake_failed_quality_report(**_: object) -> dict[str, object]:
        return {
            "status": "fail",
            "fail_checks": 1,
            "warn_checks": 0,
            "report_path": str(handoff_dir / "fake_ai_gate_quality_report.csv"),
            "summary_path": str(handoff_dir / "fake_ai_gate_quality_summary.md"),
            "notes": "quality_report_exception=unit_test_forced_failure",
        }

    monkeypatch.setattr(fpm155_module, "build_ai_gate_quality_report", _fake_failed_quality_report)

    summary = apply_review_intelligence_gate(
        root=tmp_path,
        supplier_id="supplier_a",
        run_id="run_1",
        observed_utc=OBSERVED,
        emit_json=False,
    )

    manifest = pd.read_csv(handoff_dir / "manifest.csv", dtype=str).fillna("")
    live_manifest = pd.read_csv(
        tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "review_handoff_manifest.csv",
        dtype=str,
    ).fillna("")
    operator_passes = load_feeder_review_source_df("passes", root=tmp_path)

    assert summary["status"] == "failed"
    assert summary["ai_gate_status"] == "failed_quality"
    assert summary["operator_ready_flag"] == "0"
    assert summary["block_reason"] == "ai_gate_quality_report_failed"
    assert summary["ai_gate_quality_fail_checks"] == "1"
    assert manifest.iloc[0]["ai_gate_status"] == "failed_quality"
    assert manifest.iloc[0]["operator_ready_flag"] == "0"
    assert manifest.iloc[0]["block_reason"] == "ai_gate_quality_report_failed"
    assert manifest.iloc[0]["ai_gate_quality_fail_checks"] == "1"
    assert manifest.iloc[0]["ai_gate_quality_report_path"].endswith("fake_ai_gate_quality_report.csv")
    assert live_manifest.iloc[0]["ai_gate_status"] == "failed_quality"
    assert live_manifest.iloc[0]["operator_ready_flag"] == "0"
    assert operator_passes.empty


def test_fpm155_legacy_manifest_does_not_block_candidate_queue(tmp_path: Path) -> None:
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "supplier_a"
        / "run_1"
    )
    pass_path = handoff_dir / "raw_pass.csv"
    near_path = handoff_dir / "raw_near.csv"
    summary_path = handoff_dir / "raw_summary.csv"
    _write_csv(
        pass_path,
        [
            {
                "active_supplier_id": "supplier_a",
                "active_run_id": "run_1",
                "review_batch_id": "pass_batch",
                "candidate_id": "cand-clear",
                "supplier_sku": "SUP-CLEAR",
                "asin": "B000000001",
                "title": "Kensington Orbit Wireless Trackball",
            }
        ],
    )
    _write_csv(near_path, [])
    _write_csv(summary_path, [{"observed_utc": OBSERVED, "metric": "pass_review_rows", "value": "1"}])
    _write_candidate_manifest(tmp_path, pass_path=pass_path, near_path=near_path, summary_path=summary_path)
    _seed_supplier_titles(tmp_path)
    pd.DataFrame(
        [
            {
                "built_at_utc": OBSERVED,
                "supplier_id": "supplier_a",
                "supplier_name": "Supplier A",
                "run_id": "run_1",
                "pass_review_rows": "1",
                "near_miss_review_rows": "0",
                "pass_review_path": str(pass_path),
                "near_miss_review_path": str(near_path),
                "operator_ready_flag": "",
                "notes": "legacy pre AI manifest",
            }
        ],
        columns=REVIEW_HANDOFF_MANIFEST_COLUMNS,
    ).to_csv(handoff_dir / "manifest.csv", index=False)

    pending = apply_review_intelligence_gate(
        root=tmp_path,
        supplier_id="supplier_a",
        run_id="run_1",
        observed_utc=OBSERVED,
        emit_json=False,
    )

    assert pending["status"] == "pending_ai_decision"
    assert pending["operator_ready_flag"] == "0"
    assert (handoff_dir / "ai_review_queue.csv").exists()
    legacy_manifest = pd.read_csv(handoff_dir / "manifest.csv", dtype=str).fillna("")
    assert legacy_manifest.iloc[0]["notes"] == "legacy pre AI manifest"


def test_fpm155_treats_missing_page_text_as_secondary_when_f032_passes(tmp_path: Path) -> None:
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "supplier_a"
        / "run_1"
    )
    pass_path = handoff_dir / "raw_pass.csv"
    near_path = handoff_dir / "raw_near.csv"
    summary_path = handoff_dir / "raw_summary.csv"
    _write_csv(
        pass_path,
        [
            {
                "active_supplier_id": "supplier_a",
                "active_run_id": "run_1",
                "review_batch_id": "pass_batch",
                "candidate_id": "cand-clear-missing-page",
                "supplier_sku": "SUP-CLEAR",
                "asin": "B000000001",
                "title": "Kensington Orbit Wireless Trackball",
                "brand": "Kensington",
                "seller_history_recommended_action": "allow_if_other_checks_pass",
            }
        ],
    )
    _write_csv(near_path, [])
    _write_csv(summary_path, [{"observed_utc": OBSERVED, "metric": "pass_review_rows", "value": "1"}])
    _write_candidate_manifest(tmp_path, pass_path=pass_path, near_path=near_path, summary_path=summary_path)
    _seed_supplier_titles(tmp_path)

    pending = apply_review_intelligence_gate(
        root=tmp_path,
        supplier_id="supplier_a",
        run_id="run_1",
        observed_utc=OBSERVED,
        emit_json=False,
    )
    assert pending["status"] == "pending_ai_decision"

    queue = pd.read_csv(handoff_dir / "ai_review_queue.csv", dtype=str).fillna("")
    queue_row = queue.iloc[0].to_dict()
    pd.DataFrame(
        [
            {
                "f032_decision_id": queue_row["f032_decision_id"],
                "codex_ai_action": "rescan_needed",
                "codex_ai_decision_bucket": "needs_rescan",
                "codex_ai_fail_category": "missing_page_evidence",
                "codex_ai_confidence": "low",
                "codex_ai_needs_user_guidance": "0",
                "codex_ai_rescan_needed": "1",
                "codex_ai_reason": "Core page evidence is missing, so route to rescan.",
                "codex_ai_evidence": "amazon_product_description_present=false | f032_rule_action=allow_if_other_checks_pass",
                "codex_ai_reviewed_utc": OBSERVED,
                "codex_ai_reviewer": "unit_test",
            }
        ]
    ).to_csv(handoff_dir / "codex_ai_review_decisions.csv", index=False)

    summary = apply_review_intelligence_gate(
        root=tmp_path,
        supplier_id="supplier_a",
        run_id="run_1",
        observed_utc=OBSERVED,
        emit_json=False,
    )

    manifest = pd.read_csv(summary["manifest_path"], dtype=str).fillna("")
    pass_df = pd.read_csv(manifest.iloc[0]["pass_review_path"], dtype=str).fillna("")
    rescan_df = pd.read_csv(manifest.iloc[0]["ai_gate_rescan_queue_path"], dtype=str).fillna("")
    assert summary["status"] == "gated"
    assert set(pass_df["candidate_id"]) == {"cand-clear-missing-page"}
    assert rescan_df.empty
    assert pass_df.iloc[0]["f032_action"] == "allow_if_other_checks_pass"
    assert pass_df.iloc[0]["supplier_title"] == "Kensington Orbit Wireless Trackball"
    assert "secondary evidence" in pass_df.iloc[0]["f032_reason"]


def test_fpm155_archives_stale_codex_decisions_not_in_current_queue(tmp_path: Path) -> None:
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "supplier_a"
        / "run_1"
    )
    pass_path = handoff_dir / "raw_pass.csv"
    near_path = handoff_dir / "raw_near.csv"
    summary_path = handoff_dir / "raw_summary.csv"
    _write_csv(
        pass_path,
        [
            {
                "active_supplier_id": "supplier_a",
                "active_run_id": "run_1",
                "review_batch_id": "pass_batch",
                "candidate_id": "cand-current",
                "supplier_sku": "SUP-CLEAR",
                "asin": "B000000001",
                "title": "Kensington Orbit Wireless Trackball",
                "brand": "Kensington",
                "seller_history_recommended_action": "allow_if_other_checks_pass",
            }
        ],
    )
    _write_csv(near_path, [])
    _write_csv(summary_path, [{"observed_utc": OBSERVED, "metric": "pass_review_rows", "value": "1"}])
    _write_candidate_manifest(tmp_path, pass_path=pass_path, near_path=near_path, summary_path=summary_path)
    _seed_supplier_titles(tmp_path)

    pending = apply_review_intelligence_gate(
        root=tmp_path,
        supplier_id="supplier_a",
        run_id="run_1",
        observed_utc=OBSERVED,
        emit_json=False,
    )
    assert pending["status"] == "pending_ai_decision"
    queue = pd.read_csv(handoff_dir / "ai_review_queue.csv", dtype=str).fillna("")
    current_decision_id = queue.iloc[0]["f032_decision_id"]
    pd.DataFrame(
        [
            {
                "f032_decision_id": current_decision_id,
                "codex_ai_action": "allow_if_other_checks_pass",
                "codex_ai_decision_bucket": "ai_review_clear",
                "codex_ai_fail_category": "",
                "codex_ai_confidence": "high",
                "codex_ai_needs_user_guidance": "0",
                "codex_ai_rescan_needed": "0",
                "codex_ai_reason": "Current queue row is a clear match.",
                "codex_ai_evidence": "active_queue_row",
                "codex_ai_reviewed_utc": OBSERVED,
                "codex_ai_reviewer": "unit_test",
            },
            {
                "f032_decision_id": "f032_old_not_current",
                "codex_ai_action": "rescan_needed",
                "codex_ai_decision_bucket": "needs_rescan",
                "codex_ai_fail_category": "missing_page_evidence",
                "codex_ai_confidence": "low",
                "codex_ai_needs_user_guidance": "0",
                "codex_ai_rescan_needed": "1",
                "codex_ai_reason": "Old decision from a previous queue.",
                "codex_ai_evidence": "stale_queue_row",
                "codex_ai_reviewed_utc": OBSERVED,
                "codex_ai_reviewer": "unit_test",
            },
        ]
    ).to_csv(handoff_dir / "codex_ai_review_decisions.csv", index=False)

    summary = apply_review_intelligence_gate(
        root=tmp_path,
        supplier_id="supplier_a",
        run_id="run_1",
        observed_utc=OBSERVED,
        emit_json=False,
    )

    active_decisions = pd.read_csv(handoff_dir / "codex_ai_review_decisions.csv", dtype=str).fillna("")
    archive = pd.read_csv(handoff_dir / "codex_ai_review_decisions_stale_archive.csv", dtype=str).fillna("")
    health = pd.read_csv(handoff_dir / "ai_review_intelligence_gate_health.csv", dtype=str).fillna("")
    archive_health = health[health["check"].eq("stale_codex_ai_decision_rows_archived")].iloc[0]
    assert summary["status"] == "gated"
    assert summary["stale_codex_decision_rows_archived"] == "1"
    assert active_decisions["f032_decision_id"].tolist() == [current_decision_id]
    assert archive.iloc[0]["f032_decision_id"] == "f032_old_not_current"
    assert archive.iloc[0]["archive_reason"] == "decision_not_in_current_ai_queue"
    assert archive_health["value"] == "1"


def test_fpm155_blocks_clean_pass_when_current_scanner_fail_evidence_exists(tmp_path: Path) -> None:
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "supplier_a"
        / "run_1"
    )
    pass_path = handoff_dir / "raw_pass.csv"
    near_path = handoff_dir / "raw_near.csv"
    summary_path = handoff_dir / "raw_summary.csv"
    _write_csv(
        pass_path,
        [
            {
                "active_supplier_id": "supplier_a",
                "active_run_id": "run_1",
                "review_batch_id": "pass_batch",
                "candidate_id": "cand-clear-current-fail",
                "supplier_sku": "SUP-CLEAR",
                "asin": "B000000001",
                "title": "Kensington Orbit Wireless Trackball",
                "brand": "Kensington",
                "seller_history_recommended_action": "allow_if_other_checks_pass",
            }
        ],
    )
    _write_csv(near_path, [])
    _write_csv(summary_path, [{"observed_utc": OBSERVED, "metric": "pass_review_rows", "value": "1"}])
    _write_candidate_manifest(tmp_path, pass_path=pass_path, near_path=near_path, summary_path=summary_path)
    _seed_supplier_titles(tmp_path)

    pending = apply_review_intelligence_gate(
        root=tmp_path,
        supplier_id="supplier_a",
        run_id="run_1",
        observed_utc=OBSERVED,
        emit_json=False,
    )
    assert pending["status"] == "pending_ai_decision"
    queue = pd.read_csv(handoff_dir / "ai_review_queue.csv", dtype=str).fillna("")
    queue_row = queue.iloc[0].to_dict()
    pd.DataFrame(
        [
            {
                "f032_decision_id": queue_row["f032_decision_id"],
                "codex_ai_action": "allow_if_other_checks_pass",
                "codex_ai_decision_bucket": "ai_review_clear",
                "codex_ai_fail_category": "",
                "codex_ai_confidence": "high",
                "codex_ai_needs_user_guidance": "0",
                "codex_ai_rescan_needed": "0",
                "codex_ai_reason": "AI title check allowed the product.",
                "codex_ai_evidence": "titles_match",
                "codex_ai_reviewed_utc": OBSERVED,
                "codex_ai_reviewer": "unit_test",
            }
        ]
    ).to_csv(handoff_dir / "codex_ai_review_decisions.csv", index=False)
    audit_path = tmp_path / "out" / "systems" / "F" / "page_evidence_backfill" / "current_scanner_fail_evidence.csv"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "observed_utc": OBSERVED,
                "batch_id": "batch-current-fail",
                "backfill_id": "f036_row_1",
                "backfill_status": "skipped_current_scanner_fail",
                "supplier_id": "supplier_a",
                "active_run_id": "run_1",
                "review_batch_id": "pass_batch",
                "candidate_id": "cand-clear-current-fail",
                "supplier_sku": "SUP-CLEAR",
                "asin": "B000000001",
                "resolved_asin": "B000000001",
                "barcode": "5012345678901",
                "supplier_title": "Kensington Orbit Wireless Trackball",
                "amazon_title": "Kensington Orbit Wireless Trackball",
                "scanner_fail_reason": "current_scanner_fail:LOWROI",
                "scrape_error": "LOWROI",
                "scrape_attempted": "True",
                "scrape_success": "False",
                "page_evidence_captured_flag": "0",
                "proof_root": "proof/current-fail",
                "state_path": "state.csv",
                "evidence_source_path": "evidence.csv",
            }
        ],
        columns=CURRENT_SCANNER_FAIL_EVIDENCE_COLUMNS,
    ).to_csv(audit_path, index=False)

    summary = apply_review_intelligence_gate(
        root=tmp_path,
        supplier_id="supplier_a",
        run_id="run_1",
        observed_utc=OBSERVED,
        emit_json=False,
    )

    manifest = pd.read_csv(summary["manifest_path"], dtype=str).fillna("")
    pass_df = pd.read_csv(manifest.iloc[0]["pass_review_path"], dtype=str).fillna("")
    removed_df = pd.read_csv(manifest.iloc[0]["ai_gate_removed_audit_path"], dtype=str).fillna("")
    decisions = pd.read_csv(handoff_dir / "codex_ai_review_decisions.csv", dtype=str).fillna("")
    assert summary["status"] == "gated"
    assert summary["current_scanner_fail_guard_rows"] == "1"
    assert pass_df.empty
    assert set(removed_df["candidate_id"]) == {"cand-clear-current-fail"}
    assert removed_df.iloc[0]["f032_action"] == "remove_from_clean_pass"
    assert decisions.iloc[0]["codex_ai_reviewer"] == "fpm155_current_scanner_fail_guard"
    assert "LOWROI" in decisions.iloc[0]["codex_ai_reason"]


def test_fpm155_does_not_publish_manifest_when_ai_gate_health_fails(tmp_path: Path) -> None:
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "supplier_a"
        / "run_1"
    )
    pass_path = handoff_dir / "raw_pass.csv"
    near_path = handoff_dir / "raw_near.csv"
    summary_path = handoff_dir / "raw_summary.csv"
    _write_csv(
        pass_path,
        [
            {
                "active_supplier_id": "supplier_a",
                "active_run_id": "run_1",
                "review_batch_id": "pass_batch",
                "candidate_id": "cand-missing-title",
                "supplier_sku": "SUP-CLEAR",
                "asin": "B000000001",
                "title": "",
            }
        ],
    )
    _write_csv(near_path, [])
    _write_csv(summary_path, [{"observed_utc": OBSERVED, "metric": "pass_review_rows", "value": "1"}])
    _write_candidate_manifest(tmp_path, pass_path=pass_path, near_path=near_path, summary_path=summary_path)
    _seed_supplier_titles(tmp_path)

    pending = apply_review_intelligence_gate(
        root=tmp_path,
        supplier_id="supplier_a",
        run_id="run_1",
        observed_utc=OBSERVED,
        emit_json=False,
    )
    assert pending["status"] == "pending_ai_decision"
    _write_codex_decisions_from_queue(handoff_dir, {"cand-missing-title": "manual_review"})

    summary = apply_review_intelligence_gate(
        root=tmp_path,
        supplier_id="supplier_a",
        run_id="run_1",
        observed_utc=OBSERVED,
        emit_json=False,
    )

    assert summary["status"] == "failed"
    assert summary["ai_gate_status"] == "failed"
    assert not (handoff_dir / "manifest.csv").exists()
    health = pd.read_csv(handoff_dir / "ai_review_intelligence_gate_health.csv", dtype=str).fillna("")
    assert "fail" in set(health["status"])
