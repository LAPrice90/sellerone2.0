from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "project_control" / "DATA_BLUEPRINT_REGISTRY.csv"
OUT_PATH = ROOT / "out" / "system_blueprint_validation.csv"


def _as_bool_text(value: bool) -> str:
    return "true" if value else "false"


def _path_exists_and_mtime(canonical_path: str) -> Tuple[bool, float | None]:
    raw = (canonical_path or "").strip()
    if not raw:
        return False, None

    # Wildcard canonical paths (for example: out/manifests/A/*) are treated
    # as directory-level presence checks.
    if "*" in raw:
        wildcard_path = Path(raw)
        directory = wildcard_path.parent
        if not directory.is_absolute():
            directory = ROOT / directory
        if directory.exists():
            return True, directory.stat().st_mtime
        return False, None

    target = Path(raw)
    if not target.is_absolute():
        target = ROOT / target
    if target.exists():
        return True, target.stat().st_mtime
    return False, None


def _freshness_status(age_hours: float | None) -> str:
    if age_hours is None:
        return "missing"
    if age_hours <= 1.0:
        return "fresh"
    if age_hours <= 24.0:
        return "recent"
    return "stale"


def _format_age(age_hours: float | None) -> str:
    if age_hours is None:
        return ""
    return f"{age_hours:.2f}"


def build_validation_rows(registry_rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    now_ts = datetime.now(timezone.utc).timestamp()
    out_rows: List[Dict[str, str]] = []

    for row in registry_rows:
        dataset_id = (row.get("dataset_id") or "").strip()
        canonical_path = (row.get("canonical_path") or "").strip()
        owner_cycle = (row.get("owner_cycle") or "").strip()
        dataset_family = (row.get("dataset_family") or "").strip()

        exists, mtime = _path_exists_and_mtime(canonical_path)
        age_hours = ((now_ts - mtime) / 3600.0) if (exists and mtime is not None) else None

        # Runtime_Control datasets are presence-governed; keep same output shape
        # while avoiding any scoring logic (this script does not score).
        if dataset_family == "Runtime_Control":
            freshness = "fresh" if exists else "missing"
            age_out = _format_age(age_hours) if exists else ""
        else:
            freshness = _freshness_status(age_hours)
            age_out = _format_age(age_hours)

        out_rows.append(
            {
                "dataset_id": dataset_id,
                "canonical_path": canonical_path,
                "exists": _as_bool_text(exists),
                "freshness_status": freshness,
                "file_age_hours": age_out,
                "owner_cycle": owner_cycle,
                "dataset_family": dataset_family,
            }
        )

    return out_rows


def main() -> None:
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Registry not found: {REGISTRY_PATH}")

    with REGISTRY_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        registry_rows = list(csv.DictReader(f))

    validation_rows = build_validation_rows(registry_rows)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "dataset_id",
        "canonical_path",
        "exists",
        "freshness_status",
        "file_age_hours",
        "owner_cycle",
        "dataset_family",
    ]
    with OUT_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(validation_rows)

    print(
        {
            "status": "ok",
            "registry_rows": len(registry_rows),
            "validation_rows": len(validation_rows),
            "output": str(OUT_PATH),
        }
    )


if __name__ == "__main__":
    main()
