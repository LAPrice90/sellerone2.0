from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.api.amazon_listings_items import run_submit_for_draft_row
from scripts.flows.F._contract_io import read_f_contract_df, write_f_contract_df
from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract


SubmitClient = Callable[[dict[str, str]], dict[str, Any]]


REQUIRED_SUBMIT_FIELDS = (
    "draft_id",
    "asin",
    "expected_seller_sku",
    "marketplace_id",
    "product_type",
    "condition_type",
    "fulfillment_channel",
    "starting_price_gbp",
    "starting_quantity",
    "country_of_origin",
    "purchase_pack_size",
    "sold_pack_size",
    "vat_confirmed_flag",
    "product_tax_code",
    "currency_code",
    "price_includes_tax",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    text = str(value or "").strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _hash_text(*parts: object, length: int = 16) -> str:
    raw = "|".join(_normalize_text(part) for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:length]


def _hash_id(prefix: str, *parts: object, length: int = 16) -> str:
    return f"{prefix}_{_hash_text(*parts, length=length)}"


def _missing_submit_fields(row: dict[str, str]) -> list[str]:
    return [field for field in REQUIRED_SUBMIT_FIELDS if _normalize_text(row.get(field, "")) == ""]


def _payload(response: dict[str, Any]) -> dict[str, Any]:
    raw = response.get("payload", response)
    return raw if isinstance(raw, dict) else {}


def _issue_list(response: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _payload(response)
    raw_issues = payload.get("issues")
    if raw_issues is None and isinstance(payload.get("payload"), dict):
        raw_issues = payload["payload"].get("issues")
    if not isinstance(raw_issues, list):
        return []
    return [issue for issue in raw_issues if isinstance(issue, dict)]


def _response_status(response: dict[str, Any]) -> str:
    payload = _payload(response)
    status = _normalize_text(payload.get("status", ""))
    if status == "" and isinstance(payload.get("payload"), dict):
        status = _normalize_text(payload["payload"].get("status", ""))
    return status


def _http_status(response: dict[str, Any]) -> str:
    return _normalize_text(response.get("http_status", response.get("status_code", "")))


def _submission_id(response: dict[str, Any]) -> str:
    payload = _payload(response)
    return _normalize_text(
        payload.get("submissionId", "")
        or payload.get("submission_id", "")
        or (payload.get("payload", {}) if isinstance(payload.get("payload"), dict) else {}).get("submissionId", "")
    )


def _short_payload(response: dict[str, Any], *, limit: int = 300) -> str:
    payload = _payload(response)
    if not payload:
        return ""
    try:
        text = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    except Exception:
        text = str(payload)
    text = _normalize_text(text)
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def _issue_severity(issue: dict[str, Any]) -> str:
    return _normalize_text(issue.get("severity", issue.get("issueSeverity", ""))).upper()


def _issue_code(issue: dict[str, Any]) -> str:
    return _normalize_text(issue.get("code", issue.get("issueCode", "")))


def _issue_message(issue: dict[str, Any]) -> str:
    return _normalize_text(issue.get("message", issue.get("issueMessage", "")))


def _submission_status(response: dict[str, Any], issues: list[dict[str, Any]], exception_text: str = "") -> str:
    if exception_text:
        return "submit_failed"
    http_status = _http_status(response)
    if http_status and not http_status.startswith("2"):
        return "submit_failed"
    if any(_issue_severity(issue) == "ERROR" for issue in issues):
        return "submit_rejected"
    response_status = _response_status(response).upper()
    if response_status in {"INVALID", "REJECTED"}:
        return "submit_rejected"
    return "submitted"


def _submission_note(
    *,
    response: dict[str, Any],
    issues: list[dict[str, Any]],
    exception_text: str,
    submission_status: str,
) -> str:
    if exception_text:
        return exception_text
    if issues:
        return "; ".join(
            _normalize_text(f"{_issue_severity(issue)} {_issue_code(issue)} {_issue_message(issue)}")
            for issue in issues[:3]
        )
    response_status = _response_status(response)
    if submission_status == "submitted":
        return response_status or "listing_submitted"
    parts = []
    http_status = _http_status(response)
    if http_status:
        parts.append(f"http_status={http_status}")
    if response_status:
        parts.append(f"response_status={response_status}")
    payload_text = _short_payload(response)
    if payload_text:
        parts.append(f"payload={payload_text}")
    return ";".join(parts) or "submit_failed_without_response_detail"


def _event_row(
    *,
    observed_utc: str,
    row: dict[str, str],
    submission_id: str,
    submission_status: str,
    notes: str,
    response_status: str,
    http_status: str,
) -> dict[str, str]:
    return {
        "event_utc": observed_utc,
        "event_id": f"f094-submit-{uuid.uuid4().hex[:12]}",
        "draft_id": _normalize_text(row.get("draft_id", "")),
        "submission_id": submission_id,
        "submission_status": submission_status,
        "candidate_id": _normalize_text(row.get("candidate_id", "")),
        "expected_seller_sku": _normalize_text(row.get("expected_seller_sku", "")),
        "asin": _normalize_text(row.get("asin", "")),
        "marketplace_id": _normalize_text(row.get("marketplace_id", "")),
        "notes": notes,
        "source_reference": "amazon_listing_drafts_live",
        "response_status": response_status,
        "http_status": http_status,
    }


def _hold_row(
    *,
    observed_utc: str,
    row: dict[str, str],
    reason: str,
    note: str,
) -> dict[str, str]:
    return {
        "hold_utc": observed_utc,
        "hold_id": _hash_id("hold", "amazon_submit", row.get("draft_id", ""), row.get("expected_seller_sku", ""), reason),
        "hold_stage": "amazon_submit",
        "supplier_id": _normalize_text(row.get("supplier_id", "")),
        "active_run_id": _normalize_text(row.get("source_run_id", "")),
        "candidate_id": _normalize_text(row.get("candidate_id", "")),
        "asin": _normalize_text(row.get("asin", "")),
        "expected_seller_sku": _normalize_text(row.get("expected_seller_sku", "")),
        "hold_reason": reason,
        "hold_note": note,
        "source_reference": "F094_submit_amazon_listing_drafts.py",
        "intake_id": _normalize_text(row.get("source_intake_id", "")),
        "draft_id": _normalize_text(row.get("draft_id", "")),
        "marketplace_id": _normalize_text(row.get("marketplace_id", "")),
    }


def _replace_submit_holds(root: Path, *, attempted_draft_ids: set[str], rows: list[dict[str, str]]) -> None:
    existing = read_f_contract_df(root, "amazon_listing_holds_live")
    if existing.empty:
        retained = existing
    else:
        stages = existing["hold_stage"].map(_normalize_text)
        draft_ids = existing["draft_id"].map(_normalize_text)
        retained = existing[~((stages == "amazon_submit") & draft_ids.isin(attempted_draft_ids))].copy()
    write_f_contract_df(root, "amazon_listing_holds_live", pd.concat([retained, pd.DataFrame(rows)], ignore_index=True))


def _append_submission_events(root: Path, rows: list[dict[str, str]]) -> None:
    existing = read_f_contract_df(root, "amazon_listing_submission_events")
    write_f_contract_df(root, "amazon_listing_submission_events", pd.concat([existing, pd.DataFrame(rows)], ignore_index=True))


def _write_health(
    root: Path,
    *,
    observed_utc: str,
    eligible_rows: int,
    attempted_rows: int,
    submitted_rows: int,
    rejected_rows: int,
    failed_rows: int,
) -> None:
    check_name = "amazon_listing_submit"
    if failed_rows > 0:
        status = "fail"
    elif rejected_rows > 0:
        status = "warn"
    else:
        status = "ok"
    existing = read_f_contract_df(root, "amazon_listing_health")
    retained = existing[existing["check"].map(_normalize_text) != check_name].copy() if not existing.empty else existing
    health = pd.DataFrame(
        [
            {
                "check": check_name,
                "status": status,
                "value": str(submitted_rows),
                "notes": (
                    f"eligible_rows={eligible_rows};attempted_rows={attempted_rows};"
                    f"submitted_rows={submitted_rows};rejected_rows={rejected_rows};failed_rows={failed_rows}"
                ),
                "observed_utc": observed_utc,
                "source_path": str(root / "out" / "systems" / "F" / "live" / "amazon_listing_drafts_live.csv"),
            }
        ]
    )
    write_f_contract_df(root, "amazon_listing_health", pd.concat([retained, health], ignore_index=True))


def _select_submit_candidates(
    drafts_df: pd.DataFrame,
    *,
    draft_ids: list[str] | None,
    retry_failed_submit: bool = False,
) -> pd.DataFrame:
    if drafts_df.empty:
        return drafts_df.copy()
    work = drafts_df.copy()
    if draft_ids:
        wanted = {_normalize_text(draft_id) for draft_id in draft_ids if _normalize_text(draft_id) != ""}
        work = work[work["draft_id"].map(_normalize_text).isin(wanted)].copy()
    ready = work[
        work["draft_status"].map(_normalize_text).eq("ready_for_live_submit")
        & work["amazon_preview_status"].map(_normalize_text).eq("preview_passed")
        & work["amazon_preview_issue_count"].map(_normalize_text).isin({"", "0"})
        & work["block_reason"].map(_normalize_text).eq("")
        & work["amazon_submission_status"].map(_normalize_text).isin({"", "not_submitted"})
    ].copy()
    if not retry_failed_submit:
        return ready
    retry = work[
        work["draft_status"].map(_normalize_text).eq("blocked_amazon_submit")
        & work["amazon_preview_status"].map(_normalize_text).eq("preview_passed")
        & work["amazon_preview_issue_count"].map(_normalize_text).isin({"", "0"})
        & work["block_reason"].map(_normalize_text).eq("amazon_submit_failed")
        & work["amazon_submission_status"].map(_normalize_text).eq("submit_failed")
        & work["amazon_submission_id"].map(_normalize_text).eq("")
    ].copy()
    return pd.concat([ready, retry], ignore_index=False).drop_duplicates(subset=["draft_id"], keep="first")


def _active_restriction_blocks(root: Path) -> dict[str, tuple[str, str]]:
    blocks: dict[str, tuple[str, str]] = {}
    restrictions = read_f_contract_df(root, "amazon_listing_restrictions_live")
    if not restrictions.empty:
        for _, row in restrictions.iterrows():
            row_dict = {key: _normalize_text(value) for key, value in row.to_dict().items()}
            draft_id = row_dict.get("draft_id", "")
            status = row_dict.get("restriction_status", "")
            if not draft_id or status in {"", "clear"}:
                continue
            reason = "brand_approval_required" if status == "approval_required" else f"amazon_restriction_{status}"
            note = row_dict.get("reason_message", "") or row_dict.get("reason_code", "") or status
            blocks[draft_id] = (reason, note)

    queue = read_f_contract_df(root, "brand_approval_queue_live")
    if not queue.empty:
        for _, row in queue.iterrows():
            row_dict = {key: _normalize_text(value) for key, value in row.to_dict().items()}
            draft_id = row_dict.get("draft_id", "")
            approval_status = row_dict.get("approval_status", "")
            if not draft_id or approval_status in {"approval_cleared", "approved", "restriction_clear"}:
                continue
            note = row_dict.get("reason_message", "") or approval_status or "brand approval required"
            blocks[draft_id] = ("brand_approval_required", note)
    return blocks


def _remove_known_restriction_blocks(
    *,
    root: Path,
    drafts_df: pd.DataFrame,
    candidates: pd.DataFrame,
    observed_utc: str,
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    if candidates.empty:
        return drafts_df, candidates, 0
    blocks = _active_restriction_blocks(root)
    if not blocks:
        return drafts_df, candidates, 0

    hold_rows: list[dict[str, str]] = []
    blocked_ids: set[str] = set()
    for row_index, draft in candidates.iterrows():
        row = {key: _normalize_text(value) for key, value in draft.to_dict().items()}
        draft_id = row.get("draft_id", "")
        if draft_id not in blocks:
            continue
        reason, note = blocks[draft_id]
        blocked_ids.add(draft_id)
        drafts_df.loc[row_index, "draft_status"] = "blocked_amazon_submit"
        drafts_df.loc[row_index, "block_reason"] = reason
        drafts_df.loc[row_index, "updated_at_utc"] = observed_utc
        hold_rows.append(_hold_row(observed_utc=observed_utc, row=row, reason=reason, note=note))

    if not blocked_ids:
        return drafts_df, candidates, 0
    write_f_contract_df(root, "amazon_listing_drafts_live", drafts_df)
    _replace_submit_holds(root, attempted_draft_ids=blocked_ids, rows=hold_rows)
    filtered = candidates[~candidates["draft_id"].map(_normalize_text).isin(blocked_ids)].copy()
    return drafts_df, filtered, len(blocked_ids)


def run_amazon_listing_submit(
    *,
    root: Path | None = None,
    draft_ids: list[str] | None = None,
    observed_utc: str | None = None,
    submit_client: SubmitClient | None = None,
    run_submit: bool = False,
    confirm_live_submit: bool = False,
    max_rows: int | None = None,
    issue_locale: str = "en_GB",
    retry_failed_submit: bool = False,
) -> dict[str, int]:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)
    observed = observed_utc or _utc_now_iso()
    drafts_df = read_f_contract_df(root_path, "amazon_listing_drafts_live")
    candidates = _select_submit_candidates(
        drafts_df,
        draft_ids=draft_ids,
        retry_failed_submit=retry_failed_submit,
    )
    drafts_df, candidates, restriction_blocked_rows = _remove_known_restriction_blocks(
        root=root_path,
        drafts_df=drafts_df,
        candidates=candidates,
        observed_utc=observed,
    )
    if max_rows is not None:
        candidates = candidates.head(max(int(max_rows), 0)).copy()

    if not run_submit or not confirm_live_submit:
        result = {
            "eligible_rows": int(len(candidates.index)),
            "attempted_rows": 0,
            "submitted_rows": 0,
            "rejected_rows": 0,
            "failed_rows": 0,
        }
        _write_health(root_path, observed_utc=observed, **result)
        print({"status": "submit_not_run", **result, "restriction_blocked_rows": restriction_blocked_rows})
        return result

    client = submit_client or (lambda row: run_submit_for_draft_row(row, issue_locale=issue_locale))
    attempted_ids: set[str] = set()
    hold_rows: list[dict[str, str]] = []
    event_rows: list[dict[str, str]] = []
    submitted_rows = 0
    rejected_rows = 0
    failed_rows = 0

    for row_index, draft in candidates.iterrows():
        row = {key: _normalize_text(value) for key, value in draft.to_dict().items()}
        draft_id = _normalize_text(row.get("draft_id", ""))
        attempted_ids.add(draft_id)
        missing = _missing_submit_fields(row)
        response: dict[str, Any] = {}
        exception_text = ""
        issues: list[dict[str, Any]] = []
        if missing:
            exception_text = "missing_submit_fields:" + ",".join(missing)
            status = "submit_failed"
        else:
            try:
                response = client(row)
                issues = _issue_list(response)
                status = _submission_status(response, issues)
            except Exception as exc:
                exception_text = f"{type(exc).__name__}:{exc}"
                status = "submit_failed"

        response_status = _response_status(response)
        http_status = _http_status(response)
        submission_id = _submission_id(response)
        notes = _submission_note(
            response=response,
            issues=issues,
            exception_text=exception_text,
            submission_status=status,
        )

        event_rows.append(
            _event_row(
                observed_utc=observed,
                row=row,
                submission_id=submission_id,
                submission_status=status,
                notes=notes,
                response_status=response_status,
                http_status=http_status,
            )
        )
        drafts_df.loc[row_index, "amazon_submission_status"] = status
        drafts_df.loc[row_index, "amazon_submission_id"] = submission_id
        drafts_df.loc[row_index, "updated_at_utc"] = observed

        if status == "submitted":
            drafts_df.loc[row_index, "draft_status"] = "submitted_to_amazon"
            drafts_df.loc[row_index, "block_reason"] = ""
            submitted_rows += 1
        elif status == "submit_rejected":
            drafts_df.loc[row_index, "draft_status"] = "blocked_amazon_submit"
            drafts_df.loc[row_index, "block_reason"] = "amazon_submit_rejected"
            hold_rows.append(_hold_row(observed_utc=observed, row=row, reason="amazon_submit_rejected", note=notes))
            rejected_rows += 1
        else:
            drafts_df.loc[row_index, "draft_status"] = "blocked_amazon_submit"
            drafts_df.loc[row_index, "block_reason"] = "amazon_submit_failed"
            hold_rows.append(_hold_row(observed_utc=observed, row=row, reason="amazon_submit_failed", note=notes))
            failed_rows += 1

    write_f_contract_df(root_path, "amazon_listing_drafts_live", drafts_df)
    _replace_submit_holds(root_path, attempted_draft_ids=attempted_ids, rows=hold_rows)
    if event_rows:
        _append_submission_events(root_path, event_rows)
    result = {
        "eligible_rows": int(len(candidates.index)),
        "attempted_rows": len(attempted_ids),
        "submitted_rows": submitted_rows,
        "rejected_rows": rejected_rows,
        "failed_rows": failed_rows,
    }
    _write_health(root_path, observed_utc=observed, **result)
    print({"status": "success", **result})
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guarded live submit for Amazon Listings Items drafts.")
    parser.add_argument("--root", default="")
    parser.add_argument("--draft-id", action="append", default=[])
    parser.add_argument("--observed-utc", default="")
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--issue-locale", default="en_GB")
    parser.add_argument("--run-submit", action="store_true")
    parser.add_argument("--confirm-live-submit", action="store_true")
    parser.add_argument("--retry-failed-submit", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    root = Path(args.root) if _normalize_text(args.root) else None
    observed = _normalize_text(args.observed_utc) or None
    run_amazon_listing_submit(
        root=root,
        draft_ids=args.draft_id,
        observed_utc=observed,
        run_submit=bool(args.run_submit),
        confirm_live_submit=bool(args.confirm_live_submit),
        max_rows=args.max_rows,
        issue_locale=args.issue_locale,
        retry_failed_submit=bool(args.retry_failed_submit),
    )


if __name__ == "__main__":
    main()
