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

from scripts.api.amazon_listings_items import run_readback_for_draft_row
from scripts.flows.F._contract_io import read_f_contract_df, write_f_contract_df
from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract


ReadbackClient = Callable[[dict[str, str]], dict[str, Any]]


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


def _payload(response: dict[str, Any]) -> dict[str, Any]:
    raw = response.get("payload", response)
    if isinstance(raw, dict) and isinstance(raw.get("payload"), dict):
        return raw["payload"]
    return raw if isinstance(raw, dict) else {}


def _http_status(response: dict[str, Any]) -> str:
    return _normalize_text(response.get("http_status", response.get("status_code", "")))


def _issue_list(response: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _payload(response)
    raw_issues = payload.get("issues", [])
    if not isinstance(raw_issues, list):
        return []
    return [issue for issue in raw_issues if isinstance(issue, dict)]


def _issue_severity(issue: dict[str, Any]) -> str:
    return _normalize_text(issue.get("severity", issue.get("issueSeverity", ""))).upper()


def _issue_code(issue: dict[str, Any]) -> str:
    return _normalize_text(issue.get("code", issue.get("issueCode", "")))


def _issue_message(issue: dict[str, Any]) -> str:
    return _normalize_text(issue.get("message", issue.get("issueMessage", "")))


def _blocking_issue_count(issues: list[dict[str, Any]]) -> int:
    return sum(1 for issue in issues if _issue_severity(issue) == "ERROR")


def _extract_amazon_asin(response: dict[str, Any]) -> str:
    payload = _payload(response)
    summaries = payload.get("summaries")
    if isinstance(summaries, list):
        for summary in summaries:
            if isinstance(summary, dict):
                asin = _normalize_text(summary.get("asin", "")).upper()
                if asin:
                    return asin
    attrs = payload.get("attributes")
    if isinstance(attrs, dict):
        for attr_name in ("merchant_suggested_asin", "item_id"):
            values = attrs.get(attr_name)
            if isinstance(values, list):
                for entry in values:
                    if isinstance(entry, dict):
                        value = _normalize_text(entry.get("value", "")).upper()
                        if value:
                            return value
    return ""


def _readback_status(response: dict[str, Any], issues: list[dict[str, Any]], expected_asin: str) -> tuple[str, str, str, str]:
    http_status = _http_status(response)
    amazon_asin = _extract_amazon_asin(response)
    expected = _normalize_text(expected_asin).upper()
    asin_match = "not_checked"
    if amazon_asin and expected:
        asin_match = "match" if amazon_asin == expected else "mismatch"
    elif expected:
        asin_match = "missing_amazon_asin"

    if http_status and http_status == "404":
        return "not_found", asin_match, amazon_asin, f"http_status={http_status}"
    if http_status and not http_status.startswith("2"):
        return "readback_failed", asin_match, amazon_asin, f"http_status={http_status}"
    if asin_match == "mismatch":
        return "asin_mismatch", asin_match, amazon_asin, f"amazon_asin={amazon_asin}"
    blocking = _blocking_issue_count(issues)
    if blocking > 0:
        issue_notes = "; ".join(
            _normalize_text(f"{_issue_severity(issue)} {_issue_code(issue)} {_issue_message(issue)}")
            for issue in issues[:3]
        )
        return "blocking_issues", asin_match, amazon_asin, issue_notes
    return "confirmed", asin_match, amazon_asin, "listing_readback_confirmed"


def _event_row(*, observed_utc: str, row: dict[str, str], response: dict[str, Any], exception_text: str = "") -> dict[str, str]:
    issues = [] if exception_text else _issue_list(response)
    if exception_text:
        readback_status = "readback_failed"
        asin_match = "not_checked"
        amazon_asin = ""
        notes = exception_text
    else:
        readback_status, asin_match, amazon_asin, notes = _readback_status(
            response,
            issues,
            _normalize_text(row.get("asin", "")),
        )
    return {
        "event_utc": observed_utc,
        "event_id": f"f095-readback-{uuid.uuid4().hex[:12]}",
        "draft_id": _normalize_text(row.get("draft_id", "")),
        "expected_seller_sku": _normalize_text(row.get("expected_seller_sku", "")),
        "asin": _normalize_text(row.get("asin", "")),
        "marketplace_id": _normalize_text(row.get("marketplace_id", "")),
        "submission_id": _normalize_text(row.get("amazon_submission_id", "")),
        "readback_status": readback_status,
        "asin_match_status": asin_match,
        "issue_count": str(len(issues)),
        "blocking_issue_count": str(_blocking_issue_count(issues)),
        "notes": notes,
        "candidate_id": _normalize_text(row.get("candidate_id", "")),
        "http_status": _http_status(response),
        "amazon_asin": amazon_asin,
        "source_reference": "amazon_listing_drafts_live",
    }


def _select_readback_candidates(drafts_df: pd.DataFrame, *, draft_ids: list[str] | None) -> pd.DataFrame:
    if drafts_df.empty:
        return drafts_df.copy()
    work = drafts_df.copy()
    if draft_ids:
        wanted = {_normalize_text(draft_id) for draft_id in draft_ids if _normalize_text(draft_id)}
        work = work[work["draft_id"].map(_normalize_text).isin(wanted)].copy()
    return work[
        work["draft_status"].map(_normalize_text).eq("submitted_to_amazon")
        & work["amazon_submission_status"].map(_normalize_text).eq("submitted")
        & work["amazon_submission_id"].map(_normalize_text).ne("")
    ].copy()


def run_amazon_listing_readback(
    *,
    root: Path | None = None,
    draft_ids: list[str] | None = None,
    observed_utc: str | None = None,
    readback_client: ReadbackClient | None = None,
    run_readback: bool = False,
    max_rows: int | None = None,
    issue_locale: str = "en_GB",
) -> dict[str, int]:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)
    observed = observed_utc or _utc_now_iso()
    drafts_df = read_f_contract_df(root_path, "amazon_listing_drafts_live")
    candidates = _select_readback_candidates(drafts_df, draft_ids=draft_ids)
    if max_rows is not None:
        candidates = candidates.head(max(int(max_rows), 0)).copy()
    if not run_readback:
        result = {"eligible_rows": int(len(candidates.index)), "attempted_rows": 0, "confirmed_rows": 0, "blocked_rows": 0, "failed_rows": 0}
        print({"status": "readback_not_run", **result})
        return result

    client = readback_client or (lambda row: run_readback_for_draft_row(row, issue_locale=issue_locale))
    event_rows: list[dict[str, str]] = []
    confirmed_rows = 0
    blocked_rows = 0
    failed_rows = 0
    for _, draft in candidates.iterrows():
        row = {key: _normalize_text(value) for key, value in draft.to_dict().items()}
        try:
            response = client(row)
            event = _event_row(observed_utc=observed, row=row, response=response)
        except Exception as exc:
            event = _event_row(observed_utc=observed, row=row, response={}, exception_text=f"{type(exc).__name__}:{exc}")
        status = _normalize_text(event.get("readback_status", ""))
        if status == "confirmed":
            confirmed_rows += 1
        elif status in {"blocking_issues", "asin_mismatch", "not_found"}:
            blocked_rows += 1
        else:
            failed_rows += 1
        event_rows.append(event)

    if event_rows:
        existing = read_f_contract_df(root_path, "amazon_listing_readback_events")
        write_f_contract_df(root_path, "amazon_listing_readback_events", pd.concat([existing, pd.DataFrame(event_rows)], ignore_index=True))
    result = {
        "eligible_rows": int(len(candidates.index)),
        "attempted_rows": len(event_rows),
        "confirmed_rows": confirmed_rows,
        "blocked_rows": blocked_rows,
        "failed_rows": failed_rows,
    }
    print({"status": "success", **result})
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read back submitted Amazon listing drafts from Listings Items API.")
    parser.add_argument("--root", default="")
    parser.add_argument("--draft-id", action="append", default=[])
    parser.add_argument("--observed-utc", default="")
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--issue-locale", default="en_GB")
    parser.add_argument("--run-readback", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    root = Path(args.root) if _normalize_text(args.root) else None
    observed = _normalize_text(args.observed_utc) or None
    run_amazon_listing_readback(
        root=root,
        draft_ids=args.draft_id,
        observed_utc=observed,
        run_readback=bool(args.run_readback),
        max_rows=args.max_rows,
        issue_locale=args.issue_locale,
    )


if __name__ == "__main__":
    main()
