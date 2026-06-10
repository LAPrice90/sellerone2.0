# CODING_PLAN - MOT 2026-04-28 Long Weekend

## Current Phase
- Phase: B shortage classification patch isolated-tested; live-owner verification in progress
- Started: 2026-04-28
- Scope: A inventory/token gap, B token shortage health, F supplier price list scan ownership.

## Allowed Files For This Phase
- Read-only investigation across `scripts/`, `tests/`, `out/`, `data/`, `project_control/`, and active plans.
- File edits allowed only after root cause is clear.
- Classification edits allowed in `scripts/flows/B/B007_allocate_tokens_live.py`, `scripts/flows/A/A015_build_system_health_check.py`, and focused tests.
- No Google Sheets writes unless explicitly approved.
- No local DB alignment changes unless explicitly approved.
- Do not edit `WORK_LOG.md` unless the user approves the final change log entry.

## Tests And Proof
- A-owned proof must use the owned A cycle path, not `A015_build_system_health_check.py` alone.
- B-owned proof must respect B lock/maintenance safety and read B health only after finalization.
- F proof must show either active ownership restored or a truthful terminal state for the scan.

## Live Monitoring Target
- `out/cycle_alerts/checklist_A_split.csv`
- `out/cycle_alerts/checklist_B_split.csv`
- `out/systems/F/inbox/supplier_price_list_run_state.csv`
- `out/systems/F/live/f061_hometime.log`
- `out/systems/F/live/f061_hometime_components.log`

## Poll Cadence
- During live validation: first check at +5 minutes, second at +10 minutes, then every +15 minutes.
- Stop at +60 minutes unless a later bounded proof window is documented.

## Success Threshold
- A: `a_inventory_stale_token_gap` is `ok`, or a clear non-code upstream blocker is documented.
- B: `token_shortages_by_sku` remains truthful and includes shortage classes/action notes; remaining shortages are proven real and non-fixable without stock/token source approval.
- F: scan state and runtime ownership agree, with new `f061_hometime.log` movement after restarting the existing resumable wrapper.

## Timeout Rule
- If proof cannot complete inside the bounded window, record exact evidence and set status to `parked pending next proof window`.

## Automatic Next Step
- If A/B root cause is clear and fix is within repo/local-output boundaries, apply the smallest fix and run the relevant boundary-safe proof.
- If F has a dead running marker with no owner, restart only `run_F_supplier_full_legacy_scan.bat stocklist_supplier`; do not reset the queue.
- If a forced B proof worker would overlap the live owner, stop the proof worker and use the next live B-owned finalize as verification.
