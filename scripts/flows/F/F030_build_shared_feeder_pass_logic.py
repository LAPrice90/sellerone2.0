from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.flows.F._contract_io import write_f_contract_df
from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract
from scripts.flows.F._schemas import get_f_output_column_types, get_f_output_contract
from scripts.flows.F._source_contracts import get_source_contract


DEFAULT_INPUT_REL_PATH = get_source_contract("supplier_price_list_universal_live").source_path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_lower(value: object) -> str:
    return _normalize_text(value).lower()


def _normalize_digits(value: object) -> str:
    return "".join(ch for ch in _normalize_text(value) if ch.isdigit())


def _parse_positive_float(value: object) -> float | None:
    raw = _normalize_text(value).replace(",", "")
    if raw == "":
        return None
    try:
        num = float(raw)
    except ValueError:
        return None
    if num <= 0:
        return None
    return num


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


def _source_missing_health_rows(observed_utc: str, source_path: Path) -> list[dict[str, str]]:
    return [
        {
            "check": "feeder_shared_pass_logic_source_contract",
            "status": "warn",
            "value": "0",
            "notes": "supplier_price_list_universal_live_missing",
            "observed_utc": observed_utc,
            "source_path": str(source_path),
        },
        {
            "check": "feeder_shared_pass_logic_quality",
            "status": "warn",
            "value": "0",
            "notes": "no_rows_processed",
            "observed_utc": observed_utc,
            "source_path": str(source_path),
        },
    ]


def _candidate_id(supplier_id: str, row_hash: str, sku: str, barcode: str, title: str) -> str:
    base = row_hash
    if base == "":
        key = "|".join([supplier_id, sku, barcode, title])
        base = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return f"F-{supplier_id}-{base[:12]}"


