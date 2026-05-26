from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._profit_model import calculate_fee_based_profit_per_unit
from scripts.core.storage import read_review_pack_dataframe


DEFAULT_PASS_PATH = ROOT / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
DEFAULT_NEAR_MISS_PATH = ROOT / "out" / "analysis_reports" / "f_live_price_file_near_miss_review_latest.csv"
DEFAULT_FIRST_CHECKS_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_legacy_first_checks_live.csv"
DEFAULT_SCRAPE_EVIDENCE_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv"
DEFAULT_OUTPUT_PATH = ROOT / "out" / "analysis_reports" / "f_profit_formula_conflict_audit_latest.csv"

REQUIRED_COLUMNS = [
    "candidate_id",
    "supplier_sku",
    "asin",
    "title",
    "review_pack_type",
    "price_basis",
    "units_basis",
    "old_profit_per_unit_gbp",
    "corrected_profit_per_unit_gbp",
    "old_expected_profit_next_30d_gbp",
    "corrected_expected_profit_next_30d_gbp",
    "profit_delta_per_unit_gbp",
    "profit_delta_total_gbp",
    "cost",
    "fba_fee",
    "referral_fee",
    "digital_fee",
    "est_shipping",
    "vat",
    "api_live_price",
    "bbp_live_sell_price",
    "bbp_30d_avg_price",
    "break_even",
    "profit_formula_code",
    "recommended_action",
    "evidence_source",
]

FORMULA_CODE_INFLATED = "profit_inflated_break_even_subtraction"
FORMULA_CODE_CLEAR = "profit_clear"
FORMULA_CODE_MISSING = "profit_missing_inputs_rescan_needed"
FORMULA_CODE_REVIEW = "profit_formula_review_needed"

RECOMMENDED_ACTION_BY_CODE = {
    FORMULA_CODE_INFLATED: "remove_from_clean_pass",
    FORMULA_CODE_CLEAR: "allow_if_other_checks_pass",
    FORMULA_CODE_MISSING: "targeted_rescan_needed",
    FORMULA_CODE_REVIEW: "manual_review",
}


@dataclass(frozen=True)
class ProfitFormulaConflictAuditResult:
    audit_df: pd.DataFrame
    output_path: Path
    report: dict[str, Any]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _read_review_pack(path: Path, pack_type: str) -> pd.DataFrame:
    return read_review_pack_dataframe(path, pack_type=pack_type, dtype=str).fillna("")


