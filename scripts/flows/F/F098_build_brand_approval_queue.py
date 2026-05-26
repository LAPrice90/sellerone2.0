from __future__ import annotations

import argparse
import hashlib
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._contract_io import read_f_contract_df, write_f_contract_df
from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract


APPROVAL_ISSUE_MARKERS = ("18304", "approval", "approve", "brand")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    text = str(value or "").strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _hash_id(prefix: str, *parts: object, length: int = 16) -> str:
    raw = "|".join(_normalize_text(part) for part in parts)
    return f"{prefix}_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:length]}"


def _money(value: object) -> str:
    text = _normalize_text(value).replace(",", "")
    if text == "":
        return ""
    try:
        parsed = float(text)
    except Exception:
        return ""
    if parsed < 0:
        return ""
    return f"{parsed:.2f}"


def _positive_int(value: object) -> str:
    text = _normalize_text(value).replace(",", "")
    if text == "":
        return ""
    try:
        parsed = int(float(text))
    except Exception:
        return ""
    if parsed <= 0:
        return ""
    return str(parsed)


def _risk_total(quantity: object, unit_cost: object, existing_total: object = "") -> str:
    total = _money(existing_total)
    if total:
        return total
    qty_text = _positive_int(quantity)
    unit_text = _money(unit_cost)
    if not qty_text or not unit_text:
        return ""
    return f"{int(qty_text) * float(unit_text):.2f}"


