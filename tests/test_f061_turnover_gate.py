from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.legacy_scanner_2_1.turnover_gate import (  # noqa: E402
    build_turnover_profit_history,
    evaluate_turnover_gate,
)


def test_build_turnover_profit_history_scales_to_current_units() -> None:
    history = build_turnover_profit_history(
        bbp_sales_history=[100, 90, 80],
        bbp_units_reference=100,
        chosen_units=120,
        profit_per_unit=1.5,
    )
    assert history == [180.0, 162.0, 144.0]


def test_evaluate_turnover_gate_passes_strong_history() -> None:
    result = evaluate_turnover_gate(
        monthly_profit_history=[120.0, 100.0, 90.0, 85.0, 75.0, 70.0],
        monthly_profit_threshold=20.0,
    )
    assert result["recommendation"] == "PASS"
    assert result["fail_code"] == ""
    assert result["score"] >= 75


def test_evaluate_turnover_gate_fails_when_current_month_below_threshold() -> None:
    result = evaluate_turnover_gate(
        monthly_profit_history=[8.0, 24.0, 26.0, 28.0],
        monthly_profit_threshold=20.0,
    )
    assert result["recommendation"] == "FAIL"
    assert result["fail_code"] == "TURNOVERFAIL_CURRENT"
