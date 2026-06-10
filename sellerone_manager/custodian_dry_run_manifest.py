from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .paths import get_manager_paths


MANIFEST_CSV_REL_PATH = Path("sellerone_manager") / "CONTROL" / "CUSTODIAN_DRY_RUN_MANIFEST.csv"
MANIFEST_MD_REL_PATH = Path("sellerone_manager") / "CONTROL" / "CUSTODIAN_DRY_RUN_MANIFEST.md"
OUT_SUBTREE_INDEX_REL_PATH = Path("sellerone_manager") / "CONTROL" / "STORAGE_INDEX_OUT_SUBTREE.csv"

MANIFEST_COLUMNS = [
    "path",
    "retention_class",
    "size_mb",
    "file_count",
    "manifest_action",
    "approval_required",
    "protected_exclusion",
    "rule",
    "recovery_route",
    "notes",
]


@dataclass(frozen=True)
class CustodianDryRunManifestResult:
    csv_path: Path
    markdown_path: Path
    rows: list[dict[str, str]]
    markdown: str
    generated_utc: str
    total_rows: int
    approval_required_count: int
    protected_exclusion_count: int
    preview_candidate_size_mb: float
    protected_size_mb: float
    action_counts: Counter[str]
    recommended_next_task: str


def utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_custodian_dry_run_manifest(
    *,
    root: Path | str | None = None,
    generated_utc: str | None = None,
) -> CustodianDryRunManifestResult:
    paths = get_manager_paths(root)
    generated = generated_utc or utc_now_text()
    control_dir = paths.root / "sellerone_manager" / "CONTROL"
    source_path = paths.root / OUT_SUBTREE_INDEX_REL_PATH
    csv_path = paths.root / MANIFEST_CSV_REL_PATH
    markdown_path = paths.root / MANIFEST_MD_REL_PATH

    source_rows = _read_csv_rows(source_path)
    rows = [_manifest_row(row) for row in source_rows]
    action_counts: Counter[str] = Counter(row["manifest_action"] for row in rows)
    approval_count = sum(1 for row in rows if row["approval_required"] == "yes")
    protected_count = sum(1 for row in rows if row["protected_exclusion"] == "yes")
    preview_candidate_size = sum(_float(row["size_mb"]) for row in rows if row["manifest_action"].startswith("preview_"))
    protected_size = sum(_float(row["size_mb"]) for row in rows if row["protected_exclusion"] == "yes")
    markdown = _build_markdown(
        generated_utc=generated,
        source_path=source_path,
        rows=rows,
        action_counts=action_counts,
        approval_required_count=approval_count,
        protected_exclusion_count=protected_count,
        preview_candidate_size_mb=preview_candidate_size,
        protected_size_mb=protected_size,
    )
    return CustodianDryRunManifestResult(
        csv_path=csv_path,
        markdown_path=markdown_path,
        rows=rows,
        markdown=markdown,
        generated_utc=generated,
        total_rows=len(rows),
        approval_required_count=approval_count,
        protected_exclusion_count=protected_count,
        preview_candidate_size_mb=preview_candidate_size,
        protected_size_mb=protected_size,
        action_counts=action_counts,
        recommended_next_task="SO21-DEAD-AUTOMATION-AND-SCHEDULER-REVIEW",
    )


def write_custodian_dry_run_manifest(
    *,
    root: Path | str | None = None,
    generated_utc: str | None = None,
) -> CustodianDryRunManifestResult:
    result = build_custodian_dry_run_manifest(root=root, generated_utc=generated_utc)
    result.csv_path.parent.mkdir(parents=True, exist_ok=True)
    with result.csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        for row in result.rows:
            writer.writerow({column: row.get(column, "") for column in MANIFEST_COLUMNS})
    result.markdown_path.write_text(result.markdown, encoding="utf-8")
    return result


def format_custodian_dry_run_manifest_status(result: CustodianDryRunManifestResult) -> str:
    action_text = ",".join(f"{action}:{count}" for action, count in sorted(result.action_counts.items()))
    return "\n".join(
        [
            "status=written",
            f"csv_path={result.csv_path}",
            f"markdown_path={result.markdown_path}",
            f"generated_utc={result.generated_utc}",
            f"rows={result.total_rows}",
            f"approval_required={result.approval_required_count}",
            f"protected_exclusions={result.protected_exclusion_count}",
            f"preview_candidate_size_mb={_format_number(result.preview_candidate_size_mb)}",
            f"protected_size_mb={_format_number(result.protected_size_mb)}",
            f"action_counts={action_text}",
            f"recommended_next_task={result.recommended_next_task}",
        ]
    )


