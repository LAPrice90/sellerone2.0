from __future__ import annotations

import csv
import json
import os
from pathlib import Path

from scripts.one_off import P003_build_sql_migration_backup_manifest as p003


def _write_registry(root: Path) -> None:
    path = root / "project_control" / "DATA_BLUEPRINT_REGISTRY.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "dataset_id,dataset_name,dataset_family,owner_cycle,canonical_path,allowed_mirror_paths,writer_scripts,consumer_scripts,dataset_type,update_frequency,decision_importance_0_10,freshness_score_0_10,reliability_score_0_10,completeness_score_0_10,overall_data_performance_score_0_10,status,schema_ref,notes,last_scored_utc",
                "B.ORDERS_ALL,Orders All,Finance,B,out/orders_all.csv,,writer,consumer,master_table,continuous,10,7,7,7,7.60,Baselining,header:a|b,Primary,2026-03-16T00:00:00Z",
                "E.MISSING,Missing,Analytics,E,out/missing.csv,,writer,consumer,derived,daily,5,0,0,0,0,Unscored,header:x,Missing target,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_registry_manifest_includes_existing_row_count_and_missing_target(tmp_path: Path) -> None:
    _write_registry(tmp_path)
    orders = tmp_path / "out" / "orders_all.csv"
    orders.parent.mkdir(parents=True, exist_ok=True)
    orders.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")

    rows, errors = p003.build_manifest_rows(
        root=tmp_path,
        scope="registry",
        backup_bundle_id="bundle_1",
        generated_at_utc="2026-04-28T12:00:00Z",
        max_hash_mb=1,
        max_count_mb=1,
    )

    assert errors == []
    by_path = {row["path"]: row for row in rows}
    assert by_path["out/orders_all.csv"]["exists"] == "true"
    assert by_path["out/orders_all.csv"]["owner_flow"] == "B"
    assert by_path["out/orders_all.csv"]["dataset_id"] == "B.ORDERS_ALL"
    assert by_path["out/orders_all.csv"]["row_count"] == "2"
    assert by_path["out/orders_all.csv"]["row_count_status"] == "ok"
    assert by_path["out/missing.csv"]["exists"] == "false"
    assert by_path["out/missing.csv"]["hash_status"] == "missing"


def test_large_hash_is_skipped_when_file_exceeds_limit(tmp_path: Path) -> None:
    target = tmp_path / "data" / "large.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("a\n" + ("x\n" * 10), encoding="utf-8")

    row = p003.manifest_row_for_file(
        target,
        root=tmp_path,
        backup_bundle_id="bundle_1",
        generated_at_utc="2026-04-28T12:00:00Z",
        scope="core",
        max_hash_bytes=1,
        max_count_bytes=1024,
    )

    assert row["hash_status"] == "skipped_large"
    assert row["row_count"] == "10"


def test_pause_state_blocks_active_lock(tmp_path: Path) -> None:
    lock = tmp_path / "out" / "B_cycle.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(f"B|pid={os.getpid()}|run_id=B_TEST|heartbeat=2026-04-28T12:00:00Z\n", encoding="utf-8")

    state = p003.collect_pause_state(tmp_path, scan_processes=False)

    assert state["safe_to_backup"] is False
    assert any("lock_present:out/B_cycle.lock" in blocker for blocker in state["blockers"])


def test_pause_state_blocks_active_supervisor_lock(tmp_path: Path) -> None:
    lock = tmp_path / "out" / "systems" / "B" / "live" / "B_supervisor.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(
        f"B_SUPERVISOR|pid={os.getpid()}|worker=scripts/cycles/run_B_cycle.py\n",
        encoding="utf-8",
    )

    state = p003.collect_pause_state(tmp_path, scan_processes=False)

    assert state["safe_to_backup"] is False
    assert any("lock_present:out/systems/B/live/B_supervisor.lock" in blocker for blocker in state["blockers"])


def test_pause_state_blocks_known_process_match(tmp_path: Path) -> None:
    state = p003.collect_pause_state(
        tmp_path,
        scan_processes=True,
        injected_process_rows=[
            {"pid": "123", "command": "python scripts/cycles/run_H_pricing_cycle.py"},
        ],
    )

    assert state["safe_to_backup"] is False
    assert "process_match:run_H_pricing_cycle.py:pid=123" in state["blockers"]


def test_write_manifest_outputs_csv_and_summary(tmp_path: Path) -> None:
    _write_registry(tmp_path)
    orders = tmp_path / "out" / "orders_all.csv"
    orders.parent.mkdir(parents=True, exist_ok=True)
    orders.write_text("a,b\n1,2\n", encoding="utf-8")

    summary = p003.write_manifest_outputs(
        root=tmp_path,
        output_root=tmp_path / "backup_out",
        scope="registry",
        backup_bundle_id="bundle_1",
        max_hash_mb=1,
        max_count_mb=1,
        quiet_seconds=0,
        scan_processes=False,
    )

    manifest_path = tmp_path / summary["manifest_path"]
    summary_path = tmp_path / summary["summary_path"]
    assert manifest_path.exists()
    assert summary_path.exists()

    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        manifest_rows = list(csv.DictReader(handle))
    assert len(manifest_rows) == 2
    assert summary["safe_to_start_backup"] is True
    assert json.loads(summary_path.read_text(encoding="utf-8"))["row_count"] == 2
