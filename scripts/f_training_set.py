from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd

TRAINING_SET_PATH = Path("config/f_training_set.csv")
REQUIRED_COLUMNS = ["sku", "asin", "marketplace", "notes", "enabled"]


def load_training_set(path: Path | None = None) -> pd.DataFrame:
    target = path or TRAINING_SET_PATH
    if not target.exists():
        print(f"[training_set] WARN missing training set file: {target}")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    try:
        df = pd.read_csv(target, dtype=str).fillna("")
    except Exception as exc:
        print(f"[training_set] WARN failed to read training set: {exc}")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        print(f"[training_set] WARN training set missing columns: {','.join(missing)}")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    return df


def load_enabled_training_skus(path: Path | None = None) -> List[str]:
    df = load_training_set(path)
    if df.empty:
        return []
    enabled = df.get("enabled", "").astype(str).str.strip().str.lower()
    is_enabled = enabled.isin(["yes", "y", "1", "true"])
    skus = df.loc[is_enabled, "sku"].astype(str).str.strip()
    return [s for s in skus.tolist() if s]
