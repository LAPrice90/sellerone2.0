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

from scripts.flows.O.O486_build_po_draft_review_controls import build_po_draft_review_controls
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract


SOURCE_READY_STATE = "ready_for_local_po_draft_file_shape_review_only"
CONTROL_READY_STATE = "local_po_draft_shape_ready_not_po"
READY_STATE = "ready_for_local_po_draft_export_preview_only"
BLOCKED_STATE = "blocked_from_local_po_draft_export_preview"
PREVIEW_ID_PREFIX = "o_po_draft_export_preview_v1"
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
CONTROL_FLAG_MAP = {
    "po_file_write_allowed": "control_po_file_write_allowed",
    "po_creation_allowed": "control_po_creation_allowed",
    "purchase_commitment_allowed": "control_purchase_commitment_allowed",
    "receiving_allowed": "control_receiving_allowed",
    "send_to_amazon_allowed": "control_send_to_amazon_allowed",
    "creates_live_action": "control_creates_live_action",
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
        return float(text)
    except ValueError:
        return None


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


def _export_preview_id(row: pd.Series) -> str:
    basis = _normalize_text(row.get("po_draft_file_shape_preview_id", ""))
    if not basis:
        basis = _normalize_text(row.get("po_draft_hold_review_id", ""))
    if not basis:
        basis = _normalize_text(row.get("supplier_code", "")) or _normalize_text(row.get("supplier_name", ""))
    return f"{PREVIEW_ID_PREFIX}:{_safe_fragment(basis)}"


def _control_by_shape(controls_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    controls: dict[str, dict[str, str]] = {}
    if controls_df.empty:
        return controls
    for _, row in controls_df.iterrows():
        normalized = {key: _normalize_text(value) for key, value in row.to_dict().items()}
        preview_id = normalized.get("po_draft_file_shape_preview_id", "")
        if preview_id:
            controls[preview_id] = normalized
    return controls


def _source_flag_value(row: pd.Series, flag_column: str) -> str:
    mapped = SOURCE_FLAG_MAP[flag_column]
    direct = _normalize_text(row.get(flag_column, ""))
    if direct:
        return direct
    return _normalize_text(row.get(mapped, ""))


def _line_state(line: pd.Series, control: dict[str, str] | None) -> tuple[str, str]:
    reasons: list[str] = []
    if control is None:
        reasons.append("missing_review_control")
    if _normalize_text(line.get("po_draft_file_shape_preview_id", "")) == "":
        reasons.append("missing_file_shape_preview_id")
    if _normalize_text(line.get("source_class", "")) == "":
        reasons.append("missing_source_class")
    if _normalize_text(line.get("file_shape_line_state", "")) != SOURCE_READY_STATE:
        reasons.append("file_shape_line_not_ready")
    for source_column in ZERO_FLAG_COLUMNS:
        if _source_flag_value(line, source_column) != "0":
            reasons.append("source_action_flags_not_zero")
            break
        if _normalize_text(line.get(source_column, "")) != "0":
            reasons.append("source_action_flags_not_zero")
            break
    if control is not None:
        if _normalize_text(control.get("review_control_state", "")) != CONTROL_READY_STATE:
            reasons.append("review_control_not_shape_ready")
        for control_column in ZERO_FLAG_COLUMNS:
            if _normalize_text(control.get(control_column, "")) != "0":
                reasons.append("review_control_action_flags_not_zero")
                break
    if _positive_num(line.get("file_shape_qty", "")) is None:
        reasons.append("missing_or_invalid_export_preview_qty")
    if _positive_num(line.get("file_shape_unit_cost_gbp", "")) is None:
        reasons.append("missing_or_invalid_unit_cost")
    if _positive_num(line.get("file_shape_line_value_gbp", "")) is None:
        reasons.append("missing_or_invalid_line_value")
    if reasons:
        return BLOCKED_STATE, "|".join(dict.fromkeys(reasons))
    return READY_STATE, ""


def _build_lines(export_preview_utc: str, source_df: pd.DataFrame, controls_df: pd.DataFrame) -> pd.DataFrame:
    if source_df.empty:
        return pd.DataFrame()
    controls = _control_by_shape(controls_df)
    rows: list[dict[str, str]] = []
    for _, line in source_df.iterrows():
        preview_id = _normalize_text(line.get("po_draft_file_shape_preview_id", ""))
        control = controls.get(preview_id)
        state, reasons = _line_state(line, control)
        output_row = {
            "export_preview_utc": export_preview_utc,
            "po_draft_export_preview_id": _export_preview_id(line),
            "po_draft_file_shape_preview_id": preview_id,
            "po_draft_hold_review_id": _normalize_text(line.get("po_draft_hold_review_id", "")),
            "po_draft_packet_review_id": _normalize_text(line.get("po_draft_packet_review_id", "")),
            "po_line_design_packet_id": _normalize_text(line.get("po_line_design_packet_id", "")),
            "approval_packet_id": _normalize_text(line.get("approval_packet_id", "")),
            "source_shape_utc": _normalize_text(line.get("shape_utc", "")),
            "source_control_utc": _normalize_text((control or {}).get("control_utc", "")),
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
            "export_preview_qty": _normalize_text(line.get("file_shape_qty", "")),
            "export_preview_unit_cost_gbp": _normalize_text(line.get("file_shape_unit_cost_gbp", "")),
            "export_preview_line_value_gbp": _normalize_text(line.get("file_shape_line_value_gbp", "")),
            "source_file_shape_line_state": _normalize_text(line.get("file_shape_line_state", "")),
            "source_review_control_state": _normalize_text((control or {}).get("review_control_state", "")),
            "export_preview_line_state": state,
            "export_preview_block_reasons": reasons,
            "expected_profit_per_unit_gbp": _normalize_text(line.get("expected_profit_per_unit_gbp", "")),
            "expected_roi_pct": _normalize_text(line.get("expected_roi_pct", "")),
            "profit_verdict": _normalize_text(line.get("profit_verdict", "")),
            "market_price_proof_state": _normalize_text(line.get("market_price_proof_state", "")),
            "refund_proof_state": _normalize_text(line.get("refund_proof_state", "")),
            "inbound_cost_proof_state": _normalize_text(line.get("inbound_cost_proof_state", "")),
            "latest_supplier_proof_id": _normalize_text(line.get("latest_supplier_proof_id", "")),
            "latest_pack_moq_proof_id": _normalize_text(line.get("latest_pack_moq_proof_id", "")),
            "source_classes": _normalize_text(line.get("source_classes", "")),
            "export_preview_basis": "local_po_draft_export_preview_only",
        }
        for source_column, output_column in SOURCE_FLAG_MAP.items():
            output_row[output_column] = _source_flag_value(line, source_column)
        for control_column, output_column in CONTROL_FLAG_MAP.items():
            output_row[output_column] = _normalize_text((control or {}).get(control_column, ""))
        for column in ZERO_FLAG_COLUMNS:
            output_row[column] = "0"
        rows.append(output_row)
    return pd.DataFrame(rows)


def _build_summary(export_preview_utc: str, lines_df: pd.DataFrame) -> pd.DataFrame:
    if lines_df.empty:
        return pd.DataFrame()
    rows: list[dict[str, str]] = []
    grouped = lines_df.groupby(
        [
            "po_draft_export_preview_id",
            "po_draft_file_shape_preview_id",
            "po_draft_hold_review_id",
            "po_draft_packet_review_id",
            "po_line_design_packet_id",
            "approval_packet_id",
            "supplier_name",
            "supplier_code",
        ],
        dropna=False,
        sort=True,
    )
    for (
        export_preview_id,
        file_shape_id,
        hold_id,
        packet_id,
        design_packet_id,
        approval_packet_id,
        supplier_name,
        supplier_code,
    ), group in grouped:
        ready_count = int(group.get("export_preview_line_state", pd.Series(dtype=str)).map(_normalize_text).eq(READY_STATE).sum())
        blocked_count = int(group.get("export_preview_line_state", pd.Series(dtype=str)).map(_normalize_text).eq(BLOCKED_STATE).sum())
        qty_total = pd.to_numeric(group.get("export_preview_qty", ""), errors="coerce").fillna(0).sum()
        value_total = pd.to_numeric(group.get("export_preview_line_value_gbp", ""), errors="coerce").fillna(0).sum()
        reason_counter: Counter[str] = Counter()
        for reason_text in group.get("export_preview_block_reasons", pd.Series(dtype=str)).tolist():
            for reason in [part for part in _normalize_text(reason_text).split("|") if part]:
                reason_counter[reason] += 1
        source_classes = {
            _normalize_text(value)
            for value in group.get("source_class", pd.Series(dtype=str)).tolist()
            if _normalize_text(value)
        }
        export_state = READY_STATE if ready_count and not blocked_count else BLOCKED_STATE
        row = {
            "export_preview_utc": export_preview_utc,
            "po_draft_export_preview_id": _normalize_text(export_preview_id),
            "po_draft_file_shape_preview_id": _normalize_text(file_shape_id),
            "po_draft_hold_review_id": _normalize_text(hold_id),
            "po_draft_packet_review_id": _normalize_text(packet_id),
            "po_line_design_packet_id": _normalize_text(design_packet_id),
            "approval_packet_id": _normalize_text(approval_packet_id),
            "supplier_name": _normalize_text(supplier_name),
            "supplier_code": _normalize_text(supplier_code),
            "line_count": str(len(group.index)),
            "ready_line_count": str(ready_count),
            "blocked_line_count": str(blocked_count),
            "export_preview_qty_total": _num_text(float(qty_total)),
            "export_preview_value_gbp": _num_text(float(value_total)) if value_total > 0 else "",
            "export_preview_state": export_state,
            "export_preview_block_reasons": "|".join(reason for reason, _count in reason_counter.most_common(8)),
            "source_classes": "|".join(sorted(source_classes)),
        }
        for column in ZERO_FLAG_COLUMNS:
            row[column] = "0"
        rows.append(row)
    return pd.DataFrame(rows)


def _build_health(
    export_preview_utc: str,
    lines_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    source_paths: list[Path],
) -> pd.DataFrame:
    source_action_rows: list[str] = []
    control_action_rows: list[str] = []
    live_action_rows: list[str] = []
    live_language_rows: list[str] = []
    unknown_state_rows: list[str] = []
    false_ready_rows: list[str] = []
    missing_block_reason_rows: list[str] = []
    bad_summary_rows: list[str] = []
    if not lines_df.empty:
        for _, row in lines_df.iterrows():
            row_label = _normalize_text(row.get("row_id", "")) or _normalize_text(row.get("seller_sku", "")) or "missing_row"
            if any(_normalize_text(row.get(column, "")) != "0" for column in SOURCE_FLAG_MAP.values()):
                source_action_rows.append(row_label)
            if any(_normalize_text(row.get(column, "")) != "0" for column in CONTROL_FLAG_MAP.values()):
                control_action_rows.append(row_label)
            if any(_normalize_text(row.get(column, "")) != "0" for column in ZERO_FLAG_COLUMNS):
                live_action_rows.append(row_label)
            if _contains_unsafe_language(
                row.get("source_review_control_state", ""),
                row.get("export_preview_line_state", ""),
                row.get("export_preview_block_reasons", ""),
                row.get("export_preview_basis", ""),
            ):
                live_language_rows.append(row_label)
            state = _normalize_text(row.get("export_preview_line_state", ""))
            if state not in {READY_STATE, BLOCKED_STATE}:
                unknown_state_rows.append(row_label)
            if state == READY_STATE and (
                _normalize_text(row.get("po_draft_file_shape_preview_id", "")) == ""
                or _normalize_text(row.get("source_file_shape_line_state", "")) != SOURCE_READY_STATE
                or _normalize_text(row.get("source_review_control_state", "")) != CONTROL_READY_STATE
                or any(_normalize_text(row.get(column, "")) != "0" for column in SOURCE_FLAG_MAP.values())
                or any(_normalize_text(row.get(column, "")) != "0" for column in CONTROL_FLAG_MAP.values())
                or _positive_num(row.get("export_preview_qty", "")) is None
                or _positive_num(row.get("export_preview_unit_cost_gbp", "")) is None
                or _positive_num(row.get("export_preview_line_value_gbp", "")) is None
            ):
                false_ready_rows.append(row_label)
            if state == BLOCKED_STATE and _normalize_text(row.get("export_preview_block_reasons", "")) == "":
                missing_block_reason_rows.append(row_label)
    if not summary_df.empty:
        for _, row in summary_df.iterrows():
            preview_id = _normalize_text(row.get("po_draft_export_preview_id", "")) or "missing_export_preview"
            ready_count = _num(row.get("ready_line_count", ""))
            blocked_count = _num(row.get("blocked_line_count", ""))
            line_count = _num(row.get("line_count", ""))
            state = _normalize_text(row.get("export_preview_state", ""))
            if any(_normalize_text(row.get(column, "")) != "0" for column in ZERO_FLAG_COLUMNS):
                bad_summary_rows.append(f"{preview_id}:action_flag")
            if _contains_unsafe_language(row.get("export_preview_state", ""), row.get("export_preview_block_reasons", "")):
                bad_summary_rows.append(f"{preview_id}:unsafe_language")
            if state not in {READY_STATE, BLOCKED_STATE}:
                bad_summary_rows.append(f"{preview_id}:unknown_state")
            if line_count is None or ready_count is None or blocked_count is None or int(ready_count + blocked_count) != int(line_count):
                bad_summary_rows.append(f"{preview_id}:count_mismatch")
            if state == READY_STATE and (not ready_count or blocked_count):
                bad_summary_rows.append(f"{preview_id}:false_ready")
    checks = [
        (
            "local_only_guard",
            not source_action_rows and not control_action_rows and not live_action_rows and not live_language_rows and not bad_summary_rows,
            (
                f"source_action_rows={len(source_action_rows)};"
                f"control_action_rows={len(control_action_rows)};"
                f"live_action_rows={len(live_action_rows)};"
                f"live_language_rows={len(live_language_rows)};"
                f"bad_summary_rows={len(bad_summary_rows)}"
            ),
            "PO draft export preview must not write files, create POs, commit buying, receive stock, or send to Amazon.",
        ),
        (
            "export_preview_claim_guard",
            not unknown_state_rows and not false_ready_rows and not missing_block_reason_rows,
            (
                f"unknown_state_rows={len(unknown_state_rows)};"
                f"false_ready_rows={len(false_ready_rows)};"
                f"missing_block_reason_rows={len(missing_block_reason_rows)}"
            ),
            "A line can only be export-preview ready after safe file-shape proof and local review control.",
        ),
        (
            "summary_matches_lines",
            len(summary_df.index) <= len(lines_df.index),
            f"summary_rows={len(summary_df.index)};line_rows={len(lines_df.index)}",
            "PO draft export preview summary must not invent packets beyond preview lines.",
        ),
        (
            "source_file_guard",
            all(path.exists() for path in source_paths),
            f"source_files_present={sum(1 for path in source_paths if path.exists())};source_files_expected={len(source_paths)}",
            "PO draft export preview must be built from local review-control and file-shape proof files.",
        ),
    ]
    source_path_text = ";".join(str(path) for path in source_paths)
    return pd.DataFrame(
        [
            {
                "check_utc": export_preview_utc,
                "check": check,
                "status": "ok" if passed else "fail",
                "value": value,
                "notes": notes,
                "source_path": source_path_text,
            }
            for check, passed, value, notes in checks
        ]
    )


def build_po_draft_export_preview(
    root: Path | None = None,
    *,
    export_preview_utc: str | None = None,
    write_outputs: bool = True,
    refresh_review_controls: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    paths = ensure_o_directories(root=root_path)
    observed = export_preview_utc or _utc_now_iso()
    if refresh_review_controls:
        build_po_draft_review_controls(
            root=root_path,
            control_utc=observed,
            write_outputs=write_outputs,
            refresh_construction_summary=True,
        )
    source_df = read_o_contract_df(root_path, "restock_po_draft_file_shape_preview_lines_live")
    controls_df = read_o_contract_df(root_path, "restock_po_draft_review_controls_live")
    lines_df = _build_lines(observed, source_df, controls_df)
    summary_df = _build_summary(observed, lines_df)
    source_paths = [
        root_path / "out" / "systems" / "O" / "live" / "restock_po_draft_file_shape_preview_lines_live.csv",
        root_path / "out" / "systems" / "O" / "live" / "restock_po_draft_review_controls_live.csv",
    ]
    health_df = _build_health(observed, lines_df, summary_df, source_paths)
    if write_outputs:
        lines_df = write_o_contract_df(root_path, "restock_po_draft_export_preview_lines_live", lines_df)
        summary_df = write_o_contract_df(root_path, "restock_po_draft_export_preview_summary_live", summary_df)
        health_df = write_o_contract_df(root_path, "restock_po_draft_export_preview_health", health_df)
        history_dir = paths.history_dir / f"po_draft_export_preview_v1_{observed.replace(':', '').replace('-', '')}"
        history_dir.mkdir(parents=True, exist_ok=True)
        lines_df.to_csv(history_dir / "restock_po_draft_export_preview_lines_live.csv", index=False)
        summary_df.to_csv(history_dir / "restock_po_draft_export_preview_summary_live.csv", index=False)
        health_df.to_csv(history_dir / "restock_po_draft_export_preview_health.csv", index=False)
    return lines_df, summary_df, health_df


def main() -> int:
    lines_df, summary_df, health_df = build_po_draft_export_preview()
    bad_health = health_df[health_df.get("status", "").map(_normalize_text).ne("ok")]
    print(f"po_draft_export_preview_line_rows={len(lines_df.index)}")
    print(f"po_draft_export_preview_summary_rows={len(summary_df.index)}")
    print(f"health_status={'ok' if bad_health.empty else 'fail'}")
    return 0 if bad_health.empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
