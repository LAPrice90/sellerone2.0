from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.one_off import BEF005_run_sold_truth_replay_capture_path as bef005
from scripts.one_off import F008_capture_full_bbp_evidence_pack as f008


def _write_csv(path: Path, rows: list[dict[str, object]], *, columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows, columns=columns) if columns is not None else pd.DataFrame(rows)
    frame.to_csv(path, index=False)


def test_bef005_skips_capture_when_queue_empty(tmp_path: Path, monkeypatch) -> None:
    analysis_dir = tmp_path / "out" / "analysis_reports"
    queue_path = analysis_dir / "f_sold_truth_replay_capture_queue_latest.csv"
    _write_csv(
        queue_path,
        [],
        columns=[
            "observed_utc",
            "asin",
            "seller_sku",
            "amazon_link",
            "capture_reason",
            "current_model_side_evidence_state",
        ],
    )

    called = {"capture": False}

    def _capture_should_not_run(**kwargs):
        _ = kwargs
        called["capture"] = True
        raise AssertionError("capture should not run for empty queue")

    monkeypatch.setattr(bef005.f008, "capture_full_bbp_evidence_pack", _capture_should_not_run)
    monkeypatch.setattr(
        bef005,
        "_run_rescore",
        lambda **kwargs: {
            "queue_rows_after": 0,
            "guard_status": "ready",
            "guard_readiness_label": "ready_clean",
            "guard_next_action": "safe_for_scheduled_one_off",
            "guard_warnings": [],
        },
    )

    result = bef005.run_sold_truth_replay_capture_path(
        output_dir=analysis_dir,
        queue_path=queue_path,
        observed_utc="2026-04-21T13:00:00Z",
    )

    assert result.report["capture_state"] == "skipped_queue_empty"
    assert called["capture"] is False
    metrics = result.report["metrics"]
    assert int(metrics["queue_rows_before"]) == 0
    assert int(metrics["capture_pack_rows"]) == 0
    assert int(metrics["queue_rows_after"]) == 0
    assert int(metrics["queue_rows_reduced"]) == 0


def test_bef005_runs_capture_and_reduces_queue_when_rows_exist(tmp_path: Path, monkeypatch) -> None:
    analysis_dir = tmp_path / "out" / "analysis_reports"
    queue_path = analysis_dir / "f_sold_truth_replay_capture_queue_latest.csv"
    _write_csv(
        queue_path,
        [
            {
                "observed_utc": "2026-04-21T12:00:00Z",
                "asin": "B00TEST001",
                "seller_sku": "OPER::001",
                "amazon_link": "https://www.amazon.co.uk/dp/B00TEST001",
                "capture_reason": "missing_model_side_evidence_for_sold_truth_row",
                "current_model_side_evidence_state": "missing",
            },
            {
                "observed_utc": "2026-04-21T12:05:00Z",
                "asin": "B00TEST001",
                "seller_sku": "OPER::001",
                "amazon_link": "https://www.amazon.co.uk/dp/B00TEST001",
                "capture_reason": "missing_model_side_evidence_for_sold_truth_row",
                "current_model_side_evidence_state": "missing",
            },
            {
                "observed_utc": "2026-04-21T12:10:00Z",
                "asin": "B00TEST002",
                "seller_sku": "OPER::002",
                "amazon_link": "https://www.amazon.co.uk/dp/B00TEST002",
                "capture_reason": "missing_model_side_evidence_for_sold_truth_row",
                "current_model_side_evidence_state": "missing",
            },
        ],
    )

    capture_args: dict[str, object] = {}

    def _fake_capture(**kwargs):
        capture_args.update(kwargs)
        manifest_df = pd.DataFrame(
            [
                {"capture_status": "success"},
                {"capture_status": "success"},
                {"capture_status": "failed"},
                {"capture_status": "success"},
            ]
        )
        latest_path = analysis_dir / "f_full_capture_manifest_latest.csv"
        manifest_df.to_csv(latest_path, index=False)
        return f008.FullBbpCaptureBuildResult(
            manifest_df=manifest_df,
            manifest_path=latest_path,
            latest_path=latest_path,
            raw_dir=analysis_dir / "raw_json",
            screenshot_dir=analysis_dir / "screenshots",
        )

    monkeypatch.setattr(bef005.f008, "capture_full_bbp_evidence_pack", _fake_capture)
    monkeypatch.setattr(
        bef005,
        "_run_post_capture_rebuild_chain",
        lambda **kwargs: {
            "consistency_facts_rows": 20,
            "alignment_rows": 10,
            "health_fail_count": 0,
            "health_warn_count": 1,
        },
    )
    monkeypatch.setattr(
        bef005,
        "_run_rescore",
        lambda **kwargs: {
            "queue_rows_after": 1,
            "guard_status": "ready",
            "guard_readiness_label": "ready_with_warnings",
            "guard_next_action": "monitor_alignment_map_and_expand_true_overlap",
            "guard_warnings": ["summary_asin_overlap_recovered_by_alignment_map"],
        },
    )

    result = bef005.run_sold_truth_replay_capture_path(
        output_dir=analysis_dir,
        queue_path=queue_path,
        max_asins=0,
        passes=2,
        observed_utc="2026-04-21T13:10:00Z",
    )

    capture_pack_df = pd.read_csv(result.capture_pack_latest_path, dtype=str).fillna("")
    assert len(capture_pack_df.index) == 2
    assert set(capture_pack_df["asin"].tolist()) == {"B00TEST001", "B00TEST002"}
    assert capture_pack_df.iloc[0]["validation_case"] == "sold_truth_replay_capture"
    assert capture_pack_df.iloc[0]["supplier_sku"].startswith("OPER::")

    assert Path(str(capture_args["asin_pack_path"])) == result.capture_pack_latest_path
    assert int(capture_args["max_asins"]) == 2
    assert int(capture_args["passes"]) == 2

    metrics = result.report["metrics"]
    assert result.report["capture_state"] == "captured"
    assert int(metrics["queue_rows_before"]) == 3
    assert int(metrics["capture_pack_rows"]) == 2
    assert int(metrics["capture_manifest_rows"]) == 4
    assert int(metrics["capture_success_rows"]) == 3
    assert int(metrics["capture_failed_rows"]) == 1
    assert int(metrics["queue_rows_after"]) == 1
    assert int(metrics["queue_rows_reduced"]) == 2
    assert float(metrics["queue_reduction_rate"]) == 0.6667
