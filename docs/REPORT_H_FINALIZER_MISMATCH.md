# REPORT H Finalizer Mismatch

Generated from code and runtime artifacts only. No fixes were applied.

## 1) Where run_id is created (all code paths)

### H cycle orchestrator run_id creation
- `scripts/cycles/run_H_pricing_cycle.py:539-545`
  - `_resolve_cycle_run_id(now_utc)` creates the cycle run id.
  - Path A: returns env override `H_CYCLE_EXPECTED_RUN_ID` if it matches `\d{8}T\d{6}Z`.
  - Path B: otherwise returns `now_utc.strftime("%Y%m%dT%H%M%SZ")`.
- `scripts/cycles/run_H_pricing_cycle.py:4230`
  - Main loop calls `_resolve_cycle_run_id(now_utc)` and assigns current cycle run id.

### H110 phase1 pilot fallback run_id creation
- `scripts/flows/H/H110_run_phase1_h_pilot.py:1321-1332`
  - Receives `--run-id` from orchestrator.
  - If missing, creates fallback run id with `datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")`.

### Manifest fallback run_id creation (generic core helper)
- `scripts/core/run_manifest.py:15-19`
  - `run_id_for_cycle(cycle)` creates fallback `"<CYCLE>_<stamp>_<suffix>"`.
- `scripts/core/run_manifest.py:83`
  - Used only if manifest `run_id` is empty at write time.

## 2) Where run_id is persisted (marker files, lock files, csv headers, logs)

### Marker and state files (H finalizer pipeline)
- `out/systems/H/live/H_cycle_current_run_id.txt`
  - written at `scripts/cycles/run_H_pricing_cycle.py:4241`
- `out/systems/H/live/H_run_in_progress.txt`
  - written at `scripts/cycles/run_H_pricing_cycle.py:467-468`
- `out/systems/H/live/H_last_finalized_run_id.txt`
  - written at `scripts/cycles/run_H_pricing_cycle.py:471-476`
  - also written by launcher self-heal in `run_H_cycle.bat:106`
- `out/systems/H/live/H_cycle_last_publish_run_id.txt`
  - written at `scripts/cycles/run_H_pricing_cycle.py:396-399`
- `out/systems/H/live/H_cycle_last_completed_run_id.txt`
  - written at `scripts/cycles/run_H_pricing_cycle.py:411-412`
- `out/systems/H/live/H_cycle_last_publish_info.txt`
  - includes `run_id=<value>` written at `scripts/cycles/run_H_pricing_cycle.py:399-407`
- `out/systems/H/live/H_batch_state.json`
  - contains `"run_id"` written at `scripts/cycles/run_H_pricing_cycle.py:1093-1112`

### Lock files and lock-related paths
- `out/systems/H/live/H_pricing_cycle.lock`
- `out/H_pricing_cycle.lock`
  - written by `_write_lock()` at `scripts/cycles/run_H_pricing_cycle.py:1285-1291`
  - payload format: `H|pid=<pid>|start=<utc>|heartbeat=<utc>` (no run_id field)
- `out/systems/H/staged/<run_id>/phase1.lock`
  - run_id is embedded in the staged directory path at `scripts/cycles/run_H_pricing_cycle.py:807-817, 820-828`

### CSV files with run_id header/field
- `out/h_executioner_action_log.csv`
  - header includes `run_id` at `scripts/cycles/run_H_pricing_cycle.py:1415-1433`
  - rows include run_id at `scripts/cycles/run_H_pricing_cycle.py:3213-3232`
- `out/systems/H/live/h110_sku_decision_log.csv`
  - header includes `run_id` at `scripts/flows/H/H110_run_phase1_h_pilot.py:341-351`
- `out/systems/H/live/h110_sku_lifecycle_log.csv`
  - header includes `run_id` at `scripts/flows/H/H110_run_phase1_h_pilot.py:365-375`

### Logs with run_id fields
- `out/systems/H/live/H_cycle.log` (via `_log`) `scripts/cycles/run_H_pricing_cycle.py:1134-1149`
- `out/systems/H/live/H_pricing_cycle.log` (via `_log`) `scripts/cycles/run_H_pricing_cycle.py:1134-1149`
- `out/H_cycle.log` and `out/H_pricing_cycle.log` legacy mirrors `scripts/cycles/run_H_pricing_cycle.py:1137`
- `out/systems/H/live/H_publish_gap_trace.txt` appends `run_id=...` at `scripts/cycles/run_H_pricing_cycle.py:415-430`
- `out/systems/H/live/H_ATEXIT_TRACE.log` appends `run_id=...` at `scripts/cycles/run_H_pricing_cycle.py:267-279`
- launcher log `out/systems/H/live/phase1_pilot_task.log` contains finalizer check lines from `run_H_cycle.bat:110`

## 3) Where finalizer reads "finalized run_id" from (exact path + parsing)

### Launcher gate that produced rc=3
- `run_H_cycle.bat:102`
  - `H_FINALIZED_RUN_FILE=%H_LIVE%\H_last_finalized_run_id.txt`
