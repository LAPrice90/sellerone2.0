from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.core.storage import read_dataframe_with_sql_fallback, write_dataframe_with_sql_compat
from scripts.flows.O._schemas import get_o_output_contract


def o_contract_table_name(contract_name: str) -> str:
    return f"o_{contract_name}"


def o_contract_columns(contract_name: str) -> list[str]:
    contract = get_o_output_contract(contract_name)
    return [*contract.required_columns, *contract.optional_columns]


def empty_o_contract_df(contract_name: str) -> pd.DataFrame:
    return pd.DataFrame(columns=o_contract_columns(contract_name))


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def finalize_o_contract_df(df: pd.DataFrame, contract_name: str) -> pd.DataFrame:
    ordered = o_contract_columns(contract_name)
    out = df.copy()
    missing_columns = [column for column in ordered if column not in out.columns]
    if missing_columns:
        out = pd.concat([out, pd.DataFrame("", index=out.index, columns=missing_columns)], axis=1)
    extra_columns = [column for column in out.columns if column not in ordered]
    out = out[ordered + extra_columns]
    for column in out.columns:
        out[column] = out[column].map(_normalize_text)
    return out


def read_o_contract_df(root: Path, contract_name: str) -> pd.DataFrame:
    path = root / get_o_output_contract(contract_name).rel_path
    columns = o_contract_columns(contract_name)
    try:
        df = read_dataframe_with_sql_fallback(path, o_contract_table_name(contract_name), dtype=str).fillna("")
    except (FileNotFoundError, pd.errors.EmptyDataError):
        df = pd.DataFrame(columns=columns)
    return finalize_o_contract_df(df, contract_name)


def write_o_contract_df(root: Path, contract_name: str, df: pd.DataFrame) -> pd.DataFrame:
    finalized = finalize_o_contract_df(df, contract_name)
    path = root / get_o_output_contract(contract_name).rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    write_dataframe_with_sql_compat(finalized, path, o_contract_table_name(contract_name))
    return finalized


def append_o_contract_row(root: Path, contract_name: str, row: dict[str, object]) -> dict[str, str]:
    ordered = o_contract_columns(contract_name)
    existing = read_o_contract_df(root, contract_name)
    normalized = {column: _normalize_text(row.get(column, "")) for column in ordered}
    out_df = pd.concat([existing, pd.DataFrame([normalized])], ignore_index=True)
    write_o_contract_df(root, contract_name, out_df)
    return normalized
