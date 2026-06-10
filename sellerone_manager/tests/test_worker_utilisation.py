from __future__ import annotations

from pathlib import Path

from sellerone_manager.worker_utilisation import build_worker_utilisation_board, write_worker_utilisation_board


def _write_log(root: Path) -> None:
    control = root / "sellerone_manager" / "CONTROL"
    control.mkdir(parents=True)
    (control / "SO21_WORKER_SIGN_IN_OUT_LOG.md").write_text(
        """# SO21 Worker Sign-In / Sign-Out Log

## Active Worker Register

| Lane | Role | Thread ID | Job Ref | Sign-In UK | Last Movement UK | State | Next Action | Sign-Out UK | Notes |
|---|---|---|---|---|---|---|---|---|---|
| Control | Worker | `thread-1` | `SO21-A` | 2026-06-09 15:00 | 2026-06-09 15:00 | working | Continue packet |  | Active worker |
| Runtime | Worker | `thread-2` | `F-JOB` | 2026-06-09 11:00 | 2026-06-09 14:00 | blocked | Wait for clearance |  | Blocked worker |

## Recently Signed Out

| Lane | Role | Thread ID | Job Ref | Sign-In UK | Sign-Out UK | Result | Notes |
|---|---|---|---|---|---|---|---|
| Review | Reviewer | `thread-3` | `SO21-B` | 2026-06-09 15:10 | 2026-06-09 15:15 | proved | Passed |
""",
        encoding="utf-8",
    )


def test_build_worker_utilisation_board_reads_active_and_signed_out(tmp_path: Path) -> None:
    _write_log(tmp_path)

    result = build_worker_utilisation_board(root=tmp_path, generated_utc="2026-06-09T15:20:00Z")

    assert result["active_count"] == 2
    assert result["signed_out_count"] == 1
    job_refs = {row["job_ref"] for row in result["rows"]}
    assert {"SO21-A", "F-JOB", "SO21-B"} <= job_refs


def test_write_worker_utilisation_board_outputs_markdown_and_csv(tmp_path: Path) -> None:
    _write_log(tmp_path)

    result = write_worker_utilisation_board(root=tmp_path, generated_utc="2026-06-09T15:20:00Z")

    board_path = Path(result["board_path"])
    csv_path = Path(result["csv_path"])
    assert board_path.exists()
    assert csv_path.exists()
    board = board_path.read_text(encoding="utf-8")
    assert "SO21 Worker Utilisation Board" in board
    assert "SO21-A" in board
    assert "SO21-B" in board
