from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"
IDENTITY_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "hf_learning_identity_bridge_latest.csv"
ASSUMPTION_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "hf_learning_assumption_snapshots_latest.csv"
METRICS_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "hf_learning_foundation_metrics_latest.csv"

SCREENING_PATH = ROOT / "out" / "systems" / "F" / "live" / "f_screening_row_state_live.csv"
QUEUE_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_approval_queue_live.csv"
DECISIONS_PATH = ROOT / "out" / "systems" / "F" / "history" / "feeder_approval_decisions_log.csv"
HANDOFF_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_po_handoff_ready_live.csv"
RECOMMENDATION_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_candidate_recommendations_live.csv"
LEGACY_EVIDENCE_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv"
LISTING_SNAPSHOT_PATH = ROOT / "out" / "listing_offer_snapshot_latest.csv"
LISTING_HISTORY_PATH = ROOT / "out" / "listing_offer_history.csv"
MERCHANT_LISTINGS_PATH = ROOT / "out" / "merchant_listings_latest.csv"
PRODUCT_DB_PREVIEW_PATH = ROOT / "out" / "product_db_preview.csv"
SKU_SUMMARY_PATH = ROOT / "out" / "sku_performance_summary.csv"

IDENTITY_SOURCE_STALE_DAYS_DEFAULT = 7

REQUIRED_INPUTS = [
    SCREENING_PATH,
    QUEUE_PATH,
    DECISIONS_PATH,
    HANDOFF_PATH,
    RECOMMENDATION_PATH,
    LISTING_SNAPSHOT_PATH,
    SKU_SUMMARY_PATH,
]

IDENTITY_COLUMNS = [
    "snapshot_utc",
    "candidate_id",
    "feeder_candidate_id",
    "supplier_id",
    "supplier_sku",
    "asin",
    "sku",
    "sku_resolution_status",
    "sku_resolution_source",
    "asin_value_count",
    "supplier_sku_value_count",
    "asin_conflict_flag",
    "supplier_sku_conflict_flag",
    "source_screening_flag",
    "source_recommendation_flag",
    "source_queue_flag",
    "source_decision_flag",
    "source_handoff_flag",
    "source_event_count",
    "latest_source_utc",
    "latest_source_name",
]

ASSUMPTION_COLUMNS = [
    "snapshot_utc",
    "candidate_id",
    "feeder_candidate_id",
    "supplier_id",
    "supplier_sku",
    "asin",
    "snapshot_stage",
    "assumption_anchor_utc",
    "assumption_anchor_source",
    "in_scope_approval_decision_flag",
    "recommendation_status",
    "recommended_test_qty",
    "estimated_roi_pct",
    "estimated_margin_gbp",
    "estimated_demand",
    "decision_action",
    "final_decision_status",
    "decision_source",
    "actor",
    "decision_utc",
    "handoff_utc",
    "source_row_hash",
    "source_file_path",
    "source_seen_at_utc",
]


@dataclass(frozen=True)
class FoundationBuildResult:
    identity_path: Path
    identity_rows: int
    assumption_path: Path
    assumption_rows: int
    metrics_path: Path
    decision_scope_rows: int
    decision_scope_snapshot_rows: int
    resolved_sku_rows: int
    unresolved_sku_rows: int


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _safe_int(value: object, default: int = 0) -> int:
    text = _normalize_text(value)
    if text == "":
        return int(default)
    try:
        return int(float(text))
    except Exception:
        return int(default)


