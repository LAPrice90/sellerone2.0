from __future__ import annotations

from pathlib import Path

import pandas as pd


def normalize_text(value: object) -> str:
    return str(value or "").strip()


def finalize_df(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = ""
    out = out[columns]
    for column in columns:
        out[column] = out[column].map(normalize_text)
    return out


def read_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns)
    df = pd.read_csv(path, dtype=str).fillna("")
    return finalize_df(df, columns)


def write_csv(path: Path, df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    finalized = finalize_df(df, columns)
    path.parent.mkdir(parents=True, exist_ok=True)
    finalized.to_csv(path, index=False)
    return finalized

