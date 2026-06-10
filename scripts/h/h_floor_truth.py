from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import pandas as pd

from scripts.h.h_floor_policy import gross_from_exvat, load_h_floor_vat_policy
from scripts.core.out_paths import resolve_compat_path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
PRODUCT_DB_PATH = OUT / "product_db_preview.csv"
TOKEN_LEDGER_COMPAT = resolve_compat_path("token_ledger_live.csv", default_system="B")
TOKEN_LEDGER_PATH = TOKEN_LEDGER_COMPAT.live_path if TOKEN_LEDGER_COMPAT.live_path.exists() else TOKEN_LEDGER_COMPAT.legacy_path
TOKEN_COGS_LEDGER_PATH = OUT / "token_cogs_ledger.csv"
TRACE_PATH = OUT / "h_floor_truth_trace.csv"
MIN_REFERRAL_FEE_GBP = 0.25
DEFAULT_VAT_RATE = 0.2

REASON_REFERRAL_BAND_MISSING_10 = "REFERRAL_BAND_MISSING_10"
REASON_REFERRAL_BAND_MISSING_100 = "REFERRAL_BAND_MISSING_100"
REASON_FBA_BAND_MISSING_10 = "FBA_BAND_MISSING_10"
REASON_FBA_BAND_MISSING_100 = "FBA_BAND_MISSING_100"
REASON_COGS_TOKEN_MISSING = "COGS_TOKEN_MISSING"
REASON_VAT_RATE_MISSING_FALLBACK_USED = "VAT_RATE_MISSING_FALLBACK_USED"
REASON_CANDIDATE_PRICE_MISSING = "CANDIDATE_PRICE_MISSING"

BLOCKING_REASON_CODES = {
    REASON_REFERRAL_BAND_MISSING_10,
    REASON_REFERRAL_BAND_MISSING_100,
    REASON_FBA_BAND_MISSING_10,
    REASON_FBA_BAND_MISSING_100,
    REASON_COGS_TOKEN_MISSING,
    REASON_CANDIDATE_PRICE_MISSING,
}


@dataclass(frozen=True)
class HTokenCogsSource:
    cost_exvat_gbp: float
    source_cogs: str
    token_id: str = ""
    token_source: str = ""
    source_batch_id: str = ""
    source_order_key: str = ""
    notes: str = ""
    proof_state: str = "unknown"


def _norm(value: object) -> str:
    return str(value or "").strip()


def _to_float(value: object) -> float | None:
    try:
        raw = _norm(value)
        if not raw:
            return None
        out = float(raw)
        if not math.isfinite(out):
            return None
        return out
    except Exception:
        return None


def _round_half_up(value: float, ndigits: int = 2) -> float:
    q = 10 ** ndigits
    if value >= 0:
        return math.floor(value * q + 0.5) / q
    return math.ceil(value * q - 0.5) / q


def _uniq_codes(codes: list[str]) -> list[str]:
    out: list[str] = []
    seen = set()
    for code in codes:
        key = _norm(code)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _notes_value(notes: object, key: str) -> str:
    wanted = _norm(key).lower()
    for part in _norm(notes).split(";"):
        if "=" not in part:
            continue
        raw_key, raw_value = part.split("=", 1)
        if _norm(raw_key).lower() == wanted:
            return _norm(raw_value)
    return ""


def _is_fallback_token_row(row: Mapping[str, object]) -> bool:
    token_id = _norm(row.get("token_id", "")).upper()
    source = _norm(row.get("source", "")).lower()
    notes = _norm(row.get("notes", "")).lower()
    return (
        token_id.startswith("ADJ-")
        or source == "stock_adjustment_fallback"
        or "adjustment_fallback_create:" in notes
    )


def _token_cost_proof_state(row: Mapping[str, object], source_cogs: str) -> str:
    if source_cogs == "token_cogs_ledger_median":
        return "unproved"
    if not row:
        return "unknown"
    if not _is_fallback_token_row(row):
        return "clean"
    cost_source = _notes_value(row.get("notes", ""), "cost_source").lower()
    if cost_source == "receipt_proved":
        return "receipt_proved"
    if cost_source == "source_token_proved":
        return "source_token_proved"
    if cost_source:
        return "weak_fallback"
    return "unproved"


