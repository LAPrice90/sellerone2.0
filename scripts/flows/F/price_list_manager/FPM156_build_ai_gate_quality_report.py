from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager._io import normalize_text, write_csv
from scripts.flows.F.price_list_manager._paths import get_manager_paths
from scripts.flows.F.price_list_manager._schemas import MANAGER_HEALTH_COLUMNS
from scripts.flows.O.O400_operator_ui import build_ai_product_check_gate_df, load_feeder_review_source_df

VALID_CODEX_AI_ACTIONS = {
    "allow_if_other_checks_pass",
    "manual_review",
    "rescan_needed",
    "remove_from_clean_pass",
}
VISIBLE_AI_STATES = {"ai_cleared", "needs_user_guidance"}
FALLBACK_REVIEWERS = {"fpm155_secondary_evidence_guard"}
TITLE_CLEAR_BUCKETS = {
    "ai_review_clear",
    "same_product_confirmed_by_combined_amazon_text",
    "title_match_clear",
}
PROOF_EXAMPLE_LIMIT = 3
QUEUE_PROOF_DETAIL_COLUMNS = [
    "profit_on_cost_pct",
    "title_match_profit_on_cost_pct",
    "profit_per_unit_gbp",
    "expected_profit_gbp",
    "supplier_unit_cost_gbp",
    "amazon_sell_price_gbp",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _current_key(row: pd.Series) -> str:
    supplier = normalize_text(row.get("supplier_id", "")).lower()
    supplier_sku = normalize_text(row.get("supplier_sku", "")).upper()
    asin = normalize_text(row.get("asin", "")).upper()
    if supplier and supplier_sku and asin:
        return f"product|{supplier}|{supplier_sku}|{asin}"
    decision_id = normalize_text(row.get("f032_decision_id", ""))
    if supplier and decision_id:
        return f"decision|{supplier}|{decision_id}"
    return (
        f"row|{normalize_text(row.get('handoff_id', ''))}|{normalize_text(row.get('run_id', ''))}|"
        f"{decision_id}|{supplier_sku}|{asin}"
    )


def _blank_count(df: pd.DataFrame, column: str, mask: pd.Series | None = None) -> int:
    if df.empty or column not in df.columns:
        return 0
    series = df[column].map(normalize_text)
    if mask is not None:
        series = series[mask]
    return int(series.eq("").sum())


def _text_series(df: pd.DataFrame, column: str) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=str)
    if column not in df.columns:
        return pd.Series([""] * len(df.index), index=df.index, dtype=str)
    return df[column].map(normalize_text)


def _invalid_action_count(df: pd.DataFrame) -> int:
    if df.empty or "codex_ai_action" not in df.columns:
        return 0
    actions = df["codex_ai_action"].map(normalize_text)
    return int(actions.ne("").sum() - actions.isin(VALID_CODEX_AI_ACTIONS).sum())


def _read_any_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _join_example_parts(*parts: object) -> str:
    return " / ".join(part for part in (normalize_text(value) for value in parts) if part)


def _row_examples(df: pd.DataFrame, columns: list[str], *, limit: int = PROOF_EXAMPLE_LIMIT) -> str:
    if df.empty:
        return ""
    examples: list[str] = []
    for _, row in df.head(limit).iterrows():
        example = _join_example_parts(*(row.get(column, "") for column in columns))
        if example:
            examples.append(example)
    return "; ".join(examples)


def _notes_with_examples(notes: str, examples: str) -> str:
    clean_examples = normalize_text(examples)
    if not clean_examples:
        return notes
    return f"{notes} Examples: {clean_examples}."


def _decision_id_series(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=str)
    if "f032_decision_id" not in df.columns:
        return pd.Series([""] * len(df.index), index=df.index, dtype=str)
    return df["f032_decision_id"].map(normalize_text)


