from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
POLICY_REL_PATH = Path("config") / "feeder" / "f_scanner_timeout_policy.csv"

POLICY_COLUMNS = [
    "fail_code",
    "enabled",
    "timeout_mode",
    "timeout_days",
    "max_timeout_days",
    "cost_change_resets_flag",
    "source_change_resets_flag",
    "manual_review_required_flag",
    "notes",
    "updated_at_utc",
]

ALLOWED_TIMEOUT_MODES = {
    "fixed_days",
    "until_cost_changes",
    "until_source_changes",
    "manual_review",
    "disabled",
}

KNOWN_FAIL_AND_RETRY_CODES = (
    "NOASIN",
    "OVER50K",
    "HAZMATFAIL",
    "NOCOST",
    "ROIFAIL",
    "LOWROI",
    "BRANDFAIL",
    "NODATE",
    "REVIEWFAIL",
    "SCRAPEFAIL",
    "LOWSALESFAIL",
    "SELLERHISTORYFAIL",
    "PRICEHISTORYFAIL",
    "RESCAN",
    "FAIL",
)

DEFAULT_POLICY_BY_CODE: dict[str, dict[str, str]] = {
    "NOASIN": {
        "timeout_mode": "fixed_days",
        "timeout_days": "90",
        "max_timeout_days": "90",
        "notes": "Balanced default: retry unchanged barcode-to-ASIN misses after 90 days.",
    },
    "OVER50K": {
        "timeout_mode": "fixed_days",
        "timeout_days": "90",
        "max_timeout_days": "90",
        "notes": "Balanced default: retry weak rank or demand rows after 90 days.",
    },
    "HAZMATFAIL": {
        "timeout_mode": "fixed_days",
        "timeout_days": "365",
        "max_timeout_days": "365",
        "notes": "Balanced default: hazmat or FBA eligibility rarely changes, so wait 365 days.",
    },
    "NOCOST": {
        "timeout_mode": "until_cost_changes",
        "timeout_days": "",
        "max_timeout_days": "90",
        "cost_change_resets_flag": "1",
        "notes": "Balanced default: rescan on cost change, otherwise retry after 90 days.",
    },
    "ROIFAIL": {
        "timeout_mode": "until_cost_changes",
        "timeout_days": "",
        "max_timeout_days": "90",
        "cost_change_resets_flag": "1",
        "notes": "Balanced default: rescan on cost change, otherwise retry ROI fails after 90 days.",
    },
    "LOWROI": {
        "timeout_mode": "until_cost_changes",
        "timeout_days": "",
        "max_timeout_days": "60",
        "cost_change_resets_flag": "1",
        "notes": "Balanced default: near-threshold weak ROI retries after 60 days unless cost changes sooner.",
    },
    "BRANDFAIL": {
        "timeout_mode": "fixed_days",
        "timeout_days": "180",
        "max_timeout_days": "180",
        "notes": "Balanced default: brand or seller conflict rows wait 180 days.",
    },
    "NODATE": {
        "timeout_mode": "fixed_days",
        "timeout_days": "90",
        "max_timeout_days": "90",
        "notes": "Balanced default: missing date evidence retries after 90 days.",
    },
    "REVIEWFAIL": {
        "timeout_mode": "fixed_days",
        "timeout_days": "90",
        "max_timeout_days": "90",
        "notes": "Balanced default: review evidence failures retry after 90 days.",
    },
    "SCRAPEFAIL": {
        "timeout_mode": "fixed_days",
        "timeout_days": "30",
        "max_timeout_days": "30",
        "notes": "Balanced default: unknown technical scrape failures retry after 30 days.",
    },
    "LOWSALESFAIL": {
        "timeout_mode": "fixed_days",
        "timeout_days": "90",
        "max_timeout_days": "90",
        "notes": "Balanced default: low sales evidence retries after 90 days.",
    },
    "SELLERHISTORYFAIL": {
        "timeout_mode": "fixed_days",
        "timeout_days": "180",
        "max_timeout_days": "180",
        "notes": "Balanced default: seller history risk waits 180 days.",
    },
    "PRICEHISTORYFAIL": {
        "timeout_mode": "fixed_days",
        "timeout_days": "180",
        "max_timeout_days": "180",
        "notes": "Balanced default: missing 365 day price history waits 180 days.",
    },
    "RESCAN": {
        "timeout_mode": "fixed_days",
        "timeout_days": "30",
        "max_timeout_days": "30",
        "notes": "Balanced default: technical retry rows wait 30 days.",
    },
    "FAIL": {
        "timeout_mode": "fixed_days",
        "timeout_days": "90",
        "max_timeout_days": "90",
        "notes": "Balanced default: generic fails retry after 90 days and should be investigated.",
    },
}

