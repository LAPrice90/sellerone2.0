from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
DEFAULT_HEALTH_PATH = OUT / "system_health_checklist.csv"
DEFAULT_CREDS = ROOT / "secrets" / "sellerone-2-0d3642b951a0.json"
DEFAULT_LIGHTS_TAB = "Health Lights"
DEFAULT_ISSUES_TAB = "Health Issues"


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm(v: object) -> str:
    return str(v or "").strip()


def _status_rank(status: str) -> int:
    key = _norm(status).lower()
    if key == "fail":
        return 3
    if key == "warn":
        return 2
    if key == "not_checked":
        return 1
    return 0


def _flow_from_check(check: str) -> str:
    text = _norm(check).lower()
    if "_" not in text:
        return "GLOBAL"
    prefix = text.split("_", 1)[0].upper()
    if len(prefix) == 1 and prefix in {"A", "B", "C", "D", "E", "F", "G", "H"}:
        return prefix
    return "GLOBAL"


def _load_health(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"missing health csv: {path}")
    df = pd.read_csv(path, dtype=str).fillna("")
    expected = {"check", "status", "value", "notes"}
    missing = [c for c in expected if c not in df.columns]
    if missing:
        raise ValueError(f"health csv missing columns: {','.join(missing)}")
    df["status"] = df["status"].astype(str).str.strip().str.lower()
    df["flow"] = df["check"].map(_flow_from_check)
    return df


