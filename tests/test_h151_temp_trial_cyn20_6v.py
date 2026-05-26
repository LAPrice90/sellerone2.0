from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from scripts.one_off.H151_temp_trial_cyn20_6v import build_temp_trial_decision


def _row(
    *,
    sku: str = "6V-EEC1-2S9Z",
    asin: str = "B06WW79DX5",
    current: str = "7.10",
    competitor: str = "7.10",
    floor: str = "5.90",
    ceiling: str = "10.64",
) -> dict[str, str]:
    return {
        "sku": sku,
        "asin": asin,
        "current_price_gbp": current,
        "next_comp_gbp": competitor,
        "floor_gbp": floor,
        "ceiling_gbp": ceiling,
    }


def test_temp_trial_uses_competitor_minus_five_pence() -> None:
    decision = build_temp_trial_decision(
        row=_row(),
        combined_path=Path("out/analysis_reports/phase1_observation_combined_2026-03-30.csv"),
        undercut_gbp=Decimal("0.05"),
    )
    assert decision.action_status == "READY"
    assert decision.raw_target_gbp == "7.05"
    assert decision.final_target_gbp == "7.05"
    assert decision.action_reason_codes == "UNDERCUT_APPLIED"


def test_temp_trial_clamps_to_floor() -> None:
    decision = build_temp_trial_decision(
        row=_row(competitor="5.91", floor="5.90", current="6.20"),
        combined_path=Path("dummy.csv"),
        undercut_gbp=Decimal("0.05"),
    )
    assert decision.raw_target_gbp == "5.86"
    assert decision.final_target_gbp == "5.90"
    assert "FLOOR_CLAMPED" in decision.action_reason_codes


def test_temp_trial_clamps_to_ceiling() -> None:
    decision = build_temp_trial_decision(
        row=_row(competitor="11.00", ceiling="10.64", current="9.90"),
        combined_path=Path("dummy.csv"),
        undercut_gbp=Decimal("0.05"),
    )
    assert decision.raw_target_gbp == "10.95"
    assert decision.final_target_gbp == "10.64"
    assert "CEILING_CLAMPED" in decision.action_reason_codes


def test_temp_trial_blocks_when_competitor_missing() -> None:
    decision = build_temp_trial_decision(
        row=_row(competitor=""),
        combined_path=Path("dummy.csv"),
        undercut_gbp=Decimal("0.05"),
    )
    assert decision.action_status == "BLOCKED"
    assert decision.final_target_gbp == ""
    assert "COMPETITOR_MISSING" in decision.action_reason_codes

