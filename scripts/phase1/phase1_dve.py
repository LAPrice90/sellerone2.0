from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, Iterable, List, Mapping, Sequence


DEFAULT_PENALTY_BY_GAP_DAYS: tuple[Decimal, ...] = (
    Decimal("0.00"),
    Decimal("0.15"),
    Decimal("0.30"),
    Decimal("0.45"),
    Decimal("0.60"),
)


@dataclass(frozen=True)
class DveComputationResult:
    rows: List[Dict[str, str]]
    fastest_delivery_days: int | None
    penalty_curve_version: str
    delivery_penalty_unknown_flag: bool


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


def _to_int(value: object) -> int | None:
    dec = _to_decimal(value)
    if dec is None:
        return None
    try:
        return int(dec)
    except (ValueError, OverflowError):
        return None


def _to_money_string(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"{value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


def penalty_for_gap_days(
    delivery_gap_days: int,
    penalty_by_gap_days: Sequence[float | Decimal] = DEFAULT_PENALTY_BY_GAP_DAYS,
) -> Decimal:
    if not penalty_by_gap_days:
        raise ValueError("penalty_by_gap_days must not be empty")
    curve: List[Decimal] = [Decimal(str(v)) for v in penalty_by_gap_days]
    gap = max(0, int(delivery_gap_days))
    idx = min(gap, len(curve) - 1)
    return curve[idx]


def compute_effective_price(
    landed_price_gbp: float | Decimal,
    delivery_gap_days: int,
    penalty_by_gap_days: Sequence[float | Decimal] = DEFAULT_PENALTY_BY_GAP_DAYS,
) -> Decimal:
    landed = Decimal(str(landed_price_gbp))
    return landed + penalty_for_gap_days(delivery_gap_days, penalty_by_gap_days=penalty_by_gap_days)


def apply_dve_v0(
    snapshot_rows: Iterable[Mapping[str, object]],
    penalty_by_gap_days: Sequence[float | Decimal] = DEFAULT_PENALTY_BY_GAP_DAYS,
) -> DveComputationResult:
    source_rows = [dict(row) for row in snapshot_rows]
    if not source_rows:
        return DveComputationResult(
            rows=[],
            fastest_delivery_days=None,
            penalty_curve_version="v0",
            delivery_penalty_unknown_flag=True,
        )

    min_days_candidates: List[int] = []
    for row in source_rows:
        day_value = _to_int(row.get("min_delivery_days"))
        if day_value is not None and day_value >= 0:
            min_days_candidates.append(day_value)

    if min_days_candidates:
        fastest = min(min_days_candidates)
        unknown_penalty = False
    else:
        fastest = None
        unknown_penalty = True

    out_rows: List[Dict[str, str]] = []
    for row in source_rows:
        out_row: Dict[str, str] = {str(k): str(v) if v is not None else "" for k, v in row.items()}
        landed = _to_decimal(row.get("landed_price_gbp"))
        this_min_days = _to_int(row.get("min_delivery_days"))

        if fastest is None or this_min_days is None or this_min_days < 0:
            out_row["delivery_gap_days"] = ""
            out_row["delivery_penalty_gbp"] = ""
            out_row["effective_price_gbp"] = _to_money_string(landed)
            out_rows.append(out_row)
            continue

        gap = max(0, this_min_days - fastest)
        penalty = penalty_for_gap_days(gap, penalty_by_gap_days=penalty_by_gap_days)
        out_row["delivery_gap_days"] = str(gap)
        out_row["delivery_penalty_gbp"] = _to_money_string(penalty)
        out_row["effective_price_gbp"] = _to_money_string(landed + penalty if landed is not None else None)
        out_rows.append(out_row)

    return DveComputationResult(
        rows=out_rows,
        fastest_delivery_days=fastest,
        penalty_curve_version="v0",
        delivery_penalty_unknown_flag=unknown_penalty,
    )

