from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._schemas import get_f_output_contract
from scripts.one_off.F020_check_review_event_contract import assert_review_event_contract, check_review_event_contract


def _write_review_events(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def test_f020_fails_loudly_when_review_event_file_is_missing(tmp_path: Path) -> None:
    report = check_review_event_contract(root=tmp_path)

    assert report["status"] == "fail"
    assert any("missing contract file" in err for err in report["errors"])
    with pytest.raises(ValueError):
        assert_review_event_contract(root=tmp_path)


def test_f020_passes_when_review_event_file_has_required_columns_and_valid_values(tmp_path: Path) -> None:
    event_path = tmp_path / get_f_output_contract("feeder_review_events").rel_path
    _write_review_events(
        event_path,
        [
            {
                "event_utc": "2026-04-23T10:00:00Z",
                "event_id": "evt-1",
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-1",
                "supplier_sku": "SKU-1",
                "asin_raw": "B000000001",
                "asin_padded": "B000000001",
                "amazon_dp_url": "https://www.amazon.co.uk/dp/B000000001",
                "review_decision": "pass",
                "review_reason_code": "wrong_product",
                "review_note": "looks good",
                "actor": "tester",
                "source_reference": "unit_test",
            }
        ],
    )

    report = assert_review_event_contract(root=tmp_path)

    assert report["status"] == "pass"
    assert report["row_count"] == 1
    assert report["missing_columns"] == []
    assert report["invalid_review_reason_code_rows"] == 0


def test_f020_fails_when_required_columns_or_values_are_invalid(tmp_path: Path) -> None:
    event_path = tmp_path / get_f_output_contract("feeder_review_events").rel_path
    _write_review_events(
        event_path,
        [
            {
                "event_utc": "not-a-timestamp",
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-1",
                "supplier_sku": "SKU-1",
                "asin_raw": "B000000001",
                "asin_padded": "B000000001",
                "amazon_dp_url": "https://www.amazon.co.uk/dp/B000000001",
                "review_decision": "maybe",
                "review_reason_code": "not_a_real_reason",
                "review_note": "invalid",
                "actor": "tester",
                "source_reference": "unit_test",
            }
        ],
    )

    report = check_review_event_contract(root=tmp_path)

    assert report["status"] == "fail"
    assert any("missing required columns: event_id" in err for err in report["errors"])
    assert any("invalid review_decision values" in err for err in report["errors"])
    assert any("invalid review_reason_code values" in err for err in report["errors"])
    assert any("invalid event_utc values" in err for err in report["errors"])