@dataclass
class HFloorInputs:
    sku: str
    candidate_price_gbp: float
    vat_rate: float
    cogs_exvat_gbp: float
    fba_exvat_gbp: float
    referral_pct: float
    referral_amount_gbp: float
    digital_fee_exvat_gbp: float
    margin_exvat_gbp: float
    source_cogs: str
    source_fba: str
    source_referral: str
    reason_codes: list[str] = field(default_factory=list)
    band_bucket: str = ""
    referral_min_fee_applied: bool = False
    cogs_source_token_id: str = ""
    cogs_token_source: str = ""
    cogs_source_batch_id: str = ""
    cogs_source_order_key: str = ""
    cogs_source_notes: str = ""
    cogs_source_proof_state: str = "unknown"


@dataclass
class HFloorResult:
    floor_total_gbp: float
    sale_exvat_gbp: float
    break_even_exvat_gbp: float
    break_even_total_gbp: float
    profit_exvat_at_floor: float
    reason_codes: list[str] = field(default_factory=list)


@dataclass
class HFloorContext:
    product_db_rows: dict[str, dict[str, str]]
    token_cogs_by_sku: dict[str, HTokenCogsSource]
    vat_policy: dict[str, object]


def load_h_floor_context(
    *,
    product_db_path: Path = PRODUCT_DB_PATH,
    token_ledger_path: Path = TOKEN_LEDGER_PATH,
    token_cogs_path: Path = TOKEN_COGS_LEDGER_PATH,
) -> HFloorContext:
    product_db_rows: dict[str, dict[str, str]] = {}
    if product_db_path.exists():
        try:
            df = pd.read_csv(product_db_path, dtype=str).fillna("")
            for _, row in df.iterrows():
                sku = _norm(row.get("seller_sku", "")).upper() or _norm(row.get("sku", "")).upper()
                if not sku or sku in product_db_rows:
                    continue
                product_db_rows[sku] = {str(k): _norm(v) for k, v in row.to_dict().items()}
        except Exception:
            product_db_rows = {}

    token_cogs_by_sku: dict[str, HTokenCogsSource] = {}

    if token_ledger_path.exists():
        try:
            tdf = pd.read_csv(token_ledger_path, dtype=str).fillna("")
            tdf["sku_u"] = tdf.get("seller_sku", "").astype(str).str.strip().str.upper()
            tdf["cost_num"] = pd.to_numeric(tdf.get("cost_per_unit", ""), errors="coerce")
            tdf["status_key"] = tdf.get("status", "").astype(str).str.strip().str.lower()
            tdf = tdf.loc[(tdf["sku_u"] != "") & tdf["cost_num"].notna() & tdf["cost_num"].gt(0.0)].copy()
            if not tdf.empty:
                available = tdf.loc[tdf["status_key"].eq("available")].copy()
                base = available if not available.empty else tdf
                if "sort_rank" in base.columns:
                    base["sort_rank_num"] = pd.to_numeric(base.get("sort_rank", ""), errors="coerce")
                elif "lot_rank_num" in base.columns:
                    base["sort_rank_num"] = pd.to_numeric(base.get("lot_rank_num", ""), errors="coerce")
                else:
                    base["sort_rank_num"] = pd.Series([float("nan")] * len(base), index=base.index)
                if "received_date" in base.columns:
                    base["received_dt"] = pd.to_datetime(
                        base.get("received_date", ""),
                        errors="coerce",
                        utc=True,
                    )
                else:
                    base["received_dt"] = pd.NaT
                base["sort_rank_num"] = base["sort_rank_num"].fillna(10**12)
                base["received_dt"] = base["received_dt"].fillna(pd.Timestamp("2262-04-11T00:00:00Z"))
                base = base.sort_values(["sku_u", "sort_rank_num", "received_dt"], kind="stable")
                first_rows = base.groupby("sku_u", as_index=False).head(1).copy()
                source = "token_ledger_live_next_available" if not available.empty else "token_ledger_live_first_cost"
                for _, row in first_rows.iterrows():
                    row_dict = {str(k): _norm(v) for k, v in row.to_dict().items()}
                    token_cogs_by_sku[str(row["sku_u"]).strip().upper()] = HTokenCogsSource(
                        cost_exvat_gbp=float(row["cost_num"]),
                        source_cogs=source,
                        token_id=row_dict.get("token_id", ""),
                        token_source=row_dict.get("source", ""),
                        source_batch_id=row_dict.get("source_batch_id", ""),
                        source_order_key=row_dict.get("source_order_key", ""),
                        notes=row_dict.get("notes", ""),
                        proof_state=_token_cost_proof_state(row_dict, source),
                    )
        except Exception:
            token_cogs_by_sku = {}

    if token_cogs_path.exists():
        try:
            tdf = pd.read_csv(token_cogs_path, dtype=str).fillna("")
            tdf["sku_u"] = tdf.get("seller_sku", "").astype(str).str.strip().str.upper()
            tdf["cogs_exvat_num"] = pd.to_numeric(tdf.get("cogs_exvat", ""), errors="coerce")
            tdf = tdf.loc[(tdf["sku_u"] != "") & tdf["cogs_exvat_num"].notna() & tdf["cogs_exvat_num"].gt(0.0)].copy()
            if not tdf.empty:
                med = tdf.groupby("sku_u")["cogs_exvat_num"].median().to_dict()
                for sku, value in med.items():
                    sku_key = str(sku).strip().upper()
                    if sku_key in token_cogs_by_sku:
                        continue
                    token_cogs_by_sku[sku_key] = HTokenCogsSource(
                        cost_exvat_gbp=float(value),
                        source_cogs="token_cogs_ledger_median",
                        proof_state="unproved",
                    )
        except Exception:
            pass

    return HFloorContext(
        product_db_rows=product_db_rows,
        token_cogs_by_sku=token_cogs_by_sku,
        vat_policy=load_h_floor_vat_policy(),
    )


