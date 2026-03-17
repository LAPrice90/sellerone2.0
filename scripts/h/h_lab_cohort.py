from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd

LAB_COHORT_PATH = Path("config/h_lab_cohort.csv")
REQUIRED_COLUMNS = ["sku", "lane", "enabled", "effective_utc", "note"]


def load_lab_cohort(path: Path | None = None) -> pd.DataFrame:
    target = path or LAB_COHORT_PATH
    if not target.exists():
        print(f"[lab_cohort] WARN missing lab cohort file: {target}")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    try:
        df = pd.read_csv(target, dtype=str).fillna("")
    except Exception as exc:
        print(f"[lab_cohort] WARN failed to read lab cohort: {exc}")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        print(f"[lab_cohort] WARN lab cohort missing columns: {','.join(missing)}")
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    return df


def load_active_lab_skus(path: Path | None = None) -> List[str]:
    df = load_lab_cohort(path)
    if df.empty:
        return []
    enabled = df.get("enabled", "").astype(str).str.strip().str.lower()
    is_enabled = enabled.isin(["yes", "y", "1", "true"])
    skus = df.loc[is_enabled, "sku"].astype(str).str.strip().str.upper()
    return [s for s in skus.tolist() if s]

