from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import ensure_manager_test_mode_dir
from scripts.flows.F.price_list_manager._schemas import (
    BATCH_SCAN_ELIGIBILITY_COLUMNS,
    MANAGER_DECISION_COLUMNS,
    MANAGER_HEALTH_COLUMNS,
    NEXT_ACTION_SKIP_REASON_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
    SUPPLIER_REGISTRY_COLUMNS,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _latest_decision(decisions: pd.DataFrame) -> pd.Series | None:
    if decisions.empty:
        return None
    work = decisions.copy()
    work = work[work.apply(lambda row: any(normalize_text(value) for value in row.values), axis=1)]
    return work.iloc[-1] if not work.empty else None


def _supplier_name(registry: pd.DataFrame, supplier_id: str) -> str:
    match = registry[registry["supplier_id"].map(normalize_text) == supplier_id]
    if match.empty:
        return supplier_id
    return normalize_text(match.iloc[0].get("supplier_name", "")) or supplier_id


def _batch_lookup(batches: pd.DataFrame) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    for _, row in batches.iterrows():
        batch_id = normalize_text(row.get("batch_id", ""))
        if batch_id:
            out[batch_id] = row
    return out


def _reason_table(eligibility: pd.DataFrame) -> pd.DataFrame:
    if eligibility.empty:
        return pd.DataFrame(columns=NEXT_ACTION_SKIP_REASON_COLUMNS)
    skipped = eligibility[eligibility["scan_decision"].map(normalize_text) == "skip"].copy()
    if skipped.empty:
        return pd.DataFrame(columns=NEXT_ACTION_SKIP_REASON_COLUMNS)
    grouped = (
        skipped.groupby(["supplier_id", "decision_reason"], dropna=False)
        .size()
        .reset_index(name="rows")
        .sort_values(["supplier_id", "rows"], ascending=[True, False], kind="stable")
    )
    grouped["rows"] = grouped["rows"].map(str)
    return grouped[NEXT_ACTION_SKIP_REASON_COLUMNS]


def _supplier_totals(eligibility: pd.DataFrame, registry: pd.DataFrame) -> pd.DataFrame:
    if eligibility.empty:
        return pd.DataFrame(columns=["supplier_id", "supplier_name", "scan_rows", "skip_rows", "total_rows"])
    rows: list[dict[str, str]] = []
    for supplier_id, group in eligibility.groupby("supplier_id", dropna=False):
        supplier = normalize_text(supplier_id)
        scan_rows = int((group["scan_decision"].map(normalize_text) == "scan").sum())
        skip_rows = int((group["scan_decision"].map(normalize_text) == "skip").sum())
        rows.append(
            {
                "supplier_id": supplier,
                "supplier_name": _supplier_name(registry, supplier),
                "scan_rows": str(scan_rows),
                "skip_rows": str(skip_rows),
                "total_rows": str(len(group.index)),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["_scan_sort"] = pd.to_numeric(out["scan_rows"], errors="coerce").fillna(0)
    return out.sort_values("_scan_sort", ascending=False, kind="stable").drop(columns=["_scan_sort"])


def _render_markdown(
    *,
    built_at: str,
    decision: pd.Series | None,
    registry: pd.DataFrame,
    batches: pd.DataFrame,
    eligibility: pd.DataFrame,
) -> str:
    totals = _supplier_totals(eligibility, registry)
    reasons = _reason_table(eligibility)
    batch_map = _batch_lookup(batches)

    lines: list[str] = []
    lines.append("# Price List Next Action Report")
    lines.append("")
    lines.append(f"Built at: {built_at}")
    lines.append("")
    lines.append("Live F061 handoff: disabled")
    lines.append("")

    if decision is None:
        lines.append("## Recommendation")
        lines.append("")
        lines.append("- Action: no decision available")
        lines.append("")
    else:
        supplier_id = normalize_text(decision.get("supplier_id", ""))
        batch_id = normalize_text(decision.get("batch_id", ""))
        batch = batch_map.get(batch_id)
        lines.append("## Recommendation")
        lines.append("")
        lines.append(f"- Action: {normalize_text(decision.get('recommended_action', ''))}")
        lines.append(f"- Supplier: {_supplier_name(registry, supplier_id)}")
        lines.append(f"- Batch: {batch_id or '-'}")
        lines.append(f"- Estimated scan rows: {normalize_text(decision.get('estimated_scan_rows', '0'))}")
        lines.append(f"- Estimated skipped rows: {normalize_text(decision.get('estimated_skip_rows', '0'))}")
        lines.append(f"- Reason: {normalize_text(decision.get('reason_code', ''))}")
        lines.append(f"- Safe to hand off to F061: {normalize_text(decision.get('safe_to_handoff_flag', '0'))}")
        if batch is not None:
            lines.append(f"- Source date: {normalize_text(batch.get('source_received_at_utc', ''))}")
        lines.append("")

    lines.append("## Supplier Totals")
    lines.append("")
    if totals.empty:
        lines.append("- No supplier eligibility rows found.")
    else:
        for _, row in totals.iterrows():
            lines.append(
                f"- {normalize_text(row.get('supplier_name', ''))}: scan {normalize_text(row.get('scan_rows', '0'))}, "
                f"skip {normalize_text(row.get('skip_rows', '0'))}, total {normalize_text(row.get('total_rows', '0'))}"
            )
    lines.append("")

    lines.append("## Skip Reasons")
    lines.append("")
    if reasons.empty:
        lines.append("- No skipped rows.")
    else:
        for _, row in reasons.iterrows():
            supplier = _supplier_name(registry, normalize_text(row.get("supplier_id", "")))
            lines.append(
                f"- {supplier}: {normalize_text(row.get('decision_reason', ''))} = {normalize_text(row.get('rows', '0'))}"
            )
    lines.append("")

    lines.append("## Safety")
    lines.append("")
    lines.append("- This report is read-only.")
    lines.append("- It does not start F061.")
    lines.append("- It does not write live scanner inbox files.")
    lines.append("- Queue controls are test-mode only; live F061 handoff still requires explicit approval and a separate apply phase.")
    lines.append("")
    return "\n".join(lines)


def build_next_action_report(root: Path | None = None, *, built_at_utc: str | None = None) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=root)
    built_at = built_at_utc or _utc_now_iso()
    test_dir = paths.test_mode_dir
    eligibility = read_csv(test_dir / "batch_scan_eligibility.csv", BATCH_SCAN_ELIGIBILITY_COLUMNS)
    decisions = read_csv(test_dir / "manager_decisions.csv", MANAGER_DECISION_COLUMNS)
    batches = read_csv(test_dir / "price_list_batches.csv", PRICE_LIST_BATCH_COLUMNS)
    registry = read_csv(test_dir / "supplier_registry.csv", SUPPLIER_REGISTRY_COLUMNS)
    if eligibility.empty:
        raise FileNotFoundError("batch_scan_eligibility.csv is required before building next-action report")

    decision = _latest_decision(decisions)
    report_text = _render_markdown(
        built_at=built_at,
        decision=decision,
        registry=registry,
        batches=batches,
        eligibility=eligibility,
    )
    report_path = test_dir / "next_action_report.md"
    report_path.write_text(report_text, encoding="utf-8")

    reason_counts = _reason_table(eligibility)
    reason_path = test_dir / "next_action_skip_reasons.csv"
    write_csv(reason_path, reason_counts, NEXT_ACTION_SKIP_REASON_COLUMNS)

    health_path = test_dir / "health.csv"
    existing_health = read_csv(health_path, MANAGER_HEALTH_COLUMNS)
    scan_rows = int((eligibility["scan_decision"].map(normalize_text) == "scan").sum())
    skip_rows = int((eligibility["scan_decision"].map(normalize_text) == "skip").sum())
    health_row = pd.DataFrame(
        [
            {
                "check": "next_action_report_reconciliation",
                "status": "ok" if scan_rows + skip_rows == len(eligibility.index) else "fail",
                "value": str(len(eligibility.index)),
                "notes": f"scan_rows={scan_rows};skip_rows={skip_rows};report_path={report_path}",
                "observed_utc": built_at,
                "source_path": str(report_path),
            }
        ]
    )
    health = write_csv(health_path, pd.concat([existing_health, health_row], ignore_index=True), MANAGER_HEALTH_COLUMNS)

    summary = {
        "status": "success",
        "eligibility_rows": int(len(eligibility.index)),
        "scan_rows": scan_rows,
        "skip_rows": skip_rows,
        "report_path": str(report_path),
        "skip_reasons_path": str(reason_path),
        "health_fail_rows": int((health["status"].map(lambda value: normalize_text(value).lower()) == "fail").sum()),
    }
    print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the price-list manager next-action report.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--built-at-utc", default=None)
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    build_next_action_report(root=root, built_at_utc=args.built_at_utc)


if __name__ == "__main__":
    main()
