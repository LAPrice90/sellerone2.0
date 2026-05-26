from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import pandas as pd

from scripts.flows.F.f_scanner_timeout_policy import read_timeout_policy_df
from scripts.flows.F.f_scanner_timeout_policy import resolve_timeout_policy_row
from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import ensure_manager_test_mode_dir
from scripts.flows.F.price_list_manager._schemas import (
    BARCODE_SCAN_MEMORY_COLUMNS,
    BATCH_ROW_COLUMNS,
    BATCH_SCAN_ELIGIBILITY_COLUMNS,
    PLACEHOLDER_SCANNER_RESULT_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
)


PolicyResolver = Callable[[str], tuple[dict[str, str], str, bool]]
SKIP_BATCH_STATUSES = {"superseded"}


def _parse_utc(value: object) -> datetime | None:
    raw = normalize_text(value)
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        parsed = pd.to_datetime(raw, errors="coerce", utc=True)
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime()


def _parse_float(value: object) -> float | None:
    raw = normalize_text(value)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _changed(previous: object, current: object) -> bool:
    old = normalize_text(previous)
    new = normalize_text(current)
    return old != "" and new != "" and old != new


def _effective_timeout_days(row: dict[str, str]) -> float | None:
    mode = normalize_text(row.get("timeout_mode", "")).lower()
    timeout_days = _parse_float(row.get("timeout_days", ""))
    max_timeout_days = _parse_float(row.get("max_timeout_days", ""))
    if mode in {"until_cost_changes", "until_source_changes"} and max_timeout_days is not None:
        return max_timeout_days
    return timeout_days


