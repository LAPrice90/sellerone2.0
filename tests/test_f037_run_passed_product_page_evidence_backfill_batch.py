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
from scripts.one_off.F036_build_passed_product_page_evidence_backfill_queue import BACKFILL_QUEUE_COLUMNS
from scripts.one_off.F037_run_passed_product_page_evidence_backfill_batch import (
    CURRENT_SCANNER_FAIL_EVIDENCE_COLUMNS,
    RESULT_COLUMNS,
    STATE_COLUMNS,
    apply_batch_outputs,
    run_backfill_batch,
)


OBSERVED = "2026-05-20T16:00:00Z"


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).fillna("").to_csv(path, index=False)


def _queue_row(idx: int, *, ready: str = "1") -> dict[str, str]:
    row = {column: "" for column in BACKFILL_QUEUE_COLUMNS}
    row.update(
        {
            "observed_utc": OBSERVED,
            "backfill_batch_id": "queue-batch",
            "backfill_scope": "all",
            "backfill_id": f"f036_row_{idx}",
            "backfill_priority": str(100 - idx),
            "asin": f"B00000000{idx}",
            "supplier_id": "stocklist_supplier",
            "supplier_sku": f"SKU-{idx}",
            "supplier_title": f"Supplier title {idx}",
            "amazon_title": f"Amazon title {idx}",
            "barcode": f"501234567890{idx}",
            "unit_cost": "5.00",
            "currency": "GBP",
            "vat_rate": "20",
            "source_pass_file": "f_live_price_file_pass_review_latest.csv",
            "source_pass_files": "f_live_price_file_pass_review_latest.csv",
            "source_pass_row_count": "1",
            "f061_ready_flag": ready,
            "recommended_next_action": "run_f061_page_evidence_backfill" if ready == "1" else "needs_barcode_before_f061_backfill",
        }
    )
    if ready != "1":
        row["barcode"] = ""
    return row


def test_prepare_batch_stages_next_pending_rows(tmp_path: Path) -> None:
    queue_path = tmp_path / "queue.csv"
    state_path = tmp_path / "state.csv"
    results_path = tmp_path / "results.csv"
    health_path = tmp_path / "health.csv"
    manifest_path = tmp_path / "manifest.csv"
    proof_base = tmp_path / "proof"
    _write_csv(queue_path, [_queue_row(1), _queue_row(2), _queue_row(3)], BACKFILL_QUEUE_COLUMNS)

    result = run_backfill_batch(
        root=tmp_path,
        queue_path=queue_path,
        state_path=state_path,
        results_path=results_path,
        health_path=health_path,
        manifest_path=manifest_path,
        proof_base=proof_base,
        batch_size=2,
        batch_id="batch-test",
        observed_utc=OBSERVED,
        execute=False,
    )

    assert result.status == "prepared"
    assert result.staged_rows == 2
    state = pd.read_csv(state_path, dtype=str).fillna("")
    assert list(state.columns) == STATE_COLUMNS
    assert state["backfill_status"].tolist() == ["staged", "staged", "pending"]
    active_run_path = proof_base / "batch-test" / get_f_output_contract("supplier_price_list_active_run").rel_path
    active_run = pd.read_csv(active_run_path, dtype=str).fillna("")
    assert len(active_run.index) == 2
    assert active_run.iloc[0]["supplier_title"] == "Supplier title 1"
    assert health_path.exists()
    assert manifest_path.exists()


