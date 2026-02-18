from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd

HEAD_BOUNDARIES_PATH = Path("config/h_head_boundaries.csv")
REQUIRED_COLUMNS = [
    "sku",
    "lane",
    "enabled",
    "effective_utc",
    "expiry_utc",
    "hard_floor_gbp",
    "ceiling_gbp",
    "max_move_per_cycle_gbp",
    "max_daily_down_move_gbp",
    "cooldown_minutes",
    "max_probes_per_day",
    "max_active_probe_skus",
    "note",
]


def load_head_boundaries(path: Path | None = None) -> pd.DataFrame:
    target = path or HEAD_BOUNDARIES_PATH
    if not target.exists():
        print(f"[head_boundaries] WARN missing head boundary file: {target}")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    try:
        df = pd.read_csv(target, dtype=str).fillna("")
    except Exception as exc:
        print(f"[head_boundaries] WARN failed to read head boundary file: {exc}")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        print(f"[head_boundaries] WARN head boundary file missing columns: {','.join(missing)}")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    return df


def load_active_head_boundary_skus(path: Path | None = None) -> List[str]:
    df = load_head_boundaries(path)
    if df.empty:
        return []
    enabled = df.get("enabled", "").astype(str).str.strip().str.lower()
    is_enabled = enabled.isin(["yes", "y", "1", "true"])
    skus = df.loc[is_enabled, "sku"].astype(str).str.strip().str.upper()
    return [s for s in skus.tolist() if s]
