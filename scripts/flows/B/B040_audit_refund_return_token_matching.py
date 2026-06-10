from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.safe_file_writes import safe_to_csv


OUT = Path("out")
BRIDGE = OUT / "systems" / "B" / "refunds" / "b_refund_return_token_bridge.csv"
REFUND_TOKEN_EVENTS = OUT / "refund_token_events.csv"
STOCK_ADJUSTMENT_TOKEN_EVENTS = OUT / "stock_adjustment_token_events.csv"
STOCK_EVENTS_RAW = OUT / "stock_events_raw.csv"
TOKEN_RETURN_LEDGER = OUT / "token_return_ledger.csv"
OUT_AUDIT = OUT / "systems" / "B" / "refunds" / "b_return_token_matching_audit.csv"
OUT_SUMMARY = OUT / "systems" / "B" / "refunds" / "b_return_token_matching_audit_summary.csv"
NEARBY_DAYS = 14

AUDIT_COLUMNS = [
    "order_id",
    "sku",
    "proof_label",
    "mismatch_state",
    "refund_posted_date",
    "amazon_return_date",
    "amazon_return_disposition",
    "token_return_state",
    "refund_money_state",
    "return_cogs_recovered_exvat",
    "unsafe_original_return_tokens",
    "unsafe_original_token_ids",
    "b008_status",
    "b008_requested_qty",
    "b008_applied_qty",
    "b008_note",
    "b009_nearby_sellable_events",
    "b009_nearby_sellable_applied_qty",
    "b009_nearby_sellable_partial_events",
    "b009_nearby_unsellable_events",
    "b009_nearby_unsellable_applied_qty",
    "stock_raw_nearby_sellable_qty",
    "stock_raw_nearby_unsellable_qty",
    "return_cogs_rows_for_sku_nearby",
    "diagnosis",
    "future_proofing_need",
    "bounded_worker_task",
    "retest_rule",
    "protected_stop_rule",
]

SUMMARY_COLUMNS = ["metric", "value"]


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


