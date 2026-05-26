from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.flows.F._contract_io import write_f_contract_df
from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract
from scripts.flows.F._schemas import get_f_output_column_types, get_f_output_contract
from scripts.flows.F._source_contracts import get_source_contract


DEFAULT_INPUT_REL_PATH = get_source_contract("supplier_discovery_handoff").source_path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_lower(value: object) -> str:
    return _normalize_text(value).lower()


def _truthy(value: object) -> bool:
    return _normalize_lower(value) in {"1", "true", "yes", "y", "on"}


def _contract_columns(contract_name: str) -> list[str]:
    contract = get_f_output_contract(contract_name)
    return [*contract.required_columns, *contract.optional_columns]


def _empty_contract_df(contract_name: str) -> pd.DataFrame:
    return pd.DataFrame(columns=_contract_columns(contract_name))


def _finalize_contract_df(df: pd.DataFrame, contract_name: str) -> pd.DataFrame:
    ordered = _contract_columns(contract_name)
    out = df.copy()
    for column in ordered:
        if column not in out.columns:
            out[column] = ""
    out = out[ordered]
    for column in ordered:
        out[column] = out[column].map(_normalize_text)
    return out


def _type_mismatch_columns(df: pd.DataFrame, contract_name: str) -> list[str]:
    expected_types = get_f_output_column_types(contract_name)
    mismatches: list[str] = []
    for column, expected in expected_types.items():
        if expected == "string" and column in df.columns and not pd.api.types.is_object_dtype(df[column]):
            mismatches.append(column)
    return mismatches


def _write_contract_df(df: pd.DataFrame, contract_name: str, root_path: Path) -> pd.DataFrame:
    finalized = _finalize_contract_df(df, contract_name)
    mismatches = _type_mismatch_columns(finalized, contract_name)
    if mismatches:
        mismatch_text = ",".join(sorted(mismatches))
        raise ValueError(f"{contract_name} type mismatch for string columns: {mismatch_text}")
    out_path = root_path / get_f_output_contract(contract_name).rel_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_f_contract_df(root_path, contract_name, finalized)
    return finalized


def _build_hold_row(source_row: pd.Series, source_row_ref: str, reasons: list[str], hold_utc: str) -> dict[str, str]:
    return {
        "hold_utc": hold_utc,
        "source_row_ref": source_row_ref,
        "discovery_candidate_id": _normalize_text(source_row.get("discovery_candidate_id", "")),
        "discovery_run_id": _normalize_text(source_row.get("discovery_run_id", "")),
        "asin": _normalize_text(source_row.get("asin", "")),
        "barcode": _normalize_text(source_row.get("barcode", "")),
        "brand": _normalize_text(source_row.get("brand", "")),
        "chosen_supplier_id": _normalize_text(source_row.get("chosen_supplier_id", "")),
        "chosen_supplier_name": _normalize_text(source_row.get("chosen_supplier_name", "")),
        "price_list_status": _normalize_lower(source_row.get("price_list_status", "")),
        "price_list_artifact_path": _normalize_text(source_row.get("price_list_artifact_path", "")),
        "handoff_ready_flag": "1" if _truthy(source_row.get("handoff_ready_flag", "")) else "0",
        "hold_reason_codes": "|".join(reasons),
        "hold_note": "source_contract_validation_failed",
        "title": _normalize_text(source_row.get("title", "")),
        "keyword_source": _normalize_text(source_row.get("keyword_source", "")),
        "category_source": _normalize_text(source_row.get("category_source", "")),
        "last_reviewed_utc": _normalize_text(source_row.get("last_reviewed_utc", "")),
    }


