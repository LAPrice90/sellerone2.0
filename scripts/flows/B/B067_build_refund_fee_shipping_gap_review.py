from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.safe_file_writes import safe_to_csv


OUT = Path("out")
SELLERBOARD_SUMMARY = OUT / "systems" / "M" / "sellerboard_bridge" / "b_sellerboard_bridge_summary.csv"
REFUND_BRIDGE = OUT / "systems" / "B" / "refunds" / "b_refund_pnl_bridge.csv"
REFUND_RATE = OUT / "systems" / "B" / "refunds" / "b_sku_refund_rate.csv"
LEVEL3_PROOF_MAP = OUT / "systems" / "B" / "refunds" / "b_level3_fee_shipping_api_proof_map.csv"
E_PERFORMANCE = OUT / "sku_performance_summary.csv"
O_RESTOCK_SOURCE = OUT / "systems" / "O" / "live" / "restock_source_view.csv"
OUT_REVIEW = OUT / "systems" / "B" / "refunds" / "b_refund_fee_shipping_gap_review.csv"
OUT_SUMMARY = OUT / "systems" / "B" / "refunds" / "b_refund_fee_shipping_gap_review_summary.csv"

MANAGER_LABELS = {"api_proved", "sellerboard_bridge_estimate", "not_yet_proven"}
DOWNSTREAM_CONSUMER_AREAS = {"live_roi_safety_gate", "e_roi_confidence", "o_restock_confidence"}

REVIEW_COLUMNS = [
    "money_area",
    "manager_money_label",
    "source_metric",
    "source_value",
    "api_proof_state",
    "sellerboard_witness_rows",
    "gap_rows",
    "downstream_warning_rows",
    "live_roi_use_allowed",
    "roi_or_restock_use_allowed",
    "sellerboard_final_truth_allowed",
    "manager_expectation",
    "bounded_worker_task",
    "retest_rule",
    "protected_stop_rule",
    "source_path",
]

SUMMARY_COLUMNS = ["metric", "value"]

LEVEL3_FIELD_BY_MONEY_AREA = {
    "commission_fee": "commission",
    "fba_fee": "fba_fee",
    "shipping_income": "shipping_income",
    "shipping_fee": "shipping_chargeback_or_cost",
    "refund_fee_reversals": "refund_fee_reversals",
}


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame()


def _text(value: object) -> str:
    return str(value or "").strip()


def _metric_rows(summary: pd.DataFrame) -> dict[str, dict[str, str]]:
    if summary.empty or "metric" not in summary.columns:
        return {}
    rows: dict[str, dict[str, str]] = {}
    for _, row in summary.iterrows():
        metric = _text(row.get("metric", ""))
        if metric:
            rows[metric] = {str(key): _text(value) for key, value in row.to_dict().items()}
    return rows


def _metric(metrics: dict[str, dict[str, str]], name: str, default: str = "") -> str:
    return _text(metrics.get(name, {}).get("value", default))


def _metric_int(metrics: dict[str, dict[str, str]], name: str) -> int:
    try:
        return int(float(_metric(metrics, name, "0") or "0"))
    except ValueError:
        return 0


def _to_int(value: object) -> int:
    try:
        return int(float(_text(value) or "0"))
    except ValueError:
        return 0


def _safe_count(df: pd.DataFrame, column: str, value: str) -> int:
    if df.empty or column not in df.columns:
        return 0
    return int((df[column].astype(str).str.strip() == value).sum())


def _metric_notes(metrics: dict[str, dict[str, str]], name: str) -> str:
    return _text(metrics.get(name, {}).get("notes", ""))


def _split_order_notes(value: str) -> list[str]:
    return [part.strip() for part in _text(value).split(";") if part.strip()]


def _api_proved_refund_orders(refund_bridge: pd.DataFrame) -> set[str]:
    if refund_bridge.empty or "order_id" not in refund_bridge.columns or "api_refund_proof_state" not in refund_bridge.columns:
        return set()
    proved = refund_bridge[refund_bridge["api_refund_proof_state"].astype(str).str.strip() == "api_proved"].copy()
    return {order_id for order_id in proved["order_id"].astype(str).str.strip() if order_id}


def _manager_label_for_state(state: str) -> str:
    clean = _text(state).lower()
    if clean in {"api_proved", "api_proved_or_not_applicable", "api_backed_safe"}:
        return "api_proved"
    if clean in {"sellerboard_bridge_only", "bridge_labelled_only", "sellerboard_bridge_estimate"}:
        return "sellerboard_bridge_estimate"
    return "not_yet_proven"


