from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
CONFIG = ROOT / "config"
SOURCE = "A016_refresh_phase1_daily_intel"
DEFAULT_CONFIG_PATH = ROOT / "config" / "pilot_sku.yaml"
MANUAL_CAPS_PATH = CONFIG / "phase1_manual_max_caps.csv"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts import phase1_main_loop, phase1_sku_scope, phase1_storage
    from scripts.phase1_target_universe import resolve_target_universe
    from scripts.api.get_competitive_summary import fetch_cpt_for_asin
except ModuleNotFoundError:
    import phase1_main_loop
    import phase1_sku_scope
    import phase1_storage
    from phase1_target_universe import resolve_target_universe
    from api.get_competitive_summary import fetch_cpt_for_asin


def _norm(value: object) -> str:
    return str(value or "").strip()


def _to_float(value: object) -> float | None:
    raw = _norm(value)
    if not raw:
        return None
    try:
        return float(raw)
    except Exception:
        return None


def _to_int(value: object) -> int | None:
    raw = _norm(value)
    if not raw:
        return None
    try:
        return int(float(raw))
    except Exception:
        return None


def _to_dt(value: object) -> datetime | None:
    text = _norm(value)
    if not text:
        return None
    try:
        raw = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _parse_scalar(text: str) -> object:
    raw = str(text).strip()
    if raw == "":
        return ""
    low = raw.lower()
    if low in {"true", "yes", "on"}:
        return True
    if low in {"false", "no", "off"}:
        return False
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except Exception:
        return raw.strip("\"'")


def _simple_yaml_load(path: Path) -> dict:
    root: dict[str, object] = {}
    stack: list[tuple[int, dict[str, object]]] = [(-1, root)]
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        text = line.strip()
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if ":" not in text:
            continue
        key, value = text.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            child: dict[str, object] = {}
            parent[key] = child
            stack.append((indent, child))
            continue
        parent[key] = _parse_scalar(value)
    return root


def _cfg_get(cfg: dict, *keys: str, default: object = "") -> object:
    cur: object = cfg
    for key in keys:
        if not isinstance(cur, dict):
            return default
        if key not in cur:
            return default
        cur = cur[key]
    return cur


def _to_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _cfg_float(cfg: dict, *keys: str, default: float) -> float:
    value = _to_float(_cfg_get(cfg, *keys, default=default))
    if value is None:
        return float(default)
    return float(value)


def _latest_listing_map() -> dict[str, dict[str, str]]:
    files = sorted(OUT.glob("listing_offer_snapshot_*.csv"))
    if not files:
        return {}
    try:
        df = pd.read_csv(files[-1], dtype=str).fillna("")
    except Exception:
        return {}
    out: dict[str, dict[str, str]] = {}
    for _, row in df.iterrows():
        rec = {str(k): _norm(v) for k, v in row.to_dict().items()}
        sku = _norm(rec.get("sku", "")).upper()
        if not sku or sku in out:
            continue
        out[sku] = rec
    return out


def _load_manual_caps() -> tuple[dict[str, str], dict[str, str]]:
    by_sku: dict[str, str] = {}
    by_asin: dict[str, str] = {}
    if not MANUAL_CAPS_PATH.exists():
        return by_sku, by_asin
    try:
        df = pd.read_csv(MANUAL_CAPS_PATH, dtype=str).fillna("")
    except Exception:
        return by_sku, by_asin
    for _, row in df.iterrows():
        cap = _to_float(row.get("manual_max_price_gbp", ""))
        if cap is None or cap <= 0:
            continue
        cap_text = f"{cap:.2f}"
        sku = _norm(row.get("sku", "")).upper()
        asin = _norm(row.get("asin", "")).upper()
        if sku and sku not in by_sku:
            by_sku[sku] = cap_text
        if asin and asin not in by_asin:
            by_asin[asin] = cap_text
    return by_sku, by_asin


