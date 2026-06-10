from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.safe_file_writes import safe_to_csv


OUT = Path("out")
LEVEL3_RAW = OUT / "financial_events_level3_raw.csv"
LEVEL3_SUMMARY = OUT / "financial_events_level3_summary.csv"
LEVEL3_OFFICIAL = OUT / "financial_events_level3_official.csv"
REFUNDS = OUT / "financial_events_refunds.csv"
REFUNDS_OFFICIAL = OUT / "financial_events_refunds_official.csv"
ORDER_MASTER = OUT / "order_master.csv"
FEE_DETAIL_API = OUT / "fee_detail_ledger_api.csv"
TRANSACTION_BREAKDOWNS = OUT / "financial_transactions_v2024_breakdowns.csv"
OUT_MAP = OUT / "systems" / "B" / "refunds" / "b_level3_fee_shipping_api_proof_map.csv"
OUT_SUMMARY = OUT / "systems" / "B" / "refunds" / "b_level3_fee_shipping_api_proof_map_summary.csv"

PROOF_LABELS = {
    "api_source_available",
    "api_source_missing",
    "repo_path_unclear",
    "protected_live_pull_required",
    "superseded_non_blocking",
}

MAP_COLUMNS = [
    "money_field",
    "api_source_file",
    "source_amount_types",
    "source_row_count",
    "official_output_file",
    "official_output_field",
    "official_output_row_count",
    "order_master_row_count",
    "required_keys_present",
    "missing_required_keys",
    "proof_label",
    "proof_reason",
    "live_roi_use_allowed",
    "roi_or_restock_use_allowed",
    "sellerboard_final_truth_allowed",
    "bounded_worker_task",
    "retest_rule",
    "protected_stop_rule",
]

SUMMARY_COLUMNS = ["metric", "value"]

RAW_REQUIRED_KEYS = ["order_id", "sku", "posted_date", "amount_type", "amount", "currency"]
FEE_DETAIL_REQUIRED_KEYS = ["posted_date", "transaction_id", "fee_type", "amount_total", "currency"]


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame()


def _text(value: object) -> str:
    return str(value or "").strip()


def _nonzero_count(df: pd.DataFrame, column: str) -> int:
    if df.empty or column not in df.columns:
        return 0
    values = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    return int((values.abs() > 0.0000005).sum())


def _count_amount_types(df: pd.DataFrame, amount_types: list[str]) -> int:
    if df.empty or "amount_type" not in df.columns:
        return 0
    return int(df["amount_type"].astype(str).str.strip().isin(amount_types).sum())


def _missing_keys(df: pd.DataFrame, required: list[str], *, amount_types: list[str] | None = None) -> list[str]:
    if df.empty:
        return list(required)
    work = df
    if amount_types and "amount_type" in work.columns:
        work = work[work["amount_type"].astype(str).str.strip().isin(amount_types)].copy()
    missing: list[str] = []
    for column in required:
        if column not in work.columns:
            missing.append(column)
        elif not work.empty and int((work[column].astype(str).str.strip() == "").sum()) == len(work):
            missing.append(column)
    return missing


def _breakdown_type_counts(breakdowns: pd.DataFrame) -> str:
    if breakdowns.empty or "transaction_type" not in breakdowns.columns:
        return "missing"
    counts = breakdowns["transaction_type"].astype(str).str.strip().value_counts().to_dict()
    return ";".join(f"{key}={value}" for key, value in sorted(counts.items()))


def _append_field(
    rows: list[dict[str, str]],
    *,
    money_field: str,
    source_file: Path,
    source_amount_types: list[str],
    source_row_count: int,
    official_file: Path,
    official_field: str,
    official_output_row_count: int,
    order_master_row_count: int,
    missing_required_keys: list[str],
    proof_label: str,
    proof_reason: str,
) -> None:
    rows.append(
        {
            "money_field": money_field,
            "api_source_file": str(source_file),
            "source_amount_types": "|".join(source_amount_types),
            "source_row_count": str(source_row_count),
            "official_output_file": str(official_file),
            "official_output_field": official_field,
            "official_output_row_count": str(official_output_row_count),
            "order_master_row_count": str(order_master_row_count),
            "required_keys_present": "1" if not missing_required_keys else "0",
            "missing_required_keys": ";".join(missing_required_keys),
            "proof_label": proof_label if proof_label in PROOF_LABELS else "repo_path_unclear",
            "proof_reason": proof_reason,
            "live_roi_use_allowed": "0",
            "roi_or_restock_use_allowed": "0",
            "sellerboard_final_truth_allowed": "0",
            "bounded_worker_task": (
                "Use this read-only map to decide the next API proof step. "
                "Do not write fee/shipping facts into live ROI or restocking in this packet."
            ),
            "retest_rule": "Rerun B068, then rerun read-only B MOT. The same MOT row must clear or remain warning-labelled.",
            "protected_stop_rule": (
                "Stop before live Amazon API pulling, B run/restart, Sheet write, local DB alignment, "
                "output deletion, ROI/restocking use, price change, queue change, or Sellerboard-final truth."
            ),
        }
    )