- `run_H_cycle.bat:110`
  - Reads current and finalized values with PowerShell:
  - `Get-Content '<file>' -Raw).Trim()` for both files
  - Decision logic:
    - `fail_missing_finalized` if finalized is empty
    - `fail_mismatch` if `current != finalized`
    - on `fail*` exits with code `3`

### Python fail-closed checks (same finalized file)
- `scripts/cycles/run_H_pricing_cycle.py:450-452`
  - `_promote_zero_exit_without_finalizer` reads `H_last_finalized_run_id.txt` via `_read_first_line(...)`
- `scripts/cycles/run_H_pricing_cycle.py:515-517`
  - `_guarded_os_exit` reads same file via `_read_first_line(...)`
- `scripts/cycles/run_H_pricing_cycle.py:4879-4892`
  - return-path check compares `success_run_id` vs `_read_first_line(H_LAST_FINALIZED_RUN_ID_PATH)` and raises `SystemExit(3)` on mismatch
- Parse helper:
  - `scripts/cycles/run_H_pricing_cycle.py:377-383`
  - `_read_first_line(path)` reads only first line and normalizes with `_norm(...)`.

## 4) Exact mismatch scenario from latest failing run (20260301T120040Z)

### Required evidence lines (quoted)
From `out/systems/H/live/phase1_pilot_task.log`:

- `118746:[01/03/2026 12:02:21.46] H-cycle child exit raw_rc=0`
- `118748:finalizer_check path=C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\H\live\H_last_finalized_run_id.txt decision=fail_mismatch current=20260301T120040Z finalized=20260301T112116Z`
- `118749:[01/03/2026 12:02:22.18] H-cycle launcher postchild checkpoint=after_finalizer_check rc=3`

### Current vs finalized values
- current run_id: `20260301T120040Z`
  - source: `out/systems/H/live/H_cycle_current_run_id.txt`
- finalized run_id: `20260301T112116Z`
  - source file: `out/systems/H/live/H_last_finalized_run_id.txt`

### Last modified timestamps of involved marker/lock files (UTC)
Captured from filesystem metadata:

- `out/systems/H/live/H_cycle_current_run_id.txt`
  - mtime: `2026-03-01T12:00:40.143Z`
  - value: `20260301T120040Z`
- `out/systems/H/live/H_run_in_progress.txt`
  - mtime: `2026-03-01T12:00:40.103Z`
  - value: `20260301T120040Z`
- `out/systems/H/live/H_last_finalized_run_id.txt`
  - mtime: `2026-03-01T11:22:45.386Z`
  - value: `20260301T112116Z`
- `out/systems/H/live/H_cycle_last_completed_run_id.txt`
  - mtime: `2026-03-01T11:17:41.136Z`
  - value: `20260301T111611Z`
- `out/systems/H/live/H_cycle_last_publish_run_id.txt`
  - mtime: `2026-03-01T11:17:41.124Z`
  - value: `20260301T111611Z`
- `out/systems/H/live/H_pricing_cycle.lock`
  - mtime: `2026-03-01T12:01:45.825Z`
  - first line: `H|pid=14020|start=2026-03-01T12:01:40Z|heartbeat=2026-03-01T12:01:45Z`
- `out/H_pricing_cycle.lock`
  - mtime: `2026-03-01T12:01:45.831Z`
  - first line: `H|pid=14020|start=2026-03-01T12:01:40Z|heartbeat=2026-03-01T12:01:45Z`

Deterministic interpretation:
- Child process returned `raw_rc=0`.
- Launcher finalizer gate then compared current vs finalized marker values.
- Finalized marker was older than current run marker, so decision became `fail_mismatch` and launcher forced `rc=3`.

## 5) How h_cycle_stale_lock is detected and how it influences finalizer behavior

### How h_cycle_stale_lock is detected (A015 health check)
- `scripts/flows/A/A015_build_system_health_check.py:89-92`
  - candidate lock paths: `out/systems/H/live/H_pricing_cycle.lock`, `out/H_pricing_cycle.lock`
- `scripts/flows/A/A015_build_system_health_check.py:3589-3614`
  - for each existing lock:
    - read payload text
    - parse `pid=` via `_parse_lock_pid(...)` (`:221, :3600-3602`)
    - if pid missing/unreadable -> WARN
    - if pid parsed but process is not alive (`_pid_alive`) -> FAIL as stale
    - otherwise -> OK

### Launcher stale lock handling before run
- `run_H_cycle.bat:31-47`
  - parses lock line for `pid=` and `heartbeat=`
  - if heartbeat age is fresh (`< H_LOCK_STALE_SECONDS`, default 300) it exits `96` (active holder)
  - if not fresh, it removes lock and continues (stale/non-owner lock cleared)

### Influence on finalizer behavior
- Directly: none. Finalizer mismatch decision uses only:
  - `H_cycle_current_run_id.txt`
  - `H_last_finalized_run_id.txt`
  - compare equality in `run_H_cycle.bat:110`
- Indirectly: stale lock recovery allows a new child run to start, but it does not update finalized marker state. If finalized marker is behind, finalizer check can still fail with `rc=3` after a `raw_rc=0` child exit.
