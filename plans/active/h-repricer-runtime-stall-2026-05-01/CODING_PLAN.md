# H Repricer Runtime Stall - 2026-05-01

## Status
- Phase: live verification confirmed
- Started at: 2026-05-01T09:01:32Z
- Owner: Codex

## Problem
H stopped making progress after run `20260501T012125Z`.

Evidence:
- Last finalized run: `20260501T005311Z`.
- Nonterminal run: `20260501T012125Z`, state `started`, stage `cycle_start`, owner PID `1320`.
- First stall point: `snapshot_refresh own_offer_lookup` launched child PID `4552` at `2026-05-01T01:21:35Z`, with no completion line and empty stdout/stderr.
- Repeated restarts then failed with `startup_nonterminal_guard_blocked ... owner_alive=1`.
- Current PID `1320` is `svchost.exe`, not H Python.
- Launcher lock PID `16456` is a stale `cmd.exe`; scheduler retry rejected it as `healthy_live_owner` even with `h_python_active=false`.

## Root Cause Theory
The original H owner died or was externally interrupted while waiting for `own_offer_lookup`.
The durable failure was the restart guard:
- core startup guard used PID existence as owner truth
- launcher gate accepted stale launcher heartbeat as live ownership without requiring an H Python process

This caused fail-closed recovery to block every later restart.

## Allowed Files
- `scripts/cycles/run_H_pricing_cycle.py`
- `scripts/tools/h_launcher_gate.ps1`
- focused H guard tests under `tests/`
- this plan file
- H roadmap/expectation files only if final evidence supports a status update

## Proof Plan
- Add an isolated test showing a reused non-H PID does not count as live H owner.
- Add an isolated launcher-gate test or focused PowerShell probe showing stale launcher lock with no H Python is replaceable.
- Run focused tests for changed guard behavior.
- Use H-owned runtime proof after tests: controlled H isolation or scheduler-safe H restart, then confirm terminal/finalized marker and ownership restoration.

## Monitoring
- Cadence: first check 5 minutes after restart, second at 10 minutes, then every 15 minutes up to 60 minutes.
- Artifacts: `out/systems/H/live/H_run_state.json`, `H_last_finalized_run_id.txt`, `H_runtime_status.json`, `phase1_pilot_task.log`.
- Success threshold: at least one new H run after the fix reaches finalized/succeeded and launcher ownership is not stuck on stale lock.
- Timeout rule: if no terminal run by 60 minutes, park as `parked pending next proof window` with exact blocker.

## Live Verification
- Fix changed at: 2026-05-01T09:11Z.
- Stale run `20260501T012125Z` was terminalized at `2026-05-01T09:11:48Z` with `STALE_OWNER_IDENTITY_MISMATCH`.
- Recovery run `20260501T091405Z` started at `2026-05-01T09:14:05Z`.
- Snapshot refresh passed: own-offer lookup rc `0`, item-offers lookup rc `0`, listing rows `65`, seller rows `156`.
- Pilot processed `50/50` SKUs and emitted success payload at `2026-05-01T09:29:18Z`.
- Publish completed with status `ok` and staged publish committed at `2026-05-01T09:31:10Z`.
- `H_run_state.json` showed `state=finalized`, `publish_status=ok`; `H_worker_lifecycle.json` showed `state=succeeded`, `expected_outputs_ok=1`.
- Ownership restoration confirmed by new live run `20260501T093154Z` starting at `2026-05-01T09:31:55Z`.
- Follow-on run `20260501T093154Z` also finalized successfully and published `ok` at `2026-05-01T09:47:38Z`.
- Current observed run `20260501T094820Z` is live in `phase1_pilot` with current heartbeat, so H recovery remains active.
- Monitoring check at `2026-05-01T10:11Z`: run `20260501T094820Z` finalized and published `ok`; next run `20260501T100227Z` is live in `phase1_pilot` with current heartbeat. A suspicious `phase1 pilot step returned no output` line was confirmed to be from `2026-02-18`, not the active run.
- Monitoring check at `2026-05-01T10:16Z`: run `20260501T100227Z` finalized with `publish_status=ok`; worker lifecycle `state=succeeded`, `expected_outputs_ok=1`.
- Monitoring check at `2026-05-01T10:18Z`: ownership restoration confirmed again by new run `20260501T101631Z` entering `phase1_pilot` with current heartbeat.
