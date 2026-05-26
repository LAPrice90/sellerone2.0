from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.core.flow_health_gate import flow_gate_checklist_path
from scripts.cycles import run_A_all as a_cycle
from scripts.cycles import run_B_cycle as b_cycle
from scripts.cycles import run_E_cycle as e_cycle
from scripts.cycles import run_H_pricing_cycle as h_cycle


def test_flow_gate_defaults() -> None:
    assert flow_gate_checklist_path("A").as_posix().endswith("out/cycle_alerts/checklist_A_split.csv")
    assert flow_gate_checklist_path("B").as_posix().endswith("out/cycle_alerts/checklist_B.csv")
    assert flow_gate_checklist_path("E").as_posix().endswith("out/cycle_alerts/checklist_E_split.csv")
    assert flow_gate_checklist_path("H").as_posix().endswith("out/cycle_alerts/checklist_H.csv")


def test_flow_gate_legacy_env_override_for_b() -> None:
    old = os.environ.get("HEALTH_CHECKLIST_B_PATH")
    try:
        os.environ["HEALTH_CHECKLIST_B_PATH"] = str(ROOT / "out" / "tmp_b_gate.csv")
        assert flow_gate_checklist_path("B") == Path(os.environ["HEALTH_CHECKLIST_B_PATH"])
    finally:
        if old is None:
            os.environ.pop("HEALTH_CHECKLIST_B_PATH", None)
        else:
            os.environ["HEALTH_CHECKLIST_B_PATH"] = old


def test_b_cycle_uses_flow_gate_path_for_manifest() -> None:
    text = (ROOT / "scripts" / "cycles" / "run_B_cycle.py").read_text(encoding="utf-8", errors="replace")
    assert "B_GATE_CHECKLIST_PATH = flow_gate_checklist_path(\"B\")" in text
    assert "health_checklist_path=B_GATE_CHECKLIST_PATH" in text


def test_flow_owned_health_gate_selection() -> None:
    assert a_cycle.A_SPLIT_CHECKLIST_PATH == flow_gate_checklist_path("A")
    assert b_cycle.B_GATE_CHECKLIST_PATH == flow_gate_checklist_path("B")
    assert e_cycle.E_SPLIT_CHECKLIST_PATH == flow_gate_checklist_path("E")
    assert h_cycle.H_PRIMARY_CHECKLIST_PATH == flow_gate_checklist_path("H")


def test_global_health_not_used_as_flow_gate() -> None:
    a_text = (ROOT / "scripts" / "cycles" / "run_A_all.py").read_text(encoding="utf-8", errors="replace")
    b_text = (ROOT / "scripts" / "cycles" / "run_B_cycle.py").read_text(encoding="utf-8", errors="replace")
    h_text = (ROOT / "scripts" / "cycles" / "run_H_pricing_cycle.py").read_text(encoding="utf-8", errors="replace")

    assert "global observability rc=" in a_text
    assert "required_outputs=[str(A_SPLIT_CHECKLIST_PATH)]" in a_text
    assert "_health_snapshot_counts(path: Path | None = None)" in b_text
    assert "gate_path = path or B_GATE_CHECKLIST_PATH" in b_text
    assert "flow_gate_primary_h" in h_text
    assert "\"A003_run_inventory_to_sheet.py\"" in a_text


def test_gate_freshness_uses_flow_scope_first() -> None:
    path, source = h_cycle._choose_h_gate_checklist_path()
    assert path == h_cycle.H_PRIMARY_CHECKLIST_PATH
    assert source in {"flow_gate_primary_h", "flow_gate_primary_h_missing"}


def test_cycle_step_artifacts_match_current_output_paths() -> None:
    assert b_cycle.STEP_ARTIFACTS["B001_run_orders_to_sheet.py"] == [
        "out/orders_all.csv",
        "out/order_items_all.csv",
    ]
    assert b_cycle.STEP_ARTIFACTS["B002_run_pending_orders_to_sheet.py"] == [
        "out/orders_pending_raw.csv",
        "out/order_items_pending_raw.csv",
    ]
    assert b_cycle.STEP_ARTIFACTS["B006_build_fx_ledgers.py"] == [
        "out/order_ledger_fx.csv",
        "out/financial_ledger_fx.csv",
        "out/fx_rates_daily.csv",
    ]
    assert h_cycle.STEP_ARTIFACTS["resolve_h_split_gate"] == ["out/cycle_alerts/checklist_H.csv"]
