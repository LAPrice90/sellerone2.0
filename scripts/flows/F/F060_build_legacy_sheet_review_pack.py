from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.flows.F._contract_io import write_f_contract_df
from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract
from scripts.flows.F._schemas import get_f_output_column_types, get_f_output_contract
from scripts.flows.F._source_contracts import get_source_contract


APPROVED_STATUSES = {"approved", "approved_for_test_buy", "approved_for_po", "approved_test_buy"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_lower(value: object) -> str:
    return _normalize_text(value).lower()


def _normalize_digits(value: object) -> str:
    return "".join(ch for ch in _normalize_text(value) if ch.isdigit())


def _parse_positive_int(value: object) -> int | None:
    raw = _normalize_text(value).replace(",", "")
    if raw == "":
        return None
    try:
        num = int(float(raw))
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


def _latest_decisions(decisions_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    if decisions_df.empty:
        return {}
    ordered = decisions_df.copy()
    ordered["decision_utc"] = ordered["decision_utc"].map(_normalize_text)
    ordered["candidate_id"] = ordered["candidate_id"].map(_normalize_text)
    ordered["event_id"] = ordered["event_id"].map(_normalize_text)
    ordered = ordered.sort_values(["candidate_id", "decision_utc", "event_id"], kind="stable")
    latest = ordered.drop_duplicates(subset=["candidate_id"], keep="last")
    out: dict[str, dict[str, str]] = {}
    for _, row in latest.iterrows():
        payload = {column: _normalize_text(value) for column, value in row.to_dict().items()}
        candidate_id = payload.get("candidate_id", "")
        if candidate_id:
            out[candidate_id] = payload
    return out


def _source_missing_health_rows(observed_utc: str, source_path: Path) -> list[dict[str, str]]:
    return [
        {
            "check": "feeder_legacy_sheet_source_contract",
            "status": "warn",
            "value": "0",
            "notes": "feeder_candidate_recommendations_live_missing",
            "observed_utc": observed_utc,
            "source_path": str(source_path),
        },
        {
            "check": "feeder_legacy_sheet_quality",
            "status": "warn",
            "value": "0",
            "notes": "no_rows_processed",
            "observed_utc": observed_utc,
            "source_path": str(source_path),
        },
        {
            "check": "feeder_legacy_sheet_send_ready",
            "status": "warn",
            "value": "0",
            "notes": "no_send_ready_rows",
            "observed_utc": observed_utc,
            "source_path": str(source_path),
        },
    ]


def build_legacy_sheet_review_pack(
    root: Path | None = None,
    *,
    supplier_id: str,
    review_utc: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)

    supplier_filter = _normalize_lower(supplier_id)
    if supplier_filter == "":
        raise ValueError("supplier_id is required")

    rec_contract = get_source_contract("feeder_candidate_recommendations_live")
    decisions_contract = get_source_contract("feeder_approval_decisions_log")
    rec_path = root_path / rec_contract.source_path
    decisions_path = root_path / decisions_contract.source_path
    observed_utc = review_utc or _utc_now_iso()

    if not rec_path.exists():
        first_df = _write_contract_df(_empty_contract_df("feeder_legacy_first_checks_live"), "feeder_legacy_first_checks_live", root_path)
        second_df = _write_contract_df(_empty_contract_df("feeder_legacy_second_checks_live"), "feeder_legacy_second_checks_live", root_path)
        bot_df = _write_contract_df(_empty_contract_df("feeder_legacy_bot_status_live"), "feeder_legacy_bot_status_live", root_path)
        health_df = _write_contract_df(
            pd.DataFrame(_source_missing_health_rows(observed_utc, rec_path)),
            "feeder_legacy_sheet_health",
            root_path,
        )
        print(
            {
                "status": "success",
                "supplier_id": supplier_id,
                "first_checks_rows": 0,
                "second_checks_rows": 0,
                "bot_status_rows": int(len(bot_df)),
                "notes": "recommendations source missing; emitted warn health state",
            }
        )
        return first_df, second_df, bot_df, health_df

    rec_df = pd.read_csv(rec_path, dtype=str).fillna("")
    missing_columns = [column for column in rec_contract.required_columns if column not in rec_df.columns]
    if missing_columns:
        first_df = _write_contract_df(_empty_contract_df("feeder_legacy_first_checks_live"), "feeder_legacy_first_checks_live", root_path)
        second_df = _write_contract_df(_empty_contract_df("feeder_legacy_second_checks_live"), "feeder_legacy_second_checks_live", root_path)
        bot_df = _write_contract_df(_empty_contract_df("feeder_legacy_bot_status_live"), "feeder_legacy_bot_status_live", root_path)
        missing_text = "|".join(missing_columns)
        health_df = _write_contract_df(
            pd.DataFrame(
                [
                    {
                        "check": "feeder_legacy_sheet_source_contract",
                        "status": "fail",
                        "value": str(len(missing_columns)),
                        "notes": f"missing_columns:{missing_text}",
                        "observed_utc": observed_utc,
                        "source_path": str(rec_path),
                    },
                    {
                        "check": "feeder_legacy_sheet_quality",
                        "status": "fail",
                        "value": "0",
                        "notes": "no_rows_processed_due_to_contract_failure",
                        "observed_utc": observed_utc,
                        "source_path": str(rec_path),
                    },
                    {
                        "check": "feeder_legacy_sheet_send_ready",
                        "status": "warn",
                        "value": "0",
                        "notes": "no_send_ready_rows",
                        "observed_utc": observed_utc,
                        "source_path": str(rec_path),
                    },
                ]
            ),
            "feeder_legacy_sheet_health",
            root_path,
        )
        print(
            {
                "status": "success",
                "supplier_id": supplier_id,
                "first_checks_rows": 0,
                "second_checks_rows": 0,
                "bot_status_rows": int(len(bot_df)),
                "notes": f"recommendations contract failed: {missing_text}",
            }
        )
        return first_df, second_df, bot_df, health_df

    rec_work = rec_df[rec_df["supplier_id"].map(_normalize_lower) == supplier_filter].copy()
    decisions_df = pd.read_csv(decisions_path, dtype=str).fillna("") if decisions_path.exists() else _empty_contract_df(
        "feeder_approval_decisions_log"
    )
    latest_by_candidate = _latest_decisions(decisions_df)

    first_rows: list[dict[str, str]] = []
    second_rows: list[dict[str, str]] = []
    send_ready_count = 0

    for _, row in rec_work.iterrows():
        rec = {column: _normalize_text(value) for column, value in row.to_dict().items()}
        candidate_id = rec.get("candidate_id", "")
        latest = latest_by_candidate.get(candidate_id, {})
        decision_status = _normalize_lower(latest.get("final_decision_status", ""))
        decision_action = latest.get("decision_action", "")
        qty_num = _parse_positive_int(rec.get("recommended_test_qty", ""))
        recommended_qty = "" if qty_num is None else str(qty_num)
        recommendation_status = _normalize_lower(rec.get("recommendation_status", ""))

        pf = "PASS" if recommendation_status == "approve_test_buy" else "FAIL"
        status_reason = rec.get("recommendation_reason_codes", "") or rec.get("viability_reason_codes", "")
        send_value = "SEND" if decision_status in APPROVED_STATUSES else ""
        if send_value:
            send_ready_count += 1

        first_rows.append(
            {
                "completed": rec.get("supplier_sku", ""),
                "barcode": _normalize_digits(rec.get("barcode", "")),
                "cost": rec.get("unit_cost", ""),
                "vat": rec.get("vat_rate", ""),
                "supplier": rec.get("supplier_name", ""),
                "asin": "",
                "main_rank": "",
                "start_date": "",
                "brand": "",
                "size_1": "",
                "size_2": "",
                "size_3": "",
                "weight": "",
                "dg_ok": "",
                "hazmat": "",
                "buy_box_price": "",
                "lowest_afn_price": "",
                "lowest_mfn_price": "",
                "reasonable_price": "",
                "fba_fee": "",
                "referral_fee": "",
                "digital_fee": "",
                "est_shipping": "",
                "vat_adjusted_price": "",
                "break_even": "",
                "min_sell_price": "",
                "scan_day": rec.get("recommendation_utc", ""),
                "title": rec.get("supplier_title", ""),
                "sales": "",
                "rating": "",
                "date": "",
                "variant_reviews": "",
                "reviews_list": "",
                "point_score": rec.get("estimated_roi_pct", ""),
                "history_score": "",
                "pf": pf,
                "status_reason": status_reason,
                "candidate_id": candidate_id,
                "supplier_sku": rec.get("supplier_sku", ""),
                "recommendation_status": rec.get("recommendation_status", ""),
                "recommended_test_qty": recommended_qty,
            }
        )

        second_rows.append(
            {
                "sku": rec.get("supplier_sku", ""),
                "barcode": _normalize_digits(rec.get("barcode", "")),
                "cost": rec.get("unit_cost", ""),
                "vat": rec.get("vat_rate", ""),
                "supplier": rec.get("supplier_name", ""),
                "asin": "",
                "main_rank": "",
                "start_date": "",
                "brand": "",
                "size_1": "",
                "size_2": "",
                "size_3": "",
                "weight": "",
                "dg_pass": "",
                "hazmat": "",
                "buy_box_price": "",
                "lowest_afn_price": "",
                "lowest_mfn_price": "",
                "reasonable_price": "",
                "fba_fee": "",
                "referral_fee": "",
                "digital_fee": "",
                "est_shipping": "",
                "vat_adjusted_price": "",
                "break_even": "",
                "min_sell_price": "",
                "scan_day": rec.get("recommendation_utc", ""),
                "title": rec.get("supplier_title", ""),
                "sales": "",
                "rating": "",
                "product_info": "",
                "variant_reviews": "",
                "reviews_list": "",
                "point_score": rec.get("estimated_roi_pct", ""),
                "pf": pf,
                "max_qty": recommended_qty,
                "p": "1" if recommendation_status == "approve_test_buy" else "",
                "f": "1" if recommendation_status != "approve_test_buy" else "",
                "send": send_value,
                "candidate_id": candidate_id,
                "decision_status": decision_status,
                "decision_action": decision_action,
                "status_reason": status_reason,
            }
        )

    first_df = _write_contract_df(pd.DataFrame(first_rows), "feeder_legacy_first_checks_live", root_path)
    second_df = _write_contract_df(pd.DataFrame(second_rows), "feeder_legacy_second_checks_live", root_path)

    first_pass = int((first_df["pf"] == "PASS").sum()) if not first_df.empty else 0
    first_fail = int((first_df["pf"] == "FAIL").sum()) if not first_df.empty else 0
    first_unprocessed = int((first_df["pf"] == "").sum()) if not first_df.empty else 0
    first_rescan = int(first_df["status_reason"].str.contains("rescan", case=False, na=False).sum()) if not first_df.empty else 0

    second_pass = int((second_df["send"] == "SEND").sum()) if not second_df.empty else 0
    second_unprocessed = int((second_df["send"] == "").sum()) if not second_df.empty else 0
    second_fail = max(len(second_df) - second_pass - second_unprocessed, 0)

    bot_status = "In Process"
    if len(first_df) == 0:
        bot_status = "No Rows"
    elif second_unprocessed == 0:
        bot_status = "Complete"

    bot_df = _write_contract_df(
        pd.DataFrame(
            [
                {
                    "supplier": supplier_id,
                    "run_utc": observed_utc,
                    "status": bot_status,
                    "first_unprocessed": str(first_unprocessed),
                    "first_pass": str(first_pass),
                    "first_fail": str(first_fail),
                    "first_rescan": str(first_rescan),
                    "second_unprocessed": str(second_unprocessed),
                    "second_pass": str(second_pass),
                    "second_fail": str(second_fail),
                }
            ]
        ),
        "feeder_legacy_bot_status_live",
        root_path,
    )

    quality_status = "ok"
    quality_note = f"first_rows={len(first_df)};second_rows={len(second_df)}"
    if len(first_df) == 0:
        quality_status = "warn"
        quality_note = "no_rows_in_supplier_scope"

    send_status = "ok" if send_ready_count > 0 else "warn"
    send_note = "send_ready_rows_present" if send_ready_count > 0 else "no_send_ready_rows"

    health_df = _write_contract_df(
        pd.DataFrame(
            [
                {
                    "check": "feeder_legacy_sheet_source_contract",
                    "status": "ok",
                    "value": str(len(rec_work)),
                    "notes": "recommendations_contract_valid",
                    "observed_utc": observed_utc,
                    "source_path": str(rec_path),
                },
                {
                    "check": "feeder_legacy_sheet_quality",
                    "status": quality_status,
                    "value": str(len(first_df)),
                    "notes": quality_note,
                    "observed_utc": observed_utc,
                    "source_path": str(rec_path),
                },
                {
                    "check": "feeder_legacy_sheet_send_ready",
                    "status": send_status,
                    "value": str(send_ready_count),
                    "notes": send_note,
                    "observed_utc": observed_utc,
                    "source_path": str(decisions_path),
                },
            ]
        ),
        "feeder_legacy_sheet_health",
        root_path,
    )

    print(
        {
            "status": "success",
            "supplier_id": supplier_id,
            "first_checks_rows": int(len(first_df)),
            "second_checks_rows": int(len(second_df)),
            "bot_status_rows": int(len(bot_df)),
            "send_ready_rows": int(send_ready_count),
            "health_quality_status": quality_status,
        }
    )
    return first_df, second_df, bot_df, health_df


def main() -> None:
    parser = argparse.ArgumentParser(description="Build local legacy sheet style review pack for one supplier.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--supplier-id", required=True)
    parser.add_argument("--review-utc", default=None)
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    build_legacy_sheet_review_pack(
        root=root,
        supplier_id=args.supplier_id,
        review_utc=args.review_utc,
    )


if __name__ == "__main__":
    main()
