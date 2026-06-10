# SO21 Overnight Control Test Plan

Created: 2026-06-08
Window: evening of 2026-06-08 to before the expected 02:00 UK PC restart on 2026-06-09
Mode: read-only and planning/control tests only

## Plain-English Purpose

Use the quiet overnight window to test the new management layer without touching the live business.

The PC is expected to restart at 02:00 UK time on Tuesday, 9 June 2026. Tests must either finish before that restart or leave a clear post-restart check.

## What Can Be Tested Tonight

- Current-state regeneration.
- Current-ticket and backlog regeneration.
- Scheduler-state reconciliation evidence as read-only.
- Runtime-status read-only design review.
- Maintenance-record spec review.
- Cleanup apply proof/status tidy-up.
- Whether Operations logs blockers properly.
- Whether active control automations are visible and classified.

## What Must Not Be Tested Tonight

- Process killing.
- Business runtime pause or restart.
- Windows Task Scheduler enable, disable, edit, create, delete, or restart.
- Worker restart.
- Amazon login or security.
- Price changes.
- Google Sheets writes.
- Database writes or alignment.
- Output deletion.
- Purchase, receiving, or send-to-Amazon action.
- Maintenance scripts that change state.

## Timing Rules

- Before 01:30 UK: run only short read-only checks and planning reviews.
- By 01:45 UK: stop starting new checks that could be interrupted by the PC restart.
- At 02:00 UK: expect PC restart.
- After 02:15 UK, if the system is available again: run a read-only recovery check only.

## Post-Restart Recovery Check

After the expected restart, Operations should check:

- control files can still regenerate
- active automation list is readable
- no active maintenance record was left open
- no old manager-noise folder has reappeared as live control
- any Windows permission, locked-file, or connector issue is logged as a blocker

## Success Criteria

Tonight is successful if, by morning:

- cleanup proof/status is clearer
- runtime-status and maintenance-record designs have review evidence or clear gaps
- any blocker is written down with the affected job and safest proposed fix
- no protected business action occurred

## Stop Conditions

Stop and report a blocker before any action that would touch runtime, scheduler state, processes, workers, Amazon/security, prices, Sheets, databases, outputs, purchases, receiving, send-to-Amazon, or permanent deletion.