def _manifest_row(row: dict[str, str]) -> dict[str, str]:
    retention_class = _text(row.get("retention_class")) or "unknown"
    action, approval, protected, rule, recovery = _rules_for_class(retention_class)
    notes = _text(row.get("notes")) or _text(row.get("role")) or "classified from storage index"
    return {
        "path": _text(row.get("path")),
        "retention_class": retention_class,
        "size_mb": _normalise_number(row.get("size_mb")),
        "file_count": _normalise_int(row.get("file_count")),
        "manifest_action": action,
        "approval_required": approval,
        "protected_exclusion": protected,
        "rule": rule,
        "recovery_route": recovery,
        "notes": notes,
    }


def _rules_for_class(retention_class: str) -> tuple[str, str, str, str, str]:
    rules = {
        "current_runtime": (
            "exclude_keep",
            "no",
            "yes",
            "Live runtime, locks, and current proof stay protected.",
            "Not applicable - no cleanup action is proposed.",
        ),
        "manual_protected": (
            "exclude_keep",
            "no",
            "yes",
            "Human-created control or business-critical files stay protected.",
            "Not applicable - no cleanup action is proposed.",
        ),
        "code_protected": (
            "exclude_keep",
            "no",
            "yes",
            "Source code, tests, and Git history need a code-maintenance ticket.",
            "Not applicable - no cleanup action is proposed.",
        ),
        "raw_import": (
            "exclude_keep",
            "no",
            "yes",
            "Canonical source proof stays protected until a source-specific dedupe rule exists.",
            "Not applicable - no cleanup action is proposed.",
        ),
        "temp_debug": (
            "preview_purge_candidate",
            "yes",
            "no",
            "Dry-run purge candidate only after active-owner and lock checks.",
            "No action taken. Before apply, create an exact purge manifest and rollback or quarantine route.",
        ),
        "audit_history": (
            "preview_archive_candidate",
            "yes",
            "no",
            "Audit and proof history may be archived by exact manifest only.",
            "No action taken. Before apply, create archive destination and restore route.",
        ),
        "derived_report": (
            "preview_archive_candidate",
            "yes",
            "no",
            "Derived reports may be archived only when source evidence is still present.",
            "No action taken. Before apply, create archive destination and rebuild proof route.",
        ),
        "failed_partial": (
            "preview_purge_candidate",
            "yes",
            "no",
            "Failed partial outputs may be purged only after the investigation closes.",
            "No action taken. Before apply, confirm no active investigation references the path.",
        ),
        "rollback": (
            "manifest_keep_count_review",
            "yes",
            "no",
            "Rollback folders need a fixed keep-count policy before archive or purge.",
            "No action taken. Rollback sources remain available for recovery.",
        ),
        "state_rolling": (
            "manifest_keep_count_review",
            "yes",
            "no",
            "Rolling state snapshots need latest-plus-history keep rules before cleanup.",
            "No action taken. Current and recent history remain available.",
        ),
        "mixed_current_and_history": (
            "manifest_grouping_required",
            "yes",
            "yes",
            "Mixed roots must be split into exact files or subgroups before any cleanup is proposed.",
            "No action taken. Future review must separate live files from historical files first.",
        ),
    }
    return rules.get(
        retention_class,
        (
            "manual_review_required",
            "yes",
            "yes",
            "Unknown retention class needs manual classification before cleanup.",
            "No action taken. Classify this path before any archive or purge plan.",
        ),
    )


