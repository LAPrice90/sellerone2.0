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

from scripts.flows.F._review_intelligence import build_review_intelligence_cycle
from scripts.flows.F.price_list_manager.FPM156_build_ai_gate_quality_report import build_ai_gate_quality_report
from scripts.flows.F.price_list_manager.FPM158_ai_precheck_common import (
    PRECHECK_STATUS_COLUMNS,
    ai_precheck_dir,
    load_precheck_registry,
    queue_evidence_hash,
    read_any_csv as read_precheck_csv,
    write_csv as write_precheck_csv,
)
from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import get_manager_paths
from scripts.flows.F.price_list_manager._schemas import (
    MANAGER_HEALTH_COLUMNS,
    REVIEW_CANDIDATE_MANIFEST_COLUMNS,
    REVIEW_HANDOFF_MANIFEST_COLUMNS,
)

AI_GATE_VERSION = "F032_review_intelligence_v1"
CODEX_AI_DECISION_COLUMNS = [
    "f032_decision_id",
    "codex_ai_action",
    "codex_ai_decision_bucket",
    "codex_ai_fail_category",
    "codex_ai_confidence",
    "codex_ai_needs_user_guidance",
    "codex_ai_rescan_needed",
    "codex_ai_reason",
    "codex_ai_evidence",
    "codex_ai_reviewed_utc",
    "codex_ai_reviewer",
]
STALE_CODEX_AI_DECISION_ARCHIVE_COLUMNS = [
    *CODEX_AI_DECISION_COLUMNS,
    "archived_utc",
    "archive_reason",
    "archived_from_path",
    "active_ai_queue_path",
    "active_queue_rows",
]
AI_REVIEW_QUEUE_COLUMNS = [
    "observed_utc",
    "f032_decision_id",
    "source_review_pack_type",
    "active_supplier_id",
    "active_run_id",
    "review_batch_id",
    "candidate_id",
    "supplier_sku",
    "asin",
    "supplier_title",
    "amazon_title",
    "amazon_product_detail_text",
    "amazon_product_description",
    "amazon_feature_bullets",
    "supplier_brand",
    "amazon_brand",
    "supplier_unit_cost_gbp",
    "amazon_sell_price_gbp",
    "expected_profit_gbp",
    "profit_per_unit_gbp",
    "profit_on_cost_pct",
    "review_priority_score",
    "main_rank",
    "expected_units_next_30d",
    "sales_lower_30d",
    "sales_upper_30d",
    "title_match_action",
    "title_match_decision_bucket",
    "title_match_reason_code",
    "title_match_confidence",
    "title_match_evidence",
    "seller_history_code",
    "seller_history_recommended_action",
    "demand_conflict_code",
    "demand_recommended_action",
    "history_risk_code",
    "history_recommended_action",
    "uk_review_code",
    "uk_review_recommended_action",
    "profit_formula_code",
    "profit_recommended_action",
    "f032_rule_action",
    "f032_rule_bucket",
    "f032_rule_fail_category",
    "f032_rule_confidence",
    "f032_rule_reason",
    "f032_rule_evidence",
    "codex_ai_action",
    "codex_ai_decision_bucket",
    "codex_ai_fail_category",
    "codex_ai_confidence",
    "codex_ai_reason",
    "codex_ai_evidence",
]
VALID_CODEX_AI_ACTIONS = {
    "allow_if_other_checks_pass",
    "manual_review",
    "rescan_needed",
    "remove_from_clean_pass",
}
AMAZON_PAGE_TEXT_QUEUE_COLUMNS = [
    "amazon_product_detail_text",
    "amazon_product_description",
    "amazon_feature_bullets",
]
CURRENT_SCANNER_FAIL_EVIDENCE_COLUMNS = [
    "observed_utc",
    "batch_id",
    "backfill_id",
    "backfill_status",
    "supplier_id",
    "active_run_id",
    "review_batch_id",
    "candidate_id",
    "supplier_sku",
    "asin",
    "resolved_asin",
    "barcode",
    "supplier_title",
    "amazon_title",
    "scanner_fail_reason",
    "scrape_error",
    "scrape_attempted",
    "scrape_success",
    "page_evidence_captured_flag",
    "proof_root",
    "state_path",
    "evidence_source_path",
]
CURRENT_SCANNER_FAIL_STATUSES = {"skipped_current_scanner_fail"}
CURRENT_SCANNER_RESCAN_STATUSES = {"needs_asin_recheck"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _handoff_dir(root: Path, *, supplier_id: str, run_id: str) -> Path:
    paths = get_manager_paths(root=root)
    safe_supplier = normalize_text(supplier_id).replace("/", "_").replace("\\", "_") or "unknown_supplier"
    safe_run = normalize_text(run_id).replace("/", "_").replace("\\", "_") or "unknown_run"
    return paths.system_dir / "review_handoffs" / safe_supplier / safe_run


def _read_any_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _int_value(value: object) -> int:
    raw = normalize_text(value)
    if raw == "":
        return 0
    try:
        return int(float(raw))
    except ValueError:
        return 0


def _load_current_scanner_fail_evidence(root: Path) -> pd.DataFrame:
    path = root / "out" / "systems" / "F" / "page_evidence_backfill" / "current_scanner_fail_evidence.csv"
    df = _read_any_csv(path)
    if df.empty:
        return pd.DataFrame(columns=CURRENT_SCANNER_FAIL_EVIDENCE_COLUMNS)
    for column in CURRENT_SCANNER_FAIL_EVIDENCE_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    work = df[CURRENT_SCANNER_FAIL_EVIDENCE_COLUMNS].copy().fillna("")
    work = work.loc[
        work["backfill_status"].map(normalize_text).isin(
            CURRENT_SCANNER_FAIL_STATUSES | CURRENT_SCANNER_RESCAN_STATUSES
        )
    ].copy()
    if work.empty:
        return pd.DataFrame(columns=CURRENT_SCANNER_FAIL_EVIDENCE_COLUMNS)
    work["_observed_ts"] = pd.to_datetime(work["observed_utc"], errors="coerce", utc=True, format="mixed")
    work = work.sort_values("_observed_ts", ascending=False, kind="stable")
    return work.drop(columns=["_observed_ts"])


def _current_scanner_fail_lookup(evidence_df: pd.DataFrame, selected_run_id: str) -> dict[tuple[str, str, str], dict[str, str]]:
    out: dict[tuple[str, str, str], dict[str, str]] = {}
    if evidence_df.empty:
        return out
    selected_run = normalize_text(selected_run_id)
    for _, row in evidence_df.fillna("").iterrows():
        record = {column: normalize_text(value) for column, value in row.to_dict().items()}
        active_run = normalize_text(record.get("active_run_id", ""))
        if selected_run and active_run != selected_run:
            continue
        candidate_id = normalize_text(record.get("candidate_id", ""))
        supplier_sku = normalize_text(record.get("supplier_sku", "")).upper()
        asin = normalize_text(record.get("asin", "")).upper()
        resolved_asin = normalize_text(record.get("resolved_asin", "")).upper()
        if candidate_id:
            out.setdefault(("candidate_id", active_run, candidate_id), record)
        if supplier_sku and asin:
            out.setdefault(("sku_asin", active_run, f"{supplier_sku}|{asin}"), record)
        if supplier_sku and resolved_asin and resolved_asin != asin:
            out.setdefault(("sku_asin", active_run, f"{supplier_sku}|{resolved_asin}"), record)
    return out


def _scanner_fail_for_queue_row(
    row: dict[str, str],
    lookup: dict[tuple[str, str, str], dict[str, str]],
) -> dict[str, str]:
    if not lookup:
        return {}
    active_run = normalize_text(row.get("active_run_id", ""))
    candidate_id = normalize_text(row.get("candidate_id", ""))
    supplier_sku = normalize_text(row.get("supplier_sku", "")).upper()
    asin = normalize_text(row.get("asin", "")).upper()
    if candidate_id:
        found = lookup.get(("candidate_id", active_run, candidate_id))
        if found:
            return found
    if supplier_sku and asin:
        return lookup.get(("sku_asin", active_run, f"{supplier_sku}|{asin}"), {})
    return {}


def _current_scanner_fail_decision(
    *,
    decision_id: str,
    queue_record: dict[str, str],
    scanner_fail: dict[str, str],
    observed_utc: str,
) -> dict[str, str]:
    status = normalize_text(scanner_fail.get("backfill_status", ""))
    reason = normalize_text(scanner_fail.get("scanner_fail_reason", "")) or normalize_text(scanner_fail.get("scrape_error", ""))
    supplier_title = normalize_text(queue_record.get("supplier_title", "")) or normalize_text(scanner_fail.get("supplier_title", ""))
    amazon_title = normalize_text(queue_record.get("amazon_title", "")) or normalize_text(scanner_fail.get("amazon_title", ""))
    supplier_sku = normalize_text(queue_record.get("supplier_sku", "")) or normalize_text(scanner_fail.get("supplier_sku", ""))
    asin = normalize_text(queue_record.get("asin", "")) or normalize_text(scanner_fail.get("asin", ""))
    if status in CURRENT_SCANNER_RESCAN_STATUSES:
        action = "rescan_needed"
        bucket = "current_scanner_needs_rescan"
        fail_category = "current_scanner_needs_asin_recheck"
        needs_user = "0"
        needs_rescan = "1"
        human_reason = (
            "The current scanner could not confirm the ASIN for this row, so it must go back through scanner "
            "recheck before it can be shown to the user."
        )
    else:
        action = "remove_from_clean_pass"
        bucket = "current_scanner_fail"
        fail_category = "current_scanner_fail"
        needs_user = "0"
        needs_rescan = "0"
        human_reason = (
            "The current scanner rechecked this row and failed it before page evidence was captured, so it must "
            "not be shown as a clean AI pass."
        )
    return {
        "f032_decision_id": decision_id,
        "codex_ai_action": action,
        "codex_ai_decision_bucket": bucket,
        "codex_ai_fail_category": fail_category,
        "codex_ai_confidence": "high",
        "codex_ai_needs_user_guidance": needs_user,
        "codex_ai_rescan_needed": needs_rescan,
        "codex_ai_reason": f"{human_reason} Scanner reason: {reason or status}.",
        "codex_ai_evidence": (
            f"current_scanner_fail_status={status} | "
            f"scanner_reason={reason} | "
            f"supplier_sku={supplier_sku} | "
            f"asin={asin} | "
            f"supplier_title={supplier_title} | "
            f"amazon_title={amazon_title} | "
            f"proof_root={normalize_text(scanner_fail.get('proof_root', ''))}"
        ),
        "codex_ai_reviewed_utc": observed_utc,
        "codex_ai_reviewer": "fpm155_current_scanner_fail_guard",
    }


def _resolve_path(root: Path, raw_path: object) -> Path:
    text = normalize_text(raw_path)
    if text == "":
        return Path()
    path = Path(text)
    if path.is_absolute():
        return path
    return root / path


def _join_key(row: pd.Series | dict[str, object]) -> tuple[str, str, str, str]:
    return (
        normalize_text(row.get("source_review_pack_type", "")),
        normalize_text(row.get("candidate_id", "")).upper(),
        normalize_text(row.get("supplier_sku", "")).upper(),
        normalize_text(row.get("asin", "")).upper(),
    )


def _decision_lookup(decision_df: pd.DataFrame) -> dict[tuple[str, str, str, str], dict[str, str]]:
    out: dict[tuple[str, str, str, str], dict[str, str]] = {}
    if decision_df.empty:
        return out
    for _, row in decision_df.fillna("").iterrows():
        record = {column: normalize_text(value) for column, value in row.to_dict().items()}
        key = _join_key(record)
        out[key] = record
        pack, candidate, supplier_sku, asin = key
        if candidate:
            out.setdefault((pack, candidate, "", ""), record)
        if supplier_sku and asin:
            out.setdefault((pack, "", supplier_sku, asin), record)
    return out


def _with_f032_decisions(raw_df: pd.DataFrame, decision_df: pd.DataFrame, pack_type: str) -> pd.DataFrame:
    if raw_df.empty:
        return raw_df.copy()
    lookup = _decision_lookup(decision_df)
    rows: list[dict[str, str]] = []
    for _, row in raw_df.fillna("").iterrows():
        record = {column: normalize_text(value) for column, value in row.to_dict().items()}
        decision_key = (
            pack_type,
            normalize_text(record.get("candidate_id", "")).upper(),
            normalize_text(record.get("supplier_sku", "")).upper(),
            normalize_text(record.get("asin", "")).upper(),
        )
        decision = (
            lookup.get(decision_key)
            or lookup.get((pack_type, decision_key[1], "", ""))
            or lookup.get((pack_type, "", decision_key[2], decision_key[3]))
            or {}
        )
        for field in [
            "f032_decision_id",
            "f032_action",
            "f032_decision_bucket",
            "f032_fail_category",
            "f032_confidence",
            "f032_needs_user_guidance",
            "f032_rescan_needed",
            "f032_rule_tightening_candidate",
            "f032_reason",
            "f032_evidence",
        ]:
            record[field] = normalize_text(decision.get(field, ""))
        if not normalize_text(record.get("supplier_title", "")):
            record["supplier_title"] = normalize_text(decision.get("supplier_title", ""))
        if not normalize_text(record.get("amazon_title", "")):
            record["amazon_title"] = normalize_text(decision.get("amazon_title", ""))
        record["f032_source_review_pack_type"] = pack_type
        if record["f032_action"] == "manual_review":
            record["near_miss_type"] = normalize_text(record.get("near_miss_type", "")) or "f032_manual_review"
            record["identity_recommended_action"] = "manual_review"
            if not normalize_text(record.get("recovery_hint", "")):
                record["recovery_hint"] = record["f032_reason"]
            if not normalize_text(record.get("watch_data_summary", "")):
                record["watch_data_summary"] = record["f032_reason"]
        rows.append(record)
    return pd.DataFrame(rows).fillna("")


def _write_raw_output(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.fillna("").to_csv(path, index=False)


def _finalize_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = ""
    out = out[columns]
    for column in columns:
        out[column] = out[column].map(normalize_text)
    return out


def _evidence_lookup(evidence_df: pd.DataFrame) -> dict[tuple[str, str, str, str], dict[str, str]]:
    out: dict[tuple[str, str, str, str], dict[str, str]] = {}
    if evidence_df.empty:
        return out
    for _, row in evidence_df.fillna("").iterrows():
        record = {column: normalize_text(value) for column, value in row.to_dict().items()}
        out[_join_key(record)] = record
    return out


def _build_ai_review_queue(evidence_df: pd.DataFrame, decision_df: pd.DataFrame) -> pd.DataFrame:
    evidence_by_key = _evidence_lookup(evidence_df)
    rows: list[dict[str, str]] = []
    for _, decision_row in decision_df.fillna("").iterrows():
        decision = {column: normalize_text(value) for column, value in decision_row.to_dict().items()}
        evidence = evidence_by_key.get(_join_key(decision), {})
        row = {column: normalize_text(evidence.get(column, "")) for column in AI_REVIEW_QUEUE_COLUMNS}
        for column in [
            "observed_utc",
            "f032_decision_id",
            "source_review_pack_type",
            "active_supplier_id",
            "active_run_id",
            "review_batch_id",
            "candidate_id",
            "supplier_sku",
            "asin",
            "supplier_title",
            "amazon_title",
        ]:
            row[column] = normalize_text(decision.get(column, row.get(column, "")))
        row["f032_rule_action"] = normalize_text(decision.get("f032_action", ""))
        row["f032_rule_bucket"] = normalize_text(decision.get("f032_decision_bucket", ""))
        row["f032_rule_fail_category"] = normalize_text(decision.get("f032_fail_category", ""))
        row["f032_rule_confidence"] = normalize_text(decision.get("f032_confidence", ""))
        row["f032_rule_reason"] = normalize_text(decision.get("f032_reason", ""))
        row["f032_rule_evidence"] = normalize_text(decision.get("f032_evidence", ""))
        rows.append(row)
    return _finalize_columns(pd.DataFrame(rows), AI_REVIEW_QUEUE_COLUMNS)


def _write_decision_template(path: Path, queue_df: pd.DataFrame) -> None:
    if path.exists():
        return
    rows = []
    for _, row in queue_df.fillna("").iterrows():
        rows.append(
            {
                "f032_decision_id": normalize_text(row.get("f032_decision_id", "")),
                "codex_ai_action": "",
                "codex_ai_decision_bucket": "",
                "codex_ai_fail_category": "",
                "codex_ai_confidence": "",
                "codex_ai_needs_user_guidance": "",
                "codex_ai_rescan_needed": "",
                "codex_ai_reason": "",
                "codex_ai_evidence": "",
                "codex_ai_reviewed_utc": "",
                "codex_ai_reviewer": "",
            }
        )
    _write_raw_output(path, _finalize_columns(pd.DataFrame(rows), CODEX_AI_DECISION_COLUMNS))


def _load_codex_decisions(path: Path) -> pd.DataFrame:
    return _finalize_columns(_read_any_csv(path), CODEX_AI_DECISION_COLUMNS)


def _archive_stale_codex_decisions(
    *,
    codex_decision_path: Path,
    ai_queue_path: Path,
    queue_df: pd.DataFrame,
    codex_df: pd.DataFrame,
    observed_utc: str,
) -> tuple[pd.DataFrame, int, Path]:
    archive_path = codex_decision_path.with_name("codex_ai_review_decisions_stale_archive.csv")
    if codex_df.empty:
        return codex_df, 0, archive_path
    active_ids = {
        normalize_text(value)
        for value in queue_df.get("f032_decision_id", pd.Series(dtype=str)).tolist()
        if normalize_text(value)
    }
    active_rows: list[dict[str, str]] = []
    stale_rows: list[dict[str, str]] = []
    for _, row in codex_df.fillna("").iterrows():
        record = {column: normalize_text(row.get(column, "")) for column in CODEX_AI_DECISION_COLUMNS}
        decision_id = normalize_text(record.get("f032_decision_id", ""))
        if decision_id and decision_id in active_ids:
            active_rows.append(record)
        else:
            stale = dict(record)
            stale["archived_utc"] = observed_utc
            stale["archive_reason"] = "decision_not_in_current_ai_queue"
            stale["archived_from_path"] = str(codex_decision_path)
            stale["active_ai_queue_path"] = str(ai_queue_path)
            stale["active_queue_rows"] = str(len(queue_df.index))
            stale_rows.append(stale)

    active_df = _finalize_columns(pd.DataFrame(active_rows), CODEX_AI_DECISION_COLUMNS)
    if not stale_rows:
        return active_df, 0, archive_path

    existing_archive = _read_any_csv(archive_path)
    archive_df = pd.concat(
        [
            existing_archive,
            pd.DataFrame(stale_rows, columns=STALE_CODEX_AI_DECISION_ARCHIVE_COLUMNS),
        ],
        ignore_index=True,
    ).fillna("")
    for column in STALE_CODEX_AI_DECISION_ARCHIVE_COLUMNS:
        if column not in archive_df.columns:
            archive_df[column] = ""
    archive_df = archive_df[STALE_CODEX_AI_DECISION_ARCHIVE_COLUMNS]
    archive_df["_dedupe_key"] = archive_df.apply(
        lambda row: "|".join(
            [
                normalize_text(row.get("f032_decision_id", "")),
                normalize_text(row.get("codex_ai_action", "")),
                normalize_text(row.get("codex_ai_reviewed_utc", "")),
                normalize_text(row.get("archive_reason", "")),
            ]
        ),
        axis=1,
    )
    archive_df = archive_df.drop_duplicates("_dedupe_key", keep="last").drop(columns=["_dedupe_key"])
    _write_raw_output(archive_path, _finalize_columns(archive_df, STALE_CODEX_AI_DECISION_ARCHIVE_COLUMNS))
    return active_df, len(stale_rows), archive_path


def _codex_decision_lookup(decision_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    if decision_df.empty:
        return out
    for _, row in decision_df.fillna("").iterrows():
        record = {column: normalize_text(value) for column, value in row.to_dict().items()}
        decision_id = normalize_text(record.get("f032_decision_id", ""))
        if decision_id:
            out[decision_id] = record
    return out


def _codex_decision_gaps(queue_df: pd.DataFrame, codex_df: pd.DataFrame) -> tuple[int, int, int]:
    lookup = _codex_decision_lookup(codex_df)
    missing = 0
    invalid = 0
    missing_reason = 0
    for _, row in queue_df.fillna("").iterrows():
        decision_id = normalize_text(row.get("f032_decision_id", ""))
        decision = lookup.get(decision_id, {})
        action = normalize_text(decision.get("codex_ai_action", ""))
        reason = normalize_text(decision.get("codex_ai_reason", ""))
        if not decision or not action:
            missing += 1
            continue
        if action not in VALID_CODEX_AI_ACTIONS:
            invalid += 1
        if not reason:
            missing_reason += 1
    return missing, invalid, missing_reason


def _missing_columns(df: pd.DataFrame, columns: list[str]) -> list[str]:
    return [column for column in columns if column not in df.columns]


def _should_defer_missing_page_rescan_to_f032(record: dict[str, str], codex: dict[str, str]) -> bool:
    rule_action = normalize_text(record.get("f032_action", "")) or normalize_text(record.get("f032_rule_action", ""))
    rule_fail_category = normalize_text(record.get("f032_fail_category", "")) or normalize_text(
        record.get("f032_rule_fail_category", "")
    )
    codex_action = normalize_text(codex.get("codex_ai_action", ""))
    codex_fail_category = normalize_text(codex.get("codex_ai_fail_category", ""))
    codex_reviewer = normalize_text(codex.get("codex_ai_reviewer", ""))
    codex_evidence = normalize_text(codex.get("codex_ai_evidence", ""))
    if not rule_action:
        return False
    if codex_reviewer == "fpm155_secondary_evidence_guard" and "stale_missing_page_rescan_deferred_to_f032" in codex_evidence:
        return True
    if codex_action != "rescan_needed":
        return False
    if codex_fail_category != "missing_page_evidence":
        return False
    if rule_action == "rescan_needed" and rule_fail_category in {"", "missing_evidence_rescan_needed", "missing_page_evidence"}:
        return False
    return True


def _secondary_evidence_reason(
    *,
    rule_action: str,
    rule_fail_category: str,
    rule_reason: str,
    supplier_title: str,
    amazon_title: str,
) -> str:
    title_note = ""
    if supplier_title and amazon_title:
        title_note = f" Supplier title: {supplier_title}. Amazon title: {amazon_title}."
    reason_note = f" F032 reason: {rule_reason}." if rule_reason else ""
    if rule_action == "allow_if_other_checks_pass":
        return (
            "Titles carry enough evidence for this row; product description/page text is secondary evidence, "
            "so the old missing-page rescan was not allowed to block a clear title match."
            f"{title_note}{reason_note}"
        )
    if rule_action == "manual_review":
        category = rule_fail_category.replace("_", " ") or "title evidence"
        return (
            f"Needs user guidance because the title evidence points to {category}; product description/page text "
            "can help, but it is not the only valid evidence source."
            f"{title_note}{reason_note}"
        )
    if rule_action == "remove_from_clean_pass":
        category = rule_fail_category.replace("_", " ") or "clear title breach"
        return (
            f"Removed from clean pass because the title evidence points to {category}; missing page text is "
            "secondary and must not rescue a bad match."
            f"{title_note}{reason_note}"
        )
    if rule_action == "rescan_needed":
        category = rule_fail_category.replace("_", " ") or "missing core evidence"
        return (
            f"Rescan needed because the current evidence still points to {category}; page text remains useful "
            "supporting evidence for this row."
            f"{title_note}{reason_note}"
        )
    return (
        "Product description/page text is secondary evidence here, and the stale missing-page decision was "
        "replaced by the current F032 decision."
        f"{title_note}{reason_note}"
    )


def _effective_codex_decision(record: dict[str, str], codex: dict[str, str]) -> dict[str, str]:
    if not _should_defer_missing_page_rescan_to_f032(record, codex):
        return codex

    rule_action = normalize_text(record.get("f032_action", "")) or normalize_text(record.get("f032_rule_action", ""))
    rule_bucket = normalize_text(record.get("f032_decision_bucket", "")) or normalize_text(record.get("f032_rule_bucket", ""))
    rule_confidence = normalize_text(record.get("f032_confidence", "")) or normalize_text(record.get("f032_rule_confidence", ""))
    rule_reason = normalize_text(record.get("f032_reason", "")) or normalize_text(record.get("f032_rule_reason", ""))
    rule_fail_category = normalize_text(record.get("f032_fail_category", "")) or normalize_text(
        record.get("f032_rule_fail_category", "")
    )
    supplier_title = normalize_text(record.get("supplier_title", "")) or normalize_text(record.get("title", ""))
    amazon_title = normalize_text(record.get("amazon_title", ""))
    effective = dict(codex)
    effective["codex_ai_action"] = rule_action
    effective["codex_ai_decision_bucket"] = rule_bucket or ("ai_review_clear" if rule_action == "allow_if_other_checks_pass" else rule_action)
    effective["codex_ai_fail_category"] = "" if rule_action == "allow_if_other_checks_pass" else rule_fail_category
    effective["codex_ai_confidence"] = rule_confidence or "medium"
    effective["codex_ai_needs_user_guidance"] = "1" if rule_action == "manual_review" else "0"
    effective["codex_ai_rescan_needed"] = "1" if rule_action == "rescan_needed" else "0"
    effective["codex_ai_reason"] = _secondary_evidence_reason(
        rule_action=rule_action,
        rule_fail_category=rule_fail_category,
        rule_reason=rule_reason,
        supplier_title=supplier_title,
        amazon_title=amazon_title,
    )
    effective["codex_ai_evidence"] = (
        f"stale_missing_page_rescan_deferred_to_f032 | "
        f"f032_rule_action={rule_action} | "
        f"f032_rule_fail_category={rule_fail_category} | "
        f"supplier_title={supplier_title} | "
        f"amazon_title={amazon_title} | "
        f"f032_rule_reason={rule_reason}"
    )
    return effective


def _normalize_codex_secondary_evidence_decisions(
    queue_df: pd.DataFrame,
    codex_df: pd.DataFrame,
    observed_utc: str,
) -> tuple[pd.DataFrame, int]:
    if queue_df.empty or codex_df.empty:
        return codex_df, 0
    queue_lookup: dict[str, dict[str, str]] = {}
    for _, queue_row in queue_df.fillna("").iterrows():
        queue_record = {column: normalize_text(value) for column, value in queue_row.to_dict().items()}
        decision_id = normalize_text(queue_record.get("f032_decision_id", ""))
        if decision_id:
            queue_lookup[decision_id] = queue_record

    changed = 0
    rows: list[dict[str, str]] = []
    for _, codex_row in codex_df.fillna("").iterrows():
        codex_record = {column: normalize_text(value) for column, value in codex_row.to_dict().items()}
        decision_id = normalize_text(codex_record.get("f032_decision_id", ""))
        queue_record = queue_lookup.get(decision_id, {})
        effective = _effective_codex_decision(queue_record, codex_record) if queue_record else codex_record
        if effective != codex_record:
            changed += 1
            effective["codex_ai_reviewed_utc"] = observed_utc
            effective["codex_ai_reviewer"] = "fpm155_secondary_evidence_guard"
        rows.append(effective)
    return _finalize_columns(pd.DataFrame(rows), CODEX_AI_DECISION_COLUMNS), changed


def _normalize_codex_current_scanner_fail_decisions(
    queue_df: pd.DataFrame,
    codex_df: pd.DataFrame,
    observed_utc: str,
    scanner_fail_lookup: dict[tuple[str, str, str], dict[str, str]],
) -> tuple[pd.DataFrame, int, int]:
    if queue_df.empty or not scanner_fail_lookup:
        return codex_df, 0, 0
    existing_by_id = _codex_decision_lookup(codex_df)
    rows_by_id: dict[str, dict[str, str]] = {
        decision_id: dict(record) for decision_id, record in existing_by_id.items()
    }
    changed = 0
    guarded = 0
    for _, queue_row in queue_df.fillna("").iterrows():
        queue_record = {column: normalize_text(value) for column, value in queue_row.to_dict().items()}
        decision_id = normalize_text(queue_record.get("f032_decision_id", ""))
        if not decision_id:
            continue
        scanner_fail = _scanner_fail_for_queue_row(queue_record, scanner_fail_lookup)
        if not scanner_fail:
            continue
        guarded += 1
        replacement = _current_scanner_fail_decision(
            decision_id=decision_id,
            queue_record=queue_record,
            scanner_fail=scanner_fail,
            observed_utc=observed_utc,
        )
        if rows_by_id.get(decision_id, {}) != replacement:
            changed += 1
        rows_by_id[decision_id] = replacement

    if not rows_by_id:
        return codex_df, changed, guarded
    ordered_rows: list[dict[str, str]] = []
    used_ids: set[str] = set()
    for _, queue_row in queue_df.fillna("").iterrows():
        decision_id = normalize_text(queue_row.get("f032_decision_id", ""))
        if decision_id and decision_id in rows_by_id:
            ordered_rows.append(rows_by_id[decision_id])
            used_ids.add(decision_id)
    for decision_id, row in rows_by_id.items():
        if decision_id not in used_ids:
            ordered_rows.append(row)
    return _finalize_columns(pd.DataFrame(ordered_rows), CODEX_AI_DECISION_COLUMNS), changed, guarded


def _merge_matching_precheck_decisions(
    *,
    root: Path,
    supplier_id: str,
    run_id: str,
    queue_df: pd.DataFrame,
    codex_df: pd.DataFrame,
    observed_utc: str,
) -> tuple[pd.DataFrame, int, int]:
    precheck_dir = ai_precheck_dir(root, supplier_id=supplier_id, run_id=run_id)
    precheck_decision_path = precheck_dir / "codex_ai_review_decisions.csv"
    if queue_df.empty or not precheck_decision_path.exists():
        return codex_df, 0, 0

    registry = load_precheck_registry(precheck_dir)
    if registry.empty:
        return codex_df, 0, 0

    current_hash_by_id: dict[str, str] = {}
    for _, row in queue_df.fillna("").iterrows():
        record = {column: normalize_text(value) for column, value in row.to_dict().items()}
        decision_id = normalize_text(record.get("f032_decision_id", ""))
        if decision_id:
            current_hash_by_id[decision_id] = queue_evidence_hash(record)

    registry_hash_by_id = {
        normalize_text(row.get("f032_decision_id", "")): normalize_text(row.get("evidence_hash", ""))
        for row in registry.fillna("").to_dict("records")
        if normalize_text(row.get("f032_decision_id", ""))
    }
    precheck_decisions = _load_codex_decisions(precheck_decision_path)
    precheck_by_id = _codex_decision_lookup(precheck_decisions)
    final_by_id = _codex_decision_lookup(codex_df)
    ordered_rows: list[dict[str, str]] = []
    reused = 0
    stale = 0
    used_ids: set[str] = set()

    for _, queue_row in queue_df.fillna("").iterrows():
        decision_id = normalize_text(queue_row.get("f032_decision_id", ""))
        existing = final_by_id.get(decision_id, {})
        if normalize_text(existing.get("codex_ai_action", "")):
            ordered_rows.append(existing)
            used_ids.add(decision_id)
            continue

        precheck = precheck_by_id.get(decision_id, {})
        action = normalize_text(precheck.get("codex_ai_action", ""))
        reason = normalize_text(precheck.get("codex_ai_reason", ""))
        current_hash = current_hash_by_id.get(decision_id, "")
        precheck_hash = registry_hash_by_id.get(decision_id, "")
        if not precheck or not action:
            if existing:
                ordered_rows.append(existing)
                used_ids.add(decision_id)
            continue
        if action not in VALID_CODEX_AI_ACTIONS or not reason or not current_hash or current_hash != precheck_hash:
            stale += 1
            if existing:
                ordered_rows.append(existing)
                used_ids.add(decision_id)
            continue
        reused_record = {column: normalize_text(precheck.get(column, "")) for column in CODEX_AI_DECISION_COLUMNS}
        ordered_rows.append(reused_record)
        used_ids.add(decision_id)
        reused += 1

    for decision_id, record in final_by_id.items():
        if decision_id and decision_id not in used_ids:
            ordered_rows.append(record)

    status_path = precheck_dir / "ai_precheck_status.csv"
    status_df = read_precheck_csv(status_path)
    if not status_df.empty:
        status_df = status_df.copy()
        status_df.loc[status_df.index[-1], "reused_in_final_rows"] = str(reused)
        status_df.loc[status_df.index[-1], "stale_decision_rows"] = str(
            _int_value(status_df.iloc[-1].get("stale_decision_rows", "0")) + stale
        )
        write_precheck_csv(status_path, status_df, PRECHECK_STATUS_COLUMNS)

    return _finalize_columns(pd.DataFrame(ordered_rows), CODEX_AI_DECISION_COLUMNS), reused, stale


def _apply_codex_decisions_to_review_rows(raw_df: pd.DataFrame, decision_df: pd.DataFrame, pack_type: str, codex_df: pd.DataFrame) -> pd.DataFrame:
    work = _with_f032_decisions(raw_df, decision_df, pack_type)
    if work.empty:
        return work
    codex_lookup = _codex_decision_lookup(codex_df)
    rows: list[dict[str, str]] = []
    for _, row in work.fillna("").iterrows():
        record = {column: normalize_text(value) for column, value in row.to_dict().items()}
        decision_id = normalize_text(record.get("f032_decision_id", ""))
        codex = codex_lookup.get(decision_id, {})
        rule_action = normalize_text(record.get("f032_action", ""))
        rule_bucket = normalize_text(record.get("f032_decision_bucket", ""))
        rule_fail_category = normalize_text(record.get("f032_fail_category", ""))
        rule_confidence = normalize_text(record.get("f032_confidence", ""))
        rule_reason = normalize_text(record.get("f032_reason", ""))
        rule_evidence = normalize_text(record.get("f032_evidence", ""))
        codex = _effective_codex_decision(record, codex)
        final_action = normalize_text(codex.get("codex_ai_action", ""))
        record["f032_rule_action"] = rule_action
        record["f032_rule_bucket"] = rule_bucket
        record["f032_rule_fail_category"] = rule_fail_category
        record["f032_rule_confidence"] = rule_confidence
        record["f032_rule_reason"] = rule_reason
        record["f032_rule_evidence"] = rule_evidence
        for column in CODEX_AI_DECISION_COLUMNS:
            if column == "f032_decision_id":
                continue
            record[column] = normalize_text(codex.get(column, ""))
        record["f032_action"] = final_action
        record["f032_decision_bucket"] = normalize_text(codex.get("codex_ai_decision_bucket", ""))
        record["f032_fail_category"] = "" if final_action == "allow_if_other_checks_pass" else normalize_text(
            codex.get("codex_ai_fail_category", "")
        )
        record["f032_confidence"] = normalize_text(codex.get("codex_ai_confidence", ""))
        record["f032_needs_user_guidance"] = normalize_text(codex.get("codex_ai_needs_user_guidance", ""))
        record["f032_rescan_needed"] = normalize_text(codex.get("codex_ai_rescan_needed", ""))
        record["f032_reason"] = normalize_text(codex.get("codex_ai_reason", ""))
        record["f032_evidence"] = normalize_text(codex.get("codex_ai_evidence", ""))
        if final_action == "manual_review":
            record["near_miss_type"] = normalize_text(record.get("near_miss_type", "")) or "codex_ai_manual_review"
            record["identity_recommended_action"] = "manual_review"
            if not normalize_text(record.get("recovery_hint", "")):
                record["recovery_hint"] = record["f032_reason"]
            if not normalize_text(record.get("watch_data_summary", "")):
                record["watch_data_summary"] = record["f032_reason"]
        rows.append(record)
    return pd.DataFrame(rows).fillna("")


def _health_row(
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


def _missing_visible_field_count(df: pd.DataFrame, field: str) -> int:
    if df.empty:
        return 0
    if field not in df.columns:
        return len(df.index)
    return int(df[field].map(normalize_text).eq("").sum())


def _run_ai_gate_quality_report(root_path: Path, observed_utc: str) -> dict[str, object]:
    try:
        return build_ai_gate_quality_report(root=root_path, observed_utc=observed_utc)
    except Exception as exc:
        return {
            "status": "fail",
            "fail_checks": 1,
            "warn_checks": 0,
            "report_path": "",
            "summary_path": "",
            "notes": f"quality_report_exception={type(exc).__name__}:{normalize_text(exc)}",
        }


def _quality_notes(notes: object, quality_summary: dict[str, object]) -> str:
    base = normalize_text(notes)
    base_parts = [
        part
        for part in base.split(";")
        if part
        and not part.startswith("quality_status=")
        and not part.startswith("quality_fail_checks=")
        and not part.startswith("quality_warn_checks=")
        and not part.startswith("quality_report_path=")
        and not part.startswith("quality_report_exception=")
    ]
    quality_bits = [
        f"quality_status={normalize_text(quality_summary.get('status', ''))}",
        f"quality_fail_checks={_int_value(quality_summary.get('fail_checks', 0))}",
        f"quality_warn_checks={_int_value(quality_summary.get('warn_checks', 0))}",
    ]
    report_path = normalize_text(quality_summary.get("report_path", ""))
    if report_path:
        quality_bits.append(f"quality_report_path={report_path}")
    extra_notes = normalize_text(quality_summary.get("notes", ""))
    if extra_notes:
        quality_bits.append(extra_notes)
    return ";".join([part for part in [*base_parts, *quality_bits] if part])


def _write_quality_blocked_manifest(
    *,
    manifest_path: Path,
    live_manifest_path: Path,
    manifest_row: dict[str, object],
    quality_summary: dict[str, object],
) -> None:
    blocked_row = dict(manifest_row)
    blocked_row["ai_gate_status"] = "failed_quality"
    blocked_row["operator_ready_flag"] = "0"
    blocked_row["block_reason"] = "ai_gate_quality_report_failed"
    blocked_row["ai_gate_fail_rows"] = str(_int_value(quality_summary.get("fail_checks", 0)))
    blocked_row["ai_gate_warn_rows"] = str(_int_value(quality_summary.get("warn_checks", 0)))
    blocked_row["ai_gate_quality_status"] = normalize_text(quality_summary.get("status", ""))
    blocked_row["ai_gate_quality_fail_checks"] = str(_int_value(quality_summary.get("fail_checks", 0)))
    blocked_row["ai_gate_quality_warn_checks"] = str(_int_value(quality_summary.get("warn_checks", 0)))
    blocked_row["ai_gate_quality_report_path"] = normalize_text(quality_summary.get("report_path", ""))
    blocked_row["notes"] = _quality_notes(blocked_row.get("notes", ""), quality_summary)
    write_csv(manifest_path, pd.DataFrame([blocked_row]), REVIEW_HANDOFF_MANIFEST_COLUMNS)
    write_csv(live_manifest_path, pd.DataFrame([blocked_row]), REVIEW_HANDOFF_MANIFEST_COLUMNS)


def apply_review_intelligence_gate(
    *,
    root: Path | None = None,
    supplier_id: str = "",
    run_id: str = "",
    observed_utc: str | None = None,
    force_rebuild: bool = False,
    emit_json: bool = True,
) -> dict[str, object]:
    paths = get_manager_paths(root=root)
    root_path = paths.root
    live_dir = paths.system_dir / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    observed = observed_utc or _utc_now_iso()
    selected_dir = _handoff_dir(root_path, supplier_id=supplier_id, run_id=run_id)
    candidate_manifest_path = selected_dir / "candidate_manifest.csv"
    manifest_path = selected_dir / "manifest.csv"

    if manifest_path.exists() and not force_rebuild:
        manifest = read_csv(manifest_path, REVIEW_HANDOFF_MANIFEST_COLUMNS)
        row = manifest.iloc[0].to_dict() if not manifest.empty else {}
        ai_gate_status = normalize_text(row.get("ai_gate_status", ""))
        operator_ready_flag = normalize_text(row.get("operator_ready_flag", ""))
        if ai_gate_status == "passed" and operator_ready_flag == "1":
            quality_summary = _run_ai_gate_quality_report(root_path, observed)
            quality_fail_checks = _int_value(quality_summary.get("fail_checks", 0))
            if quality_fail_checks:
                _write_quality_blocked_manifest(
                    manifest_path=manifest_path,
                    live_manifest_path=live_dir / "review_handoff_manifest.csv",
                    manifest_row=row,
                    quality_summary=quality_summary,
                )
                summary = {
                    "status": "failed",
                    "supplier_id": normalize_text(row.get("supplier_id", supplier_id)),
                    "run_id": normalize_text(row.get("run_id", run_id)),
                    "manifest_path": str(manifest_path),
                    "pass_review_rows": normalize_text(row.get("pass_review_rows", "0")) or "0",
                    "near_miss_review_rows": normalize_text(row.get("near_miss_review_rows", "0")) or "0",
                    "ai_gate_status": "failed_quality",
                    "operator_ready_flag": "0",
                    "block_reason": "ai_gate_quality_report_failed",
                    "ai_gate_quality_status": normalize_text(quality_summary.get("status", "")),
                    "ai_gate_quality_fail_checks": str(quality_fail_checks),
                    "ai_gate_quality_warn_checks": str(_int_value(quality_summary.get("warn_checks", 0))),
                    "ai_gate_quality_report_path": normalize_text(quality_summary.get("report_path", "")),
                    "notes": "FPM156 quality report failed. Operator-ready manifest was blocked.",
                }
                if emit_json:
                    print(json.dumps(summary, indent=2, sort_keys=True))
                return summary
            row["ai_gate_quality_status"] = normalize_text(quality_summary.get("status", ""))
            row["ai_gate_quality_fail_checks"] = "0"
            row["ai_gate_quality_warn_checks"] = str(_int_value(quality_summary.get("warn_checks", 0)))
            row["ai_gate_quality_report_path"] = normalize_text(quality_summary.get("report_path", ""))
            row["notes"] = _quality_notes(row.get("notes", ""), quality_summary)
            write_csv(manifest_path, pd.DataFrame([row]), REVIEW_HANDOFF_MANIFEST_COLUMNS)
            write_csv(live_dir / "review_handoff_manifest.csv", pd.DataFrame([row]), REVIEW_HANDOFF_MANIFEST_COLUMNS)
            summary = {
                "status": "already_gated",
                "supplier_id": normalize_text(row.get("supplier_id", supplier_id)),
                "run_id": normalize_text(row.get("run_id", run_id)),
                "manifest_path": str(manifest_path),
                "pass_review_rows": normalize_text(row.get("pass_review_rows", "0")) or "0",
                "near_miss_review_rows": normalize_text(row.get("near_miss_review_rows", "0")) or "0",
                "ai_gate_status": ai_gate_status,
                "operator_ready_flag": operator_ready_flag,
                "ai_gate_quality_status": normalize_text(row.get("ai_gate_quality_status", "")),
                "ai_gate_quality_fail_checks": "0",
                "ai_gate_quality_warn_checks": normalize_text(row.get("ai_gate_quality_warn_checks", "")),
                "ai_gate_quality_report_path": normalize_text(row.get("ai_gate_quality_report_path", "")),
            }
            if emit_json:
                print(json.dumps(summary, indent=2, sort_keys=True))
            return summary

    if not candidate_manifest_path.exists():
        summary = {
            "status": "blocked",
            "supplier_id": supplier_id,
            "run_id": run_id,
            "manifest_path": "",
            "candidate_manifest_path": str(candidate_manifest_path),
            "block_reason": "missing_candidate_manifest",
            "notes": "FPM150 raw candidate pack has not been built yet.",
        }
        if emit_json:
            print(json.dumps(summary, indent=2, sort_keys=True))
        return summary

    candidate_manifest = read_csv(candidate_manifest_path, REVIEW_CANDIDATE_MANIFEST_COLUMNS)
    if candidate_manifest.empty:
        summary = {
            "status": "failed",
            "supplier_id": supplier_id,
            "run_id": run_id,
            "manifest_path": "",
            "candidate_manifest_path": str(candidate_manifest_path),
            "block_reason": "empty_candidate_manifest",
            "notes": "FPM150 candidate manifest exists but has no row.",
        }
        if emit_json:
            print(json.dumps(summary, indent=2, sort_keys=True))
        return summary

    raw_manifest = candidate_manifest.iloc[0].to_dict()
    selected_supplier = normalize_text(raw_manifest.get("supplier_id", supplier_id))
    selected_run = normalize_text(raw_manifest.get("run_id", run_id))
    raw_pass_path = _resolve_path(root_path, raw_manifest.get("raw_pass_review_path", ""))
    raw_near_miss_path = _resolve_path(root_path, raw_manifest.get("raw_near_miss_review_path", ""))
    raw_summary_path = _resolve_path(root_path, raw_manifest.get("raw_summary_path", ""))
    hard_reject_rows = normalize_text(raw_manifest.get("hard_reject_rows", "0")) or "0"

    f032_result = build_review_intelligence_cycle(
        pass_review_path=raw_pass_path,
        near_miss_review_path=raw_near_miss_path,
        title_match_path=root_path / "out" / "analysis_reports" / "f_title_match_agent_decisions_latest.csv",
        supplier_inbox_dir=root_path / "out" / "systems" / "F" / "inbox" / "suppliers",
        evidence_output_path=selected_dir / "ai_review_intelligence_evidence_pack.csv",
        decision_output_path=selected_dir / "ai_review_intelligence_decisions.csv",
        fail_category_output_path=selected_dir / "ai_review_intelligence_fail_categories.csv",
        checklist_output_path=selected_dir / "ai_review_intelligence_checklist.csv",
        rule_suggestion_output_path=selected_dir / "ai_rule_tightening_suggestions.csv",
        health_output_path=selected_dir / "ai_review_intelligence_health.csv",
        summary_output_path=selected_dir / "ai_review_intelligence_summary.md",
        observed_utc=observed,
    )

    raw_pass_df = _read_any_csv(raw_pass_path)
    raw_near_df = _read_any_csv(raw_near_miss_path)
    raw_total_rows = len(raw_pass_df.index) + len(raw_near_df.index)
    f032_fail_rows = int(f032_result.health_df["status"].eq("FAIL").sum()) if not f032_result.health_df.empty else 0
    f032_warn_rows = int(f032_result.health_df["status"].eq("WARN").sum()) if not f032_result.health_df.empty else 0
    ai_health_path = selected_dir / "ai_review_intelligence_gate_health.csv"
    ai_queue_path = selected_dir / "ai_review_queue.csv"
    ai_decision_template_path = selected_dir / "codex_ai_review_decision_template.csv"
    ai_decision_path = selected_dir / "codex_ai_review_decisions.csv"

    queue_df = _build_ai_review_queue(f032_result.evidence_df, f032_result.decision_df)
    _write_raw_output(ai_queue_path, queue_df)
    _write_decision_template(ai_decision_template_path, queue_df)
    codex_decision_df = _load_codex_decisions(ai_decision_path)
    codex_decision_df, stale_codex_decision_rows, stale_codex_archive_path = _archive_stale_codex_decisions(
        codex_decision_path=ai_decision_path,
        ai_queue_path=ai_queue_path,
        queue_df=queue_df,
        codex_df=codex_decision_df,
        observed_utc=observed,
    )
    scanner_fail_evidence_df = _load_current_scanner_fail_evidence(root_path)
    scanner_fail_lookup = _current_scanner_fail_lookup(scanner_fail_evidence_df, selected_run)
    codex_decision_df, normalized_codex_rows = _normalize_codex_secondary_evidence_decisions(
        queue_df,
        codex_decision_df,
        observed,
    )
    codex_decision_df, current_scanner_fail_changed_rows, current_scanner_fail_guard_rows = (
        _normalize_codex_current_scanner_fail_decisions(
            queue_df,
            codex_decision_df,
            observed,
            scanner_fail_lookup,
        )
    )
    precheck_reused_rows = 0
    precheck_stale_decision_rows = 0
    codex_decision_df, precheck_reused_rows, precheck_stale_decision_rows = _merge_matching_precheck_decisions(
        root=root_path,
        supplier_id=selected_supplier,
        run_id=selected_run,
        queue_df=queue_df,
        codex_df=codex_decision_df,
        observed_utc=observed,
    )
    if (
        normalized_codex_rows
        or current_scanner_fail_changed_rows
        or stale_codex_decision_rows
        or precheck_reused_rows
    ):
        _write_raw_output(ai_decision_path, codex_decision_df)
    missing_codex, invalid_codex, missing_codex_reason = _codex_decision_gaps(queue_df, codex_decision_df)
    missing_amazon_page_text_columns = _missing_columns(queue_df, AMAZON_PAGE_TEXT_QUEUE_COLUMNS)

    if missing_codex or invalid_codex or missing_codex_reason:
        health_rows = [
            _health_row(
                observed_utc=observed,
                check="ai_queue_amazon_page_text_columns_present",
                status="fail" if missing_amazon_page_text_columns else "ok",
                value="|".join(missing_amazon_page_text_columns) if missing_amazon_page_text_columns else "present",
                notes="AI queue should carry Amazon product description, feature bullets, and detail text columns when available.",
                source_path=ai_queue_path,
            ),
            _health_row(
                observed_utc=observed,
                check="codex_ai_decision_rows_pending",
                status="warn",
                value=missing_codex,
                notes="Codex AI must decide every queued row before the operator manifest can be published.",
                source_path=ai_queue_path,
            ),
            _health_row(
                observed_utc=observed,
                check="codex_ai_invalid_action_rows",
                status="fail" if invalid_codex else "ok",
                value=invalid_codex,
                notes="Codex AI decisions must use a valid action.",
                source_path=ai_decision_path,
            ),
            _health_row(
                observed_utc=observed,
                check="codex_ai_missing_reason_rows",
                status="fail" if missing_codex_reason else "ok",
                value=missing_codex_reason,
                notes="Codex AI decisions must include a reason.",
                source_path=ai_decision_path,
            ),
            _health_row(
                observed_utc=observed,
                check="current_scanner_fail_guard_rows",
                status="warn" if current_scanner_fail_guard_rows else "ok",
                value=current_scanner_fail_guard_rows,
                notes="Rows already failed by the current scanner are automatically blocked from clean operator handoff.",
                source_path=root_path
                / "out"
                / "systems"
                / "F"
                / "page_evidence_backfill"
                / "current_scanner_fail_evidence.csv",
            ),
            _health_row(
                observed_utc=observed,
                check="stale_codex_ai_decision_rows_archived",
                status="warn" if stale_codex_decision_rows else "ok",
                value=stale_codex_decision_rows,
                notes="Old Codex AI decisions not present in the current AI queue are archived and removed from the active decision file.",
                source_path=stale_codex_archive_path,
            ),
            _health_row(
                observed_utc=observed,
                check="precheck_reused_in_final_rows",
                status="ok",
                value=precheck_reused_rows,
                notes="Hidden incremental AI precheck decisions reused in this final handoff only when evidence hashes matched.",
                source_path=ai_precheck_dir(root_path, supplier_id=selected_supplier, run_id=selected_run)
                / "ai_precheck_registry.csv",
            ),
            _health_row(
                observed_utc=observed,
                check="precheck_stale_decision_rows",
                status="warn" if precheck_stale_decision_rows else "ok",
                value=precheck_stale_decision_rows,
                notes="Hidden precheck decisions not reused because the action, reason, or evidence hash was unsafe.",
                source_path=ai_precheck_dir(root_path, supplier_id=selected_supplier, run_id=selected_run)
                / "codex_ai_review_decisions.csv",
            ),
        ]
        write_csv(ai_health_path, pd.DataFrame(health_rows), MANAGER_HEALTH_COLUMNS)
        summary = {
            "status": "pending_ai_decision",
            "supplier_id": selected_supplier,
            "run_id": selected_run,
            "manifest_path": "",
            "candidate_manifest_path": str(candidate_manifest_path),
            "ai_review_queue_path": str(ai_queue_path),
            "codex_ai_decision_template_path": str(ai_decision_template_path),
            "codex_ai_decision_path": str(ai_decision_path),
            "queued_rows": str(len(queue_df.index)),
            "pending_decision_rows": str(missing_codex),
            "invalid_decision_rows": str(invalid_codex),
            "missing_reason_rows": str(missing_codex_reason),
            "ai_gate_status": "pending_ai_decision",
            "operator_ready_flag": "0",
            "ai_gate_warn_rows": "1",
            "current_scanner_fail_guard_rows": str(current_scanner_fail_guard_rows),
            "stale_codex_decision_rows_archived": str(stale_codex_decision_rows),
            "precheck_reused_in_final_rows": str(precheck_reused_rows),
            "precheck_stale_decision_rows": str(precheck_stale_decision_rows),
            "notes": "Codex AI decisions are required before the operator-ready manifest is written.",
        }
        if emit_json:
            print(json.dumps(summary, indent=2, sort_keys=True))
        return summary

    pass_with_ai = _apply_codex_decisions_to_review_rows(raw_pass_df, f032_result.decision_df, "passes", codex_decision_df)
    near_with_ai = _apply_codex_decisions_to_review_rows(raw_near_df, f032_result.decision_df, "near_misses", codex_decision_df)

    ai_pass_df = pass_with_ai[pass_with_ai["f032_action"].eq("allow_if_other_checks_pass")].copy() if not pass_with_ai.empty else pd.DataFrame()
    near_allow_df = near_with_ai[near_with_ai["f032_action"].eq("allow_if_other_checks_pass")].copy() if not near_with_ai.empty else pd.DataFrame()
    pass_manual_df = pass_with_ai[pass_with_ai["f032_action"].eq("manual_review")].copy() if not pass_with_ai.empty else pd.DataFrame()
    near_manual_df = near_with_ai[near_with_ai["f032_action"].eq("manual_review")].copy() if not near_with_ai.empty else pd.DataFrame()
    ai_near_df = pd.concat([near_allow_df, pass_manual_df, near_manual_df], ignore_index=True).fillna("")
    ai_manual_df = pd.concat([pass_manual_df, near_manual_df], ignore_index=True).fillna("")
    ai_rescan_df = pd.concat(
        [
            pass_with_ai[pass_with_ai["f032_action"].eq("rescan_needed")] if not pass_with_ai.empty else pd.DataFrame(),
            near_with_ai[near_with_ai["f032_action"].eq("rescan_needed")] if not near_with_ai.empty else pd.DataFrame(),
        ],
        ignore_index=True,
    ).fillna("")
    ai_removed_df = pd.concat(
        [
            pass_with_ai[pass_with_ai["f032_action"].eq("remove_from_clean_pass")] if not pass_with_ai.empty else pd.DataFrame(),
            near_with_ai[near_with_ai["f032_action"].eq("remove_from_clean_pass")] if not near_with_ai.empty else pd.DataFrame(),
        ],
        ignore_index=True,
    ).fillna("")

    ai_pass_path = selected_dir / "ai_operator_pass_review.csv"
    ai_near_path = selected_dir / "ai_operator_near_miss_review.csv"
    ai_manual_path = selected_dir / "ai_manual_review.csv"
    ai_rescan_path = selected_dir / "ai_rescan_queue.csv"
    ai_removed_path = selected_dir / "ai_removed_from_clean_pass_audit.csv"
    routed_total_rows = len(ai_pass_df.index) + len(ai_near_df.index) + len(ai_rescan_df.index) + len(ai_removed_df.index)
    visible_df = pd.concat([ai_pass_df, ai_near_df], ignore_index=True).fillna("")
    missing_visible_ids = _missing_visible_field_count(visible_df, "f032_decision_id")
    missing_visible_actions = _missing_visible_field_count(visible_df, "f032_action")
    ai_gate_warn_rows = (
        f032_warn_rows
        + (1 if current_scanner_fail_guard_rows else 0)
        + (1 if stale_codex_decision_rows else 0)
    )

    health_rows = [
        _health_row(
            observed_utc=observed,
            check="f032_health_fail_rows",
            status="fail" if f032_fail_rows else "ok",
            value=f032_fail_rows,
            notes="F032 hard health failures must be zero before operator handoff.",
            source_path=selected_dir / "ai_review_intelligence_health.csv",
        ),
        _health_row(
            observed_utc=observed,
            check="ai_queue_amazon_page_text_columns_present",
            status="fail" if missing_amazon_page_text_columns else "ok",
            value="|".join(missing_amazon_page_text_columns) if missing_amazon_page_text_columns else "present",
            notes="AI queue should carry Amazon product description, feature bullets, and detail text columns when available.",
            source_path=ai_queue_path,
        ),
        _health_row(
            observed_utc=observed,
            check="current_scanner_fail_guard_rows",
            status="warn" if current_scanner_fail_guard_rows else "ok",
            value=current_scanner_fail_guard_rows,
            notes="Rows already failed by the current scanner are automatically blocked from clean operator handoff.",
            source_path=root_path
            / "out"
            / "systems"
            / "F"
            / "page_evidence_backfill"
            / "current_scanner_fail_evidence.csv",
        ),
        _health_row(
            observed_utc=observed,
            check="stale_codex_ai_decision_rows_archived",
            status="warn" if stale_codex_decision_rows else "ok",
            value=stale_codex_decision_rows,
            notes="Old Codex AI decisions not present in the current AI queue are archived and removed from the active decision file.",
            source_path=stale_codex_archive_path,
        ),
        _health_row(
            observed_utc=observed,
            check="precheck_reused_in_final_rows",
            status="ok",
            value=precheck_reused_rows,
            notes="Hidden incremental AI precheck decisions reused in this final handoff only when evidence hashes matched.",
            source_path=ai_precheck_dir(root_path, supplier_id=selected_supplier, run_id=selected_run)
            / "ai_precheck_registry.csv",
        ),
        _health_row(
            observed_utc=observed,
            check="precheck_stale_decision_rows",
            status="warn" if precheck_stale_decision_rows else "ok",
            value=precheck_stale_decision_rows,
            notes="Hidden precheck decisions not reused because the action, reason, or evidence hash was unsafe.",
            source_path=ai_precheck_dir(root_path, supplier_id=selected_supplier, run_id=selected_run)
            / "codex_ai_review_decisions.csv",
        ),
        _health_row(
            observed_utc=observed,
            check="decision_rows_match_raw_rows",
            status="ok" if int(f032_result.report["decision_rows"]) == raw_total_rows else "fail",
            value=f"{f032_result.report['decision_rows']}/{raw_total_rows}",
            notes="Every raw candidate row must receive one F032 decision.",
            source_path=candidate_manifest_path,
        ),
        _health_row(
            observed_utc=observed,
            check="routed_rows_match_raw_rows",
            status="ok" if routed_total_rows == raw_total_rows else "fail",
            value=f"{routed_total_rows}/{raw_total_rows}",
            notes="Every raw row must route to pass, manual/near-miss, rescan, or removed audit.",
            source_path=candidate_manifest_path,
        ),
        _health_row(
            observed_utc=observed,
            check="visible_rows_have_f032_decision_id",
            status="ok" if missing_visible_ids == 0 else "fail",
            value=missing_visible_ids,
            notes="Rows visible to the operator must prove the AI gate saw them.",
            source_path=ai_pass_path,
        ),
        _health_row(
            observed_utc=observed,
            check="visible_rows_have_f032_action",
            status="ok" if missing_visible_actions == 0 else "fail",
            value=missing_visible_actions,
            notes="Rows visible to the operator must carry the F032 action.",
            source_path=ai_pass_path,
        ),
        _health_row(
            observed_utc=observed,
            check="raw_paths_not_operator_paths",
            status="ok" if ai_pass_path != raw_pass_path and ai_near_path != raw_near_miss_path else "fail",
            value="checked",
            notes="Operator paths must point to AI-gated files, not raw scanner files.",
            source_path=candidate_manifest_path,
        ),
    ]
    hard_fail_rows = sum(1 for row in health_rows if row["status"] == "fail")
    write_csv(ai_health_path, pd.DataFrame(health_rows), MANAGER_HEALTH_COLUMNS)

    if hard_fail_rows:
        summary = {
            "status": "failed",
            "supplier_id": selected_supplier,
            "run_id": selected_run,
            "manifest_path": "",
            "candidate_manifest_path": str(candidate_manifest_path),
            "ai_gate_status": "failed",
            "ai_gate_fail_rows": str(hard_fail_rows),
            "f032_health_fail_rows": str(f032_fail_rows),
            "ai_gate_warn_rows": str(ai_gate_warn_rows),
            "notes": "AI gate failed. No operator-ready manifest was written.",
        }
        if emit_json:
            print(json.dumps(summary, indent=2, sort_keys=True))
        return summary

    _write_raw_output(ai_pass_path, ai_pass_df)
    _write_raw_output(ai_near_path, ai_near_df)
    _write_raw_output(ai_manual_path, ai_manual_df)
    _write_raw_output(ai_rescan_path, ai_rescan_df)
    _write_raw_output(ai_removed_path, ai_removed_df)

    manifest_row = {
        "built_at_utc": normalize_text(raw_manifest.get("built_at_utc", observed)),
        "supplier_id": selected_supplier,
        "supplier_name": normalize_text(raw_manifest.get("supplier_name", "")),
        "run_id": selected_run,
        "review_snapshot_id": normalize_text(raw_manifest.get("review_snapshot_id", "")),
        "source_file_path": normalize_text(raw_manifest.get("source_file_path", "")),
        "source_seen_at_utc": normalize_text(raw_manifest.get("source_seen_at_utc", "")),
        "completed_at_utc": normalize_text(raw_manifest.get("completed_at_utc", "")),
        "pass_review_rows": str(len(ai_pass_df.index)),
        "near_miss_review_rows": str(len(ai_near_df.index)),
        "hard_reject_rows": hard_reject_rows,
        "pass_review_path": str(ai_pass_path),
        "near_miss_review_path": str(ai_near_path),
        "summary_path": str(raw_summary_path),
        "handoff_dir": str(selected_dir),
        "published_to_operator_latest_flag": "0",
        "ai_gate_status": "passed",
        "ai_gate_observed_utc": observed,
        "ai_gate_version": AI_GATE_VERSION,
        "ai_gate_health_path": str(ai_health_path),
        "ai_review_queue_path": str(ai_queue_path),
        "ai_gate_decision_path": str(ai_decision_path),
        "codex_ai_decision_path": str(ai_decision_path),
        "ai_gate_checklist_path": str(selected_dir / "ai_review_intelligence_checklist.csv"),
        "ai_gate_rule_suggestion_path": str(selected_dir / "ai_rule_tightening_suggestions.csv"),
        "ai_gate_rescan_queue_path": str(ai_rescan_path),
        "ai_gate_removed_audit_path": str(ai_removed_path),
        "ai_gate_manual_review_path": str(ai_manual_path),
        "raw_candidate_manifest_path": str(candidate_manifest_path),
        "raw_pass_review_path": str(raw_pass_path),
        "raw_near_miss_review_path": str(raw_near_miss_path),
        "ai_gate_fail_rows": "0",
        "ai_gate_warn_rows": str(ai_gate_warn_rows),
        "ai_gate_clear_rows": str(len(ai_pass_df.index)),
        "ai_gate_manual_rows": str(len(ai_manual_df.index)),
        "ai_gate_rescan_rows": str(len(ai_rescan_df.index)),
        "ai_gate_removed_rows": str(len(ai_removed_df.index)),
        "operator_ready_flag": "1",
        "block_reason": "",
        "notes": (
            "ai_gated_operator_review_pack_built;"
            f"precheck_reused_in_final_rows={precheck_reused_rows};"
            f"precheck_stale_decision_rows={precheck_stale_decision_rows}"
        ),
    }
    write_csv(manifest_path, pd.DataFrame([manifest_row]), REVIEW_HANDOFF_MANIFEST_COLUMNS)
    write_csv(live_dir / "review_handoff_manifest.csv", pd.DataFrame([manifest_row]), REVIEW_HANDOFF_MANIFEST_COLUMNS)

    quality_summary = _run_ai_gate_quality_report(root_path, observed)
    quality_fail_checks = _int_value(quality_summary.get("fail_checks", 0))
    quality_warn_checks = _int_value(quality_summary.get("warn_checks", 0))
    if quality_fail_checks:
        _write_quality_blocked_manifest(
            manifest_path=manifest_path,
            live_manifest_path=live_dir / "review_handoff_manifest.csv",
            manifest_row=manifest_row,
            quality_summary=quality_summary,
        )
        summary = {
            "status": "failed",
            "supplier_id": selected_supplier,
            "run_id": selected_run,
            "manifest_path": str(manifest_path),
            "candidate_manifest_path": str(candidate_manifest_path),
            "pass_review_rows": str(len(ai_pass_df.index)),
            "near_miss_review_rows": str(len(ai_near_df.index)),
            "manual_review_rows": str(len(ai_manual_df.index)),
            "rescan_needed_rows": str(len(ai_rescan_df.index)),
            "remove_from_clean_pass_rows": str(len(ai_removed_df.index)),
            "ai_gate_status": "failed_quality",
            "ai_gate_fail_rows": str(quality_fail_checks),
            "ai_gate_warn_rows": str(quality_warn_checks),
            "operator_ready_flag": "0",
            "block_reason": "ai_gate_quality_report_failed",
            "ai_gate_quality_status": normalize_text(quality_summary.get("status", "")),
            "ai_gate_quality_fail_checks": str(quality_fail_checks),
            "ai_gate_quality_warn_checks": str(quality_warn_checks),
            "ai_gate_quality_report_path": normalize_text(quality_summary.get("report_path", "")),
            "current_scanner_fail_guard_rows": str(current_scanner_fail_guard_rows),
            "stale_codex_decision_rows_archived": str(stale_codex_decision_rows),
            "precheck_reused_in_final_rows": str(precheck_reused_rows),
            "precheck_stale_decision_rows": str(precheck_stale_decision_rows),
            "notes": "FPM156 quality report failed. Operator-ready manifest was blocked.",
        }
        if emit_json:
            print(json.dumps(summary, indent=2, sort_keys=True))
        return summary

    manifest_row["ai_gate_quality_status"] = normalize_text(quality_summary.get("status", ""))
    manifest_row["ai_gate_quality_fail_checks"] = "0"
    manifest_row["ai_gate_quality_warn_checks"] = str(quality_warn_checks)
    manifest_row["ai_gate_quality_report_path"] = normalize_text(quality_summary.get("report_path", ""))
    manifest_row["notes"] = _quality_notes(manifest_row.get("notes", ""), quality_summary)
    write_csv(manifest_path, pd.DataFrame([manifest_row]), REVIEW_HANDOFF_MANIFEST_COLUMNS)
    write_csv(live_dir / "review_handoff_manifest.csv", pd.DataFrame([manifest_row]), REVIEW_HANDOFF_MANIFEST_COLUMNS)

    summary = {
        "status": "gated",
        "supplier_id": selected_supplier,
        "run_id": selected_run,
        "manifest_path": str(manifest_path),
        "candidate_manifest_path": str(candidate_manifest_path),
        "pass_review_rows": str(len(ai_pass_df.index)),
        "near_miss_review_rows": str(len(ai_near_df.index)),
        "manual_review_rows": str(len(ai_manual_df.index)),
        "rescan_needed_rows": str(len(ai_rescan_df.index)),
        "remove_from_clean_pass_rows": str(len(ai_removed_df.index)),
        "ai_gate_status": "passed",
        "ai_gate_fail_rows": "0",
        "ai_gate_warn_rows": str(ai_gate_warn_rows),
        "operator_ready_flag": "1",
        "ai_gate_quality_status": normalize_text(quality_summary.get("status", "")),
        "ai_gate_quality_fail_checks": "0",
        "ai_gate_quality_warn_checks": str(quality_warn_checks),
        "ai_gate_quality_report_path": normalize_text(quality_summary.get("report_path", "")),
        "current_scanner_fail_guard_rows": str(current_scanner_fail_guard_rows),
        "stale_codex_decision_rows_archived": str(stale_codex_decision_rows),
        "precheck_reused_in_final_rows": str(precheck_reused_rows),
        "precheck_stale_decision_rows": str(precheck_stale_decision_rows),
    }
    if emit_json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply the F032 AI gate to a completed FPM raw candidate review pack.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--supplier-id", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--observed-utc", default=None)
    parser.add_argument("--force-rebuild", action="store_true")
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    apply_review_intelligence_gate(
        root=root,
        supplier_id=args.supplier_id,
        run_id=args.run_id,
        observed_utc=args.observed_utc,
        force_rebuild=bool(args.force_rebuild),
    )


if __name__ == "__main__":
    main()
