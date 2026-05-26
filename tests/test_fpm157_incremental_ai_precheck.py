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

from scripts.flows.F.price_list_manager.FPM155_apply_review_intelligence_gate import (
    CODEX_AI_DECISION_COLUMNS,
    apply_review_intelligence_gate,
)
from scripts.flows.F.price_list_manager.FPM157_build_incremental_ai_precheck import build_incremental_ai_precheck
from scripts.flows.F.price_list_manager.FPM158_ai_precheck_common import ai_precheck_dir
from scripts.flows.F.price_list_manager._schemas import REVIEW_CANDIDATE_MANIFEST_COLUMNS


OBSERVED = "2026-05-22T08:30:00Z"


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    if columns is not None:
        for column in columns:
            if column not in df.columns:
                df[column] = ""
        df = df[columns]
    df.to_csv(path, index=False)


def _seed_precheck_sources(
    root: Path,
    *,
    supplier_id: str = "td_synnex",
    run_id: str = "td_run_1",
    amazon_title: str = "Kensington Orbit Wireless Trackball",
) -> None:
    live = root / "out" / "systems" / "F" / "live"
    inbox = root / "out" / "systems" / "F" / "inbox"
    analysis = root / "out" / "analysis_reports"
    candidate_id = "td-cand-1"
    supplier_sku = "TD-SKU-1"
    asin = "B000000001"
    _write_csv(
        live / "f_screening_row_state_live.csv",
        [
            {
                "supplier_id": supplier_id,
                "run_id": run_id,
                "candidate_id": candidate_id,
                "supplier_sku": supplier_sku,
                "asin": asin,
                "row_status": "pass",
                "status_reason": "PASS",
                "fail_code": "",
                "last_stage": "webscrape",
                "source_seen_at_utc": "2026-05-22T08:00:00Z",
            }
        ],
    )
    _write_csv(
        live / "feeder_legacy_first_checks_live.csv",
        [
            {
                "candidate_id": candidate_id,
                "supplier_sku": supplier_sku,
                "asin": asin,
                "title": amazon_title,
                "brand": "Kensington",
                "main_rank": "1200",
                "point_score": "4.00",
                "pf": "PASS",
                "status_reason": "PASS",
            }
        ],
    )
    _write_csv(
        live / "feeder_legacy_scrape_evidence_live.csv",
        [
            {
                "observed_utc": OBSERVED,
                "supplier_id": supplier_id,
                "run_id": run_id,
                "candidate_id": candidate_id,
                "supplier_sku": supplier_sku,
                "asin": asin,
                "title": amazon_title,
                "status_reason": "PASS",
                "estimated_monthly_profit": "80",
                "profit_per_unit_30d": "8",
                "avg_30_day_price": "18",
                "break_even": "10",
                "bbp_sales_replay_demand_basis_units": "10",
                "opportunity_recommendation": "PASS",
                "history_recommendation": "PASS",
                "historical_uk_reviews": "20",
                "variant_reviews": "100",
                "product_description": "Amazon description for the matching product.",
                "product_feature_bullets": "Wireless trackball with USB receiver.",
            }
        ],
    )
    _write_csv(
        live / "feeder_backtest_summary_live.csv",
        [
            {
                "seller_sku": supplier_sku,
                "asin": asin,
                "decision_state": "pass",
                "decision_confidence": "high",
                "stability_state": "stable",
                "expected_units_next_30d": "10",
                "expected_profit_next_30d_gbp": "80",
                "recommendation": "Managed fit",
                "decision_reason_codes": "meets_profit_floor",
            }
        ],
    )
    _write_csv(analysis / "f_profit_formula_conflict_audit_latest.csv", [])
    _write_csv(analysis / "f_title_match_agent_decisions_latest.csv", [])
    _write_csv(inbox / "feeder_review_events.csv", [])
    _write_csv(
        inbox / "suppliers" / supplier_id / "canonical_current.csv",
        [
            {
                "supplier_id": supplier_id,
                "supplier_sku": supplier_sku,
                "supplier_title": "Kensington Orbit Wireless Trackball",
                "brand": "Kensington",
                "unit_cost": "10",
                "currency": "GBP",
            }
        ],
    )


