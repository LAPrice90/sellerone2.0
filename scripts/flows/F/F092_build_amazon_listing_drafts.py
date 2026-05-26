from __future__ import annotations

import argparse
import hashlib
import sys
import uuid
from datetime import datetime, timezone
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


REQUIRED_DRAFT_FIELDS = (
    "asin",
    "expected_seller_sku",
    "supplier_cost_gbp",
    "marketplace_id",
    "country_of_origin",
    "purchase_pack_size",
    "sold_pack_size",
    "vat_confirmed_flag",
    "product_tax_code",
    "currency_code",
    "price_includes_tax",
    "product_type",
    "condition_type",
    "fulfillment_channel",
    "starting_price_gbp",
    "starting_quantity",
    "listing_mode",
    "minimum_selling_price_rule",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    text = str(value or "").strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _normalize_country_of_origin(value: object) -> str:
    text = _normalize_text(value).upper()
    if len(text) == 2 and text.isalpha():
        return text
    return ""


def _normalize_currency_code(value: object) -> str:
    text = _normalize_text(value).upper()
    if len(text) == 3 and text.isalpha():
        return text
    return ""


def _normalize_price_includes_tax(value: object) -> str:
    text = _normalize_text(value).lower()
    if text in {"0", "false", "no", "n", "off"}:
        return "0"
    if text in {"1", "true", "yes", "y", "on"}:
        return "1"
    return ""


def _hash_text(*parts: object, length: int = 16) -> str:
    raw = "|".join(_normalize_text(part) for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:length]


def _hash_id(prefix: str, *parts: object, length: int = 16) -> str:
    return f"{prefix}_{_hash_text(*parts, length=length)}"


def _read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _load_defaults(root: Path) -> list[dict[str, str]]:
    frame = _read_csv_safe(root / "config" / "feeder" / "amazon_listing_defaults.csv")
    if frame.empty:
        return []
    rows: list[dict[str, str]] = []
    for record in frame.to_dict("records"):
        row = {key: _normalize_text(value) for key, value in record.items()}
        enabled = _normalize_text(row.get("enabled", "1")).lower()
        if enabled in {"0", "false", "no", "n"}:
            continue
        rows.append(row)
    return rows


def _default_for(defaults: list[dict[str, str]], *, marketplace_id: str) -> dict[str, str]:
    if not defaults:
        return {}
    marketplace_key = _normalize_text(marketplace_id)
    for row in defaults:
        if _normalize_text(row.get("marketplace_id", "")) == marketplace_key:
            return row
    return defaults[0]


def _existing_draft_map(drafts_df: pd.DataFrame) -> dict[tuple[str, str, str, str], dict[str, str]]:
    if drafts_df.empty:
        return {}
    out: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for record in drafts_df.to_dict("records"):
        row = {key: _normalize_text(value) for key, value in record.items()}
        key = (
            _normalize_key(row.get("candidate_id", "")),
            _normalize_key(row.get("asin", "")),
            _normalize_key(row.get("expected_seller_sku", "")),
            _normalize_text(row.get("marketplace_id", "")),
        )
        if all(part != "" for part in key):
            out[key] = row
    return out


def _reservation_map(reservations_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    if reservations_df.empty:
        return out
    for record in reservations_df.to_dict("records"):
        row = {key: _normalize_text(value) for key, value in record.items()}
        intake_id = _normalize_text(row.get("intake_id", ""))
        if intake_id != "":
            out[intake_id] = row
    return out


def _first_non_blank(*values: object) -> str:
    for value in values:
        text = _normalize_text(value)
        if text != "":
            return text
    return ""


def _missing_fields(row: dict[str, str]) -> list[str]:
    return [field for field in REQUIRED_DRAFT_FIELDS if _normalize_text(row.get(field, "")) == ""]


def _hold_row(
    *,
    observed_utc: str,
    supplier_id: str,
    active_run_id: str,
    candidate_id: str,
    asin: str,
    expected_seller_sku: str,
    reason: str,
    note: str,
    intake_id: str,
    draft_id: str,
    marketplace_id: str,
) -> dict[str, str]:
    return {
        "hold_utc": observed_utc,
        "hold_id": _hash_id("hold", "draft_builder", supplier_id, active_run_id, candidate_id, asin, expected_seller_sku, reason),
        "hold_stage": "draft_builder",
        "supplier_id": supplier_id,
        "active_run_id": active_run_id,
        "candidate_id": candidate_id,
        "asin": asin,
        "expected_seller_sku": expected_seller_sku,
        "hold_reason": reason,
        "hold_note": note,
        "source_reference": "amazon_listing_intake_live|amazon_listing_sku_reservations_live",
        "intake_id": intake_id,
        "draft_id": draft_id,
        "marketplace_id": marketplace_id,
    }


def _replace_stage_holds(root: Path, *, rows: list[dict[str, str]]) -> None:
    existing = read_f_contract_df(root, "amazon_listing_holds_live")
    if existing.empty:
        retained = existing
    else:
        retained = existing[existing["hold_stage"].map(_normalize_text) != "draft_builder"].copy()
    out_df = pd.concat([retained, pd.DataFrame(rows)], ignore_index=True)
    write_f_contract_df(root, "amazon_listing_holds_live", out_df)


def _write_health(
    root: Path,
    *,
    observed_utc: str,
    ready_rows: int,
    blocked_rows: int,
) -> None:
    check_name = "amazon_listing_draft_builder"
    status = "ok" if blocked_rows == 0 else "warn"
    existing = read_f_contract_df(root, "amazon_listing_health")
    retained = existing[existing["check"].map(_normalize_text) != check_name].copy() if not existing.empty else existing
    health = pd.DataFrame(
        [
            {
                "check": check_name,
                "status": status,
                "value": str(ready_rows),
                "notes": f"ready_rows={ready_rows};blocked_rows={blocked_rows}",
                "observed_utc": observed_utc,
                "source_path": str(root / "out" / "systems" / "F" / "live" / "amazon_listing_sku_reservations_live.csv"),
            }
        ]
    )
    write_f_contract_df(root, "amazon_listing_health", pd.concat([retained, health], ignore_index=True))


def _append_draft_events(root: Path, rows: list[dict[str, str]]) -> None:
    existing = read_f_contract_df(root, "amazon_listing_draft_events")
    out_df = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True)
    write_f_contract_df(root, "amazon_listing_draft_events", out_df)


def build_amazon_listing_drafts(
    *,
    root: Path | None = None,
    observed_utc: str | None = None,
) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)
    observed = observed_utc or _utc_now_iso()

    intake_df = read_f_contract_df(root_path, "amazon_listing_intake_live")
    reservations_df = read_f_contract_df(root_path, "amazon_listing_sku_reservations_live")
    existing_drafts_df = read_f_contract_df(root_path, "amazon_listing_drafts_live")
    existing_drafts = _existing_draft_map(existing_drafts_df)
    reservations = _reservation_map(reservations_df)
    defaults = _load_defaults(root_path)

    draft_rows: list[dict[str, str]] = []
    hold_rows: list[dict[str, str]] = []
    event_rows: list[dict[str, str]] = []

    for record in intake_df.to_dict("records"):
        intake = {key: _normalize_text(value) for key, value in record.items()}
        intake_id = _normalize_text(intake.get("intake_id", ""))
        reservation = reservations.get(intake_id, {})
        reservation_status = _normalize_text(reservation.get("sku_reservation_status", ""))
        reservation_reason = _normalize_text(reservation.get("sku_reservation_reason", ""))
        expected_sku = _normalize_text(reservation.get("expected_seller_sku", ""))
        marketplace_id = _first_non_blank(reservation.get("marketplace_id", ""), intake.get("marketplace_id", ""))
        default_row = _default_for(defaults, marketplace_id=marketplace_id)

        supplier_id = _normalize_text(intake.get("supplier_id", ""))
        active_run_id = _normalize_text(intake.get("active_run_id", ""))
        candidate_id = _normalize_text(intake.get("candidate_id", ""))
        asin = _normalize_key(intake.get("asin", ""))
        draft_id = _hash_id("draft", candidate_id, asin, expected_sku, marketplace_id)

        draft = {
            "observed_utc": observed,
            "draft_id": draft_id,
            "supplier_id": supplier_id,
            "supplier_name": _normalize_text(intake.get("supplier_name", "")),
            "source_run_id": active_run_id,
            "review_snapshot_id": _normalize_text(intake.get("review_snapshot_id", "")),
            "review_batch_id": _normalize_text(intake.get("review_batch_id", "")),
            "candidate_id": candidate_id,
            "supplier_sku": _normalize_text(intake.get("supplier_sku", "")),
            "barcode": _normalize_text(intake.get("barcode", "")),
            "asin": asin,
            "amazon_title": _normalize_text(intake.get("amazon_title", "")),
            "supplier_cost_gbp": _normalize_text(intake.get("supplier_cost_gbp", "")),
            "expected_seller_sku": expected_sku,
            "sku_reservation_status": reservation_status,
            "sku_reservation_reason": reservation_reason,
            "marketplace_id": marketplace_id,
            "country_of_origin": _normalize_country_of_origin(intake.get("country_of_origin", "")),
            "purchase_pack_size": _normalize_text(intake.get("purchase_pack_size", "")),
            "sold_pack_size": _normalize_text(intake.get("sold_pack_size", "")),
            "supplier_case_qty": _normalize_text(intake.get("supplier_case_qty", "")),
            "supplier_case_multiple": _normalize_text(intake.get("supplier_case_multiple", "")),
            "valid_order_step": _normalize_text(intake.get("valid_order_step", "")),
            "moq": _normalize_text(intake.get("moq", "")),
            "target_margin": _normalize_text(intake.get("target_margin", "")),
            "vat_confirmed_flag": _normalize_text(intake.get("vat_confirmed_flag", "")),
            "product_tax_code": _first_non_blank(
                intake.get("product_tax_code", ""),
                default_row.get("product_tax_code", ""),
            ),
            "currency_code": _normalize_currency_code(
                _first_non_blank(intake.get("currency_code", ""), default_row.get("currency_code", ""))
            ),
            "price_includes_tax": _normalize_price_includes_tax(
                _first_non_blank(intake.get("price_includes_tax", ""), default_row.get("price_includes_tax", ""))
            ),
            "product_type": _first_non_blank(intake.get("product_type", ""), default_row.get("product_type", "")),
            "condition_type": _first_non_blank(intake.get("condition_type", ""), default_row.get("condition_type", "")),
            "fulfillment_channel": _first_non_blank(
                intake.get("fulfillment_channel", ""),
                default_row.get("fulfillment_channel", ""),
            ),
            "starting_price_gbp": _first_non_blank(intake.get("starting_price_gbp", ""), default_row.get("starting_price_gbp", "")),
            "starting_quantity": _first_non_blank(intake.get("starting_quantity", ""), default_row.get("starting_quantity", "")),
            "listing_mode": _normalize_text(intake.get("listing_mode", "")),
            "draft_status": "",
            "block_reason": "",
            "amazon_preview_status": "not_run",
            "amazon_preview_issue_count": "0",
            "amazon_submission_status": "not_submitted",
            "amazon_submission_id": "",
            "updated_at_utc": observed,
            "minimum_selling_price_rule": _first_non_blank(
                intake.get("minimum_selling_price_rule", ""),
                default_row.get("minimum_selling_price_rule", ""),
            ),
            "listing_approval_status": "pending_operator_approval",
            "source_intake_id": intake_id,
            "source_reservation_id": _normalize_text(reservation.get("reservation_id", "")),
            "vat_source_value": _normalize_text(intake.get("vat_source_value", "")),
            "profile_event_id": _normalize_text(intake.get("profile_event_id", "")),
            "profile_utc": _normalize_text(intake.get("profile_utc", "")),
            "profile_note": _normalize_text(intake.get("profile_note", "")),
        }

        prior_key = (candidate_id.upper(), asin, expected_sku.upper(), marketplace_id)
        prior = existing_drafts.get(prior_key, {})
        if prior:
            for field in (
                "amazon_preview_status",
                "amazon_preview_issue_count",
                "amazon_submission_status",
                "amazon_submission_id",
                "listing_approval_status",
            ):
                prior_value = _normalize_text(prior.get(field, ""))
                if prior_value != "":
                    draft[field] = prior_value

        missing: list[str] = []
        if reservation_status != "reserved":
            missing.append("reserved_seller_sku")
        missing.extend(_missing_fields(draft))

        if missing:
            block_reason = "missing_local_data:" + ",".join(dict.fromkeys(missing))
            draft["draft_status"] = "blocked_missing_local_data"
            draft["block_reason"] = block_reason
            hold_rows.append(
                _hold_row(
                    observed_utc=observed,
                    supplier_id=supplier_id,
                    active_run_id=active_run_id,
                    candidate_id=candidate_id,
                    asin=asin,
                    expected_seller_sku=expected_sku,
                    reason=block_reason,
                    note="Draft is blocked until required local data is present",
                    intake_id=intake_id,
                    draft_id=draft_id,
                    marketplace_id=marketplace_id,
                )
            )
        else:
            draft["draft_status"] = "ready_for_listing_approval"
            draft["block_reason"] = ""

        draft_rows.append(draft)
        event_rows.append(
            {
                "event_utc": observed,
                "event_id": f"f092-draft-{uuid.uuid4().hex[:12]}",
                "draft_id": draft_id,
                "event_type": "draft_built",
                "draft_status": draft["draft_status"],
                "candidate_id": candidate_id,
                "expected_seller_sku": expected_sku,
                "asin": asin,
                "marketplace_id": marketplace_id,
                "notes": draft["block_reason"],
                "source_reference": intake_id,
            }
        )

    out_df = pd.DataFrame(draft_rows)
    if not out_df.empty:
        out_df = out_df.drop_duplicates(
            subset=["candidate_id", "asin", "expected_seller_sku", "marketplace_id"],
            keep="last",
        )
        out_df = out_df.sort_values(
            by=["supplier_id", "source_run_id", "candidate_id", "asin"],
            ascending=[True, True, True, True],
            kind="stable",
        )

    finalized = write_f_contract_df(root_path, "amazon_listing_drafts_live", out_df)
    _replace_stage_holds(root_path, rows=hold_rows)
    if event_rows:
        _append_draft_events(root_path, event_rows)
    ready_count = int((finalized.get("draft_status", pd.Series(dtype=str)) == "ready_for_listing_approval").sum())
    blocked_count = int((finalized.get("draft_status", pd.Series(dtype=str)) == "blocked_missing_local_data").sum())
    _write_health(root_path, observed_utc=observed, ready_rows=ready_count, blocked_rows=blocked_count)
    print(
        {
            "status": "success",
            "draft_rows": int(len(finalized.index)),
            "ready_rows": ready_count,
            "blocked_rows": blocked_count,
        }
    )
    return finalized


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build draft-only Amazon listing drafts from reserved review-pass intake rows.")
    parser.add_argument("--root", default="")
    parser.add_argument("--observed-utc", default="")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    root = Path(args.root) if _normalize_text(args.root) else None
    observed = _normalize_text(args.observed_utc) or None
    build_amazon_listing_drafts(root=root, observed_utc=observed)


if __name__ == "__main__":
    main()