def _level3_proof_rows(proof_map: pd.DataFrame) -> dict[str, dict[str, str]]:
    if proof_map.empty or "money_field" not in proof_map.columns:
        return {}
    rows: dict[str, dict[str, str]] = {}
    for _, row in proof_map.iterrows():
        money_field = _text(row.get("money_field", ""))
        if money_field:
            rows[money_field] = {str(key): _text(value) for key, value in row.to_dict().items()}
    return rows


def _level3_override_for_money_area(
    level3_rows: dict[str, dict[str, str]],
    money_area: str,
) -> dict[str, str] | None:
    money_field = LEVEL3_FIELD_BY_MONEY_AREA.get(money_area, "")
    if not money_field or money_field not in level3_rows:
        return None
    row = level3_rows[money_field]
    proof_label = _text(row.get("proof_label", ""))
    source_rows = _to_int(row.get("source_row_count", "0"))
    official_rows = _to_int(row.get("official_output_row_count", "0"))
    order_master_rows = _to_int(row.get("order_master_row_count", "0"))
    keys_ok = _text(row.get("required_keys_present", "")) == "1"
    unsafe = (
        _text(row.get("live_roi_use_allowed", "")) != "0"
        or _text(row.get("roi_or_restock_use_allowed", "")) != "0"
        or _text(row.get("sellerboard_final_truth_allowed", "")) != "0"
    )
    label = "not_yet_proven"
    if proof_label == "api_source_available" and source_rows > 0 and keys_ok and not unsafe:
        label = "api_proved"
    return {
        "money_field": money_field,
        "label": label,
        "api_proof_state": "level3_api_source_available" if label == "api_proved" else proof_label or "not_yet_proven",
        "source_rows": str(source_rows),
        "official_rows": str(official_rows),
        "order_master_rows": str(order_master_rows),
        "required_keys_present": "1" if keys_ok else "0",
        "proof_label": proof_label or "not_yet_proven",
        "gap_rows": "0" if label == "api_proved" else "1",
    }


def _weak_refund_state(value: object) -> bool:
    clean = _text(value).lower()
    return clean not in {"", "api_proved", "api_proved_or_not_applicable", "api_backed_safe"}


def _expected_refund_nonzero(row: pd.Series) -> bool:
    try:
        return abs(float(_text(row.get("expected_refund_cost_per_unit_gbp", "")) or "0")) > 0.005
    except ValueError:
        return False


def _performance_warning_counts(performance: pd.DataFrame) -> tuple[int, int, int]:
    if performance.empty:
        return 0, 0, 0
    bridge_rows = _safe_count(performance, "b_money_confidence_state", "bridge_labelled_only")
    unsafe_rows = 0
    if "b_bridge_values_safe_for_live_roi" in performance.columns:
        unsafe_rows = int((performance["b_bridge_values_safe_for_live_roi"].astype(str).str.strip() != "1").sum())
    weak_refund_rows = 0
    if "refund_proof_state" in performance.columns:
        weak_refund_rows = int(performance["refund_proof_state"].map(_weak_refund_state).sum())
    missing_proof_rows = 0
    if "restock_missing_proof" in performance.columns:
        missing_proof_rows = int(
            performance["restock_missing_proof"]
            .astype(str)
            .str.lower()
            .str.contains("weak_refund_proof|bridge_labelled_money", regex=True)
            .sum()
        )
    return bridge_rows, max(unsafe_rows, weak_refund_rows, missing_proof_rows), weak_refund_rows


def _restock_warning_counts(restock: pd.DataFrame) -> tuple[int, int]:
    if restock.empty:
        return 0, 0
    weak_rows = 0
    if "refund_proof_state" in restock.columns:
        weak_rows = int(
            restock[
                restock.apply(
                    lambda row: _expected_refund_nonzero(row) and _weak_refund_state(row.get("refund_proof_state", "")),
                    axis=1,
                )
            ].shape[0]
        )
    blocker_rows = 0
    if "profit_input_blockers" in restock.columns:
        blocker_rows = int(
            restock["profit_input_blockers"]
            .astype(str)
            .str.lower()
            .str.contains("refund|bridge|fee|shipping", regex=True)
            .sum()
        )
    return max(weak_rows, blocker_rows), blocker_rows


