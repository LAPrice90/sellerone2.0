from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BOOT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT))

from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories


WEAK_REFUND_STATES = {
    "",
    "missing",
    "unknown",
    "weak",
    "not_yet_proven",
    "sellerboard_bridge_only",
    "bridge_labelled_only",
}
WEAK_REFUND_CONFIDENCE = {"", "missing", "unknown", "weak", "not_yet_proven"}
WEAK_INBOUND_STATES = {
    "",
    "missing",
    "unknown",
    "weak",
    "not_yet_proven",
    "missing_inbound_cost_confidence",
    "unsupported_currency",
}
WEAK_PROFIT_STATES = {"", "missing_profit_inputs", "weak_profit_inputs", "unknown", "not_yet_proven"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value: object) -> str:
    return str(value or "").strip()


def _lower(value: object) -> str:
    return _text(value).lower()


def _row_map(df: pd.DataFrame, key: str) -> dict[str, pd.Series]:
    if df.empty or key not in df.columns:
        return {}
    mapped: dict[str, pd.Series] = {}
    for _, row in df.iterrows():
        value = _text(row.get(key, "")).upper()
        if value and value not in mapped:
            mapped[value] = row
    return mapped


def _lookup(row: pd.Series, by_sku: dict[str, pd.Series], by_asin: dict[str, pd.Series]) -> pd.Series | None:
    sku = _text(row.get("seller_sku", "")).upper()
    asin = _text(row.get("asin", "")).upper()
    if sku and sku in by_sku:
        return by_sku[sku]
    if asin and asin in by_asin:
        return by_asin[asin]
    return None


def _weak_flags(row: pd.Series) -> tuple[bool, bool, bool, bool]:
    weak_refund = (
        _lower(row.get("refund_proof_state", "")) in WEAK_REFUND_STATES
        or _lower(row.get("refund_sample_confidence", "")) in WEAK_REFUND_CONFIDENCE
    )
    weak_inbound = _lower(row.get("inbound_cost_confidence", "")) in WEAK_INBOUND_STATES
    weak_profit = _lower(row.get("profit_input_confidence", "")) in WEAK_PROFIT_STATES
    weak_token = _lower(row.get("token_cost_trust_state", "")) != "trusted"
    return weak_refund, weak_inbound, weak_profit, weak_token


def _primary_blocker(*, weak_refund: bool, weak_inbound: bool, weak_profit: bool, weak_token: bool) -> str:
    if weak_inbound:
        return "inbound_fba_cost_missing"
    if weak_token:
        return "token_cost_not_trusted"
    if weak_refund:
        return "refund_confidence_missing"
    if weak_profit:
        return "profit_input_confidence_missing"
    return "none"


def _next_safe_action(primary: str) -> str:
    if primary == "inbound_fba_cost_missing":
        return "build_sku_level_inbound_fba_cost_proof"
    if primary == "refund_confidence_missing":
        return "repair_refund_confidence_proof"
    if primary == "profit_input_confidence_missing":
        return "repair_profit_input_confidence_labels"
    if primary == "token_cost_not_trusted":
        return "build_token_cost_trust_gate"
    return "no_action"


