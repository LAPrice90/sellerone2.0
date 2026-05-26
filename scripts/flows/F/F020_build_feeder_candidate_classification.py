from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.flows.F._contract_io import write_f_contract_df
from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract
from scripts.flows.F._schemas import get_f_output_column_types, get_f_output_contract


DEFAULT_INPUT_REL_PATH = get_f_output_contract("feeder_candidate_intake_live").rel_path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_lower(value: object) -> str:
    return _normalize_text(value).lower()


def _truthy(value: object) -> bool:
    return _normalize_lower(value) in {"1", "true", "yes", "y", "on"}


def _normalize_asin(value: object) -> str:
    return _normalize_text(value).upper()


def _normalize_barcode(value: object) -> str:
    raw = _normalize_text(value)
    return "".join(char for char in raw if char.isdigit())


def _is_valid_asin(asin: str) -> bool:
    return len(asin) == 10 and asin.isalnum()


def _is_valid_barcode(barcode: str) -> bool:
    return barcode.isdigit() and len(barcode) in {8, 12, 13, 14}


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


def _build_normalized_row(source_row: pd.Series, normalized_utc: str) -> dict[str, str]:
    asin_raw = _normalize_text(source_row.get("asin", ""))
    barcode_raw = _normalize_text(source_row.get("barcode", ""))

    asin = _normalize_asin(asin_raw)
    barcode = _normalize_barcode(barcode_raw)
    asin_status = "missing" if asin == "" else ("valid" if _is_valid_asin(asin) else "invalid")
    barcode_status = "missing" if barcode == "" else ("valid" if _is_valid_barcode(barcode) else "invalid")

    identity_key = ""
    if asin_status == "valid":
        identity_key = asin
    elif barcode_status == "valid":
        identity_key = barcode

    normalization_reasons: list[str] = []
    if asin and asin != asin_raw:
        normalization_reasons.append("asin_uppercased")
    if barcode and barcode != barcode_raw:
        normalization_reasons.append("barcode_compacted_digits")

    supplier_id = _normalize_text(source_row.get("chosen_supplier_id", ""))
    supplier_name = _normalize_text(source_row.get("chosen_supplier_name", ""))
    chosen_supplier = supplier_name if supplier_name else supplier_id

    return {
        "candidate_id": _normalize_text(source_row.get("candidate_id", "")),
        "source_discovery_candidate_id": _normalize_text(source_row.get("source_discovery_candidate_id", "")),
        "source_discovery_run_id": _normalize_text(source_row.get("source_discovery_run_id", "")),
        "source_row_ref": _normalize_text(source_row.get("source_row_ref", "")),
        "source_file_path": _normalize_text(source_row.get("source_file_path", "")),
        "asin": asin,
        "asin_validation_status": asin_status,
        "barcode": barcode,
        "barcode_validation_status": barcode_status,
        "identity_key": identity_key,
        "brand": _normalize_text(source_row.get("brand", "")),
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "chosen_supplier": chosen_supplier,
        "supplier_sku": "",
        "price_list_status": _normalize_lower(source_row.get("price_list_status", "")),
        "price_list_artifact_path": _normalize_text(source_row.get("price_list_artifact_path", "")),
        "handoff_ready_flag": "1" if _truthy(source_row.get("handoff_ready_flag", "")) else "0",
        "intake_status": _normalize_lower(source_row.get("intake_status", "")),
        "intake_reason_codes": _normalize_text(source_row.get("intake_reason_codes", "")),
        "intake_received_utc": _normalize_text(source_row.get("intake_received_utc", "")),
        "normalization_status": "normalized",
        "normalization_reason_codes": "|".join(normalization_reasons),
        "normalized_utc": normalized_utc,
        "title": _normalize_text(source_row.get("title", "")),
        "keyword_source": _normalize_text(source_row.get("keyword_source", "")),
        "category_source": _normalize_text(source_row.get("category_source", "")),
        "last_reviewed_utc": _normalize_text(source_row.get("last_reviewed_utc", "")),
    }