FAIL_REASON_DETAILS: dict[str, dict[str, str]] = {
    "NOASIN": {
        "meaning": "Barcode did not resolve to an Amazon ASIN",
        "stage": "catalog",
        "recommendation": "90 days for unchanged barcodes",
    },
    "OVER50K": {
        "meaning": "Rank or demand is too weak",
        "stage": "rank gate",
        "recommendation": "90 days",
    },
    "HAZMATFAIL": {
        "meaning": "FBA eligibility or hazmat check failed",
        "stage": "hazmat gate",
        "recommendation": "365 days",
    },
    "NOCOST": {
        "meaning": "Supplier cost is missing or invalid",
        "stage": "cost gate",
        "recommendation": "until cost changes with a 90 day max",
    },
    "ROIFAIL": {
        "meaning": "ROI clearly fails",
        "stage": "ROI gate",
        "recommendation": "until cost changes with a 90 day max",
    },
    "LOWROI": {
        "meaning": "ROI is weak after scrape evidence",
        "stage": "webscrape",
        "recommendation": "until cost changes with a 60 day max",
    },
    "BRANDFAIL": {
        "meaning": "Brand or seller conflict was detected",
        "stage": "webscrape",
        "recommendation": "180 days or manual review for strategic brands",
    },
    "NODATE": {
        "meaning": "Product date or history evidence is missing",
        "stage": "webscrape",
        "recommendation": "90 days",
    },
    "REVIEWFAIL": {
        "meaning": "Review evidence failed",
        "stage": "webscrape",
        "recommendation": "90 days",
    },
    "SCRAPEFAIL": {
        "meaning": "Technical scrape failure",
        "stage": "webscrape",
        "recommendation": "30 days",
    },
    "LOWSALESFAIL": {
        "meaning": "Sales evidence is too low",
        "stage": "webscrape",
        "recommendation": "90 days",
    },
    "SELLERHISTORYFAIL": {
        "meaning": "Seller or history risk block",
        "stage": "webscrape",
        "recommendation": "180 days",
    },
    "PRICEHISTORYFAIL": {
        "meaning": "No usable 365-day price history was available",
        "stage": "webscrape",
        "recommendation": "180 days",
    },
    "RESCAN": {
        "meaning": "Technical retry is needed",
        "stage": "retry",
        "recommendation": "30 days",
    },
    "FAIL": {
        "meaning": "Generic fail fallback",
        "stage": "unknown",
        "recommendation": "90 days and investigate why generic",
    },
}


@dataclass(frozen=True)
class TimeoutDecision:
    skip: bool
    reason: str
    timeout_until_utc: str
    effective_fail_code: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_code(value: object) -> str:
    return _normalize_text(value).upper()


def _normalize_bool_flag(value: object) -> str:
    raw = _normalize_text(value).lower()
    return "1" if raw in {"1", "true", "yes", "y", "on"} else "0"


def _parse_utc(value: object) -> datetime | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        parsed = pd.to_datetime(raw, errors="coerce", utc=True)
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime()


def _parse_float(value: object) -> float | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    try:
        parsed = float(raw)
    except ValueError:
        return None
    if parsed != parsed:
        return None
    return parsed


def timeout_policy_path(root: Path | None = None) -> Path:
    root_path = Path(root) if root is not None else ROOT
    return root_path / POLICY_REL_PATH