def _build_intake_row(source_row: pd.Series, source_row_ref: str, intake_utc: str, source_path: Path) -> dict[str, str]:
    candidate_id = _normalize_text(source_row.get("discovery_candidate_id", ""))
    return {
        "candidate_id": candidate_id,
        "source_discovery_candidate_id": candidate_id,
        "source_discovery_run_id": _normalize_text(source_row.get("discovery_run_id", "")),
        "asin": _normalize_text(source_row.get("asin", "")),
        "barcode": _normalize_text(source_row.get("barcode", "")),
        "brand": _normalize_text(source_row.get("brand", "")),
        "chosen_supplier_id": _normalize_text(source_row.get("chosen_supplier_id", "")),
        "chosen_supplier_name": _normalize_text(source_row.get("chosen_supplier_name", "")),
        "price_list_status": "acquired",
        "price_list_artifact_path": _normalize_text(source_row.get("price_list_artifact_path", "")),
        "handoff_ready_flag": "1",
        "intake_status": "intake_ready",
        "intake_reason_codes": "",
        "intake_received_utc": intake_utc,
        "source_row_ref": source_row_ref,
        "source_file_path": str(source_path),
        "title": _normalize_text(source_row.get("title", "")),
        "keyword_source": _normalize_text(source_row.get("keyword_source", "")),
        "category_source": _normalize_text(source_row.get("category_source", "")),
        "last_reviewed_utc": _normalize_text(source_row.get("last_reviewed_utc", "")),
    }


def _source_missing_health_rows(observed_utc: str, source_path: Path) -> list[dict[str, str]]:
    return [
        {
            "check": "feeder_intake_source_contract",
            "status": "warn",
            "value": "0",
            "notes": "supplier_discovery_handoff_missing",
            "observed_utc": observed_utc,
            "source_path": str(source_path),
        },
        {
            "check": "feeder_intake_quality",
            "status": "warn",
            "value": "0",
            "notes": "no_rows_processed",
            "observed_utc": observed_utc,
            "source_path": str(source_path),
        },
    ]


