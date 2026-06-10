from __future__ import annotations

import csv
import re
from collections import Counter, OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .paths import get_manager_paths


LANE_BY_STATUS: OrderedDict[str, str] = OrderedDict(
    [
        ("approved", "Not Started"),
        ("in_progress", "In Progress"),
        ("fixed_needs_retest", "Waiting Proof"),
        ("retest_failed", "Proof Failed"),
        ("blocked_needs_luke", "Blocked"),
        ("parked", "Parked"),
        ("proved", "Proven"),
    ]
)

ACTIVE_STATUSES = {
    "approved",
    "in_progress",
    "fixed_needs_retest",
    "retest_failed",
    "blocked_needs_luke",
    "parked",
}

FLOW_ORDER = ["A", "B", "E", "H", "F", "O", "M"]
FLOW_COLOURS = {
    "A": "#15803d",
    "B": "#2563eb",
    "E": "#7c3aed",
    "H": "#dc2626",
    "F": "#0f766e",
    "O": "#b45309",
    "M": "#374151",
}


@dataclass(frozen=True)
class TaskCard:
    task_id: str
    job_ref: str
    title: str
    flow: str
    status: str
    lane: str
    priority: str
    luke_action_required: bool
    source_type: str
    updated_utc: str
    notes: str
    proof_required: str
    retest_command: str
    allowed_scope: str
    forbidden_actions: str
    packet_path: str
    source_path: str
    detail_text: str = ""

    @property
    def protected_label(self) -> str:
        if self.luke_action_required:
            return "Luke gate"
        forbidden = self.forbidden_actions.lower()
        if any(word in forbidden for word in ("price", "queue", "sheet", "restart", "delete", "local db")):
            return "Protected boundary"
        return "Safe Codex task"


@dataclass(frozen=True)
class TaskBoard:
    cards: tuple[TaskCard, ...]
    lane_counts: dict[str, int]
    flow_counts: dict[str, int]
    total_cards: int


def load_task_board(
    *,
    root: Path | str | None = None,
    active_only: bool = True,
    flows: Iterable[str] | None = None,
    statuses: Iterable[str] | None = None,
    protected_only: bool = False,
    search: str | None = None,
) -> TaskBoard:
    paths = get_manager_paths(root)
    selected_flows = {_normalise_flow(flow) for flow in flows or [] if _normalise_flow(flow)}
    selected_statuses = {_normalise_status(status) for status in statuses or [] if _normalise_status(status)}
    search_text = _clean_summary(search).lower()

    packet_lookup = {path.stem: path for path in _task_packet_paths(paths.root)}
    rows_by_task_id: dict[str, dict[str, str]] = {}
    for row in _read_csv_rows(paths.output_dir / "approved_task_packets.csv"):
        task_id = _text(row.get("task_id"))
        if _valid_task_id(task_id):
            rows_by_task_id[task_id] = _enrich_with_packet_markdown(row, packet_lookup=packet_lookup, root=paths.root)

    for row in _read_csv_rows(paths.output_dir / "mot" / "mot_worklist.csv"):
        task_id = _text(row.get("work_item_id"))
        if _valid_task_id(task_id) and task_id not in rows_by_task_id:
            rows_by_task_id[task_id] = _enrich_with_packet_markdown(
                _mot_worklist_card_row(row),
                packet_lookup=packet_lookup,
                root=paths.root,
            )

    cards: list[TaskCard] = []
    for row in rows_by_task_id.values():
        card = _card_from_row(row)
        if not card.task_id:
            continue
        if active_only and card.status not in ACTIVE_STATUSES:
            continue
        if selected_flows and card.flow not in selected_flows:
            continue
        if selected_statuses and card.status not in selected_statuses:
            continue
        if protected_only and not card.luke_action_required:
            continue
        if search_text and not _card_matches_search(card, search_text):
            continue
        cards.append(card)

    cards.sort(key=_card_sort_key)
    lane_counts = {lane: 0 for lane in LANE_BY_STATUS.values() if lane != "Proven" or not active_only}
    lane_counter = Counter(card.lane for card in cards)
    for lane, count in lane_counter.items():
        lane_counts[lane] = count
    flow_counts = dict(Counter(card.flow for card in cards))
    return TaskBoard(cards=tuple(cards), lane_counts=lane_counts, flow_counts=flow_counts, total_cards=len(cards))


def lane_names(*, active_only: bool = True) -> list[str]:
    lanes = list(OrderedDict.fromkeys(LANE_BY_STATUS.values()))
    if active_only:
        lanes = [lane for lane in lanes if lane != "Proven"]
    return lanes


def status_options(*, active_only: bool = True) -> list[str]:
    statuses = list(LANE_BY_STATUS.keys())
    if active_only:
        statuses = [status for status in statuses if status != "proved"]
    return statuses


