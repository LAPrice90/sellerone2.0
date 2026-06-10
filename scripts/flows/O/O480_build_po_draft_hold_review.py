from __future__ import annotations

import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BOOT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT))

from scripts.flows.O.O478_build_po_draft_packet_review import build_po_draft_packet_review
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract


SOURCE_CLASSES = {"native_o", "legacy_bridge", "feeder_review_handoff", "manual_walkthrough_fixture"}
SOURCE_READY_STATE = "ready_for_local_po_draft_packet_review_only"
HELD_STATE = "held_for_local_po_draft_review_only"
BLOCKED_STATE = "blocked_from_local_po_draft_hold_review"
HOLD_ID_PREFIX = "o_po_draft_hold_review_v1"
DEFAULT_HOLD_REASON = "local_review_hold_zero_action"
ZERO_FLAG_COLUMNS = (
    "po_file_write_allowed",
    "po_creation_allowed",
    "purchase_commitment_allowed",
    "receiving_allowed",
    "send_to_amazon_allowed",
    "creates_live_action",
)
SOURCE_FLAG_MAP = {
    "po_file_write_allowed": "source_po_file_write_allowed",
    "po_creation_allowed": "source_po_creation_allowed",
    "purchase_commitment_allowed": "source_purchase_commitment_allowed",
    "receiving_allowed": "source_receiving_allowed",
    "send_to_amazon_allowed": "source_send_to_amazon_allowed",
    "creates_live_action": "source_creates_live_action",
}
UNSAFE_TEXT_TOKENS = (
    "purchase_order",
    "purchase order",
    "po_created",
    "po created",
    "committed",
    "sent_to_amazon",
    "sent to amazon",
    "buy_committed",
    "approval_applied",
    "live_action",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _safe_fragment(value: object) -> str:
    text = _normalize_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "unknown"


def _num(value: object) -> float | None:
    text = _normalize_text(value).replace(",", "")
    if text == "":
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed


def _positive_num(value: object) -> float | None:
    parsed = _num(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed


def _num_text(value: float | None) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _contains_unsafe_language(*values: object) -> bool:
    text = " ".join(_normalize_text(value).lower() for value in values)
    return any(token in text for token in UNSAFE_TEXT_TOKENS)


def _hold_id(row: pd.Series) -> str:
    basis = _normalize_text(row.get("po_draft_packet_review_id", ""))
    if not basis:
        basis = _normalize_text(row.get("po_line_design_packet_id", ""))
    if not basis:
        basis = _normalize_text(row.get("approval_packet_id", ""))
    if not basis:
        basis = _normalize_text(row.get("supplier_code", "")) or _normalize_text(row.get("supplier_name", ""))
    return f"{HOLD_ID_PREFIX}:{_safe_fragment(basis)}"


def _line_state(row: pd.Series) -> tuple[str, str]:
    reasons: list[str] = []
    if _normalize_text(row.get("po_draft_packet_review_id", "")) == "":
        reasons.append("missing_packet_review_id")
    if _normalize_text(row.get("source_class", "")) not in SOURCE_CLASSES:
        reasons.append("unsupported_source_class")
    if _normalize_text(row.get("packet_review_line_state", "")) != SOURCE_READY_STATE:
        reasons.append("source_packet_review_not_ready")
    for source_column in ZERO_FLAG_COLUMNS:
        if _normalize_text(row.get(source_column, "")) != "0":
            reasons.append(f"source_{source_column}_not_zero")
    if _positive_num(row.get("review_order_qty", "")) is None:
        reasons.append("missing_or_invalid_hold_qty")
    if _positive_num(row.get("review_unit_cost_gbp", "")) is None:
        reasons.append("missing_or_invalid_unit_cost")
    if _positive_num(row.get("review_line_value_gbp", "")) is None:
        reasons.append("missing_or_invalid_line_value")
    if reasons:
        return BLOCKED_STATE, "|".join(dict.fromkeys(reasons))
    return HELD_STATE, DEFAULT_HOLD_REASON


def _build_lines(hold_utc: str, packet_df: pd.DataFrame) -> pd.DataFrame:
    if packet_df.empty:
        return pd.DataFrame()
    rows: list[dict[str, str]] = []
    for _, line in packet_df.iterrows():
        hold_id = _hold_id(line)
        state, reasons = _line_state(line)
        output_row = {
            "hold_utc": hold_utc,
            "po_draft_hold_review_id": hold_id,
            "po_draft_packet_review_id": _normalize_text(line.get("po_draft_packet_review_id", "")),
            "po_line_design_packet_id": _normalize_text(line.get("po_line_design_packet_id", "")),
            "approval_packet_id": _normalize_text(line.get("approval_packet_id", "")),
            "source_packet_review_utc": _normalize_text(line.get("review_utc", "")),
            "batch_id": _normalize_text(line.get("batch_id", "")),
            "session_id": _normalize_text(line.get("session_id", "")),
            "row_id": _normalize_text(line.get("row_id", "")),
            "supplier_name": _normalize_text(line.get("supplier_name", "")),
            "supplier_code": _normalize_text(line.get("supplier_code", "")),
            "source_class": _normalize_text(line.get("source_class", "")),
            "seller_sku": _normalize_text(line.get("seller_sku", "")),
            "asin": _normalize_text(line.get("asin", "")),
            "title": _normalize_text(line.get("title", "")),
            "supplier_sku": _normalize_text(line.get("supplier_sku", "")),
            "barcode": _normalize_text(line.get("barcode", "")),
            "hold_order_qty": _normalize_text(line.get("review_order_qty", "")),
            "hold_unit_cost_gbp": _normalize_text(line.get("review_unit_cost_gbp", "")),
            "hold_line_value_gbp": _normalize_text(line.get("review_line_value_gbp", "")),
            "source_packet_review_line_state": _normalize_text(line.get("packet_review_line_state", "")),
            "hold_review_line_state": state,
            "hold_review_reasons": reasons,
            "expected_profit_per_unit_gbp": _normalize_text(line.get("expected_profit_per_unit_gbp", "")),
            "expected_roi_pct": _normalize_text(line.get("expected_roi_pct", "")),
            "profit_verdict": _normalize_text(line.get("profit_verdict", "")),
            "market_price_proof_state": _normalize_text(line.get("market_price_proof_state", "")),
            "refund_proof_state": _normalize_text(line.get("refund_proof_state", "")),
            "inbound_cost_proof_state": _normalize_text(line.get("inbound_cost_proof_state", "")),
            "latest_supplier_proof_id": _normalize_text(line.get("latest_supplier_proof_id", "")),
            "latest_pack_moq_proof_id": _normalize_text(line.get("latest_pack_moq_proof_id", "")),
            "source_classes": _normalize_text(line.get("source_classes", "")),
            "hold_review_basis": "local_po_draft_hold_review_only",
        }
        for source_column, output_column in SOURCE_FLAG_MAP.items():
            output_row[output_column] = _normalize_text(line.get(source_column, ""))
        for column in ZERO_FLAG_COLUMNS:
            output_row[column] = "0"
        rows.append(output_row)
    return pd.DataFrame(rows)


def _build_summary(hold_utc: str, lines_df: pd.DataFrame) -> pd.DataFrame:
    if lines_df.empty:
        return pd.DataFrame()
    rows: list[dict[str, str]] = []
    grouped = lines_df.groupby(
        ["po_draft_hold_review_id", "po_draft_packet_review_id", "po_line_design_packet_id", "approval_packet_id", "supplier_name", "supplier_code"],
        dropna=False,
        sort=True,
    )
    for (hold_id, packet_id, design_packet_id, approval_packet_id, supplier_name, supplier_code), group in grouped:
        held_count = int(group.get("hold_review_line_state", pd.Series(dtype=str)).map(_normalize_text).eq(HELD_STATE).sum())
        blocked_count = int(group.get("hold_review_line_state", pd.Series(dtype=str)).map(_normalize_text).eq(BLOCKED_STATE).sum())
        qty_total = pd.to_numeric(group.get("hold_order_qty", ""), errors="coerce").fillna(0).sum()
        value_total = pd.to_numeric(group.get("hold_line_value_gbp", ""), errors="coerce").fillna(0).sum()
        reason_counter: Counter[str] = Counter()
        for reason_text in group.get("hold_review_reasons", pd.Series(dtype=str)).tolist():
            for reason in [part for part in _normalize_text(reason_text).split("|") if part]:
                reason_counter[reason] += 1
        source_classes = {
            _normalize_text(value)
            for value in group.get("source_class", pd.Series(dtype=str)).tolist()
            if _normalize_text(value)
        }
        hold_state = HELD_STATE if held_count and not blocked_count else BLOCKED_STATE
        row = {
            "hold_utc": hold_utc,
            "po_draft_hold_review_id": _normalize_text(hold_id),
            "po_draft_packet_review_id": _normalize_text(packet_id),
            "po_line_design_packet_id": _normalize_text(design_packet_id),
            "approval_packet_id": _normalize_text(approval_packet_id),
            "supplier_name": _normalize_text(supplier_name),
            "supplier_code": _normalize_text(supplier_code),
            "line_count": str(len(group.index)),
            "held_line_count": str(held_count),
            "blocked_line_count": str(blocked_count),
            "hold_order_qty_total": _num_text(float(qty_total)),
            "hold_order_value_gbp": _num_text(float(value_total)) if value_total > 0 else "",
            "hold_review_state": hold_state,
            "hold_review_reasons": "|".join(reason for reason, _count in reason_counter.most_common(8)),
            "source_classes": "|".join(sorted(source_classes)),
        }
        for column in ZERO_FLAG_COLUMNS:
            row[column] = "0"
        rows.append(row)
    return pd.DataFrame(rows)


def _build_health(hold_utc: str, lines_df: pd.DataFrame, summary_df: pd.DataFrame, source_paths: list[Path]) -> pd.DataFrame:
    invalid_source_rows: list[str] = []
    source_action_rows: list[str] = []
    live_action_rows: list[str] = []
    live_language_rows: list[str] = []
    false_hold_rows: list[str] = []
    missing_hold_reason_rows: list[str] = []
    bad_summary_rows: list[str] = []
    if not lines_df.empty:
        for _, row in lines_df.iterrows():
            row_label = _normalize_text(row.get("row_id", "")) or _normalize_text(row.get("seller_sku", "")) or "missing_row"
            if _normalize_text(row.get("source_class", "")) not in SOURCE_CLASSES:
                invalid_source_rows.append(row_label)
            if any(_normalize_text(row.get(column, "")) != "0" for column in SOURCE_FLAG_MAP.values()):
                source_action_rows.append(row_label)
            if any(_normalize_text(row.get(column, "")) != "0" for column in ZERO_FLAG_COLUMNS):
                live_action_rows.append(row_label)
            if _contains_unsafe_language(row.get("hold_review_line_state", ""), row.get("hold_review_reasons", "")):
                live_language_rows.append(row_label)
            if _normalize_text(row.get("hold_review_line_state", "")) == HELD_STATE and (
                _normalize_text(row.get("po_draft_packet_review_id", "")) == ""
                or _normalize_text(row.get("source_packet_review_line_state", "")) != SOURCE_READY_STATE
                or any(_normalize_text(row.get(column, "")) != "0" for column in SOURCE_FLAG_MAP.values())
                or _positive_num(row.get("hold_order_qty", "")) is None
                or _positive_num(row.get("hold_unit_cost_gbp", "")) is None
                or _positive_num(row.get("hold_line_value_gbp", "")) is None
                or _normalize_text(row.get("source_class", "")) not in SOURCE_CLASSES
            ):
                false_hold_rows.append(row_label)
            if _normalize_text(row.get("hold_review_line_state", "")) in {HELD_STATE, BLOCKED_STATE} and _normalize_text(row.get("hold_review_reasons", "")) == "":
                missing_hold_reason_rows.append(row_label)
    if not summary_df.empty:
        for _, row in summary_df.iterrows():
            hold_id = _normalize_text(row.get("po_draft_hold_review_id", "")) or "missing_hold"
            if any(_normalize_text(row.get(column, "")) != "0" for column in ZERO_FLAG_COLUMNS):
                bad_summary_rows.append(f"{hold_id}:action_flag")
            if _contains_unsafe_language(row.get("hold_review_state", ""), row.get("hold_review_reasons", "")):
                bad_summary_rows.append(f"{hold_id}:unsafe_language")
    checks = [
        (
            "source_label_guard",
            not invalid_source_rows,
            f"invalid_source_rows={len(invalid_source_rows)};line_rows={len(lines_df.index)}",
            "Every PO draft hold review row must keep an approved O source class.",
        ),
        (
            "local_only_guard",
            not source_action_rows and not live_action_rows and not bad_summary_rows and not live_language_rows,
            (
                f"source_action_rows={len(source_action_rows)};"
                f"live_action_rows={len(live_action_rows)};"
                f"bad_summary_rows={len(bad_summary_rows)};"
                f"live_language_rows={len(live_language_rows)}"
            ),
            "PO draft hold review must not write PO files, write PO hold files, create POs, commit buying, receive stock, or send to Amazon.",
        ),
        (
            "hold_claim_guard",
            not false_hold_rows and not missing_hold_reason_rows,
            (
                f"false_hold_rows={len(false_hold_rows)};"
                f"missing_hold_reason_rows={len(missing_hold_reason_rows)}"
            ),
            "A line can only be locally held after safe packet-review proof, quantity, unit cost, and line value.",
        ),
        (
            "summary_matches_lines",
            len(summary_df.index) <= len(lines_df.index),
            f"summary_rows={len(summary_df.index)};line_rows={len(lines_df.index)}",
            "PO draft hold review summary must not invent packets beyond hold lines.",
        ),
    ]
    source_path_text = ";".join(str(path) for path in source_paths)
    return pd.DataFrame(
        [
            {
                "check_utc": hold_utc,
                "check": check,
                "status": "ok" if passed else "fail",
                "value": value,
                "notes": notes,
                "source_path": source_path_text,
            }
            for check, passed, value, notes in checks
        ]
    )


def build_po_draft_hold_review(
    root: Path | None = None,
    *,
    hold_utc: str | None = None,
    write_outputs: bool = True,
    refresh_packet_review: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    paths = ensure_o_directories(root=root_path)
    observed = hold_utc or _utc_now_iso()
    if refresh_packet_review:
        build_po_draft_packet_review(
            root=root_path,
            review_utc=observed,
            write_outputs=write_outputs,
            refresh_design=True,
        )
    packet_df = read_o_contract_df(root_path, "restock_po_draft_packet_review_lines_live")
    lines_df = _build_lines(observed, packet_df)
    summary_df = _build_summary(observed, lines_df)
    source_paths = [
        root_path / "out" / "systems" / "O" / "live" / "restock_po_draft_packet_review_lines_live.csv",
    ]
    health_df = _build_health(observed, lines_df, summary_df, source_paths)
    if write_outputs:
        lines_df = write_o_contract_df(root_path, "restock_po_draft_hold_review_lines_live", lines_df)
        summary_df = write_o_contract_df(root_path, "restock_po_draft_hold_review_summary_live", summary_df)
        health_df = write_o_contract_df(root_path, "restock_po_draft_hold_review_health", health_df)
        history_dir = paths.history_dir / f"po_draft_hold_review_v1_{observed.replace(':', '').replace('-', '')}"
        history_dir.mkdir(parents=True, exist_ok=True)
        lines_df.to_csv(history_dir / "restock_po_draft_hold_review_lines_live.csv", index=False)
        summary_df.to_csv(history_dir / "restock_po_draft_hold_review_summary_live.csv", index=False)
        health_df.to_csv(history_dir / "restock_po_draft_hold_review_health.csv", index=False)
    return lines_df, summary_df, health_df


def main() -> int:
    lines_df, summary_df, health_df = build_po_draft_hold_review()
    bad_health = health_df[health_df.get("status", "").map(_normalize_text).ne("ok")]
    print(f"po_draft_hold_review_line_rows={len(lines_df.index)}")
    print(f"po_draft_hold_review_summary_rows={len(summary_df.index)}")
    print(f"health_status={'ok' if bad_health.empty else 'fail'}")
    return 0 if bad_health.empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
