from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from scripts.flows.F.price_list_manager._io import normalize_text
from scripts.flows.F.price_list_manager._paths import get_manager_paths


PRECHECK_STATUS_COLUMNS = [
    "observed_utc",
    "supplier_id",
    "run_id",
    "status",
    "eligible_pass_rows",
    "ai_queue_rows",
    "pending_ai_decision_rows",
    "decided_rows",
    "invalid_action_rows",
    "missing_reason_rows",
    "stale_decision_rows",
    "reused_in_final_rows",
    "hidden_until_completed_flag",
    "ai_review_queue_path",
    "codex_ai_decision_path",
    "registry_path",
    "notes",
]

PRECHECK_REGISTRY_COLUMNS = [
    "observed_utc",
    "first_seen_utc",
    "last_seen_utc",
    "supplier_id",
    "run_id",
    "f032_decision_id",
    "source_review_pack_type",
    "candidate_id",
    "supplier_sku",
    "asin",
    "evidence_hash",
    "decision_status",
    "codex_ai_action",
    "hidden_until_completed_flag",
    "notes",
]

PRECHECK_EVIDENCE_HASH_EXCLUDE = {
    "observed_utc",
    "codex_ai_action",
    "codex_ai_decision_bucket",
    "codex_ai_fail_category",
    "codex_ai_confidence",
    "codex_ai_reason",
    "codex_ai_evidence",
}


def safe_path_part(value: object, fallback: str) -> str:
    clean = normalize_text(value).replace("/", "_").replace("\\", "_").strip()
    return clean or fallback


def ai_precheck_root(root: Path) -> Path:
    return get_manager_paths(root=root).system_dir / "ai_prechecks"


def ai_precheck_dir(root: Path, *, supplier_id: str, run_id: str) -> Path:
    return (
        ai_precheck_root(root)
        / safe_path_part(supplier_id, "unknown_supplier")
        / safe_path_part(run_id, "unknown_run")
    )


def read_any_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def finalize_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = ""
    out = out[columns]
    for column in columns:
        out[column] = out[column].map(normalize_text)
    return out


def write_csv(path: Path, df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    out = finalize_columns(df, columns) if columns is not None else df.fillna("")
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)
    return out


def queue_evidence_hash(record: dict[str, object]) -> str:
    payload = {
        str(key): normalize_text(value)
        for key, value in record.items()
        if str(key) not in PRECHECK_EVIDENCE_HASH_EXCLUDE
    }
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(encoded.encode("utf-8")).hexdigest()


def queue_hash_lookup(queue_df: pd.DataFrame) -> dict[str, str]:
    out: dict[str, str] = {}
    if queue_df.empty:
        return out
    for _, row in queue_df.fillna("").iterrows():
        record = {column: normalize_text(value) for column, value in row.to_dict().items()}
        decision_id = normalize_text(record.get("f032_decision_id", ""))
        if decision_id:
            out[decision_id] = queue_evidence_hash(record)
    return out


def load_precheck_registry(precheck_dir: Path) -> pd.DataFrame:
    return finalize_columns(read_any_csv(precheck_dir / "ai_precheck_registry.csv"), PRECHECK_REGISTRY_COLUMNS)
