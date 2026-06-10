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
IMPACT_PREVIEW = OUT / "systems" / "B" / "refunds" / "b_disposition_correction_impact_preview.csv"
TOKEN_LEDGER = OUT / "token_ledger_live.csv"
TOKEN_ALLOCATIONS = OUT / "token_allocations_live.csv"
TOKEN_COGS = OUT / "token_cogs_ledger.csv"
OUT_PREVIEW = OUT / "systems" / "B" / "refunds" / "b_disposition_correction_apply_preview.csv"
OUT_SUMMARY = OUT / "systems" / "B" / "refunds" / "b_disposition_correction_apply_preview_summary.csv"

PREVIEW_COLUMNS = [
    "return_order_id",
    "sku",
    "amazon_return_disposition",
    "reused_token_id",
    "downstream_order_id",
    "downstream_order_status",
    "downstream_order_date",
    "reused_token_allocation_rows",
    "reused_token_cogs_rows",
    "replacement_candidate_token_id",
    "replacement_candidate_received_date",
    "replacement_candidate_date_relation",
    "replacement_candidate_days_after_order",
    "replacement_date_validation_reason",
    "replacement_candidate_cost",
    "replacement_candidate_currency",
    "replacement_available_token_count",
    "replacement_before_order_count",
    "replacement_unknown_date_count",
    "correction_apply_lane",
    "correction_preview_action",
    "protected_decision_required",
    "requires_luke_live_apply",
    "preview_live_write_allowed",
    "protected_before_apply",
    "roi_or_restock_use_allowed",
    "sellerboard_final_truth_allowed",
    "bounded_worker_task",
    "retest_rule",
    "protected_stop_rule",
]

SUMMARY_COLUMNS = ["metric", "value"]
AVAILABLE_STATUSES = {"available"}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _text(value: object) -> str:
    return str(value or "").strip()


def _norm(value: object) -> str:
    return _text(value).upper()


def _split(value: object) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for part in _text(value).split("|"):
        item = part.strip()
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _first(value: object) -> str:
    parts = _split(value)
    return parts[0] if parts else ""


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