def _resolve_manual_cap(
    *,
    sku: str,
    asin: str,
    listing_row: dict[str, str],
    cfg: dict,
    manual_cap_by_sku: dict[str, str],
    manual_cap_by_asin: dict[str, str],
) -> str:
    configured_default = _norm(_cfg_get(cfg, "boundaries", "manual_cap_gbp", default=""))
    cap = manual_cap_by_sku.get(sku) or manual_cap_by_asin.get(asin) or configured_default
    if _norm(cap):
        return _norm(cap)
    buy_box = _to_float(listing_row.get("buy_box_price", ""))
    if buy_box is not None and buy_box > 0:
        return f"{buy_box:.2f}"
    our_price = _to_float(listing_row.get("our_price", ""))
    if our_price is not None and our_price > 0:
        return f"{our_price:.2f}"
    return ""


def _resolve_compliance_anchor(
    *,
    listing_row: dict[str, str],
    manual_cap_gbp: str,
    cfg: dict,
) -> str:
    configured = _norm(_cfg_get(cfg, "daily_intel", "compliance_anchor_gbp", default=""))
    if configured:
        return configured
    if _norm(manual_cap_gbp):
        return manual_cap_gbp
    buy_box = _to_float(listing_row.get("buy_box_price", ""))
    if buy_box is not None and buy_box > 0:
        return f"{buy_box:.2f}"
    our_price = _to_float(listing_row.get("our_price", ""))
    if our_price is not None and our_price > 0:
        return f"{our_price:.2f}"
    return ""


def _cpt_age_due(
    *,
    tier: str,
    cpt_status: str,
    last_refresh_utc: str,
    now_utc: str,
    no_cpt_recheck_hours: float = 168.0,
) -> tuple[bool, list[str], str]:
    reasons: list[str] = []
    tier_up = _norm(tier).upper()
    if tier_up == "PARKED":
        return False, ["CPT_SKIP_PARKED"], "SKIP"

    status_up = _norm(cpt_status).upper() or "MISSING"
    last_dt = _to_dt(last_refresh_utc)
    now_dt = _to_dt(now_utc) or datetime.now(timezone.utc)

    if status_up == "NO_CPT":
        weekly_window = timedelta(hours=max(float(no_cpt_recheck_hours), 1.0))
        if last_dt is None:
            reasons.append("CPT_DUE_NO_CPT_WEEKLY")
            return True, reasons, "DUE_NO_CPT_WEEKLY"
        age = now_dt - last_dt
        if age >= weekly_window:
            reasons.append("CPT_DUE_NO_CPT_WEEKLY")
            return True, reasons, "DUE_NO_CPT_WEEKLY"
        reasons.append("CPT_SKIP_NO_CPT_WEEKLY_NOT_DUE")
        return False, reasons, "SKIP_NO_CPT_WEEKLY"

    # Recovery mode: if CPT is missing/error, retry once per UTC day.
    if status_up in {"MISSING", "ERROR"}:
        if last_dt is None:
            reasons.append("CPT_DUE_STATUS_RECOVERY_NO_LAST_REFRESH")
            return True, reasons, "DUE_MISSING_ERROR"
        if last_dt.date() < now_dt.date():
            reasons.append("CPT_DUE_STATUS_RECOVERY_NEW_DAY")
            return True, reasons, "DUE_MISSING_ERROR"
        reasons.append("CPT_SKIP_STATUS_RECOVERY_ALREADY_RETRIED_TODAY")
        return False, reasons, "SKIP"

    if tier_up == "ACTIVE_WRITE":
        max_age = timedelta(hours=24)
    else:
        max_age = timedelta(hours=72)

    if last_dt is None:
        reasons.append("CPT_DUE_MISSING_LAST_REFRESH")
        return True, reasons, "DUE_STALE"
    age = now_dt - last_dt
    if age >= max_age:
        reasons.append(f"CPT_DUE_STALE_{int(max_age.total_seconds() // 3600)}H")
        return True, reasons, "DUE_STALE"
    reasons.append("CPT_SKIP_FRESH")
    return False, reasons, "SKIP"