def _resolve_vat_rate(row: Mapping[str, str], reason_codes: list[str]) -> float:
    vat_raw = _to_float(row.get("last_vat_rate_pct", ""))
    if vat_raw is None:
        vat_raw = _to_float(row.get("vat_rate", ""))
    if vat_raw is None:
        reason_codes.append(REASON_VAT_RATE_MISSING_FALLBACK_USED)
        return DEFAULT_VAT_RATE
    if vat_raw > 1:
        vat_raw = vat_raw / 100.0
    if vat_raw < 0:
        return DEFAULT_VAT_RATE
    return float(vat_raw)


def _resolve_fba_exvat(row: Mapping[str, str], band_bucket: str, reason_codes: list[str]) -> tuple[float, str]:
    if band_bucket == "10":
        band_value = _to_float(row.get("last_fba_fee_ex_vat_10", ""))
        if band_value is not None and band_value > 0:
            return float(band_value), "L3_BAND_10"
        generic_value = _to_float(row.get("last_fba_fee_ex_vat", ""))
        if generic_value is not None and generic_value > 0:
            return float(generic_value), "L3_GENERIC"
        api_value = _to_float(row.get("fba_fee_10", ""))
        if api_value is not None and api_value > 0:
            return float(api_value), "API_BAND_10"
        reason_codes.append(REASON_FBA_BAND_MISSING_10)
        return 0.0, "MISSING"

    band_value = _to_float(row.get("last_fba_fee_ex_vat_100", ""))
    if band_value is not None and band_value > 0:
        return float(band_value), "L3_BAND_100"
    generic_value = _to_float(row.get("last_fba_fee_ex_vat", ""))
    if generic_value is not None and generic_value > 0:
        return float(generic_value), "L3_GENERIC"
    api_value = _to_float(row.get("fba_fee_100", ""))
    if api_value is not None and api_value > 0:
        return float(api_value), "API_BAND_100"
    reason_codes.append(REASON_FBA_BAND_MISSING_100)
    return 0.0, "MISSING"


def _resolve_referral_pct(row: Mapping[str, str], band_bucket: str, reason_codes: list[str]) -> tuple[float, str]:
    if band_bucket == "10":
        band_value = _to_float(row.get("last_commission_pct_10", ""))
        if band_value is not None and band_value > 0:
            rate = band_value / 100.0 if band_value > 1 else band_value
            return float(rate), "L3_BAND_10"
        api_value = _to_float(row.get("referral_fee_10", ""))
        if api_value is not None and api_value > 0:
            rate = api_value / 100.0 if api_value > 1 else api_value
            return float(rate), "API_BAND_10"
        reason_codes.append(REASON_REFERRAL_BAND_MISSING_10)
        return 0.0, "MISSING"

    band_value = _to_float(row.get("last_commission_pct_100", ""))
    if band_value is not None and band_value > 0:
        rate = band_value / 100.0 if band_value > 1 else band_value
        return float(rate), "L3_BAND_100"
    api_value = _to_float(row.get("referral_fee_100", ""))
    if api_value is not None and api_value > 0:
        rate = api_value / 100.0 if api_value > 1 else api_value
        return float(rate), "API_BAND_100"
    reason_codes.append(REASON_REFERRAL_BAND_MISSING_100)
    return 0.0, "MISSING"