def build_feeder_candidate_intake(
    root: Path | None = None,
    *,
    input_rel_path: str | None = None,
    intake_utc: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)

    source_contract = get_source_contract("supplier_discovery_handoff")
    source_path = root_path / (input_rel_path or source_contract.source_path)
    observed_utc = intake_utc or _utc_now_iso()

    if not source_path.exists():
        intake_df = _write_contract_df(_empty_contract_df("feeder_candidate_intake_live"), "feeder_candidate_intake_live", root_path)
        holds_df = _write_contract_df(_empty_contract_df("feeder_candidate_intake_holds"), "feeder_candidate_intake_holds", root_path)
        health_df = _write_contract_df(
            pd.DataFrame(_source_missing_health_rows(observed_utc, source_path)),
            "feeder_intake_health",
            root_path,
        )
        print(
            {
                "status": "success",
                "accepted_rows": int(len(intake_df)),
                "held_rows": int(len(holds_df)),
                "source_rows": 0,
                "source_file": str(source_path),
                "notes": "source file missing; emitted warn health state",
            }
        )
        return intake_df, holds_df, health_df

    source_df = pd.read_csv(source_path, dtype=str).fillna("")
    missing_columns = [column for column in source_contract.required_columns if column not in source_df.columns]
    if missing_columns:
        intake_df = _write_contract_df(_empty_contract_df("feeder_candidate_intake_live"), "feeder_candidate_intake_live", root_path)
        holds_df = _write_contract_df(_empty_contract_df("feeder_candidate_intake_holds"), "feeder_candidate_intake_holds", root_path)
        missing_text = "|".join(missing_columns)
        health_rows = [
            {
                "check": "feeder_intake_source_contract",
                "status": "fail",
                "value": str(len(missing_columns)),
                "notes": f"missing_columns:{missing_text}",
                "observed_utc": observed_utc,
                "source_path": str(source_path),
            },
            {
                "check": "feeder_intake_quality",
                "status": "fail",
                "value": "0",
                "notes": "no_rows_processed_due_to_contract_failure",
                "observed_utc": observed_utc,
                "source_path": str(source_path),
            },
        ]
        health_df = _write_contract_df(pd.DataFrame(health_rows), "feeder_intake_health", root_path)
        print(
            {
                "status": "success",
                "accepted_rows": int(len(intake_df)),
                "held_rows": int(len(holds_df)),
                "source_rows": int(len(source_df)),
                "source_file": str(source_path),
                "notes": f"source contract failed: {missing_text}",
            }
        )
        return intake_df, holds_df, health_df

    candidate_series = source_df.get("discovery_candidate_id", "").map(_normalize_text)
    duplicate_candidate_ids = set(candidate_series[candidate_series.ne("") & candidate_series.duplicated(keep=False)])

    intake_rows: list[dict[str, str]] = []
    hold_rows: list[dict[str, str]] = []

    for row_index, source_row in source_df.iterrows():
        source_row_ref = str(row_index + 2)
        reasons: list[str] = []

        discovery_candidate_id = _normalize_text(source_row.get("discovery_candidate_id", ""))
        asin = _normalize_text(source_row.get("asin", ""))
        barcode = _normalize_text(source_row.get("barcode", ""))
        brand = _normalize_text(source_row.get("brand", ""))
        chosen_supplier_id = _normalize_text(source_row.get("chosen_supplier_id", ""))
        chosen_supplier_name = _normalize_text(source_row.get("chosen_supplier_name", ""))
        price_list_status = _normalize_lower(source_row.get("price_list_status", ""))
        price_list_artifact_path = _normalize_text(source_row.get("price_list_artifact_path", ""))
        handoff_ready = _truthy(source_row.get("handoff_ready_flag", ""))

        if discovery_candidate_id == "":
            reasons.append("missing_discovery_candidate_id")
        elif discovery_candidate_id in duplicate_candidate_ids:
            reasons.append("duplicate_discovery_candidate_id")

        if not handoff_ready:
            reasons.append("handoff_not_ready")
        if price_list_status != "acquired":
            reasons.append("price_list_not_acquired")
        if price_list_artifact_path == "":
            reasons.append("missing_price_list_artifact_path")
        if asin == "" and barcode == "":
            reasons.append("missing_identity_key")
        if brand == "":
            reasons.append("missing_brand")
        if chosen_supplier_id == "" and chosen_supplier_name == "":
            reasons.append("missing_supplier_reference")

        if reasons:
            hold_rows.append(_build_hold_row(source_row, source_row_ref, reasons, observed_utc))
            continue

        intake_rows.append(_build_intake_row(source_row, source_row_ref, observed_utc, source_path))

    intake_df = _write_contract_df(pd.DataFrame(intake_rows), "feeder_candidate_intake_live", root_path)
    holds_df = _write_contract_df(pd.DataFrame(hold_rows), "feeder_candidate_intake_holds", root_path)

    source_status = "ok"
    source_notes = "source_contract_columns_present"
    quality_status = "ok"
    quality_notes = f"accepted_rows={len(intake_df)};held_rows={len(holds_df)};source_rows={len(source_df)}"

    if len(source_df) == 0:
        quality_status = "warn"
        quality_notes = "no_rows_processed"
    elif len(intake_df) == 0:
        quality_status = "fail"
        quality_notes = f"all_rows_held;held_rows={len(holds_df)};source_rows={len(source_df)}"
    elif len(holds_df) > 0:
        quality_status = "warn"

    health_rows = [
        {
            "check": "feeder_intake_source_contract",
            "status": source_status,
            "value": "0",
            "notes": source_notes,
            "observed_utc": observed_utc,
            "source_path": str(source_path),
        },
        {
            "check": "feeder_intake_quality",
            "status": quality_status,
            "value": str(len(holds_df)),
            "notes": quality_notes,
            "observed_utc": observed_utc,
            "source_path": str(source_path),
        },
    ]
    health_df = _write_contract_df(pd.DataFrame(health_rows), "feeder_intake_health", root_path)

    print(
        {
            "status": "success",
            "accepted_rows": int(len(intake_df)),
            "held_rows": int(len(holds_df)),
            "source_rows": int(len(source_df)),
            "source_file": str(source_path),
            "intake_output": str(root_path / get_f_output_contract("feeder_candidate_intake_live").rel_path),
            "hold_output": str(root_path / get_f_output_contract("feeder_candidate_intake_holds").rel_path),
            "health_output": str(root_path / get_f_output_contract("feeder_intake_health").rel_path),
        }
    )
    return intake_df, holds_df, health_df


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build feeder candidate intake from Supplier Discovery handoff artifact.")
    parser.add_argument(
        "--input-rel-path",
        default=None,
        help=f"Repo-relative handoff csv path (default: {DEFAULT_INPUT_REL_PATH}).",
    )
    parser.add_argument(
        "--intake-utc",
        default=None,
        help="Override observed utc for deterministic runs.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_feeder_candidate_intake(
        input_rel_path=args.input_rel_path,
        intake_utc=args.intake_utc,
    )


if __name__ == "__main__":
    main()
