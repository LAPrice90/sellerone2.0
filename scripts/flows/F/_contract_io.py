from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.core.storage import read_dataframe_with_sql_fallback, write_dataframe_with_sql_compat
from scripts.flows.F._schemas import get_f_output_column_types, get_f_output_contract


def f_contract_table_name(contract_name: str) -> str:
    return f"f_{contract_name}"


def f_contract_columns(contract_name: str) -> list[str]:
    contract = get_f_output_contract(contract_name)
    return [*contract.required_columns, *contract.optional_columns]


def empty_f_contract_df(contract_name: str) -> pd.DataFrame:
    return pd.DataFrame(columns=f_contract_columns(contract_name))


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def finalize_f_contract_df(df: pd.DataFrame, contract_name: str) -> pd.DataFrame:
    ordered = f_contract_columns(contract_name)
    out = df.copy()
    missing_columns = [column for column in ordered if column not in out.columns]
    if missing_columns:
        out = pd.concat(
            [out, pd.DataFrame({column: "" for column in missing_columns}, index=out.index)],
            axis=1,
        )
    out = out[ordered]
    for column in ordered:
        out[column] = out[column].map(_normalize_text)
    return out


def assert_f_contract_types(df: pd.DataFrame, contract_name: str) -> None:
    expected_types = get_f_output_column_types(contract_name)
    mismatches: list[str] = []
    for column, expected in expected_types.items():
        if expected == "string" and column in df.columns and not pd.api.types.is_object_dtype(df[column]):
            mismatches.append(column)
    if mismatches:
        mismatch_text = ",".join(sorted(mismatches))
        raise ValueError(f"{contract_name} type mismatch for string columns: {mismatch_text}")


def read_f_contract_df(root: Path, contract_name: str) -> pd.DataFrame:
    path = root / get_f_output_contract(contract_name).rel_path
    columns = f_contract_columns(contract_name)
    try:
        df = read_dataframe_with_sql_fallback(path, f_contract_table_name(contract_name), dtype=str).fillna("")
    except (FileNotFoundError, pd.errors.EmptyDataError):
        df = pd.DataFrame(columns=columns)
    return finalize_f_contract_df(df, contract_name)


def write_f_contract_df(root: Path, contract_name: str, df: pd.DataFrame) -> pd.DataFrame:
    finalized = finalize_f_contract_df(df, contract_name)
    assert_f_contract_types(finalized, contract_name)
    path = root / get_f_output_contract(contract_name).rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    write_dataframe_with_sql_compat(finalized, path, f_contract_table_name(contract_name))
    return finalized


def append_f_contract_row(root: Path, contract_name: str, row: dict[str, object]) -> dict[str, str]:
    ordered = f_contract_columns(contract_name)
    existing = read_f_contract_df(root, contract_name)
    normalized = {column: _normalize_text(row.get(column, "")) for column in ordered}
    out_df = pd.concat([existing, pd.DataFrame([normalized])], ignore_index=True)
    write_f_contract_df(root, contract_name, out_df)
    return normalized