def has_blocking_reason_codes(reason_codes: list[str]) -> bool:
    return any(code in BLOCKING_REASON_CODES for code in reason_codes)


def resolve_h_floor_inputs(
    sku: str,
    candidate_price_gbp: float,
    *,
    context: HFloorContext | None = None,
    forced_band_bucket: str | None = None,
    allow_candidate_fallback: bool = True,
) -> HFloorInputs:
    ctx = context or load_h_floor_context()
    sku_key = _norm(sku).upper()
    row = ctx.product_db_rows.get(sku_key, {})
    reason_codes: list[str] = []
    candidate = max(float(candidate_price_gbp or 0.0), 0.0)
    if candidate <= 0:
        fallback = None
        if allow_candidate_fallback:
            fallback = _to_float(row.get("live_listing_price", "")) or _to_float(row.get("last_sold_price", ""))
        if fallback is None or fallback <= 0:
            reason_codes.append(REASON_CANDIDATE_PRICE_MISSING)
            candidate = 0.0
        else:
            candidate = max(float(fallback), 0.01)
    if forced_band_bucket in {"10", "100"}:
        band_bucket = forced_band_bucket
    else:
        band_bucket = "10" if candidate <= 10.0 else "100"

    vat_rate = _resolve_vat_rate(row, reason_codes)
    cogs_info = ctx.token_cogs_by_sku.get(sku_key)
    if cogs_info is None:
        cogs_ex = 0.0
        source_cogs = "MISSING"
        cogs_source_token_id = ""
        cogs_token_source = ""
        cogs_source_batch_id = ""
        cogs_source_order_key = ""
        cogs_source_notes = ""
        cogs_source_proof_state = "unknown"
        reason_codes.append(REASON_COGS_TOKEN_MISSING)
    else:
        cogs_ex = float(cogs_info.cost_exvat_gbp)
        source_cogs = str(cogs_info.source_cogs)
        cogs_source_token_id = cogs_info.token_id
        cogs_token_source = cogs_info.token_source
        cogs_source_batch_id = cogs_info.source_batch_id
        cogs_source_order_key = cogs_info.source_order_key
        cogs_source_notes = cogs_info.notes
        cogs_source_proof_state = cogs_info.proof_state

    fba_ex, source_fba = _resolve_fba_exvat(row, band_bucket, reason_codes)
    referral_pct, source_referral = _resolve_referral_pct(row, band_bucket, reason_codes)

    referral_raw = candidate * referral_pct
    referral_min_applied = False
    if referral_pct > 0.0 and referral_raw < MIN_REFERRAL_FEE_GBP:
        referral_raw = MIN_REFERRAL_FEE_GBP
        referral_min_applied = True
    referral_amount = _round_half_up(referral_raw, 2)

    dsf_fba = _round_half_up(abs(fba_ex) * 0.02, 2)
    dsf_ref = _round_half_up(abs(referral_amount) * 0.02, 2)
    digital_fee_ex = _round_half_up(dsf_fba + dsf_ref, 2)
    margin_ex = _round_half_up(cogs_ex * 0.10, 3)

    return HFloorInputs(
        sku=sku_key,
        candidate_price_gbp=float(candidate),
        vat_rate=float(vat_rate),
        cogs_exvat_gbp=float(cogs_ex),
        fba_exvat_gbp=float(fba_ex),
        referral_pct=float(referral_pct),
        referral_amount_gbp=float(referral_amount),
        digital_fee_exvat_gbp=float(digital_fee_ex),
        margin_exvat_gbp=float(margin_ex),
        source_cogs=source_cogs,
        source_fba=source_fba,
        source_referral=source_referral,
        reason_codes=_uniq_codes(reason_codes),
        band_bucket=band_bucket,
        referral_min_fee_applied=referral_min_applied,
        cogs_source_token_id=cogs_source_token_id,
        cogs_token_source=cogs_token_source,
        cogs_source_batch_id=cogs_source_batch_id,
        cogs_source_order_key=cogs_source_order_key,
        cogs_source_notes=cogs_source_notes,
        cogs_source_proof_state=cogs_source_proof_state,
    )


