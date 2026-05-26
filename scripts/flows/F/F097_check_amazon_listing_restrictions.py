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

from scripts.api.amazon_listings_restrictions import run_restriction_check_for_draft_row
from scripts.flows.F._contract_io import read_f_contract_df, write_f_contract_df
from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract


RestrictionClient = Callable[[dict[str, str]], dict[str, Any]]


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


def _restriction_list(response: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _payload(response)
    raw = payload.get("restrictions", [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _reason_list(restrictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    for restriction in restrictions:
        raw = restriction.get("reasons", [])
        if isinstance(raw, list):
            reasons.extend(reason for reason in raw if isinstance(reason, dict))
    return reasons


def _reason_code(reason: dict[str, Any]) -> str:
    return _normalize_text(reason.get("reasonCode", reason.get("reason_code", ""))).upper()


def _reason_message(reason: dict[str, Any]) -> str:
    return _normalize_text(reason.get("message", reason.get("reasonMessage", reason.get("reason_message", ""))))


def _approval_link_from_container(container: dict[str, Any]) -> str:
    raw_links = container.get("links", [])
    if not isinstance(raw_links, list):
        return ""
    for link in raw_links:
        if not isinstance(link, dict):
            continue
        for key in ("resource", "href", "url"):
            value = _normalize_text(link.get(key, ""))
            if value:
                return value
    return ""


def _first_approval_link(restrictions: list[dict[str, Any]], reasons: list[dict[str, Any]]) -> str:
    for reason in reasons:
        value = _approval_link_from_container(reason)
        if value:
            return value
    for restriction in restrictions:
        value = _approval_link_from_container(restriction)
        if value:
            return value
    return ""


def _restriction_status(response: dict[str, Any], *, exception_text: str = "") -> tuple[str, str, str, str, str]:
    if exception_text:
        return "restriction_check_failed", "0", "", exception_text, ""
    http_status = _http_status(response)
    if http_status and not http_status.startswith("2"):
        return "restriction_check_failed", "0", "", f"http_status={http_status}", ""

    restrictions = _restriction_list(response)
    if not restrictions:
        return "clear", "0", "", "no_restrictions", ""

    reasons = _reason_list(restrictions)
    reason_code = ""
    reason_message = ""
    for reason in reasons:
        reason_code = _reason_code(reason)
        reason_message = _reason_message(reason)
        if reason_code or reason_message:
            break
    approval_link = _first_approval_link(restrictions, reasons)
    approval_required = any(
        _reason_code(reason) == "APPROVAL_REQUIRED" or "approval" in _reason_message(reason).lower()
        for reason in reasons
    )
    if approval_required:
        return "approval_required", "1", reason_code or "APPROVAL_REQUIRED", reason_message, approval_link
    return "restricted", "0", reason_code, reason_message or "listing_restricted", approval_link


def _event_row(
    *,
    observed_utc: str,
    row: dict[str, str],
    response: dict[str, Any],
    exception_text: str = "",
) -> dict[str, str]:
    status, approval_flag, reason_code, reason_message, approval_link = _restriction_status(
        response,
        exception_text=exception_text,
    )
    notes = reason_message if status != "clear" else "no_restrictions"
    return {
        "event_utc": observed_utc,
        "event_id": f"f097-restriction-{uuid.uuid4().hex[:12]}",
        "draft_id": _normalize_text(row.get("draft_id", "")),
        "candidate_id": _normalize_text(row.get("candidate_id", "")),
        "expected_seller_sku": _normalize_text(row.get("expected_seller_sku", "")),
        "asin": _normalize_text(row.get("asin", "")).upper(),
        "marketplace_id": _normalize_text(row.get("marketplace_id", "")),
        "condition_type": _normalize_text(row.get("condition_type", "")) or "new_new",
        "restriction_status": status,
        "approval_required_flag": approval_flag,
        "reason_code": reason_code,
        "reason_message": reason_message,
        "approval_link": approval_link,
        "http_status": _http_status(response),
        "notes": notes,
        "source_reference": "amazon_listing_drafts_live",
        "brand": _normalize_text(row.get("brand", "")),
        "amazon_title": _normalize_text(row.get("amazon_title", "")),
        "supplier_id": _normalize_text(row.get("supplier_id", "")),
        "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
    }


def _live_row(*, observed_utc: str, event: dict[str, str]) -> dict[str, str]:
    return {
        "observed_utc": observed_utc,
        "restriction_id": _hash_id(
            "restriction",
            event.get("draft_id", ""),
            event.get("asin", ""),
            event.get("marketplace_id", ""),
            event.get("condition_type", ""),
        ),
        "draft_id": _normalize_text(event.get("draft_id", "")),
        "candidate_id": _normalize_text(event.get("candidate_id", "")),
        "expected_seller_sku": _normalize_text(event.get("expected_seller_sku", "")),
        "asin": _normalize_text(event.get("asin", "")),
        "marketplace_id": _normalize_text(event.get("marketplace_id", "")),
        "condition_type": _normalize_text(event.get("condition_type", "")),
        "restriction_status": _normalize_text(event.get("restriction_status", "")),
        "approval_required_flag": _normalize_text(event.get("approval_required_flag", "")),
        "reason_code": _normalize_text(event.get("reason_code", "")),
        "reason_message": _normalize_text(event.get("reason_message", "")),
        "approval_link": _normalize_text(event.get("approval_link", "")),
        "http_status": _normalize_text(event.get("http_status", "")),
        "source_reference": "amazon_listing_restriction_events",
        "updated_at_utc": observed_utc,
        "brand": _normalize_text(event.get("brand", "")),
        "amazon_title": _normalize_text(event.get("amazon_title", "")),
        "supplier_id": _normalize_text(event.get("supplier_id", "")),
        "supplier_sku": _normalize_text(event.get("supplier_sku", "")),
        "latest_restriction_event_id": _normalize_text(event.get("event_id", "")),
        "latest_restriction_utc": _normalize_text(event.get("event_utc", "")),
    }


def _select_restriction_candidates(drafts_df: pd.DataFrame, *, draft_ids: list[str] | None) -> pd.DataFrame:
    if drafts_df.empty:
        return drafts_df.copy()
    work = drafts_df.copy()
    if draft_ids:
        wanted = {_normalize_text(draft_id) for draft_id in draft_ids if _normalize_text(draft_id)}
        work = work[work["draft_id"].map(_normalize_text).isin(wanted)].copy()
    return work[
        work["asin"].map(_normalize_text).ne("")
        & work["marketplace_id"].map(_normalize_text).ne("")
        & work["condition_type"].map(_normalize_text).ne("")
    ].copy()


def _replace_live_rows(root: Path, *, checked_draft_ids: set[str], rows: list[dict[str, str]]) -> pd.DataFrame:
    existing = read_f_contract_df(root, "amazon_listing_restrictions_live")
    if existing.empty:
        retained = existing
    else:
        retained = existing[~existing["draft_id"].map(_normalize_text).isin(checked_draft_ids)].copy()
    return write_f_contract_df(root, "amazon_listing_restrictions_live", pd.concat([retained, pd.DataFrame(rows)], ignore_index=True))


def _append_events(root: Path, rows: list[dict[str, str]]) -> None:
    existing = read_f_contract_df(root, "amazon_listing_restriction_events")
    write_f_contract_df(root, "amazon_listing_restriction_events", pd.concat([existing, pd.DataFrame(rows)], ignore_index=True))


def _write_health(
    root: Path,
    *,
    observed_utc: str,
    checked_rows: int,
    clear_rows: int,
    approval_required_rows: int,
    restricted_rows: int,
    failed_rows: int,
) -> None:
    check_name = "amazon_listing_restrictions"
    if failed_rows > 0:
        status = "fail"
    elif approval_required_rows > 0 or restricted_rows > 0:
        status = "warn"
    else:
        status = "ok"
    existing = read_f_contract_df(root, "amazon_listing_health")
    retained = existing[existing["check"].map(_normalize_text) != check_name].copy() if not existing.empty else existing
    row = pd.DataFrame(
        [
            {
                "check": check_name,
                "status": status,
                "value": str(clear_rows),
                "notes": (
                    f"checked_rows={checked_rows};clear_rows={clear_rows};"
                    f"approval_required_rows={approval_required_rows};restricted_rows={restricted_rows};failed_rows={failed_rows}"
                ),
                "observed_utc": observed_utc,
                "source_path": str(root / "out" / "systems" / "F" / "live" / "amazon_listing_drafts_live.csv"),
            }
        ]
    )
    write_f_contract_df(root, "amazon_listing_health", pd.concat([retained, row], ignore_index=True))


def run_amazon_listing_restriction_check(
    *,
    root: Path | None = None,
    draft_ids: list[str] | None = None,
    observed_utc: str | None = None,
    restriction_client: RestrictionClient | None = None,
    run_check: bool = False,
    max_rows: int | None = None,
    reason_locale: str = "en_GB",
) -> dict[str, int]:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)
    observed = observed_utc or _utc_now_iso()
    drafts_df = read_f_contract_df(root_path, "amazon_listing_drafts_live")
    candidates = _select_restriction_candidates(drafts_df, draft_ids=draft_ids)
    if max_rows is not None:
        candidates = candidates.head(max(int(max_rows), 0)).copy()
    if not run_check:
        result = {
            "eligible_rows": int(len(candidates.index)),
            "checked_rows": 0,
            "clear_rows": 0,
            "approval_required_rows": 0,
            "restricted_rows": 0,
            "failed_rows": 0,
        }
        print({"status": "restriction_check_not_run", **result})
        return result

    client = restriction_client or (lambda row: run_restriction_check_for_draft_row(row, reason_locale=reason_locale))
    checked_draft_ids: set[str] = set()
    event_rows: list[dict[str, str]] = []
    live_rows: list[dict[str, str]] = []
    clear_rows = 0
    approval_required_rows = 0
    restricted_rows = 0
    failed_rows = 0

    for _, draft in candidates.iterrows():
        row = {key: _normalize_text(value) for key, value in draft.to_dict().items()}
        draft_id = _normalize_text(row.get("draft_id", ""))
        checked_draft_ids.add(draft_id)
        try:
            response = client(row)
            event = _event_row(observed_utc=observed, row=row, response=response)
        except Exception as exc:
            event = _event_row(
                observed_utc=observed,
                row=row,
                response={},
                exception_text=f"{type(exc).__name__}:{exc}",
            )
        status = _normalize_text(event.get("restriction_status", ""))
        if status == "clear":
            clear_rows += 1
        elif status == "approval_required":
            approval_required_rows += 1
        elif status == "restricted":
            restricted_rows += 1
        else:
            failed_rows += 1
        event_rows.append(event)
        live_rows.append(_live_row(observed_utc=observed, event=event))

    if event_rows:
        _append_events(root_path, event_rows)
        _replace_live_rows(root_path, checked_draft_ids=checked_draft_ids, rows=live_rows)
    result = {
        "eligible_rows": int(len(candidates.index)),
        "checked_rows": len(event_rows),
        "clear_rows": clear_rows,
        "approval_required_rows": approval_required_rows,
        "restricted_rows": restricted_rows,
        "failed_rows": failed_rows,
    }
    _write_health(root_path, observed_utc=observed, **{k: result[k] for k in ("checked_rows", "clear_rows", "approval_required_rows", "restricted_rows", "failed_rows")})
    print({"status": "success", **result})
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Amazon Listings Restrictions for listing draft ASINs.")
    parser.add_argument("--root", default="")
    parser.add_argument("--draft-id", action="append", default=[])
    parser.add_argument("--observed-utc", default="")
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--reason-locale", default="en_GB")
    parser.add_argument("--run-check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    root = Path(args.root) if _normalize_text(args.root) else None
    observed = _normalize_text(args.observed_utc) or None
    run_amazon_listing_restriction_check(
        root=root,
        draft_ids=args.draft_id,
        observed_utc=observed,
        run_check=bool(args.run_check),
        max_rows=args.max_rows,
        reason_locale=args.reason_locale,
    )


if __name__ == "__main__":
    main()
