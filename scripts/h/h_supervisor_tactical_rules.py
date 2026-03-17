from __future__ import annotations

from pathlib import Path

import pandas as pd

SUPERVISOR_TACTICAL_RULES_PATH = Path("config/h_supervisor_tactical_rules.csv")
REQUIRED_COLUMNS = [
    "sku",
    "lane",
    "state",
    "trigger_code",
    "allowed_probe_type",
    "target_adjustment_gbp",
    "cooldown_minutes",
    "expiry_minutes",
    "priority",
    "enabled",
    "stop_condition",
    "escalation_action",
    "note",
]


def load_supervisor_tactical_rules(path: Path | None = None) -> pd.DataFrame:
    target = path or SUPERVISOR_TACTICAL_RULES_PATH
    if not target.exists():
        print(f"[supervisor_tactical_rules] WARN missing file: {target}")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    try:
        df = pd.read_csv(target, dtype=str).fillna("")
    except Exception as exc:
        print(f"[supervisor_tactical_rules] WARN failed to read file: {exc}")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        print(f"[supervisor_tactical_rules] WARN missing columns: {','.join(missing)}")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    return df


def load_active_supervisor_tactical_rules(path: Path | None = None) -> pd.DataFrame:
    df = load_supervisor_tactical_rules(path)
    if df.empty:
        return df
    enabled = df.get("enabled", "").astype(str).str.strip().str.lower()
    is_enabled = enabled.isin(["yes", "y", "1", "true"])
    return df.loc[is_enabled].copy()