def _active_queue_decision_proof(root_path: Path) -> dict[str, object]:
    paths = get_manager_paths(root=root_path)
    handoff_root = paths.system_dir / "review_handoffs"
    if not handoff_root.exists():
        return {
            "queue_rows": 0,
            "decision_rows": 0,
            "queue_missing_decision_id_rows": 0,
            "decision_missing_decision_id_rows": 0,
            "duplicate_decision_id_rows": 0,
            "missing_decision_rows": 0,
            "stale_decision_rows": 0,
            "missing_decision_examples": "",
            "stale_decision_examples": "",
        }

    queue_rows = 0
    decision_rows = 0
    queue_missing_id_rows = 0
    decision_missing_id_rows = 0
    duplicate_decision_id_rows = 0
    missing_decision_rows = 0
    stale_decision_rows = 0
    missing_records: list[dict[str, str]] = []
    stale_records: list[dict[str, str]] = []

    for queue_path in sorted(handoff_root.glob("*/*/ai_review_queue.csv")):
        run_dir = queue_path.parent
        supplier_id = normalize_text(run_dir.parent.name)
        run_id = normalize_text(run_dir.name)
        decision_path = run_dir / "codex_ai_review_decisions.csv"
        queue_df = _read_any_csv(queue_path)
        decision_df = _read_any_csv(decision_path)
        queue_rows += len(queue_df.index)
        decision_rows += len(decision_df.index)

        queue_ids = _decision_id_series(queue_df)
        decision_ids = _decision_id_series(decision_df)
        queue_missing_id_rows += int(queue_ids.eq("").sum())
        decision_missing_id_rows += int(decision_ids.eq("").sum())
        duplicate_decision_id_rows += int(decision_ids[decision_ids.ne("")].duplicated().sum())

        queue_id_set = set(queue_ids[queue_ids.ne("")])
        decision_id_set = set(decision_ids[decision_ids.ne("")])

        missing_ids = queue_id_set - decision_id_set
        if missing_ids:
            missing_df = queue_df[queue_ids.isin(missing_ids)].copy()
            missing_decision_rows += len(missing_df.index)
            for _, row in missing_df.head(PROOF_EXAMPLE_LIMIT).iterrows():
                if len(missing_records) < PROOF_EXAMPLE_LIMIT:
                    missing_records.append(
                        {
                            "supplier_id": supplier_id,
                            "run_id": run_id,
                            "supplier_sku": normalize_text(row.get("supplier_sku", "")),
                            "asin": normalize_text(row.get("asin", "")),
                            "f032_decision_id": normalize_text(row.get("f032_decision_id", "")),
                        }
                    )

        stale_ids = decision_id_set - queue_id_set
        if stale_ids:
            stale_df = decision_df[decision_ids.isin(stale_ids)].copy()
            stale_decision_rows += len(stale_df.index)
            for _, row in stale_df.head(PROOF_EXAMPLE_LIMIT).iterrows():
                if len(stale_records) < PROOF_EXAMPLE_LIMIT:
                    stale_records.append(
                        {
                            "supplier_id": supplier_id,
                            "run_id": run_id,
                            "f032_decision_id": normalize_text(row.get("f032_decision_id", "")),
                            "codex_ai_action": normalize_text(row.get("codex_ai_action", "")),
                        }
                    )

    missing_examples = _row_examples(
        pd.DataFrame(missing_records),
        ["supplier_id", "run_id", "supplier_sku", "asin", "f032_decision_id"],
    )
    stale_examples = _row_examples(
        pd.DataFrame(stale_records),
        ["supplier_id", "run_id", "f032_decision_id", "codex_ai_action"],
    )
    return {
        "queue_rows": queue_rows,
        "decision_rows": decision_rows,
        "queue_missing_decision_id_rows": queue_missing_id_rows,
        "decision_missing_decision_id_rows": decision_missing_id_rows,
        "duplicate_decision_id_rows": duplicate_decision_id_rows,
        "missing_decision_rows": missing_decision_rows,
        "stale_decision_rows": stale_decision_rows,
        "missing_decision_examples": missing_examples,
        "stale_decision_examples": stale_examples,
    }