def _build_markdown(
    *,
    generated_utc: str,
    source_path: Path,
    rows: list[dict[str, str]],
    action_counts: Counter[str],
    approval_required_count: int,
    protected_exclusion_count: int,
    preview_candidate_size_mb: float,
    protected_size_mb: float,
) -> str:
    lines = [
        "# SellerOne Custodian Dry-Run Manifest",
        "",
        "Job: `SO21-CUSTODIAN-DRY-RUN-MANIFEST`",
        f"Generated UTC: {generated_utc}",
        "Generated by: `sellerone_manager.custodian_dry_run_manifest`",
        "",
        "## Plain-English Status",
        "",
        (
            "This is a preview-only cleanup manifest. No cleanup was performed: no files were deleted, moved, "
            "compressed, purged, or archived."
        ),
        "",
        "The manifest converts the `out/` storage index into plain cleanup decisions so Luke can see what is protected "
        "and what could become a future approval-based cleanup candidate.",
        "",
        "## Summary",
        "",
        f"- Source index: `{_display_path(source_path)}`",
        f"- Manifest rows: {len(rows)}",
        f"- Rows needing future approval before any apply: {approval_required_count}",
        f"- Protected exclusions: {protected_exclusion_count}",
        f"- Preview candidate size: {_format_number(preview_candidate_size_mb)} MB",
        f"- Protected size: {_format_number(protected_size_mb)} MB",
        "- Recommended next task: `SO21-DEAD-AUTOMATION-AND-SCHEDULER-REVIEW`",
        "",
        "## Action Counts",
        "",
    ]
    if not action_counts:
        lines.append("No storage index rows were available.")
    else:
        for action, count in sorted(action_counts.items()):
            lines.append(f"- `{action}`: {count}")
    lines.extend(
        [
            "",
            "## Largest Future Cleanup Candidates",
            "",
        ]
    )
    candidates = [
        row
        for row in rows
        if row["manifest_action"] != "exclude_keep" and row["manifest_action"] != "manual_review_required"
    ]
    if not candidates:
        lines.append("No future cleanup candidates are visible.")
    else:
        lines.extend(_format_table(sorted(candidates, key=lambda row: _float(row["size_mb"]), reverse=True)[:12]))
    lines.extend(
        [
            "",
            "## Protected Exclusions",
            "",
        ]
    )
    protected_rows = [row for row in rows if row["protected_exclusion"] == "yes"]
    if not protected_rows:
        lines.append("No protected exclusions were found.")
    else:
        lines.extend(_format_table(sorted(protected_rows, key=lambda row: _float(row["size_mb"]), reverse=True)[:12]))
    lines.extend(
        [
            "",
            "## Rules",
            "",
            "- This manifest is not approval to delete anything.",
            "- `exclude_keep` rows are protected from cleanup.",
            "- `preview_` rows are candidates only; they still need live-owner checks and explicit apply approval.",
            "- `manifest_keep_count_review` rows need a keep-count rule before action.",
            "- `manifest_grouping_required` rows must be split into exact files or subgroups before action.",
            "- Any future apply must create a fresh exact manifest and recovery route first.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _format_table(rows: list[dict[str, str]]) -> list[str]:
    lines = ["| Path | Class | Size MB | Action | Protected | Rule |", "|---|---|---:|---|---|---|"]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_code(row["path"]),
                    _md(row["retention_class"]),
                    _md(row["size_mb"]),
                    _md(row["manifest_action"]),
                    _md(row["protected_exclusion"]),
                    _md(_short(row["rule"], 110)),
                ]
            )
            + " |"
        )
    return lines


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [{key: value or "" for key, value in row.items()} for row in reader]


def _normalise_number(value: object) -> str:
    return _format_number(_float(value))


def _normalise_int(value: object) -> str:
    text = _text(value)
    if not text:
        return "0"
    try:
        return str(int(float(text.replace(",", ""))))
    except ValueError:
        return "0"


def _float(value: object) -> float:
    text = _text(value)
    if not text:
        return 0.0
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return 0.0


def _format_number(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text or "0"


def _display_path(path: Path) -> str:
    parts = path.parts
    try:
        index = parts.index("sellerone_manager")
    except ValueError:
        return str(path)
    return str(Path(*parts[index:]))


def _text(value: object) -> str:
    return str(value or "").strip()


def _short(value: str, limit: int) -> str:
    cleaned = " ".join(_text(value).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + "..."


def _md(value: str) -> str:
    return _text(value).replace("|", "\\|")


def _md_code(value: str) -> str:
    safe = _md(value).replace("`", "")
    return f"`{safe}`" if safe else "`unknown`"
