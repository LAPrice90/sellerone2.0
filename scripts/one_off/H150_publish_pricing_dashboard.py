from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"

SPREADSHEET_ID = "18flepYvH11078sOfEu9sBUmeF4KAl8T_iDKhxDZNPaY"
TAB_NAME = "PRICING_DASHBOARD"
CREDS_PATH = ROOT / "secrets" / "sellerone-2-0d3642b951a0.json"

STRATEGY_PATH = OUT / "phase1_strategy_monitor.csv"
RUNTIME_PATH = OUT / "phase1_runtime_floor_snapshot_latest.csv"
INVENTORY_PATH = OUT / "inventory_summaries.csv"
SCAN_STATE_PATH = OUT / "phase1_sku_scan_state.json"
REPORT_PATH = OUT / "ceiling_invalid_report.csv"


def _safe_float(value: object) -> float | None:
    try:
        text = str(value or "").strip()
        if text == "":
            return None
        out = float(text)
        if not math.isfinite(out):
            return None
        return out
    except Exception:
        return None


def _fmt_num(value: object) -> str:
    text = str(value or "").strip()
    if text == "":
        return ""
    try:
        num = float(text)
        if not math.isfinite(num):
            return ""
        return f"{num:.2f}".rstrip("0").rstrip(".")
    except Exception:
        return text


def _parse_utc(value: str) -> datetime | None:
    text = str(value or "").strip()
    if text == "":
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _latest_listing_snapshot_path() -> Path | None:
    files = sorted(OUT.glob("listing_offer_snapshot_*.csv"))
    return files[-1] if files else None


def _status_from_row(*, decision: str, excluded_reason: str) -> str:
    if str(excluded_reason or "").strip() != "":
        return "READ"
    d = str(decision or "").strip().lower()
    if d == "":
        return "READ"
    if any(flag in d for flag in ("skip", "hold", "read", "no_write", "blocked")):
        return "READ"
    return "WRITE"


def _days_metrics(*, rolling_14d_units: str, stock: str) -> tuple[str, str, str]:
    units_14d = _safe_float(rolling_14d_units)
    if units_14d is None:
        return "", "", ""
    per_day = units_14d / 14.0
    today_units = _fmt_num(units_14d)
    per_day_text = _fmt_num(per_day)
    stock_val = _safe_float(stock)
    if stock_val is None or per_day <= 0:
        return today_units, per_day_text, ""
    return today_units, per_day_text, _fmt_num(stock_val / per_day)


