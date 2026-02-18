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
) -> ProbeStateResult:
    reason_codes: List[str] = []
    outcome = str(featured_outcome or "").strip().upper()
    highest_win = _to_decimal(highest_delta_win_effective_gbp)
    lowest_loss = _to_decimal(lowest_delta_loss_effective_gbp)
    tolerance = _to_decimal(delta_tolerance_gbp) or Decimal("0.02")

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

    target = current
    write_required = False

    if ceiling is not None and ceiling < floor:
        reason_codes.append("FAIL_CEILING_BELOW_HARD_FLOOR")
        reason_codes.append("FLOOR_PRIORITY_CEILING_CONFLICT")
        if current < floor:
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
        # REGAIN no longer stair-steps down by fixed caps; move directly to rival target,
        # then let floor/ceiling guardrails clamp as needed.
        target = best_rival
        write_required = target != current
        reason_codes.append("STEP_REGAIN_TO_RIVAL")
    elif chosen_state == "RAISE_FIND_LOSS":
        if ceiling is None:
            reason_codes.append("NO_CEILING_HOLD")
            return NextPriceDecision(
                state=chosen_state,
                target_price_gbp=_to_money_string(current),
                write_required=False,
                reason_codes=reason_codes,
            )
        target = min(current + max_up, ceiling)
        write_required = target > current
        reason_codes.append("STEP_RAISE_FIND_LOSS_UP")
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
    if ceiling is not None and target > ceiling:
        target = ceiling
        reason_codes.append("GUARDRAIL_FINAL_CEILING_CLAMP")

    write_required = write_required or (target != current)
    return NextPriceDecision(
        state=chosen_state,
        target_price_gbp=_to_money_string(target),
        write_required=write_required,
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