def _append_row(
    rows: list[dict[str, str]],
    *,
    money_area: str,
    label: str,
    source_metric: str,
    source_value: str,
    api_proof_state: str,
    sellerboard_witness_rows: int = 0,
    gap_rows: int = 0,
    downstream_warning_rows: int = 0,
    source_path: Path | str = "",
) -> None:
    rows.append(
        {
            "money_area": money_area,
            "manager_money_label": label if label in MANAGER_LABELS else "not_yet_proven",
            "source_metric": source_metric,
            "source_value": _text(source_value),
            "api_proof_state": _text(api_proof_state) or "not_yet_proven",
            "sellerboard_witness_rows": str(sellerboard_witness_rows),
            "gap_rows": str(gap_rows),
            "downstream_warning_rows": str(downstream_warning_rows),
            "live_roi_use_allowed": "0",
            "roi_or_restock_use_allowed": "0",
            "sellerboard_final_truth_allowed": "0",
            "manager_expectation": (
                "B money fields must stay labelled as API proved, Sellerboard bridge estimate, "
                "or not yet proven before E ROI or O restocking can trust them."
            ),
            "bounded_worker_task": (
                "Improve API-backed refund, fee, shipping, or downstream confidence proof only. "
                "Do not change live ROI, restocking, orders, tokens, local DB, Sheets, prices, or queues."
            ),
            "retest_rule": "Rerun this read-only B067 proof and then the B MOT; the same MOT row must clear.",
            "protected_stop_rule": (
                "Stop before feeding bridge values into ROI/restocking, correcting data, running B, "
                "writing Sheets, aligning local DB data, deleting outputs, changing prices, or changing queues."
            ),
            "source_path": str(source_path),
        }
    )


