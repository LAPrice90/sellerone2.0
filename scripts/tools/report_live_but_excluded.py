from __future__ import annotations

import argparse
import csv
from pathlib import Path


ACTIVE_PATH = Path("out/active_listings.csv")
EXCLUDED_PATH = Path("out/DIFF_active_excluded_by_scope.csv")
STOCK_PATH = Path("out/inventory_summaries.csv")
OUTPUT_PATH = Path("out/REPORT_live_but_excluded.csv")
SKU_COL_CANDIDATES = ["sku", "seller_sku", "seller-sku", "seller sku"]
QTY_COL_CANDIDATES = ["total_quantity", "total_qty", "available", "available_qty", "qty", "quantity"]


def _norm(value: object) -> str:
    return str(value or "").strip()


def _to_float(value: object) -> float:
    raw = _norm(value)
    if not raw:
        return 0.0
    try:
        return float(raw)
    except Exception:
        return 0.0


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return [{str(k): _norm(v) for k, v in row.items()} for row in reader]


def _norm_header(value: object) -> str:
    return _norm(value).lower().replace("-", "").replace("_", "").replace(" ", "")


def _resolve_column(fieldnames: list[str], candidates: list[str], label: str) -> str:
    by_norm = {_norm_header(name): name for name in fieldnames if _norm(name)}
    for cand in candidates:
        resolved = by_norm.get(_norm_header(cand), "")
        if resolved:
            return resolved
    raise RuntimeError(f"missing {label} column; tried {', '.join(candidates)}")


def _write_csv(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({h: _norm(row.get(h, "")) for h in headers})


def main() -> int:
    parser = argparse.ArgumentParser(description="Build report of live-but-excluded SKUs with stock > 0.")
    parser.add_argument("--active", default=str(ACTIVE_PATH), help="Path to out/active_listings.csv")
    parser.add_argument("--excluded", default=str(EXCLUDED_PATH), help="Path to out/DIFF_active_excluded_by_scope.csv")
    parser.add_argument("--stock", default=str(STOCK_PATH), help="Path to out/parking/stock_snapshot_latest.csv")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Path to out/REPORT_live_but_excluded.csv")
    args = parser.parse_args()

    active_path = Path(args.active)
    excluded_path = Path(args.excluded)
    stock_path = Path(args.stock)
    output_path = Path(args.output)

    for required in (active_path, excluded_path, stock_path):
        if not required.exists():
            print(f"[ERROR] Missing required input: {required}")
            return 2

    active_rows = _read_csv(active_path)
    excluded_rows = _read_csv(excluded_path)
    stock_rows = _read_csv(stock_path)

    active_skus = {
        _norm(row.get("sku", "")).upper()
        for row in active_rows
        if _norm(row.get("sku", ""))
    }

    stock_headers = list(stock_rows[0].keys()) if stock_rows else []
    try:
        stock_sku_col = _resolve_column(stock_headers, SKU_COL_CANDIDATES, "stock sku")
        stock_qty_col = _resolve_column(stock_headers, QTY_COL_CANDIDATES, "stock quantity")
    except Exception as exc:
        print(f"[ERROR] Could not resolve stock columns in {stock_path}: {exc}")
        return 2

    stock_by_sku: dict[str, float] = {}
    for row in stock_rows:
        sku = _norm(row.get(stock_sku_col, "")).upper()
        if not sku:
            continue
        qty = _to_float(row.get(stock_qty_col, "0"))
        stock_by_sku[sku] = max(stock_by_sku.get(sku, 0.0), qty)

    report_rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in excluded_rows:
        sku = _norm(row.get("sku", "")).upper()
        if not sku or sku in seen:
            continue
        seen.add(sku)
        if sku not in active_skus:
            continue
        qty = stock_by_sku.get(sku, 0.0)
        if qty <= 0:
            continue
        report_rows.append(
            {
                "sku": sku,
                "total_qty": f"{int(qty)}" if float(qty).is_integer() else f"{qty:.2f}",
                "reason": _norm(row.get("reason", "")),
                "sale_status": _norm(row.get("sale_status", "")),
                "parked_flag": _norm(row.get("parked_flag", "")),
            }
        )

    report_rows.sort(key=lambda r: _to_float(r.get("total_qty", "0")), reverse=True)
    headers = ["sku", "total_qty", "reason", "sale_status", "parked_flag"]
    _write_csv(output_path, headers, report_rows)

    print(f"report_count={len(report_rows)}")
    print("top_10_rows:")
    for row in report_rows[:10]:
        print(f"{row['sku']},{row['total_qty']},{row['reason']}")
    print(f"stock_source={stock_path} stock_sku_col={stock_sku_col} stock_qty_col={stock_qty_col}")
    print(f"output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
