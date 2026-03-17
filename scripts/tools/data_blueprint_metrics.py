from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "project_control" / "DATA_BLUEPRINT_REGISTRY.csv"
VALIDATION_PATH = ROOT / "out" / "system_blueprint_validation.csv"
OUTPUT_PATH = ROOT / "out" / "system_blueprint_metrics.json"

FRESHNESS_SCORE = {
    "fresh": 10.0,
    "recent": 8.0,
    "stale": 5.0,
    "missing": 2.0,
}

METRIC_FAMILIES = {
    "finance_data_integrity": {"Finance", "Tokens"},
    "inventory_accuracy": {"Inventory", "Inbound_Logistics"},
    "repricing_intelligence_health": {"Repricing_Intelligence", "Market_Intel"},
    "analytics_confidence": {"Analytics"},
    "health_governance": {"Health_Governance"},
    "runtime_stability": {"Runtime_Control"},
}


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _avg(values: List[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / float(len(values)), 2)


def _runtime_score(exists_raw: str) -> float:
    return 10.0 if str(exists_raw).strip().lower() == "true" else 3.0


def main() -> None:
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Registry file not found: {REGISTRY_PATH}")
    if not VALIDATION_PATH.exists():
        raise FileNotFoundError(f"Validation file not found: {VALIDATION_PATH}")

    registry_rows = _read_csv(REGISTRY_PATH)
    validation_rows = _read_csv(VALIDATION_PATH)
    validation_by_id = {
        str(row.get("dataset_id", "")).strip(): row for row in validation_rows if str(row.get("dataset_id", "")).strip()
    }

    metric_scores: Dict[str, List[float]] = {name: [] for name in METRIC_FAMILIES}

    for row in registry_rows:
        dataset_id = str(row.get("dataset_id", "")).strip()
        family = str(row.get("dataset_family", "")).strip()
        validation = validation_by_id.get(dataset_id, {})
        freshness = str(validation.get("freshness_status", "missing")).strip().lower() or "missing"
        exists = str(validation.get("exists", "false")).strip().lower()

        for metric_name, families in METRIC_FAMILIES.items():
            if family not in families:
                continue
            if metric_name == "runtime_stability":
                metric_scores[metric_name].append(_runtime_score(exists))
            else:
                metric_scores[metric_name].append(FRESHNESS_SCORE.get(freshness, 2.0))

    output = {
        "finance_data_integrity": _avg(metric_scores["finance_data_integrity"]),
        "inventory_accuracy": _avg(metric_scores["inventory_accuracy"]),
        "repricing_intelligence_health": _avg(metric_scores["repricing_intelligence_health"]),
        "analytics_confidence": _avg(metric_scores["analytics_confidence"]),
        "health_governance": _avg(metric_scores["health_governance"]),
        "runtime_stability": _avg(metric_scores["runtime_stability"]),
        "dataset_count": len(registry_rows),
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(
        {
            "status": "ok",
            "output": str(OUTPUT_PATH),
            "dataset_count": len(registry_rows),
        }
    )


if __name__ == "__main__":
    main()
