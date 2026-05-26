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

from scripts.one_off.F024_build_demand_range_review_sample_pack import (
    SAMPLE_COLUMNS,
    build_demand_range_review_sample_pack,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _audit_row(
    *,
    asin: str,
    demand_conflict_code: str,
    recommended_action: str,
    bbp_units: int,
    expected_units: int | None = None,
    title: str = "",
) -> dict[str, str]:
    return {
        "asin": asin,
        "candidate_id": f"cand-{asin}",
        "supplier_sku": f"sku-{asin}",
        "review_pack_type": "passes",
        "title": title,
        "amazon_demand_signal": "",
        "amazon_demand_floor": "0",
        "amazon_demand_ceiling": "49",
        "bbp_units": str(bbp_units),
        "expected_units_next_30d": str(expected_units if expected_units is not None else bbp_units),
        "demand_conflict_code": demand_conflict_code,
        "uk_reviews": "10",
        "variant_reviews": "100",
        "confidence_adjustment": "",
        "recommended_action": recommended_action,
        "evidence_source": "unit_test",
    }


def _metric(summary_df: pd.DataFrame, metric: str) -> str:
    rows = summary_df.loc[summary_df["metric"] == metric]
    assert not rows.empty
    return str(rows.iloc[0]["value"])


def _run_pack(tmp_path: Path, rows: list[dict[str, str]]):
    audit_path = tmp_path / "audit.csv"
    sample_path = tmp_path / "sample.csv"
    summary_path = tmp_path / "summary.csv"
    _write_csv(audit_path, rows)
    return build_demand_range_review_sample_pack(
        audit_path=audit_path,
        sample_output_path=sample_path,
        summary_output_path=summary_path,
    )


def test_includes_all_remove_from_clean_pass_rows(tmp_path: Path) -> None:
    rows = [
        _audit_row(
            asin=f"REMOVE-{idx:02d}",
            demand_conflict_code="amazon_blank_bbp_high",
            recommended_action="remove_from_clean_pass",
            bbp_units=1000 - idx,
        )
        for idx in range(12)
    ]
    rows.extend(
        [
            _audit_row(
                asin=f"ALLOW-{idx:02d}",
                demand_conflict_code="amazon_blank_bbp_low",
                recommended_action="allow_if_other_checks_pass",
                bbp_units=idx,
            )
            for idx in range(3)
        ]
    )

    result = _run_pack(tmp_path, rows)

    remove_keys = {
        (row["asin"], row["demand_conflict_code"])
        for row in result.sample_df.to_dict("records")
        if row["recommended_action"] == "remove_from_clean_pass"
    }
    expected_remove_keys = {(f"REMOVE-{idx:02d}", "amazon_blank_bbp_high") for idx in range(12)}
    assert expected_remove_keys <= remove_keys


def test_samples_max_10_rows_per_other_recommended_action(tmp_path: Path) -> None:
    rows: list[dict[str, str]] = []
    for idx in range(15):
        rows.append(
            _audit_row(
                asin=f"ALLOW-{idx:02d}",
                demand_conflict_code="amazon_blank_bbp_low",
                recommended_action="allow_if_other_checks_pass",
                bbp_units=100 - idx,
            )
        )
        rows.append(
            _audit_row(
                asin=f"MANUAL-{idx:02d}",
                demand_conflict_code="amazon_50_bbp_warn",
                recommended_action="manual_review",
                bbp_units=200 - idx,
            )
        )
        rows.append(
            _audit_row(
                asin=f"WEAK-{idx:02d}",
                demand_conflict_code="weak_uk_review_confirms_demand_risk",
                recommended_action="strengthen_demand_risk_action",
                bbp_units=300 - idx,
            )
        )
        rows.append(
            _audit_row(
                asin=f"STOCK-{idx:02d}",
                demand_conflict_code="seller_stock_missing_for_demand_check",
                recommended_action="targeted_rescan_needed",
                bbp_units=400 - idx,
            )
        )

    result = _run_pack(tmp_path, rows)

    action_counts = result.sample_df["recommended_action"].value_counts().to_dict()
    assert action_counts["allow_if_other_checks_pass"] == 10
    assert action_counts["manual_review"] == 10
    assert action_counts["strengthen_demand_risk_action"] == 10
    assert action_counts["targeted_rescan_needed"] == 10


def test_samples_max_10_rows_per_major_conflict_code_reason(tmp_path: Path) -> None:
    rows = [
        _audit_row(
            asin=f"HIGH-{idx:02d}",
            demand_conflict_code="amazon_blank_bbp_high",
            recommended_action="remove_from_clean_pass",
            bbp_units=1000 - idx,
        )
        for idx in range(12)
    ]
    rows.extend(
        [
            _audit_row(
                asin=f"WARN-{idx:02d}",
                demand_conflict_code="amazon_50_bbp_warn",
                recommended_action="manual_review",
                bbp_units=200 - idx,
            )
            for idx in range(12)
        ]
    )

    result = _run_pack(tmp_path, rows)

    for code in ("amazon_blank_bbp_high", "amazon_50_bbp_warn"):
        reason = f"major_conflict_code_sample:{code}"
        reason_count = int(result.sample_df["sample_reason"].map(lambda value: reason in str(value).split("|")).sum())
        assert reason_count == 10


def test_always_includes_b0c8c3jf9x_when_present(tmp_path: Path) -> None:
    rows = [
        _audit_row(
            asin=f"ALLOW-{idx:02d}",
            demand_conflict_code="amazon_blank_bbp_low",
            recommended_action="allow_if_other_checks_pass",
            bbp_units=1000 - idx,
        )
        for idx in range(12)
    ]
    rows.append(
        _audit_row(
            asin="B0C8C3JF9X",
            demand_conflict_code="amazon_blank_bbp_low",
            recommended_action="allow_if_other_checks_pass",
            bbp_units=1,
        )
    )

    result = _run_pack(tmp_path, rows)

    b0_rows = result.sample_df.loc[result.sample_df["asin"] == "B0C8C3JF9X"]
    assert not b0_rows.empty
    assert "always_include:B0C8C3JF9X" in b0_rows.iloc[0]["sample_reason"]
    assert _metric(result.summary_df, "b0c8c3jf9x_included") == "yes"


def test_deduplicates_by_asin_and_demand_conflict_code(tmp_path: Path) -> None:
    rows = [
        _audit_row(
            asin="DUP-ASIN",
            demand_conflict_code="amazon_blank_bbp_high",
            recommended_action="remove_from_clean_pass",
            bbp_units=500,
        ),
        {
            **_audit_row(
                asin="DUP-ASIN",
                demand_conflict_code="amazon_blank_bbp_high",
                recommended_action="remove_from_clean_pass",
                bbp_units=400,
            ),
            "candidate_id": "different-candidate",
        },
        _audit_row(
            asin="DUP-ASIN",
            demand_conflict_code="seller_stock_missing_for_demand_check",
            recommended_action="targeted_rescan_needed",
            bbp_units=500,
        ),
    ]

    result = _run_pack(tmp_path, rows)

    grouped = result.sample_df.groupby(["asin", "demand_conflict_code"]).size()
    assert grouped.max() == 1
    assert len(result.sample_df.index) == 2


def test_creates_both_sample_and_summary_outputs(tmp_path: Path) -> None:
    result = _run_pack(
        tmp_path,
        [
            _audit_row(
                asin="OUT-1",
                demand_conflict_code="amazon_blank_bbp_high",
                recommended_action="remove_from_clean_pass",
                bbp_units=500,
                title="Output Product",
            )
        ],
    )

    assert result.sample_output_path.exists()
    assert result.summary_output_path.exists()
    written_sample = pd.read_csv(result.sample_output_path, dtype=str).fillna("")
    written_summary = pd.read_csv(result.summary_output_path, dtype=str).fillna("")
    assert list(written_sample.columns) == SAMPLE_COLUMNS
    assert list(written_summary.columns) == ["metric", "value"]
    assert written_sample.iloc[0]["title"] == "Output Product"


def test_does_not_modify_source_audit_file(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.csv"
    sample_path = tmp_path / "sample.csv"
    summary_path = tmp_path / "summary.csv"
    _write_csv(
        audit_path,
        [
            _audit_row(
                asin="IMMUTABLE-1",
                demand_conflict_code="amazon_blank_bbp_high",
                recommended_action="remove_from_clean_pass",
                bbp_units=500,
            )
        ],
    )
    before = audit_path.read_text(encoding="utf-8")

    build_demand_range_review_sample_pack(
        audit_path=audit_path,
        sample_output_path=sample_path,
        summary_output_path=summary_path,
    )

    after = audit_path.read_text(encoding="utf-8")
    assert after == before


def test_summary_counts_reconcile(tmp_path: Path) -> None:
    rows = [
        _audit_row(
            asin=f"REMOVE-{idx}",
            demand_conflict_code="amazon_blank_bbp_high",
            recommended_action="remove_from_clean_pass",
            bbp_units=500 - idx,
        )
        for idx in range(3)
    ]
    rows.extend(
        [
            _audit_row(
                asin=f"ALLOW-{idx}",
                demand_conflict_code="amazon_blank_bbp_low",
                recommended_action="allow_if_other_checks_pass",
                bbp_units=50 - idx,
            )
            for idx in range(11)
        ]
    )
    rows.append(
        _audit_row(
            asin="MANUAL-1",
            demand_conflict_code="amazon_50_bbp_warn",
            recommended_action="manual_review",
            bbp_units=180,
        )
    )

    result = _run_pack(tmp_path, rows)
    summary = result.summary_df
    output_rows = int(_metric(summary, "output_sample_rows"))
    action_total = sum(
        int(_metric(summary, metric))
        for metric in (
            "rows_remove_from_clean_pass",
            "rows_manual_review",
            "rows_strengthen_demand_risk_action",
            "rows_targeted_rescan_needed",
            "rows_allow_if_other_checks_pass_sampled",
        )
    )

    assert int(_metric(summary, "input_audit_rows")) == len(rows)
    assert action_total == output_rows
    assert output_rows == len(result.sample_df.index)
    assert int(_metric(summary, "unclassified_rows")) == 0