def _parse_utc(value: object) -> datetime | None:
    text = _normalize_text(value)
    if text == "":
        return None
    normalized = text.replace("Z", "+00:00") if text.endswith("Z") else text
    try:
        dt = datetime.fromisoformat(normalized)
    except Exception:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _norm_frame(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    out = df.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = ""
    out = out[[*columns]]
    for column in out.columns:
        out[column] = out[column].map(_normalize_text)
    return out


def _column_as_text(df: pd.DataFrame, column: str) -> pd.Series:
    if column in df.columns:
        return df[column].map(_normalize_text)
    return pd.Series([""] * len(df.index), index=df.index, dtype=str)


def _read_csv_required(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"required phase-0 input missing: {path}")
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _read_csv_optional(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _build_latest_value_map(
    df: pd.DataFrame,
    *,
    key_col: str,
    value_col: str,
    ts_col: str,
) -> dict[str, str]:
    if df.empty:
        return {}
    work = pd.DataFrame()
    work["key"] = _column_as_text(df, key_col)
    work["value"] = _column_as_text(df, value_col)
    work["event_utc"] = _column_as_text(df, ts_col)
    work = work[(work["key"] != "") & (work["value"] != "")].copy()
    if work.empty:
        return {}
    work = work.sort_values(["key", "event_utc"], ascending=[True, False], kind="stable")
    latest = work.drop_duplicates(subset=["key"], keep="first")
    return {row["key"]: row["value"] for _, row in latest.iterrows()}


def _build_unique_values_map(
    df: pd.DataFrame,
    *,
    key_col: str,
    value_col: str,
) -> dict[str, list[str]]:
    if df.empty:
        return {}
    work = pd.DataFrame()
    work["key"] = _column_as_text(df, key_col)
    work["value"] = _column_as_text(df, value_col)
    work = work[(work["key"] != "") & (work["value"] != "")].copy()
    if work.empty:
        return {}
    grouped = work.groupby("key")["value"].apply(list)
    return {str(key): _non_empty_unique(values) for key, values in grouped.items()}


def _event_frame(
    df: pd.DataFrame,
    *,
    source_name: str,
    source_rank: int,
    ts_col: str,
    candidate_col: str = "candidate_id",
    feeder_col: str = "feeder_candidate_id",
    supplier_id_col: str = "supplier_id",
    supplier_sku_col: str = "supplier_sku",
    asin_col: str = "asin",
) -> pd.DataFrame:
    work = pd.DataFrame()
    work["candidate_id"] = _column_as_text(df, candidate_col)
    work["feeder_candidate_id"] = _column_as_text(df, feeder_col)
    work["supplier_id"] = _column_as_text(df, supplier_id_col)
    work["supplier_sku"] = _column_as_text(df, supplier_sku_col)
    work["asin"] = _column_as_text(df, asin_col)
    work["source_name"] = source_name
    work["source_rank"] = source_rank
    work["event_utc"] = _column_as_text(df, ts_col)
    work = work[work["candidate_id"] != ""].copy()
    return work


def _latest_by(df: pd.DataFrame, key: str, ts_col: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    work[key] = _column_as_text(work, key)
    work[ts_col] = _column_as_text(work, ts_col)
    work = work[work[key] != ""].copy()
    if work.empty:
        return work
    work = work.sort_values([key, ts_col], ascending=[True, False], kind="stable")
    return work.drop_duplicates(subset=[key], keep="first")


def _first_non_empty(values: Iterable[object]) -> str:
    for value in values:
        text = _normalize_text(value)
        if text != "":
            return text
    return ""


def _non_empty_unique(values: Iterable[object]) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _normalize_text(value)
        if text == "" or text in seen:
            continue
        seen.add(text)
        items.append(text)
    return items


def _h_scope_pairs_from_frame(df: pd.DataFrame, *, asin_col: str, sku_col: str) -> list[tuple[str, str]]:
    if df.empty or asin_col not in df.columns or sku_col not in df.columns:
        return []
    work = pd.DataFrame()
    work["asin"] = _column_as_text(df, asin_col)
    work["sku"] = _column_as_text(df, sku_col)
    work = work[(work["asin"] != "") & (work["sku"] != "")].copy()
    if work.empty:
        return []
    work = work.drop_duplicates(subset=["asin", "sku"], keep="last")
    return [(str(row["asin"]), str(row["sku"])) for _, row in work.iterrows()]


def _build_h_scope_asin_map(
    *,
    listing_df: pd.DataFrame,
    listing_history_df: pd.DataFrame,
    merchant_listings_df: pd.DataFrame,
    product_db_preview_df: pd.DataFrame,
) -> tuple[dict[str, list[str]], dict[str, int]]:
    source_specs: list[tuple[str, pd.DataFrame, str, str]] = [
        ("listing_snapshot", listing_df, "asin", "sku"),
        ("listing_history", listing_history_df, "asin", "sku"),
        ("merchant_listings", merchant_listings_df, "asin1", "seller-sku"),
        ("product_db_preview", product_db_preview_df, "asin", "seller_sku"),
    ]
    asin_to_skus: dict[str, list[str]] = {}
    source_pair_counts: dict[str, int] = {}
    for source_name, frame, asin_col, sku_col in source_specs:
        pairs = _h_scope_pairs_from_frame(frame, asin_col=asin_col, sku_col=sku_col)
        source_pair_counts[source_name] = int(len(pairs))
        for asin, sku in pairs:
            existing = asin_to_skus.get(asin, [])
            if sku in existing:
                continue
            asin_to_skus[asin] = [*existing, sku]
    return asin_to_skus, source_pair_counts


def _build_identity_bridge(
    *,
    screening_df: pd.DataFrame,
    queue_df: pd.DataFrame,
    decisions_df: pd.DataFrame,
    handoff_df: pd.DataFrame,
    recommendation_df: pd.DataFrame,
    legacy_evidence_df: pd.DataFrame,
    listing_df: pd.DataFrame,
    listing_history_df: pd.DataFrame | None = None,
    merchant_listings_df: pd.DataFrame | None = None,
    product_db_preview_df: pd.DataFrame | None = None,
    snapshot_utc: str,
) -> pd.DataFrame:
    events = pd.concat(
        [
            _event_frame(screening_df, source_name="screening", source_rank=50, ts_col="observed_utc"),
            _event_frame(recommendation_df, source_name="recommendation", source_rank=40, ts_col="recommendation_utc"),
            _event_frame(queue_df, source_name="approval_queue", source_rank=30, ts_col="queue_utc"),
            _event_frame(decisions_df, source_name="approval_decision", source_rank=20, ts_col="decision_utc"),
            _event_frame(handoff_df, source_name="po_handoff", source_rank=60, ts_col="handoff_utc"),
        ],
        ignore_index=True,
    )

    events = events[events["candidate_id"] != ""].copy()
    if events.empty:
        return pd.DataFrame(columns=IDENTITY_COLUMNS)

    events = events.sort_values(
        ["candidate_id", "source_rank", "event_utc"],
        ascending=[True, False, False],
        kind="stable",
    )

    asin_to_skus, _ = _build_h_scope_asin_map(
        listing_df=listing_df,
        listing_history_df=listing_history_df if listing_history_df is not None else pd.DataFrame(),
        merchant_listings_df=merchant_listings_df if merchant_listings_df is not None else pd.DataFrame(),
        product_db_preview_df=product_db_preview_df if product_db_preview_df is not None else pd.DataFrame(),
    )
    snapshot_dt = _parse_utc(snapshot_utc)
    stale_days = max(
        _safe_int(os.environ.get("HF_IDENTITY_SOURCE_STALE_DAYS", str(IDENTITY_SOURCE_STALE_DAYS_DEFAULT))),
        1,
    )

    candidate_to_legacy_asin = _build_latest_value_map(
        legacy_evidence_df,
        key_col="candidate_id",
        value_col="asin",
        ts_col="observed_utc",
    )
    supplier_sku_to_legacy_asins = _build_unique_values_map(
        legacy_evidence_df,
        key_col="supplier_sku",
        value_col="asin",
    )

    rows: list[dict[str, str]] = []
    for candidate_id, group in events.groupby("candidate_id", sort=True):
        candidate_id_text = _normalize_text(candidate_id)
        latest_row = group.iloc[0]
        asins = _non_empty_unique(group["asin"].tolist())
        supplier_skus = _non_empty_unique(group["supplier_sku"].tolist())
        feeder_candidate_id = _first_non_empty(group["feeder_candidate_id"].tolist())
        supplier_id = _first_non_empty(group["supplier_id"].tolist())
        supplier_sku = _first_non_empty(group["supplier_sku"].tolist())

        asin_source = "event"
        if len(asins) == 0:
            legacy_candidate_asin = candidate_to_legacy_asin.get(candidate_id_text, "")
            if legacy_candidate_asin != "":
                asins = [legacy_candidate_asin]
                asin_source = "legacy_candidate"
            else:
                legacy_supplier_asins = supplier_sku_to_legacy_asins.get(supplier_sku, [])
                if len(legacy_supplier_asins) > 0:
                    asins = legacy_supplier_asins
                    asin_source = "legacy_supplier_sku"

        asin = asins[0] if asins else ""
        latest_source_utc = _normalize_text(latest_row.get("event_utc", ""))

        if len(asins) == 0:
            sku = ""
            latest_source_dt = _parse_utc(latest_source_utc)
            if (
                latest_source_dt is not None
                and snapshot_dt is not None
                and latest_source_dt <= (snapshot_dt - timedelta(days=stale_days))
            ):
                sku_status = "UNRESOLVED_NO_ASIN_SOURCE_STALE"
            else:
                sku_status = "UNRESOLVED_NO_ASIN"
        elif len(asins) > 1:
            sku = ""
            sku_status = "UNRESOLVED_MULTI_ASIN"
        else:
            matched_skus = asin_to_skus.get(asin, [])
            if len(matched_skus) == 1:
                sku = matched_skus[0]
                sku_status = "RESOLVED_FROM_H_SNAPSHOT"
            elif len(matched_skus) > 1:
                sku = ""
                sku_status = "UNRESOLVED_AMBIGUOUS_ASIN"
            else:
                sku = ""
                sku_status = "UNRESOLVED_ASIN_NOT_IN_H_SCOPE"

        source_names = set(group["source_name"].tolist())
        rows.append(
            {
                "snapshot_utc": snapshot_utc,
                "candidate_id": _normalize_text(candidate_id),
                "feeder_candidate_id": feeder_candidate_id,
                "supplier_id": supplier_id,
                "supplier_sku": supplier_sku,
                "asin": asin,
                "sku": sku,
                "sku_resolution_status": sku_status,
                "sku_resolution_source": asin_source,
                "asin_value_count": str(len(asins)),
                "supplier_sku_value_count": str(len(supplier_skus)),
                "asin_conflict_flag": "1" if len(asins) > 1 else "0",
                "supplier_sku_conflict_flag": "1" if len(supplier_skus) > 1 else "0",
                "source_screening_flag": "1" if "screening" in source_names else "0",
                "source_recommendation_flag": "1" if "recommendation" in source_names else "0",
                "source_queue_flag": "1" if "approval_queue" in source_names else "0",
                "source_decision_flag": "1" if "approval_decision" in source_names else "0",
                "source_handoff_flag": "1" if "po_handoff" in source_names else "0",
                "source_event_count": str(len(group.index)),
                "latest_source_utc": latest_source_utc,
                "latest_source_name": _normalize_text(latest_row.get("source_name", "")),
            }
        )

    out = pd.DataFrame(rows)
    return _norm_frame(out, IDENTITY_COLUMNS).sort_values(["candidate_id"], kind="stable")


def _build_assumption_snapshots(
    *,
    queue_df: pd.DataFrame,
    decisions_df: pd.DataFrame,
    handoff_df: pd.DataFrame,
    recommendation_df: pd.DataFrame,
    snapshot_utc: str,
) -> pd.DataFrame:
    queue_latest = _latest_by(queue_df, "candidate_id", "queue_utc")
    decision_latest = _latest_by(decisions_df, "candidate_id", "decision_utc")
    handoff_latest = _latest_by(handoff_df, "candidate_id", "handoff_utc")
    recommendation_latest = _latest_by(recommendation_df, "candidate_id", "recommendation_utc")

    keys = set(queue_latest.get("candidate_id", pd.Series([], dtype=str)).tolist())
    keys.update(decision_latest.get("candidate_id", pd.Series([], dtype=str)).tolist())
    keys.update(handoff_latest.get("candidate_id", pd.Series([], dtype=str)).tolist())
    keys.update(recommendation_latest.get("candidate_id", pd.Series([], dtype=str)).tolist())
    keys = {key for key in keys if _normalize_text(key) != ""}

    queue_map = {row["candidate_id"]: row for _, row in queue_latest.iterrows()} if not queue_latest.empty else {}
    decision_map = {row["candidate_id"]: row for _, row in decision_latest.iterrows()} if not decision_latest.empty else {}
    handoff_map = {row["candidate_id"]: row for _, row in handoff_latest.iterrows()} if not handoff_latest.empty else {}
    recommendation_map = (
        {row["candidate_id"]: row for _, row in recommendation_latest.iterrows()} if not recommendation_latest.empty else {}
    )

    rows: list[dict[str, str]] = []
    for candidate_id in sorted(keys):
        queue_row = queue_map.get(candidate_id)
        decision_row = decision_map.get(candidate_id)
        handoff_row = handoff_map.get(candidate_id)
        recommendation_row = recommendation_map.get(candidate_id)

        if handoff_row is not None:
            snapshot_stage = "po_handoff"
            anchor_utc = _normalize_text(handoff_row.get("handoff_utc", ""))
            anchor_source = "po_handoff"
            source_row = handoff_row
        elif decision_row is not None:
            snapshot_stage = "approval_decision"
            anchor_utc = _normalize_text(decision_row.get("decision_utc", ""))
            anchor_source = "approval_decision"
            source_row = decision_row
        elif queue_row is not None:
            snapshot_stage = "approval_queue"
            anchor_utc = _normalize_text(queue_row.get("queue_utc", ""))
            anchor_source = "approval_queue"
            source_row = queue_row
        else:
            snapshot_stage = "recommendation_only"
            anchor_utc = _normalize_text(recommendation_row.get("recommendation_utc", "")) if recommendation_row is not None else ""
            anchor_source = "recommendation"
            source_row = recommendation_row

        feeder_candidate_id = _first_non_empty(
            [
                handoff_row.get("feeder_candidate_id", "") if handoff_row is not None else "",
                decision_row.get("feeder_candidate_id", "") if decision_row is not None else "",
                queue_row.get("feeder_candidate_id", "") if queue_row is not None else "",
                recommendation_row.get("feeder_candidate_id", "") if recommendation_row is not None else "",
            ]
        )
        supplier_id = _first_non_empty(
            [
                handoff_row.get("supplier_id", "") if handoff_row is not None else "",
                decision_row.get("supplier_id", "") if decision_row is not None else "",
                queue_row.get("supplier_id", "") if queue_row is not None else "",
                recommendation_row.get("supplier_id", "") if recommendation_row is not None else "",
            ]
        )
        supplier_sku = _first_non_empty(
            [
                handoff_row.get("supplier_sku", "") if handoff_row is not None else "",
                decision_row.get("supplier_sku", "") if decision_row is not None else "",
                queue_row.get("supplier_sku", "") if queue_row is not None else "",
                recommendation_row.get("supplier_sku", "") if recommendation_row is not None else "",
            ]
        )
        asin = _first_non_empty(
            [
                handoff_row.get("asin", "") if handoff_row is not None else "",
                recommendation_row.get("asin", "") if recommendation_row is not None else "",
            ]
        )

        recommended_test_qty = _first_non_empty(
            [
                handoff_row.get("approved_test_qty", "") if handoff_row is not None else "",
                queue_row.get("recommended_test_qty", "") if queue_row is not None else "",
                decision_row.get("recommended_test_qty", "") if decision_row is not None else "",
                recommendation_row.get("recommended_test_qty", "") if recommendation_row is not None else "",
            ]
        )
        recommendation_status = _first_non_empty(
            [
                queue_row.get("recommendation_status", "") if queue_row is not None else "",
                recommendation_row.get("recommendation_status", "") if recommendation_row is not None else "",
                decision_row.get("recommendation_status", "") if decision_row is not None else "",
            ]
        )
        estimated_roi_pct = _first_non_empty(
            [
                queue_row.get("estimated_roi_pct", "") if queue_row is not None else "",
                recommendation_row.get("estimated_roi_pct", "") if recommendation_row is not None else "",
            ]
        )
        estimated_margin_gbp = _first_non_empty(
            [
                queue_row.get("estimated_margin_gbp", "") if queue_row is not None else "",
                recommendation_row.get("estimated_margin_gbp", "") if recommendation_row is not None else "",
            ]
        )
        estimated_demand = _first_non_empty(
            [
                queue_row.get("estimated_demand", "") if queue_row is not None else "",
                recommendation_row.get("estimated_demand", "") if recommendation_row is not None else "",
            ]
        )

        decision_utc = _normalize_text(decision_row.get("decision_utc", "")) if decision_row is not None else ""
        handoff_utc = _normalize_text(handoff_row.get("handoff_utc", "")) if handoff_row is not None else ""
        in_scope_flag = "1" if decision_row is not None else "0"

        rows.append(
            {
                "snapshot_utc": snapshot_utc,
                "candidate_id": _normalize_text(candidate_id),
                "feeder_candidate_id": feeder_candidate_id,
                "supplier_id": supplier_id,
                "supplier_sku": supplier_sku,
                "asin": asin,
                "snapshot_stage": snapshot_stage,
                "assumption_anchor_utc": anchor_utc,
                "assumption_anchor_source": anchor_source,
                "in_scope_approval_decision_flag": in_scope_flag,
                "recommendation_status": recommendation_status,
                "recommended_test_qty": recommended_test_qty,
                "estimated_roi_pct": estimated_roi_pct,
                "estimated_margin_gbp": estimated_margin_gbp,
                "estimated_demand": estimated_demand,
                "decision_action": _normalize_text(decision_row.get("decision_action", "")) if decision_row is not None else "",
                "final_decision_status": _first_non_empty(
                    [
                        _normalize_text(handoff_row.get("final_decision_status", "")) if handoff_row is not None else "",
                        _normalize_text(decision_row.get("final_decision_status", "")) if decision_row is not None else "",
                    ]
                ),
                "decision_source": _normalize_text(decision_row.get("decision_source", "")) if decision_row is not None else "",
                "actor": _normalize_text(decision_row.get("actor", "")) if decision_row is not None else "",
                "decision_utc": decision_utc,
                "handoff_utc": handoff_utc,
                "source_row_hash": _normalize_text(source_row.get("source_row_hash", "")) if source_row is not None else "",
                "source_file_path": _normalize_text(source_row.get("source_file_path", "")) if source_row is not None else "",
                "source_seen_at_utc": _normalize_text(source_row.get("source_seen_at_utc", "")) if source_row is not None else "",
            }
        )

    out = pd.DataFrame(rows)
    return _norm_frame(out, ASSUMPTION_COLUMNS).sort_values(["candidate_id"], kind="stable")


def _ensure_required_inputs() -> None:
    for path in REQUIRED_INPUTS:
        if not path.exists():
            raise FileNotFoundError(f"required phase-0 input missing: {path}")


def _build_foundation_metrics(
    *,
    identity_df: pd.DataFrame,
    assumption_df: pd.DataFrame,
    h_scope_asin_total: int,
    h_scope_pair_counts: dict[str, int],
    snapshot_utc: str,
) -> pd.DataFrame:
    identity_rows = int(len(identity_df.index))
    resolved_rows = int((identity_df["sku_resolution_status"] == "RESOLVED_FROM_H_SNAPSHOT").sum()) if identity_rows else 0
    unresolved_rows = int(identity_rows - resolved_rows)
    asin_present_rows = int((identity_df["asin"] != "").sum()) if identity_rows else 0
    decision_scope_rows = int((assumption_df["in_scope_approval_decision_flag"] == "1").sum()) if not assumption_df.empty else 0
    decision_scope_snapshot_rows = int(
        (
            (assumption_df["in_scope_approval_decision_flag"] == "1")
            & (assumption_df["snapshot_stage"].isin(["approval_decision", "po_handoff"]))
        ).sum()
    ) if not assumption_df.empty else 0

    def _pct(numerator: int, denominator: int) -> str:
        if denominator <= 0:
            return "0.0000"
        return f"{(numerator / denominator):.4f}"

    rows: list[dict[str, str]] = [
        {"snapshot_utc": snapshot_utc, "metric_name": "identity_rows_total", "metric_value": str(identity_rows)},
        {"snapshot_utc": snapshot_utc, "metric_name": "identity_rows_resolved", "metric_value": str(resolved_rows)},
        {"snapshot_utc": snapshot_utc, "metric_name": "identity_rows_unresolved", "metric_value": str(unresolved_rows)},
        {"snapshot_utc": snapshot_utc, "metric_name": "identity_asin_present_rows", "metric_value": str(asin_present_rows)},
        {"snapshot_utc": snapshot_utc, "metric_name": "identity_resolution_rate", "metric_value": _pct(resolved_rows, identity_rows)},
        {"snapshot_utc": snapshot_utc, "metric_name": "identity_asin_present_rate", "metric_value": _pct(asin_present_rows, identity_rows)},
        {"snapshot_utc": snapshot_utc, "metric_name": "assumption_rows_total", "metric_value": str(len(assumption_df.index))},
        {"snapshot_utc": snapshot_utc, "metric_name": "assumption_decision_scope_rows", "metric_value": str(decision_scope_rows)},
        {
            "snapshot_utc": snapshot_utc,
            "metric_name": "assumption_decision_scope_snapshot_rows",
            "metric_value": str(decision_scope_snapshot_rows),
        },
    ]

    identity_with_asin_rows = int((identity_df["asin"] != "").sum()) if identity_rows else 0
    identity_no_asin_rows = int(identity_rows - identity_with_asin_rows)
    identity_no_asin_stale_rows = (
        int((identity_df["sku_resolution_status"] == "UNRESOLVED_NO_ASIN_SOURCE_STALE").sum()) if identity_rows else 0
    )
    in_scope_statuses = {"RESOLVED_FROM_H_SNAPSHOT", "UNRESOLVED_AMBIGUOUS_ASIN"}
    identity_asin_in_h_scope_rows = (
        int(identity_df["sku_resolution_status"].isin(in_scope_statuses).sum()) if identity_rows else 0
    )
    identity_asin_not_in_h_scope_rows = (
        int((identity_df["sku_resolution_status"] == "UNRESOLVED_ASIN_NOT_IN_H_SCOPE").sum()) if identity_rows else 0
    )
    rows.extend(
        [
            {"snapshot_utc": snapshot_utc, "metric_name": "identity_rows_with_asin", "metric_value": str(identity_with_asin_rows)},
            {"snapshot_utc": snapshot_utc, "metric_name": "identity_rows_without_asin", "metric_value": str(identity_no_asin_rows)},
            {
                "snapshot_utc": snapshot_utc,
                "metric_name": "identity_rows_without_asin_source_stale",
                "metric_value": str(identity_no_asin_stale_rows),
            },
            {
                "snapshot_utc": snapshot_utc,
                "metric_name": "identity_rows_asin_in_h_scope",
                "metric_value": str(identity_asin_in_h_scope_rows),
            },
            {
                "snapshot_utc": snapshot_utc,
                "metric_name": "identity_rows_asin_not_in_h_scope",
                "metric_value": str(identity_asin_not_in_h_scope_rows),
            },
            {
                "snapshot_utc": snapshot_utc,
                "metric_name": "identity_asin_h_scope_overlap_rate",
                "metric_value": _pct(identity_asin_in_h_scope_rows, identity_with_asin_rows),
            },
        ]
    )

    source_overlap_pairs = [
        ("screening", "recommendation"),
        ("screening", "approval_queue"),
        ("screening", "approval_decision"),
        ("recommendation", "approval_queue"),
        ("recommendation", "approval_decision"),
        ("approval_queue", "approval_decision"),
    ]
    flag_col = {
        "screening": "source_screening_flag",
        "recommendation": "source_recommendation_flag",
        "approval_queue": "source_queue_flag",
        "approval_decision": "source_decision_flag",
        "po_handoff": "source_handoff_flag",
    }
    for left_name, right_name in source_overlap_pairs:
        left_col = flag_col[left_name]
        right_col = flag_col[right_name]
        if identity_rows and left_col in identity_df.columns and right_col in identity_df.columns:
            left_mask = identity_df[left_col].map(_normalize_text).eq("1")
            right_mask = identity_df[right_col].map(_normalize_text).eq("1")
            overlap_count = int((left_mask & right_mask).sum())
        else:
            overlap_count = 0
        rows.append(
            {
                "snapshot_utc": snapshot_utc,
                "metric_name": f"identity_source_overlap_{left_name}_{right_name}_rows",
                "metric_value": str(overlap_count),
            }
        )

    rows.append(
        {
            "snapshot_utc": snapshot_utc,
            "metric_name": "h_scope_asin_total",
            "metric_value": str(max(int(h_scope_asin_total), 0)),
        }
    )
    for source_name in sorted(h_scope_pair_counts.keys()):
        rows.append(
            {
                "snapshot_utc": snapshot_utc,
                "metric_name": f"h_scope_pair_count:{source_name}",
                "metric_value": str(int(h_scope_pair_counts[source_name])),
            }
        )

    if not identity_df.empty:
        for status_name, count in (
            identity_df.groupby("sku_resolution_status").size().sort_index().items()
        ):
            rows.append(
                {
                    "snapshot_utc": snapshot_utc,
                    "metric_name": f"identity_status_count:{_normalize_text(status_name)}",
                    "metric_value": str(int(count)),
                }
            )
    if not assumption_df.empty:
        for stage_name, count in (
            assumption_df.groupby("snapshot_stage").size().sort_index().items()
        ):
            rows.append(
                {
                    "snapshot_utc": snapshot_utc,
                    "metric_name": f"assumption_stage_count:{_normalize_text(stage_name)}",
                    "metric_value": str(int(count)),
                }
            )

    return pd.DataFrame(rows, columns=["snapshot_utc", "metric_name", "metric_value"]).fillna("")


def build_foundation(
    *,
    repo_root: Path,
    identity_output_path: Path,
    assumption_output_path: Path,
    metrics_output_path: Path,
) -> FoundationBuildResult:
    _ = repo_root
    _ensure_required_inputs()
    snapshot_utc = _utc_now_iso()

    screening_df = _read_csv_required(SCREENING_PATH)
    queue_df = _read_csv_required(QUEUE_PATH)
    decisions_df = _read_csv_required(DECISIONS_PATH)
    handoff_df = _read_csv_required(HANDOFF_PATH)
    recommendation_df = _read_csv_required(RECOMMENDATION_PATH)
    legacy_evidence_df = _read_csv_optional(LEGACY_EVIDENCE_PATH)
    listing_df = _read_csv_required(LISTING_SNAPSHOT_PATH)
    listing_history_df = _read_csv_optional(LISTING_HISTORY_PATH)
    merchant_listings_df = _read_csv_optional(MERCHANT_LISTINGS_PATH)
    product_db_preview_df = _read_csv_optional(PRODUCT_DB_PREVIEW_PATH)
    _ = _read_csv_required(SKU_SUMMARY_PATH)

    h_scope_asin_to_skus, h_scope_pair_counts = _build_h_scope_asin_map(
        listing_df=listing_df,
        listing_history_df=listing_history_df,
        merchant_listings_df=merchant_listings_df,
        product_db_preview_df=product_db_preview_df,
    )

    identity_df = _build_identity_bridge(
        screening_df=screening_df,
        queue_df=queue_df,
        decisions_df=decisions_df,
        handoff_df=handoff_df,
        recommendation_df=recommendation_df,
        legacy_evidence_df=legacy_evidence_df,
        listing_df=listing_df,
        listing_history_df=listing_history_df,
        merchant_listings_df=merchant_listings_df,
        product_db_preview_df=product_db_preview_df,
        snapshot_utc=snapshot_utc,
    )
    assumption_df = _build_assumption_snapshots(
        queue_df=queue_df,
        decisions_df=decisions_df,
        handoff_df=handoff_df,
        recommendation_df=recommendation_df,
        snapshot_utc=snapshot_utc,
    )
    metrics_df = _build_foundation_metrics(
        identity_df=identity_df,
        assumption_df=assumption_df,
        h_scope_asin_total=len(h_scope_asin_to_skus),
        h_scope_pair_counts=h_scope_pair_counts,
        snapshot_utc=snapshot_utc,
    )

    identity_output_path.parent.mkdir(parents=True, exist_ok=True)
    assumption_output_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_output_path.parent.mkdir(parents=True, exist_ok=True)
    identity_df.to_csv(identity_output_path, index=False)
    assumption_df.to_csv(assumption_output_path, index=False)
    metrics_df.to_csv(metrics_output_path, index=False)

    resolved_rows = int((identity_df["sku_resolution_status"] == "RESOLVED_FROM_H_SNAPSHOT").sum()) if not identity_df.empty else 0
    unresolved_rows = int(len(identity_df.index) - resolved_rows)
    decision_scope_rows = int((assumption_df["in_scope_approval_decision_flag"] == "1").sum()) if not assumption_df.empty else 0
    decision_scope_snapshot_rows = int(
        (
            (assumption_df["in_scope_approval_decision_flag"] == "1")
            & (assumption_df["snapshot_stage"].isin(["approval_decision", "po_handoff"]))
        ).sum()
    ) if not assumption_df.empty else 0

    return FoundationBuildResult(
        identity_path=identity_output_path,
        identity_rows=int(len(identity_df.index)),
        assumption_path=assumption_output_path,
        assumption_rows=int(len(assumption_df.index)),
        metrics_path=metrics_output_path,
        decision_scope_rows=decision_scope_rows,
        decision_scope_snapshot_rows=decision_scope_snapshot_rows,
        resolved_sku_rows=resolved_rows,
        unresolved_sku_rows=unresolved_rows,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build H/F learning foundation outputs (Phase 0).")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repository root")
    parser.add_argument(
        "--identity-output",
        default=str(IDENTITY_OUTPUT_PATH),
        help="Output CSV path for identity bridge",
    )
    parser.add_argument(
        "--assumption-output",
        default=str(ASSUMPTION_OUTPUT_PATH),
        help="Output CSV path for assumption snapshots",
    )
    parser.add_argument(
        "--metrics-output",
        default=str(METRICS_OUTPUT_PATH),
        help="Output CSV path for foundation coverage metrics",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = build_foundation(
        repo_root=Path(args.repo_root),
        identity_output_path=Path(args.identity_output),
        assumption_output_path=Path(args.assumption_output),
        metrics_output_path=Path(args.metrics_output),
    )
    print(f"identity_output_path={result.identity_path}")
    print(f"identity_rows={result.identity_rows}")
    print(f"identity_resolved_sku_rows={result.resolved_sku_rows}")
    print(f"identity_unresolved_sku_rows={result.unresolved_sku_rows}")
    print(f"assumption_output_path={result.assumption_path}")
    print(f"assumption_rows={result.assumption_rows}")
    print(f"assumption_decision_scope_rows={result.decision_scope_rows}")
    print(f"assumption_decision_scope_snapshot_rows={result.decision_scope_snapshot_rows}")
    print(f"metrics_output_path={result.metrics_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
