from __future__ import annotations

import os
from pathlib import Path

from scripts.cycles import run_H_pricing_cycle as h_cycle


def test_phase1_staged_publish_retries_transient_replace_permission_error(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    staged_root = tmp_path / "out" / "systems" / "H" / "staged"
    live_dir = tmp_path / "out" / "systems" / "H" / "live"
    run_id = "RUN-RETRY"
    table_name = "execution_log"

    data_dir.mkdir(parents=True)
    stage_data = staged_root / run_id / "data"
    stage_data.mkdir(parents=True)
    live_dir.mkdir(parents=True)

    live_file = data_dir / f"{table_name}.csv"
    staged_file = stage_data / f"{table_name}.csv"
    live_file.write_text("sku,status\nOLD,old\n", encoding="utf-8")
    staged_file.write_text("sku,status\nNEW,new\n", encoding="utf-8")

    monkeypatch.setattr(h_cycle, "DATA", data_dir)
    monkeypatch.setattr(h_cycle, "H_STAGED_ROOT", staged_root)
    monkeypatch.setattr(h_cycle, "H_LIVE_DIR", live_dir)
    monkeypatch.setattr(h_cycle, "PHASE1_STAGED_TABLES", [table_name])
    monkeypatch.setattr(h_cycle, "_log", lambda _message: None)

    real_replace = os.replace
    calls = {"replace": 0}

    def flaky_replace(src: str | Path, dst: str | Path) -> None:
        calls["replace"] += 1
        if calls["replace"] == 1:
            raise PermissionError("temporary lock")
        real_replace(src, dst)

    monkeypatch.setattr(h_cycle.os, "replace", flaky_replace)

    state = h_cycle._promote_phase1_staged_outputs(run_id)

    assert state["phase1_staged_publish_status"] == "ok"
    assert state["phase1_staged_publish_files"] == "1"
    assert calls["replace"] == 2
    assert live_file.read_text(encoding="utf-8") == "sku,status\nNEW,new\n"


def test_phase1_staged_publish_reports_failed_table_after_retry_exhaustion(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    staged_root = tmp_path / "out" / "systems" / "H" / "staged"
    live_dir = tmp_path / "out" / "systems" / "H" / "live"
    run_id = "RUN-FAIL"
    table_name = "execution_log"

    data_dir.mkdir(parents=True)
    stage_data = staged_root / run_id / "data"
    stage_data.mkdir(parents=True)
    live_dir.mkdir(parents=True)
    (stage_data / f"{table_name}.csv").write_text("sku,status\nNEW,new\n", encoding="utf-8")

    monkeypatch.setattr(h_cycle, "DATA", data_dir)
    monkeypatch.setattr(h_cycle, "H_STAGED_ROOT", staged_root)
    monkeypatch.setattr(h_cycle, "H_LIVE_DIR", live_dir)
    monkeypatch.setattr(h_cycle, "PHASE1_STAGED_TABLES", [table_name])
    monkeypatch.setattr(h_cycle, "_log", lambda _message: None)

    def locked_replace(_src: str | Path, _dst: str | Path) -> None:
        raise PermissionError("still locked")

    monkeypatch.setattr(h_cycle.os, "replace", locked_replace)
    monkeypatch.setattr(h_cycle.time, "sleep", lambda _seconds: None)

    state = h_cycle._promote_phase1_staged_outputs(run_id)

    assert state["phase1_staged_publish_status"] == "failed:PermissionError"
    assert state["phase1_staged_publish_failed_table"] == table_name
    assert state["phase1_staged_publish_failed_target"] == str(data_dir / f"{table_name}.csv")
    assert "still locked" in state["phase1_staged_publish_error"]
