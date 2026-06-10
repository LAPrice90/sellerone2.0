from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.safe_file_writes import safe_to_csv


OUT = Path("out")
APPLY_PREVIEW = OUT / "systems" / "B" / "refunds" / "b_disposition_correction_apply_preview.csv"
TOKEN_LEDGER = OUT / "token_ledger_live.csv"
TOKEN_ALLOCATIONS = OUT / "token_allocations_live.csv"
TOKEN_COGS = OUT / "token_cogs_ledger.csv"
OUT_PROOF = OUT / "systems" / "B" / "refunds" / "b_historical_replacement_stock_proof.csv"
OUT_SUMMARY = OUT / "systems" / "B" / "refunds" / "b_historical_replacement_stock_proof_summary.csv"

TARGET_LANE = "replacement_candidate_date_validation_required"
SAFE_LABELS = {
    "date_valid_currently_available",
    "date_valid_but_already_used_later",
    "replacement_arrived_after_sale",
    "missing_date_proof",
    "not_yet_proven",
}

PROOF_COLUMNS = [
    "return_order_id",
    "sku",
    "downstream_order_id",
    "downstream_order_date",
    "reused_token_id",
    "visible_replacement_candidate_token_id",
    "visible_replacement_candidate_received_date",
    "visible_replacement_candidate_date_relation",
    "historical_replacement_label",
    "direct_replacement_swap_ready",
    "historical_candidate_token_id",
    "historical_candidate_received_date",
    "historical_candidate_status",
    "historical_candidate_allocated_order_id",
    "historical_candidate_allocation_date",
    "historical_candidate_cogs_rows",
    "historical_candidate_days_before_downstream_sale",
    "candidate_pool_currently_available_before_count",
    "candidate_pool_used_later_count",
    "candidate_pool_late_available_count",
    "candidate_pool_missing_date_count",
    "proof_reason",
    "preview_live_write_allowed",
    "roi_or_restock_use_allowed",
    "sellerboard_final_truth_allowed",
    "protected_before_apply",
    "bounded_worker_task",
    "retest_rule",
    "protected_stop_rule",
]

SUMMARY_COLUMNS = ["metric", "value"]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame()


def _text(value: object) -> str:
    return str(value or "").strip()


def _norm(value: object) -> str:
    return _text(value).upper()