def _num_or_none(value: object) -> float | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    cleaned = raw.replace(",", "").replace("GBP", "").replace("gbp", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _num_to_text(value: float | None) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


def _latest_by_keys(df: pd.DataFrame, keys: list[str], utc_columns: list[str]) -> dict[tuple[str, ...], dict[str, str]]:
    if df.empty:
        return {}
    work = df.copy()
    for idx, key in enumerate(keys):
        work[f"_key_{idx}"] = work.get(key, "").map(_normalize_key)
    utc_series = None
    for column in utc_columns:
        if column not in work.columns:
            continue
        parsed = pd.to_datetime(work[column].map(_normalize_text), errors="coerce", utc=True, format="mixed")
        utc_series = parsed if utc_series is None else utc_series.fillna(parsed)
    if utc_series is not None:
        work["_obs_ts"] = utc_series
        work = work.sort_values("_obs_ts", ascending=False, kind="stable")

    out: dict[tuple[str, ...], dict[str, str]] = {}
    for _, row in work.iterrows():
        key_tuple = tuple(_normalize_key(row.get(f"_key_{idx}", "")) for idx in range(len(keys)))
        if any(token == "" for token in key_tuple):
            continue
        if key_tuple in out:
            continue
        out[key_tuple] = {column: _normalize_text(value) for column, value in row.to_dict().items()}
    return out


def _lookup_with_fallback(
    primary: dict[tuple[str, ...], dict[str, str]],
    primary_key: tuple[str, ...],
    secondary: dict[tuple[str, ...], dict[str, str]] | None = None,
    secondary_key: tuple[str, ...] | None = None,
) -> dict[str, str]:
    if primary_key in primary:
        return primary[primary_key]
    if secondary is not None and secondary_key is not None and secondary_key in secondary:
        return secondary[secondary_key]
    return {}


def _select_price_basis(*, row: dict[str, str], first_checks: dict[str, str], scrape: dict[str, str]) -> tuple[float | None, str]:
    candidates = [
        ("avg_30_day_price", _num_or_none(scrape.get("avg_30_day_price", ""))),
        ("bbp_30d_avg_price_scrape", _num_or_none(scrape.get("bbp_30d_avg_price", ""))),
        ("bbp_30d_avg_price_first_checks", _num_or_none(first_checks.get("bbp_30d_avg_price", ""))),
        ("api_live_price_scrape", _num_or_none(scrape.get("api_live_price", ""))),
        ("api_live_price_first_checks", _num_or_none(first_checks.get("api_live_price", ""))),
        ("bbp_live_sell_price_scrape", _num_or_none(scrape.get("bbp_live_sell_price", ""))),
        ("bbp_live_sell_price_first_checks", _num_or_none(first_checks.get("bbp_live_sell_price", ""))),
    ]
    for basis, value in candidates:
        if value is not None and value > 0:
            return value, basis
    return None, ""


def _select_referral_basis_price(*, first_checks: dict[str, str], scrape: dict[str, str], sale_price: float | None) -> float | None:
    for field in (
        "api_live_price",
        "reasonable_price",
        "buy_box_price",
        "bbp_live_sell_price",
        "bbp_30d_avg_price",
    ):
        value = _num_or_none(first_checks.get(field, ""))
        if value is not None and value > 0:
            return value
    for field in ("api_live_price", "bbp_live_sell_price", "bbp_30d_avg_price"):
        value = _num_or_none(scrape.get(field, ""))
        if value is not None and value > 0:
            return value
    return sale_price


def _classify_row(
    *,
    old_profit_per_unit: float | None,
    corrected_profit_per_unit: float | None,
    sale_price: float | None,
    break_even: float | None,
    missing_inputs: tuple[str, ...],
) -> str:
    if missing_inputs:
        return FORMULA_CODE_MISSING
    if old_profit_per_unit is None or corrected_profit_per_unit is None:
        return FORMULA_CODE_REVIEW
    if sale_price is None or break_even is None:
        profit_delta = old_profit_per_unit - corrected_profit_per_unit
        if abs(profit_delta) <= 0.05:
            return FORMULA_CODE_CLEAR
        if profit_delta > 0:
            return FORMULA_CODE_REVIEW
        return FORMULA_CODE_REVIEW

    implied_old = sale_price - break_even
    matches_break_even_subtraction = abs(old_profit_per_unit - implied_old) <= 0.05
    profit_delta = old_profit_per_unit - corrected_profit_per_unit

    if matches_break_even_subtraction and profit_delta > 0.25:
        return FORMULA_CODE_INFLATED
    if abs(profit_delta) <= 0.05:
        return FORMULA_CODE_CLEAR
    return FORMULA_CODE_REVIEW


def _build_review_rows(pass_df: pd.DataFrame, near_miss_df: pd.DataFrame) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for _, row in pass_df.iterrows():
        payload = {key: _normalize_text(value) for key, value in row.to_dict().items()}
        payload["review_pack_type"] = "passes"
        rows.append(payload)
    for _, row in near_miss_df.iterrows():
        payload = {key: _normalize_text(value) for key, value in row.to_dict().items()}
        payload["review_pack_type"] = "near_misses"
        rows.append(payload)
    return rows


def build_profit_formula_conflict_audit(
    *,
    pass_path: Path = DEFAULT_PASS_PATH,
    near_miss_path: Path = DEFAULT_NEAR_MISS_PATH,
    first_checks_path: Path = DEFAULT_FIRST_CHECKS_PATH,
    scrape_evidence_path: Path = DEFAULT_SCRAPE_EVIDENCE_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    observed_utc: str | None = None,
) -> ProfitFormulaConflictAuditResult:
    observed_utc_value = _normalize_text(observed_utc) or _utc_now_iso()

    pass_df = _read_review_pack(pass_path, "passes")
    near_miss_df = _read_review_pack(near_miss_path, "near_misses")
    first_checks_df = _read_csv(first_checks_path)
    scrape_df = _read_csv(scrape_evidence_path)

    first_checks_by_candidate = _latest_by_keys(first_checks_df, ["candidate_id"], ["scan_day"])
    first_checks_by_supplier_asin = _latest_by_keys(first_checks_df, ["supplier_sku", "asin"], ["scan_day"])
    scrape_by_candidate = _latest_by_keys(scrape_df, ["candidate_id"], ["observed_utc", "scan_day"])
    scrape_by_supplier_asin = _latest_by_keys(scrape_df, ["supplier_sku", "asin"], ["observed_utc", "scan_day"])

    rows = _build_review_rows(pass_df, near_miss_df)
    audit_rows: list[dict[str, str]] = []
    for row in rows:
        candidate_id = _normalize_text(row.get("candidate_id", ""))
        supplier_sku = _normalize_text(row.get("supplier_sku", ""))
        asin = _normalize_text(row.get("asin", ""))
        review_pack_type = _normalize_text(row.get("review_pack_type", ""))
        candidate_key = (_normalize_key(candidate_id),)
        supplier_asin_key = (_normalize_key(supplier_sku), _normalize_key(asin))
        first_checks = _lookup_with_fallback(
            first_checks_by_candidate,
            candidate_key,
            first_checks_by_supplier_asin,
            supplier_asin_key,
        )
        scrape = _lookup_with_fallback(
            scrape_by_candidate,
            candidate_key,
            scrape_by_supplier_asin,
            supplier_asin_key,
        )

        units = _num_or_none(row.get("expected_units_next_30d", ""))
        units_basis = "expected_units_next_30d" if units is not None else ""
        old_profit_per_unit = _num_or_none(row.get("profit_per_unit_30d_gbp", ""))
        old_expected_profit = _num_or_none(row.get("expected_profit_next_30d_gbp", ""))
        if old_expected_profit is None and units is not None and old_profit_per_unit is not None:
            old_expected_profit = units * old_profit_per_unit
        sale_price, price_basis = _select_price_basis(row=row, first_checks=first_checks, scrape=scrape)

        cost = _num_or_none(first_checks.get("cost", ""))
        fba_fee = _num_or_none(first_checks.get("fba_fee", ""))
        referral_fee = _num_or_none(first_checks.get("referral_fee", ""))
        digital_fee = _num_or_none(first_checks.get("digital_fee", ""))
        est_shipping = _num_or_none(first_checks.get("est_shipping", ""))
        vat = _num_or_none(first_checks.get("vat", ""))
        referral_basis_price = _select_referral_basis_price(
            first_checks=first_checks,
            scrape=scrape,
            sale_price=sale_price,
        )
        fee_profit = calculate_fee_based_profit_per_unit(
            sale_price_gbp=sale_price,
            vat_rate_pct=vat,
            product_cost_gbp=cost,
            fba_fee_gbp=fba_fee,
            referral_fee_gbp=referral_fee,
            digital_fee_gbp=digital_fee,
            est_shipping_gbp=est_shipping,
            referral_fee_basis_price_gbp=referral_basis_price,
            recalculate_referral_fee=True,
            recalculate_digital_fee=True,
        )
        corrected_profit_per_unit = fee_profit.profit_per_unit_gbp
        corrected_expected_profit = (
            corrected_profit_per_unit * units
            if corrected_profit_per_unit is not None and units is not None
            else None
        )
        profit_delta_per_unit = (
            old_profit_per_unit - corrected_profit_per_unit
            if old_profit_per_unit is not None and corrected_profit_per_unit is not None
            else None
        )
        profit_delta_total = (
            old_expected_profit - corrected_expected_profit
            if old_expected_profit is not None and corrected_expected_profit is not None
            else None
        )
        break_even = _num_or_none(first_checks.get("break_even", "")) or _num_or_none(scrape.get("break_even", ""))
        formula_code = _classify_row(
            old_profit_per_unit=old_profit_per_unit,
            corrected_profit_per_unit=corrected_profit_per_unit,
            sale_price=sale_price,
            break_even=break_even,
            missing_inputs=fee_profit.missing_inputs,
        )
        recommended_action = RECOMMENDED_ACTION_BY_CODE.get(formula_code, "manual_review")
        title = _normalize_text(row.get("title", "")) or _normalize_text(first_checks.get("title", "")) or _normalize_text(
            scrape.get("title", "")
        )
        evidence_source = (
            f"review_pack:{review_pack_type}|first_checks:{first_checks_path.name}|scrape:{scrape_evidence_path.name}"
        )
        audit_rows.append(
            {
                "candidate_id": candidate_id,
                "supplier_sku": supplier_sku,
                "asin": asin,
                "title": title,
                "review_pack_type": review_pack_type,
                "price_basis": price_basis,
                "units_basis": units_basis,
                "old_profit_per_unit_gbp": _num_to_text(old_profit_per_unit),
                "corrected_profit_per_unit_gbp": _num_to_text(corrected_profit_per_unit),
                "old_expected_profit_next_30d_gbp": _num_to_text(old_expected_profit),
                "corrected_expected_profit_next_30d_gbp": _num_to_text(corrected_expected_profit),
                "profit_delta_per_unit_gbp": _num_to_text(profit_delta_per_unit),
                "profit_delta_total_gbp": _num_to_text(profit_delta_total),
                "cost": _num_to_text(cost),
                "fba_fee": _num_to_text(fba_fee),
                "referral_fee": _num_to_text(referral_fee),
                "digital_fee": _num_to_text(digital_fee),
                "est_shipping": _num_to_text(est_shipping),
                "vat": _num_to_text(vat),
                "api_live_price": _normalize_text(first_checks.get("api_live_price", "")) or _normalize_text(
                    scrape.get("api_live_price", "")
                ),
                "bbp_live_sell_price": _normalize_text(first_checks.get("bbp_live_sell_price", "")) or _normalize_text(
                    scrape.get("bbp_live_sell_price", "")
                ),
                "bbp_30d_avg_price": _normalize_text(first_checks.get("bbp_30d_avg_price", "")) or _normalize_text(
                    scrape.get("bbp_30d_avg_price", "")
                ),
                "break_even": _num_to_text(break_even),
                "profit_formula_code": formula_code,
                "recommended_action": recommended_action,
                "evidence_source": evidence_source,
            }
        )

    audit_df = pd.DataFrame(audit_rows, columns=REQUIRED_COLUMNS)
    if audit_df.empty:
        audit_df = pd.DataFrame(columns=REQUIRED_COLUMNS)
    else:
        audit_df = audit_df.sort_values(
            by=["profit_formula_code", "review_pack_type", "asin", "candidate_id", "supplier_sku"],
            ascending=[True, True, True, True, True],
            kind="stable",
        ).reset_index(drop=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    audit_df.to_csv(output_path, index=False)

    profit_formula_counts = (
        {str(key): int(value) for key, value in audit_df["profit_formula_code"].value_counts().sort_index().items()}
        if not audit_df.empty
        else {}
    )
    recommended_action_counts = (
        {str(key): int(value) for key, value in audit_df["recommended_action"].value_counts().sort_index().items()}
        if not audit_df.empty
        else {}
    )
    unclassified_rows = 0
    if not audit_df.empty:
        valid_codes = {
            FORMULA_CODE_INFLATED,
            FORMULA_CODE_CLEAR,
            FORMULA_CODE_MISSING,
            FORMULA_CODE_REVIEW,
        }
        unclassified_rows += int((~audit_df["profit_formula_code"].isin(valid_codes)).sum())
        unclassified_rows += int((audit_df["recommended_action"].map(_normalize_text) == "").sum())

    report = {
        "observed_utc": observed_utc_value,
        "pass_path": str(pass_path),
        "near_miss_path": str(near_miss_path),
        "first_checks_path": str(first_checks_path),
        "scrape_evidence_path": str(scrape_evidence_path),
        "output_path": str(output_path),
        "rows": int(len(audit_df.index)),
        "profit_formula_counts": profit_formula_counts,
        "recommended_action_counts": recommended_action_counts,
        "unclassified_rows": int(unclassified_rows),
    }
    return ProfitFormulaConflictAuditResult(audit_df=audit_df, output_path=output_path, report=report)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit F review-pack profit inflation against fee-based profit model.")
    parser.add_argument("--pass-path", type=Path, default=DEFAULT_PASS_PATH)
    parser.add_argument("--near-miss-path", type=Path, default=DEFAULT_NEAR_MISS_PATH)
    parser.add_argument("--first-checks-path", type=Path, default=DEFAULT_FIRST_CHECKS_PATH)
    parser.add_argument("--scrape-evidence-path", type=Path, default=DEFAULT_SCRAPE_EVIDENCE_PATH)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--observed-utc", default="")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = build_profit_formula_conflict_audit(
        pass_path=args.pass_path,
        near_miss_path=args.near_miss_path,
        first_checks_path=args.first_checks_path,
        scrape_evidence_path=args.scrape_evidence_path,
        output_path=args.output_path,
        observed_utc=_normalize_text(args.observed_utc) or None,
    )
    print(json.dumps(result.report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
