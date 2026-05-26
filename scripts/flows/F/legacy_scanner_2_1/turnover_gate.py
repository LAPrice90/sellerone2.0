import statistics


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value, default=0):
    try:
        if value is None:
            return default
        return int(round(float(value)))
    except Exception:
        return default


def _mean(values):
    cleaned = [float(v) for v in values if _safe_float(v, 0.0) >= 0]
    if not cleaned:
        return 0.0
    return float(statistics.mean(cleaned))


def _component_score(actual, required):
    req = max(_safe_float(required, 0.0), 0.01)
    ratio = max(0.0, _safe_float(actual, 0.0) / req)
    return min(100.0, ratio * 100.0)


def build_turnover_profit_history(
    bbp_sales_history,
    bbp_units_reference,
    chosen_units,
    profit_per_unit,
    max_months=12,
):
    """
    Build monthly profit history (newest first), scaled to the current chosen unit logic.
    """
    ppu = max(0.0, _safe_float(profit_per_unit, 0.0))
    if ppu <= 0:
        return []

    history = []
    for val in (bbp_sales_history or []):
        qty = max(0, _safe_int(val, 0))
        if qty > 0:
            history.append(qty)
        if len(history) >= max_months:
            break

    units_ref = max(0, _safe_int(bbp_units_reference, 0))
    chosen = max(0, _safe_int(chosen_units, 0))

    if not history:
        if chosen <= 0 and units_ref <= 0:
            return []
        baseline = chosen if chosen > 0 else units_ref
        return [round(baseline * ppu, 2)]

    scale = 1.0
    if units_ref > 0 and chosen > 0:
        scale = chosen / float(units_ref)

    scaled_history = [max(0, int(round(q * scale))) for q in history]
    if chosen > 0:
        scaled_history[0] = chosen

    return [round(q * ppu, 2) for q in scaled_history]


def evaluate_turnover_gate(
    monthly_profit_history,
    monthly_profit_threshold=20.0,
    current_multiplier=1.0,
    short_multiplier=0.9,
    medium_multiplier=0.65,
    long_multiplier=0.5,
):
    """
    Evaluate turnover history with stricter short-term checks and softer long-term checks.
    """
    profits = [max(0.0, _safe_float(v, 0.0)) for v in (monthly_profit_history or [])]
    threshold = max(_safe_float(monthly_profit_threshold, 20.0), 1.0)

    current_profit = profits[0] if profits else 0.0
    short_window = profits[:3]
    medium_window = profits[:6]
    long_window = profits[:12]

    short_avg = _mean(short_window)
    medium_avg = _mean(medium_window)
    long_avg = _mean(long_window)

    current_required = threshold * max(_safe_float(current_multiplier, 1.0), 0.1)
    short_required = threshold * max(_safe_float(short_multiplier, 0.9), 0.1)
    medium_required = threshold * max(_safe_float(medium_multiplier, 0.65), 0.1)
    long_required = threshold * max(_safe_float(long_multiplier, 0.5), 0.1)

    fail_code = ""
    fail_reason = ""

    if current_profit < current_required:
        fail_code = "TURNOVERFAIL_CURRENT"
        fail_reason = f"current_month_profit={current_profit:.2f} below required={current_required:.2f}"
    elif len(short_window) >= 2 and short_avg < short_required:
        fail_code = "TURNOVERFAIL_SHORT"
        fail_reason = f"short_avg_profit={short_avg:.2f} below required={short_required:.2f}"
    elif len(medium_window) >= 4 and medium_avg < medium_required:
        fail_code = "TURNOVERFAIL_MEDIUM"
        fail_reason = f"medium_avg_profit={medium_avg:.2f} below required={medium_required:.2f}"
    elif len(long_window) >= 8 and long_avg < long_required:
        fail_code = "TURNOVERFAIL_LONG"
        fail_reason = f"long_avg_profit={long_avg:.2f} below required={long_required:.2f}"

    score_parts = []
    score_weights = []

    score_parts.append(_component_score(current_profit, current_required))
    score_weights.append(0.50)

    if len(short_window) >= 2:
        score_parts.append(_component_score(short_avg, short_required))
        score_weights.append(0.25)
    if len(medium_window) >= 4:
        score_parts.append(_component_score(medium_avg, medium_required))
        score_weights.append(0.15)
    if len(long_window) >= 8:
        score_parts.append(_component_score(long_avg, long_required))
        score_weights.append(0.10)

    if score_weights:
        weighted_score = sum(s * w for s, w in zip(score_parts, score_weights)) / sum(score_weights)
    else:
        weighted_score = 0.0

    if fail_code:
        recommendation = "FAIL"
    elif weighted_score >= 75:
        recommendation = "PASS"
    elif weighted_score >= 55:
        recommendation = "REVIEW"
    else:
        recommendation = "FAIL"

    return {
        "history_months": len(profits),
        "current_month_profit": round(current_profit, 2),
        "short_avg_profit": round(short_avg, 2),
        "medium_avg_profit": round(medium_avg, 2),
        "long_avg_profit": round(long_avg, 2),
        "score": int(round(weighted_score)),
        "recommendation": recommendation,
        "fail_code": fail_code,
        "fail_reason": fail_reason,
        "required_current": round(current_required, 2),
        "required_short": round(short_required, 2),
        "required_medium": round(medium_required, 2),
        "required_long": round(long_required, 2),
    }