def build_profit_input_blocker_breakdown(
    root: Path | str | None = None,
    *,
    proof_utc: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else Path(__file__).resolve().parents[3]
    ensure_o_directories(root=root_path)
    observed = proof_utc or _utc_now_iso()

    source_df = read_o_contract_df(root_path, "restock_source_view")
    session_df = read_o_contract_df(root_path, "restock_session_review_live")
    coverage_df = read_o_contract_df(root_path, "reorder_input_coverage_report")

    session_by_sku = _row_map(session_df, "seller_sku")
    session_by_asin = _row_map(session_df, "asin")
    coverage_by_sku = _row_map(coverage_df, "seller_sku")
    coverage_by_asin = _row_map(coverage_df, "asin")

    output_rows: list[dict[str, str]] = []
    minimum_rows = 0
    weak_refund_rows = 0
    weak_inbound_rows = 0
    weak_profit_rows = 0
    weak_token_rows = 0

    for _, row in source_df.iterrows():
        if _text(row.get("has_minimum_restock_inputs", "")) != "1":
            continue
        minimum_rows += 1
        weak_refund, weak_inbound, weak_profit, weak_token = _weak_flags(row)
        if not (weak_refund or weak_inbound or weak_profit or weak_token):
            continue
        weak_refund_rows += 1 if weak_refund else 0
        weak_inbound_rows += 1 if weak_inbound else 0
        weak_profit_rows += 1 if weak_profit else 0
        weak_token_rows += 1 if weak_token else 0
        session_row = _lookup(row, session_by_sku, session_by_asin)
        coverage_row = _lookup(row, coverage_by_sku, coverage_by_asin)
        primary = _primary_blocker(
            weak_refund=weak_refund,
            weak_inbound=weak_inbound,
            weak_profit=weak_profit,
            weak_token=weak_token,
        )
        blocker_parts = []
        if weak_refund:
            blocker_parts.append("refund")
        if weak_inbound:
            blocker_parts.append("inbound")
        if weak_profit:
            blocker_parts.append("profit")
        if weak_token:
            blocker_parts.append("token_cost")
        source_class = _text(session_row.get("source_class", "")) if session_row is not None else "native_o"
        action_safety = _text(session_row.get("action_safety_state", "")) if session_row is not None else ""
        action_ready = _text(coverage_row.get("action_ready_now", "")) if coverage_row is not None else "0"
        output_rows.append(
            {
                "proof_utc": observed,
                "seller_sku": _text(row.get("seller_sku", "")),
                "asin": _text(row.get("asin", "")),
                "supplier_name": _text(row.get("supplier_name", "")),
                "supplier_code": _text(row.get("supplier_code", "")),
                "has_minimum_restock_inputs": "1",
                "source_class": source_class,
                "action_safety_state": action_safety,
                "action_ready_now": action_ready,
                "refund_proof_state": _text(row.get("refund_proof_state", "")),
                "refund_sample_confidence": _text(row.get("refund_sample_confidence", "")),
                "inbound_cost_confidence": _text(row.get("inbound_cost_confidence", "")),
                "inbound_cost_basis": _text(row.get("inbound_cost_basis", "")),
                "expected_inbound_cost_per_unit_gbp": _text(row.get("expected_inbound_cost_per_unit_gbp", "")),
                "profit_input_confidence": _text(row.get("profit_input_confidence", "")),
                "profit_input_blockers": _text(row.get("profit_input_blockers", "")),
                "token_cost_trust_state": _text(row.get("token_cost_trust_state", "")),
                "token_cost_trust_basis": _text(row.get("token_cost_trust_basis", "")),
                "token_cost_trust_blockers": _text(row.get("token_cost_trust_blockers", "")),
                "blocker_group": "|".join(blocker_parts),
                "primary_blocker": primary,
                "next_safe_action": _next_safe_action(primary),
                "needs_luke_decision": "0",
                "safe_for_clean_buy": "0",
                "safe_for_po": "0",
                "source_path": "out/systems/O/live/restock_source_view.csv",
                "title": _text(row.get("title", "")),
                "current_supplier_buy_cost_gbp": _text(row.get("current_supplier_buy_cost_gbp", "")),
                "market_price_gbp": _text(row.get("market_price_gbp", "")),
                "expected_refund_cost_per_unit_gbp": _text(row.get("expected_refund_cost_per_unit_gbp", "")),
                "reason": "Minimum restock inputs exist, but expected profit is not clean yet.",
            }
        )

    out_df = pd.DataFrame(output_rows)
    out_df = write_o_contract_df(root_path, "restock_profit_input_blocker_breakdown_live", out_df)

    weak_rows = len(out_df.index)
    status = "ok" if weak_rows == 0 else "warn"
    health_rows = [
        {
            "proof_utc": observed,
            "check": "profit_input_blocker_rows",
            "status": status,
            "value": f"minimum_input_rows={minimum_rows};weak_rows={weak_rows}",
            "notes": "Rows with minimum restock inputs but weak expected-profit proof stay blocked from clean buy.",
            "source_path": "out/systems/O/live/restock_source_view.csv",
        },
        {
            "proof_utc": observed,
            "check": "weak_input_lanes",
            "status": status,
            "value": f"refund={weak_refund_rows};inbound={weak_inbound_rows};profit={weak_profit_rows};token_cost={weak_token_rows}",
            "notes": "Shows which proof lane is still weak for the minimum-input rows.",
            "source_path": "out/systems/O/live/restock_source_view.csv",
        },
        {
            "proof_utc": observed,
            "check": "buy_safety",
            "status": "ok",
            "value": f"safe_for_clean_buy=0;safe_for_po=0;rows={weak_rows}",
            "notes": "The blocker breakdown is read-only and does not allow clean buy or PO creation.",
            "source_path": "out/systems/O/live/restock_profit_input_blocker_breakdown_live.csv",
        },
    ]
    health_df = write_o_contract_df(
        root_path,
        "restock_profit_input_blocker_breakdown_health",
        pd.DataFrame(health_rows),
    )
    return out_df, health_df


def main() -> int:
    out_df, health_df = build_profit_input_blocker_breakdown()
    summary = health_df[health_df["check"] == "profit_input_blocker_rows"]
    lanes = health_df[health_df["check"] == "weak_input_lanes"]
    print(f"blocker_rows={len(out_df.index)}")
    if not summary.empty:
        print(str(summary.iloc[0]["value"]))
    if not lanes.empty:
        print(str(lanes.iloc[0]["value"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
