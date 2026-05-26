from __future__ import annotations

from scripts.phase1.phase1_main_loop import _compute_temp_trial_target_gbp


def test_temp_trial_target_is_competitor_minus_5p() -> None:
    target, reasons = _compute_temp_trial_target_gbp(
        competitor_price_gbp="7.10",
        undercut_gbp="0.05",
        hard_floor_gbp="5.90",
        final_ceiling_landed_gbp="10.64",
    )
    assert target == "7.05"
    assert "TEMP_TRIAL_ACTIVE" in reasons
    assert "TEMP_TRIAL_UNDERCUT_GBP_0P05" in reasons


def test_temp_trial_target_clamps_to_floor() -> None:
    target, reasons = _compute_temp_trial_target_gbp(
        competitor_price_gbp="5.91",
        undercut_gbp="0.05",
        hard_floor_gbp="5.90",
        final_ceiling_landed_gbp="10.64",
    )
    assert target == "5.90"
    assert "TEMP_TRIAL_FLOOR_CLAMP" in reasons


def test_temp_trial_target_clamps_to_ceiling() -> None:
    target, reasons = _compute_temp_trial_target_gbp(
        competitor_price_gbp="11.00",
        undercut_gbp="0.05",
        hard_floor_gbp="5.90",
        final_ceiling_landed_gbp="10.64",
    )
    assert target == "10.64"
    assert "TEMP_TRIAL_CEILING_CLAMP" in reasons


def test_temp_trial_skip_when_competitor_missing() -> None:
    target, reasons = _compute_temp_trial_target_gbp(
        competitor_price_gbp="",
        undercut_gbp="0.05",
        hard_floor_gbp="5.90",
        final_ceiling_landed_gbp="10.64",
    )
    assert target == ""
    assert reasons == ["TEMP_TRIAL_SKIPPED_NO_COMPETITOR"]
