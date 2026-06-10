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
PREVIEW = OUT / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv"
CUSTOMER_RETURNS = OUT / "systems" / "B" / "refunds" / "b_fba_customer_returns.csv"
CUSTOMER_RETURNS_SUMMARY = OUT / "systems" / "B" / "refunds" / "b_fba_customer_returns_summary.csv"
TOKEN_LEDGER = OUT / "token_ledger_live.csv"
STOCK_ADJUSTMENTS = OUT / "stock_adjustment_token_events.csv"
STOCK_RAW = OUT / "stock_events_raw.csv"
OUT_AUDIT = OUT / "systems" / "B" / "refunds" / "b_amazon_return_coverage_audit.csv"
OUT_SUMMARY = OUT / "systems" / "B" / "refunds" / "b_amazon_return_coverage_audit_summary.csv"

NEARBY_DAYS = 45

AUDIT_COLUMNS = [
    "order_id",
    "sku",
    "refund_posted_date",
    "repair_lane",
    "repair_readiness",
    "exact_customer_return_rows",
    "order_only_customer_return_rows",
    "sku_customer_return_rows",
    "nearby_sku_customer_return_rows_45d",
    "customer_return_match_state",
    "customer_return_report_window_state",
    "customer_return_report_start_utc",
    "customer_return_report_end_utc",
    "reusable_return_token_ids",
    "returned_complete_token_ids",
    "source_event_ids",
    "source_event_kind",
    "source_event_total_rows",
    "source_event_unique_skus",
    "source_event_total_quantity",
    "source_event_order_level_safe",
    "stock_adjustment_rows",
    "stock_raw_rows",
    "stock_signal_state",
    "coverage_conclusion",
    "manager_coverage_label",
    "manager_expectation",
    "bounded_worker_task",
    "retest_rule",
    "preview_live_write_allowed",
    "roi_or_restock_use_allowed",
    "sellerboard_final_truth_allowed",
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


def _unique(values: list[object]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _join(values: list[object]) -> str:
    return "|".join(_unique(values))


def _parse_date(value: object) -> pd.Timestamp | None:
    parsed = pd.to_datetime(_text(value), errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed


def _prepare_preview(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["order_id", "sku", "refund_posted_date", "repair_lane", "repair_readiness"]:
        if column not in work.columns:
            work[column] = ""
    work["order_id_norm"] = work["order_id"].map(_text)
    work["sku_norm"] = work["sku"].map(_norm_sku)
    return work[
        (work["repair_lane"].astype(str).str.strip() == "amazon_return_coverage_review")
        & (work["order_id_norm"] != "")
        & (work["sku_norm"] != "")
    ].copy()


def _prepare_customer_returns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["order-id", "order_id", "sku", "seller-sku", "return-date"]:
        if column not in work.columns:
            work[column] = ""
    order_source = work["order-id"] if "order-id" in work.columns else work["order_id"]
    sku_source = work["sku"] if "sku" in work.columns else work["seller-sku"]
    work["order_id_norm"] = order_source.map(_text)
    work["sku_norm"] = sku_source.map(_norm_sku)
    work["return_dt"] = pd.to_datetime(work["return-date"], errors="coerce", utc=True)
    return work[(work["order_id_norm"] != "") & (work["sku_norm"] != "")].copy()


def _summary_value(summary: pd.DataFrame, metric: str) -> str:
    if summary.empty or "metric" not in summary.columns or "value" not in summary.columns:
        return ""
    rows = summary[summary["metric"].astype(str).str.strip() == metric]
    if rows.empty:
        return ""
    return _text(rows.iloc[0].get("value", ""))


def _report_window(summary: pd.DataFrame) -> tuple[str, str]:
    return _summary_value(summary, "start_utc"), _summary_value(summary, "end_utc")


def _report_window_state(summary: pd.DataFrame, refund_date: object) -> tuple[str, str, str]:
    start_text, end_text = _report_window(summary)
    if not start_text or not end_text:
        return "return_report_window_missing", start_text, end_text
    refund_dt = _parse_date(refund_date)
    start_dt = _parse_date(start_text)
    end_dt = _parse_date(end_text)
    if refund_dt is None:
        return "refund_date_not_parseable", start_text, end_text
    if start_dt is None or end_dt is None:
        return "return_report_window_not_parseable", start_text, end_text
    if refund_dt < start_dt:
        return "refund_before_return_report_window", start_text, end_text
    if refund_dt > end_dt:
        return "refund_after_return_report_window", start_text, end_text
    return "return_report_window_covers_refund_date", start_text, end_text


def _prepare_token_ledger(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in [
        "token_id",
        "seller_sku",
        "status",
        "return_order_id",
        "last_return_order_id",
        "allocated_order_id",
        "notes",
    ]:
        if column not in work.columns:
            work[column] = ""
    work["sku_norm"] = work["seller_sku"].map(_norm_sku)
    work["status_norm"] = work["status"].map(lambda value: _text(value).lower())
    work["return_order_norm"] = work["return_order_id"].map(_text)
    work["last_return_order_norm"] = work["last_return_order_id"].map(_text)
    work["allocated_order_norm"] = work["allocated_order_id"].map(_text)
    work["notes_norm"] = work["notes"].map(lambda value: _text(value).lower())
    return work


def _prepare_stock_adjustments(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["event_id", "sku", "event_date", "event_type", "disposition"]:
        if column not in work.columns:
            work[column] = ""
    work["event_id_base"] = work["event_id"].map(_event_base)
    work["sku_norm"] = work["sku"].map(_norm_sku)
    return work


def _prepare_stock_raw(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    for column in ["event_id", "sku", "event_date", "event_type", "disposition"]:
        if column not in work.columns:
            work[column] = ""
    work["event_id_base"] = work["event_id"].map(_event_base)
    work["sku_norm"] = work["sku"].map(_norm_sku)
    return work


def _event_base(value: object) -> str:
    text = _text(value)
    if not text:
        return ""
    return re.sub(r"-retry\d+$", "", text)


def _event_ids_from_notes(values: list[object]) -> list[str]:
    ids: list[str] = []
    for value in values:
        text = _text(value)
        for marker in ["return_sellable_dup:", "return_closed:"]:
            if marker in text:
                event = text.split(marker, 1)[1].split(";", 1)[0].strip()
                if event:
                    ids.append(event)
    return _unique(ids)


def _token_rows(ledger: pd.DataFrame, order_id: str, sku: str) -> pd.DataFrame:
    if ledger.empty:
        return pd.DataFrame()
    rows = ledger[ledger["sku_norm"] == sku].copy()
    return rows[
        (rows["return_order_norm"] == order_id)
        | (rows["last_return_order_norm"] == order_id)
        | (rows["allocated_order_norm"] == order_id)
    ].copy()


def _nearby_customer_return_count(rows: pd.DataFrame, sku: str, center: object) -> int:
    if rows.empty:
        return 0
    center_dt = _parse_date(center)
    if center_dt is None:
        return 0
    sku_rows = rows[rows["sku_norm"] == sku].copy()
    if sku_rows.empty:
        return 0
    start = center_dt - pd.Timedelta(days=NEARBY_DAYS)
    end = center_dt + pd.Timedelta(days=NEARBY_DAYS)
    return int(((sku_rows["return_dt"] >= start) & (sku_rows["return_dt"] <= end)).sum())


def _event_matches(df: pd.DataFrame, event_ids: list[str], sku: str) -> pd.DataFrame:
    if df.empty or not event_ids:
        return pd.DataFrame()
    bases = {_event_base(event_id) for event_id in event_ids if _event_base(event_id)}
    return df[(df["sku_norm"] == sku) & (df["event_id_base"].isin(bases))].copy()


def _event_scope(
    adjustments: pd.DataFrame,
    raw_stock: pd.DataFrame,
    event_ids: list[str],
    *,
    exact_return_rows: int,
) -> dict[str, str]:
    bases = {_event_base(event_id) for event_id in event_ids if _event_base(event_id)}
    if not bases:
        return {
            "kind": "no_source_event_trace",
            "rows": "0",
            "unique_skus": "0",
            "quantity": "0",
            "order_level_safe": "1" if exact_return_rows > 0 else "0",
        }
    frames: list[pd.DataFrame] = []
    for source in [adjustments, raw_stock]:
        if source.empty or "event_id_base" not in source.columns:
            continue
        rows = source[source["event_id_base"].isin(bases)].copy()
        if not rows.empty:
            frames.append(rows)
    if not frames:
        return {
            "kind": "source_event_not_manager_readable",
            "rows": "0",
            "unique_skus": "0",
            "quantity": "0",
            "order_level_safe": "1" if exact_return_rows > 0 else "0",
        }
    combined = pd.concat(frames, ignore_index=True).fillna("")
    event_types = {str(value).strip().lower() for value in combined.get("event_type", pd.Series(dtype=str)).tolist() if str(value).strip()}
    quantity = pd.to_numeric(combined.get("quantity", pd.Series(dtype=str)), errors="coerce").fillna(0).sum()
    unique_skus = combined.get("sku_norm", pd.Series(dtype=str)).astype(str).str.strip().replace("", pd.NA).dropna().nunique()
    if exact_return_rows > 0:
        kind = "customer_return_order_sku_proved"
    elif event_types & {"receipts", "adjustments"}:
        kind = "inventory_ledger_signal_not_order_return"
    else:
        kind = "source_event_signal_not_order_return"
    return {
        "kind": kind,
        "rows": str(len(combined)),
        "unique_skus": str(int(unique_skus)),
        "quantity": f"{float(quantity):.6f}".rstrip("0").rstrip(".") if abs(float(quantity)) > 0.0000005 else "0",
        "order_level_safe": "1" if exact_return_rows > 0 else "0",
    }


def _classify(
    *,
    exact_returns: int,
    order_returns: int,
    nearby_sku_returns: int,
    reusable_tokens: list[str],
    adjustment_rows: int,
    raw_rows: int,
) -> tuple[str, str, str, str, str]:
    if exact_returns > 0:
        return (
            "customer_return_order_proved",
            "customer_return_order_sku_match",
            "Amazon customer-return proof exists for this order/SKU; if the bridge still warns, repair the bridge reader.",
            "Rerun B038/B041/B052 and B MOT; the row should leave the missing-Amazon-return lane.",
            "No Luke decision unless a live token correction is proposed.",
        )
    if order_returns > 0:
        return (
            "customer_return_order_seen_sku_mismatch",
            "customer_return_order_seen_but_sku_different",
            "Amazon has the order in the customer-return report, but not with the same SKU; repair SKU/order mapping before trusting stock recovery.",
            "Compare the order item mapping, then rerun B038/B041/B052 and B MOT.",
            "No Luke decision unless Codex proposes accepting mismatched SKU proof.",
        )
    if adjustment_rows > 0 or raw_rows > 0:
        return (
            "stock_adjustment_without_customer_return_order_proof",
            "stock_signal_seen_but_customer_return_order_missing",
            "Stock movement exists, but it is not order-level customer-return proof. Keep stock recovery blocked from ROI until proved or explicitly excepted.",
            "Use this audit to build a smaller proof packet; row clears only after Amazon customer-return proof or an approved non-customer-return exception exists.",
            "Luke decides only if Codex proposes treating stock-adjustment proof as enough for reusable stock recovery.",
        )
    if nearby_sku_returns > 0:
        return (
            "nearby_sku_customer_return_but_order_missing",
            "same_sku_return_seen_but_order_missing",
            "Amazon shows nearby customer returns for the SKU, but not this order. Do not borrow SKU-level proof for an order-level stock decision.",
            "Investigate order/SKU mapping and return report coverage, then rerun B052 and B MOT.",
            "Luke decides only if Codex proposes accepting SKU-level evidence as an exception.",
        )
    if reusable_tokens:
        return (
            "token_reuse_without_external_amazon_return_evidence",
            "token_signal_only",
            "The token route says stock was reused, but Amazon customer-return and stock-adjustment evidence are not manager-readable.",
            "Repair source-event trace proof before any live stock recovery is trusted.",
            "Luke decides only if a live token correction or exception is proposed.",
        )
    return (
        "no_amazon_or_token_coverage_evidence",
        "no_external_evidence",
        "No external Amazon coverage proof is visible for this row. Keep it blocked.",
        "Investigate the source row and keep it out of stock recovery until proved.",
        "No Luke decision unless Codex proposes an exception.",
    )


def _manager_coverage_label(conclusion: str) -> str:
    if conclusion == "customer_return_order_proved":
        return "exact_amazon_return_proved"
    if conclusion == "stock_adjustment_without_customer_return_order_proof":
        return "stock_adjustment_only"
    if conclusion == "nearby_sku_customer_return_but_order_missing":
        return "nearby_sku_only"
    if conclusion == "token_reuse_without_external_amazon_return_evidence":
        return "token_only"
    return "not_yet_proven"


def build_amazon_return_coverage_audit(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
) -> dict[str, pd.DataFrame]:
    root_path = Path(root or ".")
    observed = observed_utc or _utc_now_text()
    preview = _prepare_preview(_read_csv(root_path / PREVIEW))
    customer_returns = _prepare_customer_returns(_read_csv(root_path / CUSTOMER_RETURNS))
    customer_returns_summary = _read_csv(root_path / CUSTOMER_RETURNS_SUMMARY)
    ledger = _prepare_token_ledger(_read_csv(root_path / TOKEN_LEDGER))
    adjustments = _prepare_stock_adjustments(_read_csv(root_path / STOCK_ADJUSTMENTS))
    raw_stock = _prepare_stock_raw(_read_csv(root_path / STOCK_RAW))

    rows: list[dict[str, str]] = []
    for _, preview_row in preview.iterrows():
        order_id = _text(preview_row.get("order_id_norm", ""))
        sku = _norm_sku(preview_row.get("sku_norm", ""))
        refund_date = _text(preview_row.get("refund_posted_date", ""))
        exact_returns = customer_returns[(customer_returns["order_id_norm"] == order_id) & (customer_returns["sku_norm"] == sku)]
        order_returns = customer_returns[customer_returns["order_id_norm"] == order_id]
        sku_returns = customer_returns[customer_returns["sku_norm"] == sku]
        nearby_count = _nearby_customer_return_count(customer_returns, sku, refund_date)
        token_rows = _token_rows(ledger, order_id, sku)
        reusable_rows = token_rows[token_rows["notes_norm"].str.contains("return_sellable_dup", na=False)] if not token_rows.empty else token_rows
        returned_complete_rows = token_rows[token_rows["status_norm"] == "returned_complete"] if not token_rows.empty else token_rows
        event_ids = _event_ids_from_notes(token_rows.get("notes", pd.Series(dtype=str)).tolist() if not token_rows.empty else [])
        adjustment_matches = _event_matches(adjustments, event_ids, sku)
        raw_matches = _event_matches(raw_stock, event_ids, sku)
        report_state, report_start, report_end = _report_window_state(customer_returns_summary, refund_date)
        event_scope = _event_scope(
            adjustments,
            raw_stock,
            event_ids,
            exact_return_rows=len(exact_returns),
        )
        conclusion, stock_state, expectation, retest, luke_rule = _classify(
            exact_returns=len(exact_returns),
            order_returns=len(order_returns),
            nearby_sku_returns=nearby_count,
            reusable_tokens=reusable_rows.get("token_id", pd.Series(dtype=str)).tolist() if not reusable_rows.empty else [],
            adjustment_rows=len(adjustment_matches),
            raw_rows=len(raw_matches),
        )
        manager_label = _manager_coverage_label(conclusion)
        rows.append(
            {
                "order_id": order_id,
                "sku": sku,
                "refund_posted_date": refund_date,
                "repair_lane": _text(preview_row.get("repair_lane", "")),
                "repair_readiness": _text(preview_row.get("repair_readiness", "")),
                "exact_customer_return_rows": str(len(exact_returns)),
                "order_only_customer_return_rows": str(len(order_returns)),
                "sku_customer_return_rows": str(len(sku_returns)),
                "nearby_sku_customer_return_rows_45d": str(nearby_count),
                "customer_return_match_state": "exact_order_sku_match" if len(exact_returns) else "missing_order_sku_match",
                "customer_return_report_window_state": report_state,
                "customer_return_report_start_utc": report_start,
                "customer_return_report_end_utc": report_end,
                "reusable_return_token_ids": _join(reusable_rows.get("token_id", pd.Series(dtype=str)).tolist() if not reusable_rows.empty else []),
                "returned_complete_token_ids": _join(
                    returned_complete_rows.get("token_id", pd.Series(dtype=str)).tolist() if not returned_complete_rows.empty else []
                ),
                "source_event_ids": _join(event_ids),
                "source_event_kind": event_scope["kind"],
                "source_event_total_rows": event_scope["rows"],
                "source_event_unique_skus": event_scope["unique_skus"],
                "source_event_total_quantity": event_scope["quantity"],
                "source_event_order_level_safe": event_scope["order_level_safe"],
                "stock_adjustment_rows": str(len(adjustment_matches)),
                "stock_raw_rows": str(len(raw_matches)),
                "stock_signal_state": stock_state,
                "coverage_conclusion": conclusion,
                "manager_coverage_label": manager_label,
                "manager_expectation": expectation,
                "bounded_worker_task": "Investigate Amazon customer-return coverage versus stock-adjustment-only evidence; do not change token stock.",
                "retest_rule": retest,
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
                "protected_before_apply": "1",
            }
        )

    audit = pd.DataFrame(rows, columns=AUDIT_COLUMNS).fillna("")
    unclassified = audit[audit["coverage_conclusion"].astype(str).str.strip() == ""] if not audit.empty else audit
    unsafe_rows = 0
    if not audit.empty:
        unsafe_rows = int(
            (audit["preview_live_write_allowed"].astype(str).str.strip() != "0").sum()
            + (audit["roi_or_restock_use_allowed"].astype(str).str.strip() != "0").sum()
            + (audit["sellerboard_final_truth_allowed"].astype(str).str.strip() != "0").sum()
        )
    status = "ok"
    if preview.empty:
        status = "not_checked"
    elif len(unclassified) or unsafe_rows:
        status = "fail"
    summary_values = {
        "status": status,
        "observed_utc": observed,
        "audit_rows": str(len(audit)),
        "exact_customer_return_matched_rows": str(int((audit["exact_customer_return_rows"].astype(str) != "0").sum()) if not audit.empty else 0),
        "return_report_window_covered_rows": str(
            int((audit["customer_return_report_window_state"] == "return_report_window_covers_refund_date").sum()) if not audit.empty else 0
        ),
        "inventory_ledger_signal_not_order_return_rows": str(
            int((audit["source_event_kind"] == "inventory_ledger_signal_not_order_return").sum()) if not audit.empty else 0
        ),
        "source_event_order_level_safe_rows": str(
            int((audit["source_event_order_level_safe"].astype(str).str.strip() == "1").sum()) if not audit.empty else 0
        ),
        "stock_adjustment_without_customer_return_rows": str(
            int((audit["coverage_conclusion"] == "stock_adjustment_without_customer_return_order_proof").sum()) if not audit.empty else 0
        ),
        "manager_exact_amazon_return_proved_rows": str(
            int((audit["manager_coverage_label"] == "exact_amazon_return_proved").sum()) if not audit.empty else 0
        ),
        "manager_stock_adjustment_only_rows": str(
            int((audit["manager_coverage_label"] == "stock_adjustment_only").sum()) if not audit.empty else 0
        ),
        "manager_token_only_rows": str(
            int((audit["manager_coverage_label"] == "token_only").sum()) if not audit.empty else 0
        ),
        "manager_nearby_sku_only_rows": str(
            int((audit["manager_coverage_label"] == "nearby_sku_only").sum()) if not audit.empty else 0
        ),
        "manager_not_yet_proven_rows": str(
            int((audit["manager_coverage_label"] == "not_yet_proven").sum()) if not audit.empty else 0
        ),
        "nearby_sku_only_rows": str(
            int((audit["coverage_conclusion"] == "nearby_sku_customer_return_but_order_missing").sum()) if not audit.empty else 0
        ),
        "token_signal_only_rows": str(
            int((audit["coverage_conclusion"] == "token_reuse_without_external_amazon_return_evidence").sum()) if not audit.empty else 0
        ),
        "no_external_evidence_rows": str(
            int((audit["coverage_conclusion"] == "no_amazon_or_token_coverage_evidence").sum()) if not audit.empty else 0
        ),
        "unclassified_rows": str(len(unclassified)),
        "unsafe_rows": str(unsafe_rows),
        "live_write_allowed_rows": str(int((audit["preview_live_write_allowed"].astype(str).str.strip() != "0").sum()) if not audit.empty else 0),
        "roi_or_restock_allowed_rows": str(int((audit["roi_or_restock_use_allowed"].astype(str).str.strip() != "0").sum()) if not audit.empty else 0),
        "sellerboard_final_truth_allowed_rows": str(
            int((audit["sellerboard_final_truth_allowed"].astype(str).str.strip() != "0").sum()) if not audit.empty else 0
        ),
    }
    summary = pd.DataFrame([{"metric": key, "value": value} for key, value in summary_values.items()], columns=SUMMARY_COLUMNS)
    return {"audit": audit, "summary": summary}


def write_amazon_return_coverage_audit_outputs(
    result: dict[str, pd.DataFrame],
    *,
    root: Path | str | None = None,
) -> dict[str, Path]:
    root_path = Path(root or ".")
    audit_path = root_path / OUT_AUDIT
    summary_path = root_path / OUT_SUMMARY
    safe_to_csv(result["audit"], audit_path, index=False)
    safe_to_csv(result["summary"], summary_path, index=False)
    return {"audit": audit_path, "summary": summary_path}


def main() -> None:
    result = build_amazon_return_coverage_audit()
    paths = write_amazon_return_coverage_audit_outputs(result)
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}
    print(
        {
            "status": summary.get("status", ""),
            "audit_rows": summary.get("audit_rows", "0"),
            "exact_customer_return_matched_rows": summary.get("exact_customer_return_matched_rows", "0"),
            "stock_adjustment_without_customer_return_rows": summary.get("stock_adjustment_without_customer_return_rows", "0"),
            "unclassified_rows": summary.get("unclassified_rows", "0"),
            "audit": str(paths["audit"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