def test_apply_batch_outputs_marks_success_and_writes_results(tmp_path: Path) -> None:
    queue_path = tmp_path / "queue.csv"
    state_path = tmp_path / "state.csv"
    results_path = tmp_path / "results.csv"
    health_path = tmp_path / "health.csv"
    manifest_path = tmp_path / "manifest.csv"
    proof_base = tmp_path / "proof"
    _write_csv(queue_path, [_queue_row(1)], BACKFILL_QUEUE_COLUMNS)
    result = run_backfill_batch(
        root=tmp_path,
        queue_path=queue_path,
        state_path=state_path,
        results_path=results_path,
        health_path=health_path,
        manifest_path=manifest_path,
        proof_base=proof_base,
        batch_size=1,
        batch_id="batch-success",
        observed_utc=OBSERVED,
        execute=False,
    )
    batch_rows = pd.read_csv(Path(result.proof_root) / "page_evidence_backfill_batch_queue.csv", dtype=str).fillna("")
    evidence_path = Path(result.proof_root) / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path
    evidence_columns = [
        *get_f_output_contract("feeder_legacy_scrape_evidence_live").required_columns,
        *get_f_output_contract("feeder_legacy_scrape_evidence_live").optional_columns,
    ]
    evidence_row = {column: "" for column in evidence_columns}
    evidence_row.update(
        {
            "observed_utc": OBSERVED,
            "candidate_id": "f036_row_1",
            "supplier_id": "stocklist_supplier",
            "supplier_sku": "SKU-1",
            "supplier_title": "Supplier title 1",
            "barcode": "5012345678901",
            "asin": "B000000001",
            "title": "Amazon title 1",
            "main_title": "Amazon scraped title 1",
            "scrape_attempted": "True",
            "scrape_success": "True",
            "product_description": "Each pack contains 50 sleeves.",
            "product_feature_bullets": "Official sleeves",
        }
    )
    _write_csv(evidence_path, [evidence_row], evidence_columns)

    state, rows = apply_batch_outputs(
        proof_root=Path(result.proof_root),
        batch_rows=batch_rows,
        state_path=state_path,
        results_path=results_path,
        observed_utc=OBSERVED,
        batch_id="batch-success",
    )

    assert state.iloc[0]["backfill_status"] == "succeeded"
    assert state.iloc[0]["page_evidence_captured_flag"] == "1"
    assert rows[0]["product_description"] == "Each pack contains 50 sleeves."
    results = pd.read_csv(results_path, dtype=str).fillna("")
    assert list(results.columns) == RESULT_COLUMNS
    assert results.iloc[0]["amazon_title"] == "Amazon scraped title 1"
    assert results.iloc[0]["backfill_status"] == "succeeded"
    assert results.iloc[0]["resolved_asin"] == "B000000001"


def test_apply_batch_outputs_marks_current_scanner_fail_as_skipped(tmp_path: Path) -> None:
    queue_path = tmp_path / "queue.csv"
    state_path = tmp_path / "state.csv"
    results_path = tmp_path / "results.csv"
    health_path = tmp_path / "health.csv"
    manifest_path = tmp_path / "manifest.csv"
    proof_base = tmp_path / "proof"
    _write_csv(queue_path, [_queue_row(1)], BACKFILL_QUEUE_COLUMNS)
    result = run_backfill_batch(
        root=tmp_path,
        queue_path=queue_path,
        state_path=state_path,
        results_path=results_path,
        health_path=health_path,
        manifest_path=manifest_path,
        proof_base=proof_base,
        batch_size=1,
        batch_id="batch-current-scanner-fail",
        observed_utc=OBSERVED,
        execute=False,
    )
    batch_rows = pd.read_csv(Path(result.proof_root) / "page_evidence_backfill_batch_queue.csv", dtype=str).fillna("")
    evidence_path = Path(result.proof_root) / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path
    evidence_columns = [
        *get_f_output_contract("feeder_legacy_scrape_evidence_live").required_columns,
        *get_f_output_contract("feeder_legacy_scrape_evidence_live").optional_columns,
    ]
    evidence_row = {column: "" for column in evidence_columns}
    evidence_row.update(
        {
            "observed_utc": OBSERVED,
            "candidate_id": "f036_row_1",
            "supplier_id": "stocklist_supplier",
            "supplier_sku": "SKU-1",
            "supplier_title": "Supplier title 1",
            "barcode": "5012345678901",
            "asin": "B000000001",
            "title": "Amazon title 1",
            "main_title": "Amazon title 1",
            "pf": "FAIL",
            "first_check_status_code": "SELLERHISTORYFAIL",
            "status_reason": "SELLERHISTORYFAIL",
            "fail_codes": "DASHBOARD_NO_LOW_SELLER_COUNT",
            "hard_stop": "True",
            "scrape_attempted": "True",
            "scrape_success": "False",
            "scrape_error": "DASHBOARD_NO_LOW_SELLER_COUNT",
        }
    )
    _write_csv(evidence_path, [evidence_row], evidence_columns)

    state, rows = apply_batch_outputs(
        proof_root=Path(result.proof_root),
        batch_rows=batch_rows,
        state_path=state_path,
        results_path=results_path,
        observed_utc=OBSERVED,
        batch_id="batch-current-scanner-fail",
    )

    assert state.iloc[0]["backfill_status"] == "skipped_current_scanner_fail"
    assert state.iloc[0]["page_evidence_captured_flag"] == "0"
    assert rows[0]["backfill_status"] == "skipped_current_scanner_fail"
    assert rows[0]["scrape_error"] == "DASHBOARD_NO_LOW_SELLER_COUNT"
    audit_path = state_path.parent / "current_scanner_fail_evidence.csv"
    audit = pd.read_csv(audit_path, dtype=str).fillna("")
    assert list(audit.columns) == CURRENT_SCANNER_FAIL_EVIDENCE_COLUMNS
    assert audit.iloc[0]["backfill_status"] == "skipped_current_scanner_fail"
    assert audit.iloc[0]["scanner_fail_reason"] == "current_scanner_fail:SELLERHISTORYFAIL|SELLERHISTORYFAIL|DASHBOARD_NO_LOW_SELLER_COUNT|DASHBOARD_NO_LOW_SELLER_COUNT"


