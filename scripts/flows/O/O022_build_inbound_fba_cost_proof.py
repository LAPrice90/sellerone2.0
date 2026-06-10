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

from scripts.flows.O._contract_io import write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories


WEAK_INBOUND_COST_CONFIDENCE_STATES = {
    "",
    "missing",
    "unknown",
    "weak",
    "not_yet_proven",
    "missing_inbound_cost_confidence",
    "unsupported_currency",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _num(value: object) -> float | None:
    text = _normalize_text(value)
    if text == "":
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _int_text(value: int | float | None) -> str:
    if value is None:
        return "0"
    return str(int(value))


def _shipment_key(row: pd.Series) -> str:
    for column in ("inbound_shipment_id", "parsed_fba_shipment_id", "shipment_id"):
        value = _normalize_text(row.get(column, ""))
        if value:
            return value
    return ""


def _safe_sku_cost_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    required = {"sku", "received_qty", "currency", "allocated_total"}
    if not required.issubset(df.columns):
        return pd.DataFrame()
    work = df.copy()
    work["_sku"] = work["sku"].map(_normalize_text)
    work["_currency"] = work["currency"].map(lambda value: _normalize_text(value).upper())
    work["_received_qty"] = work["received_qty"].map(_num)
    work["_allocated_total"] = work["allocated_total"].map(_num)
    return work[
        (work["_sku"] != "")
        & (work["_currency"] == "GBP")
        & (work["_received_qty"].fillna(0) > 0)
        & (work["_allocated_total"].fillna(0).abs() > 0)
    ].copy()


def _restock_cost_counts(restock_df: pd.DataFrame) -> tuple[int, int, int]:
    if restock_df.empty:
        return 0, 0, 0
    restock_rows = len(restock_df.index)
    confidence = (
        restock_df["inbound_cost_confidence"].map(lambda value: _normalize_text(value).lower())
        if "inbound_cost_confidence" in restock_df.columns
        else pd.Series([""] * restock_rows, index=restock_df.index)
    )
    cost = (
        pd.to_numeric(restock_df["expected_inbound_cost_per_unit_gbp"], errors="coerce").fillna(0.0)
        if "expected_inbound_cost_per_unit_gbp" in restock_df.columns
        else pd.Series([0.0] * restock_rows, index=restock_df.index, dtype="float64")
    )
    safe_rows = int(((confidence == "sku_allocated") & (cost > 0)).sum())
    missing_rows = int((confidence.isin(WEAK_INBOUND_COST_CONFIDENCE_STATES) | (cost <= 0)).sum())
    return restock_rows, safe_rows, missing_rows


def build_inbound_fba_cost_proof(root: Path | str | None = None, *, proof_utc: str | None = None) -> pd.DataFrame:
    root_path = Path(root) if root is not None else Path(__file__).resolve().parents[3]
    ensure_o_directories(root=root_path)
    observed = proof_utc or _utc_now_iso()

    paths = {
        "inbound_cost_events": root_path / "out" / "inbound_cost_events.csv",
        "inbound_costs_allocated": root_path / "out" / "inbound_costs_allocated.csv",
        "inbound_costs_allocated_sku": root_path / "out" / "inbound_costs_allocated_sku.csv",
        "inbound_costs_unallocated": root_path / "out" / "inbound_costs_unallocated.csv",
        "transaction_expense_allocations": root_path / "out" / "transaction_expense_allocations.csv",
        "restock_source_view": root_path / "out" / "systems" / "O" / "live" / "restock_source_view.csv",
    }
    inbound_events = _read_csv(paths["inbound_cost_events"])
    allocated = _read_csv(paths["inbound_costs_allocated"])
    sku_allocated = _read_csv(paths["inbound_costs_allocated_sku"])
    unallocated = _read_csv(paths["inbound_costs_unallocated"])
    txn_alloc = _read_csv(paths["transaction_expense_allocations"])
    restock = _read_csv(paths["restock_source_view"])

    event_linked = int(sum(1 for _, row in inbound_events.iterrows() if _shipment_key(row)))
    event_unlinked = max(len(inbound_events.index) - event_linked, 0)
    safe_sku_rows = _safe_sku_cost_rows(sku_allocated)
    restock_rows, restock_safe, restock_missing = _restock_cost_counts(restock)
    txn_linked = 0
    if not txn_alloc.empty and {"status", "allocated_sku"}.issubset(txn_alloc.columns):
        txn_linked = int(
            (
                txn_alloc["status"].map(lambda value: _normalize_text(value).lower()).eq("allocated")
                & txn_alloc["allocated_sku"].map(_normalize_text).ne("")
            ).sum()
        )

    def row(
        *,
        check_name: str,
        status: str,
        proof_state: str,
        safe: bool,
        source_rows: int,
        linked_rows: int,
        unlinked_rows: int,
        source_path: Path,
        message: str,
        notes: str = "",
    ) -> dict[str, str]:
        return {
            "proof_utc": observed,
            "check_name": check_name,
            "status": status,
            "proof_state": proof_state,
            "safe_for_profit_use": "1" if safe else "0",
            "source_rows": _int_text(source_rows),
            "linked_rows": _int_text(linked_rows),
            "unlinked_rows": _int_text(unlinked_rows),
            "restock_rows": _int_text(restock_rows),
            "restock_rows_with_sku_cost": _int_text(restock_safe),
            "restock_rows_missing_sku_cost": _int_text(restock_missing),
            "source_path": str(source_path),
            "proof_message": message,
            "notes": notes,
        }

    rows = [
        row(
            check_name="inbound_cost_events",
            status="ok" if event_linked else ("warn" if len(inbound_events.index) else "not_checked"),
            proof_state="shipment_link_present" if event_linked else "inbound_cost_events_unlinked",
            safe=False,
            source_rows=len(inbound_events.index),
            linked_rows=event_linked,
            unlinked_rows=event_unlinked,
            source_path=paths["inbound_cost_events"],
            message=(
                "Inbound/FBA cost rows exist but do not carry a shipment link."
                if event_unlinked
                else "Inbound/FBA cost rows carry shipment links."
            ),
        ),
        row(
            check_name="shipment_cost_allocation",
            status="ok" if len(allocated.index) else "warn",
            proof_state="shipment_cost_allocated" if len(allocated.index) else "no_shipment_cost_allocation",
            safe=False,
            source_rows=len(allocated.index),
            linked_rows=len(allocated.index),
            unlinked_rows=len(unallocated.index),
            source_path=paths["inbound_costs_allocated"],
            message=(
                "Shipment-level inbound/FBA cost allocation exists."
                if len(allocated.index)
                else "No shipment-level inbound/FBA cost allocation exists yet."
            ),
            notes=f"unallocated_rows={len(unallocated.index)}",
        ),
        row(
            check_name="sku_cost_allocation",
            status="ok" if len(safe_sku_rows.index) else "warn",
            proof_state="sku_level_cost_proof_available" if len(safe_sku_rows.index) else "sku_level_cost_proof_missing",
            safe=bool(len(safe_sku_rows.index)),
            source_rows=len(sku_allocated.index),
            linked_rows=len(safe_sku_rows.index),
            unlinked_rows=0,
            source_path=paths["inbound_costs_allocated_sku"],
            message=(
                "SKU-level inbound/FBA cost allocation can be used by O."
                if len(safe_sku_rows.index)
                else "No SKU-level inbound/FBA cost allocation is available for O to use."
            ),
        ),
        row(
            check_name="transaction_expense_allocation",
            status="ok" if txn_linked else ("warn" if len(txn_alloc.index) else "not_checked"),
            proof_state="transaction_expense_sku_link_available" if txn_linked else "transaction_expense_sku_link_missing",
            safe=bool(txn_linked),
            source_rows=len(txn_alloc.index),
            linked_rows=txn_linked,
            unlinked_rows=max(len(txn_alloc.index) - txn_linked, 0),
            source_path=paths["transaction_expense_allocations"],
            message=(
                "Transaction expense allocations include SKU links."
                if txn_linked
                else "Transaction expense allocations do not include SKU links for inbound/FBA cost use."
            ),
        ),
        row(
            check_name="restock_source_attachment",
            status="ok" if restock_rows and restock_missing == 0 else ("warn" if restock_rows else "not_checked"),
            proof_state="all_restock_rows_have_sku_cost" if restock_rows and restock_missing == 0 else "restock_rows_missing_sku_cost",
            safe=bool(restock_rows and restock_missing == 0),
            source_rows=len(restock.index),
            linked_rows=restock_safe,
            unlinked_rows=restock_missing,
            source_path=paths["restock_source_view"],
            message=(
                "All O restock rows have SKU-level inbound/FBA cost proof."
                if restock_rows and restock_missing == 0
                else "O restock rows still need SKU-level inbound/FBA cost proof before profit is clean."
            ),
        ),
    ]
    out_df = pd.DataFrame(rows)
    return write_o_contract_df(root_path, "restock_inbound_fba_cost_proof_live", out_df)


def main() -> int:
    out_df = build_inbound_fba_cost_proof()
    bad = out_df[out_df["status"].isin({"warn", "fail"})]
    restock_row = out_df[out_df["check_name"] == "restock_source_attachment"]
    restock_safe = restock_row.iloc[0]["restock_rows_with_sku_cost"] if not restock_row.empty else "0"
    restock_missing = restock_row.iloc[0]["restock_rows_missing_sku_cost"] if not restock_row.empty else "0"
    print(f"proof_rows={len(out_df.index)}")
    print(f"restock_rows_with_sku_cost={restock_safe}")
    print(f"restock_rows_missing_sku_cost={restock_missing}")
    print(f"proof_status={'warn' if not bad.empty else 'ok'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
