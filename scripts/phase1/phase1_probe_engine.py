from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable, List, Mapping


@dataclass(frozen=True)
class ProbeStateResult:
    state: str
    featured_outcome: str
    learning_blocked: bool
    reason_codes: List[str]


@dataclass(frozen=True)
class NextPriceDecision:
    state: str
    target_price_gbp: str
    write_required: bool
    reason_codes: List[str]


@dataclass(frozen=True)
class DeltaMemoryUpdateResult:
    learned_delta_effective_gbp: str
    highest_delta_win_effective_gbp: str
    lowest_delta_loss_effective_gbp: str
    delta_confidence: str
    valid_test_count: str
    contaminated_test_count: str
    last_valid_test_utc: str
    learning_updated: bool
    reason_codes: List[str]


@dataclass(frozen=True)
class SuppressionMemoryUpdateResult:
    highest_eligible_price: str
    lowest_ineligible_price: str
    suppression_threshold_estimate: str
    suppression_threshold_confidence: str
    suppression_last_validated_utc: str
    learning_updated: bool
    reason_codes: List[str]


def _to_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _to_money_string(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"{value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


def _to_count(value: object) -> int:
    dec = _to_decimal(value)
    if dec is None:
        return 0
    try:
        return max(0, int(dec))
    except (ValueError, OverflowError):
        return 0


def _to_confidence(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP):.4f}".rstrip("0").rstrip(".")


def _ladder_cap_source(
    *,
    ladder_price_1: Decimal | None,
    ladder_price_2: Decimal | None,
    ladder_price_3: Decimal | None,
    ladder_gap_buffer: Decimal,
    final_ceiling: Decimal | None,
) -> tuple[Decimal | None, str, List[str]]:
    """
    Resolve ladder-aware cap and source for multi-seller paths.

    Source priority:
    - second_lowest: conservative default
    - cluster_edge: when third rung is close enough to second rung
    - ceiling_clamp: final ceiling is tighter than ladder-derived cap
    """
    if ladder_price_2 is None or ladder_price_2 <= 0:
        return None, "", []

    reason_codes: List[str] = []
    safe_gap = ladder_gap_buffer if ladder_gap_buffer > 0 else Decimal("0.01")
    cap = ladder_price_2 - safe_gap
    if cap <= 0:
        cap = ladder_price_2
    source = "second_lowest"

    # If the third rung sits near the second rung, use the cluster edge as the
    # cap source to avoid repeatedly pinning into the absolute bottom rung.
    if (
        ladder_price_1 is not None
        and ladder_price_1 > 0
        and ladder_price_3 is not None
        and ladder_price_3 > 0
        and ladder_price_3 > ladder_price_2
    ):
        cluster_gap_max = max(safe_gap * Decimal("5"), Decimal("0.15"))
        second_third_gap = ladder_price_3 - ladder_price_2
        if second_third_gap <= cluster_gap_max:
            cluster_cap = ladder_price_3 - safe_gap
            if cluster_cap <= 0:
                cluster_cap = ladder_price_3
            if cluster_cap > cap:
                cap = cluster_cap
                source = "cluster_edge"

    if final_ceiling is not None and final_ceiling > 0 and cap > final_ceiling:
        cap = final_ceiling
        source = "ceiling_clamp"

    if source == "second_lowest":
        reason_codes.append("LADDER_CAP_SOURCE_SECOND_LOWEST")
    elif source == "cluster_edge":
        reason_codes.append("LADDER_CAP_SOURCE_CLUSTER_EDGE")
    elif source == "ceiling_clamp":
        reason_codes.append("LADDER_CAP_SOURCE_CEILING_CLAMP")
    return cap, source, reason_codes


def best_rival_effective_price(snapshot_rows: Iterable[Mapping[str, object]]) -> Decimal | None:
    rivals: List[Decimal] = []
    for row in snapshot_rows:
        if str(row.get("is_our_offer", "")).strip() == "1":
            continue
        effective = _to_decimal(row.get("effective_price_gbp"))
        if effective is None:
            continue
        rivals.append(effective)
    if not rivals:
        return None
    return min(rivals)