def _write_precheck_decision(precheck_dir: Path, *, action: str = "allow_if_other_checks_pass") -> str:
    queue = pd.read_csv(precheck_dir / "ai_review_queue.csv", dtype=str).fillna("")
    decision_id = queue.iloc[0]["f032_decision_id"]
    _write_csv(
        precheck_dir / "codex_ai_review_decisions.csv",
        [
            {
                "f032_decision_id": decision_id,
                "codex_ai_action": action,
                "codex_ai_decision_bucket": f"codex_{action}",
                "codex_ai_fail_category": "" if action == "allow_if_other_checks_pass" else "codex_review",
                "codex_ai_confidence": "high",
                "codex_ai_needs_user_guidance": "0",
                "codex_ai_rescan_needed": "0",
                "codex_ai_reason": "Prechecked row is a clear same-product match.",
                "codex_ai_evidence": "precheck_unit_test",
                "codex_ai_reviewed_utc": OBSERVED,
                "codex_ai_reviewer": "unit_test",
            }
        ],
        CODEX_AI_DECISION_COLUMNS,
    )
    return decision_id


def _write_final_candidate_manifest(root: Path, precheck_dir: Path) -> Path:
    handoff_dir = (
        root
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "td_synnex"
        / "td_run_1"
    )
    handoff_dir.mkdir(parents=True, exist_ok=True)
    raw_pass = precheck_dir / "precheck_pass_review.csv"
    raw_near = precheck_dir / "precheck_near_miss_review.csv"
    raw_summary = precheck_dir / "raw_review_pack" / "f_live_price_file_review_summary_latest.csv"
    manifest = handoff_dir / "candidate_manifest.csv"
    _write_csv(
        manifest,
        [
            {
                "built_at_utc": OBSERVED,
                "supplier_id": "td_synnex",
                "supplier_name": "TD Synnex",
                "run_id": "td_run_1",
                "review_snapshot_id": "20260522T083000Z",
                "source_file_path": "td.csv",
                "source_seen_at_utc": "2026-05-22T08:00:00Z",
                "completed_at_utc": "2026-05-22T09:00:00Z",
                "raw_pass_review_rows": "1",
                "raw_near_miss_review_rows": "0",
                "hard_reject_rows": "0",
                "raw_pass_review_path": str(raw_pass),
                "raw_near_miss_review_path": str(raw_near),
                "raw_summary_path": str(raw_summary),
                "handoff_dir": str(handoff_dir),
                "operator_ready_flag": "0",
                "block_reason": "",
                "notes": "final handoff built after completion",
            }
        ],
        REVIEW_CANDIDATE_MANIFEST_COLUMNS,
    )
    return manifest


