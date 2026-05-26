from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.core.runtime_owner_contract import (
    REQUIRED_FLOWS,
    load_and_validate_runtime_owner_contract,
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_runtime_owner_contract_loads() -> None:
    contract = load_and_validate_runtime_owner_contract()
    assert isinstance(contract, dict)
    assert "flows" in contract


def test_owner_contract_has_one_owner_per_flow() -> None:
    contract = load_and_validate_runtime_owner_contract()
    flows = contract["flows"]
    owners = []
    for flow in REQUIRED_FLOWS:
        payload = flows[flow]
        owner = str(payload.get("runtime_owner", "")).strip()
        assert owner, f"runtime_owner missing for flow {flow}"
        owners.append((flow, owner))
    assert len(owners) == len(REQUIRED_FLOWS)


def test_b_single_owner_chain() -> None:
    contract = load_and_validate_runtime_owner_contract()
    b = contract["flows"]["B"]
    assert b["launcher_entrypoint"] == "run_B_cycle.bat"
    assert b["runtime_owner"] == "scripts/cycles/run_B_supervisor.py"
    assert b["worker_entrypoint"] == "scripts/cycles/run_B_cycle.py"
    assert b["owner_chain"] == [
        "run_B_cycle.bat",
        "scripts/cycles/run_B_supervisor.py",
        "scripts/cycles/run_B_cycle.py",
    ]
    assert b["allow_direct_worker_start"] is False


def test_h_single_owner_chain() -> None:
    contract = load_and_validate_runtime_owner_contract()
    h = contract["flows"]["H"]
    assert h["launcher_entrypoint"] == "run_H_cycle.bat"
    assert h["runtime_owner"] == "scripts/cycles/run_H_pricing_cycle_guarded.py"
    assert h["worker_entrypoint"] == "scripts/cycles/run_H_pricing_cycle.py"
    assert h["owner_chain"] == [
        "run_H_cycle.bat",
        "scripts/cycles/run_H_pricing_cycle_guarded.py",
        "scripts/cycles/run_H_pricing_cycle.py",
    ]
    assert h["allow_direct_worker_start"] is False


def test_no_direct_worker_scheduler_targets() -> None:
    run_b_bat = _read_text(ROOT / "run_B_cycle.bat")
    run_h_bat = _read_text(ROOT / "run_H_cycle.bat")
    run_a_all = _read_text(ROOT / "scripts" / "cycles" / "run_A_all.py")

    assert "run_B_supervisor.py" in run_b_bat
    assert "run_H_pricing_cycle_guarded.py" in run_h_bat
    assert "H_ALLOW_DIRECT_WORKER_START" in run_h_bat
    assert "direct_core_blocked" in run_h_bat
    assert "run_B_cycle.bat" in run_a_all