def _parse_utc(value: str) -> datetime:
    text = _normalize_text(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except Exception:
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _plus_days(value: str, days: int) -> str:
    return (_parse_utc(value) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _latest_by_key(df: pd.DataFrame, *, key_column: str, time_column: str, id_column: str) -> dict[str, dict[str, str]]:
    if df.empty or key_column not in df.columns:
        return {}
    work = df.copy()
    work["_sort"] = pd.to_datetime(work.get(time_column, ""), errors="coerce", utc=True)
    work = work.sort_values(by=["_sort", id_column], ascending=[True, True], kind="stable")
    latest: dict[str, dict[str, str]] = {}
    for _, row in work.iterrows():
        row_dict = {key: _normalize_text(value) for key, value in row.to_dict().items()}
        key = row_dict.get(key_column, "")
        if key:
            latest[key] = row_dict
    return latest


def _latest_decisions(events_df: pd.DataFrame) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    if events_df.empty:
        return {}, {}
    by_queue = _latest_by_key(events_df, key_column="queue_id", time_column="event_utc", id_column="event_id")
    by_draft = _latest_by_key(events_df, key_column="draft_id", time_column="event_utc", id_column="event_id")
    return by_queue, by_draft


def _approval_status_from_decision(decision: str) -> tuple[str, str]:
    value = _normalize_text(decision).lower()
    if value == "fail_now":
        return "failed_invoice_risk", "no_auto_recheck"
    if value == "park":
        return "parked_invoice_or_brand_risk", "same_brand_or_manual_recheck"
    if value == "try_seller_central":
        return "seller_central_approval_pending", "operator_marks_attempt_complete"
    if value == "invoice_planned":
        return "invoice_required", "invoice_uploaded"
    if value == "invoice_uploaded":
        return "invoice_uploaded_recheck_required", "approved_recheck"
    if value == "approved_recheck":
        return "approval_recheck_required", "approved_recheck"
    return "approval_required", "operator_decision_required"


def _is_approval_readback_event(row: dict[str, str]) -> bool:
    status = _normalize_text(row.get("readback_status", "")).lower()
    notes = _normalize_text(row.get("notes", "")).lower()
    if status != "blocking_issues":
        return False
    return any(marker in notes for marker in APPROVAL_ISSUE_MARKERS)


def _draft_lookup(drafts_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for _, row in drafts_df.iterrows():
        row_dict = {key: _normalize_text(value) for key, value in row.to_dict().items()}
        draft_id = row_dict.get("draft_id", "")
        if draft_id:
            out[draft_id] = row_dict
    return out


def _intake_lookup(intake_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for _, row in intake_df.iterrows():
        row_dict = {key: _normalize_text(value) for key, value in row.to_dict().items()}
        for key_name in ("candidate_id", "intake_id"):
            key = row_dict.get(key_name, "")
            if key:
                out[key] = row_dict
    return out


def _enrich_source(source: dict[str, str], intake_by_key: dict[str, dict[str, str]]) -> dict[str, str]:
    candidate_id = _normalize_text(source.get("candidate_id", ""))
    intake = intake_by_key.get(candidate_id, {})
    if not intake:
        return source
    enriched = dict(source)
    for field in ("brand", "amazon_title", "supplier_cost_gbp", "supplier_id", "supplier_sku"):
        if _normalize_text(enriched.get(field, "")) == "":
            enriched[field] = _normalize_text(intake.get(field, ""))
    return enriched


def _approval_sources(root: Path) -> list[dict[str, str]]:
    restrictions = read_f_contract_df(root, "amazon_listing_restrictions_live")
    readbacks = read_f_contract_df(root, "amazon_listing_readback_events")
    drafts = read_f_contract_df(root, "amazon_listing_drafts_live")
    intake = read_f_contract_df(root, "amazon_listing_intake_live")
    drafts_by_id = _draft_lookup(drafts)
    intake_by_key = _intake_lookup(intake)

    sources: list[dict[str, str]] = []
    for _, row in restrictions.iterrows():
        restriction = {key: _normalize_text(value) for key, value in row.to_dict().items()}
        if restriction.get("restriction_status", "") != "approval_required":
            continue
        draft = drafts_by_id.get(restriction.get("draft_id", ""), {})
        sources.append(
            _enrich_source(
                {
                    **draft,
                    **restriction,
                    "source_kind": "restriction",
                    "source_event_id": restriction.get("latest_restriction_event_id", ""),
                    "source_observed_utc": restriction.get("latest_restriction_utc", restriction.get("observed_utc", "")),
                    "reason_code": restriction.get("reason_code", "") or "APPROVAL_REQUIRED",
                    "reason_message": restriction.get("reason_message", ""),
                    "approval_link": restriction.get("approval_link", ""),
                },
                intake_by_key,
            )
        )

    latest_readback = _latest_by_key(readbacks, key_column="draft_id", time_column="event_utc", id_column="event_id")
    for draft_id, readback in latest_readback.items():
        if not _is_approval_readback_event(readback):
            continue
        draft = drafts_by_id.get(draft_id, {})
        sources.append(
            _enrich_source(
                {
                    **draft,
                    "draft_id": draft_id,
                    "candidate_id": readback.get("candidate_id", draft.get("candidate_id", "")),
                    "expected_seller_sku": readback.get("expected_seller_sku", draft.get("expected_seller_sku", "")),
                    "asin": readback.get("asin", draft.get("asin", "")),
                    "marketplace_id": readback.get("marketplace_id", draft.get("marketplace_id", "")),
                    "source_kind": "readback_issue",
                    "source_event_id": readback.get("event_id", ""),
                    "source_observed_utc": readback.get("event_utc", ""),
                    "reason_code": "APPROVAL_REQUIRED",
                    "reason_message": readback.get("notes", "Amazon listing read-back reported approval-required issue."),
                    "approval_link": "",
                },
                intake_by_key,
            )
        )
    return sources


def _queue_id(source: dict[str, str]) -> str:
    return _hash_id(
        "brand_approval",
        source.get("draft_id", ""),
        source.get("candidate_id", ""),
        source.get("asin", ""),
        source.get("marketplace_id", ""),
    )


def _apply_decision_defaults(
    *,
    observed_utc: str,
    source: dict[str, str],
    decision: dict[str, str],
) -> dict[str, str]:
    operator_decision = _normalize_text(decision.get("operator_decision", ""))
    approval_status, default_recheck = _approval_status_from_decision(operator_decision)
    cooldown = _normalize_text(decision.get("cooldown_until_utc", ""))
    if operator_decision == "park" and cooldown == "":
        cooldown = _plus_days(observed_utc, 365)
    invoice_qty = _positive_int(decision.get("invoice_required_quantity", ""))
    unit_cost = _money(decision.get("invoice_unit_cost_gbp", source.get("supplier_cost_gbp", "")))
    total_risk = _risk_total(invoice_qty, unit_cost, decision.get("invoice_total_risk_gbp", ""))
    return {
        "approval_status": approval_status,
        "operator_decision": operator_decision,
        "decision_reason": _normalize_text(decision.get("decision_reason", "")),
        "invoice_required_quantity": invoice_qty,
        "invoice_unit_cost_gbp": unit_cost,
        "invoice_total_risk_gbp": total_risk,
        "cooldown_until_utc": cooldown,
        "recheck_trigger": _normalize_text(decision.get("recheck_trigger", "")) or default_recheck,
        "approval_application_status": _normalize_text(decision.get("approval_application_status", "")),
        "invoice_artifact_reference": _normalize_text(decision.get("invoice_artifact_reference", "")),
    }


def _queue_row(
    *,
    observed_utc: str,
    source: dict[str, str],
    decision: dict[str, str],
) -> dict[str, str]:
    queue_id = _queue_id(source)
    decision_fields = _apply_decision_defaults(observed_utc=observed_utc, source=source, decision=decision)
    return {
        "observed_utc": observed_utc,
        "queue_id": queue_id,
        "draft_id": _normalize_text(source.get("draft_id", "")),
        "candidate_id": _normalize_text(source.get("candidate_id", "")),
        "expected_seller_sku": _normalize_text(source.get("expected_seller_sku", "")),
        "asin": _normalize_text(source.get("asin", "")).upper(),
        "marketplace_id": _normalize_text(source.get("marketplace_id", "")),
        "brand": _normalize_text(source.get("brand", "")),
        "amazon_title": _normalize_text(source.get("amazon_title", "")),
        "approval_status": decision_fields["approval_status"],
        "approval_required_flag": "1",
        "reason_code": _normalize_text(source.get("reason_code", "")) or "APPROVAL_REQUIRED",
        "reason_message": _normalize_text(source.get("reason_message", "")),
        "approval_link": _normalize_text(source.get("approval_link", "")),
        "invoice_required_quantity": decision_fields["invoice_required_quantity"],
        "invoice_unit_cost_gbp": decision_fields["invoice_unit_cost_gbp"],
        "invoice_total_risk_gbp": decision_fields["invoice_total_risk_gbp"],
        "operator_decision": decision_fields["operator_decision"],
        "decision_reason": decision_fields["decision_reason"],
        "cooldown_until_utc": decision_fields["cooldown_until_utc"],
        "recheck_trigger": decision_fields["recheck_trigger"],
        "approval_application_status": decision_fields["approval_application_status"],
        "invoice_artifact_reference": decision_fields["invoice_artifact_reference"],
        "updated_at_utc": observed_utc,
        "source_reference": f"F098_build_brand_approval_queue.py|{_normalize_text(source.get('source_kind', ''))}",
        "supplier_id": _normalize_text(source.get("supplier_id", "")),
        "supplier_sku": _normalize_text(source.get("supplier_sku", "")),
        "restriction_event_id": _normalize_text(source.get("source_event_id", "")),
        "restriction_observed_utc": _normalize_text(source.get("source_observed_utc", "")),
    }


def _write_health(root: Path, *, observed_utc: str, queue_rows: int, failed_rows: int, parked_rows: int, invoice_required_rows: int) -> None:
    check_name = "brand_approval_queue"
    status = "warn" if queue_rows > 0 else "ok"
    existing = read_f_contract_df(root, "amazon_listing_health")
    retained = existing[existing["check"].map(_normalize_text) != check_name].copy() if not existing.empty else existing
    row = pd.DataFrame(
        [
            {
                "check": check_name,
                "status": status,
                "value": str(queue_rows),
                "notes": (
                    f"queue_rows={queue_rows};failed_rows={failed_rows};"
                    f"parked_rows={parked_rows};invoice_required_rows={invoice_required_rows}"
                ),
                "observed_utc": observed_utc,
                "source_path": str(root / "out" / "systems" / "F" / "live" / "brand_approval_queue_live.csv"),
            }
        ]
    )
    write_f_contract_df(root, "amazon_listing_health", pd.concat([retained, row], ignore_index=True))


def record_brand_approval_decisions(
    *,
    root: Path | None = None,
    decision_rows: list[dict[str, object]],
    observed_utc: str | None = None,
    actor: str = "operator_ui",
    source_reference: str = "F098_build_brand_approval_queue.py",
) -> dict[str, object]:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)
    observed = observed_utc or _utc_now_iso()
    out_rows: list[dict[str, str]] = []
    skipped_rows: list[str] = []
    for row in decision_rows:
        draft_id = _normalize_text(row.get("draft_id", ""))
        queue_id = _normalize_text(row.get("queue_id", ""))
        decision = _normalize_text(row.get("operator_decision", "")).lower()
        if not draft_id and not queue_id:
            skipped_rows.append("(missing_draft_or_queue_id)")
            continue
        if decision not in {"fail_now", "park", "try_seller_central", "invoice_planned", "invoice_uploaded", "approved_recheck"}:
            skipped_rows.append(f"{draft_id or queue_id}:invalid_decision")
            continue
        invoice_qty = _positive_int(row.get("invoice_required_quantity", ""))
        unit_cost = _money(row.get("invoice_unit_cost_gbp", ""))
        total_risk = _risk_total(invoice_qty, unit_cost, row.get("invoice_total_risk_gbp", ""))
        cooldown = _normalize_text(row.get("cooldown_until_utc", ""))
        if decision == "park" and cooldown == "":
            cooldown = _plus_days(observed, 365)
        _, default_recheck = _approval_status_from_decision(decision)
        out_rows.append(
            {
                "event_utc": observed,
                "event_id": f"f098-brand-approval-decision-{uuid.uuid4().hex[:12]}",
                "queue_id": queue_id,
                "draft_id": draft_id,
                "candidate_id": _normalize_text(row.get("candidate_id", "")),
                "expected_seller_sku": _normalize_text(row.get("expected_seller_sku", "")),
                "asin": _normalize_text(row.get("asin", "")).upper(),
                "marketplace_id": _normalize_text(row.get("marketplace_id", "")),
                "operator_decision": decision,
                "decision_reason": _normalize_text(row.get("decision_reason", "")),
                "invoice_required_quantity": invoice_qty,
                "invoice_unit_cost_gbp": unit_cost,
                "invoice_total_risk_gbp": total_risk,
                "cooldown_until_utc": cooldown,
                "recheck_trigger": _normalize_text(row.get("recheck_trigger", "")) or default_recheck,
                "approval_application_status": _normalize_text(row.get("approval_application_status", "")),
                "invoice_artifact_reference": _normalize_text(row.get("invoice_artifact_reference", "")),
                "actor": _normalize_text(actor),
                "source_reference": _normalize_text(source_reference) or "F098_build_brand_approval_queue.py",
                "brand": _normalize_text(row.get("brand", "")),
            }
        )
    if out_rows:
        existing = read_f_contract_df(root_path, "brand_approval_decision_events")
        write_f_contract_df(root_path, "brand_approval_decision_events", pd.concat([existing, pd.DataFrame(out_rows)], ignore_index=True))
    return {
        "events_applied": len(out_rows),
        "skipped_rows": skipped_rows,
        "applied_event_ids": [row["event_id"] for row in out_rows],
    }


def build_brand_approval_queue(
    *,
    root: Path | None = None,
    observed_utc: str | None = None,
) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)
    observed = observed_utc or _utc_now_iso()
    sources = _approval_sources(root_path)
    decisions = read_f_contract_df(root_path, "brand_approval_decision_events")
    decisions_by_queue, decisions_by_draft = _latest_decisions(decisions)

    rows: list[dict[str, str]] = []
    seen_queue_ids: set[str] = set()
    for source in sources:
        queue_id = _queue_id(source)
        if queue_id in seen_queue_ids:
            continue
        decision = decisions_by_queue.get(queue_id) or decisions_by_draft.get(_normalize_text(source.get("draft_id", ""))) or {}
        rows.append(_queue_row(observed_utc=observed, source=source, decision=decision))
        seen_queue_ids.add(queue_id)

    out = write_f_contract_df(root_path, "brand_approval_queue_live", pd.DataFrame(rows))
    failed_rows = int((out["approval_status"].map(_normalize_text) == "failed_invoice_risk").sum()) if not out.empty else 0
    parked_rows = int((out["approval_status"].map(_normalize_text) == "parked_invoice_or_brand_risk").sum()) if not out.empty else 0
    invoice_required_rows = int((out["approval_status"].map(_normalize_text) == "invoice_required").sum()) if not out.empty else 0
    _write_health(
        root_path,
        observed_utc=observed,
        queue_rows=int(len(out.index)),
        failed_rows=failed_rows,
        parked_rows=parked_rows,
        invoice_required_rows=invoice_required_rows,
    )
    print(
        {
            "status": "success",
            "queue_rows": int(len(out.index)),
            "failed_rows": failed_rows,
            "parked_rows": parked_rows,
            "invoice_required_rows": invoice_required_rows,
        }
    )
    return out


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Amazon brand approval queue from restriction and read-back evidence.")
    parser.add_argument("--root", default="")
    parser.add_argument("--observed-utc", default="")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    root = Path(args.root) if _normalize_text(args.root) else None
    observed = _normalize_text(args.observed_utc) or None
    build_brand_approval_queue(root=root, observed_utc=observed)


if __name__ == "__main__":
    main()
