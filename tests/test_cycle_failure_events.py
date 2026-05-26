import csv
from pathlib import Path

from scripts.core import cycle_failure_events as events


def test_cycle_failure_event_schema_and_upsert(tmp_path: Path) -> None:
    ledger = tmp_path / "cycle_failure_events.csv"
    row = {
        "timestamp_utc": "2026-05-18T12:00:00Z",
        "cycle": "A",
        "run_id": "20260518T120000Z",
        "final_state": "partial",
        "cause_code": "OUTPUT_STALE",
        "cause_detail": "stale inventory outputs",
        "step_name": "A003_run_inventory_to_sheet.py",
        "stage": "A003_run_inventory_to_sheet.py",
        "rc": "0",
        "verification_status": "failed_stale_outputs",
        "manifest_path": "out/manifests/A/2026-05-18/20260518T120000Z.json",
        "source_path": "scripts/cycles/run_A_all.py",
    }

    events.upsert_cycle_failure_event(row, path=ledger)
    events.upsert_cycle_failure_event({**row, "cause_detail": "updated stale detail"}, path=ledger)

    ok, reason = events.validate_cycle_failure_events_schema(ledger)
    assert ok, reason
    with ledger.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert list(rows[0].keys()) == events.FAILURE_EVENT_COLUMNS
    assert rows[0]["cause_detail"] == "updated stale detail"


def test_failure_event_from_manifest_classifies_stale_outputs() -> None:
    manifest = {
        "cycle": "A",
        "run_id": "20260518T120000Z",
        "final_state": "partial",
        "steps": [
            {
                "name": "A003_run_inventory_to_sheet.py",
                "script_or_function": "A003_run_inventory_to_sheet.py",
                "rc": 0,
                "step_status": "failed",
                "verification_status": "failed_stale_outputs",
                "notes": "elapsed=12.0s;stale=out/inventory_snapshot_latest.csv",
                "stale_outputs": ["out/inventory_snapshot_latest.csv"],
            }
        ],
    }

    row = events.build_failure_event_from_manifest(manifest)

    assert row["cause_code"] == "OUTPUT_STALE"
    assert row["step_name"] == "A003_run_inventory_to_sheet.py"
    assert "inventory_snapshot_latest.csv" in row["cause_detail"]
