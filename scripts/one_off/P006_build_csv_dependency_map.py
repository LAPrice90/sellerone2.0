from __future__ import annotations

import argparse
import ast
import csv
import fnmatch
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "project_control" / "DATA_BLUEPRINT_REGISTRY.csv"
DEFAULT_OUTPUT_DIR = ROOT / "out" / "sql_migration"

OUTPUT_COLUMNS = [
    "scanned_at_utc",
    "script_path",
    "operation",
    "line",
    "expression",
    "resolved_path",
    "dataset_id",
    "owner_cycle",
    "canonical_path",
    "classification",
    "migration_status",
    "notes",
]

PROVEN_DATASET_IDS = {
    "A.FEES_FAILED",
    "A.FEES_LATEST",
    "A.INVENTORY_ADJUSTMENTS_LATEST",
    "A.INVENTORY_HISTORY",
    "A.INVENTORY_LEDGER_RAW",
    "A.INVENTORY_SNAPSHOT_LATEST",
    "A.PHASE1_DAILY_INTEL_LATEST",
    "A.PHASE1_FLOOR_TABLE_LATEST",
    "A.INVENTORY_SUMMARIES",
    "A.STOCK_RECEIPTS_LATEST",
    "A.STOCK_EVENTS_RAW",
    "B.CHECKLIST_B",
    "B.TOKEN_COGS_LEDGER",
    "B.ORDER_COGS_FROM_TOKENS",
    "B.ORDER_MASTER",
    "B.PHASE1_SKU_SCOPE",
    "B.ORDERS_MISSING_TOKENS",
    "B.L1_MISSING_FEE_KEYS",
    "B.L3_ORPHANS",
    "B.ORDERS_ALL",
    "B.ORDER_ITEMS_ALL",
    "B.REFUND_TOKEN_EVENTS",
    "B.STOCK_ADJUSTMENT_TOKEN_EVENTS",
    "B.TOKEN_ALLOCATIONS_LIVE",
    "B.TOKEN_EVENTS",
    "B.TOKEN_LEDGER_LIVE",
    "B.FX_RATES_DAILY",
    "B.ORDER_LEDGER_FX",
    "B.FINANCIAL_LEDGER_FX",
    "B.FINANCIAL_EVENTS_LEVEL3_OFFICIAL",
    "B.ORDERS_RAW",
    "B.ORDER_ITEMS_RAW",
    "B.ORDERS_PULLED_LAST_RUN",
    "B.FINANCIAL_EVENTS_LEVEL1",
    "B.FINANCIAL_EVENTS_LEVEL2",
    "B.FINANCIAL_EVENTS_LEVEL3_RAW",
    "B.FINANCIAL_EVENTS_LEVEL3_RAW_DEDUP",
    "B.FINANCIAL_EVENTS_LEVEL3_SUMMARY",
    "B.FINANCIAL_EVENTS_ACCOUNT_LEDGER",
    "B.FINANCIAL_EVENTS_REFUNDS",
    "B.FINANCIAL_EVENTS_REFUNDS_OFFICIAL",
    "B.FINANCIAL_EVENTS_SHIPMENTS",
    "B.FINANCIAL_EVENTS_INBOUND_SUMMARY",
    "B.FINANCIAL_EVENTS_STORAGE",
    "B.FINANCIAL_EVENTS_STORAGE_SUMMARY",
    "B.FINANCIAL_EVENTS_ACCOUNT_SUMMARY",
    "B.L2_VS_L3_DISCREPANCIES",
    "B.VAT_COUNTRY_MODEL",
    "B.FEE_COUNTRY_MODEL",
    "B.ORDERS_SHEET_ORDERS",
    "E.SKU_ROI_SNAPSHOT",
    "E.SKU_ROI_SNAPSHOT_BY_COUNTRY",
    "E.SKU_PERFORMANCE_SUMMARY",
    "E.SKU_RESTOCK_SIGNALS",
    "E.SKU_SALES_VELOCITY",
    "E.STUDY_REPORT",
    "H.HOS_DAILY_MARKET_SNAPSHOT_LATEST",
    "H.HOS_DAILY_MARKET_HISTORY",
    "H.LISTING_OFFER_SNAPSHOT_LATEST",
    "H.LISTING_OFFER_SELLER_SNAPSHOT_LATEST",
    "H.LISTING_OFFER_HISTORY",
    "H.PHASE1_RUNTIME_FLOOR_SNAPSHOT_LATEST",
    "H.SELLER_PROFILES",
    "H.SELLER_OF_INTEREST",
    "SYS.SYSTEM_HEALTH_CHECKLIST",
    "SYS.INBOUND_SHIPMENT_CONTENTS",
    "SYS.PRODUCT_DB_PREVIEW",
    "F.NEW_PRODUCT_REVIEW_PASS_PACK",
    "F.NEW_PRODUCT_REVIEW_NEAR_MISS_PACK",
    "F.NEW_PRODUCT_REVIEW_SUMMARY",
    "F.FEEDER_REVIEW_EVENTS",
    "O.FEEDER_REVIEW_UI_DRAFTS",
}