def evaluate_featured_outcome(
    *,
    featured_offer_winner_seller_id: object,
    our_seller_id: object,
    snapshot_rows: Iterable[Mapping[str, object]],
) -> str:
    winner = str(featured_offer_winner_seller_id or "").strip().lower()
    ours = str(our_seller_id or "").strip().lower()
    if winner and ours and winner == ours:
        return "OURS"
    if winner and ours and winner != ours:
        return "NOT_OURS"

    has_ours = False
    for row in snapshot_rows:
        if str(row.get("is_our_offer", "")).strip() == "1":
            has_ours = True
            if str(row.get("is_featured_offer_winner", "")).strip() == "1":
                return "OURS"
            if str(row.get("is_featured_offer_winner", "")).strip() == "0":
                return "NOT_OURS"
    if not has_ours:
        return "UNKNOWN"
    return "UNKNOWN"


def resolve_probe_state(
    *,
    featured_outcome: str,
    best_rival_effective_price_gbp: Decimal | None,
    highest_delta_win_effective_gbp: object,
    lowest_delta_loss_effective_gbp: object,
    delta_tolerance_gbp: object,
    buy_box_state: object = "",
) -> ProbeStateResult:
    reason_codes: List[str] = []
    outcome = str(featured_outcome or "").strip().upper()
    buy_box_state_text = str(buy_box_state or "").strip().upper()
    highest_win = _to_decimal(highest_delta_win_effective_gbp)
    lowest_loss = _to_decimal(lowest_delta_loss_effective_gbp)
    tolerance = _to_decimal(delta_tolerance_gbp) or Decimal("0.02")

    if buy_box_state_text in {"SUPPRESSED_ASIN", "DISQUALIFIED_SELF_PRICE"}:
        reason_codes.append(f"BUY_BOX_STATE_{buy_box_state_text}")
        return ProbeStateResult(
            state="STATE_SUPPRESSION_REACTIVATION",
            featured_outcome=outcome or "UNKNOWN",
            learning_blocked=True,
            reason_codes=reason_codes,
        )

    if outcome == "UNKNOWN":
        reason_codes.append("OUTCOME_UNKNOWN_HOLD")
        return ProbeStateResult(
            state="HOLD_OBSERVE",
            featured_outcome="UNKNOWN",
            learning_blocked=True,
            reason_codes=reason_codes,
        )

    if best_rival_effective_price_gbp is None:
        reason_codes.append("NO_RIVAL_HOLD")
        return ProbeStateResult(
            state="HOLD_OBSERVE",
            featured_outcome=outcome,
            learning_blocked=True,
            reason_codes=reason_codes,
        )

    if outcome == "NOT_OURS":
        reason_codes.append("FEATURED_NOT_OURS_REGAIN")
        return ProbeStateResult(
            state="REGAIN",
            featured_outcome=outcome,
            learning_blocked=False,
            reason_codes=reason_codes,
        )

    if highest_win is None or lowest_loss is None:
        reason_codes.append("MISSING_BOUND_RAISE_FIND_LOSS")
        return ProbeStateResult(
            state="RAISE_FIND_LOSS",
            featured_outcome=outcome,
            learning_blocked=False,
            reason_codes=reason_codes,
        )

    bracket_width = lowest_loss - highest_win
    if bracket_width > tolerance:
        reason_codes.append("BRACKET_WIDE_NARROW")
        return ProbeStateResult(
            state="BRACKET_NARROW",
            featured_outcome=outcome,
            learning_blocked=False,
            reason_codes=reason_codes,
        )

    reason_codes.append("BRACKET_TIGHT_STABLE")
    return ProbeStateResult(
        state="STABLE_WIN",
        featured_outcome=outcome,
        learning_blocked=False,
        reason_codes=reason_codes,
    )


