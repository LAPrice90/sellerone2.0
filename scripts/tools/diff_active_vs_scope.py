from __future__ import annotations

import csv
from pathlib import Path

from scripts.core.storage import read_dataframe_with_sql_fallback


ACTIVE_LISTINGS_PATH = Path("out/active_listings.csv")
SCOPE_PATH = Path("out/phase1_sku_scope.csv")
SQL_TABLE_PHASE1_SKU_SCOPE = "b_phase1_sku_scope"
OUT_EXCLUDED = Path("out/DIFF_active_excluded_by_scope.csv")
OUT_MISSING = Path("out/DIFF_active_missing_from_scope.csv")


def _norm(text: object) -> str:
    return str(text or "").strip()


def _truthy_flag(text: object) -> bool:
    return _norm(text).lower() in {"1", "true", "yes", "y", "on"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if path == SCOPE_PATH:
        df = read_dataframe_with_sql_fallback(path, SQL_TABLE_PHASE1_SKU_SCOPE, dtype=str).fillna("")
        return [{str(k): _norm(v) for k, v in row.items()} for row in df.to_dict("records")]
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return [{str(k): _norm(v) for k, v in row.items()} for row in reader]


def _write_csv(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({h: _norm(row.get(h, "")) for h in headers})


def main() -> int:
    if not ACTIVE_LISTINGS_PATH.exists():
        print(
            "[ERROR] Missing active listings file: out/active_listings.csv\n"
            "Run scripts/tools/build_active_listings_csv.py first."
        )
        return 2
    active_rows = _read_csv(ACTIVE_LISTINGS_PATH)
    try:
        scope_rows = _read_csv(SCOPE_PATH)
    except FileNotFoundError:
        print("[ERROR] Missing scope file: out/phase1_sku_scope.csv")
        return 2

    active_skus = []
    seen_active: set[str] = set()
    for row in active_rows:
        sku = _norm(row.get("sku", "")).upper()
        if not sku or sku in seen_active:
            continue
        seen_active.add(sku)
        active_skus.append(sku)

    scope_by_sku: dict[str, dict[str, str]] = {}
    for row in scope_rows:
        sku = _norm(row.get("sku", "")).upper()
        if not sku or sku in scope_by_sku:
            continue
        scope_by_sku[sku] = row

    missing_rows: list[dict[str, str]] = []
    excluded_rows: list[dict[str, str]] = []

    for sku in active_skus:
        rec = scope_by_sku.get(sku)
        if rec is None:
            missing_rows.append({"sku": sku, "reason": "NOT_IN_phase1_sku_scope"})
            continue
        sale_status = _norm(rec.get("sale_status", ""))
        parked_flag = "1" if _truthy_flag(rec.get("parked_flag", "")) else "0"
        is_dropped = sale_status.lower() == "dropped"
        is_parked = parked_flag == "1"
        if not is_dropped and not is_parked:
            continue
        if is_dropped and is_parked:
            reason = "DROPPED_AND_PARKED"
        elif is_dropped:
            reason = "DROPPED"
        else:
            reason = "PARKED"
        excluded_rows.append(
            {
                "sku": sku,
                "sale_status": sale_status,
                "parked_flag": parked_flag,
                "reason": reason,
            }
        )

    _write_csv(
        OUT_MISSING,
        ["sku", "reason"],
        missing_rows,
    )
    _write_csv(
        OUT_EXCLUDED,
        ["sku", "sale_status", "parked_flag", "reason"],
        excluded_rows,
    )

    print(f"active_count={len(active_skus)}")
    print(f"excluded_count={len(excluded_rows)}")
    print(f"missing_count={len(missing_rows)}")
    print(f"excluded_output={OUT_EXCLUDED}")
    print(f"missing_output={OUT_MISSING}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