def _timeout_until_for_policy_row(*, last_scanned_at_utc: str, row: dict[str, str]) -> str:
    mode = normalize_text(row.get("timeout_mode", "")).lower()
    if row.get("enabled") != "1" or mode in {"disabled", "manual_review"}:
        return ""
    days = _effective_timeout_days(row)
    if days is None or days <= 0:
        return ""
    scanned_dt = _parse_utc(last_scanned_at_utc) or datetime.now(timezone.utc)
    return (scanned_dt + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _policy_resolver(timeout_policy: pd.DataFrame) -> PolicyResolver:
    cache: dict[str, tuple[dict[str, str], str, bool]] = {}

    def resolve(fail_code: str) -> tuple[dict[str, str], str, bool]:
        code = normalize_text(fail_code).upper() or "FAIL"
        cached = cache.get(code)
        if cached is not None:
            return cached
        resolved = resolve_timeout_policy_row(timeout_policy, code)
        cache[code] = resolved
        return resolved

    return resolve


def _timeout_policy_decision(
    *,
    fail_code: str,
    policy_resolver: PolicyResolver,
    last_scanned_at_utc: str,
    observed_utc: str,
    timeout_until_utc: str = "",
    previous_unit_cost: object = "",
    current_unit_cost: object = "",
    previous_source_hash: object = "",
    current_source_hash: object = "",
) -> tuple[bool, str, str, str]:
    row, effective_code, fallback_used = policy_resolver(fail_code)
    mode = normalize_text(row.get("timeout_mode", "")).lower()
    if row.get("enabled") != "1" or mode == "disabled":
        return False, "policy_disabled", "", effective_code
    if mode == "manual_review" or row.get("manual_review_required_flag") == "1":
        return True, "manual_review_required", "", effective_code
    if row.get("cost_change_resets_flag") == "1" or mode == "until_cost_changes":
        if _changed(previous_unit_cost, current_unit_cost):
            return False, "cost_changed_reset", "", effective_code
    if row.get("source_change_resets_flag") == "1" or mode == "until_source_changes":
        if _changed(previous_source_hash, current_source_hash):
            return False, "source_changed_reset", "", effective_code

    timeout_until = normalize_text(timeout_until_utc)
    if timeout_until == "":
        timeout_until = _timeout_until_for_policy_row(last_scanned_at_utc=last_scanned_at_utc, row=row)
    timeout_dt = _parse_utc(timeout_until)
    observed_dt = _parse_utc(observed_utc) or datetime.now(timezone.utc)
    if timeout_dt is not None and timeout_dt > observed_dt:
        reason = "timeout_active_fallback_fail" if fallback_used else "timeout_active"
        return True, reason, timeout_until, effective_code
    return False, "timeout_expired_or_missing", timeout_until, effective_code


def _memory_by_key(memory: pd.DataFrame) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    if memory.empty:
        return out
    work = memory.copy()
    work["_updated"] = work["updated_at_utc"].map(normalize_text) if "updated_at_utc" in work.columns else ""
    work = work.sort_values("_updated", ascending=False, kind="stable")
    for _, row in work.iterrows():
        key = normalize_text(row.get("memory_key", ""))
        if key and key not in out:
            out[key] = row
    return out


def _processed_row_keys(results: pd.DataFrame) -> set[str]:
    if results.empty or "row_key" not in results.columns:
        return set()
    return {normalize_text(value) for value in results["row_key"].tolist() if normalize_text(value)}


def _candidate_memory_keys(row: pd.Series) -> list[str]:
    supplier_id = normalize_text(row.get("supplier_id", ""))
    barcode = normalize_text(row.get("barcode", ""))
    unit_cost = normalize_text(row.get("unit_cost", ""))
    if not barcode:
        return []
    return [
        f"supplier_offer:{supplier_id}:{barcode}:{unit_cost}",
        f"barcode:{barcode}",
    ]


def _latest_supplier_offer_by_prefix(memory_map: dict[str, pd.Series]) -> dict[str, tuple[str, pd.Series]]:
    out: dict[str, tuple[str, pd.Series]] = {}
    latest_updated: dict[str, str] = {}
    for key, memory_row in memory_map.items():
        parts = key.split(":", 3)
        if len(parts) < 4 or parts[0] != "supplier_offer":
            continue
        prefix = f"{parts[0]}:{parts[1]}:{parts[2]}:"
        updated = normalize_text(memory_row.get("updated_at_utc", ""))
        if prefix not in out or updated > latest_updated.get(prefix, ""):
            out[prefix] = (key, memory_row)
            latest_updated[prefix] = updated
    return out


def _active_memory(
    row: pd.Series,
    memory_map: dict[str, pd.Series],
    supplier_offer_prefix_map: dict[str, tuple[str, pd.Series]] | None = None,
) -> tuple[str, pd.Series | None]:
    for key in _candidate_memory_keys(row):
        memory_row = memory_map.get(key)
        if memory_row is not None:
            return key, memory_row

    supplier_id = normalize_text(row.get("supplier_id", ""))
    barcode = normalize_text(row.get("barcode", ""))
    if not supplier_id or not barcode:
        return "", None

    prefix = f"supplier_offer:{supplier_id}:{barcode}:"
    if supplier_offer_prefix_map is not None:
        matched = supplier_offer_prefix_map.get(prefix)
        if matched is not None:
            return matched
        return "", None

    latest_key = ""
    latest_row = None
    latest_updated = ""
    for key, memory_row in memory_map.items():
        if not key.startswith(prefix):
            continue
        updated = normalize_text(memory_row.get("updated_at_utc", ""))
        if latest_row is None or updated > latest_updated:
            latest_key = key
            latest_row = memory_row
            latest_updated = updated
    if latest_row is not None:
        return latest_key, latest_row
    return "", None


def _unit_cost_from_memory_key(memory_key: str) -> str:
    parts = normalize_text(memory_key).split(":")
    if len(parts) >= 4 and parts[0] == "supplier_offer":
        return parts[-1]
    return ""


def _base_payload(row: pd.Series, *, observed_utc: str, base_eligibility: str) -> dict[str, str]:
    return {
        "batch_id": normalize_text(row.get("batch_id", "")),
        "supplier_id": normalize_text(row.get("supplier_id", "")),
        "row_key": normalize_text(row.get("row_key", "")),
        "supplier_sku": normalize_text(row.get("supplier_sku", "")),
        "barcode": normalize_text(row.get("barcode", "")),
        "unit_cost": normalize_text(row.get("unit_cost", "")),
        "base_eligibility": base_eligibility,
        "scan_decision": "",
        "decision_reason": "",
        "memory_key": "",
        "cooldown_until_utc": "",
        "observed_utc": observed_utc,
    }


def scan_decision_for_row(
    row: pd.Series,
    *,
    observed_utc: str,
    memory_map: dict[str, pd.Series],
    supplier_offer_prefix_map: dict[str, tuple[str, pd.Series]] | None = None,
    processed_keys: set[str],
    timeout_policy: pd.DataFrame,
    policy_resolver: PolicyResolver | None = None,
) -> dict[str, str]:
    base_eligibility = normalize_text(row.get("scan_eligibility", "")).lower()
    payload = _base_payload(row, observed_utc=observed_utc, base_eligibility=base_eligibility)
    row_key = payload["row_key"]
    barcode = payload["barcode"]
    unit_cost = payload["unit_cost"]

    if row_key in processed_keys:
        payload.update(scan_decision="skip", decision_reason="already_processed_in_placeholder_results")
        return payload
    if not barcode:
        payload.update(scan_decision="skip", decision_reason="missing_barcode")
        return payload
    if not unit_cost:
        payload.update(scan_decision="skip", decision_reason="missing_unit_cost")
        return payload
    if base_eligibility != "scan_now":
        payload.update(
            scan_decision="skip",
            decision_reason=normalize_text(row.get("eligibility_reason", "")) or "base_eligibility_not_scan_now",
        )
        return payload

    memory_key, memory_row = _active_memory(row, memory_map, supplier_offer_prefix_map)
    if memory_row is not None:
        fail_code = normalize_text(memory_row.get("last_fail_code", ""))
        result_status = normalize_text(memory_row.get("last_result_status", "")).upper()
        if result_status == "PASS":
            previous_unit_cost = _unit_cost_from_memory_key(memory_key)
            if previous_unit_cost and previous_unit_cost != unit_cost:
                payload.update(
                    scan_decision="scan",
                    decision_reason="pass_cost_changed_reset",
                    memory_key=memory_key,
                    cooldown_until_utc="",
                )
                return payload
            if previous_unit_cost:
                payload.update(
                    scan_decision="skip",
                    decision_reason="already_passed_in_memory",
                    memory_key=memory_key,
                    cooldown_until_utc="",
                )
                return payload
        if fail_code and result_status in {"FAIL", "RESCAN"}:
            resolver = policy_resolver or _policy_resolver(timeout_policy)
            skip, reason, timeout_until, _effective_code = _timeout_policy_decision(
                fail_code=fail_code,
                policy_resolver=resolver,
                last_scanned_at_utc=normalize_text(memory_row.get("last_scanned_at_utc", "")),
                observed_utc=observed_utc,
                previous_unit_cost=_unit_cost_from_memory_key(memory_key),
                current_unit_cost=unit_cost,
                previous_source_hash=normalize_text(memory_row.get("last_row_hash", "")),
                current_source_hash=normalize_text(row.get("source_row_hash", "")),
            )
            payload.update(
                scan_decision="skip" if skip else "scan",
                decision_reason=reason,
                memory_key=memory_key,
                cooldown_until_utc=timeout_until,
            )
            return payload

    cooldown_until = normalize_text(memory_row.get("cooldown_until_utc", "")) if memory_row is not None else ""
    cooldown_dt = _parse_utc(cooldown_until)
    observed_dt = _parse_utc(observed_utc) or datetime.now(timezone.utc)
    if cooldown_dt is not None and cooldown_dt > observed_dt:
        payload.update(
            scan_decision="skip",
            decision_reason="cooldown_active",
            memory_key=memory_key,
            cooldown_until_utc=cooldown_until,
        )
        return payload

    payload.update(
        scan_decision="scan",
        decision_reason="eligible_after_memory_check" if memory_row is not None else "new_or_no_active_memory",
        memory_key=memory_key,
        cooldown_until_utc=cooldown_until,
    )
    return payload


def build_timeout_queue_eligibility(
    *,
    batch_rows: pd.DataFrame,
    memory: pd.DataFrame,
    timeout_policy: pd.DataFrame,
    observed_utc: str,
    results: pd.DataFrame | None = None,
) -> pd.DataFrame:
    memory_map = _memory_by_key(memory)
    supplier_offer_prefix_map = _latest_supplier_offer_by_prefix(memory_map)
    policy_resolver = _policy_resolver(timeout_policy)
    processed_keys = _processed_row_keys(results if results is not None else pd.DataFrame())
    rows = [
        scan_decision_for_row(
            row,
            observed_utc=observed_utc,
            memory_map=memory_map,
            supplier_offer_prefix_map=supplier_offer_prefix_map,
            processed_keys=processed_keys,
            timeout_policy=timeout_policy,
            policy_resolver=policy_resolver,
        )
        for _, row in batch_rows.iterrows()
    ]
    return pd.DataFrame(rows, columns=BATCH_SCAN_ELIGIBILITY_COLUMNS)


def _timeout_skip_mask(eligibility: pd.DataFrame) -> pd.Series:
    reasons = eligibility["decision_reason"].map(normalize_text) if "decision_reason" in eligibility.columns else pd.Series()
    return reasons.isin({"timeout_active", "timeout_active_fallback_fail", "manual_review_required"})


def update_batches_with_timeout_queue_counts(
    *,
    batches: pd.DataFrame,
    batch_rows: pd.DataFrame,
    eligibility: pd.DataFrame,
    observed_utc: str,
) -> pd.DataFrame:
    updated = batches.copy()
    if updated.empty or batch_rows.empty:
        return updated
    for batch_id, group in batch_rows.groupby("batch_id", dropna=False):
        batch_key = normalize_text(batch_id)
        if not batch_key:
            continue
        batch_index = updated[updated["batch_id"].map(normalize_text) == batch_key].index
        if len(batch_index) == 0:
            continue
        eligibility_group = eligibility[eligibility["batch_id"].map(normalize_text) == batch_key].copy()
        if eligibility_group.empty:
            continue
        scan_count = int((eligibility_group["scan_decision"].map(normalize_text) == "scan").sum())
        timeout_skip_count = int(_timeout_skip_mask(eligibility_group).sum())
        new_count = int(
            (
                (eligibility_group["scan_decision"].map(normalize_text) == "scan")
                & (eligibility_group["decision_reason"].map(normalize_text) == "new_or_no_active_memory")
            ).sum()
        )
        changed_count = int(
            eligibility_group["decision_reason"]
            .map(normalize_text)
            .isin({"cost_changed_reset", "source_changed_reset", "pass_cost_changed_reset"})
            .sum()
        )
        idx = batch_index[-1]
        updated.at[idx, "eligible_row_count"] = str(scan_count)
        updated.at[idx, "skipped_cooldown_row_count"] = str(timeout_skip_count)
        updated.at[idx, "new_row_count"] = str(new_count)
        updated.at[idx, "changed_row_count"] = str(changed_count)
        updated.at[idx, "updated_at_utc"] = observed_utc
    return updated


def _apply_batch_status_skips(eligibility: pd.DataFrame, batches: pd.DataFrame) -> pd.DataFrame:
    if eligibility.empty or batches.empty:
        return eligibility
    skip_batch_ids = {
        normalize_text(row.get("batch_id", ""))
        for _, row in batches.iterrows()
        if normalize_text(row.get("batch_status", "")).lower() in SKIP_BATCH_STATUSES
    }
    if not skip_batch_ids:
        return eligibility
    updated = eligibility.copy()
    mask = updated["batch_id"].map(lambda value: normalize_text(value) in skip_batch_ids)
    updated.loc[mask, "scan_decision"] = "skip"
    updated.loc[mask, "decision_reason"] = "superseded_batch"
    updated.loc[mask, "memory_key"] = ""
    updated.loc[mask, "cooldown_until_utc"] = ""
    return updated


def refresh_timeout_queue_files(
    root=None,
    *,
    observed_utc: str,
) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=root)
    test_dir = paths.test_mode_dir
    rows_path = test_dir / "batch_rows.csv"
    batches_path = test_dir / "price_list_batches.csv"
    eligibility_path = test_dir / "batch_scan_eligibility.csv"

    batch_rows = read_csv(rows_path, BATCH_ROW_COLUMNS)
    batches = read_csv(batches_path, PRICE_LIST_BATCH_COLUMNS)
    memory = read_csv(test_dir / "barcode_scan_memory.csv", BARCODE_SCAN_MEMORY_COLUMNS)
    results = read_csv(test_dir / "placeholder_scanner_results.csv", PLACEHOLDER_SCANNER_RESULT_COLUMNS)
    timeout_policy = read_timeout_policy_df(root=paths.root, create_if_missing=True, observed_utc=observed_utc)

    eligibility = build_timeout_queue_eligibility(
        batch_rows=batch_rows,
        memory=memory,
        results=results,
        timeout_policy=timeout_policy,
        observed_utc=observed_utc,
    )
    eligibility = _apply_batch_status_skips(eligibility, batches)
    eligibility = write_csv(eligibility_path, eligibility, BATCH_SCAN_ELIGIBILITY_COLUMNS)
    updated_batches = update_batches_with_timeout_queue_counts(
        batches=batches,
        batch_rows=batch_rows,
        eligibility=eligibility,
        observed_utc=observed_utc,
    )
    updated_batches = write_csv(batches_path, updated_batches, PRICE_LIST_BATCH_COLUMNS)
    timeout_skip_rows = int(_timeout_skip_mask(eligibility).sum()) if not eligibility.empty else 0
    scan_rows = int((eligibility["scan_decision"].map(normalize_text) == "scan").sum()) if not eligibility.empty else 0
    return {
        "status": "success",
        "batch_rows": int(len(batch_rows.index)),
        "batches": int(len(updated_batches.index)),
        "eligibility_rows": int(len(eligibility.index)),
        "scan_rows": scan_rows,
        "timeout_skip_rows": timeout_skip_rows,
        "eligibility_path": str(eligibility_path),
        "batches_path": str(batches_path),
    }
