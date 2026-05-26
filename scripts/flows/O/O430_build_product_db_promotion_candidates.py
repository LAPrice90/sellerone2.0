from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._contract_io import read_f_contract_df
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df
from scripts.flows.O._pack_rules import product_pack_fields_from_purchase_sold
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    text = str(value or "").strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _hash_id(prefix: str, *parts: object, length: int = 16) -> str:
    raw = "|".join(_normalize_text(part) for part in parts)
    return f"{prefix}_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:length]}"


def _money(value: object) -> str:
    text = _normalize_text(value).replace(",", "").replace("£", "")
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


def _truthy_flag(value: object) -> bool:
    return _normalize_text(value).lower() in {"1", "true", "yes", "y", "on"}


def _vat_rate(value: object) -> str:
    text = _normalize_text(value).replace("%", "").strip()
    if text == "":
        return ""
    try:
        parsed = float(text)
    except Exception:
        return ""
    if parsed < 0:
        return ""
    if parsed.is_integer():
        return str(int(parsed))
    return f"{parsed:.2f}".rstrip("0").rstrip(".")


def _read_product_db_preview(root: Path) -> pd.DataFrame:
    path = root / "out" / "product_db_preview.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame()


def _latest_by_key(df: pd.DataFrame, key_column: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    if df.empty or key_column not in df.columns:
        return out
    for _, row in df.iterrows():
        row_dict = {key: _normalize_text(value) for key, value in row.to_dict().items()}
        key = row_dict.get(key_column, "")
        if key:
            out[key] = row_dict
    return out


def _product_db_skus(product_df: pd.DataFrame) -> set[str]:
    if product_df.empty or "seller_sku" not in product_df.columns:
        return set()
    return {_normalize_key(value) for value in product_df["seller_sku"].tolist() if _normalize_key(value)}


def _active_brand_blocks(queue_df: pd.DataFrame) -> set[str]:
    blocks: set[str] = set()
    if queue_df.empty:
        return blocks
    for _, row in queue_df.iterrows():
        row_dict = {key: _normalize_text(value) for key, value in row.to_dict().items()}
        draft_id = row_dict.get("draft_id", "")
        if not draft_id:
            continue
        status = row_dict.get("approval_status", "")
        if status in {"approval_cleared", "approved", "restriction_clear"}:
            continue
        blocks.add(draft_id)
    return blocks


def _first_non_blank(*values: object) -> str:
    for value in values:
        text = _normalize_text(value)
        if text:
            return text
    return ""


def _pack_profile(*, purchase_pack_size: str, sold_pack_size: str) -> dict[str, str]:
    return product_pack_fields_from_purchase_sold(
        purchase_pack_size=purchase_pack_size,
        sold_pack_size=sold_pack_size,
        source="amazon_listing_profile_review",
    )


def _profile_int(*values: object, fallback: str = "") -> str:
    for value in values:
        parsed = _positive_int(value)
        if parsed:
            return parsed
    return fallback


def _hold_row(
    *,
    observed_utc: str,
    source: dict[str, str],
    reason_codes: list[str],
    note: str,
) -> dict[str, str]:
    seller_sku = _normalize_text(source.get("expected_seller_sku", source.get("seller_sku", "")))
    asin = _normalize_text(source.get("asin", ""))
    return {
        "hold_utc": observed_utc,
        "hold_id": _hash_id("product_db_promotion_hold", source.get("draft_id", ""), seller_sku, asin, ",".join(reason_codes)),
        "draft_id": _normalize_text(source.get("draft_id", "")),
        "candidate_id": _normalize_text(source.get("candidate_id", "")),
        "seller_sku": seller_sku,
        "asin": asin,
        "hold_reason_codes": "|".join(reason_codes),
        "hold_note": note,
        "source_reference": "O430_build_product_db_promotion_candidates.py",
        "supplier_code": _normalize_text(source.get("supplier_id", source.get("supplier_code", ""))),
        "supplier_sku": _normalize_text(source.get("supplier_sku", "")),
        "reconciliation_status": _normalize_text(source.get("reconciliation_status", "")),
    }


def _candidate_row(
    *,
    observed_utc: str,
    rec: dict[str, str],
    draft: dict[str, str],
    intake: dict[str, str],
    reason_codes: list[str],
) -> dict[str, str]:
    seller_sku = _normalize_text(rec.get("expected_seller_sku", "")) or _normalize_text(draft.get("expected_seller_sku", ""))
    asin = _normalize_text(rec.get("asin", "")) or _normalize_text(draft.get("asin", ""))
    purchase_pack = _first_non_blank(draft.get("purchase_pack_size", ""), intake.get("purchase_pack_size", ""))
    sold_pack = _first_non_blank(draft.get("sold_pack_size", ""), intake.get("sold_pack_size", ""))
    pack = _pack_profile(purchase_pack_size=purchase_pack, sold_pack_size=sold_pack)
    supplier_case_qty = _profile_int(draft.get("supplier_case_qty", ""), intake.get("supplier_case_qty", ""), fallback=pack.get("supplier_case_qty", ""))
    valid_order_step = _profile_int(draft.get("valid_order_step", ""), intake.get("valid_order_step", ""), fallback=pack.get("valid_order_step", ""))
    moq = _profile_int(draft.get("moq", ""), intake.get("moq", ""), fallback=pack.get("moq", ""))
    supplier_case_multiple = _first_non_blank(draft.get("supplier_case_multiple", ""), intake.get("supplier_case_multiple", ""), pack.get("supplier_case_multiple", ""))
    supplier_cost = _money(_first_non_blank(draft.get("supplier_cost_gbp", ""), intake.get("supplier_cost_gbp", "")))
    vat_source = _first_non_blank(draft.get("vat_source_value", ""), intake.get("vat_source_value", ""))
    vat_rate = _vat_rate(vat_source)
    if not vat_rate and _first_non_blank(draft.get("product_tax_code", ""), intake.get("product_tax_code", "")) == "A_GEN_STANDARD":
        vat_rate = ""

    return {
        "observed_utc": observed_utc,
        "promotion_id": _hash_id("product_db_promotion", rec.get("draft_id", ""), seller_sku, asin),
        "draft_id": _normalize_text(rec.get("draft_id", "")),
        "candidate_id": _normalize_text(rec.get("candidate_id", draft.get("candidate_id", ""))),
        "seller_sku": seller_sku,
        "asin": asin,
        "amazon_title": _first_non_blank(draft.get("amazon_title", ""), intake.get("amazon_title", "")),
        "supplier_code": _first_non_blank(draft.get("supplier_id", ""), intake.get("supplier_id", "")),
        "supplier_name": _first_non_blank(draft.get("supplier_name", ""), intake.get("supplier_name", "")),
        "supplier_sku": _first_non_blank(draft.get("supplier_sku", ""), intake.get("supplier_sku", "")),
        "barcode": _first_non_blank(draft.get("barcode", ""), intake.get("barcode", "")),
        "promotion_status": "ready_for_product_db_event" if not reason_codes else "held",
        "block_reason_codes": "|".join(reason_codes),
        "sale_status": "inactive",
        "supplier_pack_size": pack.get("supplier_pack_size", ""),
        "amazon_pack_size": pack.get("amazon_pack_size", ""),
        "order_qty_mode": pack.get("order_qty_mode", ""),
        "sell_pack_qty": pack.get("sell_pack_qty", ""),
        "supplier_case_qty": supplier_case_qty,
        "supplier_case_multiple": supplier_case_multiple,
        "valid_order_step": valid_order_step,
        "repack_required": pack.get("repack_required", ""),
        "bundle_required": pack.get("bundle_required", ""),
        "pack_conversion_note": pack.get("pack_conversion_note", ""),
        "moq": moq,
        "supplier_catalog_price": supplier_cost,
        "last_purchase_price": supplier_cost,
        "target_margin": _first_non_blank(draft.get("target_margin", ""), intake.get("target_margin", "")),
        "vat_rate": vat_rate,
        "notes": (
            "Created from Amazon-confirmed new product listing. "
            f"COO={_first_non_blank(draft.get('country_of_origin', ''), intake.get('country_of_origin', ''))}; "
            f"starting_price_gbp={_first_non_blank(draft.get('starting_price_gbp', ''), intake.get('starting_price_gbp', ''))}."
        ),
        "source_reference": "amazon_listing_reconciliation_live|amazon_listing_drafts_live|amazon_listing_intake_live",
        "updated_at_utc": observed_utc,
        "amazon_submission_id": _normalize_text(rec.get("submission_id", "")),
        "reconciliation_status": _normalize_text(rec.get("reconciliation_status", "")),
        "country_of_origin": _first_non_blank(draft.get("country_of_origin", ""), intake.get("country_of_origin", "")),
        "product_tax_code": _first_non_blank(draft.get("product_tax_code", ""), intake.get("product_tax_code", "")),
        "vat_confirmed_flag": _first_non_blank(draft.get("vat_confirmed_flag", ""), intake.get("vat_confirmed_flag", "")),
        "vat_source_value": vat_source,
        "starting_price_gbp": _first_non_blank(draft.get("starting_price_gbp", ""), intake.get("starting_price_gbp", "")),
    }


def _missing_profile_reasons(candidate: dict[str, str]) -> list[str]:
    reasons: list[str] = []
    required = {
        "seller_sku": "missing_seller_sku",
        "asin": "missing_asin",
        "supplier_code": "missing_supplier_code",
        "supplier_name": "missing_supplier_name",
        "supplier_pack_size": "missing_purchase_pack_size",
        "amazon_pack_size": "missing_sold_pack_size",
        "supplier_case_qty": "missing_supplier_case_qty",
        "valid_order_step": "missing_valid_order_step",
        "moq": "missing_moq",
        "supplier_catalog_price": "missing_supplier_cost",
        "vat_rate": "missing_vat_rate",
    }
    for field, reason in required.items():
        if _normalize_text(candidate.get(field, "")) == "":
            reasons.append(reason)
    if _normalize_text(candidate.get("vat_confirmed_flag", "")) != "1":
        reasons.append("missing_vat_confirmation")
    return reasons


def _write_health(root: Path, *, observed_utc: str, ready_rows: int, held_rows: int, blocked_rows: int) -> None:
    check_name = "product_db_promotion_candidates"
    status = "fail" if blocked_rows > 0 else ("warn" if held_rows > 0 else "ok")
    row = pd.DataFrame(
        [
            {
                "check": check_name,
                "status": status,
                "value": str(ready_rows),
                "notes": f"ready_rows={ready_rows};held_rows={held_rows};blocked_rows={blocked_rows}",
                "observed_utc": observed_utc,
                "source_path": str(root / "out" / "systems" / "F" / "live" / "amazon_listing_reconciliation_live.csv"),
            }
        ]
    )
    existing = read_o_contract_df(root, "product_db_promotion_health")
    retained = existing[existing["check"].map(_normalize_text) != check_name].copy() if not existing.empty else existing
    write_o_contract_df(root, "product_db_promotion_health", pd.concat([retained, row], ignore_index=True))


def build_product_db_promotion_candidates(
    *,
    root: Path | None = None,
    observed_utc: str | None = None,
) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    observed = observed_utc or _utc_now_iso()
    reconciliation = read_f_contract_df(root_path, "amazon_listing_reconciliation_live")
    drafts = read_f_contract_df(root_path, "amazon_listing_drafts_live")
    intake = read_f_contract_df(root_path, "amazon_listing_intake_live")
    approval_queue = read_f_contract_df(root_path, "brand_approval_queue_live")
    product_db = _read_product_db_preview(root_path)

    drafts_by_id = _latest_by_key(drafts, "draft_id")
    intake_by_candidate = _latest_by_key(intake, "candidate_id")
    product_db_skus = _product_db_skus(product_db)
    brand_blocks = _active_brand_blocks(approval_queue)

    candidate_rows: list[dict[str, str]] = []
    hold_rows: list[dict[str, str]] = []
    blocked_rows = 0

    for _, rec_row in reconciliation.iterrows():
        rec = {key: _normalize_text(value) for key, value in rec_row.to_dict().items()}
        draft_id = rec.get("draft_id", "")
        draft = drafts_by_id.get(draft_id, {})
        intake_row = intake_by_candidate.get(_normalize_text(rec.get("candidate_id", "")) or _normalize_text(draft.get("candidate_id", "")), {})
        source = {**draft, **intake_row, **rec}
        reasons: list[str] = []
        hard_blocked = False

        if rec.get("reconciliation_status", "") != "confirmed_product_db_eligible":
            reasons.append(rec.get("block_reason", "") or rec.get("reconciliation_status", "") or "not_product_db_eligible")
            hard_blocked = True
        if draft_id in brand_blocks:
            reasons.append("brand_approval_block")
            hard_blocked = True
        seller_sku = _normalize_key(rec.get("expected_seller_sku", ""))
        if seller_sku and seller_sku in product_db_skus:
            reasons.append("duplicate_product_db_seller_sku")
            hard_blocked = True
        if hard_blocked:
            blocked_rows += 1

        candidate = _candidate_row(observed_utc=observed, rec=rec, draft=draft, intake=intake_row, reason_codes=reasons)
        reasons = [*reasons, *[reason for reason in _missing_profile_reasons(candidate) if reason not in reasons]]
        candidate["block_reason_codes"] = "|".join(reasons)
        candidate["promotion_status"] = "ready_for_product_db_event" if not reasons else "held"
        if reasons:
            hold_rows.append(
                _hold_row(
                    observed_utc=observed,
                    source=source,
                    reason_codes=reasons,
                    note="Product DB promotion blocked until all required profile and reconciliation gates pass.",
                )
            )
        if rec.get("reconciliation_status", "") == "confirmed_product_db_eligible":
            candidate_rows.append(candidate)

    candidates_out = write_o_contract_df(root_path, "product_db_promotion_candidates_live", pd.DataFrame(candidate_rows))
    holds_out = write_o_contract_df(root_path, "product_db_promotion_holds_live", pd.DataFrame(hold_rows))
    ready_rows = int((candidates_out["promotion_status"].map(_normalize_text) == "ready_for_product_db_event").sum()) if not candidates_out.empty else 0
    held_rows = int((candidates_out["promotion_status"].map(_normalize_text) == "held").sum()) if not candidates_out.empty else 0
    _write_health(root_path, observed_utc=observed, ready_rows=ready_rows, held_rows=held_rows, blocked_rows=blocked_rows)
    print(
        {
            "status": "success",
            "candidate_rows": int(len(candidates_out.index)),
            "ready_rows": ready_rows,
            "held_rows": held_rows,
            "hold_rows": int(len(holds_out.index)),
            "blocked_rows": blocked_rows,
        }
    )
    return candidates_out


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Product DB promotion candidates from Amazon listing reconciliation.")
    parser.add_argument("--root", default="")
    parser.add_argument("--observed-utc", default="")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    root = Path(args.root) if _normalize_text(args.root) else None
    observed = _normalize_text(args.observed_utc) or None
    build_product_db_promotion_candidates(root=root, observed_utc=observed)


if __name__ == "__main__":
    main()
