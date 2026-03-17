# Operational Rules

## Allowed Operational Entrypoints
- `run_A_all.bat`
- `run_B_cycle.bat`
- `run_H_cycle.bat`
- `run_E_all.bat`

These are the only approved day-to-day launch points.

## Forbidden in Daily Operations
- Do not run `scripts/one_off/*` inside daily loops.
- Do not bypass the `.bat` entrypoints with direct script calls for routine cycles.

## Lock and Maintenance Handshake
- Before manual B maintenance or any manual B script run, check `out/B_cycle.lock`.
- If B is active, request maintenance by creating `out/locks/maintenance.requested` and wait for `out/locks/maintenance.ready`.
- A cycle must set `out/locks/maintenance.active` during maintenance work and clear flags when done.
- Legacy pause flag `out/locks/b_cycle.maintenance` is supported for manual pauses.

## Evidence Requirement for Changes
- Any operational change must include:
  - evidence
  - acceptance check
  - rollback step