def _build_lights_payload(df: pd.DataFrame) -> tuple[list[list[str]], list[tuple[int, int, str]]]:
    fail_n = int((df["status"] == "fail").sum())
    warn_n = int((df["status"] == "warn").sum())
    ok_n = int((df["status"] == "ok").sum())
    nc_n = int((df["status"] == "not_checked").sum())
    total = int(len(df))

    overall = "GREEN"
    if fail_n > 0:
        overall = "RED"
    elif warn_n > 0:
        overall = "AMBER"

    flow_rows: list[list[str]] = []
    for flow in ["A", "B", "H", "E", "GLOBAL"]:
        part = df[df["flow"] == flow]
        if part.empty:
            continue
        f = int((part["status"] == "fail").sum())
        w = int((part["status"] == "warn").sum())
        o = int((part["status"] == "ok").sum())
        n = int((part["status"] == "not_checked").sum())
        light = "GREEN"
        if f > 0:
            light = "RED"
        elif w > 0:
            light = "AMBER"
        flow_rows.append([flow, str(f), str(w), str(o), str(n), str(len(part)), light])

    cols = 14
    rows: list[list[str]] = []
    rows.append(["SellerOne Health Lights", "", "", "", "", "", "", "", "", "", "", "", "", ""])
    rows.append([f"Last refresh UTC: {_now_utc_iso()}", "", "", "", "", "", "", "", "", "", "", "", "", ""])
    rows.append(["", "", "", "", "", "", "", "", "", "", "", "", "", ""])
    rows.append(["Overall Light", overall, "", "Total Checks", str(total), "OK", str(ok_n), "Not Checked", str(nc_n), "", "", "", "", ""])
    rows.append(["FAIL", str(fail_n), "", "WARN", str(warn_n), "", "", "", "", "", "", "", "", ""])
    rows.append(["Light key", "RED - one or more FAIL", "", "AMBER - WARN and no FAIL", "", "GREEN - all OK", "", "", "", "", "", "", "", ""])
    rows.append(["", "", "", "", "", "", "", "", "", "", "", "", "", ""])
    rows.append(["Flow", "Fail", "Warn", "OK", "Not Checked", "Total", "Light", "", "", "", "", "", "", ""])
    rows.extend(flow_rows if flow_rows else [["(none)", "0", "0", "0", "0", "0", "GREEN", "", ""]])

    rows = [(r + ([""] * (cols - len(r))))[:cols] for r in rows]

    while len(rows) < 12:
        rows.append([""] * cols)

    rows.append(["148 Lights Board (one circle per check)", "", "", "", "", "", "", "", "", "", "", "", "", ""])
    rows.append([""] * cols)

    checks = df.copy()
    checks["rank"] = checks["status"].map(_status_rank)
    checks = checks.sort_values(by=["rank", "flow", "check"], ascending=[False, True, True]).reset_index(drop=True)

    light_cells: list[tuple[int, int, str]] = []
    grid_start_row = len(rows) + 1
    for idx, row in checks.iterrows():
        r = grid_start_row + (idx // cols)
        c = 1 + (idx % cols)
        while len(rows) < r:
            rows.append([""] * cols)
        status = _norm(row.get("status", "")).lower()
        if status == "fail":
            rows[r - 1][c - 1] = "🔴"
        elif status == "warn":
            rows[r - 1][c - 1] = "🟠"
        else:
            rows[r - 1][c - 1] = "🟢"
        light_cells.append((r, c, status))

    rows.append([""] * cols)
    rows.append(["Legend", "● OK", "● WARN", "● FAIL", "", "", "", "", "", "", "", "", "", ""])

    return rows, light_cells


def _open_sheet(sheet_id: str, creds_path: Path):
    import gspread

    if not creds_path.exists():
        raise FileNotFoundError(f"missing gspread creds file: {creds_path}")
    client = gspread.service_account(filename=str(creds_path))
    return client.open_by_key(sheet_id)


def _ensure_ws(sheet, title: str, rows: int, cols: int):
    import gspread

    try:
        ws = sheet.worksheet(title)
        if ws.row_count < rows or ws.col_count < cols:
            ws.resize(rows=max(rows, ws.row_count), cols=max(cols, ws.col_count))
        return ws
    except gspread.WorksheetNotFound:
        return sheet.add_worksheet(title=title, rows=max(rows, 200), cols=max(cols, 26))


def _build_issues_payload(df: pd.DataFrame) -> list[list[str]]:
    issues = df[df["status"].isin(["fail", "warn"])].copy()
    issues["rank"] = issues["status"].map(_status_rank)
    issues = issues.sort_values(by=["rank", "flow", "check"], ascending=[False, True, True])

    rows: list[list[str]] = []
    rows.append(["SellerOne Health Issues", "", "", "", "", "", "", ""])
    rows.append([f"Last refresh UTC: {_now_utc_iso()}", "", "", "", "", "", "", ""])
    rows.append(["", "", "", "", "", "", "", ""])
    rows.append(["Status", "Flow", "Check", "Value", "Notes", "First Seen UTC", "Last Seen UTC", "Runs/Age"])

    if issues.empty:
        rows.append(["OK", "GLOBAL", "no active fail/warn checks", "", "", "", "", ""])
    else:
        for _, row in issues.iterrows():
            runs = _norm(row.get("alert_consecutive_runs", ""))
            age = _norm(row.get("alert_age_hours", ""))
            runs_age = runs
            if runs and age:
                runs_age = f"{runs} / {age}h"
            elif age:
                runs_age = f"{age}h"
            rows.append(
                [
                    _norm(row.get("status", "")).upper(),
                    _norm(row.get("flow", "")),
                    _norm(row.get("check", "")),
                    _norm(row.get("value", "")),
                    _norm(row.get("notes", "")),
                    _norm(row.get("alert_first_seen_utc", "")),
                    _norm(row.get("alert_last_seen_utc", "")),
                    runs_age,
                ]
            )
    return rows


def _apply_lights_formatting(
    sheet, ws, payload_rows: int, light_cells: list[tuple[int, int, str]], *, charcoal: bool
) -> None:
    sid = int(ws.id)
    col_count = 14
    row_count = max(payload_rows + 2, 30)
    dark_bg = {"red": 0.12, "green": 0.13, "blue": 0.15}
    darker_bg = {"red": 0.09, "green": 0.1, "blue": 0.12}
    header_bg = {"red": 0.18, "green": 0.2, "blue": 0.23}
    white = {"red": 0.95, "green": 0.95, "blue": 0.95}
    black = {"red": 0.15, "green": 0.15, "blue": 0.15}

    requests = []
    requests.append(
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 8}},
                "fields": "gridProperties.frozenRowCount",
            }
        }
    )
    requests.append(
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
                "properties": {"pixelSize": 210},
                "fields": "pixelSize",
            }
        }
    )
    for idx in [1, 2, 4, 5, 6]:
        requests.append(
            {
                "updateDimensionProperties": {
                    "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": idx, "endIndex": idx + 1},
                    "properties": {"pixelSize": 120},
                    "fields": "pixelSize",
                }
            }
        )
    requests.append(
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 3, "endIndex": 4},
                "properties": {"pixelSize": 30},
                "fields": "pixelSize",
            }
        }
    )
    requests.append(
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 7, "endIndex": 14},
                "properties": {"pixelSize": 44},
                "fields": "pixelSize",
            }
        }
    )
    if charcoal:
        requests.append(
            {
                "repeatCell": {
                    "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": row_count, "startColumnIndex": 0, "endColumnIndex": col_count},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": dark_bg,
                            "textFormat": {"foregroundColor": white, "fontFamily": "Arial", "fontSize": 10},
                            "verticalAlignment": "MIDDLE",
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment)",
                }
            }
        )
    else:
        requests.append(
            {
                "repeatCell": {
                    "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": row_count, "startColumnIndex": 0, "endColumnIndex": col_count},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 1, "green": 1, "blue": 1},
                            "textFormat": {"foregroundColor": black, "fontFamily": "Arial", "fontSize": 10},
                            "verticalAlignment": "MIDDLE",
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment)",
                }
            }
        )

    header_rows = [(0, 1), (3, 5), (7, 8), (12, 13), (len(rows := ws.get_all_values()) - 1, len(rows))]
    for start, end in header_rows:
        requests.append(
            {
                "repeatCell": {
                    "range": {"sheetId": sid, "startRowIndex": start, "endRowIndex": end, "startColumnIndex": 0, "endColumnIndex": col_count},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": header_bg if charcoal else {"red": 0.92, "green": 0.93, "blue": 0.95},
                            "textFormat": {"bold": True, "foregroundColor": white if charcoal else black},
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat.bold,textFormat.foregroundColor)",
                }
            }
        )

    requests.append(
        {
            "repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": col_count},
                "cell": {"userEnteredFormat": {"backgroundColor": darker_bg if charcoal else {"red": 0.97, "green": 0.97, "blue": 0.97}}},
                "fields": "userEnteredFormat.backgroundColor",
            }
        }
    )

    sheet.batch_update({"requests": requests})

    red = {"red": 0.82, "green": 0.26, "blue": 0.26}
    amber = {"red": 0.91, "green": 0.62, "blue": 0.2}
    green = {"red": 0.29, "green": 0.66, "blue": 0.38}

    ws.format("B4", {"backgroundColor": {"red": 0.25, "green": 0.25, "blue": 0.25}, "textFormat": {"bold": True}})
    ws.format("B5", {"backgroundColor": red, "textFormat": {"bold": True}})
    ws.format("E5", {"backgroundColor": amber, "textFormat": {"bold": True}})

    rows = ws.get_all_values()
    for i, row in enumerate(rows, start=1):
        if len(row) >= 7 and i >= 9:
            light = _norm(row[6]).upper()
            if light == "RED":
                ws.format(f"G{i}", {"backgroundColor": red, "textFormat": {"bold": True}})
            elif light == "AMBER":
                ws.format(f"G{i}", {"backgroundColor": amber, "textFormat": {"bold": True}})
            elif light == "GREEN":
                ws.format(f"G{i}", {"backgroundColor": green, "textFormat": {"bold": True}})

    overall = _norm(rows[3][1] if len(rows) > 3 and len(rows[3]) > 1 else "").upper()
    if overall == "RED":
        ws.format("B4", {"backgroundColor": red, "textFormat": {"bold": True}})
    elif overall == "AMBER":
        ws.format("B4", {"backgroundColor": amber, "textFormat": {"bold": True}})
    elif overall == "GREEN":
        ws.format("B4", {"backgroundColor": green, "textFormat": {"bold": True}})

    # Glyphs are pre-colored emoji so no per-cell API formatting is needed.


