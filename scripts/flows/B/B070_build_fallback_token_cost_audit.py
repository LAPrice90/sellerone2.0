from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.safe_file_writes import safe_to_csv


OUT = Path("out")
TOKEN_LEDGER = OUT / "token_ledger_live.csv"
STOCK_ADJUSTMENTS = OUT / "stock_adjustment_token_events.csv"
STOCK_RECEIPTS = OUT / "stock_receipts_latest.csv"
AUDIT_OUT = OUT / "systems" / "B" / "refunds" / "b_fallback_token_cost_audit.csv"
SUMMARY_OUT = OUT / "systems" / "B" / "refunds" / "b_fallback_token_cost_audit_summary.csv"

AUDIT_COLUMNS = [
    "token_id",
    "seller_sku",
    "status",
    "event_id",
    "event_type",
    "event_disposition",
    "event_date",
    "cost_per_unit",
    "currency",
    "created_at",
    "received_date",
    "cost_proof_state",
    "receipt_match_count",
    "source_token_match_count",
    "source_token_id",
    "source_token_source",
    "source_token_batch_id",
    "source_token_order_key",
    "receipt_batch_id",
    "receipt_order_key",
    "manager_label",
    "manager_expectation",
    "bounded_worker_task",
    "retest_rule",
    "preview_live_write_allowed",
    "roi_or_restock_use_allowed",
    "protected_before_apply",
]

SUMMARY_COLUMNS = ["metric", "value"]


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _text(value: object) -> str:
    return str(value or "").strip()


def _norm_sku(value: object) -> str:
    return _text(value).upper()


def _num(value: object) -> float:
    raw = _text(value).replace(",", "")
    if not raw:
        return 0.0
    try:
        return float(raw)
    except Exception:
        return 0.0


def _money_equal(left: object, right: object) -> bool:
    return abs(_num(left) - _num(right)) < 0.005 and _num(left) > 0