def _card_sort_key(card: TaskCard) -> tuple[int, int, str, str]:
    lane_rank = list(LANE_BY_STATUS.values()).index(card.lane) if card.lane in LANE_BY_STATUS.values() else 99
    priority_rank = {"high": 0, "normal": 1, "low": 2}.get(card.priority.lower(), 9)
    flow_rank = FLOW_ORDER.index(card.flow) if card.flow in FLOW_ORDER else 99
    return (lane_rank, priority_rank, str(flow_rank), card.job_ref or card.task_id)


def _card_matches_search(card: TaskCard, search_text: str) -> bool:
    haystack = " ".join(
        [
            card.job_ref,
            card.title,
            card.task_id,
            card.flow,
            card.status,
            card.notes,
            card.proof_required,
            card.allowed_scope,
            card.detail_text,
        ]
    ).lower()
    return search_text in haystack


def _card_from_row(row: dict[str, str]) -> TaskCard:
    status = _normalise_status(row.get("status")) or "approved"
    flow = _normalise_flow(row.get("flow")) or _flow_from_task_id(row.get("task_id", ""))
    lane = LANE_BY_STATUS.get(status, "Not Started")
    luke_action_required = _truthy(row.get("luke_action_required")) or status == "blocked_needs_luke"
    return TaskCard(
        task_id=_text(row.get("task_id")),
        job_ref=_text(row.get("job_ref")) or _generated_job_ref(row),
        title=_text(row.get("title")) or _text(row.get("task_id")) or "Untitled manager task",
        flow=flow or "M",
        status=status,
        lane=lane,
        priority=_text(row.get("priority")) or "normal",
        luke_action_required=luke_action_required,
        source_type=_text(row.get("source_type")),
        updated_utc=_text(row.get("updated_utc")) or _text(row.get("observed_utc")),
        notes=_clean_summary(row.get("notes") or row.get("manager_action") or row.get("root_cause_guess")),
        proof_required=_clean_summary(row.get("proof_required")),
        retest_command=_text(row.get("retest_command")),
        allowed_scope=_clean_summary(row.get("allowed_scope")),
        forbidden_actions=_clean_summary(row.get("forbidden_actions")),
        packet_path=_text(row.get("packet_path")),
        source_path=_text(row.get("source_path")),
        detail_text=_clean_summary(row.get("detail_text")),
    )


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [{key: value or "" for key, value in row.items() if key is not None} for row in reader]


def _task_packet_paths(root: Path) -> list[Path]:
    task_root = root / "sellerone_manager" / "tasks"
    paths: list[Path] = []
    for folder in ("approved", "blocked"):
        folder_path = task_root / folder
        if folder_path.exists():
            paths.extend(folder_path.glob("*.md"))
    return sorted(paths)


def _enrich_with_packet_markdown(row: dict[str, str], *, packet_lookup: dict[str, Path], root: Path) -> dict[str, str]:
    task_id = _text(row.get("task_id"))
    packet_path = _text(row.get("packet_path"))
    path = Path(packet_path) if packet_path else packet_lookup.get(task_id)
    if path and not path.is_absolute():
        path = root / path
    if not path or not path.exists():
        return row
    packet_row = _packet_markdown_row(path, root=root)
    enriched = dict(row)
    for key in ("job_ref", "notes", "proof_required", "retest_command", "allowed_scope", "forbidden_actions", "detail_text"):
        if not _text(enriched.get(key)) and _text(packet_row.get(key)):
            enriched[key] = packet_row[key]
    if not _text(enriched.get("packet_path")):
        enriched["packet_path"] = str(path)
    return enriched


def _mot_worklist_card_row(row: dict[str, str]) -> dict[str, str]:
    status = _text(row.get("status"))
    title = _text(row.get("title")) or f"{_text(row.get('flow'))} MOT: {_text(row.get('check'))}"
    if status != "blocked_needs_luke" and not _truthy(row.get("luke_action_required")):
        if status == "parked":
            title = re.sub(r"\s+needs Luke decision\b", " is parked", title, flags=re.IGNORECASE)
            title = re.sub(r"\s+needs repair\b", " is parked", title, flags=re.IGNORECASE)
        else:
            title = re.sub(r"\s+needs Luke decision\b", " needs manager review", title, flags=re.IGNORECASE)
    return {
        "task_id": _text(row.get("work_item_id")),
        "job_ref": _text(row.get("job_ref")),
        "flow": _text(row.get("flow")),
        "status": status,
        "priority": _text(row.get("priority")) or "normal",
        "title": title,
        "luke_action_required": _text(row.get("luke_action_required")),
        "notes": _text(row.get("notes")) or _text(row.get("manager_action")),
        "proof_required": _text(row.get("proof_required")),
        "retest_command": _text(row.get("retest_command")),
        "allowed_scope": _text(row.get("allowed_scope")) or _text(row.get("safe_repair_boundary")),
        "forbidden_actions": _text(row.get("forbidden_actions")),
        "source_type": "mot_worklist",
        "source_path": _text(row.get("source_path")),
        "updated_utc": _text(row.get("updated_utc")) or _text(row.get("observed_utc")),
    }