def test_apply_batch_outputs_marks_screening_noasin_as_skipped(tmp_path: Path) -> None:
    queue_path = tmp_path / "queue.csv"
    state_path = tmp_path / "state.csv"
    results_path = tmp_path / "results.csv"
    health_path = tmp_path / "health.csv"
    manifest_path = tmp_path / "manifest.csv"
    proof_base = tmp_path / "proof"
    _write_csv(queue_path, [_queue_row(1)], BACKFILL_QUEUE_COLUMNS)
    result = run_backfill_batch(
        root=tmp_path,
        queue_path=queue_path,
        state_path=state_path,
        results_path=results_path,
        health_path=health_path,
        manifest_path=manifest_path,
        proof_base=proof_base,
        batch_size=1,
        batch_id="batch-noasin",
        observed_utc=OBSERVED,
        execute=False,
    )
    batch_rows = pd.read_csv(Path(result.proof_root) / "page_evidence_backfill_batch_queue.csv", dtype=str).fillna("")
    screening_path = Path(result.proof_root) / get_f_output_contract("f_screening_row_state_live").rel_path
    screening_columns = [
        *get_f_output_contract("f_screening_row_state_live").required_columns,
        *get_f_output_contract("f_screening_row_state_live").optional_columns,
    ]
    screening_row = {column: "" for column in screening_columns}
    screening_row.update(
        {
            "observed_utc": OBSERVED,
            "candidate_id": "f036_row_1",
            "supplier_id": "stocklist_supplier",
            "supplier_sku": "SKU-1",
            "barcode": "5012345678901",
            "supplier_title": "Supplier title 1",
            "pf": "FAIL",
            "status_reason": "NOASIN",
            "fail_code": "NOASIN",
            "last_stage": "catalog",
            "row_status": "timeout",
        }
    )
    _write_csv(screening_path, [screening_row], screening_columns)

    state, rows = apply_batch_outputs(
        proof_root=Path(result.proof_root),
        batch_rows=batch_rows,
        state_path=state_path,
        results_path=results_path,
        observed_utc=OBSERVED,
        batch_id="batch-noasin",
    )

    assert state.iloc[0]["backfill_status"] == "needs_asin_recheck"
    assert state.iloc[0]["result_notes"] == "current_scanner_fail:NOASIN|NOASIN"
    assert rows[0]["backfill_status"] == "needs_asin_recheck"


