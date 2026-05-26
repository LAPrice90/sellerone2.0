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


def test_resolve_unified_truth_parked_forces_non_write_outcome() -> None:
    truth = resolve_unified_truth(
        suppression_active_flag="0",
        parked_flag="1",
        write_capable=False,
        execution_state="RAISE_FIND_LOSS",
        execution_write_status="WRITE_NOT_APPLIED",
        execution_reason_codes_json='["PHASE_LIVE_WRITE_ALLOWED"]',
        execution_final_ceiling_landed_gbp="33.48",
        execution_binding_ceiling_type="",
        suppression_buy_box_state="NORMAL",
        suppression_strategy_state="",
        suppression_write_status="",
        suppression_ceiling_landed_temp="",
        execution_old_price_gbp="16.94",
        execution_new_price_gbp="17.14",
        execution_hard_floor_gbp="16.94",
        observed_our_price_gbp="16.94",
        trace_candidate_price_gbp="16.95",
        trace_floor_total_gbp="16.94",
        execution_event_ts_utc="2026-03-15T02:22:59Z",
        trace_asof_utc="2026-03-15T02:28:42Z",
    )

    assert truth["unified_writer_outcome"] == "NO_WRITE_REQUIRED"
    assert truth["write_attempted_flag"] == "0"
    assert truth["write_applied_flag"] == "0"
    assert truth["truth_status"] == "PARKED"


def test_resolve_unified_truth_seller_detail_read_only_is_not_supp_blocked() -> None:
    truth = resolve_unified_truth(
        suppression_active_flag="1",
        parked_flag="0",
        write_capable=True,
        execution_state="SELLER_DETAIL_HOLD",
        execution_write_status="READ_ONLY_NO_WRITE",
        execution_reason_codes_json='["SELLER_DETAIL_STATUS_DETAIL_EMPTY_RESPONSE"]',
        execution_final_ceiling_landed_gbp="",
        execution_binding_ceiling_type="",
        suppression_buy_box_state="SUPPRESSED",
        suppression_strategy_state="STATE_SUPPRESSION_REACTIVATION",
        suppression_write_status="READ_ONLY_NO_WRITE",
        suppression_ceiling_landed_temp="",
        execution_old_price_gbp="23.87",
        execution_new_price_gbp="23.87",
        execution_hard_floor_gbp="23.87",
        observed_our_price_gbp="23.87",
        trace_candidate_price_gbp="",
        trace_floor_total_gbp="23.87",
        execution_event_ts_utc="2026-04-07T09:25:33Z",
        trace_asof_utc="2026-04-07T09:25:33Z",
    )

    assert truth["write_attempted_flag"] == "0"
    assert truth["truth_status"] == "SUPP_GATED_DETAIL"


def test_resolve_unified_truth_clamps_suppression_temp_ceiling_to_hard_floor() -> None:
    truth = resolve_unified_truth(
        suppression_active_flag="1",
        parked_flag="0",
        write_capable=False,
        execution_state="STATE_SUPPRESSION_REACTIVATION",
        execution_write_status="NO_WRITE_REQUIRED",
        execution_reason_codes_json='["CEILING_EFFECTIVE_CLAMPED_TO_HARD_FLOOR"]',
        execution_final_ceiling_landed_gbp="2.56",
        execution_binding_ceiling_type="COMPLIANCE",
        suppression_buy_box_state="SUPPRESSED_ASIN",
        suppression_strategy_state="STATE_SUPPRESSION_REACTIVATION",
        suppression_write_status="NO_WRITE_REQUIRED",
        suppression_ceiling_landed_temp="2.56",
        execution_old_price_gbp="7.31",
        execution_new_price_gbp="7.31",
        execution_hard_floor_gbp="7.31",
        observed_our_price_gbp="7.31",
        trace_candidate_price_gbp="7.31",
        trace_floor_total_gbp="7.31",
        execution_event_ts_utc="2026-04-17T01:05:18Z",
        trace_asof_utc="2026-04-17T01:08:58Z",
    )

    assert truth["true_binding_ceiling_gbp"] == "7.31"
    assert truth["true_binding_ceiling_type"] == "SUPPRESSION_TEMP_CLAMPED"
