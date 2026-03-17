"""
Daily guardrail audit checks to prevent silent data drift.

Outputs:
- out/audit_daily_guardrails.csv
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import pandas as pd


OUT_PATH = Path("out/audit_daily_guardrails.csv")
STATE_PATH = Path("out/audit_daily_guardrails_state.csv")

UNMAPPED_FEES = Path("out/transaction_category_unmapped.csv")
FEE_VAT_LEDGER = Path("out/fee_vat_ledger.csv")
PNL_DAILY = Path("out/pnl_daily.csv")
VAT_DAILY = Path("out/vat_report_daily.csv")
MISSING_ORDERS = Path("out/analysis_reports/missing_orders_vs_sellerboard.csv")

MAX_HOURS_STALE = float(os.environ.get("AUDIT_MAX_HOURS_STALE", "36"))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _file_age_hours(path: Path) -> float:
    if not path.exists():
        return float("inf")
    ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return (_utc_now() - ts).total_seconds() / 3600.0


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def _add(rows: List[Dict[str, object]], name: str, ok: bool, value: object, threshold: object, details: str) -> None:
    rows.append(
        {
            "check": name,
            "status": _status(ok),
            "value": value,
            "threshold": threshold,
            "details": details,
        }
    )


def _read_state() -> pd.DataFrame:
    cols = ["check", "status", "first_seen_utc", "last_seen_utc", "consecutive_runs"]
    if not STATE_PATH.exists():
        return pd.DataFrame(columns=cols)
    try:
        df = pd.read_csv(STATE_PATH, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame(columns=cols)
    for col in cols:
        if col not in df.columns:
            df[col] = ""
    return df[cols]


def _apply_alert_aging(df: pd.DataFrame) -> pd.DataFrame:
    now = _utc_now()
    now_iso = now.isoformat()
    prev = _read_state()
    prev_map = {
        str(r["check"]).strip(): {
            "status": str(r["status"]).strip().upper(),
            "first_seen_utc": str(r["first_seen_utc"]).strip(),
            "consecutive_runs": str(r["consecutive_runs"]).strip(),
        }
        for _, r in prev.iterrows()
    }

    first_seen_vals: List[str] = []
    last_seen_vals: List[str] = []
    streak_vals: List[str] = []
    age_hours_vals: List[str] = []
    next_state_rows: List[Dict[str, str]] = []

    for _, row in df.iterrows():
        check = str(row.get("check", "")).strip()
        status = str(row.get("status", "")).strip().upper()
        if status == "PASS":
            first_seen_vals.append("")
            last_seen_vals.append("")
            streak_vals.append("")
            age_hours_vals.append("")
            continue

        prev_row = prev_map.get(check, {})
        prev_status = str(prev_row.get("status", "")).strip().upper()
        prev_first = str(prev_row.get("first_seen_utc", "")).strip()
        prev_streak_raw = str(prev_row.get("consecutive_runs", "")).strip()
        try:
            prev_streak = int(prev_streak_raw) if prev_streak_raw else 0
        except Exception:
            prev_streak = 0

        if prev_status == status and prev_first:
            first_seen = prev_first
            streak = prev_streak + 1 if prev_streak > 0 else 1
        else:
            first_seen = now_iso
            streak = 1

        age_hours = ""
        try:
            first_dt = datetime.fromisoformat(first_seen.replace("Z", "+00:00"))
            if first_dt.tzinfo is None:
                first_dt = first_dt.replace(tzinfo=timezone.utc)
            age_hours = f"{max((now - first_dt).total_seconds() / 3600.0, 0.0):.2f}"
        except Exception:
            age_hours = ""

        first_seen_vals.append(first_seen)
        last_seen_vals.append(now_iso)
        streak_vals.append(str(streak))
        age_hours_vals.append(age_hours)
        next_state_rows.append(
            {
                "check": check,
                "status": status,
                "first_seen_utc": first_seen,
                "last_seen_utc": now_iso,
                "consecutive_runs": str(streak),
            }
        )

    df = df.copy()
    df["alert_first_seen_utc"] = first_seen_vals
    df["alert_last_seen_utc"] = last_seen_vals
    df["alert_consecutive_runs"] = streak_vals
    df["alert_age_hours"] = age_hours_vals
    pd.DataFrame(next_state_rows, columns=["check", "status", "first_seen_utc", "last_seen_utc", "consecutive_runs"]).to_csv(
        STATE_PATH, index=False
    )
    return df


def main() -> None:
    rows: List[Dict[str, object]] = []

    # Unmapped fees should be zero.
    if UNMAPPED_FEES.exists():
        df = pd.read_csv(UNMAPPED_FEES, dtype=str).fillna("")
        count = len(df)
        _add(rows, "unmapped_fees_count", count == 0, count, 0, str(UNMAPPED_FEES))
    else:
        _add(rows, "unmapped_fees_count", False, "missing", 0, str(UNMAPPED_FEES))

    # VAT missing bucket should be small/zero in fee ledger.
    if FEE_VAT_LEDGER.exists():
        fee = pd.read_csv(FEE_VAT_LEDGER, dtype=str).fillna("")
        if "vat_source" in fee.columns:
            missing = fee[fee["vat_source"].astype(str).str.lower() == "missing"]
            missing = missing[missing.get("currency").astype(str).str.upper() == "GBP"]
            count = len(missing)
            _add(rows, "fee_vat_missing_rows_gbp", count == 0, count, 0, str(FEE_VAT_LEDGER))
        else:
            _add(rows, "fee_vat_missing_rows_gbp", False, "vat_source_missing", 0, str(FEE_VAT_LEDGER))
    else:
        _add(rows, "fee_vat_missing_rows_gbp", False, "missing", 0, str(FEE_VAT_LEDGER))

    # Freshness checks.
    for path, label in [(PNL_DAILY, "pnl_daily_fresh"), (VAT_DAILY, "vat_daily_fresh")]:
        age = _file_age_hours(path)
        ok = age <= MAX_HOURS_STALE
        _add(rows, label, ok, round(age, 2), f"<= {MAX_HOURS_STALE}h", str(path))

    # Missing orders vs Sellerboard should be zero.
    if MISSING_ORDERS.exists():
        missing = pd.read_csv(MISSING_ORDERS, dtype=str).fillna("")
        count = len(missing)
        _add(rows, "sellerboard_missing_orders", count == 0, count, 0, str(MISSING_ORDERS))
    else:
        _add(rows, "sellerboard_missing_orders", False, "missing", 0, str(MISSING_ORDERS))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_df = pd.DataFrame(rows)
    out_df = _apply_alert_aging(out_df)
    pd.DataFrame(out_df).to_csv(OUT_PATH, index=False)
    print({"status": "success", "rows": len(rows), "report": str(OUT_PATH)})


if __name__ == "__main__":
    main()