def _prepare_tokens(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in [
        "token_id",
        "seller_sku",
        "status",
        "allocated_order_id",
        "received_date",
        "cost_per_unit",
        "currency",
        "sort_rank",
        "lot_rank_num",
    ]:
        if column not in work.columns:
            work[column] = ""
    work["token_id_norm"] = work["token_id"].map(_text)
    work["sku_norm"] = work["seller_sku"].map(_norm)
    work["status_norm"] = work["status"].map(lambda value: _text(value).lower())
    work["allocated_order_norm"] = work["allocated_order_id"].map(_text)
    work["received_dt"] = work["received_date"].map(_parse_date)
    work["sort_num"] = pd.to_numeric(work["sort_rank"], errors="coerce").fillna(
        pd.to_numeric(work["lot_rank_num"], errors="coerce").fillna(999999999)
    )
    return work


def _prepare_allocations(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["order_id", "order_date", "seller_sku", "token_id"]:
        if column not in work.columns:
            work[column] = ""
    work["order_id_norm"] = work["order_id"].map(_text)
    work["sku_norm"] = work["seller_sku"].map(_norm)
    work["token_id_norm"] = work["token_id"].map(_text)
    return work


def _prepare_cogs(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["order_id", "seller_sku", "token_id"]:
        if column not in work.columns:
            work[column] = ""
    work["order_id_norm"] = work["order_id"].map(_text)
    work["sku_norm"] = work["seller_sku"].map(_norm)
    work["token_id_norm"] = work["token_id"].map(_text)
    return work


def _downstream_status(statuses: object, order_id: str) -> str:
    for part in _split(statuses):
        if ":" not in part:
            continue
        left, right = part.split(":", 1)
        if _text(left) == order_id:
            return _text(right)
    return ""


def _downstream_order_date(allocations: pd.DataFrame, *, order_id: str, sku: str, token_id: str) -> str:
    if allocations.empty:
        return ""
    rows = allocations[
        (allocations["order_id_norm"] == order_id)
        & (allocations["sku_norm"] == sku)
        & (allocations["token_id_norm"] == token_id)
    ]
    if rows.empty:
        rows = allocations[(allocations["order_id_norm"] == order_id) & (allocations["sku_norm"] == sku)]
    if rows.empty:
        return ""
    return _text(rows.iloc[0].get("order_date", ""))


def _allocation_rows(allocations: pd.DataFrame, *, order_id: str, sku: str, token_id: str) -> int:
    if allocations.empty:
        return 0
    rows = allocations[
        (allocations["order_id_norm"] == order_id)
        & (allocations["sku_norm"] == sku)
        & (allocations["token_id_norm"] == token_id)
    ]
    return int(len(rows))


def _cogs_rows(cogs: pd.DataFrame, *, order_id: str, sku: str, token_id: str) -> int:
    if cogs.empty:
        return 0
    rows = cogs[
        (cogs["order_id_norm"] == order_id)
        & (cogs["sku_norm"] == sku)
        & (cogs["token_id_norm"] == token_id)
    ]
    return int(len(rows))


def _replacement_candidates(
    tokens: pd.DataFrame,
    *,
    sku: str,
    reused_token_id: str,
    order_date: str,
    used_replacement_token_ids: set[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if tokens.empty:
        empty = pd.DataFrame()
        return empty, empty, empty
    available = tokens[
        (tokens["sku_norm"] == sku)
        & (tokens["status_norm"].isin(AVAILABLE_STATUSES))
        & (tokens["allocated_order_norm"] == "")
        & (tokens["token_id_norm"] != reused_token_id)
        & (~tokens["token_id_norm"].isin(used_replacement_token_ids))
    ].copy()
    if available.empty:
        empty = pd.DataFrame()
        return available, empty, empty
    order_dt = _parse_date(order_date)
    if order_dt is None:
        unknown = available[available["received_dt"].isna()].copy()
        dated = available[~available["received_dt"].isna()].copy()
        return available, dated, unknown
    before = available[available["received_dt"].notna() & (available["received_dt"] <= order_dt)].copy()
    unknown = available[available["received_dt"].isna()].copy()
    return available, before, unknown


def _first_candidate(before: pd.DataFrame, available: pd.DataFrame, unknown: pd.DataFrame) -> pd.Series | None:
    source = before if not before.empty else available if not available.empty else unknown
    if source.empty:
        return None
    work = source.sort_values(["sort_num", "token_id_norm"], kind="stable")
    return work.iloc[0]


def _lane(*, status: str, before_count: int, available_count: int, unknown_count: int) -> str:
    if _text(status).lower() == "unshipped":
        if before_count or available_count:
            return "unshipped_order_replacement_swap_preview_ready"
        return "no_replacement_token_protected_shortage_or_exception_review"
    if before_count:
        return "shipped_order_replacement_swap_preview_ready"
    if available_count or unknown_count:
        return "replacement_candidate_date_validation_required"
    return "no_replacement_token_protected_shortage_or_exception_review"


def _action_for_lane(lane: str) -> str:
    if lane.endswith("replacement_swap_preview_ready"):
        return (
            "No-write preview only. A future protected apply can propose swapping the downstream allocation to the named "
            "clean replacement token, then blocking the non-sellable returned token and return COGS recovery."
        )
    if lane == "replacement_candidate_date_validation_required":
        return (
            "No-write preview only. Candidate stock exists, but the dates are not clean enough for an automatic apply preview."
        )
    return (
        "No-write preview only. No clean replacement token is proved, so any future action needs a protected shortage or "
        "business-exception decision."
    )


def _candidate_timing_proof(*, downstream_order_date: str, candidate: pd.Series | None) -> tuple[str, str, str]:
    if candidate is None or not _text(candidate.get("token_id", "")):
        return (
            "no_replacement_candidate",
            "",
            "No clean available replacement token exists for this SKU.",
        )
    candidate_date_text = _text(candidate.get("received_date", ""))
    order_dt = _parse_date(downstream_order_date)
    candidate_dt = _parse_date(candidate_date_text)
    if order_dt is None:
        return (
            "missing_downstream_order_date",
            "",
            "Downstream order date is missing, so replacement timing cannot be proved.",
        )
    if candidate_dt is None:
        return (
            "unknown_replacement_date",
            "",
            "Replacement token received date is missing, so timing cannot be proved.",
        )
    days_after = int((candidate_dt.date() - order_dt.date()).days)
    if candidate_dt > order_dt:
        return (
            "after_downstream_order",
            str(days_after),
            "Replacement token was received after the downstream order, so it cannot be used as an automatic historical replacement.",
        )
    return (
        "on_or_before_downstream_order",
        str(days_after),
        "Replacement token was available by the downstream order date.",
    )


def build_disposition_correction_apply_preview(*, root: Path | str | None = None) -> dict[str, object]:
    root_path = Path(root or ".")
    impact = _read_csv(root_path / IMPACT_PREVIEW)
    tokens = _prepare_tokens(_read_csv(root_path / TOKEN_LEDGER))
    allocations = _prepare_allocations(_read_csv(root_path / TOKEN_ALLOCATIONS))
    cogs = _prepare_cogs(_read_csv(root_path / TOKEN_COGS))

    rows: list[dict[str, str]] = []
    used_replacement_token_ids: set[str] = set()
    if not impact.empty:
        for _, impact_row in impact.iterrows():
            sku = _norm(impact_row.get("sku", ""))
            reused_token_id = _first(impact_row.get("reusable_return_token_ids", ""))
            downstream_order_id = _first(impact_row.get("downstream_allocated_order_ids", ""))
            downstream_status = _downstream_status(impact_row.get("downstream_order_statuses", ""), downstream_order_id)
            downstream_date = _downstream_order_date(
                allocations,
                order_id=downstream_order_id,
                sku=sku,
                token_id=reused_token_id,
            )
            available, before, unknown = _replacement_candidates(
                tokens,
                sku=sku,
                reused_token_id=reused_token_id,
                order_date=downstream_date,
                used_replacement_token_ids=used_replacement_token_ids,
            )
            candidate = _first_candidate(before, available, unknown)
            if candidate is not None:
                candidate_token_id = _text(candidate.get("token_id", ""))
                if candidate_token_id:
                    used_replacement_token_ids.add(candidate_token_id)
            lane = _lane(
                status=downstream_status,
                before_count=len(before),
                available_count=len(available),
                unknown_count=len(unknown),
            )
            date_relation, days_after_order, date_reason = _candidate_timing_proof(
                downstream_order_date=downstream_date,
                candidate=candidate,
            )
            rows.append(
                {
                    "return_order_id": _text(impact_row.get("return_order_id", "")),
                    "sku": sku,
                    "amazon_return_disposition": _text(impact_row.get("amazon_return_disposition", "")),
                    "reused_token_id": reused_token_id,
                    "downstream_order_id": downstream_order_id,
                    "downstream_order_status": downstream_status,
                    "downstream_order_date": downstream_date,
                    "reused_token_allocation_rows": str(
                        _allocation_rows(
                            allocations,
                            order_id=downstream_order_id,
                            sku=sku,
                            token_id=reused_token_id,
                        )
                    ),
                    "reused_token_cogs_rows": str(
                        _cogs_rows(
                            cogs,
                            order_id=downstream_order_id,
                            sku=sku,
                            token_id=reused_token_id,
                        )
                    ),
                    "replacement_candidate_token_id": _text(candidate.get("token_id", "")) if candidate is not None else "",
                    "replacement_candidate_received_date": _text(candidate.get("received_date", "")) if candidate is not None else "",
                    "replacement_candidate_date_relation": date_relation,
                    "replacement_candidate_days_after_order": days_after_order,
                    "replacement_date_validation_reason": date_reason,
                    "replacement_candidate_cost": _text(candidate.get("cost_per_unit", "")) if candidate is not None else "",
                    "replacement_candidate_currency": _text(candidate.get("currency", "")) if candidate is not None else "",
                    "replacement_available_token_count": str(len(available)),
                    "replacement_before_order_count": str(len(before)),
                    "replacement_unknown_date_count": str(len(unknown)),
                    "correction_apply_lane": lane,
                    "correction_preview_action": _action_for_lane(lane),
                    "protected_decision_required": "1",
                    "requires_luke_live_apply": "1",
                    "preview_live_write_allowed": "0",
                    "protected_before_apply": "1",
                    "roi_or_restock_use_allowed": "0",
                    "sellerboard_final_truth_allowed": "0",
                    "bounded_worker_task": (
                        "If Luke approves a live correction window later, build or run a guarded apply from these exact rows. "
                        "Do not write token, COGS, downstream allocation, ROI, or restocking state from B061."
                    ),
                    "retest_rule": (
                        "After any future protected apply, rerun B061, B060, B059, B058, B041, B038, B051, and B MOT."
                    ),
                    "protected_stop_rule": (
                        "Stop before live token correction, replacement-token swap, downstream allocation correction, COGS correction, "
                        "B run/restart, Sheet write, DB alignment, output deletion, ROI/restocking use, price/queue change, or widening beyond B return-token repair."
                    ),
                }
            )

    preview = pd.DataFrame(rows, columns=PREVIEW_COLUMNS).fillna("")
    live_write_rows = int((preview["preview_live_write_allowed"] != "0").sum()) if not preview.empty else 0
    roi_rows = int((preview["roi_or_restock_use_allowed"] != "0").sum()) if not preview.empty else 0
    sellerboard_rows = int((preview["sellerboard_final_truth_allowed"] != "0").sum()) if not preview.empty else 0
    unclassified_rows = int((preview["correction_apply_lane"].astype(str).str.strip() == "").sum()) if not preview.empty else 0
    replacement_ready_rows = (
        int(preview["correction_apply_lane"].astype(str).str.endswith("replacement_swap_preview_ready").sum())
        if not preview.empty
        else 0
    )
    date_validation_rows = (
        int((preview["correction_apply_lane"].astype(str) == "replacement_candidate_date_validation_required").sum())
        if not preview.empty
        else 0
    )
    no_replacement_rows = (
        int((preview["correction_apply_lane"].astype(str) == "no_replacement_token_protected_shortage_or_exception_review").sum())
        if not preview.empty
        else 0
    )
    candidate_after_order_rows = (
        int((preview["replacement_candidate_date_relation"].astype(str) == "after_downstream_order").sum())
        if not preview.empty
        else 0
    )
    candidate_unknown_timing_rows = (
        int(
            preview["replacement_candidate_date_relation"]
            .astype(str)
            .isin({"missing_downstream_order_date", "unknown_replacement_date"})
            .sum()
        )
        if not preview.empty
        else 0
    )
    summary_values = {
        "status": "fail" if live_write_rows or roi_rows or sellerboard_rows or unclassified_rows else "ok",
        "preview_rows": str(len(preview)),
        "source_impact_rows": str(len(impact)),
        "protected_decision_rows": str(
            int((preview["protected_decision_required"].astype(str).str.strip() == "1").sum()) if not preview.empty else 0
        ),
        "replacement_swap_preview_ready_rows": str(replacement_ready_rows),
        "replacement_date_validation_rows": str(date_validation_rows),
        "replacement_candidate_after_order_rows": str(candidate_after_order_rows),
        "replacement_candidate_unknown_timing_rows": str(candidate_unknown_timing_rows),
        "no_replacement_rows": str(no_replacement_rows),
        "live_write_allowed_rows": str(live_write_rows),
        "roi_or_restock_allowed_rows": str(roi_rows),
        "sellerboard_final_truth_allowed_rows": str(sellerboard_rows),
        "unclassified_rows": str(unclassified_rows),
    }
    summary = pd.DataFrame([{"metric": key, "value": value} for key, value in summary_values.items()], columns=SUMMARY_COLUMNS)
    return {
        "preview": preview,
        "summary": summary,
        "preview_path": root_path / OUT_PREVIEW,
        "summary_path": root_path / OUT_SUMMARY,
    }


def write_disposition_correction_apply_preview_outputs(result: dict[str, object]) -> dict[str, Path]:
    preview_path = Path(result["preview_path"])
    summary_path = Path(result["summary_path"])
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    safe_to_csv(result["preview"], preview_path, index=False)
    safe_to_csv(result["summary"], summary_path, index=False)
    return {"preview": preview_path, "summary": summary_path}


def main() -> None:
    result = build_disposition_correction_apply_preview()
    paths = write_disposition_correction_apply_preview_outputs(result)
    preview = result["preview"]
    values = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()} if not result["summary"].empty else {}
    print(
        {
            "status": values.get("status", ""),
            "preview_rows": len(preview),
            "replacement_swap_preview_ready_rows": values.get("replacement_swap_preview_ready_rows", "0"),
            "no_replacement_rows": values.get("no_replacement_rows", "0"),
            "preview": str(paths["preview"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