PROVEN_UNREGISTERED_PATHS = {
    "out/token_movement_log.csv": "B token movement pilot proven",
    "out/token_daily_checklist.csv": "B token checklist pilot proven",
    "out/sku_roi_snapshot_uk.csv": "E ROI UK compatibility export proven",
    "out/sku_roi_snapshot_non_uk.csv": "E ROI non-UK compatibility export proven",
    "out/sales_truth_sku_30d_latest.csv": "E sales truth local output proven",
    "out/sales_truth_reconciliation_latest.csv": "E sales truth reconciliation local output proven",
    "out/sku_daily_sales_truth_latest.csv": "E daily sales truth local output proven",
}

PROVEN_SCHEMA_CONTRACT_IDS = {
    "F.SUPPLIER_PRICE_LIST_UNIVERSAL_LIVE",
    "F.SUPPLIER_PRICE_LIST_UNIVERSAL_HOLDS",
    "F.SUPPLIER_PRICE_LIST_ACTIVE_RUN",
    "F.SUPPLIER_PRICE_LIST_RUN_STATE",
    "F.SUPPLIER_PRICE_LIST_QUEUE_STATE",
    "F.SUPPLIER_PRICE_LIST_HEALTH",
    "F.FEEDER_CANDIDATE_INTAKE_LIVE",
    "F.FEEDER_CANDIDATE_INTAKE_HOLDS",
    "F.FEEDER_INTAKE_HEALTH",
    "F.FEEDER_CANDIDATE_NORMALIZED_LIVE",
    "F.FEEDER_CANDIDATE_FIRST_PASS_CLASSIFICATION_LIVE",
    "F.FEEDER_CANDIDATE_FIRST_PASS_HOLDS",
    "F.FEEDER_CLASSIFICATION_HEALTH",
    "F.FEEDER_SHARED_PASS_LOGIC_LIVE",
    "F.FEEDER_SHARED_PASS_LOGIC_HOLDS",
    "F.FEEDER_SHARED_PASS_LOGIC_HEALTH",
    "F.FEEDER_CANDIDATE_RECOMMENDATIONS_LIVE",
    "F.FEEDER_APPROVAL_QUEUE_LIVE",
    "F.FEEDER_APPROVAL_DECISIONS_LOG",
    "F.FEEDER_APPROVAL_HEALTH",
    "F.FEEDER_PO_HANDOFF_READY_LIVE",
    "F.FEEDER_PO_HANDOFF_HOLDS",
    "F.FEEDER_PO_HANDOFF_HEALTH",
    "F.FEEDER_LEGACY_FIRST_CHECKS_LIVE",
    "F.F_SCREENING_ROW_STATE_LIVE",
    "F.FEEDER_LEGACY_SCRAPE_EVIDENCE_LIVE",
    "F.FEEDER_LEGACY_CHART_DAILY_RAW_LIVE",
    "F.FEEDER_LEGACY_SECOND_CHECKS_LIVE",
    "F.FEEDER_LEGACY_BOT_STATUS_LIVE",
    "F.FEEDER_LEGACY_SHEET_HEALTH",
    "F.FEEDER_BACKTEST_POLICY_LIVE",
    "F.FEEDER_BACKTEST_POLICY_UPDATE_EVENTS",
    "F.FEEDER_BACKTEST_INPUT_VIEW_LIVE",
    "F.FEEDER_BACKTEST_REPLAY_DAILY_LIVE",
    "F.FEEDER_BACKTEST_SUMMARY_LIVE",
    "F.FEEDER_BACKTEST_HEALTH",
    "O.PRODUCT_DB_OPERATOR_VIEW",
    "O.PRODUCT_DB_EDIT_EVENTS",
    "O.PRODUCT_DB_EDIT_HOLDS",
    "O.RESTOCK_SOURCE_VIEW",
    "O.RESTOCK_RECOMMENDATIONS_LIVE",
    "O.RESTOCK_REVIEW_QUEUE",
    "O.SUPPLIER_COST_SNAPSHOT_TEST",
    "O.REORDER_INPUT_COVERAGE_REPORT",
    "O.REORDER_INPUT_COVERAGE_BY_SUPPLIER",
    "O.REORDER_INPUT_BLOCK_REASONS",
    "O.RESTOCK_DECISION_EVENTS",
    "O.RESTOCK_DECISIONS_LOG",
    "O.PURCHASE_ORDERS_LIVE",
    "O.PURCHASE_ORDER_LINES_LIVE",
    "O.PURCHASE_ORDER_DRAFT_HOLDS",
    "O.RECEIVING_EVENTS",
    "O.RECEIVING_EVENTS_INBOX",
    "O.RECEIVING_EVENT_HOLDS",
    "O.ORDERED_STOCK_STATE",
    "O.SEND_TO_AMAZON_QUEUE",
    "O.SEND_TO_AMAZON_HANDOFF_EVENTS",
    "O.SEND_TO_AMAZON_HANDOFF_LOG",
    "O.SEND_TO_AMAZON_HANDOFF_HOLDS",
}