def build_refund_fee_shipping_gap_review(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
) -> dict[str, pd.DataFrame]:
    root_path = Path(root or ".")
    observed = observed_utc or _utc_now_text()
    sellerboard_summary_path = root_path / SELLERBOARD_SUMMARY
    refund_bridge_path = root_path / REFUND_BRIDGE
    refund_rate_path = root_path / REFUND_RATE
    level3_proof_map_path = root_path / LEVEL3_PROOF_MAP
    performance_path = root_path / E_PERFORMANCE
    restock_path = root_path / O_RESTOCK_SOURCE

    sellerboard_summary = _read_csv(sellerboard_summary_path)
    refund_bridge = _read_csv(refund_bridge_path)
    refund_rate = _read_csv(refund_rate_path)
    level3_proof_map = _read_csv(level3_proof_map_path)
    performance = _read_csv(performance_path)
    restock = _read_csv(restock_path)
    metrics = _metric_rows(sellerboard_summary)
    level3_rows = _level3_proof_rows(level3_proof_map)

    rows: list[dict[str, str]] = []
    api_refund_rows = _safe_count(refund_bridge, "api_refund_proof_state", "api_proved")
    bridge_refund_rows = _safe_count(refund_bridge, "api_refund_proof_state", "sellerboard_bridge_only")
    _append_row(
        rows,
        money_area="api_refund_money",
        label="api_proved" if api_refund_rows else "not_yet_proven",
        source_metric="b_refund_pnl_bridge.api_refund_proof_state",
        source_value=f"api_rows={api_refund_rows};bridge_rows={bridge_refund_rows};total_rows={len(refund_bridge)}",
        api_proof_state="api_proved" if api_refund_rows else "not_yet_proven",
        gap_rows=bridge_refund_rows,
        source_path=refund_bridge_path,
    )

    sellerboard_return_rows = _metric_int(metrics, "sellerboard_return_rows")
    return_gap = _metric_int(metrics, "sellerboard_return_orders_missing_local_refund_posted_window")
    return_gap_orders = _split_order_notes(_metric_notes(metrics, "sellerboard_return_orders_missing_local_refund_posted_window"))
    api_proved_orders = _api_proved_refund_orders(refund_bridge)
    api_proved_gap_orders = [order_id for order_id in return_gap_orders if order_id in api_proved_orders]
    unproved_gap_orders = [order_id for order_id in return_gap_orders if order_id not in api_proved_orders]
    if return_gap_orders:
        unresolved_return_gap = len(unproved_gap_orders)
    else:
        unresolved_return_gap = return_gap
    return_gap_label = "api_proved" if unresolved_return_gap == 0 else "sellerboard_bridge_estimate"
    _append_row(
        rows,
        money_area="sellerboard_return_refund_gap",
        label=return_gap_label,
        source_metric="sellerboard_return_orders_missing_local_refund_posted_window",
        source_value=(
            f"sellerboard_gap={return_gap};api_proved_gap_orders={len(api_proved_gap_orders)};"
            f"unproved_gap_orders={unresolved_return_gap}"
        ),
        api_proof_state="api_proved" if return_gap_label == "api_proved" else _metric(metrics, "refund_api_proof_state", "not_yet_proven"),
        sellerboard_witness_rows=sellerboard_return_rows,
        gap_rows=unresolved_return_gap,
        source_path=f"{sellerboard_summary_path};{refund_bridge_path}",
    )

    fee_components = [
        ("commission_fee", "commission_api_proof_state", "fee_detail_commission_api_rows"),
        ("fba_fee", "fba_fee_api_proof_state", "fee_detail_fba_fee_api_rows"),
        ("other_fee", "other_fee_api_proof_state", "fee_detail_other_fee_api_rows"),
        ("shipping_income", "shipping_income_api_proof_state", "sellerboard_shipping_income_rows"),
        ("shipping_fee", "shipping_fee_api_proof_state", "fee_detail_shipping_fee_api_rows"),
    ]
    for money_area, state_metric, count_metric in fee_components:
        state = _metric(metrics, state_metric, "not_yet_proven")
        count_value = _metric_int(metrics, count_metric)
        level3_override = _level3_override_for_money_area(level3_rows, money_area)
        if level3_override:
            label = level3_override["label"]
            source_metric = f"b_level3_fee_shipping_api_proof_map.{level3_override['money_field']}"
            source_value = (
                f"level3_label={level3_override['proof_label']};"
                f"source_rows={level3_override['source_rows']};"
                f"official_rows={level3_override['official_rows']};"
                f"order_master_rows={level3_override['order_master_rows']};"
                f"required_keys_present={level3_override['required_keys_present']};"
                f"sellerboard_state={state};sellerboard_rows={count_value}"
            )
            api_state = level3_override["api_proof_state"]
            gap_rows = _to_int(level3_override["gap_rows"])
            source_path = level3_proof_map_path
        else:
            label = _manager_label_for_state(state)
            source_metric = state_metric
            source_value = f"state={state};api_rows_or_source_rows={count_value}"
            api_state = state
            gap_rows = 1 if label == "not_yet_proven" else 0
            source_path = sellerboard_summary_path
        _append_row(
            rows,
            money_area=money_area,
            label=label,
            source_metric=source_metric,
            source_value=source_value,
            api_proof_state=api_state,
            sellerboard_witness_rows=sellerboard_return_rows,
            gap_rows=gap_rows,
            source_path=source_path,
        )

    refund_fee_reversal_override = _level3_override_for_money_area(level3_rows, "refund_fee_reversals")
    if refund_fee_reversal_override:
        _append_row(
            rows,
            money_area="refund_fee_reversals",
            label=refund_fee_reversal_override["label"],
            source_metric=f"b_level3_fee_shipping_api_proof_map.{refund_fee_reversal_override['money_field']}",
            source_value=(
                f"level3_label={refund_fee_reversal_override['proof_label']};"
                f"source_rows={refund_fee_reversal_override['source_rows']};"
                f"official_rows={refund_fee_reversal_override['official_rows']};"
                f"required_keys_present={refund_fee_reversal_override['required_keys_present']}"
            ),
            api_proof_state=refund_fee_reversal_override["api_proof_state"],
            sellerboard_witness_rows=sellerboard_return_rows,
            gap_rows=_to_int(refund_fee_reversal_override["gap_rows"]),
            source_path=level3_proof_map_path,
        )

    refund_rate_api_rows = _safe_count(refund_rate, "proof_state", "api_proved_or_not_applicable") + _safe_count(
        refund_rate, "proof_state", "api_proved"
    )
    roi_refund_state = _metric(metrics, "roi_refund_proof_state", "not_yet_proven")
    _append_row(
        rows,
        money_area="roi_refund_drag",
        label="api_proved" if refund_rate_api_rows or _manager_label_for_state(roi_refund_state) == "api_proved" else "not_yet_proven",
        source_metric="b_sku_refund_rate.proof_state",
        source_value=f"api_rate_rows={refund_rate_api_rows};total_rows={len(refund_rate)};roi_state={roi_refund_state}",
        api_proof_state=roi_refund_state,
        gap_rows=0 if refund_rate_api_rows else 1,
        source_path=refund_rate_path,
    )

    live_roi_safe = _metric(metrics, "bridge_values_safe_for_live_roi", "0")
    _append_row(
        rows,
        money_area="live_roi_safety_gate",
        label="api_proved" if live_roi_safe == "1" else "not_yet_proven",
        source_metric="bridge_values_safe_for_live_roi",
        source_value=live_roi_safe,
        api_proof_state="api_backed_safe" if live_roi_safe == "1" else _metric(metrics, "roi_money_confidence_state", "not_yet_proven"),
        gap_rows=0 if live_roi_safe == "1" else 1,
        source_path=sellerboard_summary_path,
    )

    performance_bridge_rows, performance_warning_rows, performance_refund_weak_rows = _performance_warning_counts(performance)
    performance_label = (
        "sellerboard_bridge_estimate"
        if performance_bridge_rows
        else "not_yet_proven"
        if performance.empty or performance_warning_rows
        else "api_proved"
    )
    _append_row(
        rows,
        money_area="e_roi_confidence",
        label=performance_label,
        source_metric="out/sku_performance_summary.csv",
        source_value=(
            f"rows={len(performance)};bridge_rows={performance_bridge_rows};"
            f"warning_rows={performance_warning_rows};weak_refund_rows={performance_refund_weak_rows}"
        ),
        api_proof_state="api_backed_safe" if performance_label == "api_proved" else "bridge_labelled_only" if performance_label == "sellerboard_bridge_estimate" else "not_yet_proven",
        gap_rows=performance_warning_rows,
        downstream_warning_rows=performance_warning_rows,
        source_path=performance_path,
    )

    restock_warning_rows, restock_blocker_rows = _restock_warning_counts(restock)
    restock_label = "not_yet_proven" if restock.empty or restock_warning_rows else "api_proved"
    _append_row(
        rows,
        money_area="o_restock_confidence",
        label=restock_label,
        source_metric="out/systems/O/live/restock_source_view.csv",
        source_value=f"rows={len(restock)};warning_rows={restock_warning_rows};blocker_rows={restock_blocker_rows}",
        api_proof_state="api_backed_safe" if restock_label == "api_proved" else "not_yet_proven",
        gap_rows=restock_warning_rows,
        downstream_warning_rows=restock_warning_rows,
        source_path=restock_path,
    )

    review = pd.DataFrame(rows, columns=REVIEW_COLUMNS).fillna("")
    unsafe_rows = (
        int((review["live_roi_use_allowed"].astype(str).str.strip() != "0").sum())
        + int((review["roi_or_restock_use_allowed"].astype(str).str.strip() != "0").sum())
        + int((review["sellerboard_final_truth_allowed"].astype(str).str.strip() != "0").sum())
        if not review.empty
        else 0
    )
    unclassified_rows = int((~review["manager_money_label"].isin(MANAGER_LABELS)).sum()) if not review.empty else 0
    label_counts = {
        label: int((review["manager_money_label"] == label).sum()) if not review.empty else 0
        for label in sorted(MANAGER_LABELS)
    }
    b_source_review = review[~review["money_area"].isin(DOWNSTREAM_CONSUMER_AREAS)].copy() if not review.empty else review
    downstream_review = review[review["money_area"].isin(DOWNSTREAM_CONSUMER_AREAS)].copy() if not review.empty else review
    b_source_label_counts = {
        label: int((b_source_review["manager_money_label"] == label).sum()) if not b_source_review.empty else 0
        for label in sorted(MANAGER_LABELS)
    }
    downstream_consumer_warning_rows = (
        int((downstream_review["manager_money_label"] != "api_proved").sum())
        + int(downstream_review["downstream_warning_rows"].map(_to_int).sum())
        if not downstream_review.empty
        else 0
    )
    b_source_chain_state = "not_yet_proven"
    if b_source_label_counts["not_yet_proven"]:
        b_source_chain_state = "not_yet_proven"
    elif b_source_label_counts["sellerboard_bridge_estimate"]:
        b_source_chain_state = "bridge_labelled_only"
    elif b_source_label_counts["api_proved"]:
        b_source_chain_state = "api_proved"
    b_source_ready = (
        b_source_chain_state == "api_proved"
        and unsafe_rows == 0
        and unclassified_rows == 0
    )
    missing_sources = [
        str(path)
        for path in [sellerboard_summary_path, refund_bridge_path, refund_rate_path, performance_path, restock_path]
        if not path.exists()
    ]
    level3_connected_api_rows = sum(
        1
        for money_area in LEVEL3_FIELD_BY_MONEY_AREA
        if (_level3_override_for_money_area(level3_rows, money_area) or {}).get("label") == "api_proved"
    )
    level3_connected_not_yet_rows = sum(
        1
        for money_area in LEVEL3_FIELD_BY_MONEY_AREA
        if (_level3_override_for_money_area(level3_rows, money_area) or {}).get("label") == "not_yet_proven"
    )
    status = "ok"
    if unsafe_rows or unclassified_rows:
        status = "fail"
    elif not b_source_ready:
        status = "warn"

    summary_rows = [
        {"metric": "status", "value": status},
        {"metric": "observed_utc", "value": observed},
        {"metric": "review_rows", "value": str(len(review))},
        {"metric": "api_proved_rows", "value": str(label_counts["api_proved"])},
        {"metric": "sellerboard_bridge_estimate_rows", "value": str(label_counts["sellerboard_bridge_estimate"])},
        {"metric": "not_yet_proven_rows", "value": str(label_counts["not_yet_proven"])},
        {"metric": "b_source_review_rows", "value": str(len(b_source_review))},
        {"metric": "b_source_api_proved_rows", "value": str(b_source_label_counts["api_proved"])},
        {"metric": "b_source_sellerboard_bridge_estimate_rows", "value": str(b_source_label_counts["sellerboard_bridge_estimate"])},
        {"metric": "b_source_not_yet_proven_rows", "value": str(b_source_label_counts["not_yet_proven"])},
        {"metric": "b_source_chain_state", "value": b_source_chain_state},
        {"metric": "b_source_handoff_ready", "value": "1" if b_source_ready else "0"},
        {"metric": "downstream_consumer_review_rows", "value": str(len(downstream_review))},
        {"metric": "downstream_consumer_warning_rows", "value": str(downstream_consumer_warning_rows)},
        {"metric": "unsafe_rows", "value": str(unsafe_rows)},
        {"metric": "unclassified_rows", "value": str(unclassified_rows)},
        {"metric": "bridge_values_safe_for_live_roi", "value": live_roi_safe},
        {"metric": "api_refund_rows", "value": str(api_refund_rows)},
        {"metric": "sellerboard_return_gap_rows", "value": str(return_gap)},
        {"metric": "fee_detail_ledger_api_rows", "value": str(_metric_int(metrics, "fee_detail_ledger_api_rows"))},
        {"metric": "level3_proof_map_rows", "value": str(len(level3_proof_map))},
        {"metric": "level3_connected_api_proved_rows", "value": str(level3_connected_api_rows)},
        {"metric": "level3_connected_not_yet_proven_rows", "value": str(level3_connected_not_yet_rows)},
        {"metric": "e_bridge_warning_rows", "value": str(performance_bridge_rows)},
        {"metric": "e_downstream_warning_rows", "value": str(performance_warning_rows)},
        {"metric": "o_downstream_warning_rows", "value": str(restock_warning_rows)},
        {"metric": "missing_sources", "value": ";".join(missing_sources)},
    ]
    summary = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS).fillna("")
    return {"review": review, "summary": summary}


def write_refund_fee_shipping_gap_review_outputs(
    result: dict[str, pd.DataFrame],
    *,
    root: Path | str | None = None,
) -> dict[str, Path]:
    root_path = Path(root or ".")
    review_path = root_path / OUT_REVIEW
    summary_path = root_path / OUT_SUMMARY
    safe_to_csv(result["review"], review_path, index=False)
    safe_to_csv(result["summary"], summary_path, index=False)
    return {"review": review_path, "summary": summary_path}


def main() -> None:
    result = build_refund_fee_shipping_gap_review()
    paths = write_refund_fee_shipping_gap_review_outputs(result)
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}
    print(
        {
            "status": summary.get("status", ""),
            "review_rows": summary.get("review_rows", "0"),
            "api_proved_rows": summary.get("api_proved_rows", "0"),
            "sellerboard_bridge_estimate_rows": summary.get("sellerboard_bridge_estimate_rows", "0"),
            "not_yet_proven_rows": summary.get("not_yet_proven_rows", "0"),
            "review": str(paths["review"]),
            "summary": str(paths["summary"]),
        }
    )


if __name__ == "__main__":
    main()