def _classify_row(row: pd.Series, pass_logic_utc: str) -> tuple[dict[str, str], dict[str, str] | None]:
    supplier_id = _normalize_text(row.get("supplier_id", ""))
    supplier_name = _normalize_text(row.get("supplier_name", ""))
    supplier_sku = _normalize_text(row.get("supplier_sku", ""))
    supplier_title = _normalize_text(row.get("supplier_title", ""))
    barcode = _normalize_digits(row.get("barcode", ""))
    cost_num = _parse_positive_float(row.get("unit_cost", ""))
    unit_cost = "" if cost_num is None else f"{cost_num:.2f}"
    source_row_hash = _normalize_text(row.get("row_hash", ""))
    source_file_path = _normalize_text(row.get("source_file_path", ""))
    source_seen_at_utc = _normalize_text(row.get("source_seen_at_utc", ""))
    source_url = _normalize_text(row.get("source_url", ""))
    normalized_utc = _normalize_text(row.get("normalized_utc", ""))

    has_barcode = barcode != ""
    has_title = supplier_title != ""
    has_sku = supplier_sku != ""

    legacy_precheck_identity_mode = "barcode" if has_barcode else ("title_only" if has_title else "none")
    legacy_precheck_result = "pass"
    legacy_precheck_reason_codes: list[str] = []
    if has_barcode:
        legacy_precheck_reason_codes.append("BARCODE_PRESENT")
    elif not has_title:
        legacy_precheck_result = "fail"
        legacy_precheck_reason_codes.append("NOIDENTITY")
    elif len(supplier_title) < 8:
        legacy_precheck_result = "review"
        legacy_precheck_reason_codes.append("TITLE_ONLY_TOO_SHORT")
    elif not has_sku:
        legacy_precheck_result = "review"
        legacy_precheck_reason_codes.append("TITLE_ONLY_MISSING_SKU")
    else:
        legacy_precheck_reason_codes.append("TITLE_ONLY_PRECHECK_PASS")

    reasons: list[str] = []
    if unit_cost == "":
        reasons.append("NOCOST")
    if barcode == "" and supplier_title == "":
        reasons.append("NOIDENTITY")
    elif barcode == "" and legacy_precheck_result != "pass":
        reasons.append("MISSING_BARCODE_TITLE_ONLY")
    if supplier_title != "" and len(supplier_title) < 5:
        reasons.append("WEAK_TITLE")
    if cost_num is not None and cost_num > 250:
        reasons.append("COST_OUTLIER")

    status = "ready_for_amazon_checks"
    legacy_status = "PASS"
    if "NOCOST" in reasons or "NOIDENTITY" in reasons:
        status = "hold"
        legacy_status = "FAIL"
    elif reasons:
        status = "manual_review"
        legacy_status = "REVIEW"

    feeder_candidate_id = _candidate_id(
        supplier_id=supplier_id,
        row_hash=source_row_hash,
        sku=supplier_sku,
        barcode=barcode,
        title=supplier_title,
    )

    pass_row = {
        "feeder_candidate_id": feeder_candidate_id,
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "supplier_sku": supplier_sku,
        "supplier_title": supplier_title,
        "barcode": barcode,
        "unit_cost": unit_cost,
        "currency": _normalize_text(row.get("currency", "")),
        "vat_rate": _normalize_text(row.get("vat_rate", "")),
        "pass_logic_status": status,
        "pass_logic_reason_codes": "|".join(reasons),
        "legacy_status_code": legacy_status,
        "ready_for_amazon_checks_flag": "1" if status == "ready_for_amazon_checks" else "0",
        "manual_review_flag": "1" if status == "manual_review" else "0",
        "hold_flag": "1" if status == "hold" else "0",
        "pass_logic_utc": pass_logic_utc,
        "source_row_hash": source_row_hash,
        "source_file_path": source_file_path,
        "source_seen_at_utc": source_seen_at_utc,
        "source_url": source_url,
        "normalized_utc": normalized_utc,
        "legacy_precheck_identity_mode": legacy_precheck_identity_mode,
        "legacy_precheck_result": legacy_precheck_result,
        "legacy_precheck_reason_codes": "|".join(legacy_precheck_reason_codes),
        "notes": "",
    }

    hold_row: dict[str, str] | None = None
    if status != "ready_for_amazon_checks":
        hold_row = {
            "hold_utc": pass_logic_utc,
            "feeder_candidate_id": feeder_candidate_id,
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "supplier_sku": supplier_sku,
            "supplier_title": supplier_title,
            "barcode": barcode,
            "unit_cost": unit_cost,
            "hold_reason_codes": "|".join(reasons),
            "legacy_status_code": legacy_status,
            "source_row_hash": source_row_hash,
            "source_file_path": source_file_path,
            "source_seen_at_utc": source_seen_at_utc,
            "source_url": source_url,
            "legacy_precheck_identity_mode": legacy_precheck_identity_mode,
            "legacy_precheck_result": legacy_precheck_result,
            "legacy_precheck_reason_codes": "|".join(legacy_precheck_reason_codes),
            "notes": "not_ready_for_amazon_checks",
        }

    return pass_row, hold_row


