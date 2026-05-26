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

from scripts.one_off.F027_build_profit_formula_conflict_audit import (
    FORMULA_CODE_CLEAR,
    FORMULA_CODE_INFLATED,
    FORMULA_CODE_MISSING,
    FORMULA_CODE_REVIEW,
    REQUIRED_COLUMNS,
    build_profit_formula_conflict_audit,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _row_by_candidate(df: pd.DataFrame, candidate_id: str) -> dict[str, str]:
    row = df.loc[df["candidate_id"] == candidate_id]
    assert not row.empty
    return {key: str(value) for key, value in row.iloc[0].to_dict().items()}


def test_f027_builds_required_columns_and_classifies_formula_conflicts(tmp_path: Path) -> None:
    pass_path = tmp_path / "pass.csv"
    near_miss_path = tmp_path / "near.csv"
    first_checks_path = tmp_path / "first_checks.csv"
    scrape_path = tmp_path / "scrape.csv"
    output_path = tmp_path / "audit.csv"

    _write_csv(
        pass_path,
        [
            {
                "candidate_id": "cand-b0b7298qn6",
                "supplier_sku": "1204860",
                "asin": "B0B7298QN6",
                "title": "B0B7298QN6 Item",
                "expected_units_next_30d": "40",
                "profit_per_unit_30d_gbp": "6.92",
                "expected_profit_next_30d_gbp": "276.8",
            },
            {
                "candidate_id": "cand-clear",
                "supplier_sku": "SKU-CLEAR",
                "asin": "ASIN-CLEAR",
                "title": "Clear Row",
                "expected_units_next_30d": "30",
                "profit_per_unit_30d_gbp": "4.38",
                "expected_profit_next_30d_gbp": "131.4",
            },
            {
                "candidate_id": "cand-missing",
                "supplier_sku": "SKU-MISSING",
                "asin": "ASIN-MISSING",
                "title": "Missing Inputs Row",
                "expected_units_next_30d": "12",
                "profit_per_unit_30d_gbp": "5.0",
                "expected_profit_next_30d_gbp": "60",
            },
            {
                "candidate_id": "cand-negative",
                "supplier_sku": "SKU-NEG",
                "asin": "ASIN-NEG",
                "title": "Negative Profit Row",
                "expected_units_next_30d": "8",
                "profit_per_unit_30d_gbp": "1.5",
                "expected_profit_next_30d_gbp": "12",
            },
        ],
    )
    _write_csv(near_miss_path, [])
    _write_csv(
        first_checks_path,
        [
            {
                "candidate_id": "cand-b0b7298qn6",
                "supplier_sku": "1204860",
                "asin": "B0B7298QN6",
                "cost": "10.01",
                "fba_fee": "2.07",
                "referral_fee": "3.61",
                "digital_fee": "0.11",
                "est_shipping": "0.02",
                "vat": "20",
                "api_live_price": "24.09",
                "bbp_live_sell_price": "24.89",
                "bbp_30d_avg_price": "24.28",
                "break_even": "17.36",
            },
            {
                "candidate_id": "cand-clear",
                "supplier_sku": "SKU-CLEAR",
                "asin": "ASIN-CLEAR",
                "cost": "10.01",
                "fba_fee": "2.07",
                "referral_fee": "3.61",
                "digital_fee": "0.11",
                "est_shipping": "0.02",
                "vat": "20",
                "api_live_price": "24.09",
                "bbp_live_sell_price": "24.89",
                "bbp_30d_avg_price": "24.28",
                "break_even": "17.36",
            },
            {
                "candidate_id": "cand-missing",
                "supplier_sku": "SKU-MISSING",
                "asin": "ASIN-MISSING",
                "cost": "11.00",
                "fba_fee": "2.30",
                "referral_fee": "",
                "digital_fee": "0.13",
                "est_shipping": "0.04",
                "vat": "20",
                "api_live_price": "20.00",
                "bbp_live_sell_price": "21.00",
                "bbp_30d_avg_price": "20.50",
                "break_even": "16.00",
            },
            {
                "candidate_id": "cand-negative",
                "supplier_sku": "SKU-NEG",
                "asin": "ASIN-NEG",
                "cost": "9.00",
                "fba_fee": "2.00",
                "referral_fee": "1.00",
                "digital_fee": "0.10",
                "est_shipping": "0.10",
                "vat": "20",
                "api_live_price": "10.00",
                "bbp_live_sell_price": "10.50",
                "bbp_30d_avg_price": "10.00",
                "break_even": "",
            },
        ],
    )
    _write_csv(
        scrape_path,
        [
            {
                "candidate_id": "cand-b0b7298qn6",
                "supplier_sku": "1204860",
                "asin": "B0B7298QN6",
                "avg_30_day_price": "24.28",
            },
            {
                "candidate_id": "cand-clear",
                "supplier_sku": "SKU-CLEAR",
                "asin": "ASIN-CLEAR",
                "avg_30_day_price": "24.28",
            },
            {
                "candidate_id": "cand-missing",
                "supplier_sku": "SKU-MISSING",
                "asin": "ASIN-MISSING",
                "avg_30_day_price": "20.50",
            },
            {
                "candidate_id": "cand-negative",
                "supplier_sku": "SKU-NEG",
                "asin": "ASIN-NEG",
                "avg_30_day_price": "10.00",
            },
        ],
    )

    result = build_profit_formula_conflict_audit(
        pass_path=pass_path,
        near_miss_path=near_miss_path,
        first_checks_path=first_checks_path,
        scrape_evidence_path=scrape_path,
        output_path=output_path,
        observed_utc="2026-04-23T12:00:00Z",
    )

    assert output_path.exists()
    assert list(result.audit_df.columns) == REQUIRED_COLUMNS
    assert result.report["unclassified_rows"] == 0

    b0b = _row_by_candidate(result.audit_df, "cand-b0b7298qn6")
    assert b0b["profit_formula_code"] == FORMULA_CODE_INFLATED
    assert float(b0b["corrected_profit_per_unit_gbp"]) < float(b0b["old_profit_per_unit_gbp"])
    assert float(b0b["corrected_expected_profit_next_30d_gbp"]) < float(b0b["old_expected_profit_next_30d_gbp"])

    clear = _row_by_candidate(result.audit_df, "cand-clear")
    assert clear["profit_formula_code"] == FORMULA_CODE_CLEAR
    assert clear["recommended_action"] == "allow_if_other_checks_pass"

    missing = _row_by_candidate(result.audit_df, "cand-missing")
    assert missing["profit_formula_code"] == FORMULA_CODE_MISSING
    assert missing["recommended_action"] == "targeted_rescan_needed"

    negative = _row_by_candidate(result.audit_df, "cand-negative")
    assert negative["profit_formula_code"] == FORMULA_CODE_REVIEW
    assert float(negative["corrected_profit_per_unit_gbp"]) <= 0
    assert negative["recommended_action"] != "allow_if_other_checks_pass"

    seen_codes = set(result.audit_df["profit_formula_code"].tolist())
    assert FORMULA_CODE_INFLATED in seen_codes
    assert FORMULA_CODE_CLEAR in seen_codes
    assert FORMULA_CODE_MISSING in seen_codes
    assert FORMULA_CODE_REVIEW in seen_codes
