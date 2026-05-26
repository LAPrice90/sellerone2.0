from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_REGISTER_PATH = ROOT / "project_control" / "DUE_CHECK_REGISTER.csv"
DEFAULT_STATUS_PATH = ROOT / "out" / "cycle_alerts" / "due_check_register_status.csv"

REGISTER_COLUMNS = [
    "check_id",
    "title",
    "owner_flow",
    "status",
    "due_utc",
    "trigger",
    "artifact_path",
    "success_condition",
    "failure_action",
    "created_utc",
    "updated_utc",
    "last_checked_utc",
    "last_result",
    "notes",
]

STATUS_COLUMNS = [
    "check_id",
    "owner_flow",
    "title",
    "register_status",
    "due_state",
    "due_utc",
    "trigger",
    "artifact_path",
    "success_condition",
    "failure_action",
    "last_checked_utc",
    "last_result",
    "observed_utc",
    "alert_status",
    "notes",
]

OPEN_STATUSES = {"open", "pending", "monitoring"}
CLOSED_STATUSES = {"complete", "completed", "cancelled", "closed"}
EXECUTABLE_CHECK_IDS = {"F_PRICE_LIST_POST_RESTART_MOT_DAILY"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_header(value: object) -> str:
    return _normalize_text(value).lstrip("\ufeff").strip().strip('"').strip("'")


def _parse_utc(value: object) -> datetime | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _read_register(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = [_normalize_header(name) for name in list(reader.fieldnames or [])]
        missing = [column for column in REGISTER_COLUMNS if column not in fieldnames]
        if missing:
            raise ValueError(f"due check register missing columns: {','.join(missing)}")
        out: list[dict[str, str]] = []
        for row in reader:
            normalized_row = {_normalize_header(key): _normalize_text(value) for key, value in row.items() if key is not None}
            out.append({column: _normalize_text(normalized_row.get(column, "")) for column in REGISTER_COLUMNS})
        return out


def _duplicate_ids(rows: Iterable[dict[str, str]]) -> set[str]:
    seen: set[str] = set()
    duplicate: set[str] = set()
    for row in rows:
        check_id = _normalize_text(row.get("check_id", ""))
        if check_id == "":
            continue
        if check_id in seen:
            duplicate.add(check_id)
        seen.add(check_id)
    return duplicate


def _due_state(*, status: str, due_utc: str, trigger: str, observed_dt: datetime) -> str:
    normalized_status = _normalize_text(status).lower()
    if normalized_status in CLOSED_STATUSES:
        return normalized_status
    raw_due_utc = _normalize_text(due_utc)
    if raw_due_utc == "":
        return "trigger_based" if _normalize_text(trigger) else "open_no_due_or_trigger"
    due_dt = _parse_utc(raw_due_utc)
    if due_dt is None:
        return "invalid_due_utc"
    if due_dt <= observed_dt:
        return "due"
    return "not_due"


def _alert_status(*, due_state: str, duplicate_id: bool, missing_id: bool) -> str:
    if duplicate_id or missing_id or due_state == "invalid_due_utc":
        return "fail"
    if due_state in {"due", "open_no_due_or_trigger"}:
        return "warn"
    return "ok"


def _run_executable_check(*, check_id: str, root: Path, observed_utc: str) -> dict[str, str] | None:
    if check_id not in EXECUTABLE_CHECK_IDS:
        return None
    from scripts.tools.f_price_list_post_restart_mot import run_f_post_restart_mot

    summary = run_f_post_restart_mot(root=root, observed_utc=observed_utc)
    return {
        "status": _normalize_text(summary.get("status", "")),
        "output_path": _normalize_text(summary.get("output_path", "")),
        "json_path": _normalize_text(summary.get("json_path", "")),
        "fail_rows": _normalize_text(summary.get("fail_rows", "")),
        "warn_rows": _normalize_text(summary.get("warn_rows", "")),
        "cause_anchor": _normalize_text(summary.get("cause_anchor", "")),
    }


def build_due_check_status(
    *,
    register_path: Path = DEFAULT_REGISTER_PATH,
    observed_utc: str | None = None,
    root: Path = ROOT,
) -> list[dict[str, str]]:
    observed = observed_utc or _utc_now_iso()
    observed_dt = _parse_utc(observed) or datetime.now(timezone.utc)
    rows = _read_register(register_path)
    duplicates = _duplicate_ids(rows)
    status_rows: list[dict[str, str]] = []
    for row in rows:
        check_id = _normalize_text(row.get("check_id", ""))
        state = _due_state(
            status=row.get("status", ""),
            due_utc=row.get("due_utc", ""),
            trigger=row.get("trigger", ""),
            observed_dt=observed_dt,
        )
        duplicate_id = check_id in duplicates
        missing_id = check_id == ""
        notes = _normalize_text(row.get("notes", ""))
        if duplicate_id:
            notes = f"{notes};duplicate_check_id".strip(";")
        if missing_id:
            notes = f"{notes};missing_check_id".strip(";")
        executable = _run_executable_check(check_id=check_id, root=root, observed_utc=observed)
        computed_alert_status = _alert_status(due_state=state, duplicate_id=duplicate_id, missing_id=missing_id)
        last_checked_utc = _normalize_text(row.get("last_checked_utc", ""))
        last_result = _normalize_text(row.get("last_result", ""))
        if executable is not None:
            executable_status = _normalize_text(executable.get("status", "")).lower()
            if executable_status in {"ok", "warn", "fail"} and not duplicate_id and not missing_id and state != "invalid_due_utc":
                computed_alert_status = executable_status
            last_checked_utc = observed
            last_result = executable_status
            executable_notes = (
                f"executable_check=1;output_path={executable.get('output_path', '')};"
                f"fail_rows={executable.get('fail_rows', '')};warn_rows={executable.get('warn_rows', '')};"
                f"cause_anchor={executable.get('cause_anchor', '')}"
            )
            notes = f"{notes};{executable_notes}".strip(";")
        status_rows.append(
            {
                "check_id": check_id,
                "owner_flow": _normalize_text(row.get("owner_flow", "")),
                "title": _normalize_text(row.get("title", "")),
                "register_status": _normalize_text(row.get("status", "")),
                "due_state": state,
                "due_utc": _normalize_text(row.get("due_utc", "")),
                "trigger": _normalize_text(row.get("trigger", "")),
                "artifact_path": _normalize_text(row.get("artifact_path", "")),
                "success_condition": _normalize_text(row.get("success_condition", "")),
                "failure_action": _normalize_text(row.get("failure_action", "")),
                "last_checked_utc": last_checked_utc,
                "last_result": last_result,
                "observed_utc": observed,
                "alert_status": computed_alert_status,
                "notes": notes,
            }
        )
    return status_rows


def write_status_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=STATUS_COLUMNS)
        writer.writeheader()
        writer.writerows([{column: _normalize_text(row.get(column, "")) for column in STATUS_COLUMNS} for row in rows])


def run_due_check_register(
    *,
    register_path: Path = DEFAULT_REGISTER_PATH,
    output_path: Path = DEFAULT_STATUS_PATH,
    observed_utc: str | None = None,
    root: Path = ROOT,
) -> dict[str, object]:
    rows = build_due_check_status(register_path=register_path, observed_utc=observed_utc, root=root)
    write_status_csv(output_path, rows)
    warn_rows = sum(1 for row in rows if row.get("alert_status") == "warn")
    fail_rows = sum(1 for row in rows if row.get("alert_status") == "fail")
    due_rows = sum(1 for row in rows if row.get("due_state") == "due")
    return {
        "status": "failed" if fail_rows else "warn" if warn_rows else "ok",
        "register_path": str(register_path),
        "output_path": str(output_path),
        "rows": len(rows),
        "due_rows": due_rows,
        "warn_rows": warn_rows,
        "fail_rows": fail_rows,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build due-check register status for morning MOT and operator alerts.")
    parser.add_argument("--register-path", default=str(DEFAULT_REGISTER_PATH))
    parser.add_argument("--output-path", default=str(DEFAULT_STATUS_PATH))
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--observed-utc", default="")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run_due_check_register(
        register_path=Path(args.register_path),
        output_path=Path(args.output_path),
        root=Path(args.root),
        observed_utc=_normalize_text(args.observed_utc) or None,
    )
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        for key, value in summary.items():
            print(f"{key}: {value}")
    return 1 if summary["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
