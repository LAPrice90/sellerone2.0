from __future__ import annotations

import argparse
import hashlib
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

from scripts.api.amazon_listings_items import run_preview_for_draft_row
from scripts.flows.F._contract_io import read_f_contract_df, write_f_contract_df
from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract


PreviewClient = Callable[[dict[str, str]], dict[str, Any]]


REQUIRED_PREVIEW_FIELDS = (
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


def _normalize_lower(value: object) -> str:
    return _normalize_text(value).lower()


def _hash_text(*parts: object, length: int = 16) -> str:
    raw = "|".join(_normalize_text(part) for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:length]


def _hash_id(prefix: str, *parts: object, length: int = 16) -> str:
    return f"{prefix}_{_hash_text(*parts, length=length)}"


def _missing_preview_fields(row: dict[str, str]) -> list[str]:
    return [field for field in REQUIRED_PREVIEW_FIELDS if _normalize_text(row.get(field, "")) == ""]


def _issue_list(response: dict[str, Any]) -> list[dict[str, Any]]:
    payload = response.get("payload", response)
    if not isinstance(payload, dict):
        return []
    raw_issues = payload.get("issues")
    if raw_issues is None and isinstance(payload.get("payload"), dict):
        raw_issues = payload["payload"].get("issues")
    if not isinstance(raw_issues, list):
        return []
    return [issue for issue in raw_issues if isinstance(issue, dict)]


def _response_status(response: dict[str, Any]) -> str:
    payload = response.get("payload", response)
    if not isinstance(payload, dict):
        return ""
    status = _normalize_text(payload.get("status", ""))
    if status == "" and isinstance(payload.get("payload"), dict):
        status = _normalize_text(payload["payload"].get("status", ""))
    return status


def _http_status(response: dict[str, Any]) -> str:
    return _normalize_text(response.get("http_status", response.get("status_code", "")))


def _issue_severity(issue: dict[str, Any]) -> str:
    return _normalize_text(issue.get("severity", issue.get("issueSeverity", ""))).upper()


def _issue_code(issue: dict[str, Any]) -> str:
    return _normalize_text(issue.get("code", issue.get("issueCode", "")))


def _issue_message(issue: dict[str, Any]) -> str:
    return _normalize_text(issue.get("message", issue.get("issueMessage", "")))


def _attribute_names(issue: dict[str, Any]) -> list[str]:
    for key in ("attributeNames", "attribute_names", "attributes"):
        raw = issue.get(key)
        if isinstance(raw, list):
            return [_normalize_text(value) for value in raw if _normalize_text(value) != ""]
        if _normalize_text(raw) != "":
            return [_normalize_text(raw)]
    return []


def _preview_status(response: dict[str, Any], issues: list[dict[str, Any]], exception_text: str = "") -> str:
    if exception_text:
        return "preview_failed"
    http_status = _http_status(response)
    if http_status and not http_status.startswith("2"):
        return "preview_failed"
    if any(_issue_severity(issue) == "ERROR" for issue in issues):
        return "preview_rejected"
    response_status = _response_status(response).upper()
    if response_status in {"INVALID", "REJECTED"}:
        return "preview_rejected"
    return "preview_passed"


def _event_row(
    *,
    observed_utc: str,
    row: dict[str, str],
    preview_id: str,
    preview_status: str,
    issue_count: int,
    notes: str,
    response_status: str,
) -> dict[str, str]:
    return {
        "event_utc": observed_utc,
        "event_id": f"f093-preview-{uuid.uuid4().hex[:12]}",
        "draft_id": _normalize_text(row.get("draft_id", "")),
        "preview_id": preview_id,
        "preview_status": preview_status,
        "candidate_id": _normalize_text(row.get("candidate_id", "")),
        "expected_seller_sku": _normalize_text(row.get("expected_seller_sku", "")),
        "asin": _normalize_text(row.get("asin", "")),
        "marketplace_id": _normalize_text(row.get("marketplace_id", "")),
        "issue_count": str(issue_count),
        "notes": notes,
        "source_reference": "amazon_listing_drafts_live",
        "response_status": response_status,
    }


def _issue_rows(
    *,
    observed_utc: str,
    row: dict[str, str],
    preview_id: str,
    issues: list[dict[str, Any]],
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    draft_id = _normalize_text(row.get("draft_id", ""))
    for index, issue in enumerate(issues, start=1):
        attrs = _attribute_names(issue)
        attr_text = ",".join(attrs)
        code = _issue_code(issue)
        severity = _issue_severity(issue) or "UNKNOWN"
        message = _issue_message(issue)
        out.append(
            {
                "observed_utc": observed_utc,
                "issue_id": _hash_id("issue", preview_id, draft_id, index, code, severity, message),
                "draft_id": draft_id,
                "issue_code": code,
                "issue_severity": severity,
                "issue_message": message,
                "expected_seller_sku": _normalize_text(row.get("expected_seller_sku", "")),
                "asin": _normalize_text(row.get("asin", "")),
                "marketplace_id": _normalize_text(row.get("marketplace_id", "")),
                "source_reference": preview_id,
                "attribute_name": attr_text,
                "candidate_id": _normalize_text(row.get("candidate_id", "")),
            }
        )
    return out


def _hold_row(
    *,
    observed_utc: str,
    row: dict[str, str],
    reason: str,
    note: str,
) -> dict[str, str]:
    return {
        "hold_utc": observed_utc,
        "hold_id": _hash_id(
            "hold",
            "amazon_preview",
            row.get("draft_id", ""),
            row.get("expected_seller_sku", ""),
            reason,
        ),
        "hold_stage": "amazon_preview",
        "supplier_id": _normalize_text(row.get("supplier_id", "")),
        "active_run_id": _normalize_text(row.get("source_run_id", "")),
        "candidate_id": _normalize_text(row.get("candidate_id", "")),
        "asin": _normalize_text(row.get("asin", "")),
        "expected_seller_sku": _normalize_text(row.get("expected_seller_sku", "")),
        "hold_reason": reason,
        "hold_note": note,
        "source_reference": "F093_run_amazon_listing_preview.py",
        "intake_id": _normalize_text(row.get("source_intake_id", "")),
        "draft_id": _normalize_text(row.get("draft_id", "")),
        "marketplace_id": _normalize_text(row.get("marketplace_id", "")),
    }


def _replace_preview_holds(root: Path, *, attempted_draft_ids: set[str], rows: list[dict[str, str]]) -> None:
    existing = read_f_contract_df(root, "amazon_listing_holds_live")
    if existing.empty:
        retained = existing
    else:
        stages = existing["hold_stage"].map(_normalize_text)
        draft_ids = existing["draft_id"].map(_normalize_text)
        retained = existing[~((stages == "amazon_preview") & draft_ids.isin(attempted_draft_ids))].copy()
    out_df = pd.concat([retained, pd.DataFrame(rows)], ignore_index=True)
    write_f_contract_df(root, "amazon_listing_holds_live", out_df)


def _replace_preview_issues(root: Path, *, attempted_draft_ids: set[str], rows: list[dict[str, str]]) -> None:
    existing = read_f_contract_df(root, "amazon_listing_preview_issues_live")
    if existing.empty:
        retained = existing
    else:
        retained = existing[~existing["draft_id"].map(_normalize_text).isin(attempted_draft_ids)].copy()
    out_df = pd.concat([retained, pd.DataFrame(rows)], ignore_index=True)
    write_f_contract_df(root, "amazon_listing_preview_issues_live", out_df)


def _append_preview_events(root: Path, rows: list[dict[str, str]]) -> None:
    existing = read_f_contract_df(root, "amazon_listing_preview_events")
    out_df = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True)
    write_f_contract_df(root, "amazon_listing_preview_events", out_df)


def _write_health(
    root: Path,
    *,
    observed_utc: str,
    eligible_rows: int,
    attempted_rows: int,
    passed_rows: int,
    rejected_rows: int,
    failed_rows: int,
) -> None:
    check_name = "amazon_listing_preview"
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
                "value": str(passed_rows),
                "notes": (
                    f"eligible_rows={eligible_rows};attempted_rows={attempted_rows};"
                    f"passed_rows={passed_rows};rejected_rows={rejected_rows};failed_rows={failed_rows}"
                ),
                "observed_utc": observed_utc,
                "source_path": str(root / "out" / "systems" / "F" / "live" / "amazon_listing_drafts_live.csv"),
            }
        ]
    )
    write_f_contract_df(root, "amazon_listing_health", pd.concat([retained, health], ignore_index=True))


