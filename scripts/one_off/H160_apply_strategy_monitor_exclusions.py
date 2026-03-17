from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
MONITOR_PATH = OUT / "phase1_strategy_monitor.csv"
EXCLUSIONS_PATH = OUT / "phase1_strategy_monitor_exclusions.csv"

PHASE_FIELDS_TO_BLANK = (
    "phase",
    "days_under_new_strategy",
    "days_in_current_phase",
)


def _load_exclusions(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            sku = str(row.get("sku", "")).strip()
            reason = str(row.get("excluded_reason", "")).strip()
            if not sku:
                continue
            out[sku] = reason
    return out


def main() -> int:
    if not MONITOR_PATH.exists():
        print(f"monitor_missing path={MONITOR_PATH}")
        return 1

    exclusions = _load_exclusions(EXCLUSIONS_PATH)

    with MONITOR_PATH.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
        fieldnames = list(rows[0].keys()) if rows else []

    if "excluded_reason" not in fieldnames:
        fieldnames.append("excluded_reason")

    for row in rows:
        sku = str(row.get("sku", "")).strip()
        reason = exclusions.get(sku, "")
        row["excluded_reason"] = reason
        if reason:
            for col in PHASE_FIELDS_TO_BLANK:
                if col in row:
                    row[col] = ""

    with MONITOR_PATH.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"monitor_updated path={MONITOR_PATH} rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
