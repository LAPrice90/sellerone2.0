from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .paths import get_manager_paths


SIGN_IN_LOG_REL_PATH = Path("sellerone_manager") / "CONTROL" / "SO21_WORKER_SIGN_IN_OUT_LOG.md"
BOARD_REL_PATH = Path("sellerone_manager") / "CONTROL" / "SO21_WORKER_UTILISATION_BOARD.md"
CSV_OUTPUT_NAME = "worker_utilisation_board.csv"


@dataclass(frozen=True)
class WorkerEntry:
    lane: str
    role: str
    thread_id: str
    job_ref: str
    sign_in_uk: str
    last_movement_uk: str
    state: str
    next_action: str
    sign_out_uk: str
    notes: str
    section: str


def _now_utc_text(generated_utc: str | None = None) -> str:
    if generated_utc:
        return generated_utc
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clean_cell(value: str) -> str:
    value = value.strip()
    if value.startswith("`") and value.endswith("`"):
        value = value[1:-1]
    return value.strip()


def _extract_table(markdown: str, heading: str) -> list[list[str]]:
    heading_pattern = rf"^## {re.escape(heading)}\s*$"
    match = re.search(heading_pattern, markdown, flags=re.MULTILINE)
    if not match:
        return []
    following = markdown[match.end() :]
    next_heading = re.search(r"^##\s+", following, flags=re.MULTILINE)
    section = following[: next_heading.start()] if next_heading else following
    rows: list[list[str]] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [_clean_cell(cell) for cell in stripped.strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells):
            continue
        rows.append(cells)
    return rows


def _table_entries(markdown: str, heading: str, section: str) -> list[WorkerEntry]:
    rows = _extract_table(markdown, heading)
    if len(rows) < 2:
        return []
    header = [cell.lower().replace(" ", "_").replace("-", "_") for cell in rows[0]]
    entries: list[WorkerEntry] = []
    for cells in rows[1:]:
        row = {header[index]: cells[index] if index < len(cells) else "" for index in range(len(header))}
        entries.append(
            WorkerEntry(
                lane=row.get("lane", ""),
                role=row.get("role", ""),
                thread_id=row.get("thread_id", ""),
                job_ref=row.get("job_ref", ""),
                sign_in_uk=row.get("sign_in_uk", ""),
                last_movement_uk=row.get("last_movement_uk", ""),
                state=row.get("state", row.get("result", "")),
                next_action=row.get("next_action", ""),
                sign_out_uk=row.get("sign_out_uk", ""),
                notes=row.get("notes", ""),
                section=section,
            )
        )
    return entries


def read_worker_entries(root: Path | str | None = None) -> list[WorkerEntry]:
    paths = get_manager_paths(root)
    log_path = paths.root / SIGN_IN_LOG_REL_PATH
    if not log_path.exists():
        return []
    markdown = log_path.read_text(encoding="utf-8")
    return [
        *_table_entries(markdown, "Active Worker Register", "active"),
        *_table_entries(markdown, "Recently Signed Out", "signed_out"),
    ]


def _minutes_between(start: str, end: str) -> str:
    if not start or not end:
        return ""
    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(end, "%Y-%m-%d %H:%M")
    except ValueError:
        return ""
    minutes = int((end_dt - start_dt).total_seconds() // 60)
    return str(max(minutes, 0))


def _entry_row(entry: WorkerEntry) -> dict[str, str]:
    duration = _minutes_between(entry.sign_in_uk, entry.sign_out_uk)
    quiet_minutes = "" if entry.section != "active" else _minutes_between(entry.last_movement_uk, datetime.now().strftime("%Y-%m-%d %H:%M"))
    return {
        "section": entry.section,
        "lane": entry.lane,
        "role": entry.role,
        "thread_id": entry.thread_id,
        "job_ref": entry.job_ref,
        "sign_in_uk": entry.sign_in_uk,
        "last_movement_uk": entry.last_movement_uk,
        "state": entry.state,
        "next_action": entry.next_action,
        "sign_out_uk": entry.sign_out_uk,
        "duration_minutes": duration,
        "quiet_minutes": quiet_minutes,
        "notes": entry.notes,
    }


def build_worker_utilisation_board(root: Path | str | None = None, generated_utc: str | None = None) -> dict[str, object]:
    entries = read_worker_entries(root)
    rows = [_entry_row(entry) for entry in entries]
    active_rows = [row for row in rows if row["section"] == "active"]
    signed_out_rows = [row for row in rows if row["section"] == "signed_out"]
    working_rows = [row for row in active_rows if row["state"] not in {"blocked", "complete", "replaced"}]
    quiet_rows = [
        row
        for row in working_rows
        if row["quiet_minutes"].isdigit() and int(row["quiet_minutes"]) >= 4 and row["state"] not in {"blocked"}
    ]
    return {
        "generated_utc": _now_utc_text(generated_utc),
        "rows": rows,
        "active_count": len(active_rows),
        "working_count": len(working_rows),
        "signed_out_count": len(signed_out_rows),
        "quiet_count": len(quiet_rows),
        "quiet_rows": quiet_rows,
    }


def _markdown_table(rows: list[dict[str, str]], columns: list[str]) -> list[str]:
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(row.get(column, "") for column in columns) + " |")
    return lines


