# Out Structure Policy

## Goal
Keep `out/` navigable by enforcing ownership and placement rules.

## Top-level folders allowed
- `out/systems/` - system-owned runtime data
- `out/reviews/` - docs, audits, runbooks
- `out/manifests/` - cycle manifests
- `out/golden_runs/` - regression baselines
- `out/process_guides/` - process documentation
- `out/waiting_room/` - staging/quarantine
- `out/locks/` - lock files only
- `out/cycle_alerts/` - health check outputs

## System folders
Each system must use:
- `out/systems/<SYSTEM>/live/`
- `out/systems/<SYSTEM>/archive/`
- `out/systems/<SYSTEM>/todo/`

Current systems:
- `A`
- `B`
- `E`
- `H`
- `shared`

## Placement rules
- New files must not be written to `out/` root.
- Runtime scripts may keep legacy root writes only during migration windows.
- Every moved file batch must include a rollback manifest.

## Archive rules
- One-off diagnostics, debug dumps, and manual reconciliation files belong under `archive/`.
- Archive folder names should include UTC timestamp, for example `legacy_root_dump_YYYYMMDDTHHMMSSZ`.

## Migration policy
- Phase 1: move safe clutter only (no runtime dependencies).
- Phase 2: update writers to target `out/systems/<SYSTEM>/live/`.
- Phase 3: remove legacy root writes after 10 clean runs.