def _final_review_proof(root_path: Path) -> dict[str, object]:
    frames: list[pd.DataFrame] = []
    for lane in ("passes", "near_misses"):
        lane_df = load_feeder_review_source_df(lane, root=root_path).fillna("")
        if lane_df.empty:
            continue
        lane_df = lane_df.copy()
        lane_df["_review_lane"] = lane
        frames.append(lane_df)
    if not frames:
        return {
            "rows": 0,
            "missing_ai_compare_note_rows": 0,
            "missing_ai_confidence_note_rows": 0,
            "missing_ai_compare_examples": "",
        }
    review_df = pd.concat(frames, ignore_index=True)
    helper_text = review_df["helper_text"].map(normalize_text) if "helper_text" in review_df.columns else pd.Series("", index=review_df.index)
    missing_confidence_mask = ~helper_text.str.contains("ai_match_confidence=", regex=False)
    missing_compare_mask = ~helper_text.str.contains("ai_compare=", regex=False)
    missing_any_mask = missing_confidence_mask | missing_compare_mask
    examples = _row_examples(
        review_df[missing_any_mask].copy(),
        ["_review_lane", "supplier_sku", "asin", "title", "helper_text"],
    )
    return {
        "rows": int(len(review_df.index)),
        "missing_ai_compare_note_rows": int(missing_any_mask.sum()),
        "missing_ai_confidence_note_rows": int(missing_confidence_mask.sum()),
        "missing_ai_compare_examples": examples,
    }


def _current_rows_with_queue_details(current_df: pd.DataFrame) -> pd.DataFrame:
    if current_df.empty:
        return current_df.copy()
    queue_cache: dict[str, pd.DataFrame] = {}
    rows: list[dict[str, str]] = []
    for _, row in current_df.iterrows():
        record = {column: normalize_text(value) for column, value in row.to_dict().items()}
        queue_path_text = normalize_text(record.get("queue_path", ""))
        decision_id = normalize_text(record.get("f032_decision_id", ""))
        queue_row: dict[str, str] = {}
        if queue_path_text and decision_id:
            if queue_path_text not in queue_cache:
                queue_cache[queue_path_text] = _read_any_csv(Path(queue_path_text))
            queue_df = queue_cache[queue_path_text]
            if not queue_df.empty and "f032_decision_id" in queue_df.columns:
                match = queue_df[queue_df["f032_decision_id"].map(normalize_text).eq(decision_id)]
                if not match.empty:
                    queue_row = {column: normalize_text(value) for column, value in match.iloc[0].to_dict().items()}
        for column in QUEUE_PROOF_DETAIL_COLUMNS:
            record[f"queue_{column}"] = normalize_text(queue_row.get(column, ""))
        rows.append(record)
    return pd.DataFrame(rows).fillna("")


def _commercial_signal_mask(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=bool)
    mask = pd.Series(False, index=df.index)
    for column in [
        "roi_pct",
        "queue_profit_on_cost_pct",
        "queue_title_match_profit_on_cost_pct",
        "queue_profit_per_unit_gbp",
        "queue_expected_profit_gbp",
    ]:
        if column in df.columns:
            mask = mask | df[column].map(normalize_text).ne("")
    return mask


def _profit_fallback_mask(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=bool)
    roi_present = df["roi_pct"].map(normalize_text).ne("") if "roi_pct" in df.columns else pd.Series(False, index=df.index)
    profit_present = pd.Series(False, index=df.index)
    for column in ["queue_profit_per_unit_gbp", "queue_expected_profit_gbp"]:
        if column in df.columns:
            profit_present = profit_present | df[column].map(normalize_text).ne("")
    return ~roi_present & profit_present