def main() -> int:
    strategy_df = pd.read_csv(STRATEGY_PATH, dtype=str).fillna("")
    runtime_df = pd.read_csv(RUNTIME_PATH, dtype=str).fillna("") if RUNTIME_PATH.exists() else pd.DataFrame()
    inventory_df = pd.read_csv(INVENTORY_PATH, dtype=str).fillna("") if INVENTORY_PATH.exists() else pd.DataFrame()
    listing_path = _latest_listing_snapshot_path()
    listing_df = pd.read_csv(listing_path, dtype=str).fillna("") if listing_path is not None else pd.DataFrame()

    scan_state = {}
    if SCAN_STATE_PATH.exists():
        try:
            scan_state = json.loads(SCAN_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            scan_state = {}
    last_scan_utc = scan_state.get("last_scan_utc", {}) if isinstance(scan_state, dict) else {}
    if not isinstance(last_scan_utc, dict):
        last_scan_utc = {}

    inventory_map: dict[str, str] = {}
    if not inventory_df.empty and "seller_sku" in inventory_df.columns:
        for _, row in inventory_df.iterrows():
            sku = str(row.get("seller_sku", "")).strip()
            if sku == "":
                continue
            stock = str(row.get("available", "")).strip()
            if stock == "":
                stock = str(row.get("total_quantity", "")).strip()
            inventory_map[sku] = stock

    current_map: dict[str, str] = {}
    if not listing_df.empty and "sku" in listing_df.columns:
        for _, row in listing_df.iterrows():
            sku = str(row.get("sku", "")).strip()
            if sku == "":
                continue
            current_map[sku] = str(row.get("our_price", "")).strip()

    source_column_used = ""
    for candidate in ("ceiling_gbp", "ceiling_rule_value_gbp", "execution_final_ceiling_landed_gbp"):
        if candidate in runtime_df.columns:
            source_column_used = candidate
            break

    runtime_map: dict[str, dict[str, str]] = {}
    if not runtime_df.empty and "sku" in runtime_df.columns:
        for _, row in runtime_df.iterrows():
            sku = str(row.get("sku", "")).strip()
            if sku == "":
                continue
            runtime_map[sku] = {
                "cpt_gbp": str(row.get("cpt_gbp", "")).strip(),
                "ceiling_raw": str(row.get(source_column_used, "")).strip() if source_column_used else "",
            }

    now = datetime.now(timezone.utc)
    dashboard_rows: list[list[str]] = []
    report_rows: list[dict[str, str]] = []
    invalid_before = 0
    invalid_after = 0

    for _, row in strategy_df.sort_values("sku").iterrows():
        sku = str(row.get("sku", "")).strip()
        if sku == "":
            continue
        floor = str(row.get("floor_price", "")).strip()
        current = str(current_map.get(sku, "")).strip()
        runtime_row = runtime_map.get(sku, {})
        ceiling_raw = str(runtime_row.get("ceiling_raw", "")).strip()
        cpt = str(runtime_row.get("cpt_gbp", "")).strip()

        floor_v = _safe_float(floor)
        current_v = _safe_float(current)
        ceiling_v = _safe_float(ceiling_raw)

        ceiling_fixed = ceiling_raw
        is_invalid = 0
        if ceiling_v is not None:
            ref_candidates = [v for v in (floor_v, current_v) if v is not None]
            if ref_candidates and ceiling_v < max(ref_candidates):
                is_invalid = 1
                ceiling_fixed = ""

        if is_invalid == 1:
            invalid_before += 1

        if _safe_float(ceiling_fixed) is not None:
            ref_candidates_after = [v for v in (floor_v, current_v) if v is not None]
            if ref_candidates_after and float(ceiling_fixed) < max(ref_candidates_after):
                invalid_after += 1

        status = _status_from_row(
            decision=str(row.get("decision", "")),
            excluded_reason=str(row.get("excluded_reason", "")),
        )
        scan_ts = str(last_scan_utc.get(sku, "")).strip()
        minutes = ""
        dt = _parse_utc(scan_ts)
        if dt is not None:
            minutes = str(max(int((now - dt).total_seconds() // 60), 0))

        stock = str(inventory_map.get(sku, "")).strip()
        today_units, per_day, stock_days = _days_metrics(
            rolling_14d_units=str(row.get("rolling_14d_units", "")).strip(),
            stock=stock,
        )

        dashboard_rows.append(
            [
                status,
                minutes,
                sku,
                stock,
                floor,
                cpt,
                current,
                str(row.get("competitor_price", "")).strip(),
                ceiling_fixed,
                today_units,
                per_day,
                stock_days,
                scan_ts,
            ]
        )
        report_rows.append(
            {
                "sku": sku,
                "floor": floor,
                "current": current,
                "ceiling_raw": ceiling_raw,
                "ceiling_fixed": ceiling_fixed,
                "source_column_used": source_column_used,
                "ceiling_invalid": str(is_invalid),
            }
        )

    report_df = pd.DataFrame(report_rows)
    report_df[["sku", "floor", "current", "ceiling_raw", "ceiling_fixed", "source_column_used", "ceiling_invalid"]].to_csv(
        REPORT_PATH,
        index=False,
    )

    headers = [
        "Status (WRITE/READ based on decision, excluded_reason)",
        "Minutes (age since last_scan_utc if available, else blank)",
        "SKU",
        "Stock",
        "Floor",
        "CPT (if available, else blank)",
        "Current",
        "Compet",
        "Ceiling",
        "Today Units (if available, else blank)",
        "Per Day (if available, else blank)",
        "Stock Days (if available, else blank)",
        "last_scan_utc",
    ]

    import gspread

    client = gspread.service_account(filename=str(CREDS_PATH))
    sheet = client.open_by_key(SPREADSHEET_ID)
    try:
        ws = sheet.worksheet(TAB_NAME)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=TAB_NAME, rows=max(100, len(dashboard_rows) + 10), cols=len(headers) + 2)
    ws.clear()
    ws.update(range_name="A1", values=[headers] + dashboard_rows, value_input_option="USER_ENTERED")
    try:
        ws.freeze(rows=1)
    except Exception:
        pass

    example = next((r for r in dashboard_rows if r[2] == "0G-JB6S-PN34"), [])
    print(f"mapping_source_column={source_column_used}")
    print(f"invalid_before={invalid_before}")
    print(f"invalid_after={invalid_after}")
    print(f"report_path={REPORT_PATH}")
    print(f"rows_written={len(dashboard_rows)}")
    if example:
        print(
            "example_0G-JB6S-PN34="
            + json.dumps(
                {
                    "SKU": example[2],
                    "Floor": example[4],
                    "Current": example[6],
                    "Ceiling": example[8],
                },
                ensure_ascii=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