def compute_h_floor(inputs: HFloorInputs, *, context: HFloorContext | None = None) -> HFloorResult:
    policy = (context.vat_policy if context is not None else load_h_floor_vat_policy())
    sale_ex = (
        float(inputs.cogs_exvat_gbp)
        + float(inputs.fba_exvat_gbp)
        + float(inputs.referral_amount_gbp)
        + float(inputs.digital_fee_exvat_gbp)
        + float(inputs.margin_exvat_gbp)
    )
    be_ex = (
        float(inputs.cogs_exvat_gbp)
        + float(inputs.fba_exvat_gbp)
        + float(inputs.referral_amount_gbp)
        + float(inputs.digital_fee_exvat_gbp)
    )
    floor_total = _round_half_up(gross_from_exvat(sale_ex, inputs.vat_rate, policy), 2)
    be_total = _round_half_up(gross_from_exvat(be_ex, inputs.vat_rate, policy), 2)
    profit_ex = _round_half_up(sale_ex - (be_ex + float(inputs.margin_exvat_gbp)), 6)
    return HFloorResult(
        floor_total_gbp=float(floor_total),
        sale_exvat_gbp=float(_round_half_up(sale_ex, 3)),
        break_even_exvat_gbp=float(_round_half_up(be_ex, 3)),
        break_even_total_gbp=float(be_total),
        profit_exvat_at_floor=float(profit_ex),
        reason_codes=list(inputs.reason_codes),
    )


def compute_h_floor_for_sku(
    sku: str,
    candidate_price_gbp: float,
    *,
    context: HFloorContext | None = None,
    max_iter: int = 12,
) -> tuple[HFloorInputs, HFloorResult]:
    ctx = context or load_h_floor_context()
    seed = max(float(candidate_price_gbp or 0.0), 0.0)

    def _solve_one_band(band_bucket: str) -> tuple[HFloorInputs, HFloorResult]:
        candidate = seed
        last_inputs = resolve_h_floor_inputs(
            sku,
            candidate,
            context=ctx,
            forced_band_bucket=band_bucket,
            allow_candidate_fallback=False,
        )
        last_result = compute_h_floor(last_inputs, context=ctx)
        reason_codes: list[str] = list(last_inputs.reason_codes) + list(last_result.reason_codes)
        for _ in range(max(int(max_iter), 1)):
            inputs = resolve_h_floor_inputs(
                sku,
                candidate,
                context=ctx,
                forced_band_bucket=band_bucket,
                allow_candidate_fallback=False,
            )
            result = compute_h_floor(inputs, context=ctx)
            reason_codes.extend(inputs.reason_codes)
            reason_codes.extend(result.reason_codes)
            last_inputs = inputs
            last_result = result
            if has_blocking_reason_codes(inputs.reason_codes):
                break
            required = float(result.floor_total_gbp)
            if abs(required - candidate) < 0.01:
                break
            candidate = required
        merged_codes = _uniq_codes(reason_codes)
        last_inputs.reason_codes = list(merged_codes)
        last_result.reason_codes = list(merged_codes)
        return last_inputs, last_result

    inputs_10, result_10 = _solve_one_band("10")
    inputs_100, result_100 = _solve_one_band("100")

    valid_10 = (not has_blocking_reason_codes(inputs_10.reason_codes)) and result_10.floor_total_gbp > 0
    valid_100 = (not has_blocking_reason_codes(inputs_100.reason_codes)) and result_100.floor_total_gbp > 0

    chosen_inputs = inputs_100
    chosen_result = result_100
    if valid_10 and valid_100:
        # Keep 10-band only when its own solved floor stays in <=10 range.
        ten_allowed = result_10.floor_total_gbp <= 10.0 + 1e-9
        if ten_allowed and (result_10.floor_total_gbp <= result_100.floor_total_gbp):
            chosen_inputs = inputs_10
            chosen_result = result_10
        else:
            chosen_inputs = inputs_100
            chosen_result = result_100
    elif valid_10:
        chosen_inputs = inputs_10
        chosen_result = result_10
    elif valid_100:
        chosen_inputs = inputs_100
        chosen_result = result_100
    else:
        # Both invalid: keep 100-band as default hold path, but include all reasons.
        merged = _uniq_codes(inputs_10.reason_codes + result_10.reason_codes + inputs_100.reason_codes + result_100.reason_codes)
        chosen_inputs.reason_codes = list(merged)
        chosen_result.reason_codes = list(merged)
        return chosen_inputs, chosen_result

    merged_reason_codes = _uniq_codes(chosen_inputs.reason_codes + chosen_result.reason_codes)
    chosen_inputs.reason_codes = list(merged_reason_codes)
    chosen_result.reason_codes = list(merged_reason_codes)
    return chosen_inputs, chosen_result