def test_fpm157_builds_hidden_precheck_queue_without_handoff(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FPM_INCREMENTAL_AI_PRECHECK_SUPPLIERS", "td_synnex")
    _seed_precheck_sources(tmp_path)

    summary = build_incremental_ai_precheck(
        root=tmp_path,
        supplier_id="td_synnex",
        run_id="td_run_1",
        observed_utc=OBSERVED,
        emit_json=False,
    )

    precheck_dir = ai_precheck_dir(tmp_path, supplier_id="td_synnex", run_id="td_run_1")
    queue = pd.read_csv(precheck_dir / "ai_review_queue.csv", dtype=str).fillna("")
    registry = pd.read_csv(precheck_dir / "ai_precheck_registry.csv", dtype=str).fillna("")
    assert summary["status"] == "pending_ai_decision"
    assert summary["eligible_pass_rows"] == "1"
    assert len(queue.index) == 1
    assert len(registry.index) == 1
    assert registry.iloc[0]["hidden_until_completed_flag"] == "1"
    assert not (tmp_path / "out" / "systems" / "F" / "price_list_manager" / "review_handoffs").exists()

    second = build_incremental_ai_precheck(
        root=tmp_path,
        supplier_id="td_synnex",
        run_id="td_run_1",
        observed_utc="2026-05-22T08:45:00Z",
        emit_json=False,
    )
    queue_2 = pd.read_csv(precheck_dir / "ai_review_queue.csv", dtype=str).fillna("")
    assert second["ai_queue_rows"] == "1"
    assert queue_2["f032_decision_id"].tolist() == queue["f032_decision_id"].tolist()


def test_fpm157_archives_precheck_decision_when_evidence_hash_changes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FPM_INCREMENTAL_AI_PRECHECK_SUPPLIERS", "td_synnex")
    _seed_precheck_sources(tmp_path)
    build_incremental_ai_precheck(root=tmp_path, supplier_id="td_synnex", run_id="td_run_1", observed_utc=OBSERVED, emit_json=False)
    precheck_dir = ai_precheck_dir(tmp_path, supplier_id="td_synnex", run_id="td_run_1")
    original_decision_id = _write_precheck_decision(precheck_dir)

    _seed_precheck_sources(tmp_path, amazon_title="Kensington Orbit Wireless Trackball Updated")
    summary = build_incremental_ai_precheck(
        root=tmp_path,
        supplier_id="td_synnex",
        run_id="td_run_1",
        observed_utc="2026-05-22T08:50:00Z",
        emit_json=False,
    )

    decisions = pd.read_csv(precheck_dir / "codex_ai_review_decisions.csv", dtype=str).fillna("")
    archive = pd.read_csv(precheck_dir / "codex_ai_review_decisions_stale_archive.csv", dtype=str).fillna("")
    assert summary["stale_decision_rows"] == "1"
    assert decisions.empty
    assert archive.iloc[0]["f032_decision_id"] == original_decision_id
    assert archive.iloc[0]["archive_reason"] == "precheck_evidence_hash_changed"


def test_fpm155_reuses_matching_precheck_decision_in_final_handoff(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FPM_INCREMENTAL_AI_PRECHECK_SUPPLIERS", "td_synnex")
    _seed_precheck_sources(tmp_path)
    build_incremental_ai_precheck(root=tmp_path, supplier_id="td_synnex", run_id="td_run_1", observed_utc=OBSERVED, emit_json=False)
    precheck_dir = ai_precheck_dir(tmp_path, supplier_id="td_synnex", run_id="td_run_1")
    _write_precheck_decision(precheck_dir)
    _write_final_candidate_manifest(tmp_path, precheck_dir)

    summary = apply_review_intelligence_gate(
        root=tmp_path,
        supplier_id="td_synnex",
        run_id="td_run_1",
        observed_utc="2026-05-22T09:05:00Z",
        emit_json=False,
    )

    handoff_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "review_handoffs" / "td_synnex" / "td_run_1"
    decisions = pd.read_csv(handoff_dir / "codex_ai_review_decisions.csv", dtype=str).fillna("")
    manifest = pd.read_csv(summary["manifest_path"], dtype=str).fillna("")
    assert summary["status"] == "gated"
    assert summary["precheck_reused_in_final_rows"] == "1"
    assert decisions.iloc[0]["codex_ai_reviewer"] == "unit_test"
    assert manifest.iloc[0]["operator_ready_flag"] == "1"
    assert "precheck_reused_in_final_rows=1" in manifest.iloc[0]["notes"]


def test_fpm155_does_not_reuse_invalid_precheck_action(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FPM_INCREMENTAL_AI_PRECHECK_SUPPLIERS", "td_synnex")
    _seed_precheck_sources(tmp_path)
    build_incremental_ai_precheck(root=tmp_path, supplier_id="td_synnex", run_id="td_run_1", observed_utc=OBSERVED, emit_json=False)
    precheck_dir = ai_precheck_dir(tmp_path, supplier_id="td_synnex", run_id="td_run_1")
    _write_precheck_decision(precheck_dir, action="not_a_valid_action")
    _write_final_candidate_manifest(tmp_path, precheck_dir)

    summary = apply_review_intelligence_gate(
        root=tmp_path,
        supplier_id="td_synnex",
        run_id="td_run_1",
        observed_utc="2026-05-22T09:05:00Z",
        emit_json=False,
    )

    assert summary["status"] == "pending_ai_decision"
    assert summary["precheck_reused_in_final_rows"] == "0"
    assert summary["precheck_stale_decision_rows"] == "1"
