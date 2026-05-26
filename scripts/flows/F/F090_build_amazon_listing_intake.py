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

from scripts.flows.F._contract_io import read_f_contract_df, write_f_contract_df
from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract
from scripts.flows.F._scanner_state import has_required_dashboard_signal


DEFAULT_MARKETPLACE_ID = "A1F83G8C2ARO7P"
LISTING_MODE_EXISTING_ASIN = "existing_asin_offer"
REVIEW_IDENTITY_COLUMNS = ("active_supplier_id", "active_run_id", "review_pack_type", "candidate_id")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    text = str(value or "").strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


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


def _normalize_positive_money(value: object) -> str:
    text = _normalize_text(value).replace(",", "")
    if text == "":
        return ""
    try:
        parsed = float(text)
    except Exception:
        return ""
    if parsed <= 0:
        return ""
    return f"{parsed:.2f}"


def _normalize_positive_int_text(value: object) -> str:
    text = _normalize_text(value).replace(",", "")
    if text == "":
        return ""
    try:
        parsed = float(text)
    except Exception:
        return ""
    if parsed <= 0 or parsed != int(parsed):
        return ""
    return str(int(parsed))


def _normalize_truthy_flag(value: object) -> str:
    text = _normalize_text(value).lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return "1"
    if text in {"0", "false", "no", "n", "off"}:
        return "0"
    return ""


def _normalize_price_includes_tax(value: object) -> str:
    text = _normalize_text(value).lower()
    if text in {"0", "false", "no", "n", "off"}:
        return "0"
    if text in {"1", "true", "yes", "y", "on"}:
        return "1"
    return ""


def _hash_id(prefix: str, *parts: object, length: int = 16) -> str:
    raw = "|".join(_normalize_text(part) for part in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}_{digest}"


def _read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _resolve_path(root: Path, raw_path: object) -> Path:
    text = _normalize_text(raw_path)
    if text == "":
        return Path()
    path = Path(text)
    if path.is_absolute():
        return path
    return root / path


def _manifest_paths(root: Path) -> list[Path]:
    base = root / "out" / "systems" / "F" / "price_list_manager"
    candidates: list[Path] = [base / "live" / "review_handoff_manifest.csv"]
    handoff_root = base / "review_handoffs"
    if handoff_root.exists():
        candidates.extend(handoff_root.glob("*/*/manifest.csv"))
    seen: set[str] = set()
    out: list[Path] = []
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        if path.exists():
            out.append(path)
    return out