def _build_classification_row(
    normalized_row: dict[str, str],
    *,
    status: str,
    reason_codes: list[str],
    status_bucket: str,
    classification_utc: str,
) -> dict[str, str]:
    return {
        "candidate_id": normalized_row.get("candidate_id", ""),
        "source_discovery_candidate_id": normalized_row.get("source_discovery_candidate_id", ""),
        "source_discovery_run_id": normalized_row.get("source_discovery_run_id", ""),
        "first_pass_status": status,
        "first_pass_reason_codes": "|".join(reason_codes),
        "status_bucket": status_bucket,
        "ready_for_f1c_flag": "1" if status == "ready_for_viability" else "0",
        "manual_review_flag": "1" if status == "manual_review" else "0",
        "hold_flag": "1" if status == "hold" else "0",
        "classification_utc": classification_utc,
        "identity_key": normalized_row.get("identity_key", ""),
        "asin": normalized_row.get("asin", ""),
        "barcode": normalized_row.get("barcode", ""),
        "brand": normalized_row.get("brand", ""),
        "supplier_id": normalized_row.get("supplier_id", ""),
        "supplier_name": normalized_row.get("supplier_name", ""),
        "chosen_supplier": normalized_row.get("chosen_supplier", ""),
        "source_row_ref": normalized_row.get("source_row_ref", ""),
        "source_file_path": normalized_row.get("source_file_path", ""),
        "title": normalized_row.get("title", ""),
    }


def _build_not_ready_row(
    normalized_row: dict[str, str],
    classification_row: dict[str, str],
    *,
    hold_utc: str,
    hold_reasons: list[str],
) -> dict[str, str]:
    return {
        "hold_utc": hold_utc,
        "candidate_id": classification_row.get("candidate_id", ""),
        "source_discovery_candidate_id": classification_row.get("source_discovery_candidate_id", ""),
        "source_discovery_run_id": classification_row.get("source_discovery_run_id", ""),
        "first_pass_status": classification_row.get("first_pass_status", ""),
        "first_pass_reason_codes": classification_row.get("first_pass_reason_codes", ""),
        "hold_reason_codes": "|".join(hold_reasons),
        "hold_note": "not_ready_for_f1c",
        "identity_key": classification_row.get("identity_key", ""),
        "asin": classification_row.get("asin", ""),
        "barcode": classification_row.get("barcode", ""),
        "brand": classification_row.get("brand", ""),
        "supplier_id": classification_row.get("supplier_id", ""),
        "supplier_name": classification_row.get("supplier_name", ""),
        "source_row_ref": normalized_row.get("source_row_ref", ""),
        "source_file_path": normalized_row.get("source_file_path", ""),
        "title": classification_row.get("title", ""),
    }


def _source_missing_health_rows(observed_utc: str, source_path: Path) -> list[dict[str, str]]:
    return [
        {
            "check": "feeder_classification_source_contract",
            "status": "warn",
            "value": "0",
            "notes": "feeder_candidate_intake_live_missing",
            "observed_utc": observed_utc,
            "source_path": str(source_path),
        },
        {
            "check": "feeder_classification_quality",
            "status": "warn",
            "value": "0",
            "notes": "no_rows_processed",
            "observed_utc": observed_utc,
            "source_path": str(source_path),
        },
    ]


