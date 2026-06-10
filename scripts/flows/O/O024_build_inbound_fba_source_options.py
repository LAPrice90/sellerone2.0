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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value: object) -> str:
    return str(value or "").strip()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _shipment_key(row: pd.Series) -> str:
    for column in ("inbound_shipment_id", "parsed_fba_shipment_id", "shipment_id"):
        value = _text(row.get(column, ""))
        if value:
            return value
    return ""


def _safe_sku_cost_rows(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    required = {"sku", "received_qty", "currency", "allocated_total"}
    if not required.issubset(df.columns):
        return 0
    work = df.copy()
    qty = pd.to_numeric(work["received_qty"], errors="coerce").fillna(0)
    allocated = pd.to_numeric(work["allocated_total"], errors="coerce").fillna(0)
    sku = work["sku"].map(_text)
    currency = work["currency"].map(lambda value: _text(value).upper())
    return int(((sku != "") & (currency == "GBP") & (qty > 0) & (allocated.abs() > 0)).sum())


def _allocated_transaction_sku_rows(df: pd.DataFrame) -> int:
    if df.empty or not {"status", "allocated_sku"}.issubset(df.columns):
        return 0
    return int(
        (
            df["status"].map(lambda value: _text(value).lower()).eq("allocated")
            & df["allocated_sku"].map(_text).ne("")
        ).sum()
    )


def _row(
    *,
    proof_utc: str,
    route_id: str,
    route_name: str,
    route_class: str,
    status: str,
    source_rows: int,
    linked_rows: int,
    safe_for_profit_use: bool,
    needs_luke_decision: bool,
    route_message: str,
    next_step: str,
    source_path: Path | str,
    notes: str = "",
) -> dict[str, str]:
    return {
        "proof_utc": proof_utc,
        "route_id": route_id,
        "route_name": route_name,
        "route_class": route_class,
        "status": status,
        "source_rows": str(source_rows),
        "linked_rows": str(linked_rows),
        "safe_for_profit_use": "1" if safe_for_profit_use else "0",
        "needs_luke_decision": "1" if needs_luke_decision else "0",
        "route_message": route_message,
        "next_step": next_step,
        "source_path": str(source_path),
        "notes": notes,
    }


def build_inbound_fba_source_options(
    root: Path | str | None = None,
    *,
    proof_utc: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else Path(__file__).resolve().parents[3]
    ensure_o_directories(root=root_path)
    observed = proof_utc or _utc_now_iso()
    out = root_path / "out"

    paths = {
        "inbound_cost_events": out / "inbound_cost_events.csv",
        "inbound_shipment_contents": out / "inbound_shipment_contents.csv",
        "inbound_costs_allocated_sku": out / "inbound_costs_allocated_sku.csv",
        "transaction_expense_allocations": out / "transaction_expense_allocations.csv",
        "inbound_history": out / "inbound_history.csv",
        "financial_events_inbound_summary": out / "financial_events_inbound_summary.csv",
    }
    inbound_events = _read_csv(paths["inbound_cost_events"])
    shipment_contents = _read_csv(paths["inbound_shipment_contents"])
    sku_allocated = _read_csv(paths["inbound_costs_allocated_sku"])
    txn_alloc = _read_csv(paths["transaction_expense_allocations"])
    inbound_history = _read_csv(paths["inbound_history"])
    inbound_summary = _read_csv(paths["financial_events_inbound_summary"])

    event_linked = int(sum(1 for _, row in inbound_events.iterrows() if _shipment_key(row)))
    content_links = 0
    if not shipment_contents.empty and {"inbound_shipment_id", "sku"}.issubset(shipment_contents.columns):
        content_links = int(
            (
                shipment_contents["inbound_shipment_id"].map(_text).ne("")
                & shipment_contents["sku"].map(_text).ne("")
            ).sum()
        )
    safe_sku_rows = _safe_sku_cost_rows(sku_allocated)
    txn_sku_rows = _allocated_transaction_sku_rows(txn_alloc)
    inbound_history_rows = len(inbound_history.index)
    inbound_summary_rows = len(inbound_summary.index)

    rows = [
        _row(
            proof_utc=observed,
            route_id="direct_fee_event_shipment_link",
            route_name="Fee event has shipment ID",
            route_class="direct",
            status="safe" if event_linked else "missing",
            source_rows=len(inbound_events.index),
            linked_rows=event_linked,
            safe_for_profit_use=bool(event_linked),
            needs_luke_decision=False,
            route_message=(
                "Inbound/FBA fee rows carry shipment IDs and can join to shipment contents."
                if event_linked
                else "Inbound/FBA fee rows exist, but no fee row carries a shipment ID."
            ),
            next_step="join_fee_events_to_shipment_contents" if event_linked else "keep_blocked_no_direct_fee_link",
            source_path=paths["inbound_cost_events"],
        ),
        _row(
            proof_utc=observed,
            route_id="shipment_contents_sku_link",
            route_name="Shipment contents can link shipment to SKU",
            route_class="direct_dependency",
            status="available_waiting_fee_link" if content_links else "missing",
            source_rows=len(shipment_contents.index),
            linked_rows=content_links,
            safe_for_profit_use=False,
            needs_luke_decision=False,
            route_message=(
                "Shipment content rows have shipment-to-SKU links, but they need fee rows with matching shipment IDs."
                if content_links
                else "No shipment-to-SKU content rows are available."
            ),
            next_step="wait_for_fee_event_shipment_link",
            source_path=paths["inbound_shipment_contents"],
        ),
        _row(
            proof_utc=observed,
            route_id="sku_cost_allocation_file",
            route_name="SKU-level inbound/FBA allocation file",
            route_class="direct",
            status="safe" if safe_sku_rows else "missing",
            source_rows=len(sku_allocated.index),
            linked_rows=safe_sku_rows,
            safe_for_profit_use=bool(safe_sku_rows),
            needs_luke_decision=False,
            route_message=(
                "SKU-level GBP inbound/FBA allocation rows exist."
                if safe_sku_rows
                else "No SKU-level GBP inbound/FBA allocation rows exist."
            ),
            next_step="attach_sku_cost_to_o_rows" if safe_sku_rows else "keep_blocked_no_sku_cost_allocation",
            source_path=paths["inbound_costs_allocated_sku"],
        ),
        _row(
            proof_utc=observed,
            route_id="transaction_expense_sku_allocation",
            route_name="Transaction expense has allocated SKU",
            route_class="direct",
            status="safe" if txn_sku_rows else "missing",
            source_rows=len(txn_alloc.index),
            linked_rows=txn_sku_rows,
            safe_for_profit_use=bool(txn_sku_rows),
            needs_luke_decision=False,
            route_message=(
                "Transaction expense rows include SKU allocation."
                if txn_sku_rows
                else "Transaction expense rows exist but do not include allocated SKUs for this cost route."
            ),
            next_step="attach_transaction_expense_sku_cost" if txn_sku_rows else "keep_blocked_no_transaction_sku_link",
            source_path=paths["transaction_expense_allocations"],
        ),
        _row(
            proof_utc=observed,
            route_id="inbound_history_proxy",
            route_name="Inbound history quantity proxy",
            route_class="protected_estimate",
            status="protected_not_automatic" if inbound_history_rows else "missing",
            source_rows=inbound_history_rows,
            linked_rows=inbound_history_rows,
            safe_for_profit_use=False,
            needs_luke_decision=bool(inbound_history_rows),
            route_message="Inbound quantity history exists, but it is not cost proof and cannot set profit automatically.",
            next_step="needs_user_policy_if_used",
            source_path=paths["inbound_history"],
        ),
        _row(
            proof_utc=observed,
            route_id="inbound_fee_average_policy",
            route_name="Average inbound/FBA fee policy",
            route_class="protected_policy",
            status="protected_not_automatic" if inbound_summary_rows else "missing",
            source_rows=inbound_summary_rows,
            linked_rows=0,
            safe_for_profit_use=False,
            needs_luke_decision=bool(inbound_summary_rows),
            route_message="Inbound/FBA fee totals exist, but averaging or spreading them across SKUs is a policy choice.",
            next_step="needs_user_policy_if_used",
            source_path=paths["financial_events_inbound_summary"],
        ),
        _row(
            proof_utc=observed,
            route_id="live_source_repair_or_fetch",
            route_name="Live source repair or Amazon fetch",
            route_class="protected_fetch",
            status="protected_not_automatic",
            source_rows=0,
            linked_rows=0,
            safe_for_profit_use=False,
            needs_luke_decision=True,
            route_message="Fetching or repairing source facts is protected and is not part of this local O task.",
            next_step="needs_user_approval_for_live_fetch_or_source_repair",
            source_path="protected",
        ),
    ]
    options_df = write_o_contract_df(
        root_path,
        "restock_inbound_fba_source_options_live",
        pd.DataFrame(rows),
    )

    direct_safe = int(
        (
            options_df["route_class"].isin(["direct", "direct_dependency"])
            & options_df["safe_for_profit_use"].eq("1")
        ).sum()
    )
    protected = int(options_df["needs_luke_decision"].eq("1").sum())
    health_status = "ok" if direct_safe else "warn"
    health_rows = [
        {
            "proof_utc": observed,
            "check": "direct_safe_routes",
            "status": health_status,
            "value": f"direct_safe_routes={direct_safe};protected_routes={protected}",
            "notes": "Only direct linked shipment/SKU cost routes can make inbound/FBA profit proof clean.",
            "source_path": ";".join(str(path) for path in paths.values()),
        },
        {
            "proof_utc": observed,
            "check": "protected_routes",
            "status": "warn" if protected else "ok",
            "value": f"protected_routes={protected}",
            "notes": "Protected routes need Luke before O can use them for profit truth.",
            "source_path": "out/financial_events_inbound_summary.csv;out/inbound_history.csv;protected",
        },
        {
            "proof_utc": observed,
            "check": "buy_safety",
            "status": "ok",
            "value": "safe_for_profit_use_from_protected_routes=0",
            "notes": "No protected or estimated route is treated as clean profit proof.",
            "source_path": "out/systems/O/live/restock_inbound_fba_source_options_live.csv",
        },
    ]
    health_df = write_o_contract_df(
        root_path,
        "restock_inbound_fba_source_options_health",
        pd.DataFrame(health_rows),
    )
    return options_df, health_df


def main() -> int:
    options_df, health_df = build_inbound_fba_source_options()
    direct = health_df[health_df["check"] == "direct_safe_routes"]
    protected = health_df[health_df["check"] == "protected_routes"]
    print(f"source_routes={len(options_df.index)}")
    if not direct.empty:
        print(str(direct.iloc[0]["value"]))
    if not protected.empty:
        print(str(protected.iloc[0]["value"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