def choose_next_price(
    *,
    state: str,
    current_price_gbp: object,
    hard_floor_gbp: object,
    final_ceiling_landed_gbp: object,
    max_step_down_gbp: object,
    max_step_up_gbp: object,
    max_daily_drop_gbp: object,
    daily_drop_used_gbp: object,
    highest_delta_win_effective_gbp: object,
    lowest_delta_loss_effective_gbp: object,
    best_rival_effective_price_gbp: object,
    stable_buffer_gbp: object,
    suppression_reactivation_target_landed_gbp: object = "",
    anchor_floor_gbp: object = "",
    suppression_threshold_estimate_gbp: object = "",
    suppression_threshold_upper_bound_gbp: object = "",
    seller_count: object = "",
    ladder_price_1_gbp: object = "",
    ladder_price_2_gbp: object = "",
    ladder_price_3_gbp: object = "",
    ladder_gap_buffer_gbp: object = "0.01",
) -> NextPriceDecision:
    reason_codes: List[str] = []
    chosen_state = str(state or "").strip().upper()
    current = _to_decimal(current_price_gbp) or Decimal("0")
    floor = _to_decimal(hard_floor_gbp) or Decimal("0")
    ceiling = _to_decimal(final_ceiling_landed_gbp)
    max_down = _to_decimal(max_step_down_gbp) or Decimal("0")
    max_up = _to_decimal(max_step_up_gbp) or Decimal("0")
    max_daily_drop = _to_decimal(max_daily_drop_gbp) or Decimal("0")
    drop_used = _to_decimal(daily_drop_used_gbp) or Decimal("0")
    highest_win = _to_decimal(highest_delta_win_effective_gbp)
    lowest_loss = _to_decimal(lowest_delta_loss_effective_gbp)
    best_rival = _to_decimal(best_rival_effective_price_gbp)
    stable_buffer = _to_decimal(stable_buffer_gbp) or Decimal("0.02")
    suppression_target = _to_decimal(suppression_reactivation_target_landed_gbp)
    anchor_floor = _to_decimal(anchor_floor_gbp)
    suppression_threshold = _to_decimal(suppression_threshold_estimate_gbp)
    suppression_upper_bound = _to_decimal(suppression_threshold_upper_bound_gbp)
    seller_count_num = _to_count(seller_count)
    ladder_price_1 = _to_decimal(ladder_price_1_gbp)
    ladder_price_2 = _to_decimal(ladder_price_2_gbp)
    ladder_price_3 = _to_decimal(ladder_price_3_gbp)
    ladder_gap_buffer = _to_decimal(ladder_gap_buffer_gbp) or Decimal("0.01")

    target = current
    write_required = False

    remaining_daily_drop = max(max_daily_drop - drop_used, Decimal("0"))

    def _allowed_downward_step(default_step: Decimal) -> Decimal:
        candidates = [d for d in (max_down, remaining_daily_drop) if d > 0]
        if candidates:
            return min(candidates)
        if default_step > 0:
            return default_step
        return Decimal("0")

    if ceiling is not None and ceiling < floor:
        reason_codes.append("FAIL_CEILING_BELOW_HARD_FLOOR")
        reason_codes.append("FLOOR_PRIORITY_CEILING_CONFLICT")
        if current != floor:
            reason_codes.append("FLOOR_PRIORITY_ENFORCED")
            return NextPriceDecision(
                state=chosen_state or "HOLD_OBSERVE",
                target_price_gbp=_to_money_string(floor),
                write_required=True,
                reason_codes=reason_codes,
            )
        reason_codes.append("FLOOR_PRIORITY_ALREADY_SAFE_NO_WRITE")
        return NextPriceDecision(
            state=chosen_state or "HOLD_OBSERVE",
            target_price_gbp=_to_money_string(current),
            write_required=False,
            reason_codes=reason_codes,
        )

    if chosen_state == "REGAIN":
        if best_rival is None:
            reason_codes.append("NO_RIVAL_HOLD")
            return NextPriceDecision(
                state=chosen_state,
                target_price_gbp=_to_money_string(current),
                write_required=False,
                reason_codes=reason_codes,
            )
        if seller_count_num >= 2 and ladder_price_2 is not None and ladder_price_2 > 0:
            ladder_target, _, ladder_source_codes = _ladder_cap_source(
                ladder_price_1=ladder_price_1,
                ladder_price_2=ladder_price_2,
                ladder_price_3=ladder_price_3,
                ladder_gap_buffer=ladder_gap_buffer,
                final_ceiling=ceiling,
            )
            if ladder_target is None:
                ladder_target = best_rival
                ladder_source_codes = []
            # Multi-seller ladders are capped to the next rung instead of blindly
            # chasing the absolute bottom every cycle. If the ladder cap is above
            # current, step upward toward that cap to reset bottom-chase pressure.
            target = current
            if ladder_target < current:
                target = ladder_target
            elif ladder_target > current and max_up > 0:
                target = min(current + max_up, ladder_target)
                if target > current:
                    reason_codes.append("STEP_REGAIN_MULTI_SELLER_RESET_UP")
            reason_codes.append("STEP_REGAIN_MULTI_SELLER_LADDER_CAP")
            reason_codes.append("TACTIC_MULTI_SELLER_LADDER_CAP")
            reason_codes.extend(ladder_source_codes)
            if target == current:
                reason_codes.append("REGAIN_MULTI_SELLER_NO_DOWNWARD_HEADROOM")
            if ladder_price_1 is not None and ladder_price_3 is not None:
                reason_codes.append("LADDER_DEPTH_THREE_PLUS")
        else:
            # Single-rival paths keep direct regain behavior.
            target = best_rival
            reason_codes.append("STEP_REGAIN_TO_RIVAL")
            reason_codes.append("TACTIC_SINGLE_RIVAL_RESET")
            if target == current and ceiling is not None and ceiling > current and max_up > 0:
                target = min(current + max_up, ceiling)
                reason_codes.append("SINGLE_RIVAL_RESET_DEADLOCK_BREAK")
                reason_codes.append("STEP_SINGLE_RIVAL_RESET_BREAK_UP")
        write_required = target != current
    elif chosen_state == "RAISE_FIND_LOSS":
        if ceiling is None:
            reason_codes.append("NO_CEILING_HOLD")
            return NextPriceDecision(
                state=chosen_state,
                target_price_gbp=_to_money_string(current),
                write_required=False,
                reason_codes=reason_codes,
            )
        if seller_count_num >= 2 and ladder_price_2 is not None and ladder_price_2 > 0:
            ladder_ceiling, _, ladder_source_codes = _ladder_cap_source(
                ladder_price_1=ladder_price_1,
                ladder_price_2=ladder_price_2,
                ladder_price_3=ladder_price_3,
                ladder_gap_buffer=ladder_gap_buffer,
                final_ceiling=ceiling,
            )
            effective_ceiling = ladder_ceiling if ladder_ceiling is not None else ceiling
            target = min(current + max_up, effective_ceiling)
            write_required = target > current
            reason_codes.append("STEP_RAISE_FIND_LOSS_LADDER_CAP")
            reason_codes.append("TACTIC_MULTI_SELLER_LADDER_CAP")
            reason_codes.extend(ladder_source_codes)
            if effective_ceiling < ceiling:
                reason_codes.append("RAISE_MULTI_SELLER_CEILING_CAPPED_TO_LADDER")
            if not write_required:
                reason_codes.append("RAISE_MULTI_SELLER_NO_HEADROOM")
        else:
            target = min(current + max_up, ceiling)
            write_required = target > current
            reason_codes.append("STEP_RAISE_FIND_LOSS_UP")
            reason_codes.append("TACTIC_SINGLE_RIVAL_RESET")
    elif chosen_state in {"MARGIN_COMPRESS_TO_FLOOR", "CONTROLLED_EXIT_TO_FLOOR", "LIQUIDATE_TO_FLOOR"}:
        if current <= floor:
            reason_codes.append("CANNOT_COMPETE_ALREADY_AT_ACTIVE_FLOOR")
            return NextPriceDecision(
                state=chosen_state,
                target_price_gbp=_to_money_string(current),
                write_required=False,
                reason_codes=reason_codes,
            )
        default_step = Decimal("0.20")
        if chosen_state == "CONTROLLED_EXIT_TO_FLOOR":
            default_step = Decimal("0.30")
        elif chosen_state == "LIQUIDATE_TO_FLOOR":
            default_step = Decimal("0.40")
        allowed_drop = _allowed_downward_step(default_step)
        if allowed_drop <= 0:
            reason_codes.append("CANNOT_COMPETE_DAILY_DROP_LIMIT_REACHED")
            return NextPriceDecision(
                state=chosen_state,
                target_price_gbp=_to_money_string(current),
                write_required=False,
                reason_codes=reason_codes,
            )
        target = current - allowed_drop
        write_required = target != current
        reason_codes.append("CANNOT_COMPETE_FLOOR_SEEK_STEP")
        if target < floor:
            target = floor
            reason_codes.append("CANNOT_COMPETE_ACTIVE_FLOOR_TARGET")
    elif chosen_state == "BRACKET_NARROW":
        if highest_win is None or lowest_loss is None or best_rival is None:
            reason_codes.append("BRACKET_INPUTS_MISSING_HOLD")
            return NextPriceDecision(
                state=chosen_state,
                target_price_gbp=_to_money_string(current),
                write_required=False,
                reason_codes=reason_codes,
            )
        midpoint_delta = (highest_win + lowest_loss) / Decimal("2")
        target = best_rival + midpoint_delta
        reason_codes.append("STEP_BRACKET_MIDPOINT")
    elif chosen_state == "STABLE_WIN":
        if highest_win is None or best_rival is None:
            reason_codes.append("STABLE_INPUTS_MISSING_HOLD")
            return NextPriceDecision(
                state=chosen_state,
                target_price_gbp=_to_money_string(current),
                write_required=False,
                reason_codes=reason_codes,
            )
        target = best_rival + highest_win - stable_buffer
        reason_codes.append("STEP_STABLE_BUFFER_BELOW_WIN")
    elif chosen_state == "STATE_SUPPRESSION_REACTIVATION":
        probe_floor_candidates = [d for d in (anchor_floor, floor) if d is not None and d > 0]
        probe_floor = max(probe_floor_candidates) if probe_floor_candidates else floor
        if suppression_target is not None:
            target = suppression_target
            write_required = target != current
            reason_codes.append("SUPPRESSION_DIRECT_TARGET")
            if not write_required:
                reason_codes.append("SUPPRESSION_DIRECT_TARGET_NO_MOVE")
                upward_caps = [d for d in (suppression_upper_bound, ceiling) if d is not None and d > current]
                upward_step = max(max_up, Decimal("0"))
                if upward_caps and upward_step > 0:
                    target = min(current + upward_step, min(upward_caps))
                    write_required = target != current
                    if write_required:
                        reason_codes.append("SUPPRESSION_DIRECT_TARGET_STALE")
                        reason_codes.append("SUPPRESSION_PROBE_UPWARD_STEP")
                if not write_required:
                    allowed_drop = _allowed_downward_step(Decimal("0.20"))
                    if allowed_drop > 0 and current > probe_floor:
                        target = current - allowed_drop
                        if target < probe_floor:
                            target = probe_floor
                            reason_codes.append("SUPPRESSION_PROBE_FLOOR_CLAMP")
                        write_required = target != current
                        if write_required:
                            reason_codes.append("SUPPRESSION_DIRECT_TARGET_STALE")
                            reason_codes.append("SUPPRESSION_PROBE_DOWNWARD_STEP")
        elif suppression_threshold is not None and suppression_threshold > 0:
            target = suppression_threshold
            write_required = target != current
            reason_codes.append("SUPPRESSION_PROBE_THRESHOLD_ESTIMATE")
        else:
            if suppression_upper_bound is not None and suppression_upper_bound > 0 and current > suppression_upper_bound:
                target = suppression_upper_bound
                write_required = target != current
                reason_codes.append("SUPPRESSION_PROBE_START_FROM_INFERRED_UPPER_BOUND")
            else:
                allowed_drop = _allowed_downward_step(Decimal("0.20"))
                target = current - allowed_drop
                if target < probe_floor:
                    target = probe_floor
                    reason_codes.append("SUPPRESSION_PROBE_FLOOR_CLAMP")
                write_required = target != current
                reason_codes.append("SUPPRESSION_PROBE_DOWNWARD_STEP")
    else:
        reason_codes.append("STATE_HOLD_NO_WRITE")
        return NextPriceDecision(
            state=chosen_state or "HOLD_OBSERVE",
            target_price_gbp=_to_money_string(current),
            write_required=False,
            reason_codes=reason_codes,
        )

    if target < floor:
        target = floor
        reason_codes.append("GUARDRAIL_HARD_FLOOR_CLAMP")
    if chosen_state == "STATE_SUPPRESSION_REACTIVATION" and anchor_floor is not None and target < anchor_floor:
        target = anchor_floor
        reason_codes.append("GUARDRAIL_ANCHOR_FLOOR_CLAMP")
    if ceiling is not None and target > ceiling:
        target = ceiling
        reason_codes.append("GUARDRAIL_FINAL_CEILING_CLAMP")

    if chosen_state == "REGAIN" and seller_count_num >= 2 and target == current:
        if "REGAIN_MULTI_SELLER_NO_DOWNWARD_HEADROOM" not in reason_codes:
            reason_codes.append("REGAIN_MULTI_SELLER_NO_DOWNWARD_HEADROOM")
    if chosen_state == "RAISE_FIND_LOSS" and seller_count_num >= 2 and target == current:
        if "RAISE_MULTI_SELLER_NO_HEADROOM" not in reason_codes:
            reason_codes.append("RAISE_MULTI_SELLER_NO_HEADROOM")

    # Final write intent must follow the post-guardrail target, not the pre-clamp
    # target candidate, otherwise no-op writes can be emitted as APPLIED.
    write_required = target != current
    return NextPriceDecision(
        state=chosen_state,
        target_price_gbp=_to_money_string(target),
        write_required=write_required,
        reason_codes=reason_codes,
    )


