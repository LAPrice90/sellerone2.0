from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_POLICY_PATH = ROOT / "config" / "h_floor_vat_policy.json"

DEFAULT_POLICY = {
    "vat_registered": True,
    "recover_input_vat_on_cogs": True,
    "recover_input_vat_on_fees": True,
    "formula_version": "vat_registered_exvat_basis_v1",
    "note": "Remove output VAT from sale first; run floor on ex-VAT costs and re-gross at the end.",
}


def _to_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        out = float(str(value or "").strip())
        if out < 0:
            return 0.0
        return out
    except Exception:
        return default


def load_h_floor_vat_policy(path: Path | None = None) -> dict[str, object]:
    cfg_path = path or DEFAULT_POLICY_PATH
    merged: dict[str, object] = dict(DEFAULT_POLICY)
    if not cfg_path.exists():
        return merged
    try:
        payload = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return merged
    if not isinstance(payload, dict):
        return merged
    for key in DEFAULT_POLICY.keys():
        if key in payload:
            merged[key] = payload[key]
    merged["vat_registered"] = _to_bool(merged.get("vat_registered", True), True)
    merged["recover_input_vat_on_cogs"] = _to_bool(merged.get("recover_input_vat_on_cogs", True), True)
    merged["recover_input_vat_on_fees"] = _to_bool(merged.get("recover_input_vat_on_fees", True), True)
    merged["formula_version"] = str(merged.get("formula_version", DEFAULT_POLICY["formula_version"]) or "").strip()
    merged["note"] = str(merged.get("note", DEFAULT_POLICY["note"]) or "").strip()
    return merged


def gross_from_exvat(amount_exvat: float, vat_rate: float, policy: Mapping[str, object]) -> float:
    amount = _to_float(amount_exvat, 0.0)
    rate = _to_float(vat_rate, 0.0)
    if not _to_bool(policy.get("vat_registered", True), True):
        return amount
    return amount * (1.0 + rate)


def cogs_cost_from_exvat(cogs_exvat: float, vat_rate: float, policy: Mapping[str, object]) -> float:
    cogs = _to_float(cogs_exvat, 0.0)
    rate = _to_float(vat_rate, 0.0)
    if _to_bool(policy.get("recover_input_vat_on_cogs", True), True):
        return cogs
    return cogs * (1.0 + rate)


def fee_cost_from_exvat(fee_exvat: float, vat_rate: float, policy: Mapping[str, object]) -> float:
    fee = _to_float(fee_exvat, 0.0)
    rate = _to_float(vat_rate, 0.0)
    if _to_bool(policy.get("recover_input_vat_on_fees", True), True):
        return fee
    return fee * (1.0 + rate)
