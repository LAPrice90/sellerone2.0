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

from scripts.one_off.F030_build_review_feedback_reason_theme_report import (
    OUTPUT_COLUMNS,
    build_review_feedback_reason_theme_report,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def test_feedback_theme_report_classifies_manual_fail_reasons(tmp_path: Path) -> None:
    events_path = tmp_path / "events.csv"
    triage_path = tmp_path / "triage.csv"
    output_path = tmp_path / "theme.csv"
    summary_path = tmp_path / "summary.md"

    _write_csv(
        events_path,
        [
            {
                "event_utc": "2026-05-15T14:32:04Z",
                "event_id": "evt-wrong-product",
                "active_supplier_id": "entertainment_trading",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-wrong",
                "supplier_sku": "1093205",
                "asin_padded": "B0BHDQ2JJH",
                "review_decision": "fail",
                "review_reason_code": "wrong_product",
                "review_reason_label": "Wrong product",
                "review_note": "wrong product on the price list and suspicious profit",
                "title": "Lexar memory card",
                "brand": "Lexar",
            },
            {
                "event_utc": "2026-04-29T08:21:05Z",
                "event_id": "evt-amazon-only",
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-2",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-seller",
                "supplier_sku": "1120373",
                "asin_padded": "B00007KQF8",
                "review_decision": "fail",
                "review_note": "only sold by amazon and average 1 seller",
                "title": "BOSS Bottled",
                "brand": "HUGO BOSS",
            },
            {
                "event_utc": "2026-04-29T11:58:11Z",
                "event_id": "evt-pass",
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-2",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-pass",
                "supplier_sku": "1257989",
                "asin_padded": "B09FQCWKPW",
                "review_decision": "pass",
                "review_note": "Looks like a good listing",
                "title": "Kensington trackball",
                "brand": "Kensington",
            },
        ],
    )
    _write_csv(
        triage_path,
        [
            {
                "candidate_id": "cand-wrong",
                "asin": "B0BHDQ2JJH",
                "fail_type": "type_2_known_policy_or_memory",
                "fail_reason_code": "review_memory_fail_decision",
                "evidence_source": "feeder_review_events:evt-wrong-product",
            }
        ],
    )

    result = build_review_feedback_reason_theme_report(
        review_events_path=events_path,
        triage_path=triage_path,
        output_path=output_path,
        summary_path=summary_path,
        observed_utc="2026-05-19T12:00:00Z",
    )

    assert list(result.report_df.columns) == OUTPUT_COLUMNS
    by_event = {row["event_id"]: row for row in result.report_df.to_dict("records")}
    assert "product_identity_mismatch" in by_event["evt-wrong-product"]["reason_themes"]
    assert "profit_or_upside_weak" in by_event["evt-wrong-product"]["reason_themes"]
    assert "structured_reason_code:wrong_product" in by_event["evt-wrong-product"]["theme_evidence_terms"]
    assert by_event["evt-wrong-product"]["review_reason_code"] == "wrong_product"
    assert "seller_ownership_risk" in by_event["evt-amazon-only"]["reason_themes"]
    assert by_event["evt-pass"]["reason_themes"] == "pass_calibration"
    assert by_event["evt-wrong-product"]["triage_fail_reason_code"] == "review_memory_fail_decision"
    assert result.report["feedback_rows"] == 3
    assert result.report["manual_fail_rows"] == 2
    assert result.report["manual_pass_rows"] == 1
    assert result.report["unclassified_manual_fail_rows"] == 0
    assert result.report["review_reason_code_counts"] == {"wrong_product": 1}
    assert output_path.exists()
    assert summary_path.exists()