def update_suppression_memory(
    *,
    current_memory: Mapping[str, object],
    observed_price_gbp: object,
    buy_box_state: object,
    buy_box_eligible_offers: object,
    direct_target_gbp: object,
    anchor_floor_gbp: object,
    now_utc: object,
    update_allowed_flag: object = "1",
) -> SuppressionMemoryUpdateResult:
    reason_codes: List[str] = []
    highest_eligible = _to_decimal(current_memory.get("highest_eligible_price"))
    lowest_ineligible = _to_decimal(current_memory.get("lowest_ineligible_price"))
    threshold_estimate = _to_decimal(current_memory.get("suppression_threshold_estimate"))
    anchor_floor = _to_decimal(anchor_floor_gbp)
    observed_price = _to_decimal(observed_price_gbp)
    direct_target = _to_decimal(direct_target_gbp)
    state = str(buy_box_state or "").strip().upper()
    eligible_count = _to_count(buy_box_eligible_offers)
    update_allowed = str(update_allowed_flag or "").strip() in {"1", "true", "True", "TRUE"}
    last_validated = str(current_memory.get("suppression_last_validated_utc") or "").strip()

    if not update_allowed:
        reason_codes.append("SUPPRESSION_MEMORY_UPDATE_BLOCKED")
        confidence = _to_confidence(Decimal("0")) if threshold_estimate is None else str(current_memory.get("suppression_threshold_confidence") or "0")
        return SuppressionMemoryUpdateResult(
            highest_eligible_price=_to_money_string(highest_eligible),
            lowest_ineligible_price=_to_money_string(lowest_ineligible),
            suppression_threshold_estimate=_to_money_string(threshold_estimate),
            suppression_threshold_confidence=confidence,
            suppression_last_validated_utc=last_validated,
            learning_updated=False,
            reason_codes=reason_codes,
        )

    learning_updated = False
    if state in {"SUPPRESSED_ASIN", "DISQUALIFIED_SELF_PRICE"} and observed_price is not None:
        lowest_ineligible = observed_price if lowest_ineligible is None else min(lowest_ineligible, observed_price)
        learning_updated = True
        reason_codes.append("SUPPRESSION_LOWEST_INELIGIBLE_UPDATED")
    elif state in {"NORMAL", "LOST_TO_COMPETITOR"} and eligible_count > 0 and observed_price is not None:
        highest_eligible = observed_price if highest_eligible is None else max(highest_eligible, observed_price)
        last_validated = str(now_utc or "").strip()
        learning_updated = True
        reason_codes.append("SUPPRESSION_HIGHEST_ELIGIBLE_UPDATED")

    if direct_target is not None and direct_target > 0:
        threshold_estimate = direct_target
        last_validated = str(now_utc or "").strip()
        learning_updated = True
        reason_codes.append("SUPPRESSION_DIRECT_TARGET_PERSISTED")

    if anchor_floor is not None and threshold_estimate is not None and threshold_estimate < anchor_floor:
        threshold_estimate = anchor_floor
        reason_codes.append("SUPPRESSION_THRESHOLD_CLAMPED_TO_ANCHOR_FLOOR")

    if highest_eligible is not None and lowest_ineligible is not None:
        threshold_estimate = (highest_eligible + lowest_ineligible) / Decimal("2")
        reason_codes.append("SUPPRESSION_THRESHOLD_BRACKET_ESTIMATE")
        confidence = Decimal("0.8")
    elif threshold_estimate is not None:
        confidence = Decimal("0.6") if direct_target is not None and direct_target > 0 else Decimal("0.4")
    elif highest_eligible is not None:
        threshold_estimate = highest_eligible
        confidence = Decimal("0.5")
        reason_codes.append("SUPPRESSION_THRESHOLD_FROM_HIGHEST_ELIGIBLE")
    else:
        confidence = Decimal("0")

    if anchor_floor is not None and threshold_estimate is not None and threshold_estimate < anchor_floor:
        threshold_estimate = anchor_floor
        reason_codes.append("SUPPRESSION_THRESHOLD_RECLAMPED_TO_ANCHOR_FLOOR")

    return SuppressionMemoryUpdateResult(
        highest_eligible_price=_to_money_string(highest_eligible),
        lowest_ineligible_price=_to_money_string(lowest_ineligible),
        suppression_threshold_estimate=_to_money_string(threshold_estimate),
        suppression_threshold_confidence=_to_confidence(confidence),
        suppression_last_validated_utc=last_validated,
        learning_updated=learning_updated,
        reason_codes=reason_codes,
    )