def _num_text(value: object) -> str:
    number = _num(value)
    if abs(number) < 0.0000005:
        return "0"
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _parse_dt(value: object) -> pd.Timestamp | None:
    parsed = pd.to_datetime(_text(value), errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed


def _nearby_window(value: object, days: int = NEARBY_DAYS) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    center = _parse_dt(value)
    if center is None:
        return None, None
    return center - pd.Timedelta(days=days), center + pd.Timedelta(days=days)


def _date_filter(df: pd.DataFrame, date_col: str, center: object, days: int = NEARBY_DAYS) -> pd.DataFrame:
    if df.empty or date_col not in df.columns:
        return df.iloc[0:0].copy()
    start, end = _nearby_window(center, days)
    if start is None or end is None:
        return df.iloc[0:0].copy()
    work = df.copy()
    work["__dt"] = pd.to_datetime(work[date_col], errors="coerce", utc=True)
    return work[(work["__dt"] >= start) & (work["__dt"] <= end)].copy()


def _prepare_refund_events(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["order_id", "sku", "requested_qty", "applied_qty", "status", "note"]:
        if column not in work.columns:
            work[column] = ""
    work["order_id_norm"] = work["order_id"].map(_text)
    work["sku_norm"] = work["sku"].map(_norm_sku)
    return work


def _prepare_stock_adjustments(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["sku", "event_date", "disposition", "quantity", "applied_qty", "status", "note"]:
        if column not in work.columns:
            work[column] = ""
    work["sku_norm"] = work["sku"].map(_norm_sku)
    work["disposition_norm"] = work["disposition"].map(lambda value: _text(value).upper())
    work["quantity_num"] = pd.to_numeric(work["quantity"], errors="coerce").fillna(0.0)
    work["applied_qty_num"] = pd.to_numeric(work["applied_qty"], errors="coerce").fillna(0.0)
    return work


def _prepare_stock_raw(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["sku", "event_date", "disposition", "quantity"]:
        if column not in work.columns:
            work[column] = ""
    work["sku_norm"] = work["sku"].map(_norm_sku)
    work["disposition_norm"] = work["disposition"].map(lambda value: _text(value).upper())
    work["quantity_num"] = pd.to_numeric(work["quantity"], errors="coerce").fillna(0.0)
    return work


def _prepare_return_cogs(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["seller_sku", "return_date", "token_id"]:
        if column not in work.columns:
            work[column] = ""
    work["sku_norm"] = work["seller_sku"].map(_norm_sku)
    return work


def _refund_event_summary(refund_events: pd.DataFrame, order_id: str, sku: str) -> dict[str, str]:
    if refund_events.empty:
        return {"status": "missing", "requested": "0", "applied": "0", "note": "refund_token_events_missing"}
    rows = refund_events[(refund_events["order_id_norm"] == order_id) & (refund_events["sku_norm"] == sku)].copy()
    if rows.empty:
        return {"status": "missing", "requested": "0", "applied": "0", "note": "no B008 refund-token event for order/SKU"}
    requested = pd.to_numeric(rows.get("requested_qty", 0), errors="coerce").fillna(0.0).sum()
    applied = pd.to_numeric(rows.get("applied_qty", 0), errors="coerce").fillna(0.0).sum()
    statuses = sorted({_text(value) for value in rows.get("status", pd.Series(dtype=str)).tolist() if _text(value)})
    notes = sorted({_text(value) for value in rows.get("note", pd.Series(dtype=str)).tolist() if _text(value)})
    return {
        "status": "|".join(statuses) or "seen",
        "requested": _num_text(requested),
        "applied": _num_text(applied),
        "note": "|".join(notes),
    }


def _nearby_stock_summary(stock: pd.DataFrame, sku: str, center: object, *, sellable: bool) -> dict[str, str]:
    if stock.empty:
        return {"events": "0", "applied": "0", "partial": "0"}
    rows = _date_filter(stock[stock["sku_norm"] == sku].copy(), "event_date", center)
    if sellable:
        rows = rows[rows["disposition_norm"] == "SELLABLE"]
    else:
        rows = rows[(rows["disposition_norm"] != "SELLABLE") & (rows["disposition_norm"] != "")]
    positive = rows[rows["quantity_num"] > 0].copy()
    partial = positive[positive.get("status", "").astype(str).str.lower() == "partial"] if not positive.empty else positive
    return {
        "events": str(int(len(positive.index))),
        "applied": _num_text(float(positive["applied_qty_num"].sum()) if not positive.empty else 0.0),
        "partial": str(int(len(partial.index))),
    }


def _nearby_raw_qty(raw: pd.DataFrame, sku: str, center: object, *, sellable: bool) -> str:
    if raw.empty:
        return "0"
    rows = _date_filter(raw[raw["sku_norm"] == sku].copy(), "event_date", center)
    if sellable:
        rows = rows[rows["disposition_norm"] == "SELLABLE"]
    else:
        rows = rows[(rows["disposition_norm"] != "SELLABLE") & (rows["disposition_norm"] != "")]
    rows = rows[rows["quantity_num"] > 0]
    return _num_text(float(rows["quantity_num"].sum()) if not rows.empty else 0.0)


def _nearby_return_cogs_rows(return_cogs: pd.DataFrame, sku: str, center: object) -> str:
    if return_cogs.empty:
        return "0"
    rows = _date_filter(return_cogs[return_cogs["sku_norm"] == sku].copy(), "return_date", center)
    return str(int(len(rows.index)))


def _diagnose(
    *,
    bridge_row: pd.Series,
    b008: dict[str, str],
    sellable_stock: dict[str, str],
    unsellable_stock: dict[str, str],
    stock_raw_sellable_qty: str,
    stock_raw_unsellable_qty: str,
    return_cogs_rows: str,
) -> tuple[str, str, str]:
    label = _text(bridge_row.get("proof_label", ""))
    disposition = _text(bridge_row.get("amazon_return_disposition", "")).upper()
    b008_applied = _num(b008.get("applied", "0"))
    sellable_events = int(_num(sellable_stock.get("events", "0")))
    sellable_applied = _num(sellable_stock.get("applied", "0"))
    sellable_partial = int(_num(sellable_stock.get("partial", "0")))
    unsellable_events = int(_num(unsellable_stock.get("events", "0")))
    raw_sellable = _num(stock_raw_sellable_qty)
    raw_unsellable = _num(stock_raw_unsellable_qty)
    cogs_rows = int(_num(return_cogs_rows))
    cogs = _num(bridge_row.get("return_cogs_recovered_exvat", "0"))
    unsafe_original = int(_num(bridge_row.get("unsafe_original_return_tokens", "0")))

    if label == "returned_sellable_token_reused":
        if cogs <= 0 or cogs_rows == 0:
            return (
                "Sellable return token reuse is proved, but return COGS recovery is not manager-readable.",
                "Reusable stock and recovered cost must be traceable together before ROI uses stock recovery.",
                "Add return COGS trace proof for this reused returned token through the existing return ledger path.",
            )
        return (
            "Sellable return token reuse warning needs clearer bridge proof detail.",
            "Keep reused returned tokens tied to Amazon return proof, token proof, and COGS proof in one manager-readable row.",
            "Repair bridge proof mapping for this reused returned token before ROI uses stock recovery.",
        )

    if label == "returned_sellable_token_missing":
        if b008_applied <= 0:
            return (
                "B008 did not prove a returned-pending token for this refunded order/SKU.",
                "Make B008 refund-token marking order/SKU complete before B009 matching is trusted.",
                "Audit B008 allocations for this order/SKU and repair mapping only through the normal refund-token path.",
            )
        if sellable_events > 0 and sellable_applied <= 0:
            return (
                "B009 saw sellable stock movement near the Amazon return date but did not apply it to a returned-pending token.",
                "Add order-aware or retry-safe matching so sellable customer returns cannot be lost behind FIFO timing.",
                "Audit B009 returned_pending availability and retry rules for the SKU/date window.",
            )
        if sellable_events > 0 and sellable_partial > 0:
            return (
                "B009 applied only part of the nearby sellable stock movement.",
                "Keep partial sellable returns visible until the exact order/SKU is matched or explained.",
                "Create a B009 partial-return proof repair task for this SKU/date window.",
            )
        if cogs > 0 and cogs_rows == 0:
            return (
                "Refund bridge has recovered COGS but the token return ledger does not expose matching return rows.",
                "Make return COGS proof traceable by order/SKU/token, not just as a money total.",
                "Audit return COGS source mapping and add trace columns before ROI uses stock recovery.",
            )
        if raw_sellable > 0 and sellable_events == 0:
            return (
                "Raw stock evidence has sellable movement, but B009 event proof does not show it applied.",
                "Ensure raw stock return evidence always creates manager-readable B009 proof.",
                "Audit stock_events_raw to B009 event ingestion for this SKU/date window.",
            )
        return (
            "Amazon says sellable, but current B proof does not show a reusable returned token.",
            "Future proofing needs order/SKU-aware customer-return matching, not only SKU FIFO stock adjustments.",
            "Build an order-aware return matching repair plan before any token correction.",
        )

    if label == "token_reuse_without_amazon_return_proof":
        if unsafe_original > 0:
            return (
                "Original returned token has a live status, but reusable returned-stock proof is not clean for this order/SKU.",
                "Original sold tokens must not be treated as reusable returned stock; only the token-return duplicate path can prove stock recovery.",
                "Audit the original returned token lifecycle and keep it protected until B008/B009 state agrees with Amazon return proof.",
            )
        if raw_sellable > 0 or sellable_events > 0 or cogs_rows > 0:
            return (
                "Token/COGS evidence suggests stock came back, but the Amazon customer return report did not match the same order/SKU.",
                "Keep Amazon return coverage and token-return reuse reconciled by order/SKU before stock recovery affects ROI.",
                "Audit whether the stock movement is a customer return, another adjustment type, or an Amazon report coverage gap.",
            )
        if cogs > 0:
            return (
                "Refund bridge carries stock recovery money, but no Amazon customer-return or token event proof matched it.",
                "Make recovered COGS traceable to token-return events before ROI uses it.",
                "Audit B037 return COGS mapping and require order/SKU trace proof.",
            )
        return (
            "Bridge labelled token reuse without Amazon return proof, but supporting token evidence is not manager-readable.",
            "Avoid relying on bridge labels unless the underlying token event source is visible in MOT proof.",
            "Repair the bridge proof mapping so every warning includes the source event.",
        )

    if disposition != "SELLABLE" and _num(bridge_row.get("reusable_return_tokens", "0")) > 0:
        return (
            "Amazon says the return was not sellable, but B has reusable-token evidence for the same order/SKU.",
            "B009 must not let SKU FIFO sellable movements mask an order-level non-sellable customer return.",
            "Audit B009 FIFO matching against Amazon customer-return disposition before any token correction.",
        )

    return (
        "Warning needs manual proof classification.",
        "Keep this row warning-labelled until the bridge can explain it automatically.",
        "Improve the audit classifier for this proof pattern.",
    )


def build_matching_audit(*, root: Path | str | None = None) -> dict[str, object]:
    root_path = Path(root or ".")
    bridge = _read_csv(root_path / BRIDGE)
    refund_events = _prepare_refund_events(_read_csv(root_path / REFUND_TOKEN_EVENTS))
    stock_adjustments = _prepare_stock_adjustments(_read_csv(root_path / STOCK_ADJUSTMENT_TOKEN_EVENTS))
    stock_raw = _prepare_stock_raw(_read_csv(root_path / STOCK_EVENTS_RAW))
    return_cogs = _prepare_return_cogs(_read_csv(root_path / TOKEN_RETURN_LEDGER))

    if bridge.empty:
        audit = pd.DataFrame(columns=AUDIT_COLUMNS)
    else:
        warnings = bridge[bridge.get("mismatch_state", "").astype(str).str.lower() == "warning"].copy()
        rows: list[dict[str, str]] = []
        for _, row in warnings.iterrows():
            order_id = _text(row.get("order_id", ""))
            sku = _norm_sku(row.get("sku", ""))
            center = row.get("amazon_return_date", "") or row.get("refund_posted_date", "")
            b008 = _refund_event_summary(refund_events, order_id, sku)
            sellable_stock = _nearby_stock_summary(stock_adjustments, sku, center, sellable=True)
            unsellable_stock = _nearby_stock_summary(stock_adjustments, sku, center, sellable=False)
            raw_sellable_qty = _nearby_raw_qty(stock_raw, sku, center, sellable=True)
            raw_unsellable_qty = _nearby_raw_qty(stock_raw, sku, center, sellable=False)
            return_cogs_rows = _nearby_return_cogs_rows(return_cogs, sku, center)
            diagnosis, future_need, worker_task = _diagnose(
                bridge_row=row,
                b008=b008,
                sellable_stock=sellable_stock,
                unsellable_stock=unsellable_stock,
                stock_raw_sellable_qty=raw_sellable_qty,
                stock_raw_unsellable_qty=raw_unsellable_qty,
                return_cogs_rows=return_cogs_rows,
            )
            rows.append(
                {
                    "order_id": order_id,
                    "sku": sku,
                    "proof_label": _text(row.get("proof_label", "")),
                    "mismatch_state": _text(row.get("mismatch_state", "")),
                    "refund_posted_date": _text(row.get("refund_posted_date", "")),
                    "amazon_return_date": _text(row.get("amazon_return_date", "")),
                    "amazon_return_disposition": _text(row.get("amazon_return_disposition", "")),
                    "token_return_state": _text(row.get("token_return_state", "")),
                    "refund_money_state": _text(row.get("refund_money_state", "")),
                    "return_cogs_recovered_exvat": _num_text(row.get("return_cogs_recovered_exvat", "")),
                    "unsafe_original_return_tokens": _num_text(row.get("unsafe_original_return_tokens", "")),
                    "unsafe_original_token_ids": _text(row.get("unsafe_original_token_ids", "")),
                    "b008_status": b008["status"],
                    "b008_requested_qty": b008["requested"],
                    "b008_applied_qty": b008["applied"],
                    "b008_note": b008["note"],
                    "b009_nearby_sellable_events": sellable_stock["events"],
                    "b009_nearby_sellable_applied_qty": sellable_stock["applied"],
                    "b009_nearby_sellable_partial_events": sellable_stock["partial"],
                    "b009_nearby_unsellable_events": unsellable_stock["events"],
                    "b009_nearby_unsellable_applied_qty": unsellable_stock["applied"],
                    "stock_raw_nearby_sellable_qty": raw_sellable_qty,
                    "stock_raw_nearby_unsellable_qty": raw_unsellable_qty,
                    "return_cogs_rows_for_sku_nearby": return_cogs_rows,
                    "diagnosis": diagnosis,
                    "future_proofing_need": future_need,
                    "bounded_worker_task": worker_task,
                    "retest_rule": "Rerun B040, B038, and B MOT; row clears only when b_refund_return_token_bridge warning count drops or the row is explicitly exception-labelled.",
                    "protected_stop_rule": "Stop before token correction, B run/restart, Sheet write, DB alignment, output deletion, ROI/restocking use, or scope widening.",
                }
            )
        audit = pd.DataFrame(rows, columns=AUDIT_COLUMNS).fillna("")

    summary_values = {
        "audit_rows": str(len(audit)),
        "diagnosis_count": str(audit["diagnosis"].nunique() if not audit.empty else 0),
        "b008_missing_or_zero_applied": str(
            int((pd.to_numeric(audit.get("b008_applied_qty", pd.Series(dtype=str)), errors="coerce").fillna(0.0) <= 0).sum())
            if not audit.empty
            else 0
        ),
        "sellable_missing_rows": str(int((audit.get("proof_label", pd.Series(dtype=str)) == "returned_sellable_token_missing").sum()) if not audit.empty else 0),
        "token_reuse_without_amazon_rows": str(int((audit.get("proof_label", pd.Series(dtype=str)) == "token_reuse_without_amazon_return_proof").sum()) if not audit.empty else 0),
        "original_return_live_status_conflict_rows": str(
            int((pd.to_numeric(audit.get("unsafe_original_return_tokens", pd.Series(dtype=str)), errors="coerce").fillna(0.0) > 0).sum())
            if not audit.empty
            else 0
        ),
        "non_sellable_reuse_conflict_rows": str(
            int(
                (
                    (audit.get("amazon_return_disposition", pd.Series(dtype=str)).astype(str).str.upper() != "SELLABLE")
                    & (audit.get("proof_label", pd.Series(dtype=str)) == "returned_unsellable_no_reuse")
                    & (audit.get("mismatch_state", pd.Series(dtype=str)) == "warning")
                ).sum()
            )
            if not audit.empty
            else 0
        ),
    }
    summary = pd.DataFrame([{"metric": key, "value": value} for key, value in summary_values.items()], columns=SUMMARY_COLUMNS)
    return {
        "audit": audit,
        "summary": summary,
        "audit_path": root_path / OUT_AUDIT,
        "summary_path": root_path / OUT_SUMMARY,
    }


def write_matching_audit_outputs(result: dict[str, object]) -> dict[str, Path]:
    audit_path = Path(result["audit_path"])
    summary_path = Path(result["summary_path"])
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    safe_to_csv(result["audit"], audit_path, index=False)
    safe_to_csv(result["summary"], summary_path, index=False)
    return {"audit": audit_path, "summary": summary_path}


def main() -> None:
    result = build_matching_audit()
    paths = write_matching_audit_outputs(result)
    audit = result["audit"]
    summary = result["summary"]
    values = {row["metric"]: row["value"] for _, row in summary.iterrows()} if not summary.empty else {}
    print(
        {
            "status": "success",
            "audit_rows": int(len(audit)),
            "diagnosis_count": int(_num(values.get("diagnosis_count", "0"))),
            "audit": str(paths["audit"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
