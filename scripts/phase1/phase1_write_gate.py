from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


ALLOWED_REASON = "PHASE_LIVE_WRITE_ALLOWED"
BLOCKED_PREFIX = "PHASE_LIVE_WRITE_BLOCKED_"


@dataclass(frozen=True)
class LiveWriteGateResult:
    write_allowed: bool
    reason_codes: list[str]


def evaluate_live_write_gate(
    *,
    writer_mode: str,
    phase_engine_enabled: bool,
    phase_engine_behavior: bool,
    phase_engine_live_writes: bool,
    in_cohort: bool,
    excluded: bool,
) -> LiveWriteGateResult:
    mode = str(writer_mode or "").strip().upper()
    reason = "PHASE_LIVE_WRITE_BLOCKED_FLAG_OFF"
    allowed = False
    if mode != "CODEX_H":
        reason = "PHASE_LIVE_WRITE_BLOCKED_WRITER_MODE"
    elif excluded:
        reason = "PHASE_LIVE_WRITE_BLOCKED_EXCLUDED"
    elif phase_engine_live_writes:
        if not phase_engine_enabled or not phase_engine_behavior:
            reason = "PHASE_LIVE_WRITE_BLOCKED_FLAG_OFF"
        elif not in_cohort:
            reason = "PHASE_LIVE_WRITE_BLOCKED_NOT_IN_COHORT"
        else:
            reason = ALLOWED_REASON
            allowed = True
    else:
        reason = ALLOWED_REASON
        allowed = True
    return LiveWriteGateResult(write_allowed=allowed, reason_codes=[reason])


def live_write_allowed_from_reason_codes(
    reason_codes: Iterable[str],
    *,
    fallback_write_effective: bool = False,
    fallback_writer_mode: str = "",
) -> bool:
    codes = {str(code or "").strip().upper() for code in reason_codes if str(code or "").strip()}
    if ALLOWED_REASON in codes:
        return True
    if any(code.startswith(BLOCKED_PREFIX) for code in codes):
        return False
    return bool(fallback_write_effective) or str(fallback_writer_mode or "").strip().upper() == "CODEX_H"
