# TASK B Backdate Recovery Proof Builder

Status: proposed

## Goal
Build the read-only worker path that can check all Amazon marketplaces from 2025-11-01 and write recovered order evidence into quarantine only.

## Manager Expectation
The worker must fetch or inspect order proof by marketplace and date window, then output quarantine rows labelled as `API proved`, `Sellerboard bridge estimate`, or `not yet proven`.

## Allowed Scope
- B backdate scanner code
- recovery quarantine proof output design
- manager report and MOT integration
- tests for missing order recovery proof

## Forbidden Actions
- no live B run
- no B restart
- no shared marker edit
- no per-marketplace marker edit during proof build
- no Google Sheets write
- no local DB alignment
- no output deletion
- no live order merge
- no ROI or restocking use
- no token, refund, fee, shipping, or order correction
- no price or queue change

## Acceptance Checks
- Scanner can run in read-only/quarantine mode.
- It checks all Amazon marketplaces from 2025-11-01.
- It does not write live B outputs.
- It does not update shared order markers.
- Missing Sellerboard shipped orders become API-proved in quarantine only when API evidence exists.
- If API evidence is unavailable, the order remains `not yet proven`.

## Retest Rule
Retest with the B independent MOT and confirm `b_backdate_recovery_quarantine` clears.

## Stop Condition
Stop and return to Luke before any live B run, backfill into live outputs, marker edit, Sheet write, local DB alignment, output deletion, or live ROI/restocking use.
