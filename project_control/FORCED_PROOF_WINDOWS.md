# Forced Proof Windows

## Purpose

This guide exists to stop unnecessary "wait for the next cycle" validation when the repo already has a safe way to force proof now.

Use this when:
- a code change needs sign-off
- a runtime fix needs one-run proof
- a scoped health check can be run safely at a flow boundary

Do not use this to fake long-horizon evidence. If the proof depends on more volume or more time, say that plainly.

## Core rule

If the task is about single-run correctness, boundary-safe health, or a narrow regression check, do not wait for tomorrow's scheduler pass by default.

Instead:
1. identify the owner flow
2. find the safe boundary for that flow
3. run the owned proof path
4. read health only after the run finalizes

Mid-cycle checks are not proof.

## Safe boundary by flow

### A flow

Use when:
- the change belongs to the A-owned path itself

Safe boundary:
- run the owned A cycle path
- if B is live, use the existing A/B maintenance handoff and wait for `maintenance.ready`

Do:
- use the full A-owned flow proof
- read the fresh A outputs written by that run

Do not:
- use `A015_build_system_health_check.py` alone as proof for A-owned changes unless the user explicitly asked for that exact narrow run

## B flow

Use when:
- the change belongs to B logic, B outputs, or B-scoped health

Safe boundary:
- if B is live, request maintenance and let B finish its current full cycle
- once B is idle or `maintenance.ready` is present, run one full boundary-safe B cycle with `B_RUN_ONCE=1`
- read B-scoped health only after B finalizes

Command shape:
```powershell
$env:B_RUN_ONCE = "1"
python scripts/cycles/run_B_cycle.py
python scripts/flows/A/A015_build_system_health_check.py --profile b --no-toast
```

Do not:
- run overlapping B proof while a live B owner is active
- read COG or token health halfway through B
- treat a mid-cycle missing-cost state as a final fail

## E flow

Use when:
- the change belongs to E logic or E outputs

Safe boundary:
- run one owned E cycle
- use the E-scoped proof written by that run

Command shape:
```powershell
python scripts/cycles/run_E_cycle.py
```

Notes:
- `run_E_cycle.py` already includes its own E-scoped health path
- do not overlap a manual E proof run with an active E owner

## H flow

Use when:
- the change belongs to H runtime logic, H outputs, or H-scoped health

Safe boundary:
1. pause scheduler ownership
2. confirm no active H owner remains
3. run the guarded H controlled one-shot
4. run H-scoped health after terminal markers exist
5. resume scheduler ownership
6. confirm ownership is restored

Command shape:
```powershell
.\run_H_isolation_status.bat
.\run_H_isolation_pause.bat
.\run_H_isolation_success.bat
python scripts/flows/A/A015_build_system_health_check.py --profile h --no-toast
.\run_H_isolation_resume.bat
```

Do not:
- overlap the controlled proof with a live H owner
- read H health before the controlled run finalizes
- rely on history-wide append logs when the health rule is supposed to score the latest run only

## Read-only planning helper

Use this helper before runtime proof when the boundary is unclear:

```powershell
python scripts/one_off/P002_plan_forced_proof_window.py --flow h
python scripts/one_off/P002_plan_forced_proof_window.py --flow b --format json
```

What it does:
- reads current lock and marker state
- identifies the safe proof mode for the flow
- lists the preflight checks
- prints the command sequence
- tells you whether the next step is ready now or needs a boundary or pause first

What it does not do:
- it does not run the proof
- it does not change locks
- it does not change scheduler ownership

## Allowed fallback

Next scheduled cycle waiting is fallback only.

Use it only when:
- there is no safe forced proof path yet
- the owner cannot be paused or handed off safely
- the user declines the forced proof run
- the proof depends on time-window sample volume, not on single-run correctness

If forced proof is blocked, record:
- exact blocker
- exact boundary required
- exact command or artifact that will resume proof

Do not write a vague line such as `wait for the next scheduled cycle`.