def _high_confidence_clear_match_mask(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=bool)
    action = _text_series(df, "codex_ai_action").eq("allow_if_other_checks_pass")
    confidence = _text_series(df, "codex_ai_confidence").str.lower().eq("high")
    bucket_match = (
        _text_series(df, "codex_ai_decision_bucket").str.lower().isin(TITLE_CLEAR_BUCKETS)
        | _text_series(df, "f032_rule_bucket").str.lower().isin(TITLE_CLEAR_BUCKETS)
        | _text_series(df, "f032_decision_bucket").str.lower().isin(TITLE_CLEAR_BUCKETS)
    )
    return action & confidence & bucket_match


def _duplicate_group_count(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    keys = df.apply(_current_key, axis=1)
    counts = keys.value_counts()
    return int((counts > 1).sum())


def _row(
    *,
    observed_utc: str,
    check: str,
    status: str,
    value: object,
    notes: str,
    source_path: Path,
) -> dict[str, str]:
    return {
        "check": check,
        "status": status,
        "value": str(value),
        "notes": notes,
        "observed_utc": observed_utc,
        "source_path": str(source_path),
    }


def _write_summary(path: Path, *, observed_utc: str, health: pd.DataFrame, current_rows: int, history_rows: int) -> None:
    fail_rows = int(health["status"].eq("fail").sum()) if not health.empty else 0
    warn_rows = int(health["status"].eq("warn").sum()) if not health.empty else 0
    overall = "fail" if fail_rows else ("warn" if warn_rows else "ok")
    lines = [
        "# AI Gate Quality Report",
        "",
        f"- Observed UTC: {observed_utc}",
        f"- Overall status: {overall}",
        f"- Current UI rows: {current_rows}",
        f"- Full audit rows: {history_rows}",
        f"- Hard fail checks: {fail_rows}",
        f"- Warning checks: {warn_rows}",
        "",
        "## Checks",
        "",
    ]
    for record in health.to_dict("records"):
        lines.append(
            f"- {normalize_text(record.get('status', '')).upper()} - "
            f"{normalize_text(record.get('check', ''))}: {normalize_text(record.get('value', ''))} - "
            f"{normalize_text(record.get('notes', ''))}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_ai_gate_quality_report(
    *,
    root: Path | None = None,
    observed_utc: str | None = None,
) -> dict[str, object]:
    root_path = Path(root) if root is not None else ROOT
    observed = observed_utc or _utc_now_iso()
    paths = get_manager_paths(root=root_path)
    live_dir = paths.system_dir / "live"
    report_path = live_dir / "ai_gate_quality_report.csv"
    summary_path = live_dir / "ai_gate_quality_summary.md"

    history_df = build_ai_product_check_gate_df(root=root_path, include_history=True).fillna("")
    current_df = build_ai_product_check_gate_df(root=root_path).fillna("")
    current_detail_df = _current_rows_with_queue_details(current_df)
    visible_mask = (
        current_detail_df["operator_visible_flag"].map(normalize_text).eq("1")
        & current_detail_df["queue_state"].map(normalize_text).isin(VISIBLE_AI_STATES)
    ) if not current_detail_df.empty else pd.Series(dtype=bool)
    clear_match_mask = _high_confidence_clear_match_mask(current_detail_df)
    fallback_visible_mask = (
        visible_mask
        & current_detail_df["codex_ai_reviewer"].map(normalize_text).isin(FALLBACK_REVIEWERS)
        & ~clear_match_mask
    ) if not current_detail_df.empty else pd.Series(dtype=bool)
    low_visible_mask = (
        visible_mask
        & current_detail_df["codex_ai_confidence"].map(normalize_text).str.lower().eq("low")
    ) if not current_detail_df.empty else pd.Series(dtype=bool)
    low_clean_pass_mask = (
        low_visible_mask
        & current_detail_df["queue_state"].map(normalize_text).eq("ai_cleared")
    ) if not current_detail_df.empty else pd.Series(dtype=bool)

    checks = [
        _row(
            observed_utc=observed,
            check="current_ui_rows",
            status="ok",
            value=len(current_df.index),
            notes="Rows currently shown in the AI Product Check Gate after current-only dedupe.",
            source_path=report_path,
        ),
        _row(
            observed_utc=observed,
            check="full_audit_rows",
            status="ok",
            value=len(history_df.index),
            notes="Rows retained in the full AI gate audit history.",
            source_path=report_path,
        ),
    ]

    history_duplicate_groups = _duplicate_group_count(history_df)
    current_duplicate_groups = _duplicate_group_count(current_df)
    current_missing_supplier_title = _blank_count(current_detail_df, "supplier_title")
    current_missing_amazon_title = _blank_count(current_detail_df, "amazon_title")
    current_missing_reason = _blank_count(current_detail_df, "codex_ai_reason", visible_mask)
    current_missing_evidence = _blank_count(current_detail_df, "codex_ai_evidence", visible_mask)
    current_invalid_actions = _invalid_action_count(current_detail_df)
    current_pending = int(current_detail_df["queue_state"].map(normalize_text).eq("pending_ai_check").sum()) if not current_detail_df.empty else 0
    current_waiting_queue = int(current_detail_df["queue_state"].map(normalize_text).eq("waiting_for_ai_queue").sum()) if not current_detail_df.empty else 0
    page_text_blank_mask = (
        current_detail_df["amazon_description_snippet"].map(normalize_text).eq("")
        if not current_detail_df.empty and "amazon_description_snippet" in current_detail_df.columns
        else pd.Series(dtype=bool)
    )
    page_text_warning_mask = (
        visible_mask & page_text_blank_mask & ~clear_match_mask
    ) if not current_detail_df.empty else pd.Series(dtype=bool)
    current_page_text_missing = int(page_text_warning_mask.sum()) if not current_detail_df.empty else 0
    current_hidden_page_text_missing = int((~visible_mask & page_text_blank_mask).sum()) if not current_detail_df.empty else 0
    commercial_signal_mask = _commercial_signal_mask(current_detail_df)
    profit_fallback_mask = _profit_fallback_mask(current_detail_df)
    current_roi_missing = int((visible_mask & ~commercial_signal_mask).sum()) if not current_detail_df.empty else 0
    current_visible_profit_fallback_rows = int((visible_mask & profit_fallback_mask).sum()) if not current_detail_df.empty else 0
    current_low_visible = int(low_visible_mask.sum()) if not current_detail_df.empty else 0
    current_low_clean_pass = int(low_clean_pass_mask.sum()) if not current_detail_df.empty else 0
    current_fallback_visible = int(fallback_visible_mask.sum()) if not current_detail_df.empty else 0
    queue_decision_proof = _active_queue_decision_proof(root_path)
    final_review_proof = _final_review_proof(root_path)
    active_queue_rows = int(queue_decision_proof["queue_rows"])
    active_decision_rows = int(queue_decision_proof["decision_rows"])
    active_queue_decision_balance_delta = abs(active_queue_rows - active_decision_rows)
    active_missing_decisions = int(queue_decision_proof["missing_decision_rows"])
    active_stale_decisions = int(queue_decision_proof["stale_decision_rows"])
    active_queue_missing_decision_ids = int(queue_decision_proof["queue_missing_decision_id_rows"])
    active_decision_missing_decision_ids = int(queue_decision_proof["decision_missing_decision_id_rows"])
    active_duplicate_decision_ids = int(queue_decision_proof["duplicate_decision_id_rows"])
    final_review_rows = int(final_review_proof["rows"])
    final_missing_ai_compare = int(final_review_proof["missing_ai_compare_note_rows"])

    checks.extend(
        [
            _row(
                observed_utc=observed,
                check="history_duplicate_product_groups",
                status="ok",
                value=history_duplicate_groups,
                notes="Historical duplicates are kept for audit, but only the latest product row should be current.",
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="current_duplicate_product_groups",
                status="fail" if current_duplicate_groups else "ok",
                value=current_duplicate_groups,
                notes="Current AI gate view must not show repeated copies of the same supplier SKU and ASIN.",
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="active_ai_queue_rows",
                status="ok",
                value=active_queue_rows,
                notes="Rows currently present in active AI queue files across review handoffs.",
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="active_ai_decision_rows",
                status="ok",
                value=active_decision_rows,
                notes="Rows currently present in active Codex AI decision files across review handoffs.",
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="active_queue_decision_row_balance_delta",
                status="fail" if active_queue_decision_balance_delta else "ok",
                value=active_queue_decision_balance_delta,
                notes="Active AI queue row count and active AI decision row count must match after the worker cycle.",
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="active_queue_missing_decision_id_rows",
                status="fail" if active_queue_missing_decision_ids else "ok",
                value=active_queue_missing_decision_ids,
                notes="Every active AI queue row must have an F032 decision ID so decisions can be matched safely.",
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="active_decision_missing_decision_id_rows",
                status="fail" if active_decision_missing_decision_ids else "ok",
                value=active_decision_missing_decision_ids,
                notes="Every active Codex AI decision row must have an F032 decision ID so stale rows can be detected.",
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="active_duplicate_decision_id_rows",
                status="fail" if active_duplicate_decision_ids else "ok",
                value=active_duplicate_decision_ids,
                notes="An active Codex AI decision file must not contain duplicate decisions for the same F032 row.",
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="active_queue_missing_decision_rows",
                status="fail" if active_missing_decisions else "ok",
                value=active_missing_decisions,
                notes=_notes_with_examples(
                    "Every active AI queue row must have a matching active Codex AI decision before reaching the final list.",
                    normalize_text(queue_decision_proof["missing_decision_examples"]),
                ),
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="active_stale_decision_rows",
                status="fail" if active_stale_decisions else "ok",
                value=active_stale_decisions,
                notes=_notes_with_examples(
                    "Active Codex AI decision files must not retain decisions for rows no longer present in the active queue.",
                    normalize_text(queue_decision_proof["stale_decision_examples"]),
                ),
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="current_missing_supplier_title_rows",
                status="fail" if current_missing_supplier_title else "ok",
                value=current_missing_supplier_title,
                notes="Supplier title is the primary identity evidence and must be present.",
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="current_missing_amazon_title_rows",
                status="fail" if current_missing_amazon_title else "ok",
                value=current_missing_amazon_title,
                notes="Amazon title is the primary comparison evidence and must be present.",
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="current_invalid_action_rows",
                status="fail" if current_invalid_actions else "ok",
                value=current_invalid_actions,
                notes="AI decisions must use only the approved gate actions.",
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="current_visible_low_confidence_rows",
                status="warn" if current_low_visible else "ok",
                value=current_low_visible,
                notes="Low confidence rows are allowed only when routed away from clean pass, usually to user guidance or rescan.",
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="current_clean_pass_low_confidence_rows",
                status="fail" if current_low_clean_pass else "ok",
                value=current_low_clean_pass,
                notes="Low confidence rows must not be visible as clean AI-cleared work.",
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="current_visible_missing_reason_rows",
                status="fail" if current_missing_reason else "ok",
                value=current_missing_reason,
                notes="Every row shown to the user must explain why the AI made that decision.",
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="current_visible_missing_evidence_rows",
                status="fail" if current_missing_evidence else "ok",
                value=current_missing_evidence,
                notes="Every row shown to the user must list the evidence used for the decision.",
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="current_visible_secondary_guard_rows",
                status="warn" if current_fallback_visible else "ok",
                value=current_fallback_visible,
                notes="Rows corrected by the built-in secondary-evidence guard should be re-reviewed by Codex when capacity allows.",
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="current_pending_ai_check_rows",
                status="warn" if current_pending else "ok",
                value=current_pending,
                notes="Pending rows are blocked from user review until Codex writes a decision.",
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="current_waiting_ai_queue_rows",
                status="warn" if current_waiting_queue else "ok",
                value=current_waiting_queue,
                notes="Waiting rows need an AI queue file before Codex can decide them.",
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="current_missing_page_text_rows",
                status="warn" if current_page_text_missing else "ok",
                value=current_page_text_missing,
                notes=_notes_with_examples(
                    "Operator-visible rows should carry page text when it was captured, but titles can still be enough for some decisions.",
                    _row_examples(
                        current_detail_df[page_text_warning_mask].copy()
                        if not current_detail_df.empty and "amazon_description_snippet" in current_detail_df.columns
                        else pd.DataFrame(),
                        ["supplier_id", "run_id", "supplier_sku", "asin"],
                    ),
                ),
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="current_hidden_missing_page_text_rows",
                status="ok",
                value=current_hidden_page_text_missing,
                notes="Hidden or rejected rows do not need page text before the operator final list.",
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="current_missing_roi_rows",
                status="warn" if current_roi_missing else "ok",
                value=current_roi_missing,
                notes=_notes_with_examples(
                    "Operator-visible rows should have either ROI percentage or a profit fallback signal for suspicion checks.",
                    _row_examples(
                        current_detail_df[visible_mask & ~commercial_signal_mask].copy()
                        if not current_detail_df.empty
                        else pd.DataFrame(),
                        ["supplier_id", "run_id", "supplier_sku", "asin"],
                    ),
                ),
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="current_visible_profit_fallback_rows",
                status="ok",
                value=current_visible_profit_fallback_rows,
                notes="Operator-visible rows where ROI percent is missing but profit evidence is still present.",
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="final_review_rows",
                status="ok",
                value=final_review_rows,
                notes="Rows currently loaded by the New Product Review source loaders.",
                source_path=report_path,
            ),
            _row(
                observed_utc=observed,
                check="final_review_missing_ai_compare_note_rows",
                status="fail" if final_missing_ai_compare else "ok",
                value=final_missing_ai_compare,
                notes=_notes_with_examples(
                    "Every final review row must carry AI match confidence and AI compare text inside What to watch.",
                    normalize_text(final_review_proof["missing_ai_compare_examples"]),
                ),
                source_path=report_path,
            ),
        ]
    )

    health = write_csv(report_path, pd.DataFrame(checks), MANAGER_HEALTH_COLUMNS)
    _write_summary(summary_path, observed_utc=observed, health=health, current_rows=len(current_df.index), history_rows=len(history_df.index))
    fail_rows = int(health["status"].eq("fail").sum()) if not health.empty else 0
    warn_rows = int(health["status"].eq("warn").sum()) if not health.empty else 0
    return {
        "status": "fail" if fail_rows else ("warn" if warn_rows else "ok"),
        "observed_utc": observed,
        "current_rows": int(len(current_df.index)),
        "history_rows": int(len(history_df.index)),
        "fail_checks": fail_rows,
        "warn_checks": warn_rows,
        "report_path": str(report_path),
        "summary_path": str(summary_path),
        "history_duplicate_product_groups": history_duplicate_groups,
        "current_visible_secondary_guard_rows": current_fallback_visible,
        "current_pending_ai_check_rows": current_pending,
        "active_ai_queue_rows": active_queue_rows,
        "active_ai_decision_rows": active_decision_rows,
        "active_queue_decision_row_balance_delta": active_queue_decision_balance_delta,
        "active_queue_missing_decision_rows": active_missing_decisions,
        "active_stale_decision_rows": active_stale_decisions,
        "final_review_rows": final_review_rows,
        "final_review_missing_ai_compare_note_rows": final_missing_ai_compare,
        "current_missing_supplier_title_rows": current_missing_supplier_title,
        "current_missing_amazon_title_rows": current_missing_amazon_title,
        "current_missing_page_text_rows": current_page_text_missing,
        "current_hidden_missing_page_text_rows": current_hidden_page_text_missing,
        "current_missing_roi_rows": current_roi_missing,
        "current_visible_profit_fallback_rows": current_visible_profit_fallback_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the F AI gate quality report.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--observed-utc", default=None)
    args = parser.parse_args()
    root = Path(args.root) if args.root else None
    summary = build_ai_gate_quality_report(root=root, observed_utc=args.observed_utc)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if summary["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
