from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._schemas import get_f_output_contract


DEFAULT_ANALYSIS_DIR = ROOT / "out" / "analysis_reports"
DEFAULT_SUPPLIER_INBOX_DIR = ROOT / "out" / "systems" / "F" / "inbox" / "suppliers"
DEFAULT_SCRAPE_EVIDENCE_PATH = ROOT / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path
DEFAULT_QUEUE_OUTPUT_PATH = DEFAULT_ANALYSIS_DIR / "f_passed_product_page_evidence_backfill_queue_latest.csv"
DEFAULT_F061_OUTPUT_PATH = DEFAULT_ANALYSIS_DIR / "f_passed_product_page_evidence_backfill_f061_active_run_latest.csv"
DEFAULT_HEALTH_OUTPUT_PATH = DEFAULT_ANALYSIS_DIR / "f_passed_product_page_evidence_backfill_health_latest.csv"
DEFAULT_SUMMARY_OUTPUT_PATH = DEFAULT_ANALYSIS_DIR / "f_passed_product_page_evidence_backfill_summary_latest.csv"
DEFAULT_REPORT_OUTPUT_PATH = DEFAULT_ANALYSIS_DIR / "f_passed_product_page_evidence_backfill_summary_latest.md"


BACKFILL_QUEUE_COLUMNS = [
    "observed_utc",
    "backfill_batch_id",
    "backfill_scope",
    "backfill_id",
    "backfill_priority",
    "asin",
    "supplier_id",
    "supplier_sku",
    "candidate_id",
    "active_run_id",
    "review_batch_id",
    "supplier_title",
    "amazon_title",
    "brand",
    "barcode",
    "unit_cost",
    "currency",
    "vat_rate",
    "review_priority_score",
    "expected_profit_next_30d_gbp",
    "estimated_monthly_profit_gbp",
    "profit_per_unit_30d_gbp",
    "source_pass_file",
    "source_pass_files",
    "source_pass_row_count",
    "latest_pass_flag",
    "historical_pass_flag",
    "supplier_title_source",
    "existing_page_evidence_flag",
    "existing_evidence_observed_utc",
    "existing_product_detail_text_flag",
    "existing_product_description_flag",
    "existing_product_feature_bullets_flag",
    "f061_ready_flag",
    "recommended_next_action",
    "queue_reason",
]

_F061_ACTIVE_RUN_CONTRACT = get_f_output_contract("supplier_price_list_active_run")
F061_ACTIVE_RUN_COLUMNS = [
    *_F061_ACTIVE_RUN_CONTRACT.required_columns,
    *_F061_ACTIVE_RUN_CONTRACT.optional_columns,
]

HEALTH_COLUMNS = [
    "check",
    "status",
    "value",
    "notes",
    "observed_utc",
    "source_path",
]

SUMMARY_COLUMNS = [
    "observed_utc",
    "metric",
    "value",
]


@dataclass(frozen=True)
class PassedProductBackfillResult:
    queue_df: pd.DataFrame
    f061_active_run_df: pd.DataFrame
    health_df: pd.DataFrame
    summary_df: pd.DataFrame
    report: dict[str, Any]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _normalize_digits(value: object) -> str:
    return "".join(ch for ch in _normalize_text(value) if ch.isdigit())


def _to_int(value: object, default: int = 0) -> int:
    text = _normalize_text(value).replace(",", "")
    if text == "":
        return default
    try:
        return int(float(text))
    except ValueError:
        return default