def default_timeout_policy_rows(observed_utc: str | None = None) -> list[dict[str, str]]:
    updated = observed_utc or _utc_now_iso()
    rows: list[dict[str, str]] = []
    for code in KNOWN_FAIL_AND_RETRY_CODES:
        defaults = DEFAULT_POLICY_BY_CODE[code]
        rows.append(
            {
                "fail_code": code,
                "enabled": "1",
                "timeout_mode": defaults.get("timeout_mode", "fixed_days"),
                "timeout_days": defaults.get("timeout_days", ""),
                "max_timeout_days": defaults.get("max_timeout_days", ""),
                "cost_change_resets_flag": defaults.get("cost_change_resets_flag", "0"),
                "source_change_resets_flag": defaults.get("source_change_resets_flag", "0"),
                "manual_review_required_flag": defaults.get("manual_review_required_flag", "0"),
                "notes": defaults.get("notes", ""),
                "updated_at_utc": updated,
            }
        )
    return rows


def default_timeout_policy_df(observed_utc: str | None = None) -> pd.DataFrame:
    return pd.DataFrame(default_timeout_policy_rows(observed_utc), columns=POLICY_COLUMNS)


def finalize_timeout_policy_df(df: pd.DataFrame, *, observed_utc: str | None = None) -> pd.DataFrame:
    out = df.copy()
    for column in POLICY_COLUMNS:
        if column not in out.columns:
            out[column] = ""
    out = out[POLICY_COLUMNS]
    for column in POLICY_COLUMNS:
        out[column] = out[column].map(_normalize_text)
    out["fail_code"] = out["fail_code"].map(_normalize_code)
    for column in ("enabled", "cost_change_resets_flag", "source_change_resets_flag", "manual_review_required_flag"):
        out[column] = out[column].map(_normalize_bool_flag)
    if observed_utc is not None:
        out["updated_at_utc"] = _normalize_text(observed_utc)
    return out


def write_timeout_policy_df(root: Path | None, df: pd.DataFrame, *, observed_utc: str | None = None) -> pd.DataFrame:
    path = timeout_policy_path(root)
    finalized = finalize_timeout_policy_df(df, observed_utc=observed_utc)
    path.parent.mkdir(parents=True, exist_ok=True)
    finalized.to_csv(path, index=False)
    return finalized


def read_timeout_policy_df(
    root: Path | None = None,
    *,
    create_if_missing: bool = True,
    observed_utc: str | None = None,
) -> pd.DataFrame:
    path = timeout_policy_path(root)
    if not path.exists():
        if not create_if_missing:
            return pd.DataFrame(columns=POLICY_COLUMNS)
        return write_timeout_policy_df(root, default_timeout_policy_df(observed_utc), observed_utc=None)
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        df = pd.DataFrame(columns=POLICY_COLUMNS)
    return finalize_timeout_policy_df(df)


def reset_timeout_policy_to_defaults(root: Path | None = None, *, observed_utc: str | None = None) -> pd.DataFrame:
    return write_timeout_policy_df(root, default_timeout_policy_df(observed_utc), observed_utc=None)


def _single_policy_row(policy_df: pd.DataFrame, code: str) -> dict[str, str] | None:
    if policy_df.empty or "fail_code" not in policy_df.columns:
        return None
    matched = policy_df[policy_df["fail_code"].map(_normalize_code) == code].copy()
    if len(matched.index) != 1:
        return None
    return {column: _normalize_text(matched.iloc[0].get(column, "")) for column in POLICY_COLUMNS}


def resolve_timeout_policy_row(policy_df: pd.DataFrame, fail_code: str) -> tuple[dict[str, str], str, bool]:
    finalized = finalize_timeout_policy_df(policy_df)
    requested = _normalize_code(fail_code) or "FAIL"
    row = _single_policy_row(finalized, requested)
    if row is not None:
        return row, requested, False
    fallback = _single_policy_row(finalized, "FAIL")
    if fallback is not None:
        return fallback, "FAIL", True
    synthetic = default_timeout_policy_df()
    fallback = _single_policy_row(synthetic, "FAIL")
    if fallback is None:
        raise RuntimeError("default FAIL timeout policy is missing")
    return fallback, "FAIL", True