def _parse_dt(value: object) -> pd.Timestamp | None:
    parsed = pd.to_datetime(_text(value), errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed


def _first_present(row: pd.Series, names: list[str]) -> str:
    for name in names:
        if name in row.index and _text(row.get(name, "")):
            return _text(row.get(name, ""))
    return ""


def _event_id_from_token(row: pd.Series) -> str:
    batch = _text(row.get("source_batch_id", ""))
    if batch:
        return batch
    note = _text(row.get("notes", ""))
    match = re.search(r"adjustment_fallback_create:([^;|\s]+)", note)
    if match:
        return match.group(1).strip()
    token_id = _text(row.get("token_id", ""))
    if "-ADJ-" in token_id:
        return token_id.split("-ADJ-", 1)[1]
    return ""


def _prepare_ledger(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    for column in [
        "token_id",
        "seller_sku",
        "cost_per_unit",
        "currency",
        "status",
        "received_date",
        "created_at",
        "notes",
        "source",
        "source_batch_id",
        "source_order_key",
    ]:
        if column not in work.columns:
            work[column] = ""
    work["sku_norm"] = work["seller_sku"].map(_norm_sku)
    work["cost_num"] = pd.to_numeric(work["cost_per_unit"], errors="coerce").fillna(0.0)
    work["cost_key"] = work["cost_num"].map(lambda value: f"{float(value):.2f}")
    work["received_dt"] = pd.to_datetime(work["received_date"], errors="coerce", utc=True)
    work["created_dt"] = pd.to_datetime(work["created_at"], errors="coerce", utc=True)
    work["is_fallback"] = (
        work["source"].astype(str).str.strip().eq("stock_adjustment_fallback")
        | work["notes"].astype(str).str.contains("adjustment_fallback_create:", na=False)
        | work["token_id"].astype(str).str.startswith("ADJ-")
    )
    return work


def _prepare_events(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    for column in ["event_id", "sku", "event_date", "event_type", "disposition"]:
        if column not in work.columns:
            work[column] = ""
    work["event_id_norm"] = work["event_id"].map(_text)
    work["sku_norm"] = work["sku"].map(_norm_sku)
    return work


def _prepare_receipts(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    for column in ["seller_sku", "SKU", "cost_per_unit", "Cost PU", "batch_id", "OrderKey", "order_key", "status"]:
        if column not in work.columns:
            work[column] = ""
    work["sku_norm"] = work.apply(lambda row: _norm_sku(_first_present(row, ["seller_sku", "SKU"])), axis=1)
    work["cost_text"] = work.apply(lambda row: _first_present(row, ["cost_per_unit", "Cost PU"]), axis=1)
    work["cost_num"] = pd.to_numeric(work["cost_text"], errors="coerce").fillna(0.0)
    work["cost_key"] = work["cost_num"].map(lambda value: f"{float(value):.2f}")
    work["order_key_text"] = work.apply(lambda row: _first_present(row, ["order_key", "OrderKey"]), axis=1)
    return work


def _source_token_candidates(source_groups: dict[tuple[str, str], pd.DataFrame], row: pd.Series) -> pd.DataFrame:
    sku = _norm_sku(row.get("seller_sku", ""))
    token_id = _text(row.get("token_id", ""))
    cutoff = _parse_dt(row.get("created_at", "")) or _parse_dt(row.get("received_date", ""))
    candidates = source_groups.get((sku, f"{_num(row.get('cost_per_unit', '')):.2f}"), pd.DataFrame()).copy()
    if not candidates.empty:
        candidates = candidates[candidates["token_id"].map(_text) != token_id].copy()
    if cutoff is not None and not candidates.empty:
        date_ok = (
            candidates["received_dt"].isna()
            | (candidates["received_dt"] <= cutoff)
            | candidates["created_dt"].isna()
            | (candidates["created_dt"] <= cutoff)
        )
        candidates = candidates[date_ok].copy()
    if candidates.empty:
        return candidates
    candidates = candidates.sort_values(by=["has_source_proof", "received_dt", "created_dt"], ascending=[False, True, True])
    return candidates


def _receipt_matches(receipt_groups: dict[tuple[str, str], pd.DataFrame], row: pd.Series) -> pd.DataFrame:
    sku = _norm_sku(row.get("seller_sku", ""))
    return receipt_groups.get((sku, f"{_num(row.get('cost_per_unit', '')):.2f}"), pd.DataFrame()).copy()


def _classify(receipt_count: int, source_candidates: pd.DataFrame, cost: object) -> tuple[str, str, str, str]:
    if _num(cost) <= 0:
        return (
            "fallback_cost_unproved",
            "not_yet_proven",
            "Fallback token has no positive cost proof.",
            "Do not use this fallback cost in ROI/restocking until corrected or approved.",
        )
    if receipt_count > 0:
        return (
            "fallback_cost_receipt_proved",
            "api_or_receipt_proved",
            "Fallback token cost matches a local receipt row for the same SKU.",
            "No live correction needed from this audit.",
        )
    if not source_candidates.empty and bool(source_candidates.iloc[0].get("has_source_proof", False)):
        return (
            "fallback_cost_source_token_proved",
            "source_token_proved",
            "Fallback token cost matches a non-fallback source token with source proof.",
            "No live correction needed from this audit.",
        )
    if not source_candidates.empty:
        return (
            "fallback_cost_weak_latest_token",
            "weak_fallback_cost",
            "Fallback token cost only matches another same-SKU token without clear source proof.",
            "Keep warning visible and prepare a correction preview before ROI/restocking use.",
        )
    return (
        "fallback_cost_unproved",
        "not_yet_proven",
        "Fallback token cost does not match a receipt or non-fallback source token.",
        "Keep warning visible and prepare a correction preview before ROI/restocking use.",
    )


def build_fallback_token_cost_audit(*, root: Path | str | None = None, observed_utc: str | None = None) -> dict[str, object]:
    root_path = Path(root or ".")
    observed = observed_utc or _utc_now_text()
    ledger = _prepare_ledger(_read_csv(root_path / TOKEN_LEDGER))
    events = _prepare_events(_read_csv(root_path / STOCK_ADJUSTMENTS))
    receipts = _prepare_receipts(_read_csv(root_path / STOCK_RECEIPTS))
    fallback = ledger[ledger["is_fallback"]].copy()
    source_pool = ledger[(~ledger["is_fallback"]) & (ledger["cost_num"] > 0)].copy()
    if not source_pool.empty:
        source_pool["has_source_proof"] = (
            source_pool["source_batch_id"].map(_text).ne("")
            | source_pool["source_order_key"].map(_text).ne("")
            | source_pool["source"].map(_text).ne("")
        )
    source_groups = {
        key: group.copy()
        for key, group in source_pool.groupby(["sku_norm", "cost_key"], dropna=False)
    } if not source_pool.empty else {}
    receipt_groups = {
        key: group.copy()
        for key, group in receipts[receipts["cost_num"] > 0].groupby(["sku_norm", "cost_key"], dropna=False)
    } if not receipts.empty else {}

    rows: list[dict[str, str]] = []
    events_by_id = {row["event_id_norm"]: row for _, row in events.iterrows() if _text(row.get("event_id_norm", ""))}
    for _, token in fallback.iterrows():
        event_id = _event_id_from_token(token)
        event = events_by_id.get(event_id)
        receipt_rows = _receipt_matches(receipt_groups, token)
        source_candidates = _source_token_candidates(source_groups, token)
        state, label, expectation, task = _classify(len(receipt_rows), source_candidates, token.get("cost_per_unit", ""))
        source = source_candidates.iloc[0] if not source_candidates.empty else pd.Series(dtype=str)
        receipt = receipt_rows.iloc[0] if not receipt_rows.empty else pd.Series(dtype=str)
        rows.append(
            {
                "token_id": _text(token.get("token_id", "")),
                "seller_sku": _text(token.get("seller_sku", "")),
                "status": _text(token.get("status", "")),
                "event_id": event_id,
                "event_type": _text(event.get("event_type", "")) if event is not None else "",
                "event_disposition": _text(event.get("disposition", "")) if event is not None else "",
                "event_date": _text(event.get("event_date", "")) if event is not None else "",
                "cost_per_unit": _text(token.get("cost_per_unit", "")),
                "currency": _text(token.get("currency", "")),
                "created_at": _text(token.get("created_at", "")),
                "received_date": _text(token.get("received_date", "")),
                "cost_proof_state": state,
                "receipt_match_count": str(len(receipt_rows)),
                "source_token_match_count": str(len(source_candidates)),
                "source_token_id": _text(source.get("token_id", "")),
                "source_token_source": _text(source.get("source", "")),
                "source_token_batch_id": _text(source.get("source_batch_id", "")),
                "source_token_order_key": _text(source.get("source_order_key", "")),
                "receipt_batch_id": _text(receipt.get("batch_id", "")),
                "receipt_order_key": _text(receipt.get("order_key_text", "")),
                "manager_label": label,
                "manager_expectation": expectation,
                "bounded_worker_task": task,
                "retest_rule": "Rerun B070 and B MOT; row clears only when fallback cost has receipt/source proof or is parked for correction.",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "protected_before_apply": "1" if label in {"weak_fallback_cost", "not_yet_proven"} else "0",
            }
        )

    audit = pd.DataFrame(rows, columns=AUDIT_COLUMNS).fillna("")
    weak_rows = audit[audit["manager_label"].isin(["weak_fallback_cost", "not_yet_proven"])] if not audit.empty else audit
    summary_rows = [
        {"metric": "observed_utc", "value": observed},
        {"metric": "fallback_token_rows", "value": str(len(audit))},
        {"metric": "receipt_proved_rows", "value": str(int((audit["cost_proof_state"] == "fallback_cost_receipt_proved").sum()) if not audit.empty else 0)},
        {"metric": "source_token_proved_rows", "value": str(int((audit["cost_proof_state"] == "fallback_cost_source_token_proved").sum()) if not audit.empty else 0)},
        {"metric": "weak_latest_token_rows", "value": str(int((audit["cost_proof_state"] == "fallback_cost_weak_latest_token").sum()) if not audit.empty else 0)},
        {"metric": "unproved_rows", "value": str(int((audit["cost_proof_state"] == "fallback_cost_unproved").sum()) if not audit.empty else 0)},
        {"metric": "weak_or_unproved_rows", "value": str(len(weak_rows))},
        {"metric": "live_write_allowed_rows", "value": "0"},
        {"metric": "roi_or_restock_blocked_rows", "value": str(len(weak_rows))},
    ]
    summary = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS)
    return {"audit": audit, "summary": summary}


def write_fallback_token_cost_audit_outputs(result: dict[str, object], *, root: Path | str | None = None) -> dict[str, Path]:
    root_path = Path(root or ".")
    audit = result["audit"]
    summary = result["summary"]
    audit_path = root_path / AUDIT_OUT
    summary_path = root_path / SUMMARY_OUT
    safe_to_csv(audit, audit_path, index=False)
    safe_to_csv(summary, summary_path, index=False)
    return {"audit": audit_path, "summary": summary_path}


def main() -> None:
    result = build_fallback_token_cost_audit()
    paths = write_fallback_token_cost_audit_outputs(result)
    audit = result["audit"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}
    print(
        {
            "status": "ok",
            "fallback_token_rows": len(audit),
            "weak_or_unproved_rows": summary.get("weak_or_unproved_rows", "0"),
            "audit": str(paths["audit"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
