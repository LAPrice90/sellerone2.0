# Runbook

## Purpose
- explain how the new-product commercial launch process should work from live supplier file to monitored test orders

## Core operating stance
- this is a conservative selector, not an exact predictor
- lower-band logic controls starter quantity
- the user keeps veto power before any new-product order is released
- one supplier wave should be kept under control before widening to another

## Start-to-finish process
1. Confirm the active supplier wave.
- Read `out/systems/F/inbox/supplier_price_list_queue_state.csv`.
- Confirm which supplier file is actually live.

2. Confirm no overlapping screening owner is running.
- Do not run overlapping `F061` work.
- If an `F061` worker is already active, use that owner path instead of starting a second one.

3. Freeze the launch baseline.
- Record current counts for:
  - raw rows
  - canonical rows
  - pending rows
  - timeout rows
  - pass rows
  - rescan rows
- Mark stale recommendation and approval surfaces as unsafe if they do not match the active supplier wave.

4. Refresh the screening truth in controlled windows.
- Do not run uncontrolled open-ended refreshes.
- Refresh in bounded windows and recheck counts after each window.
- Keep the supplier wave fixed while the launch baseline is being built.

5. Build the pass review pack.
- Show:
  - candidate identity
  - why it passed
  - lower/expected/upper band
  - conservative starter quantity
  - commercial notes

6. Build the near-miss review pack.
- Show:
  - first blocker
  - blocker family
  - whether it is a borderline review case or a hard reject
  - what would need to change for it to be reconsidered

7. User commercial review.
- Review pass rows first.
- Review near-miss rows second.
- For each row, the user can choose:
  - test
  - watch
  - reject

8. Build the release shortlist.
- Include only user-approved rows.
- Keep starter quantities conservative.
- Do not mix in watch or reject rows.

9. Prepare controlled PO handoff.
- Build handoff-ready rows only for approved candidates.
- Keep all release counts explicit.

10. Monitor the launch cohort.
- Review at:
  - 14 days
  - 30 days
  - 60 days
- Judge the outcome using bands:
  - did it clear the lower band
  - did it stay commercially healthy
  - did it show negative-mode behaviour

11. Tune from repeated evidence only.
- Do not rewrite pass logic from one odd result.
- Adjust only when the same commercial mistake repeats.

## Keep-reins rules
- one active supplier wave at a time for launch review
- one launch baseline pack per wave
- one pass pack and one near-miss pack per review cycle
- one explicit user decision before release
- one controlled test-order release, not a full buying jump
- one monitoring pack for the launch cohort

## Stop conditions
- stop if the active supplier wave changes mid-review
- stop if current screening truth and review pack counts do not reconcile
- stop if stale recommendation outputs are being treated as current launch truth
- stop if PO handoff includes rows that were not explicitly approved

## Not allowed
- no exact-forecast worship
- no hidden optimism in starter quantity
- no auto-release from pass directly into buying
- no second supplier launch wave before the first wave has review and monitoring in place