def format_worker_utilisation_status(result: dict[str, object]) -> str:
    return (
        f"worker_utilisation_board={result['board_path']}\n"
        f"worker_utilisation_csv={result['csv_path']}\n"
        f"active_count={result['active_count']}\n"
        f"working_count={result['working_count']}\n"
        f"signed_out_count={result['signed_out_count']}\n"
        f"quiet_count={result['quiet_count']}"
    )


def write_worker_utilisation_board(root: Path | str | None = None, generated_utc: str | None = None) -> dict[str, object]:
    paths = get_manager_paths(root)
    result = build_worker_utilisation_board(root=paths.root, generated_utc=generated_utc)
    control_dir = paths.root / "sellerone_manager" / "CONTROL"
    board_path = paths.root / BOARD_REL_PATH
    csv_path = paths.output_dir / CSV_OUTPUT_NAME
    rows = result["rows"]

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "section",
        "lane",
        "role",
        "thread_id",
        "job_ref",
        "sign_in_uk",
        "last_movement_uk",
        "state",
        "sign_out_uk",
        "duration_minutes",
        "quiet_minutes",
        "next_action",
        "notes",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    active_rows = [row for row in rows if row["section"] == "active"]
    signed_out_rows = [row for row in rows if row["section"] == "signed_out"]
    quiet_rows = result["quiet_rows"]

    lines = [
        "# SO21 Worker Utilisation Board",
        "",
        f"Generated UTC: {result['generated_utc']}",
        "Owner: Operations",
        "",
        "## Summary",
        "",
        f"- Active workers/reviewers: {result['active_count']}",
        f"- Actually working or reviewing now: {result['working_count']}",
        f"- Signed out entries tracked: {result['signed_out_count']}",
        f"- Quiet active entries needing attention: {result['quiet_count']}",
        f"- Source log: `{SIGN_IN_LOG_REL_PATH.as_posix()}`",
        f"- CSV output: `{csv_path.relative_to(paths.root).as_posix() if csv_path.is_relative_to(paths.root) else csv_path}`",
        "",
        "## Active Now",
        "",
    ]
    if active_rows:
        lines.extend(
            _markdown_table(
                active_rows,
                ["lane", "role", "job_ref", "last_movement_uk", "state", "quiet_minutes", "next_action"],
            )
        )
    else:
        lines.append("No active workers are currently logged.")
    lines.extend(["", "## Quiet Attention", ""])
    if quiet_rows:
        lines.extend(
            _markdown_table(
                quiet_rows,
                ["lane", "role", "job_ref", "last_movement_uk", "state", "quiet_minutes", "next_action"],
            )
        )
    else:
        lines.append("No active worker is over the quiet threshold in the current log.")
    lines.extend(["", "## Capacity Warning", ""])
    if int(result["working_count"]) < 2:
        lines.append("Fewer than two non-blocked workers/reviewers are currently moving. Operations should refill a safe lane if one is available.")
    else:
        lines.append("At least two non-blocked workers/reviewers are currently moving.")
    lines.extend(["", "## Recently Signed Out", ""])
    if signed_out_rows:
        lines.extend(
            _markdown_table(
                signed_out_rows[-10:],
                ["lane", "role", "job_ref", "sign_in_uk", "sign_out_uk", "duration_minutes", "state"],
            )
        )
    else:
        lines.append("No signed-out entries are currently logged.")
    lines.extend(
        [
            "",
            "## Operating Rule",
            "",
            "- Quiet for one Operations pass: nudge.",
            "- Quiet for two Operations passes: block with reason or replace if safe.",
            "- Finished lane: sign out, route review/closure, then refill with the next safe packet.",
        ]
    )
    control_dir.mkdir(parents=True, exist_ok=True)
    board_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        **result,
        "board_path": str(board_path),
        "csv_path": str(csv_path),
    }