def build_h_floor_trace_row(
    *,
    inputs: HFloorInputs,
    result: HFloorResult,
    source_script: str,
    asof_utc: str | None = None,
) -> dict[str, str]:
    ts = _norm(asof_utc) or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "asof_utc": ts,
        "source_script": _norm(source_script),
        "sku": _norm(inputs.sku),
        "candidate_price_gbp": f"{_round_half_up(inputs.candidate_price_gbp, 2):.2f}",
        "floor_total_gbp": f"{_round_half_up(result.floor_total_gbp, 2):.2f}",
        "sale_exvat_gbp": f"{_round_half_up(result.sale_exvat_gbp, 3):.3f}",
        "break_even_exvat_gbp": f"{_round_half_up(result.break_even_exvat_gbp, 3):.3f}",
        "break_even_total_gbp": f"{_round_half_up(result.break_even_total_gbp, 2):.2f}",
        "profit_exvat_at_floor": f"{_round_half_up(result.profit_exvat_at_floor, 6):.6f}",
        "vat_rate": f"{inputs.vat_rate:.6f}",
        "cogs_exvat_gbp": f"{_round_half_up(inputs.cogs_exvat_gbp, 3):.3f}",
        "fba_exvat_gbp": f"{_round_half_up(inputs.fba_exvat_gbp, 3):.3f}",
        "referral_pct": f"{_round_half_up(inputs.referral_pct, 6):.6f}",
        "referral_amount_gbp": f"{_round_half_up(inputs.referral_amount_gbp, 3):.3f}",
        "digital_fee_exvat_gbp": f"{_round_half_up(inputs.digital_fee_exvat_gbp, 3):.3f}",
        "margin_exvat_gbp": f"{_round_half_up(inputs.margin_exvat_gbp, 3):.3f}",
        "source_cogs": _norm(inputs.source_cogs),
        "cogs_source_token_id": _norm(inputs.cogs_source_token_id),
        "cogs_token_source": _norm(inputs.cogs_token_source),
        "cogs_source_batch_id": _norm(inputs.cogs_source_batch_id),
        "cogs_source_order_key": _norm(inputs.cogs_source_order_key),
        "cogs_source_notes": _norm(inputs.cogs_source_notes),
        "cogs_source_proof_state": _norm(inputs.cogs_source_proof_state),
        "source_fba": _norm(inputs.source_fba),
        "source_referral": _norm(inputs.source_referral),
        "band_bucket": _norm(inputs.band_bucket),
        "referral_min_fee_applied": "1" if inputs.referral_min_fee_applied else "0",
        "reason_codes_csv": ",".join(_uniq_codes(result.reason_codes)),
        "used_order_data_flag": "0",
    }


def append_h_floor_trace_rows(rows: list[dict[str, str]], *, path: Path = TRACE_PATH) -> None:
    if not rows:
        return
    headers = [
        "asof_utc",
        "source_script",
        "sku",
        "candidate_price_gbp",
        "floor_total_gbp",
        "sale_exvat_gbp",
        "break_even_exvat_gbp",
        "break_even_total_gbp",
        "profit_exvat_at_floor",
        "vat_rate",
        "cogs_exvat_gbp",
        "fba_exvat_gbp",
        "referral_pct",
        "referral_amount_gbp",
        "digital_fee_exvat_gbp",
        "margin_exvat_gbp",
        "source_cogs",
        "cogs_source_token_id",
        "cogs_token_source",
        "cogs_source_batch_id",
        "cogs_source_order_key",
        "cogs_source_notes",
        "cogs_source_proof_state",
        "source_fba",
        "source_referral",
        "band_bucket",
        "referral_min_fee_applied",
        "reason_codes_csv",
        "used_order_data_flag",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    if exists:
        try:
            with path.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                existing_headers = list(reader.fieldnames or [])
                existing_rows = list(reader)
            merged_headers = existing_headers + [header for header in headers if header not in existing_headers]
            if merged_headers != existing_headers:
                with path.open("w", encoding="utf-8", newline="") as fh:
                    writer = csv.DictWriter(fh, fieldnames=merged_headers)
                    writer.writeheader()
                    for existing_row in existing_rows:
                        writer.writerow({k: _norm(existing_row.get(k, "")) for k in merged_headers})
            headers = merged_headers
        except OSError:
            pass
    with path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({k: _norm(row.get(k, "")) for k in headers})

