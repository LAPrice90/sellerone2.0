from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

_FLOW_GATE_DEFAULTS = {
    "A": ROOT / "out" / "cycle_alerts" / "checklist_A_split.csv",
    "B": ROOT / "out" / "cycle_alerts" / "checklist_B.csv",
    "E": ROOT / "out" / "cycle_alerts" / "checklist_E_split.csv",
    "H": ROOT / "out" / "cycle_alerts" / "checklist_H.csv",
}

_FLOW_GATE_ENV_KEYS = {
    "A": "A_GATE_CHECKLIST_PATH",
    "B": "B_GATE_CHECKLIST_PATH",
    "E": "E_GATE_CHECKLIST_PATH",
    "H": "H_GATE_CHECKLIST_PATH",
}
_FLOW_GATE_LEGACY_ENV_KEYS = {
    "A": "A_SPLIT_CHECKLIST_PATH",
    "B": "HEALTH_CHECKLIST_B_PATH",
    "E": "E_SPLIT_CHECKLIST_PATH",
    "H": "H_PRIMARY_CHECKLIST_PATH",
}


def flow_gate_checklist_path(flow: str) -> Path:
    flow_key = str(flow or "").strip().upper()
    if flow_key not in _FLOW_GATE_DEFAULTS:
        raise ValueError(f"unsupported flow key: {flow_key}")
    env_key = _FLOW_GATE_ENV_KEYS[flow_key]
    env_value = str(os.environ.get(env_key, "")).strip()
    if env_value:
        return Path(env_value)
    legacy_env_key = _FLOW_GATE_LEGACY_ENV_KEYS[flow_key]
    legacy_env_value = str(os.environ.get(legacy_env_key, "")).strip()
    if legacy_env_value:
        return Path(legacy_env_value)
    return _FLOW_GATE_DEFAULTS[flow_key]