def build_shared_feeder_pass_logic(
    root: Path | None = None,
    *,
    input_rel_path: str | None = None,
    pass_logic_utc: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)

    source_contract = get_source_contract("supplier_price_list_universal_live")
    source_path = root_path / (input_rel_path or source_contract.source_path)
    observed_utc = pass_logic_utc or _utc_now_iso()

    if not source_path.exists():
        pass_df = _write_contract_df(_empty_contract_df("feeder_shared_pass_logic_live"), "feeder_shared_pass_logic_live", root_path)
        holds_df = _write_contract_df(_empty_contract_df("feeder_shared_pass_logic_holds"), "feeder_shared_pass_logic_holds", root_path)
        health_df = _write_contract_df(
            pd.DataFrame(_source_missing_health_rows(observed_utc, source_path)),
            "feeder_shared_pass_logic_health",
            root_path,
        )
        print(
            {
                "status": "success",
                "source_rows": 0,
                "ready_rows": 0,
                "not_ready_rows": 0,
                "notes": "source file missing; emitted warn health state",
            }
        )
        return pass_df, holds_df, health_df

    source_df = pd.read_csv(source_path, dtype=str).fillna("")
    missing_columns = [column for column in source_contract.required_columns if column not in source_df.columns]
    if missing_columns:
        pass_df = _write_contract_df(_empty_contract_df("feeder_shared_pass_logic_live"), "feeder_shared_pass_logic_live", root_path)
        holds_df = _write_contract_df(_empty_contract_df("feeder_shared_pass_logic_holds"), "feeder_shared_pass_logic_holds", root_path)
        missing_text = "|".join(missing_columns)
        health_rows = [
            {
                "check": "feeder_shared_pass_logic_source_contract",
                "status": "fail",
                "value": str(len(missing_columns)),
                "notes": f"missing_columns:{missing_text}",
                "observed_utc": observed_utc,
                "source_path": str(source_path),
            },
            {
                "check": "feeder_shared_pass_logic_quality",
                "status": "fail",
                "value": "0",
                "notes": "no_rows_processed_due_to_contract_failure",
                "observed_utc": observed_utc,
                "source_path": str(source_path),
            },
        ]
        health_df = _write_contract_df(pd.DataFrame(health_rows), "feeder_shared_pass_logic_health", root_path)
        print(
            {
                "status": "success",
                "source_rows": int(len(source_df)),
                "ready_rows": 0,
                "not_ready_rows": 0,
                "notes": f"source contract failed: {missing_text}",
            }
        )
        return pass_df, holds_df, health_df

    pass_rows: list[dict[str, str]] = []
    hold_rows: list[dict[str, str]] = []
    for _, row in source_df.iterrows():
        pass_row, hold_row = _classify_row(row, observed_utc)
        pass_rows.append(pass_row)
        if hold_row is not None:
            hold_rows.append(hold_row)

    pass_df = _write_contract_df(pd.DataFrame(pass_rows), "feeder_shared_pass_logic_live", root_path)
    holds_df = _write_contract_df(pd.DataFrame(hold_rows), "feeder_shared_pass_logic_holds", root_path)

    ready_rows = int((pass_df["ready_for_amazon_checks_flag"] == "1").sum()) if not pass_df.empty else 0
    not_ready_rows = int(len(holds_df))

    quality_status = "ok" if not_ready_rows == 0 else "warn"
    quality_note = "all_rows_ready_for_amazon_checks" if not_ready_rows == 0 else "manual_or_hold_rows_present"
    health_rows = [
        {
            "check": "feeder_shared_pass_logic_source_contract",
            "status": "ok",
            "value": str(len(source_df)),
            "notes": "supplier_price_list_universal_contract_valid",
            "observed_utc": observed_utc,
            "source_path": str(source_path),
        },
        {
            "check": "feeder_shared_pass_logic_quality",
            "status": quality_status,
            "value": str(ready_rows),
            "notes": quality_note,
            "observed_utc": observed_utc,
            "source_path": str(source_path),
        },
    ]
    health_df = _write_contract_df(pd.DataFrame(health_rows), "feeder_shared_pass_logic_health", root_path)

    print(
        {
            "status": "success",
            "source_rows": int(len(source_df)),
            "ready_rows": ready_rows,
            "not_ready_rows": not_ready_rows,
            "health_quality_status": quality_status,
        }
    )
    return pass_df, holds_df, health_df


def main() -> None:
    parser = argparse.ArgumentParser(description="Build shared feeder pass/fail logic from universal supplier rows.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--input-rel-path", default=None)
    parser.add_argument("--pass-logic-utc", default=None)
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    build_shared_feeder_pass_logic(
        root=root,
        input_rel_path=args.input_rel_path,
        pass_logic_utc=args.pass_logic_utc,
    )


if __name__ == "__main__":
    main()