PROVEN_DATASET_IDS.update(PROVEN_SCHEMA_CONTRACT_IDS)

SKIP_DIR_PARTS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "out",
    "reference",
    ".venv",
    "venv",
}


@dataclass(frozen=True)
class RegistryRow:
    dataset_id: str
    owner_cycle: str
    canonical_path: str
    canonical_norm: str
    basename: str
    match_patterns: tuple[str, ...]


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _norm_path(value: str) -> str:
    text = str(value or "").replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    return text


def _load_registry(path: Path = REGISTRY_PATH) -> list[RegistryRow]:
    rows: list[RegistryRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            canonical = _norm_path(row.get("canonical_path", ""))
            if not canonical or not canonical.lower().endswith(".csv"):
                continue
            mirror_text = str(row.get("allowed_mirror_paths", "") or "")
            patterns = [canonical]
            for token in re.split(r"[|;]", mirror_text):
                mirror = _norm_path(token)
                if mirror and (mirror.lower().endswith(".csv") or "*" in mirror):
                    patterns.append(mirror)
            rows.append(
                RegistryRow(
                    dataset_id=str(row.get("dataset_id", "")).strip(),
                    owner_cycle=str(row.get("owner_cycle", "")).strip(),
                    canonical_path=canonical,
                    canonical_norm=canonical.lower(),
                    basename=Path(canonical).name.lower(),
                    match_patterns=tuple(dict.fromkeys(pattern.lower() for pattern in patterns)),
                )
            )
    rows.extend(_schema_contract_registry_rows())
    return rows


def _schema_contract_registry_rows() -> list[RegistryRow]:
    rows: list[RegistryRow] = []
    try:
        from scripts.flows.F._schemas import get_f_output_contracts
        from scripts.flows.O._schemas import get_o_output_contracts
    except Exception:
        return rows

    for prefix, owner, contracts in (
        ("F", "F", get_f_output_contracts()),
        ("O", "O", get_o_output_contracts()),
    ):
        for contract_name, contract in contracts.items():
            canonical = _norm_path(contract.rel_path)
            if not canonical.lower().endswith(".csv"):
                continue
            dataset_id = f"{prefix}.{contract_name.upper()}"
            rows.append(
                RegistryRow(
                    dataset_id=dataset_id,
                    owner_cycle=owner,
                    canonical_path=canonical,
                    canonical_norm=canonical.lower(),
                    basename=Path(canonical).name.lower(),
                    match_patterns=(canonical.lower(),),
                )
            )
    return rows


def _is_skipped(path: Path) -> bool:
    parts = set(path.parts)
    return bool(parts & SKIP_DIR_PARTS)


def _python_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        target = path if path.is_absolute() else ROOT / path
        if target.is_file() and target.suffix == ".py":
            files.append(target)
            continue
        if target.is_dir():
            for candidate in target.rglob("*.py"):
                if not _is_skipped(candidate):
                    files.append(candidate)
    return sorted(set(files))


def _literal_value(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def _name_of(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name_of(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _eval_path_expr(node: ast.AST, constants: dict[str, str]) -> str:
    literal = _literal_value(node)
    if literal:
        return _norm_path(literal)
    if isinstance(node, ast.Name):
        return constants.get(node.id, "")
    if isinstance(node, ast.Call) and _name_of(node.func) == "Path" and node.args:
        return _eval_path_expr(node.args[0], constants)
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                parts.append("*")
        return _norm_path("".join(parts))
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _eval_path_expr(node.left, constants)
        right = _eval_path_expr(node.right, constants)
        if left and right:
            return _norm_path(f"{left.rstrip('/')}/{right.lstrip('/')}")
    return ""


def _module_constants(tree: ast.Module) -> dict[str, str]:
    constants: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        value = _eval_path_expr(node.value, constants)
        if value:
            constants[target.id] = value
    return constants


def _call_operation(node: ast.Call) -> str:
    func_name = _name_of(node.func)
    if func_name.endswith("read_csv"):
        return "read_csv"
    if func_name.endswith("to_csv"):
        return "to_csv"
    return ""


def _call_path_arg(node: ast.Call, operation: str) -> ast.AST | None:
    if operation == "read_csv":
        if node.args:
            return node.args[0]
        for keyword in node.keywords:
            if keyword.arg in {"filepath_or_buffer", "path"}:
                return keyword.value
    if operation == "to_csv":
        if node.args:
            return node.args[0]
        for keyword in node.keywords:
            if keyword.arg in {"path_or_buf", "path"}:
                return keyword.value
    return None


def _match_registry(path_text: str, registry: list[RegistryRow]) -> RegistryRow | None:
    norm = _norm_path(path_text).lower()
    if not norm:
        return None
    for row in registry:
        if norm == row.canonical_norm:
            return row
    for row in registry:
        if norm.endswith(row.canonical_norm):
            return row
    for row in registry:
        for pattern in row.match_patterns:
            if "*" not in pattern:
                continue
            if fnmatch.fnmatch(norm, pattern) or fnmatch.fnmatch(norm, f"*{pattern}"):
                return row
    basename = Path(norm).name
    candidates = [row for row in registry if row.basename == basename]
    if len(candidates) == 1:
        return candidates[0]
    return None


def _declared_csv_path_nodes(tree: ast.Module) -> list[ast.AST]:
    nodes: list[ast.AST] = []
    for node in ast.walk(tree):
        path_text = ""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            path_text = _norm_path(node.value)
        elif isinstance(node, ast.JoinedStr):
            path_text = _eval_path_expr(node, {})
        if not path_text.lower().endswith(".csv"):
            continue
        if "/" not in path_text and "\\" not in path_text and not path_text.lower().startswith("out/"):
            continue
        nodes.append(node)
    return nodes


def _classification(operation: str, path_text: str, match: RegistryRow | None) -> str:
    if match is not None:
        if operation == "to_csv":
            return "registered_writer_or_export"
        return "registered_reader"
    if not path_text:
        return "dynamic_path_unresolved"
    if _norm_path(path_text).lower().endswith(".csv"):
        return "unregistered_csv_path"
    return "non_csv_or_dynamic"


def _migration_status(path_text: str, match: RegistryRow | None) -> tuple[str, str]:
    norm = _norm_path(path_text)
    if match and match.dataset_id in PROVEN_DATASET_IDS:
        return "sql_primary_pilot_proven", ""
    if norm in PROVEN_UNREGISTERED_PATHS:
        return "sql_primary_pilot_proven", PROVEN_UNREGISTERED_PATHS[norm]
    if match:
        return "csv_dependency_remaining", ""
    return "needs_review", ""


def build_rows(scan_paths: list[Path], registry_path: Path = REGISTRY_PATH) -> list[dict[str, str]]:
    registry = _load_registry(registry_path)
    scanned_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows: list[dict[str, str]] = []
    for path in _python_files(scan_paths):
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue
        constants = _module_constants(tree)
        csv_call_path_node_ids: set[int] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            operation = _call_operation(node)
            if not operation:
                continue
            path_arg = _call_path_arg(node, operation)
            if path_arg is not None:
                csv_call_path_node_ids.add(id(path_arg))
        seen_declared: set[tuple[int, str]] = set()
        for node in _declared_csv_path_nodes(tree):
            if id(node) in csv_call_path_node_ids:
                continue
            resolved = _eval_path_expr(node, constants)
            if not resolved:
                continue
            dedupe_key = (getattr(node, "lineno", 0), resolved)
            if dedupe_key in seen_declared:
                continue
            seen_declared.add(dedupe_key)
            match = _match_registry(resolved, registry)
            status, note = _migration_status(resolved, match)
            rows.append(
                {
                    "scanned_at_utc": scanned_at,
                    "script_path": _display_path(path),
                    "operation": "declared_csv_path",
                    "line": str(getattr(node, "lineno", "")),
                    "expression": ast.unparse(node),
                    "resolved_path": resolved,
                    "dataset_id": match.dataset_id if match else "",
                    "owner_cycle": match.owner_cycle if match else "",
                    "canonical_path": match.canonical_path if match else "",
                    "classification": _classification("read_csv", resolved, match),
                    "migration_status": status,
                    "notes": note,
                }
            )
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            operation = _call_operation(node)
            if not operation:
                continue
            path_arg = _call_path_arg(node, operation)
            resolved = _eval_path_expr(path_arg, constants) if path_arg is not None else ""
            match = _match_registry(resolved, registry)
            status, note = _migration_status(resolved, match)
            rows.append(
                {
                    "scanned_at_utc": scanned_at,
                    "script_path": _display_path(path),
                    "operation": operation,
                    "line": str(getattr(node, "lineno", "")),
                    "expression": ast.unparse(path_arg) if path_arg is not None else "",
                    "resolved_path": resolved,
                    "dataset_id": match.dataset_id if match else "",
                    "owner_cycle": match.owner_cycle if match else "",
                    "canonical_path": match.canonical_path if match else "",
                    "classification": _classification(operation, resolved, match),
                    "migration_status": status,
                    "notes": note,
                }
            )
    return rows


def _validate_rows(rows: list[dict[str, str]]) -> None:
    for index, row in enumerate(rows, start=1):
        missing = [col for col in OUTPUT_COLUMNS if col not in row]
        if missing:
            raise ValueError(f"row {index} missing columns: {missing}")
        for col in OUTPUT_COLUMNS:
            if row[col] is None:
                raise ValueError(f"row {index} column {col} is None")


def write_outputs(rows: list[dict[str, str]], output_dir: Path) -> tuple[Path, Path, dict[str, Any]]:
    _validate_rows(rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "csv_dependency_map.csv"
    summary_path = output_dir / "csv_dependency_map_summary.json"
    with report_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    summary: dict[str, Any] = {
        "status": "success",
        "row_count": len(rows),
        "registered_dependency_count": sum(1 for row in rows if row["dataset_id"]),
        "unresolved_dynamic_count": sum(1 for row in rows if row["classification"] == "dynamic_path_unresolved"),
        "unregistered_csv_count": sum(1 for row in rows if row["classification"] == "unregistered_csv_path"),
        "sql_primary_pilot_proven_count": sum(
            1 for row in rows if row["migration_status"] == "sql_primary_pilot_proven"
        ),
        "csv_dependency_remaining_count": sum(
            1 for row in rows if row["migration_status"] == "csv_dependency_remaining"
        ),
        "report_path": _display_path(report_path),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")
    return report_path, summary_path, summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the SQL migration CSV dependency map.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for report outputs.")
    parser.add_argument(
        "--scan",
        action="append",
        default=[],
        help="File or directory to scan. Defaults to scripts/.",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scan_paths = [Path(item) for item in args.scan] if args.scan else [Path("scripts")]
    rows = build_rows(scan_paths)
    report_path, summary_path, summary = write_outputs(rows, Path(args.output_dir))
    if args.format == "json":
        print(json.dumps({"report_path": str(report_path), "summary_path": str(summary_path), **summary}, indent=2))
    else:
        for key in [
            "status",
            "row_count",
            "registered_dependency_count",
            "sql_primary_pilot_proven_count",
            "csv_dependency_remaining_count",
            "unresolved_dynamic_count",
            "unregistered_csv_count",
        ]:
            print(f"{key}={summary[key]}")
        print(f"report_path={_display_path(report_path)}")
        print(f"summary_path={_display_path(summary_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
