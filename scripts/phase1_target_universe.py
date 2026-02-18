from __future__ import annotations

from pathlib import Path
from typing import Mapping

import pandas as pd

try:
    from scripts.h_lab_cohort import load_active_lab_skus
except ModuleNotFoundError:
    from h_lab_cohort import load_active_lab_skus

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
DEFAULT_SCOPE_PATH = OUT / "phase1_sku_scope.csv"
DEFAULT_MERCHANT_LISTINGS_PATH = OUT / "merchant_listings_latest.csv"

ALLOWED_TARGET_UNIVERSE_MODES = {
    "active_merchant",
    "scope_non_parked",
    "lab_cohort",
    "single_sku",
}
TRUTHY = {"1", "true", "yes", "y", "on"}


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


def _to_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = _norm(value).lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _cfg_get(cfg: Mapping[str, object], *keys: str, default: object = "") -> object:
    cur: object = cfg
    for key in keys:
        if not isinstance(cur, Mapping):
            return default
        if key not in cur:
            return default
        cur = cur[key]
    return cur


def _cfg_sku_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip().upper() for v in value if str(v).strip()]
    text = _norm(value)
    if not text:
        return []
    if "," in text:
        return [part.strip().upper() for part in text.split(",") if part.strip()]
    return [text.upper()]


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for value in values:
        key = _norm(value).upper()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _latest_listing_snapshot_path(out_dir: Path = OUT) -> Path | None:
    files = sorted(out_dir.glob("listing_offer_snapshot_*.csv"))
    if not files:
        return None
    return files[-1]


def _is_in_stock_listing_row(row: Mapping[str, str]) -> bool:
    if _norm(row.get("we_present_flag", "")).lower() in TRUTHY:
        return True
    our_price = _to_float(row.get("our_price", ""))
    return our_price is not None and our_price > 0


def _load_listing_row_map(out_dir: Path = OUT) -> dict[str, dict[str, str]]:
    snapshot_path = _latest_listing_snapshot_path(out_dir)
    if snapshot_path is None:
        return {}
    try:
        df = pd.read_csv(snapshot_path, dtype=str).fillna("")
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


def _load_active_merchant_skus(merchant_listings_path: Path = DEFAULT_MERCHANT_LISTINGS_PATH) -> list[str]:
    if not merchant_listings_path.exists():
        return []
    try:
        df = pd.read_csv(merchant_listings_path, dtype=str).fillna("")
    except Exception:
        return []
    if "status" not in df.columns:
        return []
    status = df["status"].astype(str).str.strip().str.lower()
    sku_col_name = "seller-sku" if "seller-sku" in df.columns else ("seller_sku" if "seller_sku" in df.columns else "")
    if not sku_col_name:
        return []
    sku_col = df[sku_col_name].astype(str).str.strip().str.upper()
    return _dedupe_keep_order([s for s in sku_col.loc[status.eq("active")].tolist() if s])


def _load_scope_non_parked_skus(scope_path: Path = DEFAULT_SCOPE_PATH) -> tuple[list[str], int]:
    if not scope_path.exists():
        return [], 0
    try:
        scope = pd.read_csv(scope_path, dtype=str).fillna("")
    except Exception:
        return [], 0
    if "sku" not in scope.columns or "parked_flag" not in scope.columns:
        return [], 0
    sku_col = scope["sku"].astype(str).str.strip().str.upper()
    parked = scope["parked_flag"].astype(str).str.strip()
    non_parked = [s for s in sku_col.loc[~parked.eq("1")].tolist() if s]
    parked_count = int(parked.eq("1").sum())
    return _dedupe_keep_order(non_parked), parked_count


def _resolve_mode(cfg: Mapping[str, object]) -> tuple[str, str]:
    explicit_mode = _norm(_cfg_get(cfg, "target_universe_mode", default="")).lower()
    if explicit_mode in ALLOWED_TARGET_UNIVERSE_MODES:
        return explicit_mode, "target_universe_mode"
    legacy_use_active_merchant = _to_bool(_cfg_get(cfg, "use_active_merchant_skus", default=True), default=True)
    if legacy_use_active_merchant:
        return "active_merchant", "legacy_use_active_merchant_skus"
    return "single_sku", "legacy_use_active_merchant_skus"


def _resolve_single_sku_targets(cfg: Mapping[str, object]) -> list[str]:
    explicit = _cfg_sku_list(
        _cfg_get(cfg, "pilot_whitelist_skus", default=_cfg_get(cfg, "pilot_whitelist_sku", default=""))
    )
    explicit = [s for s in explicit if s]
    fallback = _norm(_cfg_get(cfg, "sku", default="")).upper()
    if explicit:
        return _dedupe_keep_order(explicit)
    if fallback:
        return [fallback]
    return []


def resolve_target_universe(
    cfg: Mapping[str, object],
    *,
    out_dir: Path = OUT,
    scope_path: Path = DEFAULT_SCOPE_PATH,
    cohort_path: Path | None = None,
) -> dict[str, object]:
    mode, mode_source = _resolve_mode(cfg)
    notes: list[str] = []

    skus: list[str] = []
    source = ""
    candidate_count = 0
    skipped_no_listing_count = 0
    skipped_out_of_stock_count = 0
    skipped_parked_count = 0

    if mode == "single_sku":
        skus = _resolve_single_sku_targets(cfg)
        source = "config_single_sku"
        candidate_count = len(skus)
    elif mode == "lab_cohort":
        skus = _dedupe_keep_order(load_active_lab_skus(path=cohort_path))
        source = "h_lab_cohort_enabled"
        candidate_count = len(skus)
    elif mode == "scope_non_parked":
        skus, skipped_parked_count = _load_scope_non_parked_skus(scope_path=scope_path)
        source = "phase1_sku_scope_non_parked"
        candidate_count = len(skus) + int(skipped_parked_count)
        if not skus:
            notes.append("scope_non_parked_empty_or_missing")
    else:
        candidate_skus = _load_active_merchant_skus(merchant_listings_path=out_dir / "merchant_listings_latest.csv")
        listing_rows = _load_listing_row_map(out_dir=out_dir)
        source = "merchant_active_with_listing_in_stock"
        candidate_count = len(candidate_skus)
        for sku in candidate_skus:
            row = listing_rows.get(sku)
            if row is None:
                skipped_no_listing_count += 1
                continue
            if not _is_in_stock_listing_row(row):
                skipped_out_of_stock_count += 1
                continue
            skus.append(sku)
        if not candidate_skus:
            notes.append("merchant_active_empty_or_missing")

    return {
        "mode": mode,
        "mode_source": mode_source,
        "source": source,
        "skus": _dedupe_keep_order(skus),
        "resolved_count": len(_dedupe_keep_order(skus)),
        "candidate_count": int(candidate_count),
        "skipped_no_listing_count": int(skipped_no_listing_count),
        "skipped_out_of_stock_count": int(skipped_out_of_stock_count),
        "skipped_parked_count": int(skipped_parked_count),
        "notes_csv": ",".join(notes),
    }