def _packet_markdown_row(path: Path, *, root: Path) -> dict[str, str]:
    markdown = path.read_text(encoding="utf-8", errors="ignore")
    task_id = _field_value(markdown, "task_id") or path.stem
    status = _field_value(markdown, "status") or ("blocked_needs_luke" if path.parent.name == "blocked" else "approved")
    return {
        "task_id": _safe_id(task_id),
        "job_ref": _field_value(markdown, "job_ref"),
        "title": _markdown_title(markdown) or _safe_id(task_id),
        "flow": _field_value(markdown, "flow") or _flow_from_task_id(task_id),
        "status": status,
        "priority": _field_value(markdown, "priority") or "normal",
        "source_type": "packet_markdown",
        "updated_utc": "",
        "luke_action_required": _field_value(markdown, "luke_action_required"),
        "allowed_scope": _field_value(markdown, "allowed_scope") or _section_text(markdown, "Allowed Work"),
        "forbidden_actions": _field_value(markdown, "forbidden_actions") or _section_text(markdown, "Forbidden Work"),
        "proof_required": _field_value(markdown, "proof_required") or _section_text(markdown, "Acceptance Proof"),
        "retest_command": _field_value(markdown, "retest_command"),
        "packet_path": str(path),
        "source_path": str(path.relative_to(root)) if _is_relative_to(path, root) else str(path),
        "notes": _field_value(markdown, "notes") or _section_text(markdown, "Plain English"),
        "detail_text": _detail_excerpt(markdown),
    }


def _field_value(markdown: str, field_name: str) -> str:
    pattern = rf"^\s*-?\s*{re.escape(field_name)}\s*:\s*(?P<value>.*)$"
    match = re.search(pattern, markdown, flags=re.MULTILINE)
    return match.group("value").strip() if match else ""


def _section_text(markdown: str, heading: str) -> str:
    pattern = rf"^## {re.escape(heading)}\s*\n(?P<body>.*?)(?=^## |\Z)"
    match = re.search(pattern, flags=re.MULTILINE | re.DOTALL, string=markdown)
    if not match:
        return ""
    return _clean_summary(match.group("body"))


def _markdown_title(markdown: str) -> str:
    for line in markdown.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _detail_excerpt(markdown: str) -> str:
    lines: list[str] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("```"):
            continue
        lines.append(line)
        if len(" ".join(lines)) > 900:
            break
    return _clean_summary(" ".join(lines))


def _flow_from_task_id(task_id: str) -> str:
    match = re.match(r"^(?:MGR|MOT)_([A-Z])(?:_|$)", _text(task_id))
    return match.group(1) if match else "M"


def _generated_job_ref(row: dict[str, str]) -> str:
    flow = _normalise_flow(row.get("flow")) or _flow_from_task_id(row.get("task_id", ""))
    text = " ".join(
        [
            _text(row.get("title")),
            _text(row.get("check")),
            _text(row.get("source_id")),
            _text(row.get("task_id")),
        ]
    )
    words = re.findall(r"[A-Za-z0-9]+", text.upper().replace("RETURNEDTOKEN", "RETURNED TOKEN"))
    stop = {
        "MOT",
        "MGR",
        "TASK",
        "MANAGER",
        "NEEDS",
        "REPAIR",
        "LUKE",
        "DECISION",
        "PROTECTED",
        "STATUS",
        "STATE",
        "APPLY",
        "LIVE",
        "RETURN",
        "RETURNED",
        "PROOF",
        "PRICE",
        "LIST",
        "LATEST",
        flow,
    }
    tokens: list[str] = []
    for word in words:
        if word in stop or (len(word) == 1 and word.isalpha()):
            continue
        if word not in tokens:
            tokens.append(word)
    if "EMAIL" in tokens and "SOURCE" in tokens:
        tokens = ["EMAIL", "SOURCE"]
    elif "ORIGINAL" in tokens and "TOKEN" in tokens:
        tokens = ["ORIGINAL", "TOKEN"]
    else:
        tokens = tokens[:3]
    return "-".join([flow or "M"] + (tokens or ["JOB"]))


def _normalise_flow(value: object) -> str:
    text = _text(value).upper()
    if text in FLOW_ORDER:
        return text
    if text.startswith("MGR_") or text.startswith("MOT_"):
        return _flow_from_task_id(text)
    return text[:1] if text[:1] in FLOW_ORDER else ""


def _normalise_status(value: object) -> str:
    text = _text(value).lower().strip()
    if text in {"new", "assigned"}:
        return "approved"
    return text


def _truthy(value: object) -> bool:
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _safe_id(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_]+", "_", _text(value)).strip("_")
    return text[:96] or "manager_task"


def _valid_task_id(value: str) -> bool:
    text = _text(value)
    return bool(text) and not bool(re.search(r"\s|`", text))


def _clean_summary(value: object) -> str:
    text = _text(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _text(value: object) -> str:
    return str(value or "").strip()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