def _effective_timeout_days(row: dict[str, str]) -> float | None:
    mode = _normalize_text(row.get("timeout_mode", "")).lower()
    timeout_days = _parse_float(row.get("timeout_days", ""))
    max_timeout_days = _parse_float(row.get("max_timeout_days", ""))
    if mode in {"until_cost_changes", "until_source_changes"} and max_timeout_days is not None:
        return max_timeout_days
    return timeout_days


def timeout_until_utc_for_policy(
    *,
    observed_utc: str,
    fail_code: str,
    policy_df: pd.DataFrame,
) -> str:
    row, _effective_code, _fallback_used = resolve_timeout_policy_row(policy_df, fail_code)
    mode = _normalize_text(row.get("timeout_mode", "")).lower()
    if row.get("enabled") != "1" or mode == "disabled" or mode == "manual_review":
        return ""
    days = _effective_timeout_days(row)
    if days is None or days <= 0:
        return ""
    observed_dt = _parse_utc(observed_utc) or datetime.now(timezone.utc)
    return (observed_dt + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _changed(previous: object, current: object) -> bool:
    old = _normalize_text(previous)
    new = _normalize_text(current)
    return old != "" and new != "" and old != new


def should_skip_for_timeout_policy(
    *,
    fail_code: str,
    policy_df: pd.DataFrame,
    last_scanned_at_utc: str,
    observed_utc: str,
    timeout_until_utc: str = "",
    previous_unit_cost: object = "",
    current_unit_cost: object = "",
    previous_source_hash: object = "",
    current_source_hash: object = "",
) -> TimeoutDecision:
    row, effective_code, fallback_used = resolve_timeout_policy_row(policy_df, fail_code)
    mode = _normalize_text(row.get("timeout_mode", "")).lower()
    if row.get("enabled") != "1" or mode == "disabled":
        return TimeoutDecision(False, "policy_disabled", "", effective_code)
    if mode == "manual_review" or row.get("manual_review_required_flag") == "1":
        return TimeoutDecision(True, "manual_review_required", "", effective_code)
    if row.get("cost_change_resets_flag") == "1" or mode == "until_cost_changes":
        if _changed(previous_unit_cost, current_unit_cost):
            return TimeoutDecision(False, "cost_changed_reset", "", effective_code)
    if row.get("source_change_resets_flag") == "1" or mode == "until_source_changes":
        if _changed(previous_source_hash, current_source_hash):
            return TimeoutDecision(False, "source_changed_reset", "", effective_code)

    timeout_until = _normalize_text(timeout_until_utc)
    if timeout_until == "":
        timeout_until = timeout_until_utc_for_policy(
            observed_utc=last_scanned_at_utc,
            fail_code=effective_code,
            policy_df=policy_df,
        )
    timeout_dt = _parse_utc(timeout_until)
    observed_dt = _parse_utc(observed_utc) or datetime.now(timezone.utc)
    if timeout_dt is not None and timeout_dt > observed_dt:
        reason = "timeout_active_fallback_fail" if fallback_used else "timeout_active"
        return TimeoutDecision(True, reason, timeout_until, effective_code)
    return TimeoutDecision(False, "timeout_expired_or_missing", timeout_until, effective_code)


def _health_row(*, check: str, status: str, value: str, notes: str, observed_utc: str, source_path: Path) -> dict[str, str]:
    return {
        "check": check,
        "status": status,
        "value": value,
        "notes": notes,
        "observed_utc": observed_utc,
        "source_path": str(source_path),
    }


def _policy_code_counts(policy_df: pd.DataFrame) -> dict[str, int]:
    counts: dict[str, int] = {}
    if policy_df.empty or "fail_code" not in policy_df.columns:
        return counts
    for value in policy_df["fail_code"].tolist():
        code = _normalize_code(value)
        if code == "":
            continue
        counts[code] = counts.get(code, 0) + 1
    return counts


def _unknown_codes_from_screening_state(screening_state_df: pd.DataFrame | None) -> list[str]:
    if screening_state_df is None or screening_state_df.empty or "fail_code" not in screening_state_df.columns:
        return []
    known = set(KNOWN_FAIL_AND_RETRY_CODES)
    unknown: set[str] = set()
    for value in screening_state_df["fail_code"].tolist():
        code = _normalize_code(value)
        if code and code not in known:
            unknown.add(code)
    return sorted(unknown)


def _invalid_value_notes(policy_df: pd.DataFrame) -> list[str]:
    notes: list[str] = []
    for index, row in policy_df.iterrows():
        code = _normalize_code(row.get("fail_code", "")) or f"row_{index + 1}"
        mode = _normalize_text(row.get("timeout_mode", "")).lower()
        enabled = _normalize_text(row.get("enabled", ""))
        if enabled not in {"0", "1"}:
            notes.append(f"{code}:invalid_enabled")
        if mode not in ALLOWED_TIMEOUT_MODES:
            notes.append(f"{code}:invalid_mode")
            continue
        if enabled != "1" or mode == "disabled":
            continue
        timeout_days = _parse_float(row.get("timeout_days", ""))
        max_timeout_days = _parse_float(row.get("max_timeout_days", ""))
        if mode == "fixed_days" and (timeout_days is None or timeout_days <= 0):
            notes.append(f"{code}:timeout_days_required")
        if mode in {"until_cost_changes", "until_source_changes"}:
            if max_timeout_days is None or max_timeout_days <= 0:
                notes.append(f"{code}:max_timeout_days_required")
            if timeout_days is not None and timeout_days < 0:
                notes.append(f"{code}:timeout_days_invalid")
        if mode == "manual_review" and _normalize_text(row.get("manual_review_required_flag", "")) != "1":
            notes.append(f"{code}:manual_review_flag_required")
    return notes


def timeout_policy_health_rows(
    *,
    policy_df: pd.DataFrame,
    policy_exists: bool,
    policy_path: Path,
    screening_state_df: pd.DataFrame | None = None,
    observed_utc: str | None = None,
) -> list[dict[str, str]]:
    observed = observed_utc or _utc_now_iso()
    finalized = finalize_timeout_policy_df(policy_df)
    counts = _policy_code_counts(finalized)
    missing = [code for code in KNOWN_FAIL_AND_RETRY_CODES if counts.get(code, 0) == 0]
    duplicate = [code for code, count in counts.items() if count > 1]
    unknown_policy_rows = [code for code in counts if code not in set(KNOWN_FAIL_AND_RETRY_CODES)]
    invalid_notes = _invalid_value_notes(finalized)
    unknown_screening_codes = _unknown_codes_from_screening_state(screening_state_df)
    manual_rows = finalized[
        (finalized["timeout_mode"].map(_normalize_text).str.lower() == "manual_review")
        & (finalized["enabled"].map(_normalize_text) == "1")
    ]
    manual_flag_bad = [
        _normalize_code(row.get("fail_code", ""))
        for _, row in manual_rows.iterrows()
        if _normalize_text(row.get("manual_review_required_flag", "")) != "1"
    ]
    fallback_fail_count = counts.get("FAIL", 0)

    code_status = "ok" if not missing and not duplicate and not unknown_policy_rows else "warn"
    value_status = "ok" if not invalid_notes else "warn"
    unknown_status = "ok" if not unknown_screening_codes else "warn"
    manual_status = "ok" if not manual_flag_bad else "warn"
    fallback_status = "ok" if fallback_fail_count == 1 else "fail"

    return [
        _health_row(
            check="f_scanner_timeout_policy_file_exists",
            status="ok" if policy_exists else "warn",
            value="1" if policy_exists else "0",
            notes="policy_file_present" if policy_exists else "policy_file_missing_default_created",
            observed_utc=observed,
            source_path=policy_path,
        ),
        _health_row(
            check="f_scanner_timeout_policy_known_codes",
            status=code_status,
            value=str(len(finalized.index)),
            notes=(
                "all_known_codes_present"
                if code_status == "ok"
                else f"missing={','.join(missing) or '-'};duplicate={','.join(duplicate) or '-'};unknown_policy_rows={','.join(unknown_policy_rows) or '-'}"
            ),
            observed_utc=observed,
            source_path=policy_path,
        ),
        _health_row(
            check="f_scanner_timeout_policy_values",
            status=value_status,
            value=str(len(invalid_notes)),
            notes="valid" if not invalid_notes else ";".join(invalid_notes),
            observed_utc=observed,
            source_path=policy_path,
        ),
        _health_row(
            check="f_scanner_timeout_policy_unknown_fail_codes",
            status=unknown_status,
            value=str(len(unknown_screening_codes)),
            notes="none" if not unknown_screening_codes else f"fallback_FAIL_for={','.join(unknown_screening_codes)}",
            observed_utc=observed,
            source_path=policy_path,
        ),
        _health_row(
            check="f_scanner_timeout_policy_manual_review",
            status=manual_status,
            value=str(len(manual_rows.index)),
            notes="manual_review_rows_block_automatic_rescan" if not manual_flag_bad else f"flag_missing={','.join(manual_flag_bad)}",
            observed_utc=observed,
            source_path=policy_path,
        ),
        _health_row(
            check="f_scanner_timeout_policy_fallback_fail",
            status=fallback_status,
            value=str(fallback_fail_count),
            notes="fallback_FAIL_policy_present" if fallback_status == "ok" else "fallback_FAIL_policy_missing_or_duplicate",
            observed_utc=observed,
            source_path=policy_path,
        ),
    ]


def build_timeout_policy_health_rows(
    root: Path | None = None,
    *,
    screening_state_df: pd.DataFrame | None = None,
    observed_utc: str | None = None,
) -> list[dict[str, str]]:
    path = timeout_policy_path(root)
    existed_before = path.exists()
    policy = read_timeout_policy_df(root=root, create_if_missing=True, observed_utc=observed_utc)
    return timeout_policy_health_rows(
        policy_df=policy,
        policy_exists=path.exists() or existed_before,
        policy_path=path,
        screening_state_df=screening_state_df,
        observed_utc=observed_utc,
    )


def recommendation_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for code in KNOWN_FAIL_AND_RETRY_CODES:
        detail = FAIL_REASON_DETAILS.get(code, {})
        rows.append(
            {
                "fail_code": code,
                "meaning": detail.get("meaning", ""),
                "stage": detail.get("stage", ""),
                "recommendation": detail.get("recommendation", ""),
            }
        )
    return rows


def policy_display_df(policy_df: pd.DataFrame) -> pd.DataFrame:
    finalized = finalize_timeout_policy_df(policy_df)
    rows = []
    for _, row in finalized.iterrows():
        payload = {column: _normalize_text(row.get(column, "")) for column in POLICY_COLUMNS}
        detail = FAIL_REASON_DETAILS.get(payload["fail_code"], {})
        payload["meaning"] = detail.get("meaning", "")
        payload["stage"] = detail.get("stage", "")
        payload["recommendation"] = detail.get("recommendation", "")
        rows.append(payload)
    display_columns = [
        "fail_code",
        "meaning",
        "stage",
        "recommendation",
        "enabled",
        "timeout_mode",
        "timeout_days",
        "max_timeout_days",
        "cost_change_resets_flag",
        "source_change_resets_flag",
        "manual_review_required_flag",
        "notes",
        "updated_at_utc",
    ]
    return pd.DataFrame(rows, columns=display_columns)


def policy_df_from_display(display_df: pd.DataFrame) -> pd.DataFrame:
    return finalize_timeout_policy_df(display_df[[column for column in POLICY_COLUMNS if column in display_df.columns]])