def _compute_cpt_risk(
    *,
    cpt_gbp: str,
    buy_box_gbp: str,
    high_pct: float,
    medium_pct: float,
) -> tuple[str, str, str, list[str]]:
    reasons: list[str] = []
    cpt = _to_float(cpt_gbp)
    buy_box = _to_float(buy_box_gbp)
    if cpt is None or cpt <= 0:
        reasons.append("CPT_RISK_UNKNOWN_MISSING_CPT")
        return "UNKNOWN", "", "", reasons
    if buy_box is None or buy_box <= 0:
        reasons.append("CPT_RISK_UNKNOWN_MISSING_BUY_BOX")
        return "UNKNOWN", "", "", reasons
    delta = buy_box - cpt
    pct = (delta / cpt) * 100 if cpt else 0.0
    if pct >= high_pct:
        band = "HIGH"
        reasons.append("CPT_RISK_HIGH")
    elif pct >= medium_pct:
        band = "MEDIUM"
        reasons.append("CPT_RISK_MEDIUM")
    else:
        band = "LOW"
        reasons.append("CPT_RISK_LOW")
    return band, f"{delta:.2f}", f"{pct:.2f}", reasons


def _load_cfg(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return _simple_yaml_load(path)
    except Exception:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="A016 - Refresh Phase 1 daily intel (full DB or single SKU)")
    parser.add_argument("--phase1-config", default=str(DEFAULT_CONFIG_PATH), help="Path to phase1 YAML config")
    parser.add_argument("--scope", choices=["full_db", "single_sku"], default="full_db", help="Refresh scope")
    parser.add_argument("--sku", default="", help="Required when --scope single_sku")
    parser.add_argument("--max-skus", type=int, default=0, help="Optional cap for full_db scope")
    parser.add_argument("--dry-run", action="store_true", help="Do not write sku_daily_intel rows")
    parser.add_argument("--force", action="store_true", help="Reserved for parity")
    args = parser.parse_args()

    cfg_path = Path(args.phase1_config)
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    cfg = _load_cfg(cfg_path)

    now_utc = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    listing_map = _latest_listing_map()
    manual_cap_by_sku, manual_cap_by_asin = _load_manual_caps()
    high_pct = float(_norm(_cfg_get(cfg, "daily_intel", "cpt_high_risk_pct", default="5")) or "5")
    medium_pct = float(_norm(_cfg_get(cfg, "daily_intel", "cpt_medium_risk_pct", default="2")) or "2")
    cpt_call_spacing_seconds = max(_cfg_float(cfg, "daily_intel", "cpt_call_spacing_seconds", default=31.0), 0.0)
    cpt_no_value_recheck_hours = max(_cfg_float(cfg, "daily_intel", "cpt_no_value_recheck_hours", default=168.0), 1.0)

    scope_df, scope_path = phase1_sku_scope.build_and_write_scope(asof_utc=now_utc)
    scope_mode = _norm(args.scope).lower()
    single_sku = _norm(args.sku).upper() or _norm(_cfg_get(cfg, "sku", default="")).upper()
    target_cfg: dict[str, object] = dict(cfg)
    if scope_mode == "single_sku":
        if not single_sku:
            raise SystemExit("[A016] --sku is required when --scope single_sku")
        target_cfg["target_universe_mode"] = "single_sku"
        target_cfg["pilot_whitelist_sku"] = single_sku
        target_cfg["pilot_whitelist_skus"] = single_sku
        target_cfg["sku"] = single_sku

    target_universe = resolve_target_universe(target_cfg, out_dir=OUT)
    target_skus = [
        _norm(s).upper()
        for s in (target_universe.get("skus") or [])
        if _norm(s)
    ]
    if scope_mode == "single_sku" and not target_skus:
        raise SystemExit(f"[A016] SKU not resolved from config/scope: {single_sku}")

    max_skus = max(int(args.max_skus), 0)
    if scope_mode != "single_sku" and max_skus > 0:
        target_skus = target_skus[:max_skus]

    scope_rows = [{str(k): _norm(v) for k, v in r.items()} for r in scope_df.to_dict(orient="records")]
    scope_by_sku = {
        _norm(r.get("sku", "")).upper(): r
        for r in scope_rows
        if _norm(r.get("sku", ""))
    }
    rows: list[dict[str, str]] = []
    for sku in target_skus:
        rec = scope_by_sku.get(sku)
        if rec is None:
            rec = {
                "sku": sku,
                "asin": "",
                "writer_mode": "READ_ONLY",
                "cpt_tier": "ACTIVE_READONLY",
                "parked_flag": "0",
                "park_reason_codes": "",
            }
        rows.append(rec)

    processed = 0
    cpt_calls = 0
    cpt_due_stale_count = 0
    cpt_due_missing_error_count = 0
    cpt_due_no_cpt_weekly_count = 0
    cpt_skip_no_cpt_weekly_count = 0
    cpt_no_cpt_rows = 0
    cpt_reused_or_skipped_count = 0
    coverage_missing = 0
    dry_run_plans = 0
    last_result: phase1_main_loop.AcycleResult | None = None
    last_cpt_call_started_monotonic: float | None = None

    for rec in rows:
        sku = _norm(rec.get("sku", "")).upper()
        if not sku:
            continue
        listing_row = listing_map.get(sku, {})
        asin = _norm(rec.get("asin", "")).upper() or _norm(listing_row.get("asin", "")).upper()
        writer_mode = _norm(rec.get("writer_mode", "")).upper() or "READ_ONLY"
        tier = _norm(rec.get("cpt_tier", "")).upper() or ("ACTIVE_WRITE" if writer_mode == "CODEX_H" else "ACTIVE_READONLY")
        parked_flag = _norm(rec.get("parked_flag", "")) or "0"
        park_reasons = [x for x in _norm(rec.get("park_reason_codes", "")).split("|") if x]

        latest_daily = phase1_storage.read_latest("sku_daily_intel", {"sku": sku}) or {}
        latest_cpt_status = _norm(latest_daily.get("cpt_status", "")) or "MISSING"
        last_cpt_refresh = _norm(latest_daily.get("cpt_last_refresh_utc", ""))
        should_call_cpt, cpt_call_reason_codes, cpt_due_bucket = _cpt_age_due(
            tier=tier,
            cpt_status=latest_cpt_status,
            last_refresh_utc=last_cpt_refresh,
            now_utc=now_utc,
            no_cpt_recheck_hours=cpt_no_value_recheck_hours,
        )
        if cpt_due_bucket == "DUE_STALE":
            cpt_due_stale_count += 1
        elif cpt_due_bucket == "DUE_MISSING_ERROR":
            cpt_due_missing_error_count += 1
        elif cpt_due_bucket == "DUE_NO_CPT_WEEKLY":
            cpt_due_no_cpt_weekly_count += 1
        elif cpt_due_bucket == "SKIP_NO_CPT_WEEKLY":
            cpt_skip_no_cpt_weekly_count += 1

        cpt_payload = {
            "cpt_gbp": _norm(latest_daily.get("cpt_gbp", "")),
            "cpt_status": latest_cpt_status,
            "cpt_last_refresh_utc": _norm(latest_daily.get("cpt_last_refresh_utc", "")) or now_utc,
            "reason_codes": [],
            "error_summary": "",
        }

        if tier == "PARKED":
            cpt_call_reason_codes = ["CPT_SKIP_PARKED"]
            cpt_reused_or_skipped_count += 1
        elif not asin:
            cpt_call_reason_codes.append("CPT_SKIP_NO_ASIN")
            cpt_payload["cpt_status"] = "MISSING"
            cpt_reused_or_skipped_count += 1
        elif should_call_cpt and args.dry_run:
            cpt_call_reason_codes.append("CPT_SKIP_DRY_RUN")
            cpt_reused_or_skipped_count += 1
        elif should_call_cpt:
            if cpt_call_spacing_seconds > 0 and last_cpt_call_started_monotonic is not None:
                elapsed = max(time.monotonic() - last_cpt_call_started_monotonic, 0.0)
                wait_seconds = cpt_call_spacing_seconds - elapsed
                if wait_seconds > 0:
                    time.sleep(wait_seconds)
                    cpt_call_reason_codes.append(f"CPT_CALL_SPACING_WAIT_{wait_seconds:.1f}S")
            last_cpt_call_started_monotonic = time.monotonic()
            cpt_payload = fetch_cpt_for_asin(
                asin=asin,
                marketplace_id=_norm(_cfg_get(cfg, "marketplace_id", default="")) or "A1F83G8C2ARO7P",
                run_id=run_id,
                script_name=SOURCE,
            )
            cpt_calls += 1
            cpt_call_reason_codes.append("CPT_CALL_PERFORMED")
        else:
            cpt_call_reason_codes.append("CPT_REUSE_LAST")
            cpt_reused_or_skipped_count += 1

        cpt_status = _norm(cpt_payload.get("cpt_status", "MISSING")).upper() or "MISSING"
        if cpt_status == "NO_CPT":
            cpt_no_cpt_rows += 1
        cpt_gbp = _norm(cpt_payload.get("cpt_gbp", ""))
        cpt_last_refresh = _norm(cpt_payload.get("cpt_last_refresh_utc", "")) or now_utc
        cpt_reason_codes = [str(x).strip() for x in (cpt_payload.get("reason_codes") or []) if str(x).strip()]
        cpt_error_summary = _norm(cpt_payload.get("error_summary", ""))
        if cpt_error_summary:
            cpt_call_reason_codes.append(f"CPT_ERROR_SUMMARY:{cpt_error_summary[:120]}")

        buy_box = _norm(listing_row.get("buy_box_price", ""))
        cpt_risk_band, cpt_delta_gbp, cpt_delta_pct, cpt_risk_reasons = _compute_cpt_risk(
            cpt_gbp=cpt_gbp,
            buy_box_gbp=buy_box,
            high_pct=high_pct,
            medium_pct=medium_pct,
        )
        cpt_call_reason_codes.extend(cpt_reason_codes + cpt_risk_reasons)

        manual_cap = _resolve_manual_cap(
            sku=sku,
            asin=asin,
            listing_row=listing_row,
            cfg=cfg,
            manual_cap_by_sku=manual_cap_by_sku,
            manual_cap_by_asin=manual_cap_by_asin,
        )
        compliance_anchor = _resolve_compliance_anchor(
            listing_row=listing_row,
            manual_cap_gbp=manual_cap,
            cfg=cfg,
        )
        extra_reason_codes = []
        if not _norm(compliance_anchor):
            extra_reason_codes.append("COMPLIANCE_ANCHOR_MISSING")
        if not _norm(manual_cap):
            extra_reason_codes.append("MANUAL_CAP_MISSING")

        if args.dry_run:
            dry_run_plans += 1
            processed += 1
            continue

        result = phase1_main_loop.run_a_cycle(
            sku=sku,
            now_utc=now_utc,
            compliance_anchor_gbp=compliance_anchor,
            policy_buffer_pct=_cfg_get(cfg, "boundaries", "policy_buffer_pct", default="0.03"),
            manual_cap_gbp=manual_cap,
            foep_price_gbp=_cfg_get(cfg, "daily_intel", "foep_price_gbp", default=buy_box),
            foep_status=_cfg_get(cfg, "daily_intel", "foep_status", default="MISSING"),
            foep_last_refresh_utc=_cfg_get(cfg, "daily_intel", "foep_last_refresh_utc", default=now_utc),
            cpt_gbp=cpt_gbp,
            cpt_last_refresh_utc=cpt_last_refresh,
            cpt_status=cpt_status,
            last_known_safe_gbp=_cfg_get(cfg, "daily_intel", "last_known_safe_gbp", default=_norm(listing_row.get("our_price", ""))),
            foep_stale_hours=int(float(_cfg_get(cfg, "eligibility", "foep_stale_hours", default=48))),
            foep_sanity_min_mult=_cfg_get(cfg, "eligibility", "foep_sanity_min_mult", default="0.50"),
            foep_sanity_max_mult=_cfg_get(cfg, "eligibility", "foep_sanity_max_mult", default="2.00"),
            market_reference_price_gbp=_cfg_get(cfg, "daily_intel", "market_reference_price_gbp", default=buy_box),
            extra_reason_codes=extra_reason_codes,
            cpt_risk_band=cpt_risk_band,
            cpt_delta_vs_buy_box_gbp=cpt_delta_gbp,
            cpt_delta_vs_buy_box_pct=cpt_delta_pct,
            cpt_call_tier=tier,
            cpt_call_reason_codes=cpt_call_reason_codes,
            parked_flag=parked_flag,
            park_reason_codes=park_reasons,
        )
        processed += 1
        last_result = result
        if not _norm(result.compliance_ceiling_landed_gbp):
            coverage_missing += 1

    total_scope_rows = len(scope_df.index)
    total_parked = int(scope_df.get("parked_flag", "").astype(str).str.strip().eq("1").sum()) if not scope_df.empty else 0
    total_non_parked = total_scope_rows - total_parked

    print(f"a016_scope={scope_mode}")
    print(f"a016_target_universe_mode={_norm(target_universe.get('mode', ''))}")
    print(f"a016_target_universe_source={_norm(target_universe.get('source', ''))}")
    print(f"a016_target_universe_mode_source={_norm(target_universe.get('mode_source', ''))}")
    print(f"a016_target_universe_candidate_count={_to_int(target_universe.get('candidate_count', 0)) or 0}")
    print(f"a016_target_universe_resolved_count={_to_int(target_universe.get('resolved_count', 0)) or 0}")
    print(
        "a016_target_universe_skipped_no_listing_count="
        f"{_to_int(target_universe.get('skipped_no_listing_count', 0)) or 0}"
    )
    print(
        "a016_target_universe_skipped_out_of_stock_count="
        f"{_to_int(target_universe.get('skipped_out_of_stock_count', 0)) or 0}"
    )
    print(f"a016_target_universe_notes={_norm(target_universe.get('notes_csv', ''))}")
    print(f"a016_scope_file={scope_path}")
    print(f"a016_scope_rows={total_scope_rows}")
    print(f"a016_scope_non_parked={total_non_parked}")
    print(f"a016_scope_parked={total_parked}")
    print(f"a016_processed={processed}")
    print(f"a016_cpt_calls={cpt_calls}")
    print(f"a016_cpt_due_stale={cpt_due_stale_count}")
    print(f"a016_cpt_due_missing_error={cpt_due_missing_error_count}")
    print(f"a016_cpt_due_no_cpt_weekly={cpt_due_no_cpt_weekly_count}")
    print(f"a016_cpt_skip_no_cpt_weekly={cpt_skip_no_cpt_weekly_count}")
    print(f"a016_cpt_no_cpt_rows={cpt_no_cpt_rows}")
    print(f"a016_cpt_no_value_recheck_hours={cpt_no_value_recheck_hours:.2f}")
    print(f"a016_cpt_reused_or_skipped={cpt_reused_or_skipped_count}")
    print(f"a016_cpt_call_spacing_seconds={cpt_call_spacing_seconds:.2f}")
    print(f"a016_missing_compliance_rows={coverage_missing}")
    if args.dry_run:
        print(f"a016_dry_run_plans={dry_run_plans}")
    if last_result is not None:
        print(f"a016_sku={last_result.sku}")
        print(f"a016_date={last_result.date_utc}")
        print(f"a016_cpt_status={last_result.cpt_status}")
        print(f"a016_compliance_ceiling={last_result.compliance_ceiling_landed_gbp}")
        print(f"a016_eligibility_source={last_result.eligibility_source}")
        print(f"a016_eligibility_ceiling={last_result.eligibility_ceiling_landed_gbp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