def build_feeder_candidate_first_pass_classification(
    root: Path | None = None,
    *,
    input_rel_path: str | None = None,
    classification_utc: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)

    source_path = root_path / (input_rel_path or DEFAULT_INPUT_REL_PATH)
    observed_utc = classification_utc or _utc_now_iso()

    if not source_path.exists():
        normalized_df = _write_contract_df(
            _empty_contract_df("feeder_candidate_normalized_live"),
            "feeder_candidate_normalized_live",
            root_path,
        )
        classification_df = _write_contract_df(
            _empty_contract_df("feeder_candidate_first_pass_classification_live"),
            "feeder_candidate_first_pass_classification_live",
            root_path,
        )
        holds_df = _write_contract_df(
            _empty_contract_df("feeder_candidate_first_pass_holds"),
            "feeder_candidate_first_pass_holds",
            root_path,
        )
        health_df = _write_contract_df(
            pd.DataFrame(_source_missing_health_rows(observed_utc, source_path)),
            "feeder_classification_health",
            root_path,
        )
        print(
            {
                "status": "success",
                "normalized_rows": int(len(normalized_df)),
                "classification_rows": int(len(classification_df)),
                "not_ready_rows": int(len(holds_df)),
                "source_rows": 0,
                "source_file": str(source_path),
                "notes": "source file missing; emitted warn health state",
            }
        )
        return normalized_df, classification_df, holds_df, health_df

    source_df = pd.read_csv(source_path, dtype=str).fillna("")
    required_source_columns = get_f_output_contract("feeder_candidate_intake_live").required_columns
    missing_columns = [column for column in required_source_columns if column not in source_df.columns]
    if missing_columns:
        normalized_df = _write_contract_df(
            _empty_contract_df("feeder_candidate_normalized_live"),
            "feeder_candidate_normalized_live",
            root_path,
        )
        classification_df = _write_contract_df(
            _empty_contract_df("feeder_candidate_first_pass_classification_live"),
            "feeder_candidate_first_pass_classification_live",
            root_path,
        )
        holds_df = _write_contract_df(
            _empty_contract_df("feeder_candidate_first_pass_holds"),
            "feeder_candidate_first_pass_holds",
            root_path,
        )
        missing_text = "|".join(missing_columns)
        health_df = _write_contract_df(
            pd.DataFrame(
                [
                    {
                        "check": "feeder_classification_source_contract",
                        "status": "fail",
                        "value": str(len(missing_columns)),
                        "notes": f"missing_columns:{missing_text}",
                        "observed_utc": observed_utc,
                        "source_path": str(source_path),
                    },
                    {
                        "check": "feeder_classification_quality",
                        "status": "fail",
                        "value": "0",
                        "notes": "no_rows_processed_due_to_contract_failure",
                        "observed_utc": observed_utc,
                        "source_path": str(source_path),
                    },
                ]
            ),
            "feeder_classification_health",
            root_path,
        )
        print(
            {
                "status": "success",
                "normalized_rows": int(len(normalized_df)),
                "classification_rows": int(len(classification_df)),
                "not_ready_rows": int(len(holds_df)),
                "source_rows": int(len(source_df)),
                "source_file": str(source_path),
                "notes": f"source contract failed: {missing_text}",
            }
        )
        return normalized_df, classification_df, holds_df, health_df

    normalized_rows = [_build_normalized_row(source_row, observed_utc) for _, source_row in source_df.iterrows()]
    normalized_df = _write_contract_df(
        pd.DataFrame(normalized_rows),
        "feeder_candidate_normalized_live",
        root_path,
    )

    candidate_series = normalized_df.get("candidate_id", "").map(_normalize_text)
    duplicate_candidate_ids = set(candidate_series[candidate_series.ne("") & candidate_series.duplicated(keep=False)])

    classification_rows: list[dict[str, str]] = []
    not_ready_rows: list[dict[str, str]] = []
    ready_count = 0
    manual_review_count = 0
    hold_count = 0

    for _, normalized_row in normalized_df.iterrows():
        normalized_map = {column: _normalize_text(value) for column, value in normalized_row.to_dict().items()}

        hold_reasons: list[str] = []
        review_reasons: list[str] = []

        candidate_id = normalized_map.get("candidate_id", "")
        asin_status = _normalize_lower(normalized_map.get("asin_validation_status", ""))
        barcode_status = _normalize_lower(normalized_map.get("barcode_validation_status", ""))
        supplier_id = normalized_map.get("supplier_id", "")
        supplier_name = normalized_map.get("supplier_name", "")

        if candidate_id == "":
            hold_reasons.append("missing_candidate_id")
        elif candidate_id in duplicate_candidate_ids:
            hold_reasons.append("duplicate_candidate_id")

        if normalized_map.get("identity_key", "") == "":
            hold_reasons.append("missing_identity_key")
        if asin_status == "invalid":
            hold_reasons.append("invalid_asin_format")
        if barcode_status == "invalid":
            hold_reasons.append("invalid_barcode_format")
        if normalized_map.get("brand", "") == "":
            hold_reasons.append("missing_brand")
        if supplier_id == "" and supplier_name == "":
            hold_reasons.append("missing_supplier_reference")
        if _normalize_lower(normalized_map.get("price_list_status", "")) != "acquired":
            hold_reasons.append("price_list_not_acquired")
        if not _truthy(normalized_map.get("handoff_ready_flag", "")):
            hold_reasons.append("handoff_not_ready")
        if _normalize_lower(normalized_map.get("intake_status", "")) != "intake_ready":
            hold_reasons.append("intake_not_ready")

        if asin_status == "valid" and barcode_status == "valid":
            review_reasons.append("identity_dual_key_review")
        if supplier_id != "" and supplier_name == "":
            review_reasons.append("supplier_name_missing")

        if hold_reasons:
            status = "hold"
            reason_codes = hold_reasons
            status_bucket = "problem"
            hold_count += 1
        elif review_reasons:
            status = "manual_review"
            reason_codes = review_reasons
            status_bucket = "review"
            manual_review_count += 1
        else:
            status = "ready_for_viability"
            reason_codes = ["baseline_structure_pass"]
            status_bucket = "ready"
            ready_count += 1

        classification_row = _build_classification_row(
            normalized_map,
            status=status,
            reason_codes=reason_codes,
            status_bucket=status_bucket,
            classification_utc=observed_utc,
        )
        classification_rows.append(classification_row)

        if status != "ready_for_viability":
            not_ready_rows.append(
                _build_not_ready_row(
                    normalized_map,
                    classification_row,
                    hold_utc=observed_utc,
                    hold_reasons=reason_codes,
                )
            )

    classification_df = _write_contract_df(
        pd.DataFrame(classification_rows),
        "feeder_candidate_first_pass_classification_live",
        root_path,
    )
    holds_df = _write_contract_df(
        pd.DataFrame(not_ready_rows),
        "feeder_candidate_first_pass_holds",
        root_path,
    )

    source_status = "ok"
    source_notes = "source_contract_columns_present"
    quality_status = "ok"
    quality_notes = (
        f"ready_rows={ready_count};manual_review_rows={manual_review_count};"
        f"hold_rows={hold_count};source_rows={len(source_df)}"
    )

    if len(source_df) == 0:
        quality_status = "warn"
        quality_notes = "no_rows_processed"
    elif len(classification_df) == 0:
        quality_status = "fail"
        quality_notes = "no_rows_classified"
    elif ready_count == 0:
        quality_status = "fail"
        quality_notes = (
            f"no_ready_rows;manual_review_rows={manual_review_count};"
            f"hold_rows={hold_count};source_rows={len(source_df)}"
        )
    elif hold_count > 0 or manual_review_count > 0:
        quality_status = "warn"

    health_df = _write_contract_df(
        pd.DataFrame(
            [
                {
                    "check": "feeder_classification_source_contract",
                    "status": source_status,
                    "value": "0",
                    "notes": source_notes,
                    "observed_utc": observed_utc,
                    "source_path": str(source_path),
                },
                {
                    "check": "feeder_classification_quality",
                    "status": quality_status,
                    "value": str(hold_count + manual_review_count),
                    "notes": quality_notes,
                    "observed_utc": observed_utc,
                    "source_path": str(source_path),
                },
            ]
        ),
        "feeder_classification_health",
        root_path,
    )

    print(
        {
            "status": "success",
            "normalized_rows": int(len(normalized_df)),
            "classification_rows": int(len(classification_df)),
            "ready_rows": int(ready_count),
            "manual_review_rows": int(manual_review_count),
            "hold_rows": int(hold_count),
            "not_ready_rows": int(len(holds_df)),
            "source_rows": int(len(source_df)),
            "source_file": str(source_path),
            "normalized_output": str(root_path / get_f_output_contract("feeder_candidate_normalized_live").rel_path),
            "classification_output": str(
                root_path / get_f_output_contract("feeder_candidate_first_pass_classification_live").rel_path
            ),
            "not_ready_output": str(root_path / get_f_output_contract("feeder_candidate_first_pass_holds").rel_path),
            "health_output": str(root_path / get_f_output_contract("feeder_classification_health").rel_path),
        }
    )
    return normalized_df, classification_df, holds_df, health_df


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build canonical feeder normalization and first-pass candidate classification from intake-ready rows."
    )
    parser.add_argument(
        "--input-rel-path",
        default=None,
        help=f"Repo-relative intake csv path (default: {DEFAULT_INPUT_REL_PATH}).",
    )
    parser.add_argument(
        "--classification-utc",
        default=None,
        help="Override observed utc for deterministic runs.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_feeder_candidate_first_pass_classification(
        input_rel_path=args.input_rel_path,
        classification_utc=args.classification_utc,
    )


if __name__ == "__main__":
    main()
