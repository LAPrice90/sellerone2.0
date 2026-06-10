from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BOOT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT))

from scripts.flows.O.O482_build_po_draft_file_shape_preview import build_po_draft_file_shape_preview
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract
from scripts.flows.O._schemas import get_o_output_contract


ZERO_FLAG_COLUMNS = (
    "po_file_write_allowed",
    "po_creation_allowed",
    "purchase_commitment_allowed",
    "receiving_allowed",
    "send_to_amazon_allowed",
    "creates_live_action",
)
UNSAFE_TEXT_TOKENS = (
    "purchase_order",
    "purchase order",
    "po_created",
    "po created",
    "committed",
    "sent_to_amazon",
    "sent to amazon",
    "buy_committed",
    "approval_applied",
    "live_action",
)
STAGES = (
    {
        "stage_key": "po_draft_readiness",
        "stage_label": "PO draft readiness",
        "source_contract": "restock_po_draft_readiness_preview_lines_live",
        "health_contract": "restock_po_draft_readiness_preview_health",
        "state_column": "po_draft_readiness_state",
        "ready_states": {"ready_for_local_po_draft_review_only"},
        "blocked_state": "blocked_from_local_po_draft_review",
    },
    {
        "stage_key": "po_line_design",
        "stage_label": "PO line design",
        "source_contract": "restock_po_line_design_preview_lines_live",
        "health_contract": "restock_po_line_design_preview_health",
        "state_column": "line_design_state",
        "ready_states": {"ready_for_local_po_line_design_review_only"},
        "blocked_state": "blocked_from_local_po_line_design_review",
    },
    {
        "stage_key": "po_draft_packet_review",
        "stage_label": "PO draft packet review",
        "source_contract": "restock_po_draft_packet_review_lines_live",
        "health_contract": "restock_po_draft_packet_review_health",
        "state_column": "packet_review_line_state",
        "ready_states": {"ready_for_local_po_draft_packet_review_only"},
        "blocked_state": "blocked_from_local_po_draft_packet_review",
    },
    {
        "stage_key": "po_draft_hold_review",
        "stage_label": "PO draft hold review",
        "source_contract": "restock_po_draft_hold_review_lines_live",
        "health_contract": "restock_po_draft_hold_review_health",
        "state_column": "hold_review_line_state",
        "ready_states": {"held_for_local_po_draft_review_only"},
        "blocked_state": "blocked_from_local_po_draft_hold_review",
    },
    {
        "stage_key": "po_draft_file_shape",
        "stage_label": "PO draft file-shape preview",
        "source_contract": "restock_po_draft_file_shape_preview_lines_live",
        "health_contract": "restock_po_draft_file_shape_preview_health",
        "state_column": "file_shape_line_state",
        "ready_states": {"ready_for_local_po_draft_file_shape_review_only"},
        "blocked_state": "blocked_from_local_po_draft_file_shape_review",
    },
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _contains_unsafe_language(*values: object) -> bool:
    text = " ".join(_normalize_text(value).lower() for value in values)
    return any(token in text for token in UNSAFE_TEXT_TOKENS)


def _contract_path(root: Path, contract_name: str) -> Path:
    return root / get_o_output_contract(contract_name).rel_path


def _stage_row(summary_utc: str, root: Path, stage: dict[str, object]) -> dict[str, str]:
    source_contract = _normalize_text(stage.get("source_contract", ""))
    health_contract = _normalize_text(stage.get("health_contract", ""))
    state_column = _normalize_text(stage.get("state_column", ""))
    ready_states = {str(value) for value in stage.get("ready_states", set())}
    blocked_state = _normalize_text(stage.get("blocked_state", ""))
    line_path = _contract_path(root, source_contract)
    health_path = _contract_path(root, health_contract)
    line_df = read_o_contract_df(root, source_contract)
    health_df = read_o_contract_df(root, health_contract)
    missing_files = [path.name for path in (line_path, health_path) if not path.exists()]
    health_bad_rows = health_df[health_df.get("status", pd.Series(dtype=str)).map(_normalize_text).str.lower().ne("ok")].copy()
    states = line_df.get(state_column, pd.Series(dtype=str)).map(_normalize_text)
    known_states = set(ready_states)
    if blocked_state:
        known_states.add(blocked_state)
    ready_or_held_rows = int(states.isin(ready_states).sum()) if not states.empty else 0
    blocked_rows = int(states.eq(blocked_state).sum()) if not states.empty else 0
    unknown_state_rows = int((states.ne("") & ~states.isin(known_states)).sum()) if not states.empty else 0

    reasons: list[str] = []
    if missing_files:
        reasons.append("missing_stage_file")
    if len(health_bad_rows.index):
        reasons.append("source_health_not_ok")
    if unknown_state_rows:
        reasons.append("unknown_line_state")
    if blocked_rows:
        reasons.append("stage_has_blocked_rows")

    if missing_files:
        stage_state = "not_verified_missing_source"
    elif len(health_bad_rows.index) or unknown_state_rows:
        stage_state = "blocked_by_stage_health"
    elif line_df.empty:
        stage_state = "built_waiting_for_rows"
    elif blocked_rows:
        stage_state = "local_preview_blocked"
    else:
        stage_state = "local_preview_ready_or_held"

    row = {
        "summary_utc": summary_utc,
        "stage_key": _normalize_text(stage.get("stage_key", "")),
        "stage_label": _normalize_text(stage.get("stage_label", "")),
        "source_contract": source_contract,
        "source_health_contract": health_contract,
        "state_column": state_column,
        "line_rows": str(len(line_df.index)),
        "ready_or_held_rows": str(ready_or_held_rows),
        "blocked_rows": str(blocked_rows),
        "health_rows": str(len(health_df.index)),
        "health_bad_rows": str(len(health_bad_rows.index)),
        "stage_state": stage_state,
        "stage_block_reasons": "|".join(dict.fromkeys(reasons)),
    }
    for column in ZERO_FLAG_COLUMNS:
        row[column] = "0"
    return row


def _build_summary(summary_utc: str, root: Path) -> pd.DataFrame:
    return pd.DataFrame([_stage_row(summary_utc, root, stage) for stage in STAGES])


def _build_health(summary_utc: str, summary_df: pd.DataFrame, root: Path) -> pd.DataFrame:
    source_paths = [
        _contract_path(root, _normalize_text(stage.get("source_contract", "")))
        for stage in STAGES
    ] + [
        _contract_path(root, _normalize_text(stage.get("health_contract", "")))
        for stage in STAGES
    ]
    missing_files = [path.name for path in source_paths if not path.exists()]
    live_action_rows: list[str] = []
    live_language_rows: list[str] = []
    stage_health_bad: list[str] = []
    if not summary_df.empty:
        for _, row in summary_df.iterrows():
            stage_key = _normalize_text(row.get("stage_key", "")) or "missing_stage"
            if any(_normalize_text(row.get(column, "")) != "0" for column in ZERO_FLAG_COLUMNS):
                live_action_rows.append(stage_key)
            if _contains_unsafe_language(row.get("stage_state", ""), row.get("stage_block_reasons", "")):
                live_language_rows.append(stage_key)
            if _normalize_text(row.get("health_bad_rows", "")) not in {"", "0"}:
                stage_health_bad.append(stage_key)
    checks = [
        (
            "stage_count_guard",
            len(summary_df.index) == len(STAGES),
            f"summary_rows={len(summary_df.index)};expected_rows={len(STAGES)}",
            "PO preview construction summary must show every local preview stage in one place.",
        ),
        (
            "source_file_guard",
            not missing_files,
            f"missing_files={len(missing_files)}",
            "PO preview construction summary must be built from existing local preview proof files.",
        ),
        (
            "local_only_guard",
            not live_action_rows and not live_language_rows,
            f"live_action_rows={len(live_action_rows)};live_language_rows={len(live_language_rows)}",
            "PO preview construction summary must not claim PO creation, buying, receiving, or Amazon handoff.",
        ),
        (
            "source_health_guard",
            not stage_health_bad,
            f"stage_health_bad={len(stage_health_bad)}",
            "PO preview construction summary must show source-stage health blockers instead of hiding them.",
        ),
    ]
    source_path_text = ";".join(str(path) for path in source_paths)
    return pd.DataFrame(
        [
            {
                "check_utc": summary_utc,
                "check": check,
                "status": "ok" if passed else "fail",
                "value": value,
                "notes": notes,
                "source_path": source_path_text,
            }
            for check, passed, value, notes in checks
        ]
    )


def build_po_preview_construction_summary(
    root: Path | None = None,
    *,
    summary_utc: str | None = None,
    write_outputs: bool = True,
    refresh_file_shape: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    paths = ensure_o_directories(root=root_path)
    observed = summary_utc or _utc_now_iso()
    if refresh_file_shape:
        build_po_draft_file_shape_preview(
            root=root_path,
            shape_utc=observed,
            write_outputs=write_outputs,
            refresh_hold_review=True,
        )
    summary_df = _build_summary(observed, root_path)
    health_df = _build_health(observed, summary_df, root_path)
    if write_outputs:
        summary_df = write_o_contract_df(root_path, "restock_po_preview_construction_summary_live", summary_df)
        health_df = write_o_contract_df(root_path, "restock_po_preview_construction_summary_health", health_df)
        history_dir = paths.history_dir / f"po_preview_construction_summary_v1_{observed.replace(':', '').replace('-', '')}"
        history_dir.mkdir(parents=True, exist_ok=True)
        summary_df.to_csv(history_dir / "restock_po_preview_construction_summary_live.csv", index=False)
        health_df.to_csv(history_dir / "restock_po_preview_construction_summary_health.csv", index=False)
    return summary_df, health_df


def main() -> int:
    summary_df, health_df = build_po_preview_construction_summary()
    bad_health = health_df[health_df.get("status", "").map(_normalize_text).ne("ok")]
    print(f"po_preview_construction_summary_rows={len(summary_df.index)}")
    print(f"health_status={'ok' if bad_health.empty else 'fail'}")
    return 0 if bad_health.empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
