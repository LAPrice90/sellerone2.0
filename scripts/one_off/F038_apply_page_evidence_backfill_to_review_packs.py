from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


DEFAULT_BACKFILL_RESULTS_PATH = (
    ROOT / "out" / "systems" / "F" / "page_evidence_backfill" / "page_evidence_backfill_results.csv"
)
DEFAULT_REVIEW_PACK_PATHS = [
    ROOT / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv",
    ROOT / "out" / "analysis_reports" / "f_live_price_file_near_miss_review_latest.csv",
]
DEFAULT_OUTPUT_DIR = ROOT / "out" / "systems" / "F" / "page_evidence_backfill"
DEFAULT_PROOF_DIR = ROOT / "out" / "proof"
DEFAULT_BACKUP_DIR = ROOT / "out" / "backups"

TARGET_TO_SOURCE_FIELDS = {
    "amazon_product_detail_text": "product_detail_text",
    "amazon_product_description": "product_description",
    "amazon_feature_bullets": "product_feature_bullets",
}

MANIFEST_COLUMNS = [
    "observed_utc",
    "mode",
    "status",
    "review_pack_path",
    "preview_path",
    "backup_path",
    "target_rows",
    "source_rows",
    "usable_source_rows",
    "matched_rows",
    "updated_rows",
    "updated_cells",
    "already_had_text_rows",
    "no_match_rows",
    "notes",
]

HEALTH_COLUMNS = [
    "check",
    "status",
    "value",
    "notes",
    "observed_utc",
    "source_path",
]


