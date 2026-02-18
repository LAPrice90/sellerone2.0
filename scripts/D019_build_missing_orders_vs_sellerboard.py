"""
Compare Sellerboard order items export to Order_Master and list missing orders.

Outputs:
- out/analysis_reports/missing_orders_vs_sellerboard.csv
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

import pandas as pd


OUT_DIR = Path("out") / "analysis_reports"
OUT_PATH = OUT_DIR / "missing_orders_vs_sellerboard.csv"
ORDER_MASTER = Path("out/order_master.csv")

ORDER_ID_RE = re.compile(r"\b\d{3}-\d{7}-\d{7}\b")


def _find_latest_sellerboard_export() -> Optional[Path]:
    # Prefer explicit env var.
    env_path = os.environ.get("SELLERBOARD_ORDER_ITEMS_PATH", "").strip()
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path
    # Fallbacks: out/analysis_reports and reference
    patterns = [
        "DRJ_Hardware_Dashboard_Order_Items_*.csv",
    ]
    candidates: list[Path] = []
    for base in [Path("out/analysis_reports"), Path("reference")]:
        for pat in patterns:
            candidates.extend(base.glob(pat))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _extract_order_id(raw: str) -> str:
    match = ORDER_ID_RE.search(str(raw))
    return match.group(0) if match else str(raw).strip()


def main() -> None:
    if not ORDER_MASTER.exists():
        print({"status": "skip", "reason": "missing order_master.csv"})
        return

    sb_path = _find_latest_sellerboard_export()
    if not sb_path:
        print({"status": "skip", "reason": "no sellerboard export found"})
        return

    sb = pd.read_csv(sb_path, sep=";", engine="python", encoding="utf-8-sig").fillna("")
    if "Order number" not in sb.columns:
        print({"status": "skip", "reason": "missing Order number column"})
        return

    sb["order_id"] = sb["Order number"].apply(_extract_order_id)
    sb = sb[sb["order_id"].astype(str).str.len() == 19]
    sb = sb.rename(columns={"Order date": "order_date", "SKU": "sku"})

    om = pd.read_csv(ORDER_MASTER, dtype=str).fillna("")
    om_ids = set(om["Order ID"].astype(str))

    sb_ids = set(sb["order_id"].astype(str))
    missing_ids = sorted(sb_ids - om_ids)

    missing = sb[sb["order_id"].isin(missing_ids)].copy()
    keep_cols = ["order_id", "order_date", "sku", "ASIN", "Product", "Units", "Sales", "Cost of Goods"]
    keep_cols = [c for c in keep_cols if c in missing.columns]
    missing = missing[keep_cols].copy()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    missing.to_csv(OUT_PATH, index=False)
    print(
        {
            "status": "success",
            "sellerboard_export": str(sb_path),
            "missing_count": len(missing_ids),
            "report": str(OUT_PATH),
        }
    )


if __name__ == "__main__":
    main()