def _parse_date(value: object) -> datetime | None:
    raw = _text(value)
    if not raw:
        return None
    candidates = [raw]
    if raw.endswith("Z"):
        candidates.append(raw[:-1] + "+00:00")
    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            pass
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _num_text(value: object) -> str:
    raw = _text(value)
    if not raw:
        return "0"
    try:
        number = float(raw.replace(",", ""))
    except Exception:
        return "0"
    if abs(number) < 0.0000005:
        return "0"
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _prepare_tokens(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in [
        "token_id",
        "seller_sku",
        "status",
        "allocated_order_id",
        "allocated_date",
        "received_date",
        "sort_rank",
        "lot_rank_num",
        "return_order_id",
        "last_return_order_id",
        "return_event_id",
        "last_return_event_id",
        "disposed_event_id",
        "disposed_date",
        "disposed_reason",
        "notes",
    ]:
        if column not in work.columns:
            work[column] = ""
    work["token_id_norm"] = work["token_id"].map(_text)
    work["sku_norm"] = work["seller_sku"].map(_norm)
    work["status_norm"] = work["status"].map(lambda value: _text(value).lower())
    work["allocated_order_norm"] = work["allocated_order_id"].map(_text)
    work["allocated_dt"] = work["allocated_date"].map(_parse_date)
    work["received_dt"] = work["received_date"].map(_parse_date)
    work["sort_num"] = pd.to_numeric(work["sort_rank"], errors="coerce").fillna(
        pd.to_numeric(work["lot_rank_num"], errors="coerce").fillna(999999999)
    )
    return work


def _prepare_allocations(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["order_id", "order_date", "allocation_date", "seller_sku", "token_id"]:
        if column not in work.columns:
            work[column] = ""
    work["order_id_norm"] = work["order_id"].map(_text)
    work["sku_norm"] = work["seller_sku"].map(_norm)
    work["token_id_norm"] = work["token_id"].map(_text)
    work["order_dt"] = work["order_date"].map(_parse_date)
    work["allocation_dt"] = work["allocation_date"].map(_parse_date)
    return work


def _prepare_cogs(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["order_id", "seller_sku", "token_id"]:
        if column not in work.columns:
            work[column] = ""
    work["token_id_norm"] = work["token_id"].map(_text)
    return work


def _has_any(row: pd.Series, columns: list[str]) -> bool:
    return any(_text(row.get(column, "")) for column in columns)


def _is_clean_stock_token(row: pd.Series, *, bad_token_id: str) -> bool:
    token_id = _text(row.get("token_id_norm", ""))
    if not token_id or token_id == bad_token_id:
        return False
    status = _text(row.get("status_norm", ""))
    notes = _text(row.get("notes", "")).lower()
    blocked_status_parts = ["return", "unsell", "research", "dispos", "damag", "defect"]
    if any(part in status for part in blocked_status_parts):
        return False
    if _has_any(
        row,
        [
            "return_order_id",
            "last_return_order_id",
            "return_event_id",
            "last_return_event_id",
            "disposed_event_id",
            "disposed_date",
            "disposed_reason",
        ],
    ):
        return False
    if "return_" in notes or "non_sellable_return" in notes:
        return False
    return True


def _allocation_date_for_token(allocations: pd.DataFrame, row: pd.Series) -> datetime | None:
    ledger_dt = row.get("allocated_dt")
    if ledger_dt is not None and not pd.isna(ledger_dt):
        return ledger_dt
    token_id = _text(row.get("token_id_norm", ""))
    if allocations.empty or not token_id:
        return None
    matches = allocations[allocations["token_id_norm"] == token_id]
    if matches.empty:
        return None
    for column in ["allocation_dt", "order_dt"]:
        for value in matches[column].tolist():
            if value is not None and not pd.isna(value):
                return value
    return None


def _allocation_order_for_token(allocations: pd.DataFrame, row: pd.Series) -> str:
    order_id = _text(row.get("allocated_order_norm", ""))
    token_id = _text(row.get("token_id_norm", ""))
    if order_id or allocations.empty or not token_id:
        return order_id
    matches = allocations[allocations["token_id_norm"] == token_id]
    if matches.empty:
        return ""
    return _text(matches.iloc[0].get("order_id", ""))


def _candidate_cogs_rows(cogs: pd.DataFrame, token_id: str) -> int:
    if cogs.empty or not token_id:
        return 0
    return int(len(cogs[cogs["token_id_norm"] == token_id]))


def _sort_candidates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df.sort_values(["sort_num", "token_id_norm"], kind="stable")


def _days_before_sale(candidate_dt: datetime | None, downstream_dt: datetime | None) -> str:
    if candidate_dt is None or downstream_dt is None:
        return ""
    return str(int((downstream_dt.date() - candidate_dt.date()).days))


def _label_task(label: str) -> str:
    if label == "date_valid_currently_available":
        return "Keep this row as a future protected correction candidate only; do not swap tokens from this proof."
    if label == "date_valid_but_already_used_later":
        return "Park as not direct-swap-ready because the date-valid token was later consumed by another order."
    if label == "replacement_arrived_after_sale":
        return "Park as late replacement stock unless another older clean token is later proved."
    if label == "missing_date_proof":
        return "Create a bounded proof task to fill missing token or downstream order dates before any correction can be considered."
    return "Create a bounded proof task only if source evidence is restored or widened by an approved B packet."


def _classify_source_row(
    source: pd.Series,
    *,
    tokens: pd.DataFrame,
    allocations: pd.DataFrame,
    cogs: pd.DataFrame,
    token_source_missing: bool,
) -> dict[str, str]:
    sku = _norm(source.get("sku", ""))
    downstream_order_date = _text(source.get("downstream_order_date", ""))
    downstream_dt = _parse_date(downstream_order_date)
    reused_token_id = _text(source.get("reused_token_id", ""))
    visible_token_id = _text(source.get("replacement_candidate_token_id", ""))
    visible_received_date = _text(source.get("replacement_candidate_received_date", ""))
    visible_relation = _text(source.get("replacement_candidate_date_relation", ""))

    label = "not_yet_proven"
    proof_reason = "Required token proof source is missing or unreadable."
    candidate: pd.Series | None = None
    candidate_allocation_dt: datetime | None = None
    candidate_allocated_order = ""

    available_before = pd.DataFrame()
    used_later = pd.DataFrame()
    late_available = pd.DataFrame()
    missing_date = pd.DataFrame()

    if downstream_dt is None:
        label = "missing_date_proof"
        proof_reason = "Downstream sale date is missing, so historical replacement timing cannot be proved."
    elif not token_source_missing:
        same_sku = tokens[tokens["sku_norm"] == sku].copy() if not tokens.empty else pd.DataFrame()
        if not same_sku.empty:
            same_sku = same_sku[
                same_sku.apply(lambda row: _is_clean_stock_token(row, bad_token_id=reused_token_id), axis=1)
            ].copy()
        if not same_sku.empty:
            same_sku["resolved_allocation_dt"] = same_sku.apply(
                lambda row: _allocation_date_for_token(allocations, row),
                axis=1,
            )
            same_sku["resolved_allocated_order"] = same_sku.apply(
                lambda row: _allocation_order_for_token(allocations, row),
                axis=1,
            )
            available_before = same_sku[
                (same_sku["status_norm"] == "available")
                & (same_sku["allocated_order_norm"] == "")
                & same_sku["received_dt"].notna()
                & (same_sku["received_dt"] <= downstream_dt)
            ].copy()
            used_later = same_sku[
                same_sku["received_dt"].notna()
                & (same_sku["received_dt"] <= downstream_dt)
                & (
                    (same_sku["allocated_order_norm"] != "")
                    | (same_sku["resolved_allocated_order"].map(_text) != "")
                )
                & same_sku["resolved_allocation_dt"].notna()
                & (same_sku["resolved_allocation_dt"] > downstream_dt)
            ].copy()
            late_available = same_sku[
                (same_sku["status_norm"] == "available")
                & (same_sku["allocated_order_norm"] == "")
                & same_sku["received_dt"].notna()
                & (same_sku["received_dt"] > downstream_dt)
            ].copy()
            missing_date = same_sku[same_sku["received_dt"].isna()].copy()

        if not available_before.empty:
            candidate = _sort_candidates(available_before).iloc[0]
            label = "date_valid_currently_available"
            proof_reason = "A clean same-SKU token was received on or before the downstream sale and is still currently available."
        elif not used_later.empty:
            candidate = _sort_candidates(used_later).iloc[0]
            candidate_allocation_dt = candidate.get("resolved_allocation_dt")
            candidate_allocated_order = _text(candidate.get("resolved_allocated_order", ""))
            label = "date_valid_but_already_used_later"
            proof_reason = "A clean same-SKU token existed before the downstream sale, but it was later used on another order."
        elif not late_available.empty:
            candidate = _sort_candidates(late_available).iloc[0]
            label = "replacement_arrived_after_sale"
            proof_reason = "The only visible clean replacement stock was received after the downstream sale."
        elif visible_relation == "after_downstream_order" and visible_token_id:
            label = "replacement_arrived_after_sale"
            proof_reason = "B061 already proves the visible replacement candidate arrived after the downstream sale."
        elif not missing_date.empty or visible_relation in {"missing_downstream_order_date", "unknown_replacement_date"}:
            candidate = _sort_candidates(missing_date).iloc[0] if not missing_date.empty else None
            label = "missing_date_proof"
            proof_reason = "A possible same-SKU token exists, but token or order dates are incomplete."
        else:
            label = "not_yet_proven"
            proof_reason = "No clean same-SKU historical replacement token is proved from the current source files."

    candidate_token_id = _text(candidate.get("token_id", "")) if candidate is not None else ""
    candidate_received_date = _text(candidate.get("received_date", "")) if candidate is not None else ""
    candidate_status = _text(candidate.get("status", "")) if candidate is not None else ""
    if candidate is not None and candidate_allocation_dt is None:
        candidate_allocation_dt = _allocation_date_for_token(allocations, candidate)
    if candidate is not None and not candidate_allocated_order:
        candidate_allocated_order = _allocation_order_for_token(allocations, candidate)
    candidate_allocation_text = (
        candidate_allocation_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        if candidate_allocation_dt is not None
        else ""
    )
    direct_ready = "1" if label == "date_valid_currently_available" else "0"

    return {
        "return_order_id": _text(source.get("return_order_id", "")),
        "sku": sku,
        "downstream_order_id": _text(source.get("downstream_order_id", "")),
        "downstream_order_date": downstream_order_date,
        "reused_token_id": reused_token_id,
        "visible_replacement_candidate_token_id": visible_token_id,
        "visible_replacement_candidate_received_date": visible_received_date,
        "visible_replacement_candidate_date_relation": visible_relation,
        "historical_replacement_label": label,
        "direct_replacement_swap_ready": direct_ready,
        "historical_candidate_token_id": candidate_token_id,
        "historical_candidate_received_date": candidate_received_date,
        "historical_candidate_status": candidate_status,
        "historical_candidate_allocated_order_id": candidate_allocated_order,
        "historical_candidate_allocation_date": candidate_allocation_text,
        "historical_candidate_cogs_rows": str(_candidate_cogs_rows(cogs, candidate_token_id)),
        "historical_candidate_days_before_downstream_sale": _days_before_sale(_parse_date(candidate_received_date), downstream_dt),
        "candidate_pool_currently_available_before_count": str(len(available_before)),
        "candidate_pool_used_later_count": str(len(used_later)),
        "candidate_pool_late_available_count": str(len(late_available)),
        "candidate_pool_missing_date_count": str(len(missing_date)),
        "proof_reason": proof_reason,
        "preview_live_write_allowed": "0",
        "roi_or_restock_use_allowed": "0",
        "sellerboard_final_truth_allowed": "0",
        "protected_before_apply": "1",
        "bounded_worker_task": _label_task(label),
        "retest_rule": "Rerun B065 and B MOT. Any future live swap needs a protected B repair window and B061/B060/B059/B058 retest.",
        "protected_stop_rule": (
            "Stop before live token swap, allocation change, COGS correction, stock exception, Sheet write, DB alignment, "
            "output deletion, ROI/restocking use, B run/restart, price change, queue edit, or widening beyond B historical replacement proof."
        ),
    }


def build_historical_replacement_stock_proof(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
) -> dict[str, pd.DataFrame]:
    root_path = Path(root or ".")
    observed = observed_utc or _utc_now_text()
    preview_path = root_path / APPLY_PREVIEW
    token_path = root_path / TOKEN_LEDGER
    allocation_path = root_path / TOKEN_ALLOCATIONS
    cogs_path = root_path / TOKEN_COGS
    preview = _read_csv(preview_path)
    tokens = _prepare_tokens(_read_csv(token_path))
    allocations = _prepare_allocations(_read_csv(allocation_path))
    cogs = _prepare_cogs(_read_csv(cogs_path))

    required_preview = {
        "return_order_id",
        "sku",
        "reused_token_id",
        "downstream_order_id",
        "downstream_order_date",
        "replacement_candidate_token_id",
        "replacement_candidate_received_date",
        "replacement_candidate_date_relation",
        "correction_apply_lane",
    }
    missing_schema = sorted(required_preview - set(preview.columns)) if preview_path.exists() else []
    rows: list[dict[str, str]] = []
    token_source_missing = not token_path.exists() or tokens.empty

    if preview_path.exists() and not missing_schema:
        targets = preview[preview["correction_apply_lane"].map(_text) == TARGET_LANE].copy()
        for _, source in targets.iterrows():
            rows.append(
                _classify_source_row(
                    source,
                    tokens=tokens,
                    allocations=allocations,
                    cogs=cogs,
                    token_source_missing=token_source_missing,
                )
            )

    proof = pd.DataFrame(rows, columns=PROOF_COLUMNS).fillna("")
    unsafe_rows = (
        proof[
            (proof["preview_live_write_allowed"] != "0")
            | (proof["roi_or_restock_use_allowed"] != "0")
            | (proof["sellerboard_final_truth_allowed"] != "0")
        ]
        if not proof.empty
        else proof
    )
    unclassified_rows = (
        proof[~proof["historical_replacement_label"].isin(SAFE_LABELS)] if not proof.empty else proof
    )
    direct_ready_mismatch_rows = (
        proof[
            ((proof["historical_replacement_label"] == "date_valid_currently_available") & (proof["direct_replacement_swap_ready"] != "1"))
            | ((proof["historical_replacement_label"] != "date_valid_currently_available") & (proof["direct_replacement_swap_ready"] != "0"))
        ]
        if not proof.empty
        else proof
    )

    status = "ok"
    if not preview_path.exists():
        status = "not_checked"
    elif missing_schema or len(unsafe_rows) or len(unclassified_rows) or len(direct_ready_mismatch_rows):
        status = "fail"

    label_counts = {
        label: int((proof["historical_replacement_label"] == label).sum()) if not proof.empty else 0
        for label in sorted(SAFE_LABELS)
    }
    summary_rows = [
        {"metric": "status", "value": status},
        {"metric": "observed_utc", "value": observed},
        {"metric": "proof_rows", "value": str(len(proof))},
        {"metric": "source_preview_exists", "value": "1" if preview_path.exists() else "0"},
        {"metric": "token_ledger_exists", "value": "1" if token_path.exists() else "0"},
        {"metric": "token_allocation_exists", "value": "1" if allocation_path.exists() else "0"},
        {"metric": "token_cogs_exists", "value": "1" if cogs_path.exists() else "0"},
        {"metric": "date_valid_currently_available_rows", "value": str(label_counts["date_valid_currently_available"])},
        {"metric": "date_valid_but_already_used_later_rows", "value": str(label_counts["date_valid_but_already_used_later"])},
        {"metric": "replacement_arrived_after_sale_rows", "value": str(label_counts["replacement_arrived_after_sale"])},
        {"metric": "missing_date_proof_rows", "value": str(label_counts["missing_date_proof"])},
        {"metric": "not_yet_proven_rows", "value": str(label_counts["not_yet_proven"])},
        {
            "metric": "direct_replacement_swap_ready_rows",
            "value": str(int((proof["direct_replacement_swap_ready"] == "1").sum()) if not proof.empty else 0),
        },
        {"metric": "unsafe_rows", "value": str(len(unsafe_rows))},
        {"metric": "unclassified_rows", "value": str(len(unclassified_rows))},
        {"metric": "direct_ready_mismatch_rows", "value": str(len(direct_ready_mismatch_rows))},
        {"metric": "missing_schema", "value": ";".join(missing_schema)},
    ]
    summary = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS).fillna("")
    return {"proof": proof, "summary": summary}


def write_historical_replacement_stock_proof_outputs(
    result: dict[str, pd.DataFrame],
    *,
    root: Path | str | None = None,
) -> dict[str, Path]:
    root_path = Path(root or ".")
    proof_path = root_path / OUT_PROOF
    summary_path = root_path / OUT_SUMMARY
    safe_to_csv(result["proof"], proof_path, index=False)
    safe_to_csv(result["summary"], summary_path, index=False)
    return {"proof": proof_path, "summary": summary_path}


def main() -> None:
    result = build_historical_replacement_stock_proof()
    paths = write_historical_replacement_stock_proof_outputs(result)
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}
    print(
        {
            "status": summary.get("status", ""),
            "proof_rows": summary.get("proof_rows", "0"),
            "date_valid_currently_available_rows": summary.get("date_valid_currently_available_rows", "0"),
            "date_valid_but_already_used_later_rows": summary.get("date_valid_but_already_used_later_rows", "0"),
            "replacement_arrived_after_sale_rows": summary.get("replacement_arrived_after_sale_rows", "0"),
            "missing_date_proof_rows": summary.get("missing_date_proof_rows", "0"),
            "not_yet_proven_rows": summary.get("not_yet_proven_rows", "0"),
            "proof": str(paths["proof"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