def _to_float(value: object, default: float = 0.0) -> float:
    text = _normalize_text(value).replace(",", "").replace("%", "")
    if text == "":
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _hash_id(prefix: str, *parts: object, length: int = 16) -> str:
    raw = "|".join(_normalize_text(part) for part in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}_{digest}"


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _write_csv(path: Path, df: pd.DataFrame, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = ""
    out = out[columns].fillna("")
    out.to_csv(path, index=False)


def _pass_review_paths(analysis_dir: Path, scope: str) -> list[Path]:
    normalized_scope = _normalize_text(scope).lower() or "latest"
    latest_path = analysis_dir / "f_live_price_file_pass_review_latest.csv"
    historical_paths = sorted(
        path for path in analysis_dir.glob("f_live_price_file_pass_review_*.csv") if path.name != latest_path.name
    )
    if normalized_scope == "latest":
        return [latest_path] if latest_path.exists() else []
    if normalized_scope == "historical":
        return historical_paths
    if normalized_scope == "all":
        paths: list[Path] = []
        if latest_path.exists():
            paths.append(latest_path)
        paths.extend(historical_paths)
        return paths
    raise ValueError("scope must be one of: latest, historical, all")


def _load_pass_rows(paths: list[Path]) -> tuple[pd.DataFrame, int]:
    frames: list[pd.DataFrame] = []
    total_rows = 0
    for path in paths:
        df = _read_csv(path)
        if df.empty:
            continue
        total_rows += int(len(df.index))
        work = df.copy()
        work["source_pass_file"] = path.name
        work["source_pass_path"] = str(path)
        work["latest_pass_flag"] = "1" if path.name == "f_live_price_file_pass_review_latest.csv" else "0"
        frames.append(work)
    if not frames:
        return pd.DataFrame(), total_rows
    return pd.concat(frames, ignore_index=True).fillna(""), total_rows


def _load_supplier_catalog(supplier_inbox_dir: Path) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    if not supplier_inbox_dir.exists():
        return pd.DataFrame()
    for path in supplier_inbox_dir.glob("*/canonical_current.csv"):
        df = _read_csv(path)
        if df.empty or "supplier_sku" not in df.columns:
            continue
        work = df.copy()
        if "supplier_id" not in work.columns:
            work["supplier_id"] = path.parent.name
        for column in ["supplier_title", "brand", "barcode", "unit_cost", "currency", "vat_rate"]:
            if column not in work.columns:
                work[column] = ""
        work["_supplier_id_key"] = work["supplier_id"].map(_normalize_key)
        work["_supplier_sku_key"] = work["supplier_sku"].map(_normalize_key)
        rows.append(
            work[
                [
                    "_supplier_id_key",
                    "_supplier_sku_key",
                    "supplier_id",
                    "supplier_sku",
                    "supplier_title",
                    "brand",
                    "barcode",
                    "unit_cost",
                    "currency",
                    "vat_rate",
                ]
            ].copy()
        )
    if not rows:
        return pd.DataFrame()
    combined = pd.concat(rows, ignore_index=True).fillna("")
    combined = combined[combined["_supplier_sku_key"] != ""].copy()
    return combined.drop_duplicates(subset=["_supplier_id_key", "_supplier_sku_key"], keep="last")


def _merge_supplier_catalog(pass_df: pd.DataFrame, supplier_df: pd.DataFrame) -> pd.DataFrame:
    if pass_df.empty:
        return pass_df.copy()
    work = pass_df.copy()
    for column in ["active_supplier_id", "supplier_sku", "title", "brand", "supplier_title"]:
        if column not in work.columns:
            work[column] = ""
    work["_supplier_id_key"] = work["active_supplier_id"].map(_normalize_key)
    work["_supplier_sku_key"] = work["supplier_sku"].map(_normalize_key)
    if supplier_df.empty:
        work["supplier_title_source"] = "missing_supplier_canonical"
        for column in ["barcode", "unit_cost", "currency", "vat_rate"]:
            if column not in work.columns:
                work[column] = ""
        return work

    exact = supplier_df.rename(
        columns={
            "supplier_title": "_exact_supplier_title",
            "brand": "_exact_brand",
            "barcode": "_exact_barcode",
            "unit_cost": "_exact_unit_cost",
            "currency": "_exact_currency",
            "vat_rate": "_exact_vat_rate",
            "supplier_id": "_exact_supplier_id",
        }
    )
    work = work.merge(
        exact[
            [
                "_supplier_id_key",
                "_supplier_sku_key",
                "_exact_supplier_title",
                "_exact_brand",
                "_exact_barcode",
                "_exact_unit_cost",
                "_exact_currency",
                "_exact_vat_rate",
                "_exact_supplier_id",
            ]
        ],
        on=["_supplier_id_key", "_supplier_sku_key"],
        how="left",
    )
    fallback = supplier_df.sort_values(["_supplier_sku_key", "_supplier_id_key"]).drop_duplicates(
        subset=["_supplier_sku_key"], keep="last"
    )
    fallback = fallback.rename(
        columns={
            "supplier_title": "_fallback_supplier_title",
            "brand": "_fallback_brand",
            "barcode": "_fallback_barcode",
            "unit_cost": "_fallback_unit_cost",
            "currency": "_fallback_currency",
            "vat_rate": "_fallback_vat_rate",
            "supplier_id": "_fallback_supplier_id",
        }
    )
    work = work.merge(
        fallback[
            [
                "_supplier_sku_key",
                "_fallback_supplier_title",
                "_fallback_brand",
                "_fallback_barcode",
                "_fallback_unit_cost",
                "_fallback_currency",
                "_fallback_vat_rate",
                "_fallback_supplier_id",
            ]
        ],
        on="_supplier_sku_key",
        how="left",
    )

    exact_title = work["_exact_supplier_title"].fillna("").map(_normalize_text)
    fallback_title = work["_fallback_supplier_title"].fillna("").map(_normalize_text)
    existing_supplier_title = work.get("supplier_title", pd.Series([""] * len(work.index))).fillna("").map(_normalize_text)
    work["supplier_title"] = exact_title.where(
        exact_title != "",
        fallback_title.where(fallback_title != "", existing_supplier_title),
    )
    work["brand"] = work["_exact_brand"].fillna("").where(
        exact_title != "",
        work["_fallback_brand"].fillna("").where(fallback_title != "", work.get("brand", "").fillna("")),
    )
    work["barcode"] = work["_exact_barcode"].fillna("").where(
        exact_title != "",
        work["_fallback_barcode"].fillna(""),
    )
    work["unit_cost"] = work["_exact_unit_cost"].fillna("").where(
        exact_title != "",
        work["_fallback_unit_cost"].fillna(""),
    )
    work["currency"] = work["_exact_currency"].fillna("").where(
        exact_title != "",
        work["_fallback_currency"].fillna(""),
    )
    work["vat_rate"] = work["_exact_vat_rate"].fillna("").where(
        exact_title != "",
        work["_fallback_vat_rate"].fillna(""),
    )
    work["supplier_title_source"] = "active_supplier_canonical"
    work.loc[(exact_title == "") & (fallback_title != ""), "supplier_title_source"] = "supplier_sku_fallback"
    work.loc[work["supplier_title"].map(_normalize_text) == "", "supplier_title_source"] = "missing_supplier_title"
    drop_cols = [column for column in work.columns if column.startswith("_exact_") or column.startswith("_fallback_")]
    return work.drop(columns=drop_cols)


def _page_text_flags(record: dict[str, str]) -> dict[str, str]:
    detail = "1" if _normalize_text(record.get("product_detail_text", "")) else "0"
    description = "1" if _normalize_text(record.get("product_description", "")) else "0"
    bullets = "1" if _normalize_text(record.get("product_feature_bullets", "")) else "0"
    return {
        "existing_product_detail_text_flag": detail,
        "existing_product_description_flag": description,
        "existing_product_feature_bullets_flag": bullets,
        "existing_page_evidence_flag": "1" if "1" in {detail, description, bullets} else "0",
    }


def _existing_page_evidence_by_asin(scrape_evidence_path: Path) -> dict[str, dict[str, str]]:
    df = _read_csv(scrape_evidence_path)
    if df.empty or "asin" not in df.columns:
        return {}
    out: dict[str, dict[str, str]] = {}
    for _, row in df.fillna("").iterrows():
        record = {column: _normalize_text(value) for column, value in row.to_dict().items()}
        asin = _normalize_key(record.get("asin", ""))
        if asin == "":
            continue
        flags = _page_text_flags(record)
        if flags["existing_page_evidence_flag"] != "1":
            continue
        current = out.get(asin)
        if current is None:
            out[asin] = {**record, **flags}
            continue
        current_seen = _normalize_text(current.get("observed_utc", ""))
        new_seen = _normalize_text(record.get("observed_utc", ""))
        if new_seen >= current_seen:
            out[asin] = {**record, **flags}
    return out


def _first_non_blank(row: pd.Series | dict[str, object], fields: list[str]) -> str:
    for field in fields:
        value = _normalize_text(row.get(field, ""))
        if value != "":
            return value
    return ""


def _dedupe_pass_rows(pass_df: pd.DataFrame, observed_utc: str, backfill_batch_id: str, scope: str) -> pd.DataFrame:
    if pass_df.empty:
        return pd.DataFrame(columns=BACKFILL_QUEUE_COLUMNS)
    work = pass_df.copy()
    for column in [
        "active_supplier_id",
        "active_run_id",
        "review_batch_id",
        "candidate_id",
        "supplier_sku",
        "asin",
        "title",
        "brand",
        "source_pass_file",
        "latest_pass_flag",
        "supplier_title",
        "barcode",
        "unit_cost",
        "currency",
        "vat_rate",
        "review_priority_score",
        "expected_profit_next_30d_gbp",
        "estimated_monthly_profit_gbp",
        "profit_per_unit_30d_gbp",
        "supplier_title_source",
    ]:
        if column not in work.columns:
            work[column] = ""
    work["_asin_key"] = work["asin"].map(_normalize_key)
    work = work[work["_asin_key"] != ""].copy()
    if work.empty:
        return pd.DataFrame(columns=BACKFILL_QUEUE_COLUMNS)

    rows: list[dict[str, str]] = []
    grouped = work.groupby("_asin_key", sort=False)
    for asin, group in grouped:
        sorted_group = group.copy()
        sorted_group["_latest_sort"] = sorted_group["latest_pass_flag"].map(lambda value: 1 if _normalize_text(value) == "1" else 0)
        sorted_group["_priority_sort"] = sorted_group["review_priority_score"].map(_to_float)
        sorted_group = sorted_group.sort_values(
            by=["_latest_sort", "_priority_sort", "source_pass_file"],
            ascending=[False, False, False],
            kind="stable",
        )
        selected = sorted_group.iloc[0]
        source_files = sorted({_normalize_text(value) for value in group["source_pass_file"].tolist() if _normalize_text(value)})
        latest_flag = "1" if any(_normalize_text(value) == "1" for value in group["latest_pass_flag"].tolist()) else "0"
        pass_count = int(len(group.index))
        priority = _to_float(selected.get("review_priority_score", ""), default=0.0)
        if latest_flag == "1":
            priority += 100000.0
        priority += min(pass_count, 999)
        supplier_id = _first_non_blank(selected, ["active_supplier_id", "supplier_id"])
        supplier_sku = _normalize_text(selected.get("supplier_sku", ""))
        barcode = _normalize_digits(selected.get("barcode", ""))
        row = {
            "observed_utc": observed_utc,
            "backfill_batch_id": backfill_batch_id,
            "backfill_scope": scope,
            "backfill_id": _hash_id("f036", asin),
            "backfill_priority": f"{priority:.2f}",
            "asin": asin,
            "supplier_id": supplier_id,
            "supplier_sku": supplier_sku,
            "candidate_id": _normalize_text(selected.get("candidate_id", "")),
            "active_run_id": _normalize_text(selected.get("active_run_id", "")),
            "review_batch_id": _normalize_text(selected.get("review_batch_id", "")),
            "supplier_title": _normalize_text(selected.get("supplier_title", "")),
            "amazon_title": _first_non_blank(selected, ["amazon_title", "title"]),
            "brand": _normalize_text(selected.get("brand", "")),
            "barcode": barcode,
            "unit_cost": _normalize_text(selected.get("unit_cost", "")),
            "currency": _normalize_text(selected.get("currency", "")),
            "vat_rate": _normalize_text(selected.get("vat_rate", "")),
            "review_priority_score": _normalize_text(selected.get("review_priority_score", "")),
            "expected_profit_next_30d_gbp": _normalize_text(selected.get("expected_profit_next_30d_gbp", "")),
            "estimated_monthly_profit_gbp": _normalize_text(selected.get("estimated_monthly_profit_gbp", "")),
            "profit_per_unit_30d_gbp": _normalize_text(selected.get("profit_per_unit_30d_gbp", "")),
            "source_pass_file": _normalize_text(selected.get("source_pass_file", "")),
            "source_pass_files": "|".join(source_files),
            "source_pass_row_count": str(pass_count),
            "latest_pass_flag": latest_flag,
            "historical_pass_flag": "1" if any(name != "f_live_price_file_pass_review_latest.csv" for name in source_files) else "0",
            "supplier_title_source": _normalize_text(selected.get("supplier_title_source", "")),
            "existing_page_evidence_flag": "0",
            "existing_evidence_observed_utc": "",
            "existing_product_detail_text_flag": "0",
            "existing_product_description_flag": "0",
            "existing_product_feature_bullets_flag": "0",
            "f061_ready_flag": "1" if barcode else "0",
            "recommended_next_action": "run_f061_page_evidence_backfill" if barcode else "needs_barcode_before_f061_backfill",
            "queue_reason": "passed_product_missing_amazon_page_evidence",
        }
        rows.append(row)

    out = pd.DataFrame(rows, columns=BACKFILL_QUEUE_COLUMNS).fillna("")
    return out.sort_values(by=["backfill_priority", "asin"], ascending=[False, True], kind="stable").reset_index(drop=True)


def _apply_existing_evidence_skip(queue_df: pd.DataFrame, evidence_by_asin: dict[str, dict[str, str]]) -> tuple[pd.DataFrame, int]:
    if queue_df.empty:
        return queue_df.copy(), 0
    work = queue_df.copy()
    skip_indexes: list[int] = []
    for idx, row in work.iterrows():
        asin = _normalize_key(row.get("asin", ""))
        evidence = evidence_by_asin.get(asin)
        if evidence is None:
            continue
        flags = _page_text_flags(evidence)
        for column, value in flags.items():
            work.at[idx, column] = value
        work.at[idx, "existing_evidence_observed_utc"] = _normalize_text(evidence.get("observed_utc", ""))
        if flags["existing_page_evidence_flag"] == "1":
            skip_indexes.append(idx)
    if skip_indexes:
        work = work.drop(index=skip_indexes)
    return work.reset_index(drop=True), len(skip_indexes)


def _build_f061_active_run(queue_df: pd.DataFrame, observed_utc: str, batch_id: str) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    if queue_df.empty:
        return pd.DataFrame(columns=F061_ACTIVE_RUN_COLUMNS)
    ready_df = queue_df[queue_df["f061_ready_flag"].map(_normalize_text).eq("1")].copy()
    for _, row in ready_df.iterrows():
        supplier_id = _normalize_text(row.get("supplier_id", ""))
        supplier_name = supplier_id
        run_id = f"{batch_id}_{supplier_id}" if supplier_id else batch_id
        rows.append(
            {
                "run_id": run_id,
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "row_key": _normalize_text(row.get("backfill_id", "")),
                "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                "barcode": _normalize_text(row.get("barcode", "")),
                "supplier_title": _normalize_text(row.get("supplier_title", "")) or _normalize_text(row.get("amazon_title", "")),
                "unit_cost": _normalize_text(row.get("unit_cost", "")),
                "currency": _normalize_text(row.get("currency", "")) or "GBP",
                "vat_rate": _normalize_text(row.get("vat_rate", "")),
                "scan_status": "pending",
                "scan_reason": "passed_product_page_evidence_backfill",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": observed_utc,
                "completion_block_reason": "",
                "backtrack_original_observed_utc": "",
                "backtrack_attempt_count": "",
            }
        )
    return pd.DataFrame(rows, columns=F061_ACTIVE_RUN_COLUMNS).fillna("")


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


def _build_health(
    *,
    observed_utc: str,
    queue_df: pd.DataFrame,
    f061_df: pd.DataFrame,
    raw_pass_rows: int,
    missing_asin_rows: int,
    skipped_existing_evidence_rows: int,
    pass_paths: list[Path],
    queue_output_path: Path,
) -> pd.DataFrame:
    duplicate_asins = 0
    if not queue_df.empty and "asin" in queue_df.columns:
        duplicate_asins = int(queue_df["asin"].map(_normalize_key).duplicated().sum())
    missing_required_columns = [column for column in BACKFILL_QUEUE_COLUMNS if column not in queue_df.columns]
    missing_barcode_rows = 0
    if not queue_df.empty and "f061_ready_flag" in queue_df.columns:
        missing_barcode_rows = int(queue_df["f061_ready_flag"].map(_normalize_text).ne("1").sum())
    ready_rows = int(len(f061_df.index))
    source_path = pass_paths[0] if pass_paths else Path("")
    rows = [
        _health_row(
            observed_utc=observed_utc,
            check="passed_product_backfill_queue_schema",
            status="fail" if missing_required_columns else "ok",
            value="|".join(missing_required_columns) if missing_required_columns else "present",
            notes="Backfill queue must contain all required columns before any scanner handoff.",
            source_path=queue_output_path,
        ),
        _health_row(
            observed_utc=observed_utc,
            check="passed_product_backfill_duplicate_asin_rows",
            status="fail" if duplicate_asins else "ok",
            value=duplicate_asins,
            notes="Backfill queue should have one row per ASIN.",
            source_path=queue_output_path,
        ),
        _health_row(
            observed_utc=observed_utc,
            check="passed_product_backfill_missing_asin_rows",
            status="warn" if missing_asin_rows else "ok",
            value=missing_asin_rows,
            notes=f"raw_pass_rows={raw_pass_rows};missing ASIN rows are skipped.",
            source_path=source_path,
        ),
        _health_row(
            observed_utc=observed_utc,
            check="passed_product_backfill_existing_evidence_skip_rows",
            status="ok",
            value=skipped_existing_evidence_rows,
            notes="Rows with existing product description, feature bullets, or detail text are skipped.",
            source_path=queue_output_path,
        ),
        _health_row(
            observed_utc=observed_utc,
            check="passed_product_backfill_missing_barcode_rows",
            status="warn" if missing_barcode_rows else "ok",
            value=missing_barcode_rows,
            notes="Rows without barcodes need direct-ASIN handling or supplier canonical repair before F061 barcode mode.",
            source_path=queue_output_path,
        ),
        _health_row(
            observed_utc=observed_utc,
            check="passed_product_backfill_f061_ready_rows",
            status="ok" if ready_rows > 0 or len(queue_df.index) == 0 else "warn",
            value=ready_rows,
            notes=f"queue_rows={len(queue_df.index)};ready rows have barcodes and can be staged for F061.",
            source_path=queue_output_path,
        ),
    ]
    return pd.DataFrame(rows, columns=HEALTH_COLUMNS)


def _build_summary_df(report: dict[str, Any]) -> pd.DataFrame:
    observed_utc = _normalize_text(report.get("observed_utc", ""))
    rows = [
        {"observed_utc": observed_utc, "metric": key, "value": str(value)}
        for key, value in report.items()
        if key not in {"observed_utc", "output_paths"}
    ]
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def _write_markdown_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Passed Product Page Evidence Backfill Queue",
        "",
        f"- Observed UTC: `{_normalize_text(report.get('observed_utc', ''))}`",
        f"- Scope: `{_normalize_text(report.get('scope', ''))}`",
        f"- Pass files inspected: `{report.get('pass_files_inspected', 0)}`",
        f"- Raw pass rows read: `{report.get('raw_pass_rows', 0)}`",
        f"- Unique pass ASINs before evidence skip: `{report.get('unique_pass_asins_before_skip', 0)}`",
        f"- Existing evidence skip rows: `{report.get('skipped_existing_evidence_rows', 0)}`",
        f"- Queue rows: `{report.get('queue_rows', 0)}`",
        f"- F061 ready rows: `{report.get('f061_ready_rows', 0)}`",
        f"- Missing barcode rows: `{report.get('missing_barcode_rows', 0)}`",
        "",
        "## Output Paths",
    ]
    output_paths = report.get("output_paths", {})
    if isinstance(output_paths, dict):
        for label, value in output_paths.items():
            lines.append(f"- {label}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_passed_product_page_evidence_backfill_queue(
    *,
    root: Path | None = None,
    scope: str = "latest",
    limit: int | None = None,
    observed_utc: str | None = None,
    analysis_dir: Path | None = None,
    supplier_inbox_dir: Path | None = None,
    scrape_evidence_path: Path | None = None,
    queue_output_path: Path | None = None,
    f061_output_path: Path | None = None,
    health_output_path: Path | None = None,
    summary_output_path: Path | None = None,
    report_output_path: Path | None = None,
) -> PassedProductBackfillResult:
    root_path = Path(root) if root is not None else ROOT
    observed = observed_utc or _utc_now_iso()
    normalized_scope = _normalize_text(scope).lower() or "latest"
    batch_id = f"passed_page_evidence_backfill_{observed.replace('-', '').replace(':', '').replace('Z', 'Z')}"
    analysis_root = Path(analysis_dir) if analysis_dir is not None else root_path / "out" / "analysis_reports"
    supplier_root = (
        Path(supplier_inbox_dir)
        if supplier_inbox_dir is not None
        else root_path / "out" / "systems" / "F" / "inbox" / "suppliers"
    )
    evidence_path = (
        Path(scrape_evidence_path)
        if scrape_evidence_path is not None
        else root_path / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path
    )
    queue_path = Path(queue_output_path) if queue_output_path is not None else analysis_root / DEFAULT_QUEUE_OUTPUT_PATH.name
    f061_path = Path(f061_output_path) if f061_output_path is not None else analysis_root / DEFAULT_F061_OUTPUT_PATH.name
    health_path = Path(health_output_path) if health_output_path is not None else analysis_root / DEFAULT_HEALTH_OUTPUT_PATH.name
    summary_path = Path(summary_output_path) if summary_output_path is not None else analysis_root / DEFAULT_SUMMARY_OUTPUT_PATH.name
    report_path = Path(report_output_path) if report_output_path is not None else analysis_root / DEFAULT_REPORT_OUTPUT_PATH.name

    pass_paths = _pass_review_paths(analysis_root, normalized_scope)
    pass_df, raw_pass_rows = _load_pass_rows(pass_paths)
    missing_asin_rows = 0
    if not pass_df.empty:
        asin_series = pass_df["asin"].map(_normalize_key) if "asin" in pass_df.columns else pd.Series([""] * len(pass_df.index))
        missing_asin_rows = int(asin_series.eq("").sum())

    supplier_df = _load_supplier_catalog(supplier_root)
    enriched_pass_df = _merge_supplier_catalog(pass_df, supplier_df)
    queue_before_skip = _dedupe_pass_rows(enriched_pass_df, observed, batch_id, normalized_scope)
    evidence_by_asin = _existing_page_evidence_by_asin(evidence_path)
    queue_df, skipped_existing = _apply_existing_evidence_skip(queue_before_skip, evidence_by_asin)
    if limit is not None and int(limit) >= 0:
        queue_df = queue_df.head(int(limit)).copy().reset_index(drop=True)
    f061_df = _build_f061_active_run(queue_df, observed, batch_id)
    health_df = _build_health(
        observed_utc=observed,
        queue_df=queue_df,
        f061_df=f061_df,
        raw_pass_rows=raw_pass_rows,
        missing_asin_rows=missing_asin_rows,
        skipped_existing_evidence_rows=skipped_existing,
        pass_paths=pass_paths,
        queue_output_path=queue_path,
    )

    missing_barcode_rows = (
        int(queue_df["f061_ready_flag"].map(_normalize_text).ne("1").sum())
        if not queue_df.empty and "f061_ready_flag" in queue_df.columns
        else 0
    )
    report = {
        "observed_utc": observed,
        "scope": normalized_scope,
        "limit": "" if limit is None else int(limit),
        "pass_files_inspected": len(pass_paths),
        "raw_pass_rows": raw_pass_rows,
        "missing_asin_rows": missing_asin_rows,
        "unique_pass_asins_before_skip": int(len(queue_before_skip.index)),
        "skipped_existing_evidence_rows": skipped_existing,
        "queue_rows": int(len(queue_df.index)),
        "f061_ready_rows": int(len(f061_df.index)),
        "missing_barcode_rows": missing_barcode_rows,
        "health_fail_rows": int(health_df["status"].map(_normalize_text).str.lower().eq("fail").sum()),
        "health_warn_rows": int(health_df["status"].map(_normalize_text).str.lower().eq("warn").sum()),
        "output_paths": {
            "queue": str(queue_path),
            "f061_active_run": str(f061_path),
            "health": str(health_path),
            "summary": str(summary_path),
            "report": str(report_path),
        },
    }
    summary_df = _build_summary_df(report)

    _write_csv(queue_path, queue_df, BACKFILL_QUEUE_COLUMNS)
    _write_csv(f061_path, f061_df, F061_ACTIVE_RUN_COLUMNS)
    _write_csv(health_path, health_df, HEALTH_COLUMNS)
    _write_csv(summary_path, summary_df, SUMMARY_COLUMNS)
    _write_markdown_report(report_path, report)

    return PassedProductBackfillResult(
        queue_df=queue_df,
        f061_active_run_df=f061_df,
        health_df=health_df,
        summary_df=summary_df,
        report=report,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a scanner-ready queue for passed products missing Amazon page evidence.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--scope", default="latest", choices=["latest", "historical", "all"])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--observed-utc", default=None)
    parser.add_argument("--analysis-dir", default=None)
    parser.add_argument("--supplier-inbox-dir", default=None)
    parser.add_argument("--scrape-evidence-path", default=None)
    parser.add_argument("--queue-output-path", default=None)
    parser.add_argument("--f061-output-path", default=None)
    parser.add_argument("--health-output-path", default=None)
    parser.add_argument("--summary-output-path", default=None)
    parser.add_argument("--report-output-path", default=None)
    args = parser.parse_args()

    result = build_passed_product_page_evidence_backfill_queue(
        root=Path(args.root) if args.root else None,
        scope=args.scope,
        limit=args.limit,
        observed_utc=args.observed_utc,
        analysis_dir=Path(args.analysis_dir) if args.analysis_dir else None,
        supplier_inbox_dir=Path(args.supplier_inbox_dir) if args.supplier_inbox_dir else None,
        scrape_evidence_path=Path(args.scrape_evidence_path) if args.scrape_evidence_path else None,
        queue_output_path=Path(args.queue_output_path) if args.queue_output_path else None,
        f061_output_path=Path(args.f061_output_path) if args.f061_output_path else None,
        health_output_path=Path(args.health_output_path) if args.health_output_path else None,
        summary_output_path=Path(args.summary_output_path) if args.summary_output_path else None,
        report_output_path=Path(args.report_output_path) if args.report_output_path else None,
    )
    print(json.dumps(result.report, indent=2, sort_keys=True))
    return 1 if int(result.report.get("health_fail_rows", 0)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
