from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import List

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.out_paths import resolve_compat_path, write_csv_with_compat


OUT_EVENTS = Path("out/token_duplicate_receipt_cleanup_events.csv")


def _parse_dt(value: object) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(ts):
        return pd.Timestamp.min.tz_localize("UTC")
    return ts


def _select_keep_token_ids(df: pd.DataFrame, expected_qty: int) -> set[str]:
    if expected_qty <= 0 or df.empty:
        return set()
    work = df.copy()
    work["__allocated"] = work["status"].astype(str).str.strip().str.lower().eq("allocated")
    work["__allocated_date"] = work.get("allocated_date", "").apply(_parse_dt)
    work["__created_at"] = work.get("created_at", "").apply(_parse_dt)
    work["__received_date"] = work.get("received_date", "").apply(_parse_dt)
    work = work.sort_values(
        by=["__allocated", "__allocated_date", "__created_at", "__received_date", "token_id"],
        ascending=[False, True, True, True, True],
    )
    return set(work.head(expected_qty)["token_id"].astype(str).tolist())


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove excess duplicate stock-receipt tokens for one order key.")
    parser.add_argument("--order-key", required=True, help="Receipt order key to clean.")
    parser.add_argument("--expected-qty", type=int, required=True, help="Expected token qty for this order key.")
    parser.add_argument("--seller-sku", default="", help="Optional SKU constraint.")
    parser.add_argument("--apply", action="store_true", help="Write changes when set. Default is dry-run.")
    args = parser.parse_args()

    if args.expected_qty <= 0:
        raise SystemExit("expected-qty must be > 0")

    ledger_paths = resolve_compat_path("token_ledger_live.csv", default_system="B")
    alloc_paths = resolve_compat_path("token_allocations_live.csv", default_system="B")
    ledger_path = ledger_paths.live_path if ledger_paths.live_path.exists() else ledger_paths.legacy_path
    alloc_path = alloc_paths.live_path if alloc_paths.live_path.exists() else alloc_paths.legacy_path
    if not ledger_path.exists() or not alloc_path.exists():
        raise SystemExit("Required token ledger/allocation files are missing.")

    ledger = pd.read_csv(ledger_path, dtype=str).fillna("")
    alloc = pd.read_csv(alloc_path, dtype=str).fillna("")

    required_ledger_cols = {"token_id", "seller_sku", "source", "source_order_key", "status"}
    missing_ledger_cols = sorted(required_ledger_cols - set(ledger.columns))
    if missing_ledger_cols:
        raise SystemExit(f"token_ledger_live missing columns: {missing_ledger_cols}")
    if "token_id" not in alloc.columns:
        raise SystemExit("token_allocations_live missing token_id column")

    mask = (
        ledger["source"].astype(str).str.strip().str.lower().eq("stock_receipt")
        & ledger["source_order_key"].astype(str).str.strip().eq(args.order_key.strip())
    )
    if args.seller_sku.strip():
        mask &= ledger["seller_sku"].astype(str).str.strip().eq(args.seller_sku.strip())
    target = ledger.loc[mask].copy()
    if target.empty:
        raise SystemExit("No stock_receipt tokens found for the provided order key/sku.")

    keep_ids = _select_keep_token_ids(target, args.expected_qty)
    remove_df = target.loc[~target["token_id"].astype(str).isin(keep_ids)].copy()
    remove_ids = set(remove_df["token_id"].astype(str).tolist())

    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    cleanup_rows: List[dict[str, str]] = []
    if not remove_df.empty:
        alloc_hit = alloc["token_id"].astype(str).isin(remove_ids)
        alloc_hit_map = set(alloc.loc[alloc_hit, "token_id"].astype(str).tolist())
        for _, row in remove_df.iterrows():
            token_id = str(row.get("token_id", ""))
            cleanup_rows.append(
                {
                    "event_ts": now_iso,
                    "order_key": args.order_key,
                    "seller_sku": str(row.get("seller_sku", "")),
                    "token_id": token_id,
                    "status_before": str(row.get("status", "")),
                    "allocation_removed": "1" if token_id in alloc_hit_map else "0",
                    "reason": "duplicate_receipt_excess",
                }
            )

    summary = {
        "status": "dry_run" if not args.apply else "applied",
        "order_key": args.order_key,
        "seller_sku": args.seller_sku,
        "expected_qty": int(args.expected_qty),
        "actual_qty": int(len(target.index)),
        "excess_qty": int(max(len(target.index) - args.expected_qty, 0)),
        "remove_qty": int(len(remove_ids)),
    }

    OUT_EVENTS.parent.mkdir(parents=True, exist_ok=True)
    events_df = pd.DataFrame(cleanup_rows)
    if OUT_EVENTS.exists() and not events_df.empty:
        events_df.to_csv(OUT_EVENTS, mode="a", header=False, index=False)
    elif not events_df.empty:
        events_df.to_csv(OUT_EVENTS, index=False)

    if args.apply and remove_ids:
        ledger = ledger.loc[~ledger["token_id"].astype(str).isin(remove_ids)].copy()
        alloc = alloc.loc[~alloc["token_id"].astype(str).isin(remove_ids)].copy()
        write_csv_with_compat(ledger, path_or_rel="token_ledger_live.csv", default_system="B", index=False, mirror_legacy=True)
        write_csv_with_compat(
            alloc,
            path_or_rel="token_allocations_live.csv",
            default_system="B",
            index=False,
            mirror_legacy=True,
        )

    print(summary)


if __name__ == "__main__":
    main()