def test_apply_batch_outputs_matches_evidence_by_backfill_id_when_asin_changes(tmp_path: Path) -> None:
    queue_path = tmp_path / "queue.csv"
    state_path = tmp_path / "state.csv"
    results_path = tmp_path / "results.csv"
    health_path = tmp_path / "health.csv"
    manifest_path = tmp_path / "manifest.csv"
    proof_base = tmp_path / "proof"
    _write_csv(queue_path, [_queue_row(1)], BACKFILL_QUEUE_COLUMNS)
    result = run_backfill_batch(
        root=tmp_path,
        queue_path=queue_path,
        state_path=state_path,
        results_path=results_path,
        health_path=health_path,
        manifest_path=manifest_path,
        proof_base=proof_base,
        batch_size=1,
        batch_id="batch-asin-changed",
        observed_utc=OBSERVED,
        execute=False,
    )
    batch_rows = pd.read_csv(Path(result.proof_root) / "page_evidence_backfill_batch_queue.csv", dtype=str).fillna("")
    evidence_path = Path(result.proof_root) / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path
    evidence_columns = [
        *get_f_output_contract("feeder_legacy_scrape_evidence_live").required_columns,
        *get_f_output_contract("feeder_legacy_scrape_evidence_live").optional_columns,
    ]
    evidence_row = {column: "" for column in evidence_columns}
    evidence_row.update(
        {
            "observed_utc": OBSERVED,
            "candidate_id": "f036_row_1",
            "supplier_id": "stocklist_supplier",
            "supplier_sku": "SKU-1",
            "supplier_title": "Supplier title 1",
            "barcode": "5012345678901",
            "asin": "B999999999",
            "main_title": "Resolved Amazon title",
            "scrape_attempted": "True",
            "scrape_success": "True",
            "product_description": "Resolved page evidence.",
        }
    )
    _write_csv(evidence_path, [evidence_row], evidence_columns)

    state, rows = apply_batch_outputs(
        proof_root=Path(result.proof_root),
        batch_rows=batch_rows,
        state_path=state_path,
        results_path=results_path,
        observed_utc=OBSERVED,
        batch_id="batch-asin-changed",
    )

    assert state.iloc[0]["backfill_status"] == "succeeded"
    assert "resolved_asin_changed:B000000001->B999999999" in state.iloc[0]["result_notes"]
    assert rows[0]["asin"] == "B000000001"
    assert rows[0]["resolved_asin"] == "B999999999"
    assert rows[0]["amazon_title"] == "Resolved Amazon title"


def test_existing_results_seed_completed_rows_without_restaging(tmp_path: Path) -> None:
    queue_path = tmp_path / "queue.csv"
    state_path = tmp_path / "state.csv"
    results_path = tmp_path / "results.csv"
    health_path = tmp_path / "health.csv"
    manifest_path = tmp_path / "manifest.csv"
    proof_base = tmp_path / "proof"
    _write_csv(queue_path, [_queue_row(1)], BACKFILL_QUEUE_COLUMNS)
    result_row = {column: "" for column in RESULT_COLUMNS}
    result_row.update(
        {
            "observed_utc": OBSERVED,
            "batch_id": "old-batch",
            "backfill_id": "f036_row_1",
            "asin": "B000000001",
            "page_evidence_captured_flag": "1",
            "product_description": "Already captured",
        }
    )
    _write_csv(results_path, [result_row], RESULT_COLUMNS)

    result = run_backfill_batch(
        root=tmp_path,
        queue_path=queue_path,
        state_path=state_path,
        results_path=results_path,
        health_path=health_path,
        manifest_path=manifest_path,
        proof_base=proof_base,
        batch_size=1,
        batch_id="batch-none",
        observed_utc=OBSERVED,
        execute=False,
    )

    assert result.status == "no_pending_rows"
    state = pd.read_csv(state_path, dtype=str).fillna("")
    assert state.iloc[0]["backfill_status"] == "succeeded"
    assert state.iloc[0]["page_evidence_captured_flag"] == "1"


def test_prepare_can_reuse_existing_staged_batch_by_id(tmp_path: Path) -> None:
    queue_path = tmp_path / "queue.csv"
    state_path = tmp_path / "state.csv"
    results_path = tmp_path / "results.csv"
    health_path = tmp_path / "health.csv"
    manifest_path = tmp_path / "manifest.csv"
    proof_base = tmp_path / "proof"
    _write_csv(queue_path, [_queue_row(1), _queue_row(2)], BACKFILL_QUEUE_COLUMNS)

    first = run_backfill_batch(
        root=tmp_path,
        queue_path=queue_path,
        state_path=state_path,
        results_path=results_path,
        health_path=health_path,
        manifest_path=manifest_path,
        proof_base=proof_base,
        batch_size=1,
        batch_id="same-batch",
        observed_utc=OBSERVED,
        execute=False,
    )
    second = run_backfill_batch(
        root=tmp_path,
        queue_path=queue_path,
        state_path=state_path,
        results_path=results_path,
        health_path=health_path,
        manifest_path=manifest_path,
        proof_base=proof_base,
        batch_size=1,
        batch_id="same-batch",
        observed_utc=OBSERVED,
        execute=False,
    )

    assert first.status == "prepared"
    assert second.status == "prepared"
    assert first.proof_root == second.proof_root
    state = pd.read_csv(state_path, dtype=str).fillna("")
    assert state["backfill_status"].tolist() == ["staged", "pending"]