def _apply_issues_formatting(sheet, ws, payload_rows: int, *, charcoal: bool) -> None:
    sid = int(ws.id)
    col_count = 8
    row_count = max(payload_rows + 2, 30)
    dark_bg = {"red": 0.12, "green": 0.13, "blue": 0.15}
    header_bg = {"red": 0.18, "green": 0.2, "blue": 0.23}
    white = {"red": 0.95, "green": 0.95, "blue": 0.95}
    black = {"red": 0.15, "green": 0.15, "blue": 0.15}

    requests = [
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 4}},
                "fields": "gridProperties.frozenRowCount",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": row_count, "startColumnIndex": 0, "endColumnIndex": col_count},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": dark_bg if charcoal else {"red": 1, "green": 1, "blue": 1},
                        "textFormat": {"foregroundColor": white if charcoal else black, "fontFamily": "Arial", "fontSize": 10},
                        "verticalAlignment": "MIDDLE",
                        "wrapStrategy": "WRAP",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment,wrapStrategy)",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": col_count},
                "cell": {"userEnteredFormat": {"backgroundColor": header_bg if charcoal else {"red": 0.92, "green": 0.93, "blue": 0.95}, "textFormat": {"bold": True}}},
                "fields": "userEnteredFormat(backgroundColor,textFormat.bold)",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": 3, "endRowIndex": 4, "startColumnIndex": 0, "endColumnIndex": col_count},
                "cell": {"userEnteredFormat": {"backgroundColor": header_bg if charcoal else {"red": 0.92, "green": 0.93, "blue": 0.95}, "textFormat": {"bold": True}}},
                "fields": "userEnteredFormat(backgroundColor,textFormat.bold)",
            }
        },
    ]

    widths = [90, 80, 280, 80, 550, 170, 170, 120]
    for idx, px in enumerate(widths):
        requests.append(
            {
                "updateDimensionProperties": {
                    "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": idx, "endIndex": idx + 1},
                    "properties": {"pixelSize": px},
                    "fields": "pixelSize",
                }
            }
        )
    sheet.batch_update({"requests": requests})

    red = {"red": 0.82, "green": 0.26, "blue": 0.26}
    amber = {"red": 0.91, "green": 0.62, "blue": 0.2}
    rows = ws.get_all_values()
    for i in range(5, len(rows) + 1):
        status = _norm(rows[i - 1][0]).upper() if rows[i - 1] else ""
        if status == "FAIL":
            ws.format(f"A{i}", {"backgroundColor": red, "textFormat": {"bold": True}})
        elif status == "WARN":
            ws.format(f"A{i}", {"backgroundColor": amber, "textFormat": {"bold": True}})


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish health switchboard to Google Sheets.")
    parser.add_argument("--sheet-id", required=True)
    parser.add_argument("--lights-tab", default=DEFAULT_LIGHTS_TAB)
    parser.add_argument("--issues-tab", default=DEFAULT_ISSUES_TAB)
    parser.add_argument("--health-path", default=str(DEFAULT_HEALTH_PATH))
    parser.add_argument("--creds", default=str(DEFAULT_CREDS))
    parser.add_argument("--theme", choices=["charcoal", "blank"], default="charcoal")
    args = parser.parse_args()

    health_path = Path(args.health_path)
    creds = Path(args.creds)
    df = _load_health(health_path)
    lights_payload, light_cells = _build_lights_payload(df)
    issues_payload = _build_issues_payload(df)

    sheet = _open_sheet(args.sheet_id, creds)
    lights_ws = _ensure_ws(sheet, args.lights_tab, rows=max(len(lights_payload) + 20, 80), cols=9)
    lights_ws.clear()
    lights_ws.update(values=lights_payload, range_name="A1", value_input_option="RAW")
    _apply_lights_formatting(
        sheet,
        lights_ws,
        len(lights_payload),
        light_cells,
        charcoal=(args.theme == "charcoal"),
    )
    issues_ws = _ensure_ws(sheet, args.issues_tab, rows=max(len(issues_payload) + 20, 120), cols=8)
    issues_ws.clear()
    issues_ws.update(values=issues_payload, range_name="A1", value_input_option="RAW")
    _apply_issues_formatting(sheet, issues_ws, len(issues_payload), charcoal=(args.theme == "charcoal"))

    fail_n = int((df["status"] == "fail").sum())
    warn_n = int((df["status"] == "warn").sum())
    print(f"switchboard_sheet_id={args.sheet_id}")
    print(f"switchboard_lights_tab={args.lights_tab}")
    print(f"switchboard_issues_tab={args.issues_tab}")
    print(f"switchboard_theme={args.theme}")
    print(f"switchboard_checks={len(df)}")
    print(f"switchboard_fail={fail_n}")
    print(f"switchboard_warn={warn_n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