def update_delta_memory(
    *,
    current_memory: Mapping[str, object],
    observed_delta_effective_gbp: object,
    observed_outcome: object,
    oas_admissible_flag: object,
    now_utc: object,
    min_clean_tests_for_confidence: int = 5,
) -> DeltaMemoryUpdateResult:
    reason_codes: List[str] = []
    highest_win = _to_decimal(current_memory.get("highest_delta_win_effective_gbp"))
    lowest_loss = _to_decimal(current_memory.get("lowest_delta_loss_effective_gbp"))
    valid_tests = _to_count(current_memory.get("valid_test_count"))
    contaminated_tests = _to_count(current_memory.get("contaminated_test_count"))
    last_valid = str(current_memory.get("last_valid_test_utc") or "").strip()

    observed_delta = _to_decimal(observed_delta_effective_gbp)
    outcome = str(observed_outcome or "").strip().upper()
    admissible = str(oas_admissible_flag or "").strip() in {"1", "TRUE", "True", "true"}

    if not admissible or observed_delta is None or outcome not in {"WIN", "LOSS"}:
        contaminated_tests += 1
        reason_codes.append("LEARNING_BLOCKED_OR_CONTAMINATED")
    else:
        valid_tests += 1
        last_valid = str(now_utc or "").strip()
        if outcome == "WIN":
            highest_win = observed_delta if highest_win is None else max(highest_win, observed_delta)
            reason_codes.append("BOUND_WIN_UPDATED")
        else:
            lowest_loss = observed_delta if lowest_loss is None else min(lowest_loss, observed_delta)
            reason_codes.append("BOUND_LOSS_UPDATED")

    learned_delta: Decimal | None = None
    if highest_win is not None and lowest_loss is not None:
        learned_delta = (highest_win + lowest_loss) / Decimal("2")
    elif highest_win is not None:
        learned_delta = highest_win
    elif lowest_loss is not None:
        learned_delta = lowest_loss

    confidence = Decimal(valid_tests) / Decimal(max(min_clean_tests_for_confidence, 1))
    if confidence > Decimal("1"):
        confidence = Decimal("1")

    learning_updated = "BOUND_WIN_UPDATED" in reason_codes or "BOUND_LOSS_UPDATED" in reason_codes

    return DeltaMemoryUpdateResult(
        learned_delta_effective_gbp=_to_money_string(learned_delta),
        highest_delta_win_effective_gbp=_to_money_string(highest_win),
        lowest_delta_loss_effective_gbp=_to_money_string(lowest_loss),
        delta_confidence=_to_confidence(confidence),
        valid_test_count=str(valid_tests),
        contaminated_test_count=str(contaminated_tests),
        last_valid_test_utc=last_valid,
        learning_updated=learning_updated,
        reason_codes=reason_codes,
    )

