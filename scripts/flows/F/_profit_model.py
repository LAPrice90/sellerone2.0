from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class FeeBasedProfitResult:
    profit_per_unit_gbp: float | None
    sale_price_ex_vat_gbp: float | None
    referral_fee_used_gbp: float | None
    digital_fee_used_gbp: float | None
    referral_rate: float | None
    formula_variant: str
    missing_inputs: tuple[str, ...]


def _is_finite_number(value: object) -> bool:
    if value is None:
        return False
    try:
        num = float(value)
    except (TypeError, ValueError):
        return False
    return not math.isnan(num) and not math.isinf(num)


def _as_float_or_none(value: object) -> float | None:
    if not _is_finite_number(value):
        return None
    return float(value)


def derive_referral_rate(*, referral_fee_gbp: object, referral_fee_basis_price_gbp: object) -> float | None:
    referral = _as_float_or_none(referral_fee_gbp)
    basis_price = _as_float_or_none(referral_fee_basis_price_gbp)
    if referral is None or basis_price is None or basis_price <= 0:
        return None
    if referral < 0:
        return None
    return max(referral / basis_price, 0.0)


def calculate_fee_based_profit_per_unit(
    *,
    sale_price_gbp: object,
    vat_rate_pct: object,
    product_cost_gbp: object,
    fba_fee_gbp: object,
    referral_fee_gbp: object,
    digital_fee_gbp: object,
    est_shipping_gbp: object,
    referral_fee_basis_price_gbp: object | None = None,
    recalculate_referral_fee: bool = True,
    recalculate_digital_fee: bool = True,
) -> FeeBasedProfitResult:
    sale_price = _as_float_or_none(sale_price_gbp)
    vat_rate = _as_float_or_none(vat_rate_pct)
    product_cost = _as_float_or_none(product_cost_gbp)
    fba_fee = _as_float_or_none(fba_fee_gbp)
    referral_fee = _as_float_or_none(referral_fee_gbp)
    digital_fee = _as_float_or_none(digital_fee_gbp)
    est_shipping = _as_float_or_none(est_shipping_gbp)

    missing_inputs: list[str] = []
    if sale_price is None or sale_price <= 0:
        missing_inputs.append("sale_price_gbp")
    if vat_rate is None or vat_rate < 0:
        missing_inputs.append("vat_rate_pct")
    if product_cost is None or product_cost < 0:
        missing_inputs.append("product_cost_gbp")
    if fba_fee is None or fba_fee < 0:
        missing_inputs.append("fba_fee_gbp")
    if referral_fee is None or referral_fee < 0:
        missing_inputs.append("referral_fee_gbp")
    if digital_fee is None or digital_fee < 0:
        missing_inputs.append("digital_fee_gbp")
    if est_shipping is None or est_shipping < 0:
        missing_inputs.append("est_shipping_gbp")

    if missing_inputs:
        return FeeBasedProfitResult(
            profit_per_unit_gbp=None,
            sale_price_ex_vat_gbp=None,
            referral_fee_used_gbp=None,
            digital_fee_used_gbp=None,
            referral_rate=None,
            formula_variant="missing_inputs",
            missing_inputs=tuple(missing_inputs),
        )

    vat_multiplier = 1.0 + (float(vat_rate) / 100.0)
    if vat_multiplier <= 0:
        return FeeBasedProfitResult(
            profit_per_unit_gbp=None,
            sale_price_ex_vat_gbp=None,
            referral_fee_used_gbp=None,
            digital_fee_used_gbp=None,
            referral_rate=None,
            formula_variant="missing_inputs",
            missing_inputs=("vat_rate_pct",),
        )

    sale_price_ex_vat = float(sale_price) / vat_multiplier
    referral_fee_used = float(referral_fee)
    digital_fee_used = float(digital_fee)
    referral_rate = None
    formula_variant = "fee_based_stored_fees"

    if recalculate_referral_fee:
        referral_rate = derive_referral_rate(
            referral_fee_gbp=referral_fee,
            referral_fee_basis_price_gbp=referral_fee_basis_price_gbp,
        )
        if referral_rate is not None:
            referral_fee_used = float(sale_price) * referral_rate
            formula_variant = "fee_based_referral_recalculated"

    if recalculate_digital_fee:
        baseline_total = float(fba_fee) + float(referral_fee)
        if baseline_total > 0:
            digital_rate = max(float(digital_fee) / baseline_total, 0.0)
            digital_fee_used = digital_rate * (float(fba_fee) + referral_fee_used)
            if formula_variant == "fee_based_referral_recalculated":
                formula_variant = "fee_based_referral_and_digital_recalculated"
            else:
                formula_variant = "fee_based_digital_recalculated"

    profit_per_unit = (
        sale_price_ex_vat
        - float(product_cost)
        - float(fba_fee)
        - referral_fee_used
        - digital_fee_used
        - float(est_shipping)
    )
    return FeeBasedProfitResult(
        profit_per_unit_gbp=profit_per_unit,
        sale_price_ex_vat_gbp=sale_price_ex_vat,
        referral_fee_used_gbp=referral_fee_used,
        digital_fee_used_gbp=digital_fee_used,
        referral_rate=referral_rate,
        formula_variant=formula_variant,
        missing_inputs=(),
    )
