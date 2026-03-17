"""
Recover missing OrderItems for L3 orphans by calling OrderItems API directly.

Inputs:
- out/l3_orphans_missing_orders_all.csv (created by analysis step)
Fallback:
- out/l3_orphans_with_orders_all.csv (Order ID column)

Outputs:
- out/orphan_order_items_recovered.csv (newly recovered items)
- out/orphan_order_items_failed.csv (orders that failed)
- out/order_items_all.csv (append + dedupe)
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api.get_orders import get_lwa_access_token, list_order_items, load_dotenv_if_missing
from scripts.B001_run_orders_to_sheet import _compiled_items_dedupe_key, _write_compiled_unique

L3_ORPHANS_MISSING = ROOT / "out" / "l3_orphans_missing_orders_all.csv"
L3_ORPHANS_WITH = ROOT / "out" / "l3_orphans_with_orders_all.csv"
ITEMS_ALL_PATH = ROOT / "out" / "order_items_all.csv"
RECOVERED_PATH = ROOT / "out" / "orphan_order_items_recovered.csv"
FAILED_PATH = ROOT / "out" / "orphan_order_items_failed.csv"

SLEEP_SEC = float(os.environ.get("ORPHAN_ITEMS_SLEEP_SEC", "1.5"))
MAX_PER_RUN = int(os.environ.get("ORPHAN_ITEMS_MAX_PER_RUN", "0"))  # 0 = all


def _load_orphan_order_ids() -> List[str]:
    for path in (L3_ORPHANS_MISSING, L3_ORPHANS_WITH):
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path, dtype=str)
        except Exception:
            continue
        if df.empty:
            continue
        if "Order ID" in df.columns:
            ids = df["Order ID"].astype(str).str.strip().tolist()
        elif "amazon_order_id" in df.columns:
            ids = df["amazon_order_id"].astype(str).str.strip().tolist()
        else:
            continue
        ids = [i for i in ids if i]
        if ids:
            return sorted(set(ids))
    return []


def main() -> int:
    load_dotenv_if_missing()
    order_ids = _load_orphan_order_ids()
    if not order_ids:
        print("[B012] no orphan order IDs found; nothing to recover")
        return 0

    if MAX_PER_RUN > 0:
        order_ids = order_ids[:MAX_PER_RUN]

    token = get_lwa_access_token()
    recovered_items: List[Dict[str, object]] = []
    failed_rows: List[Dict[str, object]] = []

    for idx, order_id in enumerate(order_ids, 1):
        try:
            nt: Optional[str] = None
            items: List[Dict[str, object]] = []
            while True:
                batch, nt = list_order_items(access_token=token, amazon_order_id=order_id, next_token=nt)
                for it in batch:
                    it["AmazonOrderId"] = order_id
                items.extend(batch)
                if not nt:
                    break
            if not items:
                failed_rows.append({"order_id": order_id, "error": "no_items_returned"})
            else:
                recovered_items.extend(items)
        except Exception as exc:
            failed_rows.append({"order_id": order_id, "error": str(exc)})
        time.sleep(SLEEP_SEC)

    if recovered_items:
        df_recovered = pd.DataFrame(recovered_items).fillna("").astype(str)
        RECOVERED_PATH.parent.mkdir(parents=True, exist_ok=True)
        df_recovered.to_csv(RECOVERED_PATH, index=False)

        df_recovered["_dedupe_key"] = _compiled_items_dedupe_key(df_recovered)
        existing_items = pd.read_csv(ITEMS_ALL_PATH, dtype=str).fillna("") if ITEMS_ALL_PATH.exists() else pd.DataFrame()
        if not existing_items.empty:
            existing_items = existing_items.copy()
            existing_items["_dedupe_key"] = _compiled_items_dedupe_key(existing_items)
        _write_compiled_unique(
            ITEMS_ALL_PATH,
            existing_items,
            df_recovered,
            dedupe_key_cols=["_dedupe_key"],
        )
        # Drop helper column from stored file.
        try:
            items_all_df = pd.read_csv(ITEMS_ALL_PATH, dtype=str).fillna("")
            if "_dedupe_key" in items_all_df.columns:
                items_all_df = items_all_df.drop(columns=["_dedupe_key"])
                items_all_df.to_csv(ITEMS_ALL_PATH, index=False)
        except Exception:
            pass

    if failed_rows:
        FAILED_PATH.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(failed_rows).to_csv(FAILED_PATH, index=False)

    print(
        {
            "status": "success",
            "orders_requested": len(order_ids),
            "items_recovered": len(recovered_items),
            "failed_orders": len(failed_rows),
            "snapshot_recovered": str(RECOVERED_PATH),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