def _load_completed_manifest_rows(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in _manifest_paths(root):
        frame = _read_csv_safe(path)
        if frame.empty:
            continue
        for record in frame.to_dict("records"):
            row = {key: _normalize_text(value) for key, value in record.items()}
            if row.get("block_reason", "") != "":
                continue
            if row.get("ai_gate_status", "").lower() != "passed" or row.get("operator_ready_flag", "") != "1":
                continue
            if row.get("pass_review_path", "") == "":
                continue
            row["_manifest_path"] = str(path)
            rows.append(row)
    return rows


def _load_latest_analysis_review_manifest_rows(root: Path) -> list[dict[str, str]]:
    pass_path = root / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
    summary_path = root / "out" / "analysis_reports" / "f_live_price_file_review_summary_latest.csv"
    if not pass_path.exists():
        return []
    summary: dict[str, str] = {}
    summary_df = _read_csv_safe(summary_path)
    if not summary_df.empty:
        for record in summary_df.to_dict("records"):
            metric = _normalize_text(record.get("metric", ""))
            if metric != "":
                summary[metric] = _normalize_text(record.get("value", ""))
    pass_df = _read_csv_safe(pass_path)
    if pass_df.empty:
        return []
    return [
        {
            "built_at_utc": _normalize_text(summary_df.iloc[0].get("observed_utc", "")) if not summary_df.empty else "",
            "supplier_id": summary.get("active_supplier_id", ""),
            "supplier_name": summary.get("active_supplier_label", "") or summary.get("active_supplier_id", ""),
            "run_id": summary.get("active_run_id", ""),
            "review_snapshot_id": "latest",
            "source_seen_at_utc": summary.get("source_seen_at_utc", ""),
            "completed_at_utc": _normalize_text(summary_df.iloc[0].get("observed_utc", "")) if not summary_df.empty else "",
            "pass_review_rows": str(len(pass_df.index)),
            "pass_review_path": str(pass_path),
            "near_miss_review_path": str(root / "out" / "analysis_reports" / "f_live_price_file_near_miss_review_latest.csv"),
            "summary_path": str(summary_path),
            "block_reason": "",
            "notes": "fallback_latest_analysis_review_pack",
            "_manifest_path": str(summary_path),
        }
    ]


def _latest_review_events(events_df: pd.DataFrame) -> dict[tuple[str, str, str, str], dict[str, str]]:
    if events_df.empty:
        return {}
    work = events_df.copy()
    for column in REVIEW_IDENTITY_COLUMNS:
        if column not in work.columns:
            work[column] = ""
        work[column] = work[column].map(_normalize_text)
    if "event_utc" not in work.columns:
        work["event_utc"] = ""
    if "event_id" not in work.columns:
        work["event_id"] = ""
    work["_event_sort"] = pd.to_datetime(work["event_utc"], errors="coerce", utc=True)
    work = work.sort_values(by=["_event_sort", "event_id"], ascending=[False, False], kind="stable")
    latest: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for _, row in work.iterrows():
        record = {key: _normalize_text(value) for key, value in row.to_dict().items()}
        key = tuple(record.get(column, "") for column in REVIEW_IDENTITY_COLUMNS)
        if any(part == "" for part in key):
            continue
        if key not in latest:
            latest[key] = record
    return latest


def _latest_profile_events(events_df: pd.DataFrame) -> dict[tuple[str, str, str, str], dict[str, str]]:
    latest: dict[tuple[str, str, str, str], dict[str, str]] = {}
    if events_df.empty:
        return latest
    work = events_df.copy()
    work["_event_sort"] = pd.to_datetime(work.get("event_utc", ""), errors="coerce", utc=True)
    work = work.sort_values(by=["_event_sort", "event_id"], ascending=[True, True], kind="stable")
    for _, row in work.iterrows():
        row_dict = {key: _normalize_text(value) for key, value in row.to_dict().items()}
        if row_dict.get("profile_status", "").lower() != "complete":
            continue
        key = tuple(row_dict.get(column, "") for column in REVIEW_IDENTITY_COLUMNS)
        if any(part == "" for part in key):
            continue
        latest[key] = row_dict
    return latest


def _first_non_blank(record: dict[str, str], *fields: str) -> str:
    for field in fields:
        value = _normalize_text(record.get(field, ""))
        if value != "":
            return value
    return ""


def _pass_row_missing_required_dashboard_yes_no(record: dict[str, str]) -> bool:
    code = _normalize_text(record.get("seller_history_code", ""))
    if code not in {"seller_history_clear", "single_fba_seller_amazon_absent", "single_seller_owner_unclear"}:
        return False
    return not has_required_dashboard_signal(record.get("seller_history_dashboard_yes_or_no", ""))


def _load_supplier_cost_lookup(root: Path) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    candidates = [
        root / "out" / "analysis_reports" / "f_dashboard_yes_no_rescan_plan_latest.csv",
        root / "out" / "systems" / "F" / "live" / "feeder_legacy_first_checks_live.csv",
    ]
    for path in candidates:
        frame = _read_csv_safe(path)
        if frame.empty:
            continue
        for record_raw in frame.to_dict("records"):
            record = {key: _normalize_text(value) for key, value in record_raw.items()}
            candidate_id = _first_non_blank(record, "candidate_id")
            asin = _first_non_blank(record, "asin", "asin_padded", "asin_raw").upper()
            supplier_sku = _first_non_blank(record, "supplier_sku", "sku")
            cost = _normalize_positive_money(
                _first_non_blank(
                    record,
                    "supplier_cost_gbp",
                    "unit_cost",
                    "cost",
                    "current_supplier_buy_cost_gbp",
                    "supplier_catalog_price",
                )
            )
            if cost == "":
                continue
            for key in ((candidate_id, asin), (supplier_sku, asin)):
                if all(part != "" for part in key) and key not in out:
                    out[key] = cost
    return out


def _normalize_asin(record: dict[str, str], event: dict[str, str] | None = None) -> str:
    return _first_non_blank(
        record,
        "asin",
        "asin_padded",
        "asin_raw",
        "ASIN",
    ) or (_first_non_blank(event or {}, "asin_padded", "asin_raw", "asin") if event else "")


def _hold_row(
    *,
    observed_utc: str,
    stage: str,
    supplier_id: str,
    active_run_id: str,
    candidate_id: str,
    asin: str,
    reason: str,
    note: str,
    source_reference: str,
    intake_id: str = "",
    marketplace_id: str = DEFAULT_MARKETPLACE_ID,
) -> dict[str, str]:
    return {
        "hold_utc": observed_utc,
        "hold_id": _hash_id("hold", stage, supplier_id, active_run_id, candidate_id, asin, reason),
        "hold_stage": stage,
        "supplier_id": supplier_id,
        "active_run_id": active_run_id,
        "candidate_id": candidate_id,
        "asin": asin,
        "expected_seller_sku": "",
        "hold_reason": reason,
        "hold_note": note,
        "source_reference": source_reference,
        "intake_id": intake_id,
        "draft_id": "",
        "marketplace_id": marketplace_id,
    }


def _replace_stage_holds(root: Path, *, stage: str, rows: list[dict[str, str]]) -> None:
    existing = read_f_contract_df(root, "amazon_listing_holds_live")
    if existing.empty:
        retained = existing
    else:
        retained = existing[existing["hold_stage"].map(_normalize_text) != stage].copy()
    out_df = pd.concat([retained, pd.DataFrame(rows)], ignore_index=True)
    write_f_contract_df(root, "amazon_listing_holds_live", out_df)


def _write_health(
    root: Path,
    *,
    observed_utc: str,
    intake_rows: int,
    hold_rows: int,
    source_path: str,
) -> None:
    check_name = "amazon_listing_intake_bridge"
    status = "ok" if hold_rows == 0 else "warn"
    existing = read_f_contract_df(root, "amazon_listing_health")
    retained = existing[existing["check"].map(_normalize_text) != check_name].copy() if not existing.empty else existing
    health = pd.DataFrame(
        [
            {
                "check": check_name,
                "status": status,
                "value": str(intake_rows),
                "notes": f"intake_rows={intake_rows};hold_rows={hold_rows}",
                "observed_utc": observed_utc,
                "source_path": source_path,
            }
        ]
    )
    write_f_contract_df(root, "amazon_listing_health", pd.concat([retained, health], ignore_index=True))


def build_amazon_listing_intake(
    *,
    root: Path | None = None,
    observed_utc: str | None = None,
) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)
    observed = observed_utc or _utc_now_iso()

    events_df = read_f_contract_df(root_path, "feeder_review_events")
    latest_events = _latest_review_events(events_df)
    profile_events_df = read_f_contract_df(root_path, "amazon_listing_profile_events")
    latest_profiles = _latest_profile_events(profile_events_df)
    manifest_rows = _load_completed_manifest_rows(root_path)
    supplier_cost_lookup = _load_supplier_cost_lookup(root_path)

    intake_rows: list[dict[str, str]] = []
    hold_rows: list[dict[str, str]] = []
    matched_event_keys: set[tuple[str, str, str, str]] = set()

    for manifest in manifest_rows:
        manifest_path = _normalize_text(manifest.get("_manifest_path", ""))
        review_pack_path = _resolve_path(root_path, manifest.get("pass_review_path", ""))
        pack_df = _read_csv_safe(review_pack_path)
        if pack_df.empty:
            continue
        for record_raw in pack_df.to_dict("records"):
            record = {key: _normalize_text(value) for key, value in record_raw.items()}
            supplier_id = _first_non_blank(record, "active_supplier_id", "supplier_id") or _normalize_text(
                manifest.get("supplier_id", "")
            )
            active_run_id = _first_non_blank(record, "active_run_id", "run_id") or _normalize_text(manifest.get("run_id", ""))
            review_pack_type = "passes"
            candidate_id = _first_non_blank(record, "candidate_id")
            asin = _normalize_asin(record)
            intake_id = _hash_id("intake", supplier_id, active_run_id, candidate_id, asin, DEFAULT_MARKETPLACE_ID)
            key = (supplier_id, active_run_id, review_pack_type, candidate_id)
            event = latest_events.get(key)
            source_reference = f"{manifest_path}|{review_pack_path}"

            if _normalize_text(record.get("f032_decision_id", "")) == "" or _normalize_text(record.get("f032_action", "")) == "":
                hold_rows.append(
                    _hold_row(
                        observed_utc=observed,
                        stage="intake",
                        supplier_id=supplier_id,
                        active_run_id=active_run_id,
                        candidate_id=candidate_id,
                        asin=asin,
                        reason="ai_gate_decision_missing",
                        note="AI-gated pass review row is missing F032 decision evidence",
                        source_reference=source_reference,
                        intake_id=intake_id,
                    )
                )
                continue

            if candidate_id == "":
                hold_rows.append(
                    _hold_row(
                        observed_utc=observed,
                        stage="intake",
                        supplier_id=supplier_id,
                        active_run_id=active_run_id,
                        candidate_id="",
                        asin=asin,
                        reason="missing_candidate_id",
                        note="completed pass review pack row has no candidate_id",
                        source_reference=source_reference,
                        intake_id=intake_id,
                    )
                )
                continue

            if _pass_row_missing_required_dashboard_yes_no(record):
                hold_rows.append(
                    _hold_row(
                        observed_utc=observed,
                        stage="intake",
                        supplier_id=supplier_id,
                        active_run_id=active_run_id,
                        candidate_id=candidate_id,
                        asin=asin,
                        reason="dashboard_yes_no_backtrack_required",
                        note="pass review row is missing required BBP dashboard Yes/No evidence",
                        source_reference=source_reference,
                        intake_id=intake_id,
                    )
                )
                continue

            matched_event_keys.add(key)
            if event is None:
                hold_rows.append(
                    _hold_row(
                        observed_utc=observed,
                        stage="intake",
                        supplier_id=supplier_id,
                        active_run_id=active_run_id,
                        candidate_id=candidate_id,
                        asin=asin,
                        reason="no_review_pass_event",
                        note="completed pass review pack row has no New Product Review pass event",
                        source_reference=source_reference,
                        intake_id=intake_id,
                    )
                )
                continue

            review_decision = _normalize_text(event.get("review_decision", "")).lower()
            asin = _normalize_asin(record, event)
            intake_id = _hash_id("intake", supplier_id, active_run_id, candidate_id, asin, DEFAULT_MARKETPLACE_ID)
            if review_decision != "pass":
                hold_rows.append(
                    _hold_row(
                        observed_utc=observed,
                        stage="intake",
                        supplier_id=supplier_id,
                        active_run_id=active_run_id,
                        candidate_id=candidate_id,
                        asin=asin,
                        reason="latest_review_decision_not_pass",
                        note=f"latest_review_decision={review_decision or 'blank'}",
                        source_reference=source_reference,
                        intake_id=intake_id,
                    )
                )
                continue

            profile = latest_profiles.get(key)
            if profile is None:
                hold_rows.append(
                    _hold_row(
                        observed_utc=observed,
                        stage="intake",
                        supplier_id=supplier_id,
                        active_run_id=active_run_id,
                        candidate_id=candidate_id,
                        asin=asin,
                        reason="product_listing_profile_required",
                        note="New Product Review pass is waiting for Product Listing Profile Review completion",
                        source_reference=source_reference,
                        intake_id=intake_id,
                    )
                )
                continue

            country_of_origin = _normalize_country_of_origin(profile.get("country_of_origin", ""))
            purchase_pack_size = _normalize_positive_int_text(profile.get("purchase_pack_size", ""))
            sold_pack_size = _normalize_positive_int_text(profile.get("sold_pack_size", ""))
            supplier_case_qty = _normalize_positive_int_text(profile.get("supplier_case_qty", "")) or purchase_pack_size
            supplier_case_multiple = _normalize_truthy_flag(profile.get("supplier_case_multiple", ""))
            valid_order_step = _normalize_positive_int_text(profile.get("valid_order_step", "")) or supplier_case_qty
            moq = _normalize_positive_int_text(profile.get("moq", "")) or "1"
            vat_confirmed_flag = _normalize_truthy_flag(profile.get("vat_confirmed_flag", ""))
            vat_source_value = _normalize_text(profile.get("vat_source_value", "")).replace("%", "")
            product_tax_code = _normalize_text(profile.get("product_tax_code", ""))
            currency_code = _normalize_currency_code(profile.get("currency_code", ""))
            price_includes_tax = _normalize_price_includes_tax(profile.get("price_includes_tax", ""))
            starting_price_gbp = _normalize_positive_money(
                _first_non_blank(
                    profile,
                    "starting_price_gbp",
                )
                or _first_non_blank(record, "starting_price_gbp", "target_sell_price_gbp")
            )
            missing_compliance = []
            if country_of_origin == "":
                missing_compliance.append("country_of_origin")
            if purchase_pack_size == "":
                missing_compliance.append("purchase_pack_size")
            if sold_pack_size == "":
                missing_compliance.append("sold_pack_size")
            if supplier_case_qty == "":
                missing_compliance.append("supplier_case_qty")
            if valid_order_step == "":
                missing_compliance.append("valid_order_step")
            if moq == "":
                missing_compliance.append("moq")
            if vat_source_value == "":
                missing_compliance.append("vat_source_value")
            if vat_confirmed_flag != "1":
                missing_compliance.append("vat_confirmed_flag")
            if product_tax_code == "":
                missing_compliance.append("product_tax_code")
            if currency_code == "":
                missing_compliance.append("currency_code")
            if price_includes_tax == "":
                missing_compliance.append("price_includes_tax")
            if starting_price_gbp == "":
                missing_compliance.append("starting_price_gbp")
            if missing_compliance:
                hold_rows.append(
                    _hold_row(
                        observed_utc=observed,
                        stage="intake",
                        supplier_id=supplier_id,
                        active_run_id=active_run_id,
                        candidate_id=candidate_id,
                        asin=asin,
                        reason="missing_listing_compliance:" + ",".join(missing_compliance),
                        note="Product Listing Profile Review is missing required Amazon listing/profile fields",
                        source_reference=source_reference,
                        intake_id=intake_id,
                    )
                )
                continue
            supplier_sku = _first_non_blank(record, "supplier_sku") or _normalize_text(event.get("supplier_sku", ""))
            supplier_cost_gbp = _first_non_blank(
                record,
                "supplier_cost_gbp",
                "unit_cost",
                "cost",
                "current_supplier_buy_cost_gbp",
                "supplier_catalog_price",
            )
            if supplier_cost_gbp == "":
                supplier_cost_gbp = supplier_cost_lookup.get((candidate_id, asin), "") or supplier_cost_lookup.get(
                    (supplier_sku, asin),
                    "",
                )

            intake_rows.append(
                {
                    "observed_utc": observed,
                    "intake_id": intake_id,
                    "supplier_id": supplier_id,
                    "supplier_name": _first_non_blank(record, "supplier_name", "supplier") or _normalize_text(
                        manifest.get("supplier_name", "")
                    ),
                    "active_run_id": active_run_id,
                    "review_pack_type": review_pack_type,
                    "review_snapshot_id": _normalize_text(manifest.get("review_snapshot_id", "")),
                    "review_batch_id": _first_non_blank(record, "review_batch_id") or _normalize_text(
                        event.get("review_batch_id", "")
                    ),
                    "candidate_id": candidate_id,
                    "supplier_sku": supplier_sku,
                    "barcode": _first_non_blank(record, "barcode", "ean", "upc"),
                    "asin": asin,
                    "amazon_title": _first_non_blank(record, "title", "amazon_title") or _normalize_text(event.get("title", "")),
                    "brand": _first_non_blank(record, "brand") or _normalize_text(event.get("brand", "")),
                    "supplier_cost_gbp": supplier_cost_gbp,
                    "starting_price_gbp": starting_price_gbp,
                    "marketplace_id": _first_non_blank(record, "marketplace_id") or DEFAULT_MARKETPLACE_ID,
                    "country_of_origin": country_of_origin,
                    "purchase_pack_size": purchase_pack_size,
                    "sold_pack_size": sold_pack_size,
                    "supplier_case_qty": supplier_case_qty,
                    "supplier_case_multiple": supplier_case_multiple,
                    "valid_order_step": valid_order_step,
                    "moq": moq,
                    "target_margin": _normalize_text(profile.get("target_margin", "")),
                    "vat_confirmed_flag": vat_confirmed_flag,
                    "product_tax_code": product_tax_code,
                    "currency_code": currency_code,
                    "price_includes_tax": price_includes_tax,
                    "listing_mode": LISTING_MODE_EXISTING_ASIN,
                    "latest_review_event_id": _normalize_text(event.get("event_id", "")),
                    "latest_review_utc": _normalize_text(event.get("event_utc", "")),
                    "intake_status": "ready_for_sku_reservation",
                    "block_reason": "",
                    "source_manifest_path": manifest_path,
                    "source_review_pack_path": str(review_pack_path),
                    "updated_at_utc": observed,
                    "main_rank": _first_non_blank(record, "main_rank") or _normalize_text(event.get("main_rank", "")),
                    "review_priority_score": _first_non_blank(record, "review_priority_score")
                    or _normalize_text(event.get("review_priority_score", "")),
                    "source_seen_at_utc": _normalize_text(manifest.get("source_seen_at_utc", "")),
                    "review_note": _normalize_text(event.get("review_note", "")),
                    "vat_source_value": vat_source_value,
                    "starting_quantity": _normalize_positive_int_text(profile.get("starting_quantity", "")),
                    "condition_type": _normalize_text(profile.get("condition_type", "")),
                    "profile_event_id": _normalize_text(profile.get("event_id", "")),
                    "profile_utc": _normalize_text(profile.get("event_utc", "")),
                    "profile_note": _normalize_text(profile.get("profile_note", "")),
                }
            )

    for key, event in latest_events.items():
        if key in matched_event_keys:
            continue
        review_decision = _normalize_text(event.get("review_decision", "")).lower()
        review_pack_type = _normalize_text(event.get("review_pack_type", ""))
        if review_pack_type != "passes" or review_decision != "pass":
            continue
        supplier_id, active_run_id, _, candidate_id = key
        asin = _normalize_asin(event)
        intake_id = _hash_id("intake", supplier_id, active_run_id, candidate_id, asin, DEFAULT_MARKETPLACE_ID)
        hold_rows.append(
            _hold_row(
                observed_utc=observed,
                stage="intake",
                supplier_id=supplier_id,
                active_run_id=active_run_id,
                candidate_id=candidate_id,
                asin=asin,
                reason="no_completed_review_pack",
                note="New Product Review pass event has no matching completed pass review pack row",
                source_reference=_normalize_text(event.get("source_reference", "")) or "feeder_review_events",
                intake_id=intake_id,
            )
        )

    intake_df = pd.DataFrame(intake_rows)
    if not intake_df.empty:
        intake_df = intake_df.drop_duplicates(
            subset=["supplier_id", "active_run_id", "candidate_id", "asin", "marketplace_id"],
            keep="last",
        )
        intake_df = intake_df.sort_values(
            by=["supplier_id", "active_run_id", "review_batch_id", "candidate_id"],
            ascending=[True, True, True, True],
            kind="stable",
        )

    finalized = write_f_contract_df(root_path, "amazon_listing_intake_live", intake_df)
    _replace_stage_holds(root_path, stage="intake", rows=hold_rows)
    source_path = str(root_path / "out" / "systems" / "F" / "inbox" / "feeder_review_events.csv")
    _write_health(
        root_path,
        observed_utc=observed,
        intake_rows=int(len(finalized.index)),
        hold_rows=len(hold_rows),
        source_path=source_path,
    )
    print(
        {
            "status": "success",
            "intake_rows": int(len(finalized.index)),
            "hold_rows": len(hold_rows),
        }
    )
    return finalized


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build draft-only Amazon listing intake from New Product Review pass events.")
    parser.add_argument("--root", default="")
    parser.add_argument("--observed-utc", default="")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    root = Path(args.root) if _normalize_text(args.root) else None
    observed = _normalize_text(args.observed_utc) or None
    build_amazon_listing_intake(root=root, observed_utc=observed)


if __name__ == "__main__":
    main()