def _select_preview_candidates(
    drafts_df: pd.DataFrame,
    *,
    draft_ids: list[str] | None,
) -> pd.DataFrame:
    if drafts_df.empty:
        return drafts_df.copy()
    work = drafts_df.copy()
    if draft_ids:
        wanted = {_normalize_text(draft_id) for draft_id in draft_ids if _normalize_text(draft_id) != ""}
        work = work[work["draft_id"].map(_normalize_text).isin(wanted)].copy()
    work = work[
        work["draft_status"].map(_normalize_text).eq("ready_for_amazon_preview")
        & work["listing_approval_status"].map(_normalize_text).eq("approved_for_preview")
        & work["block_reason"].map(_normalize_text).eq("")
        & work["amazon_submission_status"].map(_normalize_text).isin({"", "not_submitted"})
    ].copy()
    return work


def run_amazon_listing_preview(
    *,
    root: Path | None = None,
    draft_ids: list[str] | None = None,
    observed_utc: str | None = None,
    preview_client: PreviewClient | None = None,
    run_preview: bool = False,
    max_rows: int | None = None,
    issue_locale: str = "en_GB",
) -> dict[str, int]:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)
    observed = observed_utc or _utc_now_iso()
    drafts_df = read_f_contract_df(root_path, "amazon_listing_drafts_live")
    candidates = _select_preview_candidates(drafts_df, draft_ids=draft_ids)
    if max_rows is not None:
        candidates = candidates.head(max(int(max_rows), 0)).copy()

    if not run_preview:
        _write_health(
            root_path,
            observed_utc=observed,
            eligible_rows=int(len(candidates.index)),
            attempted_rows=0,
            passed_rows=0,
            rejected_rows=0,
            failed_rows=0,
        )
        result = {
            "eligible_rows": int(len(candidates.index)),
            "attempted_rows": 0,
            "passed_rows": 0,
            "rejected_rows": 0,
            "failed_rows": 0,
        }
        print({"status": "preview_not_run", **result})
        return result

    client = preview_client or (lambda row: run_preview_for_draft_row(row, issue_locale=issue_locale))
    attempted_ids: set[str] = set()
    issue_rows: list[dict[str, str]] = []
    hold_rows: list[dict[str, str]] = []
    event_rows: list[dict[str, str]] = []
    passed_rows = 0
    rejected_rows = 0
    failed_rows = 0

    for row_index, draft in candidates.iterrows():
        row = {key: _normalize_text(value) for key, value in draft.to_dict().items()}
        draft_id = _normalize_text(row.get("draft_id", ""))
        attempted_ids.add(draft_id)
        preview_id = _hash_id("preview", draft_id, row.get("expected_seller_sku", ""), observed)
        missing = _missing_preview_fields(row)
        response: dict[str, Any] = {}
        exception_text = ""
        issues: list[dict[str, Any]] = []
        if missing:
            exception_text = "missing_preview_fields:" + ",".join(missing)
            status = "preview_failed"
        else:
            try:
                response = client(row)
                issues = _issue_list(response)
                status = _preview_status(response, issues)
            except Exception as exc:
                exception_text = f"{type(exc).__name__}:{exc}"
                status = "preview_failed"

        issue_count = len(issues)
        response_status = _response_status(response)
        if exception_text:
            notes = exception_text
        elif issue_count:
            notes = "; ".join(
                _normalize_text(f"{_issue_severity(issue)} {_issue_code(issue)} {_issue_message(issue)}")
                for issue in issues[:3]
            )
        else:
            notes = response_status or "validation_preview_accepted"

        issue_rows.extend(_issue_rows(observed_utc=observed, row=row, preview_id=preview_id, issues=issues))
        event_rows.append(
            _event_row(
                observed_utc=observed,
                row=row,
                preview_id=preview_id,
                preview_status=status,
                issue_count=issue_count,
                notes=notes,
                response_status=response_status,
            )
        )

        drafts_df.loc[row_index, "amazon_preview_status"] = status
        drafts_df.loc[row_index, "amazon_preview_issue_count"] = str(issue_count)
        drafts_df.loc[row_index, "updated_at_utc"] = observed

        if status == "preview_passed":
            drafts_df.loc[row_index, "draft_status"] = "ready_for_live_submit"
            drafts_df.loc[row_index, "block_reason"] = ""
            passed_rows += 1
        elif status == "preview_rejected":
            drafts_df.loc[row_index, "draft_status"] = "blocked_amazon_preview"
            drafts_df.loc[row_index, "block_reason"] = "amazon_preview_rejected"
            hold_rows.append(
                _hold_row(
                    observed_utc=observed,
                    row=row,
                    reason="amazon_preview_rejected",
                    note=notes,
                )
            )
            rejected_rows += 1
        else:
            drafts_df.loc[row_index, "draft_status"] = "blocked_amazon_preview"
            drafts_df.loc[row_index, "block_reason"] = "amazon_preview_failed"
            hold_rows.append(
                _hold_row(
                    observed_utc=observed,
                    row=row,
                    reason="amazon_preview_failed",
                    note=notes,
                )
            )
            failed_rows += 1

    write_f_contract_df(root_path, "amazon_listing_drafts_live", drafts_df)
    _replace_preview_issues(root_path, attempted_draft_ids=attempted_ids, rows=issue_rows)
    _replace_preview_holds(root_path, attempted_draft_ids=attempted_ids, rows=hold_rows)
    if event_rows:
        _append_preview_events(root_path, event_rows)
    _write_health(
        root_path,
        observed_utc=observed,
        eligible_rows=int(len(candidates.index)),
        attempted_rows=len(attempted_ids),
        passed_rows=passed_rows,
        rejected_rows=rejected_rows,
        failed_rows=failed_rows,
    )
    result = {
        "eligible_rows": int(len(candidates.index)),
        "attempted_rows": len(attempted_ids),
        "passed_rows": passed_rows,
        "rejected_rows": rejected_rows,
        "failed_rows": failed_rows,
    }
    print({"status": "success", **result})
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Amazon Listings Items validation preview for approved listing drafts.")
    parser.add_argument("--root", default="")
    parser.add_argument("--draft-id", action="append", default=[])
    parser.add_argument("--observed-utc", default="")
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--issue-locale", default="en_GB")
    parser.add_argument("--run-preview", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    root = Path(args.root) if _normalize_text(args.root) else None
    observed = _normalize_text(args.observed_utc) or None
    run_amazon_listing_preview(
        root=root,
        draft_ids=args.draft_id,
        observed_utc=observed,
        run_preview=bool(args.run_preview),
        max_rows=args.max_rows,
        issue_locale=args.issue_locale,
    )


if __name__ == "__main__":
    main()