@dataclass(frozen=True)
class RefreshResult:
    status: str
    mode: str
    manifest_path: str
    health_path: str
    review_pack_count: int
    updated_rows: int
    updated_cells: int
    backup_dir: str
    proof_dir: str
    notes: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _timestamp_slug(observed_utc: str) -> str:
    return datetime.strptime(observed_utc, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y%m%dT%H%M%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _write_csv(path: Path, df: pd.DataFrame, columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy().fillna("")
    if columns is not None:
        for column in columns:
            if column not in out.columns:
                out[column] = ""
        out = out[columns]
    out.to_csv(path, index=False)


def _has_backfill_page_text(record: dict[str, str]) -> bool:
    return any(_normalize_text(record.get(source_field, "")) for source_field in TARGET_TO_SOURCE_FIELDS.values())


def _build_backfill_indexes(backfill_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[tuple[str, str], dict[str, str]], dict[str, dict[str, str]]]:
    if backfill_df.empty:
        return pd.DataFrame(), {}, {}
    work = backfill_df.copy().fillna("")
    for column in [
        "observed_utc",
        "backfill_status",
        "page_evidence_captured_flag",
        "supplier_sku",
        "asin",
        "resolved_asin",
        *TARGET_TO_SOURCE_FIELDS.values(),
    ]:
        if column not in work.columns:
            work[column] = ""
    work = work.loc[
        (work["backfill_status"].map(lambda value: _normalize_text(value).lower()) == "succeeded")
        & (work["page_evidence_captured_flag"].map(_normalize_text) == "1")
    ].copy()
    if work.empty:
        return work, {}, {}
    work["effective_asin"] = work.apply(
        lambda row: _normalize_text(row.get("resolved_asin", "")) or _normalize_text(row.get("asin", "")),
        axis=1,
    )
    work = work.loc[
        work.apply(
            lambda row: _normalize_text(row.get("effective_asin", "")) != ""
            and _has_backfill_page_text({column: _normalize_text(row.get(column, "")) for column in work.columns}),
            axis=1,
        )
    ].copy()
    if work.empty:
        return work, {}, {}
    work["_observed_ts"] = pd.to_datetime(work["observed_utc"], errors="coerce", utc=True, format="mixed")
    work = work.sort_values("_observed_ts", ascending=False, kind="stable")

    by_supplier_asin: dict[tuple[str, str], dict[str, str]] = {}
    by_asin: dict[str, dict[str, str]] = {}
    for _, row in work.iterrows():
        record = {column: _normalize_text(value) for column, value in row.to_dict().items()}
        asin = _normalize_key(record.get("effective_asin", ""))
        supplier_sku = _normalize_key(record.get("supplier_sku", ""))
        if supplier_sku and asin:
            by_supplier_asin.setdefault((supplier_sku, asin), record)
        if asin:
            by_asin.setdefault(asin, record)
    return work, by_supplier_asin, by_asin


def _lookup_backfill(
    row: dict[str, str],
    by_supplier_asin: dict[tuple[str, str], dict[str, str]],
    by_asin: dict[str, dict[str, str]],
) -> dict[str, str]:
    asin = _normalize_key(row.get("asin", ""))
    supplier_sku = _normalize_key(row.get("supplier_sku", ""))
    if supplier_sku and asin and (supplier_sku, asin) in by_supplier_asin:
        return by_supplier_asin[(supplier_sku, asin)]
    if asin and asin in by_asin:
        return by_asin[asin]
    return {}


def _refresh_pack_df(
    pack_df: pd.DataFrame,
    *,
    by_supplier_asin: dict[tuple[str, str], dict[str, str]],
    by_asin: dict[str, dict[str, str]],
) -> tuple[pd.DataFrame, dict[str, int]]:
    out = pack_df.copy().fillna("")
    for target_field in TARGET_TO_SOURCE_FIELDS:
        if target_field not in out.columns:
            out[target_field] = ""

    matched_rows = 0
    updated_rows = 0
    updated_cells = 0
    already_had_text_rows = 0
    no_match_rows = 0

    for idx, row in out.iterrows():
        record = {column: _normalize_text(value) for column, value in row.to_dict().items()}
        backfill = _lookup_backfill(record, by_supplier_asin, by_asin)
        if not backfill:
            no_match_rows += 1
            continue
        matched_rows += 1
        row_updated = False
        row_already_had_text = False
        for target_field, source_field in TARGET_TO_SOURCE_FIELDS.items():
            existing_text = _normalize_text(out.at[idx, target_field])
            source_text = _normalize_text(backfill.get(source_field, ""))
            if existing_text:
                row_already_had_text = True
                continue
            if source_text:
                out.at[idx, target_field] = source_text
                row_updated = True
                updated_cells += 1
        if row_updated:
            updated_rows += 1
        elif row_already_had_text:
            already_had_text_rows += 1

    return out, {
        "matched_rows": matched_rows,
        "updated_rows": updated_rows,
        "updated_cells": updated_cells,
        "already_had_text_rows": already_had_text_rows,
        "no_match_rows": no_match_rows,
    }


def _backup_pack(path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / path.name
    shutil.copy2(path, backup_path)
    return backup_path


def _health_row(
    *,
    check: str,
    status: str,
    value: object,
    notes: str,
    observed_utc: str,
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


def apply_page_evidence_backfill_to_review_packs(
    *,
    backfill_results_path: Path = DEFAULT_BACKFILL_RESULTS_PATH,
    review_pack_paths: list[Path] | None = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    proof_base_dir: Path = DEFAULT_PROOF_DIR,
    backup_base_dir: Path = DEFAULT_BACKUP_DIR,
    observed_utc: str | None = None,
    execute: bool = False,
) -> RefreshResult:
    observed = observed_utc or _utc_now_iso()
    slug = _timestamp_slug(observed)
    mode = "execute" if execute else "dry_run"
    output_dir.mkdir(parents=True, exist_ok=True)
    proof_dir = proof_base_dir / f"f038_review_pack_page_evidence_refresh_{slug}"
    proof_dir.mkdir(parents=True, exist_ok=True)
    backup_dir = backup_base_dir / f"f038_review_pack_page_evidence_refresh_{slug}"
    target_paths = review_pack_paths or DEFAULT_REVIEW_PACK_PATHS

    backfill_df = _read_csv(backfill_results_path)
    usable_backfill_df, by_supplier_asin, by_asin = _build_backfill_indexes(backfill_df)
    manifest_rows: list[dict[str, str]] = []
    health_rows: list[dict[str, str]] = []
    total_updated_rows = 0
    total_updated_cells = 0
    status = "ok"

    health_rows.append(
        _health_row(
            check="review_pack_page_evidence_refresh_health_schema",
            status="ok",
            value="present",
            notes="health output uses fixed columns",
            observed_utc=observed,
            source_path=output_dir / "review_pack_page_evidence_refresh_health.csv",
        )
    )
    health_rows.append(
        _health_row(
            check="review_pack_page_evidence_backfill_usable_rows",
            status="ok" if len(usable_backfill_df.index) > 0 else "warn",
            value=len(usable_backfill_df.index),
            notes=f"source_rows={len(backfill_df.index)}",
            observed_utc=observed,
            source_path=backfill_results_path,
        )
    )

    for target_path in target_paths:
        pack_df = _read_csv(target_path)
        preview_path = proof_dir / target_path.name
        backup_path_text = ""
        if pack_df.empty:
            manifest_rows.append(
                {
                    "observed_utc": observed,
                    "mode": mode,
                    "status": "skipped_empty_or_missing",
                    "review_pack_path": str(target_path),
                    "preview_path": "",
                    "backup_path": "",
                    "target_rows": "0",
                    "source_rows": str(len(backfill_df.index)),
                    "usable_source_rows": str(len(usable_backfill_df.index)),
                    "matched_rows": "0",
                    "updated_rows": "0",
                    "updated_cells": "0",
                    "already_had_text_rows": "0",
                    "no_match_rows": "0",
                    "notes": "target pack missing or empty",
                }
            )
            health_rows.append(
                _health_row(
                    check=f"review_pack_page_evidence_refresh:{target_path.name}",
                    status="warn",
                    value="skipped_empty_or_missing",
                    notes="target pack missing or empty",
                    observed_utc=observed,
                    source_path=target_path,
                )
            )
            continue

        refreshed_df, counts = _refresh_pack_df(pack_df, by_supplier_asin=by_supplier_asin, by_asin=by_asin)
        _write_csv(preview_path, refreshed_df, list(refreshed_df.columns))
        if execute and counts["updated_rows"] > 0:
            backup_path_text = str(_backup_pack(target_path, backup_dir))
            _write_csv(target_path, refreshed_df, list(refreshed_df.columns))

        total_updated_rows += counts["updated_rows"]
        total_updated_cells += counts["updated_cells"]
        row_status = "updated" if counts["updated_rows"] > 0 else "no_changes"
        manifest_rows.append(
            {
                "observed_utc": observed,
                "mode": mode,
                "status": row_status,
                "review_pack_path": str(target_path),
                "preview_path": str(preview_path),
                "backup_path": backup_path_text,
                "target_rows": str(len(pack_df.index)),
                "source_rows": str(len(backfill_df.index)),
                "usable_source_rows": str(len(usable_backfill_df.index)),
                "matched_rows": str(counts["matched_rows"]),
                "updated_rows": str(counts["updated_rows"]),
                "updated_cells": str(counts["updated_cells"]),
                "already_had_text_rows": str(counts["already_had_text_rows"]),
                "no_match_rows": str(counts["no_match_rows"]),
                "notes": "filled blank page evidence fields only",
            }
        )
        health_rows.append(
            _health_row(
                check=f"review_pack_page_evidence_refresh:{target_path.name}",
                status="ok",
                value=row_status,
                notes=json.dumps(counts, sort_keys=True),
                observed_utc=observed,
                source_path=target_path,
            )
        )

    if execute and total_updated_rows > 0 and not backup_dir.exists():
        status = "fail"
        health_rows.append(
            _health_row(
                check="review_pack_page_evidence_refresh_backup_created",
                status="fail",
                value="missing",
                notes="execute mode updated rows but backup dir is missing",
                observed_utc=observed,
                source_path=backup_dir,
            )
        )
    else:
        health_rows.append(
            _health_row(
                check="review_pack_page_evidence_refresh_backup_created",
                status="ok",
                value=str(backup_dir.exists()) if execute and total_updated_rows > 0 else "not_required",
                notes="backup required only when execute mode writes updates",
                observed_utc=observed,
                source_path=backup_dir,
            )
        )

    manifest_path = output_dir / "review_pack_page_evidence_refresh_manifest.csv"
    health_path = output_dir / "review_pack_page_evidence_refresh_health.csv"
    manifest_df = pd.DataFrame(manifest_rows, columns=MANIFEST_COLUMNS)
    health_df = pd.DataFrame(health_rows, columns=HEALTH_COLUMNS)
    _write_csv(manifest_path, manifest_df, MANIFEST_COLUMNS)
    _write_csv(health_path, health_df, HEALTH_COLUMNS)

    return RefreshResult(
        status=status,
        mode=mode,
        manifest_path=str(manifest_path),
        health_path=str(health_path),
        review_pack_count=len(target_paths),
        updated_rows=total_updated_rows,
        updated_cells=total_updated_cells,
        backup_dir=str(backup_dir),
        proof_dir=str(proof_dir),
        notes="filled blank review-pack page evidence fields from successful backfill rows",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fill blank New Product Review page evidence fields from F037 backfill results.")
    parser.add_argument("--backfill-results-path", type=Path, default=DEFAULT_BACKFILL_RESULTS_PATH)
    parser.add_argument("--review-pack-path", type=Path, action="append", default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--proof-base-dir", type=Path, default=DEFAULT_PROOF_DIR)
    parser.add_argument("--backup-base-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    parser.add_argument("--observed-utc", default="")
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = apply_page_evidence_backfill_to_review_packs(
        backfill_results_path=args.backfill_results_path,
        review_pack_paths=args.review_pack_path,
        output_dir=args.output_dir,
        proof_base_dir=args.proof_base_dir,
        backup_base_dir=args.backup_base_dir,
        observed_utc=_normalize_text(args.observed_utc) or None,
        execute=bool(args.execute),
    )
    print(json.dumps(result.__dict__, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
