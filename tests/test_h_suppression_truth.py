from scripts.h.h_suppression_truth import resolve_unified_truth


def test_resolve_unified_truth_infers_observed_floor_seek_apply() -> None:
    truth = resolve_unified_truth(
        suppression_active_flag="0",
        parked_flag="0",
        write_capable=True,
        execution_state="RAISE_FIND_LOSS",
        execution_write_status="NO_WRITE_REQUIRED",
        execution_reason_codes_json='["FLOOR_PRIORITY_CEILING_CONFLICT","PHASE_BEHAVIOR_APPLIED"]',
        execution_final_ceiling_landed_gbp="17.99",
        execution_binding_ceiling_type="COMPLIANCE",
        suppression_buy_box_state="NORMAL",
        suppression_strategy_state="",
        suppression_write_status="",
        suppression_ceiling_landed_temp="",
        execution_old_price_gbp="32.16",
        execution_new_price_gbp="32.16",
        execution_hard_floor_gbp="29.37",
        observed_our_price_gbp="29.36",
        trace_candidate_price_gbp="29.38",
        trace_floor_total_gbp="29.37",
        execution_event_ts_utc="2026-03-07T17:01:09Z",
        trace_asof_utc="2026-03-07T17:14:13Z",
    )

    assert truth["unified_writer_outcome"] == "APPLIED_OBSERVED"
    assert truth["unified_strategy_state"] == "CONTROLLED_EXIT_TO_FLOOR"
    assert truth["true_binding_ceiling_type"] == "PHASE_FLOOR"
    assert truth["true_binding_ceiling_gbp"] == "29.37"
    assert truth["truth_status"] == "WRITE_APPLIED"
