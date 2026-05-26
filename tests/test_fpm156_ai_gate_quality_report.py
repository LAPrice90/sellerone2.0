from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.flows.F.price_list_manager.FPM156_build_ai_gate_quality_report import build_ai_gate_quality_report
from scripts.flows.O.O400_operator_ui import build_ai_product_check_gate_df


def _seed_handoff(
    root: Path,
    *,
    supplier_id: str,
    run_id: str,
    decision_id: str,
    reviewed_utc: str,
) -> None:
    handoff_dir = (
        root
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / supplier_id
        / run_id
    )
    handoff_dir.mkdir(parents=True, exist_ok=True)
    queue_path = handoff_dir / "ai_review_queue.csv"
    decision_path = handoff_dir / "codex_ai_review_decisions.csv"
    pd.DataFrame(
        [
            {"supplier_id": supplier_id, "supplier_name": "Sample Supplier", "run_id": run_id},
        ]
    ).to_csv(handoff_dir / "candidate_manifest.csv", index=False)
    pd.DataFrame(
        [
            {
                "supplier_id": supplier_id,
                "supplier_name": "Sample Supplier",
                "run_id": run_id,
                "ai_gate_status": "passed",
                "operator_ready_flag": "1",
                "ai_review_queue_path": str(queue_path),
                "codex_ai_decision_path": str(decision_path),
                "pass_review_path": str(root / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"),
                "near_miss_review_path": str(
                    root / "out" / "analysis_reports" / "f_live_price_file_near_miss_review_latest.csv"
                ),
            }
        ]
    ).to_csv(handoff_dir / "manifest.csv", index=False)
    pd.DataFrame(
        [
            {
                "f032_decision_id": decision_id,
                "supplier_sku": "DUP-1",
                "asin": "B000DUP001",
                "supplier_title": "Sample Product 50 Pack",
                "amazon_title": "Sample Product 50 Pack",
                "amazon_product_description": "Each pack contains 50 units.",
                "profit_on_cost_pct": "25",
            }
        ]
    ).to_csv(queue_path, index=False)
    pd.DataFrame(
        [
            {
                "f032_decision_id": decision_id,
                "codex_ai_action": "allow_if_other_checks_pass",
                "codex_ai_decision_bucket": "ai_review_clear",
                "codex_ai_confidence": "high",
                "codex_ai_needs_user_guidance": "0",
                "codex_ai_rescan_needed": "0",
                "codex_ai_reason": "Supplier and Amazon titles describe the same 50 pack.",
                "codex_ai_evidence": "supplier_title=Sample Product 50 Pack | amazon_title=Sample Product 50 Pack",
                "codex_ai_reviewed_utc": reviewed_utc,
                "codex_ai_reviewer": "codex_manager",
            }
        ]
    ).to_csv(decision_path, index=False)


def test_ai_gate_quality_report_keeps_history_but_current_view_dedupes(tmp_path: Path) -> None:
    _seed_handoff(
        tmp_path,
        supplier_id="sample_supplier",
        run_id="run_20260520",
        decision_id="old_decision",
        reviewed_utc="2026-05-20T06:00:00Z",
    )
    _seed_handoff(
        tmp_path,
        supplier_id="sample_supplier",
        run_id="run_20260521",
        decision_id="new_decision",
        reviewed_utc="2026-05-21T06:00:00Z",
    )

    current_df = build_ai_product_check_gate_df(root=tmp_path)
    history_df = build_ai_product_check_gate_df(root=tmp_path, include_history=True)
    summary = build_ai_gate_quality_report(root=tmp_path, observed_utc="2026-05-21T08:00:00Z")
    report = pd.read_csv(summary["report_path"], dtype=str).fillna("")

    assert len(current_df.index) == 1
    assert len(history_df.index) == 2
    assert current_df.iloc[0]["f032_decision_id"] == "new_decision"
    assert summary["history_duplicate_product_groups"] == 1
    assert summary["current_rows"] == 1
    assert summary["history_rows"] == 2
    assert summary["fail_checks"] == 0
    assert summary["warn_checks"] == 0
    assert report[report["check"].eq("history_duplicate_product_groups")].iloc[0]["status"] == "ok"
    assert report[report["check"].eq("current_duplicate_product_groups")].iloc[0]["status"] == "ok"


def test_ai_gate_quality_report_proves_queue_decisions(tmp_path: Path) -> None:
    _seed_handoff(
        tmp_path,
        supplier_id="sample_supplier",
        run_id="run_20260521",
        decision_id="decided_row",
        reviewed_utc="2026-05-21T06:00:00Z",
    )
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "sample_supplier"
        / "run_20260521"
    )
    queue_path = handoff_dir / "ai_review_queue.csv"
    queue_df = pd.read_csv(queue_path, dtype=str).fillna("")
    queue_df = pd.concat(
        [
            queue_df,
            pd.DataFrame(
                [
                    {
                        "f032_decision_id": "missing_decision",
                        "supplier_sku": "MISS-1",
                        "asin": "B000MISS01",
                        "supplier_title": "Missing Decision Product",
                        "amazon_title": "Missing Decision Product",
                        "amazon_product_description": "Matching product description.",
                        "profit_on_cost_pct": "20",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    queue_df.to_csv(queue_path, index=False)

    summary = build_ai_gate_quality_report(root=tmp_path, observed_utc="2026-05-21T08:00:00Z")
    report = pd.read_csv(summary["report_path"], dtype=str).fillna("")
    by_check = {row["check"]: row for row in report.to_dict("records")}

    assert summary["status"] == "fail"
    assert summary["active_ai_queue_rows"] == 2
    assert summary["active_ai_decision_rows"] == 1
    assert summary["active_queue_missing_decision_rows"] == 1
    assert by_check["active_queue_missing_decision_rows"]["status"] == "fail"
    assert "MISS-1" in by_check["active_queue_missing_decision_rows"]["notes"]


def test_ai_gate_quality_report_proves_final_review_ai_notes(tmp_path: Path) -> None:
    _seed_handoff(
        tmp_path,
        supplier_id="sample_supplier",
        run_id="run_20260521",
        decision_id="decided_row",
        reviewed_utc="2026-05-21T06:00:00Z",
    )

    review_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "candidate_id": "visible_without_ai_note",
                "f032_decision_id": "decided_row",
                "f032_action": "allow_if_other_checks_pass",
                "codex_ai_action": "allow_if_other_checks_pass",
                "supplier_sku": "MISS-1",
                "asin": "B000MISS01",
                "title": "Missing Decision Product",
                "watch_data_summary": "decision_confidence=medium",
            }
        ]
    ).to_csv(review_path, index=False)

    summary = build_ai_gate_quality_report(root=tmp_path, observed_utc="2026-05-21T08:00:00Z")
    report = pd.read_csv(summary["report_path"], dtype=str).fillna("")
    by_check = {row["check"]: row for row in report.to_dict("records")}

    assert summary["status"] == "fail"
    assert summary["final_review_rows"] == 1
    assert summary["final_review_missing_ai_compare_note_rows"] == 1
    assert by_check["final_review_missing_ai_compare_note_rows"]["status"] == "fail"
    assert "MISS-1" in by_check["final_review_missing_ai_compare_note_rows"]["notes"]


def test_ai_gate_quality_report_scopes_page_text_and_roi_warnings_to_visible_risk(tmp_path: Path) -> None:
    _seed_handoff(
        tmp_path,
        supplier_id="sample_supplier",
        run_id="run_20260521",
        decision_id="decided_row",
        reviewed_utc="2026-05-21T06:00:00Z",
    )
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "sample_supplier"
        / "run_20260521"
    )
    queue_path = handoff_dir / "ai_review_queue.csv"
    decision_path = handoff_dir / "codex_ai_review_decisions.csv"
    queue_df = pd.read_csv(queue_path, dtype=str).fillna("")
    decision_df = pd.read_csv(decision_path, dtype=str).fillna("")
    queue_df = pd.concat(
        [
            queue_df,
            pd.DataFrame(
                [
                    {
                        "f032_decision_id": "visible_profit_fallback",
                        "supplier_sku": "PROFIT-1",
                        "asin": "B000PROFIT",
                        "supplier_title": "Profit fallback product",
                        "amazon_title": "Profit fallback product",
                        "amazon_product_description": "The product page confirms the same item.",
                        "profit_per_unit_gbp": "2.50",
                        "expected_profit_gbp": "25",
                    },
                    {
                        "f032_decision_id": "hidden_no_page",
                        "supplier_sku": "HIDDEN-1",
                        "asin": "B000HIDDEN",
                        "supplier_title": "Hidden rejected product",
                        "amazon_title": "Hidden rejected product",
                    },
                    {
                        "f032_decision_id": "visible_title_only_clear",
                        "supplier_sku": "TITLE-1",
                        "asin": "B000TITLE",
                        "supplier_title": "Clear title match product",
                        "amazon_title": "Clear title match product",
                        "profit_on_cost_pct": "50",
                    },
                ]
            ),
        ],
        ignore_index=True,
    )
    decision_df = pd.concat(
        [
            decision_df,
            pd.DataFrame(
                [
                    {
                        "f032_decision_id": "visible_profit_fallback",
                        "codex_ai_action": "allow_if_other_checks_pass",
                        "codex_ai_decision_bucket": "ai_review_clear",
                        "codex_ai_confidence": "high",
                        "codex_ai_reason": "Titles describe the same product.",
                        "codex_ai_evidence": "supplier_title=Profit fallback product | amazon_title=Profit fallback product",
                        "codex_ai_reviewed_utc": "2026-05-21T08:00:00Z",
                    },
                    {
                        "f032_decision_id": "hidden_no_page",
                        "codex_ai_action": "remove_from_clean_pass",
                        "codex_ai_decision_bucket": "clear_breach",
                        "codex_ai_confidence": "high",
                        "codex_ai_reason": "Rejected rows stay hidden from the final list.",
                        "codex_ai_evidence": "supplier_title=Hidden rejected product | amazon_title=Hidden rejected product",
                        "codex_ai_reviewed_utc": "2026-05-21T08:01:00Z",
                    },
                    {
                        "f032_decision_id": "visible_title_only_clear",
                        "codex_ai_action": "allow_if_other_checks_pass",
                        "codex_ai_decision_bucket": "same_product_confirmed_by_combined_amazon_text",
                        "codex_ai_confidence": "high",
                        "codex_ai_reason": "Titles carry enough evidence that this is the same product.",
                        "codex_ai_evidence": "supplier_title=Clear title match product | amazon_title=Clear title match product",
                        "codex_ai_reviewed_utc": "2026-05-21T08:02:00Z",
                        "codex_ai_reviewer": "fpm155_secondary_evidence_guard",
                    },
                ]
            ),
        ],
        ignore_index=True,
    )
    queue_df.to_csv(queue_path, index=False)
    decision_df.to_csv(decision_path, index=False)

    summary = build_ai_gate_quality_report(root=tmp_path, observed_utc="2026-05-21T08:00:00Z")
    report = pd.read_csv(summary["report_path"], dtype=str).fillna("")
    by_check = {row["check"]: row for row in report.to_dict("records")}

    assert summary["status"] == "ok"
    assert summary["current_missing_page_text_rows"] == 0
    assert summary["current_hidden_missing_page_text_rows"] == 1
    assert summary["current_missing_roi_rows"] == 0
    assert summary["current_visible_profit_fallback_rows"] == 1
    assert summary["current_visible_secondary_guard_rows"] == 0
    assert by_check["current_missing_page_text_rows"]["status"] == "ok"
    assert by_check["current_hidden_missing_page_text_rows"]["status"] == "ok"
    assert by_check["current_missing_roi_rows"]["status"] == "ok"
    assert by_check["current_visible_profit_fallback_rows"]["status"] == "ok"
    assert by_check["current_visible_secondary_guard_rows"]["status"] == "ok"