def build_level3_fee_shipping_api_proof_map(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
) -> dict[str, pd.DataFrame]:
    root_path = Path(root or ".")
    observed = observed_utc or _utc_now_text()
    raw_path = root_path / LEVEL3_RAW
    official_path = root_path / LEVEL3_OFFICIAL
    refunds_path = root_path / REFUNDS
    refunds_official_path = root_path / REFUNDS_OFFICIAL
    order_master_path = root_path / ORDER_MASTER
    fee_detail_path = root_path / FEE_DETAIL_API
    breakdown_path = root_path / TRANSACTION_BREAKDOWNS

    raw = _read_csv(raw_path)
    official = _read_csv(official_path)
    refunds = _read_csv(refunds_path)
    refunds_official = _read_csv(refunds_official_path)
    order_master = _read_csv(order_master_path)
    fee_detail = _read_csv(fee_detail_path)
    breakdowns = _read_csv(breakdown_path)

    rows: list[dict[str, str]] = []
    field_specs = [
        (
            "commission",
            raw_path,
            raw,
            ["Commission"],
            official_path,
            "Commission_ExVAT",
            _nonzero_count(official, "Commission_ExVAT"),
            _nonzero_count(order_master, "Commission_ExVAT"),
            "api_source_available",
            "Level 3 raw and official outputs contain order-level commission lines.",
        ),
        (
            "fba_fee",
            raw_path,
            raw,
            ["FBAPerUnitFulfillmentFee"],
            official_path,
            "FBA_Fee_ExVAT",
            _nonzero_count(official, "FBA_Fee_ExVAT"),
            _nonzero_count(order_master, "FBA_Fee_ExVAT"),
            "api_source_available",
            "Level 3 raw and official outputs contain order-level FBA fee lines.",
        ),
        (
            "shipping_income",
            raw_path,
            raw,
            ["ShippingCharge", "ShippingTax"],
            official_path,
            "Shipping_ExVAT",
            _nonzero_count(official, "Shipping_ExVAT"),
            _nonzero_count(order_master, "Shipping_ExVAT"),
            "api_source_available",
            "Level 3 raw and official outputs contain customer shipping income lines.",
        ),
        (
            "shipping_chargeback_or_cost",
            raw_path,
            raw,
            ["ShippingChargeback"],
            official_path,
            "",
            0,
            0,
            "api_source_available",
            (
                "Level 3 raw has API-backed shipping chargeback lines with order, SKU, posted date, amount, and currency. "
                "The current official/order-master outputs do not expose a named shipping-cost field, so live ROI use remains blocked."
            ),
        ),
        (
            "refund_fee_reversals",
            refunds_path,
            refunds,
            [
                "Refund_Commission",
                "Refund_RefundCommission",
                "Refund_ShippingChargeback",
                "Refund_FixedClosingFee",
                "Refund_VariableClosingFee",
                "Refund_DigitalServicesFee",
            ],
            refunds_official_path,
            "refund_fee_reversal_fields",
            len(refunds_official),
            0,
            "api_source_available",
            "Level 3 refund outputs contain refund fee reversal amount types.",
        ),
    ]
    for (
        money_field,
        source_file,
        source_df,
        amount_types,
        official_file,
        official_field,
        official_count,
        order_master_count,
        default_label,
        reason,
    ) in field_specs:
        source_count = _count_amount_types(source_df, amount_types)
        missing = _missing_keys(source_df, RAW_REQUIRED_KEYS, amount_types=amount_types)
        label = default_label
        if source_count == 0:
            label = "api_source_missing"
        elif missing:
            label = "repo_path_unclear"
        _append_field(
            rows,
            money_field=money_field,
            source_file=source_file,
            source_amount_types=amount_types,
            source_row_count=source_count,
            official_file=official_file,
            official_field=official_field,
            official_output_row_count=official_count,
            order_master_row_count=order_master_count,
            missing_required_keys=missing,
            proof_label=label,
            proof_reason=reason,
        )

    useful_level3_fields = {
        "commission",
        "fba_fee",
        "shipping_income",
        "shipping_chargeback_or_cost",
        "refund_fee_reversals",
    }
    useful_level3_available = {
        row["money_field"]
        for row in rows
        if row.get("money_field") in useful_level3_fields and row.get("proof_label") == "api_source_available"
    }
    fee_detail_missing = _missing_keys(fee_detail, FEE_DETAIL_REQUIRED_KEYS)
    breakdown_summary = _breakdown_type_counts(breakdowns)
    fee_detail_label = "api_source_available"
    if len(fee_detail) and not fee_detail_missing:
        fee_detail_label = "api_source_available"
    elif len(fee_detail) == 0 and useful_level3_available == useful_level3_fields:
        fee_detail_label = "superseded_non_blocking"
    elif len(fee_detail) == 0:
        fee_detail_label = "api_source_missing"
    else:
        fee_detail_label = "repo_path_unclear"
    _append_field(
        rows,
        money_field="fee_detail_ledger_api",
        source_file=fee_detail_path,
        source_amount_types=["ServiceFee"],
        source_row_count=len(fee_detail),
        official_file=breakdown_path,
        official_field="transaction_breakdown_diagnostic",
        official_output_row_count=len(breakdowns),
        order_master_row_count=0,
        missing_required_keys=fee_detail_missing if len(fee_detail) else [],
        proof_label=fee_detail_label,
        proof_reason=(
            "This file is empty because the current v2024 transaction breakdown path has "
            f"{breakdown_summary}, not ServiceFee rows. It should not be the main proof source for order commission/FBA/shipping."
        ),
    )

    proof_map = pd.DataFrame(rows, columns=MAP_COLUMNS).fillna("")
    unsafe_rows = (
        int((proof_map["live_roi_use_allowed"].astype(str).str.strip() != "0").sum())
        + int((proof_map["roi_or_restock_use_allowed"].astype(str).str.strip() != "0").sum())
        + int((proof_map["sellerboard_final_truth_allowed"].astype(str).str.strip() != "0").sum())
        if not proof_map.empty
        else 0
    )
    unclassified_rows = int((~proof_map["proof_label"].isin(PROOF_LABELS)).sum()) if not proof_map.empty else 0
    counts = {
        label: int((proof_map["proof_label"] == label).sum()) if not proof_map.empty else 0
        for label in sorted(PROOF_LABELS)
    }
    status = "ok"
    if unsafe_rows or unclassified_rows:
        status = "fail"
    elif counts["api_source_missing"] or counts["repo_path_unclear"] or counts["protected_live_pull_required"]:
        status = "warn"

    summary_rows = [
        {"metric": "status", "value": status},
        {"metric": "observed_utc", "value": observed},
        {"metric": "proof_rows", "value": str(len(proof_map))},
        {"metric": "api_source_available_rows", "value": str(counts["api_source_available"])},
        {"metric": "api_source_missing_rows", "value": str(counts["api_source_missing"])},
        {"metric": "repo_path_unclear_rows", "value": str(counts["repo_path_unclear"])},
        {"metric": "protected_live_pull_required_rows", "value": str(counts["protected_live_pull_required"])},
        {"metric": "superseded_non_blocking_rows", "value": str(counts["superseded_non_blocking"])},
        {"metric": "unsafe_rows", "value": str(unsafe_rows)},
        {"metric": "unclassified_rows", "value": str(unclassified_rows)},
        {"metric": "level3_raw_rows", "value": str(len(raw))},
        {"metric": "level3_summary_rows", "value": str(len(_read_csv(root_path / LEVEL3_SUMMARY)))},
        {"metric": "level3_official_rows", "value": str(len(official))},
        {"metric": "order_master_rows", "value": str(len(order_master))},
        {"metric": "fee_detail_ledger_api_rows", "value": str(len(fee_detail))},
        {"metric": "transaction_breakdown_rows", "value": str(len(breakdowns))},
    ]
    summary = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS).fillna("")
    return {"proof_map": proof_map, "summary": summary}


def write_level3_fee_shipping_api_proof_map_outputs(
    result: dict[str, pd.DataFrame],
    *,
    root: Path | str | None = None,
) -> dict[str, Path]:
    root_path = Path(root or ".")
    map_path = root_path / OUT_MAP
    summary_path = root_path / OUT_SUMMARY
    safe_to_csv(result["proof_map"], map_path, index=False)
    safe_to_csv(result["summary"], summary_path, index=False)
    return {"proof_map": map_path, "summary": summary_path}


def main() -> None:
    result = build_level3_fee_shipping_api_proof_map()
    paths = write_level3_fee_shipping_api_proof_map_outputs(result)
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}
    print(
        {
            "status": summary.get("status", ""),
            "proof_rows": summary.get("proof_rows", "0"),
            "api_source_available_rows": summary.get("api_source_available_rows", "0"),
            "repo_path_unclear_rows": summary.get("repo_path_unclear_rows", "0"),
            "api_source_missing_rows": summary.get("api_source_missing_rows", "0"),
            "proof_map": str(paths["proof_map"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
